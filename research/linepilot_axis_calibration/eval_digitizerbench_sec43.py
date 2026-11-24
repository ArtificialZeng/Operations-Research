"""
Exact Paper Section 4.3 Evaluation Metrics for DigitizerBench (`arXiv:2609.19377v1` §4.3):
  - Failure-penalized capped normalized RMSE (`FPC-NRMSE`, Eq. 1)
  - Output Success (`OS`, %)
  - Trusted Usability (`TU`, %)
  - Digitized Points Per Line (`DPPL`)

Explicitly distinct from `AccuracyTester/accuracy_batch_cli.py` (which scores only a single
color slot on `original_x` with no Hungarian matching, no coverage/count trust gate, and no
unit-loss failure penalty).

Exact §4.3 rules implemented:
  1. Each predicted series and GT series is cleaned (finite numeric, sorted ascending by x,
     duplicate x collapsed by median, matching `accuracy_core.prepare_series`).
  2. For each candidate (pred, gt) line pair, interpolate BOTH without extrapolation on their
     shared x-range [x_lo, x_hi] at 1 sample per horizontal plot pixel:
         W_i = |x_px_max_tick - x_px_min_tick|   (endpoint-tick plot width in pixels)
         px_per_x = W_i / (x_val_max_tick - x_val_min_tick)
         K_{i,l} = int(round((x_hi - x_lo) * px_per_x))   (0 if x_hi <= x_lo or < 2)
         C_{i,l} = min(1.0, K_{i,l} / W_i)
  3. Per-line NRMSE:
         e_{i,l} = sqrt(mean((y_hat - y_gt)^2)) / (y_{i,max} - y_{i,min})
     where y_{i,max} - y_{i,min} is the image-level GT y-span across all GT lines in image i.
  4. Hungarian matching (`scipy.optimize.linear_sum_assignment`) minimizes:
         cost(p, g) = min(e_{p,g}, 1.0) + (1.0 - C_{p,g})   (2.0 if non-overlapping/invalid).
  5. Trusted usability T_i = 1 ONLY IF:
       - predicted line count == ground-truth line count G_i, AND
       - every matched pair l in 1..G_i has finite e_{i,l}, >= 20 valid coordinate pairs
         (both K_{i,l} >= 20 and raw predicted unique points >= 20), and C_{i,l} >= 0.800.
  6. Image-level FPC-NRMSE:
         e_bar_i = mean_{l=1..G_i}(e_{i,l})
         F_i = e_bar_i if (T_i == 1 and e_bar_i < 1.0) else 1.0.
     Dataset FPC-NRMSE averages F_i over ALL N images (keeping every failure at unit loss 1.0).
"""
from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from scipy.optimize import linear_sum_assignment


@dataclass(frozen=True)
class CleanSeries:
    x: np.ndarray
    y: np.ndarray
    n_valid_raw: int
    n_unique: int


@dataclass(frozen=True)
class ImageEvalResult:
    image_id: str
    gt_line_count: int
    pred_line_count: int
    output_success: bool
    trusted: bool
    fpc_nrmse: float
    mean_matched_nrmse: Optional[float]
    min_matched_coverage: float
    min_matched_grid_k: int
    mean_points_per_pred_line: Optional[float]
    endpoint_tick_width_px: float
    gt_y_span: float
    failure_reason: str


def clean_xy_series(xs: Sequence[float], ys: Sequence[float]) -> Optional[CleanSeries]:
    x_arr = np.asarray(xs, dtype=np.float64)
    y_arr = np.asarray(ys, dtype=np.float64)
    mask = np.isfinite(x_arr) & np.isfinite(y_arr)
    x_arr = x_arr[mask]
    y_arr = y_arr[mask]
    n_valid = int(x_arr.size)
    if n_valid == 0:
        return None
    order = np.argsort(x_arr, kind="mergesort")
    x_arr = x_arr[order]
    y_arr = y_arr[order]
    uniq_x, idx_start, counts = np.unique(x_arr, return_index=True, return_counts=True)
    if uniq_x.size == x_arr.size:
        uniq_y = y_arr
    else:
        uniq_y = np.empty(uniq_x.size, dtype=np.float64)
        for i, (st, cnt) in enumerate(zip(idx_start, counts)):
            uniq_y[i] = float(np.median(y_arr[st : st + cnt]))
    return CleanSeries(x=uniq_x, y=uniq_y, n_valid_raw=n_valid, n_unique=int(uniq_x.size))


def load_pred_series_from_csv(csv_path: str) -> List[CleanSeries]:
    df = pd.read_csv(csv_path)
    if df.empty or "x" not in df.columns or "y" not in df.columns:
        return []
    series_list: List[CleanSeries] = []
    if "color_slot" in df.columns:
        for _, grp in df.groupby("color_slot", sort=True):
            cs = clean_xy_series(grp["x"].to_numpy(), grp["y"].to_numpy())
            if cs is not None:
                series_list.append(cs)
    else:
        cs = clean_xy_series(df["x"].to_numpy(), df["y"].to_numpy())
        if cs is not None:
            series_list.append(cs)
    return series_list


def evaluate_image_sec43(
    image_id: str,
    pred_series: List[CleanSeries],
    gt_series: List[CleanSeries],
    x_ticks_px_val: Tuple[float, float, float, float],
    y_axis_span: Optional[float] = None,
    run_error: str = "",
) -> ImageEvalResult:
    """
    `x_ticks_px_val = (x_px_min, x_px_max, x_val_min, x_val_max)` from `tick_ground_truth.parquet`.
    `y_axis_span = y_tick_max - y_tick_min` (image-level y-axis span `y_{i,max} - y_{i,min}` from
    `tick_ground_truth.parquet`, required for flat zero-span GT curves where `max(GT y) == min(GT y)`).
    If `y_axis_span` is omitted, falls back to GT curve span when > 0.
    """
    x_px_min, x_px_max, x_val_min, x_val_max = x_ticks_px_val
    w_i = abs(float(x_px_max) - float(x_px_min))
    x_val_span = float(x_val_max) - float(x_val_min)
    assert w_i > 0.0 and x_val_span > 0.0, f"Invalid tick span for {image_id}"
    px_per_x = w_i / x_val_span

    g_i = len(gt_series)
    all_gt_y = np.concatenate([g.y for g in gt_series])
    gt_curve_y_span = float(np.max(all_gt_y) - np.min(all_gt_y))
    y_span = float(y_axis_span) if (y_axis_span is not None and y_axis_span > 0.0) else gt_curve_y_span
    assert y_span > 0.0, f"Zero y-span denominator for {image_id}"

    n_pred = len(pred_series)
    output_success = n_pred >= 1 and all(p.n_valid_raw >= 1 for p in pred_series)
    if not output_success:
        return ImageEvalResult(
            image_id=image_id,
            gt_line_count=g_i,
            pred_line_count=0,
            output_success=False,
            trusted=False,
            fpc_nrmse=1.0,
            mean_matched_nrmse=None,
            min_matched_coverage=0.0,
            min_matched_grid_k=0,
            mean_points_per_pred_line=None,
            endpoint_tick_width_px=w_i,
            gt_y_span=y_span,
            failure_reason=run_error or "no_valid_output",
        )

    dppl_img = float(np.mean([p.n_valid_raw for p in pred_series]))

    # Pairwise cost matrix [n_pred, g_i]: min(e_{p,g}, 1) + (1 - C_{p,g})
    e_mat = np.full((n_pred, g_i), np.inf, dtype=np.float64)
    c_mat = np.zeros((n_pred, g_i), dtype=np.float64)
    k_mat = np.zeros((n_pred, g_i), dtype=np.int64)
    cost_mat = np.full((n_pred, g_i), 2.0, dtype=np.float64)

    for pi, ps in enumerate(pred_series):
        if ps.n_unique < 2:
            continue
        for gi, gs in enumerate(gt_series):
            if gs.n_unique < 2:
                continue
            x_lo = max(float(ps.x[0]), float(gs.x[0]))
            x_hi = min(float(ps.x[-1]), float(gs.x[-1]))
            if x_hi <= x_lo:
                continue
            k_grid = int(round((x_hi - x_lo) * px_per_x))
            if k_grid < 2:
                continue
            x_grid = np.linspace(x_lo, x_hi, k_grid, dtype=np.float64)
            y_hat = np.interp(x_grid, ps.x, ps.y)
            y_gt = np.interp(x_grid, gs.x, gs.y)
            rmse = float(np.sqrt(np.mean((y_hat - y_gt) ** 2)))
            e_val = rmse / y_span
            c_val = min(1.0, float(k_grid) / w_i)
            e_mat[pi, gi] = e_val
            c_mat[pi, gi] = c_val
            k_mat[pi, gi] = k_grid
            cost_mat[pi, gi] = min(e_val, 1.0) + (1.0 - c_val)

    row_ind, col_ind = linear_sum_assignment(cost_mat)
    matched_e = [float(e_mat[r, c]) for r, c in zip(row_ind, col_ind)]
    matched_c = [float(c_mat[r, c]) for r, c in zip(row_ind, col_ind)]
    matched_k = [int(k_mat[r, c]) for r, c in zip(row_ind, col_ind)]
    matched_pred_raw = [int(pred_series[r].n_valid_raw) for r in row_ind]

    # Check exact §4.3 trust gate T_i = 1
    reasons: List[str] = []
    if n_pred != g_i:
        reasons.append(f"line_count_mismatch(pred={n_pred},gt={g_i})")
    if not matched_e or any(not math.isfinite(ev) for ev in matched_e):
        reasons.append("nonfinite_or_nonoverlapping_match")
    if not matched_k or any(kv < 20 for kv in matched_k) or any(rv < 20 for rv in matched_pred_raw):
        reasons.append(f"fewer_than_20_valid_pairs(min_k={min(matched_k) if matched_k else 0})")
    if not matched_c or any(cv < 0.800 for cv in matched_c):
        reasons.append(f"coverage_below_0.800(min_c={min(matched_c) if matched_c else 0.0:.3f})")

    trusted = len(reasons) == 0
    finite_es = [ev for ev in matched_e if math.isfinite(ev)]
    e_bar = float(np.mean(matched_e)) if (len(matched_e) == g_i and len(finite_es) == g_i) else None

    if trusted and e_bar is not None and e_bar < 1.0:
        f_i = e_bar
        fail_str = ""
    else:
        f_i = 1.0
        if trusted and e_bar is not None and e_bar >= 1.0:
            reasons.append(f"capped_unit_error(e_bar={e_bar:.4f})")
        fail_str = ";".join(reasons)

    return ImageEvalResult(
        image_id=image_id,
        gt_line_count=g_i,
        pred_line_count=n_pred,
        output_success=True,
        trusted=trusted,
        fpc_nrmse=f_i,
        mean_matched_nrmse=e_bar,
        min_matched_coverage=min(matched_c) if matched_c else 0.0,
        min_matched_grid_k=min(matched_k) if matched_k else 0,
        mean_points_per_pred_line=dppl_img,
        endpoint_tick_width_px=w_i,
        gt_y_span=y_span,
        failure_reason=fail_str,
    )


def summarize_sec43(results: List[ImageEvalResult]) -> Dict[str, Any]:
    n = len(results)
    if n == 0:
        return {"n_images": 0}
    fpc = float(np.mean([r.fpc_nrmse for r in results]))
    os_pct = 100.0 * sum(1 for r in results if r.output_success) / n
    tu_pct = 100.0 * sum(1 for r in results if r.trusted) / n
    dppl_vals = [r.mean_points_per_pred_line for r in results if r.output_success and r.mean_points_per_pred_line is not None]
    dppl = float(np.mean(dppl_vals)) if dppl_vals else 0.0
    return {
        "n_images": n,
        "fpc_nrmse": fpc,
        "output_success_pct": os_pct,
        "output_success_count": sum(1 for r in results if r.output_success),
        "trusted_usability_pct": tu_pct,
        "trusted_count": sum(1 for r in results if r.trusted),
        "dppl": dppl,
    }


def run_unit_fixtures() -> Dict[str, Any]:
    """Synthetic self-verification of every Paper §4.3 clause."""
    xs = np.linspace(0.0, 10.0, 500)
    y1 = np.sin(xs)
    y2 = np.cos(xs) + 3.0
    gt1 = [clean_xy_series(xs, y1)]
    gt2 = [clean_xy_series(xs, y1), clean_xy_series(xs, y2)]
    ticks = (100.0, 600.0, 0.0, 10.0)  # W_i = 500 px

    # 1. Exact recovery
    r_exact = evaluate_image_sec43("f_exact", [clean_xy_series(xs, y1)], gt1, ticks)
    assert r_exact.trusted and r_exact.fpc_nrmse < 1e-12 and abs(r_exact.min_matched_coverage - 1.0) < 1e-9

    # 2. Failed/empty output -> unit loss 1.0, OS=False, TU=False
    r_fail = evaluate_image_sec43("f_fail", [], gt1, ticks, run_error="ocr_failed")
    assert (not r_fail.output_success) and (not r_fail.trusted) and r_fail.fpc_nrmse == 1.0

    # 3. Wrong line count (1 pred vs 2 GT) -> OS=True, TU=False, F_i=1.0
    r_cnt = evaluate_image_sec43("f_cnt", [clean_xy_series(xs, y1)], gt2, ticks)
    assert r_cnt.output_success and (not r_cnt.trusted) and r_cnt.fpc_nrmse == 1.0

    # 4. Coverage 0.75 < 0.80 -> TU=False, F_i=1.0
    xs_short = np.linspace(0.0, 7.5, 375)
    r_cov = evaluate_image_sec43("f_cov", [clean_xy_series(xs_short, np.sin(xs_short))], gt1, ticks)
    assert r_cov.output_success and (not r_cov.trusted) and r_cov.fpc_nrmse == 1.0

    # 5. Coverage 0.82 >= 0.80 -> TU=True, F_i ~ 0
    xs_ok = np.linspace(0.0, 8.2, 410)
    r_ok = evaluate_image_sec43("f_ok", [clean_xy_series(xs_ok, np.sin(xs_ok))], gt1, ticks)
    assert r_ok.trusted and r_ok.fpc_nrmse < 1e-3 and r_ok.min_matched_coverage >= 0.800

    # 6. <20 points -> TU=False, F_i=1.0
    xs_few = np.linspace(0.0, 10.0, 15)
    r_few = evaluate_image_sec43("f_few", [clean_xy_series(xs_few, np.sin(xs_few))], gt1, ticks)
    assert (not r_few.trusted) and r_few.fpc_nrmse == 1.0

    # 7. Hungarian permutation invariance on 2-line plot (reversed order!)
    r_perm = evaluate_image_sec43("f_perm", [clean_xy_series(xs, y2 + 0.02), clean_xy_series(xs, y1 - 0.02)], gt2, ticks)
    assert r_perm.trusted and 0.0 < r_perm.fpc_nrmse < 0.02

    # 8. Capped error > 1.0 even when trusted -> F_i = 1.0 (while TU=True!)
    r_cap = evaluate_image_sec43("f_cap", [clean_xy_series(xs, y1 + 10.0)], gt1, ticks)
    assert r_cap.trusted and r_cap.mean_matched_nrmse > 1.0 and r_cap.fpc_nrmse == 1.0

    # 9. Flat zero-span GT curve (`zero_span_confinement=True`) normalized by image y-axis span
    y_flat = np.full_like(xs, 0.5)
    r_flat = evaluate_image_sec43("f_flat", [clean_xy_series(xs, y_flat + 0.01)], [clean_xy_series(xs, y_flat)], ticks, y_axis_span=2.0)
    assert r_flat.trusted and abs(r_flat.fpc_nrmse - 0.005) < 1e-9

    return {"all_sec43_unit_fixtures_passed": True, "n_assertions": 9}


if __name__ == "__main__":
    print(run_unit_fixtures())
