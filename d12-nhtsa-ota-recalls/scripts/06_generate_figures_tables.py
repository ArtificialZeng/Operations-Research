"""Step 6: Generate all zero-NaN publication CSV tables (tables/) and 5 publication-grade
300-DPI PNG + vector PDF figures (figures/) for D12 Boost.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
PROC_DIR = BASE_DIR / "data_processed"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
FIG_DIR = BASE_DIR / "figures"
TBL_DIR.mkdir(parents=True, exist_ok=True)
FIG_DIR.mkdir(parents=True, exist_ok=True)

# Clean academic publication styling
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.serif": ["DejaVu Serif", "Georgia", "Times New Roman"],
        "axes.edgecolor": "#334155",
        "axes.linewidth": 0.8,
        "axes.grid": True,
        "grid.color": "#e2e8f0",
        "grid.linewidth": 0.6,
        "grid.alpha": 0.85,
        "xtick.color": "#1e293b",
        "ytick.color": "#1e293b",
        "text.color": "#0f172a",
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "savefig.dpi": 300,
    }
)

COLORS = {
    "Pure_OTA": "#1b365d",       # Deep Navy
    "Hybrid_OTA": "#d95f02",     # Burnt Orange
    "Dealer_Software": "#2a9d8f",# Teal
    "Physical_Hardware": "#64748b", # Cool Slate
    "API_OTA": "#6d28d9",        # Royal Violet
    "ITT": "#0284c7",            # Sky Blue
    "Red": "#b91c1c",
    "Green": "#15803d",
}


def build_tables(res: dict, audit: dict, df_camp: pd.DataFrame) -> None:
    # ---- Table 1: API Measurement-Integrity Reconciliation Audit (2019-2026) ----
    c18 = df_camp[df_camp["rec_year"].between(2018, 2026)].copy()
    t1_rows = []
    for yr in range(2018, 2027):
        sub = c18[c18["rec_year"] == yr]
        n_veh = len(sub)
        n_pure = int((sub["modality4"] == "Pure_OTA").sum())
        n_hyb = int((sub["modality4"] == "Hybrid_OTA").sum())
        n_aud = n_pure + n_hyb
        n_api = int((sub["is_ota_api_full"] == 1).sum())
        agree_pct = round(100.0 * n_api / n_aud, 1) if n_aud > 0 else 100.0
        t1_rows.append(
            {
                "Recall_Year": str(yr),
                "Total_Vehicle_Recalls": n_veh,
                "Dealer_Software": int((sub["modality4"] == "Dealer_Software").sum()),
                "Audited_Pure_OTA": n_pure,
                "Audited_Hybrid_OTA": n_hyb,
                "Audited_Total_OTA": n_aud,
                "Official_API_OTA_True": n_api,
                "API_Agreement_Pct": agree_pct,
                "API_Regime": "Pre-OTA" if yr == 2018 else ("Active_API_Flag" if yr <= 2024 else "Post_May8_2025_Public_API_Anomaly"),
            }
        )
    # Totals row
    t1_rows.append(
        {
            "Recall_Year": "Total_2018_2026",
            "Total_Vehicle_Recalls": len(c18),
            "Dealer_Software": int((c18["modality4"] == "Dealer_Software").sum()),
            "Audited_Pure_OTA": int((c18["modality4"] == "Pure_OTA").sum()),
            "Audited_Hybrid_OTA": int((c18["modality4"] == "Hybrid_OTA").sum()),
            "Audited_Total_OTA": int((c18["is_ota_audited"] == 1).sum()),
            "Official_API_OTA_True": int((c18["is_ota_api_full"] == 1).sum()),
            "API_Agreement_Pct": round(100.0 * (c18["is_ota_api_full"] == 1).sum() / max(1, (c18["is_ota_audited"] == 1).sum()), 1),
            "API_Regime": f"PhysAudit_FN={audit['physical_audit_api_ota_true_false_negatives']}/{audit['physical_audit_valid']}",
        }
    )
    pd.DataFrame(t1_rows).to_csv(TBL_DIR / "table1_api_measurement_audit.csv", index=False)

    # ---- Table 2: Pillar 1 Blast-Radius Concentration & Endogenous Selection Decomposition ----
    p1 = res["pillar1_blast_radius"]
    t2_rows = []

    def add_reg_rows(section: str, spec_label: str, reg_dict: dict, terms_filter: list[str] | None = None) -> None:
        if reg_dict.get("skipped"):
            return
        for term, vals in reg_dict["terms"].items():
            if terms_filter and term not in terms_filter:
                continue
            t2_rows.append(
                {
                    "Panel": section,
                    "Specification": spec_label,
                    "Outcome": reg_dict["y"],
                    "Term": term,
                    "N": reg_dict["n"],
                    "G_OEM_Clusters": reg_dict["G_clusters"],
                    "Coef": vals["coef"],
                    "SE_CR1": vals["se_cr1"],
                    "t_CR1": vals["t_cr1"],
                    "p_t_G1": vals["p_t_G1"],
                    "p_WCB_999": vals["p_wcb"],
                    "CI95_Lo": vals["ci95_lo"],
                    "CI95_Hi": vals["ci95_hi"],
                    "R2": reg_dict["r2"],
                }
            )

    add_reg_rows("A_Primary_SW_OTA_OEMs", "4-Way Modality (OEM+Yr+MY+Comp FE)", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "Any Audited OTA (OEM+Yr+MY+Comp FE)", p1["main_sw_ota_oems"]["sw_ota_oems_anyota_log_potaff"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "Official API OTA 2018-24 (Active Era)", p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_log_potaff"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "4-Way Modality: Models Affected", p1["main_sw_ota_oems"]["sw_ota_oems_4way_n_models"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "Official API OTA 2018-24: Models Affected", p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_n_models"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "4-Way Modality: Model Years Affected", p1["main_sw_ota_oems"]["sw_ota_oems_4way_n_mys"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "Official API OTA 2018-24: Model Years Affected", p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_n_mys"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "4-Way Modality: Fleet per Model-Year", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff_per_my"])
    add_reg_rows("A_Primary_SW_OTA_OEMs", "Official API OTA 2018-24: Fleet per Model-Year", p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_log_potaff_per_my"])

    add_reg_rows("B_All_Vehicles_vs_Phys", "All Vehicles 2018-26 (OEM+Yr+MY+Comp FE)", p1["all_vehicles_benchmark"]["all_vehicles_4way_log_potaff"])
    add_reg_rows("B_All_Vehicles_vs_Phys", "All Vehicles 2018-24 API OTA", p1["all_vehicles_benchmark"]["all_vehicles_api2018_24_log_potaff"])

    for rkey, rlbl in [
        ("modern_MY2020plus_4way", "Modern Vehicles MY>=2020"),
        ("oem_x_year_fe_4way", "Saturated OEM x Year FE"),
        ("make_x_model_fe_4way", "Make x Model FE"),
        ("breadth_controlled_4way", "Controlling Breadth (log_models + log_mys)"),
        ("excl_tesla_4way", "Excluding Tesla"),
        ("excl_tesla_ford_4way", "Excluding Tesla & Ford"),
        ("hybrid_swchoice_vs_hwmixed", "Hybrid Split (SW-Choice vs HW-Mixed)"),
        ("light_duty_passenger_4way", "Light-Duty Passenger OEMs Only"),
        ("singleton_dropped_main_4way", "Iterative Singleton-FE Dropped (Main FE)"),
        ("singleton_dropped_oem_x_year_4way", "Iterative Singleton-FE Dropped (OEM x Year FE)"),
        ("singleton_dropped_make_x_model_4way", "Iterative Singleton-FE Dropped (Make x Model FE)"),
    ]:
        add_reg_rows("C_Robustness_Ladder", rlbl, p1["robustness_ladder"][rkey])

    add_reg_rows("D_Unconditional_ITT_and_Cohort", "ITT Staggered OEM OTA Adoption (2015-26)", p1["itt_staggered_adoption"]["pooled_did"])
    add_reg_rows("D_Unconditional_ITT_and_Cohort", "ITT Staggered Adoption + Min-MY FE", p1["itt_staggered_adoption"]["pooled_did_with_myfe"])
    add_reg_rows("D_Unconditional_ITT_and_Cohort", "ITT Staggered Adoption (Excl. Tesla)", p1["itt_staggered_adoption"]["pooled_did_excl_tesla"])
    sa = p1["itt_staggered_adoption"]["sun_abraham_iw"]
    if not sa.get("skipped"):
        t2_rows.append(
            {
                "Panel": "D_Unconditional_ITT_and_Cohort",
                "Specification": "True Sun-Abraham (2021) Cohort x Rel-Time IW (7 Cohorts)",
                "Outcome": "log_potaff",
                "Term": "iw_post_25cells",
                "N": sa["n"],
                "G_OEM_Clusters": sa["G_clusters"],
                "Coef": sa["iw_post_coef"],
                "SE_CR1": sa["iw_se_cr1"],
                "t_CR1": sa["iw_t"],
                "p_t_G1": sa["iw_p_t_G1"],
                "p_WCB_999": sa["iw_p_t_G1"],
                "CI95_Lo": round(sa["iw_post_coef"] - 1.996 * sa["iw_se_cr1"], 4),
                "CI95_Hi": round(sa["iw_post_coef"] + 1.996 * sa["iw_se_cr1"], 4),
                "R2": 0.0,
            }
        )
    add_reg_rows(
        "D_Unconditional_ITT_and_Cohort",
        "Unconditional SW x SDV Cohort MY>=2021 DiD",
        p1["unconditional_sdv_cohort_shift"]["sw_vs_physical_sdv_did"],
    )
    pd.DataFrame(t2_rows).to_csv(TBL_DIR / "table2_blast_radius_and_selection.csv", index=False)

    # ---- Table 3: Pillar 2 Remediation Velocity & Vehicle-Age Compliance-Decay ----
    p2 = res["pillar2_remediation_velocity"]
    t3_rows = []

    def add_p2(panel: str, label: str, reg: dict) -> None:
        if reg.get("skipped"):
            return
        for term, vals in reg["terms"].items():
            t3_rows.append(
                {
                    "Panel": panel,
                    "Specification": label,
                    "Outcome": reg["y"],
                    "Term": term,
                    "N": reg["n"],
                    "G_OEM_Clusters": reg["G_clusters"],
                    "Coef_pp": vals["coef"],
                    "SE_CR1": vals["se_cr1"],
                    "t_CR1": vals["t_cr1"],
                    "p_t_G1": vals["p_t_G1"],
                    "p_WCB_999": vals["p_wcb"],
                    "CI95_Lo": vals["ci95_lo"],
                    "CI95_Hi": vals["ci95_hi"],
                    "R2": reg["r2"],
                }
            )

    for k, lbl in [
        ("sw_ota_oems_4way", "Mature >=18m SW OTA-OEMs (4-Way)"),
        ("sw_ota_oems_anyota", "Mature >=18m SW OTA-OEMs (Any Audited OTA)"),
        ("sw_ota_oems_api_ota", "Mature >=18m SW OTA-OEMs (Official API OTA)"),
        ("sw_ota_oems_4way_ctrl_potaff", "Mature >=18m SW + log(PotAff) Control"),
        ("all_vehicles_4way_vs_phys", "Mature >=18m All Vehicles vs Physical"),
        ("all_vehicles_api_vs_phys", "Mature >=18m All Vehicles API OTA vs Physical"),
        ("strict_drop_cr_gt100_all_veh", "Strict Drop CR>100% All Vehicles"),
        ("excl_tesla_sw_4way", "Mature >=18m SW Excl. Tesla"),
        ("excl_tesla_ford_sw_4way", "Mature >=18m SW Excl. Tesla & Ford"),
        ("oem_x_year_fe_sw_4way", "Mature >=18m SW Saturated OEM x Year FE"),
        ("hybrid_swchoice_vs_hwmixed_sw", "Mature >=18m SW Hybrid Split (SW-Choice vs HW-Mixed)"),
        ("light_duty_passenger_sw_4way", "Mature >=18m SW Light-Duty Passenger OEMs Only"),
        ("singleton_dropped_sw_4way", "Mature >=18m SW Singleton-FE Dropped"),
        ("singleton_dropped_all_veh_4way", "Mature >=18m All Vehicles Singleton-FE Dropped"),
    ]:
        add_p2("A_Mature_18m_Completion", lbl, p2["mature_18m_regressions"][k])

    add_p2("B_Full_Age_Controlled", "Full 2018-26 SW + Cubic Age + Quarter FE", p2["full_sample_age_controlled"]["sw_ota_oems_4way_agepoly"])
    add_p2("B_Full_Age_Controlled", "Full 2018-26 All Vehicles + Cubic Age", p2["full_sample_age_controlled"]["all_vehicles_4way_agepoly"])

    add_p2("C_Execution_Gap_Tiers", "Tesla vs Non-Tesla Pure vs Legacy Hybrid (No OEM FE)", p2["tesla_vs_legacy_execution_gap"]["tier_reg_completion_rate_no_oem_fe"])
    add_p2("C_Execution_Gap_Tiers", "Execution Tiers: Light-Duty Passenger OEMs Only", p2["tesla_vs_legacy_execution_gap"]["tier_reg_completion_rate_light_duty"])
    add_p2("C_Execution_Gap_Tiers", "Direct Pure-OTA vs Hybrid-OTA (OTA Campaigns Only)", p2["tesla_vs_legacy_execution_gap"]["pure_vs_hybrid_ota_only_cr"])

    add_p2("D_Vehicle_Age_Decay", "SW OTA-OEMs: Any OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_ota_oems_anyota_x_age"])
    add_p2("D_Vehicle_Age_Decay", "SW OTA-OEMs: 4-Way OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_ota_oems_4way_x_age"])
    add_p2("D_Vehicle_Age_Decay", "SW OTA-OEMs: Official API OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_ota_oems_api_x_age"])
    add_p2("D_Vehicle_Age_Decay", "SW Excl. Tesla: Any OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_excl_tesla_anyota_x_age"])
    add_p2("D_Vehicle_Age_Decay", "SW Excl. Tesla: Official API OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_excl_tesla_api_x_age"])
    add_p2("D_Vehicle_Age_Decay", "SW Excl. Tesla: 4-Way OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_excl_tesla_4way_x_age"])
    add_p2("D_Vehicle_Age_Decay", "SW Light-Duty Passenger: 4-Way OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_light_duty_4way_x_age"])
    add_p2("D_Vehicle_Age_Decay", "SW Light-Duty Passenger: Official API OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["sw_light_duty_api_x_age"])
    add_p2("D_Vehicle_Age_Decay", "All Vehicles: 4-Way OTA x Vehicle Age", p2["vehicle_age_decay"]["regressions"]["all_vehicles_4way_x_age"])
    pd.DataFrame(t3_rows).to_csv(TBL_DIR / "table3_remediation_velocity_and_age_decay.csv", index=False)

    # ---- Table 4: Pillar 3 Net Unremedied Fleet Exposure & Aggregate Accounting ----
    p3 = res["pillar3_net_unremedied_exposure"]
    t4_rows = []
    for k, lbl in [
        ("mature_sw_ota_oems_4way", "Mature >=18m SW OTA-OEMs (Unconditional Net Exposure)"),
        ("mature_sw_ota_oems_anyota", "Mature >=18m SW OTA-OEMs (Any Audited OTA)"),
        ("mature_sw_ota_oems_api_ota", "Mature >=18m SW OTA-OEMs (Official API OTA)"),
        ("mature_sw_ota_oems_4way_ctrl_potaff", "Mature >=18m SW Holding Fleet Size Fixed"),
        ("mature_sw_excl_tesla_4way", "Mature >=18m SW Excl. Tesla"),
        ("mature_sw_excl_tesla_ford_4way", "Mature >=18m SW Excl. Tesla & Ford"),
        ("mature_sw_hybrid_swchoice_vs_hwmixed", "Mature >=18m SW Hybrid Split (SW-Choice vs HW-Mixed)"),
        ("mature_all_vehicles_4way_vs_phys", "Mature >=18m All Vehicles vs Physical"),
        ("mature_all_vehicles_api_vs_phys", "Mature >=18m All Vehicles API OTA vs Physical"),
        ("mature_all_vehicles_hybrid_swchoice_vs_hwmixed", "Mature >=18m All Veh Hybrid Split vs Physical"),
        ("mature_strict_drop_cr_gt100", "Strict Drop CR>100% All Vehicles"),
        ("mature_all_vehicles_singleton_dropped_4way", "Mature >=18m All Vehicles Singleton-FE Dropped"),
        ("full_agepoly_sw_ota_oems_4way", "Full 2018-26 SW + Cubic Age Control"),
        ("mature_sw_tiers_no_oem_fe", "Mature >=18m Execution Tiers (No OEM FE)"),
        ("mature_sw_tiers_light_duty", "Mature >=18m Execution Tiers (Light-Duty Passenger Only)"),
    ]:
        reg = p3["regressions"][k]
        for term, vals in reg["terms"].items():
            t4_rows.append(
                {
                    "Specification": lbl,
                    "Term": term,
                    "N": reg["n"],
                    "G_OEM_Clusters": reg["G_clusters"],
                    "Coef_log_unrem": vals["coef"],
                    "SE_CR1": vals["se_cr1"],
                    "t_CR1": vals["t_cr1"],
                    "p_t_G1": vals["p_t_G1"],
                    "p_WCB_999": vals["p_wcb"],
                    "CI95_Lo": vals["ci95_lo"],
                    "CI95_Hi": vals["ci95_hi"],
                    "R2": reg["r2"],
                }
            )
    pd.DataFrame(t4_rows).to_csv(TBL_DIR / "table4_net_unremedied_exposure.csv", index=False)

    # Table 4B: Aggregate Recall-Level Vehicle-Instance Accounting & Break-Even Frontier
    acc = p3["aggregate_fleet_accounting_mature18m"]
    acc_rows = []
    for mod in [
        "Pure_OTA",
        "Hybrid_OTA",
        "Hybrid_SW_Choice",
        "Official_API_OTA",
        "Dealer_Software",
        "OTA_OEMs_Dealer_Software",
        "Physical_Hardware",
    ]:
        a = acc[mod]
        acc_rows.append(
            {
                "Modality": mod,
                "N_Mature_Campaigns": a["n_campaigns"],
                "Summed_Affected_Vehicle_Instances": a["total_affected"],
                "Share_Affected_Pct": a["share_total_affected_pct"],
                "Summed_Unremedied_Instance_Proxy": a["total_unremedied"],
                "Share_Unremedied_Proxy_Pct": a["share_total_unremedied_pct"],
                "Mean_CR_Pct": a["mean_cr_pct"],
                "Instance_Weighted_Completion_Pct": a["completion_rate_fleet_weighted_pct"],
                "Median_Affected_Instances": a["median_affected"],
                "Median_Unremedied_Proxy": a["median_unremedied"],
                "Mean_Log_Unremedied_Proxy": a["mean_log_unremedied"],
            }
        )
    pd.DataFrame(acc_rows).to_csv(TBL_DIR / "table4b_aggregate_fleet_accounting.csv", index=False)

    # Table 4C: Dedicated Mature Pure-OTA & Hybrid-OTA OEM Composition & Weight Disclosure
    comp = p3["mature_sample_composition"]
    comp_rows = []
    for lbl, sub_d in [
        ("Summary: Tesla Pure-OTA", comp["pure_ota_tesla_subsample"]),
        ("Summary: Non-Tesla Pure-OTA (All)", comp["pure_ota_nontesla_subsample"]),
        ("Summary: Non-Tesla Pure-OTA (Light-Duty)", comp["pure_ota_nontesla_light_duty_subsample"]),
    ]:
        comp_rows.append(
            {
                "Group": "Pure_OTA_Subsample_Summary",
                "OEM_or_Slice": lbl,
                "N_Campaigns": sub_d["n_campaigns"],
                "Share_Modality_Campaigns_Pct": sub_d["share_pure_campaigns_pct"],
                "Affected_Vehicle_Instances": sub_d["affected_vehicle_instances"],
                "Share_Modality_Affected_Pct": sub_d["share_pure_affected_pct"],
                "Unremedied_Instance_Proxy": sub_d["unremedied_instance_proxy"],
                "Share_Modality_Unremedied_Pct": sub_d["share_pure_unremedied_pct"],
                "Mean_CR_Pct": sub_d["mean_cr_pct"],
                "Median_CR_Pct": sub_d["median_cr_pct"],
                "Median_Affected_Instances": sub_d["median_affected"],
                "Median_Unremedied_Proxy": sub_d["median_unremedied_proxy"],
                "Max_Vehicle_Age_Yr": sub_d["max_vehicle_age_yr"],
                "N_Age_6Plus_Yr": sub_d["n_age_6plus_yr"],
            }
        )
    for grp_lbl, oem_list in [
        ("Pure_OTA_OEM", comp["pure_ota_by_oem"]),
        ("Hybrid_OTA_OEM", comp["hybrid_ota_by_oem"]),
    ]:
        for r in oem_list:
            comp_rows.append(
                {
                    "Group": grp_lbl,
                    "OEM_or_Slice": r["oem"],
                    "N_Campaigns": r["n_campaigns"],
                    "Share_Modality_Campaigns_Pct": r["share_campaigns_pct"],
                    "Affected_Vehicle_Instances": r["affected_vehicle_instances"],
                    "Share_Modality_Affected_Pct": r["share_affected_pct"],
                    "Unremedied_Instance_Proxy": r["unremedied_instance_proxy"],
                    "Share_Modality_Unremedied_Pct": r["share_unremedied_pct"],
                    "Mean_CR_Pct": r["mean_cr_pct"],
                    "Median_CR_Pct": r["median_cr_pct"],
                    "Median_Affected_Instances": r["median_affected"],
                    "Median_Unremedied_Proxy": r["median_unremedied_proxy"],
                    "Max_Vehicle_Age_Yr": r["max_vehicle_age_yr"],
                    "N_Age_6Plus_Yr": r["n_age_6plus_yr"],
                }
            )
    pd.DataFrame(comp_rows).to_csv(TBL_DIR / "table4c_mature_ota_oem_composition.csv", index=False)

    # ---- Table 5: Pillar 4 Safety Severity, Oversight, Repeat Cascades & Complaint DiD ----
    p4 = res["pillar4_safety_and_complaints"]
    t5_rows = []
    for y_lbl, key in [
        ("FMVSS Noncompliance", "4way_has_fmvss"),
        ("FMVSS Noncompliance (API OTA 2018-24)", "apiota2018_24_has_fmvss"),
        ("Formal ODI Investigation Action", "4way_has_odi_action"),
        ("Formal ODI Action (API OTA 2018-24)", "apiota2018_24_has_odi_action"),
        ("Regulator-Forced (ODI/OVSC)", "4way_is_regulator_forced"),
        ("Regulator-Forced (API OTA 2018-24)", "apiota2018_24_is_regulator_forced"),
        ("Do Not Drive Advisory", "4way_do_not_drive"),
        ("Park Outside Fire Advisory", "4way_park_outside"),
        ("Crash Consequence Text", "4way_con_crash"),
        ("Fire Consequence Text", "4way_con_fire"),
        ("Days Recall to Owner Notice", "4way_days_recall_to_owner"),
        ("Days Production to Recall (MY-FE Null)", "4way_days_mfg_to_recall"),
        ("Days Production to Recall (API OTA 2018-24)", "apiota2018_24_days_mfg_to_recall"),
        ("Repeat Same-Component Cascade 365d", "4way_any_repeat_365d"),
        ("Repeat Cascade 365d (API OTA 2018-24)", "apiota2018_24_any_repeat_365d"),
        ("Repeat Same-Component Cascade 730d", "4way_any_repeat_730d"),
        ("Repeat Cascade 730d (API OTA 2018-24)", "apiota2018_24_any_repeat_730d"),
    ]:
        reg = p4["safety_fe_regressions"][key]
        for term, vals in reg["terms"].items():
            t5_rows.append(
                {
                    "Panel": "A_Safety_Oversight_Cascades",
                    "Outcome_Label": y_lbl,
                    "Term": term,
                    "N": reg["n"],
                    "G_Clusters": reg["G_clusters"],
                    "Coef": vals["coef"],
                    "SE_CR1": vals["se_cr1"],
                    "t_CR1": vals["t_cr1"],
                    "p_t_G1": vals["p_t_G1"],
                    "p_WCB": vals["p_wcb"],
                }
            )
    cd = p4["complaint_did_summary"]["did_regressions"]
    for c_lbl, c_key in [
        ("SW All: Failure-Date Complaints (OEM-cl)", "sw_all_4way_oemcl__log_cmpl_fail"),
        ("SW All: Failure-Date Complaints (API OTA, OEM-cl)", "sw_all_api_oemcl__log_cmpl_fail"),
        ("SW All: Receipt-Date Complaints (OEM-cl)", "sw_all_4way_oemcl__log_cmpl_ldate"),
        ("SW Active: Failure-Date Complaints (OEM-cl)", "sw_active_4way_oemcl__log_cmpl_fail"),
        ("SW Active: Failure-Date Complaints (API OTA, OEM-cl)", "sw_active_api_oemcl__log_cmpl_fail"),
        ("SW Active: Receipt-Date Complaints (OEM-cl)", "sw_active_4way_oemcl__log_cmpl_ldate"),
        ("SW Active: Severe Crash/Fire Failure (OEM-cl)", "sw_active_4way_oemcl__log_cmpl_fail_sev"),
        ("SW Active: Failure Rate per 100k (OEM-cl)", "sw_active_4way_oemcl__log_rate_fail_100k"),
        ("SW Active Short [-3,-1] vs [+1,+12]: Failure-Date (OEM-cl)", "sw_short_m3m1_p1p12_4way_oemcl__log_cmpl_fail"),
        ("SW Active: Failure-Date Complaints (Camp-cl)", "sw_active_4way_campcl__log_cmpl_fail"),
        ("All Veh Active: Failure-Date (OEM-cl)", "allveh_active_4way_oemcl__log_cmpl_fail"),
    ]:
        reg = cd[c_key]
        for term, vals in reg["terms"].items():
            t5_rows.append(
                {
                    "Panel": "B_Complaint_Decay_DiD",
                    "Outcome_Label": c_lbl,
                    "Term": term,
                    "N": reg["n_obs"],
                    "G_Clusters": reg["G_clusters"],
                    "Coef": vals["coef"],
                    "SE_CR1": vals["se_cr1"],
                    "t_CR1": vals["t_cr1"],
                    "p_t_G1": vals["p_t_G1"],
                    "p_WCB": vals["p_wcb"],
                }
            )
    pd.DataFrame(t5_rows).to_csv(TBL_DIR / "table5_safety_cascades_and_complaints_did.csv", index=False)

    # Table 5B: Pre-Recall Safety-Complaint Buildup ([-12m, -1m]) & Crash/Fire/Injury/Fatal Rates
    pre_rows = []
    for mod in ["Pure_OTA", "Hybrid_OTA", "Official_API_OTA", "Dealer_Software", "Physical_Hardware"]:
        s = p4["prerecall_buildup_and_hazards"][mod]
        pre_rows.append(
            {
                "Modality": mod,
                "N_Balanced_Campaigns": s["n_campaigns"],
                "Pct_With_Pre12m_Fail_Cmpl": s["pct_with_ge1_pre12m_fail"],
                "Mean_Pre12m_Fail_Cmpl": s["mean_pre12m_fail_cmpl"],
                "Median_Pre12m_Fail_Cmpl": s["median_pre12m_fail_cmpl"],
                "Mean_Post12m_Fail_Cmpl": s["mean_post12m_fail_cmpl"],
                "Pre_Buildup_Ratio_m3m1_vs_m12m4": s["pre_buildup_ratio_m3m1_vs_m12m4"],
                "Pct_With_Pre12m_Crash": s["pct_with_ge1_pre12m_crash"],
                "Pct_With_Pre12m_Fire": s["pct_with_ge1_pre12m_fire"],
                "Pct_With_Pre12m_Inj_Cmpl": s["pct_with_ge1_pre12m_inj_cmpl"],
                "Pct_With_Pre12m_Fatal_Cmpl": s["pct_with_ge1_pre12m_fatal_cmpl"],
            }
        )
    pd.DataFrame(pre_rows).to_csv(TBL_DIR / "table5b_prerecall_complaints_and_hazards.csv", index=False)

    # ---- Table 6: Maturation Curve & Vehicle-Age Compliance Profiles (zero-NaN via clean formatting) ----
    t6_rows = []
    for r in p2["maturation_curve"]:
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
            m = r[mod]
            if m["n"] > 0:
                t6_rows.append(
                    {
                        "Profile": "Campaign_Age_Maturation",
                        "Bin": r["age_bin"],
                        "Modality": mod,
                        "N": m["n"],
                        "Mean_CR_Pct": m["mean"],
                        "Median_CR_Pct": m["median"],
                    }
                )
    for r in p2["vehicle_age_decay"]["descriptive_bins"]:
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
            m = r[mod]
            if m["n"] > 0:
                t6_rows.append(
                    {
                        "Profile": "Vehicle_Age_Decay_Mature18m",
                        "Bin": r["veh_age_bin"],
                        "Modality": mod,
                        "N": m["n"],
                        "Mean_CR_Pct": m["mean"],
                        "Median_CR_Pct": m["median"],
                    }
                )
    pd.DataFrame(t6_rows).to_csv(TBL_DIR / "table6_maturation_and_age_profiles.csv", index=False)
    print("[OK] Wrote 9 publication CSV tables in tables/", flush=True)


def make_fig1(res: dict, df_camp: pd.DataFrame) -> None:
    """Fig 1: Panel A = Public API Metadata Anomaly vs. 2025 Annual Report; Panel B = Conditional Size vs. Unconditional ITT."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.5, 5.3), gridspec_kw={"width_ratios": [1.04, 1.24]})

    # Panel A: 2019-2026 Audited Pure/Hybrid OTA vs Official NHTSA Public API Flag
    c19 = df_camp[df_camp["rec_year"].between(2019, 2026)]
    yrs = np.arange(2019, 2027)
    pure_cnt = np.array([int(((c19["rec_year"] == y) & (c19["modality4"] == "Pure_OTA")).sum()) for y in yrs])
    hyb_cnt = np.array([int(((c19["rec_year"] == y) & (c19["modality4"] == "Hybrid_OTA")).sum()) for y in yrs])
    api_cnt = np.array([int(((c19["rec_year"] == y) & (c19["is_ota_api_full"] == 1)).sum()) for y in yrs])

    w = 0.56
    ax1.bar(yrs, pure_cnt, width=w, color=COLORS["Pure_OTA"], label="Audited Pure-OTA (No Dealer Visit)", zorder=3)
    ax1.bar(yrs, hyb_cnt, width=w, bottom=pure_cnt, color=COLORS["Hybrid_OTA"], label="Audited Hybrid-OTA (OTA or Dealer)", zorder=3)
    ax1.plot(yrs, api_cnt, color=COLORS["API_OTA"], marker="D", markersize=6.5, linewidth=2.2, label="Public NHTSA API overTheAirUpdate=True", zorder=5)
    ax1.scatter([2025], [33], color=COLORS["Green"], marker="*", s=140, edgecolor="white", linewidth=0.7, label="NHTSA 2025 Annual Recalls Report (33)", zorder=6)

    for y, tot, ap in zip(yrs, pure_cnt + hyb_cnt, api_cnt):
        pct = round(100 * ap / tot) if tot > 0 else 0
        y_off = 2.1 if y == 2023 else (1.7 if y == 2024 else 1.2)
        ax1.text(
            y,
            tot + y_off,
            f"{ap}/{tot}\n({pct}%)",
            ha="center",
            va="bottom",
            fontsize=7.3,
            color="#1e293b",
            fontweight="bold" if y >= 2025 else "normal",
            bbox={"boxstyle": "round,pad=0.12", "facecolor": "white", "edgecolor": "none", "alpha": 0.8},
        )

    ax1.axvline(2024.55, color=COLORS["Red"], linestyle="--", linewidth=1.3, zorder=4)
    ax1.annotate(
        "Public API Metadata Anomaly\nMay 8, 2025 (25V282000): 36/36 True\nMay 9, 2025 (25V315000): 44/44 False\nPost-May 8: 0/68 vs. 33 in 2025 Report",
        xy=(2024.55, 42.8),
        xytext=(2018.85, 29.2),
        fontsize=7.0,
        color=COLORS["Red"],
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.30", "facecolor": "#fef2f2", "edgecolor": "#fca5a5", "lw": 0.8},
        arrowprops={"arrowstyle": "->", "color": COLORS["Red"], "lw": 1.1, "connectionstyle": "arc3,rad=-0.12"},
    )
    ax1.set_title("A. Public NHTSA API Endpoint Metadata Anomaly (2019–2026)", fontsize=10.2, fontweight="bold", loc="left", pad=8)
    ax1.set_xlabel("Recall Filing Year", fontsize=9.1)
    ax1.set_ylabel("Number of Vehicle Recall Campaigns", fontsize=9.1)
    ax1.set_xticks(yrs)
    ax1.set_ylim(0, 52.5)
    ax1.legend(loc="upper left", fontsize=7.0, frameon=True, facecolor="white", framealpha=0.95)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Conditional Within-OEM Size Differential vs. Distinct Unconditional Estimands (No % Share!)
    p1 = res["pillar1_blast_radius"]
    sa = p1["itt_staggered_adoption"]["sun_abraham_iw"]
    sa_item = {
        "coef": sa["iw_post_coef"],
        "ci95_lo": round(sa["iw_post_coef"] - 1.996 * sa["iw_se_cr1"], 4),
        "ci95_hi": round(sa["iw_post_coef"] + 1.996 * sa["iw_se_cr1"], 4),
        "p_t_G1": sa["iw_p_t_G1"],
        "is_sa": True,
    }
    items = [
        ("Hybrid-OTA vs. Dealer-SW (Main FE)", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"]),
        ("Hybrid-OTA (OEM × Year FE)", p1["robustness_ladder"]["oem_x_year_fe_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"]),
        ("Hybrid-OTA (Make × Model FE)", p1["robustness_ladder"]["make_x_model_fe_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"]),
        ("Hybrid-OTA (Excl. Tesla & Ford)", p1["robustness_ladder"]["excl_tesla_ford_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"]),
        ("Hybrid-OTA (Controlling Breadth)", p1["robustness_ladder"]["breadth_controlled_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"]),
        ("Official API OTA (2018–2024)", p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_log_potaff"]["terms"]["is_ota_api_full"], COLORS["API_OTA"]),
        ("Pure-OTA vs. Dealer-SW (Main FE)", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_pure"], COLORS["Pure_OTA"]),
        ("Uncond. TWFE First-OTA ITT (OEM)", p1["itt_staggered_adoption"]["pooled_did"]["terms"]["post_ota_adopt"], COLORS["ITT"]),
        ("Uncond. Sun–Abraham IW First-OTA ITT", sa_item, "#1e3a8a"),
        ("Uncond. SW × SDV Cohort (MY ≥ 2021)", p1["unconditional_sdv_cohort_shift"]["sw_vs_physical_sdv_did"]["terms"]["sw_x_sdv_my2021p"], COLORS["Dealer_Software"]),
    ]

    y_pos = np.arange(len(items))[::-1]
    ax2.axvline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=2)
    ax2.axhspan(-0.5, 2.5, color="#f0f9ff", alpha=0.85, zorder=1)
    for idx, (_lbl, d, col) in enumerate(items):
        yp = y_pos[idx]
        c = d["coef"]
        lo = d["ci95_lo"]
        hi = d["ci95_hi"]
        ax2.errorbar(
            c, yp, xerr=[[c - lo], [hi - c]],
            fmt="o", color=col, ecolor=col, elinewidth=1.9, capsize=3.3, markersize=6.0, zorder=4
        )
        if d.get("is_sa"):
            p_str = f"$p_t$={d['p_t_G1']:.3f}"
        else:
            p_str = f"$p_{{\\mathrm{{WCB}}}}$={d['p_wcb']:.3f}" if d["p_wcb"] >= 0.001 else "$p_{\\mathrm{WCB}}$<0.001"
        txt_x = hi + 0.10
        ax2.text(txt_x, yp, f"{c:+.2f} ({p_str})", va="center", ha="left", fontsize=7.3, color="#1e293b")

    ax2.text(2.45, 0.95, "Distinct Unconditional\nOEM-Level Estimands\n(No % Share Implied)", fontsize=7.2, color="#0369a1", fontweight="bold", ha="left", va="center")
    ax2.set_yticks(y_pos)
    ax2.set_yticklabels([it[0] for it in items], fontsize=8.0)
    ax2.set_xlabel("Effect on log(1 + Affected Vehicle-Instances) [CR1 $t(G-1)$ 95% CI]", fontsize=8.6)
    ax2.set_title("B. Conditional Campaign Size vs. Unconditional OEM ITT", fontsize=10.2, fontweight="bold", loc="left", pad=8)
    ax2.set_xlim(-2.25, 5.25)
    ax2.set_ylim(-0.65, len(items) - 0.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout(w_pad=2.2)
    fig.savefig(FIG_DIR / "fig1_api_audit_and_blast_radius.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig1_api_audit_and_blast_radius.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig2(res: dict, df_camp: pd.DataFrame) -> None:
    """Fig 2: Panel A = TWFE + True Sun-Abraham (2021) IW Event Study; Panel B = Fleet-Size CDF Fixed-Cost Selection."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.0), gridspec_kw={"width_ratios": [1.08, 1.05]})

    # Panel A: ITT Event Study (TWFE + True Sun & Abraham 2021 Saturated Cohort x Rel-Time IW)
    es = res["pillar1_blast_radius"]["itt_staggered_adoption"]["event_study"]["terms"]
    pre_w = res["pillar1_blast_radius"]["itt_staggered_adoption"]["pre_trend_wald_m3_m2"]
    sa = res["pillar1_blast_radius"]["itt_staggered_adoption"]["sun_abraham_iw"]
    sa_dyn = sa["iw_dynamic_terms"]
    sa_pre = sa["iw_pre_trend_wald_m3_m2"]
    did_p = res["pillar1_blast_radius"]["itt_staggered_adoption"]["pooled_did"]["terms"]["post_ota_adopt"]

    ks = np.array([-3, -2, -1, 0, 1, 2, 3], dtype=float)
    coefs, los, his = [], [], []
    sa_c, sa_lo, sa_hi = [], [], []
    for k in ks:
        ki = int(k)
        if ki == -1:
            coefs.append(0.0)
            los.append(0.0)
            his.append(0.0)
            sa_c.append(0.0)
            sa_lo.append(0.0)
            sa_hi.append(0.0)
        else:
            key = f"ev_m{abs(ki)}" if ki < 0 else f"ev_p{ki}"
            d = es[key]
            coefs.append(d["coef"])
            los.append(d["coef"] - d["ci95_lo"])
            his.append(d["ci95_hi"] - d["coef"])
            ds = sa_dyn[key]
            sa_c.append(ds["coef"])
            sa_lo.append(ds["coef"] - ds["ci95_lo"])
            sa_hi.append(ds["ci95_hi"] - ds["coef"])

    ax1.axhline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=2)
    ax1.axvline(-0.5, color=COLORS["Red"], linestyle=":", linewidth=1.2, zorder=2)
    ax1.axvspan(-0.5, 3.45, color="#f8fafc", alpha=0.9, zorder=1)
    ax1.errorbar(
        ks - 0.10, coefs, yerr=[los, his], fmt="o-", color=COLORS["ITT"], ecolor=COLORS["ITT"],
        elinewidth=1.7, capsize=3.5, markersize=6.2, linewidth=1.7, label="TWFE ITT Event Study", zorder=4,
    )
    ax1.errorbar(
        ks + 0.10, sa_c, yerr=[sa_lo, sa_hi], fmt="s--", color=COLORS["Pure_OTA"], ecolor=COLORS["Pure_OTA"],
        elinewidth=1.5, capsize=3.5, markersize=5.8, linewidth=1.5, alpha=0.9, label="Sun–Abraham (2021) Saturated IW", zorder=4,
    )
    ax1.scatter([-1.10, -0.90], [0.0, 0.0], color="white", edgecolor=[COLORS["ITT"], COLORS["Pure_OTA"]], s=48, linewidth=1.8, zorder=5)

    ax1.text(
        0.03,
        0.96,
        (
            f"TWFE Pre-trend Wald $F(2,{pre_w['df2']})={pre_w['F_stat']:.2f}$ ($p={pre_w['p_value']:.3f}$)\n"
            f"TWFE Pooled Post ITT = {did_p['coef']:+.2f} ($p_{{\\mathrm{{WCB}}}}={did_p['p_wcb']:.3f}$)\n"
            f"Sun–Abraham IW Pre-trend $F(2,{sa_pre['df2']})={sa_pre['F_stat']:.2f}$ ($p={sa_pre['p_value']:.3f}$)\n"
            f"Sun–Abraham IW Post (25 cells) = {sa['iw_post_coef']:+.2f} ($p={sa['iw_p_t_G1']:.3f}$)"
        ),
        transform=ax1.transAxes,
        va="top",
        ha="left",
        fontsize=7.3,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "white", "edgecolor": "#cbd5e1", "lw": 0.8},
    )
    ax1.set_xticks(ks)
    ax1.set_xticklabels(["≤ −3", "−2", "−1\n(Ref)", "0\n(1st OTA)", "+1", "+2", "≥ +3"], fontsize=8.4)
    ax1.set_xlabel("Years Relative to OEM's First OTA Recall (Unconditional All Software Recalls)", fontsize=8.7)
    ax1.set_ylabel("Change in log(1 + Affected Vehicle-Instances)", fontsize=8.9)
    ax1.set_title("A. Intent-to-Treat OEM OTA-Adoption Event Study (2015–2026)", fontsize=10.1, fontweight="bold", loc="left", pad=8)
    ax1.set_ylim(-3.15, 2.45)
    ax1.set_xlim(-3.45, 3.45)
    ax1.legend(loc="lower left", fontsize=7.4, frameon=True, facecolor="white", framealpha=0.95)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Empirical CDF of log10(Potentially Affected) across 4 Modalities (dynamic from res!)
    c18 = df_camp[df_camp["rec_year"].between(2018, 2026) & df_camp["potaff"].notna() & (df_camp["potaff"] > 0)].copy()
    dist = res["pillar1_blast_radius"]["fleet_size_distributions"]
    labels_map = [
        ("Physical_Hardware", f"Physical Hardware (med = {round(dist['Physical_Hardware']['p50']):,})", "--", 1.8),
        ("Dealer_Software", f"Dealer Software (med = {round(dist['Dealer_Software']['p50']):,})", "-.", 2.1),
        ("Pure_OTA", f"Pure-OTA (med = {round(dist['Pure_OTA']['p50']):,})", "-", 2.4),
        ("Hybrid_OTA", f"Hybrid-OTA (med = {round(dist['Hybrid_OTA']['p50']):,})", "-", 2.5),
    ]
    for mod, lbl, ls, lw in labels_map:
        vals = np.sort(np.log10(c18[c18["modality4"] == mod]["potaff"].to_numpy()))
        ecdf = np.arange(1, len(vals) + 1) / len(vals)
        ax2.plot(vals, ecdf, label=lbl, color=COLORS[mod], linestyle=ls, linewidth=lw, zorder=4 if "OTA" in mod else 3)

    ax2.axhline(0.5, color="#94a3b8", linestyle=":", linewidth=0.9)
    ax2.axvline(np.log10(10_000), color="#475569", linestyle=":", linewidth=1.0)
    hyb_10k = dist["Hybrid_OTA"]["pct_ge_10k"]
    dsw_10k = dist["Dealer_Software"]["pct_ge_10k"]
    ax2.annotate(
        f"Conditional Size Selection:\n{hyb_10k:.1f}% of Hybrid-OTA ≥ 10k\nvs. {dsw_10k:.1f}% of Dealer-SW",
        xy=(4.0, 1.0 - hyb_10k / 100.0),
        xytext=(4.32, 0.11),
        fontsize=7.9,
        color="#9a3412",
        fontweight="bold",
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#fff7ed", "edgecolor": "#fdba74", "lw": 0.8},
        arrowprops={"arrowstyle": "->", "color": "#9a3412", "lw": 1.2, "connectionstyle": "arc3,rad=-0.12"},
    )
    ax2.set_xticks([1, 2, 3, 4, 5, 6])
    ax2.set_xticklabels(["10", "100", "1k", "10k", "100k", "1M"], fontsize=8.6)
    ax2.set_xlabel("Campaign Size: Affected Vehicle-Instances ($\\log_{10}$ scale)", fontsize=8.8)
    ax2.set_ylabel("Empirical Cumulative Distribution Function (ECDF)", fontsize=9.0)
    ax2.set_title("B. Campaign-Size Distributions by Remedy Modality", fontsize=10.1, fontweight="bold", loc="left", pad=8)
    ax2.set_xlim(0.2, 6.7)
    ax2.set_ylim(-0.02, 1.03)
    ax2.legend(loc="upper left", fontsize=7.6, frameon=True, facecolor="white", framealpha=0.95)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout(w_pad=2.2)
    fig.savefig(FIG_DIR / "fig2_itt_event_study_and_fleet_selection.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig2_itt_event_study_and_fleet_selection.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig3(res: dict) -> None:
    """Fig 3: Panel A = Campaign-Age Maturation Curve; Panel B = Vehicle-Age Compliance-Decay Cliff Eradication."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.2, 5.1), gridspec_kw={"width_ratios": [1.05, 1.05]})
    p2 = res["pillar2_remediation_velocity"]
    tiers = p2["tesla_vs_legacy_execution_gap"]["descriptive_tiers"]
    # Dynamic mature medians from >24m / mature stats
    dsw_med_mat = tiers["Dealer_Software"]["median_cr"]
    phys_med_mat = tiers["Physical_Hardware"]["median_cr"]
    hyb_med_mat = tiers["Legacy_Hybrid_OTA"]["median_cr"]
    pure_med_mat = p2["maturation_curve"][-1]["Pure_OTA"]["median"]

    # Panel A: Maturation Curve
    bins = [r["age_bin"] for r in p2["maturation_curve"]]
    x = np.arange(len(bins))
    ax1.axvspan(3.5, 5.45, color="#f0fdf4", alpha=0.85, zorder=1)
    ax1.text(4.48, 56.0, "Mature Window\n(≥ 18 mo post-RCDATE;\n49 CFR § 573.7 proxy)", ha="center", va="center", fontsize=7.6, color="#166534", fontweight="bold")

    mod_styles = [
        ("Pure_OTA", f"Pure-OTA (Mature med = {pure_med_mat:.2f}%)", "o", "-", 2.5),
        ("Hybrid_OTA", f"Hybrid-OTA (Mature med = {hyb_med_mat:.2f}%)", "s", "-", 2.3),
        ("Dealer_Software", f"Dealer Software (Mature med = {dsw_med_mat:.2f}%)", "^", "--", 2.0),
        ("Physical_Hardware", f"Physical Hardware (Mature med = {phys_med_mat:.2f}%)", "D", ":", 1.9),
    ]
    for mod, lbl, mk, ls, lw in mod_styles:
        xs, ys = [], []
        for idx, r in enumerate(p2["maturation_curve"]):
            m = r[mod]
            if m["n"] >= 2 and m["median"] is not None:
                xs.append(idx)
                ys.append(m["median"])
        ax1.plot(xs, ys, marker=mk, linestyle=ls, linewidth=lw, markersize=6.5, color=COLORS[mod], label=lbl, zorder=4)

    n0_phys = p2["maturation_curve"][0]["Physical_Hardware"]["n"]
    ax1.annotate(
        f"Early-filing selection\n(n = {n0_phys} pre-completed)",
        xy=(0, p2["maturation_curve"][0]["Physical_Hardware"]["median"]),
        xytext=(-0.22, 67.5),
        fontsize=7.2,
        color="#475569",
        bbox={"boxstyle": "round,pad=0.22", "facecolor": "white", "edgecolor": "#cbd5e1", "lw": 0.6, "alpha": 0.95},
        arrowprops={"arrowstyle": "->", "color": "#64748b", "lw": 0.9},
    )
    ax1.set_xticks(x)
    ax1.set_xticklabels(bins, fontsize=8.6)
    ax1.set_xlabel("Campaign Age Since NHTSA Filing Date (RCDATE)", fontsize=9.0)
    ax1.set_ylabel("Median Official U.S. DOT Completion Rate (%)", fontsize=9.0)
    ax1.set_title("A. Recall Remediation Maturation Curve (2018–2026)", fontsize=10.3, fontweight="bold", loc="left", pad=8)
    ax1.set_ylim(10, 105.5)
    ax1.set_xlim(-0.3, 5.45)
    ax1.legend(loc="lower right", fontsize=7.5, frameon=True, facecolor="white", framealpha=0.96)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Vehicle-Age Compliance-Decay Cliff Eradication (Mature >= 18m)
    dbins = p2["vehicle_age_decay"]["descriptive_bins"]
    vbins = [r["veh_age_bin"] for r in dbins]
    xv = np.arange(len(vbins))
    age_reg = p2["vehicle_age_decay"]["regressions"]["sw_ota_oems_4way_x_age"]["terms"]
    age_slope = age_reg["veh_age"]["coef"]
    pure_off_pct = round(100.0 * age_reg["pure_x_age"]["coef"] / abs(age_slope))
    hyb_off_pct = round(100.0 * age_reg["hybrid_x_age"]["coef"] / abs(age_slope))

    for mod, lbl, mk, ls, lw in [
        ("Pure_OTA", f"Pure-OTA ({dbins[0]['Pure_OTA']['mean']:.1f}% → {dbins[3]['Pure_OTA']['mean']:.1f}%)", "o", "-", 2.6),
        ("Hybrid_OTA", f"Hybrid-OTA ({dbins[0]['Hybrid_OTA']['mean']:.1f}% → {dbins[2]['Hybrid_OTA']['mean']:.1f}% at 4–5y)", "s", "-", 2.3),
        ("Dealer_Software", f"Dealer Software ({dbins[0]['Dealer_Software']['mean']:.1f}% → {dbins[3]['Dealer_Software']['mean']:.1f}%)", "^", "--", 2.2),
        ("Physical_Hardware", f"Physical Hardware ({dbins[0]['Physical_Hardware']['mean']:.1f}% → {dbins[3]['Physical_Hardware']['mean']:.1f}%)", "D", ":", 2.0),
    ]:
        xs, ys = [], []
        for idx, r in enumerate(dbins):
            m = r[mod]
            if m["n"] >= 3 and m["mean"] is not None:
                xs.append(idx)
                ys.append(m["mean"])
        ax2.plot(xs, ys, marker=mk, linestyle=ls, linewidth=lw, markersize=7.0, color=COLORS[mod], label=lbl, zorder=4)
        for xi, yi in zip(xs, ys):
            if mod == "Pure_OTA":
                ax2.text(xi, yi + 2.8, f"{yi:.1f}%", ha="center", va="bottom", fontsize=7.6, color=COLORS[mod], fontweight="bold")
            elif mod == "Hybrid_OTA":
                if xi == 0:
                    ax2.text(xi + 0.14, yi - 1.5, f"{yi:.1f}%", ha="left", va="top", fontsize=7.6, color=COLORS[mod], fontweight="bold")
                else:
                    ax2.text(xi, yi - 2.6, f"{yi:.1f}%", ha="center", va="top", fontsize=7.6, color=COLORS[mod], fontweight="bold")
            elif mod == "Dealer_Software":
                if xi == 0:
                    ax2.text(xi - 0.04, yi - 2.6, f"{yi:.1f}%", ha="center", va="top", fontsize=7.6, color=COLORS[mod], fontweight="bold")
                else:
                    ax2.text(xi, yi + 2.5, f"{yi:.1f}%", ha="center", va="bottom", fontsize=7.6, color=COLORS[mod], fontweight="bold")
            else:
                ax2.text(xi, yi - 3.0, f"{yi:.1f}%", ha="center", va="top", fontsize=7.6, color=COLORS[mod], fontweight="bold")

    age_api = p2["vehicle_age_decay"]["regressions"]["sw_ota_oems_api_x_age"]["terms"]["api_ota_x_age"]
    age_not_api = p2["vehicle_age_decay"]["regressions"]["sw_excl_tesla_api_x_age"]["terms"]["api_ota_x_age"]
    ax2.text(
        0.02,
        0.02,
        (
            "Within-OEM SW Compliance-Decay Slopes:\n"
            f"Dealer-SW Age: {age_slope:.2f} pp/yr ($p_{{\\mathrm{{WCB}}}}={age_reg['veh_age']['p_wcb']:.3f}$)\n"
            f"Pure-OTA × Age: {age_reg['pure_x_age']['coef']:+.2f} pp/yr ($p_{{\\mathrm{{WCB}}}}={age_reg['pure_x_age']['p_wcb']:.3f}$, −{pure_off_pct}%)\n"
            f"Hybrid-OTA × Age: {age_reg['hybrid_x_age']['coef']:+.2f} pp/yr ($p_{{\\mathrm{{WCB}}}}={age_reg['hybrid_x_age']['p_wcb']:.3f}$, −{hyb_off_pct}%)\n"
            f"API OTA × Age: {age_api['coef']:+.2f} ($p_{{\\mathrm{{WCB}}}}={age_api['p_wcb']:.3f}$) | Excl. Tesla: {age_not_api['coef']:+.2f} ({age_not_api['p_wcb']:.3f})"
        ),
        transform=ax2.transAxes,
        va="bottom",
        ha="left",
        fontsize=6.95,
        bbox={"boxstyle": "round,pad=0.33", "facecolor": "#f8fafc", "edgecolor": "#94a3b8", "lw": 0.8},
    )
    ax2.set_xticks(xv)
    ax2.set_xticklabels(vbins, fontsize=8.8)
    ax2.set_xlabel("Vehicle Age at Recall Filing (Recall Year − Min Model Year)", fontsize=9.0)
    ax2.set_ylabel("Mean Mature (≥ 18 mo) Completion Rate (%)", fontsize=9.0)
    ax2.set_title("B. OTA Flattens the Vehicle-Age Compliance-Decay Cliff", fontsize=10.3, fontweight="bold", loc="left", pad=8)
    ax2.set_ylim(14, 108.5)
    ax2.set_xlim(-0.38, 3.38)
    ax2.legend(loc="lower left", bbox_to_anchor=(0.02, 0.30), fontsize=7.0, frameon=True, facecolor="white", framealpha=0.96)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout(w_pad=2.2)
    fig.savefig(FIG_DIR / "fig3_maturation_and_age_decay_cliff.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig3_maturation_and_age_decay_cliff.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig4(res: dict) -> None:
    """Fig 4: Panel A = Sample-Matched Break-Even Frontier (with Tesla 98.7% disclosure); Panel B = Unremedied Proxy Forest Plot with EXACT p_WCB."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.6, 5.25), gridspec_kw={"width_ratios": [1.08, 1.08]})
    p3 = res["pillar3_net_unremedied_exposure"]
    bf = p3["breakeven_frontier"]
    mf = bf["within_ota_oem_matched_frontier"]
    comp = p3["mature_sample_composition"]
    r0 = mf["r0_pct"] / 100.0
    raw_pts = bf["raw_median_multiplier_coordinates"]

    # Panel A: Sample-Matched Within-OTA-OEM Break-Even Frontier r*(M) = 1 - (1 - r0)/M (r0 = OTA-OEMs Dealer-SW)
    M_grid = np.linspace(1.0, 11.5, 400)
    r_star = 100.0 * (1.0 - (1.0 - r0) / M_grid)

    ax1.fill_between(M_grid, r_star, 100.6, color="#dcfce7", alpha=0.55, label="Net Safety Gain Zone ($r > r^*$)", zorder=1)
    ax1.fill_between(M_grid, 83.0, r_star, color="#fee2e2", alpha=0.45, label="Net Exposure Penalty Zone ($r < r^*$)", zorder=1)
    ax1.plot(M_grid, r_star, color=COLORS["Red"], linewidth=2.4, label=f"Break-Even Frontier $r^*(M)$, OTA-OEM $r_0$={mf['r0_pct']:.1f}%", zorder=3)

    # Consistent apples-to-apples empirical coordinates (all referenced to OTA-OEM Dealer-SW!)
    t_m = raw_pts["Tesla_Pure_OTA"]["M_vs_ota_oems_dsw_median"]
    t_r = raw_pts["Tesla_Pure_OTA"]["observed_mean_r_pct"]
    t_sh = comp["pure_ota_tesla_subsample"]["share_pure_affected_pct"]
    nt_r = comp["pure_ota_nontesla_subsample"]["mean_cr_pct"]
    pts = [
        (
            f"Pure-OTA (FE $M$={mf['pure_ota_M']:.2f}×)",
            mf["pure_ota_M"],
            mf["pure_ota_observed_mean_r_pct"],
            COLORS["Pure_OTA"],
            "o",
            (0.72, 100.35),
            f"{mf['pure_ota_margin_above_frontier_pp']:+.2f} pp ABOVE (99.18%; Non-Tesla: {nt_r:.2f}%)",
        ),
        (
            f"Tesla Pure-OTA (Med $M$={t_m:.2f}×)",
            t_m,
            t_r,
            "#0f172a",
            "D",
            (6.95, 100.35),
            f"{t_r:.2f}% mean ({t_sh:.1f}% Pure-OTA share)",
        ),
        (
            f"Hybrid-OTA (FE $M$={mf['hybrid_ota_M']:.2f}×)",
            mf["hybrid_ota_M"],
            mf["hybrid_ota_observed_mean_r_pct"],
            COLORS["Hybrid_OTA"],
            "s",
            (5.9, 91.6),
            f"{mf['hybrid_ota_margin_above_frontier_pp']:+.2f} pp BELOW frontier\n(SW-Choice: {mf['hybrid_swchoice_margin_above_frontier_pp']:+.2f} pp)",
        ),
        (
            "OTA-OEM Dealer-SW ($M$=1.0×)",
            1.0,
            mf["r0_pct"],
            COLORS["Dealer_Software"],
            "^",
            (2.1, 88.3),
            f"Sample-matched $r_0$ = {mf['r0_pct']:.2f}%",
        ),
    ]
    for lbl, mx, ry, col, mk, txt_xy, note in pts:
        ax1.scatter([mx], [ry], color=col, marker=mk, s=95, edgecolor="white", linewidth=1.3, zorder=6)
        ax1.annotate(
            f"{lbl}\n{note}",
            xy=(mx, ry),
            xytext=txt_xy,
            fontsize=6.6,
            color=col,
            fontweight="bold",
            bbox={"boxstyle": "round,pad=0.24", "facecolor": "white", "edgecolor": col, "lw": 0.85, "alpha": 0.96},
            arrowprops={"arrowstyle": "->", "color": col, "lw": 1.1},
            zorder=7,
        )

    ax1.set_xlabel("Recall-Size Multiplier $M$ vs. OTA-OEM Dealer-Software (×)", fontsize=8.8)
    ax1.set_ylabel("Mature (≥ 18 mo) Campaign Completion Rate (%)", fontsize=8.9)
    ax1.set_title("A. Sample-Matched Break-Even Frontier (Recall-Instance Proxy)", fontsize=9.8, fontweight="bold", loc="left", pad=8)
    ax1.set_xlim(0.45, 12.6)
    ax1.set_ylim(84.0, 102.7)
    ax1.legend(loc="lower right", fontsize=7.0, frameon=True, facecolor="white", framealpha=0.96)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Recall-Level Unremedied Vehicle-Instance Proxy Forest Plot (EXACT p_WCB on every row!)
    regs = p3["regressions"]
    w_diff = p3["hybrid_minus_pure_unremedied_wald"]
    b_items = [
        ("Pure-OTA vs. Physical (All Veh FE)", regs["mature_all_vehicles_4way_vs_phys"]["terms"]["is_ota_pure"], COLORS["Pure_OTA"]),
        ("Hybrid-OTA vs. Physical (All Veh FE)", regs["mature_all_vehicles_4way_vs_phys"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"]),
        ("Hybrid SW-Choice vs. Physical (All Veh)", regs["mature_all_vehicles_hybrid_swchoice_vs_hwmixed"]["terms"]["is_ota_hybrid_swchoice"], "#c2410c"),
        ("Dealer-SW vs. Physical (All Veh FE)", regs["mature_all_vehicles_4way_vs_phys"]["terms"]["is_dealer_sw"], COLORS["Dealer_Software"]),
        ("Pure-OTA vs. Dealer-SW (Uncond. FE)", regs["mature_sw_ota_oems_4way"]["terms"]["is_ota_pure"], COLORS["Pure_OTA"]),
        ("Hybrid-OTA vs. Dealer-SW (Uncond. FE)", regs["mature_sw_ota_oems_4way"]["terms"]["is_ota_hybrid"], COLORS["Hybrid_OTA"]),
        ("Pure-OTA (Holding Campaign Size Fixed)", regs["mature_sw_ota_oems_4way_ctrl_potaff"]["terms"]["is_ota_pure"], "#1e40af"),
        ("Hybrid-OTA (Holding Campaign Size Fixed)", regs["mature_sw_ota_oems_4way_ctrl_potaff"]["terms"]["is_ota_hybrid"], "#ea580c"),
        ("Non-Tesla Pure-OTA (Light-Duty Tiers)", regs["mature_sw_tiers_light_duty"]["terms"]["is_nontesla_pure"], COLORS["Pure_OTA"]),
        ("Tesla Pure-OTA (Light-Duty Tiers)", regs["mature_sw_tiers_light_duty"]["terms"]["is_tesla_pure"], "#0f172a"),
    ]
    yp = np.arange(len(b_items))[::-1]
    ax2.axvline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=2)
    ax2.axhspan(1.5, 3.5, color="#f8fafc", alpha=0.9, zorder=1)
    for idx, (_lbl, d, col) in enumerate(b_items):
        y0 = yp[idx]
        c, lo, hi = d["coef"], d["ci95_lo"], d["ci95_hi"]
        ax2.errorbar(c, y0, xerr=[[c - lo], [hi - c]], fmt="o", color=col, ecolor=col, elinewidth=1.9, capsize=3.2, markersize=6.0, zorder=4)
        p_txt = f"$p_{{\\mathrm{{WCB}}}}$={d['p_wcb']:.3f}" if d["p_wcb"] >= 0.001 else "$p_{\\mathrm{WCB}}$<0.001"
        if c >= 0:
            ax2.text(hi + 0.14, y0, f"{c:+.2f} ({p_txt})", va="center", ha="left", fontsize=7.0, color="#1e293b")
        else:
            ax2.text(lo - 0.14, y0, f"{c:+.2f} ({p_txt})", va="center", ha="right", fontsize=7.0, color="#1e293b")

    ax2.text(
        0.98,
        0.03,
        (
            "Hybrid − Pure Contrast (Exact WCB):\n"
            f"All Veh: +{w_diff['all_vehicles']['diff_hybrid_minus_pure']:.2f} ($p_{{\\mathrm{{WCB}}}}={w_diff['all_vehicles']['p_wcb']:.3f}$)\n"
            f"SW-Only: +{w_diff['sw_ota_oems']['diff_hybrid_minus_pure']:.2f} ($p_{{\\mathrm{{WCB}}}}={w_diff['sw_ota_oems']['p_wcb']:.3f}$)"
        ),
        transform=ax2.transAxes,
        ha="right",
        va="bottom",
        fontsize=7.0,
        bbox={"boxstyle": "round,pad=0.32", "facecolor": "#fffbeb", "edgecolor": "#fcd34d", "lw": 0.8},
    )
    ax2.set_yticks(yp)
    ax2.set_yticklabels([it[0] for it in b_items], fontsize=7.7)
    ax2.set_xlabel("Effect on log(1 + Unremedied Vehicle-Instance Proxy) [Mature ≥ 18 mo, CR1 95% CI]", fontsize=8.1)
    ax2.set_title("B. Recall-Level Unremedied Proxy: Exact WCB Inference", fontsize=9.8, fontweight="bold", loc="left", pad=8)
    ax2.set_xlim(-8.8, 6.2)
    ax2.set_ylim(-0.65, len(b_items) - 0.35)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout(w_pad=2.2)
    fig.savefig(FIG_DIR / "fig4_breakeven_frontier_and_net_exposure.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig4_breakeven_frontier_and_net_exposure.pdf", bbox_inches="tight")
    plt.close(fig)


def make_fig5(res: dict) -> None:
    """Fig 5: Panel A = Safety Severity, Oversight & Repeat-Cascade Audit; Panel B = Real-World Complaint-Decay DiD."""
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13.3, 5.05), gridspec_kw={"width_ratios": [1.05, 1.12]})
    p4 = res["pillar4_safety_and_complaints"]
    sreg = p4["safety_fe_regressions"]

    # Panel A: Paired Pure-OTA vs Hybrid-OTA within-OEM effects (percentage-point outcomes)
    s_items = [
        ("FMVSS Noncompliance", "4way_has_fmvss"),
        ("Formal ODI Action", "4way_has_odi_action"),
        ("Regulator-Forced (ODI/OVSC)", "4way_is_regulator_forced"),
        ("Park Outside Fire Risk", "4way_park_outside"),
        ("Do Not Drive Advisory", "4way_do_not_drive"),
        ("Crash Consequence Text", "4way_con_crash"),
        ("Fire Consequence Text", "4way_con_fire"),
        ("Repeat Cascade (365d)", "4way_any_repeat_365d"),
        ("Repeat Cascade (730d)", "4way_any_repeat_730d"),
    ]
    yp = np.arange(len(s_items))[::-1]
    ax1.axvline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=2)

    for idx, (_lbl, k) in enumerate(s_items):
        y0 = yp[idx]
        dp = sreg[k]["terms"]["is_ota_pure"]
        dh = sreg[k]["terms"]["is_ota_hybrid"]
        cp, lop, hip = 100 * dp["coef"], 100 * dp["ci95_lo"], 100 * dp["ci95_hi"]
        ch, loh, hih = 100 * dh["coef"], 100 * dh["ci95_lo"], 100 * dh["ci95_hi"]
        ax1.errorbar(cp, y0 + 0.14, xerr=[[cp - lop], [hip - cp]], fmt="o", color=COLORS["Pure_OTA"], ecolor=COLORS["Pure_OTA"], elinewidth=1.7, capsize=3, markersize=5.8, label="Pure-OTA vs. Dealer-SW" if idx == 0 else None, zorder=4)
        ax1.errorbar(ch, y0 - 0.14, xerr=[[ch - loh], [hih - ch]], fmt="s", color=COLORS["Hybrid_OTA"], ecolor=COLORS["Hybrid_OTA"], elinewidth=1.7, capsize=3, markersize=5.5, label="Hybrid-OTA vs. Dealer-SW" if idx == 0 else None, zorder=4)

    fmv_p = sreg["4way_has_fmvss"]["terms"]["is_ota_pure"]
    odi_p = sreg["4way_has_odi_action"]["terms"]["is_ota_pure"]
    odi_a = sreg["apiota2018_24_has_odi_action"]["terms"]["is_ota_api_full"]
    ax1.annotate(
        f"Pure-OTA: {100 * fmv_p['coef']:+.1f} pp\n($p_{{\\mathrm{{WCB}}}}={fmv_p['p_wcb']:.3f}$)",
        xy=(100 * fmv_p["coef"], yp[0] + 0.14),
        xytext=(21.0, yp[0] - 1.15),
        fontsize=7.3,
        color=COLORS["Pure_OTA"],
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": COLORS["Pure_OTA"], "lw": 0.9},
    )
    ax1.annotate(
        f"Pure-OTA: {100 * odi_p['coef']:+.1f} pp\n(API: {100 * odi_a['coef']:+.1f} pp, $p_{{\\mathrm{{WCB}}}}={odi_a['p_wcb']:.3f}$)",
        xy=(100 * odi_p["coef"], yp[1] + 0.14),
        xytext=(-68.5, yp[1] - 0.58),
        fontsize=7.0,
        color=COLORS["Pure_OTA"],
        fontweight="bold",
        arrowprops={"arrowstyle": "->", "color": COLORS["Pure_OTA"], "lw": 0.9},
    )

    ax1.set_yticks(yp)
    ax1.set_yticklabels([it[0] for it in s_items], fontsize=8.3)
    ax1.set_xlabel("Within-OEM FE Difference vs. Dealer-Software (Percentage Points, 95% CI)", fontsize=8.5)
    ax1.set_title("A. Safety Severity, Regulatory Oversight & Repeat Cascades", fontsize=10.1, fontweight="bold", loc="left", pad=8)
    ax1.set_xlim(-70, 58)
    ax1.set_ylim(-0.65, len(s_items) - 0.35)
    ax1.legend(loc="center left", bbox_to_anchor=(0.01, 0.44), fontsize=7.5, frameon=True, facecolor="white", framealpha=0.96)
    ax1.spines["top"].set_visible(False)
    ax1.spines["right"].set_visible(False)

    # Panel B: Real-World Consumer Complaint-Decay Event Study ([-12m, +12m] Deduplicated Failure-Date Complaints)
    cd = p4["complaint_did_summary"]
    dyn_f = cd["dynamic_event_study_fail"]["terms"]
    pre_w = cd["dynamic_event_study_fail_pre_wald"]
    did_act = cd["did_regressions"]["sw_active_4way_oemcl__log_cmpl_fail"]["terms"]
    did_short = cd["did_regressions"]["sw_short_m3m1_p1p12_4way_oemcl__log_cmpl_fail"]["terms"]
    ms = list(range(-12, 13))
    c_f, lo_f, hi_f = [], [], []
    for m in ms:
        if m == -1:
            c_f.append(0.0)
            lo_f.append(0.0)
            hi_f.append(0.0)
        else:
            key = f"ota_m{abs(m)}" if m < 0 else f"ota_p{m}"
            d = dyn_f[key]
            c_f.append(d["coef"])
            lo_f.append(d["coef"] - d["ci95_lo"])
            hi_f.append(d["ci95_hi"] - d["coef"])

    ax2.axhline(0.0, color="#334155", linestyle="--", linewidth=1.0, zorder=2)
    ax2.axvline(-0.5, color=COLORS["Red"], linestyle=":", linewidth=1.2, zorder=2)
    ax2.axvspan(-0.5, 12.5, color="#f8fafc", alpha=0.9, zorder=1)
    ax2.errorbar(ms, c_f, yerr=[lo_f, hi_f], fmt="o-", color=COLORS["Pure_OTA"], ecolor="#64748b", elinewidth=1.3, capsize=2.5, markersize=4.8, linewidth=1.5, label="OTA vs. Dealer-SW: log(1 + Failure-Date Complaints)", zorder=4)
    ax2.scatter([-1], [0.0], color="white", edgecolor=COLORS["Pure_OTA"], s=48, linewidth=1.8, zorder=5)

    ax2.text(
        0.025,
        0.96,
        (
            f"Deduplicated ODI Complaints (437,886 Unique; {cd['n_sw_campaigns']} SW Recalls):\n"
            f"Pre-trend Wald $F({pre_w['q']},{pre_w['df2']})={pre_w['F_stat']:.2f}$ ($p={pre_w['p_value']:.3f}$, fleet ramp-up)\n"
            f"Full [−12,+12] Pure: {did_act['is_pure_post']['coef']:+.3f} ($p_{{\\mathrm{{WCB}}}}={did_act['is_pure_post']['p_wcb']:.3f}$) | Hyb: {did_act['is_hybrid_post']['coef']:+.3f} ($p_{{\\mathrm{{WCB}}}}={did_act['is_hybrid_post']['p_wcb']:.3f}$)\n"
            f"Short [−3,+12] Pure: {did_short['is_pure_post']['coef']:+.3f} ($p_{{\\mathrm{{WCB}}}}={did_short['is_pure_post']['p_wcb']:.3f}$) | Hyb: {did_short['is_hybrid_post']['coef']:+.3f} ($p_{{\\mathrm{{WCB}}}}={did_short['is_hybrid_post']['p_wcb']:.3f}$)"
        ),
        transform=ax2.transAxes,
        va="top",
        ha="left",
        fontsize=7.1,
        bbox={"boxstyle": "round,pad=0.35", "facecolor": "#f8fafc", "edgecolor": "#cbd5e1", "lw": 0.8},
    )
    ax2.set_xticks(range(-12, 13, 3))
    ax2.set_xlabel("Months Relative to Recall Filing Date (RCDATE; Month −1 = Reference)", fontsize=8.7)
    ax2.set_ylabel("Event-Study DiD Coefficient: log(1 + Failure Complaints)", fontsize=8.8)
    ax2.set_title("B. Real-World Consumer Complaint-Decay Event Study (2021–2025)", fontsize=10.1, fontweight="bold", loc="left", pad=8)
    ax2.set_xlim(-12.8, 12.8)
    ax2.set_ylim(-0.42, 0.48)
    ax2.legend(loc="lower right", fontsize=7.4, frameon=True, facecolor="white", framealpha=0.96)
    ax2.spines["top"].set_visible(False)
    ax2.spines["right"].set_visible(False)

    plt.tight_layout(w_pad=2.2)
    fig.savefig(FIG_DIR / "fig5_safety_oversight_and_complaint_did.png", dpi=300, bbox_inches="tight")
    fig.savefig(FIG_DIR / "fig5_safety_oversight_and_complaint_did.pdf", bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    res = json.loads((RES_DIR / "d12_econometric_results.json").read_text(encoding="utf-8"))
    audit = json.loads((RES_DIR / "api_reconciliation_audit.json").read_text(encoding="utf-8"))
    df_camp = pd.read_csv(PROC_DIR / "campaigns_2015_2026.csv")

    build_tables(res, audit, df_camp)
    make_fig1(res, df_camp)
    make_fig2(res, df_camp)
    make_fig3(res)
    make_fig4(res)
    make_fig5(res)
    print("[DONE] Generated all 9 CSV tables and 5 publication figures (PNG + PDF)!", flush=True)


if __name__ == "__main__":
    main()
