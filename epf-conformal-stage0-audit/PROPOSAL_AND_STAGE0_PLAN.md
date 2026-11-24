> **STATUS: SUPERSEDED AND FORMALLY CLOSED AT STAGE 0B (2026-11-24).**  
> This initial Stage 0 draft was **never executed on real outcomes** and is **formally closed** by `STAGE0B_BOUNDARY_AND_FRONTIER_CLOSURE.md` and `stage0b_frontier_and_boundary_audit.json`. Its blanket "no revision", "strictly pre-gate SMARD forecasts", and "zero power problem" assertions are retracted: official SMARD PV/wind submissions are due by `18:00` CET (6 hours post-`12:00` gate), EnergyBench spans only `17` live issue days (`2026-10-02`–`2026-10-18`) plus `18` separate backtest issue days (`2026-09-14`–`2026-10-01`), SDAC 15-minute MTU began `2025-10-01`, and 12 verified 2022–2026 primary works (including Brusaferri et al. *Applied Energy* 2025, Ding–Gibbs–Tibshirani `MultiQT`, `O2CP`, `ACM e-Energy` 2026, `SSRN 6731093`, `arXiv:2611.03661`, `MVP`, and `DtACI`) already directly overlap the proposed scope. Retained verbatim below for transparent audit history only.

---

# Stage 0 Research Proposal & Bounded Feasibility Plan: Online Conformal vs. Isotonic Distributional Postprocessing for Day-Ahead Electricity Prices Under Structural Regime Shifts

**Directory:** `epf-conformal-stage0-audit/`  
**Date:** 2026-11-24  
**Domain:** Energy Forecasting / Distribution-Free Uncertainty Quantification / Storage Operations Research (non-biology, non-offensive)  
**Stage:** **Stage 0 Non-Outcome Input, Literature, and Baseline-Solver Integration Check (ZERO real holdout outcomes fitted or inspected).**

---

## 1. Two Closest Verified Primary Sources & External Benchmark Lineage

1. **EPF Distributional Postprocessing SOTA (`Energy Economics` 2024 & `arXiv:2507.15079` 2025/2026):**
   - **Lipiecki, A., Uniejewski, B., & Weron, R. (2024).** *"Postprocessing of point predictions for probabilistic forecasting of day-ahead electricity prices: The benefits of using isotonic distributional regression."* *Energy Economics*, 139, 107934 (`DOI: 10.1016/j.eneco.2024.107934`, `arXiv:2404.02270`).
   - **Lipiecki, A., & Uniejewski, B. (2025/2026).** *"Isotonic Quantile Regression Averaging for uncertainty quantification of electricity price forecasts."* `arXiv:2507.15079`.
   - Built directly on the canonical open-access EPF benchmark **Lago, J., Marcjasz, G., De Schutter, B., & Weron, R. (2021)** (*Applied Energy*, 293, 116983; `epftoolbox`; Zenodo `10.5281/zenodo.4624805`) and **Kath, C., & Ziel, F. (2021)** (*IEEE Trans. Power Systems*, rolling split-conformal prediction for day-ahead power markets).
2. **Distribution-Free Online Conformal Time-Series Theory (`NeurIPS` 2023):**
   - **Angelopoulos, A. N., Candès, E. J., & Tibshirani, R. J. (2023).** *"Conformal PID Control for Time Series Prediction."* *Advances in Neural Information Processing Systems (NeurIPS 2023)*, `arXiv:2307.16895` (generalizing **Gibbs & Candès, 2021**, *NeurIPS 2021*, Adaptive Conformal Inference [ACI]).

---

## 2. Sharp, Falsifiable Scientific Gap (Zero Proxy Narrative)

- Lipiecki et al. (2024) and Lipiecki & Uniejewski (2025/2026) show that rolling-window **Isotonic Distributional Regression (IDR)** and **Isotonic Quantile Regression Averaging (iQRA)** outperform **static rolling-window Conformal Prediction (Kath & Ziel, 2021)** on German day-ahead electricity prices (CRPS, Pinball loss, reliability, and Battery Energy Storage System [BESS] arbitrage).
- **The Unresolved Structural Tension**:
  1. Static rolling CP is *not* online adaptive conformal inference; meanwhile **IDR / iQRA** rely on fixed rolling windows (e.g., `182` days) with **no finite-sample or online coverage guarantee under abrupt non-stationary regime transitions** (such as the post-2022 European gas shock unwinding into the 2024–2026 solar negative-price & evening-ramp regime in Germany `DE-LU`).
  2. Conversely, vanilla **ACI (Gibbs & Candès, 2021)** and **Conformal PID (Angelopoulos et al., 2023)** guarantee long-run marginal coverage under arbitrary distribution shift, yet naive application to 24-hour simultaneous day-ahead price vectors faces a sharp structural flaw: a pooled scalar controller trades off over-coverage in quiet night hours against systematic under-coverage in volatile midday-solar and evening-ramp hours, whereas `24` independent per-hour controllers adapt slowly (1 step/day per hour) and ignore asymmetric upper/lower tail risk unless coupled to an asymmetric quantile/isotonic base postprocessor.
- **One Discriminating Question**:
  > Across the canonical **`epftoolbox` 5-market benchmark** (`NP`, `PJM`, `BE`, `FR`, `DE`: `5 × 730 = 3,650` test days = **`87,600` test hours**, enabling exact reproduction verification against Lago et al. 2021) **AND** a strictly unseen modern **`DE-LU` German SMARD regime-shift hard holdout** (`2024-01-01`–`2026-10-31`: **`> 1,000` test days = `> 24,000` unseen test hours** with official pre-gate-closure load, solar, and wind day-ahead forecasts), does **asymmetric online conformalized distributional postprocessing** (combining `IDR`/`iQRA` base distributions with structured **Conformal PID** / cross-hour volatility-scaled online calibration) strictly improve BOTH **conditional calibration & proper scoring rules** (`CRPS`, `Winkler Score`, `worst-hour conditional coverage gap`, `Kupiec`/`Christoffersen`, multivariate `Diebold-Mariano`) AND **exact LP-solved BESS arbitrage realized profit & CVaR shortfall** relative to:
  > - **B1**: Static rolling Split-Conformal (`CP-LEAR`, Kath & Ziel 2021),
  > - **B2**: Quantile Regression Averaging (`QRA-LEAR`, Nowotarski & Weron 2015),
  > - **B3**: Isotonic Distributional Regression (`IDR-LEAR`, Lipiecki, Uniejewski & Weron 2024),
  > - **B4**: Isotonic QRA (`iQRA-LEAR`, Lipiecki & Uniejewski 2025/2026),
  > - **B5**: Vanilla Online `ACI` (Gibbs & Candès 2021) & `Conformal PID` (Angelopoulos et al. 2023)?

---

## 3. Why This Study Has Zero Power, Revision, or Proxy Ambiguity

- **Huge Effective Sample Size**: `3,650` test days (`87,600` hourly observations) on canonical `epftoolbox` + `> 1,000` unseen test days (`> 24,000` hourly observations) on modern `DE-LU` SMARD `2024–2026`.
- **100% Strictly Real-Time & Non-Revised**: Day-ahead electricity auctions clear at `12:00 CET` on day `d - 1` (binding settlement prices, never revised); SMARD day-ahead forecasts (`411` total load, `125` solar, `123` wind onshore, `3791` wind offshore) are published strictly before auction gate closure.
- **Exact Verifiable Scoring**: Proper scoring rules (`CRPS`, `Pinball`, `Winkler`), exact empirical coverage tests, and deterministic exact LP-solved BESS day-ahead arbitrage profit (`highspy`).

---

## 4. Stage 0 Bounded Non-Outcome Feasibility & Baseline Integration Gate (Executed First)

Before writing any real-data forecasting or evaluation pipeline, `stage0_input_and_baseline_check.py` must verify:
1. Live arXiv metadata for `arXiv:2307.16895`, `arXiv:2404.02270`, and `arXiv:2507.15079`.
2. Live Zenodo `10.5281/zenodo.4624805` metadata and exact headers/date ranges/row counts/missingness across all 5 canonical `epftoolbox` markets (`NP`, `PJM`, `BE`, `FR`, `DE`) + GitHub `jeslago/epftoolbox` availability (**no price modeling or holdout stats**).
3. Live official German Bundesnetzagentur **SMARD** REST API coverage for `DE-LU` price (`4169`) and pre-gate-closure day-ahead forecasts (`411`, `125`, `123`, `3791`, `122`) across `2018-10`–`2026-11`, plus stratified chunk checks verifying non-null completeness and `23h`/`25h` DST clock handling (**strictly non-null presence checks, zero price values inspected or summarized**).
4. Pure synthetic integration & KKT/LP optimality timing checks for every baseline algorithmic primitive (`LEAR` LASSO coordinate descent, exact PAVA `IDR`, `highspy` `QRA`/`iQRA` LP, online `Conformal PID`, and `highspy` `BESS` arbitrage LP) inside our pinned Python `3.14.10` runtime.
