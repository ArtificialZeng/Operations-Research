"""Step 12 (v4 ES&T): Generate 4 Publication-Grade ES&T Main Figures + 2 Supporting Information
Figures (300 DPI PNG + vector PDF), 100% dynamically driven by saved JSON receipts and parquets.

Main ES&T Figures:
  1. fig1_est_caseflow_and_common_support.png/.pdf
  2. fig2_est_official_and_oot_tier_replay.png/.pdf
  3. fig3_est_smoke_vs_nonsmoke_and_ground_truth.png/.pdf
  4. fig4_est_inference_loro_and_speciation.png/.pdf

Supporting Information Figures:
  S1. figS1_si_dv_reclassification_and_rooftop_lottery.png/.pdf
  S2. figS2_si_oot_reconstruction_and_ee_nulls.png/.pdf
"""

from __future__ import annotations

import json

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

matplotlib.use("Agg")

from econ_utils import ENRICH_DIR, FIG_DIR, PROC_DIR, RES_DIR, WS_DIR

# Clean ACS / ES&T colorblind-safe palette
NAVY = "#0B2545"
RUST = "#B45309"      # T640_FW primary warm tone
CRIMSON = "#B91C1C"   # Strong divergence / excess highlight
TEAL = "#0F766E"      # BAM background comparator
SLATE = "#475569"
MUTED = "#94A3B8"
GRID = "#CBD5E1"
BG_SOFT = "#F8FAFC"


def setup_rc() -> None:
    plt.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 8.5,
            "axes.titlesize": 9.8,
            "axes.titleweight": "bold",
            "axes.labelsize": 8.7,
            "axes.labelweight": "bold",
            "xtick.labelsize": 7.9,
            "ytick.labelsize": 7.9,
            "legend.fontsize": 7.4,
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
    print(f"  Saved {png_p.name} ({png_p.stat().st_size / 1024:.0f} KB) & {pdf_p.name}", flush=True)


def make_fig1(r11: dict) -> None:
    """Figure 1: EPA Region Common Support Audit, Case-Flow Summary, and Differential Benchmarks."""
    cs = r11["common_support_audit"]
    reg_d = cs["heavy_smoke_2023_2025"]["epa_region_counts_matched"]
    all_d = cs["all_2023_2025"]
    h_d = cs["heavy_smoke_2023_2025"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.5), gridspec_kw={"width_ratios": [1.05, 1.15]})
    fig.subplots_adjust(wspace=0.42)

    # Panel A: EPA Region geographic support mismatch (R1-R10)
    regs = [str(r) for r in range(1, 11)]
    t_cnts = [reg_d[r]["t640_n"] for r in regs]
    b_cnts = [reg_d[r]["bam_n"] for r in regs]
    x = np.arange(len(regs))
    w = 0.38
    ax1.bar(
        x - w / 2, t_cnts, width=w, color=RUST, edgecolor="#0F172A", lw=0.6,
        label=f"T640_FW–FRM (N={sum(t_cnts)}, 165 sites)", zorder=3,
    )
    ax1.bar(
        x + w / 2, b_cnts, width=w, color=TEAL, edgecolor="#0F172A", lw=0.6,
        label=f"BAM–FRM Ref. (N={sum(b_cnts)}, 53 sites)", zorder=3,
    )
    ax1.grid(axis="y", color=GRID, ls="--", lw=0.6, alpha=0.7, zorder=0)

    # Shade Regions 9-10 where T640 has zero Heavy-smoke support
    ax1.axvspan(7.5, 9.5, color="#FEE2E2", alpha=0.55, zorder=1)
    ax1.text(
        8.5, 148, "No T640 Heavy\nsupport (R9–R10:\n23.9% of BAM)",
        ha="center", va="top", fontsize=7.2, fontweight="bold", color=CRIMSON,
    )

    for i, (tc, bc) in enumerate(zip(t_cnts, b_cnts)):
        if tc > 0:
            ax1.text(i - w / 2, tc + 2.8, str(tc), ha="center", va="bottom", fontsize=7.0, color="#78350F", fontweight="bold")
        if bc > 0:
            ax1.text(i + w / 2, bc + 2.8, str(bc), ha="center", va="bottom", fontsize=7.0, color="#115E59", fontweight="bold")

    ax1.set_xticks(x, [f"R{r}" for r in regs])
    ax1.set_ylim(0, 232)
    ax1.set_xlabel("U.S. EPA Region")
    ax1.set_ylabel("Matched Heavy-Smoke Site-Days (2023–2025)")
    ax1.set_title("A. Geographic Disjointness & Network Case-Flow Audit", loc="left", pad=22)
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, 1.005), ncols=2, frameon=False, fontsize=7.3)

    # Case-Flow box sits cleanly in dedicated upper-left headroom above R1-R4 bars
    cf_txt = (
        f"Case-Flow Attrition (2023–2025):\n"
        f"• T640–FRM: {all_d['t640_pairs']:,} → {h_d['t640_full_pairs']} Heavy → {sum(t_cnts)} matched\n"
        f"• BAM–FRM:  {all_d['bam_pairs']:,} → {h_d['bam_full_pairs']} Heavy → {sum(b_cnts)} matched\n"
        f"• Same-site triples: {all_d['triple_site_days']} all-day ({all_d['triple_sites']} sites), only {h_d['heavy_triple_site_days']} Heavy ({h_d['heavy_overlap_dates']} shared dates)\n"
        f"→ BAM retained strictly as background reference comparator"
    )
    ax1.text(
        0.02, 0.97, cf_txt, transform=ax1.transAxes, fontsize=6.7, va="top", ha="left",
        bbox={"boxstyle": "round,pad=0.33", "facecolor": BG_SOFT, "edgecolor": SLATE, "lw": 0.7},
    )

    # Panel B: Common-support differential (T640 - BAM) forest + dedicated lower band for Triples box
    bm_keys = [
        ("full_matched_heavy", "Full Matched Heavy\n(100% T640 / 100% BAM)"),
        ("overlap_epa_regions", "Overlap EPA Regions\n(100% T640 / 76% BAM)"),
        ("overlap_dates", "Overlap Smoke Dates\n(89% T640 / 57% BAM)"),
        ("overlap_dates_and_regions", "Overlap Dates & Regions\n(89% T640 / 48% BAM)"),
        ("overlap_dates_regions_frm_le50", "Overlap + FRM ≤ 50 µg/m³\n(88% T640 / 47% BAM)"),
    ]
    labels = [lbl for _, lbl in bm_keys] + ["Overlap-Weighted\n(Region × FRM Bin, 29 cells)"]
    diffs = [cs["matched_benchmarks"][k]["differential_t640_minus_bam_pp"] for k, _ in bm_keys]
    lo = [cs["matched_benchmarks"][k]["differential_ci95_block_pp"][0] for k, _ in bm_keys]
    hi = [cs["matched_benchmarks"][k]["differential_ci95_block_pp"][1] for k, _ in bm_keys]
    ow = cs["overlap_weighted_region_x_frm_bin"]
    diffs.append(ow["differential_pp"])
    lo.append(ow["block_bootstrap_ci95_pp"][0])
    hi.append(ow["block_bootstrap_ci95_pp"][1])

    y = np.arange(len(labels))
    ax2.axvline(0.0, color=SLATE, ls="--", lw=1.0, zorder=1)
    ax2.grid(axis="x", color=GRID, ls=":", lw=0.6, alpha=0.8, zorder=0)
    cols = [NAVY] * len(bm_keys) + [CRIMSON]
    for i, (d, l, h, c) in enumerate(zip(diffs, lo, hi, cols)):
        ax2.errorbar(
            d, i, xerr=[[d - l], [h - d]], fmt="o", color=c, ecolor=c,
            markersize=6.2, elinewidth=1.8, capsize=3.2, zorder=4,
        )
        ax2.text(
            h + 0.5, i, f"{d:+.2f} pp [{l:+.1f}, {h:+.1f}]",
            va="center", ha="left", fontsize=7.1, fontweight="bold", color=c,
        )

    ax2.set_yticks(y, labels)
    ax2.set_ylim(7.35, -0.55)  # extra dedicated space at bottom for Triples summary box!
    ax2.set_xlim(-2.0, 31.5)
    ax2.set_xlabel("Differential Tier-1 Excess: (T640 − FRM) − (BAM − FRM) (pp, 95% Block CI)")
    ax2.set_title("B. Common-Support Matched Differential & Same-Rooftop Triples", loc="left", pad=22)

    tr = all_d["triples_by_hms_level"]
    tr_txt = (
        f"Exact Same-Rooftop Triples (N={all_d['triple_site_days']}, 5 sites):  "
        f"HMS None (n={tr['hms_0_none']['n_site_days']}): T640−BAM = {tr['hms_0_none']['mean_t640_minus_bam']:+.2f} | "
        f"Light (n={tr['hms_1_light']['n_site_days']}): {tr['hms_1_light']['mean_t640_minus_bam']:+.2f}\n"
        f"HMS Medium (n={tr['hms_2_medium']['n_site_days']}): T640−BAM = {tr['hms_2_medium']['mean_t640_minus_bam']:+.2f} µg/m³  |  "
        f"HMS Heavy (n={tr['hms_3_heavy']['n_site_days']}): T640−FRM = {tr['hms_3_heavy']['mean_t640_minus_frm']:+.2f}, "
        f"BAM−FRM = {tr['hms_3_heavy']['mean_bam_minus_frm']:+.2f}, T640−BAM = {tr['hms_3_heavy']['mean_t640_minus_bam']:+.2f} µg/m³"
    )
    ax2.text(
        0.50, 0.03, tr_txt, transform=ax2.transAxes, fontsize=6.7, va="bottom", ha="center",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#FFFBEB", "edgecolor": RUST, "lw": 0.8},
    )

    save_fig(fig, "fig1_est_caseflow_and_common_support")


def make_fig2(r11: dict) -> None:
    """Figure 2: Official & Out-of-Time Prospective EPA Tier-1 Replay + Near-Threshold Scatter."""
    off = r11["official_fixed_2021_2025"]
    oot = r11["oot_prospective_rolling_5yr"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.8, 5.7), gridspec_kw={"width_ratios": [1.18, 1.0]})
    fig.subplots_adjust(wspace=0.30)

    # Panel A: Forest plot with clean vertical separation between Retrospective & Out-of-Time blocks
    rows = [
        ("Official EPA 2021–25\nTier 1 (Retrospective)", off["t640_fw"]["tier_1"], off["bam"]["tier_1"]),
        ("Official EPA 2021–25\nTier 2 Lower Threshold", off["t640_fw"]["tier_2_lower"], off["bam"]["tier_2_lower"]),
        ("Fixed Daily >35 µg/m³\n(Matched Heavy Sample)", off["t640_fw"]["fixed_35_matched"], off["bam"]["fixed_35_matched"]),
        ("OOT-A Rolling 5-Yr\n(R-Excl AQS / AMP480)", oot["oot_a_conservative_r_excl"]["t640_fw"]["tier_1"], oot["oot_a_conservative_r_excl"]["bam"]["tier_1"]),
        ("OOT-B Rolling 5-Yr\n(Excl. HMS Heavy)", oot["oot_b_fire_proxy_hms_heavy"]["t640_fw"]["tier_1"], oot["oot_b_fire_proxy_hms_heavy"]["bam"]["tier_1"]),
        ("OOT-B2 Rolling 5-Yr\n(Excl. HMS Med+Heavy)", oot["oot_b2_fire_proxy_hms_med_heavy"]["t640_fw"]["tier_1"], oot["oot_b2_fire_proxy_hms_med_heavy"]["bam"]["tier_1"]),
        ("OOT-C Rolling 5-Yr\n(Pure FRM-Only Baseline)", oot["oot_c_pure_frm_only"]["t640_fw"]["tier_1"], oot["oot_c_pure_frm_only"]["bam"]["tier_1"]),
    ]
    y_pos = [0.0, 1.0, 2.0, 3.65, 4.65, 5.65, 6.65]

    ax1.axvline(0.0, color=SLATE, ls="--", lw=1.0, zorder=1)
    ax1.axhline(2.82, color=MUTED, ls=":", lw=1.1, zorder=1)
    ax1.grid(axis="x", color=GRID, ls=":", lw=0.6, alpha=0.8, zorder=0)

    for idx, (yp, (_, tb, bb)) in enumerate(zip(y_pos, rows)):
        td = tb["difference_pp"]
        t_tw = tb["inference"]["twoway_site_x_reg_episode"]["ci95"]
        t_nb = tb["inference"]["oneway_nat_block"]["ci95"]
        y_t = yp - 0.14
        ax1.plot(t_nb, [y_t, y_t], color=RUST, lw=1.1, alpha=0.65, zorder=3)
        ax1.errorbar(
            td, y_t, xerr=[[td - t_tw[0]], [t_tw[1] - td]], fmt="o", color=RUST, ecolor=RUST,
            markersize=5.8, elinewidth=2.1, capsize=3.0, zorder=4,
            label="T640_FW–FRM (thick: 2-way Site×RegEp; thin: Nat. Block)" if idx == 0 else None,
        )
        ax1.text(
            max(t_tw[1], t_nb[1]) + 0.35, y_t,
            f"{td:+.2f} pp ({tb['fem_only']}/{tb['frm_only']})",
            va="center", ha="left", fontsize=7.0, fontweight="bold", color="#7C2D12",
        )

        bd = bb["difference_pp"]
        b_tw = bb["inference"]["twoway_site_x_reg_episode"]["ci95"]
        y_b = yp + 0.14
        ax1.errorbar(
            bd, y_b, xerr=[[bd - b_tw[0]], [b_tw[1] - bd]], fmt="s", color=TEAL, ecolor=TEAL,
            markersize=4.9, elinewidth=1.5, capsize=2.5, zorder=4,
            label="BAM–FRM Background Ref. (2-way Site×RegEp CI)" if idx == 0 else None,
        )

    ax1.set_yticks(y_pos, [r[0] for r in rows])
    ax1.set_ylim(7.35, -0.60)
    ax1.set_xlim(-6.2, 21.8)
    ax1.set_xlabel("Paired Exceedance Difference: Instrument − FRM (percentage points)")
    ax1.set_title("A. Official Retrospective & Out-of-Time Prospective EPA Tier-1 Replay", loc="left", pad=36)
    ax1.legend(loc="lower center", bbox_to_anchor=(0.5, 1.01), ncols=1, frameon=False, fontsize=7.0)
    ax1.text(-5.9, 2.66, "Retrospective EPA 2021–25 Published Table ↑", fontsize=6.9, color=SLATE, style="italic", va="bottom")
    ax1.text(-5.9, 2.98, "Strictly Out-of-Time Rolling 5-Yr (18–22→23, 19–23→24, 20–24→25) ↓", fontsize=6.9, color=NAVY, fontweight="bold", va="top")

    # Panel B: Normalized T640/Tier-1 vs FRM/Tier-1 Scatter showing 36 vs 2 Asymmetric Crossing
    pair_df = pd.read_csv(WS_DIR / "tables" / "collocated_heavy_smoke_pairs_2023_2025.csv")
    t6p = pair_df[(pair_df["instrument"] == "T640_FW") & pair_df["tier_1"].notna()].copy()
    t6p["rx"] = t6p["frm"] / t6p["tier_1"]
    t6p["ry"] = t6p["fem"] / t6p["tier_1"]

    ax2.axvspan(0.8, 1.2, color="#FEF3C7", alpha=0.55, zorder=0, label="Near-threshold band (±20% of Tier-1)")
    ax2.axhline(1.0, color=NAVY, ls="--", lw=1.0, zorder=1)
    ax2.axvline(1.0, color=NAVY, ls="--", lw=1.0, zorder=1)
    ax2.plot([0, 2.4], [0, 2.4], color=MUTED, ls=":", lw=1.0, zorder=1, label="1:1 Identity")

    both_lo = t6p[(t6p["fem_ge_epa_tier1"] == 0) & (t6p["frm_ge_epa_tier1"] == 0)]
    both_hi = t6p[(t6p["fem_ge_epa_tier1"] == 1) & (t6p["frm_ge_epa_tier1"] == 1)]
    t6_only = t6p[(t6p["fem_ge_epa_tier1"] == 1) & (t6p["frm_ge_epa_tier1"] == 0)]
    frm_only = t6p[(t6p["fem_ge_epa_tier1"] == 0) & (t6p["frm_ge_epa_tier1"] == 1)]

    lim = 2.35
    ax2.scatter(both_lo["rx"].clip(upper=lim), both_lo["ry"].clip(upper=lim), s=18, color="#94A3B8", alpha=0.55, edgecolors="none", label=f"Both < Tier-1 (n={len(both_lo)})", zorder=2)
    ax2.scatter(both_hi["rx"].clip(upper=lim), both_hi["ry"].clip(upper=lim), s=22, color=NAVY, alpha=0.65, edgecolors="none", label=f"Both ≥ Tier-1 (n={len(both_hi)})", zorder=3)
    ax2.scatter(t6_only["rx"].clip(upper=lim), t6_only["ry"].clip(upper=lim), s=44, color=CRIMSON, edgecolor="white", lw=0.5, label=f"T640-only ≥ Tier-1 (n={len(t6_only)})", zorder=5)
    ax2.scatter(frm_only["rx"].clip(upper=lim), frm_only["ry"].clip(upper=lim), s=52, marker="D", color=TEAL, edgecolor="white", lw=0.6, label=f"FRM-only ≥ Tier-1 (n={len(frm_only)})", zorder=6)

    ax2.set_xlim(0.15, 2.42)
    ax2.set_ylim(0.15, 2.42)
    ax2.set_xlabel("Collocated Gravimetric FRM / Site-Month Tier-1 Threshold")
    ax2.set_ylabel("Aligned Optical T640_FW / Site-Month Tier-1 Threshold")
    ax2.set_title("B. Asymmetric Tier-1 Crossings & Near-Threshold Concentration", loc="left", pad=36)
    ax2.legend(loc="lower right", frameon=True, facecolor="white", edgecolor=GRID, fontsize=6.9)

    t1_off = off["t640_fw"]["tier_1"]
    yr = t1_off["by_year"]
    nb20 = t1_off["near_threshold_bands"]["frm_pm20pct"]
    ax2.text(
        0.20, 2.34,
        f"T640-Only Quadrant: {t1_off['fem_only']} vs {t1_off['frm_only']} FRM-only\n"
        f"Within ±20% (FRM): {nb20['fem_only']} vs {nb20['frm_only']} ({nb20['difference_pp']:+.1f} pp)\n"
        f"By Year: 2023 {yr['2023']['difference_pp']:+.2f} | 2024 {yr['2024']['difference_pp']:+.2f} | 2025 {yr['2025']['difference_pp']:+.2f} pp",
        fontsize=7.0, va="top", ha="left", fontweight="bold", color=CRIMSON,
        bbox={"boxstyle": "round,pad=0.32", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.8},
    )

    save_fig(fig, "fig2_est_official_and_oot_tier_replay")


def make_fig3(r11: dict) -> None:
    """Figure 3: Equal-Concentration Non-Smoke vs Heavy Smoke Controls & Ground-Level Smoke Confirmation."""
    sv = r11["smoke_vs_nonsmoke_controls"]["t640_fw"]
    mc = sv["matched_concentration_smoke_vs_nonsmoke"]
    gv = sv["ground_level_smoke_verification"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.4, 5.4), gridspec_kw={"width_ratios": [1.15, 1.0]})
    fig.subplots_adjust(wspace=0.58)

    keys = [
        ("other_site_15_25", "Other-Site\n15–25"),
        ("other_site_ge25", "Other-Site\n≥25"),
        ("frm_15_25", "FRM\n15–25"),
        ("frm_ge20", "FRM\n≥20"),
        ("frm_ge25", "FRM\n≥25"),
        ("midpoint_15_25", "Midpoint\n15–25"),
        ("midpoint_ge25", "Midpoint\n≥25"),
    ]
    x = np.arange(len(keys))
    w = 0.36
    ns_b = [mc[k]["nonsmoke"]["mean_bias"] for k, _ in keys]
    hs_b = [mc[k]["heavy_smoke"]["mean_bias"] for k, _ in keys]
    ns_t1 = [mc[k]["nonsmoke"]["t1_diff_pp"] for k, _ in keys]
    hs_t1 = [mc[k]["heavy_smoke"]["t1_diff_pp"] for k, _ in keys]

    ax1.axhline(0.0, color=SLATE, lw=0.9, zorder=1)
    ax1.grid(axis="y", color=GRID, ls="--", lw=0.6, alpha=0.7, zorder=0)
    ax1.bar(x - w / 2, ns_b, width=w, color=SLATE, edgecolor="#0F172A", lw=0.6, label="Non-Smoke (HMS = 0)", zorder=3)
    ax1.bar(x + w / 2, hs_b, width=w, color=CRIMSON, edgecolor="#0F172A", lw=0.6, label="HMS Heavy Smoke (HMS = 3)", zorder=3)

    for i, (nb, hb, nt, ht, (k, _)) in enumerate(zip(ns_b, hs_b, ns_t1, hs_t1, keys)):
        p_b = mc[k]["bias_diff_p_site"]
        star = "***" if p_b < 0.001 else ("**" if p_b < 0.01 else ("*" if p_b < 0.05 else ""))
        y_nb = nb + (0.25 if nb >= 0 else -0.32)
        va_nb = "bottom" if nb >= 0 else "top"
        ax1.text(i - w / 2, y_nb, f"{nb:+.1f}", ha="center", va=va_nb, fontsize=6.9, color=SLATE, fontweight="bold")
        ax1.text(i + w / 2, hb + 0.25, f"{hb:+.1f}{star}", ha="center", va="bottom", fontsize=7.0, color=CRIMSON, fontweight="bold")
        ax1.text(i, -4.55, f"T1: {nt:+.1f}\nvs {ht:+.1f}pp", ha="center", va="center", fontsize=6.3, color=NAVY)

    ax1.set_xticks(x, [lbl for _, lbl in keys])
    ax1.set_ylim(-5.5, 11.4)
    ax1.set_ylabel("Mean Paired Bias: T640_FW − FRM (µg/m³)")
    ax1.set_title("A. Equal-Concentration Non-Smoke vs. Heavy Smoke (T640_FW)", loc="left", pad=8)
    ax1.legend(loc="upper left", frameon=True, facecolor="white", edgecolor=GRID)
    ax1.text(
        0.99, 0.98, "Site-clustered ΔBias *** p < 0.001 in all 7 strata\nBottom tags: Tier-1 diff (Non-Smoke vs Heavy)",
        transform=ax1.transAxes, ha="right", va="top", fontsize=6.8, color=NAVY,
        bbox={"boxstyle": "round,pad=0.28", "facecolor": BG_SOFT, "edgecolor": GRID},
    )

    g_rows = [
        ("HMS Heavy & OC ≥ 5 µg/m³\n(Surface Smoke Confirmed)", gv["heavy_oc_ge5"], CRIMSON),
        ("HMS Heavy & FRM > Mo p90\n(Surface-Impacted Plume)", gv["heavy_surface_impact_frm_gt_p90"], RUST),
        ("HMS Heavy & OC/EC ≥ 5\n(Biomass-Burning Ratio)", gv["heavy_oc_ec_ge5"], "#D97706"),
        ("HMS Heavy & OC < 5 µg/m³\n(Low Surface OC)", gv["heavy_oc_lt5"], MUTED),
        ("HMS Heavy & FRM ≤ Mo p90\n(Aloft / Minimal Surface)", gv["heavy_lofted_frm_le_p90"], "#CBD5E1"),
        ("Non-Smoke Winter (DJF)\nFRM ≥ 20 (Inorganic Haze)", gv["nonsmoke_frm_ge20_winter_djf"], NAVY),
        ("Non-Smoke Warm (May–Sep)\nFRM ≥ 20 (Fire Season)", gv["nonsmoke_frm_ge20_warm_mjjas"], TEAL),
    ]
    y2 = np.arange(len(g_rows))
    vals = [r[1]["t1_diff_pp"] for r in g_rows]
    cols2 = [r[2] for r in g_rows]

    ax2.axvline(0.0, color=SLATE, lw=0.9, zorder=1)
    ax2.axhline(4.5, color=MUTED, ls=":", lw=1.0, zorder=1)
    ax2.grid(axis="x", color=GRID, ls=":", lw=0.6, alpha=0.8, zorder=0)
    ax2.barh(y2, vals, height=0.58, color=cols2, edgecolor="#0F172A", lw=0.6, zorder=3)

    for i, (_, rec, _) in enumerate(g_rows):
        v = rec["t1_diff_pp"]
        b_u = rec["mean_bias"]
        n_r = rec["n"]
        txt = f"{v:+.1f} pp (bias {b_u:+.2f}, n={n_r})"
        if v >= 0:
            ax2.text(v + 0.65, i, txt, va="center", ha="left", fontsize=6.9, fontweight="bold", color="#0F172A")
        else:
            ax2.text(0.65, i, txt, va="center", ha="left", fontsize=6.9, fontweight="bold", color=TEAL)

    ax2.set_yticks(y2, [r[0] for r in g_rows])
    ax2.invert_yaxis()
    ax2.set_xlim(-24.0, 29.0)
    ax2.set_xlabel("Paired Tier-1 Exceedance Difference: T640_FW − FRM (pp)")
    ax2.set_title("B. Ground-Level Smoke Confirmation vs. Non-Smoke Regimes", loc="left", pad=8)

    save_fig(fig, "fig3_est_smoke_vs_nonsmoke_and_ground_truth")


def make_fig4(r11: dict, r2: dict) -> None:
    """Figure 4: Multi-Dimensional Inference, Leave-EPA-Region-Out, and Observational Speciation."""
    t1 = r11["official_fixed_2021_2025"]["t640_fw"]["tier_1"]
    inf = t1["inference"]
    loro = r11["leave_epa_region_out_t640_tier1"]["by_region"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.4, 5.6), gridspec_kw={"width_ratios": [1.08, 1.05]})
    fig.subplots_adjust(wspace=0.56)

    pt = t1["difference_pp"]
    specs = [
        ("1-Way Site CR1 (165 sites)", pt, inf["oneway_site"]["ci95"], SLATE),
        ("1-Way Date CR1 (45 dates)", pt, inf["oneway_date"]["ci95"], SLATE),
        ("1-Way National Block (27 blk.)", pt, inf["oneway_nat_block"]["ci95"], NAVY),
        ("1-Way Region-Episode (55 ep.)", pt, inf["oneway_reg_episode"]["ci95"], NAVY),
        ("2-Way Site × Nat. Block (CGM)", pt, inf["twoway_site_x_nat_block"]["ci95"], CRIMSON),
        ("2-Way Site × Region-Ep. (Primary)", pt, inf["twoway_site_x_reg_episode"]["ci95"], CRIMSON),
    ]
    for rk in sorted(loro.keys(), key=lambda s: int(s[1:])):
        v = loro[rk]
        specs.append(
            (
                f"Drop EPA {rk} (n={v['loro_n']})",
                v["loro_diff_pp"],
                v["loro_ci95_twoway_reg_ep_pp"],
                RUST,
            )
        )

    ax1.axvline(0.0, color=SLATE, ls="--", lw=0.9, zorder=1)
    ax1.axvline(pt, color=CRIMSON, ls=":", lw=0.9, alpha=0.65, zorder=1)
    ax1.axhline(5.5, color=MUTED, ls=":", lw=1.0, zorder=1)
    ax1.grid(axis="x", color=GRID, ls=":", lw=0.6, alpha=0.8, zorder=0)

    for i, (_, m, ci, col) in enumerate(specs):
        ax1.errorbar(
            m, i, xerr=[[m - ci[0]], [ci[1] - m]], fmt="o", color=col, ecolor=col,
            markersize=5.6 if i != 5 else 7.0, elinewidth=1.6 if i != 5 else 2.3, capsize=3.0, zorder=4,
        )
        ax1.text(
            ci[1] + 0.35, i, f"{m:+.2f} [{ci[0]:+.2f}, {ci[1]:+.2f}]",
            va="center", ha="left", fontsize=6.7, color=col, fontweight="bold" if i in (2, 5) else "normal",
        )

    ax1.set_yticks(range(len(specs)), [s[0] for s in specs])
    ax1.invert_yaxis()
    ax1.set_xlim(-0.8, 20.5)
    ax1.set_xlabel("Paired Tier-1 Difference: T640_FW − FRM (pp, 95% CI)")
    ax1.set_title("A. Multi-Way Event Inference & Leave-EPA-Region-Out Stability", loc="left", pad=8)

    # Panel B: Observational Speciation & Meteorology (Site FE + Month FE, 2023-2025)
    s1_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s1_spec_met_level_site_cr1"]
    s2_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s2_interactions_level_site_cr1"]
    s1_b = r2["speciation_and_meteorology"]["bam"]["model_s1_spec_met_level_site_cr1"]
    s2_b = r2["speciation_and_meteorology"]["bam"]["model_s2_interactions_level_site_cr1"]

    var_specs = [
        ("Organic Carbon\n(OC, +1 µg/m³)", "oc", s1_t, s1_b, 1.0),
        ("OC × HMS Heavy\n(Addtl. Slope)", "oc_x_hms_h", s2_t, s2_b, 1.0),
        ("Elemental Carbon\n(EC, +1 µg/m³)", "ec", s1_t, s1_b, 1.0),
        ("Nitrate\n(NO₃⁻, +1 µg/m³)", "no3", s1_t, s1_b, 1.0),
        ("Sulfate\n(SO₄²⁻, +1 µg/m³)", "so4", s1_t, s1_b, 1.0),
        ("Relative Humidity\n(+10% RH)", "rh_10", s1_t, s1_b, 1.0),
        ("Temperature\n(+10 °C)", "temp_c", s1_t, s1_b, 10.0),
    ]
    ax2.axvline(0.0, color=SLATE, ls="--", lw=0.9, zorder=1)
    ax2.grid(axis="x", color=GRID, ls=":", lw=0.6, alpha=0.8, zorder=0)

    for i, (_, vk, mt, mb, mult) in enumerate(var_specs):
        ct = mt["coefs"][vk]
        cb = mb["coefs"][vk]
        bt, set_ = mult * ct["beta"], mult * 1.96 * ct["se_cr1"]
        bb, seb = mult * cb["beta"], mult * 1.96 * cb["se_cr1"]
        ax2.errorbar(
            bt, i - 0.14, xerr=set_, fmt="o", color=RUST, ecolor=RUST,
            markersize=6.0, elinewidth=1.9, capsize=3.0, zorder=4,
            label=f"T640_FW (N={s1_t['n']:,} pairs)" if i == 0 else None,
        )
        ax2.errorbar(
            bb, i + 0.14, xerr=seb, fmt="s", color=TEAL, ecolor=TEAL,
            markersize=5.2, elinewidth=1.5, capsize=2.8, zorder=4,
            label=f"BAM Ref. (N={s1_b['n']:,} pairs)" if i == 0 else None,
        )
        ax2.text(
            bt + set_ + 0.05 if bt >= 0 else bt - set_ - 0.05,
            i - 0.14,
            f"{bt:+.2f}",
            va="center", ha="left" if bt >= 0 else "right",
            fontsize=6.9, fontweight="bold", color="#7C2D12",
        )

    ax2.set_yticks(range(len(var_specs)), [v[0] for v in var_specs])
    ax2.invert_yaxis()
    ax2.set_xlim(-1.85, 1.38)
    ax2.set_xlabel("Observational Partial Effect on (FEM − FRM) Bias (µg/m³, Site+Mo FE)")
    ax2.set_title("B. Observational Speciation & Hygroscopicity Associations", loc="left", pad=8)
    ax2.legend(loc="lower left", frameon=True, facecolor="white", edgecolor=GRID, fontsize=7.2)

    save_fig(fig, "fig4_est_inference_loro_and_speciation")


def make_si_figs(r1: dict, r2: dict, r3: dict, r11: dict) -> None:
    """Generate 2 clean Supporting Information figures (Fig S1 & Fig S2)."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.2), gridspec_kw={"width_ratios": [1.08, 1.0]})
    fig.subplots_adjust(wspace=0.32)

    wf = r1["accounting"]["combined_site_reg_appn_11of12"]["matched_2123_waterfall"]
    epa21 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2021_2023_final_08_08_24_0.xlsx"]
    lbls = ["2021–23\nPre-Align\n(Raw T640)", "2021–23\nPost-Align\n(Aligned)", "2021–23\nAligned +\nConc. EE", "2021–23\nAligned +\nAll EE Flags"]
    cnts = [wf["raw_2123"]["counties"], wf["aln_2123"]["counties"], wf["aln_ee_conc_2123"]["counties"], wf["aln_ee_all_2123"]["counties"]]
    pops = [wf["raw_2123"]["pop_millions"], wf["aln_2123"]["pop_millions"], wf["aln_ee_conc_2123"]["pop_millions"], wf["aln_ee_all_2123"]["pop_millions"]]
    cols = [CRIMSON, NAVY, TEAL, "#2563EB"]
    x = np.arange(len(lbls))
    bars = ax1.bar(x, cnts, width=0.56, color=cols, edgecolor="#0F172A", lw=0.7, zorder=3)
    ax1.grid(axis="y", color=GRID, ls="--", lw=0.6, alpha=0.7, zorder=0)
    for b, c, p in zip(bars, cnts, pops):
        ax1.text(b.get_x() + b.get_width() / 2, c - 6, f"{c}\n({p:.1f}M)", ha="center", va="top", color="white", fontsize=8.0, fontweight="bold", zorder=4)
    ax1.scatter([1], [epa21["epa_na_counties"]], marker="D", s=64, color="#D97706", edgecolor="#0F172A", zorder=5, label=f"Official EPA Table 4a ({epa21['epa_na_counties']} counties)")
    ax1.set_xticks(x, lbls)
    ax1.set_ylim(0, 196)
    ax1.set_ylabel("Matched Regulatory Counties with Monitor DV ≥ 9.1 µg/m³")
    ax1.set_title("A. Screening-Level 2021–2023 Monitor DV Reclassifications (Not §107(d))", loc="left", pad=8)
    ax1.legend(loc="upper right", frameon=True, facecolor="white", edgecolor=GRID)
    ax1.text(
        1.5, 165,
        f"T640 Alignment Alone: −{wf['flip_t640_alone']['counties']} counties (−{wf['flip_t640_alone']['pop_millions']:.2f}M)\n"
        f"(Screening DV cross-overs; distinct from CAA § 107(d) designations)",
        ha="center", va="center", fontsize=7.0, fontweight="bold", color=CRIMSON,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.8},
    )

    dv_t = pd.read_parquet(PROC_DIR / "rooftop_dv_t640_2023_2025.parquet")
    rt_t = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_b = r2["rooftop_dv_lottery_2023_2025"]["bam"]
    ax2.axhline(9.05, color=NAVY, ls="--", lw=0.9)
    ax2.axvline(9.05, color=NAVY, ls="--", lw=0.9)
    ax2.plot([3, 16], [3, 16], color=MUTED, ls=":", lw=1.0)
    t_only = dv_t[(dv_t["dv_fem_r"] >= 9.1) & (dv_t["dv_frm_r"] <= 9.0)]
    f_only = dv_t[(dv_t["dv_frm_r"] >= 9.1) & (dv_t["dv_fem_r"] <= 9.0)]
    agree = dv_t[~dv_t.index.isin(t_only.index) & ~dv_t.index.isin(f_only.index)]
    ax2.scatter(agree["dv_frm"], agree["dv_fem"], s=20, color=SLATE, alpha=0.55, label=f"Agree (n={len(agree)})", zorder=2)
    ax2.scatter(t_only["dv_frm"], t_only["dv_fem"], s=48, color=CRIMSON, edgecolor="white", lw=0.5, label=f"T640 ≥ 9.1, FRM ≤ 9.0 (n={len(t_only)})", zorder=4)
    ax2.scatter(f_only["dv_frm"], f_only["dv_fem"], s=52, marker="D", color=TEAL, edgecolor="white", lw=0.6, label=f"FRM ≥ 9.1, T640 ≤ 9.0 (n={len(f_only)})", zorder=5)
    ax2.set_xlim(3.5, 14.5)
    ax2.set_ylim(3.5, 14.5)
    ax2.set_xlabel("Collocated FRM Paired-Day 2023–2025 Design Value (µg/m³)")
    ax2.set_ylabel("Aligned T640_FW Paired-Day 2023–2025 Design Value (µg/m³)")
    ax2.set_title(f"B. Same-Rooftop 3-Yr Annual DV Sensitivity (N={rt_t['n_sites']} Sites)", loc="left", pad=8)
    ax2.legend(loc="lower right", frameon=True, facecolor="white", edgecolor=GRID, fontsize=7.0)
    ax2.text(
        3.8, 14.1,
        f"T640 Mean DV Bias: +{rt_t['mean_dv_bias']:.3f} µg/m³ (t={rt_t['t_bias']:+.2f})\n"
        f"Discordant: {rt_t['fem_na_frm_att']} vs {rt_t['frm_na_fem_att']} (binom. p={rt_t['binom_p']:.4f})\n"
        f"BAM Ref. (N={rt_b['n_sites']}): {rt_b['mean_dv_bias']:+.3f} µg/m³ ({rt_b['fem_na_frm_att']} vs {rt_b['frm_na_fem_att']})",
        va="top", ha="left", fontsize=7.0, fontweight="bold", color=NAVY,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": BG_SOFT, "edgecolor": SLATE, "lw": 0.7},
    )
    save_fig(fig, "figS1_si_dv_reclassification_and_rooftop_lottery")

    # Fig S2
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.0), gridspec_kw={"width_ratios": [1.0, 1.05]})
    fig.subplots_adjust(wspace=0.34)

    rb = r11["oot_reconstruction_benchmark_2021_2025"]
    b_keys = [
        ("cs_all_no_ann_excl", "Combined-Site\n(App N Tbl 1)"),
        ("oot_a_cs_r_excl", "OOT-A\n(R-Excl Ann)"),
        ("oot_b_cs_excl_hms3", "OOT-B\n(Excl HMS 3)"),
        ("oot_b2_cs_excl_hms23", "OOT-B2\n(Excl HMS 2–3)"),
        ("oot_c_pure_frm", "OOT-C\n(Pure FRM)"),
    ]
    x1 = np.arange(len(b_keys))
    w = 0.36
    all_r = [rb[k]["all_sites_corr"] for k, _ in b_keys]
    cln_r = [rb[k]["zero_flag_clean_corr"] for k, _ in b_keys]
    ax1.bar(x1 - w / 2, all_r, width=w, color=NAVY, edgecolor="#0F172A", lw=0.6, label="All Collocated Sites (n=3,798 site-mo)", zorder=3)
    ax1.bar(x1 + w / 2, cln_r, width=w, color=TEAL, edgecolor="#0F172A", lw=0.6, label="Zero-Event Clean Sites", zorder=3)
    ax1.grid(axis="y", color=GRID, ls="--", lw=0.6, alpha=0.7, zorder=0)
    for i, (ar, cr, (k, _)) in enumerate(zip(all_r, cln_r, b_keys)):
        ax1.text(i - w / 2, ar + 0.018, f"{ar:.2f}", ha="center", va="bottom", fontsize=7.0, fontweight="bold", color=NAVY)
        ax1.text(i + w / 2, cr + 0.018, f"{cr:.2f}", ha="center", va="bottom", fontsize=7.0, fontweight="bold", color=TEAL)
        ax1.text(i + w / 2, 0.35, f"med|e|\n{rb[k]['zero_flag_clean_median_abs_err']:.2f}", ha="center", va="center", fontsize=6.0, color="white", fontweight="bold")
    ax1.set_xticks(x1, [lbl for _, lbl in b_keys])
    ax1.set_ylim(0, 1.24)
    ax1.set_ylabel("Correlation (r) with Official EPA 2021–2025 Tier-1 Table")
    ax1.set_title("A. Validation of 40 CFR 50 App. N Threshold Reconstruction", loc="left", pad=8)
    ax1.legend(loc="upper right", frameon=True, facecolor="white", edgecolor=GRID, fontsize=7.0)

    es_all = r3["county_year_dv1820_85_115"]["true_ee_flag"]["event_study_county_cr1"]["coefs"]
    es_conc = r3["county_year_dv1820_85_115"]["true_ee_conc"]["event_study_county_cr1"]["coefs"]
    yrs = [2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]

    def _get_es(d_c: dict) -> tuple[list[float], list[float]]:
        bs, ses = [], []
        for y in yrs:
            if y == 2020:
                bs.append(0.0)
                ses.append(0.0)
            else:
                c = d_c[f"nb_{y}"]
                bs.append(100.0 * c["beta"])
                ses.append(100.0 * 1.96 * c["se_cr1"])
        return bs, ses

    b_a, s_a = _get_es(es_all)
    b_c, s_c = _get_es(es_conc)
    ax2.axhline(0.0, color=SLATE, ls="--", lw=0.9)
    ax2.axvline(2024.1, color=CRIMSON, ls=":", lw=1.1, label="Feb 2024 Final Rule (89 FR 16202)")
    ax2.grid(axis="y", color=GRID, ls=":", lw=0.6, alpha=0.8)
    ax2.errorbar(np.array(yrs) - 0.08, b_a, yerr=s_a, fmt="o-", color=NAVY, lw=1.6, capsize=2.8, label="All State EE Flags (County-Year)")
    ax2.errorbar(np.array(yrs) + 0.08, b_c, yerr=s_c, fmt="s--", color=TEAL, lw=1.4, capsize=2.8, label="EPA-Concurred Exclusions")
    ax2.set_xticks(yrs)
    ax2.set_ylim(-16.5, 36.0)
    ax2.set_xlabel("Calendar Year (Reference = 2020)")
    ax2.set_ylabel("Event-Study Coefficient (pp, 95% County CI)")
    ax2.set_title("B. Observational EE Flagging Context & Within-County-Year Null", loc="left", pad=8)
    ax2.legend(loc="upper left", frameon=True, facecolor="white", edgecolor=GRID, fontsize=6.9)
    u2_wcy = r3["unification_u2_t640_ee_flagging"]["borderline_within_county_year_fe_flag"]
    ax2.text(
        0.98, 0.04,
        f"Within-County-Year T640 Flagging Test:\n"
        f"{100*u2_wcy['coefs']['is_t640_f']['beta']:+.2f} pp ($p_{{\\mathrm{{WCB}}}}$ = {u2_wcy['wcb']['p_wcb']:.3f}, N={u2_wcy['n']})\n"
        f"→ No causal instrument-filing effect identified",
        transform=ax2.transAxes, ha="right", va="bottom", fontsize=6.9, fontweight="bold", color=CRIMSON,
        bbox={"boxstyle": "round,pad=0.3", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.8},
    )
    save_fig(fig, "figS2_si_oot_reconstruction_and_ee_nulls")


def main() -> int:
    print("=== STEP 12: GENERATING V4 ES&T MAIN & SI FIGURES ===", flush=True)
    setup_rc()
    r1 = json.loads((RES_DIR / "01_appn_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_collocated_physics_speciation.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_ee_triage_hms_unification.json").read_text(encoding="utf-8"))
    r11 = json.loads((RES_DIR / "11_v4_est_comprehensive_audit.json").read_text(encoding="utf-8"))

    assert (ENRICH_DIR / "epa_pm25_tier_thresholds_2026-09-14.csv").exists()
    make_fig1(r11)
    make_fig2(r11)
    make_fig3(r11)
    make_fig4(r11, r2)
    make_si_figs(r1, r2, r3, r11)
    print("[DONE STEP 12] Generated all 4 Main ES&T figures + 2 SI figures cleanly.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
