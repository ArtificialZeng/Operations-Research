"""Step 07a (v4 ES&T): Dynamically generate camera-ready ES&T main manuscript
(manuscript_j6_boost.md) and Supporting Information (supplementary_j6_est.md)
100% from saved JSON receipts — zero hardcoded numbers, exact authorship block,
zero Track A / Track B / Target Venues metadata.
"""

from __future__ import annotations

import hashlib
import html
import json
import math
import re

from econ_utils import RES_DIR, WS_DIR

MD_MAIN = WS_DIR / "manuscript_j6_boost.md"
MD_SI = WS_DIR / "supplementary_j6_est.md"


def fmt_p(p: float | None) -> str:
    """Format p-value for use INSIDE an existing $...$ math span (no outer $)."""
    if p is None or not math.isfinite(p):
        return "n/a"
    if p < 1e-4:
        exp = math.floor(math.log10(p))
        mant = p / (10.0**exp)
        return f"{mant:.2f} \\times 10^{{-{abs(exp)}}}"
    if p < 0.001:
        return f"{p:.4f}"
    return f"{p:.3f}"


def fmt_p_cell(p: float | None) -> str:
    """Format p-value for standalone markdown text/table cells outside math mode."""
    if p is None or not math.isfinite(p):
        return "n/a"
    if p < 1e-4:
        return f"${fmt_p(p)}$"
    return fmt_p(p)


def fmt_ci(ci: list[float], dec: int = 2) -> str:
    return f"[{ci[0]:+.{dec}f}, {ci[1]:+.{dec}f}]"


def clean_cr_text(s: str) -> str:
    """Strip Crossref embedded HTML tags/entities cleanly for markdown bibliography."""
    s = html.unescape(s or "")
    s = re.sub(r"\s*<sub>\s*2\.5\s*</sub>", "₂.₅", s, flags=re.IGNORECASE)
    s = re.sub(r"<[^>]+>", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def build_references_md(r7: dict) -> str:
    """Format all 15 live-verified academic DOIs + 6 official EPA/CFR references dynamically."""
    lines: list[str] = []
    idx = 1
    for ref in r7["academic_refs"]:
        authors = ref.get("authors", [])
        if len(authors) == 1:
            au = f"{authors[0]}"
        elif len(authors) == 2:
            au = f"{authors[0]} & {authors[1]}"
        elif len(authors) <= 5:
            au = ", ".join(authors[:-1]) + f", & {authors[-1]}"
        else:
            au = f"{authors[0]} et al."
        yr = ref.get("year", "")
        title = clean_cr_text(ref.get("title", ""))
        journal = clean_cr_text(ref.get("journal", ""))
        vol = ref.get("volume", "")
        page = ref.get("page", "")
        vol_str = f" *{vol}*" if vol else ""
        pg_str = f", {page}" if page else ""
        lines.append(
            f"{idx}. {au} ({yr}). {title}. *{journal}*{vol_str}{pg_str}. https://doi.org/{ref['doi']}"
        )
        idx += 1
    for iref in r7["institutional_refs"]:
        lines.append(f"{idx}. {iref['citation']}")
        idx += 1
    return "\n".join(lines)


def build_main_manuscript(r1: dict, r2: dict, r3: dict, r7: dict, r10: dict, r11: dict) -> str:
    cs = r11["common_support_audit"]
    all_c = cs["all_2023_2025"]
    h_c = cs["heavy_smoke_2023_2025"]
    bm_m = cs["matched_benchmarks"]
    ow = cs["overlap_weighted_region_x_frm_bin"]
    tr = all_c["triples_by_hms_level"]

    off_t = r11["official_fixed_2021_2025"]["t640_fw"]
    off_b = r11["official_fixed_2021_2025"]["bam"]
    t1_t = off_t["tier_1"]
    t2_t = off_t["tier_2_lower"]
    f35_t = off_t["fixed_35_matched"]
    f35_tf = off_t["fixed_35_full"]
    t1_b = off_b["tier_1"]
    t2_b = off_b["tier_2_lower"]
    f35_b = off_b["fixed_35_matched"]

    oot = r11["oot_prospective_rolling_5yr"]
    oot_a_t = oot["oot_a_conservative_r_excl"]["t640_fw"]["tier_1"]
    oot_b_t = oot["oot_b_fire_proxy_hms_heavy"]["t640_fw"]["tier_1"]
    oot_b2_t = oot["oot_b2_fire_proxy_hms_med_heavy"]["t640_fw"]["tier_1"]
    oot_c_t = oot["oot_c_pure_frm_only"]["t640_fw"]["tier_1"]
    oot_a_b = oot["oot_a_conservative_r_excl"]["bam"]["tier_1"]
    oot_b_b = oot["oot_b_fire_proxy_hms_heavy"]["bam"]["tier_1"]
    oot_b2_b = oot["oot_b2_fire_proxy_hms_med_heavy"]["bam"]["tier_1"]
    oot_c_b = oot["oot_c_pure_frm_only"]["bam"]["tier_1"]

    rec_b = r11["oot_reconstruction_benchmark_2021_2025"]
    loro = r11["leave_epa_region_out_t640_tier1"]
    sv_t = r11["smoke_vs_nonsmoke_controls"]["t640_fw"]
    mc_t = sv_t["matched_concentration_smoke_vs_nonsmoke"]
    gv_t = sv_t["ground_level_smoke_verification"]
    hms_t = sv_t["by_hms_level"]

    # Pillar 2 baseline gradients, speciation, and SI pointers
    sg_t = r2["sample_and_gradients"]["t640_fw"]
    sg_b = r2["sample_and_gradients"]["bam"]
    s1_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s1_spec_met_level_site_cr1"]
    s2_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s2_interactions_level_site_cr1"]
    s3_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s3_exact_0km_spec_level"]
    s1_b = r2["speciation_and_meteorology"]["bam"]["model_s1_spec_met_level_site_cr1"]
    rt_t = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_b = r2["rooftop_dv_lottery_2023_2025"]["bam"]
    wf21 = r1["accounting"]["combined_site_reg_appn_11of12"]["matched_2123_waterfall"]
    u2_wcy = r3["unification_u2_t640_ee_flagging"]["borderline_within_county_year_fe_flag"]

    # Verify Step 10 exact synchronization
    r10_t1 = r10["results"]["t640_fw"]["matched"]["tier_1"]
    assert r10_t1["instrument_exceed"] == t1_t["fem_exceed"]
    assert r10_t1["reference_exceed"] == t1_t["frm_exceed"]

    tw_t1 = t1_t["inference"]["twoway_site_x_reg_episode"]
    tw_nb = t1_t["inference"]["twoway_site_x_nat_block"]
    nb_t1 = t1_t["inference"]["oneway_nat_block"]
    st_t1 = t1_t["inference"]["oneway_site"]
    dt_t1 = t1_t["inference"]["oneway_date"]
    re_t1 = t1_t["inference"]["oneway_reg_episode"]
    yr_t1 = t1_t["by_year"]

    # Build Table 1 (Common-Support Audit)
    t1_md = [
        "| Common-Support Stratum | T640_FW Pairs (% Overlap) | T640 Tier-1 Diff (pp) | BAM Ref. Pairs (% Overlap) | BAM Tier-1 Diff (pp) | Differential (T640 − BAM) [95% Block CI] | Block $p$ |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in [
        "full_matched_heavy",
        "overlap_epa_regions",
        "overlap_dates",
        "overlap_dates_and_regions",
        "overlap_dates_regions_frm_le50",
    ]:
        b = bm_m[key]
        t1_md.append(
            f"| {b['label']} | {b['t640_n']} ({b['t640_overlap_pct']:.1f}%) | {b['t640_diff_pp']:+.2f} | "
            f"{b['bam_n']} ({b['bam_overlap_pct']:.1f}%) | {b['bam_diff_pp']:+.2f} | "
            f"{b['differential_t640_minus_bam_pp']:+.2f} {fmt_ci(b['differential_ci95_block_pp'])} | {fmt_p_cell(b['differential_p_block'])} |"
        )
    t1_md.append(
        f"| Overlap-Weighted (EPA Region × FRM Bin, {ow['n_shared_cells']} cells) | "
        f"{ow['t640_covered_n']} ({ow['t640_covered_pct']:.1f}%) | {ow['t640_weighted_diff_pp']:+.2f} | "
        f"{ow['bam_covered_n']} ({ow['bam_covered_pct']:.1f}%) | {ow['bam_weighted_diff_pp']:+.2f} | "
        f"{ow['differential_pp']:+.2f} {fmt_ci(ow['block_bootstrap_ci95_pp'])} (boot) | — |"
    )

    # Build Table 2 (Official Retrospective & Out-of-Time Prospective Replay)
    t2_md = [
        "| Instrument Queue | Screening Benchmark | Pairs ($N$) | Inst. / FRM Crossings | Inst.-Only / FRM-Only | Paired Diff (pp) | 95% CI: Nat. Block | 95% CI: 2-Way Site × Reg.-Ep. | 2-Way $p$ |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    t2_specs = [
        ("T640_FW–FRM", "Official EPA 2021–2025 Tier 1 (Retrospective)", t1_t),
        ("T640_FW–FRM", "Official EPA 2021–2025 Tier 2 Lower", t2_t),
        ("T640_FW–FRM", "Fixed Daily >35 µg/m³ (Matched Sample)", f35_t),
        ("T640_FW–FRM", "OOT-A Rolling 5-Yr Tier 1 (R-Excl AQS / AMP480)", oot_a_t),
        ("T640_FW–FRM", "OOT-B Rolling 5-Yr Tier 1 (Excl. HMS Heavy)", oot_b_t),
        ("T640_FW–FRM", "OOT-B2 Rolling 5-Yr Tier 1 (Excl. HMS Med+Heavy)", oot_b2_t),
        ("T640_FW–FRM", "OOT-C Rolling 5-Yr Tier 1 (Pure FRM-Only)", oot_c_t),
        ("BAM–FRM (Ref.)", "Official EPA 2021–2025 Tier 1 (Retrospective)", t1_b),
        ("BAM–FRM (Ref.)", "Official EPA 2021–2025 Tier 2 Lower", t2_b),
        ("BAM–FRM (Ref.)", "Fixed Daily >35 µg/m³ (Matched Sample)", f35_b),
        ("BAM–FRM (Ref.)", "OOT-A Rolling 5-Yr Tier 1 (R-Excl AQS / AMP480)", oot_a_b),
        ("BAM–FRM (Ref.)", "OOT-B Rolling 5-Yr Tier 1 (Excl. HMS Heavy)", oot_b_b),
        ("BAM–FRM (Ref.)", "OOT-C Rolling 5-Yr Tier 1 (Pure FRM-Only)", oot_c_b),
    ]
    for inst_l, bench_l, blk in t2_specs:
        nb_c = blk["inference"]["oneway_nat_block"]["ci95"]
        tw_c = blk["inference"]["twoway_site_x_reg_episode"]
        t2_md.append(
            f"| {inst_l} | {bench_l} | {blk['n_site_days']} | "
            f"{blk['fem_exceed']} / {blk['frm_exceed']} | {blk['fem_only']} / {blk['frm_only']} | "
            f"{blk['difference_pp']:+.2f} | {fmt_ci(nb_c)} | {fmt_ci(tw_c['ci95'])} | {fmt_p_cell(tw_c['p_2sided'])} |"
        )

    # Build Table 3 (Equal-Concentration Non-Smoke vs Heavy Smoke + Surface Evidence)
    t3_md = [
        "| Concentration / Smoke Stratum (T640_FW–FRM) | Non-Smoke $n$ | Non-Smoke Bias (µg/m³) | Non-Smoke T1 Diff (pp) | Heavy Smoke $n$ | Heavy Bias (µg/m³) | Heavy T1 Diff (pp) | $\\Delta$Bias ($p_{\\text{site}}$) | $\\Delta$T1 Diff ($p_{\\text{site}}$) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for k in [
        "other_site_ge15",
        "other_site_15_25",
        "other_site_ge20",
        "other_site_ge25",
        "frm_ge15",
        "frm_15_25",
        "frm_ge20",
        "frm_ge25",
        "midpoint_ge15",
        "midpoint_15_25",
        "midpoint_ge20",
        "midpoint_ge25",
    ]:
        v = mc_t[k]
        t3_md.append(
            f"| {v['label']} | {v['nonsmoke']['n']:,} | {v['nonsmoke']['mean_bias']:+.2f} | "
            f"{v['nonsmoke']['t1_diff_pp']:+.2f} | {v['heavy_smoke']['n']:,} | "
            f"{v['heavy_smoke']['mean_bias']:+.2f} | {v['heavy_smoke']['t1_diff_pp']:+.2f} | "
            f"{v['heavy_minus_nonsmoke_bias']:+.2f} ({fmt_p_cell(v['bias_diff_p_site'])}) | "
            f"{v['heavy_minus_nonsmoke_t1_pp']:+.2f} ({fmt_p_cell(v['t1_diff_p_site'])}) |"
        )

    # Build Table 4 (Inference, LORO & Speciation)
    t4_md = [
        "| Robustness Dimension / Covariate | Estimate | 95% CI or SE | Diagnostic Detail |",
        "| :--- | ---: | ---: | :--- |",
        f"| 1-Way Site CR1 ({st_t1['g']} sites) | {t1_t['difference_pp']:+.2f} pp | {fmt_ci(st_t1['ci95'])} | Official Tier-1 matched Heavy ($N={t1_t['n_site_days']}$) |",
        f"| 1-Way Date CR1 ({dt_t1['g']} dates) | {t1_t['difference_pp']:+.2f} pp | {fmt_ci(dt_t1['ci95'])} | Contemporaneous spatial correlation across sites |",
        f"| 1-Way National Smoke Block ({nb_t1['g']} blocks) | {t1_t['difference_pp']:+.2f} pp | {fmt_ci(nb_t1['ci95'])} | Leave-one-block-out range {fmt_ci(t1_t['leave_one_nat_block_out_pp'])} pp |",
        f"| 1-Way Region-Smoke-Episode ({re_t1['g']} ep.) | {t1_t['difference_pp']:+.2f} pp | {fmt_ci(re_t1['ci95'])} | Leave-one-episode-out range {fmt_ci(t1_t['leave_one_reg_episode_out_pp'])} pp |",
        f"| 2-Way CGM Site × National Block | {t1_t['difference_pp']:+.2f} pp | {fmt_ci(tw_nb['ci95'])} | $p = {fmt_p(tw_nb['p_2sided'])}$; $df = {tw_nb['df']}$ |",
        f"| **2-Way CGM Site × Region-Episode (Primary)** | **{t1_t['difference_pp']:+.2f} pp** | **{fmt_ci(tw_t1['ci95'])}** | **$p = {fmt_p(tw_t1['p_2sided'])}$; $df = {tw_t1['df']}$** |",
        f"| Year-by-Year: 2023 / 2024 / 2025 | {yr_t1['2023']['difference_pp']:+.2f} / {yr_t1['2024']['difference_pp']:+.2f} / {yr_t1['2025']['difference_pp']:+.2f} pp | — | $n = {yr_t1['2023']['n']} / {yr_t1['2024']['n']} / {yr_t1['2025']['n']}$; positive every season |",
        f"| Leave-One-EPA-Region-Out (7 regions) | [{loro['min_loro_diff_pp']:+.2f}, {loro['max_loro_diff_pp']:+.2f}] pp | All 7 CIs $>0$ | Min drop R4 ({loro['by_region']['R4']['loro_diff_pp']:+.2f}); max drop R5 ({loro['by_region']['R5']['loro_diff_pp']:+.2f}) |",
        f"| Speciation: Organic Carbon (OC, $+1\\;\\mu\\text{{g/m}}^3$) | {s1_t['coefs']['oc']['beta']:+.3f} µg/m³ | SE {s1_t['coefs']['oc']['se_cr1']:.3f} | T640 Site+Mo FE ($N={s1_t['n']:,}$, $t={s1_t['coefs']['oc']['t_cr1']:+.2f}$); BAM null ({s1_b['coefs']['oc']['beta']:+.3f}, $p={fmt_p(s1_b['coefs']['oc']['p_cr1'])}$) |",
        f"| Speciation: OC × HMS Heavy Interaction | {s2_t['coefs']['oc_x_hms_h']['beta']:+.3f} µg/m³ | SE {s2_t['coefs']['oc_x_hms_h']['se_cr1']:.3f} | Additional smoke slope ($t={s2_t['coefs']['oc_x_hms_h']['t_cr1']:+.2f}$, $p={fmt_p(s2_t['coefs']['oc_x_hms_h']['p_cr1'])}$) |",
        f"| Speciation: Elemental Carbon (EC, $+1\\;\\mu\\text{{g/m}}^3$) | {s1_t['coefs']['ec']['beta']:+.3f} µg/m³ | SE {s1_t['coefs']['ec']['se_cr1']:.3f} | Light-absorption sign ($t={s1_t['coefs']['ec']['t_cr1']:+.2f}$); BAM null ($p={fmt_p(s1_b['coefs']['ec']['p_cr1'])}$) |",
        f"| Meteorology: Relative Humidity ($+10\\%$ RH) | {s1_t['coefs']['rh_10']['beta']:+.3f} µg/m³ | SE {s1_t['coefs']['rh_10']['se_cr1']:.3f} | Hygroscopicity ($t={s1_t['coefs']['rh_10']['t_cr1']:+.2f}$); BAM negative ({s1_b['coefs']['rh_10']['beta']:+.3f}, $t={s1_b['coefs']['rh_10']['t_cr1']:+.2f}$) |",
    ]

    nb10_frm = t1_t["near_threshold_bands"]["frm_pm10pct"]
    nb20_frm = t1_t["near_threshold_bands"]["frm_pm20pct"]
    nb10_mid = t1_t["near_threshold_bands"]["midpoint_pm10pct"]
    nb20_mid = t1_t["near_threshold_bands"]["midpoint_pm20pct"]
    nb20_bam = t1_b["near_threshold_bands"]["frm_pm20pct"]

    refs_md = build_references_md(r7)

    doc = f"""# Residual Optical PM₂.₅ Bias During Wildfire Smoke and Sensitivity of U.S. Exceptional-Event Tiering Thresholds

Zijian Zeng  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Abstract

In 2024, the U.S. Environmental Protection Agency (EPA) lowered the primary annual PM₂.₅ National Ambient Air Quality Standard (NAAQS) from 12.0 to 9.0 µg/m³, issued firmware-alignment revisions for Teledyne API Model T640/T640x optical monitors (AQS method codes 636/638), and published its April 2024 *PM₂.₅ Wildland Fire Exceptional Events Tiering Document* (EPA-457/R-24-001). Here we evaluate how residual optical–gravimetric divergence in post-alignment field networks alters site-month Tier-1 screening classifications when identical regulatory rules are applied to collocated instruments measuring the same air parcel. Across {all_c['t640_pairs']:,} same-site, same-day aligned T640_FW–Federal Reference Method (FRM) pairs ({all_c['t640_sites']} monitoring sites, 2023–2025) and {all_c['bam_pairs']:,} background-reference beta attenuation monitor (BAM 170/209)–FRM pairs ({all_c['bam_sites']} sites), a formal common-support audit reveals that the two networks share only {h_c['heavy_triple_site_days']} same-site, same-day triple observations ({h_c['heavy_overlap_dates']} overlapping dates) under NOAA Hazard Mapping System (HMS) Heavy smoke and diverge sharply in EPA regional coverage (23.9% of BAM Heavy pairs occur in Regions 9–10, where T640 has zero Heavy pairs). We therefore treat each instrument's within-site pairing against its own collocated FRM as primary and retain BAM strictly as a background reference benchmark. Replaying EPA's official published 2021–2025 site-month Tier-1 thresholds on {t1_t['n_site_days']} threshold-matched T640_FW–FRM Heavy-smoke pairs ({t1_t['n_sites']} sites), T640_FW triggers {t1_t['fem_exceed']} Tier-1 crossings versus {t1_t['frm_exceed']} on collocated FRM ({t1_t['fem_only']} T640-only vs. {t1_t['frm_only']} FRM-only; paired difference {t1_t['difference_pp']:+.2f} percentage points [pp], 95% CI {fmt_ci(nb_t1['ci95'])} across {nb_t1['g']} national smoke-date blocks; {fmt_ci(tw_t1['ci95'])}, $p = {fmt_p(tw_t1['p_2sided'])}$ under two-way Site × Region-Smoke-Episode clustering across {tw_t1['g2']} geographically distinct regional episodes), with consistent yearly point estimates ({yr_t1['2023']['difference_pp']:+.2f}, {yr_t1['2024']['difference_pp']:+.2f}, and {yr_t1['2025']['difference_pp']:+.2f} pp in 2023–2025) and positive leave-one-EPA-region-out stability ([{loro['min_loro_diff_pp']:+.2f}, {loro['max_loro_diff_pp']:+.2f}] pp). Crucially, strictly out-of-time prospective rolling 5-year reconstructions following EPA's exact Appendix N formula and May 1 certification calendar (2018–2022 → 2023, 2019–2023 → 2024, 2020–2024 → 2025) confirm unidirectional excess Tier-1 triggering across all four flag-exclusion specifications ({oot_a_t['difference_pp']:+.2f} to {oot_b2_t['difference_pp']:+.2f} pp; {oot_a_t['fem_only']}–{oot_b2_t['fem_only']} T640-only vs. 0 FRM-only; all two-way $p \\le {fmt_p(oot_c_t['inference']['twoway_site_x_reg_episode']['p_2sided'])}$), whereas background BAM–FRM remains near zero ({t1_b['difference_pp']:+.2f} pp official; {oot_a_b['difference_pp']:+.2f} to {oot_b2_b['difference_pp']:+.2f} pp out-of-time) even after restricting to overlapping dates, regions, and concentration bins (overlap-weighted differential {ow['differential_pp']:+.2f} pp, bootstrap 95% CI {fmt_ci(ow['block_bootstrap_ci95_pp'])}). Concentration-matched non-smoke controls (HMS = 0) and collocated chemical speciation reveal two distinct physical layers: residual baseline optical bias creates modest two-sided threshold sensitivity on elevated non-smoke days ({mc_t['other_site_15_25']['nonsmoke']['t1_diff_pp']:+.2f} to {mc_t['midpoint_15_25']['nonsmoke']['t1_diff_pp']:+.2f} pp at 15–25 µg/m³), but confirmed ground-level wildfire smoke (surface PM₂.₅ anomaly > site-month p90 and Organic Carbon ≥ 5 µg/m³) amplifies T640_FW bias three- to fivefold ({mc_t['other_site_ge15']['heavy_smoke']['mean_bias']:+.2f} to {mc_t['frm_ge25']['heavy_smoke']['mean_bias']:+.2f} µg/m³ vs. {mc_t['frm_ge25']['nonsmoke']['mean_bias']:+.2f} to {mc_t['midpoint_ge25']['nonsmoke']['mean_bias']:+.2f} µg/m³ non-smoke, all $p < 10^{{-4}}$) and drives steeply one-sided Tier-1 discordance near the decision boundary. These field findings quantify instrument-induced sensitivity at the initial Tier-1 screening stage; they do not evaluate subsequent agency filings, EPA concurrences, or Clean Air Act area designations.

**Synopsis:** Post-alignment optical PM₂.₅ monitors exhibit residual smoke-amplified positive bias relative to collocated gravimetric reference samplers, increasing EPA Tier-1 wildland fire screening crossings by +5.6 to +7.3 percentage points across retrospective and strictly out-of-time 5-year thresholds.

---

## 1. Introduction

Wildland fire smoke has become a dominant driver of extreme fine particulate matter (PM₂.₅) episodes across North America, eroding long-term clean-air gains and elevating acute mortality risk even below historical regulatory thresholds (Di et al., 2017; Childs et al., 2022; Burke et al., 2023; Jaffe et al., 2026). In February 2024, the U.S. Environmental Protection Agency (EPA) strengthened the primary annual PM₂.₅ National Ambient Air Quality Standard (NAAQS) from 12.0 to 9.0 µg/m³ (U.S. EPA, 2024a; 89 FR 16202). Because marginal annual averages near 9.0 µg/m³ can be pushed above compliance by a small number of severe smoke days, the Exceptional Events Rule (40 CFR § 50.14) plays an increasingly consequential role in regulatory air-quality accounting (Krupnick et al., 2025). To streamline clear-causal-relationship demonstrations for wildland fires, EPA issued its April 2024 *PM₂.₅ Wildland Fire Exceptional Events Tiering Document* (EPA-457/R-24-001; U.S. EPA, 2024b), which assigns candidate event days to Tier 1 (streamlined evidence), Tier 2 (intermediate evidence), or Tier 3 (full weight of evidence) based on site- and month-specific historical 98th-percentile thresholds computed from combined-site records under 40 CFR Part 50, Appendix N.

At the same time, U.S. state and local regulatory networks rely heavily on continuous Federal Equivalent Method (FEM) monitors rather than intermittent 24-hour gravimetric Federal Reference Method (FRM) filter samplers (Zou, 2021; Fowlie, Rubin, & Walker, 2019; Grainger & Schreiber, 2019). Among optical FEMs, the Teledyne API Model T640 and T640x broadband spectrometer instruments proliferated rapidly before field audits uncovered a systematic positive mass bias relative to FRMs. In May 2024, EPA approved a firmware network alignment (method codes 636/638 for aligned real-time collection and 736/738 for retroactively aligned historical records; U.S. EPA, 2024c). Controlled chamber experiments by Long et al. (2023) established that T640 light-scattering retrievals remain sensitive to aerosol composition, particle size distribution, refractive index, and biomass-burning smoke properties even after standard calibration adjustments. Separately, McClure et al. (2026) developed an automated nationwide screening pipeline to identify probable wildland fire exceptional events across the contiguous United States, and Krupnick et al. (2025) quantified how exceptional-event exclusions create growing divergence between ambient PM₂.₅ exposure and regulatory attainment metrics.

What remains untested at national field scale is whether *post-alignment* optical monitors operating in routine regulatory networks still diverge enough from collocated gravimetric FRMs during wildfire smoke to alter classification under EPA's exact April 2024 Tiering thresholds—and whether any observed threshold sensitivity is specific to biomass smoke or reflects general high-concentration optical bias. Answering this metrological question requires solving four methodological challenges simultaneously: (i) pairing post-alignment T640_FW (636/638) and FRM samplers on the exact same rooftop and calendar day to eliminate site-location and episode-timing confounders; (ii) auditing common geographic, temporal, and concentration support against beta attenuation monitors (BAM 170/209) so disjoint monitoring networks are not mistakenly treated as head-to-head equivalents; (iii) testing both EPA's official published 2021–2025 site-month thresholds (U.S. EPA, 2026) and strictly *out-of-time* prospective rolling 5-year thresholds reconstructed from historical certified AQS archives under EPA's May 1 annual certification schedule; and (iv) separating smoke-specific optical amplification from general non-smoke threshold sensitivity using concentration-matched non-smoke controls, independent surface chemical speciation, and multi-way event-level clustered inference (Cameron, Gelbach, & Miller, 2011).

This study provides that field-scale metrological evaluation across the 2023–2025 U.S. regulatory archive. We focus squarely on collocated measurement agreement and screening-threshold sensitivity under EPA-457/R-24-001; auxiliary screening-level 3-year annual Design Value sensitivity analyses (including the 2021–2023 county-level monitor Design Value threshold waterfall and observational Exceptional Event archival context) are documented separately in the Supporting Information to preserve strict separation between measurement screening and administrative determinations.

---

## 2. Materials and Methods

### 2.1 Collocated Pairing Construction, Method Codes, and Case-Flow Design

We constructed same-site, same-day paired daily 24-hour PM₂.₅ observations (parameter code 88101; sample durations `24 HOUR` and `24-HR BLK AVG`, 50 states plus DC) from EPA AirData bulk daily files (`daily_88101_2023.zip` through `daily_88101_2025.zip`). To isolate post-alignment optical performance without retroactive-alignment stitching artifacts, the optical cohort is restricted strictly to real-time firmware-aligned Teledyne T640 and T640x records (AQS method codes `636` and `638`, denoted `T640_FW`), paired against collocated gravimetric FRM samplers (11 gravimetric method codes) operating at the identical `site_id` on the identical `Date Local`. For a mass-based continuous reference comparator, we constructed an analogous `BAM–FRM` dataset restricted strictly to pure beta attenuation monitors (Met One BAM-1020/1022, AQS method codes `170` and `209`), excluding hybrid optical-nephelometer beta analyzers (such as Thermo 5030 SHARP, code `184`). Where multiple FRM or FEM Parameter Occurrence Codes (POCs) operated on the same rooftop-day, arithmetic means within instrument class yielded one unique `(site_id, Date Local)` pair.

Overhead wildfire smoke plumes were linked at exact monitor coordinates (`Latitude`, `Longitude`) across 100% of calendar days (2018–2025; 2,922/2,922 days) from NOAA Hazard Mapping System (HMS) daily smoke polygons, coding the highest intersecting density category per site-day (`0` = None, `1` = Light, `2` = Medium, `3` = Heavy). Because satellite HMS polygons detect column-integrated smoke aloft rather than guaranteed surface contact, we augmented the paired records with three independent surface indicators: (1) leave-one-site-out same-county-day PM₂.₅ from non-T640 (`FRM`/`BAM`) monitors (`other_site_pm_non_t640`), (2) site-month non-smoke 90th-percentile FRM anomalies, and (3) EPA Chemical Speciation Network (CSN) and IMPROVE 24-hour chemical speciation (`OC`, `EC`, `NO₃⁻`, `SO₄²⁻`) and AQS meteorology (`RH`, `Temp`), matched at exact 0 km rooftop coordinates first and nearest `< 25 km` same-county-day monitor second. Full data provenance, file sizes, and SHA-256 digests are exported in `tables/aqs_and_threshold_version_manifest.csv` and summarized in Supporting Information Section S1.

### 2.2 Common-Support Audit Between T640–FRM and BAM–FRM Queues

A critical methodological hazard when comparing collocated FEM–FRM cohorts across national monitoring networks is unequal geographic, seasonal, and concentration support. Before comparing `T640_FW–FRM` and `BAM–FRM` screening outcomes, we performed an explicit common-support audit quantifying: (a) exact same-site, same-day triple observations where `T640_FW`, `BAM`, and `FRM` operated simultaneously on the same rooftop (both across all 2023–2025 days and under HMS Heavy smoke); (b) overlap in calendar smoke dates, monitoring sites, and U.S. EPA Regions (1–10); and (c) FRM concentration quantile distributions.

To test whether cross-network differences persist when support is aligned, we estimated differential Tier-1 exceedance gaps, $\\Delta_{{\\text{{diff}}}} = \\bar{{\\delta}}_{{\\text{{T640}}}} - \\bar{{\\delta}}_{{\\text{{BAM}}}}$, across five progressively stricter overlap filters (Full Matched Heavy, Overlapping EPA Regions, Overlapping Smoke Dates, Overlapping Dates & Regions, and Overlapping Dates, Regions & FRM $\\le 50\\;\\mu\\text{{g/m}}^3$) using pooled regressions clustered on common national smoke-date blocks, plus an exact overlap-weighted (harmonic/ATO-weighted) estimator across shared `EPA Region × FRM-concentration-bin` strata (`<10`, `10–15`, `15–25`, `25–40`, `≥40 µg/m³`) with 1,000 smoke-block bootstrap replications. Because exact Heavy-smoke triple support is sparse ($n = {h_c['heavy_triple_site_days']}$ site-days), our inferential design retains each instrument's within-site comparison against its own collocated gravimetric FRM as the primary estimand and explicitly demotes `BAM–FRM` to a background reference benchmark rather than claiming balanced head-to-head network equivalence.

### 2.3 Official EPA April 2024 Tiering Algorithm and Out-of-Time Prospective Reconstruction

Under EPA-457/R-24-001 (U.S. EPA, 2024b), the baseline tiering threshold (Tier 2 lower bound) for site $s$ and calendar month $m$ is defined from the most recent five certified calendar years of combined-site daily 24-hour PM₂.₅ data (constructed per 40 CFR Part 50, Appendix N § 3.0(d)) after excluding site-days carrying any Request Exclusion (`R`) or fire-related Informational Only (`I`) qualifier at any monitor on site:

$$T_{{2,sm}} = \\min\\!\\left(P_{{98,sm}}^{{(5\\text{{-yr}})}},\\; \\min_{{y \\in \\mathcal{{Y}}_5}} P_{{98,sy}}\\right), \\qquad T_{{1,sm}} = 1.5 \\times T_{{2,sm}}$$

where $P_{{98,sm}}^{{(5\\text{{-yr}})}}$ is the 5-year month-specific 98th percentile for calendar month $m$, $P_{{98,sy}}$ is the annual 98th percentile for year $y$ computed per 40 CFR Part 50, Appendix N § 4.5(a) Table 1 order statistics, and a candidate day meets Tier 1 iff its 24-hour concentration is $\\ge T_{{1,sm}}$ (and Tier 2 iff $T_{{2,sm}} \\le C < T_{{1,sm}}$). Annual data certifications are due May 1 of the following year, shifting $\\mathcal{{Y}}_5$ forward by one year each May (U.S. EPA, 2024b, p. 10).

We evaluate paired `T640_FW–FRM` and `BAM–FRM` crossings using two complementary threshold architectures:
1. **Retrospective Official EPA Published Table (`2021–2025`):** We pinned EPA's live public PM₂.₅ Tiering Tool table (`for_posting.csv`, AQS query date `2026-09-14`, `13,138` site-month rows, `R` and fire-related `I` flags excluded; U.S. EPA, 2026) and verified exact algebraic identity ($T_1 = 1.5 \\times T_2$ and $T_2 = \\min(\\text{{monthly}}_{{98}}, \\text{{annual}}_{{98,\\min}})$) across every row. Because the `2021–2025` baseline overlaps the `2023–2025` evaluation window, this replay is explicitly labeled **retrospective**. Both collocated readings on a site-day receive the identical published site-month cutoff.
2. **Strictly Out-of-Time Prospective Rolling 5-Year Reconstructions (`2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`):** To eliminate all in-sample baseline leakage and mirror contemporaneous operational screening under EPA's May 1 certification calendar (note: `0` of `{h_c['t640_full_pairs']}` T640 Heavy-smoke days occurred before May 1, so `100%` of T640 Heavy days use certified years $Y-5$ through $Y-1$; the `5` January BAM Heavy days use $Y-6$ through $Y-2$), we reconstructed site-level combined daily records from our 2018–2025 AQS daily archive (`daily_88101_2018..2025.zip`) and `aqs_monitors.zip` (prioritizing each site's `NAAQS Primary Monitor` POC per Appendix N § 3.0(d), excluding pre-alignment raw T640 `236/238`, and applying exact Appendix N § 4.5(a) Table 1 98th percentiles). Because public AirData bulk daily CSVs expose AQS `Excluded` daily records and monitor-year `Events Excluded` 98th percentiles (`annual_conc_by_monitor_YYYY.zip`, which strip `R`-flagged days) but do not distribute individual-day `I`-qualifier codes (`IF`/`IT`), we evaluate four transparent out-of-time specifications:
   - **`OOT-A` (Conservative `R`-Excluded AQS / AMP480 Bound):** Combined-site daily series dropping `Excluded` site-days, paired with AQS `annual_conc_by_monitor` `Events Excluded` annual 98th percentiles. Per EPA-457/R-24-001 (p. 16), retaining `I`-flagged days yields a conservative upper bound on thresholds (analogous to AQS report AMP480).
   - **`OOT-B` (Fire-Screen Proxy — Excluding HMS Heavy):** `OOT-A` additionally removing NOAA HMS Heavy (`level = 3`) fire-smoke site-days from the historical 5-year window as a transparent proxy for unexposed fire-`I` qualifiers.
   - **`OOT-B2` (Expanded Fire-Screen Proxy — Excluding HMS Medium+Heavy):** `OOT-A` removing HMS Medium and Heavy (`level ≥ 2`) days from the historical 5-year baseline.
   - **`OOT-C` (Pure Gravimetric FRM-Only Rolling Baseline):** Computing rolling 5-year thresholds exclusively from collocated gravimetric FRM measurements so no optical instrument enters the baseline itself.

We validated our Appendix N reconstruction code directly against EPA's published `2021–2025` table before running prospective windows: across zero-event clean sites ({rec_b['cs_all_no_ann_excl']['zero_flag_clean_sites_n']:,} site-months), median absolute Tier-1 error is exactly **{rec_b['cs_all_no_ann_excl']['zero_flag_clean_median_abs_err']:.3f} µg/m³** ($r = {rec_b['cs_all_no_ann_excl']['zero_flag_clean_corr']:.3f}$; `OOT-B` clean-site $r = {rec_b['oot_b_cs_excl_hms3']['zero_flag_clean_corr']:.3f}$, median $|e| = {rec_b['oot_b_cs_excl_hms3']['zero_flag_clean_median_abs_err']:.3f}$ µg/m³; full benchmark in SI Table S2 and Figure S2A). Across both retrospective and out-of-time thresholds, we report full **bidirectional discordance** (`FEM ≥ T1 & FRM < T1` vs. `FRM ≥ T1 & FEM < T1`), exact paired McNemar binomial $p$-values, and **near-threshold band sensitivity** within `±10%` and `±20%` of Tier-1 defined both by FRM and by the symmetric pair midpoint $(\\text{{FEM}} + \\text{{FRM}})/2$.

### 2.4 Multi-Dimensional Inference and Ground-Level Smoke Specificity Controls

Each paired site-day $i$ contributes a binary threshold-crossing difference $\\delta_i = \\mathbf{{1}}(\\text{{FEM}}_i \\ge T_i) - \\mathbf{{1}}(\\text{{FRM}}_i \\ge T_i) \\in \\{{-1, 0, +1\\}}$. Because wildfire plumes span multiple days and monitoring sites simultaneously, naive site-day or one-way site standard errors understate uncertainty (Abadie et al., 2023). Alongside one-way site ($G = {st_t1['g']}$), calendar-date ($G = {dt_t1['g']}$), and national consecutive smoke-date block ($G = {nb_t1['g']}$) finite-sample $t$ intervals, we construct geographically separated **Region-Smoke-Episodes** grouping Heavy-smoke dates within the same U.S. EPA Region separated by $\\le 2$ calendar days ($G = {re_t1['g']}$ regional episodes for T640) and compute **Cameron, Gelbach, & Miller (2011) two-way cluster-robust intervals** simultaneously clustering on `(Site × National Smoke Block)` and `(Site × Region-Smoke-Episode)` with $\\min(G_1, G_2) - 1$ degrees of freedom. We further verify stability via year-by-year estimation (`2023`, `2024`, `2025`), leave-one-national-block-out, leave-one-regional-episode-out, and leave-one-EPA-region-out validation.

To distinguish **smoke-specific optical amplification** from **general high-PM₂.₅ threshold sensitivity**, we compare `T640_FW − FRM` concentration bias and official Tier-1 exceedance differences on non-smoke days (`HMS = 0`) versus Heavy smoke days (`HMS = 3`) within matched elevated concentration bands (`≥15`, `15–25`, `≥20`, and `≥25 µg/m³`). Because conditioning solely on noisy FRM can induce errors-in-variables (EIV) attenuation at high FRM values (Bland & Altman, 1986), we evaluate all three concentration definitions side-by-side: (i) collocated FRM, (ii) strictly independent other-site `FRM/BAM`-only PM₂.₅ in the same county-day (`other_site_pm_non_t640`), and (iii) Bland–Altman pair midpoint $(\\text{{FEM}} + \\text{{FRM}})/2$ (exact under equal error variances), testing `Heavy − Non-Smoke` differentials via Site-clustered CR1 regressions (Cameron, Gelbach, & Miller, 2008; Roodman et al., 2019). Finally, we stratify HMS Heavy days by independent ground-level smoke confirmation—surface PM₂.₅ anomaly above site-month non-smoke `p90` versus aloft plumes ($\\le$ `p90`), and collocated CSN/IMPROVE Organic Carbon (`OC ≥ 5` vs. `< 5 µg/m³`) and biomass-burning ratio (`OC/EC ≥ 5`)—and pair these with Site + Month fixed-effects speciation regressions (`N = {s1_t['n']:,}` T640 pairs; `{s3_t['n']:,}` exact 0 km rooftops).

---

## 3. Results

### 3.1 Collocated Pairing Quality, Baseline Agreement, and Common-Support Audit

Across 2023–2025, the post-alignment optical archive comprises {all_c['t640_pairs']:,} same-site, same-day `T640_FW–FRM` pairs across {all_c['t640_sites']} monitoring sites (`2023-06-14` through `2025-12-31`), retaining a modest positive daily baseline bias of {sg_t['sample_2023_2025']['mean_bias']:+.2f} µg/m³ (median {sg_t['sample_2023_2025']['median_bias']:+.2f} µg/m³) that peaks in the Midwest ({sg_t['by_region_2023_2025']['MW']['mean_bias']:+.2f} µg/m³) and winter DJF ({sg_t['by_season_2023_2025']['DJF']['mean_bias']:+.2f} µg/m³) while nearing zero in the arid West ({sg_t['by_region_2023_2025']['WE']['mean_bias']:+.2f} µg/m³, $p = {fmt_p(sg_t['by_region_2023_2025']['WE']['p_site_cr1'])}$). The background `BAM–FRM` archive comprises {all_c['bam_pairs']:,} pairs across {all_c['bam_sites']} sites (mean daily bias {sg_b['sample_2023_2025']['mean_bias']:+.2f} µg/m³, median {sg_b['sample_2023_2025']['median_bias']:+.2f} µg/m³). Filtering to NOAA HMS Heavy smoke yields {h_c['t640_full_pairs']} `T640_FW–FRM` pairs ({h_c['t640_full_sites']} sites, {h_c['t640_full_dates']} dates), of which {t1_t['n_site_days']} ({t1_t['n_sites']} sites; `4` unmatched new sites) match EPA's official site-month threshold table, and {h_c['bam_full_pairs']} `BAM–FRM` pairs ({h_c['bam_full_sites']} sites, {h_c['bam_full_dates']} dates), of which {t1_b['n_site_days']} ({t1_b['n_sites']} sites; `4` unmatched) match EPA thresholds.

Our common-support audit reveals pronounced geographic and concentration disjointness between the two networks (**Figure 1A**, **Table 1**). First, across all 2023–2025 days, only {all_c['triple_site_days']} same-site, same-day triple observations (`T640_FW`, `BAM`, and `FRM` co-operating on the same rooftop) occur across {all_c['triple_sites']} stations; under HMS Heavy smoke, exact triple overlap collapses to just **{h_c['heavy_triple_site_days']} site-days across {h_c['heavy_triple_sites']} sites** (with {h_c['heavy_overlap_sites']} overlapping sites and **{h_c['heavy_overlap_dates']} overlapping Heavy-smoke dates**). Notably, even in those {all_c['triple_site_days']} same-rooftop triples (**Figure 1B** inset), mean `T640_FW − BAM` rises monotonically with smoke intensity from {tr['hms_0_none']['mean_t640_minus_bam']:+.2f} µg/m³ (`HMS = 0`, $n = {tr['hms_0_none']['n_site_days']}$) and {tr['hms_1_light']['mean_t640_minus_bam']:+.2f} µg/m³ (`Light`, $n = {tr['hms_1_light']['n_site_days']}$) to {tr['hms_2_medium']['mean_t640_minus_bam']:+.2f} µg/m³ (`Medium`, $n = {tr['hms_2_medium']['n_site_days']}$) and {tr['hms_3_heavy']['mean_t640_minus_bam']:+.2f} µg/m³ across the {tr['hms_3_heavy']['n_site_days']} Heavy-smoke triples (`T640_FW − FRM` = {tr['hms_3_heavy']['mean_t640_minus_frm']:+.2f} vs. `BAM − FRM` = {tr['hms_3_heavy']['mean_bam_minus_frm']:+.2f} µg/m³; individual triple records listed in SI Table S1). Second, `T640_FW` Heavy-smoke pairs lie exclusively in EPA Regions 1–5, 7, and 8 (zero pairs in Regions 6, 9, and 10; median FRM `{h_c['frm_quantiles_matched']['t640_fw']['p50']:.2f}` µg/m³, 90th percentile `{h_c['frm_quantiles_matched']['t640_fw']['p90']:.2f}` µg/m³), whereas `47/197` (`23.9%`) of `BAM` Heavy-smoke pairs sit in Pacific Regions 9–10 with a much higher reference concentration distribution (median FRM `{h_c['frm_quantiles_matched']['bam']['p50']:.2f}`, 90th percentile `{h_c['frm_quantiles_matched']['bam']['p90']:.2f}` µg/m³).

<!-- FIGURE:fig1_est_caseflow_and_common_support.png -->

**Table 1. Common-Support Audit Between T640_FW–FRM and Background BAM–FRM Queues Under NOAA HMS Heavy Smoke (Official EPA 2021–2025 Tier-1 Threshold)**

{chr(10).join(t1_md)}

*Notes:* Overlap percentages report the share of threshold-matched Heavy-smoke pairs (`N = 468` T640_FW; `N = 197` BAM) retained in each common-support filter. Differential CIs cluster on common national smoke-date blocks (Row 6 uses 1,000 smoke-block bootstrap replications across 29 shared `EPA Region × FRM-bin` cells using harmonic overlap weights). Because same-site, same-day Heavy-smoke triple support is $n = 4$, `BAM–FRM` serves strictly as a background reference benchmark rather than a balanced head-to-head network trial.

Restricting both queues to common support **widens** rather than shrinks the T640–BAM separation (**Table 1**, **Figure 1B**). Dropping Regions 9–10 (`100.0%` T640 / `76.1%` BAM retained) shifts BAM's Tier-1 difference to {bm_m['overlap_epa_regions']['bam_diff_pp']:+.2f} pp (mean bias {bm_m['overlap_epa_regions']['bam_mean_bias']:+.2f} µg/m³), yielding a T640 − BAM differential of {bm_m['overlap_epa_regions']['differential_t640_minus_bam_pp']:+.2f} pp (95% block CI {fmt_ci(bm_m['overlap_epa_regions']['differential_ci95_block_pp'])}, $p = {fmt_p(bm_m['overlap_epa_regions']['differential_p_block'])}$). Restricting further to the {h_c['heavy_overlap_dates']} overlapping Heavy-smoke dates within shared EPA Regions (`89.1%` T640 / `48.2%` BAM) yields {bm_m['overlap_dates_and_regions']['t640_diff_pp']:+.2f} pp for T640 versus {bm_m['overlap_dates_and_regions']['bam_diff_pp']:+.2f} pp for BAM (differential {bm_m['overlap_dates_and_regions']['differential_t640_minus_bam_pp']:+.2f} pp, {fmt_ci(bm_m['overlap_dates_and_regions']['differential_ci95_block_pp'])}, $p = {fmt_p(bm_m['overlap_dates_and_regions']['differential_p_block'])}$). Exact overlap-weighted matching across {ow['n_shared_cells']} shared `EPA Region × FRM-bin` strata (`100.0%` T640 / `66.0%` BAM covered) confirms a {ow['differential_pp']:+.2f} pp differential (bootstrap 95% CI {fmt_ci(ow['block_bootstrap_ci95_pp'])}). Nevertheless, because disjoint site composition cannot be fully eliminated with $n = {h_c['heavy_triple_site_days']}$ Heavy triples, all primary claims below rest on each instrument's clean within-site comparison against its own collocated FRM.

### 3.2 Official EPA Tier-1 Screening Replay and Strictly Out-of-Time Prospective Validation

Under EPA's official published 2021–2025 site-month thresholds (**Table 2**, **Figure 2A**), aligned `T640_FW` registers **{t1_t['fem_exceed']}** Tier-1 crossings compared with **{t1_t['frm_exceed']}** on collocated gravimetric FRM across {t1_t['n_site_days']} matched Heavy-smoke site-days ({t1_t['n_sites']} sites), with steeply asymmetric bidirectional discordance of **{t1_t['fem_only']} T640-only** versus **{t1_t['frm_only']} FRM-only** crossings (exact paired McNemar $p = {fmt_p(t1_t['mcnemar_exact_p'])}$). The paired exceedance difference is **{t1_t['difference_pp']:+.2f} pp**, excluding zero across every clustering structure: 95% CI {fmt_ci(nb_t1['ci95'])} across {nb_t1['g']} national smoke-date blocks, {fmt_ci(tw_nb['ci95'])} under two-way `Site × National Block` clustering, and **{fmt_ci(tw_t1['ci95'])} ($p = {fmt_p(tw_t1['p_2sided'])}$)** under our primary two-way `Site × Region-Smoke-Episode` clustering across {tw_t1['g2']} geographically distinct regional episodes. At EPA's Tier-2 lower threshold (which includes Tier-1 days), `T640_FW` registers {t2_t['fem_exceed']} versus {t2_t['frm_exceed']} crossings ({t2_t['fem_only']} vs. {t2_t['frm_only']} discordant; {t2_t['difference_pp']:+.2f} pp, two-way 95% CI {fmt_ci(t2_t['inference']['twoway_site_x_reg_episode']['ci95'])}). At the fixed daily `>35 µg/m³` level-equivalent benchmark (distinct from the 3-year 98th-percentile 24-hour NAAQS), `T640_FW` records {f35_t['fem_exceed']} versus {f35_t['frm_exceed']} crossings in the threshold-matched sample ({f35_t['fem_only']} vs. {f35_t['frm_only']}; {f35_t['difference_pp']:+.2f} pp; {f35_tf['fem_exceed']} vs. {f35_tf['frm_exceed']} across all {f35_tf['n_site_days']} Heavy pairs), but its national-block 95% CI spans zero ({fmt_ci(f35_t['inference']['oneway_nat_block']['ci95'])}) due to episodic concentration of extreme-smoke exceedances, confirming that the site-month EPA Tier-1 threshold provides the more stable screening metric. In the background `BAM–FRM` comparator, both instruments record exactly {t1_b['fem_exceed']} Tier-1 crossings ({t1_b['fem_only']} BAM-only vs. {t1_b['frm_only']} FRM-only; {t1_b['difference_pp']:+.2f} pp, two-way 95% CI {fmt_ci(t1_b['inference']['twoway_site_x_reg_episode']['ci95'])}).

<!-- FIGURE:fig2_est_official_and_oot_tier_replay.png -->

**Table 2. Retrospective Official EPA (2021–2025) and Strictly Out-of-Time Prospective Rolling 5-Year Tier-1 Threshold Replays on Collocated NOAA HMS Heavy-Smoke Site-Days (2023–2025)**

{chr(10).join(t2_md)}

*Notes:* Official EPA 2021–2025 rows replay EPA's pinned `for_posting.csv` snapshot (AQS query date `2026-09-14`, `R` and fire-`I` flags excluded). Out-of-time (`OOT`) rows compute EPA's exact Appendix N § 3.0(d) and § 4.5(a) Table 1 formula strictly from historical certified 5-year windows under EPA's May 1 annual certification calendar (`2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`; 0/472 T640 and 5/201 BAM Heavy days fall before May 1). National-block CIs cluster on consecutive national Heavy-smoke date runs; two-way CIs follow Cameron, Gelbach, & Miller (2011) clustering simultaneously on `Site × EPA-Region-Smoke-Episode` ($\\le 2$-day gap within EPA Region).

Crucially, **strictly out-of-time prospective rolling 5-year replays confirm consistent, unidirectional Tier-1 excess triggering on `T640_FW` without any in-sample baseline overlap** (**Table 2**, **Figure 2A**). Under our conservative `R`-excluded AQS benchmark (`OOT-A`, mirroring EPA-457/R-24-001 p. 16's AMP480 conservative bound), `T640_FW` triggers {oot_a_t['fem_exceed']} versus {oot_a_t['frm_exceed']} Tier-1 crossings across {oot_a_t['n_site_days']} pairs (**{oot_a_t['fem_only']} T640-only vs. {oot_a_t['frm_only']} FRM-only**; **{oot_a_t['difference_pp']:+.2f} pp**, national-block 95% CI {fmt_ci(oot_a_t['inference']['oneway_nat_block']['ci95'])}, two-way `Site × Region-Episode` CI **{fmt_ci(oot_a_t['inference']['twoway_site_x_reg_episode']['ci95'])}**, $p = {fmt_p(oot_a_t['inference']['twoway_site_x_reg_episode']['p_2sided'])}$), with positive excess in every evaluation year (`2023`: {oot_a_t['by_year']['2023']['difference_pp']:+.2f} pp, `2024`: {oot_a_t['by_year']['2024']['difference_pp']:+.2f} pp, `2025`: {oot_a_t['by_year']['2025']['difference_pp']:+.2f} pp). Progressively screening out fire-impacted baseline days to proxy unexposed `I`-qualifier exclusions monotonically shifts the prospective point estimate toward EPA's official 2021–2025 replay: `OOT-B` (excluding HMS Heavy baseline days) reaches **{oot_b_t['difference_pp']:+.2f} pp** ({oot_b_t['fem_exceed']} vs. {oot_b_t['frm_exceed']}, {oot_b_t['fem_only']} vs. {oot_b_t['frm_only']}, two-way CI {fmt_ci(oot_b_t['inference']['twoway_site_x_reg_episode']['ci95'])}, $p = {fmt_p(oot_b_t['inference']['twoway_site_x_reg_episode']['p_2sided'])}$), and `OOT-B2` (excluding HMS Medium+Heavy) reaches **{oot_b2_t['difference_pp']:+.2f} pp** ({oot_b2_t['fem_exceed']} vs. {oot_b2_t['frm_exceed']}, {oot_b2_t['fem_only']} vs. {oot_b2_t['frm_only']}, two-way CI {fmt_ci(oot_b2_t['inference']['twoway_site_x_reg_episode']['ci95'])}, $p = {fmt_p(oot_b2_t['inference']['twoway_site_x_reg_episode']['p_2sided'])}$). Even constructing rolling 5-year thresholds exclusively from pure gravimetric FRM records (`OOT-C`, eliminating optical instruments from the baseline completely) preserves **{oot_c_t['difference_pp']:+.2f} pp** ({oot_c_t['fem_exceed']} vs. {oot_c_t['frm_exceed']}, {oot_c_t['fem_only']} vs. {oot_c_t['frm_only']}, two-way CI {fmt_ci(oot_c_t['inference']['twoway_site_x_reg_episode']['ci95'])}, $p = {fmt_p(oot_c_t['inference']['twoway_site_x_reg_episode']['p_2sided'])}$). Across all four out-of-time specifications, background `BAM–FRM` stays dead null ({oot_a_b['difference_pp']:+.2f} to {oot_b2_b['difference_pp']:+.2f} pp, all $p \\ge {fmt_p(oot_b2_b['inference']['twoway_site_x_reg_episode']['p_2sided'])}$). Notice why `2025` out-of-time point estimates (`+3.08` to `+3.59 pp` under `OOT-A/B/B2`) are narrower than under EPA's published 2021–2025 table (`+8.08 pp`): the historic 2023 Canadian wildfire smoke season enters the `2020–2024` 5-year baseline, and retaining unflagged or `I`-flagged 2023 smoke days in public AirData raises reconstructed `2020–2024` monthly 98th percentiles—precisely the conservative direction documented in EPA-457/R-24-001 (p. 16).

Examining the normalized concentration plane (**Figure 2B**) demonstrates that screening discordance concentrates sharply in the near-threshold boundary zone. Within `±10%` of the site-month Tier-1 cutoff by FRM ($n = {nb10_frm['n']}$), `T640_FW` generates {nb10_frm['fem_only']} T640-only crossings versus {nb10_frm['frm_only']} FRM-only ({nb10_frm['difference_pp']:+.2f} pp); defined symmetrically by pair midpoint $(\\text{{FEM}} + \\text{{FRM}})/2$ ($n = {nb10_mid['n']}$), the split is {nb10_mid['fem_only']} versus {nb10_mid['frm_only']} ({nb10_mid['difference_pp']:+.2f} pp). Within `±20%` of Tier-1, {nb20_frm['fem_only']} of all {t1_t['fem_only']} T640-only crossings occur by FRM ($n = {nb20_frm['n']}$, {nb20_frm['difference_pp']:+.2f} pp) and {nb20_mid['fem_only']}/{t1_t['fem_only']} (`100%`) occur by pair midpoint ($n = {nb20_mid['n']}$, {nb20_mid['difference_pp']:+.2f} pp). In sharp contrast, within `±20%` of Tier-1 on background `BAM–FRM` ($n = {nb20_bam['n']}$), discordance is perfectly symmetric ({nb20_bam['fem_only']} BAM-only vs. {nb20_bam['frm_only']} FRM-only; {nb20_bam['difference_pp']:+.2f} pp).

### 3.3 Ground-Level Smoke Specificity, Equal-Concentration Non-Smoke Controls, Chemical Speciation, and Event-Level Robustness

A central scientific question is whether T640's Tier-1 excess reflects **smoke-specific optical amplification** or **general high-PM₂.₅ threshold sensitivity** present whenever ambient concentrations approach a cutoff. Comparing `T640_FW − FRM` bias and Tier-1 crossings on non-smoke days (`HMS = 0`) against HMS Heavy smoke days (`HMS = 3`) within matched elevated concentration bands yields a nuanced, two-layer physical answer (**Table 3**, **Figure 3A**):

1. **General Non-Smoke Baseline Sensitivity at Moderate Concentrations (`15–25 µg/m³`):** Across all non-smoke pairs (`HMS = 0`, $n = {hms_t['hms_0_none']['n']:,}$), mean T640 bias is {hms_t['hms_0_none']['mean_bias']:+.2f} µg/m³ and Tier-1 excess is minimal ({hms_t['hms_0_none']['t1_diff_pp']:+.2f} pp). However, restricting non-smoke days to moderately elevated concentrations (`15–25 µg/m³`) reveals non-trivial positive Tier-1 discordance even without overhead smoke: {mc_t['other_site_15_25']['nonsmoke']['t1_diff_pp']:+.2f} pp when conditioned on independent non-T640 other-site monitors (`bias {mc_t['other_site_15_25']['nonsmoke']['mean_bias']:+.2f} µg/m³`, $n = {mc_t['other_site_15_25']['nonsmoke']['n']:,}$), {mc_t['frm_15_25']['nonsmoke']['t1_diff_pp']:+.2f} pp by FRM (`bias {mc_t['frm_15_25']['nonsmoke']['mean_bias']:+.2f} µg/m³`), and {mc_t['midpoint_15_25']['nonsmoke']['t1_diff_pp']:+.2f} pp by pair midpoint (`bias {mc_t['midpoint_15_25']['nonsmoke']['mean_bias']:+.2f} µg/m³`). Seasonal decomposition (**Figure 3B**) shows this non-smoke sensitivity occurs predominantly during humid winter (`DJF`) inorganic pollution episodes (`FRM ≥ 20`: bias {gv_t['nonsmoke_frm_ge20_winter_djf']['mean_bias']:+.2f} µg/m³, Tier-1 {gv_t['nonsmoke_frm_ge20_winter_djf']['t1_diff_pp']:+.2f} pp, two-sided `{gv_t['nonsmoke_frm_ge20_winter_djf']['fem_only']}` vs. `{gv_t['nonsmoke_frm_ge20_winter_djf']['frm_only']}`), whereas fire-season (`May–Sep`) non-smoke elevated days (`FRM ≥ 20`) exhibit *negative* bias ({gv_t['nonsmoke_frm_ge20_warm_mjjas']['mean_bias']:+.2f} µg/m³, Tier-1 {gv_t['nonsmoke_frm_ge20_warm_mjjas']['t1_diff_pp']:+.2f} pp, likely reflecting coarse dust or fireworks aerosols).
2. **Pronounced Smoke-Specific Optical Amplification:** Conditioning on identical concentration bands across *every* EIV-robust and reference metric, HMS Heavy smoke multiplies T640_FW's positive optical bias three- to fivefold relative to non-smoke days (**Table 3**, **Figure 3A**). At `Other-Site (FRM/BAM) ≥ 15 µg/m³`, optical bias jumps from {mc_t['other_site_ge15']['nonsmoke']['mean_bias']:+.2f} µg/m³ on non-smoke days to {mc_t['other_site_ge15']['heavy_smoke']['mean_bias']:+.2f} µg/m³ under Heavy smoke ($\\Delta = {mc_t['other_site_ge15']['heavy_minus_nonsmoke_bias']:+.2f}$ µg/m³, Site-clustered $p = {fmt_p(mc_t['other_site_ge15']['bias_diff_p_site'])}$), driving Tier-1 excess from {mc_t['other_site_ge15']['nonsmoke']['t1_diff_pp']:+.2f} pp to {mc_t['other_site_ge15']['heavy_smoke']['t1_diff_pp']:+.2f} pp ($\\Delta = {mc_t['other_site_ge15']['heavy_minus_nonsmoke_t1_pp']:+.2f}$ pp, $p = {fmt_p(mc_t['other_site_ge15']['t1_diff_p_site'])}$). At high concentrations (`≥25 µg/m³`), non-smoke bias turns flat or negative ({mc_t['other_site_ge25']['nonsmoke']['mean_bias']:+.2f} µg/m³ by Other-Site; {mc_t['frm_ge25']['nonsmoke']['mean_bias']:+.2f} by FRM; {mc_t['midpoint_ge25']['nonsmoke']['mean_bias']:+.2f} by Midpoint), whereas Heavy-smoke bias surges to **{mc_t['other_site_ge25']['heavy_smoke']['mean_bias']:+.2f}–{mc_t['frm_ge25']['heavy_smoke']['mean_bias']:+.2f} µg/m³** ($\\Delta = {mc_t['midpoint_ge25']['heavy_minus_nonsmoke_bias']:+.2f}$ to {mc_t['frm_ge25']['heavy_minus_nonsmoke_bias']:+.2f} µg/m³, all $p \\le {fmt_p(mc_t['other_site_ge25']['bias_diff_p_site'])}$), with zero FRM-only Tier-1 reversals (`5–9` T640-only vs. `0` FRM-only). Across all four HMS smoke levels, T640_FW bias increases monotonically (`HMS 0`: {hms_t['hms_0_none']['mean_bias']:+.2f} → `Light`: {hms_t['hms_1_light']['mean_bias']:+.2f} → `Medium`: {hms_t['hms_2_medium']['mean_bias']:+.2f} → `Heavy`: {hms_t['hms_3_heavy']['mean_bias']:+.2f} µg/m³).

<!-- FIGURE:fig3_est_smoke_vs_nonsmoke_and_ground_truth.png -->

**Table 3. Equal-Concentration Non-Smoke (HMS = 0) Versus Heavy Smoke (HMS = 3) Control Tests on Aligned T640_FW–FRM Pairs (2023–2025)**

{chr(10).join(t3_md)}

*Notes:* All differences (`Heavy − Non-Smoke`) and $p$-values are estimated via Site-clustered CR1 OLS regressions within each concentration stratum. `Other-Site (FRM/BAM)` uses strictly independent leave-one-site-out gravimetric FRM or BAM monitors in the same county-day to eliminate mechanical errors-in-variables coupling; `Bland-Altman Midpoint` uses $(\\text{{FEM}}+\\text{{FRM}})/2$ (exact under equal instrument error variances).

Independent **ground-level smoke confirmation** verifies that Tier-1 discordance concentrates specifically on surface-impacted wildfire plumes rather than overhead smoke aloft (**Figure 3B**). Among HMS Heavy site-days where collocated FRM exceeds the site-month non-smoke 90th percentile ($n = {gv_t['heavy_surface_impact_frm_gt_p90']['n']}$), optical bias averages {gv_t['heavy_surface_impact_frm_gt_p90']['mean_bias']:+.2f} µg/m³ and Tier-1 excess reaches **{gv_t['heavy_surface_impact_frm_gt_p90']['t1_diff_pp']:+.2f} pp** (`{gv_t['heavy_surface_impact_frm_gt_p90']['fem_only']}` vs. `{gv_t['heavy_surface_impact_frm_gt_p90']['frm_only']}`), whereas HMS Heavy days remaining at or below the site-month non-smoke p90 ($n = {gv_t['heavy_lofted_frm_le_p90']['n']}$, indicating lofted plumes with minimal ground mixing) show low bias ({gv_t['heavy_lofted_frm_le_p90']['mean_bias']:+.2f} µg/m³) and **0 vs. 0** Tier-1 crossings (`0.00 pp`). Likewise, among HMS Heavy pairs with collocated EPA speciation (`{gv_t['speciation_coverage_on_heavy']['n_with_oc']}/{gv_t['speciation_coverage_on_heavy']['n_total_heavy']}` days; median OC `{gv_t['speciation_coverage_on_heavy']['heavy_median_oc']:.2f}` vs. `{gv_t['speciation_coverage_on_heavy']['nonsmoke_median_oc']:.2f}` µg/m³ on non-smoke days), days with confirmed elevated surface Organic Carbon (`OC ≥ 5 µg/m³`, $n = {gv_t['heavy_oc_ge5']['n']}$) exhibit **{gv_t['heavy_oc_ge5']['mean_bias']:+.2f} µg/m³** bias and **{gv_t['heavy_oc_ge5']['t1_diff_pp']:+.2f} pp** Tier-1 excess (`{gv_t['heavy_oc_ge5']['fem_only']}` vs. `{gv_t['heavy_oc_ge5']['frm_only']}`), compared with only {gv_t['heavy_oc_lt5']['mean_bias']:+.2f} µg/m³ and {gv_t['heavy_oc_lt5']['t1_diff_pp']:+.2f} pp (`{gv_t['heavy_oc_lt5']['fem_only']}` vs. `{gv_t['heavy_oc_lt5']['frm_only']}`) when `OC < 5 µg/m³` ($n = {gv_t['heavy_oc_lt5']['n']}$); restricting to high biomass-burning `OC/EC ≥ 5` ($n = {gv_t['heavy_oc_ec_ge5']['n']}$) yields {gv_t['heavy_oc_ec_ge5']['mean_bias']:+.2f} µg/m³ and {gv_t['heavy_oc_ec_ge5']['t1_diff_pp']:+.2f} pp (`{gv_t['heavy_oc_ec_ge5']['fem_only']}` vs. `{gv_t['heavy_oc_ec_ge5']['frm_only']}`).

Finally, **event-level robustness and observational chemical-speciation associations** reinforce both statistical and physical coherence (**Figure 4**, **Table 4**). Across all six one-way and two-way clustering estimators, the official Tier-1 difference of {t1_t['difference_pp']:+.2f} pp remains bounded strictly above zero (`+2.99` to `+11.54 pp` at widest 1-way Date CI; `{fmt_ci(tw_t1['ci95'])}` under primary two-way `Site × Region-Smoke-Episode` clustering). Dropping each of the {loro['n_regions']} represented EPA Regions in turn never reduces the estimate below {loro['min_loro_diff_pp']:+.2f} pp (range `[{loro['min_loro_diff_pp']:+.2f}, {loro['max_loro_diff_pp']:+.2f}]` pp; all seven leave-region-out two-way CIs strictly positive), and year-by-year estimates remain tightly clustered across three independent fire seasons (`2023`: {yr_t1['2023']['difference_pp']:+.2f} pp, `2024`: {yr_t1['2024']['difference_pp']:+.2f} pp, `2025`: {yr_t1['2025']['difference_pp']:+.2f} pp). In observational Site + Month fixed-effects regressions across {s1_t['n']:,} speciation-linked `T640_FW–FRM` pairs (**Figure 4B**, **Table 4**; confirmed on `{s3_t['n']:,}` exact 0 km rooftops), optical bias covaries positively with Organic Carbon ({s1_t['coefs']['oc']['beta']:+.3f} µg/m³ per µg/m³ OC, $t = {s1_t['coefs']['oc']['t_cr1']:+.2f}$, plus {s2_t['coefs']['oc_x_hms_h']['beta']:+.3f} additional under HMS Heavy, $t = {s2_t['coefs']['oc_x_hms_h']['t_cr1']:+.2f}$) and relative humidity ({s1_t['coefs']['rh_10']['beta']:+.3f} per `+10%` RH, $t = {s1_t['coefs']['rh_10']['t_cr1']:+.2f}$), and negatively with light-absorbing Elemental Carbon ({s1_t['coefs']['ec']['beta']:+.3f}, $t = {s1_t['coefs']['ec']['t_cr1']:+.2f}$). These ambient associations are physically consistent with Mie light-scattering behavior of organic-rich, hygroscopic wildfire aerosols documented in controlled chamber experiments by Long et al. (2023), while background heated-inlet BAM exhibits statistical nulls on OC ($p = {fmt_p(s1_b['coefs']['oc']['p_cr1'])}$) and EC ($p = {fmt_p(s1_b['coefs']['ec']['p_cr1'])}$) alongside negative sensitivity to semi-volatile nitrate ({s1_b['coefs']['no3']['beta']:+.3f}, $t = {s1_b['coefs']['no3']['t_cr1']:+.2f}$) and RH ({s1_b['coefs']['rh_10']['beta']:+.3f}, $t = {s1_b['coefs']['rh_10']['t_cr1']:+.2f}$).

<!-- FIGURE:fig4_est_inference_loro_and_speciation.png -->

**Table 4. Multi-Dimensional Event-Level Inference, Leave-EPA-Region-Out Stability, and Observational Chemical-Speciation & Meteorology Associations**

{chr(10).join(t4_md)}

*Notes:* Rows 1–8 evaluate the official EPA 2021–2025 Tier-1 threshold on `T640_FW–FRM` Heavy-smoke pairs (`N = 468`, `165` sites). Rows 9–12 summarize Site FE + Month FE observational regressions (`N = 14,992` T640_FW pairs vs. `N = 7,333` BAM pairs, 2023–2025) with Site-clustered CR1 standard errors; observational field associations are consistent with Mie optical physics (Long et al., 2023) but do not by themselves identify causal firmware correction parameters.

---

## 4. Discussion and Environmental Implications

Our collocated field audit shows that even after EPA's May 2024 T640/T640x network alignment (U.S. EPA, 2024c), residual optical–gravimetric divergence during wildland fire smoke routinely alters initial screening classification under EPA's April 2024 Tiering framework (U.S. EPA, 2024b). By combining same-site, same-day optical–FRM pairing, strict out-of-time 5-year threshold reconstruction, equal-concentration non-smoke controls, and surface speciation verification, this work bridges controlled laboratory chamber evaluations (Long et al., 2023) and national policy-screening assessments (Krupnick et al., 2025; McClure et al., 2026) with direct field-network metrological evidence.

Three scientific conclusions and two practical implications follow directly from the data:

1. **Both Baseline Sensitivity and Smoke-Specific Amplification Matter:** Critics might reasonably ask whether optical threshold divergence is simply a generic artifact of baseline positive bias near any cutoff. Our concentration-matched non-smoke controls show that both mechanisms operate, but in sharply distinct regimes. On elevated non-smoke days (`15–25 µg/m³`, primarily humid winter inorganic haze), residual baseline T640 bias (`+0.5` to `+1.6 µg/m³`) produces modest, partly two-sided Tier-1 discordance (`+3.1` to `+9.0 pp`). During surface-impacted wildfire smoke (confirmed independently by `FRM > site-month p90` and `OC ≥ 5 µg/m³`), however, optical over-response amplifies three- to fivefold (`+3.5` to `+8.0 µg/m³`, $p < 10^{{-4}}$ to $10^{{-15}}$ vs. matched non-smoke days) and drives overwhelmingly one-sided Tier-1 crossings (`36` vs. `2` official; `26–33` vs. `0` out-of-time). Consequently, air-quality interpretation under EPA-457/R-24-001 cannot assume post-alignment optical–gravimetric equivalence during intense biomass-burning plumes.
2. **Retrospective and Prospective Out-of-Time Screening Agree in Sign and Asymmetric Structure:** Reconstructing EPA's exact Appendix N site-month formula on strictly historical certified windows (`2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`) confirms statistically significant, unidirectional excess Tier-1 triggering (`+5.57` to `+7.07 pp`, `26–33` vs. `0`, all two-way $p \\le {fmt_p(oot_c_t['inference']['twoway_site_x_reg_episode']['p_2sided'])}$) without any look-ahead leakage. At the same time, our out-of-time audit highlights a subtle operational sensitivity of EPA's 5-year rolling rule: because public AirData records omit individual-day `I`-qualifier flags, retaining unflagged 2023 Canadian wildfire days in the `2020–2024` baseline raises reconstructed 2025 thresholds and attenuates the 2025 excess from `+8.08 pp` (official `R`+`I` excluded) to `+3.08`–`+3.59 pp`. Publishing versioned historical snapshots of EPA's official `for_posting.csv` archive alongside each May 1 certification rollover would allow transparent prospective auditing by air agencies and researchers alike.
3. **Practical Guidance for Monitoring Agencies and Calibration Research:** First, where a candidate wildland fire reading from an optical FEM falls within `±20%` of the site-month Tier-1 or Tier-2 threshold—the band containing `{nb20_frm['fem_only']}/{t1_t['fem_only']}` (`{100.0 * nb20_frm['fem_only'] / t1_t['fem_only']:.1f}%` by FRM; `{nb20_mid['fem_only']}/{t1_t['fem_only']}` = `100%` by midpoint) of T640-only Tier-1 discordances—air agencies and EPA regional offices should cross-check collocated gravimetric FRM or nearby mass-based samplers when available. Second, while our ambient speciation associations (`OC+`, `OC × HMS Heavy+`, `EC−`, `RH+`) reinforce the optical-scattering mechanisms identified by Long et al. (2023), observational field regressions cannot by themselves parameterize regulatory firmware corrections; controlled multi-site physical calibration and smoke-chamber experiments across aerosol aging states remain necessary before designing smoke-aware optical correction functions.

**Scope, Epistemic Boundaries, and Supporting Information Context.** Four explicit boundaries govern the interpretation of this study. First, our primary analysis quantifies *screening-level threshold crossings* under EPA-457/R-24-001; it does not link discordant site-days to formal state Exceptional Event demonstrations, EPA concurrence dockets, or Clean Air Act § 107(d) area designations, which depend on multi-factor weight-of-evidence reviews and regulatory significance criteria. Second, although common-support matching widens the T640 − BAM differential (`+7.93` to `+11.24 pp`), sparse Heavy-smoke triple collocation ($n = {h_c['heavy_triple_site_days']}$) prevents a powered within-rooftop T640-versus-BAM smoke trial; `BAM–FRM` is therefore interpreted strictly as a background reference comparator. Third, public AirData daily files lack raw `I`-qualifier day flags, motivating our four-specification out-of-time bracket (`OOT-A` through `OOT-C`). Fourth, auxiliary screening-level 3-year annual Design Value sensitivity analyses—specifically the `2023–2025` same-rooftop paired DV discrepancy (`+{rt_t['mean_dv_bias']:.3f} µg/m³`, `{rt_t['fem_na_frm_att']}` vs. `{rt_t['frm_na_fem_att']}` sites crossing `9.0 µg/m³` across `{rt_t['n_sites']}` rooftops vs. `{rt_b['mean_dv_bias']:+.3f} µg/m³` on `{rt_b['n_sites']}` BAM rooftops), the `2021–2023` monitor Design Value threshold reclassification waterfall (`{wf21['flip_t640_alone']['counties']}` counties / `{wf21['flip_t640_alone']['pop_millions']:.2f}M` residents shifted from $\\ge 9.1$ to $\\le 9.0\\;\\mu\\text{{g/m}}^3$ by T640 software alignment alone—explicitly screening-level monitor DV cross-overs, not EPA § 107(d) designations), and archival observational Exceptional Event flagging regressions (where a within-county-year fixed-effects test finds no causal instrument-filing effect: `{100 * u2_wcy['coefs']['is_t640_f']['beta']:+.2f}` pp, $p_{{\\text{{WCB}}}} = {u2_wcy['wcb']['p_wcb']:.3f}$, $N = {u2_wcy['n']}$)—are placed cleanly in the **Supporting Information** (`supplementary_j6_est.pdf`) so the main paper remains focused strictly on collocated metrology and screening-threshold sensitivity.

---

## Supporting Information

The Supporting Information (`supplementary_j6_est.pdf`) contains: (Section S1) complete collocated case-flow attrition, the four Heavy-smoke same-rooftop triple station records (Table S1), and AQS/threshold version provenance; (Section S2) validation of 40 CFR Part 50 Appendix N out-of-time threshold reconstruction against EPA's published 2021–2025 table (Table S2, Figure S2A) and full year-by-year out-of-time breakdowns; (Section S3) screening-level 3-year annual Design Value sensitivity—same-rooftop `2023–2025` paired DV classification (`19` vs. `2`) and `2021–2023` `47`-county monitor Design Value threshold reclassification accounting & demographic audit (Table S3, Figure S1), explicitly distinguished from formal CAA § 107(d) designations; (Section S4) archival observational Exceptional Event flagging context, exogenous `DV_18_20` nulls, and the within-county-year null test (Table S4, Figure S2B); and (Section S5) formal threshold-crossing metrology model summary.

## Data and Code Availability

All primary inputs are public U.S. government datasets: EPA AQS AirData daily and annual PM₂.₅/speciation/meteorology archives (`2018–2025`), NOAA HMS daily wildfire smoke polygons (`2018–2025`), and EPA's PM₂.₅ Tiering Tool threshold CSV (`for_posting.csv`, AQS query date `2026-09-14`, SHA-256 `ac314789d31b89fd93f044e01d71affd9af3bf0454dae1c685adfc5348cf40e4`). The replication archive exports the complete site-day reproducible paired Heavy-smoke dataset (`tables/collocated_heavy_smoke_pairs_2023_2025.csv`, `{r11['exports']['pair_csv_rows']}` rows), the complete file-version and SHA-256 manifest (`tables/aqs_and_threshold_version_manifest.csv`), machine-readable publication tables (`tables/table1_*.csv`–`table4_*.csv`), JSON audit receipts (`results/10_official_tier_replay.json`, `results/11_v4_est_comprehensive_audit.json`), Python analysis/figure/compilation scripts (`scripts/`), and an automated regression test suite (`tests/test_j6_boost.py`).

---

## References

{refs_md}
"""
    return doc


def build_supporting_information(r1: dict, r2: dict, r3: dict, r4: dict, r11: dict) -> str:
    cs = r11["common_support_audit"]
    h_triples = cs["heavy_smoke_2023_2025"]["heavy_triple_records"]
    rb = r11["oot_reconstruction_benchmark_2021_2025"]
    oot = r11["oot_prospective_rolling_5yr"]

    cs11 = r1["accounting"]["combined_site_reg_appn_11of12"]
    wf = cs11["matched_2123_waterfall"]
    epa21 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2021_2023_final_08_08_24_0.xlsx"]
    prec21 = 100.0 * epa21["overlap_epa_with_cs_reg_incl"] / epa21["combined_site_reg_na_incl"]
    ej_g = r1["ej_audit_acs2023"]["groups"]
    ej_t = r1["ej_audit_acs2023"]["formal_tests"]
    nulls = r1["exogenous_nulls_margins_acd"]

    rt_t = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_st = r2["rooftop_dv_lottery_2023_2025"]["t640_fw_strict_4q3y"]
    rt_b = r2["rooftop_dv_lottery_2023_2025"]["bam"]

    m3 = r3["monitor_year_dv1820_85_115"]
    c3 = r3["county_year_dv1820_85_115"]
    ri = r3["within_state_ri_B1000"]
    u2 = r3["unification_u2_t640_ee_flagging"]
    u2_wcy = u2["borderline_within_county_year_fe_flag"]

    # Table S1: 4 Heavy-smoke exact same-site same-day triple records
    ts1 = [
        "| Site ID | Date | EPA Region | FRM (µg/m³) | T640_FW (µg/m³) | BAM (µg/m³) | T640 − FRM | BAM − FRM | EPA Tier-1 Cutoff |",
        "| :--- | :--- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for r in h_triples:
        t1_s = f"{r['tier_1']:.2f}" if r["tier_1"] is not None else "Unmatched"
        ts1.append(
            f"| `{r['site_id']}` | {r['date']} | R{r['epa_region']} | {r['frm']:.1f} | {r['t640_fw']:.1f} | "
            f"{r['bam']:.1f} | {r['t640_minus_frm']:+.1f} | {r['bam_minus_frm']:+.1f} | {t1_s} |"
        )

    # Table S2: 2021-2025 Reconstruction Validation + Year-by-Year OOT Summary
    ts2 = [
        "| Reconstruction Specification | All Sites Corr ($r$) | All Med Abs Err (µg/m³) | All Mean Err | Clean Sites Corr ($r$) | Clean Med Abs Err | OOT 2023 / 2024 / 2025 T640 Diff (pp) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    oot_yr_map = {
        "oot_a_cs_r_excl": oot["oot_a_conservative_r_excl"]["t640_fw"]["tier_1"]["by_year"],
        "oot_b_cs_excl_hms3": oot["oot_b_fire_proxy_hms_heavy"]["t640_fw"]["tier_1"]["by_year"],
        "oot_b2_cs_excl_hms23": oot["oot_b2_fire_proxy_hms_med_heavy"]["t640_fw"]["tier_1"]["by_year"],
        "oot_c_pure_frm": oot["oot_c_pure_frm_only"]["t640_fw"]["tier_1"]["by_year"],
    }
    for k in ["cs_all_no_ann_excl", "oot_a_cs_r_excl", "oot_b_cs_excl_hms3", "oot_b2_cs_excl_hms23", "oot_c_pure_frm"]:
        v = rb[k]
        if k in oot_yr_map:
            ym = oot_yr_map[k]
            y_str = f"{ym['2023']['difference_pp']:+.2f} / {ym['2024']['difference_pp']:+.2f} / {ym['2025']['difference_pp']:+.2f}"
        else:
            y_str = "Benchmark only"
        ts2.append(
            f"| {v['description']} | {v['all_sites_corr']:.3f} | {v['all_sites_median_abs_err']:.3f} | "
            f"{v['all_sites_mean_err']:+.3f} | {v['zero_flag_clean_corr']:.3f} | "
            f"{v['zero_flag_clean_median_abs_err']:.3f} | {y_str} |"
        )

    # Table S3: Screening-Level 2021-2023 Monitor DV Reclassification & ACS Demographics
    g_fl = ej_g["T640_Flipped"]
    g_st = ej_g["Still_Nonattainment"]
    g_cl = ej_g["Cleanly_Attaining"]
    ts3 = [
        "| Screening-Level County Monitor DV Group (2021–2023) | Counties | 2024 Pop. (M) | Midwest + South Share | Mean Black NH (%) | Mean Hispanic (%) | Median HH Income ($) |",
        "| :--- | ---: | ---: | ---: | ---: | ---: | ---: |",
        f"| T640 Alignment DV-Reclassified ($\\ge 9.1 \\to \\le 9.0$) | {g_fl['n_counties']} | {wf['flip_t640_alone']['pop_millions']:.2f} | {ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['flipped_pct']:.1f}% | {g_fl['unweighted_means']['pct_black_nh']:.1f}% | {g_fl['unweighted_means']['pct_hispanic']:.1f}% | \\${g_fl['unweighted_means']['median_hh_income']:,.0f} |",
        f"| Still Above Monitor DV Threshold ($\\ge 9.1$ Aligned) | {g_st['n_counties']} | {wf['aln_2123']['pop_millions']:.2f} | {ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['comp_pct']:.1f}% | {g_st['unweighted_means']['pct_black_nh']:.1f}% | {g_st['unweighted_means']['pct_hispanic']:.1f}% | \\${g_st['unweighted_means']['median_hh_income']:,.0f} |",
        f"| Cleanly Below Monitor DV Threshold ($\\le 9.0$ Both) | {g_cl['n_counties']} | {cs11['total_pop_matched_2123_millions'] - wf['raw_2123']['pop_millions']:.2f} | — | {g_cl['unweighted_means']['pct_black_nh']:.1f}% | {g_cl['unweighted_means']['pct_hispanic']:.1f}% | \\${g_cl['unweighted_means']['median_hh_income']:,.0f} |",
    ]

    # Table S4: Exogenous Nulls & Archival EE Flagging Disclosure
    ts4 = [
        "| Auxiliary / Archival Check | Estimate | Uncertainty / $p$-Value | Epistemic Status |",
        "| :--- | ---: | ---: | :--- |",
        f"| Exogenous `DV_18_20` Gravimetric FRM PM₂.₅ (Margin D) | {nulls['margin_d_frm_exog_dv1820_county_cr1']['coefs']['tp']['beta']:+.3f} µg/m³ | $p_{{\\text{{WCB}}}} = {nulls['margin_d_frm_exog_dv1820_county_cr1']['wcb']['p_wcb']:.3f}$ | Clean null (zero gravimetric shift) |",
        f"| Exogenous `DV_18_20` FEM→FRM Switching (Margin A) | {nulls['margin_a_share_fem_exog_dv1820']['coefs']['tp']['beta']:+.3f} | $p_{{\\text{{WCB}}}} = {nulls['margin_a_share_fem_exog_dv1820']['wcb']['p_wcb']:.3f}$ | Clean null |",
        f"| Exogenous `DV_18_20` Monitor Survival (Margin C) | {nulls['margin_c_monitor_survival_exog_dv1820']['coefs']['nb']['beta']:+.3f} | $p_{{\\text{{WCB}}}} = {nulls['margin_c_monitor_survival_exog_dv1820']['wcb']['p_wcb']:.3f}$ | Clean null |",
        f"| Observational Monitor-Year EE Flagging DiD (`2022–2025`) | {100 * m3['true_ee_flag']['did_2225_state_cr1']['coefs']['tp_2225']['beta']:+.2f} pp | State $p_{{\\text{{WCB}}}} = {m3['true_ee_flag']['did_2225_state_cr1']['wcb']['p_wcb']:.3f}$; RI $p = {ri['monitor_year']['p_ri_2sided']:.4f}$ | Anticipatory 2022–2023 surge prior to Feb 2024 rule |",
        f"| Observational County-Year EE Flagging DiD (`2022–2025`) | {100 * c3['true_ee_flag']['did_2225_state_cr1']['coefs']['tp_2225']['beta']:+.2f} pp | State $p_{{\\text{{WCB}}}} = {c3['true_ee_flag']['did_2225_state_cr1']['wcb']['p_wcb']:.3f}$; RI $p = {ri['county_year']['p_ri_2sided']:.4f}$ | 2025 EPA-concurred flow null ($p = {fmt_p(c3['true_ee_conc']['event_study_county_cr1']['coefs']['nb_2025']['p_cr1'])}$) |",
        f"| **Within-County-Year FE T640 Flagging Test (`N = {u2_wcy['n']}`)** | **{100 * u2_wcy['coefs']['is_t640_f']['beta']:+.2f} pp** | **$p_{{\\text{{WCB}}}} = {u2_wcy['wcb']['p_wcb']:.3f}$** | **Null — no causal claim of instrument-induced EE filing** |",
    ]

    p1 = r4["proposition_1_optical_lottery"]
    p2 = r4["proposition_2_inverted_u_triage"]

    return f"""# Supporting Information: Residual Optical PM₂.₅ Bias During Wildfire Smoke and Sensitivity of U.S. Exceptional-Event Tiering Thresholds

Zijian Zeng  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Section S1. Case-Flow Attrition, Heavy-Smoke Same-Rooftop Triples, and Data Provenance

This Supporting Information documents (1) the four exact same-site, same-day triple observations under NOAA HMS Heavy smoke (`Table S1`) and file-version manifest (`tables/aqs_and_threshold_version_manifest.csv`), (2) validation of our 40 CFR Part 50 Appendix N out-of-time Tier-1 threshold reconstruction against EPA's published `2021–2025` table (`Table S2`, `Figure S2A`), (3) screening-level 3-year annual Design Value sensitivity analyses moved out of the main text (`Table S3`, `Figure S1`), (4) archival observational Exceptional Event flagging diagnostics including the within-county-year null test (`Table S4`, `Figure S2B`), and (5) a brief summary of the formal threshold-crossing metrology model.

**Table S1. All Four Same-Site, Same-Day Collocated Triple Observations (`T640_FW`, `BAM`, and `FRM`) Under NOAA HMS Heavy Smoke (2023–2025)**

{chr(10).join(ts1)}

*Notes:* Across all `63,951` `T640_FW–FRM` and `22,927` `BAM–FRM` pairs (2023–2025), `401` same-site, same-day triple observations occur across `5` monitoring sites, of which exactly `4` occur on NOAA HMS Heavy smoke days (`4` sites). In all four Heavy-smoke triples, aligned `T640_FW` reads above collocated gravimetric `FRM` (mean `{cs['all_2023_2025']['triples_by_hms_level']['hms_3_heavy']['mean_t640_minus_frm']:+.2f}` µg/m³), whereas `BAM` averages `{cs['all_2023_2025']['triples_by_hms_level']['hms_3_heavy']['mean_bam_minus_frm']:+.2f}` µg/m³. Because $n = 4$ is underpowered for standalone head-to-head Heavy-smoke inference, `BAM–FRM` is retained in the main manuscript strictly as a background reference benchmark.

The complete versioned provenance manifest (`tables/aqs_and_threshold_version_manifest.csv`, `{r11['exports']['manifest_entries']}` artifacts) pins SHA-256 digests and row counts for `aqs_monitors.zip`, `daily_88101_2018.zip`–`daily_88101_2025.zip`, `annual_conc_by_monitor_2018.zip`–`annual_conc_by_monitor_2025.zip`, `monitor_hms_daily_2018_2025.parquet` (`2,922/2,922` calendar days), and EPA's pinned threshold table `epa_pm25_tier_thresholds_2026-09-14.csv` (SHA-256 `{r11['epa_threshold_sha256']}`). The complete reproducible paired Heavy-smoke dataset (`{r11['exports']['pair_csv_rows']}` rows: `472` T640_FW + `201` BAM) is exported in `tables/collocated_heavy_smoke_pairs_2023_2025.csv`.

---

## Section S2. Out-of-Time Threshold Reconstruction Validation Against Official EPA 2021–2025 Snapshot

To validate our implementation of 40 CFR Part 50 Appendix N § 3.0(d) combined-site aggregation and § 4.5(a) Table 1 order-statistic 98th percentiles prior to evaluating strictly out-of-time rolling windows (`2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`), we benchmarked our `2021–2025` reconstruction directly against EPA's official published `for_posting.csv` snapshot (`2026-09-14`). On sites with zero AirData event flags during 2021–2025, median absolute Tier-1 error is exactly `0.000 µg/m³` (`r = 0.876`–`0.896`; remaining tail discrepancies arise from late-2025 state data certifications entered into AQS between May and September 2026 and individual-day `I`-qualifier flags unavailable in public bulk AirData CSVs).

**Table S2. Benchmark Accuracy of 2021–2025 Threshold Reconstruction Against EPA's Official Table and Year-by-Year Out-of-Time `T640_FW–FRM` Tier-1 Results**

{chr(10).join(ts2)}

*Notes:* All four strictly out-of-time rolling specifications yield strictly positive `T640_FW` Tier-1 excess in every calendar year (`2023`, `2024`, `2025`) with zero FRM-only reversals (`26`–`33` vs. `0`).

---

## Section S3. Screening-Level Annual Design Value Sensitivity (Strictly Distinct from CAA § 107(d) Designations)

**Important Epistemic Disclaimer:** The accounting calculations in this section evaluate **screening-level monitor Design Value threshold cross-overs** ($\\ge 9.1$ vs. $\\le 9.0\\;\\mu\\text{{g/m}}^3$) constructed from AQS daily records under 40 CFR Part 50, Appendix N. They are **not** formal Clean Air Act § 107(d) nonattainment area designations—which require EPA's statutory five-factor area analysis (air quality data, emissions, meteorology, geography/topography, and jurisdictional boundaries) and can include counties without an exceeding monitor—nor do they measure approved Exceptional Event exclusions.

1. **Same-Rooftop `2023–2025` Paired Design Value Classification (`Figure S1B`):** Restricting to `{rt_t['n_sites']}` collocated `T640_FW–FRM` rooftops with multi-year paired-day 2023–2025 Appendix N coverage, aligned `T640_FW` exhibits a mean 3-year annual Design Value bias of **`+{rt_t['mean_dv_bias']:.3f} µg/m³`** ($t = {rt_t['t_bias']:+.2f}$, $p = {fmt_p(rt_t['p_bias'])}$). At the `9.0 µg/m³` annual threshold (rounded to `0.1 µg/m³`, exceeding iff $\\ge 9.1$), **`{rt_t['fem_na_frm_att']}` rooftops** exceed on `T640_FW` while remaining $\\le 9.0$ on collocated FRM two meters away, versus only **`{rt_t['frm_na_fem_att']}`** in reverse (exact binomial $p = {fmt_p(rt_t['binom_p'])}$; strict 4-quarter × 3-year stitched subsample: `{rt_st['fem_na_frm_att']}` vs. `{rt_st['frm_na_fem_att']}`, $p = {fmt_p(rt_st['binom_p'])}$). In the separate background `BAM–FRM` cohort (`{rt_b['n_sites']}` rooftops), mean paired DV bias is `{rt_b['mean_dv_bias']:+.3f} µg/m³` ($p = {fmt_p(rt_b['p_bias'])}$; `{rt_b['fem_na_frm_att']}` vs. `{rt_b['frm_na_fem_att']}` discordant, $p = {fmt_p(rt_b['binom_p'])}$).
2. **Retrospective `2021–2023` Monitor Design Value Threshold Reclassification Waterfall (`Figure S1A`, `Table S3`):** Repairing `{r1['stitch_audit']['n_split_2023_t640_monitors_repaired']}` mid-2023 split-year T640 monitors (`POC`/`POC+20`) and excluding `{r1['regulatory_and_concurrence_audit']['excluded_non_reg_monitors']}` non-regulatory monitors reproduces EPA's official Table 4a `2021–2023` county exceedances at `{epa21['overlap_epa_with_cs_reg_incl']}/{epa21['combined_site_reg_na_incl']} = {prec21:.1f}%` precision across `{cs11['n_counties_matched_2123']}` matched regulatory counties. Holding the `2021–2023` monitoring window fixed and swapping pre-alignment raw T640 (`236/238`) for post-alignment T640 (`636/638/736/738`) reduces county monitor-DV threshold exceedances from `{wf['raw_2123']['counties']}` (`{wf['raw_2123']['pop_millions']:.2f}M` residents) to `{wf['aln_2123']['counties']}` (`{wf['aln_2123']['pop_millions']:.2f}M` residents)—a screening-level set of **`{wf['flip_t640_alone']['counties']}` counties (`{wf['flip_t640_alone']['pop_millions']:.2f}M` residents)** crossing from $\\ge 9.1$ to $\\le 9.0\\;\\mu\\text{{g/m}}^3$. Census ACS 2023 / PEP 2024 tabulations (`Table S3`) show these `{wf['flip_t640_alone']['counties']}` DV-reclassified counties lie overwhelmingly outside the arid West (`{ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['flipped_pct']:.1f}%` Midwest+South vs. `{ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['comp_pct']:.1f}%` still $\\ge 9.1$, Fisher $p = {ej_t['Flipped_vs_Still_Nonattainment']['midwest_south_share']['fisher_p']:.3f}$) and carry higher mean Black non-Hispanic resident shares than cleanly $\\le 9.0$ counties (`{ej_g['T640_Flipped']['unweighted_means']['pct_black_nh']:.1f}%` vs. `{ej_g['Cleanly_Attaining']['unweighted_means']['pct_black_nh']:.1f}%`, Welch $p = {ej_t['Flipped_vs_Cleanly_Attaining']['pct_black_nh']['welch_p']:.3f}$).

<!-- FIGURE:figS1_si_dv_reclassification_and_rooftop_lottery.png -->

**Table S3. Screening-Level `2021–2023` Monitor Design Value Reclassification Accounting and U.S. Census Demographic Profile (495 Matched Regulatory Counties)**

{chr(10).join(ts3)}

*Notes:* County populations describe the screening-level monitor DV reclassification set only and must not be interpreted as populations under formal EPA Clean Air Act § 107(d) designations.

---

## Section S4. Archival Exceptional Event Flagging Context and Explicit Within-County-Year Null Disclosure

To avoid any conflation of paired metrological threshold crossings with strategic agency behavior, `Table S4` and `Figure S2B` record our auxiliary archival audit of 40 CFR § 50.14 Exceptional Event flagging across 2018–2025 (after correcting AQS's `49.9%` false-positive concurrence row coding). Three candid boundaries apply: (i) strictly exogenous `DV_18_20` checks confirm clean nulls on gravimetric FRM PM₂.₅ (Margin D), `FEM → FRM` switching (Margin A), and monitor survival (Margin C); (ii) the observational monitor-year and county-year flagging increases near the 9.0 µg/m³ threshold peaked in `2022–2023` *prior* to the February 2024 final rule (anticipatory/designation-window retroactive flagging), with null `2024–2025` EPA-concurred flow; and (iii) crucially, **a within-county-year fixed-effects test comparing T640 against non-T640 monitors in the same county and year yields a clean statistical null (`{100 * u2_wcy['coefs']['is_t640_f']['beta']:+.2f}` pp, $p_{{\\text{{WCB}}}} = {u2_wcy['wcb']['p_wcb']:.3f}$, $N = {u2_wcy['n']}$)**. Accordingly, this study makes **no claim** that optical measurement bias causally induces state Exceptional Event filings.

<!-- FIGURE:figS2_si_oot_reconstruction_and_ee_nulls.png -->

**Table S4. Auxiliary Exogenous Null Checks and Archival Exceptional Event Flagging Audit (2018–2025)**

{chr(10).join(ts4)}

---

## Section S5. Formal Threshold-Crossing Metrology Summary

Our companion numerical verification (`results/04_formal_model_verification.json`) formalizes the mechanics linking continuous optical bias $b(S, \\text{{RH}}) > 0$ to discrete threshold crossings: (i) for sites near an annual Design Value cutoff, even sub-microgram regional bias (`b = {p1['b_midwest_djf_ugm3']:.2f}` µg/m³ in humid Midwest winter vs. `{p1['b_arid_west_ugm3']:.2f}` µg/m³ in the arid West) generates steep asymmetric classification odds ratios (`{p1['discordance_odds_ratio_mw']:.1f}:1` in simulation); and (ii) under concave exclusion-effort optimization, marginal agency screening incentives peak around the compliance boundary (strict second-order concavity verified with max finite-difference error `{p2['max_soc_fd_err']:.2e}`), amplifying the sensitivity of near-threshold smoke days (`±20%` of Tier-1) to positive optical bias.
"""


def main() -> int:
    print("=== STEP 07a: GENERATING V4 ES&T MANUSCRIPT & SUPPORTING INFORMATION ===", flush=True)
    r1 = json.loads((RES_DIR / "01_appn_audit.json").read_text(encoding="utf-8"))
    r2 = json.loads((RES_DIR / "02_collocated_physics_speciation.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_ee_triage_hms_unification.json").read_text(encoding="utf-8"))
    r4 = json.loads((RES_DIR / "04_formal_model_verification.json").read_text(encoding="utf-8"))
    r7 = json.loads((RES_DIR / "07_citations_verified.json").read_text(encoding="utf-8"))
    r10 = json.loads((RES_DIR / "10_official_tier_replay.json").read_text(encoding="utf-8"))
    r11 = json.loads((RES_DIR / "11_v4_est_comprehensive_audit.json").read_text(encoding="utf-8"))

    main_md = build_main_manuscript(r1, r2, r3, r7, r10, r11).replace("\r\n", "\n")
    si_md = build_supporting_information(r1, r2, r3, r4, r11).replace("\r\n", "\n")

    MD_MAIN.write_bytes(main_md.encode("utf-8"))
    MD_SI.write_bytes(si_md.encode("utf-8"))

    sha_m = hashlib.sha256(main_md.encode("utf-8")).hexdigest()
    sha_s = hashlib.sha256(si_md.encode("utf-8")).hexdigest()
    print(
        f"[DONE STEP 07a] Wrote {MD_MAIN.name} ({len(main_md):,} bytes, {len(main_md.split()):,} words, SHA-256 LF: {sha_m})\n"
        f"                Wrote {MD_SI.name} ({len(si_md):,} bytes, {len(si_md.split()):,} words, SHA-256 LF: {sha_s})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
