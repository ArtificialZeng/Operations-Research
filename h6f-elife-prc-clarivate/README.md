# H6f Flagship (`v4` *Scientometrics* Submission): Version-Level Measurement, Incremental Predictive Validity, and Revision Trajectories in *eLife* Reviewed Preprints

**Title:** *Version-Level Measurement, Incremental Predictive Validity, and Revision Trajectories of Public Peer-Review Assessments in eLife Reviewed Preprints*  
**Author:** Zijian Zeng  
**Affiliation:** Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
**Email:** `zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`  
**Deliverables:** `manuscript_h6f_boost.pdf` (Main *Scientometrics* Original Research Manuscript, 14 pages) and `supplementary_h6f_scientometrics.pdf` (Supplementary Information, 6 pages)

## Core Scientific Findings (`v4`)

1. **Version Linking, Look-Ahead Covariate Freezing & OpenAlex Citing-Work ID Deduplication Audit:**
   - Across `4,551` *eLife* PRC manuscripts (`4,541` recovered `v1` assessments, `99.78%`; `N = 2,653` mature `2023–2024` cohorts including `2,315` VoRs and `338` non-VoR reviewed preprints), freezing covariates strictly at `v1` (`v1_n_authors` from Crossref `posted-content ver == 1`; `v1_primary_subject` from `v1_subjects[0]`) eliminates look-ahead leakage affecting `368/2,285` (`16.1%`) benchmark VoRs on authorship (`-14.03% -> -13.74% [-18.97%, -8.18%]`) and `441/4,551` (`9.7%`) manuscripts on primary discipline.
   - A stratified OpenAlex citing-work ID deduplication audit (`N = 200` multi-DOI manuscripts, mean `4.53` DOIs/work) uncovers asymmetric canonicalization: **`118/120` (`98.3%`)** VoRs consolidate into a single canonical OpenAlex Work ID, whereas **`76/80` (`95.0%`)** non-VoR reviewed preprints remain split across separate bioRxiv/medRxiv and *eLife* Work IDs. Yearly-max matches exact citing-ID unions closely (`r = 0.99979` eLife-only, `r = 0.99672` all-DOI, aggregate ratio `0.9716`) with minimal PPML regression distortion (`-25.43%` vs. `-25.38%` eLife-only; `-27.28%` vs. `-26.21%` all-DOI).
2. **Incremental Predictive Value of `v1` Assessments Over Equal-Length Windows (All-`v1`, VoR, and Non-VoR):**
   - Freezing all covariates strictly at `v1`, initial below-*Solid* evidence predicts **`-22.59% [-29.14%, -15.43%]`** (`p = 1.17e-5`, `+3.09` pp Poisson pseudo-$R^2$) next-full-calendar-year citations across all mature `v1` preprints (`N = 2,635`), **`-18.22% [-23.65%, -12.41%]`** within VoRs (`N = 2,309`), and **`-30.12% [-51.12%, -0.09%]`** (`p = 0.0495`) post-`v1` citations (`-33.81%`, `p = 0.050` next-year all-DOI under subject-year FE) within non-VoR reviewed preprints (`N = 338`). Switching solely from `v1`-quarter to VoR-quarter FE attenuates VoR estimates (`-12.94% -> -9.53%`).
   - Observational onsite readership associations (`N = 1,851` untruncated monthly cohort, `v1 >= 2023-11`, controlling for `v1_posting_day`) show positive *Significance* gradients for views/downloads and a `-10.1%` cumulative download association for below-*Solid* evidence; all readership contrasts are framed strictly as prospective observational associations overlapping *eLife*'s June 2024 discoverability redesign.
3. **Public Revision, Rating Upgrades, VoR Conversion & Readership Trajectories:**
   - Across `964` mature `v1` below-*Solid* preprints: **`842/964` (`87.3%`)** posted public revisions (`Crossref posted-content ver >= 2`), **`793/964` (`82.3%`)** reached VoR, **`644/964` (`66.8%` unconditional; `644/793 = 81.2%` VoR-conditional)** upgraded evidence ratings over a mean `325.4`-day `v1 -> VoR` calendar interval, and **`192/216` (`88.9%`)** final below-*Solid* VoRs (Apr 2023+ cohort) posted public revisions.
   - Observational contrasts for upgrading to *Solid+* are imprecise (`+3.2% [-10.7%, +19.2%]` benchmark; `+8.6% [-9.3%, +30.0%]` strict `v1` covariates, TOST `±20% p = 0.127`, `±15% p = 0.253`) and do not establish zero return; onsite traffic co-moves sharply with VoR and multi-version release events.
4. **Exploratory Indexing-Transition Material Isolated in Supplementary Information:**
   - All cohort survival curves, sequential ID-velocity proxies, synthetic-control published-output series, and 12-nation geographic tabulations around the December 10, 2024 dual Web of Science & Scopus announcement (`166/514` cross-announcement VoRs; null subject-adjusted 450d contrasts `-2.76 pp [-7.54, +2.02]` & `-3.47 pp [-10.84, +3.90]`) are documented transparently in `supplementary_h6f_scientometrics.pdf`.

## Pipeline Structure

- `scripts/03_build_clean_panels.py`: Builds `data/h6f_boost_v1_panel.csv.gz` with strictly frozen `v1` covariates (`v1_n_authors`, `v1_primary_subject`), public-revision flags, equal-length next-year citation endpoints, and `2023-11` anti-truncation guards.
- `scripts/03b_openalex_dedup_audit.py`: Runs the stratified `N = 200` OpenAlex citing-work ID deduplication audit (`data/openalex_citing_dedup_audit.json`, `results/03b_openalex_dedup_audit.json`).
- `scripts/04_pillar1_2_revision_and_attention.py` & `scripts/05_pillar3_4_clarivate_sc_and_geo.py`: Shared econometric primitives (CR1/WCB OLS, PPML, KM/AJ competing risks) and Supplementary Information exploratory published-output synthetic-control / geographic models.
- `scripts/09_v4_scientometrics_engine.py`: Unified `v4` econometric engine (`results/09_v4_scientometrics_results.json` + 5 publication CSV tables in `tables/`).
- `scripts/06_generate_figures.py`: Generates 4 Main + 3 Supplementary 300-DPI PNG + vector PDF figures dynamically from JSON receipts.
- `scripts/10_build_v4_manuscripts.py`: Dynamically generates `manuscript_h6f_boost.md` and `supplementary_h6f_scientometrics.md` with zero hardcoded numbers.
- `scripts/08_compile_manuscript_pdf.py`: Compiles `manuscript_h6f_boost.pdf` and `supplementary_h6f_scientometrics.pdf` via isolated Edge headless with zero-leak verification.
- `scripts/07_verify_refs_and_build_manifest.py`: Live-verifies all `31/31` Crossref DOIs and writes `VERIFICATION_MANIFEST.md` and `SHA256SUMS.json`.

## Quick Verification

```powershell
& ".\.venv\Scripts\ruff.exe" check scripts tests
& ".\.venv\Scripts\pytest.exe" -v tests/test_h6f_boost.py
```
