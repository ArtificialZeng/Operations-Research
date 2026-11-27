# Referee Response Log — K1 `v4` (Strict *Nature Energy* `Analysis` Submission Package)

**Date:** `2026-11-28`  
**Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my`)  
**Main Manuscript PDF:** `manuscript_k1_nature_energy.pdf`  
**Supplementary Information PDF:** `supplementary_k1_nature_energy.pdf`

---

## Point-by-Point Summary of `v4` Formatting & Scientific Upgrades

### 1. Strict *Nature Energy* `Analysis` Official Format Compliance & Authorship
- Replaced placeholder metadata (`Target Venues`, `Target Format`, `Data Universe`, `Track A/B`) completely with the exact author block (`Zijian Zeng`, `Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA`, `zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my`).
- Restructured the manuscript to follow *Nature Energy*'s official `Analysis` template verbatim:
  - **Abstract:** strictly `100–150` words, unreferenced (enforced programmatically in `pytest`).
  - **Introduction:** strictly without heading.
  - **Main text:** divided by four concise topical subheadings (no numbered sections).
  - **Discussion:** strictly without subheadings.
  - **Main body word count:** strictly `<= 3,000` words excluding Abstract, Methods, References, Tables, and Figure legends (enforced programmatically in `pytest`).
  - **Display items:** `4` Main Figures strictly numbered in order of appearance (Figure 1: Fleet Accounting Discrepancy; Figure 2: 14-BA Joint Bootstrap + Independent MEF Validation; Figure 3: California Curtailment Collapse & Multi-Day Block Bootstrap; Figure 4: Congestion-Constrained Break-Even Frontier + ERCOT Coal-Margin Validation) + `2` Main Tables = `6` items (`<= 8` limit).
  - **Methods & Supplementary Information:** moved heavy data engineering, telemetry forensics, 49-BA WLS robustness tables, distributed leads, daily dispatch, duration horse-race, and BA-level validation tables cleanly into `Methods` and a dedicated `supplementary_k1_nature_energy.pdf` (Box S1, Tables S1–S4, Figures S1–S3).

### 2. Fixed Proposition 2 Mathematical Inequality Logic
- Corrected the earlier logical slip claiming `MEF_chg >= MEF_dis` across all 14 grids: `scripts/03b_nature_energy_v4_extensions.py` verifies that all `14/14` grids satisfy the exact break-even condition `MEF_dis / MEF_chg < 1 / eta_b` (`alpha_b* > 0`), whereas `MEF_chg >= MEF_dis` holds specifically in `4/14` grids (`CISO`, `MISO`, `IID`, `CPLE`), and in the remaining `10/14` grids (`ERCO`, `AZPS`, `PNM`, `SOCO`, etc.) `MEF_dis > MEF_chg` yet the diurnal spread is too narrow to overcome round-trip efficiency losses.

### 3. Same-Window (`2024H2–2025`) Sensitivity & Full 14-BA Joint 14-Day Block Bootstrap
- Added `scripts/03b_nature_energy_v4_extensions.py` implementing a full 14-BA + bilateral-neighbor + CAISO-curtailment joint 14-day contiguous moving-block bootstrap (`B = 1,000`) on BOTH the full 27-month window (`49.77 TWh`) and the exact 18-month same-window overlap (`2024-07..2025-12`, `26.05 TWh`, eliminating temporal extrapolation into 2026):
  - At non-CAISO `alpha = 15%`, fleet net CO2 spans zero (`+0.26 [-0.14, +0.64] Mt` full; `+0.13 [-0.09, +0.35] Mt` same-window), transparently reported in Main Table 2 and Figure 2a.
  - Across every scenario in both windows, the **counterfactual accounting discrepancy relative to naive AEF** stays strictly positive far above zero (`+7.42 [+7.11, +7.78]` to `+4.01 [+3.60, +4.39] Mt` full; `+3.47 [+3.29, +3.69]` to `+1.72 [+1.49, +1.93] Mt` same-window).

### 4. Three Independent MEF Validations (Zero Shared EIA-930 Fuel Slopes)
- **Direct metered hourly battery-dispatch CEMS regressions (`-dCO2_CEMS / dBESS_MW`):** `CISO 271.3 (±4.2)`, `ERCO 499.3 (±3.4)`, `AZPS 222.3 (±22.5)`, `MISO 618.6 (±84.4) kg/MWh`—matching direct `dCO2/dLoad` and 24-hour CEMS MEFs without dispatchable-generation slopes.
- **Pure CEMS internal stack ramp slopes (`dCO2 / dGrossLoad_CEMS`, zero EIA-930):** `CISO 376`, `ERCO 516`, `AZPS 597`, `MISO 636 kg/MWh`.
- **Official EPA eGRID 2023 rev2 BA Non-Baseload CO2 output rates (zero hourly regressions):** pure round-trip loss floor yields `+89.6 kg/MWh (+4.46 Mt CO2)`, independently reproducing the sign reversal relative to AEF (`-3.75 Mt`).

### 5. Congestion-Constrained Carbon Break-Even Frontier & Cross-Regional Validation in ERCOT (`9.92 TWh`)
- Built the **Congestion-Constrained Carbon Break-Even Frontier** (Main Figure 4a) over incremental storage scale `kappa in [0.1x, 3.0x]` and local-congestion access `tau_local in {0%, 25%, 50%, 100%}`, quantifying exact break-even expansion caps (`0%` never abates; `25%` caps near `0.25x / 4.3 GW`; `50%` near `0.47x / 8.1 GW`; `100%` frictionless ceiling saturates near `0.88x / 15.2 GW`).
- Added **cross-regional interior renewable-penetration stratification** across `ERCO` (`9.92 TWh`), `CISO`, `MISO`, and `AZPS` (Main Figure 4b): unlike zero-coal CAISO (dropping to `70 kg/MWh` above `60%` renewables), ERCOT's CEMS MEF stays at `495–532 kg/MWh` even above `60%` renewables (`73.6%` of ERCOT charging occurs above `40%` renewables) because high wind/solar displaces gas peakers and forces **coal units onto the operating margin (`279 kg/MWh` coal share above `60%` renewables)**.
