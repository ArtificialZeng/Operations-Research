"""Comprehensive verification test suite for F7 Boost:
The Asset-Light Safety Gap (U.S. CPSC Recalls 2000-2026).

Covers:
  1. Unit tests for all 7 Wave-3 forensic parser fixes PLUS second-round deep
     audit fixes: late-2026 Retailers-nested Chinese entities, domain- & online-
     phrase-stripped Brick-and-Mortar matching (branded stores & independent
     shops), multi-comma/UK/Armenia Non-China FD, platform corporate-office
     co-listing guards vs. Amazon 1P private-label, 100% verified U.S. entity
     purity in 3_Mkt_True_US, negation-aware sentence-level direct_return,
     noun-inclusive hazardous-waste disposal ("disposal"), hazard-gated lithium
     classification (zero mechanical brake/bolt e-bike FPs), and double-count-
     free injury parsing with co-occurring property damage.
  2. Full-rank design matrix assertions across every saved regression receipt.
  3. Exact numerical equivalence of fit_cr1_ols against statsmodels CR1 and
     exact brute-force equivalence of Restricted Rademacher WCB-r.
  4. Formal theory model closed-form & proposition verification.
  5. Programmatic exact numerical parity between manuscript_f7_boost.md and
     CSV/JSON receipts (including Pillar 2 B&M diffusion decomposition, Pillar 3
     HAC statutory-control & monthly stress tests, and dual 150+50 OOS audits).
  6. 100% body citation coverage & live Crossref-verified DOI parity.
  7. Zero-NaN publication tables, 5 PNG+PDF figures, zero-leak & clean-math PDF,
     and live SHA256SUMS.json verification.
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
# 1. Parser Unit Tests (Wave-3 + Round-2 Deep Forensic Fixes)
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

    # Verify live census regressions fixed from Round-2 audit (physical stores no longer polluted into DTC!)
    by_id = _load_raw_by_id()
    for rid in (9550, 9727, 9843, 10217, 10322, 11058, 9262, 9468, 10103, 10245, 10754):
        p = parse_recall_record(by_id[rid])
        assert p is not None and p["has_brick"] == 1, f"Live physical-store recall {rid} missed brick!"
        assert p["archetype_6"] != "4_DTC_Online_Only", f"Live physical-store recall {rid} leaked into DTC!"


def test_nonchina_fd_and_platform_colisting_and_us_purity() -> None:
    by_id = _load_raw_by_id()
    # Multi-comma ("Laval, QC, Canada"), "of the United Kingdom", and Armenia must map to 2_Mkt_FD_NonChina!
    for rid in (9277, 9500, 10499):
        p = parse_recall_record(by_id[rid])
        assert p is not None and p["archetype_6"] == "2_Mkt_FD_NonChina", f"Recall {rid} expected 2_Mkt_FD_NonChina, got {p['archetype_6']}"

    # Platform corporate offices co-listed with Chinese 3P sellers must map to 1_Mkt_FD_China!
    for rid in (10227, 10228, 10614, 9218):
        p = parse_recall_record(by_id[rid])
        assert p is not None and p["archetype_6"] == "1_Mkt_FD_China", f"Recall {rid} expected 1_Mkt_FD_China, got {p['archetype_6']}"

    # Genuine Amazon 1P private label (Amazon Basics) MUST stay 3_Mkt_True_US!
    p_amz1p = parse_recall_record(by_id[9436])
    assert p_amz1p is not None and p_amz1p["archetype_6"] == "3_Mkt_True_US"

    # Global invariant: 100% of 3_Mkt_True_US recalls in parsed CSV MUST have verified has_us_entity == 1!
    df = pd.read_csv(BASE_DIR / "data" / "cpsc_parsed_2000_2026.csv", low_memory=False)
    d22_us = df[(df["year"] >= 2022) & (df["archetype_6"] == "3_Mkt_True_US")]
    assert int((d22_us["has_us_entity"] == 0).sum()) == 0, "Unverified entity leaked into 3_Mkt_True_US!"


def test_negation_aware_direct_return_and_hazwaste_fixes() -> None:
    # Negation guard: "should not return to stores" -> 0
    assert parse_direct_return("Consumers should not return the recalled pajamas to the stores.") == 0
    # Multi-sentence: prepaid mail return + "Do not return to Walmart" -> 1
    assert parse_direct_return(
        "Contact Sakar for prepaid postage packaging to return the helmet to them. Do not return the helmet to Walmart."
    ) == 1

    by_id = _load_raw_by_id()
    assert parse_recall_record(by_id[10279])["direct_return"] == 0
    for rid in (9216, 9314, 9426, 9505, 10260):
        assert parse_recall_record(by_id[rid])["direct_return"] == 1, f"Missed direct_return on {rid}"

    # Noun "disposal" rescue on Anker 1.158M PowerCore 10000 recall (10311)
    p_anker = parse_recall_record(by_id[10311])
    assert p_anker is not None
    assert p_anker["haz_lithium"] == 1
    assert p_anker["self_dispose_instructed"] == 1
    assert p_anker["direct_return"] == 0

    # Non-battery mechanical e-bike/hoverboard recalls must NOT be flagged as haz_lithium!
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
        # Round-2 live regression cases!
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

    for ycol, m in p1["main_models_2022_2026"].items():
        assert m["rank"] == m["k"], f"Main model {ycol} rank deficient: {m['rank']} != {m['k']}"
        assert m["n"] == 1822

    for sk, r in p1["robustness_photo_verify_2022_2026"].items():
        if isinstance(r, dict) and "rank" in r and "k" in r:
            assert r["rank"] == r["k"], f"Robustness {sk} rank deficient"

    assert "R7b_strict_durables_ge_100" in p1["robustness_photo_verify_2022_2026"]
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
# 3. Formal Theory Model & Exact Manuscript-to-Receipt Parity
# ---------------------------------------------------------------------------
def test_theory_propositions_verified() -> None:
    th = json.loads((BASE_DIR / "results" / "03_theory_equilibrium.json").read_text(encoding="utf-8"))
    pv = th["proposition_verifications"]
    assert pv["prop1_fd_cutoff_lower_than_us"] is True
    assert pv["prop1_price_monotonicity_PU"] is True
    assert pv["prop2_dtc_observability_shield"] is True
    assert pv["prop3_audit_cost_diffusion"] is True
    assert pv["prop4_private_vs_social_wedge"] is True


def test_manuscript_numerical_parity_with_receipts() -> None:
    md = (BASE_DIR / "manuscript_f7_boost.md").read_text(encoding="utf-8")
    p1 = json.loads((BASE_DIR / "results" / "04_pillar1_econometrics.json").read_text(encoding="utf-8"))
    p234 = json.loads((BASE_DIR / "results" / "05_pillars_2_3_4.json").read_text(encoding="utf-8"))
    aud = json.loads((BASE_DIR / "results" / "02_parser_audit_metrics.json").read_text(encoding="utf-8"))

    mm = p1["main_models_2022_2026"]
    rob = p1["robustness_photo_verify_2022_2026"]
    hac = p234["pillar3"]["hac_its_results"]["jul2024_2024Q3"]
    hac_stat = p234["pillar3"]["hac_statutory_rule_controls_2024Q3"]["log_amz_over_bm_L4"]["params"]["slope_change"]
    hac_mo = p234["pillar3"]["hac_monthly_its_2021_2026"]["log_amz_over_bm_L6"]["params"]["slope_change_mo"]
    bm_dec = p234["pillar2"]["bm_diffusion_decomposition"]
    hw_fd = p234["pillar4"]["hazwaste_by_archetype"]["1_Mkt_FD_China"]
    hw_conc = p234["pillar4"]["hazwaste_concentration_audit"]
    rd_fd = p1["remedy_disaggregation_photo_verify_2022_2026"]["by_archetype"]["1_Mkt_FD_China"]
    fba_aud = p234["pillar3"]["fba_scope_audit"]
    oos = aud["oos_50_2025_2026"]
    r7b = rob["R7b_strict_durables_ge_100"]
    dtc_pv = mm["photo_verify"]["terms"]["a_dtc_online"]

    # Verify exact 4-way remedy disaggregation & hazwaste concentration receipts
    assert rd_fd["n_photo_verify"] == 371
    assert rd_fd["n_without_physical_mutilate"] == 118
    assert rd_fd["n_with_physical_mutilate"] == 253
    assert sum(rd_fd["mutually_exclusive_4way_counts"].values()) == 371
    assert hw_conc["total_units_assigned_consumer_self_disposal"] == 3_947_390
    assert hw_conc["top2_ocoopa_anker_units"] == 2_658_000
    assert hw_conc["ocoopa_10895_prohibits_ordinary_trash_and_curbside_bins"] is True
    assert fba_aud["n_amazon_only_2022_2026"] == 601
    assert fba_aud["n_explicit_fba_mentions_2022_2026"] == 1

    expected_tokens = [
        "8{,}386",
        "1{,}822",
        "1{,}414",
        f"+{100 * mm['photo_verify']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * mm['photo_verify']['contrast']['diff']:.2f}",
        f"+{100 * mm['physical_mutilate']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"{100 * mm['direct_return']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * mm['free_webmail']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * mm['no_phone']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * dtc_pv['beta']:.2f}",
        f"{100 * dtc_pv['ci_lo']:+.2f}",
        f"{100 * dtc_pv['ci_hi']:+.2f}",
        f"+{100 * rob['R7_high_price_ge_100']['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * r7b['terms']['a_mkt_fd_cn']['beta']:.2f}",
        f"+{100 * r7b['contrast']['diff']:.2f}",
        f"{r7b['n']}",
        f"{r7b['n_clusters']}",
        "118/371",
        "253/371",
        "202/371",
        "51/371",
        "26/371",
        "92/371",
        f"{rob['R4_binomial_logit_or']['terms']['a_mkt_fd_cn']['or']:.2f}",
        f"+{100 * bm_dec['BM_Made_in_China']['annual_slope_pp']:.2f}",
        f"+{hac['log_amz_over_bm_L4']['its_params']['slope_change']['beta']:.4f}",
        f"+{hac['log_amz_over_nonamz_L4']['its_params']['slope_change']['beta']:.4f}",
        f"+{hac_stat['beta']:.4f}",
        f"+{hac_mo['beta']:.4f}",
        f"{hw_fd['units_self_disposed_total']:,}",
        "67.34%",
        "1/601",
        f"{100 * aud['archetype_6']['exact_accuracy']:.2f}\\%",
        f"{aud['binary_fields']['has_injury']['f1']:.4f}",
        f"{oos['binary_fields']['physical_mutilate']['f1']:.4f}",
    ]
    for tok in expected_tokens:
        assert tok in md, f"Expected verified receipt number {tok!r} missing from manuscript_f7_boost.md!"


def test_table5_exact_programmatic_parity_and_table3_table7_sync() -> None:
    md = (BASE_DIR / "manuscript_f7_boost.md").read_text(encoding="utf-8")

    # 1. Exact block match between Table 5 in manuscript_f7_boost.md and canonical CSV generator
    canonical_t5 = build_canonical_table5_markdown()
    assert canonical_t5 in md, "Table 5 in manuscript_f7_boost.md drifted from canonical table5 CSV!"

    # 2. Independent cell-by-cell numeric parity audit of every Table 5 data row against CSV
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
    data_rows = [
        ln for ln in t5_lines[2:]
        if not ln.startswith("| **")
    ]
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

    # 3. Verify Table 3 R7/R7b & Table 7 OOS-50 exact counts match CSVs
    assert "| R7. **Products Priced $\\ge \\$100$ (All Categories)** | 794 | 571 | **+45.17** |" in md
    assert "| R7b. **Strict Durables ($\\ge \\$100$)** | 685 | 481 | **+41.39** |" in md
    assert "| OOS `photo_verify` | 50 | 32 | 0 | 18 | 0 |" in md
    assert "| OOS `direct_return` | 50 | 6 | 0 | 44 | 0 |" in md


def test_no_referee_overclaims_in_manuscript_and_audit_json() -> None:
    md = (BASE_DIR / "manuscript_f7_boost.md").read_text(encoding="utf-8")
    aud = json.loads((BASE_DIR / "results" / "02_parser_audit_metrics.json").read_text(encoding="utf-8"))

    assert aud["audit_methodology"]["audit_type"] == "author_reviewed_parser_consistency_audit"
    assert aud["audit_methodology"]["independent_blind_annotation"] is False

    forbidden_patterns = [
        r"\bground[\s\-]truth\b",
        r"\bindependent\s+blind\s+ground",
        r"\bmunicipal\s+trash\b",
        r"\bmunicipal\s+solid[\s\-]waste\b",
        r"\binto\s+household\s+trash\b",
        r"\bisolate\s+the\s+causal\s+effect\b",
        r"\bHigh[\s\-]Price\s+Durables\b",
        r"\bproves\s+that\b",
    ]
    for pat in forbidden_patterns:
        assert not re.search(pat, md, re.IGNORECASE), f"Forbidden referee-flagged overclaim {pat!r} found in manuscript!"


def test_references_100_percent_cited_and_crossref_verified() -> None:
    md = (BASE_DIR / "manuscript_f7_boost.md").read_text(encoding="utf-8")
    refs = json.loads((BASE_DIR / "results" / "06_verified_references.json").read_text(encoding="utf-8"))
    assert refs["n_crossref_verified"] == 20

    body_text, ref_section = md.split("## References", maxsplit=1)

    for jref in refs["journal_references"]:
        assert jref["http_status"] == 200
        assert jref["doi"] in ref_section, f"Verified DOI {jref['doi']} missing from References!"
        first_surname = jref["authors"][0].split(",")[0].strip()
        assert first_surname in body_text, f"Reference author {first_surname} ({jref['key']}) not cited in body!"

    for needle in ("Amazon.com, Inc. v. CPSC", "U.S. CPSC 2024", "U.S. CPSC 2025", "Bolanos et al. 2025", "Consumer Federation of America 2025"):
        assert needle in body_text, f"Official/policy reference {needle!r} not cited in body!"

    ref_nums = [int(m.group(1)) for m in re.finditer(r"^(\d+)\.\s+", ref_section, re.MULTILINE)]
    assert ref_nums == list(range(1, 26)), f"Expected references 1..25, found {ref_nums}"


# ---------------------------------------------------------------------------
# 4. Math Renderer, Zero-NaN Tables, 5 Figures, Zero-Leak PDF, & SHA256SUMS
# ---------------------------------------------------------------------------
def test_tex_to_html_escaped_underscores_no_nested_sub() -> None:
    rendered = _tex_to_html(r"\beta_{\text{Mkt\_FD\_China}} - \log(1 + \text{clean\_injuries})")
    assert "<sub>China</sub>" not in rendered
    assert "<sub>injuries</sub>" not in rendered
    assert "&#95;" in rendered


def test_zero_nan_tables_and_figures_and_pdf() -> None:
    tbl_dir = BASE_DIR / "tables"
    csvs = sorted(tbl_dir.glob("*.csv"))
    assert len(csvs) >= 8, f"Expected >= 8 CSV tables, found {len(csvs)}"
    for cp in csvs:
        df_t = pd.read_csv(cp, keep_default_na=False)
        assert len(df_t) > 0
        bad = int(df_t.astype(str).apply(lambda s: s.str.lower().isin(["nan", "none", "null"])).sum().sum())
        assert bad == 0, f"NaN/null string found in {cp.name}"

    expected_figs = [
        "fig1_regime_emergence_and_diffusion",
        "fig2_theory_equilibrium_and_archetype_gaps",
        "fig3_robustness_forest_and_platforms",
        "fig4_amazon_enforcement_ramp",
        "fig5_safety_hazwaste_and_infrastructure",
    ]
    for stem in expected_figs:
        png = BASE_DIR / "figures" / f"{stem}.png"
        pdf_f = BASE_DIR / "figures" / f"{stem}.pdf"
        assert png.exists() and png.stat().st_size > 50_000, f"Missing/tiny PNG: {png}"
        assert pdf_f.exists() and pdf_f.stat().st_size > 10_000, f"Missing/tiny PDF: {pdf_f}"

    pdf_path = BASE_DIR / "manuscript_f7_boost.pdf"
    assert pdf_path.exists() and pdf_path.stat().st_size > 1_000_000
    n_pages, leaks = verify_pdf_zero_leaks(pdf_path)
    assert n_pages >= 10
    assert leaks == [], f"Leaked tokens in compiled PDF: {leaks}"


def test_sha256_manifest_live_integrity() -> None:
    sums_path = BASE_DIR / "SHA256SUMS.json"
    assert sums_path.exists(), "SHA256SUMS.json missing!"
    manifest = json.loads(sums_path.read_text(encoding="utf-8"))
    assert len(manifest) >= 20
    for rel_path, expected_hash in manifest.items():
        fp = BASE_DIR / rel_path
        assert fp.exists(), f"Manifest file missing: {rel_path}"
        actual_hash = _sha256(fp)
        assert actual_hash == expected_hash, f"SHA-256 mismatch for {rel_path}: expected {expected_hash}, got {actual_hash}"
