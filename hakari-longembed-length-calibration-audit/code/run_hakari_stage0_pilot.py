"""
Stage-0 CPU-Only Pilot: Training-Free Length-Calibrated Long-Document Retrieval on
HAKARI-Bench NanoLongEmbed (`NanoQMSum` and `NanoNarrativeQA`, pinned revision
`ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e`).

Locked Protocol: STAGE0_HAKARI_PROTOCOL.md
Pre-Launch Gates Asserted BEFORE Scoring Any Held-Out Query:
  1. DATASET_DOWNLOAD_RECEIPT.json verified
  2. HAKARI_STAGE0_SPLITS_RECEIPT.json (`zero_query_overlap == True`, `zero_relevant_doc_group_overlap == True`)
  3. HAKARI_STAGE0_FIXTURE_RECEIPT.json (`all_fixtures_passed == True`)
  4. STAGE0_HAKARI_PROTOCOL.md exists

Strict Execution Separation:
  - Phase 1: Full-corpus chunk Okapi BM25 indexing (W=256 words, k1=1.2, b=0.75; 100% corpus recall).
  - Phase 2: Fit Empirical Count-Conditional Null strictly on `unlabeled_bg_pool` (zero qrels read).
  - Phase 3: Dev-only hyperparameter selection (`lambda`, `h`, BM25 RRF fusion `alpha`) strictly on `dev`.
  - Phase 4: Freeze all parameters -> evaluate ONCE on natural `heldout_test` and persist frozen
             natural per-query outputs (`stage0_natural_heldout_per_query.jsonl`) BEFORE any diagnostic.
  - Phase 5: Mechanism diagnostics ONLY (natural non-relevant length-bias audit + artificial irrelevant
             suffix padding stress test), strictly separate from natural benchmark scores.
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import pathlib
import sys
import time
from collections import defaultdict
from typing import Any, Dict, List, Tuple

import numpy as np
import pyarrow.parquet as pq
from scipy import stats

BASE = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE))

import hakari_retrieval_core as hrc  # noqa: E402

CHUNK_WORDS = 256
BM25_K1 = 1.2
BM25_B = 0.75
RRF_K = 60

LAMBDA_GRID = [0.0, 0.25, 0.5, 1.0, 1.5, 2.0, 3.0, 4.0, 6.0, 8.0]
BANDWIDTH_GRID = [0.35, 0.50, 0.75]
ALPHA_GRID = [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
ADVANCE_MACRO_GAIN_MIN = 0.030


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load_task_data(task: str) -> Dict[str, Any]:
    d = BASE / "data"
    corpus_rows = pq.read_table(d / f"corpus/{task}-00000-of-00001.parquet").to_pylist()
    query_rows = pq.read_table(d / f"queries/{task}-00000-of-00001.parquet").to_pylist()
    qrel_rows = pq.read_table(d / f"qrels/{task}-00000-of-00001.parquet").to_pylist()
    bm25_rows = pq.read_table(d / f"bm25/{task}-00000-of-00001.parquet").to_pylist()
    hyb_rows = pq.read_table(d / f"reranking_hybrid/{task}-00000-of-00001.parquet").to_pylist()

    doc_ids = [str(r["_id"]) for r in corpus_rows]
    doc_texts = [str(r["text"]) for r in corpus_rows]
    query_text_by_id = {str(r["_id"]): str(r["text"]) for r in query_rows}

    qrels: Dict[str, set] = defaultdict(set)
    for r in qrel_rows:
        qrels[str(r["query-id"])].add(str(r["corpus-id"]))

    bm25_rankings = {str(r["query-id"]): [str(x) for x in r["corpus-ids"]] for r in bm25_rows}
    # Strip rank-101 oracle safeguard strictly!
    hyb_top100_rankings = {str(r["query-id"]): [str(x) for x in r["corpus-ids"][:100]] for r in hyb_rows}

    return {
        "doc_ids": doc_ids,
        "doc_texts": doc_texts,
        "query_text_by_id": query_text_by_id,
        "qrels": dict(qrels),
        "official_bm25": bm25_rankings,
        "official_hybrid_top100_nosafeguard": hyb_top100_rankings,
    }


def natural_nonrel_length_bias_diagnostic(
    scores_q_d: np.ndarray,
    query_ids: List[str],
    doc_ids: List[str],
    doc_chunk_counts: np.ndarray,
    qrels: Dict[str, set],
) -> Dict[str, Any]:
    """
    Measures length bias on natural non-relevant documents:
      - Spearman rho(score, log(n_d)) pooled across all non-relevant (q, d) pairs,
      - Share of non-relevant top-10 intrusions from Q4 (longest quartile) vs Q1 (shortest quartile).
    """
    q25, q75 = np.percentile(doc_chunk_counts, [25, 75])
    is_q1 = doc_chunk_counts <= q25
    is_q4 = doc_chunk_counts >= q75
    log_n = np.log(np.maximum(1.0, doc_chunk_counts.astype(np.float64)))
    doc_to_idx = {did: i for i, did in enumerate(doc_ids)}

    nonrel_scores = []
    nonrel_logn = []
    q1_top10_intrusions = 0
    q4_top10_intrusions = 0
    total_nonrel_top10 = 0

    for qi, qid in enumerate(query_ids):
        rel_idxs = {doc_to_idx[d] for d in qrels.get(qid, set()) if d in doc_to_idx}
        row = scores_q_d[qi]
        mask_nr = np.ones(len(doc_ids), dtype=bool)
        for ri in rel_idxs:
            mask_nr[ri] = False
        nonrel_scores.append(row[mask_nr])
        nonrel_logn.append(log_n[mask_nr])

        order = np.argsort(-row, kind="mergesort")[:10]
        for idx in order:
            if idx not in rel_idxs:
                total_nonrel_top10 += 1
                if is_q1[idx]:
                    q1_top10_intrusions += 1
                if is_q4[idx]:
                    q4_top10_intrusions += 1

    all_s = np.concatenate(nonrel_scores)
    all_ln = np.concatenate(nonrel_logn)
    rho = float(stats.spearmanr(all_s, all_ln).statistic)
    return {
        "nonrel_spearman_rho_score_vs_log_n": rho,
        "q1_shortest_top10_nonrel_share": float(q1_top10_intrusions / max(1, total_nonrel_top10)),
        "q4_longest_top10_nonrel_share": float(q4_top10_intrusions / max(1, total_nonrel_top10)),
        "q4_to_q1_intrusion_ratio": float(q4_top10_intrusions / max(1, q1_top10_intrusions)),
        "total_nonrel_top10_slots": int(total_nonrel_top10),
    }


def run_task(task: str, split_info: Dict[str, Any], out_dir: pathlib.Path) -> Dict[str, Any]:
    t_task0 = time.perf_counter()
    print(f"\n==================== TASK: {task} ====================", flush=True)
    data = load_task_data(task)
    doc_ids = data["doc_ids"]
    doc_texts = data["doc_texts"]
    q_text = data["query_text_by_id"]
    qrels = data["qrels"]

    dev_qids = split_info["dev"]["query_ids"]
    dev_groups = [split_info["dev"]["query_to_group_doc"][q] for q in dev_qids]
    test_qids = split_info["heldout_test"]["query_ids"]
    test_groups = [split_info["heldout_test"]["query_to_group_doc"][q] for q in test_qids]
    bg_qids = split_info["unlabeled_bg_pool"]["query_ids"]

    # Phase 1: Full-corpus chunk BM25 indexing (100% candidate recall)
    t_idx0 = time.perf_counter()
    idx = hrc.SparseChunkBM25Index(doc_ids, doc_texts, chunk_words=CHUNK_WORDS, k1=BM25_K1, b=BM25_B)
    t_index_s = time.perf_counter() - t_idx0
    doc_counts = idx.doc_chunk_counts
    log_doc_counts = np.log(np.maximum(1.0, doc_counts.astype(np.float64)))
    print(
        f"  Indexed {idx.n_docs} docs -> {idx.n_chunks} chunks (W={CHUNK_WORDS}, vocab={idx.n_vocab}) in {t_index_s:.2f}s | "
        f"chunks/doc: min={doc_counts.min()}, p50={int(np.median(doc_counts))}, max={doc_counts.max()}",
        flush=True,
    )

    # Phase 2: Score disjoint UNLABELED background query pool (ZERO qrels ever read!)
    t_bg0 = time.perf_counter()
    bg_chunk_sc = idx.score_queries_all_chunks([q_text[q] for q in bg_qids])
    bg_feats = hrc.compute_doc_passage_features(bg_chunk_sc, idx.doc_chunk_starts, doc_counts)
    t_bg_s = time.perf_counter() - t_bg0
    print(f"  Scored {len(bg_qids)} unlabeled background queries (0 qrels read) in {t_bg_s:.2f}s", flush=True)

    # Phase 3: Score DEV queries and select ALL tunable parameters STRICTLY ON DEV
    t_dev0 = time.perf_counter()
    dev_chunk_sc = idx.score_queries_all_chunks([q_text[q] for q in dev_qids])
    dev_feats = hrc.compute_doc_passage_features(dev_chunk_sc, idx.doc_chunk_starts, doc_counts)

    def eval_ndcg(rankings: Dict[str, List[str]], qids: List[str]) -> Tuple[float, np.ndarray]:
        arr = hrc.per_query_ndcg_at_k(rankings, qrels, qids, k=10)
        return float(np.mean(arr)), arr

    # 3a. Dev tune lambda for MaxP - lambda * log(n_d)
    dev_lambda_curve = {}
    best_lambda, best_lambda_ndcg = 0.0, -1.0
    for lam in LAMBDA_GRID:
        sc = dev_feats["maxp"] - lam * log_doc_counts[None, :]
        m, _ = eval_ndcg(hrc.scores_to_rankings(sc, dev_qids, doc_ids), dev_qids)
        dev_lambda_curve[str(lam)] = m
        if m > best_lambda_ndcg + 1e-12:
            best_lambda_ndcg = m
            best_lambda = lam

    # 3b. Dev tune bandwidth h for Empirical_CountCond_Null (fit strictly on unlabeled bg_feats["z_lodo"])
    dev_h_curve = {}
    best_h, best_h_ndcg = 0.50, -1.0
    best_calibrator = None
    for h in BANDWIDTH_GRID:
        cal = hrc.EmpiricalCountConditionalCalibrator(bg_feats["z_lodo"], doc_counts, bandwidth_h=h, tail_q=0.98)
        dev_emp = cal.calibrate_matrix(dev_feats["z_lodo"], doc_counts)
        m, _ = eval_ndcg(hrc.scores_to_rankings(dev_emp, dev_qids, doc_ids), dev_qids)
        dev_h_curve[str(h)] = m
        if m > best_h_ndcg + 1e-12:
            best_h_ndcg = m
            best_h = h
            best_calibrator = cal
    assert best_calibrator is not None
    dev_emp_best = best_calibrator.calibrate_matrix(dev_feats["z_lodo"], doc_counts)
    dev_maxlogn_best = dev_feats["maxp"] - best_lambda * log_doc_counts[None, :]

    # 3c. Dev tune BM25 RRF fusion weights alpha for RawMaxP, MaxMinusLogN, and EmpiricalNull
    def tune_rrf_alpha(dev_sc_mat: np.ndarray) -> Tuple[float, float, Dict[str, float]]:
        curve = {}
        b_a, b_m = 0.0, -1.0
        for alpha in ALPHA_GRID:
            rk = hrc.rrf_fuse_official_bm25_with_scores(data["official_bm25"], dev_sc_mat, dev_qids, doc_ids, alpha, RRF_K)
            m, _ = eval_ndcg(rk, dev_qids)
            curve[str(alpha)] = m
            if m > b_m + 1e-12:
                b_m = m
                b_a = alpha
        return b_a, b_m, curve

    alpha_rawmax, dev_rrf_rawmax, curve_rrf_rawmax = tune_rrf_alpha(dev_feats["maxp"])
    alpha_maxlogn, dev_rrf_maxlogn, curve_rrf_maxlogn = tune_rrf_alpha(dev_maxlogn_best)
    alpha_emp, dev_rrf_emp, curve_rrf_emp = tune_rrf_alpha(dev_emp_best)

    # Record complete DEV scores across all methods
    dev_methods = {
        "Official_WholeDoc_BM25": eval_ndcg(data["official_bm25"], dev_qids)[0],
        "Official_Hybrid_Top100_NoSafeguard": eval_ndcg(data["official_hybrid_top100_nosafeguard"], dev_qids)[0],
        "Raw_MaxP": eval_ndcg(hrc.scores_to_rankings(dev_feats["maxp"], dev_qids, doc_ids), dev_qids)[0],
        "Top3_Mean": eval_ndcg(hrc.scores_to_rankings(dev_feats["top3_mean"], dev_qids, doc_ids), dev_qids)[0],
        "MaxP_Minus_Lambda_LogN": best_lambda_ndcg,
        "Analytical_IID_Null": eval_ndcg(hrc.scores_to_rankings(dev_feats["analytical_iid"], dev_qids, doc_ids), dev_qids)[0],
        "Empirical_CountCond_Null": best_h_ndcg,
        "RRF_BM25_plus_RawMaxP": dev_rrf_rawmax,
        "RRF_BM25_plus_MaxMinusLogN": dev_rrf_maxlogn,
        "RRF_BM25_plus_EmpiricalNull": dev_rrf_emp,
    }
    t_dev_s = time.perf_counter() - t_dev0
    print(
        f"  DEV ({len(dev_qids)}q, {t_dev_s:.2f}s) locked params: lambda*={best_lambda}, h*={best_h}, "
        f"alpha*(raw={alpha_rawmax}, logn={alpha_maxlogn}, emp={alpha_emp})",
        flush=True,
    )
    print(
        f"  DEV nDCG@10: BM25={dev_methods['Official_WholeDoc_BM25']:.4f} | "
        f"RawMaxP={dev_methods['Raw_MaxP']:.4f}, Top3={dev_methods['Top3_Mean']:.4f}, "
        f"Max-logN={dev_methods['MaxP_Minus_Lambda_LogN']:.4f}, AnalytIID={dev_methods['Analytical_IID_Null']:.4f}, "
        f"EmpNull={dev_methods['Empirical_CountCond_Null']:.4f}",
        flush=True,
    )

    # Phase 4: FROZEN EVALUATION ON NATURAL HELD-OUT TEST (ONCE!)
    t_test0 = time.perf_counter()
    test_chunk_sc = idx.score_queries_all_chunks([q_text[q] for q in test_qids])
    test_feats = hrc.compute_doc_passage_features(test_chunk_sc, idx.doc_chunk_starts, doc_counts)
    t_cal0 = time.perf_counter()
    test_emp = best_calibrator.calibrate_matrix(test_feats["z_lodo"], doc_counts)
    t_cal_s = time.perf_counter() - t_cal0
    test_maxlogn = test_feats["maxp"] - best_lambda * log_doc_counts[None, :]
    t_test_s = time.perf_counter() - t_test0

    test_score_mats = {
        "Raw_MaxP": test_feats["maxp"],
        "Top3_Mean": test_feats["top3_mean"],
        "MaxP_Minus_Lambda_LogN": test_maxlogn,
        "Analytical_IID_Null": test_feats["analytical_iid"],
        "Empirical_CountCond_Null": test_emp,
    }
    test_rankings = {
        "Official_WholeDoc_BM25": data["official_bm25"],
        "Official_Hybrid_Top100_NoSafeguard": data["official_hybrid_top100_nosafeguard"],
        **{k: hrc.scores_to_rankings(m, test_qids, doc_ids) for k, m in test_score_mats.items()},
        "RRF_BM25_plus_RawMaxP": hrc.rrf_fuse_official_bm25_with_scores(data["official_bm25"], test_feats["maxp"], test_qids, doc_ids, alpha_rawmax, RRF_K),
        "RRF_BM25_plus_MaxMinusLogN": hrc.rrf_fuse_official_bm25_with_scores(data["official_bm25"], test_maxlogn, test_qids, doc_ids, alpha_maxlogn, RRF_K),
        "RRF_BM25_plus_EmpiricalNull": hrc.rrf_fuse_official_bm25_with_scores(data["official_bm25"], test_emp, test_qids, doc_ids, alpha_emp, RRF_K),
    }

    test_per_q_ndcg: Dict[str, np.ndarray] = {}
    test_mean_ndcg: Dict[str, float] = {}
    for m_name, rk in test_rankings.items():
        mean_v, arr_v = eval_ndcg(rk, test_qids)
        test_mean_ndcg[m_name] = mean_v
        test_per_q_ndcg[m_name] = arr_v

    # Persist FROZEN natural held-out per-query ledger BEFORE running any mechanism diagnostic!
    pq_path = out_dir / f"{task}_natural_heldout_per_query.jsonl"
    with pq_path.open("w", encoding="utf-8") as fout:
        for qi, qid in enumerate(test_qids):
            rel_doc = next(iter(qrels[qid]))
            rel_idx = doc_ids.index(rel_doc)
            row = {
                "task": task,
                "query_id": qid,
                "relevant_doc_id": rel_doc,
                "relevant_doc_chunk_count": int(doc_counts[rel_idx]),
                "ndcg10": {m_name: float(test_per_q_ndcg[m_name][qi]) for m_name in test_rankings},
            }
            fout.write(json.dumps(row) + "\n")

    print(
        f"  HELD-OUT NATURAL ({len(test_qids)}q, {t_test_s:.2f}s, cal={t_cal_s*1000:.1f}ms, 100% corpus recall):\n"
        f"    Official BM25={test_mean_ndcg['Official_WholeDoc_BM25']:.4f} | Hybrid[:100](no-sg)={test_mean_ndcg['Official_Hybrid_Top100_NoSafeguard']:.4f}\n"
        f"    Passage-only: RawMaxP={test_mean_ndcg['Raw_MaxP']:.4f}, Top3={test_mean_ndcg['Top3_Mean']:.4f}, "
        f"Max-logN={test_mean_ndcg['MaxP_Minus_Lambda_LogN']:.4f}, AnalytIID={test_mean_ndcg['Analytical_IID_Null']:.4f}, "
        f"EmpNull={test_mean_ndcg['Empirical_CountCond_Null']:.4f}\n"
        f"    BM25+RRF: +RawMaxP={test_mean_ndcg['RRF_BM25_plus_RawMaxP']:.4f}, "
        f"+Max-logN={test_mean_ndcg['RRF_BM25_plus_MaxMinusLogN']:.4f}, +EmpNull={test_mean_ndcg['RRF_BM25_plus_EmpiricalNull']:.4f}",
        flush=True,
    )

    # Paired cluster-bootstrap comparisons on natural held-out
    passage_baselines = ["Raw_MaxP", "Top3_Mean", "MaxP_Minus_Lambda_LogN", "Analytical_IID_Null"]
    strongest_passage_baseline = max(passage_baselines, key=lambda k: test_mean_ndcg[k])
    strongest_comparable_all = max(passage_baselines + ["Official_WholeDoc_BM25"], key=lambda k: test_mean_ndcg[k])

    paired_comparisons = {
        f"EmpiricalNull_vs_{b}": hrc.cluster_paired_bootstrap_diff(
            test_per_q_ndcg["Empirical_CountCond_Null"], test_per_q_ndcg[b], test_groups
        )
        for b in passage_baselines + ["Official_WholeDoc_BM25"]
    }
    paired_comparisons["RRF_EmpNull_vs_Official_BM25"] = hrc.cluster_paired_bootstrap_diff(
        test_per_q_ndcg["RRF_BM25_plus_EmpiricalNull"], test_per_q_ndcg["Official_WholeDoc_BM25"], test_groups
    )
    paired_comparisons["RRF_EmpNull_vs_RRF_RawMaxP"] = hrc.cluster_paired_bootstrap_diff(
        test_per_q_ndcg["RRF_BM25_plus_EmpiricalNull"], test_per_q_ndcg["RRF_BM25_plus_RawMaxP"], test_groups
    )

    # Phase 5: MECHANISM DIAGNOSTICS ONLY (strictly AFTER freezing natural held-out outputs;
    # NEVER counted as benchmark progress!)
    # 5a. Natural non-relevant length-bias audit (Q1 shortest vs Q4 longest)
    length_bias_diag = {
        m_name: natural_nonrel_length_bias_diagnostic(mat, test_qids, doc_ids, doc_counts, qrels)
        for m_name, mat in test_score_mats.items()
    }

    # 5b. Artificial irrelevant-suffix control:
    # Draw M=100 irrelevant chunks deterministically from `dev`-only relevant docs (guaranteed non-relevant
    # to EVERY heldout_test query due to group-disjoint split!), append those exact chunk scores to every
    # NON-RELEVANT doc for each heldout_test query, and measure degradation vs natural nDCG@10!
    dev_doc_set = set(split_info["dev"]["query_to_group_doc"].values())
    dev_doc_indices = [i for i, did in enumerate(doc_ids) if did in dev_doc_set]
    rng_diag = np.random.default_rng(2026112401)
    # Build pool of chunk indices belonging strictly to dev-only docs
    dev_chunk_pool = np.concatenate([
        np.arange(idx.doc_chunk_starts[di], idx.doc_chunk_starts[di] + doc_counts[di], dtype=np.int64)
        for di in dev_doc_indices
    ])
    pad_m = 100
    # Fixed deterministic suffix per non-relevant document (so every non-relevant doc gains +100 irrelevant chunks)
    suffix_chunk_idxs_per_doc = rng_diag.choice(dev_chunk_pool, size=(idx.n_docs, pad_m), replace=True)

    # Evaluate padded distractors per held-out query (relevant doc for query q stays UNMODIFIED!)
    pad_ndcg_per_q = {m: np.zeros(len(test_qids), dtype=np.float64) for m in test_score_mats}
    doc_to_idx = {did: i for i, did in enumerate(doc_ids)}

    for qi, qid in enumerate(test_qids):
        rel_doc = next(iter(qrels[qid]))
        rel_di = doc_to_idx[rel_doc]
        sc_q = test_chunk_sc[qi]  # [C]

        # Construct augmented chunk vector for query qi (original chunks + 100 suffix chunks on every di != rel_di)
        aug_chunks = []
        aug_starts = np.zeros(idx.n_docs, dtype=np.int64)
        aug_counts = np.zeros(idx.n_docs, dtype=np.int64)
        cur = 0
        for di in range(idx.n_docs):
            st = int(idx.doc_chunk_starts[di])
            cnt = int(doc_counts[di])
            base_c = sc_q[st : st + cnt]
            if di == rel_di:
                arr_c = base_c
            else:
                suf_c = sc_q[suffix_chunk_idxs_per_doc[di]]
                arr_c = np.concatenate([base_c, suf_c])
            aug_starts[di] = cur
            aug_counts[di] = len(arr_c)
            aug_chunks.append(arr_c)
            cur += len(arr_c)

        aug_mat = np.concatenate(aug_chunks)[None, :]  # [1, C_aug]
        af = hrc.compute_doc_passage_features(aug_mat, aug_starts, aug_counts)
        a_emp = best_calibrator.calibrate_matrix(af["z_lodo"], aug_counts)
        a_logn = af["maxp"] - best_lambda * np.log(np.maximum(1.0, aug_counts.astype(np.float64)))[None, :]
        a_mats = {
            "Raw_MaxP": af["maxp"],
            "Top3_Mean": af["top3_mean"],
            "MaxP_Minus_Lambda_LogN": a_logn,
            "Analytical_IID_Null": af["analytical_iid"],
            "Empirical_CountCond_Null": a_emp,
        }
        for m_name, mat in a_mats.items():
            rk = hrc.scores_to_rankings(mat, [qid], doc_ids)
            pad_ndcg_per_q[m_name][qi] = hrc.per_query_ndcg_at_k(rk, qrels, [qid], 10)[0]

    suffix_control_diag = {
        "note": "MECHANISM DIAGNOSTIC ONLY (run AFTER freezing natural held-out outputs; NEVER counted as benchmark progress): +100 irrelevant chunks from dev-only docs appended to every non-relevant doc.",
        "pad_chunks_added_per_nonrel_doc": pad_m,
        "methods": {
            m_name: {
                "natural_ndcg10": test_mean_ndcg[m_name],
                "padded_distractors_ndcg10": float(np.mean(pad_ndcg_per_q[m_name])),
                "drop_padded_minus_natural": float(np.mean(pad_ndcg_per_q[m_name]) - test_mean_ndcg[m_name]),
            }
            for m_name in test_score_mats
        },
    }

    return {
        "task": task,
        "corpus_size": idx.n_docs,
        "total_chunks": idx.n_chunks,
        "candidate_recall_all_passage_methods": 1.0,
        "chunk_count_stats": {
            "min": int(doc_counts.min()),
            "p10": float(np.percentile(doc_counts, 10)),
            "p50": float(np.median(doc_counts)),
            "p90": float(np.percentile(doc_counts, 90)),
            "max": int(doc_counts.max()),
        },
        "runtime_s": {
            "index_build_s": t_index_s,
            "bg_unlabeled_score_s": t_bg_s,
            "dev_score_and_tune_s": t_dev_s,
            "heldout_natural_score_s": t_test_s,
            "heldout_empirical_calibrator_only_s": t_cal_s,
            "task_total_s": time.perf_counter() - t_task0,
        },
        "dev_locked_hyperparameters": {
            "lambda_max_minus_logn": best_lambda,
            "lambda_dev_curve": dev_lambda_curve,
            "bandwidth_h_empirical_null": best_h,
            "bandwidth_dev_curve": dev_h_curve,
            "alpha_rrf_rawmax": alpha_rawmax,
            "alpha_rrf_maxlogn": alpha_maxlogn,
            "alpha_rrf_emp": alpha_emp,
        },
        "dev_ndcg10": dev_methods,
        "heldout_natural_ndcg10": test_mean_ndcg,
        "heldout_strongest_passage_baseline": strongest_passage_baseline,
        "heldout_strongest_comparable_frozen_baseline": strongest_comparable_all,
        "heldout_natural_per_query_jsonl": str(pq_path.name),
        "heldout_natural_per_query_sha256": sha256_file(pq_path),
        "heldout_paired_cluster_bootstrap": paired_comparisons,
        "mechanism_diagnostics_SEPARATE_NOT_BENCHMARK_PROGRESS": {
            "natural_nonrel_length_bias": length_bias_diag,
            "artificial_irrelevant_suffix_control": suffix_control_diag,
        },
    }


def main():
    t0 = time.perf_counter()
    pid = os.getpid()

    # HARD PRE-LAUNCH GATES
    dl_p = BASE / "DATASET_DOWNLOAD_RECEIPT.json"
    sp_p = BASE / "HAKARI_STAGE0_SPLITS_RECEIPT.json"
    fx_p = BASE / "HAKARI_STAGE0_FIXTURE_RECEIPT.json"
    pr_p = BASE / "STAGE0_HAKARI_PROTOCOL.md"
    assert dl_p.exists() and sp_p.exists() and fx_p.exists() and pr_p.exists(), "Missing pre-launch locked receipt/protocol!"
    assert json.loads(fx_p.read_text(encoding="utf-8"))["all_fixtures_passed"] is True
    splits = json.loads(sp_p.read_text(encoding="utf-8"))
    for t in ("NanoQMSum", "NanoNarrativeQA"):
        assert splits[t]["zero_query_overlap"] is True and splits[t]["zero_relevant_doc_group_overlap"] is True

    print(f"=== Stage-0 HAKARI Length-Calibrated Retrieval Pilot (CPU-only, PID={pid}) ===", flush=True)
    out_dir = BASE / "stage0_pilot_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)

    task_results = {}
    for task in ("NanoQMSum", "NanoNarrativeQA"):
        task_results[task] = run_task(task, splits[task], out_dir)

    # Macro averages & exact prespecified advancement gate
    methods = list(task_results["NanoQMSum"]["heldout_natural_ndcg10"].keys())
    macro_heldout = {
        m: 0.5 * (task_results["NanoQMSum"]["heldout_natural_ndcg10"][m] + task_results["NanoNarrativeQA"]["heldout_natural_ndcg10"][m])
        for m in methods
    }

    # Check BOTH pure-passage gate AND overall (including Official_WholeDoc_BM25) gate
    passage_baselines = ["Raw_MaxP", "Top3_Mean", "MaxP_Minus_Lambda_LogN", "Analytical_IID_Null"]
    best_passage_macro_name = max(passage_baselines, key=lambda m: macro_heldout[m])
    best_all_comparable_macro_name = max(passage_baselines + ["Official_WholeDoc_BM25"], key=lambda m: macro_heldout[m])

    def evaluate_gate(cand_name: str, baseline_name_by_task: Dict[str, str], macro_base_name: str) -> Dict[str, Any]:
        q_gain = task_results["NanoQMSum"]["heldout_natural_ndcg10"][cand_name] - task_results["NanoQMSum"]["heldout_natural_ndcg10"][baseline_name_by_task["NanoQMSum"]]
        n_gain = task_results["NanoNarrativeQA"]["heldout_natural_ndcg10"][cand_name] - task_results["NanoNarrativeQA"]["heldout_natural_ndcg10"][baseline_name_by_task["NanoNarrativeQA"]]
        macro_gain_vs_best_macro = macro_heldout[cand_name] - macro_heldout[macro_base_name]
        macro_gain_vs_per_task_best = 0.5 * (q_gain + n_gain)
        passes = bool(q_gain > 0.0 and n_gain > 0.0 and macro_gain_vs_best_macro >= ADVANCE_MACRO_GAIN_MIN)
        return {
            "candidate": cand_name,
            "strongest_baseline_per_task": baseline_name_by_task,
            "strongest_baseline_macro": macro_base_name,
            "gain_NanoQMSum_vs_per_task_best": q_gain,
            "gain_NanoNarrativeQA_vs_per_task_best": n_gain,
            "macro_gain_vs_strongest_macro_baseline": macro_gain_vs_best_macro,
            "macro_gain_vs_per_task_best": macro_gain_vs_per_task_best,
            "improves_both_tasks": bool(q_gain > 0.0 and n_gain > 0.0),
            "passes_advance_gate_ge_0.03": passes,
        }

    gate_passage_only = evaluate_gate(
        "Empirical_CountCond_Null",
        {t: task_results[t]["heldout_strongest_passage_baseline"] for t in ("NanoQMSum", "NanoNarrativeQA")},
        best_passage_macro_name,
    )
    gate_vs_all_including_bm25 = evaluate_gate(
        "Empirical_CountCond_Null",
        {t: task_results[t]["heldout_strongest_comparable_frozen_baseline"] for t in ("NanoQMSum", "NanoNarrativeQA")},
        best_all_comparable_macro_name,
    )
    gate_rrf_emp_vs_all = evaluate_gate(
        "RRF_BM25_plus_EmpiricalNull",
        {t: max(passage_baselines + ["Official_WholeDoc_BM25", "RRF_BM25_plus_RawMaxP", "RRF_BM25_plus_MaxMinusLogN"], key=lambda m: task_results[t]["heldout_natural_ndcg10"][m]) for t in ("NanoQMSum", "NanoNarrativeQA")},
        max(passage_baselines + ["Official_WholeDoc_BM25", "RRF_BM25_plus_RawMaxP", "RRF_BM25_plus_MaxMinusLogN"], key=lambda m: macro_heldout[m]),
    )

    summary = {
        "protocol": "STAGE0_HAKARI_PROTOCOL.md",
        "protocol_sha256": sha256_file(pr_p),
        "real_pid": pid,
        "cpu_only": True,
        "wall_time_s": time.perf_counter() - t0,
        "source_and_code_hashes": {
            "DATASET_DOWNLOAD_RECEIPT_json": sha256_file(dl_p),
            "HAKARI_STAGE0_SPLITS_RECEIPT_json": sha256_file(sp_p),
            "HAKARI_STAGE0_FIXTURE_RECEIPT_json": sha256_file(fx_p),
            "hakari_retrieval_core_py": sha256_file(BASE / "hakari_retrieval_core.py"),
            "run_hakari_stage0_pilot_py": sha256_file(pathlib.Path(__file__)),
        },
        "macro_heldout_natural_ndcg10": macro_heldout,
        "prespecified_advancement_gates": {
            "criterion": "Held-out natural nDCG@10 improves in BOTH NanoQMSum and NanoNarrativeQA AND macro gain >= +0.030 over strongest comparable frozen baseline.",
            "passage_only_gate": gate_passage_only,
            "vs_all_comparable_including_official_bm25_gate": gate_vs_all_including_bm25,
            "rrf_fusion_vs_all_gate": gate_rrf_emp_vs_all,
            "recommendation": (
                "ADVANCE"
                if (gate_vs_all_including_bm25["passes_advance_gate_ge_0.03"] or gate_rrf_emp_vs_all["passes_advance_gate_ge_0.03"])
                else "STOP_OR_ADAPT"
            ),
        },
        "tasks": task_results,
    }

    sum_p = out_dir / "hakari_stage0_summary.json"
    sum_p.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(f"\n=== Stage-0 HAKARI Pilot COMPLETE (PID={pid}, wall={summary['wall_time_s']:.2f}s) ===", flush=True)
    print(f"MACRO HELD-OUT nDCG@10: {json.dumps({k: round(v, 4) for k, v in macro_heldout.items()})}", flush=True)
    print(f"GATE (passage-only): {gate_passage_only['passes_advance_gate_ge_0.03']} (macro_gain={gate_passage_only['macro_gain_vs_strongest_macro_baseline']:+.4f})", flush=True)
    print(f"GATE (vs all incl BM25): {gate_vs_all_including_bm25['passes_advance_gate_ge_0.03']} (macro_gain={gate_vs_all_including_bm25['macro_gain_vs_strongest_macro_baseline']:+.4f})", flush=True)
    print(f"GATE (RRF fusion vs all): {gate_rrf_emp_vs_all['passes_advance_gate_ge_0.03']} (macro_gain={gate_rrf_emp_vs_all['macro_gain_vs_strongest_macro_baseline']:+.4f})", flush=True)
    print(f"RECOMMENDATION: {summary['prespecified_advancement_gates']['recommendation']} | Saved {sum_p} (sha256={sha256_file(sum_p)})", flush=True)


if __name__ == "__main__":
    main()
