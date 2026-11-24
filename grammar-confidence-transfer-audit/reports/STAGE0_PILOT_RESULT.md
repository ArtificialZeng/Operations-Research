# Stage-0 Bounded Pilot Report: Offline Single-Turn Function-Call Confidence Transfer Across Syntax-Only JSON Grammars (`grammar_confidence_transfer_20261124`)

**Status:** COMPLETE & SEALED (`PID = 42516`, `NVIDIA GeForce RTX 5060 Laptop GPU`, `torch 2.11.0+cu128` `bfloat16`, `xgrammar 0.2.9` Apache-2.0, `transformers 5.24.0` Apache-2.0, wall time `1,019.6 s`, `max_algebra_identity_abs_err = 2.21e-13`).  
**Locked Pre-Launch Protocol:** [`STAGE0_PROTOCOL.md`](../protocols/STAGE0_PROTOCOL.md) (`SHA-256: 9c4573d8...`).  
**Model & Provenance Receipt:** [`MODEL_TRANSPORT_RECEIPT.json`](../receipts/MODEL_TRANSPORT_RECEIPT.json) (`74cdd02f...`) — `Qwen/Qwen2.5-1.5B-Instruct` (**Apache-2.0**), official commit **`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`**, `model.safetensors` verified via native resumable `curl.exe -fL -C -` (`3,087,467,144 B`, exact `X-Linked-ETag` SHA-256 `dd924a11b4c220f385b51ffa522daea7c9f3d850e31b162bb5661df483c6d3ee`), loaded strictly offline (`HF_HUB_OFFLINE=1`; note `model.config._commit_hash` reports `"unknown"` in offline mode while the verified snapshot commit is sealed in `MODEL_TRANSPORT_RECEIPT.json`).  
**Dataset & Blind-Split Isolation:** [`BFCL_PILOT_SPLIT_RECEIPT.json`](../receipts/BFCL_PILOT_SPLIT_RECEIPT.json) (`3d6e0be0...`) — official BFCL v4 (`ShishirPatil/gorilla`, commit `6ea57973c7a6097fd7c5915698c54c17c5b1b6c8`, Apache-2.0), neutral read-only pilot **`N = 100`** (`60` `simple_python` + `40` `multiple`, `70` tool-family clusters, `113` domain roots). The **`N = 416`** future blind test (`74` disjoint clusters) remains **100% untouched**.

---

## 1. Executive Summary & Honest Power / Confound Assessment

1. **Exact Algebra Verified Across All 100 Pilot Instances:** `pre-NLL = post-NLL - log(retained_mass)` held to `<= 2.21e-13` across every generated and teacher-forced token step (`100/100` `G_compact` paths accepted and terminated by both `G_compact` and `G_optws` under one shared unmasked forward pass). *(Not claimed as novelty — algebraic verification only.)*
2. **Severe Syntax-Only Constraint Collapse Under `G_compact` (BPE Boundary Pathology + Prompt-Spacing Confound):**
   - While **all three arms achieved `100/100` JSON validity and `100/100` root-envelope validity (`{"name": <str>, "arguments": <obj>}` ONLY — NOT full tool parameter schemas)**, offered-menu tool-name presence was **`100/100`** (`Unconstrained`, `G_optws`) vs. **`2/100`** (`G_compact`), and official BFCL inert AST semantic correctness was **`95/100`** under both `Unconstrained` (`58/60` simple, `37/40` multiple) and `G_optws` (`95/100`, `0` accuracy flips vs. unconstrained), versus **`2/100`** under `G_compact` (`1/60` simple, `1/40` multiple; `93` flips `W_ok -> C_err`, `0` flips `C_ok -> W_err`; `98/100` failures are `simple_function_checker:wrong_func_name`).
   - **Exact BPE Token-Boundary Mechanism Verified:** Both the neutral prompt (`{"name": ..., "arguments": {...}}`) and Qwen2.5's pretraining distribution strongly favor `": "` after `"name"`. When `G_compact` masks `": "`, step 2 restricts the model to `8` tokens and selects `":` (`id=788`), forcing step 3 onto only the **`269` `"`-prefixed BPE tokens** (`min_retained_mass ~ 1e-11` to `1e-13`), which injects spurious prefixes into function names (e.g., `use_get_event_date`, `ioe.european_history.battle_details`, `IronSource`, `io.earth.functions.timezone.convert`). This reproduces and sharpens the valid-but-wrong / prompt–grammar mismatch failure documented by `macamiri/validbutwrong` and Reddy et al. (`2603.03305`), and **confounds** free-generation comparison between `G_compact` and `G_optws`.
3. **Massive Fixed-Path Scale, Rank-Correlation & Threshold-Transfer Failure — Including Mandatory Comparator Ye et al. (TMLR 2026) `G-NLL_SMT`:**
   - Even on the **exact same `100/100` fixed compact token paths** scored from **one shared unmasked forward pass** (identical tokens, identical AST correctness label):
     - **`post_nll_all_mean`:** `G_compact` mean = **`0.2696`** vs. `G_optws` = **`2.5797`** (unmasked `2.5908`, **`9.6×` overconfident** under `G_compact`); Spearman $\rho = +0.743$, Kendall $\tau = +0.543$; 80%-coverage threshold transfer collapses completely (**`C -> W`: `0.0%` coverage; `W -> C`: `100.0%` coverage**).
     - **Ye et al. (TMLR 2026) `G-NLL_SMT` (`post_gnll_smt_mean`):** Does **not** eliminate syntax-grammar distortion! Because the `"`-prefixed BPE boundary token overlaps the function-name SMT span, `G_compact` drops mean `post_gnll_smt_mean` **`6.6×`** (`0.5111` vs. `3.3861` under `G_optws` / `3.3864` unmasked), lowers Spearman $\rho$ from `1.000` (unmasked) to **`+0.778`** (Kendall $\tau = +0.595$), and breaks threshold transfer (**`C -> W`: `0.0%` coverage; `W -> C`: `100.0%` coverage**). Identical transfer failure holds for `post_gnll_smt_sum` (`4.715` vs. `28.189`, $\rho = +0.862$) and value-only `post_gnll_smt_val_mean` (`0.586` vs. `4.007`, $\rho = +0.736$).
     - **Unmasked `pre_nll` / `pre_gnll_smt_mean`:** By contrast, scoring on the unmasked logits from the same forward pass is **100% invariant** across grammars on fixed paths ($\rho = 1.000$, `80.0%` transfer coverage both ways).
4. **Pilot Statistical Power Verdict (UNDERPOWERED FOR RANKING / AUROC):**
   - **This Stage-0 pilot is severely underpowered for within-arm ranking (`AUROC`) comparisons:** `G_optws`/`Unconstrained` produced only **`5` errors** (`95` correct), while `G_compact` produced only **`2` correct** (`98` errors; approximate unpaired AUROC SE `= 0.207`, cluster-bootstrap 95% CIs on `ΔAUROC` span up to `±0.50`).
   - **Implication Before Any Blind Held-Out Run:** While the threshold-transfer collapse (`0%` / `100%` coverage failure) and BPE boundary leakage into `G-NLL_SMT` are unmistakable even at `N = 100`, **we should NOT proceed straight to the blind held-out split with the current spaced-prompt vs. `G_compact` pair alone**, because `G_compact`'s `95% -> 2%` accuracy collapse confounds confidence-ordering transfer with severe prompt–grammar incompatibility. A clean follow-up design (upon coordinator review) should test **format-compatible / balanced-accuracy syntax pairs** (e.g., `G_optws` vs. `G_canonical_spaced` vs. `G_pretty_multiline`, or format-neutral prompts without inline JSON whitespace hints, plus a second open model with a higher natural BFCL error rate so both grammars have adequate error counts for powered AUROC/AURC comparisons).

---

## 2. All-Generated-Cases Results (`N = 100`, Zero Cherry-Picking)

| Arm | JSON / Root-Envelope Valid *(NOT tool schema)* | BFCL Inert AST Correct (`Simple` / `Mult`) | Score Metric | Mean (SD) | AUROC *(underpowered)* | AURC | Risk@80% Cov | $\tau_{80}$ |
|---|---:|---:|---|---:|---:|---:|---:|---:|
| **`Unconstrained`** | `100 / 100` | **`95 / 100`** (`58/60`, `37/40`) | `pre_nll_all_mean` | `0.0075` (`0.0091`) | `0.7432` | `0.0195` | `0.0250` | `0.01392` |
| **`Unconstrained`** | `100 / 100` | `95 / 100` | **`pre_gnll_smt_mean`** *(Ye26)* | `0.0059` (`0.0133`) | `0.8758` | `0.0085` | `0.0250` | `0.00612` |
| **`Unconstrained`** | `100 / 100` | `95 / 100` | `pre_gnll_smt_sum` *(Ye26)* | `0.0856` (`0.1840`) | `0.8989` | `0.0071` | `0.0250` | `0.09889` |
| **`G_optws`** | `100 / 100` | **`95 / 100`** (`58/60`, `37/40`) | `post_nll_all_mean` | `0.0075` (`0.0091`) | `0.7432` | `0.0195` | `0.0250` | `0.01392` |
| **`G_optws`** | `100 / 100` | `95 / 100` | **`post_gnll_smt_mean`** *(Ye26)* | `0.0059` (`0.0133`) | `0.8758` | `0.0085` | `0.0250` | `0.00612` |
| **`G_optws`** | `100 / 100` | `95 / 100` | `neg_logz_all_mean` *(FeasMass)* | `0.0000` (`0.0000`) | `0.8505` | `0.0098` | `0.0250` | `0.00000` |
| **`G_optws`** | `100 / 100` | `95 / 100` | `h_post_first` *(Parvatikar26)* | `0.0596` (`0.0553`) | `0.7011` | `0.0400` | `0.0125` | `0.09086` |
| **`G_compact`** | `100 / 100` | **`2 / 100`** (`1/60`, `1/40`) | `pre_nll_all_mean` | `2.5887` (`1.1081`) | `0.8980` | `0.9495` | `0.9750` | `3.35451` |
| **`G_compact`** | `100 / 100` | `2 / 100` | `post_nll_all_mean` | `0.2679` (`0.1431`) | `1.0000` | `0.9063` | `0.9750` | `0.39982` |
| **`G_compact`** | `100 / 100` | `2 / 100` | **`post_gnll_smt_mean`** *(Ye26)* | `0.5096` (`0.4476`) | `0.9949` | `0.9113` | `0.9750` | `0.70422` |
| **`G_compact`** | `100 / 100` | `2 / 100` | `neg_logz_all_mean` *(FeasMass)* | `2.3208` (`1.0134`) | `0.8112` | `0.9634` | `0.9750` | `2.88017` |
| **`G_compact`** | `100 / 100` | `2 / 100` | `h_post_first` *(Parvatikar26)* | `0.0011` (`0.0009`) | `0.4490` | `0.9857` | `0.9750` | `0.00173` |

- **All-Generated Cross-Grammar Transfer (`N = 100`, `70`-Cluster Bootstrap):**
  - `post_gnll_smt_mean`: `G_compact -> G_optws` transfers `tau_C = 0.7042` -> **`100.0%` coverage** `[100.0, 100.0]`, risk `5.00%` (vs. `2.50%` in-grammar risk@80%); `G_optws -> G_compact` transfers `tau_W = 0.0061` -> **`0.0%` coverage** `[0.0, 0.0]` (`rho = -0.189`, `tau = -0.131`).
  - `h_post_first` reverses direction: `G_optws -> G_compact` (`tau_W = 0.0909`) accepts **`100.0%` of `G_compact` calls at `98.0%` error risk** (`G_compact -> G_optws` accepts `0.0%`).

---

## 3. Fixed-Path Paired Scoring (Same Unmasked Forward Pass, `n = 100/100` Accepted by Both Grammars)

| Score Metric | `G_compact` Mean | `G_optws` Mean | Spearman $\rho$ / Kendall $\tau$ (`C` vs `W`) | AUROC (`C` vs `W`) [Cluster 95% $\Delta$CI] | `C -> W` Realized Cov (Target 80%) | `W -> C` Realized Cov (Target 80%) |
|---|---:|---:|---|---:|---:|---:|
| `pre_nll_all_mean` *(Unmasked)* | `2.5908` | `2.5908` | `+1.000` / `+1.000` | `0.898` vs `0.898` `[+0.000, +0.000]` | `80.0%` | `80.0%` |
| `pre_gnll_smt_mean` *(Unmasked Ye26)* | `3.3864` | `3.3864` | `+1.000` / `+1.000` | `0.776` vs `0.776` `[+0.000, +0.000]` | `80.0%` | `80.0%` |
| **`post_nll_all_mean`** | **`0.2696`** | **`2.5797`** | **`+0.743` / `+0.543`** | `1.000` vs `0.898` `[+0.009, +0.235]` | **`0.0%`** | **`100.0%`** |
| **`post_gnll_smt_mean`** *(Ye26)* | **`0.5111`** | **`3.3861`** | **`+0.778` / `+0.595`** | `0.995` vs `0.776` `[+0.017, +0.483]` | **`0.0%`** | **`100.0%`** |
| **`post_gnll_smt_sum`** *(Ye26)* | **`4.7151`** | **`28.1891`** | **`+0.862` / `+0.698`** | `0.990` vs `1.000` `[-0.043, +0.000]` | **`0.0%`** | **`100.0%`** |
| `post_gnll_smt_val_mean` *(Val-only)* | `0.5861` | `4.0065` | `+0.736` / `+0.554` | `0.995` vs `0.740` `[+0.017, +0.549]` | **`0.0%`** | **`100.0%`** |
| `post_nll_syntax_mean` | `0.1115` | `2.4672` | `+0.571` / `+0.396` | `1.000` vs `0.929` `[+0.024, +0.130]` | **`0.0%`** | **`100.0%`** |
| `neg_logz_all_mean` *(FeasMass)* | `2.3212` | `0.0111` | `+0.482` / `+0.322` | `0.811` vs `0.597` `[-0.090, +0.500]` | `100.0%` | `0.0%` |
| `neg_logz_smt_mean` | `2.8754` | `0.0004` | `+0.242` / `+0.165` | `0.724` vs `0.990` `[-0.551, -0.023]` | `100.0%` | `0.0%` |
| `h_post_first` *(Parvatikar26)* | `0.0011` | `0.0587` | `+0.257` / `+0.191` | `0.513` vs `0.515` `[-0.182, +0.160]` | `0.0%` | `100.0%` |

---

## 4. Sealed Stage-0 SHA-256 Artifact Manifest

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| [`build_bfcl_pilot_split.py`](../code/build_bfcl_pilot_split.py) | 11,360 | `24256c697b7ad68c777aeb82a2ad39039367432198e0c793957f908546877f90` |
| [`BFCL_PILOT_SPLIT_RECEIPT.json`](../receipts/BFCL_PILOT_SPLIT_RECEIPT.json) | 12,185 | `3d6e0be091e3f6a85c7985dcb29b364268df1e6d039f86895daf309e13943f57` |
| [`bfcl_stage0_pilot_dataset.json`](../data/bfcl_stage0_pilot_dataset.json) | 209,128 | `191e8e8c8c9c00f0f7dacd0a98b6f592b02e878e444da0016e99f1e31c1cd446` |
| `bfcl_future_blind_test_ids_sealed.json` *(omitted from public archive; SHA-256 `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a`)* | 10,249 | `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a` |
| [`grammar_utils.py`](../code/grammar_utils.py) | 18,204 | `d063e5e347bf2928f1c6f22becafd67611f711842960276e1399359dab966423` |
| [`verify_grammar_mask_algebra.py`](../code/verify_grammar_mask_algebra.py) | 10,899 | `e48745d4b7217ca3bce3d209d14d79bea15e1ae08a102dbc0d92d921baea0dd8` |
| [`STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json`](../receipts/STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json) | 1,981 | `e4945f6a42bc2959783506f908e32bdb4d6e66b827b8c507459ab84d60ca34ef` |
| [`STAGE0_PROTOCOL.md`](../protocols/STAGE0_PROTOCOL.md) | 8,266 | `9c4573d847d18a683c22440390d6e9b11d44691d45321e6ede5217894ec065b6` |
| [`MODEL_TRANSPORT_RECEIPT.json`](../receipts/MODEL_TRANSPORT_RECEIPT.json) | 924 | `74cdd02fae04f8328eef6a323f3e80e2f02d52a2b0f8d200c2674b629071c8ad` |
| [`stage0_grammar_confidence_pilot.py`](../code/stage0_grammar_confidence_pilot.py) | 33,153 | `4f366ffb06617f2fcb2f36661c6c9b503096a47dd709450603faf095da9a7cb9` |
| [`stage0_pilot_outputs/stage0_pilot_per_instance.jsonl`](../outputs/stage0/stage0_pilot_per_instance.jsonl) | 741,678 | `06c90359910592d3d43916c50479abadc15a5cac2d9600ada8b2b0e2566b6aa8` |
| [`stage0_pilot_outputs/stage0_pilot_summary.json`](../outputs/stage0/stage0_pilot_summary.json) | 88,134 | `a39963f0cf7d00a1ef4c2c0864708883a7f01072e364580c6e7fd3d4e7b8af6c` |
