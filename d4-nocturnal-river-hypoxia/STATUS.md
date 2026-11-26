# Project Status — D4 Boost v2 (Diurnal DO Decoupling, Nocturnal River Hypoxia & 24-Hour Clock-Bias)

- **State:** `V2_REFEREE_REVISION_COMPLETE_LOCAL` (pending coordinator verification and push)
- **Date:** 2026-11-26
- **CONUS Daily Screened Monitoring Subset:** `397` screened free-flowing freshwater USGS stations (`38` states, `17/18` HUC-2 basins, `1,446,764` station-days, `2005–2025`; `324` in the primary discharge-controlled Spec 2; geospatially verified against all `62,226` dams in the official USACE National Inventory of Dams)
- **CONUS Subdaily IV 24-Hour Clock & Astronomical Nocturnal Audit:** `139` screened stations (`25` states, `17` HUC-2 basins, `92,800` warm-season river-days, `91,495` consecutive day pairs, `2021–2024`; exact Spencer/Iqbal astronomical sunset-to-sunrise `DO_min_night` alongside full-day `DO_min_24h`, first threshold-crossing solar hour, continuous hypoxia duration hours, `>=90%` / `>=86/96` completeness sensitivity, equal-site vs. site-day weighting, and well-conditioned 17-fold LOHUC2 transfer function `max VIF = 3.09–4.00`)
- **International Non-U.S. Replication (UK Environment Agency):** `65` screened, 2-km-deduplicated free-flowing English monitoring stations (`19` 1° hydrometric grid clusters, `54` river clusters, `33,019` warm-season river-days, including exact raw 15-minute astronomical sunset-to-sunrise verification)
- **v2 Referee Revisions Completed:**
  1. True astronomical sunset-to-sunrise nocturnal window (`DO_min_night`), first threshold-crossing solar hour, continuous hypoxia duration hours, `>=90%` (`>=86/96`) completeness sensitivity, and equal-site vs. site-day weighting implemented in `scripts/03_fetch_iv_24h_clock_census.py` & `scripts/04_uk_ea_international_replication.py` and reported in Tables 2b/2c/2d and manuscript.
  2. Renamed satellite framing accurately to **Overpass-Time (Landsat-Window, 10:00–11:00 LST) Sampling Bias**, explicitly stating it isolates pure temporal overpass sampling bias without modeling optical retrieval error, cloud masking, or 16-day revisit intervals.
  3. Removed unstable `16×` ratio headline everywhere; reported exact probability shifts (`+9.90 pp` vs. `+0.62 pp`), bounded night-minus-day compound gap (`+9.28 pp`, 95% CI `[+4.89, +13.68] pp`, `p = 3.83e-4`), and exact HUC-2 95% CIs on all super-additive `Hot × Dry` interactions (`+2.25 pp`, `+0.62 pp`, `+0.52 pp`).
  4. Recalibrated mechanism scope to observed short-term temperature sensitivity of daily DO extrema (acknowledging coupled metabolic/reaeration/irradiance/flow dynamics requiring independent metabolism modeling such as Appling et al. 2018), clarified screened monitoring subsets (`397` / `324` CONUS; `65` UK), and explicitly differentiated Crossref-verified Zhi et al. (2023) and Blaszczak et al. (2023).
- **Deliverables Verified:**
  - 5 publication-grade `300 DPI PNG` + vector `PDF` figures (visually audited via `read_file`)
  - 9 zero-NaN CSV tables in `tables/` (100% programmatic parity verified against JSON receipts and manuscript tables)
  - Submission-ready `manuscript_d4_boost.md` + compiled `manuscript_d4_boost.pdf` (`0` leaked tokens, updated pages visually audited)
  - Point-by-point `REFEREE_RESPONSE_v2.md`
  - Expanded `pytest` suite (`100%` passing) & `ruff check scripts tests` (`0` errors)
  - `SHA256SUMS.json` + `VERIFICATION_MANIFEST.md` regenerated and verified
