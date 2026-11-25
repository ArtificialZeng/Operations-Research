"""Step 3: Build fully harmonized campaign panel (2015-2026), Make-Model-MY panel,
and balanced [-12m, +12m] NHTSA Consumer Complaint Event-Study panel (2021-2025 campaigns).
"""
from __future__ import annotations

import json
import re
import time
import zipfile
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
RAW_DIR = BASE_DIR / "data_raw"
PROC_DIR = BASE_DIR / "data_processed"
RES_DIR = BASE_DIR / "results"
PROC_DIR.mkdir(parents=True, exist_ok=True)
RES_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_DATE = pd.Timestamp("2026-11-25")

RCL_COLS = [
    "RECORD_ID", "CAMPNO", "MAKETXT", "MODELTXT", "YEARTXT", "MFGCAMPNO",
    "COMPNAME", "MFGNAME", "BGMAN", "ENDMAN", "RCLTYPECD", "POTAFF",
    "ODATE", "INFLUENCED_BY", "MFGTXT", "RCDATE", "DATEA", "RPNO", "FMVSS",
    "DESC_DEFECT", "CONEQUENCE_DEFECT", "CORRECTIVE_ACTION", "NOTES",
    "RCL_CMPT_ID", "MFR_COMP_NAME", "MFR_COMP_DESC", "MFR_COMP_PTNO",
    "DO_NOT_DRIVE", "PARK_OUTSIDE",
]

# Explicit corporate rename consolidation (preserving legally separate truck/car entities)
EXPLICIT_OEM_MAP = {
    "TESLA MOTORS, INC.": "Tesla, Inc.",
    "KIA MOTORS AMERICA": "Kia America, Inc.",
    "LUCID MOTORS, INC.": "Lucid USA, Inc.",
    "VOLVO CARS OF N.A., LLC": "Volvo Car USA, LLC",
    "CHRYSLER (FCA US, LLC) (STELLANTIS)": "Chrysler (FCA US, LLC)",
    "MERCEDES-BENZ USA, LLC - DBA SPRINTER": "Mercedes-Benz USA, LLC",
}

OTA_REMEDY_PAT = re.compile(
    r"\bover[- ]the[- ]air\b|\bota\s+(?:software\s+)?(?:update|remedy|release|fix|patch|download)"
    r"|\bvia\s+ota\b|\bthrough\s+ota\b|\bwireless(?:ly)?\s+(?:update|push|download|install|remedy)"
    r"|\bremote(?:ly)?\s+(?:update|push|download|install)",
    re.IGNORECASE,
)
OTA_NEG_PAT = re.compile(
    r"(?:not\s+(?:eligible|capable|equipped|able)\s+(?:for|to\s+receive)\s+(?:an?\s+)?(?:over[- ]the[- ]air|ota))"
    r"|(?:cannot\s+be\s+(?:updated|remedied|fixed|completed)\s+(?:over[- ]the[- ]air|via\s+ota))"
    r"|(?:unable\s+to\s+(?:receive|complete)\s+(?:an?\s+)?(?:over[- ]the[- ]air|ota))",
    re.IGNORECASE,
)
DEALER_OR_HW_PAT = re.compile(
    r"\bdealer(?:s|ship)?\b|\bservice\s+center\b|\bservice\s+technician\b"
    r"|\bbring\s+(?:their|the)\s+vehicle\b|\bvisit\b|\breplac\w*\b|\binspect\w*\b"
    r"|\bphysical\b|\brepair(?:ed|s)?\s+at\b",
    re.IGNORECASE,
)
HW_MIXED_PAT = re.compile(r"\breplac\w*\b|\binspect\w*\b|\bphysical\b", re.IGNORECASE)
SW_REMEDY_PAT = re.compile(
    r"\bsoftware\b|\bfirmware\b|\breprogram\w*|\bre-?flash\w*"
    r"|\bflash\w*\s+(?:the\s+)?(?:[\w-]+\s+){0,3}(?:module|ecu|ecm|pcm|bcm|tcm|software|controller)"
    r"|\bupdate\s+(?:the\s+)?(?:[\w-]+\s+){0,4}(?:software|firmware|module|ecu|ecm|pcm|bcm|tcm|abs|infotainment|telematics|head\s+unit|display|camera|calibration|data\s+set|program|parameter|controller|computer|configuration)"
    r"|\bupdated\s+(?:software|firmware|calibration|data\s+set|program)"
    r"|\b(?:re)?calibrat\w*\s+(?:the\s+)?(?:[\w'-]+\s+){0,4}(?:module|ecu|ecm|pcm|bcm|tcm|ocs|sensor|camera|radar|speed|maximum\s+speed|powertrain|brake|transmission|engine|steering|controller|cluster|display|adas|collision)"
    r"|\brevised\s+(?:the\s+)?parameters",
    re.IGNORECASE,
)
NON_LIGHT_DUTY_OEM_PAT = re.compile(
    r"\btrucks?\b|\bbus(?:es)?\b|\bcoach\b|\brv\b|\bmotorhomes?\b|\btrailers?\b|\bcamper\b"
    r"|\bwinnebago\b|\bjayco\b|\bgrand\s+design\b|\bforest\s+river\b|\bthor\b|\btiffin\b|\bnewmar\b"
    r"|\bairstream\b|\bkeystone\b|\bheartland\b|\bmotiv\b|\blonestar\b|\bpaccar\b|\bnavistar\b"
    r"|\binternational\s+motors\b|\bfreightliner\b|\bdaimler\s+(?:trucks|vans)\b|\bblue\s+bird\b"
    r"|\bthomas\s+built\b|\bproterra\b|\bnew\s+flyer\b|\bgillig\b|\baltec\b|\brosenbauer\b"
    r"|\bpierce\s+manufacturing\b|\bspartan\b|\boshkosh\b|\bharley\b|\bindian\s+motorcycle\b"
    r"|\blivewire\b|\bzero\s+motorcycles\b|\bducati\b|\bkawasaki\b|\btriumph\s+motorcycles\b"
    r"|\bktm\b|\bbombardier\b|\bpolaris\b|\byamaha\b|\bhino\b|\bfuso\b|\bautocar\b|\bmarion\s+body\b"
    r"|\btractor\b|\bspecialty\s+vehicles\b|\bfire\s+apparatus\b|\bambulance\b|\bequipment\b|\bcrane\b",
    re.IGNORECASE,
)
CRASH_PAT = re.compile(r"\bcrash\b|\bcollision\b|\binjury\b|\bdeath\b", re.IGNORECASE)
FIRE_PAT = re.compile(r"\bfire\b|\bthermal\b|\bsmoke\b|\bignite\b", re.IGNORECASE)


def canonicalize_oems(mfg_series: pd.Series) -> pd.Series:
    cleaned = mfg_series.fillna("").astype(str).str.strip()
    mapped = cleaned.apply(lambda x: EXPLICIT_OEM_MAP.get(x.upper(), x))
    alnum = mapped.str.upper().str.replace(r"[^A-Z0-9]", "", regex=True)
    # Map each canonical alphanumeric key to its most frequent display name
    best_name: dict[str, str] = {}
    vc = mapped.groupby(alnum).value_counts()
    for key, disp in vc.index:
        if key not in best_name:
            best_name[key] = disp
    return alnum.map(best_name).fillna(mapped)


def parse_date_yyyymmdd(s: pd.Series) -> pd.Series:
    return pd.to_datetime(s.astype(str).str.strip(), format="%Y%m%d", errors="coerce")


def build_campaigns() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    t0 = time.time()
    zip_path = RAW_DIR / "FLAT_RCL_POST_2010.zip"
    with zipfile.ZipFile(zip_path) as zf:
        txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        raw_bytes = zf.read(txt_name)

    lines = raw_bytes.decode("latin-1", errors="replace").splitlines()
    parsed = []
    for ln in lines:
        parts = ln.split("\t")
        if len(parts) < 23:
            continue
        if len(parts) < 29:
            parts = parts + [""] * (29 - len(parts))
        parsed.append(parts[:29])

    df = pd.DataFrame(parsed, columns=RCL_COLS)
    df["CAMPNO"] = df["CAMPNO"].str.strip()
    df["RCDATE_dt"] = parse_date_yyyymmdd(df["RCDATE"])
    df["BGMAN_dt"] = parse_date_yyyymmdd(df["BGMAN"])
    df["ENDMAN_dt"] = parse_date_yyyymmdd(df["ENDMAN"])
    df["ODATE_dt"] = parse_date_yyyymmdd(df["ODATE"])
    df["POTAFF"] = pd.to_numeric(df["POTAFF"], errors="coerce")
    df["rec_year"] = df["RCDATE_dt"].dt.year
    df["model_year"] = pd.to_numeric(df["YEARTXT"], errors="coerce")
    df["MAKETXT"] = df["MAKETXT"].fillna("").str.strip().str.upper()
    df["MODELTXT"] = df["MODELTXT"].fillna("").str.strip().str.upper()
    df["comp_top"] = df["COMPNAME"].fillna("").str.split(":").str[0].str.strip().str.upper()

    v = df[(df["RCLTYPECD"].str.strip() == "V") & (df["rec_year"].between(2015, 2026))].copy()
    v["mfg_canon"] = canonicalize_oems(v["MFGNAME"])
    print(
        f"[RCL] Loaded {len(v):,} Vehicle rows (2015-2026), {v['CAMPNO'].nunique():,} campaigns, "
        f"OEMs reduced {v['MFGNAME'].nunique()} -> {v['mfg_canon'].nunique()} canonical",
        flush=True,
    )

    # Primary Make-Model per campaign (modal pair)
    v["make_model"] = v["MAKETXT"] + "__" + v["MODELTXT"]
    mm_mode = (
        v.groupby(["CAMPNO", "make_model"]).size().reset_index(name="cnt")
        .sort_values(["CAMPNO", "cnt", "make_model"], ascending=[True, False, True])
        .drop_duplicates("CAMPNO")[["CAMPNO", "make_model"]]
        .rename(columns={"make_model": "primary_make_model"})
    )

    # Campaign-level aggregation
    camp = v.groupby("CAMPNO", as_index=False).agg(
        mfg_raw=("MFGNAME", "first"),
        mfg=("mfg_canon", "first"),
        rec_date=("RCDATE_dt", "min"),
        bgman=("BGMAN_dt", "min"),
        endman=("ENDMAN_dt", "max"),
        odate=("ODATE_dt", "min"),
        rec_year=("rec_year", "min"),
        potaff_rcl=("POTAFF", "max"),
        influenced_by=("INFLUENCED_BY", "first"),
        comp_top=("comp_top", "first"),
        n_makes=("MAKETXT", "nunique"),
        n_models=("MODELTXT", "nunique"),
        rcl_do_not_drive=("DO_NOT_DRIVE", lambda s: int((s.str.strip().str.upper() == "Y").any())),
        rcl_park_outside=("PARK_OUTSIDE", lambda s: int((s.str.strip().str.upper() == "Y").any())),
        has_fmvss=("FMVSS", lambda s: int((s.str.strip() != "").any())),
        desc_defect=("DESC_DEFECT", "first"),
        consequence=("CONEQUENCE_DEFECT", "first"),
        corrective_action=("CORRECTIVE_ACTION", "first"),
    )

    # Model-year stats (valid vehicle MYs 1980-2027)
    v_my = v[v["model_year"].between(1980, 2027)]
    my_agg = v_my.groupby("CAMPNO", as_index=False).agg(
        min_my=("model_year", "min"),
        max_my=("model_year", "max"),
        median_my=("model_year", "median"),
        n_mys=("model_year", "nunique"),
        n_make_model_mys=("make_model", "count"),
    )
    camp = camp.merge(my_agg, on="CAMPNO", how="left").merge(mm_mode, on="CAMPNO", how="left")

    # Merge DOT Socrata 6axg-epim
    dot = pd.read_csv(RAW_DIR / "dot_6axg_epim_recalls.csv", low_memory=False)
    dot["CAMPNO"] = dot["nhtsa_id"].astype(str).str.strip()
    dot_sub = dot.drop_duplicates("CAMPNO")[
        [
            "CAMPNO",
            "potentially_affected",
            "completion_rate",
            "do_not_drive",
            "fire_risk_when_parked",
            "subject",
            "defect_summary",
            "corrective_action",
        ]
    ].rename(
        columns={
            "potentially_affected": "dot_potaff",
            "completion_rate": "dot_completion_rate_raw",
            "do_not_drive": "dot_dnd_str",
            "fire_risk_when_parked": "dot_fire_parked_str",
            "subject": "dot_subject",
            "defect_summary": "dot_defect_summary",
            "corrective_action": "dot_corrective_action",
        }
    )
    camp = camp.merge(dot_sub, on="CAMPNO", how="left")

    # Merge NHTSA Campaign API ground truth
    api = pd.read_csv(PROC_DIR / "nhtsa_api_campaign_groundtruth.csv")
    api_sub = api.drop_duplicates("campno")[
        [
            "campno",
            "sample_stratum",
            "api_ota_any",
            "api_ota_all",
            "api_ota_share",
            "api_park_it",
            "api_park_outside",
            "nhtsa_action_number",
        ]
    ].rename(columns={"campno": "CAMPNO"})
    camp = camp.merge(api_sub, on="CAMPNO", how="left")
    camp["api_queried"] = camp["api_ota_any"].notna().astype(int)

    # Reconcile potentially_affected (DOT vs FLAT_RCL)
    camp["potaff"] = camp["dot_potaff"].combine_first(camp["potaff_rcl"])
    both_pa = camp.dropna(subset=["dot_potaff", "potaff_rcl"])
    pa_corr = float(np.corrcoef(np.log1p(both_pa["dot_potaff"].clip(0)), np.log1p(both_pa["potaff_rcl"].clip(0)))[0, 1])

    # Completion rate hygiene (flag >100% administrative outliers, clip to [0, 100])
    camp["cr_gt_100"] = (camp["dot_completion_rate_raw"] > 100.0).astype(int)
    camp["completion_rate"] = camp["dot_completion_rate_raw"].clip(lower=0.0, upper=100.0)
    camp["completion_rate_strict"] = camp["dot_completion_rate_raw"].where(
        camp["dot_completion_rate_raw"].between(0.0, 100.0)
    )

    # Audited 4-way Remedy Modality classification (strictly remedy-based to avoid hardware-only false positives)
    act_comb = camp["corrective_action"].fillna("") + " " + camp["dot_corrective_action"].fillna("")
    has_ota_txt = act_comb.str.contains(OTA_REMEDY_PAT)
    has_ota_neg = act_comb.str.contains(OTA_NEG_PAT)
    has_dealer_or_hw = act_comb.str.contains(DEALER_OR_HW_PAT)
    has_hw_mixed = act_comb.str.contains(HW_MIXED_PAT)
    has_sw_remedy = act_comb.str.contains(SW_REMEDY_PAT)

    camp["is_ota_audited"] = (
        (has_ota_txt & (~has_ota_neg)) | (camp["api_ota_any"] == 1)
    ).astype(int)
    camp["is_ota_pure"] = ((camp["is_ota_audited"] == 1) & (~has_dealer_or_hw)).astype(int)
    camp["is_ota_hybrid"] = ((camp["is_ota_audited"] == 1) & has_dealer_or_hw).astype(int)
    camp["is_ota_hybrid_swchoice"] = ((camp["is_ota_hybrid"] == 1) & (~has_hw_mixed)).astype(int)
    camp["is_ota_hybrid_hwmixed"] = ((camp["is_ota_hybrid"] == 1) & has_hw_mixed).astype(int)
    camp["is_sw_any"] = ((camp["is_ota_audited"] == 1) | has_sw_remedy).astype(int)
    camp["is_dealer_sw"] = ((camp["is_ota_audited"] == 0) & has_sw_remedy).astype(int)

    camp["modality4"] = np.where(
        camp["is_ota_pure"] == 1,
        "Pure_OTA",
        np.where(
            camp["is_ota_hybrid"] == 1,
            "Hybrid_OTA",
            np.where(camp["is_dealer_sw"] == 1, "Dealer_Software", "Physical_Hardware"),
        ),
    )

    # Official API OTA flag (strict among queried + full with 0 for non-candidate physicals verified 0/250 FN)
    camp["is_ota_api_strict"] = camp["api_ota_any"]
    camp["is_ota_api_full"] = camp["api_ota_any"].fillna(0).astype(int)

    # Safety severity & regulatory oversight indicators
    camp["do_not_drive"] = (
        (camp["rcl_do_not_drive"] == 1)
        | (camp["dot_dnd_str"].fillna("").str.strip().str.upper() == "YES")
        | (camp["api_park_it"] == 1)
    ).astype(int)
    camp["park_outside"] = (
        (camp["rcl_park_outside"] == 1)
        | (camp["dot_fire_parked_str"].fillna("").str.strip().str.upper() == "YES")
        | (camp["api_park_outside"] == 1)
    ).astype(int)
    camp["has_odi_action"] = (camp["nhtsa_action_number"].fillna("").str.strip() != "").astype(int)
    camp["is_regulator_forced"] = (
        camp["influenced_by"].fillna("").str.strip().str.upper().isin(["ODI", "OVSC"])
    ).astype(int)
    camp["con_crash"] = camp["consequence"].fillna("").str.contains(CRASH_PAT).astype(int)
    camp["con_fire"] = camp["consequence"].fillna("").str.contains(FIRE_PAT).astype(int)

    # Campaign age, maturity, and quarters
    camp["days_since_recall"] = (SNAPSHOT_DATE - camp["rec_date"]).dt.days
    camp["is_mature_18m"] = (camp["days_since_recall"] >= 540).astype(int)
    camp["is_mature_12m"] = (camp["days_since_recall"] >= 365).astype(int)
    camp["rec_quarter"] = (
        camp["rec_date"].dt.year.astype("Int64").astype(str)
        + "Q"
        + camp["rec_date"].dt.quarter.astype("Int64").astype(str)
    )
    camp["age_bin"] = pd.cut(
        camp["days_since_recall"],
        bins=[-1, 90, 180, 365, 540, 730, 100000],
        labels=["0-3m", "3-6m", "6-12m", "12-18m", "18-24m", ">24m"],
    ).astype(str)

    # Lifecycle lags & operational speed
    camp["days_mfg_to_recall"] = (camp["rec_date"] - camp["bgman"]).dt.days
    camp.loc[~camp["days_mfg_to_recall"].between(0, 5475), "days_mfg_to_recall"] = np.nan
    camp["still_in_production"] = (camp["endman"] >= camp["rec_date"] - pd.Timedelta(days=90)).astype(float)
    camp.loc[camp["endman"].isna(), "still_in_production"] = np.nan
    camp["days_recall_to_owner"] = (camp["odate"] - camp["rec_date"]).dt.days
    camp.loc[~camp["days_recall_to_owner"].between(0, 730), "days_recall_to_owner"] = np.nan

    # Fleet blast radius & Net Unremedied Fleet Exposure
    camp["log_potaff"] = np.log1p(camp["potaff"].clip(lower=0))
    camp["log_n_models"] = np.log1p(camp["n_models"].clip(lower=0))
    camp["log_n_mys"] = np.log1p(camp["n_mys"].fillna(1).clip(lower=1))
    denom_my = (camp["n_models"].clip(lower=1) * camp["n_mys"].fillna(1).clip(lower=1))
    camp["log_potaff_per_my"] = np.log1p(camp["potaff"].clip(lower=0) / denom_my)
    camp["vehicle_age_years"] = (camp["rec_year"] - camp["min_my"]).clip(lower=-1, upper=30)
    camp["median_vehicle_age"] = (camp["rec_year"] - camp["median_my"]).clip(lower=-1, upper=30)

    camp["unremedied_vehicles"] = (
        camp["potaff"] * (1.0 - camp["completion_rate"] / 100.0)
    ).clip(lower=0.0)
    camp.loc[camp["completion_rate"].isna() | camp["potaff"].isna(), "unremedied_vehicles"] = np.nan
    camp["log_unremedied"] = np.log1p(camp["unremedied_vehicles"])

    camp["unremedied_vehicles_strict"] = (
        camp["potaff"] * (1.0 - camp["completion_rate_strict"] / 100.0)
    ).clip(lower=0.0)
    camp.loc[
        camp["completion_rate_strict"].isna() | camp["potaff"].isna(), "unremedied_vehicles_strict"
    ] = np.nan
    camp["log_unremedied_strict"] = np.log1p(camp["unremedied_vehicles_strict"])

    # Repeat-defect cascades at exact (MAKETXT, MODELTXT, model_year, comp_top) across 2015-2026
    mm = (
        v[v["model_year"].between(2005, 2027)]
        .groupby(["CAMPNO", "MAKETXT", "MODELTXT", "model_year", "comp_top"], as_index=False)
        .agg(rec_date=("RCDATE_dt", "min"))
    )
    mm = mm.sort_values(["MAKETXT", "MODELTXT", "model_year", "comp_top", "rec_date", "CAMPNO"])
    mm["next_date"] = mm.groupby(["MAKETXT", "MODELTXT", "model_year", "comp_top"])["rec_date"].shift(-1)
    mm["days_to_repeat"] = (mm["next_date"] - mm["rec_date"]).dt.days
    mm["has_repeat_365d"] = ((mm["days_to_repeat"] >= 1) & (mm["days_to_repeat"] <= 365)).astype(int)
    mm["has_repeat_730d"] = ((mm["days_to_repeat"] >= 1) & (mm["days_to_repeat"] <= 730)).astype(int)

    camp_rep = mm.groupby("CAMPNO", as_index=False).agg(
        any_repeat_365d=("has_repeat_365d", "max"),
        any_repeat_730d=("has_repeat_730d", "max"),
        share_repeat_365d=("has_repeat_365d", "mean"),
        share_repeat_730d=("has_repeat_730d", "mean"),
    )
    camp = camp.merge(camp_rep, on="CAMPNO", how="left")
    camp["uncensored_365d"] = (camp["rec_date"] <= SNAPSHOT_DATE - pd.Timedelta(days=365)).astype(int)
    camp["uncensored_730d"] = (camp["rec_date"] <= SNAPSHOT_DATE - pd.Timedelta(days=730)).astype(int)

    # OEM OTA adoption timing (first OTA recall year per canonical OEM)
    ota_first = (
        camp[camp["is_ota_audited"] == 1]
        .groupby("mfg", as_index=False)
        .agg(oem_first_ota_year=("rec_year", "min"), oem_first_ota_date=("rec_date", "min"), oem_n_ota=("CAMPNO", "count"))
    )
    camp = camp.merge(ota_first, on="mfg", how="left")
    camp["oem_ever_ota"] = camp["oem_first_ota_year"].notna().astype(int)
    camp["event_time_yr"] = camp["rec_year"] - camp["oem_first_ota_year"]
    camp["is_tesla"] = (camp["mfg"] == "Tesla, Inc.").astype(int)
    camp["is_ev_native"] = camp["mfg"].isin(
        ["Tesla, Inc.", "Rivian Automotive, LLC", "Lucid USA, Inc.", "Fisker Group Inc", "Polestar Automotive USA, Inc."]
    ).astype(int)
    camp["is_light_duty_passenger"] = (~camp["mfg"].fillna("").str.contains(NON_LIGHT_DUTY_OEM_PAT)).astype(int)

    # Build clean Make-Model-MY-Comp lookup for Complaint matching (2021-2025 campaigns)
    v_ev = v[(v["RCDATE_dt"] >= "2021-01-01") & (v["RCDATE_dt"] <= "2025-11-25") & (v["model_year"].between(2000, 2026))].copy()
    v_ev["my_int"] = v_ev["model_year"].astype(int)
    mm_lookup = v_ev[["CAMPNO", "MAKETXT", "MODELTXT", "my_int", "comp_top", "RCDATE_dt"]].drop_duplicates()

    stats_summary = {
        "n_campaigns_2015_2026": len(camp),
        "n_campaigns_2018_2026": int(camp["rec_year"].between(2018, 2026).sum()),
        "potaff_log_corr_dot_vs_rcl": round(pa_corr, 5),
        "n_cr_gt_100_2018_2026": int(camp[camp["rec_year"].between(2018, 2026)]["cr_gt_100"].sum()),
        "modality4_2018_2026": camp[camp["rec_year"].between(2018, 2026)]["modality4"].value_counts().to_dict(),
        "modality4_2018_2026_mature18m": camp[
            camp["rec_year"].between(2018, 2026) & (camp["is_mature_18m"] == 1) & camp["completion_rate"].notna()
        ]["modality4"].value_counts().to_dict(),
        "n_ota_oems_2018_2026": int(camp[camp["rec_year"].between(2018, 2026) & (camp["is_ota_audited"] == 1)]["mfg"].nunique()),
        "elapsed_sec": round(time.time() - t0, 2),
    }
    return camp, mm_lookup, stats_summary


def build_complaint_event_study(camp: pd.DataFrame, mm_lookup: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Stream 2020-2026 NHTSA ODI consumer complaints and link to 2021-2025 vehicle recalls
    over a strictly balanced [-12, +12] relative-month window (both LDATE receipt & FAILDATE incident).
    """
    t0 = time.time()
    # Map (MAKE, MODEL, MY, COMP) -> list[(CAMPNO, rec_ym)] and (MAKE, MODEL, MY) -> list[(CAMPNO, rec_ym)]
    camp_rec_ym: dict[str, int] = {}
    key_comp_map: dict[tuple[str, str, int, str], list[tuple[str, int]]] = defaultdict(list)
    key_veh_map: dict[tuple[str, str, int], list[tuple[str, int]]] = defaultdict(list)
    seen_veh: set[tuple[str, str, int, str]] = set()

    for row in mm_lookup.itertuples(index=False):
        cno = row.CAMPNO
        ym = row.RCDATE_dt.year * 12 + (row.RCDATE_dt.month - 1)
        camp_rec_ym[cno] = ym
        key_comp_map[(row.MAKETXT, row.MODELTXT, int(row.my_int), row.comp_top)].append((cno, ym))
        vk = (row.MAKETXT, row.MODELTXT, int(row.my_int))
        if (vk[0], vk[1], vk[2], cno) not in seen_veh:
            seen_veh.add((vk[0], vk[1], vk[2], cno))
            key_veh_map[vk].append((cno, ym))

    valid_camps = sorted(camp_rec_ym.keys())
    print(
        f"[CMPL] Indexed {len(valid_camps):,} balanced 2021-2025 campaigns "
        f"({len(key_comp_map):,} make-model-MY-comp keys, {len(key_veh_map):,} make-model-MY keys)",
        flush=True,
    )

    # Counters keyed by (CAMPNO, rel_month) ->
    # [0:comp_ldate, 1:comp_ldate_sev, 2:comp_fail, 3:comp_fail_sev, 4:veh_ldate, 5:veh_ldate_sev,
    #  6:comp_fail_crash, 7:comp_fail_fire, 8:comp_fail_inj, 9:comp_fail_deaths]
    # Strictly deduplicated by unique ODINO (vehicle-level) and unique (ODINO, comp_top) (component-level)
    camp_idx = {cno: i for i, cno in enumerate(valid_camps)}
    counts = np.zeros((len(valid_camps), 25, 10), dtype=np.int32)

    n_total_cmpl_rows = 0
    seen_all_odino: set[str] = set()
    seen_all_odino_comp: set[tuple[str, str]] = set()
    seen_camp_veh_odino: set[tuple[int, str]] = set()
    seen_camp_comp_odino: set[tuple[int, str]] = set()
    n_matched_comp_ldate = 0
    n_matched_comp_fail = 0
    n_matched_veh_ldate = 0

    for zname in ("COMPLAINTS_RECEIVED_2020-2024.zip", "COMPLAINTS_RECEIVED_2025-2026.zip"):
        zpath = RAW_DIR / zname
        with zipfile.ZipFile(zpath) as zf:
            txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
            with zf.open(txt_name) as fh:
                for raw_ln in fh:
                    n_total_cmpl_rows += 1
                    parts = raw_ln.decode("latin-1", errors="replace").split("\t")
                    if len(parts) < 17:
                        continue
                    odino = parts[1].strip()
                    comp_top = parts[11].split(":")[0].strip().upper()
                    seen_all_odino.add(odino)
                    seen_all_odino_comp.add((odino, comp_top))

                    mk = parts[3].strip().upper()
                    mdl = parts[4].strip().upper()
                    yr_s = parts[5].strip()
                    if len(yr_s) != 4 or not yr_s.isdigit():
                        continue
                    my = int(yr_s)
                    vk = (mk, mdl, my)
                    veh_hits = key_veh_map.get(vk)
                    if not veh_hits:
                        continue

                    crash = 1 if parts[6].strip().upper() == "Y" else 0
                    fire = 1 if parts[8].strip().upper() == "Y" else 0
                    inj = int(parts[9]) if parts[9].strip().isdigit() else 0
                    deaths = int(parts[10]) if parts[10].strip().isdigit() else 0
                    is_sev = 1 if (crash or fire or inj > 0 or deaths > 0) else 0

                    # Parse LDATE (col 16) and FAILDATE (col 7) fast from YYYYMMDD
                    ld = parts[16].strip()
                    ld_ym = -1
                    if len(ld) == 8 and ld.isdigit():
                        ly, lm = int(ld[:4]), int(ld[4:6])
                        if 2020 <= ly <= 2026 and 1 <= lm <= 12:
                            ld_ym = ly * 12 + (lm - 1)

                    fd = parts[7].strip()
                    fd_ym = -1
                    if len(fd) == 8 and fd.isdigit():
                        fy, fm = int(fd[:4]), int(fd[4:6])
                        if 2020 <= fy <= 2026 and 1 <= fm <= 12:
                            fd_ym = fy * 12 + (fm - 1)

                    if ld_ym >= 0:
                        for cno, rym in veh_hits:
                            rel = ld_ym - rym
                            if -12 <= rel <= 12:
                                ci = camp_idx[cno]
                                cv_key = (ci, odino)
                                if cv_key not in seen_camp_veh_odino:
                                    seen_camp_veh_odino.add(cv_key)
                                    slot = rel + 12
                                    counts[ci, slot, 4] += 1
                                    if is_sev:
                                        counts[ci, slot, 5] += 1
                                    n_matched_veh_ldate += 1

                    comp_hits = key_comp_map.get((mk, mdl, my, comp_top))
                    if comp_hits:
                        for cno, rym in comp_hits:
                            ci = camp_idx[cno]
                            cc_key = (ci, odino)
                            if cc_key in seen_camp_comp_odino:
                                continue
                            ld_ok = ld_ym >= 0 and (-12 <= (ld_ym - rym) <= 12)
                            fd_ok = fd_ym >= 0 and (-12 <= (fd_ym - rym) <= 12)
                            if not (ld_ok or fd_ok):
                                continue
                            seen_camp_comp_odino.add(cc_key)
                            if ld_ok:
                                slot_l = (ld_ym - rym) + 12
                                counts[ci, slot_l, 0] += 1
                                if is_sev:
                                    counts[ci, slot_l, 1] += 1
                                n_matched_comp_ldate += 1
                            if fd_ok:
                                slot_f = (fd_ym - rym) + 12
                                counts[ci, slot_f, 2] += 1
                                if is_sev:
                                    counts[ci, slot_f, 3] += 1
                                if crash:
                                    counts[ci, slot_f, 6] += 1
                                if fire:
                                    counts[ci, slot_f, 7] += 1
                                if inj > 0:
                                    counts[ci, slot_f, 8] += 1
                                if deaths > 0:
                                    counts[ci, slot_f, 9] += 1
                                n_matched_comp_fail += 1

    # Assemble tidy panel DataFrame (only campaigns with valid metadata)
    camp_meta = camp.set_index("CAMPNO")[
        [
            "mfg",
            "rec_year",
            "rec_date",
            "potaff",
            "modality4",
            "is_ota_audited",
            "is_ota_pure",
            "is_ota_hybrid",
            "is_dealer_sw",
            "is_ota_api_full",
            "comp_top",
            "min_my",
            "is_tesla",
        ]
    ]
    rows_out = []
    camp_pre_post = []
    for i, cno in enumerate(valid_camps):
        if cno not in camp_meta.index:
            continue
        rym = camp_rec_ym[cno]
        arr = counts[i]  # (25, 10)
        camp_pre_post.append(
            {
                "CAMPNO": cno,
                "cmpl_pre12m_comp": int(arr[0:12, 0].sum()),
                "cmpl_post12m_comp": int(arr[13:25, 0].sum()),
                "cmpl_pre12m_sev": int(arr[0:12, 1].sum()),
                "cmpl_post12m_sev": int(arr[13:25, 1].sum()),
                "cmpl_pre12m_fail": int(arr[0:12, 2].sum()),
                "cmpl_post12m_fail": int(arr[13:25, 2].sum()),
                "cmpl_pre12m_fail_sev": int(arr[0:12, 3].sum()),
                "cmpl_post12m_fail_sev": int(arr[13:25, 3].sum()),
                "cmpl_pre12m_crash": int(arr[0:12, 6].sum()),
                "cmpl_post12m_crash": int(arr[13:25, 6].sum()),
                "cmpl_pre12m_fire": int(arr[0:12, 7].sum()),
                "cmpl_post12m_fire": int(arr[13:25, 7].sum()),
                "cmpl_pre12m_inj_cmpl": int(arr[0:12, 8].sum()),
                "cmpl_post12m_inj_cmpl": int(arr[13:25, 8].sum()),
                "cmpl_pre12m_fatal_cmpl": int(arr[0:12, 9].sum()),
                "cmpl_post12m_fatal_cmpl": int(arr[13:25, 9].sum()),
            }
        )
        for slot in range(25):
            rel = slot - 12
            cal_ym = rym + rel
            cal_y = cal_ym // 12
            cal_m = (cal_ym % 12) + 1
            rows_out.append(
                (
                    cno,
                    rel,
                    f"{cal_y:04d}-{cal_m:02d}",
                    int(arr[slot, 0]),
                    int(arr[slot, 1]),
                    int(arr[slot, 2]),
                    int(arr[slot, 3]),
                    int(arr[slot, 4]),
                    int(arr[slot, 5]),
                    int(arr[slot, 6]),
                    int(arr[slot, 7]),
                    int(arr[slot, 8]),
                    int(arr[slot, 9]),
                )
            )

    es_df = pd.DataFrame(
        rows_out,
        columns=[
            "CAMPNO",
            "rel_month",
            "cal_ym",
            "cmpl_comp_ldate",
            "cmpl_comp_ldate_sev",
            "cmpl_comp_fail",
            "cmpl_comp_fail_sev",
            "cmpl_veh_ldate",
            "cmpl_veh_ldate_sev",
            "cmpl_comp_fail_crash",
            "cmpl_comp_fail_fire",
            "cmpl_comp_fail_inj",
            "cmpl_comp_fail_deaths",
        ],
    )
    es_df = es_df.merge(camp_meta.reset_index(), on="CAMPNO", how="left")
    cmpl_summary_df = pd.DataFrame(camp_pre_post)
    camp = camp.merge(cmpl_summary_df, on="CAMPNO", how="left")

    cmpl_stats = {
        "n_raw_complaint_rows_2020_2026": int(n_total_cmpl_rows),
        "n_unique_odino_2020_2026": len(seen_all_odino),
        "n_unique_odino_comp_2020_2026": len(seen_all_odino_comp),
        "n_balanced_campaigns_2021_2025": len(valid_camps),
        "n_event_study_rows": len(es_df),
        "n_matched_comp_ldate_links": int(n_matched_comp_ldate),
        "n_matched_comp_fail_links": int(n_matched_comp_fail),
        "n_matched_veh_ldate_links": int(n_matched_veh_ldate),
        "n_campaigns_with_ge1_comp_cmpl": int(
            (cmpl_summary_df["cmpl_pre12m_comp"] + cmpl_summary_df["cmpl_post12m_comp"] > 0).sum()
        ),
        "elapsed_sec": round(time.time() - t0, 2),
    }
    print(f"[CMPL] Built complaint event study in {cmpl_stats['elapsed_sec']}s: {cmpl_stats}", flush=True)
    return camp, es_df, cmpl_stats


def main() -> None:
    camp, mm_lookup, rcl_stats = build_campaigns()
    camp, es_df, cmpl_stats = build_complaint_event_study(camp, mm_lookup)

    # Drop verbose text blobs from main econometric CSV so it stays fast and lean (save text audit copy separately)
    text_cols = ["desc_defect", "consequence", "corrective_action", "dot_subject", "dot_defect_summary", "dot_corrective_action"]
    camp_lean = camp.drop(columns=text_cols)
    camp_lean.to_csv(PROC_DIR / "campaigns_2015_2026.csv", index=False)
    camp[["CAMPNO", "mfg", "rec_year", "modality4", "is_ota_api_strict"] + text_cols].to_csv(
        PROC_DIR / "campaigns_text_audit.csv", index=False
    )
    es_df.to_csv(PROC_DIR / "complaint_event_study_panel.csv", index=False)

    summary = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "snapshot_date": str(SNAPSHOT_DATE.date()),
        "rcl_panel": rcl_stats,
        "complaint_panel": cmpl_stats,
    }
    (RES_DIR / "step3_panel_build_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("[DONE] Step 3 complete!", flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
