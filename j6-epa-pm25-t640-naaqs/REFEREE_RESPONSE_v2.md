# Point-by-Point Referee Response (`v2` Major Revision) — Flagship `J6`

**Manuscript:** *Optical Measurement Bias, Wildfire Smoke Amplification, and Regulatory Triage Under the 2024 U.S. Fine Particulate Matter Standard*  
**Workspace:** `D:\AI_Science\antigravity\j6_boost_epa_pm25_t640_naaqs_20261126`  
**Revision Date:** `2026-11-26`

We thank the external referee for a rigorous, constructive, and scientifically incisive review. Every concrete regulatory, statistical, screening-threshold, and epistemic-framing defect identified in review has been fixed directly in code, empirical receipts, publication figures, manuscript prose/tables, and automated regression tests (`tests/test_j6_boost.py`). Below is a complete point-by-point mapping of every critique to exact code changes and verified empirical outputs.

---

## Comment 1: Distinguish Monitor Design-Value Threshold Reclassifications from Formal Clean Air Act § 107(d) Legal Nonattainment Designations

**Referee Critique:**  
Describing the `47` counties (`18.39M` residents) shifted by EPA's May 2024 T640 alignment as "nonattainment designations" or "flipped from nonattainment to attainment" conflates monitor-level Design-Value threshold exceedances (`>= 9.1 → <= 9.0 µg/m³`) with formal EPA legal nonattainment area designations under Clean Air Act § 107(d), which additionally incorporate a statutory five-factor area analysis (air quality data, emissions, meteorology, geography/topography, and jurisdictional boundaries).

**Actions Taken:**
1. **Manuscript Revision (`scripts/07a_generate_manuscript_md.py`):** Systematically revised the **Abstract, Section 1 (Introduction), Section 2.1 (Regulatory Architecture), Section 4.1, Table 1, Section 4.2, Section 5.1, and Section 7 (Conclusion & Limitations #2)** to distinguish **2021–2023 monitor Design-Value threshold reclassifications (`>= 9.1 → <= 9.0 µg/m³`)** cleanly from **formal Clean Air Act § 107(d) legal nonattainment designations**, explicitly detailing EPA's 5-factor area analysis (air quality, emissions, meteorology, topography, and jurisdictional boundaries).
2. **Figures & PDF Captions (`scripts/06_generate_figures.py`, `scripts/08_compile_manuscript_pdf.py`):** Updated **Figure 1** titles, callout box (`−47 DV-reclassified (−18.4M)`), legend entries (`T640 DV-Reclassified`, `Still ≥9.1 µg/m³ DV`, `Cleanly ≤9.0 µg/m³ DV`), **Figure 2** Panel A title/legend (`DV Threshold Lottery`, `Both ≤ 9.0 µg/m³` / `Both ≥ 9.1 µg/m³`), and both dynamic HTML/PDF captions.
3. **Automated Guardrail (`tests/test_j6_boost.py::test_16`):** Asserts explicit `monitor Design-Value threshold reclassifications` and `5-factor` / `five-factor` disclosures across Abstract, Section 4, Section 7, and Figure 1 caption, and bans leftover `statutory nonattainment lottery` phrasing.

---

## Comment 2: Implement True EPA Wildfire Tier-1 5-Year Historical 98th-Percentile Screening & Correct `> 35 µg/m³` Terminology

**Referee Critique:**  
A single daily reading `> 35 µg/m³` is neither a 24-hour PM2.5 NAAQS violation (which requires a 3-year average of annual 98th percentiles) nor by itself an EPA Wildfire Tier-1 trigger (EPA's Wildfire Tiering Tool uses site-specific **5-year historical 98th-percentile** thresholds, specifically `min(p98_5yr, 35 µg/m³)` for Tier-1/Tier-2 screening).

**Actions Taken (New Code Computation + Terminological Upgrade):**
1. **New Code Implementation (`scripts/03_ee_triage_and_hms_unification.py`):**
   - Added strictly pre-period **5-year historical (`2018–2022`) gravimetric FRM site baseline** computation directly from read-only EPA `daily_88101_2018..2022.zip` records (`p98_hist_1822` and `tier1_min_p98_35 = min(p98_hist_1822, 35.0)` — zero in-sample leakage from `2023–2025`), matched across `220/234` (`94.0%`) collocated `T640_FW` rooftops (median historical FRM `p98 = 18.51 µg/m³`, `0.0% > 35`) and `99/107` (`92.5%`) collocated pure Met One `BAM (170/209)` rooftops (median `20.69 µg/m³`, `21.2% > 35`).
   - Added `run_u1_historical_tier1_screening()` executing exact paired **McNemar binomial tests** and Site-clustered CR1 + Roodman WCB (`B = 499`) paired-difference LPMs comparing `T640_FW` vs. collocated `FRM` and `BAM (170/209)` vs. `FRM` across all paired days, NOAA HMS smoke strata, other-site `>= 25`, and a strict `>= 3` historical-year sensitivity. Results are persisted under `results/03_ee_triage_hms_unification.json["unification_u1_historical_tier1_1822"]`.
2. **Verified New Empirical Results (`2023–2025` against `2018–2022` Historical FRM Baseline):**
   - **NOAA HMS Heavy Smoke (`N = 461` paired days, `160` rooftops):** `T640_FW` exceeds `min(p98_18–22, 35)` **`1.33×` more often** (`168` vs. `126`, `36.44%` vs. `27.33%`, **`42` vs. `0` discordant days**, exact McNemar **`p = 4.55 × 10^-13`**, paired diff `+9.11 pp`, Site-CR1 `t = +7.46`, `p_WCB = 0.002`; strict `>= 3` historical-year sensitivity: `154` vs. `117`, `37` vs. `0`, `p = 1.46 × 10^-11`).
   - **All Paired Days (`N = 60,929` days, `220` rooftops):** `T640_FW` exceeds `min(p98_18–22, 35)` **`1.66×` more often** (`2,224` vs. `1,338`, **`1,043` vs. `157` discordant days**, exact McNemar **`p = 7.24 × 10^-161`**, `t = +7.83`, `p_WCB = 0.002`).
   - **Pure Met One `BAM (170/209)` Placebo:** **Dead null across every single historical Tier-1 stratum** — HMS Heavy: `75` vs. `77`, `5` vs. `7` discordant, McNemar **`p = 0.774`** (`t = -0.71`, `p_WCB = 0.402`; uncapped `> p98_hist`: `74` vs. `77`, `p = 0.549`); All paired days: `498` vs. `517`, **`p = 0.195`**; Other-site `>= 25`: `141` vs. `142`, **`p = 1.000`**.
3. **Accurate `> 35 µg/m³` Terminology:** Permanently retired *"EPA Tier-1 trigger"* and *"24-hr NAAQS violation"* for single-day `> 35 µg/m³` readings; renamed consistently across **Abstract, Section 2.1, Section 6.2, Table 5, Figure 5, and Section 7** to **"24-hour NAAQS level-equivalent daily exceedance (`> 35 µg/m³`)"** (`52` vs. `26`, `26` vs. `0` discordant, McNemar `p = 2.98 × 10^-8`), explicitly noting the statutory 24-hour NAAQS requires a 3-year 98th percentile.
4. **Figure 5 & Table 5 (`scripts/06_generate_figures.py`, `scripts/07a_generate_manuscript_md.py`, `scripts/08_compile_manuscript_pdf.py`):** Rebuilt **Figure 5 Panel A** to display BOTH `24-hr Level-Equiv. (>35 µg/m³)` AND `EPA Tier-1 5-Yr p98 min(p98_18–22, 35)` side-by-side for `T640_FW vs FRM` and `BAM vs FRM` under NOAA HMS Heavy smoke, and added `U1: EPA Tier-1 5-Yr p98 (Heavy)` directly to **Figure 5 Panel B** and **Table 5**.

---

## Comment 3: Recalibrate "Zero-EIV" and Causal Chemical-Speciation Claims

**Referee Critique:**  
Calling the smoke instruments *"strictly zero-EIV"* overstates Bland-Altman pair means (which eliminate mechanical coupling only under equal instrument error variances), and ambient CSN/IMPROVE regressions cannot by themselves prove causal Mie-scattering calibration formulas without controlled chamber/physical-calibration experiments (as conducted by Long, Urbanski, & Lincoln, 2023).

**Actions Taken:**
1. **EIV-Robust Framing (`scripts/07a_generate_manuscript_md.py`, `scripts/06_generate_figures.py`, `scripts/08_compile_manuscript_pdf.py`):** Replaced all occurrences of *"strictly zero-EIV"*, *"EIV-free"*, and *"Zero-EIV Proof"* across Abstract, Sections 1, 3.2, 5.2, Table 2, Figure 3A, and Conclusion with **"EIV-robust independent-instrument smoke amplification"**, explicitly distinguishing primary independent instruments (leave-one-site-out other-site PM2.5 including FRM/BAM-only sites, and external satellite NOAA HMS plumes) from Bland-Altman pair means (explicitly caveated as an auxiliary diagnostic exact only under equal error variances).
2. **Observational Speciation Recalibration:** Reframed **Section 5.3, Table 3, Figure 3B, Abstract, and Conclusion** as **"observational chemical-speciation and hygroscopicity associations consistent with Mie optical scattering theory"** (`OC +0.657, OC × HMS Heavy +0.287, EC -0.936, RH +0.066` per `+10%`), explicitly crediting **Long, Urbanski, & Lincoln (2023)** for controlled chamber experimental evaluations and explicitly stating in Sections 5.3 and 7 (Policy Reform #1 & Limitation #3) that **controlled multi-site physical calibration and chamber experiments are required to establish causal firmware correction formulas**.

---

## Comment 4: Pillar 3 & `U2` Causal Recalibration (Explicitly Drop "Optical Bias Causes Strategic Filing")

**Referee Critique:**  
Because the within-county-year instrument comparison for EE flagging is null (`p_WCB = 0.931`), cross-monitor T640 deployment is observational, and the main `2022–2023` EE flagging surge occurred *before* EPA's February 2024 final rule took effect, the manuscript must not claim that optical bias causally induces strategic Exceptional Event filing.

**Actions Taken:**
1. **Epistemic Architecture & Causal Core (`Abstract`, `Section 1`, `Section 5`, `Section 6`, `Table 5`, `Figure 5`, `Section 7`):**
   - Repositioned **Pillar 2 + Unification Test `U1`** (same-rooftop `9.5:1` DV threshold lottery, EIV-robust smoke-amplified residual bias, and same-rooftop `2.00×` `>35` / `1.33×` `42 vs. 0` historical 5-year Tier-1 screening divergence—comparing instruments two meters apart on the exact same air parcel) explicitly as the **causal physical core** of the paper.
   - Highlighted upfront in **Abstract, Section 6.1, Figure 4 caption, and Conclusion** that the main `2022–2023` EE surge occurred **before** the February 2024 final rule took effect, reflecting **anticipatory / designation-window retroactive flagging** (`67.5%` unconcurred precautionary flags; null `2024–2025` EPA-concurred flow).
   - Prominently disclosed the **within-county-year FE null for EE flagging (`+0.81 pp, t = +0.10, p_WCB = 0.931`, `N = 981`)** directly in the **Abstract, Section 1, Section 6.2, Table 5 (dedicated row), Figure 5A inset, Figure 5B Honest Nulls section, and Section 7**, while transparently reporting the within-county-year claimed annual-mean reduction (`+0.208 µg/m³, p_WCB = 0.002`, consistent with mechanically larger smoke-day concentrations on T640 when agencies flag county-wide events).
   - **Explicitly retracted/disclaimed any causal claim that optical bias induces strategic EE filing** across Abstract, Section 6.2, Table 5, Figure 5 caption, and Section 7, framing `U2` strictly as a **cross-monitor observational association** (controlling for `State × Year FE` and satellite NOAA HMS plumes).
   - Retired hype phrasing (*"The Killer Unification"*, *"prove Proposition 3 definitively"*).

---

## Verification Summary (`v2`)

| Verification Check | Result |
| :--- | :--- |
| Step 03 (`03_ee_triage_and_hms_unification.py`) | Exit `0`; new `unification_u1_historical_tier1_1822` saved cleanly (zero NaN/Inf) |
| Step 06 (`06_generate_figures.py`) | Exit `0`; all `5` figures regenerated (`300 DPI PNG` + vector `PDF`), visually audited |
| Step 07a & Step 07 (`07a`, `07_verify_citations.py`) | Exit `0`; `16/16` Crossref DOIs live-verified (`100%`), `21/21` two-way citation sync |
| Step 08 (`08_compile_manuscript_pdf.py`) | Exit `0`; `0` leaked LaTeX/Markdown/HTML tokens, visually audited via `read_file` |
| Static Linting (`ruff check scripts/ tests/`) | `0` errors (`All checks passed!`) |
| Regression Suite (`pytest -v tests/test_j6_boost.py`) | `16/16` passed (`100%`), including new `test_16_v2_historical_tier1_screening_and_referee_recalibrations` |
| Integrity Manifest (`SHA256SUMS.json`) | Regenerated via Step 09 (`31` files disk-verified, LF-normalized) |
