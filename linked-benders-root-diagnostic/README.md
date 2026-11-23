# Linked Benders Continuous Fractional-Root Diagnostic Archive

> **Archive Scope & Status**: Closed reproducibility archive for `ArtificialZeng/Operations-Research` (`linked-benders-root-diagnostic/`). This package records completed continuous fractional-root LP and iterative linked Benders diagnostics on adapted public Díaz facility-location instances (`p01`, `p26`, `p50`). It is **not** a claim of journal readiness and **not** a claim of an integer-search speedup. Both `p50` deterministic-equivalent timeouts are preserved as unresolved outcomes, and the fractional-root linked Benders line is closed following negative/null equal-disaggregation multi-cut results on `p01` and `p26`.

---

## 1. Minimal Methods

All experiments evaluate the **continuous fractional root relaxation** ($x \in [0, 1]^n$) of a two-stage stochastic split-delivery capacitated facility location problem with uniform shortage price $\rho$ and 200 equally weighted synthetic demand scenarios adapted deterministically from the pinned public Díaz instances (`MCDMSociety/MOrepo-Gadegaard16`, commit `5d5a64e1f9e43a2484de52dacc9148a81df5d30d`):

1. **Deterministic-Equivalent (DE) Root Diagnostic (`experiments/linked_root/`)**:
   - Compares three LP formulations under a 45 s single-threaded HiGHS IPM cap: `plain` (facility capacity rows only), `linked` (adds binary-valid proportional arc links $y_{sij} \le x_i d_{sj}$), and `linked_separated` (same proportional arc links, reduced dummy price $\eta = 2\max_{i,j} c_{ij}$, plus 200 exact scalar shortage hinges $h_s(x) = (D_s - \sum_i \min(u_i, D_s)x_i)^+$ weighted by $\rho - \eta$).
   - By the pointwise identity, `linked` and `linked_separated` have identical exact LP optima.
2. **Paired Iterative Linked Benders Root Diagnostic (`antigravity/native_linked_root_execution_20261124/`)**:
   - Compares cold-start iterative Benders on the **identical proportional-arc linked polytope** (`linked` vs. `linked_separated`) with zero initial Benders cuts, single-threaded HiGHS dual simplex (`highs-ds`), symmetric 1D capacity-dual lifting, `30 s` wall-clock cap, `60` max candidate sweeps, and `1e-6` relative gap target.
   - `p01` evaluated both `multi`-cut (200 scenario epigraphs $\theta_s$) and `single`-cut (1 aggregated epigraph $\theta$); `p26` ran a pre-registered `multi`-cut stress check without secondary trajectory pricing.
3. **Exact Rational Verification (`experiments/linked_root/certify.py`)**:
   - Projects numerical openings onto `OPEN_GRID = 10**9`, repairs flows to exact primal feasibility, projects dual multipliers onto `DUAL_GRID = 10**8`, and checks overlap against the independent sealed DE reference intervals.
   - **Fractional vs. Integer Distinction**: Every certified lower bound $L_{\mathrm{cert}}$ bounds both the continuous LP relaxation and the binary MIP from below. Every certified upper bound $U_{\mathrm{cert}}$ evaluates a fractional opening (`is_binary_opening = false`) and bounds **only** the continuous fractional root LP relaxation—not an integer incumbent.

---

## 2. Summary of Archived Results

### A. Sealed 45 s Deterministic-Equivalent Root LPs (`experiments/linked_root/runs_45s/`)

| Case (Sites × Cust × Scen) | Mode | Status (45 s cap) | Certified Fractional Interval $[L_{\mathrm{cert}}, U_{\mathrm{cert}}]$ | Linking Gain vs. `plain` | Wall Time (one-run) |
|---|---|---|---:|---:|---:|
| `p01` ($10 \times 20 \times 200$) | `plain` | Optimal | `[2274.5190751992, 2274.5190752619]` | — | 1.195 s |
| `p01` | `linked` | Optimal | `[2275.7042275738, 2275.7042276416]` | `[+1.18515231, +1.18515244]` | 2.361 s |
| `p01` | `linked_separated` | Optimal | `[2275.7042275738, 2275.7042276260]` | overlaps `linked` | 2.837 s |
| `p26` ($20 \times 50 \times 200$) | `plain` | Optimal | `[5506.9217580699, 5506.9217597341]` | — | 7.401 s |
| `p26` | `linked` | Optimal | `[5531.1342901615, 5531.1342902168]` | `[+24.21253043, +24.21253215]` | 23.643 s |
| `p26` | `linked_separated` | Optimal | `[5531.1342901615, 5531.1342902053]` | overlaps `linked` | 33.742 s |
| `p50` ($30 \times 90 \times 200$) | `plain` | Optimal | `[6801.6212890644, 6801.6212907939]` | — | 26.690 s |
| `p50` | `linked` | **Timeout (preserved)** | No certificate (`status = 1`, 25 IPM iters) | unresolved | 41.111 s |
| `p50` | `linked_separated` | **Timeout (preserved)** | No certificate (`status = 1`, 30 IPM iters) | unresolved | 41.096 s |

### B. Paired Cold-Start Iterative Linked Benders Root Diagnostics (CPU 26, `30 s` / `60` sweeps / `1e-6` target)

| Case | Cut Regime | Arm | Sweeps | Stop Status | Certified Fractional Rel. Gap | Sound / Ref Overlap | Time (pre-cert, descriptive) |
|---|---|---|---:|---|---:|---|---:|
| `p01` (smoke, `max_iters=4`) | `multi` | `linked` | 4 | `max_iters` | `4.352e-07` | `true` / `true` | 1.137 s |
| `p01` (smoke, `max_iters=4`) | `multi` | `linked_separated` | 4 | `max_iters` | `5.768e-07` | `true` / `true` | 1.158 s |
| `p01` (full) | `multi` | `linked` | **5** | `converged_rel_tol` | `3.017e-11` | `true` / `true` | 1.418 s |
| `p01` (full) | `multi` | `linked_separated` | **5** | `converged_rel_tol` | `2.323e-11` | `true` / `true` | 1.437 s |
| `p01` (full) | `single` | `linked` | 11 | `converged_rel_tol` | `4.326e-09` | `true` / `true` | 3.246 s |
| `p01` (full) | `single` | `linked_separated` | **8** | `converged_rel_tol` | `2.323e-11` | `true` / `true` | 2.456 s |
| `p26` (Option 1 stress check) | `multi` | `linked` | **8** | `converged_rel_tol` | `3.545e-07` | `true` / `true` | 4.540 s |
| `p26` (Option 1 stress check) | `multi` | `linked_separated` | **8** | `converged_rel_tol` | `3.552e-07` | `true` / `true` | 4.671 s |

**Closure Decision**:
- On `p01`, the `single`-cut reduction (`8` vs. `11` sweeps) is confounded by injecting 200 disaggregated per-scenario hinge rows into an otherwise single-cut master and remains slower than plain `multi`-cut `linked` (`1.418 s` vs. `2.456 s`).
- Under equal per-scenario cut disaggregation (`multi`), `linked_separated` saves **0** sweeps on both `p01` (`5` vs. `5`) and `p26` (`8` vs. `8`), failing the pre-registered `p26` replication gate (`sweeps_saved_by_separated >= 2`, verdict: `close_fractional_root_scale_line`). Both arms are preserved as closed negative/mixed diagnostic evidence.

---

## 3. Clean-Clone Replay Instructions

### Prerequisites & Line-Ending (CRLF/LF) Preservation
- **Exact Recorded Environment**: `Python 3.14.10` (Linux/WSL), `numpy 2.5.3`, `scipy 1.18.1`, plus `ortools` (imported at module top level by frozen `experiments/bodur_holmberg_transfer/independent.py`, which supplies the `Instance` dataclass).
- **Exact CRLF/LF Byte Preservation**: Several frozen files (`experiments/diaz_lost_sales/manifest.json`, `seal_inputs.py`, `experiments/linked_root/run_root.py`, `root_model.py`, `certify.py`, `PROTOCOL.md`, `runs_45s/lock.json`, `experiments/bodur_holmberg_transfer/independent.py`, and the pilot scripts) are verified by byte-exact SHA-256 digests. The archive includes `.gitattributes` (`* -text`) so Git preserves exact raw bytes on checkout; on Windows or cross-platform clones, keep automatic line-ending conversion disabled (`git clone -c core.autocrlf=false ...`).
- Keep the directory layout (`experiments/` and `antigravity/`) intact as listed in `ARCHIVE_MANIFEST.json`; all scripts resolve sibling and parent paths relative to `__file__`.

### Step 1 — Reconstruct Checksum-Verified Adapted Díaz Inputs (No Republished Raw Matrices)
From the root of `linked-benders-root-diagnostic/`:
```bash
python3 prepare_archive_inputs.py
```
This imports `seal_inputs.raw_source`, `seal_inputs.adapt`, and `seal_inputs.encode` (never calling `seal_inputs.main()`, which expects unrelated Scotland files and attempts to reseal), downloads the three pinned public `.raw` files from `MCDMSociety/MOrepo-Gadegaard16` (`5d5a64e1f9e43a2484de52dacc9148a81df5d30d`), verifies `raw_sha256` and `raw_bytes`, and writes `experiments/diaz_lost_sales/{p01,p26,p50}.json` only when each reconstructed JSON's SHA-256 matches `experiments/diaz_lost_sales/manifest.json` exactly. (For offline replay with previously downloaded raw files, pass `--raw-dir /path/to/raw_files`; pass `--verify-only` to verify existing JSON checksums without writing.)

### Step 2 — Replay Iterative Linked Benders Diagnostics (Always Write to Fresh Output Paths)
**Never overwrite the archived `pilot_*_result.json` or `p26_multicut_result.json` records.** Always pass `--out` pointing to a fresh temporary or scratch directory outside the archived paths (e.g., `/tmp/replay/`):
```bash
# p01 smoke (4 iterations, multi-cut)
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 -B antigravity/native_linked_root_execution_20261124/linked_benders_pilot.py \
  --mode smoke --out /tmp/replay_p01_smoke.json

# p01 full paired pilot (multi-cut and single-cut)
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 -B antigravity/native_linked_root_execution_20261124/linked_benders_pilot.py \
  --mode full --out /tmp/replay_p01_full.json

# p26 pre-registered multi-cut stress check
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
  python3 -B antigravity/native_linked_root_execution_20261124/linked_benders_p26.py \
  --out /tmp/replay_p26_multicut.json
```
*(Optional on Linux with pinned CPU 26: prefix with `taskset -c 26` to match single-core execution affinity. Exact rational soundness and sealed-reference overlap checks run automatically inside both scripts.)*

### Step 3 — Inspecting or Re-Running the Sealed DE Reference
- All 9 sealed deterministic-equivalent JSON results (including both `p50` timeouts) and `lock.json` are archived under `experiments/linked_root/runs_45s/`.
- `experiments/linked_root/run_root.py` enforces exact `lock.json` package versions (`numpy 2.5.3`, `scipy 1.18.1`), CPU affinity (`18`/`22`/`26`), sibling relative paths (`../bodur_holmberg_transfer/independent.py` and `../diaz_lost_sales/`), and refuses to overwrite existing `runs_45s/*.json` files. To execute a new DE run without touching archived records, copy the **entire `linked-benders-root-diagnostic/` archive subtree** into a disposable directory so all sibling dependencies remain intact, remove or replace only `experiments/linked_root/runs_45s/` inside that disposable copy with a fresh `runs_45s/` directory, run `prepare_archive_inputs.py` there if needed, and re-seal/run inside the disposable copy only.
