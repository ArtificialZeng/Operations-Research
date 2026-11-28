"""Cache screened stations' native UTC dissolved-oxygen observations from USGS STAC."""

from __future__ import annotations

import argparse
import json
import time
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
import requests

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / "data" / "raw_usgs_stac"
SITES = ROOT / "data" / "processed" / "conus_iv_rivers_meta.csv"
SOURCE = "https://api.waterdata.usgs.gov/stac-files/continuous/USGS-{site}/USGS-{site}.parquet"
COLS = ["time_series_id", "time", "parameter_code", "value", "approval_status"]


def fetch(site: str) -> dict:
    data = DEST / f"{site}.parquet"
    meta = DEST / f"{site}.json"
    if data.is_file() and meta.is_file():
        return json.loads(meta.read_text(encoding="utf-8"))
    url = SOURCE.format(site=site)
    for attempt in range(3):
        try:
            response = requests.get(url, timeout=(15, 70))
            response.raise_for_status()
            break
        except requests.RequestException:
            if attempt == 2:
                raise
            time.sleep(2 ** (attempt + 1))

    table = pq.read_table(BytesIO(response.content), columns=COLS,
                          filters=[("parameter_code", "==", "00300")])
    df = table.to_pandas()
    time_utc = df["time"].dt
    df = df.loc[time_utc.year.between(2021, 2024) & time_utc.month.between(5, 10)].copy()
    df["value"] = pd.to_numeric(df["value"], errors="coerce")
    df = df.loc[df["approval_status"].eq("Approved") & df["value"].between(0, 25)]
    coverage = df.groupby("time_series_id")["time"].nunique().sort_index()
    series = str(coverage.idxmax()) if not coverage.empty else None
    df = (df.loc[df["time_series_id"].eq(series), ["time", "value"]]
          .groupby("time", as_index=False).agg(do=("value", "median")))
    df.to_parquet(data, index=False)
    receipt = {
        "site": site,
        "source": url,
        "source_sha256": sha256(response.content).hexdigest(),
        "source_last_modified": response.headers.get("Last-Modified"),
        "filtered_sha256": sha256(data.read_bytes()).hexdigest(),
        "selected_ts_id": series,
        "n_approved_readings": len(df),
    }
    meta.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    if not 1 <= args.workers <= 8:
        parser.error("--workers must be between 1 and 8")
    DEST.mkdir(parents=True, exist_ok=True)
    sites = pd.read_csv(SITES, dtype={"site_no": "string"})["site_no"].tolist()
    def run(site: str) -> dict:
        try:
            return fetch(site)
        except (requests.RequestException, OSError, ValueError) as error:
            return {"site": site, "error": f"{type(error).__name__}: {error}"}

    results = []
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(run, sites):
            results.append(result)
            print(result["site"], result.get("n_approved_readings", result.get("error")), flush=True)
    (DEST / "download_manifest.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    errors = [row for row in results if "error" in row]
    print(f"Retrieved {len(results) - len(errors)} of {len(results)} stations")
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
