# Stage-0 Feasibility, First-Party Overlap & Oracle Case Verification — Randomization Support Audit

**Date:** 2026-11-24  
**Workspace:** `D:\AI_Science\antigravity\randomization_support_audit_20261124`  
**Research Question:** Can AI reconstruct the original randomization support from a real trial methods excerpt plus joined public replication tables, and distinguish outcomes of admissible random reassignment from matched-total illegal reassignments that preserve the overall treated count yet violate cluster/block constraints? *(Research on statistical correctness, not campaigning.)*

---

## 1. First-Party Literature Overlap Audit

1. **CausalVerify ([`arXiv:2609.07944v1`](https://arxiv.org/abs/2609.07944), full HTML inspected):**
   - *"CausalVerify: End-to-End Verification of Causal Analyses by Language Models"* evaluates LLM causal inference workflows across 4 layers (method recognition, design specification, executable implementation, estimand recovery) on **observational quasi-experimental designs** (DID, Event Study, IV, RDD: `259` real economics paper contexts, `100` fixed-seed synthetic scenarios, `23` paper-twin pairs).
   - First-party full-text keyword check: `Fisher: 0 hits`, `RCT: 0 hits`, `randomiz*: 2 hits`, `cluster: 2 hits`.
   - **Exact Non-Overlap:** CausalVerify does **not** evaluate reconstructing exact randomization support (randomized unit, ID mapping, block/pair strata, treated quotas) from real RCT methods + joined public replication tables, nor rejecting matched-total illegal cluster/block reassignments.
2. **Agentic Data Science Multiverse ([`PMC13393493`](https://pmc.ncbi.nlm.nih.gov/articles/PMC13393493/), *PNAS* 2026, full XML inspected):**
   - *"Many AI analysts, one dataset: Navigating the agentic data science multiverse"* (Bertrán, Fogliato & Wu) measures analytical dispersion and persona steerability of autonomous AI analysts + an LLM compliance auditor on `soccer`, `metr-rct` (coding RCT), and `anes-views`.
   - First-party full-text keyword check: `Fisher: 0 hits`, `randomiz*: 1 hit`, `block: 1 hit`, `cluster: 2 hits`.
   - **Exact Non-Overlap:** Focuses on subjective dispersion across *defensible* analytical forks in a multiverse, whereas violating an RCT's exact randomization support while holding total treated count constant is **objectively mathematically invalid** (not a valid specification fork).
3. **Very Close Direct Prior — Gao & Xiao (2026) ([`arXiv:2611.25198v1`](https://arxiv.org/html/2611.25198v1), full HTML inspected):**
   - *"When AI Analysts Disagree: Agentic Multiverse Analysis and the Robustness of Empirical Research"* directly reports in **§4.1 ("Step 4: Code review gate")** and Appendix A that among blocker/major findings across ten autonomous assessments, *"one agent mislabeled an invalid permutation procedure as a randomization test"* (and another built a placebo test contaminated by the true effect; both produced plausible numbers and were caught by the code-review gate before human review; see also §5 / Appendix G.6 on contested displaced-cutoff permutation exchangeability).
   - **No Priority Claim:** Gao & Xiao (2026) §4.1 already document an invalid permutation procedure produced by an AI agent in empirical research workflows; this Stage-0 pilot makes zero claim of priority and serves solely as a bounded diagnostic probe of randomization-support reconstruction on two public trials.

---

## 2. Verified Real Trial Sources & Privacy / Indeterminate-Arm Audit

All artifacts contain **public de-identified aggregate market/cluster metadata only — ZERO individual voter or personal records**.

| Feature | Trial 1: `RockTheVote` (Green & Vavreck 2008) | Trial 2: `Bangladesh Mask Cluster-RCT` (Abaluck et al. 2022, *Science*) |
|---|---|---|
| **Domain** | Voter mobilization (`Political Analysis` 16:138–152) | **Non-election public health / epidemiology** (`Science` 375(6577):eabi9069) |
| **Primary Public Source & License** | CRAN [`pscl_1.5.9.tar.gz`](https://cran.r-project.org/src/contrib/pscl_1.5.9.tar.gz) (`RockTheVote.rda` + `RockTheVote.Rd`, GPL-2); cross-referenced with Yale CC0 [`doi:10.60600/YU/OYIPLJ`](https://dataverse.yale.edu/dataset.xhtml?persistentId=doi%3A10.60600%2FYU%2FOYIPLJ) *(note: Yale Dataverse API returned HTTP 403 to automated HTTP client; verified directly on CRAN `pscl` without bypassing WAF)* | Official Zenodo [`doi:10.5281/zenodo.5703876`](https://zenodo.org/records/5703876) (`bd-mask-rct.zip`, **CC-BY-4.0**), extracting ONLY aggregate union tables (`union_reg_sample.dta`, `union_baseline_blood_stats.dta`), READMEs, and authors' RI `.do` scripts (`10a_reg_rand_inf_symp_sero.do`, `10b_reg_rand_inf_symp.do`) via HTTP Range (`< 160 KB`) |
| **Randomized Unit & Data ID** | Cable TV system / single-zip market (`85` rows; `market_id` from original row indices; aggregate counts `r`, `n`, `p`) | Rural Bangladesh village (`572` complete-blood-baseline clusters joined on `union`, where `README.md` maps `village -> union` de-identified 7-digit code; `isid union`) |
| **Blocks & Exact Quotas Verified** | `40` strata (`strata` 1..40): `35` blocks of size `2` (`m=1`), `3` blocks of size `3` (`strata 3, 8, 25`: `m=1`), `2` blocks of size `3` (`strata 6, 20`: `m=2`); total `42/85` treated — **100% verified against `RockTheVote.Rd` & `RockTheVote.rda`** | `286` matched pairs (`pairID`) in joined blood-baseline table (`298` in `union_reg_sample.dta`): **100% verified `pair_size == 2`, `n_treated == 1`, `n_districts == 1`, `n_waves == 1`**, directly matching authors' `10a_reg_rand_inf_symp_sero.do` (`bys pairID: assert(_N == 2); assert count_treat == 1`) |
| **Real Document-to-Data Ambiguity** | `treatedIndex` sequential counter looks like a group ID; aggregate voter counts `r`/`n` tempt unit-level confusion; unequal size-2 & size-3 strata | Prose refers to *"villages paired within districts across 7 waves"*; table encodes villages as `union` and contains real distractor hierarchy columns `district`, `wave`, `surgical_pair`, `cloth_pair` |
| **Indeterminate / Excluded Arms** | None (single binary `treated` arm; all matched illegals violate unambiguously via all-0 or all-1 blocks) | Treated-only sub-arms (`signage`, `incentive`, `text_village`, `treat_color`, household sub-arms) lack explicit RI enumeration in `10a_reg_rand_inf_symp_sero.do` -> **marked indeterminate & excluded from exact labels** |

---

## 3. Exact Small-Block Enumeration, Independent Double-Check & Illustrative Case

Implemented in [`oracle_support_enumerator.py`](oracle_support_enumerator.py):
- **Independent Cross-Check:** Method 1 (constructive Cartesian product of $\binom{n_b}{m_b}$ per block, equivalent to `randomizr::block_ra` / `ri2::obtain_permutation_matrix`) vs. Method 2 (independent brute-force enumeration of all $\binom{N}{M}$ same-total vectors filtered by study-code per-block assertions). Verified **100% exact set equality** across all `12` small oracle cases (`STAGE0_ORACLE_CASES_12.json`, local-only SHA `96d0ee40...`: `6` RockTheVote + `6` Bangladesh Mask CRT) and all `40` completely non-overlapping matched cases (`STAGE0_MATCHED_40_CASES.json`, local-only SHA `dde8d956...`: `13` RockTheVote using `39/40` strata + `27` Bangladesh Mask CRT using `81/286` pairs, **zero cluster overlap**).

### Illustrative Exact Case (`BDM_01` — Bangladesh Mask Cluster-RCT, Non-Election Public Health)
- **Subset:** `3` matched pairs (`pairID in {17, 24, 26}`, `6` village clusters `union`) **all inside the same `district = 2019`, same `wave = 5`, and same `surgical_pair = 1`**.
- **Exact Support:** $|S| = 2^3 = 8$ admissible vectors out of $\binom{6}{3} = 20$ same-total vectors (`12` matched-total illegal vectors, all preserving exact total treated `= 3`, exact `district = 2019` treated `= 3`, and exact `wave = 5` treated `= 3`).
- **Observed Assignment (`1` treated per `pairID`):**
  - `pairID 17`: `2019128 -> 1`, `2019131 -> 0`
  - `pairID 24`: `2019143 -> 0`, `2019148 -> 1`
  - `pairID 26`: `2019145 -> 1`, `2019147 -> 0`
- **Positive Admissible Reassignment (`oracle_valid = True`):** `{2019128: 0, 2019131: 1, 2019143: 0, 2019148: 1, 2019145: 0, 2019147: 1}` (total `= 3`, `1/2` in every `pairID`, distinct from observed).
- **Matched Illegal Reassignment (`oracle_valid = False`):** `{2019128: 0, 2019131: 1, 2019143: 0, 2019148: 0, 2019145: 1, 2019147: 1}` — **exact same total treated (`3/6`), exact same district treated (`3`), exact same wave treated (`3`), exact same `surgical_pair` treated (`3`)**, yet violates `pairID` (`P24: 0 != 1`, `P26: 2 != 1`).
- *(Companion RockTheVote illustrative case `RTV_01` covers strata `{1, 2, 3}` — sizes `{2, 2, 3}`, quotas `{1, 1, 1}`, $|S| = 12$ of $\binom{7}{3} = 35$, with matched minimal-swap illegal `S1:1/2, S2:0/2, S3:2/3`, exact total `= 3/7`.)*

---

## 4. Local Callable Model Route Feasibility

- **Hardware & Precision:** Local `NVIDIA GeForce RTX 5060 Laptop GPU` (`8,151 MiB` VRAM), `PyTorch 2.11.0+cu128`, `Transformers 5.24.0`, loaded in **`BF16` (`torch.bfloat16`, NOT quantized)** (zero paid APIs, zero secret discovery, zero global installs). Scope is strictly limited to these two small local BF16 models; do not extrapolate to frontier models.
- **Model Family 1 (Verified Locally Callable Offline, BF16):** `Qwen/Qwen2.5-1.5B-Instruct` (pinned `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, Apache-2.0, `gated=False`, `2.88 GB`, `torch.bfloat16`; smoke-tested: `LOAD = 6.05 s`, `GEN = 1.03 s`, `VRAM = 3.10 GB`).
- **Model Family 2 (Verified Locally Callable Offline, BF16):** `ibm-granite/granite-3.1-2b-instruct` (pinned `bbc2aed595bd38bd770263dc3ab831db9794441d`, Apache-2.0, `gated=False`, `4.72 GB`, `torch.bfloat16`; smoke-tested: `GEN = 1.04 s`, `VRAM = 5.08 GB`, `LOAD = 345.28 s` including initial download).
