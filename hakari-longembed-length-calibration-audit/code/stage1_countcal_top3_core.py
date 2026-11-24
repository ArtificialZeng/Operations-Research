"""
Stage-1 Targeted Follow-Up Core Module:
  - Reuses unchanged Stage-0 `hakari_retrieval_core` chunks, tokenizer, and BM25 chunk scorer
    without modifying any Stage-0 file.
  - Adds `LocalWholeDocBM25Index` (exact same lexical BM25 scorer: `tokenize_english_porter_stop`,
    `k1=1.2`, `b=0.75`, positive Lucene IDF, query TF, 100% full-corpus recall).
  - Adds ONE targeted new method: `CountConditionalTop3Calibrator` applied to `Top3_Mean`
    after fixed score-only per-query 5%-upper-trimmed robust normalization, fitted strictly
    on original `unlabeled_bg_pool` (zero qrels read; score-only top-1 exclusion per bg query;
    fixed Gaussian kernel bandwidth h=0.50 in log(n_d); globally tied POT tail scale beta_global
    above u0(n_d) to prevent Stage-0 tail-slope distortion), with optional one-scalar dev-locked
    unit-matched interpolation weight gamma in {0.25, 0.50, 0.75, 1.0}.
"""
from __future__ import annotations

import math
from collections import Counter
from typing import Any, Dict, List

import numpy as np
import scipy.sparse as sp

import hakari_retrieval_core as stage0_core


class LocalWholeDocBM25Index:
    """
    Exact same-scored local whole-document Okapi BM25 index matching `SparseChunkBM25Index`:
      - Tokenizer: `stage0_core.tokenize_english_porter_stop`
      - Parameters: `k1 = 1.2`, `b = 0.75`, positive Lucene IDF `log(1 + (N - df + 0.5) / (df + 0.5))`
      - Query term frequency weighting; scores 100% of corpus documents.
    Explicitly labeled as `Local_WholeDoc_BM25` on fresh queries (not official precomputed parquet).
    """

    def __init__(
        self,
        doc_ids: List[str],
        doc_texts: List[str],
        k1: float = 1.2,
        b: float = 0.75,
        lucene_idf: bool = True,
    ):
        self.doc_ids = list(doc_ids)
        self.n_docs = len(doc_ids)
        self.k1 = float(k1)
        self.b = float(b)
        self.lucene_idf = bool(lucene_idf)

        vocab: Dict[str, int] = {}
        df_counts: List[int] = []
        doc_lens = np.zeros(self.n_docs, dtype=np.float64)
        indptr = [0]
        indices: List[int] = []
        tfs: List[float] = []

        for di, txt in enumerate(doc_texts):
            toks = stage0_core.tokenize_english_porter_stop(txt)
            doc_lens[di] = float(len(toks))
            cnt = Counter(toks)
            for term, tf in cnt.items():
                tid = vocab.get(term)
                if tid is None:
                    tid = len(vocab)
                    vocab[term] = tid
                    df_counts.append(1)
                else:
                    df_counts[tid] += 1
                indices.append(tid)
                tfs.append(float(tf))
            indptr.append(len(indices))

        self.vocab = vocab
        self.n_vocab = len(vocab)
        self.avgdl = float(np.mean(doc_lens)) if self.n_docs > 0 else 1.0
        if self.avgdl <= 0.0:
            self.avgdl = 1.0

        df_arr = np.array(df_counts, dtype=np.float64)
        if self.lucene_idf:
            self.idf = np.log(1.0 + (self.n_docs - df_arr + 0.5) / (df_arr + 0.5))
        else:
            self.idf = np.maximum(0.0, np.log((self.n_docs - df_arr + 0.5) / (df_arr + 0.5)))

        indptr_arr = np.array(indptr, dtype=np.int64)
        indices_arr = np.array(indices, dtype=np.int32)
        tfs_arr = np.array(tfs, dtype=np.float64)
        row_lengths = np.repeat(doc_lens, np.diff(indptr_arr))
        denom = tfs_arr + self.k1 * (1.0 - self.b + self.b * (row_lengths / self.avgdl))
        data_arr = ((tfs_arr * (self.k1 + 1.0)) / denom) * self.idf[indices_arr]
        self.doc_matrix = sp.csr_matrix(
            (data_arr, indices_arr, indptr_arr),
            shape=(self.n_docs, self.n_vocab),
            dtype=np.float64,
        )

    def score_queries(self, query_texts: List[str]) -> np.ndarray:
        """Returns exact float64 [n_queries, n_docs] BM25 score matrix."""
        n_q = len(query_texts)
        q_indptr = [0]
        q_indices: List[int] = []
        q_data: List[float] = []
        for qt in query_texts:
            cnt = Counter(stage0_core.tokenize_english_porter_stop(qt))
            for term, tf in cnt.items():
                tid = self.vocab.get(term)
                if tid is not None:
                    q_indices.append(tid)
                    q_data.append(float(tf))
            q_indptr.append(len(q_indices))
        q_mat = sp.csr_matrix(
            (
                np.array(q_data, dtype=np.float64),
                np.array(q_indices, dtype=np.int32),
                np.array(q_indptr, dtype=np.int64),
            ),
            shape=(n_q, self.n_vocab),
            dtype=np.float64,
        )
        return (q_mat @ self.doc_matrix.T).toarray()


def robust_normalize_per_query(scores_q_d: np.ndarray, upper_trim_frac: float = 0.05) -> np.ndarray:
    """
    Fixed per-query robust normalization strictly from document scores (zero qrels):
      - For each query q, excludes the top `m = max(2, floor(upper_trim_frac * D))` document
        scores so a high-scoring positive document cannot inflate location or scale.
      - Computes body mean `mu_q` and body std `sigma_q` on the remaining bottom (1 - 5%) body.
      - If the bottom 95% body is constant (e.g., ultra-sparse query with >95% zeros), falls
        back cleanly to full-query `std(scores[q])` (or `1.0` if all scores are equal).
      - Positive affine transform per query: strictly preserves within-query `Raw_Top3` order.
    """
    n_q, n_d = scores_q_d.shape
    out = np.zeros((n_q, n_d), dtype=np.float64)
    m_trim = min(max(2, int(math.floor(upper_trim_frac * n_d))), max(1, n_d - 2))
    n_body = n_d - m_trim

    for qi in range(n_q):
        row = scores_q_d[qi]
        s_sorted = np.sort(row)
        body = s_sorted[:n_body]
        mu = float(np.mean(body))
        sig = float(np.std(body))
        if sig <= 1e-12:
            sig_full = float(np.std(row))
            sig = sig_full if sig_full > 1e-12 else 1.0
        out[qi] = (row - mu) / sig
    return out


class CountConditionalTop3Calibrator:
    """
    Count-Conditional Null Calibrator for robust-normalized `Top3_Mean` evidence.

    Zero-leakage, fixed-parameter background fitting (strictly on original `unlabeled_bg_pool`,
    zero qrels read):
      1. Score-only top-1 exclusion per background query (`argmax_d bg_r[q, d]` masked out)
         to prevent unlabeled background positive matches from contaminating the null tail.
      2. Fixed Gaussian kernel weighting in `log(n_d)` space (`bandwidth_h = 0.50`, no sweep).
      3. Nonparametric mid-p weighted empirical survival up to each chunk-count's 98th weighted
         quantile `u0(n_d)`.
      4. Globally tied Peaks-Over-Threshold exponential tail scale `beta_global` estimated over
         all pooled masked exceedances `r - u0(n_d) > 0`, ensuring strict length monotonicity
         through the extreme tail without Stage-0's count-dependent slope compression.
      5. Unit-matched score `c_tilde = beta_global * (-log P_null(R >= r | n_d))` has slope 1.0
         in `r` in the extreme tail, enabling clean unit-matched interpolation with `r`:
           score_gamma(q, d) = (1 - gamma) * r_{q,d} + gamma * c_tilde_{q,d}.
    """

    def __init__(
        self,
        bg_r_q_d: np.ndarray,
        bg_doc_chunk_counts: np.ndarray,
        bandwidth_h: float = 0.50,
        tail_q: float = 0.98,
        exclude_top_k_per_bg_query: int = 1,
    ):
        self.bandwidth_h = float(bandwidth_h)
        self.tail_q = float(tail_q)
        self.exclude_top_k = int(exclude_top_k_per_bg_query)
        self.bg_log_n_docs = np.log(np.maximum(1.0, bg_doc_chunk_counts.astype(np.float64)))
        self.n_bg_q, self.n_bg_d = bg_r_q_d.shape

        # Build score-only mask excluding top-k highest-scoring docs per unlabeled background query
        keep_mask = np.ones((self.n_bg_q, self.n_bg_d), dtype=bool)
        if self.exclude_top_k > 0 and self.exclude_top_k < self.n_bg_d:
            for qi in range(self.n_bg_q):
                top_idx = np.argpartition(bg_r_q_d[qi], self.n_bg_d - self.exclude_top_k)[
                    self.n_bg_d - self.exclude_top_k :
                ]
                keep_mask[qi, top_idx] = False

        # Keep flattened masked background (r, doc_idx) pairs
        q_idx, d_idx = np.nonzero(keep_mask)
        self.flat_r = bg_r_q_d[q_idx, d_idx].astype(np.float64)
        self.flat_d_idx = d_idx.astype(np.int64)
        self.order = np.argsort(self.flat_r, kind="mergesort")
        self.r_sorted = self.flat_r[self.order]
        self.d_idx_sorted = self.flat_d_idx[self.order]

        # Precompute unique chunk-count u0(n) thresholds & globally tied POT scale beta_global
        self._base_cache: Dict[int, Dict[str, Any]] = {}
        unique_ns = sorted(set(int(x) for x in bg_doc_chunk_counts))
        doc_u0 = np.zeros(self.n_bg_d, dtype=np.float64)
        for n_val in unique_ns:
            self._get_base_profile(n_val)
        for di in range(self.n_bg_d):
            doc_u0[di] = self._base_cache[int(bg_doc_chunk_counts[di])]["u0"]

        # Pooled exceedances across all masked background pairs above their own doc's u0(n_d)
        u0_for_pairs = doc_u0[self.flat_d_idx]
        exc = self.flat_r - u0_for_pairs
        pos_exc = exc[exc > 0.0]
        if len(pos_exc) > 0:
            self.beta_global = float(np.mean(pos_exc))
        else:
            self.beta_global = max(1e-3, float(np.std(self.flat_r)) * 0.25)
        if self.beta_global <= 1e-8:
            self.beta_global = 1.0

    def _get_base_profile(self, n_chunks: int) -> Dict[str, Any]:
        if n_chunks in self._base_cache:
            return self._base_cache[n_chunks]

        target_log_n = math.log(max(1.0, float(n_chunks)))
        doc_w = np.exp(-0.5 * ((self.bg_log_n_docs - target_log_n) / self.bandwidth_h) ** 2)
        w_sorted = doc_w[self.d_idx_sorted]
        w_cum = np.cumsum(w_sorted)
        w_tot = float(w_cum[-1])

        q_idx = int(np.searchsorted(w_cum, self.tail_q * w_tot, side="left"))
        q_idx = min(len(self.r_sorted) - 1, max(0, q_idx))
        u0 = float(self.r_sorted[q_idx])

        # Exact weighted survival mass strictly above u0
        hi_u0 = int(np.searchsorted(self.r_sorted, u0, side="right"))
        w_le_u0 = float(w_cum[hi_u0 - 1]) if hi_u0 > 0 else 0.0
        w_gt_u0 = max(0.0, w_tot - w_le_u0)
        s_u0 = (1.0 + w_gt_u0) / (1.0 + w_tot)

        prof = {
            "w_cum": w_cum,
            "w_tot": w_tot,
            "u0": u0,
            "neg_log_s_u0": -math.log(max(s_u0, 1e-300)),
        }
        self._base_cache[n_chunks] = prof
        return prof

    def calibrate_unit_matched(self, r_q_d: np.ndarray, doc_chunk_counts: np.ndarray) -> np.ndarray:
        """
        Returns unit-matched calibrated Top-3 score matrix `c_tilde = beta_global * (-log P_null)`.
        Pure `CountCal_Top3` (gamma = 1.0) has identical ranking to `-log P_null(R >= r | n_d)`.
        """
        n_q, n_d = r_q_d.shape
        out = np.zeros((n_q, n_d), dtype=np.float64)
        r_sorted = self.r_sorted
        beta = self.beta_global

        for di in range(n_d):
            prof = self._get_base_profile(int(doc_chunk_counts[di]))
            w_cum = prof["w_cum"]
            w_tot = prof["w_tot"]
            u0 = prof["u0"]
            neg_log_s_u0 = prof["neg_log_s_u0"]

            col = r_q_d[:, di]
            hi_idx = np.searchsorted(r_sorted, col, side="right")
            lo_idx = np.searchsorted(r_sorted, col, side="left")

            w_le_hi = np.where(hi_idx > 0, w_cum[np.maximum(0, hi_idx - 1)], 0.0)
            w_lt_lo = np.where(lo_idx > 0, w_cum[np.maximum(0, lo_idx - 1)], 0.0)
            w_gt = np.maximum(0.0, w_tot - w_le_hi)
            w_eq = np.maximum(0.0, w_le_hi - w_lt_lo)

            s_emp = (1.0 + w_gt + 0.5 * w_eq) / (1.0 + w_tot)
            neg_log_emp = -np.log(np.maximum(s_emp, 1e-300))

            pot_val = neg_log_s_u0 + np.maximum(0.0, col - u0) / beta
            neg_log_p = np.where(col > u0, np.maximum(neg_log_emp, pot_val), neg_log_emp)
            out[:, di] = beta * neg_log_p

        return out

    def score_interpolated(
        self,
        r_q_d: np.ndarray,
        c_tilde_q_d: np.ndarray,
        gamma: float,
    ) -> np.ndarray:
        """Unit-matched convex interpolation between robust-normalized Raw_Top3 and CountCal_Top3."""
        g = float(gamma)
        return (1.0 - g) * r_q_d + g * c_tilde_q_d


def rrf_fuse_score_matrices(
    bm25_scores_q_d: np.ndarray,
    passage_scores_q_d: np.ndarray,
    query_ids: List[str],
    doc_ids: List[str],
    alpha_passage: float,
    rrf_k: int = 60,
) -> Dict[str, List[str]]:
    """
    Training-free Reciprocal Rank Fusion between two full-corpus score matrices:
      RRF(d) = (1 - alpha_passage) / (rrf_k + rank_bm25(d)) + alpha_passage / (rrf_k + rank_passage(d))
    """
    n_q, n_d = bm25_scores_q_d.shape
    out: Dict[str, List[str]] = {}
    a = float(alpha_passage)
    for qi, qid in enumerate(query_ids):
        b_order = np.argsort(-bm25_scores_q_d[qi], kind="mergesort")
        b_rank = np.empty(n_d, dtype=np.float64)
        b_rank[b_order] = np.arange(1, n_d + 1, dtype=np.float64)

        p_order = np.argsort(-passage_scores_q_d[qi], kind="mergesort")
        p_rank = np.empty(n_d, dtype=np.float64)
        p_rank[p_order] = np.arange(1, n_d + 1, dtype=np.float64)

        fused = (1.0 - a) / (rrf_k + b_rank) + a / (rrf_k + p_rank)
        f_order = np.argsort(-fused, kind="mergesort")
        out[qid] = [doc_ids[idx] for idx in f_order]
    return out
