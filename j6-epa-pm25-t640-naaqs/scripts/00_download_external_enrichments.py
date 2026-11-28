"""Step 00: Download and cache all official external enrichments for J6 /boost.

Enrichments downloaded into data/raw_enrichment/ and processed into data/processed/:
  1. EPA AQS Speciation (daily_SPEC_{2023,2024,2025}.zip)
  2. EPA AQS Meteorology (daily_TEMP_{2023,2024,2025}.zip, daily_RH_DP_{2023,2024,2025}.zip)
  3. Official EPA PM2.5 Design Value Excel workbooks from epa.gov/air-trends/air-quality-design-values
  4. Census ACS 5-Year (2023) county demographics (population, median income, poverty, race/ethnicity)
  5. NOAA HMS Daily Wildfire Smoke Plume Polygons (2018-2025) spatially intersected with all
     EPA 88101 monitoring site coordinates via shapely STRtree into compact per-year & combined parquets.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import time
import urllib.parse
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import requests
import shapefile
from econ_utils import (
    ENRICH_DIR,
    PROC_DIR,
    RES_DIR,
    VALID_STATES,
    WAVE6_RAW_DIR,
    read_zip_csv,
    save_json_lf,
)
from shapely import STRtree, make_valid
from shapely.geometry import Point, shape

HEADERS = {"User-Agent": "J6BoostEPAPm25Study/1.0 (academic atmospheric & economic research)"}


def download_file(url: str, dest: Path, min_bytes: int = 1000, retries: int = 3) -> dict[str, Any]:
    """Download a file with caching, polite UA, timeout=60, and exponential backoff."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        return {"url": url, "path": str(dest), "bytes": int(dest.stat().st_size), "cached": True}

    last_err = ""
    for attempt in range(1, retries + 1):
        try:
            r = requests.get(url, headers=HEADERS, timeout=60, stream=True)
            if r.status_code == 200:
                chunks = []
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        chunks.append(chunk)
                data = b"".join(chunks)
                if len(data) < min_bytes:
                    last_err = f"Too small ({len(data)} bytes)"
                else:
                    dest.write_bytes(data)
                    return {"url": url, "path": str(dest), "bytes": len(data), "cached": False}
            else:
                last_err = f"HTTP {r.status_code}"
        except (requests.RequestException, OSError, ValueError) as exc:
            last_err = str(exc)
        time.sleep(min(2**attempt, 8))
    raise RuntimeError(f"Failed downloading {url}: {last_err}")


def fetch_epa_airdata() -> dict[str, Any]:
    """Download EPA AQS Speciation, Temperature, and RH/Dewpoint zips for 2023-2025."""
    out: dict[str, Any] = {}
    base = "https://aqs.epa.gov/aqsweb/airdata"
    files = [
        f"daily_SPEC_{yr}.zip" for yr in (2023, 2024, 2025)
    ] + [
        f"daily_TEMP_{yr}.zip" for yr in (2023, 2024, 2025)
    ] + [
        f"daily_RH_DP_{yr}.zip" for yr in (2023, 2024, 2025)
    ]
    for fname in files:
        dest = ENRICH_DIR / fname
        info = download_file(f"{base}/{fname}", dest, min_bytes=50_000)
        out[fname] = info
        print(
            f"  [EPA AirData] {fname}: {info['bytes']/1e6:.2f} MB (cached={info['cached']})",
            flush=True,
        )
    return out


def fetch_epa_dv_workbooks() -> dict[str, Any]:
    """Scrape epa.gov/air-trends/air-quality-design-values and download official PM2.5 DV workbooks."""
    page_url = "https://www.epa.gov/air-trends/air-quality-design-values"
    r = requests.get(page_url, headers=HEADERS, timeout=60)
    r.raise_for_status()
    raw_links = sorted(
        set(re.findall(r'href=["\']([^"\']*pm25[^"\']*\.xlsx?)["\']', r.text, flags=re.IGNORECASE))
    )
    print(f"  [EPA DV Page] Found {len(raw_links)} PM2.5 workbook links", flush=True)

    downloaded: dict[str, Any] = {}
    for href in raw_links:
        full_url = urllib.parse.urljoin(page_url, href)
        fname = Path(urllib.parse.urlparse(full_url).path).name
        # Prioritize recent 2021-2025 design value workbooks
        if any(tag in fname.lower() for tag in ("2023", "2024", "2025", "2022", "2021")):
            dest = ENRICH_DIR / "epa_dv" / fname
            try:
                info = download_file(full_url, dest, min_bytes=10_000)
                downloaded[fname] = info
                print(
                    f"  [EPA DV] {fname}: {info['bytes']/1e6:.2f} MB (cached={info['cached']})",
                    flush=True,
                )
            except (RuntimeError, requests.RequestException, OSError, ValueError) as exc:
                downloaded[fname] = {"url": full_url, "error": str(exc)}
                print(f"  [EPA DV WARN] {fname}: {exc}", flush=True)
    return {"page_url": page_url, "all_links": raw_links, "downloaded": downloaded}


def fetch_census_demographics() -> dict[str, Any]:
    """Download official U.S. Census Bureau county demographics (no API key required):
      - 2023 SAIPE (est23all.xls): official county Median Household Income & Poverty Rate
      - 2024 County Population Characteristics (cc-est2024-alldata.csv): official county
        Total Population, Non-Hispanic White, Non-Hispanic Black, and Hispanic counts.
    """
    saipe_url = "https://www2.census.gov/programs-surveys/saipe/datasets/2023/2023-state-and-county/est23all.xls"
    saipe_dest = ENRICH_DIR / "saipe_est23all.xls"
    saipe_info = download_file(saipe_url, saipe_dest, min_bytes=100_000)
    print(
        f"  [Census SAIPE 2023] {saipe_dest.name}: {saipe_info['bytes']/1e6:.2f} MB (cached={saipe_info['cached']})",
        flush=True,
    )

    pep_url = "https://www2.census.gov/programs-surveys/popest/datasets/2020-2024/counties/asrh/cc-est2024-alldata.csv"
    pep_dest = ENRICH_DIR / "cc-est2024-alldata.csv"
    pep_info = download_file(pep_url, pep_dest, min_bytes=5_000_000)
    print(
        f"  [Census PEP ASRH 2024] {pep_dest.name}: {pep_info['bytes']/1e6:.2f} MB (cached={pep_info['cached']})",
        flush=True,
    )

    # Parse SAIPE 2023 Excel (skip metadata rows to locate 'State FIPS Code')
    raw_xl = pd.read_excel(saipe_dest, sheet_name=0, header=None, dtype=str)
    hdr_idx = None
    for idx in range(min(15, len(raw_xl))):
        row_txt = " ".join(str(x or "").lower() for x in raw_xl.iloc[idx].tolist())
        if "state fips" in row_txt and "county fips" in row_txt:
            hdr_idx = idx
            break
    if hdr_idx is None:
        raise RuntimeError("Could not locate header row in saipe_est23all.xls")
    headers = [str(x).strip() for x in raw_xl.iloc[hdr_idx].tolist()]
    sdf = raw_xl.iloc[hdr_idx + 1 :].copy()
    sdf.columns = headers
    st_col = next(c for c in headers if "state fips" in c.lower())
    cn_col = next(c for c in headers if "county fips" in c.lower())
    nm_col = next(c for c in headers if c.lower() == "name")
    pov_col = next(c for c in headers if "poverty percent, all ages" in c.lower())
    inc_col = next(c for c in headers if "median household income" in c.lower() and "90%" not in c.lower())

    sdf["state_fips"] = sdf[st_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.zfill(2)
    sdf["cnty_part"] = sdf[cn_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.zfill(3)
    sdf = sdf[(sdf["state_fips"].isin(VALID_STATES)) & (sdf["cnty_part"] != "000")].copy()
    sdf["county_fips"] = sdf["state_fips"] + sdf["cnty_part"]
    sdf["NAME"] = sdf[nm_col].astype(str).str.strip()
    sdf["poverty_rate"] = pd.to_numeric(sdf[pov_col], errors="coerce")
    sdf["median_hh_income"] = pd.to_numeric(sdf[inc_col], errors="coerce")
    sdf = sdf[["county_fips", "state_fips", "NAME", "median_hh_income", "poverty_rate"]].drop_duplicates("county_fips")

    # Parse PEP cc-est2024-alldata.csv (AGEGRP==0 all ages, max YEAR = July 1, 2024)
    use_pep = [
        "STATE",
        "COUNTY",
        "YEAR",
        "AGEGRP",
        "TOT_POP",
        "NHWA_MALE",
        "NHWA_FEMALE",
        "NHBA_MALE",
        "NHBA_FEMALE",
        "H_MALE",
        "H_FEMALE",
    ]
    pdf = pd.read_csv(
        pep_dest,
        encoding="latin1",
        usecols=use_pep,
        dtype={"STATE": str, "COUNTY": str},
    )
    max_yr = int(pdf["YEAR"].max())
    pdf = pdf[(pdf["YEAR"] == max_yr) & (pdf["AGEGRP"] == 0)].copy()
    pdf["state_fips"] = pdf["STATE"].str.zfill(2)
    pdf = pdf[pdf["state_fips"].isin(VALID_STATES)].copy()
    pdf["county_fips"] = pdf["state_fips"] + pdf["COUNTY"].str.zfill(3)
    pdf["acs_pop"] = pd.to_numeric(pdf["TOT_POP"], errors="coerce")
    nhwa = pd.to_numeric(pdf["NHWA_MALE"], errors="coerce") + pd.to_numeric(pdf["NHWA_FEMALE"], errors="coerce")
    nhba = pd.to_numeric(pdf["NHBA_MALE"], errors="coerce") + pd.to_numeric(pdf["NHBA_FEMALE"], errors="coerce")
    hisp = pd.to_numeric(pdf["H_MALE"], errors="coerce") + pd.to_numeric(pdf["H_FEMALE"], errors="coerce")
    pdf["pct_white_nh"] = 100.0 * nhwa / pdf["acs_pop"]
    pdf["pct_black_nh"] = 100.0 * nhba / pdf["acs_pop"]
    pdf["pct_hispanic"] = 100.0 * hisp / pdf["acs_pop"]
    pdf["pct_nonwhite"] = 100.0 - pdf["pct_white_nh"]

    merged = sdf.merge(
        pdf[
            [
                "county_fips",
                "acs_pop",
                "pct_black_nh",
                "pct_hispanic",
                "pct_nonwhite",
                "pct_white_nh",
            ]
        ],
        on="county_fips",
        how="inner",
    )

    out_pq = PROC_DIR / "acs5_2023_counties.parquet"
    out_pq.parent.mkdir(parents=True, exist_ok=True)
    merged.to_parquet(out_pq, index=False)
    print(
        f"  [Census SAIPE 2023 + PEP 2024] {len(merged):,} U.S. counties saved -> {out_pq.name} "
        f"(total pop={merged['acs_pop'].sum()/1e6:.2f}M, PEP YEAR code={max_yr})",
        flush=True,
    )
    return {
        "source": "U.S. Census Bureau SAIPE 2023 (income/poverty) + PEP 2024 ASRH (race/ethnicity/pop)",
        "saipe_info": saipe_info,
        "pep_info": pep_info,
        "parquet": str(out_pq),
        "n_counties": len(merged),
        "total_pop_millions": float(merged["acs_pop"].sum() / 1e6),
    }


def load_all_pm25_site_coords() -> pd.DataFrame:
    """Collect unique (site_id, lat, lon) across all EPA 88101 monitors/sites."""
    mons = read_zip_csv(
        WAVE6_RAW_DIR / "aqs_monitors.zip",
        usecols=["State Code", "County Code", "Site Number", "Parameter Code", "Latitude", "Longitude"],
        dtype=str,
    )
    mons = mons[mons["Parameter Code"] == "88101"].copy()
    mons["state_fips"] = mons["State Code"].str.zfill(2)
    mons = mons[mons["state_fips"].isin(VALID_STATES)].copy()
    mons["site_id"] = (
        mons["state_fips"] + mons["County Code"].str.zfill(3) + "-" + mons["Site Number"].str.zfill(4)
    )
    mons["lat"] = pd.to_numeric(mons["Latitude"], errors="coerce")
    mons["lon"] = pd.to_numeric(mons["Longitude"], errors="coerce")
    sites = (
        mons.dropna(subset=["lat", "lon"])
        .groupby("site_id", as_index=False)
        .agg(lat=("lat", "first"), lon=("lon", "first"))
    )

    # Supplement with aqs_sites.zip for any missing site coordinates
    asites = read_zip_csv(
        WAVE6_RAW_DIR / "aqs_sites.zip",
        usecols=["State Code", "County Code", "Site Number", "Latitude", "Longitude"],
        dtype=str,
    )
    asites["state_fips"] = asites["State Code"].str.zfill(2)
    asites = asites[asites["state_fips"].isin(VALID_STATES)].copy()
    asites["site_id"] = (
        asites["state_fips"] + asites["County Code"].str.zfill(3) + "-" + asites["Site Number"].str.zfill(4)
    )
    asites["lat"] = pd.to_numeric(asites["Latitude"], errors="coerce")
    asites["lon"] = pd.to_numeric(asites["Longitude"], errors="coerce")
    asites = asites.dropna(subset=["lat", "lon"]).drop_duplicates("site_id")[["site_id", "lat", "lon"]]

    combined = pd.concat([sites, asites], ignore_index=True).drop_duplicates("site_id")
    # Keep only sites that ever appear in 88101 monitors OR annual files
    ann_sites: set[str] = set(sites["site_id"])
    for yr in range(2018, 2026):
        a = read_zip_csv(
            WAVE6_RAW_DIR / f"annual_conc_by_monitor_{yr}.zip",
            usecols=["State Code", "County Code", "Site Num", "Parameter Code"],
            dtype=str,
        )
        a = a[a["Parameter Code"] == "88101"]
        sf = a["State Code"].str.zfill(2)
        a = a[sf.isin(VALID_STATES)]
        sids = sf[sf.isin(VALID_STATES)] + a["County Code"].str.zfill(3) + "-" + a["Site Num"].str.zfill(4)
        ann_sites.update(sids.unique())

    final = combined[combined["site_id"].isin(ann_sites)].reset_index(drop=True)
    # Filter clearly invalid coordinates (0, 0)
    final = final[(final["lat"].abs() > 1.0) & (final["lon"].abs() > 1.0)].reset_index(drop=True)
    final.to_parquet(PROC_DIR / "pm25_site_coords.parquet", index=False)
    return final


def _parse_hms_density(val: Any) -> int:
    """Parse NOAA HMS polygon Density attribute into 1=Light, 2=Medium, 3=Heavy (0=Unknown)."""
    if val is None:
        return 0
    s = str(val).strip().lower()
    if not s:
        return 0
    if "heavy" in s or "thick" in s:
        return 3
    if "med" in s:
        return 2
    if "light" in s or "thin" in s:
        return 1
    try:
        v = float(s)
        if v >= 21.0:
            return 3
        if v >= 10.0:
            return 2
        if v > 0.0:
            return 1
    except ValueError:
        pass
    return 1  # Conservative fallback: smoke polygon present -> at least Light


def _fetch_one_hms_day(
    day: dt.date,
    session: requests.Session,
    site_ids: np.ndarray,
    tree: STRtree,
) -> tuple[str, str, list[tuple[str, str, int, int, int, int]]]:
    """Fetch one day's NOAA HMS smoke shapefile and intersect with all EPA PM2.5 sites."""
    ymd = day.strftime("%Y%m%d")
    iso = day.strftime("%Y-%m-%d")
    url = (
        f"https://satepsanone.nesdis.noaa.gov/pub/FIRE/web/HMS/Smoke_Polygons/Shapefile/"
        f"{day.year}/{day.month:02d}/hms_smoke{ymd}.zip"
    )
    for attempt in range(1, 4):
        try:
            r = session.get(url, headers=HEADERS, timeout=45)
            if r.status_code == 404:
                return iso, "404", []
            if r.status_code != 200:
                if attempt < 3:
                    time.sleep(attempt)
                    continue
                return iso, f"http_{r.status_code}", []
            if len(r.content) < 100:
                return iso, "empty", []

            with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
                names = zf.namelist()
                shps = [n for n in names if n.lower().endswith(".shp")]
                dbfs = [n for n in names if n.lower().endswith(".dbf")]
                if not shps or not dbfs:
                    return iso, "no_shp", []
                sf = shapefile.Reader(
                    shp=io.BytesIO(zf.read(shps[0])),
                    dbf=io.BytesIO(zf.read(dbfs[0])),
                )
                hit_map: dict[int, list[int]] = {}
                for sr in sf.iterShapeRecords():
                    rec = sr.record.as_dict()
                    dens_raw = rec.get("Density", rec.get("DENSITY", rec.get("density", None)))
                    lvl = _parse_hms_density(dens_raw)
                    if lvl <= 0:
                        continue
                    try:
                        geom = shape(sr.shape.__geo_interface__)
                        if not geom.is_valid:
                            geom = make_valid(geom)
                        idxs = tree.query(geom, predicate="intersects")
                        for idx in idxs:
                            i = int(idx)
                            if i not in hit_map:
                                hit_map[i] = [0, 0, 0]
                            hit_map[i][lvl - 1] = 1
                    except (ValueError, TypeError, AttributeError) as geom_exc:
                        _ = geom_exc

            rows = [
                (
                    str(site_ids[i]),
                    iso,
                    flags[0],
                    flags[1],
                    flags[2],
                    3 if flags[2] else (2 if flags[1] else 1),
                )
                for i, flags in hit_map.items()
            ]
            return iso, "ok", rows
        except (requests.RequestException, zipfile.BadZipFile, OSError, ValueError, KeyError):
            if attempt < 3:
                time.sleep(attempt)
                continue
            return iso, "err", []
    return iso, "err", []


def fetch_noaa_hms_all_years(years: list[int]) -> dict[str, Any]:
    """Fetch NOAA HMS daily wildfire smoke polygons across full calendar years 2018-2025."""
    sites = load_all_pm25_site_coords()
    print(f"  [NOAA HMS] Loaded {len(sites):,} unique EPA PM2.5 site coordinates", flush=True)

    pts = [Point(lon, lat) for lon, lat in zip(sites["lon"].to_numpy(), sites["lat"].to_numpy())]
    tree = STRtree(pts)
    site_ids = sites["site_id"].to_numpy()

    hms_dir = ENRICH_DIR / "hms_yearly"
    hms_dir.mkdir(parents=True, exist_ok=True)
    year_stats: dict[str, Any] = {}
    all_dfs: list[pd.DataFrame] = []

    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)

    for yr in years:
        pq_yr = hms_dir / f"hms_monitor_daily_{yr}.parquet"
        meta_yr = hms_dir / f"hms_monitor_daily_{yr}.meta.json"
        if pq_yr.exists() and meta_yr.exists():
            df_yr = pd.read_parquet(pq_yr)
            st = json.loads(meta_yr.read_text(encoding="utf-8"))
            st["cached"] = True
            year_stats[str(yr)] = st
            all_dfs.append(df_yr)
            print(
                f"  [NOAA HMS {yr}] Cached: {len(df_yr):,} smoke site-days "
                f"(ok={st['days_ok']}, 404={st['days_404']}, err={st['days_err']})",
                flush=True,
            )
            continue

        start = dt.date(yr, 1, 1)
        end = dt.date(yr, 12, 31)
        days = [start + dt.timedelta(days=k) for k in range((end - start).days + 1)]
        t0 = time.time()
        yr_rows: list[tuple[str, str, int, int, int, int]] = []
        status_cnt = {"ok": 0, "404": 0, "other": 0}

        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(_fetch_one_hms_day, d, session, site_ids, tree) for d in days]
            for fut in as_completed(futs):
                _, status, rows = fut.result()
                if status == "ok":
                    status_cnt["ok"] += 1
                    if rows:
                        yr_rows.extend(rows)
                elif status == "404":
                    status_cnt["404"] += 1
                else:
                    status_cnt["other"] += 1

        df_yr = pd.DataFrame(
            yr_rows,
            columns=["site_id", "date", "hms_light", "hms_medium", "hms_heavy", "hms_max_level"],
        )
        if len(df_yr):
            df_yr["hms_light"] = df_yr["hms_light"].astype(np.int8)
            df_yr["hms_medium"] = df_yr["hms_medium"].astype(np.int8)
            df_yr["hms_heavy"] = df_yr["hms_heavy"].astype(np.int8)
            df_yr["hms_max_level"] = df_yr["hms_max_level"].astype(np.int8)
            df_yr = df_yr.sort_values(["date", "site_id"]).reset_index(drop=True)
        df_yr.to_parquet(pq_yr, index=False)

        st = {
            "year": yr,
            "n_days_total": len(days),
            "days_ok": status_cnt["ok"],
            "days_404": status_cnt["404"],
            "days_err": status_cnt["other"],
            "smoke_site_days": len(df_yr),
            "heavy_site_days": int(df_yr["hms_heavy"].sum()) if len(df_yr) else 0,
            "elapsed_sec": round(time.time() - t0, 1),
            "cached": False,
        }
        save_json_lf(meta_yr, st)
        year_stats[str(yr)] = st
        all_dfs.append(df_yr)
        print(
            f"  [NOAA HMS {yr}] Done in {st['elapsed_sec']}s: {st['smoke_site_days']:,} smoke site-days "
            f"(heavy={st['heavy_site_days']:,}, ok={st['days_ok']}, 404={st['days_404']}, err={st['days_err']})",
            flush=True,
        )

    combined = pd.concat(all_dfs, ignore_index=True) if all_dfs else pd.DataFrame()
    out_all = PROC_DIR / "monitor_hms_daily_2018_2025.parquet"
    combined.to_parquet(out_all, index=False)
    return {
        "n_sites_indexed": len(sites),
        "combined_parquet": str(out_all),
        "total_smoke_site_days": len(combined),
        "total_heavy_site_days": int(combined["hms_heavy"].sum()) if len(combined) else 0,
        "by_year": year_stats,
    }


def main() -> int:
    print("=== STEP 00: DOWNLOAD & CACHE ALL EXTERNAL ENRICHMENTS ===", flush=True)
    ENRICH_DIR.mkdir(parents=True, exist_ok=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    audit: dict[str, Any] = {}
    audit["epa_airdata"] = fetch_epa_airdata()
    audit["epa_dv_workbooks"] = fetch_epa_dv_workbooks()
    audit["census_demographics"] = fetch_census_demographics()
    audit["noaa_hms_2018_2025"] = fetch_noaa_hms_all_years(list(range(2018, 2026)))

    sha = save_json_lf(RES_DIR / "00_enrichment_audit.json", audit)
    print(f"\n[DONE STEP 00] Saved results/00_enrichment_audit.json (SHA-256 LF: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
