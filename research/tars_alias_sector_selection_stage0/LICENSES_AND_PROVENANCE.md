# Licenses, Provenance & Exclusions — TARS Stage-0 Feasibility Archive

## 1. Upstream Public Sources, Reuse Licenses & Attribution

- **MAST High-Level Science Product (HLSP) — TARS (`v01` per-sector FITS light curves):**
  - Product Page: `https://archive.stsci.edu/hlsp/tars`
  - Persistent DOI: `10.17909/2sff-fn29`
  - Citation / Attribution: Boyle, A. W., Bouma, L. G., & Mann, A. W. (2025/2026), *TESS All-Sky Rotation Survey (TARS)* (`arXiv:2603.05586`), hosted at the Mikulski Archive for Space Telescopes (MAST, Space Telescope Science Institute) using NASA TESS mission FFI data.
  - License Verified in FITS `HDU 0` (`LICENSE` header across all verified files): **Creative Commons Attribution 4.0 International (`CC BY 4.0`)** — `https://creativecommons.org/licenses/by/4.0/`.
  - Reuse Scope in This Archive: Raw FITS files are **excluded**. Compact numeric summary statistics (`stage0_fits_and_coverage_receipt.json`, `stage0_ambiguity_and_shape_summary.json`, `stage0_ambiguity_and_shape_stars.jsonl`) contain derived timestamps/periodogram/subspace-geometry metrics computed directly by our scripts from `CC BY 4.0` HLSP TARS FITS files, with full attribution preserved.

- **TARS Validation Samples Archive (Zenodo Record `19917941`):**
  - Persistent URL: `https://zenodo.org/records/19917941`
  - Specific Archive Used Locally (Excluded from Git): `validation_samples.zip` (`82,732,764 B`, MD5 `1d31cd3c1ae2bc52f81484de7b28ee33`, SHA-256 `96b405ac3bbb99626f068f4a35dcfc7b1a754106d700a221a94f439770066b62`).
  - License: **Creative Commons Attribution 4.0 International (`CC BY 4.0`)**.
  - Upstream Catalog Provenance: `k2_validation_sample.feather` and `mcquillan_holdout.feather` link TESS Input Catalog (`TICID`) and TESS sector/camera/CCD coverage to external K2 rotation compilations and the McQuillan, Mazeh, & Aigrain (2014, *ApJS* 211, 24) Kepler rotation catalog.
  - Reuse & Blindness Scope in This Archive: Only `TICID`, `sector`, `camera`, `ccd`, source partition tag (`"k2"` / `"mcquillan"`), and aggregate integer counts of stars having a finite positive `Prot` availability flag were derived. **Zero** external numeric `Prot` values and **zero** TARS catalog period/power/classifier columns are stored or redistributed in this archive.

- **Software Dependencies (`requirements.lock.txt`):**
  - `astropy==8.0.3` (BSD-3-Clause), `numpy==2.5.5` (BSD-3-Clause), `scipy==1.18.1` (BSD-3-Clause), `pandas==3.1.1` (BSD-3-Clause), `pyarrow==26.0.1` (Apache-2.0), `PyYAML==6.0.4` (MIT), `python-dateutil==4.0.0` (Apache-2.0 / BSD-3-Clause), `packaging==26.4` (Apache-2.0 / BSD-2-Clause), `pyerfa==2.0.1.5` (BSD-3-Clause), `tzdata==2026.6` (Apache-2.0).

## 2. Explicit Archive Exclusions

The following files and directories are strictly **excluded** from the archive branch `archive/tars-alias-sector-selection-stage0-20261124`:
- All raw downloaded per-sector FITS files (`raw_stage0/stage0_cohort_fits/*.fits` — `210` files; `raw_stage0/verified_fits/*.fits` — `13` files; `raw_stage0/hlsp_tars_tess_ffi_s0067-*.fits`).
- The Zenodo reference archive (`raw_stage0/validation_samples.zip`) and any extracted feather/CSV tables.
- Copied upstream documentation (`raw_stage0/hlsp_tars_readme.txt`, `raw_stage0/HOW_TO_USE.md`).
- Virtual environment and caches (`.venv/`, `__pycache__/`).
- Superseded local Stage-0/Stage-1 draft notes (`STAGE0_TARS_FEASIBILITY_RECEIPT.md`, `STAGE1_TARS_SECTOR_SELECTION_PROTOCOL.md`).
- Desktop steering notes (`desktop_*.txt`), credentials, PDFs, local PR handoff helper files (`PR_HANDOFF.md`, `PR_TITLE.txt`, `PR_BODY.md`), and any changes outside `research/tars_alias_sector_selection_stage0/`.
