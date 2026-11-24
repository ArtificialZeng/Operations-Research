"""
Download ONLY the pinned original QMSum and NarrativeQA query/qrel files (+ README)
from `dwzhu/LongEmbed` (commit `10039a580487dacecf79db69166e17ace3ede392`), verify
LFS SHA-256 hashes, and audit exact original-to-Nano query/document mapping and
strict fresh-group exclusion counts BEFORE deciding whether to proceed.
"""
from __future__ import annotations

import hashlib
import json
import re
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import pyarrow.parquet as pq

PROJ = Path(__file__).resolve().parent.parent
OUT_DIR = PROJ / "data_longembed_stage1"
OUT_DIR.mkdir(parents=True, exist_ok=True)

PINNED_REV = "10039a580487dacecf79db69166e17ace3ede392"
REPO = "dwzhu/LongEmbed"

FILES = [
    ("README.md", None),
    ("qmsum/queries.jsonl", None),
    ("qmsum/qrels.jsonl", "65a2dc5c1db95d7a0a7c0e49eb10f62d9ffd4e885c9fac84c300f00a954f22a3"),
    ("narrativeqa/queries.jsonl", None),
    ("narrativeqa/qrels.jsonl", "d498af1c2ffad0f14e6fe58ba00bd063f9e686f90fd8107d93266fa3e0fd3ddb"),
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def norm_query_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def norm_query_hash(s: str) -> str:
    return hashlib.sha256(norm_query_text(s).encode("utf-8")).hexdigest()


def download_files() -> Dict[str, Any]:
    receipt_files = []
    for rel_path, expected_lfs_sha in FILES:
        url = f"https://huggingface.co/datasets/{REPO}/resolve/{PINNED_REV}/{rel_path}"
        dest = OUT_DIR / rel_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            req = urllib.request.Request(url, headers={"User-Agent": "hakari-stage1-audit/1.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = resp.read()
            dest.write_bytes(data)
        else:
            data = dest.read_bytes()
        h = sha256_bytes(data)
        if expected_lfs_sha is not None and h != expected_lfs_sha:
            raise RuntimeError(f"SHA mismatch for {rel_path}: got {h}, expected {expected_lfs_sha}")
        receipt_files.append({
            "path": rel_path,
            "url": url,
            "bytes": len(data),
            "sha256": h,
            "verified_against_hf_lfs_oid": expected_lfs_sha is not None,
        })
    receipt = {
        "dataset_id": REPO,
        "pinned_revision": PINNED_REV,
        "scope": "Original QA query/qrel files (+ README) ONLY for qmsum and narrativeqa; corpus text kept strictly local as inert data and never republished.",
        "files": receipt_files,
    }
    (PROJ / "LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json").write_text(
        json.dumps(receipt, indent=2), encoding="utf-8"
    )
    return receipt


def audit_mapping() -> Dict[str, Any]:
    task_map = [("qmsum", "NanoQMSum"), ("narrativeqa", "NanoNarrativeQA")]
    report: Dict[str, Any] = {}

    for orig_name, nano_name in task_map:
        # Load Nano queries, qrels, corpus IDs
        nq_tbl = pq.read_table(PROJ / "data" / "queries" / f"{nano_name}-00000-of-00001.parquet")
        nano_q_ids = nq_tbl["_id"].to_pylist()
        nano_q_texts = nq_tbl["text"].to_pylist()
        nano_q_by_id = dict(zip(nano_q_ids, nano_q_texts))

        nqr_tbl = pq.read_table(PROJ / "data" / "qrels" / f"{nano_name}-00000-of-00001.parquet")
        nano_qrels = defaultdict(set)
        for qid, did in zip(nqr_tbl["query-id"].to_pylist(), nqr_tbl["corpus-id"].to_pylist()):
            nano_qrels[str(qid)].add(str(did))
        nano_pos_docs = {d for ds in nano_qrels.values() for d in ds}

        nc_tbl = pq.read_table(PROJ / "data" / "corpus" / f"{nano_name}-00000-of-00001.parquet")
        nano_corpus_ids = set(str(x) for x in nc_tbl["_id"].to_pylist())

        # Load Original LongEmbed queries & qrels
        orig_queries = [
            json.loads(line)
            for line in (OUT_DIR / orig_name / "queries.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        orig_qrels_rows = [
            json.loads(line)
            for line in (OUT_DIR / orig_name / "qrels.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        orig_q_by_id = {str(r["qid"]): str(r["text"]) for r in orig_queries}
        orig_qrels = defaultdict(set)
        for r in orig_qrels_rows:
            orig_qrels[str(r["qid"])].add(str(r["doc_id"]))

        # Check exact ID & text & qrel-doc matching for all 200 Nano queries
        id_hits = 0
        exact_text_hits = 0
        norm_hash_hits = 0
        qrel_doc_id_exact_match = 0
        sample_mismatches = []

        nano_norm_hashes = {norm_query_hash(t) for t in nano_q_texts}
        orig_by_norm_hash = defaultdict(list)
        for qid, txt in orig_q_by_id.items():
            orig_by_norm_hash[norm_query_hash(txt)].append(qid)

        # Check if Nano query IDs directly match Orig query IDs
        for nqid, ntxt in nano_q_by_id.items():
            nh = norm_query_hash(ntxt)
            if nqid in orig_q_by_id:
                id_hits += 1
                if orig_q_by_id[nqid].strip() == ntxt.strip():
                    exact_text_hits += 1
                if norm_query_hash(orig_q_by_id[nqid]) == nh:
                    norm_hash_hits += 1
                if orig_qrels.get(nqid) == nano_qrels.get(nqid):
                    qrel_doc_id_exact_match += 1
                elif len(sample_mismatches) < 5:
                    sample_mismatches.append({
                        "nqid": nqid,
                        "nano_doc": sorted(nano_qrels.get(nqid, set())),
                        "orig_doc": sorted(orig_qrels.get(nqid, set())),
                    })

        # Also check mapping by normalized query hash (in case IDs were re-indexed!)
        nano_matched_by_hash = 0
        orig_doc_to_nano_doc_via_hash = defaultdict(set)
        for nqid, ntxt in nano_q_by_id.items():
            nh = norm_query_hash(ntxt)
            matches = orig_by_norm_hash.get(nh, [])
            if matches:
                nano_matched_by_hash += 1
                for oqid in matches:
                    for od in orig_qrels.get(oqid, set()):
                        for nd in nano_qrels.get(nqid, set()):
                            orig_doc_to_nano_doc_via_hash[od].add(nd)

        orig_all_qrel_docs = {d for ds in orig_qrels.values() for d in ds}
        orig_docs_in_nano_corpus = orig_all_qrel_docs & nano_corpus_ids

        # Compute fresh candidate queries under strict exclusions:
        # Exclude ALL Nano query IDs, ALL Nano normalized query hashes, AND ALL Nano positive doc groups!
        nano_qid_set = set(nano_q_ids)
        fresh_by_doc = defaultdict(list)
        excluded_by_qid = 0
        excluded_by_qhash = 0
        excluded_by_nano_pos_doc = 0
        excluded_missing_in_nano_corpus = 0

        for r in orig_queries:
            oqid = str(r["qid"])
            otxt = str(r["text"])
            oh = norm_query_hash(otxt)
            odocs = orig_qrels.get(oqid, set())
            if not odocs:
                continue
            if oqid in nano_qid_set:
                excluded_by_qid += 1
                continue
            if oh in nano_norm_hashes:
                excluded_by_qhash += 1
                continue
            if any(d not in nano_corpus_ids for d in odocs):
                excluded_missing_in_nano_corpus += 1
                continue
            if any(d in nano_pos_docs for d in odocs):
                excluded_by_nano_pos_doc += 1
                continue
            # Require single positive doc (or record multi-doc)
            doc_key = "|".join(sorted(odocs))
            fresh_by_doc[doc_key].append(oqid)

        # Also check query-text deduplication within fresh pool
        fresh_unique_qhashes = set()
        fresh_dedup_by_doc = defaultdict(list)
        for doc_key, qlist in sorted(fresh_by_doc.items()):
            for oqid in qlist:
                oh = norm_query_hash(orig_q_by_id[oqid])
                if oh in fresh_unique_qhashes:
                    continue
                fresh_unique_qhashes.add(oh)
                fresh_dedup_by_doc[doc_key].append(oqid)

        report[nano_name] = {
            "orig_task": orig_name,
            "orig_query_count": len(orig_queries),
            "orig_qrel_rows": len(orig_qrels_rows),
            "orig_unique_qrel_docs": len(orig_all_qrel_docs),
            "nano_corpus_count": len(nano_corpus_ids),
            "nano_query_count": len(nano_q_ids),
            "nano_positive_doc_groups": len(nano_pos_docs),
            "orig_qrel_docs_present_in_nano_corpus": len(orig_docs_in_nano_corpus),
            "direct_id_overlap_with_200_nano": id_hits,
            "direct_id_exact_text_matches": exact_text_hits,
            "direct_id_norm_hash_matches": norm_hash_hits,
            "direct_id_exact_qrel_doc_matches": qrel_doc_id_exact_match,
            "nano_queries_matched_by_norm_hash": nano_matched_by_hash,
            "sample_id_doc_mismatches": sample_mismatches,
            "strict_exclusion_counts": {
                "excluded_by_nano_qid": excluded_by_qid,
                "excluded_by_nano_norm_qhash": excluded_by_qhash,
                "excluded_by_nano_pos_doc_group": excluded_by_nano_pos_doc,
                "excluded_doc_not_in_nano_corpus": excluded_missing_in_nano_corpus,
            },
            "fresh_eligible_queries_raw": sum(len(v) for v in fresh_by_doc.values()),
            "fresh_eligible_queries_dedup_text": sum(len(v) for v in fresh_dedup_by_doc.values()),
            "fresh_eligible_doc_groups": len(fresh_dedup_by_doc),
            "sample_orig_qids": [str(orig_queries[i]["qid"]) for i in range(min(5, len(orig_queries)))],
            "sample_nano_qids": nano_q_ids[:5],
            "sample_orig_qrel_docs": sorted(list(orig_all_qrel_docs))[:5],
            "sample_nano_corpus_docs": sorted(list(nano_corpus_ids))[:5],
        }
    return report


if __name__ == "__main__":
    rec = download_files()
    print("Downloaded & verified", len(rec["files"]), "files from", REPO, "@", PINNED_REV)
    rep = audit_mapping()
    print(json.dumps(rep, indent=2))
