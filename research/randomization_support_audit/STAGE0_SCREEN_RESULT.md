# Stage-0 Feasibility & Bounded Screen Report — Randomization Support Reconstruction Audit (FROZEN LIMITED NEGATIVE / DIAGNOSTIC ARCHIVE)

**Date Sealed:** 2026-11-24  
**Workspace:** `D:\AI_Science\antigravity\randomization_support_audit_20261124`  
**Pre-Locked Gate Decision:** **`STOP_OR_REFRAME_STAGE0_GATE_FAILED`** (frozen as a limited negative/diagnostic archive)  
**Scope & Non-Extrapolation Notice:** Bounded native Stage-0 diagnostic screen across **two actual public trials** (`RockTheVote_2008` `N = 13` + `Bangladesh_Mask_CRT_2022` `N = 27` = `40` completely non-overlapping matched cases) evaluated on **two small local `BF16` (`torch.bfloat16`, non-quantized) open-weights models** (`Qwen/Qwen2.5-1.5B-Instruct` and `ibm-granite/granite-3.1-2b-instruct`). **Do NOT extrapolate these small-BF16 results to frontier models or larger model tiers.** Public de-identified aggregate cluster/market metadata only — zero individual voter or personal records. **No paper, PDF, news, leaderboard, priority, or novelty claims.**

---

## 1. Executive Decision & Core Empirical Findings

We **STOP and freeze** at Stage-0 in strict compliance with the pre-locked conjunctive gate in [`STAGE0_SCREEN_PROTOCOL.md`](STAGE0_SCREEN_PROTOCOL.md) (SHA-256 `c22c6b6d9a3e7203d76a3107e52abd2ebe4fa48c84918500e51af2060ec268c9`).

1. **Direct Results Are Opposite Constant Response Tendencies — NOT a Meaningful Reproduced False-Acceptance Mechanism (`0/40` Paired Exact Accuracy in BOTH BF16 Families):**
   - `Qwen/Qwen2.5-1.5B-Instruct` (`BF16`) accepted **`0/40`** legal admissible assignments and **`0/40`** matched-total illegal assignments (`Direct FA = 0/40`, `VAC = 0/40`, `PEA = 0/40`, `Parse fails = 0`, constant-`ILLEGAL` collapse).
   - `ibm-granite/granite-3.1-2b-instruct` (`BF16`) accepted **`40/40`** legal admissible assignments and **`40/40`** matched-total illegal assignments (`Direct FA = 40/40`, `VAC = 40/40`, `PEA = 0/40`, `Parse fails = 0`, constant-`ADMISSIBLE` collapse).
   - **Mandatory Constant-Label Shortcut Disclosure:** In `stage0_screen_summary.json`, Granite's literal single-family boolean (`family_all_pass`) evaluated `true` strictly because its `40/40` constant-`ADMISSIBLE` shortcut satisfied `Direct FA >= 8` and `VAC >= 40%` while achieving **`0/40` paired discrimination**. Similarly, `0/40` reorder/ID-renaming flips in both families are a trivial artifact of constant-label collapse, not calibrated invariance. The **joint pre-locked conjunctive gate failed** (`all_families_pass = false`, `decision = STOP_OR_REFRAME_STAGE0_GATE_FAILED`).
2. **Extracted Schemas (`extract_verify`) vs. Gold-Schema Deterministic Verifier (`gold_verify = 40/40`):**
   - Given gold schemas, the identical deterministic Python verifier (`gold_verify`) achieved **`40/40` (`100.0%`)** paired exact accuracy (`0/40` FA), confirming that a correctly filled schema solves support trivially.
   - **`Qwen/Qwen2.5-1.5B-Instruct` (`extract_verify`):** `17/40` legitimate accepted (`42.5%`), **`12/40` illegal accepted (`30.0%`)** — all `12/12` in `RockTheVote_2008`, where it selected aggregate count column `n` as `block_col` with `quota_rule = "total_only"` — paired exact **`5/40` (`12.5%`)**, **`35/40` schema errors** (`13/13` RTV, `22/27` BDM). On `Bangladesh_Mask_CRT_2022`, it still identified `unit_col = "union"` and `block_col = "pairID"` on `27/27` (`100%`) cases (`0/27` illegal accepted), failing mainly on quota values (`14/27` put pair size `2` instead of treated count `1`; `8/27` keyed `block_quotas` by 7-digit de-identified `union` codes).
   - **`ibm-granite/granite-3.1-2b-instruct` (`extract_verify`):** **`24/40` legitimate accepted (`60.0%`)**, **`0/40` invalid accepted (`0.0%`)**, paired exact **`24/40` (`60.0%`)** (`20/27` BDM, `4/13` RTV), **`16/40` schema errors** (`9/13` RTV, `7/27` BDM). Raw-output inspection shows `Granite-3.1-2B` already wrote exact gold `(unit_col, block_col)` in **`40/40` (`100.0%`)** raw responses (`13/13` `market_id`/`strata`, `27/27` `union`/`pairID`), with remaining errors driven by small-model JSON/quota-serialization bugs (duplicate keys `{"17": 1, "17": 0}`, repetitive token truncation at `max_new_tokens = 200`, or prose-number bleed).
3. **Out-of-Scope Counterfactual Cross-Table Mapping Test (NOT Run):**
   - A counterfactual cross-table mapping test (e.g., swapping column semantics or testing whether models actually rely on methods prose vs. transparent column-name priors like `strata` / `pairID`) could distinguish genuine evidence use from column-name shortcuts. That test **was NOT run** and is explicitly **out of scope now** — we do **not** run post-hoc follow-ups on the same development cases to rescue the failed gate.

---

## 2. First-Party Literature Context & Very Close Prior (No Priority Claim)

Full details are sealed in [`STAGE0_FEASIBILITY_AND_OVERLAP.md`](STAGE0_FEASIBILITY_AND_OVERLAP.md):

- **Very Close Direct Prior — Gao & Xiao (2026) ([`arXiv:2611.25198v1`](https://arxiv.org/html/2611.25198v1), *"When AI Analysts Disagree: Agentic Multiverse Analysis and the Robustness of Empirical Research"*, §4.1 & Appendix A):** Directly reports that among blocker/major findings caught by their Step-4 code-review gate across ten autonomous assessments, *"one agent mislabeled an invalid permutation procedure as a randomization test"* (alongside a contaminated placebo test, both producing plausible numbers before human review; see also §5 / Appendix G.6 on contested displaced-cutoff permutation exchangeability). Because Gao & Xiao (2026) §4.1 already document an invalid permutation procedure used by an AI agent, this archive makes **no priority or novelty claim**.
- **CausalVerify ([`arXiv:2609.07944v1`](https://arxiv.org/abs/2609.07944)):** Evaluates observational quasi-experimental workflows (DID, Event Study, IV, RDD; full-text hits: `Fisher=0`, `RCT=0`, `randomiz*=2`, `cluster=2`).
- **Agentic Data Science Multiverse ([`PMC13393493`](https://pmc.ncbi.nlm.nih.gov/articles/PMC13393493/), *PNAS* 2026):** Studies defensible analytical dispersion and persona steerability (`soccer`, `metr-rct`, `anes-views`; full-text hits: `Fisher=0`, `randomiz*=1`, `block=1`, `cluster=2`).

---

## 3. Two Verified Public Trial Sources & Independent Oracle Enumeration

- **Trial 1 — `RockTheVote_2008`** (Green & Vavreck 2008, *Political Analysis* 16:138–152): Verified from CRAN `pscl_1.5.9.tar.gz` (`RockTheVote.rda` SHA `851400e266058e24cb46b964a401bf687933a26a1f2657a8630b86302f29ae4d`; `RockTheVote.Rd` raw tarball LF SHA `978b44ea4097e68f28219501a4de5f0aa02e1c2e24e85b24003440bd3a80ce5c`, local Windows CRLF SHA `0c80edd061516294082d818188d57259d7ebf43273bb15b0f1c385aeb716173d`, GPL-2; Yale Dataverse API `doi:10.60600/YU/OYIPLJ` returned HTTP 403 to automated HTTP client and was not bypassed). `85` cable TV markets, `40` strata (`35` pairs of `1/2`; strata `3, 8, 25` size `3` with `m=1`; strata `6, 20` size `3` with `m=2`; `42/85` treated). Public aggregate market counts only; zero individual voter records.
- **Trial 2 — `Bangladesh_Mask_CRT_2022`** (Abaluck et al. 2022, *Science* 375(6577):eabi9069; **non-election public health**): Verified from official Zenodo `doi:10.5281/zenodo.5703876` (`bd-mask-rct.zip`, CC-BY-4.0), extracting `< 160 KB` via HTTP Range (`union_reg_sample.dta` SHA `61c4784c70fcd5dbea84bfd3a39abb64dc3c9879524b5d294f3159b74ad654a9`, `union_baseline_blood_stats.dta` SHA `f7f8a8d05701f504fb74341cfebd771b39fa5346392698d42cf5fbabaa304cb4`, READMEs, and authors' RI script `10a_reg_rand_inf_symp_sero.do` SHA `647aceac42a07d4deb658c68f94aef25846a7dc9dbc28a837a900b4bd9c84abe`). Joined aggregate blood-baseline table has `572` de-identified `union` clusters (`286` complete pairs, `100%` `pair_size == 2`, `n_treated == 1`, `n_districts == 1`, `n_waves == 1`). Treated-only sub-arms (`signage`, `incentive`, `text_village`, `treat_color`, household sub-arms) were marked indeterminate and excluded.
- **Independent Exact Oracle Verification (`oracle_support_enumerator.py`):** Verified **100% set equality** between constructive Cartesian block enumeration and brute-force same-total assertion filtering across `12` small oracle cases (`STAGE0_ORACLE_CASES_12.json`, local-only SHA `96d0ee402501bf474c5553cb953ad19c57db59b56ca00761ff94de5abb7866f5`) and `40` completely non-overlapping matched cases (`STAGE0_MATCHED_40_CASES.json`, local-only SHA `dde8d95694b0c6bfc9e806d3d88d3b9b3fe4ffb327ff96ad6aaff9192d25d9f1`: `13` RTV using `39/40` strata + `27` BDM using `81/286` pairs, zero cluster overlap, all `27/27` BDM matched illegals preserving exact total, `district`, and `wave` treated counts).

---

## 4. Execution Integrity, Initial Diagnostic-Key Error Patch & Run Receipts

- **Hardware & Precision (`BF16`, NOT Quantized):** Local `NVIDIA GeForce RTX 5060 Laptop GPU` (`8,151 MiB` VRAM), `PyTorch 2.11.0+cu128`, `Transformers 5.24.0`, `dtype=torch.bfloat16`, greedy deterministic `do_sample=False` (zero paid APIs, zero secret discovery, zero global installs, zero simulated scores):
  - Family 1: `Qwen/Qwen2.5-1.5B-Instruct`, rev `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` (`BF16`, Apache-2.0, ungated).
  - Family 2: `ibm-granite/granite-3.1-2b-instruct`, rev `bbc2aed595bd38bd770263dc3ab831db9794441d` (`BF16`, Apache-2.0, ungated).
- **Initial Run Interruption & Exact Runner-Only Patch:**
  - Initial run (`task-1792`, PID `20288`, runner SHA `eb664be6f9f58c6b84f221036cd45f705839f81450f2ee7774be04248cce4267`) terminated on case `7/40` (`RTV_07`) with `KeyError: 'extracted_unit_col'` at line 475 because the `schema is None` early return at line 219 omitted three logging keys (`extracted_unit_col`, `extracted_block_col`, `extracted_quota_rule`) from `diag`.
  - **Exact Patch Scope:** Added only those three `None` keys to the `schema is None` diagnostic dictionary in [`run_stage0_support_screen.py`](run_stage0_support_screen.py) (runner SHA `eb664be6f9f58c6b84f221036cd45f705839f81450f2ee7774be04248cce4267` -> `b83468242770cdb97c7572e50d83f70c78d0066879a4f180358d83947b4d89ab`). **Conditions, locked protocol (`c22c6b6d...`), benchmark (`dde8d956...`), prompts, models (`BF16`), decoding, and deterministic verifier logic remained completely untouched.**
- **Completed Native Run Receipts (`task-1805`):**
  - **Real PID:** `34272` | **Wall Time:** `948.402 s` (`qwen25_1p5b`: `5.645 s` load + `327.075 s` inference; `granite31_2b`: `2.639 s` load + `611.195 s` inference)
  - **Gold-Schema Verifier (`gold_verify`):** `40/40` positive accepted, `40/40` illegal rejected, `0/40` FA, **`100.0%` paired exact accuracy**
  - [`stage0_screen_outputs/stage0_screen_summary.json`](stage0_screen_outputs/stage0_screen_summary.json): SHA-256 `d2f5de11be8db0ede04d4d7e4859b376664cac00ed251a822ec6ec2d82cbda90`
  - [`stage0_screen_outputs/stage0_screen_per_case.json`](stage0_screen_outputs/stage0_screen_per_case.json): SHA-256 `2d888580e1a9fec9363d531a9d70116d43f0d0d035fa13521c5b12b8a08b85de`
  - Native local-only raw responses (`raw_responses_qwen25_1p5b.jsonl`, `160` rows, not redistributed in git): SHA-256 `8aabba2e8e6e09c54687e213c70897bcd71c376ab9419fb9459ed04cb47b3ea6`
  - Native local-only raw responses (`raw_responses_granite31_2b.jsonl`, `160` rows, not redistributed in git): SHA-256 `daf99f1b8b8b1f416b90fb10c971ec3a9d95a1f4901a1771867c1fbe8a248a41`

---

## 5. Trial-Wise Descriptive Results & Pre-Locked Gate Outcome

*(Reported descriptively per trial source — NEVER treating `40` cases across `2` trials as `40` independent trials.)*

| Model Family (`BF16`, Pinned Rev) | Trial / Slice (`N`) | Direct FA (Illegal Acc.) | Direct VAC (Legal Acc.) | Direct PEA (Paired) | Parse Fails | Reorder Flips | EV FA (Illegal Acc.) | EV VAC (Legal Acc.) | EV PEA (Paired) | EV SchemaErr | Raw Text Gold `(unit_col, block_col)` |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Oracle (`gold_verify`)** | Overall (`40`) | — | — | — | — | — | **0/40 (0.0%)** | **40/40 (100%)** | **40/40 (100%)** | **0/40** | `40/40` (gold) |
| **`Qwen2.5-1.5B-Instruct`** (`989aa7980e4c`) | `RockTheVote_2008` (`13`) | 0/13 | 0/13 | 0/13 | 0 | 0/14 | 12/13 (92.3%) | 12/13 (92.3%) | 0/13 | 13/13 | 0/13 (`b="n"`, `total_only`) |
| **`Qwen2.5-1.5B-Instruct`** (`989aa7980e4c`) | `Bangladesh_Mask_CRT_2022` (`27`) | 0/27 | 0/27 | 0/27 | 0 | 0/26 | 0/27 | 5/27 (18.5%) | 5/27 (18.5%) | 22/27 | **27/27 (100%)** |
| **`Qwen2.5-1.5B-Instruct`** | **Pooled Descriptive (`40`)** | **0/40 (0.0%)** | **0/40 (0.0%)** | **0/40 (0.0%)** | **0** | **0/40** | **12/40 (30.0%)** | **17/40 (42.5%)** | **5/40 (12.5%)** | **35/40** | **27/40 (67.5%)** |
| **`Granite-3.1-2B-Instruct`** (`bbc2aed595bd`) | `RockTheVote_2008` (`13`) | 13/13 (100%) | 13/13 (100%) | 0/13 | 0 | 0/14 | 0/13 | 4/13 (30.8%) | 4/13 (30.8%) | 9/13 | **13/13 (100%)** |
| **`Granite-3.1-2B-Instruct`** (`bbc2aed595bd`) | `Bangladesh_Mask_CRT_2022` (`27`) | 27/27 (100%) | 27/27 (100%) | 0/27 | 0 | 0/26 | 0/27 | 20/27 (74.1%) | 20/27 (74.1%) | 7/27 | **27/27 (100%)** |
| **`Granite-3.1-2B-Instruct`** | **Pooled Descriptive (`40`)** | **40/40 (100%)** | **40/40 (100%)** | **0/40 (0.0%)** | **0** | **0/40** | **0/40 (0.0%)** | **24/40 (60.0%)** | **24/40 (60.0%)** | **16/40** | **40/40 (100%)** |

### Pre-Locked Conjunctive Advance Gate (`STAGE0_SCREEN_PROTOCOL.md` §3)
- **`Qwen2.5-1.5B-Instruct` (`BF16`):** **FAIL** (`C1` fail: `Direct FA = 0/40`, `VAC = 0.0%`; `C3` fail: `0/13` RTV, `0/27` BDM; `C2` `0/40` flips is a constant-`ILLEGAL` collapse artifact; `C4` pass: `EV_FA = 12`, `EV_SchemaErr = 35`).
- **`Granite-3.1-2B-Instruct` (`BF16`):** Literal programmatic gate flags `true` (`C1`: `40/40`, `100%`; `C2`: `0/40`; `C3`: `13/13`, `27/27`; `C4`: `EV_SchemaErr = 16`), **explicitly disclosed as a constant-`ADMISSIBLE` label shortcut (`Direct PEA = 0/40`) rather than a valid false-acceptance mechanism**.
- **Joint Conjunctive Gate:** **`FAIL` -> `STOP_OR_REFRAME_STAGE0_GATE_FAILED`** -> frozen as a limited negative/diagnostic archive.
