# Project Status — D4 Boost (Nocturnal River Hypoxia & 24-Hour Clock-Bias)

- **State:** `PUBLICATION_READY_FROZEN_LOCAL` (pending parent-level git/PR handling)
- **Date:** 2026-11-26
- **CONUS Daily Census:** `397` clean free-flowing rivers (`38` states, `17/18` HUC-2 basins, `1,446,764` station-days, `2005–2025`; `324` with paired continuous discharge; geospatially verified against all `62,226` dams in the official USACE National Inventory of Dams)
- **CONUS 15-Minute IV 24-Hour Clock Census:** `139` clean rivers (`25` states, `17` HUC-2 basins, `92,800` warm-season river-days, `2021–2024`; well-conditioned transfer function `max VIF = 3.09–4.00` benchmarked against 21-feature nonlinear piecewise splines)
- **International Non-U.S. Replication (UK Environment Agency):** `65` clean, 2-km-deduplicated free-flowing English rivers (`19` 1° hydrometric grid clusters, `54` river clusters, `33,019` warm-season river-days)
- **Exclusion Audit:** `148` dam/tailrace/lock/S-structure/lake/estuary/swamp/canal/Klamath USGS gauges + `6` unflagged brackish `SpCond > 5,000 uS/cm` USGS gauges + `67` UK tidal/dam/lake-outflow/STW/groundwater gauges systematically excluded and audited
- **Deliverables Verified:**
  - 5 publication-grade `300 DPI PNG` + vector `PDF` figures (all 5 visually inspected via `read_file`, zero label collisions, centered diverging map, true within-river biological excess CIs)
  - 7 zero-NaN CSV tables in `tables/` (100% parity verified programmatically against JSON receipts and manuscript tables)
  - Submission-ready `manuscript_d4_boost.md` + compiled `manuscript_d4_boost.pdf` (`0` leaked LaTeX/markdown/ASCII/filename tokens, all pages visually audited)
  - Expanded `pytest` verification suite (`100%` passing, including automated manuscript-vs-JSON/CSV exact parity tests)
  - `ruff check scripts tests` (`0` errors)
  - `SHA256SUMS.json` + `VERIFICATION_MANIFEST.md` verified
- **Calibrated Journal-Tier Verdict:**
  - **Primary High-Probability Tier:** *Nature Water* / *Science Advances* / *Nature Communications*
  - **Stretch Tier:** *Nature Climate Change* / *PNAS* (main desk-review friction: sparse public tropical continuous DO sensors and CWA-confounded CONUS average secular trend)
