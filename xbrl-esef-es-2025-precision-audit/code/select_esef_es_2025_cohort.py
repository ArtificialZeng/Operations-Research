"""
Outcome-Independent Deterministic Cohort Selector for Spain ESEF 2025 Original Filings.

Reads ONLY metadata from `filings-2025.json` (NEVER downloads or inspects financial values):
  - country == "ES"
  - fxo_id ends with "-ESEF-ES-0" (original version-0 ESEF filing)
  - report_url is non-null
  - Strictly ONE original filing per distinct LEI
  - Deterministic SHA-256 order: sha256("xbrl_precision_esef_es_2025_v1:" + lei)
  - Selects first N = 20 independent Spanish ESEF 2025 original reports.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib

BASE = pathlib.Path(os.environ.get("XBRL_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
EXPECTED_INDEX_SHA256 = "f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f"
COHORT_N = 20
SALT = "xbrl_precision_esef_es_2025_v1:"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    idx_p = BASE / "filings-2025.json"
    idx_sha = sha256_file(idx_p)
    assert idx_sha == EXPECTED_INDEX_SHA256, f"Index SHA mismatch: {idx_sha}"

    idx = json.loads(idx_p.read_text(encoding="utf-8"))
    entities_by_id = {e["id"]: e for e in idx.get("included", []) if e.get("type") == "entity"}

    pool = []
    seen_leis = set()
    for r in idx["data"]:
        a = r["attributes"]
        if a.get("country") != "ES":
            continue
        fxo = a.get("fxo_id") or ""
        if not fxo.endswith("-ESEF-ES-0"):
            continue
        if not a.get("report_url"):
            continue
        lei = fxo.split("-")[0]
        assert lei not in seen_leis, f"Duplicate version-0 LEI encountered: {lei}"
        seen_leis.add(lei)

        ent_ref_id = r.get("relationships", {}).get("entity", {}).get("data", {}).get("id")
        ent_obj = entities_by_id.get(ent_ref_id, {})
        ent_name = ent_obj.get("attributes", {}).get("name")
        rank_key = hashlib.sha256((SALT + lei).encode("utf-8")).hexdigest()

        pool.append({
            "selection_rank_key": rank_key,
            "lei": lei,
            "entity_name": ent_name,
            "filing_id": r["id"],
            "fxo_id": fxo,
            "period_end": a.get("period_end"),
            "report_url": a.get("report_url"),
            "json_url": a.get("json_url"),
            "package_sha256": a.get("sha256"),
            "date_added": a.get("date_added"),
            "processed": a.get("processed"),
        })

    pool.sort(key=lambda x: x["selection_rank_key"])
    selected = pool[:COHORT_N]
    assert len(selected) == COHORT_N
    assert len({x["lei"] for x in selected}) == COHORT_N

    receipt = {
        "purpose": "Outcome-independent deterministic cohort selection from XBRL International filings-2025.json (Spain ESEF 2025 original version-0 filings, one per LEI, bounded N=20).",
        "index_source_url": "https://filings.xbrl.org/indexes/filings-2025.json",
        "filings_2025_json_sha256": idx_sha,
        "selector_script_sha256": sha256_file(pathlib.Path(__file__)),
        "selection_rule": "country=='ES' & fxo_id.endswith('-ESEF-ES-0') & report_url!=None, one original filing per LEI, sorted ascending by sha256('xbrl_precision_esef_es_2025_v1:' + lei), top 20 selected before downloading or inspecting any filing.",
        "n_es_esef_v0_unique_leis_in_index": len(pool),
        "n_selected": len(selected),
        "selected_filings": selected,
    }
    out_p = BASE / "SPAIN_ESEF_2025_COHORT_20_RECEIPT.json"
    out_p.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"SELECTED {len(selected)}/{len(pool)} INDEPENDENT SPAIN ESEF 2025 LEIs -> {out_p} (sha256={sha256_file(out_p)[:16]}...)")


if __name__ == "__main__":
    main()
