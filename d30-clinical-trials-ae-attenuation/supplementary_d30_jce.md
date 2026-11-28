# Supplementary Appendix: Geographic Site Mix and Registered Non-Serious Adverse Events in Multiregional Drug Trials

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

This Supplementary Appendix documents secondary sensitivity checks, therapeutic-area heterogeneity, site-to-patient accrual calibration bounds, post-2017 temporal patterns, 2022–2025 all-registered trial-site footprints, exploratory post-approval FDA/FAERS linkages, the EMA Policy 0070 CSR validation extraction template, and cryptographic data-snapshot provenance accompanying the main manuscript (*Journal of Clinical Epidemiology*). All numeric values are verified directly against machine-readable JSON receipts (`results/d30_econometrics_results.json`, `results/08_reporting_sensitivity.json`, `results/d30_gate2_openfda_results.json`, and `data/processed/meddra_soc_abs_summary.json`).

---

## Appendix S1. Extended Sensitivity Analyses, Therapeutic-Area Heterogeneity, and Simplex-Valid Site-to-Patient Accrual Calibration

**Table S1** summarizes extended sensitivity checks across reporting thresholds (`5%` and `0%`), `SYSTEMATIC_ASSESSMENT` checklist controls and interactions, inclusion of `483` terminated trials (with explicit early-termination selection test), non-placebo active-comparator out-of-sample replication, enrollment-weighted WLS, and leave-one-country-out / leave-one-sponsor-out checks, all scaled strictly per `+10 pp` site share. **Figure S1** (`figures/figS1_therapeutic_areas_and_accrual_bounds.png`) displays therapeutic-area consistency (9/9 clinical domains negative, 7/9 `p < 0.05`) and simplex-preserving patient-share calibration across accrual velocity ratios `w ∈ [0.5, 3.0]`.

**Table S1. Extended Protocol, Survivorship, Out-of-Sample, and Leave-One-Out Sensitivity Checks (Per `+10 pp` Site Share)**

| Sensitivity Check | N | Regressor | Placebo / Trial AE per `+10 pp` [95% CI] | p-value | Active AE per `+10 pp` [95% CI] | p-value |
| :--- | :---: | :--- | :---: | :---: | :---: | :---: |
| Strict `freq_thr == 5%` Only (P3 `Drug × Sp`) | 938 | `eu_east_sh` | **−2.86 pp** `[−4.27, −1.46]` | `1.06e-4` | **−3.20 pp** `[−4.51, −1.89]` | `4.96e-6` |
| Strict `freq_thr == 0%` Only (P2+P3 `TA` FE) | 217 | `ee_sh` | −1.72 pp `[−3.74, +0.30]` | `0.0944` | −1.56 pp `[−3.79, +0.66]` | `0.166` |
| Strict `freq_thr == 0%` Only (P2+P3 `Sponsor` FE) | 159 | `ee_sh` | −3.37 pp `[−8.26, +1.51]` | `0.169` | −3.19 pp `[−8.37, +1.99]` | `0.218` |
| + `SYSTEMATIC_ASSESSMENT` Control (P2+P3) | 1,685 | `eu_east_sh` | **−2.52 pp** `[−3.43, −1.61]` | `1.74e-7` | **−2.68 pp** `[−3.72, −1.64]` | `1.05e-6` |
| `ee_sh × all_systematic` Interaction (P2+P3) | 1,685 | `ee_x_sys` | −0.41 pp `[−2.10, +1.27]` | `0.630` | −0.37 pp `[−1.65, +0.92]` | `0.574` |
| All-Status incl. `483` Terminated (P2+P3) | 2,188 | `eu_east_sh` | **−2.96 pp** `[−4.09, −1.84]` | `5.30e-7` | **−3.08 pp** `[−4.10, −2.06]` | `1.22e-8` |
| Early Termination Selection (`is_terminated`) | 2,188 | `eu_east_sh` | −1.19 pp `[−3.09, +0.72]` | `0.222` | — | — |
| Non-Placebo Active-Comparator OOS (P2+P3) | 1,276 | `eu_east_sh` | **−2.50 pp** `[−3.89, −1.12]` | `5.09e-4` | *(mort: −0.74 pp)* | `(0.474)` |
| Enrollment-Weighted WLS (P3 `Drug × Sp`) | 1,282 | `eu_east_sh` | **−3.18 pp** `[−5.36, −1.00]` | `0.00450` | **−3.11 pp** `[−4.98, −1.24]` | `0.00132` |
| Leave-One-Country-Out Range (7 EE countries) | 1,764 | `ee_minus_c` | −1.82 to −2.43 pp | `≤ 0.00215` | −2.23 to −2.91 pp | `≤ 4.86e-5` |
| Leave-One-Sponsor-Out Range (Top 5 pharma) | ~1,650 | `ee_sh` | −1.76 to −2.14 pp | `≤ 8.57e-4` | −2.16 to −2.50 pp | `≤ 4.37e-5` |

*Source:* `results/d30_econometrics_results.json` and `tables/table2_sensitivity_subsamples.csv`.

Because ClinicalTrials.gov enumerates sites rather than country-level patient enrollment, **Table S2** calibrates site-share slopes to implied patient-share slopes via simplex-preserving rescaling $p_{i,\text{EE}}(w) = w s_{i,\text{EE}} / [w s_{i,\text{EE}} + (1 - s_{i,\text{EE}})]$ ($\sum_r p_{ir}(w) \equiv 1.000$) alongside degree-of-freedom-corrected classical errors-in-variables (EIV) bounds (`df_resid = 1,276`, within-program SD `0.1098`). Direct within-program accrual-velocity estimation (`log(enrollment / n_sites)`) estimates $\hat{w}_{\text{EE}} = 1.354\times$ U.S. (`EU-East: 1.451×`, `p = 0.00265`; `Non-EU RU/UA: 1.170×`, `p = 0.503`).

**Table S2. Simplex-Valid Site-to-Patient Accrual Calibration and EIV Attenuation Bounds (`P2+P3 Drug × Sponsor FE`, `N = 1,764`, Per `+10 pp` Share)**

| Calibration Parameter | Placebo per `+10 pp` (SE) | p-value | Active per `+10 pp` (SE) | p-value | Notes |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Simplex Ratio `w = 0.50` | −2.62 pp (0.67) | `1.41e-4` | −3.07 pp (0.63) | `2.43e-6` | Lower EE per-site accrual |
| Simplex Ratio `w = 0.75` | −2.30 pp (0.58) | `9.86e-5` | −2.70 pp (0.53) | `1.07e-6` | Moderately lower accrual |
| Unadjusted Site Share (`w = 1.00`) | −2.09 pp (0.53) | `1.03e-4` | −2.47 pp (0.49) | `1.47e-6` | Baseline OLS (`ee_sh`) |
| **Empirical Twin-Trial `ŵ_EE = 1.354`** | **−1.90 pp** (0.49) | **`1.33e-4`** | **−2.24 pp** (0.47) | **`3.68e-6`** | Estimated from `log(enroll/sites)` |
| High-Velocity Bound `w = 2.00` | −1.70 pp (0.45) | `2.29e-4` | −2.00 pp (0.45) | `1.74e-5` | 2× patients/site in EE |
| Extreme Bound `w = 3.00` | −1.53 pp (0.43) | `4.45e-4` | −1.80 pp (0.45) | `8.16e-5` | 3× patients/site in EE |
| Classical EIV `σ_η = 0.02` (`λ = 0.967`) | −2.17 pp | — | −2.55 pp | — | Mild random site/patient noise |
| Classical EIV `σ_η = 0.04` (`λ = 0.867`) | −2.42 pp | — | −2.84 pp | — | Moderate random noise |
| Classical EIV `σ_η = 0.06` (`λ = 0.701`) | −2.99 pp | — | −3.52 pp | — | Substantial random noise |

*Source:* `results/d30_econometrics_results.json` and `tables/table4_accrual_calibration_bounds.csv`.

---

## Appendix S2. Post-2017 Temporal Patterns and Concurrent Regulatory Regimes (Descriptive Secondary Analysis)

Two major regulatory changes took effect almost simultaneously around 2017: the U.S. FDAAA Final Rule (`42 CFR Part 11`, effective January 18, 2017; Zarin et al., 2016), which coincided with a `1.59×` rise in `0%`-threshold submissions (`6.1% -> 9.7%`), and the ICH E6(R2) risk-based monitoring addendum (Step 4 November 2016; EMA effective June 2017) alongside ICH E17 MRCT guidelines (Step 4 November 2017; EMA effective June 2018; Matsushima et al., 2024). **Because these regulatory timelines overlap closely with broader post-2017 shifts in trial monitoring, EDC adoption, and therapeutic mix, observational period interactions cannot causally attribute temporal attenuation to any single regulation (such as ICH E17 or ICH E6(R2)).**

**Table S3** and **Figure S2** (`figures/figS2_post2017_temporal_overlap.png`) document these descriptive temporal patterns strictly per `+10 pp` site share. Within pooled Phase 2+3 `drug × sponsor` FE (`N = 1,764`), pre-2017 EU-East slopes (`-3.05 / -3.13 pp`, `p <= 5.48e-6`) showed non-significant transition shifts in `2017–2019` (`+1.42 / +0.67 pp`, `p >= 0.218`) and positive offsetting shifts in `2020–2024` (`+3.57 pp, p = 0.0157, p_WCB = 0.030` placebo; `+4.01 pp, p = 0.0185`, borderline `p_WCB = 0.051` active). Joint horse-race models including `eu × post_ich_2017`, `eu × post_fdaaa_2017`, and `eu × is_freq0` simultaneously are individually imprecise (`p = 0.528`, `0.126`, `0.909`), confirming that overlapping 2017 regimes are not individually separable. In the separate `2020–2024` cross-sectional window (`N = 441`, TA FE — a cross-sectional slope rather than a within-program change), EU-East slopes were `-1.17 pp (p = 0.198)` placebo and `-0.48 pp (p = 0.638)` active, whereas Non-EU Eastern Europe/RU-UA retained steep negative cross-sectional slopes (`-4.94 pp, 95% CI [-7.40, -2.47], p = 1.13e-4` placebo; `-4.70 pp, p = 2.19e-4` active).

**Table S3. Descriptive Post-2017 Period Interactions and Joint Overlapping-Regime Specification (`P2+P3 Drug × Sponsor FE`, `N = 1,764`, Per `+10 pp` Share)**

| Model & Interaction Term | Placebo AE (`ctrl_oth`) (SE) | p-value | Active AE (`act_oth`) (SE) | p-value | Risk Diff (`oth_rd`) (SE) | p-value |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| 3-Era Model: `eu_east_sh` (Pre-2017 Baseline) | **−3.05 pp** (0.65) | `5.48e-6` | **−3.13 pp** (0.53) | `2.29e-8` | −0.09 pp (0.28) | `0.756` |
| 3-Era Model: `eu_east_sh × 2017–2019` | +1.42 pp (1.15) | `0.218` | +0.67 pp (1.22) | `0.582` | −0.75 pp (0.74) | `0.310` |
| 3-Era Model: `eu_east_sh × 2020–2024` | **+3.57 pp** (1.46) | `0.0157` *(WCB 0.030)* | **+4.01 pp** (1.69) | `0.0185` *(WCB 0.051)* | +0.44 pp (0.72) | `0.540` |
| 3-Era Model: `ru_ua_sh × 2020–2024` (Non-EU) | −1.41 pp (1.99) | `0.481` | +0.29 pp (1.65) | `0.863` | +1.69 pp (1.73) | `0.330` |
| Joint Overlap: `eu_east_sh × is_freq0` | −0.19 pp (1.69) | `0.909` | −0.24 pp (1.48) | `0.870` | −0.05 pp (1.06) | `0.963` |
| Joint Overlap: `eu_east_sh × post_fdaaa_2017` | +1.70 pp (1.10) | `0.126` | +0.88 pp (1.07) | `0.414` | −0.82 pp (0.83) | `0.327` |
| Joint Overlap: `eu_east_sh × post_ich_2017` | +1.01 pp (1.60) | `0.528` | +1.44 pp (1.48) | `0.332` | +0.43 pp (0.77) | `0.575` |

*Source:* `results/d30_econometrics_results.json` and `tables/table3_post2017_fdaaa_decomposition.csv`.

---

## Appendix S3. 2022–2025 Geopolitical Trial-Site Footprints: All-Registered Cohort (`N = 20,649`) vs. Results-Posted Subsample

Analyzing post-2022 trial footprints solely inside results-posted studies introduces severe right-censoring (results-posted Russia/Ukraine participation dropped from `46.98%` [`187/398` in 2019] to `0.00%` [`0/43` short trials in 2024]). To eliminate results-posting selection, we separately harvested **all `20,649` registered Phase 2/3 industry interventional trials started `2017–2025`** regardless of results status (`data/processed/ctgov_all_registered_war_2017_2025.parquet`), yielding **`N = 6,011` uncensored MRCTs** (`4,747` randomized; `611–789` MRCTs annually through `2025`).

**Table S4** and **Figure S3** (`figures/figS3_war2022_all_registered_footprints.png`) summarize participation trajectories and within-sponsor reallocation. In the uncensored all-registered cohort, trials listing `>= 1` Russia or Ukraine site dropped from **`41.86%` (`270/645`) in 2019** to **`3.76%` (`23/611`) in 2023** and **`6.10%` (`43/705`) in 2025**—driven by complete exit from Russia (`34.11% -> 0.00% [0/705]` in 2025) paired with partial Ukrainian site persistence (`22.33% -> 2.95% -> 6.10%`). Within-sponsor period regressions (`N = 5,362`) show Russia/Ukraine share fell **`-3.58 pp`** (`p = 2.95e-29`) while Latin America (`+1.48 pp, p = 1.09e-4`) and Emerging Asia (`+1.37 pp, p = 3.18e-4`) rose across periods and U.S. share did not shift significantly (`+0.36 pp, p = 0.633`). Crucially, in strictly out-of-sample pre-war sponsor-exposure DiDs (`2017–2019` exposure applied to disjoint `2020–2025`, passing a fake-2020 pre-war placebo at `p = 0.125 / 0.264`), the **U.S. reallocation coefficient is statistically null** (`+0.328, 95% CI [-0.084, +0.739], p = 0.117`; randomized MRCTs `+0.354, p = 0.175`; alt `2017–18 -> 2019–25` `+0.146, p = 0.480`), and all alternative regional destinations are statistically imprecise. Thus, **uncensored registry data document a sharp exit from Russian trial sites but do not identify a statistically significant U.S. reshoring shift or uniquely resolve destination regions**.

**Table S4. All-Registered War Cohort (`2017–2025`, `N = 6,011` MRCTs) vs. Results-Posted Subsample**

| Panel A: Annual All-Registered MRCTs | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| All-Registered MRCTs (`N`) | 645 | 688 | 645 | 651 | 789 | 647 | 611 | 630 | 705 |
| `%` With Posted Results | 86.98% | 81.40% | 75.97% | 72.35% | 59.57% | 42.81% | 23.24% | 8.25% | 0.28% |
| `%` With `≥1` RU or UA Site (`k`) | 37.98% (245) | 39.10% (269) | **41.86% (270)** | 37.02% (241) | 28.39% (224) | 5.41% (35) | 3.76% (23) | 4.29% (27) | **6.10% (43)** |
| `%` With `≥1` Russia Site (`k`) | 32.71% (211) | 34.59% (238) | **34.11% (220)** | 32.41% (211) | 21.93% (173) | 3.09% (20) | 0.98% (6) | 0.79% (5) | **0.00% (0)** |
| `%` With `≥1` Ukraine Site (`k`) | 19.22% (124) | 18.90% (130) | **22.33% (144)** | 19.35% (126) | 15.08% (119) | 3.71% (24) | 2.95% (18) | 3.65% (23) | **6.10% (43)** |

| Panel B: Site-Share Models | N | RU/UA (`ru_ua_strict_sh`) | United States (`us_sh`) | Latin America (`latam_sh`) | Emerging Asia (`asia_sh`) | EU-East (`eu_east_sh`) |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: |
| All-Reg Within-Sponsor Shift (`2017–2025`, pp) | 5,362 | **−3.58 pp** (`2.95e-29`) | +0.36 pp (`0.633`) | **+1.48 pp** (`1.09e-4`) | **+1.37 pp** (`3.18e-4`) | −0.24 pp (`0.628`) |
| All-Reg OOS DiD (`2017–19 → 2020–25`, All) | 2,596 | **−0.226** (`0.0107`) | +0.328 `[−0.084, +0.739]` (`0.117`) | −0.069 (`0.531`) | +0.190 (`0.238`) | −0.198 (`0.099`) |
| All-Reg OOS DiD (`2017–19 → 2020–25`, Rand.) | 2,001 | **−0.256** (`0.0163`) | +0.354 `[−0.161, +0.870]` (`0.175`) | +0.087 (`0.459`) | +0.208 (`0.274`) | −0.217 (`0.155`) |
| All-Reg OOS DiD Alt (`2017–18 → 2019–25`) | 2,823 | **−0.362** (`0.00144`) | +0.146 `[−0.263, +0.555]` (`0.480`) | −0.129 (`0.207`) | +0.174 (`0.118`) | −0.116 (`0.423`) |
| Results-Posted OOS DiD (`2015–19 → 2020–24`, Cens.) | 834 | **−0.531** (`0.00565`) | +1.083 `[−0.019, +2.185]` (`0.0541`) | +0.071 (`0.877`) | +0.110 (`0.702`) | −0.021 (`0.959`) |

*Source:* `data/processed/ctgov_all_registered_war_2017_2025.parquet`, `results/d30_econometrics_results.json`, and `tables/table4b_all_registered_war_2017_2025.csv`.

---

## Appendix S4. Exploratory Post-Approval FDA Labeling Supplements and FAERS Spontaneous-Reporting Audit (`N = 229` Drugs)

Linking `697` canonical Phase 3 molecules to live `openFDA` endpoints (`Drugs@FDA` originator NDA/BLAs including FDA 4-letter biologic suffixes, `drug/label`, and Primary-Suspect `FAERS`) matched `402` originator drugs, of which **`N = 229`** had pre-approval Phase 3 MRCTs (`start_date <= orig_approval_date`, approved `2005–2024`; **Table S5** and **Figure S4**, `figures/figS4_exploratory_openfda_faers.png`).

**Critical Regulatory Caveat:** Per the U.S. FDA's official FAERS Limitations Notice (`https://www.fda.gov/media/136729/download`), FAERS is a passive spontaneous reporting system lacking exposed-patient denominators, subject to under-reporting and stimulated reporting, and **cannot estimate adverse-event incidence rates or comparative drug safety risks**. Similarly, post-approval labeling revisions lack comparable exposure denominators and are statistically imprecise at `N = 190–229` drugs. All results in **Table S5** are therefore **strictly hypothesis-generating**. While pivotal Eastern European site share strongly predicts lower pre-approval registered active AE proportions (`-3.60 pp` per `+10 pp`, `p = 4.57e-4`), post-approval labeling supplements (`p = 0.302` OLS; Poisson IRR `1.041 [0.983, 1.103]` per `+10 pp`, `p = 0.167`) and boxed warnings (`+0.61 pp [-4.25, +5.48]` per `+10 pp`, `p = 0.803`) are statistically null with wide intervals. Moreover, our 10-step forensic covariate audit (`faers_us_serious_forensic_audit`) demonstrates that the borderline main-model `us_serious_share` estimate (`+1.81 pp` per `+10 pp`, `p = 0.0462`) is fragile—null in raw bivariate (`-0.89 pp, p = 0.357`), with U.S. FAERS volume control (`+1.71 pp, p = 0.0611`), with Sponsor FE (`+1.93 pp, p = 0.236`, `N = 144`), and in the U.S./Non-U.S. non-serious log-odds ratio (`+0.003, p = 0.960`).

**Table S5. Exploratory Post-Approval FDA Labeling Supplements, Boxed Warnings, and FAERS Profiles (Per `+10 pp` Pivotal EE Share, `N = 229` Originator NDA/BLAs)**

| Category & Outcome Variable | N | Mean | Per-`+10 pp` Coef [95% CI] | p-value | Notes / Precision Caveat |
| :--- | :---: | :---: | :---: | :---: | :--- |
| First Stage: Pivotal Active AE (`pre_act_oth`) | 229 | 0.602 | **−3.60 pp** `[−5.58, −1.63]` | `4.57e-4` | Pre-approval registry difference |
| First Stage: Pivotal Placebo AE (`pre_ctrl_oth`) | 229 | 0.555 | **−3.23 pp** `[−5.16, −1.30]` | `0.00124` | Pre-approval registry difference |
| `Drugs@FDA`: `n_labeling_5yr` (OLS) | 190 | 3.742 | +0.116 `[−0.106, +0.339]` suppl. | `0.302` | Null; wide CI (Poisson IRR `1.041 [0.983, 1.103], p=0.167`) |
| `Drugs@FDA`: `n_labeling_3yr` (OLS) | 216 | 2.014 | −0.005 `[−0.146, +0.136]` suppl. | `0.948` | Null |
| `Drugs@FDA`: `log_labeling_per_yr` | 229 | 0.405 | −0.002 `[−0.019, +0.015]` | `0.814` | Null |
| `Drugs@FDA`: `labeling_share` | 219 | 0.686 | −0.006 `[−0.030, +0.018]` | `0.604` | Null |
| `Drugs@FDA`: `any_safety_rems` | 229 | 0.476 | +1.97 pp `[−2.38, +6.31]` | `0.372` | Null; wide CI |
| FDA Label: `has_boxed_warning` | 205 | 0.312 | +0.61 pp `[−4.25, +5.48]` | `0.803` | Null; imprecise (`−4.25` to `+5.48 pp`) |
| FDA Label: `log_adverse_reactions_chars` | 205 | 9.076 | +0.017 `[−0.045, +0.080]` | `0.585` | Null |
| FAERS (No Denom): `us_serious_share` | 210 | 0.414 | +1.81 pp `[+0.03, +3.60]` | `0.0462` | **Fragile** (`p=0.061` w/ vol; `p=0.236` Sp FE; `p=0.357` raw) |
| FAERS (No Denom): `us_vs_nonus_nonser_lor` | 203 | 2.723 | +0.003 `[−0.122, +0.128]` | `0.960` | Null; lacks exposed denominators |

*Source:* `results/d30_gate2_openfda_results.json` and `tables/table5_gate2_openfda_faers.csv`.

---

## Appendix S5. Pre-Defined Common MedDRA Panels, EMA Policy 0070 Validation Instrument, and Snapshot Provenance

### S5.1 Pre-Defined Common MedDRA Preferred-Term Panels (Derived Strictly from `N = 220` Uncensored `0%`-Threshold Trials)

- **15 Subjective-Symptom Terms (`cpanel_subj`):** `headache`, `nausea`, `diarrhoea`, `back pain`, `vomiting`, `cough`, `dizziness`, `arthralgia`, `pyrexia`, `fatigue`, `rash`, `abdominal pain`, `pain in extremity`, `oropharyngeal pain`, `dyspepsia`.
- **15 Broad Objective-SOC Terms (`cpanel_obj`):** `nasopharyngitis`, `urinary tract infection`, `upper respiratory tract infection`, `hypertension`, `influenza`, `bronchitis`, `gastroenteritis`, `sinusitis`, `alanine aminotransferase increased`, `pharyngitis`, `anaemia`, `palpitations`, `decreased appetite`, `aspartate aminotransferase increased`, `pneumonia`.
- **15 Pure `Investigations` Biomarker Terms (`cpanel_inv`, zero symptom terms):** `alanine aminotransferase increased`, `aspartate aminotransferase increased`, `blood pressure increased`, `blood creatinine increased`, `hepatic enzyme increased`, `weight increased`, `weight decreased`, `blood glucose increased`, `gamma-glutamyltransferase increased`, `blood creatine phosphokinase increased`, `transaminases increased`, `haemoglobin decreased`, `blood alkaline phosphatase increased`, `blood bilirubin increased`, `blood cholesterol increased`.

### S5.2 EMA Policy 0070 CSR Extraction Schema & Cryptographic Snapshot Provenance

**Table S6. Frozen API Snapshot Provenance and EMA Policy 0070 CSR Validation Extraction Fields**

| Artifact / Validation Module | Exact Scope & Specification | Cryptographic / Audit Verification |
| :--- | :--- | :--- |
| Bulk Results-Posted Universe (`page_0001..0023.json.gz`) | `22,303` industry Phase 2/3 trials with results (`2,771` placebo MRCTs; `1,842` Phase 3) | Manifest: `data/raw_ctgov/ctgov_fetch_manifest.json` |
| **Frozen Per-Term MedDRA Snapshot (`meddra_other_events_snapshot.jsonl.gz`)** | **`2,771 / 2,771` trials (`210,424` reported cells); fetched `2026-11-27T23:38:43Z`** | `5,856,781` B gz (`82,813,757` B raw); `SHA-256` `7eb1eefdeae3b188...` |
| All-Registered Geopolitical Cohort (`ctgov_all_registered_war_2017_2025.parquet`) | `20,649` Phase 2/3 industry trials (`2017–2025`, `HasResults` true & false; `6,011` MRCTs) | Manifest: `data/processed/war_all_registered_summary.json` |
| **EMA Policy 0070 Validation Fields (Blinded Dual Extraction)** | (1) Country×arm safety-set `N`; (2) Person-years & AE `timeFrame`; (3) CRF active vs. spontaneous elicitation; (4) Central-lab shift tables; (5) Uncensored (`0%`) symptom proportions; (6) Public-posting selection audit | Pre-specified decision rule: if only country `N` is extractable without country×arm events & elicitation, maintain registry-association scope |
