"""
CPU-only training-free long-document passage chunking, Okapi BM25 scorer,
baseline passage aggregators, analytical i.i.d. count-corrected null,
and empirical count-conditional null calibrator for HAKARI NanoLongEmbed.

Strict zero-leakage architecture:
  - Corpus text kept local as inert data (never republished).
  - Empirical count-conditional null fits strictly on disjoint unlabeled background queries
    (`Q_bg`, zero qrels ever read).
  - All scalar hyperparameters (lambda for max - lambda*log(n), bandwidth h for empirical null,
    and fusion alpha for BM25 RRF fusion) are selected ONLY on `dev` queries and frozen before
    scoring `heldout_test`.
"""
from __future__ import annotations

import math
import re
from collections import Counter
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import scipy.sparse as sp
import snowballstemmer

# Standard compact English stopword list (deterministic, zero external downloads)
ENGLISH_STOPWORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each", "few", "for",
    "from", "further", "had", "has", "have", "having", "he", "her", "here", "hers", "herself",
    "him", "himself", "his", "how", "i", "if", "in", "into", "is", "it", "its", "itself", "just",
    "me", "more", "most", "my", "myself", "no", "nor", "not", "now", "of", "off", "on", "once",
    "only", "or", "other", "our", "ours", "ourselves", "out", "over", "own", "s", "same", "she",
    "should", "so", "some", "such", "t", "than", "that", "the", "their", "theirs", "them",
    "themselves", "then", "there", "these", "they", "this", "those", "through", "to", "too",
    "under", "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "would", "you", "your", "yours", "yourself",
    "yourselves",
})

_TOKEN_RE = re.compile(r"[a-z0-9]+")
_STEMMER = snowballstemmer.stemmer("english")
_STEM_CACHE: Dict[str, str] = {}


def tokenize_english_porter_stop(text: str) -> List[str]:
    """Lowercase alphanumeric tokenization + English stopwords + English Snowball stemmer."""
    raw = _TOKEN_RE.findall(text.lower())
    out: List[str] = []
    for tok in raw:
        if tok in ENGLISH_STOPWORDS or len(tok) <= 1:
            continue
        st = _STEM_CACHE.get(tok)
        if st is None:
            st = _STEMMER.stemWord(tok)
            _STEM_CACHE[tok] = st
        out.append(st)
    return out


def chunk_document_words(text: str, chunk_words: int = 256) -> List[str]:
    """Fixed non-overlapping word-window chunking (`chunk_words = 256`)."""
    words = text.split()
    if not words:
        return [""]
    return [" ".join(words[i : i + chunk_words]) for i in range(0, len(words), chunk_words)]


class SparseChunkBM25Index:
    """
    Fast exact float64 Okapi BM25 index over all document chunks using SciPy CSR sparse matrices.
    Scores EVERY chunk of EVERY document in the corpus for any query (100% full-corpus recall).
    """

    def __init__(
        self,
        doc_ids: List[str],
        doc_texts: List[str],
        chunk_words: int = 256,
        k1: float = 1.2,
        b: float = 0.75,
        extra_chunks_per_doc: Optional[Dict[str, List[str]]] = None,
    ):
        self.doc_ids = list(doc_ids)
        self.n_docs = len(doc_ids)
        self.chunk_words = chunk_words
        self.k1 = k1
        self.b = b

        self.doc_chunk_starts = np.zeros(self.n_docs, dtype=np.int64)
        self.doc_chunk_counts = np.zeros(self.n_docs, dtype=np.int64)

        chunk_token_lists: List[List[str]] = []
        cursor = 0
        for i, (did, txt) in enumerate(zip(doc_ids, doc_texts)):
            chs = chunk_document_words(txt, chunk_words=chunk_words)
            if extra_chunks_per_doc and did in extra_chunks_per_doc:
                chs = chs + list(extra_chunks_per_doc[did])
            self.doc_chunk_starts[i] = cursor
            self.doc_chunk_counts[i] = len(chs)
            for c_txt in chs:
                chunk_token_lists.append(tokenize_english_porter_stop(c_txt))
            cursor += len(chs)

        self.n_chunks = cursor
        self.chunk_doc_idx = np.repeat(np.arange(self.n_docs, dtype=np.int64), self.doc_chunk_counts)

        # Build vocabulary, DF, and Okapi BM25 chunk-term CSR matrix [n_chunks, vocab]
        vocab: Dict[str, int] = {}
        df_counts: List[int] = []
        chunk_lens = np.zeros(self.n_chunks, dtype=np.float64)

        indptr = [0]
        indices: List[int] = []
        tfs: List[float] = []

        for c_idx, toks in enumerate(chunk_token_lists):
            chunk_lens[c_idx] = float(len(toks))
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
        self.avgdl = float(np.mean(chunk_lens)) if self.n_chunks > 0 else 1.0
        if self.avgdl <= 0.0:
            self.avgdl = 1.0

        df_arr = np.array(df_counts, dtype=np.float64)
        # Positive Robertson/Lucene BM25 IDF (non-negative -> zero score when no terms match)
        self.idf = np.log(1.0 + (self.n_chunks - df_arr + 0.5) / (df_arr + 0.5))

        # Fill normalized BM25 TF weights into CSR
        indptr_arr = np.array(indptr, dtype=np.int64)
        indices_arr = np.array(indices, dtype=np.int32)
        tfs_arr = np.array(tfs, dtype=np.float64)

        # Map each nonzero entry to its chunk length
        row_lengths = np.repeat(chunk_lens, np.diff(indptr_arr))
        denom = tfs_arr + k1 * (1.0 - b + b * (row_lengths / self.avgdl))
        bm25_tf_w = (tfs_arr * (k1 + 1.0)) / denom

        # Pre-multiply column IDF into matrix so scoring a query is a single sparse matvec!
        data_arr = bm25_tf_w * self.idf[indices_arr]
        self.chunk_matrix = sp.csr_matrix((data_arr, indices_arr, indptr_arr), shape=(self.n_chunks, self.n_vocab), dtype=np.float64)

    def score_queries_all_chunks(self, query_texts: List[str]) -> np.ndarray:
        """
        Returns dense float64 array of shape [n_queries, n_chunks] with exact BM25 chunk scores.
        (For n_queries=50..100 and n_chunks<=80,000, this uses <=64 MB RAM and runs in <0.2s!)
        """
        n_q = len(query_texts)
        q_indptr = [0]
        q_indices: List[int] = []
        q_data: List[float] = []
        for qt in query_texts:
            cnt = Counter(tokenize_english_porter_stop(qt))
            for term, tf in cnt.items():
                tid = self.vocab.get(term)
                if tid is not None:
                    q_indices.append(tid)
                    q_data.append(float(tf))
            q_indptr.append(len(q_indices))
        q_mat = sp.csr_matrix(
            (np.array(q_data, dtype=np.float64), np.array(q_indices, dtype=np.int32), np.array(q_indptr, dtype=np.int64)),
            shape=(n_q, self.n_vocab),
            dtype=np.float64,
        )
        # [n_q, n_vocab] @ [n_vocab, n_chunks] -> [n_q, n_chunks]
        prod = q_mat @ self.chunk_matrix.T
        return prod.toarray()


# ==============================================================================
# Passage Aggregators & Leave-One-Doc-Out Statistics (Zero Qrel Leakage)
# ==============================================================================

def compute_doc_passage_features(
    chunk_scores_q_c: np.ndarray,
    doc_chunk_starts: np.ndarray,
    doc_chunk_counts: np.ndarray,
) -> Dict[str, np.ndarray]:
    """
    Computes exact per-(query, doc) passage summaries from `chunk_scores_q_c` [Q, C]:
      - `maxp`: raw MaxP = max_{c in d} s(q, c)
      - `top3_mean`: mean of top min(3, n_d) chunk scores
      - `z_lodo`: leave-one-document-out standardized MaxP = (M_{q,d} - mu_{q,-d}) / sigma_{q,-d}
      - `analytical_iid_score`: -log(1 - (1 - p_{q,-d}(M_{q,d}))^{n_d}) using leave-one-doc-out
        empirical chunk tail with smooth POT exponential tail above 99th chunk percentile to
        prevent top-rank ceiling saturation!
    """
    n_q, n_c = chunk_scores_q_c.shape
    n_d = len(doc_chunk_starts)

    maxp = np.zeros((n_q, n_d), dtype=np.float64)
    top3_mean = np.zeros((n_q, n_d), dtype=np.float64)
    z_lodo = np.zeros((n_q, n_d), dtype=np.float64)
    analytical_iid = np.zeros((n_q, n_d), dtype=np.float64)

    # Precompute per-doc chunk sums & sum-of-squares for exact O(1) leave-one-doc-out mean/std
    total_sum = np.sum(chunk_scores_q_c, axis=1)      # [Q]
    total_sq = np.sum(chunk_scores_q_c ** 2, axis=1)  # [Q]

    for qi in range(n_q):
        sc = chunk_scores_q_c[qi]  # [C]
        sc_sorted = np.sort(sc)
        # 99th percentile threshold & exponential tail scale on all chunks for smooth extreme tail
        p99_idx = min(n_c - 1, max(0, int(math.floor(0.99 * n_c))))
        u99 = float(sc_sorted[p99_idx])
        exc99 = sc_sorted[sc_sorted > u99] - u99
        beta99 = float(np.mean(exc99)) if len(exc99) > 0 else 1.0
        if beta99 <= 1e-12:
            beta99 = 1.0
        p_u99 = float(np.mean(sc >= u99))
        p_u99 = max(p_u99, 0.5 / (n_c + 1.0))

        for di in range(n_d):
            st = int(doc_chunk_starts[di])
            cnt = int(doc_chunk_counts[di])
            d_sc = sc[st : st + cnt]

            # Raw MaxP & Top-3 mean
            m_val = float(np.max(d_sc))
            maxp[qi, di] = m_val
            if cnt <= 3:
                top3_mean[qi, di] = float(np.mean(d_sc))
            else:
                top3_mean[qi, di] = float(np.mean(np.partition(d_sc, cnt - 3)[cnt - 3 :]))

            # Exact leave-one-doc-out mean & std across all chunks NOT in doc di
            n_other = n_c - cnt
            s_doc = float(np.sum(d_sc))
            sq_doc = float(np.sum(d_sc * d_sc))
            if n_other > 1:
                mu_o = (total_sum[qi] - s_doc) / n_other
                var_o = max(0.0, (total_sq[qi] - sq_doc) / n_other - mu_o * mu_o)
                sig_o = math.sqrt(var_o)
            else:
                mu_o, sig_o = 0.0, 1.0
            if sig_o <= 1e-12:
                z_lodo[qi, di] = 0.0
            else:
                z_lodo[qi, di] = (m_val - mu_o) / sig_o

            # Leave-one-doc-out chunk tail probability p_{q,-d}(m_val) with mid-p tie handling
            # + smooth exponential tail continuation above u99 (prevents rank-1 ceiling saturation!)
            if m_val <= 0.0:
                # Sparse zero score -> p = 1.0 -> -log(1 - 0) = 0.0
                analytical_iid[qi, di] = 0.0
            else:
                # Count strictly greater & equal across ALL chunks via binary search, minus doc's own chunks
                idx_hi = int(np.searchsorted(sc_sorted, m_val, side="right"))
                idx_lo = int(np.searchsorted(sc_sorted, m_val, side="left"))
                gt_all = n_c - idx_hi
                eq_all = idx_hi - idx_lo

                gt_doc = int(np.sum(d_sc > m_val))
                eq_doc = int(np.sum(d_sc == m_val))

                gt_other = max(0, gt_all - gt_doc)
                eq_other = max(0, eq_all - eq_doc)

                p_emp = (0.5 + gt_other + 0.5 * eq_other) / (1.0 + max(1, n_other))
                if m_val > u99 and gt_other < 5:
                    # Smooth POT exponential tail beyond u99 so extreme top-1/top-2 never tie-saturate
                    log_p_tail = math.log(p_u99) - (m_val - u99) / beta99
                    # Combine smoothly: take min(p_emp, exp(log_p_tail)) in log space
                    log_p = min(math.log(p_emp), log_p_tail)
                else:
                    log_p = math.log(p_emp)

                # Compute -log(1 - (1 - p)^n) stably in log space:
                # let a = n * log(1 - p); if p is tiny, log(1-p) ~ -p => a ~ -n*p
                if log_p < -20.0:
                    # p < 2e-9 -> 1 - (1-p)^n ~= n * p => -log(P) ~= -log(n) - log(p)
                    neg_log_prob = -math.log(float(cnt)) - log_p
                else:
                    p_val = math.exp(log_p)
                    if p_val >= 1.0 - 1e-15:
                        neg_log_prob = 0.0
                    else:
                        a = cnt * math.log1p(-p_val)
                        # 1 - exp(a) = -expm1(a)
                        one_minus_exp_a = -math.expm1(a)
                        neg_log_prob = -math.log(max(one_minus_exp_a, 1e-300))
                analytical_iid[qi, di] = max(0.0, neg_log_prob)

    return {
        "maxp": maxp,
        "top3_mean": top3_mean,
        "z_lodo": z_lodo,
        "analytical_iid": analytical_iid,
    }


class EmpiricalCountConditionalCalibrator:
    """
    Fixed Empirical Count-Conditional Null Calibrator.

    Estimates P_null(Z >= z | log(n_d)) purely from the disjoint UNLABELED background query
    pool `Q_bg` (zero qrels read!) scored on real corpus documents (capturing real within-doc
    chunk dependence and sparse zero mass!), using:
      - Gaussian kernel weights in log(n_d) space with bandwidth `h` (selected ONLY on dev),
      - Mid-p tie-handled empirical survival probability for z <= q_tail(n_d),
      - Smooth count-conditional Peaks-Over-Threshold (POT) exponential continuation above
        the 98th weighted quantile q_98(n_d) so top-10 rankings never suffer empirical ceiling ties.
    Returns calibrated relevance score = -log(P_null(Z >= z_{q,d} | n_d)) >= 0.
    """

    def __init__(self, bg_z_q_d: np.ndarray, bg_doc_chunk_counts: np.ndarray, bandwidth_h: float = 0.50, tail_q: float = 0.98):
        self.bandwidth_h = float(bandwidth_h)
        self.tail_q = float(tail_q)
        self.bg_log_n_docs = np.log(np.maximum(1.0, bg_doc_chunk_counts.astype(np.float64)))  # [D_bg]
        self.n_bg_q, self.n_bg_d = bg_z_q_d.shape
        # Flatten background pairs grouped by document so kernel weighting per target n_d is fast!
        self.bg_z_q_d = bg_z_q_d.astype(np.float64)
        self._cache: Dict[int, Dict[str, Any]] = {}

    def _get_count_profile(self, n_chunks: int) -> Dict[str, Any]:
        if n_chunks in self._cache:
            return self._cache[n_chunks]

        target_log_n = math.log(max(1.0, float(n_chunks)))
        doc_w = np.exp(-0.5 * ((self.bg_log_n_docs - target_log_n) / self.bandwidth_h) ** 2)  # [D_bg]
        # Repeat doc weights across all n_bg_q unlabeled background queries
        flat_z = self.bg_z_q_d.reshape(-1)
        flat_w = np.tile(doc_w, self.n_bg_q)

        order = np.argsort(flat_z, kind="mergesort")
        z_sorted = flat_z[order]
        w_sorted = flat_w[order]
        w_cum = np.cumsum(w_sorted)
        w_tot = float(w_cum[-1])

        # Weighted tail quantile u0 at self.tail_q (e.g. 98th percentile)
        q_idx = int(np.searchsorted(w_cum, self.tail_q * w_tot, side="left"))
        q_idx = min(len(z_sorted) - 1, max(0, q_idx))
        u0 = float(z_sorted[q_idx])

        # Weighted POT exponential exceedance scale beta above u0
        mask_tail = z_sorted > u0
        if np.any(mask_tail):
            w_tail = w_sorted[mask_tail]
            exc = z_sorted[mask_tail] - u0
            beta = float(np.sum(w_tail * exc) / np.sum(w_tail))
            # Exact weighted survival probability at u0
            s_u0 = (1.0 + float(np.sum(w_tail))) / (1.0 + w_tot)
        else:
            beta = 1.0
            s_u0 = 1.0 / (1.0 + w_tot)
        if beta <= 1e-8:
            beta = max(1e-4, float(np.std(z_sorted)) * 0.1)

        prof = {
            "z_sorted": z_sorted,
            "w_cum": w_cum,
            "w_tot": w_tot,
            "u0": u0,
            "beta": beta,
            "neg_log_s_u0": -math.log(max(s_u0, 1e-300)),
        }
        self._cache[n_chunks] = prof
        return prof

    def calibrate_matrix(self, z_q_d: np.ndarray, doc_chunk_counts: np.ndarray) -> np.ndarray:
        """Calibrates z_q_d [Q, D] using exact empirical count-conditional null profiles."""
        n_q, n_d = z_q_d.shape
        out = np.zeros((n_q, n_d), dtype=np.float64)

        for di in range(n_d):
            prof = self._get_count_profile(int(doc_chunk_counts[di]))
            z_sorted = prof["z_sorted"]
            w_cum = prof["w_cum"]
            w_tot = prof["w_tot"]
            u0 = prof["u0"]
            beta = prof["beta"]
            neg_log_s_u0 = prof["neg_log_s_u0"]

            col = z_q_d[:, di]
            # Vectorized mid-p empirical survival for body + POT continuation for z > u0
            hi_idx = np.searchsorted(z_sorted, col, side="right")
            lo_idx = np.searchsorted(z_sorted, col, side="left")

            w_le_hi = np.where(hi_idx > 0, w_cum[np.maximum(0, hi_idx - 1)], 0.0)
            w_lt_lo = np.where(lo_idx > 0, w_cum[np.maximum(0, lo_idx - 1)], 0.0)
            w_gt = np.maximum(0.0, w_tot - w_le_hi)
            w_eq = np.maximum(0.0, w_le_hi - w_lt_lo)

            s_emp = (1.0 + w_gt + 0.5 * w_eq) / (1.0 + w_tot)
            neg_log_emp = -np.log(np.maximum(s_emp, 1e-300))

            # Smooth POT tail continuation for col > u0
            pot_val = neg_log_s_u0 + np.maximum(0.0, col - u0) / beta
            out[:, di] = np.where(col > u0, np.maximum(neg_log_emp, pot_val), neg_log_emp)

        return out


# ==============================================================================
# Official HAKARI nDCG@10 & Paired Clustered Bootstrap Inference
# ==============================================================================

def scores_to_rankings(scores_q_d: np.ndarray, query_ids: List[str], doc_ids: List[str]) -> Dict[str, List[str]]:
    """Deterministic descending sort (tie-broken by doc_id order via stable mergesort)."""
    rankings: Dict[str, List[str]] = {}
    for qi, qid in enumerate(query_ids):
        order = np.argsort(-scores_q_d[qi], kind="mergesort")
        rankings[qid] = [doc_ids[idx] for idx in order]
    return rankings


def per_query_ndcg_at_k(rankings: Dict[str, List[str]], qrels: Dict[str, set], query_ids: List[str], k: int = 10) -> np.ndarray:
    """Official HAKARI binary nDCG@k (0-1 scale) per query."""
    vals = np.zeros(len(query_ids), dtype=np.float64)
    for i, qid in enumerate(query_ids):
        rels = qrels.get(qid, set())
        if not rels:
            continue
        ranked = rankings.get(qid, [])[:k]
        dcg = 0.0
        for rank_idx, did in enumerate(ranked, start=1):
            if did in rels:
                dcg += 1.0 / math.log2(rank_idx + 1.0)
        ideal = sum(1.0 / math.log2(r + 1.0) for r in range(1, min(len(rels), k) + 1))
        vals[i] = (dcg / ideal) if ideal > 0.0 else 0.0
    return vals


def rrf_fuse_official_bm25_with_scores(
    official_bm25_rankings: Dict[str, List[str]],
    passage_scores_q_d: np.ndarray,
    query_ids: List[str],
    doc_ids: List[str],
    alpha_passage: float,
    rrf_k: int = 60,
) -> Dict[str, List[str]]:
    """
    Training-free Reciprocal Rank Fusion between official whole-document BM25 ranking
    and a chunk-aggregated ranking:
      RRF(d) = (1 - alpha_passage) / (rrf_k + rank_bm25(d)) + alpha_passage / (rrf_k + rank_passage(d))
    """
    doc_to_idx = {did: i for i, did in enumerate(doc_ids)}
    n_d = len(doc_ids)
    out: Dict[str, List[str]] = {}
    for qi, qid in enumerate(query_ids):
        p_order = np.argsort(-passage_scores_q_d[qi], kind="mergesort")
        p_rank = np.empty(n_d, dtype=np.float64)
        p_rank[p_order] = np.arange(1, n_d + 1, dtype=np.float64)

        b_rank = np.full(n_d, float(n_d + 1), dtype=np.float64)
        for r_idx, did in enumerate(official_bm25_rankings.get(qid, []), start=1):
            d_i = doc_to_idx.get(did)
            if d_i is not None:
                b_rank[d_i] = float(r_idx)

        fused = (1.0 - alpha_passage) / (rrf_k + b_rank) + alpha_passage / (rrf_k + p_rank)
        f_order = np.argsort(-fused, kind="mergesort")
        out[qid] = [doc_ids[idx] for idx in f_order]
    return out


def cluster_paired_bootstrap_diff(
    a_vals: np.ndarray,
    b_vals: np.ndarray,
    groups: List[str],
    n_boot: int = 5000,
    seed: int = 20261124,
) -> Dict[str, Any]:
    """Cluster-resampled paired bootstrap (clustered by relevant-doc group) for mean(a - b)."""
    rng = np.random.default_rng(seed)
    g_to_idx: Dict[str, List[int]] = {}
    for i, g in enumerate(groups):
        g_to_idx.setdefault(g, []).append(i)
    g_keys = sorted(g_to_idx.keys())
    n_g = len(g_keys)

    diffs = a_vals - b_vals
    point = float(np.mean(diffs))
    boot = np.zeros(n_boot, dtype=np.float64)
    for b in range(n_boot):
        drawn = rng.integers(0, n_g, size=n_g)
        idxs = [i for k in drawn for i in g_to_idx[g_keys[k]]]
        boot[b] = float(np.mean(diffs[idxs]))
    lo, hi = np.percentile(boot, [2.5, 97.5])
    return {
        "mean_a": float(np.mean(a_vals)),
        "mean_b": float(np.mean(b_vals)),
        "diff_a_minus_b": point,
        "ci95_cluster_bootstrap": [float(lo), float(hi)],
        "n_groups": n_g,
        "n_queries": len(a_vals),
        "n_wins_a_gt_b": int(np.sum(diffs > 1e-12)),
        "n_losses_a_lt_b": int(np.sum(diffs < -1e-12)),
        "n_ties": int(np.sum(np.abs(diffs) <= 1e-12)),
    }
