# H6f `/boost` Flagship: Intrinsic Revision Norms & Asymmetric Impact-Factor Dependence (*eLife* PRC, 2021–2026)

**Title:** *Intrinsic Revision Norms and Asymmetric Impact-Factor Dependence: Causal Evidence from the eLife Publish-Review-Curate Experiment and Clarivate's 2024 Delisting, 2021–2026*  
**Workspace:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126`  
**Target Venues:** *Nature Human Behaviour* | *PNAS* | *Science Advances* | *Nature Communications* | *PLOS Biology*

## Scientific Summary

Exploiting the complete `4,551`-paper *eLife* Publish-Review-Curate (PRC) census (`2023–2026`, `99.78%` true `v1` recovery), live *eLife* article-level `page-views` and `downloads` (`100.00%` of `N = 2,653` mature `2023–2024` `v1` cohorts with strict rolling `2023-11` monthly left-truncation guards), and a strictly audited `30`-journal (`35`-journal expanded) clean life-science OpenAlex panel (`2021H1–2026H1`), this repository replicates four main results:

1. **Intrinsic Revision Norms (Pillar 1):** `82.3%` of initially *Incomplete/Inadequate* `v1` preprints convert to VoR and `81.2%` of those VoRs (`78.3%` crossing into *Solid+*) upgrade over a mean `325.4`-day revision lag; Clarivate's December 2024 ESCI *Solid*-threshold indexing cliff shifted uncensored `450`-day upgrade rates by just `+0.40` pp ($p = 0.873$, $p_{\text{WCB}} = 0.864$; clean `2023`-only pre-cohort `-2.92` pp, $p_{\text{WCB}} = 0.232$).
2. **Double Evaluation-Market Paradox & `VoR`-Date Autopsy (Pillar 2):** True `v1`-date alignment exposes a `-14.5%` post-`v1` OpenAlex citation penalty for `v1` *Incomplete* ($t = -5.11$, $p = 8.67 \times 10^{-5}$; erased to `+0.7%`, $p = 0.915$ under flawed VoR-date alignment), whereas live readers initially click headline `v1` *Significance* (`+10.0%` views, $p = 0.00077$; `+9.6%` downloads, $p = 0.00217$). Once rolling `2023-11` API left-truncation is eliminated, upgrading *Incomplete* $\to$ *Solid+* yields **zero sustained marginal payoff in either citations (`+3.2%`, $p = 0.654$, TOST $\pm 20\%$ $p = 0.0125$) or post-VoR readership** (untruncated `v1 >= 2023-11` rate DiD `+0.058`, $p_{\text{WCB}} = 0.256$, TOST $\pm 15\%$ $p = 0.0426$; clean local VoR event study `N = 651` uniform month-0 spike `+1.11` vs. `+1.11`, FE DiD `+0.001`, $p_{\text{WCB}} = 0.984$; post-VoR `t = +1..+6` `-0.103`, $p_{\text{WCB}} = 0.171$); reader traffic responds instead to **version-release events** (`+0.234` to `+0.301` per published version, $p \le 0.012$).
3. **Clarivate Delisting & Editorial Cushioning (Pillar 3):** Sequential `eid` submission velocity (`sentForReview` Spearman $r = 0.9988$) fell `-56.3%`, cushioned by a `+4.63` pp jump in peer-review acceptance (`15.44%` $\to$ `20.06%`, HAC $t = +3.41$, Perm $p = 0.0002$, Sup-Wald $F = 53.14$) with invariant `v1` quality (`+0.54` pp, $p = 0.756$).
4. **Asymmetric Global Metric Dependence (Pillar 4):** Under strictly convex unique ADH Synthetic Control (`30` strict / `35` expanded clean journals), total output fell `-0.552` log pts (Rank `1/30`, $p = 0.0333$; Expanded Rank `1/35`, $p = 0.0286$) and China surged during Phase-1 PRC (`+4.86` pp share; Senior-PI `13.0%` $\to$ `20.5%`) before crashing `-1.091` log pts (`-66.4%`, Rank `1/30`, $p = 0.0333$; Expanded `-1.098`, Rank `1/35`, $p = 0.0286$; Senior-PI `9.1%` overnight). Across `12` nations, JIF-codified systems (`CN, ES, IT`: `-57.8%`) contracted `-21.2` pp deeper than DORA-reformed systems (7 nations: `-36.6%`, exact permutation $p = 0.0167$), cross-validating *eLife*'s March 2026 official submission ledger (Spearman $\rho = 0.683$, $p = 0.0424$).

## Pipeline Structure

- `scripts/01_copy_seed_and_fetch_metrics.py`: Copies verified read-only Wave-4B seed caches and harvests live monthly *eLife* `page-views` & `downloads` (`2,654/2,654` HTTP 200).
- `scripts/02_fetch_expanded_openalex_panel.py`: Harvests the candidate OpenAlex panel (`2021H1–2026H1`) via exact single-call `group_by=authorships.countries:include_unknown`.
- `scripts/03_build_clean_panels.py`: Assembles `data/h6f_boost_v1_panel.csv.gz` (with strict `2023-11` rolling-window anti-truncation guards and clean local VoR event-study variables) and `data/h6f_boost_journal_panel.csv`.
- `scripts/04_pillar1_2_revision_and_attention.py`: Pillars 1 & 2 econometrics (exact LSDV-equivalent CR1/WCB, converged PPML, clean untruncated local VoR event study & 22-month trajectory -> `results/04_pillar1_2_results.json`, `tables/table1_*.csv`, `tables/table2_*.csv`).
- `scripts/05_pillar3_4_clarivate_sc_and_geo.py`: Pillars 3 & 4 econometrics (unique minimum-L2-norm ADH Synthetic Control, Abadie–L'Hour penalized sensitivity, Sup-Wald break, 12-nation JIF-vs-DORA regime test -> `results/05_pillar3_4_results.json`, `tables/table3_*.csv`, `tables/table4_*.csv`).
- `scripts/06_generate_figures.py`: Generates 5 publication-grade 300-DPI PNG + vector PDF figures in `figures/`.
- `scripts/07_verify_refs_and_build_manifest.py`: Live-verifies all 29 Crossref DOIs and builds `VERIFICATION_MANIFEST.md` & `SHA256SUMS.json`.
- `scripts/08_compile_manuscript_pdf.py`: Compiles `manuscript_h6f_boost.md` into `manuscript_h6f_boost.pdf` with 100% dynamic captions and strict zero-leak verification.

## Quick Verification

```powershell
& ".\.venv\Scripts\ruff.exe" check scripts tests
& ".\.venv\Scripts\pytest.exe" -v tests/test_h6f_boost.py
```
