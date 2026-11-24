# Stage-2b Locked Protocol: Bounded Downstream Controlled Intervention for `MDKP-Capacity` Training-Label Mispairing (`dfl_constraints_dual_pinball_20261124`)

**Status:** LOCKED BEFORE EXECUTION (2026-11-24)  
**Trigger:** Stage-2a ([stage2a_capacity_pairing_results.json](stage2a_capacity_pairing_results.json)) demonstrated a material, 5/5-seed consistent clean-target score degradation from upstream training-label mispairing (`OLS` clean `OOS R^2 = +0.5380 ± 0.0711` vs mispaired `-0.0051 ± 0.0281`, min $\Delta = +0.4354$, max per-seed Wilcoxon $p = 2.78 \times 10^{-8}$; published `Adam-MSE(lr=0.005, 20ep)` clean vs mispaired `5/5` seeds, mean $\Delta = +0.3192$, max $p = 3.86 \times 10^{-5}$, while also revealing severe under-convergence at `lr=0.005, 20ep` with negative `OOS R^2` even on clean labels).  
**Label & Scope Discipline:** This is strictly a **controlled downstream intervention** evaluating how upstream training-label mispairing (`KnapsackCapaExp.py:L69-73`) degrades downstream knapsack decisions on **identical clean held-out true constraints and costs**. It is **NOT** a claim about published method rankings, and executes **zero all-alpha `ODECE` retraining**.

---

## 1. Benchmark, Seeds & Identical Clean Ground-Truth Evaluation
- **Regime:** Published `MDKP-Capacity` (`genCapacity`, `num_items=50, dim=3, num_feat=10, deg=6, noise_width=0.25, fixed_cost=False`), exact `sklearn.model_selection.train_test_split` indices (`900 train / 100 val / 500 test`) across all **5 published seeds `s in {11, 12, 13, 14, 15}`** (`2,500` pooled held-out test instances).
- **Fixed Clean Evaluation Set (IDENTICAL across all arms):** `(X[idx_te], w[idx_te], capacity[idx_te], costs[idx_te])` evaluated against **original unrounded `float64` true constraints & costs**, with **100% of offline test true OPT (`2,500` MIPs) and 100% of every confirmatory test arm solved directly in unrounded `float64` `HiGHS 1.16.0`** (`mip_rel_gap=1e-4`, `time_limit=5.0`).
- **Metrics:** Official `penalty = 1.0` primary (`0.21` secondary from identical binary decisions):
  1. `strict_01_infeasibility_rate` (exact unrounded `(w_true @ x) <= cap_true` across all 3 dims)
  2. `official_frac_surrogate_posthoc` (clearly labeled fractional-scaling surrogate `sol / max_tau`, upstream `kpsolver.py:L81-88`)
  3. `strict_01_int_repair_posthoc` (true greedy 0–1 binary removal, `assert` verified strictly 0–1 feasible on 100% of instances)
  4. `strict_01_feasible_regret` (feasible-only regret alongside count `n/500`).

---

## 2. Controlled Training-Label Arms & Prespecified Validation Policy
Five predictors trained with **0 training MIPs** (no all-alpha ODECE retraining):
1. **`OLS-Clean`:** Closed-form OLS on clean `(X[idx_tr], capacity[idx_tr])`.
2. **`OLS-Mispaired`:** Closed-form OLS on mispaired `(X[idx_tr], capacity[:900])`.
3. **`AdamMSE-Clean`:** Published `LinearRegressionforKP_PredCapacity` (`Adam(lr=0.005, bs=32, 20ep)`) on clean `(X[idx_tr], capacity[idx_tr])`.
4. **`AdamMSE-Mispaired`:** Published `LinearRegressionforKP_PredCapacity` (`Adam(lr=0.005, bs=32, 20ep)`) on mispaired `(X[idx_tr], capacity[:900])`.
5. **`SharedMean`:** Constant baseline predicting `capacity[idx_tr].mean(axis=0)`.

Evaluated under two pre-registered decision policies (using predicted capacity clipped at `>= 0.0` so RHS is nonnegative):
- **Policy A (`Raw_Plugin`, `gamma = 0`):** Direct plug-in solve using raw predicted capacity $\hat{b}(X)$.
- **Policy B (`ValPinned_le10pct`, prespecified `P_le10pct_frac_p1` on identical clean validation split):** Conservative RHS shift $\hat{b}_\gamma(X) = \max(\hat{b}(X) - \gamma \hat{\sigma}_{\text{val}}, 0)$ over $\gamma \in \{0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00\}$, where $\hat{\sigma}_{\text{val}}$ is the per-dimension residual SD on clean `val` (`n=100`) and $\gamma^*$ minimizes clean-val `official_frac_surrogate_posthoc_p1` subject to clean-val `strict_01_infeasibility_rate <= 0.10` (fallback: lowest clean-val infeasibility). Giving both Clean and Mispaired identical clean-validation risk calibration isolates the pure downstream cost of **training-label mispairing** at matched target risk.

---

## 3. Paired Uncertainty & Reporting
- Report **per-seed (`n = 500`)** AND **5-seed aggregate** (5-seed mean $\pm$ SD, plus pooled `n = 2,500` paired differences explicitly labeled **conditional on the 5 fitted seed pairs**):
  - `OLS-Clean - OLS-Mispaired`
  - `OLS-Clean - SharedMean`
  - `AdamMSE-Clean - AdamMSE-Mispaired`
- Report `frac_p1`, `int_p1`, `frac_p021`, `int_p021` (95% paired bootstrap CI, Wilcoxon $p$) AND realized strict 0–1 infeasibility difference (95% CI, discordant counts, exact McNemar $p$), plus exact solver statuses (`kOptimal` / `OPTIMAL`), MIP gaps, integrality errors, and call parity.
