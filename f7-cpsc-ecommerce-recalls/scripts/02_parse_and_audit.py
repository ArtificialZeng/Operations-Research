"""Step 2: Parse the complete 2000-2026 CPSC Recall Census (N = 8,386) using
frozen parser_lib.py, export data/cpsc_parsed_2000_2026.csv, and produce:
  1. Reproducible deterministic 150-recall stratified author-reviewed parser
     consistency audit (tables/table_parser_audit_150.csv +
     results/02_parser_audit_metrics.json) covering archetype_6, 7 binary
     fields (including direct_return), and 3 numeric fields.
  2. Completely disjoint fresh 50-recall 2025-2026 out-of-sample author-reviewed
     parser consistency stress-test (seed=9992026) quantifying residual
     generalization F1.

Honesty Note: In both batches, reference labels (gt_*) are initialized from
frozen parser_lib.py outputs and edited line-by-line by the author against raw
CPSC JSON text. Accordingly, these metrics constitute an author-reviewed parser
consistency audit—NOT an independent double-blind human annotation (which
remains required prior to formal journal submission).
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from parser_lib import parse_recall_record

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
RAW_JSON_PATH = BASE_DIR / "data" / "cpsc_recalls_2000_2026.json"
PARSED_CSV_PATH = BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv"
SUMMARY_JSON_PATH = BASE_DIR / "results" / "02_parse_summary.json"
AUDIT_CSV_PATH = BASE_DIR / "tables" / "table_parser_audit_150.csv"
AUDIT_METRICS_PATH = BASE_DIR / "results" / "02_parser_audit_metrics.json"


# Author-reviewed line-by-line inspection overrides against raw CPSC JSON text
# for the 150-recall stratified sample (seed=20261126) on frozen parser_lib.py.
# Note: labels are initialized from parser outputs before editing, making this
# an author-reviewed parser consistency audit rather than independent blind coding.
MANUAL_GT_OVERRIDES_150: dict[int, dict[str, Any]] = {
    # Recall 10072 (PowerBlock): sold online + commercial fitness dealers ("Advanced Exercise Equipment, Advantage Sport & Fitness...")
    10072: {
        "gt_archetype_6": "6_Brick_and_Mortar",
        "audit_note": "FN brick dealer list: named specialty fitness dealers without 'stores/dealers' keyword misclassified as DTC.",
    },
    # Recall 10629 (Surreal Brands): "Two consumers reported bruises and swelling after being struck in the arm and face"
    10629: {
        "gt_has_injury": 1,
        "gt_clean_injuries": 2,
        "audit_note": "FN injury: 'Two consumers reported bruises and swelling' missed explicit injury count pattern.",
    },
    # Recall 10736 (heat-related incidents): "14 heat-related incidents have been reported, with 13 involving first- or second-degree burns."
    10736: {
        "gt_has_injury": 1,
        "gt_clean_injuries": 13,
        "audit_note": "FN injury: 'with 13 involving first- or second-degree burns' missed count extractor.",
    },
    # Recall 10385 (Drinkmate): "including four reports resulting in lacerations, impact injuries and hearing damage"
    10385: {
        "gt_clean_injuries": 4,
        "audit_note": "Injury count undercount (1 vs 4): 'four reports resulting in lacerations' triggered fallback 1 instead of 4.",
    },
    # Recall 10637 (TheKiddoSpace): "18 reports worldwide, including one in the United States, of strong paint odor, skin irritation..."
    10637: {
        "gt_clean_injuries": 18,
        "audit_note": "Injury count discrepancy (1 U.S. vs 18 worldwide): fallback captured 1; global count is 18.",
    },
    # Recall 10134 (CLSYS International Inc., NY): verified U.S. importer + Chinese distributor, flagged shell_suspected=1
    10134: {
        "gt_archetype_6": "3_Mkt_True_US",
        "audit_note": "Verified U.S. importer on record (NY) + Chinese distributor; flagged shell_suspected=1 for sensitivity audit.",
    },
    # Recall 9475 (Liu Xianli, Staten Island, NY): verified U.S. importer + Chinese manufacturer, flagged shell_suspected=1
    9475: {
        "gt_archetype_6": "3_Mkt_True_US",
        "audit_note": "Verified U.S. storefront importer (Staten Island, NY) + Chinese manufacturer; flagged shell_suspected=1.",
    },
}

# Author-reviewed line-by-line inspection overrides on the completely disjoint
# 50-recall fresh out-of-sample 2025-2026 consistency stress-test (seed=9992026).
MANUAL_GT_OVERRIDES_OOS50: dict[int, dict[str, Any]] = {
    # Recall 10451 (3M laminators): "upload a photograph of the machine with the unplugged power cord cut"
    10451: {
        "gt_physical_mutilate": 1,
        "audit_note": "OOS FN physical_mutilate: passive participle 'unplugged power cord cut'.",
    },
    # Recall 10705 (Shymery LED lights): "disassemble and submerge all components in water"
    10705: {
        "gt_physical_mutilate": 1,
        "audit_note": "OOS FN physical_mutilate: 'submerge all components in water' (object between submerge and in water).",
    },
    # Recall 10725 (ZMC LED lights): "remove the batteries, break each component in half"
    10725: {
        "gt_physical_mutilate": 1,
        "audit_note": "OOS FN physical_mutilate: 'break each component in half' (novel object noun).",
    },
    # Recall 10769 (Can-Am ATV): "flipped the ATV, resulting in scrapes and bruises to the rider"
    10769: {
        "gt_has_injury": 1,
        "gt_clean_injuries": 1,
        "audit_note": "OOS FN injury: 'resulting in scrapes and bruises to the rider' missed explicit count.",
    },
}


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def build_stratified_150_sample(df: pd.DataFrame, raw_by_id: dict[int, dict]) -> pd.DataFrame:
    rng = np.random.default_rng(20261126)
    picked_ids: list[int] = []
    strata_labels: dict[int, str] = {}

    def sample_from(mask: pd.Series, k: int, label: str) -> None:
        pool = df.loc[mask & (~df["recall_id"].isin(picked_ids)), "recall_id"].to_numpy()
        pool = np.sort(pool)
        take = min(k, len(pool))
        if take > 0:
            chosen = rng.choice(pool, size=take, replace=False)
            for rid in sorted(int(x) for x in chosen):
                picked_ids.append(rid)
                strata_labels[rid] = label

    is_22_26 = df["year"] >= 2022
    sample_from(is_22_26 & (df["archetype_6"] == "1_Mkt_FD_China"), 28, "2022_26_Mkt_FD_China")
    sample_from(is_22_26 & (df["archetype_6"] == "2_Mkt_FD_NonChina"), 12, "2022_26_Mkt_FD_NonChina")
    sample_from(is_22_26 & (df["archetype_6"] == "3_Mkt_True_US") & (df["shell_suspected"] == 0), 16, "2022_26_Mkt_True_US_Verified")
    sample_from(is_22_26 & (df["archetype_6"] == "3_Mkt_True_US") & (df["shell_suspected"] == 1), 10, "2022_26_Mkt_US_ShellSuspected")
    sample_from(is_22_26 & (df["archetype_6"] == "4_DTC_Online_Only"), 16, "2022_26_DTC_Online_Only")
    sample_from(is_22_26 & (df["archetype_6"] == "5_Omnichannel"), 18, "2022_26_Omnichannel")
    sample_from(is_22_26 & (df["archetype_6"] == "6_Brick_and_Mortar"), 18, "2022_26_Brick_and_Mortar")
    sample_from((df["year"] == 2026) & (df["rescued_from_retailers"] == 1), 8, "Edge_2026_RetailerNestedEntity")
    sample_from(is_22_26 & (df["has_injury"] == 1) & (df["clean_injuries"] >= 2), 10, "Edge_MultiInjury_2022_26")
    sample_from(df["year"] <= 2021, 14, "Historical_2000_2021")

    if len(picked_ids) < 150:
        sample_from(is_22_26 & (df["archetype_6"] != "7_Other_Unclear"), 150 - len(picked_ids), "2022_26_TopUp")

    sub = df[df["recall_id"].isin(picked_ids)].copy()
    sub["audit_stratum"] = sub["recall_id"].map(strata_labels)
    sub = sub.sort_values(["audit_stratum", "recall_id"]).reset_index(drop=True)

    raw_ret, raw_ent, raw_rem, raw_cc, raw_inj, raw_haz = [], [], [], [], [], []
    for rid in sub["recall_id"]:
        rec = raw_by_id[int(rid)]
        raw_ret.append(" || ".join(str(x.get("Name") or "") for x in (rec.get("Retailers") or [])))
        ent_parts = []
        for fld in ("Importers", "Manufacturers", "Distributors"):
            vals = [str(x.get("Name") or "") for x in (rec.get(fld) or []) if x.get("Name")]
            if vals:
                ent_parts.append(f"{fld}: " + "; ".join(vals))
        raw_ent.append(" | ".join(ent_parts))
        raw_rem.append(" ".join(str(x.get("Name") or "") for x in (rec.get("Remedies") or [])))
        raw_cc.append(str(rec.get("ConsumerContact") or ""))
        raw_inj.append(" ".join(str(x.get("Name") or "") for x in (rec.get("Injuries") or [])))
        raw_haz.append(" ".join(str(x.get("Name") or "") for x in (rec.get("Hazards") or [])))

    sub["raw_retailers"] = raw_ret
    sub["raw_entities"] = raw_ent
    sub["raw_remedy"] = raw_rem
    sub["raw_contact"] = raw_cc
    sub["raw_injuries"] = raw_inj
    sub["raw_hazards"] = raw_haz
    return sub


def binary_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> dict[str, Any]:
    tp = int(((y_true == 1) & (y_pred == 1)).sum())
    fp = int(((y_true == 0) & (y_pred == 1)).sum())
    tn = int(((y_true == 0) & (y_pred == 0)).sum())
    fn = int(((y_true == 1) & (y_pred == 0)).sum())
    prec = tp / (tp + fp) if (tp + fp) > 0 else 1.0
    rec = tp / (tp + fn) if (tp + fn) > 0 else 1.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) > 0 else 0.0
    acc = (tp + tn) / len(y_true)
    return {
        "n": len(y_true),
        "tp": tp,
        "fp": fp,
        "tn": tn,
        "fn": fn,
        "accuracy": round(acc, 4),
        "precision": round(prec, 4),
        "recall": round(rec, 4),
        "f1": round(f1, 4),
    }


def score_audit_batch(
    audit_df: pd.DataFrame,
    overrides: dict[int, dict[str, Any]],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Attach author-reviewed parser consistency labels (initialized from parser
    outputs and edited on line-by-line inspection) and compute confusion matrices
    across all audited fields (including direct_return).
    """
    audited_fields = [
        "archetype_6",
        "photo_verify",
        "physical_mutilate",
        "direct_return",
        "free_webmail",
        "no_phone",
        "mandatory_rule",
        "has_injury",
        "clean_injuries",
        "price",
        "units",
    ]
    df_out = audit_df.copy()
    for fld in audited_fields:
        df_out[f"gt_{fld}"] = df_out[fld]
    df_out["audit_note"] = "Author-reviewed consistency check: matched raw CPSC JSON text."

    for idx, row in df_out.iterrows():
        rid = int(row["recall_id"])
        if rid in overrides:
            for k, v in overrides[rid].items():
                df_out.at[idx, k] = v

    binary_fields = (
        "photo_verify",
        "physical_mutilate",
        "direct_return",
        "free_webmail",
        "no_phone",
        "mandatory_rule",
        "has_injury",
    )
    metrics: dict[str, Any] = {
        "n_audited": len(df_out),
        "strata_counts": df_out["audit_stratum"].value_counts().to_dict() if "audit_stratum" in df_out.columns else {},
        "binary_fields": {},
    }
    for bf in binary_fields:
        y_true = df_out[f"gt_{bf}"].astype(int).to_numpy()
        y_pred = df_out[bf].astype(int).to_numpy()
        metrics["binary_fields"][bf] = binary_metrics(y_true, y_pred)

    classes = sorted(set(df_out["gt_archetype_6"].unique()) | set(df_out["archetype_6"].unique()))
    cm = {}
    f1s = []
    for c in classes:
        yt = (df_out["gt_archetype_6"] == c).astype(int).to_numpy()
        yp = (df_out["archetype_6"] == c).astype(int).to_numpy()
        m_c = binary_metrics(yt, yp)
        if yt.sum() > 0 or yp.sum() > 0:
            f1s.append(m_c["f1"])
        cm[c] = {c2: int(((df_out["gt_archetype_6"] == c) & (df_out["archetype_6"] == c2)).sum()) for c2 in classes}
    arch_acc = float((df_out["gt_archetype_6"] == df_out["archetype_6"]).mean())
    metrics["archetype_6"] = {
        "n": len(df_out),
        "exact_accuracy": round(arch_acc, 4),
        "macro_f1": round(float(np.mean(f1s)), 4),
        "n_disagreements": int((df_out["gt_archetype_6"] != df_out["archetype_6"]).sum()),
        "confusion_matrix": cm,
    }

    inj_exact = float((df_out["gt_clean_injuries"] == df_out["clean_injuries"]).mean())
    price_match = float(
        (
            (df_out["gt_price"].isna() & df_out["price"].isna())
            | (np.isclose(df_out["gt_price"].fillna(-1), df_out["price"].fillna(-2), rtol=1e-4))
        ).mean()
    )
    units_match = float(
        (
            (df_out["gt_units"].isna() & df_out["units"].isna())
            | (np.isclose(df_out["gt_units"].fillna(-1), df_out["units"].fillna(-2), rtol=1e-4))
        ).mean()
    )
    metrics["numeric_fields"] = {
        "clean_injuries_exact_acc": round(inj_exact, 4),
        "clean_injuries_n_disagreements": int((df_out["gt_clean_injuries"] != df_out["clean_injuries"]).sum()),
        "price_exact_acc": round(price_match, 4),
        "units_exact_acc": round(units_match, 4),
    }
    return df_out, metrics


def main() -> int:
    raw_records = json.loads(RAW_JSON_PATH.read_text(encoding="utf-8"))
    raw_by_id = {int(r["RecallID"]): r for r in raw_records if r.get("RecallID") is not None}

    rows = [r for r in (parse_recall_record(rec) for rec in raw_records) if r is not None]
    df = pd.DataFrame(rows)
    df.to_csv(PARSED_CSV_PATH, index=False, encoding="utf-8")
    parsed_sha = sha256_file(PARSED_CSV_PATH)

    d22 = df[df["year"] >= 2022].copy()
    d22_clean = d22[
        (d22["archetype_6"] != "7_Other_Unclear")
        & d22["price"].notna()
        & d22["units"].notna()
    ].copy()

    # 1. Primary 150-recall stratified author-reviewed parser consistency audit
    audit_raw = build_stratified_150_sample(df, raw_by_id)
    audit_scored, audit_metrics = score_audit_batch(audit_raw, MANUAL_GT_OVERRIDES_150)
    audit_metrics["audit_methodology"] = {
        "audit_type": "author_reviewed_parser_consistency_audit",
        "independent_blind_annotation": False,
        "initialization_procedure": (
            "Reference columns (gt_*) are initialized from frozen parser_lib.py outputs "
            "and subsequently edited by the author following line-by-line review of raw CPSC JSON text."
        ),
        "journal_submission_requirement": (
            "Independent double-blind human annotation of remedy categories and seller legal entities "
            "is required prior to formal journal submission."
        ),
    }

    keep_cols = [
        "recall_id", "recall_date", "year", "audit_stratum",
        "archetype_6", "gt_archetype_6",
        "photo_verify", "gt_photo_verify",
        "physical_mutilate", "gt_physical_mutilate",
        "direct_return", "gt_direct_return",
        "free_webmail", "gt_free_webmail",
        "no_phone", "gt_no_phone",
        "mandatory_rule", "gt_mandatory_rule",
        "has_injury", "gt_has_injury",
        "clean_injuries", "gt_clean_injuries",
        "price", "gt_price", "units", "gt_units",
        "shell_suspected", "rescued_from_retailers",
        "audit_note", "title_snip", "raw_retailers", "raw_entities",
    ]
    out_audit = audit_scored[keep_cols].copy()
    for sc in ("audit_note", "title_snip", "raw_retailers", "raw_entities"):
        out_audit[sc] = out_audit[sc].fillna("").astype(str).str.replace("\r", " ").str.replace("\n", " ")
    out_audit = out_audit.fillna("NA")

    AUDIT_CSV_PATH.parent.mkdir(parents=True, exist_ok=True)
    out_audit.to_csv(AUDIT_CSV_PATH, index=False, encoding="utf-8")

    # 2. Disjoint fresh 50-recall out-of-sample 2025-2026 validation stress-test
    rng_oos = np.random.default_rng(9992026)
    oos_pool = np.sort(
        df.loc[
            (df["year"] >= 2025)
            & (df["archetype_6"] != "7_Other_Unclear")
            & (~df["recall_id"].isin(audit_raw["recall_id"])),
            "recall_id",
        ].to_numpy()
    )
    oos_ids = sorted(int(x) for x in rng_oos.choice(oos_pool, size=50, replace=False))
    oos_sub = df[df["recall_id"].isin(oos_ids)].sort_values("recall_id").reset_index(drop=True)
    oos_sub["audit_stratum"] = "Fresh_OOS_2025_2026"
    _, oos_metrics = score_audit_batch(oos_sub, MANUAL_GT_OVERRIDES_OOS50)
    audit_metrics["oos_50_2025_2026"] = oos_metrics

    AUDIT_METRICS_PATH.write_text(json.dumps(audit_metrics, indent=2), encoding="utf-8")

    summary_payload = {
        "total_parsed_2000_2026": len(df),
        "parsed_csv_sha256": parsed_sha,
        "count_2022_2026_all": len(d22),
        "count_2022_2026_other_unclear": int((d22["archetype_6"] == "7_Other_Unclear").sum()),
        "count_2022_2026_clean_reg_sample": len(d22_clean),
        "firm_clusters_2022_2026_clean": int(d22_clean["firm_cluster"].nunique()),
        "rescued_from_retailers_2026": int(df[df["year"] == 2026]["rescued_from_retailers"].sum()),
        "archetype_counts_2022_2026_all": d22["archetype_6"].value_counts().to_dict(),
        "archetype_counts_2022_2026_clean": d22_clean["archetype_6"].value_counts().to_dict(),
        "other_unclear_share_2022_2026": round(float((d22["archetype_6"] == "7_Other_Unclear").mean()), 4),
        "price_nonmissing_share_2022_2026": round(float(d22["price"].notna().mean()), 4),
        "units_nonmissing_share_2022_2026": round(float(d22["units"].notna().mean()), 4),
        "months_on_sale_nonmissing_share_2022_2026": round(float(d22["months_on_sale"].notna().mean()), 4),
        "audit_sample_n": len(out_audit),
        "oos_audit_sample_n": len(oos_sub),
        "audit_csv_sha256": sha256_file(AUDIT_CSV_PATH),
    }
    SUMMARY_JSON_PATH.write_text(json.dumps(summary_payload, indent=2), encoding="utf-8")

    print(f"[DONE STEP 2] Parsed {len(df):,} recalls | Clean 2022-2026 sample: N={len(d22_clean):,} ({d22_clean['firm_cluster'].nunique():,} firm clusters)", flush=True)
    print("\n=== 150-Recall Stratified Author-Reviewed Parser Consistency Audit Metrics ===", flush=True)
    print(f"  archetype_6 (6-class): Accuracy={audit_metrics['archetype_6']['exact_accuracy']:.4f}, Macro-F1={audit_metrics['archetype_6']['macro_f1']:.4f} (disagreements={audit_metrics['archetype_6']['n_disagreements']}/150)", flush=True)
    for bf, m in audit_metrics["binary_fields"].items():
        print(f"  {bf:20s}: Acc={m['accuracy']:.4f} | Prec={m['precision']:.4f} | Rec={m['recall']:.4f} | F1={m['f1']:.4f} (TP={m['tp']}, FP={m['fp']}, TN={m['tn']}, FN={m['fn']})", flush=True)
    nf = audit_metrics["numeric_fields"]
    print(f"  clean_injuries exact: {nf['clean_injuries_exact_acc']:.4f} | price exact: {nf['price_exact_acc']:.4f} | units exact: {nf['units_exact_acc']:.4f}", flush=True)

    print("\n=== Fresh Out-of-Sample 50-Recall (2025-2026) Author-Reviewed Consistency Stress-Test ===", flush=True)
    print(f"  archetype_6 (OOS 50): Accuracy={oos_metrics['archetype_6']['exact_accuracy']:.4f} (disagreements={oos_metrics['archetype_6']['n_disagreements']}/50)", flush=True)
    for bf in ("photo_verify", "physical_mutilate", "direct_return", "has_injury"):
        m = oos_metrics["binary_fields"][bf]
        print(f"  OOS {bf:18s}: Acc={m['accuracy']:.4f} | Prec={m['precision']:.4f} | Rec={m['recall']:.4f} | F1={m['f1']:.4f}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
