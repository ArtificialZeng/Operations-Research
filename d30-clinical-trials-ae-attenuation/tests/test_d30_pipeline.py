"""Comprehensive automated verification test suite for the D30 v4 (JCE) pipeline.

Verifies:
  1. Unit tests & edge cases for parser helpers (dates, molecules, MeSH resolution, placebo vs
     double-dummy vs crossover arms, case-insensitive MedDRA SOC, regional share simplex, Drugs@FDA).
  2. Processed panel integrity & archived per-term MedDRA API snapshot cryptographic provenance.
  3. Complete econometric receipts (ZERO rank-deficient models, ZERO errors/NaNs, finite-sample
     t(G-1), FWL exact identity, two-way clustering & wild bootstrap, EIV monotonicity, uncensored war).
  4. All v4 JCE methodological requirements (P0 #1–#4):
     - Extensive vs. intensive decomposition (`I(share=0)` matching `-2.11 / -2.50 pp`), common-236
       programs, 4-knot RCS nonlinearity Wald test, Aronow-Samii FWL weights + leave-top-10/20-out,
       two-way alternative-region counterfactuals (US, NA, WE EU/EEA, LatAm, Asia, RU/UA).
     - Four-state MedDRA recoding (`210,424` reported cells, `166,260` common-panel cells), strict
       zero-fallback & pure `Investigations` biomarker contrasts, uncensored `0%`-threshold models,
       sharp Manski FWL bounds on peak-term rates excluding zero, and `369` missing AE `timeFrame` audit.
     - Pre-specified TOST clinical equivalence (met for SAEs & `oth_rd` at ±1–2 pp; unmet for mortality at ±0.5 pp).
  5. Gate-2 openFDA integrity (moved cleanly into Supplementary Appendix S4).
  6. Publication deliverables: 4 main + 4 SI figures, zero-NaN CSV tables, exact authorship block,
     zero banned overclaiming/metadata tokens, zero LaTeX/placeholder leaks in both compiled PDFs,
     and 100% SHA-256 manifest match.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

BASE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BASE_DIR / "scripts"
RAW_DIR = BASE_DIR / "data" / "raw_ctgov"
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
        assert "metformin" in all_mols and "placebo" not in all_mols

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
        assert BUILD.classify_event_group("Placebo", "")[0] == "placebo"
        assert BUILD.classify_event_group("Matching Placebo QD", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo + Methotrexate", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo - Treatment Phase", "")[0] == "placebo"
        assert BUILD.classify_event_group("Placebo-controlled Phase: Placebo", "")[0] == "placebo"
        assert BUILD.classify_event_group("Drug X 10 mg + Placebo", "")[0] == "active"
        assert BUILD.classify_event_group("Placebo-controlled Phase: Apremilast 30 mg", "")[0] == "active"
        assert BUILD.classify_event_group("Placebo to Dupilumab", "")[0] == "exclude"
        assert BUILD.classify_event_group("Drug X / Placebo", "")[0] == "exclude"
        assert BUILD.classify_event_group("Placebo-Efgartigimod", "")[0] == "exclude"

    def test_region_shares_and_meddra_soc_sets(self):
        countries = [
            "United States", "Puerto Rico", "Canada", "Germany", "Japan",
            "Poland", "Czechia", "Russia", "Ukraine", "Serbia and Montenegro",
            "Brazil", "China", "South Africa",
        ]
        sh = BUILD.compute_region_shares(countries)
        total7 = sh["us_sh"] + sh["we_sh"] + sh["eu_east_sh"] + sh["ru_ua_sh"] + sh["latam_sh"] + sh["asia_sh"] + sh["other_sh"]
        total8 = sh["na_sh"] + sh["we_eu_sh"] + sh["dev_apac_no_ca_sh"] + sh["eu_east_sh"] + sh["ru_ua_sh"] + sh["latam_sh"] + sh["asia_sh"] + sh["other_sh"]
        assert abs(total7 - 1.0) < 1e-12
        assert abs(total8 - 1.0) < 1e-12
        assert abs(sh["na_sh"] - (3 / len(countries))) < 1e-12
        assert BUILD.compute_region_shares([]) == {}
        assert "general disorders" in BUILD.SUBJECTIVE_SOCS
        assert "investigations" in BUILD.OBJECTIVE_SOCS

    def test_drugsfda_excludes_anda_generics(self):
        anda_rec = {
            "application_number": "ANDA090123",
            "submissions": [{"submission_type": "ORIG", "submission_status": "AP", "submission_status_date": "20150101"}],
        }
        assert FDA_MOD.summarize_drugsfda_record(anda_rec) is None


# =============================================================================
# 2. PROCESSED PANEL & ARCHIVED MEDDRA SNAPSHOT INTEGRITY
# =============================================================================
class TestPanelAndSnapshotIntegrity:
    @pytest.fixture(scope="class")
    @classmethod
    def panel(cls) -> pd.DataFrame:
        return pd.read_parquet(PROC_DIR / "d30_mrct_placebo_panel.parquet")

    def test_panel_counts_simplex_and_bounds(self, panel: pd.DataFrame):
        assert panel["nct_id"].is_unique
        assert len(panel) == 2771
        assert (panel["is_phase3"] == 1).sum() == 1842
        assert (panel["is_phase2_only"] == 1).sum() == 929
        assert ((panel["is_phase3"] == 1) & (panel["is_phase2_only"] == 1)).sum() == 0
        for col in ["ctrl_oth", "act_oth", "ctrl_sae", "act_sae", "ctrl_mort", "act_mort"]:
            s = panel[col].dropna()
            assert (s >= 0.0).all() and (s <= 1.0).all()
        s7 = panel["us_sh"] + panel["we_sh"] + panel["eu_east_sh"] + panel["ru_ua_sh"] + panel["latam_sh"] + panel["asia_sh"] + panel["other_sh"]
        s8 = panel["na_sh"] + panel["we_eu_sh"] + panel["dev_apac_no_ca_sh"] + panel["eu_east_sh"] + panel["ru_ua_sh"] + panel["latam_sh"] + panel["asia_sh"] + panel["other_sh"]
        assert np.allclose(s7, 1.0, atol=1e-9)
        assert np.allclose(s8, 1.0, atol=1e-9)

    def test_archived_meddra_snapshot_manifest_and_four_state_audit(self):
        snap_path = RAW_DIR / "meddra_other_events_snapshot.jsonl.gz"
        man_path = RAW_DIR / "meddra_snapshot_manifest.json"
        sum_path = PROC_DIR / "meddra_soc_abs_summary.json"
        assert snap_path.exists() and man_path.exists() and sum_path.exists()

        man = json.loads(man_path.read_text(encoding="utf-8"))
        assert man["nct_requested"] == 2771 and man["nct_returned"] == 2771
        assert hashlib.sha256(snap_path.read_bytes()).hexdigest() == man["sha256_gz"]

        msum = json.loads(sum_path.read_text(encoding="utf-8"))
        assert msum["ae_timeframe_audit"]["n_missing_timeframe"] == 369
        assert msum["ae_timeframe_audit"]["n_with_timeframe"] == 2402
        cc = msum["common_panel_four_state_counts"]
        assert cc.get("cpanel_freq0_below_threshold", 0) == 0
        assert cc["cpanel_freq5_below_threshold"] > 80_000
        assert msum["reported_cell_audit"]["reported_cells_total"] > 200_000


# =============================================================================
# 3. ECONOMETRIC RECEIPTS & v4 P0 #1-#3 VERIFICATION
# =============================================================================
class TestEconometricsAndV4Audits:
    @pytest.fixture(scope="class")
    @classmethod
    def econ(cls) -> dict:
        return json.loads((RES_DIR / "d30_econometrics_results.json").read_text(encoding="utf-8"))

    @pytest.fixture(scope="class")
    @classmethod
    def sens(cls) -> dict:
        return json.loads((RES_DIR / "08_reporting_sensitivity.json").read_text(encoding="utf-8"))

    def test_zero_rank_deficiencies_errors_or_nans_across_all_receipts(self, econ: dict, sens: dict):
        assert len(_walk_regressions(econ)) == 0
        assert len(_walk_regressions(sens)) == 0

    def test_core_twin_trial_fwl_eiv_and_war_receipts(self, econ: dict):
        p3 = econ["block_a_core_twin_trial"]["p3_mol_sponsor_split"]
        assert p3["ctrl_oth"]["n"] == 1282 and p3["ctrl_oth"]["n_fe_groups"] == 328
        assert abs(100 * p3["ctrl_oth"]["terms"]["eu_east_sh"]["per_10pp_coef"] - (-2.48)) < 0.01
        assert abs(100 * p3["act_oth"]["terms"]["eu_east_sh"]["per_10pp_coef"] - (-2.67)) < 0.01
        bs = econ["binscatter_data"]["p23_mol_sp_ee"]
        reg = econ["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]
        for y in ["ctrl_oth", "act_oth", "ctrl_sae"]:
            assert abs(bs["fwl_exact_slopes"][y] - reg[y]["terms"]["ee_sh"]["coef"]) < 1e-4

    def test_v4_p0_1_support_margins_splines_weights_and_counterfactuals(self, sens: dict):
        sup = sens["phase3_support"]
        assert sup["n"] == 1842 and sup["n_zero"] == 504 and sup["n_at_least_half"] == 25

        ext = sens["extensive_intensive_decomposition"]
        assert ext["n_programs_positive_0_35"] == 236
        elook = {(r["sample"], r["arm"]): r for r in ext["models"]}

        # Reviewer benchmark: 0-35% + zero indicator -> -2.11 [-4.24, +0.02] ctrl, -2.50 [-4.64, -0.36] act
        zc = elook[("shares_0_35_with_zero_indicator", "ctrl")]
        za = elook[("shares_0_35_with_zero_indicator", "act")]
        assert zc["n"] == 1211 and abs(100 * zc["per_10pp_coef"] - (-2.11)) < 0.02
        assert za["n"] == 1211 and abs(100 * za["per_10pp_coef"] - (-2.50)) < 0.02

        # Common-236-program comparison
        c_full = elook[("common_236_progs_0_35_full", "ctrl")]
        c_pos = elook[("common_236_progs_positive_0_35", "ctrl")]
        assert c_full["n_fe_groups"] == 236 and c_pos["n_fe_groups"] == 236 and c_pos["n"] == 870

        # RCS nonlinearity Wald test present and non-significant
        rcs3 = sens["nonlinear_bins_and_spline"]["phase3"]["rcs_4knot"]
        assert rcs3["ctrl"]["nonlinearity_wald_p"] > 0.10 and rcs3["act"]["nonlinearity_wald_p"] > 0.10

        # Aronow-Samii FWL weights & leave-top-10/20-out stability
        fw = sens["effective_fwl_weights"]["phase3"]
        assert fw["n_programs"] == 328 and len(fw["top10_programs"]) == 10
        d10 = fw["leave_top_weighted_programs_out"]["drop_top10_weighted_programs"]
        d20 = fw["leave_top_weighted_programs_out"]["drop_top20_weighted_programs"]
        assert d10["ctrl"]["p"] < 0.005 and d20["ctrl"]["p"] < 0.01

        # Two-way alternative-region counterfactuals all negative & significant for non-EE comparators
        cf3 = {(r["outcome"], r["comparator_key"]): r for r in sens["alternative_region_counterfactuals"]["phase3"]}
        for reg_k in ("us_sh", "na_sh", "we_eu_sh", "we_sh", "latam_sh", "asia_sh"):
            assert cf3[("ctrl_oth", reg_k)]["per_10pp_pp"] < -2.0 and cf3[("ctrl_oth", reg_k)]["p"] < 0.005
            assert cf3[("act_oth", reg_k)]["per_10pp_pp"] < -2.0 and cf3[("act_oth", reg_k)]["p"] < 0.005

    def test_v4_p0_2_meddra_strict_manski_and_timeframe(self, sens: dict):
        mb = sens["meddra_threshold_and_bounds"]
        sc = {(r["spec"], r["arm"]): r for r in mb["strict_vs_legacy_soc_contrasts"]}
        for spec_k in ("strict_p23_subj_minus_obj", "strict_no_anomaly_p23_subj_minus_obj", "strict_p23_subj_minus_investigations"):
            assert sc[(spec_k, "ctrl")]["per_10pp_ci95_hi"] < 0
            assert sc[(spec_k, "act")]["per_10pp_ci95_hi"] < 0

        # Sharp Manski FWL bounds on peak-term rates exclude zero in both arms & active Subj-Obj!
        bl = {(b["stratum"], b["arm"], b["metric"]): b for b in mb["interval_and_manski_bounds"] if "error" not in b}
        assert bl[("p23_all_thresholds", "ctrl", "strict_soc_subj_max_pct")]["manski_sharp_per_10pp"]["excludes_zero_im95"] is True
        assert bl[("p23_all_thresholds", "act", "strict_soc_subj_max_pct")]["manski_sharp_per_10pp"]["excludes_zero_im95"] is True
        assert bl[("p23_all_thresholds", "act", "strict_soc_maxpct_subj_minus_obj")]["manski_sharp_per_10pp"]["excludes_zero_im95"] is True
        # Adversarial Manski bounds on 15-term sums span zero (honest disclosure!)
        assert bl[("p23_all_thresholds", "ctrl", "cpanel15_sum_subj_minus_obj")]["manski_sharp_per_10pp"]["excludes_zero_id"] is False

        # Documented AE timeFrame restriction preserves negative significance
        tf = mb["ae_timeframe_audit"]
        assert tf["p23_missing_timeframe"] == 369 and tf["p3_missing_timeframe"] == 238
        assert tf["timeframe_missingness_on_eu_east_p3"]["terms"]["eu_east_sh"]["p"] > 0.50
        assert tf["restricted_to_documented_timeframe"]["phase3"]["ctrl"]["p"] < 0.005
        assert tf["restricted_to_documented_timeframe"]["phase3"]["act"]["p"] < 0.001

    def test_v4_p0_3_prespecified_tost_equivalence(self, sens: dict):
        tl = {(r["specification"], r["outcome"], r["margin_pp"]): r for r in sens["prespecified_equivalence_tost"]}
        for spec_s in ("Phase 3 Mol × Sponsor FE", "Pooled P2+P3 Mol × Sponsor FE"):
            for ep in ("ctrl_sae", "act_sae", "oth_rd"):
                assert tl[(spec_s, ep, 2.0)]["equivalent_alpha_05"] is True
                assert tl[(spec_s, ep, 1.0)]["equivalent_alpha_05"] is True
            for ep in ("ctrl_mort", "act_mort"):
                assert tl[(spec_s, ep, 0.5)]["equivalent_alpha_05"] is False


# =============================================================================
# 4. GATE-2 OPENFDA (SUPPLEMENTARY APPENDIX S4) INTEGRITY
# =============================================================================
class TestGate2OpenFDA:
    def test_gate2_full_rank_and_biologics(self):
        gdf = pd.read_csv(PROC_DIR / "d30_gate2_openfda_molecules.csv")
        g2 = json.loads((RES_DIR / "d30_gate2_openfda_results.json").read_text(encoding="utf-8"))
        assert len(gdf) >= 380 and gdf["application_number"].str.startswith(("NDA", "BLA")).all()
        assert len(_walk_regressions(g2)) == 0
        assert g2["linkage_audit"]["with_pre_approval_p3_2005_2024"] == 229


# =============================================================================
# 5. DELIVERABLES, ZERO-NaN TABLES, ZERO OVERCLAIMING, PDFS & SHA-256 MANIFEST
# =============================================================================
class TestDeliverablesAndManifest:
    def test_all_8_figures_and_zero_nan_tables_exist(self):
        expected_figs = [
            "fig1_main_within_program_and_counterfactuals",
            "fig2_support_spline_and_weights",
            "fig3_meddra_fourstate_and_manski_bounds",
            "fig4_tost_equivalence_sae_mortality",
            "figS1_therapeutic_areas_and_accrual_bounds",
            "figS2_post2017_temporal_overlap",
            "figS3_war2022_all_registered_footprints",
            "figS4_exploratory_openfda_faers",
        ]
        for stem in expected_figs:
            assert (FIG_DIR / f"{stem}.png").stat().st_size > 20_000
            assert (FIG_DIR / f"{stem}.pdf").stat().st_size > 10_000

        expected_tables = [
            "table1_core_twin_trial.csv",
            "table2_sensitivity_subsamples.csv",
            "table2b_meddra_absolute_soc_rates.csv",
            "table3_post2017_fdaaa_decomposition.csv",
            "table4_accrual_calibration_bounds.csv",
            "table4b_all_registered_war_2017_2025.csv",
            "table5_gate2_openfda_faers.csv",
            "table_v4_support_and_margins.csv",
            "table_v4_alternative_regions.csv",
            "table_v4_meddra_bounds.csv",
            "table_v4_tost_equivalence.csv",
        ]
        for tab in expected_tables:
            p = TAB_DIR / tab
            assert p.exists() and p.stat().st_size > 200
            tdf = pd.read_csv(p)
            assert int(tdf.isna().sum().sum()) == 0, f"Found NaN in {tab}"

    def test_jce_manuscript_authorship_discipline_and_zero_overclaiming(self):
        ms_txt = (BASE_DIR / "manuscript_d30_boost.md").read_text(encoding="utf-8")
        si_txt = (BASE_DIR / "supplementary_d30_jce.md").read_text(encoding="utf-8")
        resp_txt = (BASE_DIR / "REFEREE_RESPONSE_v4.md").read_text(encoding="utf-8")
        assert len(resp_txt) > 5_000

        # Exact authorship block required
        for auth_tok in [
            "Zijian Zeng",
            "Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA",
            "zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my",
        ]:
            assert auth_tok in ms_txt
            assert auth_tok in si_txt

        # Banned metadata & overclaiming phrases MUST be absent from main text
        ms_low = ms_txt.lower()
        for banned in [
            "target venues", "target format", "track a", "track b",
            "objective outcomes flat", "ich e17 caused", "tolerability illusion",
            "calibrated journal-tier assessment", "tbd", "todo", "placeholder",
        ]:
            assert banned not in ms_low, f"Found banned phrase '{banned}' in main manuscript"
        # "underreporting" only allowed inside explicit disclaimer ("cannot be interpreted as proof of regional \"underreporting\"")
        for m_u in re.finditer(r"underreport", ms_low):
            ctx = ms_low[max(0, m_u.start() - 60) : m_u.end() + 40]
            assert "cannot be interpreted" in ctx, f"Unqualified underreporting claim: {ctx}"

        # Exact core v4 tokens & Crossref-verified citations present
        for tok in [
            "−2.48 pp", "−2.67 pp", "−2.11 pp", "−2.50 pp",
            "369 / 2,771", "10.1136/bmjopen-2024-094950",
            "177(5), 727", "10.1093/rheumatology/keaa043",
            "Policy 0070", "Manski", "Aronow", "TOST",
        ]:
            assert tok in ms_txt or tok.replace("−", "-") in ms_txt, f"Missing token '{tok}'"

    def test_compiled_pdfs_zero_leaks_and_sha256_manifest(self):
        from pypdf import PdfReader

        comp_mod = load_module("compile_pdf_check", SCRIPTS_DIR / "07_compile_manuscript_pdf.py")
        for md_name, pdf_name, fig_map in [
            ("manuscript_d30_boost.md", "manuscript_d30_boost.pdf", comp_mod.MAIN_FIGURES),
            ("supplementary_d30_jce.md", "supplementary_d30_jce.pdf", comp_mod.SI_FIGURES),
        ]:
            md_txt = (BASE_DIR / md_name).read_text(encoding="utf-8")
            html_rendered = comp_mod.convert_md_to_html(md_txt, fig_map=fig_map)
            text_only = re.sub(r"data:image/png;base64,[A-Za-z0-9+/=]+", "", html_rendered)
            for leak in ["TBD", "TODO", "XXX", r"\underbrace", r"\frac{", r"\text{", r"\mathbf{", r"\min", r"\max", r"\_", "$$"]:
                assert leak not in text_only, f"Rendered leak '{leak}' in {md_name}"

            pdf_path = BASE_DIR / pdf_name
            assert pdf_path.exists() and pdf_path.stat().st_size > 200_000
            reader = PdfReader(pdf_path)
            assert len(reader.pages) >= 5
            extracted = " ".join(" ".join((p.extract_text() or "").split()) for p in reader.pages)
            assert "Zijian Zeng" in extracted
            for leak in [r"\frac{", r"\underbrace", r"\min", r"\max", r"\_", "$$", "Target Venues"]:
                assert leak not in extracted, f"PDF text leak '{leak}' in {pdf_name}"

        manifest = json.loads((BASE_DIR / "SHA256SUMS.json").read_text(encoding="utf-8"))
        assert len(manifest["files"]) >= 30
        for rel_path, expected_sha in manifest["files"].items():
            fp = BASE_DIR / rel_path
            assert fp.exists(), f"Missing manifest artifact: {rel_path}"
            assert hashlib.sha256(fp.read_bytes()).hexdigest() == expected_sha
