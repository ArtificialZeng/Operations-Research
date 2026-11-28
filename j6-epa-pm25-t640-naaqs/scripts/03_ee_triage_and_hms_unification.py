"""Step 03 (Pillar 3 + Unification Tests U2 & U3 + Honest Test 4 Audit):
Pre-Trend-Clean Exogenous DV_18_20 State Exceptional-Event (40 CFR 50.14) Triage,
Fixed EPA-Concurrence Decomposition, Within-State RI (B=1000), LOSO, Inverted-U Profile,
and Satellite NOAA HMS Unification Tests (U2 & U3).

Fixes EVERY Wave-6 Pillar 3 Audit Defect (Problems 1-4 & 11):
  - Uses exact nested-FE DOF and high-precision LSDV-exact WCB (econ_utils.py).
  - Standardizes 100% of Pillar 3 tests on strictly pre-trend-clean exogenous DV_18_20 [8.5, 11.5]
    (with [9.0, 12.0] sensitivity) at BOTH Monitor-Year (Monitor FE + State x Year FE +
    monitor smoke controls + log_obs) AND County-Year levels.
  - Fixes the 50.4% EPA-concurrence bug permanently (true_ee_conc iff obs_conc < obs_incl or
    |mean_incl - mean_conc| > 1e-6), decomposing true_ee_flag = unconc_flag + true_ee_conc.
  - Transparently reports ALL event-study years (2018-2025, ref=2020), explicitly showing both
    the 2022-2023 designation surge and dead-zero 2024-2025 flow.
  - Drops flawed Test 3 timestamp DiD; reports Test 4 primary-monitor selection honestly with
    legacy installation-age control (first_year).
  - Executes Killer Unification Tests U2 & U3 linking Pillar 2 T640 optical amplification
    directly to Pillar 3 EE flagging under identical satellite NOAA HMS wildfire smoke exposure.
"""

from __future__ import annotations

import json
import math
from typing import Any

import numpy as np
import pandas as pd
from econ_utils import (
    PROC_DIR,
    RES_DIR,
    VALID_STATES,
    WAVE6_RAW_DIR,
    demean_groups,
    mc_class,
    ols_cr1,
    read_zip_csv,
    save_json_lf,
)
from scipy import stats


def build_monitor_daily_smoke_and_hms(
    my_aln: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compute annual monitor-level & county-level ground smoke severity + satellite NOAA HMS
    exposure metrics across 2018-2025 (aligned daily records only, no raw 236/238), plus each
    site's strictly pre-period 5-year historical (2018-2022) FRM 98th-percentile baseline for
    official EPA Wildfire Tier-1/Tier-2 Exceptional Event screening.
    """
    # Build stitch map from my_aln? Wait: load daily 2018-2025 aligned and map canon_id cleanly
    # Reuse stitch logic consistent with Step 01: map POC>=21 for 736/738 to POC-20
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
    d_parts = []
    for yr in range(2018, 2026):
        df = read_zip_csv(
            WAVE6_RAW_DIR / f"daily_88101_{yr}.zip",
            usecols=use_d,
            dtype={
                "State Code": str,
                "County Code": str,
                "Site Num": str,
                "POC": str,
                "Method Code": str,
            },
        )
        df = df[df["Sample Duration"].isin(["24 HOUR", "24-HR BLK AVG"])].copy()
        df["Year"] = yr
        d_parts.append(df)
    daily = pd.concat(d_parts, ignore_index=True)
    daily["state_fips"] = daily["State Code"].str.zfill(2)
    daily = daily[daily["state_fips"].isin(VALID_STATES)].copy()
    daily["county_fips"] = daily["state_fips"] + daily["County Code"].str.zfill(3)
    daily["site_id"] = daily["county_fips"] + "-" + daily["Site Num"].str.zfill(4)
    daily["poc_int"] = pd.to_numeric(daily["POC"], errors="coerce").fillna(-1).astype(int)
    daily["method_code"] = daily["Method Code"].str.strip().str.replace(".0", "", regex=False)
    daily["Event Type"] = daily["Event Type"].fillna("None").astype(str)
    daily = daily[daily["Event Type"].isin(["None", "Included"])].copy()
    daily["Arithmetic Mean"] = pd.to_numeric(daily["Arithmetic Mean"], errors="coerce")
    daily = daily.dropna(subset=["Arithmetic Mean"]).copy()
    mc_u = daily[["method_code", "Method Name"]].drop_duplicates("method_code")
    mc_dict = {r["method_code"]: mc_class(r["method_code"], r["Method Name"]) for _, r in mc_u.iterrows()}
    daily["inst"] = daily["method_code"].map(mc_dict)

    # Strictly pre-period 5-year historical (2018-2022) gravimetric FRM site baseline for
    # official EPA Wildfire Tier-1/Tier-2 screening (98th percentile & min(98th pct, 35 ug/m3))
    frm_hist_day = (
        daily[(daily["inst"] == "FRM") & (daily["Year"].between(2018, 2022))]
        .groupby(["site_id", "Year", "Date Local"], as_index=False)
        .agg(frm_pm=("Arithmetic Mean", "mean"))
    )
    site_hist_1822 = (
        frm_hist_day.groupby("site_id", as_index=False)
        .agg(
            n_days_1822=("frm_pm", "size"),
            n_yrs_1822=("Year", "nunique"),
            p98_hist_1822=("frm_pm", lambda s: float(np.percentile(s, 98))),
        )
    )
    site_hist_1822["tier1_min_p98_35"] = np.minimum(site_hist_1822["p98_hist_1822"], 35.0)
    site_hist_1822["tier1_max_p98_35"] = np.maximum(site_hist_1822["p98_hist_1822"], 35.0)

    # Aligned universe only (drop T640_RAW 236/238)
    daily = daily[daily["inst"] != "T640_RAW"].copy()
    # Apply the exact canonical stitch_map saved by Step 01 so zero regulatory monitors are dropped!
    stitch_path = PROC_DIR / "t640_stitch_map.json"
    stitch_map: dict[str, str] = json.loads(stitch_path.read_text(encoding="utf-8"))
    raw_mid = daily["site_id"] + "-" + daily["poc_int"].astype(str)
    daily["canon_id"] = raw_mid.map(lambda m: stitch_map.get(m, m))

    # Deduplicate per (canon_id, Date Local)
    m_day = (
        daily.groupby(["canon_id", "site_id", "county_fips", "state_fips", "Year", "Date Local"], as_index=False)
        .agg(pm25=("Arithmetic Mean", "mean"))
    )

    # Monitor-year ground smoke metrics
    m_smk = (
        m_day.groupby(["canon_id", "Year"], as_index=False)
        .agg(
            n_days_gt15=("pm25", lambda s: int((s >= 15.0).sum())),
            n_days_gt25=("pm25", lambda s: int((s >= 25.0).sum())),
            n_days_gt35=("pm25", lambda s: int((s >= 35.0).sum())),
            max_pm25=("pm25", "max"),
            excess_gt15=("pm25", lambda s: float(np.sum(np.maximum(0.0, s - 15.0)))),
            excess_gt25=("pm25", lambda s: float(np.sum(np.maximum(0.0, s - 25.0)))),
            clean_mean_lt25=("pm25", lambda s: float(s[s < 25.0].mean()) if (s < 25.0).any() else np.nan),
        )
    )

    # County-year ground smoke metrics (county-day max PM2.5)
    c_day = (
        m_day.groupby(["county_fips", "state_fips", "Year", "Date Local"], as_index=False)
        .agg(c_pm25=("pm25", "max"))
    )
    c_smk = (
        c_day.groupby(["county_fips", "state_fips", "Year"], as_index=False)
        .agg(
            n_days_gt15=("c_pm25", lambda s: int((s >= 15.0).sum())),
            n_days_gt25=("c_pm25", lambda s: int((s >= 25.0).sum())),
            n_days_gt35=("c_pm25", lambda s: int((s >= 35.0).sum())),
            max_pm25=("c_pm25", "max"),
            excess_gt15=("c_pm25", lambda s: float(np.sum(np.maximum(0.0, s - 15.0)))),
            excess_gt25=("c_pm25", lambda s: float(np.sum(np.maximum(0.0, s - 25.0)))),
            clean_mean_lt25=("c_pm25", lambda s: float(s[s < 25.0].mean()) if (s < 25.0).any() else np.nan),
        )
    )

    # Satellite NOAA HMS annual exposure per (site_id, Year) and (county_fips, Year)
    hms = pd.read_parquet(PROC_DIR / "monitor_hms_daily_2018_2025.parquet")
    hms["Year"] = hms["date"].str.slice(0, 4).astype(int)
    hms["county_fips"] = hms["site_id"].str.slice(0, 5)

    site_hms = (
        hms.groupby(["site_id", "Year"], as_index=False)
        .agg(
            hms_any_days=("hms_max_level", lambda s: int((s >= 1).sum())),
            hms_light_only_days=("hms_max_level", lambda s: int((s == 1).sum())),
            hms_med_days=("hms_max_level", lambda s: int((s == 2).sum())),
            hms_heavy_days=("hms_max_level", lambda s: int((s == 3).sum())),
        )
    )
    # County-day max HMS level -> county-year HMS days
    c_hms_day = (
        hms.groupby(["county_fips", "Year", "date"], as_index=False)
        .agg(max_lvl=("hms_max_level", "max"))
    )
    cnty_hms = (
        c_hms_day.groupby(["county_fips", "Year"], as_index=False)
        .agg(
            hms_any_days=("max_lvl", lambda s: int((s >= 1).sum())),
            hms_light_only_days=("max_lvl", lambda s: int((s == 1).sum())),
            hms_med_days=("max_lvl", lambda s: int((s == 2).sum())),
            hms_heavy_days=("max_lvl", lambda s: int((s == 3).sum())),
        )
    )

    m_smk = m_smk.merge(
        my_aln[["canon_id", "site_id", "Year"]].drop_duplicates(["canon_id", "Year"]),
        on=["canon_id", "Year"],
        how="left",
    ).merge(site_hms, on=["site_id", "Year"], how="left")
    c_smk = c_smk.merge(cnty_hms, on=["county_fips", "Year"], how="left")

    for df in (m_smk, c_smk):
        for col in ("hms_any_days", "hms_light_only_days", "hms_med_days", "hms_heavy_days"):
            df[col] = df[col].fillna(0).astype(int)
        df["log_days15"] = np.log1p(df["n_days_gt15"])
        df["log_days25"] = np.log1p(df["n_days_gt25"])
        df["log_days35"] = np.log1p(df["n_days_gt35"])
        df["log_max_pm"] = np.log(np.maximum(df["max_pm25"], 1.0))
        df["log_excess15"] = np.log1p(np.maximum(df["excess_gt15"], 0.0))
        df["log_excess25"] = np.log1p(np.maximum(df["excess_gt25"], 0.0))
        df["max_pm_sq"] = df["log_max_pm"] ** 2
        df["ex25_sq"] = df["log_excess25"] ** 2
        df["d25_sq"] = df["log_days25"] ** 2
        df["log_hms_l"] = np.log1p(df["hms_light_only_days"])
        df["log_hms_m"] = np.log1p(df["hms_med_days"])
        df["log_hms_h"] = np.log1p(df["hms_heavy_days"])
        df["hms_h_sq"] = df["log_hms_h"] ** 2

    return m_smk.drop(columns=["site_id"]), c_smk, site_hist_1822


def run_u1_historical_tier1_screening(site_hist_1822: pd.DataFrame) -> dict[str, Any]:
    """Compute official EPA Wildfire Tier-1/Tier-2 screening divergence in 2023-2025 using each
    collocated site's strictly pre-period 5-year historical (2018-2022) gravimetric FRM
    98th percentile and min(98th percentile, 35 ug/m3), via exact paired McNemar tests and
    Site-clustered CR1 + Roodman WCB paired-difference LPMs for T640_FW vs FRM and BAM vs FRM.
    """
    out: dict[str, Any] = {}
    for key, fname, label in [
        ("t640_fw", "collocated_t640_fw_frm_2023_2026.parquet", "T640_FW (636/638)"),
        ("bam", "collocated_bam_frm_2023_2026.parquet", "BAM (170/209)"),
    ]:
        col = pd.read_parquet(PROC_DIR / fname)
        col = col[col["Year"].isin([2023, 2024, 2025])].copy()
        n_sites_tot = int(col["site_id"].nunique())
        merged = col.merge(site_hist_1822, on="site_id", how="left")
        base = merged[merged["n_days_1822"] >= 30].copy()
        u_sites = base.drop_duplicates("site_id")
        u_sites_3y = base[base["n_yrs_1822"] >= 3].drop_duplicates("site_id")

        inst_out: dict[str, Any] = {
            "baseline_audit_2018_2022": {
                "n_collocated_sites_total": n_sites_tot,
                "n_sites_matched_ge30d": len(u_sites),
                "n_sites_matched_ge3y": len(u_sites_3y),
                "matched_site_share_pct": float(100.0 * len(u_sites) / max(n_sites_tot, 1)),
                "median_p98_hist_1822": float(u_sites["p98_hist_1822"].median()),
                "p25_p98_hist_1822": float(u_sites["p98_hist_1822"].quantile(0.25)),
                "p75_p98_hist_1822": float(u_sites["p98_hist_1822"].quantile(0.75)),
                "pct_sites_p98_gt35": float(100.0 * (u_sites["p98_hist_1822"] > 35.0).mean()),
            }
        }

        subsets = {
            "all_paired_days": base,
            "hms_any_smoke": base[base["hms_max_level"] >= 1],
            "hms_medium_or_heavy": base[base["hms_max_level"] >= 2],
            "hms_heavy_smoke": base[base["hms_max_level"] == 3],
            "other_site_ge25": base[base["other_site_pm"] >= 25.0],
        }
        for sname, sub in subsets.items():
            rec: dict[str, Any] = {
                "n_days": len(sub),
                "n_sites": int(sub["site_id"].nunique()),
            }
            sub_3y = sub[sub["n_yrs_1822"] >= 3]
            thresh_specs = [
                ("gt_hist_p98_1822", sub, "p98_hist_1822"),
                ("gt_tier1_min_p98_35", sub, "tier1_min_p98_35"),
                ("gt_tier1_min_p98_35_ge3y", sub_3y, "tier1_min_p98_35"),
                ("gt_max_p98_35", sub, "tier1_max_p98_35"),
            ]
            for tname, df_t, tcol in thresh_specs:
                valid = df_t[tcol].notna()
                sv = df_t[valid]
                n_v = len(sv)
                if n_v < 10:
                    rec[tname] = {"n_valid_days": n_v, "skipped": True}
                    continue
                fh = (sv["fem"] > sv[tcol]).to_numpy(dtype=bool)
                gh = (sv["frm"] > sv[tcol]).to_numpy(dtype=bool)
                fem_n = int(fh.sum())
                frm_n = int(gh.sum())
                fem_only = int((fh & (~gh)).sum())
                frm_only = int(((~fh) & gh).sum())
                both = int((fh & gh).sum())
                disc = fem_only + frm_only
                mcnemar_p = float(stats.binomtest(fem_only, disc, 0.5).pvalue) if disc > 0 else 1.0
                ratio = float(fem_n / frm_n) if frm_n > 0 else None
                diff_arr = fh.astype(float) - gh.astype(float)
                lpm = ols_cr1(
                    diff_arr,
                    np.ones((n_v, 1), dtype=float),
                    sv["site_id"].to_numpy(),
                    None,
                    ["fem_minus_frm"],
                    wcb_var_idx=0,
                    wcb_B=499,
                )
                c = lpm.get("coefs", {}).get("fem_minus_frm", {})
                rec[tname] = {
                    "n_valid_days": n_v,
                    "n_sites": int(sv["site_id"].nunique()),
                    "fem_exceed_n": fem_n,
                    "frm_exceed_n": frm_n,
                    "fem_rate_pct": float(100.0 * fem_n / max(n_v, 1)),
                    "frm_rate_pct": float(100.0 * frm_n / max(n_v, 1)),
                    "trigger_multiplier_ratio": ratio,
                    "fem_only_discordant": fem_only,
                    "frm_only_discordant": frm_only,
                    "both_exceed": both,
                    "mcnemar_exact_p": mcnemar_p,
                    "paired_diff_pp": float(100.0 * c["beta"]) if "beta" in c else None,
                    "se_site_cr1_pp": float(100.0 * c["se_cr1"]) if "se_cr1" in c else None,
                    "t_site_cr1": float(c["t_cr1"]) if "t_cr1" in c else None,
                    "p_site_cr1": float(c["p_cr1"]) if "p_cr1" in c else None,
                    "p_wcb": float(lpm["wcb"]["p_wcb"]) if "wcb" in lpm else None,
                }
            inst_out[sname] = rec
        out[key] = inst_out

        # Concise audit log
        hh = inst_out["hms_heavy_smoke"]["gt_tier1_min_p98_35"]
        aa = inst_out["all_paired_days"]["gt_tier1_min_p98_35"]
        print(
            f"  [U1 Historical 5-Yr (2018-22) Tier-1 min(p98,35): {label}] "
            f"All: {aa['fem_exceed_n']} vs {aa['frm_exceed_n']} ({aa['trigger_multiplier_ratio']:.2f}x, "
            f"disc {aa['fem_only_discordant']} vs {aa['frm_only_discordant']}, p={aa['mcnemar_exact_p']:.2e}) | "
            f"HMS Heavy: {hh['fem_exceed_n']} vs {hh['frm_exceed_n']} ({hh['trigger_multiplier_ratio']:.2f}x, "
            f"disc {hh['fem_only_discordant']} vs {hh['frm_only_discordant']}, p={hh['mcnemar_exact_p']:.2e}, "
            f"t={hh['t_site_cr1']:+.2f}, p_WCB={hh['p_wcb']:.3f})",
            flush=True,
        )
    return out


def run_within_state_ri(
    df: pd.DataFrame,
    outcome_col: str,
    ctrl_cols: list[str],
    unit_fe_col: str,
    B: int = 1000,
    seed: int = 20261126,
) -> dict[str, Any]:
    """Exact within-state county-level Randomization Inference (B=1000 permutations),
    re-demeaning permuted treat_post against [unit_fe_col, st_yr] and projecting out controls.
    """
    y = df[outcome_col].to_numpy(dtype=np.float64)
    Z = df[ctrl_cols].to_numpy(dtype=np.float64)
    fe_g = [df[unit_fe_col].to_numpy(), df["st_yr"].to_numpy()]

    M = demean_groups(np.column_stack([y, df["treat_post"].to_numpy(dtype=np.float64), Z]), fe_g, tol=1e-12, max_iter=400)
    y_dm = M[:, 0]
    tp_dm = M[:, 1]
    Z_dm = M[:, 2:]

    # Project out Z_dm via QR/lstsq
    ZtZ_inv = np.linalg.inv(Z_dm.T @ Z_dm)
    y_perp = y_dm - Z_dm @ (ZtZ_inv @ (Z_dm.T @ y_dm))
    tp_perp = tp_dm - Z_dm @ (ZtZ_inv @ (Z_dm.T @ tp_dm))
    obs_beta = float((tp_perp @ y_perp) / (tp_perp @ tp_perp))

    # County -> nb mapping, grouped by state_fips for within-state permutation
    c_map = df[["county_fips", "state_fips", "nb"]].drop_duplicates("county_fips").reset_index(drop=True)
    st_groups = c_map.groupby("state_fips").indices
    c_idx_map = {cf: i for i, cf in enumerate(c_map["county_fips"].tolist())}
    row_cidx = np.array([c_idx_map[cf] for cf in df["county_fips"].tolist()], dtype=np.int64)
    post_arr = df["post"].to_numpy(dtype=np.float64)
    nb_orig = c_map["nb"].to_numpy(dtype=np.int64)

    u_codes, u_u = pd.factorize(df[unit_fe_col].to_numpy(), sort=False)
    u_cnt = np.bincount(u_codes, minlength=len(u_u)).astype(np.float64)
    sy_codes, sy_u = pd.factorize(df["st_yr"].to_numpy(), sort=False)
    sy_cnt = np.bincount(sy_codes, minlength=len(sy_u)).astype(np.float64)

    def fast_dm(v: np.ndarray) -> np.ndarray:
        x = v.copy()
        for _ in range(120):
            mu = np.bincount(u_codes, weights=x, minlength=len(u_u)) / u_cnt
            x -= mu[u_codes]
            ms = np.bincount(sy_codes, weights=x, minlength=len(sy_u)) / sy_cnt
            x -= ms[sy_codes]
            if max(float(np.max(np.abs(mu))), float(np.max(np.abs(ms)))) < 1e-10:
                break
        return x

    rng = np.random.default_rng(seed)
    ri_betas = np.empty(B, dtype=np.float64)
    for b in range(B):
        nb_p = nb_orig.copy()
        for idxs in st_groups.values():
            if len(idxs) > 1:
                nb_p[idxs] = rng.permutation(nb_p[idxs])
        tp_p = nb_p[row_cidx] * post_arr
        tp_p_dm = fast_dm(tp_p)
        tp_p_perp = tp_p_dm - Z_dm @ (ZtZ_inv @ (Z_dm.T @ tp_p_dm))
        denom = float(tp_p_perp @ tp_p_perp)
        ri_betas[b] = float((tp_p_perp @ y_perp) / denom) if denom > 1e-12 else 0.0

    p_ri = float((1 + np.sum(np.abs(ri_betas) >= abs(obs_beta))) / (B + 1))
    return {
        "B": int(B),
        "obs_beta": obs_beta,
        "p_ri_2sided": p_ri,
        "ri_sd": float(np.std(ri_betas, ddof=1)),
        "ri_p95_abs": float(np.percentile(np.abs(ri_betas), 95)),
        "ri_max_abs": float(np.max(np.abs(ri_betas))),
    }


def main() -> int:
    print("=== STEP 03 (PILLAR 3 + U2/U3): PRE-TREND-CLEAN EE TRIAGE & NOAA HMS UNIFICATION ===", flush=True)
    my_all = pd.read_parquet(PROC_DIR / "stitched_monitor_year_aln_2018_2025.parquet")
    cdv = pd.read_parquet(PROC_DIR / "county_dvs_stitched.parquet")

    # Regulatory App. N-eligible monitors only, with >= 30 valid days in year
    my = my_all[(my_all["is_appn_reg"] == 1) & (my_all["total_days"] >= 30)].copy()

    print("  Building monitor-year & county-year ground smoke + satellite NOAA HMS covariates + 2018-2022 FRM Tier-1 baseline...", flush=True)
    m_smk, c_smk, site_hist_1822 = build_monitor_daily_smoke_and_hms(my)
    u1_hist_tier1 = run_u1_historical_tier1_screening(site_hist_1822)

    # Pure FRM-only 2018-2020 county DV and Clean non-smoke (<25) 2018-2020 county baseline
    frm_1820 = (
        my[(my["dom_inst"] == "FRM") & (my["Year"].isin([2018, 2019, 2020]))]
        .groupby(["canon_id", "county_fips"], as_index=False)
        .agg(dv=("ann_mean", "mean"), ny=("Year", "nunique"))
    )
    frm_1820 = (
        frm_1820[frm_1820["ny"] >= 2]
        .groupby("county_fips", as_index=False)["dv"]
        .max()
        .rename(columns={"dv": "dv1820_frm"})
    )
    clean_1820 = (
        c_smk[c_smk["Year"].isin([2018, 2019, 2020])]
        .groupby("county_fips", as_index=False)["clean_mean_lt25"]
        .mean()
        .rename(columns={"clean_mean_lt25": "clean_1820"})
    )
    # 2018-2019 baseline for Fake-Rule 2020-2021 vs 2018-2019 placebo
    dv_1819 = (
        my[my["Year"].isin([2018, 2019])]
        .groupby(["canon_id", "county_fips"], as_index=False)
        .agg(dv=("ann_mean", "mean"), ny=("Year", "nunique"))
    )
    dv_1819 = (
        dv_1819[dv_1819["ny"] >= 2]
        .groupby("county_fips", as_index=False)["dv"]
        .max()
        .rename(columns={"dv": "dv1819_aln"})
    )

    # --- Assemble MONITOR-YEAR panel (2018-2025) ---
    my_p = (
        my.merge(m_smk, on=["canon_id", "Year"], how="inner")
        .merge(cdv.drop(columns=["state_fips"]), on="county_fips", how="left")
        .merge(frm_1820, on="county_fips", how="left")
        .merge(clean_1820, on="county_fips", how="left")
        .merge(dv_1819, on="county_fips", how="left")
    )
    my_p["log_obs"] = np.log(np.maximum(my_p["total_days"].to_numpy(dtype=float), 1.0))
    my_p["st_yr"] = my_p["state_fips"] + "_" + my_p["Year"].astype(str)
    my_p["cnty_yr"] = my_p["county_fips"] + "_" + my_p["Year"].astype(str)
    my_p["is_t640"] = my_p["dom_inst"].isin(["T640_FW", "T640_RETRO"]).astype(int)
    my_p["is_frm"] = (my_p["dom_inst"] == "FRM").astype(int)
    my_p["is_bam"] = (my_p["dom_inst"] == "BAM").astype(int)
    my_p.to_parquet(PROC_DIR / "pillar3_monitor_year_panel.parquet", index=False)

    # --- Assemble COUNTY-YEAR panel (2018-2025) ---
    cy_ee = (
        my_p.groupby(["county_fips", "state_fips", "Year"], as_index=False)
        .agg(
            true_ee_flag=("true_ee_flag", "max"),
            true_ee_conc=("true_ee_conc", "max"),
            ee_red_all=("ee_red_all", "max"),
            ee_red_conc=("ee_red_conc", "max"),
            n_mon=("canon_id", "nunique"),
        )
    )
    cy_ee["unconc_flag"] = ((cy_ee["true_ee_flag"] == 1) & (cy_ee["true_ee_conc"] == 0)).astype(int)
    cy_p = (
        cy_ee.merge(c_smk, on=["county_fips", "state_fips", "Year"], how="inner")
        .merge(cdv.drop(columns=["state_fips"]), on="county_fips", how="left")
        .merge(frm_1820, on="county_fips", how="left")
        .merge(clean_1820, on="county_fips", how="left")
        .merge(dv_1819, on="county_fips", how="left")
    )
    cy_p["log_n_mon"] = np.log(np.maximum(cy_p["n_mon"].to_numpy(dtype=float), 1.0))
    cy_p["st_yr"] = cy_p["state_fips"] + "_" + cy_p["Year"].astype(str)
    cy_p.to_parquet(PROC_DIR / "pillar3_county_year_panel.parquet", index=False)

    smk_ctrls = [
        "log_days15",
        "log_days25",
        "log_days35",
        "log_max_pm",
        "log_excess15",
        "log_excess25",
        "max_pm_sq",
        "ex25_sq",
        "d25_sq",
    ]
    hms_ctrls = ["log_hms_l", "log_hms_m", "log_hms_h", "hms_h_sq"]
    mon_ctrls = smk_ctrls + ["log_obs"]
    mon_ctrls_hms = smk_ctrls + hms_ctrls + ["log_obs"]
    cnty_ctrls = smk_ctrls + ["log_n_mon"]
    cnty_ctrls_hms = smk_ctrls + hms_ctrls + ["log_n_mon"]

    def prep_band(df_in: pd.DataFrame, bcol: str, lo: float, hi: float, ctrl_hi: float = 8.0) -> pd.DataFrame:
        s = df_in[df_in[bcol].notna()].copy()
        s["nb"] = ((s[bcol] >= lo) & (s[bcol] <= hi)).astype(int)
        s["cl"] = (s[bcol] < ctrl_hi).astype(int)
        return s[(s["nb"] == 1) | (s["cl"] == 1)].copy()

    def run_event_study_and_did(
        df_band: pd.DataFrame,
        unit_fe: str,
        ctrls: list[str],
        outcome: str,
        wcb_B: int = 999,
    ) -> dict[str, Any]:
        s = df_band.copy()
        yrs_ev = [2018, 2019, 2021, 2022, 2023, 2024, 2025]
        for y in yrs_ev:
            s[f"nb_{y}"] = s["nb"] * (s["Year"] == y).astype(int)
        ev_cols = [f"nb_{y}" for y in yrs_ev] + ctrls
        es_cnty = ols_cr1(
            s[outcome].to_numpy(),
            s[ev_cols].to_numpy(),
            s["county_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ev_cols,
            joint_test_indices=[0, 1, 2],  # 2018, 2019, 2021 vs 2020
        )
        es_state = ols_cr1(
            s[outcome].to_numpy(),
            s[ev_cols].to_numpy(),
            s["state_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ev_cols,
            joint_test_indices=[0, 1, 2],
        )

        # Also Event Study normalized to ref=2021 (last pre-designation year before 2022-2023 window)
        yrs_ev21 = [2018, 2019, 2020, 2022, 2023, 2024, 2025]
        for y in yrs_ev21:
            s[f"nb21_{y}"] = s["nb"] * (s["Year"] == y).astype(int)
        ev21_cols = [f"nb21_{y}" for y in yrs_ev21] + ctrls
        es21_cnty = ols_cr1(
            s[outcome].to_numpy(),
            s[ev21_cols].to_numpy(),
            s["county_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ev21_cols,
            joint_test_indices=[0, 1, 2],
        )

        # Linear pre-trends: 2018-2020 AND 2018-2021
        pre20 = s[s["Year"].isin([2018, 2019, 2020])].copy()
        pre20["lin"] = pre20["nb"] * (pre20["Year"] - 2018)
        r_pre20 = ols_cr1(
            pre20[outcome].to_numpy(),
            pre20[["lin"] + ctrls].to_numpy(),
            pre20["county_fips"].to_numpy(),
            [pre20[unit_fe].to_numpy(), pre20["st_yr"].to_numpy()],
            ["lin"] + ctrls,
        )
        pre21 = s[s["Year"].isin([2018, 2019, 2020, 2021])].copy()
        pre21["lin"] = pre21["nb"] * (pre21["Year"] - 2018)
        r_pre21 = ols_cr1(
            pre21[outcome].to_numpy(),
            pre21[["lin"] + ctrls].to_numpy(),
            pre21["county_fips"].to_numpy(),
            [pre21[unit_fe].to_numpy(), pre21["st_yr"].to_numpy()],
            ["lin"] + ctrls,
        )

        # Pooled DiD: (a) 2022-2025 vs 2018-2021, (b) 2022-2023 designation window vs 2018-2021, (c) 2024-2025 vs 2018-2021
        s["post_2225"] = (s["Year"] >= 2022).astype(int)
        s["tp_2225"] = s["nb"] * s["post_2225"]
        did_2225_cnty = ols_cr1(
            s[outcome].to_numpy(),
            s[["tp_2225"] + ctrls].to_numpy(),
            s["county_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ["tp_2225"] + ctrls,
            wcb_var_idx=0,
            wcb_B=wcb_B,
        )
        did_2225_state = ols_cr1(
            s[outcome].to_numpy(),
            s[["tp_2225"] + ctrls].to_numpy(),
            s["state_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ["tp_2225"] + ctrls,
            wcb_var_idx=0,
            wcb_B=wcb_B,
        )

        # Split post window: 2022-2023 vs 2024-2025 explicitly inside full 2018-2025 panel
        s["tp_2223"] = s["nb"] * s["Year"].isin([2022, 2023]).astype(int)
        s["tp_2425"] = s["nb"] * s["Year"].isin([2024, 2025]).astype(int)
        did_split_cnty = ols_cr1(
            s[outcome].to_numpy(),
            s[["tp_2223", "tp_2425"] + ctrls].to_numpy(),
            s["county_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ["tp_2223", "tp_2425"] + ctrls,
            wcb_var_idx=0,
            wcb_B=wcb_B,
        )
        did_split_state = ols_cr1(
            s[outcome].to_numpy(),
            s[["tp_2223", "tp_2425"] + ctrls].to_numpy(),
            s["state_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ["tp_2223", "tp_2425"] + ctrls,
            wcb_var_idx=0,
            wcb_B=wcb_B,
        )
        did_split_2425_wcb_state = ols_cr1(
            s[outcome].to_numpy(),
            s[["tp_2223", "tp_2425"] + ctrls].to_numpy(),
            s["state_fips"].to_numpy(),
            [s[unit_fe].to_numpy(), s["st_yr"].to_numpy()],
            ["tp_2223", "tp_2425"] + ctrls,
            wcb_var_idx=1,
            wcb_B=wcb_B,
        )
        return {
            "event_study_county_cr1": es_cnty,
            "event_study_state_cr1": es_state,
            "event_study_ref2021_county_cr1": es21_cnty,
            "pre_linear_2018_2020": r_pre20,
            "pre_linear_2018_2021": r_pre21,
            "did_2225_county_cr1": did_2225_cnty,
            "did_2225_state_cr1": did_2225_state,
            "did_split_2223_2425_county_cr1": did_split_cnty,
            "did_split_2223_2425_state_cr1": did_split_state,
            "did_split_2425_wcb_state_cr1": did_split_2425_wcb_state["wcb"],
        }

    # =========================================================================
    # 1. HEADLINE MONITOR-YEAR & COUNTY-YEAR SUITE ON EXOGENOUS DV_18_20 [8.5, 11.5]
    # =========================================================================
    print("\n--- 1. HEADLINE MONITOR-YEAR & COUNTY-YEAR ON EXOGENOUS DV_18_20 [8.5, 11.5] ---", flush=True)
    m_85 = prep_band(my_p, "dv1820_aln", 8.5, 11.5, 8.0)
    c_85 = prep_band(cy_p, "dv1820_aln", 8.5, 11.5, 8.0)
    m_90 = prep_band(my_p, "dv1820_aln", 9.0, 12.0, 8.0)

    mon_outcomes: dict[str, Any] = {}
    for ycol in ("true_ee_flag", "unconc_flag", "true_ee_conc", "ee_red_all", "ee_red_conc"):
        mon_outcomes[ycol] = run_event_study_and_did(m_85, "canon_id", mon_ctrls, ycol, wcb_B=999)
        d_c = mon_outcomes[ycol]["did_2225_county_cr1"]
        d_s = mon_outcomes[ycol]["did_2225_state_cr1"]
        ds_s = mon_outcomes[ycol]["did_split_2223_2425_state_cr1"]
        pl = mon_outcomes[ycol]["pre_linear_2018_2021"]["coefs"]["lin"]
        jf = mon_outcomes[ycol]["event_study_county_cr1"].get("joint_F", {})
        print(
            f"  [MON-YR {ycol:13s}] 22-25={d_c['coefs']['tp_2225']['beta']:+.4f} "
            f"(cnty t={d_c['coefs']['tp_2225']['t_cr1']:+.2f}, p_WCB={d_c['wcb']['p_wcb']:.3f} | "
            f"st t={d_s['coefs']['tp_2225']['t_cr1']:+.2f}, p_WCB={d_s['wcb']['p_wcb']:.3f}) | "
            f"22-23={ds_s['coefs']['tp_2223']['beta']:+.4f} (st p_WCB={ds_s['wcb']['p_wcb']:.3f}), "
            f"24-25={ds_s['coefs']['tp_2425']['beta']:+.4f} | pre_lin p={pl['p_cr1']:.3f}, jointF p={jf.get('p', math.nan):.3f}",
            flush=True,
        )

    # Also Monitor-Year adding Satellite NOAA HMS controls directly!
    mon_with_hms = run_event_study_and_did(m_85, "canon_id", mon_ctrls_hms, "true_ee_flag", wcb_B=999)
    mon_90_12 = run_event_study_and_did(m_90, "canon_id", mon_ctrls, "true_ee_flag", wcb_B=999)

    cnty_outcomes: dict[str, Any] = {}
    for ycol in ("true_ee_flag", "unconc_flag", "true_ee_conc", "ee_red_all"):
        cnty_outcomes[ycol] = run_event_study_and_did(c_85, "county_fips", cnty_ctrls, ycol, wcb_B=999)
        d_c = cnty_outcomes[ycol]["did_2225_county_cr1"]
        d_s = cnty_outcomes[ycol]["did_2225_state_cr1"]
        pl = cnty_outcomes[ycol]["pre_linear_2018_2021"]["coefs"]["lin"]
        print(
            f"  [CNTY-YR {ycol:12s}] 22-25={d_c['coefs']['tp_2225']['beta']:+.4f} "
            f"(cnty t={d_c['coefs']['tp_2225']['t_cr1']:+.2f}, p_WCB={d_c['wcb']['p_wcb']:.3f} | "
            f"st t={d_s['coefs']['tp_2225']['t_cr1']:+.2f}, p_WCB={d_s['wcb']['p_wcb']:.3f}) | pre_lin p={pl['p_cr1']:.3f}",
            flush=True,
        )
    cnty_with_hms = run_event_study_and_did(c_85, "county_fips", cnty_ctrls_hms, "true_ee_flag", wcb_B=999)

    # =========================================================================
    # 2. ROBUSTNESS SUITE (100% ON DV_18_20 [8.5, 11.5]): RI (B=1000), LOSO,
    #    SMOKE-ONLY, FRM-ONLY BASE, CLEAN-DAYS BASE, FAKE-RULE PLACEBO, INVERTED-U, BAILOUT
    # =========================================================================
    print("\n--- 2. ROBUSTNESS SUITE ON DV_18_20 [8.5, 11.5] (RI B=1000, LOSO, SUBSAMPLES, INVERTED-U) ---", flush=True)
    m_85_ri = m_85.copy()
    m_85_ri["post"] = (m_85_ri["Year"] >= 2022).astype(int)
    m_85_ri["treat_post"] = m_85_ri["nb"] * m_85_ri["post"]
    ri_mon = run_within_state_ri(m_85_ri, "true_ee_flag", mon_ctrls, "canon_id", B=1000, seed=20261126)

    c_85_ri = c_85.copy()
    c_85_ri["post"] = (c_85_ri["Year"] >= 2022).astype(int)
    c_85_ri["treat_post"] = c_85_ri["nb"] * c_85_ri["post"]
    ri_cnty = run_within_state_ri(c_85_ri, "true_ee_flag", cnty_ctrls, "county_fips", B=1000, seed=20261126)
    print(f"  Within-State RI (B=1000): Mon-Yr obs={ri_mon['obs_beta']:+.4f}, p_RI={ri_mon['p_ri_2sided']:.4f} | Cnty-Yr obs={ri_cnty['obs_beta']:+.4f}, p_RI={ri_cnty['p_ri_2sided']:.4f}", flush=True)

    # LOSO on Monitor-Year DV_18_20 [8.5, 11.5]
    loso_list = []
    for st in sorted(m_85_ri["state_fips"].unique()):
        sub = m_85_ri[m_85_ri["state_fips"] != st]
        rs = ols_cr1(
            sub["true_ee_flag"].to_numpy(),
            sub[["treat_post"] + mon_ctrls].to_numpy(),
            sub["county_fips"].to_numpy(),
            [sub["canon_id"].to_numpy(), sub["st_yr"].to_numpy()],
            ["treat_post"] + mon_ctrls,
        )
        if "coefs" in rs:
            c = rs["coefs"]["treat_post"]
            loso_list.append({"dropped_state": st, "beta": c["beta"], "t": c["t_cr1"], "p": c["p_cr1"]})
    worst = min(loso_list, key=lambda x: x["t"])
    loso_summary = {
        "n_states": len(loso_list),
        "min_beta": min(x["beta"] for x in loso_list),
        "max_beta": max(x["beta"] for x in loso_list),
        "min_t": worst["t"],
        "max_p": max(x["p"] for x in loso_list),
        "worst_dropped_state": worst,
    }
    print(f"  LOSO ({loso_summary['n_states']} states): beta=[{loso_summary['min_beta']:+.4f}, {loso_summary['max_beta']:+.4f}], min_t={loso_summary['min_t']:+.2f}, max_p={loso_summary['max_p']:.4f} (worst={worst['dropped_state']})", flush=True)

    # Subsample & Alternative Exogenous Baseline Specs (Monitor-Year)
    rob_specs: dict[str, Any] = {}
    spec_defs = [
        ("smoke_ge25_days_only", m_85_ri[m_85_ri["n_days_gt25"] >= 1], mon_ctrls),
        ("smoke_ge15_days_only", m_85_ri[m_85_ri["n_days_gt15"] >= 1], mon_ctrls),
        ("noaa_hms_heavy_days_only", m_85_ri[m_85_ri["hms_heavy_days"] >= 1], mon_ctrls_hms),
        ("strict_appn_3yr_dv1820", prep_band(my_p, "dv1820_strict", 8.5, 11.5, 8.0), mon_ctrls),
        ("frm_only_baseline_dv1820", prep_band(my_p, "dv1820_frm", 8.5, 11.5, 8.0), mon_ctrls),
        ("clean_nonsmoke_baseline_1820", prep_band(my_p, "clean_1820", 8.0, 11.0, 7.5), mon_ctrls),
    ]
    for sname, df_s, c_list in spec_defs:
        ds = df_s.copy()
        ds["treat_post"] = ds["nb"] * (ds["Year"] >= 2022).astype(int)
        r_c = ols_cr1(
            ds["true_ee_flag"].to_numpy(),
            ds[["treat_post"] + c_list].to_numpy(),
            ds["county_fips"].to_numpy(),
            [ds["canon_id"].to_numpy(), ds["st_yr"].to_numpy()],
            ["treat_post"] + c_list,
            wcb_var_idx=0,
            wcb_B=499,
        )
        r_s = ols_cr1(
            ds["true_ee_flag"].to_numpy(),
            ds[["treat_post"] + c_list].to_numpy(),
            ds["state_fips"].to_numpy(),
            [ds["canon_id"].to_numpy(), ds["st_yr"].to_numpy()],
            ["treat_post"] + c_list,
            wcb_var_idx=0,
            wcb_B=499,
        )
        rob_specs[sname] = {"county_cr1": r_c, "state_cr1": r_s}
        cc = r_c.get("coefs", {}).get("treat_post", {})
        print(
            f"    Rob [{sname:30s}] N={r_c.get('n',0):4d}: beta={cc.get('beta',math.nan):+.4f} "
            f"(cnty t={cc.get('t_cr1',math.nan):+.2f}, p_WCB={r_c.get('wcb',{}).get('p_wcb',math.nan):.3f} | "
            f"st p_WCB={r_s.get('wcb',{}).get('p_wcb',math.nan):.3f})",
            flush=True,
        )

    # Fake-Rule Placebo: 2020-2021 vs 2018-2019 on DV_18_19
    pl = prep_band(my_p[my_p["Year"].isin([2018, 2019, 2020, 2021])], "dv1819_aln", 8.5, 11.5, 8.0)
    pl["treat_post"] = pl["nb"] * (pl["Year"] >= 2020).astype(int)
    rob_specs["fake_rule_placebo_2020_21_vs_18_19"] = ols_cr1(
        pl["true_ee_flag"].to_numpy(),
        pl[["treat_post"] + mon_ctrls].to_numpy(),
        pl["county_fips"].to_numpy(),
        [pl["canon_id"].to_numpy(), pl["st_yr"].to_numpy()],
        ["treat_post"] + mon_ctrls,
        wcb_var_idx=0,
        wcb_B=499,
    )
    print(
        f"    Fake-Rule Placebo 2020-21 vs 18-19: beta={rob_specs['fake_rule_placebo_2020_21_vs_18_19']['coefs']['treat_post']['beta']:+.4f} "
        f"(p={rob_specs['fake_rule_placebo_2020_21_vs_18_19']['coefs']['treat_post']['p_cr1']:.4f})",
        flush=True,
    )

    # Inverted-U 40 CFR 50.14 Regulatory-Significance Profile across DV_18_20 bins (<7.0 ref!)
    inv_u = my_p[my_p["dv1820_aln"].notna()].copy()
    inv_u["post"] = (inv_u["Year"] >= 2022).astype(int)
    inv_u["b_70_85"] = ((inv_u["dv1820_aln"] >= 7.0) & (inv_u["dv1820_aln"] < 8.5)).astype(int) * inv_u["post"]
    inv_u["b_85_95"] = ((inv_u["dv1820_aln"] >= 8.5) & (inv_u["dv1820_aln"] < 9.5)).astype(int) * inv_u["post"]
    inv_u["b_95_115"] = ((inv_u["dv1820_aln"] >= 9.5) & (inv_u["dv1820_aln"] <= 11.5)).astype(int) * inv_u["post"]
    inv_u["b_gt115"] = (inv_u["dv1820_aln"] > 11.5).astype(int) * inv_u["post"]
    iu_cols = ["b_70_85", "b_85_95", "b_95_115", "b_gt115"] + mon_ctrls
    inverted_u = {
        "monitor_year_county_cr1": ols_cr1(
            inv_u["true_ee_flag"].to_numpy(),
            inv_u[iu_cols].to_numpy(),
            inv_u["county_fips"].to_numpy(),
            [inv_u["canon_id"].to_numpy(), inv_u["st_yr"].to_numpy()],
            iu_cols,
        ),
        "monitor_year_state_cr1": ols_cr1(
            inv_u["true_ee_flag"].to_numpy(),
            inv_u[iu_cols].to_numpy(),
            inv_u["state_fips"].to_numpy(),
            [inv_u["canon_id"].to_numpy(), inv_u["st_yr"].to_numpy()],
            iu_cols,
        ),
        "bin_counts_monitors": {
            "<7.0": int(inv_u[inv_u["dv1820_aln"] < 7.0]["canon_id"].nunique()),
            "7.0-8.5": int(inv_u[(inv_u["dv1820_aln"] >= 7.0) & (inv_u["dv1820_aln"] < 8.5)]["canon_id"].nunique()),
            "8.5-9.5": int(inv_u[(inv_u["dv1820_aln"] >= 8.5) & (inv_u["dv1820_aln"] < 9.5)]["canon_id"].nunique()),
            "9.5-11.5": int(inv_u[(inv_u["dv1820_aln"] >= 9.5) & (inv_u["dv1820_aln"] <= 11.5)]["canon_id"].nunique()),
            ">11.5": int(inv_u[inv_u["dv1820_aln"] > 11.5]["canon_id"].nunique()),
        },
    }
    print("  Inverted-U Profile (ref <7.0):", {k: round(inverted_u["monitor_year_county_cr1"]["coefs"][k]["beta"], 4) for k in ("b_70_85", "b_85_95", "b_95_115", "b_gt115")}, flush=True)

    # T640 Bailed-Out vs Still-Binding Substitution Test (on Exogenous DV_18_20 Raw vs Aligned!)
    sub_b = my_p[my_p["dv1820_raw_r"].notna() & my_p["dv1820_aln_r"].notna()].copy()
    sub_b["grp_bailed"] = ((sub_b["dv1820_raw_r"] >= 9.1) & (sub_b["dv1820_raw_r"] <= 12.0) & (sub_b["dv1820_aln_r"] <= 9.0)).astype(int)
    sub_b["grp_still"] = ((sub_b["dv1820_aln_r"] >= 9.1) & (sub_b["dv1820_aln_r"] <= 12.0)).astype(int)
    sub_b["grp_clean"] = (sub_b["dv1820_raw_r"] < 8.0).astype(int)
    sub_b = sub_b[(sub_b["grp_bailed"] == 1) | (sub_b["grp_still"] == 1) | (sub_b["grp_clean"] == 1)].copy()
    sub_b["post"] = (sub_b["Year"] >= 2022).astype(int)
    sub_b["still_post"] = sub_b["grp_still"] * sub_b["post"]
    sub_b["bailed_post"] = sub_b["grp_bailed"] * sub_b["post"]
    bailout_sub = {
        "n_counties_still": int(sub_b[sub_b["grp_still"] == 1]["county_fips"].nunique()),
        "n_counties_bailed": int(sub_b[sub_b["grp_bailed"] == 1]["county_fips"].nunique()),
        "n_counties_clean": int(sub_b[sub_b["grp_clean"] == 1]["county_fips"].nunique()),
        "vs_clean_county_cr1": ols_cr1(
            sub_b["true_ee_flag"].to_numpy(),
            sub_b[["still_post", "bailed_post"] + mon_ctrls].to_numpy(),
            sub_b["county_fips"].to_numpy(),
            [sub_b["canon_id"].to_numpy(), sub_b["st_yr"].to_numpy()],
            ["still_post", "bailed_post"] + mon_ctrls,
            wcb_var_idx=0,
            wcb_B=499,
        ),
        "vs_clean_state_cr1": ols_cr1(
            sub_b["true_ee_flag"].to_numpy(),
            sub_b[["still_post", "bailed_post"] + mon_ctrls].to_numpy(),
            sub_b["state_fips"].to_numpy(),
            [sub_b["canon_id"].to_numpy(), sub_b["st_yr"].to_numpy()],
            ["still_post", "bailed_post"] + mon_ctrls,
            wcb_var_idx=0,
            wcb_B=499,
        ),
    }

    # =========================================================================
    # 3. HONEST TEST 4 AUDIT: COLLOCATED NAAQS PRIMARY SELECTION WITH LEGACY-AGE CONTROL
    # =========================================================================
    print("\n--- 3. HONEST TEST 4 AUDIT (LEGACY INSTALLATION-AGE CONTROL) ---", flush=True)
    s2425 = (
        my_p[my_p["Year"].isin([2024, 2025])]
        .groupby(["site_id", "county_fips", "state_fips", "canon_id", "dom_inst", "is_naaqs_primary"], as_index=False)
        .agg(pm=("ann_mean", "mean"), first_yr=("first_year", "min"))
    )
    col_sites = set(s2425[s2425["dom_inst"] == "FRM"]["site_id"]) & set(s2425[s2425["dom_inst"] == "T640_FW"]["site_id"])
    cs = s2425[s2425["site_id"].isin(col_sites)].copy()
    cs_piv = (
        cs.groupby(["site_id", "county_fips", "state_fips"], as_index=False)
        .agg(
            frm_is_prim=("is_naaqs_primary", lambda s: int(s[cs.loc[s.index, "dom_inst"] == "FRM"].max())),
            frm_first_yr=("first_yr", lambda s: float(s[cs.loc[s.index, "dom_inst"] == "FRM"].min())),
            t640_first_yr=("first_yr", lambda s: float(s[cs.loc[s.index, "dom_inst"] == "T640_FW"].min())),
        )
        .merge(cdv[["county_fips", "dv1820_aln"]], on="county_fips", how="left")
    )
    cs_piv = cs_piv.dropna(subset=["dv1820_aln", "frm_first_yr", "t640_first_yr"]).copy()
    cs_piv["nb"] = ((cs_piv["dv1820_aln"] >= 8.5) & (cs_piv["dv1820_aln"] <= 11.5)).astype(float)
    cs_piv["frm_older_yrs"] = cs_piv["t640_first_yr"] - cs_piv["frm_first_yr"]
    test4_honest = {
        "n_collocated_sites": len(cs_piv),
        "without_age_ctrl_state_fe": ols_cr1(
            cs_piv["frm_is_prim"].to_numpy(),
            cs_piv[["nb"]].to_numpy(),
            cs_piv["county_fips"].to_numpy(),
            [cs_piv["state_fips"].to_numpy()],
            ["nb"],
            wcb_var_idx=0,
            wcb_B=499,
        ),
        "with_legacy_age_ctrl_state_fe": ols_cr1(
            cs_piv["frm_is_prim"].to_numpy(),
            cs_piv[["nb", "frm_older_yrs"]].to_numpy(),
            cs_piv["county_fips"].to_numpy(),
            [cs_piv["state_fips"].to_numpy()],
            ["nb", "frm_older_yrs"],
            wcb_var_idx=0,
            wcb_B=499,
        ),
    }
    t4c = test4_honest["with_legacy_age_ctrl_state_fe"]["coefs"]["nb"]
    print(f"  Honest Test 4 (with FRM legacy-age ctrl, N={len(cs_piv)}): nb={t4c['beta']:+.4f} (t={t4c['t_cr1']:+.2f}, p={t4c['p_cr1']:.4f}, WCB={test4_honest['with_legacy_age_ctrl_state_fe']['wcb']['p_wcb']:.3f})", flush=True)

    # =========================================================================
    # 4. KILLER UNIFICATION U2 & U3: T640 -> EE FLAGGING UNDER IDENTICAL NOAA HMS SMOKE!
    # =========================================================================
    print("\n--- 4. KILLER UNIFICATION U2 & U3 (T640 INSTRUMENT EFFECT & HMS STATUTORY TRIAGE) ---", flush=True)
    # U2A: Inside borderline counties (DV_18_20 in [8.5, 11.5]) during 2022-2025 (and peak 2023),
    # controlling for State x Year FE + satellite NOAA HMS smoke-day counts + log_obs (NO ground PM2.5 on RHS
    # because ground PM2.5 is a collider/mediator of T640's optical inflation!!), compare T640 vs FRM/BAM!
    u2_df = my_p[
        (my_p["dv1820_aln"].between(8.5, 11.5))
        & (my_p["Year"].isin([2022, 2023, 2024, 2025]))
        & (my_p["dom_inst"].isin(["T640_FW", "T640_RETRO", "FRM", "BAM"]))
    ].copy()
    u2_df["is_t640_f"] = u2_df["is_t640"].astype(float)
    u2_df["t640_x_hms_h"] = u2_df["is_t640_f"] * u2_df["log_hms_h"]
    u2_x = ["is_t640_f"] + hms_ctrls + ["log_obs"]
    u2_x_int = ["is_t640_f", "t640_x_hms_h"] + hms_ctrls + ["log_obs"]

    u2_2023 = u2_df[u2_df["Year"] == 2023].copy()
    # Restrict to counties having BOTH T640 and non-T640 in the same county-year for County x Year FE!
    cy_var = u2_df.groupby("cnty_yr")["is_t640"].nunique()
    u2_within_cy = u2_df[u2_df["cnty_yr"].isin(cy_var[cy_var >= 2].index)].copy()

    unification_u2: dict[str, Any] = {
        "borderline_2225_state_yr_fe_flag": ols_cr1(
            u2_df["true_ee_flag"].to_numpy(),
            u2_df[u2_x].to_numpy(),
            u2_df["county_fips"].to_numpy(),
            [u2_df["st_yr"].to_numpy()],
            u2_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "borderline_2225_state_yr_fe_unconc": ols_cr1(
            u2_df["unconc_flag"].to_numpy(),
            u2_df[u2_x].to_numpy(),
            u2_df["county_fips"].to_numpy(),
            [u2_df["st_yr"].to_numpy()],
            u2_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "borderline_2225_state_yr_fe_ee_red": ols_cr1(
            u2_df["ee_red_all"].to_numpy(),
            u2_df[u2_x].to_numpy(),
            u2_df["county_fips"].to_numpy(),
            [u2_df["st_yr"].to_numpy()],
            u2_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "borderline_2225_state_yr_fe_ee_red_state_cr1": ols_cr1(
            u2_df["ee_red_all"].to_numpy(),
            u2_df[u2_x].to_numpy(),
            u2_df["state_fips"].to_numpy(),
            [u2_df["st_yr"].to_numpy()],
            u2_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "borderline_2225_t640_x_hms_heavy_flag": ols_cr1(
            u2_df["true_ee_flag"].to_numpy(),
            u2_df[u2_x_int].to_numpy(),
            u2_df["county_fips"].to_numpy(),
            [u2_df["st_yr"].to_numpy()],
            u2_x_int,
            wcb_var_idx=1,
            wcb_B=999,
        ),
        "borderline_2225_t640_x_hms_heavy_flag_state_cr1": ols_cr1(
            u2_df["true_ee_flag"].to_numpy(),
            u2_df[u2_x_int].to_numpy(),
            u2_df["state_fips"].to_numpy(),
            [u2_df["st_yr"].to_numpy()],
            u2_x_int,
            wcb_var_idx=1,
            wcb_B=999,
        ),
        "borderline_2023_peak_state_fe_flag": ols_cr1(
            u2_2023["true_ee_flag"].to_numpy(),
            u2_2023[u2_x].to_numpy(),
            u2_2023["county_fips"].to_numpy(),
            [u2_2023["state_fips"].to_numpy()],
            u2_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "borderline_within_county_year_fe_flag": ols_cr1(
            u2_within_cy["true_ee_flag"].to_numpy(),
            u2_within_cy[["is_t640_f", "log_obs"]].to_numpy(),
            u2_within_cy["county_fips"].to_numpy(),
            [u2_within_cy["cnty_yr"].to_numpy()],
            ["is_t640_f", "log_obs"],
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "borderline_within_county_year_fe_ee_red": ols_cr1(
            u2_within_cy["ee_red_all"].to_numpy(),
            u2_within_cy[["is_t640_f", "log_obs"]].to_numpy(),
            u2_within_cy["county_fips"].to_numpy(),
            [u2_within_cy["cnty_yr"].to_numpy()],
            ["is_t640_f", "log_obs"],
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "raw_rates_borderline_2225": {
            inst_g: {
                "n_mon_yrs": len(g),
                "ee_flag_pct": float(100.0 * g["true_ee_flag"].mean()),
                "unconc_pct": float(100.0 * g["unconc_flag"].mean()),
                "conc_pct": float(100.0 * g["true_ee_conc"].mean()),
                "mean_ee_red": float(g["ee_red_all"].mean()),
                "mean_hms_heavy_days": float(g["hms_heavy_days"].mean()),
            }
            for inst_g, g in u2_df.assign(
                inst_grp=np.where(u2_df["is_t640"] == 1, "T640", u2_df["dom_inst"])
            ).groupby("inst_grp")
        },
    }
    for k in ("borderline_2225_state_yr_fe_flag", "borderline_2225_state_yr_fe_ee_red", "borderline_2225_t640_x_hms_heavy_flag", "borderline_within_county_year_fe_flag"):
        r = unification_u2[k]
        vname = r.get("wcb", {}).get("var", "is_t640_f")
        c = r.get("coefs", {}).get(vname, {})
        print(f"  [U2 {k:38s}] {vname}={c.get('beta',math.nan):+.4f} (t={c.get('t_cr1',math.nan):+.2f}, p={c.get('p_cr1',math.nan):.4f}, p_WCB={r.get('wcb',{}).get('p_wcb',math.nan):.3f})", flush=True)

    # U3: Statutory 40 CFR 50.14 Triage vs Marginal/Non-Heavy Flagging via Satellite NOAA HMS!
    # Fully saturated triple-diff / stratified DiD INCLUDING pre-period nb * has_hms_heavy!
    # (Omitting nb * has_hms_heavy biases tp_hms_no_heavy upward whenever clean Western counties
    #  experienced Heavy smoke in 2018/2020.)
    u3_df = m_85.copy()
    u3_df["post"] = (u3_df["Year"] >= 2022).astype(int)
    u3_df["has_hms_heavy"] = (u3_df["hms_heavy_days"] >= 1).astype(int)
    u3_df["has_hms_any"] = (u3_df["hms_any_days"] >= 1).astype(int)
    u3_df["nb_x_h"] = u3_df["nb"] * u3_df["has_hms_heavy"]
    u3_df["tp_hms_heavy"] = u3_df["nb"] * u3_df["post"] * u3_df["has_hms_heavy"]
    u3_df["tp_hms_no_heavy"] = u3_df["nb"] * u3_df["post"] * (1 - u3_df["has_hms_heavy"])
    u3_df["post_hms_heavy"] = u3_df["post"] * u3_df["has_hms_heavy"]
    u3_x = ["tp_hms_heavy", "tp_hms_no_heavy", "nb_x_h", "has_hms_heavy", "post_hms_heavy"] + hms_ctrls + ["log_obs"]

    u3_post_flags = my_p[(my_p["Year"] >= 2022) & (my_p["true_ee_flag"] == 1)]
    u3_post_unconc = my_p[(my_p["Year"] >= 2022) & (my_p["unconc_flag"] == 1)]
    u3_post_conc = my_p[(my_p["Year"] >= 2022) & (my_p["true_ee_conc"] == 1)]
    unification_u3 = {
        "did_by_hms_stratum_flag": ols_cr1(
            u3_df["true_ee_flag"].to_numpy(),
            u3_df[u3_x].to_numpy(),
            u3_df["county_fips"].to_numpy(),
            [u3_df["canon_id"].to_numpy(), u3_df["st_yr"].to_numpy()],
            u3_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "did_by_hms_stratum_unconc": ols_cr1(
            u3_df["unconc_flag"].to_numpy(),
            u3_df[u3_x].to_numpy(),
            u3_df["county_fips"].to_numpy(),
            [u3_df["canon_id"].to_numpy(), u3_df["st_yr"].to_numpy()],
            u3_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "did_by_hms_stratum_conc": ols_cr1(
            u3_df["true_ee_conc"].to_numpy(),
            u3_df[u3_x].to_numpy(),
            u3_df["county_fips"].to_numpy(),
            [u3_df["canon_id"].to_numpy(), u3_df["st_yr"].to_numpy()],
            u3_x,
            wcb_var_idx=0,
            wcb_B=999,
        ),
        "satellite_hms_backing_2022_2025": {
            "all_ee_flagged_n": len(u3_post_flags),
            "all_ee_pct_with_hms_heavy": float(100.0 * (u3_post_flags["hms_heavy_days"] >= 1).mean()) if len(u3_post_flags) else 0.0,
            "all_ee_pct_with_hms_med_or_heavy": float(100.0 * ((u3_post_flags["hms_heavy_days"] + u3_post_flags["hms_med_days"]) >= 1).mean()) if len(u3_post_flags) else 0.0,
            "all_ee_pct_with_hms_any": float(100.0 * (u3_post_flags["hms_any_days"] >= 1).mean()) if len(u3_post_flags) else 0.0,
            "unconc_n": len(u3_post_unconc),
            "unconc_pct_with_hms_heavy": float(100.0 * (u3_post_unconc["hms_heavy_days"] >= 1).mean()) if len(u3_post_unconc) else 0.0,
            "conc_n": len(u3_post_conc),
            "conc_pct_with_hms_heavy": float(100.0 * (u3_post_conc["hms_heavy_days"] >= 1).mean()) if len(u3_post_conc) else 0.0,
        },
    }
    print(
        "  [U3 HMS Triage Strata on true_ee_flag]:",
        {
            k: (round(unification_u3["did_by_hms_stratum_flag"]["coefs"][k]["beta"], 4), round(unification_u3["did_by_hms_stratum_flag"]["coefs"][k]["t_cr1"], 2))
            for k in ("tp_hms_heavy", "tp_hms_no_heavy")
        },
        flush=True,
    )
    print(f"  [U3 Satellite HMS Backing 2022-25]: {unification_u3['satellite_hms_backing_2022_2025']}", flush=True)
    print("  [Mon-Yr Event Study true_ee_flag (ref=2020)]:", flush=True)
    for y in (2018, 2019, 2021, 2022, 2023, 2024, 2025):
        c = mon_outcomes["true_ee_flag"]["event_study_county_cr1"]["coefs"][f"nb_{y}"]
        cs = mon_outcomes["true_ee_flag"]["event_study_state_cr1"]["coefs"][f"nb_{y}"]
        print(f"    {y}: beta={c['beta']:+.4f} (cnty t={c['t_cr1']:+.2f}, p={c['p_cr1']:.4f} | st t={cs['t_cr1']:+.2f}, p={cs['p_cr1']:.4f})", flush=True)

    receipt = {
        "stitch_merge_audit": {
            "n_reg_monitor_years_in": len(my),
            "n_merged_monitor_years_out": len(my_p),
            "n_dropped_on_merge": int(len(my) - len(my_p)),
        },
        "monitor_year_dv1820_85_115": mon_outcomes,
        "monitor_year_dv1820_85_115_with_hms_ctrls": mon_with_hms,
        "monitor_year_dv1820_90_120": mon_90_12,
        "county_year_dv1820_85_115": cnty_outcomes,
        "county_year_dv1820_85_115_with_hms_ctrls": cnty_with_hms,
        "within_state_ri_B1000": {"monitor_year": ri_mon, "county_year": ri_cnty},
        "loso_monitor_year": loso_summary,
        "robustness_specs_dv1820": rob_specs,
        "inverted_u_profile_dv1820": inverted_u,
        "t640_bailout_substitution_dv1820": bailout_sub,
        "test4_honest_primary_selection": test4_honest,
        "unification_u1_historical_tier1_1822": u1_hist_tier1,
        "unification_u2_t640_ee_flagging": unification_u2,
        "unification_u3_hms_triage_validation": unification_u3,
    }
    sha = save_json_lf(RES_DIR / "03_ee_triage_hms_unification.json", receipt)
    print(f"\n[DONE STEP 03] Saved results/03_ee_triage_hms_unification.json (SHA-256 LF: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
