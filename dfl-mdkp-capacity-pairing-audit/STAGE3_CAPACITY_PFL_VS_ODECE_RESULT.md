# Stage-3 Capacity Published-Comparison Bounded Intervention Report: `ODECE(alpha=0.5)` vs. Upstream `PFL/MSE` (`2 × 2` Train-Pairing × Test-Pairing Factorial, Published Seeds `11` & `15`)

**Status:** COMPLETE & SEALED (`PID = 26536`, `torch 2.15.0+cpu`, `HiGHS 1.16.0`, `float64`, wall time `182.1 s`, `75,600` CP-SAT calls + `10,000` HiGHS calls).
**Locked Pre-Launch Protocol:** [`STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md`](STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md) (`SHA-256: dca02adc...`).
**Pre-Launch Gates:** [`ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json`](ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json) (`direct_pytorch_gate_pass_float64 = true`) & [`STAGE3_SYNTHETIC_CHECK_RECEIPT.json`](STAGE3_SYNTHETIC_CHECK_RECEIPT.json) (`all_checks_passed = true`).
**Scope & Prior Integrity:** Published seed IDs **`11` and `15`** (diagnostic subset of `11–15`). Both the diagonal contrast and the off-diagonal cross-cells are strictly **controlled benchmark-integrity adaptations**, **never** reproduced NeurIPS Table 2 scores. All sealed Stage-0/1a/1b/2a/2b/2c/2d artifacts verified byte-identical (`ALL_SEALED_INTACT=True`).

---

## 1. Direct Answer: Does Complete Scenario-Row Alignment Change the Relative Method Comparison?

1. **Qualitative dominance is UNCHANGED (`8/8` seed×cell evaluations = `tradeoff_ODECE_lower_risk_higher_repair`):** Neither method dominates the other in joint risk + integer-repair loss in any cell on either seed. Under the raw policy (`0` negative-RHS skips across all 16 model×cell evaluations), `ODECE(alpha=0.5)` consistently achieves dramatically lower infeasibility than `PFL/MSE` (`1.0%–15.8%` vs. `45.6%–60.4%`), while `PFL/MSE` consistently achieves lower feasible-only regret (`14.07%–20.14%` vs. `25.06%–44.81%`) and lower all-instance strict 0–1 integer-repair loss `p=1` (`17.31%–27.04%` vs. `24.39%–44.61%`).
2. **Quantitative relative comparison IS MATERIALLY CHANGED — NOT merely a parallel shift of both methods' absolute numbers:**
   - Comparing the **literal released diagonal (`Train_Released__Test_Released`)** against the **fully aligned diagonal (`Train_Aligned__Test_Aligned`)**:
     - **Seed `11`:** `ODECE`'s all-instance integer-repair (`p=1`) gap vs. `PFL/MSE` is **cut by more than half**, from **`+19.042 pp`** to **`+9.104 pp`** (a **`-9.938 pp`** reduction in the relative method gap); feasible-only regret marginal gap shrinks by **`-12.263 pp`** (`+26.719 pp` -> `+14.456 pp`, paired `both_feasible` `+38.043 pp` -> `+23.218 pp`), while `ODECE`'s strict risk advantage narrows modestly from `-49.80 pp` (`1.0%` vs `50.8%`) to `-44.20 pp` (`2.4%` vs `46.6%`).
     - **Seed `15`:** `ODECE`'s integer-repair (`p=1`) gap vs. `PFL/MSE` is **also cut by more than half**, from **`+15.298 pp`** to **`+7.082 pp`** (a **`-8.216 pp`** reduction in the relative method gap); feasible-only regret marginal gap shrinks by **`-9.626 pp`** (`+20.617 pp` -> `+10.991 pp`, paired `both_feasible` `+31.332 pp` -> `+19.237 pp`), while `ODECE`'s strict risk advantage **widens** from `-50.80 pp` (`5.8%` vs `56.6%`) to `-54.60 pp` (`5.8%` vs `60.4%`).
   - **Asymmetric driver:** Under the 20-epoch author budget, `ODECE` gains **2.7×–2.8× larger integer-repair improvement** from complete alignment (`-15.457 pp` on seed `11`, `-13.172 pp` on seed `15`) than under-converged `PFL/MSE` (`-5.520 pp` on seed `11`, `-4.955 pp` on seed `15`). The literal released positional bug thus substantially inflates `ODECE`'s apparent regret/repair penalty against `PFL/MSE` (`~8.2–9.9 pp` on `int_p1`, `~9.6–12.3 pp` on feasible-only regret) without overturning the raw risk–repair tradeoff direction.
   - **Cross-cell mechanism check:** Evaluating `ODECE_Aligned` on misaligned positional test rows (`Train_Aligned__Test_Released`) spikes its infeasibility from `2.4% -> 14.0%` (`+11.6 pp`, seed `11`) and `5.8% -> 15.8%` (`+10.0 pp`, seed `15`), confirming `ODECE_Aligned` learned genuine context-dependent capacities tied to the aligned scenario rows rather than a static conservative shift.

---

## 2. Full `2 × 2` Factorial Results (Raw Policy, `HiGHS 1.16.0` `float64`, `n = 500` per Seed)

> **Solver-tolerance & negative-RHS note:** Every test oracle (`2,000/2,000`) and every test prediction solve (`8,000/8,000`) returned `kOptimal` within HiGHS's configured tolerance (`mip_rel_gap = 1e-4`; observed max gap `<= 9.99e-5`, max integrality error `<= 3.19e-11`). **Zero negative predicted RHS** (`n_neg_pred_rows = 0`, `n_neg_pred_dims = 0`, `pred_cap_min >= 1.25`) and **zero solver skips** occurred in any test evaluation, so `source_raw_infeas_denom = 500` in all 16 arms and the prediction-only `max(cap_hat, 0)` fallback was never triggered. All 95% CIs are 10,000-resample paired bootstrap intervals **conditional on each fitted seed pair**.

### 2.1 Arm-Level Metrics (`PFL/MSE` and `ODECE(alpha=0.5)`)

| Seed | Cell (`Train__Test`) | Method | Source Raw Infeas (`num/denom`) | Source Feas-Only Regret (`denom`) | Strict 0–1 Risk (`n=500`) | Skips / Neg RHS | All-Inst Int Repair `p=1` (%) | All-Inst Int `p=0.21` / Frac `p=1` (%) | Pred Min / Mean vs True Mean |
|---:|---|---|---:|---:|---:|---:|---:|---:|---|
| **11** | `Released__Released` *(diag)* | `PFL/MSE` | `50.80%` (`254/500`) | `17.449%` (`n=246`) | `50.80%` | `0 / 0` | `24.945` | `14.114` / `23.996` | `5.71` / `19.12` vs `19.62` |
| **11** | `Released__Released` *(diag)* | `ODECE(0.5)` | `1.00%` (`5/500`) | `44.168%` (`n=495`) | `1.00%` | `0 / 0` | `43.987` | `43.870` / `43.824` | `2.28` / `23.50` vs `19.62` |
| **11** | `Aligned__Aligned` *(diag)* | `PFL/MSE` | `46.60%` (`233/500`) | `14.234%` (`n=267`) | `46.60%` | `0 / 0` | `19.425` | `12.246` / `17.308` | `4.20` / `19.27` vs `19.64` |
| **11** | `Aligned__Aligned` *(diag)* | `ODECE(0.5)` | `2.40%` (`12/500`) | `28.690%` (`n=488`) | `2.40%` | `0 / 0` | `28.530` | `28.278` / `28.309` | `2.40` / `24.14` vs `19.64` |
| **11** | `Released__Aligned` *(cross)* | `PFL/MSE` | `45.60%` (`228/500`) | `15.413%` (`n=272`) | `45.60%` | `0 / 0` | `22.669` | `13.368` / `21.300` | `5.71` / `19.12` vs `19.64` |
| **11** | `Released__Aligned` *(cross)* | `ODECE(0.5)` | `1.20%` (`6/500`) | `44.807%` (`n=494`) | `1.20%` | `0 / 0` | `44.609` | `44.449` / `44.338` | `2.28` / `23.50` vs `19.64` |
| **11** | `Aligned__Released` *(cross)* | `PFL/MSE` | `51.40%` (`257/500`) | `20.143%` (`n=243`) | `51.40%` | `0 / 0` | `27.039` | `15.627` / `26.537` | `4.20` / `19.27` vs `19.62` |
| **11** | `Aligned__Released` *(cross)* | `ODECE(0.5)` | `14.00%` (`70/500`) | `31.254%` (`n=430`) | `14.00%` | `0 / 0` | `30.507` | `28.482` / `29.799` | `2.40` / `24.14` vs `19.62` |
| **15** | `Released__Released` *(diag)* | `PFL/MSE` | `56.60%` (`283/500`) | `17.481%` (`n=217`) | `56.60%` | `0 / 0` | `22.260` | `13.018` / `24.210` | `10.04` / `23.97` vs `24.13` |
| **15** | `Released__Released` *(diag)* | `ODECE(0.5)` | `5.80%` (`29/500`) | `38.098%` (`n=471`) | `5.80%` | `0 / 0` | `37.559` | `36.779` / `37.533` | `1.25` / `17.73` vs `24.13` |
| **15** | `Aligned__Aligned` *(diag)* | `PFL/MSE` | `60.40%` (`302/500`) | `14.069%` (`n=198`) | `60.40%` | `0 / 0` | `17.305` | `10.371` / `17.958` | `9.69` / `24.05` vs `24.04` |
| **15** | `Aligned__Aligned` *(diag)* | `ODECE(0.5)` | `5.80%` (`29/500`) | `25.059%` (`n=471`) | `5.80%` | `0 / 0` | `24.387` | `24.086` / `24.329` | `6.26` / `19.01` vs `24.04` |
| **15** | `Released__Aligned` *(cross)* | `PFL/MSE` | `60.20%` (`301/500`) | `14.246%` (`n=199`) | `60.20%` | `0 / 0` | `18.427` | `11.084` / `19.702` | `10.04` / `23.97` vs `24.04` |
| **15** | `Released__Aligned` *(cross)* | `ODECE(0.5)` | `1.60%` (`8/500`) | `36.979%` (`n=492`) | `1.60%` | `0 / 0` | `36.730` | `36.613` / `36.651` | `1.25` / `17.73` vs `24.04` |
| **15** | `Aligned__Released` *(cross)* | `PFL/MSE` | `59.20%` (`296/500`) | `18.247%` (`n=204`) | `59.20%` | `0 / 0` | `22.952` | `13.403` / `24.865` | `9.69` / `24.05` vs `24.13` |
| **15** | `Aligned__Released` *(cross)* | `ODECE(0.5)` | `15.80%` (`79/500`) | `28.386%` (`n=421`) | `15.80%` | `0 / 0` | `28.064` | `25.948` / `28.339` | `6.26` / `19.01` vs `24.13` |

### 2.2 Per-Seed Method Gaps (`ODECE(alpha=0.5) - PFL/MSE`) & Risk/Repair Dominance

| Seed | Cell (`Train__Test`) | Dominance | Strict Risk Gap (`pp`) [95% Cond. CI] (McNemar $p$) | Int Repair `p=1` Gap (`pp`) [95% Cond. CI] (Wilcoxon $p$) | Frac `p=1` Gap (`pp`) | Feas-Only Regret Gap: Marginal / Paired `both_feas` (`n`) |
|---:|---|---|---|---:|---:|---|
| **11** | `Released__Released` | Tradeoff (`O` safer, higher repair) | **`-49.80`** `[-54.20, -45.60]` (`2.21e-75`) | **`+19.042`** `[+16.487, +21.494]` (`7.89e-36`) | `+19.829` | `+26.719 pp` / `+38.043 pp` (`n=246`) |
| **11** | `Aligned__Aligned` | Tradeoff (`O` safer, higher repair) | **`-44.20`** `[-48.60, -39.80]` (`5.93e-67`) | **`+9.104`** `[+7.376, +10.784]` (`7.72e-22`) | `+11.001` | `+14.456 pp` / `+23.218 pp` (`n=267`) |
| **11** | `Released__Aligned` | Tradeoff (`O` safer, higher repair) | `-44.40` `[-48.80, -40.00]` (`2.97e-67`) | `+21.940` `[+19.529, +24.348]` (`6.63e-41`) | `+23.037` | `+29.394 pp` / `+39.575 pp` (`n=272`) |
| **11** | `Aligned__Released` | Tradeoff (`O` safer, higher repair) | `-37.40` `[-41.60, -33.20]` (`1.02e-56`) | `+3.468` `[+1.427, +5.489]` (`6.04e-04`) | `+3.262` | `+11.111 pp` / `+22.221 pp` (`n=243`) |
| **15** | `Released__Released` | Tradeoff (`O` safer, higher repair) | **`-50.80`** `[-55.20, -46.40]` (`6.91e-77`) | **`+15.298`** `[+13.162, +17.356]` (`2.60e-36`) | `+13.323` | `+20.617 pp` / `+31.332 pp` (`n=217`) |
| **15** | `Aligned__Aligned` | Tradeoff (`O` safer, higher repair) | **`-54.60`** `[-58.80, -50.40]` (`1.32e-82`) | **`+7.082`** `[+5.641, +8.469]` (`1.70e-22`) | `+6.371` | `+10.991 pp` / `+19.237 pp` (`n=198`) |
| **15** | `Released__Aligned` | Tradeoff (`O` safer, higher repair) | `-58.60` `[-62.80, -54.20]` (`1.26e-88`) | `+18.303` `[+16.605, +19.996]` (`1.97e-54`) | `+16.949` | `+22.732 pp` / `+31.505 pp` (`n=199`) |
| **15** | `Aligned__Released` | Tradeoff (`O` safer, higher repair) | `-43.40` `[-47.80, -39.20]` (`5.22e-64`) | `+5.111` `[+3.550, +6.725]` (`2.25e-11`) | `+3.473` | `+10.139 pp` / `+19.474 pp` (`n=203`) |

---

## 3. Matched Row Keys, Training Audits, Solver Failures & Guards

- **Matched row keys (`Released_Positional` vs `Aligned_Joint`):**
  - **Seed `11`:** `Released` matched `1/900` train, `0/100` val, `0/500` test rows (`305/500` test indices overlap `0:899`, and `500/500` `Test_Released` capacity/cost rows are drawn from `0:499` inside `Train_Released`'s `0:899` prefix). `Aligned` matched `900/900` train, `100/100` val, `500/500` test (`100%`).
  - **Seed `15`:** `Released` matched `0/900` train, `0/100` val, `0/500` test rows (`313/500` test indices overlap `0:899`, and `500/500` `Test_Released` capacity/cost rows are drawn from `0:499` inside `Train_Released`'s `0:899` prefix). `Aligned` matched `900/900` train, `100/100` val, `500/500` test (`100%`).
- **Training solver failures / skips & numerical guards (`580` batches/arm):**
  - `PFL/MSE`: `0` solver calls, `0` skips, `0` guards, `grad_clip = None` (exact upstream `src/pfl.py`), `0.13–0.14 s` wall time; epoch-20 train MSE drops from `24.914 -> 12.985` (seed `11`) and `24.839 -> 17.461` (seed `15`) under alignment.
  - `ODECE(alpha=0.5)` (`18,000` in-loop CP-SAT solves/arm; all offline train/test oracles `900/900 OPTIMAL` & `500/500 kOptimal`):
    - Seed `11` `ODECE_Released`: `14,002 OPTIMAL`, **`3,998 INFEASIBLE`** (in-loop negative predicted RHS skips, masked out via `mask_t`), Guard 1 (`empty_ipl`) = `234`, Guard 2 (`mask==0`, ep 1) = `8`, IEEE-754 true-sol ULP viols = `260`.
    - Seed `11` `ODECE_Aligned`: `14,667 OPTIMAL`, **`3,333 INFEASIBLE`**, Guard 1 = `238`, Guard 2 = `8`, ULP viols = `240`.
    - Seed `15` `ODECE_Released`: `16,791 OPTIMAL`, **`1,209 INFEASIBLE`**, Guard 1 = `144`, Guard 2 = `4`, ULP viols = `240`.
    - Seed `15` `ODECE_Aligned`: `16,955 OPTIMAL`, **`1,045 INFEASIBLE`**, Guard 1 = `163`, Guard 2 = `4`, ULP viols = `220`.

---

## 4. Raw Data & Sealed Artifact SHA-256 Manifest

### 4.1 Raw Generated Data Hashes (`genCapacity` + `train_test_split`)

| Seed | `X` SHA-256 | `w` SHA-256 | `costs` SHA-256 | `capacity` SHA-256 | `(idx_tr, idx_va, idx_te)` SHA-256 |
|---:|---|---|---|---|---|
| **11** | `9a37ba2ecba5a4e3...` | `95f57249782bdc9f...` | `33fee1c279766759...` | `237683bb3b881925...` | `5d8603697b50b276...` |
| **15** | `3bf23acf0a9ae457...` | `b810e648695728cb...` | `d61fb62b03e1ca49...` | `0337307f4890e573...` | `3c736b2668a674ca...` |

*(Full 64-hex raw data SHA-256 digests are persisted inside [`stage3_capacity_factorial_summary.json`](stage3_capacity_factorial_summary.json).)*

### 4.2 Sealed Stage-3 Scripts, Summaries & Per-Instance HiGHS Outputs

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| [`verify_stage3_synthetic_loading_metrics.py`](verify_stage3_synthetic_loading_metrics.py) | 13,895 | `c8a8b77bbc620c5c6e8e46500114c498425af8535b5afc522a303bb1b98e67a2` |
| [`STAGE3_SYNTHETIC_CHECK_RECEIPT.json`](STAGE3_SYNTHETIC_CHECK_RECEIPT.json) | 1,604 | `8be296a61f0feb18f3689550ec324f7659b8c9a6c694f00356d25e4cf3765e09` |
| [`STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md`](STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md) | 9,682 | `dca02adc5e209bfaa6c215cf18c041ce79735862da054c31f18c71764da9ca66` |
| [`stage3_capacity_pfl_vs_odece_factorial.py`](stage3_capacity_pfl_vs_odece_factorial.py) | 43,670 | `b5002086a04b3b2a019784b0afc450777175f3e00035ae4f9f216ebaa8ca89c1` |
| [`stage3_capacity_factorial_summary.json`](stage3_capacity_factorial_summary.json) | 147,399 | `e773dff8546853d94cf15ccf20dd64907b764e63ec6eb6fb7cdad552f2c2bb18` |
| [`stage3_capacity_factorial_seed11/stage3_seed11_summary.json`](stage3_capacity_factorial_seed11/stage3_seed11_summary.json) | 65,804 | `3c3147f39aa06978c11a9f2ff8836dea3599275f713cb2bd82fb1e41ff629b4a` |
| [`stage3_capacity_factorial_seed11/paired_init_weights.json`](stage3_capacity_factorial_seed11/paired_init_weights.json) | 960 | `188eed622d1f625a6028f401e468650b2aff49c8d572573b14ae2e657626356a` |
| [`stage3_capacity_factorial_seed11/per_instance_highs_PFL_Train_Released__Test_Released_unclipped.json`](stage3_capacity_factorial_seed11/per_instance_highs_PFL_Train_Released__Test_Released_unclipped.json) | 145,121 | `13d68d459ec9c656a761d75a59cb94c0652520d65c544d67578ffaa8d9cc1d94` |
| [`stage3_capacity_factorial_seed11/per_instance_highs_ODECE_Train_Released__Test_Released_unclipped.json`](stage3_capacity_factorial_seed11/per_instance_highs_ODECE_Train_Released__Test_Released_unclipped.json) | 147,421 | `8179cbd784bc3cf386a99b6907e03fb52b1f46f5881160fc4369fcbbeee77f4f` |
| [`stage3_capacity_factorial_seed11/per_instance_highs_PFL_Train_Aligned__Test_Aligned_unclipped.json`](stage3_capacity_factorial_seed11/per_instance_highs_PFL_Train_Aligned__Test_Aligned_unclipped.json) | 145,311 | `221280479e09ec62a6193bd790208ce2468c1606a02da4c3d799d3e1488e8b3d` |
| [`stage3_capacity_factorial_seed11/per_instance_highs_ODECE_Train_Aligned__Test_Aligned_unclipped.json`](stage3_capacity_factorial_seed11/per_instance_highs_ODECE_Train_Aligned__Test_Aligned_unclipped.json) | 147,937 | `fe7c8221091ed72137ee8c7143ad41683f0ca16a11067bcb65cc880b546b658e` |
| [`stage3_capacity_factorial_seed15/stage3_seed15_summary.json`](stage3_capacity_factorial_seed15/stage3_seed15_summary.json) | 66,073 | `183e509724de30734d8531ea9964f0cb3fde3459e8c527292d0c3cde3e62eddf` |
| [`stage3_capacity_factorial_seed15/paired_init_weights.json`](stage3_capacity_factorial_seed15/paired_init_weights.json) | 950 | `a423bae5d0068342846cd793845da8f97a1257b7db169fc2a00f517bb18ffdde` |
| [`stage3_capacity_factorial_seed15/per_instance_highs_PFL_Train_Released__Test_Released_unclipped.json`](stage3_capacity_factorial_seed15/per_instance_highs_PFL_Train_Released__Test_Released_unclipped.json) | 144,727 | `50622d0c534c786119bfe3706a58537a94c25679b657bd321bd0ae53fc20db25` |
| [`stage3_capacity_factorial_seed15/per_instance_highs_ODECE_Train_Released__Test_Released_unclipped.json`](stage3_capacity_factorial_seed15/per_instance_highs_ODECE_Train_Released__Test_Released_unclipped.json) | 147,420 | `41c22ac8c75aa30896358f302c4d63de66564d6341018a62a6f7691c37ccc91a` |
| [`stage3_capacity_factorial_seed15/per_instance_highs_PFL_Train_Aligned__Test_Aligned_unclipped.json`](stage3_capacity_factorial_seed15/per_instance_highs_PFL_Train_Aligned__Test_Aligned_unclipped.json) | 144,797 | `8dda0d81567944c08140b6b78d77a76d9936dc57045758508e8171495a605712` |
| [`stage3_capacity_factorial_seed15/per_instance_highs_ODECE_Train_Aligned__Test_Aligned_unclipped.json`](stage3_capacity_factorial_seed15/per_instance_highs_ODECE_Train_Aligned__Test_Aligned_unclipped.json) | 147,866 | `cf7af6a2ad241802fe1d15e83def004e2202158f6952ce8562a755f70bfae0e8` |

*(All 8 off-diagonal per-instance HiGHS JSONs and all 8 `final_weights_*.json` checkpoints are likewise saved and SHA-256 hashed in each seed's summary JSON.)*
