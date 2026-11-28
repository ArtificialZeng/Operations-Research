# Status & Freeze Record — Flagship `#8 K1` (`v6` *Nature Energy* `Analysis` Double-Anonymized Submission Package)

- **State:** `FROZEN_SUBMISSION_READY_V6_DAPR` (Strict *Nature Energy* `Analysis` Format · Double-Anonymized Peer Review Opt-In + Editor Cover Letter + Synchronized Named Archival Copies + Independent Reproducibility Package)
- **Author (Archival / Cover Letter Only):** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my`)
- **Revision Timestamp:** `2026-11-28`
- **Workspace:** `D:\AI_Science\antigravity\k1_boost_grid_battery_carbon_20261127`
- **Direct *Nature Energy* DAPR Upload Files (`3`):**
  1. **Blinded Main Manuscript PDF (`v6`):** `manuscript_k1_nature_energy_blinded.pdf` (`11` pages, `2,213,228` bytes, `0` leaks, `0` author/affiliation/email/metadata traces, `SHA-256: db7347a03307c7aabd57511c93f0c048c27198f70b161b2b50a54cebeaecc619`)
  2. **Blinded Supplementary Information PDF (`v6`):** `supplementary_k1_nature_energy_blinded.pdf` (`5` pages, `1,613,811` bytes, `0` leaks, `0` author/affiliation/email/metadata traces, `SHA-256: 93c6b0811fd42bb45f3c3874960cf609d218e4608094c5bdfbbd39ccd333b556`)
  3. **Editor-Only Cover Letter PDF (`v6`):** `COVER_LETTER_NATURE_ENERGY.pdf` (`2` pages, `141,988` bytes, `0` leaks, full author identity + DAPR request + disclosures, `SHA-256: d45e6bf6a51edcb6e09124a528f0261c693dcd07a1fb1f85f776fe109559a982`)
- **Synchronized Archival Named Copies (`v6`):**
  - **Named Main Manuscript PDF:** `manuscript_k1_nature_energy.pdf` (`12` pages, `2,232,436` bytes, synced to `manuscript_k1_boost.pdf`, `SHA-256: f685b25f3296e2f18ee443a3548ec054b127106f84e1f0100731241d48b95237`)
  - **Named Supplementary Information PDF:** `supplementary_k1_nature_energy.pdf` (`5` pages, `1,637,038` bytes, `SHA-256: 204dac73f637de74a7abad19469203270620337d326d8642ce309828314a3732`)
- **Independent Reproducibility Package:** `REPRODUCIBILITY.md` + `tables/*.csv` (`5` CSVs: `table1_14ba_accounting.csv`, `table2_joint_bootstrap_curtailment.csv`, `fig4_frontier_and_ercot.csv`, `table_oos_and_leadlag.csv`, `table_ercot_unit_cems_mechanism.csv`)
- **Referee Response Records:** `REFEREE_RESPONSE_v2.md` through `REFEREE_RESPONSE_v6.md`
- **Official *Nature Energy* `Analysis` & DAPR Compliance Audit (`v6`):**
  - **Abstract:** `133` words (`100–150` limit), strictly unreferenced
  - **Main Body Length:** `2,680` words (`<= 3,000` limit, excluding Abstract, Methods, References, Tables, Figure legends)
  - **Citations:** Official *Nature* superscript numbered citations strictly ordered by first appearance (`1..22`, `nature_numbered_order_ok = True`), `22/22` live Crossref HTTP-200 verified DOIs (`<= 50` guideline), adding Peplinski et al. (2026), Staadecker et al. (2024), Brander et al. (2018), and Bjørn et al. (2022)
  - **Display Items:** `4` sequential Main Figures (`Figure 1 → 4`) + `2` Main Tables = `6 <= 8`, plus separate 5-page SI PDF (`Supplementary Box 1`, `Supplementary Tables 1–6`, `Supplementary Figures 1–3`)
  - **Required *Nature Energy* Declarations:** Data availability, Code availability, Use of AI-assisted tools (Nature Portfolio disclosure), Author contributions (CRediT in Named/Cover Letter; redacted in Blinded), Competing interests, Funding
  - **DAPR Anonymity Audit:** Zero occurrences of `Zijian`, `Zeng`, `UCSI`, `Kuala Lumpur`, `Malaysia`, `foxmail`, `ucsiuniversity`, `ArtificialZeng` across BOTH extracted text AND stripped PDF metadata/XMP on both blinded PDFs
- **Independent Verification (`v6`):**
  - `ruff check scripts/ tests/`: `0` errors (`All checks passed!`)
  - `pytest -v tests/test_k1_boost.py`: `25/25` passed (`100%`)
  - `SHA256SUMS.json`: `59/59` disk-verified (`0` missing, `0` mismatches)
  - Crossref Live Citations: `22/22` academic DOIs HTTP-200 verified (`100%` two-way sync, strict `1..22` order)
  - PDF Zero-Leak & Visual Inspection Audit: `0` leaks across all 5 compiled PDFs; visually inspected Blinded Main (Pages 1, 8, 11), Blinded SI (Page 1), and Cover Letter (Pages 1–2) via `pymupdf`
- **Major `v6` Upgrades Beyond `v5`:**
  - Complete Double-Anonymized Peer Review (DAPR) Main + SI PDFs with stripped PDF metadata/XMP + dedicated editor-only Cover Letter PDF
  - Direct unit-level ERCOT EPA CEMS operating-envelope physical verification (`scripts/03d_ercot_unit_level_cems_mechanism.py`, `6,965,982` unit-hours, `351` active units, `61` `Season×Hour×Load-Quartile` matched cells: NGCT online `33.3 → 15.3` `t = -9.1`, NGCT ramp share `25.1% → 7.3%` `t = -10.2`, coal ceiling exit `41.2% → 9.9%` `t = -15.1`, coal part-load `56.1% → 68.3%` `t = +5.9`, coal ramp share `22.1% → 30.0%` `t = +7.0`), with honest disclosure of `ercot.com` HTTP 403 SCED anti-bot gates
  - P0/P1 precision fixes: `"held-out model-based estimate"` replacing `"actual"` for OOS `4.38 Mt`; `"coal's estimated marginal contribution increases under high renewable penetration"` replacing `"coal enters the margin"`; strict policy separation of `IRC Section 48E`, `GHG Protocol Scope 2`, and consequential avoided-emissions attribution
  - Official *Nature* superscript numbered citations (`1..22`) + full required *Nature Energy* declarations
