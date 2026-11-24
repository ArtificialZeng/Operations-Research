# Licenses, Attribution & Provenance — Poryos2026 Stage-0 Feasibility Archive

## 1. Upstream Public Sources & Exact Pins
- **Benchmark Data Source (Not Redistributed in This Archive):**
  - Repository: `https://github.com/ANR-MAMUT/MAMUT-routing-Poryos2026`
  - Exact Pinned Commit: `0400ed2c3a27ed36f725034a38873b69d3af1dea`
  - License: **Open Data Commons Open Database License 1.0 (`ODbL-1.0`)** — `https://opendatacommons.org/licenses/odbl/1-0/`
  - Mandatory OpenStreetMap Attribution: **Data from OpenStreetMap and its contributors, https://www.openstreetmap.org/copyright**
  - Asset Verification: Exact SHA-256 checksums for all `150` `.road.json.gz` and `.traffic-*.json.gz` sidecars (`n ∈ {10, 25, 50}`) are recorded in `stage0_outputs/stage0_poryos_feasibility_summary.json`.
- **Official Time-Dependent Routing Checker:**
  - Package: `mamut-routing-lib==0.12.0` (`https://github.com/ANR-MAMUT/MAMUT-routing-lib`, commit `0c30b33b3a3fd0a94a27362bcbb5acd871b374c8`)
  - License: **MIT**
- **Reference Solver Ecosystem (Not Executed on Windows — Disclosed):**
  - Repository: `https://github.com/0nyr/kayros` (`v1.7.1`, commit `d5eb0c1b338bbef493d86a89da022bd2135298dc`, `MIT`, `arXiv:2607.23116`). Ships Linux `manylinux` PyPI wheels only (no Windows wheel; no local C++23/Boost toolchain).
- **Holdout Benchmark Family (Untouched):**
  - `Blauth2024` (`blauth2024`) was strictly unopened and untouched throughout Stage-0.

## 2. Explicit Archive Exclusions
The following local files and directories are **excluded** from the git archive branch:
- All raw benchmark data, geodata, sidecars, and hosted BKS/instance files (`raw_poryos2026/`, `.road.json.gz`, `.traffic-*.json.gz`, `.vrp.json`, `.bks.Duration.json`, `mamut-collection.json`).
- All copied literature downloads/extracts (`literature_notes/`).
- All virtual environments and Python bytecode (`.venv/`, `__pycache__/`).
- All desktop steering notes (`desktop_*.txt`), local PR handoff helper notes, secrets, credentials, and unrelated workspace files.
- Exploratory one-off catalog inspection scripts (`stage0_inspect_*.py`) not required for Stage-0 verification or reproduction.
