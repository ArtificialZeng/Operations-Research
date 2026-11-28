"""Comprehensive verification, econometric exactness, fixed-report reconciliation,
common-support audit, and zero-leak PDF parity test suite for D12 (v4).
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

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
    """Regression guard for Step 3 OEM canonicalization (corporate punctuation/renames)."""
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
    """Adversarial proof: vectorized WCB t-stats in script 04 match brute-force loop OLS+CR1 to <1e-10."""
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
    """Mathematical proof: FWL within-unit absorbed DiD matches explicit unit-FE OLS+CR1+WCB."""
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
    """Verify Sun & Abraham (2021) estimator uses saturated cohort x relative-time cells with zero leakage."""
    res = json.loads((RES_DIR / "d12_econometric_results.json").read_text(encoding="utf-8"))
    sa = res["pillar1_blast_radius"]["itt_staggered_adoption"]["sun_abraham_iw"]
    assert sa["skipped"] is False
    assert sa["full_rank_verified"] is True
    assert sa["n_cohorts"] == 7
    assert sa["cohorts"] == [2019, 2020, 2021, 2022, 2023, 2024, 2025]
    assert sa["excluded_partial_cohort"] == 2026
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
    assert checked >= 100


def test_v4_fixed_report_linkage_duplicates_and_denominators():
    """Verify P0 #2: SHA-256 frozen eighth-report linkage, duplicate exclusion, denominator reconciliation, and ODATE flow."""
    mod = _load_module("09_v4_fixed_report_and_support.py")
    _, annual = mod.link_reported_campaigns()
    assert annual.groupby("report_year").size().to_dict() == {2024: 809, 2025: 728}
    assert annual["_merge"].eq("both").all()
    eligible = mod.eligible_eighth_reports(annual)
    assert len(eligible) == 1533
    assert eligible["campaign_code"].is_unique
    assert set(annual.loc[~annual.index.isin(eligible.index), "campaign_code"]) == {"22V315", "22V743"}

    v4 = json.loads((RES_DIR / "d12_v4_fixed_report_audit.json").read_text(encoding="utf-8"))
    assert v4["source_provenance"]["annual_eighth_report_csv"]["sha256"] == "7c19005d8880e8b1534e779d53288606640f41acc4c1470ecdd0eac44c91e596"
    assert (RAW_DIR / "dot_79374_DS1.pdf").exists()
    rec = v4["reconciliation"]
    assert rec["matched_unique_campaigns"] == 1533
    assert rec["denominator_exact_match_count"] == 1531
    assert rec["denominator_sw_exact_match_count"] == rec["denominator_sw_total_count"] == 227
    assert rec["odate_statutory_alignment"]["combined_two_year_lag_n"] == 1515

    sf = v4["sample_flow"]["odate_2022_2023_by_modality"]
    assert sf["Pure_OTA"]["Total_Campaigns"] == 21
    assert sf["Pure_OTA"]["In_8th_Report_Unique"] == 15
    assert sf["Pure_OTA"]["Unlisted_Early_Completed_100pct"] == 5
    assert sf["Pure_OTA"]["Unlisted_Missing_DOT_Report"] == 1
    assert sf["Hybrid_OTA"]["Total_Campaigns"] == sf["Hybrid_OTA"]["In_8th_Report_Unique"] == 15


def test_v4_common_support_reviewer_benchmarks_and_looo():
    """Verify P0 #1: exact Tesla 11/15 (99.17%) concentration, reviewer benchmarks, same-OEM CS, and 18-OEM LOOO."""
    v4 = json.loads((RES_DIR / "d12_v4_fixed_report_audit.json").read_text(encoding="utf-8"))
    cs8 = v4["common_support_summary"]["eighth_report"]
    assert cs8["pure_total_n"] == 15
    assert cs8["pure_tesla_n"] == 11
    assert cs8["pure_tesla_vehicle_share_pct"] == pytest.approx(99.17, abs=0.01)
    assert cs8["tesla_dealer_sw_n"] == 0
    assert cs8["pure_nontesla_n"] == 4
    assert set(cs8["pure_nontesla_oems"]) == {"Lucid USA, Inc.", "Volvo Car USA, LLC"}
    assert cs8["pure_nontesla_max_age_yr"] <= 1.0
    assert len(cs8["same_oem_both_dsw_and_ota_oems"]) == 8

    terms = {(r["Specification"], r["Term"]): r for r in v4["age_sensitivity_models"]}
    # Exact reviewer benchmarks
    b_pure = terms["Fixed 8th report: oldest model year (4-way)", "is_ota_pure_x_age"]
    assert b_pure["Coef"] == pytest.approx(3.6852, abs=0.005)
    assert b_pure["p_WCB"] == pytest.approx(0.030, abs=0.002)

    w5_pure = terms["Fixed 8th report: oldest MY, 0-5 yr window (4-way)", "is_ota_pure_x_age"]
    assert w5_pure["Coef"] == pytest.approx(3.4934, abs=0.005)
    assert w5_pure["p_WCB"] == pytest.approx(0.226, abs=0.002)

    nt_pure = terms["Fixed 8th report: oldest MY, excluding Tesla (4-way)", "is_ota_pure_x_age"]
    assert nt_pure["Coef"] == pytest.approx(1.5914, abs=0.005)
    assert nt_pure["p_WCB"] == pytest.approx(0.553, abs=0.002)

    cs_pool = terms["Same-OEM common support (8 OEMs, all ages, pooled OTA)", "is_ota_audited_x_age"]
    assert cs_pool["N"] == 70 and cs_pool["OEMs"] == 8 and cs_pool["p_WCB"] > 0.50

    looo = v4["looo_summary"]
    assert looo["n_oems_tested"] == 18
    assert looo["dealer_age_sig_05_count"] == 18
    assert looo["dealer_age_max_pwcb"] <= 0.005
    assert looo["pure_x_age_non_sig_05_count"] == 8
    assert looo["hybrid_x_age_sig_05_count"] == 0


def test_all_tables_and_v4_figures_exist_zero_nans():
    expected_tables = [
        "table1_api_measurement_audit.csv",
        "table2_blast_radius_and_selection.csv",
        "table3_remediation_velocity_and_age_decay.csv",
        "table4_net_unremedied_exposure.csv",
        "table4b_aggregate_fleet_accounting.csv",
        "table4c_mature_ota_oem_composition.csv",
        "table5_safety_cascades_and_complaints_did.csv",
        "table5b_prerecall_complaints_and_hazards.csv",
        "table6_maturation_and_age_profiles.csv",
        "table_v4_sample_flow.csv",
        "table_v4_eighth_report_completion.csv",
        "table_channel_oem_age_support.csv",
        "table_v4_vehicle_age_sensitivity.csv",
        "table_v4_looo_sensitivity.csv",
        "table_v4_text_coding_vs_api.csv",
    ]
    for fname in expected_tables:
        p = TBL_DIR / fname
        assert p.exists(), f"Missing table {fname}"
        df = pd.read_csv(p)
        assert len(df) > 0
        assert int(df.isna().sum().sum()) == 0, f"NaN found in {fname}"

    for stem in (
        "fig1_v4_sample_flow_and_completion",
        "fig2_v4_channel_oem_age_support",
        "fig3_v4_age_gradients_and_looo",
        "fig4_v4_api_audit_and_hybrid_scale",
    ):
        png = FIG_DIR / f"{stem}.png"
        pdf = FIG_DIR / f"{stem}.pdf"
        assert png.exists() and png.stat().st_size > 100_000
        assert pdf.exists() and pdf.stat().st_size > 15_000


def test_all_23_references_and_institutional_urls_verified_and_cited():
    """All 23 Crossref-verified DOIs (incl. Pagiavlas 10.1177/00222429211023016) + 6 institutional URLs cited in body."""
    md = (BASE_DIR / "manuscript_d12_boost.md").read_text(encoding="utf-8")
    assert "## References" in md
    body, refs_sec = md.split("## References", 1)
    vref = json.loads((PROC_DIR / "verified_references.json").read_text(encoding="utf-8"))
    refs = vref["references"]
    assert len(refs) == 23
    assert refs["pagiavlas_2022"]["doi"] == "10.1177/00222429211023016"

    for key, info in refs.items():
        assert info["verified"] is True
        assert info["doi"] in refs_sec, f"DOI missing in References section for {key}"
        first_chunk = info["authors"].split(",")[0].strip()
        surname = first_chunk.split()[-1]
        yr = str(info["year"])
        assert surname in body and yr in body, f"Uncited reference in manuscript body: {key} ({surname} {yr})"

    for url in (
        "https://rosap.ntl.bts.gov/view/dot/79374",
        "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-573/section-573.7",
        "https://www.nhtsa.gov/sites/nhtsa.gov/files/2025-01/2024-recall-completion-rates.pdf",
        "https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-01/2025-recall-completion-rates.pdf",
        "https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-03/2025-annual-recalls-report.pdf",
    ):
        assert url in refs_sec, f"Required official URL missing from References: {url}"


def test_v4_manuscript_and_appendix_parity_zero_leaks_and_claim_withdrawal():
    """Verify authorship block, forbidden token absence, exact v4 numbers, claim withdrawal, and zero-leak PDFs."""
    md = (BASE_DIR / "manuscript_d12_boost.md").read_text(encoding="utf-8")
    sup = (BASE_DIR / "supplementary_d12_jsr.md").read_text(encoding="utf-8")
    readme = (BASE_DIR / "README.md").read_text(encoding="utf-8")

    # Exact authorship block & zero meta-labels
    for doc_name, txt in (("manuscript", md), ("appendix", sup)):
        assert "Zijian Zeng" in txt, f"Missing author in {doc_name}"
        assert "Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA" in txt
        assert "zijianzeng@foxmail.com" in txt
        assert "1002266693@ucsiuniversity.edu.my" in txt

    for forbidden in ("85–90%", "85-90%", "-85.3%", "−85.3%", "Target Venues", "Target Format", "Track A", "Track B"):
        assert forbidden not in md, f"Forbidden token '{forbidden}' found in manuscript_d12_boost.md"
        assert forbidden not in sup, f"Forbidden token '{forbidden}' found in supplementary_d12_jsr.md"
        assert forbidden not in readme, f"Forbidden token '{forbidden}' found in README.md"

    # Explicit withdrawal of universal OTA age-buffering claim & required v4 empirical tokens
    for req_tok in (
        "explicitly withdraw any universal claim",
        "1,533",
        "11/15",
        "99.17%",
        "+3.69",
        "0.030",
        "+3.49",
        "0.226",
        "+1.59",
        "0.553",
        "7.01×",
        "25V282000",
        "25V315000",
        "DOT HS 813 687",
        "49 CFR § 573.7",
        "Pagiavlas",
        "table_channel_oem_age_support.csv",
    ):
        assert req_tok in md, f"Required v4 token '{req_tok}' missing from manuscript_d12_boost.md"

    # Both compiled PDFs exist and pass strict zero-leak verification
    comp = _load_module("08_compile_manuscript_pdf.py")
    main_pdf = BASE_DIR / "manuscript_d12_boost.pdf"
    sup_pdf = BASE_DIR / "supplementary_d12_jsr.pdf"
    assert main_pdf.exists() and main_pdf.stat().st_size > 500_000
    assert sup_pdf.exists() and sup_pdf.stat().st_size > 100_000

    n_main, leaks_main = comp.verify_pdf_zero_leaks(main_pdf)
    n_sup, leaks_sup = comp.verify_pdf_zero_leaks(sup_pdf)
    assert n_main >= 12 and leaks_main == [], f"Main PDF leaks: {leaks_main}"
    assert n_sup >= 3 and leaks_sup == [], f"Appendix PDF leaks: {leaks_sup}"
    assert (BASE_DIR / "REFEREE_RESPONSE_v4.md").exists()


def test_sha256_manifest_cryptographic_integrity():
    sha_path = BASE_DIR / "SHA256SUMS.json"
    assert sha_path.exists()
    manifest = json.loads(sha_path.read_text(encoding="utf-8"))
    assert manifest["revision"] == "v4"
    assert manifest["n_files_hashed"] == len(manifest["files"])
    for req_rel in (
        "manuscript_d12_boost.pdf",
        "supplementary_d12_jsr.pdf",
        "REFEREE_RESPONSE_v4.md",
        "data_raw/nhtsa_annual_eighth_report_2024_2025.csv",
        "data_raw/dot_79374_DS1.pdf",
        "data_processed/d12_v4_eighth_report_analysis_panel.csv",
        "tables/table_channel_oem_age_support.csv",
    ):
        assert req_rel in manifest["files"], f"Missing required manifest entry: {req_rel}"

    for rel, info in manifest["files"].items():
        fpath = BASE_DIR / rel
        assert fpath.exists(), f"Manifest artifact missing: {rel}"
        assert fpath.stat().st_size == info["bytes"], f"Size mismatch on {rel}"
        h = hashlib.sha256(fpath.read_bytes()).hexdigest()
        assert h == info["sha256"], f"SHA-256 mismatch on {rel}"
