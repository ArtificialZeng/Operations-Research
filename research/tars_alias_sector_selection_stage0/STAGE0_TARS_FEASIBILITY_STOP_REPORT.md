# Stage-0 Feasibility Audit & Stop Report — TARS Retrospective Second-Sector Selection

**Verdict:** **`STOP_STAGE0_INSUFFICIENT_SEPARABLE_AMBIGUOUS_CASES`**  
**Date Frozen:** 2026-11-24  
**External Outcome Blindness:** **100% preserved** — Stage-0 terminated strictly prior to reading, storing, or scoring any numeric external `Prot` reference period. Earlier local Stage-1 design notes are superseded by this Stage-0 stop decision.

---

## 1. Objective & Framing

This Stage-0 feasibility study evaluated whether archived TESS All-Sky Rotation Survey (TARS) multi-sector light curves yield enough genuinely first-sector-ambiguous stars for a clean fixed-budget (two-sector) retrospective second-sector selection test, in which a **time-translation-invariant, phase-flexible within-sector subspace similarity selector (`min_rho_1h`)** actually selects different candidate second sectors than strong same-budget baselines (`max_cadences`, `farthest_temporally`, `max_duration`).

- This is strictly **retrospective data selection** at a fixed two-sector analyzed light-curve budget, **not** scheduling future telescope pointings.
- Existing statistical periodogram and alias-discrimination literature is explicitly acknowledged with no novelty claims:
  - **Baluev (2008)**, *MNRAS* 385, 1279 (`10.1111/j.1365-2966.2008.12689.x`): analytic false-alarm probability and extreme-value aliasing analysis of Lomb-Scargle periodograms.
  - **Dawson & Fabrycky (2010)**, *ApJ* 722, 937 (`10.1088/0004-637X/722/1/937`): spectral window functions for discriminating periodogram aliases.
  - **Boyle, Bouma, & Mann (2025/2026)**, TARS (`arXiv:2603.05586`, MAST HLSP `DOI: 10.17909/2sff-fn29`, Zenodo `19917941`): TESS FFI rotation-period extraction, cross-sector reliability aggregation, and harmonic classification.
  - Additional background: `arXiv:2504.13262` (K2–TESS sector stitching), Bell et al. (2018, `arXiv:1812.03142`), and Angus et al. (2018, `arXiv:1706.05459`).

---

## 2. Verified Public Data Pins, Schema & Co-Located `TIME` Audit

All raw data sources remained external (excluded from this git archive) and were verified by exact byte counts and cryptographic digests:

| Upstream Public Artifact | Source / Persistent ID | License | Bytes | SHA-256 (or MD5) |
|---|---|---|---:|---|
| MAST HLSP TARS Readme | `https://archive.stsci.edu/hlsp/tars` (`DOI: 10.17909/2sff-fn29`) | `CC BY 4.0` | `10,927` | `b2f7e4a275cabcdc49143099cb107fa6c6af512f81c4225296c5a9350dcc41c9` |
| MAST HLSP Example FITS (`s0067-TIC167811790`) | `mast:HLSP/tars/sec_67_cam_2_ccd_4/...` | `CC BY 4.0` | `149,760` | `139f3edd24e415cc805f668a333e676b8fabfaa6cce86c862b417ca7b05816eb` |
| Zenodo `HOW_TO_USE.md` | `https://zenodo.org/records/19917941` | `CC BY 4.0` | `14,845` | `948896d5ed012b34bc3d8341287eaa5c12c7976f799c90776b04ea468df678d8` (MD5 `519ccd060537019d18179085a022e599`) |
| Zenodo `validation_samples.zip` | `https://zenodo.org/records/19917941` | `CC BY 4.0` | `82,732,764` | `96b405ac3bbb99626f068f4a35dcfc7b1a754106d700a221a94f439770066b62` (MD5 `1d31cd3c1ae2bc52f81484de7b28ee33`) |

- The 13 GB `tars_table_4` master table was **never** downloaded.
- Resolved direct MAST per-sector FITS URI template:
  `https://mast.stsci.edu/api/v0.1/Download/file?uri=mast:HLSP/tars/sec_<sector>_cam_<camera>_ccd_<ccd>/hlsp_tars_tess_ffi_s<SSSS>-<TIC16>_tess_v01_lc.fits`
- **FITS Structure (`13` Spot-Check FITS in `stage0_outputs/stage0_fits_and_coverage_receipt.json`, SHA-256 `df76c0603b74412fc0799a30ca9bbd6cec9930870556d2da85996d6b83a81919`):**
  - `HDU 1 (LIGHTCURVE)` contains only `TIME` (`float64`, BTJD days) and `FLUX` (`float32`), with **no** `QUALITY` column.
  - Flux-derived periodogram headers (`PER1`, `POW1`, `PER2`, `POW2`, `AMPFIT`, `SNR`, `BIC1T`) exist in `HDU 1` and were **strictly ignored** in both scripts.
  - Verified cadence regimes: `1800s` (~1,190 rows), `600s` (~2,794–3,917 rows), and `200s` (~9,577–11,268 rows).
- **Co-Located `(sector=42, camera=3, ccd=2)` `TIME`-Sampling Audit (`TIC 388814959` vs. `TIC 248342750`):**
  - `n_rows = 2,874` vs. `2,874` (`same_row_count = true`), `span = 25.17514 d` vs. `25.17514 d`, `max_abs_barycentric_time_diff_s = 0.0 s`, `diff_std_s = 0.0 s`.
  - Confirms `TIME` in TARS HLSP FITS reflects pure sector-camera-CCD temporal sampling rather than star-specific flux/outlier clipping.

---

## 3. Catalog Upper Coverage vs. Bounded Usable Stage-0 Cohort (`48` Stars, `210` FITS)

Catalog upper bounds and successfully fetched Stage-0 samples must be kept strictly separate:

| Benchmark Partition (Zenodo `19917941`) | Valid-Flag Rows (`Prot > 0` boolean only) | Unique TICs | TICs `>= 2` Sectors | TICs `>= 3` Sectors (Catalog Upper Bound) | TICs `>= 4` Sectors (Sampling Pool) | Sector Range | Bounded Usable Stage-0 Cohort (`S1` + `>=2` `S2` Verified on MAST) |
|---|---:|---:|---:|---:|---:|---|---:|
| `k2_validation_sample.feather` | `56,320` | `16,823` | `16,074` | `12,126` | `6,881` | `2..96` | **`24` stars** |
| `mcquillan_holdout.feather` | `62,619` | `28,574` | `19,223` | `9,715` | `3,679` | `14..83` | **`24` stars** |
| **Combined (`0` TIC overlap)** | `118,939` | `45,397` | `35,297` | `21,841` | `10,560` | `2..96` | **`48` stars (`210` FITS)** |

- **MAST HLSP Footprint Gap:** `validation_samples.zip` contains stars outside MAST HLSP TARS's released light-curve footprint (notably faint/distant McQuillan stars with `d > 500 pc` or `T > 16`), which return `HTTP 404` when queried on MAST. Therefore catalog row counts (`21,841` TICs with `>= 3` sectors) are strictly an **upper coverage ceiling**, not the MAST-available FITS yield.
- **Deterministic Selection & Download Audit:** Stars were traversed in fixed deterministic order `SHA-256("stage0_ambiguity_v1:{source}:{tic}")` within each `>= 4`-sector pool (up to 5 sectors per star: earliest `S1` + up to `4` later sectors spaced across available coverage), retaining the first `24` K2 and `24` McQuillan stars with verified `S1` (`>= 200` cadences, `>= 15 d` span) and `>= 2` competing `S2` FITS (`30` stars with `3` competing `S2`, `18` stars with `4` competing `S2` -> `48 + 162 = 210` cohort FITS, `17,922,240 B`).
- **Operational Transport Note:** An initial serial MAST download worker stalled on a half-open TCP socket after caching `126` FITS across `29` stars. All `126` cached files and the exact target ordering were preserved verbatim; `stage0_ambiguity_and_shape_audit.py` was switched to cache-respecting `ThreadPoolExecutor(max_workers=5)` with a `12 s` socket timeout, `18 s` read deadline, atomic `.tmp` replacement, and immediate stop on HTTP `400/403/404/500`, completing all `48` stars (`210` FITS) cleanly.

---

## 4. Independent First-Sector Periodogram, Operational Ambiguity Rule & Phase-Flexible Geometry Results

Verified outputs:
- Summary JSON: `stage0_outputs/stage0_ambiguity_and_shape_summary.json` (`SHA-256`: `1599fff502003c7b7727e1aad30006b18bfa452ed425b3efbbf73542d4e8aaf5`)
- Per-star ledger: `stage0_outputs/stage0_ambiguity_and_shape_stars.jsonl` (`SHA-256`: `9086b148969a21e3cf83cb2787ee044628510c3a041b0b1b4e43b3adca4a8f67`)

### 4.1 Exact Method Specification (100% Blind to `Prot` & Candidate `FLUX`)
- **First-Sector Periodogram (`S1` only):** `astropy.timeseries.LombScargle(t, fl, fit_mean=True, center_data=True)` on a uniform linear frequency grid spanning candidate periods **`0.2` to `20.0` days** (`f in [0.05, 5.0] d^-1`, frequency step `df = 1 / (10 * max(T_span, 20.0))`).
- **Excluded Nearest Peaks:** `f_1` is the highest local periodogram maximum; `f_2` is the highest local maximum separated by at least **`1.5` first-sector resolution units** (`|f_2 - f_1| >= 1.5 / max(T_span, 20.0)`). Peaks closer than `1.5` resolution units to `f_1` are excluded by construction.
- **Time-Translation-Invariant Phase-Flexible Subspace Similarity (`rho_1h`, `rho_2h`):** On candidate timestamps `t` alone (never candidate `FLUX`), mean-centered `[cos(2π k f t), sin(2π k f t)]` columns (`k = 1..K`) are QR-orthonormalized to `Q_1, Q_2`, yielding $\rho_{\text{flex}}(t; f_1, f_2) = \frac{1}{2K}\|Q_1^T Q_2\|_F^2 \in [0, 1]$. Verified invariant under `t -> t + 1234.56789 d` to `< 1e-13` for both `K = 1` and `K = 2`.
- **Geometry-Only `fixed-1000` Sensitivity (`min_rho_1h_fixed1000`):** Uniformly subsamples candidate timestamps via `np.linspace(0, len(t) - 1, 1000).round().astype(int)` whenever `len(t) > 1000` (unchanged if `len(t) <= 1000`). Across all `162` competing second-sector light curves (`n_cadences` in `[1190, 11766]`), every candidate had `>= 1,000` points, isolating pure within-sector temporal geometry from raw cadence count.

### 4.2 Stage-0 Quantitative Summary Across Cohorts

| Slice (Operational Detection Rule on Bounded `48`-Star Cohort) | `N` Stars (`K2 / McQ`) | Pair Types | Median `max rho_1h` (Max) | Median `rho_1h` Spread (Max) | `min_rho_1h` != `max_duration` | `min_rho_1h` != `max_cadences` | `min_rho_1h` != `farthest_temporally` | `min_rho_1h` != `fixed-1000` |
|---|---:|---|---:|---:|---:|---:|---:|---:|
| **All Bounded Cohort Stars** | `48` (`24 / 24`) | `29` Dist, `9` Close, `6` 2:1, `4` 3:1 | `0.007729` (`0.112176`) | `0.004428` (`0.038728`) | `26 / 48` | `33 / 48` | `32 / 48` | `3 / 48` |
| **`pow1 >= 0.10` & `pow2/pow1 >= 0.30`** | **`2`** (`1 / 1`) | `1` Close, `1` Dist | `0.043410` (`0.060636`) | `0.012985` (`0.015136`) | `2 / 2` | **`0 / 2`** | **`0 / 2`** | `0 / 2` |
| **`pow1 >= 0.10` & `pow2/pow1 >= 0.40`** | **`1`** (`0 / 1`) | `1` Dist | `0.026184` (`0.026184`) | `0.015136` (`0.015136`) | `1 / 1` | **`0 / 1`** | **`0 / 1`** | `0 / 1` |

*(For completeness: `12 / 48` stars had `pow1 >= 0.10`; `33 / 48` had `pow2/pow1 >= 0.30` and `25 / 48` had `pow2/pow1 >= 0.40` without the `pow1 >= 0.10` floor, predominantly in low-normalized-power stars with median `pow1 = 0.0192`.)*

### 4.3 Exact Inspection of the Two Qualifying Operational-Ambiguity Stars

1. **`K2 TIC 21337961`** (`is_ambiguous_030 = true`, `is_ambiguous_040 = false`):
   - `S1 = Sector 44` (`3,261` cadences, `24.2454 d`): `P1 = 4.56404 d` (`pow1 = 0.30768`), `P2 = 3.45757 d` (`pow2 = 0.11107`, `pow2/pow1 = 0.36100`, `CLOSE_PERIODOGRAM_ALIAS`, `df * span = 1.7`).
   - Competing `S2` candidates: `S45` (`rho_1h = 0.06064`, `3,191` pts, `24.51 d`, `dt = 26.1 d`), `S46` (`rho_1h = 0.05025`, `3,320` pts, `26.63 d`, `dt = 53.1 d`), `S72` (`rho_1h = 0.04980`, `9,577` pts, `25.40 d`, `dt = 760.6 d`).
   - **Selections:** `min_rho_1h = S72`, `min_rho_1h_fixed1000 = S72`, `max_cadences = S72`, `farthest_temporally = S72` (all identical!), while `max_duration = S46` and `min_rho_2h = S46`.
2. **`McQuillan TIC 121602171`** (`is_ambiguous_030 = true`, `is_ambiguous_040 = true`):
   - `S1 = Sector 40` (`3,917` cadences, `28.1947 d`): `P1 = 12.20690 d` (`pow1 = 0.11750`), `P2 = 4.77089 d` (`pow2 = 0.06276`, `pow2/pow1 = 0.53412`, `DISTANT_NON_HARMONIC`, `df * span = 3.6`).
   - Competing `S2` candidates: `S54` (`rho_1h = 0.02618`, `3,571` pts, `26.22 d`, `dt = 378.3 d`), `S55` (`rho_1h = 0.01761`, `3,771` pts, `27.15 d`, `dt = 405.9 d`), `S82` (`rho_1h = 0.01105`, `10,872` pts, `25.85 d`, `dt = 1141.6 d`).
   - **Selections:** `min_rho_1h = S82`, `min_rho_2h = S82`, `min_rho_1h_fixed1000 = S82`, `max_cadences = S82`, `farthest_temporally = S82` (all identical!), while `max_duration = S55`.

---

## 5. Stop Justification & Strict Interpretation Limits

1. **Insufficient Ambiguous & Separable Cohort Under the Pre-Coded Operational Rule:** Only `2 / 48` stars passed `pow1 >= 0.10 & pow2/pow1 >= 0.30` and only `1 / 48` passed `>= 0.40`, and on **100% (`2/2`)** of those stars, `min_rho_1h` collapsed to the **exact same sector choice** as `max_cadences` and `farthest_temporally` (with tiny `rho_1h` values `<= 0.061` and spreads `<= 0.015`). Proceeding to numeric `Prot` evaluation on `1–2` non-separated cases (or relaxing thresholds post-hoc to rescue sample size) would violate the pre-registered Stage-0 stop discipline.
2. **Operational Rule != Universal Prevalence:** `pow1 >= 0.10` with `pow2/pow1 >= 0.30 / 0.40` (on `0.2–20.0 d` periods with `>= 1.5`-resolution-unit peak separation) is strictly an **operational detection rule for this bounded `48`-star cohort**, NOT an astrophysical claim about the overall prevalence of TESS rotation-period aliases.
3. **Zero Outcome Accuracy Claims:** Because Stage-0 stopped cleanly before inspecting any external `Prot` label, no claim is made regarding downstream period-recovery accuracy under any selector.
