# Single-Tree Lazy Integer Linked Benders Kill-Test Protocol (`p26`)

**Working Directory:** `D:\AI_Science\antigravity\native_linked_integer_20261124\`  
**Authoring Date:** 2026-11-24  
**Execution Status:** **Protocol, cold single-tree worker (`linked_benders_integer_p26.py`), and separate post-run evaluator (`evaluate_p26_integer_run.py`) authored; capability probe verified (`solver_capability_probe.json`); main `p26` benchmark NOT YET EXECUTED** (awaiting coordinator inspection of source entry points).  
**Immutable Predecessors (Untouched):**
- Closed fractional-root archive PR #5 (`https://github.com/ArtificialZeng/Operations-Research/pull/5`) and `D:\AI_Science\antigravity\native_linked_root_execution_20261124\`.
- Frozen `experiments/diaz_lost_sales/`, `experiments/linked_root/`, `experiments/liu_lost_sales/`, and `experiments/bodur_holmberg_transfer/`.

---

## 1. Verified Local Solver Capability Evidence (True Single-Tree Lazy Callbacks)

Empirically probed in `/home/ailab/frontieror_letelier_runtime_20261124/site314` (`Python 3.14.10`, `ortools 9.15.6755`, `highspy 1.15.1`, `scipy 1.18.1`, `numpy 2.5.3`) via `probe_solver_capabilities.py` -> `solver_capability_probe.json`:

- **Initial Error & Corrected Verification**: An earlier invocation passed `cb_reg=` instead of `callback_reg=` and hit a Python `TypeError` prior to invoking any solver. Correcting to `callback_reg=` verified **`ortools.math_opt` + `SolverType.GSCIP`** (SCIP inside `ortools 9.15.6755`):
  - Single-cut 2-binary toy MIP: `OPTIMAL`, objective `6.0`, `best_objective_bound = 6.0`, `solve_calls = 1`, `callback_calls = 9`, `lazy_cuts_added = 2` sequential cuts inside one tree.
  - Multi-cut lazy callback calling `scipy.optimize.linprog(..., method="highs-ds")` inside the callback: `OPTIMAL`, objective `6.0`, `callback_calls = 7`, `lazy_cuts_added = 2`, `scipy_lp_solves_inside_cb = 14`.
  - Other backends' packaging/wrapper errors (`math_opt[HIGHS/GLPK/CP_SAT]` `StatusNotOk` wrapper `AttributeError`; `highspy`/`ortools` shared-library symbol collision) are environment limitations, not mechanism tests.
- **Selected Backend**: **`ortools.math_opt` + `SolverType.GSCIP`** (`solve_calls == 1` strictly enforced; zero outer MIP restarts), paired with single-threaded `scipy.optimize.linprog(..., method="highs-ds")` inside `MIP_SOLUTION` callbacks.

---

## 2. Why `p26` Only First & Guard Against Rediscovery

Existing `experiments/diaz_lost_sales/PROTOCOL.md` and `RESULT.md` already evaluated **outer-loop adaptive MIP** (repeated MIP solves with scenario partition refinement) at 60 s:
- **`p01`**: Exhausted (1,024 layouts enumerated in `~4.5 s`).
- **`p50`**: Prior seed objective `110941759969/16087500` **already equals the sealed exact global optimum**, saturating incumbent-quality metrics.
- **`p26`** ($20 \times 50 \times 200$, $2^{20} = 1{,}048{,}576$ binary layouts): Earlier `p26` seed was **not** optimal; continuous linked root (`5531.134290`) sits strictly below the binary optimum (`5558.540868`, integrality gap `+27.41` $\approx 0.493\%$), forcing genuine binary branching; one 200-scenario linked LP sweep takes `~0.56 s` on CPU 26. Earlier 60 s outer adaptive MIP reached `1.428669%` certified gap (`16.527 s`, `1,086` cuts) for original vs. `1.330593%` (`14.340 s`, `738` cuts) for separated.

This pilot tests **`p26` only** under **true one-tree execution (`solve_calls == 1`)** with zero outer MIP restarts and zero access to prior seeds, layouts, or optima inside cold workers.

---

## 3. Cold, Resource-Matched Three-Arm Binary Design (`p26`)

All three arms load sealed `p26` via read-only `experiments/linked_root/run_root.py:load_case("p26")` (`input_sha256 = c8573d88fe95131ab6b473c0fa1dbb29d7381918044ca845c34bbe59df420e66`), enforce **identical proportional-arc linked recourse** ($0 \le y_{sij} \le x_i d_{sj}$, $\sum_j y_{sij} \le u_i x_i$, $\sum_{i=0}^{20} y_{sij} = d_{sj}$) inside `MIP_SOLUTION` callbacks with symmetric 1D capacity-dual lifting, and share identical single-core resources (`threads=1`, pinned CPU 26, `60.0 s` wall-clock cap per arm).

### Shared Deterministic Model-Input-Only Cold Seed (Equally Charged Inside 60 s Clock)
Using **only** `p26` model inputs `(capacities, opening_costs, demands)` (never reading prior seeds, optima, or layout files):
- Sort real facilities $i \in \{0,\dots,19\}$ by ascending `(opening[i] / capacities[i], i)` and open greedily until cumulative real capacity $\sum_{i \in S_0} u_i \ge \text{peak\_demand}$ (`1211.3`).
- At `t = 0` inside each arm's 60 s budget, evaluate `x_seed` across all 200 linked subproblems (charging its exact wall time equally), record `x_seed` as initial evaluated binary incumbent, and add its single valid initial Benders cut (1 aggregated cut in A1/B; 200 scenario cuts in A2) before invoking the single `GSCIP` solve for the remaining time `60.0 - seed_seconds`.
- Each arm caches evaluated 20-bit binary layouts inside `MIP_SOLUTION` to avoid duplicate subproblem sweeps on repeated SCIP queries; both total callback calls and unique binary layouts evaluated are logged.

### The Three Arms (All Binary $x \in \{0, 1\}^{20}$, Single `GSCIP` Solve)
1. **Arm A1 — `orig_single` (Plain Original-Price Single-Cut Comparator)**:
   - Master: $x \in \{0, 1\}^{20}$, single aggregated epigraph $\theta \ge 0$ (no extra hinge variables, no upfront shortage floor rows). Objective: $\min f^\top x + \theta$.
   - Callback: 200 original-price ($\rho$) linked subproblems $\to$ adds 1 aggregated original-price lazy cut only when the **projected valid cut** is violated at callback values `(x_raw, theta_val)` by more than `cut_tol = 1e-6`.
2. **Arm A2 — `orig_multi_floor` (Amended Strong Original-Price Multi-Cut Baseline)**:
   - Master: $x \in \{0, 1\}^{20}$, 200 scenario epigraphs $\theta_s \ge 0$ (**no extra hinge variables $h_s$**, no double charging), plus the 200 direct valid per-scenario shortage floor rows giving the **exact same $(\rho - \eta) h_s(x)$ shortage information as Arm B**:
     $$\theta_s \;\ge\; \frac{\rho - \eta}{\mathrm{div}} \left(D_s - \sum_{i=0}^{19} \min(u_i, D_s)\, x_i\right) \qquad (\forall s \in \{0,\dots,199\}),$$
     which together with $\theta_s \ge 0$ enforces $\theta_s \ge \frac{\rho - \eta}{\mathrm{div}} h_s(x)$ cleanly without extra hinge variables. Objective: $\min f^\top x + \sum_{s=0}^{199} \theta_s$.
   - Callback: 200 original-price ($\rho$) linked subproblems $\to$ adds each scenario's lazy cut only when that scenario's **projected valid cut** is violated at callback values `(x_raw, theta_s_val)` by more than `cut_tol = 1e-6`.
3. **Arm B — `sep_single_hinge` (Candidate Separated Residual Single-Cut + Scalar Shortage Hinges)**:
   - Master: $x \in \{0, 1\}^{20}$, 200 scalar shortage hinges $h_s \ge 0$ with $\sum_{i=0}^{19} \min(u_i, D_s) x_i + h_s \ge D_s$ priced at $(\rho - \eta)/\mathrm{div}$ ($\eta = 98{,}508{,}230{,}140{,}320$ ticks), plus single residual epigraph $\theta_{\mathrm{res}} \ge 0$ (no double charging). Objective: $\min f^\top x + \sum_{s=0}^{199} \frac{\rho - \eta}{\mathrm{div}} h_s + \theta_{\mathrm{res}}$.
   - Callback: 200 residual-price ($\eta$) linked subproblems $\to$ adds 1 aggregated residual lazy cut only when the **projected valid cut** is violated at callback values `(x_raw, theta_res_val)` by more than `cut_tol = 1e-6`.

### MathOpt Termination & Cut-Violation Hygiene
- Preserve BOTH `termination.reason.name` (`OPTIMAL`, `FEASIBLE`, `NO_SOLUTION_FOUND`, `INTERRUPTED`, etc.) AND `termination.limit.name` (`TIME`, `INTERRUPTED`, `UNDETERMINED`, etc., plus `termination.detail`). Classify deadlines accurately via `termination_limit == "TIME"` or `termination_limit == "INTERRUPTED"` or `cb_deadline_interrupts > 0` (never assuming `reason == "TIME_LIMIT"`).
- Add lazy constraints strictly when `projected_cut_val(x_raw) - theta_val > cut_tol` using the exact dual-projected cut `(a, g)`.

---

## 4. Two-Stage No-Leakage Verification: Cold Worker vs. Separate Post-Run Evaluator

1. **Cold Worker (`linked_benders_integer_p26.py` — Zero Reference Leakage)**:
   - Never opens `p26_class9_finite.json` or any prior layout/optimum file.
   - Records each arm's single-tree execution, best evaluated binary layout (`open_real_sites`, `bits`), exact rational cut-LP lower bound $L_{\mathrm{cert}}^{\mathrm{LP}}$ from that arm's own generated cuts via frozen `certify.py`, grid-repaired feasible primal fallback via `certify.py` (`trimmed_flow_grid_ticks` logged transparently; trimmed ticks alone do not invalidate a repaired flow), and SCIP's floating-point `best_objective_bound()` explicitly labeled **`numeric_mip_dual_bound_diagnostic_not_exact_proof`**.
2. **Separate Post-Run Evaluator (`evaluate_p26_integer_run.py`)**:
   - Reads only the worker's output JSON, sealed `p26` instance data, and post-run sealed reference `experiments/diaz_lost_sales/p26_class9_finite.json` ($z_{\mathrm{ref,exact}}^{\mathrm{IP}} = 135321426758663/24344775000 \approx 5558.540867955$) + `experiments/linked_root/runs_45s/p26_linked_separated.json` ($U_{\mathrm{ref}}^{\mathrm{LP}}$).
   - **Exact Original-Price Integer Incumbent Repricing**: Deduplicates the distinct final binary layouts reported across the three arms and evaluates each distinct layout **once** (with equal bounded post-processing budget, e.g. `30 s` per distinct layout, strictly outside search clocks) using frozen **`experiments/liu_lost_sales/solve.py:verify(data, layout_with_dummy, deadline)`** (including fixed dummy index `20`, requiring all `200` original scenarios; at a binary layout the proportional arc links reduce identically to the per-customer demand edge capacity in `exact_flow`).
   - **Exact Zero Gap Qualification**: Only an arm with `exact_repricing_complete == true` (`exact_scenarios == 200`) AND exact rational `U_exact_IP == z_ref_exact_IP` qualifies as exact zero incumbent gap (`post_run_exact_reference_incumbent_gap == 0`). If exact repricing times out, `exact_repricing_complete = false` is labeled explicitly and the grid-repaired feasible upper bound from `certify.py` is kept as an upper fallback (never qualifying for exact zero gap).
   - **Strict Separation**: `post_run_exact_reference_incumbent_gap` is reported strictly as an independent post-run incumbent evaluation, never conflated with SCIP's numeric dual bound or claimed as a solver-side exact optimality proof.

---

## 5. Pre-Set Stop / Advancement Decision (Unweakened)

1. **Validity & Single-Tree Gate**: Each arm must satisfy `solve_calls == 1`, `is_binary_opening == true`, `U_incumbent_valid >= z_ref_exact_IP`, `L_cert_LP <= U_incumbent_valid`, and `L_cert_LP <= U_ref_LP(p26)`. Any failed certificate or crash renders that arm inconclusive.
2. **Advancement Gate (Arm B Must Beat BOTH Plain A1 `orig_single` AND Strong Baseline A2 `orig_multi_floor`)**:
   - **Branch 1 (Both Arm B and best original baseline $\text{BestOrig} \in \{\text{A1}, \text{A2}\}$ terminate `OPTIMAL` with `exact_repricing_complete == true` and `post_run_exact_reference_incumbent_gap == 0` within 60 s)**: Arm B motivates follow-up **only if** Arm B reduces **unique binary subproblem sweeps by at least 25% AND at least 5 sweeps** relative to **both** A1 and A2, **and** achieves at least **20% shorter wall time** to `OPTIMAL` than both A1 and A2.
   - **Branch 2 (At least one of Arm B or $\text{BestOrig}$ does not reach `OPTIMAL` within 60 s)**: Arm B motivates follow-up **only if** either (a) Arm B achieves `OPTIMAL` with `exact_repricing_complete == true` and `post_run_exact_reference_incumbent_gap == 0` while **both** A1 and A2 fail to reach `OPTIMAL` with numeric MIP gap `>= 0.25%` (or suboptimal exact incumbent), **or** (b) Arm B's exact-repriced $U_{\mathrm{exact}}^{\mathrm{IP}}$ (`exact_repricing_complete == true`) improves over **both** A1 and A2 by at least **`0.10%` of $z_{\mathrm{ref,exact}}^{\mathrm{IP}}$** (`>= 5.56`) AND Arm B's numeric MIP gap is smaller than both A1 and A2 by at least **`0.25` percentage points**.
3. **Kill / Closure Gate**: If amended strong baseline **Arm A2 (`orig_multi_floor`)** matches or outperforms **Arm B (`sep_single_hinge`)**, or if Arm B fails the Advancement Gate above, **close the single-tree linked integer line immediately** and archive all three arms without retuning or expanding to `p50`.
