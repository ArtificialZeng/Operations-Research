# Status & Freeze Record — Flagship `#6 I4` (SEC Rule 35d-1 "80% Names Rule", Major Revision `v4`)

- **State:** `FROZEN_SUBMISSION_READY_V4`
- **Revision Timestamp:** `2026-11-28` (Referee-Driven Major Revision `v4`, *Journal of Banking & Finance* Architecture)
- **Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)
- **Workspace:** `D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126`
- **Main Manuscript PDF:** `manuscript_i4_boost.pdf` (`12` pages, `2,130,777` bytes, `SHA-256: C55F67B906EA7C3490B13B719A16B3BEA48E85AE9F93DEE6D8685B7B530DFA41`)
- **Supplementary Data Appendix PDF:** `supplementary_i4_jbf.pdf` (`4` pages, `646,737` bytes, `SHA-256: 78C8E2C64788989620A4D3AD83BB181BB287CBC2AB9F6857271C78A4C30695E5`)
- **Referee Response:** `REFEREE_RESPONSE_v4.md` (`15,789` bytes, `SHA-256: 44FB6D82F945F17CE3F3D18103DC558C8B3857D71AD78E92E05936D18514BCBD`)
- **Independent Verification (`v4`):**
  - `ruff check scripts/ tests/`: `0` errors (`All checks passed!`)
  - `pytest -v tests/test_i4_boost.py`: `11/11` passed (`100%`, covering zero-NaN/Inf invariants, N-PORT redemption-sign fix, repaired Capital Income Builder & Income Fund of America historical look-through splits, FWL absorbed-FE equivalence to 1e-12, 50-renamer + 50-retained + 164-unregulated per-fund EDGAR audit, sharp partial-identification bounds + 4-point multi-quarter paths, 15/15 null placebos + Rambachan–Roth + Callaway–Sant'Anna cohort audits, 300-DPI figures, live citations & authorship zero-leak check, and PDF zero-leak + `SHA256SUMS.json` disk sync)
  - `SHA256SUMS.json`: `70/70` disk-verified (`0` missing, `0` mismatches; LF-normalized for all text artifacts)
  - Live Citations (`scripts/07_verify_citations.py`): `19/19` academic DOIs HTTP 200 live via Crossref (incl. Callaway & Sant'Anna 2021, Rambachan & Roth 2023, Espenlaub et al. 2017, He, Wang, & Ward 2025 `10.2139/ssrn.5844262`, Imbens & Manski 2004) + `6/6` official SEC URLs HTTP 200 (`IC-24828`, `33-11238/IC-35000`, `2025–26 Names Rule FAQs`, `33-11368/IC-35500`, `IC-35963`, `Press Release 2026-19`); `100%` two-way citation sync
  - PDF Zero-Leak & Visual Audit: `0` leaked tokens across all `12` pages of `manuscript_i4_boost.pdf` and all `4` pages of `supplementary_i4_jbf.pdf`; all figures, tables (Tables 1–5, A1, B1, C1, C2), formulas, and references visually inspected via `pymupdf` PNG renders
- **Verified Scope & Methodological Guardrails:**
  - Strict descriptive / institutional manager-choice framing wherever causal identification fails (`49/50` pre-June-11 effective dates, `36/50` not due on-cycle until 2027, `FAQ2 p = 0.043` & `FAQ4 p = 0.003` pre-trend rejections, narrow Rambachan–Roth breakdown thresholds $M^* \in [0.002, 0.018]$, $\bar{M}^* \in [0.02, 0.18]$, null Callaway–Sant'Anna early-vs-late large cohort contrast in `26Q2–Q3`, and `35/50` Growth/Value strictly labeled a lexical screen with `8.6%` precision against Pass-2 fund-scoped 35d-1 mentions)
  - Investor flows (`7` numeric funds across `3` complexes, `p_WCB = 0.170`, Wilcoxon `p = 0.375`) strictly bounded as exploratory descriptive evidence with zero investor-welfare or comprehension claims
  - Full staggered causal evaluation of binding on-cycle enforcement awaits `2026Q3–2027Q4` N-PORT and `485BPOS` filings
- **No Unauthorized Edits:** Do not modify any verified artifact in this directory after freeze.
