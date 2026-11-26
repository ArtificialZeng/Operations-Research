# Real-World Diurnal Gas-Peaker Displacement and the Carbon-Arbitrage Paradox of U.S. Utility-Scale Battery Storage (2019–2026) (`K1`)

**Status:** FROZEN SUBMISSION-READY ARCHIVE (`2026-11-27`)  
**Target Journals:** Track A (*Nature Energy* / *Nature Climate Change* / *PNAS*) & Track B (*AEJ: Economic Policy* / *JEEM* / *Management Science*; stretch *AER*)

## Overview
This archive contains the complete, reproducible physical-telemetry, smokestack-emissions, and econometric pipeline, formal thermodynamic carbon-arbitrage model, forensic repairs of five federal EIA-930 reporting defects (including an undocumented 2-year `+5,553 MW` California natural-gas corruption), `1,066/1,066` days of official CAISO standalone 5-minute `fuelsource.csv` battery telemetry, official CAISO hourly renewable curtailment logs (`2024–2025`, `4,347.2 GWh`), direct hourly EPA CEMS smokestack `CO2` (`1,043,187` BA-hours, `99.94%` plant-to-BA CO2 match via EPA eGRID 2023 rev2), 5 publication figures (`300 DPI PNG` + vector `PDF`), 21-test regression suite, and 13-page camera-ready manuscript PDF.

### Headline Verified Findings
- **Pillar 1 — Federal Telemetry Forensics (`52,816.8 GWh` Discharged Across 14 Grids):** Exposes and repairs five EIA-930 defects: (i) a 2-year `+5,553 MW` mean (`+7,639 MW` peak) midday `CISO` natural-gas inflation (`2023-12..2025-12`, lifting CEMS lag-0 correlation from `r = 0.835` to `0.9962`), (ii) `ERCO` (`7,224 GWh`) and `AZPS` (`5,690 GWh`) routing charging into `Unknown Energy Storage` (`RTE`: `1.49 → 0.778` and `∞ → 0.875`), (iii) standalone `CAISO` `fuelsource.csv` `RTE = 0.863` (vs. broken EIA-930 `1.076`; 13 clean AC-coupled grids fleet `RTE = 0.845`), (iv) filtering `FPL`'s `2,668 MW` glitch (`2025-08-27 HE 6`), and (v) verifying `0/4` pumped-hydro leakage. Exact 4-window diurnal taxonomy shows Southwest grids draw `71%–83%` midday solar (`0.9%–5.8%` overnight) while `MISO` (`56.7%`), `SOCO` (`56.4%`), and `DUK` (`50.6%`) draw over half of charging energy overnight (`23:00–06:00`).
- **Pillar 2 — Nationwide Demand-Weighted WLS Causal Gas-Peaker Displacement (`G = 49, N = 4,589`):** Expanding BESS by `1%` of baseline demand reduces evening-minus-midday natural gas by **`-0.3352` (`SE = 0.0570, t_CR1 = -5.88, t_2way = -5.84, p_Rad = 0.004, p_Webb6 = 0.002, RI p = 0.0010`)**, strengthening outside California and Texas (`Drop CISO & ERCO, G = 47: -0.3810, t = -6.29, p_Rad = 0.002`), surviving `Drop Top-7 BESS (G = 42: -0.3166)`, `BA × Post2024H2 FE (-0.3231, p_Rad = 0.001)`, 49-BA LOBAO (`∈ [-0.3651, -0.2923], max p = 0.0015`), peaking at Hour Ending 20 (`-0.2912, t = -8.95`), passing spotless distributed 6-month future lead tests (`F = 0.082, p = 0.921`), passing high-frequency daily `BA × Year-Month FE` (`N = 139,497, t = -3.60`), confirming the Proposition 1 Energy (`MWh`) vs. Power (`MW`) duration horse-race (`MWh p_WCB = 0.037` vs `MW p_WCB = 0.929`), and returning a precision zero on baseload Nuclear (`-0.0005, p_Rad = 0.291`).
- **Pillar 3 — Direct EPA CEMS Smokestack `CO2` Carbon-Arbitrage Paradox (`49,771.3 GWh`, 14 Grids):** Without curtailment credit, naive consumption-weighted AEF accounting claims **`-75.3 kg CO2/MWh (-3.75 Mt CO2)`** of abatement, whereas direct hourly EPA CEMS smokestack MEFs (with exact `24×24` date-clustered covariances) measure **`+74.2 kg CO2/MWh (+3.69 Mt CO2)`**—a **`+7.44 Mt CO2` sign reversal** (`9/14` grids flip sign), cross-validated against independent 24-hour EPA eGRID 2023 rev2 Peaker MEFs (`r = 0.977, MAD = 9.8 kg/MWh`).
- **Pillar 4 — Non-Circular Empirical CAISO Interior Curtailment Proof (`13,170` hrs):** Restricting strictly to interior curtailment regimes (`both t and t-1 in bin`), real curtailment slashes CAISO's domestic CEMS MEF by **83%** (`+160.6 → +26.8 kg/MWh`), instrument-free pure exogenous `∂CO2/∂Load` by **83%** (`+164.4 → +27.9`), and system CEMS MEF by **60%** (`+268.8 → +107.0`), while marginal un-curtailment jumps from exact **`0.0%`** to **`62.4%`**. Yet because `84.9%` of CAISO curtailment is local congestion, empirical marginal curtailment absorption (`α̂_unspill = 14.1%`, `α̂_MEF = 16.7%`) and incremental residual headroom (`ρ_res = 18.2%`, `2.8%` system-only) sit below CAISO's break-even threshold `α*_CISO = 19.9%`, yielding curtailment-stratified CAISO net CO2 of **`-0.8 kg/MWh` system-wide (`-30.6 kg/MWh` domestic)**—erasing `>99%` of naive AEF's `-104.7 kg/MWh` claim.

## Verification & Reproduction Order
1. **Verify Frozen Checksums & Automated Tests First** (before rerunning scripts that regenerate outputs):
   ```powershell
   ruff check scripts/ tests/
   pytest -v tests/test_k1_boost.py
   ```
2. **Optional Full End-to-End Regeneration** (requires EIA-930 `2019–2026`, EIA-860M, CAISO `fuelsource.csv` & curtailment workbooks, EPA eGRID 2023 rev2, and Catalyst PUDL EPA CEMS S3 parquet):
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
Heavy raw downloads & compiled parquets (`~177 MB` in `data/` plus `.venv`) are omitted from git and deterministically reproducible via `scripts/00..01`. All 30 core deliverables (scripts, tests, 6 JSON receipts, 5 PNG + 5 vector PDF figures, `manuscript_k1_boost.md`, and 13-page `manuscript_k1_boost.pdf`) are pinned in `SHA256SUMS.json`.
