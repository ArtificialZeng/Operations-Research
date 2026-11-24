# LinePilot Axis-Calibration Dev Pilot Archive (`research/linepilot_axis_calibration`)

**Status:** `FROZEN_LIMITED_DEV_ARCHIVE_GATE_FAILED` (2026-11-24)  
**Outcome:** Pre-locked Stage-1 conjunctive advancement gate **FAILED** (`NO_MATERIAL_MULTISCALE_GAIN_OVER_CONTROL`) because the paired bootstrap 95% CI for multi-resolution `Arm C` vs. single-resolution `Arm B` included zero (`[-0.0006114, +0.2234884]`) on the `N = 30` dev cohort. Stop rule honored: frozen as a limited exploratory dev archive with **zero held-out selection, download, or scoring** (`2,470` untouched `DigitizerBench-Full` `base_id`s remain untouched), zero retuning, and no paper, PDF, leaderboard, or novelty claims.

---

## 1. Scientific Scope & Explicit Disclaimers

- **Question Tested:** On pinned `RayanA07/LinePilot` (`8fb89a62fb0565290b72ba61cb073d732d8e7578`, `LinePilot 2.17.1`), can multi-scale OCR with held-out tick consistency improve numerical single-line plot recovery over an equal-call-budget single-resolution axis-ROI control by changing **only axis calibration** (keeping exact frozen pixel traces identical)?
- **Pinned-Code Single-Line Diagnostic Scope (NOT an Official DigitizerBench-Full Comparison):**
  - Source audit confirmed that released `RayanA07/LinePilot` (`8fb89a62`) `Digitizer/digitizer_api.py` automatically selects and exports **one active color slot only**, with no public automatic multicurve DP runner shipped.
  - Both Stage-0 and Stage-1 therefore evaluated a locked balanced **single-line** non-bridge dev cohort (`N = 30`: `10` matplotlib, `10` plotly, `10` altair; `0` overlap with `60` Lite/bridge `base_id`s; `2,470` Full `base_id`s untouched).
  - **Do NOT compare this dev-only single-line diagnostic directly with Paper Table 3's DigitizerBench-Full (`2,980` images) `0.672` FPC-NRMSE / `38.2%` TU (`arXiv:2609.19377v1`).**
- **Separate Oracle Diagnostic:** Stage-0's fixed-tracker oracle-axis arm (`tick_points` + `axis_values` from `tick_ground_truth.parquet`) is strictly a diagnostic ceiling kept separate from all deployed automatic arms (`A`, `B`, `C`); no oracle or ground-truth inputs were used in any automated calibration or curve trace.
- **Nearby Prior Art:** Contextualized against Graph-FINDER ([`npj Computational Materials 2026`](https://www.nature.com/articles/s41524-026-02247-y)), ChartRecover, and LinePilot's own §3.1 axis-ROI + Tesseract PSM 6/11 + robust endpoint checking (`Digitizer/AxisReader.py` `_line_inliers` / `_robust_endpoints`).

---

## 2. Summary of Sealed Dev-Only Results (`N = 30`, Exact Paper §4.3 Eq. 1)

### Stage-0: Fixed-Tracker Oracle-Axis Bottleneck Diagnostic (`PID = 53928`, `26.58 s`)
- **Released Default OCR (`Arm A`, `8fb89a62`):** `FPC-NRMSE = 0.937580`, `OS = 13.3% (4/30)`, `TU = 10.0% (3/30)` (`4/4` valid outputs verified `0.0 px` pixel-identical to frozen trace). Error counts: `14` `axis_calibration_snap_failed`, `7` `axis_ocr_missing_ticks`, `5` `axis_ocr_degenerate_same_endpoint`, `4` `ok` (`3/4` with X-axis misreads).
- **Separate Oracle-Axis Diagnostic Ceiling (`Arm B`):** `FPC-NRMSE = 0.119598`, `OS = 100.0% (30/30)`, `TU = 100.0% (30/30)` (`30/30` verified `0.0 px` pixel-identical). Paired oracle bottleneck gain: `+0.817982` FPC reduction (95% CI `[+0.7072, +0.9126]`), `+27/30` net newly trusted -> Stage-0 feasibility gate (`>= 0.080` and `>= 3` TU) **PASSED**.
- **Stage-0 Revisions Disclosed:** Locked `STAGE0_LINEPILOT_PROTOCOL.md` (`b05506fb...`) preserved unmodified. First run interrupted at `[03/30] A0250__single__matplotlib` (`zero_span_confinement=True`, `curve_span == 0`); applied scoped denominator-only patch (`eval_digitizerbench_sec43.py`: `d4c59352... -> b0f1aea6...`; `run_linepilot_stage0_diagnostic.py`: `5b19cc0f... -> 13bc671f...`; curve-span fallback sensitivity `+0.8107`). Data fetched via persistent `KeepAliveRangeClient` HTTP Range (`9.09 MB`, `30/2,980` row groups).

### Stage-1: Matched-Call-Budget Dev Engineering Pilot (`PID = 62340`, `82.35 s`)
- All three deployed arms ran on **identical cached frozen pixel traces** (`max_abs_px_diff = 0.0 px` verified on `4/4` Arm A, `17/17` Arm B, `19/19` Arm C).
- **Budget, Pixel-Count & Timing Clarification:** Both Arm B and Arm C perform **`8` attempted OCR calls per image before fallback** (`4` X-ROI + `4` Y-ROI; `4× PSM 6 + 4× PSM 11`), adding `2` full-image Arm A calls only on deterministic fallback (`13/30` images in B -> `8.87` mean effective calls; `12/30` in C -> `8.80` mean effective calls). Because View C2 (`2.0x` bicubic) processes **`4×` more pixels** than View B2 (`1.0x`), measured end-to-end wall time per image is higher for C (`1.112 s/img`, max `2.857 s`) than for B (`0.982 s/img`, max `1.906 s`).

| Dev Arm (`N = 30`, Deployed Automatic Only) | Pre-Fallback Calls (Eff.) | FPC-NRMSE (↓) | Curve-Span Sensitivity | `OS` (↑) | `TU` (↑) | Mean End-to-End s/img |
|---|---:|---:|---:|---:|---:|---:|
| **Arm A:** Released Default (`8fb89a62`) | `2` (`2.00`) | `0.937579854` | `0.941755394` | `13.3%` (`4/30`) | `10.0%` (`3/30`) | `0.511 s` |
| **Arm B:** Single-Res `1.0x` Control (ROI + PSM 6/11 + LOTO) | `8` (`8.87`) | `0.590085925` | `0.598248719` | `56.7%` (`17/30`) | `53.3%` (`16/30`) | `0.982 s` |
| **Arm C:** Matched Two-Res `1.0x + 2.0x` (Same Engine) | `8` (`8.80`) | `0.493545253` | `0.502092878` | `63.3%` (`19/30`) | `60.0%` (`18/30`) | `1.112 s` |

- **B vs. A:** `+0.347493930` FPC reduction (95% CI `[+0.1997952, +0.5033300]`), `+13` newly trusted (`14` improved / `0` worsened) — single-resolution geometry/ROI/LOTO already captured `78.3%` of C's total gain over A.
- **Primary C vs. B:** `+0.096540672` FPC reduction (curve-span sensitivity `+0.096155841`), **paired bootstrap 95% CI `[-0.0006114, +0.2234884]`**, `+2` net newly trusted (`16 -> 18`, `0` lost), `3` plots improve `> 0.01` (`B0587` matplotlib `+0.937`, `D0326` plotly `+0.989`, `A0431` altair `+0.993`), `1` worsens `> 0.01` (`A0234` `-0.013`).
- **Pre-Locked Conjunctive Gate:** **FAILED** (`passes_fpc = True`, `passes_tu = True`, `passes_no_serious_renderer_reg = True`, `passes_ci_gt_0 = False`).
- **Stage-1 Original-Run Symbol-Only Fix Disclosure:** The original Stage-1 run (`run_stage1_dev_pilot.py` SHA `5191a160...`) wrote all 30 forward per-image records cleanly and hit an aggregation-symbol typo (`ev.aggregate_sec43` -> `ev.summarize_sec43`). Only that symbol was fixed (`5191a160... -> dbb2c060...`), with zero modification to `STAGE1_DEV_PROTOCOL.md` (`27922a57...`), `stage1_axis_calibration.py` (`3f6d8c95...`), or `eval_digitizerbench_sec43.py` (`b0f1aea6...`), before the clean `PID = 62340` run (`stage1_dev30_summary.json` SHA `d07078e3...`).

---

## 3. Public Sources, Licenses & Reproducibility (No Raw Assets Redistributed)

No dataset images, Parquets, vendor OCR binaries, nested git clones, virtual environments, or raw per-pixel CSVs are redistributed in this archive. Reproduce locally from official public sources:

- **DigitizerBench:** [`https://huggingface.co/datasets/LinePilot/DigitizerBench`](https://huggingface.co/datasets/LinePilot/DigitizerBench), pinned commit `8b4a3190d5991414dad92049671de75754dd9f44` (**Apache-2.0**).
- **LinePilot Upstream Code:** [`https://github.com/RayanA07/LinePilot`](https://github.com/RayanA07/LinePilot), pinned commit `8fb89a62fb0565290b72ba61cb073d732d8e7578` (`v2.17.1`, **Apache-2.0**).
- **LinePilot Paper Protocol:** [`https://arxiv.org/html/2609.19377v1`](https://arxiv.org/html/2609.19377v1) (**CC BY 4.0**).
- **Official Portable Tesseract Source:** [`https://github.com/RayanA07/LinePilot/releases/download/v2.17.1/Digitizer.exe`](https://github.com/RayanA07/LinePilot/releases/download/v2.17.1/Digitizer.exe) (Apache-2.0 / Tesseract bundled runtime, SHA-256 `5b15b73b066e3ba2cca4dab1bde208e580d2ab03804c5e037cbb074a35ce8f7e`).

### Minimal CPU-Only Reproduction Steps
```powershell
# 1. Clone pinned upstream LinePilot into upstream_linepilot/
git clone https://github.com/RayanA07/LinePilot.git upstream_linepilot
git -C upstream_linepilot checkout 8fb89a62fb0565290b72ba61cb073d732d8e7578

# 2. Create isolated Python 3.12 venv matching upstream constraints.txt
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r upstream_linepilot\requirements.txt -c upstream_linepilot\constraints.txt pandas pyarrow matplotlib pytest pyinstaller pefile

# 3. Extract workspace-only portable Tesseract v5.5.3.20260724 (zero global install / PATH changes)
.\.venv\Scripts\python.exe setup_portable_vendor_tesseract.py

# 4. Fetch ONLY full/manifest.parquet + the 30 locked single-line dev plots (~9.1 MB via HTTP Range)
.\.venv\Scripts\python.exe fetch_digitizerbench_lite_and_full_manifest.py
.\.venv\Scripts\python.exe stage0_lock_single_dev30_and_fetch.py

# 5. Verify §4.3 scorer and synthetic Stage-1 fixtures, then replay Stage-0 and Stage-1 dev pilots
.\.venv\Scripts\python.exe eval_digitizerbench_sec43.py
.\.venv\Scripts\python.exe test_stage1_axis_calibration.py
.\.venv\Scripts\python.exe run_linepilot_stage0_diagnostic.py
.\.venv\Scripts\python.exe run_stage1_dev_pilot.py
```

---

## 4. Archive Contents

- **Protocols & Reports:** `README.md`, `STATUS.md`, `STAGE0_LINEPILOT_PROTOCOL.md`, `STAGE0_LINEPILOT_RESULT.md`, `STAGE1_DEV_PROTOCOL.md`, `STAGE1_DEV_PILOT_RESULT.md`, `MANIFEST.json`.
- **Provenance Receipts:** `PORTABLE_OCR_RECEIPT.json`, `STAGE0_SINGLE_DEV_30_RECEIPT.json`, `STAGE0_PRELAUNCH_FIXTURES_RECEIPT.json`.
- **Reproducible Scripts & Tests:** `setup_portable_vendor_tesseract.py`, `fetch_digitizerbench_lite_and_full_manifest.py`, `stage0_lock_single_dev30_and_fetch.py`, `eval_digitizerbench_sec43.py`, `run_linepilot_stage0_diagnostic.py`, `stage1_axis_calibration.py`, `test_stage1_axis_calibration.py`, `run_stage1_dev_pilot.py`.
- **Sealed Evidence:** `stage0_outputs/linepilot_stage0_dev30_summary.json`, `stage0_outputs/linepilot_stage0_dev30_per_image.jsonl`, `stage1_dev_outputs/stage1_dev30_summary.json`, `stage1_dev_outputs/stage1_dev30_per_image.jsonl`.
