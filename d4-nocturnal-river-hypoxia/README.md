# D4 Boost: Continental Nocturnal River Hypoxia Acceleration & the 24-Hour Observational Clock-Bias Under Climate Warming

**Track:** Pure Track A — Earth, Climate & Hydrologic Science  
**Deliverables:** Full reproducible USGS NWIS + USACE NID + UK Environment Agency pipeline, 5 publication-grade 300-DPI PNG + vector PDF figures, 7 zero-NaN CSV tables, compiled journal-grade manuscript (`manuscript_d4_boost.pdf` & `manuscript_d4_boost.md`), expanded automated `pytest` verification suite (including programmatic manuscript-vs-receipt parity checks), `0` ruff errors, and SHA-256 cryptographic manifest (`SHA256SUMS.json`).

---

## Core Findings at a Glance

- **Purified Continental Free-Flowing River Census (`2005–2025`):** `397` systematically dam-, tailrace-, lock-, water-control-structure (`S-79`/`S-40`), lake-, canal-, estuary-, swamp-, Klamath-, and salinity-filtered (`SpCond <= 5,000 uS/cm`) CONUS rivers across `38` states and `17/18` HUC-2 watershed basins (`1,446,764` total station-days; `771,486` warm-season days), geospatially linked to all **`62,226` dams** in the official USACE National Inventory of Dams (NID).
- **Continental Diurnal Thermal Decoupling (`N = 324` Q-controlled rivers, `Year × Month FE + log(Q) + log(Q)^2`):**
  - Nocturnal `DO_min`: `-0.2319 mg/L/°C` (`99.4%` neg) — **25.1% faster** than barometric- and water-vapor-adjusted Benson–Krause Henry's Law (`-0.1855`; excess `-0.0465`, HUC-2 `p = 6.34e-8`, State `p = 2.40e-10`).
  - Daytime `DO_max`: `-0.1566 mg/L/°C` — **15.6% slower** than Henry's Law (photosynthetic buffering `+0.0289`, HUC-2 `p = 0.0070`).
  - Diurnal decoupling `d(DO_min - DO_max)/dT`: **`-0.0754 mg/L/°C`** (`87.3%` of rivers negative, `16/17` HUC-2 basins negative; HUC-2 `p = 7.70e-9`, State `p = 1.98e-8`, cluster bootstrap `p = 0.0002`). Strengthens under official **USACE NID dam-free restriction** (`>5 km` from `>=500 af` dam, `N = 242`: **`-0.0795, p = 4.50e-9`**; `>10 km` from `>=5,000 af` dam, `N = 247`: **`-0.0765, p = 7.97e-9`**; `>5 km` from *any* dam, `N = 141`: **`-0.0903, p = 4.05e-5`**), and remains invariant to exact diurnal `T_min/T_max` solubility, SpCond, turbidity, 2-km reach deduplication (`-0.0753`), and `float64` pooled panel estimation (`607,735` river-days, `21,155` absorbed FE cells, `-0.0734, p = 2.34e-9`).
- **24-Hour Clock-Bias Census (`N = 139` multi-year 15-min USGS IV rivers, `25` states, `17` HUC-2 basins, `92,800` warm-season river-days, `2021–2024`):**
  - **Afternoon grab samples (`13:00–16:00` civil clock; WQP/GEMStat / Zhi et al. *NCC* 2023):** underestimate true nocturnal warming sensitivity by **`53.4%`** (**`72.8%`** under instantaneous grab temperature `T(h)`; **`33.5%`** after discharge control, `p = 5.12e-4`), overestimate DO by `+1.64 mg/L`, and miss **`65.3%–72.6%`** of `<5` to `<3 mg/L` nocturnal hypoxic days.
  - **Landsat sun-synchronous overpasses (`10:00–11:00` LST; Guan et al. *Sci. Adv.* May 2026):** miss **`52.8%–67.8%`** of `<5` to `<3 mg/L` nocturnal hypoxic days (`+1.17 mg/L` bias) alongside **`31.0%`** slope attenuation (`19.6%` discharge-controlled).
  - **Well-Conditioned 17-Fold Leave-One-HUC2-Basin-Out Transfer Function (`max VIF = 3.09–4.00`):** anchored by the $20^\circ\text{C}$-centered daytime supersaturation hinge (`+1.08–1.09 mg/L` overnight drawdown per `1 mg/L` supersaturation), removes **`95.8%–97.6%`** of mean concentration bias, cuts RMSE by **`45.0%–56.8%`** (matching or beating a 21-feature nonlinear piecewise-spline benchmark), and recovers **`69.7%–86.0%`** of missing warming sensitivity strictly out-of-sample.
- **Compound Heatwave × Drought (`N = 319`):** daytime `DO_max` is completely null (`+0.0555 mg/L, p = 0.605`; `<5 mg/L` hypoxia `+0.62 pp, p = 0.161`), while nocturnal `DO_min` collapses `-0.8542 mg/L` (`p = 2.19e-6`) with super-additive biological deficit (`-0.0349 mg/L, p = 0.0288`) and super-additive hypoxia surges across all thresholds (`<5 mg/L`: `+2.25 pp` interaction, `p = 0.0036`; `+9.90 pp` total = `16.0×` daytime; `<3 mg/L`: `+0.62 pp, p = 0.0173`; `<2 mg/L`: `+0.52 pp, p = 0.0227`).
- **Uniform Discharge-Controlled Split-Half Productivity Mechanism (`N = 271`):** early-half baseline diurnal swing predicts late-half decoupling out-of-sample with Spearman `r = -0.6755` (`p = 1.81e-37`, `R² = 0.475`), widening `13.9×` from oligotrophic to eutrophic quartiles (where nocturnal loss runs `42.2%` faster than physical solubility).
- **Secular 20-Year Audit (`N = 194`, `2005–2025`):** Clean Water Act nutrient recovery masks average CONUS nocturnal decline (`Bio Deficit +0.1144, p = 0.0270`), yet faster-warming rivers (`>= +0.25 °C/dec`) reverse CWA nocturnal gains (`dDO_min = -0.0275`) and widen diurnal swings (`r = +0.295, p = 2.96e-5`).
- **Spatially Clustered Trans-Atlantic Independent Replication (UK Environment Agency, `N = 65` clean 2-km-deduplicated English rivers, `19` 1° grid clusters, `54` river clusters, `33,019` warm-season river-days):** reproduces diurnal decoupling (`-0.0947 mg/L/°C`, 1°-grid CR1 `p = 1.98e-4`, river `p = 1.13e-6`), nocturnal respiratory excess (`-0.0389`, grid `p = 0.0085`), daytime buffering (`+0.0557`, grid `p = 0.0355`), afternoon clock bias (`29.1%` solar / `27.5%` civil BST; `61.3%–66.4%` hypoxia blindness), and Landsat clock bias (`15.1%` attenuation; `50.4%–58.4%` hypoxia blindness).

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

- `scripts/` — End-to-end deterministic data fetch, hydrologic purification, USACE NID dam linkage, econometrics, UK replication, figures, PDF compilation, and manifest scripts (`00`–`08`).
- `data/processed/` — Purified CONUS and UK river metadata, exclusion audit logs, verified Crossref bibliography, and river-level econometric panels.
- `results/` — Authoritative JSON empirical receipts (`d4_econometric_hydrologic_results.json`, `conus_iv_24h_clock_results.json`, `uk_ea_replication_results.json`).
- `tables/` — 7 zero-NaN publication CSV tables.
- `figures/` — 5 publication-grade `300 DPI PNG` + vector `PDF` figures.
- `tests/` — Expanded automated `pytest` verification suite including programmatic manuscript-vs-JSON/CSV parity checks.
- `manuscript_d4_boost.md` & `manuscript_d4_boost.pdf` — Full submission-ready manuscript and compiled journal-grade PDF.
- `SHA256SUMS.json` & `VERIFICATION_MANIFEST.md` — Cryptographic checksums of all project deliverables.
