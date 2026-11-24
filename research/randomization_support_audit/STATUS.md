# Project Status — Randomization Support Reconstruction Audit (FROZEN LIMITED NEGATIVE / DIAGNOSTIC ARCHIVE)

- **State:** `FROZEN_LIMITED_NEGATIVE_DIAGNOSTIC_ARCHIVE` (`STOP_OR_REFRAME_STAGE0_GATE_FAILED`)
- **Date Sealed:** 2026-11-24
- **Scope:** Two actual public trials (`RockTheVote_2008` `N = 13` + `Bangladesh_Mask_CRT_2022` `N = 27` = `40` non-overlapping matched cases) on two small local **`BF16` (`torch.bfloat16`, non-quantized)** models (`Qwen/Qwen2.5-1.5B-Instruct`, `ibm-granite/granite-3.1-2b-instruct`). No frontier extrapolation; no counterfactual cross-table rescue run; no paper, PDF, news, leaderboard, priority, or novelty claims.
- **Very Close Prior Cited (No Priority Claim):** Gao & Xiao (2026) [`arXiv:2611.25198v1`](https://arxiv.org/html/2611.25198v1) §4.1 already report an invalid permutation procedure used by an AI agent.
- **No-Touch Guarantees Preserved:** `main` (`940709d372ae3716e09daf771d5438d07232d022`) and prior PRs `#13–#17` remain completely untouched (PR `#17` receipt appended locally to LinePilot `STATUS.md` only, with no new LinePilot commit/PR).

## Sealed Native Run Summary (`PID = 34272`, `Wall = 948.402 s`)
- **Initial Launch Crash & Scoped Runner-Only Patch:** First launch (`task-1792`, PID `20288`, runner SHA `eb664be6...`) hit `KeyError: 'extracted_unit_col'` at line 475 on case `7/40` (`RTV_07`) when `schema is None` returned early without three diagnostic logging keys. Patched ONLY those 3 `None` keys in `run_stage0_support_screen.py` (`eb664be6... -> b8346824...`), leaving conditions, locked protocol (`c22c6b6d...`), benchmark (`dde8d956...`), prompts, BF16 models, and verifier logic completely untouched.
- **Direct (`0/40` Paired Exact in BOTH BF16 Families — Opposite Constant Response Tendencies):**
  - `Qwen/Qwen2.5-1.5B-Instruct` (`BF16`): `0/40` legal accepted, `0/40` illegal accepted, `0/40` paired, `0/40` reorder flips (constant-`ILLEGAL` collapse).
  - `ibm-granite/granite-3.1-2b-instruct` (`BF16`): `40/40` legal accepted, `40/40` illegal accepted, `0/40` paired, `0/40` reorder flips (constant-`ADMISSIBLE` shortcut — explicitly disclosed even though Granite's literal single-family gate boolean was `true`).
- **Extracted Schemas (`extract_verify`) vs. Gold Verifier (`gold_verify = 40/40`):**
  - `Qwen/Qwen2.5-1.5B-Instruct`: `17/40` legal accepted, `12/40` illegal accepted (all `12` in RockTheVote, selecting `n` as `block_col` + `total_only`), `5/40` paired, `35` schema errors.
  - `ibm-granite/granite-3.1-2b-instruct`: `24/40` legal accepted, `0/40` invalid accepted, `24/40` paired, `16` schema errors (`40/40` raw text gold `(unit_col, block_col)`).
  - `gold_verify`: `40/40` paired exact accuracy (`100.0%`).
- **Joint Pre-Locked Gate:** **FAILED (`STOP_OR_REFRAME_STAGE0_GATE_FAILED`)**.

## Sealed SHA-256 Receipts (Archived + Native Local-Only)
- Pre-locked protocol (`STAGE0_SCREEN_PROTOCOL.md`, archived): `c22c6b6d9a3e7203d76a3107e52abd2ebe4fa48c84918500e51af2060ec268c9`
- Runner (`run_stage0_support_screen.py`, archived): `b83468242770cdb97c7572e50d83f70c78d0066879a4f180358d83947b4d89ab`
- Summary (`stage0_screen_outputs/stage0_screen_summary.json`, archived): `d2f5de11be8db0ede04d4d7e4859b376664cac00ed251a822ec6ec2d82cbda90`
- Per-case evidence (`stage0_screen_outputs/stage0_screen_per_case.json`, archived): `2d888580e1a9fec9363d531a9d70116d43f0d0d035fa13521c5b12b8a08b85de`
- Native local-only oracle 12-case JSON (`STAGE0_ORACLE_CASES_12.json`, not redistributed): `96d0ee402501bf474c5553cb953ad19c57db59b56ca00761ff94de5abb7866f5`
- Native local-only 40-case JSON (`STAGE0_MATCHED_40_CASES.json`, not redistributed): `dde8d95694b0c6bfc9e806d3d88d3b9b3fe4ffb327ff96ad6aaff9192d25d9f1`
- Native local-only raw responses `qwen25_1p5b` (`raw_responses_qwen25_1p5b.jsonl`, `160` rows, not redistributed): `8aabba2e8e6e09c54687e213c70897bcd71c376ab9419fb9459ed04cb47b3ea6`
- Native local-only raw responses `granite31_2b` (`raw_responses_granite31_2b.jsonl`, `160` rows, not redistributed): `daf99f1b8b8b1f416b90fb10c971ec3a9d95a1f4901a1771867c1fbe8a248a41`
