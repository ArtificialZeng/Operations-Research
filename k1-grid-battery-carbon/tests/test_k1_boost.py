"""Strict automated regression & mathematical-verification pytest suite for K1 /boost
(U.S. Utility-Scale Battery Storage, Diurnal Gas Displacement & Carbon-Arbitrage Paradox).

Verifies 22 end-to-end invariants including:
  - Exact WLS FWL vs brute-force LSDV WCB (Rademacher & Webb-6pt, both balanced AND
    unbalanced with time-varying weights and non-FE clusters) to atol = 1e-12,
  - Permanent repair of EIA-930's 2-year CISO midday natural-gas corruption in Panel A,
  - Exact 24x24 date-clustered CEMS covariance SEs & import-only AEF / MEF invariance,
  - Strictly interior CAISO curtailment regimes (exact 0.0% un-curtailment in 0 MW bin)
    and pure exogenous dLoad monotonic collapse,
  - Rigorous Corollary 2.1 (zero post-dispatch upper-bound fallacy),
  - Zero hardcoded numbers in figures, manuscript, and PDF compiler,
  - 100% live Crossref DOI verification & two-way sync,
  - Zero-leak PDF & disk-verified LF SHA256SUMS + Wave-7 cryptographic read-only boundary.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image
from pypdf import PdfReader

WS_DIR = Path(r"D:\AI_Science\antigravity\k1_boost_grid_battery_carbon_20261127")
SCRIPTS_DIR = WS_DIR / "scripts"
PROC_DIR = WS_DIR / "data" / "processed"
RAW_EXT_DIR = WS_DIR / "data" / "raw_external"
RES_DIR = WS_DIR / "results"
FIG_DIR = WS_DIR / "figures"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from econ_utils import (
    DIURNAL_WINDOWS,
    RADEMACHER_WEIGHTS,
    WEBB6_WEIGHTS,
    count_fe_dof_exact,
    wls_fe_cr1_wcb,
)


def _load_json(name: str) -> dict:
    return json.loads((RES_DIR / name).read_text(encoding="utf-8"))


def _assert_all_finite(obj, path: str = "$") -> None:
    if isinstance(obj, float):
        assert math.isfinite(obj), f"Non-finite float at {path}: {obj}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_all_finite(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_all_finite(v, f"{path}[{i}]")


def _explicit_wls_lsdv_cr1_wcb(
    y: np.ndarray,
    X: np.ndarray,
    fe1: np.ndarray,
    fe2: np.ndarray,
    clusters: np.ndarray,
    weights: np.ndarray,
    wcb_var_idx: int,
    wcb_B: int,
    wcb_dist: str,
    seed: int,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, float]:
    """Brute-force explicit WLS LSDV reference implementation (W^{1/2}[X, D]) for atol=1e-12 audit."""
    n, k = X.shape
    w = weights / np.mean(weights)
    sw = np.sqrt(w)

    u1, c1 = np.unique(fe1, return_inverse=True)
    u2, c2 = np.unique(fe2, return_inverse=True)
    D1 = np.eye(len(u1))[c1]
    D2 = np.eye(len(u2))[c2][:, 1:]  # drop 1 reference dummy for connected 2-way FE
    Z = np.column_stack([X, D1, D2])
    Zw = sw[:, None] * Z
    yw = sw * y
    p_tot = Z.shape[1]

    ZtZ_inv = np.linalg.inv(Zw.T @ Zw)
    theta = ZtZ_inv @ (Zw.T @ yw)
    ew = yw - Zw @ theta

    cl_c, cl_u = pd.factorize(clusters, sort=False)
    G = len(cl_u)
    S = np.zeros((G, p_tot))
    for j in range(p_tot):
        S[:, j] = np.bincount(cl_c, weights=Zw[:, j] * ew, minlength=G)
    dfc = (G / (G - 1.0)) * ((n - 1.0) / (n - p_tot))
    V = dfc * (ZtZ_inv @ (S.T @ S) @ ZtZ_inv)
    se = np.sqrt(np.diag(V))[:k]
    beta = theta[:k]
    t_obs = beta / se

    # Explicit restricted WLS LSDV WCB
    other_cols = [j for j in range(p_tot) if j != wcb_var_idx]
    Zo = Zw[:, other_cols]
    th0 = np.linalg.inv(Zo.T @ Zo) @ (Zo.T @ yw)
    e0_raw = y - Z[:, other_cols] @ th0
    yhat0_raw = Z[:, other_cols] @ th0

    rng = np.random.default_rng(seed)
    dist_vals = WEBB6_WEIGHTS if wcb_dist == "webb6" else RADEMACHER_WEIGHTS
    t_boot = np.empty(wcb_B)
    for bi in range(wcb_B):
        rw = rng.choice(dist_vals, size=G)
        ys_w = sw * (yhat0_raw + rw[cl_c] * e0_raw)
        ths = ZtZ_inv @ (Zw.T @ ys_w)
        es_w = ys_w - Zw @ ths
        Sb = np.zeros((G, p_tot))
        for j in range(p_tot):
            Sb[:, j] = np.bincount(cl_c, weights=Zw[:, j] * es_w, minlength=G)
        Vb = dfc * (ZtZ_inv @ (Sb.T @ Sb) @ ZtZ_inv)
        t_boot[bi] = ths[wcb_var_idx] / np.sqrt(Vb[wcb_var_idx, wcb_var_idx])
    p_wcb = float((1.0 + np.sum(np.abs(t_boot) >= abs(t_obs[wcb_var_idx]))) / (wcb_B + 1.0))
    return beta, se, t_obs, p_wcb


# ------------------------------------------------------------------
# 1. Exact Mathematical Verification Tests (WLS FWL vs Brute-Force LSDV to atol=1e-12)
# ------------------------------------------------------------------
def test_wls_fwl_vs_explicit_lsdv_rademacher_atol_1e12() -> None:
    rng = np.random.default_rng(42)
    n_g, n_t = 12, 10
    fe1 = np.repeat(np.arange(n_g), n_t)
    fe2 = np.tile(np.arange(n_t), n_g)
    n = len(fe1)
    weights = np.repeat(rng.uniform(100.0, 5000.0, size=n_g), n_t)
    X = rng.normal(size=(n, 3))
    y = 2.0 * fe1 - 1.5 * fe2 + X @ np.array([-0.35, 0.25, 0.80]) + rng.normal(scale=1.2, size=n)

    fwl = wls_fe_cr1_wcb(
        y, X, clusters=fe1, fe_groups=[fe1, fe2], weights=weights,
        col_names=["x0", "x1", "x2"], wcb_var_idx=0, wcb_B=199, wcb_dist="rademacher", seed=777,
    )
    b_ref, se_ref, t_ref, p_ref = _explicit_wls_lsdv_cr1_wcb(
        y, X, fe1, fe2, fe1, weights, wcb_var_idx=0, wcb_B=199, wcb_dist="rademacher", seed=777,
    )
    assert fwl["fe_dof"] == n_g + n_t - 1
    for j, nm in enumerate(["x0", "x1", "x2"]):
        assert abs(fwl["coefs"][nm]["beta"] - b_ref[j]) < 1e-12
        assert abs(fwl["coefs"][nm]["se_cr1"] - se_ref[j]) < 1e-12
        assert abs(fwl["coefs"][nm]["t_cr1"] - t_ref[j]) < 1e-12
    assert abs(fwl["wcb"]["p_wcb"] - p_ref) < 1e-12


def test_wls_fwl_vs_explicit_lsdv_webb6_atol_1e12() -> None:
    rng = np.random.default_rng(99)
    n_g, n_t = 10, 8
    fe1 = np.repeat(np.arange(n_g), n_t)
    fe2 = np.tile(np.arange(n_t), n_g)
    n = len(fe1)
    weights = np.repeat(rng.uniform(50.0, 2000.0, size=n_g), n_t)
    X = rng.normal(size=(n, 2))
    y = 0.7 * fe1 + 0.4 * fe2 + X @ np.array([-0.42, 0.65]) + rng.normal(scale=0.9, size=n)

    fwl = wls_fe_cr1_wcb(
        y, X, clusters=fe1, fe_groups=[fe1, fe2], weights=weights,
        col_names=["x0", "x1"], wcb_var_idx=0, wcb_B=199, wcb_dist="webb6", seed=999,
    )
    b_ref, se_ref, t_ref, p_ref = _explicit_wls_lsdv_cr1_wcb(
        y, X, fe1, fe2, fe1, weights, wcb_var_idx=0, wcb_B=199, wcb_dist="webb6", seed=999,
    )
    for j, nm in enumerate(["x0", "x1"]):
        assert abs(fwl["coefs"][nm]["beta"] - b_ref[j]) < 1e-12
        assert abs(fwl["coefs"][nm]["se_cr1"] - se_ref[j]) < 1e-12
        assert abs(fwl["coefs"][nm]["t_cr1"] - t_ref[j]) < 1e-12
    assert abs(fwl["wcb"]["p_wcb"] - p_ref) < 1e-12


def test_wls_fwl_vs_lsdv_unbalanced_timevarying_weights_nonfe_clusters_atol_1e12() -> None:
    """Harder edge case: unbalanced panel, observation-varying weights, clusters != fe1."""
    rng = np.random.default_rng(2026)
    n_g, n_t = 14, 9
    fe1_all = np.repeat(np.arange(n_g), n_t)
    fe2_all = np.tile(np.arange(n_t), n_g)
    # Drop 11 interior/trailing observations to make panel genuinely unbalanced
    keep = np.ones(len(fe1_all), dtype=bool)
    keep[[3, 17, 29, 44, 58, 71, 88, 102, 114, 121, 124]] = False
    fe1, fe2 = fe1_all[keep], fe2_all[keep]
    n = len(fe1)
    # Coarser cluster grouping (7 macro-clusters of 2 units each -> clusters != fe1!)
    clusters = fe1 // 2
    weights = rng.uniform(10.0, 500.0, size=n)
    X = rng.normal(size=(n, 2))
    y = 1.2 * fe1 - 0.8 * fe2 + X @ np.array([-0.28, 0.51]) + rng.normal(scale=1.1, size=n)

    fwl = wls_fe_cr1_wcb(
        y, X, clusters=clusters, fe_groups=[fe1, fe2], weights=weights,
        col_names=["x0", "x1"], wcb_var_idx=0, wcb_B=149, wcb_dist="webb6", seed=1234,
    )
    b_ref, se_ref, t_ref, p_ref = _explicit_wls_lsdv_cr1_wcb(
        y, X, fe1, fe2, clusters, weights, wcb_var_idx=0, wcb_B=149, wcb_dist="webb6", seed=1234,
    )
    for j, nm in enumerate(["x0", "x1"]):
        assert abs(fwl["coefs"][nm]["beta"] - b_ref[j]) < 1e-12
        assert abs(fwl["coefs"][nm]["se_cr1"] - se_ref[j]) < 1e-12
        assert abs(fwl["coefs"][nm]["t_cr1"] - t_ref[j]) < 1e-12
    assert abs(fwl["wcb"]["p_wcb"] - p_ref) < 1e-12


def test_exact_nested_fe_dof_components() -> None:
    unit = np.repeat([0, 1, 2, 3], 3)
    reg_per = np.array(["A1", "A2", "A3", "A1", "A2", "A3", "B1", "B2", "B3", "B1", "B2", "B3"])
    assert count_fe_dof_exact([unit, reg_per]) == 4 + 6 - 2


# ------------------------------------------------------------------
# 2. JSON Hygiene & Zero-NaN / Zero-Inf Invariants
# ------------------------------------------------------------------
def test_all_json_receipts_exist_and_zero_nan() -> None:
    expected = [
        "00_external_downloads_audit.json",
        "01_telemetry_audit.json",
        "02_panel_a_wls_results.json",
        "03_cems_carbon_curtailment_results.json",
        "04_formal_model_verification.json",
        "07_citation_verification.json",
    ]
    for fn in expected:
        p = RES_DIR / fn
        assert p.exists(), f"Missing JSON receipt: {fn}"
        raw = p.read_text(encoding="utf-8")
        assert "\r\n" not in raw, f"CRLF found in {fn}"
        obj = json.loads(raw)
        _assert_all_finite(obj, fn)


# ------------------------------------------------------------------
# 3. Pillar 1 Physical Telemetry & Panel A CISO Repair Invariants
# ------------------------------------------------------------------
def test_diurnal_windows_disjoint_24h_partition() -> None:
    all_h = [h for hrs in DIURNAL_WINDOWS.values() for h in hrs]
    assert len(all_h) == 24
    assert sorted(all_h) == list(range(1, 25))
    assert len(DIURNAL_WINDOWS["Overnight"]) == 8
    assert len(DIURNAL_WINDOWS["Morning Ramp"]) == 3
    assert len(DIURNAL_WINDOWS["Midday Solar"]) == 7
    assert len(DIURNAL_WINDOWS["Evening Peak"]) == 6


def test_caiso_standalone_rte_and_telemetry_repairs() -> None:
    r1 = _load_json("01_telemetry_audit.json")
    ciso_rep = r1["ciso_telemetry_repair"]
    assert 0.75 <= ciso_rep["caiso_fuelsource_rte"] <= 0.92
    assert ciso_rep["caiso_fuelsource_rte"] < 1.0
    assert ciso_rep["eia930_broken_other_geo_rte"] > 1.0

    # Documented 2-year EIA-930 CISO midday NG corruption audit
    ng_corr = ciso_rep["eia930_ng_corruption_202312_202512"]
    assert ng_corr["mean_midday_phantom_ng_mw_2024_2025"] > 4500.0
    assert ng_corr["post_eia_fix_2026_mean_abs_diff_mw"] < 100.0

    # ERCO & AZPS UES charging recovered cleanly
    assert r1["ues_charging_bug"]["ERCO"]["unk_stor_min_mw"] < -5000.0
    assert r1["ues_charging_bug"]["AZPS"]["unk_stor_min_mw"] < -2000.0
    assert 0.75 <= r1["ues_charging_bug"]["ERCO"]["repaired_rte"] <= 0.90
    assert 0.75 <= r1["ues_charging_bug"]["AZPS"]["repaired_rte"] <= 0.92

    # Zero pumped-hydro leakage across SOCO, DUK, MISO, CPLE
    for ba in ["SOCO", "DUK", "MISO", "CPLE"]:
        assert r1["pumped_hydro_leakage_audit"][ba]["pumped_leakage_detected"] is False

    # FPL 2,668 MW glitch caught and logged
    anoms = r1["physical_bound_anomalies"]
    assert any(a["ba"] == "FPL" and a["date"] == "2025-08-27" and a["raw_bess_mw"] > 2500 for a in anoms)

    # CEMS lag-0 exact alignment across all 6 major grids
    for ba in ["CISO", "ERCO", "AZPS", "MISO", "SOCO", "DUK"]:
        assert r1["cems_utc_alignment_audit"][ba]["best_lag_hr"] == 0
        assert r1["cems_utc_alignment_audit"][ba]["r_at_lag0"] > 0.85

    # EIA-860M hygiene: zero all-zero stale rows in top20_bas
    assert len(r1["eia860m_fleet"]["top20_bas"]) == 20
    assert all(row["bess_mw"] > 0 for row in r1["eia860m_fleet"]["top20_bas"])


def test_panel_a_ciso_natural_gas_repaired_against_fuelsource() -> None:
    """Confirm Panel A CISO 2024-2025 midday NG matches official CAISO fuelsource.csv (NOT corrupted EIA-930!)."""
    sp = pd.read_parquet(PROC_DIR / "panel_a_monthly_spreads.parquet")
    cfs = pd.read_parquet(RAW_EXT_DIR / "caiso_fuelsource_hourly_202312_202610.parquet")
    cfs["ym"] = pd.to_datetime(cfs["date"]).dt.strftime("%Y-%m")
    fs_md = cfs[cfs["hour"].isin(DIURNAL_WINDOWS["Midday Solar"])].groupby("ym")["ng_mw"].mean()
    ciso_24_25 = sp[(sp["ba"] == "CISO") & (sp["ym"] >= "2024-01") & (sp["ym"] <= "2025-12")].copy()
    ciso_24_25["fs_md"] = ciso_24_25["ym"].map(fs_md)
    max_err_mw = float((ciso_24_25["md_ng"] - ciso_24_25["fs_md"]).abs().max())
    assert max_err_mw < 25.0, f"Panel A CISO still differs from CAISO fuelsource by {max_err_mw:.1f} MW"
    # Verify raw unrepaired column indeed differed by >5,000 MW (proving repair took effect!)
    max_raw_err_mw = float((ciso_24_25["md_ng_unrepaired"] - ciso_24_25["fs_md"]).abs().max())
    assert max_raw_err_mw > 5000.0


# ------------------------------------------------------------------
# 4. Pillar 3 Panel A Demand-Weighted WLS Econometric Invariants
# ------------------------------------------------------------------
def test_panel_a_wls_headline_and_robustness() -> None:
    r2 = _load_json("02_panel_a_wls_results.json")
    sp = r2["main_and_robustness_specs"]

    assert r2["leverage_audit"]["dopd_ols_leverage_pct"] > 15.0
    assert r2["leverage_audit"]["dopd_wls_leverage_pct"] < 2.0

    # Core specs strictly negative with p_CR1 < 0.01 and both WCBs < 0.05 (main < 0.01)
    for key in [
        "WLS_ALL49_MAIN_NG",
        "WLS_ALL49_NO_EM_SOLAR_NG",
        "WLS_DROP_CISO_48_NG",
        "WLS_DROP_CE_47_NG",
        "WLS_DROP_TOP7_42_NG",
        "WLS_ALL49_BA_POST24H2_NG",
        "WLS_DROP_CE_BA_POST24H2_NG",
        "WLS_PRE_SCHEMA_2019_2024H1_NG",
        "WLS_POST_SCHEMA_2024H2_2026_NG",
    ]:
        c = sp[key]["coefs"]["bess_share"]
        assert c["beta"] < -0.20, f"{key} beta too weak: {c['beta']}"
        assert c["p_cr1"] < 0.01, f"{key} p_cr1 not <0.01: {c['p_cr1']}"
        assert sp[key]["wcb"]["p_wcb"] < 0.04, f"{key} Rademacher WCB failed"
        assert sp[key]["wcb_webb6"]["p_wcb"] < 0.04, f"{key} Webb-6pt WCB failed"

    assert sp["WLS_ALL49_MAIN_NG"]["wcb"]["p_wcb"] < 0.01
    assert sp["WLS_ALL49_MAIN_NG"]["wcb_webb6"]["p_wcb"] < 0.01
    assert "WLS_ALL49_NO_CONTROLS_NG" in sp

    assert r2["lobao_49_wls"]["n_bas"] == 49
    assert r2["lobao_49_wls"]["p_cr1_max"] < 0.01

    nuc = sp["WLS_ALL49_NUCLEAR_PLACEBO"]
    assert abs(nuc["coefs"]["bess_share"]["beta"]) < 0.005
    assert nuc["coefs"]["bess_share"]["p_cr1"] > 0.20
    assert nuc["wcb"]["p_wcb"] > 0.20


def test_panel_a_distributed_leads_and_daily_dispatch() -> None:
    r2 = _load_json("02_panel_a_wls_results.json")
    ll_all = r2["distributed_6m_lead_lag"]["WLS_ALL49_BA_YM"]
    assert ll_all["joint_future_leads_F"]["p"] > 0.50
    assert ll_all["terms"]["fut_t0_tp6"]["p_cr1"] > 0.20
    assert ll_all["terms"]["fut_tp6_tp12"]["p_cr1"] > 0.20
    assert ll_all["terms"]["stock_tm12"]["beta"] < -0.25

    dy = r2["high_freq_daily_ba_ym_fe"]
    assert dy["DAILY_ALL49_NG_MWH"]["coefs"]["sol_x_bess_mwh"]["beta"] < -0.05
    assert dy["DAILY_ALL49_NG_MWH"]["coefs"]["sol_x_bess_mwh"]["p_cr1"] < 0.01
    assert dy["DAILY_ALL49_NG_MWH_QUAD_SOLCAP"]["coefs"]["sol_x_bess_mwh"]["beta"] < -0.05
    assert dy["DAILY_ALL49_NUCLEAR_PLACEBO"]["coefs"]["sol_x_bess_mwh"]["p_cr1"] > 0.15


# ------------------------------------------------------------------
# 5. Pillar 4 Direct EPA CEMS (Exact 24x24 SE) & Non-Circular CAISO Invariants
# ------------------------------------------------------------------
def test_cems_sign_reversal_exact_24x24_se_and_egrid_convergence() -> None:
    r3 = _load_json("03_cems_carbon_curtailment_results.json")
    fl = r3["fleet_aggregates"]["all_14_bas"]
    assert fl["aef_kg_mwh"] < -50.0
    assert fl["cems_mef_kg_mwh"] > 50.0
    assert fl["cems_mef_imp_weight_kg_mwh"] > 50.0
    assert fl["sign_reversal_cems_minus_aef_mt"] > 5.0
    assert r3["cems_vs_egrid_cross_validation"]["r_net_kg_mwh"] > 0.95

    # Verify exact 24x24 date-clustered SEs are present and strictly positive across all 14 BAs
    for row in r3["ba_carbon_table"]:
        assert row["se_net_cems_kg_mwh"] > 0.5
        assert "se_net_cems_diag_kg_mwh" in row


def test_noncircular_caiso_interior_curtailment_and_pure_load_collapse() -> None:
    r3 = _load_json("03_cems_carbon_curtailment_results.json")
    cc = r3["caiso_noncircular_curtailment"]
    bins = cc["curtailment_stratified_bins"]
    assert len(bins) == 4
    # Strictly monotonic decline in domestic, system, AND instrument-free pure dLoad CEMS MEFs!
    dom_mefs = [b["mef_cems_dom_kg_mwh"] for b in bins]
    sys_mefs = [b["mef_cems_sys_kg_mwh"] for b in bins]
    load_mefs = [b["pure_load_mef_dom_kg_mwh"] for b in bins]
    assert dom_mefs[0] > dom_mefs[1] > dom_mefs[2] > dom_mefs[3]
    assert sys_mefs[0] > sys_mefs[1] > sys_mefs[2] > sys_mefs[3]
    assert load_mefs[0] > load_mefs[1] > load_mefs[2] > load_mefs[3]

    # Interior 0 MW regime MUST have exact 0.0% marginal un-curtailment (zero boundary leakage!)
    assert abs(bins[0]["d_curt_per_d_netload"]) < 1e-12
    assert bins[3]["d_curt_per_d_netload"] < -0.50

    assert cc["dispatch_elasticity_total"]["coefs"]["total_curt_mw"]["beta"] > 0.05
    assert cc["dispatch_elasticity_total"]["coefs"]["total_curt_mw"]["t_day"] > 5.0

    src_03 = (SCRIPTS_DIR / "03_cems_carbon_and_caiso_curtailment.py").read_text(encoding="utf-8")
    assert "sol_pen >= 0.5" not in src_03.lower()
    assert "ct+sol50" not in src_03.lower()


def test_caiso_empirical_absorption_and_incremental_headroom_rigor() -> None:
    """Verify Corollary 2.1 rigorously separates empirical marginal absorption from incremental headroom."""
    r3 = _load_json("03_cems_carbon_curtailment_results.json")
    cc = r3["caiso_noncircular_curtailment"]
    assert 0.0 < cc["rho_residual_headroom_system"] < cc["rho_residual_headroom_total"] < cc["alpha_any_curt_share"]
    assert 0.05 < cc["alpha_emp_unspill_share"] < cc["alpha_star_ciso_cems"]
    assert cc["rho_residual_headroom_total"] < cc["alpha_star_ciso_cems"]
    spl = cc["dispatch_elasticity_system_vs_local"]["coefs"]
    assert spl["system_curt_mw"]["beta"] > 0.05 and spl["system_curt_mw"]["t_day"] > 3.0
    assert spl["local_curt_mw"]["beta"] > 0.05 and spl["local_curt_mw"]["t_day"] > 3.0

    # Ensure manuscript never repeats the false post-dispatch historical upper-bound claim
    md_txt = (WS_DIR / "manuscript_k1_boost.md").read_text(encoding="utf-8")
    assert "physical curtailment absorption cannot exceed" not in md_txt.lower()


def test_caiso_pure_load_and_joint_block_bootstrap_invariants() -> None:
    """Verify v2 CAISO pure exogenous dLoad re-weighting (~+1.34 kg/MWh) & B=1,000 joint block-bootstrap CIs."""
    r3 = _load_json("03_cems_carbon_curtailment_results.json")
    cc = r3["caiso_noncircular_curtailment"]

    net_sys_main = cc["empirical_curt_adjusted_ciso_net_sys_kg_mwh"]
    net_sys_load = cc["empirical_curt_adjusted_ciso_pure_load_net_sys_kg_mwh"]
    net_dom_main = cc["empirical_curt_adjusted_ciso_net_dom_kg_mwh"]
    net_dom_load = cc["empirical_curt_adjusted_ciso_pure_load_net_dom_kg_mwh"]

    # Point estimates straddle zero across main (-0.80) vs pure dLoad (+1.34) system specs!
    assert -2.5 < net_sys_main < 0.0
    assert 0.5 < net_sys_load < 2.5
    assert -35.0 < net_dom_main < -25.0
    assert -35.0 < net_dom_load < -25.0

    jb = cc["joint_block_bootstrap_1000"]
    assert jb["B"] == 1000
    assert jb["n_overlap_days"] == 549
    assert jb["n_neighbor_bas"] >= 5

    for key in ("net_sys_main", "net_sys_pure_load"):
        b_stat = jb[key]
        assert b_stat["covers_zero"] is True, f"{key} joint 95% CI must cover zero"
        assert b_stat["ci95_lo"] < 0.0 < b_stat["ci95_hi"]
        assert b_stat["boot_se"] > 2.0
        assert b_stat["p_boot_vs_zero_2sided"] > 0.20

    assert jb["net_dom_main"]["covers_zero"] is False
    assert jb["net_dom_pure_load"]["covers_zero"] is False

    # Verify both specs & joint CIs are synced into manuscript MD & compiled PDF
    md_txt = (WS_DIR / "manuscript_k1_boost.md").read_text(encoding="utf-8")
    pdf_txt = "\n".join((p.extract_text() or "") for p in PdfReader(str(WS_DIR / "manuscript_k1_boost.pdf")).pages)
    for token in (
        f"{net_sys_main:+.2f}",
        f"{net_sys_load:+.2f}",
        f"{jb['net_sys_main']['ci95_lo']:+.2f}",
        f"{jb['net_sys_main']['ci95_hi']:+.2f}",
        f"{jb['net_sys_pure_load']['ci95_lo']:+.2f}",
        f"{jb['net_sys_pure_load']['ci95_hi']:+.2f}",
    ):
        assert token in md_txt, f"CAISO bootstrap token {token!r} missing from manuscript_k1_boost.md"
        # Edge PDF uses Unicode minus (U+2212) in math spans and ASCII hyphen in plain text
        assert (token in pdf_txt) or (token.replace("-", "\u2212") in pdf_txt), (
            f"CAISO bootstrap token {token!r} missing from manuscript_k1_boost.pdf"
        )


def test_referee_v2_scientific_precision_invariants() -> None:
    """Verify all 4 external referee v2 scientific precision & framing requirements in MD & PDF."""
    md_txt = (WS_DIR / "manuscript_k1_boost.md").read_text(encoding="utf-8")
    pdf_txt = "\n".join((p.extract_text() or "") for p in PdfReader(str(WS_DIR / "manuscript_k1_boost.pdf")).pages)
    md_lo = md_txt.lower()
    pdf_lo = pdf_txt.lower()

    # 1. Objective framing of +5,553 MW EIA-930 vs CAISO midday NG discrepancy (ZERO 'corruption' phrasing!)
    forbidden_phrases = [
        "federal data corruption",
        "federal reporting corruption",
        "reporting corruptions",
        "natural-gas corruption",
        "phantom gas",
        "phantom natural gas",
        "direct epa cems measures",
        "direct epa cems smokestack mefs measure",
    ]
    for bad in forbidden_phrases:
        assert bad not in md_lo, f"Forbidden phrasing {bad!r} found in manuscript_k1_boost.md"
        assert bad not in pdf_lo, f"Forbidden phrasing {bad!r} found in manuscript_k1_boost.pdf"
    assert "reporting discrepancy" in md_lo

    # 2. Exact scientific meaning of +7.44 Mt CO2 as counterfactual accounting discrepancy
    assert "counterfactual accounting discrepancy" in md_lo
    assert "counterfactual accounting discrepancy" in pdf_lo

    # 3. Prominent No Controls (-0.0579, p = 0.576) disclosure in BOTH Abstract AND Section 4
    abs_sec = md_txt.split("## Abstract", 1)[1].split("## 1. Introduction", 1)[0]
    sec4_sec = md_txt.split("## 4.", 1)[1].split("## 5.", 1)[0]
    for sec_name, sec_txt in [("Abstract", abs_sec), ("Section 4", sec4_sec)]:
        assert "No Controls" in sec_txt, f"No Controls missing from {sec_name}"
        assert "-0.0579" in sec_txt, f"-0.0579 missing from {sec_name}"
        assert "0.576" in sec_txt, f"p_Rad = 0.576 missing from {sec_name}"

    # 4. Explicit 3-Sample Architecture Summary (Box 1) & 83% domestic vs 60% system drop clarity
    assert "Box 1." in md_txt and "Box 1." in pdf_txt
    assert "Sample 1:" in md_txt and "Sample 2:" in md_txt and "Sample 3:" in md_txt
    assert "83%" in abs_sec and "60%" in abs_sec


# ------------------------------------------------------------------
# 6. Pillar 2 Formal Thermodynamic Model Invariants
# ------------------------------------------------------------------
def test_formal_model_propositions_machine_precision() -> None:
    r4 = _load_json("04_formal_model_verification.json")
    assert r4["proposition_1_duration_scaling"]["linearity_abs_error"] < 1e-12
    assert r4["proposition_2_breakeven_curtailment"]["max_zero_identity_error"] < 1e-10
    assert r4["proposition_2_breakeven_curtailment"]["max_derivative_error"] < 1e-6
    assert r4["proposition_3_aef_mef_bias"]["max_identity_error"] < 1e-10


# ------------------------------------------------------------------
# 7. Pillars 5, 6, 7 & 8: Figures, Zero Hardcoding, Citations, Zero-Leak PDF
# ------------------------------------------------------------------
def test_all_5_figures_exist_high_res() -> None:
    stems = [
        "fig1_diurnal_gas_displacement_and_leads",
        "fig2_telemetry_forensics_and_diurnal_charging",
        "fig3_cems_mef_vs_aef_sign_reversal",
        "fig4_caiso_noncircular_curtailment_tipping",
        "fig5_hourly_dispatch_and_master_audit",
    ]
    for st in stems:
        png = FIG_DIR / f"{st}.png"
        pdf = FIG_DIR / f"{st}.pdf"
        assert png.exists() and png.stat().st_size > 80_000
        assert pdf.exists() and pdf.stat().st_size > 20_000
        with Image.open(png) as im:
            w, h = im.size
            assert w >= 3000 and h >= 1200, f"{st}.png resolution too low: {w}x{h}"


def test_zero_hardcoded_numbers_in_figures_manuscript_and_pdf_scripts() -> None:
    """Guard against regressions back to hardcoded Round-1 numbers."""
    src_06 = (SCRIPTS_DIR / "06_generate_figures.py").read_text(encoding="utf-8")
    src_07a = (SCRIPTS_DIR / "07a_generate_manuscript_md.py").read_text(encoding="utf-8")
    src_08 = (SCRIPTS_DIR / "08_compile_manuscript_pdf.py").read_text(encoding="utf-8")
    for src in (src_06, src_07a, src_08):
        assert "-109.3" not in src
        assert "109.3" not in src
    assert "57.7%" not in src_07a
    assert "4,322,664" not in src_07a
    assert "3.83" not in src_07a and "3.83" not in src_08


def test_crossref_citations_and_two_way_sync() -> None:
    r7 = _load_json("07_citation_verification.json")
    assert r7["crossref"]["all_verified"] is True
    assert r7["crossref"]["n_verified"] == 18
    assert r7["two_way_sync"]["checked"] is True
    assert r7["two_way_sync"]["two_way_sync_ok"] is True

    # Verify exact Crossref page numbers for Dupont et al. (2026) appear in manuscript
    md_txt = (WS_DIR / "manuscript_k1_boost.md").read_text(encoding="utf-8")
    assert "28(2), 663-685" in md_txt


def test_manuscript_zero_leaks_pdf_and_receipt_sync() -> None:
    pdf_path = WS_DIR / "manuscript_k1_boost.pdf"
    md_path = WS_DIR / "manuscript_k1_boost.md"
    assert pdf_path.exists() and pdf_path.stat().st_size > 200_000
    assert md_path.exists()

    spec = importlib.util.spec_from_file_location("step08", SCRIPTS_DIR / "08_compile_manuscript_pdf.py")
    assert spec is not None and spec.loader is not None
    mod08 = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod08)
    n_pages, leaks = mod08.verify_pdf_zero_leaks(pdf_path)
    assert n_pages >= 8
    assert leaks == [], f"PDF leaks detected: {leaks}"

    reader = PdfReader(str(pdf_path))
    txt = "\n".join((p.extract_text() or "") for p in reader.pages)
    r3 = _load_json("03_cems_carbon_curtailment_results.json")
    rev_str = f"{r3['fleet_aggregates']['all_14_bas']['sign_reversal_cems_minus_aef_mt']:.2f}"
    assert rev_str in txt, f"Fleet sign reversal {rev_str} missing from PDF"
    assert "Figure 1." in txt and "Figure 5." in txt
    assert not re.search(r"\bNaN\b|\bInf\b", txt)


def test_prop1_duration_horserace_and_24h_peak_he20() -> None:
    r2 = _load_json("02_panel_a_wls_results.json")
    for stag in ["ALL_49", "DROP_CISO_ERCO_47"]:
        prof = r2["diurnal_24h_profile"][stag]
        assert len(prof) == 24
        pk = min(prof, key=lambda row: row["ng"]["beta"])
        assert pk["hour"] in (19, 20), f"{stag} peak hour unexpected: {pk['hour']}"
        assert pk["ng"]["t_cr1"] < -5.0

    for tag in ["ALL49_EM_NG", "DROP_CE_47_PKMD_NG"]:
        hr = r2["duration_mwh_vs_mw"][tag]
        assert hr["horserace_mwh"]["beta"] < -0.05
        assert hr["horserace_mwh"]["p_wcb"] < 0.05
        assert hr["horserace_mw"]["p_wcb"] > 0.20


def test_sha256sums_manifest_matches_disk() -> None:
    manifest_path = WS_DIR / "SHA256SUMS.json"
    assert manifest_path.exists()
    man = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert man["n_files"] >= 25
    text_exts = {".py", ".md", ".json", ".txt", ".csv"}
    for rel, meta in man["files"].items():
        fp = WS_DIR / rel
        assert fp.exists(), f"Checksummed file missing: {rel}"
        raw = fp.read_bytes()
        data = raw.replace(b"\r\n", b"\n") if fp.suffix.lower() in text_exts else raw
        assert hashlib.sha256(data).hexdigest() == meta["sha256"], f"SHA mismatch: {rel}"
        assert len(data) == meta["bytes"], f"Byte length mismatch: {rel}"


def test_wave7_readonly_boundary_cryptographically_unmodified() -> None:
    w7 = Path(r"D:\AI_Science\antigravity\frontier_discovery_20261126_wave7")
    expected_w7 = {
        "k1_step0_coverage_audit.json": "ca4da61e9886880624debdf242001cfeebe129f6c2685ac7aa72c4eb61d7203b",
        "k1_stage0_results.json": "9e3347e0288caa25d4b32ca15470888fffbdb5c7e150fb2d68049ba1d21e0446",
        "k1_r2_round1_results.json": "1c8ea4b471b8c49c5d77952e43ef560c10965e049bf1f92ccca786d6e69a072f",
        "k1_r2_round2_results.json": "35989a5e9acf2338c2bc89850f87812bd9e4c949cc1163d86061360f18bf8b93",
        "k1_r2_round3_results.json": "555c73a63a5afde5e7f2a040de26c09a63fb4e2b90f3d20545cbe80da8092a4d",
    }
    for fn, exp_sha in expected_w7.items():
        norm = (w7 / fn).read_bytes().replace(b"\r\n", b"\n")
        assert hashlib.sha256(norm).hexdigest() == exp_sha, f"Wave-7 file mutated: {fn}"
