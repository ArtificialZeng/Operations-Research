# Stage-1 Locked Dev Engineering Protocol — Matched-Budget Multi-Resolution vs. Single-Resolution Axis Calibration (`N = 30` Single-Line Dev Split)

**Date Locked:** 2026-11-24 (BEFORE running any Stage-1 evaluation on the 30 dev images)  
**Scope:** Strictly ONE small CPU-only **dev engineering pilot** on the already-downloaded `N = 30` balanced single-line non-bridge dev split (`STAGE0_SINGLE_DEV_30_RECEIPT.json`, SHA `91c324e9...`). **ZERO held-out images/labels opened or downloaded** (`2,470` untouched Full `base_id`s / `2,950` images remain untouched). Zero PDF, media, PR, or global leaderboard/novelty claims.

---

## 1. Stage-0 Seal, Exact Patch/Transport Scope & Nearby Prior Art

- **Sealed Stage-0 Receipt:** `PID = 53928`, `linepilot_stage0_dev30_summary.json` (`SHA-256: 74aedcb5a9c98bdad37cf1ddb102b540f00111b0c29b77b4f526c72081f3eaf5`), `STAGE0_LINEPILOT_RESULT.md` (`741cabe0...`), `STATUS.md` (`30ac9fa6...`).
  - Default upstream automatic OCR (`RayanA07/LinePilot 8fb89a62`, vendored Tesseract `v5.5.3.20260724`): `FPC-NRMSE = 0.937580`, `TU = 3/30` (`4/4` valid outputs verified `0.0 px` pixel-identical).
  - Fixed-tracker Oracle-Axis (`tick_points` + `axis_values`, `limit_to_calibration = False`): `FPC-NRMSE = 0.119598`, `TU = 30/30` (`30/30` verified `0.0 px` pixel-identical).
  - Errors in released default: `14` `axis_calibration_snap_failed`, `7` `axis_ocr_missing_ticks`, `5` `axis_ocr_degenerate_same_endpoint`, plus `3/4` `ok` outputs with X-axis misreads.
- **Exact Stage-0 Transport & Runner Revision Disclosure:**
  - `STAGE0_LINEPILOT_PROTOCOL.md` (`b05506fb7c112e35d16075cf052041019a7ce55198f868d90ae2fd081e9ec518`) was **preserved unmodified**.
  - **Transport revision:** `fetch_digitizerbench_lite_and_full_manifest.py` (`f4d87caa...`) and `stage0_lock_single_dev30_and_fetch.py` (`4e405a3a...`) replaced slow per-range `urllib` requests with a persistent `KeepAliveRangeClient` HTTP Range fetcher + Parquet row-group pruning (`9.09 MB` fetched, `30/2,980` row groups read).
  - **First-run interruption & exact scoped runner/scorer patch:** First Stage-0 run failed at `[03/30] A0250__single__matplotlib` with `AssertionError: Zero GT y-span` because two locked dev plots (`A0250`, `B0464`) have `zero_span_confinement = True` (`max(GT y) - min(GT y) == 0.0`). Patched ONLY the NRMSE denominator to pass image-level `y_axis_span = y_val_max - y_val_min`:
    - `eval_digitizerbench_sec43.py`: `d4c593529cb4d032930fc99aa109b2702dfcc1060564962240a97caf50c7968b` -> `b0f1aea660c1878a91debe5c2d74010c9c2848c9395e1c5e5501774fdef7cece` (added optional `y_axis_span` argument + 9th synthetic zero-span unit fixture; `9/9` passed).
    - `run_linepilot_stage0_diagnostic.py`: `5b19cc0f76010c0cb0d88956a39df5e855959c3955dc26dd814ede021a8a1a1b` -> `13bc671f13d2e4195a267476bf3b41c7266e04a9c0b2a0b98c2755aeef08e4cd` (passed `y_axis_span` to `evaluate_image_sec43`).
    - Zero changes to upstream `LinePilot`, OCR, curve tracing, dev split, or advance gate. Both `y_axis_span` (`0.9376 -> 0.1196`) and curve-span-with-zero-span-fallback (`0.9418 -> 0.1310`) are documented.
- **Scope & Prior Art Context:** Small paired method development in a **single-line pinned-code (`8fb89a62`) diagnostic** — NOT directly comparable to published Full `0.672` (`arXiv:2609.19377v1` Table 3), and NOT an upstream reproduction project. Nearby prior art includes **Graph-FINDER** (`https://www.nature.com/articles/s41524-026-02247-y`), **ChartRecover**, and **LinePilot's own existing robust endpoint checking** (`Digitizer/AxisReader.py` `_line_inliers` / `_robust_endpoints`) and §3.1 paper description (axis neighborhood cropping + Tesseract PSM 6/11 + scale-consistency filtering).

---

## 2. Three Paired Arms & Strict Equal-Budget Design

All three arms operate on the **exact same cached frozen pixel traces** `(x_px, y_px)` and `color_rgb` from unmodified `DigitizerWindow` (`_auto_select_color` + `_compute_points`, `limit_to_calibration = False`, zero GT colors or trace truth). Every produced output CSV across Arms A, B, and C MUST pass `max_abs_px_diff == 0.0 px` and exact `color_rgb` identity against the cached frozen trace. **No oracle ticks/values, GT colors, trace truth, or per-image thresholds may be used to generate or choose axes; GT is solely the evaluator.**

| Arm | Description | OCR Call Budget / Image | View Allocation (Per Axis ROI) | Alignment, Fit, Acceptance & Fallback |
|---|---|---:|---|---|
| **Arm A** | Released automatic default (`RayanA07/LinePilot 8fb89a62`), unchanged | `2` (full image + `-90°`) | Full `1.0x` + `-90°` rotated, `--psm 6` | Upstream `AxisReader.py` + `Calibration.py` (`_snap_to_black` at `RGB<=30`) |
| **Arm B** | Stronger fixed paper-inspired **single-resolution (`1.0x`) control** | **`8`** (`4` X-ROI + `4` Y-ROI; `4× PSM6 + 4× PSM11`) | **View B1 (`1.0x`, `enhanced`):** `PSM 6`, `PSM 11`<br>**View B2 (`1.0x`, `clean_gray`):** `PSM 6`, `PSM 11` | **Shared engine:** ROI crop + right-edge Y / baseline X clustering + tick-geometry alignment (no mandatory snap-to-black) + held-out LOTO residual agreement + OLS integer-anchor projection + deterministic fallback to Arm A |
| **Arm C** | Matched **two-resolution (`1.0x` + `2.0x`) candidate** | **`8`** (`4` X-ROI + `4` Y-ROI; `4× PSM6 + 4× PSM11`) | **View C1 (`1.0x`, `enhanced`):** `PSM 6`, `PSM 11`<br>**View C2 (`2.0x` bicubic, `enhanced`):** `PSM 6`, `PSM 11` | **IDENTICAL shared engine** (exact same ROI, parser, sign check, clustering, alignment, LOTO fit, acceptance gate, and deterministic fallback to Arm A); **ONLY view allocation differs** (`1.0x clean_gray` vs `2.0x enhanced` projected to exact original float pixels) |

---

## 3. Pre-Locked Parameters of the Shared Calibration Engine (`B` & `C`)

All constants below are locked BEFORE running on the 30 dev plots and remain identical across all 30 images and all 3 renderers:

1. **Axis-Neighborhood ROI Localization (Image-Only):**
   - Grayscale luminance `G`; outer ink box `G < 245`.
   - Structural lines: Tier-1 dark spines (`G < 200`, continuous run `>= 0.35 * span`), Tier-2 light spines/gridlines/tinted plot boxes (`G < 246`, row/col non-white coverage `>= 0.45 * span`).
   - `plot_bottom`: lowest Tier-1 (else Tier-2) horizontal line in `[0.48*H, 0.97*H]`, fallback `int(0.82*H)`.
   - `plot_top`: highest Tier-1 (else Tier-2) horizontal line in `[0.01*H, 0.45*H]`, fallback `int(0.06*H)`.
   - `plot_left`: leftmost Tier-1 (else Tier-2) vertical line in `[0.03*W, 0.48*W]`, fallback `int(0.14*W)`.
   - `plot_right`: rightmost Tier-1 (else Tier-2) vertical line in `[0.55*W, 0.99*W]`, fallback `int(0.96*W)`.
   - `X_roi`: `x in [max(0, plot_left - max(12, round(0.06*W))), W]`, `y in [min(H-1, plot_bottom+1), H]` (if height `< 12`, start at `max(0, plot_bottom-2)`).
   - `Y_roi`: `x in [0, max(1, plot_left-1)]` (if width `< 12`, end at `min(W, plot_left+2)`), `y in [max(0, plot_top - max(12, round(0.06*H))), min(H, plot_bottom + max(12, round(0.06*H)))]`.
   - Constant `16 px` pure white border padding added to every ROI crop before OCR (subtracted before mapping back to original floating-point coordinates).
2. **Preprocessing Views:**
   - `enhanced` (matches LinePilot `AxisReader._preprocess_for_ocr`): grayscale -> autocontrast -> Contrast(1.6) -> UnsharpMask(radius=1.2, percent=180, threshold=3).
   - `clean_gray` (Arm B's second `1.0x` view): grayscale -> autocontrast (no unsharp ringing).
   - Scale projection for View C2 (`scale = 2.0`): `Image.Resampling.BICUBIC` on the padded ROI, mapping every detected bbox `(l, t, w, h)` back to original image pixels `((l - pad)/2.0 + roi_x0, (t - pad)/2.0 + roi_y0, w/2.0, h/2.0)`.
3. **Token Parsing, Adjacent Sign Merge & Image-Grounded Dropped-Minus Check:**
   - Whitelist `-c tessedit_char_whitelist=0123456789.-+,eE`; Unicode minus/en-dash normalized; commas stripped; scientific notation accepted.
   - Merge adjacent standalone sign tokens (`-`, `+`) immediately left of numeric tokens on the same line (`|cy_s - cy_n| <= 0.6*h_n`, `0 <= left_n - right_s <= 1.2*h_n`).
   - Reject along-axis box artifacts (`w > 0.60*roi_w` on X-ROI, `h > 0.45*roi_h` on Y-ROI, or full-ROI box `> 98%` in both dimensions).
   - Image-grounded dropped-minus hypothesis: for any positive token where the original grayscale strip immediately left of the box (`[left - 0.85*h, left - 1] × [cy - 0.25*h, cy + 0.25*h]`) contains a dark horizontal stroke (`min_val < 180` and `local_bg - min_val >= 35`), also register `-val` (with `0.85 * conf`) as a competing slot hypothesis for LOTO adjudication.
4. **Band Clustering & Physical Tick-Slot Grouping:**
   - X-axis bands clustered by `y_center` (`band_tol = max(6.0, 0.55*med_h, 0.015*min(W, H))`).
   - Y-axis bands clustered by **right edge `x_right = left + width`** (`band_tol = max(8.0, 0.85*med_h, 0.020*min(W, H))`), fixing upstream's center-x fragmentation on right-aligned variable-width labels.
   - Multi-call detections within a band grouped into physical tick slots along the axis (`slot_tol = max(6.0, 0.65*med_h)`), preserving distinct numeric hypotheses `(median_pos, val, votes, mean_conf)` per slot and enforcing strictly distinct numeric values across inlier slots.
5. **Original-Image Tick-Geometry Alignment & Held-Out LOTO Acceptance:**
   - Expected orientation: `slope > 0` for X (`x_val` increases rightward), `slope < 0` for Y (`y_val` increases upward).
   - Pair-consensus RANSAC over slot hypotheses (`|p_j - p_i| >= max(10.0, 0.05*expected_plot_span)`), collecting at most 1 best hypothesis per slot within `<= 0.03 * span_est`.
   - Refit OLS $(\hat{a}, \hat{b})$ on the `m` inlier slots and evaluate exact **leave-one-tick-out (LOTO)** normalized prediction residuals $r_k^{\text{LOTO}} = |v_k - (\hat{a}_{-k} p_k + \hat{b}_{-k})| / V_{\text{span}}$ for each $k \in \{1..m\}$.
   - **Primary Acceptance (`"loto_m>=3_accepted"`):** `m >= 3`, `max_loto_resid <= 0.035`, `med_loto_resid <= 0.015`, `inlier_pixel_span >= 0.25 * expected_plot_span`.
   - **Secondary Acceptance (`"two_tick_multiview_verified"`):** ONLY if no `m >= 3` model passes: `m == 2`, `inlier_pixel_span >= 0.50 * expected_plot_span`, both slots have `votes >= 2` view agreement, and `min_conf >= 70.0`.
   - **No Mandatory Snap-to-Black:** Emit strictly horizontal X-anchor pair `((p_lo_int, y_anchor), (p_hi_int, y_anchor))` (`y_anchor = plot_bottom`) and strictly vertical Y-anchor pair `((x_anchor, p_lo_int), (x_anchor, p_hi_int))` (`x_anchor = plot_left`), evaluating OLS $\hat{v}(p)$ at the exact rounded integer pixels `(p_lo_int, p_hi_int)` to eliminate `digitizer_api._normalize_ticks` quantization bias.
   - **Fallback (`"fallback_to_arm_a"`):** If either axis fails acceptance, deterministically execute unmodified Arm A.

---

## 4. Scorer, Forward Diagnostics & Pre-Locked Dev Advancement Gate

- **Scorer:** Exact same [`eval_digitizerbench_sec43.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/eval_digitizerbench_sec43.py) (`b0f1aea6...`, Eq. 1), reporting primary `y_axis_span` denominator plus curve-span-with-zero-span-fallback sensitivity.
- **Required Forward JSON/Diagnostics (per image & summary):** failure categories, `x_accept_reason` & `y_accept_reason`, fallback flag, OCR call count, timing breakdown (ROI / OCR / fit / digitize / total), inlier counts & `(pos_px, val)` coordinates, `med_loto_resid` & `max_loto_resid`, source renderer breakdown (`matplotlib`, `plotly`, `altair`), curve-color breakdown, and `max_abs_px_diff == 0.0` verification for Arms A, B, and C.
- **Pre-Locked Dev Advancement Criterion (Before Considering Any Untouched Held-Out Groups):**
  - Material dev improvement for **Arm C over best non-oracle Arm B**:
    1. Mean FPC-NRMSE reduction **`FPC_B - FPC_C >= 0.050`** with strong paired evidence (paired bootstrap 95% CI & directional win count), **AND**
    2. Net newly trusted usable plots **`TU_C - TU_B >= +2`** (out of `30`), **AND**
    3. No serious renderer regression or unacceptable runtime tradeoff.
  - **Honest Null/Control-Dominated Stop Rule:** If Arm B (single-resolution ROI + PSM 6/11 + tick-geometry alignment + LOTO) already captures the gain and Arm C fails the above criteria, **STOP and report `SAME_VIEW_GEOMETRY_CAPTURED_GAIN` / `NO_MATERIAL_MULTISCALE_GAIN_OVER_CONTROL`** without retuning or opening held-out data.

---

## 5. Locked Pre-Launch SHA-256 Manifest (Recorded Before Execution)

| File | SHA-256 |
|---|---|
| `STAGE0_LINEPILOT_PROTOCOL.md` | `b05506fb7c112e35d16075cf052041019a7ce55198f868d90ae2fd081e9ec518` |
| `PORTABLE_OCR_RECEIPT.json` | `a8f3d81f7b5a67e7542eb48400618e853cf792492a09cad5b2226597f72200a6` |
| `STAGE0_SINGLE_DEV_30_RECEIPT.json` | `91c324e95724d649a56197d697647027743ffec68dfefb93921bf9c5cae49b47` |
| `eval_digitizerbench_sec43.py` | `b0f1aea660c1878a91debe5c2d74010c9c2848c9395e1c5e5501774fdef7cece` |
| `stage1_axis_calibration.py` | `3f6d8c957cece1b9a4c2f3b0e1087bc09fc576b2d2230ec44de8749c5ea9dadd` |
| `test_stage1_axis_calibration.py` | `1e83c9809793656241a4062d13f95f2e48dd8a61555c966e8e520676bbc08bf6` |
| `run_stage1_dev_pilot.py` | `5191a1606be0b25fc3bfc620da94570031395df99fcf028c90dbad3c7c180f39` |

*(All 7 synthetic unit fixtures in `test_stage1_axis_calibration.py` passed prior to launch; zero dev or held-out plots were evaluated during fixture testing.)*
