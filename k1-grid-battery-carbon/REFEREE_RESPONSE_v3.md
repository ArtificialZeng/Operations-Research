# Referee Response Log — K1 `v3` (*Nature Energy* Analysis Submission Polish)

**Date:** `2026-11-27`  
**Manuscript:** *Counterfactual Carbon Accounting and Diurnal Gas-Peaker Displacement of U.S. Utility-Scale Battery Storage (2019–2026)*  
**Target Format:** *Nature Energy* (Analysis) | Secondary: *Environmental Science & Technology* / *Nature Communications* / *JEEM*  
**Workspace:** `D:\AI_Science\antigravity\k1_boost_grid_battery_carbon_20261127`

---

## Point-by-Point Summary of `v3` Code-Backed Revisions

### 1. Multi-Day Contiguous Block Bootstraps (`L = 1d, 7d, 14d`; `B = 1,000` Each)
- **Referee Critique:** Resampling single calendar days (`L = 1d`) ignores multi-day synoptic weather and curtailment autocorrelation; extending to contiguous 7-day and 14-day blocks widens California's import-adjusted system 95% confidence intervals (still spanning zero while domestic-only remains strictly negative).
- **Code Action (`scripts/03_cems_carbon_and_caiso_curtailment.py`):** Replaced single-day-only resampling with joint contiguous moving-block bootstraps (`B = 1,000` each at `1d`, `7d`, and `14d` block lengths) simultaneously resampling across all 549 overlap days, 273 post-overlap CEMS days, all 10 CISO bilateral neighbor BAs' 24-hour CEMS MEFs, all 4 interior curtailment regimes, and all 13,170 CAISO hourly charge/discharge weights & RTE:
  - **Main System (`dNetLoad_pot`, `-0.80 kg/MWh`):** `1d 95% CI [-10.39, +8.15]` (`SE = 4.76`) -> `7d [-13.24, +9.83]` (`SE = 5.90`) -> **`14d [-14.20, +12.58]` (`SE = 6.85`, `p = 0.920`)**.
  - **Observed-Load (`ΔLoad`) System (`+1.34 kg/MWh`):** `1d 95% CI [-14.14, +18.62]` (`SE = 8.26`) -> `7d [-17.90, +26.27]` (`SE = 11.20`) -> **`14d [-21.86, +30.51]` (`SE = 13.78`, `p = 0.764`)**.
  - **In-State Domestic Only:** remains strictly negative across all block lengths (`Main -30.64`, `14d [-42.78, -17.48]`; `Observed ΔLoad -30.67`, `14d [-49.02, -8.54]`).

### 2. Unifying Statistical Interpretation & Removing Overclaims
- **Referee Critique:** Wide 95% intervals spanning zero do not "confirm carbon neutrality"; observed `ΔLoad` should not be called "pure exogenous"; and `+7.44 Mt CO2` must always be stated as the discrepancy between two counterfactual models. Additionally, defensive/hype phrases (`Spotless Timing`, `proving rigorously`, `extraordinary correlation`, `Master Forensic Audit`) should be purged, and marginal WCB `p`-values in Table 3 (`0.075–0.130`) should be disclosed transparently in prose.
- **Manuscript, Figure & Test Action (`scripts/06`, `07a`, `08`, `tests/test_k1_boost.py`):**
  - Unified Abstract, Section 1, Section 5.2, Table 5, Figure 4, Figure 4 caption, and Section 6 to state explicitly: **"accounting for cross-region imports, California's net emissions direction remains undetermined"** (while cleanly rejecting naive AEF's `-104.7 kg/MWh` abatement claim).
  - Removed 100% of `"carbon neutral"`, `"carbon neutrality"`, `"pure exogenous"`, `"spotless"`, `"proving rigorously"`, `"extraordinary"`, `"Master Forensic Audit"`, and `"definitively"` across both `manuscript_k1_boost.md` and `manuscript_k1_boost.pdf` (enforced by automated `pytest` guardrails).
  - Explicitly reported both CR1 and finite-cluster wild bootstrap `p`-values in Section 4.2 prose for Table 3 (`Stock(t-12) p_WCB = 0.078`, `Add(t-6..t) p_WCB = 0.128`, Daily Solar×MWh `p_WCB = 0.075`, `+Quad & SolCap p_WCB = 0.130`), framing Sample 1 strictly as supporting operational context.

### 3. Centering Narrative for *Nature Energy* (Analysis) + Curtailment Sensitivity & Saturation Frontier
- **Referee Critique:** Center the paper on the 14-BA counterfactual accounting comparison on the same metered dispatch (`AEF -3.75 Mt` vs. `CEMS-MEF +3.69 Mt`, discrepancy `+7.44 Mt`), use CAISO to illustrate how curtailment and cross-region imports reshape estimates, quantify sensitivity of the 14-BA discrepancy to non-zero curtailment absorption ($\alpha > 0$), and characterize how local transmission congestion creates diminishing marginal decarbonization as storage capacity scales.
- **Code & Manuscript Action (`scripts/04_formal_carbon_model.py`, `07a`, `08`):**
  - Re-centered Title, Abstract, and Section 1 squarely on the **14-BA counterfactual carbon accounting comparison** (Sample 2) as Finding 1, CAISO curtailment & cross-region imports (Sample 3) as Finding 2, EIA-930 telemetry reconciliation as Finding 3, and 49-BA conditional gas displacement (Sample 1) as operational context.
  - Added **Table 4b (14-BA Curtailment-Absorption Sensitivity)**: exact uniform fleet break-even is `18.9%`; substituting CAISO's empirical curtailment-stratified balance (`-0.80 kg/MWh`) for California and sweeping non-CAISO absorption `0%–15%` leaves a fleet net total of `+1.84` to `+0.29 Mt CO2` and a **`+5.59` to `+4.04 Mt CO2` discrepancy** relative to naive AEF (`-3.75 Mt`).
  - Added the **CAISO Congestion-Constrained Incremental Storage Saturation Frontier**: sweeping incremental storage scale `κ = 0.25×` to `3.0×` against observed residual curtailment shows total headroom falling from `40.3%` (`0.25×`) to `18.2%` (`1.0×`, already below `19.9%` break-even) and `10.1%` (`2.0×`), while system-wide (congestion-constrained) headroom stays at `5.3%` / `2.8%` / `1.6%`.
