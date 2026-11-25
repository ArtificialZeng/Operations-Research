"""Step 4 (Pillar 1): Complete 2000-2026 Structural Regime Emergence and
Strict-Era (2022-2026) 6-Archetype Contract-Design Econometrics.

Strict Era Discipline (Audit Fix 2):
  - photo_verify was ~0% prior to 2022. Therefore ALL primary contract-design
    and contact-infrastructure regressions run strictly on 2022-2026 (N=1,803,
    G=1,400 independent firm clusters), with zero era splicing.
  - Historical 2000-2026 annual series tracks the 27-year structural shift.
  - Complete robustness battery: Product x Year clustering, Fine-Product-Noun x Year FE,
    Binomial Logit ORs, Within Refund-Only, Within Repair/Replace, High-Price (>= $100),
    Large-Batch (>= 10,000 units), Within Made-in-China, Mediation (free_webmail + no_phone),
    Suspected U.S. Shell-Front LLC Sensitivity, General vs. Mandatory Rules,
    Exact Stratified Permutation (B=1,000), Leave-One-Category-Out, Leave-One-Year-Out,
    and transparent era sensitivity (2021-2026, 2018-2026).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from econometrics_lib import (
    build_full_rank_design,
    fit_clustered_logit,
    fit_cr1_ols,
    stratified_permutation_test,
    wald_linear_contrast,
    wild_cluster_bootstrap_t,
)

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
PARSED_CSV = BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv"
OUT_JSON = BASE_DIR / "results" / "04_pillar1_econometrics.json"

ARCH_INDICATORS = [
    "a_mkt_fd_cn",
    "a_mkt_fd_noncn",
    "a_mkt_true_us",
    "a_dtc_online",
    "a_omnichannel",
]
ARCH_LABELS = {
    "a_mkt_fd_cn": "1_Mkt_FD_China",
    "a_mkt_fd_noncn": "2_Mkt_FD_NonChina",
    "a_mkt_true_us": "3_Mkt_True_US",
    "a_dtc_online": "4_DTC_Online_Only",
    "a_omnichannel": "5_Omnichannel",
}


def add_reg_features(sub: pd.DataFrame) -> pd.DataFrame:
    d = sub.copy().reset_index(drop=True)
    d["p_dec"] = pd.qcut(d["price"], q=10, labels=False, duplicates="drop").astype(int).astype(str)
    d["u_dec"] = pd.qcut(d["units"], q=10, labels=False, duplicates="drop").astype(int).astype(str)
    d["a_mkt_fd_cn"] = (d["archetype_6"] == "1_Mkt_FD_China").astype(int)
    d["a_mkt_fd_noncn"] = (d["archetype_6"] == "2_Mkt_FD_NonChina").astype(int)
    d["a_mkt_true_us"] = (d["archetype_6"] == "3_Mkt_True_US").astype(int)
    d["a_dtc_online"] = (d["archetype_6"] == "4_DTC_Online_Only").astype(int)
    d["a_omnichannel"] = (d["archetype_6"] == "5_Omnichannel").astype(int)
    # Shell-front split indicators
    d["a_mkt_us_shell"] = ((d["archetype_6"] == "3_Mkt_True_US") & (d["shell_suspected"] == 1)).astype(int)
    d["a_mkt_us_legacy"] = ((d["archetype_6"] == "3_Mkt_True_US") & (d["shell_suspected"] == 0)).astype(int)
    # Alternative clustering & fine FE keys
    d["prod_yr"] = d["prod_cat"].astype(str) + "_" + d["year"].astype(str)
    d["fine_noun_yr"] = d["fine_noun"].astype(str) + "_" + d["year"].astype(str)
    return d


def run_saturated_spec(
    sub: pd.DataFrame,
    ycol: str,
    treat_cols: list[str],
    extra_num: list[str] | None = None,
    cat_fe: list[str] | None = None,
    cluster_col: str = "firm_cluster",
    contrast_pair: tuple[str, str] | None = ("a_mkt_fd_cn", "a_mkt_true_us"),
    run_wcb: bool = True,
    wcb_B: int = 999,
    seed: int = 20261126,
) -> dict[str, Any]:
    num_cols = list(treat_cols) + (extra_num if extra_num is not None else ["is_china_mfr"])
    fe_cols = cat_fe if cat_fe is not None else ["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"]

    X, names = build_full_rank_design(sub, num_cols, fe_cols)
    y = sub[ycol].astype(float).to_numpy()
    cl = sub[cluster_col].astype(str).to_numpy()

    fit = fit_cr1_ols(y, X, names, cl)

    out_terms: dict[str, Any] = {}
    for idx_t, tc in enumerate(treat_cols):
        if tc in fit["params"]:
            rec = dict(fit["params"][tc])
            if run_wcb:
                wcb = wild_cluster_bootstrap_t(y, X, names, cl, {tc: 1.0}, B=wcb_B, seed=seed + idx_t * 17)
                rec["p_wcb"] = wcb["p_wcb"]
            out_terms[tc] = rec

    contrast_res = None
    if contrast_pair is not None and contrast_pair[0] in fit["params"] and contrast_pair[1] in fit["params"]:
        c_weights = {contrast_pair[0]: 1.0, contrast_pair[1]: -1.0}
        contrast_res = wald_linear_contrast(fit, c_weights)
        if run_wcb:
            wcb_c = wild_cluster_bootstrap_t(y, X, names, cl, c_weights, B=wcb_B, seed=seed + 777)
            contrast_res["p_wcb"] = wcb_c["p_wcb"]

    return {
        "ycol": ycol,
        "n": fit["n"],
        "k": fit["k"],
        "rank": fit["rank"],
        "n_clusters": fit["n_clusters"],
        "df_t": fit["df_t"],
        "r2": round(fit["r2"], 4),
        "cluster_col": cluster_col,
        "terms": out_terms,
        "contrast": contrast_res,
    }


def main() -> int:
    df = pd.read_csv(PARSED_CSV, low_memory=False)
    print(f"[STEP 4] Loaded {len(df):,} parsed recalls (2000-2026).", flush=True)

    # 1. Historical 2000-2026 annual regime emergence table
    hist_rows = []
    for yr, g in df.groupby("year"):
        n_yr = len(g)
        mkt_only = g["channel"] == "Marketplace_Only"
        fd_cn = g["archetype_6"] == "1_Mkt_FD_China"
        fd_any = g["is_foreign_direct_any"] == 1
        pv_all = float(g["photo_verify"].mean())
        hist_rows.append({
            "year": int(yr),
            "n_total": int(n_yr),
            "n_mkt_only": int(mkt_only.sum()),
            "share_mkt_only": round(float(mkt_only.mean()), 4),
            "n_fd_china": int(fd_cn.sum()),
            "share_fd_china": round(float(fd_cn.mean()), 4),
            "n_fd_any": int(fd_any.sum()),
            "share_fd_any": round(float(fd_any.mean()), 4),
            "n_amazon_only": int(g["amazon_only_mkt"].sum()),
            "share_photo_verify_all": round(pv_all, 4),
            "share_physical_mutilate_all": round(float(g["physical_mutilate"].mean()), 4),
            "share_free_webmail_all": round(float(g["free_webmail"].mean()), 4),
            "share_no_phone_all": round(float(g["no_phone"].mean()), 4),
        })

    # 2. Strict-Era 2022-2026 descriptive summary across 6 archetypes
    d22_all = df[(df["year"] >= 2022) & (df["archetype_6"] != "7_Other_Unclear")].copy()
    d22_reg = add_reg_features(d22_all[d22_all["price"].notna() & d22_all["units"].notna()])

    # Concentration check inside Marketplace_Only (2022-2026)
    mkt_22 = d22_all[d22_all["channel"] == "Marketplace_Only"]
    top10_share = float(mkt_22["firm_cluster"].value_counts().head(10).sum() / max(len(mkt_22), 1))
    concentration_stats = {
        "n_mkt_only_2022_2026": len(mkt_22),
        "unique_firms_mkt_only_2022_2026": int(mkt_22["firm_cluster"].nunique()),
        "top10_firm_share": round(top10_share, 4),
        "fd_china_2022_2026_n": int((d22_all["archetype_6"] == "1_Mkt_FD_China").sum()),
        "fd_china_unique_firms": int(d22_all.loc[d22_all["archetype_6"] == "1_Mkt_FD_China", "firm_cluster"].nunique()),
    }

    arch_order = [
        "1_Mkt_FD_China", "2_Mkt_FD_NonChina", "3_Mkt_True_US",
        "4_DTC_Online_Only", "5_Omnichannel", "6_Brick_and_Mortar",
    ]
    desc_6 = {}
    for a in arch_order:
        g = d22_all[d22_all["archetype_6"] == a]
        desc_6[a] = {
            "n_all": len(g),
            "n_reg": int((d22_reg["archetype_6"] == a).sum()),
            "median_price": round(float(g["price"].median()), 2) if g["price"].notna().any() else None,
            "median_units": round(float(g["units"].median()), 1) if g["units"].notna().any() else None,
            "china_mfr_share": round(float(g["is_china_mfr"].mean()), 4),
            "photo_verify": round(float(g["photo_verify"].mean()), 4),
            "physical_mutilate": round(float(g["physical_mutilate"].mean()), 4),
            "direct_return": round(float(g["direct_return"].mean()), 4),
            "email_only": round(float(g["email_only"].mean()), 4),
            "free_webmail": round(float(g["free_webmail"].mean()), 4),
            "no_phone": round(float(g["no_phone"].mean()), 4),
            "refund_only": round(float(g["refund_only"].mean()), 4),
            "repair_or_replace": round(float(g["repair_or_replace"].mean()), 4),
            "mandatory_rule": round(float(g["mandatory_rule"].mean()), 4),
            "has_upc": round(float(g["has_upc"].mean()), 4),
            "has_inconjunction": round(float(g["has_inconjunction"].mean()), 4),
            "has_injury": round(float(g["has_injury"].mean()), 4),
        }

    # 3. MAIN STRICT-ERA (2022-2026) ULTRA-SATURATED CONTRACT & CONTACT REGRESSIONS
    print(f"\n=== MAIN STRICT-ERA (2022-2026) REGRESSIONS (N={len(d22_reg):,}, G={d22_reg['firm_cluster'].nunique():,}) ===", flush=True)
    main_outcomes = [
        "photo_verify",
        "physical_mutilate",
        "direct_return",
        "email_only",
        "free_webmail",
        "no_phone",
        "refund_only",
        "repair_or_replace",
    ]
    main_models: dict[str, Any] = {}
    for idx_y, ycol in enumerate(main_outcomes):
        res = run_saturated_spec(
            d22_reg,
            ycol=ycol,
            treat_cols=ARCH_INDICATORS,
            run_wcb=True,
            wcb_B=999,
            seed=20261126 + idx_y * 101,
        )
        main_models[ycol] = res
        fd = res["terms"]["a_mkt_fd_cn"]
        us = res["terms"]["a_mkt_true_us"]
        dtc = res["terms"]["a_dtc_online"]
        om = res["terms"]["a_omnichannel"]
        ct = res["contrast"]
        print(
            f"  {ycol:18s}: FD_CN={fd['beta']:+.4f} (t={fd['t']:+.2f}, pWCB={fd['p_wcb']:.3f}) | "
            f"Mkt_US={us['beta']:+.4f} (t={us['t']:+.2f}) | "
            f"DTC={dtc['beta']:+.4f} (t={dtc['t']:+.2f}, pWCB={dtc['p_wcb']:.3f}) | "
            f"Omni={om['beta']:+.4f} (t={om['t']:+.2f}) | "
            f"FD-US={ct['diff']:+.4f} (t={ct['t']:+.2f}, pWCB={ct['p_wcb']:.3f})",
            flush=True,
        )

    # 4. COMPLETE ROBUSTNESS & IDENTIFICATION BATTERY ON photo_verify (STRICTLY 2022-2026!)
    print("\n=== ROBUSTNESS & IDENTIFICATION BATTERY (photo_verify, 2022-2026) ===", flush=True)
    robust: dict[str, Any] = {}

    # R1: Baseline
    robust["R1_baseline_firm_cr1"] = main_models["photo_verify"]

    # R2: Product_Cat x Year clustering
    robust["R2_prod_year_cluster"] = run_saturated_spec(
        d22_reg, "photo_verify", ARCH_INDICATORS, cluster_col="prod_yr", run_wcb=True, wcb_B=999, seed=3001
    )

    # R3: Fine-Product-Noun x Year FE (within exact same fine product noun & year!)
    robust["R3_fine_noun_x_year_fe"] = run_saturated_spec(
        d22_reg,
        "photo_verify",
        ARCH_INDICATORS,
        cat_fe=["p_dec", "u_dec", "hazard_cat", "yq", "fine_noun_yr"],
        run_wcb=True,
        wcb_B=999,
        seed=3002,
    )

    # R4: Binomial Logit ORs (2022-2026, firm-clustered; use clean non-separating FE: price_dec, unit_dec, prod_cat, hazard_cat, year)
    # Note: year FE avoids empty YQ perfect-separation cells in nonlinear logit while holding exact saturated controls!
    X_log, n_log = build_full_rank_design(
        d22_reg,
        ARCH_INDICATORS + ["is_china_mfr"],
        ["p_dec", "u_dec", "prod_cat", "hazard_cat", "year"],
    )
    logit_res = fit_clustered_logit(
        d22_reg["photo_verify"].to_numpy(),
        X_log,
        n_log,
        d22_reg["firm_cluster"].astype(str).to_numpy(),
    )
    robust["R4_binomial_logit_or"] = {
        "n": logit_res["n"],
        "k": logit_res["k"],
        "converged": logit_res["converged"],
        "terms": {tc: logit_res["params"][tc] for tc in ARCH_INDICATORS if tc in logit_res["params"]},
    }

    # R5: Within Refund_Only
    sub_ref = add_reg_features(d22_reg[d22_reg["refund_only"] == 1])
    robust["R5_within_refund_only"] = run_saturated_spec(
        sub_ref, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3005
    )

    # R6: Within Has_Repair_or_Replace
    sub_rep = add_reg_features(d22_reg[d22_reg["repair_or_replace"] == 1])
    robust["R6_within_repair_replace"] = run_saturated_spec(
        sub_rep, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3006
    )

    # R7: High-Price Durables (Price >= $100)
    sub_hi_p = add_reg_features(d22_reg[d22_reg["price"] >= 100.0])
    robust["R7_high_price_ge_100"] = run_saturated_spec(
        sub_hi_p, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3007
    )

    # R8: Large Batches (Units >= 10,000)
    sub_hi_u = add_reg_features(d22_reg[d22_reg["units"] >= 10000.0])
    robust["R8_large_batch_ge_10k"] = run_saturated_spec(
        sub_hi_u, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3008
    )

    # R9: Strictly within Made-in-China only
    sub_cn = add_reg_features(d22_reg[d22_reg["is_china_mfr"] == 1])
    robust["R9_within_made_in_china"] = run_saturated_spec(
        sub_cn, "photo_verify", ARCH_INDICATORS, extra_num=[], run_wcb=True, wcb_B=999, seed=3009
    )

    # R10: Controlling for free_webmail & no_phone (Mediation Decomposition)
    robust["R10_control_webmail_nophone"] = run_saturated_spec(
        d22_reg,
        "photo_verify",
        ARCH_INDICATORS,
        extra_num=["is_china_mfr", "free_webmail", "no_phone"],
        run_wcb=True,
        wcb_B=999,
        seed=3010,
    )
    # Also save mediation coefficients on free_webmail and no_phone
    X_med, n_med = build_full_rank_design(
        d22_reg,
        ARCH_INDICATORS + ["is_china_mfr", "free_webmail", "no_phone"],
        ["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"],
    )
    fit_med = fit_cr1_ols(d22_reg["photo_verify"].to_numpy(), X_med, n_med, d22_reg["firm_cluster"].astype(str).to_numpy())
    robust["R10_control_webmail_nophone"]["mediator_terms"] = {
        "free_webmail": fit_med["params"]["free_webmail"],
        "no_phone": fit_med["params"]["no_phone"],
    }

    # R11: Suspected U.S.-Registered Shell Front LLC Sensitivity Audit
    shell_treats = [
        "a_mkt_fd_cn", "a_mkt_fd_noncn", "a_mkt_us_shell",
        "a_mkt_us_legacy", "a_dtc_online", "a_omnichannel",
    ]
    robust["R11_shell_front_audit"] = run_saturated_spec(
        d22_reg,
        "photo_verify",
        shell_treats,
        contrast_pair=("a_mkt_fd_cn", "a_mkt_us_legacy"),
        run_wcb=True,
        wcb_B=999,
        seed=3011,
    )
    # Also save exact Shell - Legacy contrast!
    X_sh, n_sh = build_full_rank_design(
        d22_reg, shell_treats + ["is_china_mfr"], ["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"]
    )
    fit_sh = fit_cr1_ols(d22_reg["photo_verify"].to_numpy(), X_sh, n_sh, d22_reg["firm_cluster"].astype(str).to_numpy())
    sh_diff = wald_linear_contrast(fit_sh, {"a_mkt_us_shell": 1.0, "a_mkt_us_legacy": -1.0})
    sh_wcb = wild_cluster_bootstrap_t(
        d22_reg["photo_verify"].to_numpy(), X_sh, n_sh, d22_reg["firm_cluster"].astype(str).to_numpy(),
        {"a_mkt_us_shell": 1.0, "a_mkt_us_legacy": -1.0}, B=999, seed=3111
    )
    sh_diff["p_wcb"] = sh_wcb["p_wcb"]
    robust["R11_shell_front_audit"]["shell_minus_legacy_contrast"] = sh_diff

    # R12: General Non-Rule Safety Defects Only (mandatory_rule == 0)
    sub_gen = add_reg_features(d22_reg[d22_reg["mandatory_rule"] == 0])
    robust["R12_general_defects_only"] = run_saturated_spec(
        sub_gen, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3012
    )

    # R13: Mandatory Federal Safety-Rule Violations Only (mandatory_rule == 1)
    sub_rule = add_reg_features(d22_reg[d22_reg["mandatory_rule"] == 1])
    robust["R13_mandatory_rules_only"] = run_saturated_spec(
        sub_rule, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3013
    )

    # R14: Exact Within-Marketplace Stratified Permutation (B=1,000, Year x China strata, FD_China vs Mkt_True_US)
    perm_sub = d22_all[d22_all["archetype_6"].isin(["1_Mkt_FD_China", "3_Mkt_True_US"])].copy()
    perm_strata = (perm_sub["year"].astype(str) + "_" + perm_sub["is_china_mfr"].astype(str)).to_numpy()
    perm_treat = (perm_sub["archetype_6"] == "1_Mkt_FD_China").astype(int).to_numpy()
    perm_res = stratified_permutation_test(
        perm_sub["photo_verify"].to_numpy(), perm_treat, perm_strata, B=1000, seed=20261126
    )
    perm_res["n"] = len(perm_sub)
    robust["R14_exact_permutation_mkt"] = perm_res

    # R15a: Leave-One-Category-Out (all 15 categories)
    loco_rows = []
    for cat in sorted(d22_reg["prod_cat"].unique()):
        sub_c = add_reg_features(d22_reg[d22_reg["prod_cat"] != cat])
        r_c = run_saturated_spec(sub_c, "photo_verify", ARCH_INDICATORS, run_wcb=False)
        loco_rows.append({
            "dropped_category": cat,
            "n": r_c["n"],
            "fd_beta": round(r_c["terms"]["a_mkt_fd_cn"]["beta"], 4),
            "fd_t": round(r_c["terms"]["a_mkt_fd_cn"]["t"], 2),
            "diff_fd_us": round(r_c["contrast"]["diff"], 4),
            "diff_t": round(r_c["contrast"]["t"], 2),
        })
    robust["R15a_leave_one_category_out"] = {
        "min_fd_beta": min(x["fd_beta"] for x in loco_rows),
        "max_fd_beta": max(x["fd_beta"] for x in loco_rows),
        "min_fd_t": min(x["fd_t"] for x in loco_rows),
        "min_diff_fd_us": min(x["diff_fd_us"] for x in loco_rows),
        "min_diff_t": min(x["diff_t"] for x in loco_rows),
        "rows": loco_rows,
    }

    # R15b: Leave-One-Year-Out (all 5 years 2022-2026)
    loyo_rows = []
    for yr in sorted(d22_reg["year"].unique()):
        sub_y = add_reg_features(d22_reg[d22_reg["year"] != yr])
        r_y = run_saturated_spec(sub_y, "photo_verify", ARCH_INDICATORS, run_wcb=False)
        loyo_rows.append({
            "dropped_year": int(yr),
            "n": r_y["n"],
            "fd_beta": round(r_y["terms"]["a_mkt_fd_cn"]["beta"], 4),
            "fd_t": round(r_y["terms"]["a_mkt_fd_cn"]["t"], 2),
            "diff_fd_us": round(r_y["contrast"]["diff"], 4),
            "diff_t": round(r_y["contrast"]["t"], 2),
        })
    robust["R15b_leave_one_year_out"] = {
        "min_fd_beta": min(x["fd_beta"] for x in loyo_rows),
        "max_fd_beta": max(x["fd_beta"] for x in loyo_rows),
        "min_fd_t": min(x["fd_t"] for x in loyo_rows),
        "min_diff_fd_us": min(x["diff_fd_us"] for x in loyo_rows),
        "min_diff_t": min(x["diff_t"] for x in loyo_rows),
        "rows": loyo_rows,
    }

    # R16: Transparent Era-Sensitivity Check (explicitly separate from 2022-2026 main table!)
    d21_reg = add_reg_features(df[(df["year"] >= 2021) & (df["archetype_6"] != "7_Other_Unclear") & df["price"].notna() & df["units"].notna()])
    d18_reg = add_reg_features(df[(df["year"] >= 2018) & (df["archetype_6"] != "7_Other_Unclear") & df["price"].notna() & df["units"].notna()])
    robust["R16a_era_2021_2026"] = run_saturated_spec(d21_reg, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3016)
    robust["R16b_era_2018_2026"] = run_saturated_spec(d18_reg, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3017)

    # Print crisp robustness summary
    for rk in [
        "R1_baseline_firm_cr1", "R2_prod_year_cluster", "R3_fine_noun_x_year_fe",
        "R5_within_refund_only", "R6_within_repair_replace", "R7_high_price_ge_100",
        "R8_large_batch_ge_10k", "R9_within_made_in_china", "R10_control_webmail_nophone",
        "R11_shell_front_audit", "R12_general_defects_only", "R13_mandatory_rules_only",
        "R16a_era_2021_2026", "R16b_era_2018_2026",
    ]:
        r = robust[rk]
        fd = r["terms"]["a_mkt_fd_cn"]
        ct = r["contrast"]
        dtc = r["terms"].get("a_dtc_online", {})
        print(
            f"  {rk:28s}: N={r['n']:4d} | FD_CN={fd['beta']:+.4f} (t={fd['t']:+.2f}, pWCB={fd.get('p_wcb', float('nan')):.3f}) | "
            f"Diff={ct['diff']:+.4f} (t={ct['t']:+.2f}, pWCB={ct.get('p_wcb', float('nan')):.3f}) | "
            f"DTC={dtc.get('beta', float('nan')):+.4f} (t={dtc.get('t', float('nan')):+.2f})",
            flush=True,
        )
    l_fd = robust["R4_binomial_logit_or"]["terms"]["a_mkt_fd_cn"]
    l_dtc = robust["R4_binomial_logit_or"]["terms"]["a_dtc_online"]
    print(f"  R4_binomial_logit_or        : N={robust['R4_binomial_logit_or']['n']} | FD_CN OR={l_fd['or']:.2f}x (z={l_fd['z']:+.2f}, p={l_fd['p']:.2e}) | DTC OR={l_dtc['or']:.2f}x (z={l_dtc['z']:+.2f})", flush=True)
    print(f"  R14_exact_permutation_mkt   : N={perm_res['n']} | obs_diff={perm_res['obs_diff']:+.4f} vs null SD={perm_res['perm_sd']:.4f} | p={perm_res['p_perm']:.4f}", flush=True)
    print(f"  R15a_LOCO (15 cats)         : FD_CN beta in [{robust['R15a_leave_one_category_out']['min_fd_beta']:+.4f}, {robust['R15a_leave_one_category_out']['max_fd_beta']:+.4f}], min t={robust['R15a_leave_one_category_out']['min_fd_t']:+.2f}", flush=True)
    print(f"  R15b_LOYO (5 yrs 22-26)     : FD_CN beta in [{robust['R15b_leave_one_year_out']['min_fd_beta']:+.4f}, {robust['R15b_leave_one_year_out']['max_fd_beta']:+.4f}], min t={robust['R15b_leave_one_year_out']['min_fd_t']:+.2f}", flush=True)

    payload = {
        "historical_2000_2026": hist_rows,
        "concentration_2022_2026": concentration_stats,
        "descriptives_6_archetypes_2022_2026": desc_6,
        "main_models_2022_2026": main_models,
        "robustness_photo_verify_2022_2026": robust,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[DONE STEP 4] Saved {OUT_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
