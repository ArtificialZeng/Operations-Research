# Theorem, Exact Rational Certificates, Scope & Stage 0B Receipt: Hub-Lifted Closed-Neighborhood Valid Inequalities for `2-DCNP`

**Directory:** `d:\AI_Science\antigravity\dcnp_polyhedral_cuts_20261124\`  
**Date:** 2026-11-24  
**Scope:** Simple, undirected, unweighted, fixed-budget Distance-2 Critical Node Problem (`2-DCNP`) on **abstract/synthetic graphs only** (zero real transport, power, telecom, biological, or operational targeting networks; zero third-party code or datasets copied from unlicensed archives).  
**Polyhedral Claim Label:** **Valid inequalities** (explicitly NOT a convex-hull or facet-defining claim without a separate dimension/facet proof).

---

## 1. Exact Problem Statement & Variable Conventions

Let $G = (V, E)$ be a simple, undirected, unweighted graph with $n = |V|$ vertices and fixed deletion budget $b \in \{0, 1, \dots, n\}$. Define the distance-$\le 2$ pair set
$$E^{(2)} \;=\; \bigl\{\{u,v\} \subset V : u \ne v,\; \mathrm{dist}_G(u, v) \le 2\bigr\} \;=\; E \;\cup\; E_2^{\setminus},$$
where $E_2^{\setminus} = E^{(2)} \setminus E$ denotes non-adjacent pairs sharing at least one common neighbor in $G$.

The **fixed-budget unweighted `2-DCNP`** minimizes the number of surviving unordered pairs at distance $\le 2$ in $G - S$:
$$\min_{x, y} \;\; \sum_{\{u,v\} \in E^{(2)}} y_{uv}$$
subject to:
- $x_v \in \{0, 1\}$ for all $v \in V$ ($x_v = 1$ iff vertex $v$ is deleted, $S = \{v \in V : x_v = 1\}$), with budget $\sum_{v \in V} x_v \le b$;
- $y_{uv} \in [0, 1]$ for all $\{u,v\} \in E^{(2)}$ (equivalently $y_{uv} \in \{0,1\}$ at any optimal integer $x$), encoding $y_{uv} = 1$ iff $u, v \notin S$ and $\mathrm{dist}_{G - S}(u, v) \le 2$;
- **Salemi & Buchanan (2022) Thin `d = 2` constraints** (`DOI: 10.1287/ijoc.2021.1136`):
  - Edge constraints: $y_{uv} + x_u + x_v \ge 1$ for every $\{u,v\} \in E$;
  - Disaggregated 2-hop constraints: $y_{uv} + x_u + x_v + x_w \ge 1$ for every $\{u,v\} \in E_2^{\setminus}$ and every common neighbor $w \in N(u) \cap N(v)$.

---

## 2. Theorem 1 — Hub-Lifted Closed-Neighborhood (`N[w]`) Valid Inequalities (Two-Case Proof)

Let $w \in V$ be any hub vertex, let $Q \subseteq N(w)$ be any neighbor subset of size $q = |Q| \ge 2$, and let $t \in \{0, 1, \dots, q - 1\}$ be any integer chord parameter. Define:
- **Slope:** $s = q - t \in \{1, \dots, q\}$;
- **Baseline clique-on-$(Q \cup \{w\})$ RHS:**
  $$R(q, t) \;=\; \binom{q + 1 - t}{2} + t(q - t) \;=\; \frac{(q - t)(q + t + 1)}{2};$$
- **Internal neighbor-edge lower bound:** Let $m_Q = |E(G[Q])|$ and let $d_{G[Q]}^{(1)} \ge d_{G[Q]}^{(2)} \ge \dots \ge d_{G[Q]}^{(q)}$ be the vertex degrees of the induced subgraph $G[Q]$ sorted in non-increasing order. For any $r \in \{0, 1, \dots, q\}$, define
  $$L_Q(r) \;=\; \max\!\left(0,\; m_Q - \sum_{i=1}^{r} d_{G[Q]}^{(i)}\right), \qquad \mu_Q(s) \;=\; \min_{0 \le r \le q} \bigl(L_Q(r) + s r\bigr), \qquad M_w \;=\; R(q, t) - \mu_Q(s).$$

> **Theorem 1 (Validity).** For every feasible integer solution $(x, y) \in \{0,1\}^n \times [0,1]^{|E^{(2)}|}$ of simple, undirected, unweighted `2-DCNP`, the **Hub-Lifted Closed-Neighborhood inequality**
> $$\sum_{\{u,v\} \subset Q \cup \{w\}} y_{uv} \;+\; s \sum_{u \in Q} x_u \;+\; M_w\, x_w \;\ge\; R(q, t)$$
> is **valid**.

### Proof (Two-Case Algebraic Proof)

Note first that every unordered pair $\{u,v\} \subset Q \cup \{w\}$ belongs to $E^{(2)}$: either one endpoint is $w$ (so $\{u,v\} \in E$), or $u, v \in Q \subseteq N(w)$ share common neighbor $w$ (so $\mathrm{dist}_G(u,v) \le 2$). Let $R_{\text{del}} = \{u \in Q : x_u = 1\}$ with $r = |R_{\text{del}}| \in \{0, \dots, q\}$.

- **Case 1: Retained hub ($x_w = 0$).**
  Since $w \notin S$, every pair of distinct surviving vertices in $(Q \cup \{w\}) \setminus R_{\text{del}}$ (of cardinality $q + 1 - r$) is connected in $G - S$ either directly by an edge incident to $w$ or via the 2-hop path $u - w - v$. Hence every such surviving pair has $y_{uv} = 1$, giving
  $$\sum_{\{u,v\} \subset Q \cup \{w\}} y_{uv} \;\ge\; \binom{q + 1 - r}{2}.$$
  Compare $\binom{q + 1 - r}{2} + s r$ with $R(q, t) = \binom{q + 1 - t}{2} + s t$ using $s = q - t$:
  $$\binom{q + 1 - r}{2} + (q - t) r - \left[\binom{q + 1 - t}{2} + (q - t) t\right] \;=\; \frac{(r - t)(r - t - 1)}{2}.$$
  Because $r, t \in \mathbb{Z}$, the product $(r - t)(r - t - 1)$ of two consecutive integers is always $\ge 0$ (equality at $r \in \{t, t + 1\}$). Thus
  $$\sum_{\{u,v\} \subset Q \cup \{w\}} y_{uv} + s r + M_w \cdot 0 \;\ge\; R(q, t).$$

- **Case 2: Deleted hub ($x_w = 1$).**
  Every edge $\{u,v\} \in E(G[Q \setminus R_{\text{del}}])$ remains at distance $1 \le 2$ in $G - S$ regardless of $x_w = 1$, so $y_{uv} = 1$ for every surviving internal edge of $G[Q]$. Deleting any $r$ vertices from $G[Q]$ removes at most the sum of their degrees in $G[Q]$, which is bounded above by the sum of the $r$ largest degrees $\sum_{i=1}^r d_{G[Q]}^{(i)}$. Since the surviving edge count is nonnegative,
  $$\sum_{\{u,v\} \subset Q \cup \{w\}} y_{uv} \;\ge\; \bigl|E(G[Q \setminus R_{\text{del}}])\bigr| \;\ge\; \max\!\left(0,\; m_Q - \sum_{i=1}^r d_{G[Q]}^{(i)}\right) \;=\; L_Q(r).$$
  Adding $s r + M_w \cdot 1$ yields
  $$\sum_{\{u,v\} \subset Q \cup \{w\}} y_{uv} + s r + M_w \;\ge\; L_Q(r) + s r + \bigl(R(q, t) - \mu_Q(s)\bigr) \;\ge\; \mu_Q(s) + R(q, t) - \mu_Q(s) \;=\; R(q, t),$$
  by definition of $\mu_Q(s) = \min_{0 \le r' \le q}(L_Q(r') + s r')$. $\square$

*(Remark on $L_Q$ tightening: When $G[Q]$ is triangle-free or an independent set, $m_Q = 0 \implies \mu_Q(s) = 0$ and $M_w = R(q, t)$ is exact; when $G[Q]$ is dense, e.g., $Q \cong K_4$ inside $K_5$, $L_Q(r)$ is a valid polynomial-time lower bound but can be strictly smaller than the exact minimum remaining-edge count for $r \ge 2$ — see Section 5 below.)*

---

## 3. Proposition 2 — Infinite Graph-Family Consequence ($d$-Regular Graphs of Girth $\ge 6$)

Let $\mathcal{P}_{\text{base}}(G, b)$ denote the **full exhaustive baseline LP relaxation** containing:
1. Budget $\sum_{v \in V} x_v \le b$ and box bounds $x_v, y_{uv} \in [0, 1]$;
2. Salemi & Buchanan (2022) Thin `d = 2` edge and disaggregated 2-hop constraints;
3. Khoshbakhtian et al. (`arXiv:2308.05204v2`) aggregated `2-DCNDP` constraints;
4. **ALL** Chen et al. (2025) analogously adapted Clique-Chord inequalities over every clique subset $|K| \ge 3$ and every chord $t$ (which includes Alozie Prop. 3.4.1 triangles as $|K| = 3, t = 0$);
5. **ALL** Alozie (2021/2024) Prop. 3.4.2 5-cycle inequalities.

Define two augmented models. **$\mathcal{P}_{\text{aug}}^{\text{full}}(G, b)$** is $\mathcal{P}_{\text{base}}(G, b)$ plus the Theorem 1 inequalities with $Q = N(w)$ only (all hubs $w$, all chords $t$). **$\mathcal{P}_{\text{aug}}^{\text{all}}(G, b)$** is $\mathcal{P}_{\text{base}}(G, b)$ plus the Theorem 1 inequalities for every hub, every $Q \subseteq N(w)$ with $|Q| \ge 2$ and every $t$. Since $\mathcal{P}_{\text{aug}}^{\text{all}} \subseteq \mathcal{P}_{\text{aug}}^{\text{full}}$, $z^{*}_{\text{all}} \ge z^{*}_{\text{full}} \ge z^{*}_{\text{base}}$. Exact LP optima are written $z_{\text{base}}^*$, $z_{\text{full}}^*$, $z_{\text{all}}^*$. **Scope correction (supersedes the single $\mathcal{P}_{\text{aug}}$ wording and items 3-4 below):** items 3-4 of Proposition 2 were proved for the $(w, N(w), t=1)$ rows only. See Section 7 (`stage2_family_reduction_certificate.json`) for the corrected whole-family statement, which proves upper feasibility for all $Q$ and all $t$ by averaging, and for the exact quantifier ranges.

> **Proposition 2 (Closed-Form Exact LP Lift on $d$-Regular Graphs of Girth $\ge 6$).** Let $G = (V, E)$ be any $d$-regular graph ($d \ge 3$) of girth at least $6$ on $n$ vertices (hence containing zero triangles, zero cliques of size $\ge 3$, zero $C_4$, and zero $C_5$). For every budget $b$ satisfying $\frac{n}{d + 1} < b \le \frac{n}{3}$ (with $\alpha = b / n$):
> 1. Every Clique-Chord inequality ($|K| \ge 3$) and every Alozie 3-cycle and 5-cycle inequality is vacuous (empty), and Khoshbakhtian's aggregated 2-hop constraint coincides with Thin (each pair in $E_2^{\setminus}$ has a unique common neighbor).
> 2. The exact full-baseline LP optimum is
>    $$z_{\text{base}}^*(G, b) \;=\; \frac{n d^2}{2} - \frac{d(3d - 1)}{2}\, b.$$
> 3. Adding the $n$ full-neighborhood Hub-Lifted inequalities $(w, N(w), t = 1)$ gives a **lower bound**, valid for $\mathcal{P}_{\text{full}}$ and $\mathcal{P}_{\text{all}}$ alike (superset of the $t=1$ row family):
> $$z^*_{\text{all}}(G, b),\ z^*_{\text{full}}(G, b) \;\ge\; \frac{n(d^2 - 1)}{2} - \frac{(d - 1)(3d + 1)}{2}\, b, \qquad\text{so}\quad z^* - z_{\text{base}}^* \;\ge\; \frac{(d + 1)\,b - n}{2} > 0.$$
> 4. **Equality scope (restricted).** For $\alpha = \frac{b}{n} \le \frac{2}{d + 2}$ the symmetric point $x_v = \alpha$, $y_e = \frac{d-1}{d}(1 - \alpha)$, $y_p = 1 - 3\alpha$ is feasible for the **$(w, N(w), t=1)$ rows** and shows equality for **that row family only**. Feasibility for every $Q \subsetneq N(w)$ and every $t$ is **not** shown by this item; Section 7 proves it by averaging (verified exactly for $3 \le d \le 10$, all $\alpha \in [\frac{1}{d+1}, \frac13]$), and the whole-family value exceeds the expression in item 3 once $\alpha > \frac{2}{d+2}$.

### Proof (Exact Primal + Nonnegative Dual Construction)

Because $G$ is $d$-regular with girth $\ge 6$: $|E| = \frac{nd}{2}$, $|E_2^{\setminus}| = n\binom{d}{2} = \frac{nd(d-1)}{2}$, $|E^{(2)}| = \frac{nd^2}{2}$, every edge $e \in E$ belongs to exactly $2$ closed neighborhoods $N[w]$, every pair $p \in E_2^{\setminus}$ belongs to exactly $1$ closed neighborhood $N[w]$ (unique common neighbor $w$), and $m_{N(w)} = 0$ for all $w$ ($\mu_{N(w)} = 0$).

- **Baseline Primal (`<=`):** Setting $x_v = \alpha$, $y_e = 1 - 2\alpha \in [0,1]$, $y_p = 1 - 3\alpha \in [0,1]$ (valid since $\alpha \le 1/3$) satisfies budget, box, edge, Thin 2-hop, and Khoshbakhtian constraints with exact objective $\frac{nd}{2}(1-2\alpha) + \frac{nd(d-1)}{2}(1-3\alpha) = \frac{nd^2}{2} - \frac{d(3d-1)}{2}b$.
- **Baseline Dual (`>=`):** Assigning multiplier $1$ to every edge row, $1$ to every Thin 2-hop row, and $\frac{d(3d-1)}{2}$ to $-\sum x_v \ge -b$ yields column sums $1$ on every $y_e$, $1$ on every $y_p$, and $d + \binom{d}{2} + d(d-1) - \frac{d(3d-1)}{2} = 0$ on every $x_v$, giving dual lower bound $|E| + |E_2^{\setminus}| - \frac{d(3d-1)}{2}b = \frac{nd^2}{2} - \frac{d(3d-1)}{2}b$. Thus (2) holds with exact equality.
- **Augmented Nonnegative Dual (`>=`):** Assign multiplier $\frac{1}{2}$ to each of the $n$ Hub-Lifted cuts $(w, N(w), t=1)$ (where $s = d - 1$ and $M_w = R(d, 1) = \frac{(d-1)(d+2)}{2}$), multiplier $\frac{1}{2}$ to each of the $n\binom{d}{2}$ Thin 2-hop rows, and multiplier $\lambda_b = \frac{(d-1)(3d+1)}{2} \ge 0$ to $-\sum x_v \ge -b$. Column-sum check:
  - Every $y_e$ ($e \in E$): $2 \cdot \frac{1}{2} = 1 \le 1$;
  - Every $y_p$ ($p \in E_2^{\setminus}$): $\frac{1}{2} + \frac{1}{2} = 1 \le 1$;
  - Every $x_v$ ($v \in V$): $\frac{1}{2}\bigl((d-1)d + \frac{(d-1)(d+2)}{2}\bigr) + \frac{1}{2}\bigl(\frac{3d(d-1)}{2}\bigr) - \lambda_b = \frac{(d-1)(6d+2)}{4} - \frac{(d-1)(3d+1)}{2} = 0 \le 0$.
  Dual objective value: $\frac{n}{2}\bigl(\frac{(d-1)(d+2)}{2} + \frac{d(d-1)}{2}\bigr) - \lambda_b b = \frac{n(d^2-1)}{2} - \frac{(d-1)(3d+1)}{2}b$. Subtracting $z_{\text{base}}^*$ gives $\frac{(d+1)b - n}{2} > 0$ for $b > \frac{n}{d+1}$, proving (3).
- **Augmented Primal Equality (4):** Substituting $x_v = \alpha$, $y_e = \frac{d-1}{d}(1-\alpha)$, $y_p = 1 - 3\alpha$ into $(w, N(w), t)$ gives $\mathrm{LHS}(t) - R(d, t) = \frac{t - 1}{2}\bigl((t + 2) - (2d + t + 2)\alpha\bigr)$, which is $\ge 0$ at $t=0$ (since $\alpha > \frac{1}{d+1}$), $0$ at $t=1$, and $\ge 0$ for all $t \ge 2$ whenever $\alpha \le \frac{2}{d+2}$; edge slack is $\frac{(d+1)\alpha - 1}{d} > 0$, and objective equals the dual bound identically. $\square$

---

## 4. Explicit Literature Positioning & Direct vs. Analogous Adaptation Scope

| Prior Work | Exact Formulation / Variant | Relationship to Fixed-Budget `2-DCNP` | Direct vs. Analogous Adaptation | Implies Theorem 1? |
| :--- | :--- | :--- | :--- | :---: |
| **Salemi & Buchanan (2022)**, *INFORMS JoC* `10.1287/ijoc.2021.1136` | Thin `d`-DCNP formulation + simplicial vertex fixing (pinned repo `halisalemi/DCNP @ 3762e099...`, **no license file found in pinned archive**, `license_files: []`, `0` clique cuts in `GRBInterface.cpp`) | Exact fixed-budget `2-DCNP` base formulation | **Direct** (`d = 2`) | **No** (Prop. 2 + Sec. 5) |
| **Veremyev et al. (2015)**, *Networks* `10.1002/net.21622` | Recursive `d`-DCNP IP formulation | Equivalent LP to Thin at `d = 2` | **Direct** (`d = 2`) | **No** |
| **Khoshbakhtian et al.** (`arXiv:2308.05204v2`) | Aggregated `2-DCNDP` 2-hop constraints $c(y_{uv} + x_u + x_v) + \sum_{w \in N(u)\cap N(v)} x_w \ge c$ | Fixed-budget `2-DCNP` compact relaxation | **Direct** (`d = 2`) | **No** (Prop. 2 + Sec. 5) |
| **Alozie et al. (2021/2024)**, *COR* `10.1016/j.cor.2021.105254`, Springer `10.1007/978-981-99-5491-9_7`, Strathclyde thesis `T16048` Sec. 3.4.2 | Two CG valid inequality families: **Prop. 3.4.1 (Eq. 3.34, 3-cycles $K_3$):** $\sum_{i=1}^3 x_i + \sum_{i<j} y_{ij} \ge 2$; **Prop. 3.4.2 (Eq. 3.35, 5-cycles $C_5$):** $2\sum_{i=1}^5 x_i + \sum_{i=1}^5 y_{i, i+2} \ge 4$ | Fixed-budget `2-DCNP` odd-hole cuts | **Direct** (`d = 2`) | **No** — **mutually non-dominating** (Prop. 2 & `reg_n12_d4_b3` vs. $C_5$ witness below) |
| **Chen, Chen, Li & Dai (2025)**, *COAP* `10.1007/s10589-025-00698-5` | Clique-Subgraph valid inequalities $\sum_{\{u,v\} \subset K} y_{uv} + (|K|-t-1)\sum_{v \in K} x_v \ge \binom{|K|-t}{2} + t(|K|-t-1)$ | Originally proved for classical `CNDP` (`d = ∞`); valid for `2-DCNP` because every clique pair is an edge | **Analogous adaptation** (`d = ∞ -> d = 2`) | **No** — **mutually non-dominating** (Prop. 2 & `reg_n12_d4_b3` vs. $K_5$ witness below) |
| **Zhou et al. (2026)**, *Frontiers of Eng. Mgmt.* `10.1007/s42524-026-5349-2` | Unknown-budget ($\beta$-distance-based vertex disruptor: minimize $|S|$ s.t. remaining connectivity $\le \beta$) | **Distinct optimization problem** (variable cardinality, fixed connectivity cap) | **Distinct variant** (not fixed-budget comparator) | N/A (different objective/budget structure) |

### Verified Mutual Non-Implication Boundaries (`stage0b_exact_rational_certificate.json`, Pure `Fraction` Arithmetic)
1. **Hub-Star does NOT imply Alozie's $C_5$ inequality:** On $C_5$ ($n = 5, b = 2$), the rational vector $x_v = \frac{1}{3}$, $y_e = \frac{1}{3}$ ($e \in E$), $y_p = 0$ ($p \in E_2^{\setminus}$) satisfies **100%** of Thin + Aggregated + **ALL** Hub-Lifted cuts ($q = 2, t \in \{0,1\}$), yet violates Alozie's 5-cycle inequality (`LHS = 10/3 < 4`, exact violation **`2/3`**).
2. **$L_Q$-based Hub-Star does NOT imply Chen's Clique-Chord for cliques $|K| \ge 5$:** While Hub-Star with $q=3, t=1$ coincides identically with Chen's Clique-Chord on $K_4$, on $K_5$ ($n = 5, b = 3$) the rational vector $x_v = \frac{1}{2}$, $y_{uv} = \frac{1}{6}$ satisfies **100%** of Thin + Aggregated + **ALL** $L_Q$-based Hub-Lifted cuts (all subsets $|Q| \le 4$, all chords), yet violates Chen's $K_5$ ($t=2$) Clique-Chord inequality (`LHS = 20/3 < 7`, exact violation **`1/3`**).
3. **Consequence:** All three valid-inequality families (Chen Clique-Chord, Alozie $C_5$, and Theorem 1 Hub-Lifted Closed-Neighborhood) are **polyhedrally complementary**; therefore, any credible held-out computational comparison must include BOTH Clique-Chord and Alozie $C_5$ inside the baseline arm.

---

## 5. Executed Exact Verification Receipts (`0` Discrepancies; Pure Integer / `Fraction` Arithmetic)

### 5.1 Exhaustive $2^n$ Exact Integer Falsification (`stage0b_validity_and_witness.py` → `.json`)
Across **15 synthetic graphs** ($n = 5 \dots 11$: $K_{1,5}$, $K_{1,7}$, $K_{2,4}$, $K_{3,4}$, $K_{3,5}$, $W_6$, $W_8$, $C_5$, $C_7$, $K_6$, Petersen($10$), `barbell(4,1)`, `ER(10,0.35)`, `ER(11,0.30)`, `Reg(10,3)`):
- Binary deletion vectors checked via exact BFS: **`6,944`** (full $2^n$ per graph);
- Exhaustive Clique-Chord cuts checked (all clique subsets $|K| \ge 3$, all chords $t$): **`194`** cuts → **`65,792`** exact integer vector $\times$ cut checks;
- Exhaustive Hub-Lifted Closed-Neighborhood cuts checked (all hubs $w$, all $Q \subseteq N(w)$ with $|Q| \ge 2$, all chords $t$): **`3,364`** cuts → **`2,219,136`** exact integer vector $\times$ cut checks;
- **Total exact integer checks:** **`2,284,928`**; **`total_violations = 0`**; **`first_discrepancy = null`**.

### 5.2 Exact Rational Primal + Dual LP Certificates (`stage0b_exact_rational_certificate.py` → `.json`, `exit code 0`, `0.417s`)
Zero floating-point numbers are trusted in any inequality or bound below; every primal feasibility check ($A z \ge r, z \ge 0$), every nonnegative dual check ($A^\top \lambda \le c, \lambda \ge 0$), and every integer optimum is verified in exact Python `fractions.Fraction` / integer BFS arithmetic:

| Certified Witness | Graph Structure (`clq >= 3` / `C_5`) | Exact `z*_base` (Primal = Dual) | Exact `z*_aug` (Dual & Primal) | Exact Strict LP Lift | Exact `z*_IP` (Exhaustive BFS) | Gap Closed over Full Baseline |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: |
| **`heawood_bipartite_girth6_n14_b4`** | `n=14, d=3, g=6, b=4` (`0` / `0`) | **`15`** (Primal `x=2/7` & Stage 0B primal `= 15`; Dual `= 15`) | **`16`** — scope: **all-subset model** (`stage0b_exact_rational_certificate`: primal feasible for all `126` hub rows; Dual `lam_star=1/2, lam_2hop=1/2, lam_b=10` uses the `Q=N(w)`, `t=1` rows, i.e. the `Q=full` lower bound `16`; also re-certified in `stage2_family_reduction_certificate` for `t=1`/full-nbr/all-subset rows, 197/225/309 rows) | **`+1`** | **`17`** (`1,471` vecs) | **`50.0%`** |
| **`reg_n12_d4_b3`** *(non-bipartite, NOT regular girth >= 6, Prop. 2 does not apply)* | `n=12, d=4, b=3` (**`3` clq / `6` rows, `31` $C_5$**) | **`227/10` (`22.7`)** (Primal `= 227/10`; Dual `58` rows `= 227/10`) | **`23` exact for the `Q = N(w)` augmentation only** (solver run used `include_hub_mode="full_nbr"`, `3` hub rows in the dual, Primal `= 23`, Dual `50` rows `= 23`). For the **all-subset model the value is `>= 23`** (it is a superset of constraints) and is **not separately certified** | **`+3/10` for full-nbr arm; `>= +3/10` for all-subset** | **`25`** (`299` vecs) | **`13.04%` (full-nbr arm)** |
| `tutte_coxeter_n30_d3_girth8_b9` | `n=30, d=3, g=8, b=9` (`0` / `0`) | **`27`** (Primal = Dual) | **`30`** (Dual = Primal, `270` hub rows checked) | **`+3`** | — | Prop. 2 exact |
| `tutte_coxeter_n30_d3_girth8_b10` | `n=30, d=3, g=8, b=10` (`0` / `0`) | **`15`** (Primal = Dual) | **`20`** (Dual = Primal, `270` hub rows checked) | **`+5`** | — | Prop. 2 exact |
| `pg2_3_levi_n26_d4_girth6_b6` | `n=26, d=4, g=6, b=6` (`0` / `0`) | **`76`** (Primal = Dual) | **`78`** (Dual = Primal) | **`+2`** | — | Prop. 2 exact |
| `pg2_3_levi_n26_d4_girth6_b8` | `n=26, d=4, g=6, b=8` (`0` / `0`) | **`32`** (Primal = Dual) | **`39`** (Dual = Primal) | **`+7`** | — | Prop. 2 exact |
| `pg2_5_levi_n62_d6_girth6_b15` | `n=62, d=6, g=6, b=15` (`0` / `0`) | **`351`** (Primal = Dual) | **`745/2` (`372.5`)** (Dual = Primal) | **`+43/2`** | — | Prop. 2 exact |
| `pg2_5_levi_n62_d6_girth6_b20` | `n=62, d=6, g=6, b=20` (`0` / `0`) | **`96`** (Primal = Dual) | **Superseded.** Earlier receipt: `>= 135` = `t=1`, `Q=full` lower bound (primal pin failed). Resolved in Section 7: exact **`153`** for BOTH the `Q=N(w)` all-`t` model and the all-subset model (`t=2` active) | **`+57`** | — | exact (Section 7) |

*(Additional floating-point LP-lift candidates with exact rational baseline primals verified in `stage0b_validity_and_witness.json`: `cube_Q4_bipartite_n16_b4`, `bip_rand_7x7_p045_b3`, `bip_rand_8x8_p040_b4`, `reg_n14_d4_b4`, `er_n14_p035_b4` — retained as exploratory objective-lift candidates; exact primal+dual certificates above establish the rigorous bound lifts.)*

### 5.3 Exhaustive Verification of Independent-Set Simplicial Fixing (`stage0b_exact_rational_certificate.json`)
Fixing a deterministic greedy **independent set** $F$ of simplicial vertices to $x_v = 0$ (no two fixed vertices adjacent, so any optimal deletion of $v \in F$ can be swapped to an unfixed surviving neighbor $u \in N(v) \setminus S$ or dropped if $N(v) \subseteq S$) was verified across all **15** Part-1 synthetic graphs and all **132** `(graph, b)` pairs ($b = 0 \dots n$, `15` fixed vertices total): **`0` discrepancies** vs. unrestricted exact integer optimum.

---

## 6. Preserved Bounded Synthetic Mechanism Smoke (`stage0b_validity_and_witness.json`) — Mixed Timing, NO Speed Claim

Executed on `6` small synthetic graphs ($n = 48 \dots 56$) in single-threaded `HiGHS 1.15.1` (`30s` limit; build, LP/separation, and MIP times reported separately). **Explicit caveat:** This is an initial mechanism diagnostic ONLY (note that this smoke did not yet include Alozie $C_5$ rows in `A3`, and timing was mixed — dense Hub-Star rows slowed MIP search on `syn_bipartite_28x28` and `syn_sbm_4x14`). **No speed claim is made.**

| Synthetic Instance (`n, m, |E^(2)|, b`, `tri`) | `A1` Thin LP (`t_tot`) | `A3` Clique-Only LP (`cuts`, `t_tot`) | `A4_STAR` LP (`cuts`, `t_sep`, `t_mip`, `t_tot`) | `A4_BOTH` LP (`clq+hub`, `t_tot`) | Exact `OPT` (BFS) | Nodes (`A1`/`A3` vs `A4_STAR`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| `syn_bipartite_24x24_p018_b8` (`48,102,408,8`, `0`) | `132.25` (`0.067s`) | `132.25` (`0`, `0.060s`) | **`133.00`** (`10`, `0.014s`, `0.015s`, `0.029s`) | `133.00` (`0+10`, `0.028s`) | `133` | `1 / 1` vs `1` |
| `syn_bipartite_28x28_p016_b10` (`56,131,550,10`, `0`) | `172.50` (`1.317s`) | `172.50` (`0`, `1.309s`) | **`177.72`** (`27`, `0.036s`, `2.822s`, **`2.858s` slower!**) | `177.72` (`0+27`, `2.921s`) | `193` | `3 / 3` vs `3` |
| `syn_reg_n48_d4_b8` (`48,96,348,8`, `5`) | `180.33` (`0.304s`) | `180.33` (`0`, `0.303s`) | **`182.45`** (`22`, `0.023s`, `0.254s`, `0.277s`) | `182.45` (`0+22`, `0.277s`) | `183` | `1 / 1` vs `1` |
| `syn_reg_n56_d4_b10` (`56,112,418,10`, `2`) | `204.67` (`0.770s`) | `204.67` (`0`, `0.776s`) | **`207.23`** (`31`, `0.032s`, `0.527s`, `0.559s`) | `207.23` (`0+31`, `0.551s`) | `208` | `3 / 3` vs **`1`** |
| `syn_ws_n56_k6_p015_b10` (`56,168,524,10`, `112`) | `217.57` (`1.104s`) | `217.86` (`2`, `1.940s`) | **`219.73`** (`21`, `0.033s`, `0.992s`, `1.025s`) | **`220.01`** (`4+22`, `1.469s`) | `224` | `1 / 1` vs `1` |
| `syn_sbm_4x14_b10` (`56,228,925,10`, `179`) | `365.40` (`2.092s`) | `368.00` (`15`, `2.404s`) | `368.02` (`40`, `0.123s`, `3.539s`, **`3.664s` slower!**) | **`369.64`** (`22+44`, **`3.535s` slower!**) | `379` | `1 / 1` vs `1` |

**Mechanism Insight Driving the Locked Held-Out Protocol:** Unrestricted separation of `27–44` dense $O(|Q|^2)$ Hub-Star rows tightened the root LP on `6/6` synthetic instances (`100%`), but degraded total MIP wall time on `syn_bipartite_28x28` and `syn_sbm_4x14`. Accordingly, the locked held-out protocol (STAGE1_SEALED_SYNTHETIC_PROTOCOL.md) matches the **full credible baseline** (Thin + independent-set simplicial fixing + bounded Clique-Chord + bounded Alozie $C_5$) against `BASE_FULL + Hub-Star` with a fixed pre-registered sparsity/violation cap (`|Q| <= 8`, normalized violation threshold, fixed cut-pool budget) under a **common actual monotone wall deadline** covering build, simplicial fixing, LP/separation cycles, and MIP search.

---

## 7. Whole-Family Exact LP Reduction on $d$-Regular, Girth $\ge 6$ Graphs (Proposition 2'; synthetic only, no symmetry assumed)

**Scope note on the earlier table (Section 5.2).** Tested row scopes in `stage0b_exact_rational_certificate.json`: Heawood and Tutte–Coxeter primals were checked against **all-subset** hub rows; `PG(2,3)` and `PG(2,5)` against **`Q=N(w)` (all `t`)** rows; each dual used only the `t=1`, `Q=N(w)` rows (the "`Q=full` lower bound"). The `stage2` receipt below re-certifies every instance for three explicit scopes: **`t1full`** (only $(w,N(w),t=1)$), **`full_nbr`** ($Q=N(w)$, all $t$) and **`all`** (all hubs, all $Q$, all $t$).

**Setting.** $G$ is $d$-regular, girth $\ge 6$, $n$ vertices, $b=\alpha n$, $\alpha\le\frac13$. Then every $N(w)$ is independent ($\mu_Q=0$), every distance-2 pair has a unique hub, the clique and $C_3$/$C_5$ rows are empty, and $R(q,t)=\frac{(q-t)(q+t+1)}{2}$. Put $Y_e=\sum_{e\in E}y_e$, $Y_p=\sum_{p\in E_2^{\setminus}}y_p$, $X=\sum_v x_v$.

**Proposition 2' (counting reduction).** Averaging each row family over hubs and (for $|Q|=q<d$) over all $\binom dq$ subsets, with no automorphism or vertex-transitivity assumption, gives aggregate rows valid for *every* feasible point:
- edge: $Y_e+dX\ge \frac{nd}{2}$; thin: $Y_p+\frac{3d(d-1)}{2}X\ge\frac{nd(d-1)}{2}$;
- cut$(q,t)$: $\frac{2q}{d}Y_e+\frac{q(q-1)}{d(d-1)}Y_p+\big(sq+R(q,t)\big)X\ge nR(q,t)$, $s=q-t$.

Hence $z^*\ge \min\{Y_e+Y_p\}$ over these aggregate rows together with the box rows $0\le Y_e\le\frac{nd}{2}$, $0\le Y_p\le\frac{nd(d-1)}{2}$ and $X=b$ (increasing $X$ only relaxes every row). Conversely the **uniform point** $x_v=\alpha$, $y_e\equiv a$, $y_p\equiv c$ satisfies each *original* row iff it satisfies the corresponding scalar inequality, which is the aggregate row divided by $n$. **Statement (exact, all $d\ge3$):** for every $d$-regular graph of girth $\ge6$ with $d\ge3$, every row family closed under hub/subset averaging (`base`, `t1full`, `full_nbr`, `all`) has LP value $n\cdot v_F(\alpha)$, where $v_F$ is the optimum of the **boxed** two-variable LP above. No automorphism is assumed. This is a proof, not a computation, so it does not depend on $d\le 10$. What was *computed* (exact Fractions) is: the breakpoints for $d=3,\dots,8$, the graph-level certificates in the table below, and the closed-form check of the next paragraph.

**Scope map (do not conflate).**

| Statement | Range | Status |
| :--- | :--- | :--- |
| Boxed two-variable LP equals the whole-family LP value (counting + uniform point) | all $d\ge3$, regular, girth $\ge6$, any budget fraction $\alpha\in[0,1]$ | proved here |
| Simplified formula $z^*=n\max_t v_t(\alpha)$ | $3\le d\le10$, $\alpha\in[\frac1{d+1},\frac13]$ | verified exactly; **not** claimed for $d\ge11$ (the unboxed vertex needs $y_e>1$, e.g. $d=11,t=5,\alpha=\frac13$) |
| $\max_t v_t(\alpha)$ as a lower bound only | all $d\ge3$, all $\alpha$ | proved (dual feasible for every $d,t,\alpha$) |
| $t=1$ bound is the whole-family value | $\alpha\le\frac{2}{d+2}$, within the verified range | verified for $d\le10$ |
| Behaviour for $\alpha<\frac1{d+1}$ or $\alpha>\frac13$ | — | not checked |
| Closed form with chord/row families other than the four above (e.g. partial $t$ sets) | — | not checked |
| Girth $\ge5$ but $<6$, irregular graphs, $d=2$ | — | outside the proof (e.g. the $n=12$, $d=4$ witness has triangles) |

**Proposition 2'' (closed form, with scope).** Dual: $\mu_{(d,t)}=\frac12$ on cut$(d,t)$, $\frac12$ on thin, budget multiplier $S_t$ is nonnegative and feasible for every $d,t,\alpha$, giving the valid lower bound per vertex
$$v_t(\alpha)=I_t-S_t\alpha,\qquad I_t=\frac{2d^2-t(t+1)}{4},\quad S_t=\frac{6d^2-2d-2dt-t^2-t}{4}.$$
$v_0$ is the baseline ($d^2/2-d(3d-1)\alpha/2$) and $v_1$ is the earlier $t=1$ bound. $v_t=v_{t+1}$ exactly at $\alpha_t=\frac{t+1}{d+t+1}$, so $t$ is the best chord on $\big[\frac{t}{d+t},\frac{t+1}{d+t+1}\big]$; the $t=1$ bound is therefore the whole-family bound only up to $\alpha=\frac{2}{d+2}$. **Exactness** ($z^*_{\text{full}}=z^*_{\text{all}}=n\max_t v_t$) is verified in exact arithmetic for $3\le d\le 10$ and all $\alpha\in[\frac1{d+1},\frac13]$: the interval-endpoint point satisfies all aggregate rows and the box (`stage2b_closed_form_check.json`, `failed_d` list starts at 11). **For $d\ge 11$ the closed form is a valid lower bound but exactness is not claimed:** the unboxed vertex has $a>1$ (e.g. $d=11$, $t=5$, $\alpha=\frac13$, $a=\frac{12}{11}$), violating $y_e\le1$; no aggregate-row violation occurs, so only the box blocks it, and the boxed LP for $d\ge11$ was not solved here.

**Quantifier resolution.** (i) The $t=1$, $Q=N(w)$ value is exact only for $\alpha\le \frac{2}{d+2}$ (always true for $d=3$, and for $d=4$ since $\frac13=\frac26$). (ii) For $d\in\{5,\dots,10\}$ and larger $\alpha$, $z^*_{\text{full}}=z^*_{\text{all}}=n\max_t v_t>$ the $t=1$ value. (iii) Smaller $Q$ never became active in any exact sweep for $d\le8$ ($z^*_{\text{full}}=z^*_{\text{all}}$ at every breakpoint and endpoint, 0 mismatches).

### Exact breakpoints (`stage2_family_reduction_certificate.json`, Fraction arithmetic)

| $d$ | breakpoints in $[\frac1{d+1},\frac13]$ | active chord $t$ (all-subset model) |
| :-: | :--- | :--- |
| 3, 4 | none beyond $\frac1{d+1}$ | $t=1$ on the whole range |
| 5 | $\frac27$ | $t=1$ then $t=2$ |
| 6 | $\frac14$ | $t=1$ then $t=2$ |
| 7 | $\frac29,\ \frac3{10}$ | $t=1,2,3$ |
| 8 | $\frac15,\ \frac3{11}$ | $t=1,2,3$ |

**At $b=n/3$** (checked exactly $3\le d\le 40$ for the lower-bound formula, exactness only $d\le10$): $v_{\text{base}}=\frac d6$, $v_{t=1}=\frac{d-1}3$, whole family $\ge\frac{\lfloor (d+1)^2/4\rfloor}{6}$ (i.e. $\max_t (d-t)(t+1)/6$). E.g. $d=8$: $\frac43\to\frac73$ ($t=1$) $\to\frac{10}3$ (all $t$), exact.

### Graph-level exact two-sided certificates (primal vs every explicit row, dual nonnegative, both exact, `0` failures)

| Instance | $\alpha$ | base | `t1full` | `full_nbr` (all $t$) | `all` subsets | rows (`t1full`/`full_nbr`/`all`) | active |
| :--- | :-: | :-: | :-: | :-: | :-: | :-: | :--- |
| Heawood $n=14,d=3,b=4$ | 2/7 | 15 | 16 | 16 | 16 | 197 / 225 / 309 | $t=1$ |
| Tutte–Coxeter $n=30,d=3,b=9$ | 3/10 | 27 | 30 | 30 | 30 | 421 / 481 / 661 | $t=1$ |
| Tutte–Coxeter $b=10$ | 1/3 | 15 | 20 | 20 | 20 | 421 / 481 / 661 | $t=1$ |
| $PG(2,3)$ Levi $n=26,d=4,b=6$ | 3/13 | 76 | 78 | 78 | 78 | 625 / 703 / 1327 | $t=1$ |
| $PG(2,3)$ Levi $b=8$ | 4/13 | 32 | 39 | 39 | 39 | 625 / 703 / 1327 | $t=1$ |
| $PG(2,5)$ Levi $n=62,d=6,b=15$ | 15/62 | 351 | 745/2 | 745/2 | 745/2 | 3287 / 3597 / 14757 | $t=1$ |
| **$PG(2,5)$ Levi $b=20$** | 10/31 | 96 | **135** | **153** | **153** | 3287 / 3597 / 14757 | **$t=2$** |

**Resolved case.** The earlier `pg2_5_levi_n62_b20` receipt only had the lower bound $135$ (the $t=1$ dual) with a failed primal pin. The whole-family LP value is exactly $153$ for $Q=N(w)$ with all $t$ and for all subsets, certified by an exact nonnegative dual (multiplier $\frac12$ on the $(w,N(w),t=2)$ rows and on thin, budget multiplier $S_2$) matched by the exact uniform primal. The strict lift over the baseline $96$ is $+57$, not $\ge+39$; the $t=1$ rows alone give exactly $135$ (`t1full` column).

---

## 8. Nearest-Prior-Art Check (primary sources; synthetic-only context)

| Source | What was read | Exact IDs | Relation to Theorem 1 / Prop. 2' |
| :--- | :--- | :--- | :--- |
| Salemi & Buchanan, optimization-online preprint `7751.pdf` (not the published JoC pagination) | full text via `pdftotext` | Lemma 7 (partial dominant of THIN), Theorem 3, Theorem 4 ($\text{THIN}^{\uparrow x}=\text{proj}\,\text{PATH}^{\uparrow x}=\text{proj}\,R^{\uparrow x}$), Propositions 1–3 (simplicial fixing), Theorem 5 | Equivalence of formulations only; no star/closed-neighborhood inequality found in the text (only 1 hit for "star", in a different context). Does not imply Theorem 1: every row of THIN is a single pair constraint. |
| Alozie thesis `T16048` §3.4.2 | read earlier | Prop. 3.4.1 (Eq. 3.34), Prop. 3.4.2 (Eq. 3.35) | Odd-hole CG cuts; empty on girth $\ge 6$, so they cannot produce the $+1,+57,\dots$ lifts above. |
| Chen, Chen, Li, Dai (2025), COAP `10.1007/s10589-025-00698-5` | **not read**: Springer returned an HTML landing page (352 KB), no full text; abstract-level only via search | — | Clique-subgraph inequalities are empty on girth $\ge 6$, but I **cannot rule out** that this paper's projected/polynomial-size results contain an equivalent projected star statement. **Inaccessible claim.** |
| Di Summa–Grosso–Locatelli (2012), Zhou et al. (2026), Alozie COR (2021) | not read directly | — | Not verified. |

**Conclusion of the check.** I found no accessible primary statement of the hub-lifted closed-neighborhood family or of the counting reduction above, but the single most relevant source (Chen et al. 2025 full text) was not accessible, so no novelty or priority claim is made.
