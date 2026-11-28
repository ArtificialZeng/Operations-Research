"""Comprehensive verification test suite for F7 v4 (Journal of Consumer Policy / M&SOM Data Set):
Who Bears the Burden of Product Recall Remedies? Notice-Level Duties, Channel Classification,
and Institutional Governance in U.S. Third-Party E-Commerce Recalls, 2000-2026.

Covers:
  1. Legacy + v4 forensic parser unit tests:
     - Late-2026 Retailers-nested Chinese entities, domain- & online-phrase-stripped B&M matching,
       multi-comma/UK/Armenia Non-China FD, platform corporate-office co-listing guards vs. Amazon 1P,
       100% verified U.S. entity purity in 3_Mkt_True_US, negation-aware direct_return,
       noun-inclusive hazardous disposal, hazard-gated lithium classification, double-count-free injuries.
     - NEW v4 verbatim 3-way Amazon channel classification (Anker 10311, OCOOPA 10895 multi-channel;
       Jugader 9924, UVIPC 10148, TADAKAZU 10317 strict exclusive; 9234, 10238, 10245, 10276, 10494 ambiguous).
     - NEW v4 5-dimensional remedy-duty edge cases: Jugader (9924) optional photo-or-order-number,
       UVIPC (10148) non-photo destruction proof, TADAKAZU (10317) standalone FBA model suffix vs.
       0/601 explicit "Fulfilled by Amazon", Anker (10311) & OCOOPA (10895) full-notice HHW warnings.
  2. Full-rank design matrix assertions across every saved regression receipt (04, 05, 09).
  3. Exact numerical equivalence of fit_cr1_ols against statsmodels CR1 and Restricted Rademacher WCB-r.
  4. Formal theory model closed-form & proposition verification.
  5. Exact programmatic numerical parity across results/09_v4_channel_remedy_audit.json,
     results/04_pillar1_econometrics.json, results/05_pillars_2_3_4.json, manuscript_f7_boost.md,
     and supplementary_f7_jcp.md (including Table S3 canonical_t5 sync & Table S2 R7/R7b sync).
  6. Authorship hygiene (Zijian Zeng, UCSI University, exact emails; zero Target Venues/Track A/Track B)
     and strict zero-overclaim checks across main + supplement Markdown and PDFs.
  7. 22/22 live HTTP-200 Crossref DOIs (including Raithel et al. 10.1007/s11747-023-00967-x and
     Fang et al. 10.1287/mksc.2025.0618) + 10 official records = 32/32 cited in body text.
  8. Zero-NaN publication tables (incl. N=150 verifiable coding audit CSV), 6 PNG+PDF figures,
     both zero-leak PDFs (manuscript_f7_boost.pdf & supplementary_f7_jcp.pdf), and SHA256SUMS.json.
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
import statsmodels.api as sm

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
SCRIPT_DIR = BASE_DIR / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from econometrics_lib import (
    build_full_rank_design,
    fit_cr1_ols,
    wild_cluster_bootstrap_t,
)
from parser_lib import (
    parse_direct_return,
    parse_injuries_clean,
    parse_recall_record,
)

_spec08 = importlib.util.spec_from_file_location("compile08", SCRIPT_DIR / "08_compile_manuscript_pdf.py")
assert _spec08 is not None and _spec08.loader is not None
_mod08 = importlib.util.module_from_spec(_spec08)
_spec08.loader.exec_module(_mod08)
verify_pdf_zero_leaks = _mod08.verify_pdf_zero_leaks
_tex_to_html = _mod08._tex_to_html

_spec07 = importlib.util.spec_from_file_location("gen07", SCRIPT_DIR / "07_generate_figures_and_tables.py")
assert _spec07 is not None and _spec07.loader is not None
_mod07 = importlib.util.module_from_spec(_spec07)
_spec07.loader.exec_module(_mod07)
build_canonical_table5_markdown = _mod07.build_canonical_table5_markdown


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _load_raw_by_id() -> dict[int, dict]:
    raw = json.loads((BASE_DIR / "data" / "cpsc_recalls_2000_2026.json").read_text(encoding="utf-8"))
    return {int(r["RecallID"]): r for r in raw if r.get("RecallID") is not None}


# ---------------------------------------------------------------------------
# 1. Parser Unit Tests (Legacy Forensic + v4 Verbatim Channel & Remedy Duties)
# ---------------------------------------------------------------------------
def test_late2026_retailer_nested_chinese_entities() -> None:
    by_id = _load_raw_by_id()
    for rid in (11067, 11068):
        assert rid in by_id, f"Expected late-2026 audit recall {rid} in live CPSC JSON"
        parsed = parse_recall_record(by_id[rid])
        assert parsed is not None
        assert parsed["archetype_6"] == "1_Mkt_FD_China", f"Recall {rid} misclassified: {parsed['archetype_6']}"
        assert parsed["rescued_from_retailers"] == 1
        assert parsed["photo_verify"] == 1
        assert parsed["has_cn_entity"] == 1
        assert parsed["has_us_entity"] == 0


def test_domain_stripped_brick_and_mortar_and_pure_dtc() -> None:
    rec_online = {
        "RecallID": 999001,
        "RecallDate": "2025-05-01T00:00:00",
        "Title": "Online Heater Recall",
        "Description": "Sold online.",
        "Retailers": [{"Name": "Online at Amazon.com, Target.com, Walmart.com, HomeDepot.com, and Costco.com from Jan 2024 through Jan 2025 for $90."}],
        "Importers": [{"Name": "Shenzhen Bright Heat Co., Ltd., of China"}],
        "Manufacturers": [],
        "Distributors": [],
        "Remedies": [{"Name": "Cut the power cord and email a photo to support@gmail.com."}],
        "ConsumerContact": "Email support@gmail.com.",
        "Hazards": [{"Name": "Fire hazard"}],
        "Injuries": [{"Name": "None reported."}],
        "Products": [{"Name": "Heater", "NumberOfUnits": "About 5,000"}],
        "ManufacturerCountries": [{"Country": "China"}],
    }
    p_on = parse_recall_record(rec_online)
    assert p_on is not None
    assert p_on["has_brick"] == 0
    assert p_on["archetype_6"] == "1_Mkt_FD_China"
    assert p_on["amazon_channel_3way"] == "multi_channel_with_amazon"
    assert p_on["strict_amazon_exclusive"] == 0
    assert p_on["multi_channel_online_with_amazon"] == 1

    for store_str in [
        "Aldi stores nationwide for $15.",
        "JC Penney nationwide for $40.",
        "Ross nationwide for $20.",
        "Kohl's nationwide for $35.",
        "Target stores nationwide and online at Target.com for $25.",
        "Helly Hansen clothing stores and uniform clothing suppliers nationwide and online at www.hhworkwear.com for $90.",
        "MoMA Design Stores and online at store.moma.org for $85.",
        "Independent bike shops nationwide and online at www.buzzbicycles.com for $1,500.",
    ]:
        rec_bm = dict(rec_online)
        rec_bm["Retailers"] = [{"Name": store_str}]
        rec_bm["Importers"] = [{"Name": "Legacy Retail Corp., of Minneapolis, Minnesota"}]
        p_bm = parse_recall_record(rec_bm)
        assert p_bm is not None
        assert p_bm["has_brick"] == 1, f"Failed brick detection for: {store_str}"

    rec_ross = dict(rec_online)
    rec_ross["Retailers"] = [{"Name": "Online at Amazon.com for $20 (Bob Ross collectible mug)."}]
    p_ross = parse_recall_record(rec_ross)
    assert p_ross is not None
    assert p_ross["has_brick"] == 0
    assert p_ross["strict_amazon_exclusive"] == 1

    by_id = _load_raw_by_id()
    for rid in (9550, 9727, 9843, 10217, 10322, 11058, 9262, 9468, 10103, 10245, 10754):
        p = parse_recall_record(by_id[rid])
        assert p is not None and p["has_brick"] == 1, f"Live physical-store recall {rid} missed brick!"
        assert p["archetype_6"] != "4_DTC_Online_Only", f"Live physical-store recall {rid} leaked into DTC!"


def test_nonchina_fd_and_platform_colisting_and_us_purity() -> None:
    by_id = _load_raw_by_id()
    for rid in (9277, 9500, 10499):
        p = parse_recall_record(by_id[rid])
        assert p is not None and p["archetype_6"] == "2_Mkt_FD_NonChina", f"Recall {rid} expected 2_Mkt_FD_NonChina, got {p['archetype_6']}"

    for rid in (10227, 10228, 10614, 9218):
        p = parse_recall_record(by_id[rid])
        assert p is not None and p["archetype_6"] == "1_Mkt_FD_China", f"Recall {rid} expected 1_Mkt_FD_China, got {p['archetype_6']}"

    p_amz1p = parse_recall_record(by_id[9436])
    assert p_amz1p is not None and p_amz1p["archetype_6"] == "3_Mkt_True_US"

    df = pd.read_csv(BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv", low_memory=False)
    d22_us = df[(df["year"] >= 2022) & (df["archetype_6"] == "3_Mkt_True_US")]
    assert int((d22_us["has_us_entity"] == 0).sum()) == 0, "Unverified entity leaked into 3_Mkt_True_US!"


def test_v4_verbatim_3way_amazon_channel_and_remedy_duty_edge_cases() -> None:
    """Explicitly test all reviewer-cited edge cases (P0 #1 and P0 #2):
    Anker (10311), OCOOPA (10895), Jugader (9924), UVIPC (10148), TADAKAZU (10317),
    and the 5 ambiguous Amazon notices (9234, 10238, 10245, 10276, 10494).
    """
    by_id = _load_raw_by_id()

    # 1. Jugader Zipline Kits (RecallID 9924): optional "photo OR online purchase order number"
    p_jug = parse_recall_record(by_id[9924])
    assert p_jug is not None
    assert p_jug["archetype_6"] == "1_Mkt_FD_China"
    assert p_jug["amazon_channel_3way"] == "strict_amazon_exclusive"
    assert p_jug["strict_amazon_exclusive"] == 1
    assert p_jug["photo_language"] == 1
    assert p_jug["proof_alternative_path"] == 1
    assert p_jug["proof_status"] == "optional_or_alternative_proof"
    assert p_jug["photo_mandatory"] == 0
    assert p_jug["physically_disabled"] == 0
    assert p_jug["remedy_duty_4cat"] == "photo_optional_or_alternative"

    # 2. UVIPC Baby Gates (RecallID 10148): proof of destruction WITHOUT literal "photo"
    p_uv = parse_recall_record(by_id[10148])
    assert p_uv is not None
    assert p_uv["archetype_6"] == "1_Mkt_FD_China"
    assert p_uv["amazon_channel_3way"] == "strict_amazon_exclusive"
    assert p_uv["photo_language"] == 0
    assert p_uv["destruction_proof"] == 1
    assert p_uv["destruction_proof_without_photo"] == 1
    assert p_uv["proof_status"] == "mandatory_proof"
    assert p_uv["physically_disabled"] == 1
    assert p_uv["remedy_duty_4cat"] == "non_photo_destruction_or_disposal_proof"

    # 3. Anker PowerCore 10000 (RecallID 10311): multi-channel (Anker, Amazon, Newegg, eBay) + full-notice HHW warning
    p_ank = parse_recall_record(by_id[10311])
    assert p_ank is not None
    assert p_ank["amazon_channel_3way"] == "multi_channel_with_amazon"
    assert p_ank["strict_amazon_exclusive"] == 0
    assert p_ank["multi_channel_online_with_amazon"] == 1
    assert p_ank["photo_language"] == 1
    assert p_ank["photo_mandatory"] == 1
    assert p_ank["permanent_marking"] == 1
    assert p_ank["physically_disabled"] == 0
    assert p_ank["warning_remedy"] == 0
    assert p_ank["warning_full_notice"] == 1

    # 4. OCOOPA Hand Warmers (RecallID 10895): multi-channel (Amazon, Ocoopa.com, Ocoopa.net, Walmart.com) + HHW warning
    p_oco = parse_recall_record(by_id[10895])
    assert p_oco is not None
    assert p_oco["amazon_channel_3way"] == "multi_channel_with_amazon"
    assert p_oco["strict_amazon_exclusive"] == 0
    assert p_oco["multi_channel_online_with_amazon"] == 1
    assert p_oco["warning_remedy"] == 1
    assert p_oco["warning_full_notice"] == 1

    # 5. TADAKAZU Baby Loungers (RecallID 10317): strict exclusive, explicit_fba=0, fba_token=1 (model suffix only)
    p_tad = parse_recall_record(by_id[10317])
    assert p_tad is not None
    assert p_tad["amazon_channel_3way"] == "strict_amazon_exclusive"
    assert p_tad["explicit_fba"] == 0
    assert p_tad["fba_token"] == 1

    # 6. Five ambiguous Amazon notices (non-retail Fire TV + 4 CPSC field conflicts)
    for rid in (9234, 10238, 10245, 10276, 10494):
        p_amb = parse_recall_record(by_id[rid])
        assert p_amb is not None
        assert p_amb["amazon_channel_3way"] == "amazon_channel_ambiguous", f"Recall {rid} expected ambiguous, got {p_amb['amazon_channel_3way']}"
        assert p_amb["strict_amazon_exclusive"] == 0

    # 7. Global 2022-2026 counts in parsed CSV match exact audited totals
    df = pd.read_csv(BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv", low_memory=False)
    d22 = df[df["year"] >= 2022]
    vc = d22["amazon_channel_3way"].value_counts().to_dict()
    assert vc["strict_amazon_exclusive"] == 441
    assert vc["multi_channel_with_amazon"] == 440
    assert vc["amazon_channel_ambiguous"] == 5
    assert vc["no_amazon_mention"] == 985
    assert int(d22["destruction_proof_without_photo"].sum()) == 7


def test_negation_aware_direct_return_and_hazwaste_fixes() -> None:
    assert parse_direct_return("Consumers should not return the recalled pajamas to the stores.") == 0
    assert parse_direct_return(
        "Contact Sakar for prepaid postage packaging to return the helmet to them. Do not return the helmet to Walmart."
    ) == 1

    by_id = _load_raw_by_id()
    assert parse_recall_record(by_id[10279])["direct_return"] == 0
    for rid in (9216, 9314, 9426, 9505, 10260):
        assert parse_recall_record(by_id[rid])["direct_return"] == 1, f"Missed direct_return on {rid}"

    p_anker = parse_recall_record(by_id[10311])
    assert p_anker is not None
    assert p_anker["haz_lithium"] == 1
    assert p_anker["self_dispose_instructed"] == 1
    assert p_anker["direct_return"] == 0

    for rid in (9306, 9697, 9706, 10174, 10299, 10359):
        p_mech = parse_recall_record(by_id[rid])
        assert p_mech is not None and p_mech["haz_lithium"] == 0, f"Mechanical recall {rid} falsely flagged haz_lithium!"


def test_double_count_free_injury_parser() -> None:
    cases = [
        ("The firm has received 56 injuries, including 35 burns.", 1, 56, 0),
        ("SharkNinja has received 106 reports of burn injuries, including more than 50 reports of second- or third-degree burns.", 1, 106, 0),
        ("Harbor Freight Tools has received 96 reports of the seat weld breaking, including ten reports of minor injuries, including bruises.", 1, 10, 0),
        ("Little Giant has received 25 reports of ladders retracting, including 19 reports of injuries, consisting of three reports of head injuries and 16 reports of other injuries.", 1, 19, 0),
        ("None reported. CPSC estimates 2,400 magnet ingestions were treated in hospital emergency departments. CPSC is aware of eight deaths since 2005.", 0, 0, 0),
        ("Giant Bicycle has received one report of the fork cracking with no reported injuries.", 0, 0, 0),
        ("The firm has received 1,399 reports of magnet closures failing. No magnet ingestions or injuries have been reported.", 0, 0, 0),
        ("Vive Health has received two reports of entrapment deaths.", 1, 2, 1),
        ("Globally, IKEA has received notice of four incident reports of the rivet coming loose. None of the reported incidents occurred in the U.S. or required medical attention.", 0, 0, 0),
        ("BISSELL has received 17 reports of the recalled vacuum cleaners smoking and emitting a burning odor. Six of the reports included the battery pack catching fire, three of which resulted in minor property damage and two resulting in minor burn injuries.", 1, 2, 0),
        ("Briggs & Stratton has received five reports of the surface cleaners spray bar detaching from the central hub, including one report of the spray bar striking an operator, resulting in a cut on the knee.", 1, 1, 0),
        ("A 4-year-old girl and a 6-year-old girl reportedly became entrapped in the cover of the weighted blanket and died due to asphyxia at Camp Lejeune, North Carolina in April 2022. Target has received four reports of children becoming entrapped in these weighted blankets, including the two fatalities.", 1, 2, 1),
        ("The firm is aware of at least 152 reports of mold in the air conditioners, including 17 reports of consumers experiencing symptoms such as respiratory infections, allergic reactions, coughing, sneezing and/or sore throats from mold exposure.", 1, 17, 0),
    ]
    for txt, exp_has, exp_cnt, exp_dth in cases:
        res = parse_injuries_clean(txt)
        assert res["has_injury"] == exp_has, f"has_injury mismatch on: {txt} -> {res}"
        assert res["clean_injuries"] == exp_cnt, f"clean_injuries mismatch on: {txt} -> {res}"
        assert res["has_death"] == exp_dth, f"has_death mismatch on: {txt} -> {res}"


# ---------------------------------------------------------------------------
# 2. Full-Rank Design Matrix & Exact Brute-Force CR1 + WCB Equivalence
# ---------------------------------------------------------------------------
def test_all_saved_regressions_are_full_rank() -> None:
    p1 = json.loads((BASE_DIR / "results" / "04_pillar1_econometrics.json").read_text(encoding="utf-8"))
    p234 = json.loads((BASE_DIR / "results" / "05_pillars_2_3_4.json").read_text(encoding="utf-8"))
    v4 = json.loads((BASE_DIR / "results" / "09_v4_channel_remedy_audit.json").read_text(encoding="utf-8"))

    for ycol, m in p1["main_models_2022_2026"].items():
        assert m["rank"] == m["k"], f"Main model {ycol} rank deficient: {m['rank']} != {m['k']}"
        assert m["n"] == 1822

    for sk, r in p1["robustness_photo_verify_2022_2026"].items():
        if isinstance(r, dict) and "rank" in r and "k" in r:
            assert r["rank"] == r["k"], f"Robustness {sk} rank deficient"

    r7b = p1["robustness_photo_verify_2022_2026"]["R7b_strict_durables_ge_100"]
    assert r7b["n"] == 685
    assert r7b["n_clusters"] == 481
    assert r7b["rank"] == r7b["k"]
    assert r7b["exclusion_audit"]["n_price_ge_100_all"] == 794
    assert r7b["exclusion_audit"]["n_excluded_total"] == 109
    assert r7b["exclusion_audit"]["n_strict_durables_retained"] == 685

    for key in ("traceability_upc_fe", "coordination_inconjunction_fe", "platform_amazon_vs_nonamazon_fe"):
        m = p234["pillar2"][key]
        assert m["rank"] == m["k"], f"Pillar 2 {key} rank deficient"

    for key in ("mandatory_rule_fe", "hazwaste_photo_verify_fe", "hazwaste_self_dispose_fe", "haz_photo_disposal_full_pop_fe", "duration_log_fe", "has_injury_fe", "log_clean_injuries_fe"):
        m = p234["pillar4"][key]
        assert m["rank"] == m["k"], f"Pillar 4 {key} rank deficient"

    # Every v4 all-channel & strict-durables disaggregated model must also be full rank!
    for out_name, res in v4["all_channel_disaggregated_2022_2026"].items():
        assert res["rank"] == res["k"], f"v4 all_channel/{out_name} rank deficient!"
    for out_name, res in v4["strict_durables_ge_100_disaggregated"].items():
        assert res["rank"] == res["k"], f"v4 strict_durables/{out_name} rank deficient!"
    for def_name, block in v4["three_definition_channel_comparisons"].items():
        for out_name, res in block["common_support_models"].items():
            assert res["n"] == block["cs_n"], f"v4 {def_name}/{out_name} n mismatch!"
            assert np.isfinite(res["beta"]) and np.isfinite(res["se"]), f"v4 {def_name}/{out_name} non-finite!"


def test_cr1_exact_equivalence_with_statsmodels() -> None:
    df = pd.read_csv(BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv", low_memory=False)
    sub = df[(df["year"] >= 2022) & (df["archetype_6"] != "7_Other_Unclear") & df["price"].notna() & df["units"].notna()].copy().reset_index(drop=True)
    sub["p_dec"] = pd.qcut(sub["price"], q=10, labels=False, duplicates="drop").astype(int).astype(str)
    sub["u_dec"] = pd.qcut(sub["units"], q=10, labels=False, duplicates="drop").astype(int).astype(str)
    sub["a_mkt_fd_cn"] = (sub["archetype_6"] == "1_Mkt_FD_China").astype(int)
    sub["a_mkt_fd_noncn"] = (sub["archetype_6"] == "2_Mkt_FD_NonChina").astype(int)
    sub["a_mkt_true_us"] = (sub["archetype_6"] == "3_Mkt_True_US").astype(int)
    sub["a_dtc_online"] = (sub["archetype_6"] == "4_DTC_Online_Only").astype(int)
    sub["a_omnichannel"] = (sub["archetype_6"] == "5_Omnichannel").astype(int)

    num_cols = ["a_mkt_fd_cn", "a_mkt_fd_noncn", "a_mkt_true_us", "a_dtc_online", "a_omnichannel", "is_china_mfr"]
    fe_cols = ["p_dec", "u_dec", "prod_cat", "hazard_cat", "yq"]
    X, names = build_full_rank_design(sub, num_cols, fe_cols)
    y = sub["photo_verify"].astype(float).to_numpy()
    cl = sub["firm_cluster"].astype(str).to_numpy()

    ours = fit_cr1_ols(y, X, names, cl)
    sm_res = sm.OLS(y, X).fit(cov_type="cluster", cov_kwds={"groups": cl}, use_t=True)

    for idx, nm in enumerate(names[:6]):
        assert np.isclose(ours["params"][nm]["beta"], float(sm_res.params[idx]), atol=1e-10)
        assert np.isclose(ours["params"][nm]["se"], float(sm_res.bse[idx]), atol=1e-10)
        assert np.isclose(ours["params"][nm]["t"], float(sm_res.tvalues[idx]), atol=1e-9)
        assert np.isclose(ours["params"][nm]["p"], float(sm_res.pvalues[idx]), atol=1e-9)


def test_wcb_r_exact_equivalence_with_brute_force() -> None:
    rng = np.random.default_rng(12345)
    G, m = 30, 8
    n = G * m
    clusters = np.repeat(np.arange(G), m)
    x1 = rng.normal(size=n)
    x2 = rng.normal(size=n)
    u_g = rng.normal(scale=0.8, size=G)[clusters]
    y = 1.0 + 0.5 * x1 - 0.3 * x2 + u_g + rng.normal(scale=0.5, size=n)
    X = np.column_stack([np.ones(n), x1, x2])
    names = ["const", "x1", "x2"]

    fast = wild_cluster_bootstrap_t(y, X, names, clusters, {"x1": 1.0}, B=199, seed=777)

    X_r = np.column_stack([np.ones(n), x2])
    beta_r = np.linalg.lstsq(X_r, y, rcond=None)[0]
    yhat_r = X_r @ beta_r
    e_r = y - yhat_r

    obs_fit = fit_cr1_ols(y, X, names, clusters)
    t_obs_bf = obs_fit["params"]["x1"]["t"]

    rng_bf = np.random.default_rng(777)
    W_bf = rng_bf.choice(np.array([-1.0, 1.0]), size=(199, G))
    t_stars = []
    for b in range(199):
        y_star = yhat_r + W_bf[b, clusters] * e_r
        f_b = fit_cr1_ols(y_star, X, names, clusters)
        t_stars.append(abs(f_b["params"]["x1"]["t"]))
    p_bf = (1 + sum(ts >= abs(t_obs_bf) for ts in t_stars)) / 200.0

    assert np.isclose(fast["t_obs"], t_obs_bf, atol=1e-10)
    assert np.isclose(fast["p_wcb"], p_bf, atol=1e-12)


# ---------------------------------------------------------------------------
# 3. Formal Theory Model & Exact v4 Receipt-to-Manuscript/Supplement Parity
# ---------------------------------------------------------------------------
def test_theory_propositions_verified() -> None:
    th = json.loads((BASE_DIR / "results" / "03_theory_equilibrium.json").read_text(encoding="utf-8"))
    pv = th["proposition_verifications"]
    assert pv["prop1_fd_cutoff_lower_than_us"] is True
    assert pv["prop1_price_monotonicity_PU"] is True
    assert pv["prop2_dtc_observability_shield"] is True
    assert pv["prop3_audit_cost_diffusion"] is True
    assert pv["prop4_private_vs_social_wedge"] is True


def test_v4_receipts_and_manuscript_supplement_parity() -> None:
    md = (BASE_DIR / "manuscript_f7_boost.md").read_text(encoding="utf-8")
    supp = (BASE_DIR / "supplementary_f7_jcp.md").read_text(encoding="utf-8")
    p1 = json.loads((BASE_DIR / "results" / "04_pillar1_econometrics.json").read_text(encoding="utf-8"))
    v4 = json.loads((BASE_DIR / "results" / "09_v4_channel_remedy_audit.json").read_text(encoding="utf-8"))

    sf = v4["channel_contamination_and_sample_flow"]
    c3 = v4["three_definition_channel_comparisons"]
    disp = v4["hazardous_notice_coverage_v4"]
    amz_cs = v4["in_re_amazon_case_study_v4"]
    fba = amz_cs["fba_terminology_audit"]
    audit = v4["remedy_duty_coding_audit_150"]
    ac = v4["all_channel_disaggregated_2022_2026"]
    sd_ac = v4["strict_durables_ge_100_disaggregated"]
    r7b = p1["robustness_photo_verify_2022_2026"]["R7b_strict_durables_ge_100"]

    # Verify exact contamination & benchmark numbers in JSON receipt
    assert sf["legacy_cs_391_contamination"]["other_flagged_plat_total"] == 51
    assert sf["legacy_cs_391_contamination"]["other_flagged_plat_by_group"]["1_Mkt_FD_China"] == 13
    assert sf["legacy_cs_391_contamination"]["other_flagged_plat_by_group"]["3_Mkt_True_US"] == 38
    assert sf["legacy_cs_391_contamination"]["verbatim_multi_channel_total"] == 100
    assert sf["legacy_amazon_only_mkt_601_breakdown"]["multi_channel_online_total"] == 162

    d1 = c3["Def1_Broad_Mkt_Mentions_Amazon"]
    d2a = c3["Def2a_NoOtherFlaggedPlat_Benchmark"]
    d2b = c3["Def2b_Strict_Amazon_Exclusive_Verbatim"]
    d3 = c3["Def3_MultiChannel_Online_With_Amazon"]

    assert d1["cs_n"] == 391 and d1["cs_cells"] == 38
    assert d2a["cs_n"] == 313 and d2a["cs_cells"] == 34
    assert np.isclose(100 * d2a["common_support_models"]["photo_language"]["beta"], 10.89, atol=0.02)
    assert np.isclose(d2a["common_support_models"]["photo_language"]["p_wcb"], 0.121, atol=0.005)
    assert np.isclose(100 * d2a["common_support_models"]["direct_return"]["beta"], -7.00, atol=0.02)
    assert np.isclose(d2a["common_support_models"]["direct_return"]["p_wcb"], 0.097, atol=0.005)

    assert d2b["cs_n"] == 236 and d2b["cs_cells"] == 25
    assert np.isclose(100 * d2b["common_support_models"]["photo_language"]["beta"], 10.70, atol=0.02)
    assert np.isclose(d2b["common_support_models"]["photo_language"]["p_wcb"], 0.226, atol=0.005)
    assert np.isclose(100 * d2b["common_support_models"]["direct_return"]["beta"], -10.76, atol=0.02)
    assert np.isclose(d2b["common_support_models"]["direct_return"]["p_wcb"], 0.044, atol=0.005)
    assert d3["raw_n"] == 138
    assert d3["cs_n"] == 55 and d3["cs_cells"] == 11

    # Hazardous notice coverage & In re Amazon FBA terminology receipts
    assert disp["screened_notices"] == 67
    assert disp["screened_affected_units"] == 3_947_390
    assert disp["disposal_word_notices"] == 65
    assert disp["disposal_word_affected_units"] == 3_944_590
    assert disp["warning_remedy_notices"] == 52
    assert disp["warning_full_notice_count"] == 54
    assert disp["warning_full_notice_affected_units"] == 3_910_951
    assert np.isclose(100 * disp["top2_ocoopa_anker_share"], 67.34, atol=0.02)
    assert fba["explicit_fulfilled_by_amazon_mentions"] == 0
    assert fba["standalone_fba_tokens"] == 1
    assert [x["recall_id"] for x in fba["fba_token_notices"]] == [10317]

    # Audit N=150 & methodology honesty
    assert audit["overall"]["n"] == 150
    assert audit["overall"]["n_any_discrepancy"] == 24
    assert audit["audit_methodology"]["independent_blind_multi_coder"] is False

    # Check exact numerical tokens in manuscript_f7_boost.md
    main_tokens = [
        "8,386",
        "1,822",
        "1,414",
        "51/391",
        "13/264",
        "38/127",
        "100/391",
        "162/601",
        f"+{100 * ac['photo_language']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"{100 * ac['direct_return']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * ac['photo_language']['contrast']['diff']:.2f}",
        f"{100 * ac['direct_return']['contrast']['diff']:.2f}",
        f"+{100 * d1['common_support_models']['photo_language']['beta']:.2f}",
        f"+{100 * d2a['common_support_models']['photo_language']['beta']:.2f}",
        f"{d2a['common_support_models']['photo_language']['p_wcb']:.3f}",
        f"{100 * d2a['common_support_models']['direct_return']['beta']:.2f}",
        f"{d2a['common_support_models']['direct_return']['p_wcb']:.3f}",
        f"+{100 * d2b['common_support_models']['photo_language']['beta']:.2f}",
        f"{d2b['common_support_models']['photo_language']['p_wcb']:.3f}",
        f"{100 * d2b['common_support_models']['direct_return']['beta']:.2f}",
        f"{d2b['common_support_models']['direct_return']['p_wcb']:.3f}",
        f"+{100 * r7b['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * sd_ac['photo_language']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * sd_ac['photo_language']['contrast']['diff']:.2f}",
        "Jugader",
        "UVIPC",
        "Anker",
        "OCOOPA",
        "TADAKAZU",
        "3,947,390",
        "3,910,951",
        "54/67",
        "67.34%",
        "0/601",
        "1/601",
        "+0.1831/qtr",
        "+0.1734/qtr",
        "24/150",
        "specification-sensitive",
    ]
    for tok in main_tokens:
        assert tok in md, f"Expected verified v4 receipt token {tok!r} missing from manuscript_f7_boost.md!"

    # Check underpowered sub-comparisons & Table S2/S3 in supplementary_f7_jcp.md
    supp_tokens = [
        "Table S1.",
        "Table S2.",
        "Table S3.",
        "N = 55",
        r"Strict Durables >=\$100 in Def 2b Strict Amz-Excl: Photo Language",
        "49",
        "Jugader Zipline Kits",
        "UVIPC Baby Gates",
        "TADAKAZU Baby Loungers",
    ]
    for tok in supp_tokens:
        assert tok in supp, f"Expected verified v4 supplement token {tok!r} missing from supplementary_f7_jcp.md!"


def test_table_s3_canonical_parity_and_table_s2_sync() -> None:
    supp = (BASE_DIR / "supplementary_f7_jcp.md").read_text(encoding="utf-8")

    # 1. Exact block match between Table S3 in supplementary_f7_jcp.md and canonical CSV generator
    canonical_t5 = build_canonical_table5_markdown()
    assert canonical_t5 in supp, "Table S3 in supplementary_f7_jcp.md drifted from canonical table5 CSV!"

    # 2. Independent cell-by-cell numeric parity audit of every Table S3 data row against CSV
    df5 = pd.read_csv(BASE_DIR / "tables" / "table5_amazon_hac_shock_and_persistence.csv", dtype={"slope_change_p": str})
    lookup = {(str(r["cutoff"]), str(r["series"])): r for _, r in df5.iterrows()}
    t5_lines = [ln.strip() for ln in canonical_t5.splitlines() if ln.strip().startswith("|")]
    expected_row_keys = [
        ("jul2024_2024Q3", "log_amz_over_bm_L4"),
        ("jul2024_2024Q3", "log_amz_over_nonamz_L4"),
        ("jul2024_2024Q3", "log_amz_1p_L4"),
        ("jul2024_2024Q3", "log_bm_1p_L4"),
        ("jan2025_2025Q1", "log_amz_over_bm_L4"),
        ("jan2025_2025Q1", "log_amz_over_nonamz_L4"),
        ("ramp_2025Q2", "log_amz_over_bm_L4"),
        ("jul2024_2024Q3_statutory_ctrl", "log_amz_over_bm_L4"),
        ("monthly_2024_08_T70", "log_amz_over_bm_L6"),
        ("monthly_2024_08_T70", "log_amz_over_nonamz_L6"),
    ]
    data_rows = [ln for ln in t5_lines[2:] if not ln.startswith("| **")]
    assert len(data_rows) == len(expected_row_keys)
    for row_md, key in zip(data_rows, expected_row_keys, strict=True):
        cells = [c.strip().replace("*", "") for c in row_md.strip("|").split("|")]
        rec = lookup[key]
        assert np.isclose(float(cells[1]), float(rec["pre_slope"]), atol=1e-4)
        assert np.isclose(float(cells[2]), float(rec["pre_slope_t"]), atol=1e-2)
        assert np.isclose(float(cells[3]), float(rec["level_jump"]), atol=1e-4)
        assert np.isclose(float(cells[4]), float(rec["level_jump_t"]), atol=1e-2)
        assert np.isclose(float(cells[5]), float(rec["slope_change"]), atol=1e-4)
        assert np.isclose(float(cells[6]), float(rec["slope_change_se"]), atol=1e-4)
        assert np.isclose(float(cells[7]), float(rec["slope_change_t"]), atol=1e-2)
        assert cells[8] == str(rec["slope_change_p"]).strip()
        assert np.isclose(float(cells[9]), float(rec["r2"]), atol=1e-3)

    # 3. Verify Table S2 R7/R7b exact counts match CSV
    assert "| R7. Products Priced $\\ge \\$100$ (All Categories) | 794 | 571 | +45.17 |" in supp
    assert "| R7b. Strict Durables ($\\ge \\$100$) | 685 | 481 | +41.39 |" in supp


def test_authorship_hygiene_and_no_referee_overclaims() -> None:
    md = (BASE_DIR / "manuscript_f7_boost.md").read_text(encoding="utf-8")
    supp = (BASE_DIR / "supplementary_f7_jcp.md").read_text(encoding="utf-8")
    aud = json.loads((BASE_DIR / "results" / "02_parser_audit_metrics.json").read_text(encoding="utf-8"))

    assert aud["audit_methodology"]["audit_type"] == "author_reviewed_parser_consistency_audit"
    assert aud["audit_methodology"]["independent_blind_annotation"] is False

    # Exact required authorship block in BOTH main manuscript and supplement
    required_auth = [
        "Zijian Zeng",
        "Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA",
        "zijianzeng@foxmail.com",
        "1002266693@ucsiuniversity.edu.my",
    ]
    for doc_name, txt in [("manuscript_f7_boost.md", md), ("supplementary_f7_jcp.md", supp)]:
        for req in required_auth:
            assert req in txt, f"Required authorship line {req!r} missing from {doc_name}!"

    forbidden_patterns = [
        r"\bTarget\s+Venues?\b",
        r"\bTarget\s+Format\b",
        r"\bTrack\s+A\b",
        r"\bTrack\s+B\b",
        r"\bground[\s\-]truth\b",
        r"\bindependent\s+blind\s+ground",
        r"\bmunicipal\s+trash\b",
        r"\bmunicipal\s+solid[\s\-]waste\b",
        r"\binto\s+household\s+trash\b",
        r"\bisolate\s+the\s+causal\s+effect\b",
        r"\bHigh[\s\-]Price\s+Durables\b",
        r"\bproves\s+that\b",
    ]
    for doc_name, txt in [("manuscript_f7_boost.md", md), ("supplementary_f7_jcp.md", supp)]:
        for pat in forbidden_patterns:
            assert not re.search(pat, txt, re.IGNORECASE), f"Forbidden pattern {pat!r} found in {doc_name}!"


def test_references_100_percent_cited_and_crossref_verified() -> None:
    md = (BASE_DIR / "manuscript_f7_boost.md").read_text(encoding="utf-8")
    refs = json.loads((BASE_DIR / "results" / "06_verified_references.json").read_text(encoding="utf-8"))
    assert refs["n_crossref_verified"] == 22
    assert refs["n_official_records"] == 10

    body_text, ref_section = md.split("## References", maxsplit=1)

    dois_found = set()
    for jref in refs["journal_references"]:
        assert jref["http_status"] == 200
        assert jref["doi"] in ref_section, f"Verified DOI {jref['doi']} missing from References!"
        dois_found.add(jref["doi"])
        first_surname = jref["authors"][0].split(",")[0].strip()
        assert first_surname in body_text, f"Reference author {first_surname} ({jref['key']}) not cited in body!"

    # Explicitly confirm required v4 reviewer citations are live Crossref-verified and in References
    assert "10.1007/s11747-023-00967-x" in dois_found
    assert "10.1287/mksc.2025.0618" in dois_found

    for needle in (
        "Amazon.com, Inc. v. CPSC",
        "U.S. CPSC 2024",
        "U.S. CPSC 2025",
        "Bolanos et al. 2025",
        "Consumer Federation of America 2025",
        "Jugader",
        "UVIPC",
        "Anker",
        "OCOOPA",
        "TADAKAZU",
    ):
        assert needle in body_text, f"Official/policy/notice reference {needle!r} not cited in body!"

    ref_nums = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.\s+", ref_section, re.MULTILINE)]
    assert ref_nums == list(range(1, 33)), f"Expected references 1..32, found {ref_nums}"


# ---------------------------------------------------------------------------
# 4. Math Renderer, Zero-NaN Tables (incl. N=150 Audit CSV), 6 Figures,
#    Zero-Leak PDFs (Main + Supplement), & Live SHA256SUMS.json
# ---------------------------------------------------------------------------
def test_tex_to_html_escaped_underscores_no_nested_sub() -> None:
    rendered = _tex_to_html(r"\beta_{\text{Mkt\_FD\_China}} - \log(1 + \text{clean\_injuries})")
    assert "<sub>China</sub>" not in rendered
    assert "<sub>injuries</sub>" not in rendered
    assert "&#95;" in rendered


def test_zero_nan_tables_and_v4_audit_csv_and_figures_and_pdfs() -> None:
    tbl_dir = BASE_DIR / "tables"
    csvs = sorted(tbl_dir.glob("*.csv"))
    assert len(csvs) >= 14, f"Expected >= 14 CSV tables, found {len(csvs)}"
    for cp in csvs:
        df_t = pd.read_csv(cp, keep_default_na=False)
        assert len(df_t) > 0
        bad = int(df_t.astype(str).apply(lambda s: s.str.lower().isin(["nan", "none", "null"])).sum().sum())
        assert bad == 0, f"NaN/null string found in {cp.name}"

    # Verify stratified N=150 verifiable audit CSV structure & mandatory benchmark IDs
    aud_csv = pd.read_csv(tbl_dir / "table_remedy_duty_coding_audit.csv", keep_default_na=False)
    assert len(aud_csv) == 150
    aud_ids = set(aud_csv["recall_id"].astype(int).tolist())
    for req_id in (9924, 10148, 10311, 10895, 10317, 9234, 10276, 10494):
        assert req_id in aud_ids, f"Mandatory benchmark RecallID {req_id} missing from N=150 audit CSV!"
    assert int((aud_csv["audit_discrepancy_fields"].astype(str) != "no_discrepancy").sum()) == 24

    expected_figs = [
        "fig1_sample_flow_and_channel_audit",
        "fig2_three_definition_channel_comparison",
        "fig3_regime_emergence_and_diffusion",
        "fig4_hazwaste_coverage_and_in_re_amazon",
        "fig5_robustness_forest_and_platforms",
        "fig2_theory_equilibrium_and_archetype_gaps",
    ]
    for stem in expected_figs:
        png = BASE_DIR / "figures" / f"{stem}.png"
        pdf_f = BASE_DIR / "figures" / f"{stem}.pdf"
        assert png.exists() and png.stat().st_size > 50_000, f"Missing/tiny PNG: {png}"
        assert pdf_f.exists() and pdf_f.stat().st_size > 10_000, f"Missing/tiny PDF: {pdf_f}"

    # Verify BOTH compiled PDFs (main manuscript + supplementary material) have 0 leaked tokens
    main_pdf = BASE_DIR / "manuscript_f7_boost.pdf"
    assert main_pdf.exists() and main_pdf.stat().st_size > 1_000_000
    n_main, leaks_main = verify_pdf_zero_leaks(main_pdf)
    assert n_main >= 12
    assert leaks_main == [], f"Leaked tokens in manuscript_f7_boost.pdf: {leaks_main}"

    supp_pdf = BASE_DIR / "supplementary_f7_jcp.pdf"
    assert supp_pdf.exists() and supp_pdf.stat().st_size > 500_000
    n_supp, leaks_supp = verify_pdf_zero_leaks(supp_pdf)
    assert n_supp >= 4
    assert leaks_supp == [], f"Leaked tokens in supplementary_f7_jcp.pdf: {leaks_supp}"


def test_sha256_manifest_live_integrity() -> None:
    sums_path = BASE_DIR / "SHA256SUMS.json"
    assert sums_path.exists(), "SHA256SUMS.json missing!"
    manifest = json.loads(sums_path.read_text(encoding="utf-8"))
    assert len(manifest) >= 50
    for rel_path, expected_hash in manifest.items():
        fp = BASE_DIR / rel_path
        assert fp.exists(), f"Manifest file missing: {rel_path}"
        actual_hash = _sha256(fp)
        assert actual_hash == expected_hash, f"SHA-256 mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}"
