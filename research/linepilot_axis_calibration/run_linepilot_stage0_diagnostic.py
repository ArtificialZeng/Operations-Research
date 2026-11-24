"""
Stage-0 Native CPU-Only Paired Diagnostic Harness for LinePilot 2.17.1 (commit 8fb89a62):
  - Arm A: Actual default upstream automatic OCR (`digitizer_api.digitize_image`, vendored
    Tesseract v5.5.3.20260724, `limit_to_calibration=False`).
  - Arm B: Diagnostic fixed-tracker oracle-axis arm (`digitizer_api.digitize_image` with BOTH
    official `tick_points` AND `axis_values` from `dev_tick_ground_truth_30.parquet`,
    `limit_to_calibration=False`, zero GT colors, zero GT series during tracing).
  - Verifies exact `(x_px, y_px)` traced pixel-path identity and exact `color_rgb` identity
    across arms by freezing the upstream pixel path ONCE per image and asserting zero pixel diff!
  - Scores ALL 30 locked balanced single-line Full dev images (`10 matplotlib`, `10 plotly`,
    `10 altair`) using exact Paper §4.3 Equation (1) FPC-NRMSE (`eval_digitizerbench_sec43.py`).
  - Evaluates the pre-locked Stage-0 advance gate (`FPC_ocr - FPC_oracle >= 0.080` AND
    `TU_oracle_count - TU_ocr_count >= 3`). Does NOT implement or score any new OCR variant
    and does NOT touch the 2,470 untouched Full `base_id`s.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

os.environ["QT_QPA_PLATFORM"] = "offscreen"

import numpy as np
import pandas as pd

PROJ = Path(r"D:\AI_Science\antigravity\linepilot_axis_calibration_stage0_20261124")
DIGITIZER_DIR = PROJ / "upstream_linepilot" / "Digitizer"
sys.path.insert(0, str(DIGITIZER_DIR))
sys.path.insert(0, str(PROJ))

from PyQt6 import QtGui  # noqa: E402
import digitizer_api  # noqa: E402
from UI import DigitizerWindow  # noqa: E402
import eval_digitizerbench_sec43 as ev  # noqa: E402

DEV_DIR = PROJ / "data_digitizerbench" / "full_single_dev_30"
OUT_DIR = PROJ / "stage0_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

GATE_MIN_FPC_REDUCTION = 0.080
GATE_MIN_NEW_TRUSTED = 3
N_BOOT = 5000
BOOT_SEED = 20261124


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def classify_ocr_error(msg: str) -> str:
    m = msg.lower()
    if "same x value" in m or "same y value" in m or "degenerate" in m:
        return "axis_ocr_degenerate_same_endpoint"
    if "did not find all x/y min/max" in m or "did not find all tick point" in m:
        return "axis_ocr_missing_ticks"
    if "snap-to-black" in m or "could not locate all four axis tick" in m:
        return "axis_calibration_snap_failed"
    if "no color was supplied" in m or "auto color selection" in m:
        return "baseline_no_color_detected"
    if "produced no points" in m:
        return "baseline_zero_points_extracted"
    if "calibration box is invalid" in m or "requires calibration" in m:
        return "axis_calibration_box_invalid"
    return "other_runtime_error"


def extract_frozen_pixels(img_path: Path) -> Tuple[Optional[Tuple[int, int, int]], List[Tuple[float, float]]]:
    """
    Runs upstream `DigitizerWindow` color auto-pick + `PointPlacer.find_points_by_color`
    with `limit_to_calibration=False` and ZERO GT colors or GT series, freezing `(x_px, y_px)`.
    """
    _app = digitizer_api._ensure_qt_app()
    img = QtGui.QImage(str(img_path))
    if img.isNull():
        return None, []
    win = DigitizerWindow()
    win.set_image(img)
    color = win._selected_color
    if color is None:
        return None, []
    win._limit_points_to_calib = False
    win._active_color_state().limit_points_to_calib = False
    win._compute_points()
    pts = [(float(pt.x), float(pt.y)) for pt in win._active_color_state().points]
    return (int(color[0]), int(color[1]), int(color[2])), pts


def verify_csv_pixels_identical(csv_path: Path, frozen_pixels: List[Tuple[float, float]]) -> Tuple[bool, float]:
    df = pd.read_csv(csv_path)
    if len(df) != len(frozen_pixels):
        return False, float("inf")
    if len(df) == 0:
        return True, 0.0
    csv_x = df["x_px"].to_numpy(dtype=np.float64)
    csv_y = df["y_px"].to_numpy(dtype=np.float64)
    fx = np.array([p[0] for p in frozen_pixels], dtype=np.float64)
    fy = np.array([p[1] for p in frozen_pixels], dtype=np.float64)
    max_diff = float(max(np.max(np.abs(csv_x - fx)), np.max(np.abs(csv_y - fy))))
    return max_diff <= 1e-5, max_diff


def paired_bootstrap_ci(diffs: np.ndarray, n_boot: int = N_BOOT, seed: int = BOOT_SEED) -> List[float]:
    rng = np.random.default_rng(seed)
    n = len(diffs)
    idx = rng.integers(0, n, size=(n_boot, n))
    means = np.mean(diffs[idx], axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return [float(lo), float(hi)]


def main() -> None:
    t_all0 = time.perf_counter()
    protocol_path = PROJ / "STAGE0_LINEPILOT_PROTOCOL.md"
    assert protocol_path.exists(), "STAGE0_LINEPILOT_PROTOCOL.md must be locked before running!"
    protocol_sha = sha256_file(protocol_path)

    split_rec = json.loads((PROJ / "STAGE0_SINGLE_DEV_30_RECEIPT.json").read_text(encoding="utf-8"))
    gt_df = pd.read_parquet(DEV_DIR / "dev_ground_truth_30.parquet")
    tk_df = pd.read_parquet(DEV_DIR / "dev_tick_ground_truth_30.parquet")

    ocr_out_dir = OUT_DIR / "arm_a_default_ocr_csvs"
    ora_out_dir = OUT_DIR / "arm_b_oracle_axis_csvs"
    ocr_out_dir.mkdir(parents=True, exist_ok=True)
    ora_out_dir.mkdir(parents=True, exist_ok=True)

    per_image_rows: List[Dict[str, Any]] = []
    ocr_evals: List[ev.ImageEvalResult] = []
    ora_evals: List[ev.ImageEvalResult] = []

    ocr_pixel_identity_checks = {"checked": 0, "exact_match": 0, "max_abs_px_diff": 0.0}
    ora_pixel_identity_checks = {"checked": 0, "exact_match": 0, "max_abs_px_diff": 0.0}
    ocr_times: List[float] = []
    ora_times: List[float] = []

    for idx, meta in enumerate(split_rec["selected_plots"], start=1):
        img_id = meta["image_id"]
        img_path = DEV_DIR / meta["image_path"]

        # Load GT series (used ONLY for scoring AFTER both arms run; NEVER passed to tracing!)
        g_sub = gt_df[gt_df["image_id"] == img_id]
        gt_series = [
            ev.clean_xy_series(grp.sort_values("sample_index")["x"].to_numpy(), grp.sort_values("sample_index")["y"].to_numpy())
            for _, grp in g_sub.groupby("line_id", sort=True)
        ]

        # Official ticks from tick_ground_truth.parquet (used ONLY in scoring W_i and diagnostic Oracle-Axis Arm B!)
        t_sub = tk_df[tk_df["image_id"] == img_id]
        tx = t_sub[t_sub["axis"] == "x"].sort_values("tick_value")
        ty = t_sub[t_sub["axis"] == "y"].sort_values("tick_value")
        x_ticks_px_val = (
            float(tx["pixel_x"].iloc[0]),
            float(tx["pixel_x"].iloc[-1]),
            float(tx["tick_value"].iloc[0]),
            float(tx["tick_value"].iloc[-1]),
        )
        oracle_ticks = [
            (float(tx["pixel_x"].iloc[0]), float(tx["pixel_y"].iloc[0])),
            (float(tx["pixel_x"].iloc[-1]), float(tx["pixel_y"].iloc[-1])),
            (float(ty["pixel_x"].iloc[0]), float(ty["pixel_y"].iloc[0])),
            (float(ty["pixel_x"].iloc[-1]), float(ty["pixel_y"].iloc[-1])),
        ]
        oracle_axis = (
            float(tx["tick_value"].iloc[0]),
            float(tx["tick_value"].iloc[-1]),
            float(ty["tick_value"].iloc[0]),
            float(ty["tick_value"].iloc[-1]),
        )
        y_axis_span = float(oracle_axis[3] - oracle_axis[2])

        # 0. Freeze baseline extraction (color auto-pick + traced pixels) ONCE per image (zero GT info!)
        frozen_color, frozen_pixels = extract_frozen_pixels(img_path)
        baseline_extraction_ok = (frozen_color is not None) and (len(frozen_pixels) > 0)

        # 1. Arm A: Actual default upstream automatic OCR (RayanA07/LinePilot 8fb89a62)
        t0 = time.perf_counter()
        ocr_status = "ok"
        ocr_err_cat = ""
        ocr_err_msg = ""
        ocr_axis_vals = None
        ocr_tick_pts = None
        ocr_conf = None
        ocr_pred_series: List[ev.CleanSeries] = []
        ocr_px_match: Optional[bool] = None
        try:
            res_ocr = digitizer_api.digitize_image(
                pic_dir=img_path,
                limit_to_calibration=False,
                output_dir=ocr_out_dir,
            )
            assert res_ocr.used_ocr is True
            ocr_axis_vals = list(res_ocr.axis_values)
            ocr_tick_pts = [list(p) for p in res_ocr.tick_points]
            ocr_conf = res_ocr.ocr_confidence
            ocr_pred_series = ev.load_pred_series_from_csv(res_ocr.csv_path)
            matched, mdiff = verify_csv_pixels_identical(Path(res_ocr.csv_path), frozen_pixels)
            assert matched and tuple(res_ocr.color_rgb) == frozen_color, (
                f"Pixel/color drift in OCR arm on {img_id}: diff={mdiff}, color={res_ocr.color_rgb} vs {frozen_color}"
            )
            ocr_px_match = matched
            ocr_pixel_identity_checks["checked"] += 1
            ocr_pixel_identity_checks["exact_match"] += int(matched)
            ocr_pixel_identity_checks["max_abs_px_diff"] = max(ocr_pixel_identity_checks["max_abs_px_diff"], mdiff)
        except Exception as exc:
            ocr_status = "failed"
            ocr_err_msg = str(exc)
            ocr_err_cat = classify_ocr_error(ocr_err_msg)
        ocr_dt = time.perf_counter() - t0
        ocr_times.append(ocr_dt)

        eval_ocr = ev.evaluate_image_sec43(
            image_id=img_id,
            pred_series=ocr_pred_series,
            gt_series=gt_series,
            x_ticks_px_val=x_ticks_px_val,
            y_axis_span=y_axis_span,
            run_error=ocr_err_cat or ocr_err_msg,
        )
        ocr_evals.append(eval_ocr)

        # 2. Arm B: Diagnostic Fixed-Tracker Oracle-Axis (BOTH official tick_points AND axis_values!)
        t0 = time.perf_counter()
        ora_status = "ok"
        ora_err_cat = ""
        ora_err_msg = ""
        ora_pred_series: List[ev.CleanSeries] = []
        ora_px_match: Optional[bool] = None
        try:
            res_ora = digitizer_api.digitize_image(
                pic_dir=img_path,
                tick_points=oracle_ticks,
                axis_values=oracle_axis,
                limit_to_calibration=False,
                output_dir=ora_out_dir,
            )
            assert res_ora.used_ocr is False, "Oracle arm MUST skip OCR!"
            ora_pred_series = ev.load_pred_series_from_csv(res_ora.csv_path)
            matched, mdiff = verify_csv_pixels_identical(Path(res_ora.csv_path), frozen_pixels)
            assert matched and tuple(res_ora.color_rgb) == frozen_color, (
                f"Pixel/color drift in Oracle arm on {img_id}: diff={mdiff}, color={res_ora.color_rgb} vs {frozen_color}"
            )
            ora_px_match = matched
            ora_pixel_identity_checks["checked"] += 1
            ora_pixel_identity_checks["exact_match"] += int(matched)
            ora_pixel_identity_checks["max_abs_px_diff"] = max(ora_pixel_identity_checks["max_abs_px_diff"], mdiff)
        except Exception as exc:
            ora_status = "failed"
            ora_err_msg = str(exc)
            ora_err_cat = classify_ocr_error(ora_err_msg)
        ora_dt = time.perf_counter() - t0
        ora_times.append(ora_dt)

        eval_ora = ev.evaluate_image_sec43(
            image_id=img_id,
            pred_series=ora_pred_series,
            gt_series=gt_series,
            x_ticks_px_val=x_ticks_px_val,
            y_axis_span=y_axis_span,
            run_error=ora_err_cat or ora_err_msg,
        )
        ora_evals.append(eval_ora)

        # Classify joint diagnostic outcome for clean failure attribution
        fpc_gain = eval_ocr.fpc_nrmse - eval_ora.fpc_nrmse
        if not baseline_extraction_ok:
            diag_bucket = "baseline_extraction_empty"
        elif eval_ora.trusted and eval_ora.fpc_nrmse < 0.05 and (not eval_ocr.trusted or eval_ocr.fpc_nrmse >= 0.05):
            diag_bucket = "axis_bottleneck_rescued_cleanly"
        elif eval_ora.trusted and eval_ocr.trusted and eval_ocr.fpc_nrmse < 0.05 and eval_ora.fpc_nrmse < 0.05:
            diag_bucket = "both_arms_already_accurate"
        elif eval_ora.fpc_nrmse < eval_ocr.fpc_nrmse - 0.02:
            diag_bucket = "axis_bottleneck_partial_rescue"
        elif not eval_ora.trusted:
            diag_bucket = "non_axis_tracking_or_coverage_failure"
        else:
            diag_bucket = "non_axis_color_or_curve_error"

        row = {
            "index": idx,
            "base_id": meta["base_id"],
            "image_id": img_id,
            "renderer": meta["renderer"],
            "plot_type": meta["plot_type"],
            "line_count": meta["line_count"],
            "R1_thickness_px": meta["R1_thickness_px"],
            "R2_color": meta["R2_color"],
            "R3_dpi": meta["R3_dpi"],
            "R4_blur": meta["R4_blur"],
            "R5_width_in": meta["R5_width_in"],
            "R7_tick_font_pt": meta["R7_tick_font_pt"],
            "R8_ticks": meta["R8_ticks"],
            "R9_x_range": meta["R9_x_range"],
            "R10_y_range": meta["R10_y_range"],
            "width_px": meta["width_px"],
            "height_px": meta["height_px"],
            "frozen_auto_color_rgb": list(frozen_color) if frozen_color else None,
            "frozen_pixel_count": len(frozen_pixels),
            "baseline_extraction_ok": baseline_extraction_ok,
            "true_axis_values": list(oracle_axis),
            "arm_a_default_ocr": {
                "status": ocr_status,
                "error_category": ocr_err_cat,
                "error_message": ocr_err_msg,
                "ocr_axis_values": ocr_axis_vals,
                "ocr_tick_points": ocr_tick_pts,
                "ocr_confidence": ocr_conf,
                "pixel_path_identical_to_frozen": ocr_px_match,
                "elapsed_s": round(ocr_dt, 4),
                "eval_sec43": asdict(eval_ocr),
            },
            "arm_b_oracle_axis": {
                "status": ora_status,
                "error_category": ora_err_cat,
                "error_message": ora_err_msg,
                "pixel_path_identical_to_frozen": ora_px_match,
                "elapsed_s": round(ora_dt, 4),
                "eval_sec43": asdict(eval_ora),
            },
            "fpc_nrmse_reduction_ocr_minus_oracle": fpc_gain,
            "newly_trusted_by_oracle": bool(eval_ora.trusted and not eval_ocr.trusted),
            "lost_trust_by_oracle": bool(eval_ocr.trusted and not eval_ora.trusted),
            "diagnostic_bucket": diag_bucket,
        }
        per_image_rows.append(row)
        print(
            f"[{idx:02d}/30] {img_id:30s} | {meta['renderer']:10s} {meta['R3_dpi']:3d}dpi {meta['R2_color']:7s} | "
            f"OCR: F={eval_ocr.fpc_nrmse:.4f} T={int(eval_ocr.trusted)} ({ocr_err_cat or 'ok'}) | "
            f"ORA: F={eval_ora.fpc_nrmse:.4f} T={int(eval_ora.trusted)} | dF={fpc_gain:+.4f} [{diag_bucket}]",
            flush=True,
        )

    # Persist per-image JSONL immediately
    jsonl_path = OUT_DIR / "linepilot_stage0_dev30_per_image.jsonl"
    jsonl_path.write_text("\n".join(json.dumps(r) for r in per_image_rows) + "\n", encoding="utf-8")
    jsonl_sha = sha256_file(jsonl_path)

    # Aggregate summaries & paired bootstrap
    sum_ocr = ev.summarize_sec43(ocr_evals)
    sum_ora = ev.summarize_sec43(ora_evals)
    fpc_diffs = np.array([a.fpc_nrmse - b.fpc_nrmse for a, b in zip(ocr_evals, ora_evals)], dtype=np.float64)
    tu_diffs = np.array([int(b.trusted) - int(a.trusted) for a, b in zip(ocr_evals, ora_evals)], dtype=np.float64)

    mean_fpc_red = float(np.mean(fpc_diffs))
    net_new_trusted = int(sum_ora["trusted_count"] - sum_ocr["trusted_count"])
    passes_gate = (mean_fpc_red >= GATE_MIN_FPC_REDUCTION) and (net_new_trusted >= GATE_MIN_NEW_TRUSTED)

    # Renderer & color breakdowns
    by_renderer = {}
    for rend in ["matplotlib", "plotly", "altair"]:
        sub_ocr = [e for e, r in zip(ocr_evals, per_image_rows) if r["renderer"] == rend]
        sub_ora = [e for e, r in zip(ora_evals, per_image_rows) if r["renderer"] == rend]
        s_a, s_b = ev.summarize_sec43(sub_ocr), ev.summarize_sec43(sub_ora)
        by_renderer[rend] = {
            "arm_a_default_ocr": s_a,
            "arm_b_oracle_axis": s_b,
            "fpc_nrmse_reduction": s_a["fpc_nrmse"] - s_b["fpc_nrmse"],
            "net_newly_trusted": s_b["trusted_count"] - s_a["trusted_count"],
        }

    by_color_black = {}
    for label, cond in [
        ("colored_non_black_R2", lambda r: r["R2_color"].lower() != "#000000"),
        ("black_curve_R2_000000", lambda r: r["R2_color"].lower() == "#000000"),
    ]:
        sub_ocr = [e for e, r in zip(ocr_evals, per_image_rows) if cond(r)]
        sub_ora = [e for e, r in zip(ora_evals, per_image_rows) if cond(r)]
        s_a, s_b = ev.summarize_sec43(sub_ocr), ev.summarize_sec43(sub_ora)
        by_color_black[label] = {
            "arm_a_default_ocr": s_a,
            "arm_b_oracle_axis": s_b,
            "fpc_nrmse_reduction": s_a["fpc_nrmse"] - s_b["fpc_nrmse"],
            "net_newly_trusted": s_b["trusted_count"] - s_a["trusted_count"],
        }

    summary = {
        "protocol": "STAGE0_LINEPILOT_PROTOCOL.md",
        "protocol_sha256": protocol_sha,
        "scope_disclosure": (
            "Pinned-code (RayanA07/LinePilot 8fb89a62fb0565290b72ba61cb073d732d8e7578) balanced "
            "SINGLE-line Full diagnostic (N = 30 non-bridge single-line Full base_ids: 10 matplotlib, "
            "10 plotly, 10 altair). Do NOT compare this single-line diagnostic directly with paper "
            "Table 3's DigitizerBench-Full (2,980 images) 0.672 FPC-NRMSE / 38.2% TU."
        ),
        "real_pid": os.getpid(),
        "cpu_only": True,
        "wall_time_s": time.perf_counter() - t_all0,
        "runtime_s": {
            "arm_a_default_ocr_total_s": float(sum(ocr_times)),
            "arm_a_default_ocr_mean_per_img_s": float(np.mean(ocr_times)),
            "arm_b_oracle_axis_total_s": float(sum(ora_times)),
            "arm_b_oracle_axis_mean_per_img_s": float(np.mean(ora_times)),
        },
        "pixel_path_identity_verification": {
            "arm_a_default_ocr": ocr_pixel_identity_checks,
            "arm_b_oracle_axis": ora_pixel_identity_checks,
        },
        "source_and_code_hashes": {
            "upstream_linepilot_commit": "8fb89a62fb0565290b72ba61cb073d732d8e7578",
            "digitizerbench_commit": "8b4a3190d5991414dad92049671de75754dd9f44",
            "PORTABLE_OCR_RECEIPT_json": sha256_file(PROJ / "PORTABLE_OCR_RECEIPT.json"),
            "STAGE0_SINGLE_DEV_30_RECEIPT_json": sha256_file(PROJ / "STAGE0_SINGLE_DEV_30_RECEIPT.json"),
            "STAGE0_PRELAUNCH_FIXTURES_RECEIPT_json": sha256_file(PROJ / "STAGE0_PRELAUNCH_FIXTURES_RECEIPT.json"),
            "eval_digitizerbench_sec43_py": sha256_file(PROJ / "eval_digitizerbench_sec43.py"),
            "run_linepilot_stage0_diagnostic_py": sha256_file(PROJ / "run_linepilot_stage0_diagnostic.py"),
        },
        "overall_sec43_dev30": {
            "arm_a_default_ocr": sum_ocr,
            "arm_b_oracle_axis": sum_ora,
            "paired_fpc_nrmse_reduction_ocr_minus_oracle": mean_fpc_red,
            "paired_fpc_nrmse_reduction_ci95": paired_bootstrap_ci(fpc_diffs),
            "net_newly_trusted_count": net_new_trusted,
            "newly_trusted_count": int(sum(1 for r in per_image_rows if r["newly_trusted_by_oracle"])),
            "lost_trust_count": int(sum(1 for r in per_image_rows if r["lost_trust_by_oracle"])),
            "paired_tu_gain_pp": 100.0 * float(np.mean(tu_diffs)),
            "paired_tu_gain_pp_ci95": [100.0 * x for x in paired_bootstrap_ci(tu_diffs)],
            "n_improved_fpc_gt_0.01": int(np.sum(fpc_diffs > 0.01)),
            "n_worsened_fpc_gt_0.01": int(np.sum(fpc_diffs < -0.01)),
        },
        "by_renderer": by_renderer,
        "by_curve_color_black_vs_colored": by_color_black,
        "arm_a_ocr_error_categories": dict(Counter(r["arm_a_default_ocr"]["error_category"] or "ok" for r in per_image_rows)),
        "diagnostic_buckets": dict(Counter(r["diagnostic_bucket"] for r in per_image_rows)),
        "prespecified_stage0_advance_gate": {
            "criterion": f"Mean FPC-NRMSE reduction >= {GATE_MIN_FPC_REDUCTION:.3f} AND net newly trusted usable plots >= {GATE_MIN_NEW_TRUSTED} (out of 30) under fixed-tracker oracle-axis diagnostic.",
            "observed_fpc_nrmse_reduction": mean_fpc_red,
            "observed_net_newly_trusted": net_new_trusted,
            "passes_advance_gate": passes_gate,
            "recommendation": "PROPOSE_MULTISCALE_OCR_CANDIDATE_PENDING_REVIEW" if passes_gate else "STOP_AXES_NOT_DOMINANT_BOTTLENECK",
        },
        "per_image_jsonl": "linepilot_stage0_dev30_per_image.jsonl",
        "per_image_jsonl_sha256": jsonl_sha,
    }

    sum_path = OUT_DIR / "linepilot_stage0_dev30_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    sum_sha = sha256_file(sum_path)

    print("\n" + "=" * 78)
    print(f"STAGE-0 DONE | PID={summary['real_pid']} | wall={summary['wall_time_s']:.2f}s | summary_sha256={sum_sha}")
    print(f"Arm A (Default OCR)   : FPC-NRMSE={sum_ocr['fpc_nrmse']:.4f} | OS={sum_ocr['output_success_pct']:.1f}% ({sum_ocr['output_success_count']}/30) | TU={sum_ocr['trusted_usability_pct']:.1f}% ({sum_ocr['trusted_count']}/30) | DPPL={sum_ocr['dppl']:.1f}")
    print(f"Arm B (Oracle-Axis)   : FPC-NRMSE={sum_ora['fpc_nrmse']:.4f} | OS={sum_ora['output_success_pct']:.1f}% ({sum_ora['output_success_count']}/30) | TU={sum_ora['trusted_usability_pct']:.1f}% ({sum_ora['trusted_count']}/30) | DPPL={sum_ora['dppl']:.1f}")
    print(f"Oracle Gain           : dFPC={mean_fpc_red:+.4f} (95% CI {summary['overall_sec43_dev30']['paired_fpc_nrmse_reduction_ci95']}), net_newly_trusted={net_new_trusted:+d}")
    print(f"Advance Gate          : {summary['prespecified_stage0_advance_gate']['passes_advance_gate']} -> {summary['prespecified_stage0_advance_gate']['recommendation']}")
    print("Diagnostic buckets    :", summary["diagnostic_buckets"])
    print("OCR error categories  :", summary["arm_a_ocr_error_categories"])


if __name__ == "__main__":
    main()
