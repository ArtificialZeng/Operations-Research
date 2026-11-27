# Counterfactual Carbon Accounting and Diurnal Gas-Peaker Displacement of U.S. Utility-Scale Battery Storage (2019–2026) (`K1`)

**Status:** FROZEN SUBMISSION-READY ARCHIVE (`v3` *Nature Energy* Analysis Submission Polish, `2026-11-27`)  
**Target Format:** *Nature Energy* (Analysis) | Secondary Venues: *Environmental Science & Technology* / *Nature Communications* / *JEEM*

## Overview
This archive contains the complete, reproducible physical-telemetry, generator-stack emissions, and counterfactual carbon-accounting pipeline across three explicitly delineated empirical samples (**Box 1** in manuscript): (1) a `14`-BA EPA CEMS counterfactual carbon-accounting panel (`Sample 2`, `2024-07-01..2026-09-30`, `49.77 TWh` discharged) reconciling five EIA-930 telemetry discrepancies, (2) a California curtailment subsample (`Sample 3`, `2024-07-01..2025-12-31`, `13,170` hrs, `4,347.2 GWh` official curtailment) with `B = 1,000` joint contiguous moving-block bootstraps at `1d`, `7d`, and `14d` block lengths and a congestion-constrained incremental saturation frontier, and (3) a `49`-BA operational gas-displacement panel (`Sample 1`, `2019–2026`, `3,359,080` hourly rows). Includes `1,066/1,066` days of official CAISO standalone 5-minute `fuelsource.csv` telemetry, direct hourly EPA CEMS generator-stack `CO2` (`1,043,187` BA-hours, `99.94%` plant-to-BA CO2 match via EPA eGRID 2023 rev2), 5 publication figures (`300 DPI PNG` + vector `PDF`), 23-test regression suite, `REFEREE_RESPONSE_v2.md`, `REFEREE_RESPONSE_v3.md`, and camera-ready manuscript PDF.

### Headline Verified Findings (`v3`)
- **Centerpiece (Sample 2) — Fleet-Wide AEF vs. CEMS-MEF Counterfactual Accounting Discrepancy (`49.77 TWh`, 14 Grids):** Evaluated on identical metered storage dispatch without curtailment absorption (`α = 0`), a naive consumption-weighted AEF counterfactual implies **`-75.3 kg CO2/MWh (-3.75 Mt CO2)`** of abatement, whereas a CEMS-MEF marginal displacement counterfactual (with exact `24×24` date-clustered covariances) estimates **`+74.2 kg CO2/MWh (+3.69 Mt CO2)`**—a **`+7.44 Mt CO2` counterfactual accounting discrepancy** (`9/14` grids reverse sign; EPA eGRID 2023 rev2 cross-validation `r = 0.977, MAD = 9.8 kg/MWh`). **Table 4b** shows this gap persists under non-zero curtailment sensitivity: uniform fleet break-even is `18.9%`, and substituting CAISO's empirical curtailment-stratified estimate (`-0.80 kg/MWh`) for California while allowing `0%–15%` absorption across the other 13 grids leaves a **`+5.59` to `+4.04 Mt CO2` discrepancy** vs. AEF.
- **Sample 3 — CAISO Curtailment Stratification, Cross-Region Imports, Multi-Day Block Bootstraps & Saturation Frontier (`13,170` hrs):** Restricting strictly to consecutive interior curtailment hours (`both t and t-1 in bin`), curtailment `>2,000 MW` reduces California's **in-state domestic** CEMS MEF by **83%** (`+160.6 → +26.8 kg/MWh`) and **import-adjusted system-wide** CEMS MEF by **60%** (`+268.8 → +107.0 kg/MWh`), while marginal un-curtailment climbs from `0.0%` to `62.4%`. Because `84.9%` of curtailment is local congestion, incremental residual headroom falls rapidly with scale (`κ = 0.25×/1.0×/2.0×`: `40.3%/18.2%/10.1%` total vs. `5.3%/2.8%/1.6%` system-only vs. `α*_CISO = 19.9%`). Under conservative **`B = 1,000` 14-day contiguous block bootstraps**, CAISO system-wide net CO2 is **`-0.80 kg/MWh` (`14d 95% CI [-14.20, +12.58]`, `p = 0.920`; `7d [-13.24, +9.83]`; `1d [-10.39, +8.15]`)** under the main specification and **`+1.34 kg/MWh` (`14d 95% CI [-21.86, +30.51]`, `p = 0.764`)** under an alternative observed-load (`ΔLoad`) specification (domestic-only: **`-30.64 kg/MWh`**, `14d [-42.78, -17.48]`). Accounting for cross-region imports, **California's net emissions direction remains undetermined**, while naive AEF's `-104.7 kg/MWh` abatement claim is decisively rejected.
- **Telemetry Reconciliation & Operational Context (Sample 1: `G = 49, N = 4,589`):** Reconciles five EIA-930 discrepancies—including a 2-year `+5,553 MW` EIA-930 vs. CAISO/CEMS midday natural-gas reporting discrepancy, `ERCO`/`AZPS` `Unknown Energy Storage` charging recovery, standalone CAISO `RTE = 0.863`, `FPL` `2,668 MW` outlier filtering, and `0/4` pumped-hydro leakage. Demand-weighted WLS shows conditional diurnal natural-gas displacement (`-0.3352, p_Rad = 0.004`; Drop CISO & ERCO `-0.3810`; Nuclear placebo `-0.0005`), transparently contrasted against the solar-confounded uncontrolled baseline (`No Controls = -0.0579, p_Rad = 0.576`) and disclosing conservative finite-cluster WCB `p`-values (`0.075–0.130`) on Table 3 sub-components.

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
   python scripts/04_formal_carbon_model.py
   python scripts/06_generate_figures.py
   python scripts/07a_generate_manuscript_md.py
   python scripts/07_verify_citations.py
   python scripts/08_compile_manuscript_pdf.py
   python scripts/09_generate_checksums.py
   ```

## Curated Archive Scope
Heavy raw downloads & compiled parquets (`~177 MB` in `data/` plus `.venv`) are omitted from git and deterministically reproducible via `scripts/00..01`. All 32 core deliverables are pinned in `SHA256SUMS.json`.
