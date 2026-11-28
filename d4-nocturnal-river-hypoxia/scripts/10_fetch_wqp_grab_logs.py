"""Step 10: Fetch official timestamped discrete DO grab-sample logs from the U.S. Water Quality Portal (WQP)
and probe UK Environment Agency Water Quality Archive for empirical real-world field sampling clock audits.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from hashlib import sha256
from io import StringIO
from pathlib import Path

import numpy as np
import pandas as pd
import requests

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RAW_WQP = ROOT / "data" / "raw_wqp"
WQP_URL = "https://www.waterqualitydata.us/data/Result/search"

# Official USGS/WQP US timezone offsets (hours relative to UTC)
TZ_OFFSETS_HR: dict[str, float] = {
    "UTC": 0.0,
    "GMT": 0.0,
    "EST": -5.0,
    "EDT": -4.0,
    "CST": -6.0,
    "CDT": -5.0,
    "MST": -7.0,
    "MDT": -6.0,
    "PST": -8.0,
    "PDT": -7.0,
    "AKST": -9.0,
    "AKDT": -8.0,
}


def fetch_wqp_chunk(site_ids: list[str], start_mdy: str, end_mdy: str) -> pd.DataFrame:
    payload = {
        "siteid": site_ids,
        "pCode": ["00300"],
        "startDateLo": start_mdy,
        "startDateHi": end_mdy,
    }
    for attempt in range(4):
        try:
            r = requests.post(
                WQP_URL,
                params={"mimeType": "csv", "dataProfile": "narrowResult"},
                json=payload,
                timeout=90,
            )
            if r.status_code == 200:
                if len(r.content) < 80:
                    return pd.DataFrame()
                return pd.read_csv(StringIO(r.text), low_memory=False)
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2 ** (attempt + 1))
                continue
            r.raise_for_status()
        except requests.RequestException:
            if attempt == 3:
                raise
            time.sleep(2 ** (attempt + 1))
    return pd.DataFrame()


def parse_wqp_timestamps(df: pd.DataFrame, meta: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame()
    out = pd.DataFrame()
    out["site"] = df["MonitoringLocationIdentifier"].astype(str).str.replace("^USGS-", "", regex=True).str.strip()
    out["date_str"] = df["ActivityStartDate"].astype(str).str.strip()
    out["time_str"] = df["ActivityStartTime/Time"].astype(str).str.strip()
    out["tz_code"] = df["ActivityStartTime/TimeZoneCode"].astype(str).str.strip().str.upper()
    out["activity_type"] = df.get("ActivityTypeCode", pd.Series("", index=df.index)).astype(str).str.strip()
    out["media"] = df.get("ActivityMediaName", pd.Series("", index=df.index)).astype(str).str.strip()
    out["status"] = df.get("ResultStatusIdentifier", pd.Series("", index=df.index)).astype(str).str.strip()
    out["unit"] = df.get("ResultMeasure/MeasureUnitCode", pd.Series("", index=df.index)).astype(str).str.strip().str.lower()
    out["do_grab"] = pd.to_numeric(df["ResultMeasureValue"], errors="coerce")

    # Keep valid freshwater mg/L measurements with valid HH:MM:SS timestamps and known timezones
    valid = (
        out["do_grab"].between(0.0, 25.0)
        & out["unit"].isin(["mg/l", "mg/l as o2"])
        & out["tz_code"].isin(TZ_OFFSETS_HR)
        & out["time_str"].str.match(r"^\d{2}:\d{2}(:\d{2})?$", na=False)
        & out["date_str"].str.match(r"^\d{4}-\d{2}-\d{2}$", na=False)
        & out["status"].isin(["Accepted", "Final", "Historical", "Validated", "Preliminary"])
    )
    out = out.loc[valid].copy()
    if out.empty:
        return out

    local_dt = pd.to_datetime(out["date_str"] + " " + out["time_str"], errors="coerce")
    offsets = out["tz_code"].map(TZ_OFFSETS_HR)
    utc_dt = (local_dt - pd.to_timedelta(offsets, unit="h")).dt.tz_localize("UTC")
    out["time_utc"] = utc_dt
    out["local_clock_hr"] = local_dt.dt.hour + local_dt.dt.minute / 60.0 + local_dt.dt.second / 3600.0
    out["month"] = local_dt.dt.month
    out["year"] = local_dt.dt.year

    # Attach site coordinates
    coords = meta[["site", "lat", "lon", "huc2"]].drop_duplicates("site")
    out = out.merge(coords, on="site", how="inner")

    # Exact local mean solar time (LMST) in hours [0, 24)
    epoch = pd.Timestamp("1970-01-01", tz="UTC")
    solar_min = (out["time_utc"] - epoch).dt.total_seconds() / 60.0 + 4.0 * out["lon"]
    out["solar_min"] = solar_min
    out["solar_day"] = np.floor(solar_min / 1440.0).astype(int)
    out["solar_hr"] = (solar_min % 1440.0) / 60.0

    # Collapse exact duplicate timestamp-site entries (e.g. QC replicates at identical timestamp) by median
    out = out.sort_values(["site", "time_utc"]).reset_index(drop=True)
    return out


def fetch_cohort(name: str, meta_df: pd.DataFrame, start_mdy: str, end_mdy: str, chunk_size: int = 35) -> tuple[pd.DataFrame, dict]:
    cache_pq = RAW_WQP / f"wqp_{name}.parquet"
    cache_js = RAW_WQP / f"wqp_{name}_manifest.json"
    if cache_pq.exists() and cache_js.exists():
        return pd.read_parquet(cache_pq), json.loads(cache_js.read_text(encoding="utf-8"))

    sites = meta_df["site"].dropna().astype(str).unique().tolist()
    site_ids = [f"USGS-{s}" for s in sites]
    frames = []
    for i in range(0, len(site_ids), chunk_size):
        chunk = site_ids[i : i + chunk_size]
        df_c = fetch_wqp_chunk(chunk, start_mdy, end_mdy)
        if not df_c.empty:
            frames.append(df_c)
        print(f"  [{name}] chunk {i // chunk_size + 1}/{(len(site_ids) - 1) // chunk_size + 1}: {len(df_c)} raw rows", flush=True)
        time.sleep(0.3)

    raw_all = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()
    parsed = parse_wqp_timestamps(raw_all, meta_df)
    # Keep warm-season (May-Oct) routine + replicate discrete observations
    warm = parsed[parsed["month"].between(5, 10)].copy()
    warm.to_parquet(cache_pq, index=False)

    manifest = {
        "cohort": name,
        "fetched_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source_url": WQP_URL,
        "date_window": [start_mdy, end_mdy],
        "n_queried_sites": len(sites),
        "n_raw_rows": len(raw_all),
        "n_parsed_all_season": len(parsed),
        "n_warm_season_rows": len(warm),
        "n_sites_with_warm_grabs": int(warm["site"].nunique()) if not warm.empty else 0,
        "sha256": sha256(cache_pq.read_bytes()).hexdigest(),
    }
    cache_js.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return warm, manifest


def main() -> None:
    RAW_WQP.mkdir(parents=True, exist_ok=True)

    iv_meta = pd.read_csv(PROC / "conus_iv_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
    iv_meta = iv_meta.rename(columns={"site_no": "site"})
    all_meta = pd.read_csv(PROC / "conus_valid_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
    all_meta = all_meta.rename(columns={"site_no": "site"})

    print("Fetching WQP discrete DO grab logs for 139 IV stations (2021-2024)...", flush=True)
    iv_grabs, iv_man = fetch_cohort("iv139_2021_2024", iv_meta, "05-01-2021", "10-31-2024")
    print("IV-139 manifest:", json.dumps(iv_man), flush=True)

    print("Fetching WQP discrete DO grab logs for 397 CONUS stations (2015-2024)...", flush=True)
    all_grabs, all_man = fetch_cohort("conus397_2015_2024", all_meta, "05-01-2015", "10-31-2024")
    print("CONUS-397 manifest:", json.dumps(all_man), flush=True)

    for label, df in [("IV-139 (2021-2024)", iv_grabs), ("CONUS-397 (2015-2024)", all_grabs)]:
        if df.empty:
            continue
        # Deduplicate to distinct site-visit timestamps (median DO across replicates)
        visits = df.groupby(["site", "time_utc"], as_index=False).agg(
            do_grab=("do_grab", "median"),
            local_clock_hr=("local_clock_hr", "first"),
            solar_hr=("solar_hr", "first"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            huc2=("huc2", "first"),
            month=("month", "first"),
        )
        print(
            f"{label}: {len(visits)} distinct site-visits across {visits['site'].nunique()} sites | "
            f"median local clock={visits['local_clock_hr'].median():.2f} h (IQR {visits['local_clock_hr'].quantile(0.25):.2f}-{visits['local_clock_hr'].quantile(0.75):.2f}) | "
            f"median solar={visits['solar_hr'].median():.2f} h | "
            f"08:00-17:00={100*visits['local_clock_hr'].between(8, 17).mean():.1f}% | "
            f"<07:00={100*(visits['solar_hr'] < 7).mean():.2f}%",
            flush=True,
        )


if __name__ == "__main__":
    main()
