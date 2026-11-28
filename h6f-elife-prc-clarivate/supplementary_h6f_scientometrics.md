# Supplementary Information: Version-Level Measurement Audits and Exploratory Analyses Around *eLife*'s December 2024 Indexing Transition

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
Email: zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

*Companion Supplementary Information to:* **Version-Level Measurement, Incremental Predictive Validity, and Revision Trajectories of Public Peer-Review Assessments in *eLife* Reviewed Preprints**

---

## Scope and Interpretive Notice

In accordance with strict identification standards, this Supplementary Information separates two sets of material from the main *Scientometrics* manuscript: **(Section S1)** granular look-ahead covariate audits, monthly fixed-effect sensitivities, and extended OpenAlex multi-DOI diagnostics; and **(Sections S2–S3)** exploratory descriptive analyses surrounding *eLife*'s late-2024 Web of Science and Scopus indexing transition. **None of the exploratory cohort, sequential ID-velocity, synthetic-control, or country-share contrasts in Sections S2–S3 establish a causal indexing-policy effect.** Establishing causal author or editorial responses to indexing shocks requires confidential submission, desk-review, transfer, and VoR-declaration logs across comparable peer journals stratified by pre-existing institutional evaluation regimes.

---

## Section S1. Extended Covariate-Freeze and Multi-DOI Deduplication Diagnostics

1. **Complete Look-Ahead Covariate Accounting.** Across the full census ($N = 4,551$), `cr_n_authors_max > v1_n_authors` in 554 manuscripts (399/2,653 mature 2023–2024 manuscripts; 368/2,285 in the fixed VoR benchmark), with zero missing `v1_n_authors`. Primary subject labels differed between `v1_subjects[0]` and final census `subjects[0]` in 441/4,551 manuscripts (301 reordered within an identical multi-subject list; 140 changed discipline tags; 309/2,653 mature).
2. **Monthly Fixed-Effect and Strictly Preprint-Only Pre-$v_1$ Controls.** Tightening fixed effects from `v1_primary_subject × v1_quarter` to `v1_primary_subject × v1_month` yields virtually identical $v_1$ below-*Solid* citation gradients: All-$v_1$ post-$v_1$ = -17.07% [-25.21%, -8.04%] ($N = 2,609$, $p = 0.001$); All-$v_1$ next full calendar year = -20.96% [-28.64%, -12.45%] ($N = 2,594$, $p = 0.0001$); VoR-only post-$v_1$ = -12.60% [-19.20%, -5.45%]; VoR-only next full calendar year = -17.34% [-23.60%, -10.57%]. Restricting pre-$v_1$ citation controls strictly to upstream preprint-DOI citations (`year < v1_year`) yields -17.27% [-24.44%, -9.41%] (All-$v_1$) and -12.67% [-18.32%, -6.63%] (VoRs).
3. **Extended OpenAlex Split-Work Diagnostics ($N = 200$).** Among the 78 multi-work split manuscripts (76 of 80 audited non-VoR reviewed preprints and 2 of 120 audited VoRs), the aggregate yearly-max-to-union ratio is 0.8723 (Pearson $r = 0.99282$, Spearman $\rho = 0.98829$, 10th percentile ratio 0.7273, maximum absolute difference 7 citations), whereas naive summing inflates split-work totals by +12.34% (aggregate sum/union = 1.1234) due to 63 overlapping citing OpenAlex Work IDs across 29 manuscripts.

---

## Section S2. Exploratory Cohort Analysis Around the December 10, 2024 Web of Science & Scopus Announcement

### S2.1 Dual-Database Policy Timeline and Cross-Announcement Exposure Overlap

*eLife*'s late-2024 indexing transition unfolded across multiple dates and two distinct bibliographic databases: Web of Science placed *eLife* on hold on October 23–24, 2024 (eLife, 2024a); *eLife* outlined a proposed selective feed on November 20, 2024 (eLife, 2024b); and on **December 10, 2024**, *eLife* announced **both** (i) a partial Web of Science Core Collection feed limited to *Solid+* VoRs (removing Journal Impact Factor eligibility) **and** (ii) a simultaneous migration from the **Scopus Journals Collection** to the **Scopus Preprints Collection** (eLife, 2024c).

Comparing initially below-*Solid* preprints posted before October 1, 2024 ($n = 807$) against those posted on or after December 10, 2024 ($n = 749$, excluding 119 transition posts from October 1 to December 9, 2024) exposes a severe exposure-contamination boundary: of the **514** earlier-cohort manuscripts that finalized as VoRs within 450 days, **166 (32.3%) actually finalized after the December 10, 2024 announcement**. Consequently, earlier posting cohorts were partially exposed to the announcement during their revision windows, while concurrent shifts in author composition and dual WoS/Scopus rules confound any causal policy interpretation.

<!-- FIGURE:figs1_si_indexing_cohort_cif.png -->

**Table S1. Unadjusted Kaplan–Meier and Aalen–Johansen Competing-Risks Cumulative Incidence (Earlier $< $ Oct 1, 2024 vs. Later $\ge$ Dec 10, 2024)**

| Horizon | Outcome | Earlier Cohort ($n=807$) | Later Cohort ($n=749$) | Difference [95% Boot CI] | Boot $p$ |
| :--- | :--- | ---: | ---: | ---: | ---: |
| 365 d | Any VoR (KM) | 56.51% | 47.68% | -8.83 pp [-14.36, -3.26] | 0.002 |
| 365 d | Final Solid+ VoR (AJ CIF) | 44.61% | 40.95% | -3.66 pp [-9.32, +1.67] | 0.193 |
| 365 d | Final Below-Solid VoR (AJ CIF) | 11.90% | 6.73% | -5.16 pp [-8.18, -2.12] | 0.001 |
| 450 d | Any VoR (KM) | 63.69% | 55.72% | -7.97 pp [-13.51, -2.42] | 0.005 |
| 450 d | Final Solid+ VoR (AJ CIF) | 49.69% | 47.06% | -2.63 pp [-8.70, +3.07] | 0.370 |
| 450 d | Final Below-Solid VoR (AJ CIF) | 14.00% | 8.66% | -5.34 pp [-8.79, -1.93] | 0.003 |
| 540 d | Any VoR (KM) | 70.38% | 65.05% | -5.34 pp [-11.55, +0.30] | 0.071 |
| 540 d | Final Solid+ VoR (AJ CIF) | 54.40% | 55.25% | +0.85 pp [-5.13, +6.77] | 0.788 |
| 540 d | Final Below-Solid VoR (AJ CIF) | 15.99% | 9.80% | -6.18 pp [-10.20, -2.14] | 0.001 |

*Notes:* Within-cohort nonparametric article bootstrap ($B = 1{,}000$). By construction, `CIF(Solid+) + CIF(Below-Solid) == KM(Any VoR)`. Follow-up ends November 25, 2026.

**Table S2. Subject-Adjusted Complete Fixed-Horizon Linear Probability Contrasts (No Policy Effect Established)**

| Horizon | Outcome | $N$ | Final-Subject FE (v3 Parity) [CR1 95% CI] | WCB $p$ | Strict $v_1$-Subject FE [CR1 95% CI] | WCB $p$ |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| 365 d | Any VoR | 1,180 | -7.47 pp [-12.28, -2.66] | 0.009 | -7.28 pp [-13.17, -1.39] | 0.005 |
| 365 d | Final Solid+ VoR | 1,180 | -3.56 pp [-9.24, +2.11] | 0.218 | -3.78 pp [-9.41, +1.86] | 0.142 |
| 365 d | Final Below-Solid VoR | 1,180 | -3.91 pp [-8.91, +1.10] | 0.101 | -3.50 pp [-7.80, +0.80] | 0.053 |
| 365 d | Posted Public Revision | 1,180 | -5.40 pp [-10.36, -0.43] | 0.060 | -5.32 pp [-10.88, +0.24] | 0.054 |
| 450 d | Any VoR | 1,076 | -6.14 pp [-12.03, -0.25] | 0.011 | -5.79 pp [-12.36, +0.77] | 0.008 |
| 450 d | Final Solid+ VoR | 1,076 | -3.37 pp [-9.47, +2.72] | 0.222 | -3.33 pp [-11.20, +4.53] | 0.400 |
| 450 d | Final Below-Solid VoR | 1,076 | -2.76 pp [-7.54, +2.02] | 0.195 | -2.46 pp [-7.76, +2.84] | 0.303 |
| 450 d | Posted Public Revision | 1,076 | -3.47 pp [-10.84, +3.90] | 0.334 | -3.79 pp [-10.21, +2.63] | 0.223 |
| 540 d | Any VoR | 1,000 | -3.24 pp [-10.26, +3.78] | 0.307 | -3.19 pp [-11.08, +4.71] | 0.406 |
| 540 d | Final Solid+ VoR | 1,000 | -0.22 pp [-7.62, +7.18] | 0.947 | -0.60 pp [-8.50, +7.31] | 0.884 |
| 540 d | Final Below-Solid VoR | 1,000 | -3.02 pp [-8.19, +2.15] | 0.203 | -2.59 pp [-7.57, +2.39] | 0.247 |
| 540 d | Posted Public Revision | 1,000 | -2.21 pp [-8.98, +4.56] | 0.481 | -2.37 pp [-8.69, +3.95] | 0.412 |

*Notes:* Restricted to cohorts with complete non-censored follow-up at each horizon relative to November 25, 2026 (`v1_date <= freeze - horizon`), controlling for discipline fixed effects and `v1_sig_rank`, without conditioning on VoR conversion. Public revision requires a Crossref `posted-content` (`ver >= 2`) record dated within the horizon.

**Table S3. Aalen–Johansen Cutoff Sensitivity Across Candidate Dates (Comparator Always $v_1 <$ Oct 1, 2024)**

| Later-Cohort Start Date | Later $N$ | 450-Day Final Below-*Solid* $\Delta$ [95% CI] | 540-Day Final *Solid+* $\Delta$ [95% CI] |
| :--- | ---: | ---: | ---: |
| 2024-11-20 | 784 | -5.26 pp [-8.75, -1.83] | +0.21 pp [-5.81, +5.61] |
| 2024-12-10 | 749 | -5.34 pp [-8.79, -1.93] | +0.85 pp [-5.13, +6.77] |
| 2024-12-19 | 733 | -5.01 pp [-8.57, -1.19] | +0.03 pp [-6.09, +6.40] |
| 2025-01-01 | 716 | -5.04 pp [-8.57, -0.98] | -0.04 pp [-6.88, +6.42] |

*Notes:* November 20 marks *eLife*'s proposed selective-feed update; December 10 marks *eLife*'s operational WoS and Scopus announcement; December 19 and January 1 are alternative calendar sensitivity cutoffs without causal breakpoint attribution.

As Tables S1–S3 and Figure S1 show, while unadjusted 450-day Aalen–Johansen cumulative incidence of final below-*Solid* VoRs was -5.34 pp lower in the later posting cohort, **complete-followup subject-adjusted linear probability models yield statistically imprecise, non-significant contrasts at 450 days** for both final below-*Solid* VoRs (-2.76 pp [-7.54, +2.02], $p_{\text{WCB}} = 0.195$; strict $v_1$-subject FE: -2.46 pp [-7.76, +2.84], $p_{\text{WCB}} = 0.303$) and posted public revisions (-3.47 pp [-10.84, +3.90], $p_{\text{WCB}} = 0.334$; strict $v_1$-subject FE: -3.79 pp [-10.21, +2.63], $p_{\text{WCB}} = 0.223$). Combined with the 166/514 cross-announcement overlap and simultaneous Scopus reclassification, these data do not establish a causal indexing-policy effect.

---

## Section S3. Exploratory Sequential ID Velocity, Published-Output Synthetic Control, and Geographic Shares

For completeness and transparency relative to earlier working versions, this section archives our exploratory macro-level published-output series around the October–December 2024 indexing transition. Because OpenAlex measures **published output** rather than confidential submission inflows, and because sequential manuscript IDs (`eid`) are an indirect velocity proxy rather than direct submission logs, all estimates below are strictly descriptive/exploratory and excluded from the main manuscript's abstract and core claims.

<!-- FIGURE:figs2_si_id_velocity_and_sc.png -->

1. **Sequential Manuscript-ID Velocity Proxy & 500-`eid` Acceptance Shares.** Calibrating sequential manuscript IDs against $N = 200$ exact `sentForReview` timestamps (Spearman $r = 0.9988$) implies a -56.3% contraction in quarterly ID velocity (2,579 $\to$ 1,127/quarter), broadly consistent with *eLife*'s published full-year submission decline from 6,396 to 2,853 ($-55.4\%$; Rodgers & Pattinson, 2026). Across 49 sequential 500-`eid` blocks (`eid` 87.5k–112k), the share reaching Reviewed Preprint rose from 15.44% to 20.06% (+4.63 pp, HAC $t = +3.41$, permutation $p = 0.0002$, Quandt–Andrews Sup-Wald $F = 53.14$; Andrews, 1993) while $v_1$ below-*Solid* quality share showed no detectable shift (+0.46 pp, $p = 0.770$).
2. **Published-Output Synthetic Control (30 Strict / 35 Expanded Biology Journals).** Applying strictly convex Abadie–Diamond–Hainmueller synthetic controls (Abadie, Diamond, & Hainmueller, 2010, 2015; Abadie, 2021) to half-yearly OpenAlex published counts (`2021H1–2026H1`) yields a post-2024 total published-output gap of -0.552 log points (RMSPE Rank 1/30, $p = 0.0333$; expanded $N = 35$ gap -0.541, Rank 1/35, $p = 0.0286$) and a China-affiliated published-output gap of -1.091 ($T_0 = 3$, Rank 1/30; Full-Pre $T_0 = 7$ gap -1.070, Rank 1/30, $p = 0.0333$; expanded $N = 35$ Rank 1/35, $p = 0.0286$). Because synthetic controls here operate on **published articles** rather than submissions, they reflect the combined net result of submission shifts, editorial screening, and publication lags.

<!-- FIGURE:figs3_si_geographic_exploratory.png -->

**Table S4. Exploratory 12-Nation Phase-2 Published-Output DiD (2025H1–2026H1 vs. 2023H2–2024H2) and External Submission Comparison**

| Country | Policy-Label Grouping | *eLife* Share (21–22 $\to$ 23–24 $\to$ 25–26) | Phase-2 Published-Output Log DiD (%) | Phase-2 Share DiD | *eLife* Mar 2026 Blog Submission Drop |
| :--- | :--- | ---: | ---: | ---: | ---: |
| China (CN) | JIF Codified | 9.5% $\to$ 20.0% $\to$ 15.1% | -1.036 (-64.5%) | -8.95 pp | -80% |
| Spain (ES) | JIF Codified | 3.7% $\to$ 3.6% $\to$ 2.5% | -0.962 (-61.8%) | -1.44 pp | -54% |
| Germany (DE) | DORA Reformed | 15.2% $\to$ 13.0% $\to$ 11.9% | -0.662 (-48.4%) | -1.04 pp | -52% |
| India (IN) | Mixed Other | 1.8% $\to$ 3.0% $\to$ 3.4% | -0.658 (-48.2%) | +0.05 pp | -25% |
| Italy (IT) | JIF Codified | 3.1% $\to$ 2.2% $\to$ 2.3% | -0.592 (-44.7%) | -0.15 pp | -75% |
| Canada (CA) | DORA Reformed | 6.9% $\to$ 6.0% $\to$ 5.4% | -0.580 (-44.0%) | -0.09 pp | Not reported |
| United States (US) | DORA Reformed | 59.8% $\to$ 50.0% $\to$ 48.6% | -0.534 (-41.4%) | +2.21 pp | -40% |
| Japan (JP) | Mixed Other | 5.5% $\to$ 6.1% $\to$ 6.8% | -0.474 (-37.7%) | +0.69 pp | Not reported |
| France (FR) | DORA Reformed | 8.3% $\to$ 7.7% $\to$ 8.2% | -0.457 (-36.7%) | +0.85 pp | -23% |
| United Kingdom (GB) | DORA Reformed | 17.5% $\to$ 14.2% $\to$ 16.2% | -0.418 (-34.2%) | +2.14 pp | -18% |
| Switzerland (CH) | DORA Reformed | 6.1% $\to$ 4.4% $\to$ 5.2% | -0.405 (-33.3%) | +0.82 pp | Not reported |
| Netherlands (NL) | DORA Reformed | 4.6% $\to$ 3.8% $\to$ 5.4% | -0.139 (-13.0%) | +1.69 pp | -47% |

*Notes:* Exploratory published-output differences relative to clean peer biology donor journals (NOT submission volumes). Policy-label groupings draw on published research-evaluation literature documenting JIF/WoS codification (Seglen, 1997; Hicks et al., 2015; Quan, Chen, & Shu, 2017; McKiernan et al., 2019; Baccini, De Nicolao, & Petrovich, 2019; Shu et al., 2020; Zhang & Sivertsen, 2020). Across these small country groups, the 3 JIF-codified nations (CN, ES, IT; mean -57.8%) contracted more sharply in published output than the 7 DORA-reformed nations (mean -36.6%, exact permutation $p = 0.0167$), tracking *eLife*'s published 9-country submission drops (Spearman $\rho = 0.683$, $p = 0.0424$; Rodgers & Pattinson, 2026). Senior/last-author PI shares inside *eLife* PRC shifted from 20.5% (2024H2) to 9.1% (2025H1) for China while US Senior-PI share stayed near 38.1%–39.4%.

---

## Supplementary References

1. Hicks, Diana, Wouters, Paul, Waltman, Ludo, de Rijcke, Sarah, & Rafols, Ismael (2015). Bibliometrics: The Leiden Manifesto for research metrics. *Nature*, *520*(7548), 429-431. https://doi.org/10.1038/520429a
2. Seglen, Per O (1997). Why the impact factor of journals should not be used for evaluating research. *BMJ*, *314*(7079), 497.1. https://doi.org/10.1136/bmj.314.7079.497
3. McKiernan, Erin C, Schimanski, Lesley A, Muñoz Nieves, Carol, Matthias, Lisa, Niles, Meredith T, & Alperin, Juan P (2019). Use of the Journal Impact Factor in academic review, promotion, and tenure evaluations. *eLife*, *8*. https://doi.org/10.7554/eLife.47338
4. Quan, Wei, Chen, Bikun, & Shu, Fei (2017). Publish or impoverish. *Aslib Journal of Information Management*, *69*(5), 486-502. https://doi.org/10.1108/AJIM-01-2017-0014
5. Zhang, Lin, & Sivertsen, Gunnar (2020). The New Research Assessment Reform in China and Its Implementation. *Scholarly Assessment Reports*, *2*(1), 3. https://doi.org/10.29024/sar.15
6. Shu, Fei, Quan, Wei, Chen, Bikun, Qiu, Junping, Sugimoto, Cassidy R., & Larivière, Vincent (2020). The role of Web of Science publications in China’s tenure system. *Scientometrics*, *122*(3), 1683-1695. https://doi.org/10.1007/s11192-019-03339-x
7. Baccini, Alberto, De Nicolao, Giuseppe, & Petrovich, Eugenio (2019). Citation gaming induced by bibliometric evaluation: A country-level comparative analysis. *PLOS ONE*, *14*(9), e0221212. https://doi.org/10.1371/journal.pone.0221212
8. Abadie, Alberto, Diamond, Alexis, & Hainmueller, Jens (2010). Synthetic Control Methods for Comparative Case Studies: Estimating the Effect of California’s Tobacco Control Program. *Journal of the American Statistical Association*, *105*(490), 493-505. https://doi.org/10.1198/jasa.2009.ap08746
9. Abadie, Alberto, Diamond, Alexis, & Hainmueller, Jens (2015). Comparative Politics and the Synthetic Control Method. *American Journal of Political Science*, *59*(2), 495-510. https://doi.org/10.1111/ajps.12116
10. Abadie, Alberto (2021). Using Synthetic Controls: Feasibility, Data Requirements, and Methodological Aspects. *Journal of Economic Literature*, *59*(2), 391-425. https://doi.org/10.1257/jel.20191450
11. Andrews, Donald W. K. (1993). Tests for Parameter Instability and Structural Change With Unknown Change Point. *Econometrica*, *61*(4), 821. https://doi.org/10.2307/2951764
12. eLife (2024a). Update on eLife's indexing status at Web of Science. *Inside eLife*, October 24, 2024. https://elifesciences.org/inside-elife/16afe6ec/update-on-elife-s-indexing-status-at-web-of-science
13. eLife (2024b). The eLife Model: An update on progress following changes in Web of Science indexing status. *Inside eLife*, November 20, 2024. https://elifesciences.org/inside-elife/c11c6101/the-elife-model-an-update-on-progress-following-changes-in-web-of-science-indexing-status
14. eLife (2024c). Changes to eLife's indexing status in Web of Science and Scopus. *Inside eLife*, December 10, 2024. https://elifesciences.org/inside-elife/ae620829/changes-to-elife-s-indexing-status-in-web-of-science-and-scopus
15. Rodgers, P., & Pattinson, D. (2026). The eLife Model: Three years of data and lessons learned. *Inside eLife*, March 17, 2026. https://elifesciences.org/inside-elife/7da92a51/the-elife-model-three-years-of-data-and-lessons-learned
