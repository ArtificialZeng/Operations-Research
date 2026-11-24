# Stage 0B Frontier & Information-Boundary Closure (`epf-conformal-stage0-audit`)

**Date:** 2026-11-24  
**Status:** **FORMALLY CLOSED AT STAGE 0B — ZERO REAL ELECTRICITY PRICE OUTCOMES FITTED, RANKED, OR ARCHIVED.**

---

## 1. Decisive Closure Verdict (No Renaming of Overlapping Ideas)

Following the Stage 0 and Stage 0B non-outcome audits (`audit/stage0_input_and_baseline_check.json`, `audit/stage0b_frontier_and_boundary_audit.json`), this prospective conformal/isotonic day-ahead electricity price forecasting (EPF) study is **formally closed at Stage 0** without running real-outcome trials or renaming an overlapping contribution. Both the **vetted pre-gate input gate** and the **external novelty-gap gate** fail cleanly.

---

## 2. Verified Information-Boundary, Resolution, and Sample-Support Findings

1. **SMARD (`DE-LU`, `2018-10`–`2026-11`) Post-Gate Vintage Boundary:**  
   Official Bundesnetzagentur SMARD documentation (`https://www.smard.de/home/neu-prognostizierte-pv-und-windenergieeinspeisung-208702`) states that next-day PV and wind generation forecast submissions are due by **`18.00 Uhr`** — **6 hours after** the `12:00` CET SDAC/EPEX SPOT day-ahead auction gate. Present-day HTTP availability does not certify historical publication timing, and EU Regulation 543/2013 Art. 6's load forecast deadline does not certify which publication vintage SMARD stores in `411` (`425` weekly chunks from `2018-10`, nominal `~2,975` days; `151` chunks from `2024-01`, nominal `~1,057` days). Excluding uncertified SMARD exogenous series leaves only a pure price-history + calendar baseline (`4169` only).
2. **Foretec EnergyBench (`ujohn33/foretec-energy-bench`, DOI `10.57967/hf/11052`) Smoke-Sized Live Window & SDAC 15-Minute MTU Boundary:**  
   Verified live via HuggingFace Datasets Server API (`audit/stage0b_frontier_and_boundary_audit.json`): EnergyBench freezes pre-`11:30` CET inputs across `39` models (`6` zones, `60,480` actuals rows), explicitly split into **`17` live issue days (`2026-10-02`–`2026-10-18`, `4,438` score rows)** and **`18` separate backtest issue days (`2026-09-14`–`2026-10-01`, `15,642` score rows)**. Seventeen live issue days are smoke-sized and cannot support model ranking or multi-season online calibration. Per NEMO/SDAC go-live schedule, European SDAC **15-minute MTU** delivery began **`2025-10-01`**, so historical hourly aggregates cannot enter a 15-minute live board without native delivery-slot mapping.
3. **Legacy `epftoolbox` (`Zenodo 4624805`, `BE/FR/DE/NP/PJM`):**  
   All 5 CSVs (`52,416` hourly rows = `2,184` **nominal** 24-hour days/market, `730` **nominal** 24-hour holdout days/market) end in `2016–2018`, lack archival pre-`12:00` vintage certification for stored historical TSO forecast exports, and represent serially dependent multi-day vectors (not independent hourly observations).

---

## 3. Verified Directly Overlapping Primary Literature (12 Works Audited via arXiv & Crossref)

1. **Brusaferri, A., Ballarino, A., Grossi, L., & Laurini, F. (2025).** *"On-line conformalized neural networks ensembles for probabilistic forecasting of day-ahead electricity prices."* *Applied Energy*, `DOI: 10.1016/j.apenergy.2025.126412` (open CNR preprint; executable `https://github.com/bruale/PefCodeBench`): already performs online conformal recalibration of day-ahead electricity price distributions across Germany and Italy with improved hourly coverage and stable proper scores.
2. **Ding, T., Gibbs, I., & Tibshirani, R. J. (`arXiv:2512.23671v2`, 2025/2026).** *"Calibrated Multi-Level Quantile Forecasting"* (`MultiQT`): already delivers monotone multi-quantile online calibration under delayed feedback and bounded outcomes, evaluated on energy forecasting.
3. **Li, R., Menacho, D., & Rodríguez, A. (`arXiv:2508.13362v3`, 2025/2026).** *"Optimization-based Online Conformal Prediction for Multi-step Forecasting"* (`O2CP`): already jointly optimizes online intervals across lead horizons under coverage preservation.
4. **He, X., Wang, Z., Yuan, K., & Tong, Y. (2026).** *"Online Multiscale Conformal Calibration for Response-Defined Wind-Ramp Groups."* *Processes*, `DOI: 10.3390/pr14193119`: directly studies batched group feedback in renewable energy forecasting.
5. **Agrawal, A., & O'Sullivan, A. (`arXiv:2611.03661v1`, `2026-09-22`).** *"Tail reliability in probabilistic electricity price forecasts: comparing model combination and conformal prediction in the GB day-ahead market."*
6. **Lipiecki, A., Uniejewski, B., & Weron, R. (2024).** *Energy Economics* 139, 107934 (`arXiv:2404.02270v2`): IDR vs. QRA and rolling CP on day-ahead electricity prices.
7. **Lipiecki, A., & Uniejewski, B. (2025; updated `2026-11-06`).** `arXiv:2507.15079v2`: Isotonic QRA (`iQRA`) vs. CP/IDR/DDNN + BESS arbitrage.
8. **Wu, Y., Yi, M., Xu, B., & Anderson, J. (2026).** *Proc. 17th ACM e-Energy*, `DOI: 10.1145/3744255.3798116`: *"Online Energy Storage Arbitrage under Imperfect Predictions: A Conformal Risk-Aware Approach."*
9. **Hoxha, J., Thanasi, M., Khalifa, T., & Kulaglic, A. (2026).** `DOI: 10.2139/ssrn.6731093`: *"Decision-level conformal profit calibration for battery arbitrage in day-ahead electricity markets: a public seven-market benchmark."*
10. **Bastani, O., Gupta, V., Jung, C., Noarov, G., Ramalingam, R., & Roth, A. (NeurIPS 2022).** `arXiv:2206.01067v1`: *"Practical Adversarial Multivalid Conformal Prediction"* (`MVP`).
11. **Angelopoulos, A. N., Candès, E. J., & Tibshirani, R. J. (NeurIPS 2023).** `arXiv:2307.16895v1`: *"Conformal PID Control for Time Series Prediction."*
12. **Gibbs, I., & Candès, E. J. (JMLR 2024).** `arXiv:2208.08401v3`: *"Conformal Inference for Online Prediction with Arbitrary Distribution Shifts"* (`DtACI`).

---

## 4. Explicit Methodological & Distribution Clarifications Logged

- `PROPOSAL_AND_STAGE0_PLAN.md` is retained as **SUPERSEDED AND FORMALLY CLOSED AT STAGE 0B** (never executed on real outcomes). Blanket "no revision", "pre-gate SMARD forecasts", and "zero power problem" claims are retracted.
- **Marginal Distribution vs. Joint Dispatch Dependence:** Marginal CRPS requires a **valid marginal forecast distribution** (e.g., monotonic, non-crossing quantile functions at each delivery slot); **cross-hour dependence / rank coherence** is separately required when generating joint multi-hour dispatch scenarios (e.g., for storage scheduling). Standard ACI guarantees neither per-hour nor conditional coverage.
- **Synthetic BESS LP Caveat:** The synthetic timing smoke in `audit/stage0_input_and_baseline_check.py` did not forbid simultaneous charge/discharge under negative prices and checked numerical solver status (`kOptimal`) rather than exact rational certification; any future storage comparator must explicitly exclude simultaneous charge/discharge, verify duration parameters, and distinguish solver tolerance from exact certification.
