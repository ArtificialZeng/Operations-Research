# Stage-0b Mechanism Follow-Up Result — Isolating the Stage-0 `95 -> 2` `G_compact` Effect

**Status:** **COMPLETE & SEALED** (Exploratory mechanism follow-up on 24 outcome-independent Stage-0 pilot items; sealed `N = 416` blind test `bfcl_future_blind_test_ids_sealed.json` *(omitted from public archive; SHA-256 `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a`)* remains **100% untouched**).  
**Locked Protocol:** [`STAGE0B_AMENDMENT_PROTOCOL.md`](../protocols/STAGE0B_AMENDMENT_PROTOCOL.md) (`41291369ff4aec5d9d4ebbb7697c9aec5d69be6bf26b94b31bfce09aefa41732`)  
**Execution Receipt:** Real OS `PID = 62508`, wall time `460.0 s` (`RTX 5060 Laptop GPU`, `bfloat16`, `HF_HUB_OFFLINE=1`, `local_files_only=True`), verified local snapshot `Qwen/Qwen2.5-1.5B-Instruct` (`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, Apache-2.0), `xgrammar 0.2.9` (Apache-2.0), `max_algebra_identity_abs_err = 2.07e-13 < 1e-11`.  
**Integrity Gate:** All 10 sealed Stage-0 and blind-test SHA-256 hashes verified **byte-identical before and after execution** ([`stage0b_summary.json`](../outputs/stage0b/stage0b_summary.json)).

---

## 1. Executive Mechanism Verdict

The Stage-0 `95 -> 2` (`23/24 -> 0/24` on this outcome-independent 24-item subset) accuracy collapse of `G_compact` is **NOT** merely an artifact of having a spaced JSON example in the Stage-0 prompt — **it persists identically (`23/24 -> 0/24`) under a completely format-neutral prompt (`Prompt_Neutral`)** that describes keys in prose with zero JSON formatting examples.

However, the collapse **vanishes completely under BOTH targeted controls**:
1. **Prompt-to-grammar serialization match (`Prompt_Compact`):** Providing a compact JSON example shifts Qwen2.5's step-2 token from `":` (`prob ≈ 0.998`) to the single fused token `":"` (`prob ≈ 0.993–0.996`) on `24/24` items, completely bypassing the BPE opening-quote trap and restoring `G_compact` to **`23/24` AST accuracy (`0` flips vs. `G_optws = 23/24`)**.
2. **Equal per-item offered-menu enum (`Prompt_Neutral + MenuEnum`):** Constraining `"name"` to the identical canonical sorted union of offered functions from `item["function"]` (zero gold leakage; whitespace-only difference) eliminates all `24/24` unknown-function hallucinations (`in_menu: 0/24 -> 24/24`) and restores `G_compact_menu` to **`22/24` AST accuracy** (`12/12` on `multiple`, `10/12` on `simple_python`; `1` argument-value flip on `simple_python_202` relative to `G_optws_menu = 23/24`).

**Critical Counterevidence on Confidence Transfer (`Prompt_Neutral + MenuEnum`):**
- On **free generation across ALL 24 pairs** (where `G_optws_menu` emits pretty-printed spaced JSON and `G_compact_menu` emits compact JSON), **removing the grammar mask (`raw_pre_gnll_smt_mean`) performs WORSE (`C->W = 24/24 = 100.0%`, `W->C = 16/24 = 66.7%`) than keeping the mask (`raw_post_gnll_smt_mean`: `C->W = 19/24 = 79.2%`, `W->C = 17/24 = 70.8%`)**.
- The large `62.5% / 100.0%` post-mask SMT-NLL coverage failure (and trivial `79.2% / 79.2%` pre-mask invariance) belong **STRICTLY to same-path fixed-path rescoring**, NOT to real free-generation cross-grammar transfer. Removing the mask fails on free generation because `5/24` compact paths still cross a forced `"`-prefixed BPE token boundary inside the function-name SMT span (`pre_nll ~ 24` nats vs. `0.005` nats on spaced paths).

---

## 2. Matched vs. Confounded Prompt-Cell Matrix (All 24, Split Simple 12 vs. Multiple 12)

Every cell achieves `24/24` JSON valid and `24/24` envelope-schema valid (`0` `parse_or_envelope_fail`, `0` `offered_but_wrong_func`). `Prompt_Spaced` arms are reused **byte-for-byte** from sealed Stage-0 ([`stage0_pilot_per_instance.jsonl`](../outputs/stage0/stage0_pilot_per_instance.jsonl)).

| Arm | Cell Alignment | In Menu (`/24`) | AST Correct (`/24`) | Simple (`/12`, menu=1) | Multiple (`/12`, menu=2–3) | Unknown Func (Not in Menu) | Offered Wrong Func | Right Func Wrong Args |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| `spaced__unconstrained_reused` | Baseline (spaced example, no grammar) | `24/24` | `23/24` | `11/12` | `12/12` | `0` | `0` | `1` |
| `spaced__G_optws_reused` | **MATCHED** (spaced + optws) | `24/24` | `23/24` | `11/12` | `12/12` | `0` | `0` | `1` |
| `spaced__G_compact_reused` | **CONFOUNDED** (spaced + compact) | `0/24` | `0/24` | `0/12` | `0/12` | `24` | `0` | `0` |
| `neutral__G_optws` | **FORMAT-NEUTRAL** (prose + optws) | `24/24` | `23/24` | `11/12` | `12/12` | `0` | `0` | `1` |
| `neutral__G_compact` | **FORMAT-NEUTRAL** (prose + compact) | `0/24` | `0/24` | `0/12` | `0/12` | `24` | `0` | `0` |
| `compact__G_optws` | **SUPERSET-COMPATIBLE** (compact + optws) | `24/24` | `23/24` | `11/12` | `12/12` | `0` | `0` | `1` |
| `compact__G_compact` | **MATCHED** (compact + compact) | `24/24` | `23/24` | `11/12` | `12/12` | `0` | `0` | `1` |
| `neutral_menu__G_optws_menu` | **NEUTRAL + MENU-ENUM** (optws) | `24/24` | `23/24` | `11/12` | `12/12` | `0` | `0` | `1` |
| `neutral_menu__G_compact_menu` | **NEUTRAL + MENU-ENUM** (compact) | `24/24` | `22/24` | `10/12` | `12/12` | `0` | `0` | `2` |

*Exact failure cases outside `unknown_func_not_in_menu`:*
- `simple_python_334` (`blackjack.check_winner`, `value_error:others`): shared `right_func_wrong_args` error across ALL non-collapsed arms.
- `simple_python_202` (`calculate_emission_savings`, `value_error:string`): single flip in `neutral_menu__G_compact_menu` (`"energy_type": "renewable energy sources"` vs. `"renewable"` in `neutral_menu__G_optws_menu`).

---

## 3. Prefix-Logit Timing & First Tool-Name Token Inspection

From [`stage0b_prefix_logit_inspection.json`](../outputs/stage0b/stage0b_prefix_logit_inspection.json) (mean per-item menu-enum pair compilation time `7.20 ms`, max `7.98 ms`; all `6/6` read-only `Prompt_Spaced` 8-step probes matched sealed Stage-0 prefixes byte-for-byte):

| Arm | Median 1st Tool-Name Step | Preceding Token Counts (All 24) | Median Allowed Tokens | Median Retained Mass | Min Retained Mass | Top-1 Unmasked Allowed | Mean Fwd / Mask (`ms`) |
|---|---:|---|---:|---:|---:|---:|---:|
| `neutral__G_optws` | `6.0` | `' "'`: 24/24 | `147,137` | `1.000` | `1.000` | `100%` | `36.73 / 67.28` |
| `neutral__G_compact` | `3.0` | `'":'`: 24/24 | `269` | `5.93e-10` | `7.18e-11` | `0%` | `36.82 / 1.12` |
| `compact__G_optws` | `3.0` | `'":"'`: 24/24 | `147,137` | `1.000` | `1.000` | `100%` | `37.14 / 67.34` |
| `compact__G_compact` | `3.0` | `'":"'`: 24/24 | `147,062` | `1.000` | `1.000` | `100%` | `39.14 / 70.02` |
| `neutral_menu__G_optws_menu` | `6.0` | `' "'`: 24/24 | `5` | `0.9999` | `0.9148` | `100%` | `38.00 / 1.11` |
| `neutral_menu__G_compact_menu` | `4.0` | `'"'`: 19/24, `'":'`: 5/24 | `5` | `0.9999` | `1.30e-11` | `79%` | `36.82 / 1.10` |

**Exact token-level mechanism:**
- Under `Prompt_Neutral` (no example), Qwen2.5's default is pretty-printed JSON (`{\n  "name": "..."`). `G_compact` forces `{"` at step 0 (`mass ~ 0.006–0.026`), Qwen emits `name` then `":` (`prob ≈ 0.998`), and then puts `~1.000` probability mass on ` "` (space + opening quote) at step 3. `G_compact` masks ` "`, leaving only `269` `"`-prefixed BPE tokens (`mass ~ 10^-10`), injecting hallucinated prefixes (`"github`, `"title`, `"io`) on `24/24` items.
- Under `Prompt_Compact`, Qwen emits the fused token `":"` (`id = 3252`, `prob ≈ 0.993–0.996`) at step 2 on `24/24` items, bypassing the ` "` step completely (`147,062` allowed tokens, `mass = 1.000`).
- Under `Prompt_Neutral + G_compact_menu`, the menu grammar restricts step 3 after `":` to `"` (`19/24` items, e.g. `light_travel_time`) or exact `"`-prefixed menu prefixes (`5/24` items, e.g. `"time` on `multiple_189`, `mass = 4.73e-11`). On those `5/24` items, the forced `"`-prefixed token overlaps the Ye26 function-name SMT span, explaining why `raw_pre_gnll_smt_mean` spikes to `0.498` while `raw_post_gnll_smt_mean` stays near `0.007`.

---

## 4. Free-Generation vs. Fixed-Path Confidence Transfer (Strictly Separated)

> [!WARNING]
> **Small-Minority Instability Guardrail:** Every arm has `minority_class_count <= 2` (`0`, `1`, or `2` errors/positives out of 24). Conditional ranking metrics (`AUROC`, `AURC`, `risk@80%`) are explicitly flagged `conditional_metrics_unstable = True` and MUST NOT be interpreted as ranking or risk improvements.

### A. Free-Generation Pairwise Transfer (`free_generation_all_24`, ALL 24 freely generated pairs, target coverage `80%`)

| Condition | Parsed Equal (`C==W`) | Metric | Mean `C` | Mean `W` | Spearman $\rho$ | Transfer Cov `C -> W` | Transfer Cov `W -> C` |
|---|---:|---|---:|---:|---:|---:|---:|
| `Prompt_Spaced` (reused) | `0/24` | `post_gnll_smt_mean` | `0.5285` | `0.0018` | `-0.316` | `100.0%` (`24/24`) | `0.0%` (`0/24`) |
| `Prompt_Neutral` | `0/24` | `post_gnll_smt_mean` | `0.4628` | `0.0050` | `-0.183` | `100.0%` (`24/24`) | `0.0%` (`0/24`) |
| `Prompt_Compact` | `24/24` | `post_gnll_smt_mean` | `0.0016` | `0.0024` | `+0.780` | `70.8%` (`17/24`) | `83.3%` (`20/24`) |
| `Prompt_Compact` | `24/24` | `pre_gnll_smt_mean` | `0.0024` | `0.0024` | `+1.000` | `79.2%` (`19/24`) | `79.2%` (`19/24`) |
| **`Prompt_Neutral + MenuEnum`** | **`21/24`** | **`post_gnll_smt_mean` (raw post)** | **`0.0072`** | **`0.0047`** | **`+0.874`** | **`79.2%` (`19/24`)** | **`70.8%` (`17/24`)** |
| **`Prompt_Neutral + MenuEnum`** | **`21/24`** | **`pre_gnll_smt_mean` (raw pre)** | **`0.4976`** | **`0.0050`** | **`+0.520`** | **`100.0%` (`24/24`)** | **`66.7%` (`16/24`)** |
| `Prompt_Neutral + MenuEnum` | `21/24` | `post_nll_all_mean` | `0.0187` | `0.0043` | `+0.534` | `100.0%` (`24/24`) | `25.0%` (`6/24`) |

### B. Fixed-Path Same-Path Shared-Forward Rescoring (`fixed_path_paired_shared_forward_SEPARATE`, `24/24` compact paths scored under both grammars)

*(Do NOT conflate these same-path rescoring numbers with free-generation cross-grammar transfer above.)*

| Condition | Metric | Mean `C` | Mean `W` | Spearman $\rho$ | Same-Path Cov `C -> W` | Same-Path Cov `W -> C` |
|---|---|---:|---:|---:|---:|---:|
| `Prompt_Spaced` (reused) | `post_gnll_smt_mean` | `0.5300` | `3.4114` | `+0.730` | `0.0%` (`0/24`) | `100.0%` (`24/24`) |
| `Prompt_Neutral` | `post_gnll_smt_mean` | `0.4611` | `3.2246` | `+0.824` | `0.0%` (`0/24`) | `100.0%` (`24/24`) |
| `Prompt_Compact` | `post_gnll_smt_mean` | `0.0015` | `0.0022` | `+0.780` | `70.8%` (`17/24`) | `83.3%` (`20/24`) |
| `Prompt_Neutral + MenuEnum` | `post_gnll_smt_mean` | `0.0069` | `0.3779` | `+0.815` | `62.5%` (`15/24`) | `100.0%` (`24/24`) |
| `Prompt_Neutral + MenuEnum` | `pre_gnll_smt_mean` | `0.4980` | `0.4980` | `+1.000` | `79.2%` (`19/24`) | `79.2%` (`19/24`) |

---

## 5. Sealed Stage-0b File Manifest

| File | SHA-256 |
|---|---|
| [`select_stage0b_subset_and_verify.py`](../code/select_stage0b_subset_and_verify.py) | `0a0d9b95cedc580b8fdff00ac44277b6e0409c411dcc0dc4138a1fed168defa1` |
| [`STAGE0B_SUBSET_24_RECEIPT.json`](../receipts/STAGE0B_SUBSET_24_RECEIPT.json) | `65bcba4a28ee39bf3ff7f4173e773c110c076a136f663cda7dcde57f928cbf46` |
| [`STAGE0B_FIXTURE_RECEIPT.json`](../receipts/STAGE0B_FIXTURE_RECEIPT.json) | `04ee945695311cc738406e5a769556b14ed0bbc7e8212b85ac86cdc36d456d65` |
| [`STAGE0B_AMENDMENT_PROTOCOL.md`](../protocols/STAGE0B_AMENDMENT_PROTOCOL.md) | `41291369ff4aec5d9d4ebbb7697c9aec5d69be6bf26b94b31bfce09aefa41732` |
| [`stage0b_mechanism_followup.py`](../code/stage0b_mechanism_followup.py) | `9c866ba0f08080f57556ec92dc8fc0af6274a814a2a93ded2e55bfc3d57cbb1a` |
| [`stage0b_outputs/stage0b_per_instance.jsonl`](../outputs/stage0b/stage0b_per_instance.jsonl) | `724e921058677ee9b32d5a2e1fc74083af9d6dd29717c32bd6a9bc33ce489c9e` |
| [`stage0b_outputs/stage0b_prefix_logit_inspection.json`](../outputs/stage0b/stage0b_prefix_logit_inspection.json) | `78b826ecf3134f76246296b4c8043ecab5c813776281b778cd52b26cf58ce861` |
| [`stage0b_outputs/stage0b_summary.json`](../outputs/stage0b/stage0b_summary.json) | `9036772bb510bac388dc123dadaef89a1cf037a40ba0806ecef0cbc5b352812d` |
