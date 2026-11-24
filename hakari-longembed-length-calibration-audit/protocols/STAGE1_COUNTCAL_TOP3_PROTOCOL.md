# Stage-1 Locked Protocol — Count-Calibrated Top-3 Evidence (`CountCal_Top3`) on Fresh Independent LongEmbed Query Groups

**Date Locked:** 2026-11-24 (BEFORE evaluating any fresh held-out query)  
**Stage-0 Sealed Anchor (Unaltered):** [`hakari_stage0_summary.json`](../outputs/hakari_stage0_summary.json) (`SHA-256: 2fee379490cd163d4924128822e8f6db40946f898cc6d13d13927c723cbb4876`, `PID = 55912`, natural macro `Empirical_CountCond_Null = 0.7474` vs. `Top3_Mean = 0.7925` and `Official_WholeDoc_BM25 = 0.7983`; `RRF_BM25_plus_EmpiricalNull = 0.8030` vs. `RRF_BM25_plus_MaxMinusLogN = 0.8069`). Stage-0 synthetic suffix stress was negative-only padding and label-dependent, so it remains strictly diagnostic only and is not used as benchmark evidence here.  
**Scope:** Strictly CPU-only, ONE targeted variant (`CountCal_Top3`) before deciding whether to freeze or close. Zero GPU, zero neural training, zero paid APIs, zero sweeps of `k`/methods/tasks, zero fresh-test-informed choices, zero corpus text republication (corpus text kept strictly local as inert data), zero new PDF/media/PR pending review.

---

## 1. Source Provenance, Exact Mapping & Fresh Disjoint Evaluation Split

- **Fresh Query/Qrel Source:** Official [`dwzhu/LongEmbed`](https://huggingface.co/datasets/dwzhu/LongEmbed), pinned commit `10039a580487dacecf79db69166e17ace3ede392` (exact `source_revision` recorded in HAKARI's `metadata/NanoQMSum.json` & `metadata/NanoNarrativeQA.json`). Downloaded ONLY the 4 original QA query/qrel files + `README.md` (LFS SHA-256 verified in [`LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json`](../receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json), `15bb9348...`).
- **Verified Exact Original-to-Nano Mapping & Full Exclusions** ([`STAGE1_FRESH_SPLITS_RECEIPT.json`](../receipts/STAGE1_FRESH_SPLITS_RECEIPT.json), `7b02ad57...`):
  - `200/200` direct query ID, exact query text, normalized query SHA-256 hash, and exact qrel `doc_id` match on both `QMSum` and `NarrativeQA` (`197/197` and `355/355` unique Nano corpus text hashes and exact `doc_id` set identity).
  - **Strict Exclusions (never relaxed):** Excluded ALL `200` Nano query IDs, ALL `200` Nano normalized query hashes, AND ALL `122` (`NanoQMSum`) / `163` (`NanoNarrativeQA`) Nano positive document groups — guaranteeing `0` overlap with `dev`, Stage-0 `heldout_test`, AND `unlabeled_bg_pool`.
  - **Deterministic 1:1 Group-Balanced Fresh Held-Out Split:**
    - `QMSum`: `559` fresh deduplicated queries across `75` fresh relevant docs -> selected **`75` fresh queries across `75` distinct fresh relevant docs** (`1` query per doc, ascending SHA-256 order).
    - `NarrativeQA`: `5,616` fresh deduplicated queries across `192` fresh relevant docs -> selected **`75` fresh queries across `75` distinct fresh relevant docs** (`1` query per doc, ascending SHA-256 order).
    - Both tasks satisfy `~60–80` fresh queries and `>= 20` fresh relevant doc groups (`75` independent clusters each).
- **Primary Related Literature (No Priority or Leaderboard Claims):** Edy, Conti, & Macé ([arXiv:2603.26259](https://arxiv.org/abs/2603.26259)) on late-interaction `MaxSim` length bias, HAKARI ([arXiv:2606.22778](https://arxiv.org/abs/2606.22778)) / LongEmbed ([arXiv:2404.12096](https://arxiv.org/abs/2404.12096)), MPE ([arXiv:2606.23642](https://arxiv.org/abs/2606.23642)), DICE ([arXiv:2606.18781](https://arxiv.org/abs/2606.18781)), and Dai & Callan (SIGIR 2019, MaxP/SumP).

---

## 2. Unchanged Corpora, Shared Scorer, Local Whole-Doc BM25 Parity & Targeted Method

- **Unchanged Corpora, Chunks & Lexical Scorer:** Exact same Nano corpora (`197` / `355` docs, `100%` full-corpus recall), exact same `W = 256`-word non-overlapping chunks and `SparseChunkBM25Index` (`hakari_retrieval_core.py`, `k1=1.2, b=0.75`, positive Lucene IDF, `tokenize_english_porter_stop`).
- **Same-Scored `Local_WholeDoc_BM25` Parity Verification** ([`STAGE1_PARITY_AND_FIXTURES_RECEIPT.json`](../receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json), `1f93c8ae...`):
  - Uses the exact same lexical scorer (`k1=1.2, b=0.75`, positive Lucene IDF, query TF, `tokenize_english_porter_stop`) over whole documents, explicitly labeled `Local_WholeDoc_BM25` on fresh queries.
  - Verified on all `200` original Nano queries vs. official `bm25/*.parquet`:
    - `NanoQMSum`: local `0.7993` vs. official `0.7440` (`+0.0552`, Top-1 agreement `159/200`, Top-10 Jaccard `0.6356`, per-query Spearman `0.8376`). (Diagnostic zero-clamped Robertson IDF `k1=1.5` matches official `bm25s` at `0.7555` vs. `0.7440`, `187/200` Top-1, Jaccard `0.8815`; our same-scored Lucene-IDF `Local_WholeDoc_BM25` is a strictly stronger whole-doc baseline on QMSum.)
    - `NanoNarrativeQA`: local `0.7546` vs. official `0.7619` (`-0.0073`, Top-1 agreement `155/200`, Top-10 Jaccard `0.6529`, per-query Spearman `0.7771`; diagnostic Robertson IDF `k1=1.5`: `0.7659`, `194/200` Top-1, Jaccard `0.8035`).
- **ONE Targeted New Method — `CountCal_Top3` (`stage1_countcal_top3_core.py`, `ba471679...`):**
  1. Evidence: exact same `Top3_Mean` (mean of top `min(3, n_d)` chunk BM25 scores; no sweep of `k`).
  2. Fixed score-only per-query robust normalization (`robust_normalize_per_query`): 5%-upper-trimmed body mean and std across the bottom `95%` of document scores (with full-std fallback if body std is 0; verified order-preserving even at `92.5%` and `99%` zeros; zero qrels).
  3. Count-conditional null calibration strictly from original Stage-0 `unlabeled_bg_pool` (`98` queries × $D$ docs, zero qrels read!): score-only top-1 exclusion per background query (`exclude_top_k = 1`), fixed Gaussian kernel in $\log n_d$ (`h = 0.50`, no bandwidth sweep), nonparametric mid-p survival up to weighted 98th quantile $u_0(n_d)$, and globally tied POT exponential tail scale $\beta_{\text{global}}$ above $u_0(n_d)$ (verified strictly monotone with zero short-vs-long tail crossover out to `r = 50`).
  4. Unit-matched score $\tilde{c}_{q,d} = \beta_{\text{global}} \cdot (-\log P_{\text{null}}(R \ge r_{q,d} \mid n_d))$ interpolated with $r_{q,d}$ via ONE dev-fixed weight $\gamma^* \in \{0.25, 0.50, 0.75, 1.0\}$ selected SOLELY on original Stage-0 `dev` (`51q` / `52q`; ties broken toward larger $\gamma$).
- **Matched Controls (Equal Dev Handling):**
  1. `Raw_MaxP` (0 dev params)
  2. `Raw_Top3` (0 dev params)
  3. `Local_WholeDoc_BM25` (0 dev params)
  4. `CountCal_Top3` (1 dev-locked scalar $\gamma^*$ on original `dev`)
  5. `RRF_LocalBM25_plus_RawTop3` (`rrf_k = 60`, 1 dev-locked scalar $\alpha^* \in \{0.0, 0.1, \dots, 1.0\}$ on original `dev`)
  6. `RRF_LocalBM25_plus_CountCalTop3` (`rrf_k = 60`, 1 dev-locked scalar $\alpha^* \in \{0.0, 0.1, \dots, 1.0\}$ on original `dev`)

---

## 3. Prespecified Decision Gate

Count as a **meaningful new signal ONLY IF** natural fresh held-out `nDCG@10` improves over the strongest comparable frozen baseline in **BOTH** `QMSum` (`75q / 75d`) AND `NarrativeQA` (`75q / 75d`) AND macro-average gain **`>= +0.030`** (evaluated with paired cluster-bootstrap 95% CIs across the `75` independent fresh doc clusters and practical CPU overhead). Otherwise close this line (or name an independent implementation defect warranting correction rather than adding more variants).

---

## 4. Locked Pre-Launch SHA-256 Manifest

| File | SHA-256 |
|---|---|
| `LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json` | `15bb9348cd49b1ad85b1a437df76b44e4af86011551042ca5a6d8fc8a3ad86f6` |
| `STAGE1_FRESH_SPLITS_RECEIPT.json` | `7b02ad57b5867eb301f7b37f8f8a6d112a522764c577af56da47ff17bb343d55` |
| `STAGE1_PARITY_AND_FIXTURES_RECEIPT.json` | `1f93c8aeb91f00366a8b2d5acccfebbcb9a9c96ad9d0be5910d9e0c4a6b65bc9` |
| `hakari_retrieval_core.py` *(Stage-0 unchanged)* | `1a936b34e6bd5546de8a677a7cdcd024107de69fa8649afa9e950680616885e3` |
| `stage1_countcal_top3_core.py` | `ba471679d1ab738c4c62ea19b49652a3c6b828980f33f16d6277556460adece4` |
| `stage1_build_splits_and_fixtures.py` | `81fd2a5f03806de1c9392b4ed0e97e4e2e5c819dca79a7677be0b069c0e9614a` |
| `run_hakari_stage1_followup.py` | `1bc9396cf9b5b57f74ef6ae987d8b33a5759a03fba4891186e4e38b035453861` |
