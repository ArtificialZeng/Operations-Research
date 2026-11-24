# Stage-0 Locked Bounded Screen Protocol — Randomization Support Reconstruction (`N = 40` Non-Overlapping Matched Cases)

**Date Locked:** 2026-11-24 (BEFORE running ANY model scoring on the 40 cases)  
**Scope:** Bounded Stage-0 screen ONLY across two verified real trials (`RockTheVote_2008` `N = 13` + `Bangladesh_Mask_CRT_2022` `N = 27` = `40` completely non-overlapping matched cases, zero shared clusters). No PDF, PR, submission, announcement, or publication claims.

---

## 1. Benchmark & Controls (`STAGE0_MATCHED_40_CASES.json`, SHA `dde8d956...`)

- **Trial 1 (`RockTheVote_2008`, `N = 13` cases):** `13` disjoint `3`-block subsets (`39/40` strata, `83/85` cable markets, `0` overlap). Every matched illegal vector preserves exact total treated count AND creates an unambiguous single-swap violation (`0/n_b` or `n_b/n_b` block).
- **Trial 2 (`Bangladesh_Mask_CRT_2022`, `N = 27` cases):** `27` disjoint `3`-pair subsets (`81/286` pairs, `162/572` village clusters `union`, `0` overlap). Every case lies inside a single `(district, wave)` and every matched illegal vector preserves exact total treated count, exact `district` treated count, and exact `wave` treated count while violating ONLY `pairID` (`0/2` and `2/2`).
- **Neutral Reorder & Opaque ID-Renaming Control (`20` balanced cases = `40` candidate judgments: `7` RockTheVote `RTV_01..RTV_07` + `13` Bangladesh Mask CRT `BDM_01..BDM_13`):** Shuffles row order in both joined tables and bijectively renames unit IDs (`MKT_xx -> C01..`, `union -> 800xxxx`, plus `pairID -> 901..903` on Bangladesh Mask CRT while preserving `strata` numbers in RockTheVote to stay text-consistent with `RockTheVote.Rd`).

---

## 2. Two Model Families & Two Paired Conditions (Greedy Deterministic `do_sample = False`)

- **Model Family 1:** `Qwen/Qwen2.5-1.5B-Instruct`, pinned revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` (Apache-2.0, ungated local).
- **Model Family 2:** `ibm-granite/granite-3.1-2b-instruct`, pinned revision `bbc2aed595bd38bd770263dc3ab831db9794441d` (Apache-2.0, ungated local).
- **Raw Audit Trail:** Every prompt, raw model response, parsed JSON/verdict, and SHA-256 hash is persisted in JSONL; zero simulated scores.

### Condition A: Direct Judgment (`direct`)
- Input: Real primary methods excerpt + joined public replication tables (Table 1 & Table 2) + one candidate reassignment `{unit_id: 0/1}` (total treated count always matches observed).
- Output schema: strict JSON `{"verdict": "ADMISSIBLE" | "ILLEGAL", "reason": "<concise explanation>"}`.
- Evaluated on all `40` positive admissible controls + `40` matched-total illegal vectors (`80` calls/model), plus `40` neutral reorder/ID-renaming control items (`20` admissible + `20` illegal).

### Condition B: Same Model Structured Extraction + Deterministic Verifier (`extract_verify`)
- Input: **Identical** real primary methods excerpt + joined Table 1 & Table 2 (no candidate vector shown).
- Model outputs structured JSON design specification:
  ```json
  {
    "unit_col": "<column identifying each randomized unit>",
    "block_col": "<column identifying randomization block/stratum/pair, or null if unblocked>",
    "quota_rule": "observed_per_block | fixed_per_block | total_only",
    "block_quotas": {"<block_value>": <int_treated_quota>}
  }
  ```
- Deterministic Python verifier (`verify_from_extracted_schema`) joins Table 1 & Table 2 on `unit_col`, groups by `block_col`, applies extracted quotas (or observed per-block counts under `observed_per_block`, or total count under `total_only`), and checks BOTH the admissible and illegal assignments deterministically.
- **Gold-Schema Oracle Check (`gold_verify`):** Runs the exact same deterministic verifier with gold `(unit_col, block_col, block_quotas)`, verifying `0/40` false acceptances and `40/40` (`100.0%`) paired exact accuracy (confirming a correctly filled schema trivially solves support).

---

## 3. Pre-Locked Metrics & Conjunctive Advance Threshold

Reported overall AND **trial-wise descriptively** (`RockTheVote` `N = 13` vs. `Bangladesh Mask CRT` `N = 27`; never treating `40` cases as `40` independent trials):
- **Primary Failure Metric:** `FA` = incorrect acceptance count & rate on matched-total illegal assignments (out of `40`).
- **Coverage & Pairing:** `VAC` = valid acceptance coverage on true admissible controls (out of `40`); `PEA` = paired exact accuracy (both admissible=`ADMISSIBLE` AND illegal=`ILLEGAL` on the same case); explicit parse-failure count.
- **Control Stability:** `Flips` = verdict flips between original and neutral reorder/ID-renamed tables (out of `40` control judgments).
- **Extraction+Verifier Persistence:** `EV_FA` (false acceptances under `extract_verify`) and `EV_SchemaErr` (cases with wrong `unit_col`, wrong `block_col`, wrong `block_quotas`, or unparseable schema).

### Pre-Locked Conjunctive Advance Gate (ALL 4 Required to Advance Beyond Stage-0)
1. **Material Direct False Acceptances:** `Direct FA >= 8 / 40` (`>= 20.0%`) in **EACH** of the two model families (with `VAC >= 40%` so the family is not trivially collapsed to constant `ILLEGAL`), **AND**
2. **Reorder/ID-Renaming Control Stability:** `Flips <= 2` (out of `40` neutral control judgments, i.e., `<= 5.0%`) in **EACH** family (or if higher, flag instability explicitly rather than treating noisy flips as clean design-support failure!), **AND**
3. **Signal on BOTH Trial Sources:** `Direct FA >= 2 / 13` on `RockTheVote` **AND** `>= 4 / 27` on `Bangladesh Mask CRT` in **EACH** family, **AND**
4. **Persistence Under Automatic Structured Extraction + Deterministic Verifier:** `EV_FA >= 4 / 40` **OR** `EV_SchemaErr >= 4 / 40` in **EACH** family (confirming errors survive extraction + deterministic verification due to genuine document-to-data / unit-ID / block-column ambiguity).

If any prerequisite (source, oracle, or model route) is unavailable OR any conjunctive gate fails, stop cleanly and report the exact outcome.
