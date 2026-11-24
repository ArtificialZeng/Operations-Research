"""
Stage-1 Matched-Budget Dev Engineering Pilot Runner (N = 30 Single-Line Dev Split ONLY).

Locked Protocol: `STAGE1_DEV_PROTOCOL.md`
ZERO held-out images/labels are accessed. ZERO GT inputs are used to generate or choose axes.
GT is used SOLELY inside the exact Paper §4.3 Eq. (1) evaluator (`eval_digitizerbench_sec43.py`).

Paired Arms on IDENTICAL Cached Frozen Pixel Traces (max_abs_px_diff == 0.0 px asserted):
  - Arm A (`A_default_ocr`): Released automatic default (`RayanA07/LinePilot 8fb89a62`), unchanged.
  - Arm B (`B_single_res`):  Stronger fixed paper-inspired single-resolution (1.0x) control
                             (axis ROI + Tesseract PSM6 & PSM11, 8 OCR calls/img, no mandatory
                              snap-to-black, held-out LOTO tick residual agreement + Arm A fallback).
  - Arm C (`C_two_res`):     Matched two-resolution (1.0x + 2.0x) candidate with IDENTICAL ROI,
                             parser, alignment, LOTO fit, acceptance, fallback & 8 OCR calls/img.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
DIGITIZER_DIR = ROOT / "upstream_linepilot" / "Digitizer"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(DIGITIZER_DIR))

from PyQt6 import QtGui, QtWidgets  # noqa: E402
import digitizer_api  # noqa: E402
from UI import DigitizerWindow  # noqa: E402
import eval_digitizerbench_sec43 as ev  # noqa: E402
import stage1_axis_calibration as cal  # noqa: E402


DEV_DIR = ROOT / "data_digitizerbench" / "full_single_dev_30"
OUT_DIR = ROOT / "stage1_dev_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def classify_error(msg: str) -> str:
    m = (msg or "").lower()
    if "snap-to-black" in m or "locate all four axis tick points" in m:
        return "axis_calibration_snap_failed"
    if "same x value" in m or "same y value" in m or "degenerate" in m:
        return "axis_ocr_degenerate_same_endpoint"
    if "did not find all x/y min/max" in m or "axis ocr" in m:
        return "axis_ocr_missing_ticks"
    if "no color" in m or "auto color selection" in m:
        return "auto_color_failed"
    if "no points" in m:
        return "curve_extraction_no_points"
    return "other_runtime_error"


def freeze_baseline_pixel_trace(img_path: Path) -> Tuple[Tuple[int, int, int], np.ndarray]:
    """Run unmodified upstream _auto_select_color + _compute_points (limit_to_calibration=False).
    Uses ZERO ground-truth colors or series."""
    image = QtGui.QImage(str(img_path))
    if image.isNull():
        raise RuntimeError(f"Failed to load image: {img_path}")
    win = DigitizerWindow()
    win.set_image(image)
    if win._selected_color is None:
        raise RuntimeError(f"Upstream _auto_select_color failed on {img_path.name}")
    win._limit_points_to_calib = False
    win._active_color_state().limit_points_to_calib = False
    win._export_selected_color_indices = {win._active_color_index}
    win._compute_points()
    color_rgb = digitizer_api._normalize_color(win._selected_color)
    pts = list(win._active_color_state().points)
    if not pts:
        raise RuntimeError(f"Upstream _compute_points produced 0 pixels on {img_path.name}")
    arr = np.asarray([(float(p.x), float(p.y)) for p in pts], dtype=np.float64)
    return color_rgb, arr


def verify_csv_pixels_identical(csv_path: Path, frozen_px: np.ndarray) -> Tuple[bool, float]:
    df = pd.read_csv(csv_path)
    if "x_px" not in df.columns or "y_px" not in df.columns:
        return False, float("inf")
    got = np.column_stack([df["x_px"].to_numpy(dtype=np.float64), df["y_px"].to_numpy(dtype=np.float64)])
    if got.shape != frozen_px.shape:
        return False, float("inf")
    max_diff = float(np.max(np.abs(got - frozen_px)))
    return max_diff == 0.0, max_diff


def paired_bootstrap_ci(
    diffs: np.ndarray,
    n_boot: int = 10000,
    seed: int = 20261124,
) -> List[float]:
    rng = np.random.default_rng(seed)
    n = diffs.size
    idx = rng.integers(0, n, size=(n_boot, n))
    means = diffs[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return [float(lo), float(hi)]


def run_arm_a(
    img_path: Path,
    arm_out_dir: Path,
    frozen_color: Tuple[int, int, int],
    frozen_pixels: np.ndarray,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    status = "ok"
    err_cat = ""
    err_msg = ""
    pred_axis = None
    pred_ticks = None
    ocr_conf = None
    pred_series: List[ev.CleanSeries] = []
    px_identical: Optional[bool] = None
    max_px_diff: Optional[float] = None
    csv_path_str = None
    try:
        res = digitizer_api.digitize_image(
            pic_dir=img_path,
            limit_to_calibration=False,
            output_dir=arm_out_dir,
        )
        assert res.used_ocr is True, "Arm A must use default OCR"
        pred_axis = [float(v) for v in res.axis_values]
        pred_ticks = [[int(p[0]), int(p[1])] for p in res.tick_points]
        ocr_conf = res.ocr_confidence
        csv_path_str = str(res.csv_path)
        pred_series = ev.load_pred_series_from_csv(res.csv_path)
        matched, mdiff = verify_csv_pixels_identical(Path(res.csv_path), frozen_pixels)
        assert matched and tuple(res.color_rgb) == frozen_color, (
            f"Pixel/color drift in Arm A on {img_path.name}: diff={mdiff}, color={res.color_rgb} vs {frozen_color}"
        )
        px_identical = matched
        max_px_diff = mdiff
    except Exception as exc:
        status = "failed"
        err_msg = str(exc)
        err_cat = classify_error(err_msg)
    total_s = time.perf_counter() - t0
    return {
        "status": status,
        "error_category": err_cat,
        "error_message": err_msg,
        "fallback_used": False,
        "ocr_call_count": 2,
        "predicted_axis_values": pred_axis,
        "predicted_tick_points": pred_ticks,
        "ocr_confidence": ocr_conf,
        "pixel_path_identical_to_frozen": px_identical,
        "max_abs_px_diff": max_px_diff,
        "csv_path": csv_path_str,
        "timing_s": {"total_s": round(total_s, 4)},
        "_pred_series": pred_series,
    }


def run_matched_arm(
    arm_name: str,
    img_path: Path,
    arm_out_dir: Path,
    frozen_color: Tuple[int, int, int],
    frozen_pixels: np.ndarray,
) -> Dict[str, Any]:
    t0 = time.perf_counter()
    prop = cal.calibrate_axes_matched(img_path, arm=arm_name)
    assert prop.ocr_call_count == 8, f"Expected exact 8 OCR calls for {arm_name}, got {prop.ocr_call_count}"

    status = "ok"
    err_cat = ""
    err_msg = ""
    pred_axis = None
    pred_ticks = None
    pred_series: List[ev.CleanSeries] = []
    px_identical: Optional[bool] = None
    max_px_diff: Optional[float] = None
    csv_path_str = None
    fallback_used = prop.use_fallback_arm_a

    t_dig0 = time.perf_counter()
    try:
        if prop.accepted:
            res = digitizer_api.digitize_image(
                pic_dir=img_path,
                tick_points=prop.tick_points,
                axis_values=prop.axis_values,
                limit_to_calibration=False,
                output_dir=arm_out_dir,
            )
            assert res.used_ocr is False, f"{arm_name} accepted proposal must skip upstream OCR"
        else:
            # Deterministic fallback to unmodified released Arm A
            res = digitizer_api.digitize_image(
                pic_dir=img_path,
                limit_to_calibration=False,
                output_dir=arm_out_dir,
            )
            assert res.used_ocr is True, f"{arm_name} fallback must run unmodified Arm A"

        pred_axis = [float(v) for v in res.axis_values]
        pred_ticks = [[int(p[0]), int(p[1])] for p in res.tick_points]
        csv_path_str = str(res.csv_path)
        pred_series = ev.load_pred_series_from_csv(res.csv_path)
        matched, mdiff = verify_csv_pixels_identical(Path(res.csv_path), frozen_pixels)
        assert matched and tuple(res.color_rgb) == frozen_color, (
            f"Pixel/color drift in {arm_name} on {img_path.name}: diff={mdiff}, color={res.color_rgb} vs {frozen_color}"
        )
        px_identical = matched
        max_px_diff = mdiff
    except Exception as exc:
        status = "failed"
        err_msg = str(exc)
        err_cat = classify_error(err_msg)
    dig_s = time.perf_counter() - t_dig0
    total_s = time.perf_counter() - t0

    timing = dict(prop.timing_s)
    timing["digitize_s"] = round(dig_s, 4)
    timing["total_s"] = round(total_s, 4)

    return {
        "status": status,
        "error_category": err_cat,
        "error_message": err_msg,
        "proposal_accepted": prop.accepted,
        "fallback_used": fallback_used,
        "ocr_call_count": prop.ocr_call_count,
        "effective_ocr_calls_incl_fallback": prop.ocr_call_count + (2 if fallback_used else 0),
        "predicted_axis_values": pred_axis,
        "predicted_tick_points": pred_ticks,
        "roi_geometry": prop.roi_geometry,
        "x_fit": prop.x_fit,
        "y_fit": prop.y_fit,
        "pixel_path_identical_to_frozen": px_identical,
        "max_abs_px_diff": max_px_diff,
        "csv_path": csv_path_str,
        "timing_s": timing,
        "_pred_series": pred_series,
    }


def summarize_eval_group(
    evals: List[ev.ImageEvalResult],
    records: List[Dict[str, Any]],
    arm_key: str,
) -> Dict[str, Any]:
    agg = ev.summarize_sec43(evals)
    times = [r[arm_key]["timing_s"]["total_s"] for r in records]
    agg["mean_total_s"] = round(float(statistics.mean(times)), 4)
    agg["median_total_s"] = round(float(statistics.median(times)), 4)
    agg["max_total_s"] = round(float(max(times)), 4)
    agg["total_s"] = round(float(sum(times)), 4)
    if arm_key != "arm_a_default_ocr":
        cal_times = [r[arm_key]["timing_s"]["calibration_total_s"] for r in records]
        ocr_times = [r[arm_key]["timing_s"]["ocr_s"] for r in records]
        agg["mean_calibration_s"] = round(float(statistics.mean(cal_times)), 4)
        agg["mean_ocr_s"] = round(float(statistics.mean(ocr_times)), 4)
        agg["proposal_accepted_count"] = sum(1 for r in records if r[arm_key]["proposal_accepted"])
        agg["fallback_used_count"] = sum(1 for r in records if r[arm_key]["fallback_used"])
        agg["x_accept_reasons"] = dict(Counter(r[arm_key]["x_fit"]["accept_reason"] for r in records))
        agg["y_accept_reasons"] = dict(Counter(r[arm_key]["y_fit"]["accept_reason"] for r in records))
        x_inliers = [r[arm_key]["x_fit"]["n_inliers"] for r in records if r[arm_key]["x_fit"]["accepted"]]
        y_inliers = [r[arm_key]["y_fit"]["n_inliers"] for r in records if r[arm_key]["y_fit"]["accepted"]]
        agg["mean_x_inliers_when_accepted"] = round(float(statistics.mean(x_inliers)), 2) if x_inliers else None
        agg["mean_y_inliers_when_accepted"] = round(float(statistics.mean(y_inliers)), 2) if y_inliers else None
    return agg


def paired_contrast(
    base_evals: List[ev.ImageEvalResult],
    cand_evals: List[ev.ImageEvalResult],
    image_ids: List[str],
) -> Dict[str, Any]:
    f_base = np.asarray([e.fpc_nrmse for e in base_evals], dtype=np.float64)
    f_cand = np.asarray([e.fpc_nrmse for e in cand_evals], dtype=np.float64)
    t_base = np.asarray([1.0 if e.trusted else 0.0 for e in base_evals], dtype=np.float64)
    t_cand = np.asarray([1.0 if e.trusted else 0.0 for e in cand_evals], dtype=np.float64)

    f_red = f_base - f_cand  # positive = cand better (lower FPC-NRMSE)
    tu_diff = t_cand - t_base  # positive = cand newly trusted

    newly_trusted_ids = [iid for iid, d in zip(image_ids, tu_diff) if d > 0.5]
    lost_trust_ids = [iid for iid, d in zip(image_ids, tu_diff) if d < -0.5]
    improved_ids = [iid for iid, d in zip(image_ids, f_red) if d > 0.01]
    worsened_ids = [iid for iid, d in zip(image_ids, f_red) if d < -0.01]

    return {
        "mean_fpc_reduction_base_minus_cand": float(np.mean(f_red)),
        "fpc_reduction_ci95": paired_bootstrap_ci(f_red),
        "median_fpc_reduction": float(np.median(f_red)),
        "net_newly_trusted_count": int(np.sum(tu_diff)),
        "newly_trusted_count": len(newly_trusted_ids),
        "lost_trust_count": len(lost_trust_ids),
        "newly_trusted_ids": newly_trusted_ids,
        "lost_trust_ids": lost_trust_ids,
        "tu_gain_pp": float(100.0 * np.mean(tu_diff)),
        "tu_gain_pp_ci95": [100.0 * x for x in paired_bootstrap_ci(tu_diff)],
        "n_improved_fpc_gt_0.01": len(improved_ids),
        "n_worsened_fpc_gt_0.01": len(worsened_ids),
        "improved_ids": improved_ids,
        "worsened_ids": worsened_ids,
    }


def main() -> None:
    t_wall0 = time.perf_counter()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    _ = app

    receipt = json.loads((ROOT / "STAGE0_SINGLE_DEV_30_RECEIPT.json").read_text(encoding="utf-8"))
    selected_plots = receipt["selected_plots"]
    assert len(selected_plots) == 30, f"Expected 30 locked dev plots, got {len(selected_plots)}"
    assert receipt["overlap_with_untouched_full_base_ids"] == 0

    gt_df = pd.read_parquet(DEV_DIR / "dev_ground_truth_30.parquet")
    tick_df = pd.read_parquet(DEV_DIR / "dev_tick_ground_truth_30.parquet")

    # Pre-index GT by image_id (SOLELY for evaluation)
    gt_by_id: Dict[str, List[ev.CleanSeries]] = {}
    curve_yspan_by_id: Dict[str, float] = {}
    for img_id, grp in gt_df.groupby("image_id", sort=False):
        series_list: List[ev.CleanSeries] = []
        for _, lgrp in grp.groupby("line_id", sort=True):
            lgrp_s = lgrp.sort_values("sample_index") if "sample_index" in lgrp.columns else lgrp
            cs = ev.clean_xy_series(lgrp_s["x"].to_numpy(), lgrp_s["y"].to_numpy())
            if cs is not None:
                series_list.append(cs)
        gt_by_id[str(img_id)] = series_list
        curve_yspan_by_id[str(img_id)] = float(grp["y"].max() - grp["y"].min())

    tick_by_id: Dict[str, pd.DataFrame] = {
        str(img_id): tgrp for img_id, tgrp in tick_df.groupby("image_id", sort=False)
    }

    records: List[Dict[str, Any]] = []
    evals_a: List[ev.ImageEvalResult] = []
    evals_b: List[ev.ImageEvalResult] = []
    evals_c: List[ev.ImageEvalResult] = []

    evals_a_curve: List[ev.ImageEvalResult] = []
    evals_b_curve: List[ev.ImageEvalResult] = []
    evals_c_curve: List[ev.ImageEvalResult] = []

    px_checks: Dict[str, Dict[str, Any]] = {
        "arm_a_default_ocr": {"checked": 0, "exact_match": 0, "max_abs_px_diff": 0.0},
        "arm_b_single_res": {"checked": 0, "exact_match": 0, "max_abs_px_diff": 0.0},
        "arm_c_two_res": {"checked": 0, "exact_match": 0, "max_abs_px_diff": 0.0},
    }

    csv_root = OUT_DIR / "csv_artifacts"
    csv_root.mkdir(parents=True, exist_ok=True)

    for idx, meta in enumerate(selected_plots, start=1):
        img_id = meta["image_id"]
        img_path = DEV_DIR / meta["image_path"]
        assert img_path.is_file(), f"Missing dev image: {img_path}"

        # Evaluator-only GT metadata
        t_sub = tick_by_id[img_id]
        tx = t_sub[t_sub["axis"] == "x"].sort_values("tick_value")
        ty = t_sub[t_sub["axis"] == "y"].sort_values("tick_value")
        x_ticks_px_val = (
            float(tx["pixel_x"].iloc[0]),
            float(tx["pixel_x"].iloc[-1]),
            float(tx["tick_value"].iloc[0]),
            float(tx["tick_value"].iloc[-1]),
        )
        y_axis_span = float(ty["tick_value"].iloc[-1]) - float(ty["tick_value"].iloc[0])
        true_axis_values = [
            float(tx["tick_value"].iloc[0]),
            float(tx["tick_value"].iloc[-1]),
            float(ty["tick_value"].iloc[0]),
            float(ty["tick_value"].iloc[-1]),
        ]
        gt_series = gt_by_id[img_id]
        curve_span_eff = curve_yspan_by_id[img_id] if curve_yspan_by_id[img_id] > 0.0 else y_axis_span

        # 0. Freeze baseline pixel trace ONCE (zero GT)
        frozen_color, frozen_pixels = freeze_baseline_pixel_trace(img_path)

        # 1. Run Arm A, Arm B, Arm C (all strictly image-only, zero GT)
        out_a = run_arm_a(img_path, csv_root / "arm_a" / img_id, frozen_color, frozen_pixels)
        out_b = run_matched_arm("B_single_res", img_path, csv_root / "arm_b" / img_id, frozen_color, frozen_pixels)
        out_c = run_matched_arm("C_two_res", img_path, csv_root / "arm_c" / img_id, frozen_color, frozen_pixels)

        # Track pixel-path identity across every valid arm output
        for arm_key, arm_out in (
            ("arm_a_default_ocr", out_a),
            ("arm_b_single_res", out_b),
            ("arm_c_two_res", out_c),
        ):
            if arm_out["pixel_path_identical_to_frozen"] is not None:
                px_checks[arm_key]["checked"] += 1
                px_checks[arm_key]["exact_match"] += int(bool(arm_out["pixel_path_identical_to_frozen"]))
                px_checks[arm_key]["max_abs_px_diff"] = max(
                    px_checks[arm_key]["max_abs_px_diff"],
                    float(arm_out["max_abs_px_diff"]),
                )

        # 2. Evaluate strictly with exact Paper §4.3 Eq. (1) scorer (primary y_axis_span + curve-span sensitivity)
        ev_a = ev.evaluate_image_sec43(img_id, out_a.pop("_pred_series"), gt_series, x_ticks_px_val, y_axis_span=y_axis_span, run_error=out_a["error_category"] or out_a["error_message"])
        ev_b = ev.evaluate_image_sec43(img_id, out_b.pop("_pred_series"), gt_series, x_ticks_px_val, y_axis_span=y_axis_span, run_error=out_b["error_category"] or out_b["error_message"])
        ev_c = ev.evaluate_image_sec43(img_id, out_c.pop("_pred_series"), gt_series, x_ticks_px_val, y_axis_span=y_axis_span, run_error=out_c["error_category"] or out_c["error_message"])

        # Curve-span sensitivity (re-load pred series cleanly from saved CSV if produced)
        ps_a = ev.load_pred_series_from_csv(out_a["csv_path"]) if out_a["csv_path"] else []
        ps_b = ev.load_pred_series_from_csv(out_b["csv_path"]) if out_b["csv_path"] else []
        ps_c = ev.load_pred_series_from_csv(out_c["csv_path"]) if out_c["csv_path"] else []
        ev_a_cu = ev.evaluate_image_sec43(img_id, ps_a, gt_series, x_ticks_px_val, y_axis_span=curve_span_eff, run_error=out_a["error_category"] or out_a["error_message"])
        ev_b_cu = ev.evaluate_image_sec43(img_id, ps_b, gt_series, x_ticks_px_val, y_axis_span=curve_span_eff, run_error=out_b["error_category"] or out_b["error_message"])
        ev_c_cu = ev.evaluate_image_sec43(img_id, ps_c, gt_series, x_ticks_px_val, y_axis_span=curve_span_eff, run_error=out_c["error_category"] or out_c["error_message"])

        evals_a.append(ev_a)
        evals_b.append(ev_b)
        evals_c.append(ev_c)
        evals_a_curve.append(ev_a_cu)
        evals_b_curve.append(ev_b_cu)
        evals_c_curve.append(ev_c_cu)

        out_a["eval_sec43"] = asdict(ev_a)
        out_b["eval_sec43"] = asdict(ev_b)
        out_c["eval_sec43"] = asdict(ev_c)

        rec = {
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
            "frozen_auto_color_rgb": list(frozen_color),
            "frozen_pixel_count": int(frozen_pixels.shape[0]),
            "true_axis_values": true_axis_values,
            "arm_a_default_ocr": out_a,
            "arm_b_single_res": out_b,
            "arm_c_two_res": out_c,
            "delta_fpc_a_minus_b": round(ev_a.fpc_nrmse - ev_b.fpc_nrmse, 6),
            "delta_fpc_a_minus_c": round(ev_a.fpc_nrmse - ev_c.fpc_nrmse, 6),
            "delta_fpc_b_minus_c": round(ev_b.fpc_nrmse - ev_c.fpc_nrmse, 6),
        }
        records.append(rec)
        print(
            f"[{idx:02d}/30] {img_id:28s} dpi={meta['R3_dpi']:3d} "
            f"A={ev_a.fpc_nrmse:.4f}(T={int(ev_a.trusted)}) "
            f"B={ev_b.fpc_nrmse:.4f}(T={int(ev_b.trusted)},acc={int(out_b['proposal_accepted'])},{out_b['timing_s']['total_s']:.2f}s) "
            f"C={ev_c.fpc_nrmse:.4f}(T={int(ev_c.trusted)},acc={int(out_c['proposal_accepted'])},{out_c['timing_s']['total_s']:.2f}s) "
            f"B-C={ev_b.fpc_nrmse - ev_c.fpc_nrmse:+.4f}",
            flush=True,
        )

    wall_s = time.perf_counter() - t_wall0

    # Write per-image JSONL
    jsonl_path = OUT_DIR / "stage1_dev30_per_image.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")
    jsonl_sha = sha256_file(jsonl_path)

    image_ids = [r["image_id"] for r in records]
    c_vs_b = paired_contrast(evals_b, evals_c, image_ids)
    b_vs_a = paired_contrast(evals_a, evals_b, image_ids)
    c_vs_a = paired_contrast(evals_a, evals_c, image_ids)

    # Breakdowns
    by_renderer: Dict[str, Any] = {}
    for rend in ("matplotlib", "plotly", "altair"):
        idxs = [i for i, r in enumerate(records) if r["renderer"] == rend]
        sub_r = [records[i] for i in idxs]
        sub_a = [evals_a[i] for i in idxs]
        sub_b = [evals_b[i] for i in idxs]
        sub_c = [evals_c[i] for i in idxs]
        by_renderer[rend] = {
            "arm_a_default_ocr": summarize_eval_group(sub_a, sub_r, "arm_a_default_ocr"),
            "arm_b_single_res": summarize_eval_group(sub_b, sub_r, "arm_b_single_res"),
            "arm_c_two_res": summarize_eval_group(sub_c, sub_r, "arm_c_two_res"),
            "b_minus_c_fpc": round(ev.summarize_sec43(sub_b)["fpc_nrmse"] - ev.summarize_sec43(sub_c)["fpc_nrmse"], 6),
            "c_minus_b_trusted": ev.summarize_sec43(sub_c)["trusted_count"] - ev.summarize_sec43(sub_b)["trusted_count"],
        }

    by_dpi_bucket: Dict[str, Any] = {}
    for label, cond in (("low_dpi_le_150", lambda r: r["R3_dpi"] <= 150), ("high_dpi_ge_300", lambda r: r["R3_dpi"] >= 300)):
        idxs = [i for i, r in enumerate(records) if cond(r)]
        sub_r = [records[i] for i in idxs]
        sub_a = [evals_a[i] for i in idxs]
        sub_b = [evals_b[i] for i in idxs]
        sub_c = [evals_c[i] for i in idxs]
        by_dpi_bucket[label] = {
            "n_images": len(idxs),
            "arm_a_fpc": ev.summarize_sec43(sub_a)["fpc_nrmse"],
            "arm_b_fpc": ev.summarize_sec43(sub_b)["fpc_nrmse"],
            "arm_c_fpc": ev.summarize_sec43(sub_c)["fpc_nrmse"],
            "arm_a_tu_count": ev.summarize_sec43(sub_a)["trusted_count"],
            "arm_b_tu_count": ev.summarize_sec43(sub_b)["trusted_count"],
            "arm_c_tu_count": ev.summarize_sec43(sub_c)["trusted_count"],
            "b_minus_c_fpc": round(ev.summarize_sec43(sub_b)["fpc_nrmse"] - ev.summarize_sec43(sub_c)["fpc_nrmse"], 6),
            "c_minus_b_trusted": ev.summarize_sec43(sub_c)["trusted_count"] - ev.summarize_sec43(sub_b)["trusted_count"],
        }

    by_color: Dict[str, Any] = {}
    for label, cond in (("colored_non_black_R2", lambda r: r["R2_color"] != "#000000"), ("black_curve_R2_000000", lambda r: r["R2_color"] == "#000000")):
        idxs = [i for i, r in enumerate(records) if cond(r)]
        sub_r = [records[i] for i in idxs]
        sub_a = [evals_a[i] for i in idxs]
        sub_b = [evals_b[i] for i in idxs]
        sub_c = [evals_c[i] for i in idxs]
        by_color[label] = {
            "n_images": len(idxs),
            "arm_a_fpc": ev.summarize_sec43(sub_a)["fpc_nrmse"],
            "arm_b_fpc": ev.summarize_sec43(sub_b)["fpc_nrmse"],
            "arm_c_fpc": ev.summarize_sec43(sub_c)["fpc_nrmse"],
            "arm_b_tu_count": ev.summarize_sec43(sub_b)["trusted_count"],
            "arm_c_tu_count": ev.summarize_sec43(sub_c)["trusted_count"],
        }

    # Pre-locked Stage-1 dev advancement gate (C over B)
    fpc_gain_c_over_b = c_vs_b["mean_fpc_reduction_base_minus_cand"]
    tu_gain_c_over_b = c_vs_b["net_newly_trusted_count"]
    ci_lo_c_over_b = c_vs_b["fpc_reduction_ci95"][0]
    worst_renderer_delta = min(by_renderer[r]["b_minus_c_fpc"] for r in ("matplotlib", "plotly", "altair"))
    passes_fpc = fpc_gain_c_over_b >= 0.050
    passes_tu = tu_gain_c_over_b >= 2
    passes_ci = ci_lo_c_over_b > 0.0
    no_serious_renderer_reg = worst_renderer_delta >= -0.050

    if passes_fpc and passes_tu and passes_ci and no_serious_renderer_reg:
        gate_decision = "PASS_DEV_MATERIAL_MULTISCALE_GAIN_PENDING_HELDOUT_APPROVAL"
    elif b_vs_a["mean_fpc_reduction_base_minus_cand"] >= 0.40 and not (passes_fpc and passes_tu):
        gate_decision = "SAME_VIEW_GEOMETRY_CAPTURED_GAIN_NO_MATERIAL_MULTISCALE_GAIN"
    else:
        gate_decision = "NO_MATERIAL_MULTISCALE_GAIN_OVER_CONTROL"

    summary = {
        "protocol": "STAGE1_DEV_PROTOCOL.md",
        "protocol_sha256": sha256_file(ROOT / "STAGE1_DEV_PROTOCOL.md"),
        "scope_disclosure": "Stage-1 CPU-only matched-budget dev engineering pilot on N = 30 locked single-line non-bridge dev plots ONLY. ZERO held-out images/labels accessed. Single-slot pinned-code (8fb89a62) diagnostic; NOT directly comparable to Paper Table 3 Full 0.672.",
        "real_pid": os.getpid(),
        "cpu_only": True,
        "wall_time_s": round(wall_s, 4),
        "ocr_call_budget_verified": {
            "arm_a_calls_per_image": 2,
            "arm_b_calls_per_image": 8,
            "arm_c_calls_per_image": 8,
            "b_and_c_equal_budget": True,
        },
        "pixel_path_identity_verification": px_checks,
        "source_and_code_hashes": {
            "upstream_linepilot_commit": "8fb89a62fb0565290b72ba61cb073d732d8e7578",
            "digitizerbench_commit": "8b4a3190d5991414dad92049671de75754dd9f44",
            "STAGE0_LINEPILOT_PROTOCOL_md": sha256_file(ROOT / "STAGE0_LINEPILOT_PROTOCOL.md"),
            "STAGE1_DEV_PROTOCOL_md": sha256_file(ROOT / "STAGE1_DEV_PROTOCOL.md"),
            "PORTABLE_OCR_RECEIPT_json": sha256_file(ROOT / "PORTABLE_OCR_RECEIPT.json"),
            "STAGE0_SINGLE_DEV_30_RECEIPT_json": sha256_file(ROOT / "STAGE0_SINGLE_DEV_30_RECEIPT.json"),
            "eval_digitizerbench_sec43_py": sha256_file(ROOT / "eval_digitizerbench_sec43.py"),
            "stage1_axis_calibration_py": sha256_file(ROOT / "stage1_axis_calibration.py"),
            "run_stage1_dev_pilot_py": sha256_file(ROOT / "run_stage1_dev_pilot.py"),
        },
        "overall_sec43_dev30": {
            "arm_a_default_ocr": summarize_eval_group(evals_a, records, "arm_a_default_ocr"),
            "arm_b_single_res": summarize_eval_group(evals_b, records, "arm_b_single_res"),
            "arm_c_two_res": summarize_eval_group(evals_c, records, "arm_c_two_res"),
        },
        "denominator_sensitivity_curve_span_with_zero_fallback": {
            "arm_a_fpc": ev.summarize_sec43(evals_a_curve)["fpc_nrmse"],
            "arm_b_fpc": ev.summarize_sec43(evals_b_curve)["fpc_nrmse"],
            "arm_c_fpc": ev.summarize_sec43(evals_c_curve)["fpc_nrmse"],
            "b_minus_c_fpc": ev.summarize_sec43(evals_b_curve)["fpc_nrmse"] - ev.summarize_sec43(evals_c_curve)["fpc_nrmse"],
        },
        "paired_contrasts": {
            "B_vs_A": b_vs_a,
            "C_vs_A": c_vs_a,
            "C_vs_B_primary": c_vs_b,
        },
        "by_renderer": by_renderer,
        "by_dpi_bucket": by_dpi_bucket,
        "by_curve_color": by_color,
        "prespecified_dev_gate_C_over_B": {
            "criterion": "FPC_B - FPC_C >= 0.050 AND net newly trusted TU_C - TU_B >= 2 AND 95% CI > 0 AND no serious renderer regression (worst renderer B-C >= -0.050).",
            "observed_fpc_reduction_B_minus_C": fpc_gain_c_over_b,
            "observed_fpc_ci95": c_vs_b["fpc_reduction_ci95"],
            "observed_net_newly_trusted_C_minus_B": tu_gain_c_over_b,
            "worst_renderer_B_minus_C": worst_renderer_delta,
            "passes_fpc_ge_0.05": passes_fpc,
            "passes_tu_ge_2": passes_tu,
            "passes_ci_gt_0": passes_ci,
            "passes_no_serious_renderer_reg": no_serious_renderer_reg,
            "decision": gate_decision,
        },
        "per_image_jsonl": jsonl_path.name,
        "per_image_jsonl_sha256": jsonl_sha,
    }

    summary_path = OUT_DIR / "stage1_dev30_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary_sha = sha256_file(summary_path)

    print("\n=== STAGE-1 DEV PILOT COMPLETE ===")
    print(f"PID = {os.getpid()} | Wall = {wall_s:.2f} s | Summary SHA = {summary_sha}")
    print(
        f"Arm A (Default OCR): FPC={summary['overall_sec43_dev30']['arm_a_default_ocr']['fpc_nrmse']:.6f}, "
        f"TU={summary['overall_sec43_dev30']['arm_a_default_ocr']['trusted_count']}/30, "
        f"mean_t={summary['overall_sec43_dev30']['arm_a_default_ocr']['mean_total_s']:.3f}s"
    )
    print(
        f"Arm B (1.0x Control): FPC={summary['overall_sec43_dev30']['arm_b_single_res']['fpc_nrmse']:.6f}, "
        f"TU={summary['overall_sec43_dev30']['arm_b_single_res']['trusted_count']}/30, "
        f"mean_t={summary['overall_sec43_dev30']['arm_b_single_res']['mean_total_s']:.3f}s"
    )
    print(
        f"Arm C (1x+2x Matched): FPC={summary['overall_sec43_dev30']['arm_c_two_res']['fpc_nrmse']:.6f}, "
        f"TU={summary['overall_sec43_dev30']['arm_c_two_res']['trusted_count']}/30, "
        f"mean_t={summary['overall_sec43_dev30']['arm_c_two_res']['mean_total_s']:.3f}s"
    )
    print(
        f"PRIMARY C vs B: FPC reduction={fpc_gain_c_over_b:+.6f} "
        f"(CI95=[{c_vs_b['fpc_reduction_ci95'][0]:+.4f}, {c_vs_b['fpc_reduction_ci95'][1]:+.4f}]), "
        f"net TU={tu_gain_c_over_b:+d}, improved={c_vs_b['n_improved_fpc_gt_0.01']}, worsened={c_vs_b['n_worsened_fpc_gt_0.01']}"
    )
    print(f"GATE DECISION: {gate_decision}")


if __name__ == "__main__":
    main()
