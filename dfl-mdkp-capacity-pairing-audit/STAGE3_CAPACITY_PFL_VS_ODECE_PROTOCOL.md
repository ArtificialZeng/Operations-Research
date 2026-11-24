# Stage-3 Locked Protocol: Bounded `ODECE(alpha=0.5)` vs. Upstream `PFL/MSE` `2 × 2` Train-Pairing × Test-Pairing Factorial (`MDKP-Capacity`, Published Seeds `11` & `15`)

**Status:** LOCKED PRE-LAUNCH — written and hashed **before** running seeds `11` or `15`.
**Scope Statement:** Controlled benchmark-integrity adaptation of the NeurIPS 2025 Table 2 `MDKP-Capacity` comparison on published seed IDs **`11` and `15`** (explicitly labeled as a diagnostic subset of `11–15`). Both the diagonal contrast (`Released/Released` vs. `Aligned/Aligned`) and the off-diagonal cross-cells (`Released/Aligned`, `Aligned/Released`) are strictly **controlled adaptations**, **never** reproduced published paper scores.

---

## 1. Pre-Launch Gates & SHA-256 Manifest

1. **Direct PyTorch `ODECE` Parity Gate:** [`ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json`](ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json) (`573671e4...`) — `direct_pytorch_gate_pass_float64 = true`, `all_four_fixtures_exercised = true` (max autograd vs. 33-param FD error `2.14e-10` on `W` `< 1e-7`, `1.95e-10` on `b` `< 1e-8`).
2. **Stage-3 Minimal Synthetic Loading, Isolation, Metric & PFL-Parity Gate:** [`STAGE3_SYNTHETIC_CHECK_RECEIPT.json`](STAGE3_SYNTHETIC_CHECK_RECEIPT.json) (`8be296a6...`) — `all_checks_passed = true` (`PFL/MSE` step diff = `0.0` vs. `src/pfl.py`, strict anti-leakage prediction-solver check passed, 4-instance hand-verified metric & negative-RHS check passed).

| File | Bytes | SHA-256 |
|---|---:|---|
| `verify_stage3_synthetic_loading_metrics.py` | 13,895 | `c8a8b77bbc620c5c6e8e46500114c498425af8535b5afc522a303bb1b98e67a2` |
| `STAGE3_SYNTHETIC_CHECK_RECEIPT.json` | 1,604 | `8be296a61f0feb18f3689550ec324f7659b8c9a6c694f00356d25e4cf3765e09` |
| `stage3_capacity_pfl_vs_odece_factorial.py` | 43,670 | `b5002086a04b3b2a019784b0afc450777175f3e00035ae4f9f216ebaa8ca89c1` |
| `official_odece_repo/KnapsackCapaExp.py` | 7,365 | `faffe92415df659360603ec90494be496a8d89168ba1e1e7b60d38b54f2ed971` |
| `official_odece_repo/MDKP_CapaExp.sh` | 692 | `29e08746be2449bf207636f71699f2f997f7520128afbda0fa65eb411ba6fd15` |
| `official_odece_repo/src/pfl.py` | 23,682 | `3cf21d21aa8c3afb437a892aa4c97472b1cf010fdcd18443ef644179ed786b61` |
| `official_odece_repo/src/odece.py` | 12,415 | `07c0161ba5bcbfae848ec68a90fa5d7d28567c42bec9161a089a81ff17bedf48` |
| `official_odece_repo/OptProblems/knapsack/kpdataset.py` | 2,122 | `ea7be9b763d6678c21d0b933367ce1ee3aa0bcfbffae2ffc12a8b0ceca4c86fd` |
| `official_odece_repo/OptProblems/knapsack/kpsolver.py` | 8,912 | `f1fc217c11daa5ab02e7de52c416428ce10016c1845b216e1faaea8c4beb63f5` |
| `official_odece_repo/OptProblems/knapsack/kpdata.py` | 5,708 | `bd21081c6f1861c7c2d5421a29e1415832541ab08b0f528fdf6673c972a8ef30` |
| `official_odece_repo/ML/TorchML.py` | 6,871 | `6cb64787154cde4a57bb35ddc3e4ae369901ed4ff394a40132ac7ec2d19f0775` |

---

## 2. Exact `2 × 2` Factorial Design (Published Seeds `11` & `15`, Separate Run Directories)

- **Data generation (exact `MDKP_CapaExp.sh` flags):** `genCapacity(num_data=1500, num_features=10, num_items=50, dim=3, deg=6, noise_width=0.25, fixed_cost=False, seed=seed)` with `train_test_split` (`900` train / `100` val / `500` test, `random_state=seed`). Raw data arrays `(X, w, costs, capacity)` and split indices `(idx_tr, idx_va, idx_te)` are SHA-256 hashed per seed.
- **Two Train Pipelines (fixed `X_tr = X[idx_tr]`, `W_tr = w[idx_tr]`):**
  1. **`Train_Released` (`Released_Positional`):** Literal `KnapsackCapaExp.py:L69-75` + `kpdataset.py` — positional `capacity[0:900]` and positional `costs[0:900]`.
  2. **`Train_Aligned` (`Aligned_Joint`):** Same row indices `idx_tr` applied to every field — `capacity[idx_tr]` and `costs[idx_tr]`.
- **Two Test Evaluation Interpretations (fixed scenario order `X_te = X[idx_te]`, `W_te = w[idx_te]`):**
  1. **`Test_Released` (`Released_Positional`):** Row $i \in \{0,\dots,499\}$ has evaluation capacity `capacity[i]` (`0:500`) and evaluation costs `costs[i]` (`0:500`).
  2. **`Test_Aligned` (`Aligned_Joint`):** Row $i \in \{0,\dots,499\}$ has evaluation capacity `capacity[idx_te[i]]` and evaluation costs `costs[idx_te[i]]`.
- **Four Frozen Models per Seed:** `{PFL/MSE, ODECE(alpha=0.5)} × {Train_Released, Train_Aligned}`, each evaluated on BOTH `Test_Released` and `Test_Aligned` -> 4 cells per seed (`Train_Released__Test_Released`, `Train_Aligned__Test_Aligned`, `Train_Released__Test_Aligned`, `Train_Aligned__Test_Released`). Within every cell, compare `ODECE(alpha=0.5)` directly against `PFL/MSE` on identical `(train, test)` pairings.

---

## 3. Prediction-Solver Isolation & Raw Policy Rules (Zero True-Capacity Leakage)

- **Strict Isolation Guarantee:** The prediction solver (`solve_single_highs`) receives **ONLY** `(W_te[i], cap_hat[i], c_eval[i])` — the evaluation row's known weights, the frozen model's predicted capacity `cap_hat[i] = model(X_te[i])`, and the evaluation row's known costs.
- **Evaluation Row's True Capacity (`cap_eval[i]`):** Used **ONLY** for (1) the true oracle `(x*_eval[i], obj*_eval[i])`, (2) realized feasibility verification, and (3) post-hoc repair/scoring. Under **no condition** is true test capacity passed to the prediction solver, clipping, fallback choice, or model.
- **Raw Policy Only:** **No** gamma selection, **no** post-hoc margin selection, **no** validation thresholds.
- **Negative Predicted RHS Treatment:**
  - **Primary (`raw_unclipped_primary`):** Exact literal upstream `kpsolver.py` / `src/pfl.py:L359-372` behavior — any row with `any(cap_hat[i] < 0)` returns `kInfeasible` (unsolvable/skip), excluded from source-defined raw infeasibility & feasible-only regret denominators, counted as failed in all-500 strict 0–1 risk, and assigned normalized empty-knapsack loss `1.0` in all-instance repair loss. Every negative predicted RHS dim/row and skip is explicitly counted and reported.
  - **Secondary (`pred_only_zeroclip_fallback`, documented whenever `n_neg_pred_rows > 0`):** Purely prediction-side `np.clip(cap_hat, 0.0, None)` (uses **zero** true capacity; turns negative-RHS rows into optimal `x = 0` feasible decisions with regret `1.0`).

---

## 4. Exact Upstream `PFL/MSE` vs. `ODECE(alpha=0.5)` Specification & Documented Source Differences

- **Shared Architecture & Budget (`MDKP_CapaExp.sh:L6,8`, `ML/TorchML.py:L49-68`):**
  - `LinearRegressionforKP_PredCapacity(10, 50, 3)` (`nn.Linear(10, 3, bias=True)`, `xavier_uniform_` weights, `zeros_` bias, no output clamping).
  - `Adam(lr=0.005)` (default PyTorch betas/eps, no scheduler), `batch_size=32`, `max_epochs=20`, epoch-20 weights frozen for test.
- **`PFL/MSE` (`src/pfl.py:L137-197, 465-481`):**
  - Loss formula: `nn.MSELoss()` (`reduction='mean'`) on predicted vs. target capacity; **no gradient clipping** (matching `src/pfl.py:L173-176`); `0` training MIP solves.
- **`ODECE(alpha=0.5)` (`src/odece.py:L75-252`):**
  - Unmodified pinned `ODECE.losses_computation` with `alpha=0.5`, original `margin_threshold=2.0`, `nn.utils.clip_grad_norm_(0.5)`, plus validated Guard 1 (`empty_ipl -> 0.0`, preventing `NaN`) and Guard 2 (`mask==0` symmetric at `alpha=0.5`).
- **Documented Controlled-Adaptation Differences vs. Published Upstream Runs:**
  1. **Solvers:** OR-Tools `CP-SAT` (`_SCALE=10000`, `5s` offline / `2s` in-loop) for training and unrounded `float64` `HiGHS 1.16.0` (`mip_rel_gap=1e-4`, `5s`) for all test oracle & prediction solves in place of commercial Gurobi (`TimeLimit=10`). Note explicitly that **`kOptimal` refers to HiGHS solver tolerance (`mip_rel_gap = 1e-4`)**.
  2. **Precision:** `torch.float64` throughout (matching our validated direct PyTorch parity gate) instead of upstream `torch.FloatTensor` (`float32`).
  3. **Paired Initialization & Minibatch Order:** All 4 models per seed share the exact same `torch.manual_seed(seed)` Xavier-uniform/zero-bias `float64` checkpoint (`paired_init_weights.json`) and deterministic permutation stream (`rng(seed + 1000)`), whereas upstream `KnapsackCapaExp.py` initializes `reg` before `torch.manual_seed(seed)` and uses PyTorch `DataLoader(shuffle=True)`.
  4. **Metric Aggregation & Exception Scoring:** Upstream `src/pfl.py:L409-424` averages unweighted batch-64 `nanmean` values across 8 batches (7×64 + 1×52) and logs unnormalized `true_obj * penalty_coeff` on solver exceptions (`L371`). We compute exact instance-level pooled ratios with explicit integer numerators/denominators and normalized `1.0` fallback loss on skips.

---

## 5. Required Reported Metrics & Outputs (Per Seed `11` & `15`, All 4 Cells)

1. **Source-defined raw infeasibility** (`n_infeas_solved / n_solved`, with exact numerator/denominator).
2. **Source-defined feasible-only normalized regret** (with exact denominator `n_strict_feasible`, plus intersection `both_feasible` paired diff).
3. **Per-instance strict 0–1 risk (`n = 500`)** and **all-instance strict 0–1 integer-repair post-hoc loss (`p = 1.0`, plus `p = 0.21` and fractional surrogate)**.
4. **Risk/repair dominance classification** (`ODECE_dominates`, `PFL_dominates`, or explicit tradeoff) and **paired per-seed method gaps (`ODECE - PFL/MSE`)** with conditional 95% bootstrap CIs, Wilcoxon $p$, and exact McNemar $p$.
5. **Matched row keys, raw data & per-instance output SHA-256 hashes, and all guard/solver failures (including skips).**
6. **Direct answer:** Does complete scenario-row alignment materially change the relative `ODECE(alpha=0.5)` vs. `PFL/MSE` comparison, or mostly shift both methods' absolute performance numbers?
