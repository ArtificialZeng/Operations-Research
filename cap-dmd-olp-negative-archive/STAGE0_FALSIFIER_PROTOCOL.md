# Stage-0 One-Run Falsifier Protocol (`cap_dmd_olp_20261124`)

**Status:** LOCKED BEFORE IMPLEMENTATION (2026-11-24)  
**Purpose:** Fast, decisive, single-hyperparameter one-run falsifier testing whether `CAP-DMD` genuinely dominates published comparators across all four multi-resource OLP regimes simultaneously — without per-regime retuning and without offline LP re-solves.

---

## 1. Benchmark Problem (Multi-Resource Online Packing LP / Network Revenue Management)
- Resources: $m = 20$, horizon $T = 5,000$ arrivals, budget rate $\rho_i \in [0.15, 0.35]$ ($B_i = T \rho_i$).
- At each arrival $t = 1, \dots, T$: request $t$ has reward $r_t \in [0.5, 5.0]$ and sparse resource consumption vector $a_t \in \mathbb{R}_+^m$ (each request consumes $k_{\text{req}} \in \{2, 3\}$ resources with positive weights in $[0.2, 1.0]$). Decision $x_t \in [0, 1]$ (fractional online packing LP, matching Balseiro–Lu–Mirrokni 2023 and An et al. 2024; exact feasibility enforced via $a_t x_t \le B_t$).
- Offline optimum `OPT` and exact offline dual shadow price $\mu^* \in \mathbb{R}_+^m$ computed via **HiGHS** (`highspy`, exact LP optimum + dual solution) on every seed.
- **Seeds:** 5 deterministic seeds (`seed = 1001..1005`) per regime $\times$ 4 regimes = 20 runs total.

## 2. Exact Published Comparators (Identical Arrival Streams, Identical `OPT`)
1. **`DMD` (Balseiro, Lu & Mirrokni 2023, *Management Science*):** $\mu_1 = 0$, fixed step size $\eta = \eta_0 / \sqrt{T}$ ($\eta_0 = 1.0$, Euclidean mirror map $\Pi_{\mathbb{R}_+^m}(\mu_t - \eta g_t)$).
2. **`WS-DMD` (Warm-Start DMD):** Identical to `DMD` except $\mu_1 = \hat{\mu}$.
3. **`An24-SA` (An, Li, Moseley & Visotsky 2024, `arXiv:2402.13530` Alg. 2):** Warm-start $\mu_1 = \hat{\mu}$ with global doubling step-size schedule across epochs ($\eta$ scaled up when dual displacement triggers epoch doubling).
4. **`An24-MainALG` (An, Li, Moseley & Visotsky 2024, `arXiv:2402.13530` Alg. 4):** Warm-start `SA` with epoch checkpoints ($t \in \{250, 500, 1000, 2000\}$) solving exact offline LP `OPT_{t-1}` via HiGHS and globally switching to prediction-blind `DMD` (restarted from $\mu = 0$) if realized prefix revenue lags $(1 - \tau_{\text{sw}}) \mathrm{OPT}_{t-1}$ (total runtime including checkpoint LP solves recorded!).
5. **`CAP-DMD` (Proposed):** Coordinate-wise 1D `FreeGrad` (Mhammedi & Koolen 2020) anchored at $\hat{\mu}_i$ with exact Cutkosky–Orabona (2018) 1D box reduction onto $[0, U_i]$ ($U_i = \bar{r}/\rho_i$), **single fixed initial wealth parameter** $\varepsilon_i = G_i / \sqrt{T}$ (zero per-regime tuning, zero offline LP solves!).

## 3. Four Simultaneous Regimes & Pre-Registered One-Run Falsifier Gates
All methods run with ONE frozen configuration across all four regimes:

1. **`R1_Accurate_IID` (i.i.d. arrivals, accurate prediction $\hat{\mu} = \mu^* + \text{tiny } 1\%$ noise):**
   - **Gate 1 (Consistency):** Mean regret of `CAP-DMD` must be **$\le 0.50\times$** of prediction-blind `DMD` ($\ge 2.0\times$ regret reduction).
2. **`R2_SparseCorrupt_IID` (i.i.d. arrivals, 2 of 20 resources poisoned: one set to $5 \max(\mu^*_i, 1.0)$, one set to $0$; other 18 resources accurate $\hat{\mu}_i = \mu^*_i$):**
   - **Gate 2 (Partial-Corruption Separation — Core Claim):** Mean regret of `CAP-DMD` must strictly beat **all four** baselines (`DMD`, `WS-DMD`, `An24-SA`, `An24-MainALG`), achieving **$\ge 1.5\times$** lower regret than `DMD` and `An24-MainALG` and **$\ge 2.0\times$** lower regret than `WS-DMD`.
3. **`R3_FullPoison_IID` (i.i.d. arrivals, all 20 resources poisoned: half set to $5 \max(\mu^*_i, 1.0)$, half set to $0$):**
   - **Gate 3 (Full-Corruption Robustness):** Mean regret of `CAP-DMD` must stay within **$\le 1.35\times$** of prediction-blind `DMD` while achieving **$\ge 2.5\times$** lower regret than `WS-DMD`.
4. **`R4_AdversarialShift_Poison` (adversarial non-stationary front-loaded low-reward wave in first 40% followed by high-reward wave in last 60%, combined with poisoned $\hat{\mu} = 0$ encouraging early budget depletion):**
   - **Gate 4 (Adversarial Robustness):** Mean realized reward of `CAP-DMD` must be **$\ge 95\%$** of prediction-blind `DMD` (and strictly above `WS-DMD` when `WS-DMD` is harmed by $\hat{\mu}$).

**Kill Criterion:** If `CAP-DMD` fails **Gate 1**, **Gate 2**, or **Gate 3**, diagnose the exact finite-horizon mechanism immediately (e.g., FreeGrad wealth wake-up lag vs. gradient normalization or resource depletion cascading) and either freeze/archive or record an explicit pre-registered revision before any scaling.
