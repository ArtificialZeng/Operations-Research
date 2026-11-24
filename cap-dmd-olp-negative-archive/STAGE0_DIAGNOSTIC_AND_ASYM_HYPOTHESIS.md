# Stage-0 Diagnostic & Asymmetric Coin-Betting Mechanism (`cap_dmd_olp_20261124`)

**Date:** 2026-11-24  
**Workflow Provenance:** 100% native (zero local skill workflows invoked).

---

## 1. Stage-0 Falsifier Record (Preserved Untouched)
1. **v1 smoke (`stage0_one_run_falsifier.py` / `stage0_falsifier_results.json`):** Caught an immediate budget-scaling bug (`rho in [0.15, 0.35]` exceeded expected demand `0.078`, yielding non-binding $\mu^* = 0$ and `DMD Regret = 0`).
2. **v2 binding suite (`stage0_v2_binding_falsifier.py` / `stage0_v2_binding_results.json`, `m=20`, `T=5000`, `rho in [0.025, 0.055]`, `>=19/20` binding resources):**
   - **Pre-registered `eta0=1.0` gates:** Symmetric `CAP-DMD` **PASSED Gate 1** (`28.18×` vs `DMD`: regret `74.03` vs `2086.58`), **PASSED Gate 2** (`3.43×` vs `DMD`, `2.85×` vs `An24-MainALG`, `2.22×` vs `An24-SA`, `2.02×` vs `WS-DMD`: regret `608.62` vs `1231–2087`), **PASSED Gate 4** (`1.20×` reward vs `DMD`), and missed Gate 3 solely on `WS-DMD / CAP-DMD = 2.02× < 2.5×` (while passing `CAP/DMD = 1.25× <= 1.35×`).
   - **Critical self-audit (strong scale-normalized baseline `DMD-Norm`, $\eta_0 = 1/\bar{\rho} \approx 25$):** Adding `DMD-Norm` exposed a major scientific insight!
     - On `R1_Accurate_IID`, `CAP-DMD` (`74.03`) crushed `DMD-Norm` (`369.47`, **5.0×**) and `WS-DMD-Norm` (`265.48`, **3.6×**).
     - **However**, on `R2`/`R3`/`R4`, symmetric `CAP-DMD` (`608.62` / `2614.99` / `4498.90`) **lost** to `DMD-Norm` (`369.47` / `369.47` / `2544.23`)!

## 2. Exact Mathematical Diagnosis: Gradient Asymmetry in Sparse Multi-Resource OLP
In any sparse multi-resource packing LP ($k \ll m$ resources per request), the dual subgradient $g_{t,i} = \rho_i - a_{t,i} x_t$ lies in the **heavily asymmetric interval**
$$g_{t,i} \in \big[-G_i^-,\; +G_i^+\big], \qquad G_i^+ := \rho_i, \qquad G_i^- := \bar{a}_i - \rho_i, \qquad \frac{G_i^-}{G_i^+} = \Theta(m) \approx 25.$$
Symmetric-envelope `FreeGrad` normalizes both signs by $G_i = \max(G_i^+, G_i^-) = G_i^- \approx 0.96$, causing two finite-horizon failures:
1. **Upward-correction damping ($25\times$ too slow):** When $\hat{\mu}_i < \mu_i^*$ (e.g., $\hat{\mu}_i = 0$ in `R2`, `R3`, `R4`), an upward displacement $w_{t,i}^+ \ge 0$ loses wealth **only** when $g_{t,i} > 0$, which is bounded by $G_i^+ = \rho_i$ — NOT $G_i^-$! Normalizing by $G_i^-$ suppresses upward price defense by $G_i^- / \rho_i \approx 25\times$.
2. **Downward-correction variance-floor lag:** When $\hat{\mu}_i > \mu_i^*$ (rejecting requests so $g_{t,i} = +\rho_i$), initializing $V_0 = (G_i^-)^2$ requires $(G_i^-/\rho_i)^2 \approx 600$ steps just for $\sum g_{s,i}^2$ to match $V_0$!

## 3. Exact Asymmetric Two-Sided Coin-Betting Dual Mirror Descent (`Asym-CAP-DMD`)
Decompose the dual displacement from $\hat{\mu}_i$ as $w_{t,i} = w_{t,i}^+ - w_{t,i}^-$ ($w_{t,i}^+ \ge 0$ raises $\mu_i$, $w_{t,i}^- \ge 0$ lowers $\mu_i$):
- **Upward coin-betting expert ($w_{t,i}^+ = \beta_{t,i} W_{t-1,i}^+ / \rho_i \ge 0$, $\beta_{t,i} \in [0, 1/2]$):**
  Wealth update $W_{t,i}^+ = W_{t-1,i}^+ - g_{t,i} w_{t,i}^+ = W_{t-1,i}^+ \!\left(1 - \beta_{t,i} \frac{g_{t,i}}{\rho_i}\right)$. Because $g_{t,i} \le \rho_i$ identically, $1 - \beta_{t,i} g_{t,i}/\rho_i \ge \frac{1}{2} > 0$ **unconditionally**, while over-consumption ($g_{t,i} < 0$) multiplies wealth by $1 + \beta_{t,i}|g_{t,i}|/\rho_i \gg 1$!
- **Downward coin-betting expert ($w_{t,i}^- = \gamma_{t,i} W_{t-1,i}^- / G_i^- \ge 0$, $\gamma_{t,i} \in [0, 1/2]$):**
  Wealth update $W_{t,i}^- = W_{t-1,i}^- + g_{t,i} w_{t,i}^- = W_{t-1,i}^- \!\left(1 + \gamma_{t,i} \frac{g_{t,i}}{G_i^-}\right)$. Because $g_{t,i} \ge -G_i^-$ identically, $1 + \gamma_{t,i} g_{t,i}/G_i^- \ge \frac{1}{2} > 0$ **unconditionally**!
- Both fractions $\beta_{t,i}, \gamma_{t,i} \in [0, 1/2]$ are updated by exact 1D **Online Newton Step (ONS)** on log-wealth (Cutkosky & Orabona, ICML 2018), with exact Cutkosky–Orabona box-constraint reduction onto $[-\hat{\mu}_i, U_i - \hat{\mu}_i]$.

### Stage-0b Pre-Registered Gate Against STRONG Scale-Normalized Baselines (`DMD-Norm`, `WS-DMD-Norm`, `An24-MainALG-Norm`)
With ONE frozen configuration across all 4 binding regimes (`R1`–`R4`), `Asym-CAP-DMD` must:
1. **`R1_Accurate_IID`:** Beat `DMD-Norm` by **$\ge 3.0\times$** and `WS-DMD-Norm` by **$\ge 2.0\times$**.
2. **`R2_SparseCorrupt_IID`:** Strictly beat **ALL** strong normalized baselines (`DMD-Norm`, `WS-DMD-Norm`, `An24-SA-Norm`, `An24-MainALG-Norm`) by **$\ge 1.5\times$** lower regret!
3. **`R3_FullPoison_IID`:** Stay within **$\le 1.35\times$** of `DMD-Norm`'s regret while beating `WS-DMD-Norm` by **$\ge 2.0\times$**.
4. **`R4_AdversarialShift_Poison`:** Achieve **$\ge 95\%$** of `DMD-Norm`'s realized reward!
