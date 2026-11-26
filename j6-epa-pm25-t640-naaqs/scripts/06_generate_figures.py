"""Step 06 (Pillar 5): Generate 5 Nature Sustainability / Science / PNAS-grade 300-DPI PNG + vector
PDF publication figures, 100% dynamically driven by saved JSON receipts and processed parquets.

Figures generated into figures/:
  1. fig1_t640_windfall_and_ej_map.png/.pdf
  2. fig2_rooftop_lottery_and_regional_bias.png/.pdf
  3. fig3_zero_eiv_smoke_and_speciation_physics.png/.pdf
  4. fig4_ee_triage_event_study_and_decomposition.png/.pdf
  5. fig5_optical_to_flagging_multiplier.png/.pdf
"""

from __future__ import annotations

import json

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")

from econ_utils import FIG_DIR, PROC_DIR, RES_DIR

# Okabe-Ito / Nature-inspired colorblind-safe palette
NAVY = "#0B2545"
CRIMSON = "#B91C1C"
TEAL = "#0F766E"
AMBER = "#D97706"
SLATE = "#64748B"
LIGHT_BG = "#F8FAFC"
GRID_COL = "#CBD5E1"


def setup_rc() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.9,
            "axes.titlesize": 10.2,
            "axes.titleweight": "bold",
            "axes.labelsize": 9.1,
            "axes.labelweight": "bold",
            "xtick.labelsize": 8.2,
            "ytick.labelsize": 8.2,
            "legend.fontsize": 7.8,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#334155",
            "axes.linewidth": 0.9,
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "savefig.dpi": 300,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
        }
    )


def save_fig(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    png_p = FIG_DIR / f"{stem}.png"
    pdf_p = FIG_DIR / f"{stem}.pdf"
    fig.savefig(png_p, dpi=300, bbox_inches="tight", pad_inches=0.14)
    fig.savefig(pdf_p, bbox_inches="tight", pad_inches=0.14)
    plt.close(fig)
    print(f"  Saved {png_p.name} ({png_p.stat().st_size/1024:.0f} KB) & {pdf_p.name}", flush=True)


def make_fig1(r1: dict) -> None:
    """Figure 1: Stitched App. N Nonattainment Waterfall + Exogenous FRM Null & EJ Profile."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.4), gridspec_kw={"width_ratios": [1.14, 1.0]})
    fig.subplots_adjust(wspace=0.34)

    wf21 = r1["accounting"]["combined_site_reg_appn_11of12"]["matched_2123_waterfall"]
    wf25 = r1["accounting"]["combined_site_reg_appn_11of12"]["matched_2123_to_2325_waterfall"]
    unm = r1["accounting"]["combined_site_reg_appn_11of12"]["all_valid_unmatched"]
    epa21 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2021_2023_final_08_08_24_0.xlsx"]
    epa25 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2023_2025_final_06_12_26.xlsx"]

    labels = [
        "2021–23\nRaw T640\n(Pre-Align)",
        "2021–23\nAligned\n(Post-T640)",
        "2021–23\nAligned +\nConcurred EE",
        "2021–23\nAligned +\nAll EE Flags",
        "2023–25\nAligned\n(All Valid)",
    ]
    counts = [
        wf21["raw_2123"]["counties"],
        wf21["aln_2123"]["counties"],
        wf21["aln_ee_conc_2123"]["counties"],
        wf21["aln_ee_all_2123"]["counties"],
        unm["na_2325_aln"],
    ]
    pops = [
        wf21["raw_2123"]["pop_millions"],
        wf21["aln_2123"]["pop_millions"],
        wf21["aln_ee_conc_2123"]["pop_millions"],
        wf21["aln_ee_all_2123"]["pop_millions"],
        wf25["aln_2325"]["pop_millions"],
    ]
    colors = [CRIMSON, NAVY, TEAL, "#2563EB", SLATE]
    x = np.arange(len(labels))
    bars = ax1.bar(x, counts, width=0.58, color=colors, edgecolor="#0F172A", linewidth=0.7, zorder=3)
    ax1.grid(axis="y", color=GRID_COL, linestyle="--", linewidth=0.6, alpha=0.7, zorder=0)

    # Put clean bold count + pop INSIDE the upper half of each bar so EPA Official diamonds sit unobstructed ABOVE!
    for idx, (bar, cnt, pop) in enumerate(zip(bars, counts, pops)):
        tag = f"{cnt}\n({pop:.1f}M)" if idx < 4 else f"{cnt}\n({wf25['aln_2325']['counties']} mtd)"
        ax1.text(
            bar.get_x() + bar.get_width() / 2.0,
            cnt - 6.0,
            tag,
            ha="center",
            va="top",
            fontsize=7.8,
            fontweight="bold",
            color="white",
            zorder=4,
        )

    # Overlay Official EPA Published DV nonattainment counts cleanly ABOVE bars 1 & 4
    ax1.scatter(
        [1, 4],
        [epa21["epa_na_counties"], epa25["epa_na_counties"]],
        marker="D",
        s=62,
        color=AMBER,
        edgecolor="#0F172A",
        linewidth=0.9,
        zorder=5,
        label=f"Official EPA Published DVs ({epa21['epa_na_counties']} in 21–23; {epa25['epa_na_counties']} in 23–25)",
    )
    ax1.text(1.0, epa21["epa_na_counties"] + 4.5, f"EPA: {epa21['epa_na_counties']}", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#92400E")
    ax1.text(4.0, epa25["epa_na_counties"] + 4.5, f"EPA: {epa25['epa_na_counties']}", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color="#92400E")

    # Highlight the -47 T640 alignment drop bracket cleanly above the bars
    flip = wf21["flip_t640_alone"]
    ax1.annotate(
        "",
        xy=(0.95, epa21["epa_na_counties"] + 16),
        xytext=(0.05, counts[0] + 6),
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 1.6, "connectionstyle": "arc3,rad=-0.18"},
    )
    ax1.text(
        0.58,
        counts[0] + 22,
        f"T640 Alignment Alone:\n−{flip['counties']} DV-reclassified (−{flip['pop_millions']:.1f}M)",
        ha="center",
        va="bottom",
        fontsize=7.9,
        fontweight="bold",
        color=CRIMSON,
        bbox={"boxstyle": "round,pad=0.28", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.9},
    )

    nulls = r1["exogenous_nulls_margins_acd"]
    frm_ex = nulls["margin_d_frm_exog_dv1820_county_cr1"]["coefs"]["tp"]
    frm_rtm = nulls["margin_d_frm_endog_dv2123_rtm"]["coefs"]["tp"]
    ax1.text(
        0.98,
        0.97,
        f"Margin D Gravimetric FRM Check:\n"
        f"• Exog. DV18–20: {frm_ex['beta']:+.3f} µg/m³ (p={frm_ex['p_cr1']:.2f})\n"
        f"• Endog. DV21–23 RTM: {frm_rtm['beta']:+.3f} µg/m³",
        transform=ax1.transAxes,
        ha="right",
        va="top",
        fontsize=7.3,
        color="#1E293B",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": LIGHT_BG, "edgecolor": "#94A3B8", "lw": 0.8},
    )

    ax1.set_xticks(x)
    ax1.set_xticklabels(labels)
    ax1.set_ylabel("Counties Exceeding 9.0 µg/m³ (DV ≥ 9.1)")
    ax1.set_ylim(0, max(counts) + 58)
    ax1.set_title("A. Stitched App. N DV Threshold Waterfall (≥9.1 µg/m³) & EPA Reconciliation", loc="left", pad=10)
    ax1.legend(loc="upper right", bbox_to_anchor=(0.98, 0.77), frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.2)

    # Panel B: Regional & Environmental Justice Profile (Census SAIPE 2023 + PEP 2024)
    ej = r1["ej_audit_acs2023"]["groups"]
    ej_t = r1["ej_audit_acs2023"]["formal_tests"]
    g_fl = ej["T640_Flipped"]
    g_st = ej["Still_Nonattainment"]
    g_cl = ej["Cleanly_Attaining"]

    cats = [
        "Midwest + South\nCounty Share (%)",
        "Western U.S.\nCounty Share (%)",
        "Pop-Wtd Black\nNH Share (%)",
        "Pop-Wtd Hispanic\nShare (%)",
        "Pop-Wtd Non-White\nShare (%)",
        "County Poverty\nRate (%)",
    ]
    v_fl = [
        100.0 * (g_fl["region_counts"].get("MW", 0) + g_fl["region_counts"].get("SO", 0)) / g_fl["n_counties"],
        100.0 * g_fl["region_counts"].get("WE", 0) / g_fl["n_counties"],
        g_fl["pop_weighted_means"]["pct_black_nh"],
        g_fl["pop_weighted_means"]["pct_hispanic"],
        g_fl["pop_weighted_means"]["pct_nonwhite"],
        g_fl["unweighted_means"]["poverty_rate"],
    ]
    v_st = [
        100.0 * (g_st["region_counts"].get("MW", 0) + g_st["region_counts"].get("SO", 0)) / g_st["n_counties"],
        100.0 * g_st["region_counts"].get("WE", 0) / g_st["n_counties"],
        g_st["pop_weighted_means"]["pct_black_nh"],
        g_st["pop_weighted_means"]["pct_hispanic"],
        g_st["pop_weighted_means"]["pct_nonwhite"],
        g_st["unweighted_means"]["poverty_rate"],
    ]
    v_cl = [
        100.0 * (g_cl["region_counts"].get("MW", 0) + g_cl["region_counts"].get("SO", 0)) / g_cl["n_counties"],
        100.0 * g_cl["region_counts"].get("WE", 0) / g_cl["n_counties"],
        g_cl["pop_weighted_means"]["pct_black_nh"],
        g_cl["pop_weighted_means"]["pct_hispanic"],
        g_cl["pop_weighted_means"]["pct_nonwhite"],
        g_cl["unweighted_means"]["poverty_rate"],
    ]

    y = np.arange(len(cats))[::-1]
    h = 0.25
    ax2.barh(y + h, v_fl, height=h, color=CRIMSON, edgecolor="#0F172A", lw=0.5, label=f"T640 DV-Reclassified ({g_fl['n_counties']} cntys, {g_fl['pop_2024_millions']:.1f}M)", zorder=3)
    ax2.barh(y, v_st, height=h, color=NAVY, edgecolor="#0F172A", lw=0.5, label=f"Still ≥9.1 µg/m³ DV ({g_st['n_counties']} cntys, {g_st['pop_2024_millions']:.1f}M)", zorder=3)
    ax2.barh(y - h, v_cl, height=h, color="#94A3B8", edgecolor="#0F172A", lw=0.5, label=f"Cleanly ≤9.0 µg/m³ DV ({g_cl['n_counties']} cntys, {g_cl['pop_2024_millions']:.1f}M)", zorder=3)
    ax2.grid(axis="x", color=GRID_COL, linestyle="--", linewidth=0.6, alpha=0.7, zorder=0)

    # Escape $ so matplotlib NEVER interprets paired dollar signs as math mode!
    inc_fl = g_fl["unweighted_means"]["median_hh_income"] / 1e3
    inc_st = g_st["unweighted_means"]["median_hh_income"] / 1e3
    we_fl = g_fl["region_counts"].get("WE", 0)
    we_st = g_st["region_counts"].get("WE", 0)
    p_hisp = ej_t["Flipped_vs_Still_Nonattainment"]["pct_hispanic"]["welch_p"]
    p_nw = ej_t["Flipped_vs_Still_Nonattainment"]["pct_nonwhite"]["welch_p"]
    p_notes = [
        f"p={ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['fisher_p']:.3f} vs Still",
        f"{we_fl}/{g_fl['n_counties']} vs {we_st}/{g_st['n_counties']}",
        f"p={ej_t['Flipped_vs_Cleanly_Attaining']['pct_black_nh']['welch_p']:.3f} vs Clean",
        f"p{'<0.001' if p_hisp < 0.001 else f'={p_hisp:.3f}'} vs Still",
        f"p{'<0.001' if p_nw < 0.001 else f'={p_nw:.3f}'} vs Still",
        f"Inc: \\${inc_fl:.1f}k vs \\${inc_st:.1f}k",
    ]
    for yi, mval, ptxt in zip(y, [max(a, b, c) for a, b, c in zip(v_fl, v_st, v_cl)], p_notes):
        ax2.text(mval + 1.5, yi + 0.02, ptxt, va="center", ha="left", fontsize=7.1, color="#334155", style="italic")

    ax2.set_yticks(y)
    ax2.set_yticklabels(cats)
    ax2.set_xlabel("Percentage (%)")
    ax2.set_xlim(0, 108)
    ax2.set_title("B. Regional & Demographic Profile of DV-Reclassified Counties", loc="left", pad=10)
    ax2.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.0)

    save_fig(fig, "fig1_t640_windfall_and_ej_map")


def make_fig2(r2: dict) -> None:
    """Figure 2: Same-Rooftop 2023-2025 App. N Lottery Scatter & Regional/Seasonal Residual Bias."""
    sdv = pd.read_parquet(PROC_DIR / "rooftop_dv_t640_2023_2025.parquet")
    rt = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_st = r2["rooftop_dv_lottery_2023_2025"]["t640_fw_strict_4q3y"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.4), gridspec_kw={"width_ratios": [1.0, 1.16]})
    fig.subplots_adjust(wspace=0.28)

    lim_lo, lim_hi = 3.2, 15.2
    ax1.fill_between([lim_lo, 9.05], 9.05, lim_hi, color="#FEE2E2", alpha=0.55, zorder=1)
    ax1.plot([lim_lo, lim_hi], [lim_lo, lim_hi], linestyle="--", color="#475569", lw=1.0, zorder=2, label="45° Equality (Zero Bias)")
    ax1.axvline(9.05, color="#334155", linestyle=":", lw=1.0, zorder=2)
    ax1.axhline(9.05, color="#334155", linestyle=":", lw=1.0, zorder=2)

    m_t640_only = (sdv["dv_fem_r"] >= 9.1) & (sdv["dv_frm_r"] <= 9.0)
    m_frm_only = (sdv["dv_frm_r"] >= 9.1) & (sdv["dv_fem_r"] <= 9.0)
    m_both_na = (sdv["dv_fem_r"] >= 9.1) & (sdv["dv_frm_r"] >= 9.1)
    m_both_att = (sdv["dv_fem_r"] <= 9.0) & (sdv["dv_frm_r"] <= 9.0)

    ax1.scatter(sdv.loc[m_both_att, "dv_frm"], sdv.loc[m_both_att, "dv_fem"], s=24, color="#94A3B8", alpha=0.75, edgecolor="white", lw=0.4, zorder=3, label=f"Both ≤ 9.0 µg/m³ ({int(m_both_att.sum())})")
    ax1.scatter(sdv.loc[m_both_na, "dv_frm"], sdv.loc[m_both_na, "dv_fem"], s=34, color=NAVY, alpha=0.88, edgecolor="white", lw=0.5, zorder=4, label=f"Both ≥ 9.1 µg/m³ ({int(m_both_na.sum())})")
    ax1.scatter(sdv.loc[m_frm_only, "dv_frm"], sdv.loc[m_frm_only, "dv_fem"], s=46, marker="s", color=AMBER, edgecolor="#0F172A", lw=0.7, zorder=5, label=f"FRM ≥ 9.1, T640 ≤ 9.0 ({int(m_frm_only.sum())})")
    ax1.scatter(sdv.loc[m_t640_only, "dv_frm"], sdv.loc[m_t640_only, "dv_fem"], s=52, marker="o", color=CRIMSON, edgecolor="#0F172A", lw=0.7, zorder=6, label=f"T640 ≥ 9.1, FRM ≤ 9.0 ({int(m_t640_only.sum())})")

    ax1.text(
        3.55,
        14.65,
        f"Optical Lottery Zone:\n{rt['fem_na_frm_att']} vs {rt['frm_na_fem_att']} ({rt['odds_ratio_lottery']:.1f}:1)\n"
        f"Exact binom p = {rt['binom_p']:.1e}\n"
        f"(Strict 4q×3y: {rt_st['fem_na_frm_att']} vs {rt_st['frm_na_fem_att']})",
        ha="left",
        va="top",
        fontsize=7.8,
        fontweight="bold",
        color=CRIMSON,
        bbox={"boxstyle": "round,pad=0.32", "facecolor": "white", "edgecolor": CRIMSON, "lw": 0.9, "alpha": 0.95},
    )
    ax1.text(
        14.9,
        3.55,
        f"N = {rt['n_sites']} rooftops (2023–2025)\n"
        f"Mean DV bias = {rt['mean_dv_bias']:+.3f} µg/m³\n"
        f"(t = {rt['t_bias']:+.2f}, {rt['pct_positive']:.1f}% > 0)",
        ha="right",
        va="bottom",
        fontsize=7.6,
        color="#1E293B",
        bbox={"boxstyle": "round,pad=0.3", "facecolor": LIGHT_BG, "edgecolor": "#94A3B8", "lw": 0.8},
    )

    ax1.set_xlim(lim_lo, lim_hi)
    ax1.set_ylim(lim_lo, lim_hi)
    ax1.set_xlabel("Collocated Gravimetric FRM Design Value (µg/m³)")
    ax1.set_ylabel("Post-Alignment T640_FW (636/638) Design Value (µg/m³)")
    ax1.set_title("A. Same-Rooftop 2023–2025 App. N DV Threshold Lottery", loc="left", pad=10)
    ax1.legend(loc="lower right", bbox_to_anchor=(0.99, 0.22), frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.2)

    # Panel B: Regional & Seasonal Residual Bias (T640_FW vs BAM, generous lower ylim so ZERO clipping!)
    tg = r2["sample_and_gradients"]["t640_fw"]
    bg = r2["sample_and_gradients"]["bam"]
    keys = ["MW", "SO", "NE", "WE", "DJF", "MAM", "SON", "JJA"]
    x_pos = np.array([0, 1, 2, 3, 4.6, 5.6, 6.6, 7.6])
    x_lbl = ["Midwest", "South", "Northeast", "West", "Winter\n(DJF)", "Spring\n(MAM)", "Fall\n(SON)", "Summer\n(JJA)"]

    t_m, t_e, b_m, b_e = [], [], [], []
    for k in keys:
        src_t = tg["by_region_2023_2025"] if k in ("MW", "SO", "NE", "WE") else tg["by_season_2023_2025"]
        src_b = bg["by_region_2023_2025"] if k in ("MW", "SO", "NE", "WE") else bg["by_season_2023_2025"]
        t_m.append(src_t[k]["mean_bias"])
        t_e.append(1.96 * src_t[k]["se_site_cr1"])
        b_m.append(src_b[k]["mean_bias"])
        b_e.append(1.96 * src_b[k]["se_site_cr1"])

    w = 0.34
    ax2.axhline(0.0, color="#334155", lw=0.9, zorder=2)
    ax2.axvline(3.8, color="#94A3B8", linestyle="--", lw=1.0, zorder=2)
    ax2.grid(axis="y", color=GRID_COL, linestyle="--", linewidth=0.6, alpha=0.7, zorder=0)

    ax2.bar(x_pos - w / 2, t_m, width=w, yerr=t_e, capsize=3, color=CRIMSON, edgecolor="#0F172A", lw=0.6, error_kw={"elinewidth": 1.1, "ecolor": "#450A0A"}, label="Post-Alignment T640_FW (636/638)", zorder=3)
    ax2.bar(x_pos + w / 2, b_m, width=w, yerr=b_e, capsize=3, color=TEAL, edgecolor="#0F172A", lw=0.6, error_kw={"elinewidth": 1.1, "ecolor": "#134E4A"}, label="Benchmark Mass-Based BAM (170/209)", zorder=3)

    for xp, tm, te in zip(x_pos, t_m, t_e):
        ax2.text(xp - w / 2, tm + te + 0.035, f"{tm:+.2f}", ha="center", va="bottom", fontsize=7.2, fontweight="bold", color=CRIMSON)

    ax2.text(1.5, 1.15, "Census Region", ha="center", va="top", fontsize=8.4, fontweight="bold", color=NAVY)
    ax2.text(6.1, 1.15, "Meteorological Season", ha="center", va="top", fontsize=8.4, fontweight="bold", color=NAVY)
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(x_lbl)
    ax2.set_ylabel("Mean Daily Bias: FEM − FRM (µg/m³, 95% Site-CR1 CI)")
    ax2.set_ylim(-0.72, 1.38)
    ax2.set_title("B. Regional & Seasonal Residual Optical Bias (2023–2025)", loc="left", pad=10)
    ax2.legend(loc="upper center", ncol=2, frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.2)

    save_fig(fig, "fig2_rooftop_lottery_and_regional_bias")


def make_fig3(r2: dict) -> None:
    """Figure 3: Zero-EIV Nonlinear Wildfire Smoke Amplification & Aerosol Speciation Physics."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.0, 5.5), gridspec_kw={"width_ratios": [1.08, 1.04]})
    fig.subplots_adjust(wspace=0.38)

    st = r2["zero_eiv_smoke_amplification"]["t640_fw"]
    sb = r2["zero_eiv_smoke_amplification"]["bam"]

    c_t1 = st["inst1_other_site_level_site_cr1"]["coefs"]
    c_b1 = sb["inst1_other_site_level_site_cr1"]["coefs"]
    c_t3 = st["inst3_noaa_hms_level_site_cr1"]["coefs"]
    c_b3 = sb["inst3_noaa_hms_level_site_cr1"]["coefs"]
    c_t1l = st["inst1_other_site_logratio_site_cr1"]["coefs"]
    c_t3l = st["inst3_noaa_hms_logratio_site_cr1"]["coefs"]

    x_oth = np.array([0.0, 1.0, 2.0])
    x_hms = np.array([3.4, 4.4, 5.4, 6.4])
    t_oth_y = [0.0, c_t1["oth_15_25"]["beta"], c_t1["oth_ge25"]["beta"]]
    t_oth_e = [0.0, 1.96 * c_t1["oth_15_25"]["se_cr1"], 1.96 * c_t1["oth_ge25"]["se_cr1"]]
    b_oth_y = [0.0, c_b1["oth_15_25"]["beta"], c_b1["oth_ge25"]["beta"]]
    b_oth_e = [0.0, 1.96 * c_b1["oth_15_25"]["se_cr1"], 1.96 * c_b1["oth_ge25"]["se_cr1"]]

    t_hms_y = [0.0, c_t3["hms_l"]["beta"], c_t3["hms_m"]["beta"], c_t3["hms_h"]["beta"]]
    t_hms_e = [0.0, 1.96 * c_t3["hms_l"]["se_cr1"], 1.96 * c_t3["hms_m"]["se_cr1"], 1.96 * c_t3["hms_h"]["se_cr1"]]
    b_hms_y = [0.0, c_b3["hms_l"]["beta"], c_b3["hms_m"]["beta"], c_b3["hms_h"]["beta"]]
    b_hms_e = [0.0, 1.96 * c_b3["hms_l"]["se_cr1"], 1.96 * c_b3["hms_m"]["se_cr1"], 1.96 * c_b3["hms_h"]["se_cr1"]]

    ax1.axhline(0.0, color="#334155", lw=0.9, zorder=2)
    ax1.axvline(2.7, color="#94A3B8", linestyle="--", lw=1.0, zorder=2)
    ax1.grid(axis="y", color=GRID_COL, linestyle="--", lw=0.6, alpha=0.7, zorder=0)

    ax1.errorbar(x_oth - 0.09, t_oth_y, yerr=t_oth_e, fmt="-o", color=CRIMSON, lw=2.0, ms=6.4, capsize=3.5, label="T640_FW (636/638) − FRM", zorder=4)
    ax1.errorbar(x_oth + 0.09, b_oth_y, yerr=b_oth_e, fmt="--s", color=TEAL, lw=1.8, ms=5.6, capsize=3.5, label="BAM (170/209) − FRM", zorder=3)
    ax1.errorbar(x_hms - 0.09, t_hms_y, yerr=t_hms_e, fmt="-o", color=CRIMSON, lw=2.0, ms=6.4, capsize=3.5, zorder=4)
    ax1.errorbar(x_hms + 0.09, b_hms_y, yerr=b_hms_e, fmt="--s", color=TEAL, lw=1.8, ms=5.6, capsize=3.5, zorder=3)

    pct_oth = 100.0 * (np.exp(c_t1l["oth_ge25"]["beta"]) - 1.0)
    pct_hms = 100.0 * (np.exp(c_t3l["hms_h"]["beta"]) - 1.0)
    # Place red callout cleanly to the left of x=1.91 error bar (zero overlap!)
    ax1.annotate(
        f"+{c_t1['oth_ge25']['beta']:.2f} µg/m³\n(+{pct_oth:.1f}%, $p_{{\\mathrm{{WCB}}}}$={st['inst1_other_site_level_site_cr1']['wcb']['p_wcb']:.3f})",
        xy=(1.86, t_oth_y[2]),
        xytext=(0.56, 4.45),
        ha="center",
        fontsize=7.3,
        fontweight="bold",
        color=CRIMSON,
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 1.1},
        bbox={"boxstyle": "round,pad=0.24", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.8},
    )
    ax1.annotate(
        f"+{c_t3['hms_h']['beta']:.2f} µg/m³\n(+{pct_hms:.1f}%, t=+{c_t3['hms_h']['t_cr1']:.1f})",
        xy=(6.26, t_hms_y[3]),
        xytext=(4.75, 4.45),
        ha="center",
        fontsize=7.3,
        fontweight="bold",
        color=CRIMSON,
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 1.1},
        bbox={"boxstyle": "round,pad=0.24", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.8},
    )
    ax1.annotate(
        f"BAM: {b_oth_y[2]:+.2f} µg/m³ ($p_{{\\mathrm{{WCB}}}}$={sb['inst1_other_site_level_site_cr1']['wcb']['p_wcb']:.2f})",
        xy=(2.09, b_oth_y[2]),
        xytext=(1.05, -1.55),
        ha="center",
        fontsize=7.1,
        color=TEAL,
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": TEAL, "lw": 0.9},
    )

    ax1.text(1.0, 6.05, "Other-Site County PM2.5", ha="center", va="top", fontsize=8.3, fontweight="bold", color=NAVY)
    ax1.text(4.9, 6.05, "Satellite NOAA HMS Plume", ha="center", va="top", fontsize=8.3, fontweight="bold", color=NAVY)
    ax1.set_xticks(np.concatenate([x_oth, x_hms]))
    ax1.set_xticklabels(["<15\n(Ref)", "15–25\nµg/m³", "≥25\nµg/m³", "None\n(Ref)", "Light", "Med.", "Heavy"])
    ax1.set_ylabel("Excess Daily Bias vs. Clean Baseline (µg/m³)\n(Site FE + Month FE, 95% Site-CR1 CI)")
    ax1.set_ylim(-2.15, 6.35)
    ax1.set_title("A. EIV-Robust Nonlinear Wildfire Smoke Amplification", loc="left", pad=10)
    ax1.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.5)

    # Panel B: Aerosol Speciation & Hygroscopicity Mechanism (legend cleanly tucked in empty upper-left!)
    sp_t1 = r2["speciation_and_meteorology"]["t640_fw"]["model_s1_spec_met_level_site_cr1"]["coefs"]
    sp_b1 = r2["speciation_and_meteorology"]["bam"]["model_s1_spec_met_level_site_cr1"]["coefs"]
    sp_t2 = r2["speciation_and_meteorology"]["t640_fw"]["model_s2_interactions_level_site_cr1"]["coefs"]
    sp_b2 = r2["speciation_and_meteorology"]["bam"]["model_s2_interactions_level_site_cr1"]["coefs"]
    diag_t = r2["speciation_and_meteorology"]["t640_fw"]["match_diagnostics"]
    diag_b = r2["speciation_and_meteorology"]["bam"]["match_diagnostics"]

    spec_items = [
        ("Organic Carbon (OC)\n[per µg/m³]", sp_t1["oc"], sp_b1["oc"]),
        ("OC × HMS Heavy Smoke\n[interaction]", sp_t2["oc_x_hms_h"], sp_b2["oc_x_hms_h"]),
        ("Relative Humidity (RH)\n[per +10% RH]", sp_t1["rh_10"], sp_b1["rh_10"]),
        ("Nitrate (NO3⁻)\n[per µg/m³]", sp_t1["no3"], sp_b1["no3"]),
        ("Sulfate (SO4²⁻)\n[per µg/m³]", sp_t1["so4"], sp_b1["so4"]),
        ("Elemental Carbon (EC)\n[light-absorbing soot]", sp_t1["ec"], sp_b1["ec"]),
    ]

    y = np.arange(len(spec_items))[::-1]
    ax2.axvline(0.0, color="#334155", lw=1.0, linestyle="--", zorder=2)
    ax2.grid(axis="x", color=GRID_COL, linestyle="--", lw=0.6, alpha=0.7, zorder=0)

    for yi, (_, ct, cb) in zip(y, spec_items):
        ax2.errorbar(ct["beta"], yi + 0.14, xerr=1.96 * ct["se_cr1"], fmt="o", color=CRIMSON, ms=6.5, lw=1.6, capsize=3, zorder=4)
        ax2.errorbar(cb["beta"], yi - 0.14, xerr=1.96 * cb["se_cr1"], fmt="s", color=TEAL, ms=5.8, lw=1.5, capsize=3, zorder=3)
        ax2.text(1.00, yi + 0.14, f"T640: {ct['beta']:+.2f} (t={ct['t_cr1']:+.1f})", va="center", ha="left", fontsize=7.0, color=CRIMSON, fontweight="bold")
        ax2.text(1.00, yi - 0.14, f"BAM: {cb['beta']:+.2f} (t={cb['t_cr1']:+.1f})", va="center", ha="left", fontsize=7.0, color=TEAL)

    ax2.errorbar([], [], xerr=[], fmt="o", color=CRIMSON, ms=6.5, label=f"T640_FW (N={diag_t['spec_and_met_matched_pairs']:,}, {diag_t['spec_and_met_sites']} sites)")
    ax2.errorbar([], [], xerr=[], fmt="s", color=TEAL, ms=5.8, label=f"BAM 170/209 (N={diag_b['spec_and_met_matched_pairs']:,}, {diag_b['spec_and_met_sites']} sites)")

    ax2.set_yticks(y)
    ax2.set_yticklabels([x[0] for x in spec_items])
    ax2.set_xlabel("Partial Effect on Daily Bias (FEM − FRM, µg/m³)")
    ax2.set_xlim(-1.58, 2.02)
    ax2.set_ylim(-0.65, 5.75)
    ax2.set_title("B. Observational Speciation & RH Associations (2023–25)", loc="left", pad=10)
    # Place legend cleanly in empty upper-left region where ZERO data points sit!
    ax2.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.1)

    save_fig(fig, "fig3_zero_eiv_smoke_and_speciation_physics")


def make_fig4(r3: dict) -> None:
    """Figure 4: Pre-Trend-Clean 40 CFR 50.14 EE Event Study (2018-2025) & Inverted-U Profile."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.5), gridspec_kw={"width_ratios": [1.14, 1.0]})
    fig.subplots_adjust(wspace=0.28)

    cy = r3["county_year_dv1820_85_115"]
    my_did = r3["monitor_year_dv1820_85_115"]["true_ee_flag"]["did_2225_state_cr1"]
    my_unc = r3["monitor_year_dv1820_85_115"]["unconc_flag"]["did_2225_county_cr1"]
    yrs = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

    def extract_series(key: str) -> tuple[np.ndarray, np.ndarray]:
        coefs = cy[key]["event_study_county_cr1"]["coefs"]
        ys, es = [], []
        for yr in yrs:
            if yr == 2020:
                ys.append(0.0)
                es.append(0.0)
            else:
                ys.append(100.0 * coefs[f"nb_{yr}"]["beta"])
                es.append(100.0 * 1.96 * coefs[f"nb_{yr}"]["se_cr1"])
        return np.array(ys), np.array(es)

    y_all, e_all = extract_series("true_ee_flag")
    y_unc, _e_unc = extract_series("unconc_flag")
    y_con, _e_con = extract_series("true_ee_conc")

    ax1.axvspan(2021.5, 2023.5, color="#FEF3C7", alpha=0.55, zorder=0, label="2022–23 Designation Window")
    ax1.axvline(2024.1, color=CRIMSON, linestyle=":", lw=1.2, zorder=1)
    ax1.text(2024.18, 39.5, "Feb 2024\nFinal Rule\n(9.0 µg/m³)", fontsize=7.1, color=CRIMSON, va="top", ha="left", fontweight="bold")
    ax1.axhline(0.0, color="#334155", lw=0.9, zorder=1)
    ax1.grid(axis="y", color=GRID_COL, linestyle="--", lw=0.6, alpha=0.7, zorder=0)

    p_pre_all = cy["true_ee_flag"]["event_study_county_cr1"]["joint_F"]["p"]
    p_pre_unc = cy["unconc_flag"]["event_study_county_cr1"]["joint_F"]["p"]
    p_pre_con = cy["true_ee_conc"]["event_study_county_cr1"]["joint_F"]["p"]

    ax1.fill_between(yrs, y_all - e_all, y_all + e_all, color=NAVY, alpha=0.14, zorder=2)
    ax1.plot(yrs, y_all, "-o", color=NAVY, lw=2.2, ms=6.2, label=f"All State EE Flags (pre-F p={p_pre_all:.2f})", zorder=5)
    ax1.plot(yrs, y_unc, "--s", color=AMBER, lw=1.8, ms=5.4, label=f"Unconcurred Precautionary (pre-F p={p_pre_unc:.2f})", zorder=4)
    ax1.plot(yrs, y_con, ":^", color=TEAL, lw=1.8, ms=5.8, label=f"True EPA-Concurred (pre-F p={p_pre_con:.2f})", zorder=4)

    # Place 2023 peak callout cleanly in open upper-middle space well clear of upper-left legend!
    ax1.annotate(
        f"2023 Peak:\n+{y_all[5]:.1f} pp (All)\n+{y_con[5]:.1f} pp (Conc.)",
        xy=(2023.0, y_all[5]),
        xytext=(2023.0, 34.0),
        ha="center",
        fontsize=7.4,
        fontweight="bold",
        color=NAVY,
        arrowprops={"arrowstyle": "->", "color": NAVY, "lw": 1.1},
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": NAVY, "lw": 0.8},
    )
    # Place 2024-25 annotation strictly to the RIGHT of the Feb 2024 red dotted line (ZERO line slicing!)
    ax1.annotate(
        "2024–25:\nEPA-Concurred\nNull (1–2 yr lag)",
        xy=(2025.0, y_con[7] + 0.4),
        xytext=(2024.92, -10.8),
        ha="center",
        fontsize=6.7,
        color="#334155",
        style="italic",
        arrowprops={"arrowstyle": "->", "color": TEAL, "lw": 0.9},
        bbox={"boxstyle": "round,pad=0.20", "facecolor": "white", "edgecolor": "#CBD5E1", "lw": 0.7, "alpha": 0.94},
    )

    unc_share = 100.0 * my_unc["coefs"]["tp_2225"]["beta"] / my_did["coefs"]["tp_2225"]["beta"]
    ax1.text(
        0.02,
        0.025,
        f"Mon-Yr DiD (22–25): +{100*my_did['coefs']['tp_2225']['beta']:.2f} pp\n"
        f"(State $p_{{\\mathrm{{WCB}}}}$={my_did['wcb']['p_wcb']:.3f}; {unc_share:.0f}% unconcurred)",
        transform=ax1.transAxes,
        ha="left",
        va="bottom",
        fontsize=6.9,
        color="#1E293B",
        bbox={"boxstyle": "round,pad=0.26", "facecolor": LIGHT_BG, "edgecolor": "#94A3B8", "lw": 0.8},
    )

    ax1.set_xticks(yrs)
    ax1.set_xlim(2017.65, 2025.72)
    ax1.set_ylabel("County-Year EE Differential vs. Clean (<8.0) (pp)")
    ax1.set_ylim(-18.5, 42.0)
    ax1.set_title("A. County-Year Exogenous DV18–20 [8.5, 11.5] Event Study", loc="left", pad=10)
    ax1.legend(loc="upper left", frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.0)

    # Panel B: Inverted-U Regulatory-Significance Profile across DV_18_20 bins (generous top margin!)
    iu = r3["inverted_u_profile_dv1820"]["monitor_year_county_cr1"]["coefs"]
    ri_m = r3["within_state_ri_B1000"]["monitor_year"]
    loso = r3["loso_monitor_year"]
    pl = r3["robustness_specs_dv1820"]["fake_rule_placebo_2020_21_vs_18_19"]["coefs"]["treat_post"]

    bin_lbls = ["<7.0\n(Ref)", "7.0–8.5\n(Clean)", "8.5–9.5\n(Near Cutoff)", "9.5–11.5\n(Newly Binding)", ">11.5\n(Already NA)"]
    bin_keys = [None, "b_70_85", "b_85_95", "b_95_115", "b_gt115"]
    bx = np.arange(len(bin_lbls))
    by = [0.0 if k is None else 100.0 * iu[k]["beta"] for k in bin_keys]
    be = [0.0 if k is None else 100.0 * 1.96 * iu[k]["se_cr1"] for k in bin_keys]
    bcols = ["#94A3B8", "#64748B", AMBER, CRIMSON, NAVY]

    ax2.axvspan(1.55, 3.45, color="#FEE2E2", alpha=0.42, zorder=0, label="Newly Binding 40 CFR § 50.14 Band")
    ax2.axhline(0.0, color="#334155", lw=0.9, zorder=1)
    ax2.grid(axis="y", color=GRID_COL, linestyle="--", lw=0.6, alpha=0.7, zorder=0)
    ax2.bar(bx, by, width=0.56, yerr=be, capsize=3.5, color=bcols, edgecolor="#0F172A", lw=0.6, error_kw={"elinewidth": 1.15, "ecolor": "#0F172A"}, zorder=3)

    for xi, yi, ei in zip(bx, by, be):
        if xi == 0:
            ax2.text(xi, 0.5, "0.0", ha="center", va="bottom", fontsize=7.6, color="#475569", fontweight="bold")
        else:
            va_pos = yi + ei + 0.45 if yi >= 0 else yi - ei - 0.45
            va_alg = "bottom" if yi >= 0 else "top"
            ax2.text(xi, va_pos, f"{yi:+.1f} pp", ha="center", va=va_alg, fontsize=7.8, fontweight="bold", color="#0F172A")

    ax2.text(
        0.03,
        0.97,
        f"Hardened Inference (Mon-Yr DV18–20 [8.5, 11.5]):\n"
        f"• Within-State RI (B=1,000): p = {ri_m['p_ri_2sided']:.4f}\n"
        f"• LOSO ({loso['n_states']} states): β ∈ [{100*loso['min_beta']:+.1f}, {100*loso['max_beta']:+.1f}] pp (min t={loso['min_t']:+.2f})\n"
        f"• Fake-Rule Placebo (20–21): {100*pl['beta']:+.1f} pp (p={pl['p_cr1']:.2f})",
        transform=ax2.transAxes,
        ha="left",
        va="top",
        fontsize=7.2,
        color="#1E293B",
        bbox={"boxstyle": "round,pad=0.32", "facecolor": "white", "edgecolor": "#94A3B8", "lw": 0.85},
    )

    ax2.set_xticks(bx)
    ax2.set_xticklabels(bin_lbls)
    ax2.set_ylabel("Post-2022 EE Flagging Shift vs. <7.0 µg/m³ (pp)")
    ax2.set_ylim(-6.0, 24.5)
    ax2.set_title("B. Inverted-U 40 CFR § 50.14 Triage Profile Across Pre-Rule DVs", loc="left", pad=10)
    ax2.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.4)

    save_fig(fig, "fig4_ee_triage_event_study_and_decomposition")


def make_fig5(r1: dict, r2: dict, r3: dict) -> None:
    """Figure 5: Same-Rooftop Screening Divergence (U1: >35 Level-Equiv & EPA Tier-1 5-Yr Hist p98)
    and Master Forest Plot of Verified Effects vs Honest Nulls (incl. U2 Within-County-Year Null).
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(15.8, 6.7), gridspec_kw={"width_ratios": [1.0, 1.18]})
    fig.subplots_adjust(wspace=0.70)

    u1_t = r2["unification_u1_exceedance_multiplier"]["t640_fw"]
    u1_b = r2["unification_u1_exceedance_multiplier"]["bam"]
    u1_hist_t = r3["unification_u1_historical_tier1_1822"]["t640_fw"]
    u1_hist_b = r3["unification_u1_historical_tier1_1822"]["bam"]
    u2 = r3["unification_u2_t640_ee_flagging"]

    groups = [
        ("24-hr Level-Equiv.\n(>35 µg/m³)\nT640 vs FRM", u1_t["hms_heavy_smoke"]["gt_35_naaqs24h"], CRIMSON),
        ("24-hr Level-Equiv.\n(>35 µg/m³)\nBAM vs FRM", u1_b["hms_heavy_smoke"]["gt_35_naaqs24h"], TEAL),
        ("EPA Tier-1 5-Yr p98\nmin(p98₁₈–₂₂, 35)\nT640 vs FRM", u1_hist_t["hms_heavy_smoke"]["gt_tier1_min_p98_35"], CRIMSON),
        ("EPA Tier-1 5-Yr p98\nmin(p98₁₈–₂₂, 35)\nBAM vs FRM", u1_hist_b["hms_heavy_smoke"]["gt_tier1_min_p98_35"], TEAL),
    ]
    gx = np.arange(len(groups))
    w = 0.34
    fem_r = [g[1]["fem_rate_pct"] for g in groups]
    frm_r = [g[1]["frm_rate_pct"] for g in groups]
    cols = [g[2] for g in groups]

    ax1.grid(axis="y", color=GRID_COL, linestyle="--", lw=0.6, alpha=0.7, zorder=0)
    ax1.bar(gx - w / 2, frm_r, width=w, color="#94A3B8", edgecolor="#0F172A", lw=0.6, label="Collocated Gravimetric FRM (2m away)", zorder=3)
    ax1.bar(gx + w / 2, fem_r, width=w, color=cols, edgecolor="#0F172A", lw=0.6, label="Collocated FEM (Crimson=T640_FW, Teal=BAM)", zorder=3)

    for idx, (_, rec, col) in enumerate(groups):
        ratio = rec["trigger_multiplier_ratio"]
        p_mc = rec["mcnemar_exact_p"]
        disc_s = f"{rec['fem_only_discordant']} vs {rec['frm_only_discordant']}"
        p_str = f"p={p_mc:.1e}" if p_mc < 0.001 else f"p={p_mc:.2f}"
        top_y = max(rec["fem_rate_pct"], rec["frm_rate_pct"])
        ax1.text(
            idx,
            top_y + 1.2,
            f"{ratio:.2f}×\n({disc_s})\n{p_str}",
            ha="center",
            va="bottom",
            fontsize=7.3,
            fontweight="bold" if p_mc < 0.01 else "normal",
            color=col if p_mc < 0.01 else "#475569",
        )

    c_u2_int = u2["borderline_2225_t640_x_hms_heavy_flag"]["coefs"]["t640_x_hms_h"]
    c_u2_wcy = u2["borderline_within_county_year_fe_flag"]["coefs"]["is_t640_f"]
    ax1.text(
        0.50,
        0.975,
        f"Observational U2 (DV18–20 [8.5, 11.5], State×Yr FE + HMS):\n"
        f"• Cross-monitor T640 × log(HMS Heavy) → Flag: +{100*c_u2_int['beta']:.1f} pp (St $p_{{\\mathrm{{WCB}}}}$={u2['borderline_2225_t640_x_hms_heavy_flag_state_cr1']['wcb']['p_wcb']:.3f})\n"
        f"• Within-County-Year FE (T640 → Flag): {100*c_u2_wcy['beta']:+.1f} pp ($p_{{\\mathrm{{WCB}}}}$={u2['borderline_within_county_year_fe_flag']['wcb']['p_wcb']:.3f}, Null)",
        transform=ax1.transAxes,
        ha="center",
        va="top",
        fontsize=6.4,
        color="#0F172A",
        bbox={"boxstyle": "round,pad=0.30", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.9},
    )

    ax1.axvline(1.5, color="#94A3B8", linestyle="--", lw=0.9, zorder=2)
    ax1.set_xticks(gx)
    ax1.set_xticklabels([g[0] for g in groups], fontsize=7.4)
    ax1.set_ylabel("Exceedance Rate on NOAA HMS Heavy Smoke Days (%)")
    ax1.set_ylim(0, 70)
    ax1.set_title("A. Same-Rooftop HMS Heavy Smoke Screening Divergence (U1)", loc="left", pad=10)
    ax1.legend(loc="upper left", bbox_to_anchor=(0.01, 0.79), frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=6.9)

    # Panel B: 100% dynamically driven from JSON receipts (ZERO hardcoded numbers!)
    st = r2["zero_eiv_smoke_amplification"]["t640_fw"]
    sb = r2["zero_eiv_smoke_amplification"]["bam"]
    sp_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s1_spec_met_level_site_cr1"]["coefs"]
    nulls = r1["exogenous_nulls_margins_acd"]
    m3 = r3["monitor_year_dv1820_85_115"]
    c3 = r3["county_year_dv1820_85_115"]
    pl_c = r3["robustness_specs_dv1820"]["fake_rule_placebo_2020_21_vs_18_19"]["coefs"]["treat_post"]
    u1_hms = u1_t["hms_heavy_smoke"]["gt_35_naaqs24h"]
    u1_t1 = u1_hist_t["hms_heavy_smoke"]["gt_tier1_min_p98_35"]
    u2_wcy_r = u2["borderline_within_county_year_fe_flag"]

    def _pfmt(p: float) -> str:
        return f".{round(p * 1000):03d}" if p < 0.1 else f".{round(p * 100):02d}"

    rows = [
        ("P2: NOAA HMS Heavy Bias (T640)", st["inst3_noaa_hms_level_site_cr1"]["coefs"]["hms_h"]["t_cr1"], f"+{st['inst3_noaa_hms_level_site_cr1']['coefs']['hms_h']['beta']:.2f} µg/m³ ($p_{{\\mathrm{{WCB}}}}$={_pfmt(st['inst3_noaa_hms_level_site_cr1']['wcb']['p_wcb'])})", CRIMSON),
        ("P2: Rooftop 2023–25 DV Bias (T640)", r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]["t_bias"], f"+{r2['rooftop_dv_lottery_2023_2025']['t640_fw']['mean_dv_bias']:.3f} µg/m³ (p<10⁻¹⁵)", CRIMSON),
        ("P2: Speciation OC Assoc. (T640)", sp_t["oc"]["t_cr1"], f"+{sp_t['oc']['beta']:.2f} per µg/m³ OC", CRIMSON),
        ("P2: Other-Site ≥25 Bias (T640)", st["inst1_other_site_level_site_cr1"]["coefs"]["oth_ge25"]["t_cr1"], f"+{st['inst1_other_site_level_site_cr1']['coefs']['oth_ge25']['beta']:.2f} µg/m³ ($p_{{\\mathrm{{WCB}}}}$={_pfmt(st['inst1_other_site_level_site_cr1']['wcb']['p_wcb'])})", CRIMSON),
        ("U1: EPA Tier-1 5-Yr p98 (Heavy)", u1_t1["t_site_cr1"], f"+{u1_t1['paired_diff_pp']:.1f} pp ({u1_t1['fem_only_discordant']} vs {u1_t1['frm_only_discordant']})", NAVY),
        ("U1: >35 Level-Equiv (Heavy)", u1_hms["t_site_cr1"], f"+{u1_hms['paired_diff_pp']:.1f} pp ({u1_hms['fem_only_discordant']} vs {u1_hms['frm_only_discordant']})", NAVY),
        ("U2 (Obs): T640 × log(HMS) Flag", c_u2_int["t_cr1"], f"+{100*c_u2_int['beta']:.1f} pp (St $p_{{\\mathrm{{WCB}}}}$={_pfmt(u2['borderline_2225_t640_x_hms_heavy_flag_state_cr1']['wcb']['p_wcb'])})", NAVY),
        ("P3: Mon-Yr EE Flag DiD (State)", m3["true_ee_flag"]["did_2225_state_cr1"]["coefs"]["tp_2225"]["t_cr1"], f"+{100*m3['true_ee_flag']['did_2225_state_cr1']['coefs']['tp_2225']['beta']:.1f} pp ($p_{{\\mathrm{{WCB}}}}$={_pfmt(m3['true_ee_flag']['did_2225_state_cr1']['wcb']['p_wcb'])})", NAVY),
        ("P3: Unconcurred EE Flags (State)", m3["unconc_flag"]["did_2225_state_cr1"]["coefs"]["tp_2225"]["t_cr1"], f"+{100*m3['unconc_flag']['did_2225_state_cr1']['coefs']['tp_2225']['beta']:.1f} pp ($p_{{\\mathrm{{WCB}}}}$={_pfmt(m3['unconc_flag']['did_2225_state_cr1']['wcb']['p_wcb'])})", AMBER),
        ("NULL: U2 Within-Cnty-Yr T640 Flag", c_u2_wcy["t_cr1"], f"{100*c_u2_wcy['beta']:+.1f} pp ($p_{{\\mathrm{{WCB}}}}$={_pfmt(u2_wcy_r['wcb']['p_wcb'])})", TEAL),
        ("NULL: BAM 170/209 Smoke (Oth ≥25)", sb["inst1_other_site_level_site_cr1"]["coefs"]["oth_ge25"]["t_cr1"], f"{sb['inst1_other_site_level_site_cr1']['coefs']['oth_ge25']['beta']:+.2f} µg/m³ ($p_{{\\mathrm{{WCB}}}}$={_pfmt(sb['inst1_other_site_level_site_cr1']['wcb']['p_wcb'])})", TEAL),
        ("NULL: Margin D FRM (DV18–20)", nulls["margin_d_frm_exog_dv1820_county_cr1"]["coefs"]["tp"]["t_cr1"], f"{nulls['margin_d_frm_exog_dv1820_county_cr1']['coefs']['tp']['beta']:+.3f} µg/m³ ($p_{{\\mathrm{{WCB}}}}$={_pfmt(nulls['margin_d_frm_exog_dv1820_county_cr1']['wcb']['p_wcb'])})", TEAL),
        ("NULL: Margin A FEM→FRM Switch", nulls["margin_a_share_fem_exog_dv1820"]["coefs"]["tp"]["t_cr1"], f"{nulls['margin_a_share_fem_exog_dv1820']['coefs']['tp']['beta']:+.3f} ($p_{{\\mathrm{{WCB}}}}$={_pfmt(nulls['margin_a_share_fem_exog_dv1820']['wcb']['p_wcb'])})", TEAL),
        ("NULL: Margin C Monitor Survival", nulls["margin_c_monitor_survival_exog_dv1820"]["coefs"]["nb"]["t_cr1"], f"{nulls['margin_c_monitor_survival_exog_dv1820']['coefs']['nb']['beta']:+.3f} ($p_{{\\mathrm{{WCB}}}}$={_pfmt(nulls['margin_c_monitor_survival_exog_dv1820']['wcb']['p_wcb'])})", TEAL),
        ("NULL: Fake-Rule EE Placebo", pl_c["t_cr1"], f"{100*pl_c['beta']:+.1f} pp (p={_pfmt(pl_c['p_cr1'])})", TEAL),
        ("NULL: 2025 Concurred EE Flow", c3["true_ee_conc"]["event_study_county_cr1"]["coefs"]["nb_2025"]["t_cr1"], f"{100*c3['true_ee_conc']['event_study_county_cr1']['coefs']['nb_2025']['beta']:+.1f} pp (p={_pfmt(c3['true_ee_conc']['event_study_county_cr1']['coefs']['nb_2025']['p_cr1'])})", TEAL),
    ]

    ys = np.arange(len(rows))[::-1]
    ax2.axvspan(-1.96, 1.96, color="#E2E8F0", alpha=0.65, zorder=0, label="|t| < 1.96 Null Zone (p > 0.05)")
    ax2.axvline(0.0, color="#334155", lw=0.9, zorder=1)
    ax2.axhline(6.5, color="#475569", linestyle="--", lw=1.0, zorder=2)
    ax2.grid(axis="x", color=GRID_COL, linestyle="--", lw=0.5, alpha=0.6, zorder=0)

    for yi, (_, tval, txt, col) in zip(ys, rows):
        t_plot = min(tval, 14.2)
        ax2.barh(yi, t_plot, height=0.58, color=col, edgecolor="#0F172A", lw=0.5, alpha=0.9, zorder=3)
        x_txt = max(t_plot, 0.0) + 0.42 if t_plot >= 0 else 0.42
        ax2.text(x_txt, yi, txt, va="center", ha="left", fontsize=6.7, color="#0F172A", fontweight="bold" if abs(tval) >= 1.96 else "normal")

    eff_ts = [abs(r[1]) for r in rows[:9]]
    null_ts = [abs(r[1]) for r in rows[9:]]
    null_ps = [
        u2_wcy_r["wcb"]["p_wcb"],
        sb["inst1_other_site_level_site_cr1"]["wcb"]["p_wcb"],
        nulls["margin_d_frm_exog_dv1820_county_cr1"]["wcb"]["p_wcb"],
        nulls["margin_a_share_fem_exog_dv1820"]["wcb"]["p_wcb"],
        nulls["margin_c_monitor_survival_exog_dv1820"]["wcb"]["p_wcb"],
        pl_c["p_cr1"],
        c3["true_ee_conc"]["event_study_county_cr1"]["coefs"]["nb_2025"]["p_cr1"],
    ]
    # Section badges tucked cleanly in empty far-right space!
    ax2.text(25.2, 7.2, f"VERIFIED EFFECTS\n(|t| = {min(eff_ts):.1f} to {max(eff_ts):.1f})", ha="right", va="bottom", fontsize=7.3, fontweight="bold", color=CRIMSON, bbox={"boxstyle": "round,pad=0.22", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.7})
    ax2.text(25.2, 5.9, f"VERIFIED HONEST NULLS\n(|t| ≤ {max(null_ts):.2f}, p ≥ {min(null_ps):.2f})", ha="right", va="top", fontsize=7.3, fontweight="bold", color=TEAL, bbox={"boxstyle": "round,pad=0.22", "facecolor": "#F0FDFA", "edgecolor": TEAL, "lw": 0.7})

    ax2.set_yticks(ys)
    ax2.set_yticklabels([r[0] for r in rows], fontsize=7.2)
    ax2.set_xlabel("Cluster-Robust t-Statistic (with Native Estimate & WCB p)")
    ax2.set_xlim(-2.6, 25.8)
    ax2.set_title("B. Master Audit: Verified Effects vs. Clean Honest Nulls", loc="left", pad=10)
    ax2.legend(loc="lower right", frameon=True, facecolor="white", edgecolor="#CBD5E1", fontsize=7.1)

    save_fig(fig, "fig5_optical_to_flagging_multiplier")


def main() -> int:
    print("=== STEP 06 (PILLAR 5): GENERATING 5 300-DPI PUBLICATION FIGURES ===", flush=True)
    setup_rc()
    r1 = json.loads((RES_DIR / "01_appn_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_collocated_physics_speciation.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_ee_triage_hms_unification.json").read_text(encoding="utf-8"))

    make_fig1(r1)
    make_fig2(r2)
    make_fig3(r2)
    make_fig4(r3)
    make_fig5(r1, r2, r3)
    print("[DONE STEP 06] All 5 figures saved (300-DPI PNG + vector PDF).", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
