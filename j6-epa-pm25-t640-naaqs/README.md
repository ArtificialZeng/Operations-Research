# Optical Measurement Bias, Wildfire Smoke Amplification, and Regulatory Triage Under the 2024 U.S. Fine Particulate Matter Standard (`J6`)

**Status:** FROZEN SUBMISSION-READY ARCHIVE (`2026-11-26`)  
**Target Journals:** Track A (*Nature Sustainability* / *PNAS* / *Science*) & Track B (*AEJ: Economic Policy* / *JEEM* / *Management Science*)

## Overview
This archive contains the complete, reproducible physical-to-regulatory forensic pipeline, formal equilibrium model, stitched 40 CFR Part 50 Appendix N monitor histories (`2018–May 2026`), same-rooftop collocated optical (`T640_FW 636/638`) vs. gravimetric (`FRM`) and pure mass-based (`BAM 170/209`) datasets, EPA CSN/IMPROVE chemical speciation & meteorology linkages, 8 full years of satellite NOAA HMS daily wildfire smoke polygons (`2,922/2,922` calendar days, `1,471,932` site-days), official EPA PM2.5 Design Value workbook reconciliations, U.S. Census SAIPE/PEP Environmental Justice accounting, 5 publication figures (`300 DPI PNG` + vector `PDF`), 15-test regression suite, and 17-page camera-ready manuscript PDF.

### Headline Verified Findings
- **Pillar 1 — Stitched Appendix N Measurement Windfall & Zero Gravimetric Improvement:** Repairing `410` mid-2023 split-year T640 monitors (`POC`/`POC+20`) and implementing Combined-Site regulatory Appendix N (`98/99 = 99.0%` exact overlap with EPA Table 4a) proves EPA's May 2024 T640 software alignment alone flipped **`47` U.S. counties (`18.39M` residents; `49` / `19.87M` incl. SPM)** from nonattainment to attainment in `2021–2023` (`46/47` outside the West, `72.3%` Midwest+South `p = 0.032`; pop-weighted Black NH `17.0%` vs `12.9%` clean `p = 0.016`), while strictly exogenous `DV_18_20` gravimetric `FRM` PM2.5 (`+0.007 µg/m³, p_WCB = 0.951`), longitudinal `FEM → FRM` switching (`-0.030, p_WCB = 0.287`), and monitor survival (`+0.026, p_WCB = 0.358`) show clean nulls.
- **Pillar 2 — Same-Rooftop `9.5:1` Lottery, Zero-EIV Smoke Amplification, & Mie-Scattering Speciation Physics:** Across `63,951` `2023–2025` collocated `T640_FW–FRM` pairs (`69,224` through May 2026), aligned `T640_FW` retains a `+0.468 µg/m³` Design Value bias (`t = +9.17, N = 178` rooftops), driving a **`9.5:1` statutory nonattainment lottery (`19` vs `2`, exact binomial `p = 0.0002`)** vs. dead-zero pure Met One `BAM (170/209)` (`-0.021 µg/m³, p = 0.787`, `1` vs `0`). Under three EIV-free smoke instruments, `T640_FW` bias amplifies nonlinearly by **`+3.97 µg/m³ (+10.0%, p_WCB = 0.001)`** on independent other-site `>=25` days and **`+3.02 µg/m³ (+13.5%, t = +12.88)`** under satellite NOAA HMS Heavy plumes, while pure `BAM (170/209)` shows zero smoke bias (`+0.51 µg/m³, p_WCB = 0.694`; HMS Heavy `+1.17, p_WCB = 0.323`). Direct EPA speciation (`N = 14,992` pairs, `9,978` exact 0-km) pinpoints Mie scattering: `T640_FW` over-responds to organic carbon (`+0.657, t = +6.40`; `+0.287` additional under HMS Heavy `t = +2.38`) and RH (`+0.066` per `+10%`, `t = +3.13`) while under-responding to light-absorbing elemental carbon (`-0.936, t = -3.93`)—completely absent in pure BAM.
- **Pillar 3 & Killer Unification (`U1, U2, U3`):** Correcting EPA AQS's `49.9%` false-positive concurrence coding and standardizing on pre-trend-clean exogenous `DV_18_20 [8.5, 11.5]`, state Exceptional Event flagging surged **`+8.17 pp`** monitor-year (`State p_WCB = 0.004, RI p = 0.0010, LOSO 51 states [+6.81, +8.83] pp`; `67.5%` unconcurred precautionary flags) and **`+9.96 pp`** county-year (`State p_WCB = 0.003`), peaking in `2023` with transparent `2024–2025` EPA-concurred nulls. Unifying Pillars 2 and 3 directly: on identical NOAA HMS Heavy smoke days, `T640_FW` doubles same-rooftop `>35 µg/m³` exceedance triggers (`2.00×`: `52` vs `26`, **`26` vs `0` discordant days, McNemar `p = 2.98 × 10^-8`**; BAM `p = 0.688`), and inside the binding `40 CFR § 50.14` band `T640 × log(HMS Heavy)` drives `+15.2 pp` higher flagging (`State p_WCB = 0.016`) and `+0.250 µg/m³` larger claimed exclusions (`State p_WCB = 0.001`).

## Verification & Reproduction Order
1. **Verify Frozen Checksums & Automated Regression Tests First** (before rerunning scripts that regenerate outputs):
   ```powershell
   ruff check scripts/ tests/
   pytest -v tests/test_j6_boost.py
   ```
2. **Optional Full End-to-End Regeneration** (requires official EPA AQS `2018–2026`, EPA Speciation/Meteorology `2023–2025`, EPA DV Workbooks, NOAA HMS `2018–2025`, and Census SAIPE/PEP bulk files):
   ```powershell
   python scripts/00_download_external_enrichments.py
   python scripts/01_build_stitched_appn_panel.py
   python scripts/02_collocated_physics_and_speciation.py
   python scripts/03_ee_triage_and_hms_unification.py
   python scripts/04_formal_metrology_model.py
   python scripts/06_generate_figures.py
   python scripts/07_verify_citations.py
   python scripts/07a_generate_manuscript_md.py
   python scripts/08_compile_manuscript_pdf.py
   python scripts/09_generate_checksums.py
   ```

## Curated Archive Scope
Heavy raw EPA/NOAA/Census downloads and processed parquets (`~160 MB` in `data/` plus `.venv`) are omitted from git and deterministically reproducible via `scripts/00..03`. All 30 core deliverables (scripts, tests, 6 JSON receipts, 5 PNG + 5 vector PDF figures, `manuscript_j6_boost.md`, and 17-page `manuscript_j6_boost.pdf`) are pinned in `SHA256SUMS.json`.
