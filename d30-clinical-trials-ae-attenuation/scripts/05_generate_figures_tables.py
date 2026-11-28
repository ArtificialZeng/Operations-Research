"""Generate 4 JCE main-text figures + 4 supplementary appendix figures (300 DPI PNG + vector PDF).

All numeric values are loaded dynamically from verified JSON receipts:
  - results/d30_econometrics_results.json
  - results/08_reporting_sensitivity.json
  - results/d30_gate2_openfda_results.json
  - data/processed/meddra_soc_abs_summary.json

All main-text slopes and intervals are scaled strictly per +10 percentage points (+10 pp)
of Eastern European EU site share over observed [0%, 35%] support (zero 0->100% extrapolation
titles). Zero hardcoded empirical numbers.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"
FIG_DIR = BASE_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Okabe-Ito colorblind-safe publication palette
C_BLUE = "#0072B2"
C_VERM = "#D55E00"
C_GREEN = "#009E73"
C_PURPLE = "#CC79A7"
C_AMBER = "#E69F00"
C_SLATE = "#4D4D4D"
C_SKY = "#56B4E9"

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9.3,
    "axes.titlesize": 10.3,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.3,
    "xtick.labelsize": 8.3,
    "ytick.labelsize": 8.3,
    "legend.fontsize": 8.0,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.24,
    "grid.linestyle": "--",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def fmt_p(p: float | None) -> str:
    if p is None or (isinstance(p, float) and np.isnan(p)):
        return "NA"
    if p == 0.0 or p < 1e-16:
        return "p<1e-16"
    if p < 1e-4:
        return f"p={p:.1e}"
    if p < 0.001:
        return f"p={p:.4f}"
    return f"p={p:.3f}"


def save_dual(fig: plt.Figure, stem: str) -> None:
    png_path = FIG_DIR / f"{stem}.png"
    pdf_path = FIG_DIR / f"{stem}.pdf"
    fig.savefig(png_path, dpi=300, bbox_inches="tight", facecolor="white")
    fig.savefig(pdf_path, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    print(f"  [SAVED] {png_path.name} ({png_path.stat().st_size / 1024:.1f} KB) + {pdf_path.name}", flush=True)


def _ci10_half(t: dict) -> float:
    """Return half-width of the 95% CI in percentage points per +10 pp site share."""
    if "per_10pp_ci95_hi" in t and "per_10pp_coef" in t:
        return float(100.0 * (t["per_10pp_ci95_hi"] - t["per_10pp_coef"]))
    return float(10.0 * (t["ci95_hi"] - t["coef"]))


# =============================================================================
# MAIN FIGURE 1: Two-Way Alternative-Region Counterfactuals & Spec Replication
# =============================================================================
def make_fig1_main_counterfactuals_and_specs(econ: dict, sens: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(16.0, 6.2), gridspec_kw={"width_ratios": [1.05, 1.25]})
    fig.subplots_adjust(wspace=0.58)

    # Panel A: Two-Way Alternative-Region Counterfactuals (+10 pp EU-East replacing -10 pp comparator)
    ax = axes[0]
    cf_rows = sens["alternative_region_counterfactuals"]["phase3"]
    comp_order = [
        ("us_sh", "United States (baseline)"),
        ("na_sh", "North America (U.S. + Canada)"),
        ("we_eu_sh", "Western Europe (EU/EEA only)"),
        ("we_sh", "Western Europe & Dev. APAC/CA"),
        ("latam_sh", "Latin America"),
        ("asia_sh", "Emerging Asia"),
        ("dev_apac_no_ca_sh", "Developed APAC / Israel"),
        ("ru_ua_sh", "Non-EU Eastern Europe / RU-UA"),
    ]
    lookup = {(r["outcome"], r["comparator_key"]): r for r in cf_rows}
    yp = np.arange(len(comp_order))[::-1]
    for i, (ckey, _clbl) in enumerate(comp_order):
        rc = lookup[("ctrl_oth", ckey)]
        ra = lookup[("act_oth", ckey)]
        ec_hw = rc["per_10pp_ci95_hi_pp"] - rc["per_10pp_pp"]
        ea_hw = ra["per_10pp_ci95_hi_pp"] - ra["per_10pp_pp"]
        ax.errorbar(
            rc["per_10pp_pp"], yp[i] + 0.14, xerr=ec_hw, fmt="o", color=C_BLUE,
            markersize=6.0, capsize=3, lw=1.6, label="Placebo Arm" if i == 0 else None,
        )
        ax.errorbar(
            ra["per_10pp_pp"], yp[i] - 0.14, xerr=ea_hw, fmt="s", color=C_VERM,
            markersize=6.0, capsize=3, lw=1.6, label="Active Arm" if i == 0 else None,
        )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([x[1] for x in comp_order], fontsize=8.4)
    ax.set_ylim(-0.7, len(comp_order) - 0.3)
    ax.set_xlim(-5.5, 1.2)
    ax.set_xlabel("Registered Non-Serious AE Difference per +10 pp EU-East Share (pp, 95% CI)")
    n_p3 = econ["block_a_core_twin_trial"]["p3_mol_sponsor_split"]["ctrl_oth"]["n"]
    ax.set_title(
        f"A. Two-Way Alternative-Region Counterfactuals\n(+10 pp EU-East Replacing −10 pp Comparator; P3 N={n_p3:,})",
        pad=10,
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=True, framealpha=0.95)

    # Panel B: Cross-Specification & Sensitivity Replication (per +10 pp EU-East)
    ax = axes[1]
    a_blk = econ["block_a_core_twin_trial"]
    b_blk = econ["block_b_sensitivity_robustness"]
    tf_p3 = sens["meddra_threshold_and_bounds"]["ae_timeframe_audit"]["restricted_to_documented_timeframe"]["phase3"]
    drop10 = sens["effective_fwl_weights"]["phase3"]["leave_top_weighted_programs_out"]["drop_top10_weighted_programs"]

    specs = [
        ("P3 Mol × Sponsor FE (Primary)", a_blk["p3_mol_sponsor_split"]["ctrl_oth"]["terms"]["eu_east_sh"], a_blk["p3_mol_sponsor_split"]["act_oth"]["terms"]["eu_east_sh"], a_blk["p3_mol_sponsor_split"]["ctrl_oth"]["n"]),
        ("P3 Mol × Condition FE", a_blk["p3_mol_cond_split"]["ctrl_oth"]["terms"]["eu_east_sh"], a_blk["p3_mol_cond_split"]["act_oth"]["terms"]["eu_east_sh"], a_blk["p3_mol_cond_split"]["ctrl_oth"]["n"]),
        ("P3 Mol × Sp × Cond Triplet FE", a_blk["p3_mol_sp_cond_split"]["ctrl_oth"]["terms"]["eu_east_sh"], a_blk["p3_mol_sp_cond_split"]["act_oth"]["terms"]["eu_east_sh"], a_blk["p3_mol_sp_cond_split"]["ctrl_oth"]["n"]),
        ("P3 Documented AE Time Frame Only", tf_p3["ctrl"], tf_p3["act"], tf_p3["ctrl"]["n"]),
        ("P3 Drop Top-10 Weighted Programs", drop10["ctrl"], drop10["act"], drop10["ctrl"]["n"]),
        ("P3 Strict 5% Threshold Only", b_blk["p3_freq5_mol_sp"]["ctrl_oth"]["terms"]["eu_east_sh"], b_blk["p3_freq5_mol_sp"]["act_oth"]["terms"]["eu_east_sh"], b_blk["p3_freq5_mol_sp"]["ctrl_oth"]["n"]),
        ("Pooled P2+P3 Mol × Sponsor FE", a_blk["p23_mol_sponsor_split"]["ctrl_oth"]["terms"]["eu_east_sh"], a_blk["p23_mol_sponsor_split"]["act_oth"]["terms"]["eu_east_sh"], a_blk["p23_mol_sponsor_split"]["ctrl_oth"]["n"]),
        ("P2+P3 + SYSTEMATIC Control", b_blk["systematic_control_p23_mol_sp"]["ctrl_oth"]["terms"]["eu_east_sh"], b_blk["systematic_control_p23_mol_sp"]["act_oth"]["terms"]["eu_east_sh"], b_blk["systematic_control_p23_mol_sp"]["ctrl_oth"]["n"]),
        ("P2+P3 All-Status (w/ Terminated)", b_blk["allstatus_incl_terminated_p23_mol_sp"]["ctrl_oth"]["terms"]["eu_east_sh"], b_blk["allstatus_incl_terminated_p23_mol_sp"]["act_oth"]["terms"]["eu_east_sh"], b_blk["allstatus_incl_terminated_p23_mol_sp"]["ctrl_oth"]["n"]),
        ("Phase 2 Standalone OOS (TA FE)", a_blk["p2_standalone_ta_fe_split"]["ctrl_oth"]["terms"]["eu_east_sh"], a_blk["p2_standalone_ta_fe_split"]["act_oth"]["terms"]["eu_east_sh"], a_blk["p2_standalone_ta_fe_split"]["ctrl_oth"]["n"]),
        ("Non-Placebo Active-Comparator OOS", b_blk["non_placebo_active_comparator_oos_p23_mol_sp"]["trial_mean_oth"]["terms"]["eu_east_sh"], None, b_blk["non_placebo_active_comparator_oos_p23_mol_sp"]["trial_mean_oth"]["n"]),
    ]
    yp2 = np.arange(len(specs))[::-1]
    for i, (_lbl, tc, ta, _n) in enumerate(specs):
        ax.errorbar(
            100.0 * tc["per_10pp_coef"], yp2[i] + (0.14 if ta else 0.0), xerr=_ci10_half(tc),
            fmt="o", color=C_BLUE if ta else C_PURPLE, markersize=5.6, capsize=2.8, lw=1.5,
            label="Placebo Arm" if i == 0 else ("Trial Mean (Non-Placebo OOS)" if ta is None else None),
        )
        if ta is not None:
            ax.errorbar(
                100.0 * ta["per_10pp_coef"], yp2[i] - 0.14, xerr=_ci10_half(ta),
                fmt="s", color=C_VERM, markersize=5.6, capsize=2.8, lw=1.5,
                label="Active Arm" if i == 0 else None,
            )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp2)
    ax.set_yticklabels([f"{s[0]} (N={s[3]:,})" for s in specs], fontsize=8.2)
    ax.set_ylim(-0.7, len(specs) - 0.3)
    ax.set_xlim(-5.2, 0.8)
    ax.set_xlabel("Registered Non-Serious AE Difference per +10 pp EU-East Share (pp, 95% CI)")
    ax.set_title("B. Within-Program & Out-of-Sample Replication\n(All Scaled Strictly per +10 pp EU-East Site Share)", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=3, frameon=True, framealpha=0.95, fontsize=7.9)

    save_dual(fig, "fig1_main_within_program_and_counterfactuals")


# =============================================================================
# MAIN FIGURE 2: Observed [0%, 35%] Spline, Extensive/Intensive & FWL Weights
# =============================================================================
def make_fig2_support_spline_and_weights(sens: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(21.2, 6.0), gridspec_kw={"width_ratios": [1.18, 1.12, 1.0]})
    fig.subplots_adjust(wspace=0.72)

    # Panel A: Observed [0%, 35%] Restricted Cubic Spline + Binned Points + Support Histogram
    ax = axes[0]
    nl3 = sens["nonlinear_bins_and_spline"]["phase3"]
    c_curve = [pt for pt in nl3["rcs_4knot"]["ctrl"]["curve_vs_0pct"] if pt["share_pct"] <= 35.0]
    a_curve = [pt for pt in nl3["rcs_4knot"]["act"]["curve_vs_0pct"] if pt["share_pct"] <= 35.0]
    xs = np.array([pt["share_pct"] for pt in c_curve])
    yc = np.array([pt["pred_diff_pp"] for pt in c_curve])
    yc_lo = np.array([pt["ci95_lo_pp"] for pt in c_curve])
    yc_hi = np.array([pt["ci95_hi_pp"] for pt in c_curve])
    ya = np.array([pt["pred_diff_pp"] for pt in a_curve])
    ya_lo = np.array([pt["ci95_lo_pp"] for pt in a_curve])
    ya_hi = np.array([pt["ci95_hi_pp"] for pt in a_curve])

    ax.fill_between(xs, yc_lo, yc_hi, color=C_BLUE, alpha=0.14)
    ax.fill_between(xs, ya_lo, ya_hi, color=C_VERM, alpha=0.12)
    ax.plot(xs, yc, "-", color=C_BLUE, lw=2.0, label=f"Placebo 4-knot RCS (nonlin {fmt_p(nl3['rcs_4knot']['ctrl']['nonlinearity_wald_p'])})")
    ax.plot(xs, ya, "--", color=C_VERM, lw=2.0, label=f"Active 4-knot RCS (nonlin {fmt_p(nl3['rcs_4knot']['act']['nonlinearity_wald_p'])})")

    # Overlay binned points inside [0, 35%]
    for arm, col, mk, dx in [("ctrl", C_BLUE, "o", -0.35), ("act", C_VERM, "s", +0.35)]:
        bins = [b for b in nl3["binned"][arm]["bins"] if b["bin"] != ">35%"]
        bx = [b["mean_share_pct"] + dx for b in bins]
        by = [b["coef_pp"] for b in bins]
        be = [b["ci95_hi_pp"] - b["coef_pp"] for b in bins]
        ax.errorbar(bx, by, yerr=be, fmt=mk, color=col, markersize=5.5, capsize=2.8, lw=1.2, alpha=0.9)

    ax.axhline(0, color="black", lw=0.9)
    # Inset bottom density rug from observed Phase-3 shares
    panel = pd.read_parquet(DATA_DIR / "d30_mrct_placebo_panel.parquet")
    p3_sh = 100.0 * panel.loc[panel["is_phase3"] == 1, "eu_east_sh"].to_numpy()
    p3_clip = p3_sh[p3_sh <= 35.0]
    ax2 = ax.twinx()
    ax2.hist(p3_clip, bins=np.linspace(0, 35, 18), color="#94A3B8", alpha=0.22, edgecolor="none")
    ax2.set_ylim(0, 1600)
    ax2.set_yticks([])
    ax2.spines["right"].set_visible(False)
    ax2.spines["top"].set_visible(False)

    ax.set_xlim(-1.2, 36.2)
    ax.set_ylim(-15.5, 3.0)
    ax.set_xlabel("Eastern European EU Site Share (%, Observed 0–35% Support)")
    ax.set_ylabel("Difference vs. 0% EU-East Share (pp, 95% CI)")
    ax.set_title("A. Observed Support [0%, 35%]: Binned & RCS Curve\n(Phase 3 Mol × Sponsor FE; 95th Pct = 35.3%)", pad=10)
    ax.legend(loc="lower left", frameon=True, framealpha=0.95, fontsize=7.6)

    # Panel B: Extensive vs. Intensive Margin & Exact Common-236-Program Comparison
    ax = axes[1]
    ext_rows = sens["extensive_intensive_decomposition"]["models"]
    elook = {(r["sample"], r["arm"]): r for r in ext_rows}
    margin_specs = [
        ("All P3 (328 progs)", "all_phase3"),
        ("0–50% (325 progs)", "exclude_shares_above_50_percent"),
        ("0–35% (310 progs)", "shares_at_most_35_percent"),
        ("0–35% + Zero Ind.", "shares_0_35_with_zero_indicator"),
        ("All P3 + Zero Ind.", "all_phase3_with_zero_indicator"),
        ("Common 236: 0–35%", "common_236_progs_0_35_full"),
        ("Common 236 + Zero", "common_236_progs_0_35_with_zero_ind"),
        ("Common 236: (0,35%]", "common_236_progs_positive_0_35"),
        ("All Pos. >0% (257)", "positive_shares_all_phase3"),
    ]
    yp = np.arange(len(margin_specs))[::-1]
    for i, (_lbl, skey) in enumerate(margin_specs):
        rc = elook[(skey, "ctrl")]
        ra = elook[(skey, "act")]
        ax.errorbar(
            100.0 * rc["per_10pp_coef"], yp[i] + 0.14, xerr=_ci10_half(rc),
            fmt="o", color=C_BLUE, markersize=5.5, capsize=2.8, lw=1.5,
            label="Placebo Arm" if i == 0 else None,
        )
        ax.errorbar(
            100.0 * ra["per_10pp_coef"], yp[i] - 0.14, xerr=_ci10_half(ra),
            fmt="s", color=C_VERM, markersize=5.5, capsize=2.8, lw=1.5,
            label="Active Arm" if i == 0 else None,
        )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([f"{lbl} (n={elook[(sk, 'ctrl')]['n']:,})" for lbl, sk in margin_specs], fontsize=8.0)
    ax.set_ylim(-0.7, len(margin_specs) - 0.3)
    ax.set_xlim(-5.2, 2.0)
    ax.set_xlabel("Slope per +10 pp EU-East Share (pp, 95% CI)")
    ax.set_title("B. Extensive vs. Intensive Margin &\nCommon-Drug-Program Decomposition", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=True, framealpha=0.95, fontsize=8.0)

    # Panel C: Effective FWL Regression Weights (Aronow-Samii) & Support-Zone Leverage
    ax = axes[2]
    fw = sens["effective_fwl_weights"]["phase3"]
    top10 = fw["top10_programs"]
    names = [f"{p['molecule'][:13]} ({p['n_trials']})" for p in top10]
    wts = [p["weight_pct"] for p in top10]
    yp3 = np.arange(len(top10))[::-1]
    ax.barh(yp3, wts, color=C_BLUE, alpha=0.82, height=0.62)
    for i, wv in enumerate(wts):
        ax.text(wv + 0.25, yp3[i], f"{wv:.1f}%", va="center", ha="left", fontsize=7.6)
    ax.set_yticks(yp3)
    ax.set_yticklabels(names, fontsize=7.8)
    ax.set_xlim(0, max(wts) + 3.2)
    ax.set_xlabel("Effective FWL Weight Share (%)")
    wz = fw["weight_by_support_zone_pct"]
    d20 = fw["leave_top_weighted_programs_out"]["drop_top20_weighted_programs"]
    ax.text(
        0.97, 0.08,
        f"Total programs: {fw['n_programs']}\n"
        f"Effective N_prog: {fw['effective_n_programs']:.1f}\n"
        f"Top-10 share: {fw['top10_programs_weight_pct']:.1f}%\n"
        f"Support weight:\n"
        f"  0%: {wz['zero_share']:.1f}% | (0,35%]: {wz['pos_0_to_35']:.1f}%\n"
        f"  >35%: {wz['above_35']:.1f}%\n"
        f"Drop Top-20 progs:\n"
        f"  Ctrl {100*d20['ctrl']['per_10pp_coef']:+.2f} / Act {100*d20['act']['per_10pp_coef']:+.2f} pp",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=7.3,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#F8FAFC", "edgecolor": "#CBD5E1"},
    )
    ax.set_title("C. Top-10 Effective FWL Program Weights\n(Aronow–Samii Diagnostics; P3 N=1,282)", pad=10)

    save_dual(fig, "fig2_support_spline_and_weights")


# =============================================================================
# MAIN FIGURE 3: Four-State MedDRA Audit, Strict Contrasts & Sharp Manski Bounds
# =============================================================================
def make_fig3_meddra_fourstate_and_bounds(sens: dict, meddra_sum: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(21.4, 6.0), gridspec_kw={"width_ratios": [0.95, 1.08, 1.25]})
    fig.subplots_adjust(wspace=0.78)

    # Panel A: Four-State Cell Breakdown by Reporting Threshold Stratum (15 Subj + 15 Obj Common Panel)
    ax = axes[0]
    cc = meddra_sum["common_panel_four_state_counts"]
    strata = [
        ("0% Thr.\n(n=220)", "freq0"),
        ("5% Thr.\n(n=2,006)", "freq5"),
        ("Other >0%\n(n=545)", "other_thr"),
        ("All Trials\n(n=2,771)", "all"),
    ]
    states = [
        ("Observed Positive", "observed_pos", C_BLUE),
        ("True Zero", "true_zero", C_GREEN),
        ("Below-Threshold Censored", "below_threshold", C_AMBER),
        ("Missing Denom / Term", "anom", C_VERM),
    ]
    x = np.arange(len(strata))
    bottoms = np.zeros(len(strata))
    for slbl, skey, col in states:
        vals = []
        for _, st_tag in strata:
            tot = sum(
                cc.get(f"cpanel_{st_tag}_{k}", 0)
                for k in ("observed_pos", "true_zero", "below_threshold", "missing_unreliable_denom", "missing_term")
            )
            if skey == "anom":
                cnt = cc.get(f"cpanel_{st_tag}_missing_unreliable_denom", 0) + cc.get(f"cpanel_{st_tag}_missing_term", 0)
            else:
                cnt = cc.get(f"cpanel_{st_tag}_{skey}", 0)
            vals.append(100.0 * cnt / max(1, tot))
        ax.bar(x, vals, bottom=bottoms, width=0.58, color=col, alpha=0.88, label=slbl)
        for j, v in enumerate(vals):
            if v >= 9.0:
                ax.text(x[j], bottoms[j] + 0.5 * v, f"{v:.1f}%", ha="center", va="center", fontsize=7.6, color="white", fontweight="bold")
        bottoms += np.array(vals)
    ax.set_xticks(x)
    ax.set_xticklabels([s[0] for s in strata], fontsize=7.8)
    ax.set_ylabel("Share of Trial-Arm-Term Cells (%)")
    ax.set_ylim(0, 108)
    ax.set_title("A. Four-State Cell Audit\n(Pre-Defined 15+15 Common MedDRA Panel)", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.15), ncol=2, frameon=True, framealpha=0.95, fontsize=7.5)

    # Panel B: Paired Subjective minus Objective / Investigations Contrasts (per +10 pp EU-East)
    ax = axes[1]
    mb = sens["meddra_threshold_and_bounds"]
    sc_look = {(r["spec"], r["arm"]): r for r in mb["strict_vs_legacy_soc_contrasts"]}
    f0_look = {(r["fe"], r["arm"], r["outcome"]): r for r in mb["zero_threshold_uncensored_subset"]["models"]}

    c_items = [
        ("Legacy (P2+P3)", sc_look[("legacy_p23_subj_minus_obj", "ctrl")], sc_look[("legacy_p23_subj_minus_obj", "act")]),
        ("Strict (P2+P3)", sc_look[("strict_p23_subj_minus_obj", "ctrl")], sc_look[("strict_p23_subj_minus_obj", "act")]),
        ("Zero-Anomaly Only", sc_look[("strict_no_anomaly_p23_subj_minus_obj", "ctrl")], sc_look[("strict_no_anomaly_p23_subj_minus_obj", "act")]),
        ("Strict Phase 3", sc_look[("strict_p3_subj_minus_obj", "ctrl")], sc_look[("strict_p3_subj_minus_obj", "act")]),
        ("Subj − Investigations", sc_look[("strict_p23_subj_minus_investigations", "ctrl")], sc_look[("strict_p23_subj_minus_investigations", "act")]),
        ("Fixed 5% Thr.", sc_look[("strict_p23_freq5_subj_minus_obj", "ctrl")], sc_look[("strict_p23_freq5_subj_minus_obj", "act")]),
        ("0% Thr. (TA FE)", f0_look[("therapeutic_area", "ctrl", "strict_subj_minus_obj")], f0_look[("therapeutic_area", "act", "strict_subj_minus_obj")]),
        ("0% Panel (Subj−Inv)", f0_look[("therapeutic_area", "ctrl", "cpanel15_subj_minus_inv")], f0_look[("therapeutic_area", "act", "cpanel15_subj_minus_inv")]),
    ]
    yp = np.arange(len(c_items))[::-1]
    for i, (_lbl, rc, ra) in enumerate(c_items):
        ax.errorbar(
            rc["per_10pp_coef"], yp[i] + 0.14, xerr=rc["per_10pp_ci95_hi"] - rc["per_10pp_coef"],
            fmt="o", color=C_BLUE, markersize=5.5, capsize=2.8, lw=1.5,
            label="Placebo Arm" if i == 0 else None,
        )
        ax.errorbar(
            ra["per_10pp_coef"], yp[i] - 0.14, xerr=ra["per_10pp_ci95_hi"] - ra["per_10pp_coef"],
            fmt="s", color=C_VERM, markersize=5.5, capsize=2.8, lw=1.5,
            label="Active Arm" if i == 0 else None,
        )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([f"{lbl} (n={rc['n']:,})" for lbl, rc, _ in c_items], fontsize=7.9)
    ax.set_ylim(-0.7, len(c_items) - 0.3)
    ax.set_xlim(-0.18, 0.08)
    ax.set_xlabel("Paired (Subj − Obj) Summed-Rate Slope per +10 pp EU-East")
    ax.set_title("B. Strict Zero-Fallback & Threshold-Stratified\nPaired MedDRA Contrasts", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=True, framealpha=0.95, fontsize=8.0)

    # Panel C: Exact Sharp Manski FWL Bounds + Imbens-Manski 95% CIs on Peak Single-Term Rates (pp per +10 pp)
    ax = axes[2]
    b_look = {(b["stratum"], b["arm"], b["metric"]): b for b in mb["interval_and_manski_bounds"] if "error" not in b}
    m_items = [
        ("Subj. Peak (Ctrl, All)", b_look[("p23_all_thresholds", "ctrl", "strict_soc_subj_max_pct")], C_BLUE),
        ("Subj. Peak (Act, All)", b_look[("p23_all_thresholds", "act", "strict_soc_subj_max_pct")], C_VERM),
        ("Obj. Peak (Ctrl, All)", b_look[("p23_all_thresholds", "ctrl", "strict_soc_obj_max_pct")], C_GREEN),
        ("Obj. Peak (Act, All)", b_look[("p23_all_thresholds", "act", "strict_soc_obj_max_pct")], C_GREEN),
        ("Subj−Obj Peak (Ctrl)", b_look[("p23_all_thresholds", "ctrl", "strict_soc_maxpct_subj_minus_obj")], C_PURPLE),
        ("Subj−Obj Peak (Act)", b_look[("p23_all_thresholds", "act", "strict_soc_maxpct_subj_minus_obj")], C_PURPLE),
        ("Subj. Peak (Act, 5%)", b_look[("p23_fixed_5pct_threshold", "act", "strict_soc_subj_max_pct")], C_VERM),
        ("Subj−Obj Peak (Act, 5%)", b_look[("p23_fixed_5pct_threshold", "act", "strict_soc_maxpct_subj_minus_obj")], C_PURPLE),
    ]
    yp3 = np.arange(len(m_items))[::-1]
    for i, (_lbl, rec, col) in enumerate(m_items):
        ms = rec["manski_sharp_per_10pp"]
        # Imbens-Manski 95% CI (thin outer line)
        ax.plot([100 * ms["im95_lo"], 100 * ms["im95_hi"]], [yp3[i], yp3[i]], "-", color=col, lw=1.4, alpha=0.75)
        ax.plot([100 * ms["im95_lo"], 100 * ms["im95_hi"]], [yp3[i], yp3[i]], "|", color=col, markersize=7)
        # Sharp Manski Identification Interval [id_lo, id_hi] (thick bar)
        ax.plot([100 * ms["id_lo"], 100 * ms["id_hi"]], [yp3[i], yp3[i]], "-", color=col, lw=5.0, solid_capstyle="butt")
        # Uniform midpoint estimate dot
        mid_v = 100 * rec["uniform_midpoint"]["per_10pp_coef"]
        ax.plot(mid_v, yp3[i], "o", color="white", markeredgecolor=col, markeredgewidth=1.4, markersize=5.0)
        x_id_txt = max(100 * ms["im95_hi"] + 0.08, 0.08)
        ax.text(x_id_txt, yp3[i], f"ID [{100*ms['id_lo']:+.2f}, {100*ms['id_hi']:+.2f}]", va="center", ha="left", fontsize=7.1, color="#222222")

    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp3)
    ax.set_yticklabels([f"{lbl} ({rec['pct_point_identified_trials']:.0f}% pt-ID)" for lbl, rec, _ in m_items], fontsize=7.6)
    ax.set_ylim(-0.7, len(m_items) - 0.3)
    ax.set_xlim(-2.6, 1.95)
    ax.set_xlabel("Peak-Term Slope per +10 pp EU-East (pp; Thick = Manski ID, Thin = IM 95% CI)")
    ax.set_title("C. Sharp Manski FWL Bounds on Peak-Term Rates\n(72–88% Trials Point-Identified; Sums Wide under 5% Censoring)", pad=10)

    save_dual(fig, "fig3_meddra_fourstate_and_manski_bounds")


# =============================================================================
# MAIN FIGURE 4: Pre-Specified Clinical Equivalence (TOST) & Endpoint Scale
# =============================================================================
def make_fig4_tost_equivalence(econ: dict, sens: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.6, 5.6), gridspec_kw={"width_ratios": [1.22, 1.0]})
    fig.subplots_adjust(wspace=0.52)

    # Panel A: Pre-Specified TOST Equivalence Plot (90% CI thick + 95% CI thin vs Margins)
    ax = axes[0]
    tost_rows = sens["prespecified_equivalence_tost"]
    t_look = {(r["specification"], r["outcome"], r["margin_pp"]): r for r in tost_rows}

    plot_items = [
        ("P3 Placebo SAE (N=1,282)", t_look[("Phase 3 Mol × Sponsor FE", "ctrl_sae", 2.0)], 1.0, 2.0, C_GREEN),
        ("P3 Active SAE (N=1,282)", t_look[("Phase 3 Mol × Sponsor FE", "act_sae", 2.0)], 1.0, 2.0, C_GREEN),
        ("P3 Within-Trial RD (N=1,282)", t_look[("Phase 3 Mol × Sponsor FE", "oth_rd", 2.0)], 1.0, 2.0, C_BLUE),
        ("P2+P3 Placebo SAE (N=1,764)", t_look[("Pooled P2+P3 Mol × Sponsor FE", "ctrl_sae", 2.0)], 1.0, 2.0, C_GREEN),
        ("P2+P3 Active SAE (N=1,764)", t_look[("Pooled P2+P3 Mol × Sponsor FE", "act_sae", 2.0)], 1.0, 2.0, C_GREEN),
        ("P2+P3 Within-Trial RD (N=1,764)", t_look[("Pooled P2+P3 Mol × Sponsor FE", "oth_rd", 2.0)], 1.0, 2.0, C_BLUE),
        ("P3 Placebo Mortality (N=679)", t_look[("Phase 3 Mol × Sponsor FE", "ctrl_mort", 0.5)], 0.5, 1.0, C_VERM),
        ("P3 Active Mortality (N=679)", t_look[("Phase 3 Mol × Sponsor FE", "act_mort", 0.5)], 0.5, 1.0, C_VERM),
        ("P2+P3 Placebo Mortality (N=940)", t_look[("Pooled P2+P3 Mol × Sponsor FE", "ctrl_mort", 0.5)], 0.5, 1.0, C_VERM),
        ("P2+P3 Active Mortality (N=940)", t_look[("Pooled P2+P3 Mol × Sponsor FE", "act_mort", 0.5)], 0.5, 1.0, C_VERM),
    ]
    yp = np.arange(len(plot_items))[::-1]
    # Shaded equivalence zones: ±2.0 pp (light), ±1.0 pp (medium), ±0.5 pp (mortality primary)
    ax.axvspan(-2.0, 2.0, color="#E2E8F0", alpha=0.35, label="SAE / RD Primary Margin (±2.0 pp)")
    ax.axvspan(-1.0, 1.0, color="#CBD5E1", alpha=0.35, label="SAE / RD Strict Margin (±1.0 pp)")
    ax.axvline(-0.5, color=C_VERM, lw=1.1, ls=":", label="Mortality Primary Margin (±0.5 pp)")
    ax.axvline(+0.5, color=C_VERM, lw=1.1, ls=":")
    ax.axvline(0, color="black", lw=1.0)

    for i, (_lbl, r, _m1, _m2, col) in enumerate(plot_items):
        ax.plot([r["ci95_lo_pp"], r["ci95_hi_pp"]], [yp[i], yp[i]], "-", color=col, lw=1.4, alpha=0.8)
        ax.plot([r["ci90_lo_pp"], r["ci90_hi_pp"]], [yp[i], yp[i]], "-", color=col, lw=4.2, solid_capstyle="butt")
        ax.plot(r["per_10pp_pp"], yp[i], "o", color="white", markeredgecolor=col, markeredgewidth=1.4, markersize=5.2)
        tag = "EQ" if r["equivalent_alpha_05"] else "Not EQ"
        ax.text(r["ci95_hi_pp"] + 0.09, yp[i], f"{tag} ({fmt_p(r['p_tost'])})", va="center", ha="left", fontsize=7.2, color="#222222")

    ax.set_yticks(yp)
    ax.set_yticklabels([x[0] for x in plot_items], fontsize=8.0)
    ax.set_ylim(-0.7, len(plot_items) - 0.3)
    ax.set_xlim(-2.2, 2.85)
    ax.set_xlabel("Effect per +10 pp EU-East Share (pp; Thick = 90% TOST CI, Thin = 95% CI)")
    ax.set_title("A. Pre-Specified Clinical Equivalence (TOST)\nSAEs & RD Equivalent (±1–2 pp); Mortality Underpowered (±0.5 pp)", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.48, -0.14), ncol=2, frameon=True, framealpha=0.95, fontsize=7.5)

    # Panel B: Unified +10 pp Scale Comparison Across All Main Registry Endpoints (Pooled P2+P3)
    ax = axes[1]
    p23 = econ["block_a_core_twin_trial"]["p23_mol_sponsor_split"]
    soc_b = {
        (b["arm"], b["metric"]): b
        for b in sens["meddra_threshold_and_bounds"]["interval_and_manski_bounds"]
        if b.get("stratum") == "p23_all_thresholds" and "error" not in b
    }
    ep_items = [
        ("Placebo Non-Serious AE", 100 * p23["ctrl_oth"]["terms"]["eu_east_sh"]["per_10pp_coef"], _ci10_half(p23["ctrl_oth"]["terms"]["eu_east_sh"]), p23["ctrl_oth"]["terms"]["eu_east_sh"]["p"], C_BLUE),
        ("Active Non-Serious AE", 100 * p23["act_oth"]["terms"]["eu_east_sh"]["per_10pp_coef"], _ci10_half(p23["act_oth"]["terms"]["eu_east_sh"]), p23["act_oth"]["terms"]["eu_east_sh"]["p"], C_VERM),
        ("Subj. Peak-Term Rate (Ctrl)", 100 * soc_b[("ctrl", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"], 100 * (soc_b[("ctrl", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["per_10pp_ci95_hi"] - soc_b[("ctrl", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"]), soc_b[("ctrl", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["p"], C_AMBER),
        ("Subj. Peak-Term Rate (Act)", 100 * soc_b[("act", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"], 100 * (soc_b[("act", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["per_10pp_ci95_hi"] - soc_b[("act", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"]), soc_b[("act", "strict_soc_subj_max_pct")]["uniform_lower_bound"]["p"], C_AMBER),
        ("Obj. Peak-Term Rate (Ctrl)", 100 * soc_b[("ctrl", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"], 100 * (soc_b[("ctrl", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["per_10pp_ci95_hi"] - soc_b[("ctrl", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"]), soc_b[("ctrl", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["p"], C_GREEN),
        ("Obj. Peak-Term Rate (Act)", 100 * soc_b[("act", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"], 100 * (soc_b[("act", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["per_10pp_ci95_hi"] - soc_b[("act", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["per_10pp_coef"]), soc_b[("act", "strict_soc_obj_max_pct")]["uniform_lower_bound"]["p"], C_GREEN),
        ("Within-Trial Risk Diff (RD)", 100 * p23["oth_rd"]["terms"]["eu_east_sh"]["per_10pp_coef"], _ci10_half(p23["oth_rd"]["terms"]["eu_east_sh"]), p23["oth_rd"]["terms"]["eu_east_sh"]["p"], C_SLATE),
        ("Placebo Serious AE (SAE)", 100 * p23["ctrl_sae"]["terms"]["eu_east_sh"]["per_10pp_coef"], _ci10_half(p23["ctrl_sae"]["terms"]["eu_east_sh"]), p23["ctrl_sae"]["terms"]["eu_east_sh"]["p"], C_SLATE),
        ("Active Serious AE (SAE)", 100 * p23["act_sae"]["terms"]["eu_east_sh"]["per_10pp_coef"], _ci10_half(p23["act_sae"]["terms"]["eu_east_sh"]), p23["act_sae"]["terms"]["eu_east_sh"]["p"], C_SLATE),
        ("Placebo All-Cause Mortality", 100 * p23["ctrl_mort"]["terms"]["eu_east_sh"]["per_10pp_coef"], _ci10_half(p23["ctrl_mort"]["terms"]["eu_east_sh"]), p23["ctrl_mort"]["terms"]["eu_east_sh"]["p"], C_SLATE),
    ]
    yp2 = np.arange(len(ep_items))[::-1]
    for i, (_lbl, val, err, pv, col) in enumerate(ep_items):
        ax.errorbar(val, yp2[i], xerr=err, fmt="o", color=col, markersize=5.8, capsize=3, lw=1.6)
        x_txt = max(val + err + 0.14, 0.25) if val < 0 else (val + err + 0.14)
        ax.text(x_txt, yp2[i], f"{val:+.2f} pp ({fmt_p(pv)})", va="center", ha="left", fontsize=7.4, color="#222222")
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp2)
    ax.set_yticklabels([x[0] for x in ep_items], fontsize=8.0)
    ax.set_ylim(-0.7, len(ep_items) - 0.3)
    ax.set_xlim(-4.3, 3.3)
    ax.set_xlabel("Effect per +10 pp EU-East Site Share (pp, 95% CI)")
    ax.set_title("B. Unified +10 pp Scale Across Registry Endpoints\n(Pooled P2+P3 Mol × Sponsor FE, N=1,764)", pad=10)

    save_dual(fig, "fig4_tost_equivalence_sae_mortality")


# =============================================================================
# SUPPLEMENTARY FIGURES S1-S4 (Secondary & Exploratory Analyses per Review #4)
# =============================================================================
def make_figS1_ta_and_accrual(econ: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.0, 5.4))
    fig.subplots_adjust(wspace=0.45)

    # Panel A: Pan-Disease Therapeutic-Area Consistency (per +10 pp All-EE)
    ax = axes[0]
    ta_dict = econ["block_b_sensitivity_robustness"]["by_therapeutic_area_p23"]
    ta_sorted = sorted(ta_dict.items(), key=lambda kv: kv[1]["ctrl_oth"]["terms"]["ee_sh"]["coef"])
    yp = np.arange(len(ta_sorted))
    for i, (_ta, v) in enumerate(ta_sorted):
        tc = v["ctrl_oth"]["terms"]["ee_sh"]
        ta_m = v["act_oth"]["terms"]["ee_sh"]
        ax.errorbar(
            100.0 * tc["per_10pp_coef"], i + 0.14, xerr=_ci10_half(tc),
            fmt="o", color=C_BLUE, markersize=5.8, capsize=2.8, lw=1.5,
            label="Placebo Non-Serious AE" if i == 0 else None,
        )
        ax.errorbar(
            100.0 * ta_m["per_10pp_coef"], i - 0.14, xerr=_ci10_half(ta_m),
            fmt="s", color=C_VERM, markersize=5.8, capsize=2.8, lw=1.5,
            label="Active Non-Serious AE" if i == 0 else None,
        )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([f"{ta} (N={v['n_total']})" for ta, v in ta_sorted], fontsize=8.2)
    ax.set_xlim(-8.0, 3.6)
    ax.set_xlabel("Effect per +10 pp Eastern European Site Share (pp, 95% CI)")
    ax.set_title("A. Subgroup Consistency Across Therapeutic Areas\n(9/9 Clinical Domains Negative; Pooled P2+P3)", pad=10)
    ax.legend(loc="lower right", frameon=True, framealpha=0.95)

    # Panel B: Simplex-Valid Site-to-Patient Accrual Calibration Curve (per +10 pp)
    ax = axes[1]
    blk_e = econ["block_e_site_vs_patient_bounds"]
    cal = blk_e["nonlinear_patient_share_calibration_p23"]
    ws = np.array([r["w_ee_accrual_ratio"] for r in cal])
    bc = np.array([10.0 * r["ctrl_oth_coef"] for r in cal])
    bc_ci = np.array([10.0 * 1.975 * r["ctrl_oth_se"] for r in cal])
    ba = np.array([10.0 * r["act_oth_coef"] for r in cal])
    ba_ci = np.array([10.0 * 1.975 * r["act_oth_se"] for r in cal])
    w_hat = blk_e["implied_accrual_ratios_vs_us"]["w_hat_ee_all"]

    ax.fill_between(ws, bc - bc_ci, bc + bc_ci, color=C_BLUE, alpha=0.14)
    ax.fill_between(ws, ba - ba_ci, ba + ba_ci, color=C_VERM, alpha=0.14)
    ax.plot(ws, bc, "-o", color=C_BLUE, lw=2.0, markersize=5.5, label="Placebo Arm per +10 pp Patient Share")
    ax.plot(ws, ba, "-s", color=C_VERM, lw=2.0, markersize=5.5, label="Active Arm per +10 pp Patient Share")
    ax.axvline(w_hat, color=C_GREEN, lw=1.6, ls="--")
    ax.text(w_hat + 0.06, -0.55, f"Empirical Within-Program\nŵ_EE = {w_hat:.2f}× US", color=C_GREEN, fontsize=8.0, fontweight="bold")
    ax.axhline(0, color="black", lw=1.0)
    ax.set_xlabel("Assumed EE / Non-EE Per-Site Patient Accrual Ratio (w)")
    ax.set_ylabel("Implied Difference per +10 pp Patient Share (pp)")
    ax.set_ylim(-4.5, 0.5)
    ax.set_title("B. Simplex-Valid Site-to-Patient Accrual Calibration\n(Pooled P2+P3 Mol × Sponsor FE, w ∈ [0.5, 3.0])", pad=10)
    ax.legend(loc="lower right", frameon=True, framealpha=0.95)

    save_dual(fig, "figS1_therapeutic_areas_and_accrual_bounds")


def make_figS2_post2017_overlap(econ: dict) -> None:
    fig, axes = plt.subplots(1, 3, figsize=(18.4, 5.5))
    fig.subplots_adjust(wspace=0.52)
    blk_c = econ["block_c_post2017_fdaaa_decomposition"]

    # Panel A: Cross-Sectional Slopes Across 6 Time Windows (per +10 pp)
    ax = axes[0]
    es = blk_c["dynamic_event_study_p23_ta_fe"]
    x_idx = np.arange(len(es))
    eu_c = [100 * e["ctrl_oth"]["eu_east"]["per_10pp_coef"] for e in es]
    eu_c_ci = [_ci10_half(e["ctrl_oth"]["eu_east"]) for e in es]
    eu_a = [100 * e["act_oth"]["eu_east"]["per_10pp_coef"] for e in es]
    eu_a_ci = [_ci10_half(e["act_oth"]["eu_east"]) for e in es]
    ru_c = [100 * e["ctrl_oth"]["ru_ua"]["per_10pp_coef"] for e in es]
    ru_c_ci = [_ci10_half(e["ctrl_oth"]["ru_ua"]) for e in es]

    ax.errorbar(x_idx - 0.12, eu_c, yerr=eu_c_ci, fmt="-o", color=C_BLUE, lw=1.7, markersize=5.5, capsize=3, label="EU-East: Placebo")
    ax.errorbar(x_idx, eu_a, yerr=eu_a_ci, fmt="-s", color=C_VERM, lw=1.7, markersize=5.5, capsize=3, label="EU-East: Active")
    ax.errorbar(x_idx + 0.12, ru_c, yerr=ru_c_ci, fmt="--^", color=C_SLATE, lw=1.5, markersize=5.5, capsize=3, label="Non-EU RU/UA: Placebo")
    ax.axhline(0, color="black", lw=1.0)
    ax.axvline(3.5, color=C_GREEN, lw=1.4, ls=":")
    ax.text(3.40, 1.7, "Overlapping 2017\nRules (FDAAA/ICH)", color=C_GREEN, fontsize=7.6, fontweight="bold", ha="right")
    ax.set_xticks(x_idx)
    ax.set_xticklabels([f"{e['era']}\n(n={e['n']})" for e in es], fontsize=7.5)
    ax.set_ylabel("Cross-Sectional Slope per +10 pp (pp, 95% CI)")
    ax.set_ylim(-9.2, 3.0)
    ax.set_title("A. Era Cross-Sectional Slopes (2005–2024)\n(Descriptive Temporal Pattern)", pad=10)
    ax.legend(loc="lower left", frameon=True, framealpha=0.95, fontsize=7.6)

    # Panel B: Within-Program Period Interactions & Joint 2017 Overlap (per +10 pp)
    ax = axes[1]
    t3c = blk_c["p23_3era_lag_mol_sp"]["ctrl_oth"]["terms"]
    t3a = blk_c["p23_3era_lag_mol_sp"]["act_oth"]["terms"]
    tf5c = blk_c["p23_post2017_strict_freq5_mol_sp"]["ctrl_oth"]["terms"]
    thrc = blk_c["p23_horserace_ich_vs_fdaaa_mol_sp"]["ctrl_oth"]["terms"]
    items = [
        ("EU-East Pre-2017 (Ctrl)", t3c["eu_east_sh"], C_BLUE),
        ("EU-East Pre-2017 (Act)", t3a["eu_east_sh"], C_VERM),
        ("EU × 2017–19 Shift (Ctrl)", t3c["eu_x_17_19"], C_BLUE),
        ("EU × 2017–19 Shift (Act)", t3a["eu_x_17_19"], C_VERM),
        ("EU × 2020–24 Shift (Ctrl)", t3c["eu_x_20_24"], C_GREEN),
        ("EU × 2020–24 Shift (Act)", t3a["eu_x_20_24"], C_GREEN),
        ("EU × Post-17 (5% Thr. Only)", tf5c["eu_x_post17"], C_AMBER),
        ("Joint: EU × 0% Threshold", thrc["eu_x_freq0"], C_PURPLE),
        ("Joint: EU × FDAAA 2017", thrc["eu_x_fdaaa17"], C_PURPLE),
        ("Joint: EU × Start ≥ 2017", thrc["eu_x_post17"], C_PURPLE),
        ("Non-EU RU/UA × 2020–24", t3c["ru_x_20_24"], C_SLATE),
    ]
    yp = np.arange(len(items))[::-1]
    for i, (_lbl, t, col) in enumerate(items):
        v = 100 * t["per_10pp_coef"]
        ci = _ci10_half(t)
        ax.errorbar(v, yp[i], xerr=ci, fmt="o", color=col, markersize=5.5, capsize=2.8, lw=1.5)
        ax.text(v + ci + 0.25, yp[i], fmt_p(t["p"]), va="center", ha="left", fontsize=7.4, color="#222222")
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([x[0] for x in items], fontsize=7.7)
    ax.set_xlim(-6.5, 10.6)
    ax.set_xlabel("Within-Program Shift per +10 pp Share (pp, 95% CI)")
    ax.set_title("B. Period Shifts & Joint 2017 Overlap\n(Overlapping Regimes Not Individually Separable)", pad=10)

    # Panel C: FDAAA Final Rule Reporting-Threshold Shift
    ax = axes[2]
    reg = blk_c["regime_by_prim_comp_year"]
    yrs = [r["year"] for r in reg]
    f0 = [100 * r["freq0_share"] for r in reg]
    f5 = [100 * r["freq5_share"] for r in reg]
    sh = blk_c["fdaaa_jan2017_structural_shift"]
    ax.plot(yrs, f5, "-o", color=C_BLUE, lw=1.8, markersize=4.8,
            label=f"5% Threshold ({sh['pre_fdaaa_freq5_pct']:.1f}% → {sh['post_fdaaa_freq5_pct']:.1f}%)")
    ax.plot(yrs, f0, "-s", color=C_VERM, lw=1.8, markersize=4.8,
            label=f"0% Threshold ({sh['pre_fdaaa_freq0_pct']:.1f}% → {sh['post_fdaaa_freq0_pct']:.1f}%, {sh['freq0_jump_ratio']}×)")
    ax.axvline(2017.05, color=C_GREEN, lw=1.5, ls=":")
    ax.text(2017.25, 24, "42 CFR Part 11\nJan 18, 2017", color=C_GREEN, fontsize=7.9, fontweight="bold")
    ax.set_xlabel("Trial Primary Completion Year")
    ax.set_ylabel("Share of Completed MRCTs (%)")
    ax.set_ylim(0, 96)
    ax.set_title("C. Reporting-Threshold Shift Around 2017\n(0% vs. 5% Frequency Threshold)", pad=10)
    ax.legend(loc="center left", bbox_to_anchor=(0.02, 0.56), frameon=True, framealpha=0.95, fontsize=7.6)

    save_dual(fig, "figS2_post2017_temporal_overlap")


def make_figS3_war2022_footprints(econ: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(14.6, 5.4))
    fig.subplots_adjust(wspace=0.48)
    blk_d = econ["block_d_war2022_shock"]
    reg = blk_d["all_registered_war_2017_2025"]

    # Panel A: All-Registered Participation vs Results-Posted Subsample
    ax = axes[0]
    ann_reg = reg["annual_participation_2017_2025"]
    yrs_r = [r["year"] for r in ann_reg]
    ann_res = [r for r in blk_d["annual_regional_shares_2015_2024"] if r["year"] >= 2017]
    ax.plot(yrs_r, [r["pct_mrct_with_ru_ua"] for r in ann_reg], "-s", color=C_VERM, lw=2.0, markersize=5.8, label="All-Registered: ≥1 RU/UA Site")
    ax.plot(yrs_r, [r["pct_mrct_with_ru"] for r in ann_reg], "-o", color=C_BLUE, lw=1.7, markersize=5.0, label="All-Registered: ≥1 Russia Site")
    ax.plot(yrs_r, [r["pct_mrct_with_ua"] for r in ann_reg], "-^", color=C_AMBER, lw=1.7, markersize=5.0, label="All-Registered: ≥1 Ukraine Site")
    ax.plot([r["year"] for r in ann_res], [r["all_any_ru_ua_trial_pct"] for r in ann_res], ":d", color=C_SLATE, lw=1.5, markersize=4.5, label="Results-Posted Subsample (Censored)")
    ax.axvline(2022.15, color="black", lw=1.3, ls="--")
    ax.text(2022.28, 26, "Feb 24, 2022", fontsize=8.0, fontweight="bold")
    ax.set_xlabel("Trial Start Year")
    ax.set_ylabel("MRCTs with ≥1 Country Site (%)")
    ax.set_xlim(2016.6, 2025.4)
    ax.set_ylim(-2, 58)
    ax.set_title(
        f"A. All-Registered MRCT Footprints (2017–2025)\n(N={reg['sample_counts']['mrct_ge5sites_ge3countries_ge50enroll']:,} MRCTs from 20,649 Trials)",
        pad=10,
    )
    ax.legend(loc="upper right", frameon=True, framealpha=0.95, fontsize=7.6)

    # Panel B: Within-Sponsor Post-2022 Site-Share Shifts (Uncensored Cohort)
    ax = axes[1]
    shift = reg["within_sponsor_postwar_shift_2017_2025"]
    oos = reg["oos_did_2017_19_to_2020_25"]
    dests = [
        ("Russia / Ukraine", "ru_ua_strict_sh", C_VERM),
        ("Latin America", "latam_sh", C_GREEN),
        ("Emerging Asia", "asia_sh", C_GREEN),
        ("Other Regions", "other_sh", C_AMBER),
        ("United States", "us_sh", C_BLUE),
        ("Western Europe / Dev", "we_sh", C_SLATE),
        ("EU Eastern Europe", "eu_east_sh", C_SLATE),
    ]
    yp = np.arange(len(dests))[::-1]
    for i, (_lbl, k, col) in enumerate(dests):
        t = shift[k]["terms"]["post_war_2022"]
        v = 100 * t["coef"]
        ci = 100 * (t["ci95_hi"] - t["coef"])
        ax.barh(yp[i], v, color=col, alpha=0.82, height=0.56)
        ax.errorbar(v, yp[i], xerr=ci, fmt="none", ecolor="black", capsize=3, lw=1.3)
        ax.text(max(v + ci + 0.16, 0.25), yp[i], f"{v:+.2f} pp ({fmt_p(t['p'])})", va="center", ha="left", fontsize=7.6)
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([d[0] for d in dests], fontsize=8.2)
    ax.set_xlim(-4.8, 5.4)
    ax.set_xlabel("Within-Sponsor Post-2022 Site-Share Shift (pp, 95% CI)")
    us_o = oos["us_sh"]["terms"]["exp_x_postwar"]
    ax.set_title(
        f"B. Uncensored Within-Sponsor Period Shifts (N={shift['ru_ua_strict_sh']['n']:,})\n(OOS Exposure U.S. DiD = {us_o['coef']:+.2f}, {fmt_p(us_o['p'])}; Null)",
        pad=10,
    )

    save_dual(fig, "figS3_war2022_all_registered_footprints")


def make_figS4_exploratory_openfda(g2: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(15.4, 5.6), gridspec_kw={"width_ratios": [1.0, 1.45]})
    fig.subplots_adjust(wspace=0.58)

    # Panel A: Descriptive Pre-Approval & Post-Approval Bins
    ax = axes[0]
    desc = g2["descriptive_by_ee_tertile_pre_2005_2024"]
    bins_order = [("EE_0pct", "EE = 0%"), ("EE_0_15pct", "0% < EE < 15%"), ("EE_ge15pct", "EE ≥ 15%")]
    x = np.arange(len(bins_order))
    w = 0.25
    act_oth = [100 * (desc[k]["mean_pre_act_oth"] or 0) for k, _ in bins_order]
    bw_pct = [desc[k]["boxed_warning_pct"] or 0 for k, _ in bins_order]
    us_ser = [desc[k]["us_serious_share_pct"] or 0 for k, _ in bins_order]

    ax.bar(x - w, act_oth, width=w, color=C_BLUE, alpha=0.85, label="Pivotal Active Non-Serious AE (%)")
    ax.bar(x, us_ser, width=w, color=C_VERM, alpha=0.85, label="US FAERS Serious Share (%)")
    ax.bar(x + w, bw_pct, width=w, color=C_AMBER, alpha=0.85, label="FDA Boxed Warning (%)")
    for i in range(len(bins_order)):
        ax.text(x[i] - w, act_oth[i] + 1.2, f"{act_oth[i]:.1f}%", ha="center", fontsize=7.5)
        ax.text(x[i], us_ser[i] + 1.2, f"{us_ser[i]:.1f}%", ha="center", fontsize=7.5)
        ax.text(x[i] + w, bw_pct[i] + 1.2, f"{bw_pct[i]:.1f}%", ha="center", fontsize=7.5)
    ax.set_xticks(x)
    ax.set_xticklabels([f"{lbl}\n(n={desc[k]['n_drugs']})" for k, lbl in bins_order])
    ax.set_ylabel("Percentage (%)")
    ax.set_ylim(0, max(max(act_oth), max(us_ser), max(bw_pct)) + 20)
    ax.set_title("A. Exploratory Pre-Approval EE-Share Bins\nvs. FDA Label & FAERS Profiles", pad=10)
    ax.legend(loc="upper right", frameon=True, framealpha=0.95, fontsize=7.6)

    # Panel B: Adjusted t-Statistics (Exploratory Hypothesis-Generating Only)
    ax = axes[1]
    fs = g2["first_stage_molecule_level_check"]
    dfda = g2["drugsfda_labeling_supplements"]
    lbl = g2["fda_label_warnings"]
    faers = g2["faers_pharmacovigilance"]
    items = [
        ("First Stage: Pivotal Active AE", fs["pre_act_oth_on_pre_ee_sh"], C_BLUE),
        ("First Stage: Pivotal Placebo AE", fs["pre_ctrl_oth_on_pre_ee_sh"], C_BLUE),
        ("Drugs@FDA: log(Labeling / Yr)", dfda["log_labeling_per_yr_ee"], C_VERM),
        ("Drugs@FDA: log(Labeling 5-Yr)", dfda["log_labeling_5yr_ee"], C_VERM),
        ("Drugs@FDA: Labeling Share", dfda["labeling_share_ee"], C_VERM),
        ("Drugs@FDA: Any Safety/REMS", dfda["any_safety_rems_ee"], C_VERM),
        ("FDA Label: Boxed Warning", lbl["has_boxed_warning_ee"], C_AMBER),
        ("FDA Label: log(AR Text Len)", lbl["log_adverse_reactions_chars_ee"], C_AMBER),
        ("FAERS (No Denom): US Serious Share", faers["us_serious_share_ee"], C_PURPLE),
        ("FAERS (No Denom): US/Non-US LOR", faers["us_vs_nonus_nonser_lor_ee"], C_PURPLE),
        ("FAERS (No Denom): log(US Non-Ser/Yr)", faers["log_us_nonserious_per_yr_ee"], C_PURPLE),
    ]
    yp = np.arange(len(items))[::-1]
    for i, (_name, rec, col) in enumerate(items):
        t = rec.get("terms", {}).get("pre_ee_sh", {})
        if not t:
            continue
        tstat = t["t"]
        t_crit = float((t["ci95_hi"] - t["coef"]) / max(1e-9, t["se"]))
        ax.errorbar(tstat, yp[i], xerr=t_crit, fmt="o", color=col, markersize=5.8, capsize=2.8, lw=1.5)
        ax.text(
            max(tstat + t_crit + 0.2, 2.3) if tstat < 0 else (tstat + t_crit + 0.2), yp[i],
            f"10pp={0.10*t['coef']:+.3f} ({fmt_p(t['p'])}, n={rec['n']})",
            va="center", ha="left", fontsize=7.3, color="#222222",
        )
    ax.axvline(0, color="black", lw=1.0)
    ax.axvspan(-1.99, 1.99, color="#E0E0E0", alpha=0.35, label="Null Band (p > 0.05)")
    ax.set_yticks(yp)
    ax.set_yticklabels([x[0] for x in items], fontsize=7.9)
    ax.set_xlim(-7.2, 10.2)
    ax.set_xlabel("Adjusted t-Statistic for Pivotal EE Share (±t_0.975 band)")
    ax.set_title(
        f"B. Exploratory FDA Label & FAERS Associations (N={g2['linkage_audit']['with_pre_approval_p3_2005_2024']} Drugs)\n"
        "(Hypothesis-Generating Only; FAERS Lacks Exposed Denominators)",
        pad=10,
    )
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=1, frameon=True, framealpha=0.95, fontsize=7.8)

    save_dual(fig, "figS4_exploratory_openfda_faers")


def main() -> int:
    econ = json.loads((RES_DIR / "d30_econometrics_results.json").read_text(encoding="utf-8"))
    sens = json.loads((RES_DIR / "08_reporting_sensitivity.json").read_text(encoding="utf-8"))
    meddra_sum = json.loads((DATA_DIR / "meddra_soc_abs_summary.json").read_text(encoding="utf-8"))
    g2 = json.loads((RES_DIR / "d30_gate2_openfda_results.json").read_text(encoding="utf-8"))

    # Clean superseded legacy v2/v3 figure files so figures/ contains only verified v4 main + SI figures
    legacy_stems = [
        "fig1_twin_trial_identification",
        "fig2_binscatter_and_disease_breadth",
        "fig3_post2017_regulatory_convergence",
        "fig4_war2022_and_accrual_bounds",
        "fig5_gate2_openfda_faers",
    ]
    for stem in legacy_stems:
        for ext in (".png", ".pdf"):
            p = FIG_DIR / f"{stem}{ext}"
            if p.exists():
                p.unlink()

    print("[START] Generating 4 JCE Main Figures + 4 Supplementary Figures (300 DPI PNG + vector PDF)...", flush=True)
    make_fig1_main_counterfactuals_and_specs(econ, sens)
    make_fig2_support_spline_and_weights(sens)
    make_fig3_meddra_fourstate_and_bounds(sens, meddra_sum)
    make_fig4_tost_equivalence(econ, sens)
    make_figS1_ta_and_accrual(econ)
    make_figS2_post2017_overlap(econ)
    make_figS3_war2022_footprints(econ)
    make_figS4_exploratory_openfda(g2)
    print("[DONE] All 8 JCE v4 figures generated.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
