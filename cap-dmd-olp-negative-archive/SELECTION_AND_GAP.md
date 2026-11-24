# Route Selection, Primary Literature Audit & Mathematical Formulation (`cap_dmd_olp_20261124`)

**Date:** 2026-11-24  
**Workflow Provenance:** Native direct reading on `arxiv.org` (normal browser + native web search); **zero local skill workflows invoked**.

---

## 1. Why This Route Was Selected Over Rejected Alternative
Two distinct OR+AI frontier routes were audited directly from primary 2024–2026 literature before selection:
- **Rejected alternative (Decision-Focused Ellipsoidal Uncertainty Sets for Contextual Robust LP):** Direct check showed heavy overlap with Wang, Becker, Van Parys & Stellato (*Learning Decision-Focused Uncertainty Sets in Robust Optimization*, `arXiv:2305.19225`, *Math. Program.* 2025), which already learns end-to-end decision-focused uncertainty-set shapes with statistical feasibility bounds.
- **Selected route (`CAP-DMD` for Multi-Resource Learning-Augmented Online LP):** Completely distinct from every archived workspace project and targets a crisp, formally open multi-resource gap in the closest primary literature.

---

## 2. Closest Primary Papers Read & Exact Gaps

1. **Balseiro, Lu & Mirrokni (2023), *Management Science* 69(1):533–554 (`arXiv:2002.10455`)** — *The Best of Many Worlds: Dual Mirror Descent for Online Allocation Problems*:
   - Establishes the canonical Lagrangian reduction: for any online dual sequence $\{\mu_t\}_{t=1}^T \subset \mathbb{R}_+^m$ choosing $x_t = \arg\max_{x \in \mathcal{X}_t}\{f_t(x) - \mu_t^\top b_t(x)\}$ with subgradients $g_t = \rho - b_t(x_t)$ up to resource-depletion stopping time $\tau \le T$, both stochastic i.i.d. regret and adversarial $\alpha^*$-competitive shortfall are bounded directly by the online linear optimization (OLO) regret $R_\tau(\mu) := \sum_{t=1}^\tau \langle g_t, \mu_t - \mu \rangle$ against $\mu = \mu^*$ (stochastic) or $\mu \in \{0\} \cup \{\bar{\mu}_i e_i\}$ (adversarial), plus $O(1)$ boundary terms.
   - **Limitation:** Prediction-blind (`DMD` starts at $\mu_1 = 0$ with fixed scalar $\eta = O(1/\sqrt{T})$), incurring $\Theta(m\sqrt{T})$ regret even when accurate historical shadow-price forecasts $\hat{\mu} \approx \mu^*$ are available.

2. **An, Li, Moseley & Visotsky (Jun 2024, `arXiv:2402.13530v2`, read directly in browser)** — *Best of Many in Both Worlds: Online Resource Allocation with Predictions under Unknown Arrival Model*:
   - Extends Balseiro–Lu–Mirrokni to use a predicted dual vector $\hat{\mu} \in \mathbb{R}_+^m$ via `SA` (warm-start + global doubling step sizes), `AA` ($\eta \sim \epsilon(T)/T$), and `MainALG` (epoch-based global switching test comparing cumulative reward to offline `OPT_{t-1}`).
   - **Three concrete, executable gaps:**
     1. **Global all-or-nothing switching breaks under sparse/partial multi-resource corruption:** When $s \ll m$ resources experience a distribution shift or poisoned forecast while $m - s$ shadow prices remain accurate, `WS-DMD` stalls on corrupted coordinates, `SA` blows up its global scalar step size across all $m$ coordinates (destabilizing accurate prices), and `MainALG` trips its global test and discards **all** $m$ predictions.
     2. **Expensive offline LP checkpoints & known accuracy rate:** `MainALG` requires repeatedly solving full offline LPs `OPT_{t-1}` at epoch checkpoints, incurs a $(1-\lambda)$ multiplicative loss + $O(\delta T)$ additive switching penalty, and Assumptions 1–2 assume a known $\epsilon(T) = o(1)$ with $\|\hat{\mu} - \mu^*\|_1 = o(\epsilon(T))$.
     3. **No coordinate-wise error-dependent guarantee:** The literature lacks a zero-LP-resolve, $O(m)$-per-step dual update whose regret decomposes **additively per resource** as a function of $|\mu_i^* - \hat{\mu}_i|$.

3. **Related 2024–2026 Learning-Augmented Allocation Literature Checked:**
   - **Golrezaei, Jaillet & Zhou (`arXiv:2306.12282v2`, May 2026):** Convex-set advice for single-resource two-class protection levels (not multi-resource OLP/DMD).
   - **Daneshvaramoli et al. (`arXiv:2406.18752v2`, ICML 2025):** Single-constraint online knapsack with point/interval value threshold predictions (not multi-resource OLP).
   - **Coester, Tudose & Turoczy (`arXiv:2606.05380`, Jun 2026):** Dual predictions for online *minimization* (metrical task systems, laminar set cover), not online packing LP / DMD.
   - **Foundational parameter-free OLO building blocks:** Cutkosky & Orabona (2018, black-box constraint reduction for unconstrained parameter-free OLO) and Mhammedi & Koolen (NeurIPS 2020, `FreeGrad`: variance-adaptive parameter-free OLO achieving $\tilde{O}(|w^*|\sqrt{V_T})$ regret with $O(1)$ per-step cost).

---

## 3. Proposed Algorithm & Exact Regret Decomposition (`CAP-DMD`)

### Formulation
At each arrival $t = 1, \dots, T$ (while remaining budget $B_{t,i} \ge \bar{a}_i$ or $b_t(x_t) \le B_t$):
- Resource budget rate $\rho = B / T \in \mathbb{R}_{++}^m$; known coordinate-wise gradient envelope $G_i = \max(\rho_i, \bar{a}_i - \rho_i)$ and dual upper bound $\mu_{\max,i} = \bar{r} / \rho_i$ (or safe box $[0, U_i]$ with $U_i \ge \mu_{\max,i}$).
- Given untrusted ML dual prediction $\hat{\mu} \in [0, U]$, define shifted coordinate $w_{t,i} := \mu_{t,i} - \hat{\mu}_i \in [-\hat{\mu}_i, U_i - \hat{\mu}_i]$.
- Run **independent 1D `FreeGrad` (Mhammedi & Koolen 2020)** on each coordinate $i \in \{1, \dots, m\}$ with exact Cutkosky–Orabona (2018) black-box box-constraint reduction onto $\mathcal{W}_i := [-\hat{\mu}_i, U_i - \hat{\mu}_i]$:
  1. Unconstrained FreeGrad iterate $\tilde{w}_{t,i}$ computed in closed form from cumulative negative surrogate gradient $S_{t-1,i} = -\sum_{s<t} \tilde{g}_{s,i}$ and variance $V_{t-1,i} = \sum_{s<t} \tilde{g}_{s,i}^2$ (normalized by $G_i$, initial wealth $\varepsilon_i > 0$):
     $$\tilde{w}_{t,i} = \varepsilon_i \cdot \frac{S_{t-1,i}(2 V_{t-1,i} + G_i |S_{t-1,i}|)}{2(V_{t-1,i} + G_i |S_{t-1,i}|)^2 \sqrt{V_{t-1,i} + G_i^2}} \exp\!\left(\frac{S_{t-1,i}^2}{2 V_{t-1,i} + 2 G_i |S_{t-1,i}|}\right).$$
  2. Project onto box: $w_{t,i} = \Pi_{\mathcal{W}_i}(\tilde{w}_{t,i})$, set dual price $\mu_{t,i} = \hat{\mu}_i + w_{t,i} \in [0, U_i]$.
  3. Solve per-arrival primal decision $x_t = \arg\max_{x \in \mathcal{X}_t}\{f_t(x) - \mu_t^\top b_t(x)\}$ (feasible check $b_t(x_t) \le B_t$; else truncate/zero).
  4. Observe true dual subgradient $g_{t,i} = \rho_i - b_{t,i}(x_t)$, compute Cutkosky–Orabona surrogate gradient $\tilde{g}_{t,i} = g_{t,i} + \max(0, \operatorname{sign}(\tilde{w}_{t,i} - w_{t,i}) \cdot (-g_{t,i})) \cdot \operatorname{sign}(\tilde{w}_{t,i} - w_{t,i})$ (equivalently: if $\tilde{w}_{t,i} \neq w_{t,i}$ and $g_{t,i}(\tilde{w}_{t,i} - w_{t,i}) < 0$, set $\tilde{g}_{t,i} = 0$, else $\tilde{g}_{t,i} = g_{t,i}$ — since $w_{t,i}$ is a 1D interval projection, the exact Cutkosky–Orabona surrogate is simply $\tilde{g}_{t,i} = g_{t,i}$ unless the gradient already pushes back toward the interval, or more precisely the standard 1D subgradient of $\ell_t(w) + |g_t|\operatorname{dist}(w, \mathcal{W}_i)$: when $\tilde{w}_{t,i} > \max \mathcal{W}_i$ and $g_{t,i} < 0$, $\tilde{g}_{t,i} = g_{t,i} + |g_{t,i}| = 0$; when $\tilde{w}_{t,i} < \min \mathcal{W}_i$ and $g_{t,i} > 0$, $\tilde{g}_{t,i} = g_{t,i} - |g_{t,i}| = 0$; otherwise $\tilde{g}_{t,i} = g_{t,i}$!).
  5. Update $S_{t,i} = S_{t-1,i} - \tilde{g}_{t,i}$, $V_{t,i} = V_{t-1,i} + \tilde{g}_{t,i}^2$.

### Theorem (Coordinate-Wise Error-Dependent Best-of-Both-Worlds Regret — Exact Target Statement)
Because $\sum_{t=1}^\tau g_{t,i}(w_{t,i} - w_i) \le \sum_{t=1}^\tau \tilde{g}_{t,i}(\tilde{w}_{t,i} - w_i)$ for every $w_i \in \mathcal{W}_i$ (Cutkosky & Orabona 2018, Theorem 2) and 1D FreeGrad satisfies the variance-adaptive bound (Mhammedi & Koolen 2020, Theorem 1), summing across $i = 1, \dots, m$ and plugging into Balseiro–Lu–Mirrokni (2023, Proposition 1) gives, for **every** $\mu \in \prod_{i=1}^m [0, U_i]$ simultaneously:
$$\sum_{t=1}^\tau \langle g_t, \mu_t - \mu \rangle \;\le\; \sum_{i=1}^m \left[ \varepsilon_i G_i + |\mu_i - \hat{\mu}_i| \sqrt{2(V_{\tau,i} + G_i^2)\ln\!\left(1 + \frac{|\mu_i - \hat{\mu}_i|\sqrt{V_{\tau,i} + G_i^2}}{\varepsilon_i G_i}\right)} + 2 G_i |\mu_i - \hat{\mu}_i| \ln\!\left(1 + \frac{|\mu_i - \hat{\mu}_i| V_{\tau,i}}{\varepsilon_i G_i^2}\right) \right].$$
- **Exact consequence:** Setting $\varepsilon_i = G_i / \sqrt{T}$ (or $\varepsilon_i = \mu_{\text{ref}} / T$) gives $O(m/\sqrt{T})$ baseline overhead on accurate coordinates ($|\mu_i^* - \hat{\mu}_i| = 0$), $\tilde{O}(|S|\Delta\sqrt{T})$ regret under $s = |S|$-sparse corruption (strictly independent of $m - s$!), and $o(T)$ worst-case adversarial shortfall (preserving $\alpha^*$-competitiveness with **zero** $(1-\lambda)$ switching loss and **zero** offline LP solves!).
