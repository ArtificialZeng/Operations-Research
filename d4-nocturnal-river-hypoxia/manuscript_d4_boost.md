# Equal-budget monitoring protocols for nocturnal river hypoxia across U.S. and English networks

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Abstract

Routine river water-quality monitoring occurs predominantly during daylight working hours, creating systematic blind spots for nocturnal dissolved-oxygen (DO) depletion. Yet moving field sampling before sunrise incurs safety and overtime costs and still may not deliver early warning before ecological stress peaks. Here we evaluate deployable, equal-budget monitoring protocols using raw UTC-timestamped continuous DO records from 139 U.S. Geological Survey stations (87,785 warm-season site-nights) and 65 Environment Agency stations in England (27,635 site-nights), anchored against 10,019 timestamped U.S. Water Quality Portal (WQP) discrete agency field visits. Removing shared-reading circularity via a primary leave-one-reading-out (LORO) estimator confirms substantial pre-dawn recall gains over 14:30 afternoon sampling at <5 mg L$^{-1}$ (+49.47 [+36.87, +62.07] percentage points in the U.S.; +35.13 [+22.69, +47.57] percentage points in England; LORO reference-negative alarm rates 0.047% and 0.443%), robust across ±0.2 mg L$^{-1}$ sensor tolerances, ≥2 h persistence, 15–60 min downsampling, chronic-site exclusions, and cross-Atlantic out-of-sample transfer. Crucially, real agency visits peak near 11:00 local time (09:50 solar), and under realistic nocturnal staffing surcharges (1.75×), dark pre-dawn grabs yield fewer distinct actionable episodes per dollar than existing daytime schedules (breakeven 1.53× U.S., 1.38× England). Instead, sampling at safe first-light daylight (sunrise + 30 min) maximizes grab-only efficiency, while reallocating the identical annual budget to risk-stratified continuous sondes at the top 20% of sites (selected out-of-sample from Year-1 daytime screening) plus first-light grabs elsewhere multiplies distinct episode detections 3.5×–4.7×, cuts unit costs by 72%–79%, flags 60.6%–63.8% of impaired site-years, and provides 3.5–4.5 h pre-nadir warning.

---

## Introduction

Dissolved oxygen governs the metabolic habitability and biogeochemical integrity of flowing freshwaters (Odum, 1956; Bernhardt et al., 2018; Battin et al., 2023). Because oxygen solubility declines with temperature (Benson and Krause, 1984) while aquatic ectotherm demand rises steeply during warm extremes (Pörtner, 2010), climate warming and hydroclimatic drought are intensifying river deoxygenation and hypoxia worldwide (van Vliet et al., 2023; Zhi et al., 2023; Graham et al., 2025), even where nutrient abatement has partially reversed chronic oxygen deficits (Zhou et al., 2026).

In biologically productive rivers, however, oxygen stress is strongly concentrated in astronomical darkness when daytime photosynthesis ceases and community respiration persists (Odum, 1956; Appling et al., 2018). Global syntheses of continuous sensor records establish that lotic hypoxia is frequently nocturnal and episodic (Blaszczak et al., 2023), and catchment-scale audits in six United Kingdom rivers show that measurement clock time and sampling frequency materially alter water-quality interpretation (Elfferich et al., 2024). Yet most regional and national water-quality networks still rely on discrete grab samples collected during daytime working hours because deploying continuous telemetered sondes across every stream reach is financially prohibitive.

Bridging the gap between observational bias and operational water management requires resolving three foundational issues that remain untested at multi-network scale. First, evaluating single-reading sampling times against a nocturnal minimum computed from the *same* probe creates mechanical circularity—forcing zero pre-dawn reference-negative alarms by construction—and requires leave-one-reading-out (LORO) verification, sensor-tolerance and persistence checks, independent field-meter benchmarking, and out-of-sample regional holdout validation. Second, nocturnal hypoxia durations measured strictly inside astronomical darkness are heavily censored at sunrise and sunset; uncorrected summaries can severely mischaracterize exposure duration and decision urgency. Third, higher per-visit recall does not automatically translate into superior operational monitoring: dark pre-dawn visits trigger overtime and two-person riparian safety costs, real-world agency crews rarely sample strictly at mid-afternoon, and pre-dawn grabs may still arrive too late to avert acute ecological damage before the oxygen nadir.

Here we transform cross-network timing audits into an equal-budget operational decision framework for water agencies. Combining raw UTC-timestamped continuous DO series across 139 screened free-flowing U.S. Geological Survey (USGS) rivers and 65 screened Environment Agency (EA) rivers in England with 10,019 actual timestamped U.S. Water Quality Portal (WQP) agency grab-sample logs, we (1) characterize real-world field sampling clocks, independent field-meter agreement, and common-support coverage attrition; (2) establish non-circular LORO nocturnal detection gains, cadence sensitivity, and cross-Atlantic transferability—uncovering a near-optimal, daylight-safe first-light sampling window; (3) resolve boundary censoring bias and episodic detection lead times; and (4) quantify equal-budget cost-effectiveness across fixed afternoon, empirical agency, rotating, first-light, dark pre-dawn, and risk-stratified continuous sonde protocols. Throughout, continuous-sensor detection metrics quantify within-probe recorded nocturnal events on monitored networks rather than statutory compliance rates.

---

## Results

### Real-world monitoring schedules, field-meter fidelity, and coverage

Empirical field logs contradict the common assumption that routine water-quality monitoring occurs predominantly in mid-afternoon. Across 10,019 timestamped warm-season (May–October, 2015–2024) discrete DO visits spanning 205 screened U.S. rivers in the Water Quality Portal, agency sampling peaks in late morning: median local civil clock time is 11:00 (interquartile range [IQR] 9.50–12.67 h), corresponding to 9.84 h local mean solar time (Fig. 1a). Nearly all visits (92.9%) occur between 08:00 and 17:00 local clock time (61.5% during 08:00–12:00 and 31.5% during 12:00–17:00), whereas only 0.51% (51 of 10,019) fall within the two hours preceding geometric sunrise. The matched 2021–2024 subdaily cohort exhibits an identical distribution (1,391 visits across 76 of our 139 stations; median local clock 11.08 h, 91.6% within 08:00–17:00).

Co-located field measurements confirm that the continuous USGS sondes closely track independent calibrated field meters while demonstrating nocturnal miss rates on real agency visit days. Pairing discrete WQP readings collected within 30 min of a continuous UTC sonde timestamp (median offset 0.0 min) yields 1,287 co-located observations across 76 stations with Pearson $r = 0.961$, mean sonde-minus-meter bias of $-0.027\text{ mg L}^{-1}$, mean absolute error of $0.28\text{ mg L}^{-1}$, and median absolute error of $0.20\text{ mg L}^{-1}$—matching the $\pm 0.20\text{ mg L}^{-1}$ USGS continuous-monitor accuracy criterion (Wagner et al., 2006; Fig. 1b). Across 1,112 actual agency visit dates matched with complete continuous nocturnal records, 82 nights exhibited LORO nocturnal hypoxia (<5 mg L$^{-1}$) and 71 involved persistent ≥2 h episodes. Real field visits detected only 32/82 (39.0%; missing 61.0%) of LORO hypoxic nights and 30/71 (42.3%) of ≥2 h actionable episodes, compared with 84.1% and 93.0% detection by pre-dawn sonde readings on those exact same visit dates (Fig. 1b inset).

Transparent coverage auditing explains trans-Atlantic differences in common-support sample retention (Fig. 1c; Supplementary Tables S1–S2). Out of 93,538 warm-season candidate site-nights across 139 U.S. stations, 89,015 (95.2%) met nocturnal continuity limits (all internal and boundary gaps $\le 1.5\times$ native cadence) and 87,785 (93.8%) entered common-support evaluation (failing primarily due to nocturnal gaps [4,523] rather than daytime target matching [1,230]). Across 65 English stations, 27,635 of 33,612 candidate nights (82.2%) entered common support. Attrition stratifies sharply by native cadence rather than season (monthly entry rates vary by <2.3 percentage points across May–October in both networks): U.S. stations are predominantly 15-min (115 sites, 94.6% entry), whereas England comprises 7 stations at 15-min (79.0% entry), 28 at 30-min (67.0% entry, accounting for 4,537 of 5,824 English nocturnal gap exclusions), and 30 at 60-min (96.3% entry). Partial-data excluded nights show modestly higher <5 mg L$^{-1}$ prevalence than matched nights in the U.S. (11.89% vs. 9.68%) and lower prevalence in England (3.69% vs. 8.95%), indicating no uniform directional omission bias.

<!-- FIGURE:fig1_nw_monitoring_clock_and_coverage.png -->

### Cross-network LORO validation and the first-light window

Eliminating shared reference-outcome circularity preserves large nocturnal detection gains across both national networks while exposing non-zero pre-dawn reference-negative alarm rates (Fig. 2a; Table 1). Under our primary LORO estimator—which excludes the candidate pre-dawn reading when classifying the astronomical night—reference-positive <5 mg L$^{-1}$ nights decline by 37 of 8,499 in the U.S. (to 8,462) and by 112 of 2,472 in England (to 2,360). Moving a single daily reading from 14:30 local mean solar time to 30 min before geometric sunrise increases LORO recall from 33.90% to 83.37% in the U.S. (paired gain +49.47 [+36.87, +62.07] percentage points, clustered by 17 HUC-2 basins) and from 44.79% to 79.92% in England (paired gain +35.13 [+22.69, +47.57] percentage points, clustered by 19 1° hydrometric grids). Against the 10:30 solar overpass window, LORO pre-dawn gains are +33.29 [+22.17, +44.41] percentage points (U.S.) and +25.72 [+15.19, +36.25] percentage points (England). Transparently removing the shared-reading guarantee yields LORO pre-dawn reference-negative alarm rates of 0.047% in the U.S. (37 single-reading dips across 79,323 reference-negative nights) and 0.443% in England (112 across 25,275 nights)—still lower than daytime reference-negative rates at 14:30 (0.198% U.S., 0.514% England) and 10:30 (0.271% U.S., 1.207% England). Comparable LORO gains persist across stricter chronic and acute thresholds: <4 mg L$^{-1}$ (+48.04 U.S., +32.74 England), <3 mg L$^{-1}$ (+51.71, +35.71), and <2 mg L$^{-1}$ (+36.46, +43.09 percentage points; Table 1).

**Table 1. Primary leave-one-reading-out (LORO) nocturnal hypoxia detection across U.S. and English networks.**

| Network | Threshold (mg L$^{-1}$) | LORO ref. pos. (Δ vs. shared) | Schedule | LORO recall, % [95% CI] | Ref.-neg. alarm, % | Paired gain vs. 14:30, pp [95% CI] |
|---|---:|---:|---|---:|---:|---:|
| U.S. (USGS) | <5 | 8,462 (−37) | 14:30 afternoon | 33.90 [23.06, 44.75] | 0.198 | — |
| U.S. (USGS) | <5 | 8,462 (−37) | 10:30 overpass | 50.08 [37.75, 62.42] | 0.271 | — |
| U.S. (USGS) | <5 | 8,462 (−37) | 08:00 morning | 69.61 [57.53, 81.69] | 0.372 | — |
| U.S. (USGS) | <5 | 8,462 (−37) | 50/50 alternating | 58.48 [52.84, 64.13] | 0.125 | — |
| U.S. (USGS) | <5 | 8,462 (−37) | Pre-dawn (SR−30m) | 83.37 [77.96, 88.79] | 0.047 | +49.47 [+36.87, +62.07] |
| U.S. (USGS) | <4 | 4,409 (−30) | 14:30 afternoon | 32.82 [14.72, 50.92] | 0.150 | — |
| U.S. (USGS) | <4 | 4,409 (−30) | 10:30 overpass | 44.11 [24.29, 63.94] | 0.209 | — |
| U.S. (USGS) | <4 | 4,409 (−30) | 08:00 morning | 72.11 [58.90, 85.31] | 0.255 | — |
| U.S. (USGS) | <4 | 4,409 (−30) | 50/50 alternating | 57.07 [50.54, 63.59] | 0.095 | — |
| U.S. (USGS) | <4 | 4,409 (−30) | Pre-dawn (SR−30m) | 80.86 [72.53, 89.19] | 0.036 | +48.04 [+23.04, +73.04] |
| U.S. (USGS) | <3 | 2,454 (−11) | 14:30 afternoon | 26.65 [3.06, 50.24] | 0.082 | — |
| U.S. (USGS) | <3 | 2,454 (−11) | 10:30 overpass | 31.21 [4.67, 57.75] | 0.123 | — |
| U.S. (USGS) | <3 | 2,454 (−11) | 08:00 morning | 51.45 [38.67, 64.23] | 0.116 | — |
| U.S. (USGS) | <3 | 2,454 (−11) | 50/50 alternating | 52.12 [45.89, 58.35] | 0.067 | — |
| U.S. (USGS) | <3 | 2,454 (−11) | Pre-dawn (SR−30m) | 78.36 [63.82, 92.90] | 0.013 | +51.71 [+14.46, +88.96] |
| U.S. (USGS) | <2 | 809 (−1) | 14:30 afternoon | 29.54 [11.18, 47.91] | 0.048 | — |
| U.S. (USGS) | <2 | 809 (−1) | 10:30 overpass | 35.72 [15.03, 56.42] | 0.038 | — |
| U.S. (USGS) | <2 | 809 (−1) | 08:00 morning | 45.08 [26.80, 63.36] | 0.028 | — |
| U.S. (USGS) | <2 | 809 (−1) | 50/50 alternating | 47.96 [39.11, 56.81] | 0.020 | — |
| U.S. (USGS) | <2 | 809 (−1) | Pre-dawn (SR−30m) | 66.01 [60.74, 71.28] | 0.001 | +36.46 [+15.86, +57.07] |
| England (EA) | <5 | 2,360 (−112) | 14:30 afternoon | 44.79 [29.06, 60.51] | 0.514 | — |
| England (EA) | <5 | 2,360 (−112) | 10:30 overpass | 54.19 [40.39, 68.00] | 1.207 | — |
| England (EA) | <5 | 2,360 (−112) | 08:00 morning | 67.42 [55.41, 79.42] | 1.783 | — |
| England (EA) | <5 | 2,360 (−112) | 50/50 alternating | 62.50 [51.29, 73.71] | 0.471 | — |
| England (EA) | <5 | 2,360 (−112) | Pre-dawn (SR−30m) | 79.92 [71.46, 88.37] | 0.443 | +35.13 [+22.69, +47.57] |
| England (EA) | <4 | 1,408 (−57) | 14:30 afternoon | 44.53 [27.80, 61.26] | 0.275 | — |
| England (EA) | <4 | 1,408 (−57) | 10:30 overpass | 55.82 [36.08, 75.57] | 0.503 | — |
| England (EA) | <4 | 1,408 (−57) | 08:00 morning | 66.05 [48.84, 83.27] | 0.756 | — |
| England (EA) | <4 | 1,408 (−57) | 50/50 alternating | 60.37 [46.15, 74.59] | 0.259 | — |
| England (EA) | <4 | 1,408 (−57) | Pre-dawn (SR−30m) | 77.27 [64.18, 90.37] | 0.217 | +32.74 [+25.17, +40.31] |
| England (EA) | <3 | 885 (−27) | 14:30 afternoon | 42.71 [22.83, 62.60] | 0.179 | — |
| England (EA) | <3 | 885 (−27) | 10:30 overpass | 55.37 [37.48, 73.25] | 0.269 | — |
| England (EA) | <3 | 885 (−27) | 08:00 morning | 68.59 [46.87, 90.30] | 0.318 | — |
| England (EA) | <3 | 885 (−27) | 50/50 alternating | 61.02 [41.64, 80.39] | 0.164 | — |
| England (EA) | <3 | 885 (−27) | Pre-dawn (SR−30m) | 78.42 [60.76, 96.07] | 0.101 | +35.71 [+26.31, +45.10] |
| England (EA) | <2 | 557 (−15) | 14:30 afternoon | 36.98 [22.31, 51.66] | 0.107 | — |
| England (EA) | <2 | 557 (−15) | 10:30 overpass | 46.86 [32.94, 60.77] | 0.089 | — |
| England (EA) | <2 | 557 (−15) | 08:00 morning | 65.89 [48.97, 82.80] | 0.078 | — |
| England (EA) | <2 | 557 (−15) | 50/50 alternating | 57.63 [41.97, 73.29] | 0.048 | — |
| England (EA) | <2 | 557 (−15) | Pre-dawn (SR−30m) | 80.07 [59.83, 100.32] | 0.055 | +43.09 [+25.55, +60.63] |

*Notes:* Evaluated on identical common-support site-nights (87,785 U.S. across 139 stations; 27,635 England across 65 stations). LORO removes the candidate pre-dawn reading when determining nocturnal reference hypoxia; Δ denotes nights reclassified from positive to negative relative to shared-reading evaluation. Confidence intervals use CR1 cluster-robust standard errors with finite-sample $t(G-1)$ critical values clustered by HUC-2 basin (U.S.) or 1° grid cell (England). Source: `results/11_loro_and_sensitivity.json` and `tables/table1_nw_loro_cross_network.csv`.

Every anti-circularity, measurement-error, cadence, site-weighting, and holdout test confirms the stability of the nocturnal gain while revealing two practical insights (Fig. 2b,c; Table 2). First, excluding an entire ±30 min window around pre-dawn leaves gains virtually unchanged (+49.63 U.S., +34.77 England percentage points). Requiring persistence of ≥2 consecutive non-candidate readings or ≥2 h continuous hypoxia increases the pre-dawn advantage to +51.54–+53.58 percentage points in the U.S. and +34.98–+38.09 percentage points in England. Applying ±0.2 mg L$^{-1}$ deterministic threshold buffers or adding independent Gaussian instrument noise ($\sigma = 0.20\text{ mg L}^{-1}$, 200 Monte Carlo replications simulating two independent co-located probes) retains gains of +46.55 (U.S.) and +33.29 (England) percentage points.

Second, systematically downsampling all 119 high-frequency U.S. stations (≤15 min native cadence) onto exact 15-, 30-, and 60-min UTC grids explains England's higher LORO alarm rate as a pure sampling-interval effect: coarsening cadence from 15 to 60 min leaves LORO recall gain steady (+50.88 → +51.97 → +51.80 percentage points) while mechanically raising pre-dawn reference-negative alarms sixteen-fold from 0.023% to 0.368%—closely matching England's predominantly 30–60 min network (0.227% on England's ≤30-min cohort downsampled to 60 min; 0.361% on England's 15-min cohort). Equal-site weighting across stations with ≥5 hypoxic nights yields +46.26 (U.S., 79 sites) and +30.47 (England, 30 sites) percentage points, and excluding chronically hypoxic stations (>50% of nights <5 mg L$^{-1}$, or >25% of 14:30 readings <5 mg L$^{-1}$) *strengthens* the timing gain to +57.04–+63.73 (U.S.) and +37.83–+40.18 (England) percentage points, confirming that episodic rivers drive the scheduling benefit.

Crucially, scanning offsets from 180 min before to 120 min after geometric sunrise reveals an operationally vital **first-light daylight plateau** (Fig. 2b). Out-of-sample Youden-$J$ optimization independently selects geometric sunrise (`SR + 0 min`) in 16/16 U.S. Leave-One-HUC2-Basin-Out folds, 5/5 U.S. site folds, 11/15 English 1°-grid folds (4 selecting `SR − 30 min`), and both directions of zero-shot cross-Atlantic transfer (out-of-sample LORO gains +50.56 U.S. and +36.03 England percentage points; Table 2). Because nocturnal respiration and hypoxic water-mass advection briefly lag geometric dawn before photosynthetic irradiance reaches the compensation point, LORO recall peaks at geometric sunrise (84.46% U.S., 80.02% England) and remains virtually unchanged 30 min *after* sunrise in safe civil daylight (`SR + 30 min`: 83.85% U.S., 78.80% England; LORO reference-negative alarms 0.205% and 0.541%).

<!-- FIGURE:fig2_nw_loro_cross_network_validation.png -->

**Table 2. Anti-circularity, sensor tolerance, persistence, cadence downsampling, site-weighting, and out-of-sample holdout audit (<5 mg L$^{-1}$).**

| Sensitivity or validation test | U.S. $n$ | U.S. gain vs. 14:30, pp [95% CI] | U.S. ref.-neg. alarm, % | England $n$ | England gain vs. 14:30, pp [95% CI] | England ref.-neg. alarm, % |
|---|---:|---:|---:|---:|---:|---:|
| Shared reference (v3 baseline) | 8,499 | +49.66 [+37.14, +62.19] | 0.000 | 2,472 | +37.38 [+24.30, +50.46] | 0.000 |
| Primary LORO (drop candidate) | 8,462 | +49.47 [+36.87, +62.07] | 0.047 | 2,360 | +35.13 [+22.69, +47.57] | 0.443 |
| Strict LORO (±30 min buffer) | 8,124 | +49.63 [+36.62, +62.64] | 0.277 | 2,324 | +34.77 [+22.19, +47.35] | 0.533 |
| Persistence ≥2 consecutive readings | 8,031 | +51.54 [+38.72, +64.36] | 0.152 | 2,124 | +34.98 [+21.85, +48.11] | 0.886 |
| Actionable ≥2 h continuous | 7,633 | +53.58 [+40.52, +66.65] | 0.250 | 2,132 | +38.09 [+24.23, +51.94] | 0.561 |
| Tolerance buffer: ref <4.8 mg L$^{-1}$ | 7,403 | +51.94 [+37.95, +65.93] | 0.577 | 2,132 | +34.43 [+21.65, +47.21] | 0.914 |
| Tolerance buffer: ref <5.2 mg L$^{-1}$ | 9,689 | +43.05 [+31.73, +54.37] | 0.006 | 2,608 | +33.47 [+22.10, +44.84] | 0.208 |
| Indep. MC probe noise (σ = 0.10) | 8,462 | +48.50 [+48.12, +48.90] | 0.207 | 2,360 | +34.55 [+33.85, +35.18] | 0.528 |
| Indep. MC probe noise (σ = 0.20) | 8,462 | +46.55 [+45.96, +47.13] | 0.480 | 2,360 | +33.29 [+32.44, +34.15] | 0.684 |
| Downsampled 15-min grid | 6,834 | +50.88 [+35.44, +66.32] | 0.023 | 433 | +41.11 [-13.30, +95.52] | 0.038 |
| Downsampled 30-min grid | 6,708 | +51.97 [+36.74, +67.20] | 0.123 | 425 | +41.41 [-12.89, +95.71] | 0.035 |
| Downsampled 60-min grid | 6,419 | +51.80 [+35.28, +68.32] | 0.368 | 404 | +43.56 [-9.49, +96.62] | 0.361 |
| Equal-site weight (≥5 hyp. nights) | 79 | +46.26 [+39.10, +53.43] | 0.047 | 30 | +30.47 [+18.76, +42.18] | 0.443 |
| Excl. chronic sites (>50% nights) | 4,411 | +57.04 [+50.32, +63.76] | 0.047 | 1,816 | +37.83 [+23.61, +52.06] | 0.443 |
| Excl. daytime-chronic (>25% 14:30) | 5,821 | +63.73 [+54.63, +72.84] | 0.047 | 1,593 | +40.18 [+24.98, +55.37] | 0.443 |
| OOS Leave-One-Region-Out holdout | 8,448 | +50.56 [+38.08, +63.03] | 0.119 | 2,395 | +35.24 [+22.70, +47.78] | 0.515 |
| OOS 5-fold site holdout | 8,448 | +50.56 [+38.08, +63.03] | 0.119 | 2,389 | +35.24 [+22.83, +47.66] | 0.519 |
| Cross-Atlantic zero-shot transfer | 8,448 | +50.56 [+38.08, +63.03] | 0.119 | 2,412 | +36.03 [+23.64, +48.41] | 0.512 |

*Notes:* $n$ denotes reference-positive site-nights (or stations for equal-site weighting). Independent probe-noise Monte Carlo adds independent $\mathcal{N}(0, \sigma^2)$ noise to candidate and reference readings across 200 replications (2.5th–97.5th percentiles shown). Downsampling evaluates native ≤15-min stations (119 U.S., 7 England; England's 35-site ≤30-min cohort yields +30.54 and +29.54 pp at 30 and 60 min). Source: `results/11_loro_and_sensitivity.json` and `tables/table2_nw_robustness_holdout_cadence.csv`.

### Boundary censoring, duration bias, and episodic lead time

Evaluating hypoxia duration strictly within astronomical darkness introduces severe right- and double-censoring that distorts risk characterization unless corrected (Fig. 3a,b; Supplementary Table S3). Among all 8,499 U.S. and 2,472 English <5 mg L$^{-1}$ site-nights, only 1,246 (14.7%) and 378 (15.3%), respectively, have both run boundaries closed inside darkness. In contrast, 80.1% of U.S. hypoxic nights (3,412 right-censored at sunrise plus 3,394 doubly censored across the entire night) and 76.7% of English nights (868 right-censored plus 1,027 doubly censored) remain hypoxic past geometric sunrise. Restricting duration summaries to closed-in-night runs therefore selects solely for brief transient dips, compressing median apparent duration to 1.00–1.75 h (U.S.) and 1.00–2.00 h (England). Applying Kaplan–Meier right-censored survival estimation (Kaplan and Meier, 1958) to episodes with observed nocturnal onset shows that 71.3% (U.S.) and 61.3% (England) persist beyond 6 h (restricted 12-h mean 8.83 h U.S. and 7.91 h England; England KM median 9.75 h, U.S. KM survival never falls below 50% before sunrise). Tracing unbroken continuous runs across sunrise and sunset closes 86.6% (U.S.) and 89.5% (England) of all episodes, revealing true median continuous durations of 13.5 h (IQR 6.5–40.0 h) in the U.S. and 13.0 h (IQR 6.0–67.0 h) in England (Fig. 3b).

Explicitly separating episodic single-night actionable events (2–24 h continuous <5 mg L$^{-1}$; 5,257 U.S. and 1,257 English site-nights) from multi-day chronic hypoxia (2,376 U.S. and 875 English site-nights) clarifies why even pre-dawn grab sampling is an active-event surveillance tool rather than true early warning (Fig. 3c). On episodic 2–24 h events, 14:30 afternoon grabs miss 87.8% (U.S.) and 80.4% (England) and, when they do register low DO, arrive a median of 3.38–5.00 h *after* recovery (11.0–12.0 h post-nadir). Pre-dawn (`SR − 30 min`) and first-light (`SR + 30 min`) grabs catch 86.0%–87.0% (U.S.) and 76.7%–78.9% (England) while hypoxia remains active (+3.87 to +4.75 h remaining before recovery), yet they arrive right near or slightly after the oxygen nadir (-1.18 to -0.25 h U.S.; -0.39 to +0.50 h England). By contrast, telemetered continuous sondes triggering alerts 30 min after onset detect 100% of episodic events a median of +4.5 h (U.S.) and +3.5 h (England) *before* the oxygen nadir (94.2%–95.8% caught pre-nadir; +10.5 and +8.5 h before recovery).

<!-- FIGURE:fig3_nw_censoring_duration_and_leadtime.png -->

### Equal-budget operational protocol and cost-effectiveness frontier

Translating per-visit detection into deployable agency decisions under fixed annual budgets overturns simple pre-dawn grab recommendations (Fig. 4; Table 3; Supplementary Table S4). Evaluated strictly out-of-sample on post-Year-1 warm seasons (393 U.S. site-years with 1,066 distinct non-overlapping ≥2 h <5 mg L$^{-1}$ episodes; 109 English site-years with 348 distinct episodes) across 1,000 stratified calendar schedules, we count **distinct non-overlapping episodes** alongside actionable site-nights and impaired site-years flagged to prevent multi-day chronic events from inflating continuous-sonde counts.

Before staffing surcharges, shifting from the empirical WQP clock to pre-dawn adds +2.66 (U.S.) and +1.83 (England) actionable detections per 100 visits (+4.66 and +2.94 relative to 14:30 afternoon). Once realistic nocturnal field-safety and overtime multipliers ($m_{\text{night}} = 1.75\times$, representing two-person dark-terrain crews and night-shift differentials) constrain an identical annual budget (baseline 24 daytime-visit-equivalents site$^{-1}$ yr$^{-1}$, or \$4,800 site$^{-1}$ yr$^{-1}$ at \$200 daytime visit$^{-1}$), however, three decisive operational findings emerge:

1. **Dark pre-dawn grabs lose cost-effectiveness above modest overtime surcharges.** Analytical breakeven multipliers where pure dark pre-dawn equals the empirical WQP agency clock are only $m^* = 1.53\times$ in the U.S. and $m^* = 1.38\times$ in England (vs. 2.46× and 1.78× against 14:30 afternoon). At $m_{\text{night}} = 1.75\times$, the 43% reduction in affordable annual visits leaves dark pre-dawn yielding 1.85 distinct episodes per 100 budget-equivalents (\$10,793 episode$^{-1}$) in the U.S. and 1.51 (\$13,264 episode$^{-1}$) in England—no better than, or worse than, the existing empirical WQP clock (1.91 U.S., 1.51 England; Table 3).
2. **First-light civil daylight grabs (`SR + 30 min`) dominate all grab-only alternatives.** Because early daylight eliminates two-person dark-terrain safety crews while retaining near-peak recall (89.8% U.S., 85.3% England on ≥2 h episodes), first-light grabs (modeled with a modest 1.15× early-shift factor) deliver 2.56 (U.S.) and 2.06 (England) distinct episodes per 100 budget-equivalents, lowering cost to \$7,813 and \$9,729 per episode while flagging 55.2% (U.S.) and 54.2% (England) of impaired site-years—beating both dark pre-dawn and rotating daytime schedules (Fig. 4a,b).
3. **Risk-stratified continuous sondes plus first-light grabs dominate the entire decision frontier.** Because hypoxic episodes are strongly concentrated across rivers, allocating amortized continuous sondes ($K_{\text{sonde}} = 40$ daytime-visit-equivalents yr$^{-1}$, or \$8,000 sonde$^{-1}$ yr$^{-1}$ covering hardware amortization, telemetry, and routine biofouling calibration visits) to the top 20% highest-risk stations—ranked strictly out-of-sample using only Year-1 daytime grab observations—captures 51.2% (U.S.) and 46.8% (England) of all subsequent distinct episodes while leaving sufficient budget for 17.4 annual first-light visits at every remaining station. Under the exact same total dollar budget, this hybrid protocol yields 6.71 (U.S.) and 7.11 (England) distinct episodes per 100 budget-equivalents (3.5× and 4.7× empirical WQP grabs; 14.5× and 12.8× on actionable site-nights), reduces cost per distinct episode by 72%–79% to \$2,980 (U.S.) and \$2,812 (England), and raises network-wide site-year discovery to 63.8% (U.S.) and 60.6% (England) (Fig. 4b). Even with zero prior DO records—ranking sites strictly out-of-sample from static geographic/basin covariates—top-20% sonde hybrids achieve 5.07 (U.S.) and 4.49 (England) distinct episodes per 100 budget-equivalents. Across the full cost-ratio phase surface, top-20% hybrids dominate up to $K_{\text{sonde}} = 120$ visit-equivalents yr$^{-1}$ (\$24,000 sonde$^{-1}$ yr$^{-1}$), top-10% hybrids dominate up to $K_{\text{sonde}} = 240$, and first-light grabs win only where continuous instrumentation is infeasible or prohibitively costly (Fig. 4c; consistent across 12 and 52 annual visit budgets and <4 mg L$^{-1}$ / <3 mg L$^{-1}$ thresholds in Supplementary Table S4).

<!-- FIGURE:fig4_nw_equal_budget_protocol_frontier.png -->

**Table 3. Equal-budget operational protocol comparison for persistent actionable hypoxia (≥2 h continuous <5 mg L$^{-1}$, LORO).**

| Network | Monitoring protocol (budget = 24 day-eq site$^{-1}$ yr$^{-1}$) | Actionable / 100 visits | Distinct ep. / 100 eq | Cost / distinct ep. | Impaired site-yrs flagged | Episodic lead: nadir / end (h) | LORO ref.-neg. alarm |
|---|---|---:|---:|---:|---:|---:|---:|
| U.S. | 14:30 afternoon grab | 3.19 | 1.23 | \$16,212 | 29.7% | -11.00 / -3.38 | 0.198% |
| U.S. | Empirical WQP agency clock | 5.19 | 1.91 | \$10,460 | 43.0% | -3.75 / +2.00 | 0.276% |
| U.S. | Daytime-safe rotating (07/10:30/14:30) | 5.01 | 1.90 | \$10,541 | 43.7% | -3.50 / +2.00 | 0.271% |
| U.S. | Dawn-included rotating (1/3 pre-dawn) | 5.24 | 1.74 | \$11,518 | 45.4% | -2.25 / +3.25 | 0.172% |
| U.S. | 50/50 alternating (pre-dawn/14:30) | 5.52 | 1.68 | \$11,912 | 46.5% | -0.75 / +4.25 | 0.122% |
| U.S. | First-light daylight (SR+30m, 1.15×) | 7.80 | 2.56 | \$7,813 | 55.2% | -1.18 / +3.87 | 0.205% |
| U.S. | Dark pre-dawn (SR−30m, 1.75×) | 7.85 | 1.85 | \$10,793 | 49.2% | -0.25 / +4.75 | 0.047% |
| U.S. | Hybrid: top-10% sondes (Y1) + WQP | — (cont.) | 4.77 | \$4,189 | 43.3% | +4.50 / +10.50 | 0.137% |
| U.S. | Hybrid: top-20% sondes (Y1) + WQP | — (cont.) | 6.27 | \$3,190 | 53.8% | +4.50 / +10.50 | 0.112% |
| U.S. | Hybrid: top-20% sondes (Y1) + first light | — (cont.) | 6.71 | \$2,980 | 63.8% | +4.50 / +10.50 | 0.163% |
| U.S. | Hybrid: top-20% sondes (covar.) + WQP | — (cont.) | 5.07 | \$3,947 | 56.4% | +4.50 / +10.50 | 0.226% |
| U.S. | Hybrid: top-20% sondes (oracle) + WQP | — (cont.) | 7.90 | \$2,532 | 51.2% | +4.50 / +10.50 | 0.118% |
| England | 14:30 afternoon grab | 3.77 | 1.03 | \$19,407 | 36.8% | -12.00 / -5.00 | 0.514% |
| England | Empirical WQP agency clock | 4.88 | 1.51 | \$13,256 | 47.2% | -4.00 / +2.00 | 1.121% |
| England | Daytime-safe rotating (07/10:30/14:30) | 4.76 | 1.46 | \$13,713 | 46.6% | -4.00 / +2.00 | 1.027% |
| England | Dawn-included rotating (1/3 pre-dawn) | 5.00 | 1.35 | \$14,835 | 45.5% | -3.00 / +3.00 | 0.721% |
| England | 50/50 alternating (pre-dawn/14:30) | 5.24 | 1.38 | \$14,524 | 45.4% | -1.00 / +4.00 | 0.479% |
| England | First-light daylight (SR+30m, 1.15×) | 6.58 | 2.06 | \$9,729 | 54.2% | -0.39 / +3.92 | 0.538% |
| England | Dark pre-dawn (SR−30m, 1.75×) | 6.71 | 1.51 | \$13,264 | 46.2% | +0.50 / +5.00 | 0.443% |
| England | Hybrid: top-10% sondes (Y1) + WQP | — (cont.) | 4.37 | \$4,577 | 49.0% | +3.50 / +8.50 | 1.368% |
| England | Hybrid: top-20% sondes (Y1) + WQP | — (cont.) | 6.76 | \$2,959 | 54.5% | +3.50 / +8.50 | 0.358% |
| England | Hybrid: top-20% sondes (Y1) + first light | — (cont.) | 7.11 | \$2,812 | 60.6% | +3.50 / +8.50 | 0.317% |
| England | Hybrid: top-20% sondes (covar.) + WQP | — (cont.) | 4.49 | \$4,453 | 56.9% | +3.50 / +8.50 | 0.452% |
| England | Hybrid: top-20% sondes (oracle) + WQP | — (cont.) | 10.59 | \$1,889 | 59.4% | +3.50 / +8.50 | 0.345% |

*Notes:* Evaluated strictly out-of-sample on post-Year-1 warm seasons (393 U.S. site-years, 173 impaired; 109 English site-years, 51 impaired) across 1,000 stratified warm-season calendars at central costs ($m_{\text{night}} = 1.75\times$, early-shift first-light $1.15\times$, $K_{\text{sonde}} = 40$ daytime-visit-equivalents yr$^{-1}$, benchmark \$200 daytime visit$^{-1}$). Distinct episodes group consecutive hypoxic site-nights at the same station to avoid double-counting multi-day events. Source: `results/12_operational_protocol_decision.json` and `tables/table3_nw_equal_budget_protocols.csv`.

---

## Discussion

Our cross-network analysis demonstrates that turning nocturnal hypoxia awareness into better water management requires moving beyond fixed-time recall comparisons to explicit budget, safety, and lead-time trade-offs. Although LORO validation confirms that shifting a single sample from mid-afternoon to before sunrise raises within-probe <5 mg L$^{-1}$ detection by ~35–50 percentage points on both sides of the Atlantic, real-world agency logistics reshape the operational optimum in three concrete ways.

First, **agencies constrained to grab sampling should adopt early-morning first-light scheduling (`sunrise` to `sunrise + 30 min`) rather than pitch-dark pre-dawn shifts or uniform afternoon schedules.** Because field visits already peak around 11:00 local time—not 14:30—and nocturnal safety rules typically raise pre-dawn visit costs above the 1.38×–1.53× breakeven threshold, mandating pre-dawn dark visits across an entire network reduces detections per dollar. Shifting routine crews by 3–4 hours into early civil daylight captures nearly identical nocturnal recall (85%–90% of persistent ≥2 h episodes) without night-shift safety surcharges, while increasing impaired-site discovery over both empirical WQP clocks and dark pre-dawn schedules. Where operational logistics prohibit early shifts on every visit, rotating even one-third of visits into early daylight provides an immediate no-overtime improvement over fixed afternoon monitoring.

Second, **agencies with capital flexibility should transition from uniform grab networks to risk-stratified hybrid networks.** Deploying continuous telemetered sondes to just 10%–20% of highest-risk reaches—identifiable strictly out-of-sample from a single prior warm season of routine daytime grab data (or even static basin covariates)—and applying first-light grabs across the remaining 80%–90% of reaches multiplies distinct episode detections 3.5×–4.7× under the *same* annual budget, cuts per-episode cost by >70%, expands impaired-site discovery across the entire network, and unlocks the only operational pathway to true pre-nadir early warning (3.5–4.5 h before minimum DO) needed for reservoir aeration releases, wastewater discharge throttling, or aquaculture advisories.

Third, **transparent censoring accounting is essential when translating sensor logs into ecological risk.** Over three-quarters of nocturnal <5 mg L$^{-1}$ runs extend past geometric sunrise; naively summarizing only runs closed inside darkness understates median continuous exposure duration by roughly an order of magnitude (1–2 h vs. 13.0–13.5 h). Future monitoring syntheses should report Kaplan–Meier censored bounds or cross-boundary continuous episode durations alongside native-cadence attrition audits.

Several scope boundaries warrant explicit note. Both the USGS and EA cohorts represent screened continuous monitoring networks rather than unweighted random samples of all streams, and continuous-sensor outcomes quantify within-probe recorded nocturnal events rather than statutory regulatory compliance. Although 1,287 co-located WQP field-meter readings verify probe fidelity ($r = 0.961$, MedAE 0.20 mg L$^{-1}$), prospective field trials using dual co-located continuous probes and UK-specific grab-sampling timestamp archives (currently unavailable via the migrated EA Water Quality API) remain important next steps. Similarly, attributing long-term hypoxic trends to climate versus nutrient management requires coupled hydrodynamic, nutrient, and irradiance datasets (Graham et al., 2025; Zhou et al., 2026); supplementary daily-extremes thermal decoupling and drought-interaction analyses across 397 U.S. stations (2005–2025) are archived in the Supplementary Information to contextualize warm-season risk stratification.

---

## Methods

### Data sources and UTC timestamp reconstruction

We assembled continuous UTC-timestamped dissolved-oxygen records from two independent national networks screened to exclude dams, tailraces, lock pools, lakes, canals, tidal/estuarine waters, and brackish sites (>5,000 $\mu\text{S cm}^{-1}$; full exclusion log in `data/processed/excluded_sites_audit.csv`). For the U.S., we archived native UTC continuous Parquet files from USGS Water Data STAC (`parameter_code == "00300"`, `approval_status == "Approved"`, $0 \le \text{DO} \le 25\text{ mg L}^{-1}$, May–October 2021–2024) for all 139 multi-year subdaily stations spanning 17 HUC-2 basins, selecting the longest-coverage `time_series_id` per station and collapsing duplicate timestamps by median. For England, we used the 65 screened, 2-km-deduplicated free-flowing Environment Agency Hydrology API stations (May–October 2012–2025, 19 1° $\times$ 1° hydrometric grid clusters). To quantify real-world field visit timing and independent probe fidelity, we retrieved all warm-season discrete field DO measurements (`pCode=00300`) from the U.S. Water Quality Portal for our 139 subdaily stations (2021–2024; 1,391 visits across 76 sites) and our broader 397-station screened CONUS inventory (2015–2024; 10,019 visits across 205 sites), converting local timestamps and USGS timezone codes to UTC and local mean solar time (LMST).

### Astronomical darkness and common-support screening

Every UTC timestamp was converted to continuous LMST minutes via $t_{\text{solar}} = (t_{\text{UTC}} - t_{\text{epoch}})/60 + 4\lambda$, where $\lambda$ is station longitude (degrees east). Geometric sunrise and sunset were calculated for each solar date from station latitude and day-of-year using the 3-harmonic Spencer–Iqbal declination and equation-of-time series (Iqbal, 1983). Each station's modal native sampling step $\Delta t$ (5–60 min) was identified from consecutive observation intervals; a warm-season astronomical night (previous sunset to current sunrise) was deemed complete if all internal and boundary gaps were $\le 1.5\Delta t$. Common-support site-nights additionally required valid readings within $0.55\Delta t$ of each core target (`14:30`, `10:30`, and `sunrise − 30 min`), with the pre-dawn reading strictly inside darkness.

### Primary LORO estimator, sensitivity battery, and holdout validation

To eliminate shared reference-outcome circularity, our primary LORO estimator removes the candidate pre-dawn reading from the astronomical night array before testing whether any remaining nocturnal reading falls below threshold $\tau \in \{5, 4, 3, 2\}\text{ mg L}^{-1}$, reporting both LORO recall and LORO reference-negative alarm rate for every schedule. Sensitivity analyses evaluate: (i) excluding an entire $\pm 30\text{ min}$ window around pre-dawn; (ii) requiring persistence of $\ge 2$ consecutive non-candidate sub-threshold readings or $\ge 2\text{ h}$ continuous hypoxia; (iii) deterministic $\pm 0.1$ and $\pm 0.2\text{ mg L}^{-1}$ reference buffers plus 200-replication independent Gaussian probe noise ($\sigma = 0.10, 0.20\text{ mg L}^{-1}$); (iv) exact downsampling of native $\le 15$-min stations onto 15-, 30-, and 60-min UTC grids; (v) equal-site weighting ($\ge 5$ hypoxic nights) and exclusion of chronically hypoxic sites; and (vi) out-of-sample optimal solar-offset selection (maximizing LORO Youden's $J$ over offsets from `SR − 180` to `SR + 120` min plus fixed solar hours) evaluated via Leave-One-Region-Out (17 HUC-2 basins / 19 1° grids), 5-fold disjoint site holdout, and zero-shot cross-Atlantic transfer. All confidence intervals use CR1 cluster-robust standard errors with finite-sample $t(G-1)$ critical values (Cameron and Miller, 2015).

### Censoring classification and Kaplan–Meier survival estimation

Longest nocturnal low-DO runs were classified as both-closed, left-censored (at sunset), right-censored (at sunrise), or doubly censored. For runs initiating inside darkness, Kaplan–Meier right-censored survival curves (Kaplan and Meier, 1958) treated sunrise-truncated episodes as right-censored rather than omitting them. Unbroken continuous runs were additionally traced across sunset and sunrise in the full multi-day UTC record (halting at recovery $\ge \tau$ or gaps $>1.5\Delta t$) to measure full episode duration, onset, nadir, and recovery timing relative to sunrise.

### Equal-budget operational simulation and cost model

We pre-defined actionable episodes as LORO-verified continuous $<5\text{ mg L}^{-1}$ runs lasting $\ge 2.0\text{ h}$ (with $<4\text{ mg L}^{-1}$, $<3\text{ mg L}^{-1}$, and $\ge 4.0\text{ h}$ sensitivities) and grouped consecutive actionable site-nights at the same station into distinct non-overlapping episodes. Across 1,000 stratified warm-season calendar replications on strictly out-of-sample post-Year-1 site-years (requiring $\ge 60$ matched nights per warm season), we evaluated fixed annual visit budgets (12, 24, 52 visits site$^{-1}$ yr$^{-1}$, corresponding to 6, 12, 26 May–October visits) and equal total dollar budgets decomposing per-visit cost into travel/access (40%), daytime labor (60%), nocturnal labor/safety multipliers $m_{\text{night}} \in \{1.0, 1.35, 1.75, 2.5\}\times$ (early-shift civil daylight first-light modeled as $1 + 0.2(m_{\text{night}} - 1)$), and amortized continuous sonde cost $K_{\text{sonde}} \in [20, 100]$ daytime-visit-equivalents yr$^{-1}$ (benchmark \$200 daytime visit$^{-1}$). Risk-stratified hybrid protocols allocated continuous sondes to the top 10% or 20% sites ranked strictly out-of-sample via (a) Year-1 daytime grab DO statistics (`p10`, mean, fraction <6 mg L$^{-1}$), (b) Leave-One-Region-Out ridge regression on static site covariates, or (c) an oracle upper bound, spending all remaining budget on empirical WQP or first-light grabs at non-sonde sites.

---

## Data and code availability

All continuous DO records originate from public USGS Water Data STAC Parquet archives (`api.waterdata.usgs.gov/stac-files/continuous/`) and the UK Environment Agency Hydrology API (`environment.data.gov.uk/hydrology/id/stations`), and discrete U.S. agency field-visit logs originate from the U.S. Water Quality Portal (`waterqualitydata.us`). Complete reproducible analysis scripts (`scripts/00`–`14`), archived UTC and WQP extracts, zero-NaN summary tables (`tables/`), figure generators, automated verification tests (`tests/test_d4_pipeline.py`), and cryptographic artifact manifests (`SHA256SUMS.json`) are provided in the project repository.

---

## References

1. ODUM H. Primary Production in Flowing Waters. *Limnology and Oceanography* **1**, 102-117 (1956). https://doi.org/10.4319/lo.1956.1.2.0102
2. Benson B. & Krause D. The concentration and isotopic fractionation of oxygen dissolved in freshwater and seawater in equilibrium with the atmosphere. *Limnology and Oceanography* **29**, 620-632 (1984). https://doi.org/10.4319/lo.1984.29.3.0620
3. Pörtner H. Oxygen- and capacity-limitation of thermal tolerance: a matrix for integrating climate-related stressor effects in marine ecosystems. *Journal of Experimental Biology* **213**, 881-893 (2010). https://doi.org/10.1242/jeb.037523
4. Bernhardt E., Heffernan J., Grimm N. & Stanley E. The metabolic regimes of flowing waters. *Limnology and Oceanography* **63**, (2018). https://doi.org/10.1002/lno.10726
5. Appling A., Read J., Winslow L. & Arroita M. The metabolic regimes of 356 rivers in the United States. *Scientific Data* **5**, (2018). https://doi.org/10.1038/sdata.2018.292
6. Battin T., Lauerwald R., Bernhardt E. & Bertuzzo E. River ecosystem metabolism and carbon biogeochemistry in a changing world. *Nature* **613**, 449-459 (2023). https://doi.org/10.1038/s41586-022-05500-8
7. van Vliet M., Thorslund J., Strokal M. & Hofstra N. Global river water quality under climate change and hydroclimatic extremes. *Nature Reviews Earth & Environment* **4**, 687-702 (2023). https://doi.org/10.1038/s43017-023-00472-3
8. Blaszczak J., Koenig L., Mejia F. & Gómez‐Gener L. Extent, patterns, and drivers of hypoxia in the world's streams and rivers. *Limnology and Oceanography Letters* **8**, 453-463 (2023). https://doi.org/10.1002/lol2.10297
9. Zhi W., Klingler C., Liu J. & Li L. Widespread deoxygenation in warming rivers. *Nature Climate Change* **13**, 1105-1113 (2023). https://doi.org/10.1038/s41558-023-01793-3
10. Elfferich I. et al. Interpretation of river water quality data is strongly controlled by measurement time and frequency. *Science of The Total Environment* **954**, 176626 (2024). https://doi.org/10.1016/j.scitotenv.2024.176626
11. Graham D. et al. Climate change drives low dissolved oxygen and increased hypoxia rates in rivers worldwide. *Nature Climate Change* **15**, 1348-1354 (2025). https://doi.org/10.1038/s41558-025-02483-y
12. Zhou Y. et al. Widespread deoxygenation of freshwater ecosystems regularly reversed by nutrient management. *Nature Geoscience* **19**, 922-930 (2026). https://doi.org/10.1038/s41561-026-02024-y
13. Wagner R., Boulger R., Oblinger C. & Smith B. Guidelines and standard procedures for continuous water-quality monitors: Station operation, record computation, and data reporting. *Techniques and Methods* (2006). https://doi.org/10.3133/tm1D3
14. Iqbal M. An Introduction to Solar Radiation. *Academic Press* (1983). https://doi.org/10.1016/B978-0-12-373750-2.X5001-0
15. Kaplan E. & Meier P. Nonparametric Estimation from Incomplete Observations. *Journal of the American Statistical Association* **53**, 457-481 (1958). https://doi.org/10.1080/01621459.1958.10501452
16. Colin Cameron A. & Miller D. A Practitioner’s Guide to Cluster-Robust Inference. *Journal of Human Resources* **50**, 317-372 (2015). https://doi.org/10.3368/jhr.50.2.317
