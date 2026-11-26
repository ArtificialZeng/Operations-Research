"""Step 02 (Pillar 2 + Unification Test U1): Same-Rooftop Optical Physics, Zero-EIV Nonlinear
Wildfire Smoke Amplification, EPA Aerosol Speciation (NO3-, SO4^2-, OC, EC) & RH/Temp
Mechanism, and Same-Rooftop Daily Exceedance Trigger Multiplier (U1).

Fixes Wave-6 Audit Problems 5 & 8:
  - Explicitly separates 2023-2025 (App. N / Speciation / Met / NOAA HMS window) and full
    2023-May 2026 collocated pairs for both T640_FW (636/638) and BAM (170/209) vs FRM.
  - Permanently drops EIV-contaminated I(FRM >= 25) regressions; estimates level bias
    (FEM - FRM) and log-ratio log(FEM / FRM) using THREE strictly EIV-free instruments:
      (1) Independent other-site monitor in the same county-day (<15, 15-25, >=25 ug/m3),
      (2) Bland-Altman mean (FEM + FRM) / 2 bins (<15, 15-25, >=25 ug/m3),
      (3) External satellite NOAA HMS daily wildfire smoke polygons (None/Light/Medium/Heavy).
  - Merges EPA AQS daily Speciation (NO3-, SO4^2-, OC, EC, Soil) and Meteorology (RH, TEMP)
    onto collocated pairs (exact rooftop 0 km first, fallback nearest <25 km in same county-day)
    to identify the exact physical drivers of Midwest/Winter bias and wildfire smoke amplification.
  - Executes Unification Test U1: same-rooftop >35 ug/m3 & >25 ug/m3 & >site-p98 exceedance
    trigger multiplier (paired McNemar exact test + rooftop-day FE LPM) for T640_FW vs BAM.
"""

from __future__ import annotations

import math
from typing import Any

import numpy as np
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


def haversine_km(lat1: np.ndarray, lon1: np.ndarray, lat2: np.ndarray, lon2: np.ndarray) -> np.ndarray:
    """Vectorized Haversine distance in kilometers."""
    r = 6371.0088
    p1 = np.radians(lat1)
    p2 = np.radians(lat2)
    dp = np.radians(lat2 - lat1)
    dl = np.radians(lon2 - lon1)
    a = np.sin(dp / 2.0) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2.0) ** 2
    return 2.0 * r * np.arcsin(np.sqrt(np.clip(a, 0.0, 1.0)))


def load_daily_2023_2026() -> pd.DataFrame:
    """Load daily 24-hour 88101 data for 2023-2026 (2026 through May 2026)."""
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
        "Latitude",
        "Longitude",
    ]
    dfs = []
    for yr in (2023, 2024, 2025, 2026):
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
    daily["mon_id"] = daily["site_id"] + "-" + daily["POC"].astype(str)
    daily["method_code"] = daily["Method Code"].str.strip().str.replace(".0", "", regex=False)
    daily["Event Type"] = daily["Event Type"].fillna("None").astype(str)
    daily = daily[daily["Event Type"].isin(["None", "Included"])].copy()
    daily["Arithmetic Mean"] = pd.to_numeric(daily["Arithmetic Mean"], errors="coerce")
    daily["lat"] = pd.to_numeric(daily["Latitude"], errors="coerce")
    daily["lon"] = pd.to_numeric(daily["Longitude"], errors="coerce")
    daily = daily.dropna(subset=["Arithmetic Mean"]).copy()
    daily = daily.drop_duplicates(
        subset=["mon_id", "Date Local", "Sample Duration", "Event Type", "method_code"]
    )
    mc_u = daily[["method_code", "Method Name"]].drop_duplicates("method_code")
    mc_dict = {r["method_code"]: mc_class(r["method_code"], r["Method Name"]) for _, r in mc_u.iterrows()}
    daily["inst"] = daily["method_code"].map(mc_dict)
    daily["Month"] = daily["Date Local"].str.slice(5, 7).astype(int)
    daily["Quarter"] = (daily["Month"] - 1) // 3 + 1
    daily["ym"] = daily["Date Local"].str.slice(0, 7)
    return daily


def build_other_site_county_pm(daily: pd.DataFrame) -> pd.DataFrame:
    """Compute strictly independent other-site daily PM2.5 in the same county-day:
      - other_site_pm_all: leave-one-site-out mean across all aligned/FRM/BAM sites in county-day
      - other_site_pm_non_t640: leave-one-site-out mean across strictly FRM/BAM sites only
    """
    d_ok = daily[~daily["inst"].isin(["T640_RAW"])].copy()
    site_day = (
        d_ok.groupby(["county_fips", "site_id", "Date Local"], as_index=False)
        .agg(site_pm=("Arithmetic Mean", "mean"))
    )
    cnty_tot = (
        site_day.groupby(["county_fips", "Date Local"], as_index=False)
        .agg(sum_pm=("site_pm", "sum"), n_sites=("site_pm", "size"))
    )
    site_day = site_day.merge(cnty_tot, on=["county_fips", "Date Local"], how="left")
    site_day["other_site_pm"] = np.where(
        site_day["n_sites"] >= 2,
        (site_day["sum_pm"] - site_day["site_pm"]) / (site_day["n_sites"] - 1),
        np.nan,
    )

    # Also non-T640 other sites (FRM + BAM only) for zero-optical-instrument robustness
    d_nt = daily[daily["inst"].isin(["FRM", "BAM"])].copy()
    sd_nt = (
        d_nt.groupby(["county_fips", "site_id", "Date Local"], as_index=False)
        .agg(site_pm_nt=("Arithmetic Mean", "mean"))
    )
    ct_nt = (
        sd_nt.groupby(["county_fips", "Date Local"], as_index=False)
        .agg(sum_nt=("site_pm_nt", "sum"), n_nt=("site_pm_nt", "size"))
    )
    out = site_day[["site_id", "county_fips", "Date Local", "other_site_pm"]].merge(
        sd_nt, on=["county_fips", "site_id", "Date Local"], how="left"
    ).merge(ct_nt, on=["county_fips", "Date Local"], how="left")
    has_self_nt = out["site_pm_nt"].notna()
    other_n_nt = np.where(has_self_nt, out["n_nt"].fillna(0) - 1, out["n_nt"].fillna(0))
    other_sum_nt = np.where(
        has_self_nt,
        out["sum_nt"].fillna(0.0) - out["site_pm_nt"].fillna(0.0),
        out["sum_nt"].fillna(0.0),
    )
    out["other_site_pm_non_t640"] = np.where(other_n_nt >= 1, other_sum_nt / np.maximum(other_n_nt, 1), np.nan)
    return out[["site_id", "Date Local", "other_site_pm", "other_site_pm_non_t640"]]


def load_speciation_and_met_2023_2025() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load EPA AQS Speciation (NO3-, SO4^2-, OC, EC, Soil) and Meteorology (TEMP_C, RH) for 2023-2025."""
    spec_codes = {
        "88306": "no3",
        "88403": "so4",
        "88320": "oc_tor",
        "88370": "oc_csn",
        "88321": "ec_tor",
        "88380": "ec_csn",
        "88348": "soil",
    }
    sp_dfs = []
    use_s = [
        "State Code",
        "County Code",
        "Site Num",
        "Parameter Code",
        "Sample Duration",
        "Date Local",
        "Arithmetic Mean",
        "Latitude",
        "Longitude",
    ]
    for yr in (2023, 2024, 2025):
        df = read_zip_csv(
            ENRICH_DIR / f"daily_SPEC_{yr}.zip",
            usecols=use_s,
            dtype={"State Code": str, "County Code": str, "Site Num": str, "Parameter Code": str},
        )
        df = df[(df["Parameter Code"].isin(spec_codes.keys())) & (df["Sample Duration"] == "24 HOUR")].copy()
        sp_dfs.append(df)
    sp = pd.concat(sp_dfs, ignore_index=True)
    sp["state_fips"] = sp["State Code"].str.zfill(2)
    sp = sp[sp["state_fips"].isin(VALID_STATES)].copy()
    sp["county_fips"] = sp["state_fips"] + sp["County Code"].str.zfill(3)
    sp["site_id"] = sp["county_fips"] + "-" + sp["Site Num"].str.zfill(4)
    sp["val"] = pd.to_numeric(sp["Arithmetic Mean"], errors="coerce")
    sp["lat"] = pd.to_numeric(sp["Latitude"], errors="coerce")
    sp["lon"] = pd.to_numeric(sp["Longitude"], errors="coerce")
    sp["species"] = sp["Parameter Code"].map(spec_codes)
    sp = sp.dropna(subset=["val"]).copy()

    # Average duplicate POCs per site-day-species, then pivot wide
    sp_piv = (
        sp.groupby(["site_id", "county_fips", "Date Local", "species"], as_index=False)
        .agg(val=("val", "mean"))
        .pivot(index=["site_id", "county_fips", "Date Local"], columns="species", values="val")
        .reset_index()
    )
    sp_coords = (
        sp.dropna(subset=["lat", "lon"])
        .groupby("site_id", as_index=False)
        .agg(spec_lat=("lat", "first"), spec_lon=("lon", "first"))
    )
    sp_piv = sp_piv.merge(sp_coords, on="site_id", how="left")
    # Combine TOR primary with CSN fallback for OC & EC
    sp_piv["oc"] = sp_piv["oc_tor"].fillna(sp_piv["oc_csn"]) if "oc_csn" in sp_piv.columns else sp_piv["oc_tor"]
    sp_piv["ec"] = sp_piv["ec_tor"].fillna(sp_piv["ec_csn"]) if "ec_csn" in sp_piv.columns else sp_piv["ec_tor"]
    # Clean physically impossible negative filter-blank noise (floor at 0 for concentrations, keep raw audit)
    for col in ("no3", "so4", "oc", "ec", "soil"):
        if col in sp_piv.columns:
            sp_piv[col] = sp_piv[col].clip(lower=0.0)
    sp_wide = sp_piv[["site_id", "county_fips", "Date Local", "spec_lat", "spec_lon", "no3", "so4", "oc", "ec", "soil"]].copy()

    # Load TEMP (62101, F -> C) & RH (62201, %)
    use_met = [
        "State Code",
        "County Code",
        "Site Num",
        "Parameter Code",
        "Date Local",
        "Arithmetic Mean",
        "Latitude",
        "Longitude",
    ]
    met_dfs = []
    for prefix, pcode, colname in [("daily_TEMP", "62101", "temp_f"), ("daily_RH_DP", "62201", "rh_pct")]:
        parts = []
        for yr in (2023, 2024, 2025):
            df = read_zip_csv(
                ENRICH_DIR / f"{prefix}_{yr}.zip",
                usecols=use_met,
                dtype={"State Code": str, "County Code": str, "Site Num": str, "Parameter Code": str},
            )
            df = df[df["Parameter Code"] == pcode].copy()
            parts.append(df)
        mdf = pd.concat(parts, ignore_index=True)
        mdf["state_fips"] = mdf["State Code"].str.zfill(2)
        mdf = mdf[mdf["state_fips"].isin(VALID_STATES)].copy()
        mdf["county_fips"] = mdf["state_fips"] + mdf["County Code"].str.zfill(3)
        mdf["site_id"] = mdf["county_fips"] + "-" + mdf["Site Num"].str.zfill(4)
        mdf["val"] = pd.to_numeric(mdf["Arithmetic Mean"], errors="coerce")
        mdf["lat"] = pd.to_numeric(mdf["Latitude"], errors="coerce")
        mdf["lon"] = pd.to_numeric(mdf["Longitude"], errors="coerce")
        mdf = mdf.dropna(subset=["val"]).copy()
        agg = (
            mdf.groupby(["site_id", "county_fips", "Date Local"], as_index=False)
            .agg(**{colname: ("val", "mean"), "met_lat": ("lat", "first"), "met_lon": ("lon", "first")})
        )
        met_dfs.append(agg)

    t_df, rh_df = met_dfs
    t_df["temp_c"] = (t_df["temp_f"] - 32.0) * (5.0 / 9.0)
    rh_df["rh_pct"] = rh_df["rh_pct"].clip(lower=0.0, upper=100.0)
    met_wide = (
        t_df[["site_id", "county_fips", "Date Local", "temp_c", "met_lat", "met_lon"]]
        .merge(
            rh_df[["site_id", "county_fips", "Date Local", "rh_pct", "met_lat", "met_lon"]],
            on=["site_id", "county_fips", "Date Local"],
            how="outer",
            suffixes=("_t", "_r"),
        )
    )
    met_wide["met_lat"] = met_wide["met_lat_t"].fillna(met_wide["met_lat_r"])
    met_wide["met_lon"] = met_wide["met_lon_t"].fillna(met_wide["met_lon_r"])
    met_wide = met_wide[["site_id", "county_fips", "Date Local", "met_lat", "met_lon", "temp_c", "rh_pct"]].copy()
    return sp_wide, met_wide


def spatial_county_merge(
    pairs: pd.DataFrame,
    aux: pd.DataFrame,
    val_cols: list[str],
    lat_col: str,
    lon_col: str,
    prefix: str,
    max_km: float = 25.0,
) -> pd.DataFrame:
    """Merge auxiliary daily dataset onto collocated pairs:
      1. Exact same site_id + Date Local (dist = 0.0 km)
      2. Nearest same-county site on the same Date Local within max_km (25 km).
    """
    # Restrict aux to rows where at least one val_col is non-null
    aux_ok = aux.dropna(subset=val_cols, how="all").copy()

    # Step 1: exact site match
    exact = pairs[["site_id", "county_fips", "Date Local", "lat", "lon"]].drop_duplicates(
        ["site_id", "Date Local"]
    )
    m_exact = exact.merge(
        aux_ok[["site_id", "Date Local"] + val_cols],
        on=["site_id", "Date Local"],
        how="left",
    )
    has_exact = m_exact[val_cols].notna().all(axis=1)
    m_exact[f"{prefix}_dist_km"] = np.where(has_exact, 0.0, np.nan)
    exact_done = m_exact[has_exact].copy()

    # Step 2: unmatched -> nearest same-county site within max_km on same Date Local
    need = m_exact[~has_exact][["site_id", "county_fips", "Date Local", "lat", "lon"]].copy()
    aux_complete = aux_ok.dropna(subset=val_cols, how="any").copy()
    cand = need.merge(
        aux_complete[["county_fips", "Date Local", lat_col, lon_col] + val_cols],
        on=["county_fips", "Date Local"],
        how="inner",
    )
    if len(cand):
        cand[f"{prefix}_dist_km"] = haversine_km(
            cand["lat"].to_numpy(dtype=float),
            cand["lon"].to_numpy(dtype=float),
            cand[lat_col].to_numpy(dtype=float),
            cand[lon_col].to_numpy(dtype=float),
        )
        cand = cand[cand[f"{prefix}_dist_km"] <= max_km].copy()
        cand = cand.sort_values(["site_id", "Date Local", f"{prefix}_dist_km"]).drop_duplicates(
            ["site_id", "Date Local"]
        )
        near_done = cand[["site_id", "Date Local"] + val_cols + [f"{prefix}_dist_km"]].copy()
    else:
        near_done = pd.DataFrame(columns=["site_id", "Date Local"] + val_cols + [f"{prefix}_dist_km"])

    matched_all = pd.concat(
        [exact_done[["site_id", "Date Local"] + val_cols + [f"{prefix}_dist_km"]], near_done],
        ignore_index=True,
    ).drop_duplicates(["site_id", "Date Local"])
    return pairs.merge(matched_all, on=["site_id", "Date Local"], how="left")


def rooftop_appn_dv_lottery(col_df: pd.DataFrame, label: str, strict_4q3y: bool = False) -> tuple[dict[str, Any], pd.DataFrame]:
    """Compute 2023-2025 paired-day quarterly-weighted rooftop Design Values & 9.0 ug/m3 lottery."""
    sub = col_df[col_df["Year"].isin([2023, 2024, 2025])].copy()
    qm = (
        sub.groupby(["site_id", "county_fips", "state_fips", "Year", "Quarter"], as_index=False)
        .agg(q_frm=("frm", "mean"), q_fem=("fem", "mean"), q_n=("bias", "size"))
    )
    am = (
        qm.groupby(["site_id", "county_fips", "state_fips", "Year"], as_index=False)
        .agg(a_frm=("q_frm", "mean"), a_fem=("q_fem", "mean"), n_q=("Quarter", "nunique"), n_d=("q_n", "sum"))
    )
    if strict_4q3y:
        am = am[(am["n_q"] == 4) & (am["n_d"] >= 40)]
        min_yrs = 3
    else:
        am = am[(am["n_q"] >= 3) & (am["n_d"] >= 30)]
        min_yrs = 2
    sdv = (
        am.groupby(["site_id", "county_fips", "state_fips"], as_index=False)
        .agg(dv_frm=("a_frm", "mean"), dv_fem=("a_fem", "mean"), n_yrs=("Year", "nunique"), tot_pairs=("n_d", "sum"))
    )
    sdv = sdv[sdv["n_yrs"] >= min_yrs].copy()
    sdv["dv_frm_r"] = np.floor(sdv["dv_frm"] * 10.0 + 0.5 + 1e-9) / 10.0
    sdv["dv_fem_r"] = np.floor(sdv["dv_fem"] * 10.0 + 0.5 + 1e-9) / 10.0
    sdv["bias_dv"] = sdv["dv_fem"] - sdv["dv_frm"]
    sdv["region"] = sdv["state_fips"].map(REGION_MAP).fillna("OT")

    fem_only_na = int(((sdv["dv_fem_r"] >= 9.1) & (sdv["dv_frm_r"] <= 9.0)).sum())
    frm_only_na = int(((sdv["dv_frm_r"] >= 9.1) & (sdv["dv_fem_r"] <= 9.0)).sum())
    both_na = int(((sdv["dv_fem_r"] >= 9.1) & (sdv["dv_frm_r"] >= 9.1)).sum())
    both_att = int(((sdv["dv_fem_r"] <= 9.0) & (sdv["dv_frm_r"] <= 9.0)).sum())
    disc = fem_only_na + frm_only_na
    binom_p = float(stats.binomtest(fem_only_na, disc, 0.5).pvalue) if disc > 0 else 1.0
    t_stat, p_val = stats.ttest_1samp(sdv["bias_dv"], 0.0) if len(sdv) >= 2 else (math.nan, math.nan)

    summary = {
        "label": label,
        "strict_4q3y": strict_4q3y,
        "n_sites": len(sdv),
        "mean_dv_bias": float(sdv["bias_dv"].mean()),
        "se_dv_bias": float(sdv["bias_dv"].std(ddof=1) / math.sqrt(len(sdv))) if len(sdv) > 1 else math.nan,
        "median_dv_bias": float(sdv["bias_dv"].median()),
        "pct_positive": float(100.0 * (sdv["bias_dv"] > 0).mean()),
        "t_bias": float(t_stat),
        "p_bias": float(p_val),
        "fem_na_frm_att": fem_only_na,
        "frm_na_fem_att": frm_only_na,
        "odds_ratio_lottery": float(fem_only_na / frm_only_na) if frm_only_na > 0 else None,
        "both_na": both_na,
        "both_att": both_att,
        "binom_p": binom_p,
    }
    return summary, sdv


def run_zero_eiv_smoke_suite(col_df: pd.DataFrame, inst_label: str) -> dict[str, Any]:
    """Run all 3 strictly EIV-free smoke amplification tests (level bias & proportional log-ratio)
    with Site FE + Month FE (and Site FE + Year-Month FE sensitivity), Site & State CR1 + WCB.
    """
    out: dict[str, Any] = {}
    df = col_df[col_df["Year"].isin([2023, 2024, 2025])].copy()
    df["log_ok"] = (df["fem"] > 0.5) & (df["frm"] > 0.5)
    df["log_ratio"] = np.where(df["log_ok"], np.log(df["fem"].clip(lower=0.5) / df["frm"].clip(lower=0.5)), np.nan)

    # --- INSTRUMENT 1: Independent Other-Site Monitor in Same County-Day ---
    s1 = df[df["other_site_pm"].notna()].copy()
    s1["oth_15_25"] = ((s1["other_site_pm"] >= 15.0) & (s1["other_site_pm"] < 25.0)).astype(float)
    s1["oth_ge25"] = (s1["other_site_pm"] >= 25.0).astype(float)
    s1_log = s1[s1["log_ok"]].copy()

    out["inst1_other_site_level_site_cr1"] = ols_cr1(
        s1["bias"].to_numpy(),
        s1[["oth_15_25", "oth_ge25"]].to_numpy(),
        s1["site_id"].to_numpy(),
        [s1["site_id"].to_numpy(), s1["Month"].to_numpy()],
        ["oth_15_25", "oth_ge25"],
        wcb_var_idx=1,
        wcb_B=999,
    )
    out["inst1_other_site_level_state_cr1"] = ols_cr1(
        s1["bias"].to_numpy(),
        s1[["oth_15_25", "oth_ge25"]].to_numpy(),
        s1["state_fips"].to_numpy(),
        [s1["site_id"].to_numpy(), s1["Month"].to_numpy()],
        ["oth_15_25", "oth_ge25"],
        wcb_var_idx=1,
        wcb_B=999,
    )
    out["inst1_other_site_level_ym_fe"] = ols_cr1(
        s1["bias"].to_numpy(),
        s1[["oth_15_25", "oth_ge25"]].to_numpy(),
        s1["site_id"].to_numpy(),
        [s1["site_id"].to_numpy(), s1["ym"].to_numpy()],
        ["oth_15_25", "oth_ge25"],
        wcb_var_idx=1,
        wcb_B=499,
    )
    out["inst1_other_site_logratio_site_cr1"] = ols_cr1(
        s1_log["log_ratio"].to_numpy(),
        s1_log[["oth_15_25", "oth_ge25"]].to_numpy(),
        s1_log["site_id"].to_numpy(),
        [s1_log["site_id"].to_numpy(), s1_log["Month"].to_numpy()],
        ["oth_15_25", "oth_ge25"],
        wcb_var_idx=1,
        wcb_B=999,
    )
    out["inst1_other_site_logratio_state_cr1"] = ols_cr1(
        s1_log["log_ratio"].to_numpy(),
        s1_log[["oth_15_25", "oth_ge25"]].to_numpy(),
        s1_log["state_fips"].to_numpy(),
        [s1_log["site_id"].to_numpy(), s1_log["Month"].to_numpy()],
        ["oth_15_25", "oth_ge25"],
        wcb_var_idx=1,
        wcb_B=999,
    )
    # Non-T640 other-site sensitivity (pure FRM/BAM independent monitors)
    s1nt = df[df["other_site_pm_non_t640"].notna()].copy()
    s1nt["oth_15_25"] = ((s1nt["other_site_pm_non_t640"] >= 15.0) & (s1nt["other_site_pm_non_t640"] < 25.0)).astype(float)
    s1nt["oth_ge25"] = (s1nt["other_site_pm_non_t640"] >= 25.0).astype(float)
    out["inst1_other_site_non_t640_only_level"] = ols_cr1(
        s1nt["bias"].to_numpy(),
        s1nt[["oth_15_25", "oth_ge25"]].to_numpy(),
        s1nt["site_id"].to_numpy(),
        [s1nt["site_id"].to_numpy(), s1nt["Month"].to_numpy()],
        ["oth_15_25", "oth_ge25"],
        wcb_var_idx=1,
        wcb_B=499,
    )
    # Nonparametric bin means for plotting
    s1["oth_bin"] = pd.cut(s1["other_site_pm"], bins=[-10, 15, 25, 1000], labels=["<15", "15-25", ">=25"])
    out["inst1_bin_means"] = {
        str(k): {
            "count": len(g),
            "mean_bias": float(g["bias"].mean()),
            "median_bias": float(g["bias"].median()),
            "mean_log_ratio": float(g.loc[g["log_ok"], "log_ratio"].mean()) if g["log_ok"].any() else None,
            "mean_frm": float(g["frm"].mean()),
        }
        for k, g in s1.groupby("oth_bin", observed=False)
    }

    # --- INSTRUMENT 2: Bland-Altman Mean (FEM + FRM) / 2 Bins ---
    df["ba_mean"] = 0.5 * (df["fem"] + df["frm"])
    df["ba_15_25"] = ((df["ba_mean"] >= 15.0) & (df["ba_mean"] < 25.0)).astype(float)
    df["ba_ge25"] = (df["ba_mean"] >= 25.0).astype(float)
    df_log = df[df["log_ok"]].copy()
    out["inst2_bland_altman_level_site_cr1"] = ols_cr1(
        df["bias"].to_numpy(),
        df[["ba_15_25", "ba_ge25"]].to_numpy(),
        df["site_id"].to_numpy(),
        [df["site_id"].to_numpy(), df["Month"].to_numpy()],
        ["ba_15_25", "ba_ge25"],
        wcb_var_idx=1,
        wcb_B=999,
    )
    out["inst2_bland_altman_logratio_site_cr1"] = ols_cr1(
        df_log["log_ratio"].to_numpy(),
        df_log[["ba_15_25", "ba_ge25"]].to_numpy(),
        df_log["site_id"].to_numpy(),
        [df_log["site_id"].to_numpy(), df_log["Month"].to_numpy()],
        ["ba_15_25", "ba_ge25"],
        wcb_var_idx=1,
        wcb_B=999,
    )

    # --- INSTRUMENT 3: External Satellite NOAA HMS Wildfire Smoke Polygons ---
    df["hms_l"] = (df["hms_max_level"] == 1).astype(float)
    df["hms_m"] = (df["hms_max_level"] == 2).astype(float)
    df["hms_h"] = (df["hms_max_level"] == 3).astype(float)
    df_log = df[df["log_ok"]].copy()
    hms_cols = ["hms_l", "hms_m", "hms_h"]
    out["inst3_noaa_hms_level_site_cr1"] = ols_cr1(
        df["bias"].to_numpy(),
        df[hms_cols].to_numpy(),
        df["site_id"].to_numpy(),
        [df["site_id"].to_numpy(), df["Month"].to_numpy()],
        hms_cols,
        wcb_var_idx=2,
        wcb_B=999,
    )
    out["inst3_noaa_hms_level_state_cr1"] = ols_cr1(
        df["bias"].to_numpy(),
        df[hms_cols].to_numpy(),
        df["state_fips"].to_numpy(),
        [df["site_id"].to_numpy(), df["Month"].to_numpy()],
        hms_cols,
        wcb_var_idx=2,
        wcb_B=999,
    )
    out["inst3_noaa_hms_logratio_site_cr1"] = ols_cr1(
        df_log["log_ratio"].to_numpy(),
        df_log[hms_cols].to_numpy(),
        df_log["site_id"].to_numpy(),
        [df_log["site_id"].to_numpy(), df_log["Month"].to_numpy()],
        hms_cols,
        wcb_var_idx=2,
        wcb_B=999,
    )
    out["inst3_noaa_hms_logratio_state_cr1"] = ols_cr1(
        df_log["log_ratio"].to_numpy(),
        df_log[hms_cols].to_numpy(),
        df_log["state_fips"].to_numpy(),
        [df_log["site_id"].to_numpy(), df_log["Month"].to_numpy()],
        hms_cols,
        wcb_var_idx=2,
        wcb_B=999,
    )
    lbl_map = {0: "None", 1: "Light", 2: "Medium", 3: "Heavy"}
    out["inst3_hms_bin_means"] = {
        lbl_map[int(k)]: {
            "count": len(g),
            "mean_bias": float(g["bias"].mean()),
            "median_bias": float(g["bias"].median()),
            "mean_log_ratio": float(g.loc[g["log_ok"], "log_ratio"].mean()) if g["log_ok"].any() else None,
            "mean_frm": float(g["frm"].mean()),
        }
        for k, g in df.groupby("hms_max_level")
    }
    print(f"\n  [Zero-EIV Smoke Summary: {inst_label} (2023-2025, N={len(df):,})]", flush=True)
    c1 = out["inst1_other_site_level_site_cr1"]["coefs"]["oth_ge25"]
    c1l = out["inst1_other_site_logratio_site_cr1"]["coefs"]["oth_ge25"]
    c2 = out["inst2_bland_altman_level_site_cr1"]["coefs"]["ba_ge25"]
    c3 = out["inst3_noaa_hms_level_site_cr1"]["coefs"]["hms_h"]
    c3l = out["inst3_noaa_hms_logratio_site_cr1"]["coefs"]["hms_h"]
    print(
        f"    Inst1 Other-Site >=25: level={c1['beta']:+.3f} (t={c1['t_cr1']:+.2f}, p_WCB={out['inst1_other_site_level_site_cr1']['wcb']['p_wcb']:.3f}) | "
        f"log={c1l['beta']:+.4f} (t={c1l['t_cr1']:+.2f})",
        flush=True,
    )
    print(f"    Inst2 Bland-Altman >=25: level={c2['beta']:+.3f} (t={c2['t_cr1']:+.2f})", flush=True)
    print(
        f"    Inst3 NOAA HMS Heavy:  level={c3['beta']:+.3f} (t={c3['t_cr1']:+.2f}, p_WCB={out['inst3_noaa_hms_level_site_cr1']['wcb']['p_wcb']:.3f}) | "
        f"log={c3l['beta']:+.4f} (t={c3l['t_cr1']:+.2f})",
        flush=True,
    )
    return out


def run_speciation_met_mechanism(col_df: pd.DataFrame, inst_label: str) -> dict[str, Any]:
    """Decompose (FEM - FRM) and log(FEM / FRM) on EPA Speciation (NO3-, SO4^2-, OC, EC, Soil)
    and Meteorology (RH, TEMP) with Site FE + Month FE (full <25km match & exact 0km sensitivity).
    """
    out: dict[str, Any] = {}
    df = col_df[col_df["Year"].isin([2023, 2024, 2025])].copy()
    df["log_ok"] = (df["fem"] > 0.5) & (df["frm"] > 0.5)
    df["log_ratio"] = np.where(df["log_ok"], np.log(df["fem"].clip(lower=0.5) / df["frm"].clip(lower=0.5)), np.nan)
    df["rh_10"] = df["rh_pct"] / 10.0
    df["rh_high70"] = (df["rh_pct"] >= 70.0).astype(float)
    df["hms_heavy"] = (df["hms_max_level"] == 3).astype(float)
    df["no3_x_rh70"] = df["no3"] * df["rh_high70"]
    df["oc_x_hms_h"] = df["oc"] * df["hms_heavy"]

    # Match coverage diagnostics
    spec_ok = df[["no3", "so4", "oc", "ec"]].notna().all(axis=1)
    met_ok = df[["temp_c", "rh_pct"]].notna().all(axis=1)
    both_ok = spec_ok & met_ok
    out["match_diagnostics"] = {
        "total_collocated_pairs_2023_2025": len(df),
        "spec_matched_pairs": int(spec_ok.sum()),
        "spec_exact_rooftop_0km": int((spec_ok & (df["spec_dist_km"] == 0.0)).sum()),
        "spec_median_dist_km": float(df.loc[spec_ok, "spec_dist_km"].median()) if spec_ok.any() else math.nan,
        "met_matched_pairs": int(met_ok.sum()),
        "met_exact_rooftop_0km": int((met_ok & (df["met_dist_km"] == 0.0)).sum()),
        "spec_and_met_matched_pairs": int(both_ok.sum()),
        "spec_and_met_sites": int(df.loc[both_ok, "site_id"].nunique()),
    }

    # --- Model S4: Full-sample Meteorology + NOAA HMS (no speciation drop, huge N!) ---
    sm = df[met_ok].copy()
    sm["hms_l"] = (sm["hms_max_level"] == 1).astype(float)
    sm["hms_m"] = (sm["hms_max_level"] == 2).astype(float)
    sm["hms_h"] = (sm["hms_max_level"] == 3).astype(float)
    sm["rh_x_cold"] = sm["rh_10"] * (sm["temp_c"] < 5.0).astype(float)
    x_met = ["rh_10", "temp_c", "hms_l", "hms_m", "hms_h"]
    out["model_s4_met_hms_level"] = ols_cr1(
        sm["bias"].to_numpy(),
        sm[x_met].to_numpy(),
        sm["site_id"].to_numpy(),
        [sm["site_id"].to_numpy(), sm["Month"].to_numpy()],
        x_met,
        wcb_var_idx=0,
        wcb_B=999,
    )
    sm_l = sm[sm["log_ok"]].copy()
    out["model_s4_met_hms_logratio"] = ols_cr1(
        sm_l["log_ratio"].to_numpy(),
        sm_l[x_met].to_numpy(),
        sm_l["site_id"].to_numpy(),
        [sm_l["site_id"].to_numpy(), sm_l["Month"].to_numpy()],
        x_met,
        wcb_var_idx=0,
        wcb_B=999,
    )

    # --- Model S1: Core Aerosol Speciation + Meteorology (NO3-, SO4^2-, OC, EC, RH/10, TEMP_C) ---
    sb = df[both_ok].copy()
    x_s1 = ["no3", "so4", "oc", "ec", "rh_10", "temp_c"]
    out["model_s1_spec_met_level_site_cr1"] = ols_cr1(
        sb["bias"].to_numpy(),
        sb[x_s1].to_numpy(),
        sb["site_id"].to_numpy(),
        [sb["site_id"].to_numpy(), sb["Month"].to_numpy()],
        x_s1,
        wcb_var_idx=0,
        wcb_B=999,
    )
    out["model_s1_spec_met_level_state_cr1"] = ols_cr1(
        sb["bias"].to_numpy(),
        sb[x_s1].to_numpy(),
        sb["state_fips"].to_numpy(),
        [sb["site_id"].to_numpy(), sb["Month"].to_numpy()],
        x_s1,
        wcb_var_idx=0,
        wcb_B=999,
    )
    sb_l = sb[sb["log_ok"]].copy()
    out["model_s1_spec_met_logratio_site_cr1"] = ols_cr1(
        sb_l["log_ratio"].to_numpy(),
        sb_l[x_s1].to_numpy(),
        sb_l["site_id"].to_numpy(),
        [sb_l["site_id"].to_numpy(), sb_l["Month"].to_numpy()],
        x_s1,
        wcb_var_idx=0,
        wcb_B=999,
    )

    # Standardized 1-SD covariate regression (for clean comparability in Figure 3B!)
    sb_std = sb.copy()
    sd_map = {}
    for c in x_s1:
        sd = float(sb[c].std(ddof=1))
        sd_map[c] = sd
        sb_std[c] = (sb[c] - sb[c].mean()) / sd if sd > 0 else 0.0
    out["model_s1_covariate_sds"] = sd_map
    out["model_s1_standardized_level_site_cr1"] = ols_cr1(
        sb_std["bias"].to_numpy(),
        sb_std[x_s1].to_numpy(),
        sb_std["site_id"].to_numpy(),
        [sb_std["site_id"].to_numpy(), sb_std["Month"].to_numpy()],
        x_s1,
    )

    # --- Model S2: Physical Interactions (NO3 x RH>=70%, OC x HMS_Heavy) ---
    x_s2 = ["no3", "so4", "oc", "ec", "rh_10", "temp_c", "rh_high70", "no3_x_rh70", "hms_heavy", "oc_x_hms_h"]
    out["model_s2_interactions_level_site_cr1"] = ols_cr1(
        sb["bias"].to_numpy(),
        sb[x_s2].to_numpy(),
        sb["site_id"].to_numpy(),
        [sb["site_id"].to_numpy(), sb["Month"].to_numpy()],
        x_s2,
    )

    # --- Model S3: Strict Exact-Same-Rooftop Speciation (0 km only) Robustness ---
    sb_0 = sb[sb["spec_dist_km"] == 0.0].copy()
    if len(sb_0) >= 100 and sb_0["site_id"].nunique() >= 5:
        out["model_s3_exact_0km_spec_level"] = ols_cr1(
            sb_0["bias"].to_numpy(),
            sb_0[x_s1].to_numpy(),
            sb_0["site_id"].to_numpy(),
            [sb_0["site_id"].to_numpy(), sb_0["Month"].to_numpy()],
            x_s1,
        )

    # --- Speciation-only (without requiring met match, slightly larger N) + Soil ---
    ss = df[spec_ok & df["soil"].notna()].copy()
    if len(ss) >= 100:
        x_ss = ["no3", "so4", "oc", "ec", "soil"]
        out["model_s5_spec_plus_soil_level"] = ols_cr1(
            ss["bias"].to_numpy(),
            ss[x_ss].to_numpy(),
            ss["site_id"].to_numpy(),
            [ss["site_id"].to_numpy(), ss["Month"].to_numpy()],
            x_ss,
        )

    # Summary means by Region & Season for NO3, OC, RH to explain Midwest/Winter gradient!
    out["chem_means_by_region"] = {
        str(k): {
            "n": len(g),
            "bias": float(g["bias"].mean()),
            "no3": float(g["no3"].mean()),
            "so4": float(g["so4"].mean()),
            "oc": float(g["oc"].mean()),
            "rh_pct": float(g["rh_pct"].mean()),
            "temp_c": float(g["temp_c"].mean()),
        }
        for k, g in sb.groupby("region")
    }
    out["chem_means_by_season"] = {
        str(k): {
            "n": len(g),
            "bias": float(g["bias"].mean()),
            "no3": float(g["no3"].mean()),
            "so4": float(g["so4"].mean()),
            "oc": float(g["oc"].mean()),
            "rh_pct": float(g["rh_pct"].mean()),
            "temp_c": float(g["temp_c"].mean()),
        }
        for k, g in sb.groupby("season")
    }

    print(f"\n  [Speciation + Met Mechanism: {inst_label} (N={len(sb):,} pairs, G={sb['site_id'].nunique()} sites)]", flush=True)
    if "coefs" in out["model_s1_spec_met_level_site_cr1"]:
        for k, v in out["model_s1_spec_met_level_site_cr1"]["coefs"].items():
            print(f"    {k:8s}: beta={v['beta']:+.4f} (se={v['se_cr1']:.4f}, t={v['t_cr1']:+.2f}, p={v['p_cr1']:.4f})", flush=True)
    if "coefs" in out["model_s2_interactions_level_site_cr1"]:
        for k in ("no3", "no3_x_rh70", "oc", "oc_x_hms_h"):
            v = out["model_s2_interactions_level_site_cr1"]["coefs"][k]
            print(f"    [Int] {k:10s}: beta={v['beta']:+.4f} (t={v['t_cr1']:+.2f}, p={v['p_cr1']:.4f})", flush=True)
    return out


def run_unification_u1_exceedance_multiplier(col_df: pd.DataFrame, inst_label: str) -> dict[str, Any]:
    """Unification Test U1: Same-rooftop exceedance trigger multiplier (>35, >=25, >site p98)
    comparing FEM vs collocated FRM 2 meters away on identical days (All / HMS Any / HMS Heavy /
    Independent Other-Site >= 25), via exact paired McNemar binomial test + rooftop-day FE LPM.
    """
    df = col_df[col_df["Year"].isin([2023, 2024, 2025])].copy()
    # Compute each site's empirical FRM 98th percentile (requires >= 30 paired days)
    site_p98 = (
        df.groupby("site_id")["frm"]
        .agg(p98=lambda s: float(np.percentile(s, 98)), n="size")
        .reset_index()
    )
    site_p98 = site_p98[site_p98["n"] >= 30][["site_id", "p98"]]
    df = df.merge(site_p98, on="site_id", how="left")

    subsets = {
        "all_paired_days": df,
        "hms_any_smoke": df[df["hms_max_level"] >= 1],
        "hms_medium_or_heavy": df[df["hms_max_level"] >= 2],
        "hms_heavy_smoke": df[df["hms_max_level"] == 3],
        "other_site_ge25": df[df["other_site_pm"] >= 25.0],
    }

    out: dict[str, Any] = {}
    for sname, sub in subsets.items():
        if len(sub) < 20:
            out[sname] = {"n_days": len(sub), "skipped": True}
            continue
        rec: dict[str, Any] = {"n_days": len(sub), "n_sites": int(sub["site_id"].nunique())}
        for thresh_name, fem_hit, frm_hit in [
            ("gt_35_naaqs24h", sub["fem"] > 35.0, sub["frm"] > 35.0),
            ("ge_25_smoke", sub["fem"] >= 25.0, sub["frm"] >= 25.0),
            ("gt_site_p98", sub["fem"] > sub["p98"], sub["frm"] > sub["p98"]),
        ]:
            valid = fem_hit.notna() & frm_hit.notna()
            if thresh_name == "gt_site_p98":
                valid = valid & sub["p98"].notna()
            fh = fem_hit[valid].to_numpy(dtype=bool)
            gh = frm_hit[valid].to_numpy(dtype=bool)
            n_v = len(fh)
            fem_n = int(fh.sum())
            frm_n = int(gh.sum())
            fem_only = int((fh & (~gh)).sum())
            frm_only = int(((~fh) & gh).sum())
            both = int((fh & gh).sum())
            disc = fem_only + frm_only
            mcnemar_p = float(stats.binomtest(fem_only, disc, 0.5).pvalue) if disc > 0 else 1.0
            ratio = float(fem_n / frm_n) if frm_n > 0 else (float("inf") if fem_n > 0 else 1.0)
            # Paired difference (equivalent to rooftop-day FE LPM: exceed_ij ~ is_fem + site_date FE)
            diff_arr = fh.astype(float) - gh.astype(float)
            s_sub = sub.loc[valid, "site_id"].to_numpy()
            lpm = ols_cr1(
                diff_arr,
                np.ones((n_v, 1), dtype=float),
                s_sub,
                None,
                ["fem_minus_frm"],
                wcb_var_idx=0,
                wcb_B=499,
            )
            c = lpm.get("coefs", {}).get("fem_minus_frm", {})
            rec[thresh_name] = {
                "n_valid_days": n_v,
                "fem_exceed_n": fem_n,
                "frm_exceed_n": frm_n,
                "fem_rate_pct": float(100.0 * fem_n / max(n_v, 1)),
                "frm_rate_pct": float(100.0 * frm_n / max(n_v, 1)),
                "trigger_multiplier_ratio": ratio if math.isfinite(ratio) else None,
                "fem_only_discordant": fem_only,
                "frm_only_discordant": frm_only,
                "both_exceed": both,
                "mcnemar_exact_p": mcnemar_p,
                "paired_diff_pp": float(100.0 * c["beta"]) if "beta" in c else None,
                "se_site_cr1_pp": float(100.0 * c["se_cr1"]) if "se_cr1" in c else None,
                "t_site_cr1": float(c["t_cr1"]) if "t_cr1" in c else None,
                "p_site_cr1": float(c["p_cr1"]) if "p_cr1" in c else None,
                "p_wcb": float(lpm["wcb"]["p_wcb"]) if "wcb" in lpm else None,
            }
        out[sname] = rec

    print(f"\n  [Unification Test U1 Exceedance Multiplier: {inst_label}]", flush=True)
    for sname in ("all_paired_days", "hms_heavy_smoke", "other_site_ge25"):
        if sname in out and "gt_35_naaqs24h" in out[sname]:
            g = out[sname]["gt_35_naaqs24h"]
            print(
                f"    {sname:18s} >35 ug/m3: FEM={g['fem_exceed_n']} ({g['fem_rate_pct']:.2f}%) vs "
                f"FRM={g['frm_exceed_n']} ({g['frm_rate_pct']:.2f}%) | disc={g['fem_only_discordant']} vs {g['frm_only_discordant']} "
                f"(McNemar p={g['mcnemar_exact_p']:.2e}, diff={g['paired_diff_pp']:+.2f} pp, t={g['t_site_cr1']:+.2f})",
                flush=True,
            )
    return out


def main() -> int:
    print("=== STEP 02 (PILLAR 2 + U1): COLLOCATED OPTICAL PHYSICS, ZERO-EIV SMOKE & SPECIATION ===", flush=True)
    daily = load_daily_2023_2026()

    # Load NOAA HMS daily smoke polygons (2018-2025)
    hms = pd.read_parquet(PROC_DIR / "monitor_hms_daily_2018_2025.parquet")
    hms_2325 = hms[hms["date"].str.slice(0, 4).isin(["2023", "2024", "2025"])].rename(
        columns={"date": "Date Local"}
    )

    # Independent other-site county-day PM2.5
    other_pm = build_other_site_county_pm(daily)

    # Load EPA Speciation & Meteorology (2023-2025)
    print("  Loading EPA Speciation (2023-2025) and Meteorology (TEMP, RH 2023-2025)...", flush=True)
    spec_wide, met_wide = load_speciation_and_met_2023_2025()

    # Build collocated daily pairs for T640_FW (636/638) vs FRM and BAM (170/209) vs FRM
    frm_d = (
        daily[daily["inst"] == "FRM"]
        .groupby(["site_id", "county_fips", "state_fips", "Date Local", "Year", "Month", "Quarter", "ym"], as_index=False)
        .agg(frm=("Arithmetic Mean", "mean"), lat=("lat", "first"), lon=("lon", "first"))
    )
    t640_d = (
        daily[daily["inst"] == "T640_FW"]
        .groupby(["site_id", "Date Local", "Year"], as_index=False)
        .agg(fem=("Arithmetic Mean", "mean"))
    )
    # Also stitched aligned T640 (636/638 + 736/738, prioritizing 636/638 on transition days) for strict 4q x 3y 2023-2025!
    t640_aln_raw = daily[daily["inst"].isin(["T640_FW", "T640_RETRO"])].copy()
    t640_aln_raw["prio"] = np.where(t640_aln_raw["inst"] == "T640_FW", 1, 2)
    min_p = t640_aln_raw.groupby(["site_id", "Date Local"])["prio"].transform("min")
    t640_aln_d = (
        t640_aln_raw[t640_aln_raw["prio"] == min_p]
        .groupby(["site_id", "Date Local", "Year"], as_index=False)
        .agg(fem=("Arithmetic Mean", "mean"))
    )
    bam_d = (
        daily[daily["inst"] == "BAM"]
        .groupby(["site_id", "Date Local", "Year"], as_index=False)
        .agg(fem=("Arithmetic Mean", "mean"))
    )

    def enrich_pairs(fem_df: pd.DataFrame) -> pd.DataFrame:
        p = fem_df.merge(frm_d, on=["site_id", "Date Local", "Year"], how="inner")
        p["bias"] = p["fem"] - p["frm"]
        p["region"] = p["state_fips"].map(REGION_MAP).fillna("OT")
        p["season"] = np.where(
            p["Month"].isin([12, 1, 2]),
            "DJF",
            np.where(p["Month"].isin([3, 4, 5]), "MAM", np.where(p["Month"].isin([6, 7, 8]), "JJA", "SON")),
        )
        p = p.merge(other_pm, on=["site_id", "Date Local"], how="left")
        p = p.merge(
            hms_2325[["site_id", "Date Local", "hms_light", "hms_medium", "hms_heavy", "hms_max_level"]],
            on=["site_id", "Date Local"],
            how="left",
        )
        for c in ("hms_light", "hms_medium", "hms_heavy", "hms_max_level"):
            p[c] = p[c].fillna(0).astype(int)
        # Spatial county merge for Core-4 Speciation (no3, so4, oc, ec) WITHOUT requiring soil (88348),
        # preserving CSN urban rooftops that lack 88348; merge soil separately for Model S5!
        spec_core = spec_wide[["site_id", "county_fips", "Date Local", "spec_lat", "spec_lon", "no3", "so4", "oc", "ec"]].copy()
        spec_soil = spec_wide[["site_id", "county_fips", "Date Local", "spec_lat", "spec_lon", "soil"]].copy()
        p = spatial_county_merge(p, spec_core, ["no3", "so4", "oc", "ec"], "spec_lat", "spec_lon", "spec", max_km=25.0)
        p = spatial_county_merge(p, spec_soil, ["soil"], "spec_lat", "spec_lon", "soil", max_km=25.0)
        p = spatial_county_merge(p, met_wide, ["temp_c", "rh_pct"], "met_lat", "met_lon", "met", max_km=25.0)
        return p

    print("  Building & enriching collocated T640_FW-FRM and BAM-FRM daily pairs...", flush=True)
    col_t640 = enrich_pairs(t640_d)
    col_bam = enrich_pairs(bam_d)

    # Save enriched collocated pairs for figures & verification
    col_t640.to_parquet(PROC_DIR / "collocated_t640_fw_frm_2023_2026.parquet", index=False)
    col_bam.to_parquet(PROC_DIR / "collocated_bam_frm_2023_2026.parquet", index=False)

    # 1. Exact Sample Counts (2023-2025 vs 2023-May 2026) + Regional/Seasonal Gradients with Site-Clustered CR1 CIs
    def sample_and_gradient_summary(col_df: pd.DataFrame) -> dict[str, Any]:
        s2325 = col_df[col_df["Year"].isin([2023, 2024, 2025])]
        s_all = col_df

        def grp_cr1(sub_df: pd.DataFrame, gcol: str) -> dict[str, Any]:
            res = {}
            for k, g in sub_df.groupby(gcol):
                if str(k) == "OT" or g["site_id"].nunique() < 2:
                    continue
                r = ols_cr1(
                    g["bias"].to_numpy(),
                    np.ones((len(g), 1), dtype=float),
                    g["site_id"].to_numpy(),
                    None,
                    ["mean_bias"],
                )
                c = r.get("coefs", {}).get("mean_bias", {})
                res[str(k)] = {
                    "n_pairs": len(g),
                    "n_sites": int(g["site_id"].nunique()),
                    "mean_bias": float(g["bias"].mean()),
                    "median_bias": float(g["bias"].median()),
                    "se_site_cr1": float(c["se_cr1"]) if "se_cr1" in c else None,
                    "t_site_cr1": float(c["t_cr1"]) if "t_cr1" in c else None,
                    "p_site_cr1": float(c["p_cr1"]) if "p_cr1" in c else None,
                }
            return res

        return {
            "sample_2023_2025": {
                "n_pairs": len(s2325),
                "n_sites": int(s2325["site_id"].nunique()),
                "mean_bias": float(s2325["bias"].mean()),
                "median_bias": float(s2325["bias"].median()),
                "date_range": [str(s2325["Date Local"].min()), str(s2325["Date Local"].max())],
            },
            "sample_2023_may2026": {
                "n_pairs": len(s_all),
                "n_sites": int(s_all["site_id"].nunique()),
                "mean_bias": float(s_all["bias"].mean()),
                "median_bias": float(s_all["bias"].median()),
                "date_range": [str(s_all["Date Local"].min()), str(s_all["Date Local"].max())],
            },
            "by_region_2023_2025": grp_cr1(s2325, "region"),
            "by_season_2023_2025": grp_cr1(s2325, "season"),
            "by_region_2023_2026": grp_cr1(s_all, "region"),
            "by_season_2023_2026": grp_cr1(s_all, "season"),
        }

    t640_grad = sample_and_gradient_summary(col_t640)
    bam_grad = sample_and_gradient_summary(col_bam)
    print(
        f"  T640_FW pairs: 2023-2025 = {t640_grad['sample_2023_2025']['n_pairs']:,} ({t640_grad['sample_2023_2025']['n_sites']} sites), "
        f"2023-May26 = {t640_grad['sample_2023_may2026']['n_pairs']:,} ({t640_grad['sample_2023_may2026']['n_sites']} sites)",
        flush=True,
    )
    print(
        f"  BAM pairs:     2023-2025 = {bam_grad['sample_2023_2025']['n_pairs']:,} ({bam_grad['sample_2023_2025']['n_sites']} sites), "
        f"2023-May26 = {bam_grad['sample_2023_may2026']['n_pairs']:,} ({bam_grad['sample_2023_may2026']['n_sites']} sites)",
        flush=True,
    )

    # 2. Same-Rooftop 2023-2025 App. N Paired-Day DV Lottery (Pure T640_FW & Stitched Aligned T640 strict 4q x 3y!)
    col_t640_aln = t640_aln_d.merge(frm_d, on=["site_id", "Date Local", "Year"], how="inner")
    col_t640_aln["bias"] = col_t640_aln["fem"] - col_t640_aln["frm"]
    rt_t640, sdv_t640 = rooftop_appn_dv_lottery(col_t640, "T640_FW_vs_FRM", strict_4q3y=False)
    rt_t640_strict, _ = rooftop_appn_dv_lottery(col_t640_aln, "T640_ALN_stitched_strict_4q3y", strict_4q3y=True)
    rt_bam, sdv_bam = rooftop_appn_dv_lottery(col_bam, "BAM_vs_FRM", strict_4q3y=False)
    sdv_t640.to_parquet(PROC_DIR / "rooftop_dv_t640_2023_2025.parquet", index=False)
    sdv_bam.to_parquet(PROC_DIR / "rooftop_dv_bam_2023_2025.parquet", index=False)
    print(
        f"  Rooftop DV Lottery (T640_FW, N={rt_t640['n_sites']}): bias={rt_t640['mean_dv_bias']:+.3f} "
        f"(t={rt_t640['t_bias']:+.2f}, p={rt_t640['p_bias']:.2e}) | "
        f"T640>=9.1 & FRM<=9.0: {rt_t640['fem_na_frm_att']} vs {rt_t640['frm_na_fem_att']} "
        f"(binom p={rt_t640['binom_p']:.2e})",
        flush=True,
    )
    print(
        f"  Rooftop DV Lottery (Stitched T640_ALN Strict 4q x 3y, N={rt_t640_strict['n_sites']}): "
        f"bias={rt_t640_strict['mean_dv_bias']:+.3f} (t={rt_t640_strict['t_bias']:+.2f}, p={rt_t640_strict['p_bias']:.2e}) | "
        f"T640>=9.1 & FRM<=9.0: {rt_t640_strict['fem_na_frm_att']} vs {rt_t640_strict['frm_na_fem_att']} "
        f"(binom p={rt_t640_strict['binom_p']:.2e})",
        flush=True,
    )

    # 3. Strictly Zero-EIV Smoke Amplification Suite (3 independent instruments)
    smoke_t640 = run_zero_eiv_smoke_suite(col_t640, "T640_FW")
    smoke_bam = run_zero_eiv_smoke_suite(col_bam, "BAM")

    # 4. Aerosol Speciation (NO3-, SO4^2-, OC, EC) & RH/Temp Mechanism
    spec_t640 = run_speciation_met_mechanism(col_t640, "T640_FW")
    spec_bam = run_speciation_met_mechanism(col_bam, "BAM")

    # 5. Unification Test U1: Same-Rooftop Daily Exceedance Trigger Multiplier
    u1_t640 = run_unification_u1_exceedance_multiplier(col_t640, "T640_FW")
    u1_bam = run_unification_u1_exceedance_multiplier(col_bam, "BAM")

    receipt = {
        "method_code_audit": {
            "t640_fw_method_codes": sorted(daily.loc[daily["inst"] == "T640_FW", "method_code"].unique().tolist()),
            "bam_method_codes": sorted(daily.loc[daily["inst"] == "BAM", "method_code"].unique().tolist()),
            "frm_method_codes_count": int(daily.loc[daily["inst"] == "FRM", "method_code"].nunique()),
        },
        "sample_and_gradients": {"t640_fw": t640_grad, "bam": bam_grad},
        "rooftop_dv_lottery_2023_2025": {
            "t640_fw": rt_t640,
            "t640_fw_strict_4q3y": rt_t640_strict,
            "bam": rt_bam,
        },
        "zero_eiv_smoke_amplification": {"t640_fw": smoke_t640, "bam": smoke_bam},
        "speciation_and_meteorology": {"t640_fw": spec_t640, "bam": spec_bam},
        "unification_u1_exceedance_multiplier": {"t640_fw": u1_t640, "bam": u1_bam},
    }
    sha = save_json_lf(RES_DIR / "02_collocated_physics_speciation.json", receipt)
    print(f"\n[DONE STEP 02] Saved results/02_collocated_physics_speciation.json (SHA-256 LF: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
