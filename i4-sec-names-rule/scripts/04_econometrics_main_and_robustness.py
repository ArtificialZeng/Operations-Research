"""Pillar 4: Full-Rank Exact-DoF Econometrics, Bifurcation Decomposition, Mechanism Tests,
Honest Statutory $1B Cutoff (Exact 2-Sided RI & Fisher), ESG Contrast, Placebo & LOFO.

Enforces every econometric invariant strictly:
1. Zero rank-deficiency (`rank(X) == K` asserted in econometrics.py; collinear AGE_Q excluded
   under SERIES_ID FE + REP_YQ FE).
2. Strict iterative non-singleton FE removal and exact CR1 small-sample DoF.
3. Exact LSDV-equivalent Roodman (2019) Rademacher WCB (B=999, seed=20261126).
4. Reports BOTH Complete-Quarter Panel (2020Q1-2026Q2) AND Full-Available Panel (2020Q1-2026Q3).
5. Integrates 100%-fixed 4-Tier Look-Through Holdings (`HOLD_LT_CONSTR`) from Pillar 3.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from econometrics import (
    exact_cluster_ri_did,
    exact_fisher_2sided,
    ols_cr1_wcb,
    run_absorbed_twfe,
)

WORK_DIR = Path(__file__).resolve().parents[1]
TABLES_OUT = WORK_DIR / "tables"
RESULTS_OUT = WORK_DIR / "results"


def strip_cov(d: dict) -> dict:
    return {k: v for k, v in d.items() if k not in ("V", "beta_vec")}


def run_did_with_pretrend(
    sub: pd.DataFrame,
    y_col: str,
    treat_col: str,
    cluster_col: str = "COMPLEX_ID",
    yq_col: str = "REP_YQ",
    n_boot: int = 999,
) -> dict:
    """Standard two-period DiD (Post1: 2023Q4-2024Q4; Post2: 2025Q1+) + linear pre-trend (2020Q1-2023Q2)
    + full dynamic event-study joint 13-quarter pre-trend Wald F-test (2020Q1-2023Q1, ref 2023Q2)."""
    tr = sub[treat_col].to_numpy(dtype=float)
    yq = sub[yq_col].to_numpy(dtype=int)
    p1 = ((yq >= 20234) & (yq <= 20244)).astype(float)
    p2 = (yq >= 20251).astype(float)
    fe_q = pd.get_dummies(sub[yq_col].astype(str), drop_first=True, dtype=float).to_numpy()
    X = np.column_stack([tr * p2, tr * p1, tr, np.ones(len(sub)), fe_q])
    y = sub[y_col].to_numpy(dtype=float)
    cl = sub[cluster_col].to_numpy()
    r_post = ols_cr1_wcb(y, X, cl, test_col_idx=0, n_boot=n_boot)

    # Linear pre-trend (2020Q1-2023Q2)
    mp = yq <= 20232
    sp = sub[mp]
    tyr = (sp[yq_col].to_numpy() // 10 - 2020) + ((sp[yq_col].to_numpy() % 10) - 1) / 4.0
    fe_qp = pd.get_dummies(sp[yq_col].astype(str), drop_first=True, dtype=float).to_numpy()
    Xp = np.column_stack([tr[mp] * tyr, tr[mp], np.ones(len(sp)), fe_qp])
    r_pre_lin = ols_cr1_wcb(y[mp], Xp, cl[mp], test_col_idx=0, n_boot=n_boot)

    # Dynamic event study joint 13-quarter pre-trend F-test (2020Q1-2023Q1, ref 2023Q2)
    all_yqs = sorted(sub[yq_col].unique())
    ref_q = 20232
    qs_use = [q for q in all_yqs if q != ref_q]
    inter_cols = [tr * (yq == q).astype(float) for q in qs_use]
    X_es = np.column_stack(inter_cols + [tr, np.ones(len(sub)), fe_q])
    r_es = ols_cr1_wcb(y, X_es, cl, test_col_idx=0, do_wcb=False, return_cov=True)
    bvec = r_es["beta_vec"]
    V = r_es["V"]
    G = r_es["G"]

    pre_idxs = [i for i, q in enumerate(qs_use) if q <= 20231]
    post_idxs = [i for i, q in enumerate(qs_use) if q >= 20251]
    bp = bvec[pre_idxs]
    Vp = V[np.ix_(pre_idxs, pre_idxs)]
    # Check invertibility cleanly (use solve if full rank, else check exact nonzero pre-variance)
    rank_vp = int(np.linalg.matrix_rank(Vp))
    if rank_vp == len(pre_idxs):
        f_pre = float((bp.T @ np.linalg.inv(Vp) @ bp) / len(pre_idxs))
        df1_pre = len(pre_idxs)
    elif rank_vp > 0:
        f_pre = float((bp.T @ np.linalg.pinv(Vp) @ bp) / rank_vp)
        df1_pre = rank_vp
    else:
        f_pre, df1_pre = 0.0, len(pre_idxs)
    p_pre_f = float(stats.f.sf(f_pre, df1_pre, G - 1)) if rank_vp > 0 else 1.0

    bo = bvec[post_idxs]
    Vo = V[np.ix_(post_idxs, post_idxs)]
    rank_vo = int(np.linalg.matrix_rank(Vo))
    if rank_vo == len(post_idxs):
        f_post = float((bo.T @ np.linalg.inv(Vo) @ bo) / len(post_idxs))
        df1_post = len(post_idxs)
    elif rank_vo > 0:
        f_post = float((bo.T @ np.linalg.pinv(Vo) @ bo) / rank_vo)
        df1_post = rank_vo
    else:
        f_post, df1_post = 0.0, len(post_idxs)
    p_post_f = float(stats.f.sf(f_post, df1_post, G - 1)) if rank_vo > 0 else 1.0

    t_crit = float(stats.t.ppf(0.975, df=G - 1))
    es_q = {
        int(ref_q): {"beta_pp": 0.0, "se_pp": 0.0, "ci95_lo_pp": 0.0, "ci95_hi_pp": 0.0, "t_cr1": 0.0, "p_cr1": 1.0}
    }
    for i, q in enumerate(qs_use):
        bi = float(bvec[i] * 100.0)
        sei = float(np.sqrt(max(V[i, i], 1e-30)) * 100.0)
        ti = bi / sei if sei > 0 else 0.0
        pi = float(2.0 * stats.t.sf(abs(ti), df=G - 1))
        es_q[int(q)] = {
            "beta_pp": bi,
            "se_pp": sei,
            "ci95_lo_pp": bi - t_crit * sei,
            "ci95_hi_pp": bi + t_crit * sei,
            "t_cr1": ti,
            "p_cr1": pi,
        }

    return {
        "post_25_26": r_post,
        "pre_linear_yr": r_pre_lin,
        "joint_pre_F": {"F": f_pre, "df1": int(df1_pre), "df2": int(G - 1), "p": p_pre_f, "rank_V": rank_vp},
        "joint_post_F": {"F": f_post, "df1": int(df1_post), "df2": int(G - 1), "p": p_post_f, "rank_V": rank_vo},
        "event_study_q": es_q,
    }


def run_complex_x_qtr_fe(
    sub: pd.DataFrame,
    y_col: str,
    treat_col: str,
    controls: list[str],
    identifying_only: bool = False,
    n_boot: int = 999,
) -> dict:
    """Exact LSDV-equivalent COMPLEX_ID x REP_YQ FE regression (same complex, same quarter!)."""
    df = sub.dropna(subset=[y_col, treat_col] + controls).copy()
    df["POST2"] = (df["REP_YQ"] >= 20251).astype(float)
    df["POST1"] = ((df["REP_YQ"] >= 20234) & (df["REP_YQ"] <= 20244)).astype(float)
    df["TR_P2"] = df[treat_col] * df["POST2"]
    df["TR_P1"] = df[treat_col] * df["POST1"]
    df["CPLX_YQ"] = df["COMPLEX_ID"] + "_" + df["REP_YQ"].astype(str)

    if identifying_only:
        # Strictly cells that contain BOTH treated (treat==1) AND control (treat==0) funds!
        tr_mean = df.groupby("CPLX_YQ")[treat_col].transform("mean")
        df = df[(tr_mean > 0.0) & (tr_mean < 1.0)].copy()

    return run_absorbed_twfe(
        df,
        y_col=y_col,
        x_cols=["TR_P2", "TR_P1", treat_col] + controls,
        absorb_fe_col="CPLX_YQ",
        cluster_col="COMPLEX_ID",
        time_fe_col=None,
        test_col_idx=0,
        n_boot=n_boot,
    )


def main() -> int:
    print("[1/7] Loading clean REP_YQ quarterly panel & 100%-fixed 4-Tier Look-Through holdings...", flush=True)
    qtr = pd.read_parquet(WORK_DIR / "data" / "panel_quarterly.parquet")
    lt_pair = pd.read_parquet(WORK_DIR / "data" / "holdings_lt" / "lookthrough_panel_2023_2026.parquet")
    audit_df = pd.read_csv(WORK_DIR / "tables" / "table_all_droppers_2025_2026_audit.csv")

    # Join 2023Q2 look-through holdings attributes (strictly predetermined pre-rule!) onto full quarterly panel
    lt_map = lt_pair.set_index("SERIES_ID")[
        ["TRUE_EQ_23", "TRUE_BOND_23", "TRUE_MAX_CLASS_23", "UF_TOT_23", "HOLD_LT_CONSTR", "HOLD_UF_FOF"]
    ]
    qtr = qtr.join(lt_map, on="SERIES_ID")

    # SEC 2025-26 Names Rule FAQ Carve-Out Indicators (strictly excluding "Income" & "Growth and Income" hybrids)
    prev_nm_s = qtr["PREV_SERIES_NAME"].fillna("")
    qtr["PREV_HAS_GI"] = prev_nm_s.str.contains(r"\bgrowth\s*(?:&|and)\s*income\b", case=False, regex=True).astype(int)
    qtr["PREV_HAS_GV_NO_GI"] = ((qtr["PREV_HAS_GV"] == 1) & (qtr["PREV_HAS_GI"] == 0)).astype(int)
    qtr["PREV_HAS_GV_NO_INC"] = ((qtr["PREV_HAS_GV"] == 1) & (qtr["PREV_HAS_INCOME"] == 0)).astype(int)
    qtr["DROP_GV_NO_GI"] = ((qtr["PREV_HAS_GV_NO_GI"] == 1) & (qtr["HAS_GV"] == 0)).astype(int)
    qtr["DROP_GV_NO_INC"] = ((qtr["PREV_HAS_GV_NO_INC"] == 1) & (qtr["HAS_GV"] == 0)).astype(int)
    qtr["DROP_GV_NO_INC_OPAQUE"] = ((qtr["DROP_GV_NO_INC"] == 1) & (qtr["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM")).astype(int)

    # Two sample windows:
    # - FULL_20_26Q3: all available REP_YQ 2020Q1-2026Q3
    # - COMPLETE_20_26Q2: strictly complete calendar quarters 2020Q1-2026Q2 (excludes partial 2026Q3)
    df_full = qtr.copy()
    df_comp = qtr[qtr["IS_COMPLETE_QTR"] == 1].copy()

    results: dict = {}
    table1_rows: list[dict] = []
    table1b_rows: list[dict] = []
    table2_rows: list[dict] = []
    es_export_rows: list[dict] = []

    # -----------------------------------------------------------------------
    # [2/7] Core DiD, Bifurcation, Ex-Vanguard & SEC-FAQ Robustness (BOTH Windows)
    # -----------------------------------------------------------------------
    print("[2/7] Estimating Main DiD, Bifurcation, Ex-Vanguard & SEC-FAQ Robustness...", flush=True)
    core_specs = [
        ("A1_GV_ALL", "PREV_HAS_GV == 1", "PREV_IS_ALLOC_FUND", "DROP_GV"),
        ("A1_GV_OPAQUE_ONLY", "PREV_HAS_GV == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_OPAQUE"),
        ("A1_GV_NUMERIC_ONLY", "PREV_HAS_GV == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NUMERIC"),
        ("A2_GROWTH_ALL", "PREV_HAS_GROWTH == 1", "PREV_IS_ALLOC_FUND", "DROP_GROWTH"),
        ("A3_GVI_ALL", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI"),
        ("A3_GVI_OPAQUE_ONLY", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI_OPAQUE"),
        ("A3_GVI_NUMERIC_ONLY", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI_NUMERIC"),
        ("A3_GVI_EX_VANGUARD", "PREV_HAS_GVI == 1 and COMPLEX_ID != 'VANGUARD'", "PREV_IS_ALLOC_FUND", "DROP_GVI"),
        ("A3_GVI_OPAQUE_EX_VANGUARD", "PREV_HAS_GVI == 1 and COMPLEX_ID != 'VANGUARD'", "PREV_IS_ALLOC_FUND", "DROP_GVI_OPAQUE"),
        ("A3_GVI_NUMERIC_EX_VANGUARD", "PREV_HAS_GVI == 1 and COMPLEX_ID != 'VANGUARD'", "PREV_IS_ALLOC_FUND", "DROP_GVI_NUMERIC"),
        ("FAQ1_GV_NO_GI", "PREV_HAS_GV_NO_GI == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NO_GI"),
        ("FAQ2_GV_NO_INC", "PREV_HAS_GV_NO_INC == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NO_INC"),
        ("FAQ3_GV_NO_INC_OPAQUE", "PREV_HAS_GV_NO_INC == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NO_INC_OPAQUE"),
        ("FAQ4_GV_NO_INC_HOLD_LT80", "PREV_HAS_GV_NO_INC == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GV_NO_INC"),
        ("A4_WITHIN_ALLOC_GVI_VS_EXEMPT", "PREV_IS_ALLOC_FUND == 1", "PREV_HAS_GVI", "ANY_RENAME"),
        ("S1_NCEN_FOF_TD_GV", "PREV_HAS_GV == 1", "PREV_STRUCT_FOF_TD", "DROP_GV"),
        ("S2_NCEN_FOF_TD_GVI", "PREV_HAS_GVI == 1", "PREV_STRUCT_FOF_TD", "DROP_GVI"),
        ("LT1_HOLD_LT80_GV", "PREV_HAS_GV == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GV"),
        ("LT2_HOLD_LT80_GVI", "PREV_HAS_GVI == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GVI"),
        ("LT3_HOLD_LT80_GVI_OPAQUE", "PREV_HAS_GVI == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GVI_OPAQUE"),
    ]

    results["main_did_full_20_26Q3"] = {}
    results["main_did_complete_20_26Q2"] = {}

    for win_key, win_df in [("main_did_full_20_26Q3", df_full), ("main_did_complete_20_26Q2", df_comp)]:
        print(f"\n  --- Window: {win_key} ---", flush=True)
        for tag, qry, tr_col, y_col in core_specs:
            sub = win_df.query(qry).copy()
            r = run_did_with_pretrend(sub, y_col=y_col, treat_col=tr_col, n_boot=999)
            results[win_key][tag] = {
                "post_25_26": r["post_25_26"],
                "pre_linear_yr": r["pre_linear_yr"],
                "joint_pre_F": r["joint_pre_F"],
                "joint_post_F": r["joint_post_F"],
            }
            p = r["post_25_26"]
            jf = r["joint_pre_F"]
            table1_rows.append(
                {
                    "window": win_key,
                    "spec": tag,
                    "N": p["N"],
                    "G": p["G"],
                    "rank": p["rank"],
                    "k": p["k"],
                    "beta_pp": p["beta"] * 100.0,
                    "se_pp": p["se_cr1"] * 100.0,
                    "t_cr1": p["t_cr1"],
                    "p_cr1": p["p_cr1"],
                    "p_wcb": p["p_wcb"],
                    "pre_lin_p": r["pre_linear_yr"]["p_cr1"],
                    "joint_pre_F": jf["F"],
                    "joint_pre_p": jf["p"],
                }
            )
            print(
                f"    {tag:30s} | N={p['N']:6d} G={p['G']:3d} rk={p['rank']}/{p['k']} | "
                f"b={p['beta'] * 100:+5.2f}pp (se={p['se_cr1'] * 100:4.2f}, t={p['t_cr1']:+5.2f}, wcb={p['p_wcb']:.3f}) | "
                f"PreLin p={r['pre_linear_yr']['p_cr1']:.3f} | JointPre F={jf['F']:.2f} (p={jf['p']:.3f})",
                flush=True,
            )
            if win_key == "main_did_full_20_26Q3" and tag in (
                "A1_GV_ALL",
                "A3_GVI_ALL",
                "A3_GVI_OPAQUE_ONLY",
                "A3_GVI_NUMERIC_ONLY",
                "LT2_HOLD_LT80_GVI",
            ):
                for q_i, q_d in sorted(r["event_study_q"].items()):
                    es_export_rows.append({"spec": tag, "REP_YQ": q_i, **q_d})

    # Also compute raw quarterly hazard time series (Multi-Asset GVI Opaque vs Numeric vs Pure-Equity GVI vs Legacy-2001)
    q_hazards = []
    for yq_val, grp in df_full.groupby("REP_YQ"):
        ma_gvi = grp[(grp["PREV_IS_ALLOC_FUND"] == 1) & (grp["PREV_HAS_GVI"] == 1)]
        pe_gvi = grp[(grp["PREV_IS_ALLOC_FUND"] == 0) & (grp["PREV_HAS_GVI"] == 1)]
        esg_g = grp[grp["PREV_HAS_ESG"] == 1]
        leg_g = grp[(grp["PREV_HAS_LEGACY"] == 1) & (grp["PREV_HAS_GVI"] == 0) & (grp["PREV_HAS_ESG"] == 0)]
        q_hazards.append(
            {
                "REP_YQ": int(yq_val),
                "is_complete_qtr": int(yq_val <= 20262),
                "n_ma_gvi": len(ma_gvi),
                "ma_gvi_drop_pct": float(100.0 * ma_gvi["DROP_GVI"].mean()) if len(ma_gvi) else 0.0,
                "ma_gvi_opaque_pct": float(100.0 * ma_gvi["DROP_GVI_OPAQUE"].mean()) if len(ma_gvi) else 0.0,
                "ma_gvi_numeric_pct": float(100.0 * ma_gvi["DROP_GVI_NUMERIC"].mean()) if len(ma_gvi) else 0.0,
                "ma_gvi_other_pct": float(100.0 * ma_gvi["DROP_GVI_OTHER"].mean()) if len(ma_gvi) else 0.0,
                "pe_gvi_drop_pct": float(100.0 * pe_gvi["DROP_GVI"].mean()) if len(pe_gvi) else 0.0,
                "esg_drop_pct": float(100.0 * esg_g["DROP_ESG"].mean()) if len(esg_g) else 0.0,
                "legacy_drop_pct": float(100.0 * leg_g["DROP_LEGACY"].mean()) if len(leg_g) else 0.0,
            }
        )
    results["quarterly_hazards_rep_yq"] = q_hazards

    # 2023Q2 Pure Look-Through 80% Kink Bins (ZERO name keywords!)
    gvi_lt = df_full[(df_full["PREV_HAS_GVI"] == 1) & df_full["TRUE_MAX_CLASS_23"].notna()].copy()
    bins_m = [-1, 60, 80, 90, 200]
    lbls_m = ["<60% (Heavy Multi-Asset)", "60%-80% (Mixed <80% Rule)", "80%-90% (Slack >=80%)", ">=90% (Pure Single-Class)"]
    gvi_lt["LT_BIN"] = pd.cut(gvi_lt["TRUE_MAX_CLASS_23"], bins=bins_m, labels=lbls_m, right=False)
    kink_bins = {}
    for b in lbls_m:
        sb = gvi_lt[gvi_lt["LT_BIN"] == b]
        sp = sb[sb["REP_YQ"] <= 20232]
        so = sb[sb["REP_YQ"] >= 20251]
        kink_bins[b] = {
            "n_funds": int(sb["SERIES_ID"].nunique()),
            "pre_drops": int(sp["DROP_GVI"].sum()),
            "pre_N": len(sp),
            "pre_pct": float(100.0 * sp["DROP_GVI"].mean()) if len(sp) else 0.0,
            "post_drops": int(so["DROP_GVI"].sum()),
            "post_N": len(so),
            "post_pct": float(100.0 * so["DROP_GVI"].mean()) if len(so) else 0.0,
        }
    results["lookthrough_80pct_kink_bins_gvi"] = kink_bins

    # -----------------------------------------------------------------------
    # [3/7] High-Dimensional FE: SERIES_ID FE + REP_YQ FE (NO collinear AGE_Q!) & COMPLEX_ID x REP_YQ FE
    # -----------------------------------------------------------------------
    print("\n[3/7] High-Dimensional FE (SERIES_ID FE + REP_YQ FE; COMPLEX_ID x REP_YQ FE full & identifying-only)...", flush=True)
    hd_fe = {}
    ctrls = ["LOG_LAG_TNA", "LAG_QTR_RET_PCT"]
    for win_tag, win_df in [("FULL_20_26Q3", df_full), ("COMP_20_26Q2", df_comp)]:
        for spec_name, mask_expr, tr_col, y_col in [
            ("GV_ALLOC", "PREV_HAS_GV == 1", "PREV_IS_ALLOC_FUND", "DROP_GV"),
            ("GV_NO_INC_ALLOC", "PREV_HAS_GV_NO_INC == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NO_INC"),
            ("GVI_ALLOC", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI"),
            ("GVI_OPAQUE", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI_OPAQUE"),
            ("GVI_HOLD_LT80", "PREV_HAS_GVI == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GVI"),
            ("GV_HOLD_LT80", "PREV_HAS_GV == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GV"),
        ]:
            sub = win_df.query(mask_expr).dropna(subset=ctrls).copy()
            # 1) SERIES_ID FE + REP_YQ FE + Controls (no collinear AGE_Q!)
            sub["POST2"] = (sub["REP_YQ"] >= 20251).astype(float)
            sub["POST1"] = ((sub["REP_YQ"] >= 20234) & (sub["REP_YQ"] <= 20244)).astype(float)
            sub["TR_P2"] = sub[tr_col] * sub["POST2"]
            sub["TR_P1"] = sub[tr_col] * sub["POST1"]
            if win_tag == "FULL_20_26Q3" or spec_name in ("GVI_ALLOC", "GVI_OPAQUE", "GVI_HOLD_LT80"):
                r_sid = run_absorbed_twfe(
                    sub,
                    y_col=y_col,
                    x_cols=["TR_P2", "TR_P1"] + ctrls,
                    absorb_fe_col="SERIES_ID",
                    cluster_col="COMPLEX_ID",
                    time_fe_col="REP_YQ",
                    test_col_idx=0,
                    n_boot=999,
                )
                r_cq_all = run_complex_x_qtr_fe(sub, y_col=y_col, treat_col=tr_col, controls=ctrls, identifying_only=False)
                r_cq_id = run_complex_x_qtr_fe(sub, y_col=y_col, treat_col=tr_col, controls=ctrls, identifying_only=True)
                key_base = f"{win_tag}_{spec_name}"
                hd_fe[f"{key_base}_SERIES_FE"] = r_sid
                hd_fe[f"{key_base}_COMPLEX_X_QTR_ALL"] = r_cq_all
                hd_fe[f"{key_base}_COMPLEX_X_QTR_IDENTIFYING"] = r_cq_id
                print(
                    f"  {key_base:28s} | SeriesFE={r_sid['beta'] * 100:+5.2f}pp (t={r_sid['t_cr1']:+5.2f}, wcb={r_sid['p_wcb']:.3f}) | "
                    f"Cplx×Qtr(All)={r_cq_all['beta'] * 100:+5.2f}pp (t={r_cq_all['t_cr1']:+5.2f}, wcb={r_cq_all['p_wcb']:.3f}) | "
                    f"Cplx×Qtr(IdOnly N={r_cq_id['N']:,}, G={r_cq_id['G']})={r_cq_id['beta'] * 100:+5.2f}pp (t={r_cq_id['t_cr1']:+5.2f}, wcb={r_cq_id['p_wcb']:.3f})",
                    flush=True,
                )
                if win_tag == "FULL_20_26Q3":
                    for sub_k, r_obj in [
                        (f"FE_{spec_name}_SERIES_FE", r_sid),
                        (f"FE_{spec_name}_CPLX_QTR_ALL", r_cq_all),
                        (f"FE_{spec_name}_CPLX_QTR_IDONLY", r_cq_id),
                    ]:
                        table1b_rows.append(
                            {
                                "window": "main_did_full_20_26Q3",
                                "spec": sub_k,
                                "N": r_obj["N"],
                                "G": r_obj["G"],
                                "rank": r_obj["rank"],
                                "k": r_obj["k"],
                                "n_fe_absorbed": r_obj["n_fe_absorbed"],
                                "n_singletons_dropped": r_obj["n_singletons_dropped"],
                                "beta_pp": r_obj["beta"] * 100.0,
                                "se_pp": r_obj["se_cr1"] * 100.0,
                                "t_cr1": r_obj["t_cr1"],
                                "p_cr1": r_obj["p_cr1"],
                                "p_wcb": r_obj["p_wcb"],
                            }
                        )
    results["high_dim_fe"] = hd_fe

    # -----------------------------------------------------------------------
    # [4/7] Mechanism Analysis: Predicting OPAQUE_SYNONYM vs NUMERIC_RATIO Choice!
    # -----------------------------------------------------------------------
    print("\n[4/7] Cross-Sectional Mechanism Table: Determinants of Opaque Synonym vs Numeric Ratio...", flush=True)
    # Merge N-CEN expense ratio & pre-rule complex AUM onto all Multi-Asset GVI droppers (excluding 1 residual brand drop)
    meta_s = (
        df_full.sort_values(["SERIES_ID", "REP_YQ"])
        .drop_duplicates("SERIES_ID", keep="last")[
            ["SERIES_ID", "EXP_PRE_NCEN", "MGMT_FEE_PRE_NCEN", "COMPLEX_TNA_23Q2"]
        ]
    )
    ma_d = audit_df[
        (audit_df["DROP_GROUP"] == "MULTI_ASSET_GVI")
        & (audit_df["COMPLIANCE_TYPE"].isin(["OPAQUE_SYNONYM", "NUMERIC_RATIO"]))
    ].drop_duplicates("SERIES_ID").merge(meta_s, on="SERIES_ID", how="left")
    ma_d["IS_NUMERIC"] = (ma_d["COMPLIANCE_TYPE"] == "NUMERIC_RATIO").astype(float)
    ma_d["IS_OPAQUE"] = (ma_d["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM").astype(float)
    # Index OR Low-Fee Index-FOF (formal N-CEN IS_INDEX/IS_ETF + explicit passive index-FOF check)
    ma_d["IS_INDEX_OR_ETF"] = ((ma_d["IS_INDEX"] == 1) | (ma_d["IS_ETF"] == 1)).astype(float)
    ma_d["IS_PASSIVE_OR_IDX_FOF"] = (
        (ma_d["IS_INDEX_OR_ETF"] == 1) | ((ma_d["COMPLEX_ID"] == "VANGUARD") & (ma_d["IS_FOF"] == 1))
    ).astype(float)
    ma_d["LOG_FUND_AUM"] = np.log((ma_d["AUM_M"].clip(lower=1.0)) * 1e6)
    ma_d["LOG_COMPLEX_AUM"] = np.log(ma_d["COMPLEX_TNA_23Q2"].fillna(1e9).clip(lower=1e6))

    mech_out: dict = {
        "n_ma_gvi_bifurcated_droppers": len(ma_d),
        "bivariate_means_and_fisher": {},
        "lpm_regs": {},
        "full_ma_sample_lpm": {},
        "logit_check": {},
    }
    mech_csv_rows: list[dict] = []

    # Exact group means & Fisher exact tests on binary channels
    for col in ["IS_INDEX", "IS_ETF", "IS_INDEX_OR_ETF", "IS_PASSIVE_OR_IDX_FOF", "IS_VA_INSURANCE", "IS_FOF"]:
        opq = ma_d[ma_d["IS_OPAQUE"] == 1][col]
        num = ma_d[ma_d["IS_NUMERIC"] == 1][col]
        f_res = exact_fisher_2sided(
            int((num == 1).sum()),
            int((num == 0).sum()),
            int((opq == 1).sum()),
            int((opq == 0).sum()),
        )
        mech_out["bivariate_means_and_fisher"][col] = {
            "mean_opaque_pct": float(100.0 * opq.mean()),
            "mean_numeric_pct": float(100.0 * num.mean()),
            "fisher_p_2sided": f_res["p_2sided"],
            "table": f_res["table"],
        }
        print(
            f"  Channel {col:22s}: Opaque={100.0 * opq.mean():5.1f}% vs Numeric={100.0 * num.mean():5.1f}% (Fisher 2-sided p={f_res['p_2sided']:.4f})",
            flush=True,
        )

    for col in ["AUM_M", "LOG_FUND_AUM", "LOG_COMPLEX_AUM"]:
        opq_v = ma_d.loc[ma_d["IS_OPAQUE"] == 1, col].dropna()
        num_v = ma_d.loc[ma_d["IS_NUMERIC"] == 1, col].dropna()
        _u_stat, u_p = stats.mannwhitneyu(num_v, opq_v, alternative="two-sided")
        mech_out["bivariate_means_and_fisher"][col] = {
            "n_opaque": len(opq_v),
            "n_numeric": len(num_v),
            "mean_opaque": float(opq_v.mean()),
            "median_opaque": float(opq_v.median()),
            "mean_numeric": float(num_v.mean()),
            "median_numeric": float(num_v.median()),
            "mannwhitney_p_2sided": float(u_p),
        }
        print(
            f"  Continuous {col:14s}: Opaque med={opq_v.median():.3f} (mean={opq_v.mean():.3f}) vs "
            f"Numeric med={num_v.median():.3f} (mean={num_v.mean():.3f}) | MW p={u_p:.4f}",
            flush=True,
        )

    # Multivariate LPM (CR1 clustered by COMPLEX_ID) predicting IS_NUMERIC (Transparency-Enhancing) on Droppers
    lpm_cols = ["IS_INDEX_OR_ETF", "IS_VA_INSURANCE", "LOG_FUND_AUM", "LOG_COMPLEX_AUM", "IS_FOF"]
    X_m = np.column_stack([ma_d[c].to_numpy(dtype=float) for c in lpm_cols] + [np.ones(len(ma_d))])
    y_m = ma_d["IS_NUMERIC"].to_numpy(dtype=float)
    cl_m = ma_d["COMPLEX_ID"].to_numpy()
    for idx_c, cname in enumerate(lpm_cols):
        r_c = ols_cr1_wcb(y_m, X_m, cl_m, test_col_idx=idx_c, n_boot=999)
        mech_out["lpm_regs"][cname] = r_c
        mech_csv_rows.append({"sample": "MA_GVI_DROPPERS_49", "outcome": "IS_NUMERIC", "predictor": cname, **r_c})
        print(f"  LPM(IS_NUMERIC|Drop) {cname:16s}: beta={r_c['beta']:+.4f} (se={r_c['se_cr1']:.4f}, t={r_c['t_cr1']:+.2f}, wcb={r_c['p_wcb']:.3f})", flush=True)

    # Full Multi-Asset GVI Sample Cross-Sectional Mechanism Regressions (all unique 2025-2026 at-risk MA GVI funds!)
    ma_all_pool = (
        df_full[(df_full["REP_YQ"] >= 20251) & (df_full["PREV_IS_ALLOC_FUND"] == 1) & (df_full["PREV_HAS_GVI"] == 1)]
        .sort_values(["SERIES_ID", "REP_YQ"])
        .groupby("SERIES_ID", as_index=False)
        .agg(
            COMPLEX_ID=("COMPLEX_ID", "first"),
            IS_INDEX=("IS_INDEX", "max"),
            IS_ETF=("IS_ETF", "max"),
            IS_VA_INSURANCE=("IS_VA_INSURANCE", "max"),
            IS_FOF=("IS_FOF", "max"),
            FUND_AUM=("PREV_NET_ASSETS", "first"),
            COMPLEX_TNA_23Q2=("COMPLEX_TNA_23Q2", "first"),
            EVER_DROP_GVI=("DROP_GVI", "max"),
            EVER_DROP_OPAQUE=("DROP_GVI_OPAQUE", "max"),
            EVER_DROP_NUMERIC=("DROP_GVI_NUMERIC", "max"),
        )
    )
    ma_all_pool = ma_all_pool.dropna(subset=["FUND_AUM", "COMPLEX_TNA_23Q2"]).copy()
    ma_all_pool["IS_INDEX_OR_ETF"] = ((ma_all_pool["IS_INDEX"] == 1) | (ma_all_pool["IS_ETF"] == 1)).astype(float)
    ma_all_pool["LOG_FUND_AUM"] = np.log(ma_all_pool["FUND_AUM"].clip(lower=1e6))
    ma_all_pool["LOG_COMPLEX_AUM"] = np.log(ma_all_pool["COMPLEX_TNA_23Q2"].clip(lower=1e6))
    X_full_m = np.column_stack([ma_all_pool[c].to_numpy(dtype=float) for c in lpm_cols] + [np.ones(len(ma_all_pool))])
    cl_full_m = ma_all_pool["COMPLEX_ID"].to_numpy()
    mech_out["n_full_ma_gvi_sample"] = len(ma_all_pool)
    for y_out_col in ["EVER_DROP_GVI", "EVER_DROP_OPAQUE", "EVER_DROP_NUMERIC"]:
        y_fm = ma_all_pool[y_out_col].to_numpy(dtype=float)
        mech_out["full_ma_sample_lpm"][y_out_col] = {}
        for idx_c, cname in enumerate(lpm_cols):
            r_fm = ols_cr1_wcb(y_fm, X_full_m, cl_full_m, test_col_idx=idx_c, n_boot=999)
            mech_out["full_ma_sample_lpm"][y_out_col][cname] = r_fm
            mech_csv_rows.append({"sample": "FULL_MA_GVI_SAMPLE", "outcome": y_out_col, "predictor": cname, **r_fm})
        print(
            f"  Full MA Sample ({len(ma_all_pool)} funds, G={ma_all_pool['COMPLEX_ID'].nunique()}) {y_out_col:18s}: "
            f"VA={mech_out['full_ma_sample_lpm'][y_out_col]['IS_VA_INSURANCE']['beta']:+.3f} "
            f"(wcb={mech_out['full_ma_sample_lpm'][y_out_col]['IS_VA_INSURANCE']['p_wcb']:.3f}) | "
            f"logCplx={mech_out['full_ma_sample_lpm'][y_out_col]['LOG_COMPLEX_AUM']['beta']:+.3f} "
            f"(wcb={mech_out['full_ma_sample_lpm'][y_out_col]['LOG_COMPLEX_AUM']['p_wcb']:.3f}) | "
            f"FOF={mech_out['full_ma_sample_lpm'][y_out_col]['IS_FOF']['beta']:+.3f} "
            f"(wcb={mech_out['full_ma_sample_lpm'][y_out_col]['IS_FOF']['p_wcb']:.3f})",
            flush=True,
        )

    # Parsimonious Logit (using continuous size + VA indicator to avoid perfect separation on Index/ETF=100%!)
    try:
        logit_df = ma_d.dropna(subset=["LOG_FUND_AUM", "LOG_COMPLEX_AUM", "IS_VA_INSURANCE"]).copy()
        X_lg = sm.add_constant(logit_df[["LOG_FUND_AUM", "LOG_COMPLEX_AUM", "IS_VA_INSURANCE"]])
        lg_fit = sm.Logit(logit_df["IS_NUMERIC"], X_lg).fit(disp=False)
        mech_out["logit_check"] = {
            "converged": bool(lg_fit.mle_retvals.get("converged", True)),
            "pseudo_r2": float(lg_fit.prsquared),
            "params": {k: float(v) for k, v in lg_fit.params.items()},
            "pvalues": {k: float(v) for k, v in lg_fit.pvalues.items()},
        }
    except (ValueError, np.linalg.LinAlgError) as e:
        mech_out["logit_check"] = {"error": str(e)}

    results["mechanism_opaque_vs_numeric"] = mech_out
    pd.DataFrame(mech_csv_rows).to_csv(TABLES_OUT / "table2b_mechanism_bifurcation.csv", index=False, lineterminator="\n")

    # -----------------------------------------------------------------------
    # [5/7] Honest Statutory $1B Size Cutoff, Step-Function ($1B vs $10B), Saturated DDD & Exact RI/Fisher!
    # -----------------------------------------------------------------------
    print("\n[5/7] Statutory $1B Cutoff, Size-Bin Step Function ($1B vs $10B), Saturated DDD & Exact 2-Sided RI/Fisher...", flush=True)
    # Strictly restrict to complexes active in 2024+ (dropping pre-2024 exits cleanly!)
    active_df = df_full[df_full["COMPLEX_ACTIVE_2024PLUS"] == 1].copy()

    # Step-function bins for Multi-Asset GVI AND Political ESG
    bins_sz = [0, 1e9, 10e9, 100e9, 1e15]
    lbls_sz = ["<$1B (Exempt in 26Q3)", "$1B-$10B (Binding Jun26)", "$10B-$100B (Binding Jun26)", ">=$100B (Binding Jun26)"]
    step_out = {}
    for arm_lbl, mask_arm, dcol in [
        ("MULTI_ASSET_GVI", (active_df["PREV_IS_ALLOC_FUND"] == 1) & (active_df["PREV_HAS_GVI"] == 1), "DROP_GVI"),
        ("ESG", active_df["PREV_HAS_ESG"] == 1, "DROP_ESG"),
        ("LEGACY_2001_PLACEBO", (active_df["PREV_HAS_LEGACY"] == 1) & (active_df["PREV_HAS_GVI"] == 0) & (active_df["PREV_HAS_ESG"] == 0), "DROP_LEGACY"),
    ]:
        sub_b = active_df[mask_arm & active_df["COMPLEX_TNA_23Q2"].notna()].copy()
        sub_b["SZ_BIN"] = pd.cut(sub_b["COMPLEX_TNA_23Q2"], bins=bins_sz, labels=lbls_sz, right=False)
        step_out[arm_lbl] = {}
        print(f"\n  [STEP-FUNCTION {arm_lbl} by Pre-Rule 2023Q2 Complex AUM (Active 2024+ Complexes)]:", flush=True)
        for b in lbls_sz:
            sb = sub_b[sub_b["SZ_BIN"] == b]
            sp = sb[sb["REP_YQ"] <= 20232]
            so = sb[sb["REP_YQ"] >= 20251]
            n_cplx_post = int(so["COMPLEX_ID"].nunique())
            n_cplx_drop_post = int(so.loc[so[dcol] == 1, "COMPLEX_ID"].nunique())
            rec = {
                "n_complexes_all": int(sb["COMPLEX_ID"].nunique()),
                "n_complexes_post": n_cplx_post,
                "n_complexes_dropping_post": n_cplx_drop_post,
                "pre_drops": int(sp[dcol].sum()),
                "pre_N": len(sp),
                "pre_pct": float(100.0 * sp[dcol].mean()) if len(sp) else 0.0,
                "post_drops": int(so[dcol].sum()),
                "post_N": len(so),
                "post_pct": float(100.0 * so[dcol].mean()) if len(so) else 0.0,
            }
            step_out[arm_lbl][b] = rec
            print(
                f"    {b:28s} | Cplx(Post)={n_cplx_post:3d} (DropCplx={n_cplx_drop_post:2d}) | "
                f"Pre={rec['pre_drops']:2d}/{rec['pre_N']:5d} ({rec['pre_pct']:.2f}%) -> "
                f"Post={rec['post_drops']:2d}/{rec['post_N']:5d} ({rec['post_pct']:.2f}%)",
                flush=True,
            )
    results["statutory_size_step_function"] = step_out

    # Direct $1B Cutoff DiD + Exact 2-Sided Complex-Clustered RI (B=2000) + Exact 2-Sided Fisher Test
    cutoff_tests = {}
    for arm_lbl, mask_arm, dcol in [
        ("B1_ALLOC_GVI_LARGE_VS_SMALL", (active_df["PREV_IS_ALLOC_FUND"] == 1) & (active_df["PREV_HAS_GVI"] == 1), "DROP_GVI"),
        ("B1_LOCAL_1B_10B_VS_LT1B", (active_df["PREV_IS_ALLOC_FUND"] == 1) & (active_df["PREV_HAS_GVI"] == 1) & (active_df["COMPLEX_TNA_23Q2"] < 10e9), "DROP_GVI"),
        ("B2_ALLOC_GVI_COMPLETE_26Q2", (active_df["IS_COMPLETE_QTR"] == 1) & (active_df["PREV_IS_ALLOC_FUND"] == 1) & (active_df["PREV_HAS_GVI"] == 1), "DROP_GVI"),
        ("B3_ESG_LARGE_VS_SMALL", active_df["PREV_HAS_ESG"] == 1, "DROP_ESG"),
        ("B4_LEGACY_2001_PLACEBO", (active_df["PREV_HAS_LEGACY"] == 1) & (active_df["PREV_HAS_GVI"] == 0) & (active_df["PREV_HAS_ESG"] == 0), "DROP_LEGACY"),
        ("B4_LOCAL_1B_10B_VS_LT1B", (active_df["PREV_HAS_LEGACY"] == 1) & (active_df["PREV_HAS_GVI"] == 0) & (active_df["PREV_HAS_ESG"] == 0) & (active_df["COMPLEX_TNA_23Q2"] < 10e9), "DROP_LEGACY"),
    ]:
        sub_c = active_df[mask_arm & active_df["LARGE_COMPLEX_23Q2"].notna()].copy()
        r_did = run_did_with_pretrend(sub_c, y_col=dcol, treat_col="LARGE_COMPLEX_23Q2", n_boot=999)

        # Exact Complex-Clustered Randomization Inference (B=2000)
        sub_c["POST2"] = (sub_c["REP_YQ"] >= 20251).astype(float)
        sub_c["POST1"] = ((sub_c["REP_YQ"] >= 20234) & (sub_c["REP_YQ"] <= 20244)).astype(float)
        ri_res = exact_cluster_ri_did(
            sub_c,
            y_col=dcol,
            treat_col="LARGE_COMPLEX_23Q2",
            post2_col="POST2",
            post1_col="POST1",
            time_col="REP_YQ",
            cluster_col="COMPLEX_ID",
            n_perm=2000,
            seed=20261126,
        )

        # Exact 2-sided Fisher tests in Post (2025Q1-2026Q3): (a) complex-level, (b) fund-quarter level
        post_c = sub_c[sub_c["REP_YQ"] >= 20251]
        cl_post = post_c.groupby("COMPLEX_ID").agg(
            large=("LARGE_COMPLEX_23Q2", "first"),
            dropped=(dcol, "max"),
        )
        fisher_cplx = exact_fisher_2sided(
            int(((cl_post["large"] == 1) & (cl_post["dropped"] == 1)).sum()),
            int(((cl_post["large"] == 1) & (cl_post["dropped"] == 0)).sum()),
            int(((cl_post["large"] == 0) & (cl_post["dropped"] == 1)).sum()),
            int(((cl_post["large"] == 0) & (cl_post["dropped"] == 0)).sum()),
        )
        fisher_fq = exact_fisher_2sided(
            int(((post_c["LARGE_COMPLEX_23Q2"] == 1) & (post_c[dcol] == 1)).sum()),
            int(((post_c["LARGE_COMPLEX_23Q2"] == 1) & (post_c[dcol] == 0)).sum()),
            int(((post_c["LARGE_COMPLEX_23Q2"] == 0) & (post_c[dcol] == 1)).sum()),
            int(((post_c["LARGE_COMPLEX_23Q2"] == 0) & (post_c[dcol] == 0)).sum()),
        )

        cutoff_tests[arm_lbl] = {
            "did_post_25_26": r_did["post_25_26"],
            "pre_linear_yr": r_did["pre_linear_yr"],
            "joint_pre_F": r_did["joint_pre_F"],
            "exact_cluster_ri_B2000": ri_res,
            "fisher_complex_level_post": fisher_cplx,
            "fisher_fund_qtr_level_post": fisher_fq,
        }
        p = r_did["post_25_26"]
        print(
            f"  {arm_lbl:30s} | b={p['beta'] * 100:+5.2f}pp (t={p['t_cr1']:+5.2f}, wcb={p['p_wcb']:.3f}) | "
            f"G_small={ri_res['n_control_clusters']}, G_large={ri_res['n_treated_clusters']} | "
            f"RI 2-sided p(b)={ri_res['ri_p_2sided_beta']:.4f} (1s={ri_res['ri_p_1sided_beta']:.4f}), p(t)={ri_res['ri_p_2sided_t']:.4f} | "
            f"Fisher2s cplx={fisher_cplx['p_2sided']:.4f}, fq={fisher_fq['p_2sided']:.4f}",
            flush=True,
        )
        table2_rows.append(
            {
                "spec": arm_lbl,
                "N": p["N"],
                "G_total": p["G"],
                "G_small": ri_res["n_control_clusters"],
                "G_large": ri_res["n_treated_clusters"],
                "beta_pp": p["beta"] * 100.0,
                "se_pp": p["se_cr1"] * 100.0,
                "t_cr1": p["t_cr1"],
                "p_cr1": p["p_cr1"],
                "p_wcb": p["p_wcb"],
                "ri_p_2sided_beta": ri_res["ri_p_2sided_beta"],
                "ri_p_2sided_t": ri_res["ri_p_2sided_t"],
                "fisher_cplx_p_2s": fisher_cplx["p_2sided"],
                "fisher_fq_p_2s": fisher_fq["p_2sided"],
                "joint_pre_p": r_did["joint_pre_F"]["p"],
            }
        )
        if arm_lbl == "B4_LEGACY_2001_PLACEBO":
            for q_i, q_d in sorted(r_did["event_study_q"].items()):
                es_export_rows.append({"spec": "LEGACY_PLACEBO", "REP_YQ": q_i, **q_d})

    # Saturated Triple-Difference (DDD): Large x MultiAsset x Post25-26
    ddd_out = {}
    for dtag, sub_src, ycol, sz_col, a_col in [
        ("DDD_GVI_COMPLEX23Q2_FULL", active_df[active_df["PREV_HAS_GVI"] == 1], "DROP_GVI", "LARGE_COMPLEX_23Q2", "PREV_IS_ALLOC_FUND"),
        ("DDD_GVI_COMPLEX23Q2_COMP26Q2", active_df[(active_df["IS_COMPLETE_QTR"] == 1) & (active_df["PREV_HAS_GVI"] == 1)], "DROP_GVI", "LARGE_COMPLEX_23Q2", "PREV_IS_ALLOC_FUND"),
        ("DDD_GVI_COMPLEX24Q4_FULL", active_df[active_df["PREV_HAS_GVI"] == 1], "DROP_GVI", "LARGE_COMPLEX_24Q4", "PREV_IS_ALLOC_FUND"),
        ("DDD_GVI_CIK23Q2_FULL", active_df[active_df["PREV_HAS_GVI"] == 1], "DROP_GVI", "LARGE_CIK_23Q2", "PREV_IS_ALLOC_FUND"),
        ("DDD_GV_COMPLEX23Q2_FULL", active_df[active_df["PREV_HAS_GV"] == 1], "DROP_GV", "LARGE_COMPLEX_23Q2", "PREV_IS_ALLOC_FUND"),
        ("DDD_GVI_OPAQUE_COMPLEX23Q2", active_df[active_df["PREV_HAS_GVI"] == 1], "DROP_GVI_OPAQUE", "LARGE_COMPLEX_23Q2", "PREV_IS_ALLOC_FUND"),
    ]:
        s = sub_src[sub_src[sz_col].notna()].copy()
        L = s[sz_col].to_numpy(dtype=float)
        A = s[a_col].to_numpy(dtype=float)
        yq = s["REP_YQ"].to_numpy(dtype=int)
        P1 = ((yq >= 20234) & (yq <= 20244)).astype(float)
        P2 = (yq >= 20251).astype(float)
        fe_q = pd.get_dummies(s["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()
        X = np.column_stack([L * A * P2, L * A * P1, L * P2, L * P1, A * P2, A * P1, L * A, L, A, np.ones(len(s)), fe_q])
        r = ols_cr1_wcb(s[ycol].to_numpy(dtype=float), X, s["COMPLEX_ID"].to_numpy(), test_col_idx=0, n_boot=999)
        # Pre-trend DDD (2020Q1-2023Q2)
        mp = yq <= 20232
        sp = s[mp]
        tyr = (sp["REP_YQ"].to_numpy() // 10 - 2020) + ((sp["REP_YQ"].to_numpy() % 10) - 1) / 4.0
        fe_qp = pd.get_dummies(sp["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()
        Xp = np.column_stack([L[mp] * A[mp] * tyr, L[mp] * tyr, A[mp] * tyr, L[mp] * A[mp], L[mp], A[mp], np.ones(len(sp)), fe_qp])
        rpre = ols_cr1_wcb(sp[ycol].to_numpy(dtype=float), Xp, sp["COMPLEX_ID"].to_numpy(), test_col_idx=0, n_boot=999)
        ddd_out[dtag] = {"ddd_25_26": r, "pre_ddd_yr": rpre}
        print(
            f"  {dtag:30s} | N={r['N']:6d} G={r['G']:3d} rk={r['rank']}/{r['k']} | "
            f"DDD={r['beta'] * 100:+5.2f}pp (t={r['t_cr1']:+5.2f}, wcb={r['p_wcb']:.3f}) | PreYr p={rpre['p_cr1']:.3f}",
            flush=True,
        )
    results["statutory_cutoff_tests"] = cutoff_tests
    results["ddd_tests"] = ddd_out

    # -----------------------------------------------------------------------
    # [6/7] ESG Greenhushing Benchmark (ESG vs Legacy-2001)
    # -----------------------------------------------------------------------
    print("\n[6/7] ESG Greenhushing Benchmark (ESG vs Legacy-2001)...", flush=True)
    esg_vs_leg = df_full[
        (df_full["PREV_HAS_ESG"] == 1)
        | ((df_full["PREV_HAS_LEGACY"] == 1) & (df_full["PREV_HAS_ESG"] == 0) & (df_full["PREV_HAS_GVI"] == 0))
    ].copy()
    esg_vs_leg["Y_TERM_DROP"] = np.where(esg_vs_leg["PREV_HAS_ESG"] == 1, esg_vs_leg["DROP_ESG"], esg_vs_leg["DROP_LEGACY"])
    r_esg_bench = run_did_with_pretrend(esg_vs_leg, y_col="Y_TERM_DROP", treat_col="PREV_HAS_ESG", n_boot=999)
    results["esg_vs_legacy_benchmark"] = {
        "post_25_26": r_esg_bench["post_25_26"],
        "pre_linear_yr": r_esg_bench["pre_linear_yr"],
        "joint_pre_F": r_esg_bench["joint_pre_F"],
    }
    pe = r_esg_bench["post_25_26"]
    print(
        f"  ESG vs Legacy-2001 DiD | N={pe['N']:6d} G={pe['G']:3d} | Post25-26={pe['beta'] * 100:+5.2f}pp "
        f"(t={pe['t_cr1']:+5.2f}, wcb={pe['p_wcb']:.3f}) | PreLin p={r_esg_bench['pre_linear_yr']['p_cr1']:.3f} | "
        f"JointPre p={r_esg_bench['joint_pre_F']['p']:.3f}",
        flush=True,
    )
    for q_i, q_d in sorted(r_esg_bench["event_study_q"].items()):
        es_export_rows.append({"spec": "ESG_VS_LEGACY", "REP_YQ": q_i, **q_d})

    # -----------------------------------------------------------------------
    # [7/7] Leave-One-Complex-Out (LOFO) Across EVERY Dropping Complex
    # -----------------------------------------------------------------------
    print("\n[7/7] Leave-One-Complex-Out (LOFO) Influence Audit across every dropping complex...", flush=True)
    lofo_out = {}
    for ltag, sub_df, tr_col, y_col in [
        ("LOFO_A1_GV", df_full[df_full["PREV_HAS_GV"] == 1].copy(), "PREV_IS_ALLOC_FUND", "DROP_GV"),
        ("LOFO_A3_GVI", df_full[df_full["PREV_HAS_GVI"] == 1].copy(), "PREV_IS_ALLOC_FUND", "DROP_GVI"),
        ("LOFO_A3_GVI_OPAQUE", df_full[df_full["PREV_HAS_GVI"] == 1].copy(), "PREV_IS_ALLOC_FUND", "DROP_GVI_OPAQUE"),
        (
            "LOFO_B1_LARGE_VS_SMALL",
            active_df[(active_df["PREV_IS_ALLOC_FUND"] == 1) & (active_df["PREV_HAS_GVI"] == 1) & active_df["LARGE_COMPLEX_23Q2"].notna()].copy(),
            "LARGE_COMPLEX_23Q2",
            "DROP_GVI",
        ),
    ]:
        cand_cplx = sorted(set(sub_df.loc[(sub_df[y_col] == 1) & (sub_df["REP_YQ"] >= 20251), "COMPLEX_ID"]))
        worst_t, worst_cplx = 1e9, None
        max_b, max_t = -1e9, -1e9
        for cplx in cand_cplx:
            s = sub_df[sub_df["COMPLEX_ID"] != cplx]
            tr = s[tr_col].to_numpy(dtype=float)
            yq = s["REP_YQ"].to_numpy(dtype=int)
            p1 = ((yq >= 20234) & (yq <= 20244)).astype(float)
            p2 = (yq >= 20251).astype(float)
            fe_q = pd.get_dummies(s["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()
            X = np.column_stack([tr * p2, tr * p1, tr, np.ones(len(s)), fe_q])
            r0 = ols_cr1_wcb(s[y_col].to_numpy(dtype=float), X, s["COMPLEX_ID"].to_numpy(), test_col_idx=0, do_wcb=False)
            if r0["t_cr1"] < worst_t:
                worst_t, worst_cplx = r0["t_cr1"], cplx
            if r0["t_cr1"] > max_t:
                max_t, max_b = r0["t_cr1"], r0["beta"]
        # Full WCB on worst LOFO drop
        sw = sub_df[sub_df["COMPLEX_ID"] != worst_cplx]
        trw = sw[tr_col].to_numpy(dtype=float)
        yqw = sw["REP_YQ"].to_numpy(dtype=int)
        p1w = ((yqw >= 20234) & (yqw <= 20244)).astype(float)
        p2w = (yqw >= 20251).astype(float)
        fe_qw = pd.get_dummies(sw["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()
        rw = ols_cr1_wcb(
            sw[y_col].to_numpy(dtype=float),
            np.column_stack([trw * p2w, trw * p1w, trw, np.ones(len(sw)), fe_qw]),
            sw["COMPLEX_ID"].to_numpy(),
            test_col_idx=0,
            n_boot=999,
        )
        lofo_out[ltag] = {
            "n_dropping_complexes_tested": len(cand_cplx),
            "worst_dropped_complex": worst_cplx,
            "worst_result": rw,
            "max_beta_pp": float(max_b * 100.0),
            "max_t": float(max_t),
        }
        print(
            f"  {ltag:26s} | tested={len(cand_cplx):2d} dropping cplx | worst drop='{worst_cplx}' -> "
            f"b={rw['beta'] * 100:+5.2f}pp (t={rw['t_cr1']:+5.2f}, p={rw['p_cr1']:.4f}, wcb={rw['p_wcb']:.3f})",
            flush=True,
        )
    results["lofo"] = lofo_out

    # -----------------------------------------------------------------------
    # [7b] Ex-Vanguard Concentration Sensitivity & SEC-FAQ Carve-Out Breakdown
    # -----------------------------------------------------------------------
    ma_aud = audit_df[audit_df["DROP_GROUP"] == "MULTI_ASSET_GVI"].drop_duplicates("SERIES_ID").copy()
    ma_aud_xv = ma_aud[ma_aud["COMPLEX_ID"] != "VANGUARD"].copy()

    def _bif_share_block(df_sub: pd.DataFrame) -> dict:
        tot_n = len(df_sub)
        tot_aum_b = float(df_sub["AUM_M"].sum() / 1000.0)
        out_b: dict = {
            "n_funds": int(tot_n),
            "n_complexes": int(df_sub["COMPLEX_ID"].nunique()),
            "total_aum_B": tot_aum_b,
        }
        for ct in ("OPAQUE_SYNONYM", "NUMERIC_RATIO", "OTHER_MERGER_BRAND"):
            g = df_sub[df_sub["COMPLIANCE_TYPE"] == ct]
            aum_b = float(g["AUM_M"].sum() / 1000.0)
            out_b[ct] = {
                "n_funds": len(g),
                "pct_funds": float(100.0 * len(g) / max(tot_n, 1)),
                "n_complexes": int(g["COMPLEX_ID"].nunique()),
                "aum_B": aum_b,
                "pct_aum": float(100.0 * aum_b / max(tot_aum_b, 1e-9)),
            }
        return out_b

    vg_num_b = float(
        ma_aud.loc[
            (ma_aud["COMPLEX_ID"] == "VANGUARD") & (ma_aud["COMPLIANCE_TYPE"] == "NUMERIC_RATIO"),
            "AUM_M",
        ].sum()
        / 1000.0
    )
    all_num_b = float(ma_aud.loc[ma_aud["COMPLIANCE_TYPE"] == "NUMERIC_RATIO", "AUM_M"].sum() / 1000.0)
    all_ma_b = float(ma_aud["AUM_M"].sum() / 1000.0)

    results["ex_vanguard_sensitivity"] = {
        "vanguard_numeric_n_funds": int(
            ((ma_aud["COMPLEX_ID"] == "VANGUARD") & (ma_aud["COMPLIANCE_TYPE"] == "NUMERIC_RATIO")).sum()
        ),
        "vanguard_numeric_aum_B": vg_num_b,
        "all_numeric_aum_B": all_num_b,
        "vanguard_share_of_numeric_aum_pct": float(100.0 * vg_num_b / max(all_num_b, 1e-9)),
        "vanguard_share_of_total_ma_gvi_aum_pct": float(100.0 * vg_num_b / max(all_ma_b, 1e-9)),
        "all_ma_gvi": _bif_share_block(ma_aud),
        "ex_vanguard_ma_gvi": _bif_share_block(ma_aud_xv),
        "did_full_20_26Q3": {
            "A3_GVI_EX_VANGUARD": results["main_did_full_20_26Q3"]["A3_GVI_EX_VANGUARD"],
            "A3_GVI_OPAQUE_EX_VANGUARD": results["main_did_full_20_26Q3"]["A3_GVI_OPAQUE_EX_VANGUARD"],
            "A3_GVI_NUMERIC_EX_VANGUARD": results["main_did_full_20_26Q3"]["A3_GVI_NUMERIC_EX_VANGUARD"],
        },
        "did_complete_20_26Q2": {
            "A3_GVI_EX_VANGUARD": results["main_did_complete_20_26Q2"]["A3_GVI_EX_VANGUARD"],
            "A3_GVI_OPAQUE_EX_VANGUARD": results["main_did_complete_20_26Q2"]["A3_GVI_OPAQUE_EX_VANGUARD"],
            "A3_GVI_NUMERIC_EX_VANGUARD": results["main_did_complete_20_26Q2"]["A3_GVI_NUMERIC_EX_VANGUARD"],
        },
    }

    # Exact SEC-FAQ (Jan 8, 2025) breakdown of the 50 multi-asset GVI droppers
    old_nm_aud = ma_aud["OLD_NAME"].fillna("")
    has_gv_aud = old_nm_aud.str.contains(r"\b(?:growth|value)\b", case=False, regex=True)
    has_inc_aud = old_nm_aud.str.contains(r"\bincome\b", case=False, regex=True)
    has_gi_aud = old_nm_aud.str.contains(r"\bgrowth\s*(?:&|and)\s*income\b", case=False, regex=True)

    pure_gv_aud = ma_aud[has_gv_aud & (~has_inc_aud)]
    gi_hyb_aud = ma_aud[has_gi_aud]
    inc_only_aud = ma_aud[(~has_gv_aud) & has_inc_aud]

    results["sec_faq_robustness"] = {
        "ma_gvi_dropper_faq_breakdown": {
            "total_ma_gvi_droppers": len(ma_aud),
            "strict_non_faq_gv_no_income": {
                "n_funds": len(pure_gv_aud),
                "pct_funds": float(100.0 * len(pure_gv_aud) / max(len(ma_aud), 1)),
                "n_complexes": int(pure_gv_aud["COMPLEX_ID"].nunique()),
                "aum_B": float(pure_gv_aud["AUM_M"].sum() / 1000.0),
                "n_opaque": int((pure_gv_aud["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM").sum()),
                "n_numeric": int((pure_gv_aud["COMPLIANCE_TYPE"] == "NUMERIC_RATIO").sum()),
            },
            "growth_and_income_hybrids": {
                "n_funds": len(gi_hyb_aud),
                "pct_funds": float(100.0 * len(gi_hyb_aud) / max(len(ma_aud), 1)),
                "aum_B": float(gi_hyb_aud["AUM_M"].sum() / 1000.0),
            },
            "income_only": {
                "n_funds": len(inc_only_aud),
                "pct_funds": float(100.0 * len(inc_only_aud) / max(len(ma_aud), 1)),
                "aum_B": float(inc_only_aud["AUM_M"].sum() / 1000.0),
            },
        },
        "did_full_20_26Q3": {
            "FAQ1_GV_NO_GI": results["main_did_full_20_26Q3"]["FAQ1_GV_NO_GI"],
            "FAQ2_GV_NO_INC": results["main_did_full_20_26Q3"]["FAQ2_GV_NO_INC"],
            "FAQ3_GV_NO_INC_OPAQUE": results["main_did_full_20_26Q3"]["FAQ3_GV_NO_INC_OPAQUE"],
            "FAQ4_GV_NO_INC_HOLD_LT80": results["main_did_full_20_26Q3"]["FAQ4_GV_NO_INC_HOLD_LT80"],
        },
        "high_dim_fe_gv_no_inc_idonly": hd_fe["FULL_20_26Q3_GV_NO_INC_ALLOC_COMPLEX_X_QTR_IDENTIFYING"],
    }

    print(
        f"\n  [EX-VANGUARD] Numeric AUM share: {results['ex_vanguard_sensitivity']['all_ma_gvi']['NUMERIC_RATIO']['pct_aum']:.1f}% overall -> "
        f"{results['ex_vanguard_sensitivity']['ex_vanguard_ma_gvi']['NUMERIC_RATIO']['pct_aum']:.1f}% ex-Vanguard "
        f"(Vanguard = {results['ex_vanguard_sensitivity']['vanguard_share_of_numeric_aum_pct']:.1f}% of Numeric AUM; "
        f"Opaque ex-Vanguard = {results['ex_vanguard_sensitivity']['ex_vanguard_ma_gvi']['OPAQUE_SYNONYM']['pct_funds']:.1f}% funds / "
        f"{results['ex_vanguard_sensitivity']['ex_vanguard_ma_gvi']['OPAQUE_SYNONYM']['pct_aum']:.1f}% AUM)",
        flush=True,
    )
    print(
        f"  [SEC-FAQ BREAKDOWN] Strict non-FAQ GV (excl. Income & G&I): {len(pure_gv_aud)}/{len(ma_aud)} funds "
        f"(${pure_gv_aud['AUM_M'].sum() / 1000:.2f}B, {pure_gv_aud['COMPLEX_ID'].nunique()} cplx) | "
        f"G&I hybrids={len(gi_hyb_aud)} | Income-only={len(inc_only_aud)}",
        flush=True,
    )

    # Save CSV tables & JSON receipt
    pd.DataFrame(table1_rows).to_csv(TABLES_OUT / "table1_main_did_bifurcation.csv", index=False, lineterminator="\n")
    pd.DataFrame(table1b_rows).to_csv(TABLES_OUT / "table1b_high_dim_fe.csv", index=False, lineterminator="\n")
    pd.DataFrame(table2_rows).to_csv(TABLES_OUT / "table2_mechanisms_and_cutoff.csv", index=False, lineterminator="\n")
    pd.DataFrame(es_export_rows).to_csv(TABLES_OUT / "table3_event_study_quarterly.csv", index=False, lineterminator="\n")

    res_p = RESULTS_OUT / "04_econometrics_results.json"
    res_p.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[DONE PILLAR 4] Saved {res_p.name}, table1, table2, table3.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
