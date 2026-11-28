# Referee Response Log — K1 `v5` (*Nature Energy* `Analysis` Major Revision)

**Date:** `2026-11-28`  
**Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my`)  
**Main Manuscript PDF:** `manuscript_k1_nature_energy.pdf`  
**Supplementary Information PDF:** `supplementary_k1_nature_energy.pdf`  
**Independent Reproducibility Package:** `REPRODUCIBILITY.md` + `tables/*.csv`  
**New Computation Script & Receipt:** `scripts/03c_k1_v5_unconditional_audit.py` → `results/03c_k1_v5_unconditional_audit.json`

---

## Point-by-Point Response to Peer Review (`K1.md`)

### Reviewer Comment 1 — Complete Conditioning Statement, Full Unconditional Season-Stratified UTC-Day Bootstrap (`L = 7, 14, 28` d), Leave-BA-Out, Same-Window Trade Weights, Table 1–2 Bridge, and `99.94%` Match-Rate Wording
- **Unconditional vs. Conditional Bootstraps (`scripts/03c_k1_v5_unconditional_audit.py`, Main Table 2A, Main Fig. 2a, Supplementary Table 5):**
  - We downloaded official `EIA930_INTERCHANGE_2024_Jul_Dec.csv` to cover the complete `2024-07-01..2026-09-30` window (`75,629` BA–DIBA–UTC-day bilateral rows), retained our earlier **conditional** 14-day intervals (explicitly labeled as fixed AEF, fixed discharge volumes, and fixed 2025–2026 trade weights), and implemented a **full unconditional season-stratified (`DJF`/`MAM`/`JJA`/`SON`) joint UTC-day moving-block bootstrap (`B = 1,000`)** side-by-side at **`L = 7, 14, 28` days**.
  - On every resampled UTC-day block, we simultaneously re-estimate: (a) exact hour-by-hour consumption-weighted AEF, (b) 24-hour domestic & neighbor CEMS MEFs and marginal import shares, (c) hourly cycling volumes, RTE, and unfixed BA discharge weights, (d) exact same-window bilateral trade weights (`weight` and `imp_weight`), and (e) CAISO interior curtailment slopes.
  - Full-window (`49.77 TWh`) unconditional 14d CIs widen by `1.85×` relative to matched conditional intervals at `α = 0%` (`+7.44 [+6.97, +7.98] Mt`; `7d [+7.02, +7.88]`; `28d [+6.90, +8.14]`; AEF `-3.73 [-3.95, -3.54] Mt`) and by `1.22×` at Hybrid `15%` (`+4.03 [+3.62, +4.35] Mt`; `7d [+3.63, +4.27]`; `28d [+3.66, +4.40]`; fleet net CO₂ spans zero at `+0.29 [-0.06, +0.57] Mt`).
  - Exact 18-month same-window (`26.03 TWh`, `2024-07..2025-12`) unconditional results confirm strictly positive discrepancies at `α = 0%` (`+3.95 [+3.57, +4.47] Mt`; `7d [+3.65, +4.33]`; `28d [+3.46, +4.62]`) and Hybrid `15%` (`+2.20 [+1.95, +2.44] Mt`; `7d [+1.97, +2.40]`; `28d [+1.97, +2.52]`; fleet net CO₂ spans zero at `+0.16 [-0.03, +0.33] Mt`).
- **Exact Reconciliation Bridge (`+7.44 Mt` Table 1 vs. `+7.42 Mt` v4 Table 2):**
  - Documented transparently in Main Table 2 notes, Methods, and Supplementary Table 5: the `0.0238 Mt` gap between Table 1 (`+7.4417 Mt`, Step 03) and v4 conditional Table 2 (`+7.4179 Mt`, Step 03b) splits cleanly into `+0.0019 Mt` from the `|BESS| > 0.5 MW` & CEMS-matched mask and `-0.0247 Mt` from estimating marginal import shares on untrimmed `d_disp + d_imp` versus Step 03's 8×-MAD-trimmed `d_need`. Updating Table 1's exact estimator to same-window `2024-07..2026-09` UTC bilateral trade weights shifts the discrepancy by only `+0.0017 Mt` to `+7.4434 Mt`. On the 18-month overlap, replacing v4's 24-hour-averaged AEF shortcut (`-1.58 Mt`) with Step 03's exact hour-by-hour consumption AEF (`-2.04 Mt`, matching the full-window `-75.3 kg/MWh` intensity closely at `-78.2 kg/MWh`) cleanly explains the `+0.48 Mt` shift from `+3.47` to `+3.95 Mt`.
- **Leave-One-BA-Out (`LOBAO`) & Bounded Geographic Scope:**
  - Reported in Main Text, Main Table 2A, Main Fig. 2a, and Supplementary Table 5: `CISO + ERCO` represent `78.5%` of observed discharge and `CISO` alone contributes `65.5%` of the baseline discrepancy. Sign reversal persists across all `14/14` leave-one-BA-out sub-fleets; dropping `CISO` yields `+2.57 [+2.30, +2.83] Mt` (`+124.7 kg/MWh`), dropping `ERCO` yields `+5.80 Mt`, and dropping BOTH `CISO` and `ERCO` yields `+0.93 [+0.80, +1.04] Mt` (`+87.1 kg/MWh`) across the remaining 12 grids (`10.70 TWh`, `21.5%` of discharge). Claims are explicitly bounded throughout the Abstract, Main Text, and Discussion to these 14 observed U.S. markets and historical dispatch.
- **`99.94%` Match-Rate Wording:**
  - Replaced `"covering 99.94% of U.S. fossil stack emissions"` everywhere with `"achieving a 99.94% plant-to-BA CO2 match rate within the sampled EPA CEMS fossil archive"` (enforced in `tests/test_k1_boost.py`).

### Reviewer Comment 2 — Out-of-Sample Holdout, Leave-Quarter-Out CV, Hourly Lead-Lag Diagnostics (`k = -3..+3`), and Honest Measurement-Cross-Check Framing
- **Pre-Specified Out-of-Sample Validation (`scripts/03c_k1_v5_unconditional_audit.py`, Main Fig. 2b, Supplementary Table 6):**
  - Pre-specified four quantitative transferability criteria: (1) temporal holdout (`2024-07..2025-09` training predicting held-out `2025-10..2026-09` hourly `ΔCO₂_CEMS`) pooled & discharge-weighted `R² > 0.70`; (2) discharge-weighted calibration slope in `[0.85, 1.15]`; (3) held-out counterfactual discrepancy error `< 10%`; and (4) `9/9` sign preservation in 9-quarter leave-quarter-out CV.
  - **All 4 criteria pass:** Temporal holdout yields pooled `R² = 0.938`, discharge-weighted `R² = 0.761`, calibration slope `0.872` (`ERCO 0.967`, `MISO 0.945`, `CISO 0.759`, heavily interconnected `AZPS 0.385`), and held-out counterfactual discrepancy `+4.23` vs. `+4.38 Mt` actual (`3.5%` error). 9-quarter LQO CV achieves mean major-4 `R² = 0.952` with `9/9` quarters preserving positive discrepancy.
- **Hourly Lead-Lag Diagnostic (`k = -3..+3` h on `ΔBESS → ΔCO₂_CEMS` & `ΔImports`):**
  - Large-fleet grids concentrate `94.6%–96.1%` of `∑|β_k|` strictly at contemporaneous `k = 0` (`CISO -270.6 ± 4.4`, `ERCO -495.6 ± 3.7`, `AZPS -221.7 ± 22.7 kg/MWh`), while revealing small but statistically non-zero `k = -1` anticipation (`≤2.4%` of `k = 0`; `F = 10.28` in `CISO`, `5.81` in `ERCO`) and substantial simultaneity in small-fleet `MISO` (`47.3%` at `k = 0`, `F = 4.06`). Contemporaneous `ΔImports/ΔBESS` directly confirms `-0.675 ± 0.008 MW/MW` import displacement in `CISO` versus `-0.022 ± 0.002` in islanded `ERCO`.
- **Honest Framing of Benchmarks & Contribution:**
  - Explicitly reframed `-∂CO₂/∂BESS`, pure CEMS internal stack slopes, and eGRID 2023 Non-Baseload `(1/η - 1)` strictly as **measurement and order-of-magnitude cross-checks** (explicitly noting that `eGRID × (1/η - 1)` is positive by algebraic construction when `eGRID > 0, η < 1`, and that direct BESS / stack regressions share CEMS data and dispatch simultaneity).
  - Positioned the study cleanly as **commercial-scale counterfactual carbon-accounting model comparison and verifiable error boundaries across observed market dispatch**, explicitly noting that nodal SCED/OPF replay and exogenous forced-outage instrumental variables remain priorities for future work.

### Reviewer Comment 3 — Fixed-Profile BA-Level Upper-Bound Scenarios & ERCOT Cross-Regime Matched Stress Test
- **CAISO Capacity Scenarios (Main Fig. 4a):**
  - Explicitly reframed everywhere (`0.0 / 4.3 / 8.0 / 15.2 GW`, now computed dynamically as exact continuous break-even roots in `03c`) strictly as **fixed-profile BA-level upper-bound accounting scenarios** rather than nodal-deliverability capacity guarantees, explicitly disclosing the absence of nodal LMPs, SOC dynamic optimization, binding transmission shadow prices, and endogenous import re-optimization.
- **ERCOT Matched Cross-Regime Stress Test (Main Fig. 4b & Supplementary Table 6):**
  - Framed ERCOT transparently as a **cross-regime renewable-penetration stress test** (explicitly noting public interval-level ERCOT curtailment is absent from EIA-930 and SCED marginal-resource verification remains future work).
  - Verified that ERCOT's high-renewable coal margin persists after controlling strictly for diurnal, seasonal, and load-level confounding:
    - **Exact-matched common-support `Season × Hour × Load-Quartile` (`120` cells, reweighting `<40%` to the exact `>60%` cell distribution):** ERCOT MEF increases from `486.3` to `533.8 kg/MWh` (`+47.5 ± 12.9`, `p < 0.001`) and coal MEF increases from `206.9` to `290.2 kg/MWh` (`+83.3 ± 16.2`, `p < 0.001`), contrasting sharply with exact-matched `CISO` (`72` cells: `148.3 → 85.7`, `-62.6 ± 20.0 kg/MWh`).
    - **Fine-cell `Season × Hour × Load-Decile` FE:** ERCOT `>60%` stays at `528.8 kg/MWh` (`coal 286.3`) versus `CISO 65.6 kg/MWh`.
    - **Midday Solar (`10:00–16:00`) split:** ERCOT `>60%` midday hours (`1,313` obs, `89` cells) retain total MEF `535.5 ± 8.4` and coal MEF `291.2 ± 10.4 kg/MWh`.

### Reviewer Comment 4 — Independent Reproducibility Package
- Exported 4 clean, LF-normalized machine-readable CSV tables directly from verified JSON receipts into `tables/`:
  - `tables/table1_14ba_accounting.csv`
  - `tables/table2_joint_bootstrap_curtailment.csv`
  - `tables/fig4_frontier_and_ercot.csv`
  - `tables/table_oos_and_leadlag.csv`
- Added standalone `REPRODUCIBILITY.md` documenting exact public URLs, date ranges, archive versions, software environment, exact script execution order, and direct entry points to reconstruct Main Table 1, Main Table 2, Main Figure 4, and all CSVs.
- Preserved 49-BA gas-displacement results cleanly in the separate Supplementary Information PDF (`supplementary_k1_nature_energy.pdf`) and pinned all `v5` deliverables in `SHA256SUMS.json`.
