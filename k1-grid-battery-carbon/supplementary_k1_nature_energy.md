# Supplementary Information: Counterfactual carbon accounting and congestion-constrained abatement limits of U.S. utility-scale battery storage

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
Email: zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

**Supplementary Box 1. Three-sample empirical architecture.**

| Empirical Sample | Geographic & Unit Scope | Time Window | Sample Size & Key Volume | Primary Analysis |
| :--- | :--- | :--- | :--- | :--- |
| **Sample 1: Operational Gas-Displacement Panel** | $G = 49$ balanced U.S. BAs (43 thermal; $d_{19} \ge 100$ MW) | `2019-01` to `2026-10` (94 months) | 3,359,080 hrs; 4,589 BA-months; 139,497 BA-days | Demand-weighted WLS conditional diurnal gas displacement, 6m leads, duration horse-race, daily `BA x YM FE` (Supp. Tables 2–3; Supp. Figs. 2–3) |
| **Sample 2: EPA CEMS Carbon-Accounting Panel (Core)** | 14 two-way metered BESS BAs (13 clean AC + `FPL*` DC) | `2024-07-01` to `2026-09-30` (exact same-window subset `2024-07..2025-12`) | 49.77 TWh full (26.05 TWh same-window); 52,816.8 GWh telemetry | 24h CEMS MEFs (24x24 $V$), AEF vs. CEMS-MEF discrepancy (+7.44 Mt), 14-BA joint 14d bootstrap, independent MEF checks, ERCOT cross-regional check (Main Figs. 1, 2, 4; Tables 1–2; Supp. Table 4) |
| **Sample 3: CAISO Curtailment Subsample** | Single-grid `CISO` (`fuelsource.csv` + official curtailments + CEMS) | `2024-07-01` to `2025-12-31` | 13,170 matched hours (549 days); 4,347.2 GWh curtailed | Interior curtailment MEFs (main & observed $\Delta\text{Load}$), 1d/7d/14d contiguous block bootstraps, congestion-constrained saturation frontier (Main Figs. 3–4; Table 2B) |

---

<!-- FIGURE:fig2_telemetry_forensics_and_diurnal_charging.png -->

**Supplementary Table 1. Physical telemetry audit and exact 4-window diurnal charging mix across all 14 metered U.S. grids (July 2024–October 2026).**

| BA | Telemetry Source | EIA-860M MW | Discharged (GWh) | Charged (GWh) | Physical RTE | Overnight (23-06) | Morning (07-09) | Midday (10-16) | Evening (17-22) | Midday Solar/Dem |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **CISO** | CAISO fuelsource | 17,265.5 | 30,576.5 | 35,419.2 | 0.863 | 3.5% | 10.9% | 83.1% | 2.5% | 51.5% |
| **ERCO** | EIA-930 (+UES) | 19,609.9 | 10,748.1 | 13,817.4 | 0.778 | 24.0% | 9.0% | 63.2% | 3.8% | 34.5% |
| **AZPS** | EIA-930 (+UES) | 3,269.8 | 4,698.3 | 5,371.2 | 0.875 | 0.9% | 18.3% | 79.8% | 1.1% | 36.6% |
| **PNM** | EIA-930 clean | 1,068.2 | 1,852.5 | 2,090.8 | 0.886 | 1.3% | 19.0% | 78.7% | 1.0% | 82.5% |
| **SRP** | EIA-930 clean | 1,668.0 | 1,080.6 | 1,224.9 | 0.882 | 10.0% | 28.2% | 60.5% | 1.2% | 19.1% |
| **PGE** | EIA-930 clean | 493.0 | 959.1 | 1,115.0 | 0.860 | 32.4% | 12.7% | 49.6% | 5.4% | 0.0% |
| **MISO** | EIA-930 clean | 1,175.9 | 781.1 | 977.8 | 0.799 | 56.7% | 6.9% | 31.8% | 4.6% | 13.3% |
| **IPCO** | EIA-930 clean | 659.0 | 673.4 | 776.2 | 0.868 | 25.5% | 20.2% | 51.8% | 2.4% | 23.7% |
| **TEPC** | EIA-930 clean | 570.0 | 613.7 | 717.6 | 0.855 | 2.3% | 24.2% | 73.3% | 0.2% | 22.1% |
| **IID** | EIA-930 clean | 215.0 | 349.7 | 405.1 | 0.863 | 5.8% | 17.4% | 71.1% | 5.7% | 93.4% |
| **SOCO** | EIA-930 clean | 923.7 | 257.6 | 303.2 | 0.850 | 56.4% | 14.7% | 25.3% | 3.6% | 12.6% |
| **DUK** | EIA-930 clean | 53.5 | 82.4 | 102.4 | 0.805 | 50.6% | 11.2% | 29.4% | 8.8% | 4.9% |
| **CPLE** | EIA-930 clean | 259.6 | 29.2 | 35.9 | 0.812 | 14.3% | 31.0% | 50.0% | 4.7% | 23.1% |
| **FPL*** | EIA-930 clean | 1,014.5 | 114.8 | 121.0 | 0.949 | 9.9% | 5.3% | 76.5% | 8.3% | 26.2% |
| **13 Clean AC Total** | **Reconciled** | **—** | **52,702.0** | **62,356.6** | **0.845** | — | — | — | — | — |

---

<!-- FIGURE:fig1_diurnal_gas_displacement_and_leads.png -->

**Supplementary Table 2. Nationwide 49-BA conditional diurnal gas-peaker displacement robustness (Sample 1, demand-weighted WLS, 2019–2026).**

| Specification / Sample (Outcome: Evening 17-22 minus Midday 10-16 / $d_{19}$) | $\hat{\beta}$ | SE (CR1) | $t_{\text{CR1}}$ | $t_{\text{2-way}}$ | $p_{\text{CR1}}$ | $p_{\text{Rad}}$ | $p_{\text{Webb6}}$ | $p_{\text{RI}}$ | $G$ | $N$ |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| **WLS All 49 BAs — Main NG (`BA + YM FE`, Aligned CISO)** | -0.3352 | 0.0570 | -5.88 | -5.84 | <0.0001 | 0.004 | 0.002 | 0.0010 | 49 | 4,589 |
| **WLS All 49 — No Controls Baseline (FE Only)** | -0.0579 | 0.0997 | -0.58 | -0.59 | 0.564 | 0.576 | 0.606 | — | 49 | 4,599 |
| WLS All 49 — NG (`BA x CalMo + YM FE`) | -0.3277 | 0.0594 | -5.52 | -5.54 | <0.0001 | 0.005 | 0.002 | — | 49 | 4,589 |
| WLS All 49 — Collider-Free NG (Drop `em_solar`) | -0.4046 | 0.0395 | -10.25 | -10.09 | <0.0001 | 0.001 | 0.001 | — | 49 | 4,589 |
| WLS All 49 — NG (`BA + Region x YM FE`) | -0.2226 | 0.0534 | -4.16 | -4.13 | 0.0001 | 0.001 | 0.001 | — | 49 | 4,589 |
| WLS All 49 — NG (+ BA Linear Trends) | -0.3621 | 0.0703 | -5.15 | -5.06 | <0.0001 | 0.001 | 0.001 | — | 49 | 4,589 |
| **WLS All 49 — Dispatchable Fossil + Net Imports** | -0.5632 | 0.0703 | -8.01 | -8.09 | <0.0001 | 0.001 | 0.001 | 0.0010 | 49 | 4,589 |
| WLS Drop CISO Only — NG (`G = 48`) | -0.3052 | 0.0904 | -3.37 | -3.39 | 0.001 | 0.017 | 0.014 | — | 48 | 4,495 |
| **WLS Drop CISO & ERCO — NG (`G = 47`)** | -0.3810 | 0.0606 | -6.29 | -6.29 | <0.0001 | 0.002 | 0.004 | 0.0010 | 47 | 4,401 |
| WLS Drop CISO & ERCO — Fossil + Net Imports | -0.6319 | 0.1068 | -5.91 | -6.02 | <0.0001 | 0.001 | 0.001 | — | 47 | 4,401 |
| WLS Drop Top-7 BESS BAs — NG (`G = 42`) | -0.3166 | 0.0845 | -3.75 | -3.65 | 0.0006 | 0.002 | 0.002 | — | 42 | 3,931 |
| WLS Drop Top-5 OLS-Leverage BAs — NG (`G = 44`) | -0.2851 | 0.1025 | -2.78 | -2.79 | 0.008 | 0.032 | 0.042 | — | 44 | 4,119 |
| WLS All 49 — Schema Seam (`BA x Post2024H2 FE`) | -0.3231 | 0.0565 | -5.72 | -5.42 | <0.0001 | 0.001 | 0.002 | — | 49 | 4,589 |
| WLS Drop CISO & ERCO (`BA x Post2024H2 FE`) | -0.2623 | 0.0700 | -3.75 | -3.70 | 0.0005 | 0.011 | 0.007 | — | 47 | 4,401 |
| WLS Uniform Pre-Schema (`2019-01..2024-06`) | -0.2550 | 0.0448 | -5.70 | -4.47 | <0.0001 | 0.029 | 0.023 | — | 49 | 3,224 |
| WLS Uniform Post-Schema (`2024-07..2026-10`) | -0.3631 | 0.0951 | -3.82 | -3.90 | 0.0004 | 0.001 | 0.005 | — | 49 | 1,365 |
| Audit: Unaligned EIA-930 CISO NG | -0.4487 | 0.0706 | -6.36 | -6.25 | <0.0001 | 0.014 | 0.010 | — | 49 | 4,589 |
| Audit: Equal-Weighted OLS All 49 (DOPD Leverage) | -0.2392 | 0.0733 | -3.26 | -3.25 | 0.002 | 0.002 | 0.004 | — | 49 | 4,589 |
| WLS All 49 — **Physical Placebo: Nuclear** | -0.0005 | 0.0004 | -1.16 | -1.14 | 0.252 | 0.291 | 0.319 | 0.088 | 49 | 4,589 |

*Notes:* 49-BA LOBAO spans [-0.3651, -0.2923] ($\max p_{\text{CR1}} = 0.0015$). Peak 24h response occurs at Hour Ending 20 (-0.2912, $t = -8.95$).

<!-- FIGURE:fig5_hourly_dispatch_and_master_audit.png -->

**Supplementary Table 3. Distributed 6-month timing tests, daily solar-swing dispatch (BA x Year-Month FE), and storage duration horse-race (Sample 1).**

| Panel / Test Variable | Sample | $\hat{\beta}$ | SE (CR1) | $t_{\text{CR1}}$ | $p_{\text{CR1}}$ | $p_{\text{WCB}}$ | $N$ |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Panel A: `Stock(t-12)` (Installed $\ge 12$m) | All 49 WLS | -0.3148 | 0.0691 | -4.55 | <0.0001 | 0.078 | 3,413 |
| Panel A: `Add(t-12..t-6)` (Commissioned 6-12m ago) | All 49 WLS | -0.3990 | 0.0879 | -4.54 | <0.0001 | 0.018 | 3,413 |
| Panel A: `Add(t-6..t)` (Commissioned 0-6m ago) | All 49 WLS | -0.3321 | 0.1111 | -2.99 | 0.004 | 0.128 | 3,413 |
| Panel A: `FUT(t..t+6)` (Unbuilt 0-6m Future Lead) | All 49 WLS | -0.0287 | 0.0761 | -0.38 | 0.707 | 0.712 | 3,413 |
| Panel A: `FUT(t+6..t+12)` (Unbuilt 6-12m Future Lead) | All 49 WLS | +0.0114 | 0.0769 | +0.15 | 0.883 | 0.932 | 3,413 |
| Panel B: Daily Midday Solar x `BESS_MWh` -> NG | All 49 (`BAxYM+Date FE`) | -0.1204 | 0.0335 | -3.60 | 0.0008 | 0.075 | 139,497 |
| Panel B: Daily Solar x `BESS_MWh` (+Quad & SolCap) | All 49 (`BAxYM+Date FE`) | -0.1088 | 0.0545 | -2.00 | 0.052 | 0.130 | 139,497 |
| Panel B: Daily Midday Solar x `BESS_MWh` -> NG | Drop CE (`BAxYM+Date FE`) | -0.1252 | 0.0451 | -2.78 | 0.008 | 0.155 | 133,776 |
| Panel B: Daily Solar x `BESS_MWh` -> Fossil+Imp | All 49 (`BAxYM+Date FE`) | -0.1567 | 0.0370 | -4.23 | 0.0001 | 0.030 | 139,497 |
| Panel B: Daily Solar x `BESS_MWh` -> Nuclear Placebo | All 49 (`BAxYM+Date FE`) | +0.0002 | 0.0003 | +0.93 | 0.355 | 0.445 | 139,497 |
| Panel C: Duration Horse-Race — Energy (`BESS_MWh`) | All 49 Ev-Mid NG | -0.0973 | 0.0221 | -4.39 | <0.0001 | 0.037 | 4,589 |
| Panel C: Duration Horse-Race — Cond. Power (`BESS_MW`) | All 49 Ev-Mid NG | -0.0188 | 0.1149 | -0.16 | 0.871 | 0.929 | 4,589 |
| Panel C: Duration Horse-Race — Energy (`BESS_MWh`) | Drop CE Peak HE19-20 | -0.1121 | 0.0262 | -4.28 | <0.0001 | 0.026 | 4,401 |
| Panel C: Duration Horse-Race — Cond. Power (`BESS_MW`) | Drop CE Peak HE19-20 | -0.0233 | 0.1281 | -0.18 | 0.856 | 0.897 | 4,401 |

*Notes:* Joint future lead Wald tests: All 49 $F = 0.082$ ($p = 0.921$; `BA x CalMo`: $F = 0.037$, $p = 0.964$); Drop CISO & ERCO $F = 1.509$ ($p = 0.232$). Several sub-component wild bootstrap $p$-values sit between 0.075 and 0.130, reinforcing Sample 1's role as supportive operational context.

---

**Supplementary Table 4. Independent BA-level MEF validations (EPA eGRID 2023 rev2 Non-Baseload CO2 rates, pure CEMS stack slopes, and direct metered battery-dispatch CEMS regressions).**

| BA | Disch. (GWh) | Main 24h CEMS MEF | Pure CEMS Stack Slope (SE) | EPA eGRID 2023 Non-Baseload | eGRID NB Loss Floor (kg/MWh) | Direct $-\partial\text{CO}_2/\partial\text{BESS}$ (SE) |
| :--- | ---: | ---: | :---: | ---: | ---: | :---: |
| **CISO** | 29,156.0 | 261.9 | 376.2 (1.4) | 398.5 | +63.0 | 271.3 (4.2) |
| **ERCO** | 9,923.9 | 502.8 | 515.9 (1.9) | 565.4 | +163.9 | 499.3 (3.4) |
| **AZPS** | 4,391.8 | 342.1 | 597.0 (7.9) | 692.4 | +96.5 | 222.3 (22.5) |
| **PNM** | 1,734.7 | 301.3 | 491.8 (6.6) | 491.7 | +63.5 | — |
| **SRP** | 996.5 | 294.0 | 390.4 (2.1) | 502.8 | +67.1 | — |
| **PGE** | 906.6 | 5.2 | 325.3 (2.8) | 502.2 | +81.7 | — |
| **MISO** | 722.9 | 547.6 | 635.9 (2.2) | 699.1 | +177.5 | 618.6 (84.4) |
| **IPCO** | 640.2 | 425.9 | 480.6 (4.8) | 471.7 | +71.7 | — |
| **TEPC** | 554.4 | 337.8 | 648.8 (4.9) | 876.5 | +150.3 | — |
| **IID** | 333.1 | 255.1 | 394.4 (3.6) | 421.3 | +67.2 | — |
| **SOCO** | 204.0 | 514.9 | 584.6 (3.1) | 636.1 | +120.0 | — |
| **DUK** | 73.3 | 234.2 | 538.7 (2.5) | 598.4 | +143.0 | — |
| **CPLE** | 26.1 | 452.4 | 553.7 (6.4) | 548.8 | +120.3 | — |
| **FPL** | 107.8 | 341.8 | 355.3 (1.5) | 378.4 | +14.7 | — |

*Notes:* Official EPA eGRID 2023 rev2 BA Non-Baseload CO2 rates require zero EIA-930 regressions and imply a pure round-trip-loss fleet floor of **+89.6 kg/MWh (+4.46 Mt CO2)**. Pure CEMS stack slopes regress $\Delta\text{CO}_{2,\text{CEMS}}$ solely on $\Delta\text{GrossLoad}_{\text{CEMS}}$. Direct battery regressions regress hourly CEMS $\Delta\text{CO}_2$ on metered $\Delta\text{BESS}_{\text{MW}}$ controlling for $\Delta\text{Load}$, $\Delta\text{Solar}$, $\Delta\text{Wind}$, $\Delta\text{Imports}$, and `YM x Hour FE`.
