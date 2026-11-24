# Stage-1a Locked Protocol: Validation-Pinned 7-Alpha Baseline Audit on Fresh Seed `12` (`dfl_constraints_dual_pinball_20261124`)

**Status:** LOCKED BEFORE IMPLEMENTATION (2026-11-24)  
**Benchmark:** **Aligned benchmark adaptation** of official Apache-2.0 NeurIPS 2025 `MDKP-Weights` (`genWeights` from `JayMan91/OdeceDFLforConstraintsNeurips25`, commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`; `num_items=50`, `dim=3`, `num_feat=10`, `deg=6`, `noise_width=0.25`, `capacity_ratio=[0.18, 0.20, 0.22]`). Jointly permutes and splits all four arrays `(X, w, capacity, costs)` into strictly disjoint `900 train / 100 val / 500 held-out test` (`SOURCE_INDEX_RECEIPT.json`). Not a reproduction of upstream unsplit scores.

---

## 1. Fresh Seed & Reserved Sealed Seeds
- **Active seed for Stage-1a:** Official fresh seed **`12`** (never inspected before this protocol).
- **Untouched reserved seeds:** Official seeds **`13, 14, 15`** remain completely untouched and sealed until Stage-1a completes and is reviewed.

## 2. Methods & Identical Training Budget (No `SW-Pinball` Scaling)
All models use the exact same linear predictor (`10 -> 150`, Xavier uniform init, zero bias, Adam `lr=0.05`, `batch_size=32`, `max_epochs=20`, seed `12`):
1. **`MSE` (`PFL`):** Official symmetric MSE baseline (`0` offline train-label solves, `0` in-loop train solves).
2. **`MSE + Val-Shift(gamma)`:** Exact `MSE` predictor shifted by $+\gamma \hat{\sigma}_{\text{val}}$ (`sigma_val` computed strictly on the `100`-instance `val` split) over **11 grid values** $\gamma \in \{0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00\}$.
3. **`Uniform-Pinball(tau)`:** Elementwise asymmetric pinball loss $\rho_\tau(W - \hat{W})$ over **10 grid values** $\tau \in \{0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95\}$ (`0` offline train-label solves, `0` in-loop train solves).
4. **`ODECE(alpha)` (Official 7-$\alpha$ sweep):** Exact `official_odece_repo/src/odece.py` loss (`Softplus(beta=5)`, `margin_threshold=2.0`, `clip_grad_norm_(0.5)`) across **all seven official $\alpha \in \{0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2\}$** (`900` offline train-label solves + `18,000` in-loop train solves per $\alpha$).
   - **Pre-run One-Batch Gradient Parity Check:** Before training begins, verify analytic `ODECE` gradient against central finite differences (`eps=1e-6`, `max_abs_err < 1e-6`) AND against exact `src/odece.py` equations on batch 0 (recording exact parity JSON receipt).

## 3. Exact Metrics, Strict 0–1 Feasibility & Official Penalty `1.0`
For every candidate binary decision $\hat{x} \in \{0, 1\}^{50}$ evaluated against **ORIGINAL UNROUNDED `float64` true `(W_true, cap_true, costs_true)`**:
1. **Strict 0–1 Feasibility (`strict_01_infeasibility_rate`):** $\hat{x}$ is strictly 0–1 feasible iff $\hat{x} \in \{0,1\}^{50}$ and $(W_{\text{true}} \hat{x})_d \le \text{cap}_{\text{true}, d}$ for all $d \in \{0,1,2\}$ (exact unrounded `float64`, zero tolerance padding!).
2. **Official Fractional-Repair Surrogate Post-Hoc Regret (`official_frac_surrogate_posthoc_regret`):** Clearly labeled **surrogate** matching `kpsolver.py` lines 81–88 (`x_frac = x_hat / max_tau`, NOT integer 0–1) and `src/pfl.py` lines 333–343, evaluated at **primary official `penalty = 1.0`** (from `kpdataset.py` line 26) AND **secondary `penalty = 0.21`** from the exact same decisions!
3. **True Strict 0–1 Integer-Repair Post-Hoc Regret (`strict_01_int_repair_posthoc_regret`):** When $\hat{x}$ is infeasible, greedily remove selected items ($x_j = 1$) minimizing $c_j / \sum_{d: \text{viol}_d > 0} (W_{\text{true}, d, j} / \text{cap}_{\text{true}, d})$ until $x_{\text{int}} \in \{0,1\}^{50}$ satisfies strict unrounded $(W_{\text{true}} x_{\text{int}})_d \le \text{cap}_{\text{true}, d}$ (`assert` verified on 100% of instances!), then compute `(true_obj - corr_obj)/true_obj + penalty * |real_obj - corr_obj|/true_obj` at **both `penalty = 1.0` and `penalty = 0.21`**!
4. **Feasible-Only Regret (`strict_01_feasible_regret`):** Mean regret strictly over strictly 0–1 feasible instances (reported alongside count `n_feasible / 500`).

## 4. Matched Validation-Pinned Selection Policy (Zero Test-Based Choice!)
Every method family selects its single confirmatory model **STRICTLY on the 100-instance validation split (`val`)** for three pre-registered policies (never peeking at test!):
- **`P_unconstrained`:** Minimize val `official_frac_surrogate_posthoc_regret(p=1.0)` (and separately report selection by val `strict_01_int_repair_posthoc_regret(p=1.0)`).
- **`P_le10pct`:** Minimize val `official_frac_surrogate_posthoc_regret(p=1.0)` subject to `val strict_01_infeasibility_rate <= 0.10` (fallback if none qualifies: lowest val infeasibility, tie-broken by lowest val post-hoc regret).
- **`P_le5pct`:** Minimize val `official_frac_surrogate_posthoc_regret(p=1.0)` subject to `val strict_01_infeasibility_rate <= 0.05` (same fallback).

## 5. Solver Accounting, Exact Statuses, Quantization Audit & HiGHS Cross-Verification
- **Training/val/test solver (`OR-Tools CP-SAT`, `_SCALE = 10000`, `14` workers):** Explicitly log and persist exact counts of `OPTIMAL`, `FEASIBLE` (timeout/non-optimal — NEVER labeled exact!), `INFEASIBLE`, `UNKNOWN`, plus `quantization_violation_count` (cases where CP-SAT's quantized `W_hat` solution violates unrounded `W_hat @ x <= cap`).
- **Unrounded `float64` `HiGHS 1.16.0` Exact Cross-Audit:** For **100% of the validation-pinned confirmatory test models** (across `MSE+ValShift`, `Uniform-Pinball`, `ODECE` under `P_unconstrained`, `P_le10pct`, `P_le5pct`), ALSO re-solve the `500` held-out test instances directly in unrounded `float64` **`HiGHS 1.16.0`** (`mip_rel_gap=1e-4`, `time_limit=5.0`) and record exact HiGHS `kOptimal` / `kTimeLimit` counts, integrality error, and exact CP-SAT vs HiGHS metric delta!
- **Separate + End-to-End Cost Accounting:** Record `offline_oracle_label_solves` (and time), `inloop_train_solves` (and time), `val_selection_solves` (and time), `test_eval_solves` (and time), and `end_to_end_train_plus_val_solves` + `wall_time_s`, asserting exact parity between emitted logs and actual solver call counters.
- **Incremental Persistence:** After **EVERY** completed arm (including each individual `ODECE` $\alpha$), append to `stage1a_seed12_incremental.jsonl` and write per-instance 500-test outcomes to `stage1a_seed12_per_instance/<arm>.json` so partial runs remain fully interpretable. No superiority claim until all 7 matched `ODECE` arms finish.
