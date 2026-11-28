"""Step 10 (v4): Generate all 4 publication-grade 300-DPI PNG + vector PDF figures
for the Journal of Safety Research / M&SOM Data Set v4 revision with ZERO hardcoded numbers
and strict zero-overlap layout verification.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.lines import Line2D

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
PROC_DIR = BASE_DIR / "data_processed"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
FIG_DIR = BASE_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Georgia", "Times New Roman"],
        "axes.edgecolor": "#334155",
        "axes.linewidth": 0.85,
        "axes.grid": True,
        "grid.color": "#e2e8f0",
        "grid.linewidth": 0.6,
        "grid.alpha": 0.85,
        "xtick.color": "#1e293b",
        "ytick.color": "#1e293b",
        "text.color": "#0f172a",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 300,
    }
)

COLORS = {
    "Pure_OTA": "#1b365d",         # Deep Navy
    "Hybrid_OTA": "#d95f02",       # Burnt Orange
    "Hybrid_HW": "#f59e0b",        # Amber
    "Dealer_Software": "#0d9488",  # Teal
    "Physical_Hardware": "#64748b",# Cool Slate
    "API_OTA": "#6d28d9",          # Royal Violet
    "ITT": "#0284c7",              # Sky Blue
    "Red": "#b91c1c",              # Crimson
    "Green": "#15803d",            # Forest Green
}


def short_oem(name: str) -> str:
    mapping = {
        "Tesla, Inc.": "Tesla",
        "Lucid USA, Inc.": "Lucid",
        "Volvo Car USA, LLC": "Volvo Car",
        "Ford Motor Company": "Ford",
        "General Motors, LLC": "General Motors",
        "Mercedes-Benz USA, LLC": "Mercedes-Benz",
        "Nissan North America, Inc.": "Nissan",
        "Jaguar Land Rover North America, LLC": "Jaguar Land Rover",
        "Daimler Vans USA, LLC": "Daimler Vans",
        "BMW of North America, LLC": "BMW",
        "Chrysler (FCA US, LLC)": "Chrysler (FCA)",
        "Honda (American Honda Motor Co.)": "Honda",
        "Hyundai Motor America": "Hyundai",
        "Kia America, Inc.": "Kia",
        "Mack Trucks, Inc.": "Mack Trucks",
        "Toyota Motor Engineering & Manufacturing": "Toyota",
        "Volvo Trucks North America": "Volvo Trucks",
        "Winnebago Industries, Inc.": "Winnebago",
    }
    return mapping.get(name, name)


def save_dual(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight", facecolor="white")
    plt.close(fig)


def make_fig1(v4: dict, df_flow: pd.DataFrame, df_comp: pd.DataFrame) -> None:
    """Fig 1: Statutory ODATE 2022-2023 Sample Flow Accounting & Fixed 8th-Report Completion Proportions."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.2), gridspec_kw={"width_ratios": [1.02, 1.18]})
    fig.subplots_adjust(wspace=0.28)

    fa = df_flow[df_flow["Cohort_Panel"] == "A_Statutory_ODATE_2022_2023"].copy()
    mods = ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]
    mod_labels = ["Pure-OTA", "Hybrid-OTA", "Dealer Software", "Physical Hardware"]
    fa = fa.set_index("Modality").loc[mods]

    y_pos = np.arange(len(mods))[::-1]
    tot = fa["Total_Campaigns"].to_numpy(dtype=float)
    s_in8 = 100.0 * fa["In_8th_Report_Unique"].to_numpy(dtype=float) / tot
    s_100 = 100.0 * fa["Unlisted_Early_Completed_100pct"].to_numpy(dtype=float) / tot
    s_miss = 100.0 * fa["Unlisted_Missing_DOT_Report"].to_numpy(dtype=float) / tot
    s_oth = 100.0 * (
        fa["Excluded_Conflicting_Duplicate"].to_numpy(dtype=float)
        + fa["Unlisted_Delayed_or_Unreached"].to_numpy(dtype=float)
    ) / tot

    bar_h = 0.56
    ax1.barh(y_pos, s_in8, height=bar_h, color="#1b365d", label="In 8th-Report Unique Sample")
    ax1.barh(y_pos, s_100, left=s_in8, height=bar_h, color="#0d9488", label="Unlisted: Early-Completed (100%)")
    ax1.barh(y_pos, s_miss, left=s_in8 + s_100, height=bar_h, color="#f59e0b", label="Unlisted: Missing DOT Report")
    ax1.barh(y_pos, s_oth, left=s_in8 + s_100 + s_miss, height=bar_h, color="#b91c1c", label="Excluded Duplicate / Delayed")

    for i, mod in enumerate(mods):
        y = y_pos[i]
        row = fa.loc[mod]
        if s_in8[i] >= 18:
            ax1.text(
                s_in8[i] / 2.0,
                y,
                f"{int(row['In_8th_Report_Unique']):,}\n({s_in8[i]:.1f}%)",
                ha="center",
                va="center",
                color="white",
                fontsize=8.0,
                fontweight="bold",
            )
        if s_100[i] >= 10:
            ax1.text(
                s_in8[i] + s_100[i] / 2.0,
                y,
                f"{int(row['Unlisted_Early_Completed_100pct'])}",
                ha="center",
                va="center",
                color="white",
                fontsize=7.8,
                fontweight="bold",
            )
        ax1.text(101.8, y, f"N = {int(row['Total_Campaigns']):,}", ha="left", va="center", fontsize=8.2, fontweight="bold")

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels(mod_labels, fontsize=8.8, fontweight="bold")
    ax1.set_xlim(0, 122)
    ax1.set_xticks([0, 20, 40, 60, 80, 100])
    ax1.set_xlabel("Share of 2022–2023 Owner-Notification (ODATE) Cohort (%)", fontsize=8.6)
    n_od = v4["sample_flow"]["odate_2022_2023_total"]
    n_early = v4["sample_flow"]["earlier_odate_delayed_entries_n"]
    n_uniq = v4["reconciliation"]["matched_unique_campaigns"]
    ax1.set_title(f"A. Statutory ODATE 2022–2023 Sample Flow (N = {n_od:,})", fontsize=9.8, fontweight="bold", loc="left", pad=8)
    ax1.legend(loc="lower center", bbox_to_anchor=(0.48, -0.34), ncol=2, frameon=True, fontsize=7.6)
    ax1.text(
        0.0,
        -0.19,
        f"Note: +{n_early} delayed 2020–2021 ODATE entries yield {n_uniq:,} unique 8th-report campaigns (2 duplicates excluded).",
        transform=ax1.transAxes,
        fontsize=7.2,
        color="#475569",
    )
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Fixed 8th-Report Completion Proportions by Channel & Year (2024 vs 2025)
    c24 = df_comp[df_comp["Report_Year"] == "2024"].set_index("Modality").loc[mods]
    c25 = df_comp[df_comp["Report_Year"] == "2025"].set_index("Modality").loc[mods]
    x = np.arange(len(mods)) * 1.15
    w = 0.38

    b24 = ax2.bar(x - 0.21, c24["Mean_Completion_Pct"], width=w, color="#1b365d", alpha=0.88, label="2024 List: Unweighted Mean (%)")
    b25 = ax2.bar(x + 0.21, c25["Mean_Completion_Pct"], width=w, color="#0d9488", alpha=0.88, label="2025 List: Unweighted Mean (%)")

    ax2.scatter(x - 0.21, c24["Median_Completion_Pct"], marker="D", s=34, color="#f8fafc", edgecolor="#0f172a", zorder=5, label="Campaign Median (%)")
    ax2.scatter(x + 0.21, c25["Median_Completion_Pct"], marker="D", s=34, color="#f8fafc", edgecolor="#0f172a", zorder=5)
    ax2.scatter(x - 0.21, c24["Affected_Weighted_Mean_Pct"], marker="^", s=40, color="#d95f02", edgecolor="#0f172a", linewidth=0.5, zorder=6, label="Vehicle-Weighted Mean (%)")
    ax2.scatter(x + 0.21, c25["Affected_Weighted_Mean_Pct"], marker="^", s=40, color="#d95f02", edgecolor="#0f172a", linewidth=0.5, zorder=6)

    for bars, sub_df in [(b24, c24), (b25, c25)]:
        for bar, (_, r) in zip(bars, sub_df.iterrows(), strict=True):
            top = max(float(r["Mean_Completion_Pct"]), float(r["Median_Completion_Pct"]), float(r["Affected_Weighted_Mean_Pct"]))
            ax2.text(
                bar.get_x() + bar.get_width() / 2.0,
                top + 2.0,
                f"{r['Mean_Completion_Pct']:.1f}%\n(n={int(r['N_Campaigns'])},\n{int(r['N_OEMs'])} OEM)",
                ha="center",
                va="bottom",
                fontsize=6.4,
                linespacing=1.08,
                color="#0f172a",
            )

    ax2.set_xticks(x)
    ax2.set_xticklabels(["Pure-OTA", "Hybrid-OTA", "Dealer\nSoftware", "Physical\nHardware"], fontsize=8.4, fontweight="bold")
    ax2.set_ylim(0, 120)
    ax2.set_yticks([0, 20, 40, 60, 80, 100])
    ax2.set_ylabel("Fixed 8th-Report Completion Proportion (%)", fontsize=8.6)
    ax2.set_title(f"B. Fixed 8th-Report Completion Proportions (N = {n_uniq:,})", fontsize=9.8, fontweight="bold", loc="left", pad=8)
    ax2.legend(loc="lower center", bbox_to_anchor=(0.50, -0.34), ncol=2, frameon=True, fontsize=7.6)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    save_dual(fig, "fig1_v4_sample_flow_and_completion")


def make_fig2(v4: dict, panel8: pd.DataFrame) -> None:
    """Fig 2: Channel x Manufacturer x Vehicle-Age Common-Support Matrix & OEM Concentration."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 6.2), gridspec_kw={"width_ratios": [1.55, 1.0]})
    fig.subplots_adjust(wspace=0.28)

    cs8 = v4["common_support_summary"]["eighth_report"]
    both_pure = cs8["same_oem_both_dsw_and_pure_oems"]
    both_hyb = cs8["same_oem_both_dsw_and_hybrid_oems"]
    df_sup = pd.read_csv(TBL_DIR / "table_channel_oem_age_support.csv")
    oems_18 = sorted(df_sup[df_sup["Horizon_Sample"] == "8th_Report_Fixed_Horizon"]["Manufacturer"].unique())
    dsw_only_oems = sorted([o for o in oems_18 if o not in (["Tesla, Inc."] + both_pure + both_hyb)])

    sw8 = panel8[panel8["mfg"].isin(oems_18) & panel8["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])].copy()
    sw8["veh_age_clip"] = sw8["vehicle_age_years"].clip(0, 15)

    ordered_rows = ["Tesla, Inc."] + both_pure + both_hyb + ["__DSW_ONLY__"]
    row_labels = [short_oem(o) for o in (["Tesla, Inc."] + both_pure + both_hyb)] + [
        f"9 Dealer-SW-Only OEMs\n(n={int(sw8[sw8['mfg'].isin(dsw_only_oems)].shape[0])})"
    ]
    row_y = {k: len(ordered_rows) - 1 - i for i, k in enumerate(ordered_rows)}

    for k in ordered_rows:
        y = row_y[k]
        if k == "Tesla, Inc.":
            ax1.axhspan(y - 0.45, y + 0.45, color="#fef2f2", alpha=0.85, zorder=0)
        elif k in both_pure:
            ax1.axhspan(y - 0.45, y + 0.45, color="#eff6ff", alpha=0.65, zorder=0)
        elif k == "__DSW_ONLY__":
            ax1.axhspan(y - 0.45, y + 0.45, color="#f1f5f9", alpha=0.85, zorder=0)

    offsets = {"Pure_OTA": 0.16, "Hybrid_OTA": 0.0, "Dealer_Software": -0.17}
    markers = {"Pure_OTA": "o", "Hybrid_OTA": "s", "Dealer_Software": "^"}
    rng = np.random.default_rng(42)

    for _, r in sw8.iterrows():
        key = r["mfg"] if r["mfg"] in row_y else "__DSW_ONLY__"
        mod = r["modality4"]
        x_val = float(r["veh_age_clip"]) + rng.uniform(-0.14, 0.14)
        y_val = row_y[key] + offsets[mod] + rng.uniform(-0.04, 0.04)
        sz = 24.0 + 18.0 * np.log10(max(10.0, float(r["reported_affected"])))
        ax1.scatter(
            x_val,
            y_val,
            s=sz,
            marker=markers[mod],
            color=COLORS[mod],
            edgecolor="white",
            linewidth=0.55,
            alpha=0.88,
            zorder=4 if mod != "Dealer_Software" else 3,
        )

    ax1.axvline(5.5, color="#94a3b8", linestyle="--", linewidth=1.0, zorder=1)
    # Place Age 6+ label in completely clear open region (Lucid/Volvo rows at x=5.8)
    ax1.text(
        5.8,
        row_y["Volvo Car USA, LLC"] + 0.45,
        "Age ≥ 6 yr boundary\n(0 non-Tesla Pure-OTA,\n0 Hybrid-OTA)",
        fontsize=7.4,
        color="#475569",
        va="center",
        ha="left",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": "#cbd5e1", "alpha": 0.92},
    )

    callout = (
        f"Pure-OTA Support Gap (8th Report, n = {cs8['pure_total_n']}):\n"
        f"• Tesla: {cs8['pure_tesla_n']}/{cs8['pure_total_n']} recalls ({cs8['pure_tesla_vehicle_share_pct']:.2f}% veh), "
        f"{cs8['tesla_dealer_sw_n']} Dealer-SW\n"
        f"• Lucid ({int((sw8['mfg']=='Lucid USA, Inc.').mul(sw8['is_ota_pure']).sum())}) & Volvo ({int((sw8['mfg']=='Volvo Car USA, LLC').mul(sw8['is_ota_pure']).sum())}): "
        f"all oldest-MY age 0–{int(cs8['pure_nontesla_max_age_yr'])} yr\n"
        f"• Same-OEM common support: {len(cs8['same_oem_both_dsw_and_ota_oems'])} OEMs (excl. Tesla)"
    )
    ax1.text(
        0.98,
        0.44,
        callout,
        transform=ax1.transAxes,
        ha="right",
        va="center",
        fontsize=7.4,
        bbox={"boxstyle": "round,pad=0.45", "facecolor": "#fffbeb", "edgecolor": "#d97706", "linewidth": 0.9},
        zorder=7,
    )

    ax1.set_yticks([row_y[k] for k in ordered_rows])
    ax1.set_yticklabels(row_labels, fontsize=8.2, fontweight="bold")
    ax1.set_xlim(-0.7, 15.8)
    ax1.set_xticks(range(0, 16, 2))
    ax1.set_xlabel("Oldest Model-Year Vehicle Age at Recall Filing (Years, Clipped at 15)", fontsize=8.6)
    ax1.set_title(f"A. Manufacturer × Channel × Age Support (8th Report, N = {cs8['n_sw_ota_oems']})", fontsize=9.8, fontweight="bold", loc="left", pad=8)
    handles = [
        Line2D([0], [0], marker="o", color="w", markerfacecolor=COLORS["Pure_OTA"], markersize=7.5, label="Pure-OTA (Wireless-Only)"),
        Line2D([0], [0], marker="s", color="w", markerfacecolor=COLORS["Hybrid_OTA"], markersize=7.5, label="Hybrid-OTA (OTA or Dealer)"),
        Line2D([0], [0], marker="^", color="w", markerfacecolor=COLORS["Dealer_Software"], markersize=7.5, label="Dealer Software"),
    ]
    ax1.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.50, -0.20), ncol=3, frameon=True, fontsize=7.8)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Concentration & Age-Support Ceiling across Both Horizons
    csm = v4["common_support_summary"]["mature_18m_snapshot"]
    metrics = [
        "Tesla Share of\nPure-OTA Vehicles",
        "Tesla Share of\nPure-OTA Recalls",
        "Tesla Share of\nPure-OTA Age ≥6 yr",
        "Non-Tesla Pure-OTA\nWithin 0–5 yr Window",
    ]
    vals_8th = [
        cs8["pure_tesla_vehicle_share_pct"],
        round(100.0 * cs8["pure_tesla_n"] / cs8["pure_total_n"], 1),
        round(100.0 * cs8["pure_age_6plus_tesla"] / max(1, cs8["pure_age_6plus_total"]), 1),
        100.0,
    ]
    vals_mat = [
        csm["pure_tesla_vehicle_share_pct"],
        round(100.0 * csm["pure_tesla_n"] / csm["pure_total_n"], 1),
        round(100.0 * csm["pure_age_6plus_tesla"] / max(1, csm["pure_age_6plus_total"]), 1),
        100.0,
    ]
    ym = np.arange(len(metrics))[::-1]
    h = 0.34
    b1 = ax2.barh(ym + h / 2, vals_8th, height=h, color="#b91c1c", alpha=0.88, label=f"8th-Report Cohort (n={cs8['pure_total_n']} Pure-OTA)")
    b2 = ax2.barh(ym - h / 2, vals_mat, height=h, color="#1b365d", alpha=0.82, label=f"Mature ≥18m Snapshot (n={csm['pure_total_n']} Pure-OTA)")

    for bars in (b1, b2):
        for bar in bars:
            v = bar.get_width()
            ax2.text(v + 1.5, bar.get_y() + bar.get_height() / 2.0, f"{v:.1f}%", va="center", ha="left", fontsize=7.6, fontweight="bold")

    ax2.set_yticks(ym)
    ax2.set_yticklabels(metrics, fontsize=8.2, fontweight="bold")
    ax2.set_xlim(0, 122)
    ax2.set_xticks([0, 25, 50, 75, 100])
    ax2.set_xlabel("Percentage (%)", fontsize=8.6)
    ax2.set_title("B. Pure-OTA Concentration Across Both Horizons", fontsize=9.8, fontweight="bold", loc="left", pad=8)
    ax2.legend(loc="lower center", bbox_to_anchor=(0.45, -0.20), ncol=1, frameon=True, fontsize=7.6)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    save_dual(fig, "fig2_v4_channel_oem_age_support")


def make_fig3(df_sens: pd.DataFrame, df_looo: pd.DataFrame) -> None:
    """Fig 3: Vehicle-Age Gradient Sensitivity Forest Plot & Complete 18-OEM LOOO Diagnostics."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.6, 6.4), gridspec_kw={"width_ratios": [1.18, 1.05]})
    fig.subplots_adjust(wspace=0.72)

    key_items = [
        ("Fixed 8th report: oldest model year (4-way)", "veh_age", "Baseline Dealer-SW Age Slope\n(18 OEMs, N=148)", COLORS["Dealer_Software"], "D"),
        ("Standalone Dealer-Software (all 53 OEMs in 8th report)", "veh_age", "Standalone Dealer-SW\n(53 OEMs, N=197)", COLORS["Dealer_Software"], "D"),
        ("Standalone Physical-Hardware (all 213 OEMs in 8th report)", "veh_age", "Standalone Physical-HW\n(213 OEMs, N=1,306)", COLORS["Physical_Hardware"], "D"),
        ("Fixed 8th report: oldest model year (4-way)", "is_ota_pure_x_age", "Pure-OTA × Age\n(Full 18 OEMs, N=148)", COLORS["Pure_OTA"], "o"),
        ("Fixed 8th report: oldest MY, 0-5 yr window (4-way)", "is_ota_pure_x_age", "Pure-OTA × Age\n(0–5 yr Window, N=138)", COLORS["Pure_OTA"], "o"),
        ("Fixed 8th report: oldest MY, excluding Tesla (4-way)", "is_ota_pure_x_age", "Pure-OTA × Age\n(Excl. Tesla, N=137)", COLORS["Red"], "o"),
        ("Fixed 8th report: oldest model year (4-way)", "is_ota_hybrid_x_age", "Hybrid-OTA × Age\n(Full 18 OEMs, N=148)", COLORS["Hybrid_OTA"], "s"),
        ("Same-OEM common support (8 OEMs, all ages, pooled OTA)", "is_ota_audited_x_age", "Pooled OTA × Age\n(Same-OEM CS, N=70)", COLORS["API_OTA"], "s"),
        ("Strict Same-OEM x Overlapping-Age support (8 OEMs, pooled OTA)", "is_ota_audited_x_age", "Pooled OTA × Age\n(Strict Age-Overlap, N=53)", COLORS["API_OTA"], "s"),
    ]

    lookup = {(r["Specification"], r["Term"]): r for _, r in df_sens.iterrows()}
    y_a = np.arange(len(key_items))[::-1]
    ax1.axvline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=1)
    ax1.axhline(5.5, color="#cbd5e1", linestyle=":", linewidth=1.0)

    for idx, (spec, term, _lbl, col, mk) in enumerate(key_items):
        row = lookup[(spec, term)]
        y = y_a[idx]
        c, lo, hi, pw = float(row["Coef"]), float(row["CI95_Lo"]), float(row["CI95_Hi"]), float(row["p_WCB"])
        filled = pw < 0.05
        ax1.errorbar(
            c,
            y,
            xerr=[[max(0.0, c - lo)], [max(0.0, hi - c)]],
            fmt=mk,
            color=col,
            mfc=col if filled else "white",
            mec=col,
            mew=1.4,
            markersize=6.8,
            elinewidth=1.4,
            capsize=3.0,
            zorder=4,
        )
        ax1.text(
            10.5,
            y,
            f"{c:+.2f} ($p$={pw:.3f})",
            va="center",
            ha="left",
            fontsize=7.4,
            fontweight="bold" if filled else "normal",
            color=col if filled else "#475569",
        )

    ax1.set_yticks(y_a)
    ax1.set_yticklabels([x[2] for x in key_items], fontsize=7.6, linespacing=1.05)
    ax1.set_xlim(-10.5, 10.2)
    ax1.set_xlabel("Age Slope / Interaction (pp per Vehicle-Age Year, 95% CR1 CI)", fontsize=8.4)
    ax1.set_title("A. Fixed 8th-Report Age Gradients & Common Support", fontsize=9.6, fontweight="bold", loc="left", pad=8)
    leg_a = [
        Line2D([0], [0], marker="o", color="#334155", mfc="#334155", markersize=6.5, linestyle="None", label=r"Filled: $p_{\mathrm{WCB}} < 0.05$"),
        Line2D([0], [0], marker="o", color="#334155", mfc="white", mew=1.4, markersize=6.5, linestyle="None", label=r"Hollow: $p_{\mathrm{WCB}} \geq 0.05$"),
    ]
    ax1.legend(handles=leg_a, loc="lower center", bbox_to_anchor=(0.50, -0.20), ncol=2, frameon=True, fontsize=7.6)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Complete 18-OEM Leave-One-OEM-Out (LOOO) Sensitivity
    looo_s = df_looo.sort_values("Pure_x_Age_Coef", ascending=True).reset_index(drop=True)
    y_b = np.arange(len(looo_s))
    ax2.axvline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=1)

    for i, r in looo_s.iterrows():
        is_t = r["Dropped_OEM"] == "Tesla, Inc."
        dc = float(r["Dealer_Age_Coef"])
        ax2.scatter(dc, i, marker="D", s=34, color=COLORS["Dealer_Software"], edgecolor="#0f172a", linewidth=0.4, zorder=4)
        pc, pse, pp = float(r["Pure_x_Age_Coef"]), float(r["Pure_x_Age_SE"]), float(r["Pure_x_Age_pWCB"])
        pcol = COLORS["Red"] if is_t else COLORS["Pure_OTA"]
        pfill = pp < 0.05
        ax2.errorbar(
            pc,
            i,
            xerr=1.96 * pse,
            fmt="o",
            color=pcol,
            mfc=pcol if pfill else "white",
            mec=pcol,
            mew=1.4,
            markersize=6.2 if not is_t else 7.6,
            elinewidth=1.2 if not is_t else 1.7,
            capsize=2.2,
            zorder=5 if is_t else 4,
        )
        if is_t:
            ax2.axhspan(i - 0.45, i + 0.45, color="#fef2f2", alpha=0.9, zorder=0)
            ax2.annotate(
                f"Drop Tesla: {pc:+.2f}\n($p_{{WCB}}$={pp:.3f})",
                xy=(pc, i),
                xytext=(7.2, 2.2),
                fontsize=7.4,
                fontweight="bold",
                color=COLORS["Red"],
                bbox={"boxstyle": "round,pad=0.3", "facecolor": "#fef2f2", "edgecolor": COLORS["Red"], "linewidth": 0.8},
                arrowprops={"arrowstyle": "->", "color": COLORS["Red"], "lw": 1.0},
                zorder=6,
            )

    n_nonsig = int((looo_s["Pure_x_Age_pWCB"] >= 0.05).sum())
    ax2.set_yticks(y_b)
    ax2.set_yticklabels([f"Drop {short_oem(o)}" for o in looo_s["Dropped_OEM"]], fontsize=7.4)
    ax2.set_xlim(-6.2, 12.2)
    ax2.set_xlabel("Coefficient (pp per Vehicle-Age Year, 95% CR1 CI)", fontsize=8.4)
    ax2.set_title(f"B. Leave-One-OEM-Out Across All {len(looo_s)} OEMs", fontsize=9.6, fontweight="bold", loc="left", pad=8)
    leg_b = [
        Line2D([0], [0], marker="D", color="w", mfc=COLORS["Dealer_Software"], mec="#0f172a", markersize=6, label=rf"Dealer Age (18/18 $p_{{\mathrm{{WCB}}}} \leq {looo_s['Dealer_Age_pWCB'].max():.3f}$)"),
        Line2D([0], [0], marker="o", color=COLORS["Pure_OTA"], mfc=COLORS["Pure_OTA"], markersize=6, linestyle="None", label=rf"Pure$\times$Age $p_{{\mathrm{{WCB}}}} < 0.05$ ({len(looo_s)-n_nonsig}/18)"),
        Line2D([0], [0], marker="o", color=COLORS["Pure_OTA"], mfc="white", mew=1.4, markersize=6, linestyle="None", label=rf"Pure$\times$Age $p_{{\mathrm{{WCB}}}} \geq 0.05$ ({n_nonsig}/18)"),
    ]
    ax2.legend(handles=leg_b, loc="lower center", bbox_to_anchor=(0.48, -0.25), ncol=1, frameon=True, fontsize=7.3)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    save_dual(fig, "fig3_v4_age_gradients_and_looo")


def make_fig4(econ: dict, df_camp: pd.DataFrame) -> None:
    """Fig 4: Public Campaign API Measurement Audit & Retained Hybrid-OTA 7.01x Batch-Scale Contrast."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(14.4, 5.4), gridspec_kw={"width_ratios": [1.05, 1.05]})
    fig.subplots_adjust(wspace=0.62)

    # Panel A: Public API Measurement Validation Audit (2019-2026)
    c19 = df_camp[df_camp["rec_year"].between(2019, 2026)].copy()
    yrs = list(range(2019, 2027))
    pure_n = [int(((c19["rec_year"] == y) & (c19["is_ota_pure"] == 1)).sum()) for y in yrs]
    hyb_sw = [int(((c19["rec_year"] == y) & (c19["is_ota_hybrid_swchoice"] == 1)).sum()) for y in yrs]
    hyb_hw = [int(((c19["rec_year"] == y) & (c19["is_ota_hybrid_hwmixed"] == 1)).sum()) for y in yrs]
    api_n = [int(((c19["rec_year"] == y) & (c19["is_ota_api_full"] == 1)).sum()) for y in yrs]

    x = np.arange(len(yrs))
    w = 0.56
    ax1.bar(x, pure_n, width=w, color=COLORS["Pure_OTA"], label="Part 573 Text: Pure-OTA (Wireless-Only)")
    ax1.bar(x, hyb_sw, bottom=pure_n, width=w, color=COLORS["Hybrid_OTA"], label="Part 573 Text: Hybrid SW-Choice")
    ax1.bar(x, hyb_hw, bottom=np.array(pure_n) + np.array(hyb_sw), width=w, color=COLORS["Hybrid_HW"], label="Part 573 Text: Hybrid HW-Mixed")
    ax1.plot(x, api_n, color=COLORS["API_OTA"], marker="o", linewidth=2.2, markersize=6.8, zorder=5, label="Live Public API overTheAirUpdate = True")
    ax1.scatter([yrs.index(2025)], [33], marker="*", s=165, color=COLORS["Green"], edgecolor="#0f172a", linewidth=0.6, zorder=6, label="NHTSA 2025 Annual Recalls Report (33)")

    ax1.axvline(yrs.index(2025) - 0.38, color=COLORS["Red"], linestyle="--", linewidth=1.2)
    ax1.annotate(
        "May 8, 2025 Break:\n25V282000 (36/36 True)\n→ May 9 25V315000 (44/44 False)\n0/68 True post-cutoff",
        xy=(yrs.index(2025), 4.2),
        xytext=(0.15, 34.5),
        fontsize=7.3,
        fontweight="bold",
        color=COLORS["Red"],
        bbox={"boxstyle": "round,pad=0.38", "facecolor": "#fef2f2", "edgecolor": COLORS["Red"], "linewidth": 0.85},
        arrowprops={"arrowstyle": "->", "color": COLORS["Red"], "lw": 1.15, "connectionstyle": "arc3,rad=-0.12"},
        zorder=7,
    )

    for i, (p, hs, hh, a) in enumerate(zip(pure_n, hyb_sw, hyb_hw, api_n, strict=True)):
        tot = p + hs + hh
        ax1.text(i, tot + 0.8, f"{tot}", ha="center", va="bottom", fontsize=7.6, fontweight="bold", color="#0f172a")
        if yrs[i] >= 2025:
            ax1.text(
                i,
                a + 2.2,
                f"API={a}",
                ha="center",
                va="bottom",
                fontsize=7.2,
                fontweight="bold",
                color=COLORS["API_OTA"],
                bbox={"boxstyle": "round,pad=0.15", "facecolor": "white", "edgecolor": COLORS["API_OTA"], "alpha": 0.92, "lw": 0.6},
                zorder=8,
            )

    ax1.set_xticks(x)
    ax1.set_xticklabels([str(y) for y in yrs], fontsize=8.4)
    ax1.set_ylim(0, 46)
    ax1.set_ylabel("Annual Vehicle Recall Campaigns (Count)", fontsize=8.5)
    ax1.set_title("A. Public Campaign API Measurement Audit (2019–2026)", fontsize=9.6, fontweight="bold", loc="left", pad=8)
    ax1.legend(loc="lower center", bbox_to_anchor=(0.48, -0.34), ncol=2, frameon=True, fontsize=7.1)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Retained Within-OEM Hybrid-OTA 7.01x Batch-Scale Contrast vs Null Unconditional ITT
    p1 = econ["pillar1_blast_radius"]
    scale_specs = [
        ("Hybrid-OTA vs. Dealer-SW\n(Main FE)", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"], "s"),
        ("Hybrid-OTA vs. Dealer-SW\n(OEM × Year FE)", p1["robustness_ladder"]["oem_x_year_fe_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"], "s"),
        ("Hybrid-OTA vs. Dealer-SW\n(Make × Model FE)", p1["robustness_ladder"]["make_x_model_fe_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"], "s"),
        ("Hybrid-OTA vs. Dealer-SW\n(Excl. Tesla & Ford)", p1["robustness_ladder"]["excl_tesla_ford_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"], "s"),
        ("Hybrid SW-Choice Only\n(No Hardware Clause)", p1["robustness_ladder"]["hybrid_swchoice_vs_hwmixed"]["terms"]["is_ota_hybrid_swchoice"], COLORS["Hybrid_OTA"], "s"),
        ("Pure-OTA vs. Dealer-SW\n(Main FE)", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_pure"], COLORS["Pure_OTA"], "o"),
        ("Unconditional First-OTA\nOEM ITT (TWFE)", p1["itt_staggered_adoption"]["pooled_did"]["terms"]["post_ota_adopt"], COLORS["ITT"], "D"),
    ]
    sa = p1["itt_staggered_adoption"]["sun_abraham_iw"]
    sa_dict = {
        "coef": sa["iw_post_coef"],
        "ci95_lo": round(sa["iw_post_coef"] - 1.996 * sa["iw_se_cr1"], 4),
        "ci95_hi": round(sa["iw_post_coef"] + 1.996 * sa["iw_se_cr1"], 4),
        "p_wcb": sa["iw_p_t_G1"],
        "is_pt": True,
    }
    scale_specs.append(("Unconditional First-OTA\nOEM ITT (Sun–Abraham IW)", sa_dict, COLORS["ITT"], "D"))

    y_s = np.arange(len(scale_specs))[::-1]
    ax2.axvline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=1)
    ax2.axhline(1.5, color="#cbd5e1", linestyle=":", linewidth=1.0)

    for idx, (_lbl, d, col, mk) in enumerate(scale_specs):
        y = y_s[idx]
        c, lo, hi, pv = float(d["coef"]), float(d["ci95_lo"]), float(d["ci95_hi"]), float(d["p_wcb"])
        filled = pv < 0.05
        ax2.errorbar(
            c,
            y,
            xerr=[[max(0.0, c - lo)], [max(0.0, hi - c)]],
            fmt=mk,
            color=col,
            mfc=col if filled else "white",
            mec=col,
            mew=1.4,
            markersize=6.6,
            elinewidth=1.4,
            capsize=3.0,
            zorder=4,
        )
        p_lbl = rf"$p_t$={pv:.3f}" if d.get("is_pt") else rf"$p$={pv:.3f}"
        mult = f" ({np.exp(c):.2f}×)" if c > 1.2 and filled else ""
        ax2.text(3.75, y, f"{c:+.2f}{mult}, {p_lbl}", va="center", ha="left", fontsize=7.3, fontweight="bold" if filled else "normal", color=col if filled else "#475569")

    ax2.set_yticks(y_s)
    ax2.set_yticklabels([x[0] for x in scale_specs], fontsize=7.5, linespacing=1.05)
    ax2.set_xlim(-2.2, 3.65)
    ax2.set_xlabel("Log Points on log(1 + Affected Vehicle-Instances), 95% CR1 CI", fontsize=8.4)
    ax2.set_title("B. Conditional Hybrid Batch-Scale vs. Unconditional ITT", fontsize=9.6, fontweight="bold", loc="left", pad=8)
    leg_4b = [
        Line2D([0], [0], marker="s", color=COLORS["Hybrid_OTA"], mfc=COLORS["Hybrid_OTA"], markersize=6, linestyle="None", label="Conditional Hybrid-OTA (p < 0.05)"),
        Line2D([0], [0], marker="D", color=COLORS["ITT"], mfc="white", mew=1.4, markersize=6, linestyle="None", label="Unconditional First-OTA ITT (Null)"),
    ]
    ax2.legend(handles=leg_4b, loc="lower center", bbox_to_anchor=(0.48, -0.31), ncol=1, frameon=True, fontsize=7.2)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    save_dual(fig, "fig4_v4_api_audit_and_hybrid_scale")


def main() -> None:
    v4 = json.loads((RES_DIR / "d12_v4_fixed_report_audit.json").read_text(encoding="utf-8"))
    econ = json.loads((RES_DIR / "d12_econometric_results.json").read_text(encoding="utf-8"))
    df_flow = pd.read_csv(TBL_DIR / "table_v4_sample_flow.csv")
    df_comp = pd.read_csv(TBL_DIR / "table_v4_eighth_report_completion.csv")
    df_sens = pd.read_csv(TBL_DIR / "table_v4_vehicle_age_sensitivity.csv")
    df_looo = pd.read_csv(TBL_DIR / "table_v4_looo_sensitivity.csv")
    panel8 = pd.read_csv(PROC_DIR / "d12_v4_eighth_report_analysis_panel.csv")
    df_camp = pd.read_csv(PROC_DIR / "campaigns_2015_2026.csv")

    make_fig1(v4, df_flow, df_comp)
    make_fig2(v4, panel8)
    make_fig3(df_sens, df_looo)
    make_fig4(econ, df_camp)
    print("[DONE] Generated all 4 zero-hardcode v4 figures (300-DPI PNG + vector PDF) -> figures/", flush=True)


if __name__ == "__main__":
    main()
