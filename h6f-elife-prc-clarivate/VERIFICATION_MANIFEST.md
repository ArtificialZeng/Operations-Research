# VERIFICATION MANIFEST — H6f Scientometrics Flagship Build (v4 Submission-Ready Revision)

**Manuscript:** *Version-Level Measurement, Incremental Predictive Validity, and Revision Trajectories of Public Peer-Review Assessments in eLife Reviewed Preprints*  
**Author:** Zijian Zeng (Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA)  
**Target Venue:** *Scientometrics* (Original Research)  
**Workspace:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126`  
**Build Date:** 2026-11-28 (v4 Major Revision)

## 1. Data Completeness, Strict v1 Covariate Freezing & Multi-DOI Audit

- **Complete *eLife* PRC Census (`2023–2026`):** `N = 4,551` unique PRC manuscripts; `4,541` (`99.78%`) true `v1` assessments recovered; `0` missing `v1` dates; `0` VoR-before-`v1` date anomalies.
- **Strictly Frozen `v1`-at-Publication Covariates (P0 #1):** `0 / 4,551` missing `v1_n_authors` (Crossref `posted-content ver == 1`); `0 / 4,551` missing `v1_primary_subject` (`v1_subjects[0]`). Audit revealed `368 / 2,284` (`16.11%`) benchmark VoRs had `max_authors > v1_n_authors` and `441 / 4,551` articles changed/reordered primary subject (`301` reordered, `140` changed tags).
- **OpenAlex Citing-Work ID Deduplication Audit (`N = 200` stratified multi-DOI manuscripts, mean `4.53` DOIs/work):** `61.0%` collapsed to 1 OpenAlex Work ID (`98.3%` among VoRs vs. `5.0%` among Non-VoRs); eLife-only exact citing-ID union vs. yearly-max Pearson `r = 0.99979` (`exact match = 99.0%`, aggregate ratio `0.9980`); all-manifestation Pearson `r = 0.99672` (aggregate `ymax/union = 0.9716`, naive-sum ratio `1.0274`).
- **Live *eLife* Onsite Telemetry:** `2,653 / 2,653` (`100.00%`) lifetime coverage; `1,852` strictly untruncated monthly cohorts (`v1 >= 2023-11`, complete months `<= 2026-10`).
- **Live Crossref DOI Bibliography Verification:** `31 / 31` peer-reviewed DOIs verified HTTP 200 via `api.crossref.org/works/{doi}`.

## 2. Headline Empirical Receipts (Dynamically Extracted from JSON)

| Section / Audit | Specification | Estimate [95% CI] | Inference / Precision |
| :--- | :--- | ---: | :--- |
| **Covariate Leakage Benchmark** | `N = 2,284` VoRs: `max_authors` vs `v1_n_authors` | `-14.05%` -> `-13.77% [-19.02%, -8.19%]` | Exact parity with reviewer benchmark (`368/2,285`) |
| **Quarter-Clock Sensitivity** | Switching ONLY `v1` quarter -> VoR quarter (`v1` label fixed) | `-13.77%` -> `-9.45%` (Strict `v1`: `-12.94%` -> `-9.53%`) | Separate date-clock vs. label-timing shift |
| **All-`v1` Equal Window** | ALL `2023–2024` `v1` (`N=2,635`, strict `v1` covs) | Next-yr `-22.59% [-29.14%, -15.43%]` | `p = 1.17e-05` (Post-`v1`: `-17.53%`) |
| **VoR-Only Equal Window** | Mature VoRs (`N=2,309`, strict `v1` covs) | Next-yr `-18.22% [-23.65%, -12.41%]` | `p = 1.01e-05` (Post-`v1`: `-13.03%`) |
| **Non-VoR-Only Validation** | Non-VoR RPs (`N=306`, strict `v1` covs) | Post-`v1` `-30.12% [-51.12%, -0.09%]` | `p = 0.0495` (Next-yr: `-38.28%`) |
| **Revision vs. Upgrade Funnel** | `964` mature `v1 <Solid` preprints (`mean lag = 325.4d`) | `842/964` (`87.3%`) public rev; `644/964` (`66.8%`) all-`v1` / `644/793` (`81.2%`) VoR-cond | `192/216` (`88.9%`) final `<Solid` VoRs posted revisions |
| **Upgrade to *Solid+* Contrast** | Mature `v1 <Solid` VoRs (`v3`-parity / strict `v1`) | `+3.18% [-10.72%, +19.25%]` / Strict: `+8.55% [-9.33%, +29.96%]` | TOST `±20% p = 0.1275`, `±15% p = 0.2533` (imprecise; NOT "zero return") |
| **SI Exploratory Indexing** | Dec 10, 2024 WoS & Scopus (`166/514` pre VoRs crossed) | `450d` `<Solid`: `-2.76 pp [-7.54, +2.02]`; PubRev: `-3.47 pp [-10.84, +3.90]` | Does NOT establish a policy effect; isolated in SI PDF |

## 3. Reproducibility & Quality Gates (`v4`)

- `ruff check scripts tests`: **0 errors**
- `pytest -v tests/test_h6f_boost.py`: **100% passing**
- `manuscript_h6f_boost.pdf` & `supplementary_h6f_scientometrics.pdf`: **0 leaked LaTeX/Markdown tokens**, compiled cleanly via Edge headless with isolated `--user-data-dir`, and visually inspected across every page.
- `SHA256SUMS.json`: **100% exact match** with live disk `Path.read_bytes()`.
