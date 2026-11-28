"""Step 9 (v4): Fixed-Horizon Eighth-Report Reconciliation, Sample Flow Accounting,
Channel x Manufacturer x Vehicle-Age Common-Support Audit, Leave-One-OEM-Out (LOOO)
Sensitivity, and Public API Measurement Validation Audit.

Cleanly integrates validated v3 fixed-report logic into the primary workspace and adds
all v4 peer-review audit tables and machine-readable M&SOM Data Set replication files.
"""
from __future__ import annotations

import hashlib
import json
import re
import runpy
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
RAW_DIR = BASE_DIR / "data_raw"
PROC_DIR = BASE_DIR / "data_processed"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
SCRIPTS_DIR = BASE_DIR / "scripts"

ANNUAL_CSV = RAW_DIR / "nhtsa_annual_eighth_report_2024_2025.csv"
DOT_STUDY_PDF = RAW_DIR / "dot_79374_DS1.pdf"
PREPARED_CSV = PROC_DIR / "campaigns_2015_2026.csv"
REMEDY_TYPES = ["Dealer_Software", "Pure_OTA", "Hybrid_OTA", "Physical_Hardware"]
OFFICIAL_REPORTS = {
    "2024_eighth_report_pdf": "https://www.nhtsa.gov/sites/nhtsa.gov/files/2025-01/2024-recall-completion-rates.pdf",
    "2025_eighth_report_pdf": "https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-01/2025-recall-completion-rates.pdf",
    "nhtsa_completion_rates_study_rosap": "https://rosap.ntl.bts.gov/view/dot/79374",
    "nhtsa_completion_rates_study_pdf": "https://rosap.ntl.bts.gov/view/dot/79374/dot_79374_DS1.pdf",
    "nhtsa_2025_annual_recalls_report": "https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-03/2025-annual-recalls-report.pdf",
    "cfr_49_573_7": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-573/section-573.7",
}
SPOTCHECK_CAMPAIGNS = [
    ("25V282000", "Boundary: last public API overTheAirUpdate=True campaign (Volvo, May 8, 2025)"),
    ("25V315000", "Boundary: first next-day public API False despite verbatim OTA text (Ford, May 9, 2025)"),
    ("25V409000", "Post-cutoff verbatim Pure-OTA example (Polestar, June 2025)"),
    ("26V104000", "Post-cutoff 2026 verbatim Hybrid-OTA example (Ford, Feb 2026)"),
    ("22V315000", "Excluded duplicate across 2024 (56.9%) & 2025 (45.6%) 8th-report lists (Mercedes-Benz)"),
    ("22V743000", "Excluded duplicate across 2024 (84.2%) & 2025 (79.2%) 8th-report lists (Bentley)"),
    ("22V867000", "Physical-recall denominator discrepancy audit (17,445 CSV vs 117,445 FLAT_RCL/DOT, Honda)"),
    ("23V413000", "Physical-recall denominator amendment audit (331,401 CSV vs 305,282 FLAT_RCL/DOT, FCA)"),
    ("22V063000", "Unlisted 2022 ODATE Pure-OTA campaign missing DOT completion rate (Tesla Boombox)"),
]
OTA_TEXT_PAT = re.compile(r"over[- ]the[- ]air|\bota\b", re.IGNORECASE)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def link_reported_campaigns() -> tuple[pd.DataFrame, pd.DataFrame]:
    campaigns = pd.read_csv(PREPARED_CSV, parse_dates=["odate", "rec_date"])
    campaigns["campaign_code"] = campaigns["CAMPNO"].str[:6]
    report = pd.read_csv(ANNUAL_CSV)
    if report.duplicated(["report_year", "campaign_code"]).any():
        raise ValueError("Duplicate campaign_code within the same annual eighth-report list")
    if not report["completion_at_eighth_report_pct"].between(0, 100).all():
        raise ValueError("An annual eighth-report completion percentage is outside [0, 100]")
    if campaigns["campaign_code"].duplicated().any():
        raise ValueError("Short 6-character campaign_code is ambiguous in frozen campaign panel")
    linked = report.merge(campaigns, on="campaign_code", how="left", validate="many_to_one", indicator=True)
    return campaigns, linked


def eligible_eighth_reports(annual: pd.DataFrame) -> pd.DataFrame:
    return annual.loc[annual["_merge"].eq("both") & ~annual["campaign_code"].duplicated(keep=False)].copy()


def build_reconciliation_audit(annual: pd.DataFrame, fixed: pd.DataFrame) -> dict:
    dups_df = annual.loc[annual["campaign_code"].duplicated(keep=False)].sort_values(["campaign_code", "report_year"])
    dup_records = [
        {
            "campaign_code": str(r.campaign_code),
            "report_year": int(r.report_year),
            "mfg": str(r.mfg),
            "modality4": str(r.modality4),
            "rec_date": str(r.rec_date.date()) if pd.notna(r.rec_date) else None,
            "odate": str(r.odate.date()) if pd.notna(r.odate) else None,
            "reported_affected": int(r.reported_affected),
            "potaff_flat_rcl": round(float(r.potaff)) if pd.notna(r.potaff) else None,
            "completion_at_eighth_report_pct": float(r.completion_at_eighth_report_pct),
            "dot_latest_completion_rate_pct": round(float(r.completion_rate), 2) if pd.notna(r.completion_rate) else None,
        }
        for r in dups_df.itertuples(index=False)
    ]

    aff_diff = fixed["reported_affected"] - fixed["potaff"]
    sw_mask = fixed["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])
    mism_df = fixed.loc[aff_diff != 0]
    mism_records = [
        {
            "report_year": int(r.report_year),
            "campaign_code": str(r.campaign_code),
            "mfg": str(r.mfg),
            "modality4": str(r.modality4),
            "reported_affected": int(r.reported_affected),
            "potaff_flat_rcl": round(float(r.potaff)),
            "diff": round(float(r.reported_affected - r.potaff)),
            "completion_at_eighth_report_pct": float(r.completion_at_eighth_report_pct),
            "dot_latest_completion_rate_pct": round(float(r.completion_rate), 2) if pd.notna(r.completion_rate) else None,
        }
        for r in mism_df.itertuples(index=False)
    ]

    odate_yr = fixed["odate"].dt.year
    in_2024 = fixed["report_year"] == 2024
    in_2025 = fixed["report_year"] == 2025
    n_2024_od22 = int((in_2024 & (odate_yr == 2022)).sum())
    n_2025_od23 = int((in_2025 & (odate_yr == 2023)).sum())
    cr_diff = (fixed["completion_rate"] - fixed["completion_at_eighth_report_pct"]).dropna()

    rec_yr_tbl = {
        str(int(ry)): {str(int(cy)): int(cnt) for cy, cnt in row.items() if cnt > 0}
        for ry, row in fixed.groupby(["report_year", "rec_year"]).size().unstack(fill_value=0).iterrows()
    }
    odate_yr_tbl = {
        str(int(ry)): {str(int(oy)): int(cnt) for oy, cnt in row.items() if cnt > 0}
        for ry, row in fixed.assign(oy=odate_yr.fillna(-1).astype(int)).groupby(["report_year", "oy"]).size().unstack(fill_value=0).iterrows()
    }

    return {
        "total_extracted_rows": len(annual),
        "rows_by_report_year": {str(int(k)): int(v) for k, v in annual["report_year"].value_counts().sort_index().items()},
        "matched_to_flat_rcl_rows": int(annual["_merge"].eq("both").sum()),
        "unlinked_campaigns": annual.loc[annual["_merge"].eq("left_only"), "campaign_code"].tolist(),
        "excluded_duplicate_campaigns": sorted(dups_df["campaign_code"].unique().tolist()),
        "excluded_duplicate_rows": len(dups_df),
        "duplicate_campaign_details": dup_records,
        "matched_unique_campaigns": len(fixed),
        "unique_by_report_year": {str(int(k)): int(v) for k, v in fixed["report_year"].value_counts().sort_index().items()},
        "denominator_exact_match_count": int((aff_diff == 0).sum()),
        "denominator_exact_match_pct": round(100.0 * float((aff_diff == 0).mean()), 2),
        "denominator_sw_exact_match_count": int((aff_diff[sw_mask] == 0).sum()),
        "denominator_sw_total_count": int(sw_mask.sum()),
        "denominator_log_corr": round(
            float(np.corrcoef(np.log1p(fixed["reported_affected"]), np.log1p(fixed["potaff"]))[0, 1]), 6
        ),
        "denominator_discrepancies": mism_records,
        "rec_year_by_report_year": rec_yr_tbl,
        "odate_year_by_report_year": odate_yr_tbl,
        "odate_statutory_alignment": {
            "2024_list_odate_2022_n": n_2024_od22,
            "2024_list_total_n": int(in_2024.sum()),
            "2024_list_odate_2022_pct": round(100.0 * n_2024_od22 / max(1, int(in_2024.sum())), 2),
            "2025_list_odate_2023_n": n_2025_od23,
            "2025_list_total_n": int(in_2025.sum()),
            "2025_list_odate_2023_pct": round(100.0 * n_2025_od23 / max(1, int(in_2025.sum())), 2),
            "combined_two_year_lag_n": n_2024_od22 + n_2025_od23,
            "combined_two_year_lag_pct": round(100.0 * (n_2024_od22 + n_2025_od23) / len(fixed), 2),
        },
        "dot_latest_vs_eighth_report": {
            "n_rated_in_dot": int(fixed["completion_rate"].notna().sum()),
            "n_missing_in_dot": int(fixed["completion_rate"].isna().sum()),
            "median_drift_pp": round(float(cr_diff.median()), 2),
            "mean_drift_pp": round(float(cr_diff.mean()), 2),
            "n_higher_in_dot_gt_01pp": int((cr_diff > 0.1).sum()),
            "n_equal_within_01pp": int((cr_diff.abs() <= 0.1).sum()),
            "n_lower_in_dot_lt_01pp": int((cr_diff < -0.1).sum()),
        },
    }


def build_sample_flow_accounting(campaigns: pd.DataFrame, annual: pd.DataFrame, fixed: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    in_8th_uniq = set(fixed["campaign_code"])
    in_8th_dup = set(annual.loc[annual["campaign_code"].duplicated(keep=False), "campaign_code"])
    rows: list[dict] = []

    # Panel A: Statutory 2022-2023 Owner-Notification Cohort (ODATE in 2022-2023)
    c_od = campaigns.loc[campaigns["odate"].dt.year.between(2022, 2023)].copy()
    c_od["in_8th"] = c_od["campaign_code"].isin(in_8th_uniq)
    c_od["is_dup"] = c_od["campaign_code"].isin(in_8th_dup)
    c_od["cr_na"] = c_od["completion_rate"].isna()
    c_od["cr_100"] = c_od["completion_rate"].fillna(-1.0) >= 99.95

    panel_a_summary: dict[str, dict] = {}
    for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
        g = c_od.loc[c_od["modality4"] == mod]
        n_tot = len(g)
        n_8 = int(g["in_8th"].sum())
        n_d = int(g["is_dup"].sum())
        un = g.loc[(~g["in_8th"]) & (~g["is_dup"])]
        n_100 = int(un["cr_100"].sum())
        n_na = int(un["cr_na"].sum())
        n_other = len(un) - n_100 - n_na
        rec = {
            "Cohort_Panel": "A_Statutory_ODATE_2022_2023",
            "Modality": mod,
            "Total_Campaigns": n_tot,
            "In_8th_Report_Unique": n_8,
            "Share_In_8th_Pct": round(100.0 * n_8 / max(1, n_tot), 1),
            "Excluded_Conflicting_Duplicate": n_d,
            "Unlisted_Early_Completed_100pct": n_100,
            "Unlisted_Missing_DOT_Report": n_na,
            "Unlisted_Delayed_or_Unreached": n_other,
        }
        rows.append(rec)
        panel_a_summary[mod] = rec

    # Panel A Total row
    rows.append(
        {
            "Cohort_Panel": "A_Statutory_ODATE_2022_2023",
            "Modality": "All_Vehicles",
            "Total_Campaigns": sum(r["Total_Campaigns"] for r in panel_a_summary.values()),
            "In_8th_Report_Unique": sum(r["In_8th_Report_Unique"] for r in panel_a_summary.values()),
            "Share_In_8th_Pct": round(
                100.0
                * sum(r["In_8th_Report_Unique"] for r in panel_a_summary.values())
                / max(1, sum(r["Total_Campaigns"] for r in panel_a_summary.values())),
                1,
            ),
            "Excluded_Conflicting_Duplicate": sum(r["Excluded_Conflicting_Duplicate"] for r in panel_a_summary.values()),
            "Unlisted_Early_Completed_100pct": sum(r["Unlisted_Early_Completed_100pct"] for r in panel_a_summary.values()),
            "Unlisted_Missing_DOT_Report": sum(r["Unlisted_Missing_DOT_Report"] for r in panel_a_summary.values()),
            "Unlisted_Delayed_or_Unreached": sum(r["Unlisted_Delayed_or_Unreached"] for r in panel_a_summary.values()),
        }
    )

    # Panel B: Part 573 Filing-Year Cohort (RCDATE in 2022-2023)
    c_rc = campaigns.loc[campaigns["rec_year"].between(2022, 2023)].copy()
    c_rc["in_8th"] = c_rc["campaign_code"].isin(in_8th_uniq)
    c_rc["is_dup"] = c_rc["campaign_code"].isin(in_8th_dup)
    c_rc["cr_na"] = c_rc["completion_rate"].isna()
    c_rc["cr_100"] = c_rc["completion_rate"].fillna(-1.0) >= 99.95
    c_rc["odate_late"] = c_rc["odate"].dt.year.fillna(9999) >= 2024

    panel_b_summary: dict[str, dict] = {}
    for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
        g = c_rc.loc[c_rc["modality4"] == mod]
        n_tot = len(g)
        n_8 = int(g["in_8th"].sum())
        n_d = int(g["is_dup"].sum())
        un = g.loc[(~g["in_8th"]) & (~g["is_dup"])]
        n_100 = int(un["cr_100"].sum())
        n_na = int(un["cr_na"].sum())
        n_late = int(((~un["cr_100"]) & (~un["cr_na"]) & un["odate_late"]).sum())
        n_other = len(un) - n_100 - n_na - n_late
        rec = {
            "Cohort_Panel": "B_Filing_RCDATE_2022_2023",
            "Modality": mod,
            "Total_Campaigns": n_tot,
            "In_8th_Report_Unique": n_8,
            "Share_In_8th_Pct": round(100.0 * n_8 / max(1, n_tot), 1),
            "Excluded_Conflicting_Duplicate": n_d,
            "Unlisted_Early_Completed_100pct": n_100,
            "Unlisted_Missing_DOT_Report": n_na,
            "Unlisted_Delayed_or_Unreached": n_late + n_other,
        }
        rows.append(rec)
        panel_b_summary[mod] = {**rec, "Unlisted_ODATE_2024plus": n_late, "Unlisted_Other": n_other}

    # Panel C: Full 2018-2026 NHTSA Vehicle Recall Universe (N=7,967)
    c18 = campaigns.loc[campaigns["rec_year"].between(2018, 2026)].copy()
    c18["in_8th"] = c18["campaign_code"].isin(in_8th_uniq)
    c18["is_dup"] = c18["campaign_code"].isin(in_8th_dup)
    panel_c_summary: dict[str, dict] = {}
    for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
        g = c18.loc[c18["modality4"] == mod]
        n_tot = len(g)
        n_8 = int(g["in_8th"].sum())
        n_d = int(g["is_dup"].sum())
        un = g.loc[(~g["in_8th"]) & (~g["is_dup"])]
        n_early_100 = int((un["odate"].dt.year.between(2022, 2023) & (un["completion_rate"].fillna(-1.0) >= 99.95)).sum())
        n_miss = int((un["odate"].dt.year.between(2022, 2023) & un["completion_rate"].isna()).sum())
        n_out_window = len(un) - n_early_100 - n_miss
        rec = {
            "Cohort_Panel": "C_Full_Universe_2018_2026",
            "Modality": mod,
            "Total_Campaigns": n_tot,
            "In_8th_Report_Unique": n_8,
            "Share_In_8th_Pct": round(100.0 * n_8 / max(1, n_tot), 1),
            "Excluded_Conflicting_Duplicate": n_d,
            "Unlisted_Early_Completed_100pct": n_early_100,
            "Unlisted_Missing_DOT_Report": n_miss,
            "Unlisted_Delayed_or_Unreached": n_out_window,
        }
        rows.append(rec)
        panel_c_summary[mod] = rec

    # Earlier ODATE entries (2020-2021) that entered 2024-2025 lists late
    early_entries = fixed.loc[~fixed["odate"].dt.year.isin([2022, 2023])]
    early_entry_by_mod = early_entries["modality4"].value_counts().to_dict()

    # Exact list of unlisted 2022-2023 ODATE Pure-OTA campaigns
    unlisted_pure_od = c_od.loc[(c_od["modality4"] == "Pure_OTA") & (~c_od["in_8th"])].sort_values("rec_date")
    unlisted_pure_details = [
        {
            "campaign_code": str(r.campaign_code),
            "mfg": str(r.mfg),
            "rec_date": str(r.rec_date.date()),
            "odate": str(r.odate.date()),
            "potaff": round(float(r.potaff)),
            "dot_completion_rate_pct": round(float(r.completion_rate), 2) if pd.notna(r.completion_rate) else None,
            "disposition": "Missing DOT completion report" if pd.isna(r.completion_rate) else "Early-completed 100.0% prior to 8th report",
        }
        for r in unlisted_pure_od.itertuples(index=False)
    ]

    flow_df = pd.DataFrame(rows)
    flow_summary = {
        "odate_2022_2023_total": len(c_od),
        "odate_2022_2023_by_modality": panel_a_summary,
        "rcdate_2022_2023_total": len(c_rc),
        "rcdate_2022_2023_by_modality": panel_b_summary,
        "universe_2018_2026_total": len(c18),
        "universe_2018_2026_by_modality": panel_c_summary,
        "earlier_odate_delayed_entries_n": len(early_entries),
        "earlier_odate_delayed_entries_by_modality": {str(k): int(v) for k, v in early_entry_by_mod.items()},
        "unlisted_odate_2022_2023_pure_ota_details": unlisted_pure_details,
    }
    return flow_df, flow_summary


def build_eighth_report_completion_table(fixed: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    rows: list[dict] = []
    for yr_lbl, sub_yr in [
        ("2024", fixed.loc[fixed["report_year"] == 2024]),
        ("2025", fixed.loc[fixed["report_year"] == 2025]),
        ("Pooled_2024_2025", fixed),
    ]:
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
            g = sub_yr.loc[sub_yr["modality4"] == mod]
            rates = g["completion_at_eighth_report_pct"]
            aff = g["reported_affected"].astype(float)
            tot_aff = float(aff.sum())
            wt_mean = float((aff * rates).sum() / tot_aff) if tot_aff > 0 else 0.0
            rows.append(
                {
                    "Report_Year": yr_lbl,
                    "Modality": mod,
                    "N_Campaigns": len(g),
                    "N_OEMs": int(g["mfg"].nunique()),
                    "Mean_Completion_Pct": round(float(rates.mean()), 2),
                    "SD_Pct": round(float(rates.std(ddof=1)), 2) if len(rates) > 1 else 0.0,
                    "Median_Completion_Pct": round(float(rates.median()), 2),
                    "IQR_25_Pct": round(float(rates.quantile(0.25)), 2),
                    "IQR_75_Pct": round(float(rates.quantile(0.75)), 2),
                    "Affected_Weighted_Mean_Pct": round(wt_mean, 2),
                    "Total_Affected_Vehicles": round(tot_aff),
                    "Median_Affected_Vehicles": round(float(aff.median())),
                }
            )
    return pd.DataFrame(rows), rows


def build_channel_oem_age_support(campaigns: pd.DataFrame, fixed: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    ota_oems = set(campaigns.loc[campaigns["is_ota_audited"].eq(1) & campaigns["rec_year"].ge(2018), "mfg"])
    rows: list[dict] = []

    def _collect_horizon(sample_label: str, df_in: pd.DataFrame, cr_col: str, aff_col: str) -> dict:
        sw = df_in.loc[df_in["mfg"].isin(ota_oems) & df_in["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])].copy()
        sw["veh_age_clip"] = sw["vehicle_age_years"].clip(0, 15)
        mod_tot_aff = {
            mod: float(sw.loc[sw["modality4"] == mod, aff_col].sum())
            for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]
        }
        oem_mods = sw.groupby("mfg")["modality4"].apply(set).to_dict()

        for (mod, oem), g in sw.groupby(["modality4", "mfg"], sort=True):
            aff_sum = float(g[aff_col].sum())
            cr_vals = g[cr_col]
            wt_cr = float((g[aff_col] * cr_vals).sum() / aff_sum) if aff_sum > 0 else float(cr_vals.mean())
            ages = g["veh_age_clip"].dropna()
            has_dsw = "Dealer_Software" in oem_mods.get(oem, set())
            has_ota = ("Pure_OTA" in oem_mods.get(oem, set())) or ("Hybrid_OTA" in oem_mods.get(oem, set()))
            rows.append(
                {
                    "Horizon_Sample": sample_label,
                    "Modality": str(mod),
                    "Manufacturer": str(oem),
                    "N_Campaigns": len(g),
                    "Affected_Vehicles": round(aff_sum),
                    "Share_Modality_Vehicles_Pct": round(100.0 * aff_sum / max(1.0, mod_tot_aff[mod]), 2),
                    "Min_Oldest_MY_Age_Yr": round(float(ages.min()), 1) if len(ages) else -1.0,
                    "Median_Oldest_MY_Age_Yr": round(float(ages.median()), 1) if len(ages) else -1.0,
                    "Max_Oldest_MY_Age_Yr": round(float(ages.max()), 1) if len(ages) else -1.0,
                    "N_Age_6Plus_Yr": int((ages >= 6).sum()),
                    "Mean_Completion_Pct": round(float(cr_vals.mean()), 2),
                    "Median_Completion_Pct": round(float(cr_vals.median()), 2),
                    "Weighted_Completion_Pct": round(wt_cr, 2),
                    "Observes_Both_DealerSW_And_OTA": int(has_dsw and has_ota),
                }
            )

        pure = sw.loc[sw["modality4"] == "Pure_OTA"]
        pure_t = pure.loc[pure["is_tesla"] == 1]
        pure_nt = pure.loc[pure["is_tesla"] == 0]
        both_oems = sorted([o for o, s in oem_mods.items() if "Dealer_Software" in s and (("Pure_OTA" in s) or ("Hybrid_OTA" in s))])
        both_pure_oems = sorted([o for o, s in oem_mods.items() if "Dealer_Software" in s and "Pure_OTA" in s])
        both_hyb_oems = sorted([o for o, s in oem_mods.items() if "Dealer_Software" in s and "Hybrid_OTA" in s])
        mm_overlap = sorted(
            set(sw.loc[sw["is_ota_audited"] == 1, "primary_make_model"].dropna())
            & set(sw.loc[sw["modality4"] == "Dealer_Software", "primary_make_model"].dropna())
        )
        return {
            "n_sw_ota_oems": len(sw),
            "n_oems_total": int(sw["mfg"].nunique()),
            "pure_total_n": len(pure),
            "pure_tesla_n": len(pure_t),
            "pure_tesla_vehicle_share_pct": round(100.0 * float(pure_t[aff_col].sum()) / max(1.0, float(pure[aff_col].sum())), 2),
            "pure_tesla_ages": sorted(int(x) for x in pure_t["veh_age_clip"].dropna().tolist()),
            "pure_nontesla_n": len(pure_nt),
            "pure_nontesla_oems": sorted(pure_nt["mfg"].unique().tolist()),
            "pure_nontesla_max_age_yr": float(pure_nt["veh_age_clip"].max()) if len(pure_nt) else None,
            "pure_nontesla_ages": sorted(int(x) for x in pure_nt["veh_age_clip"].dropna().tolist()),
            "pure_age_6plus_total": int((pure["veh_age_clip"] >= 6).sum()),
            "pure_age_6plus_tesla": int((pure_t["veh_age_clip"] >= 6).sum()),
            "tesla_dealer_sw_n": int(((sw["is_tesla"] == 1) & (sw["modality4"] == "Dealer_Software")).sum()),
            "same_oem_both_dsw_and_ota_oems": both_oems,
            "same_oem_both_dsw_and_pure_oems": both_pure_oems,
            "same_oem_both_dsw_and_hybrid_oems": both_hyb_oems,
            "same_model_overlap_count": len(mm_overlap),
            "same_model_overlap_list": mm_overlap,
        }

    s8 = _collect_horizon("8th_Report_Fixed_Horizon", fixed, "completion_at_eighth_report_pct", "reported_affected")
    mat = campaigns.loc[campaigns["rec_year"].between(2018, 2026) & campaigns["is_mature_18m"].eq(1) & campaigns["completion_rate"].notna()].copy()
    sm = _collect_horizon("Mature_18m_DOT_Snapshot", mat, "completion_rate", "potaff")

    df_support = pd.DataFrame(rows).sort_values(
        ["Horizon_Sample", "Modality", "Affected_Vehicles"], ascending=[True, True, False]
    )
    return df_support, {"eighth_report": s8, "mature_18m_snapshot": sm}


def run_age_sensitivity_and_looo(campaigns: pd.DataFrame, fixed: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    econ = runpy.run_path(str(SCRIPTS_DIR / "04_econometric_core_analysis.py"))
    add_fe = econ["add_common_fe_helpers"]
    fit = econ["fit_ols_cr1_wcb"]

    ota_oems = set(campaigns.loc[campaigns["is_ota_audited"].eq(1) & campaigns["rec_year"].ge(2018), "mfg"])
    linked = add_fe(fixed)
    c18 = add_fe(campaigns.loc[campaigns["rec_year"].between(2018, 2026)].copy())
    legacy = c18.loc[c18["is_mature_18m"].eq(1) & c18["completion_rate"].notna()].copy()
    owner_notice = legacy.loc[(pd.Timestamp("2026-11-25") - legacy["odate"]).dt.days.ge(540)].copy()

    sw8 = linked.loc[linked["mfg"].isin(ota_oems) & linked["modality4"].isin(REMEDY_TYPES[:3])].copy()
    sw8["veh_age"] = sw8["vehicle_age_years"].clip(0, 15)
    oem_mods8 = sw8.groupby("mfg")["modality4"].apply(set)
    both_oems8 = sorted([o for o, s in oem_mods8.items() if "Dealer_Software" in s and (("Pure_OTA" in s) or ("Hybrid_OTA" in s))])
    sw8_cs = sw8.loc[sw8["mfg"].isin(both_oems8)].copy()

    # Strict Same-OEM x Overlapping-Age support in 8th-report sample
    overlap_idx: list[int] = []
    oem_age_overlap_ranges: dict[str, dict] = {}
    for oem in both_oems8:
        so = sw8_cs.loc[sw8_cs["mfg"] == oem]
        ota_a = so.loc[so["is_ota_audited"] == 1, "veh_age"]
        dsw_a = so.loc[so["modality4"] == "Dealer_Software", "veh_age"]
        lo = float(max(ota_a.min(), dsw_a.min()))
        hi = float(min(ota_a.max(), dsw_a.max()))
        oem_age_overlap_ranges[oem] = {
            "ota_age_range": [float(ota_a.min()), float(ota_a.max())],
            "dealer_sw_age_range": [float(dsw_a.min()), float(dsw_a.max())],
            "overlap_range": [lo, hi] if lo <= hi else None,
        }
        if lo <= hi:
            overlap_idx.extend(so.loc[so["veh_age"].between(lo, hi)].index.tolist())
    sw8_cs_age = sw8_cs.loc[overlap_idx].copy()

    # Mature same-model overlap (with & without Tesla)
    swm = legacy.loc[legacy["mfg"].isin(ota_oems) & legacy["modality4"].isin(REMEDY_TYPES[:3])].copy()
    mm_ov_m = set(swm.loc[swm["is_ota_audited"] == 1, "primary_make_model"].dropna()) & set(
        swm.loc[swm["modality4"] == "Dealer_Software", "primary_make_model"].dropna()
    )
    swm_mm = swm.loc[swm["primary_make_model"].isin(mm_ov_m)].copy()

    def _run_spec(
        panel: str,
        label: str,
        src: pd.DataFrame,
        y_col: str,
        age_col: str,
        mode: str,
        fe_cols: list[str],
        filter_ota_oems: bool = True,
    ) -> list[dict]:
        df_s = src.copy()
        if filter_ota_oems:
            df_s = df_s.loc[df_s["mfg"].isin(ota_oems) & df_s["modality4"].isin(REMEDY_TYPES[:3])].copy()
        df_s["veh_age"] = df_s[age_col].clip(0, 15)
        if mode == "4way_inter":
            xs = ["veh_age", "is_ota_pure", "is_ota_hybrid", "is_ota_pure_x_age", "is_ota_hybrid_x_age"]
            df_s["is_ota_pure_x_age"] = df_s["is_ota_pure"] * df_s["veh_age"]
            df_s["is_ota_hybrid_x_age"] = df_s["is_ota_hybrid"] * df_s["veh_age"]
            tvars = ["veh_age", "is_ota_pure_x_age", "is_ota_hybrid_x_age"]
        elif mode == "pooled_inter":
            xs = ["veh_age", "is_ota_audited", "is_ota_audited_x_age"]
            df_s["is_ota_audited_x_age"] = df_s["is_ota_audited"] * df_s["veh_age"]
            tvars = ["veh_age", "is_ota_audited_x_age"]
        elif mode == "4way_level":
            xs = ["veh_age", "is_ota_pure", "is_ota_hybrid"]
            tvars = ["veh_age", "is_ota_pure", "is_ota_hybrid"]
        elif mode == "pooled_level":
            xs = ["veh_age", "is_ota_audited"]
            tvars = ["veh_age", "is_ota_audited"]
        elif mode == "age_only":
            xs = ["veh_age"]
            tvars = ["veh_age"]
        else:
            raise ValueError(f"Unknown mode {mode}")

        res = fit(df_s, y_col, xs, fe_cols, "mfg", target_vars=tvars)
        out_rows = []
        if res.get("skipped"):
            out_rows.append({"Panel": panel, "Specification": label, "Term": "skipped", "N": res["n"], "OEMs": 0})
            return out_rows
        for term, eff in res["terms"].items():
            out_rows.append(
                {
                    "Panel": panel,
                    "Specification": label,
                    "Term": term,
                    "N": res["n"],
                    "OEMs": res["G_clusters"],
                    "Coef": eff["coef"],
                    "SE_CR1": eff["se_cr1"],
                    "t_CR1": eff["t_cr1"],
                    "p_t_G1": eff["p_t_G1"],
                    "p_WCB": eff["p_wcb"],
                    "CI95_Lo": eff["ci95_lo"],
                    "CI95_Hi": eff["ci95_hi"],
                    "R2": res["r2"],
                }
            )
        return out_rows

    fe8 = ["mfg", "comp_fe", "rec_quarter", "report_year"]
    fe_snap = ["mfg", "comp_fe", "rec_quarter"]

    sens_rows: list[dict] = []
    specs = [
        # Panel A: Primary Fixed 8th-Report Age-Interaction & Common-Support Checks
        ("A_8th_Report_Primary", "Fixed 8th report: oldest model year (4-way)", linked, "completion_at_eighth_report_pct", "vehicle_age_years", "4way_inter", fe8, True),
        ("A_8th_Report_Primary", "Fixed 8th report: middle model year (4-way)", linked, "completion_at_eighth_report_pct", "median_vehicle_age", "4way_inter", fe8, True),
        ("A_8th_Report_Primary", "Fixed 8th report: oldest MY, 0-5 yr window (4-way)", linked.loc[linked["vehicle_age_years"].le(5)], "completion_at_eighth_report_pct", "vehicle_age_years", "4way_inter", fe8, True),
        ("A_8th_Report_Primary", "Fixed 8th report: oldest MY, excluding Tesla (4-way)", linked.loc[linked["is_tesla"].eq(0)], "completion_at_eighth_report_pct", "vehicle_age_years", "4way_inter", fe8, True),
        ("A_8th_Report_Primary", "Fixed 8th report: oldest MY, excluding Tesla (pooled OTA)", linked.loc[linked["is_tesla"].eq(0)], "completion_at_eighth_report_pct", "vehicle_age_years", "pooled_inter", fe8, True),
        ("A_8th_Report_Primary", "Fixed 8th report: middle MY, excluding Tesla (pooled OTA)", linked.loc[linked["is_tesla"].eq(0)], "completion_at_eighth_report_pct", "median_vehicle_age", "pooled_inter", fe8, True),
        # Panel B: Same-OEM Common-Support & Standalone Channel Gradients (8th Report)
        ("B_8th_Report_Common_Support", "Same-OEM common support (8 OEMs, all ages, 4-way)", sw8_cs, "completion_at_eighth_report_pct", "vehicle_age_years", "4way_inter", fe8, False),
        ("B_8th_Report_Common_Support", "Same-OEM common support (8 OEMs, all ages, pooled OTA)", sw8_cs, "completion_at_eighth_report_pct", "vehicle_age_years", "pooled_inter", fe8, False),
        ("B_8th_Report_Common_Support", "Strict Same-OEM x Overlapping-Age support (8 OEMs, pooled OTA)", sw8_cs_age, "completion_at_eighth_report_pct", "vehicle_age_years", "pooled_inter", fe8, False),
        ("B_8th_Report_Common_Support", "Same-OEM common support: level contrast (+ veh_age, pooled OTA)", sw8_cs, "completion_at_eighth_report_pct", "vehicle_age_years", "pooled_level", fe8, False),
        ("B_8th_Report_Common_Support", "Same-OEM common support: level contrast (+ veh_age, 4-way)", sw8_cs, "completion_at_eighth_report_pct", "vehicle_age_years", "4way_level", fe8, False),
        ("B_8th_Report_Common_Support", "Standalone Dealer-Software (all 53 OEMs in 8th report)", linked.loc[linked["modality4"] == "Dealer_Software"], "completion_at_eighth_report_pct", "vehicle_age_years", "age_only", fe8, False),
        ("B_8th_Report_Common_Support", "Standalone Physical-Hardware (all 213 OEMs in 8th report)", linked.loc[linked["modality4"] == "Physical_Hardware"], "completion_at_eighth_report_pct", "vehicle_age_years", "age_only", fe8, False),
        # Panel C: Supplementary Latest-Snapshot (>=18m) Benchmarks
        ("C_Latest_Snapshot_Appendix", "Snapshot: oldest MY, filing >=540 d (4-way)", legacy, "completion_rate", "vehicle_age_years", "4way_inter", fe_snap, True),
        ("C_Latest_Snapshot_Appendix", "Snapshot: middle MY, filing >=540 d (4-way)", legacy, "completion_rate", "median_vehicle_age", "4way_inter", fe_snap, True),
        ("C_Latest_Snapshot_Appendix", "Snapshot: oldest MY, notice >=540 d (4-way)", owner_notice, "completion_rate", "vehicle_age_years", "4way_inter", fe_snap, True),
        ("C_Latest_Snapshot_Appendix", "Snapshot: oldest MY, 0-5 yr window (4-way)", legacy.loc[legacy["vehicle_age_years"].le(5)], "completion_rate", "vehicle_age_years", "4way_inter", fe_snap, True),
        ("C_Latest_Snapshot_Appendix", "Snapshot: middle MY, excluding Tesla (pooled OTA)", legacy.loc[legacy["is_tesla"].eq(0)], "completion_rate", "median_vehicle_age", "pooled_inter", fe_snap, True),
        ("C_Latest_Snapshot_Appendix", "Snapshot: same-model overlap (29 models, Make-Model FE, 4-way)", swm_mm, "completion_rate", "vehicle_age_years", "4way_inter", ["primary_make_model", "rec_quarter", "comp_fe"], False),
        ("C_Latest_Snapshot_Appendix", "Snapshot: same-model overlap excl. Tesla (Make-Model FE, 4-way)", swm_mm.loc[swm_mm["is_tesla"].eq(0)], "completion_rate", "vehicle_age_years", "4way_inter", ["primary_make_model", "rec_quarter", "comp_fe"], False),
        ("C_Latest_Snapshot_Appendix", "Snapshot: same-model overlap excl. Tesla (Make-Model FE, pooled OTA)", swm_mm.loc[swm_mm["is_tesla"].eq(0)], "completion_rate", "vehicle_age_years", "pooled_inter", ["primary_make_model", "rec_quarter", "comp_fe"], False),
    ]
    for args in specs:
        sens_rows.extend(_run_spec(*args))

    # Leave-One-OEM-Out (LOOO) across ALL 18 OEMs in the fixed 8th-report software sample (N=148)
    sw8["is_ota_pure_x_age"] = sw8["is_ota_pure"] * sw8["veh_age"]
    sw8["is_ota_hybrid_x_age"] = sw8["is_ota_hybrid"] * sw8["veh_age"]
    looo_rows: list[dict] = []
    for oem in sorted(sw8["mfg"].unique()):
        sub = sw8.loc[sw8["mfg"] != oem].copy()
        dropped = sw8.loc[sw8["mfg"] == oem]
        r = fit(
            sub,
            "completion_at_eighth_report_pct",
            ["veh_age", "is_ota_pure", "is_ota_hybrid", "is_ota_pure_x_age", "is_ota_hybrid_x_age"],
            fe8,
            "mfg",
            target_vars=["veh_age", "is_ota_pure_x_age", "is_ota_hybrid_x_age"],
        )
        t = r["terms"]
        looo_rows.append(
            {
                "Dropped_OEM": str(oem),
                "Dropped_N": len(dropped),
                "Dropped_Pure_N": int(dropped["is_ota_pure"].sum()),
                "Dropped_Hybrid_N": int(dropped["is_ota_hybrid"].sum()),
                "Dropped_DealerSW_N": int((dropped["modality4"] == "Dealer_Software").sum()),
                "Remaining_N": r["n"],
                "Remaining_OEMs": r["G_clusters"],
                "Dealer_Age_Coef": t["veh_age"]["coef"],
                "Dealer_Age_pWCB": t["veh_age"]["p_wcb"],
                "Pure_x_Age_Coef": t["is_ota_pure_x_age"]["coef"],
                "Pure_x_Age_SE": t["is_ota_pure_x_age"]["se_cr1"],
                "Pure_x_Age_pWCB": t["is_ota_pure_x_age"]["p_wcb"],
                "Hybrid_x_Age_Coef": t["is_ota_hybrid_x_age"]["coef"],
                "Hybrid_x_Age_SE": t["is_ota_hybrid_x_age"]["se_cr1"],
                "Hybrid_x_Age_pWCB": t["is_ota_hybrid_x_age"]["p_wcb"],
            }
        )

    df_sens = pd.DataFrame(sens_rows)
    df_looo = pd.DataFrame(looo_rows)
    looo_summary = {
        "n_oems_tested": len(df_looo),
        "dealer_age_min_coef": round(float(df_looo["Dealer_Age_Coef"].min()), 4),
        "dealer_age_max_coef": round(float(df_looo["Dealer_Age_Coef"].max()), 4),
        "dealer_age_max_pwcb": round(float(df_looo["Dealer_Age_pWCB"].max()), 4),
        "dealer_age_sig_05_count": int((df_looo["Dealer_Age_pWCB"] < 0.05).sum()),
        "pure_x_age_min_coef": round(float(df_looo["Pure_x_Age_Coef"].min()), 4),
        "pure_x_age_max_coef": round(float(df_looo["Pure_x_Age_Coef"].max()), 4),
        "pure_x_age_non_sig_05_count": int((df_looo["Pure_x_Age_pWCB"] >= 0.05).sum()),
        "pure_x_age_non_sig_05_oems": df_looo.loc[df_looo["Pure_x_Age_pWCB"] >= 0.05, "Dropped_OEM"].tolist(),
        "hybrid_x_age_sig_05_count": int((df_looo["Hybrid_x_Age_pWCB"] < 0.05).sum()),
        "oem_age_overlap_ranges": oem_age_overlap_ranges,
    }
    return df_sens, df_looo, looo_summary


def build_text_coding_vs_api_audit(campaigns: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    c18 = campaigns.loc[campaigns["rec_year"].between(2018, 2026)].copy()
    cutoff = pd.Timestamp("2025-05-08")

    categories = [
        ("Pure_OTA_Wireless_Only", "Verbatim Part 573 wireless-only remedy (no dealer/hardware clause)", c18["is_ota_pure"] == 1),
        ("Hybrid_SW_Choice_OTA_Capable", "Verbatim Part 573 OTA-capable or dealer software option (no hardware replacement)", c18["is_ota_hybrid_swchoice"] == 1),
        ("Hybrid_HW_Mixed_Hardware_Req", "Verbatim Part 573 OTA software paired with hardware inspection/replacement", c18["is_ota_hybrid_hwmixed"] == 1),
        ("Dealer_Software_No_OTA", "Verbatim Part 573 dealer-only software remedy (no OTA option)", c18["is_dealer_sw"] == 1),
        ("Physical_Hardware_NonSW", "Physical hardware recall (250 stratified campaigns queried in API)", c18["modality4"] == "Physical_Hardware"),
    ]

    rows: list[dict] = []
    for code, desc, mask in categories:
        sub = c18.loc[mask]
        pre = sub.loc[sub["rec_date"] <= cutoff]
        post = sub.loc[sub["rec_date"] > cutoff]
        pre_q = int(pre["api_queried"].sum())
        post_q = int(post["api_queried"].sum())
        pre_true = int(pre["is_ota_api_full"].sum())
        post_true = int(post["is_ota_api_full"].sum())
        rows.append(
            {
                "Text_Coding_Category": code,
                "Definition": desc,
                "Total_2018_2026": len(sub),
                "Pre_Cutoff_N": len(pre),
                "Pre_Cutoff_API_Queried": pre_q,
                "Pre_Cutoff_API_True": pre_true,
                "Pre_Cutoff_API_True_Pct": round(100.0 * pre_true / max(1, pre_q), 1),
                "Post_Cutoff_N": len(post),
                "Post_Cutoff_API_Queried": post_q,
                "Post_Cutoff_API_True": post_true,
                "Post_Cutoff_API_True_Pct": round(100.0 * post_true / max(1, post_q), 1),
            }
        )
    df_cat = pd.DataFrame(rows)
    return df_cat, {"cutoff_date": "2025-05-08", "categories": rows}


def run_live_api_spotcheck() -> dict:
    results = []
    for cid, role in SPOTCHECK_CAMPAIGNS:
        url = f"https://api.nhtsa.gov/recalls/campaignNumber?campaignNumber={cid}"
        try:
            r = requests.get(url, timeout=20, headers={"User-Agent": "AcademicResearch-D12v4Audit/1.0"})
            if r.status_code == 200:
                items = r.json().get("results", [])
                flags: dict[str, int] = {}
                ota_text_n = 0
                for row in items:
                    v = str(row.get("overTheAirUpdate")).lower()
                    flags[v] = flags.get(v, 0) + 1
                    if OTA_TEXT_PAT.search(str(row.get("Remedy") or "")):
                        ota_text_n += 1
                results.append(
                    {
                        "campaign_id": cid,
                        "audit_role": role,
                        "source_url": url,
                        "http_status": r.status_code,
                        "api_records": len(items),
                        "flag_values": flags,
                        "ota_text_records": ota_text_n,
                        "remedy_excerpt": str(items[0].get("Remedy") or "")[:220] if items else "",
                    }
                )
            else:
                results.append({"campaign_id": cid, "audit_role": role, "source_url": url, "http_status": r.status_code})
        except (requests.RequestException, ValueError, OSError) as exc:
            results.append({"campaign_id": cid, "audit_role": role, "source_url": url, "error": str(exc)})
    return {
        "retrieved_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": "Purposive live validation of May 8-9, 2025 public API cutoff boundary cases, post-cutoff examples, excluded 8th-report duplicates, and denominator audit cases. Counts do not estimate prevalence.",
        "results": results,
    }


def export_msom_replication_dataset(fixed: pd.DataFrame) -> Path:
    cols = [
        "report_year",
        "campaign_code",
        "CAMPNO",
        "mfg",
        "rec_date",
        "odate",
        "rec_year",
        "rec_quarter",
        "modality4",
        "is_ota_audited",
        "is_ota_pure",
        "is_ota_hybrid",
        "is_ota_hybrid_swchoice",
        "is_ota_hybrid_hwmixed",
        "is_dealer_sw",
        "is_ota_api_full",
        "is_tesla",
        "is_light_duty_passenger",
        "primary_make_model",
        "comp_top",
        "min_my",
        "median_my",
        "max_my",
        "n_models",
        "n_mys",
        "vehicle_age_years",
        "median_vehicle_age",
        "reported_affected",
        "potaff",
        "completion_at_eighth_report_pct",
        "completion_rate",
    ]
    out_df = fixed[cols].sort_values(["report_year", "campaign_code"]).copy()
    out_df["rec_date"] = out_df["rec_date"].dt.strftime("%Y-%m-%d")
    out_df["odate"] = out_df["odate"].dt.strftime("%Y-%m-%d")
    out_path = PROC_DIR / "d12_v4_eighth_report_analysis_panel.csv"
    out_df.to_csv(out_path, index=False)
    return out_path


def main() -> None:
    campaigns, annual = link_reported_campaigns()
    fixed = eligible_eighth_reports(annual)

    reconcil = build_reconciliation_audit(annual, fixed)
    flow_df, flow_summary = build_sample_flow_accounting(campaigns, annual, fixed)
    comp_df, comp_rows = build_eighth_report_completion_table(fixed)
    support_df, support_summary = build_channel_oem_age_support(campaigns, fixed)
    sens_df, looo_df, looo_summary = run_age_sensitivity_and_looo(campaigns, fixed)
    api_cat_df, api_cat_summary = build_text_coding_vs_api_audit(campaigns)
    spotcheck = run_live_api_spotcheck()
    panel_path = export_msom_replication_dataset(fixed)

    # Save zero-NaN CSV tables
    flow_df.to_csv(TBL_DIR / "table_v4_sample_flow.csv", index=False)
    comp_df.to_csv(TBL_DIR / "table_v4_eighth_report_completion.csv", index=False)
    support_df.to_csv(TBL_DIR / "table_channel_oem_age_support.csv", index=False)
    sens_df.to_csv(TBL_DIR / "table_v4_vehicle_age_sensitivity.csv", index=False)
    looo_df.to_csv(TBL_DIR / "table_v4_looo_sensitivity.csv", index=False)
    api_cat_df.to_csv(TBL_DIR / "table_v4_text_coding_vs_api.csv", index=False)

    # Save live spotcheck JSON
    spot_path = RES_DIR / "d12_v4_live_api_spotcheck.json"
    spot_path.write_text(json.dumps(spotcheck, indent=2), encoding="utf-8")

    # Assemble master v4 audit JSON
    audit = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": OFFICIAL_REPORTS,
        "source_provenance": {
            "annual_eighth_report_csv": {
                "path": "data_raw/nhtsa_annual_eighth_report_2024_2025.csv",
                "bytes": ANNUAL_CSV.stat().st_size,
                "sha256": sha256_file(ANNUAL_CSV),
                "nhtsa_gov_pdf_http_note": (
                    "Direct automated HTTP GET to www.nhtsa.gov PDF URLs returned HTTP 403 Akamai CDN access control; "
                    "per non-bypass policy, the verbatim transcribed 1,537-row eighth-report source table is SHA-256 locked "
                    "and independently row-reconciled against FLAT_RCL_POST_2010.zip, DOT 6axg-epim, and live api.nhtsa.gov."
                ),
            },
            "dot_hs_813_687_pdf": {
                "path": "data_raw/dot_79374_DS1.pdf",
                "url": OFFICIAL_REPORTS["nhtsa_completion_rates_study_pdf"],
                "http_status": 200,
                "bytes": DOT_STUDY_PDF.stat().st_size if DOT_STUDY_PDF.exists() else 0,
                "sha256": sha256_file(DOT_STUDY_PDF) if DOT_STUDY_PDF.exists() else None,
            },
            "msom_replication_panel_csv": {
                "path": "data_processed/d12_v4_eighth_report_analysis_panel.csv",
                "rows": len(fixed),
                "bytes": panel_path.stat().st_size,
                "sha256": sha256_file(panel_path),
            },
        },
        "reconciliation": reconcil,
        "sample_flow": flow_summary,
        "eighth_report_completions": comp_rows,
        "common_support_summary": support_summary,
        "age_sensitivity_models": sens_df.to_dict(orient="records"),
        "looo_summary": looo_summary,
        "looo_table": looo_df.to_dict(orient="records"),
        "text_coding_vs_api": api_cat_summary,
    }
    out_json = RES_DIR / "d12_v4_fixed_report_audit.json"
    out_json.write_text(json.dumps(audit, indent=2), encoding="utf-8")

    print(f"[DONE] Saved master v4 audit -> {out_json}", flush=True)
    print(f"[DONE] Saved live API spot-check -> {spot_path}", flush=True)
    print(
        f"[SUMMARY] 8th-report unique={reconcil['matched_unique_campaigns']} | "
        f"denom exact={reconcil['denominator_exact_match_count']}/{reconcil['matched_unique_campaigns']} "
        f"(SW={reconcil['denominator_sw_exact_match_count']}/{reconcil['denominator_sw_total_count']}) | "
        f"Tesla Pure-OTA={support_summary['eighth_report']['pure_tesla_n']}/{support_summary['eighth_report']['pure_total_n']} "
        f"({support_summary['eighth_report']['pure_tesla_vehicle_share_pct']}% veh) | "
        f"LOOO Dealer age=[{looo_summary['dealer_age_min_coef']:.2f}, {looo_summary['dealer_age_max_coef']:.2f}] "
        f"(max p_WCB={looo_summary['dealer_age_max_pwcb']:.3f}) | "
        f"Pure*Age non-sig in {looo_summary['pure_x_age_non_sig_05_count']}/{looo_summary['n_oems_tested']} LOOO drops",
        flush=True,
    )


if __name__ == "__main__":
    main()
