# Project Status — F7 (`v4` Submission-Ready Revision)

- **State:** `COMPLETE — v4 REVISION VERIFIED AGAINST F7.md PEER REVIEW, SUBMISSION-READY`
- **Build Date:** `2026-11-28` (`v4` Revision)
- **Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)
- **Workspace:** `D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\`
- **Access-Control Ethics:** 100% compliant — exclusively queried open HTTP-200 official APIs (`saferproducts.gov/RestWebServices/Recall?format=json` and `api.crossref.org/works/{doi}`). Zero HTTP-403 endpoints touched; `revisions_v3` read-only and untouched.
- **Peer-Review Compliance (`F7.md`, 2026-11-28):**
  - **P0 #1 (3-Way Verbatim Amazon Channel & Side-by-Side Reporting):** Fixed legacy `amazon_only_mkt` conflation (`51/391` other-flagged-platform & `100/391` multi-channel online/DTC notices including Anker & OCOOPA; `162/601` across `2022–2026`); reproduced exact reviewer benchmark (`N = 313`, `photo_language = +10.89 pp, p_WCB = 0.121`, `direct_return = -7.00 pp, p_WCB = 0.097`) alongside Broad (`N = 391`), Verbatim Strict Amazon-Exclusive (`N = 236`, `photo_language = +10.70 pp, p_WCB = 0.226`, `direct_return = -10.76 pp, p_WCB = 0.044`), Multi-Channel Online (`N = 138` full; underpowered CS `N = 55` in Appendix B), and All-Channel (`N = 1,822`, Strict Durables `>= $100` `N = 685`).
  - **P0 #2 (Verifiable `N = 150` Stratified Remedy-Duty Audit, `Jugader` & `UVIPC`, Misclassification Bounds):** Published `tables/table_remedy_duty_coding_audit.csv` (`N = 150`, `24/150` genuine discrepancies documented verbatim), unit-tested Jugader (`9924`) and UVIPC (`10148`), quantified group-specific error rates (`1_Mkt_FD_China` vs. `3_Mkt_True_US`) with exact Clopper–Pearson 95% CIs and Rogan–Gladen bounded misclassification intervals, and candidly framed validation as an automated rule-plus-author structured audit.
  - **P0 #3 (Restructured Main Manuscript + Supplement + Live Citations):** Rebuilt dynamically (`scripts/10_build_v4_manuscript_and_supplement.py`, zero hardcoded numbers) with standalone Section 4 for `3,947,390` hazardous-product notice coverage (`67.34%` OCOOPA+Anker, `54/67` full-notice HHW warnings covering `3,910,951` units [`99.08%`], never waste stream) and *In re Amazon.com* institutional case study (`0/601` explicit FBA wording, `1/601` TADAKAZU token; Broad vs. Strict-Exclusive HAC slopes `+0.1831/qtr` vs. `+0.1734/qtr`); 22/22 live Crossref-verified journal DOIs (including Raithel et al. 2024 [online 2023] `10.1007/s11747-023-00967-x` and Fang et al. 2026 `10.1287/mksc.2025.0618`).
- **Artifacts Generated & Verified:**
  - Frozen raw census (`N = 8,386`): `data/cpsc_recalls_2000_2026.json`
  - Enriched v4 parsed census (`N = 8,386`): `data/cpsc_parsed_2000_2026.csv`
  - Pipeline scripts: `scripts/01_*.py`–`scripts/10_*.py`, `scripts/parser_lib.py`, `scripts/econometrics_lib.py`
  - JSON receipts: `results/01_fetch_manifest.json`–`results/06_verified_references.json`, `results/09_v4_channel_remedy_audit.json`
  - Zero-NaN CSV tables: `tables/table_remedy_duty_coding_audit.csv`, `tables/table_v4_*.csv` (5 v4 tables), plus preserved legacy `table1`–`table7` & `table_parser_audit_150.csv`
  - 6 publication-grade figures (`300 DPI PNG` + vector `PDF`): `fig1_sample_flow_and_channel_audit`, `fig2_three_definition_channel_comparison`, `fig3_regime_emergence_and_diffusion`, `fig4_hazwaste_coverage_and_in_re_amazon`, `fig5_robustness_forest_and_platforms`, `fig2_theory_equilibrium_and_archetype_gaps`
  - Compiled zero-leak PDFs: `manuscript_f7_boost.pdf`, `supplementary_f7_jcp.pdf`
  - Audit & Manifest: `REFEREE_RESPONSE_v4.md`, `tests/test_f7_boost.py`, `SHA256SUMS.json`
