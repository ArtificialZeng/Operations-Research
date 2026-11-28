# STATUS — H6f Flagship Build (`v4` *Scientometrics* Original Research Revision)

- **Title:** *Version-Level Measurement, Incremental Predictive Validity, and Revision Trajectories of Public Peer-Review Assessments in eLife Reviewed Preprints*
- **Author:** Zijian Zeng (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)
- **Build Date:** 2026-11-28 (Major Revision `v4`)
- **Status:** `VERIFIED_SUBMISSION_READY_V4`
- **Main Manuscript:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126\manuscript_h6f_boost.pdf` (14 pages, 0 leaked tokens)
- **Supplementary Information:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126\supplementary_h6f_scientometrics.pdf` (6 pages, 0 leaked tokens)
- **Referee Response:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126\REFEREE_RESPONSE_v4.md`
- **Read-Only Directories / Git Touched:** None (`0` writes outside primary workspace)

## Completed Gates (`v4`)

- [x] **P0 #1 — Strict `v1` Covariate Freezing + Non-VoR Validation + OpenAlex Citing-Work ID Deduplication Audit:**
  - Fixed author look-ahead leakage (`368/2,285` VoRs; exact benchmark parity `-14.03% -> -13.74% [-18.97%, -8.18%]`) and primary-subject drift (`441/4,551` manuscripts); re-estimated all primary models with strictly frozen `v1` covariates (`v1_n_authors`, `v1_primary_subject`, `v1_quarter`/`v1_month`, `v1_posting_day`).
  - Validated equal-length next-full-calendar-year and post-`v1` citations across All-`v1` (`N = 2,635`: `-22.59%`, `+3.09` pp pseudo-$R^2$), VoR-only (`N = 2,309`: `-18.22%`), and Non-VoR-only (`N = 338`: `-30.12%` post-`v1`, `p = 0.0495`; `-33.81%` next-year all-DOI under subject-year FE, `p = 0.050`).
  - Executed stratified `N = 200` OpenAlex citing-work ID deduplication audit (`data/openalex_citing_dedup_audit.json`), discovering `98.3%` VoR consolidation vs. `95.0%` Non-VoR work splitting, `r = 0.99979` (eLife-only) / `r = 0.99672` (all-DOI), and PPML audit parity (`-27.28%` union vs. `-26.21%` yearly-max).
- [x] **P0 #2 — Strict Predictive-Association Framing & Transparent Precision:**
  - Documented *eLife*'s June 2024 phased discoverability redesign (`8f427668`); removed all causal badge-display claims and all "zero return" language; reported exact upgrade CIs (`+3.2% [-10.7%, +19.2%]` benchmark; `+8.6% [-9.3%, +30.0%]` strict `v1`) with exact multiplicative TOST (`±15%` & `±20%`).
- [x] **P0 #3 — Clean Separation of Exploratory Indexing / Geographic / ID-Velocity Material:**
  - Removed country shares, ID-velocity (`-56.3%`), and synthetic controls completely from the Abstract and moved all indexing-shock material cleanly into `supplementary_h6f_scientometrics.pdf` with explicit disclosure of `166/514` cross-announcement overlap, dual WoS & Scopus scope, and null subject-adjusted 450d contrasts (`-2.76 pp [-7.54, +2.02]`, `-3.47 pp [-10.84, +3.90]`).
- [x] **Live Citations & Visual / Code Verification:**
  - `31/31` peer-reviewed Crossref DOIs HTTP 200 verified (including Mutz et al., 2025 *Scientometrics* `10.1007/s11192-025-05422-y` and Ragusa et al., 2025 `10.7554/eLife.102324`) + verified live *eLife* notices (`16afe6ec`, `c11c6101`, `ae620829`, `8f427668`, `e9d530fc`, `7da92a51`).
  - All 4 Main + 3 Supplementary figures generated 100% dynamically, embedded into both PDFs, and visually verified across all 20 rendered pages (`14` main + `6` SI) via `pymupdf` + `read_file`.
  - `ruff check scripts tests` (`0` errors), `pytest -v tests/test_h6f_boost.py` (`100%` passing), `SHA256SUMS.json` 100% matched to live disk bytes.
