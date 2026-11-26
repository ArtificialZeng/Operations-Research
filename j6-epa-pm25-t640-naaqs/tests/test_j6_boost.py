"""Comprehensive automated verification suite for J6 /boost (EPA PM2.5 NAAQS & Teledyne T640).

Verifies:
  1. Exact FWL vs brute-force explicit LSDV OLS + CR1 + WCB equivalence to atol=1e-11
     and exact bipartite connected-component nested-FE DOF rank.
  2. Zero NaN/Inf across all 6 JSON receipts and processed parquet files.
  3. Pillar 0 external enrichment integrity (NOAA HMS 100% coverage, Census 3,144 counties,
     EPA official workbooks).
  4. Pillar 1 stitched App. N integrity (410 split-year repairs, regulatory filtering,
     T640 alignment flip, >=95% official EPA 2021-2023 precision, EJ regional/Black skew).
  5. Exogenous DV_18_20 nulls on Margins A, C, and D (zero RTM overlap).
  6. Pillar 2 same-rooftop 2023-2025 DV lottery (T640_FW positive & significant; BAM null).
  7. Pillar 2 zero-EIV wildfire smoke amplification across all 3 independent instruments
     (Other-Site, Bland-Altman, NOAA HMS Heavy) with BAM flat on Other-Site.
  8. Pillar 2 EPA chemical speciation & meteorology Mie-scattering mechanism (OC+, OCxHMS+,
     EC-, RH+ on T640_FW; BAM OC/EC null & NO3-/RH-).
  9. Fixed EPA-concurrence coding (49.9% false-positive removal, exact decomposition identity).
 10. Pillar 3 pre-trend-clean DV_18_20 DiD, State WCB, RI, LOSO, Inverted-U, Fake-Rule Placebo,
     and transparent 2024-2025 nulls.
 11. Killer Unification U1 (McNemar 2.00x trigger doubling), U2 (T640 x HMS Heavy & EE reduction),
     and U3 (EPA concurrence only on Heavy smoke vs unconcurred precautionary Non-Heavy surge).
 12. Formal Section 2 metrology model verification (strict concavity & Propositions 1-3).
 13. 100% live Crossref DOI verification (16/16) & two-way citation sync (21/21).
 14. All 5 publication figures (PNG >=300 DPI width & non-empty vector PDFs).
 15. Camera-ready manuscript_j6_boost.pdf zero-leak verification & receipt-to-manuscript sync.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

WS_DIR = Path(r"D:\AI_Science\antigravity\j6_boost_epa_pm25_t640_naaqs_20261126")
SCRIPTS_DIR = WS_DIR / "scripts"
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
    # 5 states, 4 units/state (20 units), 4 years, slightly unbalanced panel
    for st in range(5):
        for u_local in range(4):
            uid = st * 4 + u_local
            for yr in range(4):
                if uid == 3 and yr == 2:
                    continue  # unbalanced gap
                rows.append((uid, st, yr, f"{st}_{yr}"))
    df = pd.DataFrame(rows, columns=["unit", "state", "year", "state_yr"])
    n = len(df)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    # True DGP with unit FE + state x year FE
    u_eff = rng.normal(size=20)[df["unit"].to_numpy()]
    sy_codes, _ = pd.factorize(df["state_yr"], sort=False)
    sy_eff = rng.normal(size=20)[sy_codes]
    y = 1.75 * x1 - 0.85 * x2 + u_eff + sy_eff + rng.normal(scale=0.5, size=n)

    X = np.column_stack([x1, x2])
    fe_u = df["unit"].to_numpy()
    fe_sy = df["state_yr"].to_numpy()
    cl = df["unit"].to_numpy()

    # Exact explicit dummy matrix D for [unit, state_yr]
    Du = pd.get_dummies(fe_u, dtype=float).to_numpy()
    Dsy = pd.get_dummies(fe_sy, dtype=float).to_numpy()
    D_full = np.hstack([Du, Dsy])
    rank_exact = int(np.linalg.matrix_rank(D_full))
    # Nested FE has 5 connected components (5 states), NOT 1!
    assert rank_exact == 20 + 20 - 5
    assert count_fe_dof_exact([fe_u, fe_sy]) == rank_exact

    # Fit via our FWL + WCB engine
    seed = 98765
    B = 199
    res_fwl = ols_cr1(
        y, X, cl, fe_groups=[fe_u, fe_sy], col_names=["x1", "x2"], wcb_var_idx=0, wcb_B=B, seed=seed
    )
    assert res_fwl["fe_dof"] == rank_exact

    # Brute-force LSDV using orthonormal basis Q for col(D_full)
    U_svd, s_svd, _ = np.linalg.svd(D_full, full_matrices=False)
    Q = U_svd[:, s_svd > 1e-10]
    assert Q.shape[1] == rank_exact
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

    # Brute-force restricted LSDV WCB with identical Rademacher draws
    Zr = Z[:, 1:]  # drop x1 (null H0: beta_x1 = 0)
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
    cens = r0["census_demographics"]
    assert cens["n_counties"] >= 3100
    assert 330.0 < cens["total_pop_millions"] < 350.0
    assert len(r0["epa_dv_workbooks"]["downloaded"]) >= 5


def test_04_pillar1_stitched_appn_reconciliation_and_ej() -> None:
    r1 = _load_json("01_appn_audit.json")
    assert r1["stitch_audit"]["n_split_2023_t640_monitors_repaired"] >= 400
    assert r1["regulatory_and_concurrence_audit"]["excluded_non_reg_monitors"] >= 200

    cs11 = r1["accounting"]["combined_site_reg_appn_11of12"]
    wf = cs11["matched_2123_waterfall"]
    assert wf["flip_t640_alone"]["counties"] >= 40
    assert wf["flip_t640_alone"]["pop_millions"] >= 15.0

    epa21 = r1["epa_official_dv_reconciliation"]["pm25_designvalues_2021_2023_final_08_08_24_0.xlsx"]
    precision = epa21["overlap_epa_with_cs_reg_incl"] / epa21["combined_site_reg_na_incl"]
    assert precision >= 0.95

    ej_t = r1["ej_audit_acs2023"]["formal_tests"]
    assert ej_t["Flipped_vs_Still_Nonattainment"]["midwest_south_share"]["fisher_p"] < 0.05
    assert ej_t["Flipped_vs_Cleanly_Attaining"]["pct_black_nh"]["welch_p"] < 0.05


def test_05_exogenous_dv1820_nulls_margins_acd() -> None:
    r1 = _load_json("01_appn_audit.json")
    nulls = r1["exogenous_nulls_margins_acd"]
    assert nulls["margin_d_frm_exog_dv1820_county_cr1"]["wcb"]["p_wcb"] > 0.20
    assert nulls["margin_d_frm_exog_dv1820_state_cr1"]["wcb"]["p_wcb"] > 0.20
    assert nulls["margin_a_share_fem_exog_dv1820"]["wcb"]["p_wcb"] > 0.15
    assert nulls["margin_c_log_monitors_exog_dv1820"]["wcb"]["p_wcb"] > 0.20
    assert nulls["margin_c_monitor_survival_exog_dv1820"]["wcb"]["p_wcb"] > 0.20


def test_06_pillar2_rooftop_dv_lottery() -> None:
    r2 = _load_json("02_collocated_physics_speciation.json")
    assert r2["method_code_audit"]["t640_fw_method_codes"] == ["636", "638"]
    assert r2["method_code_audit"]["bam_method_codes"] == ["170", "209"]
    rt_t = r2["rooftop_dv_lottery_2023_2025"]["t640_fw"]
    rt_st = r2["rooftop_dv_lottery_2023_2025"]["t640_fw_strict_4q3y"]
    rt_b = r2["rooftop_dv_lottery_2023_2025"]["bam"]

    assert rt_t["n_sites"] >= 150
    assert rt_t["mean_dv_bias"] > 0.40
    assert rt_t["t_bias"] > 8.0
    assert rt_t["binom_p"] < 0.001
    assert rt_t["fem_na_frm_att"] >= 15 and rt_t["fem_na_frm_att"] > 5 * rt_t["frm_na_fem_att"]
    assert rt_st["n_sites"] >= 100 and rt_st["binom_p"] < 0.005
    assert abs(rt_b["mean_dv_bias"]) < 0.10 and rt_b["p_bias"] > 0.50
    assert rt_b["binom_p"] > 0.50


def test_07_pillar2_zero_eiv_smoke_amplification() -> None:
    r2 = _load_json("02_collocated_physics_speciation.json")
    smk_t = r2["zero_eiv_smoke_amplification"]["t640_fw"]
    smk_b = r2["zero_eiv_smoke_amplification"]["bam"]

    # T640_FW explodes across all 3 EIV-free instruments
    assert smk_t["inst1_other_site_level_site_cr1"]["coefs"]["oth_ge25"]["beta"] > 3.0
    assert smk_t["inst1_other_site_level_site_cr1"]["wcb"]["p_wcb"] <= 0.01
    assert smk_t["inst1_other_site_level_state_cr1"]["wcb"]["p_wcb"] <= 0.01
    assert smk_t["inst1_other_site_logratio_site_cr1"]["coefs"]["oth_ge25"]["beta"] > 0.08
    assert smk_t["inst2_bland_altman_level_site_cr1"]["coefs"]["ba_ge25"]["beta"] > 4.0
    assert smk_t["inst3_noaa_hms_level_site_cr1"]["coefs"]["hms_h"]["beta"] > 2.5
    assert smk_t["inst3_noaa_hms_level_site_cr1"]["wcb"]["p_wcb"] <= 0.01
    assert smk_t["inst3_noaa_hms_logratio_site_cr1"]["coefs"]["hms_h"]["beta"] > 0.10

    # Pure Met One BAM (170/209) is statistically null on ALL 3 EIV-free instruments
    assert smk_b["inst1_other_site_level_site_cr1"]["wcb"]["p_wcb"] > 0.50
    assert smk_b["inst1_other_site_logratio_site_cr1"]["coefs"]["oth_ge25"]["p_cr1"] > 0.15
    assert smk_b["inst2_bland_altman_level_site_cr1"]["wcb"]["p_wcb"] > 0.05
    assert smk_b["inst3_noaa_hms_level_site_cr1"]["wcb"]["p_wcb"] > 0.20


def test_08_pillar2_speciation_mie_scattering_mechanism() -> None:
    r2 = _load_json("02_collocated_physics_speciation.json")
    s1_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s1_spec_met_level_site_cr1"]
    s2_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s2_interactions_level_site_cr1"]
    s3_t = r2["speciation_and_meteorology"]["t640_fw"]["model_s3_exact_0km_spec_level"]
    s1_b = r2["speciation_and_meteorology"]["bam"]["model_s1_spec_met_level_site_cr1"]

    # Core-4 speciation merge preserves urban CSN rooftops lacking 88348 (soil) -> N > 14,800
    assert s1_t["n"] > 14_800
    assert s1_t["coefs"]["oc"]["beta"] > 0.55 and s1_t["coefs"]["oc"]["t_cr1"] > 6.0
    assert s2_t["coefs"]["oc_x_hms_h"]["beta"] > 0.20 and s2_t["coefs"]["oc_x_hms_h"]["p_cr1"] < 0.03
    assert s1_t["coefs"]["ec"]["beta"] < -0.70 and s1_t["coefs"]["ec"]["t_cr1"] < -3.5
    assert s1_t["coefs"]["rh_10"]["beta"] > 0.05 and s1_t["coefs"]["rh_10"]["p_cr1"] < 0.01
    # Exact 0 km rooftop subsample confirms OC+, EC-, RH+
    assert s3_t["n"] > 9_500 and s3_t["coefs"]["oc"]["beta"] > 0.50 and s3_t["coefs"]["ec"]["beta"] < -0.50

    # Pure BAM (170/209) null on OC/EC, strongly negative on NO3- and RH
    assert s1_b["coefs"]["oc"]["p_cr1"] > 0.15
    assert s1_b["coefs"]["ec"]["p_cr1"] > 0.20
    assert s1_b["coefs"]["no3"]["beta"] < -0.30 and s1_b["coefs"]["no3"]["t_cr1"] < -6.0
    assert s1_b["coefs"]["rh_10"]["beta"] < -0.08 and s1_b["coefs"]["rh_10"]["t_cr1"] < -2.5


def test_09_fixed_epa_concurrence_coding_identity() -> None:
    r1 = _load_json("01_appn_audit.json")
    conc_aud = r1["regulatory_and_concurrence_audit"]["epa_concurrence_bug_audit_2018_2025"]
    assert 45.0 < conc_aud["false_positive_share_pct"] < 55.0
    assert conc_aud["true_ee_flag_count"] == conc_aud["true_concurred_count"] + conc_aud["unconc_flag_count"]

    df_mon = pd.read_parquet(PROC_DIR / "stitched_monitor_year_aln_2018_2025.parquet")
    assert ((df_mon["true_ee_conc"] <= df_mon["true_ee_flag"]).all())
    assert ((df_mon["true_ee_flag"] == (df_mon["unconc_flag"] + df_mon["true_ee_conc"])).all())
    # Verify overlapping POC / POC+20 T640 pairs are NOT diluted by double-counted observations
    r_06051 = df_mon[(df_mon["canon_id"] == "06051-0005-4") & (df_mon["Year"] == 2023)]
    assert len(r_06051) == 1 and float(r_06051["ee_red_all"].iloc[0]) > 0.25


def test_10_pillar3_pretrend_clean_triage_and_robustness() -> None:
    r3 = _load_json("03_ee_triage_hms_unification.json")
    assert r3["stitch_merge_audit"]["n_dropped_on_merge"] == 0
    m3 = r3["monitor_year_dv1820_85_115"]
    c3 = r3["county_year_dv1820_85_115"]
    ri = r3["within_state_ri_B1000"]
    loso = r3["loso_monitor_year"]
    rob = r3["robustness_specs_dv1820"]
    iu = r3["inverted_u_profile_dv1820"]["monitor_year_county_cr1"]["coefs"]

    assert m3["true_ee_flag"]["did_2225_state_cr1"]["coefs"]["tp_2225"]["beta"] > 0.06
    assert m3["true_ee_flag"]["did_2225_state_cr1"]["wcb"]["p_wcb"] <= 0.01
    assert m3["true_ee_flag"]["pre_linear_2018_2021"]["coefs"]["lin"]["p_cr1"] > 0.10
    assert m3["true_ee_flag"]["event_study_state_cr1"]["joint_F"]["p"] > 0.20
    assert c3["true_ee_flag"]["event_study_county_cr1"]["joint_F"]["p"] > 0.20
    assert c3["true_ee_conc"]["event_study_county_cr1"]["joint_F"]["p"] > 0.50
    assert ri["monitor_year"]["p_ri_2sided"] <= 0.005
    assert ri["county_year"]["p_ri_2sided"] <= 0.005
    assert loso["n_states"] == 51 and loso["min_t"] > 3.0
    # Inverted-U peak inside [8.5, 11.5]
    assert iu["b_95_115"]["beta"] > iu["b_70_85"]["beta"] + 0.05
    assert iu["b_95_115"]["beta"] > iu["b_gt115"]["beta"]
    # Fake-rule placebo null & honest 2024-2025 EPA-concurred nulls
    assert rob["fake_rule_placebo_2020_21_vs_18_19"]["coefs"]["treat_post"]["p_cr1"] > 0.20
    assert c3["true_ee_conc"]["event_study_county_cr1"]["coefs"]["nb_2025"]["p_cr1"] > 0.20
    assert m3["true_ee_conc"]["did_split_2425_wcb_state_cr1"]["p_wcb"] > 0.10


def test_11_killer_unification_u1_u2_u3() -> None:
    r2 = _load_json("02_collocated_physics_speciation.json")
    r3 = _load_json("03_ee_triage_hms_unification.json")

    u1_t = r2["unification_u1_exceedance_multiplier"]["t640_fw"]["hms_heavy_smoke"]["gt_35_naaqs24h"]
    u1_b = r2["unification_u1_exceedance_multiplier"]["bam"]["hms_heavy_smoke"]["gt_35_naaqs24h"]
    assert u1_t["trigger_multiplier_ratio"] >= 1.90
    assert u1_t["mcnemar_exact_p"] < 1e-6
    assert u1_b["mcnemar_exact_p"] > 0.50

    # U2 un-diluted EE reduction (+0.250 ug/m3) & T640 x log(HMS Heavy) pass BOTH County and State WCB
    u2 = r3["unification_u2_t640_ee_flagging"]
    assert u2["borderline_2225_t640_x_hms_heavy_flag"]["coefs"]["t640_x_hms_h"]["beta"] > 0.10
    assert u2["borderline_2225_t640_x_hms_heavy_flag"]["wcb"]["p_wcb"] <= 0.01
    assert u2["borderline_2225_t640_x_hms_heavy_flag_state_cr1"]["wcb"]["p_wcb"] <= 0.02
    assert u2["borderline_2225_state_yr_fe_ee_red"]["coefs"]["is_t640_f"]["beta"] > 0.20
    assert u2["borderline_2225_state_yr_fe_ee_red"]["wcb"]["p_wcb"] <= 0.01
    assert u2["borderline_2225_state_yr_fe_ee_red_state_cr1"]["wcb"]["p_wcb"] <= 0.01

    # U3 properly saturated with pre-period nb_x_h interaction
    u3 = r3["unification_u3_hms_triage_validation"]
    assert "nb_x_h" in u3["did_by_hms_stratum_unconc"]["coefs"]
    assert u3["satellite_hms_backing_2022_2025"]["all_ee_pct_with_hms_any"] > 95.0
    assert u3["did_by_hms_stratum_conc"]["coefs"]["tp_hms_heavy"]["p_cr1"] < 0.05
    assert u3["did_by_hms_stratum_conc"]["coefs"]["tp_hms_no_heavy"]["p_cr1"] > 0.20
    assert u3["did_by_hms_stratum_unconc"]["coefs"]["tp_hms_heavy"]["p_cr1"] < 0.05


def test_12_formal_metrology_model_verified() -> None:
    r4 = _load_json("04_formal_model_verification.json")
    assert r4["all_propositions_verified"] is True
    assert r4["proposition_1_optical_lottery"]["verified"] is True
    assert r4["proposition_2_inverted_u_triage"]["all_socs_negative"] is True
    # Analytic d2U/de2 (exact sigma^2) matches central finite difference to < 1e-4
    assert r4["proposition_2_inverted_u_triage"]["max_soc_fd_err"] < 1e-4
    assert r4["proposition_2_inverted_u_triage"]["verified"] is True
    assert r4["proposition_3_optical_regulatory_multiplier"]["verified"] is True


def test_13_citations_100pct_crossref_and_two_way_sync() -> None:
    r7 = _load_json("07_citations_verified.json")
    assert r7["n_academic_dois"] == 16
    assert r7["n_verified"] == 16
    assert r7["all_verified"] is True
    assert r7["two_way_sync"]["two_way_sync_ok"] is True
    assert r7["two_way_sync"]["missing_in_body"] == []
    assert r7["two_way_sync"]["missing_in_refs"] == []


def test_14_all_five_publication_figures_high_res() -> None:
    import struct

    names = [
        "fig1_t640_windfall_and_ej_map",
        "fig2_rooftop_lottery_and_regional_bias",
        "fig3_zero_eiv_smoke_and_speciation_physics",
        "fig4_ee_triage_event_study_and_decomposition",
        "fig5_optical_to_flagging_multiplier",
    ]
    for stem in names:
        png = FIG_DIR / f"{stem}.png"
        pdf = FIG_DIR / f"{stem}.pdf"
        assert png.exists() and png.stat().st_size > 100_000, f"Bad PNG {png}"
        assert pdf.exists() and pdf.stat().st_size > 20_000, f"Bad PDF {pdf}"
        # Verify PNG IHDR width >= 3000px (300 DPI at >=10 in width)
        hdr = png.read_bytes()[:24]
        assert hdr[:8] == b"\x89PNG\r\n\x1a\n"
        width, height = struct.unpack(">II", hdr[16:24])
        assert width >= 3000 and height >= 1200


def test_15_pdf_zero_leaks_and_receipt_sync() -> None:
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "compile_pdf_mod", SCRIPTS_DIR / "08_compile_manuscript_pdf.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)

    pdf_path = WS_DIR / "manuscript_j6_boost.pdf"
    md_path = WS_DIR / "manuscript_j6_boost.md"
    assert pdf_path.exists() and pdf_path.stat().st_size > 1_000_000
    n_pages, leaks = mod.verify_pdf_zero_leaks(pdf_path)
    assert n_pages >= 12
    assert leaks == [], f"PDF leaks detected: {leaks}"

    # Verify Figure 4 dynamic PDF caption matches actual plot colors (amber=unconcurred, teal=concurred)
    fig_blocks = mod.build_dynamic_figure_blocks()
    fig4_cap = fig_blocks["fig4_ee_triage_event_study_and_decomposition.png"][1]
    assert "Unconcurred Precautionary Flags (amber" in fig4_cap
    assert "True EPA-Concurred Exclusions (teal" in fig4_cap
    # Verify v2 PDF figure captions reflect all referee recalibrations
    fig1_cap = fig_blocks["fig1_t640_windfall_and_ej_map.png"][1]
    fig3_cap = fig_blocks["fig3_zero_eiv_smoke_and_speciation_physics.png"][1]
    fig5_cap = fig_blocks["fig5_optical_to_flagging_multiplier.png"][1]
    assert "Design-Value threshold reclassifications" in fig1_cap
    assert "5-factor" in fig1_cap
    assert "EIV-robust" in fig3_cap and "observational" in fig3_cap.lower()
    assert "5-year historical" in fig5_cap and "within-county-year FE comparison is null" in fig5_cap

    # Verify key dynamic numbers from receipts appear verbatim in manuscript_j6_boost.md
    md_txt = md_path.read_text(encoding="utf-8")
    r1 = _load_json("01_appn_audit.json")
    r2 = _load_json("02_collocated_physics_speciation.json")
    r3 = _load_json("03_ee_triage_hms_unification.json")
    assert f"{r1['accounting']['combined_site_reg_appn_11of12']['matched_2123_waterfall']['flip_t640_alone']['counties']} " in md_txt
    assert f"{r2['rooftop_dv_lottery_2023_2025']['t640_fw']['mean_dv_bias']:.3f}" in md_txt
    assert f"{r2['speciation_and_meteorology']['t640_fw']['model_s1_spec_met_level_site_cr1']['coefs']['oc']['beta']:.3f}" in md_txt
    assert f"{100 * r3['monitor_year_dv1820_85_115']['true_ee_flag']['did_2225_state_cr1']['coefs']['tp_2225']['beta']:.2f}" in md_txt
    assert f"{r3['unification_u2_t640_ee_flagging']['borderline_2225_state_yr_fe_ee_red']['coefs']['is_t640_f']['beta']:.3f}" in md_txt


def test_16_v2_historical_tier1_screening_and_referee_recalibrations() -> None:
    """Verify all 4 Major Revision v2 referee fixes in receipts and manuscript_j6_boost.md:
    (a) Strictly pre-period 5-year historical (2018-2022) FRM 98th-percentile EPA Wildfire Tier-1
        screening McNemar tests computed and synced;
    (b) Within-county-year null (p_WCB = 0.931) explicitly disclosed in Abstract & Section 6;
    (c) Zero conflation of DV reclassification with formal EPA legal designations or single-day >35
        with 24-hr NAAQS violations;
    (d) Zero leftover absolute 'zero-EIV' / causal speciation overclaims.
    """
    import re

    r3 = _load_json("03_ee_triage_hms_unification.json")
    assert "unification_u1_historical_tier1_1822" in r3
    u1h = r3["unification_u1_historical_tier1_1822"]

    t_aud = u1h["t640_fw"]["baseline_audit_2018_2022"]
    b_aud = u1h["bam"]["baseline_audit_2018_2022"]
    assert t_aud["n_sites_matched_ge30d"] >= 200
    assert b_aud["n_sites_matched_ge30d"] >= 90

    t_hms = u1h["t640_fw"]["hms_heavy_smoke"]["gt_tier1_min_p98_35"]
    t_hms_3y = u1h["t640_fw"]["hms_heavy_smoke"]["gt_tier1_min_p98_35_ge3y"]
    t_all = u1h["t640_fw"]["all_paired_days"]["gt_tier1_min_p98_35"]
    b_hms = u1h["bam"]["hms_heavy_smoke"]["gt_tier1_min_p98_35"]
    b_all = u1h["bam"]["all_paired_days"]["gt_tier1_min_p98_35"]

    # T640_FW causal screening divergence on true pre-period 2018-2022 FRM Tier-1 threshold
    assert t_hms["trigger_multiplier_ratio"] >= 1.25
    assert t_hms["fem_only_discordant"] >= 35 and t_hms["frm_only_discordant"] == 0
    assert t_hms["mcnemar_exact_p"] < 1e-10
    assert t_hms["p_wcb"] <= 0.01
    assert t_hms_3y["mcnemar_exact_p"] < 1e-9
    assert t_all["trigger_multiplier_ratio"] >= 1.50 and t_all["mcnemar_exact_p"] < 1e-100

    # Pure Met One BAM (170/209) clean null across historical Tier-1 strata
    assert b_hms["mcnemar_exact_p"] > 0.50
    assert b_all["mcnemar_exact_p"] > 0.10

    # Manuscript text checks: Abstract, Section 4, Section 5, Section 6, Section 7
    md_txt = (WS_DIR / "manuscript_j6_boost.md").read_text(encoding="utf-8")
    abs_sec = md_txt.split("## Abstract", 1)[1].split("## 1.", 1)[0]
    sec4 = md_txt.split("## 4.", 1)[1].split("## 5.", 1)[0]
    sec5 = md_txt.split("## 5.", 1)[1].split("## 6.", 1)[0]
    sec6 = md_txt.split("## 6.", 1)[1].split("## 7.", 1)[0]
    sec7 = md_txt.split("## 7.", 1)[1].split("## References", 1)[0]

    # (a) Historical Tier-1 counts synced into Abstract & Section 6
    assert f"{t_hms['fem_exceed_n']} vs. {t_hms['frm_exceed_n']}" in abs_sec
    assert f"{t_hms['fem_only_discordant']} vs. {t_hms['frm_only_discordant']}" in sec6
    assert "level-equivalent daily exceedance" in abs_sec.lower()
    assert "level-equivalent daily exceedance" in sec6.lower()

    # (b) Within-county-year null (p_WCB = 0.931) and explicit non-causal disclaimer in Abstract & Section 6 & Conclusion
    wcy_p = f"{r3['unification_u2_t640_ee_flagging']['borderline_within_county_year_fe_flag']['wcb']['p_wcb']:.3f}"
    assert wcy_p in abs_sec and "within-county-year" in abs_sec.lower()
    assert wcy_p in sec6 and "do not claim that optical bias causally" in sec6.lower()
    assert wcy_p in sec7 and "within-county-year" in sec7.lower()
    assert "do not claim that optical bias causally" in abs_sec.lower()
    assert "anticipatory" in abs_sec.lower() and "before" in abs_sec.lower()

    # (c) DV threshold reclassification vs formal EPA § 107(d) 5-factor legal designations
    assert "monitor design-value threshold reclassifications" in abs_sec.lower()
    assert "5-factor" in abs_sec.lower()
    assert "monitor design-value threshold reclassifications" in sec4.lower()
    assert "five-factor" in sec4.lower()
    assert "5-factor" in sec7.lower()

    # (d) Zero forbidden v1 overclaim phrases anywhere in manuscript
    forbidden = [
        r"zero[- ]EIV",
        r"EIV[- ]free",
        r"errors-in-variables-free",
        r"Killer Unification",
        r"exact Mie-scattering mechanism",
        r"Tier-1 Exceptional Event visibility",
        r"statutory nonattainment lottery",
        r"causes strategic",
    ]
    for pat in forbidden:
        assert not re.search(pat, md_txt, flags=re.IGNORECASE), f"Forbidden v1 phrase leaked: {pat}"
    assert "controlled multi-site physical calibration" in sec5.lower()
    assert "controlled multi-site physical calibration" in sec7.lower()
    assert (WS_DIR / "REFEREE_RESPONSE_v2.md").exists()
