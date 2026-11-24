# Stage-1 Targeted Follow-Up Result — Count-Calibrated Top-3 Evidence (`CountCal_Top3`) on Fresh Independent LongEmbed Splits

**Date:** 2026-11-24  
**Decision:** **`CLOSE_NO_MEANINGFUL_GAIN` — All three prespecified gates FAILED on fresh independent query groups (`75q / 75d` per task). Close this lexical count-calibration line without further variants.**  
**Stage-0 Sealed Anchor (Unaltered):** [`hakari_stage0_summary.json`](../outputs/hakari_stage0_summary.json) (`SHA-256: 2fee379490cd163d4924128822e8f6db40946f898cc6d13d13927c723cbb4876`, `PID = 55912`, natural macro `Empirical_CountCond_Null = 0.7474` vs. `Top3_Mean = 0.7925` and `Official_WholeDoc_BM25 = 0.7983`; `RRF_BM25_plus_EmpiricalNull = 0.8030` vs. `RRF_BM25_plus_MaxMinusLogN = 0.8069`). Stage-0's synthetic suffix stress was negative-only padding and label-dependent, so it remains strictly diagnostic only.

---

## 1. Executive Summary

Following the Stage-0 finding that `Top3_Mean > Raw_MaxP` on both tasks while single-chunk `Empirical_CountCond_Null` suffered from unlabeled positive tail contamination and count-dependent POT slope drift, we tested **one** locked targeted variant — **`CountCal_Top3`** — on **fresh, independent, 1:1 group-balanced query groups** (`75` fresh queries across `75` distinct fresh relevant docs per task) from official [`dwzhu/LongEmbed`](https://huggingface.co/datasets/dwzhu/LongEmbed) (`10039a580487dacecf79db69166e17ace3ede392`) under [`STAGE1_COUNTCAL_TOP3_PROTOCOL.md`](../protocols/STAGE1_COUNTCAL_TOP3_PROTOCOL.md) (`SHA-256: 041fa825...`).

- **Prespecified Gate Outcome (FAILED on all three comparable scopes):** Required natural fresh held-out `nDCG@10` improvement over the strongest comparable baseline in **BOTH** `QMSum` (`75q/75d`) and `NarrativeQA` (`75q/75d`) AND macro-average gain **`>= +0.030`**:
  1. **Passage-only gate (`CountCal_Top3` vs. `Raw_Top3`):** **FAIL** — `QMSum` `0.8267` vs. `0.8188` (`+0.0078`, 95% CI `[-0.0092, +0.0283]`, `5 wins / 5 losses / 65 ties`), `NarrativeQA` `0.7750` vs. `0.7771` (`-0.0021`, 95% CI `[-0.0194, +0.0129]`, `4 wins / 2 losses / 69 ties`), macro **`+0.0028`** (`0.8008` vs. `0.7980`). *(Diagnostic pure $\gamma=1.0$ without dev shrinkage: `0.8344` / `0.7779`, macro `0.8062`, `+0.0082` over `Raw_Top3` — still nearly `4x` below `+0.030`.)*
  2. **Standalone lexical gate (`CountCal_Top3` vs. `max(Raw_MaxP, Raw_Top3, Local_WholeDoc_BM25)`):** **FAIL** — trails `Local_WholeDoc_BM25` on `QMSum` (`0.8267` vs. `0.8446`, `-0.0179`, 95% CI `[-0.0867, +0.0490]`) and trails `Raw_Top3` on `NarrativeQA` (`0.7750` vs. `0.7771`, `-0.0021`); macro vs. per-task best **`-0.0100`**.
  3. **RRF fusion gate (`RRF_LocalBM25_plus_CountCalTop3` vs. all comparable controls incl. `RRF_LocalBM25_plus_RawTop3`):** **FAIL** — `QMSum` `0.8760` vs. `0.8802` (`-0.0042`, 95% CI `[-0.0207, +0.0140]`, `1 win / 5 losses / 69 ties`), `NarrativeQA` `0.7706` vs. `0.7694` (`+0.0012`, 95% CI `[-0.0181, +0.0193]`, both trailing `Raw_Top3 = 0.7771`), macro **`0.8233` vs. `0.8248`** (**`-0.0015`**).
- **No Independent Implementation Defect Found:** Every pre-launch synthetic fixture passed (strict monotonicity through `r = 50`, zero short-vs-long tail crossover, `92.5%`/`99%` sparse-zero order preservation, top-1 background outlier immunity), `CountCal_Top3` reduced natural non-relevant length intrusion cleanly (`Q4/Q1`: `1.55x -> 1.35x` on `QMSum`, `5.03x -> 3.22x` on `NarrativeQA`), and calibration ran in `6.7–11.8 ms` per 75 queries. Rather than a bug, the empirical conclusion is clear: **on lexical BM25 long-document retrieval, multi-passage aggregation (`Raw_Top3`, which replicated `+0.0319` macro over `Raw_MaxP`) and whole-document RRF fusion (`0.8248` macro) capture the useful signal, whereas empirical count-conditional null calibration adds near-zero natural accuracy (`-0.0015` to `+0.0028` macro, ~90% tied queries).**

---

## 2. Provenance, Exact Mapping, Disjointness & Local BM25 Parity

- **Pinned Sources (Corpus Text Kept Strictly Local as Inert Data, Never Republished):**
  - Unchanged corpora (`197` docs QMSum, `355` docs NarrativeQA), chunks (`W = 256` words: `7,837` and `70,173` chunks), dev split (`51q`/`52q`), and unlabeled calibration pool (`98q`/`98q`) from [`hakari-bench/NanoLongEmbed`](https://huggingface.co/datasets/hakari-bench/NanoLongEmbed) (`ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e`).
  - Original fresh QA query/qrel files from [`dwzhu/LongEmbed`](https://huggingface.co/datasets/dwzhu/LongEmbed) (`10039a580487dacecf79db69166e17ace3ede392`, exact `source_revision` recorded in HAKARI metadata; LFS SHA-256 verified in [`LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json`](../receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json), `15bb9348...`).
- **Verified Exact Mapping & Complete Disjointness** ([`STAGE1_FRESH_SPLITS_RECEIPT.json`](../receipts/STAGE1_FRESH_SPLITS_RECEIPT.json), `7b02ad57...`):
  - `200/200` exact query ID, exact query text, normalized query SHA-256 hash, and exact qrel `doc_id` match on BOTH tasks; `197/197` (`QMSum`) and `355/355` (`NarrativeQA`) unique corpus full-text hashes and exact `doc_id` set identity.
  - Excluded ALL `200` Nano query IDs/normalized texts AND ALL `122` (`QMSum`) / `163` (`NarrativeQA`) Nano positive document groups (`0` overlap with `dev`, Stage-0 `heldout_test`, AND `unlabeled_bg_pool`).
  - Deterministic 1:1 group-balanced selection: **`75` fresh queries across `75` distinct fresh relevant docs** on `QMSum` (all `75` eligible fresh docs; chunk counts min=`5`, p50=`37`, max=`96`) and **`75` fresh queries across `75` distinct fresh relevant docs** on `NarrativeQA` (from `192` eligible fresh docs; chunk counts min=`18`, p50=`113`, max=`1,034`).
- **Same-Scored `Local_WholeDoc_BM25` Parity Verification** ([`STAGE1_PARITY_AND_FIXTURES_RECEIPT.json`](../receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json), `1f93c8ae...`):
  - Uses the exact same lexical scorer as `SparseChunkBM25Index` (`tokenize_english_porter_stop`, `k1=1.2, b=0.75`, positive Lucene IDF, query TF, `100%` full-corpus recall); explicitly labeled `Local_WholeDoc_BM25` on fresh queries.
  - On all `200` original Nano queries vs. official `bm25/*.parquet`: `NanoQMSum` `0.7993` vs. `0.7440` (`+0.0552`, Top-1 `159/200`, Top-10 Jaccard `0.6356`, Spearman `0.8376`); `NanoNarrativeQA` `0.7546` vs. `0.7619` (`-0.0073`, Top-1 `155/200`, Top-10 Jaccard `0.6529`, Spearman `0.7771`). Diagnostic zero-clamped Robertson IDF (`k1=1.5`) matches official `bm25s` closely (`0.7555` / `0.7659`, `187/200` and `194/200` Top-1); using same-scored Lucene-IDF `Local_WholeDoc_BM25` gives a stronger whole-doc baseline on `QMSum` and identical scoring mechanics to the chunk index.
- **Primary Related Literature (No Priority or Leaderboard Claims):** Edy, Conti, & Macé ([arXiv:2603.26259](https://arxiv.org/abs/2603.26259)) on late-interaction `MaxSim` length bias, HAKARI ([arXiv:2606.22778](https://arxiv.org/abs/2606.22778)) / LongEmbed ([arXiv:2404.12096](https://arxiv.org/abs/2404.12096)), MPE ([arXiv:2606.23642](https://arxiv.org/abs/2606.23642)), DICE ([arXiv:2606.18781](https://arxiv.org/abs/2606.18781)), and Dai & Callan (SIGIR 2019).

---

## 3. Natural Fresh Held-Out & Dev Results (`nDCG@10`, `0–1` Scale, `100%` Recall)

### 3.1 Dev-Locked Parameters (Selected Solely on Original Stage-0 `dev`, Equal Dev Handling)
- `NanoQMSum` (`dev = 51q / 31d`): `CountCal_Top3` $\gamma^* = 0.25$ (`beta_global = 1.601`, fixed `h = 0.50`, `exclude_top_k = 1`); `RRF_LocalBM25_plus_RawTop3` $\alpha^* = 0.7$; `RRF_LocalBM25_plus_CountCalTop3` $\alpha^* = 0.7$.
- `NanoNarrativeQA` (`dev = 52q / 43d`): `CountCal_Top3` $\gamma^* = 0.25$ (`beta_global = 1.201`, fixed `h = 0.50`, `exclude_top_k = 1`); `RRF_LocalBM25_plus_RawTop3` $\alpha^* = 0.8$; `RRF_LocalBM25_plus_CountCalTop3` $\alpha^* = 0.8$.

### 3.2 Primary Natural Retrieval Table

| Method | `QMSum` Orig Dev (`51q`) | `QMSum` **Fresh Held-Out (`75q/75d`)** | `NarrativeQA` Orig Dev (`52q`) | `NarrativeQA` **Fresh Held-Out (`75q/75d`)** | **Macro Fresh Held-Out** |
|---|---:|---:|---:|---:|---:|
| `Raw_MaxP` | `0.7833` | `0.7742` | `0.8325` | `0.7580` | `0.7661` |
| `Raw_Top3` | `0.8169` | `0.8188` | `0.8377` | **`0.7771`** | `0.7980` |
| `Local_WholeDoc_BM25` *(same lexical scorer)* | `0.7928` | `0.8446` | `0.8138` | `0.7445` | `0.7945` |
| **`CountCal_Top3`** *(dev $\gamma^*=0.25$)* | `0.8402` | `0.8267` | `0.8473` | `0.7750` | `0.8008` |
| *`CountCal_Top3` ($\gamma=1.0$, diagnostic ref)* | *`0.8174`* | *`0.8344`* | *`0.8458`* | *`0.7779`* | *`0.8062`* |
| `RRF_LocalBM25_plus_RawTop3` *(dev $\alpha^*$)* | `0.8348` | **`0.8802`** | `0.8494` | `0.7694` | **`0.8248`** |
| **`RRF_LocalBM25_plus_CountCalTop3`** *(dev $\alpha^*$)* | **`0.8435`** | `0.8760` | **`0.8573`** | `0.7706` | `0.8233` |

### 3.3 Paired Cluster-Bootstrap 95% CIs (`75` Independent Fresh Doc Groups, `5,000` Draws)

| Comparison (`A` minus `B`) | `QMSum` Diff (`95% CI`, W/L/T) | `NarrativeQA` Diff (`95% CI`, W/L/T) |
|---|---|---|
| `CountCal_Top3` vs. `Raw_Top3` | `+0.0078` (`[-0.0092, +0.0283]`, `5 / 5 / 65`) | `-0.0021` (`[-0.0194, +0.0129]`, `4 / 2 / 69`) |
| `CountCal_Top3` vs. `Raw_MaxP` | **`+0.0525`** (`[+0.0027, +0.1003]`, `16 / 5 / 54`) | `+0.0170` (`[-0.0031, +0.0393]`, `8 / 2 / 65`) |
| `CountCal_Top3` vs. `Local_WholeDoc_BM25` | `-0.0179` (`[-0.0867, +0.0490]`, `14 / 16 / 45`) | `+0.0305` (`[-0.0225, +0.0870]`, `11 / 8 / 56`) |
| `Raw_Top3` vs. `Raw_MaxP` | `+0.0447` (`[-0.0036, +0.0909]`, `15 / 4 / 56`) | `+0.0191` (`[-0.0104, +0.0508]`, `7 / 3 / 65`) |
| `RRF_CountCalTop3` vs. `RRF_RawTop3` | `-0.0042` (`[-0.0207, +0.0140]`, `1 / 5 / 69`) | `+0.0012` (`[-0.0181, +0.0193]`, `4 / 2 / 69`) |
| `RRF_CountCalTop3` vs. `Local_WholeDoc_BM25` | `+0.0314` (`[-0.0213, +0.0809]`, `16 / 9 / 50`) | `+0.0261` (`[-0.0215, +0.0736]`, `11 / 8 / 56`) |
| `RRF_CountCalTop3` vs. `Raw_Top3` | **`+0.0571`** (`[+0.0225, +0.0969]`, `15 / 3 / 57`) | `-0.0065` (`[-0.0307, +0.0157]`, `6 / 4 / 65`) |
| `RRF_RawTop3` vs. `Local_WholeDoc_BM25` | `+0.0356` (`[-0.0156, +0.0861]`, `16 / 9 / 50`) | `+0.0249` (`[-0.0231, +0.0727]`, `10 / 7 / 58`) |

### 3.4 Natural Non-Relevant Length-Bias Diagnostic (Strictly Separate — NOT Benchmark Progress)

| Method | `QMSum` Non-Rel $\rho(\text{score}, \log n)$ | `QMSum` Q4/Q1 Top-10 Intrusion | `NarrativeQA` Non-Rel $\rho(\text{score}, \log n)$ | `NarrativeQA` Q4/Q1 Top-10 Intrusion |
|---|---:|---:|---:|---:|
| `Raw_MaxP` | `-0.041` | `1.400x` (`28.7% / 20.5%`) | `+0.418` | `3.775x` (`44.0% / 11.6%`) |
| `Raw_Top3` | `+0.001` | `1.553x` (`28.2% / 18.1%`) | `+0.489` | `5.029x` (`49.8% / 9.9%`) |
| `Local_WholeDoc_BM25` | `+0.235` | `2.830x` (`36.7% / 13.0%`) | `+0.362` | `3.129x` (`38.7% / 12.4%`) |
| `CountCal_Top3` | `+0.011` | `1.350x` (`27.3% / 20.2%`) | `+0.335` | `3.217x` (`43.1% / 13.4%`) |

### 3.5 Practical CPU-Only Overhead (`PID = 40612`, Total Wall Time `18.16 s`)

| Task | Chunk Index | Whole-Doc Index | Unlabeled Bg Fit (`98q`) | Dev Tune | Fresh Score All (`75q`) | Fresh `CountCal_Top3` Calibrator Only | Task Total |
|---|---:|---:|---:|---:|---:|---:|---:|
| `QMSum` (`7,837` chunks) | `0.833 s` | `0.337 s` | `0.356 s` | `0.232 s` | `0.278 s` | `0.0067 s` | `2.749 s` |
| `NarrativeQA` (`70,173` chunks) | `8.137 s` | `4.480 s` | `0.796 s` | `0.518 s` | `0.611 s` | `0.0118 s` | `15.361 s` |

---

## 4. Closure & Sealed Stage-1 SHA-256 Manifest

**Close this lexical count-calibration line.** Across both Stage-0 (`NanoLongEmbed`, `51q`/`50q`) and Stage-1 (`dwzhu/LongEmbed` fresh disjoint `75q/75d` + `75q/75d`), empirical count-conditional null calibration on lexical BM25 passage scores fails to clear the prespecified `+0.030` both-task gate (achieving `-0.0015` macro inside RRF fusion and `+0.0028` macro standalone over `Raw_Top3`, with 95% CIs straddling zero). The robust positive baseline finding is simply that multi-passage `Raw_Top3` beats `Raw_MaxP` on both tasks (`+0.0319` macro) and fuses cleanly with whole-doc BM25 (`0.8248` macro).

| Artifact | SHA-256 |
|---|---|
| [`STAGE1_COUNTCAL_TOP3_PROTOCOL.md`](../protocols/STAGE1_COUNTCAL_TOP3_PROTOCOL.md) | `041fa82514d07f1c429b0cbf360b89eb930a9f4c0dc3b6cb8e2d26d70c41999f` |
| [`LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json`](../receipts/LONGEMBED_STAGE1_QA_DOWNLOAD_RECEIPT.json) | `15bb9348cd49b1ad85b1a437df76b44e4af86011551042ca5a6d8fc8a3ad86f6` |
| [`STAGE1_FRESH_SPLITS_RECEIPT.json`](../receipts/STAGE1_FRESH_SPLITS_RECEIPT.json) | `7b02ad57b5867eb301f7b37f8f8a6d112a522764c577af56da47ff17bb343d55` |
| [`STAGE1_PARITY_AND_FIXTURES_RECEIPT.json`](../receipts/STAGE1_PARITY_AND_FIXTURES_RECEIPT.json) | `1f93c8aeb91f00366a8b2d5acccfebbcb9a9c96ad9d0be5910d9e0c4a6b65bc9` |
| [`stage1_countcal_top3_core.py`](../code/stage1_countcal_top3_core.py) | `ba471679d1ab738c4c62ea19b49652a3c6b828980f33f16d6277556460adece4` |
| [`run_hakari_stage1_followup.py`](../code/run_hakari_stage1_followup.py) | `1bc9396cf9b5b57f74ef6ae987d8b33a5759a03fba4891186e4e38b035453861` |
| [`hakari_stage1_summary.json`](../outputs/hakari_stage1_summary.json) | `22e10cfff3551ae0d7e8a771213202c855a8cf978014fc13ecd5a4ba2ccc7945` |
| [`FreshQMSum_natural_per_query.jsonl`](../outputs/FreshQMSum_natural_per_query.jsonl) | `7bded2b4c75005fd57dffa0e10a4af5d66060b05d9dffabcd4be029b3b948b74` |
| [`FreshNarrativeQA_natural_per_query.jsonl`](../outputs/FreshNarrativeQA_natural_per_query.jsonl) | `3f7f8d8f180583f2afbf26bcb081aa3556fb9df2f2a8beb6b86f7fcb7d38cc34` |
| [`hakari_stage0_summary.json`](../outputs/hakari_stage0_summary.json) *(Stage-0 sealed, unaltered)* | `2fee379490cd163d4924128822e8f6db40946f898cc6d13d13927c723cbb4876` |
