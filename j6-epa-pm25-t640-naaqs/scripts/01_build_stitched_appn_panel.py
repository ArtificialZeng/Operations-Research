"""Step 01 (Pillar 1): Exact Stitched Appendix N Panel, Official EPA DV Reconciliation,
Census ACS 2023 Environmental Justice Audit, and Exogenous Null Verification (Margins A, C, D).

Fixes Wave-6 forensic defects:
  - Filters strictly to regulatory SLAMS/App. N-eligible monitors (excluding SPM, INDUSTRIAL,
    OTHER, QA COLLOCATED, INDEX SITE, UNKNOWN, and QUALITY ASSURANCE monitoring objective).
  - Completely resolves the mid-2023 T640 split-year bug by stitching retroactive 736/738
    (POC + 20 AND any non-+20 date-non-overlapping pairs) seamlessly with 636/638 on the
    physical canonical POC, and raw 236/238 with 636/638 in the pre-alignment universe.
  - Computes exact 40 CFR Part 50 Appendix N quarterly-weighted annual means (>= 75% quarterly
    completeness in all 4 quarters/year x 3 full years, rounded to 0.1 ug/m3, NA iff >= 9.1).
  - Reconciles stitched county counts against official EPA PM2.5 Design Value Excel workbooks.
  - Audits Environmental Justice & regional demographics (Census ACS 2023) of T640-Flipped vs.
    Still-Nonattainment vs. Cleanly-Attaining counties.
  - Verifies clean nulls on Margins A (deduplicated FEM->FRM switching), C (monitor pruning),
    and D (true gravimetric FRM PM2.5) using strictly exogenous DV_18_20, while exposing the
    endogenous DV_21_23 RTM artifact via a fake-rule RTM placebo.
"""

from __future__ import annotations

import math
import re
from typing import Any

import numpy as np
import openpyxl
import pandas as pd
from econ_utils import (
    ENRICH_DIR,
    PROC_DIR,
    REGION_MAP,
    RES_DIR,
    VALID_STATES,
    WAVE6_RAW_DIR,
    mc_class,
    ols_cr1,
    read_zip_csv,
    save_json_lf,
)
from scipy import stats

REGULATORY_MONITOR_TYPES = {"SLAMS", "TRIBAL", "EPA", "NON-EPA FEDERAL"}
NON_REG_TYPES = {"SPM", "INDUSTRIAL", "OTHER", "QA COLLOCATED", "INDEX SITE", "UNKNOWN"}


def load_monitor_metadata() -> pd.DataFrame:
    """Load and clean EPA 88101 monitor metadata from aqs_monitors.zip."""
    mons = read_zip_csv(
        WAVE6_RAW_DIR / "aqs_monitors.zip",
        dtype={
            "State Code": str,
            "County Code": str,
            "Site Number": str,
            "Parameter Code": str,
            "POC": str,
            "Last Method Code": str,
        },
    )
    mons = mons[mons["Parameter Code"] == "88101"].copy()
    mons["state_fips"] = mons["State Code"].str.zfill(2)
    mons = mons[mons["state_fips"].isin(VALID_STATES)].copy()
    mons["county_fips"] = mons["state_fips"] + mons["County Code"].str.zfill(3)
    mons["site_id"] = mons["county_fips"] + "-" + mons["Site Number"].str.zfill(4)
    mons["poc_int"] = pd.to_numeric(mons["POC"], errors="coerce").fillna(-1).astype(int)
    mons["mon_id"] = mons["site_id"] + "-" + mons["poc_int"].astype(str)
    mons["monitor_type"] = mons["Monitor Type"].fillna("UNKNOWN").str.strip().str.upper()
    mons["mon_obj"] = mons["Monitoring Objective"].fillna("").str.strip().str.upper()
    mons["is_naaqs_primary"] = (mons["NAAQS Primary Monitor"] == "Y").astype(int)
    mons["is_slams_strict"] = (
        (mons["monitor_type"] == "SLAMS") & (mons["mon_obj"] != "QUALITY ASSURANCE")
    ).astype(int)
    mons["is_appn_reg"] = (
        mons["monitor_type"].isin(REGULATORY_MONITOR_TYPES)
        & (mons["mon_obj"] != "QUALITY ASSURANCE")
    ).astype(int)
    mons["first_year"] = pd.to_numeric(mons["First Year of Data"], errors="coerce")
    mons["lat"] = pd.to_numeric(mons["Latitude"], errors="coerce")
    mons["lon"] = pd.to_numeric(mons["Longitude"], errors="coerce")
    mons["exclusions"] = mons["Exclusions"].fillna("")
    return mons.drop_duplicates("mon_id").reset_index(drop=True)


def load_daily_88101(years: list[int]) -> pd.DataFrame:
    """Load daily 24-hour 88101 microdata across specified years."""
    use_d = [
        "State Code",
        "County Code",
        "Site Num",
        "POC",
        "Sample Duration",
        "Date Local",
        "Event Type",
        "Arithmetic Mean",
        "Method Code",
        "Method Name",
    ]
    dfs = []
    for yr in years:
        df = read_zip_csv(
            WAVE6_RAW_DIR / f"daily_88101_{yr}.zip",
            usecols=use_d,
            dtype={
                "State Code": str,
                "County Code": str,
                "Site Num": str,
                "POC": str,
                "Method Code": str,
            },
        )
        df = df[df["Sample Duration"].isin(["24 HOUR", "24-HR BLK AVG"])].copy()
        df["Year"] = yr
        dfs.append(df)
    daily = pd.concat(dfs, ignore_index=True)
    daily["state_fips"] = daily["State Code"].str.zfill(2)
    daily = daily[daily["state_fips"].isin(VALID_STATES)].copy()
    daily["county_fips"] = daily["state_fips"] + daily["County Code"].str.zfill(3)
    daily["site_id"] = daily["county_fips"] + "-" + daily["Site Num"].str.zfill(4)
    daily["poc_int"] = pd.to_numeric(daily["POC"], errors="coerce").fillna(-1).astype(int)
    daily["mon_id"] = daily["site_id"] + "-" + daily["poc_int"].astype(str)
    daily["method_code"] = daily["Method Code"].str.strip().str.replace(".0", "", regex=False)
    daily["Event Type"] = daily["Event Type"].fillna("None").astype(str)
    daily["Arithmetic Mean"] = pd.to_numeric(daily["Arithmetic Mean"], errors="coerce")
    daily = daily.dropna(subset=["Arithmetic Mean"]).copy()
    daily = daily.drop_duplicates(
        subset=["mon_id", "Date Local", "Sample Duration", "Event Type", "method_code"]
    )

    mc_u = daily[["method_code", "Method Name"]].drop_duplicates("method_code")
    mc_dict = {
        r["method_code"]: mc_class(r["method_code"], r["Method Name"])
        for _, r in mc_u.iterrows()
    }
    daily["inst"] = daily["method_code"].map(mc_dict)
    daily["Month"] = daily["Date Local"].str.slice(5, 7).astype(int)
    daily["Quarter"] = (daily["Month"] - 1) // 3 + 1
    return daily


def load_annual_88101(years: list[int]) -> pd.DataFrame:
    """Load annual_conc_by_monitor PM25 Annual 2024 rows across specified years."""
    use_a = [
        "State Code",
        "County Code",
        "Site Num",
        "Parameter Code",
        "POC",
        "Sample Duration",
        "Pollutant Standard",
        "Event Type",
        "Observation Count",
        "Valid Day Count",
        "Required Day Count",
        "Completeness Indicator",
        "Exceptional Data Count",
        "Arithmetic Mean",
        "Method Name",
        "Date of Last Change",
    ]
    dfs = []
    for yr in years:
        df = read_zip_csv(
            WAVE6_RAW_DIR / f"annual_conc_by_monitor_{yr}.zip",
            usecols=use_a,
            dtype={
                "State Code": str,
                "County Code": str,
                "Site Num": str,
                "Parameter Code": str,
                "POC": str,
            },
        )
        df = df[
            (df["Parameter Code"] == "88101")
            & (df["Sample Duration"].isin(["24 HOUR", "24-HR BLK AVG"]))
            & (df["Pollutant Standard"] == "PM25 Annual 2024")
        ].copy()
        df["Year"] = yr
        dfs.append(df)
    ann = pd.concat(dfs, ignore_index=True)
    ann["state_fips"] = ann["State Code"].str.zfill(2)
    ann = ann[ann["state_fips"].isin(VALID_STATES)].copy()
    ann["county_fips"] = ann["state_fips"] + ann["County Code"].str.zfill(3)
    ann["site_id"] = ann["county_fips"] + "-" + ann["Site Num"].str.zfill(4)
    ann["poc_int"] = pd.to_numeric(ann["POC"], errors="coerce").fillna(-1).astype(int)
    ann["mon_id"] = ann["site_id"] + "-" + ann["poc_int"].astype(str)
    for col in ("Observation Count", "Valid Day Count", "Required Day Count", "Exceptional Data Count", "Arithmetic Mean"):
        ann[col] = pd.to_numeric(ann[col], errors="coerce")
    return ann


def build_t640_poc_stitch_map(daily: pd.DataFrame) -> tuple[dict[str, str], dict[str, Any]]:
    """Build deterministic map raw_mon_id -> canonical_mon_id stitching retroactive T640
    736/738 (POC+20 and any non-+20 date-non-overlapping T640 pairs) back to physical POC.
    """
    d_inc = daily[daily["Event Type"].isin(["None", "Included"])].copy()
    t_sub = d_inc[d_inc["inst"].isin(["T640_RAW", "T640_FW", "T640_RETRO"])].copy()

    # Summarize date spans per (site_id, poc_int, inst)
    spans = (
        t_sub.groupby(["site_id", "poc_int", "mon_id", "inst"], as_index=False)
        .agg(dmin=("Date Local", "min"), dmax=("Date Local", "max"), n_days=("Date Local", "nunique"))
    )
    retro = spans[spans["inst"] == "T640_RETRO"].copy()
    orig = spans[spans["inst"].isin(["T640_RAW", "T640_FW"])].copy()

    orig_by_site: dict[str, dict[int, tuple[str, str]]] = {}
    for _, r in orig.iterrows():
        sid, p = r["site_id"], int(r["poc_int"])
        if sid not in orig_by_site:
            orig_by_site[sid] = {}
        if p in orig_by_site[sid]:
            d0, d1 = orig_by_site[sid][p]
            orig_by_site[sid][p] = (min(d0, r["dmin"]), max(d1, r["dmax"]))
        else:
            orig_by_site[sid][p] = (r["dmin"], r["dmax"])

    stitch_map: dict[str, str] = {}
    n_exact_poc20 = 0
    n_non20_paired = 0
    n_retro_unpaired_shifted = 0
    non20_details: list[dict[str, Any]] = []

    for _, r in retro.iterrows():
        sid = r["site_id"]
        rpoc = int(r["poc_int"])
        rmid = r["mon_id"]
        site_orig = orig_by_site.get(sid, {})
        if rpoc >= 21 and (rpoc - 20) in site_orig:
            stitch_map[rmid] = f"{sid}-{rpoc - 20}"
            n_exact_poc20 += 1
            continue

        # Check non-+20 deterministic date-non-overlapping T640_FW pairing on same site
        fw_cands = spans[
            (spans["site_id"] == sid) & (spans["inst"] == "T640_FW")
        ].sort_values("poc_int")
        matched_poc: int | None = None
        for _, cand in fw_cands.iterrows():
            cpoc = int(cand["poc_int"])
            # Non-overlapping or minimal transition overlap (<= 3 days) and unclaimed
            if (
                r["dmax"] <= cand["dmin"]
                or (pd.Timestamp(r["dmax"]) - pd.Timestamp(cand["dmin"])).days <= 3
            ) and f"{sid}-{cpoc}" not in stitch_map.values():
                matched_poc = cpoc
                break

        if matched_poc is not None:
            stitch_map[rmid] = f"{sid}-{matched_poc}"
            n_non20_paired += 1
            non20_details.append(
                {
                    "site_id": sid,
                    "retro_poc": rpoc,
                    "paired_poc": matched_poc,
                    "retro_span": [r["dmin"], r["dmax"]],
                    "rule": "date_non_overlapping_fw",
                }
            )
        else:
            # Keep distinct physical monitor (shift by -20 only if unoccupied on site)
            if rpoc >= 21 and (rpoc - 20) not in site_orig:
                stitch_map[rmid] = f"{sid}-{rpoc - 20}"
            else:
                stitch_map[rmid] = rmid
            n_retro_unpaired_shifted += 1
            non20_details.append(
                {
                    "site_id": sid,
                    "retro_poc": rpoc,
                    "paired_poc": int(stitch_map[rmid].rsplit("-", 1)[1]),
                    "retro_span": [r["dmin"], r["dmax"]],
                    "rule": "standalone_retro",
                }
            )

    # Also detect sites with multiple T640s switching POCs without +20 (e.g. raw POC a -> fw POC b)
    fw_only_2023 = spans[(spans["inst"] == "T640_FW") & (spans["dmin"] >= "2023-01-01")].copy()
    raw_only_2023 = spans[(spans["inst"] == "T640_RAW") & (spans["dmax"] <= "2024-06-01")].copy()
    n_non20_raw_fw_sites = 0
    for sid, grp_fw in fw_only_2023.groupby("site_id"):
        fw_pocs = set(grp_fw["poc_int"].astype(int))
        raw_pocs = set(raw_only_2023[raw_only_2023["site_id"] == sid]["poc_int"].astype(int))
        if raw_pocs and not fw_pocs.issubset(raw_pocs):
            # Try deterministic date-non-overlapping pairing for unmatched FW POC -> RAW POC
            unmatched_fw = sorted(fw_pocs - raw_pocs)
            unmatched_raw = sorted(raw_pocs - fw_pocs)
            if unmatched_fw and unmatched_raw:
                for fp in unmatched_fw:
                    f_row = grp_fw[grp_fw["poc_int"] == fp].iloc[0]
                    for rp in list(unmatched_raw):
                        r_row = raw_only_2023[
                            (raw_only_2023["site_id"] == sid) & (raw_only_2023["poc_int"] == rp)
                        ].iloc[0]
                        if (pd.Timestamp(r_row["dmax"]) - pd.Timestamp(f_row["dmin"])).days <= 5:
                            # Stitch the new FW POC (and its +20 retro if any) onto rp
                            stitch_map[f"{sid}-{fp}"] = f"{sid}-{rp}"
                            if f"{sid}-{fp + 20}" in stitch_map:
                                stitch_map[f"{sid}-{fp + 20}"] = f"{sid}-{rp}"
                            unmatched_raw.remove(rp)
                            n_non20_raw_fw_sites += 1
                            non20_details.append(
                                {
                                    "site_id": sid,
                                    "raw_poc": rp,
                                    "fw_poc": fp,
                                    "rule": "non20_raw_to_fw_stitch",
                                }
                            )
                            break

    # Count 2023 split-year T640 monitors repaired by stitching
    d23 = t_sub[t_sub["Year"] == 2023].copy()
    d23["canon_id"] = d23["mon_id"].map(lambda m: stitch_map.get(m, m))
    c23_insts = d23.groupby("canon_id")["inst"].nunique()
    n_split_2023_repaired = int((c23_insts >= 2).sum())

    audit = {
        "n_retro_mon_ids_total": len(retro),
        "n_exact_poc_minus_20_stitched": int(n_exact_poc20),
        "n_non20_retro_paired": int(n_non20_paired),
        "n_retro_standalone": int(n_retro_unpaired_shifted),
        "n_non20_raw_to_fw_stitched": int(n_non20_raw_fw_sites),
        "n_split_2023_t640_monitors_repaired": n_split_2023_repaired,
        "non20_details_sample": non20_details[:20],
    }
    return stitch_map, audit


def _quarter_days(year: int, quarter: int) -> int:
    is_leap = (year % 4 == 0) and (year % 100 != 0 or year % 400 == 0)
    if quarter == 1:
        return 91 if is_leap else 90
    if quarter == 2:
        return 91
    return 92


def compute_stitched_appn_annual(
    daily: pd.DataFrame,
    ann: pd.DataFrame,
    stitch_map: dict[str, str],
    universe: str,
) -> pd.DataFrame:
    """Compute exact 40 CFR Part 50 Appendix N quarterly-weighted annual means and strict
    4-quarter >= 75% completeness on stitched daily records for universe in {'RAW', 'ALN'}.
    """
    if universe == "RAW":
        d = daily[
            daily["Event Type"].isin(["None", "Included"])
            & (daily["inst"] != "T640_RETRO")
            & (daily["Year"].between(2018, 2025))
        ].copy()
        # Priority if multiple methods on same stitched day: T640_RAW (1) > T640_FW (2) > other (3)
        prio = {"T640_RAW": 1, "T640_FW": 2, "FRM": 3, "BAM": 3, "OTHER_FEM": 3}
    elif universe == "ALN":
        d = daily[
            daily["Event Type"].isin(["None", "Included"])
            & (daily["inst"] != "T640_RAW")
            & (daily["Year"].between(2018, 2025))
        ].copy()
        # Priority on transition day: T640_FW (1) > T640_RETRO (2) > other (3)
        prio = {"T640_FW": 1, "T640_RETRO": 2, "FRM": 3, "BAM": 3, "OTHER_FEM": 3}
    else:
        raise ValueError(f"Unknown universe: {universe}")

    d["canon_id"] = d["mon_id"].map(lambda m: stitch_map.get(m, m))
    d["prio"] = d["inst"].map(prio).fillna(5)
    # Deduplicate same (canon_id, Date Local) keeping highest-priority method, averaging identical-priority
    d = d.sort_values(["canon_id", "Date Local", "prio"])
    best_p = d.groupby(["canon_id", "Date Local"])["prio"].transform("min")
    d = d[d["prio"] == best_p].copy()

    day_agg = (
        d.groupby(["canon_id", "site_id", "county_fips", "state_fips", "Year", "Quarter", "Date Local"], as_index=False)
        .agg(
            pm25=("Arithmetic Mean", "mean"),
            inst=("inst", "first"),
            mc=("method_code", "first"),
        )
    )

    # Infer scheduled cadence from EPA annual Required Day Count (mapped to canon_id) + daily median gap
    a_inc = ann[ann["Event Type"].isin(["No Events", "Events Included"])].copy()
    a_inc["canon_id"] = a_inc["mon_id"].map(lambda m: stitch_map.get(m, m))
    req_map = (
        a_inc.groupby(["canon_id", "Year"])["Required Day Count"]
        .max()
        .reset_index(name="req_days_ann")
    )

    # Compute median day gap per (canon_id, Year) as fallback cadence
    day_agg["dt_ord"] = pd.to_datetime(day_agg["Date Local"]).map(lambda x: x.toordinal())
    day_agg = day_agg.sort_values(["canon_id", "Year", "dt_ord"])
    day_agg["gap"] = day_agg.groupby(["canon_id", "Year"])["dt_ord"].diff()
    gap_med = (
        day_agg.groupby(["canon_id", "Year"])["gap"]
        .median()
        .reset_index(name="med_gap")
    )

    # Quarterly means and valid day counts
    q_agg = (
        day_agg.groupby(["canon_id", "site_id", "county_fips", "state_fips", "Year", "Quarter"], as_index=False)
        .agg(q_mean=("pm25", "mean"), q_days=("pm25", "size"))
    )
    q_agg = q_agg.merge(req_map, on=["canon_id", "Year"], how="left").merge(
        gap_med, on=["canon_id", "Year"], how="left"
    )

    # Determine scheduled sampling interval (1, 3, 6, or 12 days)
    def infer_interval(req_d: float, mg: float) -> int:
        if pd.notna(req_d) and req_d >= 250:
            return 1
        if pd.notna(req_d) and req_d >= 90:
            return 3
        if pd.notna(req_d) and req_d >= 45:
            return 6
        if pd.notna(req_d) and req_d > 0:
            return 12
        if pd.notna(mg):
            if mg <= 1.5:
                return 1
            if mg <= 4.0:
                return 3
            if mg <= 8.0:
                return 6
            return 12
        return 1

    intervals = [
        infer_interval(r, g)
        for r, g in zip(q_agg["req_days_ann"].to_numpy(), q_agg["med_gap"].to_numpy())
    ]
    q_agg["cadence"] = intervals
    # Scheduled samples in each quarter under 40 CFR 50 App. N
    q_agg["q_cal_days"] = [
        _quarter_days(int(y), int(q))
        for y, q in zip(q_agg["Year"].to_numpy(), q_agg["Quarter"].to_numpy())
    ]
    q_agg["q_sched"] = np.maximum(1, np.round(q_agg["q_cal_days"] / q_agg["cadence"]).astype(int))
    q_agg["q_req_75"] = np.ceil(0.75 * q_agg["q_sched"] - 1e-9).astype(int)
    q_agg["q_complete"] = (q_agg["q_days"] >= q_agg["q_req_75"]).astype(int)

    # Dominant instrument and method per (canon_id, Year)
    dom = (
        day_agg.groupby(["canon_id", "Year"], as_index=False)
        .agg(
            dom_inst=("inst", lambda s: s.mode().iloc[0]),
            dom_mc=("mc", lambda s: s.mode().iloc[0]),
            has_t640=("inst", lambda s: int(any(str(x).startswith("T640") for x in s))),
            n_days_yr=("pm25", "size"),
        )
    )

    ann_out = (
        q_agg.groupby(["canon_id", "site_id", "county_fips", "state_fips", "Year"], as_index=False)
        .agg(
            ann_mean=("q_mean", "mean"),
            n_qtrs=("Quarter", "nunique"),
            n_qtrs_complete=("q_complete", "sum"),
            total_days=("q_days", "sum"),
            cadence=("cadence", "first"),
        )
        .merge(dom, on=["canon_id", "Year"], how="left")
    )
    ann_out["appn_year_complete"] = (
        (ann_out["n_qtrs"] == 4) & (ann_out["n_qtrs_complete"] == 4)
    ).astype(int)
    return ann_out


def attach_fixed_ee_flags(ann_stitched: pd.DataFrame, ann_raw: pd.DataFrame, stitch_map: dict[str, str]) -> pd.DataFrame:
    """Attach STRICTLY FIXED EPA Exceptional Event indicators and annual mean reductions
    (eliminating the 50.4% false-positive EPA concurrence row bug!).
    """
    a = ann_raw.copy()
    a["canon_id"] = a["mon_id"].map(lambda m: stitch_map.get(m, m))

    # For each (mon_id, Year) BEFORE stitching, detect true EE flagging and true EPA concurrence
    inc = (
        a[a["Event Type"].isin(["No Events", "Events Included"])]
        .drop_duplicates(["mon_id", "Year"])
        [["mon_id", "canon_id", "Year", "Arithmetic Mean", "Observation Count", "Exceptional Data Count"]]
        .rename(columns={"Arithmetic Mean": "a_mean_incl", "Observation Count": "a_obs_incl", "Exceptional Data Count": "a_ee_cnt"})
    )
    exc = (
        a[a["Event Type"] == "Events Excluded"]
        .drop_duplicates(["mon_id", "Year"])
        [["mon_id", "Year", "Arithmetic Mean", "Observation Count"]]
        .rename(columns={"Arithmetic Mean": "a_mean_excl", "Observation Count": "a_obs_excl"})
    )
    con = (
        a[a["Event Type"] == "Concurred Events Excluded"]
        .drop_duplicates(["mon_id", "Year"])
        [["mon_id", "Year", "Arithmetic Mean", "Observation Count"]]
        .rename(columns={"Arithmetic Mean": "a_mean_conc", "Observation Count": "a_obs_conc"})
    )
    mg = inc.merge(exc, on=["mon_id", "Year"], how="left").merge(con, on=["mon_id", "Year"], how="left")

    # FIXED EPA CONCURRENCE DEFINITION: strictly requires fewer obs OR different mean (> 1e-6)
    has_conc_row = mg["a_mean_conc"].notna()
    true_conc = has_conc_row & (
        (mg["a_obs_conc"].fillna(mg["a_obs_incl"]) < mg["a_obs_incl"])
        | ((mg["a_mean_incl"] - mg["a_mean_conc"]).abs() > 1e-6)
    )
    has_excl_row = mg["a_mean_excl"].notna()
    true_excl = has_excl_row & (
        (mg["a_obs_excl"].fillna(mg["a_obs_incl"]) < mg["a_obs_incl"])
        | ((mg["a_mean_incl"] - mg["a_mean_excl"]).abs() > 1e-6)
    )
    mg["has_conc_row_buggy"] = has_conc_row.astype(int)
    mg["true_ee_conc"] = true_conc.astype(int)
    mg["true_ee_flag"] = (true_excl | true_conc | (mg["a_ee_cnt"].fillna(0) > 0)).astype(int)
    mg["unconc_flag"] = ((mg["true_ee_flag"] == 1) & (mg["true_ee_conc"] == 0)).astype(int)
    mg["ee_red_all"] = np.where(
        mg["true_ee_flag"] == 1,
        np.maximum(
            0.0,
            mg["a_mean_incl"]
            - np.minimum(
                mg["a_mean_excl"].fillna(mg["a_mean_incl"]),
                mg["a_mean_conc"].fillna(mg["a_mean_incl"]),
            ),
        ),
        0.0,
    )
    mg["ee_red_conc"] = np.where(
        mg["true_ee_conc"] == 1,
        np.maximum(0.0, mg["a_mean_incl"] - mg["a_mean_conc"].fillna(mg["a_mean_incl"])),
        0.0,
    )

    # Aggregate to stitched (canon_id, Year) WITHOUT diluting overlapping POC / POC+20 duplicates!
    # In EPA annual_conc_by_monitor, original POC already spans the full calendar year (~350-365 days)
    # while retroactive POC+20 (736/738) duplicates overlapping calendar days (often without carrying
    # the state EE flag). Summing w_obs across overlapping POC & POC+20 dilutes ee_red by ~36%.
    # Rule: if rows overlap (any stitched POC>=21 retroactive duplicate OR w_obs_sum > 366),
    # take max(ee_red) and max(ee_cnt); only take obs-weighted mean for genuinely disjoint non-+20 splits.
    mg["poc_int_row"] = pd.to_numeric(mg["mon_id"].str.rsplit("-", n=1).str[1], errors="coerce").fillna(-1).astype(int)
    mg["is_retro_dup"] = ((mg["mon_id"] != mg["canon_id"]) & (mg["poc_int_row"] >= 21)).astype(int)
    mg["w_obs"] = mg["a_obs_incl"].fillna(0.0).clip(lower=0.0)
    mg["w_red_all"] = mg["ee_red_all"] * mg["w_obs"]
    mg["w_red_conc"] = mg["ee_red_conc"] * mg["w_obs"]
    agg = (
        mg.groupby(["canon_id", "Year"], as_index=False)
        .agg(
            true_ee_flag=("true_ee_flag", "max"),
            true_ee_conc=("true_ee_conc", "max"),
            has_conc_row_buggy=("has_conc_row_buggy", "max"),
            ee_cnt_sum=("a_ee_cnt", "sum"),
            ee_cnt_max=("a_ee_cnt", "max"),
            w_obs_sum=("w_obs", "sum"),
            w_red_all_sum=("w_red_all", "sum"),
            w_red_conc_sum=("w_red_conc", "sum"),
            red_all_max=("ee_red_all", "max"),
            red_conc_max=("ee_red_conc", "max"),
            has_retro_dup=("is_retro_dup", "max"),
            n_stitched_rows=("mon_id", "size"),
        )
    )
    agg["unconc_flag"] = ((agg["true_ee_flag"] == 1) & (agg["true_ee_conc"] == 0)).astype(int)
    is_overlap = (agg["n_stitched_rows"] > 1) & ((agg["has_retro_dup"] == 1) | (agg["w_obs_sum"] > 366.0))
    agg["ee_red_all"] = np.where(
        is_overlap,
        agg["red_all_max"],
        np.where(agg["w_obs_sum"] > 0, agg["w_red_all_sum"] / agg["w_obs_sum"], 0.0),
    )
    agg["ee_red_conc"] = np.where(
        is_overlap,
        agg["red_conc_max"],
        np.where(agg["w_obs_sum"] > 0, agg["w_red_conc_sum"] / agg["w_obs_sum"], 0.0),
    )
    agg["ee_cnt_sum"] = np.where(is_overlap, agg["ee_cnt_max"], agg["ee_cnt_sum"])

    out = ann_stitched.merge(
        agg[
            [
                "canon_id",
                "Year",
                "true_ee_flag",
                "true_ee_conc",
                "unconc_flag",
                "has_conc_row_buggy",
                "ee_cnt_sum",
                "ee_red_all",
                "ee_red_conc",
            ]
        ],
        on=["canon_id", "Year"],
        how="left",
    )
    for col in ("true_ee_flag", "true_ee_conc", "unconc_flag", "has_conc_row_buggy"):
        out[col] = out[col].fillna(0).astype(int)
    for col in ("ee_cnt_sum", "ee_red_all", "ee_red_conc"):
        out[col] = out[col].fillna(0.0)
    out["ann_mean_ee_all"] = np.maximum(0.0, out["ann_mean"] - out["ee_red_all"])
    out["ann_mean_ee_conc"] = np.maximum(0.0, out["ann_mean"] - out["ee_red_conc"])
    return out


def compute_combined_site_appn_annual(
    daily: pd.DataFrame,
    ann: pd.DataFrame,
    canon_meta: pd.DataFrame,
    stitch_map: dict[str, str],
    universe: str,
    include_spm: bool = False,
) -> pd.DataFrame:
    """Implement EPA 40 CFR Part 50 Appendix N Section 3.0(d) Combined-Site Daily Record:
    at each regulatory site_id, prioritize the NAAQS Primary stitched monitor on each date
    and fill missing scheduled days with collocated regulatory monitors at that same site.
    Handles mid-3-year POC/instrument swaps (e.g., FRM POC 1 -> BAM/T640 POC 3) seamlessly.
    """
    if universe == "RAW":
        d = daily[
            daily["Event Type"].isin(["None", "Included"])
            & (daily["inst"] != "T640_RETRO")
            & (daily["Year"].between(2018, 2025))
        ].copy()
        inst_prio = {"T640_RAW": 1, "T640_FW": 2, "FRM": 3, "BAM": 3, "OTHER_FEM": 3}
    else:
        d = daily[
            daily["Event Type"].isin(["None", "Included"])
            & (daily["inst"] != "T640_RAW")
            & (daily["Year"].between(2018, 2025))
        ].copy()
        inst_prio = {"T640_FW": 1, "T640_RETRO": 2, "FRM": 3, "BAM": 3, "OTHER_FEM": 3}

    d["canon_id"] = d["mon_id"].map(lambda m: stitch_map.get(m, m))
    meta_sub = canon_meta[["canon_id", "is_appn_reg", "is_naaqs_primary", "monitor_type"]].copy()
    d = d.merge(meta_sub, on="canon_id", how="left")
    if include_spm:
        elig = (d["is_appn_reg"] == 1) | (d["monitor_type"] == "SPM")
    else:
        elig = d["is_appn_reg"] == 1
    d = d[elig].copy()

    # Priority within (site_id, Date Local): NAAQS Primary (0) > non-primary (1), then inst_prio
    d["p_rank"] = np.where(d["is_naaqs_primary"] == 1, 0, 1) * 10 + d["inst"].map(inst_prio).fillna(5)
    min_r = d.groupby(["site_id", "Date Local"])["p_rank"].transform("min")
    d = d[d["p_rank"] == min_r].copy()

    s_day = (
        d.groupby(["site_id", "county_fips", "state_fips", "Year", "Quarter", "Date Local"], as_index=False)
        .agg(pm25=("Arithmetic Mean", "mean"))
    )
    s_day["dt_ord"] = pd.to_datetime(s_day["Date Local"]).map(lambda x: x.toordinal())
    s_day = s_day.sort_values(["site_id", "Year", "dt_ord"])
    s_day["gap"] = s_day.groupby(["site_id", "Year"])["dt_ord"].diff()
    gap_med = s_day.groupby(["site_id", "Year"])["gap"].median().reset_index(name="med_gap")

    # Quarterly means and valid days per site
    q_agg = (
        s_day.groupby(["site_id", "county_fips", "state_fips", "Year", "Quarter"], as_index=False)
        .agg(q_mean=("pm25", "mean"), q_days=("pm25", "size"))
        .merge(gap_med, on=["site_id", "Year"], how="left")
    )

    def infer_cadence(mg: float) -> int:
        if pd.isna(mg) or mg <= 1.5:
            return 1
        if mg <= 4.0:
            return 3
        if mg <= 8.0:
            return 6
        return 12

    q_agg["cadence"] = [infer_cadence(g) for g in q_agg["med_gap"].to_numpy()]
    q_agg["q_cal_days"] = [
        _quarter_days(int(y), int(q))
        for y, q in zip(q_agg["Year"].to_numpy(), q_agg["Quarter"].to_numpy())
    ]
    q_agg["q_sched"] = np.maximum(1, np.round(q_agg["q_cal_days"] / q_agg["cadence"]).astype(int))
    q_agg["q_req_75"] = np.ceil(0.75 * q_agg["q_sched"] - 1e-9).astype(int)
    q_agg["q_complete"] = (q_agg["q_days"] >= q_agg["q_req_75"]).astype(int)

    # Attach site-year EE reductions (from fixed annual EE flags on regulatory monitors at site)
    a = ann.copy()
    a["canon_id"] = a["mon_id"].map(lambda m: stitch_map.get(m, m))
    a = a.merge(meta_sub, on="canon_id", how="left")
    a = a[(a["is_appn_reg"] == 1) | (include_spm & (a["monitor_type"] == "SPM"))].copy()
    inc = (
        a[a["Event Type"].isin(["No Events", "Events Included"])]
        .drop_duplicates(["mon_id", "Year"])
        [["mon_id", "site_id", "Year", "Arithmetic Mean", "Observation Count", "Exceptional Data Count"]]
        .rename(columns={"Arithmetic Mean": "mi", "Observation Count": "oi", "Exceptional Data Count": "ec"})
    )
    exc = (
        a[a["Event Type"] == "Events Excluded"]
        .drop_duplicates(["mon_id", "Year"])
        [["mon_id", "Year", "Arithmetic Mean", "Observation Count"]]
        .rename(columns={"Arithmetic Mean": "me", "Observation Count": "oe"})
    )
    con = (
        a[a["Event Type"] == "Concurred Events Excluded"]
        .drop_duplicates(["mon_id", "Year"])
        [["mon_id", "Year", "Arithmetic Mean", "Observation Count"]]
        .rename(columns={"Arithmetic Mean": "mc", "Observation Count": "oc"})
    )
    mg = inc.merge(exc, on=["mon_id", "Year"], how="left").merge(con, on=["mon_id", "Year"], how="left")
    tc = mg["mc"].notna() & ((mg["oc"].fillna(mg["oi"]) < mg["oi"]) | ((mg["mi"] - mg["mc"]).abs() > 1e-6))
    te = mg["me"].notna() & ((mg["oe"].fillna(mg["oi"]) < mg["oi"]) | ((mg["mi"] - mg["me"]).abs() > 1e-6))
    mg["red_all"] = np.where(
        te | tc | (mg["ec"].fillna(0) > 0),
        np.maximum(0.0, mg["mi"] - np.minimum(mg["me"].fillna(mg["mi"]), mg["mc"].fillna(mg["mi"]))),
        0.0,
    )
    mg["red_conc"] = np.where(tc, np.maximum(0.0, mg["mi"] - mg["mc"].fillna(mg["mi"])), 0.0)
    site_ee = (
        mg.groupby(["site_id", "Year"], as_index=False)
        .agg(ee_red_all=("red_all", "max"), ee_red_conc=("red_conc", "max"))
    )

    out = (
        q_agg.groupby(["site_id", "county_fips", "state_fips", "Year"], as_index=False)
        .agg(
            ann_mean=("q_mean", "mean"),
            n_qtrs=("Quarter", "nunique"),
            n_qtrs_complete=("q_complete", "sum"),
            total_days=("q_days", "sum"),
        )
        .merge(site_ee, on=["site_id", "Year"], how="left")
    )
    out["canon_id"] = out["site_id"]
    out["ee_red_all"] = out["ee_red_all"].fillna(0.0)
    out["ee_red_conc"] = out["ee_red_conc"].fillna(0.0)
    out["ann_mean_ee_all"] = np.maximum(0.0, out["ann_mean"] - out["ee_red_all"])
    out["ann_mean_ee_conc"] = np.maximum(0.0, out["ann_mean"] - out["ee_red_conc"])
    out["appn_year_complete"] = ((out["n_qtrs"] == 4) & (out["n_qtrs_complete"] == 4)).astype(int)
    out["appn_year_3of4"] = ((out["n_qtrs"] == 4) & (out["n_qtrs_complete"] >= 3)).astype(int)
    return out


def compute_county_dvs(
    df_my: pd.DataFrame,
    years: list[int],
    val_col: str,
    strict_3yr: bool = True,
    allow_11_of_12_qtrs: bool = False,
) -> pd.DataFrame:
    """Compute exact 40 CFR 50 App. N 3-year Design Values (rounded to 0.1 ug/m3, NA iff >= 9.1)."""
    sub = df_my[df_my["Year"].isin(years)].copy()
    if allow_11_of_12_qtrs:
        # 40 CFR 50 App. N: all 3 years have all 4 quarters present and >= 11/12 complete quarters
        sub = sub[sub["n_qtrs"] == 4].copy()
        md = (
            sub.groupby(["canon_id", "site_id", "county_fips", "state_fips"], as_index=False)
            .agg(dv=(val_col, "mean"), ny=("Year", "nunique"), tot_qc=("n_qtrs_complete", "sum"))
        )
        md = md[(md["ny"] == len(years)) & (md["tot_qc"] >= (4 * len(years) - 1))].copy()
    else:
        if strict_3yr:
            sub = sub[sub["appn_year_complete"] == 1].copy()
        md = (
            sub.groupby(["canon_id", "site_id", "county_fips", "state_fips"], as_index=False)
            .agg(dv=(val_col, "mean"), ny=("Year", "nunique"))
        )
        req_ny = len(years) if strict_3yr else max(2, len(years) - 1)
        md = md[md["ny"] >= req_ny].copy()
    # Appendix N standard rounding to 1 decimal place (half-up via small epsilon for float repr)
    md["dv_r"] = np.floor(md["dv"] * 10.0 + 0.5 + 1e-9) / 10.0
    cdv = (
        md.groupby(["county_fips", "state_fips"], as_index=False)
        .agg(cdv=("dv_r", "max"), cdv_exact=("dv", "max"), n_valid_mon=("canon_id", "nunique"))
    )
    return cdv


def parse_official_epa_dv_workbooks() -> dict[str, Any]:
    """Parse downloaded official EPA PM2.5 Design Value Excel workbooks for county-level reconciliation."""
    dv_dir = ENRICH_DIR / "epa_dv"
    if not dv_dir.exists():
        return {"error": "No epa_dv directory"}
    parsed: dict[str, Any] = {}
    for xlsx in sorted(dv_dir.glob("*.xlsx")):
        try:
            wb = openpyxl.load_workbook(xlsx, read_only=True, data_only=True)
            # Find the County-level Annual Design Value table (Table4a. County Status Ann / Annual)
            county_sheets = [
                s for s in wb.sheetnames
                if ("table4a" in s.lower().replace(" ", "") or "county status ann" in s.lower())
                and "24" not in s.lower()
            ]
            if not county_sheets:
                county_sheets = [
                    s for s in wb.sheetnames
                    if "county" in s.lower() and "24" not in s.lower()
                ]
            if not county_sheets:
                county_sheets = wb.sheetnames[:3]

            best_df = None
            best_sheet = None
            for sname in county_sheets:
                ws = wb[sname]
                rows = list(ws.iter_rows(values_only=True))
                # Locate header row containing 'State FIPS' or 'County FIPS' or 'FIPS'
                hdr_idx = None
                for idx, row in enumerate(rows[:20]):
                    joined = " ".join(str(c or "").lower() for c in row)
                    if ("county" in joined and "fips" in joined) or ("state" in joined and "county" in joined and "design value" in joined):
                        hdr_idx = idx
                        break
                if hdr_idx is None:
                    continue
                headers = [str(c or f"col_{i}").strip() for i, c in enumerate(rows[hdr_idx])]
                data_rows = rows[hdr_idx + 1 :]
                df = pd.DataFrame(data_rows, columns=headers)
                # Find FIPS and latest annual DV column
                fips_col = next((c for c in headers if "fips" in c.lower() and "county" in c.lower()), None)
                state_col = next((c for c in headers if "fips" in c.lower() and "state" in c.lower()), None)
                dv_cols = [
                    c for c in headers
                    if ("design value" in c.lower() or re.search(r"20\d\d\s*[-–]\s*20\d\d", c))
                    and "24-hr" not in c.lower()
                    and "24-hour" not in c.lower()
                    and "24hr" not in c.lower()
                    and "site" not in c.lower()
                    and "valid" not in c.lower()
                ]
                if not dv_cols:
                    dv_cols = [c for c in headers if "annual" in c.lower() and "dv" in c.lower()]
                if (fips_col or state_col) and dv_cols:
                    best_df = (df, fips_col, state_col, dv_cols)
                    best_sheet = sname
                    break
            wb.close()

            if best_df is None:
                parsed[xlsx.name] = {"sheets": wb.sheetnames, "status": "no_county_annual_table_matched"}
                continue

            df, fips_col, state_col, dv_cols = best_df
            # Construct 5-digit county_fips
            if fips_col is not None:
                raw_f = df[fips_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip()
                # Check if raw_f is already 5 digits or 3 digits needing state_col
                med_len = raw_f[raw_f.str.isdigit()].str.len().median() if raw_f.str.isdigit().any() else 0
                if med_len >= 4:
                    df["county_fips"] = raw_f.str.zfill(5)
                elif state_col is not None:
                    st_f = df[state_col].astype(str).str.replace(r"\.0$", "", regex=True).str.strip().str.zfill(2)
                    df["county_fips"] = st_f + raw_f.str.zfill(3)
                else:
                    df["county_fips"] = raw_f.str.zfill(5)
            else:
                parsed[xlsx.name] = {"sheet": best_sheet, "status": "missing_fips_col"}
                continue

            df["state_fips"] = df["county_fips"].str.slice(0, 2)
            df = df[df["state_fips"].isin(VALID_STATES) & df["county_fips"].str.match(r"^\d{5}$")].copy()

            # Take the rightmost (most recent) annual DV column
            target_dv_col = dv_cols[-1]
            df["official_dv"] = pd.to_numeric(df[target_dv_col], errors="coerce")
            valid_df = df.dropna(subset=["official_dv"]).drop_duplicates("county_fips")
            na_counties = sorted(valid_df[valid_df["official_dv"] >= 9.1]["county_fips"].tolist())
            parsed[xlsx.name] = {
                "sheet": best_sheet,
                "dv_col": target_dv_col,
                "all_dv_cols": dv_cols,
                "n_valid_counties": len(valid_df),
                "n_na_ge_9_1": len(na_counties),
                "na_counties": na_counties,
                "valid_counties": sorted(valid_df["county_fips"].tolist()),
            }
            print(
                f"  [EPA Official DV] {xlsx.name} ({best_sheet} | '{target_dv_col}'): "
                f"{len(valid_df)} valid counties, {len(na_counties)} >= 9.1 ug/m3",
                flush=True,
            )
        except (OSError, ValueError, KeyError) as exc:
            parsed[xlsx.name] = {"error": str(exc)}
    return parsed


def run_ej_audit(acct: pd.DataFrame) -> dict[str, Any]:
    """Environmental Justice & Demographic Distributional Audit using Census ACS 2023."""
    acs = pd.read_parquet(PROC_DIR / "acs5_2023_counties.parquet")
    df = acct.merge(acs.drop(columns=["state_fips"]), on="county_fips", how="left")
    df["region"] = df["state_fips"].map(REGION_MAP).fillna("OT")

    # Mutually exclusive classification based on 2021-2023 strict App. N DVs
    cond_flipped = (df["dv2123_raw"] >= 9.1) & (df["dv2123_aln"] <= 9.0)
    cond_still = df["dv2123_aln"] >= 9.1
    cond_clean = df["dv2123_raw"] <= 9.0
    df["ej_group"] = np.where(
        cond_flipped,
        "T640_Flipped",
        np.where(cond_still, "Still_Nonattainment", np.where(cond_clean, "Cleanly_Attaining", "Other")),
    )

    metrics = ["median_hh_income", "poverty_rate", "pct_black_nh", "pct_hispanic", "pct_nonwhite"]
    grp_stats: dict[str, Any] = {}
    for gname in ("T640_Flipped", "Still_Nonattainment", "Cleanly_Attaining"):
        sub = df[df["ej_group"] == gname]
        w = sub["acs_pop"].fillna(0.0).to_numpy()
        rec: dict[str, Any] = {
            "n_counties": len(sub),
            "pop_2024_millions": round(float(sub["pop_2024"].sum() / 1e6), 3),
            "acs_pop_millions": round(float(sub["acs_pop"].sum() / 1e6), 3),
            "region_counts": {k: int(v) for k, v in sub["region"].value_counts().to_dict().items()},
            "region_pop_share_pct": {
                k: round(float(100.0 * sub.loc[sub["region"] == k, "pop_2024"].sum() / max(sub["pop_2024"].sum(), 1.0)), 2)
                for k in ("MW", "SO", "NE", "WE")
            },
            "unweighted_means": {},
            "pop_weighted_means": {},
        }
        for m in metrics:
            v = sub[m].to_numpy(dtype=float)
            ok = np.isfinite(v)
            rec["unweighted_means"][m] = float(np.mean(v[ok])) if ok.any() else float("nan")
            okw = ok & (w > 0)
            rec["pop_weighted_means"][m] = (
                float(np.average(v[okw], weights=w[okw])) if okw.any() else float("nan")
            )
        grp_stats[gname] = rec

    # Formal Welch t-tests and Mann-Whitney U tests: T640_Flipped vs Still_Nonattainment & vs Cleanly_Attaining
    tests: dict[str, Any] = {}
    for comp in ("Still_Nonattainment", "Cleanly_Attaining"):
        t_comp: dict[str, Any] = {}
        g1 = df[df["ej_group"] == "T640_Flipped"]
        g2 = df[df["ej_group"] == comp]
        for m in metrics:
            a = g1[m].dropna().to_numpy(dtype=float)
            b = g2[m].dropna().to_numpy(dtype=float)
            t_val, p_t = stats.ttest_ind(a, b, equal_var=False)
            _u_val, p_u = stats.mannwhitneyu(a, b, alternative="two-sided")
            t_comp[m] = {
                "diff_flipped_minus_comp": float(np.mean(a) - np.mean(b)),
                "welch_t": float(t_val),
                "welch_p": float(p_t),
                "mwu_p": float(p_u),
            }
        # Fisher exact test for Midwest+South share: Flipped vs Still_Nonattainment
        mw_so_1 = int(g1["region"].isin(["MW", "SO"]).sum())
        mw_so_2 = int(g2["region"].isin(["MW", "SO"]).sum())
        tab = [[mw_so_1, len(g1) - mw_so_1], [mw_so_2, len(g2) - mw_so_2]]
        _, p_mwso = stats.fisher_exact(tab)
        t_comp["midwest_south_share"] = {
            "flipped_pct": float(100.0 * mw_so_1 / max(len(g1), 1)),
            "comp_pct": float(100.0 * mw_so_2 / max(len(g2), 1)),
            "fisher_p": float(p_mwso),
        }
        tests[f"Flipped_vs_{comp}"] = t_comp

    # Save enriched county panel for plotting
    df.to_parquet(PROC_DIR / "county_dv_ej_panel.parquet", index=False)
    return {"groups": grp_stats, "formal_tests": tests}


def run_exogenous_nulls_margins_acd(my_aln_reg: pd.DataFrame, cdv_1820: pd.DataFrame, cdv_2123: pd.DataFrame) -> dict[str, Any]:
    """Verify clean exogenous nulls for Margins A (FEM->FRM switching), C (monitor pruning),
    and D (gravimetric FRM PM2.5) using strictly exogenous DV_18_20 predicting 2024-2025 vs 2021-2023,
    plus expose the endogenous DV_21_23 RTM artifact via a DV_18_20 fake-rule RTM placebo.
    """
    out: dict[str, Any] = {}
    m = (
        my_aln_reg.merge(
            cdv_1820[["county_fips", "cdv_exact"]].rename(columns={"cdv_exact": "dv1820"}),
            on="county_fips",
            how="left",
        )
        .merge(
            cdv_2123[["county_fips", "cdv_exact"]].rename(columns={"cdv_exact": "dv2123"}),
            on="county_fips",
            how="left",
        )
    )
    m["st_yr"] = m["state_fips"] + "_" + m["Year"].astype(str)

    # --- MARGIN D: True Ambient PM2.5 (Gravimetric FRM monitors, 2021-2025, Post = 2024-2025) ---
    # Compute monitor-own pre-period means to separate true exogenous DV_18_20 from mechanical RTM
    frm_all = m[(m["dom_inst"] == "FRM") & (m["total_days"] >= 30)].copy()
    mon_dv_1820 = (
        frm_all[frm_all["Year"].isin([2018, 2019, 2020])]
        .groupby("canon_id", as_index=False)
        .agg(mon_dv1820=("ann_mean", "mean"), n1820=("Year", "nunique"))
    )
    mon_dv_1820 = mon_dv_1820[mon_dv_1820["n1820"] >= 2][["canon_id", "mon_dv1820"]]
    mon_dv_2123 = (
        frm_all[frm_all["Year"].isin([2021, 2022, 2023])]
        .groupby("canon_id", as_index=False)
        .agg(mon_dv2123=("ann_mean", "mean"), n2123=("Year", "nunique"))
    )
    mon_dv_2123 = mon_dv_2123[mon_dv_2123["n2123"] >= 2][["canon_id", "mon_dv2123"]]
    frm_all = frm_all.merge(mon_dv_1820, on="canon_id", how="left").merge(mon_dv_2123, on="canon_id", how="left")

    frm = frm_all[frm_all["Year"].between(2021, 2025)].copy()
    # 1. Strictly Exogenous DV_18_20 (county DV_18_20 & monitor-own DV_18_20 — zero temporal overlap!)
    f_ex = frm[frm["dv1820"].notna()].copy()
    f_ex["nb"] = ((f_ex["dv1820"] >= 8.5) & (f_ex["dv1820"] <= 11.5)).astype(int)
    f_ex["cl"] = (f_ex["dv1820"] < 8.0).astype(int)
    f_ex = f_ex[(f_ex["nb"] == 1) | (f_ex["cl"] == 1)].copy()
    f_ex["post"] = (f_ex["Year"] >= 2024).astype(int)
    f_ex["tp"] = f_ex["nb"] * f_ex["post"]
    out["margin_d_frm_exog_dv1820_county_cr1"] = ols_cr1(
        f_ex["ann_mean"].to_numpy(),
        f_ex[["tp"]].to_numpy(),
        f_ex["county_fips"].to_numpy(),
        [f_ex["canon_id"].to_numpy(), f_ex["st_yr"].to_numpy()],
        ["tp"],
        wcb_var_idx=0,
        wcb_B=999,
    )
    out["margin_d_frm_exog_dv1820_state_cr1"] = ols_cr1(
        f_ex["ann_mean"].to_numpy(),
        f_ex[["tp"]].to_numpy(),
        f_ex["state_fips"].to_numpy(),
        [f_ex["canon_id"].to_numpy(), f_ex["st_yr"].to_numpy()],
        ["tp"],
        wcb_var_idx=0,
        wcb_B=999,
    )
    # Monitor-own exogenous DV_18_20 predicting 2024-2025 vs 2021-2023 (zero overlap!)
    f_ex_m = frm[frm["mon_dv1820"].notna()].copy()
    f_ex_m["nb"] = ((f_ex_m["mon_dv1820"] >= 9.0) & (f_ex_m["mon_dv1820"] <= 12.0)).astype(int)
    f_ex_m["cl"] = (f_ex_m["mon_dv1820"] < 8.5).astype(int)
    f_ex_m = f_ex_m[(f_ex_m["nb"] == 1) | (f_ex_m["cl"] == 1)].copy()
    f_ex_m["tp"] = f_ex_m["nb"] * (f_ex_m["Year"] >= 2024).astype(int)
    out["margin_d_frm_exog_mon_dv1820"] = ols_cr1(
        f_ex_m["ann_mean"].to_numpy(),
        f_ex_m[["tp"]].to_numpy(),
        f_ex_m["county_fips"].to_numpy(),
        [f_ex_m["canon_id"].to_numpy(), f_ex_m["st_yr"].to_numpy()],
        ["tp"],
        wcb_var_idx=0,
        wcb_B=999,
    )

    # 2. Endogenous Monitor-Own DV_21_23 (overlaps pre-period 2021-2023 -> mechanical RTM!)
    f_end = frm[frm["mon_dv2123"].notna()].copy()
    f_end["nb"] = ((f_end["mon_dv2123"] >= 9.0) & (f_end["mon_dv2123"] <= 12.0)).astype(int)
    f_end["cl"] = (f_end["mon_dv2123"] < 8.5).astype(int)
    f_end = f_end[(f_end["nb"] == 1) | (f_end["cl"] == 1)].copy()
    f_end["tp"] = f_end["nb"] * (f_end["Year"] >= 2024).astype(int)
    out["margin_d_frm_endog_dv2123_rtm"] = ols_cr1(
        f_end["ann_mean"].to_numpy(),
        f_end[["tp"]].to_numpy(),
        f_end["county_fips"].to_numpy(),
        [f_end["canon_id"].to_numpy(), f_end["st_yr"].to_numpy()],
        ["tp"],
        wcb_var_idx=0,
        wcb_B=499,
    )

    # 3. Fake-Rule RTM Placebo: Monitor-Own DV_18_20 predicting 2021-2022 vs 2018-2020 (proves mechanical RTM!)
    frm_pl = frm_all[(frm_all["Year"].between(2018, 2022)) & frm_all["mon_dv1820"].notna()].copy()
    frm_pl["nb"] = ((frm_pl["mon_dv1820"] >= 9.0) & (frm_pl["mon_dv1820"] <= 12.0)).astype(int)
    frm_pl["cl"] = (frm_pl["mon_dv1820"] < 8.5).astype(int)
    frm_pl = frm_pl[(frm_pl["nb"] == 1) | (frm_pl["cl"] == 1)].copy()
    frm_pl["tp"] = frm_pl["nb"] * (frm_pl["Year"] >= 2021).astype(int)
    out["margin_d_frm_fake_rule_rtm_placebo"] = ols_cr1(
        frm_pl["ann_mean"].to_numpy(),
        frm_pl[["tp"]].to_numpy(),
        frm_pl["county_fips"].to_numpy(),
        [frm_pl["canon_id"].to_numpy(), frm_pl["st_yr"].to_numpy()],
        ["tp"],
        wcb_var_idx=0,
        wcb_B=499,
    )

    # --- MARGIN A: Deduplicated FEM -> FRM Longitudinal Switching (County-Year share_fem) ---
    # Report BOTH standardized [8.5, 11.5] vs <8.0 (matching Margin D & Pillar 3) AND [9.05, 12.0] vs <8.5
    cy_base = (
        m[m["Year"].between(2021, 2025) & m["dv1820"].notna()]
        .assign(is_fem=lambda d: (d["dom_inst"] != "FRM").astype(float))
        .groupby(["county_fips", "state_fips", "Year", "dv1820"], as_index=False)
        .agg(share_fem=("is_fem", "mean"), n_mon=("canon_id", "nunique"))
    )
    cy_base["st_yr"] = cy_base["state_fips"] + "_" + cy_base["Year"].astype(str)
    cy_base["log_n_mon"] = np.log(cy_base["n_mon"].to_numpy(dtype=float))

    for tag, lo, hi, cl_hi in [
        ("exog_dv1820_85_115", 8.5, 11.5, 8.0),
        ("exog_dv1820", 9.05, 12.0, 8.5),
    ]:
        cy_a = cy_base.copy()
        cy_a["nb"] = ((cy_a["dv1820"] >= lo) & (cy_a["dv1820"] <= hi)).astype(int)
        cy_a["cl"] = (cy_a["dv1820"] < cl_hi).astype(int)
        cy_a = cy_a[(cy_a["nb"] == 1) | (cy_a["cl"] == 1)].copy()
        cy_a["tp"] = cy_a["nb"] * (cy_a["Year"] >= 2024).astype(int)
        out[f"margin_a_share_fem_{tag}"] = ols_cr1(
            cy_a["share_fem"].to_numpy(),
            cy_a[["tp"]].to_numpy(),
            cy_a["county_fips"].to_numpy(),
            [cy_a["county_fips"].to_numpy(), cy_a["st_yr"].to_numpy()],
            ["tp"],
            wcb_var_idx=0,
            wcb_B=999,
        )
        out[f"margin_c_log_monitors_{tag}"] = ols_cr1(
            cy_a["log_n_mon"].to_numpy(),
            cy_a[["tp"]].to_numpy(),
            cy_a["county_fips"].to_numpy(),
            [cy_a["county_fips"].to_numpy(), cy_a["st_yr"].to_numpy()],
            ["tp"],
            wcb_var_idx=0,
            wcb_B=999,
        )

    # Monitor-level survival: among stitched regulatory monitors active in 2021-2023, still active in 2024-2025?
    m_pre_base = m[m["Year"].isin([2021, 2022, 2023]) & m["dv1820"].notna()][
        ["canon_id", "county_fips", "state_fips", "dv1820"]
    ].drop_duplicates("canon_id").copy()
    active_2425 = set(m[m["Year"].isin([2024, 2025])]["canon_id"])
    m_pre_base["survived_2425"] = m_pre_base["canon_id"].isin(active_2425).astype(float)
    for tag, lo, hi, cl_hi in [
        ("exog_dv1820_85_115", 8.5, 11.5, 8.0),
        ("exog_dv1820", 9.05, 12.0, 8.5),
    ]:
        m_pre = m_pre_base.copy()
        m_pre["nb"] = ((m_pre["dv1820"] >= lo) & (m_pre["dv1820"] <= hi)).astype(int)
        m_pre["cl"] = (m_pre["dv1820"] < cl_hi).astype(int)
        m_pre = m_pre[(m_pre["nb"] == 1) | (m_pre["cl"] == 1)].copy()
        out[f"margin_c_monitor_survival_{tag}"] = ols_cr1(
            m_pre["survived_2425"].to_numpy(),
            m_pre[["nb"]].to_numpy(),
            m_pre["county_fips"].to_numpy(),
            [m_pre["state_fips"].to_numpy()],
            ["nb"],
            wcb_var_idx=0,
            wcb_B=999,
        )
    return out


def main() -> int:
    print("=== STEP 01 (PILLAR 1): EXACT STITCHED APPENDIX N PANEL, EPA DV RECONCILIATION & EJ AUDIT ===", flush=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)
    RES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Load metadata, population, daily (2018-2025), and annual (2018-2025)
    mons = load_monitor_metadata()
    pop_raw = pd.read_csv(
        WAVE6_RAW_DIR / "co-est2024-alldata.csv",
        encoding="latin1",
        dtype={"STATE": str, "COUNTY": str},
    )
    pop_raw = pop_raw[pop_raw["SUMLEV"] == 50].copy()
    pop_raw["county_fips"] = pop_raw["STATE"].str.zfill(2) + pop_raw["COUNTY"].str.zfill(3)
    pop_df = pop_raw[["county_fips", "POPESTIMATE2024"]].rename(
        columns={"POPESTIMATE2024": "pop_2024"}
    )

    print("  Loading daily 88101 (2018-2025) & annual_conc_by_monitor (2018-2025)...", flush=True)
    daily = load_daily_88101(list(range(2018, 2026)))
    ann = load_annual_88101(list(range(2018, 2026)))

    # 2. Deterministic T640 POC stitching (persist canonical stitch_map for Step 03 consistency)
    stitch_map, stitch_audit = build_t640_poc_stitch_map(daily)
    save_json_lf(PROC_DIR / "t640_stitch_map.json", stitch_map)
    print(f"  T640 Stitch Audit: {stitch_audit}", flush=True)

    # Map monitor metadata onto canonical IDs (inheriting original POC metadata when 736/738 maps to POC-20)
    mons["canon_id"] = mons["mon_id"].map(lambda x: stitch_map.get(x, x))
    canon_meta = (
        mons.sort_values(["canon_id", "poc_int"])
        .groupby("canon_id", as_index=False)
        .agg(
            monitor_type=("monitor_type", "first"),
            mon_obj=("mon_obj", "first"),
            is_appn_reg=("is_appn_reg", "max"),
            is_slams_strict=("is_slams_strict", "max"),
            is_naaqs_primary=("is_naaqs_primary", "max"),
            first_year=("first_year", "min"),
            lat=("lat", "first"),
            lon=("lon", "first"),
        )
    )

    # 3. Compute exact stitched Appendix N annual panels for RAW and ALN
    print("  Computing stitched 40 CFR 50 App. N quarterly-weighted annual panels (RAW & ALN)...", flush=True)
    my_raw_all = compute_stitched_appn_annual(daily, ann, stitch_map, "RAW")
    my_aln_all = compute_stitched_appn_annual(daily, ann, stitch_map, "ALN")
    my_aln_all = attach_fixed_ee_flags(my_aln_all, ann, stitch_map)
    my_raw_all = attach_fixed_ee_flags(my_raw_all, ann, stitch_map)

    my_raw_all = my_raw_all.merge(canon_meta, on="canon_id", how="left")
    my_aln_all = my_aln_all.merge(canon_meta, on="canon_id", how="left")
    for df in (my_raw_all, my_aln_all):
        df["is_appn_reg"] = df["is_appn_reg"].fillna(0).astype(int)
        df["is_slams_strict"] = df["is_slams_strict"].fillna(0).astype(int)
        df["is_naaqs_primary"] = df["is_naaqs_primary"].fillna(0).astype(int)

    # Save full stitched monitor-year parquet (for Pillar 3 & tests!)
    my_aln_all.to_parquet(PROC_DIR / "stitched_monitor_year_aln_2018_2025.parquet", index=False)
    my_raw_all.to_parquet(PROC_DIR / "stitched_monitor_year_raw_2018_2025.parquet", index=False)

    # Audit excluded non-regulatory monitors
    reg_audit = {
        "total_canon_monitors_aln": int(my_aln_all["canon_id"].nunique()),
        "appn_regulatory_monitors_aln": int(my_aln_all[my_aln_all["is_appn_reg"] == 1]["canon_id"].nunique()),
        "slams_only_monitors_aln": int(my_aln_all[my_aln_all["is_slams_strict"] == 1]["canon_id"].nunique()),
        "excluded_non_reg_monitors": int(my_aln_all[my_aln_all["is_appn_reg"] == 0]["canon_id"].nunique()),
        "monitor_type_breakdown_canon": {
            str(k): int(v)
            for k, v in my_aln_all.drop_duplicates("canon_id")["monitor_type"].fillna("MISSING").value_counts().to_dict().items()
        },
        "epa_concurrence_bug_audit_2018_2025": {
            "buggy_concurrence_row_count": int(my_aln_all["has_conc_row_buggy"].sum()),
            "true_concurred_count": int(my_aln_all["true_ee_conc"].sum()),
            "false_positive_share_pct": round(
                float(
                    100.0
                    * (1.0 - my_aln_all["true_ee_conc"].sum() / max(my_aln_all["has_conc_row_buggy"].sum(), 1))
                ),
                2,
            ),
            "true_ee_flag_count": int(my_aln_all["true_ee_flag"].sum()),
            "unconc_flag_count": int(my_aln_all["unconc_flag"].sum()),
        },
    }
    print(f"  Regulatory & Concurrence Audit: {reg_audit['epa_concurrence_bug_audit_2018_2025']}", flush=True)

    # 4. Strict App. N Design Value Accounting:
    #    (A) EPA 40 CFR 50 App. N Sec 3.0(d) Combined-Site Regulatory (11/12 & 12/12 qtrs) -> headline!
    #    (B) Single-Monitor Stitched Regulatory (12/12 qtrs), SLAMS-Only, NAAQS-Primary-Only
    print("  Computing 40 CFR 50 App. N Sec 3.0(d) Combined-Site regulatory records (RAW & ALN)...", flush=True)
    cs_raw_reg = compute_combined_site_appn_annual(daily, ann, canon_meta, stitch_map, "RAW", include_spm=False)
    cs_aln_reg = compute_combined_site_appn_annual(daily, ann, canon_meta, stitch_map, "ALN", include_spm=False)
    cs_raw_plus_spm = compute_combined_site_appn_annual(daily, ann, canon_meta, stitch_map, "RAW", include_spm=True)
    cs_aln_plus_spm = compute_combined_site_appn_annual(daily, ann, canon_meta, stitch_map, "ALN", include_spm=True)

    def run_accounting_universe(
        df_r: pd.DataFrame,
        df_a: pd.DataFrame,
        label: str,
        allow_11_of_12: bool = False,
    ) -> tuple[dict[str, Any], pd.DataFrame]:
        kw = {"strict_3yr": True, "allow_11_of_12_qtrs": allow_11_of_12}
        c1820 = compute_county_dvs(df_a, [2018, 2019, 2020], "ann_mean", **kw).rename(
            columns={"cdv": "dv1820", "cdv_exact": "ex1820"}
        )
        c1921 = compute_county_dvs(df_a, [2019, 2020, 2021], "ann_mean", **kw).rename(
            columns={"cdv": "dv1921"}
        )
        c2022 = compute_county_dvs(df_a, [2020, 2021, 2022], "ann_mean", **kw).rename(
            columns={"cdv": "dv2022"}
        )
        c2123_raw = compute_county_dvs(df_r, [2021, 2022, 2023], "ann_mean", **kw).rename(
            columns={"cdv": "dv2123_raw", "cdv_exact": "ex2123_raw"}
        )
        c2123_aln = compute_county_dvs(df_a, [2021, 2022, 2023], "ann_mean", **kw).rename(
            columns={"cdv": "dv2123_aln", "cdv_exact": "ex2123_aln"}
        )
        c2123_ee_all = compute_county_dvs(df_a, [2021, 2022, 2023], "ann_mean_ee_all", **kw).rename(
            columns={"cdv": "dv2123_ee_all"}
        )
        c2123_ee_conc = compute_county_dvs(df_a, [2021, 2022, 2023], "ann_mean_ee_conc", **kw).rename(
            columns={"cdv": "dv2123_ee_conc"}
        )
        c2224_aln = compute_county_dvs(df_a, [2022, 2023, 2024], "ann_mean", **kw).rename(
            columns={"cdv": "dv2224_aln"}
        )
        c2224_ee_conc = compute_county_dvs(df_a, [2022, 2023, 2024], "ann_mean_ee_conc", **kw).rename(
            columns={"cdv": "dv2224_ee_conc"}
        )
        c2325_aln = compute_county_dvs(df_a, [2023, 2024, 2025], "ann_mean", **kw).rename(
            columns={"cdv": "dv2325_aln", "cdv_exact": "ex2325_aln"}
        )
        c2325_ee_all = compute_county_dvs(df_a, [2023, 2024, 2025], "ann_mean_ee_all", **kw).rename(
            columns={"cdv": "dv2325_ee_all"}
        )
        c2325_ee_conc = compute_county_dvs(df_a, [2023, 2024, 2025], "ann_mean_ee_conc", **kw).rename(
            columns={"cdv": "dv2325_ee_conc"}
        )

        # Matched panel across 2021-2023 RAW & ALN (and outer-attach 2023-2025 + matched 2021-2025)
        m2123 = (
            c2123_raw[["county_fips", "state_fips", "dv2123_raw", "ex2123_raw"]]
            .merge(c2123_aln[["county_fips", "dv2123_aln", "ex2123_aln"]], on="county_fips", how="inner")
            .merge(c2123_ee_all[["county_fips", "dv2123_ee_all"]], on="county_fips", how="inner")
            .merge(c2123_ee_conc[["county_fips", "dv2123_ee_conc"]], on="county_fips", how="inner")
            .merge(pop_df, on="county_fips", how="left")
        )
        m_full = (
            m2123.merge(c2325_aln[["county_fips", "dv2325_aln", "ex2325_aln"]], on="county_fips", how="inner")
            .merge(c2325_ee_all[["county_fips", "dv2325_ee_all"]], on="county_fips", how="inner")
            .merge(c2325_ee_conc[["county_fips", "dv2325_ee_conc"]], on="county_fips", how="inner")
            .merge(c1820[["county_fips", "dv1820", "ex1820"]], on="county_fips", how="left")
            .merge(c2224_aln[["county_fips", "dv2224_aln"]], on="county_fips", how="left")
        )

        def cp(df_x: pd.DataFrame, mask: pd.Series) -> dict[str, Any]:
            return {
                "counties": int(mask.sum()),
                "pop_millions": round(float(df_x.loc[mask, "pop_2024"].sum() / 1e6), 2),
            }

        summary = {
            "label": label,
            "allow_11_of_12_qtrs": allow_11_of_12,
            "n_counties_valid_2123_raw": len(c2123_raw),
            "n_counties_valid_2123_aln": len(c2123_aln),
            "n_counties_valid_2224_aln": len(c2224_aln),
            "n_counties_valid_2325_aln": len(c2325_aln),
            "n_counties_matched_2123": len(m2123),
            "n_counties_matched_2123_and_2325": len(m_full),
            "total_pop_matched_2123_millions": round(float(m2123["pop_2024"].sum() / 1e6), 2),
            "total_pop_matched_2125_millions": round(float(m_full["pop_2024"].sum() / 1e6), 2),
            "all_valid_unmatched": {
                "na_1921_aln": int((c1921["dv1921"] >= 9.1).sum()),
                "na_2022_aln": int((c2022["dv2022"] >= 9.1).sum()),
                "na_2123_raw": int((c2123_raw["dv2123_raw"] >= 9.1).sum()),
                "na_2123_aln": int((c2123_aln["dv2123_aln"] >= 9.1).sum()),
                "na_2123_aln_ee_conc": int((c2123_ee_conc["dv2123_ee_conc"] >= 9.1).sum()),
                "na_2123_aln_ee_all": int((c2123_ee_all["dv2123_ee_all"] >= 9.1).sum()),
                "na_2224_aln": int((c2224_aln["dv2224_aln"] >= 9.1).sum()),
                "na_2224_aln_ee_conc": int((c2224_ee_conc["dv2224_ee_conc"] >= 9.1).sum()),
                "na_2325_aln": int((c2325_aln["dv2325_aln"] >= 9.1).sum()),
                "na_2325_aln_ee_conc": int((c2325_ee_conc["dv2325_ee_conc"] >= 9.1).sum()),
                "na_2325_aln_ee_all": int((c2325_ee_all["dv2325_ee_all"] >= 9.1).sum()),
            },
            "matched_2123_waterfall": {
                "raw_2123": cp(m2123, m2123["dv2123_raw"] >= 9.1),
                "aln_2123": cp(m2123, m2123["dv2123_aln"] >= 9.1),
                "aln_ee_conc_2123": cp(m2123, m2123["dv2123_ee_conc"] >= 9.1),
                "aln_ee_all_2123": cp(m2123, m2123["dv2123_ee_all"] >= 9.1),
                "flip_t640_alone": cp(m2123, (m2123["dv2123_raw"] >= 9.1) & (m2123["dv2123_aln"] <= 9.0)),
                "flip_ee_conc_alone": cp(m2123, (m2123["dv2123_aln"] >= 9.1) & (m2123["dv2123_ee_conc"] <= 9.0)),
                "flip_ee_all_alone": cp(m2123, (m2123["dv2123_aln"] >= 9.1) & (m2123["dv2123_ee_all"] <= 9.0)),
                "flip_t640_plus_ee_all": cp(m2123, (m2123["dv2123_raw"] >= 9.1) & (m2123["dv2123_ee_all"] <= 9.0)),
            },
            "matched_2123_to_2325_waterfall": {
                "raw_2123": cp(m_full, m_full["dv2123_raw"] >= 9.1),
                "aln_2123": cp(m_full, m_full["dv2123_aln"] >= 9.1),
                "aln_ee_conc_2123": cp(m_full, m_full["dv2123_ee_conc"] >= 9.1),
                "aln_ee_all_2123": cp(m_full, m_full["dv2123_ee_all"] >= 9.1),
                "aln_2325": cp(m_full, m_full["dv2325_aln"] >= 9.1),
                "aln_ee_conc_2325": cp(m_full, m_full["dv2325_ee_conc"] >= 9.1),
                "aln_ee_all_2325": cp(m_full, m_full["dv2325_ee_all"] >= 9.1),
                "flip_t640_alone_2123": cp(m_full, (m_full["dv2123_raw"] >= 9.1) & (m_full["dv2123_aln"] <= 9.0)),
                "flip_ee_conc_alone_2123": cp(m_full, (m_full["dv2123_aln"] >= 9.1) & (m_full["dv2123_ee_conc"] <= 9.0)),
                "flip_ee_all_alone_2123": cp(m_full, (m_full["dv2123_aln"] >= 9.1) & (m_full["dv2123_ee_all"] <= 9.0)),
                "flip_ee_all_alone_2325": cp(m_full, (m_full["dv2325_aln"] >= 9.1) & (m_full["dv2325_ee_all"] <= 9.0)),
            },
            "na_counties_1921_aln_list": sorted(c1921[c1921["dv1921"] >= 9.1]["county_fips"].tolist()),
            "na_counties_2022_aln_list": sorted(c2022[c2022["dv2022"] >= 9.1]["county_fips"].tolist()),
            "na_counties_2123_aln_list": sorted(c2123_aln[c2123_aln["dv2123_aln"] >= 9.1]["county_fips"].tolist()),
            "na_counties_2123_ee_conc_list": sorted(c2123_ee_conc[c2123_ee_conc["dv2123_ee_conc"] >= 9.1]["county_fips"].tolist()),
            "na_counties_2224_aln_list": sorted(c2224_aln[c2224_aln["dv2224_aln"] >= 9.1]["county_fips"].tolist()),
            "na_counties_2224_ee_conc_list": sorted(c2224_ee_conc[c2224_ee_conc["dv2224_ee_conc"] >= 9.1]["county_fips"].tolist()),
            "na_counties_2325_aln_list": sorted(c2325_aln[c2325_aln["dv2325_aln"] >= 9.1]["county_fips"].tolist()),
            "na_counties_2325_ee_conc_list": sorted(c2325_ee_conc[c2325_ee_conc["dv2325_ee_conc"] >= 9.1]["county_fips"].tolist()),
        }
        print(f"\n  [{label}] Matched 2021-2023 (N={len(m2123)}) & Matched 2021-2025 (N={len(m_full)}):", flush=True)
        w = summary["matched_2123_waterfall"]
        print(
            f"    2021-23 RAW={w['raw_2123']} -> ALN={w['aln_2123']} (T640 flip={w['flip_t640_alone']}) "
            f"-> ALN+EE_conc={w['aln_ee_conc_2123']} -> ALN+EE_all={w['aln_ee_all_2123']}",
            flush=True,
        )
        w2 = summary["matched_2123_to_2325_waterfall"]
        print(
            f"    Matched 21-25: RAW21-23={w2['raw_2123']} -> ALN21-23={w2['aln_2123']} "
            f"-> ALN23-25={w2['aln_2325']} -> ALN23-25+EE_all={w2['aln_ee_all_2325']}",
            flush=True,
        )
        return summary, m2123

    reg_raw = my_raw_all[my_raw_all["is_appn_reg"] == 1].copy()
    reg_aln = my_aln_all[my_aln_all["is_appn_reg"] == 1].copy()
    slams_raw = my_raw_all[my_raw_all["is_slams_strict"] == 1].copy()
    slams_aln = my_aln_all[my_aln_all["is_slams_strict"] == 1].copy()
    prim_raw = my_raw_all[(my_raw_all["is_appn_reg"] == 1) & (my_raw_all["is_naaqs_primary"] == 1)].copy()
    prim_aln = my_aln_all[(my_aln_all["is_appn_reg"] == 1) & (my_aln_all["is_naaqs_primary"] == 1)].copy()

    acct_cs_11, m2123_cs_11 = run_accounting_universe(cs_raw_reg, cs_aln_reg, "COMBINED_SITE_REG_APPN_11OF12", allow_11_of_12=True)
    acct_cs_12, _ = run_accounting_universe(cs_raw_reg, cs_aln_reg, "COMBINED_SITE_REG_APPN_12OF12", allow_11_of_12=False)
    acct_cs_spm, _ = run_accounting_universe(cs_raw_plus_spm, cs_aln_plus_spm, "COMBINED_SITE_REG_PLUS_SPM_11OF12", allow_11_of_12=True)
    acct_reg, _ = run_accounting_universe(reg_raw, reg_aln, "SINGLE_MONITOR_REG_APPN_12OF12", allow_11_of_12=False)
    acct_slams, _ = run_accounting_universe(slams_raw, slams_aln, "SINGLE_MONITOR_SLAMS_ONLY_12OF12", allow_11_of_12=False)
    acct_prim, _ = run_accounting_universe(prim_raw, prim_aln, "NAAQS_PRIMARY_ONLY_12OF12", allow_11_of_12=False)

    # 5. Official EPA DV Workbook Reconciliation (reconcile against Combined-Site 11/12 & Combined-Site+SPM!)
    print("\n  Reconciling against official EPA PM2.5 Design Value Excel workbooks...", flush=True)
    epa_official = parse_official_epa_dv_workbooks()
    reconciliation: dict[str, Any] = {}
    period_map = [
        ("2023_2025", "2023-2025", "na_counties_2325_aln_list", "na_counties_2325_ee_conc_list"),
        ("2022_2024", "2022-2024", "na_counties_2224_aln_list", "na_counties_2224_ee_conc_list"),
        ("2021_2023", "2021-2023", "na_counties_2123_aln_list", "na_counties_2123_ee_conc_list"),
        ("2020_2022", "2020-2022", "na_counties_2022_aln_list", "na_counties_2022_aln_list"),
        ("2019_2021", "2019-2021", "na_counties_1921_aln_list", "na_counties_1921_aln_list"),
    ]
    for fname, info in epa_official.items():
        if "na_counties" not in info:
            reconciliation[fname] = info
            continue
        off_set = set(info["na_counties"])
        ref_lbl, k_aln, k_conc = "other", "na_counties_2123_aln_list", "na_counties_2123_ee_conc_list"
        for tag, plbl, ka, kc in period_map:
            if tag in fname.lower():
                ref_lbl, k_aln, k_conc = plbl, ka, kc
                break
        ref_cs = set(acct_cs_11[k_aln])
        ref_cs_conc = set(acct_cs_11[k_conc])
        ref_cs_spm = set(acct_cs_spm[k_aln])
        ref_sm = set(acct_reg[k_aln])
        reconciliation[fname] = {
            "period": ref_lbl,
            "sheet": info["sheet"],
            "dv_col": info["dv_col"],
            "epa_valid_counties": info["n_valid_counties"],
            "epa_na_counties": info["n_na_ge_9_1"],
            "combined_site_reg_na_incl": len(ref_cs),
            "combined_site_reg_na_ee_conc": len(ref_cs_conc),
            "combined_site_plus_spm_na_incl": len(ref_cs_spm),
            "single_monitor_12of12_na_incl": len(ref_sm),
            "overlap_epa_with_cs_reg_incl": len(off_set & ref_cs),
            "overlap_epa_with_cs_reg_ee_conc": len(off_set & ref_cs_conc),
            "overlap_epa_with_cs_spm_incl": len(off_set & ref_cs_spm),
            "in_epa_not_cs_reg_incl": len(off_set - ref_cs),
            "in_cs_reg_incl_not_epa": len(ref_cs - off_set),
        }
        print(f"    Reconcile {fname} [{ref_lbl}]: EPA={info['n_na_ge_9_1']}/{info['n_valid_counties']} | CS_Reg_Incl={len(ref_cs)} (ov={len(off_set & ref_cs)}) | CS_Reg_Conc={len(ref_cs_conc)} (ov={len(off_set & ref_cs_conc)}) | CS+SPM={len(ref_cs_spm)} (ov={len(off_set & ref_cs_spm)})", flush=True)

    # Strip long county lists before saving clean JSON receipt
    for d_acct in (acct_cs_11, acct_cs_12, acct_cs_spm, acct_reg, acct_slams, acct_prim):
        for k in list(d_acct.keys()):
            if k.endswith("_list"):
                del d_acct[k]

    # 6. Environmental Justice & Demographic Audit (Primary: Combined-Site Regulatory 11/12 App. N!)
    print("\n  Running Census SAIPE 2023 + PEP 2024 Environmental Justice & Regional Audit...", flush=True)
    ej_audit = run_ej_audit(m2123_cs_11)
    for gname, ginfo in ej_audit["groups"].items():
        print(
            f"    EJ [{gname:20s}]: N={ginfo['n_counties']:3d}, pop={ginfo['pop_2024_millions']:6.2f}M, "
            f"income=${ginfo['unweighted_means']['median_hh_income']:,.0f} (pw=${ginfo['pop_weighted_means']['median_hh_income']:,.0f}), "
            f"pov={ginfo['unweighted_means']['poverty_rate']:.1f}%, nonwhite={ginfo['unweighted_means']['pct_nonwhite']:.1f}% (pw={ginfo['pop_weighted_means']['pct_nonwhite']:.1f}%), "
            f"regions={ginfo['region_counts']}",
            flush=True,
        )

    # 7. Exogenous Null Verification (Margins A, C, D)
    print("\n  Running Exogenous Null Verification (Margins A, C, D on DV_18_20)...", flush=True)
    cdv_1820 = compute_county_dvs(cs_aln_reg, [2018, 2019, 2020], "ann_mean", strict_3yr=True, allow_11_of_12_qtrs=True)
    cdv_2123 = compute_county_dvs(cs_aln_reg, [2021, 2022, 2023], "ann_mean", strict_3yr=True, allow_11_of_12_qtrs=True)
    # Also save county exogenous DVs for Pillar 3
    cdv_1820_2yr = compute_county_dvs(reg_aln, [2018, 2019, 2020], "ann_mean", strict_3yr=False)
    cdv_1820_raw = compute_county_dvs(reg_raw, [2018, 2019, 2020], "ann_mean", strict_3yr=False)
    cdv_2123_raw = compute_county_dvs(cs_raw_reg, [2021, 2022, 2023], "ann_mean", strict_3yr=True, allow_11_of_12_qtrs=True)
    cdv_out = (
        cdv_1820_2yr[["county_fips", "state_fips", "cdv", "cdv_exact"]]
        .rename(columns={"cdv": "dv1820_aln_r", "cdv_exact": "dv1820_aln"})
        .merge(
            cdv_1820[["county_fips", "cdv", "cdv_exact"]].rename(
                columns={"cdv": "dv1820_strict_r", "cdv_exact": "dv1820_strict"}
            ),
            on="county_fips",
            how="outer",
        )
        .merge(
            cdv_1820_raw[["county_fips", "cdv", "cdv_exact"]].rename(
                columns={"cdv": "dv1820_raw_r", "cdv_exact": "dv1820_raw"}
            ),
            on="county_fips",
            how="outer",
        )
        .merge(
            cdv_2123[["county_fips", "cdv", "cdv_exact"]].rename(
                columns={"cdv": "dv2123_aln_r", "cdv_exact": "dv2123_aln"}
            ),
            on="county_fips",
            how="outer",
        )
        .merge(
            cdv_2123_raw[["county_fips", "cdv", "cdv_exact"]].rename(
                columns={"cdv": "dv2123_raw_r", "cdv_exact": "dv2123_raw"}
            ),
            on="county_fips",
            how="outer",
        )
    )
    cdv_out.to_parquet(PROC_DIR / "county_dvs_stitched.parquet", index=False)

    nulls = run_exogenous_nulls_margins_acd(reg_aln, cdv_1820, cdv_2123)
    for k, v in nulls.items():
        c = next(iter(v.get("coefs", {}).values())) if v.get("coefs") else {}
        w = v.get("wcb", {}).get("p_wcb", math.nan)
        print(
            f"    {k:38s}: beta={c.get('beta', math.nan):+.4f}, se={c.get('se_cr1', math.nan):.4f}, "
            f"t={c.get('t_cr1', math.nan):+.2f}, p={c.get('p_cr1', math.nan):.4f}, p_WCB={w:.3f}",
            flush=True,
        )

    receipt = {
        "stitch_audit": stitch_audit,
        "regulatory_and_concurrence_audit": reg_audit,
        "accounting": {
            "combined_site_reg_appn_11of12": acct_cs_11,
            "combined_site_reg_appn_12of12": acct_cs_12,
            "combined_site_reg_plus_spm_11of12": acct_cs_spm,
            "single_monitor_reg_appn_12of12": acct_reg,
            "single_monitor_slams_only_12of12": acct_slams,
            "naaqs_primary_only_12of12": acct_prim,
        },
        "epa_official_dv_reconciliation": reconciliation,
        "ej_audit_acs2023": ej_audit,
        "exogenous_nulls_margins_acd": nulls,
    }
    sha = save_json_lf(RES_DIR / "01_appn_audit.json", receipt)
    print(f"\n[DONE STEP 01] Saved results/01_appn_audit.json (SHA-256 LF: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
