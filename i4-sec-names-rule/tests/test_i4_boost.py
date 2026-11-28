"""Comprehensive v4 Verification Suite for Flagship Project I4 (Journal of Banking & Finance)."""

from __future__ import annotations

import hashlib
import json
import math
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image
from pypdf import PdfReader

WORK_DIR = Path(__file__).resolve().parents[1]
RES_DIR = WORK_DIR / "results"
TBL_DIR = WORK_DIR / "tables"
FIG_DIR = WORK_DIR / "figures"

sys.path.insert(0, str(WORK_DIR / "scripts"))
from econometrics import ols_cr1_wcb, run_absorbed_twfe


def _collect_nans(obj: object, path: str = "") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            hits.append(path)
    elif isinstance(obj, dict):
        for k, v in obj.items():
            hits.extend(_collect_nans(v, f"{path}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(_collect_nans(v, f"{path}[{i}]"))
    return hits


def test_01_zero_nan_inf_in_all_receipts_and_tables() -> None:
    json_files = sorted(RES_DIR.glob("*.json"))
    assert len(json_files) >= 8, f"Expected >= 8 result JSONs, found {len(json_files)}"
    for p in json_files:
        data = json.loads(p.read_text(encoding="utf-8"))
        nans = _collect_nans(data)
        assert not nans, f"NaN/Inf detected in {p.name}: {nans[:5]}"

    csv_files = sorted(TBL_DIR.glob("*.csv"))
    assert len(csv_files) >= 16, f"Expected >= 16 CSV tables, found {len(csv_files)}"
    for p in csv_files:
        df = pd.read_csv(p)
        assert len(df) > 0, f"Empty CSV table: {p.name}"
        na_cols = {c: int(df[c].isna().sum()) for c in df.columns if df[c].isna().any()}
        assert not na_cols, f"NaN values detected in {p.name}: {na_cols}"
        for c in df.select_dtypes(include=[np.number]).columns:
            assert np.isfinite(df[c].to_numpy()).all(), f"Non-finite values in {p.name}:{c}"


def test_02_redemption_sign_fix_correlation_jump() -> None:
    r1 = json.loads((RES_DIR / "01_panel_audit.json").read_text(encoding="utf-8"))
    nr = r1["negative_redemption_audit"]["POOLED_MON1_TO_MON3"]
    fv = r1["flow_sign_fix_validation"]
    assert 15.0 <= nr["pct_negative_of_nonnull"] <= 25.0
    assert fv["pearson_raw_unclipped_vs_tna"] < 0.20
    assert fv["pearson_fixed_abs_vs_tna"] > 0.90
    assert fv["spearman_fixed_abs_vs_tna"] > 0.85
    assert fv["neg_subset_pearson_fixed_vs_tna"] > 0.90


def test_03_repaired_lookthrough_vanguard_and_cib_ifa_sanity() -> None:
    r3 = json.loads((RES_DIR / "03_holdings_lookthrough.json").read_text(encoding="utf-8"))
    vg = r3["vanguard_sanity_check"]
    for sid, target_eq in [
        ("S000002929", 20.0),
        ("S000002927", 40.0),
        ("S000002930", 60.0),
        ("S000002928", 80.0),
    ]:
        assert abs(vg[sid]["eq_2023q2"] - target_eq) <= 3.5
        assert abs(vg[sid]["eq_2026"] - target_eq) <= 3.5
    assert vg["S000004397"]["eq_2023q2"] >= 90.0

    # Capital Income Builder & Income Fund of America MUST be resolved as balanced (~65-78% eq, ~18-28% bond), NOT 100% eq!
    rep = r3["repaired_underlying_audit_2023q2"]
    assert 65.0 <= rep["S000009000"]["eq_2023q2"] <= 82.0
    assert 15.0 <= rep["S000009000"]["bond_2023q2"] <= 30.0
    assert 60.0 <= rep["S000008814"]["eq_2023q2"] <= 78.0
    assert 18.0 <= rep["S000008814"]["bond_2023q2"] <= 32.0

    # Zero TIER3_FALLBACK_EQ silent defaults and zero UNMAPPED in Top-100!
    top100 = pd.read_csv(TBL_DIR / "table_lookthrough_100pos_audit.csv")
    assert len(top100) == 100
    assert (top100["MATCH_TIER"] == "TIER3_FALLBACK_EQ").sum() == 0
    assert (top100["MATCH_TIER"] == "TIER_UNMAPPED").sum() == 0
    assert r3["tier_aum_share_ma_gvi_2023q2_pct"].get("TIER_UNMAPPED", 0.0) < 2.0


def test_04_full_rank_and_non_singleton_invariants() -> None:
    rng = np.random.default_rng(42)
    X_bad = np.column_stack([rng.normal(size=50), np.ones(50)])
    X_bad = np.column_stack([X_bad, X_bad[:, 0] * 2.0])
    with pytest.raises(ValueError, match="Rank-deficient"):
        ols_cr1_wcb(rng.normal(size=50), X_bad, np.repeat(np.arange(10), 5), do_wcb=False)

    def check_ranks(obj: object, path: str = "") -> None:
        if isinstance(obj, dict):
            if "rank" in obj and "k" in obj:
                assert obj["rank"] == obj["k"], f"Rank deficiency in {path}: rank={obj['rank']} < k={obj['k']}"
            for k, v in obj.items():
                check_ranks(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_ranks(v, f"{path}[{i}]")

    for fn in (
        "03_holdings_lookthrough.json",
        "04_econometrics_results.json",
        "04b_counterfactual_sensitivity.json",
        "05_monthly_flow_results.json",
    ):
        check_ranks(json.loads((RES_DIR / fn).read_text(encoding="utf-8")), fn)


def test_05_fwl_absorbed_fe_matches_explicit_lsdv_wcb_to_1e12() -> None:
    rng = np.random.default_rng(20261126)
    rows = []
    for g in range(12):
        for u in range(3):
            for t in range(6):
                x1 = float(int(u == 0) * int(t >= 3))
                x2 = float(rng.normal())
                y = 0.5 * x1 + 0.3 * x2 + 0.7 * g - 0.4 * u + 0.2 * t + float(rng.normal(scale=0.5))
                rows.append({"cl": f"C_{g}", "unit": f"U_{g}_{u}", "t": t, "x1": x1, "x2": x2, "y": y})
    df = pd.DataFrame(rows)
    fwl = run_absorbed_twfe(df, "y", ["x1", "x2"], "unit", "cl", "t", test_col_idx=0, n_boot=199, seed=20261126)
    X_lsdv = np.column_stack(
        [
            df[["x1", "x2"]].to_numpy(),
            pd.get_dummies(df["t"].astype(str), drop_first=True, dtype=float).to_numpy(),
            pd.get_dummies(df["unit"].astype(str), drop_first=False, dtype=float).to_numpy(),
        ]
    )
    lsdv = ols_cr1_wcb(df["y"].to_numpy(), X_lsdv, df["cl"].to_numpy(), test_col_idx=0, n_boot=199, seed=20261126)
    for key in ("beta", "se_cr1", "t_cr1", "p_cr1", "p_wcb"):
        assert np.isclose(fwl[key], lsdv[key], atol=1e-12, rtol=1e-12)


def test_06_per_fund_50_renamers_statutory_audit_and_lexical_screen() -> None:
    ren50 = pd.read_csv(TBL_DIR / "table_50_renamers_statutory_audit.csv")
    ret50 = pd.read_csv(TBL_DIR / "table_50_retained_statutory_audit.csv")
    unreg = pd.read_csv(TBL_DIR / "table_unregulated_renamers_control.csv")
    r2b = json.loads((RES_DIR / "02b_per_fund_statutory_audit.json").read_text(encoding="utf-8"))

    assert len(ren50) == 50 and ren50["SERIES_ID"].is_unique
    assert len(ret50) == 50 and ret50["SERIES_ID"].is_unique
    assert len(unreg) >= 150
    assert r2b["gv_lexical_screen_count"] == 35
    assert r2b["effective_date_audit"]["pass1_pre_june11_2026"] == 35
    assert r2b["effective_date_audit"]["pass1_parsed_total"] == 36
    assert r2b["effective_date_audit"]["pass2_verified_total"] == 50
    assert r2b["effective_date_audit"]["pass2_pre_june11_2026"] == 49
    # Verify Vanguard unchanged policy & iShares benchmark index rename explicitly recorded
    vg_rows = ren50[ren50["COMPLEX_ID"] == "VANGUARD"]
    assert len(vg_rows) == 4 and (vg_rows["EXPLICIT_UNCHANGED_POLICY"] == 1).all()
    ish_rows = ren50[ren50["COMPLEX_ID"] == "BLACKROCK / ISHARES"]
    assert len(ish_rows) == 2 and (ish_rows["PAIRED_BENCHMARK_INDEX_RENAME"] == 1).all()


def test_07_partial_identification_bounds_and_multiquarter_paths() -> None:
    r3 = json.loads((RES_DIR / "03_holdings_lookthrough.json").read_text(encoding="utf-8"))
    pi_gvi = r3["partial_identification_bounds"]["GVI_ALL_PAIRED"]["ACTIVE_TOWARD_80"]
    assert pi_gvi["n_paired_universe"] >= 2482
    assert pi_gvi["n_boundary_crossers_droppers"] == 0
    lo_id, hi_id = pi_gvi["identified_set_beta_interval"]
    assert lo_id < pi_gvi["repaired_neutral_point"]["beta"] < hi_id < 0.0
    traj = pd.read_csv(TBL_DIR / "table_multiquarter_portfolio_paths.csv")
    assert set(traj["snapshot"]) == {"2023Q2", "2024Q2", "2025Q2", "2026Q2_Q3"}


def test_08_counterfactual_placebos_honest_did_and_cs2021() -> None:
    r4b = json.loads((RES_DIR / "04b_counterfactual_sensitivity.json").read_text(encoding="utf-8"))
    pl = pd.read_csv(TBL_DIR / "table_placebo_audits.csv")
    assert len(pl) == 15
    assert (pl["p_wcb"] > 0.10).all(), "Expected all historical & unregulated placebos to be null at 10%"
    for key in ("A3_GVI_ALL", "FAQ2_GV_NO_INC", "FAQ4_GV_NO_INC_HOLD_LT80"):
        h = r4b["phase_and_honest_did"][key]
        assert h["rambachan_roth_delta_sd"]["breakdown_M_star"] >= 0.0
        assert h["rambachan_roth_delta_rm"]["breakdown_Mbar_star"] >= 0.0
    assert r4b["phase_and_honest_did"]["FAQ2_GV_NO_INC"]["joint_pre_F"]["p"] < 0.05
    assert r4b["phase_and_honest_did"]["FAQ4_GV_NO_INC_HOLD_LT80"]["joint_pre_F"]["p"] < 0.01
    assert "EARLY_DUE_VS_LATE_LARGE_NOT_YET_DUE" in r4b["callaway_santanna_oncycle_cohorts"]


def test_09_all_v4_figures_exist_and_300dpi() -> None:
    expected = [
        "fig1_statutory_timing_and_concentration",
        "fig2_event_study_placebos_and_honest_did",
        "fig3_lookthrough_paths_and_partial_id_bounds",
        "fig4_exploratory_monthly_flows",
        "figA1_redemption_sign_audit",
    ]
    for stem in expected:
        png_p = FIG_DIR / f"{stem}.png"
        pdf_p = FIG_DIR / f"{stem}.pdf"
        assert png_p.exists() and png_p.stat().st_size > 100_000
        assert pdf_p.exists() and pdf_p.stat().st_size > 15_000
        with Image.open(png_p) as im:
            w, h = im.size
            dpi = im.info.get("dpi", (300, 300))
            assert w >= 2800 and h >= 900
            assert dpi[0] >= 299.0 and dpi[1] >= 299.0


def test_10_live_citations_and_authorship_zero_leaks() -> None:
    cits = json.loads((RES_DIR / "07_verified_references_crossref.json").read_text(encoding="utf-8"))
    assert cits["n_academic_dois_verified_live_crossref"] == 19
    assert cits["n_official_sec_releases"] == 6
    assert cits["all_bibliography_cited_in_body"] is True
    assert cits["all_body_citations_in_bibliography"] is True
    dois = {r["doi"] for r in cits["references"] if r.get("doi")}
    for req_doi in (
        "10.1016/j.jbankfin.2017.07.008",
        "10.2139/ssrn.5844262",
        "10.1016/j.jeconom.2020.12.001",
        "10.1093/restud/rdad018",
        "10.1111/j.1468-0262.2004.00555.x",
    ):
        assert req_doi in dois

    md = (WORK_DIR / "manuscript_i4_boost.md").read_text(encoding="utf-8")
    for req_txt in (
        "Zijian Zeng",
        "Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA",
        "zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my",
        "33-11368",
        "IC-35963",
        "Names Rule FAQs",
        "2026-19",
        "0.20 < w < 0.80",
        "0.043",
        "0.003",
        "0.170",
    ):
        assert req_txt in md, f"Missing required anchor in manuscript: {req_txt}"
    for forbidden in ("Target Venues", "Target Format", "Track A", "Track B", "IC-35962", "Non-Compliant"):
        assert forbidden not in md, f"Forbidden string leaked in manuscript: {forbidden}"


def test_11_pdfs_zero_leak_and_sha256_manifest_sync() -> None:
    compile_pdf = runpy.run_path(str(WORK_DIR / "scripts/08_compile_manuscript_pdf.py"))
    for pdf_fn, min_pages in [("manuscript_i4_boost.pdf", 8), ("supplementary_i4_jbf.pdf", 3)]:
        p = WORK_DIR / pdf_fn
        assert p.exists()
        pages, leaks = compile_pdf["verify_pdf_zero_leaks"](p)
        assert pages >= min_pages, f"{pdf_fn} has only {pages} pages"
        assert not leaks, f"Leaks detected in {pdf_fn}: {leaks}"
        txt = " ".join((pg.extract_text() or "") for pg in PdfReader(p).pages)
        assert "Zijian Zeng" in txt
        assert "UCSI University" in txt

    checksums = json.loads((WORK_DIR / "SHA256SUMS.json").read_text(encoding="utf-8"))["files"]
    for rel in (
        "manuscript_i4_boost.pdf",
        "manuscript_i4_boost.md",
        "supplementary_i4_jbf.pdf",
        "supplementary_i4_jbf.md",
        "REFEREE_RESPONSE_v4.md",
        "tables/table_50_renamers_statutory_audit.csv",
        "tables/table_partial_id_bounds.csv",
        "tables/table_placebo_audits.csv",
        "tables/table_honest_did_sensitivity.csv",
        "results/10_v4_manuscript_receipt.json",
    ):
        actual = hashlib.sha256((WORK_DIR / rel).read_bytes()).hexdigest().upper()
        assert checksums[rel]["sha256"] == actual, f"SHA256 mismatch on {rel}"
