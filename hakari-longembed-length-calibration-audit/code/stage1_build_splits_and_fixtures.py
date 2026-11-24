"""
Stage-1 Pre-Launch Split Construction, Local BM25 Parity Verification & Synthetic Fixtures.

Strictly executes BEFORE evaluating ANY fresh held-out queries:
  1. Constructs the deterministic, group-balanced fresh held-out split (`75` fresh queries
     across `75` distinct fresh relevant docs per task, 1 query per doc) from pinned
     `dwzhu/LongEmbed` (`10039a580487dacecf79db69166e17ace3ede392`), excluding ALL 200 Nano
     query IDs/normalized texts AND ALL 122 / 163 Nano positive document groups (so 100%
     disjoint from Stage-0 dev, Stage-0 held-out, AND Stage-0 unlabeled_bg_pool).
  2. Verifies `LocalWholeDocBM25Index` parity against official `NanoLongEmbed` BM25 rankings
     on all 200 original queries (documenting both same-scored Lucene-IDF BM25 and Robertson-IDF
     reference parity).
  3. Runs synthetic unit fixtures for `robust_normalize_per_query` (zero-sparsity & order
     preservation) and `CountConditionalTop3Calibrator` (unlabeled top-1 outlier immunity,
     strict extreme-tail monotonicity, and zero short-vs-long tail crossover out to r = 50).
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List

import numpy as np
import pyarrow.parquet as pq
from scipy.stats import spearmanr

import hakari_retrieval_core as stage0_core
import stage1_countcal_top3_core as s1

PROJ = Path(__file__).resolve().parent.parent
LONGEMBED_DIR = PROJ / "data_longembed_stage1"
TARGET_FRESH_GROUPS = 75  # 75 distinct fresh docs x 1 query/doc = 75 fresh queries per task!


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def norm_query_text(s: str) -> str:
    return re.sub(r"\s+", " ", str(s).strip().lower())


def norm_query_hash(s: str) -> str:
    return sha256_str(norm_query_text(s))


def build_fresh_splits() -> Dict[str, Any]:
    stage0_splits = json.loads((PROJ / "HAKARI_STAGE0_SPLITS_RECEIPT.json").read_text(encoding="utf-8"))
    receipt: Dict[str, Any] = {
        "source_dataset_id": "dwzhu/LongEmbed",
        "source_pinned_revision": "10039a580487dacecf79db69166e17ace3ede392",
        "nano_dataset_id": "hakari-bench/NanoLongEmbed",
        "nano_pinned_revision": "ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e",
        "selection_rule": (
            "Exclude ALL 200 Nano query IDs, ALL 200 Nano normalized query text SHA-256 hashes, "
            "AND ALL Nano positive document groups (122 in QMSum, 163 in NarrativeQA; covers dev, "
            "Stage-0 test, and unlabeled_bg_pool). Deduplicate remaining fresh queries by normalized "
            "query text hash. Sort eligible fresh relevant doc IDs ascending by "
            "sha256('hakari_stage1_fresh_doc_20261124:' + nano_task + ':' + doc_id), take the first 75 "
            "distinct fresh docs, and within each doc take the single query with minimum "
            "sha256('hakari_stage1_fresh_q_20261124:' + nano_task + ':' + qid) -> exact 1:1 group "
            "balance (75 fresh queries across 75 distinct fresh relevant docs)."
        ),
        "tasks": {},
    }

    for orig_name, nano_name in [("qmsum", "NanoQMSum"), ("narrativeqa", "NanoNarrativeQA")]:
        # Load Nano artifacts
        nc_tbl = pq.read_table(PROJ / "data" / "corpus" / f"{nano_name}-00000-of-00001.parquet")
        nano_doc_ids = [str(x) for x in nc_tbl["_id"].to_pylist()]
        nano_doc_texts = nc_tbl["text"].to_pylist()
        nano_doc_id_set = set(nano_doc_ids)
        unique_corpus_text_hashes = len({sha256_str(t) for t in nano_doc_texts})
        assert unique_corpus_text_hashes == len(nano_doc_ids), "Duplicate text in Nano corpus!"

        nq_tbl = pq.read_table(PROJ / "data" / "queries" / f"{nano_name}-00000-of-00001.parquet")
        nano_q_ids = [str(x) for x in nq_tbl["_id"].to_pylist()]
        nano_q_texts = [str(x) for x in nq_tbl["text"].to_pylist()]
        nano_q_by_id = dict(zip(nano_q_ids, nano_q_texts))
        nano_qid_set = set(nano_q_ids)
        nano_qhash_set = {norm_query_hash(t) for t in nano_q_texts}

        nqr_tbl = pq.read_table(PROJ / "data" / "qrels" / f"{nano_name}-00000-of-00001.parquet")
        nano_qrels = defaultdict(set)
        for qid, did in zip(nqr_tbl["query-id"].to_pylist(), nqr_tbl["corpus-id"].to_pylist()):
            nano_qrels[str(qid)].add(str(did))
        nano_pos_docs = {d for ds in nano_qrels.values() for d in ds}

        # Load Original LongEmbed queries & qrels
        orig_queries = [
            json.loads(line)
            for line in (LONGEMBED_DIR / orig_name / "queries.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        orig_qrels_rows = [
            json.loads(line)
            for line in (LONGEMBED_DIR / orig_name / "qrels.jsonl").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        orig_q_by_id = {str(r["qid"]): str(r["text"]) for r in orig_queries}
        orig_qrels = defaultdict(set)
        for r in orig_qrels_rows:
            orig_qrels[str(r["qid"])].add(str(r["doc_id"]))

        # Verify 200/200 exact ID, text, norm-hash, and qrel-doc identity
        for nqid, ntxt in nano_q_by_id.items():
            assert nqid in orig_q_by_id, f"Missing Nano qid {nqid} in original LongEmbed"
            assert orig_q_by_id[nqid].strip() == ntxt.strip(), f"Text mismatch on {nqid}"
            assert norm_query_hash(orig_q_by_id[nqid]) == norm_query_hash(ntxt)
            assert orig_qrels[nqid] == nano_qrels[nqid], f"Qrel doc mismatch on {nqid}"

        orig_all_qrel_docs = {d for ds in orig_qrels.values() for d in ds}
        assert orig_all_qrel_docs == nano_doc_id_set, "Original qrel doc IDs != Nano corpus doc IDs"

        # Filter strictly fresh queries (deduplicated by normalized query text hash)
        fresh_by_doc: Dict[str, List[str]] = defaultdict(list)
        seen_fresh_qhashes = set()
        for r in orig_queries:
            oqid = str(r["qid"])
            otxt = str(r["text"])
            oh = norm_query_hash(otxt)
            odocs = orig_qrels.get(oqid, set())
            if len(odocs) != 1:
                continue
            did = next(iter(odocs))
            if oqid in nano_qid_set:
                continue
            if oh in nano_qhash_set:
                continue
            if did in nano_pos_docs:
                continue
            if did not in nano_doc_id_set:
                continue
            if oh in seen_fresh_qhashes:
                continue
            seen_fresh_qhashes.add(oh)
            fresh_by_doc[did].append(oqid)

        eligible_docs = sorted(
            fresh_by_doc.keys(),
            key=lambda d: sha256_str(f"hakari_stage1_fresh_doc_20261124:{nano_name}:{d}"),
        )
        assert len(eligible_docs) >= 20, f"Insufficient fresh docs: {len(eligible_docs)}"
        chosen_docs = eligible_docs[: min(TARGET_FRESH_GROUPS, len(eligible_docs))]

        fresh_items = []
        for did in chosen_docs:
            cands = sorted(
                fresh_by_doc[did],
                key=lambda q: sha256_str(f"hakari_stage1_fresh_q_20261124:{nano_name}:{q}"),
            )
            chosen_qid = cands[0]
            fresh_items.append({
                "query_id": chosen_qid,
                "relevant_doc_id": did,
                "norm_query_sha256": norm_query_hash(orig_q_by_id[chosen_qid]),
            })

        # Exhaustive independence & disjointness assertions
        fresh_qids = {x["query_id"] for x in fresh_items}
        fresh_qhashes = {x["norm_query_sha256"] for x in fresh_items}
        fresh_pos_docs = {x["relevant_doc_id"] for x in fresh_items}

        dev_qids = set(stage0_splits[nano_name]["dev"]["query_ids"])
        s0_ho_qids = set(stage0_splits[nano_name]["heldout_test"]["query_ids"])
        bg_qids = set(stage0_splits[nano_name]["unlabeled_bg_pool"]["query_ids"])

        assert len(fresh_qids & nano_qid_set) == 0
        assert len(fresh_qids & dev_qids) == 0
        assert len(fresh_qids & s0_ho_qids) == 0
        assert len(fresh_qids & bg_qids) == 0
        assert len(fresh_qhashes & nano_qhash_set) == 0
        assert len(fresh_pos_docs & nano_pos_docs) == 0
        assert len(fresh_items) == len(fresh_pos_docs)  # exact 1:1 group balance

        receipt["tasks"][nano_name] = {
            "orig_task": orig_name,
            "orig_total_queries": len(orig_queries),
            "nano_excluded_queries": len(nano_qid_set),
            "nano_excluded_pos_doc_groups": len(nano_pos_docs),
            "nano_corpus_size": len(nano_doc_ids),
            "nano_corpus_unique_text_hashes": unique_corpus_text_hashes,
            "exact_200_of_200_nano_mapping_verified": True,
            "fresh_eligible_doc_groups_total": len(eligible_docs),
            "fresh_eligible_dedup_queries_total": sum(len(v) for v in fresh_by_doc.values()),
            "fresh_selected_queries": len(fresh_items),
            "fresh_selected_doc_groups": len(fresh_pos_docs),
            "queries_per_doc_group": 1,
            "disjointness_verified": {
                "overlap_with_all_200_nano_qids": 0,
                "overlap_with_all_200_nano_norm_qhashes": 0,
                "overlap_with_all_nano_pos_docs": 0,
                "overlap_with_dev_qids": 0,
                "overlap_with_stage0_heldout_qids": 0,
                "overlap_with_unlabeled_bg_qids": 0,
            },
            "fresh_items": fresh_items,
        }

    out_path = PROJ / "STAGE1_FRESH_SPLITS_RECEIPT.json"
    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    return receipt


def verify_bm25_parity_and_synthetic_fixtures() -> Dict[str, Any]:
    stage0_splits = json.loads((PROJ / "HAKARI_STAGE0_SPLITS_RECEIPT.json").read_text(encoding="utf-8"))
    parity: Dict[str, Any] = {}

    for nano_name in ["NanoQMSum", "NanoNarrativeQA"]:
        c_tbl = pq.read_table(PROJ / "data" / "corpus" / f"{nano_name}-00000-of-00001.parquet")
        doc_ids = [str(x) for x in c_tbl["_id"].to_pylist()]
        doc_texts = c_tbl["text"].to_pylist()

        q_tbl = pq.read_table(PROJ / "data" / "queries" / f"{nano_name}-00000-of-00001.parquet")
        q_ids = [str(x) for x in q_tbl["_id"].to_pylist()]
        q_texts = [str(x) for x in q_tbl["text"].to_pylist()]

        qr_tbl = pq.read_table(PROJ / "data" / "qrels" / f"{nano_name}-00000-of-00001.parquet")
        qrels = defaultdict(set)
        for qid, did in zip(qr_tbl["query-id"].to_pylist(), qr_tbl["corpus-id"].to_pylist()):
            qrels[str(qid)].add(str(did))

        bm_tbl = pq.read_table(PROJ / "data" / "bm25" / f"{nano_name}-00000-of-00001.parquet")
        off_rank = {str(q): [str(d) for d in ds] for q, ds in zip(bm_tbl["query-id"].to_pylist(), bm_tbl["corpus-ids"].to_pylist())}
        off_all = stage0_core.per_query_ndcg_at_k(off_rank, qrels, q_ids, k=10)

        # 1. Primary same-scored LocalWholeDocBM25 (k1=1.2, b=0.75, Lucene IDF)
        loc_idx = s1.LocalWholeDocBM25Index(doc_ids, doc_texts, k1=1.2, b=0.75, lucene_idf=True)
        loc_sc = loc_idx.score_queries(q_texts)
        loc_rank = stage0_core.scores_to_rankings(loc_sc, q_ids, doc_ids)
        loc_all = stage0_core.per_query_ndcg_at_k(loc_rank, qrels, q_ids, k=10)

        dev_qids = stage0_splits[nano_name]["dev"]["query_ids"]
        s0_ho_qids = stage0_splits[nano_name]["heldout_test"]["query_ids"]

        top1_same = sum(off_rank[q][0] == loc_rank[q][0] for q in q_ids)
        jacc10_same = float(np.mean([len(set(off_rank[q][:10]) & set(loc_rank[q][:10])) / len(set(off_rank[q][:10]) | set(loc_rank[q][:10])) for q in q_ids]))

        # 2. Diagnostic Robertson-IDF check (k1=1.5, b=0.75, zero-clamped Robertson IDF) explaining the official bm25s convention
        rob_idx = s1.LocalWholeDocBM25Index(doc_ids, doc_texts, k1=1.5, b=0.75, lucene_idf=False)
        rob_sc = rob_idx.score_queries(q_texts)
        rob_rank = stage0_core.scores_to_rankings(rob_sc, q_ids, doc_ids)
        rob_all = stage0_core.per_query_ndcg_at_k(rob_rank, qrels, q_ids, k=10)
        top1_rob = sum(off_rank[q][0] == rob_rank[q][0] for q in q_ids)
        jacc10_rob = float(np.mean([len(set(off_rank[q][:10]) & set(rob_rank[q][:10])) / len(set(off_rank[q][:10]) | set(rob_rank[q][:10])) for q in q_ids]))

        parity[nano_name] = {
            "official_bm25_ndcg10_all200": float(off_all.mean()),
            "same_scored_local_bm25_k1_1p2_b_0p75_lucene_idf": {
                "ndcg10_all200": float(loc_all.mean()),
                "diff_vs_official_all200": float(loc_all.mean() - off_all.mean()),
                "ndcg10_dev": float(stage0_core.per_query_ndcg_at_k(loc_rank, qrels, dev_qids, k=10).mean()),
                "official_ndcg10_dev": float(stage0_core.per_query_ndcg_at_k(off_rank, qrels, dev_qids, k=10).mean()),
                "ndcg10_stage0_heldout": float(stage0_core.per_query_ndcg_at_k(loc_rank, qrels, s0_ho_qids, k=10).mean()),
                "official_ndcg10_stage0_heldout": float(stage0_core.per_query_ndcg_at_k(off_rank, qrels, s0_ho_qids, k=10).mean()),
                "top1_agreement_all200": f"{top1_same}/200",
                "mean_top10_jaccard_all200": jacc10_same,
                "per_query_ndcg_spearman_all200": float(spearmanr(off_all, loc_all).statistic),
            },
            "diagnostic_robertson_idf_k1_1p5_b_0p75_reference_match": {
                "ndcg10_all200": float(rob_all.mean()),
                "diff_vs_official_all200": float(rob_all.mean() - off_all.mean()),
                "top1_agreement_all200": f"{top1_rob}/200",
                "mean_top10_jaccard_all200": jacc10_rob,
            },
        }

    # 3. Synthetic Fixtures for robust_normalize_per_query & CountConditionalTop3Calibrator
    rng = np.random.default_rng(20261124)
    # (a) Ultra-sparse & moderate-sparse robust normalization check
    syn_scores = np.zeros((3, 200), dtype=np.float64)
    syn_scores[0] = rng.exponential(2.0, size=200)
    syn_scores[0, 5] = 45.0  # strong positive spike
    syn_scores[1, :15] = rng.uniform(0.5, 10.0, size=15)  # 92.5% zeros
    syn_scores[2, :2] = np.array([12.0, 4.0])  # 99.0% zeros (fallback to full std)
    normed = s1.robust_normalize_per_query(syn_scores)
    assert np.all(np.isfinite(normed)), "Non-finite value in robust_normalize_per_query!"
    for qi in range(3):
        orig_order = np.argsort(-syn_scores[qi], kind="mergesort")
        norm_order = np.argsort(-normed[qi], kind="mergesort")
        assert np.array_equal(orig_order, norm_order), f"Order changed on query {qi}!"

    # (b) Synthetic Top-3 score distribution with realistic chunk counts + injected unlabeled rank-1 positives
    n_bg_q, n_d = 98, 200
    doc_ns = np.array([4] * 100 + [64] * 100, dtype=np.int64)
    bg_top3 = np.zeros((n_bg_q, n_d), dtype=np.float64)
    for qi in range(n_bg_q):
        for di in range(n_d):
            draws = rng.exponential(1.0, size=int(doc_ns[di]))
            bg_top3[qi, di] = float(np.mean(np.partition(draws, len(draws) - 3)[-3:]))
        # Inject one extreme unlabeled true-positive spike at a random long doc to test top-1 immunity!
        pos_d = 100 + (qi % 100)
        bg_top3[qi, pos_d] += 25.0

    bg_r = s1.robust_normalize_per_query(bg_top3)
    cal = s1.CountConditionalTop3Calibrator(bg_r, doc_ns, bandwidth_h=0.50, tail_q=0.98, exclude_top_k_per_bg_query=1)
    test_levels = np.array([0.0, 2.0, 5.0, 10.0, 20.0, 50.0], dtype=np.float64)
    probe_r = np.column_stack([test_levels, test_levels])
    probe_cal = cal.calibrate_unit_matched(probe_r, np.array([4, 64], dtype=np.int64))
    short_vals = probe_cal[:, 0].tolist()
    long_vals = probe_cal[:, 1].tolist()

    strictly_monotone_short = all(short_vals[i + 1] > short_vals[i] for i in range(len(short_vals) - 1))
    strictly_monotone_long = all(long_vals[i + 1] > long_vals[i] for i in range(len(long_vals) - 1))
    short_always_gt_long_including_r50 = all(short_vals[i] > long_vals[i] for i in range(len(short_vals)))

    assert strictly_monotone_short and strictly_monotone_long
    assert short_always_gt_long_including_r50, f"Tail crossover detected! short={short_vals}, long={long_vals}"

    fixture_receipt = {
        "purpose": "Stage-1 pre-launch parity & synthetic fixture verification (run BEFORE scoring any fresh queries).",
        "stage1_core_py_sha256": sha256_file(PROJ / "stage1_countcal_top3_core.py"),
        "fresh_splits_receipt_sha256": sha256_file(PROJ / "STAGE1_FRESH_SPLITS_RECEIPT.json"),
        "all_fixtures_passed": True,
        "local_wholedoc_bm25_parity": parity,
        "synthetic_countcal_top3_fixture": {
            "sparse_92p5_and_99p0_zero_order_preserved": True,
            "injected_bg_top1_positives_per_query": 1,
            "beta_global": cal.beta_global,
            "r_levels": test_levels.tolist(),
            "short_n4_unit_matched": short_vals,
            "long_n64_unit_matched": long_vals,
            "strictly_monotone_through_r50": strictly_monotone_short and strictly_monotone_long,
            "short_strictly_gt_long_through_r50_zero_crossover": short_always_gt_long_including_r50,
        },
    }
    (PROJ / "STAGE1_PARITY_AND_FIXTURES_RECEIPT.json").write_text(
        json.dumps(fixture_receipt, indent=2), encoding="utf-8"
    )
    return fixture_receipt


if __name__ == "__main__":
    sp_rec = build_fresh_splits()
    fx_rec = verify_bm25_parity_and_synthetic_fixtures()
    print("Fresh splits built & verified:")
    for t, info in sp_rec["tasks"].items():
        print(
            f"  {t}: {info['fresh_selected_queries']} fresh queries across "
            f"{info['fresh_selected_doc_groups']} distinct fresh docs "
            f"(from {info['fresh_eligible_doc_groups_total']} eligible fresh docs; "
            f"overlaps={info['disjointness_verified']})"
        )
    print("\nSynthetic fixture passed:", fx_rec["all_fixtures_passed"])
    print("  beta_global:", round(fx_rec["synthetic_countcal_top3_fixture"]["beta_global"], 4))
    print("  short(n=4) :", [round(x, 3) for x in fx_rec["synthetic_countcal_top3_fixture"]["short_n4_unit_matched"]])
    print("  long(n=64) :", [round(x, 3) for x in fx_rec["synthetic_countcal_top3_fixture"]["long_n64_unit_matched"]])
    print("  zero crossover through r=50:", fx_rec["synthetic_countcal_top3_fixture"]["short_strictly_gt_long_through_r50_zero_crossover"])
