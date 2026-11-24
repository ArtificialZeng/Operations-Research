# Frozen Negative Archive: Length-Calibrated Lexical Passage Retrieval on HAKARI / LongEmbed (`QMSum` & `NarrativeQA`)

**Status:** **FROZEN — `CLOSE_NO_MEANINGFUL_GAIN` (2026-11-24)**  
**Scope:** Strictly scoped to `QMSum` (`197` docs) and `NarrativeQA` (`355` docs) under a fixed CPU-only lexical `W = 256`-word chunk BM25 pipeline. **Zero GPU, zero neural training, zero corpus/query/qrel text republication, no official benchmark score or contest entry, no PDFs/media.**

---

## 1. Executive Summary (Stage-0 & Stage-1 Natural Held-Out `nDCG@10`)

We tested whether training-free empirical count-conditional null calibration — calibrating a document's chunk-aggregated lexical BM25 score by the empirical chance that an unrelated document with the same chunk count $n_d$ reaches it (fitted strictly on disjoint unlabeled background queries with zero qrels) — improves natural held-out `nDCG@10` under a prespecified advancement gate (**improvement on BOTH tasks AND macro gain `>= +0.030`** over the strongest comparable frozen baseline):

| Stage & Cohort | Primary Comparison (`0–1` `nDCG@10`, `100%` recall) | `QMSum` | `NarrativeQA` | **Macro** | Gate Outcome |
|---|---|---:|---:|---:|---|
| **Stage-0** (`NanoLongEmbed`, `51q/31d` & `50q/41d`, `PID = 55912`) | `Empirical_CountCond_Null` (`MaxP`) vs. `Top3_Mean` / `Official_WholeDoc_BM25` | `0.7193` vs. `0.7563` / `0.8065` | `0.7755` vs. `0.8287` / `0.7901` | **`0.7474`** vs. **`0.7925`** / **`0.7983`** | **FAIL** (`-0.0451` / `-0.0509`) |
| **Stage-0 RRF** (`PID = 55912`) | `RRF_BM25_plus_EmpiricalNull` vs. `RRF_BM25_plus_MaxMinusLogN` | `0.7806` vs. `0.7808` | `0.8253` vs. `0.8331` | **`0.8030`** vs. **`0.8069`** | **FAIL** (`-0.0040`) |
| **Stage-1** (`LongEmbed` fresh `75q/75d` & `75q/75d`, `PID = 40612`) | `CountCal_Top3` ($\gamma^*=0.25$) vs. `Raw_Top3` | `0.826664` vs. `0.818848` (`+0.007816`) | `0.774978` vs. `0.777123` (`-0.002144`) | **`0.800821`** vs. **`0.797985`** (**`+0.002836`**) | **FAIL** (`< +0.030`, fails both-task) |
| **Stage-1 RRF** (`PID = 40612`) | `RRF_LocalBM25_plus_CountCalTop3` vs. `RRF_LocalBM25_plus_RawTop3` | `0.875959` vs. `0.880182` (`-0.004223`) | `0.770607` vs. `0.769368` (`+0.001239`) | **`0.823283`** vs. **`0.824775`** (**`-0.001492`**) | **FAIL** (`-0.001492`) |

- **Diagnostic-only notes (no post-hoc method choice):** Stage-1 logged pure un-shrunk $\gamma = 1.0$ (`0.806162` macro; `+0.008177` vs. `Raw_Top3`) strictly as a diagnostic — it was not selected on `dev` and still misses `+0.030` by nearly `4x`. Stage-0's artificial `+100`-chunk suffix stress was label-dependent negative-only padding and is kept strictly separate as diagnostic only.
- **Local BM25 disclosure:** Stage-1's `Local_WholeDoc_BM25` (`0.794546` macro: `0.844598` QMSum / `0.744493` NarrativeQA) uses the same Lucene-IDF (`k1=1.2, b=0.75`) lexical scorer as the chunk index and differs from HAKARI's reference `bm25s` Robertson-IDF rankings (`0.7993` vs. `0.7440` on all 200 original QMSum queries; `0.7546` vs. `0.7619` on NarrativeQA — full parity table in [`receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json`](./receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json)). This archive reports local CPU experiments only and makes no official benchmark or leaderboard claim.
- **What actually moved the needle:** Plain multi-passage `Raw_Top3` consistently outperformed `Raw_MaxP` on both fresh tasks (`+0.031912` macro: `0.797985` vs. `0.766074`) and fused cleanly with whole-doc BM25 via plain RRF (`0.824775` macro), while adding count-conditional null calibration yielded a null accuracy effect (`~90%` tied queries) despite reducing natural non-relevant length intrusion (`Q4/Q1`: `1.55x -> 1.35x` QMSum, `5.03x -> 3.22x` NarrativeQA).

---

## 2. Prior Art & Citations (No Priority or Leaderboard Claims)

- **MaxSim Length Bias:** Edy, Conti, & Macé ([arXiv:2603.26259](https://arxiv.org/abs/2603.26259)), OpenReview [`85a1LK7Unu`](https://openreview.net/pdf?id=85a1LK7Unu).
- **Benchmarks & Related Long-Context Retrieval:** HAKARI-Bench ([arXiv:2606.22778](https://arxiv.org/abs/2606.22778)), LongEmbed ([arXiv:2404.12096](https://arxiv.org/abs/2404.12096)), MPE ([arXiv:2606.23642](https://arxiv.org/abs/2606.23642)), DICE ([arXiv:2606.18781](https://arxiv.org/abs/2606.18781)), long-context positional bias ([IJCNLP 2025](https://aclanthology.org/2025.ijcnlp-long.46/)), and MaxP/SumP passage aggregation (Dai & Callan, SIGIR 2019).

---

## 3. Archive Map & Excluded Data Mirrors

- **Status & provenance:** [`STATUS.md`](./STATUS.md), [`PROVENANCE_AND_SCOPE.md`](./PROVENANCE_AND_SCOPE.md), [`MANIFEST.json`](./MANIFEST.json)
- **Locked pre-launch protocols:** [`protocols/STAGE0_HAKARI_PROTOCOL.md`](./protocols/STAGE0_HAKARI_PROTOCOL.md), [`protocols/STAGE1_COUNTCAL_TOP3_PROTOCOL.md`](./protocols/STAGE1_COUNTCAL_TOP3_PROTOCOL.md)
- **Reports (before/after & per-stage):** [`reports/BEFORE_AFTER_SUMMARY.md`](./reports/BEFORE_AFTER_SUMMARY.md), [`reports/STAGE0_HAKARI_RESULT.md`](./reports/STAGE0_HAKARI_RESULT.md), [`reports/STAGE1_COUNTCAL_TOP3_RESULT.md`](./reports/STAGE1_COUNTCAL_TOP3_RESULT.md)
- **Receipts (byte-identical):** [`receipts/`](./receipts/) (`6` JSON receipts covering pinned downloads, group-disjoint splits, exact 200/200 original-to-Nano mapping, BM25 parity, and synthetic fixtures)
- **Derived outputs (byte-identical, IDs & scores only — zero text):** [`outputs/`](./outputs/) (`hakari_stage0_summary.json`, `hakari_stage1_summary.json`, and `4` per-query `nDCG@10` JSONL ledgers)
- **Runnable CPU-only code:** [`code/`](./code/), [`requirements.txt`](./requirements.txt)

*Strictly excluded from this repository:* all corpus text parquets, raw query/qrel mirrors (`data/`, `data_longembed_stage1/`), HF README/tree snapshots, virtual environments (`.venv/`), caches (`__pycache__/`), internal desktop prompts, private local paths, and email addresses. Every external source file's exact pinned Hugging Face URL, commit revision, byte size, and verified SHA-256 hash is recorded in [`receipts/DATASET_DOWNLOAD_RECEIPT.json`](./receipts/DATASET_DOWNLOAD_RECEIPT.json), [`receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json`](./receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json), and [`MANIFEST.json`](./MANIFEST.json) so anyone can re-fetch public upstream data under its original terms and reproduce all runs locally.
