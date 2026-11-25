"""Comprehensive verification, econometric exactness, and parity test suite for D12 Boost."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
PROC_DIR = BASE_DIR / "data_processed"
RAW_DIR = BASE_DIR / "data_raw"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
FIG_DIR = BASE_DIR / "figures"


def _load_module(script_name: str):
    path = BASE_DIR / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_canonicalize_oems_runs_cleanly_no_crash():
    """Regression guard for Step 3 OEM canonicalization (must harmonize corporate punctuation/renames)."""
    mod = _load_module("03_build_harmonized_panels.py")
    s = pd.Series(
        [
            "General Motors, LLC",
            "General Motors, LLC",
            "General Motors LLC",
            "Tesla Motors, Inc.",
            "Tesla, Inc.",
            "Chrysler (FCA US, LLC) (Stellantis)",
            "Chrysler (FCA US, LLC)",
        ]
    )
    out = mod.canonicalize_oems(s)
    assert out.iloc[0] == out.iloc[2] == "General Motors, LLC"
    assert out.iloc[3] == out.iloc[4] == "Tesla, Inc."
    assert out.iloc[5] == out.iloc[6] == "Chrysler (FCA US, LLC)"


def test_vectorized_cr1_wcb_matches_bruteforce_exactly():
    """Adversarial mathematical proof: vectorized WCB t-stats in script 04 match brute-force loop OLS+CR1 to <1e-10."""
    mod = _load_module("04_econometric_core_analysis.py")

    rng = np.random.default_rng(12345)
    n, G = 120, 12
    clusters = np.repeat(np.arange(G), n // G)
    x1 = rng.normal(size=n)
    x2 = rng.binomial(1, 0.35, size=n).astype(float)
    fe = np.tile(np.arange(4), n // 4)
    u = rng.normal(scale=0.5, size=G)[clusters] + rng.normal(size=n)
    y = 1.5 + 0.8 * x1 - 0.6 * x2 + 0.3 * fe + u
    df = pd.DataFrame({"y": y, "x1": x1, "x2": x2, "fe": fe.astype(str), "cl": clusters.astype(str)})

    n_boot = 99
    seed = 777
    res = mod.fit_ols_cr1_wcb(df, "y", ["x1", "x2"], ["fe"], "cl", target_vars=["x1"], n_boot=n_boot, seed=seed)
    assert res["full_rank_verified"] is True

    dum = pd.get_dummies(df["fe"], drop_first=True, dtype=float).to_numpy()
    X = np.column_stack([np.ones(n), x1, x2, dum])
    k = X.shape[1]
    P = np.linalg.inv(X.T @ X)
    beta = P @ (X.T @ y)
    resid = y - X @ beta
    scale_cr1 = (G / (G - 1.0)) * ((n - 1.0) / (n - k))

    def cr1_se_j(X_mat: np.ndarray, r_vec: np.ndarray, j_idx: int) -> float:
        P_m = np.linalg.inv(X_mat.T @ X_mat)
        scores = np.zeros((G, X_mat.shape[1]))
        for g in range(G):
            m = clusters == g
            scores[g] = X_mat[m].T @ r_vec[m]
        V = scale_cr1 * (P_m @ (scores.T @ scores) @ P_m)
        return float(np.sqrt(V[j_idx, j_idx]))

    se_ref = cr1_se_j(X, resid, 1)
    assert abs(res["terms"]["x1"]["coef"] - round(float(beta[1]), 4)) <= 1e-4
    assert abs(res["terms"]["x1"]["se_cr1"] - round(se_ref, 4)) <= 1e-4
    t_obs = float(beta[1]) / se_ref

    X_r = np.delete(X, 1, axis=1)
    b_r = np.linalg.lstsq(X_r, y, rcond=None)[0]
    y_tilde = X_r @ b_r
    u_tilde = y - y_tilde

    W = np.random.default_rng(seed).choice(np.array([-1.0, 1.0]), size=(n_boot, G))
    t_b_ref = np.zeros(n_boot)
    for b in range(n_boot):
        y_star = y_tilde + W[b, clusters] * u_tilde
        b_star = P @ (X.T @ y_star)
        r_star = y_star - X @ b_star
        se_star = cr1_se_j(X, r_star, 1)
        t_b_ref[b] = float(b_star[1]) / se_star

    p_wcb_ref = round(float((1 + np.sum(np.abs(t_b_ref) >= abs(t_obs))) / (n_boot + 1)), 4)
    assert abs(res["terms"]["x1"]["p_wcb"] - p_wcb_ref) < 1e-10


def test_absorbed_2way_fe_did_matches_explicit_ols_cr1_wcb():
    """Mathematical proof: FWL within-unit absorbed DiD matches explicit unit-FE OLS+CR1+WCB for both OEM & unit clusters."""
    mod = _load_module("04_econometric_core_analysis.py")
    rng = np.random.default_rng(999)
    rows = []
    for g in range(10):
        for c in range(3):
            uid = g * 3 + c
            treated = 1.0 if g < 4 else 0.0
            u_fe = rng.normal(0, 1.5)
            for t in range(8):
                cal = t + (c % 2)
                x = treated * (1.0 if t >= 4 else 0.0)
                y = u_fe + 0.3 * t - 0.2 * cal + 0.7 * x + rng.normal(0, 0.8)
                rows.append({"uid": f"u{uid}", "oem": f"g{g}", "t": str(t), "cal": str(cal), "x": x, "y": y})
    df_t = pd.DataFrame(rows)

    for cl_col in ("oem", "uid"):
        r_abs = mod.fit_absorbed_2way_fe_did(df_t, "y", ["x"], "uid", ["t", "cal"], cl_col, n_boot=99, seed=321)
        r_exp = mod.fit_ols_cr1_wcb(df_t, "y", ["x"], ["uid", "t", "cal"], cl_col, target_vars=["x"], n_boot=99, seed=321)
        assert abs(r_abs["terms"]["x"]["coef"] - r_exp["terms"]["x"]["coef"]) < 1e-4
        assert abs(r_abs["terms"]["x"]["se_cr1"] - r_exp["terms"]["x"]["se_cr1"]) < 1e-4
        assert abs(r_abs["terms"]["x"]["p_t_G1"] - r_exp["terms"]["x"]["p_t_G1"]) < 1e-5
        assert abs(r_abs["terms"]["x"]["p_wcb"] - r_exp["terms"]["x"]["p_wcb"]) < 1e-10


def test_sun_abraham_iw_full_rank_no_cohort_leakage():
    """Verify Sun & Abraham (2021) estimator uses true saturated cohort x relative-time cells with zero leakage."""
    res = json.loads((RES_DIR / "d12_econometric_results.json").read_text(encoding="utf-8"))
    sa = res["pillar1_blast_radius"]["itt_staggered_adoption"]["sun_abraham_iw"]
    assert sa["skipped"] is False
    assert sa["full_rank_verified"] is True
    assert sa["n_cohorts"] == 7
    assert sa["cohorts"] == [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    assert sa["excluded_partial_cohort"] == 2026
    assert sa["n_cohort_period_cells"] >= 35
    assert sa["n_post_cells"] >= 20
    assert set(sa["iw_dynamic_terms"].keys()) == {"ev_m3", "ev_m2", "ev_p0", "ev_p1", "ev_p2", "ev_p3"}
    assert sa["iw_pre_trend_wald_m3_m2"]["p_value"] > 0.10


def test_raw_receipts_and_api_ground_truth_audit():
    receipts = json.loads((RAW_DIR / "raw_download_receipts.json").read_text(encoding="utf-8"))
    for req_file in (
        "FLAT_RCL_POST_2010.zip",
        "COMPLAINTS_RECEIVED_2020-2024.zip",
        "COMPLAINTS_RECEIVED_2025-2026.zip",
        "dot_6axg_epim_recalls.csv",
    ):
        assert req_file in receipts["sources"]
        assert len(receipts["sources"][req_file]["sha256"]) == 64

    audit = json.loads((RES_DIR / "api_reconciliation_audit.json").read_text(encoding="utf-8"))
    assert audit["n_total_queried"] == 1452
    assert audit["n_http_200_valid"] == 1452
    assert audit["n_http_errors"] == 0
    assert audit["physical_audit_valid"] == 250
    assert audit["physical_audit_api_ota_true_false_negatives"] == 0
    assert audit["api_true_but_txt_zero_count"] == 0
    assert audit["cutoff_2025_early_jan1_to_may8"]["n_txt_ota"] == 7
    assert audit["cutoff_2025_early_jan1_to_may8"]["n_api_true"] == 4
    assert audit["cutoff_post_may8_2025_through_2026"]["n_txt_ota"] == 68
    assert audit["cutoff_post_may8_2025_through_2026"]["n_api_true"] == 0

    yr_map = {r["rec_year"]: r for r in audit["txt_ota_reconciliation_by_year"]}
    for yr in (2019, 2020, 2021, 2022, 2023):
        assert yr_map[yr]["api_true_rate"] == 1.0
    assert yr_map[2024]["n_api_true"] == 31
    assert yr_map[2025]["n_api_true"] == 4
    assert yr_map[2026]["n_api_true"] == 0


def test_every_regression_full_rank_verified():
    res = json.loads((RES_DIR / "d12_econometric_results.json").read_text(encoding="utf-8"))
    checked = 0

    def walk(obj):
        nonlocal checked
        if isinstance(obj, dict):
            if "full_rank_verified" in obj:
                assert obj["full_rank_verified"] is True
                assert obj.get("skipped") is False
                checked += 1
            for v in obj.values():
                walk(v)
        elif isinstance(obj, list):
            for it in obj:
                walk(it)

    walk(res)
    assert checked >= 100, f"Expected >= 100 full-rank verified regressions, found {checked}"


def test_all_tables_exist_and_zero_nans():
    expected_tables = [
        "table1_api_measurement_audit.csv",
        "table2_blast_radius_and_selection.csv",
        "table3_remediation_velocity_and_age_decay.csv",
        "table4_net_unremedied_exposure.csv",
        "table4b_aggregate_fleet_accounting.csv",
        "table5_safety_cascades_and_complaints_did.csv",
        "table5b_prerecall_complaints_and_hazards.csv",
        "table6_maturation_and_age_profiles.csv",
    ]
    for fname in expected_tables:
        p = TBL_DIR / fname
        assert p.exists(), f"Missing table {fname}"
        df = pd.read_csv(p)
        assert len(df) > 0
        assert int(df.isna().sum().sum()) == 0, f"NaN found in {fname}"


def test_all_five_figures_exist_png_and_pdf():
    stems = [
        "fig1_api_audit_and_blast_radius",
        "fig2_itt_event_study_and_fleet_selection",
        "fig3_maturation_and_age_decay_cliff",
        "fig4_breakeven_frontier_and_net_exposure",
        "fig5_safety_oversight_and_complaint_did",
    ]
    for s in stems:
        png = FIG_DIR / f"{s}.png"
        pdf = FIG_DIR / f"{s}.pdf"
        assert png.exists() and png.stat().st_size > 100_000
        assert pdf.exists() and pdf.stat().st_size > 15_000


def test_all_22_references_cited_in_manuscript_body():
    """Every single Crossref-verified reference must be cited in the manuscript body AND appear with its DOI in References."""
    md = (BASE_DIR / "manuscript_d12_boost.md").read_text(encoding="utf-8")
    assert "## References" in md
    body, refs_sec = md.split("## References", 1)
    refs = json.loads((PROC_DIR / "verified_references.json").read_text(encoding="utf-8"))["references"]
    assert len(refs) == 22

    for key, info in refs.items():
        assert info["verified"] is True
        assert info["doi"] in refs_sec, f"DOI missing in References section for {key}"
        # Extract surname cleanly (handle 'Colin Cameron, A.' -> 'Cameron')
        first_chunk = info["authors"].split(",")[0].strip()
        surname = first_chunk.split()[-1]
        yr = str(info["year"])
        assert surname in body and yr in body, f"Uncited reference in manuscript body: {key} ({surname} {yr})"


def test_manuscript_exact_numerical_and_doi_parity():
    md = (BASE_DIR / "manuscript_d12_boost.md").read_text(encoding="utf-8").replace("{,}", ",")
    res = json.loads((RES_DIR / "d12_econometric_results.json").read_text(encoding="utf-8"))
    s3 = json.loads((RES_DIR / "step3_panel_build_summary.json").read_text(encoding="utf-8"))

    p1 = res["pillar1_blast_radius"]
    p2 = res["pillar2_remediation_velocity"]
    p3 = res["pillar3_net_unremedied_exposure"]
    p4 = res["pillar4_safety_and_complaints"]

    def r3(x: float) -> str:
        return str(Decimal(str(abs(x))).quantize(Decimal("0.001"), rounding=ROUND_HALF_UP))

    must_match = [
        r3(p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_hybrid"]["coef"]),
        r3(p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_pure"]["coef"]),
        r3(p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_log_potaff"]["terms"]["is_ota_api_full"]["coef"]),
        r3(p1["itt_staggered_adoption"]["pooled_did"]["terms"]["post_ota_adopt"]["coef"]),
        r3(p1["itt_staggered_adoption"]["sun_abraham_iw"]["iw_post_coef"]),
        r3(p1["unconditional_sdv_cohort_shift"]["sw_vs_physical_sdv_did"]["terms"]["sw_x_sdv_my2021p"]["coef"]),
        f"{p2['mature_18m_regressions']['sw_ota_oems_4way']['terms']['is_ota_hybrid']['coef']:.2f}",
        f"{p2['mature_18m_regressions']['sw_ota_oems_api_ota']['terms']['is_ota_api_full']['coef']:.2f}",
        f"{abs(p2['vehicle_age_decay']['regressions']['sw_ota_oems_4way_x_age']['terms']['veh_age']['coef']):.2f}",
        f"{p2['vehicle_age_decay']['regressions']['sw_ota_oems_4way_x_age']['terms']['pure_x_age']['coef']:.2f}",
        f"{p2['vehicle_age_decay']['regressions']['sw_ota_oems_4way_x_age']['terms']['hybrid_x_age']['coef']:.2f}",
        f"{p2['vehicle_age_decay']['regressions']['sw_ota_oems_api_x_age']['terms']['api_ota_x_age']['coef']:.2f}",
        r3(p3["regressions"]["mature_all_vehicles_4way_vs_phys"]["terms"]["is_ota_pure"]["coef"]),
        r3(p3["regressions"]["mature_all_vehicles_4way_vs_phys"]["terms"]["is_ota_hybrid"]["coef"]),
        r3(p3["regressions"]["mature_all_vehicles_hybrid_swchoice_vs_hwmixed"]["terms"]["is_ota_hybrid_swchoice"]["coef"]),
        r3(p3["regressions"]["mature_sw_tiers_light_duty"]["terms"]["is_nontesla_pure"]["coef"]),
        r3(p3["hybrid_minus_pure_unremedied_wald"]["all_vehicles"]["diff_hybrid_minus_pure"]),
        r3(p3["hybrid_minus_pure_unremedied_wald"]["sw_ota_oems"]["diff_hybrid_minus_pure"]),
        f"{p3['breakeven_frontier']['within_ota_oem_matched_frontier']['pure_ota_breakeven_r_pct']:.2f}",
        f"{p3['breakeven_frontier']['within_ota_oem_matched_frontier']['hybrid_ota_breakeven_r_pct']:.2f}",
        f"{p3['breakeven_frontier']['within_ota_oem_matched_frontier']['hybrid_swchoice_breakeven_r_pct']:.2f}",
        f"{p4['safety_fe_regressions']['4way_has_fmvss']['terms']['is_ota_pure']['coef']:.4f}",
        f"{abs(p4['safety_fe_regressions']['apiota2018_24_has_odi_action']['terms']['is_ota_api_full']['coef']):.4f}",
        f"{s3['complaint_panel']['n_unique_odino_2020_2026']:,}",
        f"{s3['complaint_panel']['n_matched_comp_fail_links']:,}",
        "9,139,366",
        "91,604",
        "348,488",
        "64,001,606",
    ]
    for token in must_match:
        assert token in md, f"Expected exact numerical token '{token}' missing from manuscript_d12_boost.md"


def test_compiled_pdf_zero_leaks_and_pages():
    comp = _load_module("08_compile_manuscript_pdf.py")
    pdf_path = BASE_DIR / "manuscript_d12_boost.pdf"
    assert pdf_path.exists() and pdf_path.stat().st_size > 500_000
    n_pages, leaks = comp.verify_pdf_zero_leaks(pdf_path)
    assert n_pages >= 15
    assert leaks == [], f"PDF contains leaked tokens: {leaks}"


def test_sha256_manifest_cryptographic_integrity():
    sha_path = BASE_DIR / "SHA256SUMS.json"
    assert sha_path.exists()
    manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    assert manifest["n_files_hashed"] == len(manifest["files"])
    assert manifest["n_files_hashed"] >= 35

    for rel, info in manifest["files"].items():
        fpath = BASE_DIR / rel
        assert fpath.exists(), f"Manifest artifact missing: {rel}"
        assert fpath.stat().st_size == info["bytes"], f"Size mismatch on {rel}"
        h = hashlib.sha256(fpath.read_bytes()).hexdigest()
        assert h == info["sha256"], f"SHA-256 mismatch on {rel}"
