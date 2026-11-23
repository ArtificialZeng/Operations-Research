# Comprehensive Root Relaxation Diagnostic and Freeze Decision

## Executive Summary

This diagnostic evaluates the continuous fractional root relaxation across the three adapted Díaz benchmark cases (`p01`, `p26`, `p50`) with 200 demand scenarios each, following `experiments/linked_root/PROTOCOL.md`. We assess three deterministic equivalent LP formulations under a 45-second budget:
1. **Plain LP**: Standard facility-capacity constrained continuous relaxation.
2. **Linked LP**: Proportional arc allocation links $y_{sij} \le x_i d_{sj}$ with full original unmet-demand penalty $\rho$.
3. **Linked Separated LP**: Proportional arc allocation links $y_{sij} \le x_i d_{sj}$ with residual penalty $\eta = 2\max_{i,j} c_{ij}$ plus exact scalar shortage recourse $S_s(x) = (D_s - \sum_i x_i \min(u_i, D_s))^+$.

All nine worker runs in `experiments/linked_root/runs_45s/` were executed on pinned CPUs with exact audited inputs. All interval bounds reported below are projected onto rational cost and multiplier grids via `certify.py` to yield rigorous mathematical lower and upper bounds on the continuous LP relaxation optimum.

---

## Distinction Between Fractional Root Witnesses and Integer Feasible Solutions

> [!IMPORTANT]
> The endpoints reported below evaluate the **continuous fractional relaxation** ($x \in [0, 1]^{|I|}$) of the two-stage stochastic program.
> - **Certified Lower Bound ($L$)**: A rigorous dual projection verifying that no fractional (and therefore no binary integer) opening vector can achieve an expected cost lower than $L$.
> - **Certified Upper Bound ($U$)**: A primal flow repair for the **fractional** opening vector $x$ returned by the root LP. It provides a rigorous upper bound on the continuous LP relaxation optimum at that fractional point. It **does NOT** represent a feasible integer opening ($x \in \{0, 1\}^{|I|}$) and must not be confused with an incumbent integer solution.
> - **Finite-Budget Integer Search**: Integer branch-and-cut or adaptive Benders searches (such as those in `experiments/adaptive_early/RESULT.md` and `experiments/diaz_lost_sales/RESULT.md`) evaluate discrete configurations and are structurally distinct from these deterministic equivalent root relaxations.

---

## Exact Numerical Results and Certified Intervals

### Instance p01 ($10 \times 20$, 200 scenarios, CPU 18)
- **Plain**:
  - Wall Time: 1.195 s (23 interior-point iterations)
  - Solver Status: Optimal (HiGHS Status 7)
  - Numeric Objective: `2274.5190751991495`
  - Certified Lower: `165465974463889509719 / 72747675000000000` $\approx 2274.5190751992$
  - Certified Upper: `36499847309218213 / 16047281250000` $\approx 2274.5190752619$
  - Interval Width: $6.2770 \times 10^{-8}$ (Relative Gap: $2.7597 \times 10^{-11}$)
- **Linked**:
  - Wall Time: 2.361 s (22 interior-point iterations)
  - Solver Status: Optimal (HiGHS Status 7)
  - Numeric Objective: `2275.704227573786`
  - Certified Lower: `993313149261992936213 / 436486050000000000` $\approx 2275.7042275738$
  - Certified Upper: `9348829640391352564157 / 4108104000000000000` $\approx 2275.7042276416$
  - Interval Width: $6.7787 \times 10^{-8}$ (Relative Gap: $2.9787 \times 10^{-11}$)
- **Linked Separated**:
  - Wall Time: 2.837 s (30 interior-point iterations)
  - Solver Status: Optimal (HiGHS Status 7)
  - Numeric Objective: `2275.704227573787`
  - Certified Lower: `934882964011287255353 / 410810400000000000` $\approx 2275.7042275738$
  - Certified Upper: `1168603705040907101521 / 513513000000000000` $\approx 2275.7042276260$
  - Interval Width: $5.2186 \times 10^{-8}$ (Relative Gap: $2.2932 \times 10^{-11}$)

**Comparison for p01**:
- **Pointwise Equivalence / Interval Overlap**:
  - Linked and Linked Separated independently certified intervals **overlap**:
    $$\text{Intersection} = [2275.7042275738, 2275.7042276260], \quad \text{Width} = 5.2185 \times 10^{-8}$$
  - This overlap is consistent with the proved pointwise identity of their exact LP optima.
- **Structural Strengthening (Linked vs Plain)**:
  - Minimum Gain ($L_{\text{linked}} - U_{\text{plain}}$): `4421388472286689 / 3730650000000000` $\approx +1.1851523119$
  - Maximum Gain ($U_{\text{linked}} - L_{\text{plain}}$): `11824057331294894347 / 9976824000000000000` $\approx +1.1851524424$
  - Exact Interval: $[+1.1851523119, +1.1851524424]$ currency units.

---

### Instance p26 ($20 \times 50$, 200 scenarios, CPU 22)
- **Plain**:
  - Wall Time: 7.401 s (37 interior-point iterations)
  - Solver Status: Optimal (HiGHS Status 7)
  - Numeric Objective: `5506.921758070077`
  - Certified Lower: `5535480774578379809527655927 / 1005186021840000000000000` $\approx 5506.9217580699$
  - Certified Upper: `15417448686082960109 / 2799649125000000` $\approx 5506.9217597341$
  - Interval Width: $1.6642 \times 10^{-6}$ (Relative Gap: $3.0220 \times 10^{-10}$)
- **Linked**:
  - Wall Time: 23.643 s (39 interior-point iterations)
  - Solver Status: Optimal (HiGHS Status 7)
  - Numeric Objective: `5531.134290161565`
  - Certified Lower: `46331823944918700410161309 / 8376550182000000000000` $\approx 5531.1342901615$
  - Certified Upper: `363386854473583925384999699 / 65698432800000000000000` $\approx 5531.1342902168$
  - Interval Width: $5.5303 \times 10^{-8}$ (Relative Gap: $9.9985 \times 10^{-12}$)
- **Linked Separated**:
  - Wall Time: 33.742 s (54 interior-point iterations)
  - Solver Status: Optimal (HiGHS Status 7)
  - Numeric Objective: `5531.1342901615635`
  - Certified Lower: `794259839055748648399034677 / 143598003120000000000000` $\approx 5531.1342901615$
  - Certified Upper: `99105505765317713183013847 / 17917754400000000000000` $\approx 5531.1342902053$
  - Interval Width: $4.3856 \times 10^{-8}$ (Relative Gap: $7.9289 \times 10^{-12}$)

**Comparison for p26**:
- **Pointwise Equivalence / Interval Overlap**:
  - Linked and Linked Separated independently certified intervals **overlap**:
    $$\text{Intersection} = [5531.1342901615, 5531.1342902053], \quad \text{Width} = 4.3852 \times 10^{-8}$$
  - This overlap is consistent with the proved pointwise identity on this $20 \times 50 \times 200$ case.
- **Structural Strengthening (Linked vs Plain)**:
  - Minimum Gain ($L_{\text{linked}} - U_{\text{plain}}$): `28973925165497680576187 / 1196650026000000000000` $\approx +24.2125304274$
  - Maximum Gain ($U_{\text{linked}} - L_{\text{plain}}$): `243380988674542488628394677 / 10051860218400000000000000` $\approx +24.2125321469$
  - Exact Interval: $[+24.2125304274, +24.2125321469]$ currency units.

---

### Instance p50 ($30 \times 90$, 200 scenarios, CPU 26)
- **Plain**:
  - Wall Time: 26.690 s (44 interior-point iterations)
  - Solver Status: Optimal (HiGHS Status 7)
  - Numeric Objective: `6801.621289065005`
  - Certified Lower: `288028820990512744269455123 / 42347082960000000000000` $\approx 6801.6212890644$
  - Certified Upper: `14235793361631539 / 2093000000000` $\approx 6801.6212907939$
  - Interval Width: $1.7294 \times 10^{-6}$ (Relative Gap: $2.5427 \times 10^{-10}$)
- **Linked**:
  - Wall Time: 41.111 s (25 interior-point iterations reached before 45 s budget limit)
  - Solver Status: **Time limit reached** (HiGHS Status 13; primal feasible)
  - Numeric Objective: `None`
  - Certificate: **NONE (Timeout)**
- **Linked Separated**:
  - Wall Time: 41.096 s (30 interior-point iterations reached before 45 s budget limit)
  - Solver Status: **Time limit reached** (HiGHS Status 13; primal feasible)
  - Numeric Objective: `None`
  - Certificate: **NONE (Timeout)**

**Analysis for p50**:
- With $30$ facilities, $90$ customers, and $200$ scenarios, the linked formulation introduces $540,000$ proportional linking rows. Within the strict 45-second wall-clock cap, the single-threaded interior-point solver executed 25 iterations (linked) and 30 iterations (linked separated) before reaching the time limit.
- In accordance with `experiments/linked_root/native_review/assessment.md`, **a timeout cannot favor either formulation**. Neither arm reached optimality, and neither produced a comparable certified endpoint. Both timeouts are retained as missing/unresolved outcomes at the 45-second deterministic-equivalent LP level.

---

## Scientific Observations & Interior-Point Diagnostics

1. **Proved Identity vs. Observed IPM Timings**:
   - The pointwise identity proves that the exact continuous LP optima for `linked` and `linked_separated` are equal. On both `p01` and `p26`, the independently certified intervals overlap, which is consistent with this proved identity.
   - In these two completed cases, the `linked_separated` interior-point runs took more iterations and longer wall-clock time than the original `linked` runs:
     - On `p01`: 30 iterations (2.837 s) vs. 22 iterations (2.361 s).
     - On `p26`: 54 iterations (33.742 s) vs. 39 iterations (23.643 s).
   - These are one-run wall-clock observations on these two instances; this diagnostic does not attribute the runtime difference to a specific structural cause (such as hinge row count) and does not generalize to decomposition performance.

2. **Structural Strengthening**:
   - The addition of proportional arc links $y_{sij} \le x_i d_{sj}$ strictly tightens the root continuous relaxation by $[+1.1851523119, +1.1851524424]$ on `p01` and $[+24.2125304274, +24.2125321469]$ on `p26`.

3. **Priority Boundaries Maintained**:
   - Prior work by Zhang & Kalcsics (2026) already established the use of proportional arc links $y_{sij} \le x_i d_{sj}$ with a uniform shortage penalty.
   - Gómez-Rocha et al. (2024) equations remain inaccessible in public sources; no unverified claims of novelty regarding general Benders inequalities with shortages are asserted.

---

## Freeze and Decision Recommendation

### Decision: Freeze This Diagnostic Record Only
- The deterministic-equivalent root relaxation diagnostic record (`experiments/linked_root/runs_45s/`) should be **FROZEN** as-is, retaining both `p50` timeouts.
- The broader research article still has a material open computational question: whether shortage separation improves finite-budget Benders search *on the linked feasible region* when both arms enforce identical proportional arc links.

### Coordinator Artifact List for This Diagnostic Record
1. `experiments/linked_root/runs_45s/*.json` & `*.log`: Authoritative sealed run records and execution logs for the 9 runs (including both `p50` timeouts).
2. `experiments/linked_root/runs_45s/lock.json`: Cryptographic lock and environment manifest.
3. `experiments/linked_root/native_review/assessment.md`: Native review establishing theoretical distinctions.
4. `D:\AI_Science\antigravity\native_linked_root_execution_20261124\RESULT_AND_DECISION.md`: Exact rational interval report and diagnostic freeze decision.
5. `D:\AI_Science\antigravity\native_linked_root_execution_20261124\STATUS.md`: Execution status tracking document.

### Concrete Next Action
- Execute a narrowly scoped, matched, capped **linked Benders pilot** on Díaz `p01` (protocol in `LINKED_BENDERS_PILOT.md`), comparing original-price linked Benders against separated linked Benders under the same proportional arc links, cold wall-clock budget, candidate generation schedule, exact rational verifier, and target gap, plus a cheap fixed-history transfer check.
