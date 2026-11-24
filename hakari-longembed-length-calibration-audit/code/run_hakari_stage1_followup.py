"""
Stage-1 Targeted Follow-Up Native CPU-Only Execution Harness:
Count-Calibrated Top-3 Evidence (`CountCal_Top3`) on Fresh Independent LongEmbed Query Groups.

Strict Discipline:
  - Unchanged corpora (`NanoQMSum` 197 docs, `NanoNarrativeQA` 355 docs), unchanged W=256 chunks,
    unchanged lexical chunk BM25 scorer (`hakari_retrieval_core.py`).
  - Recalibrates ONLY from original Stage-0 `unlabeled_bg_pool` (98 queries/task, zero qrels read).
  - Selects ALL scalar parameters (`gamma` for CountCal_Top3; `alpha` for RRF fusion) SOLELY on
    original Stage-0 `dev` (51q / 52q) with equal dev handling across controls.
  - Evaluates ONCE on the deterministic, 1:1 group-balanced fresh held-out split (`75` fresh queries
    across `75` distinct fresh relevant docs per task from `dwzhu/LongEmbed`, 100% disjoint from ALL
    200 Nano queries and ALL 122 / 163 Nano positive doc groups).
  - No synthetic negative-only padding stress test; natural non-relevant length bias kept strictly
    separate as a diagnostic only.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
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
OUT_DIR = PROJ / "stage1_followup_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GAMMA_GRID = [0.25, 0.50, 0.75, 1.0]
ALPHA_GRID = [round(0.1 * i, 1) for i in range(11)]
RRF_K = 60
BANDWIDTH_H = 0.50
TAIL_Q = 0.98
EXCLUDE_TOP_K_BG = 1
N_BOOT = 5000
BOOT_SEED = 20261124


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def nonrel_length_bias_diagnostic(
    scores_q_d: np.ndarray,
    query_ids: List[str],
    doc_ids: List[str],
    doc_chunk_counts: np.ndarray,
    qrels: Dict[str, set],
) -> Dict[str, Any]:
    """Strictly diagnostic (NOT benchmark progress): non-relevant score vs log(n_d) & Q4/Q1 top-10 intrusion."""
    log_n = np.log(np.maximum(1.0, doc_chunk_counts.astype(np.float64)))
    q25, q75 = np.percentile(doc_chunk_counts, [25, 75])
    is_q1 = doc_chunk_counts <= q25
    is_q4 = doc_chunk_counts >= q75
    doc_to_idx = {d: i for i, d in enumerate(doc_ids)}

    rhos = []
    q1_slots = 0
    q4_slots = 0
    tot_nonrel_top10 = 0

    for qi, qid in enumerate(query_ids):
        rel_idxs = {doc_to_idx[d] for d in qrels.get(qid, set()) if d in doc_to_idx}
        mask = np.ones(len(doc_ids), dtype=bool)
        for ri in rel_idxs:
            mask[ri] = False
        sc_nr = scores_q_d[qi, mask]
        ln_nr = log_n[mask]
        if np.std(sc_nr) > 1e-12:
            r = spearmanr(sc_nr, ln_nr).statistic
            if np.isfinite(r):
                rhos.append(float(r))
        order = np.argsort(-scores_q_d[qi], kind="mergesort")[:10]
        for di in order:
            if di in rel_idxs:
                continue
            tot_nonrel_top10 += 1
            if is_q1[di]:
                q1_slots += 1
            if is_q4[di]:
                q4_slots += 1

    return {
        "nonrel_spearman_rho_score_vs_log_n": float(np.mean(rhos)) if rhos else 0.0,
        "q1_shortest_top10_nonrel_share": q1_slots / max(1, tot_nonrel_top10),
        "q4_longest_top10_nonrel_share": q4_slots / max(1, tot_nonrel_top10),
        "q4_to_q1_intrusion_ratio": (q4_slots / q1_slots) if q1_slots > 0 else None,
        "total_nonrel_top10_slots": tot_nonrel_top10,
    }


def run_task(
    nano_task: str,
    orig_task: str,
    stage0_split: Dict[str, Any],
    fresh_split: Dict[str, Any],
) -> Dict[str, Any]:
    t_task0 = time.perf_counter()

    # 1. Load unchanged Nano corpus, queries, and qrels
    c_tbl = pq.read_table(PROJ / "data" / "corpus" / f"{nano_task}-00000-of-00001.parquet")
    doc_ids = [str(x) for x in c_tbl["_id"].to_pylist()]
    doc_texts = c_tbl["text"].to_pylist()
    doc_to_idx = {d: i for i, d in enumerate(doc_ids)}

    nq_tbl = pq.read_table(PROJ / "data" / "queries" / f"{nano_task}-00000-of-00001.parquet")
    nano_q_map = dict(zip([str(x) for x in nq_tbl["_id"].to_pylist()], [str(x) for x in nq_tbl["text"].to_pylist()]))

    nqr_tbl = pq.read_table(PROJ / "data" / "qrels" / f"{nano_task}-00000-of-00001.parquet")
    nano_qrels: Dict[str, set] = defaultdict(set)
    for qid, did in zip(nqr_tbl["query-id"].to_pylist(), nqr_tbl["corpus-id"].to_pylist()):
        nano_qrels[str(qid)].add(str(did))

    # Load fresh LongEmbed queries & qrels (kept untouched until after dev lock!)
    orig_q_map: Dict[str, str] = {}
    for line in (LONGEMBED_DIR / orig_task / "queries.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            orig_q_map[str(r["qid"])] = str(r["text"])

    fresh_items = fresh_split["fresh_items"]
    fresh_qids = [x["query_id"] for x in fresh_items]
    fresh_qrels: Dict[str, set] = {x["query_id"]: {x["relevant_doc_id"]} for x in fresh_items}
    fresh_groups = [x["relevant_doc_id"] for x in fresh_items]

    # 2. Build unchanged chunk BM25 index + same-scored local whole-doc BM25 index
    t0 = time.perf_counter()
    chunk_idx = stage0_core.SparseChunkBM25Index(doc_ids, doc_texts, chunk_words=256, k1=1.2, b=0.75)
    chunk_index_s = time.perf_counter() - t0

    t0 = time.perf_counter()
    wholedoc_idx = s1.LocalWholeDocBM25Index(doc_ids, doc_texts, k1=1.2, b=0.75, lucene_idf=True)
    wholedoc_index_s = time.perf_counter() - t0

    # 3. Fit CountConditionalTop3Calibrator STRICTLY on original unlabeled_bg_pool (ZERO qrels!)
    bg_qids = list(stage0_split["unlabeled_bg_pool"]["query_ids"])
    t0 = time.perf_counter()
    bg_chunk_sc = chunk_idx.score_queries_all_chunks([nano_q_map[q] for q in bg_qids])
    bg_feats = stage0_core.compute_doc_passage_features(
        bg_chunk_sc, chunk_idx.doc_chunk_starts, chunk_idx.doc_chunk_counts
    )
    bg_r_top3 = s1.robust_normalize_per_query(bg_feats["top3_mean"], upper_trim_frac=0.05)
    calibrator = s1.CountConditionalTop3Calibrator(
        bg_r_top3,
        chunk_idx.doc_chunk_counts,
        bandwidth_h=BANDWIDTH_H,
        tail_q=TAIL_Q,
        exclude_top_k_per_bg_query=EXCLUDE_TOP_K_BG,
    )
    bg_fit_s = time.perf_counter() - t0

    # 4. Score original dev (51q / 52q) and lock ALL hyperparameters SOLELY on dev!
    dev_qids = list(stage0_split["dev"]["query_ids"])
    t0 = time.perf_counter()
    dev_chunk_sc = chunk_idx.score_queries_all_chunks([nano_q_map[q] for q in dev_qids])
    dev_feats = stage0_core.compute_doc_passage_features(
        dev_chunk_sc, chunk_idx.doc_chunk_starts, chunk_idx.doc_chunk_counts
    )
    dev_maxp = dev_feats["maxp"]
    dev_top3 = dev_feats["top3_mean"]
    dev_r_top3 = s1.robust_normalize_per_query(dev_top3, upper_trim_frac=0.05)
    dev_c_tilde = calibrator.calibrate_unit_matched(dev_r_top3, chunk_idx.doc_chunk_counts)
    dev_bm25 = wholedoc_idx.score_queries([nano_q_map[q] for q in dev_qids])

    # Select gamma* in {0.25, 0.50, 0.75, 1.0} on original dev (ties broken toward larger gamma / purer calibration)
    gamma_dev_curve: Dict[str, float] = {}
    best_gamma = GAMMA_GRID[-1]
    best_gamma_ndcg = -1.0
    for g in GAMMA_GRID:
        sc_g = calibrator.score_interpolated(dev_r_top3, dev_c_tilde, gamma=g)
        rk_g = stage0_core.scores_to_rankings(sc_g, dev_qids, doc_ids)
        nd_g = float(np.mean(stage0_core.per_query_ndcg_at_k(rk_g, nano_qrels, dev_qids, k=10)))
        gamma_dev_curve[str(g)] = nd_g
        if nd_g > best_gamma_ndcg + 1e-12 or (abs(nd_g - best_gamma_ndcg) <= 1e-12 and g > best_gamma):
            best_gamma_ndcg = nd_g
            best_gamma = g
    dev_countcal_sc = calibrator.score_interpolated(dev_r_top3, dev_c_tilde, gamma=best_gamma)

    # Equal dev handling for RRF alpha* on Raw_Top3 and CountCal_Top3
    alpha_raw_curve: Dict[str, float] = {}
    best_alpha_raw = 0.5
    best_nd_raw = -1.0
    for a in ALPHA_GRID:
        rk_a = s1.rrf_fuse_score_matrices(dev_bm25, dev_top3, dev_qids, doc_ids, alpha_passage=a, rrf_k=RRF_K)
        nd_a = float(np.mean(stage0_core.per_query_ndcg_at_k(rk_a, nano_qrels, dev_qids, k=10)))
        alpha_raw_curve[str(a)] = nd_a
        if nd_a > best_nd_raw + 1e-12:
            best_nd_raw = nd_a
            best_alpha_raw = a

    alpha_cal_curve: Dict[str, float] = {}
    best_alpha_cal = 0.5
    best_nd_cal = -1.0
    for a in ALPHA_GRID:
        rk_a = s1.rrf_fuse_score_matrices(dev_bm25, dev_countcal_sc, dev_qids, doc_ids, alpha_passage=a, rrf_k=RRF_K)
        nd_a = float(np.mean(stage0_core.per_query_ndcg_at_k(rk_a, nano_qrels, dev_qids, k=10)))
        alpha_cal_curve[str(a)] = nd_a
        if nd_a > best_nd_cal + 1e-12:
            best_nd_cal = nd_a
            best_alpha_cal = a

    dev_ndcg10 = {
        "Raw_MaxP": float(np.mean(stage0_core.per_query_ndcg_at_k(stage0_core.scores_to_rankings(dev_maxp, dev_qids, doc_ids), nano_qrels, dev_qids, k=10))),
        "Raw_Top3": float(np.mean(stage0_core.per_query_ndcg_at_k(stage0_core.scores_to_rankings(dev_top3, dev_qids, doc_ids), nano_qrels, dev_qids, k=10))),
        "Local_WholeDoc_BM25": float(np.mean(stage0_core.per_query_ndcg_at_k(stage0_core.scores_to_rankings(dev_bm25, dev_qids, doc_ids), nano_qrels, dev_qids, k=10))),
        "CountCal_Top3": best_gamma_ndcg,
        "CountCal_Top3_PureGamma1_diagnostic": gamma_dev_curve["1.0"],
        "RRF_LocalBM25_plus_RawTop3": best_nd_raw,
        "RRF_LocalBM25_plus_CountCalTop3": best_nd_cal,
    }
    dev_tune_s = time.perf_counter() - t0

    # 5. Evaluate ONCE on the Fresh Independent LongEmbed Held-Out Split (75q / 75 distinct fresh docs)
    t0 = time.perf_counter()
    fresh_texts = [orig_q_map[q] for q in fresh_qids]
    fresh_chunk_sc = chunk_idx.score_queries_all_chunks(fresh_texts)
    fresh_feats = stage0_core.compute_doc_passage_features(
        fresh_chunk_sc, chunk_idx.doc_chunk_starts, chunk_idx.doc_chunk_counts
    )
    fresh_maxp = fresh_feats["maxp"]
    fresh_top3 = fresh_feats["top3_mean"]
    fresh_bm25 = wholedoc_idx.score_queries(fresh_texts)

    t_cal0 = time.perf_counter()
    fresh_r_top3 = s1.robust_normalize_per_query(fresh_top3, upper_trim_frac=0.05)
    fresh_c_tilde = calibrator.calibrate_unit_matched(fresh_r_top3, chunk_idx.doc_chunk_counts)
    fresh_countcal = calibrator.score_interpolated(fresh_r_top3, fresh_c_tilde, gamma=best_gamma)
    fresh_countcal_only_s = time.perf_counter() - t_cal0
    fresh_score_s = time.perf_counter() - t0

    rankings = {
        "Raw_MaxP": stage0_core.scores_to_rankings(fresh_maxp, fresh_qids, doc_ids),
        "Raw_Top3": stage0_core.scores_to_rankings(fresh_top3, fresh_qids, doc_ids),
        "Local_WholeDoc_BM25": stage0_core.scores_to_rankings(fresh_bm25, fresh_qids, doc_ids),
        "CountCal_Top3": stage0_core.scores_to_rankings(fresh_countcal, fresh_qids, doc_ids),
        "RRF_LocalBM25_plus_RawTop3": s1.rrf_fuse_score_matrices(
            fresh_bm25, fresh_top3, fresh_qids, doc_ids, alpha_passage=best_alpha_raw, rrf_k=RRF_K
        ),
        "RRF_LocalBM25_plus_CountCalTop3": s1.rrf_fuse_score_matrices(
            fresh_bm25, fresh_countcal, fresh_qids, doc_ids, alpha_passage=best_alpha_cal, rrf_k=RRF_K
        ),
    }

    per_q_ndcg: Dict[str, np.ndarray] = {
        m: stage0_core.per_query_ndcg_at_k(rk, fresh_qrels, fresh_qids, k=10)
        for m, rk in rankings.items()
    }
    # Also log pure gamma=1.0 transparently if best_gamma != 1.0 (diagnostic reference only)
    pure_g1_ndcg = stage0_core.per_query_ndcg_at_k(
        stage0_core.scores_to_rankings(fresh_c_tilde, fresh_qids, doc_ids), fresh_qrels, fresh_qids, k=10
    )

    # Freeze per-query fresh held-out JSONL immediately
    jsonl_name = f"Fresh{nano_task.replace('Nano', '')}_natural_per_query.jsonl"
    jsonl_path = OUT_DIR / jsonl_name
    lines = []
    for qi, item in enumerate(fresh_items):
        qid = item["query_id"]
        did = item["relevant_doc_id"]
        row = {
            "task": nano_task,
            "source_task": orig_task,
            "query_id": qid,
            "relevant_doc_id": did,
            "relevant_doc_chunk_count": int(chunk_idx.doc_chunk_counts[doc_to_idx[did]]),
            "ndcg10": {m: float(per_q_ndcg[m][qi]) for m in rankings},
            "ndcg10_pure_gamma1_diagnostic": float(pure_g1_ndcg[qi]),
        }
        lines.append(json.dumps(row))
    jsonl_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    jsonl_sha = sha256_file(jsonl_path)

    fresh_ndcg10 = {m: float(np.mean(vals)) for m, vals in per_q_ndcg.items()}
    fresh_ndcg10["CountCal_Top3_PureGamma1_diagnostic"] = float(np.mean(pure_g1_ndcg))

    # Paired cluster-bootstrap CIs (75 distinct fresh doc clusters, 5000 draws)
    comparisons = [
        ("CountCal_Top3_vs_Raw_Top3", "CountCal_Top3", "Raw_Top3"),
        ("CountCal_Top3_vs_Raw_MaxP", "CountCal_Top3", "Raw_MaxP"),
        ("CountCal_Top3_vs_Local_WholeDoc_BM25", "CountCal_Top3", "Local_WholeDoc_BM25"),
        ("Raw_Top3_vs_Raw_MaxP", "Raw_Top3", "Raw_MaxP"),
        ("Raw_Top3_vs_Local_WholeDoc_BM25", "Raw_Top3", "Local_WholeDoc_BM25"),
        ("RRF_CountCalTop3_vs_RRF_RawTop3", "RRF_LocalBM25_plus_CountCalTop3", "RRF_LocalBM25_plus_RawTop3"),
        ("RRF_CountCalTop3_vs_Local_WholeDoc_BM25", "RRF_LocalBM25_plus_CountCalTop3", "Local_WholeDoc_BM25"),
        ("RRF_CountCalTop3_vs_Raw_Top3", "RRF_LocalBM25_plus_CountCalTop3", "Raw_Top3"),
        ("RRF_RawTop3_vs_Local_WholeDoc_BM25", "RRF_LocalBM25_plus_RawTop3", "Local_WholeDoc_BM25"),
    ]
    boot_cis = {
        label: stage0_core.cluster_paired_bootstrap_diff(
            per_q_ndcg[a], per_q_ndcg[b], fresh_groups, n_boot=N_BOOT, seed=BOOT_SEED
        )
        for label, a, b in comparisons
    }

    # Natural non-relevant length-bias diagnostic (strictly separate, NOT benchmark progress)
    length_bias_diag = {
        "Raw_MaxP": nonrel_length_bias_diagnostic(fresh_maxp, fresh_qids, doc_ids, chunk_idx.doc_chunk_counts, fresh_qrels),
        "Raw_Top3": nonrel_length_bias_diagnostic(fresh_top3, fresh_qids, doc_ids, chunk_idx.doc_chunk_counts, fresh_qrels),
        "Local_WholeDoc_BM25": nonrel_length_bias_diagnostic(fresh_bm25, fresh_qids, doc_ids, chunk_idx.doc_chunk_counts, fresh_qrels),
        "CountCal_Top3": nonrel_length_bias_diagnostic(fresh_countcal, fresh_qids, doc_ids, chunk_idx.doc_chunk_counts, fresh_qrels),
    }

    # Relevant-doc chunk count summary on fresh split
    fresh_rel_ns = np.array([int(chunk_idx.doc_chunk_counts[doc_to_idx[x["relevant_doc_id"]]]) for x in fresh_items])
    task_total_s = time.perf_counter() - t_task0

    return {
        "task": nano_task,
        "source_task": orig_task,
        "corpus_size": len(doc_ids),
        "total_chunks": int(chunk_idx.n_chunks),
        "candidate_recall_all_methods": 1.0,
        "fresh_eval_n_queries": len(fresh_qids),
        "fresh_eval_n_distinct_doc_groups": len(set(fresh_groups)),
        "fresh_rel_doc_chunk_stats": {
            "min": int(fresh_rel_ns.min()),
            "p25": float(np.percentile(fresh_rel_ns, 25)),
            "p50": float(np.median(fresh_rel_ns)),
            "p75": float(np.percentile(fresh_rel_ns, 75)),
            "max": int(fresh_rel_ns.max()),
        },
        "calibrator_bg_stats": {
            "bg_queries": len(bg_qids),
            "bandwidth_h_fixed": BANDWIDTH_H,
            "tail_q_fixed": TAIL_Q,
            "exclude_top_k_per_bg_query": EXCLUDE_TOP_K_BG,
            "beta_global": float(calibrator.beta_global),
        },
        "dev_locked_hyperparameters": {
            "gamma_countcal_top3": best_gamma,
            "gamma_dev_curve": gamma_dev_curve,
            "alpha_rrf_raw_top3": best_alpha_raw,
            "alpha_rrf_raw_top3_dev_curve": alpha_raw_curve,
            "alpha_rrf_countcal_top3": best_alpha_cal,
            "alpha_rrf_countcal_top3_dev_curve": alpha_cal_curve,
        },
        "dev_ndcg10": dev_ndcg10,
        "fresh_heldout_natural_ndcg10": fresh_ndcg10,
        "fresh_heldout_per_query_jsonl": jsonl_name,
        "fresh_heldout_per_query_sha256": jsonl_sha,
        "fresh_paired_cluster_bootstrap": boot_cis,
        "natural_nonrel_length_bias_DIAGNOSTIC_ONLY": length_bias_diag,
        "runtime_s": {
            "chunk_index_s": chunk_index_s,
            "wholedoc_index_s": wholedoc_index_s,
            "bg_calibrator_fit_s": bg_fit_s,
            "dev_score_and_tune_s": dev_tune_s,
            "fresh_score_all_s": fresh_score_s,
            "fresh_countcal_only_s": fresh_countcal_only_s,
            "task_total_s": task_total_s,
        },
    }


def main() -> None:
    t_all0 = time.perf_counter()
    stage0_splits = json.loads((PROJ / "HAKARI_STAGE0_SPLITS_RECEIPT.json").read_text(encoding="utf-8"))
    fresh_splits = json.loads((PROJ / "STAGE1_FRESH_SPLITS_RECEIPT.json").read_text(encoding="utf-8"))

    protocol_path = PROJ / "STAGE1_COUNTCAL_TOP3_PROTOCOL.md"
    assert protocol_path.exists(), "STAGE1_COUNTCAL_TOP3_PROTOCOL.md must be locked before running!"
    protocol_sha = sha256_file(protocol_path)

    tasks_out = {}
    for nano_task, orig_task in [("NanoQMSum", "qmsum"), ("NanoNarrativeQA", "narrativeqa")]:
        tasks_out[nano_task] = run_task(
            nano_task, orig_task, stage0_splits[nano_task], fresh_splits["tasks"][nano_task]
        )

    methods = [
        "Raw_MaxP",
        "Raw_Top3",
        "Local_WholeDoc_BM25",
        "CountCal_Top3",
        "CountCal_Top3_PureGamma1_diagnostic",
        "RRF_LocalBM25_plus_RawTop3",
        "RRF_LocalBM25_plus_CountCalTop3",
    ]
    macro_fresh = {
        m: 0.5 * (
            tasks_out["NanoQMSum"]["fresh_heldout_natural_ndcg10"][m]
            + tasks_out["NanoNarrativeQA"]["fresh_heldout_natural_ndcg10"][m]
        )
        for m in methods
    }

    def eval_gate(candidate: str, baselines: List[str]) -> Dict[str, Any]:
        best_per_task = {
            t: max(baselines, key=lambda b: tasks_out[t]["fresh_heldout_natural_ndcg10"][b])
            for t in ["NanoQMSum", "NanoNarrativeQA"]
        }
        best_macro_b = max(baselines, key=lambda b: macro_fresh[b])
        g_q = (
            tasks_out["NanoQMSum"]["fresh_heldout_natural_ndcg10"][candidate]
            - tasks_out["NanoQMSum"]["fresh_heldout_natural_ndcg10"][best_per_task["NanoQMSum"]]
        )
        g_n = (
            tasks_out["NanoNarrativeQA"]["fresh_heldout_natural_ndcg10"][candidate]
            - tasks_out["NanoNarrativeQA"]["fresh_heldout_natural_ndcg10"][best_per_task["NanoNarrativeQA"]]
        )
        macro_vs_best_macro = macro_fresh[candidate] - macro_fresh[best_macro_b]
        macro_vs_per_task_best = 0.5 * (g_q + g_n)
        improves_both = (g_q > 0.0) and (g_n > 0.0)
        passes = improves_both and (macro_vs_best_macro >= 0.030) and (macro_vs_per_task_best >= 0.030)
        return {
            "candidate": candidate,
            "comparable_baselines": baselines,
            "strongest_baseline_per_task": best_per_task,
            "strongest_baseline_macro": best_macro_b,
            "gain_QMSum_vs_per_task_best": g_q,
            "gain_NarrativeQA_vs_per_task_best": g_n,
            "macro_gain_vs_strongest_macro_baseline": macro_vs_best_macro,
            "macro_gain_vs_per_task_best": macro_vs_per_task_best,
            "improves_both_tasks": improves_both,
            "passes_gate_ge_0.030": passes,
        }

    gate_passage = eval_gate("CountCal_Top3", ["Raw_MaxP", "Raw_Top3"])
    gate_standalone = eval_gate("CountCal_Top3", ["Raw_MaxP", "Raw_Top3", "Local_WholeDoc_BM25"])
    gate_rrf = eval_gate(
        "RRF_LocalBM25_plus_CountCalTop3",
        ["Raw_MaxP", "Raw_Top3", "Local_WholeDoc_BM25", "RRF_LocalBM25_plus_RawTop3"],
    )
    any_pass = (
        gate_passage["passes_gate_ge_0.030"]
        or gate_standalone["passes_gate_ge_0.030"]
        or gate_rrf["passes_gate_ge_0.030"]
    )

    summary = {
        "protocol": "STAGE1_COUNTCAL_TOP3_PROTOCOL.md",
        "protocol_sha256": protocol_sha,
        "stage0_sealed_summary_sha256": sha256_file(PROJ / "stage0_pilot_outputs" / "hakari_stage0_summary.json"),
        "real_pid": os.getpid(),
        "cpu_only": True,
        "wall_time_s": time.perf_counter() - t_all0,
        "source_and_code_hashes": {
            "DATASET_DOWNLOAD_RECEIPT_json": sha256_file(PROJ / "DATASET_DOWNLOAD_RECEIPT.json"),
            "LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT_json": sha256_file(PROJ / "LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json"),
            "HAKARI_STAGE0_SPLITS_RECEIPT_json": sha256_file(PROJ / "HAKARI_STAGE0_SPLITS_RECEIPT.json"),
            "STAGE1_FRESH_SPLITS_RECEIPT_json": sha256_file(PROJ / "STAGE1_FRESH_SPLITS_RECEIPT.json"),
            "STAGE1_PARITY_AND_FIXTURES_RECEIPT_json": sha256_file(PROJ / "STAGE1_PARITY_AND_FIXTURES_RECEIPT.json"),
            "hakari_retrieval_core_py": sha256_file(PROJ / "hakari_retrieval_core.py"),
            "stage1_countcal_top3_core_py": sha256_file(PROJ / "stage1_countcal_top3_core.py"),
            "run_hakari_stage1_followup_py": sha256_file(PROJ / "run_hakari_stage1_followup.py"),
        },
        "macro_fresh_heldout_natural_ndcg10": macro_fresh,
        "prespecified_gates": {
            "criterion": "Natural fresh held-out nDCG@10 improves over strongest comparable baseline in BOTH QMSum (75q/75d) AND NarrativeQA (75q/75d) AND macro gain >= +0.030.",
            "passage_only_gate": gate_passage,
            "standalone_lexical_gate": gate_standalone,
            "rrf_fusion_gate": gate_rrf,
            "decision": "MEANINGFUL_NEW_SIGNAL" if any_pass else "CLOSE_NO_MEANINGFUL_GAIN",
        },
        "tasks": tasks_out,
    }

    out_path = OUT_DIR / "hakari_stage1_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    out_sha = sha256_file(out_path)

    print(f"Stage-1 native run DONE | PID={summary['real_pid']} | wall={summary['wall_time_s']:.2f}s | summary_sha256={out_sha}")
    print("\nMacro Fresh Held-Out nDCG@10 (75q/75d per task):")
    for m, v in macro_fresh.items():
        q = tasks_out["NanoQMSum"]["fresh_heldout_natural_ndcg10"][m]
        n = tasks_out["NanoNarrativeQA"]["fresh_heldout_natural_ndcg10"][m]
        print(f"  {m:38s}: QMSum={q:.4f} | NarrativeQA={n:.4f} | Macro={v:.4f}")
    print("\nGate decision:", summary["prespecified_gates"]["decision"])


if __name__ == "__main__":
    main()
