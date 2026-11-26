# Optical Measurement Bias, Wildfire Smoke Amplification, and Regulatory Triage Under the 2024 U.S. Fine Particulate Matter Standard (`J6`)

**Status:** `v2` MAJOR REVISION COMPLETE — SUBMISSION-READY ARCHIVE (`2026-11-26`)  
**Target Journals:** Track A (*Nature Sustainability* / *PNAS* / *Science*) & Track B (*AEJ: Economic Policy* / *JEEM* / *Management Science*)

## Overview
This archive contains the complete, reproducible physical-to-regulatory forensic pipeline, formal equilibrium model, stitched 40 CFR Part 50 Appendix N monitor histories (`2018–May 2026`), same-rooftop collocated optical (`T640_FW 636/638`) vs. gravimetric (`FRM`) and pure mass-based (`BAM 170/209`) datasets, EPA CSN/IMPROVE chemical speciation & meteorology linkages, 8 full years of satellite NOAA HMS daily wildfire smoke polygons (`2,922/2,922` calendar days, `1,471,932` site-days), official EPA PM2.5 Design Value workbook reconciliations, strictly pre-period 5-year historical (`2018–2022`) EPA Wildfire Tier-1 98th-percentile screening tests, U.S. Census SAIPE/PEP Environmental Justice accounting, 5 publication figures (`300 DPI PNG` + vector `PDF`), 16-test regression suite, point-by-point referee response (`REFEREE_RESPONSE_v2.md`), and camera-ready manuscript PDF.

### Headline Verified Findings (`v2`)
- **Pillar 1 — Stitched Appendix N Monitor Design-Value Threshold Reclassifications & Zero Gravimetric Improvement:** Repairing `410` mid-2023 split-year T640 monitors (`POC`/`POC+20`) and implementing Combined-Site regulatory Appendix N (`98/99 = 99.0%` exact overlap with EPA Table 4a) shows EPA's May 2024 T640 software alignment alone shifted **`47` U.S. counties (`18.39M` residents; `49` / `19.87M` incl. SPM)** across the `2021–2023` monitor Design-Value threshold (`>= 9.1 → <= 9.0 µg/m³`)—representing **monitor Design-Value threshold reclassifications** distinct from formal Clean Air Act § 107(d) 5-factor legal designations (`46/47` outside the West, `72.3%` Midwest+South `p = 0.032`; pop-weighted Black NH `17.0%` vs `12.9%` cleanly `<= 9.0`, `p = 0.016`)—while strictly exogenous `DV_18_20` gravimetric `FRM` PM2.5 (`+0.007 µg/m³, p_WCB = 0.951`), longitudinal `FEM → FRM` switching (`-0.030, p_WCB = 0.287`), and monitor survival (`+0.026, p_WCB = 0.358`) show clean nulls.
- **Pillar 2 & `U1` (Causal Physical Core) — Same-Rooftop `9.5:1` DV Lottery, EIV-Robust Smoke Amplification, Observational Speciation, & Historical Tier-1 Screening Divergence:** Across `63,951` `2023–2025` collocated `T640_FW–FRM` pairs (`69,224` through May 2026), aligned `T640_FW` retains a `+0.468 µg/m³` Design Value bias (`t = +9.17, N = 178` rooftops), driving a **`9.5:1` Design-Value threshold classification lottery (`19` vs `2`, exact binomial `p = 0.0002`)** vs. dead-zero pure Met One `BAM (170/209)` (`-0.021 µg/m³, p = 0.787`, `1` vs `0`). Via EIV-robust independent instruments, `T640_FW` bias amplifies nonlinearly by **`+3.97 µg/m³ (+10.0%, p_WCB = 0.001)`** on independent other-site `>=25` days and **`+3.02 µg/m³ (+13.5%, t = +12.88)`** under satellite NOAA HMS Heavy plumes, while pure `BAM (170/209)` shows zero smoke bias (`+0.51 µg/m³, p_WCB = 0.694`; HMS Heavy `+1.17, p_WCB = 0.323`). Observational EPA speciation (`N = 14,992` pairs, `9,978` exact 0-km) matches Mie optical theory and Long, Urbanski, & Lincoln (2023): `T640_FW` covaries positively with organic carbon (`+0.657, t = +6.40`; `+0.287` additional under HMS Heavy `t = +2.38`) and RH (`+0.066` per `+10%`, `t = +3.13`) and negatively with elemental carbon (`-0.936, t = -3.93`)—absent in BAM—with controlled multi-site calibration experiments needed for causal correction formulas. Sitting two meters apart under NOAA HMS Heavy smoke (`U1`), `T640_FW` doubles **24-hour NAAQS level-equivalent daily exceedances (`>35 µg/m³`)** (`2.00×`: `52` vs `26`, **`26` vs `0` discordant, McNemar `p = 2.98 × 10^-8`**; BAM `p = 0.688`) and increases exceedances of **EPA's Wildfire Tier-1 5-year historical (`2018–2022`) FRM 98th-percentile threshold (`min(p98_18–22, 35)`)** by **`1.33×`** (`168` vs `126`, **`42` vs `0` discordant, McNemar `p = 4.55 × 10^-13`**, `t = +7.46, p_WCB = 0.002`; `1.66×` across all paired days, `1,043` vs `157`, `p = 7.24 × 10^-161`; BAM dead null across all strata, Heavy `p = 0.774`, all days `p = 0.195`).
- **Pillar 3 & Observational `U2`/`U3`:** Correcting EPA AQS's `49.9%` false-positive concurrence coding and standardizing on pre-trend-clean exogenous `DV_18_20 [8.5, 11.5]`, state Exceptional Event flagging rose **`+8.17 pp`** monitor-year (`State p_WCB = 0.004, RI p = 0.0010, LOSO 51 states [+6.81, +8.83] pp`; `67.5%` unconcurred precautionary flags) and **`+9.96 pp`** county-year (`State p_WCB = 0.003`), driven primarily by **anticipatory/designation-window retroactive flagging in `2022–2023` prior to the Feb 2024 final rule** with transparent `2024–2025` EPA-concurred nulls. Cross-monitor `U2` finds positive observational associations between T640 and heavy-smoke flagging (`+15.2 pp`, `State p_WCB = 0.016`) and claimed exclusions (`+0.250 µg/m³`, `State p_WCB = 0.001`), **but the within-county-year FE flagging comparison is null (`+0.81 pp, p_WCB = 0.931`)**; accordingly, the manuscript explicitly makes **no claim** that optical bias causally drives strategic EE filing.

## Verification & Reproduction Order
1. **Verify Frozen Checksums & Automated Regression Tests First:**
   ```powershell
   ruff check scripts/ tests/
   pytest -v tests/test_j6_boost.py
   ```
2. **Optional Full End-to-End Regeneration:**
   ```powershell
   python scripts/00_download_external_enrichments.py
   python scripts/01_build_stitched_appn_panel.py
   python scripts/02_collocated_physics_and_speciation.py
   python scripts/03_ee_triage_and_hms_unification.py
   python scripts/04_formal_metrology_model.py
   python scripts/06_generate_figures.py
   python scripts/07a_generate_manuscript_md.py
   python scripts/07_verify_citations.py
   python scripts/08_compile_manuscript_pdf.py
   python scripts/09_generate_checksums.py
   ```

## Curated Archive Scope
Heavy raw EPA/NOAA/Census downloads and processed parquets (`~160 MB` in `data/` plus `.venv`) are omitted from git and deterministically reproducible via `scripts/00..03`. All 31 core deliverables (scripts, tests, 6 JSON receipts, 5 PNG + 5 vector PDF figures, `manuscript_j6_boost.md`, `manuscript_j6_boost.pdf`, and `REFEREE_RESPONSE_v2.md`) are pinned in `SHA256SUMS.json`.
