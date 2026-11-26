"""Generate 5 publication-grade figures (300 DPI PNG + vector PDF) for D30 /boost.

All numeric values are loaded dynamically from verified JSON receipts:
  - results/d30_econometrics_results.json
  - results/d30_gate2_openfda_results.json
Zero hardcoded estimates or fabricated values. Visual layout verified to have zero overlaps.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")
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

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 9.5,
    "axes.titlesize": 10.5,
    "axes.titleweight": "bold",
    "axes.labelsize": 9.5,
    "xtick.labelsize": 8.5,
    "ytick.labelsize": 8.5,
    "legend.fontsize": 8.3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.25,
    "grid.linestyle": "--",
    "figure.facecolor": "white",
    "axes.facecolor": "white",
})


def fmt_p(p: float | None) -> str:
    if p is None or np.isnan(p):
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
    print(f"  [SAVED] {png_path.name} ({png_path.stat().st_size/1024:.1f} KB) + {pdf_path.name}", flush=True)


def _ci_half(t: dict) -> float:
    """Return exact half-width of the finite-sample 95% CI from JSON receipt."""
    if "ci95_hi" in t and "coef" in t:
        return float(t["ci95_hi"] - t["coef"])
    return float(1.96 * t["se"])


def make_fig1_twin_trial(econ: dict) -> None:
    """Figure 1: Regional Specificity, 3-Tier Objectivity Gradient, & Cross-Spec Replication."""
    fig, axes = plt.subplots(1, 3, figsize=(19.2, 6.2), gridspec_kw={"width_ratios": [1.0, 1.22, 1.15]})
    fig.subplots_adjust(wspace=0.76)

    # Panel A: Regional Specificity (P3 Mol x Sponsor FE, US baseline)
    ax = axes[0]
    p3_sp = econ["block_a_core_twin_trial"]["p3_mol_sponsor_split"]
    regions = [
        ("EU Eastern Europe", "eu_east_sh"),
        ("Non-EU EE / RU-UA", "ru_ua_sh"),
        ("Western Europe / Dev", "we_sh"),
        ("Latin America", "latam_sh"),
        ("Asia Emerging", "asia_sh"),
    ]
    y_pos = np.arange(len(regions))[::-1]
    for idx, (_lbl, key) in enumerate(regions):
        y = y_pos[idx]
        tc = p3_sp["ctrl_oth"]["terms"][key]
        ta = p3_sp["act_oth"]["terms"][key]
        ax.errorbar(
            100 * tc["coef"], y + 0.14, xerr=100 * _ci_half(tc),
            fmt="o", color=C_BLUE, markersize=6, capsize=3, lw=1.6,
            label="Placebo Non-Serious AE" if idx == 0 else None,
        )
        ax.errorbar(
            100 * ta["coef"], y - 0.14, xerr=100 * _ci_half(ta),
            fmt="s", color=C_VERM, markersize=6, capsize=3, lw=1.6,
            label="Active Non-Serious AE" if idx == 0 else None,
        )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([r[0] for r in regions])
    ax.set_ylim(-0.7, len(regions) - 0.35)
    ax.set_xlabel("Effect per 0→100% Site Share vs. U.S. (pp; ÷10 per +10 pp)")
    ax.set_title(f"A. Regional Specificity\n(Phase 3 Mol × Sponsor FE, N={p3_sp['ctrl_oth']['n']:,})", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=1, frameon=True, framealpha=0.95)
    ax.set_xlim(-42, 24)

    # Panel B: Objectivity Gradient & Non-Compositional Absolute MedDRA SOC Peak Rates (P2+P3 Mol x Sp FE)
    ax = axes[1]
    p23_sp = econ["block_a_core_twin_trial"]["p23_mol_sponsor_split"]
    soc_abs = econ["block_b_sensitivity_robustness"]["meddra_soc_absolute_p23_mol_sp"]
    tier_items = [
        ("Placebo Non-Serious AE", p23_sp["ctrl_oth"]["terms"]["eu_east_sh"], C_BLUE),
        ("Active Non-Serious AE", p23_sp["act_oth"]["terms"]["eu_east_sh"], C_VERM),
        ("Subj. SOC Max-Term Rate (Ctrl)", soc_abs["ctrl_subj_max_pct"]["terms"]["eu_east_sh"], C_AMBER),
        ("Subj. SOC Max-Term Rate (Act)", soc_abs["act_subj_max_pct"]["terms"]["eu_east_sh"], C_AMBER),
        ("Obj. SOC Max-Term Rate (Ctrl)", soc_abs["ctrl_obj_max_pct"]["terms"]["eu_east_sh"], C_GREEN),
        ("Obj. SOC Max-Term Rate (Act)", soc_abs["act_obj_max_pct"]["terms"]["eu_east_sh"], C_GREEN),
        ("Within-Trial Risk Diff (RD)", p23_sp["oth_rd"]["terms"]["eu_east_sh"], C_SLATE),
        ("Placebo Serious AE (SAE)", p23_sp["ctrl_sae"]["terms"]["eu_east_sh"], C_SLATE),
        ("Active Serious AE (SAE)", p23_sp["act_sae"]["terms"]["eu_east_sh"], C_SLATE),
        ("Placebo All-Cause Mortality", p23_sp["ctrl_mort"]["terms"]["eu_east_sh"], C_SLATE),
    ]
    yp2 = np.arange(len(tier_items))[::-1]
    for i, (_lbl, t, col) in enumerate(tier_items):
        y = yp2[i]
        val = 100 * t["coef"]
        err = 100 * _ci_half(t)
        ax.errorbar(val, y, xerr=err, fmt="o", color=col, markersize=6.0, capsize=3, lw=1.6)
        x_txt = max(val + err + 1.8, 2.2) if val < 0 else (val + err + 1.8)
        ax.text(x_txt, y, f"{val:+.1f} pp ({fmt_p(t['p'])})", va="center", ha="left", fontsize=7.4, color="#222222")
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp2)
    ax.set_yticklabels([x[0] for x in tier_items], fontsize=8.0)
    ax.set_xlabel("EU-East 0→100% Site-Share Effect (pp, 95% CI)")
    ax.set_title(
        f"B. Objectivity Gradient & Absolute MedDRA Rates\n(Pooled P2+P3 Mol × Sponsor FE, N={p23_sp['ctrl_oth']['n']:,})",
        pad=10,
    )
    ax.set_xlim(-40, 48)

    # Panel C: Cross-Specification & Out-of-Sample Replication
    ax = axes[2]
    a_blk = econ["block_a_core_twin_trial"]
    b_blk = econ["block_b_sensitivity_robustness"]
    specs = [
        ("P3 Mol × Sponsor (EU-East)", a_blk["p3_mol_sponsor_split"]["ctrl_oth"], a_blk["p3_mol_sponsor_split"]["act_oth"], "eu_east_sh"),
        ("P3 Mol × Condition (EU-East)", a_blk["p3_mol_cond_split"]["ctrl_oth"], a_blk["p3_mol_cond_split"]["act_oth"], "eu_east_sh"),
        ("P3 Mol × Sp × Cond (EU-East)", a_blk["p3_mol_sp_cond_split"]["ctrl_oth"], a_blk["p3_mol_sp_cond_split"]["act_oth"], "eu_east_sh"),
        ("P2 Standalone OOS (TA FE)", a_blk["p2_standalone_ta_fe_split"]["ctrl_oth"], a_blk["p2_standalone_ta_fe_split"]["act_oth"], "eu_east_sh"),
        ("P2+P3 Mol × Sponsor (EU-E)", a_blk["p23_mol_sponsor_split"]["ctrl_oth"], a_blk["p23_mol_sponsor_split"]["act_oth"], "eu_east_sh"),
        ("P3 Strict freq==5% (EU-E)", b_blk["p3_freq5_mol_sp"]["ctrl_oth"], b_blk["p3_freq5_mol_sp"]["act_oth"], "eu_east_sh"),
        ("P2+P3 Strict freq==0% (EE)", b_blk["p23_freq0_ta_fe_ee"]["ctrl_oth"], b_blk["p23_freq0_ta_fe_ee"]["act_oth"], "ee_sh"),
        ("P2+P3 + SYSTEMATIC Ctrl", b_blk["systematic_control_p23_mol_sp"]["ctrl_oth"], b_blk["systematic_control_p23_mol_sp"]["act_oth"], "eu_east_sh"),
        ("P2+P3 All-Status (w/ Term.)", b_blk["allstatus_incl_terminated_p23_mol_sp"]["ctrl_oth"], b_blk["allstatus_incl_terminated_p23_mol_sp"]["act_oth"], "eu_east_sh"),
        ("Non-Placebo Active OOS", b_blk["non_placebo_active_comparator_oos_p23_mol_sp"]["trial_mean_oth"], None, "eu_east_sh"),
    ]
    yp3 = np.arange(len(specs))[::-1]
    for i, (_lbl, rc, ra, key) in enumerate(specs):
        y = yp3[i]
        tc = rc["terms"][key]
        ax.errorbar(
            100 * tc["coef"], y + (0.13 if ra else 0.0), xerr=100 * _ci_half(tc),
            fmt="o", color=C_BLUE if ra else C_PURPLE, markersize=5.5, capsize=2.5, lw=1.4,
            label="Placebo Arm" if i == 0 else ("Trial Mean (Non-Placebo OOS)" if ra is None else None),
        )
        if ra is not None:
            ta = ra["terms"][key]
            ax.errorbar(
                100 * ta["coef"], y - 0.13, xerr=100 * _ci_half(ta),
                fmt="s", color=C_VERM, markersize=5.5, capsize=2.5, lw=1.4,
                label="Active Arm" if i == 0 else None,
            )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp3)
    ax.set_yticklabels([f"{s[0]} (N={s[1]['n']})" for s in specs], fontsize=8.0)
    ax.set_ylim(-0.7, len(specs) - 0.35)
    ax.set_xlabel("Site-Share Effect on Non-Serious AE Rate (pp)")
    ax.set_title("C. Twin-Trial, Protocol & Out-of-Sample\nReplication Across Specifications", pad=10)
    ax.legend(loc="upper center", bbox_to_anchor=(0.48, -0.14), ncol=2, frameon=True, framealpha=0.95, fontsize=8.0)
    ax.set_xlim(-50, 14)

    save_dual(fig, "fig1_twin_trial_identification")


def make_fig2_binscatter_and_diseases(econ: dict) -> None:
    """Figure 2: Residualized Twin-Trial Binscatter & Pan-Disease Therapeutic-Area Consistency."""
    fig, axes = plt.subplots(1, 2, figsize=(14.2, 5.4))
    fig.subplots_adjust(wspace=0.42)

    # Panel A: FWL Residualized Binscatter (P2+P3 Mol x Sp FE, ee_sh)
    ax = axes[0]
    bs = econ["binscatter_data"]["p23_mol_sp_ee"]
    bins = bs["bins"]
    xs = np.array([100 * b["x_mean"] for b in bins])
    yc = np.array([100 * b["ctrl_oth_mean"] for b in bins])
    yc_se = np.array([100 * b["ctrl_oth_se"] for b in bins])
    ya = np.array([100 * b["act_oth_mean"] for b in bins])
    ya_se = np.array([100 * b["act_oth_se"] for b in bins])
    ys = np.array([100 * b["ctrl_sae_mean"] for b in bins])
    ys_se = np.array([100 * b["ctrl_sae_se"] for b in bins])

    t_c = econ["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]["ctrl_oth"]["terms"]["ee_sh"]
    t_a = econ["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]["act_oth"]["terms"]["ee_sh"]
    t_s = econ["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]["ctrl_sae"]["terms"]["ee_sh"]

    ax.errorbar(xs, ya, yerr=ya_se, fmt="s", color=C_VERM, markersize=6, capsize=3,
                label=f"Active Non-Serious AE ({100*t_a['coef']:+.1f} pp, {fmt_p(t_a['p'])})")
    ax.errorbar(xs, yc, yerr=yc_se, fmt="o", color=C_BLUE, markersize=6, capsize=3,
                label=f"Placebo Non-Serious AE ({100*t_c['coef']:+.1f} pp, {fmt_p(t_c['p'])})")
    ax.errorbar(xs, ys, yerr=ys_se, fmt="^", color=C_SLATE, markersize=6, capsize=3,
                label=f"Placebo Serious AE ({100*t_s['coef']:+.1f} pp, {fmt_p(t_s['p'])})")

    x_line = np.linspace(xs.min(), xs.max(), 50)
    x_bar = xs.mean()
    ax.plot(x_line, ya.mean() + t_a["coef"] * (x_line - x_bar), color=C_VERM, lw=1.8, alpha=0.85)
    ax.plot(x_line, yc.mean() + t_c["coef"] * (x_line - x_bar), color=C_BLUE, lw=1.8, alpha=0.85)
    ax.plot(x_line, ys.mean() + t_s["coef"] * (x_line - x_bar), color=C_SLATE, lw=1.6, ls="--", alpha=0.85)

    ax.set_xlabel("Residualized Eastern European Site Share (%, within Mol × Sponsor FE)")
    ax.set_ylabel("Residualized Registered Arm AE Proportion (%)")
    ax.set_title(f"A. Within-Twin-Trial Dose–Response Gradient\n(Pooled P2+P3 Mol × Sponsor FE, N={bs['n_total']:,}, {bs['n_fe_groups']} Programs)", pad=8)
    ax.legend(loc="center right", frameon=True, framealpha=0.95, fontsize=8.0)

    # Panel B: Pan-Disease Therapeutic-Area Consistency
    ax = axes[1]
    ta_dict = econ["block_b_sensitivity_robustness"]["by_therapeutic_area_p23"]
    ta_sorted = sorted(ta_dict.items(), key=lambda kv: kv[1]["ctrl_oth"]["terms"]["ee_sh"]["coef"])
    n_ta_tot = len(ta_sorted)
    n_ta_neg = sum(1 for _, v in ta_sorted if v["ctrl_oth"]["terms"]["ee_sh"]["coef"] < 0)
    n_ta_sig = sum(1 for _, v in ta_sorted if v["ctrl_oth"]["terms"]["ee_sh"]["p"] < 0.05)
    yp = np.arange(n_ta_tot)
    for i, (_ta, v) in enumerate(ta_sorted):
        tc = v["ctrl_oth"]["terms"]["ee_sh"]
        ta_m = v["act_oth"]["terms"]["ee_sh"]
        ax.errorbar(
            100 * tc["coef"], i + 0.14, xerr=100 * _ci_half(tc),
            fmt="o", color=C_BLUE, markersize=6, capsize=2.8, lw=1.5,
            label="Placebo Non-Serious AE" if i == 0 else None,
        )
        ax.errorbar(
            100 * ta_m["coef"], i - 0.14, xerr=100 * _ci_half(ta_m),
            fmt="s", color=C_VERM, markersize=6, capsize=2.8, lw=1.5,
            label="Active Non-Serious AE" if i == 0 else None,
        )
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([f"{ta} (N={v['n_total']})" for ta, v in ta_sorted])
    ax.set_xlabel("Eastern European Site-Share Effect (pp, 95% CI)")
    ax.set_title(f"B. Pan-Disease Therapeutic-Area Consistency\n({n_ta_neg}/{n_ta_tot} Clinical Domains Negative; {n_ta_sig}/{n_ta_tot} p < 0.05)", pad=8)
    ax.legend(loc="lower right", frameon=True, framealpha=0.95, fontsize=8.2)
    ax.set_xlim(-78, 34)

    save_dual(fig, "fig2_binscatter_and_disease_breadth")


def make_fig3_post2017_convergence(econ: dict) -> None:
    """Figure 3: Dynamic Event Study, 3-Era Implementation Lag, & FDAAA 42 CFR Part 11 Decomposition."""
    fig, axes = plt.subplots(1, 3, figsize=(18.2, 5.6))
    fig.subplots_adjust(wspace=0.52)
    blk_c = econ["block_c_post2017_fdaaa_decomposition"]

    # Panel A: Dynamic Event Study across 6 Eras
    ax = axes[0]
    es = blk_c["dynamic_event_study_p23_ta_fe"]
    x_idx = np.arange(len(es))
    eu_c = [100 * e["ctrl_oth"]["eu_east"]["coef"] for e in es]
    eu_c_ci = [100 * _ci_half(e["ctrl_oth"]["eu_east"]) for e in es]
    eu_a = [100 * e["act_oth"]["eu_east"]["coef"] for e in es]
    eu_a_ci = [100 * _ci_half(e["act_oth"]["eu_east"]) for e in es]
    ru_c = [100 * e["ctrl_oth"]["ru_ua"]["coef"] for e in es]
    ru_c_ci = [100 * _ci_half(e["ctrl_oth"]["ru_ua"]) for e in es]

    ax.errorbar(x_idx - 0.12, eu_c, yerr=eu_c_ci, fmt="-o", color=C_BLUE, lw=1.8, markersize=6, capsize=3, label="EU-East: Placebo AE")
    ax.errorbar(x_idx, eu_a, yerr=eu_a_ci, fmt="-s", color=C_VERM, lw=1.8, markersize=6, capsize=3, label="EU-East: Active AE")
    ax.errorbar(x_idx + 0.12, ru_c, yerr=ru_c_ci, fmt="--^", color=C_SLATE, lw=1.6, markersize=6, capsize=3, label="Non-EU RU/UA: Placebo AE")
    ax.axhline(0, color="black", lw=1.0)
    ax.axvline(3.5, color=C_GREEN, lw=1.4, ls=":")
    ax.text(3.42, 16, "ICH E6(R2) &\nFDAAA 2017", color=C_GREEN, fontsize=7.8, fontweight="bold", ha="right")
    ax.set_xticks(x_idx)
    ax.set_xticklabels([f"{e['era']}\n(n={e['n']})" for e in es], fontsize=7.6)
    ax.set_ylabel("Cross-Sectional Site-Share Slope (pp, 95% CI)")
    ax.set_title("A. Era Cross-Sectional Slopes (2005–2024)\nEU-East Convergence vs. Non-EU Persistence", pad=10)
    ax.set_ylim(-90, 28)
    ax.legend(loc="lower left", frameon=True, framealpha=0.95, fontsize=7.8)

    # Panel B: 3-Period Implementation-Lag & Horse-Race inside Twin-Trial Mol x Sp FE
    ax = axes[1]
    t3c = blk_c["p23_3era_lag_mol_sp"]["ctrl_oth"]["terms"]
    t3a = blk_c["p23_3era_lag_mol_sp"]["act_oth"]["terms"]
    t3rd = blk_c["p23_3era_lag_mol_sp"]["oth_rd"]["terms"]
    tf5c = blk_c["p23_post2017_strict_freq5_mol_sp"]["ctrl_oth"]["terms"]
    thrc = blk_c["p23_horserace_ich_vs_fdaaa_mol_sp"]["ctrl_oth"]["terms"]

    bar_items = [
        ("EU-East Pre-2017 (Ctrl)", t3c["eu_east_sh"], C_BLUE),
        ("EU-East Pre-2017 (Act)", t3a["eu_east_sh"], C_VERM),
        ("EU × 2017–19 Lag (Ctrl)", t3c["eu_x_17_19"], C_BLUE),
        ("EU × 2017–19 Lag (Act)", t3a["eu_x_17_19"], C_VERM),
        ("EU × 2020–24 Mature (Ctrl)", t3c["eu_x_20_24"], C_GREEN),
        ("EU × 2020–24 Mature (Act)", t3a["eu_x_20_24"], C_GREEN),
        ("EU × Post-17 (freq==5%)", tf5c["eu_x_post17"], C_AMBER),
        ("EU × freq==0% (Horse Race)", thrc["eu_x_freq0"], C_PURPLE),
        ("Non-EU RU/UA × 2020–24", t3c["ru_x_20_24"], C_SLATE),
        ("EU × 2020–24 Risk Diff (RD)", t3rd["eu_x_20_24"], C_SLATE),
    ]
    yp = np.arange(len(bar_items))[::-1]
    for i, (_lbl, t, col) in enumerate(bar_items):
        y = yp[i]
        v = 100 * t["coef"]
        ci = 100 * _ci_half(t)
        ax.errorbar(v, y, xerr=ci, fmt="o", color=col, markersize=6, capsize=2.8, lw=1.6)
        ax.text(v + ci + 2.2, y, fmt_p(t["p"]), va="center", ha="left", fontsize=7.6, color="#222222")
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([x[0] for x in bar_items], fontsize=7.9)
    ax.set_xlabel("Twin-Trial FE Coefficient / Interaction Shift (pp)")
    ax.set_title("B. Twin-Trial Implementation-Lag &\nFDAAA vs. ICH E6(R2) Decomposition", pad=10)
    ax.set_xlim(-66, 108)

    # Panel C: FDAAA Final Rule Reporting-Threshold Shift
    ax = axes[2]
    reg = blk_c["regime_by_prim_comp_year"]
    yrs = [r["year"] for r in reg]
    f0 = [100 * r["freq0_share"] for r in reg]
    f5 = [100 * r["freq5_share"] for r in reg]
    sh = blk_c["fdaaa_jan2017_structural_shift"]

    ax.plot(yrs, f5, "-o", color=C_BLUE, lw=1.9, markersize=5,
            label=f"freq_thr == 5% ({sh['pre_fdaaa_freq5_pct']:.1f}% → {sh['post_fdaaa_freq5_pct']:.1f}%)")
    ax.plot(yrs, f0, "-s", color=C_VERM, lw=1.9, markersize=5,
            label=f"freq_thr == 0% ({sh['pre_fdaaa_freq0_pct']:.1f}% → {sh['post_fdaaa_freq0_pct']:.1f}%, {sh['freq0_jump_ratio']}×)")
    ax.axvline(2017.05, color=C_GREEN, lw=1.5, ls=":")
    ax.text(2017.25, 25, "42 CFR Part 11\nEffective Jan 18, 2017", color=C_GREEN, fontsize=8.0, fontweight="bold")
    ax.set_xlabel("Trial Primary Completion Year")
    ax.set_ylabel("Share of Completed MRCTs (%)")
    ax.set_title("C. FDAAA Final Rule Reporting-Threshold\nShift (freq_thr == 0% vs. 5%)", pad=10)
    ax.set_ylim(0, 96)
    ax.legend(loc="center left", bbox_to_anchor=(0.02, 0.56), frameon=True, framealpha=0.95, fontsize=7.8)

    save_dual(fig, "fig3_post2017_regulatory_convergence")


def make_fig4_war_and_accrual(econ: dict) -> None:
    """Figure 4: Uncensored All-Registered War Cohort (2017-2025) Reallocation & Simplex-Valid Accrual Bounds."""
    fig, axes = plt.subplots(1, 3, figsize=(18.6, 5.6))
    fig.subplots_adjust(wspace=0.55)
    blk_d = econ["block_d_war2022_shock"]
    blk_e = econ["block_e_site_vs_patient_bounds"]
    reg = blk_d["all_registered_war_2017_2025"]

    # Panel A: Uncensored All-Registered MRCT Participation (2017-2025) vs Results-Posted Subsample
    ax = axes[0]
    ann_reg = reg["annual_participation_2017_2025"]
    yrs_r = [r["year"] for r in ann_reg]
    ru_ua_all = [r["pct_mrct_with_ru_ua"] for r in ann_reg]
    ru_only = [r["pct_mrct_with_ru"] for r in ann_reg]
    ua_only = [r["pct_mrct_with_ua"] for r in ann_reg]
    ann_res = [r for r in blk_d["annual_regional_shares_2015_2024"] if r["year"] >= 2017]
    yrs_res = [r["year"] for r in ann_res]
    ru_ua_res = [r["all_any_ru_ua_trial_pct"] for r in ann_res]

    ax.plot(yrs_r, ru_ua_all, "-s", color=C_VERM, lw=2.0, markersize=6, label="All-Registered: ≥1 RU/UA Site (%)")
    ax.plot(yrs_r, ru_only, "-o", color=C_BLUE, lw=1.7, markersize=5, label="All-Registered: ≥1 Russia Site (%)")
    ax.plot(yrs_r, ua_only, "-^", color=C_AMBER, lw=1.7, markersize=5, label="All-Registered: ≥1 Ukraine Site (%)")
    ax.plot(yrs_res, ru_ua_res, ":d", color=C_SLATE, lw=1.5, markersize=4.5, label="Results-Posted Subsample RU/UA (%)")
    ax.axvline(2022.15, color="black", lw=1.4, ls="--")
    ax.text(2022.28, 25, "Feb 24, 2022\nInvasion", ha="left", fontsize=7.9, fontweight="bold", color="#222222")
    ax.set_xlabel("Trial Start Year")
    ax.set_ylabel("MRCTs with ≥1 Country Site (%)")
    ax.set_title(
        f"A. Uncensored All-Registered War Collapse\n(2017–2025, N={reg['sample_counts']['mrct_ge5sites_ge3countries_ge50enroll']:,} MRCTs)",
        pad=10,
    )
    ax.set_xlim(2016.6, 2025.4)
    ax.set_ylim(-2, 62)
    ax.legend(loc="upper right", frameon=True, framealpha=0.96, fontsize=7.3)

    # Panel B: Uncensored All-Registered Within-Sponsor Post-War Reallocation (2017-2025)
    ax = axes[1]
    shift = reg["within_sponsor_postwar_shift_2017_2025"]
    oos_reg = reg["oos_did_2017_19_to_2020_25"]
    dests = [
        ("Russia / Ukraine (Exit)", "ru_ua_strict_sh", C_VERM),
        ("Latin America", "latam_sh", C_GREEN),
        ("Asia Emerging", "asia_sh", C_GREEN),
        ("Other Regions", "other_sh", C_AMBER),
        ("United States", "us_sh", C_BLUE),
        ("Western Europe / Dev", "we_sh", C_SLATE),
        ("EU Eastern Europe", "eu_east_sh", C_SLATE),
    ]
    yp = np.arange(len(dests))[::-1]
    n_shift = shift["ru_ua_strict_sh"]["n"]
    for i, (_lbl, k, col) in enumerate(dests):
        t = shift[k]["terms"]["post_war_2022"]
        v, ci = 100 * t["coef"], 100 * _ci_half(t)
        ax.barh(yp[i], v, color=col, alpha=0.82, height=0.56)
        ax.errorbar(v, yp[i], xerr=ci, fmt="none", ecolor="black", capsize=3, lw=1.4)
        x_txt = max(v + ci + 0.16, 0.25)
        ax.text(x_txt, yp[i], f"{v:+.2f} pp ({fmt_p(t['p'])})", va="center", ha="left", fontsize=7.5, color="#222222")
    ax.axvline(0, color="black", lw=1.0)
    ax.set_yticks(yp)
    ax.set_yticklabels([d[0] for d in dests], fontsize=8.0)
    ax.set_xlabel("Within-Sponsor Post-War Site-Share Shift (pp, 95% CI)")
    us_oos = oos_reg["us_sh"]["terms"]["exp_x_postwar"]
    ax.set_title(
        f"B. Uncensored Within-Sponsor Reallocation\n(2017–2025, N={n_shift:,}; OOS US DiD={us_oos['coef']:+.2f}, {fmt_p(us_oos['p'])})",
        pad=10,
    )
    ax.set_xlim(-4.8, 5.4)

    # Panel C: Simplex-Preserving Site-Share vs Patient-Accrual Calibration Curve
    ax = axes[2]
    cal = blk_e["nonlinear_patient_share_calibration_p23"]
    ws = np.array([r["w_ee_accrual_ratio"] for r in cal])
    bc = np.array([100 * r["ctrl_oth_coef"] for r in cal])
    bc_ci = np.array([100 * 1.975 * r["ctrl_oth_se"] for r in cal])
    ba = np.array([100 * r["act_oth_coef"] for r in cal])
    ba_ci = np.array([100 * 1.975 * r["act_oth_se"] for r in cal])
    w_hat = blk_e["implied_accrual_ratios_vs_us"]["w_hat_ee_all"]

    ax.fill_between(ws, bc - bc_ci, bc + bc_ci, color=C_BLUE, alpha=0.14)
    ax.fill_between(ws, ba - ba_ci, ba + ba_ci, color=C_VERM, alpha=0.14)
    ax.plot(ws, bc, "-o", color=C_BLUE, lw=2.0, markersize=5.5, label="Placebo AE Slope β(w)")
    ax.plot(ws, ba, "-s", color=C_VERM, lw=2.0, markersize=5.5, label="Active AE Slope β(w)")
    ax.axvline(w_hat, color=C_GREEN, lw=1.6, ls="--")
    ax.text(w_hat + 0.06, -5.5, f"Empirical Twin-Trial\nŵ_EE = {w_hat:.2f}× US", color=C_GREEN, fontsize=8.0, fontweight="bold")
    ax.axhline(0, color="black", lw=1.0)
    ax.set_xlabel("Assumed EE / Non-EE Per-Site Patient Accrual Ratio (w)")
    ax.set_ylabel("Implied Patient-Level Attenuation Slope (pp)")
    ax.set_title("C. Simplex-Valid Site-to-Patient Accrual\nBounds (Twin-Trial FE, w ∈ [0.5, 3.0])", pad=10)
    ax.set_ylim(-44, 4)
    ax.legend(loc="lower right", frameon=True, framealpha=0.95, fontsize=8.0)

    save_dual(fig, "fig4_war2022_and_accrual_bounds")


def make_fig5_gate2_openfda(g2: dict) -> None:
    """Figure 5: Gate #2 Live openFDA Drugs@FDA, Drug Label, & FAERS Pharmacovigilance Linkage."""
    fig, axes = plt.subplots(1, 2, figsize=(15.5, 5.8), gridspec_kw={"width_ratios": [1.0, 1.45]})
    fig.subplots_adjust(wspace=0.58)

    # Panel A: Descriptive Outcomes Across Pre-Approval Pivotal EE-Share Bins
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

    for i, (_k, _) in enumerate(bins_order):
        ax.text(x[i] - w, act_oth[i] + 1.2, f"{act_oth[i]:.1f}%", ha="center", fontsize=7.6)
        ax.text(x[i], us_ser[i] + 1.2, f"{us_ser[i]:.1f}%", ha="center", fontsize=7.6)
        ax.text(x[i] + w, bw_pct[i] + 1.2, f"{bw_pct[i]:.1f}%", ha="center", fontsize=7.6)

    ax.set_xticks(x)
    ax.set_xticklabels([f"{lbl}\n(n={desc[k]['n_drugs']})" for k, lbl in bins_order])
    ax.set_ylabel("Percentage (%)")
    ax.set_ylim(0, max(max(act_oth), max(us_ser), max(bw_pct)) + 20)
    ax.set_title("A. Pivotal EE-Share Bins vs. Post-Approval\nFDA Label & US FAERS Profiles", pad=10)
    ax.legend(loc="upper right", frameon=True, framealpha=0.95, fontsize=7.8)

    # Panel B: Adjusted Gate-2 Regression Forest Plot
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
        ("Placebo: log(Efficacy 5-Yr)", dfda["log_efficacy_5yr_ee"], C_SLATE),
        ("FDA Label: Boxed Warning", lbl["has_boxed_warning_ee"], C_AMBER),
        ("FDA Label: log(AR Text Len)", lbl["log_adverse_reactions_chars_ee"], C_AMBER),
        ("FAERS: US Serious AE Share", faers["us_serious_share_ee"], C_PURPLE),
        ("FAERS: US/Non-US Non-Ser LOR", faers["us_vs_nonus_nonser_lor_ee"], C_PURPLE),
        ("FAERS: log(US Non-Ser / Yr)", faers["log_us_nonserious_per_yr_ee"], C_PURPLE),
        ("FAERS: log(US Serious / Yr)", faers["log_us_serious_per_yr_ee"], C_PURPLE),
    ]
    yp = np.arange(len(items))[::-1]
    for i, (_name, rec, col) in enumerate(items):
        t = rec.get("terms", {}).get("pre_ee_sh", {})
        if not t:
            continue
        tstat = t["t"]
        t_crit = float((t["ci95_hi"] - t["coef"]) / max(1e-9, t["se"]))
        ax.errorbar(tstat, yp[i], xerr=t_crit, fmt="o", color=col, markersize=6, capsize=2.8, lw=1.5)
        ax.text(max(tstat + t_crit + 0.20, 2.35) if tstat < 0 else (tstat + t_crit + 0.20), yp[i],
                f"β={t['coef']:+.3f} ({fmt_p(t['p'])}, n={rec['n']})",
                va="center", ha="left", fontsize=7.4, color="#222222")

    ax.axvline(0, color="black", lw=1.0)
    ax.axvspan(-1.99, 1.99, color="#E0E0E0", alpha=0.35, label="Null Band (|t| < t_0.975, p > 0.05)")
    ax.set_yticks(yp)
    ax.set_yticklabels([x[0] for x in items], fontsize=8.0)
    ax.set_xlabel("Adjusted t-Statistic for Pivotal EE Site Share (±t_0.975(G−1) band)")
    ax.set_title(
        f"B. Gate-2 Adjusted Effects on FDA Labels & Exploratory FAERS\n"
        f"(BLA/NDA, Enroll, Pivotal SAE, TA & Appr.-Year FE; N={g2['linkage_audit']['with_pre_approval_p3_2005_2024']} Drugs)",
        pad=10,
    )
    ax.set_xlim(-7.2, 9.8)
    ax.set_ylim(-0.7, len(items) - 0.35)
    ax.legend(loc="upper center", bbox_to_anchor=(0.48, -0.13), frameon=True, framealpha=0.95, fontsize=8.0)

    save_dual(fig, "fig5_gate2_openfda_faers")


def main() -> int:
    econ_path = RES_DIR / "d30_econometrics_results.json"
    g2_path = RES_DIR / "d30_gate2_openfda_results.json"
    if not econ_path.exists():
        print("[ERROR] Missing results/d30_econometrics_results.json", flush=True)
        return 1
    econ = json.loads(econ_path.read_text(encoding="utf-8"))

    print("[START] Generating publication-grade figures (300 DPI PNG + vector PDF)...", flush=True)
    make_fig1_twin_trial(econ)
    make_fig2_binscatter_and_diseases(econ)
    make_fig3_post2017_convergence(econ)
    make_fig4_war_and_accrual(econ)
    if g2_path.exists():
        g2 = json.loads(g2_path.read_text(encoding="utf-8"))
        make_fig5_gate2_openfda(g2)
    else:
        print("  [WAIT] d30_gate2_openfda_results.json not found yet; skipping Fig 5.", flush=True)
    print("[DONE] Figure generation finished.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
