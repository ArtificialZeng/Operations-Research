# Stage-0 Pre-Locked Feasibility Protocol — Poryos2026 Committed-Route Suffix Repair

**Date Locked:** 2026-11-24 (BEFORE running ANY incumbent generation or paired repair feasibility screen)  
**Workspace:** `D:\AI_Science\antigravity\poryos_committed_route_repair_20261124`  
**Scope:** Stage-0 decisive feasibility screen ONLY — **NO learned ranker pilot unless this screen passes.** No manufactured deadline tightening, no cherry-picking congested days, no opening `Blauth2024` in Stage-0, no leaderboard claims, no PDF, no PR until evidence.

---

## 1. Pinned Public Sources, Checker & Licensing
- **Benchmark Family:** [`ANR-MAMUT/MAMUT-routing-Poryos2026`](https://github.com/ANR-MAMUT/MAMUT-routing-Poryos2026), exact pinned commit **`0400ed2c3a27ed36f725034a38873b69d3af1dea`** (`ODbL-1.0`; real OSM city road networks, synthetic orders & congestion; *"Data from OpenStreetMap and its contributors, https://www.openstreetmap.org/copyright"*).
- **Scoped Variants:** `TDVRPTW` `td-shared` subinstances ONLY (`bpr-light`, `bpr-heavy`, `wave-light`, `wave-heavy`), where paired overlays share identical customers, demands, vehicle capacity, service times, and `td-shared` time windows (`[0, 86400]` s horizon, float seconds). All road/traffic/ATF SHA-256 sidecars verified natively at load time.
- **Official Checker:** `mamut-routing-lib==0.12.0` (MIT, workspace-local `.venv` only; `td-fold/2` double-precision FIFO `NDCPWLF` checker, `ObjectiveFunction.DURATION`, verified `< 1e-6 s` replay parity on smoke check).
- **Solver Availability Disclosure:** `kayros==1.7.1` (`d5eb0c1b...`, MIT, `arXiv:2607.23116`) ships Linux `manylinux` wheels only (no Windows wheel; no local C++23/Boost toolchain). On Windows, independent light-traffic incumbents and suffix repair are computed in workspace-local Python directly over `mamut-routing-lib==0.12.0`'s exact `NDCPWLF` ATFs and verified by official `check_td_solution`.
- **Benchmark Anchor Trap Avoided:** `Poryos2026` constructs `td-shared` windows to certify a benchmark anchor route under all 6 overlays. We NEVER use that anchor as the operational incumbent (smoke check only); we independently solve a competitive light-traffic incumbent under a fixed CPU budget and freeze it ex ante.
- **Closest Priors (Distinct Scope):** `KAYROS` (`arXiv:2607.23116`, exact/anytime TDVRPTW solver), `LENS` (`arXiv:2403.08839`, learned neighborhood selection for static VRPTW LNS), `Gmira et al.` (*TRC* 2021, `10.1016/j.trc.2021.103379`, dynamic TD routing repair). Our target is frozen-prefix, edit-limited suffix repair after a known traffic revision, evaluated separately on operating duration cost and dispatch edits (changed next-stop arcs & vehicle assignments).

---

## 2. Predefined Non-Cherry-Picked Cohorts & Fixed Traffic Transitions

- **Two Fixed Source-to-Revised Transitions:**
  1. `bpr-light -> bpr-heavy`
  2. `wave-light -> wave-heavy`
- **Primary Stage-0 Cohort (`40` paired cases):** ALL `20` `td-shared` base instances with `n ∈ {10, 25}` across ALL `5` cities (`hong_kong`, `lyon`, `paris`, `san_francisco`, `tokyo`) × `2` sampling methods (`hyb`, `poi`) × `2` transitions = **`40` paired cases**.
- **Optional `n = 50` Cohort (`20` paired cases):** ALL `10` `td-shared` base instances with `n = 50` across ALL `5` cities × `2` sampling methods × `2` transitions = **`20` paired cases** (reported separately AND combined with Primary = `60` total un-cherry-picked cases covering `100%` of `n ∈ {10, 25, 50}`).

---

## 3. Fixed Ex-Ante Incumbent, Shock Cutoff & Prospective FIFO Replay Rules

1. **Independent Light-Traffic Incumbent (Fixed Seed `20261124`, Fixed CPU Budget):**
   - For each source instance (`bpr-light` or `wave-light`), run deterministic workspace-local `TD-ILS` (multi-start TD cheapest/regret insertion + exact-`NDCPWLF` relocate, swap, 2-opt, Or-opt) with fixed budget (`1.5 s` for `n=10`, `4.0 s` for `n=25`, `8.0 s` for `n=50`), validated by official `check_td_solution(..., ObjectiveFunction.DURATION)`.
   - Select the single lowest-duration valid incumbent ex ante, log its gap against the shipped BKS (confirming competitiveness without copying BKS or anchor), and freeze its routes `R_inc` and exact optimal source depot departures `{t*_r}`.
2. **Precommitted Shock Time (`T_shock`, Fixed Ex Ante):**
   - Let `[T_start, T_end] = [min_r t*_r, max_r (t*_r + dur_r)]` under the source overlay `atfs_old`.
   - Fix **`T_shock = T_start + 0.30 * (T_end - T_start)`**.
3. **Exact Prospective Frozen-Prefix Replay (No Past-History Replay Under New Overlay!):**
   - For each route `r = [c_1, ..., c_m]` with source schedule `(t_0, arr_1, start_1, dep_1, ..., dep_m, ret)` under `atfs_old`:
     - If `t_0 > T_shock`: vehicle has not departed depot yet (`prefix = []`, `last_node = 0`, `carried_load = 0`, editable departure `t_0' >= T_shock`).
     - If `t_0 <= T_shock`: let `p ∈ {1..m}` be the first stop index with `dep_p(old) > T_shock` (or `p = m` if `dep_m(old) <= T_shock`). Replay `atfs_old` through `c_p` to obtain exact carried state `(last_node = c_p, carried_dep_time = dep_p(old), carried_load = sum_{j=1..p} q_{c_j}, frozen_t0 = t_0)`.
     - Apply `atfs_new` **prospectively** from `(last_node, carried_dep_time)` over the remaining suffix `[c_{p+1}, ..., c_m, 0]` using exact FIFO `NDCPWLF` evaluation (and exact `NDCPWLF` domain restriction `t_0' >= T_shock` for undeparted routes).
4. **Separate Endpoints Logged:**
   - Feasibility status (`4` mutually exclusive classes below).
   - Operating cost (`total_duration` in seconds, and `Δduration` vs. fixed-order / source).
   - Actual dispatch edits: `changed_next_stop_arcs` (count of edited suffix directed arcs vs. frozen incumbent) and `changed_vehicle_assignments` (count of editable customers moved to a different vehicle).
   - Fixed-fleet (`K <= K_inc`) vs. extra-vehicle (`K > K_inc`, departing depot at `t >= T_shock`) tracked separately!

---

## 4. Four Mutually Exclusive Outcomes & Pre-Locked Stage-0 Advance Gate

Every paired case is classified into exactly one outcome (all counts & reasons preserved):
1. **`NO_OP_RESCHEDULE_FEASIBLE`**: Fixed order passes exact earliest-window FIFO propagation under `atfs_new` (plus capacity & depot return checks) with `0` dispatch edits.
2. **`GENUINE_EDIT_REQUIRED_REPARABLE`**: Fixed order violates time windows under `atfs_new` even under exact earliest-window propagation, **AND** deterministic slack/tardiness-guided suffix local repair (`5.0 s` budget, same allowed edit operations: relocate, swap, 2-opt, Or-opt on editable suffix `C_edit` keeping committed prefixes frozen) recovers a 100% valid solution.
3. **`PROVEN_INFEASIBLE_PREFIX_LOCKED`**: Fundamentally impossible with frozen prefixes (proven via exact reachability / bounded exact branch-and-bound when `|C_edit|` is small).
4. **`UNKNOWN_UNREPAIRED`**: Neither repaired within budget nor proven infeasible (`unknown stays unknown`).

### Pre-Locked Stage-0 Feasibility Advance Threshold (Required Before Any Learned Pilot)
- **`>= 15` `GENUINE_EDIT_REQUIRED_REPARABLE` paired cases** spanning **`>= 3` distinct cities** (evaluated on Primary `n=10, 25` cohort `N=40`, and separately reported on Combined `n=10, 25, 50` cohort `N=60`).
- If fewer than `15` genuine edit-required and reparable cases (or `< 3` cities) occur -> **STOP CLEANLY AT STAGE-0** and report the structural cause honestly (no manufactured deadline tightening, no cherry-picking, no learned ranker run!).


---

## 5. Pre-Scoring Preregistered Boundary Erratum v1.1 (Zero Paired Cases Scored Prior to Erratum)

**Prior Locked Protocol SHA-256 (preserved above verbatim):** `28bc316cb87cb3389573481d5e163d6cf5b48265bdd4bc0c0fe55c490a4a61fb`  
**Reason for Pre-Scoring Erratum:** Prior to scoring any paired case (the initial runner attempt exited at module import on `SolutionCheckStatus` before running any case), §3's branch `dep_m(old) <= T_shock` fell back to `p = m` and evaluated the return leg `(c_m -> 0)` under `atfs_new`, which would retroactively alter a return leg already dispatched at or before `T_shock`. This erratum closes that boundary loophole and strengthens fleet, clustering, and source-error guards:

1. **Uniform Leg-Departure Convention Across ALL Legs (Depot Departure, Inter-Customer, and Homebound Return):**
   - Any leg whose planned departure under `atfs_old` satisfies **`dep <= T_shock`** is **already dispatched under `atfs_old`** (never retroactively re-evaluated under `atfs_new`). Any leg with **`dep > T_shock`** has not yet departed at `T_shock` and is evaluated prospectively under **`atfs_new`**.
   - Every incumbent route `r = [c_1, ..., c_m]` (with exact source schedule `t_0, dep_1, ..., dep_m, ret_old` under `atfs_old`) falls into exactly one of four exhaustive regimes:
     - **`UNDEPARTED` (`t_0 > T_shock`):** `prefix = []`, `orig_suffix = r`, `editable_route = True`, carried `(node=0, load=0)`, earliest new depot departure `t_0' >= T_shock` under `atfs_new`.
     - **`ACTIVE_SUFFIX` (`t_0 <= T_shock` and `∃ p ∈ {1..m}` with `dep_p(old) > T_shock`, taking the smallest such `p`):** `prefix = r[:p]`, `orig_suffix = r[p:]`, `editable_route = True`, carried finite state `(last_node=c_p, carried_dep_time=dep_p(old) > T_shock, carried_load=sum_{j=1..p} q_{c_j}, frozen_t0=t_0)` replayed under `atfs_old`; all subsequent legs from `c_p` onward evaluated prospectively under `atfs_new`.
     - **`HOMEBOUND_LOCKED` (`t_0 <= T_shock` and `dep_m(old) <= T_shock < ret_old`):** Final customer `c_m` finished at `dep_m(old) <= T_shock`, so homebound leg `(c_m -> 0)` is already dispatched. Retain the full `atfs_old` schedule through depot arrival `ret_old` (`duration = ret_old - t_0`, zero retroactive cost/time change), `prefix = r`, `orig_suffix = []`, **`editable_route = False`** (unavailable for customer suffix edits).
     - **`RETIRED_OLD` (`ret_old <= T_shock`):** Route already returned to depot at or before `T_shock`. Retain whole `atfs_old` schedule (`duration = ret_old - t_0`, zero retroactive change), `prefix = r`, `orig_suffix = []`, **`editable_route = False`**.
2. **Physical Fleet Fixed Guard for Gate Qualification:**
   - **ONLY fixed physical fleet repair (`K <= K_inc`, editing ONLY `editable_route = True` routes)** qualifies as `GENUINE_EDIT_REQUIRED_REPARABLE` toward the Stage-0 advance threshold.
   - Repair requiring an extra vehicle (`K > K_inc`) is logged strictly as a **separate diagnostic endpoint (`extra_vehicle_reparable_diag`)** and does **NOT** qualify as `GENUINE_EDIT_REQUIRED_REPARABLE`.
3. **Base-Level Clustering & Per-City Unique Base Reporting:**
   - Because `bpr-light->heavy` and `wave-light->heavy` share the same base instance, the summary explicitly reports **qualifying UNIQUE base IDs per city** (`unique_genuine_bases_per_city` and `n_genuine_unique_bases`) alongside total qualifying pair counts, while preserving the pre-locked numerical gate (`>= 15` qualifying cases across `>= 3` cities) and flagging base clustering for any advance decision.
4. **Source / Infrastructure State Separation:**
   - Any unavailable source asset, checksum failure, or invalid light-traffic incumbent is recorded strictly as **`INFRASTRUCTURE_OR_INFEASIBLE_SOURCE`** (never counted as `NO_OP_RESCHEDULE_FEASIBLE` or evidence of no repair opportunity).
