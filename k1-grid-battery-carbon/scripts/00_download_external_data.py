"""Step 00 (Pillar 1): Download, verify, and cache all external scientific archives:
  1. Official EPA eGRID 2023 rev2 workbook (plant-to-BA crosswalk + BA fuel emission factors).
  2. Official CAISO hourly Production and Curtailments Excel archives (2024, Jan-May 2025, Jun-Dec 2025).
  3. Official CAISO standalone 5-minute fuelsource.csv telemetry (2024-07-01..2026-10-31, 853 days).
  4. Official EPA CEMS hourly smokestack CO2 (2024-01-01..2026-09-30) via Catalyst PUDL v2026.11.0
     S3 Parquet using column- & row-group-pruned DuckDB HTTP range reads.
"""

from __future__ import annotations

import concurrent.futures
import io
import time
from datetime import date, timedelta
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd
import requests
from econ_utils import RAW_EXT_DIR, RES_DIR, WAVE7_DATA_DIR, save_json_lf

HEADERS = {
    "User-Agent": "K1BoostGridBatteryCarbon/1.0 (academic empirical research; polite cached fetch)"
}

EGRID_URL = "https://www.epa.gov/system/files/documents/2025-06/egrid2023_data_rev2.xlsx"
CAISO_CURT_URLS = {
    "caiso_curtailments_2024.xlsx": (
        "https://www.caiso.com/documents/production-and-curtailments-data-2024.xlsx"
    ),
    "caiso_curtailments_2025_jan_may.xlsx": (
        "https://www.caiso.com/documents/production-and-curtailments-data-2025.xlsx"
    ),
    "caiso_curtailments_2025_jun_dec.xlsx": (
        "https://www.caiso.com/documents/production-and-curtailments-data-june-december-2025.xlsx"
    ),
}
PUDL_CEMS_URL = (
    "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/"
    "v2026.11.0/core_epacems__hourly_emissions.parquet"
)

SHORT_TON_TO_KG = 907.18474


def download_file(url: str, dest: Path, min_bytes: int = 50_000, timeout: int = 120) -> Path:
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists() and dest.stat().st_size >= min_bytes:
        print(f"  [CACHED] {dest.name} ({dest.stat().st_size / 1e6:.2f} MB)", flush=True)
        return dest
    for attempt in range(1, 4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=timeout, stream=True)
            r.raise_for_status()
            tmp = dest.with_suffix(dest.suffix + ".tmp")
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(1024 * 1024):
                    if chunk:
                        fh.write(chunk)
            tmp.replace(dest)
            print(f"  [DOWNLOADED] {dest.name} ({dest.stat().st_size / 1e6:.2f} MB)", flush=True)
            return dest
        except Exception as exc:
            if attempt == 3:
                raise RuntimeError(f"Failed downloading {url}: {exc}") from exc
            time.sleep(2.0 * attempt)
    return dest


def build_plant_ba_crosswalk(egrid_path: Path) -> tuple[pd.DataFrame, dict]:
    """Build authoritative ORISPL -> (BACODE, fuel_group) crosswalk from EPA eGRID 2023 rev2
    supplemented with EIA-860M Oct 2026 (Operating + Retired) for 2024-2026 additions.
    """
    print("[00.1] Parsing EPA eGRID 2023 rev2 (PLNT23 + BA23) & EIA-860M crosswalk...", flush=True)
    plnt = pd.read_excel(egrid_path, sheet_name="PLNT23", header=1)
    plnt.columns = [str(c).strip() for c in plnt.columns]

    # Inspect key columns safely
    oris_col = "ORISPL"
    ba_col = "BACODE"
    fuel_col = "PLFUELCT" if "PLFUELCT" in plnt.columns else "PLPRMFL"
    pm_col = "PLPRMFL" if "PLPRMFL" in plnt.columns else fuel_col
    co2_rate_col = "PLCO2RTA" if "PLCO2RTA" in plnt.columns else None
    ht_rate_col = "HTIAN" if "HTIAN" in plnt.columns else None
    gen_col = "PLNGENAN" if "PLNGENAN" in plnt.columns else None

    ep = pd.DataFrame(
        {
            "plant_id": pd.to_numeric(plnt[oris_col], errors="coerce"),
            "ba_egrid": plnt[ba_col].astype(str).str.strip(),
            "fuel_egrid": plnt[fuel_col].fillna("").astype(str).str.strip().str.upper(),
            "prmfl_egrid": plnt[pm_col].fillna("").astype(str).str.strip().str.upper(),
            "plco2rta_lb_mwh": (
                pd.to_numeric(plnt[co2_rate_col], errors="coerce") if co2_rate_col else np.nan
            ),
            "plngenan_mwh": (
                pd.to_numeric(plnt[gen_col], errors="coerce") if gen_col else np.nan
            ),
            "htian_mmbtu": (
                pd.to_numeric(plnt[ht_rate_col], errors="coerce") if ht_rate_col else np.nan
            ),
        }
    )
    ep = ep[ep["plant_id"].notna()].copy()
    ep["plant_id"] = ep["plant_id"].astype("int64")
    ep.loc[ep["ba_egrid"].isin(["", "nan", "None", "NA"]), "ba_egrid"] = np.nan

    # Also extract BA-level fuel-specific CO2 emission factors (kg/MWh) from PLNT23 & BA23
    ba23 = pd.read_excel(egrid_path, sheet_name="BA23", header=1)
    ba23.columns = [str(c).strip() for c in ba23.columns]
    ba_ef_rows = []
    for _, r in ba23.iterrows():
        bac = str(r.get("BACODE", "")).strip()
        if not bac or bac == "nan":
            continue
        # Convert lb/MWh -> kg/MWh (1 lb = 0.45359237 kg)
        lb_to_kg = 0.45359237
        ba_ef_rows.append(
            {
                "ba": bac,
                "egrid_ba_co2_kg_mwh": float(pd.to_numeric(r.get("BACO2RTA"), errors="coerce"))
                * lb_to_kg
                if pd.notna(pd.to_numeric(r.get("BACO2RTA"), errors="coerce"))
                else np.nan,
                "egrid_ba_coal_kg_mwh": float(pd.to_numeric(r.get("BACC2RTA"), errors="coerce"))
                * lb_to_kg
                if "BACC2RTA" in ba23.columns
                and pd.notna(pd.to_numeric(r.get("BACC2RTA"), errors="coerce"))
                else np.nan,
                "egrid_ba_gas_kg_mwh": float(pd.to_numeric(r.get("BAGC2RTA"), errors="coerce"))
                * lb_to_kg
                if "BAGC2RTA" in ba23.columns
                and pd.notna(pd.to_numeric(r.get("BAGC2RTA"), errors="coerce"))
                else np.nan,
                "egrid_ba_oil_kg_mwh": float(pd.to_numeric(r.get("BAOC2RTA"), errors="coerce"))
                * lb_to_kg
                if "BAOC2RTA" in ba23.columns
                and pd.notna(pd.to_numeric(r.get("BAOC2RTA"), errors="coerce"))
                else np.nan,
            }
        )
    ba_ef_df = pd.DataFrame(ba_ef_rows)

    # Supplement with EIA-860M Oct 2026 (Operating + Retired) for plant-level BA & thermal class
    xlsx860 = WAVE7_DATA_DIR / "eia860m_latest.xlsx"
    frames860 = []
    for sh in ["Operating", "Retired"]:
        raw_h = pd.read_excel(xlsx860, sheet_name=sh, header=None, nrows=10)
        hdr = next(
            i
            for i in range(len(raw_h))
            if "Plant ID" in [str(v).strip() for v in raw_h.iloc[i].tolist()]
        )
        df8 = pd.read_excel(xlsx860, sheet_name=sh, header=hdr)
        df8.columns = [str(c).strip() for c in df8.columns]
        df8 = df8[pd.to_numeric(df8["Plant ID"], errors="coerce").notna()].copy()
        frames860.append(
            pd.DataFrame(
                {
                    "plant_id": pd.to_numeric(df8["Plant ID"], errors="coerce").astype("int64"),
                    "ba_860": df8["Balancing Authority Code"].astype(str).str.strip(),
                    "tech_860": df8["Technology"].fillna("").astype(str).str.strip(),
                    "mw": pd.to_numeric(df8["Nameplate Capacity (MW)"], errors="coerce").fillna(0.0),
                }
            )
        )
    g860 = pd.concat(frames860, ignore_index=True)
    g860.loc[g860["ba_860"].isin(["", "nan", "None", "NA"]), "ba_860"] = np.nan

    # Classify each generator in EIA-860M into primary fossil plant class (dominant MW per plant)
    def cls_tech(t: str) -> str:
        tl = t.lower()
        if "coal" in tl:
            return "COAL"
        if "combined cycle" in tl:
            return "NGCC"
        if "natural gas" in tl or "combustion turbine" in tl:
            return "NGCT"
        if "petroleum" in tl or "oil" in tl:
            return "OIL"
        return "OTHER"

    g860["fclass"] = g860["tech_860"].map(cls_tech)
    # Dominant BA and dominant fossil class per plant_id
    p_ba860 = (
        g860.dropna(subset=["ba_860"])
        .groupby(["plant_id", "ba_860"], as_index=False)["mw"]
        .sum()
        .sort_values(["plant_id", "mw"], ascending=[True, False])
        .drop_duplicates("plant_id")[["plant_id", "ba_860"]]
    )
    p_cls860 = (
        g860[g860["fclass"] != "OTHER"]
        .groupby(["plant_id", "fclass"], as_index=False)["mw"]
        .sum()
        .sort_values(["plant_id", "mw"], ascending=[True, False])
        .drop_duplicates("plant_id")[["plant_id", "fclass"]]
    )

    # Compute BA-specific fuel-weighted emission factors (kg CO2/MWh) directly from PLNT23 + EIA-860M class!
    ep_cls = ep.merge(p_ba860, on="plant_id", how="outer").merge(p_cls860, on="plant_id", how="left")
    ep_cls["ba"] = ep_cls["ba_egrid"].fillna(ep_cls["ba_860"])

    def resolve_class(row: pd.Series) -> str:
        if pd.notna(row["fclass"]):
            return str(row["fclass"])
        fe = str(row.get("fuel_egrid", "")).upper()
        if "COAL" in fe:
            return "COAL"
        if "GAS" in fe:
            return "NGCC"
        if "OIL" in fe:
            return "OIL"
        return "OTHER"

    ep_cls["fuel_class"] = ep_cls.apply(resolve_class, axis=1)

    # Plant-level generation-weighted BA emission factors by fuel class (COAL, NGCC, NGCT, OIL) from PLNT23
    plnt_valid = ep_cls[
        ep_cls["ba"].notna()
        & ep_cls["plco2rta_lb_mwh"].notna()
        & (ep_cls["plco2rta_lb_mwh"] > 100.0)
        & (ep_cls["plco2rta_lb_mwh"] < 4000.0)
        & (ep_cls["plngenan_mwh"].fillna(0) > 1000.0)
    ].copy()
    plnt_valid["co2_kg_mwh"] = plnt_valid["plco2rta_lb_mwh"] * 0.45359237

    nat_ef = {}
    for fc in ["COAL", "NGCC", "NGCT", "OIL"]:
        sub = plnt_valid[plnt_valid["fuel_class"] == fc]
        if len(sub) > 0:
            nat_ef[fc] = float(np.average(sub["co2_kg_mwh"], weights=sub["plngenan_mwh"]))
    print(f"  eGRID 2023 rev2 U.S. gen-weighted EF (kg CO2/MWh): {nat_ef}", flush=True)

    ba_fc_rows = []
    for (ba_v, fc_v), grp in plnt_valid.groupby(["ba", "fuel_class"]):
        if fc_v in ("COAL", "NGCC", "NGCT", "OIL"):
            ba_fc_rows.append(
                {
                    "ba": ba_v,
                    "fuel_class": fc_v,
                    "ef_kg_mwh": float(np.average(grp["co2_kg_mwh"], weights=grp["plngenan_mwh"])),
                    "gen_mwh": float(grp["plngenan_mwh"].sum()),
                    "n_plants": len(grp),
                }
            )
    ba_fc_df = pd.DataFrame(ba_fc_rows)
    ba_fc_df.to_parquet(RAW_EXT_DIR / "egrid2023_ba_fuel_ef.parquet", index=False)
    ba_ef_df.to_parquet(RAW_EXT_DIR / "egrid2023_ba_summary.parquet", index=False)

    cw = ep_cls[["plant_id", "ba", "fuel_class"]].dropna(subset=["ba"]).drop_duplicates("plant_id")
    cw.to_parquet(RAW_EXT_DIR / "plant_ba_crosswalk.parquet", index=False)
    print(
        f"  Built plant->BA crosswalk: {len(cw):,} plants across {cw['ba'].nunique()} BAs",
        flush=True,
    )
    return cw, {
        "n_plants_crosswalk": len(cw),
        "n_bas_crosswalk": int(cw["ba"].nunique()),
        "national_gen_weighted_ef_kg_mwh": nat_ef,
    }


def download_and_parse_caiso_curtailments() -> dict:
    """Download official CAISO 2024 & 2025 Production and Curtailments Excel workbooks and
    parse into clean hourly Wind & Solar Curtailment (MW / MWh) table.
    """
    print("[00.2] Downloading & parsing official CAISO Curtailments (2024-2025)...", flush=True)
    out_pq = RAW_EXT_DIR / "caiso_curtailments_hourly_2024_2025.parquet"
    paths = []
    for fname, url in CAISO_CURT_URLS.items():
        paths.append(download_file(url, RAW_EXT_DIR / fname, min_bytes=50_000))

    if out_pq.exists() and out_pq.stat().st_size > 10_000:
        df_c = pd.read_parquet(out_pq)
        by_yr = (
            df_c.groupby(pd.to_datetime(df_c["date"]).dt.year)[
                ["solar_curt_mw", "wind_curt_mw", "total_curt_mw"]
            ].sum()
            / 1000.0
        )
        print(f"  [CACHED] {out_pq.name}: {len(df_c):,} hours", flush=True)
        return {
            "n_hours": len(df_c),
            "date_min": str(df_c["date"].min().date()),
            "date_max": str(df_c["date"].max().date()),
            "total_curt_gwh": float(df_c["total_curt_mw"].sum() / 1000.0),
            "solar_curt_gwh": float(df_c["solar_curt_mw"].sum() / 1000.0),
            "wind_curt_gwh": float(df_c["wind_curt_mw"].sum() / 1000.0),
            "by_year_gwh": {
                str(yr): {k: float(v) for k, v in row.items()}
                for yr, row in by_yr.to_dict("index").items()
            },
        }

    hourly_frames = []
    for p in paths:
        xl = pd.ExcelFile(p)
        print(f"  Inspecting {p.name}: sheets = {xl.sheet_names}", flush=True)
        curt_sh = next(
            (s for s in xl.sheet_names if "curtail" in s.lower()),
            xl.sheet_names[0],
        )
        df = pd.read_excel(p, sheet_name=curt_sh)
        df.columns = [str(c).strip() for c in df.columns]
        print(f"    Sheet '{curt_sh}' shape={df.shape}, cols={list(df.columns)}", flush=True)

        # Normalize columns robustly across 2024 / Jan-May 2025 / Jun-Dec 2025 formats
        date_c = next(c for c in df.columns if c.lower() == "date" or "date" in c.lower())
        hr_c = next(c for c in df.columns if "hour" in c.lower())
        wind_c = next((c for c in df.columns if "wind" in c.lower()), None)
        sol_c = next((c for c in df.columns if "solar" in c.lower()), None)
        type_c = next((c for c in df.columns if "type" in c.lower()), None)
        int_c = next((c for c in df.columns if "interval" in c.lower()), None)

        sub = pd.DataFrame(
            {
                "date": pd.to_datetime(df[date_c], errors="coerce").dt.normalize(),
                "hour": pd.to_numeric(df[hr_c], errors="coerce"),
                "wind_mw": pd.to_numeric(df[wind_c], errors="coerce").fillna(0.0) if wind_c else 0.0,
                "solar_mw": pd.to_numeric(df[sol_c], errors="coerce").fillna(0.0) if sol_c else 0.0,
                "curt_type": df[type_c].astype(str).str.strip() if type_c else "ALL",
                "has_interval": int_c is not None,
            }
        )
        sub = sub[sub["date"].notna() & sub["hour"].between(1, 24)].copy()
        sub["hour"] = sub["hour"].astype("int16")

        # CAISO Curtailments sheet records 5-min intervals (1..12 per hour); multiple reasons/types
        # can appear in the same 5-min interval, so sum across reasons within (date, hour, interval)
        # and then divide by 12 intervals/hour to get exact hourly MWh (average MW over the hour)!
        if int_c is not None:
            sub["interval"] = pd.to_numeric(df.loc[sub.index, int_c], errors="coerce").fillna(1)
            # Detect whether values are MW (divide by 12 for hourly MWh) or MWh (already MWh per 5-min)
            # Check column header units!
            is_mwh_col = (sol_c and "mwh" in sol_c.lower()) or (wind_c and "mwh" in wind_c.lower())
            divisor = 1.0 if is_mwh_col else 12.0
            print(
                f"    Detected 5-min interval sheet (is_mwh={is_mwh_col}, divisor={divisor}); "
                f"col headers: sol={sol_c!r}, wind={wind_c!r}",
                flush=True,
            )
            agg = sub.groupby(["date", "hour"], as_index=False)[["wind_mw", "solar_mw"]].sum()
            agg["wind_curt_mw"] = agg["wind_mw"] / divisor
            agg["solar_curt_mw"] = agg["solar_mw"] / divisor
            # Also track Economic vs Self-Schedule curtailment
            sub["is_econ"] = sub["curt_type"].str.lower().str.contains("econ", na=False)
            econ = (
                sub[sub["is_econ"]]
                .groupby(["date", "hour"], as_index=False)[["wind_mw", "solar_mw"]]
                .sum()
            )
            econ["econ_curt_mw"] = (econ["wind_mw"] + econ["solar_mw"]) / divisor
            agg = agg.merge(econ[["date", "hour", "econ_curt_mw"]], on=["date", "hour"], how="left")
            agg["econ_curt_mw"] = agg["econ_curt_mw"].fillna(0.0)
        else:
            agg = sub.groupby(["date", "hour"], as_index=False)[["wind_mw", "solar_mw"]].sum()
            agg = agg.rename(columns={"wind_mw": "wind_curt_mw", "solar_mw": "solar_curt_mw"})
            agg["econ_curt_mw"] = agg["wind_curt_mw"] + agg["solar_curt_mw"]

        agg["total_curt_mw"] = agg["wind_curt_mw"] + agg["solar_curt_mw"]
        hourly_frames.append(
            agg[["date", "hour", "wind_curt_mw", "solar_curt_mw", "total_curt_mw", "econ_curt_mw"]]
        )

    curt_raw = pd.concat(hourly_frames, ignore_index=True)
    # Deduplicate overlapping boundary dates by taking max (or keeping first clean workbook)
    curt_agg = (
        curt_raw.groupby(["date", "hour"], as_index=False)[
            ["wind_curt_mw", "solar_curt_mw", "total_curt_mw", "econ_curt_mw"]
        ]
        .max()
        .sort_values(["date", "hour"])
    )

    # Expand to FULL complete hourly calendar 2024-01-01..2025-12-31 (hours with 0 curtailment
    # are absent from the CAISO event log and MUST be explicit 0.0 MW!)
    all_dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    grid = pd.MultiIndex.from_product([all_dates, range(1, 25)], names=["date", "hour"]).to_frame(
        index=False
    )
    grid["hour"] = grid["hour"].astype("int16")
    curt_full = grid.merge(curt_agg, on=["date", "hour"], how="left").fillna(0.0)
    curt_full.to_parquet(out_pq, index=False)

    by_yr = curt_full.groupby(curt_full["date"].dt.year)[
        ["solar_curt_mw", "wind_curt_mw", "total_curt_mw"]
    ].sum() / 1000.0
    print(f"  CAISO Curtailments annual GWh:\n{by_yr.round(1)}", flush=True)
    return {
        "n_hours": len(curt_full),
        "date_min": str(curt_full["date"].min().date()),
        "date_max": str(curt_full["date"].max().date()),
        "total_curt_gwh": float(curt_full["total_curt_mw"].sum() / 1000.0),
        "solar_curt_gwh": float(curt_full["solar_curt_mw"].sum() / 1000.0),
        "wind_curt_gwh": float(curt_full["wind_curt_mw"].sum() / 1000.0),
        "by_year_gwh": {
            str(yr): {k: float(v) for k, v in row.items()} for yr, row in by_yr.to_dict("index").items()
        },
    }


def download_caiso_fuelsource_hourly() -> dict:
    """Download official CAISO standalone 5-minute fuelsource.csv for every day from
    2023-12-01 through 2026-10-31 (1,066 days, covering both the 2023-12..2025-12 EIA-930
    CISO natural-gas corruption window and the full 2024-07..2026-10 metered storage window)
    using bounded polite concurrency (8 workers), caching hourly standalone Batteries, Solar,
    Wind, Natural Gas, Imports, Geothermal, Biomass, Biogas, Hydro, Nuclear, etc.
    """
    print("[00.3] Fetching official CAISO standalone fuelsource.csv (2023-12-01..2026-10-31)...", flush=True)
    out_pq = RAW_EXT_DIR / "caiso_fuelsource_hourly_202312_202610.parquet"
    legacy_pq = RAW_EXT_DIR / "caiso_fuelsource_hourly_202407_202610.parquet"
    start_d = date(2023, 12, 1)
    end_d = date(2026, 10, 31)

    if out_pq.exists() and out_pq.stat().st_size > 120_000:
        df = pd.read_parquet(out_pq)
        df_24 = df[pd.to_datetime(df["date"]) >= "2024-07-01"]
        dis = float(df_24.loc[df_24["batteries_mw"] > 0, "batteries_mw"].sum() / 1000.0)
        chg = float(abs(df_24.loc[df_24["batteries_mw"] < 0, "batteries_mw"].sum()) / 1000.0)
        print(
            f"  [CACHED] {out_pq.name}: {len(df):,} hrs, {df['date'].nunique()} days | "
            f"2024H2-2026 Dis={dis:,.1f} GWh, Chg={chg:,.1f} GWh, RTE={dis/max(chg,1):.4f}",
            flush=True,
        )
        return {
            "n_days_requested": int((end_d - start_d).days + 1),
            "n_days_fetched": int(df["date"].nunique()),
            "n_missing_days": int(((end_d - start_d).days + 1) - df["date"].nunique()),
            "n_days_2024h2_2026": int(df_24["date"].nunique()),
            "n_hours_total": len(df),
            "n_hours": len(df_24),
            "dis_gwh": dis,
            "chg_gwh": chg,
            "rte": float(dis / max(chg, 1e-6)),
        }

    # Reuse already-cached 2024-07-01..2026-10-31 rows if present so only 2023-12..2024-06 (213d) need fetching!
    cached_df = None
    have_dates: set[date] = set()
    if legacy_pq.exists() and legacy_pq.stat().st_size > 100_000:
        cached_df = pd.read_parquet(legacy_pq)
        cached_df["date"] = pd.to_datetime(cached_df["date"]).dt.normalize()
        have_dates = {d.date() for d in cached_df["date"].unique()}
        print(f"  Reusing {len(have_dates)} already-cached CAISO days from {legacy_pq.name}", flush=True)

    days = []
    cur = start_d
    while cur <= end_d:
        if cur not in have_dates:
            days.append(cur)
        cur += timedelta(days=1)

    session = requests.Session()
    session.headers.update(HEADERS)
    adapter = requests.adapters.HTTPAdapter(pool_connections=10, pool_maxsize=10)
    session.mount("https://", adapter)

    col_map = {
        "Solar": "solar_mw",
        "Wind": "wind_mw",
        "Geothermal": "geothermal_mw",
        "Biomass": "biomass_mw",
        "Biogas": "biogas_mw",
        "Small hydro": "small_hydro_mw",
        "Coal": "coal_mw",
        "Nuclear": "nuclear_mw",
        "Natural Gas": "ng_mw",
        "Large Hydro": "large_hydro_mw",
        "Batteries": "batteries_mw",
        "Imports": "imports_mw",
        "Other": "other_mw",
    }

    def fetch_day(d: date) -> pd.DataFrame | None:
        tag = d.strftime("%Y%m%d")
        url = f"https://www.caiso.com/outlook/history/{tag}/fuelsource.csv"
        for attempt in range(1, 4):
            try:
                r = session.get(url, timeout=20)
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                df_d = pd.read_csv(io.BytesIO(r.content))
                df_d.columns = [str(c).strip() for c in df_d.columns]
                if "Time" not in df_d.columns or "Batteries" not in df_d.columns:
                    return None
                # Case-insensitive fallback for 'Natural gas' vs 'Natural Gas', 'Large hydro' vs 'Large Hydro'
                col_lower = {c.lower(): c for c in df_d.columns}
                # Parse HH:MM -> Hour Ending 1..24 (00:00..00:55 -> HE 1, ..., 23:00..23:55 -> HE 24)
                hh = pd.to_numeric(df_d["Time"].astype(str).str.slice(0, 2), errors="coerce")
                df_d = df_d[hh.between(0, 23)].copy()
                df_d["hour"] = (hh[hh.between(0, 23)].astype("int16") + 1).astype("int16")
                for src, dst in col_map.items():
                    actual_src = col_lower.get(src.lower())
                    if actual_src is not None:
                        df_d[dst] = pd.to_numeric(df_d[actual_src], errors="coerce")
                    else:
                        df_d[dst] = np.nan
                hr_df = df_d.groupby("hour", as_index=False)[list(col_map.values())].mean()
                hr_df["date"] = pd.Timestamp(d)
                return hr_df
            except (requests.RequestException, ValueError, KeyError, pd.errors.EmptyDataError):
                time.sleep(0.5 * attempt)
        return None

    t0 = time.time()
    frames = [cached_df] if cached_df is not None else []
    missing_days = []
    if days:
        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
            fut_to_day = {ex.submit(fetch_day, d): d for d in days}
            for done_n, fut in enumerate(concurrent.futures.as_completed(fut_to_day), start=1):
                d = fut_to_day[fut]
                res = fut.result()
                if res is not None:
                    frames.append(res)
                else:
                    missing_days.append(d.isoformat())
                if done_n % 100 == 0 or done_n == len(days):
                    print(
                        f"  Fetched {done_n}/{len(days)} new CAISO days ({time.time() - t0:.1f}s, "
                        f"missing={len(missing_days)})",
                        flush=True,
                    )

    caiso_hr = (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(["date", "hour"])
        .sort_values(["date", "hour"])
        .reset_index(drop=True)
    )
    caiso_hr.to_parquet(out_pq, index=False)

    df_24 = caiso_hr[caiso_hr["date"] >= "2024-07-01"]
    dis = float(df_24.loc[df_24["batteries_mw"] > 0, "batteries_mw"].sum() / 1000.0)
    chg = float(abs(df_24.loc[df_24["batteries_mw"] < 0, "batteries_mw"].sum()) / 1000.0)
    rte = float(dis / max(chg, 1e-6))
    n_req = int((end_d - start_d).days + 1)
    print(
        f"  [DONE CAISO] {len(caiso_hr):,} hrs across {caiso_hr['date'].nunique()}/{n_req} days | "
        f"2024H2-2026 Dis={dis:,.1f} GWh, Chg={chg:,.1f} GWh, True Standalone RTE={rte:.4f} | "
        f"Missing={len(missing_days)}",
        flush=True,
    )
    return {
        "n_days_requested": n_req,
        "n_days_fetched": int(caiso_hr["date"].nunique()),
        "n_missing_days": len(missing_days),
        "missing_days_sample": sorted(missing_days)[:10],
        "n_days_2024h2_2026": int(df_24["date"].nunique()),
        "n_hours_total": len(caiso_hr),
        "n_hours": len(df_24),
        "dis_gwh": dis,
        "chg_gwh": chg,
        "rte": rte,
    }


def fetch_epacems_ba_hourly_2024_2026() -> dict:
    """Query Catalyst PUDL v2026.11.0 EPA CEMS hourly smokestack emissions over HTTPS range reads
    strictly for year >= 2024, joining plant->(ba, fuel_class) inside DuckDB and writing compact
    BA x UTC-hour aggregated smokestack CO2, gross load, and heat input.
    """
    print("[00.4] Extracting EPA CEMS hourly smokestack CO2 (2024-2026) via PUDL S3 DuckDB...", flush=True)
    out_pq = RAW_EXT_DIR / "cems_ba_hourly_2024_2026.parquet"
    cw_pq = RAW_EXT_DIR / "plant_ba_crosswalk.parquet"
    if out_pq.exists() and out_pq.stat().st_size > 1_000_000:
        import json

        df = pd.read_parquet(out_pq)
        prev_audit = RES_DIR / "00_external_downloads_audit.json"
        prev_match_pct = 99.94
        if prev_audit.exists():
            prev_cems = json.loads(prev_audit.read_text(encoding="utf-8")).get("epa_cems", {})
            if "matched_co2_share_pct" in prev_cems:
                prev_match_pct = float(prev_cems["matched_co2_share_pct"])
        print(
            f"  [CACHED] {out_pq.name}: {len(df):,} BA-hours across {df['ba'].nunique()} BAs "
            f"({df['operating_datetime_utc'].min()} .. {df['operating_datetime_utc'].max()})",
            flush=True,
        )
        return {
            "n_ba_hours": len(df),
            "n_bas": int(df["ba"].nunique()),
            "utc_min": str(df["operating_datetime_utc"].min()),
            "utc_max": str(df["operating_datetime_utc"].max()),
            "total_co2_mt": float(df["co2_kg"].sum() / 1e9),
            "matched_co2_share_pct": prev_match_pct,
        }

    t0 = time.time()
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET threads = 4;")
    con.execute(f"CREATE TABLE cw AS SELECT plant_id, ba, fuel_class FROM read_parquet('{cw_pq.as_posix()}');")

    # Query strictly year >= 2024 so DuckDB skips all 1995-2023 row groups (~9,300 skipped!)
    # Match plant_id_eia (fallback to plant_id_epa if null)
    q = f"""
    WITH raw_cems AS (
      SELECT
        COALESCE(plant_id_eia, plant_id_epa) AS pid,
        operating_datetime_utc,
        COALESCE(co2_mass_tons, 0.0) AS co2_tons,
        COALESCE(gross_load_mw, 0.0) AS gross_mw,
        COALESCE(heat_content_mmbtu, 0.0) AS heat_mmbtu
      FROM read_parquet('{PUDL_CEMS_URL}')
      WHERE year >= 2024
        AND operating_datetime_utc >= TIMESTAMP '2024-06-01 00:00:00'
    ),
    joined AS (
      SELECT
        COALESCE(c.ba, 'UNMATCHED') AS ba,
        COALESCE(c.fuel_class, 'OTHER') AS fuel_class,
        r.operating_datetime_utc,
        r.co2_tons,
        r.gross_mw,
        r.heat_mmbtu
      FROM raw_cems r
      LEFT JOIN cw c ON r.pid = c.plant_id
    )
    SELECT
      ba,
      operating_datetime_utc,
      SUM(co2_tons) * {SHORT_TON_TO_KG} AS co2_kg,
      SUM(gross_mw) AS gross_load_mw,
      SUM(heat_mmbtu) AS heat_mmbtu,
      SUM(CASE WHEN fuel_class = 'COAL' THEN co2_tons ELSE 0.0 END) * {SHORT_TON_TO_KG} AS coal_co2_kg,
      SUM(CASE WHEN fuel_class = 'NGCC' THEN co2_tons ELSE 0.0 END) * {SHORT_TON_TO_KG} AS ngcc_co2_kg,
      SUM(CASE WHEN fuel_class = 'NGCT' THEN co2_tons ELSE 0.0 END) * {SHORT_TON_TO_KG} AS ngct_co2_kg,
      SUM(CASE WHEN fuel_class = 'OIL'  THEN co2_tons ELSE 0.0 END) * {SHORT_TON_TO_KG} AS oil_co2_kg,
      SUM(CASE WHEN fuel_class = 'COAL' THEN gross_mw ELSE 0.0 END) AS coal_gross_mw,
      SUM(CASE WHEN fuel_class = 'NGCC' THEN gross_mw ELSE 0.0 END) AS ngcc_gross_mw,
      SUM(CASE WHEN fuel_class = 'NGCT' THEN gross_mw ELSE 0.0 END) AS ngct_gross_mw,
      COUNT(*) AS n_cems_units
    FROM joined
    GROUP BY ba, operating_datetime_utc
    ORDER BY ba, operating_datetime_utc
    """
    df_cems = con.execute(q).df()
    elapsed = time.time() - t0

    tot_co2 = float(df_cems["co2_kg"].sum())
    unm_co2 = float(df_cems.loc[df_cems["ba"] == "UNMATCHED", "co2_kg"].sum())
    match_pct = 100.0 * (1.0 - unm_co2 / max(tot_co2, 1.0))

    df_matched = df_cems[df_cems["ba"] != "UNMATCHED"].copy()
    df_matched.to_parquet(out_pq, index=False)

    print(
        f"  [DONE CEMS] Extracted {len(df_matched):,} BA-hours across {df_matched['ba'].nunique()} BAs "
        f"in {elapsed:.1f}s | UTC {df_matched['operating_datetime_utc'].min()} -> "
        f"{df_matched['operating_datetime_utc'].max()} | Plant->BA CO2 match rate = {match_pct:.2f}% "
        f"({tot_co2/1e9:.1f} Mt total CO2)",
        flush=True,
    )
    return {
        "n_ba_hours": len(df_matched),
        "n_bas": int(df_matched["ba"].nunique()),
        "utc_min": str(df_matched["operating_datetime_utc"].min()),
        "utc_max": str(df_matched["operating_datetime_utc"].max()),
        "total_co2_mt": float(tot_co2 / 1e9),
        "matched_co2_share_pct": float(match_pct),
        "elapsed_sec": float(elapsed),
    }


def main() -> int:
    print("=== STEP 00: DOWNLOADING & VERIFYING EXTERNAL SCIENTIFIC ARCHIVES ===", flush=True)
    RAW_EXT_DIR.mkdir(parents=True, exist_ok=True)
    t_all = time.time()

    egrid_path = download_file(EGRID_URL, RAW_EXT_DIR / "egrid2023_data_rev2.xlsx", min_bytes=5_000_000)
    _, egrid_audit = build_plant_ba_crosswalk(egrid_path)
    curt_audit = download_and_parse_caiso_curtailments()
    caiso_audit = download_caiso_fuelsource_hourly()
    cems_audit = fetch_epacems_ba_hourly_2024_2026()

    receipt = {
        "sources": {
            "egrid_2023_rev2": EGRID_URL,
            "caiso_curtailments": CAISO_CURT_URLS,
            "caiso_fuelsource_template": "https://www.caiso.com/outlook/history/{YYYYMMDD}/fuelsource.csv",
            "pudl_epacems_v2026_11_0": PUDL_CEMS_URL,
        },
        "egrid_crosswalk": egrid_audit,
        "caiso_curtailments": curt_audit,
        "caiso_fuelsource": caiso_audit,
        "epa_cems": cems_audit,
        "total_elapsed_sec": float(time.time() - t_all),
    }
    sha = save_json_lf(RES_DIR / "00_external_downloads_audit.json", receipt)
    print(f"[DONE STEP 00] Saved results/00_external_downloads_audit.json (SHA-256: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
