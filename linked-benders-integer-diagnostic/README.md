# Single-Tree Lazy Integer Linked Benders Diagnostic (`linked-benders-integer-diagnostic`)

> **Scope & Negative/Mixed Closure Disclaimer**: This is a standalone reproducibility archive for the closed **single-tree lazy integer (`x in {0,1}^n`) linked Benders** diagnostic on adapted public Díaz instances (`p26`, `p50`) using open-source `OR-Tools 9.15.6755` (`ortools.math_opt`, `SolverType.GSCIP`, `solve_calls == 1`) paired with single-threaded `SciPy` HiGHS dual-simplex callbacks. It is **not** a journal submission or a claim of general integer-search advantage. While separated residual single-cut (`sep_single_hinge`) cleared the pre-registered `p26` 3-arm gate against plain original single-cut (`orig_single`) and original multi-cut with direct shortage floors (`orig_multi_floor`), the out-of-instance 4-arm `p50` validation—adding matched original-price single-cut control `orig_single_hinge_floor` (A3)—formally **closed** the separation-superiority line (`5` vs. `5` sweeps against A3; all 4 arms solved at node 1 in `5.04–6.59 s` from a shared exact-optimal mechanical cold seed in a lightly sampled `5–6` layout regime). Because `p26` did not include arm `A3`, the `p50` closure blocks generalization/attribution of price separation without identifying what caused the `p26` speedup. All 10 s plumbing smoke runs, raw public source files, adapted `p*.json` inputs, prompts, logs, and PDFs are excluded.

---

## 1. Methods & Verification Architecture

1. **Verified True Single-Tree Lazy Backend**: `probe_solver_capabilities.py` → `solver_capability_probe.json` verified `ortools.math_opt` + `SolverType.GSCIP` executes `Event.MIP_SOLUTION` `add_lazy_constraints=True` inside a single branch-and-bound solve (`solve_calls == 1`, zero outer MIP restarts) and coexists with `scipy.optimize.linprog(..., method="highs-ds")` inside callbacks.
2. **Identical Proportional-Arc Linked Recourse**: All compared arms solve the same binary stochastic CFLP with lost sales ($x \in \{0,1\}^n$, $0 \le y_{sij} \le x_i d_{sj}$, $\sum_j y_{sij} \le u_i x_i$, $\sum_{i=0}^n y_{sij} = d_{sj}$, uniform dummy penalty $\rho$, $\eta = \max_{i,j} c_{ij}$, $\kappa = (\rho - \eta)/\mathrm{div}$) with symmetric 1D capacity-dual lifting, train-free deterministic model-input-only cold seeds charged inside each arm's clock, projected valid cut violation checks `a + g @ x_raw - theta > 1e-6`, `threads = 1`, and pinned CPU `26`.
3. **Two-Stage No-Leakage Verification**:
   - **Cold Workers** (`linked_benders_integer_p26.py`, `linked_benders_integer_p50.py`): Never open or read prior seed, layout, or sealed optimum files (`worker_saw_reference_files = false`). Record auxiliary grid-repaired feasible uppers and exact rational cut-pool LP lower bounds (`L_cert_LP`) via frozen `experiments/linked_root/certify.py`, while labeling SCIP's floating-point `best_objective_bound` strictly as a numeric diagnostic (never an exact rational global proof).
   - **Standalone Post-Run Evaluators** (`evaluate_p26_integer_run.py`, `evaluate_p50_integer_run.py`): Executed strictly after cold worker exit. Independently reprice each distinct final binary layout across all `200/200` original scenarios via frozen `experiments/liu_lost_sales/solve.py:verify` (exact integer network simplex with exact primal-dual verification and fixed dummy appended) and verify provenance chains against separately sealed exact IP optima (`p26_class9_finite.json`, `p50_rival_continuation.json`).

---

## 2. Decision-Grade Results Summary

### A. `p26` (20 × 50 × 200, 60 s/Arm, 3 Arms) — Passed Pilot Gate (No A3 Control)

| Arm (`solve_calls = 1`) | Term (`reason/limit`) | Sweeps (incl. seed) | Lazy Cuts | Nodes | Search (`before_cert`) | Worker Cert | Exact 200-Scen `U_exact_IP` (`ref_gap`) | Exact `L_cert_LP` | SCIP Dual *(numeric only)* | Callback Discrepancies |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| **A1 `orig_single`** | `OPTIMAL / None` | `43` | `15` | `2` | `24.162 s` | `0.815 s` | `5558.540868` (`0`) | `5508.509` | `5558.540867954747` | `0` unsep; `max_dual_err = 1.74e-05` |
| **A2 `orig_multi_floor`** | `OPTIMAL / None` | `26` | `2,961` | `32` | `15.552 s` | `0.848 s` | `5558.540868` (`0`) | `5522.711` | `5558.540867954746` | **`1` unsep (`1.091e-05`)** = `max_dual_err` |
| **B `sep_single_hinge`** | `OPTIMAL / None` | **`17`** | `11` | `14` | **`9.698 s`** | `0.773 s` | `5558.540868` (`0`) | `5510.291` | `5558.540867954745` | `0` unsep; `max_dual_err = 1.09e-05` |

- Standalone post-run evaluator (`0.920 s`, `0.894 s` exact repricing, `200/200` scenarios, `135321426758663/24344775000`, `witness_sha256 = e8614f6d...`): `branch_1_both_optimal_with_exact_zero_incumbent_gap`, `advance_to_p50 = true`. See `antigravity/native_linked_integer_20261124/P26_INTEGER_RESULTS.md`.

### B. `p50` (30 × 90 × 200, 120 s/Arm, 4 Arms Adding Matched Control A3) — Formal Closure

| Arm (`solve_calls = 1`) | Term (`reason/limit`) | Sweeps (incl. seed) | Lazy Cuts | Nodes | Sampled Pos-Hinge Layouts | Search (`before_cert`) | Worker Cert | Exact 200-Scen `U_exact_IP` (`ref_gap`) | Exact `L_cert_LP` | SCIP Dual *(numeric only)* |
|---|---|---:|---:|---:|---|---:|---:|---:|---:|---:|
| **A1 `orig_single`** | `OPTIMAL / None` | `6` | `5` | `1` | `4/6` (final `0`) | `6.246 s` | `1.502 s` | `6896.146696` (`0`) | `6678.698` | `6896.146695819736` |
| **A2 `orig_multi_floor`** | `OPTIMAL / None` | `6` | `572` | `1` | `3/6` (final `0`) | `6.589 s` | `1.554 s` | `6896.146696` (`0`) | `6821.905` | `6896.146695819735` |
| **A3 `orig_single_hinge_floor`** | `OPTIMAL / None` | **`5`** | `2` | `1` | `2/5` (final `0`) | `5.419 s` | `1.549 s` | `6896.146696` (`0`) | `6667.821` | `6896.146695819734` |
| **B `sep_single_hinge`** | `OPTIMAL / None` | **`5`** | `2` | `1` | `2/5` (final `0`) | `5.042 s` | `1.513 s` | `6896.146696` (`0`) | `6822.324` | `6896.146695819736` |

- Standalone post-run evaluator (`0.923 s`, `0.886 s` exact repricing, `200/200` scenarios, `110941759969/16087500`, `witness_sha256 = 171fc81c...`, `cold_seed_already_optimal = true`, zero callback numerical discrepancies across all 4 arms): `verdict = "close_separation_superiority_on_p50"`, `a3_control_blocked_separation_attribution_on_p50 = true`, `passed_p50_attribution_gate = false`. See `antigravity/native_linked_integer_20261124/P50_VALIDATION_RESULTS.md`.

---

## 3. Clean-Clone Replay Instructions

### Exact Recorded Environment & Line-Ending Policy
- **Recorded Runtime**: `Python 3.14.10`, `ortools 9.15.6755`, `scipy 1.18.1`, `numpy 2.5.3`, `networkx 3.7` (single-threaded, `OMP_NUM_THREADS=1`, `OPENBLAS_NUM_THREADS=1`, `MKL_NUM_THREADS=1`, pinned CPU core).
- **Line-Ending Preservation**: `.gitattributes` sets `* -text` so Git does not alter LF/CRLF byte sequences and locked SHA-256 digests remain exact on checkout. Always copy the **entire** `linked-benders-integer-diagnostic` subtree to a disposable working directory before replaying, and write new outputs to fresh filenames so archived JSONs stay untouched.

### Step 1 — Reconstruct Sealed Public-Derived Inputs (`p26.json`, `p50.json`)
Raw Díaz matrices (`MCDMSociety/MOrepo-Gadegaard16`, commit `5d5a64e1f9e43a2484de52dacc9148a81df5d30d`) are not republished here. From the disposable archive copy root:
```bash
python3 prepare_archive_inputs.py --cases p26 p50
```
(`prepare_archive_inputs.py` downloads pinned raw files or reads `--raw-dir`, checks `raw_sha256`, applies `experiments/diaz_lost_sales/seal_inputs.py` (`raw_source`, `adapt`, `encode`), verifies exact `instance_sha256` against `manifest.json`, and refuses to overwrite any checksum-mismatched existing target.)

### Step 2 — Replay `p26` (Cold Worker + Standalone Post-Run Exact Verifier)
```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python3 -B antigravity/native_linked_integer_20261124/linked_benders_integer_p26.py \
  --time-limit 60 \
  --out /tmp/replay_p26_raw.json

OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python3 -B antigravity/native_linked_integer_20261124/evaluate_p26_integer_run.py \
  --raw-json /tmp/replay_p26_raw.json \
  --reprice-seconds-per-layout 30 \
  --out /tmp/replay_p26_evaluated.json
```

### Step 3 — Replay `p50` 4-Arm Attribution (Cold Worker + Standalone Post-Run Exact Verifier)
```bash
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python3 -B antigravity/native_linked_integer_20261124/linked_benders_integer_p50.py \
  --time-limit 120 \
  --out /tmp/replay_p50_raw.json

OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
python3 -B antigravity/native_linked_integer_20261124/evaluate_p50_integer_run.py \
  --raw-json /tmp/replay_p50_raw.json \
  --reprice-seconds-per-layout 60 \
  --out /tmp/replay_p50_evaluated.json
```

See `ARCHIVE_MANIFEST.json` for the complete 34-file machine-readable inventory and SHA-256 digests.
