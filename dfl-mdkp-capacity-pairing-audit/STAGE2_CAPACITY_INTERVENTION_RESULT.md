# Stage-2a & Stage-2b Controlled Intervention Report: Upstream Indexing Defect on `MDKP-Capacity` (`dfl_constraints_dual_pinball_20261124`)

**Date:** 2026-11-24  
**Protocols:** [STAGE2A_CAPACITY_PAIRING_PROTOCOL.md](STAGE2A_CAPACITY_PAIRING_PROTOCOL.md) (supervised fixed-clean-target diagnostic, 0 MIPs) & [STAGE2B_CAPACITY_INTERVENTION_PROTOCOL.md](STAGE2B_CAPACITY_INTERVENTION_PROTOCOL.md) (bounded downstream controlled intervention, 0 training MIPs, no all-alpha `ODECE` retraining)  
**Regime:** Published `official_odece_repo/MDKP_CapaExp.sh` (`genCapacity`, `num_items=50, dim=3, num_feat=10, deg=6, noise_width=0.25, lr=0.005, bs=32, max_epochs=20`, all 5 published seeds `11, 12, 13, 14, 15`, exact `sklearn.model_selection.train_test_split` indices `900 train / 100 val / 500 test`, commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`).  
**Scope & Causal Label:** Strictly a **controlled intervention** isolating the effect of changing **ONLY training capacity labels** (`capacity[idx_tr]` vs. upstream unsplit `capacity[:900]` from `KnapsackCapaExp.py:L69-73`) on **identical clean held-out test contexts, true constraints, costs, shared constant-mean baseline, and clean validation risk calibration**. This is **NOT** a claim about published downstream method rankings.

> **Explicit Stage-2a Gate Deviation Disclosure:** The raw boolean gate pre-registered in `STAGE2A_CAPACITY_PAIRING_PROTOCOL.md` (`gate_to_stage2b_pass`) evaluated to **`False`** (`stage2a_capacity_pairing_results.json:L12`) because: (1) published `Adam-MSE(lr=0.005, 20ep)` suffered severe under-convergence, giving `min delta OOS R^2 = +0.1461` (`< 0.25`) and `max p = 3.86e-05` (`> 1e-10`), and (2) `OLS` Seed `15` had `p = 2.78e-08` (`> 1e-10`), even though `OLS` beat mispaired labels on `5/5` seeds with `min delta OOS R^2 = +0.4354`. Accordingly, Stage-2b below is explicitly labeled a **post-deviation predeclared exploratory downstream controlled intervention** (whose policies and evaluation protocol were locked in `STAGE2B_CAPACITY_INTERVENTION_PROTOCOL.md` prior to generating any downstream MIP outputs). Stage-2b protocol, script, and result JSON are sealed byte-for-byte.

---

## 1. Stage-2a: Fixed-Clean-Target Supervised Pairing Diagnostic (0 MIPs, 5 Published Seeds)

Every arm is evaluated on the **exact same clean test `(X[idx_te], capacity[idx_te])`** and **exact same shared constant-mean baseline** (`capacity[idx_tr].mean(axis=0)`).

| Seed | Shared Mean MSE | `OLS-Clean` MSE (`OOS R^2`) | `OLS-Mispaired` MSE (`OOS R^2`) | `OLS` $\Delta \text{OOS } R^2$ (Wilcoxon $p$) | `AdamMSE-Clean` MSE (`OOS R^2`) | `AdamMSE-Mispaired` MSE (`OOS R^2`) | `Adam` $\Delta \text{OOS } R^2$ (Wilcoxon $p$) |
|---|---:|---:|---:|---:|---:|---:|---:|
| 11 | 10.284 | **4.565** (`+0.5561`) | 10.030 (`+0.0247`) | `+0.5314` (`7.37e-51`) | **11.557** (`-0.1238`) | 16.539 (`-0.6083`) | `+0.4844` (`2.92e-35`) |
| 12 | 8.664 | **3.459** (`+0.6007`) | 9.023 (`-0.0415`) | `+0.6422` (`1.29e-52`) | **15.820** (`-0.8260`) | 17.086 (`-0.9721`) | `+0.1461` (`3.86e-05`) |
| 13 | 8.380 | **3.579** (`+0.5729`) | 8.477 (`-0.0116`) | `+0.5845` (`8.37e-42`) | **12.959** (`-0.5464`) | 16.245 (`-0.9385`) | `+0.3921` (`3.19e-19`) |
| 14 | 10.686 | **4.876** (`+0.5437`) | 10.453 (`+0.0217`) | `+0.5220` (`4.14e-45`) | **15.333** (`-0.4349`) | 18.726 (`-0.7525`) | `+0.3176` (`1.87e-19`) |
| 15 | 5.458 | **3.184** (`+0.4167`) | 5.560 (`-0.0187`) | `+0.4354` (`2.78e-08`) | **16.038** (`-1.9383`) | 17.435 (`-2.1943`) | `+0.2560` (`3.62e-05`) |
| **5-Seed Mean $\pm$ SD** | `8.694 ± 2.078` | **`3.932 ± 0.741`** (`+0.5380 ± 0.0711`) | `8.709 ± 1.927` (`-0.0051 ± 0.0281`) | **`+0.5431`** (`5/5` seeds) | **`14.342 ± 1.982`** (`-0.7739 ± 0.6978`) | `17.206 ± 0.968` (`-1.0931 ± 0.6329`) | **`+0.3192`** (`5/5` seeds) |

**Two Distinct Findings from Stage-2a:**
1. **Training-label mispairing completely destroys linear target signal (5/5 seeds):** Converged `OLS-Clean` explains `53.8%` of out-of-sample variance above the shared mean (`OOS R^2 = +0.5380 ± 0.0711`), whereas `OLS-Mispaired` collapses to **`OOS R^2 = -0.0051 ± 0.0281`** (pure zero signal; indistinguishable from constant train mean, `899–900 / 900` training rows misaligned). *(Additional data note: on Seed `12`, dimension `2` of `capacity` is constant at the upper clip `25.0` across all 500 test instances.)*
2. **Orthogonal published-hyperparameter under-convergence (`MDKP_CapaExp.sh` `lr=0.005, 20ep`):** With unstandardized `X in [0, 25]` and zero bias init (`TorchML.py:L57-62`), `Adam-MSE(lr=0.005, 20ep)` is severely under-converged on 5/5 seeds — even with clean labels (`OOS R^2 = -0.7739`, worse than constant mean), though clean labels still outperform mispaired labels on 5/5 seeds (`-2.86` MSE, $\Delta \text{OOS } R^2 = +0.3192$, max $p = 3.86 \times 10^{-5}$).

---

## 2. Stage-2b: Bounded Downstream Controlled Intervention (`27,500 / 27,500 kOptimal` Unrounded `float64` `HiGHS 1.16.0`)

All held-out test evaluations (`500` offline true OPT + `5` raw plug-in + `5` val-pinned models per seed across 5 seeds = **`27,500 / 27,500 kOptimal`** HiGHS `float64`, `max_mip_gap = 1.00e-4`, `max_integrality_err = 3.66e-10`; plus `28,000` CP-SAT clean validation solves; total wall time `363.7 s`). Both Clean and Mispaired arms receive identical **clean validation** risk calibration (`P_le10pct_frac_p1`, $\hat{b}_\gamma = \max(\hat{b} - \gamma \hat{\sigma}_{\text{val}}, 0)$) to isolate training-label mispairing at matched target risk.

### 2A. Prespecified `ValPinned_le10pct` Policy — Per-Seed & 5-Seed Summary (Official `penalty = 1.0`)
| Seed | `OLS-Clean` (`g*`: inf / `frac_p1` / `int_p1`) | `OLS-Mispaired` (`g*`: inf / `frac_p1` / `int_p1`) | `SharedMean` (`g*`: inf / `frac_p1` / `int_p1`) | `AdamMSE-Clean` (`g*`: inf / `frac_p1` / `int_p1`) | `AdamMSE-Mispaired` (`g*`: inf / `frac_p1` / `int_p1`) |
|---|---|---|---|---|---|
| 11 | `1.50`: **7.8%** / **21.46%** / **22.33%** | `1.25`: 10.2% / 24.37% / 25.65% | `1.25`: 12.2% / 24.16% / 25.83% | `1.50`: **5.6%** / **32.32%** / **32.76%** | `1.25`: 8.8% / 33.80% / 34.31% |
| 12 | `1.50`: 15.0% / **12.87%** / **13.44%** | `2.00`: **8.2%** / 29.50% / 29.82% | `2.00`: 9.2% / 27.65% / 27.82% | `1.25`: **10.2%** / **22.95%** / **23.34%** | `1.25`: 13.4% / 23.06% / 23.53% |
| 13 | `2.00`: **3.4%** / **17.58%** / **17.90%** | `2.00*`: 6.2% / 30.89% / 31.22% | `2.00*`: 5.6% / 30.97% / 31.28% | `1.25`: 8.0% / **20.06%** / **20.48%** | `1.50`: **7.2%** / 27.42% / 27.86% |
| 14 | `2.00`: **8.6%** / **16.81%** / **17.37%** | `2.00*`: 12.0% / 27.37% / 27.71% | `2.00*`: 12.0% / 28.34% / 28.65% | `1.50`: **10.8%** / **24.93%** / **25.29%** | `1.50`: 12.2% / 27.92% / 28.26% |
| 15 | `2.00`: **15.0%** / **13.16%** / **13.78%** | `2.00*`: 19.6% / 18.61% / 18.54% | `2.00*`: 18.4% / 18.67% / 18.66% | `1.25`: 13.6% / **20.07%** / **20.41%** | `1.50`: **9.0%** / 23.88% / 24.15% |
| **5-Seed Mean $\pm$ SD** | **`9.96 ± 5.01%`** / **`16.377 ± 3.540%`** / **`16.962 ± 3.618%`** | `11.24 ± 5.15%` / `26.147 ± 4.876%` / `26.589 ± 4.969%` | `11.48 ± 4.70%` / `25.958 ± 4.745%` / `26.447 ± 4.774%` | `9.64 ± 3.01%` / `24.065 ± 5.052%` / `24.454 ± 5.076%` | `10.12 ± 2.58%` / `27.215 ± 4.248%` / `27.624 ± 4.301%` |

*(`*` indicates validation fallback triggered at max shift `g=2.00` because `val_infeas > 10%`: `OLS-Mispaired` and `SharedMean` failed `val_infeas <= 10%` on 3/5 seeds, whereas `OLS-Clean` qualified on 5/5 seeds.)*

### 2B. Paired Downstream Uncertainty (`ValPinned_le10pct` & `Raw_Plugin`, HiGHS `float64`)
> **Uncertainty Label:** All pooled `n = 2,500` confidence intervals and p-values below are strictly **conditional on the five fitted seed pairs (`11–15`)**.

| Policy | Comparison (`A - B`) | Scope | `frac_p1` Diff [95% CI] (Wilcoxon $p$) | `int_p1` Diff (Wilcoxon $p$) | Realized Strict 0–1 Infeas Diff (McNemar $p$) |
|---|---|---|---:|---:|---:|
| **`ValPinned_le10pct`** | `OLS-Clean - OLS-Mispaired` | **Cond. pooled (`n=2500`)** | **`-9.770 pp`** `[-10.248, -9.298]` (`1.05e-230`) | **`-9.627 pp`** (`4.00e-235`) | **`-1.28 pp`** (`p=4.07e-02`) |
| **`ValPinned_le10pct`** | `OLS-Clean - OLS-Mispaired` | Per-seed range (`5/5` lower regret, `4/5` lower risk) | `-2.90` to `-16.63 pp` (max `p=7.30e-06`) | `-3.33` to `-16.38 pp` (max `p=2.15e-07`) | `-4.60` to `-2.40 pp` (Seeds `11,13,14,15`); `+6.80 pp` (Seed `12`) |
| **`ValPinned_le10pct`** | `OLS-Clean - SharedMean` | **Cond. pooled (`n=2500`)** | **`-9.581 pp`** `[-10.056, -9.110]` (`2.47e-227`) | **`-9.485 pp`** (`3.92e-231`) | **`-1.52 pp`** (`p=1.74e-02`) |
| **`ValPinned_le10pct`** | `AdamMSE-Clean - AdamMSE-Mispaired` | **Cond. pooled (`n=2500`)** | **`-3.150 pp`** `[-3.540, -2.766]` (`3.30e-82`) | **`-3.170 pp`** (`5.97e-84`) | `-0.48 pp` (`p=4.34e-01`) |
| **`ValPinned_le10pct`** | `AdamMSE-Clean - AdamMSE-Mispaired` | Per-seed range (`5/5` lower mean regret) | `-0.11` (`p=0.367`, Seed `12`) to `-7.36 pp` (`6.92e-59`) | `-0.19` to `-7.38 pp` | `-3.20` to `+4.60 pp` (Seed `15` `+4.60 pp` risk) |
| `Raw_Plugin (g=0)` | `OLS-Clean - OLS-Mispaired` | **Cond. pooled (`n=2500`)** | **`-7.174 pp`** `[-7.743, -6.617]` (`9.95e-112`) | **`-4.826 pp`** (`2.80e-55`) | `+13.52 pp` (`4.80e-33`) *(uncalibrated)* |
| `Raw_Plugin (g=0)` | `AdamMSE-Clean - AdamMSE-Mispaired` | **Cond. pooled (`n=2500`)** | **`-3.803 pp`** `[-4.250, -3.358]` (`6.69e-48`) | **`-3.077 pp`** (`1.87e-46`) | **`-3.20 pp`** (`3.40e-05`) |

---

## 3. Key Controlled-Intervention Takeaways & SHA-256 Receipts

1. **Direct causal impact of upstream training-label mispairing on clean downstream decisions:** Even when given clean validation calibration and evaluated on identical clean constraints/costs, training a converged linear capacity predictor on upstream mispaired labels (`capacity[:900]`) destroys `100%` of covariate signal (`OLS-Mispaired` matches constant `SharedMean`: `26.15%` vs `25.96%` frac_p1) and inflates downstream regret by **`+9.77 pp` (`16.38%` -> `26.15%`)** while worsening realized infeasibility (`9.96%` -> `11.24%`, 4/5 seeds worse on both regret and risk).
2. **Compounding under-convergence in published `MDKP_CapaExp.sh` (`lr=0.005, 20ep`):** Even with clean labels, `AdamMSE-Clean` lags `OLS-Clean` by `+7.69 pp` (`24.07%` vs `16.38%`), and stacking training-label mispairing adds another `+3.15 pp` (`27.22%`, total `+10.84 pp` above `OLS-Clean` at ~`10%` risk).
3. **Strict scope discipline:** These controlled interventions quantify the impact of the indexing defect (and `lr=0.005` under-convergence) on supervised predictors; we make **no claim** about how published relative rankings among DFL methods (`ODECE`, `CombOptNet`, `SFL`, `MSE`) would shift without a separate, explicitly justified multi-method capacity benchmark.

### Stage-2a & Stage-2b SHA-256 Receipts
- [STAGE2A_CAPACITY_PAIRING_PROTOCOL.md](STAGE2A_CAPACITY_PAIRING_PROTOCOL.md) (`3,639 B`): `ab8914faf63a8f15781a6d1ddda8603dcb02e6139851ef4201a5f72a82b9de78`
- [stage2a_capacity_pairing_test.py](stage2a_capacity_pairing_test.py) (`12,895 B`): `5be2487b90c3c529d17fe8620b9ffd8eeebfe8e4f2e4f61850fc994730a7bf14`
- [stage2a_capacity_pairing_results.json](stage2a_capacity_pairing_results.json) (`16,790 B`): `8a0c8dd81241fe91d8a1d636db34b4ec37d527b904bad51e5021d97cb13cdf6b`
- [STAGE2B_CAPACITY_INTERVENTION_PROTOCOL.md](STAGE2B_CAPACITY_INTERVENTION_PROTOCOL.md) (`4,889 B`): `92f4d2254a5a933261bfe38e4495560ef7b186850e030c361edc70954e379b16`
- [stage2b_capacity_downstream_intervention.py](stage2b_capacity_downstream_intervention.py) (`26,335 B`): `855620aed9426270b9496bed47aa3bfb61220fb683a6278c68809fc639f17c24`
- [stage2b_capacity_downstream_results.json](stage2b_capacity_downstream_results.json) (`140,853 B`): `ccd9c27dfd35d887a314af3e6a49eb7d2aeacff8747563ab396a7de965bd90fe`
