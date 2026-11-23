# Paired Iterative Linked Benders Root Pilot Protocol — Díaz `p01`

**Handoff Directory:** `D:\AI_Science\antigravity\native_linked_root_execution_20261124\`  
**Authoring Date:** 2026-11-24  
**Execution State:** **Authored only — NOT yet executed** (no terminal execution was run in this authoring turn; awaiting permission-scoped execution via the exact WSL command below).

---

## 1. Research Question

The sealed deterministic-equivalent diagnostic (`experiments/linked_root/runs_45s/`) confirmed interval overlap consistent with the proved pointwise identity between the original-price linked LP (`linked`) and the shortage-separated linked LP (`linked_separated`) on Díaz `p01` and `p26`, while both arms timed out at 45 s on `p50`. However, interior-point deterministic-equivalent timings cannot answer the decomposition question:

> **On the exact same proportional-arc linked feasible region ($y_{sij} \le x_i d_{sj}$), under identical cold candidate budgets, wall-clock caps, and single-threaded solver settings, does exact shortage separation improve finite-iteration iterative Benders root convergence on Díaz `p01` compared to original-price linked Benders?**

A one-off pricing pass at a fixed fractional point or a renamed deterministic-equivalent solve does not answer this question. Both arms must execute genuine iterative Benders cuts along their own separate candidate paths and terminate with independently verifiable exact rational bounds.

---

## 2. Frozen Reusable Inputs (Read-Only, Unmodified)

1. **Sealed Instance (`p01`)**: Loaded via `experiments/linked_root/run_root.py:load_case("p01")` against `experiments/diaz_lost_sales/manifest.json` (expected SHA-256 `9be4fb7962061b5b5a42fc2ff5f67add0788f7e199bc7b577e9c7779aaeeb126`) and `p01.json` (expected SHA-256 `ce90c54559f0f341f03cbb2d91ef0ca0a3148217243cb016e8a00d37fbda351b`).
   - Dimensions: $n = 10$ real facilities (+ 1 uniform dummy), $m = 20$ customers, $S = 200$ scenarios.
   - Sharp uniform linked separation price (matching `root_model.py` and `certify.py`): $\eta = 2\max_{i < n,\, j < m} c_{ij} = 603{,}144{,}360$ ticks ($\eta \le \rho$).
2. **Exact Rational Verifier**: `experiments/linked_root/certify.py:certify(...)` (`OPEN_GRID = 10**9`, `DUAL_GRID = 10**8`).
3. **Independent Sealed Reference Interval** (read-only from `experiments/linked_root/runs_45s/p01_linked.json` and `p01_linked_separated.json`):
   - Sealed linked lower bound: `993313149261992936213/436486050000000000` ($\approx 2275.7042275738$).
   - Sealed linked-separated upper bound: `1168603705040907101521/513513000000000000` ($\approx 2275.7042276260$).
   - Intersection reference interval $I_{\mathrm{ref}}(\text{p01})$ has exact width $\approx 5.2185 \times 10^{-8}$.

---

## 3. Paired Formulation on the Shared Proportional-Arc Linked Polytope

Both arms optimize over the **exact same continuous fractional opening domain** $x \in [0, 1]^n$ and enforce the **exact same scenario flow polytope** for every $s \in \{0, \dots, S-1\}$:
$$\sum_{i=0}^{n} y_{sij} = d_{sj} \;\; (\forall j), \qquad \sum_{j=0}^{m-1} y_{sij} \le u_i x_i \;\; (\forall i < n), \qquad 0 \le y_{sij} \le d_{sj} x_i \;\; (\forall i < n, j), \qquad y_{snj} \ge 0.$$

### Arm A — Original-Price Linked Benders (`linked`)
- **Subproblem $Q_s^{\mathrm{orig}}(x)$**: Linked transportation LP on scenario $s$ with dummy unit price $\rho / \mathrm{div}$ (proportional arc links $y_{sij} \le d_{sj} x_i$ enforced as exact variable upper bounds; capacity rows $\sum_j y_{sij} \le u_i x_i$; demand rows $\sum_i y_{sij} = d_{sj}$).
- **Master LP**: Variables $x \in [0, 1]^n$ and epigraph variable(s) $\theta \ge 0$ (single-cut) or $\theta_s \ge 0$ for $s=0,\dots,S-1$ (multi-cut). Minimizes $f^\top x + \theta$ (or $f^\top x + \sum_s \theta_s$) subject to accumulated Benders optimality cuts $\theta_s \ge a_s^{(k)} + \sum_i g_{si}^{(k)} x_i$ (or aggregated $\theta \ge \sum_s a_s^{(k)} + \sum_i (\sum_s g_{si}^{(k)}) x_i$).

### Arm B — Separated Linked Benders (`linked_separated`)
- **Exact Scalar Shortage Hinges in Master**: Variables $h_s \ge 0$ ($s=0,\dots,S-1$) with the $S = 200$ linear constraints
  $$-\sum_{i=0}^{n-1} \min(u_i, D_s)\, x_i - h_s \le -D_s,$$
  priced at $(\rho - \eta)/\mathrm{div}$ directly in the master objective from iteration 0.
- **Subproblem $Q_s^{\mathrm{res},\eta}(x)$**: Identical linked transportation polytope on scenario $s$, with reduced dummy unit price $\eta / \mathrm{div}$.
- **Master LP**: Minimizes $f^\top x + \frac{\rho-\eta}{\mathrm{div}}\sum_s h_s + \theta_{\mathrm{res}}$ (single-cut) or $+\sum_s \theta_s^{\mathrm{res}}$ (multi-cut) subject to the $S$ exact scalar hinges and accumulated residual Benders cuts.

### Symmetric Dual-Cut Generation (Identical for Both Arms)
At every candidate $x^{(k)} \in [0, 1]^n$ and scenario $s$, the subproblem is solved by single-threaded HiGHS dual simplex (`highs-ds`, fallback `highs`). Let $\alpha_{sj} = \min(\max(0, \text{demand\_marginal}_{sj}),\, \text{dummy\_price})$. For each facility $i < n$, the capacity dual $\beta_{si} \le 0$ is lifted by the exact 1D piecewise-linear maximizer $\beta_{si}^* = \arg\max_{\beta \le 0}\big(u_i \beta + \sum_j d_{sj}\min(0, \tilde{c}_{ij} - \alpha_{sj} - \beta)\big)$ (eliminating arbitrary dual degeneracy when $x_i^{(k)} = 0$ while remaining strictly dual-feasible and exact at $x^{(k)}$), with $\gamma_{sij}^* = \min(0, \tilde{c}_{ij} - \alpha_{sj} - \beta_{si}^*)$. The resulting cut is
$$a_s = \sum_{j=0}^{m-1} \alpha_{sj} d_{sj}, \qquad g_{si} = u_i \beta_{si}^* + \sum_{j=0}^{m-1} d_{sj} \gamma_{sij}^* \le 0.$$

---

## 4. Cold Candidate Policy, Budgets, and Cut-Aggregation Regimes

- **Strictly Cold Start**: Both arms start with **zero Benders cuts**, zero warm-start hints from the deterministic equivalent, and identical solver settings (`threads=1`, single-threaded BLAS/OpenMP). Each arm generates its own independent sequence of candidates $\{x_{\text{arm}}^{(k)}\}$ from its own master LP.
- **Cut Modes (`--cut-mode`)**:
  - `multi`: Per-scenario epigraph variables $\theta_s \ge 0$ ($s=0,\dots,199$), adding violated per-scenario cuts at each candidate evaluation.
  - `single`: One aggregated epigraph variable $\theta \ge 0$, adding one aggregated cut per candidate evaluation.
  - `both`: Runs the matched `multi` pair and the matched `single` pair sequentially under identical per-arm budgets (default for `--mode full`).
- **Two Run Profiles**:
  - **Smoke mode (`--mode smoke`)**: `--cut-mode multi`, `--max-iters 4` candidate evaluations per arm, `--time-limit 15` s per arm, `--rel-tol 1e-6`, writing `pilot_smoke_result.json`.
  - **Bounded full pilot (`--mode full`)**: `--cut-mode both`, `--max-iters 60` candidate evaluations per arm, `--time-limit 30` s per arm, `--rel-tol 1e-6`, writing `pilot_full_result.json`.
- **Secondary Fixed-History Check (Clearly Segregated)**: After the primary independent-path paired runs finish (outside primary arm clocks), up to 8 distinct iterates from each arm's path are cross-evaluated under both original and separated subproblems to verify the pointwise objective identity $|F_{\mathrm{orig}}(x) - F_{\mathrm{sep}}(x)|$ on visited fractional iterates without conflating fixed-history pricing with independent-path convergence.

---

## 5. Exact Rational Certification and Explicit Fractional vs. Integer Distinction

At termination (whether converged to `rel_tol`, hit `max_iters`, or hit `time_limit`), each arm certifies its own bounds independently through the frozen `certify.certify(...)`:
1. **Primal Fractional Upper Bound ($U_{\mathrm{cert}}$)**: Exact rational flow repair (`OPEN_GRID = 10**9`) of the arm's best evaluated fractional opening $x_{\mathrm{best}} \in [0, 1]^n$ and its scenario flows `shipping_best`, plus `original_same_primal` evaluated at the full original shortage price $\rho$.
2. **Dual Lower Bound ($L_{\mathrm{cert}}$)**: Constructed directly from the master LP's final dual weights $\lambda_r = \max(0, -\text{cut\_marginal}_r)$ (normalized only if $\sum \lambda_r > 1$ due to floating-point tolerance) forming convex combinations $\bar{\alpha}_{sj} = \sum \lambda_r \alpha_{sj}^{(r)}$ and $\bar{\beta}_{si} = \sum \lambda_r \beta_{si}^{(r)}$ (plus master hinge marginals `shortage_marginals` in `linked_separated`), projected onto exact rational dual feasibility (`DUAL_GRID = 10**8`).
3. **Soundness & Reference Compatibility Assertions**:
   - Exact internal soundness: $L_{\mathrm{cert}} \le U_{\mathrm{cert}}$.
   - Independent sealed-reference compatibility: $L_{\mathrm{cert}} \le U_{\mathrm{ref}}(\text{p01})$ and $U_{\mathrm{cert}} \ge L_{\mathrm{ref}}(\text{p01})$ (certified interval overlaps $I_{\mathrm{ref}}(\text{p01})$).

> **Explicit Scope of Interim and Final Bounds (Fractional vs. Integer)**  
> Every candidate $x^{(k)} \in [0, 1]^n$ in this pilot belongs to the **continuous fractional root relaxation**.
> - Every certified lower bound $L_{\mathrm{cert}}$ is a valid lower bound on both the continuous fractional LP relaxation optimum $z^*_{\mathrm{LP}}$ and the binary integer MIP optimum $z^*_{\mathrm{IP}}$.
> - Every interim or final primal upper bound $U_{\mathrm{cert}}$ is a feasible upper bound **only on the continuous fractional root LP relaxation** ($x \in [0, 1]^n$). Unless `is_binary_opening == true` (all entries $0$ or `OPEN_GRID`), $U_{\mathrm{cert}}$ is **NOT** a feasible integer solution ($x \in \{0, 1\}^n$) and must never be reported as an integer incumbent.

---

## 6. Exact Run Commands & Execution Status

- **Runtime**: WSL Python `/home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14` with `PYTHONPATH=/home/ailab/frontieror_letelier_runtime_20261124/site314`.
- **Execution Status as of This Turn**: **NOT EXECUTED YET** (file-tools-only authoring turn; no process started, no result JSON generated yet).

### Exact Smoke Command (Recommended First Check)
```bash
PYTHONPATH=/home/ailab/frontieror_letelier_runtime_20261124/site314 \
  /home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14 \
  /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/linked_benders_pilot.py \
  --mode smoke \
  --out /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/pilot_smoke_result.json
```

### Exact Bounded Full Pilot Command
```bash
PYTHONPATH=/home/ailab/frontieror_letelier_runtime_20261124/site314 \
  /home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14 \
  /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/linked_benders_pilot.py \
  --mode full \
  --out /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/pilot_full_result.json
```

---

## 7. Decision Rules After Execution

- Both arms must pass exact `certify.py` soundness and overlap $I_{\mathrm{ref}}(\text{p01})$ before any performance comparison is interpreted.
- Any timeout or iteration-cap termination is reported strictly via its certified fractional interval $[L_{\mathrm{cert}}, U_{\mathrm{cert}}]$ and certified gap, never treated as converged.
- Only if the paired `p01` pilot shows a verified, consistent finite-budget advantage (or clear structural separation) across matched budgets and cut modes will an expansion to `p26` be proposed; otherwise, the `p01` paired outcome is reported directly without overclaiming.
