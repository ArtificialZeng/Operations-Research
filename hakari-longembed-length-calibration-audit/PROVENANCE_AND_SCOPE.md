# Provenance, Parity Disclosures & Scope Boundary

**Date Sealed:** 2026-11-24  
**Archive Status:** **FROZEN — `CLOSE_NO_MEANINGFUL_GAIN`** (no further experiments, tuning, baselines, GPU runs, PDFs, or media).

---

## 1. Native Execution & Disjointness Provenance

- **Stage-0 Pilot (`PID = 55912`, CPU-only, wall time `15.45 s`):**
  - Source: [`hakari-bench/NanoLongEmbed`](https://huggingface.co/datasets/hakari-bench/NanoLongEmbed), pinned commit `ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e` (`NanoQMSum` & `NanoNarrativeQA` only; `14` downloaded files verified in [`receipts/DATASET_DOWNLOAD_RECEIPT.json`](./receipts/DATASET_DOWNLOAD_RECEIPT.json)).
  - Relevant-doc-group-disjoint three-way split ([`receipts/HAKARI_STAGE0_SPLITS_RECEIPT.json`](./receipts/HAKARI_STAGE0_SPLITS_RECEIPT.json)): `NanoQMSum` (`dev = 51q/31d`, `heldout_test = 51q/31d`, `unlabeled_bg_pool = 98q`); `NanoNarrativeQA` (`dev = 52q/43d`, `heldout_test = 50q/41d`, `unlabeled_bg_pool = 98q`). Zero query overlap and zero relevant-doc overlap across all three slices.
  - Sealed outputs (byte-identical): [`outputs/hakari_stage0_summary.json`](./outputs/hakari_stage0_summary.json) (`SHA-256: 2fee379490cd163d4924128822e8f6db40946f898cc6d13d13927c723cbb4876`), [`outputs/NanoQMSum_natural_heldout_per_query.jsonl`](./outputs/NanoQMSum_natural_heldout_per_query.jsonl) (`57d4029f...`), [`outputs/NanoNarrativeQA_natural_heldout_per_query.jsonl`](./outputs/NanoNarrativeQA_natural_heldout_per_query.jsonl) (`b12db83a...`).
- **Stage-1 Targeted Follow-Up (`PID = 40612`, CPU-only, wall time `18.16 s`):**
  - Fresh QA source: [`dwzhu/LongEmbed`](https://huggingface.co/datasets/dwzhu/LongEmbed), pinned commit `10039a580487dacecf79db69166e17ace3ede392` (`5` downloaded QA/README files verified in [`receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json`](./receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json)).
  - Exact mapping & exclusion audit ([`receipts/STAGE1_FRESH_SPLITS_RECEIPT.json`](./receipts/STAGE1_FRESH_SPLITS_RECEIPT.json)): verified `200/200` exact query ID, query text, normalized query SHA-256 hash, and qrel `doc_id` match on both tasks, plus `197/197` and `355/355` unique corpus text hashes and exact `doc_id` set identity. Excluded **ALL `200` Nano query IDs/normalized texts** AND **ALL `122` (`QMSum`) / `163` (`NarrativeQA`) Nano positive doc groups** (covering `dev`, Stage-0 `heldout_test`, AND `unlabeled_bg_pool`).
  - Deterministic 1:1 group-balanced fresh held-out: **`75` fresh queries across `75` distinct fresh relevant docs** on `QMSum` and **`75` fresh queries across `75` distinct fresh relevant docs** on `NarrativeQA` (`150` fresh queries total; `0` overlap across every exclusion set).
  - Sealed outputs (byte-identical): [`outputs/hakari_stage1_summary.json`](./outputs/hakari_stage1_summary.json) (`SHA-256: 22e10cfff3551ae0d7e8a771213202c855a8cf978014fc13ecd5a4ba2ccc7945`), [`outputs/FreshQMSum_natural_per_query.jsonl`](./outputs/FreshQMSum_natural_per_query.jsonl) (`7bded2b4...`), [`outputs/FreshNarrativeQA_natural_per_query.jsonl`](./outputs/FreshNarrativeQA_natural_per_query.jsonl) (`3f7f8d8f...`).

---

## 2. Mandatory Methodological Disclosures

1. **Local Whole-Document BM25 Differs from Published HAKARI Reference BM25 (No Official Score or Contest Entry):**
   - Stage-0 evaluated the published official `bm25/*.parquet` rankings from `hakari-bench/NanoLongEmbed` (`Official_WholeDoc_BM25`, exact README `nDCG@10` parity verified on all 200 queries: `0.7440` QMSum / `0.7619` NarrativeQA; `0.7983` macro on Stage-0 held-out).
   - Stage-1 fresh LongEmbed queries have no published HAKARI `bm25/*.parquet` file, so Stage-1 uses `Local_WholeDoc_BM25` built with the **exact same lexical scorer** as the chunk index (`tokenize_english_porter_stop`, `k1=1.2, b=0.75`, positive Lucene IDF `log(1 + (N - df + 0.5)/(df + 0.5))`, query TF weighting).
   - Parity audit on all 200 original Nano queries ([`receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json`](./receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json)): `Local_WholeDoc_BM25` scored `0.7993` vs. official `0.7440` (`+0.0552`, Top-1 `159/200`, Top-10 Jaccard `0.6356`) on `NanoQMSum` and `0.7546` vs. official `0.7619` (`-0.0073`, Top-1 `155/200`, Top-10 Jaccard `0.6529`) on `NanoNarrativeQA`. The difference stems from HAKARI's `bm25s` using `k1=1.5` and zero-clamped Robertson IDF (diagnostic parity: `0.7555`/`0.7659`, `187/200` and `194/200` Top-1). Accordingly, `Local_WholeDoc_BM25` is explicitly labeled local and represents **no official HAKARI score or leaderboard/contest entry**.
2. **Stage-0 Synthetic Suffix Stress vs. Natural Queries:**
   - Stage-0's artificial `+100`-chunk suffix control appended unrelated dev chunks **only to non-relevant documents** while holding relevant-document length fixed. That stress is label-dependent negative-only padding and is strictly diagnostic only — NEVER counted as benchmark progress and omitted from Stage-1.
3. **Pure $\gamma = 1.0$ Remains Diagnostic Only:**
   - On original `dev`, `CountCal_Top3` locked $\gamma^* = 0.25$ on both tasks (`0.8402` QMSum, `0.8473` NarrativeQA). The logged `CountCal_Top3_PureGamma1_diagnostic` figure (`0.806162` macro; `+0.008177` vs. `Raw_Top3`) is reported strictly as a transparency diagnostic and is NOT used for post-hoc method choice.
4. **Strict Scope & Prior Art (No Priority Claims):**
   - Findings are scoped exclusively to `QMSum` and `NarrativeQA` under this fixed CPU-only lexical `W = 256`-word BM25 pipeline. They make no claims about neural/dense/late-interaction scorers or full HAKARI/LongEmbed leaderboards.
   - Related work: Edy, Conti, & Macé ([arXiv:2603.26259](https://arxiv.org/abs/2603.26259)) on late-interaction `MaxSim` length bias, HAKARI ([arXiv:2606.22778](https://arxiv.org/abs/2606.22778)), LongEmbed ([arXiv:2404.12096](https://arxiv.org/abs/2404.12096)), MPE ([arXiv:2606.23642](https://arxiv.org/abs/2606.23642)), DICE ([arXiv:2606.18781](https://arxiv.org/abs/2606.18781)), OpenReview [`85a1LK7Unu`](https://openreview.net/pdf?id=85a1LK7Unu), IJCNLP 2025 [`2025.ijcnlp-long.46`](https://aclanthology.org/2025.ijcnlp-long.46/), and Dai & Callan (SIGIR 2019).

---

## 3. Local-to-Archive Portability SHA-256 Crosswalk

All 6 receipts, all 6 derived output summaries/per-query JSONLs, and both core retrieval modules are archived **byte-identical**. For the 6 runner/builder scripts and 4 Markdown protocols/reports, only hardcoded local workspace root paths / local absolute file URLs were converted to portable relative paths (zero algorithmic, parameter, or numerical changes); exact full local and archived SHA-256 hashes appear in [`MANIFEST.json`](./MANIFEST.json):

| Archived Path | Local Sealed SHA-256 (prefix) | Archived SHA-256 (prefix) | Byte-Identical |
|---|---|---|---|
| `receipts/DATASET_DOWNLOAD_RECEIPT.json` | `2f27e90e5d6cc955...` | `2f27e90e5d6cc955...` | YES |
| `receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json` | `15bb9348cd49b1ad...` | `15bb9348cd49b1ad...` | YES |
| `receipts/HAKARI_STAGE0_SPLITS_RECEIPT.json` | `5d1118ea1b2c9419...` | `5d1118ea1b2c9419...` | YES |
| `receipts/HAKARI_STAGE0_FIXTURE_RECEIPT.json` | `f1a7656ef17a3b1f...` | `f1a7656ef17a3b1f...` | YES |
| `receipts/STAGE1_FRESH_SPLITS_RECEIPT.json` | `7b02ad57b5867eb3...` | `7b02ad57b5867eb3...` | YES |
| `receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json` | `1f93c8aeb91f0036...` | `1f93c8aeb91f0036...` | YES |
| `outputs/hakari_stage0_summary.json` | `2fee379490cd163d...` | `2fee379490cd163d...` | YES |
| `outputs/NanoQMSum_natural_heldout_per_query.jsonl` | `57d4029f448847de...` | `57d4029f448847de...` | YES |
| `outputs/NanoNarrativeQA_natural_heldout_per_query.jsonl` | `b12db83ae53e33dc...` | `b12db83ae53e33dc...` | YES |
| `outputs/hakari_stage1_summary.json` | `22e10cfff3551ae0...` | `22e10cfff3551ae0...` | YES |
| `outputs/FreshQMSum_natural_per_query.jsonl` | `7bded2b4c75005fd...` | `7bded2b4c75005fd...` | YES |
| `outputs/FreshNarrativeQA_natural_per_query.jsonl` | `3f7f8d8f180583f2...` | `3f7f8d8f180583f2...` | YES |
| `code/hakari_retrieval_core.py` | `1a936b34e6bd5546...` | `1a936b34e6bd5546...` | YES |
| `code/stage1_countcal_top3_core.py` | `ba471679d1ab738c...` | `ba471679d1ab738c...` | YES |
| `code/download_pinned_nanolongembed.py` | `f2b4dc56577b74fc...` | `b55639cf798aa7eb...` | NO (path/link portability only) |
| `code/build_hakari_splits_and_fixtures.py` | `31ae9258906438fb...` | `e18eb6d65a1c9d22...` | NO (path/link portability only) |
| `code/run_hakari_stage0_pilot.py` | `a0a49954ff63db74...` | `35710317e0fe9861...` | NO (path/link portability only) |
| `code/stage1_download_longembed_qa.py` | `1c4d63a896a65ca3...` | `517c8805af27ecdb...` | NO (path/link portability only) |
| `code/stage1_build_splits_and_fixtures.py` | `81fd2a5f03806de1...` | `fccb36b028e5bdcf...` | NO (path/link portability only) |
| `code/run_hakari_stage1_followup.py` | `1bc9396cf9b5b57f...` | `2ab6101d4a48d6f8...` | NO (path/link portability only) |
| `protocols/STAGE0_HAKARI_PROTOCOL.md` | `99c4c86c73b88af9...` | `21b998c7845af16c...` | NO (path/link portability only) |
| `protocols/STAGE1_COUNTCAL_TOP3_PROTOCOL.md` | `041fa82514d07f1c...` | `54658e4f3d25e122...` | NO (path/link portability only) |
| `reports/STAGE0_HAKARI_RESULT.md` | `65ce60b37391d841...` | `5abb56a39160640a...` | NO (path/link portability only) |
| `reports/STAGE1_COUNTCAL_TOP3_RESULT.md` | `8f0f9272361ba988...` | `7567c68a35da176e...` | NO (path/link portability only) |
