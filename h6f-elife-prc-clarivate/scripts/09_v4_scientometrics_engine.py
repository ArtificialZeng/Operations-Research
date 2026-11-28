"""Step 9 (v4): Unified Scientometrics Original Research Econometric Engine.

Integrates all validated v3 logic with mandatory v4 peer-review upgrades:
  1. Look-Ahead Covariate Leakage Audit:
     - Reproduces exact v3 benchmark (N = 2,285 VoRs; 368/2,285 max_authors > v1_authors;
       -14.03% -> -13.74% [-18.97%, -8.18%] when replacing max_authors with frozen v1_authors).
     - Estimates full strictly-frozen v1-at-publication specification (v1_n_authors +
       v1_primary_subject + v1_quarter/v1_month + strictly pre-v1 citations) across the
       crossed 2 x 2 (Initial vs Final assessment x Initial vs VoR quarter clock) matrix.
  2. Equal-Length Fixed-Window Citation Validation INCLUDING Non-VoR Reviewed Preprints:
     - Side-by-side PPML (subject-clustered CR1, G=17-18) across:
       (a) ALL mature 2023-2024 v1 reviewed preprints (N = 2,653),
       (b) VoR-only subsample (N = 2,315),
       (c) Non-VoR-only subsample (N = 338, both v1_subj x v1_quarter & v1_subj x v1_year FE),
       (d) Pooled All-v1 with explicit is_vor * v1_low interaction test,
       (e) Incremental predictive power (Poisson deviance reduction & pseudo-R2 gain of v1
           assessments over v1-only metadata), plus 18-subject LOSO.
  3. Onsite Readership Predictive Associations (Untruncated v1 >= 2023-11, N = 1,852):
     - Early 3-calendar-bin views/downloads (controlling for v1_posting_day) & cumulative totals.
  4. Public Revision, Rating Upgrade, VoR Conversion & Readership Trajectories:
     - Exact distinction: 842/964 public revisions vs 793/964 VoR conversion vs 644/964 (66.8%
       unconditional) / 644/793 (81.2% VoR-conditional) upgrades vs 621/964 (64.4%) / 621/793
       (78.3%) Solid+ upgrades; 325.4d mean v1->VoR calendar lag; 192/216 (88.9%) final <Solid
       VoRs posted public revisions (Apr 2023+ cohort).
     - Upgrade-to-Solid+ observational predictive associations with exact 95% CIs, exact
       multiplicative TOST bounds (±15% & ±20%), clean local VoR event study (t = -3..+6),
       and balanced 22-month version-release associations.
  5. Supplementary Information Indexing-Shock Explorations (Dec 10, 2024 WoS & Scopus):
     - Explicit disclosure of 166/514 early-cohort 450d VoRs crossing Dec 10, 2024, Aalen-Johansen
       competing risks across 4 cutoffs (Nov 20, Dec 10, Dec 19, Jan 1), and subject-adjusted
       complete fixed-horizon LPMs (450d final <Solid -2.76 pp [-7.54, +2.02]; public revision
       -3.47 pp [-10.84, +3.90]) confirming no established causal policy effect.

Outputs:
  - results/09_v4_scientometrics_results.json
  - tables/table_v4_1_audit_and_crossed_clock.csv
  - tables/table_v4_2_all_vor_nonvor_equal_window.csv
  - tables/table_v4_3_onsite_readership_predictive.csv
  - tables/table_v4_4_revision_upgrade_and_trajectories.csv
  - tables/table_s1_indexing_cohort_exploratory.csv
"""
from __future__ import annotations

import hashlib
import json
import runpy
import time
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"

METHODS = runpy.run_path(str(BASE_DIR / "scripts/04_pillar1_2_revision_and_attention.py"))
fe_ppml_cr1 = METHODS["fe_ppml_cr1"]
fe_ols_cr1 = METHODS["fe_ols_cr1"]
compute_km_and_aalen_johansen = METHODS["compute_km_and_aalen_johansen"]
bootstrap_aj_contrast = METHODS["bootstrap_aj_contrast"]

FREEZE = pd.Timestamp("2026-11-25")
POLICY = pd.Timestamp("2024-12-10")
PRE_END = pd.Timestamp("2024-10-01")
HORIZONS = (365, 450, 540)


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_lf(path: Path, obj: object) -> str:
    txt = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(txt.encode("utf-8"))
    return sha256_bytes(path)


def add_assessment_dummies(frame: pd.DataFrame, tag: str) -> list[str]:
    strength = frame[f"{tag}_str_min"]
    significance = frame[f"{tag}_sig_rank"]
    names = [f"{tag}_{k}" for k in ("low", "conv", "high", "imp", "fund")]
    frame[names[0]] = strength.le(2).astype(float)
    frame[names[1]] = strength.eq(4).astype(float)
    frame[names[2]] = strength.ge(5).astype(float)
    frame[names[3]] = (significance.ge(3.0) & significance.lt(4.0)).astype(float)
    frame[names[4]] = significance.ge(4.0).astype(float)
    return names


def extract_term(fit: dict, key: str) -> dict:
    if "params" not in fit or key not in fit["params"]:
        return {"error": fit.get("error", f"missing_{key}"), "n": fit.get("n", 0)}
    return {"n": int(fit["n"]), "G": int(fit["G"]), "M_fe": int(fit.get("M_fe", 0)), **fit["params"][key]}


def multiplicative_tost(beta: float, se: float, df_t: int, margins: tuple[float, ...] = (0.15, 0.20)) -> dict:
    """Exact TOST equivalence p-values for exact relative bounds [log(1 - m), log(1 + m)]."""
    out = {}
    for m in margins:
        p_lo = float(stats.t.sf((beta - np.log1p(-m)) / se, df=max(df_t, 1)))
        p_hi = float(stats.t.cdf((beta - np.log1p(m)) / se, df=max(df_t, 1)))
        out[f"tost_pm{round(100 * m)}"] = float(max(p_lo, p_hi))
    return out


def poisson_incremental_deviance(
    df: pd.DataFrame,
    y_col: str,
    base_cols: list[str],
    add_cols: list[str],
    fe_col: str,
) -> dict:
    """Measure incremental predictive value of v1 assessments via Poisson deviance & McFadden pseudo-R2."""
    all_x = list(dict.fromkeys(base_cols + add_cols))
    sub = df[list(dict.fromkeys([y_col] + all_x + [fe_col]))].dropna().copy()
    sub = sub[sub[y_col] >= 0].copy()
    sub = sub[sub.groupby(fe_col)[y_col].transform("sum") > 0].copy()
    vc = sub[fe_col].value_counts()
    sub = sub[sub[fe_col].isin(vc[vc >= 2].index)].copy()

    fe_d = pd.get_dummies(sub[fe_col], prefix="fe", drop_first=False, dtype=float)
    y = sub[y_col].astype(float)
    X_null = np.ones((len(sub), 1), dtype=float)
    X_base = pd.concat([sub[base_cols].astype(float), fe_d], axis=1)
    X_full = pd.concat([sub[all_x].astype(float), fe_d], axis=1)

    m_null = sm.GLM(y, X_null, family=sm.families.Poisson()).fit(maxiter=120)
    m_base = sm.GLM(y, X_base, family=sm.families.Poisson()).fit(maxiter=120)
    m_full = sm.GLM(y, X_full, family=sm.families.Poisson()).fit(maxiter=120)

    dev_null = float(m_null.deviance)
    dev_base = float(m_base.deviance)
    dev_full = float(m_full.deviance)
    lr_stat = float(max(dev_base - dev_full, 0.0))
    df_diff = len(add_cols)
    p_lr = float(stats.chi2.sf(lr_stat, df=df_diff))
    r2_base = float(1.0 - dev_base / dev_null)
    r2_full = float(1.0 - dev_full / dev_null)
    return {
        "n": len(sub),
        "M_fe": int(sub[fe_col].nunique()),
        "deviance_null": round(dev_null, 2),
        "deviance_v1_meta_only": round(dev_base, 2),
        "deviance_with_v1_assessments": round(dev_full, 2),
        "deviance_reduction": round(lr_stat, 2),
        "df_added": int(df_diff),
        "lr_p_value": p_lr,
        "pseudo_r2_v1_meta_only": round(r2_base, 4),
        "pseudo_r2_with_v1_assessments": round(r2_full, 4),
        "delta_pseudo_r2_pp": round(100.0 * (r2_full - r2_base), 3),
        "share_of_residual_deviance_explained_pct": round(100.0 * lr_stat / max(dev_base, 1e-9), 3),
    }


def intersected_clock_sample(frame: pd.DataFrame, y_col: str, req_cols: list[str], clock_a: str, clock_b: str) -> pd.DataFrame:
    """Hold exact sample fixed across both time clocks (positive, non-singleton cells under both)."""
    sub = frame.dropna(subset=[y_col, *req_cols, clock_a, clock_b]).copy()
    while True:
        n_prev = len(sub)
        for clk in (clock_a, clock_b):
            grp = sub.groupby(clk)[y_col]
            sub = sub[grp.transform("size").ge(2) & grp.transform("sum").gt(0)]
        if len(sub) == n_prev:
            break
    return sub


def main() -> None:
    t0 = time.time()
    print("=== STEP 9 (v4): SCIENTOMETRICS ORIGINAL RESEARCH ECONOMETRIC ENGINE ===", flush=True)
    RES_DIR.mkdir(parents=True, exist_ok=True)
    TBL_DIR.mkdir(parents=True, exist_ok=True)

    panel = pd.read_csv(DATA_DIR / "h6f_boost_v1_panel.csv.gz", dtype={"eid": str}, parse_dates=["v1_date", "fin_date", "revision_dt"])
    mat = panel[panel["v1_date"].dt.year.isin([2023, 2024]) & panel["v1_str_min"].notna()].copy()
    v1_lbls = add_assessment_dummies(mat, "v1")
    fin_lbls = add_assessment_dummies(mat, "fin")

    vor = mat[mat["is_vor"].eq(1) & mat["fin_str_min"].notna()].copy()
    nonvor = mat[mat["is_vor"].eq(0)].copy()

    cov_v1_strict = ["v1_age_days", "log_v1_authors", "log1p_pre_before_v1"]
    cov_v1_preprint_only = ["v1_age_days", "log_v1_authors", "log1p_pre_before_v1_preprint_only"]
    cov_leaked_max = ["v1_age_days", "log_authors_max_leaked", "log1p_pre_before_v1"]

    # =========================================================================
    # 1. COVARIATE LEAKAGE AUDIT & CROSSED 2x2 CLOCK/ASSESSMENT MATRIX
    # =========================================================================
    s_bench_post = intersected_clock_sample(vor, "oa_post_v1_cites", cov_leaked_max, "fin_subj_v1q", "fin_subj_finq")
    s_bench_next = intersected_clock_sample(vor, "oa_next_full_year", cov_leaked_max, "fin_subj_v1q", "fin_subj_finq")
    n_leak_auth_2285 = int((s_bench_post["cr_n_authors_max"] > s_bench_post["v1_n_authors"]).sum())
    n_leak_subj_2285 = int((s_bench_post["v1_primary_subject"] != s_bench_post["fin_primary_subject"]).sum())

    # Exact N=2,285 reviewer-benchmark parity (matching v3's inclusion of eid 87414 with missing v1_str_min)
    mat_v3_all = panel[panel["v1_date"].dt.year.isin([2023, 2024])].copy()
    v1_lbls_v3 = add_assessment_dummies(mat_v3_all, "v1")
    vor_v3 = mat_v3_all[mat_v3_all["is_vor"].eq(1) & mat_v3_all["fin_str_min"].notna()].copy()
    s_rev_2285 = intersected_clock_sample(vor_v3, "oa_post_v1_cites", cov_leaked_max, "fin_subj_v1q", "fin_subj_finq")
    reviewer_2285_parity = {
        "n": len(s_rev_2285),
        "n_max_authors_gt_v1": int((s_rev_2285["cr_n_authors_max"] > s_rev_2285["v1_n_authors"]).sum()),
        "leaked_max_authors": extract_term(
            fe_ppml_cr1(s_rev_2285, "oa_post_v1_cites", v1_lbls_v3 + cov_leaked_max, "fin_subj_v1q", "fin_primary_subject"), "v1_low"
        ),
        "frozen_v1_authors": extract_term(
            fe_ppml_cr1(s_rev_2285, "oa_post_v1_cites", v1_lbls_v3 + cov_v1_strict, "fin_subj_v1q", "fin_primary_subject"), "v1_low"
        ),
        "frozen_v1_authors_finq_clock": extract_term(
            fe_ppml_cr1(s_rev_2285, "oa_post_v1_cites", v1_lbls_v3 + cov_v1_strict, "fin_subj_finq", "fin_primary_subject"), "v1_low"
        ),
    }

    # Exact reviewer parity benchmark (fin_subject FE, swapping max_authors -> v1_authors) on clean non-missing v1_str_min (N=2,284)
    bench_crossed: dict = {}
    for y_col, smp in (("oa_post_v1_cites", s_bench_post), ("oa_next_full_year", s_bench_next)):
        bench_crossed[y_col] = {
            "leaked_max_authors_v1_v1q": extract_term(
                fe_ppml_cr1(smp, y_col, v1_lbls + cov_leaked_max, "fin_subj_v1q", "fin_primary_subject"), "v1_low"
            ),
            "frozen_v1_authors_v1_v1q": extract_term(
                fe_ppml_cr1(smp, y_col, v1_lbls + cov_v1_strict, "fin_subj_v1q", "fin_primary_subject"), "v1_low"
            ),
            "frozen_v1_authors_v1_finq": extract_term(
                fe_ppml_cr1(smp, y_col, v1_lbls + cov_v1_strict, "fin_subj_finq", "fin_primary_subject"), "v1_low"
            ),
            "frozen_v1_authors_fin_v1q": extract_term(
                fe_ppml_cr1(smp, y_col, fin_lbls + cov_v1_strict, "fin_subj_v1q", "fin_primary_subject"), "fin_low"
            ),
            "frozen_v1_authors_fin_finq": extract_term(
                fe_ppml_cr1(smp, y_col, fin_lbls + cov_v1_strict, "fin_subj_finq", "fin_primary_subject"), "fin_low"
            ),
        }

    # STRICTLY FROZEN v1-at-publication 2x2 crossed matrix (BOTH v1_n_authors AND v1_primary_subject frozen!)
    s_strict_post = intersected_clock_sample(vor, "oa_post_v1_cites", cov_v1_strict, "v1_subj_v1q", "v1_subj_finq")
    s_strict_next = intersected_clock_sample(vor, "oa_next_full_year", cov_v1_strict, "v1_subj_v1q", "v1_subj_finq")
    strict_crossed: dict = {}
    for y_col, smp in (("oa_post_v1_cites", s_strict_post), ("oa_next_full_year", s_strict_next)):
        strict_crossed[y_col] = {
            "v1_v1q": extract_term(fe_ppml_cr1(smp, y_col, v1_lbls + cov_v1_strict, "v1_subj_v1q", "v1_primary_subject"), "v1_low"),
            "v1_finq": extract_term(fe_ppml_cr1(smp, y_col, v1_lbls + cov_v1_strict, "v1_subj_finq", "v1_primary_subject"), "v1_low"),
            "fin_v1q": extract_term(fe_ppml_cr1(smp, y_col, fin_lbls + cov_v1_strict, "v1_subj_v1q", "v1_primary_subject"), "fin_low"),
            "fin_finq": extract_term(fe_ppml_cr1(smp, y_col, fin_lbls + cov_v1_strict, "v1_subj_finq", "v1_primary_subject"), "fin_low"),
        }

    # Granular monthly clock sensitivity (v1_primary_subject x v1_month FE) & preprint-only pre-v1 cites sensitivity
    clock_sens = {
        "all_v1_post_monthly_fe": extract_term(fe_ppml_cr1(mat, "oa_post_v1_cites", v1_lbls + cov_v1_strict, "v1_subj_v1m", "v1_primary_subject"), "v1_low"),
        "all_v1_next_yr_monthly_fe": extract_term(fe_ppml_cr1(mat, "oa_next_full_year", v1_lbls + cov_v1_strict, "v1_subj_v1m", "v1_primary_subject"), "v1_low"),
        "vor_post_monthly_fe": extract_term(fe_ppml_cr1(vor, "oa_post_v1_cites", v1_lbls + cov_v1_strict, "v1_subj_v1m", "v1_primary_subject"), "v1_low"),
        "vor_next_yr_monthly_fe": extract_term(fe_ppml_cr1(vor, "oa_next_full_year", v1_lbls + cov_v1_strict, "v1_subj_v1m", "v1_primary_subject"), "v1_low"),
        "all_v1_post_preprint_only_ctrl": extract_term(fe_ppml_cr1(mat, "oa_post_v1_cites", v1_lbls + cov_v1_preprint_only, "v1_subj_v1q", "v1_primary_subject"), "v1_low"),
        "vor_post_preprint_only_ctrl": extract_term(fe_ppml_cr1(vor, "oa_post_v1_cites", v1_lbls + cov_v1_preprint_only, "v1_subj_v1q", "v1_primary_subject"), "v1_low"),
    }

    print(
        f"[Covariate Audit] N={len(s_bench_post)} | max_authors>v1_authors: {n_leak_auth_2285}/{len(s_bench_post)} | "
        f"fin_subj!=v1_subj: {n_leak_subj_2285}/{len(s_bench_post)} | "
        f"Old={bench_crossed['oa_post_v1_cites']['leaked_max_authors_v1_v1q']['pct']:+.2f}% -> "
        f"v1_auth={bench_crossed['oa_post_v1_cites']['frozen_v1_authors_v1_v1q']['pct']:+.2f}% "
        f"[{bench_crossed['oa_post_v1_cites']['frozen_v1_authors_v1_v1q']['pct_ci95_lo']:+.2f}%, "
        f"{bench_crossed['oa_post_v1_cites']['frozen_v1_authors_v1_v1q']['pct_ci95_hi']:+.2f}%] | "
        f"Strict(v1_auth+v1_subj)={strict_crossed['oa_post_v1_cites']['v1_v1q']['pct']:+.2f}%",
        flush=True,
    )

    # =========================================================================
    # 2. EQUAL-WINDOW CITATION VALIDATION: ALL-v1 vs VoR-ONLY vs NON-VoR-ONLY
    # =========================================================================
    nonvor["v1_subj_yr"] = nonvor["v1_primary_subject"] + "__" + nonvor["v1_year"].astype(str)
    mat["v1_subj_yr"] = mat["v1_primary_subject"] + "__" + mat["v1_year"].astype(str)
    mat["vor_x_v1_low"] = mat["is_vor"] * mat["v1_low"]

    sample_validation: dict = {}
    outcomes_val = [
        ("oa_post_v1_cites", "Post-v1 OA Citations (eLife DOI max)"),
        ("oa_next_full_year", "Next Full-Calendar-Year OA Citations (eLife DOI max)"),
        ("oa_post_v1_all", "Post-v1 OA Citations (eLife + Preprint max)"),
        ("oa_next_full_year_all", "Next Full-Calendar-Year OA Citations (eLife + Preprint max)"),
        ("cr_cites", "Crossref Citations (Max Across eLife DOIs)"),
        ("pv_total", "Cumulative eLife Page-Views"),
        ("dl_total", "Cumulative eLife Downloads"),
    ]
    for grp_key, frame, fe_col in [
        ("all_v1", mat, "v1_subj_v1q"),
        ("vor_only", vor, "v1_subj_v1q"),
        ("non_vor_only_subj_q", nonvor, "v1_subj_v1q"),
        ("non_vor_only_subj_yr", nonvor, "v1_subj_yr"),
    ]:
        sample_validation[grp_key] = {}
        for y_col, _ in outcomes_val:
            sub = frame[frame["has_metrics"] == 1] if y_col in ("pv_total", "dl_total") else frame
            fit = fe_ppml_cr1(sub, y_col, v1_lbls + cov_v1_strict, fe_col, "v1_primary_subject")
            sample_validation[grp_key][y_col] = {
                "v1_low": extract_term(fit, "v1_low"),
                "v1_conv": extract_term(fit, "v1_conv"),
                "v1_high": extract_term(fit, "v1_high"),
                "v1_imp": extract_term(fit, "v1_imp"),
                "v1_fund": extract_term(fit, "v1_fund"),
                "mean_y": round(float(sub[y_col].dropna().mean()), 3),
                "median_y": round(float(sub[y_col].dropna().median()), 2),
            }

    # Formal interaction test on pooled All-v1: does v1_low slope differ significantly between VoR and Non-VoR?
    vor_interaction = {}
    for y_col in ("oa_post_v1_cites", "oa_next_full_year", "oa_next_full_year_all", "cr_cites", "dl_total"):
        sub = mat[mat["has_metrics"] == 1] if y_col == "dl_total" else mat
        fit = fe_ppml_cr1(sub, y_col, ["v1_low", "is_vor", "vor_x_v1_low"] + v1_lbls[1:] + cov_v1_strict, "v1_subj_v1q", "v1_primary_subject")
        vor_interaction[y_col] = {
            "v1_low_non_vor": extract_term(fit, "v1_low"),
            "is_vor_solid": extract_term(fit, "is_vor"),
            "vor_x_v1_low": extract_term(fit, "vor_x_v1_low"),
        }

    # Incremental predictive power (Poisson deviance reduction of adding v1 assessment terms to v1 metadata)
    incremental_power = {
        "all_v1_oa_post_v1": poisson_incremental_deviance(mat, "oa_post_v1_cites", cov_v1_strict, v1_lbls, "v1_subj_v1q"),
        "all_v1_oa_next_yr": poisson_incremental_deviance(mat, "oa_next_full_year", cov_v1_strict, v1_lbls, "v1_subj_v1q"),
        "vor_only_oa_post_v1": poisson_incremental_deviance(vor, "oa_post_v1_cites", cov_v1_strict, v1_lbls, "v1_subj_v1q"),
        "vor_only_oa_next_yr": poisson_incremental_deviance(vor, "oa_next_full_year", cov_v1_strict, v1_lbls, "v1_subj_v1q"),
    }

    # 18-subject LOSO on All-v1 next-full-year and VoR-only post-v1 (strictly frozen v1 covariates!)
    loso_v4 = {"all_v1_next_yr": [], "all_v1_post_v1": [], "vor_post_v1": []}
    for subj in sorted(mat["v1_primary_subject"].unique()):
        for key, frame, y_col in [
            ("all_v1_next_yr", mat[mat["v1_primary_subject"] != subj], "oa_next_full_year"),
            ("all_v1_post_v1", mat[mat["v1_primary_subject"] != subj], "oa_post_v1_cites"),
            ("vor_post_v1", vor[vor["v1_primary_subject"] != subj], "oa_post_v1_cites"),
        ]:
            fit = fe_ppml_cr1(frame, y_col, v1_lbls + cov_v1_strict, "v1_subj_v1q", "v1_primary_subject")
            t = extract_term(fit, "v1_low")
            loso_v4[key].append({"dropped_subject": subj, "pct": round(float(t["pct"]), 2), "p": float(t["p"])})

    print(
        f"[Equal-Window Validation] ALL-v1 next_yr={sample_validation['all_v1']['oa_next_full_year']['v1_low']['pct']:+.2f}% "
        f"(p={sample_validation['all_v1']['oa_next_full_year']['v1_low']['p']:.2e}) | "
        f"VoR-only={sample_validation['vor_only']['oa_next_full_year']['v1_low']['pct']:+.2f}% | "
        f"Non-VoR={sample_validation['non_vor_only_subj_q']['oa_next_full_year']['v1_low']['pct']:+.2f}% "
        f"(post_v1={sample_validation['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['pct']:+.2f}%, p={sample_validation['non_vor_only_subj_q']['oa_post_v1_cites']['v1_low']['p']:.4f})",
        flush=True,
    )

    # =========================================================================
    # 3. ONSITE EARLY & CUMULATIVE READERSHIP PREDICTIVE ASSOCIATIONS (N=1,852)
    # =========================================================================
    early = mat[mat["has_complete_monthly_metrics"].eq(1)].copy()
    early_attention: dict = {}
    for y_col in ("pv_first_3m", "dl_first_3m", "pv_total", "dl_total"):
        fit = fe_ppml_cr1(early, y_col, v1_lbls + cov_v1_strict + ["v1_posting_day"], "v1_subj_v1q", "v1_primary_subject")
        early_attention[y_col] = {
            "v1_low": extract_term(fit, "v1_low"),
            "v1_conv": extract_term(fit, "v1_conv"),
            "v1_high": extract_term(fit, "v1_high"),
            "v1_imp": extract_term(fit, "v1_imp"),
            "v1_fund": extract_term(fit, "v1_fund"),
        }

    # Also full mature cohort (N=2,653) lifetime totals for completeness
    lifetime_attention_all_mature: dict = {}
    for y_col in ("pv_total", "dl_total"):
        fit = fe_ppml_cr1(mat[mat["has_metrics"] == 1], y_col, v1_lbls + cov_v1_strict, "v1_subj_v1q", "v1_primary_subject")
        lifetime_attention_all_mature[y_col] = {
            "v1_low": extract_term(fit, "v1_low"),
            "v1_imp": extract_term(fit, "v1_imp"),
            "v1_fund": extract_term(fit, "v1_fund"),
        }

    # =========================================================================
    # 4. PUBLIC REVISION, RATING UPGRADE, VoR CONVERSION & TRAJECTORIES
    # =========================================================================
    tiers = [
        ("v1_Incomp_Inad", lambda d: d["v1_str_min"] <= 2),
        ("v1_Solid", lambda d: d["v1_str_min"] == 3),
        ("v1_Convincing", lambda d: d["v1_str_min"] == 4),
        ("v1_Compel_Excep", lambda d: d["v1_str_min"] >= 5),
    ]
    funnel_by_tier: dict = {}
    for lbl, fn in tiers:
        g = mat[fn(mat)]
        vg = g[g["is_vor"] == 1]
        up = vg[vg["str_upgraded"] == 1]
        up_sol = vg[vg["str_upgraded_to_solid"] == 1]
        unch = vg[vg["str_upgraded"] == 0]
        rp = g[g["is_vor"] == 0]
        funnel_by_tier[lbl] = {
            "n_total": len(g),
            "n_posted_revision": int(g["posted_revision"].sum()),
            "pct_posted_revision": round(float(100.0 * g["posted_revision"].mean()), 2),
            "n_vor": len(vg),
            "pct_vor": round(float(100.0 * len(vg) / max(len(g), 1)), 2),
            "n_vor_upgraded_any": len(up),
            "pct_all_upgraded_any": round(float(100.0 * len(up) / max(len(g), 1)), 2),
            "pct_vor_upgraded_any": round(float(100.0 * len(up) / max(len(vg), 1)), 2),
            "n_vor_upgraded_to_solid": len(up_sol),
            "pct_all_upgraded_to_solid": round(float(100.0 * len(up_sol) / max(len(g), 1)), 2),
            "pct_vor_upgraded_to_solid": round(float(100.0 * len(up_sol) / max(len(vg), 1)), 2),
            "n_vor_unchanged": len(unch),
            "n_vor_unchanged_with_revision": int(unch["posted_revision"].sum()),
            "n_rp_only": len(rp),
            "n_rp_only_with_revision": int(rp["posted_revision"].sum()),
            "mean_rev_lag_up_days": round(float(up["rev_lag_days"].mean()), 1) if len(up) else 0.0,
            "med_rev_lag_up_days": round(float(up["rev_lag_days"].median()), 1) if len(up) else 0.0,
            "mean_rev_lag_unch_days": round(float(unch["rev_lag_days"].mean()), 1) if len(unch) else 0.0,
        }

    # Exact upgrade-to-Solid+ predictive association inside mature v1 <Solid VoRs (strictly frozen v1 covariates!)
    low_vor = vor[vor["v1_str_min"].le(2)].copy()
    low_vor["upgraded_solid"] = low_vor["fin_str_min"].ge(3).astype(float)
    x_up_strict = ["upgraded_solid", "v1_sig_rank", *cov_v1_strict]
    x_up_bench = ["upgraded_solid", "v1_sig_rank", *cov_leaked_max]
    x_up_ver = ["upgraded_solid", "v1_sig_rank", *cov_v1_strict, "cr_n_versions"]

    upgrade_models: dict = {
        # Exact v3 benchmark parity (leaked max authors + fin_subject FE -> +3.18% [-10.72%, +19.25%])
        "bench_v3_parity_oa_post_v1": extract_term(
            fe_ppml_cr1(low_vor, "oa_post_v1_cites", x_up_bench, "fin_subj_v1q", "fin_primary_subject"), "upgraded_solid"
        ),
        # Stepwise covariate decomposition: frozen v1 authors only (keeping fin_subject FE)
        "v1_authors_fin_subj_oa_post_v1": extract_term(
            fe_ppml_cr1(low_vor, "oa_post_v1_cites", x_up_strict, "fin_subj_v1q", "fin_primary_subject"), "upgraded_solid"
        ),
        # Strictly frozen v1 covariates (v1_n_authors + v1_primary_subject!)
        "strict_v1_oa_post_v1": extract_term(
            fe_ppml_cr1(low_vor, "oa_post_v1_cites", x_up_strict, "v1_subj_v1q", "v1_primary_subject"), "upgraded_solid"
        ),
        "strict_v1_oa_next_yr": extract_term(
            fe_ppml_cr1(low_vor, "oa_next_full_year", x_up_strict, "v1_subj_v1q", "v1_primary_subject"), "upgraded_solid"
        ),
        "strict_v1_cr_cites": extract_term(
            fe_ppml_cr1(low_vor, "cr_cites", x_up_strict, "v1_subj_v1q", "v1_primary_subject"), "upgraded_solid"
        ),
        "strict_v1_pv_total_ols": extract_term(
            fe_ols_cr1(low_vor[low_vor["has_metrics"] == 1], "log1p_pv_total", x_up_strict, "v1_subj_v1q", "v1_primary_subject", wcb_target="upgraded_solid"),
            "upgraded_solid",
        ),
        "strict_v1_dl_total_ols": extract_term(
            fe_ols_cr1(low_vor[low_vor["has_metrics"] == 1], "log1p_dl_total", x_up_strict, "v1_subj_v1q", "v1_primary_subject", wcb_target="upgraded_solid"),
            "upgraded_solid",
        ),
    }

    for k in ("bench_v3_parity_oa_post_v1", "strict_v1_oa_post_v1", "strict_v1_oa_next_yr", "strict_v1_cr_cites"):
        m = upgrade_models[k]
        m.update(multiplicative_tost(m["beta"], m["se"], m["G"] - 1))

    # Clean local VoR event study (t = -3..+6) & balanced 22m version-release associations (strictly v1 covariates!)
    clean_ev = low_vor[low_vor["has_clean_vor_ev"].eq(1)].copy()
    clean_cm = low_vor[low_vor["has_complete_monthly_metrics"].eq(1)].copy()
    solid_cm = vor[(vor["v1_str_min"] == 3) & (vor["has_complete_monthly_metrics"].eq(1))].copy()
    solid_cm["upgraded_any"] = solid_cm["str_upgraded"].astype(float)

    ev_controls = ["upgraded_solid", "v1_sig_rank", "rev_lag_days", *cov_v1_strict]
    for y_col in ("dlog_pv_ev_m0", "dlog_pv_ev_p16", "dlog_dl_ev_m0", "dlog_dl_ev_p16"):
        upgrade_models[f"strict_v1_{y_col}"] = extract_term(
            fe_ols_cr1(clean_ev, y_col, ev_controls, "v1_subj_v1q", "v1_primary_subject", wcb_target="upgraded_solid"),
            "upgraded_solid",
        )
    upgrade_models["raw_ev_m0_summary"] = {
        "n_clean_ev": len(clean_ev),
        "pv_m0_upgraded_mean": round(float(clean_ev.loc[clean_ev["upgraded_solid"] == 1, "dlog_pv_ev_m0"].mean()), 3),
        "pv_m0_unchanged_mean": round(float(clean_ev.loc[clean_ev["upgraded_solid"] == 0, "dlog_pv_ev_m0"].mean()), 3),
        "dl_m0_upgraded_mean": round(float(clean_ev.loc[clean_ev["upgraded_solid"] == 1, "dlog_dl_ev_m0"].mean()), 3),
        "dl_m0_unchanged_mean": round(float(clean_ev.loc[clean_ev["upgraded_solid"] == 0, "dlog_dl_ev_m0"].mean()), 3),
    }

    # Monthly rate DiD (untruncated v1 >= 2023-11) & 22m version-release associations
    upgrade_models["strict_v1_rate_did_pv"] = extract_term(
        fe_ols_cr1(clean_cm, "delta_log_pv_rate", x_up_strict + ["n_months_post_vor"], "v1_subj_v1q", "v1_primary_subject", wcb_target="upgraded_solid"),
        "upgraded_solid",
    )
    upgrade_models["strict_v1_rate_did_dl"] = extract_term(
        fe_ols_cr1(clean_cm, "delta_log_dl_rate", x_up_strict + ["n_months_post_vor"], "v1_subj_v1q", "v1_primary_subject", wcb_target="upgraded_solid"),
        "upgraded_solid",
    )
    fit_ver_inc = fe_ols_cr1(clean_cm, "dlog_pv_12_21_vs_0_2", x_up_ver, "v1_subj_v1q", "v1_primary_subject", wcb_target="cr_n_versions")
    fit_ver_sol = fe_ols_cr1(
        solid_cm, "dlog_pv_12_21_vs_0_2", ["upgraded_any", "v1_sig_rank", *cov_v1_strict, "cr_n_versions"], "v1_subj_v1q", "v1_primary_subject", wcb_target="cr_n_versions"
    )
    upgrade_models["version_release_m12_21_incomp"] = {
        "upgraded_solid": extract_term(fit_ver_inc, "upgraded_solid"),
        "cr_n_versions": extract_term(fit_ver_inc, "cr_n_versions"),
    }
    upgrade_models["version_release_m12_21_solid"] = {
        "upgraded_any": extract_term(fit_ver_sol, "upgraded_any"),
        "cr_n_versions": extract_term(fit_ver_sol, "cr_n_versions"),
    }

    # Also VoR vs RP-only attention association inside mature v1 <Solid (N = 964)
    inc_all = mat[mat["v1_str_min"].le(2)].copy()
    upgrade_models["vor_vs_rp_incomp_pv_ols"] = extract_term(
        fe_ols_cr1(inc_all[inc_all["has_metrics"] == 1], "log1p_pv_total", ["is_vor", "v1_sig_rank", *cov_v1_strict], "v1_subj_v1q", "v1_primary_subject", wcb_target="is_vor"),
        "is_vor",
    )
    upgrade_models["vor_vs_rp_incomp_dl_ols"] = extract_term(
        fe_ols_cr1(inc_all[inc_all["has_metrics"] == 1], "log1p_dl_total", ["is_vor", "v1_sig_rank", *cov_v1_strict], "v1_subj_v1q", "v1_primary_subject", wcb_target="is_vor"),
        "is_vor",
    )

    print(
        f"[Upgrade Models] v3-parity={upgrade_models['bench_v3_parity_oa_post_v1']['pct']:+.2f}% "
        f"[{upgrade_models['bench_v3_parity_oa_post_v1']['pct_ci95_lo']:+.2f}%, {upgrade_models['bench_v3_parity_oa_post_v1']['pct_ci95_hi']:+.2f}%] | "
        f"Strict-v1={upgrade_models['strict_v1_oa_post_v1']['pct']:+.2f}% "
        f"[{upgrade_models['strict_v1_oa_post_v1']['pct_ci95_lo']:+.2f}%, {upgrade_models['strict_v1_oa_post_v1']['pct_ci95_hi']:+.2f}%] "
        f"(TOST ±15% p={upgrade_models['strict_v1_oa_post_v1']['tost_pm15']:.4f}, ±20% p={upgrade_models['strict_v1_oa_post_v1']['tost_pm20']:.4f})",
        flush=True,
    )

    # =========================================================================
    # 5. SUPPLEMENTARY INFORMATION: EXPLORATORY DEC 10, 2024 WoS & SCOPUS COHORT CHECKS
    # =========================================================================
    low_apr23 = panel[panel["v1_str_min"].le(2) & panel["v1_date"].ge("2023-04-01")].copy()
    final_low_apr23 = low_apr23[low_apr23["is_vor"].eq(1) & low_apr23["fin_str_min"].le(2)]
    assert not low_apr23[low_apr23["is_vor"].eq(1)]["fin_str_min"].isna().any()

    low_apr23["time_days"] = np.where(low_apr23["is_vor"].eq(1), low_apr23["rev_lag_days"], (FREEZE - low_apr23["v1_date"]).dt.days)
    low_apr23["event"] = np.where(low_apr23["is_vor"].eq(0), 0, np.where(low_apr23["fin_str_min"].ge(3), 1, 2))
    assert (low_apr23["time_days"] >= 0).all()

    pre = low_apr23[low_apr23["v1_date"].lt(PRE_END)]
    post = low_apr23[low_apr23["v1_date"].ge(POLICY)]
    grid = tuple(range(0, 541, 10))
    curves = {
        "pre": compute_km_and_aalen_johansen(pre["time_days"].to_numpy(float), pre["event"].to_numpy(int), HORIZONS, grid),
        "post": compute_km_and_aalen_johansen(post["time_days"].to_numpy(float), post["event"].to_numpy(int), HORIZONS, grid),
    }
    aj_cutoffs = {
        cut: bootstrap_aj_contrast(pre, low_apr23[low_apr23["v1_date"].ge(cut)], HORIZONS, B=1000, seed=2026)
        for cut in ("2024-11-20", "2024-12-10", "2024-12-19", "2025-01-01")
    }

    # Subject-adjusted complete fixed-horizon contrasts (both v1_primary_subject AND fin_primary_subject for full transparency!)
    fixed_horizon_strict: dict = {}
    fixed_horizon_v3_parity: dict = {}
    for horizon in HORIZONS:
        w = low_apr23[
            (low_apr23["v1_date"].lt(PRE_END) | low_apr23["v1_date"].ge(POLICY))
            & low_apr23["v1_date"].le(FREEZE - pd.Timedelta(days=horizon))
        ].copy()
        w["later_cohort"] = w["v1_date"].ge(POLICY).astype(float)
        ev_dur = w["time_days"].le(horizon)
        w["any_vor"] = (w["event"].ne(0) & ev_dur).astype(float)
        w["solid_vor"] = (w["event"].eq(1) & ev_dur).astype(float)
        w["lower_rated_vor"] = (w["event"].eq(2) & ev_dur).astype(float)
        w["observed_revision"] = (w["posted_revision"].eq(1) & w["revision_dt"].le(w["v1_date"] + pd.Timedelta(days=horizon))).astype(float)

        fixed_horizon_strict[str(horizon)] = {
            oc: extract_term(
                fe_ols_cr1(w, oc, ["later_cohort", "v1_sig_rank"], "v1_primary_subject", "v1_primary_subject", wcb_target="later_cohort"),
                "later_cohort",
            )
            for oc in ("any_vor", "solid_vor", "lower_rated_vor", "observed_revision")
        }
        fixed_horizon_v3_parity[str(horizon)] = {
            oc: extract_term(
                fe_ols_cr1(w, oc, ["later_cohort", "v1_sig_rank"], "fin_primary_subject", "fin_primary_subject", wcb_target="later_cohort"),
                "later_cohort",
            )
            for oc in ("any_vor", "solid_vor", "lower_rated_vor", "observed_revision")
        }

    pre_450_vors = int((pre["is_vor"].eq(1) & pre["time_days"].le(450)).sum())
    pre_450_vors_after_ann = int((pre["is_vor"].eq(1) & pre["time_days"].le(450) & pre["fin_date"].ge(POLICY)).sum())

    indexing_si = {
        "policy_announcement_date": "2024-12-10",
        "databases_affected": ["Web of Science (partial feed of Solid+ VoRs; JIF removal)", "Scopus (migration from Journals Collection to Preprints Collection)"],
        "pre_cohort_end_excl": "2024-10-01",
        "pre_n": len(pre),
        "post_n": len(post),
        "excluded_transition_n": int(len(low_apr23) - len(pre) - len(post)),
        "pre_450_vors": pre_450_vors,
        "pre_450_vors_after_announcement": pre_450_vors_after_ann,
        "pct_pre_450_vors_crossing_announcement": round(float(100.0 * pre_450_vors_after_ann / max(pre_450_vors, 1)), 1),
        "apr2023_lower_rated_vors": len(final_low_apr23),
        "apr2023_lower_rated_vors_with_posted_revision": int(final_low_apr23["posted_revision"].sum()),
        "apr2023_lower_rated_vors_with_revision_pct": round(float(100.0 * final_low_apr23["posted_revision"].mean()), 1),
        "aj_cutoffs": aj_cutoffs,
        "curves": curves,
        "fixed_horizon_strict_v1_subj": fixed_horizon_strict,
        "fixed_horizon_v3_parity_fin_subj": fixed_horizon_v3_parity,
    }

    print(
        f"[SI Indexing Cohort] Pre 450d VoRs crossing Dec 10={pre_450_vors_after_ann}/{pre_450_vors} | "
        f"Apr23+ Final <Solid VoRs with public rev={indexing_si['apr2023_lower_rated_vors_with_posted_revision']}/{indexing_si['apr2023_lower_rated_vors']} | "
        f"450d v3-parity <Solid={100*fixed_horizon_v3_parity['450']['lower_rated_vor']['beta']:+.2f} pp "
        f"[{100*fixed_horizon_v3_parity['450']['lower_rated_vor']['ci95_lo']:+.2f}, {100*fixed_horizon_v3_parity['450']['lower_rated_vor']['ci95_hi']:+.2f}] | "
        f"PubRev={100*fixed_horizon_v3_parity['450']['observed_revision']['beta']:+.2f} pp "
        f"[{100*fixed_horizon_v3_parity['450']['observed_revision']['ci95_lo']:+.2f}, {100*fixed_horizon_v3_parity['450']['observed_revision']['ci95_hi']:+.2f}]",
        flush=True,
    )

    # =========================================================================
    # WRITE PUBLICATION CSV TABLES (ZERO NaN!)
    # =========================================================================
    # Table V4-1: Covariate Audit & Crossed 2x2 Date-Clock / Assessment-Timing Sensitivity
    t1_rows = []
    for spec_grp, dct in [("Benchmark_FinSubj_Audit", bench_crossed), ("Strict_v1_Frozen_AuthorsAndSubj", strict_crossed)]:
        for y_col in ("oa_post_v1_cites", "oa_next_full_year"):
            for key, m in dct[y_col].items():
                t1_rows.append({
                    "specification_group": spec_grp,
                    "outcome": y_col,
                    "model_key": key,
                    "n_obs": int(m["n"]),
                    "n_clusters": int(m["G"]),
                    "beta": round(float(m["beta"]), 4),
                    "pct": round(float(m["pct"]), 2),
                    "pct_ci95_lo": round(float(m["pct_ci95_lo"]), 2),
                    "pct_ci95_hi": round(float(m["pct_ci95_hi"]), 2),
                    "se": round(float(m["se"]), 4),
                    "t_stat": round(float(m["t"]), 3),
                    "p_value": float(m["p"]),
                })
    p_t1 = TBL_DIR / "table_v4_1_audit_and_crossed_clock.csv"
    pd.DataFrame(t1_rows).to_csv(p_t1, index=False, lineterminator="\n")

    # Table V4-2: Equal-Window Validation Across All-v1 vs VoR-Only vs Non-VoR-Only (Strictly Frozen v1 Covariates)
    t2_rows = []
    for grp_key, grp_lbl in [
        ("all_v1", "All_Mature_v1_Preprints"),
        ("vor_only", "VoR_Subsample_Only"),
        ("non_vor_only_subj_q", "NonVoR_Subsample_SubjQuarterFE"),
        ("non_vor_only_subj_yr", "NonVoR_Subsample_SubjYearFE"),
    ]:
        for y_col, y_lbl in outcomes_val:
            m = sample_validation[grp_key][y_col]["v1_low"]
            t2_rows.append({
                "sample_group": grp_lbl,
                "outcome": y_col,
                "outcome_label": y_lbl,
                "n_obs": int(m["n"]),
                "n_clusters": int(m["G"]),
                "mean_outcome": sample_validation[grp_key][y_col]["mean_y"],
                "beta": round(float(m["beta"]), 4),
                "pct": round(float(m["pct"]), 2),
                "pct_ci95_lo": round(float(m["pct_ci95_lo"]), 2),
                "pct_ci95_hi": round(float(m["pct_ci95_hi"]), 2),
                "se": round(float(m["se"]), 4),
                "t_stat": round(float(m["t"]), 3),
                "p_value": float(m["p"]),
            })
    p_t2 = TBL_DIR / "table_v4_2_all_vor_nonvor_equal_window.csv"
    pd.DataFrame(t2_rows).to_csv(p_t2, index=False, lineterminator="\n")

    # Table V4-3: Onsite Early & Cumulative Readership Predictive Associations (Untruncated Monthly Cohort N=1,852)
    t3_rows = []
    for y_col, y_lbl in [
        ("pv_first_3m", "First 3 calendar bins: Page-views"),
        ("dl_first_3m", "First 3 calendar bins: Downloads"),
        ("pv_total", "Cumulative lifetime: Page-views"),
        ("dl_total", "Cumulative lifetime: Downloads"),
    ]:
        for term, t_lbl in [
            ("v1_low", "Evidence: Below Solid vs Solid"),
            ("v1_high", "Evidence: Compelling+ vs Solid"),
            ("v1_imp", "Significance: Important vs Valuable/Useful"),
            ("v1_fund", "Significance: Fundamental+ vs Valuable/Useful"),
        ]:
            m = early_attention[y_col][term]
            t3_rows.append({
                "outcome": y_col,
                "outcome_label": y_lbl,
                "term": term,
                "term_label": t_lbl,
                "n_obs": int(m["n"]),
                "n_clusters": int(m["G"]),
                "pct": round(float(m["pct"]), 2),
                "pct_ci95_lo": round(float(m["pct_ci95_lo"]), 2),
                "pct_ci95_hi": round(float(m["pct_ci95_hi"]), 2),
                "t_stat": round(float(m["t"]), 3),
                "p_value": float(m["p"]),
            })
    p_t3 = TBL_DIR / "table_v4_3_onsite_readership_predictive.csv"
    pd.DataFrame(t3_rows).to_csv(p_t3, index=False, lineterminator="\n")

    # Table V4-4: Revision Funnel by v1 Strength Tier (Public Revision vs VoR vs Rating Upgrade)
    t4_rows = []
    for lbl, _ in tiers:
        f = funnel_by_tier[lbl]
        t4_rows.append({"v1_strength_tier": lbl, **f})
    p_t4 = TBL_DIR / "table_v4_4_revision_upgrade_and_trajectories.csv"
    pd.DataFrame(t4_rows).to_csv(p_t4, index=False, lineterminator="\n")

    # Table S1: Exploratory Dec 10, 2024 Indexing Cohort Analysis (Supplementary Information)
    ts1_rows = []
    aj10 = aj_cutoffs["2024-12-10"]["contrasts"]
    for d in HORIZONS:
        for k, olbl in (("km_vor_pct", "Any_VoR_KM"), ("cif_solid_pct", "Final_SolidPlus_AJ_CIF"), ("cif_unrev_pct", "Final_BelowSolid_AJ_CIF")):
            c = aj10[f"t{d}"][k]
            ts1_rows.append({
                "estimator": "Unadjusted_KM_AJ",
                "horizon_days": d,
                "outcome": olbl,
                "n_obs": int(len(pre) + len(post)),
                "diff_pp": c["diff_pp"],
                "ci95_lo_pp": c["ci95_lo_pp"],
                "ci95_hi_pp": c["ci95_hi_pp"],
                "p_cr1_or_boot": c["p"],
                "p_wcb": c["p"],
            })
        for est_lbl, dct in (("SubjectAdjusted_LPM_StrictV1Subj", fixed_horizon_strict), ("SubjectAdjusted_LPM_V3ParityFinSubj", fixed_horizon_v3_parity)):
            for k, olbl in (("any_vor", "Any_VoR"), ("solid_vor", "Final_SolidPlus_VoR"), ("lower_rated_vor", "Final_BelowSolid_VoR"), ("observed_revision", "Posted_Public_Revision")):
                m = dct[str(d)][k]
                ts1_rows.append({
                    "estimator": est_lbl,
                    "horizon_days": d,
                    "outcome": olbl,
                    "n_obs": int(m["n"]),
                    "diff_pp": round(float(100.0 * m["beta"]), 2),
                    "ci95_lo_pp": round(float(100.0 * m["ci95_lo"]), 2),
                    "ci95_hi_pp": round(float(100.0 * m["ci95_hi"]), 2),
                    "p_cr1_or_boot": float(m["p"]),
                    "p_wcb": float(m["p_wcb"]),
                })
    p_ts1 = TBL_DIR / "table_s1_indexing_cohort_exploratory.csv"
    pd.DataFrame(ts1_rows).to_csv(p_ts1, index=False, lineterminator="\n")

    out = {
        "snapshot_date": str(FREEZE.date()),
        "cohort_summary": {
            "n_census": len(panel),
            "n_v1_with_strength": int(panel["v1_str_min"].notna().sum()),
            "n_mature_2023_2024": len(mat),
            "n_mature_vor": len(vor),
            "n_mature_non_vor": len(nonvor),
            "n_mature_complete_monthly_ge_2023_11": len(early),
            "n_bench_crossed_post": len(s_bench_post),
            "n_bench_crossed_next": len(s_bench_next),
            "n_strict_crossed_post": len(s_strict_post),
            "n_strict_crossed_next": len(s_strict_next),
            "n_bench_2285_max_authors_gt_v1": n_leak_auth_2285,
            "pct_bench_2285_max_authors_gt_v1": round(float(100.0 * n_leak_auth_2285 / len(s_bench_post)), 2),
            "n_bench_2285_fin_subj_ne_v1": n_leak_subj_2285,
            "pct_bench_2285_fin_subj_ne_v1": round(float(100.0 * n_leak_subj_2285 / len(s_bench_post)), 2),
        },
        "covariate_audit_and_crossed_clock": {
            "reviewer_2285_exact_parity": reviewer_2285_parity,
            "benchmark_fin_subj": bench_crossed,
            "strict_v1_frozen": strict_crossed,
            "clock_and_pre_v1_sensitivities": clock_sens,
        },
        "equal_window_validation": {
            "by_sample": sample_validation,
            "vor_interaction_all_v1": vor_interaction,
            "incremental_predictive_power": incremental_power,
            "loso_18subj": loso_v4,
        },
        "onsite_readership": {
            "complete_monthly_cohort_n1852": early_attention,
            "all_mature_lifetime_n2653": lifetime_attention_all_mature,
        },
        "revision_and_upgrade": {
            "funnel_by_v1_tier": funnel_by_tier,
            "upgrade_models": upgrade_models,
        },
        "supplementary_indexing_cohort": indexing_si,
        "tables_sha256": {
            p_t1.name: sha256_bytes(p_t1),
            p_t2.name: sha256_bytes(p_t2),
            p_t3.name: sha256_bytes(p_t3),
            p_t4.name: sha256_bytes(p_t4),
            p_ts1.name: sha256_bytes(p_ts1),
        },
        "elapsed_sec": round(time.time() - t0, 2),
    }

    out_path = RES_DIR / "09_v4_scientometrics_results.json"
    sha = write_json_lf(out_path, out)
    print(f"[DONE STEP 9 (v4)] Elapsed {out['elapsed_sec']}s | SHA-256: {sha}", flush=True)


if __name__ == "__main__":
    main()
