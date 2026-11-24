# Stage-0 Locked Protocol — Training-Free Length-Calibrated Long-Document Retrieval (HAKARI NanoLongEmbed)

**Date Locked:** 2026-11-24 (BEFORE evaluating any held-out test scores)  
**Scope:** CPU-only training-free long-document retrieval pilot on **NanoQMSum** and **NanoNarrativeQA** ONLY (`hakari-bench/NanoLongEmbed`, pinned commit `ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e`). **Zero GPU, zero neural training, zero paid APIs, zero corpus republication (corpus text kept strictly local as inert data), zero public release/PDF/media/leaderboard claims.**

---

## 1. Source Terms, Provenance & Primary Prior Art (No Priority Claims)

- **Official Pinned Dataset:** `https://huggingface.co/datasets/hakari-bench/NanoLongEmbed`, revision `ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e` (derived from `dwzhu/LongEmbed`; all `14` task-specific files verified against official HF LFS SHA-256 in [`DATASET_DOWNLOAD_RECEIPT.json`](../receipts/DATASET_DOWNLOAD_RECEIPT.json), `2f27e90e...`). Corpus text is retained strictly locally as inert data.
- **Primary Competition / Prior Art:** HAKARI-Bench (`arXiv:2606.22778`), Multi-Prefix Embedding MPE (`arXiv:2606.23642`), DICE (`arXiv:2606.18781`), public notes on MaxSim length bias (`https://openreview.net/pdf?id=85a1LK7Unu`), long-context positional bias (`https://aclanthology.org/2025.ijcnlp-long.46/`), and longstanding MaxP/SumP passage aggregation (Dai & Callan, SIGIR 2019).

---

## 2. Relevant-Document-Group-Disjoint Three-Way Splits

Constructed deterministically in [`HAKARI_STAGE0_SPLITS_RECEIPT.json`](../receipts/HAKARI_STAGE0_SPLITS_RECEIPT.json) (`5d1118ea...`) by grouping queries by their exact relevant `corpus-id` (each query has `1` relevant doc) and sorting groups ascending by `sha256("hakari_stage0_split_20261124:" + task + ":" + doc_id)` with **ZERO query overlap and ZERO relevant-document overlap** across all three slices:
- **`NanoQMSum` (`197` docs, `200` queries, `122` doc groups):** `dev = 51` queries, `heldout_test = 51` queries, `unlabeled_bg_pool = 98` queries.
- **`NanoNarrativeQA` (`355` docs, `200` queries, `163` doc groups):** `dev = 52` queries, `heldout_test = 50` queries, `unlabeled_bg_pool = 98` queries.
- **Full-Corpus Ranking:** Every passage method ranks the **entire full corpus** (`197/197` docs in `NanoQMSum`, `355/355` docs in `NanoNarrativeQA`, **`100.0%` candidate recall**).

---

## 3. Shared Chunks, Scorer, Baselines & Candidate Calibrator

- **Chunks & Passage Scorer (identical across all 5 passage aggregators):** Fixed non-overlapping `W = 256`-word windows, English stopword + Snowball/Porter stemmer tokenization (`snowballstemmer 3.1.1`), exact float64 Okapi BM25 (`k1 = 1.2`, `b = 0.75`, positive Robertson IDF) over all chunks.
- **Zero-Leakage Background & Handling of Sparsity, Ties, and Within-Doc Dependence:**
  - For each query $q$ and document $d$ (chunk count $n_d$), compute the leave-one-document-out standardized passage max $z_{q,d} = (M_{q,d} - \mu_{q,-d}) / \sigma_{q,-d}$ (scale-invariant across query lengths `3..186` words, continuous through rank #1 without ceiling saturation, zero qrels used).
  - Estimate the count-conditional null distribution $P_{\text{null}}(Z \ge z \mid n_d)$ **strictly on the disjoint `unlabeled_bg_pool` (`98` queries × all corpus documents; qrels NEVER read!)** using real whole-document maxima (capturing real within-doc chunk dependence and sparse zero mass directly), Gaussian kernel weights in $\log n_d$ space (bandwidth $h \in \{0.35, 0.50, 0.75\}$ selected ONLY on `dev`), mid-p tie-handled empirical survival probability up to the `98th` weighted quantile $u_0(n_d)$, and smooth count-conditional POT exponential continuation above $u_0(n_d)$.
- **Methods Compared on Exact Same Held-Out Queries & Qrels (`nDCG@10`, `0–1`, exact parity verified in `HAKARI_STAGE0_FIXTURE_RECEIPT.json` `f1a7656e...`):**
  1. `Raw_MaxP` (fixed)
  2. `Top3_Mean` (fixed mean of top `min(3, n_d)` chunks)
  3. `MaxP_Minus_Lambda_LogN` ($\lambda \in \{0, 0.25, 0.5, 1, 1.5, 2, 3, 4, 6, 8\}$ selected ONLY on `dev`)
  4. `Analytical_IID_Null` ($-\log(1 - (1 - \hat{p}_{q,-d}(M_{q,d}))^{n_d})$ with mid-p ties + smooth 99th-percentile chunk POT tail)
  5. `Empirical_CountCond_Null` (Candidate Method; $h$ selected ONLY on `dev`, background strictly from `unlabeled_bg_pool`)
  6. `Official_WholeDoc_BM25` (official full-corpus BM25 ranking from `hakari-bench/NanoLongEmbed`)
  7. `Official_Hybrid_Top100_NoSafeguard` *(reported separately with scope note: uses external neural `harrier_oss_v1_270m` + BM25 RRF top-100, stripping rank-101 oracle safeguard)*
  8. Dev-tuned RRF fusion with `Official_WholeDoc_BM25` (`rrf_k = 60`, $\alpha \in \{0.0, 0.1, \dots, 1.0\}$ selected ONLY on `dev`): `RRF_BM25_plus_RawMaxP`, `RRF_BM25_plus_MaxMinusLogN`, `RRF_BM25_plus_EmpiricalNull`.

---

## 4. Mechanism Diagnostics & Prespecified Advancement Gate

- **Mechanism Diagnostics (run ONLY AFTER freezing natural held-out per-query outputs; NEVER counted as benchmark progress):**
  1. Natural non-relevant length-bias audit (Spearman $\rho(\text{score}, \log n_d)$ and `Q4` longest vs. `Q1` shortest non-relevant top-10 intrusion ratio).
  2. Artificial irrelevant-suffix control (`+100` unrelated chunks sampled deterministically from `dev`-only docs appended to every non-relevant doc on `heldout_test`).
- **Prespecified Advancement Gate:** Advance **ONLY IF** natural held-out `nDCG@10` improves in **BOTH** `NanoQMSum` AND `NanoNarrativeQA` AND macro-average improvement is **`>= +0.030`** over the strongest comparable frozen baseline (with relevant-doc-group-clustered paired bootstrap 95% CIs and CPU runtime); otherwise report a justified stop/adapt recommendation without cherry-picking.

---

## 5. Locked Pre-Launch SHA-256 Manifest

| File | SHA-256 |
|---|---|
| `DATASET_DOWNLOAD_RECEIPT.json` | `2f27e90e5d6cc95507f511ff003437e288db290393c1d1b616c7929cf1a03ab5` |
| `hakari_retrieval_core.py` | `1a936b34e6bd5546de8a677a7cdcd024107de69fa8649afa9e950680616885e3` |
| `build_hakari_splits_and_fixtures.py` | `31ae9258906438fbee526ef48174800a5e1e6eb4ea75e3d67709fe91b4f364dd` |
| `HAKARI_STAGE0_SPLITS_RECEIPT.json` | `5d1118ea1b2c9419a618890569c95aac4ee6e32b60d9447dfee710e043e5f8e8` |
| `HAKARI_STAGE0_FIXTURE_RECEIPT.json` | `f1a7656ef17a3b1f52c0eb08fdbbf76ee4afbb13d470ceb2d5f5066ec6174599` |
| `run_hakari_stage0_pilot.py` | `a0a49954ff63db745fb993994c57300a957505e1a0b8afecceda9f3ab47f4db5` |
