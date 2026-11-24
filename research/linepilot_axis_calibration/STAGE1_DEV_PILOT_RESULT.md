# Stage-1 Dev Engineering Pilot Result — Matched-Budget Multi-Resolution (`1x + 2x`) vs. Single-Resolution (`1x`) Axis Calibration (`N = 30` Dev Split)

**Date Sealed:** 2026-11-24  
**Pre-Locked Gate Decision:** **`NO_MATERIAL_MULTISCALE_GAIN_OVER_CONTROL`** *(3 of 4 pre-locked sub-gates passed — FPC `+0.0965 >= 0.050`, net TU `+2 >= 2`, zero renderer regression — but the paired bootstrap 95% CI `[-0.0006, +0.2235]` straddled zero due to only `3/30` discrete rescue events, while single-resolution Arm B already captured `78.3%` of Arm C's total FPC gain over released Arm A.)*  
**Scope & Guardrails:** Strictly `N = 30` already-downloaded single-line non-bridge dev plots (`STAGE0_SINGLE_DEV_30_RECEIPT.json`, `91c324e9...`). **ZERO held-out images/labels opened or downloaded** (`2,470` untouched Full `base_id`s / `2,950` images remain untouched). Pinned-code (`RayanA07/LinePilot 8fb89a62`) single-line diagnostic only — NOT directly comparable to published Full `0.672` (`arXiv:2609.19377v1` Table 3). Zero novelty claims, zero PDF/media/PR/release.

---

## 1. Execution Receipt, Pixel-Path Identity & Exact Audit Trail

- **Locked Protocol:** [`STAGE1_DEV_PROTOCOL.md`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE1_DEV_PROTOCOL.md) (`SHA-256: 27922a5722704aefd77344e69dc243eeba8fbb987bf74a53ab9f0cf38ce5e916`, **preserved unmodified**).
- **Locked Calibration Engine:** [`stage1_axis_calibration.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage1_axis_calibration.py) (`SHA-256: 3f6d8c957cece1b9a4c2f3b0e1087bc09fc576b2d2230ec44de8749c5ea9dadd`, **preserved unmodified**; `7/7` synthetic unit fixtures passed in [`test_stage1_axis_calibration.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/test_stage1_axis_calibration.py), `1e83c980...`).
- **Stage-1 First-Run Interruption & Exact Symbol-Only Fix Disclosure (Zero Change to Preregistered Method):**
  - The initial Stage-1 run (`run_stage1_dev_pilot.py` SHA `5191a1606be0b25fc3bfc620da94570031395df99fcf028c90dbad3c7c180f39`) completed all `30/30` images and wrote all 30 forward per-image records cleanly, then raised `AttributeError: module 'eval_digitizerbench_sec43' has no attribute 'aggregate_sec43'` during post-loop summary aggregation.
  - Applied ONLY a single summary-aggregation symbol rename in [`run_stage1_dev_pilot.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/run_stage1_dev_pilot.py) (`ev.aggregate_sec43` -> `ev.summarize_sec43`; runner SHA `5191a1606be0b25fc3bfc620da94570031395df99fcf028c90dbad3c7c180f39` -> `dbb2c060f155f9d6ac3fffbb4372ff0eae93d091af8a55fa384fda846c00b917`). Neither the preregistered calibration engine (`stage1_axis_calibration.py`, `3f6d8c95...`), nor the exact Eq. (1) scorer (`eval_digitizerbench_sec43.py`, `b0f1aea6...`), nor the locked protocol (`STAGE1_DEV_PROTOCOL.md`, `27922a57...`) changed in any way. The clean re-run (`PID = 62340`, exit code `0`, wall `82.35 s`) produced the sealed summary and per-image ledger below.
- **Completed Native Run (`PID = 62340`, Exit Code `0`, CPU-Only Wall Time `82.35 s`):**
  - Summary JSON: [`stage1_dev30_summary.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage1_dev_outputs/stage1_dev30_summary.json) (`SHA-256: d07078e39b5b99588aa525dda7a1b9c428d1a651c12f9281e42264ce8d003dbb`)
  - Per-Image JSONL: [`stage1_dev30_per_image.jsonl`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage1_dev_outputs/stage1_dev30_per_image.jsonl) (`SHA-256: 527d1945e1a923f69eba6c4e3a5ef24e4029d9349ee07289740ce3b1ea9302a1`)
- **Strict Controls, Call-Budget & Pixel-Count / Timing Clarifications:**
  - **Attempted OCR Call Budget Before Fallback:** Both Arm B and Arm C execute exactly **`8` attempted Tesseract calls per image before fallback** (`4` X-ROI + `4` Y-ROI; `4× PSM 6 + 4× PSM 11`). When deterministic fallback to Arm A triggers (`13/30` images in Arm B, `12/30` images in Arm C), Arm A adds `2` full-image OCR calls (effective mean calls/image including fallback: `8.87` for Arm B, `8.80` for Arm C; Arm A alone uses `2` full-image calls).
  - **Differing Pixel Counts & Measured End-to-End Wall Time:** Matching attempted OCR call count (`8` vs `8`) does **not** equate total OCR pixel throughput: Arm C's View C2 (`2.0x` bicubic upscaled) processes **`4×` more pixels** than Arm B's View B2 (`1.0x` native). Measured end-to-end wall-clock runtime reflects this difference: **`0.982 s/img`** mean (median `0.893 s`, max `1.906 s`, mean OCR `0.664 s`) for Arm B vs. **`1.112 s/img`** mean (median `0.986 s`, max `2.857 s`, mean OCR `0.801 s`; `+13.3%` end-to-end) for Arm C.
  - **Exact Frozen Pixel-Path Identity (`limit_to_calibration = False`, ZERO GT inputs in calibration or tracing):**
    - Arm A: `4/4` outputs exact match, **`max_abs_px_diff = 0.0 px`** (reproduces Stage-0 `PID = 53928` Arm A FPC `0.937580` and `3/30` TU exactly).
    - Arm B: `17/17` outputs exact match, **`max_abs_px_diff = 0.0 px`**.
    - Arm C: `19/19` outputs exact match, **`max_abs_px_diff = 0.0 px`**.
  - **Dev-Only & Separate-Oracle Scope:** Arms A, B, and C below are dev-only deployed automatic results on `N = 30` single-line dev plots; the Stage-0 fixed-tracker oracle (`0.119598`, `30/30` TU) is strictly a separate diagnostic ceiling and is never compared as an automated arm or equated with DigitizerBench-Full (`2,980` images).

---

## 2. Main Three-Arm Paired Results (`N = 30`, Exact Paper §4.3 Eq. 1)

### 2.1 Overall Summary (Dev-Only Deployed Automatic Arms; Separate Stage-0 Oracle Diagnostic Noted Below)

| Arm | Pre-Fallback OCR Calls (Eff. w/ Fallback) | FPC-NRMSE (↓) | Curve-Span Sensitivity FPC | Output Success `OS` (↑) | Trusted Usability `TU` (↑) | Accepted / Fallback | Mean End-to-End CPU s/img (median, max) |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Arm A: Released Default (`8fb89a62`)** | `2` (`2.00`) | `0.937579854` | `0.941755394` | `13.3%` (`4/30`) | `10.0%` (`3/30`) | — | `0.511 s` (`0.387 s`, `1.461 s`) |
| **Arm B: Single-Res `1.0x` Control (ROI + PSM 6/11 + LOTO)** | `8` (`8.87`) | `0.590085925` | `0.598248719` | `56.7%` (`17/30`) | `53.3%` (`16/30`) | `17` / `13` | `0.982 s` (`0.893 s`, `1.906 s`) |
| **Arm C: Matched Two-Res `1.0x + 2.0x` (Same Engine, `4×` px in View 2)** | `8` (`8.80`) | `0.493545253` | `0.502092878` | `63.3%` (`19/30`) | `60.0%` (`18/30`) | `18` / `12` | `1.112 s` (`0.986 s`, `2.857 s`) |

*Separate Stage-0 Oracle Diagnostic Ceiling (NOT an automated arm; never used in B or C):* Fixed-tracker oracle-axis (`PID = 53928`) achieved `FPC-NRMSE = 0.119598008` (curve-span sensitivity `0.131032`), `OS = 100.0% (30/30)`, `TU = 100.0% (30/30)`, `0.220 s/img`.

### 2.2 Paired Contrasts (`B = 10,000` Bootstrap Resamples, `seed = 20261124`)

| Contrast | Mean FPC Reduction (↑) | Paired Bootstrap 95% CI | Net Newly Trusted (`+` / `-`) | Improved (`> 0.01`) / Worsened (`> 0.01`) |
|---|---:|---|---:|---:|
| **B vs. A** (Same-res ROI + PSM 6/11 + alignment + LOTO) | `+0.347493930` | `[+0.1997952, +0.5033300]` | `+13` (`+13` / `0`) | `14` / `0` |
| **C vs. A** (Two-res ROI + PSM 6/11 + alignment + LOTO) | `+0.444034601` | `[+0.2862803, +0.6075370]` | `+15` (`+15` / `0`) | `17` / `0` |
| **C vs. B (PRIMARY MATCHED CONTRAST)** | **`+0.096540672`** | **`[-0.0006114, +0.2234884]`** | **`+2`** (`+2` / `0`) | **`3`** / **`1`** |

- **Mean inlier counts when accepted:** Arm B `6.00` (X) / `7.00` (Y) vs. Arm C `6.56` (X) / `7.29` (Y).
- **Acceptance reasons:** Every accepted axis in BOTH Arm B (`17` X, `23` Y) and Arm C (`18` X, `24` Y) passed the primary held-out LOTO gate (`loto_m>=3_accepted`; zero axes relied on the secondary `two_tick_multiview_verified` gate).
- **Pre-Locked Dev Advancement Gate (C over B):**
  - `FPC_B - FPC_C >= 0.050`: **PASS** (`+0.096541`; curve-span sensitivity `+0.096156`)
  - `TU_C - TU_B >= +2`: **PASS** (`+2`, `16/30 -> 18/30`, `0` lost trust)
  - No serious renderer regression (`worst renderer B-C >= -0.050`): **PASS** (worst renderer is `+0.0924`, positive across all 3 renderers)
  - Paired bootstrap 95% CI strictly `> 0`: **FAIL** (`[-0.0006, +0.2235]`, straddling zero because only `3/30` discrete plots account for the gain, and $(27/30)^{30} = 4.24\% > 2.5\%$)
  - **Locked Gate Outcome:** **`NO_MATERIAL_MULTISCALE_GAIN_OVER_CONTROL`** (do NOT open held-out data without further coordinator decision).

### 2.3 Breakdown by Renderer, DPI Bucket & Curve Color

| Slice | `N` | Arm A FPC (`TU`) | Arm B FPC (`TU`) | Arm C FPC (`TU`) | `B - C` FPC | `C - B` `TU` | Arm B / Arm C Mean CPU s |
|---|---:|---:|---:|---:|---:|---:|---:|
| **`matplotlib`** | `10` | `0.9337` (`1`) | `0.6148` (`5`) | `0.5225` (`5`) | `+0.0924` | `0` | `1.011 s` / `1.183 s` |
| **`plotly`** | `10` | `0.9494` (`1`) | `0.6122` (`5`) | `0.5133` (`6`) | `+0.0989` | `+1` | `1.034 s` / `1.176 s` |
| **`altair`** | `10` | `0.9296` (`1`) | `0.5432` (`6`) | `0.4449` (`7`) | `+0.0984` | `+1` | `0.900 s` / `0.979 s` |
| **`low_dpi_le_150`** (`72–150 DPI`) | `16` | `1.0000` (`0`) | `0.5966` (`8`) | `0.4762` (`9`) | `+0.1204` | `+1` | — |
| **`high_dpi_ge_300`** (`300–600 DPI`) | `14` | `0.8662` (`3`) | `0.5827` (`8`) | `0.5134` (`9`) | `+0.0693` | `+1` | — |
| Colored non-black `R2` | `25` | `0.9532` (`2`) | `0.6441` (`11`) | `0.5280` (`13`) | `+0.1161` | `+2` | — |
| Black curve `#000000` | `5` | `0.8592` (`1`) | `0.3198` (`5`) | `0.3211` (`5`) | `-0.0012` | `0` | — |

---

## 3. Diagnostic Dissection: Where C Helped, Where B Already Captured the Gain, and Why 12 Plots Still Failed

1. **Same-Resolution Geometry (`Arm B`) Captured `78.3%` of Total FPC Reduction over Released Arm A (`+0.3475` of `+0.4440`, `+13` of `+15` newly trusted):**
   - Eliminating mandatory snap-to-black, cropping axis ROIs, combining Tesseract `PSM 6` + `PSM 11`, right-edge clustering Y-ticks, and applying held-out LOTO linearity verification immediately rescued `13` failed plots across all three renderers (`A0250`, `B0027`, `D0261`, `B0587` [trusted but scaled wrong in B], `A0348`, `D0475`, `B0606`, `A0196`, `B0048`, `B0359`, `C0568`, `B0464`, `C0590`) and cut `A0234` from `0.3375 -> 0.1292`.
   - On `B0396__single__altair` (`300 DPI`), Arm B's `1.0x clean_gray` view succeeded (`0.2904`) while Arm C fell back to Arm A (`0.2962`, `-0.0058`), confirming that Arm B is a genuine strong equal-budget single-resolution control rather than a strawman.
2. **Exact `3` Discrete Plots Where Two-Resolution Allocation (`Arm C`, `1x + 2x`) Beat `Arm B`:**
   - **`B0587__single__matplotlib` (`150 DPI`, `6 pt`, `blur = 1.0`):** `1.0x` Arm B dropped decimal points (`2.0..8.0` on X, `0.01..9.01` on Y -> `e_bar = 5.1556`, capped `F = 1.0`); `2.0x` Arm C recovered `11/11` X ticks (`[-0.998, +1.000]`) and `10/11` Y ticks (`[0.100, 1.000]`) -> **`F: 1.0000 -> 0.0630` (`+0.9370`)**.
   - **`D0326__single__plotly` (`300 DPI`, `8 pt`, `blur = 0.5`, `[0, 0.01]`):** `1.0x` Arm B failed X LOTO (`no_consistent_scale`); `2.0x` Arm C recovered `3` consistent X ticks (`[0.000003, 0.010004]`) -> **`F: 1.0000 -> 0.0109` (`+0.9891`, newly trusted)**.
   - **`A0431__single__altair` (`72 DPI`, `576×576`, `blur = 0.75`):** `1.0x` Arm B failed LOTO on both axes; `2.0x` Arm C jumped from `1` to `17` X-tokens (`7` inliers) and `7` to `10` Y-tokens (`9` inliers) -> **`F: 1.0000 -> 0.0070` (`+0.9930`, newly trusted)**.
   - Sole loss `> 0.01`: `A0234__single__matplotlib` (`0.1292 -> 0.1420`, `-0.0128`, tiny `0.8%` X-endpoint jitter).
3. **Why `12` Plots (`FPC = 1.0` in Arm C) Still Failed in BOTH B and C (Not Solved by `1x` vs `2x` View Allocation Alone):**
   - **Zero X-ROI tokens on rotated/crowded X-labels (`5` plots: `D0166`, `B0174`, `B0384`, `B0294`, plus `D0219`):** Y-axis passed LOTO cleanly on `4/5`, while X-ROI yielded `0` tokens across all horizontal OCR views (rotated/crowded multi-digit X labels).
   - **Unit-suffix (`k`) rescaling (`1` plot: `B0370__single__altair`, true X `[1000, 100000]`):** Both B and C read `20k..80k` with `"k"` stripped as a perfectly linear `[17.3, 83.3]` scale, passing LOTO (`5` inliers) while off by `1000×` (`0%` x-overlap).
   - **Clipped narrow ROIs / severe low-res blur (`4` plots: `D0244`, `C0608`, `D0398`, `D0108`):** On `C0608` (`300×169`) and `D0244` (`600×337`), `plot_left` landed at `x = 14–21`, clipping the Y-margin (`0` tokens); on `D0108` (`72 DPI`, `288×288`, `blur = 1.0`), `2.0x` increased Y tokens (`1 -> 5`) but both axes remained too degraded for `m >= 3` LOTO.
   - **3-tick minimal plots (`2` plots: `D0296`, `D0394`):** Only `3` ticks exist per axis; dropping 1 tick leaves `2` ticks that did not clear the strict `min_conf >= 70` two-tick gate.

---

## 4. Prior Art & Honest Scope Conclusion

- Relative to nearby prior work (**Graph-FINDER**, [`Nature npj Comput. Mater. 2026`](https://www.nature.com/articles/s41524-026-02247-y); **ChartRecover**; and **LinePilot's** own §3.1 axis-ROI + PSM 6/11 + robust endpoint checking), this paired dev pilot demonstrates two concrete, grounded findings on the pinned single-line diagnostic:
  1. **Same-view geometry & robust LOTO alignment (`Arm B`) captures the bulk of the gain** over released `LinePilot 8fb89a62` (`FPC 0.9376 -> 0.5901`, `TU 3/30 -> 16/30`, CI `[+0.200, +0.503]`).
  2. **Matched-budget two-resolution view allocation (`Arm C`, `1x + 2x`) adds a directionally positive cross-renderer lift (`+0.0965` FPC, `+2` TU, `3` wins vs `1` tiny `-0.013` loss, `+0.13 s/img`),** specifically on small-font / blurred / low-DPI ticks (`B0587`, `D0326`, `A0431`), **but does NOT clear the pre-locked strict 95% CI `> 0` gate on `N = 30` (`CI95 = [-0.0006, +0.2235]`)** — while `12/30` remaining failures stem from orthogonal axis-calibration bottlenecks (rotated X-labels, `"k"` unit suffixes, tight ROI clipping on narrow low-res plots) rather than `1x` vs `2x` resolution alone.
- **Stop Point Respected:** No held-out data opened, no retuning performed, no full benchmark run, no novelty claims, no PDF/media/PR created. Awaiting coordinator decision on whether to freeze here, refine the shared ROI/rotated-label/suffix handling first, or test the existing locked contrast on a larger disjoint split.

---

## 5. Sealed Stage-1 SHA-256 Artifact Manifest

| Artifact | SHA-256 |
|---|---|
| [`STAGE0_LINEPILOT_PROTOCOL.md`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE0_LINEPILOT_PROTOCOL.md) | `b05506fb7c112e35d16075cf052041019a7ce55198f868d90ae2fd081e9ec518` |
| [`STAGE1_DEV_PROTOCOL.md`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/STAGE1_DEV_PROTOCOL.md) | `27922a5722704aefd77344e69dc243eeba8fbb987bf74a53ab9f0cf38ce5e916` |
| [`stage1_axis_calibration.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage1_axis_calibration.py) | `3f6d8c957cece1b9a4c2f3b0e1087bc09fc576b2d2230ec44de8749c5ea9dadd` |
| [`test_stage1_axis_calibration.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/test_stage1_axis_calibration.py) | `1e83c9809793656241a4062d13f95f2e48dd8a61555c966e8e520676bbc08bf6` |
| [`run_stage1_dev_pilot.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/run_stage1_dev_pilot.py) | `dbb2c060f155f9d6ac3fffbb4372ff0eae93d091af8a55fa384fda846c00b917` |
| [`eval_digitizerbench_sec43.py`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/eval_digitizerbench_sec43.py) | `b0f1aea660c1878a91debe5c2d74010c9c2848c9395e1c5e5501774fdef7cece` |
| [`stage1_dev30_summary.json`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage1_dev_outputs/stage1_dev30_summary.json) | `d07078e39b5b99588aa525dda7a1b9c428d1a651c12f9281e42264ce8d003dbb` |
| [`stage1_dev30_per_image.jsonl`](file:///D:/AI_Science/antigravity/linepilot_axis_calibration_stage0_20261124/stage1_dev_outputs/stage1_dev30_per_image.jsonl) | `527d1945e1a923f69eba6c4e3a5ef24e4029d9349ee07289740ce3b1ea9302a1` |
