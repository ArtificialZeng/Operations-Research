# D4 Boost (v2): Continental Diurnal Dissolved-Oxygen Decoupling, Nocturnal River Hypoxia & the 24-Hour Observational Clock-Bias

**Track:** Pure Track A — Earth, Climate & Hydrologic Science  
**Revision:** `v2` Major Revision addressing all external peer-review critiques (`REFEREE_RESPONSE_v2.md`)  
**Deliverables:** Full reproducible USGS NWIS + USACE NID + UK Environment Agency pipeline, 5 publication-grade 300-DPI PNG + vector PDF figures, 9 zero-NaN CSV tables, compiled journal-grade manuscript (`manuscript_d4_boost.pdf` & `manuscript_d4_boost.md`), point-by-point referee response (`REFEREE_RESPONSE_v2.md`), expanded automated `pytest` verification suite (including programmatic manuscript-vs-receipt parity checks), `0` ruff errors, and SHA-256 cryptographic manifest (`SHA256SUMS.json`).

---

## Core Findings at a Glance

- **Screened Continental Free-Flowing Freshwater Monitoring Subset (`2005–2025`):** `397` systematically dam-, tailrace-, lock-, water-control-structure (`S-79`/`S-40`), lake-, canal-, estuary-, swamp-, Klamath-, and salinity-filtered (`SpCond <= 5,000 uS/cm`) CONUS USGS stations across `38` states and `17/18` HUC-2 watershed basins (`1,446,764` station-days; `771,486` warm-season days; `324` stations in the primary flow-controlled Spec 2), geospatially audited against all **`62,226` dams** in the official USACE National Inventory of Dams (NID).
- **Observed Short-Term Diurnal Thermal Decoupling (`N = 324` flow-controlled stations, `Year × Month FE + log(Q) + log(Q)^2`):**
  - Daily minimum `DO_min`: `-0.2319 mg/L/°C` (`99.4%` neg) — **25.1% steeper** than barometric- and water-vapor-adjusted Benson–Krause equilibrium solubility (`-0.1855`; excess `-0.0465`, HUC-2 `p = 6.34e-8`, State `p = 2.40e-10`).
  - Daytime `DO_max`: `-0.1566 mg/L/°C` — **15.6% shallower** than equilibrium solubility (buffering `+0.0289`, HUC-2 `p = 0.0070`).
  - Diurnal decoupling `d(DO_min - DO_max)/dT`: **`-0.0754 mg/L/°C`** (`87.3%` negative, `16/17` HUC-2 basins negative; HUC-2 `p = 7.70e-9`, State `p = 1.98e-8`, cluster bootstrap `p = 0.0002`). Strengthens under official **USACE NID dam-free restriction** (`>5 km` from `>=500 af` dam, `N = 242`: **`-0.0795, p = 4.50e-9`**; `>10 km` from `>=5,000 af` dam, `N = 247`: **`-0.0765, p = 7.97e-9`**; `>5 km` from *any* dam, `N = 141`: **`-0.0903, p = 4.05e-5`**), and remains invariant to exact diurnal `T_min/T_max` solubility, SpCond, turbidity, 2-km reach deduplication (`-0.0753`), and `float64` pooled panel estimation (`607,735` river-days, `-0.0734, p = 2.34e-9`). Short-term daily temperature sensitivity reflects coupled metabolic, reaeration, irradiance, and subdaily hydrologic co-variation.
- **24-Hour Clock-Bias Census & Astronomical Sunset-to-Sunrise Nocturnal Audit (`N = 139` subdaily USGS IV stations, `25` states, `17` HUC-2 basins, `92,800` warm-season river-days, `2021–2024`):**
  - **Exact Astronomical Night (`cos(omega_0) = -tan(phi)*tan(delta)`):** `67.0%` of all daily minima fall strictly inside astronomical darkness (`85.3%` within astronomical night + 2 h post-sunrise lag). On episodic hypoxic cycles (`91,495` consecutive day pairs), `72.6%–75.0%` of first `<5` and `<3 mg/L` crossings occur strictly during astronomical darkness (median onset `22:30–23:30` LST), lasting continuously for a median of **`8.0–11.0 h/day`** (`<5 mg/L`) and **`7.0–9.0 h/day`** (`<3 mg/L`).
  - **Afternoon grab samples (`13:00–16:00` civil clock; WQP/GEMStat / Zhi et al. *NCC* 2023):** underestimate short-term temperature sensitivity by **`53.4%`** against `DO_min_24h` (**`51.6%`** against strict astronomical `DO_min_night`, `p = 4.13e-6`; **`72.8%`** under instantaneous grab temperature `T(h)`; **`31.3%–33.5%`** after discharge control), overestimate DO by `+1.64 mg/L`, and miss **`65.3%–72.6%`** of `DO_min_24h` (**`61.9%–69.3%`** of strict astronomical `DO_min_night`) `<5` to `<3 mg/L` hypoxic days.
  - **Overpass-time (Landsat-window, `10:00–11:00` LST) pure temporal sampling bias:** misses **`52.8%–67.8%`** of `DO_min_24h` (**`49.0%–66.0%`** of strict astronomical `DO_min_night`) `<5` to `<3 mg/L` hypoxic days (`+1.17 mg/L` bias) alongside **`31.0%`** (`28.4%` nocturnal; `16.9%–19.6%` discharge-controlled) slope attenuation — isolating pure temporal overpass bias without modeling optical retrieval error, cloud masking, or 16-day revisit gaps.
  - **Completeness (`>=90%` / `>=86` of 96 15-min intervals/day) & Equal-Site Weighting Sensitivity:** miss rates stay robust or *increase* under `>=86/96` completeness (`63.7%–75.2%` afternoon, `50.2%–71.4%` overpass vs. strict `DO_min_night`) and equal-site weighting (`74.5%–74.7%` afternoon, `68.6%–70.0%` overpass vs. strict `DO_min_night`).
  - **Well-Conditioned 17-Fold LOHUC2 Transfer Function (`max VIF = 3.09–4.00`):** eliminates **`95.8%–97.6%`** of mean concentration bias, cuts RMSE by **`45.0%–56.8%`** (matching or beating a 21-feature nonlinear piecewise-spline benchmark), and recovers **`69.7%–86.0%`** of missing temperature sensitivity strictly out-of-sample.
- **Compound Heatwave × Drought (`N = 319`):** daytime `DO_max` shows zero significant decline (`+0.0555 mg/L, p = 0.605`; `<5 mg/L` hypoxia `+0.62 pp`, 95% CI `[-0.27, +1.51] pp`, `p = 0.161`), while nocturnal `DO_min` drops `-0.8542 mg/L` (`p = 2.19e-6`) with a `+9.90 pp` hypoxia surge (95% CI `[+4.83, +14.97] pp`, `p = 7.72e-4`; bounded night-minus-day gap **`+9.28 pp`**, 95% CI `[+4.89, +13.68] pp`, `p = 3.83e-4`) and super-additive `Hot × Dry` interactions across all thresholds (`<5 mg/L`: `+2.25 pp`, 95% CI `[+0.85, +3.65] pp`, `p = 0.0036`; `<3 mg/L`: `+0.62 pp`, `[+0.13, +1.12] pp`, `p = 0.0173`; `<2 mg/L`: `+0.52 pp`, `[+0.08, +0.95] pp`, `p = 0.0227`).
- **Uniform Discharge-Controlled Split-Half Diurnal Amplitude Stratification (`N = 271`):** early-half baseline diurnal swing predicts late-half decoupling out-of-sample with Spearman `r = -0.6755` (`p = 1.81e-37`, `R² = 0.475`), widening `13.9×` from oligotrophic to eutrophic quartiles.
- **Secular 20-Year Audit (`N = 194`, `2005–2025`):** Clean Water Act nutrient recovery masks average CONUS nocturnal decline (`Excess Deficit +0.1144, p = 0.0270`), yet faster-warming rivers (`>= +0.25 °C/dec`) neutralize those gains (`dDO_min = -0.0275`) and widen diurnal swings (`r = +0.295, p = 2.96e-5`).
- **Spatially Clustered Trans-Atlantic Independent Replication (UK Environment Agency, `N = 65` screened 2-km-deduplicated English stations, `19` 1° grid clusters, `54` river clusters, `33,019` warm-season river-days):** reproduces diurnal decoupling (`-0.0947 mg/L/°C`, 1°-grid CR1 `p = 1.98e-4`), excess `DO_min` sensitivity (`-0.0389`, grid `p = 0.0085`), daytime buffering (`+0.0557`, grid `p = 0.0355`), afternoon and overpass-window clock biases, and raw 15-minute astronomical sunset-to-sunrise hypoxia miss rates (`55.6%–62.8%` afternoon, `48.0%–54.0%` overpass).

---

## Reproducible Pipeline Execution Order

Run inside the isolated `.venv`:
```powershell
.venv\Scripts\python.exe scripts\00_api_probe.py
.venv\Scripts\python.exe scripts\01_discover_and_filter_conus_sites.py
.venv\Scripts\python.exe scripts\02_fetch_conus_dv_census.py
.venv\Scripts\python.exe scripts\03_fetch_iv_24h_clock_census.py
.venv\Scripts\python.exe scripts\04_uk_ea_international_replication.py
.venv\Scripts\python.exe scripts\05_econometric_hydrologic_suite.py
.venv\Scripts\python.exe scripts\06_generate_figures_tables.py
.venv\Scripts\python.exe scripts\08_compile_manuscript_pdf.py
.venv\Scripts\python.exe scripts\07_build_manifest.py
.venv\Scripts\pytest.exe -v tests\test_d4_pipeline.py
.venv\Scripts\ruff.exe check scripts tests
```

## Directory Layout

- `scripts/` — End-to-end deterministic data fetch, hydrologic purification, USACE NID dam linkage, astronomical sunset-to-sunrise audit, econometrics, UK replication, figures, PDF compilation, and manifest scripts (`00`–`08`).
- `data/processed/` — Screened CONUS and UK station metadata, exclusion audit logs, verified Crossref bibliography, and station-level econometric panels.
- `results/` — Authoritative JSON empirical receipts (`d4_econometric_hydrologic_results.json`, `conus_iv_24h_clock_results.json`, `uk_ea_replication_results.json`).
- `tables/` — 9 zero-NaN publication CSV tables (including `table2c_astronomical_night_duration_sensitivity.csv` and `table2d_nocturnal_crossing_duration.csv`).
- `figures/` — 5 publication-grade `300 DPI PNG` + vector `PDF` figures.
- `tests/` — Expanded automated `pytest` verification suite including astronomical solar geometry unit tests and programmatic manuscript-vs-JSON/CSV parity checks.
- `manuscript_d4_boost.md` & `manuscript_d4_boost.pdf` — Full `v2` submission-ready manuscript and compiled journal-grade PDF.
- `REFEREE_RESPONSE_v2.md` — Point-by-point response mapping every external referee critique to verified code, data, and manuscript revisions.
- `SHA256SUMS.json` & `VERIFICATION_MANIFEST.md` — Cryptographic checksums of all project deliverables.
