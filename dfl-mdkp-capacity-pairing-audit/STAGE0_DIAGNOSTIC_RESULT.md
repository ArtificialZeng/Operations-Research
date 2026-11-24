# Stage-0 Cheap Falsifier Result (`dfl_constraints_dual_pinball_20261124`)

**Date:** 2026-11-24  
**Verdict:** **STAGE-0 PASS (Path 2 — Strong Solver-Free Normalized Baseline Audit); Path 1 (`SW-Pinball` over `Uniform-Pinball` at $\le 10\%$ infeasibility) NOT confirmed.**  
**Benchmark:** Official Apache-2.0 NeurIPS 2025 `MDKP-Weights` (`genWeights` from `JayMan91/OdeceDFLforConstraintsNeurips25` commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`), official `MDKP_WeightExp.sh` settings (`num_items=50`, `dim=3`, `num_feat=10`, `deg=6`, `noise_width=0.25`, `penalty=0.21`), seed `11`, genuine disjoint split of all 4 arrays (`900 train / 100 val / 500 held-out test`; official seeds `12..15` remain untouched for Stage 1).  
**Exact Open-Source MIP Solver:** `OR-Tools CP-SAT` (`14` workers, cross-checked against `HiGHS 1.16.0` exact MIP on 10 test instances: max relative objective difference `1.73e-15`).  
**Sealed Artifacts:**
- `STAGE0_PROTOCOL.md` sha256 `3ec85d5fe838ae002b8c5059a674478aaeffd778221ac537882a782921cf5dc1`
- `stage0_mdkp_falsifier.py` sha256 `11b9599c164052f3372934f71ac42ddfaf5c728f72c9545dfe37273d5521db74`
- `stage0_mdkp_results.json` sha256 `cbdd69a4625f312df8e4b74b47aeb3df1db03af5b66f50a503836f535f8557c4`

---

## 1. Held-Out Test Pareto Results (`500` Test Instances, `penalty = 0.21`, Exact Same `10 -> 150` Linear Model & Adam `lr=0.05`, `20` Epochs)

| Method | Infeasibility | Post-Hoc Regret | Feasible Regret | Train Wall Time | Train ILP Solves |
|---|---:|---:|---:|---:|---:|
| `MSE` (official PFL baseline) | 35.8% | 6.760% | 6.518% | 0.024 s | 0 |
| `MSE + ValShift(g=0.25)` | 19.6% | 8.695% | 8.980% | 0.024 s | 0 |
| `MSE + ValShift(g=0.50)` | 10.2% | 11.122% | 11.475% | 0.024 s | 0 |
| `MSE + ValShift(g=0.75)` | 5.8% | 13.605% | 14.004% | 0.024 s | 0 |
| `MSE + ValShift(g=1.00)` | 3.2% | 16.110% | 16.377% | 0.024 s | 0 |
| `MSE + ValShift(g=1.50)` | 0.6% | 20.814% | 20.887% | 0.024 s | 0 |
| `MSE + ValShift(g=2.00)` | 0.0% | 25.038% | 25.038% | 0.024 s | 0 |
| **`Uniform-Pinball(t=0.50)`** | 46.2% | **5.450%** | 4.750% | **0.028 s** | **0** |
| **`Uniform-Pinball(t=0.65)`** | **14.8%** | **8.211%** | **8.307%** | **0.028 s** | **0** |
| **`Uniform-Pinball(t=0.75)`** | **6.6%** | **11.216%** | **11.428%** | **0.028 s** | **0** |
| **`Uniform-Pinball(t=0.85)`** | **1.8%** | **16.052%** | **16.194%** | **0.028 s** | **0** |
| **`Uniform-Pinball(t=0.90)`** | **0.0%** | **20.036%** | **20.036%** | **0.028 s** | **0** |
| `SW-Pinball(t=0.65)` | 64.0% | **5.205%** | 3.701% | 0.039 s | 0 |
| `SW-Pinball(t=0.85)` | 18.0% | 8.798% | 9.042% | 0.040 s | 0 |
| `SW-Pinball(t=0.90)` | 9.0% | 11.817% | 12.255% | 0.040 s | 0 |
| `SW-Pinball(t=0.95)` | 0.8% | 18.738% | 18.810% | 0.039 s | 0 |
| `ODECE(alpha=0.2)` (official formulation) | 97.4% | 7.075% | 1.947% | 88.85 s | 18,000 |
| `ODECE(alpha=0.5)` (official formulation) | 16.4% | 8.466% | 8.321% | 101.34 s | 18,000 |
| `ODECE(alpha=0.8)` (official formulation) | 3.8% | 15.112% | 15.181% | 106.42 s | 18,000 |

---

## 2. Key Stage-0 Findings
1. **Path 2 PASS — Solver-Free `Uniform-Pinball` Matches/Dominates `ODECE` Across the Entire Held-Out Test Frontier at ~3,600× Lower Training Time:**
   - **Balanced point:** `Uniform-Pinball(0.65)` (`0.028 s`, `0` ILPs) **strictly Pareto-dominates** `ODECE(0.5)` (`101.34 s`, `18,000` ILPs) on all three metrics simultaneously: infeasibility **`14.8%` vs `16.4%`**, post-hoc regret **`8.211%` vs `8.466%`**, feasible regret **`8.307%` vs `8.321%`** (**3,619× faster training**).
   - **Low-feasibility point:** `Uniform-Pinball(0.50)` (`46.2%` infeas, `5.450%` post-hoc) strictly dominates `ODECE(0.2)` (`97.4%` infeas, `7.075%` post-hoc).
   - **High-feasibility point:** Interpolating `Uniform-Pinball` between `t=0.75` (`6.6%`, `11.216%`) and `t=0.85` (`1.8%`, `16.052%`) gives ~`14.04%` post-hoc regret at `3.8%` infeasibility, outperforming `ODECE(0.8)` (`3.8%`, `15.112%`, `106.42 s`).
2. **`Uniform-Pinball` Strictly Beats `MSE + Val-Shift` Across the Whole Frontier (Slope Adaptation Under Heteroscedastic Misspecification):**
   - At `0.0%` infeasibility, `Uniform-Pinball(0.90)` achieves **`20.036%`** post-hoc regret vs `MSE + ValShift(2.00)`'s **`25.038%`** (**5.00 percentage points lower**). At `~6%` infeasibility, `Uniform-Pinball(0.75)` (`6.6%`, `11.216%`) beats `MSE + ValShift(0.75)` (`5.8%`, `13.605%`) by **2.39 pp**. Under `deg=6` polynomial misspecification, linear conditional quantile regression adapts both slope and intercept to right-skewed heteroscedastic tails, whereas homoscedastic validation-shift only adjusts the intercept.
3. **Honest Negative on `SW-Pinball` at High Feasibility (Path 1 NOT confirmed):**
   - While `SW-Pinball(0.65)` achieved the lowest overall post-hoc regret (`5.205%` at `64.0%` infeas), at `<= 10%` infeasibility `Uniform-Pinball(0.75)` (`6.6%`, `11.216%`) outperformed `SW-Pinball(0.90)` (`9.0%`, `11.817%`). Over-weighting $x^*$ under-protects unselected items ($x_j^* = 0$) from under-prediction and false selection.

## 3. Implementation Scope Note & Stage-1 Plan (Before Scaling)
- `ODECE` in `stage0_mdkp_falsifier.py` is a faithful NumPy+Adam implementation matching `official_odece_repo/src/odece.py` lines 75–151 & 239–251 with `OR-Tools CP-SAT` (verified against `HiGHS` to `1.73e-15`). Before any publication claim, Stage 1 must:
  1. Cross-verify one seed directly against PyTorch `ODECE` from `official_odece_repo` (replacing only `gurobipy` with `CP-SAT`/`HiGHS`),
  2. Run confirmatory evaluation on the **sealed untouched official seeds `12, 13, 14, 15`** across `MDKP-Weights` and `MDKP-Capacity` (fixing the `train_test_split` alignment bug documented in `SELECTION_AND_OVERLAP.md`),
  3. Add a **non-monotone constraint boundary test** (where monotone quantile regression should lose its structural advantage) and a `deg in {1, 2, 4, 6}` misspecification sweep to characterize the exact regime boundary.
