"""Pillar 5: High-Precision Monthly (m = -12..+12) & Quarterly Investor Flow Event Study.

Uses the fixed abs(REDEMPTION) monthly flows (panel_monthly.parquet) AND cross-validates
against TNA-implied quarterly flows (panel_quarterly.parquet):
1. Monthly Event Study (m = -12 .. +12, reference m = -1) & pooled Post-vs-Pre TWFE:
   - SERIES_ID FE + Month FE (exact LSDV-equivalent DoF & WCB clustered by COMPLEX_ID)
   - Category x Month FE + lagged 3m & 12m return controls + log(TNA_beg)
2. Separate arms for 2025-2026 regulatory droppers:
   - ESG Name-Droppers (testing the positive net-flow rebound, pre-trends, 1%/99% & 2.5%/97.5%
     winsorization, median/quantile robustness, and TNA-implied quarterly cross-validation!)
   - Multi-Asset GVI Name-Droppers (Pooled, OPAQUE_SYNONYM vs NUMERIC_RATIO, Retail vs VA/Insurance)
   - Pure-Equity/Bond GVI Name-Droppers
3. Inflow vs Outflow Mechanism Decomposition:
   - Separately estimates SALES_PCT (gross inflows / TNA), REINVEST_PCT, and REDEMP_ABS_PCT
     (gross redemptions / TNA) to identify whether ESG flow rebound is driven by falling
     outflows/redemptions or rising gross sales!
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from econometrics import run_absorbed_twfe

WORK_DIR = Path(r"D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126")
TABLES_OUT = WORK_DIR / "tables"
RESULTS_OUT = WORK_DIR / "results"


def ym_to_idx(ym: pd.Series | np.ndarray) -> np.ndarray:
    arr = np.asarray(ym, dtype=int)
    return (arr // 100) * 12 + (arr % 100)


def qtr_end_ym(rep_yq: int) -> int:
    yr = rep_yq // 10
    q = rep_yq % 10
    return yr * 100 + q * 3


def winsorize_series(s: pd.Series, lo_q: float = 0.01, hi_q: float = 0.99) -> pd.Series:
    lo, hi = s.quantile([lo_q, hi_q])
    return s.clip(lo, hi)


def run_monthly_arm(
    mon: pd.DataFrame,
    risk_sids: set[str],
    drop_ym_map: dict[str, int],
    arm_name: str,
    do_event_study: bool = True,
) -> tuple[dict, list[dict]]:
    """Run pooled Post-vs-Pre TWFE (exact DoF + WCB), Sales/Redemption decomposition,
    winsorization/median robustness, and m=-12..+12 event study for one risk arm."""
    sub = mon[mon["SERIES_ID"].isin(risk_sids)].copy()
    sub["DROP_YM"] = sub["SERIES_ID"].map(drop_ym_map)
    sub["IS_DROPPER"] = sub["DROP_YM"].notna().astype(int)
    sub["YM_IDX"] = ym_to_idx(sub["YM"])
    drop_idx = np.where(sub["DROP_YM"].notna(), ym_to_idx(sub["DROP_YM"].fillna(202001).astype(int)), np.nan)
    sub["REL_M"] = sub["YM_IDX"] - drop_idx
    sub["POST_DROP"] = ((sub["IS_DROPPER"] == 1) & (sub["REL_M"] >= 0)).astype(float)

    n_drop_funds = int(sub.loc[sub["IS_DROPPER"] == 1, "SERIES_ID"].nunique())
    n_ctrl_funds = int(sub.loc[sub["IS_DROPPER"] == 0, "SERIES_ID"].nunique())

    arm_res: dict = {
        "arm": arm_name,
        "n_droppers": n_drop_funds,
        "n_controls": n_ctrl_funds,
        "pooled_twfe": {},
        "robustness": {},
        "decomposition": {},
    }

    # 1. Baseline & Controlled Pooled TWFE on fixed abs(REDEMPTION) Net Flow (winsorized 1%/99%)
    base_df = sub.dropna(subset=["NET_FLOW_PCT", "LOG_TNA_BEG", "LAG3M_RET_PCT", "LAG12M_RET_PCT"]).copy()
    base_df["NF_W1"] = winsorize_series(base_df["NET_FLOW_PCT"], 0.01, 0.99)
    base_df["NF_W25"] = winsorize_series(base_df["NET_FLOW_PCT"], 0.025, 0.975)
    base_df["NF_RAW_W1"] = winsorize_series(base_df["NET_FLOW_RAW_PCT"], 0.01, 0.99)
    base_df["SALES_W1"] = winsorize_series(base_df["SALES_PCT"], 0.01, 0.99)
    base_df["REINV_W1"] = winsorize_series(base_df["REINVEST_PCT"], 0.01, 0.99)
    base_df["REDEMP_W1"] = winsorize_series(base_df["REDEMP_ABS_PCT"], 0.01, 0.99)
    base_df["LAG3M_W"] = winsorize_series(base_df["LAG3M_RET_PCT"], 0.01, 0.99)
    base_df["LAG12M_W"] = winsorize_series(base_df["LAG12M_RET_PCT"], 0.01, 0.99)

    # Spec A: SERIES_ID FE + Month FE (no return controls)
    r_base = run_absorbed_twfe(
        base_df,
        y_col="NF_W1",
        x_cols=["POST_DROP"],
        absorb_fe_col="SERIES_ID",
        cluster_col="COMPLEX_ID",
        time_fe_col="YM",
        test_col_idx=0,
        n_boot=999,
    )
    # Spec B: SERIES_ID FE + Month FE + Log(TNA_beg) + Lag3m + Lag12m Return (PREFERRED)
    r_ctrl = run_absorbed_twfe(
        base_df,
        y_col="NF_W1",
        x_cols=["POST_DROP", "LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"],
        absorb_fe_col="SERIES_ID",
        cluster_col="COMPLEX_ID",
        time_fe_col="YM",
        test_col_idx=0,
        n_boot=999,
    )
    # Spec C: 2.5%/97.5% Winsorization + controls
    r_w25 = run_absorbed_twfe(
        base_df,
        y_col="NF_W25",
        x_cols=["POST_DROP", "LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"],
        absorb_fe_col="SERIES_ID",
        cluster_col="COMPLEX_ID",
        time_fe_col="YM",
        test_col_idx=0,
        n_boot=999,
    )
    # Spec D: Local window [-12, +12] around rename (plus all never-dropped controls in same calendar months)
    loc_df = base_df[(base_df["IS_DROPPER"] == 0) | ((base_df["REL_M"] >= -12) & (base_df["REL_M"] <= 12))].copy()
    r_loc12 = run_absorbed_twfe(
        loc_df,
        y_col="NF_W1",
        x_cols=["POST_DROP", "LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"],
        absorb_fe_col="SERIES_ID",
        cluster_col="COMPLEX_ID",
        time_fe_col="YM",
        test_col_idx=0,
        n_boot=999,
    )
    # Spec E: Broken RAW signed redemption comparison (to show what happens without sign fix!)
    r_raw_broken = run_absorbed_twfe(
        base_df.dropna(subset=["NF_RAW_W1"]),
        y_col="NF_RAW_W1",
        x_cols=["POST_DROP", "LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"],
        absorb_fe_col="SERIES_ID",
        cluster_col="COMPLEX_ID",
        time_fe_col="YM",
        test_col_idx=0,
        n_boot=999,
    )

    arm_res["pooled_twfe"] = {
        "base_fe_only": r_base,
        "preferred_ret_tna_ctrl": r_ctrl,
        "local_m12_p12_ctrl": r_loc12,
    }
    arm_res["robustness"] = {
        "winsor_25_975_ctrl": r_w25,
        "broken_raw_redemption_ctrl": r_raw_broken,
    }

    # Fund-level before-vs-after median / Wilcoxon signed-rank robustness on droppers (month-FE adjusted!)
    month_med = base_df.groupby("YM")["NF_W1"].transform("median")
    base_df["NF_EX_MED"] = base_df["NF_W1"] - month_med
    d_only = base_df[(base_df["IS_DROPPER"] == 1) & (base_df["REL_M"] >= -12) & (base_df["REL_M"] <= 12)]
    pre_f = d_only[d_only["REL_M"] < 0].groupby("SERIES_ID")["NF_EX_MED"].median()
    post_f = d_only[d_only["REL_M"] >= 0].groupby("SERIES_ID")["NF_EX_MED"].median()
    paired = pd.DataFrame({"pre": pre_f, "post": post_f}).dropna()
    if len(paired) >= 6:
        diff_med = paired["post"] - paired["pre"]
        w_stat, w_p = stats.wilcoxon(diff_med.to_numpy())
        arm_res["robustness"]["paired_fund_median_wilcoxon"] = {
            "n_paired_droppers": len(paired),
            "median_pre_ex_m": float(paired["pre"].median()),
            "median_post_ex_m": float(paired["post"].median()),
            "median_diff_pp_per_mo": float(diff_med.median()),
            "mean_diff_pp_per_mo": float(diff_med.mean()),
            "pct_positive_change": float(100.0 * (diff_med > 0).mean()),
            "wilcoxon_stat": float(w_stat),
            "wilcoxon_p_2sided": float(w_p),
        }

    # 2. Inflow (SALES) vs Reinvestment vs Outflow (|REDEMPTION|) Decomposition
    for comp_name, ycol in [
        ("SALES_PCT", "SALES_W1"),
        ("REINVEST_PCT", "REINV_W1"),
        ("REDEMP_ABS_PCT", "REDEMP_W1"),
    ]:
        cdf = base_df.dropna(subset=[ycol]).copy()
        rc = run_absorbed_twfe(
            cdf,
            y_col=ycol,
            x_cols=["POST_DROP", "LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"],
            absorb_fe_col="SERIES_ID",
            cluster_col="COMPLEX_ID",
            time_fe_col="YM",
            test_col_idx=0,
            n_boot=999,
        )
        arm_res["decomposition"][comp_name] = rc

    # 3. Dynamic Monthly Event Study (m = -12 .. +12, ref m = -1, binned endpoints <= -13 and >= +13)
    es_rows: list[dict] = []
    if do_event_study and n_drop_funds >= 5:
        es_df = base_df.copy()
        rel_vals = list(range(-12, 13))
        es_cols = []
        # Endpoint bins for droppers outside [-12, +12]
        es_df["EV_LE_M13"] = ((es_df["IS_DROPPER"] == 1) & (es_df["REL_M"] <= -13)).astype(float)
        es_df["EV_GE_P13"] = ((es_df["IS_DROPPER"] == 1) & (es_df["REL_M"] >= 13)).astype(float)
        lead_lag_names = []
        for m in rel_vals:
            if m == -1:
                continue
            cname = f"EV_M{abs(m)}" if m < 0 else f"EV_P{m}"
            es_df[cname] = ((es_df["IS_DROPPER"] == 1) & (es_df["REL_M"] == m)).astype(float)
            # Only include event months with at least 3 dropper observations so design matrix is full rank
            if es_df[cname].sum() >= 3:
                es_cols.append(cname)
                lead_lag_names.append((m, cname))

        extra_bins = [c for c in ("EV_LE_M13", "EV_GE_P13") if es_df[c].sum() >= 3]
        x_all = es_cols + extra_bins + ["LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"]

        r_es = run_absorbed_twfe(
            es_df,
            y_col="NF_W1",
            x_cols=x_all,
            absorb_fe_col="SERIES_ID",
            cluster_col="COMPLEX_ID",
            time_fe_col="YM",
            test_col_idx=0,
            do_wcb=False,
            return_cov=True,
        )
        bvec = r_es["beta_vec"]
        V = r_es["V"]
        G_es = r_es["G"]
        n_tr_cl = int(es_df.loc[es_df["IS_DROPPER"] == 1, "COMPLEX_ID"].nunique())

        # Joint pre-trend F-test on m = -12 .. -2 (strictly guarded against treated-cluster rank deficiency!)
        pre_idxs = [idx for idx, (m, _) in enumerate(lead_lag_names) if -12 <= m <= -2]
        post_idxs = [idx for idx, (m, _) in enumerate(lead_lag_names) if 0 <= m <= 12]
        wald_pre_ok = bool(pre_idxs and n_tr_cl > len(pre_idxs))
        wald_post_ok = bool(post_idxs and n_tr_cl > len(post_idxs))
        if wald_pre_ok:
            bp = bvec[pre_idxs]
            Vp = V[np.ix_(pre_idxs, pre_idxs)]
            f_pre = float((bp.T @ np.linalg.inv(Vp) @ bp) / len(pre_idxs))
            p_pre = float(stats.f.sf(f_pre, len(pre_idxs), G_es - 1))
        else:
            f_pre, p_pre = None, None
        if wald_post_ok:
            bo = bvec[post_idxs]
            Vo = V[np.ix_(post_idxs, post_idxs)]
            f_post = float((bo.T @ np.linalg.inv(Vo) @ bo) / len(post_idxs))
            p_post = float(stats.f.sf(f_post, len(post_idxs), G_es - 1))
        else:
            f_post, p_post = None, None

        # Pre-period linear trend slope on m = -12 .. -2 (valid even for small treated-cluster counts via WCB!)
        pre_lin_df = base_df[
            (base_df["IS_DROPPER"] == 0) | ((base_df["REL_M"] >= -12) & (base_df["REL_M"] <= -2))
        ].copy()
        pre_lin_df["PRE_TREND_M"] = np.where(
            pre_lin_df["IS_DROPPER"] == 1, pre_lin_df["REL_M"].fillna(0.0), 0.0
        )
        r_pre_slope = run_absorbed_twfe(
            pre_lin_df,
            y_col="NF_W1",
            x_cols=["PRE_TREND_M", "LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"],
            absorb_fe_col="SERIES_ID",
            cluster_col="COMPLEX_ID",
            time_fe_col="YM",
            test_col_idx=0,
            n_boot=999,
        )

        # Also compute pre-period mean (m = -12..-2) centered path + exact SEs via linear contrast
        # (eliminates single-month April-2025 m=-1 dip distortion while preserving exact ref m=-1!)
        n_pre = len(pre_idxs)
        pre_mean_b = float(np.mean(bvec[pre_idxs])) if n_pre else 0.0
        c_pre = np.zeros(len(bvec), dtype=float)
        if n_pre:
            c_pre[pre_idxs] = 1.0 / n_pre

        arm_res["event_study_summary"] = {
            "G": int(G_es),
            "G_treated_clusters": int(n_tr_cl),
            "N": int(r_es["N"]),
            "rank": int(r_es["rank"]),
            "k": int(r_es["k"]),
            "pre_mean_m12_m2_vs_m1": pre_mean_b,
            "pre_linear_slope_m12_m2": r_pre_slope,
            "wald_pre_rank_valid": wald_pre_ok,
            "joint_pre_m12_m2_F": f_pre,
            "joint_pre_m12_m2_df1": len(pre_idxs),
            "joint_pre_m12_m2_p": p_pre,
            "wald_post_rank_valid": wald_post_ok,
            "joint_post_p0_p12_F": f_post,
            "joint_post_p0_p12_df1": len(post_idxs),
            "joint_post_p0_p12_p": p_post,
        }

        t_crit = float(stats.t.ppf(0.975, df=G_es - 1))
        se_m1_cent = float(np.sqrt(max(float(c_pre @ V @ c_pre), 1e-30))) if n_pre else 0.0
        b_m1_cent = -pre_mean_b
        es_rows.append(
            {
                "arm": arm_name,
                "rel_month": -1,
                "n_dropper_obs": int(((es_df["IS_DROPPER"] == 1) & (es_df["REL_M"] == -1)).sum()),
                "beta_pct": 0.0,
                "se_cr1": 0.0,
                "ci95_lo": 0.0,
                "ci95_hi": 0.0,
                "t_cr1": 0.0,
                "p_cr1": 1.0,
                "beta_centered_pct": b_m1_cent,
                "se_centered_cr1": se_m1_cent,
                "ci95_cent_lo": b_m1_cent - t_crit * se_m1_cent,
                "ci95_cent_hi": b_m1_cent + t_crit * se_m1_cent,
            }
        )
        for idx, (m, cname) in enumerate(lead_lag_names):
            b_i = float(bvec[idx])
            se_i = float(np.sqrt(max(V[idx, idx], 1e-30)))
            t_i = b_i / se_i
            p_i = float(2.0 * stats.t.sf(abs(t_i), df=G_es - 1))
            e_vec = np.zeros(len(bvec), dtype=float)
            e_vec[idx] = 1.0
            diff_c = e_vec - c_pre
            b_cent = b_i - pre_mean_b
            se_cent = float(np.sqrt(max(float(diff_c @ V @ diff_c), 1e-30)))
            es_rows.append(
                {
                    "arm": arm_name,
                    "rel_month": int(m),
                    "n_dropper_obs": int(es_df[cname].sum()),
                    "beta_pct": b_i,
                    "se_cr1": se_i,
                    "ci95_lo": b_i - t_crit * se_i,
                    "ci95_hi": b_i + t_crit * se_i,
                    "t_cr1": t_i,
                    "p_cr1": p_i,
                    "beta_centered_pct": b_cent,
                    "se_centered_cr1": se_cent,
                    "ci95_cent_lo": b_cent - t_crit * se_cent,
                    "ci95_cent_hi": b_cent + t_crit * se_cent,
                }
            )
        es_rows.sort(key=lambda x: x["rel_month"])

    print(
        f"  [{arm_name:24s}] Droppers={n_drop_funds:3d} | Pref Monthly NetFlow={r_ctrl['beta']:+.3f}%/mo "
        f"(t={r_ctrl['t_cr1']:+.2f}, p={r_ctrl['p_cr1']:.4f}, wcb={r_ctrl['p_wcb']:.3f}) | "
        f"Sales={arm_res['decomposition']['SALES_PCT']['beta']:+.3f}%/mo (t={arm_res['decomposition']['SALES_PCT']['t_cr1']:+.2f}) | "
        f"Redemp={arm_res['decomposition']['REDEMP_ABS_PCT']['beta']:+.3f}%/mo (t={arm_res['decomposition']['REDEMP_ABS_PCT']['t_cr1']:+.2f})",
        flush=True,
    )
    return arm_res, es_rows


def main() -> int:
    print("[1/3] Loading monthly & quarterly panels + EDGAR effective dates (if available)...", flush=True)
    mon = pd.read_parquet(WORK_DIR / "data" / "panel_monthly.parquet")
    qtr = pd.read_parquet(WORK_DIR / "data" / "panel_quarterly.parquet")
    audit_df = pd.read_csv(WORK_DIR / "tables" / "table_all_droppers_2025_2026_audit.csv")

    # Use exact EDGAR effective YM when available from Pillar 2, otherwise exact REPORT_DATE month of rename!
    edgar_p = WORK_DIR / "data" / "edgar_prospectus_audit.json"
    edgar_eff_ym: dict[str, int] = {}
    if edgar_p.exists():
        ed_list = json.loads(edgar_p.read_text(encoding="utf-8"))
        for r in ed_list:
            eym = r.get("EFFECTIVE_YM", "")
            if eym and len(eym) == 7:
                try:
                    edgar_eff_ym[r["SERIES_ID"]] = int(eym.replace("-", ""))
                except ValueError:
                    pass
        print(f"  Loaded {len(edgar_eff_ym)} exact EDGAR effective months for event-time alignment.", flush=True)

    # Map each 2025-2026 dropper's exact event month (EDGAR effective YM strictly within [-4, +2] months of REPORT_DATE YM!)
    audit_df["REP_DT"] = pd.to_datetime(audit_df["REPORT_DATE"], format="mixed", errors="coerce")
    audit_df["REP_YM"] = (audit_df["REP_DT"].dt.year * 100 + audit_df["REP_DT"].dt.month).astype(int)

    def _pick_event_ym(sid: str, rym: int) -> int:
        if sid in edgar_eff_ym:
            eym = edgar_eff_ym[sid]
            diff_m = ((eym // 100) * 12 + (eym % 100)) - ((rym // 100) * 12 + (rym % 100))
            if 202411 <= eym <= 202607 and -4 <= diff_m <= 2:
                return eym
        return int(rym)

    audit_df["EVENT_YM"] = [
        _pick_event_ym(sid, int(rym))
        for sid, rym in zip(audit_df["SERIES_ID"], audit_df["REP_YM"], strict=False)
    ]

    # Build exact risk pools from quarterly panel
    esg_risk = set(qtr.loc[qtr["PREV_HAS_ESG"] == 1, "SERIES_ID"])
    ma_gvi_risk = set(qtr.loc[(qtr["PREV_IS_ALLOC_FUND"] == 1) & (qtr["PREV_HAS_GVI"] == 1), "SERIES_ID"])
    pure_gvi_risk = set(qtr.loc[(qtr["PREV_IS_ALLOC_FUND"] == 0) & (qtr["PREV_HAS_GVI"] == 1), "SERIES_ID"])

    esg_drops = audit_df[audit_df["DROP_ESG"] == 1].drop_duplicates("SERIES_ID")
    ma_drops = audit_df[audit_df["DROP_GROUP"] == "MULTI_ASSET_GVI"].drop_duplicates("SERIES_ID")
    ma_opq_drops = ma_drops[ma_drops["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM"]
    ma_num_drops = ma_drops[ma_drops["COMPLIANCE_TYPE"] == "NUMERIC_RATIO"]
    ma_ret_drops = ma_drops[ma_drops["IS_VA_INSURANCE"] == 0]
    ma_va_drops = ma_drops[ma_drops["IS_VA_INSURANCE"] == 1]
    pure_drops = audit_df[audit_df["DROP_GROUP"] == "PURE_EQUITY_OR_BOND_GVI"].drop_duplicates("SERIES_ID")

    print("[2/3] Estimating monthly flow event studies (m=-12..+12) & inflow/outflow decompositions...", flush=True)
    arms_spec = [
        ("ESG_DROPPERS", esg_risk, esg_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict(), True),
        ("MA_GVI_POOLED", ma_gvi_risk, ma_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict(), True),
        ("MA_GVI_OPAQUE", ma_gvi_risk - set(ma_num_drops["SERIES_ID"]), ma_opq_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict(), True),
        ("MA_GVI_NUMERIC", ma_gvi_risk - set(ma_opq_drops["SERIES_ID"]), ma_num_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict(), True),
        ("MA_GVI_RETAIL", set(qtr.loc[(qtr["PREV_IS_ALLOC_FUND"] == 1) & (qtr["PREV_HAS_GVI"] == 1) & (qtr["IS_VA_INSURANCE"] == 0), "SERIES_ID"]), ma_ret_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict(), False),
        ("MA_GVI_VA_INSURANCE", set(qtr.loc[(qtr["PREV_IS_ALLOC_FUND"] == 1) & (qtr["PREV_HAS_GVI"] == 1) & (qtr["IS_VA_INSURANCE"] == 1), "SERIES_ID"]), ma_va_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict(), False),
        ("PURE_GVI_DROPPERS", pure_gvi_risk, pure_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict(), True),
    ]

    monthly_results = {}
    all_es_rows: list[dict] = []
    for arm_name, rset, dmap, do_es in arms_spec:
        ares, erows = run_monthly_arm(mon, rset, dmap, arm_name, do_event_study=do_es)
        monthly_results[arm_name] = ares
        all_es_rows.extend(erows)

    # Pooled Category x Month FE regression combining ESG + Multi-Asset GVI + Pure GVI in ONE joint specification!
    print("\n  [JOINT CATEGORY x MONTH FE] Pooled monthly net-flow test across all 3 arms:", flush=True)
    all_sids = esg_risk | ma_gvi_risk | pure_gvi_risk
    jdf = mon[mon["SERIES_ID"].isin(all_sids)].dropna(subset=["NET_FLOW_PCT", "LOG_TNA_BEG", "LAG3M_RET_PCT", "LAG12M_RET_PCT"]).copy()
    jdf["CAT"] = np.where(jdf["SERIES_ID"].isin(esg_risk), "ESG", np.where(jdf["SERIES_ID"].isin(ma_gvi_risk), "MA_GVI", "PURE_GVI"))
    jdf["CAT_YM"] = jdf["CAT"] + "_" + jdf["YM"].astype(str)
    jdf["YM_IDX"] = ym_to_idx(jdf["YM"])

    esg_map = esg_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict()
    ma_map = ma_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict()
    pure_map = pure_drops.set_index("SERIES_ID")["EVENT_YM"].to_dict()

    jdf["POST_ESG"] = [1.0 if (sid in esg_map and ym >= esg_map[sid]) else 0.0 for sid, ym in zip(jdf["SERIES_ID"], jdf["YM"], strict=False)]
    jdf["POST_MA"] = [1.0 if (sid in ma_map and ym >= ma_map[sid]) else 0.0 for sid, ym in zip(jdf["SERIES_ID"], jdf["YM"], strict=False)]
    jdf["POST_PURE"] = [1.0 if (sid in pure_map and ym >= pure_map[sid]) else 0.0 for sid, ym in zip(jdf["SERIES_ID"], jdf["YM"], strict=False)]
    jdf["NF_W1"] = winsorize_series(jdf["NET_FLOW_PCT"], 0.01, 0.99)
    jdf["LAG3M_W"] = winsorize_series(jdf["LAG3M_RET_PCT"], 0.01, 0.99)
    jdf["LAG12M_W"] = winsorize_series(jdf["LAG12M_RET_PCT"], 0.01, 0.99)

    # Construct full-rank Category x Month dummies (dropping the first month within EACH category,
    # since SERIES_ID FE already spans category main effects -> exact rank(X) == K!).
    cy_dict = {}
    for cat_val in sorted(jdf["CAT"].unique()):
        yms_c = sorted(jdf.loc[jdf["CAT"] == cat_val, "YM"].unique())
        for ym_v in yms_c[1:]:
            cname = f"CY_{cat_val}_{ym_v}"
            cy_dict[cname] = ((jdf["CAT"] == cat_val) & (jdf["YM"] == ym_v)).astype(float).to_numpy()
    cat_ym_cols = list(cy_dict.keys())
    jdf = pd.concat([jdf.reset_index(drop=True), pd.DataFrame(cy_dict)], axis=1)

    joint_cat_ym = {}
    for idx_t, tcol in enumerate(["POST_ESG", "POST_MA", "POST_PURE"]):
        rj = run_absorbed_twfe(
            jdf,
            y_col="NF_W1",
            x_cols=["POST_ESG", "POST_MA", "POST_PURE", "LOG_TNA_BEG", "LAG3M_W", "LAG12M_W"] + cat_ym_cols,
            absorb_fe_col="SERIES_ID",
            cluster_col="COMPLEX_ID",
            time_fe_col=None,
            test_col_idx=idx_t,
            n_boot=999,
        )
        joint_cat_ym[tcol] = rj
        print(f"    {tcol:12s} (Category x Month FE): {rj['beta']:+.3f}%/mo (se={rj['se_cr1']:.3f}, t={rj['t_cr1']:+.2f}, p={rj['p_cr1']:.4f}, wcb={rj['p_wcb']:.3f})", flush=True)

    # -----------------------------------------------------------------------
    # [3/3] Quarterly Flow Cross-Validation: Fixed N-PORT vs TNA-Implied vs Raw Broken
    # -----------------------------------------------------------------------
    print("\n[3/3] Quarterly flow cross-validation (Fixed N-PORT vs TNA-Implied vs Raw Broken)...", flush=True)
    qtr_cv_results = {}
    qtr_cv_rows = []
    for arm_name, rset, d_sub in [
        ("ESG_DROPPERS", esg_risk, esg_drops),
        ("MA_GVI_POOLED", ma_gvi_risk, ma_drops),
        ("MA_GVI_OPAQUE", ma_gvi_risk - set(ma_num_drops["SERIES_ID"]), ma_opq_drops),
        ("MA_GVI_NUMERIC", ma_gvi_risk - set(ma_opq_drops["SERIES_ID"]), ma_num_drops),
        ("PURE_GVI_DROPPERS", pure_gvi_risk, pure_drops),
    ]:
        qsub = qtr[qtr["SERIES_ID"].isin(rset)].copy()
        fdrop_yq = d_sub.set_index("SERIES_ID")["REP_YQ"].to_dict()
        qsub["DROP_YQ"] = qsub["SERIES_ID"].map(fdrop_yq)
        qsub["POST_DROP"] = (qsub["DROP_YQ"].notna() & (qsub["REP_YQ"] >= qsub["DROP_YQ"])).astype(float)

        qtr_cv_results[arm_name] = {}
        for ftype, col in [
            ("NPORT_FIXED_ABS", "QTR_FLOW_FIXED_PCT"),
            ("TNA_IMPLIED", "QTR_FLOW_TNA_PCT"),
            ("NPORT_RAW_BROKEN", "QTR_FLOW_RAW_PCT"),
            ("QTR_SALES_PCT", "QTR_SALES_PCT"),
            ("QTR_REDEMP_ABS_PCT", "QTR_REDEMP_ABS_PCT"),
        ]:
            sv = qsub.dropna(subset=[col, "LOG_LAG_TNA", "LAG_QTR_RET_PCT"]).copy()
            sv["Y_W"] = winsorize_series(sv[col], 0.01, 0.99)
            sv["LAG_R_W"] = winsorize_series(sv["LAG_QTR_RET_PCT"], 0.01, 0.99)
            rq = run_absorbed_twfe(
                sv,
                y_col="Y_W",
                x_cols=["POST_DROP", "LOG_LAG_TNA", "LAG_R_W"],
                absorb_fe_col="SERIES_ID",
                cluster_col="COMPLEX_ID",
                time_fe_col="REP_YQ",
                test_col_idx=0,
                n_boot=999,
            )
            qtr_cv_results[arm_name][ftype] = rq
            qtr_cv_rows.append({"arm": arm_name, "flow_metric": ftype, **rq})
        rf = qtr_cv_results[arm_name]["NPORT_FIXED_ABS"]
        rt = qtr_cv_results[arm_name]["TNA_IMPLIED"]
        rb = qtr_cv_results[arm_name]["NPORT_RAW_BROKEN"]
        print(
            f"  [{arm_name:18s}] Qtr Fixed={rf['beta']:+.2f}%/qtr (t={rf['t_cr1']:+.2f}, wcb={rf['p_wcb']:.3f}) | "
            f"TNA-Implied={rt['beta']:+.2f}%/qtr (t={rt['t_cr1']:+.2f}, wcb={rt['p_wcb']:.3f}) | "
            f"BrokenRaw={rb['beta']:+.2f}%/qtr (t={rb['t_cr1']:+.2f})",
            flush=True,
        )

    pd.DataFrame(all_es_rows).to_csv(TABLES_OUT / "table_monthly_flow_event_study.csv", index=False, lineterminator="\n")
    pd.DataFrame(qtr_cv_rows).to_csv(TABLES_OUT / "table_quarterly_flow_crossval.csv", index=False, lineterminator="\n")

    out = {
        "edgar_effective_dates_used": len(edgar_eff_ym),
        "monthly_arms": monthly_results,
        "joint_category_x_month_fe": joint_cat_ym,
        "quarterly_cross_validation": qtr_cv_results,
    }
    res_p = RESULTS_OUT / "05_monthly_flow_results.json"
    res_p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[DONE PILLAR 5] Saved {res_p.name}, table_monthly_flow_event_study.csv, and table_quarterly_flow_crossval.csv", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
