"""Comprehensive automated verification test suite for the D30 /boost pipeline.

Tests:
  1. Unit tests & edge cases for parser helpers (date parsing, molecule canonicalization,
     MeSH resolution & artifact rejection, placebo vs double-dummy vs crossover vs phase-labeled
     arm classification, case-insensitive MedDRA SOC including 'General disorders', mutually
     exclusive region shares summing to 1.0, FDAAA/War boundaries, Drugs@FDA NDA/BLA filtering).
  2. Processed panel integrity (no duplicate NCTs, [0, 1] AE rate bounds, exact regional
     share simplex identity, >95% MedDRA SOC coverage, Phase 2 vs Phase 3 disjointness).
  3. Complete econometric receipt audit (ZERO rank-deficient models across ALL Blocks A-E
     including mortality, ZERO errors/NaNs, finite-sample t(G-1) use_t=True, FWL exact slope
     identity, CGM two-way clustering & Rademacher wild bootstrap, unbiased OOS war DiD +
     fake-2020 placebo audit, exact DoF-adjusted EIV monotonicity).
  4. Complete Gate-2 openFDA linkage integrity (NDA/BLA only, biologic 4-letter suffix
     recovery, 100% global FAERS coverage, ZERO rank-deficient Gate-2 models, Poisson GLM &
     persisted 10-step forensic covariate audit).
  5. Artifact existence, ZERO NaNs in all 5 CSV tables, comprehensive manuscript-vs-JSON
     numerical verification across all 5 tables, zero placeholders, and SHA-256 manifest match.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")
SCRIPTS_DIR = BASE_DIR / "scripts"
PROC_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"
FIG_DIR = BASE_DIR / "figures"
TAB_DIR = BASE_DIR / "tables"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


BUILD = load_module("build_panel_mod", SCRIPTS_DIR / "02_build_panel.py")
FDA_MOD = load_module("openfda_mod", SCRIPTS_DIR / "04_gate2_openfda_linkage.py")


def _walk_regressions(obj, path: str = "") -> list[tuple[str, str, object]]:
    """Recursively audit every regression dict in a JSON receipt for errors, rank deficiency, or NaNs."""
    issues: list[tuple[str, str, object]] = []
    if isinstance(obj, dict):
        if "error" in obj:
            issues.append((path, "ERROR", obj["error"]))
        if obj.get("is_full_rank") is False:
            issues.append((path, "RANK_DEFICIENT", f"{obj.get('matrix_rank')}/{obj.get('n_params')}"))
        if "terms" in obj and isinstance(obj["terms"], dict):
            for tk, tv in obj["terms"].items():
                if isinstance(tv, dict):
                    for field in ("coef", "se", "t", "p"):
                        if field in tv:
                            v = tv[field]
                            if v is None or (isinstance(v, float) and not np.isfinite(v)):
                                issues.append((f"{path}.{tk}.{field}", "NON_FINITE", v))
        for k, v in obj.items():
            issues.extend(_walk_regressions(v, f"{path}.{k}" if path else k))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            issues.extend(_walk_regressions(v, f"{path}[{i}]"))
    return issues


# =============================================================================
# 1. UNIT TESTS & EDGE CASES FOR PARSER HELPERS
# =============================================================================
class TestParserEdgeCases:
    def test_parse_iso_date_formats_and_invalid(self):
        iso, yr, dt = BUILD.parse_iso_date("2017-01-18")
        assert iso == "2017-01-18" and yr == 2017.0 and dt is not None

        iso2, yr2, dt2 = BUILD.parse_iso_date("2022-02")
        assert iso2 == "2022-02-15" and yr2 == 2022.0 and dt2 is not None

        iso3, yr3, dt3 = BUILD.parse_iso_date("2019")
        assert iso3 == "2019-06-15" and yr3 == 2019.0 and dt3 is not None

        iso_bad, yr_bad, dt_bad = BUILD.parse_iso_date("")
        assert iso_bad is None and np.isnan(yr_bad) and dt_bad is None

        iso_none, yr_none, dt_none = BUILD.parse_iso_date(None)
        assert iso_none is None and np.isnan(yr_none) and dt_none is None

    def test_canonicalize_molecule_salts_doses_prefixes_and_parentheses(self):
        assert BUILD.canonicalize_molecule("Dupilumab (Dupixent) 300 mg SC") == "dupilumab"
        assert BUILD.canonicalize_molecule("Baricitinib Hydrochloride 4 mg Tablet") == "baricitinib"
        assert BUILD.canonicalize_molecule("Empagliflozin 10mg Oral") == "empagliflozin"
        assert BUILD.canonicalize_molecule("Tofacitinib Citrate Extended-Release") == "tofacitinib"
        assert BUILD.canonicalize_molecule("Experimental: Tezepelumab") == "tezepelumab"
        assert BUILD.canonicalize_molecule("Group 2 ustekinumab 130 mg") == "ustekinumab"
        assert BUILD.canonicalize_molecule("Active comparator: Niraparib") == "niraparib"
        assert BUILD.canonicalize_molecule("") == ""

    def test_extract_primary_molecule_backbone_mesh_and_artifact_rejection(self):
        # Backbone deprioritization
        ps = {
            "identificationModule": {
                "briefTitle": "Study of Empagliflozin Added to Metformin in Type 2 Diabetes",
                "officialTitle": "Phase 3 Randomized Trial of Empagliflozin + Metformin vs Placebo",
            },
            "armsInterventionsModule": {
                "interventions": [
                    {"type": "DRUG", "name": "Metformin Hydrochloride 1000 mg"},
                    {"type": "DRUG", "name": "Empagliflozin 25 mg"},
                    {"type": "DRUG", "name": "Matching Placebo"},
                ]
            },
        }
        primary, _, all_mols = BUILD.extract_primary_molecule(ps, {})
        assert primary == "empagliflozin"
        assert "metformin" in all_mols
        assert "placebo" not in all_mols

        # Dirty raw string wrapping MeSH INN
        ps_dup = {
            "identificationModule": {"briefTitle": "Dupilumab study", "officialTitle": ""},
            "armsInterventionsModule": {
                "interventions": [{"type": "BIOLOGICAL", "name": "Dupilumab SAR231893 (REGN668)"}]
            },
        }
        ds_dup = {"interventionBrowseModule": {"meshes": [{"term": "dupilumab"}]}}
        assert BUILD.extract_primary_molecule(ps_dup, ds_dup)[0] == "dupilumab"

        # Internal code resolved cleanly via unique non-artifact MeSH INN (ignoring Double-Blind Method)
        ps_code = {
            "identificationModule": {"briefTitle": "Study of CP-690,550", "officialTitle": ""},
            "armsInterventionsModule": {"interventions": [{"type": "DRUG", "name": "CP-690,550"}]},
        }
        ds_code = {
            "interventionBrowseModule": {
                "meshes": [{"term": "tofacitinib"}, {"term": "Double-Blind Method"}, {"term": "BID protein, human"}]
            }
        }
        assert BUILD.extract_primary_molecule(ps_code, ds_code)[0] == "tofacitinib"

    def test_classify_event_group_placebo_phase_labels_double_dummy_and_crossover(self):
        # Pure placebo, background SoC, and phase-labeled placebo arms -> placebo
        assert BUILD.classify_event_group("Placebo", "")[0] == "placebo"
        assert BUILD.classify_event_group("Matching Placebo QD", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo + Methotrexate", "")[0] == "placebo"
        assert BUILD.classify_event_group("Vehicle Gel", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo - Treatment Phase", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo - Randomization Phase", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo - Part A", "")[0] == "placebo"
        assert BUILD.classify_event_group("Double Blind - Placebo", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo-controlled Phase: Placebo", "")[0] == "placebo"
        assert BUILD.classify_event_group("Weeks 0-24: Placebo (Placebo-Controlled Phase)", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo-Placebo", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo-matching BI 1569912", "")[0] == "placebo"

        # Double-dummy & placebo-controlled-phase active arms -> active (NOT placebo or exclude!)
        assert BUILD.classify_event_group("Drug X 10 mg + Placebo", "")[0] == "active"
        assert BUILD.classify_event_group("Secukinumab plus Matching Placebo", "")[0] == "active"
        assert BUILD.classify_event_group("Baricitinib with Placebo", "")[0] == "active"
        assert BUILD.classify_event_group("Placebo-controlled Phase: Apremilast 30 mg", "")[0] == "active"
        assert BUILD.classify_event_group("Weeks 0-24: Apremilast 20 mg (Placebo- Controlled Phase)", "")[0] == "active"

        # Genuine crossover / withdrawal switches -> exclude
        assert BUILD.classify_event_group("Placebo to Dupilumab", "")[0] == "exclude"
        assert BUILD.classify_event_group("Drug X -> Placebo", "")[0] == "exclude"
        assert BUILD.classify_event_group("Drug X / Placebo", "")[0] == "exclude"
        assert BUILD.classify_event_group("Placebo-Efgartigimod", "")[0] == "exclude"
        assert BUILD.classify_event_group("Placebo - Elinzanetant 120mg Week 13-26", "")[0] == "exclude"

    def test_region_shares_and_meddra_soc_sets(self):
        countries = [
            "United States", "Puerto Rico", "Germany", "Japan",
            "Poland", "Czechia", "Russia", "Ukraine", "Serbia and Montenegro",
            "Brazil", "China", "South Africa",
        ]
        sh = BUILD.compute_region_shares(countries)
        total = sh["us_sh"] + sh["we_sh"] + sh["eu_east_sh"] + sh["ru_ua_sh"] + sh["latam_sh"] + sh["asia_sh"] + sh["other_sh"]
        assert abs(total - 1.0) < 1e-12
        assert abs(sh["us_sh"] - (2 / len(countries))) < 1e-12  # US + Puerto Rico
        assert abs(sh["ee_sh"] - (sh["eu_east_sh"] + sh["ru_ua_sh"])) < 1e-12
        assert abs(sh["ru_ua_strict_sh"] - (2 / len(countries))) < 1e-12
        assert abs(sh["noneu_ee_other_sh"] - (1 / len(countries))) < 1e-12  # Serbia and Montenegro
        assert BUILD.compute_region_shares([]) == {}
        assert "general disorders" in BUILD.SUBJECTIVE_SOCS
        assert "investigations" in BUILD.OBJECTIVE_SOCS

    def test_drugsfda_excludes_anda_generics(self):
        anda_rec = {
            "application_number": "ANDA090123",
            "submissions": [{"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20150101"}],
        }
        assert FDA_MOD.summarize_drugsfda_record(anda_rec) is None

        nda_rec = {
            "application_number": "NDA204629",
            "sponsor_name": "TEST PHARMA",
            "openfda": {"generic_name": ["EMPAGLIFLOZIN"], "brand_name": ["JARDIANCE"]},
            "products": [{"active_ingredients": [{"name": "EMPAGLIFLOZIN"}]}],
            "submissions": [
                {"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20140801"},
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20160601", "submission_class_code": "LABELING"},
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20180901", "submission_class_code": "EFFICACY"},
                {"submission_type": "SUPPL", "submission_status": "AP", "submission_status_date": "20220101", "submission_class_code": "LABELING"},
            ],
        }
        s = FDA_MOD.summarize_drugsfda_record(nda_rec)
        assert s is not None
        assert s["application_number"] == "NDA204629"
        assert s["is_bla"] == 0
        assert s["orig_approval_year"] == 2014
        assert s["n_labeling_suppl"] == 2
        assert s["n_labeling_3yr"] == 1
        assert s["n_labeling_5yr"] == 1
        assert s["n_efficacy_suppl"] == 1
        assert s["n_efficacy_5yr"] == 1


# =============================================================================
# 2. PROCESSED PANEL DATA INTEGRITY
# =============================================================================
class TestPanelIntegrity:
    @pytest.fixture(scope="class")
    @classmethod
    def panel(cls) -> pd.DataFrame:
        return pd.read_parquet(PROC_DIR / "d30_mrct_placebo_panel.parquet")

    def test_no_duplicate_ncts_valid_scale_and_soc_coverage(self, panel: pd.DataFrame):
        assert panel["nct_id"].is_unique
        assert len(panel) >= 2700
        assert (panel["is_phase3"] == 1).sum() >= 1800
        assert (panel["is_phase2_only"] == 1).sum() >= 900
        assert ((panel["is_phase3"] == 1) & (panel["is_phase2_only"] == 1)).sum() == 0
        # Including CT.gov's "General disorders" raises SOC coverage above 95%
        soc_cov = (panel["subj_soc_share"] + panel["obj_soc_share"]).dropna().mean()
        assert soc_cov > 0.95, f"SOC coverage too low: {soc_cov:.4f}"

    def test_rate_and_share_bounds(self, panel: pd.DataFrame):
        for col in ["ctrl_oth", "act_oth", "ctrl_sae", "act_sae", "ctrl_mort", "act_mort"]:
            s = panel[col].dropna()
            assert (s >= 0.0).all() and (s <= 1.0).all(), f"{col} out of [0,1]"

        share_sum = (
            panel["us_sh"] + panel["we_sh"] + panel["eu_east_sh"]
            + panel["ru_ua_sh"] + panel["latam_sh"] + panel["asia_sh"] + panel["other_sh"]
        )
        assert np.allclose(share_sum, 1.0, atol=1e-9)
        assert np.allclose(panel["ee_sh"], panel["eu_east_sh"] + panel["ru_ua_sh"], atol=1e-9)

    def test_fdaaa_and_war_boundary_dates(self, panel: pd.DataFrame):
        pre = panel[panel["prim_comp_date"] < "2017-01-18"]
        post = panel[panel["prim_comp_date"] >= "2017-01-18"]
        assert (pre["post_fdaaa_2017"] == 0).all()
        assert (post["post_fdaaa_2017"] == 1).all()

        pre_w = panel[panel["start_date"] < "2022-02-24"]
        post_w = panel[panel["start_date"] >= "2022-02-24"]
        assert (pre_w["post_war_2022"] == 0).all()
        assert (post_w["post_war_2022"] == 1).all()


# =============================================================================
# 3. COMPLETE ECONOMETRIC RECEIPTS, RANK, FWL, TWO-WAY/WILD BOOT & WAR AUDIT
# =============================================================================
class TestEconometricReceipts:
    @pytest.fixture(scope="class")
    @classmethod
    def econ(cls) -> dict:
        return json.loads((RES_DIR / "d30_econometrics_results.json").read_text(encoding="utf-8"))

    def test_zero_rank_deficiencies_errors_or_nans_across_entire_suite(self, econ: dict):
        issues = _walk_regressions(econ)
        assert len(issues) == 0, f"Found econometric audit issues: {issues[:10]}"

    def test_core_twin_trial_signs_use_t_and_twoway_wildboot(self, econ: dict):
        for spec_key in ["p3_mol_sponsor_split", "p23_mol_sponsor_split", "p3_mol_cond_split", "p3_mol_sp_cond_split"]:
            blk = econ["block_a_core_twin_trial"][spec_key]
            for y in ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae", "ctrl_mort"]:
                rec = blk[y]
                assert rec["is_full_rank"] is True
                assert rec["use_t"] is True
                t = rec["terms"]["eu_east_sh"]
                assert np.isfinite(t["coef"]) and t["se"] > 0 and 0 <= t["p"] <= 1
            assert blk["ctrl_oth"]["terms"]["eu_east_sh"]["coef"] < -0.15
            assert blk["act_oth"]["terms"]["eu_east_sh"]["coef"] < -0.15
            assert blk["ctrl_sae"]["terms"]["eu_east_sh"]["p"] > 0.05
            assert blk["ctrl_mort"]["terms"]["eu_east_sh"]["p"] > 0.05

        wb = econ["block_a_core_twin_trial"]["twoway_and_wildboot_inference"]
        for key in ["p3_mol_sp_ctrl_oth_eu_east", "p3_mol_sp_act_oth_eu_east", "p3_triplet_ctrl_oth_eu_east"]:
            assert wb[key]["p_twoway"] < 0.01
            assert wb[key]["p_wild_rademacher_999"] <= 0.05

    def test_fwl_binscatter_exact_slope_identity(self, econ: dict):
        bs = econ["binscatter_data"]["p23_mol_sp_ee"]
        reg = econ["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]
        for y in ["ctrl_oth", "act_oth", "ctrl_sae"]:
            assert abs(bs["fwl_exact_slopes"][y] - reg[y]["terms"]["ee_sh"]["coef"]) < 1e-4

    def test_eiv_dof_deattenuation_monotonicity(self, econ: dict):
        eiv = econ["block_e_site_vs_patient_bounds"]["classical_eiv_bounds_p23"]
        lams = [r["reliability_lambda"] for r in eiv]
        assert all(lams[i] >= lams[i + 1] for i in range(len(lams) - 1))
        assert eiv[0]["df_resid"] < econ["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]["ctrl_oth"]["n"]
        b0 = eiv[0]["deattenuated_ctrl_oth"]
        assert abs(eiv[1]["deattenuated_ctrl_oth"] - round(b0 / eiv[1]["reliability_lambda"], 4)) <= 0.001

    def test_war_oos_did_and_fake2020_placebo_audit(self, econ: dict):
        blk_d = econ["block_d_war2022_shock"]
        # Unbiased OOS first stage negative & significant
        ru = blk_d["within_sponsor_reallocation_did"]["ru_ua_strict_sh"]["terms"]["exp_x_postwar"]
        assert ru["coef"] < -0.30 and ru["p"] < 0.05
        # Industry-wide post-war shift sharply negative on RU/UA
        sh_ru = blk_d["within_sponsor_postwar_shift_2017_2024"]["ru_ua_strict_sh"]["terms"]["post_war_2022"]
        assert sh_ru["coef"] < -0.03 and sh_ru["p"] < 1e-8
        # Strictly OOS fake-2020 placebo passes cleanly (null), while naive in-sample placebo fails!
        plc = blk_d["prewar_placebo_fake2020_audit"]
        assert plc["oos_placebo_ru_ua"]["terms"]["exp_x_fakepost"]["p"] > 0.10
        assert plc["oos_placebo_us"]["terms"]["exp_x_fakepost"]["p"] > 0.10
        assert plc["naive_insample_placebo_ru_ua"]["terms"]["exp_x_fakepost"]["p"] < 1e-6


# =============================================================================
# 4. GATE-2 OPENFDA LINKAGE INTEGRITY & BIOLOGIC RECOVERY
# =============================================================================
class TestGate2OpenFDA:
    def test_gate2_dataset_biologics_full_rank_and_faers_completeness(self):
        gdf = pd.read_csv(PROC_DIR / "d30_gate2_openfda_molecules.csv")
        g2 = json.loads((RES_DIR / "d30_gate2_openfda_results.json").read_text(encoding="utf-8"))

        assert len(gdf) >= 380
        assert gdf["application_number"].str.startswith(("NDA", "BLA")).all()
        assert (gdf["n_labeling_suppl"] >= gdf["n_labeling_5yr"]).all()
        assert (gdf["n_labeling_5yr"] >= gdf["n_labeling_3yr"]).all()
        assert (gdf["us_total_n"] == gdf["us_serious_n"] + gdf["us_nonserious_n"]).all()

        # Verify FDA 4-letter-suffix post-2017 biologics are recovered!
        matched_mols = set(gdf["molecule"])
        for bio in ["risankizumab", "erenumab", "fremanezumab", "tezepelumab", "anifrolumab"]:
            assert bio in matched_mols, f"Missing recovered FDA biologic: {bio}"

        # Verify 100% global FAERS coverage among US-positive drugs
        gl_cov = g2["linkage_audit"]["faers_global_queried_among_us_pos"]
        num_s, den_s = gl_cov.split("/")
        assert int(num_s) == int(den_s) and int(den_s) >= 350

        # Verify ZERO rank deficiencies or errors across ALL Gate-2 regressions
        g2_issues = _walk_regressions(g2)
        assert len(g2_issues) == 0, f"Found Gate-2 audit issues: {g2_issues[:10]}"

        # Verify first stage, Poisson GLM, and 10-step forensic audit all persisted
        fs = g2["first_stage_molecule_level_check"]["pre_act_oth_on_pre_ee_sh"]
        assert fs["n"] >= 220 and fs["terms"]["pre_ee_sh"]["coef"] < -0.20 and fs["terms"]["pre_ee_sh"]["p"] < 0.01
        assert "n_labeling_5yr_poisson_glm" in g2["drugsfda_labeling_supplements"]
        assert len(g2["faers_us_serious_forensic_audit"]) == 10


# =============================================================================
# 5. ARTIFACTS, ZERO-NaN TABLES, MANIFEST & FULL MANUSCRIPT VERIFICATION
# =============================================================================
class TestDeliverablesAndManifest:
    def test_figures_and_zero_nan_tables_exist(self):
        expected_figs = [
            "fig1_twin_trial_identification",
            "fig2_binscatter_and_disease_breadth",
            "fig3_post2017_regulatory_convergence",
            "fig4_war2022_and_accrual_bounds",
            "fig5_gate2_openfda_faers",
        ]
        for stem in expected_figs:
            png = FIG_DIR / f"{stem}.png"
            pdf = FIG_DIR / f"{stem}.pdf"
            assert png.exists() and png.stat().st_size > 20_000, f"Missing/tiny {png.name}"
            assert pdf.exists() and pdf.stat().st_size > 10_000, f"Missing/tiny {pdf.name}"

        for tab in [
            "table1_core_twin_trial.csv",
            "table2_sensitivity_subsamples.csv",
            "table3_post2017_fdaaa_decomposition.csv",
            "table4_accrual_calibration_bounds.csv",
            "table5_gate2_openfda_faers.csv",
        ]:
            p = TAB_DIR / tab
            assert p.exists() and p.stat().st_size > 200, f"Missing/empty {tab}"
            tdf = pd.read_csv(p)
            assert int(tdf.isna().sum().sum()) == 0, f"Found NaN values in {tab}!"

        t5 = pd.read_csv(TAB_DIR / "table5_gate2_openfda_faers.csv")
        assert "pre_act_oth_on_pre_ee_sh" in set(t5["outcome"])
        assert "pre_ctrl_oth_on_pre_ee_sh" in set(t5["outcome"])

    def test_manuscript_and_sha256_manifest(self):
        ms = BASE_DIR / "manuscript_d30_boost.md"
        man = BASE_DIR / "SHA256SUMS.json"
        txt = ms.read_text(encoding="utf-8")
        assert len(txt) > 15_000
        for forbidden in ["TBD", "TODO", "XXX", "[INSERT", "PLACEHOLDER"]:
            assert forbidden not in txt, f"Found placeholder {forbidden} in manuscript!"

        manifest = json.loads(man.read_text(encoding="utf-8"))
        assert len(manifest["files"]) >= 15
        for rel_path, expected_sha in manifest["files"].items():
            fp = BASE_DIR / rel_path
            assert fp.exists(), f"Manifest file missing: {rel_path}"
            actual_sha = hashlib.sha256(fp.read_bytes()).hexdigest()
            assert actual_sha == expected_sha, f"SHA-256 mismatch on {rel_path}"

    def test_manuscript_numbers_match_verified_json_receipts_across_all_5_tables(self):
        ms_txt = (BASE_DIR / "manuscript_d30_boost.md").read_text(encoding="utf-8")
        econ = json.loads((RES_DIR / "d30_econometrics_results.json").read_text(encoding="utf-8"))
        g2 = json.loads((RES_DIR / "d30_gate2_openfda_results.json").read_text(encoding="utf-8"))

        # Overview counts
        assert f"{econ['sample_overview']['p23_completed_mrct_placebo']:,}" in ms_txt
        assert f"{econ['sample_overview']['p3_completed_mrct_placebo']:,}" in ms_txt

        # Table 1 core P3, P23, Triplet, MedDRA SOC
        p3 = econ["block_a_core_twin_trial"]["p3_mol_sponsor_split"]
        p23 = econ["block_a_core_twin_trial"]["p23_mol_sponsor_split"]
        trip = econ["block_a_core_twin_trial"]["p3_mol_sp_cond_split"]
        soc = econ["block_b_sensitivity_robustness"]["meddra_soc_composition_p23_mol_sp"]
        for val in [
            p3["ctrl_oth"]["terms"]["eu_east_sh"]["coef"],
            p3["act_oth"]["terms"]["eu_east_sh"]["coef"],
            p23["ctrl_oth"]["terms"]["eu_east_sh"]["coef"],
            p23["act_oth"]["terms"]["eu_east_sh"]["coef"],
            trip["ctrl_oth"]["terms"]["eu_east_sh"]["coef"],
            soc["subj_soc_share"]["terms"]["eu_east_sh"]["coef"],
            soc["obj_soc_share"]["terms"]["eu_east_sh"]["coef"],
        ]:
            assert f"{abs(val):.4f}" in ms_txt or f"{abs(100 * val):.2f}" in ms_txt

        # Table 3 3-era lag convergence & FDAAA horse-race
        c3 = econ["block_c_post2017_fdaaa_decomposition"]["p23_3era_lag_mol_sp"]
        assert f"{abs(c3['ctrl_oth']['terms']['eu_x_20_24']['coef']):.4f}" in ms_txt
        assert f"{abs(c3['act_oth']['terms']['eu_x_20_24']['coef']):.4f}" in ms_txt

        from decimal import ROUND_HALF_UP, Decimal

        def _fmt4_candidates(x: float) -> tuple[str, str]:
            ax = abs(x)
            half_up = str(Decimal(str(ax)).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP))
            return f"{ax:.4f}", half_up

        # Table 4 ALL key accrual calibration & EIV numbers (catches stale numbers!)
        cal = {r["w_ee_accrual_ratio"]: r for r in econ["block_e_site_vs_patient_bounds"]["nonlinear_patient_share_calibration_p23"]}
        what = econ["block_e_site_vs_patient_bounds"]["implied_accrual_ratios_vs_us"]["w_hat_ee_all"]
        for w_chk in [0.5, 0.75, 1.0, what, 2.0, 3.0]:
            c_a, c_b = _fmt4_candidates(cal[w_chk]["ctrl_oth_coef"])
            a_a, a_b = _fmt4_candidates(cal[w_chk]["act_oth_coef"])
            assert (c_a in ms_txt) or (c_b in ms_txt), f"Missing Table 4 ctrl_oth for w={w_chk}"
            assert (a_a in ms_txt) or (a_b in ms_txt), f"Missing Table 4 act_oth for w={w_chk}"

        # Table 5 Gate-2 drug count, first stage, labeling, boxed warning, FAERS + forensic audit
        assert str(g2["linkage_audit"]["with_pre_approval_p3_2005_2024"]) in ms_txt
        assert str(g2["linkage_audit"]["matched_originator_nda_bla"]) in ms_txt
        for val in [
            g2["first_stage_molecule_level_check"]["pre_act_oth_on_pre_ee_sh"]["terms"]["pre_ee_sh"]["coef"],
            g2["drugsfda_labeling_supplements"]["n_labeling_5yr_ee"]["terms"]["pre_ee_sh"]["coef"],
            g2["fda_label_warnings"]["has_boxed_warning_ee"]["terms"]["pre_ee_sh"]["coef"],
            g2["faers_pharmacovigilance"]["us_serious_share_ee"]["terms"]["pre_ee_sh"]["coef"],
            g2["faers_us_serious_forensic_audit"]["01_raw_bivariate"]["terms"]["pre_ee_sh"]["coef"],
            g2["faers_us_serious_forensic_audit"]["08_plus_us_faers_vol"]["terms"]["pre_ee_sh"]["coef"],
            g2["faers_us_serious_forensic_audit"]["10_plus_sponsor_fe"]["terms"]["pre_ee_sh"]["coef"],
        ]:
            assert f"{abs(val):.4f}" in ms_txt or f"{abs(100 * val):.2f}" in ms_txt
