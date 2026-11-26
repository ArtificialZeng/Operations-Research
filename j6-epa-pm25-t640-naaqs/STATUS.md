# Status & Freeze Record — Flagship `#7 J6` (`v2` Major Revision Complete)

- **State:** `V2_MAJOR_REVISION_VERIFIED`
- **Revision Timestamp:** `2026-11-26`
- **Workspace:** `D:\AI_Science\antigravity\j6_boost_epa_pm25_t640_naaqs_20261126`
- **Manuscript PDF:** `manuscript_j6_boost.pdf` (`18` pages, `3,155,543` bytes, `SHA-256: ab21018625f2825cc6e90384a96b8786d9229a52deb979df74aebe53a5876ecf`)
- **Manuscript MD:** `manuscript_j6_boost.md` (`79,717` bytes, `10,329` words, `SHA-256 LF: cdae3746c64282db0ec8f0c73e2999382456d7dcdd053ef03beaafd4bf0d4afa`)
- **Referee Response:** `REFEREE_RESPONSE_v2.md` (`11,626` bytes, pinned in `SHA256SUMS.json`)
- **Verification Results (`v2`):**
  - `ruff check scripts/ tests/`: `0` errors (`All checks passed!`)
  - `pytest -v tests/test_j6_boost.py`: `16/16` passed (`2.46s`, including `test_16_v2_historical_tier1_screening_and_referee_recalibrations`)
  - `SHA256SUMS.json`: `31/31` disk-verified (`0` missing, `0` mismatches; manifest `SHA-256 LF: 96ea8d7c10d5533f0851581fc6245f23c901b8b4abfafd97e76ec24c3c3cd085`)
  - Crossref Live Citations: `16/16` academic DOIs HTTP-200 verified + `5` institutional/working-paper entries (`21/21` two-way sync)
  - PDF Zero-Leak Audit: `0` HTML entities, `0` raw LaTeX commands, `0` escaped dollars, `0` raw markdown bolds, `0` NaN/Inf
  - Visual Audit: Updated 300-DPI PNG figures (`fig1`, `fig3`, `fig5`) and rendered PDF pages (`1, 2, 7, 8, 10, 11, 12, 15–18`) visually inspected with zero layout defects
- **Summary of `v2` Referee Fixes Implemented:**
  1. **Design-Value Reclassification vs. Clean Air Act § 107(d) Designations:** Clarified across Abstract, Sections 1/2.1/4/7, Table 1, Figure 1, and Figure 2 that the `47` counties (`18.39M` residents) are `2021–2023` monitor Design-Value threshold reclassifications (`>= 9.1 → <= 9.0 µg/m³`), distinct from formal § 107(d) 5-factor legal designations.
  2. **Official EPA Wildfire Tier-1 5-Year Historical (`2018–2022`) 98th-Percentile Screening (New Code in Step 03) + Accurate `>35 µg/m³` Terminology:** Computed strictly out-of-sample `2018–2022` FRM 98th percentiles (`min(p98_18–22, 35)`) across `220` `T640_FW` and `99` `BAM` rooftops (`T640_FW` HMS Heavy: `168` vs. `126`, `1.33×`, `42` vs. `0` discordant, McNemar `p = 4.55 × 10^-13`, `t = +7.46`, `p_WCB = 0.002`; all days `1.66×`, `1,043` vs. `157`, `p = 7.24 × 10^-161`; `BAM` dead null, Heavy `p = 0.774`, all days `p = 0.195`). Renamed `>35 µg/m³` accurately to *24-hour NAAQS level-equivalent daily exceedance (`>35 µg/m³`)*.
  3. **EIV-Robust & Observational Speciation Recalibration:** Replaced *"strictly zero-EIV"* with *EIV-robust independent-instrument smoke amplification* (explicitly caveating Bland-Altman equal-variance assumption) and reframed CSN/IMPROVE speciation as *observational associations consistent with Mie optical theory* crediting Long, Urbanski, & Lincoln (2023) and noting controlled multi-site physical calibration experiments are required for causal correction formulas.
  4. **Pillar 3 & `U2` Causal Recalibration:** Positioned Pillar 2 + `U1` as the causal physical core; explicitly highlighted in Abstract, Section 6, Table 5, Figure 5, and Conclusion that the main `2022–2023` EE surge preceded the Feb 2024 final rule (anticipatory/designation-window flagging) and that within-county-year FE `U2` flagging is null (`+0.81 pp, p_WCB = 0.931`), explicitly refraining from any claim that optical bias causally drives strategic EE filing.
