"""Comprehensive verification test suite for H6f Scientometrics v4 flagship revision.

Tests:
  1. Strict v1-date alignment, zero v1 covariate leakage (v1_n_authors & v1_primary_subject),
     exact 368/2,285 authorship-leakage audit parity, and 2023-11 monthly anti-truncation guard.
  2. Stratified N=200 OpenAlex citing-work ID deduplication audit integrity & metrics.
  3. Full-rank design matrices, brute-force CR1, exact non-nested LSDV WCB equivalence, & PPML convergence.
  4. Equal-window validation across All-v1, VoR-only, and Non-VoR-only subsamples + incremental deviance.
  5. Clean denominator separation (842/964 public revisions; 644/964=66.8% vs 644/793=81.2%;
     192/216 final <Solid posted revisions; 325.4d calendar lag; 166/514 cross-announcement VoRs).
  6. Globally unique ADH Synthetic Control simplex weights & starting-point invariance (SI).
  7. Zero-NaN invariant across all v4 CSV tables + all 7 PNG/PDF figures.
  8. Authorship block, Abstract hygiene (no country/ID-velocity/SC/zero-return), and full
     manuscript/SI numerical parity against JSON receipts.
  9. 31/31 Crossref-verified DOI parity + co-occurring author-year citations across Main + SI.
 10. Zero-leak verification on BOTH manuscript_h6f_boost.pdf and supplementary_h6f_scientometrics.pdf.
 11. Live disk-byte SHA256SUMS.json 100% integrity & strict LF line endings.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pypdf import PdfReader

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"
FIG_DIR = BASE_DIR / "figures"
MD_MAIN = BASE_DIR / "manuscript_h6f_boost.md"
PDF_MAIN = BASE_DIR / "manuscript_h6f_boost.pdf"
MD_SI = BASE_DIR / "supplementary_h6f_scientometrics.md"
PDF_SI = BASE_DIR / "supplementary_h6f_scientometrics.pdf"


def _load_module(script_name: str):
    path = BASE_DIR / "scripts" / script_name
    spec = importlib.util.spec_from_file_location(script_name.replace(".py", ""), path)
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_strict_v1_covariate_freeze_and_anti_truncation_guards() -> None:
    """Verify zero missing v1 authors/subjects, exact 368/2,285 leakage benchmark, and 2023-11 guard."""
    df = pd.read_csv(DATA_DIR / "h6f_boost_v1_panel.csv.gz", dtype={"eid": str})
    v1_dt = pd.to_datetime(df["v1_date"], errors="coerce")
    fin_dt = pd.to_datetime(df["fin_date"], errors="coerce")

    assert len(df) == 4551
    assert int(v1_dt.isna().sum()) == 0
    assert int(df["v1_n_authors"].isna().sum()) == 0, "v1_n_authors must have zero missing values"
    assert int(df["v1_primary_subject"].isna().sum()) == 0, "v1_primary_subject must have zero missing values"
    assert (df["primary_subject"] == df["v1_primary_subject"]).all(), "primary_subject must be frozen at v1"
    assert np.allclose(df["n_authors"], df["v1_n_authors"]), "n_authors must equal frozen v1_n_authors"

    vors = df[df["is_vor"] == 1]
    assert int((fin_dt.loc[vors.index] < v1_dt.loc[vors.index]).sum()) == 0
    assert float(df["v1_str_min"].notna().mean()) >= 0.997

    # Anti-truncation guard on 2023-11 rolling API window
    mat = df[(v1_dt >= "2023-01-01") & (v1_dt <= "2024-12-31") & df["v1_str_min"].notna()]
    assert len(mat) == 2653
    assert int((mat["has_metrics"] == 1).sum()) == 2653
    trunc = mat[mat["v1_date"] < "2023-11-01"]
    clean = mat[mat["v1_date"] >= "2023-11-01"]
    assert len(trunc) == 801 and len(clean) == 1852
    assert trunc["pv_first_3m"].isna().all()
    assert trunc["delta_log_pv_rate"].isna().all()
    assert clean["pv_first_3m"].notna().all()

    # Exact reviewer benchmark parity: 368/2,285 author leakage, -14.03% -> -13.74% [-18.97%, -8.18%]
    p9 = json.loads((RES_DIR / "09_v4_scientometrics_results.json").read_bytes().decode("utf-8"))
    rev = p9["covariate_audit_and_crossed_clock"]["reviewer_2285_exact_parity"]
    assert rev["n"] == 2285
    assert rev["n_max_authors_gt_v1"] == 368
    assert np.isclose(rev["leaked_max_authors"]["pct"], -14.03, atol=0.02)
    assert np.isclose(rev["frozen_v1_authors"]["pct"], -13.74, atol=0.02)
    assert np.isclose(rev["frozen_v1_authors"]["pct_ci95_lo"], -18.97, atol=0.03)
    assert np.isclose(rev["frozen_v1_authors"]["pct_ci95_hi"], -8.18, atol=0.03)


def test_openalex_citing_work_id_dedup_audit_integrity() -> None:
    """Verify N=200 stratified OpenAlex citing-work ID deduplication audit receipts and cache."""
    p3b = json.loads((RES_DIR / "03b_openalex_dedup_audit.json").read_bytes().decode("utf-8"))
    cache_path = DATA_DIR / "openalex_citing_dedup_audit.json"
    assert cache_path.exists()
    assert hashlib.sha256(cache_path.read_bytes()).hexdigest() == p3b["cache_sha256"]
    raw = json.loads(cache_path.read_bytes().decode("utf-8"))
    assert len(raw) == p3b["n_audited_articles"] == 200
    assert p3b["elife_only_post_v1"]["pearson_r"] > 0.999
    assert p3b["all_manifestations_post_v1"]["pearson_r"] > 0.995
    assert p3b["by_stratum"]["VoR_v1Low"]["n"] == 60
    assert p3b["by_stratum"]["NonVoR_v1Low"]["n"] == 40
    assert p3b["by_stratum"]["NonVoR_v1SolidPlus"]["pct_split_oa_works"] >= 90.0
    assert p3b["by_stratum"]["VoR_v1Low"]["pct_split_oa_works"] <= 5.0


def test_full_rank_bruteforce_cr1_and_exact_nonnested_lsdv_wcb_equivalence() -> None:
    """Verify exact CR1 sandwich and non-nested LSDV wild cluster bootstrap equivalence."""
    s4 = _load_module("04_pillar1_2_revision_and_attention.py")
    rng = np.random.default_rng(12345)
    rows = []
    for g in range(12):
        u_g = rng.normal(0.0, 0.5)
        for i in range(25):
            x1, x2 = rng.normal(), rng.normal()
            y = -0.8 * x2 + (i % 6) * 0.7 + u_g + rng.normal(0.0, 0.3)
            rows.append({"y": y, "x1": x1, "x2": x2, "fe": f"fe_{i % 6}", "cl": f"cl_{g}"})
    syn = pd.DataFrame(rows)
    wcb_B = 499
    res = s4.fe_ols_cr1(syn, "y", ["x1", "x2"], "fe", "cl", wcb_target="x1", wcb_B=wcb_B, seed=7)
    assert res["rank"] == res["K"] == 2

    fe_d = pd.get_dummies(syn["fe"], drop_first=False, dtype=float)
    X_full = pd.concat([syn[["x1", "x2"]].astype(float), fe_d], axis=1).to_numpy()
    y_vec = syn["y"].to_numpy(dtype=float)
    b_lsdv = np.linalg.lstsq(X_full, y_vec, rcond=None)[0]
    e_lsdv = y_vec - X_full @ b_lsdv
    N, P = X_full.shape
    uniq_cl, inv_cl = np.unique(syn["cl"].to_numpy(), return_inverse=True)
    G = len(uniq_cl)
    XtX_inv = np.linalg.inv(X_full.T @ X_full)
    meat = sum(np.outer(X_full[inv_cl == g_i].T @ e_lsdv[inv_cl == g_i], X_full[inv_cl == g_i].T @ e_lsdv[inv_cl == g_i]) for g_i in range(G))
    cr1_scale = (G / (G - 1.0)) * ((N - 1.0) / (N - P))
    se_bf = np.sqrt(np.diag(cr1_scale * (XtX_inv @ meat @ XtX_inv)))
    assert np.isclose(res["params"]["x1"]["beta"], b_lsdv[0], atol=1e-10)
    assert np.isclose(res["params"]["x1"]["se"], se_bf[0], atol=1e-10)

    X_r = X_full[:, 1:]
    yhat_r = X_r @ np.linalg.lstsq(X_r, y_vec, rcond=None)[0]
    e_r = y_vec - yhat_r
    v0 = X_full @ XtX_inv[0, :]
    t_obs = abs(b_lsdv[0] / se_bf[0])
    signs = np.random.default_rng(7).choice([-1.0, 1.0], size=(wcb_B, G))
    exceed = 0
    for b in range(wcb_B):
        ys = yhat_r + signs[b, inv_cl] * e_r
        bs = XtX_inv @ (X_full.T @ ys)
        rs = ys - X_full @ bs
        vs = cr1_scale * sum((np.dot(v0[inv_cl == g_i], rs[inv_cl == g_i])) ** 2 for g_i in range(G))
        if abs(bs[0] / np.sqrt(vs)) >= t_obs:
            exceed += 1
    assert np.isclose(res["params"]["x1"]["p_wcb"], (exceed + 1) / (wcb_B + 1), atol=1e-12)


def test_equal_window_nonvor_and_funnel_denominators() -> None:
    """Verify All-v1 vs VoR vs Non-VoR validation and exact funnel / public-revision counts."""
    p9 = json.loads((RES_DIR / "09_v4_scientometrics_results.json").read_bytes().decode("utf-8"))
    ev = p9["equal_window_validation"]["by_sample"]
    assert ev["all_v1"]["oa_next_full_year"]["v1_low"]["pct"] < -15.0
    assert ev["all_v1"]["oa_next_full_year"]["v1_low"]["p"] < 1e-4
    assert ev["vor_only"]["oa_next_full_year"]["v1_low"]["pct"] < -12.0
    assert ev["non_vor_only_subj_q"]["oa_post_v1_cites"]["v1_low"]["pct"] < -15.0
    assert ev["non_vor_only_subj_q"]["oa_post_v1_cites"]["v1_low"]["p"] < 0.05

    fn = p9["revision_and_upgrade"]["funnel_by_v1_tier"]["v1_Incomp_Inad"]
    assert fn["n_total"] == 964
    assert fn["n_posted_revision"] == 842
    assert fn["n_vor"] == 793
    assert fn["n_vor_upgraded_any"] == 644
    assert fn["n_vor_upgraded_to_solid"] == 621
    assert np.isclose(fn["pct_all_upgraded_any"], 66.80, atol=0.05)
    assert np.isclose(fn["pct_vor_upgraded_any"], 81.21, atol=0.05)
    assert np.isclose(fn["mean_rev_lag_up_days"], 325.4, atol=0.1)

    si = p9["supplementary_indexing_cohort"]
    assert si["apr2023_lower_rated_vors"] == 216
    assert si["apr2023_lower_rated_vors_with_posted_revision"] == 192
    assert si["pre_450_vors"] == 514
    assert si["pre_450_vors_after_announcement"] == 166
    fh = si["fixed_horizon_v3_parity_fin_subj"]["450"]
    assert np.isclose(100.0 * fh["lower_rated_vor"]["beta"], -2.76, atol=0.03)
    assert np.isclose(100.0 * fh["observed_revision"]["beta"], -3.47, atol=0.03)


def test_synthetic_control_uniqueness_for_si() -> None:
    """Verify strictly convex ADH Synthetic Control simplex weights & starting-point uniqueness (SI)."""
    s5 = _load_module("05_pillar3_4_clarivate_sc_and_geo.py")
    jp = pd.read_csv(DATA_DIR / "h6f_boost_journal_panel.csv")
    jp_c = jp[(jp["period"].isin(s5.COMPLETE_PERIODS)) & (jp["in_strict_90_panel"] == 1)]
    piv = jp_c.pivot(index="journal", columns="period", values="log_n_all")
    prc = ["2023H2", "2024H1", "2024H2"]
    pdm = piv.sub(piv[prc].mean(axis=1), axis=0)
    donors = [u for u in pdm.index if u != "eLife"]
    yp = pdm.loc["eLife", prc].to_numpy(float)
    Y0 = pdm.loc[donors, prc].to_numpy(float)
    w_ref = s5.solve_simplex_sc_weights(yp, Y0)
    assert np.isclose(np.sum(w_ref), 1.0, atol=1e-7) and np.min(w_ref) >= -1e-9
    rng = np.random.default_rng(2026)
    for _ in range(5):
        w_t = s5.solve_simplex_sc_weights(yp, Y0, w0=rng.dirichlet(np.ones(len(donors))))
        assert float(np.max(np.abs(w_t - w_ref))) < 5e-4


def test_v4_tables_zero_nan_and_all_seven_figures() -> None:
    """Verify zero NaNs in all v4 tables and existence/size of all 4 main + 3 SI figures."""
    for fname in [
        "table_v4_1_audit_and_crossed_clock.csv",
        "table_v4_2_all_vor_nonvor_equal_window.csv",
        "table_v4_3_onsite_readership_predictive.csv",
        "table_v4_4_revision_upgrade_and_trajectories.csv",
        "table_s1_indexing_cohort_exploratory.csv",
    ]:
        p = TBL_DIR / fname
        assert p.exists(), f"Missing {fname}"
        df = pd.read_csv(p, keep_default_na=True)
        assert len(df) >= 4
        assert int(df.isna().sum().sum()) == 0, f"NaNs found in {fname}"

    for stem in [
        "fig1_v4_measurement_and_dedup_audit",
        "fig2_v4_equal_window_predictive_value",
        "fig3_v4_onsite_readership_and_funnel",
        "fig4_v4_upgrade_precision_and_trajectories",
        "figs1_si_indexing_cohort_cif",
        "figs2_si_id_velocity_and_sc",
        "figs3_si_geographic_exploratory",
    ]:
        assert (FIG_DIR / f"{stem}.png").stat().st_size > 40_000
        assert (FIG_DIR / f"{stem}.pdf").stat().st_size > 15_000


def test_authorship_abstract_hygiene_and_manuscript_json_parity() -> None:
    """Enforce exact authorship block, zero venue/track leaks, Abstract hygiene, and JSON parity."""
    md_main = MD_MAIN.read_text(encoding="utf-8")
    md_si = MD_SI.read_text(encoding="utf-8")

    for doc_name, txt in (("Main", md_main), ("SI", md_si)):
        assert "Zijian Zeng" in txt, f"{doc_name} missing author"
        assert "Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA" in txt
        assert "zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my" in txt
        for forbidden in ("Target Venues", "Target Format", "Track A", "Track B"):
            assert forbidden not in txt, f"Forbidden metadata token {forbidden!r} found in {doc_name}"

    # Abstract hygiene: NO country-level shares, ID-velocity (-56.3%), or synthetic-control claims!
    m_abs = re.search(r"## Abstract\s+(.*?)\n\*\*Keywords:", md_main, flags=re.DOTALL)
    assert m_abs is not None, "Could not locate Abstract in main manuscript"
    abstract_txt = m_abs.group(1)
    for banned in ("-56.3%", "56.3%", "synthetic control", "China", "United States", "JIF-codified", "DORA", "zero return"):
        assert banned.lower() not in abstract_txt.lower(), f"Abstract must not contain {banned!r}!"

    # Main manuscript must NEVER call upgrade-to-Solid+ "zero return" as a claim
    assert "zero citation return" not in md_main.lower()
    assert "June 2024" in md_main and "Web of Science and Scopus" in md_main
    assert "supplementary_h6f_scientometrics.pdf" in md_main

    # Headline numerical parity check against JSON
    p9 = json.loads((RES_DIR / "09_v4_scientometrics_results.json").read_bytes().decode("utf-8"))
    p3b = json.loads((RES_DIR / "03b_openalex_dedup_audit.json").read_bytes().decode("utf-8"))
    rev = p9["covariate_audit_and_crossed_clock"]["reviewer_2285_exact_parity"]
    ev = p9["equal_window_validation"]["by_sample"]
    up = p9["revision_and_upgrade"]["upgrade_models"]

    for tok in [
        "368/2,285",
        f"{rev['leaked_max_authors']['pct']:+.2f}%",
        f"{rev['frozen_v1_authors']['pct']:+.2f}%",
        f"{p3b['elife_only_post_v1']['pearson_r']:.5f}",
        f"{p3b['all_manifestations_post_v1']['pearson_r']:.5f}",
        f"{ev['all_v1']['oa_next_full_year']['v1_low']['pct']:+.2f}%",
        f"{ev['vor_only']['oa_next_full_year']['v1_low']['pct']:+.2f}%",
        f"{ev['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['pct']:+.2f}%",
        "842/964",
        "66.8%",
        "81.2%",
        "192/216",
        "325.4",
        f"{up['bench_v3_parity_oa_post_v1']['pct']:+.1f}%",
        f"{up['strict_v1_oa_post_v1']['pct']:+.1f}%",
        "166/514",
        "-2.76 pp",
        "-3.47 pp",
    ]:
        assert tok in md_main, f"Required v4 token {tok!r} missing from main manuscript"


def test_bibliography_31_crossref_dois_and_body_citations() -> None:
    """Verify all 31 Crossref-verified DOIs are HTTP 200 and cited across Main + SI."""
    refs = json.loads((DATA_DIR / "verified_references_crossref.json").read_bytes().decode("utf-8"))
    assert len(refs) == 31
    md_main = MD_MAIN.read_text(encoding="utf-8")
    md_si = MD_SI.read_text(encoding="utf-8")
    body_main, _, ref_main = md_main.partition("## References")
    body_si, _, ref_si = md_si.partition("## Supplementary References")
    combined_body = body_main + "\n" + body_si
    combined_refs = ref_main + "\n" + ref_si

    for key, rec in refs.items():
        assert rec["http_status"] == 200, f"Unverified DOI: {key}"
        assert rec["doi"].lower() in combined_refs.lower(), f"DOI {rec['doi']} ({key}) missing from References"
        fam = "Santos Silva" if rec["first_author_family"] == "Silva" else rec["first_author_family"]
        yr = str(rec["year"])
        matches = list(re.finditer(re.escape(fam), combined_body))
        near = any(yr in combined_body[max(0, m.start() - 15) : min(len(combined_body), m.end() + 75)] for m in matches)
        assert near, f"Co-occurring citation {fam} ({yr}) [{key}] not found in Main+SI body"

    # Mandatory new references explicitly cited in Main Manuscript
    assert "10.1007/s11192-025-05422-y" in ref_main and "Mutz" in body_main
    assert "10.7554/eLife.102324" in ref_main and "Ragusa" in body_main
    assert "8f427668" in ref_main and "e9d530fc" in ref_main and "ae620829" in ref_main


def test_both_compiled_pdfs_zero_leaks() -> None:
    """Verify BOTH manuscript_h6f_boost.pdf and supplementary_h6f_scientometrics.pdf have 0 leaked tokens."""
    bad_patterns = [
        r"\\[A-Za-z]+",
        r"\\\|",
        r"\$\$",
        r"\*\*",
        r"\|---",
        r"\{,\}",
        r"\bp_WCB\b",
        r"\^[0-9A-Za-z{]",
        r"fig[s0-9]_[a-z0-9_]+\.png",
        r"<!--",
        r"TOK\d+",
    ]
    for pdf_path, min_pages, min_bytes in [
        (PDF_MAIN, 10, 800_000),
        (PDF_SI, 4, 400_000),
    ]:
        assert pdf_path.exists() and pdf_path.stat().st_size > min_bytes
        reader = PdfReader(str(pdf_path))
        assert len(reader.pages) >= min_pages
        full_txt = "\n".join((p.extract_text() or "") for p in reader.pages)
        leaks = [pat for pat in bad_patterns if re.search(pat, full_txt)]
        assert not leaks, f"Leaked tokens found in {pdf_path.name}: {leaks}"


def test_live_disk_sha256sums_integrity_and_lf_endings() -> None:
    """Verify SHA256SUMS.json matches live disk bytes 100% and generated text files use LF endings."""
    sha_path = BASE_DIR / "SHA256SUMS.json"
    manifest = json.loads(sha_path.read_bytes().decode("utf-8"))
    assert "manuscript_h6f_boost.pdf" in manifest
    assert "supplementary_h6f_scientometrics.pdf" in manifest
    assert "REFEREE_RESPONSE_v4.md" in manifest

    mismatches = []
    for rel, expected_hash in manifest.items():
        fpath = BASE_DIR / rel
        if not fpath.exists():
            mismatches.append((rel, "MISSING"))
            continue
        actual = hashlib.sha256(fpath.read_bytes()).hexdigest()
        if actual != expected_hash:
            mismatches.append((rel, f"{expected_hash[:12]} != {actual[:12]}"))
    assert not mismatches, f"SHA-256 disk mismatches: {mismatches}"

    for rel in [
        "manuscript_h6f_boost.md",
        "supplementary_h6f_scientometrics.md",
        "REFEREE_RESPONSE_v4.md",
        "VERIFICATION_MANIFEST.md",
        "SHA256SUMS.json",
        "README.md",
        "STATUS.md",
        "results/03_panel_audit.json",
        "results/03b_openalex_dedup_audit.json",
        "results/09_v4_scientometrics_results.json",
    ]:
        assert b"\r\n" not in (BASE_DIR / rel).read_bytes(), f"CRLF line endings found in {rel}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
