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
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from econ_utils import FIG_DIR, RES_DIR, WS_DIR
from pypdf import PdfReader

MD_PATH = WS_DIR / "manuscript_k1_boost.md"
HTML_PATH = WS_DIR / "manuscript_k1_boost.html"
PDF_PATH = WS_DIR / "manuscript_k1_boost.pdf"
PDF_NE_PATH = WS_DIR / "manuscript_k1_nature_energy.pdf"
SI_MD_PATH = WS_DIR / "supplementary_k1_nature_energy.md"
SI_HTML_PATH = WS_DIR / "supplementary_k1_nature_energy.html"
SI_PDF_PATH = WS_DIR / "supplementary_k1_nature_energy.pdf"
EDGE_EXE = Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe")


def _fmt_p_html(p: float | None) -> str:
    if p is None or not math.isfinite(p):
        return "n/a"
    if p < 1e-4:
        return "&lt;0.0001"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def build_dynamic_figure_blocks() -> tuple[dict[str, tuple[str, str]], dict[str, tuple[str, str]]]:
    """Build 4 Main Nature Energy figure legends + 3 Supplementary figure legends 100% dynamically."""
    r1 = json.loads((RES_DIR / "01_telemetry_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_panel_a_wls_results.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_cems_carbon_curtailment_results.json").read_text(encoding="utf-8"))
    r3b = json.loads((RES_DIR / "03b_nature_energy_v4_extensions.json").read_text(encoding="utf-8"))
    r3c = json.loads((RES_DIR / "03c_k1_v5_unconditional_audit.json").read_text(encoding="utf-8"))
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
    jb1 = jb["block_length_sensitivity"]["1d"]
    jb7 = jb["block_length_sensitivity"]["7d"]
    jb14 = jb["block_length_sensitivity"]["14d"]
    jb_ms = jb14["net_sys_main"]
    jb_ls = jb14["net_sys_pure_load"]
    jb_md = jb14["net_dom_main"]
    m_noctrl = sp["WLS_ALL49_NO_CONTROLS_NG"]
    cems_r_min = min(cems_al[b]["r_at_lag0"] for b in ["CISO", "ERCO", "MISO", "SOCO", "DUK"])
    cems_r_max = max(cems_al[b]["r_at_lag0"] for b in ["CISO", "ERCO", "MISO", "SOCO", "DUK"])

    db = r3b["independent_mef_validations"]["direct_cems_on_dbess_regressions"]
    strat = r3b["cross_regional_ren_penetration_stratification"]
    ub = r3c["unconditional_season_stratified_utc_bootstrap_1000"]
    uf14 = ub["full_window_202407_202609"]["14d"]
    uf28 = ub["full_window_202407_202609"]["28d"]
    us14 = ub["same_window_202407_202512"]["14d"]
    lce = r3c["lobao_and_concentration_audit"]["leave_ciso_and_erco_uncond_14d"]
    oos_th = r3c["out_of_sample_validation"]["temporal_holdout_202407_202509_to_202510_202609"]
    oos_lqo = r3c["out_of_sample_validation"]["leave_quarter_out_cv_9q"]
    ll_diag = r3c["lead_lag_timing_diagnostic_m3_p3"]
    roots = {round(r["tau_local_access"], 2): r for r in r3c["caiso_upper_bound_frontier_roots"]["roots"]}
    ciso_gw = float(r3c["caiso_upper_bound_frontier_roots"]["ciso_2026_nameplate_gw"])
    cs_e = r3c["ercot_and_ciso_matched_stress_test"]["ERCO"]["common_support_exact_matched_seas_hr_lq"]
    cs_c = r3c["ercot_and_ciso_matched_stress_test"]["CISO"]["common_support_exact_matched_seas_hr_lq"]
    erco_ld_gt60 = r3c["ercot_and_ciso_matched_stress_test"]["ERCO"]["fine_cell_fe_stratification"]["seas_hr_ld"][3]

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

    main_figs = {
        "fig3_cems_mef_vs_aef_sign_reversal.png": (
            "Figure 1. Fleet-wide counterfactual carbon accounting discrepancy across 14 U.S. balancing authorities (2024-07 to 2026-09).",
            (
                f"<b>a</b>, Counterfactual net CO<sub>2</sub> per discharged MWh under Naive AEF accounting (teal, incoming-import weighted) versus our CEMS-MEF marginal displacement model "
                f"(crimson, &plusmn;95% exact 24&times;24 date-clustered CI, &alpha; = 0) across all 14 metered grids ({fl14['dis_gwh_cems_window']/1000:.2f} TWh discharged), "
                f"with white diamonds showing independent 24-hour EPA eGRID 2023 rev2 peaker MEF counterfactuals (<em>r</em> = {cv['r_net_kg_mwh']:.3f}, MAD = {cv['mad_net_kg_mwh']:.1f} kg/MWh). "
                f"On identical metered dispatch, AEF implies {fl14['aef_kg_mwh']:+.1f} kg/MWh ({fl14['aef_total_kt']/1000:+.2f} Mt CO<sub>2</sub>) versus "
                f"{fl14['cems_mef_kg_mwh']:+.1f} kg/MWh ({fl14['cems_mef_total_kt']/1000:+.2f} Mt CO<sub>2</sub>) under CEMS-MEF&mdash;a +{fl14['sign_reversal_cems_minus_aef_mt']:.2f} Mt CO<sub>2</sub> counterfactual accounting discrepancy reversing sign in {r4['proposition_3_aef_mef_bias']['n_grids_sign_reversed']}/14 grids. "
                f"<b>b</b>, Bilateral-trade-adjusted 24-hour EPA CEMS marginal emission profiles (&plusmn;95% CI) for four grid archetypes (MISO, ERCO, AZPS, CISO)."
            ),
        ),
        "fig_ne4_joint_bootstrap_and_validation.png": (
            "Figure 2. Unconditional season-stratified UTC-day block-bootstrap sensitivity and out-of-sample validation / measurement cross-checks.",
            (
                f"<b>a</b>, Unconditional season-stratified (DJF/MAM/JJA/SON) joint UTC-day moving-block bootstrap estimates (<em>B</em> = 1,000; simultaneously re-estimating AEF, 24-hour CEMS MEFs, unfixed discharge volumes, same-window bilateral trade weights, and CAISO curtailment) showing fleet CEMS-MEF net CO<sub>2</sub> (navy, 14d CI) and AEF discrepancy (crimson, 14d solid &amp; 28d shaded outer CI for full 49.77 TWh; teal dashed, 14d CI for exact 18-month same-window 26.03 TWh) across uniform &alpha; = 0%&ndash;20%, hybrid CAISO scenarios, and Leave-CISO-&amp;-ERCO-Out (12 grids, +{lce['full_u0_disc_mt']['point']:.2f} [{lce['full_u0_disc_mt']['ci95_lo']:+.2f}, {lce['full_u0_disc_mt']['ci95_hi']:+.2f}] Mt). "
                f"At 15% non-California absorption, fleet net CO<sub>2</sub> spans zero ({uf14['h15_main_mt']['point']:+.2f} [{uf14['h15_main_mt']['ci95_lo']:+.2f}, {uf14['h15_main_mt']['ci95_hi']:+.2f}] Mt), while the discrepancy remains strictly positive (+{uf14['h15_main_disc_mt']['point']:.2f} Mt full, 28d [{uf28['h15_main_disc_mt']['ci95_lo']:+.2f}, {uf28['h15_main_disc_mt']['ci95_hi']:+.2f}]; +{us14['h15_main_disc_mt']['point']:.2f} Mt same-window). "
                f"<b>b</b>, Out-of-sample temporal holdout validation (24H2&ndash;25Q3 predicting 25Q4&ndash;26Q3: pooled <em>R</em><sup>2</sup> = {oos_th['fleet_pooled_r2_oos']:.3f}, cal. slope = {oos_th['fleet_dis_weighted_cal_slope']:.2f}, 9Q leave-quarter-out mean <em>R</em><sup>2</sup> = {oos_lqo['mean_major4_r2_oos']:.3f} with {oos_lqo['n_quarters_sign_preserved']}/9 sign preservation) alongside measurement cross-checks comparing main 24-hour CEMS MEFs (navy), direct metered &minus;&part;CO<sub>2</sub>/&part;BESS (teal, &plusmn;95% CI: CISO {-db['CISO']['d_bess_beta_kg_mwh']:.0f}, AZPS {-db['AZPS']['d_bess_beta_kg_mwh']:.0f}, ERCO {-db['ERCO']['d_bess_beta_kg_mwh']:.0f}, MISO {-db['MISO']['d_bess_beta_kg_mwh']:.0f} kg/MWh; contemporaneous <em>k</em> = 0 shares {100*ll_diag['CISO']['co2_contemp_share_of_abs_sum']:.0f}%/{100*ll_diag['AZPS']['co2_contemp_share_of_abs_sum']:.0f}%/{100*ll_diag['ERCO']['co2_contemp_share_of_abs_sum']:.0f}%/{100*ll_diag['MISO']['co2_contemp_share_of_abs_sum']:.0f}%), direct &part;CO<sub>2</sub>/&part;Load (sky), and pure CEMS internal stack slopes (amber)."
            ),
        ),
        "fig4_caiso_noncircular_curtailment_tipping.png": (
            f"Figure 3. California interior curtailment CEMS MEF collapse (&minus;{dom_drop_pct:.0f}% domestic, &minus;{sys_drop_pct:.0f}% system) and multi-day block-bootstrap uncertainty.",
            (
                f"<b>a</b>, Official CAISO hourly curtailments (2024-07 to 2025-12, {cc['window']['n_hours']:,} hours) linked to standalone CAISO battery telemetry and EPA CEMS CO<sub>2</sub> across consecutive interior regime hours (both <em>t</em> and <em>t</em>&minus;1 in bin; YM &times; Hour FE, &plusmn;95% date-clustered CI). "
                f"Above 2,000 MW curtailment, in-state domestic MEF falls {dom_drop_pct:.0f}% ({bins[0]['mef_cems_dom_kg_mwh']:.0f} &rarr; {bins[3]['mef_cems_dom_kg_mwh']:.0f} kg/MWh), system-wide import-adjusted MEF falls {sys_drop_pct:.0f}% ({bins[0]['mef_cems_sys_kg_mwh']:.0f} &rarr; {bins[3]['mef_cems_sys_kg_mwh']:.0f} kg/MWh), and marginal un-curtailment climbs from 0.0% to {abs(-100*bins[3]['d_curt_per_d_netload']):.1f}%. "
                f"<b>b</b>, Break-even thresholds &alpha;<sub>b</sub><sup>*</sup> across all 14 grids alongside CAISO&rsquo;s empirical absorption ({100*cc['alpha_emp_unspill_share']:.1f}%) and incremental residual headroom ({100*cc['rho_residual_headroom_total']:.1f}%; system-only {100*cc['rho_residual_headroom_system']:.1f}%). "
                f"Joint 14-day block bootstraps (<em>B</em> = 1,000) yield {jb_ms['point_estimate']:+.2f} kg/MWh (14d 95% CI [{jb_ms['ci95_lo']:+.2f}, {jb_ms['ci95_hi']:+.2f}]; 7d [{jb7['net_sys_main']['ci95_lo']:+.2f}, {jb7['net_sys_main']['ci95_hi']:+.2f}]; 1d [{jb1['net_sys_main']['ci95_lo']:+.2f}, {jb1['net_sys_main']['ci95_hi']:+.2f}]; season-stratified unconditional 14d/28d [{uf14['ciso_emp_main']['ci95_lo']:+.2f}, {uf14['ciso_emp_main']['ci95_hi']:+.2f}] / [{uf28['ciso_emp_main']['ci95_lo']:+.2f}, {uf28['ciso_emp_main']['ci95_hi']:+.2f}]) under the main specification and {jb_ls['point_estimate']:+.2f} kg/MWh ([{jb_ls['ci95_lo']:+.2f}, {jb_ls['ci95_hi']:+.2f}]) under observed &Delta;Load (domestic-only: {jb_md['point_estimate']:+.2f} [{jb_md['ci95_lo']:+.2f}, {jb_md['ci95_hi']:+.2f}]), leaving import-adjusted net direction undetermined."
            ),
        ),
        "fig_ne3_congestion_frontier_and_ercot.png": (
            "Figure 4. Fixed-profile BA-level upper-bound accounting scenarios (CAISO) and cross-regime renewable-penetration stress test.",
            (
                f"<b>a</b>, Fixed-profile BA-level upper-bound accounting scenarios (non-nodal; omitting nodal LMPs, SOC re-optimization, and binding constraint shadow prices) sweeping incremental storage scale &kappa; (0.1&times;&ndash;3.0&times;, or {0.1*ciso_gw:.1f}&ndash;{3.0*ciso_gw:.1f} GW atop CAISO&rsquo;s {ciso_gw:.1f} GW fleet) against CAISO&rsquo;s observed 13,170-hour residual curtailment curve across four local-congestion access shares &tau;<sub>local</sub> (0% never abates; 25% upper bound &le;{roots[0.25]['gw_breakeven_upper_bound']:.1f} GW; 50% &le;{roots[0.50]['gw_breakeven_upper_bound']:.1f} GW; 100% frictionless ceiling &le;{roots[1.00]['gw_breakeven_upper_bound']:.1f} GW). "
                f"<b>b</b>, Cross-regime renewable-penetration stress test (domestic EPA CEMS net-load MEFs, YM &times; Hour FE bars &plusmn;95% CI; yellow diamonds overlay matched Season &times; Hour &times; Load-Decile FE) across hourly (Solar + Wind)/Load bins (public interval-level ERCOT curtailment is absent from EIA-930). "
                f"Unlike zero-coal CAISO (falling to {strat['CISO'][3]['mef_dom_netload_kg_mwh']:.0f} kg/MWh above 60% renewables), ERCOT&rsquo;s MEF remains {strat['ERCO'][1]['mef_dom_netload_kg_mwh']:.0f}&ndash;{strat['ERCO'][3]['mef_dom_netload_kg_mwh']:.0f} kg/MWh (Load-Decile FE: {erco_ld_gt60['total_mef']:.0f}, coal {erco_ld_gt60['coal_mef']:.0f}; exact-matched Season &times; Hour &times; Load-Quartile difference across {cs_e['n_common_cells_total']} common-support cells: {cs_e['diff_gt60_minus_lt40_total_mef']:+.1f} &plusmn; {cs_e['diff_gt60_minus_lt40_total_se']:.1f} kg/MWh total, {cs_e['diff_gt60_minus_lt40_coal_mef']:+.1f} &plusmn; {cs_e['diff_gt60_minus_lt40_coal_se']:.1f} coal vs. CAISO {cs_c['diff_gt60_minus_lt40_total_mef']:+.1f} &plusmn; {cs_c['diff_gt60_minus_lt40_total_se']:.1f})."
            ),
        ),
    }

    si_figs = {
        "fig2_telemetry_forensics_and_diurnal_charging.png": (
            "Supplementary Figure 1. Storage telemetry reconciliation and exact 4-window diurnal charging mix across 14 metered U.S. grids (2024-07 to 2026-10).",
            (
                f"<b>a</b>, Raw unaligned EIA-930 RTE (crimson) versus reconciled physical RTE (navy): splicing standalone CAISO <code>fuelsource.csv</code> resolves CAISO&rsquo;s RTE ({c_rep['eia930_broken_other_geo_rte']:.2f} &rarr; {c_rep['caiso_fuelsource_rte']:.3f}) and the +{ng_corr['mean_midday_phantom_ng_mw_2024_2025']:,.0f} MW 2024&ndash;2025 midday natural-gas discrepancy; summing <code>Battery</code> + <code>Unknown Energy Storage</code> reconciles ERCO ({ues['ERCO']['raw_broken_rte']:.2f} &rarr; {ues['ERCO']['repaired_rte']:.3f}) and AZPS (&infin; &rarr; {ues['AZPS']['repaired_rte']:.3f}); filtering FPL&rsquo;s {fpl_a['raw_bess_mw']:,.0f} MW outlier yields DC-coupled RTE = {t14['FPL']['rte']:.3f}; 13 clean AC grids average RTE = {m14['fleet_13_ac_rte']:.3f} with 0/4 pumped-hydro leakage and lag-0 CEMS sync <em>r</em> = {cems_r_min:.3f}&ndash;{cems_r_max:.3f}. "
                f"<b>b</b>, Disjoint 4-window charging mix contrasting overnight fossil-heavy chargers (MISO {t14['MISO']['chg_share_pct']['Overnight']:.0f}%, SOCO {t14['SOCO']['chg_share_pct']['Overnight']:.0f}%, DUK {t14['DUK']['chg_share_pct']['Overnight']:.0f}%) against Southwest midday-solar fleets (CISO {t14['CISO']['chg_share_pct']['Midday Solar']:.0f}%, AZPS {t14['AZPS']['chg_share_pct']['Midday Solar']:.0f}%, PNM {t14['PNM']['chg_share_pct']['Midday Solar']:.0f}%)."
            ),
        ),
        "fig1_diurnal_gas_displacement_and_leads.png": (
            "Supplementary Figure 2. Supporting 49-BA conditional diurnal natural-gas displacement profile, 6-month timing tests, and robustness forest (Sample 1, 2019–2026).",
            (
                f"<b>a</b>, Local Hour-Ending conditional WLS natural-gas responses relative to overnight baseline (HE 2&ndash;5, &plusmn;95% CR1 CI) peaking at Hour Ending 20 ({pk_all['beta']:+.3f}, <em>t</em> = {pk_all['t_cr1']:+.2f}; Drop CISO/ERCO {pk_dce['beta']:+.3f}) alongside null Nuclear placebo. "
                f"<b>b</b>, Calendar-aligned distributed 6-month timing tests (Joint Future <em>F</em> = {ll['joint_future_leads_F']['F']:.2f}, <em>p</em> = {ll['joint_future_leads_F']['p']:.3f}) and controlled WLS robustness checks (Main {sp['WLS_ALL49_MAIN_NG']['coefs']['bess_share']['beta']:+.3f} vs. uncontrolled No Controls {m_noctrl['coefs']['bess_share']['beta']:+.4f}, <em>p</em><sub>Rad</sub> = {_fmt_p_html(m_noctrl['wcb']['p_wcb'])}; 49-BA LOBAO max <em>p</em><sub>CR1</sub> = {lob['p_cr1_max']:.4f})."
            ),
        ),
        "fig5_hourly_dispatch_and_master_audit.png": (
            "Supplementary Figure 3. High-frequency within-BA-month daily dispatch, storage duration horse-race, and summary of empirical estimates.",
            (
                f"<b>a</b>, Daily WLS regressions absorbing BA &times; Year-Month FE and Date FE ({dy['DAILY_ALL49_NG_MWH']['n']:,} BA-days; top) and Proposition 1 energy (MWh) versus power (MW) duration horse-race (bottom). "
                f"<b>b</b>, Cluster-robust |<em>t</em>|-statistics across nine empirical estimates (|<em>t</em>| = {min(eff_tvals):.2f}&ndash;{max(eff_tvals):.1f}) versus five placebo and lead tests (|<em>t</em>| &le; {max(null_tvals):.2f})."
            ),
        ),
    }
    return main_figs, si_figs


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
        (r"\kappa", "&kappa;"),
        (r"\tau", "&tau;"),
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


def convert_md_to_html(
    md_text: str,
    figure_blocks: dict[str, tuple[str, str]],
    running_header: str = "Counterfactual Carbon Accounting of U.S. Utility-Scale Battery Storage (2019-2026)",
) -> str:
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
        if stripped.startswith("<!--") and stripped.endswith("-->"):
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
            if para_first.startswith(("**Table ", "**Box ", "**Supplementary Table ", "**Supplementary Box "))
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

    css = f"""
    @page {{
      size: letter;
      margin: 0.62in 0.62in 0.68in 0.62in;
      @top-right {{
        content: "{running_header}";
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.1pt;
        color: #555;
      }}
      @bottom-center {{
        content: "Page " counter(page) " of " counter(pages);
        font-family: Georgia, "Times New Roman", serif;
        font-size: 7.8pt;
        color: #555;
      }}
    }}
    @page :first {{ @top-right {{ content: normal; }} }}""" + """
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
        "<title>Counterfactual Carbon Accounting and Diurnal Gas-Peaker Displacement of U.S. Utility-Scale Battery Storage (2019-2026)</title>"
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


def _compile_single_pdf(
    md_path: Path,
    html_path: Path,
    pdf_path: Path,
    fig_blocks: dict[str, tuple[str, str]],
    running_header: str = "Counterfactual Carbon Accounting of U.S. Utility-Scale Battery Storage (2019-2026)",
) -> tuple[int, str]:
    md_text = md_path.read_text(encoding="utf-8")
    html_doc = convert_md_to_html(md_text, fig_blocks, running_header=running_header)
    html_path.write_bytes(html_doc.encode("utf-8"))

    pdf_path.unlink(missing_ok=True)
    edge_profile_dir = Path(tempfile.mkdtemp(prefix="k1_edge_pdf_"))
    cmd = [
        str(EDGE_EXE),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        f"--user-data-dir={edge_profile_dir}",
        "--no-pdf-header-footer",
        f"--print-to-pdf={pdf_path}",
        html_path.as_uri(),
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=90, check=False)
    finally:
        shutil.rmtree(edge_profile_dir, ignore_errors=True)
    if res.returncode != 0 or not pdf_path.exists() or pdf_path.stat().st_size < 50_000:
        raise RuntimeError(f"Edge PDF compile failed for {pdf_path.name} rc={res.returncode}: {res.stderr}")

    n_pages, leaks = verify_pdf_zero_leaks(pdf_path)
    html_path.unlink(missing_ok=True)
    if leaks:
        raise RuntimeError(f"Leaked tokens found in {pdf_path.name}: {leaks}")
    sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    return n_pages, sha


def main() -> int:
    if not EDGE_EXE.exists():
        print(f"[ERROR] Microsoft Edge not found at {EDGE_EXE}", file=sys.stderr)
        return 1

    main_figs, si_figs = build_dynamic_figure_blocks()
    n_main, sha_main = _compile_single_pdf(MD_PATH, HTML_PATH, PDF_NE_PATH, main_figs)
    synced_main = False
    try:
        shutil.copy2(PDF_NE_PATH, PDF_PATH)
        synced_main = True
    except PermissionError:
        print(
            f"[WARN] {PDF_PATH.name} is open/locked; fresh Nature Energy PDF saved to {PDF_NE_PATH.name}.",
            flush=True,
        )
    print(
        f"[DONE STEP 08 MAIN] {PDF_NE_PATH.name} ({PDF_NE_PATH.stat().st_size:,} bytes, "
        f"{n_main} pages, 0 leaked tokens, synced_main={synced_main}, SHA-256: {sha_main})",
        flush=True,
    )

    if SI_MD_PATH.exists():
        n_si, sha_si = _compile_single_pdf(
            SI_MD_PATH,
            SI_HTML_PATH,
            SI_PDF_PATH,
            si_figs,
            running_header="Supplementary Information — Counterfactual Carbon Accounting of U.S. Battery Storage",
        )
        print(
            f"[DONE STEP 08 SI]   {SI_PDF_PATH.name} ({SI_PDF_PATH.stat().st_size:,} bytes, "
            f"{n_si} pages, 0 leaked tokens, SHA-256: {sha_si})",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
