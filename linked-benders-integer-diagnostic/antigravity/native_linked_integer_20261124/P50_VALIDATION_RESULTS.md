# Frozen `p50` 4-Arm Single-Tree Attribution Results (120 s/Arm — Formal Closure)

**Working Directory:** `D:\AI_Science\antigravity\native_linked_integer_20261124\`  
**Execution Date:** 2026-11-24  
**Protocol:** [P50_VALIDATION_PROTOCOL.md](file:///d:/AI_Science/antigravity/native_linked_integer_20261124/P50_VALIDATION_PROTOCOL.md)  
**Runtime & Pinning:** `Python 3.14.10`, `ortools 9.15.6755` (`SolverType.GSCIP`), `scipy 1.18.1` (`highs-ds`), `numpy 2.5.3`, `networkx 3.7`, `threads = 1`, `cpu_affinity = [26]`.

---

## 1. Frozen Artifact SHA-256 Fingerprints

| File | SHA-256 | Role |
|---|---|---|
| `P50_VALIDATION_PROTOCOL.md` | `e5e78d2a5d1ce9267298989959922a0e88b5b7e40b67de7908680a4ad8efdeb2` | Frozen pre-outcome 4-arm protocol |
| `linked_benders_integer_p50.py` | `36f96e7a3f39a34c0294aca93c659a234f5eedbf19c1354f3b34a1e36065ce5c` | Frozen cold 4-arm worker (`worker_saw_reference_files = false`) |
| `evaluate_p50_integer_run.py` | `c8fcf7b511d673ffdb19132b24d1c0badaf64dd719442ef020715097d868f704` | Amended post-run exact verifier & provenance checker |
| `p50_integer_raw.json` | `f89be8e0b090ed1c0c13c5ec843df04ce2d525db08abea67657edb112b076336` | Full 120 s/arm cold worker output (`29.495 s` total wall) |
| `p50_integer_evaluated.json` | `1c7735d592e8fd3a6c760f6a31ac66097e77033d5cdf93207aa115d202d9af61` | Standalone post-run exact evaluation (`0.923 s`) |

Separate 10 s/arm plumbing smoke artifacts (`p50_integer_smoke_raw.json`, `p50_integer_smoke_evaluated.json`) are excluded from decision-grade evidence.

---

## 2. Four-Arm Cold Single-Tree Summary (`p50`, 30 × 90 × 200)

All four arms received the identical train-free model-input-only cold seed (`bits = 000000001100100011110100000000`, `open_real_sites = [8,9,12,16,17,18,19,21]`, `open_count = 8`, `seed_sha256 = deeaa46f959117515096f54188abe4159ea827d7792c1c147cc5b643809c5450`, `matches_shared_cold_seed = true`), executed **one** `GSCIP` solve (`solve_calls = 1`), and terminated numerically `OPTIMAL` at `node_count = 1` well below the `120 s` cap. Post-run exact 200-scenario repricing (`experiments/liu_lost_sales/solve.py:verify`, `0.886 s`, fixed dummy `30`, `witness_sha256 = 171fc81c3e115e0eab4d22b77418ef17983e26a99fba5eeb64dc63e7ecfd058a`) confirmed that the **mechanical cold seed itself already equaled the unique certified exact global optimum** `110941759969/16087500` (`6896.146696`, `cold_seed_already_optimal = true`, `post_run_exact_reference_incumbent_gap = 0` for all four arms).

| Metric | A1: `orig_single` | A2: `orig_multi_floor` | A3: `orig_single_hinge_floor` *(Matched Control)* | B: `sep_single_hinge` *(Candidate)* |
|---|---:|---:|---:|---:|
| `solve_calls` / `seed_matched` / `valid` | `1` / `True` / `True` | `1` / `True` / `True` | `1` / `True` / `True` | `1` / `True` / `True` |
| Termination (`reason / limit`) | `OPTIMAL / None` | `OPTIMAL / None` | `OPTIMAL / None` | `OPTIMAL / None` |
| Unique binary sweeps (incl. seed) | `6` | `6` | **`5`** | **`5`** |
| Callbacks / cache hits / lazy cuts | `11 / 6 / 5` | `24 / 19 / 572` | `52 / 48 / 2` | `17 / 13 / 2` |
| `GSCIP` nodes / simplex iters | `1` / `9` | `1` / `475` | `1` / `234` | `1` / `41` |
| Observed sampled pos-hinge layouts | `4/6` (final `0`) | `3/6` (final `0`) | `2/5` (final `0`) | `2/5` (final `0`) |
| **Search time (`before_certification`)** | **`6.246 s`** | **`6.589 s`** | **`5.419 s`** | **`5.042 s`** |
| — Cold seed eval / Master build | `1.107 s` / `0.002 s` | `1.015 s` / `0.026 s` | `1.025 s` / `0.013 s` | `1.006 s` / `0.013 s` |
| — `GSCIP` wall (`subprob` / `overhead`) | `5.135 s` (`5.091` / `0.045`) | `5.548 s` (`5.119` / `0.429`) | `4.381 s` (`4.226` / `0.155`) | `4.023 s` (`3.983` / `0.040`) |
| **Worker cert (`grid` / `cut-LP`)** | `1.502 s` (`1.251` / `0.251`) | `1.554 s` (`1.293` / `0.261`) | `1.549 s` (`1.296` / `0.253`) | `1.513 s` (`1.260` / `0.252`) |
| Exact 200-scen `U_exact_IP` (`ref_gap`) | `6896.146696` (`0`) | `6896.146696` (`0`) | `6896.146696` (`0`) | `6896.146696` (`0`) |
| Exact rational cut-LP lower `L_cert_LP` | `6678.698` | `6821.905` | `6667.821` | `6822.324` |
| SCIP numeric dual bound *(diagnostic only)* | `6896.146695819736` (`0.0`) | `6896.146695819735` (`1.32e-16`) | `6896.146695819734` (`2.64e-16`) | `6896.146695819736` (`0.0`) |

- **Numerical Hygiene (All 4 Arms)**: `deadline_interrupts = 0`, `large_integrality_deviation_calls = 0` (`max <= 2.44e-15`), `unseparated_material_discrepancy_calls = 0` (`max_unseparated_material_discrepancy = 0.0`, `max_unseparated_sum_discrepancy = 0.0`), `max_subproblem_duality_err <= 1.36e-12`, `max_pointwise_identity_diff <= 5.82e-11`, `trimmed_flow_grid_ticks = 0`.
- **Provenance Verification (Post-Run Only)**: Verified `p50_rival_continuation.json` (`SHA-256: 571642a3...`) → `lock.json` (`5dbeac7a...`) → `manifest.json` (`9be4fb79...`) → `p50` `instance_sha256` (`957d0068...`), and `p50_separated.json` (`d61e7a2e...`) → same `instance_sha256`, with `global_optimum_certified = true` and exact `global_lower == global_upper == 110941759969/16087500`.

---

## 3. Formal Gate Verdict & Strict Non-Overclaiming Boundaries

- **Gate Branch**: `branch_1_qualifying_optimality_antecedent_holds` — **CLOSED (`verdict = "close_separation_superiority_on_p50"`, `passed_p50_attribution_gate = false`)**:
  - **Sweep Gate (`>= 25%` AND `>= 5` sweeps saved vs. every original arm)**: **FAILED** against all three comparators (`5` vs. `6` for A1, `5` vs. `6` for A2, **`5` vs. `5` exact tie for matched control A3**).
  - **Time Gate (`<= 0.80x` search time vs. every original arm)**: Passed only vs. A2 (`5.042 / 6.589 = 0.765x`), **FAILED** vs. A1 (`5.042 / 6.246 = 0.807x`) and **FAILED** vs. matched control A3 (`5.042 / 5.419 = 0.930x`).
  - **`a3_control_blocked_separation_attribution_on_p50 = true`**: Matched original-price single-cut control **A3 (`orig_single_hinge_floor`)** tied Arm B identically on unique binary sweeps (`5` vs. `5`), lazy cuts (`2` vs. `2`), and root-node closure (`1` vs. `1`), with search time within `7.0%` (`5.419 s` vs. `5.042 s`).
- **Truthful Scope Statement**:
  1. On `p50`, all four arms started from an already-optimal mechanical cold seed (`cold_seed_already_optimal = true`), so incumbent finding was uninformative; evaluation rests on sweeps, search time, `L_cert_LP` (`6822.324` for B vs. `6821.905` for A2 vs. `6667.821` for A3 vs. `6678.698` for A1), and numeric termination diagnostics (not exact rational global proofs).
  2. Matching `A3` to `B` on `p50` **blocks generalization and attribution of shortage-price separation superiority on `p50`** and formally closes the single-tree separation superiority line.
  3. **No causal claim about `p26` is permitted from `p50`**: `p26` did not include arm `A3`, so the `p50` closure does **not** identify what caused the observed `p26` speedup (`17` vs. `26` vs. `43` sweeps).
