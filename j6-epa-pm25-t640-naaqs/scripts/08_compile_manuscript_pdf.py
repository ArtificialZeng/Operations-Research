"""Step 08 (Pillar 7): Compile manuscript_j6_boost.md + embedded 300-DPI figures into
camera-ready manuscript_j6_boost.pdf via escaped-underscore-safe balanced LaTeX->HTML
and Microsoft Edge --headless=new --print-to-pdf, with strict zero-leak verification
on extracted PDF text.
"""

from __future__ import annotations

import base64
import hashlib
import html
import json
import math
import re
import subprocess
import sys
from pathlib import Path

from econ_utils import FIG_DIR, RES_DIR, WS_DIR
from pypdf import PdfReader

MD_PATH = WS_DIR / "manuscript_j6_boost.md"
HTML_PATH = WS_DIR / "manuscript_j6_boost.html"
PDF_PATH = WS_DIR / "manuscript_j6_boost.pdf"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def _fmt_p_html(p: float | None) -> str:
    if p is None or not math.isfinite(p):
        return "n/a"
    if p < 1e-4:
        exp = math.floor(math.log10(p))
        mant = p / (10.0**exp)
        return f"{mant:.2f} &times; 10<sup>&minus;{abs(exp)}</sup>"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build all 5 figure titles and captions 100% dynamically from saved JSON receipts."""
    r1 = json.loads((RES_DIR / "01_appn_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_collocated_physics_speciation.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_ee_triage_hms_unification.json").read_text(encoding="utf-8"))

    cs11 = r1["accounting"]["combined_site_reg_appn_11of12"]
    wf21 = cs11["matched_2123_waterfall"]
    epa21 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2021_2023_final_08_08_24_0.xlsx"]
    epa22 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2022_2024_final_05_28_25.xlsx"]
    epa23 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2023_2025_final_06_12_26.xlsx"]
    ej_g = r1["ej_audit_acs2023"]["groups"]
    ej_t = r1["ej_audit_acs2023"]["formal_tests"]
    g_fl = ej_g["T640_Flipped"]
    g_st = ej_g["Still_Nonattainment"]
    g_cl = ej_g["Cleanly_Attaining"]

    sg_t = r2["sample_and_gradients"]["t640_fw"]
    sg_b = r2["sample_and_gradients"]["bam"]
    rt_t = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_t_st = r2["rooftop_dv_lottery_2023_2025"]["t640_fw_strict_4q3y"]
    rt_b = r2["rooftop_dv_lottery_2023_2025"]["bam"]
    smk_t = r2["zero_eiv_smoke_amplification"]["t640_fw"]
    smk_b = r2["zero_eiv_smoke_amplification"]["bam"]
    sp_t = r2["speciation_and_meteorology"]["t640_fw"]
    sp_b = r2["speciation_and_meteorology"]["bam"]
    s1_t = sp_t["model_s1_spec_met_level_site_cr1"]
    s2_t = sp_t["model_s2_interactions_level_site_cr1"]
    s1_b = sp_b["model_s1_spec_met_level_site_cr1"]
    u1_t_hms = r2["unification_u1_exceedance_multiplier"]["t640_fw"]["hms_heavy_smoke"]["gt_35_naaqs24h"]
    u1_t_oth = r2["unification_u1_exceedance_multiplier"]["t640_fw"]["other_site_ge25"]["gt_35_naaqs24h"]
    u1_b_hms = r2["unification_u1_exceedance_multiplier"]["bam"]["hms_heavy_smoke"]["gt_35_naaqs24h"]

    m3 = r3["monitor_year_dv1820_85_115"]
    c3 = r3["county_year_dv1820_85_115"]
    ri = r3["within_state_ri_B1000"]
    iu = r3["inverted_u_profile_dv1820"]["monitor_year_county_cr1"]["coefs"]
    u2 = r3["unification_u2_t640_ee_flagging"]

    pct_t_oth = 100.0 * (math.exp(smk_t["inst1_other_site_logratio_site_cr1"]["coefs"]["oth_ge25"]["beta"]) - 1.0)
    pct_t_hms = 100.0 * (math.exp(smk_t["inst3_noaa_hms_logratio_site_cr1"]["coefs"]["hms_h"]["beta"]) - 1.0)
    prec_21 = 100.0 * epa21["overlap_epa_with_cs_reg_incl"] / epa21["combined_site_reg_na_incl"]
    nulls = r1["exogenous_nulls_margins_acd"]
    pl_c = r3["robustness_specs_dv1820"]["fake_rule_placebo_2020_21_vs_18_19"]["coefs"]["treat_post"]
    eff_ts = [
        abs(smk_t["inst3_noaa_hms_level_site_cr1"]["coefs"]["hms_h"]["t_cr1"]),
        abs(rt_t["t_bias"]),
        abs(s1_t["coefs"]["oc"]["t_cr1"]),
        abs(smk_t["inst1_other_site_level_site_cr1"]["coefs"]["oth_ge25"]["t_cr1"]),
        abs(u1_t_hms["t_site_cr1"]),
        abs(u2["borderline_2225_t640_x_hms_heavy_flag"]["coefs"]["t640_x_hms_h"]["t_cr1"]),
        abs(m3["true_ee_flag"]["did_2225_state_cr1"]["coefs"]["tp_2225"]["t_cr1"]),
        abs(m3["unconc_flag"]["did_2225_state_cr1"]["coefs"]["tp_2225"]["t_cr1"]),
    ]
    null_ts = [
        abs(smk_b["inst1_other_site_level_site_cr1"]["coefs"]["oth_ge25"]["t_cr1"]),
        abs(nulls["margin_d_frm_exog_dv1820_county_cr1"]["coefs"]["tp"]["t_cr1"]),
        abs(nulls["margin_a_share_fem_exog_dv1820"]["coefs"]["tp"]["t_cr1"]),
        abs(nulls["margin_c_monitor_survival_exog_dv1820"]["coefs"]["nb"]["t_cr1"]),
        abs(pl_c["t_cr1"]),
        abs(c3["true_ee_conc"]["event_study_county_cr1"]["coefs"]["nb_2025"]["t_cr1"]),
    ]
    null_ps = [
        smk_b["inst1_other_site_level_site_cr1"]["wcb"]["p_wcb"],
        nulls["margin_d_frm_exog_dv1820_county_cr1"]["wcb"]["p_wcb"],
        nulls["margin_a_share_fem_exog_dv1820"]["wcb"]["p_wcb"],
        nulls["margin_c_monitor_survival_exog_dv1820"]["wcb"]["p_wcb"],
        pl_c["p_cr1"],
        c3["true_ee_conc"]["event_study_county_cr1"]["coefs"]["nb_2025"]["p_cr1"],
    ]

    return {
        "fig1_t640_windfall_and_ej_map.png": (
            "Figure 1. Stitched 40 CFR Part 50 Appendix N Nonattainment Waterfall, Official EPA Reconciliation, and Regional &amp; Demographic Audit.",
            (
                f"Panel A traces county nonattainment counts (&ge; 9.1 &mu;g/m<sup>3</sup>) and affected U.S. populations across the "
                f"{cs11['n_counties_matched_2123']} matched Combined-Site regulatory counties: EPA&rsquo;s May 2024 T640 software alignment "
                f"alone drops 2021&ndash;2023 nonattainment from {wf21['raw_2123']['counties']} ({wf21['raw_2123']['pop_millions']:.2f}M) to "
                f"{wf21['aln_2123']['counties']} ({wf21['aln_2123']['pop_millions']:.2f}M)&mdash;flipping {wf21['flip_t640_alone']['counties']} "
                f"counties ({wf21['flip_t640_alone']['pop_millions']:.2f}M residents)&mdash;with diamonds overlaying official EPA published "
                f"Table 4a counts ({epa21['epa_na_counties']} in 2021&ndash;2023 [{epa21['overlap_epa_with_cs_reg_incl']}/"
                f"{epa21['combined_site_reg_na_incl']} = {prec_21:.1f}% precision], {epa22['epa_na_counties']} in 2022&ndash;2024, "
                f"{epa23['epa_na_counties']} in 2023&ndash;2025). Panel B displays the geographic and Census SAIPE 2023 / PEP 2024 "
                f"demographic audit: {g_fl['region_counts'].get('MW',0)+g_fl['region_counts'].get('SO',0)+g_fl['region_counts'].get('NE',0)}/"
                f"{g_fl['n_counties']} T640-flipped counties lie outside the West ({ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['flipped_pct']:.1f}% "
                f"MW+SO vs. {ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['comp_pct']:.1f}% Still-NA, Fisher <em>p</em> = "
                f"{ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['fisher_p']:.3f}), with significantly higher Black resident shares "
                f"than cleanly attaining counties ({g_fl['unweighted_means']['pct_black_nh']:.1f}% vs. {g_cl['unweighted_means']['pct_black_nh']:.1f}%, "
                f"Welch <em>p</em> = {ej_t['Flipped_vs_Cleanly_Attaining']['pct_black_nh']['welch_p']:.3f}) while heavily Hispanic Western basins "
                f"remain in nonattainment ({g_st['unweighted_means']['pct_hispanic']:.1f}% vs. {g_fl['unweighted_means']['pct_hispanic']:.1f}%)."
            ),
        ),
        "fig2_rooftop_lottery_and_regional_bias.png": (
            "Figure 2. Same-Rooftop 2023&ndash;2025 Statutory Nonattainment Lottery and Regional &amp; Seasonal Optical Bias Gradient.",
            (
                f"Panel A scatters paired-day 2023&ndash;2025 Appendix N Design Values for post-alignment firmware T640_FW (636/638) against "
                f"collocated gravimetric FRMs across {rt_t['n_sites']} rooftops (mean DV bias +{rt_t['mean_dv_bias']:.3f} &mu;g/m<sup>3</sup>, "
                f"<em>t</em> = {rt_t['t_bias']:+.2f}, <em>p</em> = {_fmt_p_html(rt_t['p_bias'])}): {rt_t['fem_na_frm_att']} rooftops violate "
                f"9.0 &mu;g/m<sup>3</sup> on T640_FW while attaining on FRM two meters away versus only {rt_t['frm_na_fem_att']} in reverse "
                f"({rt_t['odds_ratio_lottery']:.1f}:1, exact binomial <em>p</em> = {_fmt_p_html(rt_t['binom_p'])}; strict 4q&times;3y stitched "
                f"{rt_t_st['fem_na_frm_att']} vs. {rt_t_st['frm_na_fem_att']}, <em>p</em> = {_fmt_p_html(rt_t_st['binom_p'])}; BAM "
                f"{rt_b['fem_na_frm_att']} vs. {rt_b['frm_na_fem_att']}, <em>p</em> = {rt_b['binom_p']:.3f}). Panel B compares Site-clustered "
                f"mean daily bias (&plusmn;95% CI) across U.S. regions and seasons ({sg_t['sample_2023_2025']['n_pairs']:,} T640_FW pairs vs. "
                f"{sg_b['sample_2023_2025']['n_pairs']:,} BAM pairs): T640_FW peaks in the Midwest (+{sg_t['by_region_2023_2025']['MW']['mean_bias']:.2f}) "
                f"and Winter DJF (+{sg_t['by_season_2023_2025']['DJF']['mean_bias']:.2f}) and nears zero in the arid West "
                f"(+{sg_t['by_region_2023_2025']['WE']['mean_bias']:.2f}), whereas heated-inlet BAM turns negative in Midwest/Winter."
            ),
        ),
        "fig3_zero_eiv_smoke_and_speciation_physics.png": (
            "Figure 3. Strictly Zero-EIV Nonlinear Wildfire Smoke Amplification and Direct EPA Chemical Speciation &amp; Hygroscopicity Physics.",
            (
                f"Panel A compares daily (FEM &minus; FRM) bias across three EIV-free smoke instruments (Site FE + Month FE, 95% Site CR1 CIs): "
                f"post-alignment T640_FW explodes by +{smk_t['inst1_other_site_level_site_cr1']['coefs']['oth_ge25']['beta']:.2f} &mu;g/m<sup>3</sup> "
                f"(+{pct_t_oth:.1f}%, <em>p</em><sub>WCB</sub> = {smk_t['inst1_other_site_level_site_cr1']['wcb']['p_wcb']:.3f}) on independent "
                f"other-site &ge;25 &mu;g/m<sup>3</sup> days, +{smk_t['inst2_bland_altman_level_site_cr1']['coefs']['ba_ge25']['beta']:.2f} on "
                f"Bland-Altman &ge;25, and +{smk_t['inst3_noaa_hms_level_site_cr1']['coefs']['hms_h']['beta']:.2f} (+{pct_t_hms:.1f}%, "
                f"<em>t</em> = {smk_t['inst3_noaa_hms_level_site_cr1']['coefs']['hms_h']['t_cr1']:+.2f}) under external satellite NOAA HMS Heavy "
                f"plumes, whereas BAM stays flat on other-site &ge;25 ({smk_b['inst1_other_site_level_site_cr1']['coefs']['oth_ge25']['beta']:+.2f}, "
                f"<em>p</em><sub>WCB</sub> = {smk_b['inst1_other_site_level_site_cr1']['wcb']['p_wcb']:.3f}). Panel B plots Site+Month FE chemical "
                f"speciation and meteorology slopes ({s1_t['n']:,} T640_FW vs. {s1_b['n']:,} BAM paired days): T640_FW over-responds to light-scattering "
                f"Organic Carbon (+{s1_t['coefs']['oc']['beta']:.3f}, <em>t</em> = {s1_t['coefs']['oc']['t_cr1']:+.2f}; +{s2_t['coefs']['oc_x_hms_h']['beta']:.3f} "
                f"more under HMS Heavy smoke) and RH (+{s1_t['coefs']['rh_10']['beta']:.3f} per +10%, <em>t</em> = {s1_t['coefs']['rh_10']['t_cr1']:+.2f}) "
                f"while under-reading light-absorbing Elemental Carbon ({s1_t['coefs']['ec']['beta']:+.3f}, <em>t</em> = {s1_t['coefs']['ec']['t_cr1']:+.2f}); "
                f"BAM is null on OC/EC and negative on RH and semi-volatile NO<sub>3</sub><sup>&minus;</sup>."
            ),
        ),
        "fig4_ee_triage_event_study_and_decomposition.png": (
            "Figure 4. Pre-Trend-Clean 40 CFR &sect; 50.14 Exceptional Event Triage Event Study (2018&ndash;2025) and Inverted-U Threshold Profile.",
            (
                f"Panel A plots full 2018&ndash;2025 County-Year event-study coefficients (exogenous DV<sub>18&ndash;20</sub> [8.5, 11.5] vs. &lt;8.0, "
                f"ref = 2020, County FE + State&times;Year FE + 9 nonlinear smoke controls, 95% County CR1 CIs) decomposing All State EE Flags "
                f"(navy; joint pre-<em>F</em> <em>p</em> = {c3['true_ee_flag']['event_study_county_cr1']['joint_F']['p']:.3f}; pooled DiD "
                f"+{100*c3['true_ee_flag']['did_2225_state_cr1']['coefs']['tp_2225']['beta']:.2f} pp, State <em>p</em><sub>WCB</sub> = "
                f"{c3['true_ee_flag']['did_2225_state_cr1']['wcb']['p_wcb']:.3f}, RI <em>p</em> = {ri['county_year']['p_ri_2sided']:.4f}) into "
                f"Unconcurred Precautionary Flags (amber; pre-<em>F</em> <em>p</em> = {c3['unconc_flag']['event_study_county_cr1']['joint_F']['p']:.3f}) "
                f"and True EPA-Concurred Exclusions (teal; joint pre-<em>F</em> <em>p</em> = "
                f"{c3['true_ee_conc']['event_study_county_cr1']['joint_F']['p']:.3f}), displaying both the 2023 designation-window peak "
                f"(+{100*c3['true_ee_flag']['event_study_county_cr1']['coefs']['nb_2023']['beta']:.1f} pp) and honest 2024&ndash;2025 EPA-concurred nulls. "
                f"Panel B traces the Monitor-Year inverted-U across pre-rule DV<sub>18&ndash;20</sub> bins (ref &lt;7.0): "
                f"7.0&ndash;8.5 ({100*iu['b_70_85']['beta']:+.2f} pp), 8.5&ndash;9.5 (+{100*iu['b_85_95']['beta']:.2f} pp), "
                f"9.5&ndash;11.5 (+{100*iu['b_95_115']['beta']:.2f} pp), and &gt;11.5 (+{100*iu['b_gt115']['beta']:.2f} pp), with inset "
                f"Monitor-Year headline +{100*m3['true_ee_flag']['did_2225_state_cr1']['coefs']['tp_2225']['beta']:.2f} pp "
                f"(State <em>p</em><sub>WCB</sub> = {m3['true_ee_flag']['did_2225_state_cr1']['wcb']['p_wcb']:.3f}, RI <em>p</em> = "
                f"{ri['monitor_year']['p_ri_2sided']:.4f})."
            ),
        ),
        "fig5_optical_to_flagging_multiplier.png": (
            "Figure 5. Unifying Optical Physics and 40 CFR &sect; 50.14 Triage: Exceedance Trigger Doubling (U1 &amp; U2) and Master Empirical Audit Across Verified Effects vs. Clean Honest Nulls.",
            (
                f"Panel A (Tests U1 &amp; U2) plots collocated same-rooftop &gt;35 &mu;g/m<sup>3</sup> daily exceedance rates: under satellite NOAA HMS Heavy "
                f"smoke, post-alignment T640_FW triggers {u1_t_hms['trigger_multiplier_ratio']:.2f}&times; more federal exceedances than collocated FRMs "
                f"({u1_t_hms['fem_exceed_n']} vs. {u1_t_hms['frm_exceed_n']}, {u1_t_hms['fem_only_discordant']} vs. {u1_t_hms['frm_only_discordant']} "
                f"discordant days, exact McNemar <em>p</em> = {_fmt_p_html(u1_t_hms['mcnemar_exact_p'])}; other-site &ge;25: "
                f"{u1_t_oth['trigger_multiplier_ratio']:.2f}&times;, {u1_t_oth['fem_only_discordant']} vs. {u1_t_oth['frm_only_discordant']}, "
                f"<em>p</em> = {_fmt_p_html(u1_t_oth['mcnemar_exact_p'])}), while BAM is dead zero (HMS Heavy <em>p</em> = {u1_b_hms['mcnemar_exact_p']:.3f}). "
                f"Inset summarizes Test U2 (State&times;Year FE + satellite HMS controls inside DV<sub>18&ndash;20</sub> [8.5, 11.5], 2022&ndash;2025): "
                f"T640 &times; log(HMS Heavy) raises EE flagging by +{100*u2['borderline_2225_t640_x_hms_heavy_flag']['coefs']['t640_x_hms_h']['beta']:.2f} pp "
                f"(<em>t</em> = {u2['borderline_2225_t640_x_hms_heavy_flag']['coefs']['t640_x_hms_h']['t_cr1']:+.2f}, <em>p</em><sub>WCB</sub> = "
                f"{u2['borderline_2225_t640_x_hms_heavy_flag']['wcb']['p_wcb']:.3f}) and T640 claims "
                f"+{u2['borderline_2225_state_yr_fe_ee_red']['coefs']['is_t640_f']['beta']:.3f} &mu;g/m<sup>3</sup> larger annual EE exclusions "
                f"(<em>p</em><sub>WCB</sub> = {u2['borderline_2225_state_yr_fe_ee_red']['wcb']['p_wcb']:.3f}); see Table 5 for Test U3 satellite strata. "
                f"Panel B presents the unified Master Audit forest of cluster-robust <em>t</em>-statistics across all 14 core tests, contrasting all eight "
                f"verified optical and regulatory effects (|<em>t</em>| = {min(eff_ts):.1f}&ndash;{max(eff_ts):.1f}) directly against all six clean honest nulls "
                f"(pure BAM 170/209 smoke bias, Margin D FRM, Margin A switching, Margin C monitor survival, Fake-Rule Placebo, and 2025 concurred EE flow; "
                f"|<em>t</em>| &le; {max(null_ts):.2f}, <em>p</em> &ge; {min(null_ps):.2f})."
            ),
        ),
    }


def _extract_braced(s: str, start: int) -> tuple[str, int]:
    depth = 0
    i = start
    while i < len(s):
        if s[i] == "{":
            depth += 1
        elif s[i] == "}":
            depth -= 1
            if depth == 0:
                return s[start + 1 : i], i + 1
        i += 1
    return s[start + 1 :], len(s)


def _tex_to_html(expr: str) -> str:
    s = expr.strip()
    s = s.replace(r"\$", "$")

    # Convert degree symbols before superscript regexes
    s = s.replace(r"^{\circ}", "&deg;")
    s = s.replace(r"^\circ", "&deg;")

    while r"\frac{" in s:
        idx = s.index(r"\frac{")
        num, nxt = _extract_braced(s, idx + len(r"\frac"))
        den, end = _extract_braced(s, nxt) if nxt < len(s) and s[nxt] == "{" else ("", nxt)
        n_clean, d_clean = num.strip(), den.strip()
        if n_clean == "1" and d_clean == "2":
            frac_repl = "&frac12;"
        else:
            n_wrap = f"({n_clean})" if re.search(r"[+\-= ]", n_clean) else n_clean
            d_wrap = f"({d_clean})" if re.search(r"[+\-= ]", d_clean) else d_clean
            frac_repl = f"{n_wrap}/{d_wrap}" if (n_wrap == n_clean and d_wrap == d_clean) else f"{n_wrap} / {d_wrap}"
        s = s[:idx] + frac_repl + s[end:]

    macro_wrappers = [
        (r"\text{", '<span class="rm">', "</span>"),
        (r"\mathrm{", '<span class="rm">', "</span>"),
        (r"\mathcal{", '<span class="cal">', "</span>"),
        (r"\mathbb{", '<span class="rm"><b>', "</b></span>"),
        (r"\mathbf{", "<b>", "</b>"),
        (r"\boldsymbol{", "<b>", "</b>"),
        (r"\hat{", "", "&#770;"),
        (r"\bar{", "", "&#772;"),
        (r"\overline{", "", "&#772;"),
        (r"\tilde{", "", "&#771;"),
    ]
    for macro, pre, post in macro_wrappers:
        while macro in s:
            idx = s.index(macro)
            inner, end = _extract_braced(s, idx + len(macro) - 1)
            s = s[:idx] + f"{pre}{inner}{post}" + s[end:]

    # Protect escaped underscores \_ inside math mode so they NEVER trigger subscript regexes
    s = s.replace(r"\_", "&#95;")

    replacements = [
        (r"{,}", ","),
        (r"\arg\min", '<span class="rm">arg min</span>'),
        (r"\qquad", "&emsp;&emsp;"),
        (r"\quad", "&emsp;"),
        (r"\iff", "&hArr;"),
        (r"\Rightarrow", "&rArr;"),
        (r"\setminus", " &#8726; "),
        (r"\partial", "&part;"),
        (r"\gg", "&gg;"),
        (r"\ll", "&ll;"),
        (r"\mid", " | "),
        (r"\Big(", "("),
        (r"\Big)", ")"),
        (r"\Big[", "["),
        (r"\Big]", "]"),
        (r"\big[", "["),
        (r"\big]", "]"),
        (r"\big(", "("),
        (r"\big)", ")"),
        (r"\left(", "("),
        (r"\right)", ")"),
        (r"\left[", "["),
        (r"\right]", "]"),
        (r"\left", ""),
        (r"\right", ""),
        (r"\exp", "exp"),
        (r"\log", "log"),
        (r"\min", "min"),
        (r"\max", "max"),
        (r"\sum", "&Sigma;"),
        (r"\times", "&times;"),
        (r"\cdot", "&middot;"),
        (r"\pm", "&plusmn;"),
        (r"\le", "&le;"),
        (r"\ge", "&ge;"),
        (r"\neq", "&ne;"),
        (r"\approx", "&approx;"),
        (r"\equiv", "&equiv;"),
        (r"\to", "&rarr;"),
        (r"\in", "&isin;"),
        (r"\Phi", "&Phi;"),
        (r"\Pi", "&Pi;"),
        (r"\Omega", "&Omega;"),
        (r"\Delta", "&Delta;"),
        (r"\kappa", "&kappa;"),
        (r"\theta", "&theta;"),
        (r"\beta", "&beta;"),
        (r"\alpha", "&alpha;"),
        (r"\delta", "&delta;"),
        (r"\phi", "&phi;"),
        (r"\psi", "&psi;"),
        (r"\gamma", "&gamma;"),
        (r"\eta", "&eta;"),
        (r"\nu", "&nu;"),
        (r"\pi", "&pi;"),
        (r"\omega", "&omega;"),
        (r"\varepsilon", "&epsilon;"),
        (r"\epsilon", "&epsilon;"),
        (r"\tau", "&tau;"),
        (r"\rho", "&rho;"),
        (r"\mu", "&mu;"),
        (r"\sigma", "&sigma;"),
        (r"\lambda", "&lambda;"),
        (r"\circ", "&deg;"),
        (r"\ell", "&#8467;"),
        (r"\%", "%"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\|", "|"),
        (r"\ldots", "&hellip;"),
        (r"\dots", "&hellip;"),
        (r"\;", "&ensp;"),
        (r"\,", "&thinsp;"),
        (r"\!", ""),
        (r"\ ", " "),
        ("--", "&ndash;"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    for _ in range(3):
        for sym, tag in [("_", "sub"), ("^", "sup")]:
            while f"{sym}{{" in s:
                idx = s.index(f"{sym}{{")
                inner, end = _extract_braced(s, idx + 1)
                s = s[:idx] + f"<{tag}>{inner}</{tag}>" + s[end:]

    s = re.sub(r"(?<![A-Za-z0-9])_([A-Za-z0-9+\-]+|&[a-z]+;)", r"<sub>\1</sub>", s)
    s = re.sub(r"([A-Za-z0-9>])_([A-Za-z0-9]+)\b", r"\1<sub>\2</sub>", s)
    s = re.sub(r"\^([A-Za-z0-9+\-*]+)", r"<sup>\1</sup>", s)

    parts = re.split(r"(<[^>]+>)", s)
    for i in range(0, len(parts), 2):
        # Preserve HTML entity names like &ndash; while converting unary/binary hyphens to minus
        parts[i] = re.sub(r"(?<![&a-zA-Z])-(?![a-zA-Z]*;)", "&minus;", parts[i])
    return "".join(parts)


def _inline_md(text: str) -> str:
    tokens: list[str] = []

    def stash(html_frag: str) -> str:
        idx = len(tokens)
        tokens.append(html_frag)
        return f"\x00TOK{idx}\x00"

    text = re.sub(r"`([^`]+)`", lambda m: stash(f"<code>{html.escape(m.group(1))}</code>"), text)
    text = text.replace(r"\$", "\x00DOLLAR\x00")
    text = re.sub(
        r"\$([^$\n]+)\$",
        lambda m: stash(
            f'<span class="math">{_tex_to_html(m.group(1).replace(chr(0) + "DOLLAR" + chr(0), r"\$"))}</span>'
        ),
        text,
    )
    text = text.replace("\x00DOLLAR\x00", "$")

    escaped = html.escape(text)
    escaped = re.sub(r"\*\*\*([^*]+?)\*\*\*", r"<strong><em>\1</em></strong>", escaped)
    escaped = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"(?<!\*)\*([^*]+?)\*(?!\*)", r"<em>\1</em>", escaped)
    for i, frag in enumerate(tokens):
        escaped = escaped.replace(f"\x00TOK{i}\x00", frag)
    return escaped


def _embed_figure_html(fname: str, figure_blocks: dict[str, tuple[str, str]]) -> str:
    img_path = FIG_DIR / fname
    b64 = base64.b64encode(img_path.read_bytes()).decode("ascii")
    title_html, caption_html = figure_blocks[fname]
    alt_txt = re.sub(r"<[^>]+>", "", title_html)
    return (
        f'<figure class="pub-fig">'
        f'<img src="data:image/png;base64,{b64}" alt="{html.escape(alt_txt)}" />'
        f"<figcaption><strong>{title_html}</strong> {caption_html}</figcaption>"
        f"</figure>"
    )


def convert_md_to_html(md_text: str, figure_blocks: dict[str, tuple[str, str]]) -> str:
    lines = md_text.splitlines()
    body: list[str] = []
    inserted_figs: set[str] = set()
    i = 0
    n = len(lines)

    while i < n:
        ln = lines[i]
        stripped = ln.strip()
        if not stripped:
            i += 1
            continue
        m_fig = re.match(r"^<!--\s*FIGURE:([A-Za-z0-9_.\-]+)\s*-->$", stripped)
        if m_fig:
            fname = m_fig.group(1)
            if fname in figure_blocks and fname not in inserted_figs:
                body.append(_embed_figure_html(fname, figure_blocks))
                inserted_figs.add(fname)
            i += 1
            continue
        if stripped == "---":
            body.append("<hr />")
            i += 1
            continue
        if stripped.startswith("$$") and stripped.endswith("$$") and len(stripped) > 4:
            expr = stripped[2:-2].strip()
            body.append(f'<div class="eq-block">{_tex_to_html(expr)}</div>')
            i += 1
            continue

        m_h = re.match(r"^(#{1,3})\s+(.*)$", stripped)
        if m_h:
            lvl = len(m_h.group(1))
            cls = ' class="paper-title"' if lvl == 1 else ""
            body.append(f"<h{lvl}{cls}>{_inline_md(m_h.group(2))}</h{lvl}>")
            i += 1
            continue

        if stripped.startswith("|") and i + 1 < n and re.match(r"^\|\s*:?---", lines[i + 1].strip()):
            tbl_lines = [stripped]
            i += 1
            while i < n and lines[i].strip().startswith("|"):
                tbl_lines.append(lines[i].strip())
                i += 1

            def split_md_row(row_s: str) -> list[str]:
                tmp = row_s.strip("|").replace(r"\|", "\x00PIPE\x00")
                return [c.replace("\x00PIPE\x00", r"\|").strip() for c in tmp.split("|")]

            headers = split_md_row(tbl_lines[0])
            aligns = split_md_row(tbl_lines[1])
            if len(headers) != len(aligns):
                raise ValueError(f"Markdown table column mismatch: header={len(headers)} vs aligns={len(aligns)}: {headers}")
            col_cls = []
            for a in aligns:
                if a.startswith(":") and a.endswith(":"):
                    col_cls.append("center")
                elif a.endswith(":"):
                    col_cls.append("right")
                else:
                    col_cls.append("left")
            th_html = "".join(
                f'<th class="{col_cls[idx] if idx < len(col_cls) else "left"}">{_inline_md(h)}</th>'
                for idx, h in enumerate(headers)
            )
            rows_html = []
            for rln in tbl_lines[2:]:
                cells = split_md_row(rln)
                tds = "".join(
                    f'<td class="{col_cls[idx] if idx < len(col_cls) else "left"}">{_inline_md(c)}</td>'
                    for idx, c in enumerate(cells)
                )
                rows_html.append(f"<tr>{tds}</tr>")
            body.append(
                f'<div class="table-wrap"><table><thead><tr>{th_html}</tr></thead>'
                f'<tbody>{"".join(rows_html)}</tbody></table></div>'
            )
            continue

        if stripped.startswith("- "):
            items = []
            while i < n and lines[i].strip().startswith("- "):
                items.append(f"<li>{_inline_md(lines[i].strip()[2:])}</li>")
                i += 1
            body.append(f"<ul>{''.join(items)}</ul>")
            continue

        m_ol = re.match(r"^(\d+)\.\s+", stripped)
        if m_ol:
            start_num = int(m_ol.group(1))
            items = []
            while i < n and re.match(r"^\d+\.\s+", lines[i].strip()):
                item_txt = re.sub(r"^\d+\.\s+", "", lines[i].strip())
                i += 1
                sub_items = []
                while i < n and re.match(r"^\s{2,}-\s+", lines[i]):
                    sub_items.append(f"<li>{_inline_md(lines[i].strip()[2:])}</li>")
                    i += 1
                sub_html = f"<ul>{''.join(sub_items)}</ul>" if sub_items else ""
                items.append(f"<li>{_inline_md(item_txt)}{sub_html}</li>")
            start_attr = f' start="{start_num}"' if start_num != 1 else ""
            is_refs = bool(body and "<h2>References</h2>" in body[-1])
            cls_attr = ' class="refs-list"' if is_refs else ""
            body.append(f"<ol{cls_attr}{start_attr}>{''.join(items)}</ol>")
            continue

        para_raw_lines = [ln]
        i += 1
        while i < n:
            nxt_raw = lines[i]
            nxt = nxt_raw.strip()
            if (
                not nxt
                or nxt == "---"
                or nxt.startswith(("#", "|", "- ", "$$", "<!--"))
                or re.match(r"^\d+\.\s+", nxt)
            ):
                break
            para_raw_lines.append(nxt_raw)
            i += 1
        para_first = para_raw_lines[0].strip()
        p_cls = (
            ' class="table-caption"'
            if para_first.startswith("**Table ")
            else (' class="table-notes"' if para_first.startswith(("*Notes:*", "*Source:*")) else "")
        )
        segs: list[str] = []
        cur_seg: list[str] = []
        for raw_l in para_raw_lines:
            cur_seg.append(raw_l.strip())
            if raw_l.endswith("  "):
                segs.append(_inline_md(" ".join(cur_seg)))
                cur_seg = []
        if cur_seg:
            segs.append(_inline_md(" ".join(cur_seg)))
        body.append(f"<p{p_cls}>{'<br />'.join(segs)}</p>")

    for fname in figure_blocks:
        if fname not in inserted_figs and (FIG_DIR / fname).exists():
            body.append(_embed_figure_html(fname, figure_blocks))

    css = """
    @page {
      size: letter;
      margin: 0.65in 0.65in 0.72in 0.65in;
      @top-right {
        content: "Optical Bias, Wildfire Smoke Amplification, and Regulatory Triage (2024 PM2.5 NAAQS)";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.2pt;
        color: #555;
      }
      @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.9pt;
        color: #555;
      }
    }
    @page :first { @top-right { content: normal; } }
    body {
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.2pt;
      line-height: 1.42;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1.paper-title {
      font-size: 13.6pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }
    h2 {
      font-size: 10.9pt;
      color: #0b2545;
      margin: 11pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }
    h3 {
      font-size: 9.6pt;
      color: #1e3a5f;
      margin: 8.5pt 0 4pt 0;
      page-break-after: avoid;
    }
    p { margin: 0 0 5.3pt 0; text-align: justify; }
    p.table-caption {
      font-size: 8.3pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }
    p.table-notes {
      font-size: 7.3pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }
    ul, ol { margin: 3pt 0 6pt 16pt; padding: 0; }
    li { margin: 0 0 2.6pt 0; text-align: justify; }
    ol.refs-list li { text-align: left; font-size: 8.0pt; line-height: 1.32; break-inside: avoid; page-break-inside: avoid; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.2pt;
      background: #f1f5f9;
      padding: 0.4pt 2.0pt;
      border-radius: 2pt;
    }
    hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 7.5pt 0; }
    .math { font-family: "Cambria Math", Georgia, serif; font-style: italic; }
    .math .rm, .eq-block .rm { font-style: normal; }
    .math .cal, .eq-block .cal { font-family: "Lucida Calligraphy", "Cambria Math", serif; font-style: italic; }
    sup, sub { white-space: nowrap; }
    .eq-block {
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.3pt;
      text-align: center;
      margin: 6.2pt 0;
      padding: 5.5pt 10pt;
      background: #f8fafc;
      border-left: 2pt solid #0b2545;
      break-inside: avoid;
      page-break-inside: avoid;
    }
    .table-wrap { margin: 4pt 0 4pt 0; page-break-inside: avoid; }
    table {
      width: 100%;
      border-collapse: collapse;
      font-size: 6.6pt;
      line-height: 1.20;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }
    thead tr { border-bottom: 0.8pt solid #334155; background: #f8fafc; }
    th, td { padding: 2.0pt 2.5pt; vertical-align: top; }
    td .math, th .math { white-space: nowrap; }
    td code { white-space: nowrap; font-size: 6.3pt; }
    tbody tr:nth-child(even) { background: #fbfdff; }
    th.left, td.left { text-align: left; }
    th.center, td.center { text-align: center; }
    th.right, td.right { text-align: right; }
    figure.pub-fig {
      margin: 7.5pt 0 7.5pt 0;
      padding: 5pt;
      border: 0.5pt solid #e2e8f0;
      background: #ffffff;
      page-break-inside: avoid;
      text-align: center;
    }
    figure.pub-fig img {
      max-width: 100%;
      max-height: 3.85in;
      height: auto;
      display: block;
      margin: 0 auto 4.5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 7.4pt;
      line-height: 1.29;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        f"<title>Optical Measurement Bias, Wildfire Smoke Amplification, and Regulatory Triage (2024 PM2.5 NAAQS)</title>"
        f"<style>{css}</style></head><body>{''.join(body)}</body></html>"
    )


def verify_pdf_zero_leaks(pdf_path: Path) -> tuple[int, list[str]]:
    reader = PdfReader(str(pdf_path))
    full_txt = "\n".join((p.extract_text() or "") for p in reader.pages)
    bad_patterns = [
        r"\\[A-Za-z]+",
        r"\\\$",
        r"\\_",
        r"\$\$",
        r"\*\*",
        r"\|---",
        r"\{,\}",
        r"\\text\{",
        r"\\mathbf\{",
        r"\\mathbb\{",
        r"\\frac\{",
        r"\\mathcal\{",
        r"\bp_WCB\b",
        r"\^[0-9A-Za-z{]",
        r"fig[1-5]_[a-z0-9_]+\.png",
        r"<!--",
        r"TOK\d+",
        r"&[a-z]+;",
        r"&#\d+;",
        r"</?(?:sub|sup|em|strong|span|div|i|b)>",
        r"\bNaN\b",
        r"\bInf\b",
    ]
    leaks = []
    for pat in bad_patterns:
        m = re.search(pat, full_txt)
        if m:
            leaks.append(f"{pat} (matched: {m.group(0)!r})")
    return len(reader.pages), leaks


def main() -> int:
    figure_blocks = build_dynamic_figure_blocks()
    md_text = MD_PATH.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text, figure_blocks)
    HTML_PATH.write_bytes(html_doc.encode("utf-8"))

    if not EDGE_EXE.exists():
        print(f"[ERROR] Microsoft Edge not found at {EDGE_EXE}", file=sys.stderr)
        return 1

    cmd = [
        str(EDGE_EXE),
        "--headless=new",
        "--disable-gpu",
        "--no-pdf-header-footer",
        f"--print-to-pdf={PDF_PATH}",
        HTML_PATH.as_uri(),
    ]
    res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    if res.returncode != 0 or not PDF_PATH.exists() or PDF_PATH.stat().st_size < 50_000:
        print(f"[ERROR] Edge PDF compile failed rc={res.returncode}: {res.stderr}", file=sys.stderr)
        return 1

    n_pages, leaks = verify_pdf_zero_leaks(PDF_PATH)
    HTML_PATH.unlink(missing_ok=True)
    if leaks:
        print(f"[ERROR] Leaked LaTeX/Markdown/HTML tokens found in PDF: {leaks}", file=sys.stderr)
        return 2
    sha = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
    print(
        f"[DONE STEP 08] Compiled {PDF_PATH} ({PDF_PATH.stat().st_size:,} bytes, "
        f"{n_pages} pages, 0 leaked tokens, SHA-256: {sha})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
