"""Step 2: Full 48-state CONUS clean river daily-value (DV) census (2005-2025) from USGS NWIS (polite batch queries)."""
from __future__ import annotations

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
DV_DIR = BASE_DIR / "data" / "raw_usgs_dv"
NID_PATH = BASE_DIR / "data" / "raw_nid" / "nid_conus_dams.parquet"
PROC_DIR = BASE_DIR / "data" / "processed"
UA = {"User-Agent": "AcademicResearch-NocturnalRiverHypoxiaAudit/2.0 (contact: hydrology-audit@research.org)"}
BATCH_SIZE = 8


def _latlon_to_ecef_km(lat_deg: np.ndarray, lon_deg: np.ndarray) -> np.ndarray:
    r_earth = 6371.0088
    lat_r = np.radians(lat_deg)
    lon_r = np.radians(lon_deg)
    cos_lat = np.cos(lat_r)
    return np.column_stack([r_earth * cos_lat * np.cos(lon_r), r_earth * cos_lat * np.sin(lon_r), r_earth * np.sin(lat_r)])


def attach_nid_dam_distances(clean_vdf: pd.DataFrame) -> pd.DataFrame:
    """Attach exact geodesic distance (km) from each USGS gauge to nearest USACE NID dams."""
    from scipy.spatial import cKDTree

    out = clean_vdf.copy()
    if not NID_PATH.exists():
        NID_PATH.parent.mkdir(parents=True, exist_ok=True)
        r = requests.get("https://nid.sec.usace.army.mil/api/nation/csv", headers=UA, timeout=(15, 120))
        r.raise_for_status()
        lines = r.text.splitlines()
        skip = 1 if ("Latitude" not in lines[0] and len(lines) > 1 and "Latitude" in lines[1]) else 0
        raw_nid = pd.read_csv(io.StringIO(r.text), skiprows=skip, low_memory=False)
        nid = pd.DataFrame(
            {
                "nid_id": raw_nid.get("NID ID", ""),
                "dam_name": raw_nid.get("Dam Name", ""),
                "state": raw_nid.get("State", ""),
                "lat": pd.to_numeric(raw_nid.get("Latitude"), errors="coerce"),
                "lon": pd.to_numeric(raw_nid.get("Longitude"), errors="coerce"),
                "dam_height_ft": pd.to_numeric(raw_nid.get("Dam Height (Ft)"), errors="coerce"),
                "max_storage_af": pd.to_numeric(raw_nid.get("Max Storage (Acre-Ft)"), errors="coerce"),
            }
        ).dropna(subset=["lat", "lon"])
        nid = nid[nid["lat"].between(24.0, 50.0) & nid["lon"].between(-126.0, -66.0)].reset_index(drop=True)
        nid.to_parquet(NID_PATH, index=False)
    else:
        nid = pd.read_parquet(NID_PATH)

    g_xyz = _latlon_to_ecef_km(out["lat"].astype(float).values, out["lon"].astype(float).values)
    r_earth = 6371.0088

    def nearest_km(dam_sub: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
        d_xyz = _latlon_to_ecef_km(dam_sub["lat"].values, dam_sub["lon"].values)
        tree = cKDTree(d_xyz)
        chord, idx = tree.query(g_xyz, k=1)
        # Convert 3D chord length to exact great-circle arc distance
        arc_km = 2.0 * r_earth * np.arcsin(np.clip(chord / (2.0 * r_earth), 0.0, 1.0))
        return arc_km, dam_sub["dam_name"].astype(str).values[idx]

    d_any, _ = nearest_km(nid)
    d_500, _ = nearest_km(nid[nid["max_storage_af"].fillna(0) >= 500.0])
    d_5000, nm_5000 = nearest_km(nid[nid["max_storage_af"].fillna(0) >= 5000.0])
    out["nid_dist_any_km"] = np.round(d_any, 3)
    out["nid_dist_ge500af_km"] = np.round(d_500, 3)
    out["nid_dist_ge5000af_km"] = np.round(d_5000, 3)
    out["nearest_nid_5000af_dam"] = nm_5000
    return out


def fetch_rdb_polite(url: str, timeout: tuple[int, int] = (15, 75)) -> str | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 150:
                return r.text
            if r.status_code in (400, 404):
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(3.0 * (attempt + 1))
            else:
                return None
        except requests.RequestException:
            time.sleep(3.0 * (attempt + 1))
    return None


def split_multi_site_rdb(text: str) -> dict[str, list[str]]:
    """Split concatenated USGS multi-site RDB text into {site_no: [header, types, rows...]}."""
    blocks: list[list[str]] = []
    cur: list[str] = []
    for ln in text.splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        if ln.startswith("agency_cd\tsite_no\t"):
            if cur:
                blocks.append(cur)
            cur = [ln]
        elif cur:
            cur.append(ln)
    if cur:
        blocks.append(cur)

    by_site: dict[str, list[str]] = {}
    for blk in blocks:
        if len(blk) < 3:
            continue
        parts = blk[2].split("\t")
        if len(parts) < 2:
            continue
        sno = parts[1].strip()
        by_site[sno] = blk
    return by_site


def parse_dv_block(lines: list[str]) -> pd.DataFrame | None:
    if len(lines) < 3:
        return None
    hdr = lines[0].split("\t")
    if "datetime" not in hdr:
        return None

    targets = [
        ("do_max", "_00300_00001"),
        ("do_min", "_00300_00002"),
        ("do_mean", "_00300_00003"),
        ("temp_max", "_00010_00001"),
        ("temp_min", "_00010_00002"),
        ("temp_mean", "_00010_00003"),
        ("q_cfs", "_00060_00003"),
        ("spcond", "_00095_00003"),
        ("turb", "_63680_00003"),
    ]
    cand_cols: dict[str, list[str]] = {t: [] for t, _ in targets}
    use_cols = ["datetime"]
    for t, suffix in targets:
        for c in hdr:
            if c.endswith(suffix) and not c.endswith("_cd"):
                cand_cols[t].append(c)
                if c not in use_cols:
                    use_cols.append(c)

    if not all(cand_cols[k] for k in ("do_max", "do_min", "do_mean", "temp_mean")):
        return None

    raw = "\n".join([lines[0]] + lines[2:])
    df_raw = pd.read_csv(io.StringIO(raw), sep="\t", usecols=use_cols, low_memory=False)
    df_raw["datetime"] = pd.to_datetime(df_raw["datetime"], errors="coerce")
    df_raw = df_raw.dropna(subset=["datetime"]).drop_duplicates(subset=["datetime"]).set_index("datetime")

    out = pd.DataFrame(index=df_raw.index)
    for t, _ in targets:
        cols = cand_cols[t]
        if not cols:
            out[t] = np.nan
            continue
        best_s = None
        best_n = -1
        for c in cols:
            s = pd.to_numeric(df_raw[c], errors="coerce")
            s = s.where(s > -900.0)
            cnt = int(s.notna().sum())
            if cnt > best_n:
                best_n = cnt
                best_s = s
        out[t] = best_s if best_s is not None else np.nan
    return out.sort_index()


def clean_dv_frame(df: pd.DataFrame) -> pd.DataFrame:
    df = df.dropna(subset=["do_max", "do_min", "do_mean", "temp_mean"]).copy()
    mask = (
        df["do_min"].between(0.0, 25.0)
        & df["do_max"].between(0.0, 25.0)
        & df["do_mean"].between(0.0, 25.0)
        & df["temp_mean"].between(-2.0, 42.0)
        & (df["do_min"] <= df["do_mean"] + 0.15)
        & (df["do_mean"] <= df["do_max"] + 0.15)
        & ((df["do_max"] - df["do_min"]) <= 22.0)
    )
    df = df[mask].copy()
    for tc in ("temp_min", "temp_max"):
        if tc in df.columns:
            df[tc] = df[tc].where(df[tc].between(-2.0, 42.0))
    if "temp_min" in df.columns and "temp_max" in df.columns:
        bad_t = df["temp_min"].notna() & df["temp_max"].notna() & (df["temp_min"] > df["temp_max"] + 0.2)
        df.loc[bad_t, ["temp_min", "temp_max"]] = np.nan
    if "q_cfs" in df.columns:
        df["q_cfs"] = df["q_cfs"].where(df["q_cfs"] > 0.0)
    if "spcond" in df.columns:
        df["spcond"] = df["spcond"].where(df["spcond"].between(1.0, 50000.0))
    if "turb" in df.columns:
        df["turb"] = df["turb"].where(df["turb"].between(0.0, 10000.0))
    return df


def fetch_batch(batch_sites: list[str]) -> int:
    """Fetch a batch of uncached sites in one multi-site USGS RDB call (with single-site fallback if needed)."""
    needed = [s for s in batch_sites if not (DV_DIR / f"{s}.parquet").exists()]
    if not needed:
        return 0
    url = (
        f"https://waterservices.usgs.gov/nwis/dv/?format=rdb&sites={','.join(needed)}"
        "&startDT=2005-01-01&endDT=2025-12-31"
        "&parameterCd=00300,00010,00060,00095,63680&statCd=00001,00002,00003"
    )
    txt = fetch_rdb_polite(url)
    saved = 0
    if txt:
        blocks = split_multi_site_rdb(txt)
        for sno, blk in blocks.items():
            parsed = parse_dv_block(blk)
            if parsed is None:
                continue
            df = clean_dv_frame(parsed)
            if len(df) >= 1000:
                df.to_parquet(DV_DIR / f"{sno}.parquet")
                saved += 1
        return saved

    # Single-site fallback if batch call failed
    for sno in needed:
        u1 = (
            f"https://waterservices.usgs.gov/nwis/dv/?format=rdb&sites={sno}"
            "&startDT=2005-01-01&endDT=2025-12-31"
            "&parameterCd=00300,00010,00060,00095,63680&statCd=00001,00002,00003"
        )
        t1 = fetch_rdb_polite(u1, timeout=(10, 45))
        if not t1:
            continue
        blocks = split_multi_site_rdb(t1)
        blk = blocks.get(sno)
        if not blk:
            continue
        parsed = parse_dv_block(blk)
        if parsed is None:
            continue
        df = clean_dv_frame(parsed)
        if len(df) >= 1000:
            df.to_parquet(DV_DIR / f"{sno}.parquet")
            saved += 1
    return saved


def summarize_cached_site(row: dict) -> dict | None:
    sno = str(row["site_no"]).strip()
    cache = DV_DIR / f"{sno}.parquet"
    if not cache.exists():
        return None
    df = pd.read_parquet(cache)
    df.index = pd.to_datetime(df.index)
    warm = df[(df.index.month >= 5) & (df.index.month <= 10)]
    if len(df) < 1000 or len(warm) < 400 or warm.index.year.nunique() < 3:
        return None

    med_spcond = float(df["spcond"].median()) if df["spcond"].notna().sum() >= 100 else np.nan
    is_brackish_flag = int(pd.notna(med_spcond) and med_spcond > 5000.0)

    out = dict(row)
    out.update(
        {
            "n_valid_days": len(df),
            "n_warm_days": len(warm),
            "n_years": int(df.index.year.nunique()),
            "n_warm_years": int(warm.index.year.nunique()),
            "first_date": str(df.index.min().date()),
            "last_date": str(df.index.max().date()),
            "n_warm_q_days": int(warm["q_cfs"].notna().sum()),
            "n_warm_tmin_days": int(warm["temp_min"].notna().sum()),
            "n_warm_tmax_days": int(warm["temp_max"].notna().sum()),
            "n_warm_spcond_days": int(warm["spcond"].notna().sum()),
            "n_warm_turb_days": int(warm["turb"].notna().sum()),
            "median_spcond": med_spcond,
            "is_brackish_spcond_gt5000": is_brackish_flag,
        }
    )
    return out


def main() -> None:
    elig_path = PROC_DIR / "conus_clean_eligible_rivers.csv"
    elig = pd.read_csv(elig_path, dtype={"site_no": str, "huc2": str, "huc_cd": str})
    all_sites = [str(s).strip() for s in elig["site_no"].tolist()]
    batches = [all_sites[i : i + BATCH_SIZE] for i in range(0, len(all_sites), BATCH_SIZE)]
    print(
        f"Step 2: Batch-fetching 2005-2025 daily continuous DO/Temp/Q/SpCond/Turb for {len(all_sites)} clean CONUS rivers "
        f"({len(batches)} batches of {BATCH_SIZE}, 3 polite workers)...",
        flush=True,
    )

    t0 = time.monotonic()
    total_saved = 0
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, n_sv in enumerate(ex.map(fetch_batch, batches), 1):
            total_saved += n_sv
            if i % 5 == 0 or i == len(batches):
                cached_now = len(list(DV_DIR.glob("*.parquet")))
                print(
                    f"  [batch {i:2d}/{len(batches)}] newly_saved={total_saved} total_cached={cached_now} elapsed={time.monotonic()-t0:.1f}s",
                    flush=True,
                )

    valid_rows = []
    for row in elig.to_dict("records"):
        res = summarize_cached_site(row)
        if res is not None:
            valid_rows.append(res)

    vdf = pd.DataFrame(valid_rows)
    brackish_df = vdf[vdf["is_brackish_spcond_gt5000"] == 1].copy()
    clean_vdf = vdf[vdf["is_brackish_spcond_gt5000"] == 0].copy().reset_index(drop=True)
    clean_vdf = attach_nid_dam_distances(clean_vdf)

    brackish_df.to_csv(PROC_DIR / "excluded_brackish_spcond_sites.csv", index=False)
    clean_vdf.to_csv(PROC_DIR / "conus_valid_rivers_meta.csv", index=False)

    manifest = {
        "n_eligible_queried": len(all_sites),
        "n_valid_before_spcond_brackish_check": len(vdf),
        "n_excluded_brackish_spcond_gt5000": len(brackish_df),
        "n_final_clean_conus_rivers": len(clean_vdf),
        "n_states": int(clean_vdf["state"].nunique()),
        "n_huc2_basins": int(clean_vdf["huc2"].nunique()),
        "total_station_days": int(clean_vdf["n_valid_days"].sum()),
        "total_warm_station_days": int(clean_vdf["n_warm_days"].sum()),
        "n_with_discharge_q_ge400warm": int((clean_vdf["n_warm_q_days"] >= 400).sum()),
        "n_with_exact_diurnal_temp_minmax": int(((clean_vdf["n_warm_tmin_days"] >= 400) & (clean_vdf["n_warm_tmax_days"] >= 400)).sum()),
        "n_with_spcond_ge400warm": int((clean_vdf["n_warm_spcond_days"] >= 400).sum()),
        "n_with_turb_ge400warm": int((clean_vdf["n_warm_turb_days"] >= 400).sum()),
        "n_long_record_ge10warm_years": int((clean_vdf["n_warm_years"] >= 10).sum()),
        "n_ultra_strict_zero_infra": int((clean_vdf["ultra_strict_flagged"] == 0).sum()),
        "n_nid_gt5km_ge500af": int((clean_vdf["nid_dist_ge500af_km"] > 5.0).sum()),
        "n_nid_gt10km_ge5000af": int((clean_vdf["nid_dist_ge5000af_km"] > 10.0).sum()),
        "n_nid_gt5km_any_dam": int((clean_vdf["nid_dist_any_km"] > 5.0).sum()),
        "rivers_by_huc2": clean_vdf["huc2"].value_counts().sort_index().to_dict(),
        "rivers_by_state": clean_vdf["state"].value_counts().to_dict(),
    }
    (PROC_DIR / "conus_dv_fetch_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("\n=== STEP 2 CONUS DV CENSUS MANIFEST ===", flush=True)
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()
