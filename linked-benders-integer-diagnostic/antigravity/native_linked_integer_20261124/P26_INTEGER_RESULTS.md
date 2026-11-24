# Frozen `p26` Single-Tree Lazy Integer Linked Benders Results (60 s/Arm)

**Working Directory:** `D:\AI_Science\antigravity\native_linked_integer_20261124\`  
**Execution Date:** 2026-11-24  
**Protocol:** [INTEGER_KILL_TEST_PROTOCOL.md](file:///d:/AI_Science/antigravity/native_linked_integer_20261124/INTEGER_KILL_TEST_PROTOCOL.md)  
**Runtime & Pinning:** `Python 3.14.10`, `ortools 9.15.6755` (`SolverType.GSCIP`), `scipy 1.18.1` (`highs-ds`), `numpy 2.5.3`, `threads = 1`, `cpu_affinity = [26]`.

---

## 1. Frozen Artifact SHA-256 Hashes (Unmodified Post-Execution)

| File | SHA-256 | Role |
|---|---|---|
| `linked_benders_integer_p26.py` | `de44a7ea171864c05a8ad5741956b4e984cd97faeb504bf7a73a2db3b9fdb4b5` | Frozen cold single-tree worker (`worker_saw_reference_files = false`) |
| `evaluate_p26_integer_run.py` | `785f49b85183836b692817f74a260c04d93f72e10bb7d68984112e1208fd3c95` | Frozen standalone post-run exact verifier & scorer |
| `p26_integer_raw.json` | `d4885ee45c35a229ab002b027a169f84df6ca1408efc4433dff2f7545539efaa` | Cold 60 s/arm worker output (`total_wall_seconds = 51.927 s`) |
| `p26_integer_evaluated.json` | `2a0615ffb4ddb9fc6dd6fe8882c48946b9b4fb9aaf3708a2366713f63544b791` | Standalone post-run 200-scenario exact evaluation (`0.920 s`) |

Smoke files (`p26_integer_smoke_raw.json`, `p26_integer_smoke_evaluated.json`) remain preserved separately and were never reused as incumbents or decision-grade evidence.

---

## 2. Three-Arm Cold Single-Tree Summary (`p26`, 20 × 50 × 200)

All three arms shared the identical train-free model-input-only cold seed (`11111101011101011011`, `15` open sites, cold objective `5913.898496`, evaluated inside each arm's clock), executed **one** `GSCIP` solve (`solve_calls = 1`, zero outer restarts), and converged to the identical 15-site binary opening `11111101011101110011` (`open_real_sites = [0,1,2,3,4,5,7,9,10,11,13,14,15,18,19]`).

| Metric | A1: `orig_single` | A2: `orig_multi_floor` (Strong Baseline) | B: `sep_single_hinge` (Candidate) |
|---|---:|---:|---:|
| Master structure | Plain single-cut (`theta >= 0`) | Multi-cut + direct floor `theta_s >= (rho-eta)(D_s - sum min(u_i,D_s)x_i)/div` | Residual single-cut + 200 scalar hinges `h_s` priced at `(rho-eta)/div` |
| `solve_calls` | `1` | `1` | `1` |
| Termination (`reason` / `limit`) | `OPTIMAL` / `None` | `OPTIMAL` / `None` | `OPTIMAL` / `None` |
| Unique binary sweeps (incl. seed) | `43` (`42` in-tree + `1` seed) | `26` (`25` in-tree + `1` seed) | **`17`** (`16` in-tree + `1` seed) |
| Total callbacks / cache hits | `188` / `146` | `36` / `11` | `55` / `39` |
| Lazy cuts added in-tree (pool total) | `15` (`16`) | `2,961` (`3,161`) | `11` (`12`) |
| `GSCIP` nodes / simplex iters | `2` / `332` | `32` / `3,872` | `14` / `677` |
| **Search time (`before_certification`)** | **`24.162 s`** | **`15.552 s`** | **`9.698 s`** |
| — Cold seed eval (included in search) | `0.557 s` | `0.597 s` | `0.568 s` |
| — `GSCIP` wall / callback subproblems | `23.602 s` / `23.460 s` | `14.934 s` / `14.291 s` | `9.121 s` / `9.019 s` |
| — Best incumbent found at | `3.213 s` (sweep `5`) | `3.556 s` (sweep `5`) | `2.712 s` (sweep `4`) |
| **Worker certification time (outside search)** | `0.815 s` | `0.848 s` | `0.773 s` |
| Exact 200-scen repricing (`liu_solve.verify`) | `135321426758663/24344775000` (`5558.540868`) | `135321426758663/24344775000` (`5558.540868`) | `135321426758663/24344775000` (`5558.540868`) |
| Exact scenarios verified / witness SHA-256 | `200/200` (`e8614f6d...`) | `200/200` (`e8614f6d...`) | `200/200` (`e8614f6d...`) |
| Post-run exact ref incumbent gap (`z_ref_IP`) | `0` (exact rational) | `0` (exact rational) | `0` (exact rational) |
| Auxiliary grid fallback / trimmed ticks | `5558.540868` / `0` | `5558.540868` / `0` | `5558.540868` / `0` |
| Exact rational cut-LP lower `L_cert_LP` | `5508.508867` (`<= U_ref_LP`) | `5522.711212` (`<= U_ref_LP`) | `5510.291209` (`<= U_ref_LP`) |
| SCIP numeric dual bound (**diagnostic only**) | `5558.540867954747` (`gap = -1.64e-16`) | `5558.540867954746` (`gap = 0.0`) | `5558.540867954745` (`gap = 1.64e-16`) |

- **Standalone post-run evaluator wall time (strictly after worker exit)**: `0.920 s` total (`0.894 s` to exact-reprice the single shared distinct final layout across all 200 scenarios via frozen `experiments/liu_lost_sales/solve.py:verify` with fixed dummy `20`).
- **Bound & Proof Hygiene**: SCIP's `best_objective_bound` is a floating-point solver diagnostic (notice the `-1.64e-16` / `+1.64e-16` 1-ULP IEEE-754 roundoff against the exact rational incumbent) and is **not** treated as a solver-side exact rational global optimality proof. Exact rational bounds certified here are (i) the fixed-opening 200-scenario primal-dual network-simplex objective (`135321426758663/24344775000`), (ii) each arm's continuous cut-pool LP lower bound `L_cert_LP <= U_ref_LP(p26)`, and (iii) the independent post-run exact reference incumbent gap `0` against `experiments/diaz_lost_sales/p26_class9_finite.json`.

---

## 3. Callback Numerical Discrepancies (Transparent Audit)

| Diagnostic | A1: `orig_single` | A2: `orig_multi_floor` | B: `sep_single_hinge` |
|---|---:|---:|---:|
| `deadline_interrupts` | `0` | `0` | `0` |
| `max_integrality_deviation` (`large > 1e-5` calls) | `3.38e-14` (`0`) | `1.82e-15` (`0`) | `0.0` (`0`) |
| `unseparated_material_discrepancy_calls` | `0` | **`1`** | `0` |
| `max_unseparated_material_discrepancy` | `0.0` | **`1.09127e-05`** | `0.0` |
| `max_subproblem_duality_err` | `1.73913e-05` | `1.09127e-05` | `1.09127e-05` |
| `max_pointwise_identity_diff` | `3.64e-12` | `3.64e-12` | `7.28e-12` |

- **Explanation of `orig_multi_floor`'s 1 unseparated discrepancy (`1.09127e-05`)**: On one multi-cut callback where no projected valid cut exceeded `cut_tol = 1e-6`, the maximum single-scenario gap between HiGHS's primal subproblem objective `ev.sub_objs[s]` and `theta_s` was `1.0912698412468558e-05` — identical to `max_subproblem_duality_err = 1.0912698413800825e-05` (~`2e-9` relative to the `5558.54` total objective). This reflects HiGHS dual-simplex primal-dual tolerance on one scenario LP rather than a cut-projection bug or unseparated integer solution; all three arms converged to the exact same rational global optimum.

---

## 4. Pre-Registered Gate Evaluation & Open Attribution Question

- **Gate Branch**: `branch_1_both_optimal_with_exact_zero_incumbent_gap` — **PASSED (`advance_to_p50 = true`)**:
  - **Sweeps**: `17` vs. `43` (`-60.5%`, `-26` sweeps) and vs. `26` (`-34.6%`, `-9` sweeps) — exceeds `>= 25%` and `>= 5` sweeps against **both** original arms.
  - **Search wall time**: `9.698 s` vs. `24.162 s` (`0.401x`, `-59.9%`) and vs. `15.552 s` (`0.624x`, `-37.6%`) — beats `<= 0.80x` against **both** original arms.
- **Scope Caveat (Why No Generic or Causal Claim Yet)**: While `p26` cleared the pre-registered gate against both `orig_single` and `orig_multi_floor`, A2 differed from B in **both** cut aggregation (`200` scenario $\theta_s$ variables & `2,961` lazy rows vs. `1` $\theta$ variable & `11` lazy rows) and pricing ($\rho$ vs. $\eta$). Therefore `p26` alone **cannot** prove that shortage-price separation itself (rather than single-cut epigraph compactness + upfront scalar hinges) caused the gain, nor that the gain transfers outside `p26`. That exact causal and out-of-instance test is pre-specified in [P50_VALIDATION_PROTOCOL.md](file:///d:/AI_Science/antigravity/native_linked_integer_20261124/P50_VALIDATION_PROTOCOL.md).
