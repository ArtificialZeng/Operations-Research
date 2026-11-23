# Pre-Registered Bounded `p26` Multi-Cut Linked Benders Stress Check Protocol

**Handoff Directory:** `D:\AI_Science\antigravity\native_linked_root_execution_20261124\`  
**Authoring Date:** 2026-11-24  
**Execution Status:** **Authored only — NOT yet executed** (no terminal commands run in this turn; awaiting permission-scoped execution).  
**Prior Stage Status:** Díaz `p01` paired pilot (`LINKED_BENDERS_PILOT.md`, `linked_benders_pilot.py`, `pilot_smoke_result.json`, `pilot_full_result.json`, `PILOT_RESULTS.md`) is **FROZEN** as a mixed fractional-root diagnostic and will not be modified or re-run.

---

## 1. Objective & Scope (Option 1 Only)

On Díaz `p01` ($10 \times 20 \times 200$), equal-disaggregation multi-cut linked Benders (`cut_mode = multi`) tied in candidate count (`5` vs. `5`) and elapsed time (`1.418 s` vs. `1.437 s`). Because `p01` saturated in only 5 iterations, this single bounded stress check evaluates whether exact shortage separation improves **multi-cut** linked Benders on the larger Díaz `p26` instance under identical budgets and proportional-arc linking.

- **In Scope**: Paired `multi`-cut continuous fractional-root linked Benders (`linked` vs. `linked_separated`) on Díaz `p26` only.
- **Explicitly Out of Scope**: No re-running `p01`, no `single`-cut runs, no integer MIP search ($x \in \{0, 1\}^{20}$), no secondary fixed-history trajectory pricing, no hyperparameter retuning, and no edits to `linked_benders_pilot.py` or any frozen source.

---

## 2. Sealed Instance & Independent Reference Interval (`p26`)

- **Instance**: Díaz `p26` loaded via frozen `experiments/linked_root/run_root.py:load_case("p26")` (20 real facilities + 1 uniform dummy, 50 customers, 200 equally weighted scenarios; verified `input_sha256 = c8573d88fe95131ab6b473c0fa1dbb29d7381918044ca845c34bbe59df420e66`).
- **Sharp Uniform Linked Separation Price**: $\eta = 2 \max_{i < 20,\, j < 50} c_{ij} = 98{,}508{,}230{,}140{,}320$ ticks ($\eta \le \rho$).
- **Independent Sealed Reference Interval** (read-only from `experiments/linked_root/runs_45s/p26_linked.json` and `p26_linked_separated.json`):
  - `p26_linked` certified lower: `46331823944918700410161309/8376550182000000000000` ($\approx 5531.1342901615$)
  - `p26_linked_separated` certified lower: `794259839055748648399034677/143598003120000000000000` ($\approx 5531.1342901615$)
  - `p26_linked` certified upper: `363386854473583925384999699/65698432800000000000000` ($\approx 5531.1342902168$)
  - `p26_linked_separated` certified upper: `99105505765317713183013847/17917754400000000000000` ($\approx 5531.1342902053$)
  - Exact reference intersection $I_{\mathrm{ref}}(\text{p26}) \approx [5531.1342901615,\; 5531.1342902053]$ (width $\approx 4.385 \times 10^{-8}$; sealed DE wall times `23.643 s` / `33.742 s`).

---

## 3. Matched Experimental Controls

Both arms reuse the unmodified generic routines `build_arm_context`, `run_benders_arm`, `compare_paths`, and `load_reference_interval` from `linked_benders_pilot.py` via a minimal wrapper (`linked_benders_p26.py`):

- **Shared Linked Polytope**: Proportional-arc links $0 \le y_{sij} \le d_{sj} x_i$, facility capacities $\sum_j y_{sij} \le u_i x_i$, demand equalities $\sum_{i=0}^{20} y_{sij} = d_{sj}$, continuous openings $x \in [0, 1]^{20}$.
- **Arm A (`linked`)**: Original uniform shortage price $\rho$ in all 200 scenario subproblems; 200 per-scenario epigraph variables $\theta_s \ge 0$; zero initial Benders cuts.
- **Arm B (`linked_separated`)**: Reduced dummy price $\eta$ in all 200 scenario subproblems; 200 per-scenario epigraph variables $\theta_s^{\mathrm{res}} \ge 0$ plus 200 exact scalar shortage hinges $h_s \ge D_s - \sum_i \min(u_i, D_s) x_i$ priced at $(\rho - \eta)/\mathrm{div}$ in the master; zero initial Benders cuts.
- **Shared Caps & Environment**:
  - `cut_mode = "multi"` (200 scenario cuts per full sweep; `cut_tol = 1e-7`)
  - Wall-clock cap: `30.0 s` per arm (`time_limit = 30.0`)
  - Candidate sweep cap: `60` candidates per arm (`max_iters = 60`)
  - Convergence target: `rel_tol = 1e-6`
  - Single-threaded execution pinned to CPU 26 (`taskset -c 26`, `OMP/OPENBLAS/MKL_NUM_THREADS=1`, HiGHS `threads=1`)
  - Secondary fixed-history trajectory pricing **omitted** (stress test of primary policy only).
- **Exact Independent Rational Verification**: Each arm certifies its own terminal bounds $[L_{\mathrm{cert}}, U_{\mathrm{cert}}]$ through frozen `experiments/linked_root/certify.py` (`OPEN_GRID = 10**9`, `DUAL_GRID = 10**8`) and checks overlap with $I_{\mathrm{ref}}(\text{p26})$. All upper bounds remain **continuous fractional root LP bounds** ($x \in [0, 1]^{20}$), explicitly separated from binary integer incumbent claims.

---

## 4. Pre-Registered Primary Comparison & Decision Rule (Fixed Before Execution)

- **Primary Comparison**: Exact-certified terminal fractional relative gap $g_{\mathrm{cert}} = (U_{\mathrm{cert}} - L_{\mathrm{cert}}) / U_{\mathrm{cert}}$ under equal caps (`30 s` / `60` candidates / `1e-6` target).
- **Diagnostics**: Target attainment (`stop_reason == "converged_rel_tol"` and certified gap check), completed candidate sweeps (`candidate_evaluations`), and distinct path verification (`compare_paths`). Single-run wall-clock timing is **descriptive only**.

### Binding Gate Rules
1. **Certificate Comparability Gate**: Both arms must yield sound exact certificates ($L_{\mathrm{cert}} \le U_{\mathrm{cert}}$) that overlap $I_{\mathrm{ref}}(\text{p26})$. Any missing, unsound, or non-overlapping certificate renders the run **inconclusive** and cannot justify any speed or bound-quality claim.
2. **If Both Arms Reach the `1e-6` Target**: Only a reduction of **at least 2 completed candidate sweeps** by `linked_separated` (`linked_evals - sep_evals >= 2`) motivates later replication.
3. **If At Least One Arm Does Not Reach Target**: Only a `linked_separated` exact-certified terminal relative gap that is simultaneously:
   - **at least 20% smaller** than `linked`'s exact-certified relative gap ($g_{\mathrm{sep}} \le 0.80 \, g_{\mathrm{orig}}$), **AND**
   - **at least `0.0001` (`1e-4`) smaller** in absolute relative-gap units ($g_{\mathrm{orig}} - g_{\mathrm{sep}} \ge 10^{-4}$),
   motivates later replication.
4. **Closure Rule**: Without the above pre-registered signal, recommend **closing the fractional-root scale line** and preserving both arms' certified records without further expansion.

---

## 5. Exact Expected Run Command (Not Yet Executed)

- **Runtime**: WSL Python `/home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14`, `PYTHONPATH=/home/ailab/frontieror_letelier_runtime_20261124/site314`.
- **Execution Status**: **NOT EXECUTED YET** (file-tools-only authoring step).

```bash
wsl.exe -e /usr/bin/timeout --kill-after=2s 95s /usr/bin/taskset -c 26 /usr/bin/env \
  PYTHONPATH=/home/ailab/frontieror_letelier_runtime_20261124/site314 \
  OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  /home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14 \
  -B /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/linked_benders_p26.py \
  --out /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/p26_multicut_result.json
```
