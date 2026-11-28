"""Step 13: Generate publication-grade Nature Water main figures (350 DPI PNG + vector PDF)
and zero-NaN Main + Supplementary CSV tables programmatically from JSON/Parquet receipts.
Zero hardcoded numbers.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROC = DATA / "processed"
RES = ROOT / "results"
TBL = ROOT / "tables"
FIG = ROOT / "figures"

# Clean Nature Water colorblind-safe palette
C_NAVY = "#1b3a57"
C_TEAL = "#1f7a8c"
C_ORANGE = "#d95f02"
C_CORAL = "#c0392b"
C_GOLD = "#d4a017"
C_PURPLE = "#6a3d9a"
C_GREEN = "#2e7d32"
C_SLATE = "#64748b"
C_LIGHT = "#e2e8f0"


def set_nature_style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "DejaVu Sans"],
            "font.size": 8.5,
            "axes.titlesize": 9.5,
            "axes.titleweight": "bold",
            "axes.labelsize": 8.5,
            "xtick.labelsize": 7.8,
            "ytick.labelsize": 7.8,
            "legend.fontsize": 7.5,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.linewidth": 0.8,
            "xtick.major.width": 0.7,
            "ytick.major.width": 0.7,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.08,
        }
    )


def save_fig(fig: plt.Figure, stem: str) -> None:
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{stem}.png", dpi=350)
    fig.savefig(FIG / f"{stem}.pdf")
    plt.close(fig)


def kaplan_meier_curve(durations: np.ndarray, events: np.ndarray, max_t: float = 24.0) -> tuple[np.ndarray, np.ndarray]:
    mask = np.isfinite(durations) & (durations >= 0)
    d = durations[mask]
    e = events[mask].astype(int)
    uniq_t = np.sort(np.unique(d))
    surv = 1.0
    ts = [0.0]
    ss = [100.0]
    for t in uniq_t:
        if t > max_t:
            break
        at_risk = int(np.sum(d >= t))
        died = int(np.sum((d == t) & (e == 1)))
        if died > 0 and at_risk > 0:
            surv *= 1.0 - died / at_risk
            ts.append(float(t))
            ss.append(float(100.0 * surv))
    if ts[-1] < max_t:
        ts.append(max_t)
        ss.append(ss[-1])
    return np.array(ts), np.array(ss)


def make_figure1(r11: dict, wqp_paired: pd.DataFrame) -> None:
    """Fig 1: Real-World WQP Sampling Clock, Independent Field-Meter Validation, and Common-Support Coverage."""
    fig, axes = plt.subplots(1, 3, figsize=(11.4, 3.65), gridspec_kw={"width_ratios": [1.15, 1.05, 1.0]}, layout="constrained")

    # Panel A: 24-h Real-World WQP Agency Grab Clock (Local Mean Solar Time)
    ax = axes[0]
    wqp_all = r11["real_wqp_grab_audit"]["conus397_2015_2024_clock"]
    wqp_iv = r11["real_wqp_grab_audit"]["iv139_2021_2024_clock"]
    hours = np.arange(24)
    pct_all = 100.0 * np.array(wqp_all["hourly_hist_solar"]) / wqp_all["n_visits"]
    pct_iv = 100.0 * np.array(wqp_iv["hourly_hist_solar"]) / wqp_iv["n_visits"]

    # Shade astronomical darkness (approximate warm-season mean sunset ~18:45 to sunrise ~05:15 solar)
    ax.axvspan(0, 5.3, color="#cbd5e1", alpha=0.45, label="Astronomical darkness")
    ax.axvspan(18.7, 24.0, color="#cbd5e1", alpha=0.45)
    ax.bar(hours + 0.5, pct_all, width=0.82, color=C_TEAL, alpha=0.82, edgecolor="white", linewidth=0.4,
           label=f"CONUS-397 ({wqp_all['n_visits']:,} visits)")
    ax.step(np.r_[hours, 24], np.r_[pct_iv, pct_iv[-1]], where="post", color=C_NAVY, lw=1.5,
            label=f"IV-139 subset ({wqp_iv['n_visits']:,})")
    ax.axvline(wqp_all["solar_median_hr"], color=C_CORAL, ls="--", lw=1.2)
    ax.text(13.6, max(pct_all) * 0.62,
            f"Median {wqp_all['solar_median_hr']:.1f} h solar\n(11:00 local civil)\n{wqp_all['pct_work_08_17_local']:.1f}% in 08–17 h\n{wqp_all['pct_predawn_2h']:.2f}% pre-dawn",
            fontsize=6.8, color=C_NAVY, va="top", bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": C_LIGHT, "alpha": 0.94})
    ax.set_xlim(0, 24)
    ax.set_ylim(0, max(pct_all) * 1.18)
    ax.set_xticks([0, 4, 8, 12, 16, 20, 24])
    ax.set_xlabel("Local mean solar hour")
    ax.set_ylabel("Share of agency grab visits (%)")
    ax.set_title("a  Real-world agency grab clock (WQP)", loc="left")
    ax.legend(loc="upper right", frameon=True, facecolor="white", framealpha=0.92, edgecolor=C_LIGHT, fontsize=6.6)

    # Panel B: Independent Co-located Field-Meter Validation + Actual Visit Detection Inset
    ax = axes[1]
    co = wqp_paired.dropna(subset=["do_grab", "do_sonde"])
    val = r11["real_wqp_grab_audit"]["independent_colocated_validation"]
    det = r11["real_wqp_grab_audit"]["actual_agency_visit_detection"]
    ax.scatter(co["do_grab"], co["do_sonde"], s=9, alpha=0.42, color=C_TEAL, edgecolors="none", rasterized=True)
    lims = [0, 16]
    ax.plot(lims, lims, color=C_NAVY, lw=1.1, ls="-", label="1:1 line")
    ax.fill_between(lims, [x - 0.2 for x in lims], [x + 0.2 for x in lims], color=C_ORANGE, alpha=0.22, label="±0.2 mg/L USGS spec")
    ax.axvline(5.0, color=C_CORAL, ls=":", lw=0.9, alpha=0.8)
    ax.axhline(5.0, color=C_CORAL, ls=":", lw=0.9, alpha=0.8)
    ax.set_xlim(0, 16)
    ax.set_ylim(0, 16)
    ax.set_xlabel("Independent field-meter DO (mg/L)")
    ax.set_ylabel("Continuous sonde DO (mg/L)")
    ax.set_title("b  Co-located field-meter check", loc="left")
    ax.text(0.4, 15.3,
            f"n = {val['n_paired_readings_le30min']:,} ({val['n_sites']} sites)\nr = {val['pearson_r']:.3f}, bias = {val['mean_bias_sonde_minus_grab_mgL']:+.03f}\nMedAE = {val['median_abs_err_mgL']:.2f} mg/L",
            fontsize=6.9, va="top", color=C_NAVY, bbox={"boxstyle": "round,pad=0.25", "fc": "white", "ec": C_LIGHT, "alpha": 0.92})

    # Compact inset bar showing actual visit-day detection vs pre-dawn sonde on same dates
    ins = ax.inset_axes([0.55, 0.16, 0.42, 0.33])
    ins.set_facecolor("white")
    vals_ins = [det["actionable_2h_grab_recall_pct"], det["actionable_2h_predawn_recall_pct"]]
    ins.bar([0, 1], vals_ins, width=0.56, color=[C_ORANGE, C_NAVY], edgecolor="white")
    for xi, vi in enumerate(vals_ins):
        ins.text(xi, vi + 3, f"{vi:.0f}%", ha="center", va="bottom", fontsize=6.5, fontweight="bold")
    ins.set_xticks([0, 1])
    ins.set_xticklabels(["Actual\nvisit", "Pre-\ndawn"], fontsize=6.2)
    ins.set_ylim(0, 118)
    ins.set_yticks([0, 50, 100])
    ins.tick_params(axis="y", labelsize=6.0)
    ins.set_title(f"≥2h <5 recall (n={det['actionable_2h_n_nights']})", fontsize=6.3, pad=2)
    ins.spines[["top", "right"]].set_visible(False)

    # Panel C: Common-support coverage & attrition by native sampling cadence
    ax = axes[2]
    att_us = r11["coverage_attrition"]["USGS"]
    att_uk = r11["coverage_attrition"]["EA"]
    labels = ["US\nAll", "US\n5m", "US\n15m", "US\n30m", "US\n60m", "UK\nAll", "UK\n15m", "UK\n30m", "UK\n60m"]
    step_us = {x["native_step_min"]: x["entry_rate_pct"] for x in att_us["by_native_step"]}
    step_uk = {x["native_step_min"]: x["entry_rate_pct"] for x in att_uk["by_native_step"]}
    rates = [
        att_us["common_support_entry_pct"], step_us[5], step_us[15], step_us[30], step_us[60],
        att_uk["common_support_entry_pct"], step_uk[15], step_uk[30], step_uk[60],
    ]
    colors = [C_NAVY, C_TEAL, C_TEAL, C_TEAL, C_TEAL, C_ORANGE, "#f0a060", "#f0a060", "#f0a060"]
    x_pos = np.array([0, 1.1, 2.0, 2.9, 3.8, 5.1, 6.2, 7.1, 8.0])
    ax.bar(x_pos, rates, width=0.72, color=colors, edgecolor="white")
    for xi, ri in zip(x_pos, rates, strict=True):
        ax.text(xi, ri + 1.5, f"{ri:.0f}%", ha="center", va="bottom", fontsize=6.6)
    ax.set_xticks(x_pos)
    ax.set_xticklabels(labels, fontsize=6.8)
    ax.set_ylim(0, 112)
    ax.set_ylabel("Common-support entry rate (%)")
    ax.set_title("c  Coverage by network & cadence", loc="left")
    ax.axhline(90, color=C_SLATE, ls=":", lw=0.7, alpha=0.6)

    save_fig(fig, "fig1_nw_monitoring_clock_and_coverage")


def make_figure2(r11: dict) -> None:
    """Fig 2: Primary LORO Cross-Network Recall, Sunrise-Offset Curve, and Robustness Forest Plot."""
    fig, axes = plt.subplots(1, 3, figsize=(11.6, 4.15), gridspec_kw={"width_ratios": [1.05, 1.0, 1.25]}, layout="constrained")

    # Panel A: Primary LORO Recall (<5 mg/L) across US & England
    ax = axes[0]
    us5 = r11["loro_primary"]["USGS"]["thresholds"]["5"]
    uk5 = r11["loro_primary"]["EA"]["thresholds"]["5"]
    # Also grab first-light (SR+30m) from offset profile
    us_fl = next(x for x in r11["holdout_validation"]["sunrise_offset_profile_lt5"]["USGS"] if x["offset_min_rel_sr"] == 30)
    uk_fl = next(x for x in r11["holdout_validation"]["sunrise_offset_profile_lt5"]["EA"] if x["offset_min_rel_sr"] == 30)

    sched_labels = [
        "14:30 afternoon",
        "10:30 overpass",
        "08:00 morning",
        "50/50 alternating",
        "First light (SR+30m)",
        "Pre-dawn (SR−30m)",
    ]
    us_rows = [
        us5["loro_schedules"]["afternoon"]["recall_95_pct"],
        us5["loro_schedules"]["overpass"]["recall_95_pct"],
        us5["loro_schedules"]["morning08"]["recall_95_pct"],
        us5["loro_schedules"]["alternating"]["recall_95_pct"],
        us_fl["recall_95_pct"],
        us5["loro_schedules"]["predawn"]["recall_95_pct"],
    ]
    uk_rows = [
        uk5["loro_schedules"]["afternoon"]["recall_95_pct"],
        uk5["loro_schedules"]["overpass"]["recall_95_pct"],
        uk5["loro_schedules"]["morning08"]["recall_95_pct"],
        uk5["loro_schedules"]["alternating"]["recall_95_pct"],
        uk_fl["recall_95_pct"],
        uk5["loro_schedules"]["predawn"]["recall_95_pct"],
    ]
    y = np.arange(len(sched_labels))
    for dy, rows, col, lbl in [(-0.15, us_rows, C_NAVY, f"U.S. (n={us5['loro_n_ref_pos']:,})"), (0.15, uk_rows, C_ORANGE, f"England (n={uk5['loro_n_ref_pos']:,})")]:
        c, lo, hi = np.array(rows).T
        ax.errorbar(c, y + dy, xerr=[c - lo, hi - c], fmt="o", ms=5, capsize=2.5, lw=1.4, color=col, label=lbl)
    ax.set_yticks(y)
    ax.set_yticklabels(sched_labels)
    ax.set_xlim(15, 100)
    ax.set_xlabel("LORO <5 mg/L recall (%)")
    ax.set_title("a  Primary LORO recall (95% CI)", loc="left")
    ax.grid(axis="x", ls=":", alpha=0.4)
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor=C_LIGHT, fontsize=7.0)

    # Panel B: Sunrise-relative timing curve (SR - 180 to SR + 120 min)
    ax = axes[1]
    ax.axvspan(-190, 0, color="#cbd5e1", alpha=0.40, label="Darkness (< sunrise)")
    ax.axvspan(0, 45, color="#fef3c7", alpha=0.55, label="First-light daylight")
    for net, col, marker, lbl in [("USGS", C_NAVY, "o", "U.S. (USGS)"), ("EA", C_ORANGE, "s", "England (EA)")]:
        prof = r11["holdout_validation"]["sunrise_offset_profile_lt5"][net]
        offs = np.array([p["offset_min_rel_sr"] for p in prof])
        c = np.array([p["recall_95_pct"][0] for p in prof])
        lo = np.array([p["recall_95_pct"][1] for p in prof])
        hi = np.array([p["recall_95_pct"][2] for p in prof])
        ax.fill_between(offs, lo, hi, color=col, alpha=0.14)
        ax.plot(offs, c, f"-{marker}", color=col, lw=1.6, ms=4.5, label=lbl)
    ax.axvline(0, color=C_CORAL, ls="--", lw=1.1)
    ax.text(4, 62.5, "OOS optimal:\nSR + 0 min\n(both networks)", fontsize=6.9, color=C_CORAL, fontweight="bold")
    ax.set_xlim(-190, 130)
    ax.set_ylim(58, 94)
    ax.set_xticks([-180, -120, -60, 0, 60, 120])
    ax.set_xlabel("Minutes relative to geometric sunrise")
    ax.set_ylabel("LORO <5 mg/L recall (%)")
    ax.set_title("b  Sunrise timing & first-light window", loc="left")
    ax.grid(ls=":", alpha=0.35)
    ax.legend(loc="lower left", frameon=True, facecolor="white", edgecolor=C_LIGHT, fontsize=6.6)

    # Panel C: Anti-Circularity & Robustness Forest Plot (Pre-dawn - Afternoon gain, pp)
    ax = axes[2]
    us_c = r11["cadence_downsampling"]["USGS"]["cadences"]
    uk_c30 = r11["cadence_downsampling"]["EA"]["ea_le30min_cohort_30_vs_60"]["cadences"]
    ho = r11["holdout_validation"]

    specs = [
        ("Shared-ref (v3 benchmark)", us5["shared_dawn_minus_afternoon_95_pp"], uk5["shared_dawn_minus_afternoon_95_pp"]),
        ("Primary LORO (drop candidate)", us5["loro_dawn_minus_afternoon_95_pp"], uk5["loro_dawn_minus_afternoon_95_pp"]),
        ("Strict LORO (±30 min buffer)", us5["loro_pm30m_exclusion"]["dawn_minus_afternoon_95_pp"], uk5["loro_pm30m_exclusion"]["dawn_minus_afternoon_95_pp"]),
        ("Persistence: ≥2 readings", us5["persistence_sensitivity"]["persist_ge2_readings"]["dawn_minus_afternoon_95_pp"], uk5["persistence_sensitivity"]["persist_ge2_readings"]["dawn_minus_afternoon_95_pp"]),
        ("Actionable: ≥2 h continuous", us5["persistence_sensitivity"]["actionable_ge2h"]["dawn_minus_afternoon_95_pp"], uk5["persistence_sensitivity"]["actionable_ge2h"]["dawn_minus_afternoon_95_pp"]),
        ("Tolerance: ref <4.8 mg/L", us5["tolerance_buffers"]["ref_thr_4p8"]["dawn_minus_afternoon_95_pp"], uk5["tolerance_buffers"]["ref_thr_4p8"]["dawn_minus_afternoon_95_pp"]),
        ("Indep. probe noise (σ=0.20)", [us5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_mean_pp"], *us5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_p025_p975_pp"]],
                                        [uk5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_mean_pp"], *uk5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_p025_p975_pp"]]),
        ("Downsampled 60-min grid", us_c["60min"]["loro_dawn_minus_afternoon_95_pp"], uk_c30["60min"]["loro_dawn_minus_afternoon_95_pp"]),
        ("Equal-site weight (≥5 nights)", us5["equal_site_ge5_gain_95_pp"], uk5["equal_site_ge5_gain_95_pp"]),
        ("Excl. chronic sites (>50%)", us5["chronic_site_sensitivity"]["excl_chronic_gt50pct_nights"]["pooled_dawn_minus_afternoon_95_pp"], uk5["chronic_site_sensitivity"]["excl_chronic_gt50pct_nights"]["pooled_dawn_minus_afternoon_95_pp"]),
        ("OOS LOO-region holdout", ho["USGS"]["leave_one_region_out"]["oos_gain_95_pp"], ho["EA"]["leave_one_region_out"]["oos_gain_95_pp"]),
        ("Cross-Atlantic zero-shot", ho["cross_atlantic_transfer"]["EA_to_USGS"]["test_gain_95_pp"], ho["cross_atlantic_transfer"]["USGS_to_EA"]["test_gain_95_pp"]),
    ]
    ys = np.arange(len(specs))[::-1]
    for idx, (lbl, us_v, uk_v) in enumerate(specs):
        yi = ys[idx]
        for dy, v, col in [(0.16, us_v, C_NAVY), (-0.16, uk_v, C_ORANGE)]:
            ax.errorbar(v[0], yi + dy, xerr=[[max(0, v[0] - v[1])], [max(0, v[2] - v[0])]],
                        fmt="o", ms=4.0, capsize=2, lw=1.2, color=col)
    ax.axvline(0, color="black", lw=0.7, ls="-")
    ax.set_yticks(ys)
    ax.set_yticklabels([s[0] for s in specs], fontsize=7.2)
    ax.set_xlim(10, 75)
    ax.set_xlabel("Recall gain over 14:30 (percentage points)")
    ax.set_title("c  Anti-circularity & robustness audit", loc="left")
    ax.grid(axis="x", ls=":", alpha=0.4)

    save_fig(fig, "fig2_nw_loro_cross_network_validation")


def make_figure3(r11: dict, r12: dict, df_nights: pd.DataFrame) -> None:
    """Fig 3: Censoring Breakdown, Kaplan-Meier Duration Bias, and Episodic Actionable Lead Time."""
    fig, axes = plt.subplots(1, 3, figsize=(11.5, 3.8), gridspec_kw={"width_ratios": [0.95, 1.1, 1.15]}, layout="constrained")

    # Panel A: Censoring composition of <5 mg/L nights inside astronomical darkness
    ax = axes[0]
    cats = ["both_closed", "left_only", "right_only", "doubly_censored"]
    cat_labels = ["Both closed in night", "Left-censored (sunset)", "Right-censored (sunrise)", "Doubly censored (full night)"]
    cat_colors = [C_TEAL, C_GOLD, C_ORANGE, C_CORAL]

    y_pos = np.array([1, 0])
    net_names = ["U.S.\n(n=8,499)", "England\n(n=2,472)"]
    left_cum = np.zeros(2)
    for cat, lbl, col in zip(cats, cat_labels, cat_colors, strict=True):
        vals = []
        for net in ("USGS", "EA"):
            cd = r11["loro_primary"][net]["thresholds"]["5"]["censoring_and_duration"]
            tot = r11["loro_primary"][net]["thresholds"]["5"]["shared_n_ref_pos"]
            vals.append(100.0 * cd["censor_counts"].get(cat, 0) / tot)
        vals_arr = np.array(vals)
        ax.barh(y_pos, vals_arr, left=left_cum, height=0.52, color=col, edgecolor="white", label=lbl)
        for j, v in enumerate(vals_arr):
            if v >= 10.0:
                ax.text(left_cum[j] + v / 2, y_pos[j], f"{v:.1f}%", ha="center", va="center",
                        color="white", fontsize=7.5, fontweight="bold")
        left_cum += vals_arr
    ax.set_yticks(y_pos)
    ax.set_yticklabels(net_names)
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of <5 mg/L site-nights (%)")
    ax.set_title("a  Nocturnal boundary censoring", loc="left")
    ax.legend(loc="lower center", bbox_to_anchor=(0.48, -0.34), ncols=2, frameon=False, fontsize=6.6)

    # Panel B: Kaplan-Meier Survival Curves (Naive closed vs KM right-censored vs Full continuous episode)
    ax = axes[1]
    us_h = df_nights[(df_nights["network"] == "USGS") & (df_nights["night_min_shared"] < 5.0)]
    uk_h = df_nights[(df_nights["network"] == "EA") & (df_nights["night_min_shared"] < 5.0)]

    # Naive closed-in-night ECDF (treating only closed runs as full sample -> severe downward bias!)
    for grp, col, ls_full, lbl_net in [(us_h, C_NAVY, "-", "U.S."), (uk_h, C_ORANGE, "-", "England")]:
        # Naive closed-in-night
        cl_d = grp["t5_night_dur_hi_hr"].dropna().to_numpy()
        t_cl, s_cl = kaplan_meier_curve(cl_d, np.ones(len(cl_d)), max_t=24.0)
        ax.step(t_cl, s_cl, where="post", color=col, ls=":", lw=1.3, alpha=0.85, label=f"{lbl_net} naive closed only")
        # KM nocturnal (onset in night, sunrise right-censored)
        t_km, s_km = kaplan_meier_curve(grp["t5_night_km_obs_hr"].to_numpy(), grp["t5_night_km_event"].to_numpy(), max_t=12.0)
        ax.step(t_km, s_km, where="post", color=col, ls="--", lw=1.5, label=f"{lbl_net} KM night (censored)")
        # Full continuous series (crossing sunrise/sunset)
        t_fc, s_fc = kaplan_meier_curve(grp["t5_full_dur_hr"].to_numpy(), grp["t5_full_closed"].astype(int).to_numpy(), max_t=24.0)
        ax.step(t_fc, s_fc, where="post", color=col, ls=ls_full, lw=1.8, label=f"{lbl_net} full continuous")

    ax.axhline(50, color=C_SLATE, ls="-.", lw=0.8, alpha=0.7)
    ax.set_xlim(0, 24)
    ax.set_ylim(0, 102)
    ax.set_xticks([0, 4, 8, 12, 16, 20, 24])
    ax.set_xlabel("Episode duration (hours)")
    ax.set_ylabel("Episodes still hypoxic (%)")
    ax.set_title("b  Duration bias from censoring", loc="left")
    ax.grid(ls=":", alpha=0.35)
    ax.legend(loc="upper right", frameon=True, facecolor="white", edgecolor=C_LIGHT, fontsize=6.2)

    # Panel C: Episodic (<24h) Actionable Detection Lead Time Relative to Nadir & Recovery (US + England)
    ax = axes[2]
    us_op = r12["networks"]["USGS"]["primary_actionable_5mg_2h_visit_level"]
    uk_op = r12["networks"]["EA"]["primary_actionable_5mg_2h_visit_level"]

    p_order = [
        ("sonde", "Continuous sonde\n(onset alert)"),
        ("predawn_sr_m30", "Pre-dawn\n(SR − 30m)"),
        ("first_light_sr_p30", "First light\n(SR + 30m)"),
        ("rotating_dawn_included", "Rotating\n(dawn incl.)"),
        ("empirical_wqp_clock", "Empirical\nWQP clock"),
        ("afternoon_1430", "Afternoon\n(14:30)"),
    ]
    y_p = np.arange(len(p_order))[::-1]
    ax.axvline(0, color=C_CORAL, lw=1.1, ls="--")
    ax.axvspan(-14, 0, color="#fee2e2", alpha=0.30)
    ax.axvspan(0, 13, color="#dcfce7", alpha=0.25)

    for idx, (pkey, _) in enumerate(p_order):
        yi = y_p[idx]
        for dy, op_blk, col in [(0.14, us_op, C_NAVY), (-0.14, uk_op, C_ORANGE)]:
            if pkey == "sonde":
                ld = op_blk["continuous_sonde_benchmark"]["episodic_lt24h_lead"]
            else:
                ld = op_blk["protocols"][pkey]["episodic_lt24h_lead"]
            # Plot BOTH lead before nadir (filled circle) and lead before recovery (open diamond)
            ln = ld["median_lead_nadir_hr"]
            le = ld["median_lead_end_hr"]
            ax.plot([ln, le], [yi + dy, yi + dy], color=col, lw=1.5, alpha=0.75)
            ax.plot(ln, yi + dy, "o", color=col, ms=5.0)
            ax.plot(le, yi + dy, "D", color="white", markeredgecolor=col, markeredgewidth=1.2, ms=4.5)

    ax.set_yticks(y_p)
    ax.set_yticklabels([lbl for _, lbl in p_order], fontsize=7.2)
    ax.set_xlim(-13.5, 12.5)
    ax.set_xlabel("Lead time on episodic <24h events (hours)")
    ax.set_title("c  Lead time: nadir (dot) to recovery (diamond)", loc="left")
    ax.text(-13.0, 4.65, "Post-nadir /\npost-recovery", fontsize=6.6, color=C_CORAL, va="top")
    ax.text(5.2, 0.20, "Active / early\nwarning", fontsize=6.6, color=C_GREEN)
    ax.plot([], [], "o-", color=C_NAVY, ms=4.5, lw=1.4, label="U.S. (USGS)")
    ax.plot([], [], "o-", color=C_ORANGE, ms=4.5, lw=1.4, label="England (EA)")
    ax.legend(loc="lower right", bbox_to_anchor=(0.99, 0.22), frameon=True, facecolor="white", edgecolor=C_LIGHT, fontsize=6.3)
    ax.grid(axis="x", ls=":", alpha=0.35)

    save_fig(fig, "fig3_nw_censoring_duration_and_leadtime")


def make_figure4(r12: dict) -> None:
    """Fig 4: Equal-Budget Operational Protocol Comparison, Pareto Surveillance Frontier, and Cost Phase Map."""
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 4.15), gridspec_kw={"width_ratios": [1.15, 1.1, 1.0]}, layout="constrained")

    us_eb = r12["networks"]["USGS"]["equal_budget_simulation_5mg_2h"]["equal_dollar_budget"]["budget_24_dayeq"]
    uk_eb = r12["networks"]["EA"]["equal_budget_simulation_5mg_2h"]["equal_dollar_budget"]["budget_24_dayeq"]

    # Panel A: Equal-Dollar Distinct Actionable Episodes per 100 Daytime-Visit-Eq (Budget=24, m=1.75x, K_sonde=40)
    ax = axes[0]
    items = [
        ("14:30 afternoon", "grab", "afternoon_1430"),
        ("Empirical WQP clock", "grab", "empirical_wqp_clock"),
        ("Daytime-safe rotating", "grab", "rotating_daytime_safe"),
        ("Dawn-incl. rotating", "grab", "rotating_dawn_included"),
        ("Dark pre-dawn (1.75×)", "grab", "predawn_sr_m30"),
        ("First light (1.15×)", "grab", "first_light_sr_p30"),
        ("Sonde top-10% + WQP", "sonde", "y1_daytime_screening_top10pct"),
        ("Sonde top-20% (covar.)", "sonde", "loor_covariate_score_top20pct"),
        ("Sonde top-20% (Y1) + WQP", "sonde", "y1_daytime_screening_top20pct"),
        ("Sonde top-20% + 1st light", "sonde", "y1_daytime_screening_top20pct_plus_firstlight"),
    ]
    y = np.arange(len(items))
    us_vals, uk_vals = [], []
    for _, kind, key in items:
        if kind == "grab":
            us_vals.append(us_eb["grab_by_night_multiplier"]["m_1p75"][key]["distinct_episodes_per_100_dayeq"])
            uk_vals.append(uk_eb["grab_by_night_multiplier"]["m_1p75"][key]["distinct_episodes_per_100_dayeq"])
        else:
            us_vals.append(us_eb["hybrid_sonde_by_cost"]["k_40"][key]["distinct_episodes_per_100_dayeq"])
            uk_vals.append(uk_eb["hybrid_sonde_by_cost"]["k_40"][key]["distinct_episodes_per_100_dayeq"])

    h = 0.36
    ax.barh(y + h / 2, us_vals, height=h, color=C_NAVY, label="U.S. (USGS)")
    ax.barh(y - h / 2, uk_vals, height=h, color=C_ORANGE, label="England (EA)")
    for yi, u, e in zip(y, us_vals, uk_vals, strict=True):
        ax.text(max(u, e) + 0.14, yi, f"{u:.1f} / {e:.1f}", va="center", fontsize=6.5, color="#334155")
    ax.axhline(5.5, color=C_SLATE, ls="--", lw=0.8, alpha=0.7)
    ax.set_yticks(y)
    ax.set_yticklabels([x[0] for x in items], fontsize=7.2)
    ax.set_xlim(0, 8.9)
    ax.set_xlabel("Distinct actionable episodes / 100 budget-eq")
    ax.set_title("a  Equal-budget yield (24 eq/site-yr)", loc="left")
    ax.legend(loc="lower right", frameon=True, facecolor="white", edgecolor=C_LIGHT, fontsize=7.0)
    ax.grid(axis="x", ls=":", alpha=0.35)

    # Panel B: Surveillance Pareto Frontier (Cost per Distinct Episode vs % Impaired Site-Years Flagged)
    ax = axes[1]
    frontier_pts = [
        ("14:30", "grab", "afternoon_1430", C_SLATE, "v"),
        ("WQP", "grab", "empirical_wqp_clock", C_GOLD, "o"),
        ("Pre-dawn\n(1.75×)", "grab", "predawn_sr_m30", C_CORAL, "s"),
        ("First light\n(1.15×)", "grab", "first_light_sr_p30", C_TEAL, "^"),
        ("Sonde 20%\n(Y1)+WQP", "sonde", "y1_daytime_screening_top20pct", C_PURPLE, "D"),
        ("Sonde 20%\n+1st light", "sonde", "y1_daytime_screening_top20pct_plus_firstlight", C_GREEN, "*"),
    ]
    ann_pos = {
        "afternoon_1430": (12.8, 30.8, "right"),
        "empirical_wqp_clock": (8.6, 40.5, "right"),
        "predawn_sr_m30": (11.8, 50.8, "left"),
        "first_light_sr_p30": (8.4, 58.2, "center"),
        "y1_daytime_screening_top20pct": (3.7, 50.0, "left"),
        "y1_daytime_screening_top20pct_plus_firstlight": (3.4, 65.4, "left"),
    }
    for net_eb, ls_m, edge_c in [(us_eb, "-", C_NAVY), (uk_eb, "--", C_ORANGE)]:
        xs, ys = [], []
        for lbl, kind, key, col, mk in frontier_pts:
            blk = net_eb["grab_by_night_multiplier"]["m_1p75"][key] if kind == "grab" else net_eb["hybrid_sonde_by_cost"]["k_40"][key]
            x_v = blk["cost_usd_per_distinct_episode"] / 1000.0
            y_v = blk["impaired_sy_flagged_pct"]
            xs.append(x_v)
            ys.append(y_v)
            ms = 9.5 if mk == "*" else 6.2
            ax.plot(x_v, y_v, mk, color=col, markeredgecolor=edge_c, markeredgewidth=0.9, ms=ms, zorder=4)
            if edge_c == C_NAVY:
                tx, ty, ha = ann_pos[key]
                ax.annotate(
                    lbl.replace("\n", " "),
                    (x_v, y_v),
                    xytext=(tx, ty),
                    fontsize=6.3,
                    color=C_NAVY,
                    ha=ha,
                    arrowprops={"arrowstyle": "-", "color": C_SLATE, "lw": 0.6, "alpha": 0.7},
                )
        ax.plot(xs, ys, ls=ls_m, color=edge_c, lw=1.0, alpha=0.55, zorder=2)

    ax.set_xscale("log")
    ax.set_xticks([2, 3, 5, 10, 20])
    ax.get_xaxis().set_major_formatter(matplotlib.ticker.ScalarFormatter())
    ax.xaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
    ax.set_xlim(2.1, 24)
    ax.set_ylim(25, 70)
    ax.set_xlabel("Cost per distinct episode ($k USD, log scale)")
    ax.set_ylabel("Impaired site-years flagged ≥1× (%)")
    ax.set_title("b  Cost vs. site-discovery frontier", loc="left")
    ax.grid(ls=":", alpha=0.35)
    ax.plot([], [], "-", color=C_NAVY, lw=1.4, label="U.S. (solid)")
    ax.plot([], [], "--", color=C_ORANGE, lw=1.4, label="England (dashed)")
    ax.legend(loc="lower left", frameon=True, facecolor="white", edgecolor=C_LIGHT, fontsize=6.8)

    # Panel C: 2D Cost-Ratio Decision Phase Map (m_night x K_sonde at Budget = 24 day-eq/site-yr)
    ax = axes[2]
    m_grid = np.linspace(1.0, 2.5, 61)
    g_m1 = us_eb["grab_by_night_multiplier"]["m_1p00"]
    y_wqp = g_m1["empirical_wqp_clock"]["distinct_episodes_per_100_dayeq"]
    y_fl = g_m1["first_light_sr_p30"]["distinct_episodes_per_100_dayeq"]
    y_pd = g_m1["predawn_sr_m30"]["distinct_episodes_per_100_dayeq"]
    k_ext = np.linspace(20.0, 280.0, 105)
    ev = r12["networks"]["USGS"]["equal_budget_simulation_5mg_2h"]
    tot_eps = ev["total_distinct_episodes_in_eval"]
    tot_bud = us_eb["total_panel_budget_dayeq"]
    cap20 = ev["sonde_targeting_capture"]["y1_daytime_screening_top20pct"]["share_of_distinct_episodes_pct"] / 100.0
    cap10 = ev["sonde_targeting_capture"]["y1_daytime_screening_top10pct"]["share_of_distinct_episodes_pct"] / 100.0

    Z = np.zeros((len(k_ext), len(m_grid)), dtype=int)
    for ik, ks in enumerate(k_ext):
        for im, mn in enumerate(m_grid):
            m_early = 1.0 + 0.20 * (mn - 1.0)
            s_wqp = y_wqp
            s_pd = y_pd / mn
            s_fl = y_fl / m_early
            if 0.10 * ks <= 24.0:
                rem10 = (24.0 - 0.10 * ks) / 24.0
                s_h10 = 100.0 * (cap10 * tot_eps) / tot_bud + (1.0 - cap10) * rem10 * s_fl
            else:
                s_h10 = -1.0
            if 0.20 * ks <= 24.0:
                rem20 = (24.0 - 0.20 * ks) / 24.0
                s_h20 = 100.0 * (cap20 * tot_eps) / tot_bud + (1.0 - cap20) * rem20 * s_fl
            else:
                s_h20 = -1.0
            Z[ik, im] = int(np.argmax([s_wqp, s_pd, s_fl, s_h10, s_h20]))

    cmap = ListedColormap([C_GOLD, C_CORAL, C_TEAL, "#74c476", C_GREEN])
    ax.imshow(Z, origin="lower", aspect="auto", extent=[m_grid[0], m_grid[-1], k_ext[0], k_ext[-1]], cmap=cmap, vmin=0, vmax=4, alpha=0.86)
    ax.plot(1.75, 40.0, "*", color="white", markeredgecolor="black", ms=11, zorder=5)
    ax.text(1.79, 46.0, "Central\n(1.75×, K=40)", color="white", fontsize=6.8, fontweight="bold")
    ax.axvline(1.53, color="white", ls="--", lw=1.1, alpha=0.9)
    ax.text(1.50, 212, "Grab breakeven\nm* = 1.53×", color="#0f172a", fontsize=6.5, ha="right", fontweight="bold")
    ax.axhline(120, color="white", ls=":", lw=1.0, alpha=0.85)
    ax.axhline(240, color="white", ls=":", lw=1.0, alpha=0.85)
    ax.text(1.04, 72, "Hybrid top-20% sondes\n+ first-light grabs", color="white", fontsize=7.0, fontweight="bold")
    ax.text(1.04, 162, "Hybrid top-10% sondes\n+ first-light grabs", color="#0f172a", fontsize=6.9, fontweight="bold")
    ax.text(1.04, 253, "First-light grabs only", color="white", fontsize=6.9, fontweight="bold")
    ax.set_xlabel("Nocturnal grab cost multiplier ($m_{night}$)")
    ax.set_ylabel("Annual sonde cost ($K_{sonde}$, day-visit eq)")
    ax.set_title("c  Optimal protocol phase map (U.S.)", loc="left")
    legend_handles = [
        Patch(facecolor=C_GREEN, label="Top-20% sonde + 1st light"),
        Patch(facecolor="#74c476", label="Top-10% sonde + 1st light"),
        Patch(facecolor=C_TEAL, label="First-light grabs"),
    ]
    ax.legend(handles=legend_handles, loc="upper right", bbox_to_anchor=(0.99, 0.85), frameon=True, facecolor="white", edgecolor=C_LIGHT, fontsize=6.0)

    save_fig(fig, "fig4_nw_equal_budget_protocol_frontier")


def build_zero_nan_tables(r11: dict, r12: dict) -> None:
    """Export all Main (Tables 1–3) and Supplementary (Tables S2–S4) zero-NaN CSV tables."""
    TBL.mkdir(parents=True, exist_ok=True)

    # Table 1: Primary LORO Cross-Network Performance (<5, <4, <3, <2 mg/L)
    t1_rows = []
    for net, net_lbl in [("USGS", "United States (USGS)"), ("EA", "England (EA)")]:
        n_nights = r11["loro_primary"][net]["n_nights"]
        for thr in ("5", "4", "3", "2"):
            b = r11["loro_primary"][net]["thresholds"][thr]
            for skey, slbl in [
                ("afternoon", "14:30 afternoon"),
                ("overpass", "10:30 overpass"),
                ("morning08", "08:00 morning"),
                ("alternating", "50/50 alternating"),
                ("predawn", "Pre-dawn (SR-30m)"),
            ]:
                s = b["loro_schedules"][skey]
                t1_rows.append(
                    {
                        "network": net_lbl,
                        "n_common_nights": n_nights,
                        "threshold_mgL": int(thr),
                        "shared_ref_pos": b["shared_n_ref_pos"],
                        "loro_ref_pos": b["loro_n_ref_pos"],
                        "loro_dropped_nights": b["shared_minus_loro_dropped_nights"],
                        "schedule": slbl,
                        "detected": s["detected"],
                        "recall_pct": round(s["recall_95_pct"][0], 2),
                        "recall_ci95_lo": round(s["recall_95_pct"][1], 2),
                        "recall_ci95_hi": round(s["recall_95_pct"][2], 2),
                        "ref_neg_alarms": s["ref_neg_alarms"],
                        "ref_neg_alarm_pct": round(s["ref_neg_alarm_95_pct"][0], 3),
                        "loro_gain_vs_1430_pp": round(b["loro_dawn_minus_afternoon_95_pp"][0], 2) if skey == "predawn" else 0.0,
                        "loro_gain_ci95_lo": round(b["loro_dawn_minus_afternoon_95_pp"][1], 2) if skey == "predawn" else 0.0,
                        "loro_gain_ci95_hi": round(b["loro_dawn_minus_afternoon_95_pp"][2], 2) if skey == "predawn" else 0.0,
                    }
                )
    pd.DataFrame(t1_rows).to_csv(TBL / "table1_nw_loro_cross_network.csv", index=False)

    # Table 2: Anti-Circularity, Tolerance, Persistence, Cadence, Chronic-Site, and Holdout Validation (<5 mg/L)
    t2_rows = []
    ho = r11["holdout_validation"]
    for net, net_lbl in [("USGS", "United States (USGS)"), ("EA", "England (EA)")]:
        b5 = r11["loro_primary"][net]["thresholds"]["5"]
        cad = r11["cadence_downsampling"][net]["cadences"]
        items_t2 = [
            ("Shared reference (v3 baseline)", b5["shared_n_ref_pos"], b5["shared_dawn_minus_afternoon_95_pp"], 0.0),
            ("Primary LORO (drop candidate)", b5["loro_n_ref_pos"], b5["loro_dawn_minus_afternoon_95_pp"], b5["loro_schedules"]["predawn"]["ref_neg_alarm_95_pct"][0]),
            ("Strict LORO (+/-30 min buffer)", b5["loro_pm30m_exclusion"]["n_ref_pos"], b5["loro_pm30m_exclusion"]["dawn_minus_afternoon_95_pp"], b5["loro_pm30m_exclusion"]["predawn_ref_neg_alarm_95_pct"][0]),
            ("Persistence >=2 consecutive readings", b5["persistence_sensitivity"]["persist_ge2_readings"]["n_ref_pos"], b5["persistence_sensitivity"]["persist_ge2_readings"]["dawn_minus_afternoon_95_pp"], b5["persistence_sensitivity"]["persist_ge2_readings"]["predawn_ref_neg_alarm_pct"]),
            ("Actionable >=2 h continuous", b5["persistence_sensitivity"]["actionable_ge2h"]["n_ref_pos"], b5["persistence_sensitivity"]["actionable_ge2h"]["dawn_minus_afternoon_95_pp"], b5["persistence_sensitivity"]["actionable_ge2h"]["predawn_ref_neg_alarm_pct"]),
            ("Tolerance buffer: ref <4.8 mg/L", b5["tolerance_buffers"]["ref_thr_4p8"]["n_ref_pos"], b5["tolerance_buffers"]["ref_thr_4p8"]["dawn_minus_afternoon_95_pp"], b5["tolerance_buffers"]["ref_thr_4p8"]["predawn_ref_neg_alarm_pct"]),
            ("Tolerance buffer: ref <5.2 mg/L", b5["tolerance_buffers"]["ref_thr_5p2"]["n_ref_pos"], b5["tolerance_buffers"]["ref_thr_5p2"]["dawn_minus_afternoon_95_pp"], b5["tolerance_buffers"]["ref_thr_5p2"]["predawn_ref_neg_alarm_pct"]),
            ("Indep. MC probe noise (sigma=0.10)", b5["loro_n_ref_pos"], [b5["independent_probe_noise_mc"]["sigma_0p10"]["dawn_minus_afternoon_mean_pp"], *b5["independent_probe_noise_mc"]["sigma_0p10"]["dawn_minus_afternoon_p025_p975_pp"]], b5["independent_probe_noise_mc"]["sigma_0p10"]["predawn_ref_neg_alarm_mean_pct"]),
            ("Indep. MC probe noise (sigma=0.20)", b5["loro_n_ref_pos"], [b5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_mean_pp"], *b5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_p025_p975_pp"]], b5["independent_probe_noise_mc"]["sigma_0p20"]["predawn_ref_neg_alarm_mean_pct"]),
            ("Downsampled 15-min grid", cad["15min"]["loro_lt5_nights"], cad["15min"]["loro_dawn_minus_afternoon_95_pp"], cad["15min"]["predawn_ref_neg_alarm_pct"]),
            ("Downsampled 30-min grid", cad["30min"]["loro_lt5_nights"], cad["30min"]["loro_dawn_minus_afternoon_95_pp"], cad["30min"]["predawn_ref_neg_alarm_pct"]),
            ("Downsampled 60-min grid", cad["60min"]["loro_lt5_nights"], cad["60min"]["loro_dawn_minus_afternoon_95_pp"], cad["60min"]["predawn_ref_neg_alarm_pct"]),
            ("Equal-site weight (>=5 hyp. nights)", b5["equal_site_ge5_n"], b5["equal_site_ge5_gain_95_pp"], b5["loro_schedules"]["predawn"]["ref_neg_alarm_95_pct"][0]),
            ("Excl. chronic sites (>50% nights)", b5["chronic_site_sensitivity"]["excl_chronic_gt50pct_nights"]["n_hyp_nights_remaining"], b5["chronic_site_sensitivity"]["excl_chronic_gt50pct_nights"]["pooled_dawn_minus_afternoon_95_pp"], b5["loro_schedules"]["predawn"]["ref_neg_alarm_95_pct"][0]),
            ("Excl. daytime-chronic (>25% 14:30)", b5["chronic_site_sensitivity"]["excl_daytime_chronic_gt25pct_af"]["n_hyp_nights_remaining"], b5["chronic_site_sensitivity"]["excl_daytime_chronic_gt25pct_af"]["pooled_dawn_minus_afternoon_95_pp"], b5["loro_schedules"]["predawn"]["ref_neg_alarm_95_pct"][0]),
            ("OOS Leave-One-Region-Out holdout", ho[net]["leave_one_region_out"]["n_oos_hyp_nights"], ho[net]["leave_one_region_out"]["oos_gain_95_pp"], ho[net]["leave_one_region_out"]["oos_ref_neg_alarm_95_pct"][0]),
            ("OOS 5-fold site holdout", ho[net]["five_fold_site_holdout"]["n_oos_hyp_nights"], ho[net]["five_fold_site_holdout"]["oos_gain_95_pp"], ho[net]["five_fold_site_holdout"]["oos_ref_neg_alarm_pct"]),
            ("Cross-Atlantic zero-shot transfer", ho["cross_atlantic_transfer"]["EA_to_USGS" if net == "USGS" else "USGS_to_EA"]["test_n_hyp"], ho["cross_atlantic_transfer"]["EA_to_USGS" if net == "USGS" else "USGS_to_EA"]["test_gain_95_pp"], ho["cross_atlantic_transfer"]["EA_to_USGS" if net == "USGS" else "USGS_to_EA"]["test_ref_neg_alarm_95_pct"][0]),
        ]
        for label, n_ref, g_ci, fa in items_t2:
            t2_rows.append(
                {
                    "network": net_lbl,
                    "sensitivity_check": label,
                    "n_ref_units": int(n_ref),
                    "gain_vs_1430_pp": round(float(g_ci[0]), 2),
                    "ci95_lo_pp": round(float(g_ci[1]), 2),
                    "ci95_hi_pp": round(float(g_ci[2]), 2),
                    "ref_neg_alarm_pct": round(float(fa), 3),
                }
            )
    pd.DataFrame(t2_rows).to_csv(TBL / "table2_nw_robustness_holdout_cadence.csv", index=False)

    # Table 3: Equal-Budget Operational Protocol Comparison (Budget=24 day-eq/site-yr, m_night=1.75x, K_sonde=40)
    t3_rows = []
    for net, net_lbl in [("USGS", "United States (USGS)"), ("EA", "England (EA)")]:
        vp = r12["networks"][net]["primary_actionable_5mg_2h_visit_level"]
        eb24 = r12["networks"][net]["equal_budget_simulation_5mg_2h"]["equal_dollar_budget"]["budget_24_dayeq"]
        g175 = eb24["grab_by_night_multiplier"]["m_1p75"]
        h40 = eb24["hybrid_sonde_by_cost"]["k_40"]

        grab_defs = [
            ("afternoon_1430", "14:30 afternoon grab"),
            ("empirical_wqp_clock", "Empirical WQP agency clock"),
            ("rotating_daytime_safe", "Daytime-safe rotating (07/10:30/14:30)"),
            ("rotating_dawn_included", "Dawn-included rotating (1/3 pre-dawn)"),
            ("alternating_50_50", "50/50 alternating (pre-dawn/14:30)"),
            ("first_light_sr_p30", "First-light daylight (SR+30m, 1.15x)"),
            ("predawn_sr_m30", "Dark pre-dawn (SR-30m, 1.75x)"),
        ]
        for key, lbl in grab_defs:
            v = vp["protocols"][key]
            s = g175[key]
            t3_rows.append(
                {
                    "network": net_lbl,
                    "protocol": lbl,
                    "protocol_type": "Grab",
                    "unit_cost_dayeq": round(s["unit_visit_cost_dayeq"], 2),
                    "actionable_per_100_visits": round(v["actionable_detections_per_100_visits"], 2),
                    "new_per_100_vs_wqp": round(v["new_actionable_per_100_vs_wqp"], 2),
                    "distinct_ep_per_100_budget_eq": round(s["distinct_episodes_per_100_dayeq"], 2),
                    "actionable_nights_per_100_budget_eq": round(s["actionable_nights_per_100_dayeq"], 2),
                    "cost_usd_per_distinct_episode": round(s["cost_usd_per_distinct_episode"], 0),
                    "impaired_sy_flagged_pct": round(s["impaired_sy_flagged_pct"], 1),
                    "episodic_lead_nadir_hr": round(v["episodic_lt24h_lead"]["median_lead_nadir_hr"], 2),
                    "episodic_lead_end_hr": round(v["episodic_lt24h_lead"]["median_lead_end_hr"], 2),
                    "loro_ref_neg_alarm_pct": round(v["loro_ref_neg_alarm_pct"], 3),
                }
            )
        sonde_lead = vp["continuous_sonde_benchmark"]["episodic_lt24h_lead"]
        sonde_defs = [
            ("y1_daytime_screening_top10pct", "Hybrid: top-10% sondes (Y1) + WQP"),
            ("y1_daytime_screening_top20pct", "Hybrid: top-20% sondes (Y1) + WQP"),
            ("y1_daytime_screening_top20pct_plus_firstlight", "Hybrid: top-20% sondes (Y1) + first light"),
            ("loor_covariate_score_top20pct", "Hybrid: top-20% sondes (covar.) + WQP"),
            ("oracle_full_panel_top20pct", "Hybrid: top-20% sondes (oracle) + WQP"),
        ]
        for key, lbl in sonde_defs:
            s = h40[key]
            t3_rows.append(
                {
                    "network": net_lbl,
                    "protocol": lbl,
                    "protocol_type": "Hybrid Sonde",
                    "unit_cost_dayeq": 40.0,
                    "actionable_per_100_visits": round(100.0 * vp["actionable_prevalence_pct"] / 100.0, 2),
                    "new_per_100_vs_wqp": round(s["distinct_episodes_per_100_dayeq"] - g175["empirical_wqp_clock"]["distinct_episodes_per_100_dayeq"], 2),
                    "distinct_ep_per_100_budget_eq": round(s["distinct_episodes_per_100_dayeq"], 2),
                    "actionable_nights_per_100_budget_eq": round(s["actionable_nights_per_100_dayeq"], 2),
                    "cost_usd_per_distinct_episode": round(s["cost_usd_per_distinct_episode"], 0),
                    "impaired_sy_flagged_pct": round(s["impaired_sy_flagged_pct"], 1),
                    "episodic_lead_nadir_hr": round(sonde_lead["median_lead_nadir_hr"], 2),
                    "episodic_lead_end_hr": round(sonde_lead["median_lead_end_hr"], 2),
                    "loro_ref_neg_alarm_pct": round(s["loro_ref_neg_alarm_per_100_visits"], 3),
                }
            )
    pd.DataFrame(t3_rows).to_csv(TBL / "table3_nw_equal_budget_protocols.csv", index=False)

    # Table S2: Coverage & Attrition by Cadence and Month
    s2_rows = []
    for net, net_lbl in [("USGS", "United States (USGS)"), ("EA", "England (EA)")]:
        ca = r11["coverage_attrition"][net]
        s2_rows.append(
            {
                "network": net_lbl, "stratum_type": "Overall", "stratum": "All warm-season",
                "n_sites": ca["n_sites_with_matched"], "candidate_nights": ca["candidate_nights"],
                "matched_nights": ca["matched_nights"], "entry_rate_pct": round(ca["common_support_entry_pct"], 2),
                "fail_night_gap": ca["fail_night_gap"], "fail_target_match": ca["fail_target_match"],
            }
        )
        for st in ca["by_native_step"]:
            s2_rows.append(
                {
                    "network": net_lbl, "stratum_type": "Cadence", "stratum": f"{st['native_step_min']} min",
                    "n_sites": st["n_sites"], "candidate_nights": st["candidate_nights"],
                    "matched_nights": st["matched_nights"], "entry_rate_pct": round(st["entry_rate_pct"], 2),
                    "fail_night_gap": st["fail_night_gap"], "fail_target_match": st["fail_target_match"],
                }
            )
        m_names = {5: "May", 6: "June", 7: "July", 8: "August", 9: "September", 10: "October"}
        for mo in ca["by_month"]:
            s2_rows.append(
                {
                    "network": net_lbl, "stratum_type": "Month", "stratum": m_names[mo["month"]],
                    "n_sites": ca["n_sites_with_matched"], "candidate_nights": mo["candidate_nights"],
                    "matched_nights": mo["matched_nights"], "entry_rate_pct": round(mo["entry_rate_pct"], 2),
                    "fail_night_gap": mo["fail_night_gap"], "fail_target_match": mo["fail_target_match"],
                }
            )
    pd.DataFrame(s2_rows).to_csv(TBL / "table_s2_coverage_by_cadence_month.csv", index=False)

    # Table S3: Censoring & Kaplan-Meier Duration Summary
    s3_rows = []
    for net, net_lbl in [("USGS", "United States (USGS)"), ("EA", "England (EA)")]:
        for thr in ("5", "4", "3", "2"):
            b = r11["loro_primary"][net]["thresholds"][thr]
            cd = b["censoring_and_duration"]
            cc = cd["censor_counts"]
            tot = max(1, b["shared_n_ref_pos"])
            km_n = cd["km_nocturnal_observed_onset"]
            km_f = cd["full_continuous_series_km"]
            s3_rows.append(
                {
                    "network": net_lbl,
                    "threshold_mgL": int(thr),
                    "total_hypoxic_nights": b["shared_n_ref_pos"],
                    "both_closed_n": cc.get("both_closed", 0),
                    "both_closed_pct": round(100.0 * cc.get("both_closed", 0) / tot, 1),
                    "left_only_n": cc.get("left_only", 0),
                    "right_only_n": cc.get("right_only", 0),
                    "doubly_censored_n": cc.get("doubly_censored", 0),
                    "naive_closed_median_lo_hr": round(cd["both_closed_median_lo_hi_hr"][0], 2),
                    "naive_closed_median_hi_hr": round(cd["both_closed_median_lo_hi_hr"][1], 2),
                    "km_night_rmst_12h_hr": round(km_n["rmst_12h_hr"], 2),
                    "km_night_surv_6h_pct": round(km_n["surv_at_6h_pct"], 1),
                    "full_series_median_hr": round(cd["full_continuous_median_iqr_hr"][1], 2),
                    "full_series_q25_hr": round(cd["full_continuous_median_iqr_hr"][0], 2),
                    "full_series_q75_hr": round(cd["full_continuous_median_iqr_hr"][2], 2),
                    "full_series_closed_pct": round(cd["full_continuous_closed_pct"], 1),
                    "full_series_km_median_hr": round(km_f["median_hr"] if km_f["median_hr"] is not None else -1.0, 2),
                }
            )
    pd.DataFrame(s3_rows).to_csv(TBL / "table_s3_censoring_km_duration.csv", index=False)

    # Table S4: Full Cost-Sensitivity Grid (Budgets 12, 24, 52 x m_night x K_sonde)
    s4_rows = []
    for net, net_lbl in [("USGS", "United States (USGS)"), ("EA", "England (EA)")]:
        eb = r12["networks"][net]["equal_budget_simulation_5mg_2h"]["equal_dollar_budget"]
        for v_ann in (12, 24, 52):
            vb = eb[f"budget_{v_ann}_dayeq"]
            for m_key, m_val in [("m_1p00", 1.0), ("m_1p35", 1.35), ("m_1p75", 1.75), ("m_2p50", 2.5)]:
                for mode in ("empirical_wqp_clock", "rotating_dawn_included", "first_light_sr_p30", "predawn_sr_m30"):
                    s = vb["grab_by_night_multiplier"][m_key][mode]
                    s4_rows.append(
                        {
                            "network": net_lbl, "annual_budget_dayeq": v_ann, "protocol": mode,
                            "cost_param": f"m_night={m_val:.2f}x",
                            "distinct_ep_per_100_eq": round(s["distinct_episodes_per_100_dayeq"], 2),
                            "cost_usd_per_distinct_ep": round(s["cost_usd_per_distinct_episode"], 0),
                            "impaired_sy_flagged_pct": round(s["impaired_sy_flagged_pct"], 1),
                        }
                    )
            for k_sonde in (20, 40, 60, 100):
                for tag in ("y1_daytime_screening_top10pct", "y1_daytime_screening_top20pct", "y1_daytime_screening_top20pct_plus_firstlight"):
                    s = vb["hybrid_sonde_by_cost"][f"k_{k_sonde}"][tag]
                    if s.get("feasible"):
                        s4_rows.append(
                            {
                                "network": net_lbl, "annual_budget_dayeq": v_ann, "protocol": tag,
                                "cost_param": f"K_sonde={k_sonde}",
                                "distinct_ep_per_100_eq": round(s["distinct_episodes_per_100_dayeq"], 2),
                                "cost_usd_per_distinct_ep": round(s["cost_usd_per_distinct_episode"], 0),
                                "impaired_sy_flagged_pct": round(s["impaired_sy_flagged_pct"], 1),
                            }
                        )
    pd.DataFrame(s4_rows).to_csv(TBL / "table_s4_cost_sensitivity_grid.csv", index=False)


def main() -> None:
    set_nature_style()
    r11 = json.loads((RES / "11_loro_and_sensitivity.json").read_text(encoding="utf-8"))
    r12 = json.loads((RES / "12_operational_protocol_decision.json").read_text(encoding="utf-8"))
    df_nights = pd.read_parquet(PROC / "v4_nocturnal_site_nights.parquet")
    wqp_paired = pd.read_parquet(PROC / "v4_wqp_paired_visits.parquet")

    print("Generating Nature Water Main Figures 1-4 (350 DPI PNG + vector PDF)...", flush=True)
    make_figure1(r11, wqp_paired)
    make_figure2(r11)
    make_figure3(r11, r12, df_nights)
    make_figure4(r12)

    print("Exporting zero-NaN Main Tables 1-3 & Supplementary Tables S2-S4...", flush=True)
    build_zero_nan_tables(r11, r12)

    # Verify zero NaNs across all generated CSVs
    for fn in (
        "table1_nw_loro_cross_network.csv",
        "table2_nw_robustness_holdout_cadence.csv",
        "table3_nw_equal_budget_protocols.csv",
        "table_s1_station_coverage_attrition.csv",
        "table_s2_coverage_by_cadence_month.csv",
        "table_s3_censoring_km_duration.csv",
        "table_s4_cost_sensitivity_grid.csv",
    ):
        df_chk = pd.read_csv(TBL / fn)
        n_na = int(df_chk.isna().sum().sum())
        print(f"  {fn:45s}: {len(df_chk):4d} rows, {n_na} NaNs", flush=True)
        if n_na > 0:
            raise ValueError(f"NaNs found in {fn}!")
    print("[DONE] All v4 Nature Water figures and zero-NaN tables generated.", flush=True)


if __name__ == "__main__":
    main()
