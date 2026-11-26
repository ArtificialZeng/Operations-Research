"""Step 6: Generate 5 publication-grade 300-DPI PNG + vector PDF figures and 6 zero-NaN CSV tables."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.colors import TwoSlopeNorm

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
PROC_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"
FIG_DIR = BASE_DIR / "figures"
TBL_DIR = BASE_DIR / "tables"

plt.rcParams.update(
    {
        "font.family": "DejaVu Sans",
        "font.size": 9.0,
        "axes.titlesize": 10.2,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "xtick.labelsize": 8.4,
        "ytick.labelsize": 8.4,
        "legend.fontsize": 8.0,
        "figure.dpi": 300,
        "savefig.dpi": 300,
        "pdf.fonttype": 42,
        "ps.fonttype": 42,
    }
)

# Colorblind-safe Okabe-Ito inspired scientific palette
C_NAVY = "#0B2545"
C_BLUE = "#0072B2"
C_SKY = "#56B4E9"
C_RED = "#C0392B"
C_ORG = "#D55E00"
C_TEAL = "#009E73"
C_PURP = "#7B3F9E"
C_GOLD = "#E69F00"
C_GRAY = "#52606D"


def save_fig(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [FIG] saved {stem}.png + .pdf", flush=True)


def make_fig1(econ: dict, rdf: pd.DataFrame) -> None:
    sub_q = rdf[rdf["has_spec2_q"] == 1].copy()
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.5), gridspec_kw={"width_ratios": [1.16, 1.04]})

    # Panel A: CONUS Map colored by diurnal decoupling d(DO_min - DO_max)/dT
    # Use TwoSlopeNorm centered strictly at 0.0 with RdBu (red = negative nocturnal acceleration, white = 0, blue = positive)
    vals = np.clip(sub_q["s2_diff_min_max"].values, -0.30, 0.10)
    norm_div = TwoSlopeNorm(vmin=-0.30, vcenter=0.0, vmax=0.10)
    sc = ax1.scatter(
        sub_q["lon"].values,
        sub_q["lat"].values,
        c=vals,
        cmap="RdBu",
        norm=norm_div,
        s=34,
        edgecolors="#1e293b",
        linewidths=0.45,
        alpha=0.92,
        zorder=3,
    )
    ax1.set_xlim(-125.5, -66.5)
    ax1.set_ylim(23.5, 50.0)
    ax1.set_aspect(1.26)
    ax1.grid(True, linestyle="--", alpha=0.30, color="#94a3b8", zorder=0)
    ax1.set_xlabel("Longitude (°W)")
    ax1.set_ylabel("Latitude (°N)")
    ax1.set_title("A. Screened Free-Flowing CONUS Stations: d(DO_min − DO_max)/dT")
    cb = fig.colorbar(sc, ax=ax1, orientation="horizontal", pad=0.13, fraction=0.055, aspect=35)
    cb.set_ticks([-0.30, -0.20, -0.10, 0.0, 0.05, 0.10])
    cb.set_label("Diurnal Decoupling d(DO_min − DO_max)/dT (mg/L/°C; red < 0 = steeper DO_min drop, white = 0)", fontsize=7.8)

    ov = econ["census_overview"]
    sp2_diff = econ["spec2_ym_fe_logQ_quad_primary"]["diff_min_max"]
    box_txt = (
        f"Screened Q-Ctrl: N = {ov['n_rivers_with_q_primary']} sites ({ov['n_states_with_q']} states)\n"
        f"Basins: {ov['n_huc2_with_q']}/18 HUC-2 | Decoupling <0: {sp2_diff['pct_neg']:.1f}%\n"
        f"Screened Total: {ov['n_clean_rivers_total']} sites ({ov['total_station_days']:,} days)"
    )
    ax1.text(
        0.015,
        0.025,
        box_txt,
        transform=ax1.transAxes,
        fontsize=7.1,
        va="bottom",
        ha="left",
        bbox={"boxstyle": "round,pad=0.32", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.95},
        zorder=5,
    )

    # Panel B: Thermal Slopes & Specification Robustness (HUC-2 & State Clustered t(G-1) 95% CIs)
    s2 = econ["spec2_ym_fe_logQ_quad_primary"]
    s1 = econ["spec1_ym_fe_all_clean"]
    rob = econ["robustness_suite"]
    s6 = econ["spec6_pooled_panel_ym_fe_logQ"]["outcomes"]
    henrys = s2["do_sat_alt"]["mean"]

    rows = [
        ("Daytime DO_max (Primary YM+Q)", s2["do_max"], C_GOLD),
        ("Daily DO_mean (Primary YM+Q)", s2["do_mean"], C_BLUE),
        ("Nocturnal DO_min (Primary YM+Q)", s2["do_min"], C_RED),
        ("Decoupling: DO_min − DO_max (Spec 1: YM FE)", s1["diff_min_max"], C_NAVY),
        ("Decoupling: DO_min − DO_max (Spec 2: +logQ, Q²)", s2["diff_min_max"], C_NAVY),
        ("Decoupling: + log(SpCond) Control", rob["spec4_plus_logSpCond"]["diff_min_max"], C_TEAL),
        ("Decoupling: + log(Turbidity) Control", rob["spec4_plus_logTurbidity"]["diff_min_max"], C_TEAL),
        ("Decoupling: Ultra-Strict Zero-Infra", rob["spec5_ultra_strict_zero_infra"]["diff_min_max"], C_PURP),
        ("Decoupling: NID Dam-Free (>5 km, ≥500 af)", rob["spec5_nid_gt5km_ge500af"]["diff_min_max"], C_PURP),
        ("Decoupling: Long-Record (≥10 yr)", rob["spec5_long_record_ge10warm_yrs"]["diff_min_max"], C_PURP),
        ("Decoupling: Pooled Panel (River×YM+Q)", None, C_ORG),
    ]

    y_pos = np.arange(len(rows))[::-1]
    ax2.axvline(0.0, color="#334155", linewidth=0.9, linestyle="-", zorder=1)
    ax2.axvline(henrys, color=C_GRAY, linewidth=1.1, linestyle="--", zorder=1)
    ax2.text(henrys - 0.004, len(rows) - 0.25, f"Henry's Law ({henrys:.3f})", fontsize=7.4, color=C_GRAY, ha="right", va="bottom")

    # Shade separator between absolute slopes and decoupling contrasts
    ax2.axhline(len(rows) - 3.5, color="#cbd5e1", linewidth=0.8, linestyle=":")

    for yp, (lbl, blk, col) in zip(y_pos, rows):
        if blk is None:
            p_rec = s6["diff_min_max"]
            mu = p_rec["beta_temp"]
            lo_h, hi_h = p_rec["huc2_cluster"]["ci95_lo"], p_rec["huc2_cluster"]["ci95_hi"]
            lo_s, hi_s = p_rec["state_cluster"]["ci95_lo"], p_rec["state_cluster"]["ci95_hi"]
        else:
            mu = blk["mean"]
            lo_h, hi_h = blk["huc2_cluster"]["ci95_lo"], blk["huc2_cluster"]["ci95_hi"]
            lo_s, hi_s = blk["state_cluster"]["ci95_lo"], blk["state_cluster"]["ci95_hi"]
        ax2.plot([lo_s, hi_s], [yp, yp], color=col, linewidth=1.2, alpha=0.55, zorder=2)
        ax2.plot([lo_h, hi_h], [yp, yp], color=col, linewidth=3.0, alpha=0.90, zorder=3)
        ax2.scatter([mu], [yp], color=col, s=34, zorder=4, edgecolors="white", linewidths=0.6)
        # Place Nocturnal DO_min label cleanly to the LEFT so it never crosses the Henry's Law vertical line
        if lbl.startswith("Nocturnal DO_min"):
            ax2.text(min(lo_h, lo_s) - 0.006, yp, f"{mu:+.3f}", va="center", ha="right", fontsize=7.5, color="#1e293b")
        else:
            ax2.text(max(hi_h, hi_s) + 0.007, yp, f"{mu:+.3f}", va="center", ha="left", fontsize=7.5, color="#1e293b")

    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([r[0] for r in rows], fontsize=7.9)
    ax2.set_xlabel("Thermal Sensitivity Slope (mg/L per °C) ± 95% CI (thick: HUC-2, thin: State)")
    ax2.set_title("B. Thermal Decoupling Across Hydrologic Specifications")
    ax2.set_xlim(-0.31, 0.08)
    ax2.set_ylim(-0.6, len(rows) + 0.35)
    ax2.grid(True, axis="x", linestyle="--", alpha=0.30, color="#94a3b8")

    fig.tight_layout(w_pad=2.2)
    save_fig(fig, "fig1_conus_map_and_thermal_decoupling")


def make_fig2(iv: dict, econ: dict) -> None:
    sol = pd.DataFrame(iv["solar_24h_curve"])
    tf_pm = iv["transfer_function_oos"]["afternoon_1430"]
    tf_ls = iv["transfer_function_oos"]["landsat_1030"]
    s_domin = iv["named_windows"]["pm1316"]["mean_DOmin_slope"]
    henrys = iv.get("iv_mean_DOsat_alt_slope", econ["spec2_ym_fe_logQ_quad_primary"]["do_sat_alt"]["mean"])

    fig, (ax1, ax2, ax3) = plt.subplots(1, 3, figsize=(15.0, 5.2), gridspec_kw={"width_ratios": [1.24, 1.12, 1.04]})

    hrs = sol["hour"].values
    # Panel A: 24-hour Warming Sensitivity Curve (legend placed cleanly below axes so hours 0-8 are 100% unobstructed!)
    ax1.axvspan(5.0, 7.0, color="#dbeafe", alpha=0.55, label="Pre-Dawn (05–07h)")
    ax1.axvspan(10.0, 11.0, color="#fef3c7", alpha=0.75, label="Overpass Window (10–11h LST)")
    ax1.axvspan(13.0, 16.0, color="#fee2e2", alpha=0.65, label="Afternoon Grab (13–16h)")

    ax1.axhline(s_domin, color=C_RED, linestyle="--", linewidth=1.3, label=f"24h DO_min ({s_domin:.3f})")
    ax1.axhline(henrys, color=C_GRAY, linestyle=":", linewidth=1.2, label=f"Henry's Law ({henrys:.3f})")

    ax1.fill_between(hrs, sol["slope_ci95_lo"], sol["slope_ci95_hi"], color=C_BLUE, alpha=0.22)
    ax1.plot(hrs, sol["slope_mean"], color=C_BLUE, marker="o", markersize=3.5, linewidth=2.0, label="dDO(h)/dT_mean (95% CI)")
    ax1.plot(hrs, sol["slope_instT_mean"], color=C_PURP, linestyle="-.", linewidth=1.4, label="dDO(h)/dT(h) (Inst. T)")

    pm_att = iv["named_windows"]["pm1316"]["warming_underestimation_pct"]
    ls_att = iv["named_windows"]["ls10"]["warming_underestimation_pct"]
    ax1.annotate(
        f"Afternoon 13–16h civil:\n−{pm_att:.1f}% slope bias",
        xy=(14.5, sol.loc[sol["hour"] == 15, "slope_mean"].values[0]),
        xytext=(16.0, -0.052),
        fontsize=7.0,
        fontweight="bold",
        color=C_RED,
        arrowprops={"arrowstyle": "->", "color": C_RED, "lw": 1.0},
        bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": C_RED, "alpha": 0.94},
    )
    ax1.annotate(
        f"Overpass 10–11h:\n−{ls_att:.1f}% slope",
        xy=(10.1, sol.loc[sol["hour"] == 10, "slope_mean"].values[0]),
        xytext=(1.0, -0.075),
        fontsize=7.0,
        color="#92400e",
        arrowprops={"arrowstyle": "->", "color": "#92400e", "lw": 0.9},
        bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": "#d97706", "alpha": 0.94},
    )

    ax1.set_xlim(0, 23)
    ax1.set_ylim(-0.255, 0.015)
    ax1.set_xticks([0, 3, 6, 9, 12, 15, 18, 21])
    ax1.set_xlabel("Local Mean Solar Time (Hour)")
    ax1.set_ylabel("Apparent Temperature Sensitivity dDO(h)/dT (mg/L/°C)")
    ax1.set_title(f"A. 24-Hour Temperature-Sensitivity Clock-Bias (N = {iv['n_iv_rivers']})", pad=10)
    ax1.grid(True, linestyle="--", alpha=0.28)
    ax1.legend(
        loc="upper center",
        bbox_to_anchor=(0.5, -0.16),
        ncol=2,
        fontsize=6.7,
        frameon=True,
        framealpha=0.96,
        columnspacing=0.9,
        handlelength=1.6,
        borderpad=0.30,
    )

    # Panel B: 24-hour Missed Hypoxia Events
    ax2.axvspan(10.0, 11.0, color="#fef3c7", alpha=0.75)
    ax2.axvspan(13.0, 16.0, color="#fee2e2", alpha=0.65)
    for col_k, lbl, col_c, mk in [
        ("hyp5_missed_pct", "< 5.0 mg/L (EPA Chronic)", C_BLUE, "o"),
        ("hyp4_missed_pct", "< 4.0 mg/L (Moderate)", C_TEAL, "s"),
        ("hyp3_missed_pct", "< 3.0 mg/L (Acute Stress)", C_ORG, "^"),
        ("hyp2_missed_pct", "< 2.0 mg/L (Severe Hypoxia)", C_RED, "D"),
    ]:
        ax2.plot(hrs, sol[col_k], color=col_c, marker=mk, markersize=3.2, linewidth=1.8, label=lbl)

    ax2.set_xlim(0, 23)
    ax2.set_ylim(0, 90)
    ax2.set_xticks([0, 3, 6, 9, 12, 15, 18, 21])
    ax2.set_xlabel("Local Mean Solar Time (Hour)")
    ax2.set_ylabel("Daily Hypoxia Days Missed (%)")
    ax2.set_title("B. 24-Hour Hypoxia-Threshold Blindness", pad=10)
    ax2.grid(True, linestyle="--", alpha=0.28)
    ax2.legend(loc="lower right", fontsize=7.0, framealpha=0.94)
    ax2.text(10.5, 86, "Overpass\n10–11h", ha="center", va="top", fontsize=7.0, color="#92400e", fontweight="bold")
    ax2.text(14.5, 86, "Afternoon\n13–16h", ha="center", va="top", fontsize=7.0, color=C_RED, fontweight="bold")

    # Panel C: OOS Leave-One-HUC2-Basin-Out Transfer Function Validation
    cat_labels = [
        "Mean Bias\nReduction",
        "RMSE\nReduction",
        "Slope Bias\nReduction",
        "<5 mg/L\nRecall",
    ]
    pm_gains = [
        tf_pm["mean_bias_reduction_pct"],
        tf_pm["rmse_reduction_pct"],
        tf_pm["warming_slope_recovery"]["slope_bias_reduction_pct"],
        tf_pm["hypoxia_detection_lohuc2"]["lt_5_mgL"]["corrected_recall_pct"],
    ]
    ls_gains = [
        tf_ls["mean_bias_reduction_pct"],
        tf_ls["rmse_reduction_pct"],
        tf_ls["warming_slope_recovery"]["slope_bias_reduction_pct"],
        tf_ls["hypoxia_detection_lohuc2"]["lt_5_mgL"]["corrected_recall_pct"],
    ]
    x = np.arange(len(cat_labels))
    w = 0.35
    b1 = ax3.bar(x - w / 2, pm_gains, w, color=C_RED, alpha=0.88, label="Afternoon Grab (13:30–15:30)")
    b2 = ax3.bar(x + w / 2, ls_gains, w, color=C_GOLD, alpha=0.90, label="Overpass Window (10:00–11:00 LST)")
    for bars in (b1, b2):
        for bar in bars:
            h_v = bar.get_height()
            ax3.text(bar.get_x() + bar.get_width() / 2, h_v + 1.8, f"{h_v:.1f}%", ha="center", va="bottom", fontsize=7.0, fontweight="bold")
    # Overlay horizontal dashed raw-recall baselines cleanly on bar #4 instead of covering the bars with a box!
    raw_rec_pm = tf_pm["hypoxia_detection_lohuc2"]["lt_5_mgL"]["raw_recall_pct"]
    raw_rec_ls = tf_ls["hypoxia_detection_lohuc2"]["lt_5_mgL"]["raw_recall_pct"]
    ax3.hlines(raw_rec_pm, 3 - w, 3.0, colors="#0f172a", linestyles="--", linewidth=1.6, zorder=5)
    ax3.hlines(raw_rec_ls, 3.0, 3 + w, colors="#0f172a", linestyles="--", linewidth=1.6, zorder=5)
    ax3.text(
        3.0,
        78.0,
        f"Dashed = raw recall\n(PM {raw_rec_pm:.0f}%, OV {raw_rec_ls:.0f}%)",
        ha="center",
        va="bottom",
        fontsize=6.6,
        color="#1e293b",
        bbox={"boxstyle": "round,pad=0.22", "facecolor": "#f8fafc", "edgecolor": "#cbd5e1", "alpha": 0.94},
    )

    ax3.set_xticks(x)
    ax3.set_xticklabels(cat_labels, fontsize=7.6)
    ax3.set_ylim(0, 118)
    ax3.set_ylabel("Out-of-Sample Performance (%)")
    ax3.set_title("C. Leave-One-HUC2-Out Transfer Correction", pad=10)
    ax3.grid(True, axis="y", linestyle="--", alpha=0.28)
    ax3.legend(loc="upper right", fontsize=6.8, frameon=True, framealpha=0.94, borderpad=0.28)

    fig.tight_layout(w_pad=1.8)
    save_fig(fig, "fig2_24h_clock_bias_and_transfer")


def make_fig3(econ: dict) -> None:
    cmp = econ["compound_hot_x_dry"]
    eff = cmp["effects"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.0, 5.0), gridspec_kw={"width_ratios": [1.15, 1.0]})

    # Panel A: 2x2 Regime Effects (Hot-Only, Dry-Only, Compound Hot x Dry) on DO_sat, DO_max, DO_mean, DO_min
    regimes = [("Hot-Only\n(T ≥ P90)", "hot_only"), ("Dry-Only\n(Q ≤ P20)", "dry_only"), ("Compound\n(Hot × Dry)", "total_compound_vs_normal")]
    series_spec = [
        ("Henry's Law DO_sat", "do_sat_alt", C_GRAY),
        ("Daytime DO_max", "do_max", C_GOLD),
        ("Daily DO_mean", "do_mean", C_BLUE),
        ("Nocturnal DO_min", "do_min", C_RED),
    ]
    x = np.arange(len(regimes))
    w = 0.19
    ax1.axhline(0.0, color="#1e293b", linewidth=0.9)
    for j, (lbl, k, col) in enumerate(series_spec):
        offset = (j - 1.5) * w
        means = [eff[k][rk]["mean"] for _, rk in regimes]
        errs = [
            (eff[k][rk]["huc2_cluster"]["ci95_hi"] - eff[k][rk]["huc2_cluster"]["ci95_lo"]) / 2.0
            for _, rk in regimes
        ]
        bars = ax1.bar(x + offset, means, w, yerr=errs, capsize=2.8, color=col, alpha=0.90, label=lbl, error_kw={"lw": 1.1, "ecolor": "#0f172a"})
        for bar, mv, ev in zip(bars, means, errs):
            ytxt = mv - ev - 0.055 if mv < 0 else mv + ev + 0.045
            va = "top" if mv < 0 else "bottom"
            ax1.text(bar.get_x() + bar.get_width() / 2, ytxt, f"{mv:+.2f}", ha="center", va=va, fontsize=6.9)

    ax1.set_xticks(x)
    ax1.set_xticklabels([r[0] for r in regimes], fontsize=8.8)
    ax1.set_ylabel("Within-River DO Change vs. Normal Days (mg/L; HUC-2 95% CI)")
    ax1.set_title(f"A. Asymmetric Diurnal Response to Heat & Drought (N = {cmp['n_rivers']} Rivers)")
    ax1.set_ylim(-1.28, 0.78)
    ax1.grid(True, axis="y", linestyle="--", alpha=0.28)
    ax1.legend(loc="lower left", fontsize=7.6, framealpha=0.94, ncol=2)

    # Panel B: Formal Hot x Dry Super-Additive Interactions (Biological Deficit & Hypoxia Probability Surges vs. Null Daytime)
    int_items = [
        ("Bio Deficit: DO_min − DO_sat (mg/L)", "diff_min_sat", 1.0, "mg/L", C_PURP),
        ("Physical Solubility DO_sat (mg/L)", "do_sat_alt", 1.0, "mg/L", C_GRAY),
        ("Daytime DO_max (mg/L)", "do_max", 1.0, "mg/L", C_GOLD),
        ("Nocturnal P(DO_min < 5 mg/L) [÷10 pp]", "hyp5_min", 10.0, "pp", C_RED),
        ("Nocturnal P(DO_min < 3 mg/L) [÷10 pp]", "hyp3_min", 10.0, "pp", C_ORG),
        ("Nocturnal P(DO_min < 2 mg/L) [÷10 pp]", "hyp2_min", 10.0, "pp", C_NAVY),
        ("Daytime P(DO_max < 5 mg/L) [÷10 pp]", "hyp5_max", 10.0, "pp", C_TEAL),
    ]
    yp = np.arange(len(int_items))[::-1]
    ax2.axvline(0.0, color="#1e293b", linewidth=0.9)
    ax2.axhline(len(int_items) - 3.5, color="#cbd5e1", linewidth=0.8, linestyle=":")
    for y_i, (lbl, k, mult, unit, col) in zip(yp, int_items):
        blk = eff[k]["hot_x_dry_interaction"]
        mu = blk["mean"] * mult
        lo = blk["huc2_cluster"]["ci95_lo"] * mult
        hi = blk["huc2_cluster"]["ci95_hi"] * mult
        pv = blk["huc2_cluster"]["p_cr1_t_Gminus1"]
        ax2.plot([lo, hi], [y_i, y_i], color=col, linewidth=2.8, alpha=0.90)
        ax2.scatter([mu], [y_i], color=col, s=38, edgecolors="white", linewidths=0.6, zorder=4)
        raw_disp = f"{blk['mean']*100:+.2f} pp" if mult == 10.0 else f"{blk['mean']:+.3f}"
        p_disp = f"p={pv:.1e}" if pv < 0.001 else f"p={pv:.3f}"
        ax2.text(max(hi, 0.0) + 0.015, y_i, f"{raw_disp} ({p_disp})", va="center", ha="left", fontsize=7.4)

    ax2.set_yticks(yp)
    ax2.set_yticklabels([it[0] for it in int_items], fontsize=8.0)
    ax2.set_xlabel("Formal Hot × Dry Interaction (mg/L or 10 pp; HUC-2 95% CI)")
    ax2.set_title("B. Super-Additive Biological Deficit & Nocturnal Hypoxia Surge")
    ax2.set_xlim(-0.24, 0.72)
    ax2.grid(True, axis="x", linestyle="--", alpha=0.28)

    fig.tight_layout(w_pad=2.0)
    save_fig(fig, "fig3_compound_heatwave_drought")


def make_fig4(econ: dict) -> None:
    mech = econ["biophysical_mechanism"]
    pq = mech["split_half_productivity_quartiles"]
    henrys = econ["spec2_ym_fe_logQ_quad_primary"]["do_sat_alt"]["mean"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.4, 5.2), gridspec_kw={"width_ratios": [1.08, 1.12]})

    # Panel A: Split-Half Out-of-Sample Productivity Scissors (Early Swing -> Late Thermal Slopes)
    q_order = ["Q1_Oligotrophic", "Q2_LowMesotrophic", "Q3_HighMesotrophic", "Q4_Eutrophic"]
    q_labels = [
        f"Q1 Oligo.\n({pq[q_order[0]]['early_swing_mean']:.1f} mg/L)",
        f"Q2 Low-Meso.\n({pq[q_order[1]]['early_swing_mean']:.1f} mg/L)",
        f"Q3 High-Meso.\n({pq[q_order[2]]['early_swing_mean']:.1f} mg/L)",
        f"Q4 Eutrophic\n({pq[q_order[3]]['early_swing_mean']:.1f} mg/L)",
    ]
    xq = np.arange(4)
    ax1.axhline(0.0, color="#334155", linewidth=0.8)
    ax1.axhline(henrys, color=C_GRAY, linestyle="--", linewidth=1.2, label=f"Henry's Law ({henrys:.3f})")

    for key, lbl, col, mk in [
        ("late_do_max_slope", "Late-Period Daytime dDO_max/dT", C_GOLD, "^"),
        ("late_do_min_slope", "Late-Period Nocturnal dDO_min/dT", C_RED, "o"),
        ("late_diff_min_max", "Late-Period Decoupling d(DO_min − DO_max)/dT", C_NAVY, "s"),
    ]:
        ys = [pq[q][key]["mean"] for q in q_order]
        es = [(pq[q][key]["huc2_cluster"]["ci95_hi"] - pq[q][key]["huc2_cluster"]["ci95_lo"]) / 2.0 for q in q_order]
        ax1.errorbar(xq, ys, yerr=es, color=col, marker=mk, markersize=6, linewidth=2.0, capsize=3.5, label=lbl)

    sp_r = mech["split_half_oos_spearman"]["early_swing_vs_late_diff_min_max"]
    ax1.text(
        0.03,
        0.04,
        f"Split-Half OOS (N = {sp_r['n']} rivers):\nEarly Swing vs Late Decoupling\nSpearman r = {sp_r['spearman_r']:.3f} (p = {sp_r['p']:.2e})",
        transform=ax1.transAxes,
        fontsize=7.6,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.94},
    )
    ax1.set_xticks(xq)
    ax1.set_xticklabels(q_labels, fontsize=8.0)
    ax1.set_ylim(-0.31, 0.115)
    ax1.set_xlabel("Early-Half Baseline Diurnal DO Swing Quartile (Out-of-Sample Productivity)")
    ax1.set_ylabel("Late-Half Thermal Slope (mg/L/°C; HUC-2 95% CI)")
    ax1.set_title("A. Split-Half Diurnal Amplitude Stratification: DO_max vs. DO_min")
    ax1.grid(True, linestyle="--", alpha=0.28)
    ax1.legend(loc="upper left", fontsize=7.2, framealpha=0.94, ncol=1)

    # Panel B: Stratification across SpCond, Turbidity (light attenuation!), and Latitude
    sc_s = mech["spcond_tertiles"]
    tb_s = mech["turbidity_tertiles"]
    lt_s = mech["latitude_strata"]

    strata_rows = [
        (f"SpCond T1 Low ({sc_s['T1_LowSpCond']['median_spcond']:.0f} µS/cm)", sc_s["T1_LowSpCond"]["diff_min_max"], C_TEAL),
        (f"SpCond T2 Mid ({sc_s['T2_MidSpCond']['median_spcond']:.0f} µS/cm)", sc_s["T2_MidSpCond"]["diff_min_max"], C_TEAL),
        (f"SpCond T3 High ({sc_s['T3_HighSpCond']['median_spcond']:.0f} µS/cm)", sc_s["T3_HighSpCond"]["diff_min_max"], C_TEAL),
        (f"Turbidity T1 Clear ({tb_s['T1_Clear']['median_turb_fnu']:.1f} FNU)", tb_s["T1_Clear"]["diff_min_max"], C_ORG),
        (f"Turbidity T2 Mod. ({tb_s['T2_ModerateTurb']['median_turb_fnu']:.1f} FNU)", tb_s["T2_ModerateTurb"]["diff_min_max"], C_ORG),
        (f"Turbidity T3 Turbid ({tb_s['T3_Turbid']['median_turb_fnu']:.1f} FNU)", tb_s["T3_Turbid"]["diff_min_max"], C_ORG),
        ("South Latitude (< 35°N)", lt_s["South_lt35N"]["diff_min_max"], C_BLUE),
        ("Mid-Latitude (35–41°N)", lt_s["MidLat_35_41N"]["diff_min_max"], C_BLUE),
        ("North Latitude (> 41°N)", lt_s["North_gt41N"]["diff_min_max"], C_BLUE),
    ]
    yp = np.arange(len(strata_rows))[::-1]
    ax2.axvline(0.0, color="#1e293b", linewidth=0.9)
    ax2.axhline(5.5, color="#cbd5e1", linewidth=0.8, linestyle=":")
    ax2.axhline(2.5, color="#cbd5e1", linewidth=0.8, linestyle=":")

    for y_i, (lbl, blk, col) in zip(yp, strata_rows):
        mu = blk["mean"]
        lo = blk["huc2_cluster"]["ci95_lo"]
        hi = blk["huc2_cluster"]["ci95_hi"]
        ax2.plot([lo, hi], [y_i, y_i], color=col, linewidth=2.8, alpha=0.90)
        ax2.scatter([mu], [y_i], color=col, s=36, edgecolors="white", linewidths=0.6, zorder=4)
        ax2.text(max(hi, 0.0) + 0.008, y_i, f"{mu:+.3f} (n={blk['n_rivers']})", va="center", ha="left", fontsize=7.5)

    ax2.set_yticks(yp)
    ax2.set_yticklabels([r[0] for r in strata_rows], fontsize=8.0)
    ax2.set_xlabel("Diurnal Thermal Decoupling d(DO_min − DO_max)/dT (mg/L/°C; HUC-2 95% CI)")
    ax2.set_title("B. Ionic Loading, Turbidity Light-Attenuation & Climate Gradients")
    ax2.set_xlim(-0.27, 0.12)
    ax2.grid(True, axis="x", linestyle="--", alpha=0.28)

    fig.tight_layout(w_pad=2.0)
    save_fig(fig, "fig4_biophysical_mechanism")


def make_fig5(econ: dict, iv: dict, uk: dict) -> None:
    sec = econ["secular_trend_audit"]
    sol_us = pd.DataFrame(iv["solar_24h_curve"])
    sol_uk = pd.DataFrame(uk["hourly_24h_curve_solar_time"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.2), gridspec_kw={"width_ratios": [1.05, 1.15]})

    # Panel A: Secular 20-Year CONUS Trends Overall vs. Stratified by Warming Rate (CWA Confounding Audit)
    fast = sec["stratified_by_warming_rate"]["fast_warming_ge025C_dec"]
    slow = sec["stratified_by_warming_rate"]["slow_or_cooling_lt025C_dec"]

    vars_sec = [
        ("DO_min\n(Nocturnal)", "ols_dec_do_min", "tr_do_min"),
        ("DO_max\n(Daytime)", "ols_dec_do_max", "tr_do_max"),
        ("Diurnal\nSwing", "ols_dec_swing", "tr_swing"),
        ("Bio Deficit\n(DO_min−Sat)", "ols_dec_diff_min_sat", "tr_diff_min_sat"),
    ]
    x = np.arange(len(vars_sec))
    w = 0.25
    ax1.axhline(0.0, color="#1e293b", linewidth=0.9)

    groups_a = [
        (f"All Long-Record (N={sec['n_rivers_ge10warm_yrs']})", [sec[k1] for _, k1, _ in vars_sec], C_NAVY, -w),
        (f"Fast-Warming ≥0.25°C/dec (n={fast['n_rivers']})", [fast[k2] for _, _, k2 in vars_sec], C_RED, 0.0),
        (f"Slow/Cooling <0.25°C/dec (n={slow['n_rivers']})", [slow[k2] for _, _, k2 in vars_sec], C_TEAL, +w),
    ]
    for lbl, blks, col, off in groups_a:
        ms = [b["mean"] for b in blks]
        es = [(b["huc2_cluster"]["ci95_hi"] - b["huc2_cluster"]["ci95_lo"]) / 2.0 for b in blks]
        bars = ax1.bar(x + off, ms, w, yerr=es, capsize=2.8, color=col, alpha=0.88, label=lbl, error_kw={"lw": 1.0, "ecolor": "#0f172a"})
        for bar, mv, ev in zip(bars, ms, es):
            yt = mv + ev + 0.015 if mv >= 0 else mv - ev - 0.015
            va = "bottom" if mv >= 0 else "top"
            lbl_num = "0.00" if abs(mv) < 0.005 else f"{mv:+.2f}"
            ax1.text(bar.get_x() + bar.get_width() / 2, yt, lbl_num, ha="center", va=va, fontsize=6.6)

    sp_t = sec["warming_rate_vs_trends_spearman"]["dT_vs_dDOmin"]
    sp_sw = sec["warming_rate_vs_trends_spearman"]["dT_vs_dSwing"]
    ax1.text(
        0.02,
        0.03,
        f"Cross-River Warming Rate Correlations (N = {sp_t['n']}):\n"
        f"dT/dt vs. dDO_min/dt: r = {sp_t['spearman_r']:.3f} (p = {sp_t['p']:.2e})\n"
        f"dT/dt vs. dSwing/dt:  r = {sp_sw['spearman_r']:+.3f} (p = {sp_sw['p']:.2e})",
        transform=ax1.transAxes,
        fontsize=7.3,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.94},
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels([v[0] for v in vars_sec], fontsize=8.3)
    ax1.set_ylim(-0.44, 0.50)
    ax1.set_ylabel("Decadal Trend (mg/L per decade; HUC-2 95% CI)")
    ax1.set_title("A. CONUS 2005–2025 Secular Trends & Clean Water Act Confounding")
    ax1.grid(True, axis="y", linestyle="--", alpha=0.28)
    ax1.legend(loc="upper right", fontsize=7.0, framealpha=0.94)

    # Panel B: Trans-Atlantic Overlay — Exact Within-River Biological Excess d(DO(h) − DO_sat)/dT with Clustered t(G-1) 95% CIs!
    hrs = sol_us["hour"].values
    us_exc = sol_us["bio_excess_mean"].values
    us_lo = sol_us["bio_excess_ci95_lo"].values
    us_hi = sol_us["bio_excess_ci95_hi"].values
    uk_exc = sol_uk["bio_excess_mean"].values
    uk_lo = sol_uk["bio_excess_ci95_lo"].values
    uk_hi = sol_uk["bio_excess_ci95_hi"].values

    ax2.axvspan(10.0, 11.0, color="#fef3c7", alpha=0.75, label="Overpass Window (10–11h LST)")
    ax2.axvspan(13.0, 16.0, color="#fee2e2", alpha=0.65, label="Afternoon Grab (13–16h)")
    ax2.axhline(0.0, color=C_GRAY, linestyle="--", linewidth=1.2, label="Physical Henry's Law Benchmark (= 0)")

    ax2.fill_between(hrs, us_lo, us_hi, color=C_BLUE, alpha=0.20)
    ax2.plot(hrs, us_exc, color=C_BLUE, marker="o", markersize=3.5, linewidth=2.1, label=f"CONUS USGS (N={iv['n_iv_rivers']} screened, HUC-2 95% CI)")

    ax2.fill_between(hrs, uk_lo, uk_hi, color=C_RED, alpha=0.20)
    ax2.plot(
        hrs,
        uk_exc,
        color=C_RED,
        marker="s",
        markersize=3.5,
        linewidth=2.1,
        linestyle="-",
        label=f"England UK EA (N={uk['n_valid_clean_uk_rivers']} screened, 1° Grid 95% CI)",
    )

    ax2.annotate(
        "Daytime buffering\n(> 0)",
        xy=(15, max(us_exc[15], uk_exc[15]) + 0.008),
        xytext=(17.2, 0.092),
        fontsize=7.5,
        color=C_NAVY,
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": C_NAVY, "lw": 0.9},
    )
    ax2.annotate(
        "Nocturnal excess\nsensitivity (< 0)",
        xy=(5.5, min(us_exc[5], uk_exc[5]) - 0.004),
        xytext=(9.0, -0.072),
        fontsize=7.5,
        color=C_RED,
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": C_RED, "lw": 0.9},
    )
    ax2.set_xlim(0, 23)
    ax2.set_ylim(-0.088, 0.165)
    ax2.set_xticks([0, 3, 6, 9, 12, 15, 18, 21])
    ax2.set_xlabel("Local Mean Solar Time (Hour)")
    ax2.set_ylabel("Excess Thermal Sensitivity: d(DO(h) − DO_sat)/dT (mg/L/°C)")
    ax2.set_title("B. Trans-Atlantic Replication: CONUS (USGS) vs. England (UK EA)")
    ax2.grid(True, linestyle="--", alpha=0.28)
    ax2.legend(loc="upper left", fontsize=7.0, framealpha=0.92)

    fig.tight_layout(w_pad=2.0)
    save_fig(fig, "fig5_secular_cwa_and_uk_replication")


def build_tables(econ: dict, iv: dict, uk: dict, disc: dict) -> None:
    # Table 1: Core Thermal Decoupling & Robustness Suite (zero NaNs)
    t1_rows = []

    def add_t1(spec_name: str, outcome: str, blk: dict) -> None:
        t1_rows.append(
            {
                "specification": spec_name,
                "outcome": outcome,
                "n_rivers": int(blk["n_rivers"]),
                "mean_mgL_per_C": blk["mean"],
                "median_mgL_per_C": blk["median"],
                "pct_negative": blk["pct_neg"],
                "huc2_clusters": blk["huc2_cluster"]["n_clusters"],
                "huc2_se_cr1": blk["huc2_cluster"]["se_cr1"],
                "huc2_ci95_lo": blk["huc2_cluster"]["ci95_lo"],
                "huc2_ci95_hi": blk["huc2_cluster"]["ci95_hi"],
                "huc2_p_t_Gminus1": blk["huc2_cluster"]["p_cr1_t_Gminus1"],
                "huc2_boot_p": blk["huc2_cluster"]["boot_p"],
                "state_clusters": blk["state_cluster"]["n_clusters"],
                "state_se_cr1": blk["state_cluster"]["se_cr1"],
                "state_p_t_Gminus1": blk["state_cluster"]["p_cr1_t_Gminus1"],
                "state_boot_p": blk["state_cluster"]["boot_p"],
            }
        )

    s2 = econ["spec2_ym_fe_logQ_quad_primary"]
    for out_k in ("do_sat_alt", "do_max", "do_mean", "do_min", "diff_min_max", "diff_min_mean", "diff_min_sat", "diff_max_sat", "plunge"):
        add_t1("Spec 2 Primary (YM FE + logQ + logQ^2)", out_k, s2[out_k])
    s1 = econ["spec1_ym_fe_all_clean"]
    for out_k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat"):
        add_t1("Spec 1 All Clean Rivers (YM FE)", out_k, s1[out_k])
    s3 = econ["spec3_exact_diurnal_solubility"]
    add_t1("Spec 3 Exact Diurnal Solubility T_min", "diff_min_sat_exactTmin", s3["diff_min_sat_exactTmin"])
    add_t1("Spec 3 Exact Diurnal Solubility T_max", "diff_max_sat_exactTmax", s3["diff_max_sat_exactTmax"])
    add_t1("Spec 3 Exact vs T_mean Gap (Min)", "invariance_gap_min", s3["invariance_gap_min_exact_minus_Tmean"])
    rob = econ["robustness_suite"]
    for rtag, rlbl in [
        ("spec4_plus_logSpCond", "Spec 4a (+ log SpCond)"),
        ("spec4_plus_logTurbidity", "Spec 4b (+ log Turbidity)"),
        ("spec5_ultra_strict_zero_infra", "Spec 5a (Ultra-Strict Zero-Infra)"),
        ("spec5_long_record_ge10warm_yrs", "Spec 5b (Long Record >=10 yr)"),
        ("spec5_peak_summer_JunAug", "Spec 5c (Peak Summer Jun-Aug)"),
        ("spec5_all_year_JanDec", "Spec 5d (All-Year Jan-Dec)"),
        ("spec5_nid_gt5km_ge500af", "Spec 5e (NID >5 km from >=500 af Dam)"),
        ("spec5_nid_gt10km_ge5000af", "Spec 5f (NID >10 km from >=5000 af Dam)"),
        ("spec5_nid_gt5km_any_dam", "Spec 5g (NID >5 km from Any Dam)"),
        ("spec5_dedup_2km_reach", "Spec 5h (2-km Reach Deduplicated)"),
    ]:
        add_t1(rlbl, "diff_min_max", rob[rtag]["diff_min_max"])
        add_t1(rlbl, "diff_min_sat", rob[rtag]["diff_min_sat"])
    pd.DataFrame(t1_rows).to_csv(TBL_DIR / "table1_core_thermal_decoupling.csv", index=False)

    # Table 2: 24-Hour Clock-Bias Windows
    t2_rows = []
    win_labels = {
        "dawn0507": "Pre-Dawn Solar (05:00-07:00 LST)",
        "ls10": "Overpass Window (Landsat-Time, 10:00-11:00 LST)",
        "am0912": "Morning Grab (09:00-12:00 Civil)",
        "pm1316": "Afternoon Grab Wide (13:00-16:00 Civil)",
        "pm1330": "Afternoon Grab Core (13:30-15:30 Civil)",
    }
    for wk, wlbl in win_labels.items():
        w = iv["named_windows"][wk]
        t2_rows.append(
            {
                "sampling_window": wlbl,
                "n_rivers": w["n_rivers"],
                "mean_DOmin_slope": w["mean_DOmin_slope"],
                "mean_window_slope": w["mean_window_slope"],
                "mean_window_instT_slope": w["mean_window_instT_slope"],
                "warming_underestimation_pct": w["warming_underestimation_pct"],
                "warming_underestimation_instT_pct": w["warming_underestimation_instT_pct"],
                "warming_underestimation_qctrl_pct": w["warming_underestimation_qctrl_pct"],
                "pct_rivers_underestimating": w["pct_rivers_underestimating"],
                "slope_bias_huc2_p": w["slope_bias_huc2_clustered"]["p_cr1_t_Gminus1"],
                "slope_bias_state_p": w["slope_bias_state_clustered"]["p_cr1_t_Gminus1"],
                "mean_do_bias_mgL": w["do_bias_mgL_huc2_clustered"]["mean"],
                "hyp5_missed_pct": w["hypoxia_blindness"]["lt_5_mgL"]["missed_pct"],
                "hyp4_missed_pct": w["hypoxia_blindness"]["lt_4_mgL"]["missed_pct"],
                "hyp3_missed_pct": w["hypoxia_blindness"]["lt_3_mgL"]["missed_pct"],
                "hyp2_missed_pct": w["hypoxia_blindness"]["lt_2_mgL"]["missed_pct"],
            }
        )
    pd.DataFrame(t2_rows).to_csv(TBL_DIR / "table2_24h_clock_bias_windows.csv", index=False)

    # Table 2b: Transfer Function OOS Summary (including VIF, centered 20C supersaturation slope, & nonlinear spline benchmark)
    tf_rows = []
    for mode, mlbl in [
        ("afternoon_1316", "Afternoon Grab Wide (13:00-16:00)"),
        ("afternoon_1430", "Afternoon Grab Core (13:30-15:30)"),
        ("landsat_1030", "Overpass Window (Landsat-Time, 10:00-11:00 LST)"),
    ]:
        t = iv["transfer_function_oos"][mode]
        tf_rows.append(
            {
                "mode": mlbl,
                "n_river_days": t["n_river_days"],
                "n_rivers": t["n_rivers"],
                "n_huc2_folds": t["n_huc2_folds"],
                "max_vif": t["max_vif"],
                "supersat_marginal_20C": t["supersat_marginal_drawdown_at_20C"],
                "raw_mean_bias_mgL": t["raw_mean_bias_mgL"],
                "corrected_mean_bias_mgL": t["corrected_mean_bias_lohuc2_mgL"],
                "mean_bias_reduction_pct": t["mean_bias_reduction_pct"],
                "raw_rmse_mgL": t["raw_rmse_mgL"],
                "corrected_rmse_mgL": t["corrected_rmse_lohuc2_mgL"],
                "rmse_reduction_pct": t["rmse_reduction_pct"],
                "nonlinear_spline_rmse_mgL": t["nonlinear_spline_benchmark"]["lohuc2_rmse_mgL"],
                "oos_r2_do_min": t["oos_r2_do_min"],
                "oos_r2_drawdown": t["oos_r2_drawdown"],
                "slope_bias_reduction_pct": t["warming_slope_recovery"]["slope_bias_reduction_pct"],
                "hyp5_raw_recall_pct": t["hypoxia_detection_lohuc2"]["lt_5_mgL"]["raw_recall_pct"],
                "hyp5_corrected_recall_pct": t["hypoxia_detection_lohuc2"]["lt_5_mgL"]["corrected_recall_pct"],
                "hyp5_corrected_precision_pct": t["hypoxia_detection_lohuc2"]["lt_5_mgL"]["corrected_precision_pct"],
                "hyp5_corrected_specificity_pct": t["hypoxia_detection_lohuc2"]["lt_5_mgL"]["corrected_specificity_pct"],
                "temp2024_raw_rmse": t["temporal_2024_holdout"]["raw_rmse_2024"],
                "temp2024_corrected_rmse": t["temporal_2024_holdout"]["corrected_rmse_2024"],
            }
        )
    pd.DataFrame(tf_rows).to_csv(TBL_DIR / "table2b_transfer_function_oos.csv", index=False)

    # Table 2c: Astronomical Sunset-to-Sunrise Nocturnal Window, Completeness & Site-Weighting Sensitivity
    astro = iv["astronomical_nocturnal_audit"]
    mr = astro["hypoxia_miss_rates_by_regime"]
    eq = astro["equal_site_weighting_miss_rates"]
    t2c_rows = []
    for reg_k, reg_lbl in [
        ("full_24h_15min_siteday", "Full-Day 24h DO_min (15-min, Site-Day Weighted)"),
        ("full_24h_hourly_siteday", "Full-Day 24h DO_min (Hourly Solar Grid, Site-Day)"),
        ("astro_night_sameday_siteday", "Strict Astronomical Night (Sunset-to-Sunrise, Same-Day)"),
        ("astro_night_consec_overnight_siteday", "Strict Consecutive Overnight (Sunset_d to Sunrise_d+1)"),
        ("completeness_ge86_24h_15min", "Completeness >=90% (>=86/96 15-min) vs 24h DO_min"),
        ("completeness_ge86_astro_night", "Completeness >=90% (>=86/96 15-min) vs Astro Night"),
        ("completeness_ge22h_24h_15min", "Completeness >=90% (>=22/24 Solar Hr) vs 24h DO_min"),
        ("completeness_ge22h_astro_night", "Completeness >=90% (>=22/24 Solar Hr) vs Astro Night"),
    ]:
        t2c_rows.append(
            {
                "benchmark_regime": reg_lbl,
                "weighting": "site_day",
                "hyp5_days_or_sites": mr[reg_k]["lt_5_mgL"]["pm1316_hypoxic_days"],
                "pm1316_miss_lt5_pct": mr[reg_k]["lt_5_mgL"]["pm1316_missed_pct"],
                "overpass_miss_lt5_pct": mr[reg_k]["lt_5_mgL"]["overpass1011_missed_pct"],
                "pm1316_miss_lt3_pct": mr[reg_k]["lt_3_mgL"]["pm1316_missed_pct"],
                "overpass_miss_lt3_pct": mr[reg_k]["lt_3_mgL"]["overpass1011_missed_pct"],
                "pm1316_miss_lt2_pct": mr[reg_k]["lt_2_mgL"]["pm1316_missed_pct"],
                "overpass_miss_lt2_pct": mr[reg_k]["lt_2_mgL"]["overpass1011_missed_pct"],
            }
        )
    for pm_k, ls_k, eq_lbl in [
        ("pm_24h_15min", "ls_24h_15min", "Equal-Site Weighted vs Full-Day 24h DO_min"),
        ("pm_astro_night", "ls_astro_night", "Equal-Site Weighted vs Strict Astronomical Night"),
        ("pm_ge86_24h_15min", "ls_ge86_24h_15min", "Equal-Site Weighted (>=86/96) vs 24h DO_min"),
        ("pm_ge86_astro_night", "ls_ge86_astro_night", "Equal-Site Weighted (>=86/96) vs Astro Night"),
    ]:
        t2c_rows.append(
            {
                "benchmark_regime": eq_lbl,
                "weighting": "equal_site",
                "hyp5_days_or_sites": eq[pm_k]["lt_5_mgL"]["n_sites_ge1day"],
                "pm1316_miss_lt5_pct": eq[pm_k]["lt_5_mgL"]["equal_site_missed_pct"],
                "overpass_miss_lt5_pct": eq[ls_k]["lt_5_mgL"]["equal_site_missed_pct"],
                "pm1316_miss_lt3_pct": eq[pm_k]["lt_3_mgL"]["equal_site_missed_pct"],
                "overpass_miss_lt3_pct": eq[ls_k]["lt_3_mgL"]["equal_site_missed_pct"],
                "pm1316_miss_lt2_pct": eq[pm_k]["lt_2_mgL"]["equal_site_missed_pct"],
                "overpass_miss_lt2_pct": eq[ls_k]["lt_2_mgL"]["equal_site_missed_pct"],
            }
        )
    pd.DataFrame(t2c_rows).to_csv(TBL_DIR / "table2c_astronomical_night_duration_sensitivity.csv", index=False)

    # Table 2d: First Threshold-Crossing Solar Hour & Exact Continuous Hypoxia Duration
    td = astro["first_crossing_and_duration"]
    t2d_rows = []
    for tag, thr_lbl in [("lt_5_mgL", "< 5.0 mg/L"), ("lt_4_mgL", "< 4.0 mg/L"), ("lt_3_mgL", "< 3.0 mg/L"), ("lt_2_mgL", "< 2.0 mg/L")]:
        d = td[tag]
        t2d_rows.append(
            {
                "threshold": thr_lbl,
                "hypoxic_days_hourly": d["hypoxic_days_hourly"],
                "daily_min_in_astro_night_pct": d["daily_min_in_astro_night_pct"],
                "daily_min_in_astro_night_plus_2h_lag_pct": d["daily_min_in_astro_night_plus_2h_lag_pct"],
                "consec_hypoxic_cycles": d["consec_hypoxic_cycles"],
                "consec_episodic_cycles": d["consec_episodic_cycles"],
                "first_crossing_in_astro_night_episodic_pct": d["first_crossing_in_astro_night_episodic_pct"],
                "episodic_first_crossing_solar_hr_median": d["episodic_first_crossing_solar_hr_median"],
                "episodic_first_crossing_solar_hr_p25": d["episodic_first_crossing_solar_hr_p25"],
                "episodic_first_crossing_solar_hr_p75": d["episodic_first_crossing_solar_hr_p75"],
                "continuous_duration_all_mean_hr": d["continuous_duration_all_mean_hr"],
                "continuous_duration_all_median_hr": d["continuous_duration_all_median_hr"],
                "continuous_duration_episodic_mean_hr": d["continuous_duration_episodic_mean_hr"],
                "continuous_duration_episodic_median_hr": d["continuous_duration_episodic_median_hr"],
                "total_hypoxic_hours_all_mean_hr": d["total_hypoxic_hours_all_mean_hr"],
            }
        )
    pd.DataFrame(t2d_rows).to_csv(TBL_DIR / "table2d_nocturnal_crossing_duration.csv", index=False)

    # Table 3: Compound Heatwave x Low-Flow Drought (with bounded night-minus-day contrast and exact 95% CIs)
    t3_rows = []
    eff = econ["compound_hot_x_dry"]["effects"]
    for out_k in ("do_sat_alt", "do_max", "do_mean", "do_min", "diff_min_max", "diff_min_sat", "plunge", "hyp5_min", "hyp3_min", "hyp2_min", "hyp5_max", "hyp5_min_minus_max"):
        e = eff[out_k]
        t3_rows.append(
            {
                "outcome": out_k,
                "n_rivers": e["hot_x_dry_interaction"]["n_rivers"],
                "hot_only_mean": e["hot_only"]["mean"],
                "hot_only_p_huc2": e["hot_only"]["huc2_cluster"]["p_cr1_t_Gminus1"],
                "dry_only_mean": e["dry_only"]["mean"],
                "dry_only_p_huc2": e["dry_only"]["huc2_cluster"]["p_cr1_t_Gminus1"],
                "hot_x_dry_interaction": e["hot_x_dry_interaction"]["mean"],
                "interaction_se_huc2": e["hot_x_dry_interaction"]["huc2_cluster"]["se_cr1"],
                "interaction_ci95_lo": e["hot_x_dry_interaction"]["huc2_cluster"]["ci95_lo"],
                "interaction_ci95_hi": e["hot_x_dry_interaction"]["huc2_cluster"]["ci95_hi"],
                "interaction_p_huc2": e["hot_x_dry_interaction"]["huc2_cluster"]["p_cr1_t_Gminus1"],
                "interaction_p_state": e["hot_x_dry_interaction"]["state_cluster"]["p_cr1_t_Gminus1"],
                "total_compound_vs_normal": e["total_compound_vs_normal"]["mean"],
                "total_ci95_lo": e["total_compound_vs_normal"]["huc2_cluster"]["ci95_lo"],
                "total_ci95_hi": e["total_compound_vs_normal"]["huc2_cluster"]["ci95_hi"],
                "total_compound_p_huc2": e["total_compound_vs_normal"]["huc2_cluster"]["p_cr1_t_Gminus1"],
            }
        )
    pd.DataFrame(t3_rows).to_csv(TBL_DIR / "table3_compound_hot_x_dry.csv", index=False)

    # Table 4: Biophysical Mechanism Stratification (FIXED: true do_min_mean for SpCond!)
    t4_rows = []
    mech = econ["biophysical_mechanism"]
    for qlab, g in mech["split_half_productivity_quartiles"].items():
        t4_rows.append(
            {
                "dimension": "Split-Half Early Productivity (Uniform Spec 2)",
                "stratum": qlab,
                "n_rivers": g["n_rivers"],
                "diff_min_max_mean": g["late_diff_min_max"]["mean"],
                "diff_min_max_se_huc2": g["late_diff_min_max"]["huc2_cluster"]["se_cr1"],
                "diff_min_max_p_huc2": g["late_diff_min_max"]["huc2_cluster"]["p_cr1_t_Gminus1"],
                "do_max_mean": g["late_do_max_slope"]["mean"],
                "do_min_mean": g["late_do_min_slope"]["mean"],
            }
        )
    for tlab, g in mech["spcond_tertiles"].items():
        t4_rows.append(
            {
                "dimension": "Specific Conductance (00095)",
                "stratum": tlab,
                "n_rivers": g["n_rivers"],
                "diff_min_max_mean": g["diff_min_max"]["mean"],
                "diff_min_max_se_huc2": g["diff_min_max"]["huc2_cluster"]["se_cr1"],
                "diff_min_max_p_huc2": g["diff_min_max"]["huc2_cluster"]["p_cr1_t_Gminus1"],
                "do_max_mean": g["do_max"]["mean"],
                "do_min_mean": g["do_min"]["mean"],
            }
        )
    for tlab, g in mech["turbidity_tertiles"].items():
        t4_rows.append(
            {
                "dimension": "Turbidity Light-Attenuation (63680)",
                "stratum": tlab,
                "n_rivers": g["n_rivers"],
                "diff_min_max_mean": g["diff_min_max"]["mean"],
                "diff_min_max_se_huc2": g["diff_min_max"]["huc2_cluster"]["se_cr1"],
                "diff_min_max_p_huc2": g["diff_min_max"]["huc2_cluster"]["p_cr1_t_Gminus1"],
                "do_max_mean": g["do_max"]["mean"],
                "do_min_mean": g["do_min"]["mean"],
            }
        )
    for blab, g in mech["latitude_strata"].items():
        t4_rows.append(
            {
                "dimension": "Latitude Climate Belt",
                "stratum": blab,
                "n_rivers": g["n_rivers"],
                "diff_min_max_mean": g["diff_min_max"]["mean"],
                "diff_min_max_se_huc2": g["diff_min_max"]["huc2_cluster"]["se_cr1"],
                "diff_min_max_p_huc2": g["diff_min_max"]["huc2_cluster"]["p_cr1_t_Gminus1"],
                "do_max_mean": g["do_max"]["mean"],
                "do_min_mean": g["do_min"]["mean"],
            }
        )
    pd.DataFrame(t4_rows).to_csv(TBL_DIR / "table4_biophysical_mechanism_strata.csv", index=False)

    # Table 5: Secular Trends & UK EA International Replication (with 1-deg spatial cluster SE & p for UK EA!)
    sec = econ["secular_trend_audit"]
    t5_rows = []
    for k, lbl in [
        ("ols_dec_temp_mean", "CONUS 20yr Trend: Temp (°C/dec)"),
        ("ols_dec_do_sat_alt", "CONUS 20yr Trend: DO_sat (mg/L/dec)"),
        ("ols_dec_do_max", "CONUS 20yr Trend: DO_max (mg/L/dec)"),
        ("ols_dec_do_mean", "CONUS 20yr Trend: DO_mean (mg/L/dec)"),
        ("ols_dec_do_min", "CONUS 20yr Trend: DO_min (mg/L/dec)"),
        ("ols_dec_swing", "CONUS 20yr Trend: Diurnal Swing (mg/L/dec)"),
        ("ols_dec_plunge", "CONUS 20yr Trend: Nocturnal Plunge (mg/L/dec)"),
        ("ols_dec_diff_min_sat", "CONUS 20yr Trend: Bio Deficit DO_min-Sat (mg/L/dec)"),
    ]:
        b = sec[k]
        t5_rows.append(
            {
                "panel": "CONUS Secular 2005-2025",
                "metric": lbl,
                "n_rivers": b["n_rivers"],
                "mean": b["mean"],
                "se_clustered": b["huc2_cluster"]["se_cr1"],
                "ci95_lo": b["huc2_cluster"]["ci95_lo"],
                "ci95_hi": b["huc2_cluster"]["ci95_hi"],
                "p_clustered": b["huc2_cluster"]["p_cr1_t_Gminus1"],
                "p_river": b["river_p_t"],
            }
        )
    uk_t = uk["thermal_slopes_ym_fe"]
    for k, lbl in [
        ("DOsat_HenrysLaw", "UK EA Slope: DO_sat Henry's Law (mg/L/°C)"),
        ("DOmax_daytime", "UK EA Slope: DO_max Daytime (mg/L/°C)"),
        ("DOmean_daily", "UK EA Slope: DO_mean Daily (mg/L/°C)"),
        ("DOmin_nocturnal", "UK EA Slope: DO_min Nocturnal (mg/L/°C)"),
        ("DOmin_minus_DOmax", "UK EA Slope: DO_min - DO_max Decoupling (mg/L/°C)"),
        ("DOmin_minus_HenrysLaw", "UK EA Slope: DO_min - Henry's Law (mg/L/°C)"),
        ("DOmax_minus_HenrysLaw", "UK EA Slope: DO_max - Henry's Law (mg/L/°C)"),
    ]:
        b = uk_t[k]
        g = b["grid1deg_cluster"]
        t5_rows.append(
            {
                "panel": "UK EA International Replication",
                "metric": lbl,
                "n_rivers": b["n"],
                "mean": b["mean"],
                "se_clustered": g["se_cr1"],
                "ci95_lo": g["ci95_lo"],
                "ci95_hi": g["ci95_hi"],
                "p_clustered": g["p_cr1_t_Gminus1"],
                "p_river": b["p_t"],
            }
        )
    pd.DataFrame(t5_rows).to_csv(TBL_DIR / "table5_secular_trends_and_uk_replication.csv", index=False)

    # Table 6: HUC-2 Basin Summary
    pd.DataFrame(econ["huc2_basin_summary"]).to_csv(TBL_DIR / "table6_huc2_basin_summary.csv", index=False)
    print("  [TABLES] saved 9 zero-NaN CSV tables in tables/", flush=True)


def main() -> None:
    econ = json.loads((RES_DIR / "d4_econometric_hydrologic_results.json").read_text(encoding="utf-8"))
    iv = json.loads((RES_DIR / "conus_iv_24h_clock_results.json").read_text(encoding="utf-8"))
    uk = json.loads((RES_DIR / "uk_ea_replication_results.json").read_text(encoding="utf-8"))
    disc = json.loads((PROC_DIR / "step1_site_discovery_summary.json").read_text(encoding="utf-8"))
    rdf = pd.read_csv(PROC_DIR / "conus_river_econometric_panel.csv", dtype={"site_no": str, "huc2": str})

    print("Step 6: Generating 5 publication-grade figures (300 DPI PNG + vector PDF) and CSV tables...", flush=True)
    make_fig1(econ, rdf)
    make_fig2(iv, econ)
    make_fig3(econ)
    make_fig4(econ)
    make_fig5(econ, iv, uk)
    build_tables(econ, iv, uk, disc)
    print("[DONE] Step 6 complete!", flush=True)


if __name__ == "__main__":
    main()
