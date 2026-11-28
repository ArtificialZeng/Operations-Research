"""Step 10: Replay EPA's published site-month PM2.5 Tier-1/Tier-2 thresholds on
collocated instruments (April 2024 EPA-457/R-24-001 official formula snapshot).
"""

from __future__ import annotations

from hashlib import sha256
from io import BytesIO

import numpy as np
import pandas as pd
import requests
from econ_utils import ENRICH_DIR, PROC_DIR, RES_DIR, save_json_lf
from scipy import stats

SOURCE = "https://www.epa.gov/system/files/other-files/2025-10/for_posting.csv"
SNAPSHOT_DATE = "2026-09-14"
SNAPSHOT = ENRICH_DIR / f"epa_pm25_tier_thresholds_{SNAPSHOT_DATE}.csv"
RECEIPT = RES_DIR / "10_official_tier_replay.json"
INSTRUMENTS = {
    "t640_fw": "T640 vs FRM",
    "bam": "BAM vs FRM",
}
COMPARISONS = {
    "fixed_35": "Daily concentration >35",
    "tier_1": "At or above Tier 1 threshold",
    "tier_2_threshold": "At or above Tier 2 lower threshold",
}


def load_thresholds() -> pd.DataFrame:
    if not SNAPSHOT.exists():
        response = requests.get(SOURCE, timeout=35)
        response.raise_for_status()
        frame = pd.read_csv(BytesIO(response.content), dtype={"SITE_ID": "string"})
        if set(frame["AQS_query_date"]) != {SNAPSHOT_DATE}:
            raise ValueError("EPA returned a different threshold vintage")
        SNAPSHOT.parent.mkdir(parents=True, exist_ok=True)
        SNAPSHOT.write_bytes(response.content)
    raw = pd.read_csv(SNAPSHOT, dtype={"SITE_ID": "string"})
    if set(raw["AQS_query_date"]) != {SNAPSHOT_DATE}:
        raise ValueError("Unexpected vintage in the pinned threshold file")
    fips = raw["SITE_ID"].str.zfill(9)
    df = pd.DataFrame(
        {
            "site_id": fips.str[:5] + "-" + fips.str[5:],
            "Month": raw["month"].astype(int),
            "monthly_98th": raw["monthly_98th"].astype(float),
            "annual_98th_minimum": raw["annual_98th_minimum"].astype(float),
            "tier_1": raw["tier 1"].astype(float),
            "tier_2_threshold": raw["tier 2"].astype(float),
            "epa_region_csv": pd.to_numeric(raw["EPA_REGION"], errors="coerce"),
        }
    )
    expected = np.minimum(df["monthly_98th"], df["annual_98th_minimum"])
    if df.duplicated(["site_id", "Month"]).any() or not df["Month"].between(1, 12).all():
        raise ValueError("Invalid EPA site-month keys")
    if not (
        np.allclose(df["tier_2_threshold"], expected)
        and np.allclose(df["tier_1"], 1.5 * expected)
    ):
        raise ValueError("EPA table disagrees with the published tier formula")
    return df


def cluster_interval(difference: pd.Series, cluster: pd.Series) -> list[float]:
    centered = difference - difference.mean()
    totals = centered.groupby(cluster).sum()
    df = len(totals) - 1
    if df == 0:
        raise ValueError("At least two clusters are needed for an interval")
    standard_error = np.sqrt((df + 1) / df * np.square(totals).sum()) / len(difference)
    radius = float(stats.t.ppf(0.975, df) * standard_error)
    return [float(100.0 * (difference.mean() - radius)), float(100.0 * (difference.mean() + radius))]


def compare(frame: pd.DataFrame, key: str) -> dict:
    if key == "fixed_35":
        first, reference = frame["fem"].gt(35.0), frame["frm"].gt(35.0)
    else:
        cutoff = frame[key].round(10)
        first, reference = frame["fem"].ge(cutoff), frame["frm"].ge(cutoff)
    delta = first.astype(int) - reference.astype(int)
    blocks = frame.assign(delta=delta).groupby("episode")["delta"].agg(["sum", "size"])
    loo = 100.0 * (delta.sum() - blocks["sum"]) / (len(delta) - blocks["size"])
    return {
        "n_site_days": len(frame),
        "n_sites": int(frame["site_id"].nunique()),
        "n_dates": int(frame["date"].nunique()),
        "n_episode_blocks": len(blocks),
        "instrument_exceed": int(first.sum()),
        "reference_exceed": int(reference.sum()),
        "instrument_only": int(delta.eq(1).sum()),
        "reference_only": int(delta.eq(-1).sum()),
        "difference_pp": float(100.0 * delta.mean()),
        "ci95_site_pp": cluster_interval(delta, frame["site_id"]),
        "ci95_date_pp": cluster_interval(delta, frame["date"]),
        "ci95_episode_pp": cluster_interval(delta, frame["episode"]),
        "leave_one_episode_out_range_pp": [float(loo.min()), float(loo.max())],
    }


def main() -> int:
    print("=== STEP 10: OFFICIAL EPA APRIL 2024 SITE-MONTH TIER REPLAY ===", flush=True)
    thresholds = load_thresholds()
    pairs: dict[str, pd.DataFrame] = {}
    for key in INSTRUMENTS:
        columns = ["site_id", "Date Local", "Month", "Year", "fem", "frm", "hms_max_level"]
        frame = pd.read_parquet(
            PROC_DIR / f"collocated_{key}_frm_2023_2026.parquet", columns=columns
        )
        heavy = frame.loc[frame["Year"].between(2023, 2025) & frame["hms_max_level"].eq(3)].copy()
        heavy["date"] = pd.to_datetime(heavy["Date Local"])
        if heavy.duplicated(["site_id", "date"]).any() or heavy[["frm", "fem"]].isna().any().any():
            raise ValueError(f"Invalid paired Heavy-smoke sample for {key}")
        pairs[key] = heavy

    dates = pd.Series(sorted(set.union(*(set(frame["date"]) for frame in pairs.values()))))
    blocks = pd.Series(dates.diff().gt(pd.Timedelta(days=1)).cumsum().values, index=dates)
    results = {}
    for key, frame in pairs.items():
        frame["episode"] = frame["date"].map(blocks)
        matched = frame.merge(
            thresholds, on=["site_id", "Month"], how="inner", validate="many_to_one"
        )
        results[key] = {
            "fixed_35_full": compare(frame, "fixed_35"),
            "matched": {c: compare(matched, c) for c in COMPARISONS},
            "unmatched_site_days": int(len(frame) - len(matched)),
        }

    sha_out = save_json_lf(
        RECEIPT,
        {
            "threshold_url": SOURCE,
            "aqs_query_date": SNAPSHOT_DATE,
            "threshold_baseline": [2021, 2025],
            "threshold_sha256": sha256(SNAPSHOT.read_bytes()).hexdigest(),
            "threshold_rows": len(thresholds),
            "support": "2023-2025 paired observations on NOAA HMS Heavy site-days",
            "episode_block": "Runs of consecutive days with Heavy smoke in either paired sample nationwide",
            "retrospective": True,
            "results": results,
        },
    )
    t1 = results["t640_fw"]["matched"]["tier_1"]
    b1 = results["bam"]["matched"]["tier_1"]
    print(
        f"[DONE STEP 10] T640 Tier-1: {t1['instrument_exceed']} vs {t1['reference_exceed']} "
        f"({t1['difference_pp']:+.2f} pp, block CI {t1['ci95_episode_pp'][0]:+.2f}..{t1['ci95_episode_pp'][1]:+.2f}) | "
        f"BAM Tier-1: {b1['instrument_exceed']} vs {b1['reference_exceed']} ({b1['difference_pp']:+.2f} pp) | "
        f"SHA-256: {sha_out}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
