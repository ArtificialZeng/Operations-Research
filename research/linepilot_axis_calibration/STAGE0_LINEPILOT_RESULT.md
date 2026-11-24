# Stage-0 Result & Stage-1 Proposal — Pinned-Code LinePilot Axis-Calibration Bottleneck Diagnostic (`DigitizerBench-Full`, Single-Line Balanced Dev Split)

**Date Sealed:** 2026-11-24  
**Status:** `STAGE0_COMPLETE_GATE_PASSED_PROPOSAL_PENDING_REVIEW`  
**Execution Mode:** CPU-only, workspace-only vendored Tesseract `v5.5.3.20260724`, zero new OCR variant implemented or scored, zero untouched Full `base_id`s opened or downloaded, zero PDF/media/PR/release.

---

## 1. Provenance, Licenses & Explicit Scope Disclosure

- **Benchmark:** Official [`LinePilot/DigitizerBench`](https://huggingface.co/datasets/LinePilot/DigitizerBench), pinned commit `8b4a3190d5991414dad92049671de75754dd9f44`, **Apache-2.0** (`2,980` images across `2,500` unique `base_id`s: `2,440` core + `60` nine-rerender Lite/bridge `base_id`s). `lite.zip` (`17,094,028 B`, LFS SHA-256 `2127fde8...`) was used only for 4-image smoke checks.
- **Baseline Code:** Official [`RayanA07/LinePilot`](https://github.com/RayanA07/LinePilot), pinned commit `8fb89a62fb0565290b72ba61cb073d732d8e7578` (`LinePilot 2.17.1`), **Apache-2.0**, running in an isolated CPU-only Python `3.12.16` `.venv` pinned against upstream `constraints.txt`.
- **Workspace-Only Portable OCR Engine ([`PORTABLE_OCR_RECEIPT.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/PORTABLE_OCR_RECEIPT.json), SHA `a8f3d81f...`):** Extracted only `vendor/tesseract/*` (`tesseract v5.5.3.20260724`, `71` files, `33` DLLs) via Python `PyInstaller.archive.readers.CArchiveReader` from the official `LinePilot v2.17.1` release `Digitizer.exe` (`95,187,314 B`, SHA `5b15b73b...`; temporary `.exe` deleted) into `upstream_linepilot/Digitizer/vendor/tesseract/` — zero global installer, zero PATH or registry edits. Verified `eng.traineddata` (`7d4322bd...`) and `osd.traineddata` (`9cf5d576...`) SHA-256 checksums against `Digitizer/tesseract-lock.json`, `75/75` upstream `pytest` (`1.67 s`), and `3/3` official `tools/smoke_test.py` figures (`0.667%–1.405%` NRMSE).
- **Mandatory Pinned-Code Single-Line Diagnostic Scope Disclosure:**
  - Source audit of `RayanA07/LinePilot` (`8fb89a62`) and all public `RayanA07` repos/branches verified that `Digitizer/digitizer_api.py` automatically detects and exports **one active color slot only** (`_auto_select_color`), with no public automatic multicurve DP runner shipped, and `Digitizer/AxisReader.py` runs Tesseract `--psm 6` on full + `-90°` rotated images (without `--psm 11` or `RapidOCR` wired in, while including `tol=10` band clustering, pair-consensus RANSAC `_line_inliers`, and `>= 2/3` supermajority `_robust_endpoints`).
  - Therefore Stage-0 locked a **pinned-code (`8fb89a62`) balanced SINGLE-line Full diagnostic** (`N = 30` non-bridge single-line Full `base_id`s: `10` matplotlib, `10` plotly, `10` altair; `0` Lite/bridge overlap; **`2,470` Full `base_id`s / `2,950` images remain untouched and un-downloaded**; [`STAGE0_SINGLE_DEV_30_RECEIPT.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE0_SINGLE_DEV_30_RECEIPT.json), SHA `91c324e9...`).
  - **Do NOT compare this single-line diagnostic directly with Paper Table 3's DigitizerBench-Full (`2,980` images) `0.672` FPC-NRMSE / `38.2%` TU (`arXiv:2609.19377v1`), and make no global leaderboard claims.**

---

## 2. Native Execution Receipt, Pixel-Path Identity & First-Run Erratum

- **Locked Pre-Launch Protocol:** [`STAGE0_LINEPILOT_PROTOCOL.md`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE0_LINEPILOT_PROTOCOL.md) (`SHA-256: b05506fb7c112e35d16075cf052041019a7ce55198f868d90ae2fd081e9ec518`, **preserved completely unmodified**).
- **First-Run Interruption & Exact Scoped Patch Erratum:**
  - The initial native run interrupted at `[03/30] A0250__single__matplotlib` with `AssertionError: Zero GT y-span` because two locked dev plots (`A0250__single__matplotlib` and `B0464__single__altair`) have `zero_span_confinement = True`, producing constant-`y` flat GT curves (`max(GT y) - min(GT y) == 0.0`).
  - **Scoped denominator-only patch (zero changes to upstream LinePilot, OCR, tracing, split, or advance gate):**
    - [`eval_digitizerbench_sec43.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/eval_digitizerbench_sec43.py): `d4c593529cb4d032930fc99aa109b2702dfcc1060564962240a97caf50c7968b` -> `b0f1aea660c1878a91debe5c2d74010c9c2848c9395e1c5e5501774fdef7cece` (added `y_axis_span` parameter using image-level y-axis span `y_val_max - y_val_min` from `dev_tick_ground_truth_30.parquet`, plus a 9th unit test verifying flat zero-span curves; `9/9` synthetic assertions passed).
    - [`run_linepilot_stage0_diagnostic.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/run_linepilot_stage0_diagnostic.py): `5b19cc0f76010c0cb0d88956a39df5e855959c3955dc26dd814ede021a8a1a1b` -> `13bc671f13d2e4195a267476bf3b41c7266e04a9c0b2a0b98c2755aeef08e4cd` (passed `y_axis_span` to `evaluate_image_sec43`).
  - **Denominator Sensitivity Audit:** On the `28` non-flat plots, DigitizerBench scales every curve to exactly `0.90 * y_axis_span`. Primary `y_axis_span` denominator yields `Arm A = 0.9376 -> Arm B = 0.1196` (`delta = +0.8180`). Using `gt_curve_y_span` on the `28` non-flat plots with `y_axis_span` fallback only on the `2` flat plots yields `Arm A = 0.9418 -> Arm B = 0.1310` (`delta = +0.8107`; `OS`, `TU`, and `+27/30` net newly trusted are identical under both conventions).
- **Completed Resumed Native Run:**
  - **PID:** `53928` | **Exit Code:** `0` | **CPU-Only Wall Time:** `26.58 s`
  - **Summary JSON:** [`linepilot_stage0_dev30_summary.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage0_outputs/linepilot_stage0_dev30_summary.json) (`SHA-256: 74aedcb5a9c98bdad37cf1ddb102b540f00111b0c29b77b4f526c72081f3eaf5`)
  - **Per-Image Ledger:** [`linepilot_stage0_dev30_per_image.jsonl`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage0_outputs/linepilot_stage0_dev30_per_image.jsonl) (`SHA-256: 321c926a5deea77c1ea43008ae8b2e1117f8f734aad6c541dec8c1c9defac716`)
- **Fixed-Tracker Pixel-Path Identity Verification (`limit_to_calibration = False`, ZERO GT colors or series during tracing):**
  - **Arm A (Default Upstream Automatic OCR, `used_ocr = True`):** `4/4` valid outputs checked -> `4/4` exact `(x_px, y_px)` & `color_rgb` match, **`max_abs_px_diff = 0.0 px`**.
  - **Arm B (Diagnostic Oracle-Axis supplying BOTH `tick_points` AND `axis_values`, `used_ocr = False`):** `30/30` outputs checked -> `30/30` exact `(x_px, y_px)` & `color_rgb` match, **`max_abs_px_diff = 0.0 px`**.
  - This guarantees that **100% of the observed difference between Arm A and Arm B comes strictly from axis calibration**.

---

## 3. Main Stage-0 Results (`N = 30`, Exact Paper §4.3 Metrics)

### 3.1 Overall Paired Summary

| Arm | FPC-NRMSE (↓) | Output Success `OS` (↑) | Trusted Usability `TU` (↑) | `DPPL` | Mean CPU s/img (median, range) |
|---|---:|---:|---:|---:|---:|
| **Arm A: Default Upstream OCR (`8fb89a62`)** | `0.9376` | `13.3%` (`4/30`) | `10.0%` (`3/30`) | `1444.8` | `0.520 s` (`0.387 s`, `0.172–1.530 s`) |
| **Arm B: Fixed-Tracker Oracle-Axis** | `0.1196` | `100.0%` (`30/30`) | `100.0%` (`30/30`) | `1012.1` | `0.220 s` (`0.171 s`, `0.018–1.017 s`) |
| **Paired Oracle-Axis Gain (`A - B` / `B - A`)** | **`+0.8180`** (95% CI `[+0.7072, +0.9126]`) | **`+86.7 pp`** (`+26/30`) | **`+90.0 pp`** (`+27/30`, CI `[+76.7, +100.0 pp]`) | — | `-0.300 s/img` (OCR skipped) |

- **Per-image directional consistency:** `30/30` plots improved in FPC-NRMSE by `> 0.01`; `0/30` worsened; `27` newly trusted; `0` lost trust.
- **Arm B Oracle FPC-NRMSE distribution:** median `0.0238`, range `[0.0000, 0.5015]`; `18/30` plots achieve `F < 0.05` (`20/30` `< 0.10`).
- **Pre-Locked Advance Gate Evaluation:**
  - Criterion: Mean FPC-NRMSE reduction `>= 0.080` **AND** net newly trusted plots `>= 3/30`.
  - Observed: **`+0.8180`** (`10.2x` threshold) **AND** **`+27/30`** (`9.0x` threshold).
  - **Outcome:** **`PASS -> PROPOSE_MULTISCALE_OCR_CANDIDATE_PENDING_REVIEW`**.

### 3.2 Breakdown by Renderer (`10` plots each)

| Renderer | `N` | Arm A FPC | Arm A `OS` / `TU` | Arm B FPC | Arm B `OS` / `TU` | FPC Reduction | Net Newly Trusted |
|---|---:|---:|---:|---:|---:|---:|---:|
| `matplotlib` | `10` | `0.9337` | `1/10` / `1/10` | **`0.0248`** | `10/10` / `10/10` | **`+0.9089`** | `+9` |
| `plotly` | `10` | `0.9494` | `1/10` / `1/10` | `0.1838` | `10/10` / `10/10` | `+0.7656` | `+9` |
| `altair` | `10` | `0.9296` | `2/10` / `1/10` | `0.1502` | `10/10` / `10/10` | `+0.7794` | `+9` |

### 3.3 Curve-Color & Tracking-Residual Decomposition

| Subgroup | `N` | Arm A FPC | Arm A `TU` | Arm B FPC | Arm B `TU` | FPC Reduction | Diagnostic Mechanism |
|---|---:|---:|---:|---:|---:|---:|---|
| Colored non-black `R2` | `25` | `0.9532` | `2/25` (`8.0%`) | `0.0792` | `25/25` (`100%`) | `+0.8740` | Clean tracking except `3` Plotly navy-text mispicks |
| Black curve `R2 = #000000` | `5` | `0.8592` | `1/5` (`20.0%`) | `0.3215` | `5/5` (`100%`) | `+0.5378` | `_auto_select_color` skips `#000000`, picks gray/navy pixels |
| Clean color-pick subset (`R2 != #000000` & no Plotly `#2A3F5F` mispick) | `22` | `0.9699` | `1/22` (`4.5%`) | **`0.0273`** | `22/22` (`100%`) | **`+0.9426`** | Near-exact curve recovery once axes are calibrated |

*(The 3 Plotly non-black color mispicks are `C0608`, `D0177`, and `A0196`, where upstream `_auto_select_color` selected Plotly's dark-navy default tick/title text RGB `(42, 63, 95)` / `(49, 69, 100)` instead of the curve. All 8 non-axis residuals are preserved unchanged under fixed-tracker testing.)*

---

## 4. Arm A Failure Taxonomy (What Actually Broke in Upstream `8fb89a62`?)

| Arm A Outcome | Total (`N=30`) | `matplotlib` | `plotly` | `altair` | Root Cause in Pinned Source (`AxisReader.py` / `Calibration.py`) |
|---|---:|---:|---:|---:|---|
| **`axis_calibration_snap_failed`** | **`14` (`46.7%`)** | `4` | `7` | `3` | `Calibration._snap_to_black(..., black_threshold=30)` fails whenever `R4_blur >= 0.5` softens thin 1px dark spines (all `4` matplotlib cases) or Plotly/Altair render gray (`#888888`) / borderless axes (`10` cases). |
| **`axis_ocr_missing_ticks`** | **`7` (`23.3%`)** | `4` | `0` | `3` | Full-image `1x` Tesseract `--psm 6` misses sparse axis ticks (especially small `72–150 DPI` fonts or `600 DPI` `4800x3609` plots where hardcoded `tol=10 px` fragments tick bands). |
| **`axis_ocr_degenerate_same_endpoint`** | **`5` (`16.7%`)** | `1` | `2` | `2` | Single-scale full-image OCR + rotated-label mixing yields duplicate endpoints (`3.0==3.0`, `0.0==0.0`, `2.0==2.0`, `1.0==1.0`) when `_robust_endpoints` falls back to raw extremes (`len < 4` or `< 2/3` supermajority). |
| **`ok` (produced output)** | **`4` (`13.3%`)** | `1` | `1` | `2` | **`3/4` still had misread X-axes:** `A0234` read `[7.0, -0.75]` vs `[-1, 1]` (`F: 0.3375 -> 0.1103`); `D0177` read `[9.0, 2.095]` vs `[0, 0.01]`; `C0568` dropped minus sign `[0.75, 1.0]` vs `[-1, 1]` (coverage `14.7% < 80%` -> **untrusted `F=1.0 -> 0.3085`**); only `B0396` read consistent interior ticks (`[40600, 80200]` on `[1000, 100000]`). |

**Diagnostic Buckets:** `18` `axis_bottleneck_rescued_cleanly` (`F_oracle < 0.05`), `10` `axis_bottleneck_partial_rescue`, `2` `non_axis_color_or_curve_error` (`D0177`, `B0396`).

---

## 5. Proposed Stage-1 Axis-Calibration-Only Candidate (PENDING COORDINATOR REVIEW — NOT IMPLEMENTED OR SCORED YET)

The Stage-0 failure taxonomy proves that solving the axis bottleneck on pinned `LinePilot 2.17.1` requires fixing **both** sub-stages of axis calibration — (1) multi-scale tick-label OCR + held-out linearity verification (`12` hard OCR failures + `3/4` silent X-axis misreads) and (2) contrast-adaptive tick-to-axis pixel anchoring (`14` `snap_failed` failures) — **strictly inside axis calibration**, passing only `(tick_points, axis_values)` to unmodified `digitizer_api.digitize_image(..., limit_to_calibration=False)` with `0.0 px` verified drift against frozen pixel paths.

### 5.1 Proposed Method: `MS-HOTC` (Multi-Scale Margin-Cropped OCR with Held-Out Tick Consistency & Contrast-Adaptive Anchoring)

1. **Plot-Frame & Dedicated Axis-Margin Localization (No GT, Zero Tracking Changes):**
   - Locate the plot ink/frame bounding box via non-white row/column projections and extract dedicated **bottom X-axis margin** and **left Y-axis margin** strips (preventing plot-interior curve interference and removing the `-90°` rotated-detection mixing bug in `AxisReader.py:81`).
   - Replace hardcoded `tol = 10 px` with scale-normalized band clustering (`tol = max(6, round(0.015 * min(H, W)))`).
2. **Multi-Resolution Margin OCR (`s in {1x, 2x, 3x}`, CPU-capped):**
   - Run the same vendored Tesseract `v5.5.3.20260724` with numeric whitelist (`0123456789.-+,eE`) on the bottom and left axis strips at scales `s in {1x, 2x, 3x}` (bicubic resize, capped so crop long edge `<= 2400 px`), using `--psm 6` (with `--psm 11` sparse fallback only if `< 3` tokens are found at a given scale). Project all bounding-box centers back to original floating-point pixel coordinates.
3. **Held-Out Leave-One-Tick-Out (LOTO) Cross-Fit Consistency:**
   - For each axis separately, pool candidate ticks `(pos_k, val_k, conf_k, scale_s)` from the dominant axis band (allowing multi-scale alternative readings at the same tick position as competing hypotheses, including explicit sign-flip hypotheses for tokens with dark ink strokes directly left of the digit box to catch dropped minus signs like `C0568`).
   - Evaluate candidate monotonic affine scales (linear, plus positive-domain log-linear) induced by tick pairs with valid orientation (`slope > 0` for X, `slope < 0` for Y) and strictly positive numeric span (`val_max > val_min`).
   - For every candidate support set with `m >= 3` spatially distinct ticks, compute the **leave-one-tick-out cross-fit residual**: for each tick `j`, refit `(a_{-j}, b_{-j})` on the remaining `m - 1` ticks and compute normalized error `r_j = |val_j - (a_{-j} * pos_j + b_{-j})| / span`.
   - Accept only models passing `m >= 3` distinct ticks and `max_j r_j <= 0.02` (vs upstream's loose `0.15` and raw-extreme fallback), selecting by `(inlier_count, -median_LOTO_residual, pixel_span_coverage, mean_OCR_conf)`.
4. **Contrast-Adaptive Spine / Baseline Anchoring (Axis Calibration Only):**
   - Anchor the two chosen consistent extreme ticks onto the plot axis using a contrast-adaptive spine scan (detecting Matplotlib dark/blurred spines and Plotly/Altair gray spines via local row/column luminance minima rather than hard `RGB <= 30`), with a clean geometric fallback to the tick-band median orthogonal baseline on borderless plots (preserving exact along-axis coordinates, since `Calibration.py`'s affine mapper cancels constant perpendicular offsets).
5. **Fixed Deterministic Fallback:**
   - If either axis lacks a valid `m >= 3` LOTO-consistent solution (or fails non-degenerate / monotonicity sanity checks), fall back deterministically to the unmodified upstream `8fb89a62` calibration output (with any failure remaining penalized at `F_i = 1.0`).

### 5.2 Matched CPU Budget Control, Zero Case-Specific Tuning & Disjoint Evaluation Plan

- **Three Paired Arms on Identical Frozen Pixel Paths (`max_abs_px_diff == 0.0 px` asserted on every output):**
  1. **Arm 0 — Default Upstream `8fb89a62`:** Unmodified full-image `1x` + `-90°` rotated Tesseract `--psm 6`.
  2. **Arm 1 — Matched-Budget Single-Scale Margin + Adaptive-Anchor Control:** Identical axis-margin cropping, contrast-adaptive spine anchoring, and matched CPU OCR call budget (repeating `1x` margin passes across `--psm 6`/`--psm 11` with upstream `_robust_endpoints`, **without** multi-resolution `2x/3x` scaling or LOTO held-out consistency). This isolates the causal value of multi-scale OCR + held-out tick consistency from mere margin cropping, gray-spine threshold repair, or extra CPU time.
  3. **Arm 2 — Proposed `MS-HOTC`:** Multi-scale `{1x, 2x, 3x}` margin OCR + LOTO held-out consistency + identical contrast-adaptive anchoring + deterministic upstream fallback.
- **Zero Case-Specific Tuning & Strict `base_id` Disjointness:**
  - All thresholds (`scales={1,2,3}`, `LOTO_tol=0.02`, crop fractions, contrast percentiles) locked prospectively before touching any held-out data — zero per-image or per-renderer lookup tables, zero oracle inputs in any prediction.
  - First run an engineering verification on the already-seen `N = 30` Stage-0 dev split (explicitly labeled **Dev Diagnostic**).
  - Only if coordinator approves and dev checks pass, lock a fresh deterministic **held-out single-line Full split (`N = 90`: `30` matplotlib / `30` plotly / `30` altair)** drawn exclusively from the **`784` untouched non-bridge single-line Full `base_id`s** (`0` overlap with the `60` Lite/bridge `base_id`s and `0` overlap with the `30` Stage-0 dev `base_id`s).
  - **Pre-Specified Stage-1 Advance / Confirmation Criteria (proposed for lock before touching held-out data):** On fresh `N = 90` held-out single-line Full plots, `MS-HOTC` must beat BOTH Default Upstream (`>= 0.25` lower FPC-NRMSE, 95% CI `> 0`, `>= +15` net newly trusted) AND Matched-Budget Single-Scale Control (`>= 0.05` lower FPC-NRMSE, 95% CI `> 0`, `>= +5` net newly trusted), with `0.0 px` pixel drift on 100% of outputs and mean CPU runtime within `<= 1.2x` of the matched-budget control (`<= 2.5 s/img`).

---

## 6. Sealed Stage-0 SHA-256 Artifact Manifest

| Artifact | SHA-256 | Notes |
|---|---|---|
| [`STAGE0_LINEPILOT_PROTOCOL.md`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE0_LINEPILOT_PROTOCOL.md) | `b05506fb7c112e35d16075cf052041019a7ce55198f868d90ae2fd081e9ec518` | Pre-launch locked protocol (**UNMODIFIED**) |
| [`PORTABLE_OCR_RECEIPT.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/PORTABLE_OCR_RECEIPT.json) | `a8f3d81f7b5a67e7542eb48400618e853cf792492a09cad5b2226597f72200a6` | Vendored Tesseract `v5.5.3.20260724` receipt |
| [`STAGE0_SINGLE_DEV_30_RECEIPT.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE0_SINGLE_DEV_30_RECEIPT.json) | `91c324e95724d649a56197d697647027743ffec68dfefb93921bf9c5cae49b47` | Locked `N=30` single-line split (`2,470` untouched) |
| [`STAGE0_PRELAUNCH_FIXTURES_RECEIPT.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE0_PRELAUNCH_FIXTURES_RECEIPT.json) | `84d291555b1bc5d7cd93ff7333819fe3c9e601083f747f075f4d8cbb89fc1aed` | Pre-launch tests (`75` pytest, `3/3` smoke, §4.3 tests) |
| [`eval_digitizerbench_sec43.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/eval_digitizerbench_sec43.py) | `b0f1aea660c1878a91debe5c2d74010c9c2848c9395e1c5e5501774fdef7cece` | Post-erratum (`d4c59352...` -> `b0f1aea6...`, `9/9` tests) |
| [`run_linepilot_stage0_diagnostic.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/run_linepilot_stage0_diagnostic.py) | `13bc671f13d2e4195a267476bf3b41c7266e04a9c0b2a0b98c2755aeef08e4cd` | Post-erratum (`5b19cc0f...` -> `13bc671f...`) |
| [`linepilot_stage0_dev30_summary.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage0_outputs/linepilot_stage0_dev30_summary.json) | `74aedcb5a9c98bdad37cf1ddb102b540f00111b0c29b77b4f526c72081f3eaf5` | Completed native `PID = 53928` summary |
| [`linepilot_stage0_dev30_per_image.jsonl`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage0_outputs/linepilot_stage0_dev30_per_image.jsonl) | `321c926a5deea77c1ea43008ae8b2e1117f8f734aad6c541dec8c1c9defac716` | All `30` paired image records |
