# Route Selection, Official Benchmark Audit & Literature Overlap (`dfl_constraints_dual_pinball_20261124`)

**Date:** 2026-11-24  
**Workflow Provenance:** 100% native workflow (direct browser read on `arxiv.org`, native web search, direct `git clone` of Apache-2.0 official repo; zero local skills invoked).

---

## 1. Official Benchmark & Verified Open License
- **Repository:** `https://github.com/JayMan91/OdeceDFLforConstraintsNeurips25` (Mandi, Defresne, Berden & Guns, NeurIPS 2025, `arXiv:2510.04951`), pinned at commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`.
- **Verified License:** **Apache License 2.0** (`official_odece_repo/LICENSE`).
- **Benchmark selected for Stage 0:** Official **3D 0-1 Multi-Dimensional Knapsack — Weight Prediction (`MDKP-Weights`)** from `MDKP_WeightExp.sh` / `KnapsackWeightExp.py` / `OptProblems/knapsack/kpdata.py`:
  - `num_items = 50`, `dim = 3`, `num_feat = 10`, `deg = 6` (severe polynomial misspecification), `noise_width = 0.25`, `capacity_ratio = [0.18, 0.20, 0.22]`.
  - Total instances per seed: `1,500` (`900` train / `100` val / `500` held-out test).
  - *Note on Brass Alloy dataset:* `JayMan91/OdeceBrassAlloy` on Hugging Face had `cardData: None` (no explicit SPDX license tag on the HF card), so we intentionally avoid it for Stage 0 and use the 100% self-contained Apache-2.0 `MDKP-Weights` benchmark.
- **Code audit observation on official `KnapsackWeightExp.py` & `KnapsackCapaExp.py`:**
  In `official_odece_repo/KnapsackWeightExp.py` (lines 77–83) and `KnapsackCapaExp.py` (lines 69–75), `train_test_split` splits only `(X, w)` while passing unsplit `(capacity, costs)` to all three `knapsack_dataset(...)` constructors (for `KnapsackCapaExp.py`, this actually decouples `X` from the predicted target `capacity` and reuses `capacity[0:500]` across train and test!). In our clean benchmark harness, we split **all four arrays `(X, w, capacity, costs)` jointly** with the exact same index permutation so train (`900`), val (`100`), and held-out test (`500`) are 100% disjoint with zero leakage.

---

## 2. Closest Primary Papers & Specific Gap
1. **Mandi, Defresne, Berden & Guns (NeurIPS 2025, `arXiv:2510.04951`) — `ODECE`:**
   - Trains a linear predictor $\hat{W} = f_\theta(X)$ via `loss = alpha * L_IAL + (1 - alpha) * L_OPL` (`src/odece.py` lines 75–151, `Softplus(beta=5)`, `margin_threshold = 2.0`), requiring an **exact NP-hard 0-1 ILP solve on every training instance every epoch** (`_batchsolve`: 18,000 ILPs over 20 epochs!).
   - **Specific Gap:** Compares `ODECE` only against symmetric `MSE` (`PFL`), `CombOptNet`, `SFL`, and `2sPtO`. Never evaluates **strong normalized solver-free asymmetric baselines**: (i) `MSE + Val-Shift(gamma)` (shifting `MSE` predictions in the feasible monotone direction by $\gamma \hat{\sigma}_{\text{val}}$ calibrated on `val`), or (ii) `Uniform-Pinball(tau)` (asymmetric quantile regression), nor (iii) **offline-solution-weighted constraint-level Pinball (`SW-Pinball`)** which uses the offline optimal training solutions $x_i^*$ **without calling the ILP solver inside the training loop**!
2. **Im, Benslimane & Grigas (May 2025, `arXiv:2505.22881`) — `SPO-RC+`:**
   - Focuses on predicting *objective* coefficients $c$ given a fixed conformal uncertainty set $\mathcal{U}(x)$ for constraints (not end-to-end training of constraint-matrix predictors under known $c$).
3. **Hu, Lee & Lee (NeurIPS 2023) — `2sPtO`; Nguyen, Gust & Le (Sep 2026, `arXiv:2609.32465`) — `PolyStepOR`; Zheng et al. (Nov 2026, `arXiv:2611.09560`):**
   - None benchmark `ODECE` on its own official `MDKP-Weights` benchmark against validation-shifted `MSE`, `Uniform-Pinball`, or offline-solution-weighted constraint-level `SW-Pinball`.

---

## 3. Mathematical Mechanism: Offline-Solution-Weighted Constraint-Level Pinball (`SW-Pinball`)
For packing constraint $W x \le b$ ($W \in \mathbb{R}_+^{D \times n}$, $x \in \{0,1\}^n$) with known costs $c$ and offline optimal training solutions $x^*$ (computed once before training, identical supervision to `ODECE`):
- Feasibility is **monotone** in $W$: over-predicting $W_{d,j}$ ($\hat{W}_{d,j} \ge W_{d,j}$) preserves feasibility of $\hat{x}$ with respect to true $W$, while under-predicting causes constraint violation.
- Under `deg=6` nonlinear misspecification with a linear model $f_\theta(X) \in \mathbb{R}^{D \times n}$, elementwise `Uniform-Pinball` $\frac{1}{Dn}\sum_{d,j} \rho_\tau(W_{d,j} - \hat{W}_{d,j})$ weights all $n=50$ items equally even though only ~$20\%$ are active ($x_j^* = 1$) in the optimal knapsack!
- **Proposed `SW-Pinball(tau)` (convex in $\hat{W}$, ZERO ILP solves during training):**
  $$\mathcal{L}_{\text{SW}}(\hat{W}; W, x^*) = \underbrace{\frac{1}{D}\sum_{d=1}^D \frac{1}{\|x^*\|_1} \rho_\tau\!\left(\sum_{j=1}^n (W_{d,j} - \hat{W}_{d,j}) x_j^*\right)}_{\text{exact active-bundle constraint-level pinball}} \;+\; \lambda_{\text{item}} \underbrace{\frac{1}{Dn}\sum_{d=1}^D \sum_{j=1}^n \rho_\tau(W_{d,j} - \hat{W}_{d,j})}_{\text{item-level safety pinball (prevents false selection of } x_j^*=0\text{)}},$$
  where $\rho_\tau(u) = \max(\tau u, (\tau - 1) u)$ with $\tau \in [0.5, 0.99]$ penalizes under-prediction ($W > \hat{W}$, $u > 0$) by $\tau$ and over-prediction ($u < 0$) by $1 - \tau$.
  - **Training cost:** $O(B \cdot D \cdot n)$ per batch — **zero ILP solves inside the training loop**!
