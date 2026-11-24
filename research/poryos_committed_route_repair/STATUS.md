# Status Ledger — Poryos2026 Committed-Route Suffix Repair (FROZEN LIMITED NEGATIVE ARCHIVE)

- **State:** **`FROZEN_LIMITED_NEGATIVE_FEASIBILITY_ARCHIVE`** (`STOP_STAGE0_INSUFFICIENT_GENUINE_REPAIR_CASES`)
- **Date Sealed:** 2026-11-24
- **Target Archive Path:** `research/poryos_committed_route_repair/`

## Sealed Protocol, Runner & Execution Receipts
- **Pinned Benchmark:** `ANR-MAMUT/MAMUT-routing-Poryos2026` @ `0400ed2c3a27ed36f725034a38873b69d3af1dea` (`ODbL-1.0`; *"Data from OpenStreetMap and its contributors, https://www.openstreetmap.org/copyright"*)
- **Official Checker:** `mamut-routing-lib==0.12.0` (`MIT`, commit `0c30b33b3a3fd0a94a27362bcbb5acd871b374c8`)
- **Holdout Hygiene:** `Blauth2024` strictly **UNOPENED** (`blauth2024_unopened: true`)
- **Pre-Erratum Protocol SHA-256 (0 cases scored; initial import failed on `SolutionCheckStatus`):** `28bc316cb87cb3389573481d5e163d6cf5b48265bdd4bc0c0fe55c490a4a61fb`
- **Sealed Protocol SHA-256 (with Pre-Scoring Boundary Erratum v1.1):** `447430fb58b65a9cb0dffdeced9691b9736a43affe89ee03eb4ced4224b427c6` (`STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md`)
- **Runner SHA-256:** `51b5b522b9dcbdca25f2ff72cba30e8bcbdc639e9feb42bfd4a407a9ecda8ce7` (`run_stage0_poryos_feasibility.py`)
- **Runner Search-Control Disclosure:** `solve_light_incumbent_td_ils` line `283` guarantees `3` deterministic starts (`len(init_orders) == 3`); line `333` (`iter_idx >= 25`) is redundant/inert once `iter_idx >= 3` at line `283` (no 25-start minimum enforced). All configured durations (`1.5s/4.0s/8.0s` incumbent, `5.0s` repair, `3.0s` extra-veh diag) are nominal wall-clock search controls; no equal-budget learning claim is made.
- **Native Stage-0 Run:** `PID 56384`, wall time `1317.615 s`, exit code `0`, `150` sidecar SHA-256s verified
- **Summary JSON SHA-256:** `2fd842d21fe3fe403479d3bb3236ea7a07ba0ca2d031dd8e3abd0215fc10397a` (`stage0_outputs/stage0_poryos_feasibility_summary.json`)
- **Per-Case JSONL SHA-256:** `9f3e3baeeb7c403d2dd3ea465118749808fd084ff0aa18be802dfe13993fadf7` (`stage0_outputs/stage0_poryos_per_case.jsonl`)
- **Exposure Scan JSON SHA-256 (Descriptive Independent BKS Only):** `4789d263ffd6e99e6a7d34a95e3b9bc265ed839fae18fd62f4e92db450440097` (`STAGE0_PORYOS_EXPOSURE_SCAN.json`)

## Decisive Stage-0 Numbers
- **Primary (`n ∈ {10, 25}`, `N = 40`):** `40/40` fixed-order feasible after permitted rescheduling (`0/40` genuine edit-required, `0` unique bases, `0` cities, mean inc. gap vs. BKS `+0.020%`, diagnostic BKS violations `0/40`).
- **Optional (`n = 50`, `N = 20`):** `19/20` fixed-order feasible; `1/20` genuine fixed-fleet repair (`poryos-san_francisco-n50-poi__bpr-light_to_bpr-heavy`, `191.599 s` late at `1` stop, repaired with `1` vehicle reassignment and `4` changed successor arcs, `95,266.524 s` vs. `91,107.202 s` light incumbent; **no exact minimum-reassignment certificate**), `1` unique base in `1` city (`san_francisco`), mean inc. gap vs. BKS `+1.147%`, diagnostic BKS violations `3/20`.
- **Combined (`N = 60`):** `59/60` no edits, `1/60` repaired, `0` `PROVEN_INFEASIBLE_PREFIX_LOCKED`, `0` `UNKNOWN_UNREPAIRED`, `0` `INFRASTRUCTURE_OR_INFEASIBLE_SOURCE`, `0` extra-vehicle rescues, `262` routes classified (`158` `ACTIVE_SUFFIX`, `74` `RETIRED_OLD`, `28` `UNDEPARTED`, `2` `HOMEBOUND_LOCKED`).
- **Pre-Locked Gate (`>= 15` fixed-fleet qualifying cases AND `>= 3` cities):** **FAILED** -> Stopped cleanly at Stage-0.

## Scope, Prior-Literature & Physical-Semantics Guardrails
- **Close Priors Cited:** `Gmira et al.` (*TRC* 2021, `10.1016/j.trc.2021.103379`, plus detailed 2022 author account on real-time route stability); `Wu, Zheng, & Zhou` (*IEEE Access* 2020, `10.1109/ACCESS.2020.3032018`, `ieeexplore.ieee.org/abstract/document/9229128` — in-route TDVRPTW disruption, cross-vehicle split-goods repairs, path-change objective); `KAYROS` (`arXiv:2607.23116`); `LENS` (`arXiv:2403.08839`). **No "first dynamic route edit" claim.**
- **Source Regime & Physical-Semantics Boundary:** Real OSM roads with synthetic requests/overlays; anchor-certified `td-shared` schedule; single predeclared `30%` reveal policy; permitted depot optimization for undeparted routes; pickup-like / unassigned interchangeable service-capacity interpretation retained wherever cross-vehicle shifts are allowed without physical transfer (no real delivery claims).
- **Guardrails Honored:** No window reshaping, no `Blauth2024` inspection, no tuning/training, no PDF/news/leaderboard/paper, no raw geodata/sidecars/BKS/literature/venvs/secrets/desktop-steering in archive; `main` (`940709d3...`) and open PRs untouched.
