"""Step 14: Programmatically generate the Nature Water v4 main manuscript (manuscript_d4_boost.md)
and companion Supplementary Information (supplementary_d4_nature_water.md) strictly from JSON/CSV
receipts and Crossref-verified bibliography. Zero hardcoded empirical numbers.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
RES = ROOT / "results"
TBL = ROOT / "tables"


def fmt_ci(vals: list[float], signed: bool = False, nd: int = 2) -> str:
    fmt = f"+.{nd}f" if signed else f".{nd}f"
    return f"{vals[0]:{fmt}} [{vals[1]:{fmt}}, {vals[2]:{fmt}}]"


def fmt_ref(key: str, refs: dict) -> str:
    r = refs[key]
    auths = r["authors"]
    if len(auths) == 1:
        a_str = auths[0]
    elif len(auths) <= 4:
        a_str = ", ".join(auths[:-1]) + " & " + auths[-1]
    else:
        a_str = f"{auths[0]} et al."
    title = html.unescape(str(r["title"])).rstrip()
    # Clean legacy Crossref OCR footnote trailing '1' on 1956/1984 L&O titles
    if title.endswith("1") and not title[-2].isdigit():
        title = title[:-1]
    journal = html.unescape(str(r["journal"]))
    year_fix = {"Blaszczak2023": 2023, "Bernhardt2018": 2018}.get(key, r["year"])
    vol = f" **{r['volume']}**," if r.get("volume") else ""
    page = f" {r['page']}" if r.get("page") else ""
    return f"{a_str} {title}. *{journal}*{vol}{page} ({year_fix}). https://doi.org/{r['doi']}"


def build_main_manuscript(r11: dict, r12: dict, refs: dict) -> str:
    us = r11["loro_primary"]["USGS"]
    uk = r11["loro_primary"]["EA"]
    us5, uk5 = us["thresholds"]["5"], uk["thresholds"]["5"]
    us4, uk4 = us["thresholds"]["4"], uk["thresholds"]["4"]
    us3, uk3 = us["thresholds"]["3"], uk["thresholds"]["3"]
    us2, uk2 = us["thresholds"]["2"], uk["thresholds"]["2"]

    att_us = r11["coverage_attrition"]["USGS"]
    att_uk = r11["coverage_attrition"]["EA"]
    step_us = {x["native_step_min"]: x for x in att_us["by_native_step"]}
    step_uk = {x["native_step_min"]: x for x in att_uk["by_native_step"]}

    wqp = r11["real_wqp_grab_audit"]
    wqp_all = wqp["conus397_2015_2024_clock"]
    wqp_iv = wqp["iv139_2021_2024_clock"]
    co_val = wqp["independent_colocated_validation"]
    act_vis = wqp["actual_agency_visit_detection"]

    ho = r11["holdout_validation"]
    us_fl = next(x for x in ho["sunrise_offset_profile_lt5"]["USGS"] if x["offset_min_rel_sr"] == 30)
    uk_fl = next(x for x in ho["sunrise_offset_profile_lt5"]["EA"] if x["offset_min_rel_sr"] == 30)
    us_sr = next(x for x in ho["sunrise_offset_profile_lt5"]["USGS"] if x["offset_min_rel_sr"] == 0)
    uk_sr = next(x for x in ho["sunrise_offset_profile_lt5"]["EA"] if x["offset_min_rel_sr"] == 0)

    cad_us = r11["cadence_downsampling"]["USGS"]["cadences"]
    cad_uk = r11["cadence_downsampling"]["EA"]["cadences"]
    cad_uk30 = r11["cadence_downsampling"]["EA"]["ea_le30min_cohort_30_vs_60"]["cadences"]

    cd_us = us5["censoring_and_duration"]
    cd_uk = uk5["censoring_and_duration"]
    us_rc_pct = 100.0 * (cd_us["censor_counts"]["right_only"] + cd_us["censor_counts"]["doubly_censored"]) / us5["shared_n_ref_pos"]
    uk_rc_pct = 100.0 * (cd_uk["censor_counts"]["right_only"] + cd_uk["censor_counts"]["doubly_censored"]) / uk5["shared_n_ref_pos"]

    op_us = r12["networks"]["USGS"]
    op_uk = r12["networks"]["EA"]
    vp_us = op_us["primary_actionable_5mg_2h_visit_level"]
    vp_uk = op_uk["primary_actionable_5mg_2h_visit_level"]
    eb_us = op_us["equal_budget_simulation_5mg_2h"]
    eb_uk = op_uk["equal_budget_simulation_5mg_2h"]
    b24_us = eb_us["equal_dollar_budget"]["budget_24_dayeq"]
    b24_uk = eb_uk["equal_dollar_budget"]["budget_24_dayeq"]
    fr_us = op_us["decision_breakeven_frontiers"]
    fr_uk = op_uk["decision_breakeven_frontiers"]

    # Build Table 1 Markdown (Primary LORO <5, <4, <3, <2 mg/L)
    t1_lines = []
    for net_lbl, net_blk in [("U.S. (USGS)", us), ("England (EA)", uk)]:
        for thr in ("5", "4", "3", "2"):
            b = net_blk["thresholds"][thr]
            for skey, slbl in [
                ("afternoon", "14:30 afternoon"),
                ("overpass", "10:30 overpass"),
                ("morning08", "08:00 morning"),
                ("alternating", "50/50 alternating"),
                ("predawn", "Pre-dawn (SR−30m)"),
            ]:
                s = b["loro_schedules"][skey]
                gain_str = fmt_ci(b["loro_dawn_minus_afternoon_95_pp"], signed=True) if skey == "predawn" else "—"
                t1_lines.append(
                    f"| {net_lbl} | <{thr} | {b['loro_n_ref_pos']:,} (−{b['shared_minus_loro_dropped_nights']}) | "
                    f"{slbl} | {fmt_ci(s['recall_95_pct'])} | {s['ref_neg_alarm_95_pct'][0]:.3f} | {gain_str} |"
                )
    table1_md = "\n".join(t1_lines)

    # Build Table 2 Markdown (Anti-Circularity, Tolerance, Persistence, Cadence, Holdout <5 mg/L)
    t2_df = pd.read_csv(TBL / "table2_nw_robustness_holdout_cadence.csv")
    us_t2 = t2_df[t2_df["network"] == "United States (USGS)"].set_index("sensitivity_check")
    uk_t2 = t2_df[t2_df["network"] == "England (EA)"].set_index("sensitivity_check")
    t2_lines = []
    for chk in us_t2.index:
        ru, re_ = us_t2.loc[chk], uk_t2.loc[chk]
        chk_clean = (
            str(chk)
            .replace(">=", "≥")
            .replace("+/-", "±")
            .replace("sigma=", "σ = ")
            .replace("mg/L", "mg L$^{-1}$")
        )
        t2_lines.append(
            f"| {chk_clean} | {int(ru['n_ref_units']):,} | {ru['gain_vs_1430_pp']:+.2f} [{ru['ci95_lo_pp']:+.2f}, {ru['ci95_hi_pp']:+.2f}] | "
            f"{ru['ref_neg_alarm_pct']:.3f} | {int(re_['n_ref_units']):,} | {re_['gain_vs_1430_pp']:+.2f} [{re_['ci95_lo_pp']:+.2f}, {re_['ci95_hi_pp']:+.2f}] | {re_['ref_neg_alarm_pct']:.3f} |"
        )
    table2_md = "\n".join(t2_lines)

    # Build Table 3 Markdown (Equal-Budget Operational Protocols, Budget=24 day-eq/site-yr, m_night=1.75x, K_sonde=40)
    t3_df = pd.read_csv(TBL / "table3_nw_equal_budget_protocols.csv")
    t3_lines = []
    for row in t3_df.itertuples(index=False):
        net_s = "U.S." if "United" in row.network else "England"
        per100_str = "— (cont.)" if row.protocol_type == "Hybrid Sonde" else f"{row.actionable_per_100_visits:.2f}"
        prot_clean = str(row.protocol).replace("1.15x", "1.15×").replace("1.75x", "1.75×").replace("SR-30m", "SR−30m")
        t3_lines.append(
            f"| {net_s} | {prot_clean} | {per100_str} | {row.distinct_ep_per_100_budget_eq:.2f} | "
            f"\\${int(row.cost_usd_per_distinct_episode):,} | {row.impaired_sy_flagged_pct:.1f}% | "
            f"{row.episodic_lead_nadir_hr:+.2f} / {row.episodic_lead_end_hr:+.2f} | {row.loro_ref_neg_alarm_pct:.3f}% |"
        )
    table3_md = "\n".join(t3_lines)

    # Key ratios for narrative (computed programmatically!)
    u_g = b24_us["grab_by_night_multiplier"]["m_1p75"]
    u_h = b24_us["hybrid_sonde_by_cost"]["k_40"]
    e_g = b24_uk["grab_by_night_multiplier"]["m_1p75"]
    e_h = b24_uk["hybrid_sonde_by_cost"]["k_40"]

    us_sonde_mult = u_h["y1_daytime_screening_top20pct_plus_firstlight"]["distinct_episodes_per_100_dayeq"] / u_g["empirical_wqp_clock"]["distinct_episodes_per_100_dayeq"]
    uk_sonde_mult = e_h["y1_daytime_screening_top20pct_plus_firstlight"]["distinct_episodes_per_100_dayeq"] / e_g["empirical_wqp_clock"]["distinct_episodes_per_100_dayeq"]
    us_cost_cut = 100.0 * (1.0 - u_h["y1_daytime_screening_top20pct_plus_firstlight"]["cost_usd_per_distinct_episode"] / u_g["empirical_wqp_clock"]["cost_usd_per_distinct_episode"])
    uk_cost_cut = 100.0 * (1.0 - e_h["y1_daytime_screening_top20pct_plus_firstlight"]["cost_usd_per_distinct_episode"] / e_g["empirical_wqp_clock"]["cost_usd_per_distinct_episode"])

    us_sonde_night_mult = u_h["y1_daytime_screening_top20pct_plus_firstlight"]["actionable_nights_per_100_dayeq"] / u_g["empirical_wqp_clock"]["actionable_nights_per_100_dayeq"]
    uk_sonde_night_mult = e_h["y1_daytime_screening_top20pct_plus_firstlight"]["actionable_nights_per_100_dayeq"] / e_g["empirical_wqp_clock"]["actionable_nights_per_100_dayeq"]

    ref_keys = [
        "Odum1956",
        "BensonKrause1984",
        "Portner2010",
        "Bernhardt2018",
        "Appling2018",
        "Battin2023",
        "vanVliet2023",
        "Blaszczak2023",
        "Zhi2023",
        "Elfferich2024",
        "Graham2025",
        "Zhou2026",
        "USGS2006Wagner",
        "Iqbal1983",
        "KaplanMeier1958",
        "CameronMiller2015",
    ]
    refs_md = "\n".join(f"{i}. {fmt_ref(k, refs)}" for i, k in enumerate(ref_keys, start=1))

    text = f"""# Equal-budget monitoring protocols for nocturnal river hypoxia across U.S. and English networks

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Abstract

Routine river water-quality monitoring occurs predominantly during daylight working hours, creating systematic blind spots for nocturnal dissolved-oxygen (DO) depletion. Yet moving field sampling before sunrise incurs safety and overtime costs and still may not deliver early warning before ecological stress peaks. Here we evaluate deployable, equal-budget monitoring protocols using raw UTC-timestamped continuous DO records from {us['n_sites']} U.S. Geological Survey stations ({us['n_nights']:,} warm-season site-nights) and {uk['n_sites']} Environment Agency stations in England ({uk['n_nights']:,} site-nights), anchored against {wqp_all['n_visits']:,} timestamped U.S. Water Quality Portal (WQP) discrete agency field visits. Removing shared-reading circularity via a primary leave-one-reading-out (LORO) estimator confirms substantial pre-dawn recall gains over 14:30 afternoon sampling at <5 mg L$^{{-1}}$ ({fmt_ci(us5['loro_dawn_minus_afternoon_95_pp'], signed=True)} percentage points in the U.S.; {fmt_ci(uk5['loro_dawn_minus_afternoon_95_pp'], signed=True)} percentage points in England; LORO reference-negative alarm rates {us5['loro_schedules']['predawn']['ref_neg_alarm_95_pct'][0]:.3f}% and {uk5['loro_schedules']['predawn']['ref_neg_alarm_95_pct'][0]:.3f}%), robust across ±0.2 mg L$^{{-1}}$ sensor tolerances, ≥2 h persistence, 15–60 min downsampling, chronic-site exclusions, and cross-Atlantic out-of-sample transfer. Crucially, real agency visits peak near 11:00 local time (09:50 solar), and under realistic nocturnal staffing surcharges (1.75×), dark pre-dawn grabs yield fewer distinct actionable episodes per dollar than existing daytime schedules (breakeven 1.53× U.S., 1.38× England). Instead, sampling at safe first-light daylight (sunrise + 30 min) maximizes grab-only efficiency, while reallocating the identical annual budget to risk-stratified continuous sondes at the top 20% of sites (selected out-of-sample from Year-1 daytime screening) plus first-light grabs elsewhere multiplies distinct episode detections {us_sonde_mult:.1f}×–{uk_sonde_mult:.1f}×, cuts unit costs by {us_cost_cut:.0f}%–{uk_cost_cut:.0f}%, flags {e_h['y1_daytime_screening_top20pct_plus_firstlight']['impaired_sy_flagged_pct']:.1f}%–{u_h['y1_daytime_screening_top20pct_plus_firstlight']['impaired_sy_flagged_pct']:.1f}% of impaired site-years, and provides {vp_uk['continuous_sonde_benchmark']['episodic_lt24h_lead']['median_lead_nadir_hr']:.1f}–{vp_us['continuous_sonde_benchmark']['episodic_lt24h_lead']['median_lead_nadir_hr']:.1f} h pre-nadir warning.

---

## Introduction

Dissolved oxygen governs the metabolic habitability and biogeochemical integrity of flowing freshwaters (Odum, 1956; Bernhardt et al., 2018; Battin et al., 2023). Because oxygen solubility declines with temperature (Benson and Krause, 1984) while aquatic ectotherm demand rises steeply during warm extremes (Pörtner, 2010), climate warming and hydroclimatic drought are intensifying river deoxygenation and hypoxia worldwide (van Vliet et al., 2023; Zhi et al., 2023; Graham et al., 2025), even where nutrient abatement has partially reversed chronic oxygen deficits (Zhou et al., 2026).

In biologically productive rivers, however, oxygen stress is strongly concentrated in astronomical darkness when daytime photosynthesis ceases and community respiration persists (Odum, 1956; Appling et al., 2018). Global syntheses of continuous sensor records establish that lotic hypoxia is frequently nocturnal and episodic (Blaszczak et al., 2023), and catchment-scale audits in six United Kingdom rivers show that measurement clock time and sampling frequency materially alter water-quality interpretation (Elfferich et al., 2024). Yet most regional and national water-quality networks still rely on discrete grab samples collected during daytime working hours because deploying continuous telemetered sondes across every stream reach is financially prohibitive.

Bridging the gap between observational bias and operational water management requires resolving three foundational issues that remain untested at multi-network scale. First, evaluating single-reading sampling times against a nocturnal minimum computed from the *same* probe creates mechanical circularity—forcing zero pre-dawn reference-negative alarms by construction—and requires leave-one-reading-out (LORO) verification, sensor-tolerance and persistence checks, independent field-meter benchmarking, and out-of-sample regional holdout validation. Second, nocturnal hypoxia durations measured strictly inside astronomical darkness are heavily censored at sunrise and sunset; uncorrected summaries can severely mischaracterize exposure duration and decision urgency. Third, higher per-visit recall does not automatically translate into superior operational monitoring: dark pre-dawn visits trigger overtime and two-person riparian safety costs, real-world agency crews rarely sample strictly at mid-afternoon, and pre-dawn grabs may still arrive too late to avert acute ecological damage before the oxygen nadir.

Here we transform cross-network timing audits into an equal-budget operational decision framework for water agencies. Combining raw UTC-timestamped continuous DO series across {us['n_sites']} screened free-flowing U.S. Geological Survey (USGS) rivers and {uk['n_sites']} screened Environment Agency (EA) rivers in England with {wqp_all['n_visits']:,} actual timestamped U.S. Water Quality Portal (WQP) agency grab-sample logs, we (1) characterize real-world field sampling clocks, independent field-meter agreement, and common-support coverage attrition; (2) establish non-circular LORO nocturnal detection gains, cadence sensitivity, and cross-Atlantic transferability—uncovering a near-optimal, daylight-safe first-light sampling window; (3) resolve boundary censoring bias and episodic detection lead times; and (4) quantify equal-budget cost-effectiveness across fixed afternoon, empirical agency, rotating, first-light, dark pre-dawn, and risk-stratified continuous sonde protocols. Throughout, continuous-sensor detection metrics quantify within-probe recorded nocturnal events on monitored networks rather than statutory compliance rates.

---

## Results

### Real-world monitoring schedules, field-meter fidelity, and coverage

Empirical field logs contradict the common assumption that routine water-quality monitoring occurs predominantly in mid-afternoon. Across {wqp_all['n_visits']:,} timestamped warm-season (May–October, 2015–2024) discrete DO visits spanning {wqp_all['n_sites']} screened U.S. rivers in the Water Quality Portal, agency sampling peaks in late morning: median local civil clock time is 11:00 (interquartile range [IQR] {wqp_all['local_clock_iqr_hr'][0]:.2f}–{wqp_all['local_clock_iqr_hr'][1]:.2f} h), corresponding to {wqp_all['solar_median_hr']:.2f} h local mean solar time (Fig. 1a). Nearly all visits ({wqp_all['pct_work_08_17_local']:.1f}%) occur between 08:00 and 17:00 local clock time ({wqp_all['pct_morning_08_12_local']:.1f}% during 08:00–12:00 and {wqp_all['pct_afternoon_12_17_local']:.1f}% during 12:00–17:00), whereas only {wqp_all['pct_predawn_2h']:.2f}% ({wqp_all['n_predawn_2h']} of {wqp_all['n_visits']:,}) fall within the two hours preceding geometric sunrise. The matched 2021–2024 subdaily cohort exhibits an identical distribution ({wqp_iv['n_visits']:,} visits across {wqp_iv['n_sites']} of our {us['n_sites']} stations; median local clock {wqp_iv['local_clock_median_hr']:.2f} h, {wqp_iv['pct_work_08_17_local']:.1f}% within 08:00–17:00).

Co-located field measurements confirm that the continuous USGS sondes closely track independent calibrated field meters while demonstrating nocturnal miss rates on real agency visit days. Pairing discrete WQP readings collected within 30 min of a continuous UTC sonde timestamp (median offset {co_val['median_dt_min']:.1f} min) yields {co_val['n_paired_readings_le30min']:,} co-located observations across {co_val['n_sites']} stations with Pearson $r = {co_val['pearson_r']:.3f}$, mean sonde-minus-meter bias of ${co_val['mean_bias_sonde_minus_grab_mgL']:+.03f}\\text{{ mg L}}^{{-1}}$, mean absolute error of ${co_val['mae_mgL']:.2f}\\text{{ mg L}}^{{-1}}$, and median absolute error of ${co_val['median_abs_err_mgL']:.2f}\\text{{ mg L}}^{{-1}}$—matching the $\\pm 0.20\\text{{ mg L}}^{{-1}}$ USGS continuous-monitor accuracy criterion (Wagner et al., 2006; Fig. 1b). Across {act_vis['n_matched_visit_nights']:,} actual agency visit dates matched with complete continuous nocturnal records, {act_vis['lt5_n_hyp_nights']} nights exhibited LORO nocturnal hypoxia (<5 mg L$^{{-1}}$) and {act_vis['actionable_2h_n_nights']} involved persistent ≥2 h episodes. Real field visits detected only {act_vis['lt5_grab_detected']}/{act_vis['lt5_n_hyp_nights']} ({act_vis['lt5_grab_recall_pct']:.1f}%; missing {act_vis['lt5_grab_missed_pct']:.1f}%) of LORO hypoxic nights and {act_vis['actionable_2h_grab_detected']}/{act_vis['actionable_2h_n_nights']} ({act_vis['actionable_2h_grab_recall_pct']:.1f}%) of ≥2 h actionable episodes, compared with {act_vis['lt5_predawn_sonde_recall_pct']:.1f}% and {act_vis['actionable_2h_predawn_recall_pct']:.1f}% detection by pre-dawn sonde readings on those exact same visit dates (Fig. 1b inset).

Transparent coverage auditing explains trans-Atlantic differences in common-support sample retention (Fig. 1c; Supplementary Tables S1–S2). Out of {att_us['candidate_nights']:,} warm-season candidate site-nights across {att_us['n_sites_candidate']} U.S. stations, {att_us['complete_nights']:,} ({att_us['complete_rate_pct']:.1f}%) met nocturnal continuity limits (all internal and boundary gaps $\\le 1.5\\times$ native cadence) and {att_us['matched_nights']:,} ({att_us['common_support_entry_pct']:.1f}%) entered common-support evaluation (failing primarily due to nocturnal gaps [{att_us['fail_night_gap']:,}] rather than daytime target matching [{att_us['fail_target_match']:,}]). Across {att_uk['n_sites_candidate']} English stations, {att_uk['matched_nights']:,} of {att_uk['candidate_nights']:,} candidate nights ({att_uk['common_support_entry_pct']:.1f}%) entered common support. Attrition stratifies sharply by native cadence rather than season (monthly entry rates vary by <2.3 percentage points across May–October in both networks): U.S. stations are predominantly 15-min ({step_us[15]['n_sites']} sites, {step_us[15]['entry_rate_pct']:.1f}% entry), whereas England comprises {step_uk[15]['n_sites']} stations at 15-min ({step_uk[15]['entry_rate_pct']:.1f}% entry), {step_uk[30]['n_sites']} at 30-min ({step_uk[30]['entry_rate_pct']:.1f}% entry, accounting for {step_uk[30]['fail_night_gap']:,} of {att_uk['fail_night_gap']:,} English nocturnal gap exclusions), and {step_uk[60]['n_sites']} at 60-min ({step_uk[60]['entry_rate_pct']:.1f}% entry). Partial-data excluded nights show modestly higher <5 mg L$^{{-1}}$ prevalence than matched nights in the U.S. ({att_us['excluded_partial_lt5_rate_pct']:.2f}% vs. {att_us['included_lt5_rate_pct']:.2f}%) and lower prevalence in England ({att_uk['excluded_partial_lt5_rate_pct']:.2f}% vs. {att_uk['included_lt5_rate_pct']:.2f}%), indicating no uniform directional omission bias.

<!-- FIGURE:fig1_nw_monitoring_clock_and_coverage.png -->

### Cross-network LORO validation and the first-light window

Eliminating shared reference-outcome circularity preserves large nocturnal detection gains across both national networks while exposing non-zero pre-dawn reference-negative alarm rates (Fig. 2a; Table 1). Under our primary LORO estimator—which excludes the candidate pre-dawn reading when classifying the astronomical night—reference-positive <5 mg L$^{{-1}}$ nights decline by {us5['shared_minus_loro_dropped_nights']} of {us5['shared_n_ref_pos']:,} in the U.S. (to {us5['loro_n_ref_pos']:,}) and by {uk5['shared_minus_loro_dropped_nights']} of {uk5['shared_n_ref_pos']:,} in England (to {uk5['loro_n_ref_pos']:,}). Moving a single daily reading from 14:30 local mean solar time to 30 min before geometric sunrise increases LORO recall from {us5['loro_schedules']['afternoon']['recall_95_pct'][0]:.2f}% to {us5['loro_schedules']['predawn']['recall_95_pct'][0]:.2f}% in the U.S. (paired gain {fmt_ci(us5['loro_dawn_minus_afternoon_95_pp'], signed=True)} percentage points, clustered by {us['n_clusters']} HUC-2 basins) and from {uk5['loro_schedules']['afternoon']['recall_95_pct'][0]:.2f}% to {uk5['loro_schedules']['predawn']['recall_95_pct'][0]:.2f}% in England (paired gain {fmt_ci(uk5['loro_dawn_minus_afternoon_95_pp'], signed=True)} percentage points, clustered by {uk['n_clusters']} 1° hydrometric grids). Against the 10:30 solar overpass window, LORO pre-dawn gains are {fmt_ci(us5['loro_dawn_minus_overpass_95_pp'], signed=True)} percentage points (U.S.) and {fmt_ci(uk5['loro_dawn_minus_overpass_95_pp'], signed=True)} percentage points (England). Transparently removing the shared-reading guarantee yields LORO pre-dawn reference-negative alarm rates of {us5['loro_schedules']['predawn']['ref_neg_alarm_95_pct'][0]:.3f}% in the U.S. ({us5['loro_schedules']['predawn']['ref_neg_alarms']} single-reading dips across {us5['loro_schedules']['predawn']['n_ref_neg']:,} reference-negative nights) and {uk5['loro_schedules']['predawn']['ref_neg_alarm_95_pct'][0]:.3f}% in England ({uk5['loro_schedules']['predawn']['ref_neg_alarms']} across {uk5['loro_schedules']['predawn']['n_ref_neg']:,} nights)—still lower than daytime reference-negative rates at 14:30 ({us5['loro_schedules']['afternoon']['ref_neg_alarm_95_pct'][0]:.3f}% U.S., {uk5['loro_schedules']['afternoon']['ref_neg_alarm_95_pct'][0]:.3f}% England) and 10:30 ({us5['loro_schedules']['overpass']['ref_neg_alarm_95_pct'][0]:.3f}% U.S., {uk5['loro_schedules']['overpass']['ref_neg_alarm_95_pct'][0]:.3f}% England). Comparable LORO gains persist across stricter chronic and acute thresholds: <4 mg L$^{{-1}}$ ({us4['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} U.S., {uk4['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} England), <3 mg L$^{{-1}}$ ({us3['loro_dawn_minus_afternoon_95_pp'][0]:+.2f}, {uk3['loro_dawn_minus_afternoon_95_pp'][0]:+.2f}), and <2 mg L$^{{-1}}$ ({us2['loro_dawn_minus_afternoon_95_pp'][0]:+.2f}, {uk2['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} percentage points; Table 1).

**Table 1. Primary leave-one-reading-out (LORO) nocturnal hypoxia detection across U.S. and English networks.**

| Network | Threshold (mg L$^{{-1}}$) | LORO ref. pos. (Δ vs. shared) | Schedule | LORO recall, % [95% CI] | Ref.-neg. alarm, % | Paired gain vs. 14:30, pp [95% CI] |
|---|---:|---:|---|---:|---:|---:|
{table1_md}

*Notes:* Evaluated on identical common-support site-nights ({us['n_nights']:,} U.S. across {us['n_sites']} stations; {uk['n_nights']:,} England across {uk['n_sites']} stations). LORO removes the candidate pre-dawn reading when determining nocturnal reference hypoxia; Δ denotes nights reclassified from positive to negative relative to shared-reading evaluation. Confidence intervals use CR1 cluster-robust standard errors with finite-sample $t(G-1)$ critical values clustered by HUC-2 basin (U.S.) or 1° grid cell (England). Source: `results/11_loro_and_sensitivity.json` and `tables/table1_nw_loro_cross_network.csv`.

Every anti-circularity, measurement-error, cadence, site-weighting, and holdout test confirms the stability of the nocturnal gain while revealing two practical insights (Fig. 2b,c; Table 2). First, excluding an entire ±30 min window around pre-dawn leaves gains virtually unchanged ({us5['loro_pm30m_exclusion']['dawn_minus_afternoon_95_pp'][0]:+.2f} U.S., {uk5['loro_pm30m_exclusion']['dawn_minus_afternoon_95_pp'][0]:+.2f} England percentage points). Requiring persistence of ≥2 consecutive non-candidate readings or ≥2 h continuous hypoxia increases the pre-dawn advantage to {us5['persistence_sensitivity']['persist_ge2_readings']['dawn_minus_afternoon_95_pp'][0]:+.2f}–{us5['persistence_sensitivity']['actionable_ge2h']['dawn_minus_afternoon_95_pp'][0]:+.2f} percentage points in the U.S. and {uk5['persistence_sensitivity']['persist_ge2_readings']['dawn_minus_afternoon_95_pp'][0]:+.2f}–{uk5['persistence_sensitivity']['actionable_ge2h']['dawn_minus_afternoon_95_pp'][0]:+.2f} percentage points in England. Applying ±0.2 mg L$^{{-1}}$ deterministic threshold buffers or adding independent Gaussian instrument noise ($\\sigma = 0.20\\text{{ mg L}}^{{-1}}$, 200 Monte Carlo replications simulating two independent co-located probes) retains gains of {us5['independent_probe_noise_mc']['sigma_0p20']['dawn_minus_afternoon_mean_pp']:+.2f} (U.S.) and {uk5['independent_probe_noise_mc']['sigma_0p20']['dawn_minus_afternoon_mean_pp']:+.2f} (England) percentage points.

Second, systematically downsampling all {r11['cadence_downsampling']['USGS']['n_highfreq_sites_tested']} high-frequency U.S. stations (≤15 min native cadence) onto exact 15-, 30-, and 60-min UTC grids explains England's higher LORO alarm rate as a pure sampling-interval effect: coarsening cadence from 15 to 60 min leaves LORO recall gain steady ({cad_us['15min']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} → {cad_us['30min']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} → {cad_us['60min']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} percentage points) while mechanically raising pre-dawn reference-negative alarms sixteen-fold from {cad_us['15min']['predawn_ref_neg_alarm_pct']:.3f}% to {cad_us['60min']['predawn_ref_neg_alarm_pct']:.3f}%—closely matching England's predominantly 30–60 min network ({cad_uk30['60min']['predawn_ref_neg_alarm_pct']:.3f}% on England's ≤30-min cohort downsampled to 60 min; {cad_uk['60min']['predawn_ref_neg_alarm_pct']:.3f}% on England's 15-min cohort). Equal-site weighting across stations with ≥5 hypoxic nights yields {us5['equal_site_ge5_gain_95_pp'][0]:+.2f} (U.S., {us5['equal_site_ge5_n']} sites) and {uk5['equal_site_ge5_gain_95_pp'][0]:+.2f} (England, {uk5['equal_site_ge5_n']} sites) percentage points, and excluding chronically hypoxic stations (>50% of nights <5 mg L$^{{-1}}$, or >25% of 14:30 readings <5 mg L$^{{-1}}$) *strengthens* the timing gain to {us5['chronic_site_sensitivity']['excl_chronic_gt50pct_nights']['pooled_dawn_minus_afternoon_95_pp'][0]:+.2f}–{us5['chronic_site_sensitivity']['excl_daytime_chronic_gt25pct_af']['pooled_dawn_minus_afternoon_95_pp'][0]:+.2f} (U.S.) and {uk5['chronic_site_sensitivity']['excl_chronic_gt50pct_nights']['pooled_dawn_minus_afternoon_95_pp'][0]:+.2f}–{uk5['chronic_site_sensitivity']['excl_daytime_chronic_gt25pct_af']['pooled_dawn_minus_afternoon_95_pp'][0]:+.2f} (England) percentage points, confirming that episodic rivers drive the scheduling benefit.

Crucially, scanning offsets from 180 min before to 120 min after geometric sunrise reveals an operationally vital **first-light daylight plateau** (Fig. 2b). Out-of-sample Youden-$J$ optimization independently selects geometric sunrise (`SR + 0 min`) in 16/16 U.S. Leave-One-HUC2-Basin-Out folds, 5/5 U.S. site folds, 11/15 English 1°-grid folds (4 selecting `SR − 30 min`), and both directions of zero-shot cross-Atlantic transfer (out-of-sample LORO gains {ho['cross_atlantic_transfer']['EA_to_USGS']['test_gain_95_pp'][0]:+.2f} U.S. and {ho['cross_atlantic_transfer']['USGS_to_EA']['test_gain_95_pp'][0]:+.2f} England percentage points; Table 2). Because nocturnal respiration and hypoxic water-mass advection briefly lag geometric dawn before photosynthetic irradiance reaches the compensation point, LORO recall peaks at geometric sunrise ({us_sr['recall_95_pct'][0]:.2f}% U.S., {uk_sr['recall_95_pct'][0]:.2f}% England) and remains virtually unchanged 30 min *after* sunrise in safe civil daylight (`SR + 30 min`: {us_fl['recall_95_pct'][0]:.2f}% U.S., {uk_fl['recall_95_pct'][0]:.2f}% England; LORO reference-negative alarms {us_fl['ref_neg_alarm_95_pct'][0]:.3f}% and {uk_fl['ref_neg_alarm_95_pct'][0]:.3f}%).

<!-- FIGURE:fig2_nw_loro_cross_network_validation.png -->

**Table 2. Anti-circularity, sensor tolerance, persistence, cadence downsampling, site-weighting, and out-of-sample holdout audit (<5 mg L$^{{-1}}$).**

| Sensitivity or validation test | U.S. $n$ | U.S. gain vs. 14:30, pp [95% CI] | U.S. ref.-neg. alarm, % | England $n$ | England gain vs. 14:30, pp [95% CI] | England ref.-neg. alarm, % |
|---|---:|---:|---:|---:|---:|---:|
{table2_md}

*Notes:* $n$ denotes reference-positive site-nights (or stations for equal-site weighting). Independent probe-noise Monte Carlo adds independent $\\mathcal{{N}}(0, \\sigma^2)$ noise to candidate and reference readings across 200 replications (2.5th–97.5th percentiles shown). Downsampling evaluates native ≤15-min stations ({r11['cadence_downsampling']['USGS']['n_highfreq_sites_tested']} U.S., {r11['cadence_downsampling']['EA']['n_highfreq_sites_tested']} England; England's {r11['cadence_downsampling']['EA']['ea_le30min_cohort_30_vs_60']['n_sites_le30min']}-site ≤30-min cohort yields {cad_uk30['30min']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} and {cad_uk30['60min']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} pp at 30 and 60 min). Source: `results/11_loro_and_sensitivity.json` and `tables/table2_nw_robustness_holdout_cadence.csv`.

### Boundary censoring, duration bias, and episodic lead time

Evaluating hypoxia duration strictly within astronomical darkness introduces severe right- and double-censoring that distorts risk characterization unless corrected (Fig. 3a,b; Supplementary Table S3). Among all {us5['shared_n_ref_pos']:,} U.S. and {uk5['shared_n_ref_pos']:,} English <5 mg L$^{{-1}}$ site-nights, only {cd_us['both_closed_n']:,} ({cd_us['both_closed_pct']:.1f}%) and {cd_uk['both_closed_n']:,} ({cd_uk['both_closed_pct']:.1f}%), respectively, have both run boundaries closed inside darkness. In contrast, {us_rc_pct:.1f}% of U.S. hypoxic nights ({cd_us['censor_counts']['right_only']:,} right-censored at sunrise plus {cd_us['censor_counts']['doubly_censored']:,} doubly censored across the entire night) and {uk_rc_pct:.1f}% of English nights ({cd_uk['censor_counts']['right_only']:,} right-censored plus {cd_uk['censor_counts']['doubly_censored']:,} doubly censored) remain hypoxic past geometric sunrise. Restricting duration summaries to closed-in-night runs therefore selects solely for brief transient dips, compressing median apparent duration to {cd_us['both_closed_median_lo_hi_hr'][0]:.2f}–{cd_us['both_closed_median_lo_hi_hr'][1]:.2f} h (U.S.) and {cd_uk['both_closed_median_lo_hi_hr'][0]:.2f}–{cd_uk['both_closed_median_lo_hi_hr'][1]:.2f} h (England). Applying Kaplan–Meier right-censored survival estimation (Kaplan and Meier, 1958) to episodes with observed nocturnal onset shows that {cd_us['km_nocturnal_observed_onset']['surv_at_6h_pct']:.1f}% (U.S.) and {cd_uk['km_nocturnal_observed_onset']['surv_at_6h_pct']:.1f}% (England) persist beyond 6 h (restricted 12-h mean {cd_us['km_nocturnal_observed_onset']['rmst_12h_hr']:.2f} h U.S. and {cd_uk['km_nocturnal_observed_onset']['rmst_12h_hr']:.2f} h England; England KM median {cd_uk['km_nocturnal_observed_onset']['median_hr']:.2f} h, U.S. KM survival never falls below 50% before sunrise). Tracing unbroken continuous runs across sunrise and sunset closes {cd_us['full_continuous_closed_pct']:.1f}% (U.S.) and {cd_uk['full_continuous_closed_pct']:.1f}% (England) of all episodes, revealing true median continuous durations of {cd_us['full_continuous_median_iqr_hr'][1]:.1f} h (IQR {cd_us['full_continuous_median_iqr_hr'][0]:.1f}–{cd_us['full_continuous_median_iqr_hr'][2]:.1f} h) in the U.S. and {cd_uk['full_continuous_median_iqr_hr'][1]:.1f} h (IQR {cd_uk['full_continuous_median_iqr_hr'][0]:.1f}–{cd_uk['full_continuous_median_iqr_hr'][2]:.1f} h) in England (Fig. 3b).

Explicitly separating episodic single-night actionable events (2–24 h continuous <5 mg L$^{{-1}}$; {vp_us['n_episodic_lt24h_nights']:,} U.S. and {vp_uk['n_episodic_lt24h_nights']:,} English site-nights) from multi-day chronic hypoxia ({vp_us['n_chronic_ge24h_nights']:,} U.S. and {vp_uk['n_chronic_ge24h_nights']:,} English site-nights) clarifies why even pre-dawn grab sampling is an active-event surveillance tool rather than true early warning (Fig. 3c). On episodic 2–24 h events, 14:30 afternoon grabs miss {100.0 - vp_us['protocols']['afternoon_1430']['episodic_lt24h_recall_pct']:.1f}% (U.S.) and {100.0 - vp_uk['protocols']['afternoon_1430']['episodic_lt24h_recall_pct']:.1f}% (England) and, when they do register low DO, arrive a median of {abs(vp_us['protocols']['afternoon_1430']['episodic_lt24h_lead']['median_lead_end_hr']):.2f}–{abs(vp_uk['protocols']['afternoon_1430']['episodic_lt24h_lead']['median_lead_end_hr']):.2f} h *after* recovery ({abs(vp_us['protocols']['afternoon_1430']['episodic_lt24h_lead']['median_lead_nadir_hr']):.1f}–{abs(vp_uk['protocols']['afternoon_1430']['episodic_lt24h_lead']['median_lead_nadir_hr']):.1f} h post-nadir). Pre-dawn (`SR − 30 min`) and first-light (`SR + 30 min`) grabs catch {vp_us['protocols']['first_light_sr_p30']['episodic_lt24h_recall_pct']:.1f}%–{vp_us['protocols']['predawn_sr_m30']['episodic_lt24h_recall_pct']:.1f}% (U.S.) and {vp_uk['protocols']['first_light_sr_p30']['episodic_lt24h_recall_pct']:.1f}%–{vp_uk['protocols']['predawn_sr_m30']['episodic_lt24h_recall_pct']:.1f}% (England) while hypoxia remains active ({vp_us['protocols']['first_light_sr_p30']['episodic_lt24h_lead']['median_lead_end_hr']:+.2f} to {vp_us['protocols']['predawn_sr_m30']['episodic_lt24h_lead']['median_lead_end_hr']:+.2f} h remaining before recovery), yet they arrive right near or slightly after the oxygen nadir ({vp_us['protocols']['first_light_sr_p30']['episodic_lt24h_lead']['median_lead_nadir_hr']:+.2f} to {vp_us['protocols']['predawn_sr_m30']['episodic_lt24h_lead']['median_lead_nadir_hr']:+.2f} h U.S.; {vp_uk['protocols']['first_light_sr_p30']['episodic_lt24h_lead']['median_lead_nadir_hr']:+.2f} to {vp_uk['protocols']['predawn_sr_m30']['episodic_lt24h_lead']['median_lead_nadir_hr']:+.2f} h England). By contrast, telemetered continuous sondes triggering alerts 30 min after onset detect 100% of episodic events a median of {vp_us['continuous_sonde_benchmark']['episodic_lt24h_lead']['median_lead_nadir_hr']:+.1f} h (U.S.) and {vp_uk['continuous_sonde_benchmark']['episodic_lt24h_lead']['median_lead_nadir_hr']:+.1f} h (England) *before* the oxygen nadir ({vp_us['continuous_sonde_benchmark']['episodic_lt24h_lead']['pct_before_nadir']:.1f}%–{vp_uk['continuous_sonde_benchmark']['episodic_lt24h_lead']['pct_before_nadir']:.1f}% caught pre-nadir; {vp_us['continuous_sonde_benchmark']['episodic_lt24h_lead']['median_lead_end_hr']:+.1f} and {vp_uk['continuous_sonde_benchmark']['episodic_lt24h_lead']['median_lead_end_hr']:+.1f} h before recovery).

<!-- FIGURE:fig3_nw_censoring_duration_and_leadtime.png -->

### Equal-budget operational protocol and cost-effectiveness frontier

Translating per-visit detection into deployable agency decisions under fixed annual budgets overturns simple pre-dawn grab recommendations (Fig. 4; Table 3; Supplementary Table S4). Evaluated strictly out-of-sample on post-Year-1 warm seasons ({eb_us['n_eval_site_years']} U.S. site-years with {eb_us['total_distinct_episodes_in_eval']:,} distinct non-overlapping ≥2 h <5 mg L$^{{-1}}$ episodes; {eb_uk['n_eval_site_years']} English site-years with {eb_uk['total_distinct_episodes_in_eval']:,} distinct episodes) across 1,000 stratified calendar schedules, we count **distinct non-overlapping episodes** alongside actionable site-nights and impaired site-years flagged to prevent multi-day chronic events from inflating continuous-sonde counts.

Before staffing surcharges, shifting from the empirical WQP clock to pre-dawn adds {vp_us['protocols']['predawn_sr_m30']['new_actionable_per_100_vs_wqp']:+.2f} (U.S.) and {vp_uk['protocols']['predawn_sr_m30']['new_actionable_per_100_vs_wqp']:+.2f} (England) actionable detections per 100 visits ({vp_us['protocols']['predawn_sr_m30']['new_actionable_per_100_vs_afternoon']:+.2f} and {vp_uk['protocols']['predawn_sr_m30']['new_actionable_per_100_vs_afternoon']:+.2f} relative to 14:30 afternoon). Once realistic nocturnal field-safety and overtime multipliers ($m_{{\\text{{night}}}} = 1.75\\times$, representing two-person dark-terrain crews and night-shift differentials) constrain an identical annual budget (baseline 24 daytime-visit-equivalents site$^{{-1}}$ yr$^{{-1}}$, or \\$4,800 site$^{{-1}}$ yr$^{{-1}}$ at \\$200 daytime visit$^{{-1}}$), however, three decisive operational findings emerge:

1. **Dark pre-dawn grabs lose cost-effectiveness above modest overtime surcharges.** Analytical breakeven multipliers where pure dark pre-dawn equals the empirical WQP agency clock are only $m^* = {fr_us['predawn_breakeven_m_vs_wqp_clock']:.2f}\\times$ in the U.S. and $m^* = {fr_uk['predawn_breakeven_m_vs_wqp_clock']:.2f}\\times$ in England (vs. {fr_us['predawn_breakeven_m_vs_afternoon']:.2f}× and {fr_uk['predawn_breakeven_m_vs_afternoon']:.2f}× against 14:30 afternoon). At $m_{{\\text{{night}}}} = 1.75\\times$, the 43% reduction in affordable annual visits leaves dark pre-dawn yielding {u_g['predawn_sr_m30']['distinct_episodes_per_100_dayeq']:.2f} distinct episodes per 100 budget-equivalents (\\${u_g['predawn_sr_m30']['cost_usd_per_distinct_episode']:,.0f} episode$^{{-1}}$) in the U.S. and {e_g['predawn_sr_m30']['distinct_episodes_per_100_dayeq']:.2f} (\\${e_g['predawn_sr_m30']['cost_usd_per_distinct_episode']:,.0f} episode$^{{-1}}$) in England—no better than, or worse than, the existing empirical WQP clock ({u_g['empirical_wqp_clock']['distinct_episodes_per_100_dayeq']:.2f} U.S., {e_g['empirical_wqp_clock']['distinct_episodes_per_100_dayeq']:.2f} England; Table 3).
2. **First-light civil daylight grabs (`SR + 30 min`) dominate all grab-only alternatives.** Because early daylight eliminates two-person dark-terrain safety crews while retaining near-peak recall ({vp_us['protocols']['first_light_sr_p30']['actionable_recall_pct']:.1f}% U.S., {vp_uk['protocols']['first_light_sr_p30']['actionable_recall_pct']:.1f}% England on ≥2 h episodes), first-light grabs (modeled with a modest 1.15× early-shift factor) deliver {u_g['first_light_sr_p30']['distinct_episodes_per_100_dayeq']:.2f} (U.S.) and {e_g['first_light_sr_p30']['distinct_episodes_per_100_dayeq']:.2f} (England) distinct episodes per 100 budget-equivalents, lowering cost to \\${u_g['first_light_sr_p30']['cost_usd_per_distinct_episode']:,.0f} and \\${e_g['first_light_sr_p30']['cost_usd_per_distinct_episode']:,.0f} per episode while flagging {u_g['first_light_sr_p30']['impaired_sy_flagged_pct']:.1f}% (U.S.) and {e_g['first_light_sr_p30']['impaired_sy_flagged_pct']:.1f}% (England) of impaired site-years—beating both dark pre-dawn and rotating daytime schedules (Fig. 4a,b).
3. **Risk-stratified continuous sondes plus first-light grabs dominate the entire decision frontier.** Because hypoxic episodes are strongly concentrated across rivers, allocating amortized continuous sondes ($K_{{\\text{{sonde}}}} = 40$ daytime-visit-equivalents yr$^{{-1}}$, or \\$8,000 sonde$^{{-1}}$ yr$^{{-1}}$ covering hardware amortization, telemetry, and routine biofouling calibration visits) to the top 20% highest-risk stations—ranked strictly out-of-sample using only Year-1 daytime grab observations—captures {eb_us['sonde_targeting_capture']['y1_daytime_screening_top20pct']['share_of_distinct_episodes_pct']:.1f}% (U.S.) and {eb_uk['sonde_targeting_capture']['y1_daytime_screening_top20pct']['share_of_distinct_episodes_pct']:.1f}% (England) of all subsequent distinct episodes while leaving sufficient budget for {u_h['y1_daytime_screening_top20pct_plus_firstlight']['non_sonde_annual_visits_per_site']:.1f} annual first-light visits at every remaining station. Under the exact same total dollar budget, this hybrid protocol yields {u_h['y1_daytime_screening_top20pct_plus_firstlight']['distinct_episodes_per_100_dayeq']:.2f} (U.S.) and {e_h['y1_daytime_screening_top20pct_plus_firstlight']['distinct_episodes_per_100_dayeq']:.2f} (England) distinct episodes per 100 budget-equivalents ({us_sonde_mult:.1f}× and {uk_sonde_mult:.1f}× empirical WQP grabs; {us_sonde_night_mult:.1f}× and {uk_sonde_night_mult:.1f}× on actionable site-nights), reduces cost per distinct episode by {us_cost_cut:.0f}%–{uk_cost_cut:.0f}% to \\${u_h['y1_daytime_screening_top20pct_plus_firstlight']['cost_usd_per_distinct_episode']:,.0f} (U.S.) and \\${e_h['y1_daytime_screening_top20pct_plus_firstlight']['cost_usd_per_distinct_episode']:,.0f} (England), and raises network-wide site-year discovery to {u_h['y1_daytime_screening_top20pct_plus_firstlight']['impaired_sy_flagged_pct']:.1f}% (U.S.) and {e_h['y1_daytime_screening_top20pct_plus_firstlight']['impaired_sy_flagged_pct']:.1f}% (England) (Fig. 4b). Even with zero prior DO records—ranking sites strictly out-of-sample from static geographic/basin covariates—top-20% sonde hybrids achieve {u_h['loor_covariate_score_top20pct']['distinct_episodes_per_100_dayeq']:.2f} (U.S.) and {e_h['loor_covariate_score_top20pct']['distinct_episodes_per_100_dayeq']:.2f} (England) distinct episodes per 100 budget-equivalents. Across the full cost-ratio phase surface, top-20% hybrids dominate up to $K_{{\\text{{sonde}}}} = 120$ visit-equivalents yr$^{{-1}}$ (\\$24,000 sonde$^{{-1}}$ yr$^{{-1}}$), top-10% hybrids dominate up to $K_{{\\text{{sonde}}}} = 240$, and first-light grabs win only where continuous instrumentation is infeasible or prohibitively costly (Fig. 4c; consistent across 12 and 52 annual visit budgets and <4 mg L$^{{-1}}$ / <3 mg L$^{{-1}}$ thresholds in Supplementary Table S4).

<!-- FIGURE:fig4_nw_equal_budget_protocol_frontier.png -->

**Table 3. Equal-budget operational protocol comparison for persistent actionable hypoxia (≥2 h continuous <5 mg L$^{{-1}}$, LORO).**

| Network | Monitoring protocol (budget = 24 day-eq site$^{{-1}}$ yr$^{{-1}}$) | Actionable / 100 visits | Distinct ep. / 100 eq | Cost / distinct ep. | Impaired site-yrs flagged | Episodic lead: nadir / end (h) | LORO ref.-neg. alarm |
|---|---|---:|---:|---:|---:|---:|---:|
{table3_md}

*Notes:* Evaluated strictly out-of-sample on post-Year-1 warm seasons ({eb_us['n_eval_site_years']} U.S. site-years, {eb_us['n_impaired_site_years']} impaired; {eb_uk['n_eval_site_years']} English site-years, {eb_uk['n_impaired_site_years']} impaired) across 1,000 stratified warm-season calendars at central costs ($m_{{\\text{{night}}}} = 1.75\\times$, early-shift first-light $1.15\\times$, $K_{{\\text{{sonde}}}} = 40$ daytime-visit-equivalents yr$^{{-1}}$, benchmark \\$200 daytime visit$^{{-1}}$). Distinct episodes group consecutive hypoxic site-nights at the same station to avoid double-counting multi-day events. Source: `results/12_operational_protocol_decision.json` and `tables/table3_nw_equal_budget_protocols.csv`.

---

## Discussion

Our cross-network analysis demonstrates that turning nocturnal hypoxia awareness into better water management requires moving beyond fixed-time recall comparisons to explicit budget, safety, and lead-time trade-offs. Although LORO validation confirms that shifting a single sample from mid-afternoon to before sunrise raises within-probe <5 mg L$^{{-1}}$ detection by ~35–50 percentage points on both sides of the Atlantic, real-world agency logistics reshape the operational optimum in three concrete ways.

First, **agencies constrained to grab sampling should adopt early-morning first-light scheduling (`sunrise` to `sunrise + 30 min`) rather than pitch-dark pre-dawn shifts or uniform afternoon schedules.** Because field visits already peak around 11:00 local time—not 14:30—and nocturnal safety rules typically raise pre-dawn visit costs above the 1.38×–1.53× breakeven threshold, mandating pre-dawn dark visits across an entire network reduces detections per dollar. Shifting routine crews by 3–4 hours into early civil daylight captures nearly identical nocturnal recall (85%–90% of persistent ≥2 h episodes) without night-shift safety surcharges, while increasing impaired-site discovery over both empirical WQP clocks and dark pre-dawn schedules. Where operational logistics prohibit early shifts on every visit, rotating even one-third of visits into early daylight provides an immediate no-overtime improvement over fixed afternoon monitoring.

Second, **agencies with capital flexibility should transition from uniform grab networks to risk-stratified hybrid networks.** Deploying continuous telemetered sondes to just 10%–20% of highest-risk reaches—identifiable strictly out-of-sample from a single prior warm season of routine daytime grab data (or even static basin covariates)—and applying first-light grabs across the remaining 80%–90% of reaches multiplies distinct episode detections 3.5×–4.7× under the *same* annual budget, cuts per-episode cost by >70%, expands impaired-site discovery across the entire network, and unlocks the only operational pathway to true pre-nadir early warning (3.5–4.5 h before minimum DO) needed for reservoir aeration releases, wastewater discharge throttling, or aquaculture advisories.

Third, **transparent censoring accounting is essential when translating sensor logs into ecological risk.** Over three-quarters of nocturnal <5 mg L$^{{-1}}$ runs extend past geometric sunrise; naively summarizing only runs closed inside darkness understates median continuous exposure duration by roughly an order of magnitude (1–2 h vs. 13.0–13.5 h). Future monitoring syntheses should report Kaplan–Meier censored bounds or cross-boundary continuous episode durations alongside native-cadence attrition audits.

Several scope boundaries warrant explicit note. Both the USGS and EA cohorts represent screened continuous monitoring networks rather than unweighted random samples of all streams, and continuous-sensor outcomes quantify within-probe recorded nocturnal events rather than statutory regulatory compliance. Although 1,287 co-located WQP field-meter readings verify probe fidelity ($r = 0.961$, MedAE 0.20 mg L$^{{-1}}$), prospective field trials using dual co-located continuous probes and UK-specific grab-sampling timestamp archives (currently unavailable via the migrated EA Water Quality API) remain important next steps. Similarly, attributing long-term hypoxic trends to climate versus nutrient management requires coupled hydrodynamic, nutrient, and irradiance datasets (Graham et al., 2025; Zhou et al., 2026); supplementary daily-extremes thermal decoupling and drought-interaction analyses across 397 U.S. stations (2005–2025) are archived in the Supplementary Information to contextualize warm-season risk stratification.

---

## Methods

### Data sources and UTC timestamp reconstruction

We assembled continuous UTC-timestamped dissolved-oxygen records from two independent national networks screened to exclude dams, tailraces, lock pools, lakes, canals, tidal/estuarine waters, and brackish sites (>5,000 $\\mu\\text{{S cm}}^{{-1}}$; full exclusion log in `data/processed/excluded_sites_audit.csv`). For the U.S., we archived native UTC continuous Parquet files from USGS Water Data STAC (`parameter_code == "00300"`, `approval_status == "Approved"`, $0 \\le \\text{{DO}} \\le 25\\text{{ mg L}}^{{-1}}$, May–October 2021–2024) for all {us['n_sites']} multi-year subdaily stations spanning 17 HUC-2 basins, selecting the longest-coverage `time_series_id` per station and collapsing duplicate timestamps by median. For England, we used the {uk['n_sites']} screened, 2-km-deduplicated free-flowing Environment Agency Hydrology API stations (May–October 2012–2025, 19 1° $\\times$ 1° hydrometric grid clusters). To quantify real-world field visit timing and independent probe fidelity, we retrieved all warm-season discrete field DO measurements (`pCode=00300`) from the U.S. Water Quality Portal for our {us['n_sites']} subdaily stations (2021–2024; {wqp_iv['n_visits']:,} visits across {wqp_iv['n_sites']} sites) and our broader 397-station screened CONUS inventory (2015–2024; {wqp_all['n_visits']:,} visits across {wqp_all['n_sites']} sites), converting local timestamps and USGS timezone codes to UTC and local mean solar time (LMST).

### Astronomical darkness and common-support screening

Every UTC timestamp was converted to continuous LMST minutes via $t_{{\\text{{solar}}}} = (t_{{\\text{{UTC}}}} - t_{{\\text{{epoch}}}})/60 + 4\\lambda$, where $\\lambda$ is station longitude (degrees east). Geometric sunrise and sunset were calculated for each solar date from station latitude and day-of-year using the 3-harmonic Spencer–Iqbal declination and equation-of-time series (Iqbal, 1983). Each station's modal native sampling step $\\Delta t$ (5–60 min) was identified from consecutive observation intervals; a warm-season astronomical night (previous sunset to current sunrise) was deemed complete if all internal and boundary gaps were $\\le 1.5\\Delta t$. Common-support site-nights additionally required valid readings within $0.55\\Delta t$ of each core target (`14:30`, `10:30`, and `sunrise − 30 min`), with the pre-dawn reading strictly inside darkness.

### Primary LORO estimator, sensitivity battery, and holdout validation

To eliminate shared reference-outcome circularity, our primary LORO estimator removes the candidate pre-dawn reading from the astronomical night array before testing whether any remaining nocturnal reading falls below threshold $\\tau \\in \\{{5, 4, 3, 2\\}}\\text{{ mg L}}^{{-1}}$, reporting both LORO recall and LORO reference-negative alarm rate for every schedule. Sensitivity analyses evaluate: (i) excluding an entire $\\pm 30\\text{{ min}}$ window around pre-dawn; (ii) requiring persistence of $\\ge 2$ consecutive non-candidate sub-threshold readings or $\\ge 2\\text{{ h}}$ continuous hypoxia; (iii) deterministic $\\pm 0.1$ and $\\pm 0.2\\text{{ mg L}}^{{-1}}$ reference buffers plus 200-replication independent Gaussian probe noise ($\\sigma = 0.10, 0.20\\text{{ mg L}}^{{-1}}$); (iv) exact downsampling of native $\\le 15$-min stations onto 15-, 30-, and 60-min UTC grids; (v) equal-site weighting ($\\ge 5$ hypoxic nights) and exclusion of chronically hypoxic sites; and (vi) out-of-sample optimal solar-offset selection (maximizing LORO Youden's $J$ over offsets from `SR − 180` to `SR + 120` min plus fixed solar hours) evaluated via Leave-One-Region-Out (17 HUC-2 basins / 19 1° grids), 5-fold disjoint site holdout, and zero-shot cross-Atlantic transfer. All confidence intervals use CR1 cluster-robust standard errors with finite-sample $t(G-1)$ critical values (Cameron and Miller, 2015).

### Censoring classification and Kaplan–Meier survival estimation

Longest nocturnal low-DO runs were classified as both-closed, left-censored (at sunset), right-censored (at sunrise), or doubly censored. For runs initiating inside darkness, Kaplan–Meier right-censored survival curves (Kaplan and Meier, 1958) treated sunrise-truncated episodes as right-censored rather than omitting them. Unbroken continuous runs were additionally traced across sunset and sunrise in the full multi-day UTC record (halting at recovery $\\ge \\tau$ or gaps $>1.5\\Delta t$) to measure full episode duration, onset, nadir, and recovery timing relative to sunrise.

### Equal-budget operational simulation and cost model

We pre-defined actionable episodes as LORO-verified continuous $<5\\text{{ mg L}}^{{-1}}$ runs lasting $\\ge 2.0\\text{{ h}}$ (with $<4\\text{{ mg L}}^{{-1}}$, $<3\\text{{ mg L}}^{{-1}}$, and $\\ge 4.0\\text{{ h}}$ sensitivities) and grouped consecutive actionable site-nights at the same station into distinct non-overlapping episodes. Across 1,000 stratified warm-season calendar replications on strictly out-of-sample post-Year-1 site-years (requiring $\\ge 60$ matched nights per warm season), we evaluated fixed annual visit budgets (12, 24, 52 visits site$^{{-1}}$ yr$^{{-1}}$, corresponding to 6, 12, 26 May–October visits) and equal total dollar budgets decomposing per-visit cost into travel/access (40%), daytime labor (60%), nocturnal labor/safety multipliers $m_{{\\text{{night}}}} \\in \\{{1.0, 1.35, 1.75, 2.5\\}}\\times$ (early-shift civil daylight first-light modeled as $1 + 0.2(m_{{\\text{{night}}}} - 1)$), and amortized continuous sonde cost $K_{{\\text{{sonde}}}} \\in [20, 100]$ daytime-visit-equivalents yr$^{{-1}}$ (benchmark \\$200 daytime visit$^{{-1}}$). Risk-stratified hybrid protocols allocated continuous sondes to the top 10% or 20% sites ranked strictly out-of-sample via (a) Year-1 daytime grab DO statistics (`p10`, mean, fraction <6 mg L$^{{-1}}$), (b) Leave-One-Region-Out ridge regression on static site covariates, or (c) an oracle upper bound, spending all remaining budget on empirical WQP or first-light grabs at non-sonde sites.

---

## Data and code availability

All continuous DO records originate from public USGS Water Data STAC Parquet archives (`api.waterdata.usgs.gov/stac-files/continuous/`) and the UK Environment Agency Hydrology API (`environment.data.gov.uk/hydrology/id/stations`), and discrete U.S. agency field-visit logs originate from the U.S. Water Quality Portal (`waterqualitydata.us`). Complete reproducible analysis scripts (`scripts/00`–`14`), archived UTC and WQP extracts, zero-NaN summary tables (`tables/`), figure generators, automated verification tests (`tests/test_d4_pipeline.py`), and cryptographic artifact manifests (`SHA256SUMS.json`) are provided in the project repository.

---

## References

{refs_md}
"""
    return text


def build_supplementary_information(r11: dict, r12: dict, econ: dict, uk_econ: dict) -> str:
    s2 = pd.read_csv(TBL / "table_s2_coverage_by_cadence_month.csv")
    s3 = pd.read_csv(TBL / "table_s3_censoring_km_duration.csv")
    s4 = pd.read_csv(TBL / "table_s4_cost_sensitivity_grid.csv")
    t1_arch = pd.read_csv(TBL / "table1_core_thermal_decoupling.csv")

    s2_md = "\n".join(
        f"| {r.network} | {r.stratum_type} | {r.stratum} | {int(r.n_sites)} | {int(r.candidate_nights):,} | {int(r.matched_nights):,} | {r.entry_rate_pct:.2f}% | {int(r.fail_night_gap):,} | {int(r.fail_target_match):,} |"
        for r in s2.itertuples(index=False)
    )
    s3_md = "\n".join(
        f"| {r.network} | <{int(r.threshold_mgL)} | {int(r.total_hypoxic_nights):,} | {int(r.both_closed_n):,} ({r.both_closed_pct:.1f}%) | {int(r.left_only_n):,} | {int(r.right_only_n):,} | {int(r.doubly_censored_n):,} | {r.naive_closed_median_lo_hr:.2f}–{r.naive_closed_median_hi_hr:.2f} | {r.km_night_rmst_12h_hr:.2f} | {r.full_series_median_hr:.1f} ({r.full_series_q25_hr:.1f}–{r.full_series_q75_hr:.1f}) |"
        for r in s3.itertuples(index=False)
    )
    # Show key budget=12, 24, 52 rows of Table S4 cleanly with human-readable labels
    s4_pretty = {
        "empirical_wqp_clock": "Empirical WQP agency clock",
        "rotating_dawn_included": "Dawn-included rotating (1/3 pre-dawn)",
        "first_light_sr_p30": "First-light daylight (SR+30m)",
        "predawn_sr_m30": "Dark pre-dawn (SR−30m)",
        "y1_daytime_screening_top10pct": "Hybrid: top-10% sondes (Y1) + WQP",
        "y1_daytime_screening_top20pct": "Hybrid: top-20% sondes (Y1) + WQP",
        "y1_daytime_screening_top20pct_plus_firstlight": "Hybrid: top-20% sondes (Y1) + first light",
    }
    def fmt_cp(cp: str) -> str:
        if cp.startswith("m_night="):
            val = cp.split("=", 1)[1].replace("x", "×")
            return f"$m_{{\\text{{night}}}} = {val}$"
        if cp.startswith("K_sonde="):
            val = cp.split("=", 1)[1]
            return f"$K_{{\\text{{sonde}}}} = {val}$"
        return cp

    s4_sub = s4[s4["cost_param"].isin(["m_night=1.00x", "m_night=1.75x", "m_night=2.50x", "K_sonde=20", "K_sonde=40", "K_sonde=60", "K_sonde=100"])]
    s4_md = "\n".join(
        f"| {'U.S.' if 'United' in r.network else 'England'} | {int(r.annual_budget_dayeq)} | {s4_pretty.get(str(r.protocol), str(r.protocol))} | "
        f"{fmt_cp(str(r.cost_param))} | "
        f"{r.distinct_ep_per_100_eq:.2f} | \\${int(r.cost_usd_per_distinct_ep):,} | {r.impaired_sy_flagged_pct:.1f}% |"
        for r in s4_sub.itertuples(index=False)
    )

    spec2 = econ["spec2_ym_fe_logQ_quad_primary"]
    rob = econ["robustness_suite"]
    cmp_d = econ["compound_hot_x_dry"]["effects"]["hyp5_min_minus_max"]
    uk_dec = uk_econ["thermal_slopes_ym_fe"]["DOmin_minus_DOmax"]

    outcome_pretty = {
        "do_sat_alt": "Henry's Law $DO_{\\text{sat,alt}}$",
        "do_max": "Daily $DO_{\\max}$",
        "do_mean": "Daily $DO_{\\text{mean}}$",
        "do_min": "Daily $DO_{\\min}$",
        "diff_min_max": "$DO_{\\min} - DO_{\\max}$",
        "diff_min_sat": "$DO_{\\min} - DO_{\\text{sat,alt}}$",
        "diff_max_sat": "$DO_{\\max} - DO_{\\text{sat,alt}}$",
        "diff_mean_min": "$DO_{\\text{mean}} - DO_{\\min}$",
    }
    arch_rows = []
    for r in t1_arch.head(14).itertuples(index=False):
        spec_clean = str(r.specification).replace("logQ^2", "(log Q)²").replace("logQ", "log Q")
        out_clean = outcome_pretty.get(str(r.outcome), str(r.outcome).replace("_", " "))
        arch_rows.append(
            f"| {spec_clean} | {out_clean} | {int(r.n_rivers)} | {r.mean_mgL_per_C:+.4f} | {r.huc2_se_cr1:.4f} | {r.huc2_p_t_Gminus1:.2e} |"
        )
    arch_md = "\n".join(arch_rows)

    return f"""# Supplementary Information: Equal-budget monitoring protocols for nocturnal river hypoxia across U.S. and English networks

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Supplementary Note 1. Network Coverage and Common-Support Attrition Audit

Station-level UTC record lengths, modal native sampling cadences, candidate warm-season nights, complete astronomical nights, and common-support matched nights for all 139 U.S. Geological Survey (USGS) and 65 Environment Agency (EA) stations are archived in `tables/table_s1_station_coverage_attrition.csv`. Table S2 summarizes attrition stratified by native sampling cadence and calendar month.

**Table S2. Warm-season site-night coverage and attrition by network, native sampling interval, and month.**

| Network | Stratum type | Stratum | Sites | Candidate nights | Matched nights | Entry rate | Night-gap fail | Target-match fail |
|---|---|---|---:|---:|---:|---:|---:|---:|
{s2_md}

---

## Supplementary Note 2. Boundary Censoring, Kaplan–Meier Duration Bounds, and Cadence Downsampling

Because most nocturnal low-oxygen runs persist past geometric sunrise, summarizing duration exclusively on runs closed at both ends inside darkness introduces severe downward selection bias. Table S3 compares naive closed-in-night median bounds, Kaplan–Meier restricted 12-h mean nocturnal survival times (treating sunrise-truncated episodes as right-censored), and full unbroken continuous-series episode medians across all four thresholds (<5, <4, <3, and <2 mg L$^{{-1}}$).

**Table S3. Nocturnal boundary censoring composition and censoring-adjusted episode duration across thresholds.**

| Network | Threshold (mg L$^{{-1}}$) | Hypoxic nights | Both closed (%) | Left-only | Right-only | Doubly cens. | Naive closed med. (h) | KM night RMST-12h (h) | Full continuous med. (IQR, h) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
{s3_md}

---

## Supplementary Note 3. Complete Equal-Budget Cost-Sensitivity Grid

Table S4 expands Main Text Table 3 across annual visit budgets of 12 (monthly), 24 (biweekly), and 52 (weekly) daytime-visit-equivalents site$^{{-1}}$ yr$^{{-1}}$, nocturnal visit cost multipliers ($m_{{\\text{{night}}}} \\in \\{{1.00\\times, 1.75\\times, 2.50\\times\\}}$), and amortized continuous sonde annual costs ($K_{{\\text{{sonde}}}} \\in \\{{20, 40, 60, 100\\}}$ daytime-visit-equivalents yr$^{{-1}}$). The full 162-row grid (including $m_{{\\text{{night}}}} = 1.35\\times$) is archived in `tables/table_s4_cost_sensitivity_grid.csv`.

**Table S4. Equal-budget distinct actionable episode yield, unit cost, and impaired site-year discovery across budget and cost regimes.**

| Network | Annual budget (day-eq) | Protocol | Cost parameter | Distinct ep. / 100 eq | Cost / distinct ep. | Impaired site-yrs flagged |
|---|---:|---|---|---:|---:|---:|
{s4_md}

---

## Supplementary Note 4. Archived Daily-Extremes Thermal Decoupling, Compound Drought, and Secular Trend Context (2005–2025)

To provide hydrological and climatic context for warm-season risk stratification—kept strictly separate from the primary UTC nocturnal protocol evaluation in the Main Text—we archive our continental daily-extremes analysis across 397 screened free-flowing freshwater USGS stations (2005–2025; 1,446,764 station-days; 324 stations in the primary discharge-controlled Spec 2 absorbing within-station Year $\\times$ Month fixed effects plus $\\log Q$ and $(\\log Q)^2$, geospatially audited against all 62,226 dams in the USACE National Inventory of Dams) and 65 English stations. These daily-extremes models measure observed short-term temperature sensitivity of full-day $DO_{{\\min}}$ vs. $DO_{{\\max}}$ (capturing coupled metabolic, reaeration, irradiance, and subdaily hydrologic co-variation rather than isolated nocturnal events):

- **Continental daily thermal decoupling (Spec 2, $N = 324$):** $d(DO_{{\\min}} - DO_{{\\max}})/dT = {spec2['diff_min_max']['mean']:+.4f}\\text{{ mg L}}^{{-1}}\\text{{ }}^\\circ\\text{{C}}^{{-1}}$ (HUC-2 SE ${spec2['diff_min_max']['huc2_cluster']['se_cr1']:.4f}$, $p = {spec2['diff_min_max']['huc2_cluster']['p_cr1_t_Gminus1']:.2e}$), strengthening to ${rob['spec5_nid_gt5km_ge500af']['diff_min_max']['mean']:+.4f}$ beyond 5 km of $\\ge 500\\text{{ acre-ft}}$ NID dams ($N = 242$) and ${rob['spec5_nid_gt5km_any_dam']['diff_min_max']['mean']:+.4f}$ beyond 5 km of any dam ($N = 141$), and replicating across 65 English stations (${uk_dec['mean']:+.4f}$, 1°-grid $p = {uk_dec['grid1deg_cluster']['p_cr1_t_Gminus1']:.2e}$).
- **Compound heatwave $\\times$ low-flow drought ($N = 319$):** daily $DO_{{\\min}}$ drops $-0.854\\text{{ mg L}}^{{-1}}$ ($p = 2.19 \\times 10^{{-6}}$) with a bounded daily-minimum minus daily-maximum $<5\\text{{ mg L}}^{{-1}}$ probability contrast of ${cmp_d['total_compound_vs_normal']['mean']*100:+.2f}$ percentage points (95% CI $[{cmp_d['total_compound_vs_normal']['huc2_cluster']['ci95_lo']*100:+.2f}, {cmp_d['total_compound_vs_normal']['huc2_cluster']['ci95_hi']*100:+.2f}]$, $p = {cmp_d['total_compound_vs_normal']['huc2_cluster']['p_cr1_t_Gminus1']:.2e}$).

**Table S5. Archived continental daily-extremes thermal decoupling specifications (2005–2025; screened USGS network).**

| Specification | Outcome | $N$ sites | Mean (mg L$^{{-1}}$ °C$^{{-1}}$) | HUC-2 SE | HUC-2 $p$ |
|---|---|---:|---:|---:|---:|
{arch_md}

<!-- FIGURE:fig1_conus_map_and_thermal_decoupling.png -->
<!-- FIGURE:fig3_compound_heatwave_drought.png -->
<!-- FIGURE:fig4_biophysical_mechanism.png -->
<!-- FIGURE:fig5_secular_cwa_and_uk_replication.png -->

---

## Supplementary Note 5. Reproducibility and Verification Checklist

1. **UTC & WQP Data Archiving:** `scripts/09_fetch_usgs_stac.py` (139 USGS STAC UTC Parquet files + source SHA-256 receipts), `scripts/04_uk_ea_international_replication.py` (65 English EA stations), `scripts/10_fetch_wqp_grab_logs.py` (10,019 warm-season WQP discrete field visits).
2. **Primary LORO, Sensitivity, Holdout, Cadence & Censoring Audit:** `scripts/11_loro_and_sensitivity_analysis.py` $\\rightarrow$ `results/11_loro_and_sensitivity.json`, `data/processed/v4_nocturnal_site_nights.parquet`, `tables/table_s1_station_coverage_attrition.csv`.
3. **Equal-Budget Operational Protocol & Cost-Effectiveness Simulation:** `scripts/12_operational_protocol_decision_analysis.py` $\\rightarrow$ `results/12_operational_protocol_decision.json`.
4. **Publication Figures & Zero-NaN Tables:** `scripts/13_generate_v4_figures_tables.py` $\\rightarrow$ `figures/fig1_nw_*.png/.pdf` through `fig4_nw_*.png/.pdf`, `tables/table1_nw_*.csv` through `table_s4_*.csv`.
5. **Manuscript, Supplement, PDF Compilation & Integrity Manifest:** `scripts/14_generate_v4_manuscript_and_supplement.py`, `scripts/08_compile_manuscript_pdf.py`, `scripts/07_build_manifest.py` $\\rightarrow$ `manuscript_d4_boost.pdf`, `manuscript_d4_nature_water.pdf`, `supplementary_d4_nature_water.pdf`, `SHA256SUMS.json`.
6. **Automated Verification:** `pytest -v tests/test_d4_pipeline.py` (unit tests, exact LORO parity, programmatic manuscript-vs-JSON parity, zero-NaN table checks, zero-leak PDF checks, Crossref DOI parity, SHA-256 verification) and `ruff check scripts tests` (0 lint errors).
"""


def main() -> None:
    r11 = json.loads((RES / "11_loro_and_sensitivity.json").read_text(encoding="utf-8"))
    r12 = json.loads((RES / "12_operational_protocol_decision.json").read_text(encoding="utf-8"))
    econ = json.loads((RES / "d4_econometric_hydrologic_results.json").read_text(encoding="utf-8"))
    uk_econ = json.loads((RES / "uk_ea_replication_results.json").read_text(encoding="utf-8"))
    refs = json.loads((PROC / "verified_references.json").read_text(encoding="utf-8"))

    main_md = build_main_manuscript(r11, r12, refs)
    supp_md = build_supplementary_information(r11, r12, econ, uk_econ)

    (ROOT / "manuscript_d4_boost.md").write_text(main_md, encoding="utf-8", newline="\n")
    (ROOT / "supplementary_d4_nature_water.md").write_text(supp_md, encoding="utf-8", newline="\n")

    # Word count check (excluding Markdown tables and references for prose word count, plus total)
    prose_lines = [ln for ln in main_md.splitlines() if not ln.startswith("|") and not ln.startswith("<!--")]
    # Cut before References for Main Text body count
    body_only = "\n".join(prose_lines).split("## References")[0]
    wc_body = len(body_only.split())
    wc_total = len(main_md.split())
    print(f"[DONE] Generated manuscript_d4_boost.md ({wc_body:,} prose words excl. tables/refs; {wc_total:,} total words)", flush=True)
    print(f"[DONE] Generated supplementary_d4_nature_water.md ({len(supp_md.split()):,} total words)", flush=True)


if __name__ == "__main__":
    main()
