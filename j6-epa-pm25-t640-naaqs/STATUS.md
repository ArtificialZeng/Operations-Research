# Status & Freeze Record — Flagship `J6` (`v4` *Environmental Science & Technology* Revision Complete)

- **State:** `V4_EST_SUBMISSION_READY`
- **Revision Timestamp:** `2026-11-28`
- **Workspace:** `D:\AI_Science\antigravity\j6_boost_epa_pm25_t640_naaqs_20261126`
- **Main Manuscript PDF:** `manuscript_j6_boost.pdf` (`12` pages, `2,326,084` bytes, `0` leaked tokens, `SHA-256: 5fd65efa26054e578d2eb783f1e4658355e53e6886b08ccbdab73beb51c08abf`)
- **Supporting Information PDF:** `supplementary_j6_est.pdf` (`4` pages, `978,745` bytes, `0` leaked tokens, `SHA-256: 9abbf35b4334d814d4a2cb9060bd9edbf4baf57a3a4842a038448ab4bb32eb6b`)
- **Main Manuscript MD:** `manuscript_j6_boost.md` (`53,936` bytes, `7,580` words)
- **Supporting Information MD:** `supplementary_j6_est.md` (`11,739` bytes, `1,692` words)
- **Referee Response:** `REFEREE_RESPONSE_v4.md`
- **Reproducible Exports (`tables/`):** `collocated_heavy_smoke_pairs_2023_2025.csv` (`673` rows), `aqs_and_threshold_version_manifest.csv` (`19` artifacts), `table1`–`table4` CSVs
- **Core Receipts (`results/`):** `10_official_tier_replay.json`, `11_v4_est_comprehensive_audit.json`, `07_citations_verified.json` (`15/15` live Crossref DOIs, `21/21` two-way sync), plus legacy archived receipts (`00`–`04`)
- **Publication Figures (`figures/`):** 4 Main *ES&T* figures (`fig1`–`fig4`, 300-DPI PNG + vector PDF) + 2 SI figures (`figS1`, `figS2`), all visually verified zero-overlap
- **Summary of `v4` Upgrades (Per `J6.md`):**
  1. **P0 #1 Common-Support Audit:** Audited exact `4` Heavy triples (`401` all-day triples, `27` overlapping dates), computed overlap-matched & overlap-weighted (`29` `Region × FRM-bin` cells) differential CIs (`+7.93` to `+11.24 pp`), and demoted `BAM–FRM` to background reference comparator.
  2. **P0 #2 Out-of-Time Prospective Official EPA Tier-1 Replay:** Implemented exact EPA-457/R-24-001 formula (`1.5 × min(5-yr same-month P98, min of 5 annual P98s)`) on rolling certified 5-year windows (`2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`) across `OOT-A/B/B2/C` (`+5.57` to `+7.07 pp`, `26–33` vs. `0`, all 2-way `p <= 0.002`; BAM null) alongside pinned official `2021–2025` replay (`123` vs. `89`, `+7.26 pp`) and bidirectional / near-threshold (`±10%`/`±20%`) audit.
  3. **P1 #3 Ground-Level Smoke Specificity, Non-Smoke Controls & 2-Way Inference:** Added two-way CGM `Site × Region-Smoke-Episode` (`[+3.43, +11.10] pp`), year-by-year (`+6.77/+6.41/+8.08 pp`), leave-EPA-region-out (`[+6.33, +9.15] pp`), equal-concentration non-smoke controls (`HMS = 0` vs. `3`, `p < 10⁻⁴`–`10⁻¹⁵`), and independent surface `PM₂.₅` anomaly & `OC ≥ 5 µg/m³` confirmation.
  4. **P1 #4 *ES&T* Restructure & SI Separation:** Focused main text strictly on collocated metrology & screening thresholds; moved `47`-county screening-level monitor DV reclassifications and observational EE flagging nulls cleanly into `supplementary_j6_est.pdf`.
