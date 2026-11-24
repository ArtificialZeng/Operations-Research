# TARS Retrospective Second-Sector Selection — Stage-0 Feasibility & Stop Archive

**Status:** **`STOP_STAGE0_INSUFFICIENT_SEPARABLE_AMBIGUOUS_CASES`** (frozen prior to any numeric external `Prot` outcome scoring; earlier draft Stage-1 notes are superseded by this Stage-0 stop decision).  
**Archived Directory:** `research/tars_alias_sector_selection_stage0/`  
**Date Frozen:** 2026-11-24

## Summary of Scientific Question & Stage-0 Stop Outcome

At a fixed two-sector analyzed light-curve budget (retrospective data selection on archived TESS light curves, **not** scheduling future telescope pointings), this Stage-0 screen tested whether TARS multi-sector stars provide enough first-sector-ambiguous cases where a time-translation-invariant, phase-flexible within-sector subspace similarity selector (`min_rho_1h`) actually chooses a **different** second archived sector from simple same-budget controls (`max_cadences`, `farthest_temporally`, `max_duration`).

- **Strict External-Label Blindness Maintained:** **Zero** external numeric `Prot` values were ever read, stored, or scored (`validation_samples.zip` `Prot` was reduced immediately to a boolean finite-positive availability flag and dropped). **Zero** candidate second-sector `FLUX` arrays and **zero** FITS `HDU 1` flux-derived periodogram headers (`PER1..5`, `POW1..5`, `AMPFIT`, `SNR`, `BIC1T`) were read during candidate selection.
- **Catalog Upper Coverage vs. Bounded Usable Stage-0 Sample:**
  - *Catalog upper coverage* (Zenodo `19917941` `validation_samples.zip`, non-null `Prot > 0` flag only): `12,126` unique K2 TICs (`56,320` rows; Sectors `2..96`) and `9,715` unique McQuillan Kepler TICs (`62,619` rows; Sectors `14..83`) with `>= 3` sectors (`0` overlapping TICs). Many faint/distant McQuillan stars outside the MAST HLSP TARS `d < 500 pc, T < 16` release footprint return `HTTP 404` on MAST.
  - *Bounded usable Stage-0 cohort*: **`48` stars** (`24` K2 + `24` McQuillan, deterministically SHA-256-ordered from the `>= 4`-sector pools), backed by **`210` verified per-sector MAST HLSP FITS** (`48` Sector-1 + `162` competing Sector-2 files; `17,922,240 B` total), completed after preserving the initial `126` cached files from a stalled serial run and finishing the remaining fetches via cache-respecting bounded parallel retries. An additional `13` spot-check FITS (`stage0_fits_and_coverage_receipt.json`) verified schema, cadence diversity (`1800s / 600s / 200s`), and exact co-located `(sector=42, camera=3, ccd=2)` `TIME` equality (`2,874` vs. `2,874` rows; `max_abs_diff = 0.000 s`).
- **Operational Ambiguity Rule & Exact Stop Gate Outcome:**
  - Using independent `astropy.timeseries.LombScargle` on Sector 1 `(TIME, FLUX)` over candidate periods **`0.2` to `20.0` days** (`df = 1 / (10 * max(T_span, 20.0))`) and excluding nearest competing peaks within **`< 1.5` first-sector resolution units** (`|f_2 - f_1| >= 1.5 / max(T_span, 20.0)`):
    - Only **`2 / 48`** stars satisfied the pre-coded operational rule `pow1 >= 0.10` and `pow2 / pow1 >= 0.30` (`K2 TIC 21337961`, `McQuillan TIC 121602171`).
    - Only **`1 / 48`** star (`McQuillan TIC 121602171`) satisfied `pow1 >= 0.10` and `pow2 / pow1 >= 0.40`.
    - On **both** qualifying stars (`2/2` at `>= 0.30`; `1/1` at `>= 0.40`), the 1-harmonic phase-flexible selector (`min_rho_1h`) selected the **exact same second sector** as both `max_cadences` (`0/2` disagreements) and `farthest_temporally` (`0/2` disagreements), disagreeing only with `max_duration` (`2/2`).
  - **Decision:** **STOP at Stage-0 before any numeric external `Prot` scoring.** Preserve exact gates and archive compact Stage-0 code, receipts, and provenance.

## Scope Boundaries & Non-Claims

- The `pow1 >= 0.10` and `pow2 / pow1 >= 0.30` / `>= 0.40` thresholds represent an **operational detection rule for this bounded `48`-star cohort**, **not** an estimate of the true prevalence of rotation-period aliases across all TESS stars or alternative peak/harmonic detectors.
- Nearest peaks within `1.5` first-sector resolution units (`|f_2 - f_1| < 1.5 / max(T_span, 20.0)`) and periods outside `[0.2, 20.0]` days were excluded by construction.
- The `min_rho_1h_fixed1000` check subsamples timestamps to `1,000` points whenever at least that many points exist (`len(t) > 1000`); across all `162` competing candidate sectors in this cohort (`1,190` to `11,766` cadences), it served strictly as a **geometry-only sensitivity** control.
- **No claims of downstream period-accuracy improvement or universal lack of period ambiguity** are made; no numeric external `Prot` outcomes were evaluated.

## Prior Art Acknowledged

- **Baluev (2008)**, *MNRAS* 385, 1279 (`10.1111/j.1365-2966.2008.12689.x`): extreme-value false-alarm probabilities and periodogram aliasing theory.
- **Dawson & Fabrycky (2010)**, *ApJ* 722, 937 (`10.1088/0004-637X/722/1/937`): window-function alias discrimination in unevenly sampled time series.
- **Boyle, Bouma, & Mann (2025/2026)**, TARS (`arXiv:2603.05586`, MAST HLSP `DOI: 10.17909/2sff-fn29`, Zenodo `19917941`): TESS All-Sky Rotation Survey extraction, cross-sector reliability aggregation, and harmonic classification.
- Related context: `arXiv:2504.13262` (K2–TESS sector-stitching reliability), Bell et al. (2018, `arXiv:1812.03142`, anti-alias cadence selection), and Angus et al. (2018, `arXiv:1706.05459`, starspot phase decoherence).

## Source Pins & Replay Commands

Upstream files are **not** redistributed in this archive (see `LICENSES_AND_PROVENANCE.md`). To replay Stage-0 from scratch:

1. Create a Python `3.12` environment matching `requirements.lock.txt`.
2. Download official Zenodo `validation_samples.zip` (82,732,764 B; MD5 `1d31cd3c1ae2bc52f81484de7b28ee33`; SHA-256 `96b405ac3bbb99626f068f4a35dcfc7b1a754106d700a221a94f439770066b62`) into `raw_stage0/validation_samples.zip`:
   - `https://zenodo.org/records/19917941/files/validation_samples.zip?download=1`
   - Do **not** download the 13 GB `tars_table_4` master table.
3. Run the two archived native Stage-0 scripts in order (both fetch public `CC BY 4.0` per-sector FITS directly from MAST HLSP `https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:HLSP/tars/...`):
   ```bash
   python stage0_tars_feasibility_audit.py
   python stage0_ambiguity_and_shape_audit.py
   ```
4. Verify SHA-256 checksums of `stage0_outputs/stage0_fits_and_coverage_receipt.json`, `stage0_outputs/stage0_ambiguity_and_shape_summary.json`, and `stage0_outputs/stage0_ambiguity_and_shape_stars.jsonl` against `MANIFEST.json`.

## Archived Contents & Exclusions

- **Included:** Two untouched native Stage-0 scripts, three compact Stage-0 numeric JSON/JSONL records (zero external `Prot` values), `STAGE0_TARS_FEASIBILITY_STOP_REPORT.md`, `STATUS.md`, `LICENSES_AND_PROVENANCE.md`, `requirements.lock.txt`, `README.md`, and `MANIFEST.json`.
- **Excluded:** Raw downloaded FITS (`210` cohort FITS + `13` spot-check FITS + example FITS), Zenodo `validation_samples.zip`, copied upstream documentation (`hlsp_tars_readme.txt`, `HOW_TO_USE.md`), `.venv/`, `__pycache__/`, superseded draft Stage-1 notes, desktop steering files (`desktop_*.txt`), credentials, PDFs, and local PR handoff helper files.
