# Randomization-Support Reconstruction Audit — Stage-0 Limited Negative / Diagnostic Archive

**Status:** `FROZEN_LIMITED_NEGATIVE_DIAGNOSTIC_ARCHIVE` (`STOP_OR_REFRAME_STAGE0_GATE_FAILED`)  
**Scope:** Two verified public field experiments (`RockTheVote_2008` `N = 13` + `Bangladesh_Mask_CRT_2022` `N = 27` = `40` non-overlapping matched cases) evaluated on two small local **`BF16` (`torch.bfloat16`, non-quantized)** open-weights models (`Qwen/Qwen2.5-1.5B-Instruct` and `ibm-granite/granite-3.1-2b-instruct`). **No frontier extrapolation, no paper/PDF, no leaderboard/news/priority/novelty claims.**

## Summary of Sealed Stage-0 Outcome (`PID = 34272`, `948.402 s`, Summary SHA `d2f5de11...`)
- **Direct Judgment (`0/40` Paired Exact Accuracy in BOTH BF16 families):** Opposite constant response tendencies rather than a meaningful reproduced false-acceptance mechanism — `Qwen2.5-1.5B` accepted `0/40` legal and `0/40` illegal; `Granite-3.1-2B` accepted `40/40` legal and `40/40` illegal (Granite's literal single-family gate flag evaluated `true` strictly via this constant-`ADMISSIBLE` shortcut; joint pre-locked conjunctive gate **FAILED**).
- **Structured Extraction + Deterministic Verifier (`extract_verify`):** `Qwen2.5-1.5B` accepted `17/40` legal and `12/40` illegal (all `12` in RockTheVote, selecting `n` as `block_col` + `total_only`), paired `5/40`, `35` schema errors; `Granite-3.1-2B` accepted `24/40` legal and `0/40` invalid, paired `24/40`, `16` schema errors (`40/40` raw text gold `(unit_col, block_col)`).
- **Gold-Schema Deterministic Verifier (`gold_verify`):** `40/40` pairs (`100.0%`).
- **Close Prior (No Priority Claim):** Gao & Xiao (2026) [`arXiv:2611.25198v1`](https://arxiv.org/html/2611.25198v1) §4.1 already report an AI agent mislabeling an invalid permutation procedure as a randomization test.
- **Out-of-Scope Control:** A counterfactual cross-table mapping test could distinguish evidence use from column-name shortcuts but was **NOT run** and is excluded to avoid rescuing the failed gate on the same development cases.

## Reproduction Order (Clean Local Environment)
1. Create an isolated Python 3.12 environment (`numpy`, `pandas`, `scipy`, `rdata`; plus `torch` + `transformers` for GPU BF16 inference).
2. Download and hash-verify upstream public aggregate/metadata files (zero individual records):
   - `python fetch_pscl_rockthevote.py`
   - `python extract_abaluck_metadata.py`
3. Verify both trials' exact randomization support against primary docs/code:
   - `python verify_both_trials.py`
4. Regenerate and double-check the exact oracle enumeration (`STAGE0_ORACLE_CASES_12.json` SHA `96d0ee40...` and `STAGE0_MATCHED_40_CASES.json` SHA `dde8d956...`):
   - `python oracle_support_enumerator.py`
5. Verify local BF16 model routes (`check_model_routes.py`, `check_model_family2.py`), run gold-only check (`python run_stage0_support_screen.py --gold-only`), run full screen (`python run_stage0_support_screen.py`), and audit outputs (`python audit_stage0_results.py`).

## Key Sealed Files
- Pre-locked protocol: [`STAGE0_SCREEN_PROTOCOL.md`](STAGE0_SCREEN_PROTOCOL.md)
- Overlap & trial verification: [`STAGE0_FEASIBILITY_AND_OVERLAP.md`](STAGE0_FEASIBILITY_AND_OVERLAP.md)
- Final Stage-0 report: [`STAGE0_SCREEN_RESULT.md`](STAGE0_SCREEN_RESULT.md)
- Licenses & exclusions: [`LICENSES_AND_PROVENANCE.md`](LICENSES_AND_PROVENANCE.md)
- Status & SHA-256 inventory: [`STATUS.md`](STATUS.md) and [`MANIFEST.json`](MANIFEST.json)
- Native summary & per-case evidence: [`stage0_screen_outputs/stage0_screen_summary.json`](stage0_screen_outputs/stage0_screen_summary.json), [`stage0_screen_outputs/stage0_screen_per_case.json`](stage0_screen_outputs/stage0_screen_per_case.json)
