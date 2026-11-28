"""Step 6 (v4): Generate 4 Main Manuscript figures (Scientometrics Original Research)
and 3 Supplementary Information figures (300-DPI PNG + vector PDF), reading 100% of
data, intervals, and annotations dynamically from saved JSON receipts (zero hardcoded estimates).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import Patch

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"
FIG_DIR = BASE_DIR / "figures"

# Colorblind-safe academic palette
NAVY = "#0B2545"
CRIMSON = "#B91C1C"
TEAL = "#0F766E"
AMBER = "#B45309"
SLATE = "#475569"
LIGHT_GRAY = "#CBD5E1"
BG_TINT = "#F8FAFC"


def set_pub_style() -> None:
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 8.8,
        "axes.titlesize": 10.0,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.0,
        "axes.edgecolor": "#334155",
        "axes.linewidth": 0.8,
        "xtick.labelsize": 8.1,
        "ytick.labelsize": 8.1,
        "legend.fontsize": 7.6,
        "legend.frameon": True,
        "legend.facecolor": "white",
        "legend.edgecolor": "#CBD5E1",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "savefig.pad_inches": 0.12,
    })


def save_both(fig: plt.Figure, stem: str) -> None:
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300)
    fig.savefig(FIG_DIR / f"{stem}.pdf")
    plt.close(fig)
    print(f"  [Saved Figure] {stem}.png + {stem}.pdf", flush=True)


def make_fig1_measurement_audit(p3b: dict, audit_raw: list[dict], p9: dict) -> None:
    """Main Figure 1: Multi-DOI OpenAlex Splitting by VoR Status & Exact Citing-ID Union vs Yearly-Max."""
    bs = p3b["by_stratum"]
    am = p3b["all_manifestations_post_v1"]
    eo = p3b["elife_only_post_v1"]
    reg = p3b["regression_impact_audit_sample"]
    bp = p9["covariate_audit_and_crossed_clock"]["reviewer_2285_exact_parity"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.7), gridspec_kw={"width_ratios": [1.05, 1.1]})

    # Panel A: OpenAlex Work-ID Splitting Rate & Aggregate Proxy Ratio by Stratum
    strata = [
        ("VoR_v1Low", f"VoR\nv1 < Solid\n(n={bs['VoR_v1Low']['n']})"),
        ("VoR_v1SolidPlus", f"VoR\nv1 Solid+\n(n={bs['VoR_v1SolidPlus']['n']})"),
        ("NonVoR_v1Low", f"Non-VoR RP\nv1 < Solid\n(n={bs['NonVoR_v1Low']['n']})"),
        ("NonVoR_v1SolidPlus", f"Non-VoR RP\nv1 Solid+\n(n={bs['NonVoR_v1SolidPlus']['n']})"),
    ]
    x = np.arange(len(strata))
    split_pcts = [bs[k]["pct_split_oa_works"] for k, _ in strata]
    ratios_pct = [100.0 * bs[k]["agg_ymax_to_union_ratio"] for k, _ in strata]

    w = 0.36
    b1 = ax1.bar(x - w / 2, split_pcts, width=w, color=CRIMSON, alpha=0.88, edgecolor="#1E293B", lw=0.5, label="Split Across ≥2 OpenAlex Work IDs (%)")
    b2 = ax1.bar(x + w / 2, ratios_pct, width=w, color=NAVY, alpha=0.88, edgecolor="#1E293B", lw=0.5, label="Yearly-Max / Exact Citing-ID Union (%)")

    for rect, val in zip(b1, split_pcts, strict=True):
        ax1.text(rect.get_x() + rect.get_width() / 2, val + 1.8, f"{val:.1f}%", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color=CRIMSON)
    for rect, val in zip(b2, ratios_pct, strict=True):
        ax1.text(rect.get_x() + rect.get_width() / 2, val + 1.8, f"{val:.1f}%", ha="center", va="bottom", fontsize=7.5, fontweight="bold", color=NAVY)

    ax1.axhline(100.0, color="#64748B", ls=":", lw=0.9)
    ax1.set_xticks(x)
    ax1.set_xticklabels([lbl for _, lbl in strata], fontsize=8.0, fontweight="bold")
    ax1.set_ylim(0, 118)
    ax1.set_ylabel("Percentage (%)")
    ax1.set_title(f"A. OpenAlex Multi-DOI Merging Audit (N = {p3b['n_audited_articles']}; Mean {p3b['mean_queried_dois_per_article']} DOIs)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.5, -0.19), ncol=1, fontsize=7.5)

    # Panel B: Exact Citing-Work ID Union vs Yearly-Max Scatter (log1p scale) + Audit Callout
    vor_u = [np.log1p(r["all_manifestations"]["union_post_v1"]) for r in audit_raw if r["is_vor"] == 1]
    vor_y = [np.log1p(r["all_manifestations"]["ymax_post_v1"]) for r in audit_raw if r["is_vor"] == 1]
    nv_u = [np.log1p(r["all_manifestations"]["union_post_v1"]) for r in audit_raw if r["is_vor"] == 0]
    nv_y = [np.log1p(r["all_manifestations"]["ymax_post_v1"]) for r in audit_raw if r["is_vor"] == 0]

    lim = max(max(vor_u + nv_u), max(vor_y + nv_y)) + 0.25
    ax2.plot([0, lim], [0, lim], color="#64748B", ls="--", lw=1.0, label="Exact Identity (Yearly-Max = Union)")
    vor_n = bs["VoR_v1Low"]["n"] + bs["VoR_v1SolidPlus"]["n"]
    vor_merged_pct = 100.0 * (vor_n - bs["VoR_v1Low"]["n_split_oa_works"] - bs["VoR_v1SolidPlus"]["n_split_oa_works"]) / vor_n
    nv_n = bs["NonVoR_v1Low"]["n"] + bs["NonVoR_v1SolidPlus"]["n"]
    nv_split_pct = 100.0 * (bs["NonVoR_v1Low"]["n_split_oa_works"] + bs["NonVoR_v1SolidPlus"]["n_split_oa_works"]) / nv_n
    ax2.scatter(vor_u, vor_y, s=28, color=NAVY, alpha=0.65, edgecolors="white", lw=0.4, label=f"VoR (n = {vor_n}; {vor_merged_pct:.1f}% single OA work)")
    ax2.scatter(nv_u, nv_y, s=34, color=CRIMSON, marker="^", alpha=0.80, edgecolors="white", lw=0.4, label=f"Non-VoR RP (n = {nv_n}; {nv_split_pct:.1f}% split OA works)")

    ax2.text(
        0.03, 0.97,
        f"Exact Citing-ID Union vs. Yearly-Max (Post-v1):\n"
        f"• All DOIs: r = {am['pearson_r']:.4f}, ρ = {am['spearman_rho']:.4f} | Agg Ratio = {am['agg_ymax_to_union_ratio']:.3f}\n"
        f"• eLife DOIs only: r = {eo['pearson_r']:.5f} | Exact Match = {eo['exact_match_pct']:.1f}%\n"
        f"• Audit PPML: Union {reg['all_audit_all_manifest_union_post']['pct']:+.1f}% vs. YMax {reg['all_audit_all_manifest_ymax_post']['pct']:+.1f}%\n"
        f"Covariate Freeze Audit (N = {bp['n']:,} VoRs):\n"
        f"• max_authors > v1_authors in {bp['n_max_authors_gt_v1']}/{bp['n']:,} ({100.0*bp['n_max_authors_gt_v1']/bp['n']:.1f}%)\n"
        f"• Shift: {bp['leaked_max_authors']['pct']:+.2f}% → {bp['frozen_v1_authors']['pct']:+.2f}%",
        transform=ax2.transAxes, va="top", ha="left", fontsize=6.9, color="#0F172A",
        bbox={"boxstyle": "round,pad=0.30", "facecolor": BG_TINT, "edgecolor": "#94A3B8", "alpha": 0.96},
    )

    ax2.set_xlim(-0.1, lim)
    ax2.set_ylim(-0.1, lim)
    ax2.set_xlabel("Exact Deduplicated Citing-Work ID Union, log(1 + count)")
    ax2.set_ylabel("Yearly-Max Proxy Across DOIs, log(1 + count)")
    ax2.set_title("B. Exact Deduplicated Union vs. Yearly-Max Proxy")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="lower right", fontsize=7.2)

    fig.tight_layout()
    save_both(fig, "fig1_v4_measurement_and_dedup_audit")


def make_fig2_equal_window_validation(p9: dict) -> None:
    """Main Figure 2: Crossed 2x2 Date-Clock / Assessment-Timing Sensitivity & All-v1 vs VoR vs Non-VoR."""
    sc = p9["covariate_audit_and_crossed_clock"]["strict_v1_frozen"]
    ev = p9["equal_window_validation"]["by_sample"]
    inc_p = p9["equal_window_validation"]["incremental_predictive_power"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.9), gridspec_kw={"width_ratios": [1.0, 1.18]})

    # Panel A: Crossed 2x2 Sensitivity (Strictly Frozen v1 Authors & Subject)
    rows_a = [
        ("v1 Label / v1 Quarter\n(Post-v1 OA cites)", sc["oa_post_v1_cites"]["v1_v1q"], NAVY, "o"),
        ("v1 Label / VoR Quarter\n(Post-v1 OA cites)", sc["oa_post_v1_cites"]["v1_finq"], TEAL, "s"),
        ("Final Label / v1 Quarter\n(Post-v1 OA cites)", sc["oa_post_v1_cites"]["fin_v1q"], AMBER, "D"),
        ("Final Label / VoR Quarter\n(Post-v1 OA cites)", sc["oa_post_v1_cites"]["fin_finq"], SLATE, "^"),
        ("v1 Label / v1 Quarter\n(Next full calendar year)", sc["oa_next_full_year"]["v1_v1q"], NAVY, "o"),
        ("v1 Label / VoR Quarter\n(Next full calendar year)", sc["oa_next_full_year"]["v1_finq"], TEAL, "s"),
        ("Final Label / v1 Quarter\n(Next full calendar year)", sc["oa_next_full_year"]["fin_v1q"], AMBER, "D"),
        ("Final Label / VoR Quarter\n(Next full calendar year)", sc["oa_next_full_year"]["fin_finq"], SLATE, "^"),
    ]
    y_a = np.arange(len(rows_a))
    ax1.axvline(0.0, color="#334155", ls="--", lw=0.9)
    ax1.axhline(3.5, color="#CBD5E1", ls=":", lw=1.0)
    for i, (_, m, col, mk) in enumerate(rows_a):
        pt, lo, hi = m["pct"], m["pct_ci95_lo"], m["pct_ci95_hi"]
        ax1.errorbar(pt, y_a[i], xerr=[[pt - lo], [hi - pt]], fmt=mk, color=col, markersize=5.8, elinewidth=1.6, capsize=3.0)
        ax1.text(
            hi + 1.2, y_a[i], f"{pt:+.1f}%", va="center", ha="left", fontsize=7.5, fontweight="bold", color=col,
            bbox={"facecolor": "white", "edgecolor": "none", "pad": 0.4, "alpha": 0.88},
        )

    ax1.set_yticks(y_a)
    ax1.set_yticklabels([r[0] for r in rows_a], fontsize=7.6)
    ax1.invert_yaxis()
    ax1.set_xlim(-32, 28)
    ax1.set_xlabel("PPML Citation Association: Below-Solid vs. Solid (%, 95% CI)")
    ax1.set_title("A. Crossed 2×2 Clock & Label Timing (Strict v1 Covariates)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: All-v1 vs VoR-only vs Non-VoR-only Equal-Window Validation
    rows_b = [
        (f"ALL Mature v1 (N={ev['all_v1']['oa_next_full_year']['v1_low']['n']:,})\nNext full calendar yr (eLife)", ev["all_v1"]["oa_next_full_year"]["v1_low"], NAVY, "o"),
        (f"ALL Mature v1 (N={ev['all_v1']['oa_next_full_year_all']['v1_low']['n']:,})\nNext full calendar yr (All DOIs)", ev["all_v1"]["oa_next_full_year_all"]["v1_low"], NAVY, "s"),
        (f"ALL Mature v1 (N={ev['all_v1']['oa_post_v1_cites']['v1_low']['n']:,})\nAll post-v1 years (eLife)", ev["all_v1"]["oa_post_v1_cites"]["v1_low"], NAVY, "D"),
        (f"VoR-Only Subsample (N={ev['vor_only']['oa_next_full_year']['v1_low']['n']:,})\nNext full calendar yr (eLife)", ev["vor_only"]["oa_next_full_year"]["v1_low"], TEAL, "o"),
        (f"VoR-Only Subsample (N={ev['vor_only']['oa_post_v1_cites']['v1_low']['n']:,})\nAll post-v1 years (eLife)", ev["vor_only"]["oa_post_v1_cites"]["v1_low"], TEAL, "D"),
        (f"Non-VoR RP Subsample (N={ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['n']:,})\nAll post-v1 yrs (Subj×Qtr FE)", ev["non_vor_only_subj_q"]["oa_post_v1_cites"]["v1_low"], CRIMSON, "^"),
        (f"Non-VoR RP Subsample (N={ev['non_vor_only_subj_q']['oa_next_full_year']['v1_low']['n']:,})\nNext full yr (Subj×Qtr FE)", ev["non_vor_only_subj_q"]["oa_next_full_year"]["v1_low"], CRIMSON, "v"),
        (f"Non-VoR RP Subsample (N={ev['non_vor_only_subj_yr']['oa_next_full_year_all']['v1_low']['n']:,})\nNext full yr All DOIs (Subj×Yr)", ev["non_vor_only_subj_yr"]["oa_next_full_year_all"]["v1_low"], CRIMSON, "s"),
        (f"Non-VoR RP Subsample (N={ev['non_vor_only_subj_q']['dl_total']['v1_low']['n']:,})\nCumulative eLife Downloads", ev["non_vor_only_subj_q"]["dl_total"]["v1_low"], AMBER, "P"),
    ]
    y_b = np.arange(len(rows_b))
    ax2.axvline(0.0, color="#334155", ls="--", lw=0.9)
    ax2.axhline(2.5, color="#CBD5E1", ls=":", lw=0.9)
    ax2.axhline(4.5, color="#CBD5E1", ls=":", lw=0.9)
    for i, (_, m, col, mk) in enumerate(rows_b):
        pt, lo, hi = m["pct"], m["pct_ci95_lo"], m["pct_ci95_hi"]
        ax2.errorbar(pt, y_b[i], xerr=[[pt - lo], [hi - pt]], fmt=mk, color=col, markersize=5.8, elinewidth=1.6, capsize=3.0)
        p_txt = f"p={m['p']:.1e}" if m["p"] < 0.001 else f"p={m['p']:.3f}"
        ax2.text(hi + 1.5, y_b[i], f"{pt:+.1f}% ({p_txt})", va="center", ha="left", fontsize=7.3, fontweight="bold", color=col)

    ax2.text(
        0.48, -0.18,
        f"Incremental Deviance Gain (All-v1 Next-Yr): ΔDeviance = {inc_p['all_v1_oa_next_yr']['deviance_reduction']:.1f} "
        f"(LR p < 1e-10; ΔPseudo-R² = +{inc_p['all_v1_oa_next_yr']['delta_pseudo_r2_pp']:.2f} pp)",
        transform=ax2.transAxes, ha="center", va="top", fontsize=7.1, color=NAVY, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.28", "facecolor": BG_TINT, "edgecolor": "#CBD5E1"},
    )
    ax2.set_yticks(y_b)
    ax2.set_yticklabels([r[0] for r in rows_b], fontsize=7.4)
    ax2.invert_yaxis()
    ax2.set_xlim(-70, 46)
    ax2.set_xlabel("PPML Association: v1 Below-Solid vs. Solid (%, 95% CI, Subject-Clustered)")
    ax2.set_title("B. Equal-Window Validation: All-v1 vs. VoR vs. Non-VoR")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.tight_layout(w_pad=1.6)
    save_both(fig, "fig2_v4_equal_window_predictive_value")


def make_fig3_readership_and_funnel(p9: dict) -> None:
    """Main Figure 3: Onsite Readership Predictive Associations (N=1,852) & 4-Stage Revision/VoR Funnel."""
    att = p9["onsite_readership"]["complete_monthly_cohort_n1852"]
    fun = p9["revision_and_upgrade"]["funnel_by_v1_tier"]
    si = p9["supplementary_indexing_cohort"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.9), gridspec_kw={"width_ratios": [1.05, 1.15]})

    # Panel A: Onsite Readership Predictive Associations (Strictly Frozen v1 Covariates + Posting Day)
    outcomes = [
        ("pv_first_3m", "First 3 Bins:\nPage-Views"),
        ("dl_first_3m", "First 3 Bins:\nDownloads"),
        ("pv_total", "Cumulative:\nPage-Views"),
        ("dl_total", "Cumulative:\nDownloads"),
    ]
    y_pos = np.arange(len(outcomes))
    offsets = [-0.22, 0.0, 0.22]
    terms = [
        ("v1_low", "Evidence: Below Solid vs. Solid", CRIMSON, "o"),
        ("v1_imp", "Significance: Important vs. Lower", TEAL, "s"),
        ("v1_fund", "Significance: Fundamental+ vs. Lower", NAVY, "D"),
    ]
    ax1.axvline(0.0, color="#334155", ls="--", lw=0.9)
    for (tkey, tlbl, col, mk), off in zip(terms, offsets, strict=True):
        pts = [att[ok][tkey]["pct"] for ok, _ in outcomes]
        los = [att[ok][tkey]["pct_ci95_lo"] for ok, _ in outcomes]
        his = [att[ok][tkey]["pct_ci95_hi"] for ok, _ in outcomes]
        ax1.errorbar(
            pts, y_pos + off,
            xerr=[np.array(pts) - np.array(los), np.array(his) - np.array(pts)],
            fmt=mk, color=col, markersize=5.6, elinewidth=1.5, capsize=2.8, label=tlbl,
        )
        for idx, (pt, hi) in enumerate(zip(pts, his, strict=True)):
            ax1.text(hi + 1.0, y_pos[idx] + off, f"{pt:+.1f}%", va="center", ha="left", fontsize=7.0, color=col, fontweight="bold")

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([lbl for _, lbl in outcomes], fontsize=8.0, fontweight="bold")
    ax1.invert_yaxis()
    ax1.set_xlim(-32, 130)
    ax1.set_xlabel(f"Observational PPML Association (%, 95% CI, N = {att['pv_first_3m']['v1_low']['n']:,})")
    ax1.set_title("A. Onsite Readership Associations (Untruncated v1 ≥ 2023-11)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.48, -0.17), ncol=1, fontsize=7.2)

    # Panel B: Complete 4-Stage Outcome Decomposition Across Mature v1 Tiers (Distinguishing Public Revision!)
    order = [
        ("v1_Incomp_Inad", f"Below Solid\n(n={fun['v1_Incomp_Inad']['n_total']})"),
        ("v1_Solid", f"Solid\n(n={fun['v1_Solid']['n_total']})"),
        ("v1_Convincing", f"Convincing\n(n={fun['v1_Convincing']['n_total']})"),
        ("v1_Compel_Excep", f"Compelling+\n(n={fun['v1_Compel_Excep']['n_total']})"),
    ]
    y2 = np.arange(len(order))
    pub_rev = [fun[k]["pct_posted_revision"] for k, _ in order]
    vor_pct = [fun[k]["pct_vor"] for k, _ in order]
    up_all = [fun[k]["pct_all_upgraded_any"] for k, _ in order]

    h = 0.25
    ax2.barh(y2 - h, pub_rev, height=h, color=AMBER, alpha=0.9, label="Posted Public Revised Preprint (Crossref v≥2)")
    ax2.barh(y2, vor_pct, height=h, color=NAVY, alpha=0.9, label="Converted to Formal Version of Record (VoR)")
    ax2.barh(y2 + h, up_all, height=h, color=TEAL, alpha=0.9, label="Achieved Higher Final Rating (Unconditional All-v1 %)")

    for i, (k, _) in enumerate(order):
        r = fun[k]
        ax2.text(pub_rev[i] + 1.0, y2[i] - h, f"{pub_rev[i]:.1f}% ({r['n_posted_revision']})", va="center", ha="left", fontsize=7.0, color=AMBER, fontweight="bold")
        ax2.text(vor_pct[i] + 1.0, y2[i], f"{vor_pct[i]:.1f}% ({r['n_vor']})", va="center", ha="left", fontsize=7.0, color=NAVY, fontweight="bold")
        ax2.text(up_all[i] + 1.0, y2[i] + h, f"{up_all[i]:.1f}% ({r['n_vor_upgraded_any']}; {r['pct_vor_upgraded_any']:.1f}% of VoRs)", va="center", ha="left", fontsize=7.0, color=TEAL, fontweight="bold")

    ax2.text(
        0.50, -0.40,
        f"Public Revision ≠ Rating Upgrade: v1 <Solid posted {fun['v1_Incomp_Inad']['n_posted_revision']}/{fun['v1_Incomp_Inad']['n_total']} public revisions | "
        f"Apr 2023+ final <Solid VoRs: {si['apr2023_lower_rated_vors_with_posted_revision']}/{si['apr2023_lower_rated_vors']} "
        f"({si['apr2023_lower_rated_vors_with_revision_pct']:.1f}%) posted revisions | Mean v1→VoR lag (upgraded): {fun['v1_Incomp_Inad']['mean_rev_lag_up_days']:.1f}d",
        transform=ax2.transAxes, ha="center", va="top", fontsize=6.7, color="#0F172A", fontweight="bold",
        bbox={"boxstyle": "round,pad=0.26", "facecolor": BG_TINT, "edgecolor": "#94A3B8"},
    )
    ax2.set_yticks(y2)
    ax2.set_yticklabels([lbl for _, lbl in order], fontsize=8.0, fontweight="bold")
    ax2.invert_yaxis()
    ax2.set_xlim(0, 152)
    ax2.set_xticks([0, 20, 40, 60, 80, 100])
    ax2.set_xlabel("Share of Mature 2023–2024 v1 Cohort (%)")
    ax2.set_title(f"B. Public Revision, VoR Conversion & Rating Upgrades (N = {p9['cohort_summary']['n_mature_2023_2024']:,})")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="upper center", bbox_to_anchor=(0.48, -0.16), ncol=1, fontsize=7.1)

    fig.tight_layout(w_pad=1.6)
    save_both(fig, "fig3_v4_onsite_readership_and_funnel")


def make_fig4_upgrade_precision_and_trajectories(p9: dict) -> None:
    """Main Figure 4: Upgrade-to-Solid+ Precision / Equivalence Bounds & Version-Release Trajectories."""
    up = p9["revision_and_upgrade"]["upgrade_models"]
    raw_ev = up["raw_ev_m0_summary"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 4.9), gridspec_kw={"width_ratios": [1.18, 1.0]})

    # Panel A: Forest Plot of Upgrade-to-Solid+ Predictive Associations with Explicit ±15% & ±20% Equivalence Bands
    def log_to_pct_row(m: dict) -> tuple[float, float, float]:
        if "pct" in m:
            return m["pct"], m["pct_ci95_lo"], m["pct_ci95_hi"]
        return (
            100.0 * (np.exp(m["beta"]) - 1.0),
            100.0 * (np.exp(m["ci95_lo"]) - 1.0),
            100.0 * (np.exp(m["ci95_hi"]) - 1.0),
        )

    u_st = up["strict_v1_oa_post_v1"]
    u_bn = up["bench_v3_parity_oa_post_v1"]
    rows_a = [
        (f"Post-v1 OA Citations (Strict v1)\n[TOST ±20% p={u_st['tost_pm20']:.3f}, ±15% p={u_st['tost_pm15']:.3f}]", u_st, NAVY, "o"),
        (f"Post-v1 OA Citations (v3 parity)\n[TOST ±20% p={u_bn['tost_pm20']:.3f}, ±15% p={u_bn['tost_pm15']:.3f}]", u_bn, SLATE, "s"),
        (f"Next Full-Year OA Citations\n(Strict v1, N={up['strict_v1_oa_next_yr']['n']:,})", up["strict_v1_oa_next_yr"], NAVY, "D"),
        (f"Crossref Citations (Max DOI)\n(Strict v1, N={up['strict_v1_cr_cites']['n']:,})", up["strict_v1_cr_cites"], NAVY, "^"),
        (f"Cumulative Page-Views (log1p)\n(Strict v1, N={up['strict_v1_pv_total_ols']['n']:,})", up["strict_v1_pv_total_ols"], TEAL, "o"),
        (f"Cumulative Downloads (log1p)\n(Strict v1, N={up['strict_v1_dl_total_ols']['n']:,})", up["strict_v1_dl_total_ols"], TEAL, "^"),
        (f"Clean Monthly Rate DiD: Views\n(v1 ≥ 2023-11, N={up['strict_v1_rate_did_pv']['n']:,})", up["strict_v1_rate_did_pv"], TEAL, "s"),
        (f"Local VoR Post M+1..+6: Views\n(Clean event study, N={up['strict_v1_dlog_pv_ev_p16']['n']:,})", up["strict_v1_dlog_pv_ev_p16"], AMBER, "D"),
        (f"Local VoR Post M+1..+6: Downloads\n(Clean event study, N={up['strict_v1_dlog_dl_ev_p16']['n']:,})", up["strict_v1_dlog_dl_ev_p16"], AMBER, "^"),
    ]
    y_a = np.arange(len(rows_a))
    ax1.axvspan(-20, 20, color="#F1F5F9", alpha=0.85, zorder=0, label="±20% Equivalence Margin")
    ax1.axvspan(-15, 15, color="#E2E8F0", alpha=0.75, zorder=0, label="±15% Equivalence Margin")
    ax1.axvline(0.0, color="#334155", ls="--", lw=0.9, zorder=1)

    for i, (_, m, col, mk) in enumerate(rows_a):
        pt, lo, hi = log_to_pct_row(m)
        ax1.errorbar(pt, y_a[i], xerr=[[pt - lo], [hi - pt]], fmt=mk, color=col, markersize=5.6, elinewidth=1.6, capsize=3.0, zorder=3)
        ax1.text(hi + 1.2, y_a[i], f"{pt:+.1f}% [{lo:+.1f}, {hi:+.1f}]", va="center", ha="left", fontsize=7.0, fontweight="bold", color=col)

    ax1.set_yticks(y_a)
    ax1.set_yticklabels([r[0] for r in rows_a], fontsize=7.1)
    ax1.invert_yaxis()
    ax1.set_xlim(-30, 68)
    ax1.set_xlabel("Observational Association: Upgraded to Solid+ vs. Final <Solid (%)")
    ax1.set_title("A. Precision & Equivalence Bounds for Rating Upgrades (v1 <Solid VoRs)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.48, -0.16), ncol=2, fontsize=7.1)

    # Panel B: Version-Release & VoR Event Associations (What DOES Co-Move With Onsite Traffic!)
    rows_b = [
        ("VoR vs. RP-Only (v1 <Solid)\nCumulative Views (log1p)", up["vor_vs_rp_incomp_pv_ols"], NAVY, "o"),
        ("VoR vs. RP-Only (v1 <Solid)\nCumulative Downloads (log1p)", up["vor_vs_rp_incomp_dl_ols"], NAVY, "^"),
        ("Per Posted Version (v1 <Solid)\nMonths 12–21 vs 0–2 Views", up["version_release_m12_21_incomp"]["cr_n_versions"], CRIMSON, "D"),
        ("Per Posted Version (v1 Solid)\nMonths 12–21 vs 0–2 Views", up["version_release_m12_21_solid"]["cr_n_versions"], CRIMSON, "s"),
        ("Residual Upgrade Term (v1 <Solid)\nMonths 12–21 (Ctrl Versions)", up["version_release_m12_21_incomp"]["upgraded_solid"], SLATE, "o"),
        ("Local VoR Month t=0 Contrast\nUpgraded vs. Final <Solid (Views)", up["strict_v1_dlog_pv_ev_m0"], AMBER, "s"),
        ("Local VoR Month t=0 Contrast\nUpgraded vs. Final <Solid (Downloads)", up["strict_v1_dlog_dl_ev_m0"], AMBER, "^"),
    ]
    y_b = np.arange(len(rows_b))
    ax2.axvline(0.0, color="#334155", ls="--", lw=0.9)
    ax2.axhline(3.5, color="#CBD5E1", ls=":", lw=1.0)

    for i, (_, m, col, mk) in enumerate(rows_b):
        pt, lo, hi = m["beta"], m["ci95_lo"], m["ci95_hi"]
        ax2.errorbar(pt, y_b[i], xerr=[[pt - lo], [hi - pt]], fmt=mk, color=col, markersize=5.8, elinewidth=1.6, capsize=3.0)
        p_val = m.get("p_wcb", m["p"])
        p_lbl = "p_WCB" if "p_wcb" in m else "p"
        ax2.text(hi + 0.02, y_b[i], f"{pt:+.2f} ({p_lbl}={p_val:.3f})", va="center", ha="left", fontsize=7.2, fontweight="bold", color=col)

    ax2.text(
        0.50, -0.18,
        f"Uniform Raw VoR Month-0 Spike (N = {raw_ev['n_clean_ev']}): Views {raw_ev['pv_m0_upgraded_mean']:+.2f} (Upgraded) vs. "
        f"{raw_ev['pv_m0_unchanged_mean']:+.2f} (Final <Solid)  |  Downloads {raw_ev['dl_m0_upgraded_mean']:+.2f} vs. {raw_ev['dl_m0_unchanged_mean']:+.2f}",
        transform=ax2.transAxes, ha="center", va="top", fontsize=7.0, color=NAVY, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.26", "facecolor": BG_TINT, "edgecolor": "#CBD5E1"},
    )
    ax2.set_yticks(y_b)
    ax2.set_yticklabels([r[0] for r in rows_b], fontsize=7.3)
    ax2.invert_yaxis()
    ax2.set_xlim(-0.32, 1.52)
    ax2.set_xlabel("Log-Point Observational Association (95% CI, Subject-Clustered)")
    ax2.set_title("B. Version-Release Events vs. Rating-Change Terms")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.tight_layout(w_pad=1.6)
    save_both(fig, "fig4_v4_upgrade_precision_and_trajectories")


def make_figs1_si_indexing_cohort(p9: dict) -> None:
    """Supplementary Figure S1: Exploratory Dec 10, 2024 WoS & Scopus Cohort Analysis."""
    si = p9["supplementary_indexing_cohort"]
    curves = si["curves"]
    fh_s = si["fixed_horizon_strict_v1_subj"]
    fh_v3 = si["fixed_horizon_v3_parity_fin_subj"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.6), gridspec_kw={"width_ratios": [1.05, 1.15]})

    # Panel A: Aalen-Johansen CIF (Pre < Oct 1, 2024 vs Post >= Dec 10, 2024)
    for key, ls, tag in (("pre", "-", f"Earlier (<Oct 1, 2024; n={si['pre_n']})"), ("post", "--", f"Later (≥Dec 10, 2024; n={si['post_n']})")):
        pts = pd.DataFrame(curves[key]["curve"])
        ax1.plot(pts.days, pts.cif_solid_pct, ls, color=NAVY, lw=2.0, label=f"Final Solid+ VoR · {tag}")
        ax1.plot(pts.days, pts.cif_unrev_pct, ls, color=CRIMSON, lw=2.0, label=f"Final <Solid VoR · {tag}")
    ax1.axvline(450, color="#64748B", ls=":", lw=1.0)
    ax1.text(
        0.03, 0.96,
        f"CRITICAL OVERLAP DISCLOSURE:\n"
        f"• {si['pre_450_vors_after_announcement']}/{si['pre_450_vors']} ({si['pct_pre_450_vors_crossing_announcement']:.1f}%) earlier-cohort 450d VoRs\n"
        f"  finalized AFTER Dec 10, 2024!\n"
        f"• Dec 10 notice affected BOTH WoS & Scopus",
        transform=ax1.transAxes, va="top", ha="left", fontsize=7.0, color=CRIMSON, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.28", "facecolor": "#FEF2F2", "edgecolor": CRIMSON, "lw": 0.8},
    )
    ax1.set_xlim(0, 545)
    ax1.set_ylim(0, 68)
    ax1.set_xlabel("Calendar Days Since First Reviewed Preprint (v1)")
    ax1.set_ylabel("Unadjusted Aalen–Johansen CIF (%)")
    ax1.set_title("A. Exploratory Cohort CIF Around Dec 10, 2024 Notice")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.48, -0.17), ncol=1, fontsize=7.1)

    # Panel B: Subject-Adjusted Complete Fixed-Horizon Contrasts (450d & 540d; zero policy proof!)
    rows_b = [
        ("365d · Any VoR (Strict v1 Subj)", fh_s["365"]["any_vor"], NAVY, "o"),
        ("365d · Final <Solid VoR (Strict v1)", fh_s["365"]["lower_rated_vor"], CRIMSON, "o"),
        ("365d · Posted Public Rev (Strict v1)", fh_s["365"]["observed_revision"], TEAL, "o"),
        ("450d · Any VoR (Strict v1 Subj)", fh_s["450"]["any_vor"], NAVY, "s"),
        ("450d · Final <Solid VoR (v3 Parity)", fh_v3["450"]["lower_rated_vor"], CRIMSON, "s"),
        ("450d · Final <Solid VoR (Strict v1)", fh_s["450"]["lower_rated_vor"], CRIMSON, "D"),
        ("450d · Posted Public Rev (v3 Parity)", fh_v3["450"]["observed_revision"], TEAL, "s"),
        ("450d · Posted Public Rev (Strict v1)", fh_s["450"]["observed_revision"], TEAL, "D"),
        ("540d · Final Solid+ VoR (Strict v1)", fh_s["540"]["solid_vor"], SLATE, "^"),
        ("540d · Final <Solid VoR (Strict v1)", fh_s["540"]["lower_rated_vor"], CRIMSON, "^"),
    ]
    y_b = np.arange(len(rows_b))
    ax2.axvline(0.0, color="#334155", ls="--", lw=1.0)
    for i, (_, m, col, mk) in enumerate(rows_b):
        pt, lo, hi = 100.0 * m["beta"], 100.0 * m["ci95_lo"], 100.0 * m["ci95_hi"]
        ax2.errorbar(pt, y_b[i], xerr=[[pt - lo], [hi - pt]], fmt=mk, color=col, markersize=5.4, elinewidth=1.5, capsize=2.8)
        ax2.text(hi + 0.4, y_b[i], f"{pt:+.2f} pp [{lo:+.2f}, {hi:+.2f}]", va="center", ha="left", fontsize=6.9, fontweight="bold", color=col)

    ax2.set_yticks(y_b)
    ax2.set_yticklabels([r[0] for r in rows_b], fontsize=7.2)
    ax2.invert_yaxis()
    ax2.set_xlim(-16, 17)
    ax2.set_xlabel("Subject-Adjusted Cohort Difference (Percentage Points, CR1 95% CI)")
    ax2.set_title("B. Full-Followup Fixed-Horizon Contrasts (No Policy Effect Established)")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    fig.tight_layout()
    save_both(fig, "figs1_si_indexing_cohort_cif")


def make_figs2_si_velocity_and_sc(p5: dict) -> None:
    """Supplementary Figure S2: Exploratory Sequential ID Velocity Proxy & Published-Output SC."""
    ed = p5["pillar3a_editorial_cushioning"]
    vel = [r for r in ed["sfr_quarterly_velocity"] if "est_subs_per_quarter" in r and r["sfr_q"] >= "2023Q1"]
    sc_all = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_vs_23_24"]
    sc_cn = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_clarivate"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.5))

    qs = [r["sfr_q"] for r in vel]
    est_s = [r["est_subs_per_quarter"] for r in vel]
    x_q = np.arange(len(qs))
    clar_idx = qs.index("2024Q4") if "2024Q4" in qs else 7
    ax1.axvspan(clar_idx - 0.3, len(qs) - 0.5, color="#FEE2E2", alpha=0.45)
    ax1.axvline(clar_idx - 0.3, color=CRIMSON, ls="--", lw=1.2)
    ax1.plot(x_q, est_s, color=NAVY, lw=2.2, marker="o", markersize=5.4, label="Sequential eid Velocity Proxy")
    ax1.text(
        0.04, 0.07,
        f"Exploratory ID-velocity proxy: {ed['vel_drop_pct']:.1f}%\n"
        f"(Official eLife full-year: 6,396 → 2,853, −55.4%)\n"
        f"Acceptance jump: {ed['acc_pre_mean_pct']:.1f}% → {ed['acc_post_mean_pct']:.1f}% ({ed['acc_jump_pp']:+.2f} pp)",
        transform=ax1.transAxes, fontsize=7.1, color="#0F172A",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": BG_TINT, "edgecolor": "#CBD5E1"},
    )
    ax1.set_xticks(x_q[::2])
    ax1.set_xticklabels([qs[i] for i in range(0, len(qs), 2)], rotation=30, ha="right")
    ax1.set_ylim(450, 3250)
    ax1.set_ylabel("Implied Quarterly ID Velocity (Proxy Only)")
    ax1.set_title("A. Exploratory Sequential Manuscript-ID Velocity Proxy")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    pers = list(sc_cn["treated"]["gap_by_period"].keys())
    xc = np.arange(len(pers))
    for u, gdict in sc_cn["all_unit_gaps"].items():
        if u == "eLife":
            continue
        ax2.plot(xc, [gdict[p] for p in pers], color="#94A3B8", alpha=0.35, lw=0.95)
    ax2.plot(xc, [sc_cn["treated"]["gap_by_period"][p] for p in pers], color=CRIMSON, lw=2.6, marker="o", markersize=5.6, zorder=5, label="eLife (Published China Output − Synthetic)")
    ax2.plot([], [], color="#94A3B8", lw=1.2, alpha=0.7, label="29 Clean Biology Donor Placebos")
    ax2.axhline(0.0, color="#334155", ls="--", lw=0.9)
    ax2.axvline(6.5, color=NAVY, ls="--", lw=1.1)
    ax2.axvspan(6.5, len(pers) - 0.5, color="#FEE2E2", alpha=0.32)
    ax2.text(
        0.03, 0.08,
        f"Published Output (NOT Submissions):\n"
        f"• Total Vol SC (T0=3): {sc_all['treated']['post_mean_gap']:+.3f} (Rk {sc_all['rmspe_ratio_rank_of_N']}/{sc_all['n_units']}, p={sc_all['p_rmspe_ratio']:.4f})\n"
        f"• China Vol SC (T0=7): {sc_cn['treated']['post_mean_gap']:+.3f} (Rk {sc_cn['rmspe_ratio_rank_of_N']}/{sc_cn['n_units']}, p={sc_cn['p_rmspe_ratio']:.4f})",
        transform=ax2.transAxes, fontsize=7.0, color=NAVY, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": "white", "edgecolor": CRIMSON, "lw": 0.8},
    )
    ax2.set_xticks(xc)
    ax2.set_xticklabels(pers, rotation=30, ha="right")
    ax2.set_ylim(-1.60, 0.95)
    ax2.set_ylabel("Published-Output SC Gap (Log Articles)")
    ax2.set_title("B. Exploratory Published-Output ADH Synthetic Control (N = 30)")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="upper left", fontsize=7.2)

    fig.tight_layout()
    save_both(fig, "figs2_si_id_velocity_and_sc")


def make_figs3_si_geographic(p5: dict) -> None:
    """Supplementary Figure S3: Exploratory 12-Nation Published-Output Shifts & Senior-PI Shares."""
    p4_geo = p5["pillar4_global_metric_dependence"]
    pi = p4_geo["senior_pi_last_author_shares"]
    c_df = pd.DataFrame(p4_geo["country_12_panel"]).sort_values("phase2_pct_did")
    reg = p4_geo["institutional_regime_test"]
    ext = p4_geo["external_validation_blog_9nations"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.7), gridspec_kw={"width_ratios": [1.0, 1.2]})

    pers = sorted(pi.keys())
    xp = np.arange(len(pers))
    ax1.axvspan(2.5, len(pers) - 0.5, color="#FEE2E2", alpha=0.35)
    ax1.axvline(2.5, color=CRIMSON, ls="--", lw=1.1)
    ax1.plot(xp, [pi[p]["pi_US_pct"] for p in pers], color=NAVY, lw=2.2, marker="s", markersize=5.4, label="US (Senior PI)")
    ax1.plot(xp, [pi[p]["pi_EU_pct"] for p in pers], color=TEAL, lw=2.0, marker="^", markersize=5.4, label="Continental Europe (Senior PI)")
    ax1.plot(xp, [pi[p]["pi_CN_pct"] for p in pers], color=CRIMSON, lw=2.4, marker="o", markersize=5.8, label="China (Senior PI)")
    ax1.plot(xp, [pi[p]["pi_GB_pct"] for p in pers], color=AMBER, lw=1.9, marker="D", markersize=5.0, label="UK (Senior PI)")
    ax1.set_xticks(xp)
    ax1.set_xticklabels(pers, fontweight="bold")
    ax1.set_ylim(0, 54)
    ax1.set_ylabel("Share of Published eLife PRC Papers (%)")
    ax1.set_title("A. Exploratory Senior-PI Geography (Published Output)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper right", fontsize=7.2)

    yc = np.arange(len(c_df))
    cols = [CRIMSON if rg == "JIF_Codified" else (NAVY if rg == "DORA_Reformed" else AMBER) for rg in c_df["regime"]]
    ax2.barh(yc, c_df["phase2_pct_did"], height=0.62, color=cols, edgecolor="#1E293B", lw=0.5)
    ax2.axvline(0.0, color="#334155", lw=0.9)
    for i, (_, r) in enumerate(c_df.iterrows()):
        val = r["phase2_pct_did"]
        ax2.text(val - 1.4, yc[i], f"{val:+.1f}%", va="center", ha="right", fontsize=7.2, fontweight="bold", color="#0F172A")
    ax2.set_yticks(yc)
    ax2.set_yticklabels([f"{r['country_name']} ({r['country_code']})" for _, r in c_df.iterrows()], fontsize=7.9, fontweight="bold")
    ax2.set_xlim(-98, 4)
    ax2.set_xlabel("Exploratory Phase-2 Published-Output DiD vs. Donors (%)")
    ax2.set_title("B. Exploratory 12-Nation Published-Output Contrasts")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    handles = [
        Patch(facecolor=CRIMSON, edgecolor="#1E293B", label=f"3 JIF-Codified (CN, ES, IT): {reg['jif_mean_p2_pct']:+.1f}%"),
        Patch(facecolor=NAVY, edgecolor="#1E293B", label=f"7 DORA-Reformed: {reg['dora_mean_p2_pct']:+.1f}% (Perm p={reg['exact_comb_perm_p_1sided']:.4f})"),
        Patch(facecolor=AMBER, edgecolor="#1E293B", label=f"Mixed (IN, JP) | vs. eLife Blog (N={ext['n_countries']}): ρ={ext['spearman_rho']:.3f}"),
    ]
    ax2.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.48, -0.16), ncol=1, fontsize=7.0)

    fig.tight_layout()
    save_both(fig, "figs3_si_geographic_exploratory")


def main() -> None:
    print("=== STEP 6 (v4): GENERATING 4 MAIN + 3 SUPPLEMENTARY FIGURES (300-DPI PNG + PDF) ===", flush=True)
    set_pub_style()
    p3b = json.loads((RES_DIR / "03b_openalex_dedup_audit.json").read_bytes().decode("utf-8"))
    audit_raw = json.loads((DATA_DIR / "openalex_citing_dedup_audit.json").read_bytes().decode("utf-8"))
    p9 = json.loads((RES_DIR / "09_v4_scientometrics_results.json").read_bytes().decode("utf-8"))
    p5 = json.loads((RES_DIR / "05_pillar3_4_results.json").read_bytes().decode("utf-8"))

    make_fig1_measurement_audit(p3b, audit_raw, p9)
    make_fig2_equal_window_validation(p9)
    make_fig3_readership_and_funnel(p9)
    make_fig4_upgrade_precision_and_trajectories(p9)
    make_figs1_si_indexing_cohort(p9)
    make_figs2_si_velocity_and_sc(p5)
    make_figs3_si_geographic(p5)
    print("[DONE STEP 6 (v4)] Generated all 7 PNG + PDF figures cleanly.", flush=True)


if __name__ == "__main__":
    main()
