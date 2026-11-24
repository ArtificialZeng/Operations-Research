"""
Synthetic-only unit fixtures for `stage1_axis_calibration.py`.
Zero DigitizerBench dev or held-out images are opened or evaluated here.
"""
from __future__ import annotations

import math
from pathlib import Path
import sys
import tempfile

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "upstream_linepilot" / "Digitizer"))

import stage1_axis_calibration as cal  # noqa: E402
import digitizer_api  # noqa: E402


def test_loto_outlier_rejection() -> None:
    # True X scale: x_px in [100, 500] -> val in [-1.0, 1.0], slope = 0.005
    # Inject a garbled endpoint (7.0 instead of -1.0 at x=100) + 4 clean ticks
    band = [
        cal.RawToken(7.0, 90, 420, 20, 12, 65.0, "v1", 1.0),
        cal.RawToken(-0.5, 190, 420, 20, 12, 92.0, "v1", 1.0),
        cal.RawToken(0.0, 290, 420, 20, 12, 95.0, "v1", 1.0),
        cal.RawToken(0.5, 390, 420, 20, 12, 94.0, "v1", 1.0),
        cal.RawToken(1.0, 490, 420, 20, 12, 93.0, "v1", 1.0),
    ]
    fit = cal._fit_axis_from_band(band, axis="x", expected_plot_span=400.0, anchor_ortho_ref=400.0)
    assert fit.accepted and fit.accept_reason == "loto_m>=3_accepted", fit
    assert fit.n_inliers == 4, fit
    assert abs(fit.slope - 0.005) < 1e-6, fit
    assert abs(fit.med_loto_resid) < 1e-6, fit


def test_loto_dropped_minus_adjudication() -> None:
    # True X: [-1, 1] over [100, 500]; at x=150 (-0.75) raw OCR read +0.75,
    # image-grounded check adds synthetic -0.75; LOTO must select -0.75!
    band = [
        cal.RawToken(0.75, 140, 420, 20, 12, 85.0, "v1", 1.0, synthetic_negated=False),
        cal.RawToken(-0.75, 140, 420, 20, 12, 72.25, "v1:neg", 1.0, synthetic_negated=True),
        cal.RawToken(0.0, 290, 420, 20, 12, 95.0, "v1", 1.0),
        cal.RawToken(0.5, 390, 420, 20, 12, 95.0, "v1", 1.0),
        cal.RawToken(1.0, 490, 420, 20, 12, 95.0, "v1", 1.0),
    ]
    fit = cal._fit_axis_from_band(band, axis="x", expected_plot_span=400.0, anchor_ortho_ref=400.0)
    assert fit.accepted and fit.n_inliers == 4, fit
    vals = [d["value"] for d in fit.inliers]
    assert -0.75 in vals and 0.75 not in vals, vals
    assert abs(fit.slope - 0.005) < 1e-6, fit


def test_right_edge_y_clustering_variable_width() -> None:
    # At 600 DPI, "0" has width 30 and "100000" has width 180; both right-aligned at x_right = 240!
    toks = [
        cal.RawToken(0.0, 210, 900, 30, 40, 95.0, "v1", 1.0),       # cx = 225, right = 240
        cal.RawToken(50000.0, 90, 500, 150, 40, 95.0, "v1", 1.0),  # cx = 165, right = 240
        cal.RawToken(100000.0, 60, 100, 180, 40, 95.0, "v1", 1.0), # cx = 150, right = 240
    ]
    bands = cal._cluster_axis_bands(toks, axis="y", img_w=2400, img_h=1200)
    assert len(bands) == 1 and len(bands[0]) == 3, f"Expected 1 unified right-aligned Y band, got {len(bands)}"
    fit = cal._fit_axis_from_band(bands[0], axis="y", expected_plot_span=800.0, anchor_ortho_ref=260.0)
    assert fit.accepted and fit.n_inliers == 3, fit
    assert abs(fit.anchor_val_lo - 0.0) < 1e-3 and abs(fit.anchor_val_hi - 100000.0) < 1e-2, fit


def test_two_tick_multiview_verified_and_reject_single_view() -> None:
    # Single-view 2 ticks must REJECT
    band_1v = [
        cal.RawToken(0.0, 100, 420, 20, 12, 95.0, "v1", 1.0),
        cal.RawToken(1.0, 480, 420, 20, 12, 95.0, "v1", 1.0),
    ]
    fit1 = cal._fit_axis_from_band(band_1v, axis="x", expected_plot_span=400.0, anchor_ortho_ref=400.0)
    assert not fit1.accepted, fit1

    # Two-view agreed 2 ticks spanning >= 50% must ACCEPT as two_tick_multiview_verified
    band_2v = [
        cal.RawToken(0.0, 100, 420, 20, 12, 90.0, "v1", 1.0),
        cal.RawToken(0.0, 101, 420, 20, 12, 92.0, "v2", 1.0),
        cal.RawToken(1.0, 480, 420, 20, 12, 90.0, "v1", 1.0),
        cal.RawToken(1.0, 479, 420, 20, 12, 91.0, "v2", 1.0),
    ]
    fit2 = cal._fit_axis_from_band(band_2v, axis="x", expected_plot_span=400.0, anchor_ortho_ref=400.0)
    assert fit2.accepted and fit2.accept_reason == "two_tick_multiview_verified", fit2


def test_synthetic_end_to_end_and_equal_budget() -> None:
    with tempfile.TemporaryDirectory() as td:
        td_p = Path(td)
        # 1. Synthetic gray-spine / Plotly-like light-axis plot (where snap-to-black RGB<=30 fails!)
        img_gray = td_p / "synth_gray_spine.png"
        fig, ax = plt.subplots(figsize=(4.5, 3.0), dpi=150)
        xs = np.linspace(-1.0, 1.0, 200)
        ys = 0.5 * np.sin(np.pi * xs)
        ax.plot(xs, ys, color="#0072B2", linewidth=2.5)
        ax.set_xlim(-1.0, 1.0)
        ax.set_ylim(-1.0, 1.0)
        ax.set_xticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        ax.set_yticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        for sp in ("top", "right"):
            ax.spines[sp].set_visible(False)
        for sp in ("bottom", "left"):
            ax.spines[sp].set_color("#999999")
        ax.tick_params(colors="#333333")
        ax.grid(True, color="#E0E0E0")
        fig.savefig(img_gray, dpi=150)
        plt.close(fig)

        prop_b = cal.calibrate_axes_matched(img_gray, arm="B_single_res")
        prop_c = cal.calibrate_axes_matched(img_gray, arm="C_two_res")
        assert prop_b.ocr_call_count == 8 and prop_c.ocr_call_count == 8
        assert prop_b.accepted, f"B failed on clean gray spine: {prop_b}"
        assert prop_c.accepted, f"C failed on clean gray spine: {prop_c}"

        # Verify end-to-end digitizer_api acceptance & accuracy
        res_b = digitizer_api.digitize_image(
            pic_dir=img_gray,
            tick_points=prop_b.tick_points,
            axis_values=prop_b.axis_values,
            limit_to_calibration=False,
            output_dir=td_p / "out_b",
        )
        res_c = digitizer_api.digitize_image(
            pic_dir=img_gray,
            tick_points=prop_c.tick_points,
            axis_values=prop_c.axis_values,
            limit_to_calibration=False,
            output_dir=td_p / "out_c",
        )
        assert res_b.used_ocr is False and res_c.used_ocr is False
        assert res_b.color_rgb == res_c.color_rgb
        # Verify exact pixel trace identity between B and C
        import pandas as pd
        df_b = pd.read_csv(res_b.csv_path)
        df_c = pd.read_csv(res_c.csv_path)
        assert len(df_b) == len(df_c) and len(df_b) > 100
        assert float(np.max(np.abs(df_b["x_px"].to_numpy() - df_c["x_px"].to_numpy()))) == 0.0
        assert float(np.max(np.abs(df_b["y_px"].to_numpy() - df_c["y_px"].to_numpy()))) == 0.0
        # Verify recovered data coordinates are accurate against true sine wave
        y_true_b = 0.5 * np.sin(np.pi * df_b["x"].to_numpy())
        nrmse_b = float(np.sqrt(np.mean((df_b["y"].to_numpy() - y_true_b) ** 2)) / 2.0)
        y_true_c = 0.5 * np.sin(np.pi * df_c["x"].to_numpy())
        nrmse_c = float(np.sqrt(np.mean((df_c["y"].to_numpy() - y_true_c) ** 2)) / 2.0)
        assert nrmse_b < 0.03 and nrmse_c < 0.03, f"Synthetic NRMSE too high: B={nrmse_b:.4f}, C={nrmse_c:.4f}"

        # 2. Synthetic low-DPI tiny plot (72 DPI, 3.0x2.0 in = 216x144 px, 8pt ticks)
        img_low = td_p / "synth_low_dpi.png"
        fig, ax = plt.subplots(figsize=(3.0, 2.0), dpi=72)
        ax.plot(xs, ys, color="#D55E00", linewidth=2.0)
        ax.set_xlim(-1.0, 1.0)
        ax.set_ylim(-1.0, 1.0)
        ax.set_xticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        ax.set_yticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        ax.tick_params(labelsize=8)
        fig.tight_layout()
        fig.savefig(img_low, dpi=72)
        plt.close(fig)

        low_b = cal.calibrate_axes_matched(img_low, arm="B_single_res")
        low_c = cal.calibrate_axes_matched(img_low, arm="C_two_res")
        assert low_b.ocr_call_count == 8 and low_c.ocr_call_count == 8
        print(
            f"Synthetic gray-spine: B accepted={prop_b.accepted} (NRMSE={nrmse_b:.4f}, {prop_b.timing_s['calibration_total_s']:.2f}s), "
            f"C accepted={prop_c.accepted} (NRMSE={nrmse_c:.4f}, {prop_c.timing_s['calibration_total_s']:.2f}s)"
        )
        print(
            f"Synthetic 72-DPI tiny: B accepted={low_b.accepted} (x={low_b.x_fit['accept_reason']}, y={low_b.y_fit['accept_reason']}, {low_b.timing_s['calibration_total_s']:.2f}s), "
            f"C accepted={low_c.accepted} (x={low_c.x_fit['accept_reason']}, y={low_c.y_fit['accept_reason']}, {low_c.timing_s['calibration_total_s']:.2f}s)"
        )

        # 3. Synthetic borderless Plotly-style plot (no spines, #E5ECF6 plot background, #2A3F5F navy text)
        img_plotly = td_p / "synth_borderless_plotly.png"
        fig, ax = plt.subplots(figsize=(4.0, 3.0), dpi=150)
        ax.set_facecolor("#E5ECF6")
        ax.plot(xs, ys, color="#CC79A7", linewidth=2.5)
        ax.set_xlim(0.0, 1.0)
        ax.set_ylim(-1.0, 1.0)
        ax.set_xticks([0.0, 0.25, 0.5, 0.75, 1.0])
        ax.set_yticks([-1.0, -0.5, 0.0, 0.5, 1.0])
        for sp in ("top", "right", "bottom", "left"):
            ax.spines[sp].set_visible(False)
        ax.grid(True, color="#FFFFFF", linewidth=1.2)
        ax.tick_params(length=0, colors="#2A3F5F")
        fig.savefig(img_plotly, dpi=150, facecolor="white")
        plt.close(fig)

        pl_b = cal.calibrate_axes_matched(img_plotly, arm="B_single_res")
        pl_c = cal.calibrate_axes_matched(img_plotly, arm="C_two_res")
        assert pl_b.ocr_call_count == 8 and pl_c.ocr_call_count == 8
        assert pl_b.accepted and pl_c.accepted, f"Borderless Plotly-style failed: B={pl_b.accepted}, C={pl_c.accepted}"
        print(
            f"Synthetic borderless Plotly-style: B accepted={pl_b.accepted} ({pl_b.timing_s['calibration_total_s']:.2f}s, tiers={pl_b.roi_geometry['spine_tier_h']}/{pl_b.roi_geometry['spine_tier_v']}), "
            f"C accepted={pl_c.accepted} ({pl_c.timing_s['calibration_total_s']:.2f}s)"
        )

        # 4. Synthetic 600-DPI giant plot (4800 x 2400) with 3 ticks and [1000, 100000] wide labels
        img_giant = td_p / "synth_giant_600dpi.png"
        fig, ax = plt.subplots(figsize=(8.0, 4.0), dpi=600)
        xg = np.linspace(-1.0, 1.0, 200)
        yg = 50000.0 + 40000.0 * np.cos(np.pi * xg)
        ax.plot(xg, yg, color="#0072B2", linewidth=3.0)
        ax.set_xlim(-1.0, 1.0)
        ax.set_ylim(1000.0, 100000.0)
        ax.set_xticks([-1.0, 0.0, 1.0])
        ax.set_yticks([1000.0, 50500.0, 100000.0])
        ax.tick_params(labelsize=12)
        fig.savefig(img_giant, dpi=600)
        plt.close(fig)

        gi_b = cal.calibrate_axes_matched(img_giant, arm="B_single_res")
        gi_c = cal.calibrate_axes_matched(img_giant, arm="C_two_res")
        assert gi_b.ocr_call_count == 8 and gi_c.ocr_call_count == 8
        assert gi_b.accepted and gi_c.accepted, f"Giant 600-DPI failed: B=({gi_b.x_fit['accept_reason']},{gi_b.y_fit['accept_reason']}), C=({gi_c.x_fit['accept_reason']},{gi_c.y_fit['accept_reason']})"
        print(
            f"Synthetic 600-DPI 4800x2400: B accepted={gi_b.accepted} ({gi_b.timing_s['calibration_total_s']:.2f}s), "
            f"C accepted={gi_c.accepted} ({gi_c.timing_s['calibration_total_s']:.2f}s)"
        )


def main() -> None:
    test_loto_outlier_rejection()
    test_loto_dropped_minus_adjudication()
    test_right_edge_y_clustering_variable_width()
    test_two_tick_multiview_verified_and_reject_single_view()
    test_synthetic_end_to_end_and_equal_budget()
    print("ALL 7 SYNTHETIC STAGE-1 CALIBRATION FIXTURES PASSED!")


if __name__ == "__main__":
    main()
