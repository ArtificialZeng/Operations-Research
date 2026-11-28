# Vehicle Recall Completion at a Fixed Reporting Horizon: Software Remedy Channels, Manufacturer Common Support, and Public API Measurement Integrity (`v4`)

**Author:** Zijian Zeng
**Affiliation:** Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA
**Contact:** `zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`

## Overview

This self-contained, zero-hardcode replication repository evaluates U.S. automotive safety recall completion across over-the-air (OTA) wireless software, hybrid OTA-or-dealer, dealership software, and physical hardware remedy channels anchored on NHTSA's **fixed eighth-quarter reporting horizon** (`2024` and `2025` annual recall completion lists), fully reconciled against federal Part 573 filings (`FLAT_RCL_POST_2010.zip`), U.S. DOT Socrata completion records (`6axg-epim`), NHTSA's official ROSA P completion study (`DOT HS 813 687`), and a 1,452-campaign live audit of NHTSA's public Campaign API (`api.nhtsa.gov`).

## Headline Verified Findings (`v4`)

1. **Verifiable Fixed-Horizon Reconciliation & Sample Flow Accounting:** Linking all `1,537` published rows across NHTSA's `2024` (`809`) and `2025` (`728`) eighth-quarter lists achieves `100.0%` Part 573 campaign linkage, excludes `2` conflicting duplicate campaigns (`22V315`, `22V743`), yields **`1,533` uniquely dated campaigns** (`15` Pure-OTA, `15` Hybrid-OTA, `197` Dealer Software, `1,306` Physical Hardware), matches affected vehicle counts exactly on **`1,531/1,533` (`99.87%`)** campaigns (**`227/227` = `100.0%`** across all software recalls), and verifies 49 CFR § 573.7(a)'s two-year owner-notification (`ODATE`) clock on `98.8%` of rows. Complete channel-by-channel flow accounting on the statutory 2022–2023 `ODATE` cohort (`N = 1,814`) accounts for 100% of all `21` Pure-OTA recalls (`15` unique in 8th report, `5` early-completed at `100.0%`, `1` missing DOT record) and `15/15` (`100.0%`) Hybrid-OTA recalls.
2. **Fixed-Horizon Completion Proportions (Cross-Sectional Proportions, Not Repair Velocity):** Pooled 2024–2025 unweighted eighth-report completion proportions average **`98.32%`** for Pure-OTA (vehicle-weighted `98.58%`), **`89.56%`** for Hybrid-OTA (`94.39%`), **`82.06%`** for Dealer Software (`80.97%`), and **`67.26%`** for Physical Hardware (`65.93%`).
3. **Manufacturer × Channel × Vehicle-Age Common-Support Audit & Explicit Withdrawal of Universal OTA Age-Buffering Claim:** In the fixed eighth-report sample, **Tesla accounts for `11/15` Pure-OTA recalls and `99.17%` of Pure-OTA vehicles** (with `0` Dealer-Software recalls), while the remaining `4` non-Tesla Pure-OTA recalls (`Lucid`, `Volvo Car`) occur solely at oldest-model-year ages `0–1` years. While dealer-channel vehicle-age decay is rock-solid across every specification and all `18/18` Leave-One-OEM-Out exclusions (**`-3.52 pp/yr`**, `p_WCB = 0.001`; standalone Dealer Software **`-4.03 pp/yr`**, `p_WCB = 0.001`; Physical Hardware **`-3.27 pp/yr`**, `p_WCB = 0.001`), the baseline Pure-OTA × Age interaction (`+3.69 pp/yr`, `p_WCB = 0.030`) loses precision in the `0–5` year window (`+3.49`, `p_WCB = 0.226`), collapses without Tesla (**`+1.59 pp/yr`**, `p_WCB = 0.553`), fails 5% significance in `8/18` LOOO drops, and is null inside same-OEM common-support subsamples (`N = 70`, `8` OEMs: `+0.49`, `p_WCB = 0.703`). Any universal claim that OTA neutralizes vehicle-age compliance decay is therefore **explicitly withdrawn**.
4. **Retained Within-OEM Conditional Hybrid-OTA `7.01×` Batch-Scale Contrast:** Conditional on software recall modality within OTA-capable OEMs (`2018–2026`), Hybrid-OTA campaigns are **`7.01×` larger** (`+1.947` log points, `p_WCB = 0.006`) than Dealer Software, contrasted against null unconditional OEM-level first-OTA adoption event studies (`TWFE +0.176, p_WCB = 0.579`; saturated Sun–Abraham IW `-0.532, p_t = 0.470`).
5. **Public Campaign API Measurement Validation Audit:** Separating verbatim Part 573 text coding (`Pure-OTA`, `Hybrid SW-Choice`, `Hybrid HW-Mixed`, `Dealer-Software`) from `api.nhtsa.gov`'s `overTheAirUpdate` flag confirms `100.0%` (`54/54`) agreement in `2019–2023`, `93.9%` (`31/33`) in `2024`, `0/250` physical false negatives, and a sharp May 8, 2025 public-endpoint cutoff (`25V282000` `36/36 True` vs. May 9 `25V315000` `44/44 False`, `0/68` thereafter), contrasted with NHTSA's *2025 Annual Recalls Report* (`33` OTA recalls internally) strictly as a public-API validation finding.

## Reproducibility Pipeline

```powershell
# End-to-end execution
.venv\Scripts\python.exe scripts\01_download_official_sources.py
.venv\Scripts\python.exe scripts\02_audit_nhtsa_campaign_api.py
.venv\Scripts\python.exe scripts\03_build_harmonized_panels.py
.venv\Scripts\python.exe scripts\04_econometric_core_analysis.py
.venv\Scripts\python.exe scripts\05_verify_crossref_references.py
.venv\Scripts\python.exe scripts\06_generate_figures_tables.py
.venv\Scripts\python.exe scripts\09_v4_fixed_report_and_support.py
.venv\Scripts\python.exe scripts\10_generate_v4_figures.py
.venv\Scripts\python.exe scripts\11_build_v4_manuscripts_and_pdfs.py
.venv\Scripts\python.exe scripts\07_build_manifest.py

# Quality & integrity verification
.venv\Scripts\ruff.exe check scripts tests
.venv\Scripts\pytest.exe -v
```

## Key Deliverables (`v4`)

- `manuscript_d12_boost.md` & `manuscript_d12_boost.pdf` — Main manuscript (zero hardcoded numbers, 23 Crossref-verified peer-reviewed DOIs + 6 federal/NHTSA citations, 4 embedded 300-DPI figures, zero leaked tokens)
- `supplementary_d12_jsr.md` & `supplementary_d12_jsr.pdf` — Online Appendix (complete 18-OEM LOOO table, mature-archive sensitivity, live API spot-check receipt, and machine-readable variable codebook)
- `REFEREE_RESPONSE_v4.md` — Point-by-point response addressing every item in `D12.md`
- `data_processed/d12_v4_eighth_report_analysis_panel.csv` — Clean machine-readable replication dataset (`1,533` unique eighth-report campaigns, 31 fields)
- `tables/table_channel_oem_age_support.csv` & `tables/table_v4_*.csv` — Zero-NaN fixed-horizon, common-support, sample-flow, LOOO, and API-validation tables
- `figures/fig1_v4..fig4_v4` — 4 publication figures (`300 DPI PNG` + vector `PDF`)
- `results/d12_v4_fixed_report_audit.json` & `results/d12_v4_live_api_spotcheck.json` — Complete JSON audit receipts
- `SHA256SUMS.json` & `VERIFICATION_MANIFEST.md` — Cryptographic verification manifest
