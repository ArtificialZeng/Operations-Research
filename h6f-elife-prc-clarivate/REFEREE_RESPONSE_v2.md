# Point-by-Point Referee Response (`v2` Major Revision) — Flagship `H6f`

**Manuscript Title (`v2`):** *Voluntary Revision and Asymmetric Impact-Factor Dependence: Evidence from the eLife Publish-Review-Curate Experiment and Clarivate's 2024 Delisting, 2021–2026*  
**Workspace:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126`

We thank the referee for an unusually incisive, technically rigorous, and constructive review. Every single methodological defect and interpretive overclaim identified in the report has been corrected directly in our econometric code, regenerated end-to-end across all tables, figures, manuscript sections, and PDF outputs, and locked behind expanded automated regression tests (`tests/test_h6f_boost.py`). Below we map each referee point to the exact code change, verified numerical receipt, and manuscript revision.

---

## Critique 1: `post_esci` Date Misalignment (`2024-10-01`) + Post-Treatment VoR Collider Conditioning + Causal Overclaim (`scripts/04_pillar1_2_revision_and_attention.py:363`)

### Referee Diagnosis
1. `post_esci` was coded as `v1_dt >= "2024-10-01"`, predating both Clarivate's late-October indexing suspension (`2024-10-24`) and its December 19, 2024 confirmation of the ESCI *Solid*-threshold indexing rule (`https://elifesciences.org/articles/110392`, Behrens et al., 2026).
2. Estimating the primary ESCI contrast on `vors_win` (converted VoRs only) conditions on a post-treatment conversion outcome (collider bias), and the single-journal before-vs-after design lacks an unexposed control group—meaning the prior `+0.40` pp estimate could not prove zero indexing-incentive effect or causally prove intrinsic norms.

### Concrete Code & Statistical Fixes Applied
- **Exact Date Alignment & Transition Donut (`scripts/04_pillar1_2_revision_and_attention.py`):**
  - Replaced `v1_dt >= "2024-10-01"` with primary policy alignment **`v1_dt >= "2024-12-19"`** while explicitly excluding the **October 1–December 18, 2024 transition donut (`n = 135`)** spanning the indexing hold through the ESCI policy confirmation (comparing Pre `2023-04-01..2024-09-30`, `n = 807`, vs. Post `>= 2024-12-19`).
  - Added full cutoff sensitivities at **`>= 2025-01-01`** (excluding Oct–Dec 2024), **`>= 2024-10-24`** (Clarivate's indexing suspension date), and a **clean `2023`-only pre-cohort** (`2023-04-01..2023-12-31` vs. `>= 2024-12-19`).
  - Tightened fixed uncensored follow-up horizons to exact right-censoring-free cutoffs relative to the `2026-11-25` data snapshot: `365d` (`v1_dt <= 2025-11-25`, `n_post = 370`), `450d` (`v1_dt <= 2025-09-01`, `n_post = 264`), and `540d` (`v1_dt <= 2025-06-03`, `n_post = 188`).
- **Unconditional Intention-to-Treat (ITT) Across ALL `v1` *Incomplete/Inadequate* Preprints (Removing VoR Collider!):**
  - Elevated **unconditional ITT** (`P(Converted to VoR within W days)`, `P(Upgraded to Solid+ within W days)`, and `P(Unrevised <Solid VoR within W days)`) across all `v1` *Incomplete* preprints to the primary estimands (`tables/table1b_esci_itt_and_cif.csv`, Section 4.1 Table 1B).
  - **Verified `365d` Primary (`>= 2024-12-19`, donut excluded, `n = 1,165` inside FE):**
    - `ITT P(Converted to VoR)`: `56.51% -> 48.38%`, Subject-FE = **`-7.35` pp** (`SE = 2.40`, 95% CI `[-12.41, -2.29]`, `p = 0.0070`, `p_WCB = 0.0090`).
    - `ITT P(Upgraded to Solid+)`: `44.61% -> 41.08%`, Subject-FE = **`-3.58` pp** (`SE = 2.79`, 95% CI `[-9.46, +2.30]`, `p = 0.2163`, `p_WCB = 0.2120`).
    - `ITT P(Unrevised <Solid VoR)`: `11.90% -> 7.30%`, Subject-FE = **`-3.77` pp** (`SE = 2.42`, 95% CI `[-8.88, +1.34]`, `p = 0.1379`, `p_WCB = 0.1065`).
  - **Verified `450d` Primary (`>= 2024-12-19`, donut excluded, `n = 1,061` inside FE):**
    - `ITT P(Converted to VoR)`: `63.69% -> 56.44%`, Subject-FE = **`-6.17` pp** (`SE = 3.15`, 95% CI `[-12.81, +0.48]`, `p = 0.0670`, `p_WCB = 0.0145`).
    - `ITT P(Upgraded to Solid+)`: `49.69% -> 46.21%`, Subject-FE = **`-3.75` pp** (`SE = 3.12`, 95% CI `[-10.33, +2.84]`, `p = 0.2464`, `p_WCB = 0.2015`).
    - `ITT P(Unrevised <Solid VoR)`: `14.00% -> 10.23%`, Subject-FE = **`-2.42` pp** (`SE = 2.33`, 95% CI `[-7.35, +2.51]`, `p = 0.3145`, `p_WCB = 0.2835`).
  - **Verified Sensitivities (`450d`):** `>= 2025-01-01` yields ITT VoR `-7.14` pp (`p_WCB = 0.0080`), ITT *Solid+* `-4.56` pp (`p_WCB = 0.1210`); `>= 2024-10-24` yields ITT VoR `-5.30` pp (`p_WCB = 0.0295`), ITT *Solid+* `-2.03` pp (`p_WCB = 0.4135`).
- **Nonparametric Kaplan–Meier & Aalen–Johansen Competing-Risks Cumulative Incidence (`km_competing_risks`):**
  - Across all `1,540` non-donut `v1` *Incomplete* preprints (`Pre < 2024-10-01` `n = 807` vs. `Post >= 2024-12-19` `n = 733`, handling right-censoring transparently with `1,000`-draw bootstrap SEs), Figure 1B and Table 1B reveal a genuinely informative competing-risks decomposition previously obscured by VoR conditioning:
    - **KM Any VoR Conversion:** `-8.78` pp at `365d` (`56.51% -> 47.72%`, `p = 0.0023`); `-8.17` pp at `450d` (`63.69% -> 55.52%`, `p = 0.0066`); `-5.84` pp at `540d` (`70.38% -> 64.54%`, `p = 0.0634`).
    - **AJ Competing-Risk CIF (`Solid+` VoR):** `-3.83` pp at `365d` (`p = 0.1784`), `-3.14` pp at `450d` (`p = 0.2997`), converging identically by **`540d` (`54.40% -> 54.36%`, `-0.04` pp, `p = 0.9897`)**.
    - **AJ Competing-Risk CIF (Unrevised `<Solid` VoR):** dropped sharply by **`-4.95` pp at `365d`** (`11.90% -> 6.94%`, `p = 0.0018`), **`-5.03` pp at `450d`** (`14.00% -> 8.97%`, `p = 0.0073`), and **`-5.80` pp at `540d`** (`15.99% -> 10.18%`, `p = 0.0043`).
- **Secondary Descriptive Decomposition & Full Retraction of Overclaim:**
  - Retained `P(Solid+ | VoR)` strictly as `secondary_cond_up_given_vor` (`365d`: `+4.71` pp, `p_WCB = 0.2965`; `450d`: `+1.63` pp, `p_WCB = 0.6505`), explicitly illustrating how the `-5.0` pp drop in unrevised `<Solid` VoRs induces an upward mechanical shift once conditioned on VoR conversion.
  - **Retracted** the prior `+0.40` pp claim and all language asserting that ESCI contrasts *prove* zero indexing-incentive effect or *causally prove* intrinsic norms (including updating the manuscript title, Abstract, Sections 1, 4.1, 5.1, 5.3, 6, and Figure 1B). Framed honestly: high voluntary revision rates were already present from `2023` onward and persist despite zero or at most modest measurable badge returns, while before-after ESCI comparisons lack an unexposed control group and cannot rule out indexing-incentive effects (such as selective deferral of unrevised `<Solid` VoRs).

---

## Critique 2: Exact Funnel Denominators, Calendar-Interval Definition, & Transparent TOST Equivalence Bounds

### Referee Diagnosis
1. Reporting `81.2%` without the full unconditional funnel obscured the distinction between `%` of converted VoRs (`644 / 793`) and `%` of all `v1` *Incomplete* preprints (`644 / 964 = 66.8%`).
2. `325.4 days` needed explicit clarification as the calendar-date interval between `v1` posting and VoR publication rather than measured active bench/author time.
3. On citations (`+3.2%`), only `±20%` (`p = 0.0125`) was highlighted in the Abstract/Discussion, whereas the stricter `±15%` TOST bound (`p = 0.0508`) sits just above `0.05`, and exact 95% CIs and observation horizons were needed alongside TOST.

### Concrete Code & Text Fixes Applied
- **Complete Funnel Denominator Everywhere (`Abstract`, `Section 1`, `Section 4.1`, `Table 1`, `Figure 1A`, `tables/table1_transition_and_esci.csv`):**
  - Added `all_upgrade_any_pct` (`66.80%`) and `all_upgrade_to_solid_pct` (`64.42%`) directly into `tables/table1_transition_and_esci.csv`, Table 1 in the manuscript, and Figure 1A annotations.
  - Reported the full funnel explicitly in Abstract, Section 1, Section 4.1, and Section 6: `4,541 / 4,551` recovered `v1` -> `964` mature `v1` *Incomplete/Inadequate* preprints -> `793` converted to VoR (`82.3%`) -> `644` upgraded (**`81.2%` of converted VoRs; `66.8%` of all `964` `v1` *Incomplete* preprints**), including `621` crossing to *Solid+* (`78.3%` of VoRs; `64.4%` of all `964` `v1` *Incomplete* preprints).
- **Calendar-Interval Definition:**
  - Explicitly clarified at every occurrence of `325.4 days` (Abstract, Section 1, Section 4.1, Table 1, Section 5.1, Section 5.3, Figure 1 caption, and Section 6) that this measures the **calendar-date interval between `v1` Reviewed Preprint posting and VoR publication**, not measured active author working time.
- **Exact 95% CIs, Observation Horizons, & Both TOST Bounds (`scripts/04_pillar1_2_revision_and_attention.py`, `Abstract`, `Sections 1, 2.1, 4.2, 5.1, 5.3`, `Figure 2` caption):**
  - Added exact $t_{0.975,\,G-1}$ 95% confidence intervals (`ci95_lo`, `ci95_hi`, `pct_ci95_lo`, `pct_ci95_hi`) and `observation_horizons` directly into `results/04_pillar1_2_results.json`.
  - Reported **both** citation TOST bounds transparently in the Abstract, Section 1, Section 4.2, Section 5.1, Section 5.3, and Figure 2 caption: `+3.2%`, 95% CI `[-10.7%, +19.2%]` (`[-0.1134, +0.1760]`), $p = 0.654$, **TOST $\pm 20\%$ $p = 0.0125$, $\pm 15\%$ $p = 0.0508$** (explicitly noting that `±15%` sits just above `0.05`), alongside the exact mature horizon (`22.8–46.0` months post-`v1`, median `32.7` months; `0.2–40.2` months post-VoR, median `23.0` months) and 95% CIs for all key readership estimators.

---

## Critique 3: Clean Separation of Submissions vs. Published Output vs. Country Policy-Label Groupings & Compound-Shock Identification Boundaries

### Referee Diagnosis
1. Submission velocity (`-56.3%`) should be cleanly separated from published-output Synthetic Control (`-0.552` total; `-66.4%` China) and explicitly contextualized against *eLife*'s published full-year submission drop (`6,396 -> 2,853`, `-55.4%`) as an established factual baseline rather than an exclusive discovery.
2. The `-21.2` pp cross-national contrast needed transparent framing as a small-sample `3` JIF-codified vs. `7` DORA-reformed policy-label comparison (`Perm p = 0.0167`), and Limitations needed an explicit boundary stating that disentangling the abolition of post-review rejection, Clarivate's indexing pause, JIF removal, and selective ESCI coverage requires internal submission/review logs and multi-journal institutional benchmarks.

### Concrete Text, Figure & Verification Fixes Applied
- **Clean Three-Metric Separation (`Abstract`, `Section 1`, `Sections 4.3–4.4`, `Tables 3–4`, `Figures 3–5`, `Sections 5–6`):**
  1. **Submission Velocity (`-56.3%` sequential `eid` rate):** Explicitly introduced as a quarterly reconstruction contextualized against *eLife*'s established full-year submission drop (`6,396 -> 2,853`, `-55.4%`), citing both Rodgers and Pattinson (2026; `https://elifesciences.org/inside-elife/7da92a51/the-elife-model-three-year-update`) and Behrens et al. (2026; `https://elifesciences.org/articles/110392`).
  2. **Published-Output Synthetic Control (`-0.552` [`-42.4%`] total; `-1.091` [`-66.4%`] China-affiliated articles):** Clearly labeled throughout text, Table 3, and Figure 4 as **published article output** with exact donor-pool rank context (**Rank `1/30`, $p = 0.0333$ strict; Rank `1/35`, $p = 0.0286$ expanded**).
  3. **Small-Sample Policy-Label Comparison (`-21.2` pp):** Explicitly described everywhere (Abstract, Section 1, Section 4.4, Table 4, Figure 5B, Sections 5.2–5.3, and Conclusion) as a **small-sample `3` JIF-codified (`CN, ES, IT`, mean `-57.8%`) vs. `7` DORA-reformed (`GB, FR, US, CH, NL, DE, CA`, mean `-36.6%`) country-group comparison** (`C(10,3) = 120` partitions, exact permutation $p = 0.0167$).
- **Explicit Compound-Shock Identification Boundary (`Section 5.3, Limitation 1`):** Added a dedicated lead limitation transparently stating that cleanly separating (a) abolishing post-review rejection, (b) Clarivate's October 24, 2024 indexing pause, (c) JIF revocation, and (d) selective December 19, 2024 ESCI coverage requires internal submission/peer-review logs and multi-journal institutional benchmarks.

---

## Verification Summary (`v2`)

- **Pipeline Re-Run End-to-End:** `scripts/04`, `05`, `06`, `07`, and `08` executed cleanly with `0` errors.
- **Automated Test Suite (`tests/test_h6f_boost.py`):** Expanded to assert `post_esci >= 2024-12-19` alignment with Oct 1–Dec 18 transition donut, unconditional ITT + KM/AJ competing-risks CIF parity across `tables/table1b_esci_itt_and_cif.csv` and `manuscript_h6f_boost.md`, dual `66.8%` / `81.2%` denominators, explicit reporting of both citation TOST bounds (`±15% p = 0.0508` and `±20% p = 0.0125`), zero overclaim regressions, zero PDF leaks, and 100% live disk `SHA256SUMS.json` parity.
- **Visual PDF Inspection:** Rendered pages covering Abstract, Revision/ESCI (Section 4.1 + Table 1B + Figure 1), Citations/Attention (Section 4.2 + Figure 2), Clarivate Delisting (Sections 4.3–4.4 + Figures 3–5), and Limitations (Section 5.3) visually inspected via `read_file`, with temporary preview PNGs deleted prior to regenerating `SHA256SUMS.json`.
