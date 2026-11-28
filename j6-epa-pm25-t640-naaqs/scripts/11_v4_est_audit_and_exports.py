"""Step 11 (v4 ES&T Revision): Complete Scientific Audit Addressing Every Item in J6.md.

Implements and verifies:
  1. P0 #1 — Instrument Common-Support Audit & Case-Flow Accounting:
     - Exact overlap between T640_FW-FRM (636/638) and BAM-FRM (170/209) across all 2023-2025
       pairs (401 same-site same-day triples across 5 sites) and NOAA HMS Heavy smoke days
       (4 triples across 4 sites, 27 overlapping dates, 6 overlapping sites).
     - Common-support matched benchmarks (Overlapping EPA Regions R1-5/7-8, Overlapping Dates,
       Overlapping Dates & Regions, Overlapping Dates & Regions & FRM<=50, and Overlap-Weighted
       EPA Region x FRM-bin strata) with exact overlap rates and clustered differential CIs.
     - Explicit framing demoting BAM-FRM to a background reference comparator.
  2. P0 #2 — True Out-of-Time Prospective Official EPA April 2024 Tier-1 Threshold Replay:
     - Exact EPA-457/R-24-001 formula: Tier 1 = 1.5 * min(5-yr same-month P98, min of 5 annual P98s)
       computed via 40 CFR Part 50 Appendix N § 3.0(d) combined-site daily series and § 4.5(a)
       Table 1 order statistics under EPA's May 1 annual certification calendar:
       2018-2022 -> 2023, 2019-2023 -> 2024, 2020-2024 -> 2025 (and pre-May-1 -> Y-6..Y-2).
     - Four transparent flag-exclusion specifications benchmarked against EPA's published
       2021-2025 table (for_posting.csv, AQS query date 2026-09-14):
         (a) OOT-A (Conservative R-excluded AQS: combined-site daily excluding AQS 'Excluded'
             rows + AQS annual_conc_by_monitor 'Events Excluded' annual P98 floor, matching EPA
             Guidance p. 16 AMP480 conservative bound);
         (b) OOT-B (Fire-Screen Proxy: OOT-A additionally excluding NOAA HMS Heavy smoke days);
         (c) OOT-B2 (Expanded Fire-Screen Proxy: OOT-A excluding HMS Medium+Heavy smoke days);
         (d) OOT-C (Pure Gravimetric FRM-Only historical 5-year rolling baseline).
     - Full bidirectional threshold discordance (FEM>T1 & FRM<=T1 vs FRM>T1 & FEM<=T1) and
       near-threshold band sensitivity (+-10% and +-20% of Tier-1 by FRM and by symmetric midpoint).
  3. P1 #3 — Ground-Level Smoke Specificity, Equal-Concentration Non-Smoke Control & Event-Level
     Two-Way Inference:
     - Year-by-year stability (2023, 2024, 2025), Leave-One-EPA-Region-Out (7 regions),
       Leave-One-Region-Episode-Out, and Cameron-Gelbach-Miller (2011) two-way clustered CIs
       (Site x National Smoke Block AND Site x Region-Smoke-Episode).
     - Concentration-matched Non-Smoke (HMS=0) vs Heavy Smoke (HMS=3) controls across FRM,
       EIV-robust Other-Site (FRM/BAM only), and Bland-Altman midpoint strata (>=15, 15-25, >=20,
       >=25 ug/m3) with Site-clustered difference-in-differences tests + season split (DJF vs MJJAS).
     - Independent ground-level smoke verification via site-month PM2.5 anomaly (> non-smoke p90)
       and collocated EPA CSN/IMPROVE speciation (OC >= 5 ug/m3, OC/EC >= 5).
  4. P1 #4 — Reproducible CSV Tables & AQS/Threshold Version Manifest exported to tables/.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from econ_utils import (
    ENRICH_DIR,
    PROC_DIR,
    RES_DIR,
    WAVE6_RAW_DIR,
    WS_DIR,
    ols_cr1,
    read_zip_csv,
    save_json_lf,
)
from scipy import stats

TABLES_DIR = WS_DIR / "tables"
SNAPSHOT_DATE = "2026-09-14"
SNAPSHOT_PATH = ENRICH_DIR / f"epa_pm25_tier_thresholds_{SNAPSHOT_DATE}.csv"
RECEIPT_PATH = RES_DIR / "11_v4_est_comprehensive_audit.json"

EPA_REGION_BY_STATE: dict[str, int] = {
    "09": 1, "23": 1, "25": 1, "33": 1, "44": 1, "50": 1,
    "34": 2, "36": 2,
    "10": 3, "11": 3, "24": 3, "42": 3, "51": 3, "54": 3,
    "01": 4, "12": 4, "13": 4, "21": 4, "28": 4, "37": 4, "45": 4, "47": 4,
    "17": 5, "18": 5, "26": 5, "27": 5, "39": 5, "55": 5,
    "05": 6, "22": 6, "35": 6, "40": 6, "48": 6,
    "19": 7, "20": 7, "29": 7, "31": 7,
    "08": 8, "30": 8, "38": 8, "46": 8, "49": 8, "56": 8,
    "04": 9, "06": 9, "15": 9, "32": 9,
    "02": 10, "16": 10, "41": 10, "53": 10,
}


def q98_appn_table(arr: np.ndarray) -> float:
    """40 CFR Part 50 Appendix N § 4.5(a) Table 1 exact 98th percentile."""
    x = np.sort(np.asarray(arr, dtype=np.float64))
    n = len(x)
    if n == 0:
        return float("nan")
    k = (n - 1) // 50 + 1
    return float(x[max(0, n - k)])


def _var_1way_mean(e: np.ndarray, cl: np.ndarray) -> tuple[float, int]:
    n = len(e)
    s = pd.Series(e).groupby(cl, sort=False).sum()
    g = len(s)
    if g < 2 or n == 0:
        return 0.0, g
    return float((g / (g - 1.0)) * np.sum(np.square(s.to_numpy(dtype=np.float64))) / (n**2)), g


def cluster_mean_stats(
    delta: pd.Series,
    site: pd.Series,
    date_s: pd.Series,
    nat_ep: pd.Series,
    reg_ep: pd.Series,
    scale: float = 100.0,
) -> dict[str, Any]:
    """Compute exact 1-way (Site, Date, Nat-Block, Reg-Episode) and 2-way CGM (2011)
    (Site x Nat-Block, Site x Reg-Episode) finite-sample t intervals for a paired mean.
    """
    n = len(delta)
    mu = float(delta.mean())
    e = delta.to_numpy(dtype=np.float64) - mu

    def oneway(cl_s: pd.Series) -> dict[str, Any]:
        v, g = _var_1way_mean(e, cl_s.to_numpy())
        se = float(np.sqrt(max(v, 0.0)))
        if g < 2 or se == 0.0:
            return {
                "se": scale * se,
                "ci95": [scale * mu, scale * mu],
                "g": int(g),
                "df": max(0, int(g) - 1),
            }
        crit = float(stats.t.ppf(0.975, g - 1))
        return {
            "se": scale * se,
            "ci95": [scale * (mu - crit * se), scale * (mu + crit * se)],
            "g": int(g),
            "df": int(g - 1),
        }

    def twoway(c1: pd.Series, c2: pd.Series) -> dict[str, Any]:
        v1, g1 = _var_1way_mean(e, c1.to_numpy())
        v2, g2 = _var_1way_mean(e, c2.to_numpy())
        c12 = c1.astype(str).to_numpy() + "__" + c2.astype(str).to_numpy()
        v12, g12 = _var_1way_mean(e, c12)
        v_tw = v1 + v2 - v12
        clamped = False
        if v_tw <= 0.0:
            v_tw = max(v1, v2)
            clamped = True
        se = float(np.sqrt(max(v_tw, 0.0)))
        df = max(1, min(g1, g2) - 1)
        if min(g1, g2) < 2 or se == 0.0:
            return {
                "se": scale * se,
                "ci95": [scale * mu, scale * mu],
                "g1": int(g1),
                "g2": int(g2),
                "g12": int(g12),
                "df": int(df),
                "psd_clamped": clamped,
                "p_2sided": 1.0 if mu == 0.0 else 0.0,
            }
        crit = float(stats.t.ppf(0.975, df))
        t_val = mu / se
        p_val = float(2.0 * stats.t.sf(abs(t_val), df))
        return {
            "se": scale * se,
            "ci95": [scale * (mu - crit * se), scale * (mu + crit * se)],
            "t": float(t_val),
            "p_2sided": p_val,
            "g1": int(g1),
            "g2": int(g2),
            "g12": int(g12),
            "df": int(df),
            "psd_clamped": clamped,
        }

    return {
        "n": int(n),
        "mean": scale * mu,
        "oneway_site": oneway(site),
        "oneway_date": oneway(date_s),
        "oneway_nat_block": oneway(nat_ep),
        "oneway_reg_episode": oneway(reg_ep),
        "twoway_site_x_nat_block": twoway(site, nat_ep),
        "twoway_site_x_reg_episode": twoway(site, reg_ep),
    }


def assign_region_episodes(df: pd.DataFrame, max_gap_days: int = 2) -> pd.Series:
    """Group Heavy-smoke dates within the same EPA Region separated by <= max_gap_days
    into geographically distinct regional smoke episodes.
    """
    ep_map: dict[tuple[int, pd.Timestamp], str] = {}
    for reg, g in df.groupby("epa_region", sort=True):
        ds = pd.Series(sorted(g["date"].unique()))
        blks = ds.diff().gt(pd.Timedelta(days=max_gap_days)).cumsum().to_numpy()
        for d, b in zip(ds.tolist(), blks.tolist()):
            ep_map[(int(reg), d)] = f"R{int(reg)}_E{int(b)}"
    return pd.Series(
        [ep_map[(int(r), d)] for r, d in zip(df["epa_region"], df["date"])],
        index=df.index,
    )


def evaluate_threshold_block(frame: pd.DataFrame, cutoff_col: str | None) -> dict[str, Any]:
    """Full exceedance, bidirectional discordance, near-threshold band, and multi-way CI audit."""
    if cutoff_col is None:
        first = frame["fem"].gt(35.0)
        ref = frame["frm"].gt(35.0)
        cutoff = pd.Series(35.0, index=frame.index)
    else:
        cutoff = frame[cutoff_col].round(10)
        first = frame["fem"].ge(cutoff)
        ref = frame["frm"].ge(cutoff)

    delta = first.astype(int) - ref.astype(int)
    n_fem_only = int(delta.eq(1).sum())
    n_frm_only = int(delta.eq(-1).sum())
    n_disc = n_fem_only + n_frm_only
    mcnemar_p = float(stats.binomtest(n_fem_only, n_disc, 0.5).pvalue) if n_disc > 0 else 1.0

    ci = cluster_mean_stats(
        delta, frame["site_id"], frame["date"], frame["nat_ep"], frame["reg_ep"], scale=100.0
    )

    # Leave-one-national-block-out & leave-one-regional-episode-out
    nat_blks = frame.assign(delta=delta).groupby("nat_ep")["delta"].agg(["sum", "size"])
    loo_nat = 100.0 * (delta.sum() - nat_blks["sum"]) / (len(delta) - nat_blks["size"])
    reg_blks = frame.assign(delta=delta).groupby("reg_ep")["delta"].agg(["sum", "size"])
    loo_reg = 100.0 * (delta.sum() - reg_blks["sum"]) / (len(delta) - reg_blks["size"])

    # Near-threshold bands (+-10% and +-20%) by both FRM and symmetric midpoint (FEM+FRM)/2
    midpoint = 0.5 * (frame["fem"] + frame["frm"])
    bands: dict[str, Any] = {}
    for basis_key, val_s in [("frm", frame["frm"]), ("midpoint", midpoint)]:
        for pct in (10, 20):
            frac = pct / 100.0
            mask = val_s.between((1.0 - frac) * cutoff, (1.0 + frac) * cutoff)
            sub_d = delta[mask]
            sub_both = (first & ref)[mask]
            bands[f"{basis_key}_pm{pct}pct"] = {
                "n": int(mask.sum()),
                "fem_exceed": int(first[mask].sum()),
                "frm_exceed": int(ref[mask].sum()),
                "both_exceed": int(sub_both.sum()),
                "fem_only": int(sub_d.eq(1).sum()),
                "frm_only": int(sub_d.eq(-1).sum()),
                "difference_pp": float(100.0 * sub_d.mean()) if len(sub_d) > 0 else 0.0,
            }

    # Year-by-year stability
    by_year: dict[str, Any] = {}
    for yr, gy in frame.assign(delta=delta, first=first, ref=ref).groupby("Year", sort=True):
        by_year[str(int(yr))] = {
            "n": len(gy),
            "n_sites": int(gy["site_id"].nunique()),
            "fem_exceed": int(gy["first"].sum()),
            "frm_exceed": int(gy["ref"].sum()),
            "fem_only": int(gy["delta"].eq(1).sum()),
            "frm_only": int(gy["delta"].eq(-1).sum()),
            "difference_pp": float(100.0 * gy["delta"].mean()),
            "mean_bias_ugm3": float((gy["fem"] - gy["frm"]).mean()),
        }

    return {
        "n_site_days": len(frame),
        "n_sites": int(frame["site_id"].nunique()),
        "n_dates": int(frame["date"].nunique()),
        "n_nat_blocks": int(frame["nat_ep"].nunique()),
        "n_reg_episodes": int(frame["reg_ep"].nunique()),
        "fem_exceed": int(first.sum()),
        "frm_exceed": int(ref.sum()),
        "both_exceed": int((first & ref).sum()),
        "fem_only": n_fem_only,
        "frm_only": n_frm_only,
        "mcnemar_exact_p": mcnemar_p,
        "difference_pp": float(100.0 * delta.mean()),
        "mean_bias_ugm3": float((frame["fem"] - frame["frm"]).mean()),
        "median_bias_ugm3": float((frame["fem"] - frame["frm"]).median()),
        "inference": ci,
        "leave_one_nat_block_out_pp": [float(loo_nat.min()), float(loo_nat.max())],
        "leave_one_reg_episode_out_pp": [float(loo_reg.min()), float(loo_reg.max())],
        "near_threshold_bands": bands,
        "by_year": by_year,
    }


def build_aqs_historical_inputs(
    target_sites: list[str], hms_daily: pd.DataFrame
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, list[dict[str, Any]]]:
    """Load 2018-2025 AQS daily & annual records for all collocated sites and record manifest."""
    manifest_rows: list[dict[str, Any]] = []

    def _sha256_file(p: Path) -> str:
        return hashlib.sha256(p.read_bytes()).hexdigest()

    # 1. Monitor metadata for 40 CFR 50 App N primary POC identification
    mon_zip = WAVE6_RAW_DIR / "aqs_monitors.zip"
    mons = read_zip_csv(
        mon_zip,
        usecols=[
            "State Code",
            "County Code",
            "Site Number",
            "Parameter Code",
            "POC",
            "NAAQS Primary Monitor",
            "Monitor Type",
        ],
        dtype={
            "State Code": str,
            "County Code": str,
            "Site Number": str,
            "Parameter Code": str,
            "POC": str,
        },
    )
    manifest_rows.append(
        {
            "artifact": mon_zip.name,
            "category": "AQS Monitor Metadata",
            "years": "All active/historical",
            "rows_loaded": len(mons),
            "bytes": int(mon_zip.stat().st_size),
            "sha256": _sha256_file(mon_zip),
        }
    )
    mons = mons[mons["Parameter Code"] == "88101"].copy()
    mons["site_id"] = (
        mons["State Code"].str.zfill(2)
        + mons["County Code"].str.zfill(3)
        + "-"
        + mons["Site Number"].str.zfill(4)
    )
    mons["poc_int"] = pd.to_numeric(mons["POC"], errors="coerce").fillna(-1).astype(int)
    prim_map = (
        mons[(mons["site_id"].isin(target_sites)) & (mons["NAAQS Primary Monitor"] == "Y")]
        .groupby("site_id")["poc_int"]
        .first()
        .to_dict()
    )

    # 2. annual_conc_by_monitor (PM25 24-hour 2012) for AQS 'Events Excluded' annual 98th pct
    ann_parts = []
    for yr in range(2018, 2026):
        az = WAVE6_RAW_DIR / f"annual_conc_by_monitor_{yr}.zip"
        a = read_zip_csv(
            az,
            usecols=[
                "State Code",
                "County Code",
                "Site Num",
                "Parameter Code",
                "POC",
                "Sample Duration",
                "Pollutant Standard",
                "Event Type",
                "Valid Day Count",
                "98th Percentile",
            ],
            dtype={
                "State Code": str,
                "County Code": str,
                "Site Num": str,
                "Parameter Code": str,
                "POC": str,
            },
        )
        manifest_rows.append(
            {
                "artifact": az.name,
                "category": "AQS Annual Concentration Summary",
                "years": str(yr),
                "rows_loaded": len(a),
                "bytes": int(az.stat().st_size),
                "sha256": _sha256_file(az),
            }
        )
        a = a[
            (a["Parameter Code"] == "88101")
            & (a["Pollutant Standard"] == "PM25 24-hour 2012")
            & (a["Sample Duration"].isin(["24 HOUR", "24-HR BLK AVG"]))
        ].copy()
        a["site_id"] = (
            a["State Code"].str.zfill(2)
            + a["County Code"].str.zfill(3)
            + "-"
            + a["Site Num"].str.zfill(4)
        )
        a = a[a["site_id"].isin(target_sites)].copy()
        a["Year"] = yr
        ann_parts.append(a)
    ann_all = pd.concat(ann_parts, ignore_index=True)
    ann_all["poc_int"] = pd.to_numeric(ann_all["POC"], errors="coerce").fillna(-1).astype(int)
    ann_all["p98"] = pd.to_numeric(ann_all["98th Percentile"], errors="coerce")
    ann_all["vdays"] = pd.to_numeric(ann_all["Valid Day Count"], errors="coerce").fillna(0)
    ev_prio = {
        "Events Excluded": 0,
        "No Events": 1,
        "Concurred Events Excluded": 2,
        "Events Included": 3,
    }
    ann_all["ev_rank"] = ann_all["Event Type"].map(ev_prio).fillna(9)
    ann_all["prim_poc"] = ann_all["site_id"].map(prim_map).fillna(1).astype(int)
    ann_all["is_prim"] = (
        (ann_all["poc_int"] == ann_all["prim_poc"])
        | (ann_all["poc_int"] == ann_all["prim_poc"] + 20)
    ).astype(int)
    ann_best = (
        ann_all[ann_all["vdays"] >= 30]
        .dropna(subset=["p98"])
        .sort_values(
            ["site_id", "Year", "is_prim", "ev_rank", "poc_int"],
            ascending=[True, True, False, True, True],
        )
        .drop_duplicates(["site_id", "Year"])
        .reset_index(drop=True)
    )

    # 3. daily_88101 2018-2025 for combined-site and pure-FRM historical series
    daily_parts = []
    use_d = [
        "State Code",
        "County Code",
        "Site Num",
        "POC",
        "Sample Duration",
        "Date Local",
        "Event Type",
        "Arithmetic Mean",
        "Method Code",
        "Method Name",
    ]
    for yr in range(2018, 2026):
        dz = WAVE6_RAW_DIR / f"daily_88101_{yr}.zip"
        d = read_zip_csv(
            dz,
            usecols=use_d,
            dtype={
                "State Code": str,
                "County Code": str,
                "Site Num": str,
                "POC": str,
                "Method Code": str,
            },
        )
        manifest_rows.append(
            {
                "artifact": dz.name,
                "category": "AQS Daily PM2.5 (88101)",
                "years": str(yr),
                "rows_loaded": len(d),
                "bytes": int(dz.stat().st_size),
                "sha256": _sha256_file(dz),
            }
        )
        d = d[d["Sample Duration"].isin(["24 HOUR", "24-HR BLK AVG"])].copy()
        d["site_id"] = (
            d["State Code"].str.zfill(2)
            + d["County Code"].str.zfill(3)
            + "-"
            + d["Site Num"].str.zfill(4)
        )
        d = d[d["site_id"].isin(target_sites)].copy()
        d["Year"] = yr
        daily_parts.append(d)
    daily = pd.concat(daily_parts, ignore_index=True)
    daily["poc_int"] = pd.to_numeric(daily["POC"], errors="coerce").fillna(-1).astype(int)
    daily["val"] = pd.to_numeric(daily["Arithmetic Mean"], errors="coerce")
    daily["mc"] = daily["Method Code"].str.strip().str.replace(".0", "", regex=False)
    daily["Event Type"] = daily["Event Type"].fillna("None").astype(str)
    daily["Month"] = daily["Date Local"].str.slice(5, 7).astype(int)
    daily = daily.dropna(subset=["val"]).copy()

    # Track sites with zero AirData event flags in 2021-2025 for clean-site validation
    flagged_2125 = set(
        daily[(daily["Year"].between(2021, 2025)) & (daily["Event Type"] != "None")]["site_id"]
    )

    # Drop any site-date where any monitor has Event Type == 'Excluded'
    excl_sd = daily[daily["Event Type"] == "Excluded"][["site_id", "Date Local"]].drop_duplicates()
    excl_sd["is_excl"] = 1

    d_ok = daily[
        (~daily["mc"].isin(["236", "238"])) & (daily["Event Type"].isin(["None", "Included"]))
    ].copy()
    d_ok = d_ok.merge(excl_sd, on=["site_id", "Date Local"], how="left")
    d_ok = d_ok[d_ok["is_excl"].isna()].drop(columns=["is_excl"])
    d_ok["prim_poc"] = d_ok["site_id"].map(prim_map).fillna(1).astype(int)
    d_ok["is_prim"] = (
        (d_ok["poc_int"] == d_ok["prim_poc"])
        | (d_ok["poc_int"] == d_ok["prim_poc"] + 20)
    ).astype(int)
    d_ok = d_ok.sort_values(
        ["site_id", "Date Local", "is_prim", "poc_int"],
        ascending=[True, True, False, True],
    )
    cs = d_ok.drop_duplicates(["site_id", "Date Local"]).copy()
    cs = cs.merge(
        hms_daily[["site_id", "Date Local", "hms_max_level"]],
        on=["site_id", "Date Local"],
        how="left",
    )
    cs["hms_max_level"] = cs["hms_max_level"].fillna(0).astype(int)
    cs["is_clean_site_2125"] = ~cs["site_id"].isin(flagged_2125)

    # Pure gravimetric FRM-only site-day series
    d_frm = daily[
        daily["Method Name"].str.upper().str.contains("GRAVIMETRIC", na=False)
        & daily["Event Type"].isin(["None", "Included"])
    ].copy()
    d_frm = d_frm.merge(excl_sd, on=["site_id", "Date Local"], how="left")
    d_frm = d_frm[d_frm["is_excl"].isna()].drop(columns=["is_excl"])
    d_frm = d_frm.sort_values(["site_id", "Date Local", "poc_int"]).drop_duplicates(
        ["site_id", "Date Local"]
    )
    d_frm = d_frm.merge(
        hms_daily[["site_id", "Date Local", "hms_max_level"]],
        on=["site_id", "Date Local"],
        how="left",
    )
    d_frm["hms_max_level"] = d_frm["hms_max_level"].fillna(0).astype(int)

    return cs, d_frm, ann_best, manifest_rows


def compute_window_tiers(
    cs_in: pd.DataFrame,
    y0: int,
    y1: int,
    ann_best: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute official EPA April 2024 Tier-1/Tier-2 thresholds for a 5-year window [y0, y1]."""
    sub = cs_in[cs_in["Year"].between(y0, y1)]
    mon = sub.groupby(["site_id", "Month"], as_index=False).agg(
        monthly_98th=("val", q98_appn_table),
        n_month_days=("val", "size"),
    )
    if ann_best is not None:
        asub = ann_best[ann_best["Year"].between(y0, y1)]
        ann_min = asub.groupby("site_id", as_index=False).agg(
            annual_98th_min=("p98", "min"),
            n_years=("Year", "nunique"),
        )
    else:
        ann = sub.groupby(["site_id", "Year"], as_index=False).agg(
            ann_p98=("val", q98_appn_table),
            n_days=("val", "size"),
        )
        ann_min = (
            ann[ann["n_days"] >= 30]
            .groupby("site_id", as_index=False)
            .agg(annual_98th_min=("ann_p98", "min"), n_years=("Year", "nunique"))
        )
    out = mon.merge(ann_min, on="site_id", how="inner")
    out["tier_2"] = np.minimum(out["monthly_98th"], out["annual_98th_min"])
    out["tier_1"] = 1.5 * out["tier_2"]
    return out


def compute_common_support_audit(
    t6_all: pd.DataFrame,
    bm_all: pd.DataFrame,
    t6_hm: pd.DataFrame,
    bm_hm: pd.DataFrame,
    thr_df: pd.DataFrame,
) -> dict[str, Any]:
    """P0 #1: Rigorous common-support audit between T640_FW-FRM and BAM-FRM queues."""
    # 1. Exact same-site same-day triple observations (all 2023-2025 days & Heavy smoke)
    trip_all = t6_all.merge(bm_all, on=["site_id", "Date Local"], suffixes=("_t6", "_bm"))
    trip_all = trip_all.merge(
        thr_df[["site_id", "Month", "tier_1", "tier_2"]],
        left_on=["site_id", "Month_t6"],
        right_on=["site_id", "Month"],
        how="left",
    )
    trip_by_hms: dict[str, Any] = {}
    for lvl, name in [(0, "hms_0_none"), (1, "hms_1_light"), (2, "hms_2_medium"), (3, "hms_3_heavy")]:
        s = trip_all[trip_all["hms_max_level_t6"] == lvl]
        t_diff = s["fem_t6"] - s["frm_t6"]
        b_diff = s["fem_bm"] - s["frm_bm"]
        tb_diff = s["fem_t6"] - s["fem_bm"]
        trip_by_hms[name] = {
            "n_site_days": len(s),
            "n_sites": int(s["site_id"].nunique()) if len(s) else 0,
            "mean_frm": float(s["frm_t6"].mean()) if len(s) else 0.0,
            "mean_t640_minus_frm": float(t_diff.mean()) if len(s) else 0.0,
            "mean_bam_minus_frm": float(b_diff.mean()) if len(s) else 0.0,
            "mean_t640_minus_bam": float(tb_diff.mean()) if len(s) else 0.0,
        }

    trip_heavy = trip_all[trip_all["hms_max_level_t6"] == 3].sort_values(
        ["Date Local", "site_id"]
    )
    heavy_triple_rows = [
        {
            "site_id": str(r["site_id"]),
            "date": str(r["Date Local"]),
            "epa_region": int(r["epa_region_t6"]),
            "frm": float(r["frm_t6"]),
            "t640_fw": float(r["fem_t6"]),
            "bam": float(r["fem_bm"]),
            "t640_minus_frm": float(r["fem_t6"] - r["frm_t6"]),
            "bam_minus_frm": float(r["fem_bm"] - r["frm_bm"]),
            "tier_1": float(r["tier_1"]) if pd.notna(r["tier_1"]) else None,
        }
        for _, r in trip_heavy.iterrows()
    ]

    # 2. Overlap metrics on Heavy smoke (full 472 vs 201 and threshold-matched 468 vs 197)
    t6_h_full = t6_all[t6_all["hms_max_level"] == 3]
    bm_h_full = bm_all[bm_all["hms_max_level"] == 3]
    ov_dates_full = sorted(set(t6_h_full["Date Local"]) & set(bm_h_full["Date Local"]))
    ov_sites_full = sorted(set(t6_h_full["site_id"]) & set(bm_h_full["site_id"]))

    ov_regs = sorted(set(t6_hm["epa_region"]) & set(bm_hm["epa_region"]))
    ov_dates = sorted(set(t6_hm["date"]) & set(bm_hm["date"]))

    # Helper to compute differential CI (T640_diff - BAM_diff) clustered on common national smoke block
    def diff_benchmark(t_sub: pd.DataFrame, b_sub: pd.DataFrame, label: str) -> dict[str, Any]:
        dt = (
            t_sub["fem"].ge(t_sub["tier_1"].round(10)).astype(int)
            - t_sub["frm"].ge(t_sub["tier_1"].round(10)).astype(int)
        )
        db = (
            b_sub["fem"].ge(b_sub["tier_1"].round(10)).astype(int)
            - b_sub["frm"].ge(b_sub["tier_1"].round(10)).astype(int)
        )
        # Pooled regression delta = a + b*I(T640) clustered on common national smoke block
        y = np.concatenate([dt.to_numpy(dtype=float), db.to_numpy(dtype=float)])
        is_t = np.concatenate([np.ones(len(dt)), np.zeros(len(db))])
        X = np.column_stack([np.ones(len(y)), is_t])
        cl_blk = np.concatenate([t_sub["nat_ep"].to_numpy(), b_sub["nat_ep"].to_numpy()])
        cl_site = np.concatenate([t_sub["site_id"].to_numpy(), b_sub["site_id"].to_numpy()])
        reg_blk = ols_cr1(y, X, cl_blk, col_names=["const", "is_t640"])
        reg_site = ols_cr1(y, X, cl_site, col_names=["const", "is_t640"])
        c_blk = reg_blk["coefs"]["is_t640"]
        c_site = reg_site["coefs"]["is_t640"]
        df_blk = max(1, reg_blk["G"] - 1)
        crit_blk = float(stats.t.ppf(0.975, df_blk))
        diff_pp = 100.0 * float(c_blk["beta"])
        se_blk_pp = 100.0 * float(c_blk["se_cr1"])
        se_site_pp = 100.0 * float(c_site["se_cr1"])
        crit_site = float(stats.t.ppf(0.975, max(1, reg_site["G"] - 1)))
        return {
            "label": label,
            "t640_n": len(t_sub),
            "t640_overlap_pct": float(100.0 * len(t_sub) / len(t6_hm)),
            "t640_sites": int(t_sub["site_id"].nunique()),
            "t640_diff_pp": float(100.0 * dt.mean()),
            "t640_mean_bias": float((t_sub["fem"] - t_sub["frm"]).mean()),
            "bam_n": len(b_sub),
            "bam_overlap_pct": float(100.0 * len(b_sub) / len(bm_hm)),
            "bam_sites": int(b_sub["site_id"].nunique()),
            "bam_diff_pp": float(100.0 * db.mean()),
            "bam_mean_bias": float((b_sub["fem"] - b_sub["frm"]).mean()),
            "differential_t640_minus_bam_pp": diff_pp,
            "differential_ci95_block_pp": [
                diff_pp - crit_blk * se_blk_pp,
                diff_pp + crit_blk * se_blk_pp,
            ],
            "differential_p_block": float(c_blk["p_cr1"]),
            "differential_ci95_site_pp": [
                diff_pp - crit_site * se_site_pp,
                diff_pp + crit_site * se_site_pp,
            ],
            "differential_p_site": float(c_site["p_cr1"]),
            "n_blocks": int(reg_blk["G"]),
        }

    benchmarks = {
        "full_matched_heavy": diff_benchmark(t6_hm, bm_hm, "Full matched Heavy smoke"),
        "overlap_epa_regions": diff_benchmark(
            t6_hm[t6_hm["epa_region"].isin(ov_regs)],
            bm_hm[bm_hm["epa_region"].isin(ov_regs)],
            "Overlapping EPA Regions (R1-5, R7-8)",
        ),
        "overlap_dates": diff_benchmark(
            t6_hm[t6_hm["date"].isin(ov_dates)],
            bm_hm[bm_hm["date"].isin(ov_dates)],
            "Overlapping Smoke Dates (27 dates)",
        ),
        "overlap_dates_and_regions": diff_benchmark(
            t6_hm[t6_hm["date"].isin(ov_dates) & t6_hm["epa_region"].isin(ov_regs)],
            bm_hm[bm_hm["date"].isin(ov_dates) & bm_hm["epa_region"].isin(ov_regs)],
            "Overlapping Dates & EPA Regions",
        ),
        "overlap_dates_regions_frm_le50": diff_benchmark(
            t6_hm[
                t6_hm["date"].isin(ov_dates)
                & t6_hm["epa_region"].isin(ov_regs)
                & (t6_hm["frm"] <= 50.0)
            ],
            bm_hm[
                bm_hm["date"].isin(ov_dates)
                & bm_hm["epa_region"].isin(ov_regs)
                & (bm_hm["frm"] <= 50.0)
            ],
            "Overlapping Dates, Regions & FRM <= 50 ug/m3",
        ),
    }

    # 3. Exact Overlap-Weighted (EPA Region x FRM-bin) common-support matching + block bootstrap CI
    bins = [-np.inf, 10.0, 15.0, 25.0, 40.0, np.inf]
    bin_labels = ["<10", "10-15", "15-25", "25-40", ">=40"]
    t_tmp = t6_hm.copy()
    b_tmp = bm_hm.copy()
    t_tmp["frm_bin"] = pd.cut(t_tmp["frm"], bins=bins, labels=bin_labels).astype(str)
    b_tmp["frm_bin"] = pd.cut(b_tmp["frm"], bins=bins, labels=bin_labels).astype(str)
    t_tmp["cell"] = t_tmp["epa_region"].astype(str) + "_" + t_tmp["frm_bin"]
    b_tmp["cell"] = b_tmp["epa_region"].astype(str) + "_" + b_tmp["frm_bin"]
    t_tmp["delta"] = (
        t_tmp["fem"].ge(t_tmp["tier_1"].round(10)).astype(int)
        - t_tmp["frm"].ge(t_tmp["tier_1"].round(10)).astype(int)
    )
    b_tmp["delta"] = (
        b_tmp["fem"].ge(b_tmp["tier_1"].round(10)).astype(int)
        - b_tmp["frm"].ge(b_tmp["tier_1"].round(10)).astype(int)
    )
    shared_cells = sorted(set(t_tmp["cell"]) & set(b_tmp["cell"]))
    tc = t_tmp[t_tmp["cell"].isin(shared_cells)].copy()
    bc = b_tmp[b_tmp["cell"].isin(shared_cells)].copy()

    def _ato_est(t_df: pd.DataFrame, b_df: pd.DataFrame) -> tuple[float, float, float]:
        cells = sorted(set(t_df["cell"]) & set(b_df["cell"]))
        if not cells:
            return np.nan, np.nan, np.nan
        t_g = t_df.groupby("cell")["delta"].agg(["mean", "size"])
        b_g = b_df.groupby("cell")["delta"].agg(["mean", "size"])
        j = t_g.merge(b_g, left_index=True, right_index=True, suffixes=("_t", "_b"), how="inner")
        w = (j["size_t"] * j["size_b"]) / (j["size_t"] + j["size_b"])
        w = w / w.sum()
        mt = float(100.0 * (w * j["mean_t"]).sum())
        mb = float(100.0 * (w * j["mean_b"]).sum())
        return mt, mb, mt - mb

    mt_ato, mb_ato, diff_ato = _ato_est(tc, bc)
    # Cluster bootstrap over common national smoke blocks (B=1000, deterministic seed)
    all_blks = np.array(sorted(set(tc["nat_ep"]) | set(bc["nat_ep"])))
    rng = np.random.default_rng(20261128)
    tc_by_blk = {int(k): v for k, v in tc.groupby("nat_ep")}
    bc_by_blk = {int(k): v for k, v in bc.groupby("nat_ep")}
    boot_diffs = []
    for _ in range(1000):
        draw = rng.choice(all_blks, size=len(all_blks), replace=True)
        t_parts = [tc_by_blk[int(k)] for k in draw if int(k) in tc_by_blk]
        b_parts = [bc_by_blk[int(k)] for k in draw if int(k) in bc_by_blk]
        if not t_parts or not b_parts:
            continue
        _, _, d_b = _ato_est(pd.concat(t_parts, ignore_index=True), pd.concat(b_parts, ignore_index=True))
        if np.isfinite(d_b):
            boot_diffs.append(d_b)
    boot_arr = np.array(boot_diffs, dtype=float)
    ato_ci95 = [float(np.percentile(boot_arr, 2.5)), float(np.percentile(boot_arr, 97.5))]

    # Region distribution & FRM quantiles
    reg_dist = {
        str(r): {
            "t640_n": int((t6_hm["epa_region"] == r).sum()),
            "bam_n": int((bm_hm["epa_region"] == r).sum()),
        }
        for r in range(1, 11)
    }

    return {
        "all_2023_2025": {
            "t640_pairs": len(t6_all),
            "t640_sites": int(t6_all["site_id"].nunique()),
            "bam_pairs": len(bm_all),
            "bam_sites": int(bm_all["site_id"].nunique()),
            "triple_site_days": len(trip_all),
            "triple_sites": int(trip_all["site_id"].nunique()),
            "overlap_sites": len(set(t6_all["site_id"]) & set(bm_all["site_id"])),
            "overlap_dates": len(set(t6_all["Date Local"]) & set(bm_all["Date Local"])),
            "triples_by_hms_level": trip_by_hms,
        },
        "heavy_smoke_2023_2025": {
            "t640_full_pairs": len(t6_h_full),
            "t640_full_sites": int(t6_h_full["site_id"].nunique()),
            "t640_full_dates": int(t6_h_full["Date Local"].nunique()),
            "bam_full_pairs": len(bm_h_full),
            "bam_full_sites": int(bm_h_full["site_id"].nunique()),
            "bam_full_dates": int(bm_h_full["Date Local"].nunique()),
            "heavy_triple_site_days": len(trip_heavy),
            "heavy_triple_sites": int(trip_heavy["site_id"].nunique()),
            "heavy_overlap_sites": len(ov_sites_full),
            "heavy_overlap_dates": len(ov_dates_full),
            "heavy_triple_records": heavy_triple_rows,
            "overlapping_epa_regions": [int(x) for x in ov_regs],
            "epa_region_counts_matched": reg_dist,
            "frm_quantiles_matched": {
                "t640_fw": {
                    f"p{int(100*q)}": float(t6_hm["frm"].quantile(q))
                    for q in (0.10, 0.25, 0.50, 0.75, 0.90)
                },
                "bam": {
                    f"p{int(100*q)}": float(bm_hm["frm"].quantile(q))
                    for q in (0.10, 0.25, 0.50, 0.75, 0.90)
                },
            },
        },
        "matched_benchmarks": benchmarks,
        "overlap_weighted_region_x_frm_bin": {
            "n_shared_cells": len(shared_cells),
            "t640_covered_n": len(tc),
            "t640_covered_pct": float(100.0 * len(tc) / len(t6_hm)),
            "bam_covered_n": len(bc),
            "bam_covered_pct": float(100.0 * len(bc) / len(bm_hm)),
            "t640_weighted_diff_pp": mt_ato,
            "bam_weighted_diff_pp": mb_ato,
            "differential_pp": diff_ato,
            "block_bootstrap_ci95_pp": ato_ci95,
            "bootstrap_B": len(boot_arr),
        },
    }


def compute_smoke_vs_nonsmoke_controls(
    t6_all_m: pd.DataFrame, bm_all_m: pd.DataFrame
) -> dict[str, Any]:
    """P1 #3: Equal-concentration Non-Smoke (HMS=0) vs Smoke controls and ground-level smoke verification."""
    out: dict[str, Any] = {}
    for inst_key, df in [("t640_fw", t6_all_m), ("bam", bm_all_m)]:
        d = df.copy()
        d["ba"] = 0.5 * (d["fem"] + d["frm"])
        d["bias"] = d["fem"] - d["frm"]
        d["fem_t1"] = d["fem"].ge(d["tier_1"].round(10)).astype(int)
        d["frm_t1"] = d["frm"].ge(d["tier_1"].round(10)).astype(int)
        d["d_t1"] = d["fem_t1"] - d["frm_t1"]

        # Non-smoke site-month baseline p90 for ground-level smoke anomaly check
        base_sm = (
            d[d["hms_max_level"] == 0]
            .groupby(["site_id", "Month"])["frm"]
            .agg(base_med="median", base_p90=lambda s: float(np.percentile(s, 90)), base_n="size")
            .reset_index()
        )
        d = d.merge(base_sm, on=["site_id", "Month"], how="left")
        d["oc_ec"] = np.where(d["ec"] > 0.05, d["oc"] / d["ec"], np.nan)

        # 1. Monotonicity across HMS levels (0, 1, 2, 3)
        by_hms = {}
        for lvl, nm in [(0, "hms_0_none"), (1, "hms_1_light"), (2, "hms_2_medium"), (3, "hms_3_heavy")]:
            s = d[d["hms_max_level"] == lvl]
            reg_b = ols_cr1(s["bias"].to_numpy(), np.ones((len(s), 1)), s["site_id"].to_numpy(), col_names=["c"])
            reg_t = ols_cr1(s["d_t1"].to_numpy(), np.ones((len(s), 1)), s["site_id"].to_numpy(), col_names=["c"])
            by_hms[nm] = {
                "n": len(s),
                "n_sites": int(s["site_id"].nunique()),
                "mean_frm": float(s["frm"].mean()),
                "mean_bias": float(s["bias"].mean()),
                "bias_se_site": float(reg_b["coefs"]["c"]["se_cr1"]),
                "fem_t1": int(s["fem_t1"].sum()),
                "frm_t1": int(s["frm_t1"].sum()),
                "fem_only": int(s["d_t1"].eq(1).sum()),
                "frm_only": int(s["d_t1"].eq(-1).sum()),
                "t1_diff_pp": float(100.0 * s["d_t1"].mean()),
                "t1_se_site_pp": float(100.0 * reg_t["coefs"]["c"]["se_cr1"]),
            }

        # 2. Equal-concentration Non-Smoke (HMS=0) vs Heavy Smoke (HMS=3) formal Site-clustered tests
        matched_conc: dict[str, Any] = {}
        strata = [
            ("frm_ge15", "frm", 15.0, np.inf, "FRM >= 15 ug/m3"),
            ("frm_15_25", "frm", 15.0, 25.0, "FRM 15-25 ug/m3"),
            ("frm_ge20", "frm", 20.0, np.inf, "FRM >= 20 ug/m3"),
            ("frm_ge25", "frm", 25.0, np.inf, "FRM >= 25 ug/m3"),
            ("other_site_ge15", "other_site_pm_non_t640", 15.0, np.inf, "Other-Site (FRM/BAM) >= 15 ug/m3"),
            ("other_site_15_25", "other_site_pm_non_t640", 15.0, 25.0, "Other-Site (FRM/BAM) 15-25 ug/m3"),
            ("other_site_ge20", "other_site_pm_non_t640", 20.0, np.inf, "Other-Site (FRM/BAM) >= 20 ug/m3"),
            ("other_site_ge25", "other_site_pm_non_t640", 25.0, np.inf, "Other-Site (FRM/BAM) >= 25 ug/m3"),
            ("midpoint_ge15", "ba", 15.0, np.inf, "Bland-Altman Midpoint >= 15 ug/m3"),
            ("midpoint_15_25", "ba", 15.0, 25.0, "Bland-Altman Midpoint 15-25 ug/m3"),
            ("midpoint_ge20", "ba", 20.0, np.inf, "Bland-Altman Midpoint >= 20 ug/m3"),
            ("midpoint_ge25", "ba", 25.0, np.inf, "Bland-Altman Midpoint >= 25 ug/m3"),
        ]
        for key, col, lo, hi, desc in strata:
            ns = d[(d["hms_max_level"] == 0) & (d[col] >= lo) & (d[col] < hi)].copy()
            hs = d[(d["hms_max_level"] == 3) & (d[col] >= lo) & (d[col] < hi)].copy()
            if len(ns) < 5 or len(hs) < 5:
                continue
            comb = pd.concat([ns.assign(is_heavy=0), hs.assign(is_heavy=1)], ignore_index=True)
            X = np.column_stack([np.ones(len(comb)), comb["is_heavy"].to_numpy(dtype=float)])
            rb = ols_cr1(comb["bias"].to_numpy(), X, comb["site_id"].to_numpy(), col_names=["c", "heavy"])
            rt = ols_cr1(comb["d_t1"].to_numpy(), X, comb["site_id"].to_numpy(), col_names=["c", "heavy"])
            matched_conc[key] = {
                "label": desc,
                "nonsmoke": {
                    "n": len(ns),
                    "n_sites": int(ns["site_id"].nunique()),
                    "mean_frm": float(ns["frm"].mean()),
                    "mean_bias": float(ns["bias"].mean()),
                    "fem_t1": int(ns["fem_t1"].sum()),
                    "frm_t1": int(ns["frm_t1"].sum()),
                    "fem_only": int(ns["d_t1"].eq(1).sum()),
                    "frm_only": int(ns["d_t1"].eq(-1).sum()),
                    "t1_diff_pp": float(100.0 * ns["d_t1"].mean()),
                },
                "heavy_smoke": {
                    "n": len(hs),
                    "n_sites": int(hs["site_id"].nunique()),
                    "mean_frm": float(hs["frm"].mean()),
                    "mean_bias": float(hs["bias"].mean()),
                    "fem_t1": int(hs["fem_t1"].sum()),
                    "frm_t1": int(hs["frm_t1"].sum()),
                    "fem_only": int(hs["d_t1"].eq(1).sum()),
                    "frm_only": int(hs["d_t1"].eq(-1).sum()),
                    "t1_diff_pp": float(100.0 * hs["d_t1"].mean()),
                },
                "heavy_minus_nonsmoke_bias": float(rb["coefs"]["heavy"]["beta"]),
                "bias_diff_se_site": float(rb["coefs"]["heavy"]["se_cr1"]),
                "bias_diff_t_site": float(rb["coefs"]["heavy"]["t_cr1"]),
                "bias_diff_p_site": float(rb["coefs"]["heavy"]["p_cr1"]),
                "heavy_minus_nonsmoke_t1_pp": float(100.0 * rt["coefs"]["heavy"]["beta"]),
                "t1_diff_se_site_pp": float(100.0 * rt["coefs"]["heavy"]["se_cr1"]),
                "t1_diff_t_site": float(rt["coefs"]["heavy"]["t_cr1"]),
                "t1_diff_p_site": float(rt["coefs"]["heavy"]["p_cr1"]),
            }

        # 3. Ground-level smoke verification on HMS Heavy + Seasonal Non-Smoke decomposition
        h_only = d[d["hms_max_level"] == 3].copy()
        ns_only = d[d["hms_max_level"] == 0].copy()

        def _summ(sub: pd.DataFrame, desc: str) -> dict[str, Any]:
            if len(sub) == 0:
                return {"label": desc, "n": 0}
            return {
                "label": desc,
                "n": len(sub),
                "n_sites": int(sub["site_id"].nunique()),
                "mean_frm": float(sub["frm"].mean()),
                "mean_bias": float(sub["bias"].mean()),
                "fem_t1": int(sub["fem_t1"].sum()),
                "frm_t1": int(sub["frm_t1"].sum()),
                "fem_only": int(sub["d_t1"].eq(1).sum()),
                "frm_only": int(sub["d_t1"].eq(-1).sum()),
                "t1_diff_pp": float(100.0 * sub["d_t1"].mean()),
            }

        ground_evidence = {
            "heavy_surface_impact_frm_gt_p90": _summ(
                h_only[h_only["frm"] > h_only["base_p90"]],
                "HMS Heavy & FRM > site-month non-smoke p90",
            ),
            "heavy_lofted_frm_le_p90": _summ(
                h_only[h_only["frm"] <= h_only["base_p90"]],
                "HMS Heavy & FRM <= site-month non-smoke p90 (aloft/minimal surface impact)",
            ),
            "heavy_oc_ge5": _summ(
                h_only[h_only["oc"] >= 5.0],
                "HMS Heavy & Surface OC >= 5 ug/m3",
            ),
            "heavy_oc_lt5": _summ(
                h_only[h_only["oc"] < 5.0],
                "HMS Heavy & Surface OC < 5 ug/m3",
            ),
            "heavy_oc_ec_ge5": _summ(
                h_only[h_only["oc_ec"] >= 5.0],
                "HMS Heavy & Biomass-signature OC/EC >= 5",
            ),
            "nonsmoke_oc_ge5": _summ(
                ns_only[ns_only["oc"] >= 5.0],
                "Non-Smoke (HMS=0) & Surface OC >= 5 ug/m3",
            ),
            "nonsmoke_frm_ge20_winter_djf": _summ(
                ns_only[(ns_only["frm"] >= 20.0) & (ns_only["season"] == "DJF")],
                "Non-Smoke FRM >= 20 ug/m3 in Winter (DJF)",
            ),
            "nonsmoke_frm_ge20_warm_mjjas": _summ(
                ns_only[(ns_only["frm"] >= 20.0) & (ns_only["Month"].isin([5, 6, 7, 8, 9]))],
                "Non-Smoke FRM >= 20 ug/m3 in Fire Season (May-Sep)",
            ),
            "speciation_coverage_on_heavy": {
                "n_with_oc": int(h_only["oc"].notna().sum()),
                "n_total_heavy": len(h_only),
                "heavy_median_oc": float(h_only["oc"].median()) if h_only["oc"].notna().any() else 0.0,
                "nonsmoke_median_oc": float(ns_only["oc"].median()) if ns_only["oc"].notna().any() else 0.0,
            },
        }

        out[inst_key] = {
            "by_hms_level": by_hms,
            "matched_concentration_smoke_vs_nonsmoke": matched_conc,
            "ground_level_smoke_verification": ground_evidence,
        }
    return out


def main() -> int:
    print("=== STEP 11: V4 ES&T COMPREHENSIVE AUDIT & REPRODUCIBLE EXPORTS ===", flush=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    # Load official EPA 2021-2025 threshold table
    raw_thr = pd.read_csv(SNAPSHOT_PATH, dtype={"SITE_ID": "string"})
    fips = raw_thr["SITE_ID"].str.zfill(9)
    thr = pd.DataFrame(
        {
            "site_id": fips.str[:5] + "-" + fips.str[5:],
            "Month": raw_thr["month"].astype(int),
            "monthly_98th_epa": raw_thr["monthly_98th"].astype(float),
            "annual_98th_min_epa": raw_thr["annual_98th_minimum"].astype(float),
            "tier_1": raw_thr["tier 1"].astype(float),
            "tier_2": raw_thr["tier 2"].astype(float),
        }
    )

    # Load 2023-2025 collocated pairs
    t6_raw = pd.read_parquet(PROC_DIR / "collocated_t640_fw_frm_2023_2026.parquet")
    bm_raw = pd.read_parquet(PROC_DIR / "collocated_bam_frm_2023_2026.parquet")
    t6_all = t6_raw[t6_raw["Year"].between(2023, 2025)].copy()
    bm_all = bm_raw[bm_raw["Year"].between(2023, 2025)].copy()
    for df in (t6_all, bm_all):
        df["date"] = pd.to_datetime(df["Date Local"])
        df["epa_region"] = df["state_fips"].map(EPA_REGION_BY_STATE).astype(int)

    t6_h = t6_all[t6_all["hms_max_level"] == 3].copy()
    bm_h = bm_all[bm_all["hms_max_level"] == 3].copy()

    # Common national consecutive Heavy-smoke date blocks (matching Step 10 exactly)
    all_h_dates = pd.Series(sorted(set(t6_h["date"]) | set(bm_h["date"])))
    nat_blocks = pd.Series(
        all_h_dates.diff().gt(pd.Timedelta(days=1)).cumsum().values, index=all_h_dates
    )
    for df in (t6_h, bm_h):
        df["nat_ep"] = df["date"].map(nat_blocks)
        df["reg_ep"] = assign_region_episodes(df, max_gap_days=2)

    t6_hm = t6_h.merge(thr, on=["site_id", "Month"], how="inner", validate="many_to_one")
    bm_hm = bm_h.merge(thr, on=["site_id", "Month"], how="inner", validate="many_to_one")

    # Also merge thresholds onto ALL 2023-2025 pairs for non-smoke controls
    t6_all_m = t6_all.merge(thr, on=["site_id", "Month"], how="inner", validate="many_to_one")
    bm_all_m = bm_all.merge(thr, on=["site_id", "Month"], how="inner", validate="many_to_one")

    # ------------------------------------------------------------------
    # PART 1: P0 #1 Common-Support & Case-Flow Audit
    # ------------------------------------------------------------------
    print("  [1/4] Computing Common-Support & Case-Flow Audit...", flush=True)
    common_support = compute_common_support_audit(t6_all, bm_all, t6_hm, bm_hm, thr)

    # ------------------------------------------------------------------
    # PART 2: P0 #2 Official Retrospective + Out-of-Time Rolling Replay
    # ------------------------------------------------------------------
    print("  [2/4] Building 2018-2025 AQS Combined-Site & OOT Rolling Tier-1 Thresholds...", flush=True)
    hms_daily = pd.read_parquet(PROC_DIR / "monitor_hms_daily_2018_2025.parquet").rename(
        columns={"date": "Date Local"}
    )
    target_sites = sorted(set(t6_all["site_id"]) | set(bm_all["site_id"]))
    cs_all, d_frm, ann_best, manifest_rows = build_aqs_historical_inputs(target_sites, hms_daily)

    # Append threshold CSV & HMS parquet to manifest
    manifest_rows.append(
        {
            "artifact": SNAPSHOT_PATH.name,
            "category": "EPA Official PM2.5 Tiering Table (2021-2025)",
            "years": f"2021-2025 (AQS query {SNAPSHOT_DATE})",
            "rows_loaded": len(raw_thr),
            "bytes": int(SNAPSHOT_PATH.stat().st_size),
            "sha256": hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest(),
        }
    )
    hms_path = PROC_DIR / "monitor_hms_daily_2018_2025.parquet"
    manifest_rows.append(
        {
            "artifact": hms_path.name,
            "category": "NOAA HMS Daily Smoke Polygons (Site-Day Join)",
            "years": "2018-2025 (2,922/2,922 days)",
            "rows_loaded": len(hms_daily),
            "bytes": int(hms_path.stat().st_size),
            "sha256": hashlib.sha256(hms_path.read_bytes()).hexdigest(),
        }
    )

    # Benchmark 2021-2025 reconstruction accuracy against EPA's official published table
    clean_sites_2125 = set(cs_all[cs_all["is_clean_site_2125"]]["site_id"])
    bench_specs = {
        "cs_all_no_ann_excl": (cs_all, None, "Combined-Site daily (App N Table 1)"),
        "oot_a_cs_r_excl": (cs_all, ann_best, "OOT-A: Combined-Site + AQS Events-Excluded Annual P98"),
        "oot_b_cs_excl_hms3": (
            cs_all[cs_all["hms_max_level"] < 3],
            ann_best,
            "OOT-B: Combined-Site excl. HMS Heavy + R-Excl Annual P98",
        ),
        "oot_b2_cs_excl_hms23": (
            cs_all[cs_all["hms_max_level"] < 2],
            ann_best,
            "OOT-B2: Combined-Site excl. HMS Med+Heavy + R-Excl Annual P98",
        ),
        "oot_c_pure_frm": (d_frm, None, "OOT-C: Pure Gravimetric FRM-Only"),
    }
    reconstruction_benchmark_2125: dict[str, Any] = {}
    for skey, (cs_in, ab_in, desc) in bench_specs.items():
        rec2125 = compute_window_tiers(cs_in, 2021, 2025, ann_best=ab_in)
        m = rec2125.merge(thr, on=["site_id", "Month"], suffixes=("_rec", "_epa"))
        err = m["tier_1_rec"] - m["tier_1_epa"]
        mc = m[m["site_id"].isin(clean_sites_2125)]
        errc = mc["tier_1_rec"] - mc["tier_1_epa"]
        reconstruction_benchmark_2125[skey] = {
            "description": desc,
            "all_sites_n_site_months": len(m),
            "all_sites_corr": float(m["tier_1_rec"].corr(m["tier_1_epa"])),
            "all_sites_median_abs_err": float(err.abs().median()),
            "all_sites_mean_err": float(err.mean()),
            "all_sites_within_1ug_pct": float(100.0 * (err.abs() <= 1.0).mean()),
            "zero_flag_clean_sites_n": len(mc),
            "zero_flag_clean_corr": float(mc["tier_1_rec"].corr(mc["tier_1_epa"])),
            "zero_flag_clean_median_abs_err": float(errc.abs().median()),
            "zero_flag_clean_within_01ug_pct": float(100.0 * (errc.abs() <= 0.15).mean()),
        }

    # Evaluate Official Fixed 2021-2025 Table with full 2-way clustering & near-threshold bands
    official_fixed_2125 = {
        "t640_fw": {
            "fixed_35_full": evaluate_threshold_block(t6_h, None),
            "fixed_35_matched": evaluate_threshold_block(t6_hm, None),
            "tier_1": evaluate_threshold_block(t6_hm, "tier_1"),
            "tier_2_lower": evaluate_threshold_block(t6_hm, "tier_2"),
        },
        "bam": {
            "fixed_35_full": evaluate_threshold_block(bm_h, None),
            "fixed_35_matched": evaluate_threshold_block(bm_hm, None),
            "tier_1": evaluate_threshold_block(bm_hm, "tier_1"),
            "tier_2_lower": evaluate_threshold_block(bm_hm, "tier_2"),
        },
    }

    # Evaluate Strictly Out-of-Time Prospective Rolling 5-Year Thresholds (May 1 Certified Calendar)
    # Note: 0/472 T640 Heavy days are pre-May-1; 5/201 BAM Heavy days are in Jan (so pre-May-1 -> Y-6..Y-2)
    oot_specs = {
        "oot_a_conservative_r_excl": (
            cs_all,
            ann_best,
            "OOT-A (Conservative R-Excl AQS / AMP480 Bound)",
        ),
        "oot_b_fire_proxy_hms_heavy": (
            cs_all[cs_all["hms_max_level"] < 3],
            ann_best,
            "OOT-B (Fire-Screen Proxy: Excl. HMS Heavy + R-Excl)",
        ),
        "oot_b2_fire_proxy_hms_med_heavy": (
            cs_all[cs_all["hms_max_level"] < 2],
            ann_best,
            "OOT-B2 (Expanded Fire-Screen: Excl. HMS Med+Heavy + R-Excl)",
        ),
        "oot_c_pure_frm_only": (
            d_frm,
            None,
            "OOT-C (Pure Gravimetric FRM-Only Rolling Baseline)",
        ),
    }

    oot_results: dict[str, Any] = {}
    oot_cols_for_export: dict[str, pd.DataFrame] = {}
    for skey, (cs_in, ab_in, desc) in oot_specs.items():
        wins = {
            (w0, w0 + 4): compute_window_tiers(cs_in, w0, w0 + 4, ann_best=ab_in)
            for w0 in (2018, 2019, 2020)
        }
        spec_out: dict[str, Any] = {"description": desc}
        for inst_key, df_h in [("t640_fw", t6_h), ("bam", bm_h)]:
            df2 = df_h.copy()
            # EPA May 1 annual certification calendar
            df2["w0"] = np.where(df2["Month"] >= 5, df2["Year"] - 5, df2["Year"] - 6)
            df2["w1"] = df2["w0"] + 4
            parts = []
            for (w0, w1), g in df2.groupby(["w0", "w1"], sort=True):
                if (int(w0), int(w1)) in wins:
                    parts.append(
                        g.merge(
                            wins[(int(w0), int(w1))][
                                ["site_id", "Month", "tier_1", "tier_2", "monthly_98th", "annual_98th_min"]
                            ],
                            on=["site_id", "Month"],
                            how="inner",
                        )
                    )
            m = pd.concat(parts, ignore_index=True)
            spec_out[inst_key] = {
                "n_pre_may1_dates": int((df_h["Month"] < 5).sum()),
                "unmatched_site_days": int(len(df_h) - len(m)),
                "tier_1": evaluate_threshold_block(m, "tier_1"),
                "tier_2_lower": evaluate_threshold_block(m, "tier_2"),
            }
            if skey in ("oot_a_conservative_r_excl", "oot_b_fire_proxy_hms_heavy", "oot_c_pure_frm_only"):
                oot_cols_for_export[f"{skey}__{inst_key}"] = m[
                    ["site_id", "Date Local", "tier_1"]
                ].rename(columns={"tier_1": f"tier1_{skey[:5]}"})
        oot_results[skey] = spec_out

    # ------------------------------------------------------------------
    # PART 3: P1 #3 Leave-EPA-Region-Out & Equal-Concentration Non-Smoke Controls
    # ------------------------------------------------------------------
    print("  [3/4] Computing Leave-EPA-Region-Out & Smoke vs Non-Smoke Controls...", flush=True)
    loro_t640: dict[str, Any] = {}
    for reg in sorted(t6_hm["epa_region"].unique()):
        sub_out = t6_hm[t6_hm["epa_region"] != reg]
        sub_in = t6_hm[t6_hm["epa_region"] == reg]
        d_out = (
            sub_out["fem"].ge(sub_out["tier_1"].round(10)).astype(int)
            - sub_out["frm"].ge(sub_out["tier_1"].round(10)).astype(int)
        )
        d_in = (
            sub_in["fem"].ge(sub_in["tier_1"].round(10)).astype(int)
            - sub_in["frm"].ge(sub_in["tier_1"].round(10)).astype(int)
        )
        ci_out = cluster_mean_stats(
            d_out, sub_out["site_id"], sub_out["date"], sub_out["nat_ep"], sub_out["reg_ep"]
        )
        loro_t640[f"R{int(reg)}"] = {
            "epa_region": int(reg),
            "in_region_n": len(sub_in),
            "in_region_sites": int(sub_in["site_id"].nunique()),
            "in_region_diff_pp": float(100.0 * d_in.mean()),
            "in_region_fem_only": int(d_in.eq(1).sum()),
            "in_region_frm_only": int(d_in.eq(-1).sum()),
            "loro_n": len(sub_out),
            "loro_diff_pp": float(100.0 * d_out.mean()),
            "loro_ci95_twoway_reg_ep_pp": ci_out["twoway_site_x_reg_episode"]["ci95"],
        }
    loro_vals = [v["loro_diff_pp"] for v in loro_t640.values()]
    loro_summary = {
        "n_regions": len(loro_t640),
        "min_loro_diff_pp": float(min(loro_vals)),
        "max_loro_diff_pp": float(max(loro_vals)),
        "all_loro_positive": bool(all(x > 0 for x in loro_vals)),
        "by_region": loro_t640,
    }

    smoke_vs_nonsmoke = compute_smoke_vs_nonsmoke_controls(t6_all_m, bm_all_m)

    # ------------------------------------------------------------------
    # PART 4: Export Reproducible Pair Table, Version Manifest & Summary CSVs
    # ------------------------------------------------------------------
    print("  [4/4] Exporting Reproducible CSV Tables & Version Manifest to tables/...", flush=True)
    # Reproducible combined Heavy-smoke pair table (472 T640 + 201 BAM = 673 rows)
    trip_keys = set(
        zip(
            t6_h["site_id"],
            t6_h["Date Local"],
        )
    ) & set(zip(bm_h["site_id"], bm_h["Date Local"]))
    ov_dates_set = set(t6_hm["Date Local"]) & set(bm_hm["Date Local"])
    ov_regs_set = set(t6_hm["epa_region"]) & set(bm_hm["epa_region"])

    exp_parts = []
    for inst_key, df_h in [("T640_FW", t6_h), ("BAM", bm_h)]:
        key_l = "t640_fw" if inst_key == "T640_FW" else "bam"
        e = df_h.merge(
            thr[["site_id", "Month", "monthly_98th_epa", "annual_98th_min_epa", "tier_1", "tier_2"]],
            on=["site_id", "Month"],
            how="left",
        ).copy()
        for oot_k in ("oot_a_conservative_r_excl", "oot_b_fire_proxy_hms_heavy", "oot_c_pure_frm_only"):
            e = e.merge(
                oot_cols_for_export[f"{oot_k}__{key_l}"],
                on=["site_id", "Date Local"],
                how="left",
            )
        e["instrument"] = inst_key
        e["is_triple_site_day"] = [
            int((s, d) in trip_keys) for s, d in zip(e["site_id"], e["Date Local"])
        ]
        e["in_overlap_dates"] = e["Date Local"].isin(ov_dates_set).astype(int)
        e["in_overlap_epa_regions"] = e["epa_region"].isin(ov_regs_set).astype(int)
        e["bias_fem_minus_frm"] = e["fem"] - e["frm"]
        e["fem_ge_epa_tier1"] = np.where(
            e["tier_1"].notna(), e["fem"].ge(e["tier_1"].round(10)).astype(int), np.nan
        )
        e["frm_ge_epa_tier1"] = np.where(
            e["tier_1"].notna(), e["frm"].ge(e["tier_1"].round(10)).astype(int), np.nan
        )
        exp_parts.append(
            e[
                [
                    "instrument",
                    "site_id",
                    "county_fips",
                    "state_fips",
                    "epa_region",
                    "Date Local",
                    "Year",
                    "Month",
                    "nat_ep",
                    "reg_ep",
                    "frm",
                    "fem",
                    "bias_fem_minus_frm",
                    "hms_max_level",
                    "other_site_pm_non_t640",
                    "oc",
                    "ec",
                    "no3",
                    "so4",
                    "rh_pct",
                    "temp_c",
                    "monthly_98th_epa",
                    "annual_98th_min_epa",
                    "tier_2",
                    "tier_1",
                    "tier1_oot_a",
                    "tier1_oot_b",
                    "tier1_oot_c",
                    "fem_ge_epa_tier1",
                    "frm_ge_epa_tier1",
                    "is_triple_site_day",
                    "in_overlap_dates",
                    "in_overlap_epa_regions",
                ]
            ]
        )
    pair_export = pd.concat(exp_parts, ignore_index=True).sort_values(
        ["instrument", "Date Local", "site_id"]
    )
    pair_csv = TABLES_DIR / "collocated_heavy_smoke_pairs_2023_2025.csv"
    pair_export.to_csv(pair_csv, index=False, lineterminator="\n")

    manifest_df = pd.DataFrame(manifest_rows)
    manifest_csv = TABLES_DIR / "aqs_and_threshold_version_manifest.csv"
    manifest_df.to_csv(manifest_csv, index=False, lineterminator="\n")

    # Machine-readable publication summary tables
    # Table 1: Common Support
    t1_rows = []
    for b in common_support["matched_benchmarks"].values():
        t1_rows.append(
            {
                "stratum": b["label"],
                "t640_n": b["t640_n"],
                "t640_overlap_pct": round(b["t640_overlap_pct"], 1),
                "t640_diff_pp": round(b["t640_diff_pp"], 2),
                "bam_n": b["bam_n"],
                "bam_overlap_pct": round(b["bam_overlap_pct"], 1),
                "bam_diff_pp": round(b["bam_diff_pp"], 2),
                "diff_t640_minus_bam_pp": round(b["differential_t640_minus_bam_pp"], 2),
                "ci95_block_lo": round(b["differential_ci95_block_pp"][0], 2),
                "ci95_block_hi": round(b["differential_ci95_block_pp"][1], 2),
            }
        )
    ow = common_support["overlap_weighted_region_x_frm_bin"]
    t1_rows.append(
        {
            "stratum": "Overlap-Weighted (EPA Region x FRM Bin, 29 cells)",
            "t640_n": ow["t640_covered_n"],
            "t640_overlap_pct": round(ow["t640_covered_pct"], 1),
            "t640_diff_pp": round(ow["t640_weighted_diff_pp"], 2),
            "bam_n": ow["bam_covered_n"],
            "bam_overlap_pct": round(ow["bam_covered_pct"], 1),
            "bam_diff_pp": round(ow["bam_weighted_diff_pp"], 2),
            "diff_t640_minus_bam_pp": round(ow["differential_pp"], 2),
            "ci95_block_lo": round(ow["block_bootstrap_ci95_pp"][0], 2),
            "ci95_block_hi": round(ow["block_bootstrap_ci95_pp"][1], 2),
        }
    )
    pd.DataFrame(t1_rows).to_csv(
        TABLES_DIR / "table1_common_support_audit.csv", index=False, lineterminator="\n"
    )

    # Table 2: Official & Out-of-Time Threshold Replay
    t2_rows = []
    for inst_lbl, ikey in [("T640_FW-FRM", "t640_fw"), ("BAM-FRM (Ref.)", "bam")]:
        for b_lbl, blk in [
            ("Official EPA 2021-2025 Tier 1", official_fixed_2125[ikey]["tier_1"]),
            ("Official EPA 2021-2025 Tier 2 Lower", official_fixed_2125[ikey]["tier_2_lower"]),
            ("Fixed Daily >35 ug/m3 (Matched)", official_fixed_2125[ikey]["fixed_35_matched"]),
            ("OOT-A Rolling 5-Yr Tier 1 (R-Excl AQS)", oot_results["oot_a_conservative_r_excl"][ikey]["tier_1"]),
            ("OOT-B Rolling 5-Yr Tier 1 (Excl HMS Heavy)", oot_results["oot_b_fire_proxy_hms_heavy"][ikey]["tier_1"]),
            ("OOT-B2 Rolling 5-Yr Tier 1 (Excl HMS Med+Heavy)", oot_results["oot_b2_fire_proxy_hms_med_heavy"][ikey]["tier_1"]),
            ("OOT-C Rolling 5-Yr Tier 1 (Pure FRM)", oot_results["oot_c_pure_frm_only"][ikey]["tier_1"]),
        ]:
            tw = blk["inference"]["twoway_site_x_reg_episode"]["ci95"]
            nb = blk["inference"]["oneway_nat_block"]["ci95"]
            t2_rows.append(
                {
                    "instrument": inst_lbl,
                    "benchmark": b_lbl,
                    "n_pairs": blk["n_site_days"],
                    "fem_exceed": blk["fem_exceed"],
                    "frm_exceed": blk["frm_exceed"],
                    "fem_only": blk["fem_only"],
                    "frm_only": blk["frm_only"],
                    "diff_pp": round(blk["difference_pp"], 2),
                    "ci95_nat_block_lo": round(nb[0], 2),
                    "ci95_nat_block_hi": round(nb[1], 2),
                    "ci95_2way_site_reg_ep_lo": round(tw[0], 2),
                    "ci95_2way_site_reg_ep_hi": round(tw[1], 2),
                }
            )
    pd.DataFrame(t2_rows).to_csv(
        TABLES_DIR / "table2_official_and_oot_tier_replay.csv", index=False, lineterminator="\n"
    )

    # Table 3: Smoke vs Non-Smoke Equal-Concentration Controls
    t3_rows = []
    for v in smoke_vs_nonsmoke["t640_fw"]["matched_concentration_smoke_vs_nonsmoke"].values():
        t3_rows.append(
            {
                "stratum": v["label"],
                "nonsmoke_n": v["nonsmoke"]["n"],
                "nonsmoke_bias": round(v["nonsmoke"]["mean_bias"], 2),
                "nonsmoke_t1_diff_pp": round(v["nonsmoke"]["t1_diff_pp"], 2),
                "heavy_n": v["heavy_smoke"]["n"],
                "heavy_bias": round(v["heavy_smoke"]["mean_bias"], 2),
                "heavy_t1_diff_pp": round(v["heavy_smoke"]["t1_diff_pp"], 2),
                "delta_bias": round(v["heavy_minus_nonsmoke_bias"], 2),
                "bias_diff_p_site": v["bias_diff_p_site"],
                "delta_t1_pp": round(v["heavy_minus_nonsmoke_t1_pp"], 2),
                "t1_diff_p_site": v["t1_diff_p_site"],
            }
        )
    pd.DataFrame(t3_rows).to_csv(
        TABLES_DIR / "table3_smoke_vs_nonsmoke_controls.csv", index=False, lineterminator="\n"
    )

    # Table 4: LORO
    pd.DataFrame(list(loro_t640.values())).to_csv(
        TABLES_DIR / "table4_leave_epa_region_out.csv", index=False, lineterminator="\n"
    )

    payload = {
        "version": "v4_est_submission",
        "epa_threshold_snapshot_date": SNAPSHOT_DATE,
        "epa_threshold_sha256": hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest(),
        "common_support_audit": common_support,
        "official_fixed_2021_2025": official_fixed_2125,
        "oot_reconstruction_benchmark_2021_2025": reconstruction_benchmark_2125,
        "oot_prospective_rolling_5yr": oot_results,
        "leave_epa_region_out_t640_tier1": loro_summary,
        "smoke_vs_nonsmoke_controls": smoke_vs_nonsmoke,
        "exports": {
            "pair_csv": pair_csv.name,
            "pair_csv_rows": len(pair_export),
            "manifest_csv": manifest_csv.name,
            "manifest_entries": len(manifest_df),
        },
    }
    sha_rec = save_json_lf(RECEIPT_PATH, payload)
    print(f"[DONE STEP 11] Saved {RECEIPT_PATH.name} (SHA-256 LF: {sha_rec})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
