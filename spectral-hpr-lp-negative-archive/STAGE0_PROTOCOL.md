# Stage-0 Protocol: Executable Comparator & Cheap Failure Test (`spectral_hpr_lp_20261124`)

**Status:** LOCKED BEFORE IMPLEMENTATION (2026-11-24)  
**Purpose:** Fast, bounded, deterministic Stage-0 diagnostic designed to falsify `Spec-HPR` early if the theoretical Loewner/condition-number advantage fails to translate into real iteration and wall-clock speedups against strong published 2025–2026 comparators, or if slack-conversion overhead negates the gain on mixed-inequality LPs.

---

## 1. Exact Executable Comparators (Same Sparse Engine, Same Stopping Criteria)

All first-order methods are implemented in the exact same Python/NumPy/SciPy CSR+CSC sparse matrix engine (`float64`, single-threaded deterministic execution on CPU), evaluated on the **original unscaled LP KKT residuals** (`rel_p_res`, `rel_d_res`, `rel_gap` following `HPR-LP` / `cuPDLPx` standard relative criteria: $\le \text{tol}$ with primary $\text{tol} = 10^{-6}$ and secondary milestone $\text{tol} = 10^{-4}$), and independently verified against **HiGHS** (`highspy`, exact simplex/IPM reference optimal value $f^*$).

All methods receive the **exact same static diagonal preprocessing pipeline**: `Ruiz(10) -> Pock-Chambolle(alpha=1) -> bc normalization` (eqs. 24, 33–34 of `arXiv:2611.01872`), so any gain is strictly **above and beyond** strong diagonal preconditioning:

1. **`HPR-Native` (`r=0`, box-projection form):** Algorithm 2 of `HPR-LP` (`arXiv:2611.01872`, eqs. 4–5, 18–23) directly on $l_c \le Ax \le u_c, \; l_v \le x \le u_v$ with $\mathcal{T}_1^{(0)} = \lambda_A I_m - AA^*$ ($\lambda_A = 1.002 \|A\|_2^2$), adaptive restarts ($\alpha_1 = 0.2, \alpha_2 = 0.8, \alpha_3 = 0.36$), and adaptive penalty update $\sigma_{\text{cand}} = \Delta_x / \Delta_y$ (clamped/smoothed safeguard).
2. **`HPR-Slack` (`r=0`, equality-slack form):** Same `HPR-LP` Algorithm 2 on the slack-converted standard equality LP $\hat{A}\hat{x} = \hat{b}$ (with `Ruiz(10)->PC->bc` applied *after* slack insertion), isolating the pure slack-conversion effect vs. `HPR-Native` and the pure $\mathcal{T}_1^{(r)}$ vs. $\mathcal{T}_1^{(0)}$ effect against `Spec-HPR`.
3. **`cuPDLPx-ASB` (Reflected Halpern PDHG + PID primal weight + Active-Set Step Size Boost):** Follows `arXiv:2507.14051` and `mit-lu-lab.github.io/cuPDLPx/algorithm/step-size.html`: $\gamma = 1$, $\eta^0 = 0.998/\|A\|_2$, PID primal weight controller ($K_P = 0.3, K_I = 0.05, K_D = 0.05$ on log-ratio), fixed-point restart metric, plus Active-Set Step Size Boost (ASB) with exclusion tests, masked warm-started power iteration on $A_{B,F}$, step-size acceptance ($\alpha=0.9, \rho=1.1$), and divergence rollback ($\delta=0.05$, max 2 rollbacks). *(Note: for Stage-0 bounded runs of max 25,000 iters, we also use a shorter ASB trailing window `W=500` alongside default `10000` or note activation counts so ASB is given every fair chance to fire!)*
4. **`OnlineDiag-HPR` (Online Diagonal Preconditioning):** Applies Lu & Zhang (`arXiv:2506.17650`, normalized OGD diagonal updates on primal/dual step scales every $\phi=20$ iterations, tuned over $\text{lr} \in \{10^{-3}, 10^{-4}\}$ or fixed $\text{lr}=10^{-3}$ with AdaGrad) on top of Ruiz+PC-scaled Halpern PDHG.
5. **`Spec-HPR(r)` (Proposed — Certified Rank-$r$ Spectral Semi-Proximal HPR):** Same equality-slack standard form and exact Algorithm 2 of `HPR-LP`, replacing $\mathcal{T}_1^{(0)}$ by the **Certified Rank-$r$ Spectral Semi-Proximal Operator** $\mathcal{T}_1^{(r,\text{cert})} = \mathcal{M}_y^{(r,\text{cert})} - \hat{A}\hat{A}^*$ constructed via $q=2$ randomized subspace iteration + exact $r\times r$ Ritz eigendecomposition + Theorem 3 Schur-complement PSD certification (exact $\mathcal{M}_\sigma^{(r,\text{cert})}$ norm used in both adaptive restarts and adaptive penalty updates). Total wall-clock time **strictly includes** the randomized-SVD + certification setup time. Evaluated at fixed $r \in \{4, 8, 16\}$ AND with a simple **gap-gated auto-trigger** (only activate spectral rank $r$ when certified spectral ratio $\hat{s}_1 / \tilde{\theta} \ge 1.5$; otherwise fall back immediately to `HPR-Native` at $r=0$).
6. **External Reference Check:** `HiGHS` (exact optimal objective $f^*$) and `OR-Tools PDLP` (sanity check on original LP feasibility/optimality).

---

## 2. Bounded Synthetic Stage-0 Benchmark Suite (4 Families, 12 Instances, Seed-Locked)

All instances are generated deterministically (`seed` fixed in script) with known primal-dual feasibility and verified finite optimal value via HiGHS:

1. **`F1_FactorEq` (3 instances, equality-only, $m \in \{300, 500\}, n \in \{900, 1500\}$, rank $k \in \{1, 4, 8\}$):**
   Standard-form equality LPs $Ax = b, \; 0 \le x \le u$, where $A = A_{\text{sparse}} + \gamma P Q^\top$ (or equicorrelated nonnegative rows matching Theorem 2, so every row has comparable norm and survives `Ruiz(10)+PC` with $s_1/s_{k+1} \in [5, 25]$). All rows are equalities $\implies$ `cuPDLPx` ASB cannot exclude any row.
2. **`F2_LinkedMCF` (3 instances, mixed equality + inequality, $m \approx 400\text{--}600, n \approx 1200\text{--}1800$):**
   Multi-commodity network flow (equality flow conservation per node/commodity) plus shared congested arc-capacity and hub-budget inequality rows ($Gx \le h$) creating a multi-rank spectral spike across coupled commodities. Directly tests **Falsifier 2 (slack-conversion penalty on mixed LPs)**.
3. **`F3_FactorIneq` (3 instances, predominantly inequalities, $m \in \{300, 500\}, n \in \{900, 1500\}$, $k \in \{4, 8\}$):**
   Resource allocation / factor-budget LP $Ax \le b, \; 0 \le x \le u$ with sparse local constraints plus $k$ dense factor-coupling structure across rows (equicorrelated nonnegative constraint matrix). Stress-tests slack conversion when 100% of constraints are inequalities!
4. **`F4_FlatControl` (3 instances, negative/overhead control, $m \in \{300, 500\}, n \in \{900, 1500\}$):**
   Sparse random equality + inequality LPs with independent rows ($s_1/s_{r+1} \approx 1.1\text{--}1.3$ after `Ruiz+PC`). Tests whether gap-gated `Spec-HPR` avoids hurting flat-spectrum LPs.

---

## 3. Pre-Registered Cheap Failure Tests & Stage-0 Decision Gates

Before any scaling to large-scale MIPLIB/Netlib suites or GPU/CUDA implementation, the Stage-0 script must pass ALL THREE checks:

1. **Exact Mathematical Certificates (Pass/Fail — Hard Requirement):**
   - Numerical verification of Theorem 2 lower bound across 1,000 random positive diagonal scalings $(D_r, D_c)$ on $M_\rho$ ($m=64, \rho=0.5$): zero violations.
   - Exact eigenvalue verification of Theorem 3 Schur-complement certificate $\lambda_{\min}(\mathcal{M}_y^{(r,\text{cert})} - \hat{A}\hat{A}^*) \ge -10^{-11}$ on **100%** of Stage-0 instances (computed via dense/Lanczos minimum eigenvalue check on Stage-0 sizes).
   - Exact KKT solution agreement with HiGHS reference objective ($|f_{\text{HPR}} - f^*| / \max(1, |f^*|) \le 10^{-5}$) for all solved runs.
2. **Falsifier 1 — Home-Turf Coupled-LP Speedup Gate (Kill Criterion):**
   - Across `F1_FactorEq` (equality-only Theorem-2 regime), `Spec-HPR` must achieve **geometric mean iteration speedup $\ge 2.0\times$** AND **geometric mean total wall-clock speedup $\ge 1.5\times$** (strictly including SVD+certification setup time!) at $\text{tol} = 10^{-6}$ over **both** `HPR-Native` and `cuPDLPx-ASB`.
   - **Action if FAIL:** Freeze route immediately and record negative checkpoint.
3. **Falsifier 2 — Mixed-Inequality Slack-Penalty & Flat-Control Safety Gate:**
   - Across `F2_LinkedMCF` and `F3_FactorIneq`, measure explicitly whether slack conversion degrades `HPR-Slack` vs `HPR-Native` and whether `Spec-HPR` still beats `HPR-Native` and `cuPDLPx-ASB` in iterations and wall-clock time. If `Spec-HPR` loses to `HPR-Native` on inequality-only LPs (`F3_FactorIneq`), explicitly record that boundary condition (and investigate equality-block-only / native-inequality extension before any general-LP claim!).
   - Across `F4_FlatControl`, gap-gated `Spec-HPR` must stay within $\le 1.05\times$ total wall-clock time of `HPR-Native`.

---

## 4. Runtime Budget
- Iteration cap per solver per Stage-0 instance: `max_iter = 25,000` (sufficient to distinguish fast linear convergence vs. slow stalling, keeping total Stage-0 wall-clock runtime under ~2–3 minutes on local CPU).
- KKT check cadence: every 40 iterations (shared identically across all methods).
