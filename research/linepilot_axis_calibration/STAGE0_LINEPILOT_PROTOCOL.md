# Stage-0 Locked Protocol — Pinned-Code LinePilot Axis-Calibration Bottleneck Diagnostic (`DigitizerBench-Full`, Single-Line Balanced Dev Split)

**Date Locked:** 2026-11-24 (BEFORE running ANY evaluation on the 30 locked development images)  
**Scope:** Stage-0 diagnostic ONLY — CPU-only, zero GPU, zero new OCR variant implemented or scored yet, zero untouched Full `base_id`s opened or downloaded, zero PDF/media/release.

---

## 1. Upstream Sources, License Audit & Portable Workspace-Only OCR Route

- **Benchmark:** Official [`LinePilot/DigitizerBench`](https://huggingface.co/datasets/LinePilot/DigitizerBench), pinned commit `8b4a3190d5991414dad92049671de75754dd9f44`, **Apache-2.0** (`2,980` images across `2,500` unique `base_id`s: `2,440` non-bridge core `base_id`s + `60` nine-rerender bridge/Lite `base_id`s). `lite.zip` (`17,094,028 B`, LFS SHA-256 `2127fde8...`) used ONLY for 4-image smoke checks.
- **Baseline Code:** Official [`RayanA07/LinePilot`](https://github.com/RayanA07/LinePilot), pinned commit `8fb89a62fb0565290b72ba61cb073d732d8e7578` (`LinePilot 2.17.1`), **Apache-2.0**. Isolated Python `3.12.16` `.venv` installed against upstream `constraints.txt` (`pyqt6==6.12.1`, `numpy==2.5.5`, `pillow==13.0.0`, `pytesseract==0.3.13`, `scipy==1.18.1`, `pandas==3.1.1`, `pyarrow==26.0.1`, `matplotlib==3.11.2`).
- **Workspace-Only Portable OCR Engine (`PORTABLE_OCR_RECEIPT.json`, `a8f3d81f...`):** Safely extracted ONLY `vendor/tesseract/*` (`tesseract v5.5.3.20260724`, `33` DLLs, `71` files) purely via Python `PyInstaller.archive.readers.CArchiveReader` from the official `RayanA07/LinePilot v2.17.1` release artifact (`Digitizer.exe`, `95,187,314 B`, SHA-256 `5b15b73b...`) directly into `upstream_linepilot/Digitizer/vendor/tesseract/` — **zero global installer, zero machine PATH modification, zero registry edits, zero UAC**. Verified `tesseract --version` == `5.5.3`, required features (`libarchive`, `libcurl`), and exact SHA-256 checksums of `eng.traineddata` (`7d4322bd...`) and `osd.traineddata` (`9cf5d576...`) against `Digitizer/tesseract-lock.json`. Passed `75/75` upstream `Digitizer` unit tests (`1.67 s`) and `3/3` official `tools/smoke_test.py` figures (`0.667%–1.405%` NRMSE).
- **Verified Upstream Single-Slot CLI Scope Disclosure (NO comparison to Table 3's Full `0.672`):**
  - Source audit of `RayanA07/LinePilot` (`8fb89a62`) and all public `RayanA07` repos/branches confirms: (a) `Digitizer/digitizer_api.py` automatically detects and exports **only one active color slot** (`window._auto_select_color`), and no public automatic multicurve DP runner is shipped; (b) `Digitizer/AxisReader.py` runs Tesseract `--psm 6` on full + `-90°` rotated image (without `--psm 11` or `RapidOCR` wired in, while containing band clustering, pair-consensus RANSAC `_line_inliers`, and `>= 2/3` supermajority endpoint rejection `_robust_endpoints`).
  - Therefore, per protocol, Stage-0 locks a **pinned-code (`8fb89a62`) balanced SINGLE-line Full diagnostic** (`N = 30`) rather than feeding multiline plots through a single-slot API and misattributing structural line-count failures to axis calibration. Author-reported Full `0.672` FPC-NRMSE / `38.2%` TU (`arXiv:2609.19377v1` Table 3) are context only and are NOT directly compared against this single-line diagnostic subset.

---

## 2. Locked Disjoint `base_id` Development Split (`N = 30`)

Constructed strictly from `full/manifest.parquet` (`SHA-256: 49265a4f...`) BEFORE any benchmark outcomes ([`STAGE0_SINGLE_DEV_30_RECEIPT.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE0_SINGLE_DEV_30_RECEIPT.json), `91c324e9...`):
- Excluded **ALL `60` Lite/bridge `base_id`s** (`540` images) and restricted to non-bridge `single`-line (`line_count == 1`) core `base_id`s (`814` unique `base_id`s, `1` image per `base_id`, keeping all rerenders together).
- Within each renderer (`matplotlib`, `plotly`, `altair`), sorted `base_id`s ascending by `sha256("linepilot_stage0_single_dev_20261124:" + base_id)` and locked the first **`10`** per renderer -> **`30` balanced single-line Full diagnostic plots (`10` matplotlib, `10` plotly, `10` altair)**.
- Fetched ONLY those `30` PNGs and ONLY their `30/2,980` Parquet row groups (`9.09 MB` total via HTTP Range from `750 MB` `full.zip`). All remaining **`2,470` Full `base_id`s (`2,950` images)** remain completely untouched and un-downloaded.

---

## 3. Exact Paper §4.3 Evaluation & Fixed-Tracker Paired Arms

- **Exact Paper §4.3 Metric ([`eval_digitizerbench_sec43.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/eval_digitizerbench_sec43.py), `d4c59352...`, `8/8` synthetic assertions passed):**
  - Distinct from generic `AccuracyTester` (which skips failures, scores one slot on `original_x`, and has no Hungarian matching or trust gate).
  - Implements exact Eq. (1): interpolation without extrapolation at 1 sample per horizontal plot pixel in the shared x-range (endpoint-tick width $W_i = |x_{\text{px,max}} - x_{\text{px,min}}|$), NRMSE normalized by image GT span $y_{i,\max} - y_{i,\min}$, Hungarian assignment minimizing $\min(e_{i\ell}, 1) + (1 - C_{i\ell})$, trust gate $T_i = 1$ iff exact line count + finite error + $\ge 20$ valid pairs + $C_{i\ell} \ge 0.800$, $F_i = \bar{e}_i$ if ($T_i = 1$ and $\bar{e}_i < 1$) else `1.0`, averaged over **ALL 30 images**, alongside `OS (%)`, `TU (%)`, and `DPPL`.
- **Frozen Extraction & Paired Arms (`limit_to_calibration = False`, ZERO GT colors, ZERO GT series during tracing):**
  - **Frozen Pixel Path:** Run upstream `DigitizerWindow` `_auto_select_color` + `_compute_points` once per image with `limit_to_calibration = False`, freezing `(x_px, y_px)` and `color_rgb`; log any extraction/color-pick failure separately.
  - **Arm A (Actual Default Upstream Automatic OCR):** Unmodified `digitizer_api.digitize_image(pic_dir=img_path, limit_to_calibration=False)` (`used_ocr == True`, vendored Tesseract `v5.5.3.20260724`); assert exact `(x_px, y_px)` and `color_rgb` identity with the frozen path whenever output is produced.
  - **Arm B (Diagnostic Fixed-Tracker Oracle-Axis):** Unmodified `digitizer_api.digitize_image(pic_dir=img_path, tick_points=oracle_ticks, axis_values=oracle_axis, limit_to_calibration=False)` supplying **BOTH** official extreme tick pixel coordinates and numeric values from `dev_tick_ground_truth_30.parquet` (`used_ocr == False`, skipping OCR per `digitizer_api.py:119–167`); assert exact `(x_px, y_px)` and `color_rgb` identity with the frozen path on every image. Do NOT use oracle for any proposed prediction.

---

## 4. Pre-Locked Stage-0 Advance Gate

Work on a proposed multi-scale OCR / held-out tick-consistency candidate (specified for coordinator review, NOT implemented or scored in Stage-0) **ONLY IF** the fixed-tracker oracle-axis diagnostic achieves BOTH:
1. **Mean FPC-NRMSE reduction `>= 0.080`** (`FPC_default_OCR - FPC_oracle_axis >= 0.080`) across ALL `30` locked development images, **AND**
2. **At least `3` net newly trusted usable plots** (`TU_oracle_count - TU_ocr_count >= 3` out of `30`, i.e., `>= +10.0 pp`).

---

## 5. Locked Pre-Launch SHA-256 Manifest

| File | SHA-256 |
|---|---|
| `PORTABLE_OCR_RECEIPT.json` | `a8f3d81f7b5a67e7542eb48400618e853cf792492a09cad5b2226597f72200a6` |
| `STAGE0_SINGLE_DEV_30_RECEIPT.json` | `91c324e95724d649a56197d697647027743ffec68dfefb93921bf9c5cae49b47` |
| `STAGE0_PRELAUNCH_FIXTURES_RECEIPT.json` | `84d291555b1bc5d7cd93ff7333819fe3c9e601083f747f075f4d8cbb89fc1aed` |
| `eval_digitizerbench_sec43.py` | `d4c593529cb4d032930fc99aa109b2702dfcc1060564962240a97caf50c7968b` |
| `stage0_lock_single_dev30_and_fetch.py` | `4e405a3a1c96ec9daee4f2018623c7de4d9b6a856d6a97bbc691d960a574a3be` |
| `run_linepilot_stage0_diagnostic.py` | `5b19cc0f76010c0cb0d88956a39df5e855959c3955dc26dd814ede021a8a1a1b` |
