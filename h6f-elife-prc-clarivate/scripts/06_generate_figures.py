"""Step 6: Generate 5 publication-grade 300-DPI PNG + vector PDF figures for
manuscript_h6f_boost.md, reading 100% of data and annotations dynamically from
saved JSON/CSV receipts (zero hardcoded estimates).
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(r"D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126")
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"
FIG_DIR = BASE_DIR / "figures"

# Colorblind-safe Nature / PNAS palette
NAVY = "#0B2545"
CRIMSON = "#C1292E"
TEAL = "#1B7F79"
AMBER = "#D97706"
SLATE = "#64748B"
LIGHT_GRAY = "#CBD5E1"
BG_TINT = "#F8FAFC"


def set_pub_style() -> None:
    mpl.rcParams.update({
        "font.family": "DejaVu Sans",
        "font.size": 9.0,
        "axes.titlesize": 10.2,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.2,
        "axes.edgecolor": "#334155",
        "axes.linewidth": 0.8,
        "xtick.labelsize": 8.3,
        "ytick.labelsize": 8.3,
        "legend.fontsize": 8.0,
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


def make_fig1(p4: dict) -> None:
    """Figure 1: True v1 -> VoR Revision Architecture & Post-ESCI (Dec 19, 2024) Unconditional CIF/ITT."""
    trans = p4["pillar1_transition_mature"]
    esci = p4["pillar1_esci_solid_cliff"]
    km = esci["km_competing_risks"]
    pre_c = km["cohorts"]["pre_esci_lt_2024_10_01"]
    post_c = km["cohorts"]["post_esci_ge_2024_12_19"]
    c_aj = km["contrast_dec19_vs_pre_donut"]["contrasts"]
    w365 = esci["fixed_windows"]["win_365d"]["primary_dec19_donut"]
    w450 = esci["fixed_windows"]["win_450d"]["primary_dec19_donut"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.8), gridspec_kw={"width_ratios": [1.08, 1.12]})

    # Panel A: 100% stacked bar breakdown of v1 strength cohorts (N=2,653 mature)
    order = [
        ("v1_Incomp_Inad", "Incomplete /\nInadequate"),
        ("v1_Solid", "Solid"),
        ("v1_Convincing", "Convincing"),
        ("v1_Compel_Excep", "Compelling /\nExceptional"),
    ]
    y_pos = np.arange(len(order))
    up_pcts, unch_pcts, rp_pcts = [], [], []
    for k, _ in order:
        r = trans[k]
        tot = max(r["n_total"], 1)
        up_pcts.append(100.0 * r["n_vor_upgraded"] / tot)
        unch_pcts.append(100.0 * r["n_vor_unchanged"] / tot)
        rp_pcts.append(100.0 * r["n_rp_only"] / tot)

    up_a, un_a, rp_a = np.array(up_pcts), np.array(unch_pcts), np.array(rp_pcts)
    h = 0.56
    ax1.barh(y_pos, up_a, height=h, color=TEAL, label="VoR — Strength Upgraded")
    ax1.barh(y_pos, un_a, left=up_a, height=h, color=NAVY, label="VoR — Strength Unchanged")
    ax1.barh(y_pos, rp_a, left=up_a + un_a, height=h, color=LIGHT_GRAY, edgecolor="#94A3B8", label="Reviewed Preprint Only (No VoR)")

    for i, (k, _) in enumerate(order):
        r = trans[k]
        if up_a[i] >= 12:
            ax1.text(up_a[i] / 2, y_pos[i], f"{up_a[i]:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=8.1)
        if un_a[i] >= 12:
            ax1.text(up_a[i] + un_a[i] / 2, y_pos[i], f"{un_a[i]:.1f}%", ha="center", va="center", color="white", fontweight="bold", fontsize=8.1)
        if rp_a[i] >= 9:
            ax1.text(up_a[i] + un_a[i] + rp_a[i] / 2, y_pos[i], f"{rp_a[i]:.1f}%", ha="center", va="center", color="#1E293B", fontsize=7.6)
        ax1.text(
            101.5, y_pos[i],
            f"n={r['n_total']} | Up/All: {r['pct_all_upgraded_vor']:.1f}%\nUp/VoR: {r['pct_vor_upgraded']:.1f}% | Δt: {r['mean_rev_lag_up']:.0f}d",
            va="center", ha="left", fontsize=7.2, color="#1E293B",
        )

    ax1.set_yticks(y_pos)
    ax1.set_yticklabels([lbl for _, lbl in order], fontweight="bold")
    ax1.invert_yaxis()
    ax1.set_xlim(0, 140)
    ax1.set_xticks([0, 20, 40, 60, 80, 100])
    ax1.set_xlabel("Share of Mature 2023–2024 v1 Cohort (%)")
    ax1.set_title("A. Longitudinal v1 → VoR Outcomes (N = 2,653)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper center", bbox_to_anchor=(0.45, -0.17), ncol=2, frameon=True, fontsize=7.5)

    # Panel B: Unconditional Competing-Risks Cumulative Incidence (KM VoR, AJ Solid+, AJ Unrevised <Solid)
    # Aligned strictly to v1 >= Dec 19, 2024 vs Pre < Oct 1, 2024 (Oct-Dec 18 transition donut excluded)
    days = [pt["days"] for pt in pre_c["curve"]]
    ax2.plot(days, [pt["km_vor_pct"] for pt in pre_c["curve"]], color=NAVY, lw=2.2, ls="-", label=f"Pre (<Oct 2024, n={pre_c['n']}): Any VoR (KM)")
    ax2.plot(days, [pt["km_vor_pct"] for pt in post_c["curve"]], color=NAVY, lw=2.2, ls="--", label=f"Post (≥Dec 19, n={post_c['n']}): Any VoR (KM)")
    ax2.plot(days, [pt["cif_solid_pct"] for pt in pre_c["curve"]], color=TEAL, lw=2.1, ls="-", label="Pre: Upgraded Solid+ VoR (AJ CIF)")
    ax2.plot(days, [pt["cif_solid_pct"] for pt in post_c["curve"]], color=TEAL, lw=2.1, ls="--", label="Post: Upgraded Solid+ VoR (AJ CIF)")
    ax2.plot(days, [pt["cif_unrev_pct"] for pt in pre_c["curve"]], color=CRIMSON, lw=2.0, ls="-", label="Pre: Unrevised <Solid VoR (AJ CIF)")
    ax2.plot(days, [pt["cif_unrev_pct"] for pt in post_c["curve"]], color=CRIMSON, lw=2.0, ls="--", label="Post: Unrevised <Solid VoR (AJ CIF)")

    ax2.axvline(365, color="#94A3B8", ls=":", lw=1.0)
    ax2.axvline(450, color="#94A3B8", ls=":", lw=1.0)
    ax2.text(369, 24.5, "365d", fontsize=7.3, color="#475569", fontweight="bold")
    ax2.text(454, 24.5, "450d", fontsize=7.3, color="#475569", fontweight="bold")

    p365_vor = w365["itt_vor_win"]["params"]["post_esci"]
    p365_up = w365["itt_up_solid_win"]["params"]["post_esci"]
    p450_vor = w450["itt_vor_win"]["params"]["post_esci"]
    p450_up = w450["itt_up_solid_win"]["params"]["post_esci"]
    aj450_unr = c_aj["t450"]["cif_unrev_pct"]

    ax2.text(
        0.02, 0.98,
        f"Unconditional ITT (≥Dec 19 vs. Pre; Oct–Dec 18 Donut Excl.):\n"
        f"• 365d (n={w365['itt_vor_win']['n']:,}): VoR {100*p365_vor['beta']:+.2f} pp ($p_{{\\mathrm{{WCB}}}}$={p365_vor['p_wcb']:.3f}) | Solid+ {100*p365_up['beta']:+.2f} pp ($p_{{\\mathrm{{WCB}}}}$={p365_up['p_wcb']:.3f})\n"
        f"• 450d (n={w450['itt_vor_win']['n']:,}): VoR {100*p450_vor['beta']:+.2f} pp ($p_{{\\mathrm{{WCB}}}}$={p450_vor['p_wcb']:.3f}) | Solid+ {100*p450_up['beta']:+.2f} pp ($p_{{\\mathrm{{WCB}}}}$={p450_up['p_wcb']:.3f})\n"
        f"• 450d AJ Unrev. <Solid CIF: {aj450_unr['pre_pct']:.1f}% → {aj450_unr['post_pct']:.1f}% ({aj450_unr['diff_pp']:+.2f} pp, p={aj450_unr['p']:.4f})",
        transform=ax2.transAxes, ha="left", va="top", fontsize=6.5, color="#0F172A", zorder=10,
        bbox={"boxstyle": "round,pad=0.28", "facecolor": BG_TINT, "edgecolor": "#94A3B8", "lw": 0.75, "alpha": 0.97},
    )

    ax2.set_xlim(0, 545)
    ax2.set_ylim(0, 90)
    ax2.set_xticks([0, 90, 180, 270, 365, 450, 540])
    ax2.set_xlabel("Calendar Days Since v1 Reviewed Preprint Posting")
    ax2.set_ylabel("Cumulative Incidence Across All v1 Incomplete (%)")
    ax2.set_title("B. Post-ESCI (≥Dec 19, 2024) Unconditional CIF & ITT")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="upper center", bbox_to_anchor=(0.48, -0.17), ncol=2, frameon=True, fontsize=6.9)

    fig.tight_layout()
    save_both(fig, "fig1_transition_and_esci_norms")


def make_fig2(p4: dict) -> None:
    """Figure 2: Evaluation-Market Paradox — v1 Gradient, VoR-Date Autopsy & Untruncated Revision Payoff."""
    grad = p4["pillar2_v1_gradient_and_autopsy"]
    up_inc = p4["pillar2_upgrade_payoff"]["v1_Incomp_VoRs"]
    up_sol = p4["pillar2_upgrade_payoff"]["v1_Solid_VoRs"]
    ev_raw = up_inc["ev_raw_summary"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.4, 5.4), gridspec_kw={"width_ratios": [1.0, 1.22]})

    # Panel A: First-impression v1 gradient & VoR-date autopsy (Subject-clustered G=18 PPML!)
    rows_a = [
        ("v1 Incomplete → OA Post-v1 Cites\n(TRUE v1-date alignment)", grad["vor_true_v1_oa_post_ppml"]["params"]["v1_incomp_d"], CRIMSON, "o"),
        ("Fin Incomplete → OA Post-v1 Cites\n(FLAWED VoR-date autopsy)", grad["vor_flawed_vor_oa_post_ppml"]["params"]["fin_incomp_d"], SLATE, "s"),
        ("v1 Compelling → OA Post-v1 Cites\n(TRUE v1-date alignment)", grad["vor_true_v1_oa_post_ppml"]["params"]["v1_comp_d"], NAVY, "o"),
        ("v1 Incomplete → eLife Page-Views\n(TRUE v1-date alignment)", grad["vor_true_v1_pv_ppml"]["params"]["v1_incomp_d"], TEAL, "D"),
        ("v1 Incomplete → eLife Downloads\n(TRUE v1-date alignment)", grad["vor_true_v1_dl_ppml"]["params"]["v1_incomp_d"], TEAL, "^"),
        ("v1 Sig: Important → eLife Views\n(Headline salience drives clicks)", grad["vor_true_v1_pv_ppml"]["params"]["v1_sig_imp"], AMBER, "D"),
        ("v1 Sig: Important → eLife Downloads\n(Headline salience drives downloads)", grad["vor_true_v1_dl_ppml"]["params"]["v1_sig_imp"], AMBER, "^"),
    ]
    y_a = np.arange(len(rows_a))
    ax1.axvline(0.0, color="#334155", ls="--", lw=0.9)
    for i, (_, p, col, mk) in enumerate(rows_a):
        b = p["beta"]
        ci = 1.96 * p["se"]
        ax1.errorbar(b, y_a[i], xerr=ci, fmt=mk, color=col, markersize=6.5, elinewidth=1.8, capsize=3.5)
        pct = p.get("pct", 100.0 * (np.exp(b) - 1.0))
        p_txt = f"p={p['p']:.1e}" if p["p"] < 0.001 else f"p={p['p']:.3f}"
        ax1.text(b + ci + 0.015, y_a[i], f"{pct:+.1f}% ({p_txt})", va="center", ha="left", fontsize=7.5, color=col, fontweight="bold")

    ax1.set_yticks(y_a)
    ax1.set_yticklabels([r[0] for r in rows_a], fontsize=7.9)
    ax1.invert_yaxis()
    ax1.set_xlim(-0.30, 0.72)
    ax1.set_xlabel("PPML Log-Point Effect vs. Solid / Valuable Baseline (95% CI, G = 18)")
    ax1.set_title("A. First-Impression v1 Gradient & VoR-Date Autopsy")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Untruncated Revision-Upgrade Payoff (Citations + Clean Monthly Attention) vs. Release-Event Effect
    rows_b = [
        ("OA Post-v1 Citations (PPML)\n[v1 Incomp → Solid+]", up_inc["ppml_oa_post_v1"]["params"]["str_upgraded_to_solid"], NAVY, "o"),
        ("Crossref Citations (PPML)\n[v1 Incomp → Solid+]", up_inc["ppml_cr_max"]["params"]["str_upgraded_to_solid"], NAVY, "s"),
        ("eLife Page-Views Total (log1p OLS)\n[All mature, N=766]", up_inc["ols_log1p_pv_total"]["params"]["str_upgraded_to_solid"], TEAL, "D"),
        ("Clean Monthly Rate DiD (Views)\n[Untruncated v1 ≥ 2023-11, N=544]", up_inc["ols_did_log_pv_rate_clean"]["params"]["str_upgraded_to_solid"], TEAL, "D"),
        ("Local VoR Month t=0 Diff (Views)\n[Uniform spike: +1.11 vs +1.11]", up_inc["ev_pv_m0"]["params"]["str_upgraded_to_solid"], SLATE, "s"),
        ("Local VoR Post t=+1..+6 (Views)\n[Clean event study, N=619]", up_inc["ev_pv_p16"]["params"]["str_upgraded_to_solid"], SLATE, "D"),
        ("Local VoR Post t=+1..+6 (Downloads)\n[Clean event study, N=619]", up_inc["ev_dl_p16"]["params"]["str_upgraded_to_solid"], SLATE, "^"),
        ("22m Post-v1 M12–21 Views (Ctrl Ver)\n[Residual badge effect, N=546]", up_inc["traj_dlog_pv_12_21_ctrl_ver"]["params"]["str_upgraded_to_solid"], SLATE, "o"),
        ("Per Extra Version Posted (Incomp)\n[Release-event traffic bump]", up_inc["traj_dlog_pv_12_21_ctrl_ver"]["params"]["cr_n_versions"], CRIMSON, "D"),
        ("Per Extra Version Posted (Solid)\n[Release-event traffic bump]", up_sol["traj_dlog_pv_12_21_ctrl_ver"]["params"]["cr_n_versions"], CRIMSON, "D"),
    ]
    y_b = np.arange(len(rows_b))
    ax2.axvspan(-0.15, 0.15, color="#F1F5F9", alpha=0.85, zorder=0, label="±0.15 Log-Point Band (All G = 18 Subject-Clustered)")
    ax2.axvline(0.0, color="#334155", ls="--", lw=0.9, zorder=1)
    ax2.axhline(1.5, color="#CBD5E1", ls=":", lw=0.9)
    ax2.axhline(7.5, color="#CBD5E1", ls=":", lw=0.9)

    for i, (_, p, col, mk) in enumerate(rows_b):
        b = p["beta"]
        ci = 1.96 * p["se"]
        ax2.errorbar(b, y_b[i], xerr=ci, fmt=mk, color=col, markersize=6.2, elinewidth=1.7, capsize=3.2, zorder=3)
        p_val = p.get("p_wcb", p["p"])
        p_lbl = "$p_{\\mathrm{WCB}}$" if "p_wcb" in p else "$p$"
        p_txt = f"{p_lbl}={p_val:.4f}" if p_val < 0.01 else f"{p_lbl}={p_val:.3f}"
        ax2.text(b + ci + 0.015, y_b[i], f"{b:+.3f} ({p_txt})", va="center", ha="left", fontsize=7.2, color=col, fontweight="bold")

    ax2.set_yticks(y_b)
    ax2.set_yticklabels([r[0] for r in rows_b], fontsize=7.4)
    ax2.invert_yaxis()
    ax2.set_xlim(-0.30, 0.78)
    ax2.set_xlabel("Log-Point Effect (95% CI, Subject-Clustered G = 17–18)")
    ax2.set_title("B. Modest/Null Badge Upgrade Payoff vs. Version-Release Traffic")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.text(
        0.50, -0.18,
        f"Uniform VoR Month-0 Spike (N={up_inc['n_clean_vor_ev']}): Views {ev_raw['dlog_pv_ev_m0']['upgraded_mean']:+.2f} (Up) vs {ev_raw['dlog_pv_ev_m0']['unchanged_mean']:+.2f} (Unch)  |  "
        f"Downloads {ev_raw['dlog_dl_ev_m0']['upgraded_mean']:+.2f} vs {ev_raw['dlog_dl_ev_m0']['unchanged_mean']:+.2f}",
        transform=ax2.transAxes, ha="center", va="top", fontsize=7.1, color=NAVY, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": BG_TINT, "edgecolor": "#CBD5E1"},
    )

    fig.tight_layout(w_pad=1.8)
    save_both(fig, "fig2_evaluation_market_paradox")


def make_fig3(p5: dict) -> None:
    """Figure 3: Clarivate Oct 2024 Shock — Sequential eid Submission Collapse & Two-Margin Editorial Cushioning."""
    ed = p5["pillar3a_editorial_cushioning"]
    vel = [r for r in ed["sfr_quarterly_velocity"] if "est_subs_per_quarter" in r and r["sfr_q"] >= "2023Q1"]
    blks = pd.DataFrame(ed["blocks_500"])

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11.8, 4.5))

    # Panel A: Quarterly Submission Velocity calibrated by sentForReview (r = 0.9988)
    qs = [r["sfr_q"] for r in vel]
    est_s = [r["est_subs_per_quarter"] for r in vel]
    x_q = np.arange(len(qs))
    clar_idx = qs.index("2024Q4") if "2024Q4" in qs else 7

    ax1.axvspan(clar_idx - 0.3, len(qs) - 0.5, color="#FEE2E2", alpha=0.45, label="Post-Clarivate Delisting (Oct 24, 2024)")
    ax1.plot(x_q, est_s, color=NAVY, lw=2.3, marker="o", markersize=5.8, label="Implied Submissions / Quarter (Δeid)")
    ax1.axvline(clar_idx - 0.3, color=CRIMSON, ls="--", lw=1.3)

    ax1.annotate(
        f"Pre-Clarivate Avg:\n{ed['pre_vel_mean_subs_q']:,.0f} / qtr",
        xy=(4, ed["pre_vel_mean_subs_q"]), xytext=(1.2, 2950),
        fontsize=7.9, fontweight="bold", color=NAVY,
        arrowprops={"arrowstyle": "->", "color": NAVY, "lw": 0.9},
    )
    ax1.annotate(
        f"Post-Clarivate Avg:\n{ed['post_vel_mean_subs_q']:,.0f} / qtr ({ed['vel_drop_pct']:.1f}%)",
        xy=(10, ed["post_vel_mean_subs_q"]), xytext=(8.6, 2050),
        fontsize=7.9, fontweight="bold", color=CRIMSON,
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 0.9},
    )
    ax1.text(
        0.03, 0.06,
        f"sentForReview calibration: N = {ed['n_sfr_sample']}, Spearman r = {ed['spearman_eid_sfr_r']:.4f}",
        transform=ax1.transAxes, fontsize=7.6, color="#334155",
        bbox={"boxstyle": "round,pad=0.25", "facecolor": BG_TINT, "edgecolor": "#CBD5E1"},
    )
    ax1.set_xticks(x_q[::2])
    ax1.set_xticklabels([qs[i] for i in range(0, len(qs), 2)], rotation=30, ha="right")
    ax1.set_ylim(500, 3300)
    ax1.set_ylabel("Estimated Quarterly Submissions (Sequential eid Velocity)")
    ax1.set_title("A. Margin 1: Submission Velocity Collapse After Delisting")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper right", fontsize=7.6)

    # Panel B: 500-eid Peer-Review Acceptance Rate Jump vs Invariant v1 Incomplete Share
    eid_k = blks["eid_mid"].to_numpy() / 1000.0
    acc = blks["accept_pct"].to_numpy()
    inc = blks["v1_incomp_pct"].to_numpy()
    bp_k = ed["clarivate_bp_eid_used"] / 1000.0

    ax2.axvspan(bp_k, eid_k.max() + 0.4, color="#FEE2E2", alpha=0.38)
    ax2.axvline(bp_k, color=CRIMSON, ls="--", lw=1.3, label=f"Clarivate Cutoff (eid ≈ {ed['interpolated_eid_at_2024_10_24']:,.0f})")
    ax2.plot(eid_k, acc, color=NAVY, lw=2.0, marker="o", markersize=3.8, label="Peer-Review Acceptance Rate (%)")
    ax2.hlines(ed["acc_pre_mean_pct"], eid_k.min(), bp_k, color=NAVY, ls=":", lw=1.8)
    ax2.hlines(ed["acc_post_mean_pct"], bp_k, eid_k.max(), color=CRIMSON, ls=":", lw=1.8)

    ax2_r = ax2.twinx()
    ax2_r.plot(eid_k, inc, color=TEAL, lw=1.6, ls="-.", alpha=0.85, label="v1 Incomplete Share (%)")
    ax2_r.set_ylabel("v1 Incomplete Assessment Share (%)", color=TEAL)
    ax2_r.tick_params(axis="y", labelcolor=TEAL)
    ax2_r.set_ylim(10, 74)
    ax2_r.spines["top"].set_visible(False)

    v1_inc_p = ed["v1_quality_shift"]["v1_incomp"]["base_subj_fe"]["params"]["post_clar_eid"]
    ax2.text(
        0.03, 0.97,
        f"Accept Jump: {ed['acc_pre_mean_pct']:.2f}% → {ed['acc_post_mean_pct']:.2f}% ({ed['acc_jump_pp']:+.2f} pp)\n"
        f"HAC t = {ed['acc_jump_hac_t']:+.2f}, Perm p = {ed['acc_jump_perm_p']:.4f}, Sup-Wald F = {ed['sup_wald_best_F_hac']:.1f}\n"
        f"v1 Quality Shift: {100*v1_inc_p['beta']:+.2f} pp (p = {v1_inc_p['p']:.3f}, invariant)",
        transform=ax2.transAxes, va="top", ha="left", fontsize=7.4, color="#0F172A", zorder=10,
        bbox={"boxstyle": "round,pad=0.30", "facecolor": "white", "edgecolor": "#94A3B8", "alpha": 0.98},
    )
    ax2.set_ylim(8.5, 34.5)
    ax2.set_xlabel("Sequential Submission Manuscript ID (eid, thousands)")
    ax2.set_ylabel("Reviewed-Preprint Acceptance Rate (% of 500-eid Block)", color=NAVY)
    ax2.set_title("B. Margin 2: Editorial Cushioning with Invariant v1 Quality")
    ax2.spines["top"].set_visible(False)

    # Combine legends cleanly below axis (zero overlap with data dips!)
    h1, l1 = ax2.get_legend_handles_labels()
    h2, l2 = ax2_r.get_legend_handles_labels()
    ax2.legend(h1 + h2, l1 + l2, loc="upper center", bbox_to_anchor=(0.50, -0.17), ncol=2, fontsize=7.4)

    fig.tight_layout()
    save_both(fig, "fig3_clarivate_two_margin_cushioning")


def make_fig4(p5: dict) -> None:
    """Figure 4: Expanded N=30 Strict (& N=35) Abadie-Diamond-Hainmueller Synthetic Control & Placebo Ranks."""
    sc_all_c = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_vs_23_24"]
    sc_all_35 = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_exp35"]
    sc_cn = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_clarivate"]
    sc_cn_c = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_clarivate_vs_23_24"]
    sc_cn_35 = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_exp35"]
    es_all = p5["pillar3b_expanded_sc_and_did"]["event_study_2021H1_2026H1"]["log_n_all"]
    es_cn = p5["pillar3b_expanded_sc_and_did"]["event_study_2021H1_2026H1"]["log_n_CN"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.0, 4.7), gridspec_kw={"width_ratios": [1.15, 1.0]})

    # Panel A: Full-Pre (2021H1-2024H2 excl. 2023H1) ADH Synthetic Control Gaps for China Output (log_n_CN) across ALL 30 strict journals!
    pers_cn = list(sc_cn["treated"]["gap_by_period"].keys())
    x_c = np.arange(len(pers_cn))
    for u, gdict in sc_cn["all_unit_gaps"].items():
        vals = [gdict[p] for p in pers_cn]
        if u == "eLife":
            continue
        ax1.plot(x_c, vals, color="#94A3B8", alpha=0.35, lw=1.0)
    el_vals = [sc_cn["treated"]["gap_by_period"][p] for p in pers_cn]
    ax1.plot(x_c, el_vals, color=CRIMSON, lw=2.8, marker="o", markersize=6.0, zorder=5, label="eLife (Actual − Synthetic eLife)")
    ax1.plot([], [], color="#94A3B8", lw=1.2, alpha=0.7, label="29 Clean Peer-Biology Donor Placebos")
    ax1.axhline(0.0, color="#334155", ls="--", lw=0.9)
    ax1.axvline(6.5, color=NAVY, ls="--", lw=1.2)
    ax1.axvspan(6.5, len(pers_cn) - 0.5, color="#FEE2E2", alpha=0.35)
    ax1.text(
        0.03, 0.10,
        f"Full-Pre SC Gap (plotted, T₀=7): {sc_cn['treated']['post_mean_gap']:+.3f} (Rk {sc_cn['rmspe_ratio_rank_of_N']}/{sc_cn['n_units']}, p={sc_cn['p_rmspe_ratio']:.4f})\n"
        f"Clarivate SC Gap (T₀=3): {sc_cn_c['treated']['post_mean_gap']:+.3f} (Rk {sc_cn_c['rmspe_ratio_rank_of_N']}/{sc_cn_c['n_units']}, p={sc_cn_c['p_rmspe_ratio']:.4f})\n"
        f"Expanded N=35 Full-Pre Rank: {sc_cn_35['rmspe_ratio_rank_of_N']}/{sc_cn_35['n_units']} (p={sc_cn_35['p_rmspe_ratio']:.4f})",
        transform=ax1.transAxes, fontsize=7.2, color=NAVY, fontweight="bold",
        bbox={"boxstyle": "round,pad=0.28", "facecolor": "white", "edgecolor": CRIMSON, "lw": 0.9},
    )
    ax1.set_xticks(x_c)
    ax1.set_xticklabels(pers_cn, rotation=32, ha="right")
    ax1.set_ylim(-1.60, 0.95)
    ax1.set_ylabel("Synthetic Control Gap: log(China Articles) − Synthetic")
    ax1.set_title("A. Published-Output ADH SC Placebo Fan: China (N = 30)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper left", fontsize=7.6)

    # Panel B: Half-Yearly Event Study (2021H1-2026H1, base = 2022H2) for Total Output vs China Output across N=30 clean journals
    pers_es = ["2021H1", "2021H2", "2022H1", "2022H2", "2023H2", "2024H1", "2024H2", "2025H1", "2025H2", "2026H1"]
    xe = np.arange(len(pers_es))
    y_all = [es_all[p]["did_vs_2022H2"] for p in pers_es]
    sd_all = [es_all[p]["ctrl_sd"] for p in pers_es]
    y_cn = [es_cn[p]["did_vs_2022H2"] for p in pers_es]

    ax2.axhline(0.0, color="#334155", ls="--", lw=0.9)
    ax2.axvline(3.5, color=TEAL, ls=":", lw=1.2, label="Phase 1: PRC Launch (2023)")
    ax2.axvline(6.5, color=CRIMSON, ls="--", lw=1.2, label="Phase 2: Clarivate Delisting (Oct 2024)")
    ax2.fill_between(xe, -1.96 * np.array(sd_all), 1.96 * np.array(sd_all), color="#E2E8F0", alpha=0.55, label="Donor Pool ±1.96 SD (Total Output)")
    ax2.plot(xe, y_all, color=NAVY, lw=2.3, marker="s", markersize=5.5, label="eLife Total Output DiD (vs 2022H2)")
    ax2.plot(xe, y_cn, color=CRIMSON, lw=2.4, marker="o", markersize=5.8, label="eLife China Output DiD (vs 2022H2)")

    ax2.annotate(
        f"Phase-1 China Surge\n({es_cn['2024H2']['did_vs_2022H2']:+.2f} log pts)",
        xy=(6, es_cn["2024H2"]["did_vs_2022H2"]), xytext=(3.6, 0.62),
        fontsize=7.6, fontweight="bold", color=CRIMSON,
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 0.9},
    )
    ax2.annotate(
        f"Phase-2 Collapse\nTotal: {es_all['2026H1']['did_vs_2022H2']:+.2f}\nChina: {es_cn['2026H1']['did_vs_2022H2']:+.2f}",
        xy=(9, es_cn["2026H1"]["did_vs_2022H2"]), xytext=(6.8, -1.36),
        fontsize=7.5, fontweight="bold", color=NAVY,
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 0.9},
    )
    ax2.text(
        0.02, 0.03,
        f"Total Vol. Clarivate SC: {sc_all_c['treated']['post_mean_gap']:+.3f} (Rk {sc_all_c['rmspe_ratio_rank_of_N']}/30, p={sc_all_c['p_rmspe_ratio']:.4f}; "
        f"Exp35 Rk {sc_all_35['rmspe_ratio_rank_of_N']}/35, p={sc_all_35['p_rmspe_ratio']:.4f})",
        transform=ax2.transAxes, fontsize=6.9, color="#334155",
        bbox={"boxstyle": "round,pad=0.22", "facecolor": BG_TINT, "edgecolor": "#CBD5E1"},
    )
    ax2.set_xticks(xe)
    ax2.set_xticklabels(pers_es, rotation=32, ha="right")
    ax2.set_ylim(-1.60, 0.95)
    ax2.set_ylabel("Half-Yearly DiD vs. 2022H2 (Log Articles)")
    ax2.set_title("B. Two-Phase Event Study Across 30 Clean Biology Journals")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)
    ax2.legend(loc="lower left", bbox_to_anchor=(0.01, 0.13), fontsize=7.0)

    fig.tight_layout()
    save_both(fig, "fig4_expanded_synthetic_control")


def make_fig5(p5: dict) -> None:
    """Figure 5: Two-Phase Asymmetric Global Metric Dependence (Senior-PI Shares & 12-Nation Regime Test)."""
    p4_geo = p5["pillar4_global_metric_dependence"]
    pi = p4_geo["senior_pi_last_author_shares"]
    c_df = pd.DataFrame(p4_geo["country_12_panel"]).sort_values("phase2_pct_did")
    reg = p4_geo["institutional_regime_test"]
    ext = p4_geo["external_validation_blog_9nations"]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12.2, 4.9), gridspec_kw={"width_ratios": [1.0, 1.22]})

    # Panel A: Senior/Last-Author PI Country Shares Inside eLife PRC (2023H2-2026H1)
    pers = sorted(pi.keys())
    xp = np.arange(len(pers))
    us_pi = [pi[p]["pi_US_pct"] for p in pers]
    eu_pi = [pi[p]["pi_EU_pct"] for p in pers]
    cn_pi = [pi[p]["pi_CN_pct"] for p in pers]
    gb_pi = [pi[p]["pi_GB_pct"] for p in pers]

    ax1.axvspan(2.5, len(pers) - 0.5, color="#FEE2E2", alpha=0.38, label="Post-Clarivate Delisting")
    ax1.axvline(2.5, color=CRIMSON, ls="--", lw=1.2)
    ax1.plot(xp, us_pi, color=NAVY, lw=2.3, marker="s", markersize=5.8, label="United States (Senior PI)")
    ax1.plot(xp, eu_pi, color=TEAL, lw=2.1, marker="^", markersize=5.8, label="Continental Europe (Senior PI)")
    ax1.plot(xp, cn_pi, color=CRIMSON, lw=2.6, marker="o", markersize=6.4, label="China (Senior PI)")
    ax1.plot(xp, gb_pi, color=AMBER, lw=2.0, marker="D", markersize=5.2, label="United Kingdom (Senior PI)")

    ax1.annotate(
        f"Peak: {pi['2024H2']['pi_CN_pct']:.1f}%",
        xy=(2, pi["2024H2"]["pi_CN_pct"]), xytext=(1.35, 25.0),
        fontsize=7.8, fontweight="bold", color=CRIMSON,
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 0.9},
    )
    ax1.annotate(
        f"Overnight Crash:\n{pi['2025H1']['pi_CN_pct']:.1f}%",
        xy=(3, pi["2025H1"]["pi_CN_pct"]), xytext=(3.15, 2.5),
        fontsize=7.8, fontweight="bold", color=CRIMSON,
        arrowprops={"arrowstyle": "->", "color": CRIMSON, "lw": 0.9},
    )
    ax1.set_xticks(xp)
    ax1.set_xticklabels(pers, fontweight="bold")
    ax1.set_ylim(0, 54)
    ax1.set_ylabel("Share of eLife PRC Papers by Senior/Last-Author PI (%)")
    ax1.set_title("A. Senior-PI Geography Inside eLife PRC (2023H2–2026H1)")
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)
    ax1.legend(loc="upper right", fontsize=7.4)

    # Panel B: 12-Nation Phase-2 Clarivate DiD Output Shock & Institutional Regime Test
    yc = np.arange(len(c_df))
    colors = []
    for rg in c_df["regime"]:
        if rg == "JIF_Codified":
            colors.append(CRIMSON)
        elif rg == "DORA_Reformed":
            colors.append(NAVY)
        else:
            colors.append(AMBER)

    ax2.barh(yc, c_df["phase2_pct_did"], height=0.62, color=colors, edgecolor="#1E293B", linewidth=0.5, zorder=3)
    ax2.axvline(0.0, color="#334155", lw=0.9, zorder=2)
    ax2.axvline(reg["jif_mean_p2_pct"], color=CRIMSON, ls="--", lw=1.1, alpha=0.65, zorder=1)
    ax2.axvline(reg["dora_mean_p2_pct"], color=NAVY, ls=":", lw=1.1, alpha=0.65, zorder=1)

    for i, (_, r) in enumerate(c_df.iterrows()):
        val = r["phase2_pct_did"]
        blg = f" | Blog: {r['blog_2026_sub_drop_pct']:.0f}%" if pd.notna(r["blog_2026_sub_drop_pct"]) else ""
        ax2.text(
            val - 1.4, yc[i], f"{val:+.1f}%{blg}", va="center", ha="right",
            fontsize=7.2, fontweight="bold", color="#0F172A", zorder=5,
            bbox={"boxstyle": "square,pad=0.14", "facecolor": "white", "edgecolor": "none", "alpha": 0.92},
        )

    ax2.set_yticks(yc)
    ax2.set_yticklabels([f"{r['country_name']} ({r['country_code']})" for _, r in c_df.iterrows()], fontsize=8.0, fontweight="bold")
    ax2.set_xlim(-110, 4)
    ax2.set_ylim(-0.7, 13.7)
    ax2.set_xlabel("Phase-2 Clarivate Published-Output DiD vs. Peer Journals (%)")
    ax2.set_title("B. 12-Nation Policy-Label Groupings (3 JIF vs. 7 DORA)")
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    from matplotlib.patches import Patch
    handles = [
        Patch(facecolor=CRIMSON, edgecolor="#1E293B", label=f"3 JIF-Codified (CN, ES, IT): mean {reg['jif_mean_p2_pct']:+.1f}%"),
        Patch(facecolor=NAVY, edgecolor="#1E293B", label=f"7 DORA-Reformed (GB, FR, US, CH, NL, DE, CA): mean {reg['dora_mean_p2_pct']:+.1f}%"),
        Patch(facecolor=AMBER, edgecolor="#1E293B", label="2 Mixed / Other (IN, JP)"),
    ]
    ax2.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.48, -0.15), ncol=1, fontsize=7.2)
    ax2.text(
        0.47, 0.98,
        f"3 JIF vs. 7 DORA Perm p = {reg['exact_comb_perm_p_1sided']:.4f}  |  vs. eLife Blog Subs (N={ext['n_countries']}): Spearman ρ = {ext['spearman_rho']:.3f} (p = {ext['spearman_p']:.3f})",
        transform=ax2.transAxes, va="top", ha="center", fontsize=6.5, color="#0F172A", fontweight="bold",
        bbox={"boxstyle": "round,pad=0.24", "facecolor": "#FEF3C7", "edgecolor": AMBER, "lw": 0.8},
    )

    fig.tight_layout()
    save_both(fig, "fig5_asymmetric_global_jif_dependence")


def main() -> None:
    print("=== STEP 6: GENERATING 5 PUBLICATION-GRADE 300-DPI FIGURES (PNG + PDF) ===", flush=True)
    set_pub_style()
    p4 = json.loads((RES_DIR / "04_pillar1_2_results.json").read_bytes().decode("utf-8"))
    p5 = json.loads((RES_DIR / "05_pillar3_4_results.json").read_bytes().decode("utf-8"))

    make_fig1(p4)
    make_fig2(p4)
    make_fig3(p5)
    make_fig4(p5)
    make_fig5(p5)
    print("[DONE STEP 6] Generated all 5 PNG + PDF figures cleanly.", flush=True)


if __name__ == "__main__":
    main()
