"""Comprehensive automated verification suite for D4 v4 (Nature Water submission-ready revision)."""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from pypdf import PdfReader

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
PROC_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
FIG_DIR = BASE_DIR / "figures"

KNOWN_FORENSIC_EXCLUDED = {
    "0212880025", "03220510", "421401121480900", "03036000",
    "02292900", "02266495", "02079500", "03431091", "05406479",
    "02110704", "01477050", "02110701", "02135060",
}


def _load_module(script_name: str):
    path = BASE_DIR / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# 1. Mathematical, Solar Geometry, Kaplan-Meier & Episode Unit Tests
# ---------------------------------------------------------------------------
def test_solar_boundaries_and_equinox_solstice_symmetry() -> None:
    mod11 = _load_module("11_loro_and_sensitivity_analysis.py")
    sr_eq, ss_eq = mod11.solar_boundaries(40.0, pd.Timestamp("2023-03-21"))
    assert 340.0 < sr_eq < 380.0
    assert 1060.0 < ss_eq < 1100.0
    # Higher northern latitude in June -> earlier sunrise, later sunset
    sr_28, ss_28 = mod11.solar_boundaries(28.0, pd.Timestamp("2023-06-21"))
    sr_52, ss_52 = mod11.solar_boundaries(52.0, pd.Timestamp("2023-06-21"))
    assert sr_52 < sr_28 < 330.0
    assert ss_52 > ss_28 > 1110.0


def test_kaplan_meier_and_distinct_episode_grouping_unit() -> None:
    mod11 = _load_module("11_loro_and_sensitivity_analysis.py")
    mod12 = _load_module("12_operational_protocol_decision_analysis.py")

    # Simple KM sanity: 4 subjects, uncensored events at 2, 4, 6, 8 h -> median = 4.0 h
    km = mod11.kaplan_meier_quantiles(np.array([2.0, 4.0, 6.0, 8.0]), np.array([1, 1, 1, 1]))
    assert km["median_hr"] == 4.0
    assert km["censored_pct"] == 0.0

    # Right-censored subjects at 2, 4 h with no events -> survival stays 100%, median is None
    km_c = mod11.kaplan_meier_quantiles(np.array([2.0, 4.0, 6.0]), np.array([0, 0, 0]))
    assert km_c["median_hr"] is None
    assert km_c["surv_at_6h_pct"] == 100.0

    # Distinct episode grouping: consecutive days (10,11,12) = ep 1; gap to (15) = ep 2; (16) = ep 2
    days = np.array([10, 11, 12, 13, 15, 16])
    mask = np.array([True, True, True, False, True, True])
    ids = mod12.assign_distinct_episode_ids(days, mask)
    np.testing.assert_array_equal(ids, np.array([1, 1, 1, 0, 2, 2]))


def test_benson_krause_and_fwl_econometric_unit_guards() -> None:
    mod5 = _load_module("05_econometric_hydrologic_suite.py")
    temps = np.array([0.0, 10.0, 20.0, 30.0])
    calc = mod5.benson_krause_do_sat_1atm(temps)
    np.testing.assert_allclose(calc, np.array([14.621, 11.288, 9.092, 7.559]), atol=0.015)

    rng = np.random.default_rng(42)
    n = 360
    ym = np.repeat([f"2021-{m:02d}" for m in range(5, 11)], n // 6)
    temp = rng.normal(22.0, 3.0, n)
    log_q = rng.normal(6.0, 0.8, n)
    y = -0.22 * temp + 0.12 * log_q + rng.normal(0.0, 0.2, n)
    df = pd.DataFrame({"ym": ym, "temp": temp, "log_q": log_q, "y": y})
    fwl_res = mod5.fit_within_ym_full_betas(df, ["y"], ["temp", "log_q"], min_days=100)
    assert fwl_res is not None
    X_sm = pd.concat([df[["temp", "log_q"]], pd.get_dummies(df["ym"], dtype=float)], axis=1)
    sm_fit = sm.OLS(df["y"], X_sm).fit()
    np.testing.assert_allclose(fwl_res["y"], sm_fit.params[["temp", "log_q"]].values, atol=1e-10)


# ---------------------------------------------------------------------------
# 2. Data Hygiene & Screened Network Integrity
# ---------------------------------------------------------------------------
def test_screened_networks_free_of_forensic_dams_and_salinity() -> None:
    meta = pd.read_csv(PROC_DIR / "conus_valid_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
    iv_meta = pd.read_csv(PROC_DIR / "conus_iv_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
    assert len(meta) == 397
    assert len(iv_meta) == 139
    assert (meta["site_tp_cd"] == "ST").all()
    assert (meta["is_brackish_spcond_gt5000"] == 0).all()
    for df_chk in (meta, iv_meta):
        assert not KNOWN_FORENSIC_EXCLUDED.intersection(set(df_chk["site_no"].str.strip()))


# ---------------------------------------------------------------------------
# 3. v4 Core P0/P1 Scientific Receipts & Exact Referee Benchmark Verification
# ---------------------------------------------------------------------------
def test_p0_1_loro_primary_matches_exact_referee_benchmark_and_eliminates_circularity() -> None:
    r11 = json.loads((RES_DIR / "11_loro_and_sensitivity.json").read_text(encoding="utf-8"))
    us = r11["loro_primary"]["USGS"]
    uk = r11["loro_primary"]["EA"]
    assert us["n_sites"] == 139 and us["n_nights"] == 87_785
    assert uk["n_sites"] == 65 and uk["n_nights"] == 27_635

    us5, uk5 = us["thresholds"]["5"], uk["thresholds"]["5"]
    # Exact reproduction of reviewer's independent UTC LORO verification:
    assert us5["shared_n_ref_pos"] == 8499 and us5["loro_n_ref_pos"] == 8462
    assert us5["shared_minus_loro_dropped_nights"] == 37
    assert abs(us5["loro_dawn_minus_afternoon_95_pp"][0] - 49.47) < 0.02

    assert uk5["shared_n_ref_pos"] == 2472 and uk5["loro_n_ref_pos"] == 2360
    assert uk5["shared_minus_loro_dropped_nights"] == 112
    assert abs(uk5["loro_dawn_minus_afternoon_95_pp"][0] - 35.13) < 0.02

    # Transparent non-zero LORO pre-dawn reference-negative alarm rates (no circular zero!)
    assert us5["loro_schedules"]["predawn"]["ref_neg_alarms"] == 37
    assert uk5["loro_schedules"]["predawn"]["ref_neg_alarms"] == 112
    assert us5["loro_schedules"]["predawn"]["ref_neg_alarm_95_pct"][0] > 0.0
    assert uk5["loro_schedules"]["predawn"]["ref_neg_alarm_95_pct"][0] > 0.0

    # Persistence, sensor tolerance, independent probe noise, and out-of-sample holdout robustness
    assert us5["persistence_sensitivity"]["actionable_ge2h"]["dawn_minus_afternoon_95_pp"][0] > 50.0
    assert uk5["persistence_sensitivity"]["actionable_ge2h"]["dawn_minus_afternoon_95_pp"][0] > 35.0
    assert us5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_mean_pp"] > 45.0
    assert uk5["independent_probe_noise_mc"]["sigma_0p20"]["dawn_minus_afternoon_mean_pp"] > 30.0

    ho = r11["holdout_validation"]
    assert ho["USGS"]["leave_one_region_out"]["oos_gain_95_pp"][0] > 48.0
    assert ho["EA"]["leave_one_region_out"]["oos_gain_95_pp"][0] > 33.0
    assert ho["cross_atlantic_transfer"]["USGS_to_EA"]["test_gain_95_pp"][0] > 34.0
    assert ho["cross_atlantic_transfer"]["EA_to_USGS"]["test_gain_95_pp"][0] > 48.0

    # Real WQP independent co-located field-meter validation
    wqp = r11["real_wqp_grab_audit"]
    assert wqp["available"] is True
    assert wqp["conus397_2015_2024_clock"]["n_visits"] > 9_500
    assert wqp["independent_colocated_validation"]["n_paired_readings_le30min"] > 1_000
    assert wqp["independent_colocated_validation"]["pearson_r"] > 0.94
    assert wqp["actual_agency_visit_detection"]["lt5_grab_missed_pct"] > 50.0


def test_p0_2_equal_budget_operational_protocol_decision_frontier() -> None:
    r12 = json.loads((RES_DIR / "12_operational_protocol_decision.json").read_text(encoding="utf-8"))
    for net in ("USGS", "EA"):
        blk = r12["networks"][net]
        fr = blk["decision_breakeven_frontiers"]
        # Breakeven night multiplier vs empirical WQP clock is below realistic 1.75x surcharge
        assert 1.2 < fr["predawn_breakeven_m_vs_wqp_clock"] < 1.75

        b24 = blk["equal_budget_simulation_5mg_2h"]["equal_dollar_budget"]["budget_24_dayeq"]
        g175 = b24["grab_by_night_multiplier"]["m_1p75"]
        h40 = b24["hybrid_sonde_by_cost"]["k_40"]

        # First-light daylight beats dark pre-dawn at m=1.75x on distinct episodes/budget AND site discovery
        assert g175["first_light_sr_p30"]["distinct_episodes_per_100_dayeq"] > g175["predawn_sr_m30"]["distinct_episodes_per_100_dayeq"]
        assert g175["first_light_sr_p30"]["impaired_sy_flagged_pct"] > g175["predawn_sr_m30"]["impaired_sy_flagged_pct"]

        # Top-20% out-of-sample Year-1 sonde hybrid + first-light dominates ALL grab protocols (>3x distinct episodes!)
        hyb = h40["y1_daytime_screening_top20pct_plus_firstlight"]
        wqp = g175["empirical_wqp_clock"]
        assert hyb["distinct_episodes_per_100_dayeq"] > 3.0 * wqp["distinct_episodes_per_100_dayeq"]
        assert hyb["cost_usd_per_distinct_episode"] < 0.35 * wqp["cost_usd_per_distinct_episode"]
        assert hyb["impaired_sy_flagged_pct"] > g175["first_light_sr_p30"]["impaired_sy_flagged_pct"]

        # Continuous sondes provide genuine positive pre-nadir lead time on episodic <24h events
        sonde_lt = blk["primary_actionable_5mg_2h_visit_level"]["continuous_sonde_benchmark"]["episodic_lt24h_lead"]
        assert sonde_lt["median_lead_nadir_hr"] >= 3.0
        assert sonde_lt["pct_before_nadir"] > 90.0


def test_p1_3_coverage_attrition_downsampling_and_censoring() -> None:
    r11 = json.loads((RES_DIR / "11_loro_and_sensitivity.json").read_text(encoding="utf-8"))
    # Coverage entry rates (~94% US, ~82% England)
    assert 92.0 < r11["coverage_attrition"]["USGS"]["common_support_entry_pct"] < 96.0
    assert 80.0 < r11["coverage_attrition"]["EA"]["common_support_entry_pct"] < 85.0

    # Censoring check: exact 1,246/8,499 closed in US; full continuous median >> naive closed median
    cd_us = r11["loro_primary"]["USGS"]["thresholds"]["5"]["censoring_and_duration"]
    cd_uk = r11["loro_primary"]["EA"]["thresholds"]["5"]["censoring_and_duration"]
    assert cd_us["both_closed_n"] == 1246
    assert cd_us["full_continuous_median_iqr_hr"][1] > 5.0 * cd_us["both_closed_median_lo_hi_hr"][1]
    assert cd_uk["full_continuous_median_iqr_hr"][1] > 5.0 * cd_uk["both_closed_median_lo_hi_hr"][1]

    # Cadence downsampling: 15 -> 30 -> 60 min preserves US LORO gain while mechanically increasing ref-neg alarms
    us_cad = r11["cadence_downsampling"]["USGS"]["cadences"]
    assert us_cad["15min"]["loro_dawn_minus_afternoon_95_pp"][0] > 48.0
    assert us_cad["60min"]["loro_dawn_minus_afternoon_95_pp"][0] > 48.0
    assert us_cad["60min"]["predawn_ref_neg_alarm_pct"] > 5.0 * us_cad["15min"]["predawn_ref_neg_alarm_pct"]


# ---------------------------------------------------------------------------
# 4. Zero-NaN Tables, Manuscript Parity, Authorship, Crossref DOIs, PDF Zero-Leaks & SHA-256
# ---------------------------------------------------------------------------
def test_all_v4_and_archived_tables_zero_nans() -> None:
    v4_tables = [
        "table1_nw_loro_cross_network.csv",
        "table2_nw_robustness_holdout_cadence.csv",
        "table3_nw_equal_budget_protocols.csv",
        "table_s1_station_coverage_attrition.csv",
        "table_s2_coverage_by_cadence_month.csv",
        "table_s3_censoring_km_duration.csv",
        "table_s4_cost_sensitivity_grid.csv",
    ]
    for fn in v4_tables:
        p = TBL_DIR / fn
        assert p.exists(), f"Missing table: {fn}"
        df = pd.read_csv(p)
        assert len(df) > 0
        assert int(df.isna().sum().sum()) == 0, f"NaNs found in {fn}"


def test_manuscript_authorship_parity_and_crossref_verified_dois() -> None:
    md = (BASE_DIR / "manuscript_d4_boost.md").read_text(encoding="utf-8")
    r11 = json.loads((RES_DIR / "11_loro_and_sensitivity.json").read_text(encoding="utf-8"))
    r12 = json.loads((RES_DIR / "12_operational_protocol_decision.json").read_text(encoding="utf-8"))

    # Exact required authorship block and zero leaked internal metadata
    assert "Zijian Zeng" in md
    assert "Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA" in md
    assert "zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my" in md
    for forbidden in ("Target Venue", "Target Journal", "Target Format", "Track A", "Track B", "Manuscript ID"):
        assert forbidden not in md, f"Forbidden metadata leaked in manuscript: {forbidden}"

    # Programmatic parity check of key LORO and Equal-Budget headline numbers
    us_gain = f"{r11['loro_primary']['USGS']['thresholds']['5']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f}"
    uk_gain = f"{r11['loro_primary']['EA']['thresholds']['5']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f}"
    us_hyb = f"{r12['networks']['USGS']['equal_budget_simulation_5mg_2h']['equal_dollar_budget']['budget_24_dayeq']['hybrid_sonde_by_cost']['k_40']['y1_daytime_screening_top20pct_plus_firstlight']['distinct_episodes_per_100_dayeq']:.2f}"
    assert us_gain in md and uk_gain in md and us_hyb in md

    # Every cited DOI in manuscript exists in Crossref-verified archive
    refs = json.loads((PROC_DIR / "verified_references.json").read_text(encoding="utf-8"))
    verified_dois = {str(v["doi"]).lower() for v in refs.values() if v.get("doi")}
    cited_dois = {d.lower().rstrip(".,);") for d in re.findall(r"https://doi\.org/([^\s)]+)", md)}
    assert len(cited_dois) >= 14
    assert not (cited_dois - verified_dois), f"Unverified DOIs cited: {cited_dois - verified_dois}"
    for req_doi in ("10.1016/j.scitotenv.2024.176626", "10.1002/lol2.10297", "10.1038/s41558-025-02483-y", "10.1038/s41561-026-02024-y"):
        assert req_doi in cited_dois


def test_v4_figures_pdfs_zero_leaks_and_sha256_manifest() -> None:
    for stem in (
        "fig1_nw_monitoring_clock_and_coverage",
        "fig2_nw_loro_cross_network_validation",
        "fig3_nw_censoring_duration_and_leadtime",
        "fig4_nw_equal_budget_protocol_frontier",
    ):
        assert (FIG_DIR / f"{stem}.png").stat().st_size > 60_000
        assert (FIG_DIR / f"{stem}.pdf").stat().st_size > 15_000

    for pdf_name, min_pages in [
        ("manuscript_d4_boost.pdf", 10),
        ("manuscript_d4_nature_water.pdf", 10),
        ("supplementary_d4_nature_water.pdf", 6),
    ]:
        pdf_p = BASE_DIR / pdf_name
        assert pdf_p.exists() and pdf_p.stat().st_size > 200_000
        reader = PdfReader(str(pdf_p))
        assert len(reader.pages) >= min_pages
        txt = "\n".join((p.extract_text() or "") for p in reader.pages)
        for pat in (r"\\[A-Za-z]+", r"\$\$", r"\*\*", r"\|---", r"&amp;", r"Track\s+[AB]", r"Target\s+Journal"):
            assert not re.search(pat, txt), f"Leaked token {pat} in {pdf_name}"

    manifest = json.loads((BASE_DIR / "SHA256SUMS.json").read_text(encoding="utf-8"))
    assert manifest["n_files_hashed"] >= 35
    for rel, info in manifest["files"].items():
        fp = BASE_DIR / rel
        assert fp.exists(), f"Missing hashed file: {rel}"
        assert hashlib.sha256(fp.read_bytes()).hexdigest() == info["sha256"], f"SHA-256 mismatch: {rel}"
