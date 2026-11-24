# Stage-2c Locked Protocol: Bounded Upstream `ODECE(alpha=0.5)` Capacity-Mispairing Mechanism Confirmation on Fresh Seed `16` (`dfl_constraints_dual_pinball_20261124`)

**Status:** LOCKED BEFORE ANY SEED-16 FITS (2026-11-24)  
**Pre-Launch Parity Receipt:** [ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT.json](ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT.json) — verified directly against **ACTUAL unmodified pinned upstream `official_odece_repo/src/odece.py`** (`commit 1b432e03ce9ded1e504df60fd4c44cf936334d4f`, `predict_indices=1`, `alpha=0.5`, `torch.float64`): PyTorch autograd matches exhaustive 33-parameter central finite differences (`eps=1e-6`) to `<= 2.14e-10` across mixed, partial-mask, `mask==0`, and guarded empty-IPL cases.  
**Scope & Causal Label:** Strictly a **controlled mechanism confirmation** testing the upstream indexing defect (`KnapsackCapaExp.py:L69-73`) inside **one upstream DFL loss recipe (`ODECE`, prespecified middle `alpha = 0.5`)** on **one fresh generator seed (`16`)**. Does **NOT** claim original published rankings; no all-alpha sweep; no PDF, publicity, or external correspondence.

---

## 1. Fresh Seed, Reserved Seeds & Published Data Regime
- **Active Fresh Seed:** Official-style fresh generator seed **`16`** (never inspected prior to this locked run).
- **Reserved Untouched Seeds:** Seeds **`17, 18`** remain completely untouched.
- **Exact Published Flags (`official_odece_repo/MDKP_CapaExp.sh:L6`):**
  - `genCapacity(num_data=1500, num_features=10, num_items=50, dim=3, deg=6, noise_width=0.25, fixed_cost=False, seed=16)`.
  - Exact `sklearn.model_selection.train_test_split` indices (`test_size=500`, then `test_size=0.1`, `random_state=16`) -> `900 train / 100 val / 500 test`.

---

## 2. Controlled Two-Arm Intervention (Identical Clean Contexts, Weights, Costs, Init, Minibatch Order & Clean Val/Test)
Between both arms, **ALL** of the following are strictly identical:
- Clean training `(X_tr, w_tr, costs_tr) = (X[idx_tr], w[idx_tr], costs[idx_tr])`.
- Clean validation `(X_va, w_va, cap_va, costs_va) = (X[idx_va], w[idx_va], capacity[idx_va], costs[idx_va])`.
- Clean test `(X_te, w_te, cap_te, costs_te) = (X[idx_te], w[idx_te], capacity[idx_te], costs[idx_te])`.
- **Paired Identical Model Initialization:** Single `LinearRegressionforKP_PredCapacity(10, 50, 3).double()` initialized with `torch.manual_seed(16)` and deep-copied byte-for-byte to both arms.
- **Official Training Budget & Optimizer:** `infeasibility_aversion_coeff = 0.5`, `margin_threshold = 2.0`, `lr = 0.005`, `batch_size = 32`, `max_epochs = 20`, `torch.optim.Adam`, `nn.utils.clip_grad_norm_(model.parameters(), 0.5)`, identical minibatch permutation schedule (`np.random.default_rng(16 + 1000)`).

**ONLY Training Capacity Targets Change:**
1. **`ODECE-Clean(alpha=0.5)`:** Training capacities `cap_tr_clean = capacity[idx_tr]`, with offline training labels `sols_tr_clean` solved on `(w_tr, cap_tr_clean, costs_tr)` (matching `kpdataset.py:L32`).
2. **`ODECE-Mispaired(alpha=0.5)`:** Training capacities `cap_tr_misp = capacity[:900]` (upstream unsplit prefix from `KnapsackCapaExp.py:L73`), with offline training labels `sols_tr_misp` solved on `(w_tr, cap_tr_misp, costs_tr)`.

---

## 3. Direct Call to Pinned Upstream `src/odece.py` in `torch.float64` + Documented Numerical Guards
Both arms invoke **ACTUAL unmodified pinned `ODECE.losses_computation(...)`** (`official_odece_repo/src/odece.py`, `OptProblems/knapsack/kpsolver.py`) directly in `torch.float64` with two explicitly logged numerical guards:
1. **`guard1_empty_ipl`:** When `mask.sum() > 0` and `loss_ipl.numel() == 0` (0 infeasible predicted solutions in the batch), replace empty-tensor `.mean()` (`NaN` in unmodified `src/odece.py:L241`) with `torch.zeros((), dtype=torch.float64)` and log `n_zero_infeas_batches`.
2. **`guard2_mask_zero`:** When `mask.sum() == 0` (all 32 predicted capacities negative -> CP-SAT returns `INFEASIBLE`, matching upstream Gurobi `INFEASIBLE -> mask[b]=False`), invoke unmodified `ODECE.losses_computation(...)` (whose swapped tuple `(OPL, 0)` at `alpha = 0.5` is algebraically identical to `(0, OPL)`) and log `n_mask_zero_batches` and total `n_train_infeasible_solves`.
3. Also record `n_true_sol_ulp_viols` (count of exact binding optimal training constraints hitting `+1.78e-15` IEEE-754 summation ULP in `kpsolver.constraint_wise_feasibility`) transparently.

---

## 4. Same Solver, Stage-2b Selection Policy & Exact Receipts
- **Solvers:** Identical `OR-Tools CP-SAT` (`_SCALE=10000`, `14` workers) for offline train/val (`900 + 900 + 100`), in-loop training (`18,000` per arm), and clean validation calibration (`11 * 100` per arm); **unrounded `float64` `HiGHS 1.16.0`** (`mip_rel_gap=1e-4`, `time_limit=5.0`) for **100% of offline clean test OPT (`500`) and 100% of all confirmatory clean test evaluations (`500` each)**.
- **Decision Policies (Exact Stage-2b Policy):**
  - `Raw_Plugin (gamma = 0)`: Evaluated both unclipped (reporting exact `unsolvable_rate` if any predicted capacity is `< 0`) and Stage-2b clipped `>= 0.0` (logging `n_neg_cap_dims_clipped`).
  - `ValPinned_le10pct`: Exact Stage-2b policy $\hat{b}_\gamma = \max(\hat{b} - \gamma \hat{\sigma}_{\text{val}}, 0)$ over $\gamma \in \{0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00\}$, choosing $\gamma^*$ on clean `val` minimizing `official_frac_surrogate_posthoc_p1` subject to `val strict_01_infeasibility_rate <= 0.10` (fallback: lowest val infeasibility).
- **Receipts Persisted:** Real OS `PID`, SHA-256 hashes of pinned upstream files + protocol + script + checkpoints, exact solver status counts, per-epoch diagnostics, per-arm outputs, per-instance HiGHS test JSONs, and paired `ODECE-Clean - ODECE-Mispaired` uncertainty (`n=500`, 95% bootstrap CI, Wilcoxon $p$, exact McNemar $p$). Also logs 0-MIP supervised `OLS-Clean` vs `OLS-Mispaired` `OOS R^2` on seed `16` strictly as a data-signal sanity check.
