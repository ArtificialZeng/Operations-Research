"""Comprehensive pytest verification suite for I4 SEC Rule 35d-1 /boost pipeline.

Enforces all 8 mandatory invariants:
1. Zero NaN/Inf across all output JSON receipts and CSV tables.
2. Exact abs(REDEMPTION) sign-fix correlation jump (raw < 0.20 vs fixed > 0.85).
3. Exact 4-tier look-through sanity checks (Vanguard LifeStrategy 20/80, 40/60, 60/40, 80/20
   within +/-5 pp of target in 2023Q2 & 2026; Vanguard Capital Growth S000004397 pure equity).
4. Strict full-rank (rank(X) == K) and non-singleton FE invariants across ALL saved regressions,
   plus unit test asserting ols_cr1_wcb raises ValueError on rank-deficient X.
5. Exact FWL absorbed-FE vs. brute-force explicit LSDV CR1 & WCB equivalence to atol=1e-12
   on synthetic clustered panels (both unit+time TWFE and complex-by-quarter FE).
6. Exact sync between manuscript_i4_boost.md, CSV tables, JSON receipts, and 100% citation audit.
7. Zero Markdown / LaTeX / HTML-entity leak verification on compiled manuscript_i4_boost.pdf.
8. All 5 PNG & PDF figures exist, non-empty, and meet >=300 DPI publication resolution.
"""

from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from PIL import Image
from pypdf import PdfReader

WORK_DIR = Path(r"D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126")
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
    assert len(json_files) >= 6, f"Expected >= 6 result JSONs, found {len(json_files)}"
    for p in json_files:
        data = json.loads(p.read_text(encoding="utf-8"))
        nans = _collect_nans(data)
        assert not nans, f"NaN/Inf detected in {p.name}: {nans[:5]}"

    csv_files = sorted(TBL_DIR.glob("*.csv"))
    assert len(csv_files) >= 9, f"Expected >= 9 CSV tables, found {len(csv_files)}"
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
    assert fv["pearson_raw_unclipped_vs_tna"] < 0.20, f"Expected raw r < 0.20, got {fv['pearson_raw_unclipped_vs_tna']}"
    assert fv["pearson_fixed_abs_vs_tna"] > 0.85, f"Expected fixed r > 0.85, got {fv['pearson_fixed_abs_vs_tna']}"
    assert fv["spearman_fixed_abs_vs_tna"] > 0.85
    assert fv["neg_subset_pearson_fixed_vs_tna"] > 0.90


def test_03_lookthrough_vanguard_and_capital_growth_sanity() -> None:
    r1 = json.loads((RES_DIR / "01_panel_audit.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_holdings_lookthrough.json").read_text(encoding="utf-8"))
    vg = r3["vanguard_sanity_check"]

    for sid, target_eq in [
        ("S000002929", 20.0),
        ("S000002927", 40.0),
        ("S000002930", 60.0),
        ("S000002928", 80.0),
    ]:
        assert abs(vg[sid]["eq_2023q2"] - target_eq) <= 5.0, f"{sid} 2023Q2 Eq={vg[sid]['eq_2023q2']} vs {target_eq}"
        assert abs(vg[sid]["eq_2026"] - target_eq) <= 5.0, f"{sid} 2026 Eq={vg[sid]['eq_2026']} vs {target_eq}"

    # Vanguard Capital Growth S000004397 must be pure equity, NOT multi-asset
    assert r1["individual_fixes_verified"]["S000004397_vanguard_capital_growth_is_alloc"] == 0
    assert vg["S000004397"]["eq_2023q2"] >= 90.0
    assert vg["S000004397"]["eq_2026"] >= 90.0
    assert r1["individual_fixes_verified"]["CIK_0001126087_brighthouse_complex_id"] == ["BRIGHTHOUSE"]


def test_04_full_rank_and_non_singleton_invariants() -> None:
    # 4a. Unit test: rank-deficient X MUST raise ValueError
    rng = np.random.default_rng(42)
    X_bad = np.column_stack([rng.normal(size=50), np.ones(50)])
    X_bad = np.column_stack([X_bad, X_bad[:, 0] * 2.0])  # exact collinear column
    y_bad = rng.normal(size=50)
    cl_bad = np.repeat(np.arange(10), 5)
    with pytest.raises(ValueError, match="Rank-deficient"):
        ols_cr1_wcb(y_bad, X_bad, cl_bad, do_wcb=False)

    # 4b. Audit ALL saved regressions across JSON receipts for rank == k
    def check_ranks(obj: object, path: str = "") -> None:
        if isinstance(obj, dict):
            if "rank" in obj and "k" in obj:
                assert obj["rank"] == obj["k"], f"Rank deficiency in {path}: rank={obj['rank']} < k={obj['k']}"
            for k, v in obj.items():
                check_ranks(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                check_ranks(v, f"{path}[{i}]")

    for fn in ("03_holdings_lookthrough.json", "04_econometrics_results.json", "05_monthly_flow_results.json"):
        check_ranks(json.loads((RES_DIR / fn).read_text(encoding="utf-8")), fn)


def test_05_fwl_absorbed_fe_matches_explicit_lsdv_wcb_to_1e12() -> None:
    """Verify FWL absorbed-FE CR1 + WCB matches brute-force explicit LSDV to atol=1e-12."""
    rng = np.random.default_rng(20261126)
    n_clusters = 12
    units_per_cluster = 3
    n_periods = 6
    rows = []
    for g in range(n_clusters):
        for u in range(units_per_cluster):
            uid = f"U_{g}_{u}"
            treated = int(u == 0)
            for t in range(n_periods):
                post = int(t >= 3)
                x1 = treated * post
                x2 = rng.normal()
                y = 0.5 * x1 + 0.3 * x2 + 0.7 * g - 0.4 * u + 0.2 * t + rng.normal(scale=0.5)
                rows.append({"cl": f"C_{g}", "unit": uid, "t": t, "cl_t": f"C_{g}_{t}", "x1": float(x1), "x2": float(x2), "y": float(y)})
    df = pd.DataFrame(rows)

    # Case A: Two-way FE (unit FE nested in cluster + time FE explicit)
    fwl_twfe = run_absorbed_twfe(
        df,
        y_col="y",
        x_cols=["x1", "x2"],
        absorb_fe_col="unit",
        cluster_col="cl",
        time_fe_col="t",
        test_col_idx=0,
        n_boot=199,
        seed=20261126,
    )
    # Explicit brute-force LSDV matrix: [x1, x2, time_dummies(drop_first=True), unit_dummies(all)]
    d_t = pd.get_dummies(df["t"].astype(str), drop_first=True, dtype=float).to_numpy()
    d_u = pd.get_dummies(df["unit"].astype(str), drop_first=False, dtype=float).to_numpy()
    X_lsdv_a = np.column_stack([df[["x1", "x2"]].to_numpy(), d_t, d_u])
    lsdv_twfe = ols_cr1_wcb(
        df["y"].to_numpy(),
        X_lsdv_a,
        df["cl"].to_numpy(),
        test_col_idx=0,
        n_fe_absorbed=0,
        n_boot=199,
        seed=20261126,
    )
    for key in ("beta", "se_cr1", "t_cr1", "p_cr1", "p_wcb"):
        assert np.isclose(fwl_twfe[key], lsdv_twfe[key], atol=1e-12, rtol=1e-12), (
            f"TWFE mismatch on {key}: FWL={fwl_twfe[key]} vs LSDV={lsdv_twfe[key]}"
        )

    # Case B: Cluster-by-Period FE (cl_t strictly nested in cl)
    fwl_ct = run_absorbed_twfe(
        df,
        y_col="y",
        x_cols=["x1", "x2"],
        absorb_fe_col="cl_t",
        cluster_col="cl",
        time_fe_col=None,
        test_col_idx=0,
        n_boot=199,
        seed=20261126,
    )
    d_ct = pd.get_dummies(df["cl_t"].astype(str), drop_first=False, dtype=float).to_numpy()
    X_lsdv_b = np.column_stack([df[["x1", "x2"]].to_numpy(), d_ct])
    lsdv_ct = ols_cr1_wcb(
        df["y"].to_numpy(),
        X_lsdv_b,
        df["cl"].to_numpy(),
        test_col_idx=0,
        n_fe_absorbed=0,
        n_boot=199,
        seed=20261126,
    )
    for key in ("beta", "se_cr1", "t_cr1", "p_cr1", "p_wcb"):
        assert np.isclose(fwl_ct[key], lsdv_ct[key], atol=1e-12, rtol=1e-12), (
            f"Cluster×Time FE mismatch on {key}: FWL={fwl_ct[key]} vs LSDV={lsdv_ct[key]}"
        )


def test_06_manuscript_receipt_sync_and_100pct_citation_check() -> None:
    md = (WORK_DIR / "manuscript_i4_boost.md").read_text(encoding="utf-8")
    r1 = json.loads((RES_DIR / "01_panel_audit.json").read_text(encoding="utf-8"))
    r4 = json.loads((RES_DIR / "04_econometrics_results.json").read_text(encoding="utf-8"))
    r7 = json.loads((RES_DIR / "07_verified_references_crossref.json").read_text(encoding="utf-8"))

    # Key headline numbers present verbatim in manuscript
    assert f"{r1['nport_dedup_audit']['n_final_quarterly_panel_2020Q1_2026Q3']:,}" in md
    assert f"{r1['flow_sign_fix_validation']['pearson_fixed_abs_vs_tna']:.3f}" in md
    assert f"{r4['main_did_full_20_26Q3']['A3_GVI_ALL']['post_25_26']['beta'] * 100:+.2f}" in md
    assert f"{r4['high_dim_fe']['FULL_20_26Q3_GVI_ALLOC_COMPLEX_X_QTR_IDENTIFYING']['beta'] * 100:+.2f}" in md

    # 100% live Crossref verification and 2-way citation sync
    assert r7["n_academic_dois_verified_live_crossref"] == 17
    assert r7["n_official_sec_releases"] == 6
    assert r7["all_bibliography_cited_in_body"] is True
    assert r7["all_body_citations_in_bibliography"] is True


def test_07_pdf_zero_leak_verification() -> None:
    pdf_p = WORK_DIR / "manuscript_i4_boost.pdf"
    assert pdf_p.exists() and pdf_p.stat().st_size > 500_000
    reader = PdfReader(str(pdf_p))
    assert len(reader.pages) >= 12
    full_txt = "\n".join((p.extract_text() or "") for p in reader.pages)

    bad_patterns = [
        r"\\[A-Za-z]+",
        r"\\\$",
        r"\$\$",
        r"\*\*",
        r"\|---",
        r"\{,\}",
        r"\\text\{",
        r"\\frac\{",
        r"\bp_WCB\b",
        r"\^[0-9A-Za-z{]",
        r"fig[1-5]_[a-z0-9_]+\.png",
        r"<!--",
        r"TOK\d+",
        r"&[a-z]+;",
        r"&#\d+;",
    ]
    for pat in bad_patterns:
        assert not re.search(pat, full_txt), f"Leaked token pattern {pat!r} found in compiled PDF text!"


def test_08_all_5_figures_exist_and_300dpi_resolution() -> None:
    expected = [
        "fig1_compliance_cliffs_and_bifurcation",
        "fig2_bifurcated_equilibrium_and_edgar_proof",
        "fig3_statutory_cutoff_and_robustness_forest",
        "fig4_lookthrough_holdings_inertia",
        "fig5_monthly_investor_flows_reversal",
    ]
    for stem in expected:
        png_p = FIG_DIR / f"{stem}.png"
        pdf_p = FIG_DIR / f"{stem}.pdf"
        assert png_p.exists() and png_p.stat().st_size > 100_000, f"Missing/small PNG: {png_p.name}"
        assert pdf_p.exists() and pdf_p.stat().st_size > 20_000, f"Missing/small PDF: {pdf_p.name}"
        with Image.open(png_p) as im:
            w, h = im.size
            dpi = im.info.get("dpi", (300, 300))
            assert w >= 3400 and h >= 1200, f"Resolution too low for {png_p.name}: {w}x{h}"
            assert dpi[0] >= 299.0 and dpi[1] >= 299.0, f"DPI metadata < 300 for {png_p.name}: {dpi}"


def test_09_drop_gvi_strict_exit_and_clean_series_names() -> None:
    """Prevent false-positive Income<->Value swaps, XML phone-number typos, and complex typo splits."""
    qdf = pd.read_parquet(
        WORK_DIR / "data" / "panel_quarterly.parquet",
        columns=["SERIES_ID", "COMPLEX_ID", "PREV_HAS_GVI", "HAS_GVI", "DROP_GVI", "PREV_HAS_GVI_DIV", "HAS_GVI_DIV", "DROP_GVI_DIV"],
    )
    bad_gvi = qdf[(qdf["DROP_GVI"] == 1) & ~((qdf["PREV_HAS_GVI"] == 1) & (qdf["HAS_GVI"] == 0))]
    assert len(bad_gvi) == 0, f"DROP_GVI false positives still exist: {len(bad_gvi)}"
    bad_gvid = qdf[(qdf["DROP_GVI_DIV"] == 1) & ~((qdf["PREV_HAS_GVI_DIV"] == 1) & (qdf["HAS_GVI_DIV"] == 0))]
    assert len(bad_gvid) == 0, f"DROP_GVI_DIV false positives still exist: {len(bad_gvid)}"

    for stale_cplx in ("AMPLFY", "TOROSO", "ADVANCED", "CIK_0001126087"):
        assert not (qdf["COMPLEX_ID"] == stale_cplx).any(), f"Ununified stale COMPLEX_ID found: {stale_cplx}"

    drop_df = pd.read_csv(TBL_DIR / "table_all_droppers_2025_2026_audit.csv")
    assert len(drop_df) == 162  # 161 unique funds + 1 sequential dropper (S000077074) appearing in ESG & Pure GVI
    assert drop_df["SERIES_ID"].nunique() == 161
    # Zero non-alphabetic XML phone-number series names in droppers
    assert drop_df["NEW_NAME"].astype(str).str.contains(r"[A-Za-z]{3,}", regex=True).all()
    assert not drop_df["NEW_NAME"].astype(str).str.contains("303-626-0600", regex=False).any()


def test_10_lookthrough_top100_accuracy_and_cusip_consensus_stability() -> None:
    """Verify 100/100 top-100 look-through accuracy, non-overlapping monthly drift, and <80% inertia."""
    lt100 = pd.read_csv(TBL_DIR / "table_lookthrough_100pos_audit.csv")
    assert len(lt100) == 100
    tiers = lt100["MATCH_TIER"].astype(str)
    assert not (tiers == "TIER3_FALLBACK_EQ").any(), "Fallback row found in top-100 look-through audit"
    assert not (tiers == "TIER3_DICT_MIXED50").any(), "Crude 50/50 row found in top-100 look-through audit"
    assert not tiers.str.contains("_TIE", na=False).any(), "Tie-broken row found in top-100 look-through audit"

    def _find_pos(kw: str) -> pd.Series:
        m = lt100["ISSUER_NAME"].astype(str).str.upper().str.contains(kw, na=False) | lt100["ISSUER_TITLE"].astype(str).str.upper().str.contains(kw, na=False)
        assert m.any(), f"Expected flagship holding {kw!r} in top-100 audit"
        return lt100.loc[m].iloc[0]

    ifa = _find_pos("INCOME FUND OF AMERICA")
    assert 0.65 <= float(ifa["W_EQ"]) <= 0.78
    cib = _find_pos("CAPITAL INCOME BUILDER")
    assert 0.70 <= float(cib["W_EQ"]) <= 0.85
    msi = _find_pos("MULTI-SECTOR INCOME")
    assert float(msi["W_BD"]) >= 0.99
    nmi = _find_pos("NEW MARKETS INCOME")
    assert float(nmi["W_BD"]) >= 0.95
    pim = _find_pos("PIMCO")
    assert float(pim["W_BD"]) >= 0.99

    # Verify previously broken custodian-truncated / misclassified paired funds now sit on 45-deg line
    pairs = pd.read_parquet(WORK_DIR / "data" / "holdings_lt" / "lookthrough_panel_2023_2026.parquet")
    s_bd = pairs.loc[pairs["SERIES_ID"] == "S000059058"].iloc[0]
    assert float(s_bd["TRUE_EQ_23"]) < 5.0 and float(s_bd["TRUE_EQ_26"]) < 5.0
    s_tops = pairs.loc[pairs["SERIES_ID"] == "S000031504"].iloc[0]
    assert abs(float(s_tops["TRUE_EQ_26"]) - float(s_tops["TRUE_EQ_23"])) < 3.0

    # Verify non-overlapping monthly passive drift benchmark (no May-June 2026 double counting!)
    r3 = json.loads((RES_DIR / "03_holdings_lookthrough.json").read_text(encoding="utf-8"))
    bm = r3["passive_drift_benchmarks"]
    assert 0.50 <= bm["pure_eq_cum_ret_23Q3_26Q2"] <= 0.62
    assert abs(bm["pure_eq_cum_ret_23Q3_26Q3"] - bm["pure_eq_cum_ret_23Q3_26Q2"]) < 0.05

    # Verify <80% active shift toward 80% is strongly negative for droppers vs keepers
    act_lt = r3["inertia_cross_section"]["HOLD_LT_CONSTR_GVI"]["metrics"]["ACTIVE_TOWARD_80"]
    assert act_lt["beta"] < -5.0 and act_lt["p_wcb"] <= 0.01


def test_11_symmetric_edgar_audit_and_window_validated_dates() -> None:
    """Confirm 100% symmetric EDGAR audit (no hardcoded Keeper zero) and window-validated dates."""
    r2 = json.loads((RES_DIR / "02_edgar_audit_summary.json").read_text(encoding="utf-8"))
    keep = r2["arm_summary"]["CONTROL_MA_GVI_KEEPER"]
    ma = r2["arm_summary"]["MULTI_ASSET_GVI_ALL"]
    assert keep["name_change_sticker_pct"] > 0.0, "Keepers must NOT be hardcoded to 0% name-change stickers"
    assert keep["trust_cites_35d1_pct"] > ma["trust_cites_35d1_pct"]
    assert r2["fisher_tests_ma_droppers_vs_keepers"]["p_2sided_trust_cites_35d1"] < 0.05

    ed_rows = json.loads((WORK_DIR / "data" / "edgar_prospectus_audit.json").read_text(encoding="utf-8"))
    for row in ed_rows:
        eff = str(row.get("EFFECTIVE_DATE", "") or "")
        if eff:
            assert "2024-06-01" <= eff <= "2026-10-31", f"Out-of-window effective date {eff} on {row['SERIES_ID']}"


def test_12_full_ma_mechanism_table_and_local_1b_placebo_null() -> None:
    """Confirm full multi-asset mechanism table exists and local $1B-$10B Legacy-2001 placebo is null."""
    mech_df = pd.read_csv(TBL_DIR / "table2b_mechanism_bifurcation.csv")
    assert len(mech_df) >= 12
    assert (mech_df["sample"] == "FULL_MA_GVI_SAMPLE").any()
    assert (mech_df["sample"] == "MA_GVI_DROPPERS_49").any()

    r4 = json.loads((RES_DIR / "04_econometrics_results.json").read_text(encoding="utf-8"))
    assert r4["mechanism_opaque_vs_numeric"]["bivariate_means_and_fisher"]["IS_PASSIVE_OR_IDX_FOF"]["fisher_p_2sided"] < 0.001
    b4_loc = r4["statutory_cutoff_tests"]["B4_LOCAL_1B_10B_VS_LT1B"]
    assert b4_loc["did_post_25_26"]["p_wcb"] > 0.10
    assert b4_loc["exact_cluster_ri_B2000"]["ri_p_2sided_t"] > 0.10
    assert b4_loc["exact_cluster_ri_B2000"]["ri_p_2sided_beta"] > 0.10


def test_13_monthly_flow_rank_guard_and_flat_pretrends() -> None:
    """Confirm rank guard on 3-cluster MA_GVI_NUMERIC Wald test and flat pre-trends."""
    r5 = json.loads((RES_DIR / "05_monthly_flow_results.json").read_text(encoding="utf-8"))
    assert r5["monthly_arms"]["MA_GVI_NUMERIC"]["event_study_summary"]["wald_pre_rank_valid"] is False
    assert r5["monthly_arms"]["MA_GVI_POOLED"]["event_study_summary"]["pre_linear_slope_m12_m2"]["p_wcb"] > 0.20
    assert r5["monthly_arms"]["ESG_DROPPERS"]["event_study_summary"]["pre_linear_slope_m12_m2"]["p_wcb"] > 0.20
    es_df = pd.read_csv(TBL_DIR / "table_monthly_flow_event_study.csv")
    assert "beta_centered_pct" in es_df.columns


def test_14_formal_model_algebra_and_crossref_integrity() -> None:
    """Confirm Section 2 model sign fix, clean cross-references, and fresh headline numbers."""
    md = (WORK_DIR / "manuscript_i4_boost.md").read_text(encoding="utf-8")
    assert r"\delta_i = \theta (f_i - f_{\text{beta}})" in md
    assert r"\kappa_i f_i (\lambda_Q + \lambda_O) > v_i" not in md
    assert "Table 1 documents our exact data-cleaning waterfall" not in md
    assert "161 unique" in md
    assert "-6.92 pp" in md
    assert "66.0% vs. 42.0%" in md


def test_15_v2_sec_citations_ex_vanguard_and_sec_faq_robustness() -> None:
    """Enforce all 4 Major Revision v2 referee fixes:
    (a) zero IC-35962 and positive presence of IC-35963 + 33-11238 + 33-11368 + SEC FAQs + 2026-19,
    (b) Ex-Vanguard numeric AUM share (<6%) computed and synced in manuscript,
    (c) SEC-FAQ strict non-exempt Growth/Value DiD & look-through holdings inertia present,
    (d) accurate on-cycle compliance timing (no 2026Q4 small-group completion overclaim) and zero PDF leaks.
    """
    md = (WORK_DIR / "manuscript_i4_boost.md").read_text(encoding="utf-8")
    readme = (WORK_DIR / "README.md").read_text(encoding="utf-8")
    r3 = json.loads((RES_DIR / "03_holdings_lookthrough.json").read_text(encoding="utf-8"))
    r4 = json.loads((RES_DIR / "04_econometrics_results.json").read_text(encoding="utf-8"))
    r7 = json.loads((RES_DIR / "07_verified_references_crossref.json").read_text(encoding="utf-8"))
    reader = PdfReader(str(WORK_DIR / "manuscript_i4_boost.pdf"))
    pdf_txt = "\n".join((p.extract_text() or "") for p in reader.pages)

    # (a) Statutory citation fix: zero IC-35962 anywhere; positive presence of all official v2 SEC citations
    for label, blob in [
        ("manuscript_i4_boost.md", md),
        ("manuscript_i4_boost.pdf", pdf_txt),
        ("README.md", readme),
        ("07_verified_references_crossref.json", json.dumps(r7)),
        ("07a_generate_manuscript_md.py", (WORK_DIR / "scripts" / "07a_generate_manuscript_md.py").read_text(encoding="utf-8")),
    ]:
        assert "35962" not in blob, f"Deprecated IC-35962 found in {label}!"

    for req_tok in ("IC-35963", "33-11238", "33-11368", "Names Rule FAQs", "2026-19"):
        assert req_tok in md, f"Missing required SEC citation {req_tok!r} in manuscript_i4_boost.md"
        assert req_tok in pdf_txt, f"Missing required SEC citation {req_tok!r} in manuscript_i4_boost.pdf"

    sec_refs = [r for r in r7["references"] if r.get("official_sec_release")]
    assert len(sec_refs) == 6
    assert all(r.get("http_status") == 200 for r in sec_refs), "All 6 official SEC URLs must verify HTTP 200!"

    # (b) Ex-Vanguard concentration sensitivity (<6% numeric AUM share ex-Vanguard) + Ex-Vanguard DiD
    xv = r4["ex_vanguard_sensitivity"]
    assert xv["vanguard_share_of_numeric_aum_pct"] > 95.0
    xv_num_pct = xv["ex_vanguard_ma_gvi"]["NUMERIC_RATIO"]["pct_aum"]
    xv_opq_pct = xv["ex_vanguard_ma_gvi"]["OPAQUE_SYNONYM"]["pct_aum"]
    assert xv_num_pct < 6.0, f"Expected ex-Vanguard numeric AUM share < 6%, got {xv_num_pct:.2f}%"
    assert xv_opq_pct > 90.0
    assert f"{xv_num_pct:.1f}%" in md and f"{xv_num_pct:.1f}%" in pdf_txt
    assert f"{xv['vanguard_share_of_numeric_aum_pct']:.1f}%" in md
    assert r4["main_did_full_20_26Q3"]["A3_GVI_EX_VANGUARD"]["post_25_26"]["p_wcb"] <= 0.01
    assert r4["main_did_full_20_26Q3"]["A3_GVI_OPAQUE_EX_VANGUARD"]["post_25_26"]["p_wcb"] <= 0.01

    # (c) SEC-FAQ strict non-exempt Growth/Value DiD + within-complex FE + look-through inertia
    faq = r4["sec_faq_robustness"]
    assert faq["ma_gvi_dropper_faq_breakdown"]["strict_non_faq_gv_no_income"]["n_funds"] == 35
    assert r4["main_did_full_20_26Q3"]["FAQ1_GV_NO_GI"]["post_25_26"]["p_wcb"] <= 0.01
    assert r4["main_did_full_20_26Q3"]["FAQ2_GV_NO_INC"]["post_25_26"]["p_wcb"] <= 0.01
    assert r4["main_did_full_20_26Q3"]["FAQ3_GV_NO_INC_OPAQUE"]["post_25_26"]["p_wcb"] <= 0.01
    assert r4["main_did_full_20_26Q3"]["FAQ4_GV_NO_INC_HOLD_LT80"]["post_25_26"]["p_wcb"] <= 0.01
    assert faq["high_dim_fe_gv_no_inc_idonly"]["p_wcb"] <= 0.01
    faq_inertia = r3["inertia_cross_section"]["HOLD_LT_CONSTR_GV_NO_INC"]["metrics"]["ACTIVE_TOWARD_80"]
    assert faq_inertia["beta"] < -4.0 and faq_inertia["p_wcb"] <= 0.055

    # (d) Accurate on-cycle timing (no 2026Q4 completion overclaim) and no literal noncompliance overclaim
    assert "on-cycle" in md.lower() and "on-cycle" in pdf_txt.lower()
    assert "will appear in `2026Q4` N-PORT" not in md
    assert "Non-Compliant" not in pdf_txt
