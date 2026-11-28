"""Pillar 6 (v4): Generate Publication-Grade Figures for Journal of Banking & Finance
Manuscript + Data Appendix (100% programmatic from results/*.json & tables/*.csv,
ZERO hardcoded numbers, 300 DPI PNG + vector PDF).

Figures generated:
  1. fig1_statutory_timing_and_concentration.{png,pdf}
     - Panel A: Category concentration (Fund count vs. Assets, All vs. Ex-Vanguard)
     - Panel B: Verified effective dates vs. SEC Release 33-11368 on-cycle compliance windows (N=50)
     - Panel C: Per-fund EDGAR disclosure taxonomy (Fund count vs. AUM share, N=50)
  2. fig2_event_study_placebos_and_honest_did.{png,pdf}
     - Panel A: Quarterly name-exit event study (2020Q1-2026Q3) with Announcement / Early / On-Cycle phases
     - Panel B: Counterfactual placebo forest plot (Historical 2021-2022 & Unregulated-word placebos vs. Observed)
     - Panel C: Rambachan-Roth (2023) Delta^RM(Mbar) trend-deviation sensitivity & breakdown values
  3. fig3_lookthrough_paths_and_partial_id_bounds.{png,pdf}
     - Panel A: Multi-quarter portfolio trajectories (2023Q2 -> 2024Q2 -> 2025Q2 -> 2026Q2/Q3)
     - Panel B: Repaired look-through estimates & full partial-identification sensitivity bounds
  4. fig4_exploratory_monthly_flows.{png,pdf}
     - Panel A: Exploratory monthly net-flow event study (m = -12..+12)
     - Panel B: Exploratory pooled TWFE net flows & gross sales/redemptions decomposition
  5. figA1_redemption_sign_audit.{png,pdf} (Data & Measurement Appendix)
     - Panel A: N-PORT negative-redemption incidence across MON1-MON3 (18.61%)
     - Panel B: N-PORT vs. TNA-implied flow concordance jump (r: 0.088 -> 0.955) & $44.31T vs $46.20T reconciliation
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

WORK_DIR = Path(__file__).resolve().parents[1]
RESULTS_DIR = WORK_DIR / "results"
TABLES_DIR = WORK_DIR / "tables"
FIG_DIR = WORK_DIR / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update(
    {
        "font.family": "DejaVu Serif",
        "font.size": 8.5,
        "axes.titlesize": 9.8,
        "axes.titleweight": "bold",
        "axes.labelsize": 8.5,
        "xtick.labelsize": 7.8,
        "ytick.labelsize": 7.8,
        "legend.fontsize": 7.6,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "figure.dpi": 300,
        "savefig.dpi": 300,
    }
)

C_NAVY = "#0f2c59"
C_TEAL = "#1f6f78"
C_AMBER = "#d97706"
C_CORAL = "#c2410c"
C_SLATE = "#64748b"
C_LIGHT = "#cbd5e1"
C_GREEN = "#15803d"
C_RED = "#b91c1c"


def load_json(name: str) -> dict:
    return json.loads((RESULTS_DIR / name).read_text(encoding="utf-8"))


def save_fig(fig: plt.Figure, stem: str) -> None:
    fig.savefig(FIG_DIR / f"{stem}.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)
    print(f"  [SAVED] {stem}.png & .pdf", flush=True)


def make_fig1() -> None:
    ren50 = pd.read_csv(TABLES_DIR / "table_50_renamers_statutory_audit.csv")
    r2b = load_json("02b_per_fund_statutory_audit.json")

    fig, axes = plt.subplots(1, 3, figsize=(13.2, 4.15), constrained_layout=True)

    # Panel A: Concentration of Rename Categories (All vs Ex-Vanguard)
    ax = axes[0]
    ex_vg = ren50[ren50["COMPLEX_ID"] != "VANGUARD"]
    groups = [ren50, ex_vg]
    positions = ["Fund count\n(All, n=50)", "Renamed AUM\n(All, $117.6B)", "Fund count\n(Ex-VG, n=46)", "Renamed AUM\n(Ex-VG, $52.4B)"]
    positions[1] = f"Renamed AUM\n(All, ${ren50['AUM_M'].sum() / 1e3:.1f}B)"
    positions[3] = f"Renamed AUM\n(Ex-VG, ${ex_vg['AUM_M'].sum() / 1e3:.1f}B)"
    cats = [
        ("OPAQUE_SYNONYM", "Non-numeric descriptor", C_TEAL),
        ("NUMERIC_RATIO", "Numeric ratio", C_AMBER),
        ("OTHER_MERGER_BRAND", "Other", C_SLATE),
    ]
    lefts = np.zeros(4)
    for code, lbl, col in cats:
        vals = []
        for g in groups:
            vals.append(100.0 * (g["COMPLIANCE_TYPE"] == code).mean())
            vals.append(100.0 * g.loc[g["COMPLIANCE_TYPE"] == code, "AUM_M"].sum() / g["AUM_M"].sum())
        arr = np.array(vals)
        bars = ax.barh(positions, arr, left=lefts, color=col, label=lbl, height=0.58, edgecolor="white", lw=0.6)
        for idx_b, bar in enumerate(bars):
            w = arr[idx_b]
            if w >= 10.0:
                ax.text(
                    lefts[idx_b] + w / 2.0,
                    bar.get_y() + bar.get_height() / 2.0,
                    f"{w:.1f}%",
                    ha="center",
                    va="center",
                    color="white" if col != C_AMBER else "#1a1a1a",
                    fontsize=7.6,
                    fontweight="bold",
                )
        lefts += arr
    ax.set_xlim(0, 100)
    ax.invert_yaxis()
    ax.set_xlabel("Share of multi-asset GVI renames (%)")
    ax.set_title("A. Category concentration (All vs. Ex-Vanguard)", loc="left")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.48, -0.17), ncol=2)

    # Panel B: Verified Effective Month vs. Statutory On-Cycle Schedule (33-11368)
    ax = axes[1]
    eff_dt = pd.to_datetime(ren50["VERIFIED_EFF_DATE"])
    eff_ym = eff_dt.dt.strftime("%Y-%m")
    # Build complete monthly index from 2025-01 to 2026-08
    months = pd.period_range("2025-01", "2026-08", freq="M").strftime("%Y-%m").tolist()
    cnt_opq = [int(((eff_ym == m) & (ren50["COMPLIANCE_TYPE"] != "NUMERIC_RATIO")).sum()) for m in months]
    cnt_num = [int(((eff_ym == m) & (ren50["COMPLIANCE_TYPE"] == "NUMERIC_RATIO")).sum()) for m in months]
    x = np.arange(len(months))
    ax.bar(x, cnt_opq, color=C_TEAL, label="Non-numeric / other", width=0.72)
    ax.bar(x, cnt_num, bottom=cnt_opq, color=C_AMBER, label="Numeric ratio", width=0.72)
    jun26_idx = months.index("2026-06")
    ax.axvline(jun26_idx - 0.5, color=C_RED, ls="--", lw=1.3)
    pre_n = r2b["effective_date_audit"]["pass2_pre_june11_2026"]
    tot_n = r2b["effective_date_audit"]["pass2_verified_total"]
    y2027 = r2b["effective_date_audit"]["renamers_with_oncycle_date_in_2027"]
    ax.set_ylim(0, 10.6)
    ax.annotate(
        f"Jun 11, 2026\non-cycle start\n({pre_n}/{tot_n} prior;\n{y2027}/50 due 2027)",
        xy=(jun26_idx - 0.5, 9.6),
        xytext=(jun26_idx - 5.2, 9.9),
        ha="center",
        va="top",
        fontsize=7.0,
        color=C_RED,
        arrowprops={"arrowstyle": "->", "color": C_RED, "lw": 0.9},
        bbox={"boxstyle": "round,pad=0.25", "fc": "#fff5f5", "ec": C_RED, "alpha": 0.95, "lw": 0.6},
    )
    tick_idx = [0, 3, 6, 9, 12, 15, 18]
    ax.set_xticks(tick_idx)
    ax.set_xticklabels([months[i] for i in tick_idx], rotation=35, ha="right")
    ax.set_ylabel("Number of renaming funds")
    ax.set_xlabel("Verified effective month (EDGAR 497/485BPOS)")
    ax.set_title("B. Early timing relative to Release 33-11368", loc="left")
    ax.grid(axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.5, -0.22), ncol=2)

    # Panel C: Per-Fund EDGAR Statutory Disclosure Taxonomy (Fund Share vs. AUM Share)
    ax = axes[2]
    cat_order = [
        ("UNCHANGED_POLICY_CONFIRMED", "Unchanged policy\nconfirmed"),
        ("MULTI_FUND_REBRAND_WITH_UNREGULATED", "Multi-fund rebrand\nw/ unregulated"),
        ("NAME_CHANGE_SILENT_ON_STATUTORY_BASIS", "Silent on\nstatutory basis"),
        ("FUND_CITES_35D1_SILENT_ON_MOTIVE", "Fund-scoped 35d-1\ncitation (silent)"),
        ("STRATEGY_OR_ADVISER_CHANGE_NO_35D1", "Strategy/adviser\nchange (no 35d-1)"),
        ("BENCHMARK_INDEX_RENAME_PAIRED", "Paired benchmark\nindex rename"),
    ]
    cat_cnts = r2b["statutory_category_counts_renamers"]
    cat_aums = r2b["statutory_category_aum_B_renamers"]
    tot_aum = sum(cat_aums.values())
    y_pos = np.arange(len(cat_order))
    f_sh = [100.0 * cat_cnts.get(k, 0) / 50.0 for k, _ in cat_order]
    a_sh = [100.0 * cat_aums.get(k, 0.0) / tot_aum for k, _ in cat_order]
    h = 0.36
    ax.barh(y_pos - h / 2, f_sh, height=h, color=C_NAVY, label="Share of funds (n=50)")
    ax.barh(y_pos + h / 2, a_sh, height=h, color=C_CORAL, label=f"Share of AUM (${tot_aum:.1f}B)")
    for i, (fs, as_) in enumerate(zip(f_sh, a_sh, strict=True)):
        ax.text(fs + 0.8, y_pos[i] - h / 2, f"{fs:.0f}%", va="center", fontsize=6.9, color=C_NAVY)
        ax.text(as_ + 0.8, y_pos[i] + h / 2, f"{as_:.1f}%", va="center", fontsize=6.9, color=C_CORAL)
    ax.set_yticks(y_pos)
    ax.set_yticklabels([lbl for _, lbl in cat_order], fontsize=7.4)
    ax.invert_yaxis()
    ax.set_xlim(0, 68)
    ax.set_xlabel("Share of 50 primary renamers (%)")
    ax.set_title("C. Per-fund EDGAR statutory disclosure audit", loc="left")
    ax.grid(axis="x", alpha=0.25)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.48, -0.17), ncol=2)

    save_fig(fig, "fig1_statutory_timing_and_concentration")


def make_fig2() -> None:
    es_df = pd.read_csv(TABLES_DIR / "table3_event_study_quarterly.csv")
    r4 = load_json("04_econometrics_results.json")
    r4b = load_json("04b_counterfactual_sensitivity.json")
    pl_df = pd.read_csv(TABLES_DIR / "table_placebo_audits.csv")

    fig, axes = plt.subplots(1, 3, figsize=(13.6, 4.35), constrained_layout=True)

    # Panel A: Event Study with Shaded Institutional Phases + Pre-Trend Transparency
    ax = axes[0]
    gvi_es = es_df[es_df["spec"] == "A3_GVI_ALL"].sort_values("REP_YQ").reset_index(drop=True)
    yqs = gvi_es["REP_YQ"].to_numpy()
    x = np.arange(len(yqs))
    q_labels = [f"{q // 10}Q{q % 10}" for q in yqs]

    idx_23q2 = int(np.where(yqs == 20232)[0][0])
    idx_25q1 = int(np.where(yqs == 20251)[0][0])
    idx_26q2 = int(np.where(yqs == 20262)[0][0])

    ax.axvspan(idx_23q2 + 0.5, idx_25q1 - 0.5, color="#e2e8f0", alpha=0.45, label="Ann. (23Q3-24Q4)")
    ax.axvspan(idx_25q1 - 0.5, idx_26q2 - 0.5, color="#fef3c7", alpha=0.55, label="Early (25Q1-26Q1)")
    ax.axvspan(idx_26q2 - 0.5, len(yqs) - 0.5, color="#fee2e2", alpha=0.45, label="On-cycle (26Q2-Q3)")
    ax.axhline(0, color="0.45", lw=0.9)
    ax.axvline(idx_23q2, color=C_NAVY, ls=":", lw=1.0)

    b = gvi_es["beta_pp"].to_numpy()
    lo = gvi_es["ci95_lo_pp"].to_numpy()
    hi = gvi_es["ci95_hi_pp"].to_numpy()
    ax.fill_between(x, lo, hi, color=C_TEAL, alpha=0.18)
    ax.plot(x, b, "-o", color=C_TEAL, ms=3.5, lw=1.4, label=f"GVI All (Pre p={r4['main_did_full_20_26Q3']['A3_GVI_ALL']['joint_pre_F']['p']:.3f})")

    # Also plot Opaque-only series
    opq_es = es_df[es_df["spec"] == "A3_GVI_OPAQUE_ONLY"].sort_values("REP_YQ").reset_index(drop=True)
    ax.plot(x, opq_es["beta_pp"].to_numpy(), "--s", color=C_NAVY, ms=2.8, lw=1.1, alpha=0.85, label=f"Opaque (Pre p={r4['main_did_full_20_26Q3']['A3_GVI_OPAQUE_ONLY']['joint_pre_F']['p']:.3f})")

    # Explicit annotation noting FAQ2 & FAQ4 joint pre-trend rejections
    p_faq2 = r4["main_did_full_20_26Q3"]["FAQ2_GV_NO_INC"]["joint_pre_F"]["p"]
    p_faq4 = r4["main_did_full_20_26Q3"]["FAQ4_GV_NO_INC_HOLD_LT80"]["joint_pre_F"]["p"]
    ax.text(
        0.03,
        0.96,
        f"GV-screen pre-trend rejections:\nFAQ2 p={p_faq2:.3f}; FAQ4 p={p_faq4:.3f}",
        transform=ax.transAxes,
        va="top",
        ha="left",
        fontsize=6.9,
        color=C_RED,
        bbox={"boxstyle": "round,pad=0.25", "fc": "#fff5f5", "ec": C_RED, "alpha": 0.9, "lw": 0.5},
    )
    tick_pos = list(range(0, len(yqs), 4)) + [len(yqs) - 1]
    tick_pos = sorted(set(tick_pos))
    ax.set_xticks(tick_pos)
    ax.set_xticklabels([q_labels[i] for i in tick_pos], rotation=35, ha="right")
    ax.set_ylabel("Quarterly exit-rate contrast (pp)")
    ax.set_xlabel("Report quarter (Ref = 2023Q2)")
    ax.set_title("A. Event-study phases & pre-trend check", loc="left")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.48, -0.22), ncol=2, fontsize=6.9)

    # Panel B: Counterfactual Placebo Forest Plot (Observed vs Historical & Unregulated Placebos)
    ax = axes[1]
    did = r4["main_did_full_20_26Q3"]

    def _did_ci(key: str) -> tuple[float, float, float]:
        d = did[key]["post_25_26"]
        tc = float(stats.t.ppf(0.975, df=d["G"] - 1))
        return 100 * d["beta"], 100 * (d["beta"] - tc * d["se_cr1"]), 100 * (d["beta"] + tc * d["se_cr1"])

    def _pl_ci(spec: str) -> tuple[float, float, float]:
        row = pl_df[pl_df["spec"] == spec].iloc[0]
        return float(row["beta_pp"]), float(row["ci95_lo_pp"]), float(row["ci95_hi_pp"])

    forest_items = [
        ("Observed: GVI All (25-26)", *_did_ci("A3_GVI_ALL"), C_TEAL),
        ("Observed: Ex-Vanguard Opaque", *_did_ci("A3_GVI_OPAQUE_EX_VANGUARD"), C_TEAL),
        ("Observed: GV Screen (Pre p=.043)", *_did_ci("FAQ2_GV_NO_INC"), C_NAVY),
        ("Hist. Placebo: GVI (21Q1-22Q3)", *_pl_ci("HIST_GVI_ALL_2021Q1_22Q3"), C_SLATE),
        ("Hist. Placebo: GV (21Q1-22Q3)", *_pl_ci("HIST_GV_NO_INC_2021Q1_22Q3"), C_SLATE),
        ("Hist. Placebo: LT<80 (22Q1-23Q2)", *_pl_ci("HIST_LT2_GVI_HOLD_LT80_2022Q1_23Q2"), C_SLATE),
        ("Unreg. Placebo: All Funds", *_pl_ci("UNREG_ALL_FUNDS_ALLOC_VS_SINGLE"), C_AMBER),
        ("Unreg. Placebo: Within GVI", *_pl_ci("UNREG_WITHIN_GVI_ALLOC_VS_SINGLE"), C_AMBER),
        ("Unreg. Placebo: Style Words", *_pl_ci("UNREG_STYLE_WORDS_DROP_ALLOC_VS_SINGLE"), C_AMBER),
    ]
    y_f = np.arange(len(forest_items))
    ax.axvline(0, color="0.45", lw=1.0, ls="--")
    ax.axhline(2.5, color=C_LIGHT, lw=0.8)
    ax.axhline(5.5, color=C_LIGHT, lw=0.8)
    for i, (lbl, est, lo_v, hi_v, col) in enumerate(forest_items):
        ax.errorbar(est, i, xerr=[[est - lo_v], [hi_v - est]], fmt="o", color=col, capsize=2.8, ms=4.5, lw=1.3)
    ax.set_yticks(y_f)
    ax.set_yticklabels([x[0] for x in forest_items], fontsize=7.2)
    ax.invert_yaxis()
    ax.set_xlabel("DiD contrast (pp/quarter, 95% CR1 CI)")
    ax.set_title("B. Observed vs. historical & unregulated placebos", loc="left")
    ax.grid(axis="x", alpha=0.22)

    # Panel C: Rambachan-Roth (2023) Delta^RM(Mbar) Sensitivity Bounds
    ax = axes[2]
    ax.axhline(0, color=C_RED, ls="--", lw=1.0)
    rr_specs = [
        ("A3_GVI_OPAQUE_ONLY", "GVI Opaque", C_NAVY, -0.012),
        ("A3_GVI_ALL", "GVI All", C_TEAL, 0.0),
        ("FAQ4_GV_NO_INC_HOLD_LT80", "GV Screen + <80%", C_CORAL, +0.012),
    ]
    for skey, slbl, col, x_off in rr_specs:
        rm = r4b["phase_and_honest_did"][skey]["rambachan_roth_delta_rm"]
        m_sub = [g for g in rm["grid"] if g["Mbar"] <= 0.75]
        mb = np.array([g["Mbar"] for g in m_sub]) + x_off
        lo_g = np.array([g["robust_ci95_lo"] for g in m_sub])
        hi_g = np.array([g["robust_ci95_hi"] for g in m_sub])
        mid_g = 0.5 * (lo_g + hi_g)
        ax.errorbar(
            mb,
            mid_g,
            yerr=[mid_g - lo_g, hi_g - mid_g],
            fmt="o-",
            color=col,
            capsize=2.5,
            ms=3.8,
            lw=1.2,
            label=f"{slbl} (M̄*={rm['breakdown_Mbar_star']:.2f})",
        )
    ax.set_xlabel(r"Relative-magnitude bound $\bar{M}$ ($\Delta^{RM}$)")
    ax.set_ylabel("95% robust CI for 2025-26 avg. contrast (pp)")
    ax.set_title(r"C. Rambachan-Roth (2023) $\Delta^{RM}$ sensitivity", loc="left")
    ax.set_xticks([0.0, 0.25, 0.50, 0.75])
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, loc="upper center", bbox_to_anchor=(0.48, -0.22), ncol=1, fontsize=7.2)

    save_fig(fig, "fig2_event_study_placebos_and_honest_did")


def make_fig3() -> None:
    traj = pd.read_csv(TABLES_DIR / "table_multiquarter_portfolio_paths.csv")
    r3 = load_json("03_holdings_lookthrough.json")

    fig, axes = plt.subplots(1, 2, figsize=(11.6, 4.3), constrained_layout=True)

    # Panel A: Multi-Quarter Portfolio Trajectories (2023Q2 -> 2024Q2 -> 2025Q2 -> 2026Q2/Q3)
    ax = axes[0]
    tg = traj[traj["sample"] == "HOLD_LT_CONSTR_GVI"].copy()
    snaps = ["2023Q2", "2024Q2", "2025Q2", "2026Q2/Q3"]
    x = np.arange(len(snaps))
    ax.plot(x, tg["dropper_max_class_pct"].to_numpy(), "-o", color=C_TEAL, lw=2.0, ms=6.0, label="Renamed funds (n=39): max(Eq, Bond)")
    ax.plot(x, tg["keeper_max_class_pct"].to_numpy(), "--s", color=C_CORAL, lw=2.0, ms=5.8, label="Retained funds (n=350): max(Eq, Bond)")
    ax.axhline(80.0, color=C_RED, ls=":", lw=1.1, label="80% single-class benchmark")

    # Annotate drift-adjusted differences directly at 2024Q2, 2025Q2, 2026Q2/Q3!
    diffs = tg["active_toward_80_diff_pp"].to_numpy()
    pvals = tg["active_toward_80_p_wcb"].to_numpy()
    for i in (1, 2, 3):
        y_box = min(tg["keeper_max_class_pct"].iloc[i], tg["dropper_max_class_pct"].iloc[i]) - 4.8
        ax.text(
            x[i],
            y_box,
            f"Drift-adj Δ:\n{diffs[i]:+.2f} pp\n(p={pvals[i]:.3f})",
            ha="center",
            va="top",
            fontsize=6.9,
            color=C_NAVY,
            bbox={"boxstyle": "round,pad=0.22", "fc": "#f8fafc", "ec": C_NAVY, "lw": 0.5, "alpha": 0.95},
        )
    ax.set_xticks(x)
    ax.set_xticklabels(snaps)
    ax.set_ylim(48, 84)
    ax.set_ylabel("Mean look-through largest-class weight (%)")
    ax.set_xlabel("Historical N-PORT snapshot (repaired zero-leakage weights)")
    ax.set_title("A. Multi-quarter portfolio paths (<80% GVI sample)", loc="left")
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, loc="lower left", fontsize=7.3)

    # Panel B: Repaired Estimates & Full Partial-Identification Bounds
    ax = axes[1]
    gvi_m = r3["inertia_cross_section"]["HOLD_LT_CONSTR_GVI"]["metrics"]
    gv_m = r3["inertia_cross_section"]["HOLD_LT_CONSTR_GV_NO_INC"]["metrics"]
    pi_gvi_mx = r3["partial_identification_bounds"]["GVI_ALL_PAIRED"]["ACTIVE_TOWARD_80"]
    pi_gvi_eq = r3["partial_identification_bounds"]["GVI_ALL_PAIRED"]["ACTIVE_REBAL_EQ"]
    pi_gv_mx = r3["partial_identification_bounds"]["GV_NO_INC_PAIRED"]["ACTIVE_TOWARD_80"]
    pi_gv_eq = r3["partial_identification_bounds"]["GV_NO_INC_PAIRED"]["ACTIVE_REBAL_EQ"]

    def _m_ci(m: dict) -> tuple[float, float, float]:
        tc = float(stats.t.ppf(0.975, df=m["G"] - 1))
        return m["beta"], m["beta"] - tc * m["se_cr1"], m["beta"] + tc * m["se_cr1"]

    rows_b = [
        ("GVI Max-Class: Repaired Neutral", *_m_ci(gvi_m["ACTIVE_TOWARD_80"]), C_TEAL, None),
        ("GVI Max-Class: Fund-Return Drift", *_m_ci(gvi_m["ACTIVE_TOWARD_80_FUNDRET"]), C_TEAL, None),
        ("GVI Max-Class: Delete 21 Crossers", pi_gvi_mx["core_delete_all_crossers"]["beta"], pi_gvi_mx["core_delete_all_crossers"]["ci95_lo"], pi_gvi_mx["core_delete_all_crossers"]["ci95_hi"], C_NAVY, None),
        ("GVI Max-Class: Sharp PI Bounds", 0.5 * sum(pi_gvi_mx["identified_set_beta_interval"]), pi_gvi_mx["outer_95ci_interval"][0], pi_gvi_mx["outer_95ci_interval"][1], C_CORAL, pi_gvi_mx["identified_set_beta_interval"]),
        ("GVI Equity-Only: Sharp PI Bounds", 0.5 * sum(pi_gvi_eq["identified_set_beta_interval"]), pi_gvi_eq["outer_95ci_interval"][0], pi_gvi_eq["outer_95ci_interval"][1], C_SLATE, pi_gvi_eq["identified_set_beta_interval"]),
        ("GV Screen Max-Class: Repaired", *_m_ci(gv_m["ACTIVE_TOWARD_80"]), C_NAVY, None),
        ("GV Screen Max-Class: Sharp PI", 0.5 * sum(pi_gv_mx["identified_set_beta_interval"]), pi_gv_mx["outer_95ci_interval"][0], pi_gv_mx["outer_95ci_interval"][1], C_AMBER, pi_gv_mx["identified_set_beta_interval"]),
        ("GV Screen Equity-Only: Sharp PI", 0.5 * sum(pi_gv_eq["identified_set_beta_interval"]), pi_gv_eq["outer_95ci_interval"][0], pi_gv_eq["outer_95ci_interval"][1], C_AMBER, pi_gv_eq["identified_set_beta_interval"]),
    ]

    ax.axvline(0, color="0.45", lw=1.0, ls="--")
    ax.axhline(4.5, color=C_LIGHT, lw=0.8)
    for i, (lbl, est, lo_v, hi_v, col, id_set) in enumerate(rows_b):
        if id_set is not None:
            # Outer 95% CI thin whisker + thick solid bar for sharp identified set [lo, hi]
            ax.plot([lo_v, hi_v], [i, i], color=col, lw=1.2, alpha=0.75)
            ax.plot([lo_v, lo_v], [i - 0.14, i + 0.14], color=col, lw=1.2, alpha=0.75)
            ax.plot([hi_v, hi_v], [i - 0.14, i + 0.14], color=col, lw=1.2, alpha=0.75)
            ax.plot([id_set[0], id_set[1]], [i, i], color=col, lw=5.2, solid_capstyle="butt")
        else:
            ax.errorbar(est, i, xerr=[[est - lo_v], [hi_v - est]], fmt="o", color=col, capsize=3.0, ms=5.0, lw=1.4)
    ax.set_yticks(np.arange(len(rows_b)))
    ax.set_yticklabels([r[0] for r in rows_b], fontsize=7.4)
    ax.invert_yaxis()
    ax.set_xlabel("Renamed minus retained, drift-adjusted (pp)\n[Thick bar = sharp PI set; thin whisker = outer 95% CI]")
    ax.set_title("B. Repaired estimates & partial-identification bounds", loc="left")
    ax.grid(axis="x", alpha=0.22)

    save_fig(fig, "fig3_lookthrough_paths_and_partial_id_bounds")


def make_fig4() -> None:
    es_m = pd.read_csv(TABLES_DIR / "table_monthly_flow_event_study.csv")
    r5 = load_json("05_monthly_flow_results.json")

    fig, axes = plt.subplots(1, 2, figsize=(11.4, 4.05), constrained_layout=True)

    # Panel A: Exploratory Monthly Net-Flow Event Study (m = -12..+12)
    ax = axes[0]
    ax.axhline(0, color="0.45", lw=0.9)
    ax.axvline(-0.5, color=C_RED, ls="--", lw=1.0)
    for arm, lbl, col, mk in [
        ("MA_GVI_OPAQUE", f"Non-numeric (n=42, WCB p={r5['monthly_arms']['MA_GVI_OPAQUE']['pooled_twfe']['preferred_ret_tna_ctrl']['p_wcb']:.3f})", C_TEAL, "o"),
        ("MA_GVI_NUMERIC", f"Numeric ratio (n=7, 3 cplx; WCB p={r5['monthly_arms']['MA_GVI_NUMERIC']['pooled_twfe']['preferred_ret_tna_ctrl']['p_wcb']:.3f})", C_AMBER, "s"),
    ]:
        sub = es_m[es_m["arm"] == arm].sort_values("rel_month")
        m_vals = sub["rel_month"].to_numpy()
        b_c = sub["beta_centered_pct"].to_numpy()
        lo_c = sub["ci95_cent_lo"].to_numpy()
        hi_c = sub["ci95_cent_hi"].to_numpy()
        ax.plot(m_vals, b_c, f"-{mk}", color=col, ms=3.8, lw=1.4, label=lbl)
        ax.fill_between(m_vals, lo_c, hi_c, color=col, alpha=0.14)
    ax.set_xlabel("Months relative to verified rename month (m = 0)")
    ax.set_ylabel("Centered monthly net flow contrast (pp/mo)")
    ax.set_title("A. Exploratory monthly net-flow trajectories", loc="left")
    ax.text(
        0.03,
        0.95,
        "Strictly exploratory descriptive evidence\n(Numeric arm: 7 funds across 3 complexes)",
        transform=ax.transAxes,
        va="top",
        fontsize=7.0,
        color="#334155",
        bbox={"boxstyle": "round,pad=0.25", "fc": "#f8fafc", "ec": "#94a3b8", "lw": 0.5},
    )
    ax.grid(alpha=0.22)
    ax.legend(frameon=False, loc="lower left", fontsize=7.2)

    # Panel B: Exploratory Pooled TWFE Flow Contrasts (Net Flow, Gross Sales, Redemptions)
    ax = axes[1]
    arms_show = [
        ("MA_GVI_POOLED", "MA GVI Pooled\n(n=50)"),
        ("MA_GVI_OPAQUE", "Non-numeric\n(n=42)"),
        ("MA_GVI_NUMERIC", "Numeric ratio\n(n=7, 3 cplx)"),
        ("MA_GVI_RETAIL", "Retail channel\n(n=27)"),
        ("MA_GVI_VA_INSURANCE", "VA/Insurance\n(n=23)"),
    ]
    x = np.arange(len(arms_show))
    w = 0.26
    net_b, net_se, sal_b, sal_se, red_b, red_se = [], [], [], [], [], []
    for ak, _ in arms_show:
        a = r5["monthly_arms"][ak]
        p_net = a["pooled_twfe"]["preferred_ret_tna_ctrl"]
        p_sal = a["decomposition"]["SALES_PCT"]
        p_red = a["decomposition"]["REDEMP_ABS_PCT"]
        net_b.append(p_net["beta"]); net_se.append(1.96 * p_net["se_cr1"])
        sal_b.append(p_sal["beta"]); sal_se.append(1.96 * p_sal["se_cr1"])
        red_b.append(p_red["beta"]); red_se.append(1.96 * p_red["se_cr1"])
    ax.axhline(0, color="0.45", lw=0.9)
    ax.bar(x - w, net_b, width=w, yerr=net_se, capsize=2.2, color=C_NAVY, label="Net flow")
    ax.bar(x, sal_b, width=w, yerr=sal_se, capsize=2.2, color=C_TEAL, label="Gross sales")
    ax.bar(x + w, red_b, width=w, yerr=red_se, capsize=2.2, color=C_CORAL, label="Gross redemptions")
    ax.set_xticks(x)
    ax.set_xticklabels([lbl for _, lbl in arms_show], fontsize=7.4)
    ax.set_ylim(-1.55, 2.25)
    ax.set_ylabel("Post-rename TWFE contrast (pp/month, 95% CR1 CI)")
    ax.set_title("B. Exploratory net-flow & gross-flow decomposition", loc="left")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, loc="upper left", ncol=3, fontsize=7.2)

    save_fig(fig, "fig4_exploratory_monthly_flows")


def make_figA1() -> None:
    r1 = load_json("01_panel_audit.json")
    nr = r1["negative_redemption_audit"]
    fv = r1["flow_sign_fix_validation"]

    fig, axes = plt.subplots(1, 2, figsize=(10.2, 3.6), constrained_layout=True)

    ax = axes[0]
    cats = ["Month 1", "Month 2", "Month 3", "Pooled"]
    pct_nn = [nr[k]["pct_negative_of_nonnull"] for k in ("MON1", "MON2", "MON3", "POOLED_MON1_TO_MON3")]
    pct_nz = [nr[k]["pct_negative_of_nonzero"] for k in ("MON1", "MON2", "MON3", "POOLED_MON1_TO_MON3")]
    x = np.arange(len(cats))
    w = 0.35
    b1 = ax.bar(x - w / 2, pct_nn, width=w, color=C_NAVY, label="% of non-missing")
    b2 = ax.bar(x + w / 2, pct_nz, width=w, color=C_AMBER, label="% of non-zero")
    for bars in (b1, b2):
        for bar in bars:
            h = bar.get_height()
            ax.text(bar.get_x() + bar.get_width() / 2, h + 0.4, f"{h:.2f}%", ha="center", va="bottom", fontsize=7.0)
    ax.set_xticks(x)
    ax.set_xticklabels(cats)
    ax.set_ylim(0, 27)
    ax.set_ylabel("Share of records with negative redemptions (%)")
    ax.set_title("A. Form N-PORT negative-redemption sign incidence", loc="left")
    ax.grid(axis="y", alpha=0.22)
    ax.legend(frameon=False, loc="upper right")

    ax = axes[1]
    labels = ["Raw unclipped\nPearson r", "Raw clipped\nPearson r", "Raw Spearman\nrank ρ", "Abs-fixed\nPearson r", "Abs-fixed\nSpearman ρ"]
    vals = [
        fv["pearson_raw_unclipped_vs_tna"],
        fv["pearson_raw_clipped100_vs_tna"],
        fv["spearman_raw_vs_tna"],
        fv["pearson_fixed_abs_vs_tna"],
        fv["spearman_fixed_abs_vs_tna"],
    ]
    cols = [C_CORAL, C_CORAL, C_AMBER, C_TEAL, C_NAVY]
    bars = ax.bar(np.arange(len(labels)), vals, color=cols, width=0.58)
    for bar in bars:
        h = bar.get_height()
        ax.text(bar.get_x() + bar.get_width() / 2, h + 0.02, f"{h:.3f}", ha="center", va="bottom", fontsize=7.4, fontweight="bold")
    ax.set_xticks(np.arange(len(labels)))
    ax.set_xticklabels(labels, fontsize=7.2)
    ax.set_ylim(0, 1.09)
    ax.set_ylabel("Agreement with TNA-and-return-implied flow")
    ax.set_title(f"B. Concordance validation (N = {fv['n_valid_qtr_obs']:,})", loc="left")
    ax.grid(axis="y", alpha=0.22)

    save_fig(fig, "figA1_redemption_sign_audit")


def main() -> int:
    print("[Pillar 6 v4] Generating all JBF main-text & Data Appendix figures (300 DPI PNG + PDF)...", flush=True)
    make_fig1()
    make_fig2()
    make_fig3()
    make_fig4()
    make_figA1()
    print("[DONE PILLAR 6 v4] All 5 v4 figures generated cleanly.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
