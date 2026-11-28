# Online Appendix: Supplementary Diagnostics, Mature-Archive Sensitivity, and Machine-Readable Dataset Codebook

Zijian Zeng
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA
`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`

---

## S1. Complete 18-OEM Leave-One-OEM-Out (LOOO) Table and Same-OEM Age-Overlap Bounds

This section archives the full manufacturer-by-manufacturer Leave-One-OEM-Out (`LOOO`) sensitivity table corresponding to Main Manuscript Section 4.2 and Figure 3B (`tables/table_v4_looo_sensitivity.csv`), alongside the exact overlapping vehicle-age intervals for the 8 manufacturers observing both Dealer Software and OTA recalls in the fixed eighth-report sample.

**Appendix Table S1.** *Complete Leave-One-OEM-Out (`LOOO`) Sensitivity on Fixed Eighth-Report Vehicle-Age Interactions (Baseline $N = 148$, 18 OTA-Capable OEMs).*

| Excluded Manufacturer | Dropped $N$ (Pure / Hyb / DSW) | Rem. $N$ | Rem. OEMs | Dealer Age (pp/yr) | Dealer $p_{\text{WCB}}$ | Pure $\times$ Age (pp/yr) | Pure $p_{\text{WCB}}$ | Hybrid $\times$ Age (pp/yr) | Hybrid $p_{\text{WCB}}$ |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Tesla, Inc.** | 11 (11/0/0) | 137 | 17 | −3.56 | 0.001 | +1.59 | 0.553 | +0.72 | 0.709 |
| Mack Trucks, Inc. | 3 (0/0/3) | 145 | 17 | −3.49 | 0.001 | +2.95 | 0.114 | +0.57 | 0.818 |
| Chrysler (FCA US, LLC) | 21 (0/0/21) | 127 | 17 | −3.52 | 0.001 | +3.37 | 0.083 | +1.32 | 0.399 |
| General Motors, LLC | 7 (0/3/4) | 141 | 17 | −3.57 | 0.001 | +3.52 | 0.076 | +0.53 | 0.797 |
| Honda (American Honda Motor Co.) | 4 (0/0/4) | 144 | 17 | −3.50 | 0.001 | +3.55 | 0.053 | +0.52 | 0.731 |
| Mercedes-Benz USA, LLC | 15 (0/2/13) | 133 | 17 | −3.04 | 0.001 | +3.56 | 0.103 | −0.83 | 0.653 |
| Hyundai Motor America | 5 (0/0/5) | 143 | 17 | −3.45 | 0.001 | +3.56 | 0.046 | +0.73 | 0.706 |
| Daimler Vans USA, LLC | 5 (0/1/4) | 143 | 17 | −3.53 | 0.001 | +3.60 | 0.040 | +1.16 | 0.533 |
| Ford Motor Company | 25 (0/6/19) | 123 | 17 | −3.48 | 0.001 | +3.61 | 0.053 | +1.32 | 0.531 |
| Lucid USA, Inc. | 4 (3/0/1) | 144 | 17 | −3.53 | 0.001 | +3.68 | 0.036 | +0.74 | 0.728 |
| Winnebago Industries, Inc. | 1 (0/0/1) | 147 | 17 | −3.52 | 0.001 | +3.69 | 0.041 | +0.75 | 0.710 |
| Jaguar Land Rover North America, LLC | 5 (0/1/4) | 143 | 17 | −3.56 | 0.001 | +3.70 | 0.032 | +0.67 | 0.810 |
| Volvo Car USA, LLC | 3 (1/0/2) | 145 | 17 | −3.52 | 0.001 | +3.72 | 0.040 | +0.75 | 0.710 |
| Nissan North America, Inc. | 6 (0/2/4) | 142 | 17 | −3.50 | 0.001 | +3.72 | 0.093 | +0.57 | 0.794 |
| Toyota Motor Engineering & Manufacturing | 6 (0/0/6) | 142 | 17 | −3.54 | 0.001 | +3.74 | 0.033 | +0.75 | 0.708 |
| Volvo Trucks North America | 3 (0/0/3) | 145 | 17 | −3.57 | 0.001 | +3.82 | 0.032 | +0.92 | 0.634 |
| BMW of North America, LLC | 14 (0/0/14) | 134 | 17 | −3.60 | 0.001 | +4.03 | 0.035 | +0.66 | 0.741 |
| Kia America, Inc. | 10 (0/0/10) | 138 | 17 | −3.50 | 0.003 | +4.07 | 0.024 | +0.70 | 0.707 |

*Notes:* Each row drops all eighth-report software campaigns from the named OEM and re-estimates the baseline specification (`veh_age`, `is_ota_pure`, `is_ota_hybrid`, and age interactions with Manufacturer, Component, Filing-Quarter, and Report-Year FE; $B = 999$ Rademacher WCB). Dealer-Software age decay remains significant in 18/18 drops (all $p_{\text{WCB}} \le 0.003$), whereas Pure-OTA $\times$ Age loses 5% significance in 8/18 drops and collapses to +1.59 ($p_{\text{WCB}} = 0.553$) without Tesla.

**Appendix Table S1B.** *Within-OEM Overlapping Vehicle-Age Ranges Among the 8 Fixed Eighth-Report Common-Support Manufacturers.*

| Manufacturer (Same-OEM Common Support) | OTA Age Range (yr) | Dealer-SW Age Range (yr) | Strict Overlap Range (yr) |
|---|---:|---:|---:|
| Daimler Vans USA, LLC | 3–3 | 2–4 | 3–3 |
| Ford Motor Company | 0–2 | 0–5 | 0–2 |
| General Motors, LLC | 0–2 | 0–4 | 0–2 |
| Jaguar Land Rover North America, LLC | 4–4 | 2–4 | 4–4 |
| Lucid USA, Inc. | 1–1 | 1–1 | 1–1 |
| Mercedes-Benz USA, LLC | 0–5 | 0–15 | 0–5 |
| Nissan North America, Inc. | 1–1 | 0–7 | 1–1 |
| Volvo Car USA, LLC | 0–0 | 0–0 | 0–0 |

*Notes:* Only 6 individual `primary_make_model` lines (`FORD__MUSTANG MACH E, FREIGHTLINER__SPRINTER 1500, JAGUAR__I-PACE, LUCID__AIR, MERCEDES-BENZ__EQS 450, VOLVO__C40BEV`, $N = 20$ campaigns total) overlap across Dealer Software and OTA in the eighth-report sample, and every line exhibits zero within-model OTA age variation.

---

## S2. Mature ($\ge 18$-Month) Latest-Snapshot Cross-Sections and Common-Support Audit

Because the public U.S. DOT Socrata registry (`6axg-epim`, frozen November 25, 2026) blends heterogeneous post-remedy reporting durations rather than anchoring campaigns at a uniform reporting quarter, all mature ($\ge 540$-day) latest-snapshot analyses are presented strictly as supplementary sensitivity checks rather than primary fixed-horizon evidence.

**Appendix Table S2.** *Supplementary Mature ($\ge 18$-Month) Latest-Snapshot Vehicle-Age Interaction Sensitivity (`6axg-epim`).*

| Mature Latest-Snapshot Sensitivity Specification (`6axg-epim`) | $N$ | OEMs | Dealer Age (pp/yr, $p_{\text{WCB}}$) | Pure $\times$ Age (pp/yr, $p_{\text{WCB}}$) | Hybrid / Pooled OTA $\times$ Age (pp/yr, $p_{\text{WCB}}$) |
|---|---:|---:|---:|---:|---:|
| Snapshot: oldest MY, filing >=540 d (4-way) | 533 | 28 | −3.57 (0.001) | +3.08 (0.039) | +2.25 (0.044) |
| Snapshot: middle MY, filing >=540 d (4-way) | 533 | 28 | −4.55 (0.001) | +3.44 (0.409) | +1.99 (0.266) |
| Snapshot: oldest MY, notice >=540 d (4-way) | 506 | 28 | −3.27 (0.001) | +2.83 (0.086) | +1.54 (0.069) |
| Snapshot: oldest MY, 0-5 yr window (4-way) | 488 | 28 | −3.04 (0.003) | +2.40 (0.063) | +2.26 (0.038) |
| Snapshot: middle MY, excluding Tesla (pooled OTA) | 503 | 27 | −4.56 (0.001) | — (pooled) | +2.10 (0.207) |
| Snapshot: same-model overlap (29 models, Make-Model FE, 4-way) | 123 | 13 | −2.32 (0.014) | +2.33 (0.047) | +2.16 (0.211) |
| Snapshot: same-model overlap excl. Tesla (Make-Model FE, 4-way) | 104 | 12 | −3.66 (0.040) | +6.57 (0.516) | +3.07 (0.301) |
| Snapshot: same-model overlap excl. Tesla (Make-Model FE, pooled OTA) | 104 | 12 | −3.74 (0.030) | — (pooled) | +3.35 (0.269) |

*Notes:* Even in the larger latest-snapshot archive, restricting to ages 0–5 years ($p_{\text{WCB}} = 0.119$), middle model year ($p_{\text{WCB}} = 0.409$), owner-notice $\ge 540$ days ($p_{\text{WCB}} = 0.086$), or same-model overlap excluding Tesla (Pure $\times$ Age $p_{\text{WCB}} = 0.519$; Hybrid $\times$ Age $p_{\text{WCB}} = 0.112$; pooled OTA $p_{\text{WCB}} = 0.064$) fails to establish a robust multi-OEM OTA age-buffering effect.

**Appendix Table S3.** *Manufacturer Concentration in Mature ($\ge 18$-Month) Latest-Snapshot Pure-OTA Campaigns ($N = 46$).*

| Manufacturer (Mature $\ge 18$m Pure-OTA) | $N$ | Share $N$ (%) | Affected Instances | Share Veh. (%) | Mean CR (%) | Max Age (yr) | $N$ Aged $\ge 6$ yr |
|---|---:|---:|---:|---:|---:|---:|---:|
| Tesla, Inc. | 27 | 58.7% | 9,023,718 | 98.73% | 99.23 | 12 | 6 |
| Fisker Group Inc | 4 | 8.7% | 29,218 | 0.32% | 100.00 | 1 | 0 |
| Volvo Car USA, LLC | 1 | 2.2% | 27,457 | 0.30% | 99.86 | 0 | 0 |
| Polestar Automotive USA, Inc. | 1 | 2.2% | 25,825 | 0.28% | 100.00 | 3 | 0 |
| Hyundai Motor America | 1 | 2.2% | 18,206 | 0.20% | 98.51 | 0 | 0 |
| Lucid USA, Inc. | 5 | 10.9% | 7,576 | 0.08% | 97.51 | 2 | 0 |
| Rivian Automotive, LLC | 2 | 4.3% | 6,591 | 0.07% | 100.00 | 1 | 0 |
| LIVEWIRE EV, LLC | 1 | 2.2% | 523 | 0.01% | 97.13 | 0 | 0 |
| Motiv Power Systems | 2 | 4.3% | 228 | 0.00% | 100.00 | 5 | 0 |
| Lonestar Specialty Vehicles | 1 | 2.2% | 13 | 0.00% | 100.00 | 2 | 0 |
| Faraday Future Eco Sales Co. LLC | 1 | 2.2% | 11 | 0.00% | 100.00 | 1 | 0 |

*Notes:* Tesla accounts for 27/46 campaigns, 98.73% of affected vehicle-instances, and 6/6 (100.0%) of mature Pure-OTA campaigns aged $\ge 6$ years. Non-Tesla light-duty passenger Pure-OTA reaches a maximum oldest-model-year age of only 3 years.

---

## S3. Within-OEM Hybrid Batch-Scale Robustness and Unconditional First-OTA Event Study

Full robustness diagnostics for the retained conditional within-OEM Hybrid-OTA batch-scale contrast ($+1.947$ log points = $7.01\times$, $p_{\text{WCB}} = 0.006$) and the unconditional OEM-level staggered first-OTA adoption event study (`TWFE` $N = 1,239$, $G = 68$, $+0.176$, $p_{\text{WCB}} = 0.579$; saturated Sun–Abraham 2021 IW $N = 1,233$, $G = 67$, 7 cohorts, 39 cohort $\times$ relative-time cells, $-0.532$, $p_t = 0.470$, IW pre-trend $F(2, 66) = 0.26$, $p = 0.775$) are archived in `tables/table2_blast_radius_and_selection.csv` and `results/d12_econometric_results.json`.

---

## S4. Supplementary Recall-Level Unremedied Proxy Checks and Safety/Complaint Empirical Nulls

In the mature latest-snapshot archive (`6axg-epim`), recall-level counts sum campaign–VIN instances (not unique fleet vehicles) and incorporate 49 CFR § 573.7(b)(5) unreachable-vehicle adjustments. Holding campaign size fixed, both Pure-OTA (−2.062, $p_{\text{WCB}} = 0.035$) and Hybrid-OTA (−0.666, $p_{\text{WCB}} = 0.012$) compress `log(1 + unremedied instance proxy)`. Unconditionally under finite-sample wild cluster bootstrap inference, estimates relative to physical hardware are marginally significant at 10% for Pure-OTA (−1.918, $p_{\text{WCB}} = 0.065$) and Hybrid-OTA (+1.415, $p_{\text{WCB}} = 0.055$; Hybrid-minus-Pure contrast +3.334, $p_{\text{WCB}} = 0.007$), while relative to OTA-capable OEMs' dealer software, Pure-OTA is statistically null (−0.599, $p_{\text{WCB}} = 0.401$), Hybrid-OTA is +1.130 ($p_{\text{WCB}} = 0.097$), and their contrast is +1.729 ($p_{\text{WCB}} = 0.079$). Because these unconditional proxy contrasts confound campaign scale, single-OEM weight concentration (98.73% Tesla), and heterogeneous reporting horizons, we do not interpret them as causal fleet-stock reductions.

Across regulatory oversight and consumer safety complaints (2020–2026 NHTSA ODI bulk archives: 437,886 unique deduplicated `ODINO` complaints across 636,875 component records linked to 4,560 balanced 2021–2025 campaigns), Pure-OTA campaigns have +27.77 pp higher FMVSS technical noncompliance ($p_{\text{WCB}} = 0.005$) and active-era API OTA campaigns have -5.63 pp fewer formal ODI investigations ($p_{\text{WCB}} = 0.019$). Balanced $[-12\text{m}, +12\text{m}]$ consumer complaint-decay event studies exhibit pre-recall ramp-up (pre-trend Wald $F(11, 114) = 2.56$, $p = 0.006$) and transparent empirical nulls across full-window (`Active SW` Pure +0.011, $p_{\text{WCB}} = 0.825$; Hybrid −0.012, $p_{\text{WCB}} = 0.780$) and short $[-3, -1]$ vs. $[+1, +12]$ specifications (Pure −0.101, $p_{\text{WCB}} = 0.271$; Hybrid −0.035, $p_{\text{WCB}} = 0.480$). Full tables are archived in `tables/table5_safety_cascades_and_complaints_did.csv` and `tables/table5b_prerecall_complaints_and_hazards.csv`.

---

## S5. Live Public API Spot-Check Receipt and Machine-Readable Dataset Codebook

**Appendix Table S4.** *Live Public NHTSA Campaign API Spot-Check Receipt (`results/d12_v4_live_api_spotcheck.json`, Retrieved `2026-11-28T00:18:54Z`).*

| Campaign ID | Audit Role | HTTP | API Records | `overTheAirUpdate` Flags | OTA Text Records |
|---|---|---:|---:|---|---:|
| `25V282000` | Boundary: last public API overTheAirUpdate=True campaign (Volvo, May 8, 2025) | 200 | 36 | `true`: 36 | 36 |
| `25V315000` | Boundary: first next-day public API False despite verbatim OTA text (Ford, May 9, 2025) | 200 | 44 | `false`: 44 | 44 |
| `25V409000` | Post-cutoff verbatim Pure-OTA example (Polestar, June 2025) | 200 | 2 | `false`: 2 | 2 |
| `26V104000` | Post-cutoff 2026 verbatim Hybrid-OTA example (Ford, Feb 2026) | 200 | 51 | `false`: 51 | 51 |
| `22V315000` | Excluded duplicate across 2024 (56.9%) & 2025 (45.6%) 8th-report lists (Mercedes-Benz) | 200 | 53 | `false`: 53 | 0 |
| `22V743000` | Excluded duplicate across 2024 (84.2%) & 2025 (79.2%) 8th-report lists (Bentley) | 200 | 2 | `false`: 2 | 0 |
| `22V867000` | Physical-recall denominator discrepancy audit (17,445 CSV vs 117,445 FLAT_RCL/DOT, Honda) | 200 | 3 | `false`: 3 | 0 |
| `23V413000` | Physical-recall denominator amendment audit (331,401 CSV vs 305,282 FLAT_RCL/DOT, FCA) | 200 | 3 | `false`: 3 | 0 |
| `22V063000` | Unlisted 2022 ODATE Pure-OTA campaign missing DOT completion rate (Tesla Boombox) | 200 | 15 | `true`: 15 | 15 |

**Appendix Table S5.** *Machine-Readable Replication Dataset Variable Dictionary (`data_processed/d12_v4_eighth_report_analysis_panel.csv`, $N = 1,533$ Rows, SHA-256 `c6d46ef262a21ada...`).*

| Variable Name | Type | Description & Measurement Definition |
|---|---|---|
| `report_year` | `int` | Published NHTSA annual eighth-report list year (`2024` or `2025`). |
| `campaign_code` | `str` | Six-character NHTSA campaign identifier joining annual lists to `FLAT_RCL` (`CAMPNO[:6]`). |
| `CAMPNO` | `str` | Full nine-character NHTSA campaign identifier (e.g., `22V037000`). |
| `mfg` | `str` | Canonicalized corporate manufacturer entity (harmonized from 705 raw strings to 646 entities). |
| `rec_date` / `odate` | `date` | Part 573 filing date (`RCDATE`) and owner remedy notification date (`ODATE`, initiating § 573.7(a)). |
| `modality4` | `str` | Mutually exclusive text-coded channel: `Pure_OTA`, `Hybrid_OTA`, `Dealer_Software`, `Physical_Hardware`. |
| `is_ota_hybrid_swchoice` / `hwmixed` | `int` | Sub-indicators splitting Hybrid-OTA into pure software choice vs. OTA + hardware inspection/replacement. |
| `is_ota_api_full` | `int` | External public Campaign API `overTheAirUpdate` boolean indicator (valid pre-May 8, 2025; audit benchmark only). |
| `vehicle_age_years` / `median_vehicle_age` | `float` | `rec_year - min_my` (oldest model year) and `rec_year - median_my` (middle model year). |
| `reported_affected` / `potaff` | `int` | Affected vehicle denominator in eighth-report list vs. `FLAT_RCL` / `6axg-epim` (99.87% exact match). |
| `completion_at_eighth_report_pct` | `float` | Primary fixed-horizon completion proportion at the eighth reporting quarter (`[0, 100]`). |
| `completion_rate` | `float` | Latest-snapshot DOT `6axg-epim` completion proportion (frozen Nov 25, 2026; supplementary only). |

*Source Provenance Receipts:* `data_raw/nhtsa_annual_eighth_report_2024_2025.csv` (33,104 bytes, SHA-256 `7c19005d8880e8b1534e779d53288606640f41acc4c1470ecdd0eac44c91e596`); `data_raw/dot_79374_DS1.pdf` (`DOT HS 813 687`, 1,711,440 bytes, SHA-256 `8ed143715331731bf7eac149b5cea65efb5402b40da96add9c4a6975dbf276d5`).
