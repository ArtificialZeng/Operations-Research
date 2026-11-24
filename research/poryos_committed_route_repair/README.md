# Poryos2026 Committed-Route Suffix Repair — Stage-0 Negative Feasibility Archive

**Archive State:** `FROZEN_LIMITED_NEGATIVE_FEASIBILITY_ARCHIVE` (`STOP_STAGE0_INSUFFICIENT_GENUINE_REPAIR_CASES`)  
**Scope:** Bounded CPU Stage-0 feasibility screen on `ANR-MAMUT/MAMUT-routing-Poryos2026` (`TDVRPTW` `td-shared`, `n ∈ {10, 25, 50}`, `60` paired cases across `5` cities). **No learned ranker was trained, no time windows were modified, and `Blauth2024` was kept strictly unopened.**

## Key Verified Findings (`PID 56384`, `1317.615 s`)
- **Primary (`n ∈ {10, 25}`, `N = 40`):** `40/40` fixed-order feasible after permitted rescheduling (`0/40` genuine edit-required).
- **Optional (`n = 50`, `N = 20`):** `19/20` fixed-order feasible; **`1/20`** genuine fixed-fleet repair (`poryos-san_francisco-n50-poi`, `bpr-light -> bpr-heavy`, `191.599 s` late at `1` stop; feasible solution found with `1` vehicle reassignment and `4` changed successor arcs; **no exact minimum-reassignment certificate**).
- **Combined (`N = 60`):** `59/60` no edits, `1/60` repaired (`1` unique base in `1` city: `san_francisco`), `0` `PROVEN_INFEASIBLE_PREFIX_LOCKED`, `0` `UNKNOWN_UNREPAIRED`, `0` `INFRASTRUCTURE_OR_INFEASIBLE_SOURCE`, `0` extra-vehicle rescues.
- **Pre-Locked Gate (`>= 15` qualifying cases AND `>= 3` cities):** **FAILED** -> Stopped cleanly at Stage-0.
- **Close Priors & Physical-Semantics Guard:** Acknowledges `Gmira et al.` (*TRC* 2021, `10.1016/j.trc.2021.103379`, plus detailed 2022 author account on real-time route stability) and `Wu, Zheng, & Zhou` (*IEEE Access* 2020, `10.1109/ACCESS.2020.3032018`, [`ieeexplore.ieee.org/abstract/document/9229128`](https://ieeexplore.ieee.org/abstract/document/9229128)); makes no "first dynamic route edit" claim. Cross-vehicle suffix shifts without physical transfer apply strictly under the synthetic **pickup-like / unassigned interchangeable service-capacity** interpretation (real OSM road graphs + synthetic orders/overlays; no real delivery claims).

## Archived Files (`research/poryos_committed_route_repair/`)
- [`STAGE0_PORYOS_FEASIBILITY_RESULT.md`](STAGE0_PORYOS_FEASIBILITY_RESULT.md) — Complete sealed negative feasibility report, structural diagnosis, and implementation disclosures.
- [`STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md`](STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md) — Pre-locked protocol (`28bc316c...`) with Pre-Scoring Boundary Erratum v1.1 (`447430fb...`).
- [`STATUS.md`](STATUS.md) — Sealed status ledger and checksum index.
- [`LICENSES_AND_PROVENANCE.md`](LICENSES_AND_PROVENANCE.md) — ODbL-1.0 / OpenStreetMap attribution, upstream commits, and excluded-asset manifest.
- [`MANIFEST.json`](MANIFEST.json) — SHA-256 manifest of all archived files.
- [`requirements.lock.txt`](requirements.lock.txt) — Exact pinned Python `3.12.16` + `mamut-routing-lib==0.12.0` environment versions.
- [`run_stage0_poryos_feasibility.py`](run_stage0_poryos_feasibility.py) — Sealed Stage-0 feasibility runner (`--self-test` verifies Erratum v1.1 boundary rules; full run reproduces the 60-case screen).
- [`stage0_smoke_checker.py`](stage0_smoke_checker.py) — Official `mamut-routing-lib==0.12.0` checker parity smoke script.
- [`stage0_scan_poryos_congestion_exposure.py`](stage0_scan_poryos_congestion_exposure.py) — Descriptive 40-base metadata/BKS exposure scan script.
- [`STAGE0_PORYOS_EXPOSURE_SCAN.json`](STAGE0_PORYOS_EXPOSURE_SCAN.json) — Descriptive 40-base summary stats across independent BKS solutions (`n ∈ {10, 25, 50, 100}`).
- [`stage0_outputs/stage0_poryos_feasibility_summary.json`](stage0_outputs/stage0_poryos_feasibility_summary.json) — Sealed native Stage-0 summary JSON (`2fd842d2...`) including all `150` upstream sidecar SHA-256 checksums.
- [`stage0_outputs/stage0_poryos_per_case.jsonl`](stage0_outputs/stage0_poryos_per_case.jsonl) — Sealed 60-case per-instance ledger (`9f3e3bae...`).

## Reproduction & Verification
Raw OSM geodata, road/traffic `.json.gz` sidecars, `.vrp.json` / `.bks.Duration.json` files, copied literature, and virtual environments are intentionally **excluded** from git. To verify offline or reproduce natively:
```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.lock.txt
# 1. Verify Erratum v1.1 boundary self-test (downloads Lyon n=10 sidecars from pinned Poryos2026 commit 0400ed2c...):
python run_stage0_poryos_feasibility.py --self-test
# 2. Re-run full 60-case Stage-0 feasibility screen (~22 min CPU, downloads & verifies 150 sidecars):
python run_stage0_poryos_feasibility.py
```

## Licensing & Attribution
- Benchmark assets fetched at runtime from [`ANR-MAMUT/MAMUT-routing-Poryos2026`](https://github.com/ANR-MAMUT/MAMUT-routing-Poryos2026) (`0400ed2c3a27ed36f725034a38873b69d3af1dea`) are licensed under **ODbL-1.0**: *"Data from OpenStreetMap and its contributors, https://www.openstreetmap.org/copyright"*.
- `mamut-routing-lib==0.12.0` (`0c30b33b3a3fd0a94a27362bcbb5acd871b374c8`) is licensed under **MIT**.
