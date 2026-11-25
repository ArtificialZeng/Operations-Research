# Geographic Ascertainment Bias, Regulatory Harmonization, and Geopolitical Reallocation in Globalized Clinical Trials (`D30`)

Complete, frozen, submission-ready empirical research package examining geographic under-ascertainment of non-serious adverse events across the full universe of `22,303` industry-sponsored Phase 2 and Phase 3 clinical trials with posted results on ClinicalTrials.gov v2, linked to live FDA `Drugs@FDA`, `drug/label`, and `FAERS` pharmacovigilance databases (`openFDA`).

## Headline Findings (100% Receipt-Verified)
- **Exact Twin-Trial Identification (`100%` full rank):** Within Phase-3 `Same-Molecule × Same-Sponsor` FE (`N = 1,282`, `328` programs, `129` sponsors), EU Eastern European site share reduces reported non-serious AEs by **`-24.80 pp` (`p = 2.88e-5`; two-way `p = 2.63e-5`; wild bootstrap `p = 0.001`)** in placebo arms and **`-26.72 pp` (`p = 7.47e-6`; wild bootstrap `p = 0.001`)** in active arms. Replicates in exact `Same-Molecule × Same-Sponsor × Same-Primary-Condition` triplets (`N = 838`: `-21.21 / -19.96 pp`, `p = 0.0030 / 0.0085`), standalone Phase-2 OOS (`N = 320`: `-32.73 / -39.06 pp`), non-placebo active-comparator MRCTs (`N = 1,276`: `-25.01 pp`, `p = 5.09e-4`), and 9/9 therapeutic areas (`7/9 p < 0.05`).
- **3-Tier Objectivity Gradient & MedDRA Mirror-Image Mechanism (`96.3%` SOC coverage):** Western Europe (`p = 0.475`), LatAm (`p = 0.553`), Asia (`p = 0.699`), SAEs (`p = 0.813`), all-cause mortality (`p = 0.709`), and within-trial risk differences (`p = 0.512`) are all null. Subjective symptom MedDRA SOC share drops **`-22.03 pp` (`p = 0.000194`)** while objective laboratory/organ SOC share rises symmetrically **`+23.67 pp` (`p = 3.87e-5`)**.
- **Post-2017 Regulatory Convergence vs. FDAAA `42 CFR Part 11`:** EU Eastern Europe achieved complete symmetric convergence after a 2–3 year ICH E6(R2)/E17 implementation lag (`2020–2024`: `+35.68 pp, p = 0.0157` placebo; `+40.10 pp, p = 0.0185` active), while Non-EU Russia/Ukraine/Balkans showed zero convergence (`-49.37 pp, p = 0.000113`). FDAAA `freq_thr == 0%` expansion (`1.59x`) does not drive convergence (`eu × freq0 p = 0.909`).
- **Feb 24, 2022 Russia–Ukraine War Shock & Simplex-Valid Accrual Bounds:** Russia/Ukraine MRCT participation plunged from `47.0%` (2019) to `0.0%` (2024); strictly out-of-sample pre-war exposure DiDs (passing a pre-war fake-2020 placebo check) show heavily exposed sponsors reshored displaced site share to the United States (`+0.924, p = 0.000763`). Direct Twin-Trial accrual estimation (`ŵ_EE = 1.354x US, p = 0.0067`) bounds simplex-valid patient-level attenuation at `-19.03 / -22.42 pp` (`-15.27 to -26.22 pp` across `w ∈ [0.5, 3.0]`).
- **Gate-2 `openFDA` Audit (`N = 229` FDA-Approved Originator NDA/BLAs, incl. 21 Biologics, 100% Global FAERS):** Strong `-36.02 pp` (`p = 4.57e-4`) pre-approval tolerability illusion enters U.S.-approved profiles, while post-approval FDA labeling supplements (`p = 0.302` OLS; Poisson `p = 0.167`) and boxed warnings (`p = 0.803`) are cleanly null (coherent with SAE invariance), and U.S. FAERS serious share is fragile (`p = 0.0462` main → `p = 0.061` with FAERS volume; `p = 0.236` Sponsor FE; U.S./Non-U.S. LOR `p = 0.960`).

## Verification First (Before Any Rerun)
1. Verify archived artifacts and receipts against `SHA256SUMS.json` and run the 18-test verification suite on archived outputs:
   ```powershell
   pytest -v tests/test_d30_pipeline.py
   ruff check --select E,F,I,W,B --ignore E501 scripts tests
   ```
2. Read the compiled submission-ready manuscript PDF: `manuscript_d30_boost.pdf` (source: `manuscript_d30_boost.md`), tables (`tables/*.csv`), and publication figures (`figures/*.png`, `figures/*.pdf`).

## Optional Full From-Scratch Reproduction
Raw ClinicalTrials.gov bulk pages (`data/raw_ctgov/page_0001.json.gz..page_0023.json.gz`, ~69 MB total) are omitted from the git archive to keep the repository lightweight; their exact fetch parameters and SHA-256 digests are preserved in `data/raw_ctgov/ctgov_fetch_manifest.json`. To re-harvest live from ClinicalTrials.gov v2 and openFDA:
```powershell
python scripts/01_fetch_ctgov_universe.py
python scripts/02_build_panel.py
python scripts/03_econometrics_suite.py
python scripts/04_gate2_openfda_linkage.py --max-requests 500
python scripts/05_generate_figures_tables.py
python scripts/07_compile_manuscript_pdf.py
python scripts/06_build_manifest.py
```
*(Note: Re-running live API harvesters on a later date will reflect newly posted trials/supplements and will change hashes relative to the frozen `2026-11-25` receipts.)*
