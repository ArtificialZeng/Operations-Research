# D12 Boost: The Software-Defined Vehicle Recall Paradox (`v2` Major Revision)

**Full Publication-Grade Empirical Operations Management & Regulatory Safety Study**
**Target Journals:** *Management Science* (Operations Management / Information Systems) / *Manufacturing & Service Operations Management (M&SOM)*

## Overview

This self-contained repository executes an end-to-end empirical investigation of over-the-air (OTA) wireless software recalls versus dealer-remedied software and physical hardware recalls across the complete U.S. automotive recall census (2015–2026), integrating four official U.S. federal datasets:

1. **NHTSA ODI Complete Recalls Flat File (`FLAT_RCL_POST_2010.zip`):** 10,559 Vehicle campaigns (2015–2026); 7,967 in 2018–2026 across 646 canonicalized corporate OEM entities (32 OTA-capable OEMs; 21 light-duty passenger-vehicle OEMs).
2. **U.S. DOT Official Completion-Rate Registry (`6axg-epim`):** 30,484 rows; 7,385 rated 2018–2026 Vehicle campaigns; 6,412 mature ($\ge 18$-month post-`RCDATE`) campaigns spanning 228.43 million summed recall-level affected vehicle-instances (subject to 49 CFR § 573.7 unreachable-vehicle exclusions and remedy-available quarterly timing).
3. **Live NHTSA Public Campaign API (`api.nhtsa.gov/recalls/campaignNumber`):** 1,452 audited campaigns (100% of 1,202 software/OTA candidates + 250 stratified physical campaigns; 0 HTTP errors).
4. **NHTSA ODI Consumer Complaints (`2020–2026`):** 437,886 unique consumer complaints (`ODINO`) across 636,875 component-level records, strictly deduplicated by `(campaign, ODINO)` and linked at exact `(Make, Model, ModelYear, Component)` level into a 114,000-row balanced `[-12m, +12m]` event-study panel (4,560 campaigns).

## Headline Verified Findings (`v2`)

1. **Primary Finding 1 — OTA Flattening of the Vehicle-Age Compliance-Decay Cliff:** Mature `Dealer-Software` completion declines by **$-3.57$ pp/yr** ($p_{\text{WCB}} = 0.001$) as vehicles age (`90.3% -> 63.6%`), whereas `Pure-OTA × Age` ($+3.08$ pp/yr, $p_{\text{WCB}} = 0.039$) offsets **86.3%** of decay (`99.3% -> 97.4%` at 6+ yr), `Hybrid-OTA × Age` ($+2.25$ pp/yr, $p_{\text{WCB}} = 0.044$) offsets **63.0%**, and `Public API OTA × Age` ($+2.74$ pp/yr, $p_{\text{WCB}} = 0.002$) offsets **77.0%**. Crucially, age-decay mitigation survives complete exclusion of Tesla (`Any OTA × Age` $+2.37$ pp/yr, $p_{\text{WCB}} = 0.030$; `API OTA × Age` $+1.96$ pp/yr, $p_{\text{WCB}} = 0.023$) and holds strictly within light-duty passenger OEMs (`Pure-OTA × Age` $+3.22$, $p_{\text{WCB}} = 0.032$; `Hybrid-OTA × Age` $+2.36$, $p_{\text{WCB}} = 0.007$).
2. **Primary Finding 2 — May 8, 2025 NHTSA Public Campaign API Metadata Anomaly:** Live `overTheAirUpdate` matched audited remedy text on **54/54 (100.0%)** in 2019–2023 and **31/33 (93.9%)** in 2024 (with **0/250 = 0.0%** physical false negatives), drifted to **4/7 (57.1%)** during Jan 1–May 8, 2025 (final `True`: Volvo `25V282000`, 36/36 records `True`), and returned **`False` on 68/68 (100.0%)** subsequent 2025–2026 OTA recalls starting May 9 with Ford `25V315000` (44/44 records `False` despite explicit OTA text). Contrasting this public endpoint drop (`4/38` in 2025) against NHTSA's separate *2025 Annual Recalls Report* (March 2026), which tallied **33 OTA recalls in 2025**, isolates a public Campaign API endpoint metadata discrepancy rather than an internal agency tracking halt.
3. **Conditional Campaign-Size Differentials vs. Distinct Unconditional OEM-Level First-OTA ITT:** Within OEMs, conditional on modality, `Hybrid-OTA` recalls are **$7.01\times$ larger** ($+1.947$ log points, $p_{\text{WCB}} = 0.006$; API OTA 2018–2024 $+1.887$, $p_{\text{WCB}} = 0.039$) than `Dealer-Software`, whereas `Pure-OTA` shows no significant within-OEM size premium ($+1.084$, $p_{\text{WCB}} = 0.233$). Unconditionally around an OEM's first OTA recall, TWFE ITT ($+0.176$, $p_{\text{WCB}} = 0.579$; pre-trend $p = 0.424$) and saturated Sun–Abraham (2021) IW ($-0.532$, $p_t = 0.470$; IW pre-trend $p = 0.775$) are statistically null—qualitatively consistent with conditional size sorting without claiming an unidentified percentage share across distinct estimands.
4. **Recall-Level Unremedied Vehicle-Instance Proxy, Tesla `98.7%` Weight Disclosure, & Exact `p_WCB` Inference:** Among mature Pure-OTA campaigns ($N = 46$), Tesla accounts for **58.7% of campaigns (27/46)** and **98.7% of affected vehicle-instances** (Non-Tesla $N = 19$ averages 99.11% completion across 1.3% of instances). Holding campaign size fixed, both Pure-OTA ($-2.062$, $p_{\text{WCB}} = 0.035$) and Hybrid-OTA ($-0.666$, $p_{\text{WCB}} = 0.012$) compress unremedied residuals. Unconditionally, relative to physical hardware, Pure-OTA ($-1.918$, $p_t < 0.0001$, **$p_{\text{WCB}} = 0.065$**) and Hybrid-OTA ($+1.415$, $p_t = 0.018$, **$p_{\text{WCB}} = 0.055$**) are marginally significant at 10% under WCB while their contrast ($+3.334$) is significant at **$p_{\text{WCB}} = 0.007$**; relative to OTA-capable OEMs' dealer software, Pure-OTA is null ($-0.599$, **$p_{\text{WCB}} = 0.401$**), Hybrid-OTA is $+1.130$ (**$p_{\text{WCB}} = 0.097$**), and their contrast ($+1.729$) has **$p_{\text{WCB}} = 0.079$**.
5. **Regulatory Oversight, Pre-Recall Ramp-Up & Honest Empirical Nulls:** `Pure-OTA` has $+27.8$ pp higher FMVSS noncompliance ($p_{\text{WCB}} = 0.005$; API OTA $+15.7$ pp, $p_{\text{WCB}} = 0.042$) and `Public API OTA` has $-5.63$ pp fewer formal ODI investigations ($p_{\text{WCB}} = 0.019$). Linking 437,886 deduplicated ODI complaints documents steeper pre-recall acceleration ($2.43\times$ Pure-OTA, pre-trend Wald $p = 0.006$) alongside four transparent empirical nulls: lifecycle lag, 365-/730-day repeat cascades, acute hazard advisories, and post-recall complaint-decay DiD ($p_{\text{WCB}} \ge 0.27$).

## Reproducibility Pipeline

```powershell
# End-to-end execution
.venv\Scripts\python.exe scripts\01_download_official_sources.py
.venv\Scripts\python.exe scripts\02_audit_nhtsa_campaign_api.py
.venv\Scripts\python.exe scripts\03_build_harmonized_panels.py
.venv\Scripts\python.exe scripts\04_econometric_core_analysis.py
.venv\Scripts\python.exe scripts\05_verify_crossref_references.py
.venv\Scripts\python.exe scripts\06_generate_figures_tables.py
.venv\Scripts\python.exe scripts\08_compile_manuscript_pdf.py
.venv\Scripts\python.exe scripts\07_build_manifest.py

# Quality & integrity verification
.venv\Scripts\ruff.exe check scripts tests
.venv\Scripts\pytest.exe -v
```

## Key Deliverables

- `manuscript_d12_boost.md` — Complete English journal manuscript (`v2`, 22 Crossref-verified peer-reviewed DOIs + 2 federal institutional/regulatory citations)
- `manuscript_d12_boost.pdf` — Camera-ready compiled PDF (embedded 300-DPI figures, zero leaked tokens)
- `REFEREE_RESPONSE_v2.md` — Point-by-point referee response mapping every critique to code, econometric, table, figure, and manuscript fixes
- `figures/fig1..fig5` — 5 publication figures (`300 DPI PNG` + vector `PDF`)
- `tables/table1..table6` (including `table4b`, new `table4c_mature_ota_oem_composition.csv`, and `table5b`) — 9 zero-NaN statistical CSV tables
- `results/` — Complete JSON receipts (`api_reconciliation_audit.json`, `d12_econometric_results.json`, `step3_panel_build_summary.json`)
- `SHA256SUMS.json` & `VERIFICATION_MANIFEST.md` — Cryptographic verification manifest
