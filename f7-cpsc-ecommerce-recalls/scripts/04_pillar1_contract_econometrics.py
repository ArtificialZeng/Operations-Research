"""Step 4 (Pillar 1): Complete 2000-2026 Structural Regime Emergence and
Strict-Era (2022-2026) 6-Archetype Contract-Design Econometrics.

Strict Era Discipline (Audit Fix 2):
  - photo_verify was ~0% prior to 2022. Therefore ALL primary contract-design
    and contact-infrastructure regressions run strictly on 2022-2026 (N=1,822,
    G=1,414 independent firm clusters), with zero era splicing.
  - Historical 2000-2026 annual series tracks the 27-year structural shift.
  - Exact 4-way remedy disaggregation inside photo_verify recalls separates
    photo + physical destruction, photo + marking/defacing only, photo + local
    HHW/recycling instructions only, and photo-only instructions.
  - Complete robustness battery: Product x Year clustering, Fine-Product-Noun x Year FE,
    Binomial Logit ORs, Within Refund-Only, Within Repair/Replace, Products Priced >= $100
    (all categories), Strict Durables >= $100 (excluding apparel/clothing, textiles/bedding,
    cosmetics/personal care, food/beverages, and chemical/consumable categories),
    Large-Batch (>= 10,000 units), Within Made-in-China, Mediation (free_webmail + no_phone),
    Suspected U.S. Shell-Front LLC Sensitivity, General vs. Mandatory Rules,
    Exact Stratified Permutation (B=1,000), Leave-One-Category-Out, Leave-One-Year-Out,
    and transparent era sensitivity (2021-2026, 2018-2026).
"""
from __future__ import annotations

import json
import re
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
RAW_JSON = BASE_DIR / "data" / "cpsc_recalls_2000_2026.json"
PARSED_CSV = BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv"
OUT_JSON = BASE_DIR / "results" / "04_pillar1_econometrics.json"

# Deterministic non-durable exclusion definitions for R7b_strict_durables_ge_100
# Excludes apparel/clothing, textiles/bedding, cosmetics/personal care, food/beverages,
# and chemical/consumable categories (while preserving furniture like "clothing storage units").
NONDURABLE_PROD_CATS: tuple[str, ...] = (
    "Adult_Apparel_Footwear",
    "Child_Sleepwear_Apparel",
    "Chemicals_Medicine_Packaging",
)
NONDURABLE_FINE_NOUNS: tuple[str, ...] = (
    "Adult_Apparel_Footwear",
    "Child_Apparel_Shoes",
    "Child_Sleepwear",
    "Mattress_Bedding",
    "Hair_Dryer_PersonalCare",
    "Supplement_Bottle_Chem",
)
NONDURABLE_RESIDUAL_TITLE_PAT = re.compile(
    r"\b(?:blanket|bedding|sheet|sheets|pillow|pillows|quilt|comforter|duvet|towel|towels|"
    r"rug|rugs|carpet|throw|throws|curtain|curtains|sleep\s+sack|mattress\s+pad|"
    r"cosmetic|cosmetics|skincare|lotion|cream|shampoo|conditioner|perfume|fragrance|"
    r"makeup|wipe|wipes|personal\s+care|sunscreen|serum|soap|"
    r"beverage|beverages|supplement|supplements|vitamin|vitamins|formula|candy|snack|"
    r"essential\s+oil|detergent|pesticide|fertilizer|solvent|lubricant|candle|wax|"
    r"apparel|clothing|garment|garments|shirt|shirts|sweater|sweaters|sweatshirt|sweatshirts|"
    r"hoodie|hoodies|jacket|jackets|coat|coats|dress|dresses|skirt|skirts|pants|jeans|"
    r"robe|robes|pajama|pajamas|sleepwear|nightgown|nightgowns|boot|boots|sandal|sandals|shoe|shoes)\b",
    re.IGNORECASE,
)

# Exact 4-way remedy component patterns inside photo_verify recalls
REMEDY_MARKING_PAT = re.compile(
    r"(?:permanent\s+mar?ker|indelible\s+(?:\(permanent\)\s+)?mar?ker|"
    r"writ(?:e|ing)\s+(?:in\s+permanent\s+mar?ker\s+)?[\"\'\u201c]?recall(?:ed)?|"
    r"\binitial\s+and\s+date\b|permanently\s+mark|"
    r"mark(?:ing)?\s+(?:the\s+)?(?:product|unit|item|helmet|mattress|fabric|label|charger|power\s+bank|battery|container|package|plastic\s+\w+)\s+with|"
    r"\bdeface\b)",
    re.IGNORECASE,
)
REMEDY_PHYSICAL_DESTRUCT_PAT = re.compile(
    r"(?:cut(?:ting)?\s+(?:off\s+|out\s+|through\s+|up\s+)?(?:the\s+|a\s+|an\s+)?[^\n.;]{0,55}?\b(?:cord|cords|wire|wires|plug|strap|straps|string|strings|tie|ties|drawstring|drawstrings|loop|loops|tail|pom[\s\-]poms?|fabric|cloth|padding|skirt|dress|pajamas?|nightgowns?|robes?|clothing|garment|garments|mattress|pad|cover|foam|belt|belts|tether|hose|tube|battery\s+compartment|power\s+supply|webbing|harness|handle|mesh|liner|pillow|lounger|bouncer|net|band|bands|suction\s+cups?|wick|wicks|in\s+half|into\s+(?:two|several|pieces|halves)|vertically\s+and\s+horizontally|with\s+(?:a\s+pair\s+of\s+)?scissors|large\s+[\"\'\u201c]?x[\"\'\u201d]?|an\s+[\"\'\u201c]?x[\"\'\u201d]?)\b|"
    r"\b(?:garment|product|item|unit|mattress|cord|strap|power\s+cord|robe|nightgown|pajamas?|skirt|dress|cover)\s+cut\s+(?:in\s+half|off|into)\b|"
    r"(?:render|make)\s+(?:it|them|the\s+[^\n.;]{1,35})\s+unusable|"
    r"destroy(?:ing)?\s+(?:it\b|them\b|(?:the\s+)?[a-z0-9\s\-]{1,42}\b)|"
    r"disable\s+(?:it\b|them\b|the\s+[a-z0-9\s\-]{1,35})|"
    r"disassemble\s+(?:it\b|them\b|the\s+[^\n.;]{1,35})[^\n.;]{0,75}\b(?:dispose|discard|trash|waste|photo)\b|"
    r"disassembled\s+[a-z0-9\s\-]{1,25}\s+in\s+(?:an\s+)?(?:outdoor\s+)?(?:waste|trash|garbage)|"
    r"pour(?:ing)?\s+(?:out\s+)?the\s+contents[^\n.;]{0,45}\b(?:trash|garbage|drain|sink|dispos)|"
    r"puncture|crush|smash|saw\s+(?:in\s+half|through)|dismantle\s+and\s+dispose|"
    r"submerge\s+(?:in\s+)?(?:salt\s+)?water|"
    r"break\s+(?:the\s+)?(?:product|item|unit|handle|prong|blade))",
    re.IGNORECASE,
)
REMEDY_HHW_RECYCLE_PAT = re.compile(
    r"(?:hazardous\s+waste|local\s+and\s+state\s+(?:regulations|laws|requirements)|"
    r"state\s+and\s+local\s+(?:regulations|laws|requirements)|"
    r"applicable\s+(?:local|state|federal)?\s*(?:and\s+state\s+)?(?:laws|regulations|requirements)|"
    r"municipal\s+(?:hazardous|recycling|waste)|recycling\s+(?:facility|center|location|program)|"
    r"household\s+hazardous\s+waste|\bhhw\b|"
    r"do\s+not\s+(?:throw|place|dispose)[^\n.]{0,40}(?:trash|garbage|curbside))",
    re.IGNORECASE,
)

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


def compute_photo_remedy_disaggregation(
    d22_all: pd.DataFrame,
    raw_by_id: dict[int, dict[str, Any]],
) -> dict[str, Any]:
    """Compute exact 4-way remedy disaggregation inside photo_verify=1 recalls (2022-2026),
    separating photo + physical destruction, photo + marking/defacing only,
    photo + local HHW/recycling disposal instructions only, and photo-only.
    """
    pv_df = d22_all[d22_all["photo_verify"] == 1].copy()
    records = []
    for _, row in pv_df.iterrows():
        rid = int(row["recall_id"])
        rec = raw_by_id[rid]
        rem = " ".join(str(x.get("Name") or "") for x in (rec.get("Remedies") or []))
        has_dest = int(bool(REMEDY_PHYSICAL_DESTRUCT_PAT.search(rem)))
        has_mark = int(bool(REMEDY_MARKING_PAT.search(rem)))
        has_hhw = int(bool(REMEDY_HHW_RECYCLE_PAT.search(rem)))
        has_pm = int(row["physical_mutilate"])
        if has_dest == 1:
            bucket = "photo_plus_physical_destruction"
        elif has_mark == 1:
            bucket = "photo_plus_marking_defacing_only"
        elif has_hhw == 1:
            bucket = "photo_plus_hhw_recycling_only"
        else:
            bucket = "photo_only"
        records.append({
            "recall_id": rid,
            "archetype_6": str(row["archetype_6"]),
            "physical_mutilate": has_pm,
            "has_physical_destruction": has_dest,
            "has_marking_defacing": has_mark,
            "has_hhw_recycling": has_hhw,
            "bucket_4way": bucket,
        })
    rdf = pd.DataFrame(records)

    def summarize_group(g: pd.DataFrame) -> dict[str, Any]:
        n_pv = len(g)
        if n_pv == 0:
            return {"n_photo_verify": 0}
        b_counts = g["bucket_4way"].value_counts().to_dict()
        n_pm1 = int((g["physical_mutilate"] == 1).sum())
        n_pm0 = int((g["physical_mutilate"] == 0).sum())
        n_dest = int(g["has_physical_destruction"].sum())
        n_mark = int(g["has_marking_defacing"].sum())
        n_both_dm = int(((g["has_physical_destruction"] == 1) & (g["has_marking_defacing"] == 1)).sum())
        n_hhw = int(g["has_hhw_recycling"].sum())
        return {
            "n_photo_verify": n_pv,
            "n_with_physical_mutilate": n_pm1,
            "share_with_physical_mutilate": round(n_pm1 / n_pv, 4),
            "n_without_physical_mutilate": n_pm0,
            "share_without_physical_mutilate": round(n_pm0 / n_pv, 4),
            "mutually_exclusive_4way_counts": {
                "photo_plus_physical_destruction": int(b_counts.get("photo_plus_physical_destruction", 0)),
                "photo_plus_marking_defacing_only": int(b_counts.get("photo_plus_marking_defacing_only", 0)),
                "photo_plus_hhw_recycling_only": int(b_counts.get("photo_plus_hhw_recycling_only", 0)),
                "photo_only": int(b_counts.get("photo_only", 0)),
            },
            "mutually_exclusive_4way_shares": {
                "photo_plus_physical_destruction": round(b_counts.get("photo_plus_physical_destruction", 0) / n_pv, 4),
                "photo_plus_marking_defacing_only": round(b_counts.get("photo_plus_marking_defacing_only", 0) / n_pv, 4),
                "photo_plus_hhw_recycling_only": round(b_counts.get("photo_plus_hhw_recycling_only", 0) / n_pv, 4),
                "photo_only": round(b_counts.get("photo_only", 0) / n_pv, 4),
            },
            "marginal_component_counts": {
                "any_physical_destruction": n_dest,
                "any_marking_defacing": n_mark,
                "both_destruction_and_marking": n_both_dm,
                "any_hhw_or_recycling_instruction": n_hhw,
            },
            "marginal_component_shares": {
                "any_physical_destruction": round(n_dest / n_pv, 4),
                "any_marking_defacing": round(n_mark / n_pv, 4),
                "both_destruction_and_marking": round(n_both_dm / n_pv, 4),
                "any_hhw_or_recycling_instruction": round(n_hhw / n_pv, 4),
            },
        }

    out: dict[str, Any] = {
        "all_classified_2022_2026": summarize_group(rdf),
        "by_archetype": {},
    }
    for arch in sorted(rdf["archetype_6"].unique()):
        out["by_archetype"][arch] = summarize_group(rdf[rdf["archetype_6"] == arch])
    return out


def main() -> int:
    df = pd.read_csv(PARSED_CSV, low_memory=False)
    raw_records = json.loads(RAW_JSON.read_text(encoding="utf-8"))
    raw_by_id = {int(r["RecallID"]): r for r in raw_records if r.get("RecallID") is not None}
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

    # R7: Products Priced >= $100 (All Categories — transparently noting apparel/textiles/chemicals included)
    sub_hi_p = add_reg_features(d22_reg[d22_reg["price"] >= 100.0])
    robust["R7_high_price_ge_100"] = run_saturated_spec(
        sub_hi_p, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3007
    )
    robust["R7_high_price_ge_100"]["subsample_label"] = "Products Priced >= $100 (All Categories)"
    robust["R7_high_price_ge_100"]["subsample_note"] = (
        "Filters strictly on retail price >= $100 across all 15 product categories, "
        "including apparel/footwear, child sleepwear/apparel, mattresses/bedding, "
        "personal care, and chemicals/packaging."
    )

    # R7b: Strict Durables (>= $100) — deterministically excluding apparel/clothing,
    # textiles/bedding, cosmetics/personal care, food/beverages, and chemical/consumable categories
    hi_base = d22_reg[d22_reg["price"] >= 100.0].copy()
    mask_cat_excl = hi_base["prod_cat"].isin(NONDURABLE_PROD_CATS)
    mask_noun_excl = hi_base["fine_noun"].isin(NONDURABLE_FINE_NOUNS)
    clean_title_hi = hi_base["title_snip"].fillna("").str.replace(
        r"clothing\s+storage", "", case=False, regex=True
    )
    mask_title_excl = clean_title_hi.str.contains(NONDURABLE_RESIDUAL_TITLE_PAT)
    mask_any_excl = mask_cat_excl | mask_noun_excl | mask_title_excl

    excl_df = hi_base[mask_any_excl].copy()
    sub_strict_dur = add_reg_features(hi_base[~mask_any_excl])
    robust["R7b_strict_durables_ge_100"] = run_saturated_spec(
        sub_strict_dur, "photo_verify", ARCH_INDICATORS, run_wcb=True, wcb_B=999, seed=3077
    )
    robust["R7b_strict_durables_ge_100"]["subsample_label"] = "Strict Durables (>= $100)"
    residual_only_df = hi_base[mask_title_excl & (~mask_cat_excl) & (~mask_noun_excl)]
    robust["R7b_strict_durables_ge_100"]["exclusion_audit"] = {
        "n_price_ge_100_all": len(hi_base),
        "n_excluded_total": int(mask_any_excl.sum()),
        "n_strict_durables_retained": len(sub_strict_dur),
        "excluded_prod_cats_rule": list(NONDURABLE_PROD_CATS),
        "excluded_fine_nouns_rule": list(NONDURABLE_FINE_NOUNS),
        "excluded_counts_by_prod_cat_rule": {
            cat: int((hi_base["prod_cat"] == cat).sum()) for cat in NONDURABLE_PROD_CATS
        },
        "excluded_counts_by_fine_noun_rule": {
            noun: int((hi_base["fine_noun"] == noun).sum()) for noun in NONDURABLE_FINE_NOUNS
        },
        "excluded_total_by_prod_cat": excl_df["prod_cat"].value_counts().to_dict(),
        "excluded_total_by_fine_noun": excl_df["fine_noun"].value_counts().to_dict(),
        "residual_title_regex_only_exclusions": [
            {
                "recall_id": int(r["recall_id"]),
                "prod_cat": str(r["prod_cat"]),
                "fine_noun": str(r["fine_noun"]),
                "price": float(r["price"]),
                "title_snip": str(r["title_snip"]),
            }
            for _, r in residual_only_df.iterrows()
        ],
    }

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

    # 5. Exact 4-Way Remedy Disaggregation inside photo_verify=1 recalls (2022-2026)
    remedy_disagg = compute_photo_remedy_disaggregation(d22_all, raw_by_id)
    fd_rd = remedy_disagg["by_archetype"]["1_Mkt_FD_China"]
    print("\n=== 4-WAY REMEDY DISAGGREGATION INSIDE 1_Mkt_FD_China photo_verify=1 (2022-2026) ===", flush=True)
    print(
        f"  N_photo_verify={fd_rd['n_photo_verify']} | "
        f"With physical_mutilate={fd_rd['n_with_physical_mutilate']} ({100*fd_rd['share_with_physical_mutilate']:.1f}%) | "
        f"Without physical_mutilate={fd_rd['n_without_physical_mutilate']} ({100*fd_rd['share_without_physical_mutilate']:.1f}%)",
        flush=True,
    )
    for bk, cnt in fd_rd["mutually_exclusive_4way_counts"].items():
        print(f"    {bk:36s}: {cnt:3d} ({100*fd_rd['mutually_exclusive_4way_shares'][bk]:5.1f}%)", flush=True)

    # Print crisp robustness summary
    for rk in [
        "R1_baseline_firm_cr1", "R2_prod_year_cluster", "R3_fine_noun_x_year_fe",
        "R5_within_refund_only", "R6_within_repair_replace", "R7_high_price_ge_100",
        "R7b_strict_durables_ge_100",
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
        "remedy_disaggregation_photo_verify_2022_2026": remedy_disagg,
        "main_models_2022_2026": main_models,
        "robustness_photo_verify_2022_2026": robust,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[DONE STEP 4] Saved {OUT_JSON}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
