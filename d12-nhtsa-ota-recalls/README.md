# D12 Boost: The Software-Defined Vehicle Recall Paradox

**Full Publication-Grade Empirical Operations Management & Regulatory Safety Study**
**Target Journals:** *Management Science* (Operations Management / Information Systems) / *Manufacturing & Service Operations Management (M&SOM)*

## Overview

This self-contained repository executes an end-to-end empirical investigation of over-the-air (OTA) wireless software recalls versus dealer-remedied software and physical hardware recalls across the complete U.S. automotive fleet (2015–2026), integrating four official U.S. federal datasets:

1. **NHTSA ODI Complete Recalls Flat File (`FLAT_RCL_POST_2010.zip`):** 10,559 Vehicle campaigns (2015–2026); 7,967 in 2018–2026 across 646 canonicalized corporate OEM entities (32 OTA-capable OEMs; 21 light-duty passenger-vehicle OEMs).
2. **U.S. DOT Official Completion-Rate Registry (`6axg-epim`):** 30,484 rows; 7,385 rated 2018–2026 Vehicle campaigns; 6,412 statutory mature ($\ge 18$-month) campaigns covering 228.43 million recalled vehicles.
3. **Live NHTSA Campaign Ground-Truth API (`api.nhtsa.gov/recalls/campaignNumber`):** 1,452 audited campaigns (100% of 1,202 software/OTA candidates + 250 stratified physical campaigns; 0 HTTP errors).
4. **NHTSA ODI Consumer Complaints (`2020–2026`):** 437,886 unique consumer complaints (`ODINO`) across 636,875 component-level records, strictly deduplicated by `(campaign, ODINO)` and linked at exact `(Make, Model, ModelYear, Component)` level into a 114,000-row balanced `[-12m, +12m]` event-study panel (4,560 campaigns).

## Headline Verified Findings

1. **Silent May 8, 2025 NHTSA API Cutoff:** Official `overTheAirUpdate` matched audited remedy text on **54/54 (100.0%)** in 2019–2023 and **31/33 (93.9%)** in 2024 (with **0/250 = 0.0%** physical false negatives), drifted to **4/7 (57.1%)** during Jan 1–May 8, 2025, and **stopped completely after `25V282000` (May 8, 2025): 0/68 (0.0%)** across all subsequent 2025–2026 OTA recalls (`71/75` across all of 2025–2026). Passive-voice and strictly remedy-based classification separates **61 Pure-OTA**, **101 Hybrid-OTA** (92 pure software-choice, 9 hardware-mixed), **984 Dealer-Software**, and **6,821 Physical-Hardware** campaigns.
2. **Blast-Radius Concentration = ~85–90% Endogenous Fixed-Cost Selection:** Within-OEM `Hybrid-OTA` recalls are **$7.01\times$ larger** ($+1.947$ log points, $t = 5.32$, $p_{\text{WCB}} = 0.006$; Official API OTA 2018–2024 $+1.887$, $p_{\text{WCB}} = 0.039$) than `Dealer-Software`, whereas `Pure-OTA` shows no significant within-OEM size premium ($+1.084$, $p_{\text{WCB}} = 0.233$). Unconditional TWFE ITT staggered adoption DiD ($+0.176$, $p_{\text{WCB}} = 0.579$; pre-trend $p = 0.424$), fully saturated **Sun–Abraham (2021) cohort $\times$ relative-time IW** ($-0.532$, $p = 0.470$; IW pre-trend $p = 0.775$), and unconditional Software $\times$ SDV Cohort ($\text{MY} \ge 2021$) DiD ($+0.262$, $p_t = 0.064$) confirm ~85–90% endogenous fixed-cost selection.
3. **Eradication of the Vehicle-Age Compliance-Decay Cliff:** Mature `Dealer-Software` completion collapses by **$-3.57$ pp/yr** ($p_{\text{WCB}} = 0.001$) as vehicles age (`90.3% -> 63.6%`), whereas `Pure-OTA × Age` ($+3.08$ pp/yr, $p_{\text{WCB}} = 0.039$) eliminates **86.3%** of decay (`99.3% -> 97.4%` at 6+ yr), `Hybrid-OTA × Age` ($+2.25$ pp/yr, $p_{\text{WCB}} = 0.044$) eliminates **63.0%**, and `Official API OTA × Age` ($+2.74$ pp/yr, $p_{\text{WCB}} = 0.002$) eliminates **77.0%**.
4. **Sample-Matched Break-Even Frontier & Hybrid-OTA Safety Trap:** Anchored to OTA-capable OEMs' 85.71% mature Dealer-Software baseline, `Pure-OTA` achieves **99.18% mean (99.99% median)** completion—clearing its 97.34% frontier by $+1.84$ pp and slashing net unremedied exposure by **85.3%** ($-1.918$ log points vs. physical recalls, $p_t < 0.0001$; Light-Duty Non-Tesla Pure-OTA $-3.395$, $p_{\text{WCB}} = 0.029$; median **3.9** unremedied vehicles; 0.14% of U.S. unremedied fleet despite 4.00% of affected vehicles). `Legacy Hybrid-OTA` stops at **95.66%** (`Hybrid_SW_Choice` **95.41%**)—falling **$-2.53$ pp ($-2.76$ pp) below** its 98.19% break-even frontier and leaving **364.0 (442.6 SW-choice) median unremedied vehicles** ($+3.334$ log points above Pure-OTA across all vehicles, Wald $p < 0.00001$).
5. **Regulatory Oversight, Pre-Recall Ramp-Up & Honest Empirical Nulls:** `Pure-OTA` has $+27.8$ pp higher FMVSS noncompliance ($p_{\text{WCB}} = 0.005$; API OTA $+15.7$ pp, $p_{\text{WCB}} = 0.042$) and `Official API OTA` has $-5.63$ pp fewer formal ODI investigations ($p_{\text{WCB}} = 0.019$). Linking 437,886 deduplicated ODI complaints documents steeper pre-recall acceleration ($2.43\times$ Pure-OTA, pre-trend Wald $p = 0.006$) alongside four transparent empirical nulls: lifecycle lag ("sell first, fix later"), 365-/730-day repeat cascades, acute hazard advisories, and post-recall complaint-decay DiD ($p_{\text{WCB}} \ge 0.27$).

## Reproducibility Pipeline

```powershell
# Isolated environment
uv venv .venv
uv pip install --python .venv\Scripts\python.exe numpy pandas scipy statsmodels requests matplotlib seaborn pytest ruff pypdf pymupdf

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
.venv\Scripts\pytest.exe -q
```

## Key Deliverables

- `manuscript_d12_boost.md` — Complete English journal manuscript (22 Crossref-verified peer-reviewed DOIs, 100% cited in body text)
- `manuscript_d12_boost.pdf` — Camera-ready compiled PDF (embedded 300-DPI figures, zero leaked tokens)
- `figures/fig1..fig5` — 5 publication figures (`300 DPI PNG` + vector `PDF`)
- `tables/table1..table6` (including `table4b` and `table5b`) — 8 zero-NaN statistical CSV tables
- `results/` — Complete JSON receipts (`api_reconciliation_audit.json`, `d12_econometric_results.json`, `step3_panel_build_summary.json`)
- `SHA256SUMS.json` & `VERIFICATION_MANIFEST.md` — Cryptographic verification manifest
