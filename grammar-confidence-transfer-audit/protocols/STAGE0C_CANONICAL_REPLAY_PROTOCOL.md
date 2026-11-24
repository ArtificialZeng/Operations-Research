# Stage-0c Locked Protocol — Bounded Canonical Replay Pilot

**Date Locked:** 2026-11-24 (PRIOR to teacher-forced replay execution)  
**Scope:** Cheap exploratory teacher-forced scoring ONLY on the `24` sealed Stage-0b `neutral_menu` free-generated pairs (`neutral_menu__G_compact_menu` vs. `neutral_menu__G_optws_menu`, identical frozen AST outcomes: `22/24` vs. `23/24`). **Zero new decoding, zero new labels, zero second model; `bfcl_future_blind_test_ids_sealed.json` (`N = 416`) stays 100% sealed and untouched.**

## 1. Motivation & Prior Art
- Stage-0b showed that on ALL `24` freely generated `neutral_menu` pairs, removing the grammar mask (`raw_pre_gnll_smt_mean`: `C->W = 100.0%`, `W->C = 66.7%`) transfers **worse** than keeping the mask (`raw_post_gnll_smt_mean`: `C->W = 79.2%`, `W->C = 70.8%`), whereas the `62.5% / 100.0%` collapse belongs only to same-path rescoring.
- Prior art: **Ye et al. (TMLR 2026, `arXiv:2604.22985v2`)** introduce `G-NLL_SMT` and AST-based structural clustering for function-calling UQ; **Kim & Kang (`arXiv:2605.27752`, *"Same Answer, Different Confidence: Protocol Sensitivity in LLM Confidence Calibration"*)** demonstrate that holding an answer and correctness label fixed, surface phrasing and scoring-protocol context materially shift token confidence and calibration.
- **Epistemic caveat:** Identical-serialization score equality on deduplicated pairs (`21/24` items whose `C` and `W` parsed calls serialize identically) is **by construction**, NOT empirical novelty.

## 2. Canonicalization & Scoring Specification
- **Canonical transform (`canonicalize_parsed_call`):** Ordinary JSON serialization (`json.dumps`), standard spaces (`separators=(", ", ": ")`, `ensure_ascii=False`), **fixed root key order** (`"name"` first, `"arguments"` second), **recursively sorted argument-map keys** inside `"arguments"`, preserving exact scalar value types (`bool`/`int`/`float`/`str`/`None`), list element order, and AST semantics. Zero hindsight or gold identifiers.
- **Pre-launch fixture gate PASSED ([`STAGE0C_CANONICAL_FIXTURE_RECEIPT.json`](../receipts/STAGE0C_CANONICAL_FIXTURE_RECEIPT.json), `a24f4885...`):** `48/48` canonical outputs match original sealed BFCL inert AST verdicts, `error_type`, and typed `parsed_call` identically; `48/48` parse cleanly under Ye26 SMT span lexer; `Prompt_Neutral` neutrality verified across all `24` items; `21/24` equal canonical pairs deduplicated -> **`27` unique teacher-forced forward passes** (`3` distinct pairs: `multiple_25`, `multiple_48`, `simple_python_202`).
- **Model & Forward Pass:** Verified local `Qwen/Qwen2.5-1.5B-Instruct` snapshot (`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, `bfloat16`, RTX 5060, `HF_HUB_OFFLINE=1`, `local_files_only=True`), same Stage-0b `Prompt_Neutral`, ONE unmasked teacher-forced forward pass per unique canonical string, float64 NLL over Ye26 semantic spans (`grammar_utils.extract_smt_token_indices`) -> `canon_gnll_smt_mean`.

## 3. Locked Analysis & Decision Gate
- **Primary comparison (all 24 items, target coverage `0.80`):** Compare `canon_gnll_smt_mean` against `raw_post_gnll_smt_mean` (strongest raw post baseline) and `raw_pre_gnll_smt_mean` across BOTH directions (`C -> W` and `W -> C`) with target in-grammar controls (`W -> W`, `C -> C`):
  1. **PRIMARY:** **Leave-One-Tool-Family-Out (LOFO)** source calibration across the `18` tool-family clusters (excluding item `i` and all sibling items in its tool-family cluster when calibrating `tau`), plus cluster-bootstrap 95% CIs (`2000` draws, seed `20261124`).
  2. **COMPANION:** Full-sample in-sample source calibration (direct audit comparison to Stage-0b).
  3. **Secondary sensitivity:** `*_gnll_smt_sum` and `*_nll_all_mean` clearly separated from primary `*_gnll_smt_mean`.
- **Small-error caveat:** Target arms contain only `1` error (`W`) and `2` errors (`C`); **NO claims of improved selective risk** are permitted.
- **Prespecified Decision Gate:** Proceed to design an independent test **ONLY IF** `canon_gnll_smt_mean` improves over `raw_post_gnll_smt_mean` on free-generation coverage transfer by **`>= 8 pp` smaller worst-direction `|cov - 0.80|`** WITHOUT worse mean `|cov - 0.80|` and WITHOUT a new operational harm (extra latency/cost audited explicitly). **Otherwise: recommend FREEZING.**

## 4. Locked Pre-Launch SHA-256 Hashes

| File | SHA-256 |
|---|---|
| `bfcl_future_blind_test_ids_sealed.json` (UNTOUCHED) | `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a` |
| `stage0b_outputs/stage0b_per_instance.jsonl` (sealed Stage-0b) | `724e921058677ee9b32d5a2e1fc74083af9d6dd29717c32bd6a9bc33ce489c9e` |
| `stage0b_outputs/stage0b_summary.json` (sealed Stage-0b) | `9036772bb510bac388dc123dadaef89a1cf037a40ba0806ecef0cbc5b352812d` |
| `verify_stage0c_canonical_fixture.py` | `90bd257794ee9bbcd7d06e28223713bf019aa42781c989d699774f92df8320cc` |
| `STAGE0C_CANONICAL_FIXTURE_RECEIPT.json` | `a24f4885af86a03fd2b9481e02e5872eae57a04be97b4d46d354eb843307c172` |
| `stage0c_canonical_replay_pilot.py` | `13d25dd12dbfb34b88a30b67f15a04cd36c8c9ac2eee9731a8c81d665aec24e0` |
