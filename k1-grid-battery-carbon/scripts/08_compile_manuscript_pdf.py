"""Step 08 (Pillar 7): Compile manuscript_k1_boost.md + embedded 300-DPI figures into
camera-ready manuscript_k1_boost.pdf via escaped-underscore-safe balanced LaTeX->HTML
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

MD_PATH = WS_DIR / "manuscript_k1_boost.md"
HTML_PATH = WS_DIR / "manuscript_k1_boost.html"
PDF_PATH = WS_DIR / "manuscript_k1_boost.pdf"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def _fmt_p_html(p: float | None) -> str:
    if p is None or not math.isfinite(p):
        return "n/a"
    if p < 1e-4:
        return "&lt;0.0001"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def build_dynamic_figure_blocks() -> dict[str, tuple[str, str]]:
    """Build all 5 figure titles and captions 100% dynamically from saved JSON receipts."""
    r1 = json.loads((RES_DIR / "01_telemetry_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_panel_a_wls_results.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_cems_carbon_curtailment_results.json").read_text(encoding="utf-8"))
    r4 = json.loads((RES_DIR / "04_formal_model_verification.json").read_text(encoding="utf-8"))

    sp = r2["main_and_robustness_specs"]
    ll = r2["distributed_6m_lead_lag"]["WLS_ALL49_BA_YM"]
    lob = r2["lobao_49_wls"]
    pk_all = r2["diurnal_24h_profile"]["ALL_49"][19]["ng"]
    pk_dce = r2["diurnal_24h_profile"]["DROP_CISO_ERCO_47"][19]["ng"]

    c_rep = r1["ciso_telemetry_repair"]
    ues = r1["ues_charging_bug"]
    m14 = r1["metered_14_bas_totals"]
    t14 = {r["ba"]: r for r in r1["metered_14_bas_table"]}
    fpl_a = r1["physical_bound_anomalies"][0]
    cems_al = r1["cems_utc_alignment_audit"]

    fl14 = r3["fleet_aggregates"]["all_14_bas"]
    cv = r3["cems_vs_egrid_cross_validation"]
    cc = r3["caiso_noncircular_curtailment"]
    bins = cc["curtailment_stratified_bins"]
    c3_map = {r["ba"]: r for r in r3["ba_carbon_table"]}
    dy = r2["high_freq_daily_ba_ym_fe"]
    dur = r2["duration_mwh_vs_mw"]
    ng_corr = c_rep["eia930_ng_corruption_202312_202512"]

    dom_drop_pct = 100.0 * (1.0 - bins[3]["mef_cems_dom_kg_mwh"] / bins[0]["mef_cems_dom_kg_mwh"])
    sys_drop_pct = 100.0 * (1.0 - bins[3]["mef_cems_sys_kg_mwh"] / bins[0]["mef_cems_sys_kg_mwh"])
    jb = cc["joint_block_bootstrap_1000"]
    jb_ms = jb["net_sys_main"]
    jb_ls = jb["net_sys_pure_load"]
    jb_md = jb["net_dom_main"]
    m_noctrl = sp["WLS_ALL49_NO_CONTROLS_NG"]
    cems_r_min = min(cems_al[b]["r_at_lag0"] for b in ["CISO", "ERCO", "MISO", "SOCO", "DUK"])
    cems_r_max = max(cems_al[b]["r_at_lag0"] for b in ["CISO", "ERCO", "MISO", "SOCO", "DUK"])

    eff_tvals = [
        c3_map["ERCO"]["net_cems_kg_mwh"] / c3_map["ERCO"]["se_net_cems_kg_mwh"],
        c3_map["CISO"]["net_cems_kg_mwh"] / c3_map["CISO"]["se_net_cems_kg_mwh"],
        abs(sp["WLS_ALL49_NO_EM_SOLAR_NG"]["coefs"]["bess_share"]["t_cr1"]),
        c3_map["SOCO"]["net_cems_kg_mwh"] / c3_map["SOCO"]["se_net_cems_kg_mwh"],
        abs(cc["dispatch_elasticity_total"]["coefs"]["total_curt_mw"]["t_day"]),
        abs(pk_all["t_cr1"]),
        abs(sp["WLS_DROP_CE_47_NG"]["coefs"]["bess_share"]["t_cr1"]),
        abs(sp["WLS_ALL49_MAIN_NG"]["coefs"]["bess_share"]["t_cr1"]),
        abs(dy["DAILY_ALL49_NG_MWH"]["coefs"]["sol_x_bess_mwh"]["t_cr1"]),
    ]
    null_tvals = [
        abs(sp["WLS_ALL49_NUCLEAR_PLACEBO"]["coefs"]["bess_share"]["t_cr1"]),
        abs(dy["DAILY_ALL49_NUCLEAR_PLACEBO"]["coefs"]["sol_x_bess_mwh"]["t_cr1"]),
        abs(ll["terms"]["fut_t0_tp6"]["t_cr1"]),
        abs(dur["ALL49_EM_NG"]["horserace_mw"]["t_cr1"]),
        abs(ll["terms"]["fut_tp6_tp12"]["t_cr1"]),
    ]

    return {
        "fig1_diurnal_gas_displacement_and_leads.png": (
            "Figure 1. 24-Hour Demand-Weighted WLS Conditional Natural-Gas Displacement Profile, Distributed 6-Month Lead-Lag Timing, and Robustness Forest (Sample 1: G = 49 U.S. BAs, 2019&ndash;2026).",
            (
                f"Panel A plots local Hour-Ending conditional WLS (<em>d</em><sub>19</sub> demand-weighted, aligned CISO) natural-gas responses relative to the overnight idle baseline "
                f"(HE 2&ndash;5, &plusmn;95% BA-clustered CR1 CIs): gas displacement peaks sharply at Hour Ending 20 "
                f"({pk_all['beta']:+.3f}, <em>t</em> = {pk_all['t_cr1']:+.2f} across all 49 BAs; {pk_dce['beta']:+.3f}, <em>t</em> = {pk_dce['t_cr1']:+.2f} "
                f"dropping CISO and ERCO), mirroring midday charging increases while baseload nuclear remains identically zero. "
                f"Panel B contrasts the calendar-aligned distributed 6-month timing specification (top: installed <code>Stock(t-12)</code> = {ll['terms']['stock_tm12']['beta']:+.3f}, "
                f"recent additions {ll['terms']['add_tm12_tm6']['beta']:+.3f} and {ll['terms']['add_tm6_t0']['beta']:+.3f} vs. spotless unbuilt future leads "
                f"{ll['terms']['fut_t0_tp6']['beta']:+.3f} and {ll['terms']['fut_tp6_tp12']['beta']:+.3f}, Joint Future <em>F</em> = {ll['joint_future_leads_F']['F']:.2f}, "
                f"<em>p</em> = {ll['joint_future_leads_F']['p']:.3f}) against eight controlled WLS robustness checks (bottom: Main All 49 = {sp['WLS_ALL49_MAIN_NG']['coefs']['bess_share']['beta']:+.3f} "
                f"vs. uncontrolled solar-confounded No Controls = {m_noctrl['coefs']['bess_share']['beta']:+.4f}, <em>p</em><sub>Rad</sub> = {_fmt_p_html(m_noctrl['wcb']['p_wcb'])}; "
                f"Collider-Free = {sp['WLS_ALL49_NO_EM_SOLAR_NG']['coefs']['bess_share']['beta']:+.3f}, Drop CISO &amp; ERCO = {sp['WLS_DROP_CE_47_NG']['coefs']['bess_share']['beta']:+.3f}, "
                f"Drop Top-7 BESS = {sp['WLS_DROP_TOP7_42_NG']['coefs']['bess_share']['beta']:+.3f}, BA &times; Post2024H2 FE = {sp['WLS_ALL49_BA_POST24H2_NG']['coefs']['bess_share']['beta']:+.3f}, "
                f"Pre/Post-Schema splits, and BA linear trends; 49-BA LOBAO max <em>p</em><sub>CR1</sub> = {lob['p_cr1_max']:.4f})."
            ),
        ),
        "fig2_telemetry_forensics_and_diurnal_charging.png": (
            "Figure 2. Physical Storage Telemetry Forensics, Official Standalone CAISO Reconciliation, and Exact 4-Window Disjoint Diurnal Charging Mix (14 Metered Grids, 2024-07 to 2026-10).",
            (
                f"Panel A compares raw unaligned EIA-930 Round-Trip Efficiency (crimson) against aligned physical RTE (navy): replacing unphysical EIA-930 CISO "
                f"<code>Other+Geothermal</code> (RTE = {c_rep['eia930_broken_other_geo_rte']:.2f}) and resolving the +{ng_corr['mean_midday_phantom_ng_mw_2024_2025']:,.0f} MW 2024&ndash;2025 EIA-930 vs. CAISO/CEMS midday natural-gas reporting discrepancy "
                f"with official standalone CAISO 5-minute <code>fuelsource.csv</code> recovers true physical RTE = {c_rep['caiso_fuelsource_rte']:.3f}; combining <code>Battery</code> + <code>Unknown Energy Storage</code> reconciles "
                f"ERCO ({ues['ERCO']['raw_broken_rte']:.2f} &rarr; {ues['ERCO']['repaired_rte']:.3f}) and AZPS (zero raw charging &rarr; {ues['AZPS']['repaired_rte']:.3f}); "
                f"filtering FPL&rsquo;s single {fpl_a['raw_bess_mw']:,.0f} MW outlier ({fpl_a['date']} HE {fpl_a['hour']}) yields DC-coupled RTE = {t14['FPL']['rte']:.3f}; "
                f"and the 13 clean AC-coupled grids average RTE = {m14['fleet_13_ac_rte']:.3f} with 0/4 pumped-hydro leakage and lag-0 EPA CEMS sync "
                f"<em>r</em> = {cems_r_min:.3f}&ndash;{cems_r_max:.3f}. "
                f"Panel B decomposes charging energy across four disjoint windows (Overnight 23&ndash;06, Morning 07&ndash;09, Midday Solar 10&ndash;16, Evening 17&ndash;22), "
                f"contrasting fossil-heavy overnight chargers (MISO {t14['MISO']['chg_share_pct']['Overnight']:.0f}%, SOCO {t14['SOCO']['chg_share_pct']['Overnight']:.0f}%, "
                f"DUK {t14['DUK']['chg_share_pct']['Overnight']:.0f}%) against Southwest midday-solar fleets (CISO {t14['CISO']['chg_share_pct']['Midday Solar']:.0f}%, "
                f"AZPS {t14['AZPS']['chg_share_pct']['Midday Solar']:.0f}%, PNM {t14['PNM']['chg_share_pct']['Midday Solar']:.0f}%)."
            ),
        ),
        "fig3_cems_mef_vs_aef_sign_reversal.png": (
            "Figure 3. Fleet-Wide Counterfactual Accounting Discrepancy (Naive AEF vs. CEMS-MEF Marginal Model) and EPA CEMS 24-Hour Generator-Stack MEF Profiles (Sample 2: 2024-07 to 2026-09).",
            (
                f"Panel A compares model-based counterfactual net CO<sub>2</sub> per discharged MWh under Naive AEF accounting (teal, incoming-import weighted) against our CEMS-MEF marginal displacement counterfactual model "
                f"(crimson, &plusmn;95% exact 24&times;24 date-clustered CI, &alpha; = 0) across all 14 metered grids ({fl14['dis_gwh_cems_window']/1000:.2f} TWh / {fl14['dis_gwh_cems_window']:,.1f} GWh discharged), "
                f"with white diamonds overlaying independent 24-hour EPA eGRID 2023 rev2 Peaker MEF counterfactuals (cross-grid <em>r</em> = {cv['r_net_kg_mwh']:.3f}, MAD = {cv['mad_net_kg_mwh']:.1f} kg/MWh). "
                f"EPA CEMS directly measures hourly fossil generator smokestack emissions, whereas battery-induced net CO<sub>2</sub> relative to a no-storage baseline is estimated by our marginal displacement model: "
                f"the AEF counterfactual implies {fl14['aef_kg_mwh']:+.1f} kg CO<sub>2</sub>/MWh ({fl14['aef_total_kt']/1000:+.2f} Mt CO<sub>2</sub>) versus "
                f"{fl14['cems_mef_kg_mwh']:+.1f} kg CO<sub>2</sub>/MWh ({fl14['cems_mef_total_kt']/1000:+.2f} Mt CO<sub>2</sub>) under the CEMS-MEF counterfactual&mdash;a +{fl14['sign_reversal_cems_minus_aef_mt']:.2f} Mt CO<sub>2</sub> counterfactual accounting discrepancy (sign reversal in {r4['proposition_3_aef_mef_bias']['n_grids_sign_reversed']}/14 grids). "
                f"Panel B traces bilateral-trade-adjusted EPA CEMS 24-hour generator-stack MEF curves (&plusmn;95% CI) for four grid archetypes (MISO coal-heavy overnight, "
                f"ERCO solar/wind+gas/coal, AZPS desert solar+coal/gas, and CISO high-solar+imports)."
            ),
        ),
        "fig4_caiso_noncircular_curtailment_tipping.png": (
            f"Figure 4. Non-Circular Empirical CAISO Interior CEMS Collapse (&minus;{dom_drop_pct:.0f}% Domestic, &minus;{sys_drop_pct:.0f}% System) Under Official Curtailment Regimes and Joint Block-Bootstrap Carbon Neutrality (Sample 3: 2024-07 to 2025-12).",
            (
                f"Panel A merges official CAISO hourly curtailments (2024-07 to 2025-12, {cc['window']['n_hours']:,} hours) directly onto standalone CAISO battery telemetry "
                f"and EPA CEMS generator-stack CO<sub>2</sub> across strictly interior regime hours (requiring both <em>t</em> and <em>t</em>&minus;1 in bin; absorbing Year-Month &times; Hour FE, &plusmn;95% date-clustered CI): "
                f"in consecutive interior &gt;2,000 MW curtailment hours, in-state domestic CAISO CEMS MEF collapses by {dom_drop_pct:.0f}% ({bins[0]['mef_cems_dom_kg_mwh']:.0f} &rarr; {bins[3]['mef_cems_dom_kg_mwh']:.0f} kg/MWh), "
                f"import-adjusted system-wide CEMS MEF drops {sys_drop_pct:.0f}% ({bins[0]['mef_cems_sys_kg_mwh']:.0f} &rarr; {bins[3]['mef_cems_sys_kg_mwh']:.0f} kg/MWh), and marginal un-curtailment (&minus;&part;Curt/&part;NL, crimson diamonds) climbs from exact "
                f"{abs(-100*bins[0]['d_curt_per_d_netload']):.1f}% to {abs(-100*bins[3]['d_curt_per_d_netload']):.1f}%. Panel B plots Proposition 2&rsquo;s exact thermodynamic break-even threshold "
                f"&alpha;<sub>b</sub><sup>*</sup> = 1 &minus; &eta;<sub>b</sub> MEF<sub>dis</sub>/MEF<sub>chg</sub> across all 14 grids alongside CAISO&rsquo;s empirical marginal curtailment absorption "
                f"(&alpha;&#770;<sup>emp</sup> = {100*cc['alpha_emp_unspill_share']:.1f}%) and Corollary 2.1 incremental residual headroom (&rho;<sup>res</sup> = {100*cc['rho_residual_headroom_total']:.1f}%, system-only {100*cc['rho_residual_headroom_system']:.1f}% vs. &alpha;<sub>CISO</sub><sup>*</sup> = "
                f"{100*cc['alpha_star_ciso_cems']:.1f}%). Propagating diurnal, cross-BA import, curtailment-regime, and cycling-weight uncertainty jointly via a <em>B</em> = {jb['B']:,} date-clustered block bootstrap places CAISO system-wide net CO<sub>2</sub> at "
                f"{jb_ms['point_estimate']:+.2f} kg/MWh (95% CI [{jb_ms['ci95_lo']:+.2f}, {jb_ms['ci95_hi']:+.2f}]) under the main specification and {jb_ls['point_estimate']:+.2f} kg/MWh (95% CI [{jb_ls['ci95_lo']:+.2f}, {jb_ls['ci95_hi']:+.2f}]) under the pure exogenous &Delta;Load alternative "
                f"(vs. {jb_md['point_estimate']:+.2f} kg/MWh, 95% CI [{jb_md['ci95_lo']:+.2f}, {jb_md['ci95_hi']:+.2f}], domestic-only and {c3_map['CISO']['net_aef_kg_mwh']:+.1f} naive AEF)&mdash;confirming statistical carbon neutrality across both system-wide specifications."
            ),
        ),
        "fig5_hourly_dispatch_and_master_audit.png": (
            "Figure 5. High-Frequency Within-BA-Month Daily Dispatch (BA &times; Year-Month FE), Storage Duration Horse-Race, and Master Forensic Audit Forest.",
            (
                f"Panel A (top) displays high-frequency daily WLS regressions absorbing BA &times; Year-Month FE and Date FE ({dy['DAILY_ALL49_NG_MWH']['n']:,} BA-days): "
                f"interacting daily midday solar swings with installed BESS energy capacity (MWh) confirms strong evening displacement on Natural Gas "
                f"({dy['DAILY_ALL49_NG_MWH']['coefs']['sol_x_bess_mwh']['beta']:+.3f}, <em>t</em> = {dy['DAILY_ALL49_NG_MWH']['coefs']['sol_x_bess_mwh']['t_cr1']:+.2f}; "
                f"+Quad &amp; SolCap: {dy['DAILY_ALL49_NG_MWH_QUAD_SOLCAP']['coefs']['sol_x_bess_mwh']['beta']:+.3f}, <em>t</em> = {dy['DAILY_ALL49_NG_MWH_QUAD_SOLCAP']['coefs']['sol_x_bess_mwh']['t_cr1']:+.2f}), "
                f"Fossil+Imports ({dy['DAILY_ALL49_FOSS_IMP_MWH']['coefs']['sol_x_bess_mwh']['beta']:+.3f}, <em>p</em><sub>WCB</sub> = {_fmt_p_html(dy['DAILY_ALL49_FOSS_IMP_MWH']['wcb']['p_wcb'])}), "
                f"and Drop CISO/ERCO ({dy['DAILY_DROP_CE_47_NG_MWH']['coefs']['sol_x_bess_mwh']['beta']:+.3f}, <em>t</em> = {dy['DAILY_DROP_CE_47_NG_MWH']['coefs']['sol_x_bess_mwh']['t_cr1']:+.2f}), "
                f"against a clean Nuclear placebo ({dy['DAILY_ALL49_NUCLEAR_PLACEBO']['coefs']['sol_x_bess_mwh']['beta']:+.4f}, <em>p</em><sub>WCB</sub> = {_fmt_p_html(dy['DAILY_ALL49_NUCLEAR_PLACEBO']['wcb']['p_wcb'])}). "
                f"Panel A (bottom) confirms Proposition 1 via the joint MWh-vs-MW horse-race (All 49 MWh = {dur['ALL49_EM_NG']['horserace_mwh']['beta']:+.3f}, "
                f"<em>p</em><sub>WCB</sub> = {_fmt_p_html(dur['ALL49_EM_NG']['horserace_mwh']['p_wcb'])}; Drop CE Peak MWh = {dur['DROP_CE_47_PKMD_NG']['horserace_mwh']['beta']:+.3f}, "
                f"<em>p</em><sub>WCB</sub> = {_fmt_p_html(dur['DROP_CE_47_PKMD_NG']['horserace_mwh']['p_wcb'])} vs. conditional MW = {dur['DROP_CE_47_PKMD_NG']['horserace_mw']['beta']:+.3f}, "
                f"<em>p</em><sub>WCB</sub> = {_fmt_p_html(dur['DROP_CE_47_PKMD_NG']['horserace_mw']['p_wcb'])}). "
                f"Panel B summarizes cluster-robust |<em>t</em>|-statistics across all nine verified effects (|<em>t</em>| = {min(eff_tvals):.2f}&ndash;{max(eff_tvals):.1f}) versus all five clean empirical nulls (|<em>t</em>| &le; {max(null_tvals):.2f})."
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
    s = s.replace(r"^{\circ}", "&deg;")
    s = s.replace(r"^\circ", "&deg;")

    while r"\frac{" in s:
        idx = s.index(r"\frac{")
        num, nxt = _extract_braced(s, idx + len(r"\frac"))
        den, end = _extract_braced(s, nxt) if nxt < len(s) and s[nxt] == "{" else ("", nxt)
        n_clean, d_clean = num.strip(), den.strip()
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

    s = s.replace(r"\_", "&#95;")

    replacements = [
        (r"{,}", ","),
        (r"\qquad", "&emsp;&emsp;"),
        (r"\quad", "&emsp;"),
        (r"\iff", "&hArr;"),
        (r"\Rightarrow", "&rArr;"),
        (r"\partial", "&part;"),
        (r"\left(", "("),
        (r"\right)", ")"),
        (r"\left[", "["),
        (r"\right]", "]"),
        (r"\left", ""),
        (r"\right", ""),
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
        (r"\Delta", "&Delta;"),
        (r"\theta", "&theta;"),
        (r"\beta", "&beta;"),
        (r"\alpha", "&alpha;"),
        (r"\phi", "&phi;"),
        (r"\gamma", "&gamma;"),
        (r"\eta", "&eta;"),
        (r"\rho", "&rho;"),
        (r"\tau", "&tau;"),
        (r"\epsilon", "&epsilon;"),
        (r"\varepsilon", "&epsilon;"),
        (r"\%", "%"),
        (r"\{", "{"),
        (r"\}", "}"),
        (r"\|", "|"),
        (r"\dots", "&hellip;"),
        (r"\ldots", "&hellip;"),
        (r"\;", "&ensp;"),
        (r"\,", "&thinsp;"),
        (r"\!", ""),
        (r"\ ", " "),
        ("--", "&ndash;"),
    ]
    for old, new in replacements:
        s = s.replace(old, new)

    for _ in range(4):
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
        parts[i] = re.sub(r"(?<![&a-zA-Z])-(?![a-zA-Z]*;)", "&minus;", parts[i])
        parts[i] = parts[i].replace("2&minus;way", "2-way").replace("Chg&minus;Dis", "Chg-Dis")
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
                raise ValueError(f"Markdown table column mismatch: {headers}")
            col_cls = [
                "center" if (a.startswith(":") and a.endswith(":")) else ("right" if a.endswith(":") else "left")
                for a in aligns
            ]
            th_html = "".join(
                f'<th class="{col_cls[idx]}">{_inline_md(h)}</th>' for idx, h in enumerate(headers)
            )
            rows_html = []
            for rln in tbl_lines[2:]:
                cells = split_md_row(rln)
                tds = "".join(
                    f'<td class="{col_cls[idx]}">{_inline_md(c)}</td>' for idx, c in enumerate(cells)
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
                items.append(f"<li>{_inline_md(item_txt)}</li>")
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
            if para_first.startswith(("**Table ", "**Box "))
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
      margin: 0.62in 0.62in 0.68in 0.62in;
      @top-right {
        content: "Diurnal Gas Displacement and the Carbon-Arbitrage Paradox of U.S. Battery Storage (2019-2026)";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.1pt;
        color: #555;
      }
      @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.8pt;
        color: #555;
      }
    }
    @page :first { @top-right { content: normal; } }
    body {
      font-family: Georgia, "Times New Roman", serif;
      font-size: 9.1pt;
      line-height: 1.41;
      color: #1a1a1a;
      max-width: 100%;
    }
    h1.paper-title {
      font-size: 13.4pt;
      line-height: 1.24;
      margin: 0 0 8pt 0;
      color: #0b2545;
      border-bottom: 1.5pt solid #0b2545;
      padding-bottom: 6pt;
    }
    h2 {
      font-size: 10.8pt;
      color: #0b2545;
      margin: 11pt 0 5pt 0;
      border-bottom: 0.6pt solid #cbd5e1;
      padding-bottom: 2pt;
      page-break-after: avoid;
    }
    h3 {
      font-size: 9.5pt;
      color: #1e3a5f;
      margin: 8.5pt 0 4pt 0;
      page-break-after: avoid;
    }
    p { margin: 0 0 5.2pt 0; text-align: justify; }
    p.table-caption {
      font-size: 8.2pt;
      margin: 7pt 0 3pt 0;
      color: #0b2545;
      text-align: left;
      break-inside: avoid;
      page-break-inside: avoid;
      break-after: avoid;
      page-break-after: avoid;
    }
    p.table-notes {
      font-size: 7.2pt;
      color: #475569;
      margin: 2pt 0 8pt 0;
      text-align: left;
    }
    ul, ol { margin: 3pt 0 6pt 16pt; padding: 0; }
    li { margin: 0 0 2.6pt 0; text-align: justify; }
    ol.refs-list li { text-align: left; font-size: 7.9pt; line-height: 1.31; break-inside: avoid; page-break-inside: avoid; }
    code {
      font-family: Consolas, "Courier New", monospace;
      font-size: 7.1pt;
      background: #f1f5f9;
      padding: 0.4pt 2.0pt;
      border-radius: 2pt;
    }
    hr { border: 0; border-top: 0.6pt solid #cbd5e1; margin: 7.5pt 0; }
    .math { font-family: "Cambria Math", Georgia, serif; font-style: italic; }
    .math .rm, .eq-block .rm { font-style: normal; }
    sup, sub { white-space: nowrap; }
    .eq-block {
      font-family: "Cambria Math", Georgia, serif;
      font-size: 9.2pt;
      text-align: center;
      margin: 6pt 0;
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
      font-size: 6.5pt;
      line-height: 1.19;
      border-top: 1.3pt solid #0f172a;
      border-bottom: 1.3pt solid #0f172a;
    }
    thead tr { border-bottom: 0.8pt solid #334155; background: #f8fafc; }
    th, td { padding: 1.9pt 2.4pt; vertical-align: top; }
    td .math, th .math { white-space: nowrap; }
    td code { white-space: nowrap; font-size: 6.2pt; }
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
      max-height: 3.75in;
      height: auto;
      display: block;
      margin: 0 auto 4.5pt auto;
    }
    figure.pub-fig figcaption {
      font-size: 7.3pt;
      line-height: 1.28;
      color: #334155;
      text-align: left;
    }
    """
    return (
        "<!DOCTYPE html><html lang='en'><head><meta charset='utf-8' />"
        "<title>Real-World Diurnal Gas-Peaker Displacement and the Carbon-Arbitrage Paradox of U.S. Utility-Scale Battery Storage (2019-2026)</title>"
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
        r"\\frac\{",
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
