"""Comprehensive automated verification suite for J6 v4 (Environmental Science & Technology).

Verifies:
  1. Exact FWL vs brute-force explicit LSDV OLS + CR1 + WCB equivalence to atol=1e-11
     and exact bipartite connected-component nested-FE DOF rank.
  2. Zero NaN/Inf across all 8 JSON receipts (00..04, 07, 10, 11) and processed parquets.
  3. Pillar 0 external enrichment integrity (NOAA HMS 100% coverage, Census 3,144 counties,
     EPA official workbooks).
  4. Supporting Information screening-level Appendix N reconciliation & demographic audit.
  5. Exogenous DV_18_20 nulls on Margins A, C, and D.
  6. Same-rooftop 2023-2025 paired annual DV sensitivity (T640_FW positive; BAM null).
  7. EIV-robust wildfire smoke amplification across 3 instruments (BAM null).
  8. Observational EPA CSN/IMPROVE speciation & meteorology associations (OC+, OCxHMS+, EC-, RH+).
  9. Fixed EPA-concurrence coding identity (49.9% false-positive removal).
 10. Archival EE flagging diagnostics & within-county-year FE null (p_WCB = 0.931).
 11. Formal Section 2 metrology model verification.
 12. 100% live Crossref DOI verification (15/15 incl. Long 2023, McClure 2026, Krupnick 2025,
     Cameron-Gelbach-Miller 2011) & two-way citation sync (21/21).
 13. All 4 Main ES&T + 2 SI publication figures (300 DPI PNG width >= 3000px & vector PDFs).
 14. Official EPA April 2024 Tier-1 replay (123 vs 89 across 468 pairs, +7.26 pp [+4.15, +10.38]
     national block & [+3.43, +11.10] two-way Site x Region-Episode; BAM 84 vs 84).
 15. P0 #1 Common-Support Audit (exact 4 Heavy triples, 27 shared dates, 401 all-day triples,
     overlap-matched & overlap-weighted differentials > 0, BAM demoted to background reference).
 16. P0 #2 Strictly Out-of-Time Prospective Rolling 5-Yr EPA Tier-1 Replays (OOT-A/B/B2/C all
     unidirectionally positive 26-33 vs 0, two-way p <= 0.0021; BAM null; clean-site med|e|=0.000).
 17. P1 #3 & P1 #4 Equal-Concentration Non-Smoke vs Smoke controls, Ground-Level Smoke confirmation
     (OC>=5 & FRM>p90), Leave-EPA-Region-Out, Zero-Leak ES&T Main (12p) & SI (4p) PDFs, Exact
     Authorship Block, Reproducible tables/ exports, and REFEREE_RESPONSE_v4.md.
"""

from __future__ import annotations

import importlib.util
import json
import math
import re
import struct
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WS_DIR = Path(r"D:\AI_Science\antigravity\j6_boost_epa_pm25_t640_naaqs_20261126")
SCRIPTS_DIR = WS_DIR / "scripts"
TABLES_DIR = WS_DIR / "tables"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from econ_utils import FIG_DIR, PROC_DIR, RES_DIR, count_fe_dof_exact, ols_cr1


def _load_json(name: str) -> dict:
    return json.loads((RES_DIR / name).read_text(encoding="utf-8"))


def _assert_finite_tree(obj: object, path: str = "$") -> None:
    if isinstance(obj, float):
        assert math.isfinite(obj), f"Non-finite float {obj!r} at {path}"
    elif isinstance(obj, dict):
        for k, v in obj.items():
            _assert_finite_tree(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _assert_finite_tree(v, f"{path}[{i}]")


def test_01_fwl_vs_brute_force_lsdv_wcb_and_nested_fe_dof() -> None:
    """Prove exact nested-FE DOF rank and brute-force LSDV OLS/CR1/WCB equivalence."""
    rng = np.random.default_rng(42)
    rows = []
    for st in range(5):
        for u_local in range(4):
            uid = st * 4 + u_local
            for yr in range(4):
                if uid == 3 and yr == 2:
                    continue
                rows.append((uid, st, yr, f"{st}_{yr}"))
    df = pd.DataFrame(rows, columns=["unit", "state", "year", "state_yr"])
    n = len(df)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    u_eff = rng.normal(size=20)[df["unit"].to_numpy()]
    sy_codes, _ = pd.factorize(df["state_yr"], sort=False)
    sy_eff = rng.normal(size=20)[sy_codes]
    y = 1.75 * x1 - 0.85 * x2 + u_eff + sy_eff + rng.normal(scale=0.5, size=n)

    X = np.column_stack([x1, x2])
    fe_u = df["unit"].to_numpy()
    fe_sy = df["state_yr"].to_numpy()
    cl = df["unit"].to_numpy()

    Du = pd.get_dummies(fe_u, dtype=float).to_numpy()
    Dsy = pd.get_dummies(fe_sy, dtype=float).to_numpy()
    D_full = np.hstack([Du, Dsy])
    rank_exact = int(np.linalg.matrix_rank(D_full))
    assert rank_exact == 20 + 20 - 5
    assert count_fe_dof_exact([fe_u, fe_sy]) == rank_exact

    seed = 98765
    B = 199
    res_fwl = ols_cr1(
        y, X, cl, fe_groups=[fe_u, fe_sy], col_names=["x1", "x2"], wcb_var_idx=0, wcb_B=B, seed=seed
    )
    assert res_fwl["fe_dof"] == rank_exact

    U_svd, s_svd, _ = np.linalg.svd(D_full, full_matrices=False)
    Q = U_svd[:, s_svd > 1e-10]
    Z = np.hstack([X, Q])
    k_tot = Z.shape[1]
    ZtZ_inv = np.linalg.inv(Z.T @ Z)
    b_lsdv = ZtZ_inv @ (Z.T @ y)
    e_lsdv = y - Z @ b_lsdv

    cl_codes, cl_uniq = pd.factorize(cl, sort=False)
    G = len(cl_uniq)
    Sg = np.zeros((G, k_tot))
    np.add.at(Sg, cl_codes, Z * e_lsdv[:, None])
    scale = (G / (G - 1.0)) * ((n - 1.0) / (n - k_tot))
    V_lsdv = scale * (ZtZ_inv @ (Sg.T @ Sg) @ ZtZ_inv)
    se_lsdv = np.sqrt(np.diag(V_lsdv))
    t_lsdv = b_lsdv[:2] / se_lsdv[:2]

    np.testing.assert_allclose(res_fwl["coefs"]["x1"]["beta"], b_lsdv[0], atol=1e-11)
    np.testing.assert_allclose(res_fwl["coefs"]["x2"]["beta"], b_lsdv[1], atol=1e-11)
    np.testing.assert_allclose(res_fwl["coefs"]["x1"]["se_cr1"], se_lsdv[0], atol=1e-11)
    np.testing.assert_allclose(res_fwl["coefs"]["x1"]["t_cr1"], t_lsdv[0], atol=1e-11)

    Zr = Z[:, 1:]
    br_lsdv = np.linalg.lstsq(Zr, y, rcond=None)[0]
    yhat_r = Zr @ br_lsdv
    er = y - yhat_r

    rng_b = np.random.default_rng(seed)
    t_boot_lsdv = np.empty(B)
    for b in range(B):
        w_g = rng_b.choice([-1.0, 1.0], size=G)
        y_star = yhat_r + er * w_g[cl_codes]
        b_s = ZtZ_inv @ (Z.T @ y_star)
        r_s = y_star - Z @ b_s
        Sg_s = np.zeros((G, k_tot))
        np.add.at(Sg_s, cl_codes, Z * r_s[:, None])
        V_s = scale * (ZtZ_inv @ (Sg_s.T @ Sg_s) @ ZtZ_inv)
        t_boot_lsdv[b] = b_s[0] / np.sqrt(V_s[0, 0])

    p_wcb_lsdv = float((1 + np.sum(np.abs(t_boot_lsdv) >= abs(t_lsdv[0]))) / (B + 1))
    assert res_fwl["wcb"]["p_wcb"] == pytest.approx(p_wcb_lsdv, abs=1e-12)


def test_02_zero_nan_across_all_receipts() -> None:
    expected = [
        "00_enrichment_audit.json",
        "01_appn_audit.json",
        "02_collocated_physics_speciation.json",
        "03_ee_triage_hms_unification.json",
        "04_formal_model_verification.json",
        "07_citations_verified.json",
        "10_official_tier_replay.json",
        "11_v4_est_comprehensive_audit.json",
    ]
    for fname in expected:
        p = RES_DIR / fname
        assert p.exists(), f"Missing receipt {fname}"
        txt = p.read_text(encoding="utf-8")
        assert "NaN" not in txt and "Infinity" not in txt
        _assert_finite_tree(json.loads(txt), path=fname)


def test_03_enrichment_audit_integrity() -> None:
    r0 = _load_json("00_enrichment_audit.json")
    hms = r0["noaa_hms_2018_2025"]
    by_yr = hms["by_year"]
    assert sum(v["days_ok"] for v in by_yr.values()) == 2922
    assert sum(v["days_404"] for v in by_yr.values()) == 0
    assert sum(v["days_err"] for v in by_yr.values()) == 0
    assert hms["total_smoke_site_days"] > 1_000_000
    assert hms["total_heavy_site_days"] > 50_000


def test_04_si_stitched_appn_reconciliation_and_ej() -> None:
    r1 = _load_json("01_appn_audit.json")
    assert r1["stitch_audit"]["n_split_2023_t640_monitors_repaired"] >= 400
    cs11 = r1["accounting"]["combined_site_reg_appn_11of12"]
    wf = cs11["matched_2123_waterfall"]
    assert wf["flip_t640_alone"]["counties"] == 47
    epa21 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2021_2023_final_08_08_24_0.xlsx"]
    assert epa21["overlap_epa_with_cs_reg_incl"] / epa21["combined_site_reg_na_incl"] >= 0.95


def test_05_exogenous_dv1820_nulls_margins_acd() -> None:
    r1 = _load_json("01_appn_audit.json")
    nulls = r1["exogenous_nulls_margins_acd"]
    assert nulls["margin_d_frm_exog_dv1820_county_cr1"]["wcb"]["p_wcb"] > 0.20
    assert nulls["margin_a_share_fem_exog_dv1820"]["wcb"]["p_wcb"] > 0.15
    assert nulls["margin_c_monitor_survival_exog_dv1820"]["wcb"]["p_wcb"] > 0.20


def test_06_rooftop_dv_sensitivity() -> None:
    r2 = _load_json("02_collocated_physics_speciation.json")
    assert r2["method_code_audit"]["t640_fw_method_codes"] == ["636", "638"]
    assert r2["method_code_audit"]["bam_method_codes"] == ["170", "209"]
    rt_t = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_b = r2["rooftop_dv_lottery_2023_2025"]["bam"]
    assert rt_t["n_sites"] == 178 and rt_t["fem_na_frm_att"] == 19 and rt_t["frm_na_fem_att"] == 2
    assert rt_t["binom_p"] < 0.001
    assert abs(rt_b["mean_dv_bias"]) < 0.10 and rt_b["p_bias"] > 0.50


def test_07_eiv_robust_smoke_amplification() -> None:
    r2 = _load_json("02_collocated_physics_speciation.json")
    smk_t = r2["zero_eiv_smoke_amplification"]["t640_fw"]
    smk_b = r2["zero_eiv_smoke_amplification"]["bam"]
    assert smk_t["inst1_other_site_level_site_cr1"]["coefs"]["oth_ge25"]["beta"] > 3.0
    assert smk_t["inst3_noaa_hms_level_site_cr1"]["coefs"]["hms_h"]["beta"] > 2.5
    assert smk_b["inst1_other_site_level_site_cr1"]["wcb"]["p_wcb"] > 0.50
    assert smk_b["inst3_noaa_hms_level_site_cr1"]["wcb"]["p_wcb"] > 0.20


def test_08_observational_speciation_and_meteorology() -> None:
    r2 = _load_json("02_collocated_physics_speciation.json")
    s1_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s1_spec_met_level_site_cr1"]
    s2_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s2_interactions_level_site_cr1"]
    s1_b = r2["speciation_and_meteorology"]["bam"]["model_s1_spec_met_level_site_cr1"]
    assert s1_t["n"] > 14_800
    assert s1_t["coefs"]["oc"]["beta"] > 0.55 and s1_t["coefs"]["oc"]["t_cr1"] > 6.0
    assert s2_t["coefs"]["oc_x_hms_h"]["beta"] > 0.20 and s2_t["coefs"]["oc_x_hms_h"]["p_cr1"] < 0.03
    assert s1_t["coefs"]["ec"]["beta"] < -0.70 and s1_t["coefs"]["ec"]["t_cr1"] < -3.5
    assert s1_t["coefs"]["rh_10"]["beta"] > 0.05 and s1_t["coefs"]["rh_10"]["p_cr1"] < 0.01
    assert s1_b["coefs"]["oc"]["p_cr1"] > 0.15 and s1_b["coefs"]["ec"]["p_cr1"] > 0.20


def test_09_fixed_epa_concurrence_coding_identity() -> None:
    r1 = _load_json("01_appn_audit.json")
    conc_aud = r1["regulatory_and_concurrence_audit"]["epa_concurrence_bug_audit_2018_2025"]
    assert conc_aud["true_ee_flag_count"] == conc_aud["true_concurred_count"] + conc_aud["unconc_flag_count"]
    df_mon = pd.read_parquet(PROC_DIR / "stitched_monitor_year_aln_2018_2025.parquet")
    assert (df_mon["true_ee_flag"] == (df_mon["unconc_flag"] + df_mon["true_ee_conc"])).all()


def test_10_archival_ee_within_county_year_null() -> None:
    r3 = _load_json("03_ee_triage_hms_unification.json")
    u2_wcy = r3["unification_u2_t640_ee_flagging"]["borderline_within_county_year_fe_flag"]
    assert u2_wcy["wcb"]["p_wcb"] > 0.80


def test_11_formal_metrology_model_verified() -> None:
    r4 = _load_json("04_formal_model_verification.json")
    assert r4["all_propositions_verified"] is True
    assert r4["proposition_2_inverted_u_triage"]["max_soc_fd_err"] < 1e-4


def test_12_citations_100pct_crossref_and_two_way_sync() -> None:
    r7 = _load_json("07_citations_verified.json")
    assert r7["n_academic_dois"] == 15
    assert r7["n_verified"] == 15
    assert r7["all_verified"] is True
    dois = {r["doi"] for r in r7["academic_refs"]}
    assert "10.1080/10962247.2023.2171156" in dois  # Long 2023
    assert "10.1080/10962247.2026.2639376" in dois  # McClure 2026
    assert "10.1021/acs.est.4c08946" in dois        # Krupnick 2025
    assert "10.1198/jbes.2010.07136" in dois        # Cameron-Gelbach-Miller 2011
    assert r7["two_way_sync"]["two_way_sync_ok"] is True
    assert r7["two_way_sync"]["missing_in_body"] == []
    assert r7["two_way_sync"]["missing_in_refs"] == []


def test_13_all_est_and_si_figures_high_res() -> None:
    stems = [
        "fig1_est_caseflow_and_common_support",
        "fig2_est_official_and_oot_tier_replay",
        "fig3_est_smoke_vs_nonsmoke_and_ground_truth",
        "fig4_est_inference_loro_and_speciation",
        "figS1_si_dv_reclassification_and_rooftop_lottery",
        "figS2_si_oot_reconstruction_and_ee_nulls",
    ]
    for stem in stems:
        png = FIG_DIR / f"{stem}.png"
        pdf = FIG_DIR / f"{stem}.pdf"
        assert png.exists() and png.stat().st_size > 100_000, f"Bad PNG {png}"
        assert pdf.exists() and pdf.stat().st_size > 20_000, f"Bad PDF {pdf}"
        hdr = png.read_bytes()[:24]
        assert hdr[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", hdr[16:24])
        assert width >= 3000 and height >= 1200


def test_14_official_epa_april2024_tier1_replay() -> None:
    r10 = _load_json("10_official_tier_replay.json")
    assert r10["threshold_sha256"] == "ac314789d31b89fd93f044e01d71affd9af3bf0454dae1c685adfc5348cf40e4"
    t1 = r10["results"]["t640_fw"]["matched"]["tier_1"]
    b1 = r10["results"]["bam"]["matched"]["tier_1"]
    assert t1["n_site_days"] == 468 and t1["n_sites"] == 165 and t1["n_episode_blocks"] == 27
    assert t1["instrument_exceed"] == 123 and t1["reference_exceed"] == 89
    assert t1["instrument_only"] == 36 and t1["reference_only"] == 2
    assert t1["difference_pp"] == pytest.approx(7.264957, abs=1e-4)
    assert t1["ci95_episode_pp"][0] > 4.0 and t1["ci95_episode_pp"][1] < 11.0
    assert b1["n_site_days"] == 197 and b1["instrument_exceed"] == 84 and b1["reference_exceed"] == 84
    assert b1["difference_pp"] == 0.0


def test_15_v4_p0_common_support_audit() -> None:
    r11 = _load_json("11_v4_est_comprehensive_audit.json")
    cs = r11["common_support_audit"]
    assert cs["all_2023_2025"]["triple_site_days"] == 401
    assert cs["heavy_smoke_2023_2025"]["heavy_triple_site_days"] == 4
    assert cs["heavy_smoke_2023_2025"]["heavy_overlap_dates"] == 27
    bm = cs["matched_benchmarks"]
    assert bm["overlap_epa_regions"]["differential_ci95_block_pp"][0] > 0.0
    assert bm["overlap_dates_and_regions"]["differential_ci95_block_pp"][0] > 0.0
    ow = cs["overlap_weighted_region_x_frm_bin"]
    assert ow["n_shared_cells"] == 29 and ow["block_bootstrap_ci95_pp"][0] > 0.0


def test_16_v4_p0_out_of_time_prospective_tier1_replay() -> None:
    r11 = _load_json("11_v4_est_comprehensive_audit.json")
    rb = r11["oot_reconstruction_benchmark_2021_2025"]
    assert rb["cs_all_no_ann_excl"]["zero_flag_clean_median_abs_err"] == 0.0
    assert rb["oot_b_cs_excl_hms3"]["zero_flag_clean_median_abs_err"] == 0.0

    oot = r11["oot_prospective_rolling_5yr"]
    for sk in (
        "oot_a_conservative_r_excl",
        "oot_b_fire_proxy_hms_heavy",
        "oot_b2_fire_proxy_hms_med_heavy",
        "oot_c_pure_frm_only",
    ):
        t = oot[sk]["t640_fw"]["tier_1"]
        b = oot[sk]["bam"]["tier_1"]
        assert t["difference_pp"] > 5.0
        assert t["fem_only"] >= 26 and t["frm_only"] == 0
        assert t["inference"]["oneway_nat_block"]["ci95"][0] > 0.0
        assert t["inference"]["twoway_site_x_reg_episode"]["ci95"][0] > 2.0
        assert t["inference"]["twoway_site_x_reg_episode"]["p_2sided"] < 0.005
        # Positive every evaluation year (2023, 2024, 2025)
        for yr in ("2023", "2024", "2025"):
            assert t["by_year"][yr]["difference_pp"] > 0.0
        # Background BAM remains null across all OOT specs
        assert abs(b["difference_pp"]) < 1.0
        assert b["inference"]["twoway_site_x_reg_episode"]["p_2sided"] > 0.50


def test_17_v4_smoke_specificity_two_way_est_pdfs_and_exports() -> None:
    r11 = _load_json("11_v4_est_comprehensive_audit.json")
    # Two-way CGM Site x Region-Episode & LORO
    t1 = r11["official_fixed_2021_2025"]["t640_fw"]["tier_1"]
    tw = t1["inference"]["twoway_site_x_reg_episode"]
    assert tw["ci95"][0] > 3.0 and tw["p_2sided"] < 0.001
    loro = r11["leave_epa_region_out_t640_tier1"]
    assert loro["n_regions"] == 7 and loro["all_loro_positive"] is True and loro["min_loro_diff_pp"] > 6.0

    # Equal-concentration non-smoke vs Heavy smoke controls & ground-level confirmation
    mc = r11["smoke_vs_nonsmoke_controls"]["t640_fw"]["matched_concentration_smoke_vs_nonsmoke"]
    for k in ("other_site_ge15", "frm_ge15", "frm_ge25", "midpoint_ge15"):
        assert mc[k]["heavy_minus_nonsmoke_bias"] > 3.0
        assert mc[k]["bias_diff_p_site"] < 1e-4
    gv = r11["smoke_vs_nonsmoke_controls"]["t640_fw"]["ground_level_smoke_verification"]
    assert gv["heavy_surface_impact_frm_gt_p90"]["t1_diff_pp"] > 9.0
    assert gv["heavy_lofted_frm_le_p90"]["t1_diff_pp"] == 0.0
    assert gv["heavy_oc_ge5"]["t1_diff_pp"] > 10.0

    # Reproducible CSV exports
    for fname in (
        "collocated_heavy_smoke_pairs_2023_2025.csv",
        "aqs_and_threshold_version_manifest.csv",
        "table1_common_support_audit.csv",
        "table2_official_and_oot_tier_replay.csv",
        "table3_smoke_vs_nonsmoke_controls.csv",
        "table4_leave_epa_region_out.csv",
    ):
        assert (TABLES_DIR / fname).exists(), f"Missing export {fname}"
    pairs_csv = pd.read_csv(TABLES_DIR / "collocated_heavy_smoke_pairs_2023_2025.csv")
    assert len(pairs_csv) == 673

    # Authorship, zero Target Venues/Track A/Track B, and PDF zero-leak verification
    md_main = (WS_DIR / "manuscript_j6_boost.md").read_text(encoding="utf-8")
    md_si = (WS_DIR / "supplementary_j6_est.md").read_text(encoding="utf-8")
    for txt in (md_main, md_si):
        assert "Zijian Zeng" in txt
        assert "Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA" in txt
        assert "zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my" in txt
        assert not re.search(r"Target Venues|Target Format|Track A|Track B", txt)

    # 47-county DV reclassifications moved to Supporting Information (with explicit CAA § 107(d) disclaimer)
    assert "47" in md_si and "107(d)" in md_si and "no claim" in md_si.lower()
    assert (WS_DIR / "REFEREE_RESPONSE_v4.md").exists()

    spec = importlib.util.spec_from_file_location("compile_pdf_mod", SCRIPTS_DIR / "08_compile_manuscript_pdf.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pdf_main = WS_DIR / "manuscript_j6_boost.pdf"
    pdf_si = WS_DIR / "supplementary_j6_est.pdf"
    assert pdf_main.exists() and pdf_main.stat().st_size > 1_000_000
    assert pdf_si.exists() and pdf_si.stat().st_size > 500_000
    n_main, leaks_main = mod.verify_pdf_zero_leaks(pdf_main)
    n_si, leaks_si = mod.verify_pdf_zero_leaks(pdf_si)
    assert n_main == 12 and leaks_main == [], f"Main PDF leaks: {leaks_main}"
    assert n_si == 4 and leaks_si == [], f"SI PDF leaks: {leaks_si}"
