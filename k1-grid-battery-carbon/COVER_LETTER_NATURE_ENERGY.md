# Cover Letter — Submission to *Nature Energy* (Analysis)

**Date:** November 28, 2026  
**To:** The Editors, *Nature Energy*  
**Manuscript Title:** Counterfactual carbon accounting and congestion-constrained abatement limits of U.S. utility-scale battery storage  
**Article Type:** Analysis  
**Peer Review Option Requested:** **Double-anonymized peer review (DAPR)**

**Corresponding & Sole Author:**  
Zijian Zeng  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
Email: zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

Dear Editors,

Please consider the enclosed manuscript, *Counterfactual carbon accounting and congestion-constrained abatement limits of U.S. utility-scale battery storage*, for publication as an **Analysis** in *Nature Energy*. I formally opt into **double-anonymized peer review**: both the submitted main manuscript (`manuscript_k1_nature_energy_blinded.pdf`) and the Supplementary Information (`supplementary_k1_nature_energy_blinded.pdf`) have been fully anonymized—with all author identity, institutional affiliation, contact details, repository usernames, and embedded PDF document metadata removed—for reviewer blinding.

### Why this Analysis fits *Nature Energy*

Utility-scale battery storage has expanded rapidly to 56.6 GW (156.0 GWh) across 36 U.S. balancing authorities by October 2026, yet prior evidence on storage carbon impacts has relied largely on dispatch simulations or single-market correlations. Linking 49.77 TWh of reconciled real-world battery discharge across 14 metered U.S. grids to hourly EPA Continuous Emissions Monitoring System (CEMS) smokestack emissions (2024-07 to 2026-09), this Analysis delivers three policy-relevant empirical findings:

- **Counterfactual Carbon-Accounting Discrepancy & Unconditional Error Boundaries:** On identical historical dispatch under zero curtailment absorption, consumption-weighted Average Emission Factors (-3.75 Mt CO2) and generator-stack marginal emission factors (+3.69 Mt CO2) disagree by **+7.44 Mt CO2**, reversing sign in 9/14 grids. Full unconditional season-stratified 7/14/28-day UTC-day block bootstraps—simultaneously resampling AEF, MEF, unfixed discharge volumes, and same-window bilateral trade weights—confirm this discrepancy persists across curtailment-absorption scenarios (e.g., **+4.03 Mt** [14d CI +3.62, +4.35] full; **+2.20 Mt** strictly inside the 18-month same-window overlap) and remains strictly positive (**+0.93 Mt**, [+0.80, +1.04]) even after excluding both California and Texas.
- **Cross-Region Imports & Congestion-Constrained Abatement Upper Bounds:** In California, accounting for cross-region imports leaves net operational emissions direction undetermined (-0.80 to +1.34 kg/MWh across 14-day block bootstraps), while fixed-profile BA-level scenarios show that because 84.9% of curtailment reflects local transmission congestion, unlocking 0%, 25%, 50%, or 100% of local curtailment bounds incremental break-even storage expansion at 0.0, 4.3, 8.0, and 15.2 GW atop CAISO's 17.3 GW fleet.
- **Cross-Regime ERCOT Stress Test & Unit-Level Physical Ramping Verification:** In Texas (`ERCO`, 9.92 TWh), exact `Season x Hour x Load-Quartile` matching shows coal's estimated marginal contribution increases under high renewable penetration (total MEF rising to 533.8 kg/MWh, coal +83.3 kg/MWh). Direct unit-level EPA CEMS operating-envelope verification across 351 ERCOT fossil generators (6.97M unit-hours) confirms that above 60% renewables, online gas peakers fall by more than half (33.3 to 15.3 units, $t = -9.1$) while coal units exit their baseload ceiling and increase their share of fossil ramping from 22.1% to 30.0% ($t = +7.0$).

### Editorial Compliance, Declarations & Reproducibility

- **Format Compliance:** Main body prose is **2,680 words** (within the 3,000-word *Analysis* limit), Abstract is **133 words** (unreferenced, within 100–150 words), with **4 Main Figures + 2 Main Tables** (6 display items, within the 8-item limit), **22 numbered references** in Nature style (100% live Crossref-verified), Methods, and a 5-page Supplementary Information PDF.
- **Author Contributions (CRediT):** Zijian Zeng (sole author) conceived and designed the study, assembled and reconciled the public grid and EPA CEMS datasets, developed and audited the econometric, bootstrap, and unit-level verification code, generated all figures and tables, and wrote the manuscript.
- **Competing Interests:** The author declares no competing interests.
- **Funding:** This research received no external grant funding.
- **Use of AI-Assisted Tools:** In accordance with Nature Portfolio policy, large language model coding and writing tools assisted with Python pipeline engineering, automated unit-test scaffolding, and manuscript language editing under continuous author supervision. All study design choices, empirical specifications, data reconciliation rules, code verification, and scientific conclusions were directed and independently verified by the author, who takes full responsibility for the manuscript.
- **Originality & Non-Duplicate Submission:** This manuscript is original, has not been published previously, and is not under consideration elsewhere (earlier internal working revisions of this project are archival drafts of the same study and have not been submitted to any other journal).
- **Reproducibility & Verification Archive (Editor Access):** Complete code (`scripts/00..09`), automated test suite (`tests/test_k1_boost.py`), machine-readable table/figure CSVs (`tables/*.csv`), checksums (`SHA256SUMS.json`), and step-by-step instructions (`REPRODUCIBILITY.md`) are archived at `https://github.com/ArtificialZeng/Operations-Research/tree/submission/k1-grid-battery-carbon-20261127/k1-grid-battery-carbon` (to be deposited on Zenodo with a permanent DOI upon acceptance; anonymized copy provided for reviewers).

Thank you for your time and consideration.

Sincerely,  
**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
Email: zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my
