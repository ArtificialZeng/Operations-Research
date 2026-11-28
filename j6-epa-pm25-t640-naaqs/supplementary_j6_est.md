# Supporting Information: Residual Optical PM₂.₅ Bias During Wildfire Smoke and Sensitivity of U.S. Exceptional-Event Tiering Thresholds

Zijian Zeng  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Section S1. Case-Flow Attrition, Heavy-Smoke Same-Rooftop Triples, and Data Provenance

This Supporting Information documents (1) the four exact same-site, same-day triple observations under NOAA HMS Heavy smoke (`Table S1`) and file-version manifest (`tables/aqs_and_threshold_version_manifest.csv`), (2) validation of our 40 CFR Part 50 Appendix N out-of-time Tier-1 threshold reconstruction against EPA's published `2021–2025` table (`Table S2`, `Figure S2A`), (3) screening-level 3-year annual Design Value sensitivity analyses moved out of the main text (`Table S3`, `Figure S1`), (4) archival observational Exceptional Event flagging diagnostics including the within-county-year null test (`Table S4`, `Figure S2B`), and (5) a brief summary of the formal threshold-crossing metrology model.

**Table S1. All Four Same-Site, Same-Day Collocated Triple Observations (`T640_FW`, `BAM`, and `FRM`) Under NOAA HMS Heavy Smoke (2023–2025)**

| Site ID | Date | EPA Region | FRM (µg/m³) | T640_FW (µg/m³) | BAM (µg/m³) | T640 − FRM | BAM − FRM | EPA Tier-1 Cutoff |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| `23003-1011` | 2024-08-16 | R1 | 20.7 | 26.0 | 19.2 | +5.3 | -1.5 | 16.35 |
| `37021-0034` | 2025-05-31 | R4 | 9.5 | 11.1 | 9.0 | +1.6 | -0.5 | 17.70 |
| `47037-0023` | 2025-05-31 | R4 | 10.1 | 10.9 | 9.1 | +0.8 | -1.0 | 21.75 |
| `23001-0011` | 2025-08-05 | R1 | 14.7 | 16.7 | 15.9 | +2.0 | +1.2 | 19.20 |

*Notes:* Across all `63,951` `T640_FW–FRM` and `22,927` `BAM–FRM` pairs (2023–2025), `401` same-site, same-day triple observations occur across `5` monitoring sites, of which exactly `4` occur on NOAA HMS Heavy smoke days (`4` sites). In all four Heavy-smoke triples, aligned `T640_FW` reads above collocated gravimetric `FRM` (mean `+2.43` µg/m³), whereas `BAM` averages `-0.45` µg/m³. Because $n = 4$ is underpowered for standalone head-to-head Heavy-smoke inference, `BAM–FRM` is retained in the main manuscript strictly as a background reference benchmark.

The complete versioned provenance manifest (`tables/aqs_and_threshold_version_manifest.csv`, `19` artifacts) pins SHA-256 digests and row counts for `aqs_monitors.zip`, `daily_88101_2018.zip`–`daily_88101_2025.zip`, `annual_conc_by_monitor_2018.zip`–`annual_conc_by_monitor_2025.zip`, `monitor_hms_daily_2018_2025.parquet` (`2,922/2,922` calendar days), and EPA's pinned threshold table `epa_pm25_tier_thresholds_2026-09-14.csv` (SHA-256 `ac314789d31b89fd93f044e01d71affd9af3bf0454dae1c685adfc5348cf40e4`). The complete reproducible paired Heavy-smoke dataset (`673` rows: `472` T640_FW + `201` BAM) is exported in `tables/collocated_heavy_smoke_pairs_2023_2025.csv`.

---

## Section S2. Out-of-Time Threshold Reconstruction Validation Against Official EPA 2021–2025 Snapshot

To validate our implementation of 40 CFR Part 50 Appendix N § 3.0(d) combined-site aggregation and § 4.5(a) Table 1 order-statistic 98th percentiles prior to evaluating strictly out-of-time rolling windows (`2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`), we benchmarked our `2021–2025` reconstruction directly against EPA's official published `for_posting.csv` snapshot (`2026-09-14`). On sites with zero AirData event flags during 2021–2025, median absolute Tier-1 error is exactly `0.000 µg/m³` (`r = 0.876`–`0.896`; remaining tail discrepancies arise from late-2025 state data certifications entered into AQS between May and September 2026 and individual-day `I`-qualifier flags unavailable in public bulk AirData CSVs).

**Table S2. Benchmark Accuracy of 2021–2025 Threshold Reconstruction Against EPA's Official Table and Year-by-Year Out-of-Time `T640_FW–FRM` Tier-1 Results**

| Reconstruction Specification | All Sites Corr ($r$) | All Med Abs Err (µg/m³) | All Mean Err | Clean Sites Corr ($r$) | Clean Med Abs Err | OOT 2023 / 2024 / 2025 T640 Diff (pp) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| Combined-Site daily (App N Table 1) | 0.819 | 0.150 | +1.670 | 0.876 | 0.000 | Benchmark only |
| OOT-A: Combined-Site + AQS Events-Excluded Annual P98 | 0.795 | 0.750 | +0.578 | 0.866 | 0.000 | +8.25 / +5.13 / +3.08 |
| OOT-B: Combined-Site excl. HMS Heavy + R-Excl Annual P98 | 0.809 | 0.900 | +0.512 | 0.895 | 0.000 | +9.79 / +5.13 / +3.08 |
| OOT-B2: Combined-Site excl. HMS Med+Heavy + R-Excl Annual P98 | 0.816 | 0.900 | +0.271 | 0.896 | 0.150 | +10.31 / +7.69 / +3.59 |
| OOT-C: Pure Gravimetric FRM-Only | 0.592 | 1.950 | +0.358 | 0.723 | 1.650 | +8.76 / +9.09 / +1.08 |

*Notes:* All four strictly out-of-time rolling specifications yield strictly positive `T640_FW` Tier-1 excess in every calendar year (`2023`, `2024`, `2025`) with zero FRM-only reversals (`26`–`33` vs. `0`).

---

## Section S3. Screening-Level Annual Design Value Sensitivity (Strictly Distinct from CAA § 107(d) Designations)

**Important Epistemic Disclaimer:** The accounting calculations in this section evaluate **screening-level monitor Design Value threshold cross-overs** ($\ge 9.1$ vs. $\le 9.0\;\mu\text{g/m}^3$) constructed from AQS daily records under 40 CFR Part 50, Appendix N. They are **not** formal Clean Air Act § 107(d) nonattainment area designations—which require EPA's statutory five-factor area analysis (air quality data, emissions, meteorology, geography/topography, and jurisdictional boundaries) and can include counties without an exceeding monitor—nor do they measure approved Exceptional Event exclusions.

1. **Same-Rooftop `2023–2025` Paired Design Value Classification (`Figure S1B`):** Restricting to `178` collocated `T640_FW–FRM` rooftops with multi-year paired-day 2023–2025 Appendix N coverage, aligned `T640_FW` exhibits a mean 3-year annual Design Value bias of **`+0.468 µg/m³`** ($t = +9.17$, $p = 1.20 \times 10^{-16}$). At the `9.0 µg/m³` annual threshold (rounded to `0.1 µg/m³`, exceeding iff $\ge 9.1$), **`19` rooftops** exceed on `T640_FW` while remaining $\le 9.0$ on collocated FRM two meters away, versus only **`2`** in reverse (exact binomial $p = 0.0002$; strict 4-quarter × 3-year stitched subsample: `18` vs. `3`, $p = 0.001$). In the separate background `BAM–FRM` cohort (`56` rooftops), mean paired DV bias is `-0.021 µg/m³` ($p = 0.787$; `1` vs. `0` discordant, $p = 1.000$).
2. **Retrospective `2021–2023` Monitor Design Value Threshold Reclassification Waterfall (`Figure S1A`, `Table S3`):** Repairing `410` mid-2023 split-year T640 monitors (`POC`/`POC+20`) and excluding `281` non-regulatory monitors reproduces EPA's official Table 4a `2021–2023` county exceedances at `98/99 = 99.0%` precision across `495` matched regulatory counties. Holding the `2021–2023` monitoring window fixed and swapping pre-alignment raw T640 (`236/238`) for post-alignment T640 (`636/638/736/738`) reduces county monitor-DV threshold exceedances from `146` (`98.34M` residents) to `99` (`79.96M` residents)—a screening-level set of **`47` counties (`18.39M` residents)** crossing from $\ge 9.1$ to $\le 9.0\;\mu\text{g/m}^3$. Census ACS 2023 / PEP 2024 tabulations (`Table S3`) show these `47` DV-reclassified counties lie overwhelmingly outside the arid West (`72.3%` Midwest+South vs. `53.5%` still $\ge 9.1$, Fisher $p = 0.032$) and carry higher mean Black non-Hispanic resident shares than cleanly $\le 9.0$ counties (`14.7%` vs. `9.2%`, Welch $p = 0.016$).

<!-- FIGURE:figS1_si_dv_reclassification_and_rooftop_lottery.png -->

**Table S3. Screening-Level `2021–2023` Monitor Design Value Reclassification Accounting and U.S. Census Demographic Profile (495 Matched Regulatory Counties)**

| Screening-Level County Monitor DV Group (2021–2023) | Counties | 2024 Pop. (M) | Midwest + South Share | Mean Black NH (%) | Mean Hispanic (%) | Median HH Income ($) |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
| T640 Alignment DV-Reclassified ($\ge 9.1 \to \le 9.0$) | 47 | 18.39 | 72.3% | 14.7% | 9.6% | \$72,424 |
| Still Above Monitor DV Threshold ($\ge 9.1$ Aligned) | 99 | 79.96 | 53.5% | 14.0% | 21.2% | \$72,536 |
| Cleanly Below Monitor DV Threshold ($\le 9.0$ Both) | 349 | 107.15 | — | 9.2% | 12.4% | \$76,171 |

*Notes:* County populations describe the screening-level monitor DV reclassification set only and must not be interpreted as populations under formal EPA Clean Air Act § 107(d) designations.

---

## Section S4. Archival Exceptional Event Flagging Context and Explicit Within-County-Year Null Disclosure

To avoid any conflation of paired metrological threshold crossings with strategic agency behavior, `Table S4` and `Figure S2B` record our auxiliary archival audit of 40 CFR § 50.14 Exceptional Event flagging across 2018–2025 (after correcting AQS's `49.9%` false-positive concurrence row coding). Three candid boundaries apply: (i) strictly exogenous `DV_18_20` checks confirm clean nulls on gravimetric FRM PM₂.₅ (Margin D), `FEM → FRM` switching (Margin A), and monitor survival (Margin C); (ii) the observational monitor-year and county-year flagging increases near the 9.0 µg/m³ threshold peaked in `2022–2023` *prior* to the February 2024 final rule (anticipatory/designation-window retroactive flagging), with null `2024–2025` EPA-concurred flow; and (iii) crucially, **a within-county-year fixed-effects test comparing T640 against non-T640 monitors in the same county and year yields a clean statistical null (`+0.81` pp, $p_{\text{WCB}} = 0.931$, $N = 981$)**. Accordingly, this study makes **no claim** that optical measurement bias causally induces state Exceptional Event filings.

<!-- FIGURE:figS2_si_oot_reconstruction_and_ee_nulls.png -->

**Table S4. Auxiliary Exogenous Null Checks and Archival Exceptional Event Flagging Audit (2018–2025)**

| Auxiliary / Archival Check | Estimate | Uncertainty / $p$-Value | Epistemic Status |
| :--- | ---: | ---: | :--- |
| Exogenous `DV_18_20` Gravimetric FRM PM₂.₅ (Margin D) | +0.007 µg/m³ | $p_{\text{WCB}} = 0.951$ | Clean null (zero gravimetric shift) |
| Exogenous `DV_18_20` FEM→FRM Switching (Margin A) | -0.030 | $p_{\text{WCB}} = 0.287$ | Clean null |
| Exogenous `DV_18_20` Monitor Survival (Margin C) | +0.026 | $p_{\text{WCB}} = 0.358$ | Clean null |
| Observational Monitor-Year EE Flagging DiD (`2022–2025`) | +8.17 pp | State $p_{\text{WCB}} = 0.004$; RI $p = 0.0010$ | Anticipatory 2022–2023 surge prior to Feb 2024 rule |
| Observational County-Year EE Flagging DiD (`2022–2025`) | +9.96 pp | State $p_{\text{WCB}} = 0.003$; RI $p = 0.0010$ | 2025 EPA-concurred flow null ($p = 0.915$) |
| **Within-County-Year FE T640 Flagging Test (`N = 981`)** | **+0.81 pp** | **$p_{\text{WCB}} = 0.931$** | **Null — no causal claim of instrument-induced EE filing** |

---

## Section S5. Formal Threshold-Crossing Metrology Summary

Our companion numerical verification (`results/04_formal_model_verification.json`) formalizes the mechanics linking continuous optical bias $b(S, \text{RH}) > 0$ to discrete threshold crossings: (i) for sites near an annual Design Value cutoff, even sub-microgram regional bias (`b = 0.60` µg/m³ in humid Midwest winter vs. `0.21` µg/m³ in the arid West) generates steep asymmetric classification odds ratios (`97.1:1` in simulation); and (ii) under concave exclusion-effort optimization, marginal agency screening incentives peak around the compliance boundary (strict second-order concavity verified with max finite-difference error `1.44e-05`), amplifying the sensitivity of near-threshold smoke days (`±20%` of Tier-1) to positive optical bias.
