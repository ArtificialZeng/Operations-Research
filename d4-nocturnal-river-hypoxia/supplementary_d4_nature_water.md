# Supplementary Information: Equal-budget monitoring protocols for nocturnal river hypoxia across U.S. and English networks

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Supplementary Note 1. Network Coverage and Common-Support Attrition Audit

Station-level UTC record lengths, modal native sampling cadences, candidate warm-season nights, complete astronomical nights, and common-support matched nights for all 139 U.S. Geological Survey (USGS) and 65 Environment Agency (EA) stations are archived in `tables/table_s1_station_coverage_attrition.csv`. Table S2 summarizes attrition stratified by native sampling cadence and calendar month.

**Table S2. Warm-season site-night coverage and attrition by network, native sampling interval, and month.**

| Network | Stratum type | Stratum | Sites | Candidate nights | Matched nights | Entry rate | Night-gap fail | Target-match fail |
|---|---|---|---:|---:|---:|---:|---:|---:|
| United States (USGS) | Overall | All warm-season | 139 | 93,538 | 87,785 | 93.85% | 4,523 | 1,230 |
| United States (USGS) | Cadence | 5 min | 4 | 2,918 | 2,416 | 82.80% | 483 | 19 |
| United States (USGS) | Cadence | 15 min | 115 | 76,923 | 72,781 | 94.62% | 3,164 | 978 |
| United States (USGS) | Cadence | 30 min | 12 | 8,286 | 7,500 | 90.51% | 648 | 138 |
| United States (USGS) | Cadence | 60 min | 8 | 5,411 | 5,088 | 94.03% | 228 | 95 |
| United States (USGS) | Month | May | 139 | 15,510 | 14,658 | 94.51% | 661 | 191 |
| United States (USGS) | Month | June | 139 | 15,311 | 14,323 | 93.55% | 781 | 207 |
| United States (USGS) | Month | July | 139 | 15,721 | 14,787 | 94.06% | 755 | 179 |
| United States (USGS) | Month | August | 139 | 15,812 | 14,836 | 93.83% | 717 | 259 |
| United States (USGS) | Month | September | 139 | 15,414 | 14,473 | 93.90% | 750 | 191 |
| United States (USGS) | Month | October | 139 | 15,770 | 14,708 | 93.27% | 859 | 203 |
| England (EA) | Overall | All warm-season | 65 | 33,612 | 27,635 | 82.22% | 5,824 | 153 |
| England (EA) | Cadence | 15 min | 7 | 3,870 | 3,058 | 79.02% | 780 | 32 |
| England (EA) | Cadence | 30 min | 28 | 13,902 | 9,318 | 67.03% | 4,537 | 47 |
| England (EA) | Cadence | 60 min | 30 | 15,840 | 15,259 | 96.33% | 507 | 74 |
| England (EA) | Month | May | 65 | 5,466 | 4,426 | 80.97% | 1,015 | 25 |
| England (EA) | Month | June | 65 | 5,403 | 4,490 | 83.10% | 891 | 22 |
| England (EA) | Month | July | 65 | 5,726 | 4,771 | 83.32% | 936 | 19 |
| England (EA) | Month | August | 65 | 5,754 | 4,783 | 83.12% | 942 | 29 |
| England (EA) | Month | September | 65 | 5,585 | 4,561 | 81.67% | 1,001 | 23 |
| England (EA) | Month | October | 65 | 5,678 | 4,604 | 81.08% | 1,039 | 35 |

---

## Supplementary Note 2. Boundary Censoring, Kaplan–Meier Duration Bounds, and Cadence Downsampling

Because most nocturnal low-oxygen runs persist past geometric sunrise, summarizing duration exclusively on runs closed at both ends inside darkness introduces severe downward selection bias. Table S3 compares naive closed-in-night median bounds, Kaplan–Meier restricted 12-h mean nocturnal survival times (treating sunrise-truncated episodes as right-censored), and full unbroken continuous-series episode medians across all four thresholds (<5, <4, <3, and <2 mg L$^{-1}$).

**Table S3. Nocturnal boundary censoring composition and censoring-adjusted episode duration across thresholds.**

| Network | Threshold (mg L$^{-1}$) | Hypoxic nights | Both closed (%) | Left-only | Right-only | Doubly cens. | Naive closed med. (h) | KM night RMST-12h (h) | Full continuous med. (IQR, h) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| United States (USGS) | <5 | 8,499 | 1,246 (14.7%) | 447 | 3,412 | 3,394 | 1.00–1.75 | 8.83 | 13.5 (6.5–40.0) |
| United States (USGS) | <4 | 4,439 | 699 (15.7%) | 309 | 2,001 | 1,430 | 1.00–1.50 | 9.06 | 13.0 (6.2–25.0) |
| United States (USGS) | <3 | 2,465 | 445 (18.1%) | 189 | 1,247 | 584 | 0.75–1.25 | 9.00 | 10.0 (5.2–16.5) |
| United States (USGS) | <2 | 810 | 255 (31.5%) | 75 | 237 | 243 | 1.00–1.50 | 5.81 | 8.2 (2.2–18.8) |
| England (EA) | <5 | 2,472 | 378 (15.3%) | 199 | 868 | 1,027 | 1.00–2.00 | 7.91 | 13.0 (6.0–67.0) |
| England (EA) | <4 | 1,465 | 234 (16.0%) | 139 | 426 | 666 | 1.00–2.50 | 7.53 | 14.5 (6.0–88.4) |
| England (EA) | <3 | 912 | 143 (15.7%) | 84 | 268 | 417 | 1.00–2.50 | 7.67 | 14.0 (6.0–93.7) |
| England (EA) | <2 | 572 | 86 (15.0%) | 46 | 188 | 252 | 1.00–2.50 | 7.97 | 12.5 (6.0–69.2) |

---

## Supplementary Note 3. Complete Equal-Budget Cost-Sensitivity Grid

Table S4 expands Main Text Table 3 across annual visit budgets of 12 (monthly), 24 (biweekly), and 52 (weekly) daytime-visit-equivalents site$^{-1}$ yr$^{-1}$, nocturnal visit cost multipliers ($m_{\text{night}} \in \{1.00\times, 1.75\times, 2.50\times\}$), and amortized continuous sonde annual costs ($K_{\text{sonde}} \in \{20, 40, 60, 100\}$ daytime-visit-equivalents yr$^{-1}$). The full 162-row grid (including $m_{\text{night}} = 1.35\times$) is archived in `tables/table_s4_cost_sensitivity_grid.csv`.

**Table S4. Equal-budget distinct actionable episode yield, unit cost, and impaired site-year discovery across budget and cost regimes.**

| Network | Annual budget (day-eq) | Protocol | Cost parameter | Distinct ep. / 100 eq | Cost / distinct ep. | Impaired site-yrs flagged |
|---|---:|---|---|---:|---:|---:|
| U.S. | 12 | Empirical WQP agency clock | $m_{\text{night}} = 1.00×$ | 2.25 | \$8,897 | 34.5% |
| U.S. | 12 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.00×$ | 2.28 | \$8,781 | 37.2% |
| U.S. | 12 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.00×$ | 3.31 | \$6,042 | 47.0% |
| U.S. | 12 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.00×$ | 3.33 | \$6,013 | 47.2% |
| U.S. | 12 | Empirical WQP agency clock | $m_{\text{night}} = 1.75×$ | 2.22 | \$9,023 | 34.1% |
| U.S. | 12 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.75×$ | 1.92 | \$10,398 | 34.3% |
| U.S. | 12 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.75×$ | 3.01 | \$6,647 | 45.2% |
| U.S. | 12 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.75×$ | 2.07 | \$9,659 | 38.9% |
| U.S. | 12 | Empirical WQP agency clock | $m_{\text{night}} = 2.50×$ | 2.20 | \$9,106 | 34.0% |
| U.S. | 12 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 2.50×$ | 1.54 | \$12,950 | 29.4% |
| U.S. | 12 | First-light daylight (SR+30m) | $m_{\text{night}} = 2.50×$ | 2.67 | \$7,492 | 43.3% |
| U.S. | 12 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 2.50×$ | 1.50 | \$13,370 | 32.4% |
| U.S. | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 8.92 | \$2,241 | 36.0% |
| U.S. | 12 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 12.09 | \$1,655 | 48.6% |
| U.S. | 12 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 20$ | 12.60 | \$1,587 | 57.4% |
| U.S. | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 8.78 | \$2,278 | 33.9% |
| U.S. | 12 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 11.81 | \$1,693 | 44.0% |
| U.S. | 12 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 40$ | 12.10 | \$1,653 | 50.7% |
| U.S. | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 8.62 | \$2,320 | 31.1% |
| U.S. | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 8.29 | \$2,413 | 23.6% |
| U.S. | 24 | Empirical WQP agency clock | $m_{\text{night}} = 1.00×$ | 1.93 | \$10,357 | 43.2% |
| U.S. | 24 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.00×$ | 2.02 | \$9,918 | 48.0% |
| U.S. | 24 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.00×$ | 2.82 | \$7,081 | 57.2% |
| U.S. | 24 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.00×$ | 2.85 | \$7,023 | 57.9% |
| U.S. | 24 | Empirical WQP agency clock | $m_{\text{night}} = 1.75×$ | 1.91 | \$10,460 | 43.0% |
| U.S. | 24 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.75×$ | 1.74 | \$11,518 | 45.4% |
| U.S. | 24 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.75×$ | 2.56 | \$7,813 | 55.2% |
| U.S. | 24 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.75×$ | 1.85 | \$10,793 | 49.2% |
| U.S. | 24 | Empirical WQP agency clock | $m_{\text{night}} = 2.50×$ | 1.89 | \$10,569 | 42.6% |
| U.S. | 24 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 2.50×$ | 1.51 | \$13,249 | 42.5% |
| U.S. | 24 | First-light daylight (SR+30m) | $m_{\text{night}} = 2.50×$ | 2.34 | \$8,542 | 53.4% |
| U.S. | 24 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 2.50×$ | 1.39 | \$14,440 | 44.1% |
| U.S. | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 4.83 | \$4,139 | 44.5% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 6.35 | \$3,148 | 55.2% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 20$ | 6.89 | \$2,904 | 65.9% |
| U.S. | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 4.77 | \$4,189 | 43.3% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 6.27 | \$3,190 | 53.8% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 40$ | 6.71 | \$2,980 | 63.8% |
| U.S. | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 4.74 | \$4,219 | 42.8% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 6.14 | \$3,256 | 51.0% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 60$ | 6.51 | \$3,073 | 60.8% |
| U.S. | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 4.61 | \$4,343 | 39.7% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 5.90 | \$3,388 | 43.8% |
| U.S. | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 100$ | 6.04 | \$3,310 | 50.5% |
| U.S. | 52 | Empirical WQP agency clock | $m_{\text{night}} = 1.00×$ | 1.47 | \$13,608 | 54.2% |
| U.S. | 52 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.00×$ | 1.55 | \$12,864 | 59.4% |
| U.S. | 52 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.00×$ | 2.13 | \$9,412 | 69.2% |
| U.S. | 52 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.00×$ | 2.14 | \$9,353 | 69.7% |
| U.S. | 52 | Empirical WQP agency clock | $m_{\text{night}} = 1.75×$ | 1.45 | \$13,814 | 53.6% |
| U.S. | 52 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.75×$ | 1.39 | \$14,410 | 57.1% |
| U.S. | 52 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.75×$ | 1.95 | \$10,235 | 67.1% |
| U.S. | 52 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.75×$ | 1.52 | \$13,128 | 61.2% |
| U.S. | 52 | Empirical WQP agency clock | $m_{\text{night}} = 2.50×$ | 1.42 | \$14,042 | 52.8% |
| U.S. | 52 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 2.50×$ | 1.17 | \$17,030 | 52.5% |
| U.S. | 52 | First-light daylight (SR+30m) | $m_{\text{night}} = 2.50×$ | 1.84 | \$10,884 | 65.2% |
| U.S. | 52 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 2.50×$ | 1.18 | \$16,922 | 55.6% |
| U.S. | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 2.55 | \$7,838 | 55.9% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 3.16 | \$6,329 | 62.8% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 20$ | 3.57 | \$5,596 | 75.2% |
| U.S. | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 2.53 | \$7,902 | 55.3% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 3.15 | \$6,358 | 62.4% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 40$ | 3.56 | \$5,621 | 74.8% |
| U.S. | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 2.50 | \$7,997 | 54.2% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 3.13 | \$6,398 | 61.9% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 60$ | 3.50 | \$5,715 | 73.5% |
| U.S. | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 2.46 | \$8,116 | 52.8% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 3.06 | \$6,538 | 59.8% |
| U.S. | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 100$ | 3.38 | \$5,925 | 70.7% |
| England | 12 | Empirical WQP agency clock | $m_{\text{night}} = 1.00×$ | 1.67 | \$11,971 | 32.5% |
| England | 12 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.00×$ | 1.72 | \$11,631 | 33.6% |
| England | 12 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.00×$ | 2.54 | \$7,860 | 42.2% |
| England | 12 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.00×$ | 2.66 | \$7,531 | 43.3% |
| England | 12 | Empirical WQP agency clock | $m_{\text{night}} = 1.75×$ | 1.67 | \$11,994 | 32.6% |
| England | 12 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.75×$ | 1.52 | \$13,143 | 30.7% |
| England | 12 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.75×$ | 2.36 | \$8,476 | 41.7% |
| England | 12 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.75×$ | 1.68 | \$11,933 | 33.1% |
| England | 12 | Empirical WQP agency clock | $m_{\text{night}} = 2.50×$ | 1.65 | \$12,105 | 32.4% |
| England | 12 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 2.50×$ | 1.22 | \$16,357 | 24.8% |
| England | 12 | First-light daylight (SR+30m) | $m_{\text{night}} = 2.50×$ | 2.10 | \$9,525 | 38.4% |
| England | 12 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 2.50×$ | 1.18 | \$16,970 | 25.8% |
| England | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 7.90 | \$2,530 | 36.5% |
| England | 12 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 13.00 | \$1,538 | 45.6% |
| England | 12 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 20$ | 13.47 | \$1,485 | 53.3% |
| England | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 7.72 | \$2,592 | 33.1% |
| England | 12 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 12.73 | \$1,571 | 39.8% |
| England | 12 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 40$ | 12.98 | \$1,540 | 45.2% |
| England | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 7.50 | \$2,666 | 28.9% |
| England | 12 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 12.46 | \$1,605 | 33.3% |
| England | 12 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 60$ | 12.46 | \$1,605 | 33.3% |
| England | 12 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 7.06 | \$2,833 | 18.3% |
| England | 24 | Empirical WQP agency clock | $m_{\text{night}} = 1.00×$ | 1.51 | \$13,239 | 47.1% |
| England | 24 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.00×$ | 1.59 | \$12,543 | 49.3% |
| England | 24 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.00×$ | 2.29 | \$8,747 | 56.2% |
| England | 24 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.00×$ | 2.36 | \$8,463 | 56.6% |
| England | 24 | Empirical WQP agency clock | $m_{\text{night}} = 1.75×$ | 1.51 | \$13,256 | 47.2% |
| England | 24 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.75×$ | 1.35 | \$14,835 | 45.5% |
| England | 24 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.75×$ | 2.06 | \$9,729 | 54.2% |
| England | 24 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.75×$ | 1.51 | \$13,264 | 46.2% |
| England | 24 | Empirical WQP agency clock | $m_{\text{night}} = 2.50×$ | 1.49 | \$13,410 | 47.2% |
| England | 24 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 2.50×$ | 1.13 | \$17,740 | 39.9% |
| England | 24 | First-light daylight (SR+30m) | $m_{\text{night}} = 2.50×$ | 1.90 | \$10,536 | 52.4% |
| England | 24 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 2.50×$ | 1.10 | \$18,100 | 39.2% |
| England | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 4.44 | \$4,503 | 50.5% |
| England | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 6.85 | \$2,919 | 57.5% |
| England | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 20$ | 7.27 | \$2,752 | 63.0% |
| England | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 4.37 | \$4,577 | 49.0% |
| England | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 6.76 | \$2,959 | 54.5% |
| England | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 40$ | 7.11 | \$2,812 | 60.6% |
| England | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 4.26 | \$4,691 | 46.1% |
| England | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 6.62 | \$3,019 | 50.5% |
| England | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 60$ | 6.92 | \$2,891 | 57.1% |
| England | 24 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 4.09 | \$4,895 | 40.7% |
| England | 24 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 6.36 | \$3,143 | 39.8% |
| England | 24 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 100$ | 6.49 | \$3,082 | 45.0% |
| England | 52 | Empirical WQP agency clock | $m_{\text{night}} = 1.00×$ | 1.25 | \$15,979 | 63.1% |
| England | 52 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.00×$ | 1.36 | \$14,687 | 65.5% |
| England | 52 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.00×$ | 1.87 | \$10,703 | 69.9% |
| England | 52 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.00×$ | 1.93 | \$10,345 | 70.8% |
| England | 52 | Empirical WQP agency clock | $m_{\text{night}} = 1.75×$ | 1.25 | \$15,992 | 63.1% |
| England | 52 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 1.75×$ | 1.18 | \$16,939 | 61.2% |
| England | 52 | First-light daylight (SR+30m) | $m_{\text{night}} = 1.75×$ | 1.70 | \$11,772 | 68.2% |
| England | 52 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 1.75×$ | 1.29 | \$15,494 | 60.9% |
| England | 52 | Empirical WQP agency clock | $m_{\text{night}} = 2.50×$ | 1.24 | \$16,124 | 62.8% |
| England | 52 | Dawn-included rotating (1/3 pre-dawn) | $m_{\text{night}} = 2.50×$ | 1.01 | \$19,816 | 56.5% |
| England | 52 | First-light daylight (SR+30m) | $m_{\text{night}} = 2.50×$ | 1.55 | \$12,910 | 65.8% |
| England | 52 | Dark pre-dawn (SR−30m) | $m_{\text{night}} = 2.50×$ | 0.98 | \$20,477 | 54.7% |
| England | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 2.44 | \$8,202 | 65.7% |
| England | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 20$ | 3.42 | \$5,853 | 68.7% |
| England | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 20$ | 3.78 | \$5,293 | 73.9% |
| England | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 2.42 | \$8,251 | 64.9% |
| England | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 40$ | 3.40 | \$5,885 | 68.3% |
| England | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 40$ | 3.72 | \$5,380 | 72.4% |
| England | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 2.40 | \$8,350 | 63.8% |
| England | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 60$ | 3.36 | \$5,953 | 66.5% |
| England | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 60$ | 3.67 | \$5,446 | 71.3% |
| England | 52 | Hybrid: top-10% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 2.35 | \$8,522 | 62.6% |
| England | 52 | Hybrid: top-20% sondes (Y1) + WQP | $K_{\text{sonde}} = 100$ | 3.29 | \$6,081 | 63.7% |
| England | 52 | Hybrid: top-20% sondes (Y1) + first light | $K_{\text{sonde}} = 100$ | 3.56 | \$5,612 | 68.6% |

---

## Supplementary Note 4. Archived Daily-Extremes Thermal Decoupling, Compound Drought, and Secular Trend Context (2005–2025)

To provide hydrological and climatic context for warm-season risk stratification—kept strictly separate from the primary UTC nocturnal protocol evaluation in the Main Text—we archive our continental daily-extremes analysis across 397 screened free-flowing freshwater USGS stations (2005–2025; 1,446,764 station-days; 324 stations in the primary discharge-controlled Spec 2 absorbing within-station Year $\times$ Month fixed effects plus $\log Q$ and $(\log Q)^2$, geospatially audited against all 62,226 dams in the USACE National Inventory of Dams) and 65 English stations. These daily-extremes models measure observed short-term temperature sensitivity of full-day $DO_{\min}$ vs. $DO_{\max}$ (capturing coupled metabolic, reaeration, irradiance, and subdaily hydrologic co-variation rather than isolated nocturnal events):

- **Continental daily thermal decoupling (Spec 2, $N = 324$):** $d(DO_{\min} - DO_{\max})/dT = -0.0754\text{ mg L}^{-1}\text{ }^\circ\text{C}^{-1}$ (HUC-2 SE $0.0069$, $p = 7.70e-09$), strengthening to $-0.0795$ beyond 5 km of $\ge 500\text{ acre-ft}$ NID dams ($N = 242$) and $-0.0903$ beyond 5 km of any dam ($N = 141$), and replicating across 65 English stations ($-0.0947$, 1°-grid $p = 1.98e-04$).
- **Compound heatwave $\times$ low-flow drought ($N = 319$):** daily $DO_{\min}$ drops $-0.854\text{ mg L}^{-1}$ ($p = 2.19 \times 10^{-6}$) with a bounded daily-minimum minus daily-maximum $<5\text{ mg L}^{-1}$ probability contrast of $+9.28$ percentage points (95% CI $[+4.88, +13.68]$, $p = 3.83e-04$).

**Table S5. Archived continental daily-extremes thermal decoupling specifications (2005–2025; screened USGS network).**

| Specification | Outcome | $N$ sites | Mean (mg L$^{-1}$ °C$^{-1}$) | HUC-2 SE | HUC-2 $p$ |
|---|---|---:|---:|---:|---:|
| Spec 2 Primary (YM FE + log Q + (log Q)²) | Henry's Law $DO_{\text{sat,alt}}$ | 324 | -0.1855 | 0.0045 | 9.88e-18 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | Daily $DO_{\max}$ | 324 | -0.1566 | 0.0122 | 7.96e-10 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | Daily $DO_{\text{mean}}$ | 324 | -0.2020 | 0.0095 | 3.80e-13 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | Daily $DO_{\min}$ | 324 | -0.2319 | 0.0077 | 1.49e-15 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | $DO_{\min} - DO_{\max}$ | 324 | -0.0754 | 0.0069 | 7.70e-09 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | diff min mean | 324 | -0.0299 | 0.0029 | 1.79e-08 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | $DO_{\min} - DO_{\text{sat,alt}}$ | 324 | -0.0465 | 0.0049 | 6.34e-08 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | $DO_{\max} - DO_{\text{sat,alt}}$ | 324 | +0.0289 | 0.0093 | 6.98e-03 |
| Spec 2 Primary (YM FE + log Q + (log Q)²) | plunge | 324 | +0.0299 | 0.0029 | 1.79e-08 |
| Spec 1 All Clean Rivers (YM FE) | Daily $DO_{\min}$ | 397 | -0.2258 | 0.0118 | 1.82e-12 |
| Spec 1 All Clean Rivers (YM FE) | Daily $DO_{\max}$ | 397 | -0.1186 | 0.0150 | 6.23e-07 |
| Spec 1 All Clean Rivers (YM FE) | $DO_{\min} - DO_{\max}$ | 397 | -0.1072 | 0.0108 | 3.00e-08 |
| Spec 1 All Clean Rivers (YM FE) | $DO_{\min} - DO_{\text{sat,alt}}$ | 397 | -0.0404 | 0.0080 | 1.12e-04 |
| Spec 1 All Clean Rivers (YM FE) | $DO_{\max} - DO_{\text{sat,alt}}$ | 397 | +0.0668 | 0.0113 | 2.27e-05 |

<!-- FIGURE:fig1_conus_map_and_thermal_decoupling.png -->
<!-- FIGURE:fig3_compound_heatwave_drought.png -->
<!-- FIGURE:fig4_biophysical_mechanism.png -->
<!-- FIGURE:fig5_secular_cwa_and_uk_replication.png -->

---

## Supplementary Note 5. Reproducibility and Verification Checklist

1. **UTC & WQP Data Archiving:** `scripts/09_fetch_usgs_stac.py` (139 USGS STAC UTC Parquet files + source SHA-256 receipts), `scripts/04_uk_ea_international_replication.py` (65 English EA stations), `scripts/10_fetch_wqp_grab_logs.py` (10,019 warm-season WQP discrete field visits).
2. **Primary LORO, Sensitivity, Holdout, Cadence & Censoring Audit:** `scripts/11_loro_and_sensitivity_analysis.py` $\rightarrow$ `results/11_loro_and_sensitivity.json`, `data/processed/v4_nocturnal_site_nights.parquet`, `tables/table_s1_station_coverage_attrition.csv`.
3. **Equal-Budget Operational Protocol & Cost-Effectiveness Simulation:** `scripts/12_operational_protocol_decision_analysis.py` $\rightarrow$ `results/12_operational_protocol_decision.json`.
4. **Publication Figures & Zero-NaN Tables:** `scripts/13_generate_v4_figures_tables.py` $\rightarrow$ `figures/fig1_nw_*.png/.pdf` through `fig4_nw_*.png/.pdf`, `tables/table1_nw_*.csv` through `table_s4_*.csv`.
5. **Manuscript, Supplement, PDF Compilation & Integrity Manifest:** `scripts/14_generate_v4_manuscript_and_supplement.py`, `scripts/08_compile_manuscript_pdf.py`, `scripts/07_build_manifest.py` $\rightarrow$ `manuscript_d4_boost.pdf`, `manuscript_d4_nature_water.pdf`, `supplementary_d4_nature_water.pdf`, `SHA256SUMS.json`.
6. **Automated Verification:** `pytest -v tests/test_d4_pipeline.py` (unit tests, exact LORO parity, programmatic manuscript-vs-JSON parity, zero-NaN table checks, zero-leak PDF checks, Crossref DOI parity, SHA-256 verification) and `ruff check scripts tests` (0 lint errors).
