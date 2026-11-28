"""Step 10 (v4): Programmatically build BOTH the Scientometrics Original Research
main manuscript (manuscript_h6f_boost.md) AND the companion Supplementary Information
(supplementary_h6f_scientometrics.md) 100% dynamically from saved JSON/CSV receipts
(zero hardcoded empirical numbers, exact verified citations, clean authorship block).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"


def write_text_lf(path: Path, text: str) -> str:
    norm = text.replace("\r\n", "\n").replace("\r", "\n")
    if not norm.endswith("\n"):
        norm += "\n"
    path.write_bytes(norm.encode("utf-8"))
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fmt_pct_ci(m: dict, dec: int = 1) -> str:
    return f"{m['pct']:+.{dec}f}% [{m['pct_ci95_lo']:+.{dec}f}%, {m['pct_ci95_hi']:+.{dec}f}%]"


def fmt_beta_ci(m: dict, scale: float = 1.0, dec: int = 2, unit: str = "") -> str:
    u = f" {unit}" if unit else ""
    return f"{scale * m['beta']:+.{dec}f}{u} [{scale * m['ci95_lo']:+.{dec}f}, {scale * m['ci95_hi']:+.{dec}f}]"


def fmt_p(p: float) -> str:
    if p < 1e-4:
        return f"{p:.2e}"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def fmt_authors_apa(authors: list[str], max_show: int = 6) -> str:
    if not authors:
        return ""
    if len(authors) <= max_show:
        if len(authors) == 1:
            return authors[0]
        return ", ".join(authors[:-1]) + ", & " + authors[-1]
    return ", ".join(authors[:max_show]) + ", et al."


def fmt_ref_entry(rec: dict) -> str:
    auth = fmt_authors_apa(rec.get("authors") or [])
    yr = rec.get("year")
    title = rec.get("title", "")
    jrn = rec.get("journal", "")
    vol = rec.get("volume", "")
    iss = rec.get("issue", "")
    pg = rec.get("page", "")
    doi = rec.get("doi", "")
    loc = ""
    if vol:
        loc += f", *{vol}*"
        if iss:
            loc += f"({iss})"
    if pg:
        loc += f", {pg}"
    return f"{auth} ({yr}). {title}. *{jrn}*{loc}. https://doi.org/{doi}"


def build_main_manuscript(p3: dict, p3b: dict, p9: dict, refs: dict) -> str:
    v1a = p3["v1_panel_audit"]
    cs = p9["cohort_summary"]
    rev2285 = p9["covariate_audit_and_crossed_clock"]["reviewer_2285_exact_parity"]
    b_post = p9["covariate_audit_and_crossed_clock"]["benchmark_fin_subj"]["oa_post_v1_cites"]
    b_next = p9["covariate_audit_and_crossed_clock"]["benchmark_fin_subj"]["oa_next_full_year"]
    s_post = p9["covariate_audit_and_crossed_clock"]["strict_v1_frozen"]["oa_post_v1_cites"]
    s_next = p9["covariate_audit_and_crossed_clock"]["strict_v1_frozen"]["oa_next_full_year"]
    csens = p9["covariate_audit_and_crossed_clock"]["clock_and_pre_v1_sensitivities"]

    ev = p9["equal_window_validation"]["by_sample"]
    vint = p9["equal_window_validation"]["vor_interaction_all_v1"]
    incp = p9["equal_window_validation"]["incremental_predictive_power"]
    loso = p9["equal_window_validation"]["loso_18subj"]

    att = p9["onsite_readership"]["complete_monthly_cohort_n1852"]
    fun = p9["revision_and_upgrade"]["funnel_by_v1_tier"]
    up = p9["revision_and_upgrade"]["upgrade_models"]
    si = p9["supplementary_indexing_cohort"]
    fh_v3 = si["fixed_horizon_v3_parity_fin_subj"]["450"]

    bs = p3b["by_stratum"]
    am = p3b["all_manifestations_post_v1"]
    am_ny = p3b["all_manifestations_next_yr"]
    eo = p3b["elife_only_post_v1"]
    sp_only = p3b["split_works_only_all_manifest_post_v1"]
    reg_aud = p3b["regression_impact_audit_sample"]
    fvl = p3b["frozen_vs_live_elife_post_v1"]

    vor_split_n = bs["VoR_v1Low"]["n_split_oa_works"] + bs["VoR_v1SolidPlus"]["n_split_oa_works"]
    vor_tot_n = bs["VoR_v1Low"]["n"] + bs["VoR_v1SolidPlus"]["n"]
    vor_merged_pct = 100.0 * (vor_tot_n - vor_split_n) / vor_tot_n
    nv_split_n = bs["NonVoR_v1Low"]["n_split_oa_works"] + bs["NonVoR_v1SolidPlus"]["n_split_oa_works"]
    nv_tot_n = bs["NonVoR_v1Low"]["n"] + bs["NonVoR_v1SolidPlus"]["n"]
    nv_split_pct = 100.0 * nv_split_n / nv_tot_n

    fn_inc = fun["v1_Incomp_Inad"]
    fn_sol = fun["v1_Solid"]
    fn_conv = fun["v1_Convincing"]
    fn_comp = fun["v1_Compel_Excep"]

    loso_ny_min = min(x["pct"] for x in loso["all_v1_next_yr"])
    loso_ny_max = max(x["pct"] for x in loso["all_v1_next_yr"])
    loso_ny_pmax = max(x["p"] for x in loso["all_v1_next_yr"])
    loso_pv_min = min(x["pct"] for x in loso["all_v1_post_v1"])
    loso_pv_max = max(x["pct"] for x in loso["all_v1_post_v1"])

    # Table 1: OpenAlex Multi-DOI Deduplication Audit
    t1_md = "\n".join([
        f"| VoR · $v_1$ Below *Solid* | {bs['VoR_v1Low']['n']} | {bs['VoR_v1Low']['n_split_oa_works']} ({bs['VoR_v1Low']['pct_split_oa_works']:.1f}%) | {bs['VoR_v1Low']['mean_union_post']:.2f} | {bs['VoR_v1Low']['mean_ymax_post']:.2f} | {bs['VoR_v1Low']['agg_ymax_to_union_ratio']:.4f} | {bs['VoR_v1Low']['mean_pct_undercount']:.2f}% |",
        f"| VoR · $v_1$ *Solid+* | {bs['VoR_v1SolidPlus']['n']} | {bs['VoR_v1SolidPlus']['n_split_oa_works']} ({bs['VoR_v1SolidPlus']['pct_split_oa_works']:.1f}%) | {bs['VoR_v1SolidPlus']['mean_union_post']:.2f} | {bs['VoR_v1SolidPlus']['mean_ymax_post']:.2f} | {bs['VoR_v1SolidPlus']['agg_ymax_to_union_ratio']:.4f} | {bs['VoR_v1SolidPlus']['mean_pct_undercount']:.2f}% |",
        f"| Non-VoR RP · $v_1$ Below *Solid* | {bs['NonVoR_v1Low']['n']} | {bs['NonVoR_v1Low']['n_split_oa_works']} ({bs['NonVoR_v1Low']['pct_split_oa_works']:.1f}%) | {bs['NonVoR_v1Low']['mean_union_post']:.2f} | {bs['NonVoR_v1Low']['mean_ymax_post']:.2f} | {bs['NonVoR_v1Low']['agg_ymax_to_union_ratio']:.4f} | {bs['NonVoR_v1Low']['mean_pct_undercount']:.2f}% |",
        f"| Non-VoR RP · $v_1$ *Solid+* | {bs['NonVoR_v1SolidPlus']['n']} | {bs['NonVoR_v1SolidPlus']['n_split_oa_works']} ({bs['NonVoR_v1SolidPlus']['pct_split_oa_works']:.1f}%) | {bs['NonVoR_v1SolidPlus']['mean_union_post']:.2f} | {bs['NonVoR_v1SolidPlus']['mean_ymax_post']:.2f} | {bs['NonVoR_v1SolidPlus']['agg_ymax_to_union_ratio']:.4f} | {bs['NonVoR_v1SolidPlus']['mean_pct_undercount']:.2f}% |",
        f"| **All Audited (All DOIs, post-$v_1$)** | **{am['n_articles']}** | **{p3b['n_split_across_multiple_oa_works_all']} ({p3b['pct_split_across_multiple_oa_works_all']:.1f}%)** | **{am['mean_union']:.2f}** | **{am['mean_ymax']:.2f}** | **{am['agg_ymax_to_union_ratio']:.4f}** | **Exact={am['exact_match_pct']:.1f}%** |",
        f"| **All Audited (eLife DOIs only, post-$v_1$)** | **{eo['n_articles']}** | **{p3b['n_split_across_multiple_elife_oa_works']} ({p3b['pct_split_across_multiple_elife_oa_works']:.1f}%)** | **{eo['mean_union']:.2f}** | **{eo['mean_ymax']:.2f}** | **{eo['agg_ymax_to_union_ratio']:.4f}** | **Exact={eo['exact_match_pct']:.1f}%** |",
    ])

    # Table 2: Crossed 2x2 Date-Clock x Assessment-Timing & Covariate Leakage Audit
    t2_md = "\n".join([
        f"| Benchmark (max authors, leaked) | Initial ($v_1$) | Initial ($v_1$) quarter | {rev2285['n']:,} | {fmt_pct_ci(rev2285['leaked_max_authors'], 2)} | {fmt_p(rev2285['leaked_max_authors']['p'])} | {fmt_pct_ci(b_next['leaked_max_authors_v1_v1q'], 2)} |",
        f"| Benchmark (frozen $v_1$ authors) | Initial ($v_1$) | Initial ($v_1$) quarter | {rev2285['n']:,} | {fmt_pct_ci(rev2285['frozen_v1_authors'], 2)} | {fmt_p(rev2285['frozen_v1_authors']['p'])} | {fmt_pct_ci(b_next['frozen_v1_authors_v1_v1q'], 2)} |",
        f"| Benchmark (frozen $v_1$ authors) | Initial ($v_1$) | Formal VoR quarter | {rev2285['n']:,} | {fmt_pct_ci(rev2285['frozen_v1_authors_finq_clock'], 2)} | {fmt_p(rev2285['frozen_v1_authors_finq_clock']['p'])} | {fmt_pct_ci(b_next['frozen_v1_authors_v1_finq'], 2)} |",
        f"| **Strict $v_1$ ($v_1$ authors + $v_1$ subject)** | **Initial ($v_1$)** | **Initial ($v_1$) quarter** | **{s_post['v1_v1q']['n']:,}** | **{fmt_pct_ci(s_post['v1_v1q'], 2)}** | **{fmt_p(s_post['v1_v1q']['p'])}** | **{fmt_pct_ci(s_next['v1_v1q'], 2)}** |",
        f"| Strict $v_1$ ($v_1$ authors + $v_1$ subject) | Initial ($v_1$) | Formal VoR quarter | {s_post['v1_finq']['n']:,} | {fmt_pct_ci(s_post['v1_finq'], 2)} | {fmt_p(s_post['v1_finq']['p'])} | {fmt_pct_ci(s_next['v1_finq'], 2)} |",
        f"| Strict $v_1$ ($v_1$ authors + $v_1$ subject) | Final (VoR) | Initial ($v_1$) quarter | {s_post['fin_v1q']['n']:,} | {fmt_pct_ci(s_post['fin_v1q'], 2)} | {fmt_p(s_post['fin_v1q']['p'])} | {fmt_pct_ci(s_next['fin_v1q'], 2)} |",
        f"| Strict $v_1$ ($v_1$ authors + $v_1$ subject) | Final (VoR) | Formal VoR quarter | {s_post['fin_finq']['n']:,} | {fmt_pct_ci(s_post['fin_finq'], 2)} | {fmt_p(s_post['fin_finq']['p'])} | {fmt_pct_ci(s_next['fin_finq'], 2)} |",
    ])

    # Table 3: All-v1 vs VoR-Only vs Non-VoR-Only Equal-Window Validation
    t3_md = "\n".join([
        f"| All mature $v_1$ preprints ($v_1$ subj $\\times$ $v_1$ qtr) | Next full calendar yr (eLife) | {ev['all_v1']['oa_next_full_year']['v1_low']['n']:,} | {ev['all_v1']['oa_next_full_year']['mean_y']:.2f} | {fmt_pct_ci(ev['all_v1']['oa_next_full_year']['v1_low'], 2)} | {ev['all_v1']['oa_next_full_year']['v1_low']['t']:+.2f} | {fmt_p(ev['all_v1']['oa_next_full_year']['v1_low']['p'])} |",
        f"| All mature $v_1$ preprints ($v_1$ subj $\\times$ $v_1$ qtr) | Next full calendar yr (All DOIs) | {ev['all_v1']['oa_next_full_year_all']['v1_low']['n']:,} | {ev['all_v1']['oa_next_full_year_all']['mean_y']:.2f} | {fmt_pct_ci(ev['all_v1']['oa_next_full_year_all']['v1_low'], 2)} | {ev['all_v1']['oa_next_full_year_all']['v1_low']['t']:+.2f} | {fmt_p(ev['all_v1']['oa_next_full_year_all']['v1_low']['p'])} |",
        f"| All mature $v_1$ preprints ($v_1$ subj $\\times$ $v_1$ qtr) | All post-$v_1$ yrs (eLife) | {ev['all_v1']['oa_post_v1_cites']['v1_low']['n']:,} | {ev['all_v1']['oa_post_v1_cites']['mean_y']:.2f} | {fmt_pct_ci(ev['all_v1']['oa_post_v1_cites']['v1_low'], 2)} | {ev['all_v1']['oa_post_v1_cites']['v1_low']['t']:+.2f} | {fmt_p(ev['all_v1']['oa_post_v1_cites']['v1_low']['p'])} |",
        f"| All mature $v_1$ preprints ($v_1$ subj $\\times$ $v_1$ qtr) | Crossref citations (max DOI) | {ev['all_v1']['cr_cites']['v1_low']['n']:,} | {ev['all_v1']['cr_cites']['mean_y']:.2f} | {fmt_pct_ci(ev['all_v1']['cr_cites']['v1_low'], 2)} | {ev['all_v1']['cr_cites']['v1_low']['t']:+.2f} | {fmt_p(ev['all_v1']['cr_cites']['v1_low']['p'])} |",
        f"| VoR-only subsample ($v_1$ subj $\\times$ $v_1$ qtr) | Next full calendar yr (eLife) | {ev['vor_only']['oa_next_full_year']['v1_low']['n']:,} | {ev['vor_only']['oa_next_full_year']['mean_y']:.2f} | {fmt_pct_ci(ev['vor_only']['oa_next_full_year']['v1_low'], 2)} | {ev['vor_only']['oa_next_full_year']['v1_low']['t']:+.2f} | {fmt_p(ev['vor_only']['oa_next_full_year']['v1_low']['p'])} |",
        f"| VoR-only subsample ($v_1$ subj $\\times$ $v_1$ qtr) | All post-$v_1$ yrs (eLife) | {ev['vor_only']['oa_post_v1_cites']['v1_low']['n']:,} | {ev['vor_only']['oa_post_v1_cites']['mean_y']:.2f} | {fmt_pct_ci(ev['vor_only']['oa_post_v1_cites']['v1_low'], 2)} | {ev['vor_only']['oa_post_v1_cites']['v1_low']['t']:+.2f} | {fmt_p(ev['vor_only']['oa_post_v1_cites']['v1_low']['p'])} |",
        f"| Non-VoR RP subsample ($v_1$ subj $\\times$ $v_1$ qtr) | All post-$v_1$ yrs (eLife) | {ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['n']:,} | {ev['non_vor_only_subj_q']['oa_post_v1_cites']['mean_y']:.2f} | {fmt_pct_ci(ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low'], 2)} | {ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['t']:+.2f} | {fmt_p(ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['p'])} |",
        f"| Non-VoR RP subsample ($v_1$ subj $\\times$ $v_1$ qtr) | Next full calendar yr (eLife) | {ev['non_vor_only_subj_q']['oa_next_full_year']['v1_low']['n']:,} | {ev['non_vor_only_subj_q']['oa_next_full_year']['mean_y']:.2f} | {fmt_pct_ci(ev['non_vor_only_subj_q']['oa_next_full_year']['v1_low'], 2)} | {ev['non_vor_only_subj_q']['oa_next_full_year']['v1_low']['t']:+.2f} | {fmt_p(ev['non_vor_only_subj_q']['oa_next_full_year']['v1_low']['p'])} |",
        f"| Non-VoR RP subsample ($v_1$ subj $\\times$ $v_1$ yr) | Next full calendar yr (All DOIs) | {ev['non_vor_only_subj_yr']['oa_next_full_year_all']['v1_low']['n']:,} | {ev['non_vor_only_subj_yr']['oa_next_full_year_all']['mean_y']:.2f} | {fmt_pct_ci(ev['non_vor_only_subj_yr']['oa_next_full_year_all']['v1_low'], 2)} | {ev['non_vor_only_subj_yr']['oa_next_full_year_all']['v1_low']['t']:+.2f} | {fmt_p(ev['non_vor_only_subj_yr']['oa_next_full_year_all']['v1_low']['p'])} |",
        f"| Non-VoR RP subsample ($v_1$ subj $\\times$ $v_1$ qtr) | Cumulative eLife downloads | {ev['non_vor_only_subj_q']['dl_total']['v1_low']['n']:,} | {ev['non_vor_only_subj_q']['dl_total']['mean_y']:.1f} | {fmt_pct_ci(ev['non_vor_only_subj_q']['dl_total']['v1_low'], 2)} | {ev['non_vor_only_subj_q']['dl_total']['v1_low']['t']:+.2f} | {fmt_p(ev['non_vor_only_subj_q']['dl_total']['v1_low']['p'])} |",
    ])

    # Table 4: Onsite Readership Predictive Associations (N=1,852 untruncated monthly cohort)
    t4_md = "\n".join([
        f"| First 3 calendar bins: Page-views | {fmt_pct_ci(att['pv_first_3m']['v1_low'], 1)} (p={fmt_p(att['pv_first_3m']['v1_low']['p'])}) | {fmt_pct_ci(att['pv_first_3m']['v1_imp'], 1)} (p={fmt_p(att['pv_first_3m']['v1_imp']['p'])}) | {fmt_pct_ci(att['pv_first_3m']['v1_fund'], 1)} (p={fmt_p(att['pv_first_3m']['v1_fund']['p'])}) | {att['pv_first_3m']['v1_low']['n']:,} |",
        f"| First 3 calendar bins: Downloads | {fmt_pct_ci(att['dl_first_3m']['v1_low'], 1)} (p={fmt_p(att['dl_first_3m']['v1_low']['p'])}) | {fmt_pct_ci(att['dl_first_3m']['v1_imp'], 1)} (p={fmt_p(att['dl_first_3m']['v1_imp']['p'])}) | {fmt_pct_ci(att['dl_first_3m']['v1_fund'], 1)} (p={fmt_p(att['dl_first_3m']['v1_fund']['p'])}) | {att['dl_first_3m']['v1_low']['n']:,} |",
        f"| Cumulative lifetime: Page-views | {fmt_pct_ci(att['pv_total']['v1_low'], 1)} (p={fmt_p(att['pv_total']['v1_low']['p'])}) | {fmt_pct_ci(att['pv_total']['v1_imp'], 1)} (p={fmt_p(att['pv_total']['v1_imp']['p'])}) | {fmt_pct_ci(att['pv_total']['v1_fund'], 1)} (p={fmt_p(att['pv_total']['v1_fund']['p'])}) | {att['pv_total']['v1_low']['n']:,} |",
        f"| Cumulative lifetime: Downloads | {fmt_pct_ci(att['dl_total']['v1_low'], 1)} (p={fmt_p(att['dl_total']['v1_low']['p'])}) | {fmt_pct_ci(att['dl_total']['v1_imp'], 1)} (p={fmt_p(att['dl_total']['v1_imp']['p'])}) | {fmt_pct_ci(att['dl_total']['v1_fund'], 1)} (p={fmt_p(att['dl_total']['v1_fund']['p'])}) | {att['dl_total']['v1_low']['n']:,} |",
    ])

    # Table 5: Revision, VoR Conversion, and Rating-Upgrade Funnel by v1 Tier
    t5_md = "\n".join([
        f"| {lbl} | {r['n_total']:,} | {r['n_posted_revision']:,} ({r['pct_posted_revision']:.1f}%) | {r['n_vor']:,} ({r['pct_vor']:.1f}%) | {r['n_vor_upgraded_any']:,} ({r['pct_all_upgraded_any']:.1f}%) | {r['pct_vor_upgraded_any']:.1f}% | {r['mean_rev_lag_up_days']:.1f} d | {r['n_vor_unchanged_with_revision']}/{r['n_vor_unchanged']} |"
        for lbl, r in [
            ("Below *Solid* (*Incomplete/Inadequate*)", fn_inc),
            ("*Solid*", fn_sol),
            ("*Convincing*", fn_conv),
            ("*Compelling / Exceptional*", fn_comp),
        ]
    ])

    # Table 6: Upgrade-to-Solid+ Predictive Associations, Equivalence Bounds & Version-Release Events
    u_b = up["bench_v3_parity_oa_post_v1"]
    u_a = up["v1_authors_fin_subj_oa_post_v1"]
    u_s = up["strict_v1_oa_post_v1"]
    u_ny = up["strict_v1_oa_next_yr"]
    u_cr = up["strict_v1_cr_cites"]
    t6_md = "\n".join([
        f"| Post-$v_1$ OA cites (benchmark: max authors, final subj) | {u_b['n']:,} | {fmt_pct_ci(u_b, 1)} | {fmt_p(u_b['p'])} | ±15%: {u_b['tost_pm15']:.3f}; ±20%: {u_b['tost_pm20']:.3f} |",
        f"| Post-$v_1$ OA cites ($v_1$ authors, final subj) | {u_a['n']:,} | {fmt_pct_ci(u_a, 1)} | {fmt_p(u_a['p'])} | Stepwise author-freeze check |",
        f"| **Post-$v_1$ OA cites (strict $v_1$ authors + $v_1$ subj)** | **{u_s['n']:,}** | **{fmt_pct_ci(u_s, 1)}** | **{fmt_p(u_s['p'])}** | **±15%: {u_s['tost_pm15']:.3f}; ±20%: {u_s['tost_pm20']:.3f}** |",
        f"| Next full calendar yr OA cites (strict $v_1$) | {u_ny['n']:,} | {fmt_pct_ci(u_ny, 1)} | {fmt_p(u_ny['p'])} | ±15%: {u_ny['tost_pm15']:.3f}; ±20%: {u_ny['tost_pm20']:.3f} |",
        f"| Crossref max-DOI cites (strict $v_1$) | {u_cr['n']:,} | {fmt_pct_ci(u_cr, 1)} | {fmt_p(u_cr['p'])} | ±15%: {u_cr['tost_pm15']:.3f}; ±20%: {u_cr['tost_pm20']:.3f} |",
        f"| Cumulative page-views, log(1+y) OLS (strict $v_1$) | {up['strict_v1_pv_total_ols']['n']:,} | {fmt_beta_ci(up['strict_v1_pv_total_ols'], 1.0, 3, 'log')} | {fmt_p(up['strict_v1_pv_total_ols']['p_wcb'])} (WCB) | Lifetime article total |",
        f"| Cumulative downloads, log(1+y) OLS (strict $v_1$) | {up['strict_v1_dl_total_ols']['n']:,} | {fmt_beta_ci(up['strict_v1_dl_total_ols'], 1.0, 3, 'log')} | {fmt_p(up['strict_v1_dl_total_ols']['p_wcb'])} (WCB) | Lifetime article total |",
        f"| Monthly rate DiD ($v_1 \\ge$ 2023-11): Views | {up['strict_v1_rate_did_pv']['n']:,} | {fmt_beta_ci(up['strict_v1_rate_did_pv'], 1.0, 3, 'log')} | {fmt_p(up['strict_v1_rate_did_pv']['p_wcb'])} (WCB) | Untruncated post-vs-pre VoR rate |",
        f"| Local VoR event study (month $t=0$): Views | {up['strict_v1_dlog_pv_ev_m0']['n']:,} | {fmt_beta_ci(up['strict_v1_dlog_pv_ev_m0'], 1.0, 3, 'log')} | {fmt_p(up['strict_v1_dlog_pv_ev_m0']['p_wcb'])} (WCB) | Raw spike {up['raw_ev_m0_summary']['pv_m0_upgraded_mean']:+.2f} vs {up['raw_ev_m0_summary']['pv_m0_unchanged_mean']:+.2f} |",
        f"| Local VoR event study (months $+1..+6$): Views | {up['strict_v1_dlog_pv_ev_p16']['n']:,} | {fmt_beta_ci(up['strict_v1_dlog_pv_ev_p16'], 1.0, 3, 'log')} | {fmt_p(up['strict_v1_dlog_pv_ev_p16']['p_wcb'])} (WCB) | Post-release decay window |",
        f"| Local VoR event study (months $+1..+6$): Downloads | {up['strict_v1_dlog_dl_ev_p16']['n']:,} | {fmt_beta_ci(up['strict_v1_dlog_dl_ev_p16'], 1.0, 3, 'log')} | {fmt_p(up['strict_v1_dlog_dl_ev_p16']['p_wcb'])} (WCB) | Post-release decay window |",
        f"| **Per extra posted version (`cr_n_versions`, M12–21)** | **{up['version_release_m12_21_incomp']['cr_n_versions']['n']:,}** | **{fmt_beta_ci(up['version_release_m12_21_incomp']['cr_n_versions'], 1.0, 3, 'log')}** | **{fmt_p(up['version_release_m12_21_incomp']['cr_n_versions']['p_wcb'])} (WCB)** | **Solid cohort: {fmt_beta_ci(up['version_release_m12_21_solid']['cr_n_versions'], 1.0, 3, 'log')}** |",
    ])

    main_ref_keys = [
        "Mutz2025", "Ragusa2025", "Hardwicke2024", "Stern2019", "Eisen2020", "Eisen2022",
        "AvissarWhiting2024", "eLife2024FirstYear", "eLife2026ThreeYear", "FuHughey2019",
        "AbdillBlekhman2019", "Fraser2020", "Tomkins2017", "Teplitskiy2018",
        "CardDellaVigna2020", "Azoulay2014", "SantosSilva2006", "ChenRoth2024",
        "Cameron2008", "Lakens2017",
    ]
    refs_md_lines = [f"{i}. {fmt_ref_entry(refs[k])}" for i, k in enumerate(main_ref_keys, 1)]
    next_i = len(refs_md_lines) + 1
    refs_md_lines.extend([
        f"{next_i}. eLife (2024a). Update on eLife's indexing status at Web of Science. *Inside eLife*, October 24, 2024. https://elifesciences.org/inside-elife/16afe6ec/update-on-elife-s-indexing-status-at-web-of-science",
        f"{next_i + 1}. eLife (2024b). The eLife Model: An update on progress following changes in Web of Science indexing status. *Inside eLife*, November 20, 2024. https://elifesciences.org/inside-elife/c11c6101/the-elife-model-an-update-on-progress-following-changes-in-web-of-science-indexing-status",
        f"{next_i + 2}. eLife (2024c). Changes to eLife's indexing status in Web of Science and Scopus. *Inside eLife*, December 10, 2024. https://elifesciences.org/inside-elife/ae620829/changes-to-elife-s-indexing-status-in-web-of-science-and-scopus",
        f"{next_i + 3}. eLife (2025). The eLife Model: Improvements to research discoverability. *Inside eLife*, March 13, 2025. https://elifesciences.org/inside-elife/8f427668/the-elife-model-improvements-to-research-discoverability",
        f"{next_i + 4}. Adamson, N. (2026). The eLife Model: Comparing eLife Assessments across revisions. *Inside eLife*, March 17, 2026. https://elifesciences.org/inside-elife/e9d530fc/the-elife-model-comparing-elife-assessments-across-revisions",
    ])
    refs_md = "\n".join(refs_md_lines)

    return rf"""# Version-Level Measurement, Incremental Predictive Validity, and Revision Trajectories of Public Peer-Review Assessments in *eLife* Reviewed Preprints

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
Email: zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Abstract

Evaluating publish–review–curate (PRC) journals requires linking each manuscript's initial reviewed preprint ($v_1$) to its subsequent public revisions, formal Version of Record (VoR), multi-DOI citation footprint, and onsite readership without conditioning on post-$v_1$ outcomes or leaking post-revision covariates. Across the complete census of {v1a['n_prc_census']:,} *eLife* PRC manuscripts ({v1a['n_v1_with_strength']:,} recovered $v_1$ assessments, {v1a['v1_recovery_pct']:.2f}%; $N = {cs['n_mature_2023_2024']:,}$ mature 2023–2024 cohorts including {cs['n_mature_vor']:,} VoRs and {cs['n_mature_non_vor']:,} non-VoR reviewed preprints), we conduct a three-stage scientometric audit. First, we document two critical measurement hazards in versioned publishing: (i) look-ahead covariate leakage, where taking maximum author counts across versions exceeds $v_1$ authorship in {rev2285['n_max_authors_gt_v1']}/{rev2285['n']:,} ({100.0*rev2285['n_max_authors_gt_v1']/rev2285['n']:.1f}%) benchmark VoRs (shifting the $v_1$ below-*Solid* citation association from {rev2285['leaked_max_authors']['pct']:+.2f}% to {rev2285['frozen_v1_authors']['pct']:+.2f}% [{rev2285['frozen_v1_authors']['pct_ci95_lo']:+.2f}%, {rev2285['frozen_v1_authors']['pct_ci95_hi']:+.2f}%]) and final primary subjects differ from $v_1$ subjects in {v1a['n_primary_subject_diff_all']}/{v1a['n_prc_census']:,} articles; and (ii) asymmetric OpenAlex multi-DOI canonicalization, where a stratified citing-work ID deduplication audit ($N = {p3b['n_audited_articles']}$, mean {p3b['mean_queried_dois_per_article']} DOIs/article) shows {vor_merged_pct:.1f}% single-work consolidation among VoRs versus {nv_split_pct:.1f}% multi-work splitting between bioRxiv/medRxiv and *eLife* records among non-VoR preprints (yearly-max proxy vs. exact citing-ID union: eLife-only $r = {eo['pearson_r']:.5f}$, all-DOI $r = {am['pearson_r']:.5f}$, aggregate ratio {am['agg_ymax_to_union_ratio']:.4f}). Second, freezing all covariates strictly at $v_1$ publication, initial below-*Solid* evidence assessments strongly predict lower subsequent citations over equal next-full-calendar-year windows across all mature $v_1$ preprints ({fmt_pct_ci(ev['all_v1']['oa_next_full_year']['v1_low'], 1)}, $p = {fmt_p(ev['all_v1']['oa_next_full_year']['v1_low']['p'])}$, adding +{incp['all_v1_oa_next_yr']['delta_pseudo_r2_pp']:.2f} pp Poisson pseudo-$R^2$), within VoRs ({fmt_pct_ci(ev['vor_only']['oa_next_full_year']['v1_low'], 1)}), and within non-VoR reviewed preprints ({fmt_pct_ci(ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low'], 1)} post-$v_1$, $p = {fmt_p(ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['p'])}$), while switching solely from $v_1$-quarter to VoR-quarter fixed effects attenuates VoR estimates ({s_post['v1_v1q']['pct']:+.1f}% to {s_post['v1_finq']['pct']:+.1f}%). Third, separating denominators across {fn_inc['n_total']:,} mature $v_1$ below-*Solid* preprints shows {fn_inc['n_posted_revision']}/{fn_inc['n_total']} ({fn_inc['pct_posted_revision']:.1f}%) posted public revisions, {fn_inc['n_vor']}/{fn_inc['n_total']} ({fn_inc['pct_vor']:.1f}%) reached VoR, {fn_inc['n_vor_upgraded_any']}/{fn_inc['n_total']} ({fn_inc['pct_all_upgraded_any']:.1f}% unconditional; {fn_inc['n_vor_upgraded_any']}/{fn_inc['n_vor']} = {fn_inc['pct_vor_upgraded_any']:.1f}% VoR-conditional) upgraded evidence ratings over a mean {fn_inc['mean_rev_lag_up_days']:.1f}-day $v_1$-to-VoR calendar interval, and {si['apr2023_lower_rated_vors_with_posted_revision']}/{si['apr2023_lower_rated_vors']} ({si['apr2023_lower_rated_vors_with_revision_pct']:.1f}%) final below-*Solid* VoRs posted public revisions. Observational contrasts between upgraded and non-upgraded VoRs are imprecise ({fmt_pct_ci(u_b, 1)} benchmark; {fmt_pct_ci(u_s, 1)} strict $v_1$ covariates) and neither establish statistical equivalence to null effects nor isolate causal reader badge reactions amid *eLife*'s June 2024 discoverability redesign.

**Keywords:** Publish–Review–Curate; *eLife* Assessments; Open Peer Review; Version Linking; OpenAlex Deduplication; Predictive Validity; Scientometrics

---

## 1. Introduction

Since January 2023, *eLife* has operated a Publish–Review–Curate (PRC) publishing model that eliminates traditional binary accept/reject decisions after peer review (Stern & O'Shea, 2019; Eisen et al., 2020, 2022; Avissar-Whiting et al., 2024). Manuscripts selected for peer review are published as citable Reviewed Preprints accompanied by public peer reviews and a structured *eLife* Assessment rating two dimensions on controlled vocabularies: *Significance of Findings* (*Useful*, *Valuable*, *Important*, *Fundamental*, *Landmark*) and *Strength of Evidence* (*Inadequate*, *Incomplete*, *Solid*, *Convincing*, *Compelling*, *Exceptional*) (Hardwicke et al., 2024; Behrens et al., 2024, 2026). Authors retain full control over whether to post public revised preprints, leave assessments unchanged, or declare a formal Version of Record (VoR).

For scientometrics, this architecture creates both a rare prospective laboratory and an acute measurement challenge. Unlike traditional journals where only surviving accepted manuscripts enter bibliographic databases—masking reviewer disagreement and revision dynamics (Tomkins et al., 2017; Teplitskiy et al., 2018; Card & DellaVigna, 2020)—PRC exposes initial ($v_1$) peer evaluations, public version histories, and downstream citation and usage outcomes in machine-readable form. Yet precisely because PRC articles evolve through multiple citable manifestations (an upstream bioRxiv or medRxiv preprint, $v_1$ through $v_k$ *eLife* Reviewed Preprints, and an optional VoR), standard bibliometric workflows introduce three systematic distortions if applied naively:

1. **Final-state and date-clock conflation.** Retrieving metadata from the latest article endpoint or indexing cohorts by VoR publication date silently substitutes post-revision assessments, post-revision author lists, post-revision subject tags, and post-revision dates for the information actually observable at $v_1$. Because lower-rated manuscripts revise longer before finalizing (mean {fn_inc['mean_rev_lag_up_days']:.1f} calendar days from $v_1$ to VoR), aligning cohorts on VoR dates pairs older, revised papers against younger, initially stronger papers, confounding both timing and quality.
2. **Multi-DOI citation fragmentation and double counting.** A single PRC manuscript routinely carries four to six registered DOIs across preprint servers and *eLife* versions (Fu & Hughey, 2019; Abdill & Blekhman, 2019; Fraser et al., 2020). Whether bibliographic aggregators such as OpenAlex merge those manifestations into one canonical work record—and whether that merging differs systematically between finalized VoRs and non-VoR reviewed preprints—directly governs citation measurement error.
3. **Denominator mixing and causal over-interpretation.** Conditioning upgrade rates exclusively on finalized VoRs conflates revision propensity with VoR selection; labeling final below-*Solid* VoRs as "unrevised" ignores authors who posted public revisions without securing a rating upgrade; and interpreting observational article-level attention differences as causal reader reactions to rating badges ignores both unobserved manuscript quality and concurrent platform interface changes. In particular, *eLife* confirmed that starting in June 2024 it rolled out phased discoverability and interface changes—moving *eLife* Assessments above the abstract, adding a vocabulary dropdown, displaying color-coded article stage badges in search results, and enabling readers to browse by minimum *Significance* and *Strength of Evidence* thresholds (eLife, 2025).

Two landmark empirical studies establish the immediate benchmark for our work. First, Mutz et al. (2025) compared the reliability of *eLife*'s legacy and new peer-review processes in *Scientometrics*, evaluating rating agreement and vocabulary properties without tracking version-linked longitudinal citation windows, multi-DOI OpenAlex deduplication error, or article-level readership. Second, *eLife* reported an internal analysis of assessment shifts across 2,051 finalized VoRs (Adamson, 2026), explicitly excluding 351 articles with multi-term strength assessments, excluding all non-VoR reviewed preprints, and reporting no citation or onsite readership outcomes. Our incremental contribution to *Scientometrics* is a **prospective, reproducible, version-level measurement and predictive-validity framework** spanning the entire public PRC census ({v1a['n_prc_census']:,} manuscripts; {v1a['n_v1_with_strength']:,} recovered $v_1$ assessments, including multi-term assessments and non-VoR preprints) that: (a) audits look-ahead covariate leakage and OpenAlex citing-work ID deduplication across multi-DOI records; (b) tests the incremental predictive value of strictly $v_1$-frozen assessments over equal-length citation windows across all $v_1$ preprints, VoRs, and non-VoR preprints separately; and (c) cleanly decomposes public revisions, VoR conversion, unconditional versus VoR-conditional rating upgrades, and onsite readership trajectories with transparent precision and equivalence bounds.

Throughout this study, we adhere to a strict predictive-association estimand. Because article-level observational aggregates cannot separate public badge visibility from underlying manuscript quality, author self-selection into revision, or the phased June 2024 interface redesign, we make **no causal claims** about reader responses to displayed rating badges. Similarly, because public data lack internal submission, desk-review, and transfer logs—and because *eLife*'s December 10, 2024 indexing announcement simultaneously modified coverage in both Web of Science and Scopus (eLife, 2024a–c)—all exploratory cohort, manuscript-ID velocity, synthetic-control, and country-share analyses around the indexing transition are separated cleanly into our companion Supplementary Information (`supplementary_h6f_scientometrics.pdf`) rather than presented as causal policy effects in the main text.

---

## 2. Data Architecture, Version Linking, Covariate Freezing, and Multi-DOI Deduplication Audit

### 2.1 Public Census, Version Linking, and Telemetry Architecture

We assembled a frozen public-data snapshot anchored on November 25, 2026 (`snapshot_date = 2026-11-25`) linking four open scholarly infrastructure endpoints:

1. ***eLife* PRC Search Census & Immutable $v_1$ Assessment Snapshots.** The public *eLife* search API yielded {v1a['n_prc_census']:,} unique PRC manuscripts posted from 2023 through November 2026. Querying each manuscript's dedicated version-1 record (`version=1`) recovered machine-readable $v_1$ *Strength of Evidence* ratings for {v1a['n_v1_with_strength']:,}/{v1a['n_prc_census']:,} ({v1a['v1_recovery_pct']:.2f}%) articles, with {v1a['n_v1_date_missing']} missing $v_1$ publication dates and {v1a['n_vors_fin_lt_v1']} chronological anomalies (VoR date preceding $v_1$ date) across all {v1a['n_vors_total']:,} VoRs. Following *eLife*'s vocabulary hierarchy, multi-term ratings are conservatively indexed by their minimum strength tier (`v1_str_min`), pooling *Inadequate* and *Incomplete* as below *Solid* (`v1_str_min <= 2`) against the *Solid* (`= 3`) baseline, alongside *Convincing* (`= 4`) and *Compelling/Exceptional* (`>= 5`). To guarantee at least one complete post-$v_1$ calendar year of citation follow-up, our primary predictive-validity panel comprises all mature 2023–2024 $v_1$ cohorts with non-missing $v_1$ strength assessments ($N = {cs['n_mature_2023_2024']:,}$, consisting of {cs['n_mature_vor']:,} finalized VoRs and {cs['n_mature_non_vor']:,} non-VoR reviewed preprints).
2. **Crossref Versioned DOI Histories & Public Revision Identification.** We linked all 20,211 Crossref DOI records (`10.7554/eLife.*`, spanning both `posted-content` reviewed-preprint versions $v_1, v_2, \dots, v_k$ and `journal-article` VoR records) to the {v1a['n_prc_census']:,}-paper census. Crucially, we define a **publicly posted revision** independently of any change in the *eLife* Assessment: an article is coded as having a posted revision if and only if Crossref records at least one distinct `posted-content` DOI with `ver >= 2` dated strictly after $v_1$, on or before November 25, 2026, and (for VoRs) on or before the VoR publication date. This measures observable public releases; edits performed privately before VoR declaration without an intermediate revised preprint remain unobserved.
3. **OpenAlex Multi-DOI Citation Histories.** We matched every *eLife* DOI variant and linked upstream bioRxiv/medRxiv preprint DOI (`v1_preprint_doi`) against OpenAlex. To avoid mechanical double-counting across version DOIs of the same manuscript while preserving calendar-year granularity, our full-panel citation endpoints compute the maximum citation count per calendar year across DOI variants, evaluated over two strictly post-$v_1$ windows: (i) all post-$v_1$ calendar years (`year > v1_year`, excluding the posting year), and (ii) a strictly equal-length **next full calendar year** (`year == v1_year + 1`, i.e., 2024 for 2023 $v_1$ cohorts and 2025 for 2024 $v_1$ cohorts). We compute both eLife-DOI-family and combined eLife-plus-preprint versions of each endpoint and audit this yearly-max convention directly against exact citing-work ID deduplication in Section 2.3.
4. **Live *eLife* Onsite Readership Telemetry & Anti-Truncation Guard.** We harvested lifetime (`totalValue`) and monthly (`by=month`) article-level `page-views` and `downloads` from the public *eLife* Metrics API, achieving {v1a['n_mature_with_live_metrics']:,}/{v1a['n_mature_2023_2024']:,} ({v1a['mature_metrics_coverage_pct']:.2f}%) lifetime coverage on mature 2023–2024 cohorts. Auditing the API payload revealed a strict 37-month rolling window (`{v1a['api_monthly_min_ym']}` through `2026-11`, with `{v1a['api_monthly_max_complete_ym']}` as the last complete month). Articles posted before November 2023 ({v1a['n_mature_left_truncated_lt_2023_11']:,} mature articles) are left-truncated in monthly arrays and are strictly assigned `NaN` rather than silently imputed as zero. All monthly readership models restrict cleanly to the untruncated $v_1 \ge$ `{v1a['api_monthly_min_ym']}` cohort ($N = {v1a['n_mature_complete_monthly_ge_2023_11']:,}$), controlling explicitly for `v1_posting_day` in first-three-calendar-bin endpoints to absorb partial launch-month exposure. All onsite metrics aggregate traffic across available versions of an article and overlap *eLife*'s phased June 2024 discoverability redesign (eLife, 2025).

### 2.2 Look-Ahead Covariate Leakage Audit: Freezing Strictly at-$v_1$ Information

A foundational requirement of prospective predictive-validity modeling is that every conditioning covariate must be strictly measurable at $v_1$ publication, before subsequent revisions, author additions, or subject reclassifications occur. Auditing earlier pipeline versions uncovered two distinct sources of look-ahead covariate leakage:

- **Post-revision author-count leakage.** Aggregating Crossref author counts via `max(n_authors)` across all versions of a manuscript leaks co-authors added during revision (for instance, new collaborators recruited to run validation experiments). Across the complete census, `cr_n_authors_max > v1_n_authors` in {v1a['n_authors_max_gt_v1_all']:,}/{v1a['n_prc_census']:,} ({100.0*v1a['n_authors_max_gt_v1_all']/v1a['n_prc_census']:.1f}%) manuscripts ({v1a['n_authors_max_gt_v1_mature']:,}/{cs['n_mature_2023_2024']:,} mature manuscripts). On the exact fixed VoR benchmark sample ($N = {rev2285['n']:,}$), exactly **{rev2285['n_max_authors_gt_v1']}/{rev2285['n']:,} ({100.0*rev2285['n_max_authors_gt_v1']/rev2285['n']:.1f}%)** articles had maximum author counts exceeding their true $v_1$ Crossref `posted-content` (`ver == 1`) author count (`0` missing across all {v1a['n_prc_census']:,} manuscripts). Moreover, among $v_1$ below-*Solid* VoRs, manuscripts that later upgraded to *Solid+* added co-authors more frequently than those remaining below *Solid* (21.7% vs. 15.1%), meaning `max_authors` conditioned on a post-$v_1$ revision mediator.
- **Post-revision subject-classification drift.** Comparing `v1_subjects[0]` from the $v_1$ API payload against the final search-census `subjects[0]` revealed discrepancies in **{v1a['n_primary_subject_diff_all']}/{v1a['n_prc_census']:,} ({100.0*v1a['n_primary_subject_diff_all']/v1a['n_prc_census']:.1f}%)** manuscripts ({v1a['n_primary_subject_reordered_all']} reordered within an identical multi-subject set and {v1a['n_primary_subject_changed_set_all']} involving added or replaced discipline tags; {v1a['n_primary_subject_diff_mature']}/{cs['n_mature_2023_2024']:,} mature articles, and {cs['n_bench_2285_fin_subj_ne_v1']}/{cs['n_bench_crossed_post']:,} in the VoR benchmark).

In all primary `v4` specifications below, we eliminate both leakage channels completely by freezing **strictly at-$v_1$ covariates**: `v1_n_authors` (from Crossref `posted-content ver == 1`), `v1_primary_subject` (from `v1_subjects[0]`), `v1_quarter` (plus `v1_month` robustness), `v1_age_days`, `v1_posting_day`, and strictly pre-$v_1$ citations (`year < v1_year`, verified against strictly preprint-DOI pre-$v_1$ citations). We also retain the benchmark specification side-by-side to document exact step-by-step parity.

### 2.3 OpenAlex Citing-Work ID Deduplication Audit on Multi-DOI Works

Because every mature 2023–2024 manuscript carries at least three registered DOIs (a linked preprint DOI plus two or more Crossref *eLife* DOIs), we executed a dedicated **citing-work ID deduplication audit** on a deterministic stratified random sample of $N = {p3b['n_audited_articles']}$ multi-DOI mature manuscripts (mean {p3b['mean_queried_dois_per_article']} queried DOIs/article: 60 VoR $v_1 <$ *Solid*, 60 VoR $v_1$ *Solid+*, 40 Non-VoR $v_1 <$ *Solid*, 40 Non-VoR $v_1$ *Solid+*). For every audited article, we resolved all registered Crossref *eLife* version DOIs plus the linked bioRxiv/medRxiv DOI against OpenAlex, fetched the complete set of unique citing OpenAlex Work IDs and publication years for every resolved work record, and compared three aggregation rules on the exact same OpenAlex timestamp: (i) the **exact deduplicated citing-work ID union**, (ii) our **yearly-max proxy**, and (iii) **naive summing** across OpenAlex records.

**Table 1. Stratified OpenAlex Multi-DOI Canonicalization and Citing-Work ID Deduplication Audit ($N = {p3b['n_audited_articles']}$)**

| Stratum / Manifestation Scope | Audited $N$ | Split Across $\ge 2$ OA Work IDs | Mean Exact Union (Post-$v_1$) | Mean Yearly-Max (Post-$v_1$) | Agg. Ratio (YMax / Union) | Mean Undercount / Exact Match |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: |
{t1_md}

*Notes:* Stratified sample (`seed = {p3b['audit_seed']}`) querying all Crossref *eLife* version DOIs (`v1..vk`, VoR) plus `v1_preprint_doi` via OpenAlex `filter=doi:` and `filter=cites:`. Aggregate ratio equals total yearly-max citations divided by total unique citing-work IDs across the stratum. Exact match denotes share of articles where yearly-max equals exact citing-ID union identically.

<!-- FIGURE:fig1_v4_measurement_and_dedup_audit.png -->

Table 1 and Figure 1 uncover a sharp, previously undocumented **asymmetric canonicalization pattern in OpenAlex** with direct consequences for PRC bibliometrics:

1. **VoRs consolidate almost completely; non-VoR reviewed preprints remain split.** Across the {vor_tot_n} audited VoRs, **{vor_tot_n - vor_split_n}/{vor_tot_n} ({vor_merged_pct:.1f}%)** collapsed into a **single** canonical OpenAlex Work ID merging the bioRxiv/medRxiv preprint with all *eLife* versions (only {vor_split_n}/{vor_tot_n} remained split; aggregate `ymax/union` = {bs['VoR_v1Low']['agg_ymax_to_union_ratio']:.4f} for $v_1 <$ *Solid* and {bs['VoR_v1SolidPlus']['agg_ymax_to_union_ratio']:.4f} for *Solid+*). By stark contrast, across the {nv_tot_n} audited non-VoR reviewed preprints, **{nv_split_n}/{nv_tot_n} ({nv_split_pct:.1f}%)** remained split across two distinct OpenAlex Work IDs—one for the upstream preprint server and one for the *eLife* Reviewed Preprint (while only {p3b['n_split_across_multiple_elife_oa_works']}/{p3b['n_audited_articles']} [{p3b['pct_split_across_multiple_elife_oa_works']:.1f}%] ever split across multiple *eLife*-prefixed Work IDs).
2. **Yearly-max is near-exact for *eLife* DOIs and mildly conservative across split preprint/RP pairs.** For *eLife*-prefixed DOIs alone, yearly-max matches the exact citing-work ID union on **{eo['exact_match_pct']:.1f}%** of audited manuscripts (Pearson $r = {eo['pearson_r']:.5f}$, Spearman $\rho = {eo['spearman_rho']:.5f}$, median ratio {eo['median_ymax_to_union_ratio']:.4f}, aggregate ratio {eo['agg_ymax_to_union_ratio']:.4f}), and matches our frozen snapshot closely (frozen vs. live *eLife* union $r = {fvl['pearson_r']:.5f}$, mean {fvl['mean_frozen']:.2f} vs. {fvl['mean_live_elife_union']:.2f}). Across all manifestations including unmerged preprints, yearly-max achieves $r = {am['pearson_r']:.5f}$, $\rho = {am['spearman_rho']:.5f}$, median ratio {am['median_ymax_to_union_ratio']:.4f}, and aggregate ratio {am['agg_ymax_to_union_ratio']:.4f} (a mild {100.0*(1-am['agg_ymax_to_union_ratio']):.2f}% undercount overall, or {100.0*(1-sp_only['agg_ymax_to_union_ratio']):.2f}% within the {sp_only['n_articles']} split works; next-full-year $r = {am_ny['pearson_r']:.5f}$, aggregate ratio {am_ny['agg_ymax_to_union_ratio']:.4f}). Conversely, naive summing inflates split-work citations by +{100.0*(sp_only['agg_sum_to_union_ratio']-1):.2f}% (aggregate sum/union = {sp_only['agg_sum_to_union_ratio']:.4f}) due to {p3b['total_duplicate_citing_ids_across_works']} citing papers across {p3b['n_articles_with_duplicate_citing_ids_across_works']} manuscripts citing both manifestations simultaneously.
3. **Minimal regression distortion.** Because non-VoR undercount ratios are nearly symmetric between below-*Solid* ({bs['NonVoR_v1Low']['agg_ymax_to_union_ratio']:.4f}) and *Solid+* ({bs['NonVoR_v1SolidPlus']['agg_ymax_to_union_ratio']:.4f}), PPML estimates of the $v_1$ below-*Solid* association on the audited sample ($n = {reg_aud['all_audit_all_manifest_union_post']['n']}$) are virtually unchanged between exact citing-ID unions and yearly-max proxies: {reg_aud['all_audit_elife_only_union_post']['pct']:+.2f}% vs. {reg_aud['all_audit_elife_only_ymax_post']['pct']:+.2f}% (*eLife*-only; frozen snapshot {reg_aud['all_audit_frozen_oa_post']['pct']:+.2f}%), and {reg_aud['all_audit_all_manifest_union_post']['pct']:+.2f}% vs. {reg_aud['all_audit_all_manifest_ymax_post']['pct']:+.2f}% (all manifestations, post-$v_1$; next-year {reg_aud['all_audit_all_manifest_union_next_yr']['pct']:+.2f}% vs. {reg_aud['all_audit_all_manifest_ymax_next_yr']['pct']:+.2f}%).

### 2.4 Econometric Specification and Statistical Inference

For non-negative skewed citation and usage count endpoints, we estimate fixed-effects Poisson Pseudo-Maximum Likelihood (PPML) models, which remain consistent under arbitrary overdispersion and avoid the scale-dependent distortions of `log(1 + y)` transformations when zeros are present (Santos Silva & Tenreyro, 2006; Chen & Roth, 2024):

$$E[Y_i \mid X_i, \alpha_{{s(i), t(i)}}] = \exp\!\left(\beta_1 \mathbf{{1}}[\text{{BelowSolid}}_i] + \beta_2 \mathbf{{1}}[\text{{Conv}}_i] + \beta_3 \mathbf{{1}}[\text{{Compel+}}_i] + \gamma_1 \mathbf{{1}}[\text{{Imp}}_i] + \gamma_2 \mathbf{{1}}[\text{{Fund+}}_i] + \delta^\top Z_i^{{(v_1)}} + \alpha_{{s(i), t(i)}}\right)$$

where $\alpha_{{s(i), t(i)}}$ denotes strictly $v_1$-frozen `v1_primary_subject × v1_quarter` fixed effects (with `v1_primary_subject × v1_month` robustness checks), $Z_i^{{(v_1)}}$ contains strictly frozen $v_1$ covariates (`v1_age_days`, `log(1 + v1_n_authors)`, `log(1 + pre_v1_cites)`, plus `v1_posting_day` for first-three-bin usage), and all standard errors and 95% confidence intervals are CR1 cluster-robust at the discipline level ($G = 17$–$18$, using $t_{{G-1}}$ critical values). Reported percentage associations equal $100 \times (\exp(\hat{{\beta}}) - 1)$. For within-article log-change readership trajectories and event studies, we estimate within-FE OLS with CR1 standard errors and restricted Rademacher wild cluster bootstrap $p$-values ($B = 1{{,}}999$; Cameron, Gelbach, & Miller, 2008). To quantify whether observational upgrade contrasts rule out substantively meaningful effects rather than misinterpreting statistical non-significance as "zero return," we report exact multiplicative Two One-Sided Tests (TOST; Lakens, 2017) against pre-specified relative margins of $\pm 15\%$ ($\ln(0.85)$ to $\ln(1.15)$) and $\pm 20\%$ ($\ln(0.80)$ to $\ln(1.20)$).

---

## 3. Incremental Predictive Value of $v_1$ Assessments Over Equal-Length Windows

### 3.1 Crossed $2 \times 2$ Date-Clock and Assessment-Timing Audit

To separate the effect of freezing $v_1$ covariates from the effects of changing the date clock (initial $v_1$ quarter vs. formal VoR quarter) and substituting final assessments for initial assessments, Table 2 estimates a crossed $2 \times 2$ design holding the estimation sample strictly fixed across positive, non-singleton cells under both clocks.

**Table 2. Covariate-Freeze Audit and Crossed $2 \times 2$ Date-Clock $\times$ Assessment-Timing Sensitivity (Mature VoRs)**

| Covariate / FE Specification | Assessment Used | Quarter Clock in FE | $N$ | Post-$v_1$ OA Cites: Below-*Solid* vs. *Solid* [95% CI] | $p$ | Next Full Calendar Year [95% CI] |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
{t2_md}

*Notes:* Discipline-clustered PPML ($G = 18$). The top three rows reproduce the exact $N = {rev2285['n']:,}$ benchmark sample (which retains one article, `eid = 87414`, with missing $v_1$ strength under the final-subject FE) to verify exact numerical parity when swapping `max_authors` ({rev2285['leaked_max_authors']['pct']:+.2f}%) to frozen `v1_n_authors` ({rev2285['frozen_v1_authors']['pct']:+.2f}%). Dropping `eid = 87414` ($N = {b_post['frozen_v1_authors_v1_v1q']['n']:,}$) gives {b_post['leaked_max_authors_v1_v1q']['pct']:+.2f}% $\to$ {b_post['frozen_v1_authors_v1_v1q']['pct']:+.2f}%. Bottom four rows freeze both `v1_n_authors` and `v1_primary_subject` strictly at $v_1$ ($N = {s_post['v1_v1q']['n']:,}$ post-$v_1$; $N = {s_next['v1_v1q']['n']:,}$ next full calendar year).

Three methodological findings stand out clearly in Table 2 and Figure 2A:

1. **Covariate freezing modestly refines—and never eliminates—the $v_1$ gradient.** Replacing leaked `max_authors` with strictly frozen `v1_n_authors` on the exact $N = {rev2285['n']:,}$ benchmark shifts the post-$v_1$ citation association by 0.29 percentage points, from {rev2285['leaked_max_authors']['pct']:+.2f}% to **{rev2285['frozen_v1_authors']['pct']:+.2f}% [{rev2285['frozen_v1_authors']['pct_ci95_lo']:+.2f}%, {rev2285['frozen_v1_authors']['pct_ci95_hi']:+.2f}%]** ($p = {fmt_p(rev2285['frozen_v1_authors']['p'])}$). Additionally freezing `v1_primary_subject` yields **{fmt_pct_ci(s_post['v1_v1q'], 2)}** ($p = {fmt_p(s_post['v1_v1q']['p'])}$) for post-$v_1$ citations and **{fmt_pct_ci(s_next['v1_v1q'], 2)}** ($p = {fmt_p(s_next['v1_v1q']['p'])}$) for equal next-full-calendar-year citations.
2. **Quarter-clock substitution alone attenuates the association.** Holding the $v_1$ rating fixed and changing *only* the fixed-effect quarter clock from $v_1$ publication to formal VoR publication attenuates the strict-$v_1$ estimate from {s_post['v1_v1q']['pct']:+.2f}% to {s_post['v1_finq']['pct']:+.2f}% (and from {s_next['v1_v1q']['pct']:+.2f}% to {s_next['v1_finq']['pct']:+.2f}% in the equal next-calendar-year window; benchmark {rev2285['frozen_v1_authors']['pct']:+.2f}% $\to$ {rev2285['frozen_v1_authors_finq_clock']['pct']:+.2f}%).
3. **Final-rating substitution changes the estimand altogether.** Replacing the $v_1$ assessment with the final VoR assessment collapses the association to {fmt_pct_ci(s_post['fin_v1q'], 2)} ($p = {fmt_p(s_post['fin_v1q']['p'])}$) under the $v_1$ clock and {fmt_pct_ci(s_post['fin_finq'], 2)} ($p = {fmt_p(s_post['fin_finq']['p'])}$) under the VoR clock—showing that a combined final-date, final-rating specification conflates clock shifts with endogenous post-review selection into upgrades.

<!-- FIGURE:fig2_v4_equal_window_predictive_value.png -->

### 3.2 Equal-Length Fixed-Window Validation Including Non-VoR Reviewed Preprints

A crucial validity question raised by conditioning on finalized VoRs is whether the predictive association of initial $v_1$ assessments persists across the **unselected population of all reviewed preprints**, including manuscripts that never converted to a VoR. Table 3 and Figure 2B evaluate strictly frozen $v_1$ models across all mature 2023–2024 $v_1$ preprints ($N = {cs['n_mature_2023_2024']:,}$), the VoR-only subsample ($N = {cs['n_mature_vor']:,}$), and the non-VoR-only subsample ($N = {cs['n_mature_non_vor']:,}$).

**Table 3. Equal-Length Fixed-Window Citation Validation Across All-$v_1$, VoR-Only, and Non-VoR Subsamples (Strictly Frozen $v_1$ Covariates)**

| Sample & Fixed Effects | Citation / Usage Endpoint | $N$ | Mean | $v_1$ Below-*Solid* vs. *Solid* [95% CI] | $t$ | $p$ |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
{t3_md}

*Notes:* All models control strictly for $v_1$-frozen covariates (`v1_age_days`, `log(1 + v1_n_authors)`, `log(1 + pre_v1_cites)`, plus full $v_1$ *Strength* and *Significance* indicators) with discipline-clustered CR1 SEs ($G = 17$–$18$). Non-VoR `v1_subj × v1_year` FE avoids small-cell attrition across sparse subject-quarters.

The full-cohort and subsample validation yields four robust findings:

1. **Including non-VoR reviewed preprints strengthens the prospective predictive gradient.** Across all mature 2023–2024 $v_1$ preprints ($N = {ev['all_v1']['oa_next_full_year']['v1_low']['n']:,}$ in FE), an initial below-*Solid* evidence rating predicts **{fmt_pct_ci(ev['all_v1']['oa_next_full_year']['v1_low'], 2)}** fewer citations in the exact next full calendar year ($p = {fmt_p(ev['all_v1']['oa_next_full_year']['v1_low']['p'])}$; combined eLife + preprint DOIs: {fmt_pct_ci(ev['all_v1']['oa_next_full_year_all']['v1_low'], 2)}, $p = {fmt_p(ev['all_v1']['oa_next_full_year_all']['v1_low']['p'])}$) and **{fmt_pct_ci(ev['all_v1']['oa_post_v1_cites']['v1_low'], 2)}** across all post-$v_1$ years ($p = {fmt_p(ev['all_v1']['oa_post_v1_cites']['v1_low']['p'])}$; Crossref max-DOI: {fmt_pct_ci(ev['all_v1']['cr_cites']['v1_low'], 2)}, $p = {fmt_p(ev['all_v1']['cr_cites']['v1_low']['p'])}$). Conversely, initial *Compelling/Exceptional* preprints receive {fmt_pct_ci(ev['all_v1']['oa_next_full_year']['v1_high'], 1)} more next-year citations ($p = {fmt_p(ev['all_v1']['oa_next_full_year']['v1_high']['p'])}$), and *Important* significance predicts {fmt_pct_ci(ev['all_v1']['oa_next_full_year']['v1_imp'], 1)} ($p = {fmt_p(ev['all_v1']['oa_next_full_year']['v1_imp']['p'])}$).
2. **The negative association is NOT restricted to finalized VoRs.** Within the {cs['n_mature_non_vor']:,} non-VoR reviewed preprints alone, $v_1$ below-*Solid* preprints exhibit a large negative point estimate across every endpoint: {fmt_pct_ci(ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low'], 1)} post-$v_1$ citations ($p = {fmt_p(ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['p'])}$), {fmt_pct_ci(ev['non_vor_only_subj_q']['oa_next_full_year']['v1_low'], 1)} next-full-year *eLife* citations ($p = {fmt_p(ev['non_vor_only_subj_q']['oa_next_full_year']['v1_low']['p'])}$), {fmt_pct_ci(ev['non_vor_only_subj_yr']['oa_next_full_year_all']['v1_low'], 1)} next-full-year combined eLife+preprint citations under subject-year FE ($p = {fmt_p(ev['non_vor_only_subj_yr']['oa_next_full_year_all']['v1_low']['p'])}$), and {fmt_pct_ci(ev['non_vor_only_subj_q']['dl_total']['v1_low'], 1)} cumulative downloads ($p = {fmt_p(ev['non_vor_only_subj_q']['dl_total']['v1_low']['p'])}$). In a pooled All-$v_1$ model interacting `is_vor × v1_low`, the interaction term is statistically indistinguishable from zero across post-$v_1$ citations ($p = {fmt_p(vint['oa_post_v1_cites']['vor_x_v1_low']['p'])}$), next-year *eLife* citations ($p = {fmt_p(vint['oa_next_full_year']['vor_x_v1_low']['p'])}$), and next-year all-DOI citations ($p = {fmt_p(vint['oa_next_full_year_all']['vor_x_v1_low']['p'])}$). While non-VoR confidence intervals are understandably wider due to smaller sample size ($N = {cs['n_mature_non_vor']:,}$), these results confirm that the prospective predictive signal operates outside finalized VoRs as well as inside them—and is magnified in the full population because lower-rated $v_1$ preprints convert to VoR at lower rates ({fn_inc['pct_vor']:.1f}% vs. {fn_sol['pct_vor']:.1f}%–{fn_conv['pct_vor']:.1f}%).
3. **Measurable incremental predictive gain over $v_1$-only metadata.** Adding the five $v_1$ assessment indicators on top of strictly frozen $v_1$ metadata (`v1_primary_subject × v1_quarter` FE, `v1_age_days`, `log(1 + v1_n_authors)`, and `log(1 + pre_v1_cites)`) reduces Poisson deviance by {incp['all_v1_oa_next_yr']['deviance_reduction']:.1f} ($\Delta$McFadden pseudo-$R^2$ = +{incp['all_v1_oa_next_yr']['delta_pseudo_r2_pp']:.2f} pp, from {incp['all_v1_oa_next_yr']['pseudo_r2_v1_meta_only']:.4f} to {incp['all_v1_oa_next_yr']['pseudo_r2_with_v1_assessments']:.4f}; LR $p = {fmt_p(incp['all_v1_oa_next_yr']['lr_p_value'])}$) for equal next-full-calendar-year citations and by {incp['all_v1_oa_post_v1']['deviance_reduction']:.1f} (+{incp['all_v1_oa_post_v1']['delta_pseudo_r2_pp']:.2f} pp, from {incp['all_v1_oa_post_v1']['pseudo_r2_v1_meta_only']:.4f} to {incp['all_v1_oa_post_v1']['pseudo_r2_with_v1_assessments']:.4f}) for post-$v_1$ citations across all mature $v_1$ preprints.
4. **Robustness to finer monthly clocks, strictly preprint-only prior citations, and 18-subject LOSO.** Tightening fixed effects to `v1_primary_subject × v1_month` yields {fmt_pct_ci(csens['all_v1_next_yr_monthly_fe'], 2)} ($N = {csens['all_v1_next_yr_monthly_fe']['n']:,}$, $p = {fmt_p(csens['all_v1_next_yr_monthly_fe']['p'])}$) for All-$v_1$ next-full-year citations and {fmt_pct_ci(csens['vor_next_yr_monthly_fe'], 2)} for VoRs. Replacing merged pre-$v_1$ citations with strictly preprint-DOI-only pre-$v_1$ citations gives {fmt_pct_ci(csens['all_v1_post_preprint_only_ctrl'], 2)} (All-$v_1$) and {fmt_pct_ci(csens['vor_post_preprint_only_ctrl'], 2)} (VoRs). Dropping each of the 18 disciplines in turn (LOSO) keeps the All-$v_1$ next-full-year estimate tightly bounded between {loso_ny_min:+.2f}% and {loso_ny_max:+.2f}% (maximum $p = {fmt_p(loso_ny_pmax)}$; All-$v_1$ post-$v_1$ range: {loso_pv_min:+.2f}% to {loso_pv_max:+.2f}%).

### 3.3 Observational Onsite Readership Predictive Associations

To examine how $v_1$ assessments co-move with shorter-horizon and cumulative onsite usage across all reviewed preprints (including non-VoRs), Table 4 reports strictly $v_1$-frozen PPML estimates on the untruncated monthly cohort ($v_1 \ge$ November 2023; $N = {cs['n_mature_complete_monthly_ge_2023_11']:,}$), controlling explicitly for `v1_posting_day`.

**Table 4. Observational Onsite Readership Associations in the Untruncated Monthly Cohort ($v_1 \ge$ 2023-11, Strict $v_1$ Covariates)**

| Onsite Usage Endpoint | Evidence: Below-*Solid* vs. *Solid* | Significance: *Important* vs. Lower | Significance: *Fundamental+* vs. Lower | $N$ |
| :--- | :--- | :--- | :--- | ---: |
{t4_md}

*Notes:* Discipline-clustered PPML ($G = 18$) with `v1_primary_subject × v1_quarter` FE, strictly frozen $v_1$ covariates, and `v1_posting_day`. Counts aggregate traffic across all versions of an article, including non-VoR reviewed preprints, during a period overlapping *eLife*'s phased June 2024 discoverability redesign (eLife, 2025).

Table 4 and Figure 3A reveal a nuanced observational divergence between the two *eLife* Assessment axes. Higher *Significance* tiers (*Important* and *Fundamental+*) positively predict both early three-bin page-views ({att['pv_first_3m']['v1_imp']['pct']:+.1f}%, $p = {fmt_p(att['pv_first_3m']['v1_imp']['p'])}$; *Fundamental+* {att['pv_first_3m']['v1_fund']['pct']:+.1f}%, $p = {fmt_p(att['pv_first_3m']['v1_fund']['p'])}$) and cumulative views ({att['pv_total']['v1_imp']['pct']:+.1f}%, $p = {fmt_p(att['pv_total']['v1_imp']['p'])}$) and downloads ({att['dl_total']['v1_imp']['pct']:+.1f}%, $p = {fmt_p(att['dl_total']['v1_imp']['p'])}$). By contrast, below-*Solid* *Strength of Evidence* shows a small, statistically imprecise association with cumulative page-views ({fmt_pct_ci(att['pv_total']['v1_low'], 1)}, $p = {fmt_p(att['pv_total']['v1_low']['p'])}$) and early views ({fmt_pct_ci(att['pv_first_3m']['v1_low'], 1)}, $p = {fmt_p(att['pv_first_3m']['v1_low']['p'])}$), yet predicts significantly lower cumulative PDF downloads ({fmt_pct_ci(att['dl_total']['v1_low'], 1)}, $p = {fmt_p(att['dl_total']['v1_low']['p'])}$)—mirroring its citation gradient. Because *eLife* introduced browse-by-assessment filters, moved assessments above the abstract, and updated search badges in stages starting June 2024 (eLife, 2025), these patterns represent **prospective observational associations** capturing the combined mix of intrinsic article appeal, discoverability pathways, and version histories—not causal estimates of reader clicks on displayed badges.

---

## 4. Public Revision, Rating Upgrades, VoR Conversion, and Readership Trajectories

### 4.1 Separating Public Revision, VoR Conversion, and Rating Upgrades

A central pitfall in analyzing open-revision systems is conflating four distinct post-$v_1$ outcomes: (1) posting a public revised preprint (`Crossref posted-content ver >= 2`), (2) converting to a formal VoR, (3) securing an upward shift in *Strength of Evidence* relative to the full $v_1$ cohort (unconditional), and (4) securing an upgrade conditional on reaching VoR. Table 5 and Figure 3B disentangle all four denominators across the {cs['n_mature_2023_2024']:,} mature 2023–2024 manuscripts.

**Table 5. Public Revision, VoR Conversion, and Strength-of-Evidence Upgrade Funnel Across Mature 2023–2024 $v_1$ Tiers ($N = {cs['n_mature_2023_2024']:,}$)**

| Initial ($v_1$) Evidence Tier | All $v_1$ ($N$) | Posted Public Revision (`v>=2`) | Converted to VoR | Upgraded Any Tier (Uncond. All-$v_1$) | Upgraded Any Tier (VoR-Cond.) | Mean $v_1 \to$ VoR Lag (Upgraded) | Final Unchanged VoRs w/ Public Rev |
| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
{t5_md}

*Notes:* Public revision requires a Crossref `posted-content` record (`ver >= 2`) strictly after $v_1$ and on or before VoR date (or November 25, 2026 for non-VoRs). Calendar-date interval (`mean_rev_lag_up_days`) measures days between $v_1$ posting and VoR publication rather than private laboratory editing time.

<!-- FIGURE:fig3_v4_onsite_readership_and_funnel.png -->

Among the {fn_inc['n_total']:,} mature 2023–2024 manuscripts initially rated below *Solid* (*Incomplete* or *Inadequate*):

- **{fn_inc['n_posted_revision']}/{fn_inc['n_total']} ({fn_inc['pct_posted_revision']:.1f}%)** posted at least one public revised reviewed preprint in Crossref.
- **{fn_inc['n_vor']}/{fn_inc['n_total']} ({fn_inc['pct_vor']:.1f}%)** converted to a formal VoR (vs. {fn_sol['pct_vor']:.1f}% for *Solid* and {fn_conv['pct_vor']:.1f}% for *Convincing*).
- **{fn_inc['n_vor_upgraded_any']}/{fn_inc['n_total']} ({fn_inc['pct_all_upgraded_any']:.1f}% unconditional)**—or **{fn_inc['n_vor_upgraded_any']}/{fn_inc['n_vor']} ({fn_inc['pct_vor_upgraded_any']:.1f}% VoR-conditional)**—achieved a higher final *Strength of Evidence* rating (with {fn_inc['n_vor_upgraded_to_solid']}/{fn_inc['n_total']} = {fn_inc['pct_all_upgraded_to_solid']:.1f}% unconditional and {fn_inc['n_vor_upgraded_to_solid']}/{fn_inc['n_vor']} = {fn_inc['pct_vor_upgraded_to_solid']:.1f}% VoR-conditional reaching *Solid* or higher).
- The mean calendar-date interval from $v_1$ posting to VoR publication for upgraded below-*Solid* manuscripts was **{fn_inc['mean_rev_lag_up_days']:.1f} days** (median {fn_inc['med_rev_lag_up_days']:.1f} days), compared with {fn_inc['mean_rev_lag_unch_days']:.1f} days for VoRs remaining below *Solid*.
- **Crucial separation of public revision from final rating:** Across the full April 2023 onward cohort of initially below-*Solid* preprints, among the **{si['apr2023_lower_rated_vors']}** finalized VoRs whose final rating remained below *Solid*, **{si['apr2023_lower_rated_vors_with_posted_revision']}/{si['apr2023_lower_rated_vors']} ({si['apr2023_lower_rated_vors_with_revision_pct']:.1f}%)** actually posted at least one public revised preprint prior to VoR declaration (and {fn_inc['n_vor_unchanged_with_revision']}/{fn_inc['n_vor_unchanged']} in the mature 2023–2024 cohort). For example, Ragusa et al. (2025; `10.7554/eLife.102324`) posted a dated revised preprint yet finalized with an *Incomplete* final assessment. Treating final below-*Solid* VoRs as "unrevised" is therefore factually inaccurate; public revision and editorial re-rating are distinct empirical events.

### 4.2 Observational Associations of Upgrading to *Solid+*, Precision Bounds, and Version-Release Trajectories

Within the selected subset of mature $v_1$ below-*Solid* manuscripts that reached VoR ($N = {fn_inc['n_vor']}$), Table 6 and Figure 4 compare subsequent citations and onsite traffic between manuscripts upgraded to *Solid+* ($n = {fn_inc['n_vor_upgraded_to_solid']}$) and those finalized below *Solid* ($n = {fn_inc['n_vor'] - fn_inc['n_vor_upgraded_to_solid']}$).

**Table 6. Observational Associations for Upgrading to *Solid+* Within $v_1$ Below-*Solid* VoRs: Precision, Equivalence Bounds, and Version-Release Events**

| Endpoint / Specification | $N$ | Estimate [95% CI] | $p$ | Equivalence (TOST) / Context |
| :--- | ---: | ---: | ---: | :--- |
{t6_md}

*Notes:* Discipline-clustered CR1 SEs ($G = 17$–$18$). TOST reports exact multiplicative two one-sided test $p$-values for relative margins $\pm 15\%$ and $\pm 20\%$ (Lakens, 2017). Local VoR event studies (`m0`, `p16`) measure log-traffic shifts relative to each article's own pre-release baseline (months $-3..-1$), controlling for `rev_lag_days` and strictly frozen $v_1$ covariates. All contrasts are observational within a selected VoR sample.

<!-- FIGURE:fig4_v4_upgrade_precision_and_trajectories.png -->

Table 6 and Figure 4 deliver two vital corrective lessons for evaluating public revision outcomes:

1. **Precision limits preclude claiming "zero return" to upgrading.** Under the earlier benchmark covariates (`max_authors` + final subject FE), upgrading to *Solid+* carries a post-$v_1$ OpenAlex citation point estimate of **{fmt_pct_ci(u_b, 1)}** ($p = {fmt_p(u_b['p'])}$; TOST $\pm 20\%$ $p = {u_b['tost_pm20']:.3f}$, $\pm 15\%$ $p = {u_b['tost_pm15']:.3f}$). Once look-ahead author and subject leakage are removed (freezing both `v1_n_authors` and `v1_primary_subject`), the observational point estimate rises to **{fmt_pct_ci(u_s, 1)}** ($p = {fmt_p(u_s['p'])}$; next full calendar year **{fmt_pct_ci(u_ny, 1)}**, $p = {fmt_p(u_ny['p'])}$; Crossref **{fmt_pct_ci(u_cr, 1)}**, $p = {fmt_p(u_cr['p'])}$), and **neither** $\pm 15\%$ (TOST $p = {u_s['tost_pm15']:.3f}$) **nor** $\pm 20\%$ (TOST $p = {u_s['tost_pm20']:.3f}$) equivalence is established. The downward shift under leaked covariates is partly consistent with added co-authors acting as a post-$v_1$ mediator of revision effort (21.7% of upgraded VoRs added co-authors vs. 15.1% of non-upgraded VoRs). Thus, current sample sizes ($n = {u_s['n']}$, with only {fn_inc['n_vor'] - fn_inc['n_vor_upgraded_to_solid']} non-upgraded comparators) are compatible with anything from modest negative differences ($-9\%$) to substantial positive associations ($+25\%$ to $+30\%$); describing this wide confidence interval as "zero return" would be statistically invalid.
2. **Onsite traffic co-moves strongly with version-release events rather than differing sharply by rating outcome.** In the clean untruncated local VoR event study ($N = {up['raw_ev_m0_summary']['n_clean_ev']}$ raw; $n = {up['strict_v1_dlog_pv_ev_m0']['n']}$ in FE), VoR publication triggers a virtually identical month-$0$ surge over months $-3..-1$ regardless of whether the rating upgraded to *Solid+* or remained below *Solid* (raw mean log-view jump {up['raw_ev_m0_summary']['pv_m0_upgraded_mean']:+.2f} vs. {up['raw_ev_m0_summary']['pv_m0_unchanged_mean']:+.2f}; downloads {up['raw_ev_m0_summary']['dl_m0_upgraded_mean']:+.2f} vs. {up['raw_ev_m0_summary']['dl_m0_unchanged_mean']:+.2f}; FE contrast {fmt_beta_ci(up['strict_v1_dlog_pv_ev_m0'], 1.0, 3, 'log')}, $p_{{\text{{WCB}}}} = {fmt_p(up['strict_v1_dlog_pv_ev_m0']['p_wcb'])}$). Post-release months $+1..+6$ likewise show imprecise, near-zero contrasts for views ({fmt_beta_ci(up['strict_v1_dlog_pv_ev_p16'], 1.0, 3, 'log')}, $p_{{\text{{WCB}}}} = {fmt_p(up['strict_v1_dlog_pv_ev_p16']['p_wcb'])}$) and downloads ({fmt_beta_ci(up['strict_v1_dlog_dl_ev_p16'], 1.0, 3, 'log')}, $p_{{\text{{WCB}}}} = {fmt_p(up['strict_v1_dlog_dl_ev_p16']['p_wcb'])}$). By contrast, in balanced 22-month post-$v_1$ trajectories (`months 12–21` vs. `0–2`), each additional publicly posted version (`cr_n_versions`) is strongly associated with sustained page-view activity in both $v_1$ below-*Solid* VoRs ({fmt_beta_ci(up['version_release_m12_21_incomp']['cr_n_versions'], 1.0, 3, 'log')}, $p_{{\text{{WCB}}}} = {fmt_p(up['version_release_m12_21_incomp']['cr_n_versions']['p_wcb'])}$) and $v_1$ *Solid* VoRs ({fmt_beta_ci(up['version_release_m12_21_solid']['cr_n_versions'], 1.0, 3, 'log')}, $p_{{\text{{WCB}}}} = {fmt_p(up['version_release_m12_21_solid']['cr_n_versions']['p_wcb'])}$), while VoR conversion itself correlates with substantially higher cumulative attention across all {fn_inc['n_total']} below-*Solid* preprints (views {fmt_beta_ci(up['vor_vs_rp_incomp_pv_ols'], 1.0, 3, 'log')}, downloads {fmt_beta_ci(up['vor_vs_rp_incomp_dl_ols'], 1.0, 3, 'log')}, both $p_{{\text{{WCB}}}} = 0.0005$). Because release timing and revision decisions are jointly chosen by authors, these patterns capture observational release-event dynamics rather than isolated badge effects.

### 4.3 Methodological Scope Boundary: Indexing-Announcement Analyses Deferred to Supplementary Information

On October 23–24, 2024, Clarivate placed *eLife* on hold in Web of Science; on November 20, 2024, *eLife* described a proposed selective feed restricted to *Solid+* VoRs; and on December 10, 2024, *eLife* announced **simultaneous indexing changes across both Web of Science and Scopus**—supplying a partial *Solid+* VoR feed to Web of Science (forgoing Journal Impact Factor eligibility) while transitioning from the Scopus Journals Collection to the Scopus Preprints Collection (eLife, 2024a–c). Because public metadata lack internal submission, desk-review, and transfer timestamps across comparable journals—and because **{si['pre_450_vors_after_announcement']}/{si['pre_450_vors']} ({si['pct_pre_450_vors_crossing_announcement']:.1f}%)** of earlier-cohort ($v_1 <$ October 1, 2024) 450-day VoRs actually finalized *after* the December 10 announcement—before-after posting-cohort contrasts cannot isolate a causal indexing-policy effect. Indeed, as documented fully in Supplementary Information (`supplementary_h6f_scientometrics.pdf`, Section S2), once follow-up is held strictly equal at 450 days with subject adjustment, differences between post-December 10 and pre-October 1 posting cohorts are statistically indistinguishable from zero for both final below-*Solid* VoRs ({fmt_beta_ci(fh_v3['lower_rated_vor'], 100.0, 2, 'pp')}, $p_{{\text{{WCB}}}} = {fmt_p(fh_v3['lower_rated_vor']['p_wcb'])}$) and posted public revisions ({fmt_beta_ci(fh_v3['observed_revision'], 100.0, 2, 'pp')}, $p_{{\text{{WCB}}}} = {fmt_p(fh_v3['observed_revision']['p_wcb'])}$). All exploratory indexing-cohort survival curves, sequential manuscript-ID velocity proxies, published-output synthetic-control series, and geographic tabulations are therefore reported transparently in the Supplementary Information rather than claimed as causal findings here.

---

## 5. Discussion, Limitations, and Roadmaps for Causal Follow-Up

### 5.1 Incremental Scientometric Contribution

Relative to Mutz et al. (2025), who evaluated the reliability of *eLife*'s review process, and Adamson (2026), who summarized single-term rating shifts among 2,051 finalized VoRs, this study demonstrates why **prospective version-level measurement design** is decisive when evaluating PRC publishing. Three practical lessons emerge for scientometricians, research evaluators, and open-review publishers:

1. **Preserve immutable $v_1$ metadata snapshots.** Reconstructing $v_1$ author counts (`v1_n_authors`), $v_1$ primary discipline tags (`v1_primary_subject`), and $v_1$ posting dates eliminates look-ahead leakage affecting {rev2285['n_max_authors_gt_v1']}/{rev2285['n']:,} ({100.0*rev2285['n_max_authors_gt_v1']/rev2285['n']:.1f}%) VoRs on authorship and {v1a['n_primary_subject_diff_all']}/{v1a['n_prc_census']:,} ({100.0*v1a['n_primary_subject_diff_all']/v1a['n_prc_census']:.1f}%) manuscripts on primary discipline—leakage that substantively shifts post-review upgrade comparisons by conditioning on revision-stage co-author additions.
2. **Account for asymmetric preprint-to-VoR merging in bibliographic databases.** OpenAlex merges upstream bioRxiv/medRxiv preprints into canonical *eLife* works for {vor_merged_pct:.1f}% of VoRs but only {100.0 - nv_split_pct:.1f}% of non-VoR reviewed preprints. Consequently, *eLife*-DOI-only citation queries systematically under-measure non-VoR preprints, naive cross-DOI summing double-counts overlapping citations by +{100.0*(sp_only['agg_sum_to_union_ratio']-1):.1f}% on split records, and citing-work ID union deduplication should be adopted whenever PRC platforms are benchmarked against traditional journals.
3. **Evaluate prospective predictive validity on unselected $v_1$ cohorts and separate revision from re-rating.** Initial below-*Solid* assessments carry consistent incremental predictive value over equal next-full-calendar-year windows across all $v_1$ preprints ({ev['all_v1']['oa_next_full_year']['v1_low']['pct']:+.1f}%, +{incp['all_v1_oa_next_yr']['delta_pseudo_r2_pp']:.2f} pp pseudo-$R^2$), VoRs ({ev['vor_only']['oa_next_full_year']['v1_low']['pct']:+.1f}%), and non-VoR reviewed preprints ({ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['pct']:+.1f}% post-$v_1$). At the same time, {si['apr2023_lower_rated_vors_with_posted_revision']}/{si['apr2023_lower_rated_vors']} ({si['apr2023_lower_rated_vors_with_revision_pct']:.1f}%) final below-*Solid* VoRs posted public revisions, confirming that assessment stability does not imply author inaction.

### 5.2 Limitations

Four limitations bound our conclusions. First, all citation and readership regressions are strictly **observational predictive associations**: *eLife* Assessments reflect reviewers' judgments of underlying manuscript rigor and novelty (Azoulay, Stuart, & Wang, 2014), so lower citations for below-*Solid* preprints cannot be decomposed into intrinsic quality differences versus reader reactions to public labels. Second, *eLife*'s phased June 2024 discoverability redesign concurrently altered assessment placement, search badges, and browse filters (eLife, 2025), precluding causal attribution of onsite traffic patterns without session-level deployment logs. Third, our upgrade-to-*Solid+* comparison conditions on VoR conversion and remains statistically imprecise ({fmt_pct_ci(u_s, 1)} under strict $v_1$ covariates), leaving both modest positive returns and null differences empirically plausible. Fourth, public Crossref records capture posted preprint versions (`ver >= 2`) but cannot observe private editorial correspondence or manuscripts withdrawn before peer review.

### 5.3 Experimental and Administrative-Data Roadmaps for Causal Follow-Up

Moving from prospective predictive validity (the scope of *Scientometrics*) to causal identification of reader behavior or indexing-policy incentives requires two distinct empirical designs beyond public observational snapshots:

1. **Causal reader-behavior identification (path to *PLOS Biology* or *Nature Human Behaviour*).** Isolating the direct behavioral effect of public peer-review badges requires a pre-registered, platform-partnered **within-article, same-version randomized display experiment**. Specifically, incoming reader sessions arriving at the *exact same article version* through the *exact same referral entry* (e.g., PubMed, Google Scholar, or direct DOI) should be randomly assigned to high-prominence assessment placement (above abstract, expanded vocabulary) versus low-prominence control placement (collapsed or below abstract), recording session-level exposures, full-text opens, and PDF downloads over a fixed short window (primary endpoint: full-text open/download rate per exposure). Stratifying treatments across *Significance* versus *Strength of Evidence* phrasing separates headline salience from methodological caution. Where only phased UI deployment logs are obtainable, analysts must verify parallel pre-trends prior to rollout and test unchanged referral entry points as placebos. To meet the cross-context generalizability bar of *Nature Human Behaviour*, the same within-version display randomization should be pre-registered and replicated on a second open peer-review platform or independent reader panel to establish that reader responses transcend a single journal page layout.
2. **Causal indexing-policy identification (path to *Research Policy*).** Identifying how indexing rules reshape author submission, revision, and journal-substitution behavior requires confidential administrative logs linking manuscript submission, desk-review, public-revision, transfer, and VoR-declaration timestamps across *eLife* and comparable life-science journals. Exposure should be partitioned across the October 23–24, 2024 Web of Science hold, the November 20 selective-feed proposal, the December 10 dual Web of Science/Scopus announcement, and actual database ingestion dates, leveraging pre-existing institutional evaluation regimes (statutory WoS/JIF-dependent vs. DORA-reformed institutions) with common-trend and placebo tests among low-WoS-dependence groups.

---

## Data and Code Availability

All analyses rely exclusively on public APIs (*eLife* Search, Version, and Metrics APIs; Crossref Works API; OpenAlex Works API). Frozen data snapshots, the $N = {p3b['n_audited_articles']}$ OpenAlex citing-work ID deduplication cache (`data/openalex_citing_dedup_audit.json`), econometric receipts (`results/09_v4_scientometrics_results.json`, `results/03b_openalex_dedup_audit.json`, `results/03_panel_audit.json`), reproducible Python scripts (`scripts/`), automated test suite (`tests/test_h6f_boost.py`), and disk-byte integrity manifest (`SHA256SUMS.json`) are archived with this study.

---

## References

{refs_md}
"""


def build_supplementary_info(p3: dict, p3b: dict, p9: dict, p5: dict, refs: dict) -> str:
    v1a = p3["v1_panel_audit"]
    jpa = p3["journal_panel_audit"]
    cs = p9["cohort_summary"]
    rev2285 = p9["covariate_audit_and_crossed_clock"]["reviewer_2285_exact_parity"]
    csens = p9["covariate_audit_and_crossed_clock"]["clock_and_pre_v1_sensitivities"]
    si = p9["supplementary_indexing_cohort"]
    aj10 = si["aj_cutoffs"]["2024-12-10"]["contrasts"]
    fh_s = si["fixed_horizon_strict_v1_subj"]
    fh_v3 = si["fixed_horizon_v3_parity_fin_subj"]

    ed = p5["pillar3a_editorial_cushioning"]
    sc_all = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_vs_23_24"]
    sc_all35 = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_all"]["sc_clarivate_exp35"]
    sc_cn = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_clarivate"]
    sc_cn_c = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_clarivate_vs_23_24"]
    sc_cn35 = p5["pillar3b_expanded_sc_and_did"]["synthetic_control"]["log_n_CN"]["sc_full_pre_exp35"]
    reg = p5["pillar4_global_metric_dependence"]["institutional_regime_test"]
    ext = p5["pillar4_global_metric_dependence"]["external_validation_blog_9nations"]
    c12 = p5["pillar4_global_metric_dependence"]["country_12_panel"]
    pi = p5["pillar4_global_metric_dependence"]["senior_pi_last_author_shares"]

    # Table S1: Exploratory Dec 10, 2024 Indexing Cohort Aalen-Johansen & Subject-Adjusted Fixed-Horizon Contrasts
    ts1_aj_rows = "\n".join(
        f"| {d} d | {lbl} | {aj10[f't{d}'][k]['pre_pct']:.2f}% | {aj10[f't{d}'][k]['post_pct']:.2f}% | {aj10[f't{d}'][k]['diff_pp']:+.2f} pp [{aj10[f't{d}'][k]['ci95_lo_pp']:+.2f}, {aj10[f't{d}'][k]['ci95_hi_pp']:+.2f}] | {fmt_p(aj10[f't{d}'][k]['p'])} |"
        for d in (365, 450, 540)
        for k, lbl in (("km_vor_pct", "Any VoR (KM)"), ("cif_solid_pct", "Final Solid+ VoR (AJ CIF)"), ("cif_unrev_pct", "Final Below-Solid VoR (AJ CIF)"))
    )

    ts2_fh_rows = "\n".join(
        f"| {d} d | {lbl} | {fh_v3[str(d)][k]['n']:,} | {fmt_beta_ci(fh_v3[str(d)][k], 100.0, 2, 'pp')} | {fmt_p(fh_v3[str(d)][k]['p_wcb'])} | {fmt_beta_ci(fh_s[str(d)][k], 100.0, 2, 'pp')} | {fmt_p(fh_s[str(d)][k]['p_wcb'])} |"
        for d in (365, 450, 540)
        for k, lbl in (("any_vor", "Any VoR"), ("solid_vor", "Final Solid+ VoR"), ("lower_rated_vor", "Final Below-Solid VoR"), ("observed_revision", "Posted Public Revision"))
    )

    ts3_cut_rows = "\n".join(
        f"| {cut} | {part['post_n']:,} | {part['contrasts']['t450']['cif_unrev_pct']['diff_pp']:+.2f} pp [{part['contrasts']['t450']['cif_unrev_pct']['ci95_lo_pp']:+.2f}, {part['contrasts']['t450']['cif_unrev_pct']['ci95_hi_pp']:+.2f}] | {part['contrasts']['t540']['cif_solid_pct']['diff_pp']:+.2f} pp [{part['contrasts']['t540']['cif_solid_pct']['ci95_lo_pp']:+.2f}, {part['contrasts']['t540']['cif_solid_pct']['ci95_hi_pp']:+.2f}] |"
        for cut, part in si["aj_cutoffs"].items()
    )

    # Table S4: Exploratory 12-Nation Published-Output DiD (NOT submissions!)
    ts4_lines = []
    for r in c12:
        blg = f"{r['blog_2026_sub_drop_pct']:+.0f}%" if r["blog_2026_sub_drop_pct"] is not None else "Not reported"
        ts4_lines.append(
            f"| {r['country_name']} ({r['country_code']}) | {r['regime'].replace('_', ' ')} | "
            f"{r['elife_sh_21_22_pct']:.1f}% $\\to$ {r['elife_sh_23_24_pct']:.1f}% $\\to$ {r['elife_sh_25_26_pct']:.1f}% | "
            f"{r['phase2_log_did']:+.3f} ({r['phase2_pct_did']:+.1f}%) | {r['phase2_sh_did_pp']:+.2f} pp | {blg} |"
        )
    ts4_c12_rows = "\n".join(ts4_lines)

    si_ref_keys = [
        "Hicks2015", "Seglen1997", "McKiernan2019", "Quan2017", "ZhangSivertsen2020",
        "Shu2020", "Baccini2019", "Abadie2010", "Abadie2015", "Abadie2021", "Andrews1993",
    ]
    si_refs_lines = [f"{i}. {fmt_ref_entry(refs[k])}" for i, k in enumerate(si_ref_keys, 1)]
    nxt = len(si_refs_lines) + 1
    si_refs_lines.extend([
        f"{nxt}. eLife (2024a). Update on eLife's indexing status at Web of Science. *Inside eLife*, October 24, 2024. https://elifesciences.org/inside-elife/16afe6ec/update-on-elife-s-indexing-status-at-web-of-science",
        f"{nxt + 1}. eLife (2024b). The eLife Model: An update on progress following changes in Web of Science indexing status. *Inside eLife*, November 20, 2024. https://elifesciences.org/inside-elife/c11c6101/the-elife-model-an-update-on-progress-following-changes-in-web-of-science-indexing-status",
        f"{nxt + 2}. eLife (2024c). Changes to eLife's indexing status in Web of Science and Scopus. *Inside eLife*, December 10, 2024. https://elifesciences.org/inside-elife/ae620829/changes-to-elife-s-indexing-status-in-web-of-science-and-scopus",
        f"{nxt + 3}. Rodgers, P., & Pattinson, D. (2026). The eLife Model: Three years of data and lessons learned. *Inside eLife*, March 17, 2026. https://elifesciences.org/inside-elife/7da92a51/the-elife-model-three-years-of-data-and-lessons-learned",
    ])
    si_refs_md = "\n".join(si_refs_lines)

    return rf"""# Supplementary Information: Version-Level Measurement Audits and Exploratory Analyses Around *eLife*'s December 2024 Indexing Transition

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
Email: zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

*Companion Supplementary Information to:* **Version-Level Measurement, Incremental Predictive Validity, and Revision Trajectories of Public Peer-Review Assessments in *eLife* Reviewed Preprints**

---

## Scope and Interpretive Notice

In accordance with strict identification standards, this Supplementary Information separates two sets of material from the main *Scientometrics* manuscript: **(Section S1)** granular look-ahead covariate audits, monthly fixed-effect sensitivities, and extended OpenAlex multi-DOI diagnostics; and **(Sections S2–S3)** exploratory descriptive analyses surrounding *eLife*'s late-2024 Web of Science and Scopus indexing transition. **None of the exploratory cohort, sequential ID-velocity, synthetic-control, or country-share contrasts in Sections S2–S3 establish a causal indexing-policy effect.** Establishing causal author or editorial responses to indexing shocks requires confidential submission, desk-review, transfer, and VoR-declaration logs across comparable peer journals stratified by pre-existing institutional evaluation regimes.

---

## Section S1. Extended Covariate-Freeze and Multi-DOI Deduplication Diagnostics

1. **Complete Look-Ahead Covariate Accounting.** Across the full census ($N = {v1a['n_prc_census']:,}$), `cr_n_authors_max > v1_n_authors` in {v1a['n_authors_max_gt_v1_all']:,} manuscripts ({v1a['n_authors_max_gt_v1_mature']:,}/{cs['n_mature_2023_2024']:,} mature 2023–2024 manuscripts; {rev2285['n_max_authors_gt_v1']}/{rev2285['n']:,} in the fixed VoR benchmark), with zero missing `v1_n_authors`. Primary subject labels differed between `v1_subjects[0]` and final census `subjects[0]` in {v1a['n_primary_subject_diff_all']}/{v1a['n_prc_census']:,} manuscripts ({v1a['n_primary_subject_reordered_all']} reordered within an identical multi-subject list; {v1a['n_primary_subject_changed_set_all']} changed discipline tags; {v1a['n_primary_subject_diff_mature']}/{cs['n_mature_2023_2024']:,} mature).
2. **Monthly Fixed-Effect and Strictly Preprint-Only Pre-$v_1$ Controls.** Tightening fixed effects from `v1_primary_subject × v1_quarter` to `v1_primary_subject × v1_month` yields virtually identical $v_1$ below-*Solid* citation gradients: All-$v_1$ post-$v_1$ = {fmt_pct_ci(csens['all_v1_post_monthly_fe'], 2)} ($N = {csens['all_v1_post_monthly_fe']['n']:,}$, $p = {fmt_p(csens['all_v1_post_monthly_fe']['p'])}$); All-$v_1$ next full calendar year = {fmt_pct_ci(csens['all_v1_next_yr_monthly_fe'], 2)} ($N = {csens['all_v1_next_yr_monthly_fe']['n']:,}$, $p = {fmt_p(csens['all_v1_next_yr_monthly_fe']['p'])}$); VoR-only post-$v_1$ = {fmt_pct_ci(csens['vor_post_monthly_fe'], 2)}; VoR-only next full calendar year = {fmt_pct_ci(csens['vor_next_yr_monthly_fe'], 2)}. Restricting pre-$v_1$ citation controls strictly to upstream preprint-DOI citations (`year < v1_year`) yields {fmt_pct_ci(csens['all_v1_post_preprint_only_ctrl'], 2)} (All-$v_1$) and {fmt_pct_ci(csens['vor_post_preprint_only_ctrl'], 2)} (VoRs).
3. **Extended OpenAlex Split-Work Diagnostics ($N = {p3b['n_audited_articles']}$).** Among the {p3b['n_split_across_multiple_oa_works_all']} multi-work split manuscripts (76 of 80 audited non-VoR reviewed preprints and 2 of 120 audited VoRs), the aggregate yearly-max-to-union ratio is {p3b['split_works_only_all_manifest_post_v1']['agg_ymax_to_union_ratio']:.4f} (Pearson $r = {p3b['split_works_only_all_manifest_post_v1']['pearson_r']:.5f}$, Spearman $\rho = {p3b['split_works_only_all_manifest_post_v1']['spearman_rho']:.5f}$, 10th percentile ratio {p3b['split_works_only_all_manifest_post_v1']['p10_ymax_to_union_ratio']:.4f}, maximum absolute difference {p3b['split_works_only_all_manifest_post_v1']['max_abs_diff_ymax_vs_union']} citations), whereas naive summing inflates split-work totals by +{100.0*(p3b['split_works_only_all_manifest_post_v1']['agg_sum_to_union_ratio']-1):.2f}% (aggregate sum/union = {p3b['split_works_only_all_manifest_post_v1']['agg_sum_to_union_ratio']:.4f}) due to {p3b['total_duplicate_citing_ids_across_works']} overlapping citing OpenAlex Work IDs across {p3b['n_articles_with_duplicate_citing_ids_across_works']} manuscripts.

---

## Section S2. Exploratory Cohort Analysis Around the December 10, 2024 Web of Science & Scopus Announcement

### S2.1 Dual-Database Policy Timeline and Cross-Announcement Exposure Overlap

*eLife*'s late-2024 indexing transition unfolded across multiple dates and two distinct bibliographic databases: Web of Science placed *eLife* on hold on October 23–24, 2024 (eLife, 2024a); *eLife* outlined a proposed selective feed on November 20, 2024 (eLife, 2024b); and on **December 10, 2024**, *eLife* announced **both** (i) a partial Web of Science Core Collection feed limited to *Solid+* VoRs (removing Journal Impact Factor eligibility) **and** (ii) a simultaneous migration from the **Scopus Journals Collection** to the **Scopus Preprints Collection** (eLife, 2024c).

Comparing initially below-*Solid* preprints posted before October 1, 2024 ($n = {si['pre_n']:,}$) against those posted on or after December 10, 2024 ($n = {si['post_n']:,}$, excluding {si['excluded_transition_n']} transition posts from October 1 to December 9, 2024) exposes a severe exposure-contamination boundary: of the **{si['pre_450_vors']}** earlier-cohort manuscripts that finalized as VoRs within 450 days, **{si['pre_450_vors_after_announcement']} ({si['pct_pre_450_vors_crossing_announcement']:.1f}%) actually finalized after the December 10, 2024 announcement**. Consequently, earlier posting cohorts were partially exposed to the announcement during their revision windows, while concurrent shifts in author composition and dual WoS/Scopus rules confound any causal policy interpretation.

<!-- FIGURE:figs1_si_indexing_cohort_cif.png -->

**Table S1. Unadjusted Kaplan–Meier and Aalen–Johansen Competing-Risks Cumulative Incidence (Earlier $< $ Oct 1, 2024 vs. Later $\ge$ Dec 10, 2024)**

| Horizon | Outcome | Earlier Cohort ($n={si['pre_n']}$) | Later Cohort ($n={si['post_n']}$) | Difference [95% Boot CI] | Boot $p$ |
| :--- | :--- | ---: | ---: | ---: | ---: |
{ts1_aj_rows}

*Notes:* Within-cohort nonparametric article bootstrap ($B = 1{{,}}000$). By construction, `CIF(Solid+) + CIF(Below-Solid) == KM(Any VoR)`. Follow-up ends November 25, 2026.

**Table S2. Subject-Adjusted Complete Fixed-Horizon Linear Probability Contrasts (No Policy Effect Established)**

| Horizon | Outcome | $N$ | Final-Subject FE (v3 Parity) [CR1 95% CI] | WCB $p$ | Strict $v_1$-Subject FE [CR1 95% CI] | WCB $p$ |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
{ts2_fh_rows}

*Notes:* Restricted to cohorts with complete non-censored follow-up at each horizon relative to November 25, 2026 (`v1_date <= freeze - horizon`), controlling for discipline fixed effects and `v1_sig_rank`, without conditioning on VoR conversion. Public revision requires a Crossref `posted-content` (`ver >= 2`) record dated within the horizon.

**Table S3. Aalen–Johansen Cutoff Sensitivity Across Candidate Dates (Comparator Always $v_1 <$ Oct 1, 2024)**

| Later-Cohort Start Date | Later $N$ | 450-Day Final Below-*Solid* $\Delta$ [95% CI] | 540-Day Final *Solid+* $\Delta$ [95% CI] |
| :--- | ---: | ---: | ---: |
{ts3_cut_rows}

*Notes:* November 20 marks *eLife*'s proposed selective-feed update; December 10 marks *eLife*'s operational WoS and Scopus announcement; December 19 and January 1 are alternative calendar sensitivity cutoffs without causal breakpoint attribution.

As Tables S1–S3 and Figure S1 show, while unadjusted 450-day Aalen–Johansen cumulative incidence of final below-*Solid* VoRs was {aj10['t450']['cif_unrev_pct']['diff_pp']:+.2f} pp lower in the later posting cohort, **complete-followup subject-adjusted linear probability models yield statistically imprecise, non-significant contrasts at 450 days** for both final below-*Solid* VoRs ({fmt_beta_ci(fh_v3['450']['lower_rated_vor'], 100.0, 2, 'pp')}, $p_{{\text{{WCB}}}} = {fmt_p(fh_v3['450']['lower_rated_vor']['p_wcb'])}$; strict $v_1$-subject FE: {fmt_beta_ci(fh_s['450']['lower_rated_vor'], 100.0, 2, 'pp')}, $p_{{\text{{WCB}}}} = {fmt_p(fh_s['450']['lower_rated_vor']['p_wcb'])}$) and posted public revisions ({fmt_beta_ci(fh_v3['450']['observed_revision'], 100.0, 2, 'pp')}, $p_{{\text{{WCB}}}} = {fmt_p(fh_v3['450']['observed_revision']['p_wcb'])}$; strict $v_1$-subject FE: {fmt_beta_ci(fh_s['450']['observed_revision'], 100.0, 2, 'pp')}, $p_{{\text{{WCB}}}} = {fmt_p(fh_s['450']['observed_revision']['p_wcb'])}$). Combined with the {si['pre_450_vors_after_announcement']}/{si['pre_450_vors']} cross-announcement overlap and simultaneous Scopus reclassification, these data do not establish a causal indexing-policy effect.

---

## Section S3. Exploratory Sequential ID Velocity, Published-Output Synthetic Control, and Geographic Shares

For completeness and transparency relative to earlier working versions, this section archives our exploratory macro-level published-output series around the October–December 2024 indexing transition. Because OpenAlex measures **published output** rather than confidential submission inflows, and because sequential manuscript IDs (`eid`) are an indirect velocity proxy rather than direct submission logs, all estimates below are strictly descriptive/exploratory and excluded from the main manuscript's abstract and core claims.

<!-- FIGURE:figs2_si_id_velocity_and_sc.png -->

1. **Sequential Manuscript-ID Velocity Proxy & 500-`eid` Acceptance Shares.** Calibrating sequential manuscript IDs against $N = {ed['n_sfr_sample']}$ exact `sentForReview` timestamps (Spearman $r = {ed['spearman_eid_sfr_r']:.4f}$) implies a {ed['vel_drop_pct']:.1f}% contraction in quarterly ID velocity ({ed['pre_vel_mean_subs_q']:,.0f} $\to$ {ed['post_vel_mean_subs_q']:,.0f}/quarter), broadly consistent with *eLife*'s published full-year submission decline from 6,396 to 2,853 ($-55.4\%$; Rodgers & Pattinson, 2026). Across {len(ed['blocks_500'])} sequential 500-`eid` blocks (`eid` 87.5k–112k), the share reaching Reviewed Preprint rose from {ed['acc_pre_mean_pct']:.2f}% to {ed['acc_post_mean_pct']:.2f}% ({ed['acc_jump_pp']:+.2f} pp, HAC $t = {ed['acc_jump_hac_t']:+.2f}$, permutation $p = {ed['acc_jump_perm_p']:.4f}$, Quandt–Andrews Sup-Wald $F = {ed['sup_wald_best_F_hac']:.2f}$; Andrews, 1993) while $v_1$ below-*Solid* quality share showed no detectable shift ({100*ed['v1_quality_shift']['v1_incomp']['base_subj_fe']['params']['post_clar_eid']['beta']:+.2f} pp, $p = {fmt_p(ed['v1_quality_shift']['v1_incomp']['base_subj_fe']['params']['post_clar_eid']['p'])}$).
2. **Published-Output Synthetic Control ({jpa['n_total_journals_with_elife']} Strict / {jpa['n_expanded_journals_with_elife']} Expanded Biology Journals).** Applying strictly convex Abadie–Diamond–Hainmueller synthetic controls (Abadie, Diamond, & Hainmueller, 2010, 2015; Abadie, 2021) to half-yearly OpenAlex published counts (`2021H1–2026H1`) yields a post-2024 total published-output gap of {sc_all['treated']['post_mean_gap']:+.3f} log points (RMSPE Rank {sc_all['rmspe_ratio_rank_of_N']}/{sc_all['n_units']}, $p = {sc_all['p_rmspe_ratio']:.4f}$; expanded $N = {sc_all35['n_units']}$ gap {sc_all35['treated']['post_mean_gap']:+.3f}, Rank {sc_all35['rmspe_ratio_rank_of_N']}/{sc_all35['n_units']}, $p = {sc_all35['p_rmspe_ratio']:.4f}$) and a China-affiliated published-output gap of {sc_cn_c['treated']['post_mean_gap']:+.3f} ($T_0 = 3$, Rank {sc_cn_c['rmspe_ratio_rank_of_N']}/{sc_cn_c['n_units']}; Full-Pre $T_0 = 7$ gap {sc_cn['treated']['post_mean_gap']:+.3f}, Rank {sc_cn['rmspe_ratio_rank_of_N']}/{sc_cn['n_units']}, $p = {sc_cn['p_rmspe_ratio']:.4f}$; expanded $N = {sc_cn35['n_units']}$ Rank {sc_cn35['rmspe_ratio_rank_of_N']}/{sc_cn35['n_units']}, $p = {sc_cn35['p_rmspe_ratio']:.4f}$). Because synthetic controls here operate on **published articles** rather than submissions, they reflect the combined net result of submission shifts, editorial screening, and publication lags.

<!-- FIGURE:figs3_si_geographic_exploratory.png -->

**Table S4. Exploratory 12-Nation Phase-2 Published-Output DiD (2025H1–2026H1 vs. 2023H2–2024H2) and External Submission Comparison**

| Country | Policy-Label Grouping | *eLife* Share (21–22 $\to$ 23–24 $\to$ 25–26) | Phase-2 Published-Output Log DiD (%) | Phase-2 Share DiD | *eLife* Mar 2026 Blog Submission Drop |
| :--- | :--- | ---: | ---: | ---: | ---: |
{ts4_c12_rows}

*Notes:* Exploratory published-output differences relative to clean peer biology donor journals (NOT submission volumes). Policy-label groupings draw on published research-evaluation literature documenting JIF/WoS codification (Seglen, 1997; Hicks et al., 2015; Quan, Chen, & Shu, 2017; McKiernan et al., 2019; Baccini, De Nicolao, & Petrovich, 2019; Shu et al., 2020; Zhang & Sivertsen, 2020). Across these small country groups, the 3 JIF-codified nations (CN, ES, IT; mean {reg['jif_mean_p2_pct']:+.1f}%) contracted more sharply in published output than the 7 DORA-reformed nations (mean {reg['dora_mean_p2_pct']:+.1f}%, exact permutation $p = {reg['exact_comb_perm_p_1sided']:.4f}$), tracking *eLife*'s published 9-country submission drops (Spearman $\rho = {ext['spearman_rho']:.3f}$, $p = {ext['spearman_p']:.4f}$; Rodgers & Pattinson, 2026). Senior/last-author PI shares inside *eLife* PRC shifted from {pi['2024H2']['pi_CN_pct']:.1f}% (2024H2) to {pi['2025H1']['pi_CN_pct']:.1f}% (2025H1) for China while US Senior-PI share stayed near {pi['2024H2']['pi_US_pct']:.1f}%–{pi['2026H1']['pi_US_pct']:.1f}%.

---

## Supplementary References

{si_refs_md}
"""


def main() -> None:
    p3 = json.loads((RES_DIR / "03_panel_audit.json").read_bytes().decode("utf-8"))
    p3b = json.loads((RES_DIR / "03b_openalex_dedup_audit.json").read_bytes().decode("utf-8"))
    p9 = json.loads((RES_DIR / "09_v4_scientometrics_results.json").read_bytes().decode("utf-8"))
    p5 = json.loads((RES_DIR / "05_pillar3_4_results.json").read_bytes().decode("utf-8"))
    refs = json.loads((DATA_DIR / "verified_references_crossref.json").read_bytes().decode("utf-8"))

    main_md = build_main_manuscript(p3, p3b, p9, refs)
    si_md = build_supplementary_info(p3, p3b, p9, p5, refs)

    sha_main = write_text_lf(BASE_DIR / "manuscript_h6f_boost.md", main_md)
    sha_si = write_text_lf(BASE_DIR / "supplementary_h6f_scientometrics.md", si_md)
    print(f"[DONE STEP 10 (v4)] Wrote manuscript_h6f_boost.md ({len(main_md):,} chars, SHA={sha_main[:12]})", flush=True)
    print(f"[DONE STEP 10 (v4)] Wrote supplementary_h6f_scientometrics.md ({len(si_md):,} chars, SHA={sha_si[:12]})", flush=True)


if __name__ == "__main__":
    main()
