# Counterfactual carbon accounting and congestion-constrained abatement limits of U.S. utility-scale battery storage (`K1`)

**Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my`)  
**Status:** FROZEN SUBMISSION-READY ARCHIVE (`v4` Strict *Nature Energy* `Analysis` Package, `2026-11-28`)  
**Submission Deliverables:**
- Main Manuscript PDF (`10` pages, `140`-word unreferenced Abstract, `2,438`-word Main Body `<= 3,000`, `4` Main Figures + `2` Main Tables = `6 <= 8` display items, `18` Crossref-verified references): `manuscript_k1_nature_energy.pdf` (`SHA-256: 942b2df3905e5cb17b63a6c677341a0350a2ea2060dc53885eacb036fbdfd3a9`)
- Separate Supplementary Information PDF (`4` pages: Supplementary Box 1, Supplementary Tables 1–4, Supplementary Figures 1–3): `supplementary_k1_nature_energy.pdf` (`SHA-256: 4af4687df82fb48789e2cee08fc8f763222ed4255cab30093d8e3d0ebde0843b`)

## Overview
This archive contains the complete, reproducible physical-telemetry, generator-stack emissions, and counterfactual carbon-accounting pipeline structured strictly to ***Nature Energy* `Analysis`** submission guidelines across three explicitly delineated empirical samples (**Supplementary Box 1**): (1) a `14`-BA EPA CEMS counterfactual carbon-accounting panel (`Sample 2`, `2024-07-01..2026-09-30`, `49.77 TWh` discharged; exact `18`-month same-window overlap `2024-07..2025-12`, `26.05 TWh`) reconciling five EIA-930 telemetry discrepancies, (2) a California curtailment subsample (`Sample 3`, `2024-07-01..2025-12-31`, `13,170` hrs, `4,347.2 GWh` official curtailment) with `B = 1,000` joint contiguous moving-block bootstraps (`1d`/`7d`/`14d`) and a Congestion-Constrained Carbon Break-Even Frontier, and (3) a supporting `49`-BA operational gas-displacement panel (`Sample 1`, `2019–2026`, `3,359,080` hourly rows). Includes `1,066/1,066` days of official CAISO standalone 5-minute `fuelsource.csv` telemetry, direct hourly EPA CEMS generator-stack `CO2` (`1,043,187` BA-hours, `99.94%` plant-to-BA CO2 match via EPA eGRID 2023 rev2), `7` publication figures (`4` Main + `3` Supplementary, `300 DPI PNG` + vector `PDF`), `23`-test regression & *Nature Energy* compliance suite, `REFEREE_RESPONSE_v2.md` / `v3.md` / `v4.md`, and camera-ready Main + SI PDFs.

### Headline Verified Findings (`v4`)
- **Centerpiece (Main Fig. 1 & Table 1) — Fleet-Wide AEF vs. CEMS-MEF Counterfactual Accounting Discrepancy (`49.77 TWh`, 14 Grids):** On identical metered storage dispatch without curtailment absorption (`α = 0`), consumption-weighted AEF implies **`-75.3 kg CO2/MWh (-3.75 Mt CO2)`** of abatement whereas CEMS-MEF estimates **`+74.2 kg CO2/MWh (+3.69 Mt CO2)`**—a **`+7.44 Mt CO2` counterfactual accounting discrepancy** reversing sign in `9/14` grids. Exact Proposition 2 inequality audit verifies `α_b* > 0` (`MEF_dis / MEF_chg < 1 / η_b`) in `14/14` grids, with `MEF_chg >= MEF_dis` strictly in `4/14` grids (`CISO`, `MISO`, `IID`, `CPLE`).
- **Multi-Grid Joint 14-Day Block Bootstrap (Full vs. Exact Same-Window) & Three Independent MEF Validations (Main Fig. 2 & Table 2A):** Resampling all 14 grids, bilateral neighbors, and California curtailment regimes jointly on 14-day contiguous blocks (`B = 1,000`) on BOTH the full `49.77 TWh` window (`2024H2–2026Q3`) and exact `26.05 TWh` same-window overlap (`2024H2–2025`, zero 2026 extrapolation) shows that at `15%` non-California curtailment absorption, fleet net CO2 spans zero (`+0.26 [-0.14, +0.64] Mt` full; `+0.13 [-0.09, +0.35] Mt` same-window), whereas the **discrepancy vs. AEF stays strictly positive** (`+4.01 [+3.60, +4.39] Mt` full; `+1.72 [+1.49, +1.93] Mt` same-window). Three independent validations without shared EIA-930 fuel slopes corroborate CEMS MEFs: direct metered `-∂CO2_CEMS/∂BESS` (`CISO 271 ± 4`, `ERCO 499 ± 3`, `AZPS 222 ± 23`, `MISO 619 ± 84 kg/MWh`), pure CEMS stack slopes (`CISO 376`, `ERCO 516`, `AZPS 597`, `MISO 636`), and EPA eGRID 2023 rev2 Non-Baseload RTE loss floor (`+89.6 kg/MWh = +4.46 Mt`).
- **California Curtailment, Cross-Region Imports & Multi-Day Uncertainty (Main Fig. 3 & Table 2B):** Above `2,000 MW` consecutive interior curtailment, domestic CEMS MEF falls **83%** (`+160.6 → +26.8 kg/MWh`) and import-adjusted system MEF falls **60%** (`+268.8 → +107.0 kg/MWh`). Under `14`-day contiguous block bootstraps (`B = 1,000`), system-wide net CO2 is **`-0.80 kg/MWh` (`14d [-14.20, +12.58]`, `p = 0.920`)** under the main specification and **`+1.34 kg/MWh` (`14d [-21.86, +30.51]`, `p = 0.764`)** under observed `ΔLoad` (domestic-only `-30.64 [-42.78, -17.48]`). Accounting for cross-region imports, **California's net emissions direction remains undetermined**, while naive AEF (`-104.7 kg/MWh`) is decisively ruled out.
- **Congestion-Constrained Carbon Break-Even Frontier & ERCOT Coal-Margin Validation (Main Fig. 4):** Sweeping incremental CAISO capacity `κ ∈ [0.1×, 3.0×]` and local-congestion access `τ_local ∈ {0%, 25%, 50%, 100%}` reveals exact abatement caps (`0%` never abates; `25%` caps near `0.25× / 4.3 GW`; `50%` near `0.47× / 8.1 GW`; `100%` frictionless ceiling saturates near `0.88× / 15.2 GW`). Cross-regional stratification in Texas (`ERCO`, `9.92 TWh`) shows that although `73.6%` of battery charging occurs above `40%` renewables (`28.4%` above `60%`), domestic CEMS MEF stays `495–532 kg/MWh` because high renewables push **coal units onto the operating margin (`279 kg/MWh` coal share = `52%` of MEF above `60%` renewables)**.

## Verification & Reproduction Order
1. **Verify Frozen Checksums & Automated Tests First**:
   ```powershell
   ruff check scripts/ tests/
   pytest -v tests/test_k1_boost.py
   ```
2. **Optional Full End-to-End Regeneration**:
   ```powershell
   python scripts/00_download_external_data.py
   python scripts/01_build_clean_grid_panels.py
   python scripts/02_panel_a_wls_displacement.py
   python scripts/03_cems_carbon_and_caiso_curtailment.py
   python scripts/03b_nature_energy_v4_extensions.py
   python scripts/04_formal_carbon_model.py
   python scripts/06_generate_figures.py
   python scripts/07a_generate_manuscript_md.py
   python scripts/07_verify_citations.py
   python scripts/08_compile_manuscript_pdf.py
   python scripts/09_generate_checksums.py
   ```

## Curated Archive Scope
Heavy raw downloads & compiled parquets (`~177 MB` in `data/` plus `.venv`) are omitted from git and deterministically reproducible via `scripts/00..01`. All 41 core deliverables are pinned in `SHA256SUMS.json`.
