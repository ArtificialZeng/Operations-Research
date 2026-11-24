# Immutable Pre-Outcome Plan: Out-of-Instance 4-Arm Attribution Validation (`p50`)

**Working Directory:** `D:\AI_Science\antigravity\native_linked_integer_20261124\`  
**Authoring Date:** 2026-11-24  
**Status:** **CORRECTED PRE-OUTCOME PLAN — FROZEN BEFORE ANY `p50` EXECUTION.** All `p26` artifacts (`p26_integer_raw.json`, `p26_integer_evaluated.json`, smoke JSONs, `INTEGER_KILL_TEST_PROTOCOL.md`, `linked_benders_integer_p26.py`, `evaluate_p26_integer_run.py`), closed fractional-root archive PR #5, and all `experiments/` files remain untouched.

---

## 1. Case Selection & Non-Outcome Rationale (`p50`)

- **Selected Case**: Sealed Díaz **`p50`** (`experiments/diaz_lost_sales/p50.json`, loaded via frozen `experiments/linked_root/run_root.py:load_case("p50")`):
  - Dimensions: **30 real facilities × 90 customers × 200 equally weighted scenarios** ($2^{30} \approx 1.07 \times 10^9$ binary layouts; $2.7\times$ `p26`'s $20 \times 50$ arc count per scenario).
  - Sealed input hashes (`experiments/diaz_lost_sales/manifest.json`): `raw_sha256 = ce29c3e32f4fb5815b8c3d1ea5a870bd6f483cf9a5efae5289bd89211d45fa41`, `instance_sha256 = 957d0068abbda7e02d767fb93290dd6b8ebf30a172718a4cd03565f715106ba7`, `scenario_sha256 = 1b8bfd97d5ee7c59dbbcbda1d114fde436f27e5989921a42601453ef3cb32280`.
  - Non-outcome structural profile: `nominal_total = 1773`, `all_open_real_capacity = 6145` (`nominal_capacity_ratio = 6145/1773 ≈ 3.466`, vs. `1.721` on `p26`), `minimum_total_demand = 1368.7`, `peak_demand = 2177.3`, `dummy_capacity = 2178`, `uniform_penalty_exact = 5683/30 ≈ 189.433` (vs. `24.727` on `p26`).
- **Why `p50` Over Every Other Existing Sealed Public Case in Workspace (Strictly Non-Outcome)**:
  1. Already pre-designated as the single scale-up check in `INTEGER_KILL_TEST_PROTOCOL.md` and shares the exact frozen `run_root.load_case` + `experiments/liu_lost_sales/solve.py:verify` exact verifier schema with zero new adapter drift.
  2. Other local sealed families are structurally mismatched for this bounded single-tree test: `liu_lost_sales` ($10 \times 20 \times 36$) has only $2^{10}=1{,}024$ layouts (trivial like `p01`); `brescia_lost_sales` ($1000 \times 1000$) is deterministic single-scenario; `adaptive_early` ($100 \times 100 \times 200$, $200 \times 200 \times 200$) and `scotland_lost_sales` ($50 \times 440 \times 200$) have per-sweep LP times too large for bounded single-tree `GSCIP` callbacks; `bodur_holmberg_transfer` ($1{,}500$ scenarios) uses non-lost-sales capacity-feasible recourse; `kothari_lost_sales` ($35 \times 105 \times 400$) requires a new adapter and $2.5\times$ heavier sweeps and is deferred unless `p50` passes.
- **Upfront Structural Caveats (Disclosed Pre-Outcome)**:
  - `p50` has much looser all-open capacity (`6145` vs. peak `2177.3`) than `p26`, so shortage hinges $h_s(x) > 0$ may be observed as inactive across many sampled/evaluated layouts; we explicitly log hinge activity strictly for the **sampled/evaluated layouts** (never asserting inactivity across unsampled layouts).
  - Earlier workspace experiments noted a different prior seed already matched `p50`'s sealed optimum. Our mechanical cold seed is generated purely from model inputs without prior reference access; Section 5 pre-specifies how an exact-incumbent tie is evaluated truthfully without claiming an incumbent-finding win.

---

## 2. Four-Arm Attribution Design, Algebra, and Fairness Proof

All four arms solve the **identical binary proportional-arc linked stochastic CFLP** ($x \in \{0,1\}^{30}$, $0 \le y_{sij} \le x_i d_{sj}$, $\sum_j y_{sij} \le u_i x_i$, $\sum_{i=0}^{30} y_{sij} = d_{sj}$) inside **one** `GSCIP` branch-and-bound tree (`solve_calls == 1`, zero outer restarts, zero root LP warm-up), using the identical symmetric 1D capacity-dual lifted linked LP oracle (`linked_benders_pilot.evaluate_candidate`). Let $h_s(x) := \max\bigl(0,\, D_s - \sum_{i=0}^{n-1} \min(u_i, D_s) x_i\bigr)$ and $\kappa := \frac{\rho - \eta}{\mathrm{div}} > 0$ where $\eta = \max_{i,j} c_{ij}$ (in exact cost ticks).

| Arm | Pricing | Cuts | GSCIP Master Variables | Upfront Shortage Rows | Master Objective |
|---|---|---|---|---|---|
| **A1 — `orig_single`** | Original ($\rho$) | Single | $x \in \{0,1\}^n$, $\theta \ge 0$ | None | $\min\; f^\top x + \theta$ |
| **A2 — `orig_multi_floor`** | Original ($\rho$) | Multi ($S$) | $x \in \{0,1\}^n$, $\theta_s \ge 0$ | $\theta_s \ge \kappa\bigl(D_s - \sum_i \min(u_i,D_s)x_i\bigr)$ ($\forall s$) | $\min\; f^\top x + \sum_{s=0}^{S-1} \theta_s$ |
| **A3 — `orig_single_hinge_floor`** *(Matched Attribution Control)* | Original ($\rho$) | Single | $x \in \{0,1\}^n$, $h_s \in [0, D_s]$, $\theta \ge 0$ | $\sum_i \min(u_i,D_s)x_i + h_s \ge D_s$ ($\forall s$); $\theta \ge \kappa \sum_{s=0}^{S-1} h_s$ | $\min\; f^\top x + \theta$ *(open cost + $\theta$ ONLY)* |
| **B — `sep_single_hinge`** *(Candidate)* | Residual ($\eta$) | Single | $x \in \{0,1\}^n$, $h_s \in [0, D_s]$, $\theta_{\mathrm{res}} \ge 0$ | $\sum_i \min(u_i,D_s)x_i + h_s \ge D_s$ ($\forall s$) | $\min\; f^\top x + \kappa \sum_{s=0}^{S-1} h_s + \theta_{\mathrm{res}}$ |

### Algebraic Validity & Zero-Double-Counting Proof for Matched Control A3 (`orig_single_hinge_floor`)
1. **Valid Lower Bound**: Fix any $x \in [0,1]^n$ and scenario $s$, and let $y^{\mathrm{orig}}$ be an **optimal original-price linked flow** attaining $Q_s^{\mathrm{orig}}(x) = \mathrm{cost}_s^{\mathrm{orig}}(y^{\mathrm{orig}})$. Because $y^{\mathrm{orig}}$ is feasible for the linked recourse constraints, $\sum_j y_{sij}^{\mathrm{orig}} \le \min(u_i, D_s) x_i$ for each real site $i$, so total real shipments satisfy $\sum_{i,j} y_{sij}^{\mathrm{orig}} \le \sum_i \min(u_i, D_s) x_i$ and unmet demand (dummy shipment) satisfies $y_{s,\mathrm{dummy}}^{\mathrm{orig}} \ge h_s(x)$. Since all unit shipping costs $c_{ij} \ge 0$ and $\rho > \eta \ge 0$, splitting the dummy arc price as $\frac{\rho}{\mathrm{div}} = \kappa + \frac{\eta}{\mathrm{div}}$ yields:
   $$Q_s^{\mathrm{orig}}(x) \;=\; \mathrm{cost}_s^{\mathrm{orig}}(y^{\mathrm{orig}}) \;=\; \kappa\, y_{s,\mathrm{dummy}}^{\mathrm{orig}} + \mathrm{shipping}_s^{\mathrm{res}}(y^{\mathrm{orig}}) \;\ge\; \kappa\, h_s(x) + Q_s^{\mathrm{res}}(x) \;\ge\; \kappa\, h_s(x).$$
   Summing over $s = 0, \dots, S-1$ gives $\sum_{s=0}^{S-1} Q_s^{\mathrm{orig}}(x) \ge \kappa \sum_{s=0}^{S-1} h_s(x)$.
2. **Zero Double Counting & Matched GSCIP Master Bounds**: In Arm A3, the objective is strictly $f^\top x + \theta$ (the hinges $h_s$ carry objective coefficient $0$). For any fixed $x \in [0, 1]^n$, reducing any feasible vector $h$ to its minimal feasible vector $h_s(x) = \max(0, D_s - \sum_i \min(u_i, D_s) x_i) \in [0, D_s]$ preserves all hinge rows and never increases the floor RHS $\kappa \sum_s h_s$ or worsens the objective $f^\top x + \theta$. Thus at master optimality $\theta = \max\bigl(\kappa \sum_s h_s(x),\; \max_r (a_r^{\mathrm{orig}} + (g_r^{\mathrm{orig}})^\top x)\bigr) \le \sum_s Q_s^{\mathrm{orig}}(x)$ with zero double charging. In the actual **GSCIP masters**, both **A3** and **B** retain the identical matched variable bounds $h_s \in [0, D_s]$.
3. **Exact Fair-Comparison Contrast (`A3` vs. `B`)**: Arms A3 and B have the **exact same variable count** ($n + S + 1$), the **exact same variable bounds** $h_s \in [0, D_s]$, the **exact same 200 upfront scalar hinge inequalities**, and the **exact same single-cut epigraph dimension** ($1$ lazy cut per violated callback). The **only** mathematical difference is original pricing $\rho$ with a $\max$-floor ($\max(\kappa \sum_s h_s(x), \max_r \ell_r^{\mathrm{orig}}(x))$) vs. additive residual separation ($\kappa \sum_s h_s(x) + \max_r \ell_r^{\mathrm{res}}(x)$) at $\eta$.
4. **Exact Rational Cut-LP Lower Bound Certification for A3 (No Upper Bounds $h_s \le D_s$ in Cut-Pool LP)**: In A3's post-solve cut-pool LP ($\min f^\top x + \theta$ over $x \in [0, 1]^n$, $\theta \ge 0$, and $h_s \ge 0$ **without upper bounds $h_s \le D_s$**), removing $h_s \le D_s$ is exactly equivalent to keeping $h_s \in [0, D_s]$ because for every feasible $(x, \theta, h)$, replacing $h$ with its minimal feasible vector $h_s(x) \in [0, D_s]$ remains feasible and never tightens $\theta \ge \kappa \sum_s h_s$ or worsens $f^\top x + \theta$. Without upper bounds on $h_s$, there are no upper-bound dual multipliers on $h_s$: letting $\mu_s \ge 0$ be the hinge-row multipliers, $w_{\mathrm{fl}} \ge 0$ the single floor-row multiplier, and $w_r \ge 0$ the original cut-row multipliers, LP dual feasibility gives directly $w_{\mathrm{fl}} + \sum_r w_r \le 1$ and $0 \le \mu_s \le w_{\mathrm{fl}} \kappa$. Setting $\bar{\alpha}_{sj} = \mu_s + \sum_r w_r \alpha_{r,sj} \le (w_{\mathrm{fl}} + \sum_r w_r)\frac{\rho}{\mathrm{div}} \le \frac{\rho}{\mathrm{div}}$ and $\bar{\beta}_{si} = (-\mu_s \mathbf{1}_{u_i \le D_s}) + \sum_r w_r \beta_{r,si} \le 0$ yields an exact valid original-price dual witness for frozen `certify.py` whose exact rational lower bound is guaranteed $\ge$ A3's cut-pool LP dual bound by concavity of $g_{si}(\alpha, \beta)$.

---

## 3. Train-Free Cold Seed, Matched Caps, and Callback Hygiene

- **Train-Free Mechanical Cold Seed (Zero Leakage)**: Generated inside the cold worker purely from `p50` model inputs `(capacities, opening, demands)` by sorting real sites $i \in \{0,\dots,29\}$ by ascending `(opening[i] / capacities[i], i)` and opening greedily until $\sum u_i \ge \text{peak\_demand}$. **No prior `p50` seed, layout, or optimum file is ever readable by the cold worker (`worker_saw_reference_files = false`).** Its initial 200-scenario evaluation is charged equally inside each arm's wall clock, and its single initial cut (1 cut in A1/A3/B; 200 cuts in A2) seeds the single `GSCIP` master. The raw worker artifact explicitly records matched initial seed identity (`bits`, `open_count`, `seed_sha256`, `matches_shared_cold_seed`) and itemized per-phase timings (`cold_seed_eval`, `master_build`, `gscip_wall`, `callback_subproblem_total`, `callback_overhead_excluding_subproblems`, `best_incumbent_found_at`, `before_certification`, `worker_grid_fallback_certification`, `worker_cutlp_certification`).
- **Resource & Solver Caps**:
  - Backend: `ortools.math_opt` + `SolverType.GSCIP` (`solve_calls == 1`), `scipy.optimize.linprog(method="highs-ds")`, pinned `Python 3.14.10` / `site314`, `threads = 1`, pinned **CPU 26**.
  - Per-arm wall-clock cap: **`120.0 s`** for the full validation run (non-outcome scale adjustment for `30 × 90 × 200` being $2.7\times$ `p26`'s $20 \times 50 \times 200$ arc count; outer worker timeout `580 s`). Separate plumbing smoke uses `--time-limit 10`, outer `100 s`, and separate smoke output filenames (`p50_integer_smoke_raw.json`, `p50_integer_smoke_evaluated.json`).
  - Tolerances: unchanged `cut_tol = 1e-6`, `rel_gap_tol = 1e-6`.
  - Fixed arm order recorded transparently: `orig_single`, `orig_multi_floor`, `orig_single_hinge_floor`, `sep_single_hinge`.
- **Callback & Termination Hygiene**:
  - Test the **actual generated projected valid cut row** `a + g @ x_raw - theta > cut_tol` at callback values `(x_raw, theta)`; normalize to binary `x_bin` only to query linked subproblems.
  - Preserve verbatim `termination.reason`, `termination.limit`, `termination.detail`, separating `hit_mathopt_time_limit` (`limit == TIME` under `FEASIBLE`/`NO_SOLUTION_FOUND`) from `hit_own_callback_deadline`.
  - Log all numerical discrepancies transparently: `max_integrality_deviation`, `large_integrality_deviation_calls (> 1e-5)`, `unseparated_material_discrepancy_calls` (checking both per-scenario and summed multi-cut discrepancy when `added_here == 0`), `max_unseparated_material_discrepancy`, `max_subproblem_duality_err`, `max_pointwise_identity_diff`, plus **observed sampled-layout shortage-hinge activity counts** (`sampled_layouts_with_positive_hinge`, `mean_positive_hinge_scenarios_across_sampled_layouts`, `max_positive_hinge_scenarios_sampled`, `final_layout_positive_hinge_scenarios`).
  - Label **all** floating-point termination statuses, `best_objective_bound`, and MIP gaps strictly as **numeric diagnostics** (`numeric_mip_dual_bound_diagnostic_not_exact_proof`, `numeric_mip_gap_diagnostic`), never as exact rational proofs.

---

## 4. Reference-Only-On-Evaluation Boundary & Exact Repricing

1. **Cold Worker (`linked_benders_integer_p50.py`)**: Produces `p50_integer_raw.json` (or `p50_integer_smoke_raw.json` for smoke). Never opens `experiments/diaz_lost_sales/p50_rival_continuation.json`, `p50_seed.json`, `p50_original.json`, `p50_separated.json`, or `experiments/linked_root/runs_45s/p50_*.json`.
2. **Standalone Post-Run Evaluator (`evaluate_p50_integer_run.py`, run strictly after worker exits)**: Produces `p50_integer_evaluated.json` (or `p50_integer_smoke_evaluated.json` for smoke).
   - Reprices each **distinct** final binary layout **once** (equal post-run cap `60 s` per distinct layout, outside search clocks) via frozen `experiments/liu_lost_sales/solve.py:verify(data, layout_with_dummy, deadline)` with fixed dummy `30` appended, requiring **`exact_scenarios == 200`**.
   - Retains `certify.py` grid repair strictly as auxiliary feasible upper fallback (never qualifying for exact zero incumbent gap; trimmed grid ticks logged without invalidating feasibility). Incomplete exact repricing triggers `verdict = "inconclusive_incomplete_exact_repricing"`.
   - Reads the separately sealed `p50` exact IP reference (`experiments/diaz_lost_sales/p50_rival_continuation.json`, strictly verified to satisfy exact `global_lower == global_upper` before use) ONLY post-run to compute `post_run_exact_reference_incumbent_gap`. Also checks `L_cert_LP <= U_exact_IP` (and `<= U_ref_LP` if `p50_linked_separated.json` contains a finite rational LP upper bound).

---

## 5. Pre-Specified Search Gate, Attribution Criteria, and Failure/Closure Thresholds

1. **Validity & Numerical Integrity Gate (All 4 Arms)**:
   - Required for every arm: `solve_calls == 1`, `is_binary_opening == true`, `exact_repricing_complete == true` (`200/200`), `U_exact_IP >= z_ref_exact_IP`, `U_grid >= U_exact_IP`, `L_cert_LP <= U_exact_IP`, `large_integrality_deviation_calls == 0`, and `max_unseparated_material_discrepancy <= 1e-4`. Any violation renders the run inconclusive (`inconclusive_invalid_or_suspect_arm`) with zero advancement claim.
2. **Branch 1 — Qualifying-Optimality Antecedent (Numeric `OPTIMAL` + Exact Zero Incumbent Gap)**:
   - **Antecedent**: Applies **only** when Arm B AND at least one original comparator (`A1`, `A2`, or `A3`) terminate numerically `OPTIMAL` with `exact_repricing_complete == true` and `post_run_exact_reference_incumbent_gap == 0` within `120 s`.
   - **Pass Thresholds (All Three Original Comparators)**: Arm B passes **only if** it reduces unique binary subproblem sweeps by **at least 25% AND at least 5 sweeps** relative to **every** original arm (`sw_B <= 0.75 * sw_k` and `sw_k - sw_B >= 5` for ALL $k \in \{\text{A1, A2, A3}\}$), **AND** achieves at least **20% shorter search wall time** (`before_certification_seconds <= 0.80 * t_k` for ALL $k \in \{\text{A1, A2, A3}\}$).
   - **Branch 1 Closure**: When Branch 1's qualifying-optimality antecedent holds and Arm B fails either the sweep or timing gate against any of `A1`, `A2`, or `A3`, close the single-tree separation superiority claim on `p50`.
3. **Branch 2 — Distinct Timeout / Incomplete / Mixed Evidence Rules (When Branch 1's Antecedent Does NOT Hold)**:
   - All termination statuses, dual bounds, and MIP gaps in Branch 2 are **numeric floating-point diagnostics**, not exact rational global proofs.
   - **2a (Numeric-Termination Dominance)**: Arm B terminates numerically `OPTIMAL` with `exact_repricing_complete == true` and `post_run_exact_reference_incumbent_gap == 0` while **all three** original arms (`A1`, `A2`, `A3`) fail to reach numeric `OPTIMAL` with numeric MIP gap `>= 0.25%` (or suboptimal exact incumbent).
   - **2b (Exact Incumbent + Numeric Gap Dominance when incumbents differ)**: Arm B's exact-repriced $U_{\mathrm{exact}}^{\mathrm{IP}}$ beats **all three** original arms by `>= 0.10%` of $z_{\mathrm{ref,exact}}^{\mathrm{IP}}$ AND its numeric MIP gap diagnostic is at least `0.25` percentage points lower than **all three** original arms.
   - **2c (Exact-Incumbent-Tie Timeout Regime, e.g., Optimal Cold Seed)**: If all 4 arms tie the exact optimal incumbent (`post_run_exact_reference_incumbent_gap == 0` for all 4, including if the mechanical cold seed itself is already optimal), **do NOT claim an incumbent-finding win**; evaluate truthfully on sweeps, search time, `L_cert_LP`, and numeric MIP dual-bound gap diagnostics. Where **no** arm reaches numeric `OPTIMAL` within `120 s` under an exact-incumbent tie, pass requires Arm B's numeric MIP gap diagnostic to be `>= 0.25` percentage points lower than **all three** original arms (`A1`, `A2`, `A3`) without exceeding their sweep count; otherwise classify truthfully as **inconclusive / non-separating at 120 s** (if unresolved) or **closure** (if A3 or A2 matches/beats B on numeric gap and dual-bound progress).
4. **Explicit Attribution & Scope Boundaries (No Retroactive `p26` Causal Overclaim)**:
   - **Hinge-Control Matching (`A3` matches or outperforms `B` on `p50`)**: If matched single-cut control **A3 (`orig_single_hinge_floor`)** matches or outperforms **B (`sep_single_hinge`)** on `p50` (or B fails the Branch 1 / Branch 2 thresholds against A3), that **blocks generalization and attribution of shortage-price separation** and closes the separation-superiority claim. It does **not** identify what caused the `p26` speedup, because `p26` did not include arm `A3`.
   - **Observed Inactive-Hinge Regime Disclosure**: If shortage hinges are observed to be inactive across the sampled/evaluated `p50` layouts and B provides no advantage, record that observed sampled-layout regime boundary honestly without retuning or expanding to further instances.

---

## 6. Planned Artifacts & Strongest Literature Overlap

- **Code & Output Files**:
  - `linked_benders_integer_p50.py` (cold 4-arm single-tree `GSCIP` worker, zero reference access)
  - `evaluate_p50_integer_run.py` (standalone post-run exact 200-scenario verifier & 4-arm gate scorer)
  - Plumbing smoke (non-decision): `p50_integer_smoke_raw.json`, `p50_integer_smoke_evaluated.json` (`--time-limit 10`, outer `100 s`)
  - Full validation (pending explicit authorization after smoke): `p50_integer_raw.json`, `p50_integer_evaluated.json` (`--time-limit 120`, outer `580 s`), `P50_VALIDATION_RESULTS.md`
- **Strongest Literature Overlap (Honest Scope Boundary)**:
  - **Single-tree Branch-and-Benders-Cut (BBC) for CFLP**: Fortz & Poss (2009); Fischetti, Ljubić & Sinnl (2016, *INFORMS JOC*; 2017, *Management Science*); Rahmaniani et al. (2017, *EJOR*).
  - **Proportional-arc linking & strengthened stochastic CFLP formulations**: Cornuéjols, Sridharan & Thizy (1991); Aardal (1998); Bodur, Dash, Günlük & Luedtke (2017, *Mathematical Programming*).
  - **Multi-cut, partial aggregation, and adaptive partition Benders**: Birge & Louveaux (1988); Song & Luedtke (2015, *SIOPT*); Kothari & Luedtke (2026, *Math. Prog. Comp.*).
  - **Narrow Scope**: Tests solely whether shortage-premium separation ($\rho \to \eta$) onto upfront scalar scenario hinges outperforms identical upfront scalar hinges under original pricing (`A3`) and original multi-cut with direct shortage floors (`A2`) inside cold single-tree `GSCIP` on stochastic CFLP with uniform lost-sales penalty — with no claim of generic MIP advantage or retroactive causal attribution for `p26`.
