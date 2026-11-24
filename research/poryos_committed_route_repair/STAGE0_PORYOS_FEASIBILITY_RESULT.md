# Stage-0 Feasibility Screen Result — Poryos2026 Committed-Route Suffix Repair (Limited Negative Archive)

**Status / Decision:** **`STOP_STAGE0_INSUFFICIENT_GENUINE_REPAIR_CASES`** (`FROZEN_LIMITED_NEGATIVE_FEASIBILITY_ARCHIVE`)  
**Date Completed & Sealed:** 2026-11-24  
**Archive Target Path:** `research/poryos_committed_route_repair/`  
**Pre-Locked Stop Rule Honored:** **NO learned suffix ranker trained or evaluated**, NO time-window reshaping or deadline tightening, NO cherry-picking of congested instances, **`Blauth2024` kept strictly untouched and unopened**, NO tuning, NO PDF, NO news/press release, NO leaderboard claim, and NO claim of "first dynamic route edit" or methodological priority.

---

## 1. Executive Decision Summary

Under our pre-locked Stage-0 feasibility protocol ([STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md](STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md), sealed with Pre-Scoring Preregistered Boundary Erratum v1.1), advancing to a learned suffix-ranker pilot required **`>= 15` `GENUINE_EDIT_REQUIRED_REPARABLE` fixed-physical-fleet paired cases across `>= 3` distinct cities**.

Across **100% of non-cherry-picked `Poryos2026` `TDVRPTW` `td-shared` bases for `n ∈ {10, 25, 50}`** (`30` bases across all `5` cities × `2` sampling methods × `2` fixed transitions `bpr-light -> bpr-heavy` and `wave-light -> wave-heavy` = **`60` complete paired cases**, `PID 56384`, wall time `1317.615 s`):

- **Primary Cohort (`n ∈ {10, 25}`, `N = 40` paired cases):** **`40 / 40`** fixed-order feasible after permitted rescheduling (`NO_OP_RESCHEDULE_FEASIBLE`); **`0 / 40`** `GENUINE_EDIT_REQUIRED_REPARABLE` (`0` unique bases, `0` cities) — **GATE FAILED**.
- **Optional Cohort (`n = 50`, `N = 20` paired cases):** **`19 / 20`** fixed-order feasible after permitted rescheduling; **`1 / 20`** genuine fixed-fleet repair (`poryos-san_francisco-n50-poi`, `bpr-light -> bpr-heavy`, fixed-order `191.599 s` late at `1` stop; feasible fixed-fleet repair found with `1` vehicle reassignment and `4` changed successor arcs; **no exact minimum-reassignment certificate**) — **GATE FAILED**.
- **Combined Cohort (`n ∈ {10, 25, 50}`, `N = 60` paired cases):** **`59 / 60` (`98.33%`)** no edits required, **`1 / 60` (`1.67%`)** repaired across **`1` unique base** and **`1` city** (`san_francisco`), **`0`** `PROVEN_INFEASIBLE_PREFIX_LOCKED`, **`0`** `UNKNOWN_UNREPAIRED`, **`0`** `INFRASTRUCTURE_OR_INFEASIBLE_SOURCE`, and **`0`** extra-vehicle rescues — **GATE FAILED**.

Because exact fixed-order FIFO rescheduling already recovers **59/60** cases with zero suffix edits on unmodified `Poryos2026 td-shared` overlays, training a learned ranker on this benchmark family without artificially modifying time windows is **not justified**. This study stops cleanly at Stage-0 and is frozen as a limited negative feasibility archive.

---

## 2. Pinned Sources, Licensing, Official Checker & Close Prior Literature

- **Benchmark Family:** [`ANR-MAMUT/MAMUT-routing-Poryos2026`](https://github.com/ANR-MAMUT/MAMUT-routing-Poryos2026), pinned commit **`0400ed2c3a27ed36f725034a38873b69d3af1dea`**.
  - **License & Mandatory OpenStreetMap Attribution:** `ODbL-1.0` — *"Data from OpenStreetMap and its contributors, https://www.openstreetmap.org/copyright"*.
  - **Source Regime:** Real OSM urban road networks across 5 cities (`hong_kong`, `lyon`, `paris`, `san_francisco`, `tokyo`) paired with **synthetic customer requests/orders and synthetic congestion overlays** (`bpr`, `wave`). Raw OSM geodata, `.road.json.gz` / `.traffic-*.json.gz` sidecars, `.vrp.json` / `.bks.Duration.json` files, and benchmark archives are **excluded** from this git archive; all **`150`** sidecar SHA-256 checksums are recorded in [stage0_outputs/stage0_poryos_feasibility_summary.json](stage0_outputs/stage0_poryos_feasibility_summary.json) so anyone can verify upstream assets directly from the pinned commit.
  - **Holdout Hygiene:** `Blauth2024` (`blauth2024`) was held **strictly unopened and untouched** (`"blauth2024_unopened": true`).
- **Official Checker:** `mamut-routing-lib==0.12.0` (`MIT`, pinned commit `0c30b33b3a3fd0a94a27362bcbb5acd871b374c8`, exact pinned Python environment in [requirements.lock.txt](requirements.lock.txt)). Exact `td-fold/2` double-precision FIFO `NDCPWLF` evaluation (`ObjectiveFunction.DURATION`), verified to `< 1e-6 s` parity in [stage0_smoke_checker.py](stage0_smoke_checker.py).
- **Solver Availability Disclosure (`KAYROS`):** [`0nyr/kayros`](https://github.com/0nyr/kayros) (`v1.7.1`, commit `d5eb0c1b338bbef493d86a89da022bd2135298dc`, `MIT`, `arXiv:2607.23116`) ships Linux `manylinux` wheels only on PyPI (no Windows wheel, and no local C++23/Boost/CMake toolchain on this Windows host). Independent light-traffic incumbents were solved via workspace-local deterministic `TD-ILS` directly over official `mamut_routing_lib.td` `NDCPWLF` objects and validated by official `check_td_solution`, achieving mean gaps vs. official `Poryos2026` BKS of **`+0.000%`** (`n=10`), **`+0.041%`** (`n=25`), **`+1.147%`** (`n=50`), and **`+0.396%`** overall (without ever copying the benchmark anchor or BKS).
- **Close Prior Literature & Explicit Non-Priority Boundary (No "First Dynamic Route Edit" Claim):**
  - **Gmira et al. (2021)** (*Transportation Research Part C*, `10.1016/j.trc.2021.103379`, with supporting detailed author account in 2022): **Directly studies real-time route stability** on time-dependent road networks under dynamic travel-time updates.
  - **Wu, Zheng, & Zhou (2020)** (*IEEE Access*, Vol. 8, pp. 189614–189631, `10.1109/ACCESS.2020.3032018`, [`ieeexplore.ieee.org/abstract/document/9229128`](https://ieeexplore.ieee.org/abstract/document/9229128)): **Already studies in-route TDVRPTW disruption, cross-vehicle repairs with split goods, and a path-change objective.**
  - **KAYROS** (`arXiv:2607.23116`, Rascoussier et al. 2026): Anytime ILS + exact BPC for offline TDVRPTW duration minimization.
  - **LENS** (`arXiv:2403.08839`, Feijen et al. 2024): Learned neighborhood selection in LNS for static VRPTW.
  - **Bounded Scope & Non-Priority Statement:** We make **no claim of "first dynamic route edit"** or methodological priority. Had Stage-0 passed, the only plausible distinct test would have been the exact fixed-commitment, hard-window, **no-split** customer reassignment objective versus comparable cross-vehicle and same-vehicle slack repair under equal compute budgets.

---

## 3. Pre-Scoring Boundary Erratum v1.1, Runner Loop & Implementation Disclosures

### 3.1 Sealed Protocol Hashes & Pre-Scoring Boundary Erratum v1.1
- **Original Locked Protocol SHA-256 (preserved verbatim in §§1–4):** `28bc316cb87cb3389573481d5e163d6cf5b48265bdd4bc0c0fe55c490a4a61fb`
- **First Attempt Failure Before Scoring Any Case:** The initial runner invocation exited immediately at Python module import on the `SolutionCheckStatus` import path; **zero paired cases were scored** under the pre-erratum protocol.
- **Sealed Protocol SHA-256 (with §5 Pre-Scoring Erratum v1.1):** `447430fb58b65a9cb0dffdeced9691b9736a43affe89ee03eb4ced4224b427c6`
- **Boundary Rules Sealed Prior to Scoring Any Case:**
  1. **Uniform Exact Equality Convention Across All Legs (Depot, Inter-Customer, and Homebound):** Any leg with planned departure `dep <= T_shock` is already dispatched under `atfs_old` (immutable, zero retroactive cost/time changes); any leg with `dep > T_shock` runs prospectively under `atfs_new`.
  2. **Four Exhaustive Route Regimes (`262` incumbent routes across `60` cases):**
     - `ACTIVE_SUFFIX` (`158` routes, `editable_route = True`): finite carried state replayed under `atfs_old` through last stop departing `> T_shock`; suffix legs evaluated prospectively under `atfs_new`.
     - `RETIRED_OLD` (`74` routes, `editable_route = False`): `ret_old <= T_shock`; whole `atfs_old` schedule retained unchanged.
     - `UNDEPARTED` (`28` routes, `editable_route = True`): `t_0 > T_shock`; depot departure optimized over `t_0' >= T_shock` under `atfs_new` via exact `NDCPWLF` `min_shifted_image()`.
     - `HOMEBOUND_LOCKED` (`2` routes, `editable_route = False`): `dep_m(old) <= T_shock < ret_old`; already-dispatched homebound return retained unchanged under `atfs_old` (materially exercised on `poryos-tokyo-n10-hyb__wave-light_to_wave-heavy` and `poryos-hong_kong-n25-poi__wave-light_to_wave-heavy`).
  3. **Fixed Physical Fleet Guard:** Only fixed physical fleet repair (`K <= K_inc`, editing `editable_route = True` routes only) qualifies as `GENUINE_EDIT_REQUIRED_REPARABLE`. Extra-vehicle rescue is logged strictly as a separate diagnostic (`0` triggered).
  4. **Clustering & Source-Error Separation:** Unique qualifying base IDs per city are reported alongside pair counts; unavailable/invalid source assets map strictly to `INFRASTRUCTURE_OR_INFEASIBLE_SOURCE` (`0` occurred).

### 3.2 Runner Search-Loop & Nominal Budget Disclosure
Direct code audit of [run_stage0_poryos_feasibility.py](run_stage0_poryos_feasibility.py) (`SHA-256`: `51b5b522b9dcbdca25f2ff72cba30e8bcbdc639e9feb42bfd4a407a9ecda8ce7`) confirms:
- In `solve_light_incumbent_td_ils`, the outer loop guard at **line 283** is `while time.perf_counter() < deadline or iter_idx < len(init_orders):` (`len(init_orders) == 3`, guaranteeing at least **`3` deterministic time-window sorted starts** even if `deadline` expires during those starts).
- **Line 333** contains `if iter_idx >= 25 and time.perf_counter() >= deadline: break`, which is **redundant/inert** with respect to line 283 once `iter_idx >= 3` — i.e., the runner does **not** enforce a `25`-start minimum after `deadline` expires (the true forced minimum is `3` starts, not `25`).
- Because `construct(order)` has no internal timer check and `local_search` / `repair_suffix_deterministic` check `deadline` between outer passes/moves, all configured time limits (`1.5 s / 4.0 s / 8.0 s` incumbent, `5.0 s` fixed-fleet repair, `3.0 s` extra-vehicle diagnostic) are characterized strictly as **nominal wall-clock search controls**, not exact CPU budgets. **No equal-budget learning comparison or claim is made** (no learned model was trained or evaluated).

---

## 4. Verified Native Stage-0 Receipt & Checksums

| Artifact / Field | Verified Value |
|---|---|
| Runner Script | [run_stage0_poryos_feasibility.py](run_stage0_poryos_feasibility.py) (`SHA-256`: `51b5b522b9dcbdca25f2ff72cba30e8bcbdc639e9feb42bfd4a407a9ecda8ce7`) |
| Sealed Protocol (Erratum v1.1) | [STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md](STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md) (`SHA-256`: `447430fb58b65a9cb0dffdeced9691b9736a43affe89ee03eb4ced4224b427c6`) |
| Pre-Erratum Protocol SHA-256 | `28bc316cb87cb3389573481d5e163d6cf5b48265bdd4bc0c0fe55c490a4a61fb` (0 cases scored) |
| Native Execution Receipt | **`PID 56384`** / **`1317.615 s`** (`21.96 min`, exit code `0`, `60/60` invariants verified) |
| Summary JSON | [stage0_outputs/stage0_poryos_feasibility_summary.json](stage0_outputs/stage0_poryos_feasibility_summary.json) (`SHA-256`: `2fd842d21fe3fe403479d3bb3236ea7a07ba0ca2d031dd8e3abd0215fc10397a`) |
| Per-Case JSONL (`60` lines) | [stage0_outputs/stage0_poryos_per_case.jsonl](stage0_outputs/stage0_poryos_per_case.jsonl) (`SHA-256`: `9f3e3baeeb7c403d2dd3ea465118749808fd084ff0aa18be802dfe13993fadf7`) |
| 40-Base Descriptive Exposure Scan | [STAGE0_PORYOS_EXPOSURE_SCAN.json](STAGE0_PORYOS_EXPOSURE_SCAN.json) (`SHA-256`: `4789d263ffd6e99e6a7d34a95e3b9bc265ed839fae18fd62f4e92db450440097`) |
| Verified Upstream Sidecar `.json.gz` | **`150`** (`30` bases × `1` road + `4` traffic overlays; SHA-256s embedded in summary JSON) |

---

## 5. Complete Stage-0 Outcome Breakdown

### 5.1 By Pre-Locked Cohort, Size & Transition

| Cohort / Slice | Cases (`N`) | `NO_OP_RESCHEDULE_FEASIBLE` | `GENUINE_EDIT_REQUIRED_REPARABLE` (Fixed Fleet) | `PROVEN_INFEASIBLE` / `UNKNOWN` / `INFRA_SRC` | Qualifying Unique Bases (Per City) | Extra-Veh Rescue Diag | BKS Violated Diag | Mean Inc. Gap vs. BKS | Gate (`>=15` & `>=3` cities) |
|---|---:|---:|---:|---:|---|---:|---:|---:|---|
| **Primary (`n ∈ {10, 25}`)** | 40 | 40 | **0** | 0 / 0 / 0 | `0` (`{}`) | 0 | 0 | `+0.020%` | **FAIL** |
| **Optional (`n = 50`)** | 20 | 19 | **1** | 0 / 0 / 0 | `1` (`san_francisco: 1`) | 0 | 3 | `+1.147%` | **FAIL** |
| **Combined (`n ∈ {10, 25, 50}`)** | **60** | **59** | **1** | **0 / 0 / 0** | **`1`** (`san_francisco: [poryos-san_francisco-n50-poi]`) | **0** | **3** | **`+0.396%`** | **FAIL** |
| Size: `n = 10` | 20 | 20 | 0 | 0 / 0 / 0 | `0` | 0 | 0 | `+0.000%` | FAIL |
| Size: `n = 25` | 20 | 20 | 0 | 0 / 0 / 0 | `0` | 0 | 0 | `+0.041%` | FAIL |
| Size: `n = 50` | 20 | 19 | 1 | 0 / 0 / 0 | `1` (`san_francisco: 1`) | 0 | 3 | `+1.147%` | FAIL |
| Transition: `bpr-light -> bpr-heavy` | 30 | 29 | 1 | 0 / 0 / 0 | `1` (`san_francisco: 1`) | 0 | 2 | `+0.414%` | FAIL |
| Transition: `wave-light -> wave-heavy` | 30 | 30 | 0 | 0 / 0 / 0 | `0` | 0 | 1 | `+0.378%` | FAIL |

### 5.2 Dissection of the Single `GENUINE_EDIT_REQUIRED_REPARABLE` Case

Only **`poryos-san_francisco-n50-poi__bpr-light_to_bpr-heavy`** required a route edit:
- **Incumbent (`bpr-light`):** `K = 6` routes, duration **`91,107.202 s`** (`+0.771%` vs. light BKS `90,410.488 s`), schedule horizon `[0.00 h, 12.00 h]`, `T_shock = 3.60 h` (`12,958.52 s`).
- **Frozen Prefix Split:** `ACTIVE_SUFFIX = 3`, `UNDEPARTED = 2`, `RETIRED_OLD = 1` (`25` frozen customers, `25` editable customers).
- **Fixed-Order Prospective Replay (`bpr-heavy`):** **Infeasible** — `1` customer time window violated (`191.599 s` tardiness; infeasible duration `96,331.712 s`, `+5,224.5 s` / `+5.73%` vs. light incumbent; shipped BKS also violated under the same cutoff).
- **Deterministic Fixed-Fleet Repair (`K <= 6`, Separate Duration vs. Dispatch-Edit Endpoints):**
  - **Operating Duration:** **`95,266.524 s`** (feasible; `-1,065.188 s` vs. infeasible fixed-order, `+4,159.322 s` vs. light incumbent).
  - **Dispatch Edits Found:** **`1` changed vehicle assignment** and **`4` changed next-stop successor arcs** (zero extra vehicles).
  - **Exact Optimality Caveat:** Deterministic relocate/swap local search stops at a local optimum and provides **no exact minimum-reassignment certificate** (it proves fixed-fleet feasibility with `<= 1` vehicle shift and `<= 4` arc changes, not global edit-count optimality).
  - **Physical-Semantics Guard:** Permitting this cross-vehicle shift without a physical transfer relies explicitly on the **pickup-like / unassigned interchangeable service-capacity interpretation** (if customer-specific parcels were pre-loaded at depot departure, cross-vehicle shifts without transfer would be physically invalid).

---

## 6. Source Regime, Structural Limits & Why `59/60` Cases Need Zero Edits

1. **OSM Roads + Synthetic Requests/Overlays (Abstract Service-Demand Scope):** `Poryos2026` combines real OSM urban road networks with synthetic orders and synthetic congestion profiles. This Stage-0 screen stays explicitly synthetic at the abstract service-demand level and makes **no real-world delivery claims**.
2. **Anchor-Certified `td-shared` Schedule & Nighttime Free-Flow Placement (`00:00–06:00`):** `Poryos2026` `td-shared` routes depart at `t = 0.0 s` (`00:00`) while `BPR` congestion starts at `06:00` (`bins 0..5` are free-flow). **`48 / 60` (`80.0%`)** of Stage-0 cases finish completely before `06:00` (`0/20` at `n=10`, `4/20` at `n=25`, `8/20` at `n=50`).
3. **Wide Shared Time Windows + Permitted Depot Optimization:** `td-shared` windows are certified around a multi-overlay anchor (`mean width 2.94–4.40 h` for `n ∈ {10, 25, 50}`), and `UNDEPARTED` routes retain permitted depot departure-time optimization (`t_0' >= T_shock`). Even among the **`12 / 60`** cases crossing `06:00` — where heavy `BPR` increases fixed-order duration by up to **`+5,678.6 s (+14.12%)`** (`san_francisco-n25-poi bpr`) and **`+5,003.4 s (+5.21%)`** (`san_francisco-n50-hyb bpr`) — **`11 / 12`** absorb the slowdown with **zero edits**.
4. **Single Predeclared Reveal Policy:** Results apply strictly to the predeclared `30%` reveal cutoff `T_shock = T_start + 0.30 * (T_end - T_start)`; no alternative cutoffs or post-hoc window tightenings were tuned.
5. **Descriptive-Only BKS Exposure Scan:** [STAGE0_PORYOS_EXPOSURE_SCAN.json](STAGE0_PORYOS_EXPOSURE_SCAN.json) records moderate BKS cost shifts across **independent** overlay-specific solutions for `n ∈ {10, 25, 50, 100}` (`n=100` unscored: `6/10` bases with `e_max >= 6.0 h`, mean TW `3.70–4.54 h`, max BPR BKS diff `+1.36%`). That scan is **strictly descriptive across independent solutions**, not a committed-prefix repair test.
