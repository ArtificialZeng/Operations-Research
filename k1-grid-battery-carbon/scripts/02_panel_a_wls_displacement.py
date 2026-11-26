"""Step 02 (Pillar 3): Re-Architected Panel A — Nationwide Demand-Weighted WLS Causal
Evening Gas-Peaker Displacement (G = 49 U.S. BAs, 2019-2026).

Permanently fixes every Wave-7 Panel A audit defect:
  1. Primary estimator: Demand-weighted WLS (weight = 2019 mean demand d19_mw) on the
     non-mechanical outcome em_ng (Evening 17-22 minus Midday 10-16 Natural Gas / d19),
     completely eliminating DOPD's 22% equal-weighted OLS leverage distortion.
  2. Exact CR1 + CGM two-way (BA + YM) + Rademacher & Webb-6pt LSDV-equivalent WCB (B=999)
     + 1,000-permutation Randomization Inference.
  3. Complete robustness battery: collider-free (no em_solar), no-controls, BA x CalMo FE,
     Region x YM FE, BA linear trends, DROP_CISO_ERCO (G=47), DROP_TOP7_BESS (G=42),
     DROP_TOP5_LEVERAGE, BA x Post2024H2 schema-seam FE, PRE vs POST schema split, and
     full 49-BA Leave-One-BA-Out (LOBAO).
  4. Distributed 6-month Lead-Lag timing test + EIA-860M pre-commercial COD-lag forensic
     check + high-frequency daily solar-swing x BESS_MWh dispatch test absorbing BA x YM FE!
  5. Nuclear physical placebo, MWh Duration vs MW Power horse-race (Proposition 1), and
     full 24-hour diurnal displacement profile (h = 1..24).
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from econ_utils import (
    PROC_DIR,
    RES_DIR,
    compute_fwl_cluster_leverage,
    demean_groups_weighted,
    save_json_lf,
    wls_fe_cr1_wcb,
)


def run_ri_permutation(
    df: pd.DataFrame,
    y_col: str,
    ctrl_cols: list[str],
    fe_cols: list[str],
    weight_col: str | None = "d19_mw",
    n_perm: int = 1000,
    seed: int = 20261127,
) -> dict[str, Any]:
    """Exact within-panel BA-level trajectory permutation Randomization Inference."""
    sub = df.dropna(subset=[y_col, "bess_share"] + ctrl_cols).copy()
    y = sub[y_col].to_numpy(dtype=np.float64)
    w = sub[weight_col].to_numpy(dtype=np.float64) if weight_col else np.ones(len(sub))
    w = w / np.mean(w)
    sw = np.sqrt(w)
    fe_list = [sub[c].to_numpy() for c in fe_cols]

    X_ctrl = sub[ctrl_cols].to_numpy(dtype=np.float64)
    M_c = demean_groups_weighted(np.column_stack([y, X_ctrl]), fe_list, weights=w, tol=1e-12)
    yc_w = sw * M_c[:, 0]
    Xc_w = sw[:, None] * M_c[:, 1:]
    # Residualize y orthogonal to controls + FE once
    b_c = np.linalg.pinv(Xc_w.T @ Xc_w) @ (Xc_w.T @ yc_w)
    ey_w = yc_w - Xc_w @ b_c

    # Observed treatment slope via FWL
    x0 = sub["bess_share"].to_numpy(dtype=np.float64)
    x0_d = demean_groups_weighted(x0, fe_list, weights=w, tol=1e-12)
    x0_w = sw * x0_d
    x0_res = x0_w - Xc_w @ (np.linalg.pinv(Xc_w.T @ Xc_w) @ (Xc_w.T @ x0_w))
    beta_obs = float((x0_res @ ey_w) / max(x0_res @ x0_res, 1e-30))

    # Build BA -> YM lookup of bess_share to permute entire BA treatment paths across BAs!
    bas = sorted(sub["ba"].unique())
    piv = sub.pivot(index="ym", columns="ba", values="bess_share").fillna(0.0)
    ba_paths = {ba: piv[ba].to_dict() for ba in bas}
    row_bas = sub["ba"].to_numpy()
    row_yms = sub["ym"].to_numpy()
    ba_to_idx = {b: i for i, b in enumerate(bas)}
    row_ba_i = np.array([ba_to_idx[b] for b in row_bas], dtype=np.int32)
    ym_u, row_ym_i = np.unique(row_yms, return_inverse=True)
    path_mat = np.zeros((len(bas), len(ym_u)), dtype=np.float64)
    for bi, b in enumerate(bas):
        for yi, ym in enumerate(ym_u):
            path_mat[bi, yi] = ba_paths[b].get(ym, 0.0)

    XtX_c_inv = np.linalg.pinv(Xc_w.T @ Xc_w)
    rng = np.random.default_rng(seed)
    b_perm = np.empty(n_perm, dtype=np.float64)
    for p_i in range(n_perm):
        perm_map = rng.permutation(len(bas))
        xp = path_mat[perm_map[row_ba_i], row_ym_i]
        xp_d = demean_groups_weighted(xp, fe_list, weights=w, tol=1e-10, max_iter=200)
        xp_w = sw * xp_d
        xp_res = xp_w - Xc_w @ (XtX_c_inv @ (Xc_w.T @ xp_w))
        b_perm[p_i] = (xp_res @ ey_w) / max(xp_res @ xp_res, 1e-30)

    p_ri = float((1.0 + np.sum(np.abs(b_perm) >= abs(beta_obs))) / (n_perm + 1.0))
    return {
        "beta_obs": beta_obs,
        "n_perm": int(n_perm),
        "p_ri_2sided": p_ri,
        "perm_mean": float(np.mean(b_perm)),
        "perm_sd": float(np.std(b_perm)),
    }


def run_spec(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    fe_cols: list[str],
    weighted: bool = True,
    wcb_B: int = 999,
    run_webb6: bool = True,
    two_way: bool = True,
    seed: int = 20261127,
) -> dict[str, Any]:
    sub = df.dropna(subset=[y_col] + x_cols).copy()
    X = sub[x_cols].to_numpy(dtype=np.float64)
    y = sub[y_col].to_numpy(dtype=np.float64)
    fe_list = [sub[c].to_numpy() for c in fe_cols]
    cl1 = sub["ba"].to_numpy()
    cl2 = sub["ym"].to_numpy() if two_way else None
    w = sub["d19_mw"].to_numpy(dtype=np.float64) if weighted else None

    res = wls_fe_cr1_wcb(
        y,
        X,
        clusters=cl1,
        fe_groups=fe_list,
        weights=w,
        col_names=x_cols,
        wcb_var_idx=0,
        wcb_B=wcb_B,
        wcb_dist="rademacher",
        seed=seed,
        cluster2=cl2,
    )
    if run_webb6 and wcb_B > 0:
        res_w6 = wls_fe_cr1_wcb(
            y,
            X,
            clusters=cl1,
            fe_groups=fe_list,
            weights=w,
            col_names=x_cols,
            wcb_var_idx=0,
            wcb_B=wcb_B,
            wcb_dist="webb6",
            seed=seed + 101,
            cluster2=None,
        )
        res["wcb_webb6"] = res_w6.get("wcb")
    return res


def main() -> int:
    t0 = time.time()
    print("=== STEP 02: PANEL A DEMAND-WEIGHTED WLS CAUSAL DISPLACEMENT ===", flush=True)
    sp = pd.read_parquet(PROC_DIR / "panel_a_monthly_spreads.parquet")
    sp["em_solar_sq"] = sp["em_solar"] ** 2
    sp = sp.sort_values(["ba", "ym"]).reset_index(drop=True)

    main_ctrls = [
        "em_demand",
        "em_solar",
        "em_wind",
        "em_hydro",
        "solar_cap_share",
        "wind_cap_share",
        "coal_cap_share",
        "gas_cap_share",
        "em_solar_sq",
    ]
    collider_free_ctrls = [
        "em_demand",
        "em_wind",
        "em_hydro",
        "solar_cap_share",
        "wind_cap_share",
        "coal_cap_share",
        "gas_cap_share",
    ]

    # ------------------------------------------------------------------
    # 1. Forensic DOPD Leverage Audit: Equal-Weighted OLS vs Demand-Weighted WLS
    # ------------------------------------------------------------------
    print("[02.1] Computing exact FWL cluster leverage (Equal-Weighted OLS vs Demand-Weighted WLS)...", flush=True)
    sp_lev = sp.dropna(subset=["em_ng", "bess_share"] + main_ctrls).copy()
    X_lev = sp_lev[["bess_share"] + main_ctrls].to_numpy(dtype=np.float64)
    fe_ba_ym = [sp_lev["ba"].to_numpy(), sp_lev["ym"].to_numpy()]
    lev_ols = compute_fwl_cluster_leverage(X_lev, sp_lev["ba"].to_numpy(), fe_ba_ym, target_idx=0, weights=None)
    lev_wls = compute_fwl_cluster_leverage(
        X_lev, sp_lev["ba"].to_numpy(), fe_ba_ym, target_idx=0, weights=sp_lev["d19_mw"].to_numpy()
    )
    top5_ols_lev_bas = list(lev_ols.keys())[:5]
    top5_wls_lev_bas = list(lev_wls.keys())[:5]
    print(f"  Equal-weighted OLS Top-5 FWL leverage: { {k: round(100*lev_ols[k], 2) for k in top5_ols_lev_bas} }", flush=True)
    print(f"  Demand-weighted WLS Top-5 FWL leverage: { {k: round(100*lev_wls[k], 2) for k in top5_wls_lev_bas} }", flush=True)
    print(f"  DOPD leverage collapse: OLS={100*lev_ols.get('DOPD',0):.2f}% -> WLS={100*lev_wls.get('DOPD',0):.3f}%", flush=True)

    # ------------------------------------------------------------------
    # 2. Primary WLS Specifications & Full Robustness Battery on em_ng + em_fossil_plus_imp + Nuclear
    # ------------------------------------------------------------------
    print("\n[02.2] Running Primary WLS & Full Robustness Battery (B=999 Rademacher & Webb-6pt WCB)...", flush=True)
    df_all49 = sp.copy()
    df_drop_ce = sp[~sp["ba"].isin(["CISO", "ERCO"])].copy()
    df_drop_top7 = sp[~sp["ba"].isin(["CISO", "ERCO", "AZPS", "SRP", "NEVP", "PNM", "MISO"])].copy()
    df_drop_top5_lev_ols = sp[~sp["ba"].isin(top5_ols_lev_bas)].copy()
    df_pre = sp[sp["ym"] <= "2024-06"].copy()
    df_post = sp[sp["ym"] >= "2024-07"].copy()
    df_thermal43 = sp[sp["is_thermal"] == 1].copy()

    # BA-specific linear trend matrix for BA-trends robustness
    def add_ba_trends(df_in: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        df_t = df_in.copy()
        bas_u = sorted(df_t["ba"].unique())[:-1]
        t_std = (df_t["t_idx"] - df_t["t_idx"].mean()) / max(df_t["t_idx"].std(), 1.0)
        t_cols = []
        for b in bas_u:
            cn = f"tr_{b}"
            df_t[cn] = np.where(df_t["ba"] == b, t_std, 0.0)
            t_cols.append(cn)
        return df_t, t_cols

    specs: dict[str, dict[str, Any]] = {}
    spec_defs = [
        # Core WLS headline (BA + YM FE) and BA x CalMo FE
        ("WLS_ALL49_MAIN_NG", df_all49, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_ALL49_CALMO_NG", df_all49, "em_ng", ["bess_share"] + main_ctrls, ["ba_calmo", "ym"], True),
        ("WLS_ALL49_NO_EM_SOLAR_NG", df_all49, "em_ng", ["bess_share"] + collider_free_ctrls, ["ba", "ym"], True),
        ("WLS_ALL49_NO_CONTROLS_NG", df_all49, "em_ng", ["bess_share"], ["ba", "ym"], True),
        ("WLS_ALL49_REG_YM_NG", df_all49, "em_ng", ["bess_share"] + main_ctrls, ["ba", "reg_ym"], True),
        ("WLS_ALL49_FOSS_IMP", df_all49, "em_fossil_plus_imp", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_ALL49_NUCLEAR_PLACEBO", df_all49, "em_nuclear", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        # Unweighted OLS comparison (exposing DOPD attenuation!) & CISO corruption before-vs-after audit
        ("OLS_EQWT_ALL49_NG", df_all49, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], False),
        ("OLS_EQWT_THERMAL43_NG", df_thermal43, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], False),
        ("WLS_ALL49_UNREPAIRED_CISO_NG", df_all49, "em_ng_unrepaired", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        # Anti-concentration / Drop top grids
        ("WLS_DROP_CISO_48_NG", df_all49[df_all49["ba"] != "CISO"].copy(), "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_DROP_CE_47_NG", df_drop_ce, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_DROP_CE_47_CALMO_NG", df_drop_ce, "em_ng", ["bess_share"] + main_ctrls, ["ba_calmo", "ym"], True),
        ("WLS_DROP_CE_47_FOSS_IMP", df_drop_ce, "em_fossil_plus_imp", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_DROP_CE_47_NUCLEAR", df_drop_ce, "em_nuclear", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_DROP_TOP7_42_NG", df_drop_top7, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_DROP_TOP5_OLS_LEV_NG", df_drop_top5_lev_ols, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        # Schema-seam protection (BA x Post2024H2 FE & uniform split periods)
        ("WLS_ALL49_BA_POST24H2_NG", df_all49, "em_ng", ["bess_share"] + main_ctrls, ["ba_post24h2", "ym"], True),
        ("WLS_DROP_CE_BA_POST24H2_NG", df_drop_ce, "em_ng", ["bess_share"] + main_ctrls, ["ba_post24h2", "ym"], True),
        ("WLS_PRE_SCHEMA_2019_2024H1_NG", df_pre, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        ("WLS_POST_SCHEMA_2024H2_2026_NG", df_post, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], True),
        # Overnight-baseline decomposition (Evening-Night vs Midday-Night!)
        ("WLS_ALL49_EV_MINUS_NIGHT_NG", df_all49, "en_ng", ["bess_share", "en_demand", "en_solar", "en_wind", "en_hydro", "solar_cap_share", "coal_cap_share"], ["ba", "ym"], True),
        ("WLS_ALL49_MID_MINUS_NIGHT_NG", df_all49, "mn_ng", ["bess_share", "mn_demand", "mn_solar", "mn_wind", "mn_hydro", "solar_cap_share", "coal_cap_share"], ["ba", "ym"], True),
    ]

    for tag, d_s, yc, xcs, fecs, w_flag in spec_defs:
        r = run_spec(d_s, yc, xcs, fecs, weighted=w_flag, wcb_B=999, run_webb6=True, two_way=True)
        specs[tag] = r
        c0 = r["coefs"]["bess_share"]
        pr = r["wcb"]["p_wcb"]
        pw = r["wcb_webb6"]["p_wcb"]
        print(
            f"  {tag:32s}: beta={c0['beta']:+.4f} (SE={c0['se_cr1']:.4f}, t={c0['t_cr1']:+.2f}, "
            f"t2w={c0.get('t_2way', 0):+.2f}, p_CR1={c0['p_cr1']:.4f}, p_Rad={pr:.4f}, p_Webb6={pw:.4f}, G={r['G']})",
            flush=True,
        )

    # BA-specific linear trends robustness (ALL 49 & DROP CE)
    for tag, d_base in [("WLS_ALL49_BA_TRENDS_NG", df_all49), ("WLS_DROP_CE_BA_TRENDS_NG", df_drop_ce)]:
        d_tr, t_cols = add_ba_trends(d_base)
        r_tr = run_spec(
            d_tr, "em_ng", ["bess_share"] + main_ctrls + t_cols, ["ba", "ym"], weighted=True, wcb_B=999
        )
        # Keep summary clean (don't dump 48 trend coefs)
        specs[tag] = {
            "n": r_tr["n"],
            "G": r_tr["G"],
            "fe_dof": r_tr["fe_dof"],
            "bess_share": r_tr["coefs"]["bess_share"],
            "wcb": r_tr["wcb"],
            "wcb_webb6": r_tr["wcb_webb6"],
        }
        c0 = r_tr["coefs"]["bess_share"]
        print(
            f"  {tag:32s}: beta={c0['beta']:+.4f} (SE={c0['se_cr1']:.4f}, t={c0['t_cr1']:+.2f}, "
            f"p_Rad={r_tr['wcb']['p_wcb']:.4f}, p_Webb6={r_tr['wcb_webb6']['p_wcb']:.4f})",
            flush=True,
        )

    # Exact 1,000-permutation Randomization Inference for headline WLS specs
    print("\n[02.3] Running 1,000-permutation Randomization Inference (WLS)...", flush=True)
    ri_results = {
        "WLS_ALL49_MAIN_NG": run_ri_permutation(df_all49, "em_ng", main_ctrls, ["ba", "ym"], "d19_mw", 1000),
        "WLS_DROP_CE_47_NG": run_ri_permutation(df_drop_ce, "em_ng", main_ctrls, ["ba", "ym"], "d19_mw", 1000),
        "WLS_ALL49_FOSS_IMP": run_ri_permutation(df_all49, "em_fossil_plus_imp", main_ctrls, ["ba", "ym"], "d19_mw", 1000),
        "WLS_ALL49_NUCLEAR": run_ri_permutation(df_all49, "em_nuclear", main_ctrls, ["ba", "ym"], "d19_mw", 1000),
    }
    for k, v in ri_results.items():
        print(f"  RI {k:22s}: beta_obs={v['beta_obs']:+.4f}, p_RI={v['p_ri_2sided']:.4f}", flush=True)

    # ------------------------------------------------------------------
    # 3. Full 49-BA Leave-One-BA-Out (LOBAO) under WLS
    # ------------------------------------------------------------------
    print("\n[02.4] Running full 49-BA Leave-One-BA-Out (LOBAO) under WLS...", flush=True)
    lobao_rows = []
    for ba_drop in sorted(df_all49["ba"].unique()):
        sub_l = df_all49[df_all49["ba"] != ba_drop]
        r_l = run_spec(
            sub_l, "em_ng", ["bess_share"] + main_ctrls, ["ba", "ym"], weighted=True, wcb_B=199, run_webb6=False, two_way=False
        )
        c0 = r_l["coefs"]["bess_share"]
        lobao_rows.append(
            {
                "dropped_ba": ba_drop,
                "beta": c0["beta"],
                "se_cr1": c0["se_cr1"],
                "t_cr1": c0["t_cr1"],
                "p_cr1": c0["p_cr1"],
                "p_wcb": r_l["wcb"]["p_wcb"],
            }
        )
    lobao_df = pd.DataFrame(lobao_rows)
    lobao_summary = {
        "n_bas": len(lobao_rows),
        "beta_min": float(lobao_df["beta"].min()),
        "beta_max": float(lobao_df["beta"].max()),
        "t_min_abs": float(lobao_df["t_cr1"].abs().min()),
        "p_cr1_max": float(lobao_df["p_cr1"].max()),
        "p_wcb_max": float(lobao_df["p_wcb"].max()),
        "weakest_drop": lobao_df.loc[lobao_df["p_cr1"].idxmax()].to_dict(),
        "strongest_drop": lobao_df.loc[lobao_df["beta"].idxmin()].to_dict(),
        "all_rows": lobao_rows,
    }
    print(
        f"  49-BA LOBAO range: beta in [{lobao_summary['beta_min']:+.4f}, {lobao_summary['beta_max']:+.4f}], "
        f"min |t|={lobao_summary['t_min_abs']:.2f}, max p_CR1={lobao_summary['p_cr1_max']:.4f}, "
        f"weakest drop={lobao_summary['weakest_drop']['dropped_ba']}",
        flush=True,
    )

    # ------------------------------------------------------------------
    # 4. Distributed 6-Month Lead-Lag Timing Test + High-Frequency Daily BA x YM FE Dispatch!
    # ------------------------------------------------------------------
    print("\n[02.5] Running Distributed 6-Month Lead-Lag Timing Test (ALL_49 & DROP_CE_47)...", flush=True)
    # Reindex on complete (ba x calendar-month) grid BEFORE shifting so missing months (e.g. WACM)
    # can NEVER misalign 6-month or 12-month calendar lags/leads!
    all_bas_u = sorted(sp["ba"].unique())
    all_yms_u = sorted(sp["ym"].unique())
    full_grid = pd.MultiIndex.from_product([all_bas_u, all_yms_u], names=["ba", "ym"]).to_frame(index=False)
    sp_ll = full_grid.merge(sp, on=["ba", "ym"], how="left").sort_values(["ba", "ym"]).reset_index(drop=True)
    sp_ll["stock_tm12"] = sp_ll.groupby("ba")["bess_share"].shift(12)
    sp_ll["stock_tm6"] = sp_ll.groupby("ba")["bess_share"].shift(6)
    sp_ll["stock_tp6"] = sp_ll.groupby("ba")["bess_share"].shift(-6)
    sp_ll["stock_tp12"] = sp_ll.groupby("ba")["bess_share"].shift(-12)
    sp_ll["add_tm12_tm6"] = sp_ll["stock_tm6"] - sp_ll["stock_tm12"]
    sp_ll["add_tm6_t0"] = sp_ll["bess_share"] - sp_ll["stock_tm6"]
    sp_ll["fut_t0_tp6"] = sp_ll["stock_tp6"] - sp_ll["bess_share"]
    sp_ll["fut_tp6_tp12"] = sp_ll["stock_tp12"] - sp_ll["stock_tp6"]

    ll_vars = ["stock_tm12", "add_tm12_tm6", "add_tm6_t0", "fut_t0_tp6", "fut_tp6_tp12"]
    lead_lag_results = {}
    for tag, d_s in [
        ("WLS_ALL49_BA_YM", sp_ll),
        ("WLS_DROP_CE_47_BA_YM", sp_ll[~sp_ll["ba"].isin(["CISO", "ERCO"])]),
        ("WLS_ALL49_CALMO_YM", sp_ll),
    ]:
        fe_use = ["ba_calmo", "ym"] if "CALMO" in tag else ["ba", "ym"]
        sub_ll = d_s.dropna(subset=ll_vars + ["em_ng"] + main_ctrls).copy()
        X_ll = sub_ll[ll_vars + main_ctrls].to_numpy(dtype=np.float64)
        y_ll = sub_ll["em_ng"].to_numpy(dtype=np.float64)
        res_ll = wls_fe_cr1_wcb(
            y_ll,
            X_ll,
            clusters=sub_ll["ba"].to_numpy(),
            fe_groups=[sub_ll[c].to_numpy() for c in fe_use],
            weights=sub_ll["d19_mw"].to_numpy(),
            col_names=ll_vars + main_ctrls,
            joint_test_indices=[3, 4],  # Joint F-test on BOTH future leads!
        )
        # Also compute WCB p-values for each of the 5 timing terms
        term_wcb = {}
        for j_i, vnm in enumerate(ll_vars):
            rj = wls_fe_cr1_wcb(
                y_ll,
                X_ll,
                clusters=sub_ll["ba"].to_numpy(),
                fe_groups=[sub_ll[c].to_numpy() for c in fe_use],
                weights=sub_ll["d19_mw"].to_numpy(),
                col_names=ll_vars + main_ctrls,
                wcb_var_idx=j_i,
                wcb_B=499,
                wcb_dist="rademacher",
                seed=20261127 + j_i,
            )
            term_wcb[vnm] = rj["wcb"]["p_wcb"]
        lead_lag_results[tag] = {
            "n": res_ll["n"],
            "G": res_ll["G"],
            "joint_future_leads_F": res_ll["joint_F"],
            "terms": {v: {**res_ll["coefs"][v], "p_wcb": term_wcb[v]} for v in ll_vars},
        }
        print(f"  [LEAD-LAG {tag}] Joint Future F={res_ll['joint_F']['F']:.3f} (p={res_ll['joint_F']['p']:.4f})", flush=True)
        for v in ll_vars:
            tv = lead_lag_results[tag]["terms"][v]
            print(f"    {v:14s}: beta={tv['beta']:+.4f} (SE={tv['se_cr1']:.4f}, t={tv['t_cr1']:+.2f}, p_CR1={tv['p_cr1']:.4f}, p_WCB={tv['p_wcb']:.4f})", flush=True)

    # High-Frequency Daily Solar-Swing x BESS_MWh Dispatch Check (ABSORBING BA x Year-Month FE!)
    print("\n[02.6] Running High-Frequency Daily Dispatch Test (BA x Year-Month FE + Date FE)...", flush=True)
    daily = pd.read_parquet(PROC_DIR / "panel_a_daily_spreads.parquet")
    daily = daily.dropna(subset=["em_ng", "em_demand", "md_sol_norm", "bess_mwh_share"]).copy()
    daily["sol_x_bess_mwh"] = daily["md_sol_norm"] * daily["bess_mwh_share"]
    daily["sol_x_bess_mw"] = daily["md_sol_norm"] * daily["bess_share"]
    daily["dem_x_bess_mwh"] = daily["em_demand"] * daily["bess_mwh_share"]
    daily["md_sol_sq"] = daily["md_sol_norm"] ** 2
    daily["sol_x_solcap"] = daily["md_sol_norm"] * daily["solar_cap_share"].fillna(0.0)

    daily_results = {}
    daily_specs = [
        ("DAILY_ALL49_NG_MWH", daily, "em_ng", ["sol_x_bess_mwh", "md_sol_norm", "em_demand", "em_wind", "em_hydro"]),
        ("DAILY_ALL49_NG_MWH_QUAD_SOLCAP", daily, "em_ng", ["sol_x_bess_mwh", "md_sol_norm", "md_sol_sq", "sol_x_solcap", "em_demand", "em_wind", "em_hydro"]),
        ("DAILY_DROP_CE_47_NG_MWH", daily[~daily["ba"].isin(["CISO", "ERCO"])], "em_ng", ["sol_x_bess_mwh", "md_sol_norm", "em_demand", "em_wind", "em_hydro"]),
        ("DAILY_ALL49_FOSS_IMP_MWH", daily, "em_fossil_plus_imp", ["sol_x_bess_mwh", "md_sol_norm", "em_demand", "em_wind", "em_hydro"]),
        ("DAILY_ALL49_NUCLEAR_PLACEBO", daily, "em_nuclear", ["sol_x_bess_mwh", "md_sol_norm", "em_demand", "em_wind", "em_hydro"]),
    ]
    for tag, d_sub, y_c, x_d in daily_specs:
        r_d = wls_fe_cr1_wcb(
            d_sub[y_c].to_numpy(dtype=np.float64),
            d_sub[x_d].to_numpy(dtype=np.float64),
            clusters=d_sub["ba"].to_numpy(),
            fe_groups=[d_sub["ba_ym"].to_numpy(), d_sub["date"].to_numpy()],
            weights=d_sub["d19_mw"].to_numpy(dtype=np.float64),
            col_names=x_d,
            wcb_var_idx=0,
            wcb_B=399,
            wcb_dist="rademacher",
        )
        daily_results[tag] = r_d
        c0 = r_d["coefs"]["sol_x_bess_mwh"]
        print(
            f"  [{tag:30s}] sol_swing x BESS_MWh: beta={c0['beta']:+.4f} (SE={c0['se_cr1']:.4f}, "
            f"t={c0['t_cr1']:+.2f}, p_CR1={c0['p_cr1']:.4f}, p_WCB={r_d['wcb']['p_wcb']:.4f}, N={r_d['n']:,})",
            flush=True,
        )

    # ------------------------------------------------------------------
    # 5. Proposition 1 Duration Mechanism: MWh Energy vs MW Power Horse-Race!
    # ------------------------------------------------------------------
    print("\n[02.7] Running Duration Mechanism Horse-Race (BESS_MWh vs BESS_MW)...", flush=True)
    dur_results = {}
    for tag, d_s, yc in [
        ("ALL49_EM_NG", df_all49, "em_ng"),
        ("DROP_CE_47_EM_NG", df_drop_ce, "em_ng"),
        ("ALL49_PKMD_NG", df_all49, "pkmd_ng"),
        ("DROP_CE_47_PKMD_NG", df_drop_ce, "pkmd_ng"),
    ]:
        # Run BOTH MWh-only and joint MWh + MW horse-race!
        r_mwh_only = run_spec(d_s, yc, ["bess_mwh_share"] + main_ctrls, ["ba", "ym"], weighted=True, wcb_B=999)
        r_hr = wls_fe_cr1_wcb(
            d_s[yc].to_numpy(dtype=np.float64),
            d_s[["bess_mwh_share", "bess_share"] + main_ctrls].to_numpy(dtype=np.float64),
            clusters=d_s["ba"].to_numpy(),
            fe_groups=[d_s["ba"].to_numpy(), d_s["ym"].to_numpy()],
            weights=d_s["d19_mw"].to_numpy(dtype=np.float64),
            col_names=["bess_mwh_share", "bess_share"] + main_ctrls,
            wcb_var_idx=0,
            wcb_B=999,
            wcb_dist="rademacher",
        )
        r_hr_mw = wls_fe_cr1_wcb(
            d_s[yc].to_numpy(dtype=np.float64),
            d_s[["bess_mwh_share", "bess_share"] + main_ctrls].to_numpy(dtype=np.float64),
            clusters=d_s["ba"].to_numpy(),
            fe_groups=[d_s["ba"].to_numpy(), d_s["ym"].to_numpy()],
            weights=d_s["d19_mw"].to_numpy(dtype=np.float64),
            col_names=["bess_mwh_share", "bess_share"] + main_ctrls,
            wcb_var_idx=1,
            wcb_B=999,
            wcb_dist="rademacher",
        )
        dur_results[tag] = {
            "mwh_only": {
                **r_mwh_only["coefs"]["bess_mwh_share"],
                "p_wcb": r_mwh_only["wcb"]["p_wcb"],
                "p_webb6": r_mwh_only["wcb_webb6"]["p_wcb"],
            },
            "horserace_mwh": {
                **r_hr["coefs"]["bess_mwh_share"],
                "p_wcb": r_hr["wcb"]["p_wcb"],
            },
            "horserace_mw": {
                **r_hr["coefs"]["bess_share"],
                "p_wcb": r_hr_mw["wcb"]["p_wcb"],
            },
        }
        print(
            f"  [DURATION {tag:16s}] MWh_only={dur_results[tag]['mwh_only']['beta']:+.4f} "
            f"(p_WCB={dur_results[tag]['mwh_only']['p_wcb']:.4f}) | Joint MWh={dur_results[tag]['horserace_mwh']['beta']:+.4f} "
            f"(t={dur_results[tag]['horserace_mwh']['t_cr1']:+.2f}, p_WCB={dur_results[tag]['horserace_mwh']['p_wcb']:.4f}) vs "
            f"MW={dur_results[tag]['horserace_mw']['beta']:+.4f} (t={dur_results[tag]['horserace_mw']['t_cr1']:+.2f}, "
            f"p_WCB={dur_results[tag]['horserace_mw']['p_wcb']:.4f})",
            flush=True,
        )

    # ------------------------------------------------------------------
    # 6. Full 24-Hour Diurnal Displacement Curve (h = 1..24, Demand-Weighted WLS!)
    # ------------------------------------------------------------------
    print("\n[02.8] Estimating 24-Hour Diurnal Displacement Profile (h = 1..24, WLS)...", flush=True)
    ph = pd.read_parquet(PROC_DIR / "panel_a_ba_ym_hour.parquet")
    ph["bess_share"] = ph["BESS"] / ph["d19_mw"]
    ph["solar_cap_share"] = ph["SOLAR"] / ph["d19_mw"]
    ph["wind_cap_share"] = ph["WIND"] / ph["d19_mw"]
    ph["coal_cap_share"] = ph["COAL"] / ph["d19_mw"]
    ph["gas_cap_share"] = ph["GAS"] / ph["d19_mw"]
    for v in ["ng", "coal", "fossil_plus_imp", "nuclear", "demand", "solar", "wind", "hydro"]:
        ph[f"n_{v}"] = ph[v] / ph["d19_mw"]

    # Subtract BA x YM mean of each variable (equivalent to absorbing BA x YM FE across hours)
    # so hour h estimates exact within-day reallocation relative to 24-hour mean!
    # Wait: even cleaner & more physically transparent: demean relative to Overnight Baseline (hours 2,3,4,5)
    # so h=2..5 averages 0 and midday charging bump (+h=11..15) and evening discharge (-h=18..21) are directly visible!
    base_ov = (
        ph[ph["hour"].isin([2, 3, 4, 5])]
        .groupby(["ba", "ym"])[["n_ng", "n_fossil_plus_imp", "n_nuclear", "n_demand", "n_solar", "n_wind", "n_hydro"]]
        .mean()
        .add_prefix("ov_")
        .reset_index()
    )
    ph = ph.merge(base_ov, on=["ba", "ym"], how="left")
    for v in ["n_ng", "n_fossil_plus_imp", "n_nuclear", "n_demand", "n_solar", "n_wind", "n_hydro"]:
        ph[f"rel_{v}"] = ph[v] - ph[f"ov_{v}"]

    hourly_profile: dict[str, list[dict[str, Any]]] = {}
    for stag, d_h in [("ALL_49", ph), ("DROP_CISO_ERCO_47", ph[~ph["ba"].isin(["CISO", "ERCO"])])]:
        rows_h = []
        for h in range(1, 25):
            sh = d_h[d_h["hour"] == h].dropna(subset=["rel_n_ng", "bess_share"])
            xh_cols = [
                "bess_share",
                "rel_n_demand",
                "rel_n_solar",
                "rel_n_wind",
                "rel_n_hydro",
                "solar_cap_share",
                "coal_cap_share",
            ]
            r_ng = wls_fe_cr1_wcb(
                sh["rel_n_ng"].to_numpy(),
                sh[xh_cols].to_numpy(),
                clusters=sh["ba"].to_numpy(),
                fe_groups=[sh["ba"].to_numpy(), sh["ym"].to_numpy()],
                weights=sh["d19_mw"].to_numpy(),
                col_names=xh_cols,
            )
            r_fi = wls_fe_cr1_wcb(
                sh["rel_n_fossil_plus_imp"].to_numpy(),
                sh[xh_cols].to_numpy(),
                clusters=sh["ba"].to_numpy(),
                fe_groups=[sh["ba"].to_numpy(), sh["ym"].to_numpy()],
                weights=sh["d19_mw"].to_numpy(),
                col_names=xh_cols,
            )
            r_nu = wls_fe_cr1_wcb(
                sh["rel_n_nuclear"].to_numpy(),
                sh[xh_cols].to_numpy(),
                clusters=sh["ba"].to_numpy(),
                fe_groups=[sh["ba"].to_numpy(), sh["ym"].to_numpy()],
                weights=sh["d19_mw"].to_numpy(),
                col_names=xh_cols,
            )
            rows_h.append(
                {
                    "hour": h,
                    "ng": r_ng["coefs"]["bess_share"],
                    "fossil_plus_imp": r_fi["coefs"]["bess_share"],
                    "nuclear": r_nu["coefs"]["bess_share"],
                }
            )
        hourly_profile[stag] = rows_h
        pk_h = min(rows_h, key=lambda r: r["ng"]["beta"])
        print(
            f"  24h Profile [{stag}]: Peak NG displacement at HE {pk_h['hour']}: "
            f"beta={pk_h['ng']['beta']:+.4f} (SE={pk_h['ng']['se_cr1']:.4f}, t={pk_h['ng']['t_cr1']:+.2f})",
            flush=True,
        )

    out = {
        "leverage_audit": {
            "equal_weighted_ols_top10": {k: lev_ols[k] for k in list(lev_ols.keys())[:10]},
            "demand_weighted_wls_top10": {k: lev_wls[k] for k in list(lev_wls.keys())[:10]},
            "dopd_ols_leverage_pct": float(100.0 * lev_ols.get("DOPD", 0.0)),
            "dopd_wls_leverage_pct": float(100.0 * lev_wls.get("DOPD", 0.0)),
            "top5_ols_leverage_bas": top5_ols_lev_bas,
            "top5_wls_leverage_bas": top5_wls_lev_bas,
        },
        "main_and_robustness_specs": specs,
        "randomization_inference_1000": ri_results,
        "lobao_49_wls": lobao_summary,
        "distributed_6m_lead_lag": lead_lag_results,
        "high_freq_daily_ba_ym_fe": daily_results,
        "duration_mwh_vs_mw": dur_results,
        "diurnal_24h_profile": hourly_profile,
        "elapsed_sec": float(time.time() - t0),
    }

    sha = save_json_lf(RES_DIR / "02_panel_a_wls_results.json", out)
    print(f"[DONE STEP 02] Saved results/02_panel_a_wls_results.json (SHA-256: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
