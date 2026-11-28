# Vehicle Recall Completion at a Fixed Reporting Horizon: Software Remedy Channels, Manufacturer Common Support, and Public API Measurement Integrity

Zijian Zeng
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA
`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`

---

## Abstract

Evaluating recall compliance across over-the-air (OTA) wireless software remedies, hybrid OTA-or-dealer remedies, and dealership-only software remedies requires observing campaigns at a uniform statutory reporting horizon rather than mixing heterogeneous reporting ages in latest-snapshot registries. We link the National Highway Traffic Safety Administration's (NHTSA) 2024 and 2025 annual eighth-quarter recall completion lists (1,537 total rows; 100.0% matched to federal Part 573 filings; 2 conflicting duplicate campaigns excluded) into a verified, uniquely dated cross-sectional sample of **1,533 vehicle recalls**, including **15 Pure-OTA**, **15 Hybrid-OTA**, **197 Dealer-Software**, and **1,306 Physical-Hardware** campaigns. Complete sample-flow accounting on the statutory 2022–2023 owner-notification (`ODATE`) cohort ($N = 1,814$) reconciles every campaign by channel, showing that 98.8% of eighth-report campaigns track 49 CFR § 573.7(a)'s two-year notification clock and that 5 of 6 unlisted Pure-OTA campaigns terminated early at 100.0% completion.

At the fixed eighth-report milestone, unweighted mean completion proportions are **98.32%** for Pure-OTA (vehicle-weighted 98.58%), **89.56%** for Hybrid-OTA (94.39%), **82.06%** for Dealer Software (80.97%), and **67.26%** for Physical Hardware (65.93%). Because these annual lists provide cross-sectional milestone snapshots without multi-quarter longitudinal trajectories or phased remedy-availability dates, we interpret them strictly as fixed-horizon completion proportions rather than repair velocity. Auditing manufacturer $\times$ channel $\times$ vehicle-age common support reveals severe concentration: **Tesla accounts for 11/15 Pure-OTA recalls and 99.17% of Pure-OTA vehicles** while contributing 0 Dealer-Software recalls, whereas the remaining 4 non-Tesla Pure-OTA recalls (Lucid and Volvo Car) occur solely at oldest-model-year ages 0–1 years. While the dealer-software vehicle-age decay gradient is robustly negative across every specification and all 18 Leave-One-OEM-Out exclusions (**−3.52 pp/yr**, $p_{\text{WCB}} = 0.001$; standalone Dealer Software **−4.03 pp/yr**, $p_{\text{WCB}} = 0.001$; Physical Hardware **−3.27 pp/yr**, $p_{\text{WCB}} = 0.001$), the baseline Pure-OTA $\times$ Age interaction (**+3.69 pp/yr**, $p_{\text{WCB}} = 0.030$) loses statistical precision in the 0–5 year window (**+3.49**, $p_{\text{WCB}} = 0.226$), collapses upon excluding Tesla (**+1.59 pp/yr**, $p_{\text{WCB}} = 0.553$), and is null inside same-OEM common-support subsamples ($p_{\text{WCB}} = 0.703$). We therefore **explicitly withdraw any universal claim that OTA neutralizes vehicle-age compliance decay**. Alongside fixed-horizon proportions and dealer-channel decay, we retain the robust within-OEM conditional **Hybrid-OTA 7.01× batch-scale contrast** ($+1.947$ log points, $p_{\text{WCB}} = 0.006$, contrasted with null unconditional OEM adoption event studies) and document a **public Campaign API measurement validation audit** showing that NHTSA's public `overTheAirUpdate` flag dropped from 54/54 (100.0%) in 2019–2023 and `36/36 True` on Volvo `25V282000` (May 8, 2025) to `0/68` (0.0%) post-cutoff beginning May 9 with Ford `25V315000` (`44/44 False` despite verbatim OTA remedy text), even as NHTSA's *2025 Annual Recalls Report* recorded 33 OTA recalls internally.

**Keywords:** *automotive safety recalls; over-the-air software updates; fixed reporting horizon; vehicle-age compliance decay; common-support diagnostics; public API measurement audit; 49 CFR 573.7; NHTSA*

---

## 1. Introduction

Motor vehicle safety recalls represent a central intersection of regulatory compliance, service-bay operations, and public road safety. Prior scholarship across economics, marketing, and operations management has examined recall timing, firm valuation, organizational learning, component sharing, and safety effectiveness in traditional mechanical recalls (Jarrell and Peltzman 1985; Barber and Darrough 1996; Rupp and Taylor 2002; Haunschild and Rhee 2004; MacCormack et al. 2006; Ramdas and Randall 2008; Bae and Benítez-Silva 2011; Hora et al. 2011; Thirumalai and Sinha 2011; Kalaignanam et al. 2013; Eilert et al. 2017; Shah et al. 2017; Ball et al. 2018), alongside theoretical studies of software patching incentives and user compliance (Arora et al. 2006; August and Tunca 2006; Cavusoglu et al. 2008). In the U.S. regulatory record, the National Highway Traffic Safety Administration's (NHTSA) own supplemental analysis (*Vehicle Safety Recall Completion Rates*, Report No. `DOT HS 813 687`; NHTSA 2025) establishes two foundational empirical determinants of conventional recall completion: **vehicle age**—as older vehicles exit franchised dealership maintenance networks and change owners in secondary markets—and **delays in remedy availability** between Part 573 defect filing and final owner notification. Complementary marketing research by Pagiavlas et al. (2022 [online 2021]) evaluates whether digital information campaigns ("Safe Cars Save Lives") improve consumer recall compliance.

As automakers deploy software-defined vehicles (SDVs), recalls involving embedded software can be delivered through three distinct administrative remedy channels: **Pure-OTA** (wireless-only remote updates), **Hybrid-OTA** (owner choice between an OTA update and a franchised dealership visit, or an OTA software push paired with hardware inspection), and **Dealer Software** (in-shop module reprogramming). NHTSA's `DOT HS 813 687` report (p. 1, fn. 1) explicitly designates *"Remedies involving Over-the-Air updates"* as one of seven high-risk oversight categories under its risk-based monitoring framework. Yet rigorous cross-channel comparison of recall completion in public federal records confronts three acute empirical hazards that have not been jointly resolved:

1. **Heterogeneous Reporting Horizons in Latest-Snapshot Registries:** The public U.S. Department of Transportation (DOT) open-data recalls file (`6axg-epim`) reports only each campaign's *latest* recorded completion rate, blending recent campaigns with campaigns that continued reporting well beyond the statutory six-quarter floor under **49 CFR § 573.7(a)**. As NHTSA itself notes in `DOT HS 813 687` (p. 5), comparing completion across manufacturers or remedy channels requires anchoring campaigns at a **fixed reporting horizon**—the eighth reporting quarter published in NHTSA's 2024 and 2025 annual completion lists—while explicitly accounting for sample flow (campaigns that completed 100% early, lacked reports, or had not yet reached their eighth quarter).
2. **Severe Manufacturer $\times$ Channel $\times$ Vehicle-Age Common-Support Limits:** Pure-OTA recalls in early fixed-horizon cohorts are overwhelmingly concentrated in a single EV-native manufacturer (`Tesla, Inc.`), while non-Tesla Pure-OTA fleets are newly manufactured (`0–1` years old at filing in the eighth-report cohort). Pooling across manufacturers with non-overlapping channel and vehicle-age support risks mistaking single-OEM fleet characteristics for a universal technological property of OTA delivery.
3. **Public Federal API Measurement Drift:** Automated research pipelines and consumer VIN tools frequently rely on NHTSA's public Campaign API boolean field (`overTheAirUpdate`). Without independent validation against verbatim Part 573 corrective-action narratives and NHTSA's published annual reports, unannounced changes in public-endpoint flag serialization can silently corrupt OTA classification.

This study addresses all three challenges using a verified, machine-readable dataset anchored on NHTSA's 2024 and 2025 annual eighth-quarter completion lists linked to the complete 2015–2026 NHTSA Office of Defects Investigation (ODI) Part 573 census ($N = 10,559$ vehicle campaigns; $7,967$ in 2018–2026) and a 1,452-campaign audit of NHTSA's public Campaign API. Our paper makes four disciplined contributions organized specifically for safety-monitoring transparency and dataset reproducibility:

- **Fixed-Horizon Reconciliation and Complete Sample-Flow Accounting (Section 2):** We lock, verify, and row-reconcile all 1,537 published eighth-report entries against `FLAT_RCL_POST_2010.zip` and `6axg-epim` (100.0% campaign linkage; 99.87% exact vehicle-denominator match; 100.0% exact match on all 227 software recalls), cleanly exclude 2 conflicting duplicate campaigns (`22V315`, `22V743`), and account channel-by-channel for every campaign in the statutory 2022–2023 owner-notification (`ODATE`) cohort ($N = 1,814$).
- **Fixed-Horizon Completion Proportions (Section 3):** We report unweighted, median, and vehicle-weighted eighth-report completion proportions by remedy channel and annual cohort strictly as **fixed-horizon completion proportions** (refraining from inferring repair velocity or hazard curves from cross-sectional snapshots).
- **Manufacturer $\times$ Channel $\times$ Vehicle-Age Common-Support Audit and Explicit Claim Withdrawal (Section 4):** We publish a complete common-support matrix and 18-OEM Leave-One-OEM-Out (`LOOO`) sensitivity audit demonstrating that while the **dealer-software vehicle-age decay gradient is rock-solid** (−3.52 pp/yr in the 18-OEM sample; −4.03 pp/yr across all 53 Dealer-Software OEMs; significant in 18/18 LOOO drops, all $p_{\text{WCB}} \le 0.003$), existing public eighth-report and mature data lack multi-OEM older-vehicle common support to identify an OTA age-buffering effect. Accordingly, we **explicitly withdraw any universal claim that OTA neutralizes vehicle-age compliance decay**.
- **Public API Measurement Validation Audit, Conditional Batch-Scale Contrast, and Causal Operational Roadmap (Sections 5–6):** Separating verbatim Part 573 text coding (`Pure-OTA`, `Hybrid SW-Choice`, `Hybrid HW-Mixed`, `Dealer-Software`) from the public Campaign API flag isolates a May 8, 2025 public-endpoint serialization break (`25V282000` `36/36 True` vs. May 9 `25V315000` `44/44 False`; `0/68` thereafter) contrasted with NHTSA's *2025 Annual Recalls Report* (33 OTA recalls internally), framed strictly as a public-API validation audit; we pair this with the retained within-OEM conditional **Hybrid-OTA 7.01× batch-scale contrast** ($+1.947$ log points, $p_{\text{WCB}} = 0.006$) versus null unconditional OEM first-OTA adoption event studies, and close by specifying the exact longitudinal and quasi-experimental operational data needed for future causal mechanism identification.

---

## 2. Fixed Reporting Horizon, Source Reconciliation, and Sample Flow Accounting

### 2.1 Statutory Reporting Clock Under 49 CFR § 573.7 and Fixed-Horizon Selection

Under **49 CFR § 573.7(a)** (Office of the Federal Register 2026), manufacturers must file quarterly recall completion reports *"for each of six consecutive quarters beginning with the quarter in which the campaign was initiated (i.e., the date the manufacturer notifies its purchasers of the availability of a remedy) or corrective action has been completed on all defective or noncomplying vehicles ... whichever occurs first."* Two statutory mechanics directly govern empirical monitoring:

1. **Remedy-Notification Clock vs. Filing Date:** The quarterly completion clock starts at owner remedy notification (`ODATE`), not at Part 573 defect filing (`RCDATE`). Phased recalls that mail interim hazard notices under 49 CFR § 577.5 before a final software or parts remedy is ready enter quarterly reporting later than single-phase campaigns.
2. **Early Termination at 100% Completion and Unreachable-Vehicle Denominators:** Campaigns reaching 100% completion prior to the eighth reporting quarter lawfully terminate quarterly reporting under § 573.7(a) and therefore exit fixed-horizon lists. Meanwhile, § 573.7(b)(5) records vehicles deemed unreachable due to export, theft, scrapping, or undeliverable notification, meaning reported completion percentages reflect completion among reachable vehicles rather than raw unadjusted production totals.

In its supplemental FAST Act report (`DOT HS 813 687`, p. 5), NHTSA evaluated 2010–2022 light-vehicle recalls strictly at their **fifth reporting quarter** (substituting the early-completion quarter if 100% was achieved sooner) specifically *"to control for variability in the length of reporting periods among manufacturers, as some companies continue to submit well after the minimum regulatory requirement."* Similarly, NHTSA's published **2024 and 2025 Annual Lists of Recall Completion Rates** (NHTSA 2025, 2026a) anchor campaigns at a uniform **eighth-quarter completion milestone**. By contrast, the latest-snapshot DOT open-data registry (`6axg-epim`) updates dynamically past the eighth quarter: among the 1,528 eighth-report campaigns also rated in `6axg-epim` as of November 25, 2026, latest-snapshot rates exceed the eighth-report milestone in 1,197 campaigns (median drift **+3.62 pp**, mean **+5.42 pp**), demonstrating why latest-snapshot data confound reporting duration with remedy performance. Because the annual eighth-report lists provide one cross-sectional completion proportion per campaign without intermediate Q1–Q7 trajectories or phase-specific remedy availability dates, our primary analysis interprets these figures strictly as **fixed-horizon completion proportions** and relegates all mature ($\ge 18$-month) latest-snapshot cross-sections to Online Appendix Section S2.

### 2.2 Verifiable Source Freezing, Reconciliation, and Duplicate Exclusion

We integrate four locked public federal inputs with cryptographic SHA-256 receipts (`SHA256SUMS.json`): (i) NHTSA's complete Part 573 Vehicle Recall flat file (`FLAT_RCL_POST_2010.zip`, $10,559$ campaigns in 2015–2026; $7,967$ in 2018–2026, harmonized from 705 raw manufacturer strings into 646 canonical corporate entities); (ii) the transcribed 2024 and 2025 eighth-report source table (`data_raw/nhtsa_annual_eighth_report_2024_2025.csv`, SHA-256 `7c19005d8880e8b1...`, 1,537 rows: 809 in 2024 and 728 in 2025); (iii) U.S. DOT's official Socrata registry (`6axg-epim`, frozen November 25, 2026) and NHTSA's official ROSA P report PDF (`dot_79374_DS1.pdf`, HTTP 200, SHA-256 `8ed143715331731b...`); and (iv) our 1,452-campaign live query census of `api.nhtsa.gov/recalls/campaignNumber` supplemented by fresh boundary spot-checks (`results/d12_v4_live_api_spotcheck.json`). We note transparently that direct automated HTTP requests to the `www.nhtsa.gov` PDF URLs for the 2024 and 2025 annual lists returned HTTP 403 Akamai CDN access control; strictly adhering to non-bypass protocols, we locked the verbatim transcribed 1,537-row table and executed a complete 100% row-level programmatic reconciliation against `FLAT_RCL_POST_2010.zip` and `6axg-epim`:

- **Campaign Linkage (100.0%):** Every single row (809/809 in 2024 and 728/728 in 2025; zero unlinked rows) links cleanly via its six-character NHTSA campaign identifier (`campaign_code`) to the frozen Part 573 panel.
- **Conflicting Duplicate Exclusion (2 Campaigns, 4 Rows):** Exactly two campaigns appear in *both* the 2024 and 2025 annual lists with conflicting eighth-report completion percentages: Mercedes-Benz `22V315` (Physical Hardware, 350,294 vehicles: **56.9%** in 2024 vs. **45.6%** in 2025; latest DOT 51.44%) and Bentley `22V743` (Dealer Software, 3,134 vehicles: **84.2%** in 2024 vs. **79.2%** in 2025; latest DOT 82.26%). Dropping all four duplicate rows leaves **1,533 uniquely dated eighth-report campaigns** (807 in 2024; 726 in 2025).
- **Vehicle-Denominator Reconciliation (99.87% Exact Match):** Comparing the eighth-report affected vehicle count (`reported_affected`) against `FLAT_RCL`/`6axg-epim` (`potaff`) yields an **exact single-vehicle match on 1,531/1,533 (99.87%) campaigns** ($\log r = 0.99987$) and **100.0% (227/227) exact agreement across all software recalls** (Pure-OTA, Hybrid-OTA, and Dealer Software). Auditing the only two discrepancies—both Physical Hardware—reveals Honda `22V867` (`17,445` in the transcribed 2025 table vs. `117,445` in `FLAT_RCL` and `6axg-epim`, flagged transparently as a missing leading digit in source extraction) and Chrysler/FCA `23V413` (`331,401` vs. `305,282`, reflecting post-filing denominator amendment). Neither enters any software-channel regression.
- **Owner-Notification Clock Verification (98.8% Statutory Alignment):** Exactly **793/807 (98.3%)** of unique 2024 eighth-report campaigns carried owner notification dates (`ODATE`) in calendar year **2022**, and **722/726 (99.5%)** of unique 2025 eighth-report campaigns carried `ODATE` in calendar year **2023**—directly empirically validating 49 CFR § 573.7(a)'s two-year notification clock.

### 2.3 Channel-by-Channel Sample Flow Accounting

Because eighth-report annual lists observe only campaigns that reached their eighth reporting quarter without completing 100% earlier, interpreting cross-channel completion proportions requires complete sample-flow accounting across all remedy channels. **Table 1** and **Figure 1A** reconcile three nested frames: (A) the statutory **2022–2023 `ODATE` cohort** ($N = 1,814$ campaigns), (B) the **2022–2023 `RCDATE` filing cohort** ($N = 1,827$ campaigns), and (C) the full **2018–2026 NHTSA vehicle recall universe** ($N = 7,967$ campaigns).

**Table 1.** *Complete Channel-by-Channel Sample Flow Accounting: Statutory 2022–2023 Owner-Notification Cohort (`ODATE`), 2022–2023 Filing Cohort (`RCDATE`), and 2018–2026 Universe.*

| Cohort & Modality | Total Recalls | In 8th Report (Unique) | Share in 8th (%) | Excl. Duplicate | Unlisted: 100% Early Complete | Unlisted: Missing DOT Report | Unlisted: Delayed / Out-of-Window |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Panel A: Statutory 2022–2023 Owner-Notification Cohort (`ODATE`)** | | | | | | | |
| Pure-OTA (Wireless-Only) | 21 | 15 | 71.4% | 0 | 5 | 1 | 0 |
| Hybrid-OTA (OTA or Dealer) | 15 | 15 | 100.0% | 0 | 0 | 0 | 0 |
| Dealer Software | 229 | 196 | 85.6% | 1 | 18 | 12 | 2 |
| Physical Hardware | 1,549 | 1,293 | 83.5% | 1 | 187 | 59 | 9 |
| **All Vehicles (ODATE 2022–2023 Total)** | 1,814 | 1,519 | 83.7% | 2 | 210 | 72 | 11 |
| **Panel B: 2022–2023 Part 573 Filing-Year Cohort (`RCDATE`)** | | | | | | | |
| Pure-OTA (Wireless-Only) | 24 | 15 | 62.5% | 0 | 6 | 1 | 2 |
| Hybrid-OTA (OTA or Dealer) | 15 | 14 | 93.3% | 0 | 0 | 0 | 1 |
| Dealer Software | 236 | 179 | 75.8% | 1 | 19 | 13 | 24 |
| Physical Hardware | 1,552 | 1,163 | 74.9% | 1 | 192 | 61 | 135 |
| **Panel C: Full 2018–2026 NHTSA Vehicle Recall Universe** | | | | | | | |
| Pure-OTA (Wireless-Only) | 61 | 15 | 24.6% | 0 | 5 | 1 | 40 |
| Hybrid-OTA (OTA or Dealer) | 101 | 15 | 14.9% | 0 | 0 | 0 | 86 |
| Dealer Software | 984 | 197 | 20.0% | 1 | 18 | 12 | 756 |
| Physical Hardware | 6,821 | 1,306 | 19.1% | 1 | 187 | 59 | 5,268 |

*Notes:* Panel A tracks all 1,814 vehicle recalls with recorded owner notification (`ODATE`) in 2022–2023; adding 14 delayed 2020–2021 `ODATE` campaigns (1 Dealer Software, `20V771` Honda, plus 13 Physical Hardware) yields the exact 1,533 uniquely dated eighth-report campaigns. In Panel B, late-2023 Part 573 filings whose `ODATE` fell in 2024 (including Tesla `23V838`, `23V862`, Rivian `23V883`, and Lonestar `23V768`) had not yet reached their eighth reporting quarter by end-2025.

Three administrative selection mechanics stand out in Table 1:

1. **Complete Accounting of Software-OTA Campaigns:** Within the statutory 2022–2023 `ODATE` cohort, **15/15 (100.0%)** of Hybrid-OTA recalls appear uniquely in the 2024–2025 eighth-report lists. Among **21** Pure-OTA recalls, **15 (71.4%)** appear uniquely, and **100% of the remaining 6 unlisted campaigns are accounted for**: **5** reached **100.0% completion** prior to the eighth report (`22V037` Tesla 53,822 veh; `22V169` Tesla 947 veh; `23V244` Tesla 38 veh; `23V422` Tesla 36 veh; `23V783` Rivian 1,463 veh), lawfully terminating quarterly reporting under § 573.7(a), and **1** (`22V063` Tesla Boombox, 578,607 veh) lacks a DOT completion record.
2. **Differential Early-Completion Selection Across Channels:** Early 100% completion prior to the eighth quarter accounts for **23.8%** (5/21) of Pure-OTA campaigns versus **7.9%** (18/229) of Dealer Software and **12.1%** (187/1549) of Physical Hardware—indicating that fixed eighth-report Pure-OTA means slightly *understate* unconditional Pure-OTA completion by omitting campaigns that hit 100% early.
3. **Notification-Lag Filtering in Filing-Year Cohorts:** Comparing Panel A (`ODATE`) with Panel B (`RCDATE`) shows why late-2023 filings with 2024 owner-notification dates (e.g., Tesla `23V838`, 2,031,220 veh, `ODATE` Feb 10, 2024; Tesla `23V862`, 120,423 veh, `ODATE` Feb 17, 2024; Rivian `23V883`, 7,873 veh, `ODATE` Jan 18, 2024) are legitimately absent from the 2025 eighth-report list and will enter the 2026 list upon completing eight reporting quarters.

<!-- FIGURE:fig1_v4_sample_flow_and_completion.png -->

### 2.4 Remedy-Channel Coding and Finite-Sample Cluster-Robust Inference

To prevent public API serialization anomalies from contaminating channel labels, we classify every campaign strictly from its verbatim Part 573 and DOT `CORRECTIVE_ACTION` text (explicitly screening out negations such as *"not eligible for an over-the-air update"*), separating four mutually exclusive remedy channels (and subdividing Hybrid-OTA in audit tables): (1) **Pure-OTA** (wireless-only software update with no dealer visit, inspection, or hardware replacement clause), (2) **Hybrid-OTA** (OTA-capable software update paired with either a dealer software option—**Hybrid SW-Choice**—or physical hardware replacement/inspection—**Hybrid HW-Mixed**), (3) **Dealer Software** (software/firmware reprogramming or calibration without an OTA option), and (4) **Physical Hardware** (all non-software physical remedies). Critically, a Hybrid-OTA Part 573 notice documents *channel availability* ("over-the-air or by a dealer"), not the share of vehicles actually remedied wirelessly versus in dealership bays.

All regressions are estimated via full-rank verified ordinary least squares absorbing Manufacturer, Component-Group (top 14 subsystems plus Other), Filing-Quarter, and Annual Report-Year fixed effects (plus Model-Year fixed effects in batch-scale regressions), with Stata finite-sample CR1 manufacturer-clustered standard errors, $t(G - 1)$ inference, and exact null-imposed $B = 999$ Rademacher Wild Cluster Bootstrap $p$-values ($p_{\text{WCB}}$; Cameron et al. 2008; Cameron and Miller 2015; MacKinnon and Webb 2017). Mathematical exactness of the vectorized WCB implementation is verified against brute-force bootstrap resampling to $< 10^{-10}$ in `tests/test_d12_boost.py`.

---

## 3. Fixed-Horizon Completion Proportions by Remedy Channel and Manufacturer

### 3.1 Descriptive Fixed Eighth-Report Completion Proportions

**Table 2** and **Figure 1B** present unweighted campaign means, standard deviations, medians, interquartile ranges, and vehicle-weighted completion proportions across the 2024, 2025, and pooled 1,533-campaign eighth-report cohorts.

**Table 2.** *Fixed Eighth-Report Completion Proportions by Remedy Channel and Report Year (N = 1,533 Uniquely Dated Campaigns).*

| Report List | Remedy Channel | Campaigns ($N$) | OEMs | Mean (%) | SD (pp) | Median (%) | IQR (%) | Vehicle-Weighted Mean (%) | Summed Affected Vehicles | Median Size |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 2024 List | Pure-OTA (Wireless-Only) | 6 | 1 | 99.47 | 1.02 | 99.90 | 99.7–100.0 | 98.56 | 1,657,030 | 89,072 |
| 2024 List | Hybrid-OTA (OTA or Dealer) | 10 | 5 | 87.93 | 11.59 | 92.50 | 86.1–94.4 | 92.08 | 769,050 | 23,662 |
| 2024 List | Dealer Software | 94 | 36 | 80.75 | 16.67 | 84.65 | 70.8–95.2 | 80.06 | 5,673,290 | 8,463 |
| 2024 List | Physical Hardware | 697 | 173 | 64.83 | 26.52 | 69.60 | 48.0–87.4 | 63.85 | 22,034,823 | 553 |
| 2025 List | Pure-OTA (Wireless-Only) | 9 | 3 | 97.56 | 2.48 | 98.50 | 96.5–99.3 | 98.59 | 1,894,765 | 29,348 |
| 2025 List | Hybrid-OTA (OTA or Dealer) | 5 | 3 | 92.82 | 8.65 | 95.40 | 94.3–96.7 | 96.57 | 813,453 | 6,422 |
| 2025 List | Dealer Software | 103 | 39 | 83.26 | 15.75 | 86.20 | 74.3–96.0 | 82.41 | 3,565,937 | 2,934 |
| 2025 List | Physical Hardware | 609 | 128 | 70.05 | 27.22 | 77.90 | 56.3–91.3 | 68.60 | 17,154,856 | 559 |
| **Pooled 2024–2025** | Pure-OTA (Wireless-Only) | 15 | 3 | 98.32 | 2.20 | 99.30 | 97.8–99.8 | 98.58 | 3,551,795 | 48,184 |
| **Pooled 2024–2025** | Hybrid-OTA (OTA or Dealer) | 15 | 6 | 89.56 | 10.65 | 93.40 | 87.3–95.5 | 94.39 | 1,582,503 | 19,937 |
| **Pooled 2024–2025** | Dealer Software | 197 | 53 | 82.06 | 16.20 | 85.50 | 73.3–95.5 | 80.97 | 9,239,227 | 6,262 |
| **Pooled 2024–2025** | Physical Hardware | 1,306 | 213 | 67.26 | 26.96 | 74.20 | 50.5–89.7 | 65.93 | 39,189,679 | 555 |

*Notes:* All completion figures represent cross-sectional completion proportions at NHTSA's eighth reporting quarter milestone, not longitudinal repair-velocity or hazard-rate estimates. All 6 Pure-OTA campaigns in the 2024 list belong to a single manufacturer (`Tesla, Inc.`).

Across the pooled 2024–2025 fixed eighth-report sample, observed completion proportions display a clear descriptive ordering: **Pure-OTA** averages **98.32%** (median 99.30%, vehicle-weighted 98.58%), **Hybrid-OTA** averages **89.56%** (median 93.40%, vehicle-weighted 94.39%), **Dealer Software** averages **82.06%** (median 85.50%, vehicle-weighted 80.97%), and **Physical Hardware** averages **67.26%** (median 74.20%, vehicle-weighted 65.93%). Within the eight manufacturers that actually execute both Dealer Software and OTA remedies in the eighth-report sample ($N = 70$, $G = 8$), controlling for OEM, component, filing-quarter, report-year fixed effects, and oldest-model-year vehicle age yields a positive level contrast for pooled OTA of **+6.78 pp** ($p_{\text{WCB}} = 0.024$; Hybrid-OTA **+7.33 pp**, $p_{\text{WCB}} = 0.070$; Pure-OTA **+2.88 pp**, $p_{\text{WCB}} = 0.420$). Crucially, however, raw and level-adjusted cross-channel proportions reflect both delivery friction and unobserved differences in defect type, fleet connectivity, and manufacturer composition (including the fact that all 6 Pure-OTA recalls in 2024 came from one OEM). We therefore refrain from inferring causal delivery speed or repair-hazard curves from these cross-sectional snapshots.

---

## 4. Manufacturer × Channel × Vehicle-Age Common Support and Leave-One-OEM-Out Sensitivity

### 4.1 Explicit Manufacturer × Channel × Vehicle-Age Common-Support Audit

A central question for safety research is whether wireless OTA delivery offsets the steep decline in recall completion as vehicles age into secondary markets (NHTSA 2025). Testing an OTA $\times$ vehicle-age interaction credibly requires **common support**—multiple manufacturers executing both OTA and dealer-software recalls across overlapping vehicle ages, including older ($\ge 5$–6 year) vehicles. **Table 3** and **Figure 2** expose the exact support structure of the fixed eighth-report software sample ($N = 148$ across 18 OTA-capable OEMs; complete cross-horizon matrix archived in `tables/table_channel_oem_age_support.csv`).

**Table 3.** *Manufacturer × Channel × Vehicle-Age Common-Support Matrix in the Fixed Eighth-Report Software Sample ($N = 148$, 18 OTA-Capable OEMs).*

| Remedy Channel | Manufacturer (Canonical OEM) | Campaigns ($N$) | Affected Vehicles | Share of Channel Veh. (%) | Oldest-MY Age Range (yr) | $N$ Aged $\ge 6$ yr | Mean 8th-Rep. (%) | Both Dealer-SW & OTA? |
|---|---|---:|---:|---:|---:|---:|---:|:---:|
| Pure-OTA (Wireless-Only) | Tesla, Inc. | 11 | 3,522,202 | 99.17% | 1–7 | 1 | 99.06 | **No** |
| Pure-OTA (Wireless-Only) | Volvo Car USA, LLC | 1 | 27,457 | 0.77% | 0 | 0 | 99.50 | Yes |
| Pure-OTA (Wireless-Only) | Lucid USA, Inc. | 3 | 2,136 | 0.06% | 1 | 0 | 95.20 | Yes |
| Hybrid-OTA (OTA or Dealer) | General Motors, LLC | 3 | 1,138,997 | 71.97% | 0–2 | 0 | 94.90 | Yes |
| Hybrid-OTA (OTA or Dealer) | Mercedes-Benz USA, LLC | 2 | 243,961 | 15.42% | 0–5 | 0 | 91.10 | Yes |
| Hybrid-OTA (OTA or Dealer) | Ford Motor Company | 6 | 135,321 | 8.55% | 0–2 | 0 | 85.45 | Yes |
| Hybrid-OTA (OTA or Dealer) | Nissan North America, Inc. | 2 | 37,865 | 2.39% | 1 | 0 | 97.10 | Yes |
| Hybrid-OTA (OTA or Dealer) | Daimler Vans USA, LLC | 1 | 19,937 | 1.26% | 3 | 0 | 75.30 | Yes |
| Hybrid-OTA (OTA or Dealer) | Jaguar Land Rover North America, LLC | 1 | 6,422 | 0.41% | 4 | 0 | 94.30 | Yes |
| Dealer Software | 8 Same-OEM Common-Support Manufacturers (8 OEMs) | 51 | 2,576,255 | 34.37% | 0–15 | 2 | 83.01 | Yes |
| Dealer Software | 9 OTA-Capable OEMs Without 8th-Report OTA (9 OEMs) | 67 | 4,921,194 | 65.65% | 0–9 | 7 | 85.33 | No |

*Notes:* Vehicle age is `rec_year` minus oldest affected model year (`min_my`), clipped to $[0, 15]$. Full OEM-level breakdown across both the fixed eighth-report cohort and the mature $\ge 18$-month DOT snapshot is archived in `tables/table_channel_oem_age_support.csv`.

The support audit reveals four binding structural limitations that preclude a universal OTA age-buffering conclusion:

1. **Single-OEM Dominance in Pure-OTA:** Among all **15** fixed eighth-report Pure-OTA campaigns, **`Tesla, Inc.` accounts for 11/15 recalls (73.3%) and 99.17% of affected vehicles** (3,522,202 of 3,551,795), spanning oldest-model-year ages 1–7 years—while contributing **zero (0) Dealer-Software recalls** in the eighth-report sample. Tesla therefore has **no within-OEM dealer-software counterfactual** at the eighth-report horizon.
2. **Zero Older-Vehicle Support Outside Tesla:** The remaining **4** non-Tesla Pure-OTA recalls come from just two manufacturers—`Lucid USA, Inc.` (3 recalls, 2,136 vehicles, all oldest-MY age **1 year**) and `Volvo Car USA, LLC` (1 recall, 27,457 vehicles, oldest-MY age **0 years**). Neither manufacturer contributes any within-OEM Pure-OTA vehicle-age variation, and **zero non-Tesla Pure-OTA recalls reach age $\ge 2$ years** in the eighth-report sample. Even in the broader mature $\ge 18$-month DOT snapshot (`6axg-epim`, Online Appendix Section S2), Tesla accounts for **27/46 Pure-OTA recalls**, **98.73% of affected vehicles**, and **6/6 (100.0%) of all Pure-OTA recalls aged $\ge 6$ years** (Figure 2B), while non-Tesla light-duty Pure-OTA maxes out at age 3 years.
3. **Narrow Age Support in Hybrid-OTA:** The 15 fixed eighth-report Hybrid-OTA recalls span 6 legacy manufacturers (`Ford`, `General Motors`, `Mercedes-Benz`, `Nissan`, `Jaguar Land Rover`, `Daimler Vans`), with 13 of 15 concentrated at ages 0–3 years and zero reaching age $\ge 6$ years (max age 5 years: one Mercedes-Benz recall).
4. **Minimal Same-OEM and Same-Model Overlap:** Strictly restricting the eighth-report cohort to manufacturers observing *both* Dealer Software and any OTA channel leaves just **8 OEMs** ($N = 70$: 4 Pure-OTA, 15 Hybrid-OTA, 51 Dealer Software)—**excluding Tesla altogether**—and intersecting each OEM's overlapping age span reduces the sample to $N = 53$. Restricting further to exact same `primary_make_model` lines leaves only **6 models** (`FORD MUSTANG MACH E`, `FREIGHTLINER SPRINTER 1500`, `JAGUAR I-PACE`, `LUCID AIR`, `MERCEDES-BENZ EQS 450`, `VOLVO C40BEV`; $N = 20$ campaigns total), each having a single OTA campaign age and thus **zero within-model OTA age variation**.

<!-- FIGURE:fig2_v4_channel_oem_age_support.png -->

### 4.2 Vehicle-Age Gradients, Common-Support Subsamples, and Complete 18-OEM LOOO

**Table 4** and **Figure 3** quantify the econometric consequences of this support structure across age definitions, age windows, Tesla exclusion, same-OEM common-support subsamples, standalone channel benchmarks, and complete 18-OEM Leave-One-OEM-Out (`LOOO`) sensitivity (full 18-row LOOO table in Online Appendix Table S1 and `tables/table_v4_looo_sensitivity.csv`).

**Table 4.** *Fixed Eighth-Report Vehicle-Age Gradient Sensitivity and Common-Support Subsamples (CR1 Cluster-Robust Inference with $B = 999$ Rademacher $p_{\text{WCB}}$).*

| Fixed 8th-Report Specification | $N$ | OEMs | Dealer / Channel Age Slope (pp/yr, $p_{\text{WCB}}$) | Pure-OTA $\times$ Age (pp/yr, $p_{\text{WCB}}$) | Hybrid / Pooled OTA $\times$ Age (pp/yr, $p_{\text{WCB}}$) |
|---|---:|---:|---:|---:|---:|
| Baseline fixed 8th report (oldest MY, 18 OEMs) | 148 | 18 | −3.52 (0.001) | +3.69 (0.030) | +0.75 (0.718) |
| Fixed 8th report (middle MY, 18 OEMs) | 148 | 18 | −4.34 (0.001) | +7.47 (0.022) | −2.02 (0.599) |
| Fixed 8th report (oldest MY, restricted 0–5 yr) | 138 | 18 | −3.83 (0.001) | +3.49 (0.226) | +1.18 (0.509) |
| **Fixed 8th report (oldest MY, excluding Tesla, 4-way)** | 137 | 17 | −3.56 (0.001) | +1.59 (0.553) | +0.72 (0.709) |
| Fixed 8th report (oldest MY, excluding Tesla, pooled OTA) | 137 | 17 | −3.56 (0.001) | — (pooled) | +0.68 (0.675) |
| Fixed 8th report (middle MY, excluding Tesla, pooled OTA) | 137 | 17 | −4.38 (0.001) | — (pooled) | −2.30 (0.567) |
| Same-OEM common support (8 OEMs observing both, 4-way) | 70 | 8 | −3.67 (0.074) | +6.52 (0.201) | +0.26 (0.835) |
| Same-OEM common support (8 OEMs observing both, pooled OTA) | 70 | 8 | −3.66 (0.059) | — (pooled) | +0.49 (0.703) |
| Strict Same-OEM × Overlapping-Age support (8 OEMs) | 53 | 8 | +1.98 (0.847) | — (pooled) | −3.51 (0.289) |
| Standalone Dealer-Software (all 53 OEMs in 8th report) | 197 | 53 | −4.03 (0.001) | — | — |
| Standalone Physical-Hardware (all 213 OEMs in 8th report) | 1,306 | 213 | −3.27 (0.001) | — | — |

*Notes:* All models include Manufacturer, Component-Group, Filing-Quarter, and Report-Year fixed effects with OEM-clustered $B = 999$ Rademacher Wild Cluster Bootstrap $p$-values in parentheses. Supplementary mature latest-snapshot regressions (including 29-model Make-Model FE overlap with and without Tesla) are reported in Online Appendix Table S2.

Every econometric check converges on the exact same sharp diagnostic split:

- **Rock-Solid Dealer-Channel Vehicle-Age Decay:** Holding manufacturer, component, filing quarter, and report year constant, Dealer-Software completion at the eighth report declines by **−3.52 pp per year of oldest-model-year age** ($p_{\text{WCB}} = 0.001$; **−4.34 pp/yr** using middle model year, $p_{\text{WCB}} = 0.001$). Across all 53 OEMs in standalone Dealer Software ($N = 197$), the gradient is **−4.03 pp/yr** ($p_{\text{WCB}} = 0.001$), closely matching standalone Physical Hardware across all 213 OEMs ($N = 1,306$; **−3.27 pp/yr**, $p_{\text{WCB}} = 0.001$). Across all **18 Leave-One-OEM-Out exclusions** (Figure 3B), the Dealer-Software age slope stays tightly bounded between **−3.60** and **−3.04 pp/yr** and remains statistically significant in **18/18** drops (maximum $p_{\text{WCB}} = 0.003$).
- **Fragility and Collapse of the Pure-OTA $\times$ Age Interaction:** Although the pooled 18-OEM baseline specification yields a nominal Pure-OTA $\times$ Age interaction of **+3.69 pp/yr** ($p_{\text{WCB}} = 0.030$), that estimate fails every common-support stress test:
  1. Restricting to the **0–5 year age window** ($N = 138$) leaves the interaction statistically imprecise (**+3.49 pp/yr**, $p_{\text{WCB}} = 0.226$);
  2. **Excluding Tesla** ($N = 137$, 17 OEMs) collapses Pure-OTA $\times$ Age to **+1.59 pp/yr** (**$p_{\text{WCB}} = 0.553$**; pooled ex-Tesla OTA **+0.68**, $p_{\text{WCB}} = 0.675$; middle-MY pooled ex-Tesla **−2.30**, $p_{\text{WCB}} = 0.567$);
  3. Restricting to the **8 same-OEM common-support manufacturers** ($N = 70$) yields null interactions for pooled OTA (**+0.49**, $p_{\text{WCB}} = 0.703$), Pure-OTA (**+6.52**, $p_{\text{WCB}} = 0.201$), and Hybrid-OTA (**+0.26**, $p_{\text{WCB}} = 0.835$), and restricting further to **strict same-OEM $\times$ overlapping-age cells** ($N = 53$) turns negative and imprecise (**−3.51**, $p_{\text{WCB}} = 0.289$);
  4. Across all **18 Leave-One-OEM-Out drops** (Figure 3B), Pure-OTA $\times$ Age fails 5% wild-cluster-bootstrap significance in **8/18** exclusions (dropping Tesla, Chrysler, Ford, General Motors, Honda, Mack Trucks, Mercedes-Benz, or Nissan).
- **Consistent Null for Hybrid-OTA $\times$ Age:** Hybrid-OTA $\times$ Age is statistically indistinguishable from zero in the baseline (**+0.75**, $p_{\text{WCB}} = 0.718$), flips sign under middle model year (**−2.02**, $p_{\text{WCB}} = 0.599$), and achieves $p_{\text{WCB}} < 0.05$ in **0/18** LOOO specifications.

<!-- FIGURE:fig3_v4_age_gradients_and_looo.png -->

### 4.3 Explicit Withdrawal of Universal OTA Age-Buffering Claims

Based on the common-support audit in Section 4.1 and the LOOO diagnostics in Section 4.2, **we explicitly withdraw any universal claim that over-the-air software remediation neutralizes vehicle-age compliance decay.** While Tesla's observed Pure-OTA campaigns maintain high completion through oldest-model-year age 7 in the eighth-report sample (and age 12 in the mature latest-snapshot archive), current public federal records lack multi-manufacturer older-vehicle common support to separate wireless delivery technology from single-OEM architecture, owner demographics, or fleet-telematics design. What the fixed eighth-report evidence *does* establish robustly is (i) the complete fixed-horizon descriptive completion profile by channel and manufacturer, (ii) the persistent **$-3.52$ to $-4.03$ pp/yr dealer-software vehicle-age decay gradient** (mirroring physical hardware's $-3.27$ pp/yr decline), and (iii) the sharp **within-OEM Hybrid-OTA 7.01× batch-scale contrast**.

---

## 5. Public Campaign API Measurement Validation Audit and Conditional Hybrid Batch-Scale Contrast

### 5.1 Public Campaign API Measurement Validation Audit

Independent of completion-rate inference, safety researchers and automated VIN-lookup tools frequently extract OTA recall labels directly from NHTSA's public Campaign API (`api.nhtsa.gov/recalls/campaignNumber`, field `overTheAirUpdate`). To validate whether this public endpoint reliably reflects published Part 573 remedy texts, we audited **100% of software and OTA-candidate vehicle campaigns in 2018–2026** ($N = 1,202$) plus a **stratified random sample of 250 physical hardware recalls** (total $N = 1,452$, 100.0% HTTP 200 success, zero errors) and re-verified boundary cases live (`results/d12_v4_live_api_spotcheck.json`). Crucially, **Table 5** and **Figure 4A** separate verbatim Part 573 remedy-text coding (`Pure-OTA`, `Hybrid SW-Choice`, `Hybrid HW-Mixed`, `Dealer-Software`) cleanly from the public API flag.

**Table 5.** *Public NHTSA Campaign API Measurement Validation Audit: Verbatim Part 573 Text Coding vs. Live Public API `overTheAirUpdate` Flag (2018–2026, $N = 1,452$ Queried Campaigns).*

| Verbatim Part 573 Remedy-Text Category | Total (2018–2026) | Pre-Cutoff ($\le$ May 8, 2025) $N$ | Pre-Cutoff API `True` / Queried (%) | Post-Cutoff ($>$ May 8, 2025) $N$ | Post-Cutoff API `True` / Queried (%) |
|---|---:|---:|---:|---:|---:|
| Pure-OTA (Wireless-Only Text) | 61 | 48 | 48/48 (100.0%) | 13 | 0/13 (0.0%) |
| Hybrid SW-Choice (OTA-Capable or Dealer) | 86 | 40 | 38/40 (95.0%) | 46 | 0/46 (0.0%) |
| Hybrid HW-Mixed (OTA + Hardware Required) | 15 | 6 | 3/6 (50.0%) | 9 | 0/9 (0.0%) |
| Dealer Software (No OTA Option in Text) | 984 | 791 | 0/791 (0.0%) | 193 | 0/193 (0.0%) |
| Physical Hardware (Stratified Audit Sample) | 6,821 | 5,744 | 0/260 (0.0%) | 1,077 | 0/46 (0.0%) |

*Notes:* Pre-cutoff covers filings on or before May 8, 2025 (final `overTheAirUpdate = True` campaign: Volvo `25V282000`, 36/36 model-year records `True`); post-cutoff covers filings after May 8, 2025 through November 2026 (beginning May 9, 2025 with Ford `25V315000`, 44/44 records `False` despite explicit OTA remedy text). Zero campaigns returned `overTheAirUpdate = True` without explicit OTA text (`0/984` Dealer Software; `0/250` Physical Hardware).

Three measurement-validation findings emerge:

1. **Near-Perfect Pre-Cutoff Concordance on Pure and Software-Choice OTA:** From 2019 through 2023, the public API flag agreed with verbatim Part 573 text on **54/54 (100.0%)** of text-positive OTA campaigns, and on **31/33 (93.9%)** in 2024—with **zero (0/250) false negatives** on audited physical recalls and zero false positives on dealer-only software. Disaggregating by text structure reveals that before May 8, 2025, public API agreement was **100.0% (48/48)** on wireless-only Pure-OTA and **95.0% (38/40)** on Hybrid SW-Choice, compared with **50.0% (3/6)** on Hybrid HW-Mixed campaigns where hardware inspection or replacement was required alongside an OTA push (e.g., Lucid `24V495000`).
2. **Sharp May 8, 2025 Public-Endpoint Break:** During January 1–May 8, 2025, public API concordance fell to **4/7 (57.1%)**, ending abruptly with Volvo `25V282000` (filed May 8, 2025; live spot-check confirmed **36/36 records `True`**). Starting the very next day with Ford `25V315000` (filed May 9, 2025; live spot-check confirmed **44/44 records `False`** despite verbatim text *"updated by a dealer or through an over-the-air update"*), the public Campaign API returned **`False` on 68/68 (100.0%)** of subsequent text-positive OTA campaigns across 2025 and 2026—including wireless-only Pure-OTA recalls such as Polestar `25V409000` (`2/2 False`) and 2026 Hybrid-OTA recalls such as Ford `26V104000` (`51/51 False`).
3. **Strict Public-API Audit Scope (Not Internal Agency Error):** Contrasting the live public Campaign API count in 2025 (**4 `True`** out of 38 text-coded OTA recalls) against NHTSA's separate ***2025 Annual Recalls Report*** (NHTSA 2026b), which internally tallied **33 partially or fully OTA-remedied recalls in 2025**, demonstrates that NHTSA continued monitoring OTA recalls internally under its own counting criteria (which exclude text-offered OTA options never actually deployed). We therefore interpret this finding strictly as a **public Campaign API measurement validation issue**: researchers using `api.nhtsa.gov` after May 8, 2025 must not treat `overTheAirUpdate` as a standalone OTA label, and should instead code verbatim Part 573 remedy texts transparently while using the public API flag strictly as an external pre-cutoff validation benchmark. Note that none of our fixed eighth-report completion results depend on the post-cutoff API flag.

### 5.2 Retained Within-OEM Conditional Hybrid-OTA Batch-Scale Contrast

Alongside the measurement audit, one structural operational feature of the 2018–2026 software recall census is sharply identified across manufacturers: **within OTA-capable OEMs, Hybrid-OTA campaigns are substantially larger in batch scale than dealership-only software recalls.** **Table 6** and **Figure 4B** summarize this conditional contrast alongside distinct unconditional OEM-level first-OTA adoption event studies (full robustness ladder in Online Appendix Section S3).

**Table 6.** *Retained Within-OEM Conditional Batch-Scale Contrast vs. Unconditional OEM First-OTA Adoption Event Studies (2015–2026).*

| Estimand & Specification (Outcome: $\log(1 + \text{Affected Vehicles})$) | $N$ | OEMs | Coef. | SE (CR1) | $t_{\text{CR1}}$ | $p_{\text{WCB}}$ / $p_t$ | Implied Scale Ratio |
|---|---:|---:|---:|---:|---:|---:|---:|
| Conditional: Hybrid-OTA vs. Dealer-SW (Main FE, 2018–2026) | 736 | 32 | +1.947 | 0.366 | +5.32 | 0.006 | 7.01× |
| Conditional: Pure-OTA vs. Dealer-SW (Main FE, 2018–2026) | 736 | 32 | +1.084 | 0.791 | +1.37 | 0.233 | Null |
| Conditional: Official API OTA (Active Era 2018–2024) | 495 | 27 | +1.887 | 0.671 | +2.81 | 0.039 | 6.60× |
| Conditional: Hybrid-OTA (Saturated OEM $\times$ Year FE) | 736 | 32 | +2.059 | 0.464 | +4.44 | 0.014 | 7.84× |
| Conditional: Hybrid-OTA (Make $\times$ Model FE) | 736 | 32 | +2.213 | 0.567 | +3.90 | 0.005 | 9.14× |
| Conditional: Hybrid-OTA (Excl. Tesla & Ford) | 546 | 30 | +1.525 | 0.439 | +3.47 | 0.012 | 4.60× |
| Conditional: Hybrid SW-Choice Only (No Hardware Clause) | 736 | 32 | +2.006 | 0.326 | +6.15 | 0.006 | 7.44× |
| Unconditional: First-OTA OEM ITT (TWFE, 2015–2026) | 1,239 | 68 | +0.176 | 0.298 | +0.59 | 0.579 | Null |
| Unconditional: First-OTA OEM ITT (Sun–Abraham 2021 IW, 7 cohorts) | 1,233 | 67 | −0.532 | 0.732 | −0.73 | 0.470 ($p_t$) | Null |

*Notes:* Conditional specifications include Manufacturer, Filing-Year, Oldest-Model-Year, and Component fixed effects (unless replaced by OEM $\times$ Year or Make $\times$ Model FE) on OTA-capable OEMs' 2018–2026 software recalls. Unconditional ITT models pool *all* 2015–2026 software recalls (OTA + Dealer Software) across adopting and never-OTA OEMs (pre-trend Wald $p = 0.424$ for TWFE; $p = 0.775$ for saturated Sun–Abraham 2021 IW across 7 cohorts excluding partial-year cohort 2026). Conditional and unconditional estimates identify distinct estimands; no percentage selection-share decomposition is computed.

Conditional on observing a software recall within an OTA-capable automaker, **Hybrid-OTA campaigns are 7.01× larger** (**+1.947 log points**, $t = 5.32$, $p_{\text{WCB}} = 0.006$; Official API OTA active era 2018–2024 **+1.887**, $p_{\text{WCB}} = 0.039$) than dealer-remedied software recalls, remaining highly stable under OEM $\times$ Year FE, Make $\times$ Model FE, excluding Tesla and Ford, and restricting strictly to pure software-choice hybrids. By contrast, **Pure-OTA** exhibits no significant within-OEM scale premium (**+1.084**, $p_{\text{WCB}} = 0.233$), and **unconditional OEM-level first-OTA adoption ITT** models pooling all 2015–2026 software recalls yield clean parallel pre-trends and statistically null post-adoption shifts under both TWFE (**+0.176**, $p_{\text{WCB}} = 0.579$) and saturated Sun–Abraham (2021) interaction-weighted estimation (**−0.532**, $p_t = 0.470$; Callaway and Sant'Anna 2021; Roth et al. 2023; unconditional Software $\times$ Modern SDV $\text{MY} \ge 2021$ DiD **+0.262**, $p_{\text{WCB}} = 0.094$). Because conditional campaign-level sorting and unconditional OEM adoption are distinct estimands, we report each transparently without claiming an unidentified percentage decomposition: the contrast is qualitatively consistent with legacy manufacturers incurring fixed OTA packaging and validation overhead ($F_{\text{OTA}} > 0$) and preferentially routing high-volume campaigns into hybrid wireless delivery rather than experiencing a uniform fleet-wide jump in recall size upon adopting OTA capability.

<!-- FIGURE:fig4_v4_api_audit_and_hybrid_scale.png -->

---

## 6. Discussion: Operational Mechanism Boundary, Causal Identification Roadmap, and Dataset Specification

### 6.1 Operational Mechanism Boundary and Data Roadmap for Causal Delivery-Channel Research

Distinguishing what public federal safety records *can* establish (fixed-horizon completion monitoring, sample-flow accounting, dealer-channel vehicle-age decay, conditional batch-scale sorting, and public-API measurement audits) from what requires deeper operational microdata clarifies the exact boundary between descriptive safety-monitoring research and causal operations-management identification:

1. **Independent Dual-Coder Part 573 and Owner-Letter Classification:** While our automated text classifier achieves 100.0% pre-cutoff recall against the public API flag and cleanly separates Pure-OTA, Hybrid SW-Choice, Hybrid HW-Mixed, and Dealer Software, definitive measurement of remedy intent versus execution in hybrid campaigns requires **two independent human coders** annotating full Part 573 Defect Information Reports and 49 CFR Part 577 owner notification letters to separate *(a) OTA-capable eligibility*, *(b) actual wireless OTA deployment*, and *(c) physical hardware-required subsets*, with inter-rater reliability ($\kappa$) audited independently of the public API endpoint.
2. **Multi-Quarter Campaign Trajectories and Phased Remedy-Availability Dates:** Cross-sectional eighth-report proportions cannot measure repair velocity, hazard decay, or time-to-remedy curves. Validating repair-speed metrics requires **longitudinal Q1–Q8 quarterly report panels per campaign** paired with explicit remedy-availability launch dates and phase-specific notification waves (addressing interim vs. final notices under 49 CFR § 577.5), plus additional annual eighth-report vintages (`2026+`) as non-Tesla SDV fleets age beyond 5 years.
3. **Quasi-Experimental Identification of Delivery-Channel Mechanisms:** To identify the causal operational effect of wireless OTA delivery on dealership service capacity, actual installation timing, and unremedied vehicle-days (e.g., for *Manufacturing & Service Operations Management*, *Production and Operations Management*, or *Management Science*), future studies require **within-defect treatment-assignment boundaries**—specifically:
   - *Pre-specified hardware-eligibility cutoffs* (e.g., identical software defect affecting adjacent build weeks or model trims where only vehicles equipped with a specific telematics/gateway module qualify for OTA while otherwise comparable vehicles require dealer flashing), or
   - *Risk-orthogonal phased OTA rollout waves* staggered by VIN block or geography.
   Credible execution of either quasi-experimental design requires checking balance across the boundary on model composition, defect severity, and prior baseline completion rates, and observing **actual OTA installation timestamps, dealership service-bay visits, and unremedied vehicle-days**. Crucially, wherever an eligibility boundary simultaneously alters the underlying defect mechanism or the substance of the software/hardware remedy, causal channel attribution must be abandoned.

### 6.2 Regulatory Monitoring and Public Data Infrastructure Implications

Our audit yields three immediate, actionable improvements for NHTSA and U.S. DOT public safety infrastructure:

1. **Synchronizing Public Campaign API Serialization:** Restoring backend synchronization between internal NHTSA recall tracking (33 OTA recalls in the *2025 Annual Recalls Report*) and the public `api.nhtsa.gov/recalls/campaignNumber` `overTheAirUpdate` field—which has emitted `False` on 68/68 post-May 8, 2025 OTA recalls—would immediately restore reliability for third-party VIN tools, academic safety monitors, and fleet compliance platforms.
2. **Publishing Machine-Readable Multi-Quarter Fixed-Horizon Tables:** Releasing the annual eighth-report completion lists (and underlying Q1–Q8 trajectories) as structured CSV/JSON tables alongside static PDFs—with explicit flags for 100% early-completed campaigns, denominator amendments (`22V867`, `23V413`), and multi-year duplicate revisions (`22V315`, `22V743`)—would eliminate transcription friction and horizon mixing in `6axg-epim`.
3. **Channel-Disaggregated Reporting Under 49 CFR § 573.7:** Recording the share of Hybrid-OTA vehicles remedied wirelessly versus at franchised dealerships alongside § 573.7(b)(5) unreachable-vehicle counts would allow regulators to monitor whether hybrid compliance tails stem from connectivity opt-outs, expired cellular subscriptions, or dealership service-bay bottlenecks.

### 6.3 Machine-Readable Replication Dataset Architecture

To support transparent reuse by safety researchers and operations scholars, the replication package publishes a clean, zero-NaN campaign-level fixed-horizon dataset (`data_processed/d12_v4_eighth_report_analysis_panel.csv`, $N = 1,533$ rows, 31 harmonized fields, SHA-256 `c6d46ef262a21ada...`) paired with six structured summary tables (`table_v4_sample_flow.csv`, `table_v4_eighth_report_completion.csv`, `table_channel_oem_age_support.csv`, `table_v4_vehicle_age_sensitivity.csv`, `table_v4_looo_sensitivity.csv`, and `table_v4_text_coding_vs_api.csv`). Online Appendix Section S5 provides the complete variable codebook, inclusion rules, and cryptographic verification receipts.

---

## 7. Conclusion

Anchoring U.S. automotive recall completion analysis on NHTSA's fixed eighth-quarter reporting horizon (1,533 uniquely dated campaigns across 2024–2025, completely reconciled to Part 573 filings and the statutory 2022–2023 owner-notification cohort) separates well-identified empirical facts from unsupported generalizations. First, fixed eighth-report completion proportions are highest descriptively in Pure-OTA (98.32% mean), followed by Hybrid-OTA (89.56%), Dealer Software (82.06%), and Physical Hardware (67.26%), while within OEMs, Hybrid-OTA campaigns are robustly **7.01× larger** ($p_{\text{WCB}} = 0.006$) than dealer-remedied software recalls despite null unconditional OEM first-OTA adoption shifts. Second, vehicle-age compliance decay in dealership channels is steep and rock-solid across every sensitivity check and all 18 Leave-One-OEM-Out exclusions (**−3.52 to −4.03 pp/yr**, all $p_{\text{WCB}} \le 0.003$). Third, because Tesla accounts for **11/15 Pure-OTA recalls and 99.17% of Pure-OTA vehicles** (with zero eighth-report Dealer-Software counterfactuals) while non-Tesla Pure-OTA campaigns occur strictly at oldest-model-year ages 0–1 years, the nominal Pure-OTA $\times$ Age interaction collapses without Tesla (**+1.59 pp/yr**, $p_{\text{WCB}} = 0.553$) and inside same-OEM common-support subsamples—requiring explicit withdrawal of any universal claim that OTA neutralizes vehicle-age decay. Finally, our public-API validation audit documents a sharp post-May 8, 2025 `overTheAirUpdate` serialization break (`0/68` `True`), underscoring the necessity of independent text verification and structured fixed-horizon reporting in federal safety monitoring.

---

## Data and Code Availability

All frozen public inputs, reconciliation scripts (`scripts/01`–`scripts/11`), econometric JSON receipts (`results/d12_v4_fixed_report_audit.json`, `results/d12_v4_live_api_spotcheck.json`, `results/d12_econometric_results.json`, `results/api_reconciliation_audit.json`), machine-readable dataset files (`data_processed/d12_v4_eighth_report_analysis_panel.csv`, `tables/table_channel_oem_age_support.csv`, `tables/table_v4_*.csv`), automated verification tests (`tests/test_d12_boost.py`), and cryptographic checksums (`SHA256SUMS.json`) are archived in the project replication package. No proprietary VIN or OEM telematics records were used.

---

## References

1. Arora, A., Caulkins, J., Telang, R. (2006). Research Note—Sell First, Fix Later: Impact of Patching on Software Quality. *Management Science*, 52(3), 465-471. https://doi.org/10.1287/mnsc.1050.0440
2. August, T., Tunca, T. (2006). Network Software Security and User Incentives. *Management Science*, 52(11), 1703-1720. https://doi.org/10.1287/mnsc.1060.0568
3. Bae, Y., Benítez‐Silva, H. (2011). Do vehicle recalls reduce the number of accidents? The case of the U.S. car market. *Journal of Policy Analysis and Management*, 30(4), 821-862. https://doi.org/10.1002/pam.20600
4. Ball, G., Shah, R., Donohue, K. (2018). The decision to recall: A behavioral investigation in the medical device industry. *Journal of Operations Management*, 62(1), 1-15. https://doi.org/10.1016/j.jom.2018.07.003
5. Barber, B., Darrough, M. (1996). Product Reliability and Firm Value: The Experience of American and Japanese Automakers, 1973-1992. *Journal of Political Economy*, 104(5), 1084-1099. https://doi.org/10.1086/262053
6. Callaway, B., Sant’Anna, P. (2021). Difference-in-Differences with multiple time periods. *Journal of Econometrics*, 225(2), 200-230. https://doi.org/10.1016/j.jeconom.2020.12.001
7. Cameron, A., Gelbach, J., Miller, D. (2008). Bootstrap-Based Improvements for Inference with Clustered Errors. *Review of Economics and Statistics*, 90(3), 414-427. https://doi.org/10.1162/rest.90.3.414
8. Cavusoglu, H., Cavusoglu, H., Zhang, J. (2008). Security Patch Management: Share the Burden or Share the Damage?. *Management Science*, 54(4), 657-670. https://doi.org/10.1287/mnsc.1070.0794
9. Colin Cameron, A., Miller, D. (2015). A Practitioner’s Guide to Cluster-Robust Inference. *Journal of Human Resources*, 50(2), 317-372. https://doi.org/10.3368/jhr.50.2.317
10. Eilert, M., Jayachandran, S., Kalaignanam, K., Swartz, T. (2017). Does it Pay to Recall your Product Early? An Empirical Investigation in the Automobile Industry. *Journal of Marketing*, 81(3), 111-129. https://doi.org/10.1509/jm.15.0074
11. Haunschild, P., Rhee, M. (2004). The Role of Volition in Organizational Learning: The Case of Automotive Product Recalls. *Management Science*, 50(11), 1545-1560. https://doi.org/10.1287/mnsc.1040.0219
12. Hora, M., Bapuji, H., Roth, A. (2011). Safety hazard and time to recall: The role of recall strategy, product defect type, and supply chain player in the U.S. toy industry. *Journal of Operations Management*, 29(7-8), 766-777. https://doi.org/10.1016/j.jom.2011.06.006
13. Jarrell, G., Peltzman, S. (1985). The Impact of Product Recalls on the Wealth of Sellers. *Journal of Political Economy*, 93(3), 512-536. https://doi.org/10.1086/261313
14. Kalaignanam, K., Kushwaha, T., Eilert, M. (2013). The Impact of Product Recalls on Future Product Reliability and Future Accidents: Evidence from the Automobile Industry. *Journal of Marketing*, 77(2), 41-57. https://doi.org/10.1509/jm.11.0356
15. MacCormack, A., Rusnak, J., Baldwin, C. (2006). Exploring the Structure of Complex Software Designs: An Empirical Study of Open Source and Proprietary Code. *Management Science*, 52(7), 1015-1030. https://doi.org/10.1287/mnsc.1060.0552
16. MacKinnon, J., Webb, M. (2017 [online 2016]). Wild Bootstrap Inference for Wildly Different Cluster Sizes. *Journal of Applied Econometrics*, 32(2), 233-254. https://doi.org/10.1002/jae.2508
17. Pagiavlas, S., Kalaignanam, K., Gill, M., Bliese, P. (2022 [online 2021]). Regulating Product Recall Compliance in the Digital Age: Evidence from the “Safe Cars Save Lives” Campaign. *Journal of Marketing*, 86(5), 135-152. https://doi.org/10.1177/00222429211023016
18. Ramdas, K., Randall, T. (2008). Does Component Sharing Help or Hurt Reliability? An Empirical Study in the Automotive Industry. *Management Science*, 54(5), 922-938. https://doi.org/10.1287/mnsc.1070.0791
19. Roth, J., Sant’Anna, P., Bilinski, A., Poe, J. (2023). What’s trending in difference-in-differences? A synthesis of the recent econometrics literature. *Journal of Econometrics*, 235(2), 2218-2244. https://doi.org/10.1016/j.jeconom.2023.03.008
20. Rupp, N., Taylor, C. (2002). Who Initiates Recalls and Who Cares? Evidence from the Automobile Industry. *The Journal of Industrial Economics*, 50(2), 123-149. https://doi.org/10.1111/1467-6451.00171
21. Shah, R., Ball, G., Netessine, S. (2017). Plant Operations and Product Recalls in the Automotive Industry: An Empirical Investigation. *Management Science*, 63(8), 2439-2459. https://doi.org/10.1287/mnsc.2016.2456
22. Sun, L., Abraham, S. (2021). Estimating dynamic treatment effects in event studies with heterogeneous treatment effects. *Journal of Econometrics*, 225(2), 175-199. https://doi.org/10.1016/j.jeconom.2020.09.006
23. Thirumalai, S., Sinha, K. (2011). Product Recalls in the Medical Device Industry: An Empirical Exploration of the Sources and Financial Consequences. *Management Science*, 57(2), 376-392. https://doi.org/10.1287/mnsc.1100.1267
24. National Highway Traffic Safety Administration (NHTSA), Office of Defects Investigation. (2025). *Vehicle Safety Recall Completion Rates (Report No. DOT HS 813 687)*. U.S. Department of Transportation, National Highway Traffic Safety Administration, January 2025. https://rosap.ntl.bts.gov/view/dot/79374
25. National Highway Traffic Safety Administration (NHTSA). (2025). *2024 Annual List of Recall Completion Rates (Eighth-Quarter Completion Report)*. U.S. Department of Transportation, National Highway Traffic Safety Administration, January 2025. https://www.nhtsa.gov/sites/nhtsa.gov/files/2025-01/2024-recall-completion-rates.pdf
26. National Highway Traffic Safety Administration (NHTSA). (2026a). *2025 Annual List of Recall Completion Rates (Eighth-Quarter Completion Report)*. U.S. Department of Transportation, National Highway Traffic Safety Administration, January 2026. https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-01/2025-recall-completion-rates.pdf
27. National Highway Traffic Safety Administration (NHTSA). (2026b). *2025 Annual Recalls Report*. U.S. Department of Transportation, National Highway Traffic Safety Administration, March 2026. https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-03/2025-annual-recalls-report.pdf
28. Office of the Federal Register (NARA) / U.S. Department of Transportation. (2026). *49 CFR § 573.7 — Quarterly Reports (Defect and Noncompliance Responsibility and Reports)*. Electronic Code of Federal Regulations, Title 49, Subtitle B, Chapter V, Part 573. https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-573/section-573.7
29. U.S. Department of Transportation (DOT) / NHTSA. (2026). *Recalls Data (Socrata Open Data Registry, Dataset ID 6axg-epim)*. U.S. Department of Transportation DataHub. https://datahub.transportation.gov/resource/6axg-epim.csv
