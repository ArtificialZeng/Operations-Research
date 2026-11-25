"""Comprehensive automated verification suite for D4 Boost (Continental Nocturnal River Hypoxia & 24-Hour Clock-Bias)."""
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
# 1. Mathematical & Thermodynamic Unit Tests
# ---------------------------------------------------------------------------
def test_benson_krause_thermodynamics_reference_values_and_cross_script_parity() -> None:
    mod5 = _load_module("05_econometric_hydrologic_suite.py")
    mod3 = _load_module("03_fetch_iv_24h_clock_census.py")
    # Official USGS Benson & Krause (1984) freshwater 1-atm solubility reference values (mg/L):
    # 0 C: 14.621, 10 C: 11.288, 20 C: 9.092, 30 C: 7.559
    temps = np.array([0.0, 10.0, 20.0, 30.0])
    calc = mod5.benson_krause_do_sat_1atm(temps)
    ref = np.array([14.621, 11.288, 9.092, 7.559])
    np.testing.assert_allclose(calc, ref, atol=0.015)

    # Barometric + water-vapor altitude adjustment at 2,000 m must reduce DO_sat by ~21-22%
    alt_2000 = mod5.benson_krause_do_sat_alt(np.array([20.0]), 2000.0)[0]
    ratio = alt_2000 / calc[2]
    assert 0.77 < ratio < 0.80, f"Unexpected 2000m altitude ratio: {ratio}"
    # Sea-level (0 m) must equal 1-atm exactly
    np.testing.assert_allclose(mod5.benson_krause_do_sat_alt(temps, 0.0), calc, atol=1e-12)
    # Exact parity between Step 3 (IV transfer) and Step 5 (DV econometrics) water-vapor + altitude formulas!
    for z in (0.0, 350.0, 1500.0, 2500.0):
        np.testing.assert_allclose(
            mod3.benson_krause_do_sat_alt(temps, z),
            mod5.benson_krause_do_sat_alt(temps, z),
            atol=1e-12,
        )


def test_fwl_within_ym_ols_matches_statsmodels_dummy_ols() -> None:
    mod = _load_module("05_econometric_hydrologic_suite.py")
    rng = np.random.default_rng(42)
    n = 420
    ym = np.repeat([f"2020-{m:02d}" for m in range(5, 11)], n // 6)
    temp = rng.normal(22.0, 3.0, n) + np.repeat(np.linspace(-2, 4, 6), n // 6)
    log_q = rng.normal(6.0, 0.8, n)
    log_q2 = log_q**2
    fe_vals = np.repeat([0.5, -0.3, 0.9, -0.7, 0.2, -0.4], n // 6)
    y = fe_vals - 0.235 * temp + 0.14 * log_q - 0.01 * log_q2 + rng.normal(0.0, 0.25, n)

    df = pd.DataFrame({"ym": ym, "temp": temp, "log_q": log_q, "log_q2": log_q2, "y": y})
    fwl_res = mod.fit_within_ym_full_betas(df, ["y"], ["temp", "log_q", "log_q2"], min_days=100)
    assert fwl_res is not None

    dummies = pd.get_dummies(df["ym"], drop_first=False, dtype=float)
    X_sm = pd.concat([df[["temp", "log_q", "log_q2"]], dummies], axis=1)
    sm_fit = sm.OLS(df["y"], X_sm).fit()
    np.testing.assert_allclose(fwl_res["y"], sm_fit.params[["temp", "log_q", "log_q2"]].values, atol=1e-10)


def test_cr1_cluster_se_matches_statsmodels_exact() -> None:
    mod = _load_module("05_econometric_hydrologic_suite.py")
    rng = np.random.default_rng(99)
    n = 120
    clusters = np.repeat([f"H{i:02d}" for i in range(12)], 10)
    cl_shock = np.repeat(rng.normal(0.0, 0.05, 12), 10)
    y = -0.08 + cl_shock + rng.normal(0.0, 0.03, n)
    df = pd.DataFrame({"val": y, "state": clusters, "huc2": clusters})

    blk = mod.spatial_inference_block(df, "val", np.random.default_rng(7))
    sm_fit = sm.OLS(df["val"], np.ones((n, 1))).fit(cov_type="cluster", cov_kwds={"groups": df["huc2"]})
    assert abs(blk["huc2_cluster"]["se_cr1"] - float(sm_fit.bse.iloc[0])) < 1e-4
    assert abs(blk["mean"] - float(sm_fit.params.iloc[0])) < 1e-5


def test_exclude_rules_catch_all_forensic_dams_and_preserve_clean_towns() -> None:
    mod = _load_module("01_discover_and_filter_conus_sites.py")
    base_row = {
        "site_no": "99999999",
        "state": "PA",
        "site_tp_cd": "ST",
        "lat": "40.5",
        "lon": "-77.5",
        "huc_cd": "02050305",
        "has_all_do_stats": 1,
        "min_do_cnt": 4000,
        "temp_mean_cnt": 4000,
        "do_begin": "2010-01-01",
        "do_end": "2024-12-31",
    }
    bad_names = [
        "PEE DEE RIVER BELOW POWERHOUSE DAM NR PEE DEE, NC",
        "Scioto R. at O'Shaughnessy Dam near Dublin OH",
        "LINK RIVER DAM",
        "Mahoning Creek at Mahoning Creek Dam, PA",
        "DES PLAINES RIVER IN LOCK CHANNEL AT ROCKDALE, IL",
        "Monongahela R at L&D2 Lower Pool at Braddock, PA",
        "UPPER KLAMATH LAKE OUTFLOW, OR",
        "CALOOSAHATCHEE RIVER AT S-79, NR.OLGA, FLA",
        "REEDY CREEK AT S-40, NEAR LOUGHMAN, FL",
        "ROANOKE RIVER AT BUGGS ISLAND, VA",
        "BLACK EARTH CK NR TREATMENT PLNT @ CROSS PLAINS,WI",
        "CUMBERLAND R AT OMOHUNDRO WTR PLT AT NASHVILLE, TN",
        "WACCAMAW RIVER AT CONWAY MARINA AT CONWAY, SC",
        "DELAWARE RIVER AT CHESTER PA",
        "CRABTREE SWAMP AT CONWAY, SC",
    ]
    for nm in bad_names:
        r = dict(base_row, station_nm=nm)
        ok, reasons = mod.classify_site(r)
        assert not ok and len(reasons) > 0, f"Failed to exclude {nm}"

    # Clean town names like Amsterdam or Damascus must NOT be false-excluded
    clean_row = dict(base_row, station_nm="MOHAWK RIVER AT AMSTERDAM NY")
    ok_clean, reasons_clean = mod.classify_site(clean_row)
    assert ok_clean and len(reasons_clean) == 0


# ---------------------------------------------------------------------------
# 2. Data Hygiene, NID Dam-Free & UK Spatial-Cluster Integrity Tests
# ---------------------------------------------------------------------------
def test_conus_census_zero_forbidden_sites_strict_st_and_nid_attached() -> None:
    meta = pd.read_csv(PROC_DIR / "conus_valid_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
    panel = pd.read_csv(PROC_DIR / "conus_river_econometric_panel.csv", dtype={"site_no": str, "huc2": str})
    iv_meta = pd.read_csv(PROC_DIR / "conus_iv_rivers_meta.csv", dtype={"site_no": str, "huc2": str})

    assert len(meta) >= 350, f"Expected >=350 clean CONUS rivers, got {len(meta)}"
    assert meta["state"].nunique() >= 35, f"Expected >=35 states, got {meta['state'].nunique()}"
    assert meta["huc2"].nunique() >= 17, f"Expected >=17 CONUS HUC-2 basins, got {meta['huc2'].nunique()}"
    assert (meta["site_tp_cd"] == "ST").all(), "Non-ST site leaked into clean CONUS census!"
    assert (meta["is_brackish_spcond_gt5000"] == 0).all(), "Brackish SpCond>5000 site leaked!"
    assert meta["nid_dist_ge500af_km"].notna().all(), "Missing USACE NID dam distances!"

    for df_chk, nm in [(meta, "meta"), (panel, "panel"), (iv_meta, "iv_meta")]:
        leaked = KNOWN_FORENSIC_EXCLUDED.intersection(set(df_chk["site_no"].str.strip()))
        assert not leaked, f"Forensic excluded sites leaked into {nm}: {leaked}"
        bad_nm = df_chk["station_nm"].str.upper().str.contains(
            r"\b(?:DAM|TAILRACE|POWERHOUSE|LOCK\s+CHANNEL|L&D\d*|KLAMATH|RESERVOIR|ESTUARY|TIDAL|MARINA|SWAMP|BUGGS\s+ISLAND|TREATMENT\s*PLNT|WTR\s*PLT)\b",
            regex=True,
            na=False,
        )
        assert not bad_nm.any(), f"Forbidden hydro station name leaked into {nm}: {df_chk.loc[bad_nm, 'station_nm'].tolist()}"


def test_uk_ea_replication_clean_and_spatially_clustered() -> None:
    uk_csv = pd.read_csv(PROC_DIR / "uk_ea_clean_rivers_results.csv")
    uk_js = json.loads((RES_DIR / "uk_ea_replication_results.json").read_text(encoding="utf-8"))

    assert len(uk_csv) >= 55, f"Expected >=55 clean UK rivers, got {len(uk_csv)}"
    assert uk_js["n_uk_grid1deg_clusters"] >= 15
    norm_lbl = uk_csv["label"].astype(str).str.replace(r"[_\-/]+", " ", regex=True).str.upper()
    assert not norm_lbl.str.contains(
        r"\b(?:GW|WEIR|DAM|STW|CSO|CHISWICK|PUTNEY|ERITH|ADIT|CUNSEY|POLZEATH)\b|TYNE.*SWING|WITHAM.*BOSTON|LEVEN.*NEWBY",
        regex=True,
    ).any()

    dec = uk_js["thermal_slopes_ym_fe"]["DOmin_minus_DOmax"]
    assert dec["mean"] < -0.05
    assert dec["p_t"] < 1e-5
    assert dec["grid1deg_cluster"]["p_cr1_t_Gminus1"] < 0.001
    assert uk_js["thermal_slopes_ym_fe"]["DOmin_minus_HenrysLaw"]["grid1deg_cluster"]["p_cr1_t_Gminus1"] < 0.01
    assert uk_js["thermal_slopes_ym_fe"]["DOmax_minus_HenrysLaw"]["grid1deg_cluster"]["p_cr1_t_Gminus1"] < 0.05
    assert uk_js["clock_bias_summary"]["afternoon_warming_underestimation_pct"] > 20.0
    assert uk_js["clock_bias_summary"]["afternoon_bst_warming_underestimation_pct"] > 20.0


# ---------------------------------------------------------------------------
# 3. Core Empirical Receipts, NID, Transfer VIF, Tables & Parity Checks
# ---------------------------------------------------------------------------
def test_zero_nans_and_table4_internal_arithmetic_integrity() -> None:
    expected_tables = [
        "table1_core_thermal_decoupling.csv",
        "table2_24h_clock_bias_windows.csv",
        "table2b_transfer_function_oos.csv",
        "table3_compound_hot_x_dry.csv",
        "table4_biophysical_mechanism_strata.csv",
        "table5_secular_trends_and_uk_replication.csv",
        "table6_huc2_basin_summary.csv",
    ]
    for fn in expected_tables:
        p = TBL_DIR / fn
        assert p.exists(), f"Missing table: {fn}"
        df = pd.read_csv(p)
        assert len(df) > 0, f"Empty table: {fn}"
        n_nan = int(df.isna().sum().sum())
        assert n_nan == 0, f"Found {n_nan} NaNs in {fn}"

    # Regression guard against prior SpCond do_min_mean column corruption bug:
    # For EVERY stratum in Table 4, do_min_mean - do_max_mean MUST equal diff_min_max_mean!
    t4 = pd.read_csv(TBL_DIR / "table4_biophysical_mechanism_strata.csv")
    diff_chk = np.abs((t4["do_min_mean"] - t4["do_max_mean"]) - t4["diff_min_max_mean"])
    assert (diff_chk < 1e-4).all(), f"Table 4 arithmetic corruption detected:\n{t4[diff_chk >= 1e-4]}"


def test_core_results_nid_dam_free_and_well_conditioned_transfer() -> None:
    econ = json.loads((RES_DIR / "d4_econometric_hydrologic_results.json").read_text(encoding="utf-8"))
    iv = json.loads((RES_DIR / "conus_iv_24h_clock_results.json").read_text(encoding="utf-8"))

    # Spec 2 Primary YM FE + log(Q) + log(Q)^2
    s2 = econ["spec2_ym_fe_logQ_quad_primary"]
    assert s2["diff_min_max"]["mean"] < -0.05
    assert s2["diff_min_max"]["huc2_cluster"]["p_cr1_t_Gminus1"] < 1e-6
    assert s2["diff_min_max"]["state_cluster"]["p_cr1_t_Gminus1"] < 1e-6
    assert s2["diff_min_sat"]["mean"] < 0.0
    assert s2["diff_max_sat"]["mean"] > 0.0

    # USACE NID dam-free sensitivity must hold without attenuation!
    rob = econ["robustness_suite"]
    for nid_k in ("spec5_nid_gt5km_ge500af", "spec5_nid_gt10km_ge5000af", "spec5_nid_gt5km_any_dam", "spec5_dedup_2km_reach"):
        blk = rob[nid_k]["diff_min_max"]
        assert blk["mean"] < -0.06, f"{nid_k} attenuated: {blk['mean']}"
        assert blk["huc2_cluster"]["p_cr1_t_Gminus1"] < 1e-4

    # Exact diurnal T_min/T_max solubility invariance
    s3 = econ["spec3_exact_diurnal_solubility"]
    assert abs(s3["invariance_gap_min_exact_minus_Tmean"]["mean"]) < 0.01

    # 24-hour IV clock-bias census + well-conditioned de-collinearized transfer function (max VIF < 5!)
    assert iv["n_iv_rivers"] >= 80
    assert len(iv["solar_24h_curve"]) == 24
    assert len(iv["civil_24h_curve"]) == 24
    assert all(r["bio_excess_mean"] is not None for r in iv["solar_24h_curve"])
    pm = iv["named_windows"]["pm1316"]
    ls = iv["named_windows"]["ls10"]
    assert pm["warming_underestimation_pct"] > 20.0
    assert pm["slope_bias_huc2_clustered"]["p_cr1_t_Gminus1"] < 0.001
    assert ls["hypoxia_blindness"]["lt_5_mgL"]["missed_pct"] > 20.0
    assert pm["hypoxia_blindness"]["lt_5_mgL"]["missed_pct"] > ls["hypoxia_blindness"]["lt_5_mgL"]["missed_pct"]

    for mode in ("afternoon_1316", "afternoon_1430", "landsat_1030"):
        tf = iv["transfer_function_oos"][mode]
        assert tf["max_vif"] < 5.0, f"High transfer VIF in {mode}: {tf['max_vif']}"
        assert tf["mean_bias_reduction_pct"] > 90.0
        assert tf["rmse_reduction_pct"] > 40.0
        assert "oos_r2_do_min" in tf and "oos_r2_drawdown" in tf
        assert tf["nonlinear_spline_benchmark"]["lohuc2_rmse_mgL"] > 0.0


def test_manuscript_tables_exact_parity_with_json_and_csv_receipts() -> None:
    """Programmatically verify that manuscript Markdown tables match JSON/CSV receipts with zero transcription drift."""
    md = (BASE_DIR / "manuscript_d4_boost.md").read_text(encoding="utf-8")
    econ = json.loads((RES_DIR / "d4_econometric_hydrologic_results.json").read_text(encoding="utf-8"))
    uk = json.loads((RES_DIR / "uk_ea_replication_results.json").read_text(encoding="utf-8"))
    t4 = pd.read_csv(TBL_DIR / "table4_biophysical_mechanism_strata.csv")

    def clean_num(cell: str) -> float:
        s = re.sub(r"[*$%,()]", "", cell).replace("−", "-").strip()
        return float(s.split()[0])

    # Parse all Markdown table rows
    rows_by_label: dict[str, list[str]] = {}
    for ln in md.splitlines():
        if ln.startswith("|") and not ln.startswith("|---") and not ln.startswith("| Specification") and not ln.startswith("| Outcome") and not ln.startswith("| Mechanism") and not ln.startswith("| Panel"):
            cells = [c.strip() for c in ln.strip("|").split("|")]
            if len(cells) >= 5 and cells[1]:
                rows_by_label[cells[0]] = cells

    # Check Table 1 Spec 2 + Robustness + NID exact mean & HUC-2 SE parity
    s2 = econ["spec2_ym_fe_logQ_quad_primary"]
    rob = econ["robustness_suite"]
    t1_checks = [
        ("Henry's Law $DO_{\\text{sat,alt}}$", s2["do_sat_alt"]),
        ("Daytime $DO_{\\max}$", s2["do_max"]),
        ("Daily $DO_{\\text{mean}}$", s2["do_mean"]),
        ("Nocturnal $DO_{\\min}$", s2["do_min"]),
        ("**Decoupling: $DO_{\\min} - DO_{\\max}$**", s2["diff_min_max"]),
        ("**Nocturnal Excess: $DO_{\\min} - DO_{\\text{sat}}$**", s2["diff_min_sat"]),
        ("**Daytime Buffer: $DO_{\\max} - DO_{\\text{sat}}$**", s2["diff_max_sat"]),
        ("Spec 4a $+ \\log(\\text{SpCond})$ ($DO_{\\min}-DO_{\\max}$)", rob["spec4_plus_logSpCond"]["diff_min_max"]),
        ("Spec 4b $+ \\log(1+\\text{Turb})$ ($DO_{\\min}-DO_{\\max}$)", rob["spec4_plus_logTurbidity"]["diff_min_max"]),
        ("**Spec 5e NID Dam-Free ($>5$ km, $\\ge 500$ af)**", rob["spec5_nid_gt5km_ge500af"]["diff_min_max"]),
        ("**Spec 5f NID Reservoir-Free ($>10$ km, $\\ge 5{,}000$ af)**", rob["spec5_nid_gt10km_ge5000af"]["diff_min_max"]),
        ("**Spec 5g NID Strictly Dam-Free ($>5$ km any dam)**", rob["spec5_nid_gt5km_any_dam"]["diff_min_max"]),
    ]
    for lbl, blk in t1_checks:
        assert lbl in rows_by_label, f"Missing Table 1 row in manuscript: {lbl}"
        cells = rows_by_label[lbl]
        assert int(clean_num(cells[1])) == blk["n_rivers"], f"N mismatch for {lbl}"
        assert abs(clean_num(cells[2]) - blk["mean"]) < 1.5e-4, f"Mean mismatch for {lbl}"
        assert abs(clean_num(cells[4]) - blk["huc2_cluster"]["se_cr1"]) < 1.5e-4, f"HUC-2 SE mismatch for {lbl}"
        assert abs(clean_num(cells[6]) - blk["state_cluster"]["se_cr1"]) < 1.5e-4, f"State SE mismatch for {lbl}"

    # Check Table 4 every single stratum HUC-2 SE, do_max, do_min, diff_min_max parity against table4 CSV!
    t4_map = {
        "Q1 Oligotrophic": "Q1_Oligotrophic",
        "Q2 Low-Mesotrophic": "Q2_LowMesotrophic",
        "Q3 High-Mesotrophic": "Q3_HighMesotrophic",
        "Q4 Eutrophic": "Q4_Eutrophic",
        "T1 Low SpCond": "T1_LowSpCond",
        "T2 Mid SpCond": "T2_MidSpCond",
        "T3 High SpCond": "T3_HighSpCond",
        "T1 Clear": "T1_Clear",
        "T2 Moderate Turbidity": "T2_ModerateTurb",
        "T3 Turbid": "T3_Turbid",
        "South ($<35^\\circ\\text{N}$)": "South_lt35N",
        "Mid-Latitude ($35\\text{–}41^\\circ\\text{N}$)": "MidLat_35_41N",
        "North ($>41^\\circ\\text{N}$)": "North_gt41N",
    }
    for md_lbl, csv_key in t4_map.items():
        assert md_lbl in rows_by_label, f"Missing Table 4 row: {md_lbl}"
        cells = rows_by_label[md_lbl]
        r_csv = t4[t4["stratum"] == csv_key].iloc[0]
        assert int(clean_num(cells[1])) == int(r_csv["n_rivers"])
        assert abs(clean_num(cells[3]) - float(r_csv["do_max_mean"])) < 1.5e-4
        assert abs(clean_num(cells[4]) - float(r_csv["do_min_mean"])) < 1.5e-4
        assert abs(clean_num(cells[5]) - float(r_csv["diff_min_max_mean"])) < 1.5e-4
        assert abs(clean_num(cells[6]) - float(r_csv["diff_min_max_se_huc2"])) < 1.5e-4, f"Table 4 HUC-2 SE mismatch for {md_lbl}"

    # Check Table 5 Panel B UK EA spatially clustered parity
    uk_dec = uk["thermal_slopes_ym_fe"]["DOmin_minus_DOmax"]
    uk_row = rows_by_label["**UK Decoupling: $DO_{\\min} - DO_{\\max}$ ($\\text{mg L}^{-1}\\text{ }^\\circ\\text{C}^{-1}$)**"]
    assert int(clean_num(uk_row[1])) == uk_dec["n"]
    assert abs(clean_num(uk_row[2]) - uk_dec["mean"]) < 1.5e-4
    assert abs(clean_num(uk_row[3]) - uk_dec["grid1deg_cluster"]["se_cr1"]) < 1.5e-4


def test_figures_pdf_zero_leaks_and_sha256_manifest() -> None:
    expected_figs = [
        "fig1_conus_map_and_thermal_decoupling",
        "fig2_24h_clock_bias_and_transfer",
        "fig3_compound_heatwave_drought",
        "fig4_biophysical_mechanism",
        "fig5_secular_cwa_and_uk_replication",
    ]
    for stem in expected_figs:
        png = FIG_DIR / f"{stem}.png"
        pdf = FIG_DIR / f"{stem}.pdf"
        assert png.exists() and png.stat().st_size > 40_000, f"Invalid PNG: {png}"
        assert pdf.exists() and pdf.stat().st_size > 15_000, f"Invalid PDF: {pdf}"

    # Compiled manuscript PDF exists, has >=12 pages, and zero leaked LaTeX/Markdown/ASCII/filename tokens
    mpdf = BASE_DIR / "manuscript_d4_boost.pdf"
    assert mpdf.exists() and mpdf.stat().st_size > 200_000
    reader = PdfReader(str(mpdf))
    assert len(reader.pages) >= 12
    full_txt = "\n".join((p.extract_text() or "") for p in reader.pages)
    for bad in [
        r"\\[A-Za-z]+", r"\$\$", r"\*\*", r"\|---", r"\^°", r"\{,\}",
        r"S_\+", r"DO_min", r"DO_max", r"DO_sat", r"T_min", r"T_max",
        r"log\(Q\)\^2", r"fig[1-5]_[a-z0-9_]+\.png",
    ]:
        assert not re.search(bad, full_txt), f"Leaked token {bad} found in manuscript_d4_boost.pdf"

    # SHA-256 manifest matches every hashed file on disk
    sha_path = BASE_DIR / "SHA256SUMS.json"
    assert sha_path.exists()
    manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    assert manifest["n_files_hashed"] >= 20
    for rel, info in manifest["files"].items():
        fp = BASE_DIR / rel
        assert fp.exists(), f"Manifest file missing: {rel}"
        h = hashlib.sha256(fp.read_bytes()).hexdigest()
        assert h == info["sha256"], f"SHA-256 mismatch for {rel}"


def test_edge_cases_singleton_ym_and_collinear_design_rejected() -> None:
    mod = _load_module("05_econometric_hydrologic_suite.py")
    empty_df = pd.DataFrame(columns=["ym", "temp", "y"])
    assert mod.fit_within_ym_ols(empty_df, ["y"], ["temp"], min_days=10) is None

    rng = np.random.default_rng(123)
    n = 120
    df_col = pd.DataFrame(
        {
            "ym": np.repeat(["2022-06", "2022-07", "2022-08"], 40),
            "x1": rng.normal(20.0, 2.0, n),
            "y": rng.normal(8.0, 1.0, n),
        }
    )
    df_col["x2"] = 2.0 * df_col["x1"]
    assert mod.fit_within_ym_ols(df_col, ["y"], ["x1", "x2"], min_days=50) is None


def test_pooled_panel_and_equal_river_consistency() -> None:
    econ = json.loads((RES_DIR / "d4_econometric_hydrologic_results.json").read_text(encoding="utf-8"))
    s2 = econ["spec2_ym_fe_logQ_quad_primary"]
    s6 = econ["spec6_pooled_panel_ym_fe_logQ"]
    assert s6["n_absorbed_fe_cells"] > 15_000
    out6 = s6["outcomes"]
    assert abs(s2["diff_min_max"]["mean"] - out6["diff_min_max"]["beta_temp"]) < 0.01
    assert abs(s2["diff_min_sat"]["mean"] - out6["diff_min_sat"]["beta_temp"]) < 0.01
    assert out6["diff_min_max"]["huc2_cluster"]["p_cr1_t_Gminus1"] < 1e-7


def test_all_manuscript_dois_match_verified_crossref_archive() -> None:
    refs = json.loads((PROC_DIR / "verified_references.json").read_text(encoding="utf-8"))
    verified_dois = {str(v["doi"]).lower() for v in refs.values() if v.get("doi")}
    md = (BASE_DIR / "manuscript_d4_boost.md").read_text(encoding="utf-8")
    cited_dois = {d.lower().rstrip(".,);") for d in re.findall(r"https://doi\.org/([^\s)]+)", md)}
    assert len(cited_dois) >= 15
    unverified = cited_dois - verified_dois
    assert not unverified, f"Unverified DOIs cited in manuscript: {unverified}"
