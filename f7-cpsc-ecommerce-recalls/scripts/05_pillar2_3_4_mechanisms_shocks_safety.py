"""Step 5 (Pillars 2, 3, and 4):
  - Pillar 2: Platform generality, fine-product-noun head-to-head, traceability
    & cross-border coordination collapse (UPC & Inconjunctions), and 2022-2026
    Cross-Border Pioneer -> Domestic Diffusion curve.
  - Pillar 3: In re Amazon.com regulatory enforcement ramp (July 30, 2024
    Distributor Decision & Jan 16, 2025 Final Remedy Order) with Newey-West HAC
    inference on complete quarters (2021Q1-2026Q3 primary + 2026Q4 sensitivity),
    mandatory-rule vs. general-defect split, and post-ruling contract persistence.
  - Pillar 4: Public-safety & environmental externalization audit — mandatory
    federal safety-rule violations, Lithium-ion/Button-cell/Lead hazardous-waste
    self-disposal externalization, pre-recall market duration (months on sale),
    double-count-free injury accounting, and Aug 2025 CPSC direct_contact
    boilerplate forensic exclusion check.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from econometrics_lib import (
    build_full_rank_design,
    fit_cr1_ols,
    fit_newey_west_ols,
    wald_linear_contrast,
    wild_cluster_bootstrap_t,
)

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
RAW_JSON = BASE_DIR / "data" / "cpsc_recalls_2000_2026.json"
PARSED_CSV = BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv"
OUT_JSON = BASE_DIR / "results" / "05_pillars_2_3_4.json"

ARCH_INDICATORS = [
    "a_mkt_fd_cn",
    "a_mkt_fd_noncn",
    "a_mkt_true_us",
    "a_dtc_online",
    "a_omnichannel",
]
ARCH_ORDER = [
    "1_Mkt_FD_China",
    "2_Mkt_FD_NonChina",
    "3_Mkt_True_US",
    "4_DTC_Online_Only",
    "5_Omnichannel",
    "6_Brick_and_Mortar",
]


def prep_reg(sub: pd.DataFrame) -> pd.DataFrame:
    d = sub.copy().reset_index(drop=True)
    d["p_dec"] = pd.qcut(d["price"], q=10, labels=False, duplicates="drop").astype(int).astype(str)
    d["u_dec"] = pd.qcut(d["units"], q=10, labels=False, duplicates="drop").astype(int).astype(str)
    d["a_mkt_fd_cn"] = (d["archetype_6"] == "1_Mkt_FD_China").astype(int)
    d["a_mkt_fd_noncn"] = (d["archetype_6"] == "2_Mkt_FD_NonChina").astype(int)
    d["a_mkt_true_us"] = (d["archetype_6"] == "3_Mkt_True_US").astype(int)
    d["a_dtc_online"] = (d["archetype_6"] == "4_DTC_Online_Only").astype(int)
    d["a_omnichannel"] = (d["archetype_6"] == "5_Omnichannel").astype(int)
    return d


def run_sat(
    sub: pd.DataFrame,
    ycol: str,
    treat_cols: list[str] = ARCH_INDICATORS,
    extra_num: list[str] | None = None,
    cat_fe: list[str] | None = None,
    contrast_pair: tuple[str, str] | None = ("a_mkt_fd_cn", "a_mkt_true_us"),
    wcb_B: int = 999,
    seed: int = 5001,
) -> dict[str, Any]:
    num_cols = list(treat_cols) + (extra_num if extra_num is not None else ["is_china_mfr"])
    fe_cols = cat_fe if cat_fe is not None else ["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"]
    X, names = build_full_rank_design(sub, num_cols, fe_cols)
    y = sub[ycol].astype(float).to_numpy()
    cl = sub["firm_cluster"].astype(str).to_numpy()
    fit = fit_cr1_ols(y, X, names, cl)

    terms = {}
    for i, tc in enumerate(treat_cols):
        if tc in fit["params"]:
            rec = dict(fit["params"][tc])
            wcb = wild_cluster_bootstrap_t(y, X, names, cl, {tc: 1.0}, B=wcb_B, seed=seed + i * 19)
            rec["p_wcb"] = wcb["p_wcb"]
            terms[tc] = rec

    contrast = None
    if contrast_pair and contrast_pair[0] in fit["params"] and contrast_pair[1] in fit["params"]:
        cw = {contrast_pair[0]: 1.0, contrast_pair[1]: -1.0}
        contrast = wald_linear_contrast(fit, cw)
        contrast["p_wcb"] = wild_cluster_bootstrap_t(y, X, names, cl, cw, B=wcb_B, seed=seed + 777)["p_wcb"]

    return {
        "ycol": ycol,
        "n": fit["n"],
        "k": fit["k"],
        "rank": fit["rank"],
        "n_clusters": fit["n_clusters"],
        "r2": round(fit["r2"], 4),
        "terms": terms,
        "contrast": contrast,
    }


def main() -> int:
    df = pd.read_csv(PARSED_CSV, low_memory=False)
    raw_records = json.loads(RAW_JSON.read_text(encoding="utf-8"))
    raw_by_id = {int(r["RecallID"]): r for r in raw_records if r.get("RecallID") is not None}
    d22_all = df[(df["year"] >= 2022) & (df["archetype_6"] != "7_Other_Unclear")].copy()
    d22_reg = prep_reg(d22_all[d22_all["price"].notna() & d22_all["units"].notna()])

    # =========================================================================
    # PILLAR 2: PLATFORM GENERALITY, NOUN HEAD-TO-HEAD, TRACEABILITY, DIFFUSION
    # =========================================================================
    print("=== PILLAR 2: PLATFORM GENERALITY & DIFFUSION (2022-2026) ===", flush=True)

    # 2A. Platform generality across individual 3P marketplaces (strictly inside Marketplace_Only)
    mkt_22 = d22_all[d22_all["channel"] == "Marketplace_Only"].copy()
    plat_cols = [
        ("Amazon.com", "plat_amazon"),
        ("Walmart.com", "plat_walmart_com"),
        ("Temu.com", "plat_temu"),
        ("Shein.com", "plat_shein"),
        ("Wayfair.com", "plat_wayfair"),
        ("AliExpress", "plat_aliexpress"),
        ("eBay / Etsy", "plat_ebay_etsy"),
        ("TikTok / Wish", "plat_tiktok_wish"),
        ("Target.com (Online)", "plat_target_com"),
    ]
    platform_table = []
    for label, col in plat_cols:
        g = mkt_22[mkt_22[col] == 1]
        if len(g) == 0:
            continue
        g_fd = g[g["archetype_6"] == "1_Mkt_FD_China"]
        platform_table.append({
            "platform": label,
            "n_mkt_only": len(g),
            "fd_china_share": round(float((g["archetype_6"] == "1_Mkt_FD_China").mean()), 4),
            "photo_verify_all": round(float(g["photo_verify"].mean()), 4),
            "photo_verify_fd_china": round(float(g_fd["photo_verify"].mean()), 4) if len(g_fd) > 0 else None,
            "n_fd_china": len(g_fd),
            "physical_mutilate_all": round(float(g["physical_mutilate"].mean()), 4),
            "free_webmail_all": round(float(g["free_webmail"].mean()), 4),
            "no_phone_all": round(float(g["no_phone"].mean()), 4),
        })
        print(
            f"  Platform {label:18s}: N={len(g):3d} | FD_CN={platform_table[-1]['fd_china_share']*100:5.1f}% | "
            f"PV={platform_table[-1]['photo_verify_all']*100:5.1f}% | Webmail={platform_table[-1]['free_webmail_all']*100:5.1f}%",
            flush=True,
        )

    # Regression comparing Amazon-Only vs Non-Amazon-Only Marketplace (both FD_China and True_US)
    d22_plat = d22_reg.copy()
    d22_plat["mkt_fd_amazon"] = ((d22_plat["archetype_6"] == "1_Mkt_FD_China") & (d22_plat["plat_amazon"] == 1)).astype(int)
    d22_plat["mkt_fd_nonamazon"] = ((d22_plat["archetype_6"] == "1_Mkt_FD_China") & (d22_plat["plat_amazon"] == 0)).astype(int)
    plat_reg = run_sat(
        d22_plat,
        "photo_verify",
        treat_cols=["mkt_fd_amazon", "mkt_fd_nonamazon", "a_mkt_fd_noncn", "a_mkt_true_us", "a_dtc_online", "a_omnichannel"],
        contrast_pair=("mkt_fd_amazon", "mkt_fd_nonamazon"),
        seed=5101,
    )
    print(
        f"  FE Amazon-vs-NonAmazon FD_China: Amz={plat_reg['terms']['mkt_fd_amazon']['beta']:+.4f} (t={plat_reg['terms']['mkt_fd_amazon']['t']:+.2f}) | "
        f"NonAmz={plat_reg['terms']['mkt_fd_nonamazon']['beta']:+.4f} (t={plat_reg['terms']['mkt_fd_nonamazon']['t']:+.2f}) | "
        f"Diff={plat_reg['contrast']['diff']:+.4f} (t={plat_reg['contrast']['t']:+.2f}, pWCB={plat_reg['contrast']['p_wcb']:.3f})",
        flush=True,
    )

    # 2B. Exact Fine-Product-Noun Head-to-Head (2022-2026)
    noun_rows = []
    for noun, g in d22_all.groupby("fine_noun"):
        if noun == "Other_Noun":
            continue
        g_fd = g[g["archetype_6"] == "1_Mkt_FD_China"]
        g_us = g[g["archetype_6"] == "3_Mkt_True_US"]
        g_dom = g[g["archetype_6"].isin(["5_Omnichannel", "6_Brick_and_Mortar"])]
        if len(g_fd) >= 8 and len(g_dom) >= 8:
            pv_fd = float(g_fd["photo_verify"].mean())
            pv_dom = float(g_dom["photo_verify"].mean())
            noun_rows.append({
                "fine_noun": noun,
                "n_fd_china": len(g_fd),
                "n_mkt_us": len(g_us),
                "n_domestic": len(g_dom),
                "pv_fd_china": round(pv_fd, 4),
                "pv_mkt_us": round(float(g_us["photo_verify"].mean()), 4) if len(g_us) > 0 else None,
                "pv_domestic": round(pv_dom, 4),
                "gap_fd_minus_dom": round(pv_fd - pv_dom, 4),
                "webmail_fd_china": round(float(g_fd["free_webmail"].mean()), 4),
                "webmail_domestic": round(float(g_dom["free_webmail"].mean()), 4),
            })
    noun_rows.sort(key=lambda x: x["n_fd_china"], reverse=True)
    print("\n  Fine-Product-Noun Head-to-Head (FD_China vs Domestic B&M/Omni, 2022-2026):", flush=True)
    for nr in noun_rows[:10]:
        print(
            f"    {nr['fine_noun']:24s}: FD_CN={nr['pv_fd_china']*100:5.1f}% (n={nr['n_fd_china']:2d}) vs "
            f"Dom={nr['pv_domestic']*100:5.1f}% (n={nr['n_domestic']:2d}) | Gap={nr['gap_fd_minus_dom']*100:+5.1f} pp",
            flush=True,
        )

    # 2C. Traceability & Cross-Border Regulatory Coordination Collapse (UPC & Inconjunctions)
    reg_upc = run_sat(d22_reg, "has_upc", seed=5201)
    reg_inconj = run_sat(d22_reg, "has_inconjunction", seed=5202)
    print(
        f"\n  Traceability FE (2022-2026): has_upc FD_CN={reg_upc['terms']['a_mkt_fd_cn']['beta']:+.4f} "
        f"(t={reg_upc['terms']['a_mkt_fd_cn']['t']:+.2f}, pWCB={reg_upc['terms']['a_mkt_fd_cn']['p_wcb']:.3f}) | "
        f"has_inconjunction FD_CN={reg_inconj['terms']['a_mkt_fd_cn']['beta']:+.4f} "
        f"(t={reg_inconj['terms']['a_mkt_fd_cn']['t']:+.2f}, pWCB={reg_inconj['terms']['a_mkt_fd_cn']['p_wcb']:.3f})",
        flush=True,
    )

    # 2D. 2022 -> 2026 Pioneer -> Domestic Diffusion Curves & Annual Linear Trend Tests
    diffusion_annual = []
    for yr in range(2022, 2027):
        gy = d22_all[d22_all["year"] == yr]
        row_d: dict[str, Any] = {"year": int(yr), "n_all": len(gy), "pv_all": round(float(gy["photo_verify"].mean()), 4)}
        for arch in ARCH_ORDER:
            ga = gy[gy["archetype_6"] == arch]
            row_d[f"n_{arch}"] = len(ga)
            row_d[f"pv_{arch}"] = round(float(ga["photo_verify"].mean()), 4) if len(ga) > 0 else None
            row_d[f"pm_{arch}"] = round(float(ga["physical_mutilate"].mean()), 4) if len(ga) > 0 else None
        diffusion_annual.append(row_d)

    diffusion_slopes = {}
    for arch in ["1_Mkt_FD_China", "3_Mkt_True_US", "4_DTC_Online_Only", "5_Omnichannel", "6_Brick_and_Mortar"]:
        ga = d22_all[d22_all["archetype_6"] == arch].copy()
        ga["yr_idx"] = ga["year"] - 2022
        X_tr, n_tr = build_full_rank_design(ga, ["yr_idx"], [])
        fit_tr = fit_cr1_ols(ga["photo_verify"].to_numpy(), X_tr, n_tr, ga["firm_cluster"].astype(str).to_numpy())
        diffusion_slopes[arch] = {
            "n": fit_tr["n"],
            "pv_2022": round(float(ga[ga["year"] == 2022]["photo_verify"].mean()), 4),
            "pv_2026": round(float(ga[ga["year"] == 2026]["photo_verify"].mean()), 4),
            "annual_slope_pp": round(fit_tr["params"]["yr_idx"]["beta"], 4),
            "se": round(fit_tr["params"]["yr_idx"]["se"], 4),
            "t": round(fit_tr["params"]["yr_idx"]["t"], 2),
            "p": fit_tr["params"]["yr_idx"]["p"],
        }

    # 2E. Domestic Brick-and-Mortar Diffusion Decomposition (China-Made vs Non-China & Price < $100 vs >= $100)
    bm_all = d22_all[d22_all["archetype_6"] == "6_Brick_and_Mortar"].copy()
    bm_all["yr_idx"] = bm_all["year"] - 2022
    bm_diffusion_decomp = {}
    for seg_lbl, seg_mask in [
        ("BM_Price_lt_100", bm_all["price"].notna() & (bm_all["price"] < 100.0)),
        ("BM_Price_ge_100", bm_all["price"].notna() & (bm_all["price"] >= 100.0)),
        ("BM_Made_in_China", bm_all["is_china_mfr"] == 1),
        ("BM_Non_China_Mfr", bm_all["is_china_mfr"] == 0),
    ]:
        gs = bm_all[seg_mask].copy()
        X_s, n_s = build_full_rank_design(gs, ["yr_idx"], [])
        fit_s = fit_cr1_ols(gs["photo_verify"].to_numpy(), X_s, n_s, gs["firm_cluster"].astype(str).to_numpy())
        bm_diffusion_decomp[seg_lbl] = {
            "n": len(gs),
            "pv_2022": round(float(gs[gs["year"] == 2022]["photo_verify"].mean()), 4) if (gs["year"] == 2022).any() else None,
            "pv_2026": round(float(gs[gs["year"] == 2026]["photo_verify"].mean()), 4) if (gs["year"] == 2026).any() else None,
            "annual_slope_pp": round(fit_s["params"]["yr_idx"]["beta"], 4),
            "se": round(fit_s["params"]["yr_idx"]["se"], 4),
            "t": round(fit_s["params"]["yr_idx"]["t"], 2),
            "p": fit_s["params"]["yr_idx"]["p"],
        }
    print(
        f"  B&M Diffusion Decomp: Price<$100 slope={100*bm_diffusion_decomp['BM_Price_lt_100']['annual_slope_pp']:+.2f} pp/yr (t={bm_diffusion_decomp['BM_Price_lt_100']['t']:+.2f}) vs "
        f"Price>=$100 slope={100*bm_diffusion_decomp['BM_Price_ge_100']['annual_slope_pp']:+.2f} pp/yr (t={bm_diffusion_decomp['BM_Price_ge_100']['t']:+.2f}) | "
        f"ChinaMfr={100*bm_diffusion_decomp['BM_Made_in_China']['annual_slope_pp']:+.2f} vs NonChina={100*bm_diffusion_decomp['BM_Non_China_Mfr']['annual_slope_pp']:+.2f}",
        flush=True,
    )

    # =========================================================================
    # PILLAR 3: IN RE AMAZON.COM INTERMEDIARY LIABILITY SHOCK (2021Q1-2026Q3)
    # =========================================================================
    print("\n=== PILLAR 3: IN RE AMAZON.COM REGULATORY ENFORCEMENT RAMP (HAC) ===", flush=True)
    # Build quarterly panel 2021Q1-2026Q4 (clearly flagging 2026Q4 as partial: Oct 1 - Nov 19 = 50/92 days)
    d21 = df[df["year"] >= 2021].copy()
    all_qtrs = sorted(d21["yq"].unique())
    q_rows = []
    for idx_q, yq in enumerate(all_qtrs):
        gq = d21[d21["yq"] == yq]
        amz = int(gq["amazon_only_mkt"].sum())
        nonamz = int(gq["nonamazon_mkt_only"].sum())
        bm = int((gq["archetype_6"] == "6_Brick_and_Mortar").sum())
        omni = int((gq["archetype_6"] == "5_Omnichannel").sum())
        fd_cn = int((gq["archetype_6"] == "1_Mkt_FD_China").sum())
        amz_rule = int(((gq["amazon_only_mkt"] == 1) & (gq["mandatory_rule"] == 1)).sum())
        amz_gen = int(((gq["amazon_only_mkt"] == 1) & (gq["mandatory_rule"] == 0)).sum())
        q_rows.append({
            "t_idx": idx_q,
            "yq": yq,
            "is_complete_qtr": int(yq != "2026Q4"),
            "n_total": len(gq),
            "amz_only": amz,
            "nonamz_mkt": nonamz,
            "brick_mortar": bm,
            "omnichannel": omni,
            "fd_china": fd_cn,
            "amz_mandatory_rule": amz_rule,
            "amz_general_defect": amz_gen,
            "log_amz_over_bm": float(np.log((amz + 0.5) / (bm + 0.5))),
            "log_amz_over_nonamz": float(np.log((amz + 0.5) / (nonamz + 0.5))),
            "log_amz_1p": float(np.log1p(amz)),
            "log_nonamz_1p": float(np.log1p(nonamz)),
            "log_bm_1p": float(np.log1p(bm)),
        })
    qdf_all = pd.DataFrame(q_rows)
    qdf = qdf_all[qdf_all["is_complete_qtr"] == 1].copy().reset_index(drop=True)  # 2021Q1-2026Q3 (T=23 complete quarters)

    # Helper for interrupted time series (Newey-West HAC)
    def run_its_hac(qsub: pd.DataFrame, ycol: str, cut_yq: str, maxlags: int = 4) -> dict[str, Any]:
        cut_idx = int(qsub.loc[qsub["yq"] == cut_yq, "t_idx"].iloc[0])
        t_rel = (qsub["t_idx"] - cut_idx).to_numpy(dtype=float)
        post = (qsub["t_idx"] >= cut_idx).astype(float).to_numpy()
        post_slope = post * t_rel
        X = np.column_stack([np.ones(len(qsub)), t_rel, post, post_slope])
        cols = ["const", "pre_slope", "level_jump", "slope_change"]
        res = fit_newey_west_ols(qsub[ycol].to_numpy(), X, cols, maxlags=maxlags)
        # Also test simple pre vs post mean difference (level-only model, no time trend)
        X_lvl = np.column_stack([np.ones(len(qsub)), post])
        res_lvl = fit_newey_west_ols(qsub[ycol].to_numpy(), X_lvl, ["const", "post_mean_shift"], maxlags=maxlags)
        return {
            "ycol": ycol,
            "cut_yq": cut_yq,
            "t_quarters": len(qsub),
            "maxlags": int(maxlags),
            "its_params": res["params"],
            "r2": round(res["r2"], 4),
            "simple_level_shift": res_lvl["params"]["post_mean_shift"],
        }

    # Test BOTH July 30, 2024 Distributor Decision (2024Q3) AND Jan 16, 2025 Final Remedy Order (2025Q1 & 2025Q2 ramp)
    hac_results: dict[str, Any] = {}
    for label, cut in [("jul2024_2024Q3", "2024Q3"), ("jan2025_2025Q1", "2025Q1"), ("ramp_2025Q2", "2025Q2")]:
        hac_results[label] = {
            "log_amz_over_bm_L4": run_its_hac(qdf, "log_amz_over_bm", cut, maxlags=4),
            "log_amz_over_bm_L2": run_its_hac(qdf, "log_amz_over_bm", cut, maxlags=2),
            "log_amz_over_nonamz_L4": run_its_hac(qdf, "log_amz_over_nonamz", cut, maxlags=4),
            "log_amz_1p_L4": run_its_hac(qdf, "log_amz_1p", cut, maxlags=4),
            "log_nonamz_1p_L4": run_its_hac(qdf, "log_nonamz_1p", cut, maxlags=4),
            "log_bm_1p_L4": run_its_hac(qdf, "log_bm_1p", cut, maxlags=4),
            # Ratio sensitivity including partial 2026Q4
            "log_amz_over_bm_incl_26Q4": run_its_hac(qdf_all, "log_amz_over_bm", cut, maxlags=4),
        }
        r_bm = hac_results[label]["log_amz_over_bm_L4"]["its_params"]
        r_na = hac_results[label]["log_amz_over_nonamz_L4"]["its_params"]
        print(
            f"  HAC ITS ({label}, T=23): log(Amz/BM) level={r_bm['level_jump']['beta']:+.3f} (t={r_bm['level_jump']['t']:+.2f}), "
            f"slope_chg={r_bm['slope_change']['beta']:+.3f}/qtr (t={r_bm['slope_change']['t']:+.2f}, p={r_bm['slope_change']['p']:.2e}) | "
            f"log(Amz/NonAmz) level={r_na['level_jump']['beta']:+.3f} (t={r_na['level_jump']['t']:+.2f}), "
            f"slope_chg={r_na['slope_change']['beta']:+.3f}/qtr (t={r_na['slope_change']['t']:+.2f})",
            flush=True,
        )

    # HAC Lag Sensitivity (L=1,2,3,4,6), Statutory Rule Controls (STURDY Act 2023Q4 + Reese's Law 2024Q2),
    # and Monthly HAC ITS (2021-01 to 2026-09, T=69 complete months)
    hac_lag_sensitivity = {}
    for lag_k in (1, 2, 3, 4, 6):
        r_l = run_its_hac(qdf, "log_amz_over_bm", "2024Q3", maxlags=lag_k)
        r_na_l = run_its_hac(qdf, "log_amz_over_nonamz", "2024Q3", maxlags=lag_k)
        hac_lag_sensitivity[f"L{lag_k}"] = {
            "amz_over_bm_slope": round(r_l["its_params"]["slope_change"]["beta"], 4),
            "amz_over_bm_se": round(r_l["its_params"]["slope_change"]["se"], 4),
            "amz_over_bm_t": round(r_l["its_params"]["slope_change"]["t"], 2),
            "amz_over_nonamz_slope": round(r_na_l["its_params"]["slope_change"]["beta"], 4),
            "amz_over_nonamz_t": round(r_na_l["its_params"]["slope_change"]["t"], 2),
        }

    # Explicit control for STURDY Act (eff. Sept 1, 2023 -> 2023Q4+) & Reese's Law (eff. Mar 19, 2024 -> 2024Q2+)
    cut_jul_idx = int(qdf.loc[qdf["yq"] == "2024Q3", "t_idx"].iloc[0])
    t_rel_q = (qdf["t_idx"] - cut_jul_idx).to_numpy(dtype=float)
    post_q = (qdf["t_idx"] >= cut_jul_idx).astype(float).to_numpy()
    post_sturdy = (qdf["yq"] >= "2023Q4").astype(float).to_numpy()
    post_reeses = (qdf["yq"] >= "2024Q2").astype(float).to_numpy()
    X_stat = np.column_stack([np.ones(len(qdf)), t_rel_q, post_q, post_q * t_rel_q, post_sturdy, post_reeses])
    stat_cols = ["const", "pre_slope", "level_jump", "slope_change", "post_sturdy", "post_reeses"]
    hac_statutory_controls = {
        "log_amz_over_bm_L4": fit_newey_west_ols(qdf["log_amz_over_bm"].to_numpy(), X_stat, stat_cols, maxlags=4),
        "log_amz_over_nonamz_L4": fit_newey_west_ols(qdf["log_amz_over_nonamz"].to_numpy(), X_stat, stat_cols, maxlags=4),
    }

    # Monthly complete-month HAC ITS (2021-01 through 2026-10; T=70 complete months, L=6)
    all_months = pd.period_range("2021-01", "2026-10", freq="M").strftime("%Y-%m").tolist()
    m_rows = []
    for m_idx, ym in enumerate(all_months):
        gm = d21[d21["ym"] == ym]
        amz_m = int(gm["amazon_only_mkt"].sum())
        na_m = int(gm["nonamazon_mkt_only"].sum())
        bm_m = int((gm["archetype_6"] == "6_Brick_and_Mortar").sum())
        m_rows.append({
            "m_idx": m_idx,
            "ym": ym,
            "amz_only": amz_m,
            "nonamz_mkt": na_m,
            "brick_mortar": bm_m,
            "log_amz_over_bm": float(np.log((amz_m + 0.5) / (bm_m + 0.5))),
            "log_amz_over_nonamz": float(np.log((amz_m + 0.5) / (na_m + 0.5))),
        })
    mdf = pd.DataFrame(m_rows)
    cut_m_jul = int(mdf.loc[mdf["ym"] == "2024-08", "m_idx"].iloc[0])  # First full month post-Jul 30, 2024
    tm_rel = (mdf["m_idx"] - cut_m_jul).to_numpy(dtype=float)
    pm_post = (mdf["m_idx"] >= cut_m_jul).astype(float).to_numpy()
    Xm = np.column_stack([np.ones(len(mdf)), tm_rel, pm_post, pm_post * tm_rel])
    m_cols = ["const", "pre_slope_mo", "level_jump", "slope_change_mo"]
    hac_monthly_its = {
        "t_months": len(mdf),
        "cut_ym": "2024-08",
        "maxlags": 6,
        "log_amz_over_bm_L6": fit_newey_west_ols(mdf["log_amz_over_bm"].to_numpy(), Xm, m_cols, maxlags=6),
        "log_amz_over_nonamz_L6": fit_newey_west_ols(mdf["log_amz_over_nonamz"].to_numpy(), Xm, m_cols, maxlags=6),
    }
    print(
        f"  HAC Stress Tests: Statutory-Ctrl Amz/BM slope={hac_statutory_controls['log_amz_over_bm_L4']['params']['slope_change']['beta']:+.4f}/qtr "
        f"(t={hac_statutory_controls['log_amz_over_bm_L4']['params']['slope_change']['t']:+.2f}) | "
        f"Monthly (T={len(mdf)}, L=6) Amz/BM slope={hac_monthly_its['log_amz_over_bm_L6']['params']['slope_change_mo']['beta']:+.4f}/mo "
        f"(t={hac_monthly_its['log_amz_over_bm_L6']['params']['slope_change_mo']['t']:+.2f})",
        flush=True,
    )

    # Annual Amazon-Only decomposition: Mandatory Rules vs General Defects (2021-2026)
    amz_decomp = []
    for yr in range(2021, 2027):
        gy = d21[(d21["year"] == yr) & (d21["amazon_only_mkt"] == 1)]
        gy_na = d21[(d21["year"] == yr) & (d21["nonamazon_mkt_only"] == 1)]
        amz_decomp.append({
            "year": int(yr),
            "amz_only_total": len(gy),
            "amz_mandatory_rule": int((gy["mandatory_rule"] == 1).sum()),
            "amz_general_defect": int((gy["mandatory_rule"] == 0).sum()),
            "nonamz_mkt_total": len(gy_na),
            "amz_fd_china": int((gy["archetype_6"] == "1_Mkt_FD_China").sum()),
            "amz_photo_verify_rate": round(float(gy["photo_verify"].mean()), 4) if len(gy) > 0 else None,
        })

    # Post-Jan-16-2025 Contract Persistence Test inside 1_Mkt_FD_China & Amazon_Only (2022-2026)
    d22_reg["post_jan2025"] = (pd.to_datetime(d22_reg["recall_date"]) >= pd.Timestamp("2025-01-16")).astype(int)
    fd_sub = prep_reg(d22_reg[d22_reg["archetype_6"] == "1_Mkt_FD_China"])
    fd_sub["post_jan2025"] = (pd.to_datetime(fd_sub["recall_date"]) >= pd.Timestamp("2025-01-16")).astype(int)
    amz_sub = prep_reg(d22_reg[d22_reg["amazon_only_mkt"] == 1])
    amz_sub["post_jan2025"] = (pd.to_datetime(amz_sub["recall_date"]) >= pd.Timestamp("2025-01-16")).astype(int)

    contract_persistence = {}
    for grp_name, sub_g in [("Mkt_FD_China", fd_sub), ("Amazon_Only_Mkt", amz_sub)]:
        contract_persistence[grp_name] = {}
        for ycol in ["photo_verify", "physical_mutilate", "free_webmail", "no_phone"]:
            pre_m = float(sub_g.loc[sub_g["post_jan2025"] == 0, ycol].mean())
            post_m = float(sub_g.loc[sub_g["post_jan2025"] == 1, ycol].mean())
            # FE controlling for price, units, prod_cat, hazard_cat (without YQ FE since post_jan2025 is time shock!)
            X_p, n_p = build_full_rank_design(sub_g, ["post_jan2025"], ["p_dec", "u_dec", "prod_cat", "hazard_cat"])
            fit_p = fit_cr1_ols(sub_g[ycol].to_numpy(), X_p, n_p, sub_g["firm_cluster"].astype(str).to_numpy())
            contract_persistence[grp_name][ycol] = {
                "n_pre": int((sub_g["post_jan2025"] == 0).sum()),
                "n_post": int((sub_g["post_jan2025"] == 1).sum()),
                "pre_mean": round(pre_m, 4),
                "post_mean": round(post_m, 4),
                "fe_beta": round(fit_p["params"]["post_jan2025"]["beta"], 4),
                "fe_t": round(fit_p["params"]["post_jan2025"]["t"], 2),
                "fe_p": fit_p["params"]["post_jan2025"]["p"],
            }
    # FBA Legal Scope Audit inside public CPSC Amazon-Only notices
    amz_22_all = d22_all[d22_all["amazon_only_mkt"] == 1]
    amz_21_all = d21[d21["amazon_only_mkt"] == 1]
    fba_pat = re.compile(r"fulfilled\s+by\s+amazon|\bFBA\b", re.IGNORECASE)
    fba_22_cnt = sum(1 for rid in amz_22_all["recall_id"] if fba_pat.search(json.dumps(raw_by_id[int(rid)])))
    fba_21_cnt = sum(1 for rid in amz_21_all["recall_id"] if fba_pat.search(json.dumps(raw_by_id[int(rid)])))
    fba_scope_audit = {
        "legal_order_scope": "Fulfilled-by-Amazon (FBA) third-party products",
        "public_cpsc_series_scope": (
            "Pools all Amazon-exclusive CPSC recall announcements (FBA, FBM, and other Amazon-listed 3P) "
            "because public CPSC notices almost never report fulfillment mode."
        ),
        "n_amazon_only_2022_2026": len(amz_22_all),
        "n_explicit_fba_mentions_2022_2026": int(fba_22_cnt),
        "share_explicit_fba_2022_2026": round(fba_22_cnt / max(len(amz_22_all), 1), 4),
        "n_amazon_only_2021_2026": len(amz_21_all),
        "n_explicit_fba_mentions_2021_2026": int(fba_21_cnt),
        "share_explicit_fba_2021_2026": round(fba_21_cnt / max(len(amz_21_all), 1), 4),
    }

    print(
        f"  Post-Jan-2025 Contract Persistence (Mkt_FD_China photo_verify): "
        f"Pre={contract_persistence['Mkt_FD_China']['photo_verify']['pre_mean']*100:.1f}% -> "
        f"Post={contract_persistence['Mkt_FD_China']['photo_verify']['post_mean']*100:.1f}% "
        f"(FE beta={contract_persistence['Mkt_FD_China']['photo_verify']['fe_beta']:+.4f}, "
        f"t={contract_persistence['Mkt_FD_China']['photo_verify']['fe_t']:+.2f})",
        flush=True,
    )
    print(
        f"  FBA Scope Audit: explicit FBA mention in {fba_22_cnt}/{len(amz_22_all)} "
        f"({100*fba_scope_audit['share_explicit_fba_2022_2026']:.2f}%) Amazon-Only 2022-2026 notices.",
        flush=True,
    )

    # =========================================================================
    # PILLAR 4: PUBLIC-SAFETY, HAZARDOUS-WASTE EXTERNALIZATION, & HONEST NULLS
    # =========================================================================
    print("\n=== PILLAR 4: PUBLIC SAFETY & HAZARDOUS-WASTE EXTERNALIZATION (2022-2026) ===", flush=True)

    # 4A. Mandatory Federal Safety-Rule Violations (Ultra-Saturated FE)
    reg_mandatory = run_sat(d22_reg, "mandatory_rule", seed=5401)

    # 4B. Hazardous-Waste Externalization Audit (Lithium-ion, Button-cell, Lead/Phthalates/Chemicals)
    hw_all = d22_all[d22_all["haz_waste_product"] == 1].copy()
    hw_summary = {}
    for arch in ARCH_ORDER:
        ga = hw_all[hw_all["archetype_6"] == arch]
        hw_summary[arch] = {
            "n_hazwaste_recalls": len(ga),
            "n_lithium": int(ga["haz_lithium"].sum()),
            "n_button_cell": int(ga["haz_button"].sum()),
            "n_chemical_lead": int(ga["haz_chemical_lead"].sum()),
            "share_photo_verify": round(float(ga["photo_verify"].mean()), 4) if len(ga) > 0 else None,
            "share_household_self_disposal": round(float(ga["haz_household_disposal"].mean()), 4) if len(ga) > 0 else None,
            "share_photo_self_disposal": round(float(ga["haz_photo_disposal"].mean()), 4) if len(ga) > 0 else None,
            "share_explicit_hhw_note": round(float(ga["explicit_hhw_warning"].mean()), 4) if len(ga) > 0 else None,
            "share_direct_return": round(float(ga["direct_return"].mean()), 4) if len(ga) > 0 else None,
            "units_self_disposed_total": int(ga.loc[ga["haz_household_disposal"] == 1, "units"].fillna(0).sum()),
            "units_photo_disposed_total": int(ga.loc[ga["haz_photo_disposal"] == 1, "units"].fillna(0).sum()),
        }
        print(
            f"  HazWaste {arch:20s}: N={len(ga):3d} | PhotoDisp={100*(hw_summary[arch]['share_photo_self_disposal'] or 0):5.1f}% | "
            f"SelfDisp={100*(hw_summary[arch]['share_household_self_disposal'] or 0):5.1f}% | "
            f"DirectRet={100*(hw_summary[arch]['share_direct_return'] or 0):5.1f}% | "
            f"SelfDispUnits={hw_summary[arch]['units_self_disposed_total']:,}",
            flush=True,
        )

    # Concentration & HHW-Instruction Audit inside 1_Mkt_FD_China hazardous-product consumer self-disposal (3,947,390 units)
    hw_fd_sd = hw_all[(hw_all["archetype_6"] == "1_Mkt_FD_China") & (hw_all["haz_household_disposal"] == 1)].sort_values(
        "units", ascending=False
    )
    tot_sd_units = int(hw_fd_sd["units"].fillna(0).sum())
    top2_units = int(hw_fd_sd.head(2)["units"].fillna(0).sum())
    top4_units = int(hw_fd_sd.head(4)["units"].fillna(0).sum())
    hhw_flagged = hw_fd_sd[hw_fd_sd["explicit_hhw_warning"] == 1]
    ocoopa_rem = " ".join(str(x.get("Name") or "") for x in (raw_by_id[10895].get("Remedies") or []))
    anker_rem = " ".join(str(x.get("Name") or "") for x in (raw_by_id[10311].get("Remedies") or []))
    hw_concentration_audit = {
        "n_recalls_consumer_self_disposal": len(hw_fd_sd),
        "total_units_assigned_consumer_self_disposal": tot_sd_units,
        "top2_ocoopa_anker_units": top2_units,
        "top2_ocoopa_anker_share": round(top2_units / max(tot_sd_units, 1), 4),
        "top4_units": top4_units,
        "top4_share": round(top4_units / max(tot_sd_units, 1), 4),
        "n_explicit_hhw_warning": len(hhw_flagged),
        "share_recalls_explicit_hhw_warning": round(len(hhw_flagged) / max(len(hw_fd_sd), 1), 4),
        "units_explicit_hhw_warning": int(hhw_flagged["units"].fillna(0).sum()),
        "share_units_explicit_hhw_warning": round(int(hhw_flagged["units"].fillna(0).sum()) / max(tot_sd_units, 1), 4),
        "ocoopa_10895_prohibits_ordinary_trash_and_curbside_bins": bool(
            re.search(r"do\s+not\s+throw.*trash.*recycling", ocoopa_rem, re.IGNORECASE)
        ),
        "anker_10311_requires_disposal_per_applicable_laws": bool(
            re.search(r"confirm\s+disposal.*applicable\s+laws\s+and\s+regulations", anker_rem, re.IGNORECASE)
        ),
        "top_10_recalls": [
            {
                "recall_id": int(r["recall_id"]),
                "units": int(r["units"]) if pd.notna(r["units"]) else 0,
                "share_of_total": round(float(r["units"]) / max(tot_sd_units, 1), 4) if pd.notna(r["units"]) else 0.0,
                "photo_verify": int(r["photo_verify"]),
                "explicit_hhw_warning": int(r["explicit_hhw_warning"]),
                "title_snip": str(r["title_snip"]),
            }
            for _, r in hw_fd_sd.head(10).iterrows()
        ],
    }

    # FE regression strictly inside hazardous-waste recalls (2022-2026)
    hw_reg = prep_reg(d22_reg[d22_reg["haz_waste_product"] == 1])
    reg_hw_photo = run_sat(hw_reg, "photo_verify", cat_fe=["p_dec", "u_dec", "hazard_cat", "year"], seed=5402)
    reg_hw_selfdisp = run_sat(hw_reg, "self_dispose_instructed", cat_fe=["p_dec", "u_dec", "hazard_cat", "year"], seed=5403)
    reg_hw_full_pop = run_sat(d22_reg, "haz_photo_disposal", seed=5404)

    # Breakdown by hazard waste subtype inside Mkt_FD_China vs Domestic (Omni + B&M)
    hw_subtypes = {}
    for st_name, col in [("Lithium_Ion_Battery", "haz_lithium"), ("Button_Coin_Battery", "haz_button"), ("Lead_Phthalate_Chemical", "haz_chemical_lead")]:
        g_fd = d22_all[(d22_all[col] == 1) & (d22_all["archetype_6"] == "1_Mkt_FD_China")]
        g_dom = d22_all[(d22_all[col] == 1) & (d22_all["archetype_6"].isin(["5_Omnichannel", "6_Brick_and_Mortar"]))]
        hw_subtypes[st_name] = {
            "fd_china_n": len(g_fd),
            "fd_china_photo_verify": round(float(g_fd["photo_verify"].mean()), 4) if len(g_fd) > 0 else None,
            "fd_china_self_dispose": round(float(g_fd["self_dispose_instructed"].mean()), 4) if len(g_fd) > 0 else None,
            "fd_china_direct_return": round(float(g_fd["direct_return"].mean()), 4) if len(g_fd) > 0 else None,
            "fd_china_units_self_disposed": int(g_fd.loc[g_fd["self_dispose_instructed"] == 1, "units"].fillna(0).sum()),
            "domestic_n": len(g_dom),
            "domestic_photo_verify": round(float(g_dom["photo_verify"].mean()), 4) if len(g_dom) > 0 else None,
            "domestic_self_dispose": round(float(g_dom["self_dispose_instructed"].mean()), 4) if len(g_dom) > 0 else None,
            "domestic_direct_return": round(float(g_dom["direct_return"].mean()), 4) if len(g_dom) > 0 else None,
            "domestic_units_self_disposed": int(g_dom.loc[g_dom["self_dispose_instructed"] == 1, "units"].fillna(0).sum()),
        }

    # 4C. Pre-Recall Market Duration (months_on_sale & sale_window_months)
    d22_dur = prep_reg(d22_reg[d22_reg["months_on_sale"].notna()])
    d22_dur["log_months_on_sale"] = np.log1p(d22_dur["months_on_sale"])
    dur_by_arch = {}
    for arch in ARCH_ORDER:
        ga = d22_all[(d22_all["archetype_6"] == arch) & d22_all["months_on_sale"].notna()]
        dur_by_arch[arch] = {
            "n": len(ga),
            "median_months_on_sale": round(float(ga["months_on_sale"].median()), 1) if len(ga) > 0 else None,
            "mean_months_on_sale": round(float(ga["months_on_sale"].mean()), 1) if len(ga) > 0 else None,
            "median_sale_window": round(float(ga["sale_window_months"].median()), 1) if len(ga) > 0 else None,
        }
    reg_duration = run_sat(d22_dur, "log_months_on_sale", seed=5405)

    # 4D. Honest Double-Count-Free Injury Accounting (NO broken per-100k rate ratio!)
    d22_reg["log_clean_injuries"] = np.log1p(d22_reg["clean_injuries"])
    inj_by_arch = {}
    for arch in ARCH_ORDER:
        ga = d22_all[d22_all["archetype_6"] == arch]
        inj_by_arch[arch] = {
            "n": len(ga),
            "has_injury_share": round(float(ga["has_injury"].mean()), 4),
            "has_death_share": round(float(ga["has_death"].mean()), 4),
            "total_clean_injuries": int(ga["clean_injuries"].sum()),
            "mean_clean_injuries": round(float(ga["clean_injuries"].mean()), 2),
            "p90_clean_injuries": round(float(ga["clean_injuries"].quantile(0.90)), 1),
        }
    reg_has_injury = run_sat(d22_reg, "has_injury", seed=5406)
    reg_log_injuries = run_sat(d22_reg, "log_clean_injuries", seed=5407)

    # 4E. Forensic Verification of Aug 2025 Universal CPSC direct_contact Boilerplate Edit
    d24_26 = df[df["year"] >= 2024].copy()
    d24_26["post_aug2025"] = (pd.to_datetime(d24_26["recall_date"]) >= pd.Timestamp("2025-08-01")).astype(int)
    dc_audit = {}
    for arch in ["1_Mkt_FD_China", "3_Mkt_True_US", "5_Omnichannel", "6_Brick_and_Mortar"]:
        ga = d24_26[d24_26["archetype_6"] == arch]
        pre = ga[ga["post_aug2025"] == 0]
        post = ga[ga["post_aug2025"] == 1]
        dc_audit[arch] = {
            "pre_aug2025_n": len(pre),
            "pre_aug2025_rate": round(float(pre["direct_contact"].mean()), 4) if len(pre) > 0 else None,
            "post_aug2025_n": len(post),
            "post_aug2025_rate": round(float(post["direct_contact"].mean()), 4) if len(post) > 0 else None,
        }

    print(
        f"\n  Mandatory Rules FE: FD_CN={reg_mandatory['terms']['a_mkt_fd_cn']['beta']:+.4f} "
        f"(t={reg_mandatory['terms']['a_mkt_fd_cn']['t']:+.2f}, pWCB={reg_mandatory['terms']['a_mkt_fd_cn']['p_wcb']:.3f})",
        flush=True,
    )
    print(
        f"  HazWaste-Only photo_verify FE (N={reg_hw_photo['n']}): FD_CN={reg_hw_photo['terms']['a_mkt_fd_cn']['beta']:+.4f} "
        f"(t={reg_hw_photo['terms']['a_mkt_fd_cn']['t']:+.2f}, pWCB={reg_hw_photo['terms']['a_mkt_fd_cn']['p_wcb']:.3f})",
        flush=True,
    )
    print(
        f"  Months-on-Sale FE (log1p): FD_CN={reg_duration['terms']['a_mkt_fd_cn']['beta']:+.4f} "
        f"(t={reg_duration['terms']['a_mkt_fd_cn']['t']:+.2f}, pWCB={reg_duration['terms']['a_mkt_fd_cn']['p_wcb']:.3f})",
        flush=True,
    )
    print(
        f"  Clean Injuries FE: has_injury FD_CN={reg_has_injury['terms']['a_mkt_fd_cn']['beta']:+.4f} "
        f"(t={reg_has_injury['terms']['a_mkt_fd_cn']['t']:+.2f}) | "
        f"log1p(inj) FD_CN={reg_log_injuries['terms']['a_mkt_fd_cn']['beta']:+.4f} "
        f"(t={reg_log_injuries['terms']['a_mkt_fd_cn']['t']:+.2f})",
        flush=True,
    )
    print(
        f"  Aug-2025 direct_contact boilerplate check: FD_CN {dc_audit['1_Mkt_FD_China']['pre_aug2025_rate']*100:.1f}%->{dc_audit['1_Mkt_FD_China']['post_aug2025_rate']*100:.1f}% | "
        f"B&M {dc_audit['6_Brick_and_Mortar']['pre_aug2025_rate']*100:.1f}%->{dc_audit['6_Brick_and_Mortar']['post_aug2025_rate']*100:.1f}%",
        flush=True,
    )

    payload = {
        "pillar2": {
            "platform_table_2022_2026": platform_table,
            "platform_amazon_vs_nonamazon_fe": plat_reg,
            "fine_noun_head_to_head": noun_rows,
            "traceability_upc_fe": reg_upc,
            "coordination_inconjunction_fe": reg_inconj,
            "diffusion_annual_2022_2026": diffusion_annual,
            "diffusion_slopes_2022_2026": diffusion_slopes,
            "bm_diffusion_decomposition": bm_diffusion_decomp,
        },
        "pillar3": {
            "quarterly_series_2021Q1_2026Q4": q_rows,
            "hac_its_results": hac_results,
            "hac_lag_sensitivity_2024Q3": hac_lag_sensitivity,
            "hac_statutory_rule_controls_2024Q3": hac_statutory_controls,
            "hac_monthly_its_2021_2026": hac_monthly_its,
            "annual_amazon_decomposition": amz_decomp,
            "post_jan2025_contract_persistence": contract_persistence,
            "fba_scope_audit": fba_scope_audit,
        },
        "pillar4": {
            "mandatory_rule_fe": reg_mandatory,
            "hazwaste_by_archetype": hw_summary,
            "hazwaste_concentration_audit": hw_concentration_audit,
            "hazwaste_subtypes": hw_subtypes,
            "hazwaste_photo_verify_fe": reg_hw_photo,
            "hazwaste_self_dispose_fe": reg_hw_selfdisp,
            "haz_photo_disposal_full_pop_fe": reg_hw_full_pop,
            "duration_by_archetype": dur_by_arch,
            "duration_log_fe": reg_duration,
            "injuries_clean_by_archetype": inj_by_arch,
            "has_injury_fe": reg_has_injury,
            "log_clean_injuries_fe": reg_log_injuries,
            "aug2025_direct_contact_boilerplate_audit": dc_audit,
        },
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[DONE STEP 5] Saved {OUT_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
