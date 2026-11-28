# F7 (`v4`) — Notice-Level Duties, Verbatim Channel Classification, and Institutional Governance in U.S. Third-Party E-Commerce Product Recalls (2000–2026)

**Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)  
**Workspace Root:** `D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\`  
**Compiled PDFs (Zero Leaked Tokens):**
- Main Manuscript: [`manuscript_f7_boost.pdf`](file:///D:/AI_Science/antigravity/f7_boost_cpsc_ecommerce_recalls_20261126/manuscript_f7_boost.pdf)
- Supplementary Material: [`supplementary_f7_jcp.pdf`](file:///D:/AI_Science/antigravity/f7_boost_cpsc_ecommerce_recalls_20261126/supplementary_f7_jcp.pdf)
- Revision Audit Log: [`REFEREE_RESPONSE_v4.md`](file:///D:/AI_Science/antigravity/f7_boost_cpsc_ecommerce_recalls_20261126/REFEREE_RESPONSE_v4.md)

## Overview

Using the complete 27-year official U.S. Consumer Product Safety Commission (CPSC) SaferProducts Recall Census (`2000–2026`, `N = 8,386` unique notices; strict post-emergence contract era `2022–2026`, `N = 1,822` classified microdata notices across `G = 1,414` independent firm clusters), this study builds an auditable verbatim channel taxonomy, a five-dimensional structured remedy-duty dataset, a verifiable `N = 150` stratified rule-plus-author coding audit with group-specific error rates and Clopper–Pearson misclassification bounds, and a side-by-side comparison across all channel definitions:

- **Verbatim Amazon Channel Audit (`scripts/parser_lib.py::classify_amazon_channel_3way`):** Resolves asymmetric multi-channel conflation inside legacy `amazon_only_mkt` (`51/391` other-flagged-platform notices [`13/264` China-direct vs. `38/127` U.S.-entity] and `100/391` total multi-channel online/DTC notices [`26/264` vs. `74/127`], `162/601` across `2022–2026` including Anker and OCOOPA) into three mutually exclusive categories: `strict_amazon_exclusive` (`441`), `multi_channel_with_amazon` (`440`: `164` online + `276` omnichannel), and `amazon_channel_ambiguous` (`5`: Amazon Fire TV `9234` + `4` CPSC clerical conflicts).
- **Side-by-Side Channel Definitions (`results/09_v4_channel_remedy_audit.json`):**
  - *All-Channel `2022–2026` (`N = 1,822`, `G = 1,414`):* `1_Mkt_FD_China` vs. Brick-and-Mortar `+35.33 pp` literal `photo_language` / `-35.07 pp` `direct_return` (`p_WCB = 0.001`); within-marketplace `FD − U.S.` `+28.68 pp` / `-13.78 pp`; Strict Durables `>= $100` (`N = 685`): `+41.42 pp` vs. B&M (`+36.27 pp` within-marketplace).
  - *Def 1 Broad Mkt-Amazon CS (`N = 391`, `38` cells):* `photo_language = +13.72 pp (p_WCB = 0.027)`, `direct_return = -8.20 pp (p_WCB = 0.021)`.
  - *Def 2a Excl. Other Flagged 3P Platforms CS (`N = 313`, `34` cells):* `photo_language = +10.89 pp [-3.03, +24.80] (p_WCB = 0.121)`, `direct_return = -7.00 pp [-14.73, +0.74] (p_WCB = 0.097)`.
  - *Def 2b Verbatim Strict Amazon-Exclusive CS (`N = 236`, `25` cells):* `photo_language = +10.70 pp [-5.56, +26.96] (p_WCB = 0.226)` (wide CI crossing zero, transparently reported as specification-sensitive), `direct_return = -10.76 pp (p_WCB = 0.044)`, `physical_destruction = +15.24 pp (p_WCB = 0.035)`.
  - *Def 3 Multi-Channel Online (`N = 138` full; underpowered fine-cell CS `N = 55` in Supplementary Appendix B):* `photo_language = +15.99 pp (p_WCB = 0.088)`.
- **Structured 5D Remedy-Duty Coding, Edge Cases & Bounded Misclassification (`tables/table_remedy_duty_coding_audit.csv`):** Explicitly benchmarks **Jugader (`9924`)** (`optional_or_alternative_proof`, `photo_mandatory = 0`) and **UVIPC (`10148`)** (`destruction_proof_without_photo = 1`, `physically_disabled = 1`). Verbatim inspection of `N = 150` stratified notices documents `24/150` real discrepancies and higher false-negative rates on heterogeneous U.S.-entity wording—showing via Rogan–Gladen and 95% Clopper–Pearson bounds that differential measurement error strengthens the `direct_return` deficit (`-13.78 → -24.08 pp` all-channel; `-10.76 → -19.41 pp` strict Amazon-exclusive) while explaining much of the raw cross-border gap in narrow physical-disablement and permanent-marking clauses.
- **Standalone Institutional Evidence:** `67/74` China-direct hazardous-product notices assigning consumer self-disposal (`0.0%` firm direct return) list `3,947,390` affected units (**notice coverage only**, NOT observed waste stream), `67.34%` concentrated in multi-channel OCOOPA (`1.500M`) and Anker (`1.158M`), with `54/67` complete notices (`3,910,951` units, `99.08%`) carrying explicit HHW warnings. *In re Amazon.com* is framed strictly as an institutional case study (`0/601` explicit `"Fulfilled by Amazon"` mentions; `1/601` standalone `"FBA"` model suffix on TADAKAZU `10317`; Jul 2024 HAC `L=4` slope `+0.1831/qtr` broad vs. `+0.1734/qtr` strict Amazon-exclusive).

## Reproducible Pipeline

All scripts run deterministically inside `.venv`:

```powershell
$PY = "D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\.venv\Scripts\python.exe"
& $PY scripts\01_fetch_cpsc_census.py
& $PY scripts\02_parse_and_audit.py
& $PY scripts\03_formal_theory_model.py
& $PY scripts\04_pillar1_contract_econometrics.py
& $PY scripts\05_pillar2_3_4_mechanisms_shocks_safety.py
& $PY scripts\06_verify_references_crossref.py
& $PY scripts\09_remedy_duty_audit_and_channel_v4.py
& $PY scripts\07_generate_figures_and_tables.py
& $PY scripts\10_build_v4_manuscript_and_supplement.py
& $PY scripts\08_compile_manuscript_pdf.py
& D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\.venv\Scripts\ruff.exe check scripts tests
& D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\.venv\Scripts\pytest.exe -v
```
