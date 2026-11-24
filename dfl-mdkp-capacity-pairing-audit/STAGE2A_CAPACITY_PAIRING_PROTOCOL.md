# Stage-2a Locked Protocol: Controlled Fixed-Clean-Target `MDKP-Capacity` Pairing Diagnostic (`dfl_constraints_dual_pinball_20261124`)

**Status:** LOCKED BEFORE EXECUTION (2026-11-24)  
**Scope:** Controlled supervised intervention testing the upstream indexing defect in `official_odece_repo/KnapsackCapaExp.py` lines 64–75 (commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`), where `train_test_split` splits only `(X, w)` while leaving target `capacity` unsplit (`capacity[0..899]` assigned to `train`, `capacity[0..99]` to `val`, `capacity[0..499]` to `test`). **Zero MIP solves required.** Explicitly labeled as a **controlled intervention**, NOT a claim about published downstream method rankings.

---

## 1. Exact Published Data Regime & Seeds
Matches `official_odece_repo/MDKP_CapaExp.sh` lines 3–10:
- Generator: `OptProblems.knapsack.kpdata.genCapacity` with `num_data = 1500` (`1000 + 500`), `num_features = 10`, `num_items = 50`, `dim = 3`, `deg = 6`, `noise_width = 0.25`, `fixed_cost = False`.
- Seeds: All 5 published seeds **`s in {11, 12, 13, 14, 15}`**.
- Split indices: Exact `sklearn.model_selection.train_test_split` splits from `KnapsackCapaExp.py` lines 69–70:
  - `idx_tr_full, idx_te = train_test_split(np.arange(1500), test_size=500, random_state=s)`
  - `idx_tr, idx_va = train_test_split(idx_tr_full, test_size=0.1, random_state=s)` (`900 train / 100 val / 500 test`).

---

## 2. Fixed Clean Evaluation Target & Controlled Training-Label Intervention
To eliminate any target-set mismatch between arms, **BOTH arms are evaluated on the EXACT SAME clean test set and shared baseline**:
- **Fixed Clean Test Contexts:** `X_te_clean = X[idx_te]` (`500 x 10`).
- **Fixed Clean Test Capacity Ground Truths:** `cap_te_clean = capacity[idx_te]` (`500 x 3`).
- **Shared Constant-Mean Baseline:** `y_bar_shared = capacity[idx_tr].mean(axis=0)` evaluated on `cap_te_clean` (`MSE_shared_mean` identical for both arms per seed).
- **Controlled Intervention (ONLY training capacity labels change; identical `X_tr_clean = X[idx_tr]`, identical architecture, identical seed/initialization, identical minibatch order):**
  1. **`CleanPair`:** Trained on `(X[idx_tr], capacity[idx_tr])`.
  2. **`MispairedUpstream`:** Trained on `(X[idx_tr], capacity[:900])` (exact `KnapsackCapaExp.py:L73` training target indexing).

---

## 3. Predictors & Paired Evaluation Metrics (0 MIP Solves)
Evaluated per seed (`n = 500`) and summarized across all 5 seeds:
1. **`Adam-MSE (Published)`:** Exact `LinearRegressionforKP_PredCapacity` (`10 -> 3`, Xavier uniform init, zero bias, MSE loss, `Adam(lr=0.005)`, `batch_size=32`, `max_epochs=20`, matching `MDKP_CapaExp.sh:L8`).
2. **`OLS (Closed-Form)`:** Exact global `MSE` minimizer with intercept (`np.linalg.lstsq`), ruling out learning-rate/epoch confounds.

Per-seed metrics on fixed `(X_te_clean, cap_te_clean)`:
- `test_mse`, `test_mae`, `test_r2` (vs test variance), `oos_r2_vs_shared_mean = 1 - test_mse / mse_shared_mean`, mean per-dimension Pearson $r$.
- Paired per-instance squared-error difference `SE_clean - SE_mispaired` (`n = 500` per seed): mean diff, 95% paired bootstrap CI (`10,000` resamples), Wilcoxon signed-rank $p$.

---

## 4. Gate to Proceed to Bounded Stage-2b Downstream Intervention
Proceed to Stage-2b (bounded downstream clean-test intervention with prespecified validation policy, NO all-alpha ODECE retraining) **if and only if** `CleanPair` outperforms `MispairedUpstream` on **5/5 seeds** with a material clean-score gap ($\Delta \text{OOS } R^2 \ge 0.25$ on every seed for both `Adam-MSE` and `OLS`, paired Wilcoxon $p < 10^{-10}$ on every seed).
