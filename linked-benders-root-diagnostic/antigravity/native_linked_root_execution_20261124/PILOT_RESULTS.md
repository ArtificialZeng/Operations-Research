# Paired Iterative Linked Benders Root Pilot Results & Decision — Díaz `p01`

**Handoff Directory:** `D:\AI_Science\antigravity\native_linked_root_execution_20261124\`  
**Run Date:** 2026-11-24  
**Authoritative Evidence Files:**
- Bounded full pilot JSON: `pilot_full_result.json`
- Earlier smoke JSON (preserved unmodified): `pilot_smoke_result.json`
- Executed script (unmodified): `linked_benders_pilot.py` (SHA-256 `eff17d9a81ef08b06705b6d64034f18dedcc4577c7350779b1ddd4ea7be3ed53`)
- Independent sealed DE reference (frozen, read-only): `experiments/linked_root/runs_45s/p01_linked.json` & `p01_linked_separated.json`

---

## 1. Execution & Verification Summary

- **Command Executed**:
  ```bash
  wsl.exe -e /usr/bin/timeout --kill-after=2s 165s /usr/bin/taskset -c 26 /usr/bin/env \
    PYTHONPATH=/home/ailab/frontieror_letelier_runtime_20261124/site314 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    /home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14 \
    -B /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/linked_benders_pilot.py \
    --mode full \
    --out /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/pilot_full_result.json
  ```
- **Exit Status & Environment**: Exit code `0`; total wall time `15.633 s` (well inside `165 s` outer timeout and `30 s/arm` cap); pinned `cpu_affinity: [26]`; Python `3.14.10`, NumPy `2.5.3`, SciPy `1.18.1`; single-threaded cold start (`max_iters = 60`, `rel_tol = 1e-6`, `cut_tol = 1e-7`).
- **Global Soundness & Reference Consistency**:
  - `all_certificates_sound`: **`true`** across all 4 arms (`trimmed_flow_grid_ticks: 0`, `max_subproblem_duality_err <= 1.82e-14`).
  - `all_certificates_overlap_sealed_reference`: **`true`** across all 4 arms against the independent sealed `p01` intersection interval:
    $$I_{\mathrm{ref}}(\text{p01}) = \left[\frac{993313149261992936213}{436486050000000000},\; \frac{1168603705040907101521}{513513000000000000}\right] \approx [2275.704227573809,\; 2275.704227625994] \quad (\text{width } 5.219 \times 10^{-8}).$$
  - **Distinct Candidate Paths Verified**: Both regimes satisfied `paths_distinct: true` (`first_differing_iter: 0`, `max_pointwise_l1_diff: 5.0`, `max_pointwise_linf_diff: 1.0`).
  - **Secondary Fixed-History Pointwise Check** (outside primary arm budgets): Evaluated 6 distinct visited fractional iterates per regime; maximum discrepancy $|F_{\mathrm{orig}}(x) - F_{\mathrm{sep}}(x)|$ was `1.819e-12` in both regimes.

---

## 2. Paired Results by Cut Regime (Continuous Fractional Root Relaxation)

### Regime A — Multi-Cut Benders (`cut_mode = multi`, 200 per-scenario epigraph variables $\theta_s$)

| Metric | `linked` (Original $\rho$) | `linked_separated` ($\eta + 200$ Hinges) | Comparison (`sep` vs. `orig`) |
|---|---:|---:|---|
| Stop Reason | `converged_rel_tol` | `converged_rel_tol` | Both converged cleanly |
| Candidate Evaluations (Iters) | **5** | **5** | **Tie (`0` saved)** |
| Master Solves / Total Cuts | 5 / 637 | 5 / 633 | `-4` cuts (`-0.6%`) |
| Wall Time (pre-cert / total) | **1.418 s** / 1.445 s | 1.437 s / 1.464 s | **`+0.019 s` (`+1.3%` slower)** |
| Master / Subproblem Split | 0.024 s / 1.393 s | 0.024 s / 1.412 s | Subproblem-dominated (`>98%`) |
| Exact Certified Lower $L_{\mathrm{cert}}$ | `2270430055455984227639/997682400000000000` (`2275.7042275738095`) | `993313149261992928319/436486050000000000` (`2275.704227573809`) | Both match $I_{\mathrm{ref}}$ to `~1e-13` |
| Exact Certified Upper $U_{\mathrm{cert}}$ | `9348829640394927708917/4108104000000000000` (`2275.704227642467`) | `9348829640330011808609/4108104000000000000` (`2275.7042276266648`) | `orig_same_primal = 2275.704227642467` |
| Certified Rel. Gap (Width) | `3.017e-11` (`6.866e-08`) | `2.323e-11` (`5.286e-08`) | Both `< 3.1e-11` |
| Sound / Overlaps $I_{\mathrm{ref}}$ | `true` / `true` | `true` / `true` | Fully verified |
| Binary Opening? | `false` (`1` frac. site: `633846154/10^9`) | `false` (`1` frac. site: `633846154/10^9`) | **Fractional LP bound only** |

**Interim Multi-Cut Trajectory**:
- Iteration 0: `linked` starts at $x^{(0)}=\mathbf{0}$ (`LB = 0.00`, `UB = 8337.73`), whereas `linked_separated` opens 5 facilities via the hinges (`LB = 1470.15`, `UB = 3717.92`).
- Iterations 1–3: `linked_separated` holds modestly tighter interim numerical lower bounds (`2141.04` vs. `2128.07`; `2265.89` vs. `2263.05`; `2275.648` vs. `2275.632`), while `linked` has slightly lower candidate upper bounds on iters 1 and 3 (`2288.65` vs. `2290.14`; `2275.7052` vs. `2275.7055`).
- Iteration 4: Both arms land on the exact same optimal fractional opening (`x_hash = b40927a1384b0209`) with `0` violated cuts and converge in **5 total candidate evaluations** (`1.418 s` vs. `1.437 s`, both faster than the sealed DE IPM runs of `2.361 s` / `2.837 s`).

---

### Regime B — Single-Cut Benders (`cut_mode = single`, 1 aggregated epigraph variable $\theta$)

| Metric | `linked` (Original $\rho$) | `linked_separated` ($\eta + 200$ Hinges) | Comparison (`sep` vs. `orig`) |
|---|---:|---:|---|
| Stop Reason | `converged_rel_tol` | `converged_rel_tol` | Both converged cleanly |
| Candidate Evaluations (Iters) | 11 | **8** | **`-3` evals (`-27.3%`)** |
| Master Solves / Total Cuts | 12 / 11 | 8 / 7 | `-4` cuts |
| Wall Time (pre-cert / total) | 3.246 s / 3.274 s | **2.456 s** / 2.485 s | **`-0.790 s` (`-24.3%` faster)** |
| Master / Subproblem Split | 0.012 s / 3.233 s | 0.017 s / 2.438 s | Savings from 3 fewer subproblem sweeps |
| Exact Certified Lower $L_{\mathrm{cert}}$ | `15893010388191889199413/6983776800000000000` (`2275.704227573809`) | `1765890043132431758891/775975200000000000` (`2275.7042275738086`) | Both match $I_{\mathrm{ref}}$ to `~1e-13` |
| Exact Certified Upper $U_{\mathrm{cert}}$ | `719140744658349692447/316008000000000000` (`2275.7042374191465`) | `9348829640330011808609/4108104000000000000` (`2275.7042276266648`) | `orig_same_primal = 2275.704227642467` |
| Certified Rel. Gap (Width) | `4.326e-09` (`9.845e-06`) | **`2.323e-11`** (`5.286e-08`) | `sep` ~186× tighter at stop |
| Sound / Overlaps $I_{\mathrm{ref}}$ | `true` / `true` | `true` / `true` | Fully verified |
| Binary Opening? | `false` (`1` frac. site: `633844466/10^9`) | `false` (`1` frac. site: `633846154/10^9`) | **Fractional LP bound only** |

---

## 3. Critical Scientific Interpretation (Mixed / Negative-on-Multi-Cut Finding)

The paired `p01` full pilot yields a **decisively mixed result that cautions against overclaiming a universal Benders advantage from shortage separation**:

1. **Multi-Cut Erases the Separation Advantage on `p01` (Negative for Separation in the Fastest Regime)**:
   - When both arms receive equal per-scenario cut disaggregation (`multi`), original `linked` Benders converges in **5 candidates (`1.418 s`)** — tying `linked_separated` in iterations (`5`) and edging it slightly in wall time (`1.418 s` vs. `1.437 s`).
   - Once the master holds 200 disaggregated scenario epigraphs $\theta_s$, the first sweep of 200 scenario cuts already supplies the piecewise-linear shortage slope geometry without explicitly adding 200 separate hinge variables.
2. **Single-Cut Separation Gain Is Confounded by Partial Scenario Disaggregation and Dominated by Plain Multi-Cut**:
   - In `single`-cut mode, `linked_separated` beats `linked` (`8` vs. `11` candidates, `2.456 s` vs. `3.246 s`).
   - However, this comparison is **structurally asymmetric in master disaggregation**: `single`-cut `linked` compresses all 200 scenarios into 1 cut variable $\theta$, whereas `single`-cut `linked_separated` places **200 disaggregated per-scenario scalar hinge rows** directly into the master LP.
   - Tellingly, **ordinary original-price `multi`-cut `linked` (`5` candidates, `1.418 s`) strictly dominates `single`-cut `linked_separated` (`8` candidates, `2.456 s`) by `42.3%` in wall time** while solving the exact same continuous LP relaxation.
3. **Strict Separation of Fractional Root Bounds from Integer Search**:
   - Every arm converged to a fractional opening with `1` fractional facility (`x_2 ≈ 0.633846`, `is_binary_opening: false`, `integer_incumbent_searched: false`).
   - Certified lower bounds $L_{\mathrm{cert}}$ are valid dual lower bounds for both the continuous LP relaxation and the binary MIP ($x \in \{0, 1\}^{10}$).
   - Certified upper bounds $U_{\mathrm{cert}}$ bound **only** the continuous fractional root relaxation and are **not** feasible integer solutions. This pilot provides **zero direct evidence** on whether exact scalar shortage hinges accelerate **integer** branch-and-cut / Benders search (for instance, by tightening integer master relaxations and avoiding subproblem solves at shortage-heavy binary nodes before branching).

---

## 4. Recommendation: **FREEZE Current Continuous Fractional-Root Claim; REVISE Before Any Expansion**

- **Do NOT expand this unchanged continuous fractional-root protocol as evidence of a general linked-Benders speedup.** On `p01`, the preregistered paired evidence does **not** show a consistent advantage across cut modes: the faster equal-disaggregation regime (`multi`) is a tie in iterations (`5` vs. `5`) and `+0.019 s` slower for `linked_separated`, while the `single`-cut improvement (`8` vs. `11`) is both confounded by 200 disaggregated hinge rows and strictly slower than plain `multi`-cut `linked`.
- **Recommended Disposition**:
  1. **Freeze** the Díaz `p01` continuous fractional-root Benders pilot (`pilot_smoke_result.json`, `pilot_full_result.json`, `PILOT_RESULTS.md`) alongside the frozen deterministic-equivalent record (`experiments/linked_root/runs_45s/`) as a completed, honest mixed diagnostic.
  2. **Only resume under an explicitly REVISED protocol** if the supervisor wishes to test one of two concrete hypotheses that `p01` root LP could not resolve:
     - **Revision Option 1 (Scale / Stress Check on Continuous Root)**: Run **only** the non-confounded equal-disaggregation `multi`-cut pair on `p26` ($20 \times 50$, 200 scenarios, where `p01`'s 5-iteration convergence may be too easy to expose multi-iteration cycling or high-shortage tail effects). If `multi`-cut `linked_separated` still fails to beat `multi`-cut `linked` on `p26`, freeze the entire fractional-root separation line permanently.
     - **Revision Option 2 (Binary Integer Linked Benders)**: Move to the actual discrete problem ($x \in \{0, 1\}^n$) on the identical proportional-arc linked polytope with a true MIP master (single-cut / lazy callback vs. multi-cut), measuring verified **integer** incumbents, proven MIP gaps, and avoided subproblem sweeps—where upfront scalar shortage hinges may prune binary master configurations that continuous root LPs only traverse once.
