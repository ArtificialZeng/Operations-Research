# Point-by-Point Response to External Peer Review — D4 Boost (`v2` Major Revision)

**Manuscript:** *Continental Diurnal Dissolved-Oxygen Decoupling, Nocturnal River Hypoxia, and the 24-Hour Observational Clock-Bias* (`manuscript_d4_boost.md` / `manuscript_d4_boost.pdf`)  
**Workspace:** `D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125`  
**Date:** 2026-11-26  

We thank the external referee for a remarkably sharp, code-level technical review. Every single critique pinpointed a concrete, remediable methodological or interpretive vulnerability. Below we document the exact code recomputations, new sensitivity tables, statistical reformulations, manuscript revisions, and automated `pytest` guards implemented in `v2`.

---

## Comment 1 — Strict Astronomical Sunset-to-Sunrise Nocturnal Window (`DO_min_night`), First Threshold-Crossing Time, Continuous Hypoxia Duration, and 24-Hour Completeness / Site-Weighting Sensitivity

### Referee Audit
The referee audited `scripts/03_fetch_iv_24h_clock_census.py` and rightly observed that:
1. Subdaily hypoxia detection used the **full 24-hour daily minimum** (`do_min`) rather than strictly defining an **astronomical sunset-to-sunrise nocturnal window** (`DO_min_night`);
2. The pipeline did not report **first threshold-crossing solar time** or **continuous hypoxia duration (hours/day)** per hypoxic episode; and
3. The subdaily clock-bias audit lacked **24-hour completeness sensitivity** (`>=90%` / `>=86` of 96 15-min intervals/day) and **equal-site vs. site-day weighting** sensitivity.

### Code & Empirical Revisions Implemented
- **Exact Site-Day Astronomical Geometry (`scripts/03_fetch_iv_24h_clock_census.py`, `astronomical_sunrise_sunset_solar_hr` & `compute_astronomical_nocturnal_audit`; replicated at raw 15-minute resolution in `scripts/04_uk_ea_international_replication.py`):**
  - Implemented the exact 3-harmonic Spencer (1971) / Iqbal (1983, Crossref-verified DOI `10.1016/B978-0-12-373750-2.X5001-0`) solar declination $\delta(\gamma)$ and geometric sunrise/sunset equation $\cos(\omega_0) = -\tan(\phi)\tan(\delta)$ for every site-day across all `139` CONUS subdaily stations (`92,800` warm-season river-days; warm-season sunrise `04:00–07:06` LST, mean `05:19`; sunset `16:54–20:00` LST, mean `18:41`; mean astronomical night `10.63 h`).
  - Added strict astronomical nocturnal minimum `do_min_night` alongside full-day `do_min_24h` (15-min and hourly solar grid) and reconstructed all **`91,495` unbroken consecutive midday-to-midday diurnal cycles** ($\text{noon}_d \to \text{noon}_{d+1}$, where astronomical darkness is strictly $[t_{\text{sunset},d}, 24) \cup [0, t_{\text{sunrise},d+1})$ paired to day $d+1$'s `10:00–11:00` overpass and `13:00–16:00` afternoon windows) to avoid calendar-midnight splitting.
- **Verified Empirical Results (`results/conus_iv_24h_clock_results.json`, `tables/table2c_astronomical_night_duration_sensitivity.csv`, `tables/table2d_nocturnal_crossing_duration.csv`, Manuscript Section 2.4, Section 3.2, Table 2b):**
  1. **Nocturnal Timing of Daily Minima & Onset:** Across all `92,800` site-days, **67.0%** of daily minima occur strictly inside astronomical darkness ($\text{sunset} \to \text{sunrise}$), rising to **85.3%** within astronomical darkness plus the 2-hour post-sunrise metabolic lag (when low solar angle and riparian shading keep community oxygen demand above photosynthesis). Among hypoxic days, **53.7%** (`<5`), **61.4%** (`<3`), and **67.8%** (`<2 mg/L`) of daily minima occur strictly inside astronomical darkness (**76.6% / 82.3% / 82.0%** including the 2-hour post-sunrise lag). Along unbroken consecutive cycles, **72.6%** (`<5`), **75.0%** (`<3`), and **63.9%** (`<2 mg/L`) of episodic (non-midday-persistent) first threshold-crossings initiate strictly during astronomical darkness, with median first-crossing at **22:30 LST** (IQR `19:30–02:30`) for `<5 mg/L` and **23:30 LST** for `<3` (IQR `20:30–01:30`) and `<2 mg/L` (IQR `18:30–02:30`).
  2. **Continuous Hypoxia Duration:** Hypoxic episodes are prolonged multi-hour events, lasting continuously for a mean of **12.2 h/day** (median **11.0 h**, IQR `5–19 h`) across all `<5 mg/L` cycles and **8.5 h/day** (median **8.0 h**, IQR `4–12 h`) on episodic overnight-onset cycles; **10.1 h** all / **7.7 h** episodic (medians `9.0 / 7.0 h`) at `<3 mg/L`; and **9.4 h** all / **6.5 h** episodic (medians `7.0 / 5.0 h`) at `<2 mg/L`.
  3. **Strict Astronomical Night vs. Full-Day 24h Slopes & Miss Rates:**
     - Strict astronomical nocturnal temperature sensitivity is `dDO_min_night/dT = -0.2064 mg/L/°C` (vs. `-0.2143` 15-min `DO_min_24h` and `-0.2128` hourly `DO_min_24h`). Afternoon sampling (`13:00–16:00` civil) underestimates strict astronomical nocturnal sensitivity by **51.6%** (HUC-2 `p = 4.13e-6`, State `p = 7.32e-7`; **31.3%** Q-controlled, `p = 8.76e-4`), and the `10:00–11:00` LST overpass window underestimates it by **28.4%** (HUC-2 `p = 1.13e-6`; **16.9%** Q-controlled, `p = 5.94e-4`).
     - Against strict astronomical `DO_min_night` (same-day), afternoon miss rates are **61.9% / 69.3% / 63.7%** (`<5 / <3 / <2 mg/L`) and overpass-window miss rates are **49.0% / 66.0% / 60.4%** (compared to **65.3% / 72.6% / 68.8%** and **52.8% / 67.8% / 65.3%** against `DO_min_24h`). Under strict consecutive overnight continuity (`sunset_d -> sunrise_{d+1}`), miss rates are **63.6% / 71.9% / 68.0%** (afternoon) and **50.5% / 68.0% / 62.8%** (overpass).
  4. **24-Hour Completeness (`>=90%`) & Equal-Site Weighting Sensitivity:**
     - Tightening completeness to **`>=90%` of 96 15-min intervals (`>=86` obs/day; `N = 120` stations, `78,405` site-days)** slightly *increases* slope attenuation (**56.1%** 24h / **54.3%** astro night afternoon; **32.6%** / **29.7%** overpass) and miss rates (**67.0% / 77.7% / 74.2%** 24h and **63.7% / 75.2% / 69.7%** astro night afternoon; **54.2% / 72.8% / 71.5%** 24h and **50.2% / 71.4% / 67.4%** astro night overpass). Cadence-normalized `>=22/24` solar hours (`99.5%` of days) is virtually identical.
     - Switching from pooled site-day weighting to **equal-site weighting** (removing dominance by chronically 24h-hypoxic stations) *increases* miss rates by 8–19 percentage points to **74.7% / 74.5% / 74.6%** (afternoon) and **68.6% / 70.0% / 68.8%** (overpass) against strict astronomical `DO_min_night` (**77.5% / 77.3% / 81.1%** and **71.6% / 73.5% / 76.3%** against `DO_min_24h`; remaining **67.8%–73.1%** afternoon even when restricting to stations with `>=5` hypoxic days).
  5. **UK Raw 15-Minute Astronomical Night Verification (`results/uk_ea_replication_results.json`, Section 3.6):** Across `33,019` warm-season days (`65` screened English stations), **58.8%** of raw 15-min daily minima fall inside astronomical darkness (**74.4%** within night + 2 h post-sunrise lag), strict `dDO_min_night/dT = -0.2470 mg/L/°C` (1°-grid `p = 1.10e-12`), and strict astronomical-night miss rates are **56.7% / 58.5% / 62.8%** (afternoon solar; **55.6% / 56.5% / 61.1%** BST civil) and **48.0% / 48.4% / 54.0%** (overpass `10:00–11:00` LST).

---

## Comment 2 — Rename "Landsat Satellite Clock-Bias" Accurately to "Overpass-Time (Landsat-Window, 10:00–11:00) Sampling Bias"

### Referee Audit
Restricting in-situ DO sensors to `10:00–11:00` local solar time isolates only the **temporal overpass-time sampling bias**, whereas real optical satellite DO retrieval error (e.g., Guan et al., 2026) additionally includes optical retrieval uncertainty, cloud masking, and 16-day revisit intervals.

### Revisions Implemented
- Systematically replaced "Landsat satellite clock-bias" / "Landsat overpasses miss..." with **"overpass-time (Landsat-window, 10:00–11:00 LST) sampling bias"** across the Abstract, Introduction, Methods (Section 2.4), Results (Sections 3.2, 3.3, 3.6; Tables 2, 2b, 5), Discussion (Section 4), Limitations (Section 5, Item 3), Figures 2 & 5 legends/annotations (`scripts/06_generate_figures_tables.py`), Figure captions (`scripts/08_compile_manuscript_pdf.py`), `README.md`, and `STATUS.md`.
- Explicitly stated in Abstract, Introduction, Methods 2.4, Table 2 notes, Discussion 4, Figure 2 caption, and Limitations 5 that our `10:00–11:00` LST in-situ window isolates the **pure temporal sampling bias** of sun-synchronous optical satellites and serves strictly as a temporal benchmark—explicitly acknowledging that optical water-leaving reflectance retrieval uncertainty, clear-sky cloud-masking selection toward brighter/higher-photosynthesis days, and 16-day revisit gaps are not jointly modeled here.

---

## Comment 3 — Drop the Unstable `16×` Ratio Headline (`+9.90 pp / +0.62 pp`) & Report Exact Probability Differences + Bounded Contrasts + Interaction CIs

### Referee Audit
Dividing `+9.90 pp` nocturnal compound hypoxia surge by an insignificant daytime denominator (`+0.62 pp, p = 0.161`) produces an unbounded ratio confidence interval and should not be used as a headline metric.

### Code & Manuscript Revisions Implemented
- **Removed every instance of `16×` / `16.0×`** across `manuscript_d4_boost.md`, `manuscript_d4_boost.pdf`, `README.md`, `STATUS.md`, and figure captions (and added a strict regex guard in `scripts/08_compile_manuscript_pdf.py` and `tests/test_d4_pipeline.py` enforcing zero occurrences!).
- **Added bounded within-station Night-minus-Day probability contrast (`scripts/05_econometric_hydrologic_suite.py`, `hyp5_min_minus_max`):** Directly estimated $P(DO_{\min} < 5) - P(DO_{\max} < 5)$ inside each river's Year $\times$ Month FE Hot $\times$ Dry regression across `N = 319` screened stations (`tables/table3_compound_hot_x_dry.csv`, Manuscript Table 3, Abstract, Section 3.4, Section 4):
  - Nocturnal `<5 mg/L` total compound shift: **`+9.90 pp`** (HUC-2 95% CI **`[+4.83, +14.97] pp`**, `p = 7.72e-4`) vs. Daytime `<5 mg/L`: **`+0.62 pp`** (95% CI **`[-0.27, +1.51] pp`**, `p = 0.161`, statistically null).
  - Bounded **Night − Day total compound gap:** **`+9.28 pp`** (HUC-2 95% CI **`[+4.89, +13.68] pp`**, `p = 3.83e-4`; State 95% CI `[+5.94, +12.62] pp`, `p = 2.29e-6`).
  - Bounded **Night − Day formal `Hot × Dry` interaction gap:** **`+2.30 pp`** (HUC-2 95% CI **`[+1.00, +3.61] pp`**, `p = 0.0017`).
  - Reported exact HUC-2 95% CIs for all formal super-additive `Hot × Dry` interactions directly in Abstract, Table 3, and Section 3.4: `<5 mg/L` **`+2.25 pp`** (`[+0.85, +3.65] pp`, `p = 0.0036`); `<3 mg/L` **`+0.62 pp`** (`[+0.13, +1.12] pp`, `p = 0.0173`); `<2 mg/L` **`+0.52 pp`** (`[+0.08, +0.95] pp`, `p = 0.0227`); solubility-adjusted nocturnal deficit `DO_min - DO_sat` **`-0.0349 mg/L`** (`[-0.0657, -0.0041] mg/L`, `p = 0.0288`).

---

## Comment 4 — Recalibrate Mechanism Scope, Clarify Screened Sample Counts (`397` / `324` CONUS; `65` UK), & Explicitly Differentiate Prior Literature

### Referee Audit
1. Observational daily temperature regressions cannot causally isolate dark respiration ($Q_{10}$) from co-varying physical reaeration, irradiance, and flow/depth dynamics;
2. The `397` CONUS stations (`324` in flow-controlled Spec 2) and `65` UK EA stations are screened monitoring subsets, not random stream censuses; and
3. Prior literature (**Zhi et al., 2023, *Nature Climate Change*** and **Blaszczak et al., 2023, *Limnology and Oceanography Letters***) must be explicitly differentiated from `D4`'s value-add.

### Revisions Implemented
- **Mechanism Scope Recalibrated:** Narrowed causal wording throughout Abstract, Title, Introduction, Methods 2.3, Results 3.1/3.5, Figures 1/4/5, Discussion 4, and Limitations 5 (Item 1) to **"observed short-term (within-month) temperature sensitivity of daily dissolved-oxygen extrema (`DO_min` declining 25.1% steeper than equilibrium solubility `-0.1855 mg/L/°C`, whereas `DO_max` declines 15.6% shallower)"**. Explicitly stated that daily observational temperature sensitivity reflects coupled changes in ecosystem respiration, gross primary production, physical reaeration ($k_{O_2}$), solar irradiance/cloudiness, and subdaily depth/flow dynamics, and cannot be causally partitioned without independent whole-stream metabolism and gas-exchange measurements (explicitly citing **Appling et al., 2018**, `10.1038/sdata.2018.292`).
- **Sample Counts & Representativeness Clarified:** Explicitly framed the `397` CONUS stations (`324` in primary flow-controlled Spec 2; `139` in subdaily IV subset) and `65` English UK EA stations everywhere as **screened free-flowing freshwater continuous-monitoring subsets** rather than random stream censuses (explicitly documented in Abstract, Methods 2.1/2.4, Figure 1 & 5 labels/captions, and Limitations 5 Item 2).
- **Prior Literature Explicitly Differentiated & Crossref-Verified (HTTP 200):** Verified via live Crossref REST API queries (`data/processed/verified_references.json`):
  - **Zhi et al. (2023, *Nature Climate Change*, `10.1038/s41558-023-01793-3`, HTTP 200)** — widespread warming-driven river deoxygenation across ~800 U.S./European rivers largely from daytime grab samples and watershed models;
  - **Blaszczak et al. (2023, *Limnology and Oceanography Letters*, `10.1002/lol2.10297`, HTTP 200)** — global continuous-sensor hypoxia prevalence, episode durations, and low-flow/high-temperature drivers;
  - **Guan et al. (2026, *Science Advances*, `10.1126/sciadv.aef3132`, HTTP 200)** — sun-synchronous Landsat ML global deoxygenation attribution;
  - **Appling et al. (2018, *Scientific Data*, `10.1038/sdata.2018.292`, HTTP 200)** — 356-river USGS inverse metabolism/reaeration benchmark;
  - **Iqbal (1983, *An Introduction to Solar Radiation*, `10.1016/B978-0-12-373750-2.X5001-0`, HTTP 200)** — Spencer–Iqbal solar declination and sunset/sunrise hour-angle geometry.
  - Positioned `D4`'s distinct contribution in Introduction and Discussion squarely on: (i) quantified 24-hour clock-bias miss rates and slope attenuation, (ii) exact astronomical sunset-to-sunrise crossing/duration accounting and completeness/site-weighting sensitivity, (iii) out-of-sample 17-fold LOHUC2 transfer-function bias correction, and (iv) spatially clustered UK trans-Atlantic replication.

---

## Verification Summary (`v2`)

- **Pipeline:** `03`, `04`, `05`, `06`, `08`, `07` re-executed cleanly end-to-end (`exit code 0`).
- **Tables:** 9 zero-NaN CSV tables in `tables/` (including new `table2c_astronomical_night_duration_sensitivity.csv` and `table2d_nocturnal_crossing_duration.csv`), with programmatic manuscript-vs-receipt parity verified in `tests/test_d4_pipeline.py`.
- **Visual & Token Audit:** All 5 updated figures and updated compiled PDF pages visually inspected via `read_file`; `0` leaked LaTeX/Markdown/ASCII/`16×` tokens in `manuscript_d4_boost.pdf`.
- **Automated Checks:** `ruff check scripts tests` = `0` errors; `pytest -v tests/test_d4_pipeline.py` = `100%` passing; `SHA256SUMS.json` & `VERIFICATION_MANIFEST.md` regenerated.
