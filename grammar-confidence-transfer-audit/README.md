# Exploratory Negative Research Archive: Offline Tool-Call Grammar & Confidence Transfer Audit

**Status:** **FROZEN — EXPLORATORY NEGATIVE RESEARCH ARCHIVE (2026-11-24)**  
**Scope:** Single-model (`Qwen/Qwen2.5-1.5B-Instruct`, Apache-2.0, commit `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`), single-turn, offline read-only BFCL v4 dev subset (`N = 100` Stage-0; `N = 24 = 12 Simple + 12 Multiple` Stage-0b & Stage-0c) under `xgrammar 0.2.9` (Apache-2.0).  
**Blind Split Protection:** The disjoint `N = 416` future blind test (`74` disjoint tool-family clusters) was **never opened, decoded, or scored** and its IDs are **omitted** from this archive (sealed local file SHA-256: `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a`). No second model was run.

---

## 1. Executive Summary & Why This Study Is Frozen

This archive preserves a bounded three-stage exploratory investigation (Stages `0`, `0b`, `0c`) into whether syntax-only JSON grammar constraints (`G_compact` vs. `G_optws`) distort function-call confidence ordering or cross-grammar abstention threshold transfer, and whether canonical teacher-forced replay repairs transfer. **The prospectively locked Stage-0c Leave-One-Tool-Family-Out (LOFO) gate failed; the line is frozen as an exploratory negative research archive.**

### Narrow Robust Implementation Fact Retained
- In this one-model BFCL v4 dev pilot (`Qwen/Qwen2.5-1.5B-Instruct`, `xgrammar 0.2.9`), enforcing a **strict compact no-whitespace JSON grammar (`G_compact`)** with either a **spaced JSON exemplar** (Stage-0) or a **format-neutral prose prompt** (Stage-0b) and **unrestricted function-name strings** caused severe accuracy collapse:
  - **Stage-0 (`N = 100`, spaced exemplar):** `G_compact = 2/100` offered-name in menu & `2/100` inert BFCL AST correct (`98` errors all emitted a function name absent from the offered menu) vs. `95/100` AST correct (`100/100` offered-name in menu) for both `G_optws` and `Unconstrained`.
  - **Important schema clarification:** `call_schema_valid` (`100/100` across all arms) checks **ONLY** the root envelope `{"name": <str>, "arguments": <object>}` — it does **NOT** check full per-tool parameter schemas.
  - **Stage-0b Mechanism Controls (`N = 24 = 12 Simple + 12 Multiple`, outcome-independent SHA-256 subset):**
    - Under `Prompt_Neutral` (prose-only key description, zero JSON example), the collapse persisted identically: `G_optws = 23/24` vs. `G_compact = 0/24` (`24/24` unknown function names not in menu), driven by step-3 masking of ` "` after `":` onto `269` `"`-prefixed BPE tokens (`median retained_mass = 5.93e-10`).
    - **Matching a compact exemplar (`Prompt_Compact`)** shifted step 2 to fused token `":"` on `24/24` items and **fully restored accuracy (`23/24` vs. `23/24`, `0` flips)**.
    - **Adding an equal canonical offered-tool-name enum under `Prompt_Neutral` (`G_optws_menu` vs. `G_compact_menu`, zero gold leakage, whitespace-only difference)** eliminated all non-menu hallucinations and **largely restored accuracy (`22/24` vs. `23/24`; `12/12` on `multiple`, `10/12` on `simple_python`)**.

### Free-Generation Transfer vs. Same-Path Rescoring (Strictly Separated)
- **High-accuracy free-generation transfer (`Prompt_Neutral + MenuEnum`, `N = 24`, target coverage `80%`):**
  - Raw post-mask Ye26 semantic-token NLL (`raw_post_gnll_smt_mean`): **`C -> W = 19/24 (79.2%)`**, **`W -> C = 17/24 (70.8%)`** (LOFO worst-dir `|cov - 0.80| = 9.17 pp`, mean `= 5.00 pp`).
  - Removing the grammar mask (`raw_pre_gnll_smt_mean`): **`C -> W = 24/24 (100.0%)`**, **`W -> C = 16/24 (66.7%)`** full-sample (`87.5% / 62.5%` LOFO; worst-dir `17.50 pp`, mean `12.50 pp`) — **direct counterevidence** to naive mask removal on freely generated pairs because `5/24` compact paths still cross forced `"`-prefixed tokens overlapping the function-name SMT span.
- **Same-path fixed-path rescoring (separate — NOT free-generation transport):**
  - The `62.5% / 100.0%` post-mask SMT-NLL coverage shift in `Prompt_Neutral + MenuEnum` belongs **exclusively** to rescoring identical compact paths under both grammars.
  - On Stage-0's `100` common compact paths, post-mask `G-NLL_SMT` rank correlation is Spearman $\rho \approx 0.778$ with **only `2` correct items** (`98` errors), which does **not** establish a reliable risk discriminator.

### Stage-0c Canonical Replay Null (Failed Prospectively Locked LOFO Gate)
- On the `24` sealed `neutral_menu` free-generated pairs (`21/24` equal canonical strings deduplicated -> `27` unique unmasked teacher-forced forward passes, `PID = 11724`, [`outputs/stage0c/stage0c_summary.json`](./outputs/stage0c/stage0c_summary.json) `d47422dfdba372826c53097481032ba5b31a5c8df38e3a1038809649b8c4b797`), fixed typed JSON canonicalization (standard spaces, fixed root order `"name"` then `"arguments"`, recursively sorted argument keys, preserved types & list order) **failed** the prespecified `>= 8 pp` worst-direction coverage-improvement gate:
  - **Primary LOFO (`18` tool-family clusters):** `raw_post_gnll_smt_mean` worst-dir `0.091667` (`9.17 pp`), mean `0.0500` (`5.00 pp`) vs. `canon_gnll_smt_mean` worst-dir `0.133333` (`13.33 pp`), mean `0.133333` (`13.33 pp`) -> **`-4.17 pp` worse** worst-direction (`95%` cluster-bootstrap CI `[-14.55 pp, +25.00 pp]`), **`-8.33 pp` worse** mean.
  - **Companion whole-dev in-sample:** `canon_gnll_smt_mean` worst-dir `5.00 pp` vs. `raw_post` `9.17 pp` (`+4.167 pp < 8 pp` gate, while reusing calibration cases where `21/24` pairs serialize identically by construction).
  - **Operational harms:** Sorting argument keys alphabetically contradicts non-alphabetical schema parameter order on `12/24` items, causing `~100×` synthetic NLL inflation (`mean: 0.005 -> 0.556`), degrading in-grammar LOFO coverage (`16/24 = 66.7%` vs. `18/24 = 75.0%`), and adding `+92.4 ms` mean extra teacher-forced forward latency per single-arm production call (`mean prefill = 77.8 ms`).

---

## 2. Prior Art, Caveats, and Non-Claims

- **Low error counts:** High-accuracy arms contain only `1` error (`W` in Stage-0b/0c), `2` errors (`C` in Stage-0b/0c), or `5` errors (`W` in Stage-0 `N = 100`), while collapsed `G_compact` in Stage-0 has only `2` correct calls. **No claims of improved selective risk or reliable AUROC discrimination are made.**
- **No novelty claims & no claims about vLLM defaults:**
  - Whitespace/token-boundary quality degradation under compact JSON grammar constraints is a known implementation issue in **XGrammar / SGLang** constrained decoding (e.g., `any_whitespace` vs. `--constrained-json-disable-any-whitespace` and BPE boundary interactions). This study makes **no claims about vLLM defaults**.
  - Primary literature positioned and respected throughout: **Ye et al. (TMLR 2026, `arXiv:2604.22985v2`)** (`G-NLL_SMT` and AST-based structural clustering for function-calling UQ), **Kim & Kang (`arXiv:2605.27752`, *"Same Answer, Different Confidence: Protocol Sensitivity in LLM Confidence Calibration"*)**, **Parvatikar (UncertaiNLP 2026, `2026.uncertainlp-main.26`)**, **Reddy et al. (`arXiv:2603.03305`)**, **`macamiri/validbutwrong`**, and **multi-turn calibration (`arXiv:2609.00949`)**.
  - Identical-serialization score equality on deduplicated canonical pairs (`21/24`) is by construction and is not empirical novelty.

---

## 3. Pinned Sources, Models, and Licenses

| Dependency / Asset | Pinned Reference | License |
|---|---|---|
| Base LLM | `Qwen/Qwen2.5-1.5B-Instruct`, commit `989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, `model.safetensors` (`3,087,467,144 B`, SHA-256 `dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee`) | Apache-2.0 |
| Benchmark Dataset & Inert AST Checker | `ShishirPatil/gorilla` (BFCL v4), commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8` *(upstream checkout omitted; dev 100-item split included in `./data/bfcl_stage0_pilot_dataset.json`)* | Apache-2.0 |
| Grammar Engine | `xgrammar==0.2.9` | Apache-2.0 |
| Inference Stack | `transformers==5.24.0`, `tokenizers==0.23.3`, `torch==2.11.0+cu128` | Apache-2.0 / BSD-3-Clause |

---

## 4. Archive Map & Reproduction

- **Provenance & errata:** [`PROVENANCE_AND_INTERPRETATION.md`](./PROVENANCE_AND_INTERPRETATION.md)
- **Locked pre-launch protocols:** [`protocols/STAGE0_PROTOCOL.md`](./protocols/STAGE0_PROTOCOL.md), [`protocols/STAGE0B_AMENDMENT_PROTOCOL.md`](./protocols/STAGE0B_AMENDMENT_PROTOCOL.md), [`protocols/STAGE0C_CANONICAL_REPLAY_PROTOCOL.md`](./protocols/STAGE0C_CANONICAL_REPLAY_PROTOCOL.md)
- **Stage reports:** [`reports/STAGE0_PILOT_RESULT.md`](./reports/STAGE0_PILOT_RESULT.md), [`reports/STAGE0B_MECHANISM_RESULT.md`](./reports/STAGE0B_MECHANISM_RESULT.md), [`reports/STAGE0C_CANONICAL_REPLAY_RESULT.md`](./reports/STAGE0C_CANONICAL_REPLAY_RESULT.md)
- **Raw sealed outputs (byte-identical):** [`outputs/stage0/`](./outputs/stage0/), [`outputs/stage0b/`](./outputs/stage0b/), [`outputs/stage0c/`](./outputs/stage0c/)
- **Pre-launch receipts:** [`receipts/`](./receipts/)
- **Portable runnable scripts:** [`code/`](./code/)
- **Complete ordered SHA-256 manifest:** [`MANIFEST.json`](./MANIFEST.json)

### Offline Reproduction Notes
1. Install dependencies from [`requirements.txt`](./requirements.txt) in an isolated Python 3.11+ environment with CUDA PyTorch (`torch==2.11.0+cu128`).
2. Clone `ShishirPatil/gorilla` at commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8` into `<ARCHIVE_ROOT>/bfcl_upstream` (needed only if re-running inert BFCL AST evaluation or regenerating the dev split).
3. Cache `Qwen/Qwen2.5-1.5B-Instruct` at exact commit `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` (`model.safetensors` SHA-256 `dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee`), then set `HF_HUB_OFFLINE=1` and `TRANSFORMERS_OFFLINE=1`.
4. Note: Original scripts were executed with flat local root paths; [`MANIFEST.json`](./MANIFEST.json) records exact SHA-256 hashes of both the original local sealed scripts and the portable archive copies.
