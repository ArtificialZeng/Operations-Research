"""Step 9 (v4 Submission Revision):
  1. Verifiable N=150 stratified remedy-duty & Amazon-channel coding audit
     (tables/table_remedy_duty_coding_audit.csv) stratified across channel x
     year (2022-2026) x rare remedy clauses, explicitly benchmarking Jugader
     (9924), UVIPC (10148), Anker (10311), OCOOPA (10895), and TADAKAZU (10317).
  2. Group-specific parser error rates (FP/FN with exact Clopper-Pearson 95%
     binomial CIs) separately for cross-border China-direct (1_Mkt_FD_China)
     vs. U.S.-entity (3_Mkt_True_US) notices, plus Rogan-Gladen point
     adjustments and bounded misclassification sensitivity intervals.
  3. Complete side-by-side channel regressions across ALL channel definitions:
     - All-Channel 2022-2026 Census (N=1,822, G=1,414; plus R7 >=$100 & R7b Strict Durables >=$100)
     - Def 1: Broad Online-Marketplace Mentioning Amazon (legacy amazon_only_mkt, CS N=391, 38 cells)
     - Def 2a: Excl. Other Flagged 3P Platforms Benchmark (rebuilt CS N=313, 34 cells)
     - Def 2b: Verbatim Strict Amazon-Exclusive (zero other platforms/DTC/stores, rebuilt CS N=236, 25 cells; full N=386)
     - Def 3: Multi-Channel Online Including Amazon (full N=138; underpowered CS N=55 routed to Appendix)
     across all disaggregated remedy duties (photo_language, photo_mandatory,
     direct_return, physical_destruction, physically_disabled, permanent_marking,
     photo_only_no_action, destruction_proof, photo_and_physical_action).
  4. Validated v3/v4 hazardous-product notice coverage (3,947,390 affected units,
     54/67 full-notice HHW warnings covering 3,910,951 units, 67.34% OCOOPA+Anker
     concentration) and In re Amazon.com institutional case-study sensitivity
     under both broad amazon_only_mkt and verbatim strict_amazon_exclusive.

Honesty Disclosure: The N=150 audit is an automated rule-plus-author structured
audit (verbatim text inspected line-by-line by the author against frozen
parser_lib.py outputs). Independent double-blind multi-coder human adjudication
and matched CPSC compliance progress reports remain required to extend from
notice-level written duties to realized operational fulfillment rates.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

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
AUDIT_OUT_CSV = BASE_DIR / "tables" / "table_remedy_duty_coding_audit.csv"
OUT_JSON = BASE_DIR / "results" / "09_v4_channel_remedy_audit.json"

GROUP_FD = "1_Mkt_FD_China"
GROUP_US = "3_Mkt_True_US"

ARCH_INDICATORS = [
    "a_mkt_fd_cn",
    "a_mkt_fd_noncn",
    "a_mkt_true_us",
    "a_dtc_online",
    "a_omnichannel",
]

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
NONDURABLE_RESIDUAL_TITLE_PAT = (
    r"\b(?:blanket|bedding|sheet|sheets|pillow|pillows|quilt|comforter|duvet|towel|towels|"
    r"rug|rugs|carpet|throw|throws|curtain|curtains|sleep\s+sack|mattress\s+pad|"
    r"cosmetic|cosmetics|skincare|lotion|cream|shampoo|conditioner|perfume|fragrance|"
    r"makeup|wipe|wipes|personal\s+care|sunscreen|serum|soap|"
    r"beverage|beverages|supplement|supplements|vitamin|vitamins|formula|candy|snack|"
    r"essential\s+oil|detergent|pesticide|fertilizer|solvent|lubricant|candle|wax|"
    r"apparel|clothing|garment|garments|shirt|shirts|sweater|sweaters|sweatshirt|sweatshirts|"
    r"hoodie|hoodies|jacket|jackets|coat|coats|dress|dresses|skirt|skirts|pants|jeans|"
    r"robe|robes|pajama|pajamas|sleepwear|nightgown|nightgowns|boot|boots|sandal|sandals|shoe|shoes)\b"
)

V4_OUTCOMES: list[tuple[str, str]] = [
    ("photo_language", "Photo evidence mentioned or offered (literal wording)"),
    ("photo_mandatory", "Mandatory photo evidence (no non-photo alternative)"),
    ("direct_return", "Direct physical return option"),
    ("physical_destruction", "Explicit physical destruction / cutting / disassembly"),
    ("physically_disabled", "Product physically disabled (action or destruction proof)"),
    ("permanent_marking", "Permanent marking / defacing instruction"),
    ("photo_only_no_action", "Photo-only (no physical destruction or marking)"),
    ("destruction_proof", "Explicit phrase: proof/evidence of destruction"),
    ("photo_and_physical_action", "Photo and physical-action text co-occur"),
]

# Line-by-line verbatim-text adjudications on all 150 stratified audit notices
# (seed=20261128). Every override below reflects direct inspection of verbatim
# CPSC JSON Retailers and Remedies text against frozen parser_lib.py outputs.
AUDIT_OVERRIDES_150: dict[int, dict[str, Any]] = {
    9213: {
        "audit_duty_bearer": "firm_or_retailer_led",
        "audit_adjudication_note": (
            "Firm/technician arranges battery replacement and disposal ('Eguana Technologies will arrange "
            "for all recalled lithium-ion batteries to be properly replaced and disposed of'); parser falsely "
            "assigned consumer_action_required via generic 'disposed of' trigger."
        ),
    },
    9426: {
        "audit_has_alternative_path": 1,
        "audit_photo_mandatory": 0,
        "audit_proof_status": "optional_or_alternative_proof",
        "audit_adjudication_note": (
            "Multi-sentence alternative path missed by sentence-local parser: 'return them to any HomeGoods... "
            "Alternately, consumers can contact TJX for instructions on how to submit a photo'."
        ),
    },
    9430: {
        "audit_physically_disabled": 1,
        "audit_permanent_marking": 1,
        "audit_adjudication_note": (
            "FN on physically_disabled and permanent_marking: passive phrasing 'with the nets cut and the "
            "handles initialed and dated' missed active-verb destruction and marking patterns."
        ),
    },
    9432: {
        "audit_direct_return": 1,
        "audit_adjudication_note": (
            "FN on direct_return: 'instructions on how to return the Meic AC power adapter' omitted explicit "
            "return destination noun in sentence."
        ),
    },
    9445: {
        "audit_has_alternative_path": 1,
        "audit_photo_mandatory": 0,
        "audit_proof_status": "optional_or_alternative_proof",
        "audit_adjudication_note": (
            "Multi-sentence store-return alternative missed by sentence-local parser: 'upload a photo... "
            "Consumers may also return their shoes to the place where purchased'."
        ),
    },
    9460: {
        "audit_permanent_marking": 1,
        "audit_duty_bearer": "shared_consumer_and_firm",
        "audit_adjudication_note": (
            "FN on permanent_marking ('initials and the date written in marker' omitted word 'permanent'); "
            "shared duty because receipt or website email suffices for post-Jan 2021 purchases."
        ),
    },
    9585: {
        "audit_permanent_marking": 1,
        "audit_adjudication_note": (
            "FN on permanent_marking: 'initials and the date written in marker' omitted word 'permanent'."
        ),
    },
    9591: {
        "audit_physically_disabled": 1,
        "audit_adjudication_note": (
            "FN on physically_disabled: 'instructions to disable their battery back-up' used possessive "
            "'their' rather than 'the/it/them'."
        ),
    },
    9736: {
        "audit_physically_disabled": 1,
        "audit_direct_return": 1,
        "audit_duty_bearer": "shared_consumer_and_firm",
        "audit_adjudication_note": (
            "FN on physically_disabled and direct_return: 'instructions on how to disable all product "
            "functionality or return the product' offers choice between disablement and return."
        ),
    },
    9835: {
        "audit_permanent_marking": 1,
        "audit_adjudication_note": (
            "FN on permanent_marking: 'marking the affected door with a specific case number' used noun "
            "'door' outside fixed marking-object list."
        ),
    },
    10054: {
        "audit_has_alternative_path": 0,
        "audit_photo_mandatory": 1,
        "audit_proof_status": "mandatory_proof",
        "audit_adjudication_note": (
            "FP on proof_alternative_path: 'send a photo of the disposed bed rail, along with a statement... "
            "or an Amazon purchase receipt' makes statement-or-receipt optional while keeping photo mandatory."
        ),
    },
    10064: {
        "audit_amazon_channel": "strict_amazon_exclusive",
        "audit_adjudication_note": (
            "Channel FP from CPSC source typo 'Online exclusively atwww.Amazon.com' (missing space after "
            "'at'); verbatim text states exclusive Amazon.com sale."
        ),
    },
    10108: {
        "audit_direct_return": 1,
        "audit_adjudication_note": (
            "FN on direct_return: 'request the firm to pick up the bed crown or request a prepaid FedEx "
            "shipping label to return the item' placed carrier name 'FedEx' inside prepaid-label phrase."
        ),
    },
    10187: {
        "audit_physically_disabled": 1,
        "audit_adjudication_note": (
            "FN on physically_disabled: 'provide photos of the destroyed product' uses past-participle "
            "adjective 'destroyed' without active destruction verb."
        ),
    },
    10238: {
        "audit_physically_disabled": 1,
        "audit_adjudication_note": (
            "FN on physically_disabled: 'provide photos of the destroyed product' uses past-participle "
            "adjective 'destroyed' without active destruction verb."
        ),
    },
    10269: {
        "audit_photo_language": 1,
        "audit_photo_mandatory": 1,
        "audit_proof_status": "mandatory_proof",
        "audit_physically_disabled": 1,
        "audit_adjudication_note": (
            "FN on photo_language and physically_disabled: 'email the Amazon order number and a photo "
            "showing the remote was destroyed by the consumer' split 'photo' from 'email' and used passive 'was destroyed'."
        ),
    },
    10459: {
        "audit_direct_return": 1,
        "audit_adjudication_note": (
            "FN on direct_return: 'coordinate a free pick up of the recalled chair' is firm-collected physical retrieval."
        ),
    },
    10478: {
        "audit_permanent_marking": 1,
        "audit_adjudication_note": (
            "FN on permanent_marking: 'clearly mark the product container with \"DO NOT USE\"' inserted "
            "modifier 'product' before 'container'."
        ),
    },
    10571: {
        "audit_physically_disabled": 0,
        "audit_adjudication_note": (
            "FP on physically_disabled: notice writes 'destroy the toy by writing \"RECALLED\" with permanent "
            "marker', which marks rather than physically disabling the product."
        ),
    },
    10619: {
        "audit_permanent_marking": 1,
        "audit_adjudication_note": (
            "FN on permanent_marking: '\"RECALLED\" printed on the container' phrased marking passively."
        ),
    },
    10639: {
        "audit_physically_disabled": 1,
        "audit_adjudication_note": (
            "FN on physically_disabled: 'cut the USB cable' used noun 'cable' outside 'cord/wire' list."
        ),
    },
    10783: {
        "audit_direct_return": 1,
        "audit_adjudication_note": (
            "FN on direct_return: 'instructions on how to return the recalled ATVs, which includes free ATV "
            "pick up and transportation'."
        ),
    },
    10934: {
        "audit_has_alternative_path": 0,
        "audit_photo_mandatory": 1,
        "audit_proof_status": "mandatory_proof",
        "audit_adjudication_note": (
            "FP on proof_alternative_path: 'email their order number or bar code number, if available, along "
            "with a photo' makes order/barcode optional while keeping the disposal photo mandatory."
        ),
    },
    10963: {
        "audit_permanent_marking": 1,
        "audit_adjudication_note": (
            "FN on permanent_marking: 'label the box \"RECALLED\"' before HHW drop-off."
        ),
    },
}

BENCHMARK_NOTES: dict[int, str] = {
    9924: (
        "Benchmark edge case (Jugader 24-199): optional alternative 'photo of the cable and the trolley OR "
        "their online purchase order number' for free repair kit; correctly excluded from mandatory photo destruction."
    ),
    10148: (
        "Benchmark edge case (UVIPC 25-122): 'submit proof of destruction to obtain a full refund' with ZERO "
        "literal photo wording; correctly captured by destruction_proof_without_photo=1 and physically_disabled=1."
    ),
    10311: (
        "Benchmark edge case (Anker 25-338, 1.158M units): multi-channel online ('Anker, Amazon, Newegg and Ebay'), "
        "permanent marking + photo + disposal confirmation (not physically disabled); full-notice HHW warning=1."
    ),
    10895: (
        "Benchmark edge case (OCOOPA 26-659, 1.500M units): multi-channel online ('Amazon.com, Ocoopa.com, Ocoopa.net "
        "and Walmart.com'), permanent marking + photo + explicit HHW prohibition of trash/curbside bins."
    ),
    10317: (
        "Benchmark edge case (TADAKAZU 25-345): strict Amazon-exclusive ('Exclusively on Amazon'), physical cutting "
        "+ photo; sole standalone 'FBA' token appears inside product model-name suffix, explicit_fba=0."
    ),
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def clopper_pearson_ci(k: int, n: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact two-sided Clopper-Pearson binomial confidence interval for k/n."""
    if n <= 0:
        return 0.0, 1.0
    lo = 0.0 if k == 0 else float(stats.beta.ppf(alpha / 2.0, k, n - k + 1))
    hi = 1.0 if k == n else float(stats.beta.ppf(1.0 - alpha / 2.0, k + 1, n - k))
    return lo, hi


def binary_audit_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    n = len(y_true)
    n_pos = tp + fn
    n_neg = tn + fp
    acc = (tp + tn) / n if n > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    rec = tp / n_pos if n_pos > 0 else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else (1.0 if n_pos == 0 and fp == 0 else 0.0)
    fpr = fp / n_neg if n_neg > 0 else 0.0
    fnr = fn / n_pos if n_pos > 0 else 0.0
    fpr_lo, fpr_hi = clopper_pearson_ci(fp, n_neg)
    fnr_lo, fnr_hi = clopper_pearson_ci(fn, n_pos)
    return {
        "n": n,
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
        "fpr": round(fpr, 4),
        "fpr_ci95": [round(fpr_lo, 4), round(fpr_hi, 4)],
        "fnr": round(fnr, 4),
        "fnr_ci95": [round(fnr_lo, 4), round(fnr_hi, 4)],
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
    d["fine_noun_yr"] = d["fine_noun"].astype(str) + "_" + d["year"].astype(str)
    return d


def run_fe_model(
    sub: pd.DataFrame,
    ycol: str,
    treat_cols: list[str],
    cat_fe: list[str],
    extra_num: list[str] | None = None,
    contrast_pair: tuple[str, str] | None = None,
    wcb_B: int = 999,
    seed: int = 3001,
) -> dict[str, Any]:
    num_cols = list(treat_cols) + (extra_num if extra_num is not None else ["is_china_mfr"])
    X, names = build_full_rank_design(sub, num_cols, cat_fe)
    y = sub[ycol].astype(float).to_numpy()
    cl = sub["firm_cluster"].astype(str).to_numpy()
    fit = fit_cr1_ols(y, X, names, cl)
    if fit["rank"] != fit["k"]:
        raise RuntimeError(f"Rank defect on {ycol}: {fit['rank']} != {fit['k']}")

    terms: dict[str, Any] = {}
    for idx_t, tc in enumerate(treat_cols):
        if tc in fit["params"]:
            rec = dict(fit["params"][tc])
            rec["p_wcb"] = wild_cluster_bootstrap_t(y, X, names, cl, {tc: 1.0}, B=wcb_B, seed=seed + idx_t * 17)["p_wcb"]
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


def build_stratified_remedy_audit(
    df: pd.DataFrame,
    raw_by_id: dict[int, dict[str, Any]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build deterministic N=150 stratified remedy-duty & channel audit table
    (channel x year x rare clauses) and compute overall & group-specific error rates.
    """
    d22 = df[df["year"] >= 2022].copy()
    rng = np.random.default_rng(20261128)
    picked: list[int] = []
    strata: dict[int, str] = {}

    def add_ids(ids: list[int], label: str) -> None:
        for rid in sorted(ids):
            if rid not in picked:
                picked.append(rid)
                strata[rid] = label

    def sample_strat_yr(mask: pd.Series, k: int, label: str) -> None:
        pool_df = d22.loc[mask & (~d22["recall_id"].isin(picked)), ["recall_id", "year"]].sort_values(["year", "recall_id"])
        if len(pool_df) <= k:
            add_ids([int(x) for x in pool_df["recall_id"]], label)
            return
        yrs = sorted(pool_df["year"].unique())
        by_yr = {yr: list(rng.permutation(np.sort(pool_df.loc[pool_df["year"] == yr, "recall_id"].to_numpy()))) for yr in yrs}
        chosen: list[int] = []
        while len(chosen) < k and any(by_yr.values()):
            for yr in yrs:
                if len(chosen) >= k:
                    break
                if by_yr[yr]:
                    chosen.append(int(by_yr[yr].pop(0)))
        add_ids(chosen, label)

    add_ids([9924, 10148, 10311, 10895, 10317], "Benchmark_EdgeCase")
    add_ids([int(x) for x in d22.loc[d22["amazon_channel_ambiguous"] == 1, "recall_id"]], "Rare_Ambiguous_Amazon_Channel")
    add_ids([int(x) for x in d22.loc[d22["destruction_proof_without_photo"] == 1, "recall_id"]], "Rare_DestructionProof_NoPhoto")
    sample_strat_yr(d22["proof_alternative_path"] == 1, 10, "Rare_Optional_Alternative_Proof")
    sample_strat_yr(d22["remedy_duty_4cat"] == "photo_plus_permanent_marking_only", 12, "Duty_Photo_Plus_MarkingOnly")
    sample_strat_yr(d22["remedy_duty_4cat"] == "photo_only_mandatory", 12, "Duty_PhotoOnly_Mandatory")
    sample_strat_yr(d22["haz_household_disposal"] == 1, 10, "Duty_HazWaste_SelfDisposal")
    sample_strat_yr((d22["archetype_6"] == GROUP_FD) & (d22["strict_amazon_exclusive"] == 1), 28, "FD_China_Strict_AmazonExcl")
    sample_strat_yr((d22["archetype_6"] == GROUP_FD) & (d22["multi_channel_online_with_amazon"] == 1), 12, "FD_China_MultiChannel_Online")
    sample_strat_yr((d22["archetype_6"] == GROUP_US) & (d22["strict_amazon_exclusive"] == 1), 22, "US_Entity_Strict_AmazonExcl")
    sample_strat_yr((d22["archetype_6"] == GROUP_US) & (d22["multi_channel_online_with_amazon"] == 1), 16, "US_Entity_MultiChannel_Online")
    rem_n = 150 - len(picked)
    sample_strat_yr(d22["archetype_6"].isin(["4_DTC_Online_Only", "5_Omnichannel", "6_Brick_and_Mortar"]), rem_n, "Other_Channels_DTC_Omni_BM")

    sub = d22[d22["recall_id"].isin(picked)].copy()
    sub["audit_stratum"] = sub["recall_id"].map(strata)
    sub = sub.sort_values(["audit_stratum", "year", "recall_id"]).reset_index(drop=True)

    rows = []
    for _, r in sub.iterrows():
        rid = int(r["recall_id"])
        raw_r = raw_by_id[rid]
        ret_verbatim = " || ".join(str(x.get("Name") or "").strip() for x in (raw_r.get("Retailers") or []) if str(x.get("Name") or "").strip())
        rem_verbatim = " ".join(str(x.get("Name") or "").strip() for x in (raw_r.get("Remedies") or []) if str(x.get("Name") or "").strip())
        ret_clean = " ".join(ret_verbatim.split()) or "NA"
        rem_clean = " ".join(rem_verbatim.split()) or "NA"

        row: dict[str, Any] = {
            "recall_id": rid,
            "recall_number": str(r["recall_number"]) or "NA",
            "recall_date": str(r["recall_date"])[:10],
            "year": int(r["year"]),
            "audit_stratum": str(r["audit_stratum"]),
            "archetype_6": str(r["archetype_6"]),
            "source_url": str(r["source_url"]) or "NA",
            "parser_amazon_channel": str(r["amazon_channel_3way"]),
            "audit_amazon_channel": str(r["amazon_channel_3way"]),
            "parser_photo_language": int(r["photo_language"]),
            "audit_photo_language": int(r["photo_language"]),
            "parser_proof_status": str(r["proof_status"]),
            "audit_proof_status": str(r["proof_status"]),
            "parser_has_alternative_path": int(r["proof_alternative_path"]),
            "audit_has_alternative_path": int(r["proof_alternative_path"]),
            "parser_photo_mandatory": int(r["photo_mandatory"]),
            "audit_photo_mandatory": int(r["photo_mandatory"]),
            "parser_duty_bearer": str(r["duty_bearer"]),
            "audit_duty_bearer": str(r["duty_bearer"]),
            "parser_physically_disabled": int(r["physically_disabled"]),
            "audit_physically_disabled": int(r["physically_disabled"]),
            "parser_permanent_marking": int(r["permanent_marking"]),
            "audit_permanent_marking": int(r["permanent_marking"]),
            "parser_direct_return": int(r["direct_return"]),
            "audit_direct_return": int(r["direct_return"]),
            "parser_destruction_proof_no_photo": int(r["destruction_proof_without_photo"]),
            "audit_destruction_proof_no_photo": int(r["destruction_proof_without_photo"]),
            "audit_discrepancy_fields": "no_discrepancy",
            "audit_adjudication_note": BENCHMARK_NOTES.get(
                rid,
                "Rule-plus-author verbatim inspection: all 10 coded channel and remedy-duty fields matched CPSC text.",
            ),
            "verbatim_retailers": ret_clean,
            "verbatim_remedy": rem_clean,
        }
        if rid in AUDIT_OVERRIDES_150:
            ov = AUDIT_OVERRIDES_150[rid]
            changed = []
            for k, v in ov.items():
                if k != "audit_adjudication_note":
                    row[k] = v
                    field_stem = k.replace("audit_", "")
                    if row[k] != row[f"parser_{field_stem}"]:
                        changed.append(field_stem)
                else:
                    row[k] = v
            row["audit_discrepancy_fields"] = ";".join(changed) if changed else "no_discrepancy"
        rows.append(row)

    audit_df = pd.DataFrame(rows)
    AUDIT_OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    audit_df.to_csv(AUDIT_OUT_CSV, index=False, encoding="utf-8")

    # Compute overall and group-specific error metrics!
    bin_fields = [
        "photo_language",
        "photo_mandatory",
        "has_alternative_path",
        "physically_disabled",
        "permanent_marking",
        "direct_return",
        "destruction_proof_no_photo",
    ]
    cat_fields = ["amazon_channel", "proof_status", "duty_bearer"]

    def summarize_slice(g: pd.DataFrame) -> dict[str, Any]:
        out: dict[str, Any] = {
            "n": len(g),
            "n_any_discrepancy": int((g["audit_discrepancy_fields"] != "no_discrepancy").sum()),
            "binary_fields": {},
            "categorical_fields": {},
        }
        for bf in bin_fields:
            out["binary_fields"][bf] = binary_audit_metrics(
                g[f"audit_{bf}"].astype(int).to_numpy(),
                g[f"parser_{bf}"].astype(int).to_numpy(),
            )
        for cf in cat_fields:
            n_match = int((g[f"audit_{cf}"] == g[f"parser_{cf}"]).sum())
            n_tot = len(g)
            out["categorical_fields"][cf] = {
                "n": n_tot,
                "n_match": n_match,
                "n_disagreements": n_tot - n_match,
                "exact_accuracy": round(n_match / n_tot, 4) if n_tot > 0 else 0.0,
            }
        return out

    metrics = {
        "audit_methodology": {
            "audit_type": "automated_rule_plus_author_structured_audit",
            "independent_blind_multi_coder": False,
            "n_stratified": len(audit_df),
            "seed": 20261128,
            "strata_counts": audit_df["audit_stratum"].value_counts().to_dict(),
            "year_counts": {str(k): int(v) for k, v in audit_df["year"].value_counts().sort_index().items()},
            "archetype_counts": audit_df["archetype_6"].value_counts().to_dict(),
            "audit_csv_path": "tables/table_remedy_duty_coding_audit.csv",
            "audit_csv_sha256": sha256_file(AUDIT_OUT_CSV),
            "scope_caveat": (
                "Labels reflect automated rule-plus-author structured verification against verbatim CPSC JSON text. "
                "Independent double-blind multi-coder human adjudication and matched CPSC compliance progress reports "
                "remain required to extend from notice-level written duties to realized operational fulfillment rates."
            ),
        },
        "overall": summarize_slice(audit_df),
        "by_entity_group": {
            GROUP_FD: summarize_slice(audit_df[audit_df["archetype_6"] == GROUP_FD]),
            GROUP_US: summarize_slice(audit_df[audit_df["archetype_6"] == GROUP_US]),
            "Other_Channels": summarize_slice(audit_df[~audit_df["archetype_6"].isin([GROUP_FD, GROUP_US])]),
        },
        "benchmark_edge_cases": {
            str(rid): audit_df.loc[audit_df["recall_id"] == rid].iloc[0].drop(["verbatim_remedy", "verbatim_retailers"]).to_dict()
            for rid in (9924, 10148, 10311, 10895, 10317)
        },
    }
    return audit_df, metrics


def compute_misclassification_bounds(
    beta_fe: float,
    se_fe: float,
    ci_lo_fe: float,
    ci_hi_fe: float,
    p_fd_obs: float,
    p_us_obs: float,
    err_fd: dict[str, Any],
    err_us: dict[str, Any],
) -> dict[str, Any]:
    """Propagate group-specific parser FP/FN rates (and Clopper-Pearson 95% bounds)
    into the estimated FD_China minus US_Entity channel gap.

    For binary outcome Y with observed rate p_g = (1 - beta_g)*pi_g + alpha_g*(1 - pi_g),
    the measurement-error bias in group g is b_g = alpha_g*(1 - pi_g) - beta_g*pi_g,
    and the differential bias in (FD - US) is B = b_FD - b_US.
    """
    def rg_true(p_obs: float, alpha: float, beta: float) -> float:
        denom = 1.0 - alpha - beta
        if denom <= 0.1:
            return float(np.clip(p_obs, 0.0, 1.0))
        return float(np.clip((p_obs - alpha) / denom, 0.0, 1.0))

    def diff_bias(a_fd: float, b_fd: float, a_us: float, b_us: float) -> float:
        pi_fd = rg_true(p_fd_obs, a_fd, b_fd)
        pi_us = rg_true(p_us_obs, a_us, b_us)
        bias_fd = a_fd * (1.0 - pi_fd) - b_fd * pi_fd
        bias_us = a_us * (1.0 - pi_us) - b_us * pi_us
        return bias_fd - bias_us

    a_fd, b_fd = float(err_fd["fpr"]), float(err_fd["fnr"])
    a_us, b_us = float(err_us["fpr"]), float(err_us["fnr"])
    a_fd_lo, a_fd_hi = float(err_fd["fpr_ci95"][0]), float(err_fd["fpr_ci95"][1])
    b_fd_lo, b_fd_hi = float(err_fd["fnr_ci95"][0]), float(err_fd["fnr_ci95"][1])
    a_us_lo, a_us_hi = float(err_us["fpr_ci95"][0]), float(err_us["fpr_ci95"][1])
    b_us_lo, b_us_hi = float(err_us["fnr_ci95"][0]), float(err_us["fnr_ci95"][1])

    emp_bias = diff_bias(a_fd, b_fd, a_us, b_us)
    beta_emp_adj = beta_fe - emp_bias

    # Extreme differential misclassification corners over exact 95% Clopper-Pearson box:
    # Max positive bias (pulls adjusted beta DOWN): high a_fd, low b_fd, low a_us, high b_us
    max_pos_bias = diff_bias(a_fd_hi, b_fd_lo, a_us_lo, b_us_hi)
    # Max negative bias (pulls adjusted beta UP): low a_fd, high b_fd, high a_us, low b_us
    max_neg_bias = diff_bias(a_fd_lo, b_fd_hi, a_us_hi, b_us_lo)

    pt_bound_lo = beta_fe - max_pos_bias
    pt_bound_hi = beta_fe - max_neg_bias
    joint_ci_lo = ci_lo_fe - max_pos_bias
    joint_ci_hi = ci_hi_fe - max_neg_bias

    return {
        "beta_fe": round(beta_fe, 4),
        "se_fe": round(se_fe, 4),
        "empirical_diff_bias": round(emp_bias, 4),
        "beta_empirical_adjusted": round(beta_emp_adj, 4),
        "point_misclass_bound_lo": round(pt_bound_lo, 4),
        "point_misclass_bound_hi": round(pt_bound_hi, 4),
        "joint_sampling_and_misclass_lo": round(joint_ci_lo, 4),
        "joint_sampling_and_misclass_hi": round(joint_ci_hi, 4),
        "fd_fpr_fnr": [round(a_fd, 4), round(b_fd, 4)],
        "us_fpr_fnr": [round(a_us, 4), round(b_us, 4)],
    }


def summarize_disposal_v4(df: pd.DataFrame) -> dict[str, Any]:
    haz = df.loc[df["year"].ge(2022) & df["archetype_6"].eq(GROUP_FD) & df["haz_waste_product"].eq(1)]
    screened = haz.loc[haz["haz_household_disposal"].eq(1)].sort_values("units", ascending=False)
    explicit_disp = screened.loc[screened["explicit_disposal_word"].eq(1)]
    warn_rem = screened.loc[screened["warning_remedy"].eq(1)]
    warn_full = screened.loc[screened["warning_full_notice"].eq(1)]
    tot_units = int(screened["units"].fillna(0).sum())
    top2_units = int(screened.head(2)["units"].fillna(0).sum())
    top4_units = int(screened.head(4)["units"].fillna(0).sum())
    return {
        "hazard_group_notices": len(haz),
        "screened_notices": len(screened),
        "screened_direct_return_share": round(float(haz["direct_return"].mean()), 4),
        "screened_affected_units": tot_units,
        "disposal_word_notices": len(explicit_disp),
        "disposal_word_affected_units": int(explicit_disp["units"].fillna(0).sum()),
        "warning_remedy_notices": len(warn_rem),
        "warning_remedy_affected_units": int(warn_rem["units"].fillna(0).sum()),
        "warning_full_notice_count": len(warn_full),
        "warning_full_notice_share_notices": round(len(warn_full) / max(len(screened), 1), 4),
        "warning_full_notice_affected_units": int(warn_full["units"].fillna(0).sum()),
        "warning_full_notice_share_units": round(int(warn_full["units"].fillna(0).sum()) / max(tot_units, 1), 4),
        "top2_ocoopa_anker_units": top2_units,
        "top2_ocoopa_anker_share": round(top2_units / max(tot_units, 1), 4),
        "top4_units": top4_units,
        "top4_share": round(top4_units / max(tot_units, 1), 4),
        "largest_cases": [
            {
                "recall_id": int(r["recall_id"]),
                "recall_number": str(r["recall_number"]),
                "units": int(r["units"]),
                "share_of_total": round(float(r["units"]) / max(tot_units, 1), 4),
                "amazon_channel_3way": str(r["amazon_channel_3way"]),
                "warning_remedy": int(r["warning_remedy"]),
                "warning_full_notice": int(r["warning_full_notice"]),
                "title_snip": str(r["title_snip"]),
                "source_url": str(r["source_url"]),
            }
            for _, r in screened.head(6).iterrows()
        ],
    }


def run_in_re_amazon_comparison(df: pd.DataFrame) -> dict[str, Any]:
    """Compare In re Amazon.com quarterly ITS descriptive structural acceleration
    across BOTH Broad amazon_only_mkt AND Verbatim strict_amazon_exclusive (2021Q1-2026Q3, T=23).
    """
    d21 = df[df["year"] >= 2021].copy()
    d22_cls = df[(df["year"] >= 2022) & (df["archetype_6"] != "7_Other_Unclear")].copy()
    amz_broad_22 = d22_cls[d22_cls["amazon_only_mkt"] == 1]
    amz_strict_22 = d22_cls[d22_cls["strict_amazon_exclusive"] == 1]

    all_qtrs = sorted(d21["yq"].unique())
    q_rows = []
    for idx_q, yq in enumerate(all_qtrs):
        gq = d21[d21["yq"] == yq]
        amz_b = int(gq["amazon_only_mkt"].sum())
        amz_s = int(gq["strict_amazon_exclusive"].sum())
        nonamz = int(gq["nonamazon_mkt_only"].sum())
        bm = int((gq["archetype_6"] == "6_Brick_and_Mortar").sum())
        q_rows.append({
            "t_idx": idx_q,
            "yq": yq,
            "is_complete_qtr": int(yq != "2026Q4"),
            "amz_broad": amz_b,
            "amz_strict_exclusive": amz_s,
            "nonamz_mkt": nonamz,
            "brick_mortar": bm,
            "log_broad_over_bm": float(np.log((amz_b + 0.5) / (bm + 0.5))),
            "log_strict_over_bm": float(np.log((amz_s + 0.5) / (bm + 0.5))),
            "log_strict_over_nonamz": float(np.log((amz_s + 0.5) / (nonamz + 0.5))),
        })
    qdf = pd.DataFrame(q_rows)
    qdf_comp = qdf[qdf["is_complete_qtr"] == 1].copy().reset_index(drop=True)

    def fit_its(col: str, cut_yq: str = "2024Q3", maxlags: int = 4) -> dict[str, Any]:
        cut_idx = int(qdf_comp.loc[qdf_comp["yq"] == cut_yq, "t_idx"].iloc[0])
        t_rel = (qdf_comp["t_idx"] - cut_idx).to_numpy(dtype=float)
        post = (qdf_comp["t_idx"] >= cut_idx).astype(float).to_numpy()
        X = np.column_stack([np.ones(len(qdf_comp)), t_rel, post, post * t_rel])
        res = fit_newey_west_ols(qdf_comp[col].to_numpy(), X, ["const", "pre_slope", "level_jump", "slope_change"], maxlags=maxlags)
        return {
            "series": col,
            "cut_yq": cut_yq,
            "t_quarters": len(qdf_comp),
            "maxlags": maxlags,
            "r2": round(res["r2"], 4),
            "params": res["params"],
        }

    # Annual counts 2021-2026 comparing broad vs strict_amazon_exclusive
    ann = []
    for yr in range(2021, 2027):
        gy = d21[d21["year"] == yr]
        ann.append({
            "year": int(yr),
            "amz_broad": int(gy["amazon_only_mkt"].sum()),
            "amz_strict_exclusive": int(gy["strict_amazon_exclusive"].sum()),
            "amz_multi_channel_online": int(gy["multi_channel_online_with_amazon"].sum()),
            "brick_mortar": int((gy["archetype_6"] == "6_Brick_and_Mortar").sum()),
        })

    fba_tok_rows = amz_broad_22.loc[amz_broad_22["fba_token"] == 1, ["recall_id", "recall_number", "title_snip", "source_url"]].to_dict("records")

    return {
        "fba_terminology_audit": {
            "broad_amazon_only_mkt_2022_2026": len(amz_broad_22),
            "strict_amazon_exclusive_2022_2026": len(amz_strict_22),
            "explicit_fulfilled_by_amazon_mentions": int(amz_broad_22["explicit_fba"].sum()),
            "standalone_fba_tokens": int(amz_broad_22["fba_token"].sum()),
            "fba_token_notices": fba_tok_rows,
        },
        "quarterly_series_2021Q1_2026Q4": q_rows,
        "annual_counts_2021_2026": ann,
        "hac_its_jul2024_L4": {
            "log_broad_over_bm": fit_its("log_broad_over_bm", "2024Q3", 4),
            "log_strict_over_bm": fit_its("log_strict_over_bm", "2024Q3", 4),
            "log_strict_over_nonamz": fit_its("log_strict_over_nonamz", "2024Q3", 4),
        },
        "hac_its_jan2025_L4": {
            "log_broad_over_bm": fit_its("log_broad_over_bm", "2025Q1", 4),
            "log_strict_over_bm": fit_its("log_strict_over_bm", "2025Q1", 4),
        },
    }


def main() -> int:
    raw = json.loads(RAW_JSON.read_text(encoding="utf-8"))
    raw_by_id = {int(r["RecallID"]): r for r in raw if r.get("RecallID") is not None}
    df = pd.read_csv(PARSED_CSV, low_memory=False, parse_dates=["recall_date"])
    print(f"[STEP 9 v4] Loaded {len(df):,} parsed notices.", flush=True)

    # 1. Stratified N=150 verifiable remedy-duty & channel audit
    audit_df, audit_metrics = build_stratified_remedy_audit(df, raw_by_id)
    print(
        f"  Stratified Audit (N={len(audit_df)}): any_discrepancy={audit_metrics['overall']['n_any_discrepancy']}/150 | "
        f"channel_acc={audit_metrics['overall']['categorical_fields']['amazon_channel']['exact_accuracy']:.4f} | "
        f"photo_lang_F1={audit_metrics['overall']['binary_fields']['photo_language']['f1']:.4f} | "
        f"direct_ret_F1={audit_metrics['overall']['binary_fields']['direct_return']['f1']:.4f} | "
        f"phys_dis_F1={audit_metrics['overall']['binary_fields']['physically_disabled']['f1']:.4f}",
        flush=True,
    )

    # 2. Sample flow accounting (exact counts for Figure 1 & Table 1)
    d22_all = df[df["year"] >= 2022].copy()
    d22_cls = d22_all[d22_all["archetype_6"] != "7_Other_Unclear"].copy()
    d22_reg = d22_cls[d22_cls["price"].notna() & d22_cls["units"].notna()].copy()

    cal_mask = (df["recall_date"].dt.month < 11) | ((df["recall_date"].dt.month == 11) & (df["recall_date"].dt.day <= 19))
    base_pair = df.loc[
        df["year"].ge(2022)
        & df["archetype_6"].isin([GROUP_FD, GROUP_US])
        & df["price"].notna()
        & df["units"].notna()
        & cal_mask
    ].copy()
    base_pair["fine_noun_yr"] = base_pair["fine_noun"].astype(str) + "_" + base_pair["year"].astype(str)

    # Exact contamination audit inside legacy amazon_only_mkt (both 601 classified & 391 common support)
    amz_601 = d22_cls[d22_cls["amazon_only_mkt"] == 1]
    def1_raw = base_pair[base_pair["amazon_only_mkt"] == 1].copy()
    def1_cs = def1_raw[def1_raw.groupby("fine_noun_yr")["archetype_6"].transform("nunique").eq(2)].copy()

    channel_contamination_audit = {
        "n_2022_2026_all": len(d22_all),
        "n_2022_2026_classified": len(d22_cls),
        "n_2022_2026_other_unclear": int((d22_all["archetype_6"] == "7_Other_Unclear").sum()),
        "n_2022_2026_reg_sample": len(d22_reg),
        "g_2022_2026_reg_clusters": int(d22_reg["firm_cluster"].nunique()),
        "amazon_channel_3way_all_2022_2026": d22_all["amazon_channel_3way"].value_counts().to_dict(),
        "amazon_channel_3way_classified_2022_2026": d22_cls["amazon_channel_3way"].value_counts().to_dict(),
        "amazon_channel_3way_by_archetype_2022_2026": {
            ch: d22_all.loc[d22_all["amazon_channel_3way"] == ch, "archetype_6"].value_counts().to_dict()
            for ch in sorted(d22_all["amazon_channel_3way"].unique())
        },
        "legacy_amazon_only_mkt_601_breakdown": {
            "total": len(amz_601),
            "by_3way": amz_601["amazon_channel_3way"].value_counts().to_dict(),
            "has_other_flagged_plat": int(amz_601["has_other_flagged_plat"].sum()),
            "multi_channel_online_total": int(amz_601["multi_channel_online_with_amazon"].sum()),
            "multi_channel_online_by_arch": amz_601.loc[amz_601["multi_channel_online_with_amazon"] == 1, "archetype_6"].value_counts().to_dict(),
            "strict_exclusive_by_arch": amz_601.loc[amz_601["strict_amazon_exclusive"] == 1, "archetype_6"].value_counts().to_dict(),
        },
        "legacy_cs_391_contamination": {
            "total": len(def1_cs),
            "groups": def1_cs["archetype_6"].value_counts().to_dict(),
            "other_flagged_plat_total": int(def1_cs["has_other_flagged_plat"].sum()),
            "other_flagged_plat_by_group": {
                k: int(v) for k, v in def1_cs.groupby("archetype_6")["has_other_flagged_plat"].sum().items()
            },
            "verbatim_multi_channel_total": int(def1_cs["multi_channel_with_amazon"].sum()),
            "verbatim_multi_channel_by_group": {
                k: int(v) for k, v in def1_cs.groupby("archetype_6")["multi_channel_with_amazon"].sum().items()
            },
            "verbatim_ambiguous_total": int(def1_cs["amazon_channel_ambiguous"].sum()),
            "verbatim_strict_exclusive_in_391": int(def1_cs["strict_amazon_exclusive"].sum()),
        },
    }

    # 3. Side-by-Side Regressions across ALL channel definitions!
    channel_defs: list[tuple[str, str, pd.Series]] = [
        (
            "Def1_Broad_Mkt_Mentions_Amazon",
            "Broad Online-Marketplace Mentioning Amazon (Legacy amazon_only_mkt)",
            base_pair["amazon_only_mkt"].eq(1),
        ),
        (
            "Def2a_NoOtherFlaggedPlat_Benchmark",
            "Excl. Other Flagged 3P Platforms (Reviewer N=313 Benchmark)",
            base_pair["no_other_flagged_plat_amazon"].eq(1),
        ),
        (
            "Def2b_Strict_Amazon_Exclusive_Verbatim",
            "Verbatim Strict Amazon-Exclusive (Zero Other Platforms/DTC/Stores)",
            base_pair["strict_amazon_exclusive"].eq(1),
        ),
        (
            "Def3_MultiChannel_Online_With_Amazon",
            "Multi-Channel Online Including Amazon (Other Platforms or DTC)",
            base_pair["multi_channel_online_with_amazon"].eq(1),
        ),
    ]

    channel_comparisons: dict[str, Any] = {}
    err_fd_map = audit_metrics["by_entity_group"][GROUP_FD]["binary_fields"]
    err_us_map = audit_metrics["by_entity_group"][GROUP_US]["binary_fields"]
    bound_outcomes = {"photo_language", "photo_mandatory", "direct_return", "physically_disabled", "permanent_marking"}

    print("\n=== SIDE-BY-SIDE CHANNEL DEFINITIONS (COMMON SUPPORT & FULL SUBSAMPLE) ===", flush=True)
    for dkey, dlabel, mask in channel_defs:
        raw_sub = base_pair.loc[mask].copy()
        cs_sub = raw_sub.loc[raw_sub.groupby("fine_noun_yr")["archetype_6"].transform("nunique").eq(2)].copy()
        cs_f = add_reg_features(cs_sub)
        raw_f = add_reg_features(raw_sub)

        cs_models: dict[str, Any] = {}
        raw_models: dict[str, Any] = {}
        misclass_bounds: dict[str, Any] = {}

        for ycol, ylabel in V4_OUTCOMES:
            fit_cs = run_fe_model(
                cs_f, ycol, ["a_mkt_fd_cn"],
                cat_fe=["p_dec", "u_dec", "hazard_cat", "fine_noun_yr"],
                contrast_pair=None, wcb_B=999, seed=3001,
            )
            term_cs = fit_cs["terms"]["a_mkt_fd_cn"]
            p_fd_obs = float(cs_f.loc[cs_f["archetype_6"] == GROUP_FD, ycol].mean())
            p_us_obs = float(cs_f.loc[cs_f["archetype_6"] == GROUP_US, ycol].mean())
            cs_models[ycol] = {
                "label": ylabel,
                "n": fit_cs["n"],
                "n_clusters": fit_cs["n_clusters"],
                "r2": fit_cs["r2"],
                "raw_mean_fd": round(p_fd_obs, 4),
                "raw_mean_us": round(p_us_obs, 4),
                **term_cs,
            }
            if ycol in bound_outcomes:
                misclass_bounds[ycol] = compute_misclassification_bounds(
                    term_cs["beta"], term_cs["se"], term_cs["ci_lo"], term_cs["ci_hi"],
                    p_fd_obs, p_us_obs, err_fd_map[ycol], err_us_map[ycol],
                )

            fit_raw = run_fe_model(
                raw_f, ycol, ["a_mkt_fd_cn"],
                cat_fe=["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"],
                contrast_pair=None, wcb_B=999, seed=3001,
            )
            raw_models[ycol] = {
                "label": ylabel,
                "n": fit_raw["n"],
                "n_clusters": fit_raw["n_clusters"],
                "r2": fit_raw["r2"],
                **fit_raw["terms"]["a_mkt_fd_cn"],
            }

        channel_comparisons[dkey] = {
            "label": dlabel,
            "is_underpowered_common_support": bool(len(cs_f) < 100),
            "raw_n": len(raw_f),
            "raw_groups": raw_f["archetype_6"].value_counts().to_dict(),
            "raw_clusters": int(raw_f["firm_cluster"].nunique()),
            "cs_n": len(cs_f),
            "cs_groups": cs_f["archetype_6"].value_counts().to_dict(),
            "cs_cells": int(cs_f["fine_noun_yr"].nunique()),
            "cs_clusters": int(cs_f["firm_cluster"].nunique()),
            "common_support_models": cs_models,
            "full_subsample_prodcat_yq_models": raw_models,
            "misclassification_bounds_common_support": misclass_bounds,
        }
        pl = cs_models["photo_language"]
        dr = cs_models["direct_return"]
        pd_m = cs_models["physical_destruction"]
        print(
            f"  {dkey:40s} | CS N={len(cs_f):3d} ({cs_f['fine_noun_yr'].nunique():2d} cells) | "
            f"photo={100*pl['beta']:+6.2f} pp (pWCB={pl['p_wcb']:.3f}) | "
            f"ret={100*dr['beta']:+6.2f} pp (pWCB={dr['p_wcb']:.3f}) | "
            f"phys_dest={100*pd_m['beta']:+6.2f} pp (pWCB={pd_m['p_wcb']:.3f})",
            flush=True,
        )

    # 4. Full All-Channel 2022-2026 Disaggregated Remedy Duties (N=1,822) + Strict Durables >= $100 (N=685)
    d22_reg_f = add_reg_features(d22_reg)
    hi_mask = d22_reg_f["price"] >= 100.0
    m_cat = d22_reg_f["prod_cat"].isin(NONDURABLE_PROD_CATS)
    m_noun = d22_reg_f["fine_noun"].isin(NONDURABLE_FINE_NOUNS)
    m_ttl = (
        d22_reg_f["title_snip"].fillna("")
        .str.replace(r"clothing\s+storage", "", case=False, regex=True)
        .str.contains(NONDURABLE_RESIDUAL_TITLE_PAT, case=False, regex=True)
    )
    strict_dur_f = add_reg_features(d22_reg_f[hi_mask & (~(m_cat | m_noun | m_ttl))])
    all_hi_f = add_reg_features(d22_reg_f[hi_mask])

    all_channel_disagg: dict[str, Any] = {}
    strict_dur_disagg: dict[str, Any] = {}
    all_hi_disagg: dict[str, Any] = {}
    all_channel_misclass_bounds: dict[str, Any] = {}

    for idx_y, (ycol, ylabel) in enumerate(V4_OUTCOMES):
        fit_all = run_fe_model(
            d22_reg_f, ycol, ARCH_INDICATORS,
            cat_fe=["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"],
            contrast_pair=("a_mkt_fd_cn", "a_mkt_true_us"),
            wcb_B=999, seed=4001 + idx_y * 13,
        )
        all_channel_disagg[ycol] = {"label": ylabel, **fit_all}
        if ycol in bound_outcomes:
            ct = fit_all["contrast"]
            p_fd_obs = float(d22_reg_f.loc[d22_reg_f["archetype_6"] == GROUP_FD, ycol].mean())
            p_us_obs = float(d22_reg_f.loc[d22_reg_f["archetype_6"] == GROUP_US, ycol].mean())
            all_channel_misclass_bounds[ycol] = compute_misclassification_bounds(
                ct["diff"], ct["se"], ct["ci_lo"], ct["ci_hi"],
                p_fd_obs, p_us_obs, err_fd_map[ycol], err_us_map[ycol],
            )

        if ycol in ("photo_language", "photo_mandatory", "direct_return", "physical_destruction", "permanent_marking", "photo_only_no_action"):
            strict_dur_disagg[ycol] = {
                "label": ylabel,
                **run_fe_model(
                    strict_dur_f, ycol, ARCH_INDICATORS,
                    cat_fe=["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"],
                    contrast_pair=("a_mkt_fd_cn", "a_mkt_true_us"),
                    wcb_B=999, seed=4201 + idx_y * 13,
                ),
            }
            all_hi_disagg[ycol] = {
                "label": ylabel,
                **run_fe_model(
                    all_hi_f, ycol, ARCH_INDICATORS,
                    cat_fe=["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"],
                    contrast_pair=("a_mkt_fd_cn", "a_mkt_true_us"),
                    wcb_B=999, seed=4401 + idx_y * 13,
                ),
            }

    # Strict Durables >= $100 inside Amazon channels (underpowered -> Appendix B!)
    strict_dur_amazon: dict[str, Any] = {}
    base_pair_dur = base_pair.loc[
        base_pair["price"].ge(100.0)
        & (~base_pair["prod_cat"].isin(NONDURABLE_PROD_CATS))
        & (~base_pair["fine_noun"].isin(NONDURABLE_FINE_NOUNS))
        & (
            ~base_pair["title_snip"].fillna("")
            .str.replace(r"clothing\s+storage", "", case=False, regex=True)
            .str.contains(NONDURABLE_RESIDUAL_TITLE_PAT, case=False, regex=True)
        )
    ].copy()
    for dkey, mask_col in [
        ("Def1_Broad_Mkt_Mentions_Amazon", "amazon_only_mkt"),
        ("Def2a_NoOtherFlaggedPlat_Benchmark", "no_other_flagged_plat_amazon"),
        ("Def2b_Strict_Amazon_Exclusive_Verbatim", "strict_amazon_exclusive"),
    ]:
        sub_d = base_pair_dur[base_pair_dur[mask_col] == 1].copy()
        entry: dict[str, Any] = {
            "n": len(sub_d),
            "groups": sub_d["archetype_6"].value_counts().to_dict(),
            "underpowered_note": "Small cell counts inside narrow Amazon strict-durable subsamples; reported in Supplementary Appendix B.",
        }
        if len(sub_d) >= 30 and sub_d["archetype_6"].nunique() == 2 and sub_d["archetype_6"].value_counts().min() >= 10:
            sub_df = add_reg_features(sub_d)
            entry["models_prodcat_year_fe"] = {}
            for ycol in ("photo_language", "direct_return", "physical_destruction"):
                fit_sd = run_fe_model(
                    sub_df, ycol, ["a_mkt_fd_cn"],
                    cat_fe=["hazard_cat", "year"],
                    contrast_pair=None, wcb_B=999, seed=4601,
                )
                entry["models_prodcat_year_fe"][ycol] = {
                    "n": fit_sd["n"],
                    "n_clusters": fit_sd["n_clusters"],
                    **fit_sd["terms"]["a_mkt_fd_cn"],
                }
        strict_dur_amazon[dkey] = entry

    # 5. Four-category remedy-duty distribution across 2022-2026 archetypes
    duty_4cat_summary = {}
    for grp_name, sub_g in [
        ("All_2022_2026_Classified", d22_cls),
        (GROUP_FD, d22_cls[d22_cls["archetype_6"] == GROUP_FD]),
        (GROUP_US, d22_cls[d22_cls["archetype_6"] == GROUP_US]),
        ("4_DTC_Online_Only", d22_cls[d22_cls["archetype_6"] == "4_DTC_Online_Only"]),
        ("5_Omnichannel", d22_cls[d22_cls["archetype_6"] == "5_Omnichannel"]),
        ("6_Brick_and_Mortar", d22_cls[d22_cls["archetype_6"] == "6_Brick_and_Mortar"]),
    ]:
        vc = sub_g["remedy_duty_4cat"].value_counts().to_dict()
        n_g = len(sub_g)
        duty_4cat_summary[grp_name] = {
            "n": n_g,
            "counts": {k: int(v) for k, v in vc.items()},
            "shares": {k: round(int(v) / max(n_g, 1), 4) for k, v in vc.items()},
            "proof_status_counts": {k: int(v) for k, v in sub_g["proof_status"].value_counts().to_dict().items()},
            "duty_bearer_counts": {k: int(v) for k, v in sub_g["duty_bearer"].value_counts().to_dict().items()},
        }

    # 6. Hazardous-product notice coverage & In re Amazon.com institutional case study
    disposal_v4 = summarize_disposal_v4(df)
    in_re_amazon_v4 = run_in_re_amazon_comparison(df)

    print(
        f"\n=== DISPOSAL COVERAGE ===\n"
        f"  {disposal_v4['screened_notices']}/{disposal_v4['hazard_group_notices']} notices = {disposal_v4['screened_affected_units']:,} affected units | "
        f"Top-2 OCOOPA+Anker={100*disposal_v4['top2_ocoopa_anker_share']:.2f}% | "
        f"Full-notice HHW warnings={disposal_v4['warning_full_notice_count']}/{disposal_v4['screened_notices']} ({disposal_v4['warning_full_notice_affected_units']:,} units, {100*disposal_v4['warning_full_notice_share_units']:.2f}%)",
        flush=True,
    )
    amz_s_its = in_re_amazon_v4["hac_its_jul2024_L4"]["log_strict_over_bm"]["params"]["slope_change"]
    amz_b_its = in_re_amazon_v4["hac_its_jul2024_L4"]["log_broad_over_bm"]["params"]["slope_change"]
    print(
        f"=== IN RE AMAZON.COM CASE STUDY (2024Q3 HAC L=4, T=23) ===\n"
        f"  Explicit FBA mentions={in_re_amazon_v4['fba_terminology_audit']['explicit_fulfilled_by_amazon_mentions']}/601 | "
        f"Standalone FBA token={in_re_amazon_v4['fba_terminology_audit']['standalone_fba_tokens']}/601 (TADAKAZU 10317)\n"
        f"  Broad log(Amz/BM) slope={amz_b_its['beta']:+.4f}/qtr (t={amz_b_its['t']:+.2f}) | "
        f"Strict-Exclusive log(StrictAmz/BM) slope={amz_s_its['beta']:+.4f}/qtr (t={amz_s_its['t']:+.2f})",
        flush=True,
    )

    payload = {
        "notice_universe": len(df),
        "channel_contamination_and_sample_flow": channel_contamination_audit,
        "remedy_duty_coding_audit_150": audit_metrics,
        "three_definition_channel_comparisons": channel_comparisons,
        "all_channel_disaggregated_2022_2026": all_channel_disagg,
        "all_channel_within_mkt_misclassification_bounds": all_channel_misclass_bounds,
        "all_price_ge_100_disaggregated": all_hi_disagg,
        "strict_durables_ge_100_disaggregated": strict_dur_disagg,
        "strict_durables_ge_100_amazon_subsamples": strict_dur_amazon,
        "remedy_duty_4cat_distribution_2022_2026": duty_4cat_summary,
        "hazardous_notice_coverage_v4": disposal_v4,
        "in_re_amazon_case_study_v4": in_re_amazon_v4,
    }
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\n[DONE STEP 9 v4] Saved {OUT_JSON} and {AUDIT_OUT_CSV}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
