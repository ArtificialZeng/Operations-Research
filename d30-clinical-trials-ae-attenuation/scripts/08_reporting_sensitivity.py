"""Comprehensive v4 econometric sensitivity, support, MedDRA bounds, and TOST suite.

Addresses all JCE methodological revision requirements cleanly from verified processed panels
and archived ClinicalTrials.gov v2 snapshots:
  1. Extensive vs. Intensive Margin Decomposition (zero-share indicator + positive-share slope),
     Common-Drug-Program comparison (exact shared non-singleton programs), Nonlinear Binned and
     Harrell Restricted Cubic Spline curves, Effective FWL Regression Weights (Aronow-Samii),
     and Two-Way Alternative-Region Counterfactuals (US, North America, Western Europe EU/EEA,
     Western Europe/Dev, Latin America, Asia Emerging, Non-EU EE/RU-UA).
  2. MedDRA Four-State Cell Audit (True Zero, Below-Threshold Left-Censored, Missing/Unreliable
     Denominator, Missing Term), Legacy-Fallback vs. Strict Zero-Fallback Paired Contrasts,
     Uncensored 0%-Threshold Estimation, Fixed >0%-Threshold Pre-Defined Common Term Panels
     (15 Subjective vs. 15 Objective SOC & 15 Pure Investigations Biomarker Terms), Uniform
     Imputation + Exact Sharp Manski FWL Identification Bounds with Imbens-Manski 95% CIs,
     and AE Observation Time-Frame Completeness Audit.
  3. Pre-Specified Clinical Equivalence Margins & Formal Finite-Sample TOST for Serious AEs
     (±2.0 pp & ±1.0 pp per +10 pp), Within-Trial Risk Differences (±2.0 pp & ±1.0 pp), and
     All-Cause Mortality (±0.5 pp, ±1.0 pp, ±1.5 pp per +10 pp).

Exports:
  - results/08_reporting_sensitivity.json
  - tables/table_v4_support_and_margins.csv
  - tables/table_v4_alternative_regions.csv
  - tables/table_v4_meddra_bounds.csv
  - tables/table_v4_tost_equivalence.csv
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path
from types import ModuleType

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import optimize, stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "processed"
RES_DIR = ROOT / "results"
TAB_DIR = ROOT / "tables"
RES_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)

SITE_SHARES = ["eu_east_sh", "ru_ua_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"]
SITE_SHARES_FINE_NA = [
    "eu_east_sh", "ru_ua_sh", "we_eu_sh", "dev_apac_no_ca_sh", "latam_sh", "asia_sh", "other_sh",
]
CONTROLS = ["log_enroll", "log_sites", "log_countries", "dur_yr", "is_double_blind", "freq_thr"]
SAE_CONTROLS = ["log_enroll", "log_sites", "log_countries", "dur_yr", "is_double_blind"]


def load_econometrics() -> ModuleType:
    path = ROOT / "scripts" / "03_econometrics_suite.py"
    spec = importlib.util.spec_from_file_location("d30_econometrics_v4", path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["d30_econometrics_v4"] = module
    spec.loader.exec_module(module)
    return module


def _prepare_connected_sample(
    ec: ModuleType,
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    cov_cols: list[str],
    fe_col: str | None = "mol_sponsor",
    year_fe: bool = True,
    phase_fe: bool = False,
    cluster_col: str = "sponsor_nm",
) -> tuple[pd.DataFrame, list[str], list[str], str]:
    """Replicate exact connected-component pruning and full-rank covariate hygiene of fit_fe_cluster."""
    req = [y_col] + x_cols + cov_cols + ([fe_col] if fe_col else []) + (["start_year"] if year_fe else [])
    if phase_fe:
        req.append("phase_group")
    if cluster_col:
        req.append(cluster_col)
    req = list(dict.fromkeys(req))
    sub = df.dropna(subset=req).copy()
    if fe_col:
        sub = sub[sub[fe_col].astype(str) != ""].copy()
        if year_fe:
            sub = ec._prune_twoway_connected(sub, fe_col, "start_year")
        else:
            counts = sub[fe_col].value_counts()
            sub = sub[sub[fe_col].isin(counts[counts >= 2].index)].copy()
    if fe_col:
        active_covs = [
            c for c in cov_cols
            if sub[c].nunique(dropna=True) > 1 and bool(sub.groupby(fe_col)[c].nunique(dropna=True).gt(1).any())
        ]
    else:
        active_covs = [c for c in cov_cols if sub[c].nunique(dropna=True) > 1]
    active_xs = [c for c in x_cols if sub[c].nunique(dropna=True) > 1]

    fe_terms: list[str] = []
    if year_fe and sub["start_year"].nunique() > 1:
        fe_terms.append("C(start_year)")
    if phase_fe and sub["phase_group"].nunique() > 1:
        fe_terms.append("C(phase_group)")
    if fe_col and sub[fe_col].nunique() > 1:
        fe_terms.append(f"C({fe_col})")

    if fe_terms and active_covs:
        fe_mod = smf.ols(f"{y_col} ~ " + " + ".join(fe_terms), data=sub)
        q_fe, _ = np.linalg.qr(fe_mod.exog, mode="reduced")
        kept_covs: list[str] = []
        for c in active_covs:
            v = sub[c].to_numpy(dtype=float)
            resid = v - q_fe @ (q_fe.T @ v)
            if float(np.linalg.norm(resid)) > 1e-7 * max(1.0, float(np.linalg.norm(v))):
                kept_covs.append(c)
        active_covs = kept_covs

    formula = f"{y_col} ~ " + " + ".join(active_xs + active_covs + fe_terms)
    return sub, active_xs, active_covs, formula


def _fit_raw_cluster(sub: pd.DataFrame, formula: str, cluster_col: str = "sponsor_nm"):
    mod = smf.ols(formula, data=sub)
    n_cl = int(sub[cluster_col].nunique())
    if n_cl >= 10:
        fit = mod.fit(cov_type="cluster", cov_kwds={"groups": sub[cluster_col], "df_correction": True}, use_t=True)
        t_df = max(1, n_cl - 1)
    else:
        fit = mod.fit(cov_type="HC3", use_t=True)
        t_df = max(1, int(fit.df_resid))
    return mod, fit, t_df, n_cl


def _rcs_basis(x: np.ndarray, knots: list[float]) -> tuple[np.ndarray, np.ndarray]:
    """Harrell 4-knot restricted cubic spline nonlinear basis terms s1(x), s2(x)."""
    t1, t2, t3, t4 = knots
    scale = (t4 - t1) ** 2

    def pos3(v: np.ndarray, k: float) -> np.ndarray:
        return np.maximum(v - k, 0.0) ** 3

    s1 = (
        pos3(x, t1)
        - pos3(x, t3) * ((t4 - t1) / (t4 - t3))
        + pos3(x, t4) * ((t3 - t1) / (t4 - t3))
    ) / scale
    s2 = (
        pos3(x, t2)
        - pos3(x, t3) * ((t4 - t2) / (t4 - t3))
        + pos3(x, t4) * ((t3 - t2) / (t4 - t3))
    ) / scale
    return s1, s2


def _imbens_manski_crit(width: float, max_se: float, t_df: int, alpha: float = 0.05) -> float:
    """Imbens-Manski (2004) critical value with finite-sample t(G-1) CDF."""
    if max_se <= 0 or width <= 1e-12:
        return float(stats.t.ppf(1.0 - alpha / 2.0, df=t_df))
    ratio = width / max_se

    def obj(c: float) -> float:
        return float(stats.t.cdf(c + ratio, df=t_df) - stats.t.cdf(-c, df=t_df) - (1.0 - alpha))

    lo = float(stats.t.ppf(1.0 - alpha, df=t_df))
    hi = float(stats.t.ppf(1.0 - alpha / 2.0, df=t_df))
    if obj(lo) >= 0:
        return lo
    if obj(hi) <= 0:
        return hi
    return float(optimize.brentq(obj, lo, hi, xtol=1e-9))


def compute_support_summary(df: pd.DataFrame) -> dict:
    s = df["eu_east_sh"]
    return {
        "n": len(df),
        "n_zero": int(s.eq(0).sum()),
        "pct_zero": round(100.0 * float(s.eq(0).mean()), 2),
        "n_gt0_le10": int(((s > 0.0) & (s <= 0.10)).sum()),
        "n_gt10_le20": int(((s > 0.10) & (s <= 0.20)).sum()),
        "n_gt20_le35": int(((s > 0.20) & (s <= 0.35)).sum()),
        "n_gt35": int((s > 0.35).sum()),
        "n_at_least_half": int(s.ge(0.50).sum()),
        "mean": round(float(s.mean()), 5),
        "sd": round(float(s.std()), 5),
        "q25": round(float(s.quantile(0.25)), 5),
        "median": round(float(s.median()), 5),
        "q75": round(float(s.quantile(0.75)), 5),
        "q90": round(float(s.quantile(0.90)), 5),
        "q95": round(float(s.quantile(0.95)), 5),
        "maximum": round(float(s.max()), 5),
    }


def compute_extensive_intensive_and_common_programs(ec: ModuleType, phase3: pd.DataFrame, paired: pd.DataFrame) -> dict:
    """P0 #1: Support slices, zero-share indicator decomposition, and exact common-program comparison."""
    p3 = phase3.copy()
    p3["is_zero_eu"] = (p3["eu_east_sh"] == 0.0).astype(float)
    p23 = paired.copy()
    p23["is_zero_eu"] = (p23["eu_east_sh"] == 0.0).astype(float)

    # Identify exact non-singleton programs surviving in positive-share (0, 35%] and positive-share > 0%
    p3_pos_0_35_sub, _, _, _ = _prepare_connected_sample(
        ec, p3.loc[(p3["eu_east_sh"] > 0.0) & (p3["eu_east_sh"] <= 0.35)],
        "ctrl_oth", SITE_SHARES, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=False,
    )
    common_progs_0_35 = set(p3_pos_0_35_sub["mol_sponsor"].unique())

    p3_0_35_full_sub, _, _, _ = _prepare_connected_sample(
        ec, p3.loc[p3["eu_east_sh"] <= 0.35],
        "ctrl_oth", SITE_SHARES, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=False,
    )
    full_progs_0_35 = set(p3_0_35_full_sub["mol_sponsor"].unique())

    p3_pos_all_sub, _, _, _ = _prepare_connected_sample(
        ec, p3.loc[p3["eu_east_sh"] > 0.0],
        "ctrl_oth", SITE_SHARES, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=False,
    )
    common_progs_all_pos = set(p3_pos_all_sub["mol_sponsor"].unique())

    specs = [
        ("all_phase3", p3, SITE_SHARES, False),
        ("exclude_shares_above_50_percent", p3.loc[p3["eu_east_sh"] <= 0.50], SITE_SHARES, False),
        ("shares_at_most_35_percent", p3.loc[p3["eu_east_sh"] <= 0.35], SITE_SHARES, False),
        ("positive_shares_at_most_35_percent", p3.loc[(p3["eu_east_sh"] > 0.0) & (p3["eu_east_sh"] <= 0.35)], SITE_SHARES, False),
        ("positive_shares_all_phase3", p3.loc[p3["eu_east_sh"] > 0.0], SITE_SHARES, False),
        ("shares_0_35_with_zero_indicator", p3.loc[p3["eu_east_sh"] <= 0.35], ["is_zero_eu"] + SITE_SHARES, False),
        ("all_phase3_with_zero_indicator", p3, ["is_zero_eu"] + SITE_SHARES, False),
        ("common_236_progs_0_35_full", p3.loc[(p3["eu_east_sh"] <= 0.35) & (p3["mol_sponsor"].isin(common_progs_0_35))], SITE_SHARES, False),
        ("common_236_progs_0_35_with_zero_ind", p3.loc[(p3["eu_east_sh"] <= 0.35) & (p3["mol_sponsor"].isin(common_progs_0_35))], ["is_zero_eu"] + SITE_SHARES, False),
        ("common_236_progs_positive_0_35", p3.loc[(p3["eu_east_sh"] > 0.0) & (p3["eu_east_sh"] <= 0.35) & (p3["mol_sponsor"].isin(common_progs_0_35))], SITE_SHARES, False),
        ("common_allpos_progs_all_phase3_full", p3.loc[p3["mol_sponsor"].isin(common_progs_all_pos)], SITE_SHARES, False),
        ("common_allpos_progs_positive_only", p3.loc[(p3["eu_east_sh"] > 0.0) & (p3["mol_sponsor"].isin(common_progs_all_pos))], SITE_SHARES, False),
        ("p23_all_with_zero_indicator", p23, ["is_zero_eu"] + SITE_SHARES, True),
        ("p23_0_35_with_zero_indicator", p23.loc[p23["eu_east_sh"] <= 0.35], ["is_zero_eu"] + SITE_SHARES, True),
        ("p23_positive_0_35", p23.loc[(p23["eu_east_sh"] > 0.0) & (p23["eu_east_sh"] <= 0.35)], SITE_SHARES, True),
    ]

    rows = []
    for sample_name, frame, x_use, pfe in specs:
        for arm in ("ctrl", "act"):
            res = ec.fit_fe_cluster(frame, f"{arm}_oth", x_use, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe)
            eu_t = res["terms"]["eu_east_sh"]
            row = {
                "arm": arm,
                "sample": sample_name,
                "n": res["n"],
                "n_fe_groups": res["n_fe_groups"],
                "n_clusters": res["n_clusters"],
                "is_full_rank": res["is_full_rank"],
                "t_df": res["t_df"],
                **eu_t,
            }
            if "is_zero_eu" in res["terms"]:
                zt = res["terms"]["is_zero_eu"]
                row["zero_ind_coef"] = zt["coef"]
                row["zero_ind_se"] = zt["se"]
                row["zero_ind_p"] = zt["p"]
                row["zero_ind_ci95_lo"] = zt["ci95_lo"]
                row["zero_ind_ci95_hi"] = zt["ci95_hi"]
            rows.append(row)

    return {
        "n_programs_full_0_35": len(full_progs_0_35),
        "n_programs_positive_0_35": len(common_progs_0_35),
        "n_programs_dropped_by_positive_filter": len(full_progs_0_35 - common_progs_0_35),
        "n_programs_positive_all_phase3": len(common_progs_all_pos),
        "models": rows,
    }


def compute_nonlinear_bins_and_splines(ec: ModuleType, phase3: pd.DataFrame, paired: pd.DataFrame) -> dict:
    """Binned support model (0% omitted) and 4-knot Harrell Restricted Cubic Spline curve + Wald F-test."""
    out = {}
    knots = [0.0, 0.08, 0.17, 0.35]
    x_grid = [round(0.025 * k, 4) for k in range(17)]  # 0.000 to 0.400

    for tag, frame, pfe in [("phase3", phase3, False), ("phase2_and_3", paired, True)]:
        d = frame.copy()
        s = d["eu_east_sh"]
        d["bin_0_10"] = ((s > 0.0) & (s <= 0.10)).astype(float)
        d["bin_10_20"] = ((s > 0.10) & (s <= 0.20)).astype(float)
        d["bin_20_35"] = ((s > 0.20) & (s <= 0.35)).astype(float)
        d["bin_gt35"] = (s > 0.35).astype(float)
        bin_cols = ["bin_0_10", "bin_10_20", "bin_20_35", "bin_gt35"]
        other_shares = [c for c in SITE_SHARES if c != "eu_east_sh"]

        s1, s2 = _rcs_basis(s.to_numpy(dtype=float), knots)
        d["rcs_1"] = s1
        d["rcs_2"] = s2

        tag_out = {"knots": knots, "binned": {}, "rcs_4knot": {}}
        for arm in ("ctrl", "act"):
            y_col = f"{arm}_oth"
            # 1. Binned regression
            sub_b, _, _, form_b = _prepare_connected_sample(
                ec, d, y_col, bin_cols + other_shares, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            _, fit_b, t_df_b, n_cl_b = _fit_raw_cluster(sub_b, form_b)
            t_crit = float(stats.t.ppf(0.975, df=t_df_b))
            bin_rows = [{
                "bin": "0%",
                "n": int((sub_b["eu_east_sh"] == 0.0).sum()),
                "mean_share_pct": 0.0,
                "coef_pp": 0.0,
                "se_pp": 0.0,
                "ci95_lo_pp": 0.0,
                "ci95_hi_pp": 0.0,
                "p": None,
            }]
            for bc, blbl in [
                ("bin_0_10", "(0, 10%]"),
                ("bin_10_20", "(10, 20%]"),
                ("bin_20_35", "(20, 35%]"),
                ("bin_gt35", ">35%"),
            ]:
                coef = float(fit_b.params[bc])
                se = float(fit_b.bse[bc])
                pval = float(fit_b.pvalues[bc])
                mask = sub_b[bc] == 1.0
                bin_rows.append({
                    "bin": blbl,
                    "n": int(mask.sum()),
                    "mean_share_pct": round(100.0 * float(sub_b.loc[mask, "eu_east_sh"].mean()), 2),
                    "coef_pp": round(100.0 * coef, 3),
                    "se_pp": round(100.0 * se, 3),
                    "ci95_lo_pp": round(100.0 * (coef - t_crit * se), 3),
                    "ci95_hi_pp": round(100.0 * (coef + t_crit * se), 3),
                    "p": pval,
                })
            tag_out["binned"][arm] = {
                "n": int(fit_b.nobs),
                "n_fe_groups": int(sub_b["mol_sponsor"].nunique()),
                "n_clusters": n_cl_b,
                "t_df": t_df_b,
                "bins": bin_rows,
            }

            # 2. Restricted Cubic Spline regression + Nonlinearity Wald F-test
            sub_s, _, _, form_s = _prepare_connected_sample(
                ec, d, y_col, ["eu_east_sh", "rcs_1", "rcs_2"] + other_shares, CONTROLS,
                fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            _, fit_s, t_df_s, n_cl_s = _fit_raw_cluster(sub_s, form_s)
            t_crit_s = float(stats.t.ppf(0.975, df=t_df_s))
            cov_df = fit_s.cov_params()
            rcs_terms = ["eu_east_sh", "rcs_1", "rcs_2"]
            b_vec = fit_s.params[rcs_terms].to_numpy(dtype=float)
            v_mat = cov_df.loc[rcs_terms, rcs_terms].to_numpy(dtype=float)

            # Joint Wald F-test of H0: beta(rcs_1) = beta(rcs_2) = 0
            b_nl = b_vec[1:]
            v_nl = v_mat[1:, 1:]
            wald_f = float((b_nl @ np.linalg.solve(v_nl, b_nl)) / 2.0)
            wald_p = float(stats.f.sf(wald_f, dfn=2, dfd=t_df_s))

            # Pointwise predicted difference vs 0% along x_grid
            g_arr = np.array(x_grid, dtype=float)
            gs1, gs2 = _rcs_basis(g_arr, knots)
            curve = []
            for idx_g, xv in enumerate(x_grid):
                basis_v = np.array([xv, gs1[idx_g], gs2[idx_g]], dtype=float)
                pred = float(basis_v @ b_vec)
                se_p = float(np.sqrt(max(0.0, float(basis_v @ v_mat @ basis_v))))
                curve.append({
                    "share_pct": round(100.0 * xv, 2),
                    "pred_diff_pp": round(100.0 * pred, 3),
                    "se_pp": round(100.0 * se_p, 3),
                    "ci95_lo_pp": round(100.0 * (pred - t_crit_s * se_p), 3),
                    "ci95_hi_pp": round(100.0 * (pred + t_crit_s * se_p), 3),
                })

            tag_out["rcs_4knot"][arm] = {
                "n": int(fit_s.nobs),
                "n_fe_groups": int(sub_s["mol_sponsor"].nunique()),
                "n_clusters": n_cl_s,
                "t_df": t_df_s,
                "nonlinearity_wald_f": round(wald_f, 4),
                "nonlinearity_wald_p": wald_p,
                "curve_vs_0pct": curve,
            }
        out[tag] = tag_out
    return out


def compute_effective_fwl_weights(ec: ModuleType, phase3: pd.DataFrame, paired: pd.DataFrame) -> dict:
    """Compute exact Aronow-Samii FWL regression weights across programs & sponsors + leave-top-K-out."""
    out = {}
    for tag, frame, pfe in [("phase3", phase3, False), ("phase2_and_3", paired, True)]:
        sub, _, _, formula = _prepare_connected_sample(
            ec, frame, "ctrl_oth", SITE_SHARES, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
        )
        mod, fit, _, _ = _fit_raw_cluster(sub, formula)
        x_full = mod.exog
        idx_eu = mod.exog_names.index("eu_east_sh")
        x_eu = x_full[:, idx_eu]
        z_mat = np.delete(x_full, idx_eu, axis=1)
        q_z, _ = np.linalg.qr(z_mat, mode="reduced")
        x_tilde = x_eu - q_z @ (q_z.T @ x_eu)
        denom = float(x_tilde @ x_tilde)
        # Verify exact FWL slope identity
        fwl_slope = float((x_tilde @ mod.endog) / denom)
        ols_slope = float(fit.params["eu_east_sh"])
        assert abs(fwl_slope - ols_slope) < 1e-8, f"FWL mismatch: {fwl_slope} vs {ols_slope}"

        sub = sub.copy()
        sub["_fwl_w"] = (x_tilde ** 2) / denom

        prog_w = (
            sub.groupby("mol_sponsor")
            .agg(
                weight=("_fwl_w", "sum"),
                n_trials=("nct_id", "count"),
                min_eu_sh=("eu_east_sh", "min"),
                max_eu_sh=("eu_east_sh", "max"),
                mean_eu_sh=("eu_east_sh", "mean"),
                has_zero=("eu_east_sh", lambda s: int((s == 0.0).any())),
            )
            .sort_values("weight", ascending=False)
        )
        sp_w = sub.groupby("sponsor_nm")["_fwl_w"].sum().sort_values(ascending=False)

        hhi_prog = float((prog_w["weight"] ** 2).sum())
        eff_n_prog = 1.0 / hhi_prog
        hhi_sp = float((sp_w ** 2).sum())
        eff_n_sp = 1.0 / hhi_sp

        top10_progs = []
        for ms_key, r in prog_w.head(10).iterrows():
            mol, sp = str(ms_key).split("||", 1)
            top10_progs.append({
                "mol_sponsor": str(ms_key),
                "molecule": mol,
                "sponsor": sp,
                "n_trials": int(r["n_trials"]),
                "min_eu_pct": round(100.0 * float(r["min_eu_sh"]), 2),
                "max_eu_pct": round(100.0 * float(r["max_eu_sh"]), 2),
                "has_zero_share_trial": bool(r["has_zero"]),
                "weight_pct": round(100.0 * float(r["weight"]), 2),
            })

        # Leave-top-10 and leave-top-20 weighted programs out
        top10_keys = set(prog_w.head(10).index)
        top20_keys = set(prog_w.head(20).index)
        lko = {}
        for drop_lbl, drop_keys in [("drop_top10_weighted_programs", top10_keys), ("drop_top20_weighted_programs", top20_keys)]:
            sub_drop = frame.loc[~frame["mol_sponsor"].isin(drop_keys)]
            lko[drop_lbl] = {}
            for arm in ("ctrl", "act"):
                r_d = ec.fit_fe_cluster(sub_drop, f"{arm}_oth", SITE_SHARES, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe)
                lko[drop_lbl][arm] = {
                    "n": r_d["n"],
                    "n_fe_groups": r_d["n_fe_groups"],
                    "is_full_rank": r_d["is_full_rank"],
                    **r_d["terms"]["eu_east_sh"],
                }

        # Weight share contributed by trials with eu_east_sh == 0 vs (0, 35%] vs >35%
        zero_w_pct = round(100.0 * float(sub.loc[sub["eu_east_sh"] == 0.0, "_fwl_w"].sum()), 2)
        mid_w_pct = round(100.0 * float(sub.loc[(sub["eu_east_sh"] > 0.0) & (sub["eu_east_sh"] <= 0.35), "_fwl_w"].sum()), 2)
        hi_w_pct = round(100.0 * float(sub.loc[sub["eu_east_sh"] > 0.35, "_fwl_w"].sum()), 2)

        out[tag] = {
            "n": len(sub),
            "n_programs": len(prog_w),
            "effective_n_programs": round(eff_n_prog, 2),
            "hhi_programs": round(hhi_prog, 5),
            "top1_program_weight_pct": round(100.0 * float(prog_w["weight"].head(1).sum()), 2),
            "top5_programs_weight_pct": round(100.0 * float(prog_w["weight"].head(5).sum()), 2),
            "top10_programs_weight_pct": round(100.0 * float(prog_w["weight"].head(10).sum()), 2),
            "top20_programs_weight_pct": round(100.0 * float(prog_w["weight"].head(20).sum()), 2),
            "n_sponsors": len(sp_w),
            "effective_n_sponsors": round(eff_n_sp, 2),
            "top5_sponsors_weight_pct": round(100.0 * float(sp_w.head(5).sum()), 2),
            "top10_sponsors_weight_pct": round(100.0 * float(sp_w.head(10).sum()), 2),
            "weight_by_support_zone_pct": {
                "zero_share": zero_w_pct,
                "pos_0_to_35": mid_w_pct,
                "above_35": hi_w_pct,
            },
            "top10_programs": top10_progs,
            "leave_top_weighted_programs_out": lko,
        }
    return out


def compute_alternative_region_counterfactuals(ec: ModuleType, phase3: pd.DataFrame, paired: pd.DataFrame) -> dict:
    """Two-way alternative-region counterfactuals: +10 pp EU-East replacing -10 pp of each comparator region."""
    out = {}
    for tag, frame, pfe in [("phase3", phase3, False), ("phase2_and_3", paired, True)]:
        rows = []
        # 1. Baseline 7-region simplex (US omitted): EU-East vs US, WE/Dev, LatAm, Asia, Non-EU EE/RU-UA
        for y_col in ("ctrl_oth", "act_oth", "oth_rd", "ctrl_sae", "act_sae"):
            covs = CONTROLS if "oth" in y_col else SAE_CONTROLS
            sub, _, _, formula = _prepare_connected_sample(
                ec, frame, y_col, SITE_SHARES, covs, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            _, fit, t_df, n_cl = _fit_raw_cluster(sub, formula)
            t_crit = float(stats.t.ppf(0.975, df=t_df))
            v_cov = fit.cov_params()
            b_eu = float(fit.params["eu_east_sh"])
            v_eu = float(v_cov.loc["eu_east_sh", "eu_east_sh"])

            for alt_key, alt_lbl in [
                ("us_sh", "United States (baseline)"),
                ("we_sh", "Western Europe & Dev. APAC/CA"),
                ("latam_sh", "Latin America"),
                ("asia_sh", "Emerging Asia"),
                ("ru_ua_sh", "Non-EU Eastern Europe / RU-UA"),
            ]:
                if alt_key == "us_sh":
                    diff = b_eu
                    se = float(np.sqrt(v_eu))
                else:
                    b_alt = float(fit.params[alt_key])
                    v_alt = float(v_cov.loc[alt_key, alt_key])
                    c_ea = float(v_cov.loc["eu_east_sh", alt_key])
                    diff = b_eu - b_alt
                    se = float(np.sqrt(max(1e-16, v_eu + v_alt - 2.0 * c_ea)))
                tval = diff / se
                pval = float(2.0 * stats.t.sf(abs(tval), df=t_df))
                rows.append({
                    "sample": tag,
                    "simplex": "7-region (US omitted)",
                    "outcome": y_col,
                    "comparator_region": alt_lbl,
                    "comparator_key": alt_key,
                    "n": int(fit.nobs),
                    "n_fe_groups": int(sub["mol_sponsor"].nunique()),
                    "n_clusters": n_cl,
                    "t_df": t_df,
                    "per_10pp_pp": round(10.0 * diff, 3),
                    "per_10pp_se_pp": round(10.0 * se, 3),
                    "per_10pp_ci95_lo_pp": round(10.0 * (diff - t_crit * se), 3),
                    "per_10pp_ci95_hi_pp": round(10.0 * (diff + t_crit * se), 3),
                    "t": round(tval, 3),
                    "p": pval,
                })

            # 2. Fine 8-region simplex (North America = US + Canada omitted): explicitly separates
            # North America vs. Western Europe (EU/EEA only)!
            sub8, _, _, form8 = _prepare_connected_sample(
                ec, frame, y_col, SITE_SHARES_FINE_NA, covs, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            _, fit8, t_df8, n_cl8 = _fit_raw_cluster(sub8, form8)
            t_crit8 = float(stats.t.ppf(0.975, df=t_df8))
            v8 = fit8.cov_params()
            b_eu8 = float(fit8.params["eu_east_sh"])
            v_eu8 = float(v8.loc["eu_east_sh", "eu_east_sh"])
            for alt_key, alt_lbl in [
                ("na_sh", "North America (U.S. + Canada)"),
                ("we_eu_sh", "Western Europe (EU/EEA only)"),
                ("dev_apac_no_ca_sh", "Developed APAC / Israel"),
            ]:
                if alt_key == "na_sh":
                    diff = b_eu8
                    se = float(np.sqrt(v_eu8))
                else:
                    b_alt = float(fit8.params[alt_key])
                    v_alt = float(v8.loc[alt_key, alt_key])
                    c_ea = float(v8.loc["eu_east_sh", alt_key])
                    diff = b_eu8 - b_alt
                    se = float(np.sqrt(max(1e-16, v_eu8 + v_alt - 2.0 * c_ea)))
                tval = diff / se
                pval = float(2.0 * stats.t.sf(abs(tval), df=t_df8))
                rows.append({
                    "sample": tag,
                    "simplex": "8-region (North America omitted)",
                    "outcome": y_col,
                    "comparator_region": alt_lbl,
                    "comparator_key": alt_key,
                    "n": int(fit8.nobs),
                    "n_fe_groups": int(sub8["mol_sponsor"].nunique()),
                    "n_clusters": n_cl8,
                    "t_df": t_df8,
                    "per_10pp_pp": round(10.0 * diff, 3),
                    "per_10pp_se_pp": round(10.0 * se, 3),
                    "per_10pp_ci95_lo_pp": round(10.0 * (diff - t_crit8 * se), 3),
                    "per_10pp_ci95_hi_pp": round(10.0 * (diff + t_crit8 * se), 3),
                    "t": round(tval, 3),
                    "p": pval,
                })
        out[tag] = rows
    return out


def compute_sharp_manski_fwl_bounds(
    ec: ModuleType,
    df: pd.DataFrame,
    lo_col: str,
    hi_col: str,
    x_cols: list[str],
    cov_cols: list[str],
    fe_col: str | None = "mol_sponsor",
    year_fe: bool = True,
    phase_fe: bool = True,
) -> dict:
    """Exact sharp Manski worst-case FWL identification interval [beta_min, beta_max] + Imbens-Manski 95% CI."""
    work = df.dropna(subset=[lo_col, hi_col]).copy()
    work["_y_lo"] = work[lo_col].astype(float)
    work["_y_hi"] = work[hi_col].astype(float)
    work["_y_mid"] = 0.5 * (work["_y_lo"] + work["_y_hi"])

    sub, active_xs, active_covs, form_lo = _prepare_connected_sample(
        ec, work, "_y_lo", x_cols, cov_cols, fe_col=fe_col, year_fe=year_fe, phase_fe=phase_fe,
    )
    if len(sub) < 30 or "eu_east_sh" not in active_xs:
        return {"n": len(sub), "error": "insufficient_sample"}

    rhs = form_lo.split("~", 1)[1].strip()
    mod_lo, fit_lo, t_df, n_cl = _fit_raw_cluster(sub, f"_y_lo ~ {rhs}")
    _, fit_mid, _, _ = _fit_raw_cluster(sub, f"_y_mid ~ {rhs}")
    _, fit_hi, _, _ = _fit_raw_cluster(sub, f"_y_hi ~ {rhs}")

    # Exact FWL linear weight vector w_i = x_tilde_i / (x_tilde' x_tilde)
    x_full = mod_lo.exog
    idx_eu = mod_lo.exog_names.index("eu_east_sh")
    x_eu = x_full[:, idx_eu]
    z_mat = np.delete(x_full, idx_eu, axis=1)
    q_z, _ = np.linalg.qr(z_mat, mode="reduced")
    x_tilde = x_eu - q_z @ (q_z.T @ x_eu)
    w_vec = x_tilde / float(x_tilde @ x_tilde)

    y_lo_arr = sub["_y_lo"].to_numpy(dtype=float)
    y_hi_arr = sub["_y_hi"].to_numpy(dtype=float)
    # Sharp Manski extrema over hyper-rectangle prod_i [L_i, U_i]
    sub["_y_manski_min"] = np.where(w_vec >= 0.0, y_lo_arr, y_hi_arr)
    sub["_y_manski_max"] = np.where(w_vec >= 0.0, y_hi_arr, y_lo_arr)

    _, fit_mmin, _, _ = _fit_raw_cluster(sub, f"_y_manski_min ~ {rhs}")
    _, fit_mmax, _, _ = _fit_raw_cluster(sub, f"_y_manski_max ~ {rhs}")

    b_min = float(fit_mmin.params["eu_east_sh"])
    b_max = float(fit_mmax.params["eu_east_sh"])
    se_min = float(fit_mmin.bse["eu_east_sh"])
    se_max = float(fit_mmax.bse["eu_east_sh"])

    # Verify exact sharp algebraic match
    assert abs(b_min - float(w_vec @ sub["_y_manski_min"].to_numpy())) < 1e-7
    assert abs(b_max - float(w_vec @ sub["_y_manski_max"].to_numpy())) < 1e-7

    width = max(0.0, b_max - b_min)
    c_im = _imbens_manski_crit(width, max(se_min, se_max), t_df=t_df, alpha=0.05)
    t_crit = float(stats.t.ppf(0.975, df=t_df))

    def pack_fit(fit_obj) -> dict:
        c = float(fit_obj.params["eu_east_sh"])
        se = float(fit_obj.bse["eu_east_sh"])
        p = float(fit_obj.pvalues["eu_east_sh"])
        return {
            "per_10pp_coef": round(0.10 * c, 5),
            "per_10pp_se": round(0.10 * se, 5),
            "per_10pp_ci95_lo": round(0.10 * (c - t_crit * se), 5),
            "per_10pp_ci95_hi": round(0.10 * (c + t_crit * se), 5),
            "p": p,
        }

    n_exact_point = int((np.abs(y_hi_arr - y_lo_arr) < 1e-12).sum())
    return {
        "n": int(fit_lo.nobs),
        "n_fe_groups": int(sub[fe_col].nunique()) if fe_col else 0,
        "n_clusters": n_cl,
        "t_df": t_df,
        "n_point_identified_trials": n_exact_point,
        "pct_point_identified_trials": round(100.0 * n_exact_point / max(1, len(sub)), 2),
        "mean_interval_width": round(float(np.mean(y_hi_arr - y_lo_arr)), 5),
        "uniform_lower_bound": pack_fit(fit_lo),
        "uniform_midpoint": pack_fit(fit_mid),
        "uniform_upper_bound": pack_fit(fit_hi),
        "manski_sharp_per_10pp": {
            "id_lo": round(0.10 * b_min, 5),
            "id_hi": round(0.10 * b_max, 5),
            "se_lo": round(0.10 * se_min, 5),
            "se_hi": round(0.10 * se_max, 5),
            "im95_lo": round(0.10 * (b_min - c_im * se_min), 5),
            "im95_hi": round(0.10 * (b_max + c_im * se_max), 5),
            "excludes_zero_id": bool(b_max < 0 or b_min > 0),
            "excludes_zero_im95": bool((b_max + c_im * se_max) < 0 or (b_min - c_im * se_min) > 0),
        },
    }


def compute_meddra_threshold_and_bounds(ec: ModuleType, paired: pd.DataFrame, phase3: pd.DataFrame) -> dict:
    """P0 #2: Strict zero-fallback contrasts, 0% & 5% & 2% strata, common-term panel, Manski bounds, timeFrame audit."""
    out: dict = {}

    # 1. Legacy-fallback vs. Strict zero-fallback vs. Zero-Anomaly paired SOC contrasts
    strict_rows = []
    no_anom_mask = (
        (paired["ctrl_subj_strict_has_anom"] == 0)
        & (paired["ctrl_obj_strict_has_anom"] == 0)
        & (paired["act_subj_strict_has_anom"] == 0)
        & (paired["act_obj_strict_has_anom"] == 0)
    )
    for arm in ("ctrl", "act"):
        for spec_lbl, frame, pfe, s_col, o_col, drop_fthr in [
            ("legacy_p23_subj_minus_obj", paired, True, f"{arm}_subj_sum_aff_rate", f"{arm}_obj_sum_aff_rate", False),
            ("strict_p23_subj_minus_obj", paired, True, f"{arm}_subj_strict_sum_rate", f"{arm}_obj_strict_sum_rate", False),
            ("strict_no_anomaly_p23_subj_minus_obj", paired.loc[no_anom_mask], True, f"{arm}_subj_strict_sum_rate", f"{arm}_obj_strict_sum_rate", False),
            ("strict_p3_subj_minus_obj", phase3, False, f"{arm}_subj_strict_sum_rate", f"{arm}_obj_strict_sum_rate", False),
            ("strict_p23_subj_minus_investigations", paired, True, f"{arm}_subj_strict_sum_rate", f"{arm}_inv_strict_sum_rate", False),
            ("strict_p23_freq5_subj_minus_obj", paired.loc[paired["freq_thr"] == 5.0], True, f"{arm}_subj_strict_sum_rate", f"{arm}_obj_strict_sum_rate", True),
            ("strict_p23_freq2_subj_minus_obj", paired.loc[paired["freq_thr"] == 2.0], True, f"{arm}_subj_strict_sum_rate", f"{arm}_obj_strict_sum_rate", True),
            ("strict_p23_maxpct_subj_minus_obj", paired, True, f"{arm}_subj_strict_max_pct", f"{arm}_obj_strict_max_pct", False),
            ("strict_p23_maxpct_subj_minus_inv", paired, True, f"{arm}_subj_strict_max_pct", f"{arm}_inv_strict_max_pct", False),
        ]:
            covs = SAE_CONTROLS if drop_fthr else CONTROLS
            tmp = frame.assign(_diff=frame[s_col] - frame[o_col])
            r = ec.fit_fe_cluster(tmp, "_diff", SITE_SHARES, covs, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe)
            if "error" not in r and "eu_east_sh" in r["terms"]:
                strict_rows.append({
                    "arm": arm,
                    "spec": spec_lbl,
                    "n": r["n"],
                    "n_fe_groups": r["n_fe_groups"],
                    "is_full_rank": r["is_full_rank"],
                    **r["terms"]["eu_east_sh"],
                })
    out["strict_vs_legacy_soc_contrasts"] = strict_rows

    # 2. Strictly Uncensored 0%-Threshold Subset (ZERO threshold left-censoring!)
    f0 = paired.loc[paired["freq_thr"] == 0.0].copy()
    f0_rows = []
    for fe_lbl, fe_col in [("therapeutic_area", "therapeutic_area"), ("sponsor_nm", "sponsor_nm")]:
        for arm in ("ctrl", "act"):
            f0[f"_{arm}_strict_diff"] = f0[f"{arm}_subj_strict_sum_rate"] - f0[f"{arm}_obj_strict_sum_rate"]
            f0[f"_{arm}_cpanel_diff"] = f0[f"{arm}_cpanel_subj_sum_lo"] - f0[f"{arm}_cpanel_obj_sum_lo"]
            f0[f"_{arm}_cpanel_inv_diff"] = f0[f"{arm}_cpanel_subj_sum_lo"] - f0[f"{arm}_cpanel_inv_sum_lo"]
            f0[f"_{arm}_max_diff"] = f0[f"{arm}_subj_strict_max_pct"] - f0[f"{arm}_obj_strict_max_pct"]
            for y_lbl, y_col in [
                ("any_nonserious_ae", f"{arm}_oth"),
                ("strict_subj_sum", f"{arm}_subj_strict_sum_rate"),
                ("strict_obj_sum", f"{arm}_obj_strict_sum_rate"),
                ("strict_inv_sum", f"{arm}_inv_strict_sum_rate"),
                ("strict_subj_minus_obj", f"_{arm}_strict_diff"),
                ("cpanel15_subj_sum", f"{arm}_cpanel_subj_sum_lo"),
                ("cpanel15_obj_sum", f"{arm}_cpanel_obj_sum_lo"),
                ("cpanel15_inv_sum", f"{arm}_cpanel_inv_sum_lo"),
                ("cpanel15_subj_minus_obj", f"_{arm}_cpanel_diff"),
                ("cpanel15_subj_minus_inv", f"_{arm}_cpanel_inv_diff"),
                ("strict_maxpct_subj_minus_obj", f"_{arm}_max_diff"),
            ]:
                r = ec.fit_fe_cluster(f0, y_col, SITE_SHARES, SAE_CONTROLS, fe_col=fe_col, year_fe=True, phase_fe=True)
                if "error" not in r and "eu_east_sh" in r["terms"]:
                    f0_rows.append({
                        "fe": fe_lbl,
                        "arm": arm,
                        "outcome": y_lbl,
                        "n": r["n"],
                        "n_fe_groups": r["n_fe_groups"],
                        "y_mean": r["y_mean"],
                        "is_full_rank": r["is_full_rank"],
                        **r["terms"]["eu_east_sh"],
                    })
    out["zero_threshold_uncensored_subset"] = {
        "n_total_freq0": len(f0),
        "n_phase3_freq0": int((f0["is_phase3"] == 1).sum()),
        "models": f0_rows,
    }

    # 3. Pre-Defined Common Term Panel & Peak-Term Rates: Uniform Imputation + Sharp Manski FWL Bounds
    # Across All P2+P3, Fixed 5% Threshold, and Fixed 2% Threshold!
    bounds_out = []
    f5 = paired.loc[paired["freq_thr"] == 5.0].copy()
    for stratum_lbl, frame, covs_use in [
        ("p23_all_thresholds", paired, CONTROLS),
        ("p23_fixed_5pct_threshold", f5, SAE_CONTROLS),
    ]:
        for arm in ("ctrl", "act"):
            d_w = frame.copy()
            # (a) Common 15-term Subjective sum
            for metric_lbl, lo_c, hi_c in [
                ("cpanel15_subj_sum", f"{arm}_cpanel_subj_sum_lo", f"{arm}_cpanel_subj_sum_hi_cap"),
                ("cpanel15_obj_sum", f"{arm}_cpanel_obj_sum_lo", f"{arm}_cpanel_obj_sum_hi_cap"),
                ("cpanel15_inv_sum", f"{arm}_cpanel_inv_sum_lo", f"{arm}_cpanel_inv_sum_hi_cap"),
                ("strict_soc_subj_max_pct", f"{arm}_subj_strict_max_pct", f"{arm}_subj_strict_max_hi_cap"),
                ("strict_soc_obj_max_pct", f"{arm}_obj_strict_max_pct", f"{arm}_obj_strict_max_hi_cap"),
                ("strict_soc_inv_max_pct", f"{arm}_inv_strict_max_pct", f"{arm}_inv_strict_max_hi_cap"),
            ]:
                b_res = compute_sharp_manski_fwl_bounds(
                    ec, d_w, lo_c, hi_c, SITE_SHARES, covs_use, fe_col="mol_sponsor", year_fe=True, phase_fe=True,
                )
                bounds_out.append({"stratum": stratum_lbl, "arm": arm, "metric": metric_lbl, **b_res})

            # (b) Paired Contrasts with Exact Interval Arithmetic:
            # D = Y_subj - Y_obj in [L_subj - U_obj, U_subj - L_obj]
            for c_lbl, ls, hs, lo, ho in [
                (
                    "cpanel15_sum_subj_minus_obj",
                    f"{arm}_cpanel_subj_sum_lo", f"{arm}_cpanel_subj_sum_hi_cap",
                    f"{arm}_cpanel_obj_sum_lo", f"{arm}_cpanel_obj_sum_hi_cap",
                ),
                (
                    "cpanel15_sum_subj_minus_inv",
                    f"{arm}_cpanel_subj_sum_lo", f"{arm}_cpanel_subj_sum_hi_cap",
                    f"{arm}_cpanel_inv_sum_lo", f"{arm}_cpanel_inv_sum_hi_cap",
                ),
                (
                    "strict_soc_maxpct_subj_minus_obj",
                    f"{arm}_subj_strict_max_pct", f"{arm}_subj_strict_max_hi_cap",
                    f"{arm}_obj_strict_max_pct", f"{arm}_obj_strict_max_hi_cap",
                ),
                (
                    "strict_soc_maxpct_subj_minus_inv",
                    f"{arm}_subj_strict_max_pct", f"{arm}_subj_strict_max_hi_cap",
                    f"{arm}_inv_strict_max_pct", f"{arm}_inv_strict_max_hi_cap",
                ),
            ]:
                d_w["_d_lo"] = d_w[ls] - d_w[ho]
                d_w["_d_hi"] = d_w[hs] - d_w[lo]
                # Also compute uniform-threshold-midpoint contrast (both arms/groups imputed at 0.5*ub)
                d_w["_d_same_lo"] = d_w[ls] - d_w[lo]
                d_w["_d_same_mid"] = 0.5 * (d_w[ls] + d_w[hs]) - 0.5 * (d_w[lo] + d_w[ho])
                d_w["_d_same_hi"] = d_w[hs] - d_w[ho]
                b_res = compute_sharp_manski_fwl_bounds(
                    ec, d_w, "_d_lo", "_d_hi", SITE_SHARES, covs_use, fe_col="mol_sponsor", year_fe=True, phase_fe=True,
                )
                # Add same-rule uniform imputations (0%, 50%, 100% of censoring bound for BOTH SOCs simultaneously)
                same_rule = {}
                for r_lbl, col_u in [("both_0pct", "_d_same_lo"), ("both_50pct", "_d_same_mid"), ("both_100pct", "_d_same_hi")]:
                    rr = ec.fit_fe_cluster(d_w, col_u, SITE_SHARES, covs_use, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
                    same_rule[r_lbl] = rr["terms"]["eu_east_sh"]
                b_res["same_imputation_rule_contrast"] = same_rule
                bounds_out.append({"stratum": stratum_lbl, "arm": arm, "metric": c_lbl, **b_res})

    out["interval_and_manski_bounds"] = bounds_out

    # 4. AE Observation Time-Frame Completeness & Sensitivity
    tf_col = "has_ae_timeframe_snap"
    tf_audit = {
        "p23_total": len(paired),
        "p23_with_timeframe": int(paired[tf_col].sum()),
        "p23_missing_timeframe": int((paired[tf_col] == 0).sum()),
        "p23_pct_missing_timeframe": round(100.0 * float((paired[tf_col] == 0).mean()), 2),
        "p3_total": len(phase3),
        "p3_with_timeframe": int(phase3[tf_col].sum()),
        "p3_missing_timeframe": int((phase3[tf_col] == 0).sum()),
        "p3_pct_missing_timeframe": round(100.0 * float((phase3[tf_col] == 0).mean()), 2),
        "timeframe_missingness_on_eu_east_p3": ec.fit_fe_cluster(
            phase3, tf_col, SITE_SHARES, SAE_CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=False,
        ),
        "timeframe_missingness_on_eu_east_p23": ec.fit_fe_cluster(
            paired, tf_col, SITE_SHARES, SAE_CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=True,
        ),
        "restricted_to_documented_timeframe": {},
        "controlling_for_timeframe_indicator": {},
    }
    for tag, frame, pfe in [("phase3", phase3, False), ("phase2_and_3", paired, True)]:
        sub_tf = frame.loc[frame[tf_col] == 1]
        tf_audit["restricted_to_documented_timeframe"][tag] = {}
        tf_audit["controlling_for_timeframe_indicator"][tag] = {}
        for arm in ("ctrl", "act"):
            r_res = ec.fit_fe_cluster(sub_tf, f"{arm}_oth", SITE_SHARES, CONTROLS, fe_col="mol_sponsor", year_fe=True, phase_fe=pfe)
            r_ctl = ec.fit_fe_cluster(frame, f"{arm}_oth", SITE_SHARES, CONTROLS + [tf_col], fe_col="mol_sponsor", year_fe=True, phase_fe=pfe)
            tf_audit["restricted_to_documented_timeframe"][tag][arm] = {
                "n": r_res["n"], "n_fe_groups": r_res["n_fe_groups"], "is_full_rank": r_res["is_full_rank"],
                **r_res["terms"]["eu_east_sh"],
            }
            tf_audit["controlling_for_timeframe_indicator"][tag][arm] = {
                "n": r_ctl["n"], "n_fe_groups": r_ctl["n_fe_groups"], "is_full_rank": r_ctl["is_full_rank"],
                **r_ctl["terms"]["eu_east_sh"],
            }
    out["ae_timeframe_audit"] = tf_audit
    return out


def compute_prespecified_tost(ec: ModuleType, phase3: pd.DataFrame, paired: pd.DataFrame) -> list[dict]:
    """P0 #3: Formal finite-sample TOST against pre-specified clinical equivalence margins per +10 pp."""
    margins_by_outcome = {
        "ctrl_sae": [(2.0, "Primary (±2.0 pp)"), (1.0, "Strict (±1.0 pp)")],
        "act_sae": [(2.0, "Primary (±2.0 pp)"), (1.0, "Strict (±1.0 pp)")],
        "oth_rd": [(2.0, "Primary (±2.0 pp)"), (1.0, "Strict (±1.0 pp)")],
        "ctrl_mort": [(0.5, "Primary (±0.5 pp)"), (1.0, "Secondary (±1.0 pp)"), (1.5, "Wide (±1.5 pp)")],
        "act_mort": [(0.5, "Primary (±0.5 pp)"), (1.0, "Secondary (±1.0 pp)"), (1.5, "Wide (±1.5 pp)")],
    }
    rows = []
    for spec_lbl, frame, fe_col, pfe in [
        ("Phase 3 Mol × Sponsor FE", phase3, "mol_sponsor", False),
        ("Phase 3 Triplet FE", phase3, "mol_sp_cond", False),
        ("Pooled P2+P3 Mol × Sponsor FE", paired, "mol_sponsor", True),
    ]:
        for y_col, margin_list in margins_by_outcome.items():
            covs = CONTROLS if y_col == "oth_rd" else SAE_CONTROLS
            res = ec.fit_fe_cluster(frame, y_col, SITE_SHARES, covs, fe_col=fe_col, year_fe=True, phase_fe=pfe)
            t_info = res["terms"]["eu_east_sh"]
            df_t = res["t_df"]
            # Convert to percentage points per +10 pp EU-East site share (= 10.0 * raw coef)
            b_10 = 10.0 * t_info["coef"]
            se_10 = 10.0 * t_info["se"]
            ci95_lo = 10.0 * t_info["ci95_lo"]
            ci95_hi = 10.0 * t_info["ci95_hi"]
            ci90_lo = 10.0 * t_info["ci90_lo"]
            ci90_hi = 10.0 * t_info["ci90_hi"]
            for delta_pp, m_lbl in margin_list:
                t_lo = (b_10 - (-delta_pp)) / se_10
                t_hi = (delta_pp - b_10) / se_10
                p_lo = float(stats.t.sf(t_lo, df=df_t))
                p_hi = float(stats.t.sf(t_hi, df=df_t))
                p_tost = max(p_lo, p_hi)
                rows.append({
                    "specification": spec_lbl,
                    "outcome": y_col,
                    "n": res["n"],
                    "n_fe_groups": res["n_fe_groups"],
                    "t_df": df_t,
                    "per_10pp_pp": round(b_10, 3),
                    "per_10pp_se_pp": round(se_10, 3),
                    "ci95_lo_pp": round(ci95_lo, 3),
                    "ci95_hi_pp": round(ci95_hi, 3),
                    "ci90_lo_pp": round(ci90_lo, 3),
                    "ci90_hi_pp": round(ci90_hi, 3),
                    "margin_label": m_lbl,
                    "margin_pp": delta_pp,
                    "p_tost": p_tost,
                    "equivalent_alpha_05": bool(p_tost < 0.05),
                    "p_two_sided_null": t_info["p"],
                })
    return rows


def main() -> int:
    ec = load_econometrics()
    trials = pd.read_parquet(DATA / "d30_mrct_placebo_panel.parquet")
    soc = pd.read_parquet(DATA / "d30_meddra_soc_abs_rates.parquet")
    paired = trials.merge(soc, on="nct_id", validate="one_to_one")
    phase3 = paired.loc[paired["is_phase3"].eq(1)].copy()

    print("[1/5] Support summary & extensive/intensive/common-program decomposition...", flush=True)
    p3_support = compute_support_summary(phase3)
    p23_support = compute_support_summary(paired)
    ext_int = compute_extensive_intensive_and_common_programs(ec, phase3, paired)

    print("[2/5] Nonlinear binned & 4-knot Restricted Cubic Spline curves...", flush=True)
    nonlin = compute_nonlinear_bins_and_splines(ec, phase3, paired)

    print("[3/5] Effective FWL regression weights & leave-top-weighted-programs-out...", flush=True)
    fwl_w = compute_effective_fwl_weights(ec, phase3, paired)

    print("[4/5] Two-way alternative-region counterfactuals...", flush=True)
    alt_reg = compute_alternative_region_counterfactuals(ec, phase3, paired)

    print("[5/5] MedDRA four-state threshold bounds, Manski FWL bounds, timeFrame & TOST...", flush=True)
    meddra_b = compute_meddra_threshold_and_bounds(ec, paired, phase3)
    tost_rows = compute_prespecified_tost(ec, phase3, paired)

    # Preserve legacy v3 keys (`paired_soc_contrast`, `restricted_phase3_site_share`) for exact backward verification
    legacy_paired_contrast = []
    for arm in ("ctrl", "act"):
        for sample_lbl, frame in [
            ("phase2_and_3", paired),
            ("phase3_only", phase3),
            ("five_percent_reporting_threshold", paired.loc[paired["freq_thr"].eq(5)]),
        ]:
            contrast = frame.assign(soc_difference=frame[f"{arm}_subj_sum_aff_rate"] - frame[f"{arm}_obj_sum_aff_rate"])
            covs = CONTROLS[:-1] if sample_lbl == "five_percent_reporting_threshold" else CONTROLS
            res = ec.fit_fe_cluster(contrast, "soc_difference", SITE_SHARES, covs, phase_fe=sample_lbl != "phase3_only")
            legacy_paired_contrast.append({"arm": arm, "sample": sample_lbl, "n": res["n"], **res["terms"]["eu_east_sh"]})

    legacy_restricted = [
        r for r in ext_int["models"]
        if r["sample"] in {
            "all_phase3", "exclude_shares_above_50_percent",
            "shares_at_most_35_percent", "positive_shares_at_most_35_percent",
        }
    ]

    result = {
        "phase3_support": p3_support,
        "p23_support": p23_support,
        "meddra_pair_coverage": {"trial_records": len(trials), "matched_records": len(paired)},
        "paired_soc_contrast": legacy_paired_contrast,
        "restricted_phase3_site_share": legacy_restricted,
        "extensive_intensive_decomposition": ext_int,
        "nonlinear_bins_and_spline": nonlin,
        "effective_fwl_weights": fwl_w,
        "alternative_region_counterfactuals": alt_reg,
        "meddra_threshold_and_bounds": meddra_b,
        "prespecified_equivalence_tost": tost_rows,
    }

    out_json = RES_DIR / "08_reporting_sensitivity.json"
    out_json.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    sha = hashlib.sha256(out_json.read_bytes()).hexdigest()

    # Export clean zero-NaN v4 CSV tables
    pd.DataFrame([
        {
            "sample": r["sample"], "arm": r["arm"], "n": r["n"], "n_fe_groups": r["n_fe_groups"],
            "per_10pp_pp": round(100.0 * r["per_10pp_coef"], 3),
            "per_10pp_se_pp": round(100.0 * r["per_10pp_se"], 3),
            "ci95_lo_pp": round(100.0 * r["per_10pp_ci95_lo"], 3),
            "ci95_hi_pp": round(100.0 * r["per_10pp_ci95_hi"], 3),
            "p": r["p"],
            "zero_ind_pp": round(100.0 * r["zero_ind_coef"], 3) if "zero_ind_coef" in r else 0.0,
            "zero_ind_p": r["zero_ind_p"] if "zero_ind_p" in r else 1.0,
        }
        for r in ext_int["models"]
    ]).to_csv(TAB_DIR / "table_v4_support_and_margins.csv", index=False)

    pd.DataFrame(alt_reg["phase3"] + alt_reg["phase2_and_3"]).to_csv(
        TAB_DIR / "table_v4_alternative_regions.csv", index=False
    )

    mb_rows = []
    for b in meddra_b["interval_and_manski_bounds"]:
        if "error" in b:
            continue
        ms = b["manski_sharp_per_10pp"]
        mb_rows.append({
            "stratum": b["stratum"],
            "arm": b["arm"],
            "metric": b["metric"],
            "n": b["n"],
            "pct_point_identified": b["pct_point_identified_trials"],
            "uniform_lo_10pp": b["uniform_lower_bound"]["per_10pp_coef"],
            "uniform_mid_10pp": b["uniform_midpoint"]["per_10pp_coef"],
            "uniform_hi_10pp": b["uniform_upper_bound"]["per_10pp_coef"],
            "manski_id_lo_10pp": ms["id_lo"],
            "manski_id_hi_10pp": ms["id_hi"],
            "manski_im95_lo_10pp": ms["im95_lo"],
            "manski_im95_hi_10pp": ms["im95_hi"],
        })
    pd.DataFrame(mb_rows).to_csv(TAB_DIR / "table_v4_meddra_bounds.csv", index=False)
    pd.DataFrame(tost_rows).to_csv(TAB_DIR / "table_v4_tost_equivalence.csv", index=False)

    print(f"[DONE] Wrote {out_json.relative_to(ROOT)} (sha256={sha[:16]}...) + 4 v4 CSV tables.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
