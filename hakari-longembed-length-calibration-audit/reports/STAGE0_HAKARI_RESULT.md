# Stage-0 Pilot Result — Training-Free Length-Calibrated Long-Document Retrieval (HAKARI NanoLongEmbed)

**Date:** 2026-11-24  
**Decision:** **`STOP_OR_ADAPT` — All three prespecified advancement gates FAILED on natural held-out queries.**  
**Scope:** Strictly CPU-only training-free retrieval pilot on **`NanoQMSum`** and **`NanoNarrativeQA`** from pinned [`hakari-bench/NanoLongEmbed`](https://huggingface.co/datasets/hakari-bench/NanoLongEmbed) revision `ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e`. Zero GPU, zero neural training, zero paid APIs, zero corpus text republication (corpus retained strictly locally as inert data), zero held-out retuning, zero leaderboard/priority claims, zero PDFs/media/public release.

---

## 1. Executive Summary

We tested whether empirically calibrating a document's maximum chunk BM25 score (`MaxP`) by its count-conditional null survival probability $P_{\text{null}}(Z \ge z_{q,d} \mid n_d)$ — estimated strictly on disjoint unlabeled background queries with zero qrel leakage — improves natural held-out `nDCG@10` on long-document retrieval (`NanoQMSum` and `NanoNarrativeQA`) under a locked pre-launch protocol ([`STAGE0_HAKARI_PROTOCOL.md`](../protocols/STAGE0_HAKARI_PROTOCOL.md), SHA-256 `99c4c86c...`).

- **Prespecified Advancement Gate (FAILED):** Required held-out natural `nDCG@10` improvement on **BOTH** `NanoQMSum` and `NanoNarrativeQA` AND a macro-average gain of **`>= +0.030`** over the strongest comparable frozen baseline.
  - **Passage-only gate (`Empirical_CountCond_Null` vs. strongest passage baseline `Top3_Mean`):** **FAILED** — macro `0.7474` vs. `0.7925` (**`-0.0451`**; `-0.0370` on `NanoQMSum`, `-0.0532` on `NanoNarrativeQA`, 95% cluster-bootstrap CI `[-0.1048, -0.0132]` on `NanoNarrativeQA`). Also trailed uncalibrated `Raw_MaxP` (`0.7650` macro, `-0.0176`) and `Analytical_IID_Null` (`0.7698` macro, `-0.0224`) on both tasks.
  - **All comparable lexical baselines gate (incl. `Official_WholeDoc_BM25`):** **FAILED** — macro `0.7474` vs. `0.7983` (**`-0.0509`**; `-0.0872` on `NanoQMSum`, 95% cluster-bootstrap CI `[-0.1857, -0.0004]`).
  - **BM25 + Passage RRF fusion gate (`RRF_BM25_plus_EmpiricalNull` vs. strongest fusion/BM25 baseline):** **FAILED** — macro `0.8030` vs. `0.8069` (`RRF_BM25_plus_MaxMinusLogN`, `-0.0040`) and `0.8058` (`RRF_BM25_plus_RawMaxP`, `-0.0028`).
- **Key Scientific Findings:**
  1. **Dev gains failed to generalize to held-out:** On `dev`, `Empirical_CountCond_Null` beat `Raw_MaxP` on both tasks (`0.8000` vs. `0.7833` on `NanoQMSum`; `0.8380` vs. `0.8325` on `NanoNarrativeQA`), yet flipped negative on both tasks in group-disjoint `heldout_test` (`0.7193` vs. `0.7444`; `0.7755` vs. `0.7856`).
  2. **Multi-passage evidence dominates single-chunk length debiasing on natural lexical retrieval:** `Top3_Mean` achieved the strongest passage-only held-out score on BOTH tasks (`0.7563` on `NanoQMSum`, `0.8287` on `NanoNarrativeQA`, `0.7925` macro) — beating `Official_WholeDoc_BM25` on `NanoNarrativeQA` (`+0.0386`) — *despite* exhibiting the largest natural non-relevant long-document intrusion (`Q4/Q1 = 1.71x` on `NanoQMSum`, `7.22x` on `NanoNarrativeQA`). On `NanoQMSum` (long `446`-char multi-sentence queries), `Official_WholeDoc_BM25` (`0.8065`) outperformed every `256`-word chunk aggregator because chunk boundaries split co-occurring query terms.
  3. **Post-hoc mechanistic forensics of the frozen calibrator pinpoint a concrete failure mode:** Although `Empirical_CountCond_Null` successfully neutralized natural non-relevant length bias (`Q4/Q1`: `1.34x -> 0.99x` on `NanoQMSum`, `5.44x -> 2.05x` on `NanoNarrativeQA`), estimating an unconstrained count-conditional POT tail scale $\beta(n)$ from an **unlabeled** background pool caused `17.1%` (`NanoQMSum`) and `10.9%` (`NanoNarrativeQA`) of the top-2% tail (`z > q98`) to be contaminated by true positive background matches. On `NanoQMSum` (`h* = 0.35`), $\beta(n)$ expanded `2.45x` from `1.370` (`n=12`) to `3.355` (`n=100`), severely compressing extreme-tail calibrated scores for genuinely relevant long documents (`query_78`, `n=70`, rank `1 -> 4`; `query_145`, `n=55`, rank `1 -> 3`) that both `Raw_MaxP` and `Analytical_IID_Null` ranked `#1`.

---

## 2. Provenance, Dataset Terms & Prior Art Positioning

- **Official Source & Pinned Revision:** [`hakari-bench/NanoLongEmbed`](https://huggingface.co/datasets/hakari-bench/NanoLongEmbed), commit `ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e`. Downloaded only the `14` files required for `NanoQMSum` and `NanoNarrativeQA` (all `10` parquet files verified against official HF LFS SHA-256 in [`DATASET_DOWNLOAD_RECEIPT.json`](../receipts/DATASET_DOWNLOAD_RECEIPT.json), `2f27e90e...`).
- **Source Terms Compliance:** Inspected [official `NanoLongEmbed` README at pinned commit `ec27cccf`](https://huggingface.co/datasets/hakari-bench/NanoLongEmbed/blob/ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e/README.md) prior to download. `NanoLongEmbed` is derived from `dwzhu/LongEmbed` under upstream attribution and license terms. All corpus text is kept strictly locally as inert data under `data/corpus/` and is never quoted, redistributed, or republished.
- **Native Execution Receipt:** Executed via [`run_hakari_stage0_pilot.py`](../code/run_hakari_stage0_pilot.py) in isolated CPU-only Python `3.12.16` (`.venv`: `numpy==2.5.5`, `scipy==1.18.1`, `pyarrow==26.0.1`, `snowballstemmer==3.1.1`):
  - **PID:** `55912` (exit code `0`, CPU-only, total wall time **`15.45 s`**).
  - **Pre-Launch Parity & Fixtures:** [`HAKARI_STAGE0_FIXTURE_RECEIPT.json`](../receipts/HAKARI_STAGE0_FIXTURE_RECEIPT.json) (`f1a7656e...`, all passed): exact official README `nDCG@10` parity on all `200` queries (`NanoQMSum`: BM25 `0.744034` vs. `74.40`, Hybrid[:100] `0.609712` vs. `60.97`; `NanoNarrativeQA`: BM25 `0.761933` vs. `76.19`, Hybrid[:100] `0.512040` vs. `51.20`).
- **Prior Art & Scope (No Priority or Leaderboard Claims):** This negative CPU-only lexical pilot sits adjacent to HAKARI-Bench ([arXiv:2606.22778](https://arxiv.org/abs/2606.22778)), Multi-Prefix Embedding MPE ([arXiv:2606.23642](https://arxiv.org/abs/2606.23642)), DICE ([arXiv:2606.18781](https://arxiv.org/abs/2606.18781)), public notes on MaxSim length bias ([OpenReview 85a1LK7Unu](https://openreview.net/pdf?id=85a1LK7Unu)), long-context positional bias ([IJCNLP 2025](https://aclanthology.org/2025.ijcnlp-long.46/)), and classical MaxP/SumP passage aggregation (Dai & Callan, SIGIR 2019). Results apply solely to fixed `256`-word lexical Okapi BM25 chunks on two NanoLongEmbed splits and make no claims regarding dense/late-interaction neural scorers or full HAKARI leaderboards.

---

## 3. Experimental Setup & Zero-Leakage Splits

- **Relevant-Document-Group-Disjoint Three-Way Splits** ([`HAKARI_STAGE0_SPLITS_RECEIPT.json`](../receipts/HAKARI_STAGE0_SPLITS_RECEIPT.json), `5d1118ea...`; `0` query overlap and `0` relevant-document overlap across `dev`, `heldout_test`, and `unlabeled_bg_pool`):
  - **`NanoQMSum` (`197` docs, `7,837` chunks; chunk count min=`5`, p50=`36`, p90=`70.4`, max=`103`):** `dev = 51` queries (`31` doc groups), `heldout_test = 51` queries (`31` doc groups; relevant-doc chunks p50=`38`, p75=`52`), `unlabeled_bg_pool = 98` queries (qrels never read by calibrator).
  - **`NanoNarrativeQA` (`355` docs, `70,173` chunks; chunk count min=`13`, p50=`121`, p90=`417`, max=`1,356`):** `dev = 52` queries (`43` doc groups), `heldout_test = 50` queries (`41` doc groups; relevant-doc chunks p50=`141.5`, p75=`311.2`), `unlabeled_bg_pool = 98` queries (qrels never read by calibrator).
- **Full-Corpus Candidate Recall:** Every passage method and `Official_WholeDoc_BM25` ranks **`100.0%`** of corpus documents (`197/197` and `355/355`). `Official_Hybrid_Top100_NoSafeguard` (reported separately for external scope reference) uses HAKARI's external neural `harrier_oss_v1_270m` + BM25 RRF top-100 with the rank-101 oracle safeguard stripped.
- **Dev-Locked Hyperparameters (frozen before scoring `heldout_test`):**
  - `NanoQMSum`: $\lambda^* = 1.0$ (`MaxP - λ log n`), $h^* = 0.35$ (`Empirical_CountCond_Null`), RRF $\alpha^* = (0.7, 0.7, 0.6)$ for `(RawMaxP, MaxMinusLogN, EmpiricalNull)`.
  - `NanoNarrativeQA`: $\lambda^* = 0.5$, $h^* = 0.75$, RRF $\alpha^* = (0.7, 0.7, 0.7)$.

---

## 4. Natural Held-Out & Dev Results (`nDCG@10`, `0–1` Scale)

### 4.1 Primary Natural Retrieval Table

| Method | Scope | `NanoQMSum` Dev (`51q`) | `NanoQMSum` **Held-Out (`51q`)** | `NanoNarrativeQA` Dev (`52q`) | `NanoNarrativeQA` **Held-Out (`50q`)** | **Macro Held-Out** |
|---|---|---:|---:|---:|---:|---:|
| `Official_WholeDoc_BM25` | Official full-corpus BM25 (`100%` recall) | `0.7581` | **`0.8065`** | `0.7825` | `0.7901` | **`0.7983`** |
| `Raw_MaxP` | Passage BM25 (`W=256`, `100%` recall) | `0.7833` | `0.7444` | `0.8325` | `0.7856` | `0.7650` |
| `Top3_Mean` | Passage BM25 (`W=256`, `100%` recall) | **`0.8169`** | **`0.7563`** | `0.8377` | **`0.8287`** | **`0.7925`** |
| `MaxP_Minus_Lambda_LogN` | Passage BM25 (dev-tuned $\lambda^*$) | `0.7890` | `0.7444` | `0.8384` | `0.7844` | `0.7644` |
| `Analytical_IID_Null` | Passage BM25 (LODO i.i.d. + POT tail) | `0.7897` | `0.7413` | **`0.8463`** | `0.7984` | `0.7698` |
| **`Empirical_CountCond_Null`** *(Candidate)* | Passage BM25 (unlabeled bg + dev $h^*$) | `0.8000` | **`0.7193`** | `0.8380` | **`0.7755`** | **`0.7474`** |
| `RRF_BM25_plus_RawMaxP` | RRF w/ Official BM25 (dev $\alpha^*$) | `0.8322` | `0.7814` | `0.8393` | `0.8302` | `0.8058` |
| `RRF_BM25_plus_MaxMinusLogN` | RRF w/ Official BM25 (dev $\alpha^*$) | `0.8326` | `0.7808` | `0.8411` | **`0.8331`** | **`0.8069`** |
| **`RRF_BM25_plus_EmpiricalNull`** *(Candidate RRF)* | RRF w/ Official BM25 (dev $\alpha^*$) | **`0.8465`** | `0.7806` | `0.8405` | `0.8253` | `0.8030` |
| *`Official_Hybrid_Top100_NoSafeguard`* *(external ref)* | *Neural `harrier-270m` + BM25 top-100 (no rank-101 oracle)* | *`0.6280`* | *`0.6612`* | *`0.5614`* | *`0.5223`* | *`0.5917`* |

### 4.2 Relevant-Doc-Group-Clustered Paired Bootstrap Uncertainty (`5,000` Draws, Held-Out)

| Comparison (`A` minus `B`) | Task (`groups / queries`) | Point Diff | 95% Cluster Bootstrap CI | Wins / Losses / Ties (`A vs B`) |
|---|---|---:|---:|---:|
| `Empirical_CountCond_Null` vs. `Raw_MaxP` | `NanoQMSum` (`31 / 51`) | `-0.0251` | `[-0.0670, +0.0100]` | `2 / 5 / 44` |
| `Empirical_CountCond_Null` vs. `Top3_Mean` | `NanoQMSum` (`31 / 51`) | `-0.0370` | `[-0.1016, +0.0311]` | `6 / 9 / 36` |
| `Empirical_CountCond_Null` vs. `Analytical_IID_Null` | `NanoQMSum` (`31 / 51`) | `-0.0220` | `[-0.0565, 0.0000]` | `0 / 3 / 48` |
| `Empirical_CountCond_Null` vs. `Official_WholeDoc_BM25` | `NanoQMSum` (`31 / 51`) | **`-0.0872`** | **`[-0.1857, -0.0004]`** | `5 / 14 / 32` |
| `RRF_EmpNull` vs. `Official_WholeDoc_BM25` | `NanoQMSum` (`31 / 51`) | `-0.0259` | `[-0.0924, +0.0387]` | `5 / 10 / 36` |
| `RRF_EmpNull` vs. `RRF_RawMaxP` | `NanoQMSum` (`31 / 51`) | `-0.0008` | `[-0.0291, +0.0292]` | `5 / 4 / 42` |
| `Empirical_CountCond_Null` vs. `Raw_MaxP` | `NanoNarrativeQA` (`41 / 50`) | `-0.0101` | `[-0.0472, +0.0190]` | `2 / 3 / 45` |
| `Empirical_CountCond_Null` vs. `Top3_Mean` | `NanoNarrativeQA` (`41 / 50`) | **`-0.0532`** | **`[-0.1048, -0.0132]`** | `0 / 6 / 44` |
| `Empirical_CountCond_Null` vs. `Analytical_IID_Null` | `NanoNarrativeQA` (`41 / 50`) | `-0.0229` | `[-0.0580, 0.0000]` | `0 / 3 / 47` |
| `Empirical_CountCond_Null` vs. `Official_WholeDoc_BM25` | `NanoNarrativeQA` (`41 / 50`) | `-0.0146` | `[-0.0914, +0.0536]` | `5 / 5 / 40` |
| `RRF_EmpNull` vs. `Official_WholeDoc_BM25` | `NanoNarrativeQA` (`41 / 50`) | `+0.0352` | `[-0.0251, +0.0958]` | `7 / 4 / 39` |
| `RRF_EmpNull` vs. `RRF_RawMaxP` | `NanoNarrativeQA` (`41 / 50`) | `-0.0049` | `[-0.0118, 0.0000]` | `0 / 3 / 47` |

### 4.3 CPU-Only Runtime Breakdown (`PID = 55912`, Total Wall Time `15.45 s`)

| Task | Index Build | Unlabeled Bg Score (`98q`) | Dev Score & Tune | Held-Out Score (All Passage) | Held-Out Empirical Calibrator Only | Task Total (incl. Diagnostics) |
|---|---:|---:|---:|---:|---:|---:|
| `NanoQMSum` (`7,837` chunks) | `0.842 s` | `0.340 s` | `0.533 s` | `0.186 s` | `0.0055 s` | `2.774 s` |
| `NanoNarrativeQA` (`70,173` chunks) | `8.054 s` | `0.764 s` | `1.853 s` | `0.418 s` | `0.0100 s` | `12.614 s` |

---

## 5. Mechanism Diagnostics (STRICTLY SEPARATE — NEVER Benchmark Progress)

All mechanism diagnostics below ran **only after** freezing natural held-out per-query JSONL ledgers (`NanoQMSum` SHA `57d4029f...`, `NanoNarrativeQA` SHA `b12db83a...`).

### 5.1 Natural Non-Relevant Length-Bias Audit (Held-Out)

| Method | `NanoQMSum` Non-Rel $\rho(\text{score}, \log n)$ | `NanoQMSum` Q4/Q1 Top-10 Intrusion | `NanoNarrativeQA` Non-Rel $\rho(\text{score}, \log n)$ | `NanoNarrativeQA` Q4/Q1 Top-10 Intrusion |
|---|---:|---:|---:|---:|
| `Raw_MaxP` | `-0.026` | `1.337x` (`27.2% / 20.3%`) | `+0.338` | `5.436x` (`46.3% / 8.5%`) |
| `Top3_Mean` | `+0.001` | `1.709x` (`28.9% / 16.9%`) | `+0.389` | `7.219x` (`50.7% / 7.0%`) |
| `MaxP_Minus_Lambda_LogN` | `-0.082` | `1.144x` (`25.5% / 22.3%`) | `+0.205` | `2.333x` (`36.7% / 15.7%`) |
| `Analytical_IID_Null` | `-0.429` | `0.719x` (`20.7% / 28.8%`) | `-0.040` | `0.521x` (`15.9% / 30.5%`) |
| `Empirical_CountCond_Null` | `+0.042` | **`0.991x`** (`24.4% / 24.6%`) | `+0.189` | **`2.053x`** (`34.0% / 16.6%`) |

### 5.2 Artificial `+100`-Chunk Irrelevant Suffix Control (Diagnostic Only)

Deterministic `+100` unrelated chunks sampled from `dev`-only documents were appended **only** to non-relevant documents on `heldout_test`:

| Method | `NanoQMSum` Natural -> Padded ($\Delta$) | `NanoNarrativeQA` Natural -> Padded ($\Delta$) |
|---|---:|---:|
| `Raw_MaxP` | `0.7444 -> 0.7179` (`-0.0265`) | `0.7856 -> 0.7856` (`0.0000`) |
| `Top3_Mean` | `0.7563 -> 0.7046` (`-0.0517`) | `0.8287 -> 0.8278` (`-0.0009`) |
| `MaxP_Minus_Lambda_LogN` | `0.7444 -> 0.7352` (`-0.0092`) | `0.7844 -> 0.8113` (`+0.0268`) |
| `Analytical_IID_Null` | `0.7413 -> 0.7702` (`+0.0289`) | `0.7984 -> 0.7986` (`+0.0002`) |
| `Empirical_CountCond_Null` | `0.7193 -> 0.7827` (`+0.0635`) | `0.7755 -> 0.8089` (`+0.0334`) |

> [!WARNING]
> **Methodological Caveat on One-Sided Suffix Control:** Because only non-relevant documents were padded by `+100` chunks while relevant documents remained unpadded, positive $\Delta$ values above natural `nDCG@10` (`+0.0635` / `+0.0334`) reflect differential length penalization of padded distractors relative to unpadded positives — NOT genuine retrieval accuracy gains. The informative contrast is that `Raw_MaxP`/`Top3_Mean` degraded under distractor padding on `NanoQMSum` (`-0.0265` / `-0.0517`), whereas on `NanoNarrativeQA` sparse BM25 IDF rendered `+100` random chunks almost completely inert (`0.0000` / `-0.0009`).

### 5.3 Post-Hoc Forensic Audit of Frozen Calibrator Profiles (Zero Retuning)

Read-only inspection of the frozen held-out per-query ledgers and frozen `unlabeled_bg_pool` tail profiles revealed exactly why `Empirical_CountCond_Null` underperformed on natural held-out queries:

1. **Unlabeled background tail contamination + count-dependent POT slope drift ($\beta(n)$):** Because `unlabeled_bg_pool` reads zero qrels, each background query's own relevant document sits inside the top-2% tail (`z > q98`): **`66 / 387` (`17.1%`)** in `NanoQMSum` and **`76 / 696` (`10.9%`)** in `NanoNarrativeQA`. With localized bandwidth `h* = 0.35` on `NanoQMSum`, the estimated exceedance scale $\beta(n)$ inflated `2.45x` from `1.370` (`n=12`, `cal(z=20) = 15.02`) to `3.023` (`n=70`, `cal(z=20) = 8.51`) and `3.355` (`n=100`, `cal(z=20) = 7.92`). As a result, a short document with `z = 11.1` could outrank a genuinely relevant `n=70` document with `z = 20.0`. This explains the three sharp rank-1 collapses where BOTH `Raw_MaxP` and `Analytical_IID_Null` scored `1.0000`: `NanoQMSum query_78` (`doc_189`, `n=70`: `1.0 -> 0.4307`), `NanoQMSum query_145` (`doc_66`, `n=55`: `1.0 -> 0.5000`), and `NanoNarrativeQA query_12` (`doc_166`, `n=199`: `1.0 -> 0.3562`).
2. **Length vs. relevance alignment & single-chunk variance:** Across both tasks, wins of `Empirical_CountCond_Null` over `Raw_MaxP` occurred only on short/below-median relevant documents (`NanoQMSum`: `n=12, 32`; `NanoNarrativeQA`: `n=80, 108`), whereas losses clustered on longer relevant documents (`NanoQMSum`: `n=70, 80, 55, 40` plus `n=15`; `NanoNarrativeQA`: `n=199, 553, 813`). In `NanoNarrativeQA`, held-out relevant documents are slightly *longer* than the corpus median (`p50 = 141.5` vs. `121.0`), and recurrent multi-chunk signal (`Top3_Mean = 0.8287`) far outweighs single-chunk length debiasing.

---

## 6. Justified Recommendation: `STOP / ADAPT`

- **STOP** pursuing training-free empirical count-conditional single-chunk `MaxP` calibration on **lexical BM25** chunks for HAKARI `NanoQMSum` / `NanoNarrativeQA`. All three prespecified gates failed by wide margins (`-0.0451` to `-0.0509` macro on passage-only; `-0.0040` on RRF fusion), sparse BM25 IDF already limits natural false-positive tail inflation in long narrative text, and multi-chunk aggregation (`Top3_Mean`) or whole-document `BM25` dominates single-chunk `MaxP`.
- **Possible Future Adaptation (ONLY if explicitly authorized as a new prespecified protocol — NOT executed here):**
  1. **Target the regime where `MaxP` / `MaxSim` length bias is actually severe:** dense bi-encoder chunk embeddings or ColBERT-style late interaction (where unrelated chunks produce dense cosine noise rather than sparse lexical zeros, and where OpenReview `85a1LK7Unu` documents acute `MaxSim` length inflation).
  2. **Fix the two mechanistic flaws identified here before any future test:** (a) exclude each background query's top-$k$ candidate scores (or winsorize/trim upper outliers) and tie the extreme-tail POT slope $\beta$ globally across $n$ so length shifts location without multiplying extreme-tail compression; and (b) test count-conditional calibration on **multi-chunk** statistics (`Top3_Mean` / `SumP`) rather than single-chunk `MaxP` alone.

---

## 7. Sealed SHA-256 Artifact Manifest

| Artifact | SHA-256 |
|---|---|
| [`STAGE0_HAKARI_PROTOCOL.md`](../protocols/STAGE0_HAKARI_PROTOCOL.md) | `99c4c86c73b88af9aa09c1ac907e6fd3406f17fc20376893869604316971bdba` |
| [`DATASET_DOWNLOAD_RECEIPT.json`](../receipts/DATASET_DOWNLOAD_RECEIPT.json) | `2f27e90e5d6cc95507f511ff003437e288db290393c1d1b616c7929cf1a03ab5` |
| [`HAKARI_STAGE0_SPLITS_RECEIPT.json`](../receipts/HAKARI_STAGE0_SPLITS_RECEIPT.json) | `5d1118ea1b2c9419a618890569c95aac4ee6e32b60d9447dfee710e043e5f8e8` |
| [`HAKARI_STAGE0_FIXTURE_RECEIPT.json`](../receipts/HAKARI_STAGE0_FIXTURE_RECEIPT.json) | `f1a7656ef17a3b1f52c0eb08fdbbf76ee4afbb13d470ceb2d5f5066ec6174599` |
| [`hakari_retrieval_core.py`](../code/hakari_retrieval_core.py) | `1a936b34e6bd5546de8a677a7cdcd024107de69fa8649afa9e950680616885e3` |
| [`build_hakari_splits_and_fixtures.py`](../code/build_hakari_splits_and_fixtures.py) | `31ae9258906438fbee526ef48174800a5e1e6eb4ea75e3d67709fe91b4f364dd` |
| [`run_hakari_stage0_pilot.py`](../code/run_hakari_stage0_pilot.py) | `a0a49954ff63db745fb993994c57300a957505e1a0b8afecceda9f3ab47f4db5` |
| [`hakari_stage0_summary.json`](../outputs/hakari_stage0_summary.json) | `2fee379490cd163d4924128822e8f6db40946f898cc6d13d13927c723cbb4876` |
| [`NanoQMSum_natural_heldout_per_query.jsonl`](../outputs/NanoQMSum_natural_heldout_per_query.jsonl) | `57d4029f448847de513d7d315e4cf7fb9d0661c811245632b97cc1bcced10924` |
| [`NanoNarrativeQA_natural_heldout_per_query.jsonl`](../outputs/NanoNarrativeQA_natural_heldout_per_query.jsonl) | `b12db83ae53e33dcce659b787c6c6db5474d0453cfe98847bf9f8b33fb5f7104` |
