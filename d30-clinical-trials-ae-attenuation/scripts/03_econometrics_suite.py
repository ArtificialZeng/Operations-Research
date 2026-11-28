"""Complete Econometric & Sensitivity Suite for D30 /boost.

Executes Blocks A-E on the full ClinicalTrials.gov v2 Phase 2 + Phase 3 universe:
  Block A: Core Twin-Trial FE (Mol x Sponsor, Mol x Primary-Condition, Mol x Sp x Cond)
           across Phase 3 alone, Phase 2 standalone OOS, and Pooled Phase 2+3.
  Block B: Protocol/Reporting Rules (freq_thr == 5%, freq_thr == 0%, SYSTEMATIC_ASSESSMENT),
           Survivorship Bias (incl. TERMINATED), Active-Comparator OOS, Therapeutic Areas,
           Leave-One-Country-Out & Leave-One-Sponsor-Out, MedDRA SOC & Parser sensitivity.
  Block C: Post-2017 Asymmetric Convergence & FDAAA Final Rule (42 CFR Part 11) vs ICH E6(R2)
           horse-race decomposition, oth_rd shift test, and dynamic event study.
  Block D: Feb 24, 2022 Russia-Ukraine War exogenous site-reallocation DiD & reduced form.
  Block E: Site-Share vs Patient-Accrual empirical velocity estimation & EIV/nonlinear bounds.

Outputs:
  - results/d30_econometrics_results.json (full machine-readable verified receipts)
  - tables/table1_core_twin_trial.csv
  - tables/table2_sensitivity_subsamples.csv
  - tables/table3_post2017_fdaaa_decomposition.csv
  - tables/table4_war2022_and_accrual_bounds.csv
"""
from __future__ import annotations

import hashlib
import json
import sys
import warnings
from collections import deque
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

BASE_DIR = Path(__file__).resolve().parents[1]
PROC_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"
TAB_DIR = BASE_DIR / "tables"
RES_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)


def _prune_twoway_connected(sub: pd.DataFrame, fe_col: str, year_col: str = "start_year") -> pd.DataFrame:
    """Iteratively prune singleton fe_col cells and keep largest connected (fe_col, year_col) component.

    Guarantees exact full column rank for two-way fixed effects C(fe_col) + C(start_year)
    following Abowd-Kramarz-Margolis (AKM) / reghdfe identification.
    """
    cur = sub.copy()
    while True:
        prev_len = len(cur)
        counts = cur[fe_col].value_counts()
        cur = cur[cur[fe_col].isin(counts[counts >= 2].index)].copy()
        if len(cur) < 10:
            return cur
        if cur[year_col].nunique() <= 1 or cur[fe_col].nunique() <= 1:
            break
        # Build bipartite graph between fe_col nodes and year_col nodes
        adj: dict[tuple[str, object], set[tuple[str, object]]] = {}
        for g_val, y_val in zip(cur[fe_col].tolist(), cur[year_col].tolist(), strict=False):
            u = ("F", g_val)
            v = ("Y", y_val)
            adj.setdefault(u, set()).add(v)
            adj.setdefault(v, set()).add(u)
        visited: set[tuple[str, object]] = set()
        components: list[set[tuple[str, object]]] = []
        for node in adj:
            if node in visited:
                continue
            comp: set[tuple[str, object]] = set()
            q = deque([node])
            visited.add(node)
            while q:
                x = q.popleft()
                comp.add(x)
                for nb in adj[x]:
                    if nb not in visited:
                        visited.add(nb)
                        q.append(nb)
            components.append(comp)
        if len(components) <= 1:
            break
        # Keep the connected component with the largest number of observations
        best_f: set[object] = set()
        best_n = -1
        for comp in components:
            f_nodes = {val for kind, val in comp if kind == "F"}
            n_obs = int(cur[fe_col].isin(f_nodes).sum())
            if n_obs > best_n:
                best_n = n_obs
                best_f = f_nodes
        cur = cur[cur[fe_col].isin(best_f)].copy()
        if len(cur) == prev_len:
            break
    return cur


def fit_fe_cluster(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    cov_cols: list[str],
    fe_col: str | None = "mol_sponsor",
    year_fe: bool = True,
    phase_fe: bool = False,
    extra_fe_cols: list[str] | None = None,
    cluster_col: str = "sponsor_nm",
    weights_col: str | None = None,
) -> dict:
    """Fit FE OLS/WLS with finite-sample cluster-robust t(G-1) SEs and exact full-rank hygiene."""
    req = [y_col] + x_cols + cov_cols + ([fe_col] if fe_col else []) + (["start_year"] if year_fe else [])
    if phase_fe:
        req.append("phase_group")
    if extra_fe_cols:
        req.extend(extra_fe_cols)
    if cluster_col:
        req.append(cluster_col)
    if weights_col:
        req.append(weights_col)
    req = list(dict.fromkeys(req))

    sub = df.dropna(subset=req).copy()
    if fe_col:
        sub = sub[sub[fe_col].astype(str) != ""].copy()
        if year_fe:
            sub = _prune_twoway_connected(sub, fe_col, "start_year")
        else:
            counts = sub[fe_col].value_counts()
            sub = sub[sub[fe_col].isin(counts[counts >= 2].index)].copy()

    if len(sub) < 30:
        return {"n": len(sub), "error": "insufficient_n"}

    # Keep only covariates with non-zero variation (and within-FE variation when fe_col is absorbed!)
    if fe_col:
        active_covs = [
            c for c in cov_cols
            if sub[c].nunique(dropna=True) > 1 and bool(sub.groupby(fe_col)[c].nunique(dropna=True).gt(1).any())
        ]
    else:
        active_covs = [c for c in cov_cols if sub[c].nunique(dropna=True) > 1]
    active_xs = [c for c in x_cols if sub[c].nunique(dropna=True) > 1]
    if not active_xs:
        return {"n": len(sub), "error": "no_x_variation"}

    # Build FE + covariate formula; drop any covariate linearly spanned by FE dummies (exact full rank!)
    fe_terms: list[str] = []
    if year_fe and sub["start_year"].nunique() > 1:
        fe_terms.append("C(start_year)")
    if phase_fe and sub["phase_group"].nunique() > 1:
        fe_terms.append("C(phase_group)")
    if extra_fe_cols:
        for efe in extra_fe_cols:
            if sub[efe].nunique() > 1:
                fe_terms.append(f"C({efe})")
    if fe_col and sub[fe_col].nunique() > 1:
        fe_terms.append(f"C({fe_col})")

    if fe_terms and active_covs:
        # Check exact collinearity of each scalar covariate against FE design matrix once
        fe_mod = smf.ols(f"{y_col} ~ " + " + ".join(fe_terms), data=sub)
        Q_fe, _ = np.linalg.qr(fe_mod.exog, mode="reduced")
        kept_covs: list[str] = []
        for c in active_covs:
            v = sub[c].to_numpy(dtype=float)
            resid = v - Q_fe @ (Q_fe.T @ v)
            if float(np.linalg.norm(resid)) > 1e-7 * max(1.0, float(np.linalg.norm(v))):
                kept_covs.append(c)
        active_covs = kept_covs

    rhs_terms = active_xs + active_covs + fe_terms
    formula = f"{y_col} ~ " + " + ".join(rhs_terms)
    n_clusters = int(sub[cluster_col].nunique()) if cluster_col else 0

    try:
        if weights_col:
            mod = smf.wls(formula, data=sub, weights=sub[weights_col])
        else:
            mod = smf.ols(formula, data=sub)
        if cluster_col and n_clusters >= 10:
            fit = mod.fit(
                cov_type="cluster",
                cov_kwds={"groups": sub[cluster_col], "df_correction": True},
                use_t=True,
            )
            se_type = f"cluster:{cluster_col}"
            t_df = max(1, n_clusters - 1)
        else:
            fit = mod.fit(cov_type="HC3", use_t=True)
            se_type = "HC3"
            t_df = max(1, int(fit.df_resid))
    except (ValueError, np.linalg.LinAlgError, KeyError, ZeroDivisionError, RuntimeError) as exc:
        return {"n": len(sub), "error": str(exc)[:180]}

    t_crit = float(stats.t.ppf(0.975, df=t_df))
    t_crit_90 = float(stats.t.ppf(0.95, df=t_df))
    mat_rank = round(float(fit.df_model)) + 1
    out: dict = {
        "n": int(fit.nobs),
        "n_fe_groups": int(sub[fe_col].nunique()) if fe_col else 0,
        "n_clusters": n_clusters,
        "n_params": len(fit.params),
        "matrix_rank": mat_rank,
        "is_full_rank": bool(mat_rank == len(fit.params)),
        "se_type": se_type,
        "use_t": bool(fit.use_t),
        "t_df": int(t_df),
        "r2": round(float(fit.rsquared), 4),
        "y_mean": round(float(sub[y_col].mean()), 5),
        "y_sd": round(float(sub[y_col].std()), 5),
        "terms": {},
    }
    for term in active_xs:
        if term in fit.params.index:
            coef = float(fit.params[term])
            se = float(fit.bse[term])
            tval = float(fit.tvalues[term])
            pval = float(fit.pvalues[term])
            if not (np.isfinite(coef) and np.isfinite(se) and se > 0 and np.isfinite(pval)):
                continue
            ci95_lo = coef - t_crit * se
            ci95_hi = coef + t_crit * se
            ci90_lo = coef - t_crit_90 * se
            ci90_hi = coef + t_crit_90 * se
            out["terms"][term] = {
                "coef": round(coef, 5),
                "se": round(se, 5),
                "t": round(tval, 3),
                "p": pval,
                "ci95_lo": round(ci95_lo, 5),
                "ci95_hi": round(ci95_hi, 5),
                "ci90_lo": round(ci90_lo, 5),
                "ci90_hi": round(ci90_hi, 5),
                "tost_90_margin": round(max(abs(ci90_lo), abs(ci90_hi)), 5),
                "excludable_95_abs": round(max(abs(ci95_lo), abs(ci95_hi)), 5),
                "per_10pp_coef": round(0.10 * coef, 5),
                "per_10pp_se": round(0.10 * se, 5),
                "per_10pp_ci95_lo": round(0.10 * ci95_lo, 5),
                "per_10pp_ci95_hi": round(0.10 * ci95_hi, 5),
            }
    return out


def fit_twoway_and_wildboot(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    target_term: str,
    cov_cols: list[str],
    fe_col: str = "mol_sponsor",
    year_fe: bool = True,
    phase_fe: bool = False,
    cl1_col: str = "sponsor_nm",
    cl2_col: str = "primary_molecule",
    n_boot: int = 999,
    seed: int = 20261125,
) -> dict:
    """Compute Cameron-Gelbach-Miller two-way clustered SEs and Rademacher wild cluster bootstrap p-value."""
    req = list(dict.fromkeys(
        [y_col] + x_cols + cov_cols + [fe_col, cl1_col, cl2_col]
        + (["start_year"] if year_fe else [])
        + (["phase_group"] if phase_fe else [])
    ))
    sub = df.dropna(subset=req).copy()
    sub = sub[(sub[fe_col].astype(str) != "") & (sub[cl2_col].astype(str) != "")].copy()
    sub = _prune_twoway_connected(sub, fe_col, "start_year") if year_fe else sub
    if len(sub) < 40:
        return {"n": len(sub), "error": "insufficient_n"}

    active_covs = [
        c for c in cov_cols
        if sub[c].nunique(dropna=True) > 1 and bool(sub.groupby(fe_col)[c].nunique(dropna=True).gt(1).any())
    ]
    rhs_terms = x_cols + active_covs
    if year_fe and sub["start_year"].nunique() > 1:
        rhs_terms.append("C(start_year)")
    if phase_fe and sub["phase_group"].nunique() > 1:
        rhs_terms.append("C(phase_group)")
    if sub[fe_col].nunique() > 1:
        rhs_terms.append(f"C({fe_col})")

    formula = f"{y_col} ~ " + " + ".join(rhs_terms)
    mod = smf.ols(formula, data=sub)
    f1 = mod.fit(cov_type="cluster", cov_kwds={"groups": sub[cl1_col], "df_correction": True}, use_t=True)
    f2 = mod.fit(cov_type="cluster", cov_kwds={"groups": sub[cl2_col], "df_correction": True}, use_t=True)
    inter_grp = sub[cl1_col].astype(str) + "||" + sub[cl2_col].astype(str)
    f12 = mod.fit(cov_type="cluster", cov_kwds={"groups": inter_grp, "df_correction": True}, use_t=True)

    coef = float(f1.params[target_term])
    v1 = float(f1.bse[target_term] ** 2)
    v2 = float(f2.bse[target_term] ** 2)
    v12 = float(f12.bse[target_term] ** 2)
    # CGM two-way variance with standard positive-variance safeguard max(v1, v2) if v1+v2-v12 <= 0
    v_2way = v1 + v2 - v12
    if v_2way <= 0:
        v_2way = max(v1, v2)
    se_2way = float(np.sqrt(v_2way))
    g1 = int(sub[cl1_col].nunique())
    g2 = int(sub[cl2_col].nunique())
    df_2way = max(1, min(g1, g2) - 1)
    t_2way = coef / se_2way
    p_2way = float(2.0 * stats.t.sf(abs(t_2way), df=df_2way))

    # Fast exact restricted Rademacher Wild Cluster Bootstrap (WCR-t, Cameron-Gelbach-Miller 2008)
    # Using Frisch-Waugh-Lovell projection of target_term and y on all other regressors Z
    X_full = mod.exog
    idx_t = mod.exog_names.index(target_term)
    x_t = X_full[:, idx_t]
    Z = np.delete(X_full, idx_t, axis=1)
    y_vec = mod.endog
    # Restricted OLS under H0: beta_target = 0
    beta_r, _, _, _ = np.linalg.lstsq(Z, y_vec, rcond=None)
    e_r = y_vec - Z @ beta_r
    # FWL residualized x_tilde = M_Z x_t
    gamma_x, _, _, _ = np.linalg.lstsq(Z, x_t, rcond=None)
    x_tilde = x_t - Z @ gamma_x
    denom = float(x_tilde @ x_tilde)
    N, K = X_full.shape
    dfc = ((N - 1) / max(1, N - K)) * (g1 / max(1, g1 - 1))

    # Map observations to sponsor clusters 0..g1-1
    _, cl_codes = np.unique(sub[cl1_col].astype(str).to_numpy(), return_inverse=True)

    # Observed cluster-t using exact same FWL score formula
    u_obs = f1.resid.to_numpy()
    sc_obs = np.bincount(cl_codes, weights=x_tilde * u_obs, minlength=g1)
    se_obs_fwl = float(np.sqrt(dfc * float(sc_obs @ sc_obs)) / denom)
    t_obs_abs = abs(coef / se_obs_fwl)

    rng = np.random.default_rng(seed)
    # Precompute cluster-level contributions under Rademacher weights v_g in {-1, +1}
    # Note: y*_b = Z beta_r + v_{g(i)} e_r => M_Z y*_b = M_Z (v e_r); since x_tilde is orthogonal to Z,
    # x_tilde' y*_b = sum_g v_g * (sum_{i in g} x_tilde_i e_{r,i})!
    # And for the residual u*_b = M_Z (v e_r) - b*_b x_tilde, we evaluate fast via Q_Z (orthonormal basis of Z).
    Q_z, _ = np.linalg.qr(Z, mode="reduced")
    V_mat = rng.choice([-1.0, 1.0], size=(g1, n_boot))
    W_obs = V_mat[cl_codes, :] * e_r[:, None]  # (N, B)
    # Project out Z: E_proj = W_obs - Q_z @ (Q_z.T @ W_obs)
    E_proj = W_obs - Q_z @ (Q_z.T @ W_obs)
    b_star = (x_tilde @ E_proj) / denom  # (B,)
    U_star = E_proj - np.outer(x_tilde, b_star)  # (N, B)
    # Cluster score matrix (g1, B) via indicator matrix G_ind
    G_ind = np.zeros((g1, N), dtype=float)
    G_ind[cl_codes, np.arange(N)] = x_tilde
    SC_star = G_ind @ U_star  # (g1, B)
    se_star = np.sqrt(dfc * np.sum(SC_star ** 2, axis=0)) / denom
    t_star_abs = np.abs(b_star / np.maximum(se_star, 1e-12))
    p_wild = float((1 + np.sum(t_star_abs >= t_obs_abs)) / (n_boot + 1))

    return {
        "n": int(N),
        "g_sponsor": g1,
        "g_molecule": g2,
        "coef": round(coef, 5),
        "se_sponsor": round(float(f1.bse[target_term]), 5),
        "p_sponsor_t": float(f1.pvalues[target_term]),
        "se_molecule": round(float(f2.bse[target_term]), 5),
        "p_molecule_t": float(f2.pvalues[target_term]),
        "se_twoway": round(se_2way, 5),
        "t_twoway": round(t_2way, 3),
        "p_twoway": p_2way,
        "p_wild_rademacher_999": round(p_wild, 5),
    }


def compute_fwl_binscatter(
    df: pd.DataFrame,
    x_col: str,
    y_cols: list[str],
    other_reg_cols: list[str],
    base_covs: list[str],
    sae_covs: list[str],
    fe_col: str = "mol_sponsor",
    phase_fe: bool = True,
    n_bins: int = 10,
) -> dict:
    """Exact Frisch-Waugh-Lovell residualized binned scatter matching full Twin-Trial specification."""
    req = list(dict.fromkeys(
        [x_col] + y_cols + other_reg_cols + base_covs + [fe_col, "start_year"]
        + (["phase_group"] if phase_fe else [])
    ))
    sub = df.dropna(subset=req).copy()
    sub = sub[sub[fe_col].astype(str) != ""].copy()
    sub = _prune_twoway_connected(sub, fe_col, "start_year")

    def build_rhs(covs: list[str]) -> str:
        active = [c for c in other_reg_cols + covs if sub[c].nunique() > 1]
        terms = active + ["C(start_year)"]
        if phase_fe and sub["phase_group"].nunique() > 1:
            terms.append("C(phase_group)")
        terms.append(f"C({fe_col})")
        return " + ".join(terms)

    rhs_oth = build_rhs(base_covs)
    rhs_sae = build_rhs(sae_covs)

    # Residualize X and each Y against the EXACT matching control set
    x_res_raw = smf.ols(f"{x_col} ~ {rhs_oth}", data=sub).fit().resid
    sub["_x_res"] = x_res_raw + sub[x_col].mean()
    fwl_slopes: dict[str, float] = {}
    for y in y_cols:
        use_rhs = rhs_oth if ("oth" in y or "terms" in y) else rhs_sae
        x_for_y = x_res_raw if use_rhs == rhs_oth else smf.ols(f"{x_col} ~ {use_rhs}", data=sub).fit().resid
        y_res_raw = smf.ols(f"{y} ~ {use_rhs}", data=sub).fit().resid
        sub[f"_{y}_res"] = y_res_raw + sub[y].mean()
        fwl_slopes[y] = round(float((x_for_y @ y_res_raw) / (x_for_y @ x_for_y)), 5)

    sub["_bin"] = pd.qcut(sub["_x_res"], q=n_bins, duplicates="drop")
    bins_out = []
    for _, grp in sub.groupby("_bin", observed=True):
        row = {
            "n": len(grp),
            "x_mean": round(float(grp["_x_res"].mean()), 5),
        }
        for y in y_cols:
            m = float(grp[f"_{y}_res"].mean())
            se = float(grp[f"_{y}_res"].std(ddof=1) / np.sqrt(len(grp))) if len(grp) > 1 else 0.0
            row[f"{y}_mean"] = round(m, 5)
            row[f"{y}_se"] = round(se, 5)
        bins_out.append(row)
    return {
        "n_total": len(sub),
        "n_fe_groups": int(sub[fe_col].nunique()),
        "fwl_exact_slopes": fwl_slopes,
        "bins": bins_out,
    }


def main() -> int:
    print("[START] Loading analytic panels...", flush=True)
    df_all = pd.read_parquet(PROC_DIR / "d30_all_trials.parquet")
    df_p23 = pd.read_parquet(PROC_DIR / "d30_mrct_placebo_panel.parquet")
    df_allst = pd.read_parquet(PROC_DIR / "d30_mrct_placebo_allstatus.parquet")

    soc_abs_path = PROC_DIR / "d30_meddra_soc_abs_rates.parquet"
    if soc_abs_path.exists():
        df_soc_abs = pd.read_parquet(soc_abs_path)
        df_p23 = df_p23.merge(df_soc_abs, on="nct_id", how="left")

    df_p3 = df_p23[df_p23["is_phase3"] == 1].copy()
    df_p2 = df_p23[df_p23["is_phase2_only"] == 1].copy()

    base_covs = ["log_enroll", "log_sites", "log_countries", "dur_yr", "is_double_blind", "freq_thr"]
    sae_covs = ["log_enroll", "log_sites", "log_countries", "dur_yr", "is_double_blind"]
    reg_xs_split = ["eu_east_sh", "ru_ua_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"]
    reg_xs_pool_ee = ["ee_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"]

    results: dict = {
        "sample_overview": {
            "p23_completed_mrct_placebo": len(df_p23),
            "p3_completed_mrct_placebo": len(df_p3),
            "p2_standalone_completed_mrct_placebo": len(df_p2),
            "p23_allstatus_mrct_placebo": len(df_allst),
            "p3_unique_sponsors": int(df_p3["sponsor_nm"].nunique()),
            "p3_unique_molecules": int(df_p3[df_p3["primary_molecule"] != ""]["primary_molecule"].nunique()),
            "p23_unique_sponsors": int(df_p23["sponsor_nm"].nunique()),
            "p23_unique_molecules": int(df_p23[df_p23["primary_molecule"] != ""]["primary_molecule"].nunique()),
            "p3_mean_shares": {
                k: round(float(df_p3[k].mean()), 4)
                for k in ["us_sh", "we_sh", "eu_east_sh", "ru_ua_sh", "ee_sh", "latam_sh", "asia_sh", "other_sh"]
            },
            "p23_mean_rates": {
                k: round(float(df_p23[k].mean()), 4)
                for k in ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae", "act_sae", "sae_rd", "ctrl_mort", "act_mort"]
            },
        },
        "block_a_core_twin_trial": {},
        "block_b_sensitivity_robustness": {},
        "block_c_post2017_fdaaa_decomposition": {},
        "block_d_war2022_shock": {},
        "block_e_site_vs_patient_bounds": {},
        "binscatter_data": {},
    }

    # =========================================================================
    # BLOCK A: CORE TWIN-TRIAL IDENTIFICATION (P3, P2 OOS, Pooled P2+P3)
    # =========================================================================
    print("[Block A] Core Twin-Trial Identification...", flush=True)
    outcomes_all = [
        "ctrl_oth", "act_oth", "oth_rd", "oth_log_rr",
        "ctrl_sae", "act_sae", "sae_rd", "sae_log_rr",
        "ctrl_mort", "act_mort", "mort_rd",
        "n_other_terms", "log_other_terms",
        "ctrl_oth_minus_sae", "act_oth_minus_sae", "log_ctrl_oth_to_sae",
    ]

    def run_battery(sub_df: pd.DataFrame, fe_col: str, phase_fe: bool, x_spec: list[str], cl_col: str = "sponsor_nm") -> dict:
        out = {}
        for y in outcomes_all:
            covs = base_covs if ("oth" in y or "terms" in y) else sae_covs
            out[y] = fit_fe_cluster(sub_df, y, x_spec, covs, fe_col=fe_col, year_fe=True, phase_fe=phase_fe, cluster_col=cl_col)
        return out

    # 1. Phase 3 Same-Molecule x Same-Sponsor (split EU-East/RU-UA AND pooled EE, plus molecule-clustered SEs)
    results["block_a_core_twin_trial"]["p3_mol_sponsor_split"] = run_battery(df_p3, "mol_sponsor", False, reg_xs_split)
    results["block_a_core_twin_trial"]["p3_mol_sponsor_ee"] = run_battery(df_p3, "mol_sponsor", False, reg_xs_pool_ee)
    results["block_a_core_twin_trial"]["p3_mol_sponsor_split_molcluster"] = run_battery(df_p3, "mol_sponsor", False, reg_xs_split, cl_col="primary_molecule")

    # 2. Phase 3 Same-Molecule x Same-Primary-Condition (exact replicate twins)
    results["block_a_core_twin_trial"]["p3_mol_cond_split"] = run_battery(df_p3, "mol_cond", False, reg_xs_split)
    results["block_a_core_twin_trial"]["p3_mol_cond_ee"] = run_battery(df_p3, "mol_cond", False, reg_xs_pool_ee)

    # 3. Ultra-strict Phase 3 Same-Molecule x Same-Sponsor x Same-Primary-Condition Triplet FE
    results["block_a_core_twin_trial"]["p3_mol_sp_cond_split"] = run_battery(df_p3, "mol_sp_cond", False, reg_xs_split)
    results["block_a_core_twin_trial"]["p3_mol_sp_cond_ee"] = run_battery(df_p3, "mol_sp_cond", False, reg_xs_pool_ee)

    # 4. Phase 2 Standalone Out-of-Sample Replication!
    results["block_a_core_twin_trial"]["p2_standalone_mol_sponsor_split"] = run_battery(df_p2, "mol_sponsor", False, reg_xs_split)
    results["block_a_core_twin_trial"]["p2_standalone_mol_sponsor_ee"] = run_battery(df_p2, "mol_sponsor", False, reg_xs_pool_ee)
    results["block_a_core_twin_trial"]["p2_standalone_sp_cond_ee"] = run_battery(df_p2, "sp_cond", False, reg_xs_pool_ee)
    results["block_a_core_twin_trial"]["p2_standalone_ta_fe_split"] = run_battery(df_p2, "therapeutic_area", False, reg_xs_split)

    # 5. Pooled Phase 2 + Phase 3 (with C(phase_group) FE)
    results["block_a_core_twin_trial"]["p23_mol_sponsor_split"] = run_battery(df_p23, "mol_sponsor", True, reg_xs_split)
    results["block_a_core_twin_trial"]["p23_mol_sponsor_ee"] = run_battery(df_p23, "mol_sponsor", True, reg_xs_pool_ee)
    results["block_a_core_twin_trial"]["p23_mol_cond_split"] = run_battery(df_p23, "mol_cond", True, reg_xs_split)
    results["block_a_core_twin_trial"]["p23_mol_cond_ee"] = run_battery(df_p23, "mol_cond", True, reg_xs_pool_ee)
    results["block_a_core_twin_trial"]["p23_mol_sp_cond_split"] = run_battery(df_p23, "mol_sp_cond", True, reg_xs_split)
    results["block_a_core_twin_trial"]["p23_mol_sp_cond_ee"] = run_battery(df_p23, "mol_sp_cond", True, reg_xs_pool_ee)
    results["block_a_core_twin_trial"]["p23_sp_cond_split"] = run_battery(df_p23, "sp_cond", True, reg_xs_split)

    # 6. Cameron-Gelbach-Miller Two-Way Clustering (Sponsor x Molecule) + Rademacher Wild Cluster Bootstrap (B=999)
    print("  [Block A-Inf] Two-way clustering & Rademacher wild cluster bootstrap (B=999)...", flush=True)
    results["block_a_core_twin_trial"]["twoway_and_wildboot_inference"] = {
        "p3_mol_sp_ctrl_oth_eu_east": fit_twoway_and_wildboot(
            df_p3, "ctrl_oth", reg_xs_split, "eu_east_sh", base_covs, fe_col="mol_sponsor", phase_fe=False
        ),
        "p3_mol_sp_act_oth_eu_east": fit_twoway_and_wildboot(
            df_p3, "act_oth", reg_xs_split, "eu_east_sh", base_covs, fe_col="mol_sponsor", phase_fe=False
        ),
        "p23_mol_sp_ctrl_oth_eu_east": fit_twoway_and_wildboot(
            df_p23, "ctrl_oth", reg_xs_split, "eu_east_sh", base_covs, fe_col="mol_sponsor", phase_fe=True
        ),
        "p23_mol_sp_act_oth_eu_east": fit_twoway_and_wildboot(
            df_p23, "act_oth", reg_xs_split, "eu_east_sh", base_covs, fe_col="mol_sponsor", phase_fe=True
        ),
        "p3_triplet_ctrl_oth_eu_east": fit_twoway_and_wildboot(
            df_p3, "ctrl_oth", reg_xs_split, "eu_east_sh", base_covs, fe_col="mol_sp_cond", phase_fe=False
        ),
        "p3_triplet_act_oth_eu_east": fit_twoway_and_wildboot(
            df_p3, "act_oth", reg_xs_split, "eu_east_sh", base_covs, fe_col="mol_sp_cond", phase_fe=False
        ),
    }

    # Raw quartiles of EE share inside strict freq_thr == 5% (P3 & P2+P3)
    raw_q = {}
    for tag, sub in [("p3_freq5", df_p3[df_p3["freq_thr"] == 5.0]), ("p23_freq5", df_p23[df_p23["freq_thr"] == 5.0])]:
        raw_q[tag] = {}
        for lbl, m in [
            ("EE_0pct", sub["ee_sh"] == 0),
            ("EE_0_15pct", (sub["ee_sh"] > 0) & (sub["ee_sh"] < 0.15)),
            ("EE_15_30pct", (sub["ee_sh"] >= 0.15) & (sub["ee_sh"] < 0.30)),
            ("EE_ge30pct", sub["ee_sh"] >= 0.30),
        ]:
            g = sub[m]
            raw_q[tag][lbl] = {
                "n": len(g),
                "ctrl_oth_pct": round(100.0 * float(g["ctrl_oth"].mean()), 2),
                "act_oth_pct": round(100.0 * float(g["act_oth"].mean()), 2),
                "oth_rd_pp": round(100.0 * float(g["oth_rd"].mean()), 2),
                "ctrl_sae_pct": round(100.0 * float(g["ctrl_sae"].mean()), 2),
                "act_sae_pct": round(100.0 * float(g["act_sae"].mean()), 2),
                "ctrl_mort_pct": round(100.0 * float(g["ctrl_mort"].mean()), 2) if g["ctrl_mort"].notna().any() else None,
            }
    results["block_a_core_twin_trial"]["raw_ee_bins"] = raw_q

    # 7. Exact 95% CIs & Minimum Excludable Equivalence Bounds (TOST 90% & 95% CI) for Null Endpoints
    eq_bounds: dict = {}
    for spec_key in ["p3_mol_sponsor_split", "p23_mol_sponsor_split", "p3_mol_sp_cond_split"]:
        eq_bounds[spec_key] = {}
        blk_s = results["block_a_core_twin_trial"][spec_key]
        for y in ["oth_rd", "ctrl_sae", "act_sae", "ctrl_mort", "act_mort"]:
            rec_y = blk_s[y]
            t = rec_y["terms"]["eu_east_sh"]
            eq_bounds[spec_key][y] = {
                "n": rec_y["n"],
                "t_df": rec_y["t_df"],
                "coef_pp": round(100.0 * t["coef"], 2),
                "se_pp": round(100.0 * t["se"], 2),
                "p": t["p"],
                "ci95_pp": [round(100.0 * t["ci95_lo"], 2), round(100.0 * t["ci95_hi"], 2)],
                "ci90_pp": [round(100.0 * t["ci90_lo"], 2), round(100.0 * t["ci90_hi"], 2)],
                "tost_90_excludable_pp": round(100.0 * t["tost_90_margin"], 2),
                "ci95_excludable_abs_pp": round(100.0 * t["excludable_95_abs"], 2),
                "per_10pp_coef_pp": round(100.0 * t["per_10pp_coef"], 3),
                "per_10pp_ci95_pp": [round(100.0 * t["per_10pp_ci95_lo"], 2), round(100.0 * t["per_10pp_ci95_hi"], 2)],
                "per_10pp_tost_90_pp": round(10.0 * t["tost_90_margin"], 2),
            }
    results["block_a_core_twin_trial"]["null_endpoint_equivalence_bounds"] = eq_bounds

    # =========================================================================
    # BLOCK B: SENSITIVITY, PROTOCOL RULES, SURVIVORSHIP, OOS, LEAVE-ONE-OUT
    # =========================================================================
    print("[Block B] Sensitivity & Robustness Battery...", flush=True)
    sens = results["block_b_sensitivity_robustness"]
    key_ys = ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae", "act_sae"]

    # B1. Strict freq_thr == 5% (Mol x Sp FE) and strict freq_thr == 0% (TA FE & Sponsor FE — full rank!)
    for tag, sub, fe_use, pfe in [
        ("p3_freq5_mol_sp", df_p3[df_p3["freq_thr"] == 5.0], "mol_sponsor", False),
        ("p3_freq0_ta_fe", df_p3[df_p3["freq_thr"] == 0.0], "therapeutic_area", False),
        ("p23_freq5_mol_sp", df_p23[df_p23["freq_thr"] == 5.0], "mol_sponsor", True),
        ("p23_freq0_ta_fe", df_p23[df_p23["freq_thr"] == 0.0], "therapeutic_area", True),
        ("p23_freq0_sponsor_fe", df_p23[df_p23["freq_thr"] == 0.0], "sponsor_nm", True),
    ]:
        sens[tag] = {
            y: fit_fe_cluster(sub, y, reg_xs_split, sae_covs, fe_col=fe_use, year_fe=True, phase_fe=pfe)
            for y in key_ys
        }
        sens[tag + "_ee"] = {
            y: fit_fe_cluster(sub, y, reg_xs_pool_ee, sae_covs, fe_col=fe_use, year_fe=True, phase_fe=pfe)
            for y in key_ys
        }

    # B2. SYSTEMATIC_ASSESSMENT control & interaction
    df_p23_sys = df_p23.dropna(subset=["sys_assess_share"]).copy()
    df_p23_sys["ee_x_sys"] = df_p23_sys["ee_sh"] * df_p23_sys["all_systematic"]
    df_p23_sys["eu_x_sys"] = df_p23_sys["eu_east_sh"] * df_p23_sys["all_systematic"]
    df_p3_sys = df_p23_sys[df_p23_sys["is_phase3"] == 1].copy()

    sens["systematic_control_p3_mol_sp"] = {
        y: fit_fe_cluster(df_p3_sys, y, reg_xs_split, base_covs + ["sys_assess_share"], fe_col="mol_sponsor", year_fe=True, phase_fe=False)
        for y in ["ctrl_oth", "act_oth", "oth_rd"]
    }
    sens["systematic_control_p23_mol_sp"] = {
        y: fit_fe_cluster(df_p23_sys, y, reg_xs_split, base_covs + ["sys_assess_share"], fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        for y in ["ctrl_oth", "act_oth", "oth_rd"]
    }
    sens["systematic_interaction_p23_mol_sp"] = {
        y: fit_fe_cluster(
            df_p23_sys,
            y,
            ["ee_sh", "all_systematic", "ee_x_sys", "we_sh", "latam_sh", "asia_sh", "other_sh"],
            base_covs,
            fe_col="mol_sponsor",
            year_fe=True,
            phase_fe=True,
        )
        for y in ["ctrl_oth", "act_oth", "oth_rd"]
    }
    sens["systematic_only_sub_p23_mol_sp"] = {
        y: fit_fe_cluster(df_p23_sys[df_p23_sys["all_systematic"] == 1], y, reg_xs_split, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        for y in ["ctrl_oth", "act_oth"]
    }
    sens["nonsystematic_only_sub_p23_ta_fe"] = {
        y: fit_fe_cluster(df_p23_sys[df_p23_sys["all_nonsystematic"] == 1], y, reg_xs_pool_ee, base_covs, fe_col="therapeutic_area", year_fe=True, phase_fe=True)
        for y in ["ctrl_oth", "act_oth"]
    }

    # B3. Survivorship Bias Check (All-status incl. TERMINATED + termination selection check)
    sens["allstatus_incl_terminated_p23_mol_sp"] = {
        y: fit_fe_cluster(df_allst, y, reg_xs_split, base_covs if "oth" in y else sae_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        for y in ["ctrl_oth", "act_oth", "ctrl_sae"]
    }
    sens["termination_selection_check"] = fit_fe_cluster(
        df_allst, "is_terminated", reg_xs_split, sae_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True
    )

    # B4. Non-Placebo / Active-Comparator Out-of-Sample Replication
    df_nonpl = df_all[
        (df_all["is_completed"] == 1)
        & (df_all["start_year"].between(2005, 2024))
        & (df_all["enrollment"] >= 100)
        & (df_all["n_sites"] >= 5)
        & (df_all["n_countries"] >= 3)
        & (df_all["has_placebo"] == 0)
    ].copy()
    sens["non_placebo_active_comparator_oos_p23_mol_sp"] = {
        y: fit_fe_cluster(df_nonpl, y, reg_xs_split, base_covs if "oth" in y else sae_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        for y in ["trial_mean_oth", "trial_mean_sae", "trial_mean_mort"]
    }
    sens["non_placebo_active_comparator_oos_p23_ee"] = {
        y: fit_fe_cluster(df_nonpl, y, reg_xs_pool_ee, base_covs if "oth" in y else sae_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        for y in ["trial_mean_oth", "trial_mean_sae", "trial_mean_mort"]
    }

    # B5. Parser & Weighting Sensitivity (unweighted arm mean, legacy Wave-1 parser, enrollment-WLS)
    sens["unweighted_arm_mean_p3_mol_sp"] = {
        y: fit_fe_cluster(df_p3, y, reg_xs_split, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=False)
        for y in ["ctrl_oth_unw", "act_oth_unw"]
    }
    sens["legacy_placebo_parser_p3_mol_sp"] = {
        y: fit_fe_cluster(df_p3[df_p3["has_legacy_placebo"] == 1], y, reg_xs_split, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=False)
        for y in ["leg_ctrl_oth", "leg_act_oth"]
    }
    sens["enrollment_weighted_wls_p3_mol_sp"] = {
        y: fit_fe_cluster(df_p3, y, reg_xs_split, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=False, weights_col="enrollment")
        for y in ["ctrl_oth", "act_oth", "ctrl_sae"]
    }

    # B6. MedDRA SOC Composition Check (Subjective vs Objective SOC share) AND Absolute SOC Event/Term Rates!
    sens["meddra_soc_composition_p23_mol_sp"] = {
        y: fit_fe_cluster(df_p23, y, reg_xs_split, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        for y in ["subj_soc_share", "obj_soc_share", "n_other_terms", "n_serious_terms"]
    }
    abs_soc_outcomes = [
        "n_subj_terms", "n_obj_terms", "log_subj_terms", "log_obj_terms",
        "n_serious_subj_terms", "n_serious_obj_terms",
    ]
    if "ctrl_subj_sum_aff_rate" in df_p23.columns:
        abs_soc_outcomes.extend([
            "ctrl_subj_sum_aff_rate", "act_subj_sum_aff_rate",
            "ctrl_obj_sum_aff_rate", "act_obj_sum_aff_rate",
            "log_ctrl_subj_sum_aff_rate", "log_act_subj_sum_aff_rate",
            "log_ctrl_obj_sum_aff_rate", "log_act_obj_sum_aff_rate",
            "ctrl_subj_max_pct", "act_subj_max_pct",
            "ctrl_obj_max_pct", "act_obj_max_pct",
            "ctrl_subj_n_pos_terms", "act_subj_n_pos_terms",
            "ctrl_obj_n_pos_terms", "act_obj_n_pos_terms",
        ])
    sens["meddra_soc_absolute_p23_mol_sp"] = {
        y: fit_fe_cluster(
            df_p23, y, reg_xs_split,
            sae_covs if "serious" in y else base_covs,
            fe_col="mol_sponsor", year_fe=True, phase_fe=True,
        )
        for y in abs_soc_outcomes
    }
    sens["meddra_soc_absolute_p23_mol_sp_ee"] = {
        y: fit_fe_cluster(
            df_p23, y, reg_xs_pool_ee,
            sae_covs if "serious" in y else base_covs,
            fe_col="mol_sponsor", year_fe=True, phase_fe=True,
        )
        for y in abs_soc_outcomes
    }
    sens["meddra_soc_absolute_p3_mol_sp"] = {
        y: fit_fe_cluster(
            df_p3, y, reg_xs_split,
            sae_covs if "serious" in y else base_covs,
            fe_col="mol_sponsor", year_fe=True, phase_fe=False,
        )
        for y in abs_soc_outcomes
    }
    df_p23_f5 = df_p23[df_p23["freq_thr"] == 5.0].copy()
    sens["meddra_soc_absolute_p23_freq5_mol_sp"] = {
        y: fit_fe_cluster(
            df_p23_f5, y, reg_xs_split, sae_covs,
            fe_col="mol_sponsor", year_fe=True, phase_fe=True,
        )
        for y in [
            c for c in [
                "subj_soc_share", "obj_soc_share",
                "ctrl_subj_sum_aff_rate", "act_subj_sum_aff_rate",
                "ctrl_obj_sum_aff_rate", "act_obj_sum_aff_rate",
                "ctrl_subj_max_pct", "act_subj_max_pct",
                "ctrl_obj_max_pct", "act_obj_max_pct",
                "n_subj_terms", "n_obj_terms",
            ]
            if c in df_p23_f5.columns
        ]
    }

    # B7. Pan-Disease Therapeutic-Area Consistency (Pooled P2+P3, >= 50 trials)
    ta_res = {}
    for ta, grp in df_p23.groupby("therapeutic_area"):
        if len(grp) < 50:
            continue
        ta_res[ta] = {
            "n_total": len(grp),
            "mean_ee_sh": round(float(grp["ee_sh"].mean()), 4),
            "ctrl_oth": fit_fe_cluster(grp, "ctrl_oth", ["ee_sh"], base_covs, fe_col=None, year_fe=True, phase_fe=True),
            "act_oth": fit_fe_cluster(grp, "act_oth", ["ee_sh"], base_covs, fe_col=None, year_fe=True, phase_fe=True),
            "ctrl_sae": fit_fe_cluster(grp, "ctrl_sae", ["ee_sh"], sae_covs, fe_col=None, year_fe=True, phase_fe=True),
        }
    sens["by_therapeutic_area_p23"] = ta_res

    # B8. Leave-One-Country-Out (excluding each major EE country from ee_sh!) & Leave-One-Sponsor-Out
    loco = {}
    for c_tag, col in [("Poland", "pl_sh"), ("Czechia", "cz_sh"), ("Hungary", "hu_sh"), ("Romania", "ro_sh"), ("Bulgaria", "bg_sh"), ("Russia", "ru_sh"), ("Ukraine", "ua_sh")]:
        tmp = df_p23.copy()
        tmp["ee_minus_c"] = (tmp["ee_sh"] - tmp[col]).clip(lower=0.0)
        loco[f"drop_{c_tag}"] = {
            "ctrl_oth": fit_fe_cluster(tmp, "ctrl_oth", ["ee_minus_c", col, "we_sh", "latam_sh", "asia_sh", "other_sh"], base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
            "act_oth": fit_fe_cluster(tmp, "act_oth", ["ee_minus_c", col, "we_sh", "latam_sh", "asia_sh", "other_sh"], base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
        }
    sens["leave_one_country_out_p23_mol_sp"] = loco

    top5_sponsors = df_p23["sponsor_nm"].value_counts().head(5).index.tolist()
    loso = {}
    for sp in top5_sponsors:
        tmp = df_p23[df_p23["sponsor_nm"] != sp].copy()
        loso[sp] = {
            "ctrl_oth": fit_fe_cluster(tmp, "ctrl_oth", reg_xs_pool_ee, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
            "act_oth": fit_fe_cluster(tmp, "act_oth", reg_xs_pool_ee, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
        }
    sens["leave_one_sponsor_out_p23_mol_sp"] = loso

    # =========================================================================
    # BLOCK C: POST-2017 ASYMMETRIC CONVERGENCE & FDAAA 42 CFR PART 11
    # =========================================================================
    print("[Block C] Post-2017 & FDAAA 42 CFR Part 11 Decomposition...", flush=True)
    blk_c = results["block_c_post2017_fdaaa_decomposition"]

    # C1. Annual reporting-regime jump (freq_thr == 0%, freq_thr == 5%, sys_assess) by Primary Completion Year & Start Year
    regime_by_pcomp = []
    for yr in range(2007, 2025):
        g = df_p23[df_p23["prim_comp_year"] == yr]
        if len(g) < 5:
            continue
        regime_by_pcomp.append({
            "year": int(yr),
            "n": len(g),
            "freq0_share": round(float((g["freq_thr"] == 0.0).mean()), 4),
            "freq5_share": round(float((g["freq_thr"] == 5.0).mean()), 4),
            "mean_freq_thr": round(float(g["freq_thr"].mean()), 3),
            "sys_assess_mean": round(float(g["sys_assess_share"].mean()), 4) if g["sys_assess_share"].notna().any() else None,
            "mean_ctrl_oth": round(float(g["ctrl_oth"].mean()), 4),
            "mean_act_oth": round(float(g["act_oth"].mean()), 4),
            "mean_oth_rd": round(float(g["oth_rd"].mean()), 4),
            "mean_eu_east_sh": round(float(g["eu_east_sh"].mean()), 4),
            "mean_ru_ua_sh": round(float(g["ru_ua_sh"].mean()), 4),
        })
    blk_c["regime_by_prim_comp_year"] = regime_by_pcomp

    pre_fdaaa = df_p23[df_p23["post_fdaaa_2017"] == 0]
    post_fdaaa = df_p23[df_p23["post_fdaaa_2017"] == 1]
    blk_c["fdaaa_jan2017_structural_shift"] = {
        "pre_fdaaa_n": len(pre_fdaaa),
        "post_fdaaa_n": len(post_fdaaa),
        "pre_fdaaa_freq0_pct": round(100.0 * float((pre_fdaaa["freq_thr"] == 0.0).mean()), 2),
        "post_fdaaa_freq0_pct": round(100.0 * float((post_fdaaa["freq_thr"] == 0.0).mean()), 2),
        "freq0_jump_ratio": round(float((post_fdaaa["freq_thr"] == 0.0).mean() / max(1e-6, (pre_fdaaa["freq_thr"] == 0.0).mean())), 2),
        "pre_fdaaa_freq5_pct": round(100.0 * float((pre_fdaaa["freq_thr"] == 5.0).mean()), 2),
        "post_fdaaa_freq5_pct": round(100.0 * float((post_fdaaa["freq_thr"] == 5.0).mean()), 2),
        "pre_fdaaa_sys_assess_pct": round(100.0 * float(pre_fdaaa["sys_assess_share"].mean()), 2),
        "post_fdaaa_sys_assess_pct": round(100.0 * float(post_fdaaa["sys_assess_share"].mean()), 2),
    }

    # C2. Prepare interaction columns on P3 and Pooled P2+P3
    for tag, dsub, pfe in [("p3", df_p3.copy(), False), ("p23", df_p23.copy(), True)]:
        dsub["is_freq0"] = (dsub["freq_thr"] == 0.0).astype(float)
        dsub["eu_x_post17"] = dsub["eu_east_sh"] * dsub["post_ich_2017"]
        dsub["ru_x_post17"] = dsub["ru_ua_sh"] * dsub["post_ich_2017"]
        dsub["ee_x_post17"] = dsub["ee_sh"] * dsub["post_ich_2017"]
        dsub["eu_x_fdaaa17"] = dsub["eu_east_sh"] * dsub["post_fdaaa_2017"]
        dsub["ru_x_fdaaa17"] = dsub["ru_ua_sh"] * dsub["post_fdaaa_2017"]
        dsub["eu_x_freq0"] = dsub["eu_east_sh"] * dsub["is_freq0"]
        dsub["ru_x_freq0"] = dsub["ru_ua_sh"] * dsub["is_freq0"]
        dsub["era_17_19"] = dsub["start_year"].between(2017, 2019).astype(float)
        dsub["era_20_24"] = (dsub["start_year"] >= 2020).astype(float)
        dsub["eu_x_17_19"] = dsub["eu_east_sh"] * dsub["era_17_19"]
        dsub["eu_x_20_24"] = dsub["eu_east_sh"] * dsub["era_20_24"]
        dsub["ru_x_17_19"] = dsub["ru_ua_sh"] * dsub["era_17_19"]
        dsub["ru_x_20_24"] = dsub["ru_ua_sh"] * dsub["era_20_24"]

        # Model 1: Baseline Post-2017 Start-Year Interaction (Mol x Sponsor FE)
        blk_c[f"{tag}_post2017_mol_sp"] = {
            y: fit_fe_cluster(
                dsub, y,
                ["eu_east_sh", "eu_x_post17", "ru_ua_sh", "ru_x_post17", "we_sh", "latam_sh", "asia_sh", "other_sh"],
                base_covs if "oth" in y else sae_covs,
                fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            for y in ["ctrl_oth", "act_oth", "oth_rd", "oth_log_rr", "ctrl_sae", "act_sae"]
        }

        # Model 1b: 3-Period Implementation-Lag Interaction (Pre-2017 vs 2017-2019 Transition vs 2020-2024 Mature)
        blk_c[f"{tag}_3era_lag_mol_sp"] = {
            y: fit_fe_cluster(
                dsub, y,
                ["eu_east_sh", "eu_x_17_19", "eu_x_20_24", "ru_ua_sh", "ru_x_17_19", "ru_x_20_24", "we_sh", "latam_sh", "asia_sh", "other_sh"],
                base_covs if "oth" in y else sae_covs,
                fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            for y in ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae", "act_sae"]
        }

        # Model 2: Post-2017 Start-Year Interaction strictly inside freq_thr == 5% (removes FDAAA freq0 channel!)
        dsub_f5 = dsub[dsub["freq_thr"] == 5.0].copy()
        blk_c[f"{tag}_post2017_strict_freq5_mol_sp"] = {
            y: fit_fe_cluster(
                dsub_f5, y,
                ["eu_east_sh", "eu_x_post17", "ru_ua_sh", "ru_x_post17", "we_sh", "latam_sh", "asia_sh", "other_sh"],
                sae_covs,
                fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            for y in ["ctrl_oth", "act_oth", "oth_rd", "oth_log_rr", "ctrl_sae", "act_sae"]
        }
        blk_c[f"{tag}_post2017_strict_freq5_sp_cond"] = {
            y: fit_fe_cluster(
                dsub_f5, y,
                ["eu_east_sh", "eu_x_post17", "ru_ua_sh", "ru_x_post17", "we_sh", "latam_sh", "asia_sh", "other_sh"],
                sae_covs,
                fe_col="sp_cond", year_fe=True, phase_fe=pfe,
            )
            for y in ["ctrl_oth", "act_oth", "oth_rd"]
        }

        # Model 3: Horse-Race Decomposition — ICH E6(R2) Start>=2017 vs FDAAA PrimComp>=Jan18,2017 vs freq_thr==0%
        blk_c[f"{tag}_horserace_ich_vs_fdaaa_mol_sp"] = {
            y: fit_fe_cluster(
                dsub, y,
                [
                    "eu_east_sh", "eu_x_post17", "eu_x_fdaaa17", "eu_x_freq0",
                    "ru_ua_sh", "ru_x_post17", "ru_x_fdaaa17",
                    "post_fdaaa_2017", "is_freq0",
                    "we_sh", "latam_sh", "asia_sh", "other_sh",
                ],
                base_covs,
                fe_col="mol_sponsor", year_fe=True, phase_fe=pfe,
            )
            for y in ["ctrl_oth", "act_oth", "oth_rd"]
        }

        # Model 4: Split pre-2017 vs post-2017 slopes (clean TA FE + Sponsor FE so no over-absorption)
        blk_c[f"{tag}_era_split_ta_fe"] = {}
        for era_lbl, emask in [("pre_2017", dsub["start_year"] <= 2016), ("post_2017", dsub["start_year"] >= 2017)]:
            esub = dsub[emask]
            blk_c[f"{tag}_era_split_ta_fe"][era_lbl] = {
                y: fit_fe_cluster(esub, y, reg_xs_split, base_covs if "oth" in y else sae_covs, fe_col="therapeutic_area", year_fe=True, phase_fe=pfe)
                for y in ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae", "act_sae"]
            }
            esub5 = esub[esub["freq_thr"] == 5.0]
            blk_c[f"{tag}_era_split_ta_fe"][f"{era_lbl}_freq5"] = {
                y: fit_fe_cluster(esub5, y, reg_xs_split, sae_covs, fe_col="therapeutic_area", year_fe=True, phase_fe=pfe)
                for y in ["ctrl_oth", "act_oth", "oth_rd"]
            }

    # C3. Dynamic Event Study across 6 two/three-year bins (Pooled P2+P3, TA FE + Sponsor-clustered SEs)
    era_bins = [
        ("2005-2008", 2005, 2008),
        ("2009-2011", 2009, 2011),
        ("2012-2014", 2012, 2014),
        ("2015-2016", 2015, 2016),
        ("2017-2019", 2017, 2019),
        ("2020-2024", 2020, 2024),
    ]
    es_out = []
    for lbl, y0, y1 in era_bins:
        sub_b = df_p23[df_p23["start_year"].between(y0, y1)].copy()
        entry = {"era": lbl, "n": len(sub_b), "mean_eu_east_sh": round(float(sub_b["eu_east_sh"].mean()), 4), "mean_ru_ua_sh": round(float(sub_b["ru_ua_sh"].mean()), 4)}
        for y in ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae"]:
            fit_r = fit_fe_cluster(sub_b, y, reg_xs_split, base_covs if "oth" in y else sae_covs, fe_col="therapeutic_area", year_fe=True, phase_fe=True)
            entry[y] = {
                "n": fit_r.get("n"),
                "eu_east": fit_r.get("terms", {}).get("eu_east_sh"),
                "ru_ua": fit_r.get("terms", {}).get("ru_ua_sh"),
            }
        es_out.append(entry)
    blk_c["dynamic_event_study_p23_ta_fe"] = es_out

    # C4. Two-way clustering & Rademacher wild cluster bootstrap on 2020-2024 mature EU-East convergence!
    d23_wb = df_p23.copy()
    d23_wb["era_17_19"] = d23_wb["start_year"].between(2017, 2019).astype(float)
    d23_wb["era_20_24"] = (d23_wb["start_year"] >= 2020).astype(float)
    d23_wb["eu_x_17_19"] = d23_wb["eu_east_sh"] * d23_wb["era_17_19"]
    d23_wb["eu_x_20_24"] = d23_wb["eu_east_sh"] * d23_wb["era_20_24"]
    d23_wb["ru_x_17_19"] = d23_wb["ru_ua_sh"] * d23_wb["era_17_19"]
    d23_wb["ru_x_20_24"] = d23_wb["ru_ua_sh"] * d23_wb["era_20_24"]
    lag_xs = ["eu_east_sh", "eu_x_17_19", "eu_x_20_24", "ru_ua_sh", "ru_x_17_19", "ru_x_20_24", "we_sh", "latam_sh", "asia_sh", "other_sh"]
    blk_c["twoway_and_wildboot_2020_2024_convergence"] = {
        "ctrl_oth_eu_x_20_24": fit_twoway_and_wildboot(
            d23_wb, "ctrl_oth", lag_xs, "eu_x_20_24", base_covs, fe_col="mol_sponsor", phase_fe=True
        ),
        "act_oth_eu_x_20_24": fit_twoway_and_wildboot(
            d23_wb, "act_oth", lag_xs, "eu_x_20_24", base_covs, fe_col="mol_sponsor", phase_fe=True
        ),
    }

    # =========================================================================
    # BLOCK D: FEB 24, 2022 RUSSIA-UKRAINE WAR EXOGENOUS SITE-REALLOCATION SHOCK
    # =========================================================================
    print("[Block D] Feb 24, 2022 Russia-Ukraine War Shock (Strictly Out-of-Sample DiD & Placebo Audit)...", flush=True)
    blk_d = results["block_d_war2022_shock"]

    # Universe of ALL multiregional industry P2/P3 RCTs (n_sites >= 5, n_countries >= 3) 2012-2024
    mrct_all_geo_12 = df_all[
        (df_all["start_year"].between(2012, 2024))
        & (df_all["n_sites"] >= 5)
        & (df_all["n_countries"] >= 3)
        & (df_all["enrollment"] >= 50)
    ].copy()
    mrct_all_geo = mrct_all_geo_12[mrct_all_geo_12["start_year"].between(2015, 2024)].copy()

    annual_geo = []
    for yr in range(2015, 2025):
        g = mrct_all_geo[mrct_all_geo["start_year"] == yr]
        gp = df_p23[df_p23["start_year"] == yr]
        annual_geo.append({
            "year": int(yr),
            "n_all_mrct": len(g),
            "n_placebo_mrct": len(gp),
            "median_dur_yr": round(float(g["dur_yr"].median()), 2) if g["dur_yr"].notna().any() else None,
            "phase3_pct": round(100.0 * float(g["is_phase3"].mean()), 1) if len(g) else None,
            "all_ru_ua_strict_pct": round(100.0 * float(g["ru_ua_strict_sh"].mean()), 3) if len(g) else None,
            "all_eu_east_pct": round(100.0 * float(g["eu_east_sh"].mean()), 3) if len(g) else None,
            "all_us_pct": round(100.0 * float(g["us_sh"].mean()), 3) if len(g) else None,
            "all_we_pct": round(100.0 * float(g["we_sh"].mean()), 3) if len(g) else None,
            "all_latam_pct": round(100.0 * float(g["latam_sh"].mean()), 3) if len(g) else None,
            "all_asia_pct": round(100.0 * float(g["asia_sh"].mean()), 3) if len(g) else None,
            "all_other_pct": round(100.0 * float(g["other_sh"].mean()), 3) if len(g) else None,
            "all_any_ru_ua_trial_pct": round(100.0 * float((g["ru_ua_strict_sh"] > 0).mean()), 2) if len(g) else None,
            "n_all_any_ru_ua": int((g["ru_ua_strict_sh"] > 0).sum()),
            "pl_ru_ua_strict_pct": round(100.0 * float(gp["ru_ua_strict_sh"].mean()), 3) if len(gp) else None,
            "pl_eu_east_pct": round(100.0 * float(gp["eu_east_sh"].mean()), 3) if len(gp) else None,
        })
    blk_d["annual_regional_shares_2015_2024"] = annual_geo

    # D2. Clean Within-Sponsor Pre-vs-Post Feb 24, 2022 Reallocation Shift (2017-2024, Sponsor + TA + Phase + dur_yr)
    # Completely free of exposure-window mean-reversion bias!
    war_shift_df = mrct_all_geo[mrct_all_geo["start_year"].between(2017, 2024)].copy()
    postwar_shift = {}
    for dest in ["ru_ua_strict_sh", "us_sh", "eu_east_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"]:
        postwar_shift[dest] = fit_fe_cluster(
            war_shift_df,
            dest,
            ["post_war_2022"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr"],
            fe_col="sponsor_nm",
            year_fe=False,
            phase_fe=True,
            extra_fe_cols=["therapeutic_area"],
        )
    blk_d["within_sponsor_postwar_shift_2017_2024"] = postwar_shift

    # D3. Strictly Out-of-Sample Pre-War Exposure DiD (Primary unbiased continuous DiD):
    # Construct sponsor pre-war RU/UA reliance strictly on 2015-2019 (sponsors with >= 2 trials),
    # then estimate DiD on strictly disjoint 2020-2024 window controlling for Sponsor, Start-Year, TA, Phase & dur_yr!
    pre_oos_15_19 = (
        mrct_all_geo[mrct_all_geo["start_year"].between(2015, 2019)]
        .groupby("sponsor_nm")["ru_ua_strict_sh"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "prewar_oos_exp", "count": "prewar_oos_n"})
    )
    did_oos = mrct_all_geo[mrct_all_geo["start_year"].between(2020, 2024)].merge(
        pre_oos_15_19[pre_oos_15_19["prewar_oos_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
    )
    did_oos["exp_x_postwar"] = did_oos["prewar_oos_exp"] * did_oos["post_war_2022"]

    reallocation_did_oos = {}
    for dest in ["ru_ua_strict_sh", "us_sh", "eu_east_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"]:
        reallocation_did_oos[dest] = fit_fe_cluster(
            did_oos,
            dest,
            ["exp_x_postwar", "post_war_2022"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr"],
            fe_col="sponsor_nm",
            year_fe=True,
            phase_fe=True,
            extra_fe_cols=["therapeutic_area"],
        )
    blk_d["within_sponsor_reallocation_did"] = reallocation_did_oos

    # D3b. Alternate OOS window robustness: 2012-2016 exposure -> 2017-2024 DiD
    pre_oos_12_16 = (
        mrct_all_geo_12[mrct_all_geo_12["start_year"].between(2012, 2016)]
        .groupby("sponsor_nm")["ru_ua_strict_sh"]
        .agg(["mean", "count"])
        .rename(columns={"mean": "prewar_oos_exp", "count": "prewar_oos_n"})
    )
    did_oos_alt = mrct_all_geo_12[mrct_all_geo_12["start_year"].between(2017, 2024)].merge(
        pre_oos_12_16[pre_oos_12_16["prewar_oos_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
    )
    did_oos_alt["exp_x_postwar"] = did_oos_alt["prewar_oos_exp"] * did_oos_alt["post_war_2022"]
    blk_d["oos_did_alt_2012_16_to_2017_24"] = {
        dest: fit_fe_cluster(
            did_oos_alt, dest, ["exp_x_postwar", "post_war_2022"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr"],
            fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
        )
        for dest in ["ru_ua_strict_sh", "us_sh", "eu_east_sh", "we_sh", "latam_sh", "asia_sh"]
    }

    # D4. Pre-War Fake-2020 Placebo Audit (verifying strictly OOS passes while naive in-sample fails!)
    pre_only_17_21 = mrct_all_geo_12[mrct_all_geo_12["start_year"].between(2017, 2021)].copy()
    pre_only_17_21["fake_post_2020"] = (pre_only_17_21["start_year"] >= 2020).astype(float)
    # Strictly OOS placebo (2012-2016 exp -> fake 2020 shock on 2017-2021)
    plc_oos = pre_only_17_21.merge(
        pre_oos_12_16[pre_oos_12_16["prewar_oos_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
    )
    plc_oos["exp_x_fakepost"] = plc_oos["prewar_oos_exp"] * plc_oos["fake_post_2020"]
    # Naive in-sample placebo (2017-2019 exp -> fake 2020 shock on 2017-2021) to document mechanical mean reversion
    naive_17_19 = pre_only_17_21[pre_only_17_21["start_year"].between(2017, 2019)].groupby("sponsor_nm")["ru_ua_strict_sh"].mean().rename("naive_exp")
    plc_naive = pre_only_17_21.merge(naive_17_19, left_on="sponsor_nm", right_index=True, how="inner")
    plc_naive["exp_x_fakepost"] = plc_naive["naive_exp"] * plc_naive["fake_post_2020"]
    blk_d["prewar_placebo_fake2020_audit"] = {
        "oos_placebo_ru_ua": fit_fe_cluster(
            plc_oos, "ru_ua_strict_sh", ["exp_x_fakepost"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr"],
            fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
        ),
        "oos_placebo_us": fit_fe_cluster(
            plc_oos, "us_sh", ["exp_x_fakepost"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr"],
            fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
        ),
        "naive_insample_placebo_ru_ua": fit_fe_cluster(
            plc_naive, "ru_ua_strict_sh", ["exp_x_fakepost"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr"],
            fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
        ),
        "naive_insample_placebo_we": fit_fe_cluster(
            plc_naive, "we_sh", ["exp_x_fakepost"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr"],
            fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
        ),
    }

    # D5. Reduced-form AE effect of war shock using unbiased OOS exposure (honest power disclosure)
    blk_d["war_reduced_form_ae"] = {
        "all_mrct_trial_mean_oth": fit_fe_cluster(
            did_oos, "trial_mean_oth", ["exp_x_postwar", "post_war_2022"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr", "is_double_blind", "freq_thr"],
            fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
        ),
        "all_mrct_trial_mean_sae": fit_fe_cluster(
            did_oos, "trial_mean_sae", ["exp_x_postwar", "post_war_2022"],
            ["log_enroll", "log_sites", "log_countries", "dur_yr", "is_double_blind"],
            fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
        ),
    }
    did_oos_pl = df_p23[df_p23["start_year"].between(2020, 2024)].merge(
        pre_oos_15_19[pre_oos_15_19["prewar_oos_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
    )
    did_oos_pl["exp_x_postwar"] = did_oos_pl["prewar_oos_exp"] * did_oos_pl["post_war_2022"]
    blk_d["war_reduced_form_ae"]["placebo_mrct_ctrl_oth"] = fit_fe_cluster(
        did_oos_pl, "ctrl_oth", ["exp_x_postwar", "post_war_2022"], base_covs,
        fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
    )
    blk_d["war_reduced_form_ae"]["placebo_mrct_act_oth"] = fit_fe_cluster(
        did_oos_pl, "act_oth", ["exp_x_postwar", "post_war_2022"], base_covs,
        fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
    )
    blk_d["war_sample_counts"] = {
        "n_postwar_shift_2017_2024": len(war_shift_df),
        "n_did_all_mrct": len(did_oos),
        "n_postwar_all_mrct": int((did_oos["post_war_2022"] == 1).sum()),
        "n_did_placebo_mrct": len(did_oos_pl),
        "n_postwar_placebo_mrct": int((did_oos_pl["post_war_2022"] == 1).sum()),
        "n_all_postwar_placebo_mrct": int((df_p23["post_war_2022"] == 1).sum()),
    }

    # D6. Uncensored All-Registered ClinicalTrials.gov War Cohort (2017-2025, incl. ongoing/no results!)
    war_all_path = PROC_DIR / "ctgov_all_registered_war_2017_2025.parquet"
    if war_all_path.exists():
        print("  [Block D6] Uncensored All-Registered War Cohort (2017-2025, HasResults=True & False)...", flush=True)
        df_reg = pd.read_parquet(war_all_path)
        reg_mrct = df_reg[
            (df_reg["start_year"].between(2017, 2025))
            & (df_reg["n_sites"] >= 5)
            & (df_reg["n_countries"] >= 3)
            & (df_reg["enrollment"] >= 50)
        ].copy()
        reg_mrct_rand = reg_mrct[reg_mrct["is_randomized"] == 1].copy()

        ann_reg = []
        for yr in range(2017, 2026):
            g = reg_mrct[reg_mrct["start_year"] == yr]
            gr = reg_mrct_rand[reg_mrct_rand["start_year"] == yr]
            ann_reg.append({
                "year": int(yr),
                "n_all_registered": int((df_reg["start_year"] == yr).sum()),
                "n_mrct": len(g),
                "n_mrct_with_ru_ua": int(g["has_ru_ua_site"].sum()),
                "pct_mrct_with_ru_ua": round(100.0 * float(g["has_ru_ua_site"].mean()), 2) if len(g) else None,
                "n_mrct_with_ru": int(g["has_ru_site"].sum()),
                "pct_mrct_with_ru": round(100.0 * float(g["has_ru_site"].mean()), 2) if len(g) else None,
                "n_mrct_with_ua": int(g["has_ua_site"].sum()),
                "pct_mrct_with_ua": round(100.0 * float(g["has_ua_site"].mean()), 2) if len(g) else None,
                "pct_mrct_has_results": round(100.0 * float(g["has_results"].mean()), 2) if len(g) else None,
                "mean_ru_ua_strict_pct": round(100.0 * float(g["ru_ua_strict_sh"].mean()), 3) if len(g) else None,
                "mean_eu_east_pct": round(100.0 * float(g["eu_east_sh"].mean()), 3) if len(g) else None,
                "mean_us_pct": round(100.0 * float(g["us_sh"].mean()), 3) if len(g) else None,
                "mean_we_pct": round(100.0 * float(g["we_sh"].mean()), 3) if len(g) else None,
                "mean_latam_pct": round(100.0 * float(g["latam_sh"].mean()), 3) if len(g) else None,
                "mean_asia_pct": round(100.0 * float(g["asia_sh"].mean()), 3) if len(g) else None,
                "mean_other_pct": round(100.0 * float(g["other_sh"].mean()), 3) if len(g) else None,
                "n_rand_mrct": len(gr),
                "n_rand_with_ru_ua": int(gr["has_ru_ua_site"].sum()),
                "pct_rand_with_ru_ua": round(100.0 * float(gr["has_ru_ua_site"].mean()), 2) if len(gr) else None,
            })

        # Uncensored within-sponsor post-war shift (2017-2025)
        reg_shift = {}
        reg_covs = ["log_enroll", "log_sites", "log_countries"]
        for dest in ["ru_ua_strict_sh", "us_sh", "eu_east_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"]:
            reg_shift[dest] = fit_fe_cluster(
                reg_mrct, dest, ["post_war_2022"], reg_covs,
                fe_col="sponsor_nm", year_fe=False, phase_fe=True, extra_fe_cols=["therapeutic_area"],
            )

        # Uncensored Strictly OOS Sponsor Exposure DiD: 2017-2019 exposure -> strictly disjoint 2020-2025 DiD
        pre_reg_17_19 = (
            reg_mrct[reg_mrct["start_year"].between(2017, 2019)]
            .groupby("sponsor_nm")["ru_ua_strict_sh"]
            .agg(["mean", "count"])
            .rename(columns={"mean": "prewar_reg_exp", "count": "prewar_reg_n"})
        )
        did_reg_20_25 = reg_mrct[reg_mrct["start_year"].between(2020, 2025)].merge(
            pre_reg_17_19[pre_reg_17_19["prewar_reg_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
        )
        did_reg_20_25["exp_x_postwar"] = did_reg_20_25["prewar_reg_exp"] * did_reg_20_25["post_war_2022"]

        did_reg_main = {}
        for dest in ["ru_ua_strict_sh", "us_sh", "eu_east_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"]:
            did_reg_main[dest] = fit_fe_cluster(
                did_reg_20_25, dest, ["exp_x_postwar", "post_war_2022"], reg_covs,
                fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
            )

        # Randomized-only uncensored OOS DiD (2017-2019 -> 2020-2025)
        pre_rand_17_19 = (
            reg_mrct_rand[reg_mrct_rand["start_year"].between(2017, 2019)]
            .groupby("sponsor_nm")["ru_ua_strict_sh"]
            .agg(["mean", "count"])
            .rename(columns={"mean": "prewar_reg_exp", "count": "prewar_reg_n"})
        )
        did_rand_20_25 = reg_mrct_rand[reg_mrct_rand["start_year"].between(2020, 2025)].merge(
            pre_rand_17_19[pre_rand_17_19["prewar_reg_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
        )
        did_rand_20_25["exp_x_postwar"] = did_rand_20_25["prewar_reg_exp"] * did_rand_20_25["post_war_2022"]
        did_reg_rand = {
            dest: fit_fe_cluster(
                did_rand_20_25, dest, ["exp_x_postwar", "post_war_2022"], reg_covs,
                fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
            )
            for dest in ["ru_ua_strict_sh", "us_sh", "eu_east_sh", "we_sh", "latam_sh", "asia_sh"]
        }

        # Alternate uncensored OOS window: 2017-2018 exposure -> 2019-2025 DiD & Fake-2020 OOS Placebo (2019-2021)
        pre_reg_17_18 = (
            reg_mrct[reg_mrct["start_year"].between(2017, 2018)]
            .groupby("sponsor_nm")["ru_ua_strict_sh"]
            .agg(["mean", "count"])
            .rename(columns={"mean": "prewar_reg_exp", "count": "prewar_reg_n"})
        )
        did_reg_19_25 = reg_mrct[reg_mrct["start_year"].between(2019, 2025)].merge(
            pre_reg_17_18[pre_reg_17_18["prewar_reg_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
        )
        did_reg_19_25["exp_x_postwar"] = did_reg_19_25["prewar_reg_exp"] * did_reg_19_25["post_war_2022"]
        did_reg_alt = {
            dest: fit_fe_cluster(
                did_reg_19_25, dest, ["exp_x_postwar", "post_war_2022"], reg_covs,
                fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
            )
            for dest in ["ru_ua_strict_sh", "us_sh", "eu_east_sh", "we_sh", "latam_sh", "asia_sh"]
        }

        plc_reg_19_21 = reg_mrct[reg_mrct["start_year"].between(2019, 2021)].merge(
            pre_reg_17_18[pre_reg_17_18["prewar_reg_n"] >= 2], left_on="sponsor_nm", right_index=True, how="inner"
        )
        plc_reg_19_21["fake_post_2020"] = (plc_reg_19_21["start_year"] >= 2020).astype(float)
        plc_reg_19_21["exp_x_fakepost"] = plc_reg_19_21["prewar_reg_exp"] * plc_reg_19_21["fake_post_2020"]
        plc_reg = {
            "oos_placebo_ru_ua": fit_fe_cluster(
                plc_reg_19_21, "ru_ua_strict_sh", ["exp_x_fakepost"], reg_covs,
                fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
            ),
            "oos_placebo_us": fit_fe_cluster(
                plc_reg_19_21, "us_sh", ["exp_x_fakepost"], reg_covs,
                fe_col="sponsor_nm", year_fe=True, phase_fe=True, extra_fe_cols=["therapeutic_area"],
            ),
        }

        blk_d["all_registered_war_2017_2025"] = {
            "sample_counts": {
                "total_registered_p2_p3_2017_2025": len(df_reg),
                "mrct_ge5sites_ge3countries_ge50enroll": len(reg_mrct),
                "randomized_mrct": len(reg_mrct_rand),
                "pct_mrct_has_results_overall": round(100.0 * float(reg_mrct["has_results"].mean()), 2),
                "n_mrct_post_war_2022_2025": int((reg_mrct["post_war_2022"] == 1).sum()),
                "n_did_2020_2025": len(did_reg_20_25),
                "n_did_2020_2025_postwar": int((did_reg_20_25["post_war_2022"] == 1).sum()),
            },
            "annual_participation_2017_2025": ann_reg,
            "within_sponsor_postwar_shift_2017_2025": reg_shift,
            "oos_did_2017_19_to_2020_25": did_reg_main,
            "oos_did_2017_19_to_2020_25_randomized": did_reg_rand,
            "oos_did_2017_18_to_2019_25": did_reg_alt,
            "oos_placebo_fake2020_2017_18_to_2019_21": plc_reg,
        }

    # =========================================================================
    # BLOCK E: SITE-SHARE VS PATIENT-ACCRUAL BOUNDS & EIV DEATTENUATION
    # =========================================================================
    print("[Block E] Site-Share vs Patient-Accrual Attenuation Bounds...", flush=True)
    blk_e = results["block_e_site_vs_patient_bounds"]

    # E1. Directly estimate per-site accrual velocity log(enrollment/n_sites) inside Twin-Trial FE!
    pps_covs = ["log_countries", "dur_yr", "is_double_blind"]
    blk_e["empirical_accrual_velocity_p3_mol_sp"] = fit_fe_cluster(
        df_p3, "log_pps", reg_xs_split, pps_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=False
    )
    blk_e["empirical_accrual_velocity_p23_mol_sp"] = fit_fe_cluster(
        df_p23, "log_pps", reg_xs_split, pps_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True
    )
    blk_e["empirical_accrual_velocity_p23_ee"] = fit_fe_cluster(
        df_p23, "log_pps", reg_xs_pool_ee, pps_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True
    )

    # Extract empirically implied accrual ratio w_hat = exp(gamma_ee)
    gam_ee = blk_e["empirical_accrual_velocity_p23_ee"].get("terms", {}).get("ee_sh", {}).get("coef", 0.0)
    w_hat_ee = float(np.exp(gam_ee))
    gam_eu = blk_e["empirical_accrual_velocity_p23_mol_sp"].get("terms", {}).get("eu_east_sh", {}).get("coef", 0.0)
    gam_ru = blk_e["empirical_accrual_velocity_p23_mol_sp"].get("terms", {}).get("ru_ua_sh", {}).get("coef", 0.0)
    blk_e["implied_accrual_ratios_vs_us"] = {
        "w_hat_ee_all": round(w_hat_ee, 3),
        "w_hat_eu_east": round(float(np.exp(gam_eu)), 3),
        "w_hat_ru_ua": round(float(np.exp(gam_ru)), 3),
    }

    # E2. Nonlinear Simplex-Preserving Patient-Share Calibration across accrual ratios w in [0.5, ..., 3.0]
    # Rescales ALL regional shares by D = w * ee_sh + (1 - ee_sh) so sum_r p_r(w) == 1.0 identically!
    w_grid = sorted({0.5, 0.75, 1.0, round(w_hat_ee, 3), 1.5, 2.0, 2.5, 3.0})
    cal_curve = []
    for w in w_grid:
        tmp = df_p23.copy()
        denom_w = (w * tmp["ee_sh"] + (1.0 - tmp["ee_sh"])).clip(lower=1e-9)
        tmp["p_ee_cal"] = (w * tmp["ee_sh"]) / denom_w
        tmp["p_we_cal"] = tmp["we_sh"] / denom_w
        tmp["p_latam_cal"] = tmp["latam_sh"] / denom_w
        tmp["p_asia_cal"] = tmp["asia_sh"] / denom_w
        tmp["p_other_cal"] = tmp["other_sh"] / denom_w
        tmp["p_us_cal"] = tmp["us_sh"] / denom_w
        assert np.allclose(
            tmp["p_ee_cal"] + tmp["p_we_cal"] + tmp["p_latam_cal"] + tmp["p_asia_cal"] + tmp["p_other_cal"] + tmp["p_us_cal"],
            1.0,
            atol=1e-9,
        )
        cal_xs = ["p_ee_cal", "p_we_cal", "p_latam_cal", "p_asia_cal", "p_other_cal"]
        m_c = fit_fe_cluster(tmp, "ctrl_oth", cal_xs, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        m_a = fit_fe_cluster(tmp, "act_oth", cal_xs, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True)
        tc = m_c.get("terms", {}).get("p_ee_cal", {})
        ta = m_a.get("terms", {}).get("p_ee_cal", {})
        cal_curve.append({
            "w_ee_accrual_ratio": w,
            "is_empirical_what": bool(abs(w - round(w_hat_ee, 3)) < 1e-4),
            "ctrl_oth_coef": tc.get("coef"),
            "ctrl_oth_se": tc.get("se"),
            "ctrl_oth_p": tc.get("p"),
            "act_oth_coef": ta.get("coef"),
            "act_oth_se": ta.get("se"),
            "act_oth_p": ta.get("p"),
        })
    blk_e["nonlinear_patient_share_calibration_p23"] = cal_curve

    # E3. Classical Errors-in-Variables (EIV) Attenuation Bounds (exact DoF-adjusted SSR / df_resid within FE!)
    req_eiv = ["ee_sh", "ctrl_oth", "act_oth", "mol_sponsor", "start_year", "phase_group", "we_sh", "latam_sh", "asia_sh", "other_sh"] + base_covs
    sub_eiv = df_p23.dropna(subset=req_eiv).copy()
    sub_eiv = sub_eiv[sub_eiv["mol_sponsor"] != ""].copy()
    sub_eiv = _prune_twoway_connected(sub_eiv, "mol_sponsor", "start_year")
    rhs_eiv = " + ".join(base_covs + ["we_sh", "latam_sh", "asia_sh", "other_sh", "C(start_year)", "C(phase_group)", "C(mol_sponsor)"])
    fit_ee_eiv = smf.ols(f"ee_sh ~ {rhs_eiv}", data=sub_eiv).fit()
    # Exact within-FE residual variance accounting for K absorbed FE/control degrees of freedom: E[s'Ms] = E[p'Mp] + (N-K)*sigma_eta^2
    var_s_tilde = float(fit_ee_eiv.ssr / fit_ee_eiv.df_resid)
    sd_s_tilde = float(np.sqrt(var_s_tilde))

    b_ctrl_obs = results["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]["ctrl_oth"]["terms"]["ee_sh"]["coef"]
    b_act_obs = results["block_a_core_twin_trial"]["p23_mol_sponsor_ee"]["act_oth"]["terms"]["ee_sh"]["coef"]
    eiv_bounds = []
    for sigma_eta in [0.00, 0.02, 0.04, 0.06, 0.08]:
        rel_lambda = max(0.20, 1.0 - (sigma_eta ** 2) / var_s_tilde)
        eiv_bounds.append({
            "sigma_eta_site_patient_noise": sigma_eta,
            "within_fe_sd_ee_sh": round(sd_s_tilde, 4),
            "df_resid": int(fit_ee_eiv.df_resid),
            "reliability_lambda": round(rel_lambda, 4),
            "deattenuated_ctrl_oth": round(b_ctrl_obs / rel_lambda, 4),
            "deattenuated_act_oth": round(b_act_obs / rel_lambda, 4),
        })
    blk_e["classical_eiv_bounds_p23"] = eiv_bounds

    # E4. Heterogeneity by trial patients-per-site (median split) — verifies effect isn't driven by small/sparse sites!
    med_pps = float(df_p23["patients_per_site"].median())
    blk_e["pps_median_split_p23"] = {
        "median_patients_per_site": round(med_pps, 2),
        "low_pps_ctrl_oth": fit_fe_cluster(df_p23[df_p23["patients_per_site"] <= med_pps], "ctrl_oth", reg_xs_pool_ee, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
        "high_pps_ctrl_oth": fit_fe_cluster(df_p23[df_p23["patients_per_site"] > med_pps], "ctrl_oth", reg_xs_pool_ee, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
        "low_pps_act_oth": fit_fe_cluster(df_p23[df_p23["patients_per_site"] <= med_pps], "act_oth", reg_xs_pool_ee, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
        "high_pps_act_oth": fit_fe_cluster(df_p23[df_p23["patients_per_site"] > med_pps], "act_oth", reg_xs_pool_ee, base_covs, fe_col="mol_sponsor", year_fe=True, phase_fe=True),
    }

    # =========================================================================
    # RESIDUALIZED BINSCATTER DATA FOR FIGURE 2 (Exact FWL matching full model!)
    # =========================================================================
    print("[Binscatter] Computing exact FWL residualized Twin-Trial binned scatters...", flush=True)
    results["binscatter_data"]["p3_mol_sp_ee"] = compute_fwl_binscatter(
        df_p3, "ee_sh", ["ctrl_oth", "act_oth", "ctrl_sae"],
        ["we_sh", "latam_sh", "asia_sh", "other_sh"], base_covs, sae_covs,
        fe_col="mol_sponsor", phase_fe=False, n_bins=10,
    )
    results["binscatter_data"]["p23_mol_sp_ee"] = compute_fwl_binscatter(
        df_p23, "ee_sh", ["ctrl_oth", "act_oth", "ctrl_sae"],
        ["we_sh", "latam_sh", "asia_sh", "other_sh"], base_covs, sae_covs,
        fe_col="mol_sponsor", phase_fe=True, n_bins=10,
    )
    results["binscatter_data"]["p23_mol_sp_eu_east"] = compute_fwl_binscatter(
        df_p23, "eu_east_sh", ["ctrl_oth", "act_oth", "ctrl_sae"],
        ["ru_ua_sh", "we_sh", "latam_sh", "asia_sh", "other_sh"], base_covs, sae_covs,
        fe_col="mol_sponsor", phase_fe=True, n_bins=10,
    )

    # Save master JSON receipt
    out_json = RES_DIR / "d30_econometrics_results.json"
    out_json.write_text(json.dumps(results, indent=2), encoding="utf-8")
    sha = hashlib.sha256(out_json.read_bytes()).hexdigest()

    # Export clean structured CSV tables
    # Table 1: Core Twin-Trial Specifications
    t1_rows = []
    spec_list = [
        ("P3 Mol x Sponsor FE (EU-East)", "p3_mol_sponsor_split", "eu_east_sh"),
        ("P3 Mol x Sponsor FE (Non-EU EE/RU-UA)", "p3_mol_sponsor_split", "ru_ua_sh"),
        ("P3 Mol x Sponsor FE (All EE)", "p3_mol_sponsor_ee", "ee_sh"),
        ("P3 Mol x Sponsor FE (Western Europe/Dev)", "p3_mol_sponsor_split", "we_sh"),
        ("P3 Mol x Sponsor FE (LatAm)", "p3_mol_sponsor_split", "latam_sh"),
        ("P3 Mol x Sponsor FE (Asia Emerging)", "p3_mol_sponsor_split", "asia_sh"),
        ("P3 Mol x Condition FE (EU-East)", "p3_mol_cond_split", "eu_east_sh"),
        ("P3 Mol x Condition FE (All EE)", "p3_mol_cond_ee", "ee_sh"),
        ("P3 Mol x Sp x Cond Triplet FE (EU-East)", "p3_mol_sp_cond_split", "eu_east_sh"),
        ("P3 Mol x Sp x Cond Triplet FE (All EE)", "p3_mol_sp_cond_ee", "ee_sh"),
        ("P2 Standalone OOS Mol x Sp FE (All EE)", "p2_standalone_mol_sponsor_ee", "ee_sh"),
        ("P2 Standalone OOS TA FE (EU-East)", "p2_standalone_ta_fe_split", "eu_east_sh"),
        ("Pooled P2+P3 Mol x Sp FE (EU-East)", "p23_mol_sponsor_split", "eu_east_sh"),
        ("Pooled P2+P3 Mol x Sp FE (All EE)", "p23_mol_sponsor_ee", "ee_sh"),
        ("Pooled P2+P3 Mol x Cond FE (All EE)", "p23_mol_cond_ee", "ee_sh"),
        ("Pooled P2+P3 Mol x Sp x Cond FE (EU-East)", "p23_mol_sp_cond_split", "eu_east_sh"),
    ]
    for label, spec_key, term_key in spec_list:
        blk = results["block_a_core_twin_trial"][spec_key]
        for y in ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae", "act_sae", "ctrl_mort", "n_other_terms"]:
            r = blk.get(y, {})
            t = r.get("terms", {}).get(term_key, {})
            t1_rows.append({
                "specification": label,
                "outcome": y,
                "n": r.get("n"),
                "n_fe_groups": r.get("n_fe_groups"),
                "n_clusters": r.get("n_clusters"),
                "coef": t.get("coef"),
                "se": t.get("se"),
                "t": t.get("t"),
                "p": t.get("p"),
                "ci95_lo": t.get("ci95_lo"),
                "ci95_hi": t.get("ci95_hi"),
                "tost_90_margin": t.get("tost_90_margin"),
                "per_10pp_coef": t.get("per_10pp_coef"),
            })
    pd.DataFrame(t1_rows).to_csv(TAB_DIR / "table1_core_twin_trial.csv", index=False)

    # Table 2: Sensitivity Subsamples (strictly full-rank, zero NaN rows!)
    t2_rows = []
    sens_specs = [
        ("P3 Strict freq_thr==5% (Mol x Sp, EU-East)", "p3_freq5_mol_sp", "eu_east_sh"),
        ("P3 Strict freq_thr==5% (Mol x Sp, All EE)", "p3_freq5_mol_sp_ee", "ee_sh"),
        ("P2+P3 Strict freq_thr==5% (Mol x Sp, All EE)", "p23_freq5_mol_sp_ee", "ee_sh"),
        ("P2+P3 Strict freq_thr==0% (TA FE, All EE)", "p23_freq0_ta_fe_ee", "ee_sh"),
        ("P2+P3 Strict freq_thr==0% (Sponsor FE, All EE)", "p23_freq0_sponsor_fe_ee", "ee_sh"),
        ("P3 + SYSTEMATIC_ASSESSMENT control (EU-East)", "systematic_control_p3_mol_sp", "eu_east_sh"),
        ("P2+P3 + SYSTEMATIC_ASSESSMENT control (EU-East)", "systematic_control_p23_mol_sp", "eu_east_sh"),
        ("P2+P3 All-Systematic Only (EU-East)", "systematic_only_sub_p23_mol_sp", "eu_east_sh"),
        ("P2+P3 All-Status incl. Terminated (EU-East)", "allstatus_incl_terminated_p23_mol_sp", "eu_east_sh"),
        ("P3 Enrollment-Weighted WLS (EU-East)", "enrollment_weighted_wls_p3_mol_sp", "eu_east_sh"),
    ]
    for label, s_key, term_key in sens_specs:
        blk = sens.get(s_key, {})
        for y in ["ctrl_oth", "act_oth", "oth_rd", "ctrl_sae"]:
            if y not in blk:
                continue
            r = blk[y]
            t = r.get("terms", {}).get(term_key, {})
            if not t:
                continue
            t2_rows.append({
                "specification": label,
                "outcome": y,
                "n": r.get("n"),
                "coef": t.get("coef"),
                "se": t.get("se"),
                "t": t.get("t"),
                "p": t.get("p"),
            })
    pd.DataFrame(t2_rows).to_csv(TAB_DIR / "table2_sensitivity_subsamples.csv", index=False)

    # Table 3: Post-2017 & FDAAA Horse-Race Decomposition
    t3_rows = []
    for model_key in [
        "p3_post2017_mol_sp", "p23_post2017_mol_sp",
        "p3_3era_lag_mol_sp", "p23_3era_lag_mol_sp",
        "p3_post2017_strict_freq5_mol_sp", "p23_post2017_strict_freq5_mol_sp",
        "p23_horserace_ich_vs_fdaaa_mol_sp",
    ]:
        blk = blk_c[model_key]
        for y, r in blk.items():
            for term, vals in r.get("terms", {}).items():
                if any(k in term for k in ("eu_", "ru_", "post_fdaaa", "is_freq0")):
                    t3_rows.append({
                        "model": model_key,
                        "outcome": y,
                        "term": term,
                        "n": r.get("n"),
                        "coef": vals.get("coef"),
                        "se": vals.get("se"),
                        "t": vals.get("t"),
                        "p": vals.get("p"),
                    })
    pd.DataFrame(t3_rows).to_csv(TAB_DIR / "table3_post2017_fdaaa_decomposition.csv", index=False)

    # Table 4: War Reallocation & Accrual Bounds
    pd.DataFrame(blk_e["nonlinear_patient_share_calibration_p23"]).to_csv(
        TAB_DIR / "table4_accrual_calibration_bounds.csv", index=False
    )

    # Table 2b: MedDRA Compositional Share vs Absolute SOC Event/Term Rates (zero NaNs)
    t2b_rows = []
    for spec_lbl, blk_m in [
        ("P2+P3 Mol x Sponsor FE (Composition)", sens.get("meddra_soc_composition_p23_mol_sp", {})),
        ("P2+P3 Mol x Sponsor FE (Absolute)", sens.get("meddra_soc_absolute_p23_mol_sp", {})),
        ("P3 Mol x Sponsor FE (Absolute)", sens.get("meddra_soc_absolute_p3_mol_sp", {})),
        ("P2+P3 Strict freq==5% (Absolute)", sens.get("meddra_soc_absolute_p23_freq5_mol_sp", {})),
    ]:
        for y, r in blk_m.items():
            t = r.get("terms", {}).get("eu_east_sh", {})
            if not t:
                continue
            t2b_rows.append({
                "specification": spec_lbl,
                "outcome": y,
                "n": r.get("n"),
                "y_mean": r.get("y_mean"),
                "coef_eu_east": t.get("coef"),
                "se": t.get("se"),
                "p": t.get("p"),
                "ci95_lo": t.get("ci95_lo"),
                "ci95_hi": t.get("ci95_hi"),
                "per_10pp_coef": t.get("per_10pp_coef"),
            })
    if t2b_rows:
        pd.DataFrame(t2b_rows).to_csv(TAB_DIR / "table2b_meddra_absolute_soc_rates.csv", index=False)

    # Table 4b: Uncensored All-Registered CT.gov War Cohort (2017-2025) Annual & OOS DiD (zero NaNs)
    if "all_registered_war_2017_2025" in blk_d:
        reg_blk = blk_d["all_registered_war_2017_2025"]
        t4b_rows = []
        for dest, r in reg_blk["oos_did_2017_19_to_2020_25"].items():
            t = r.get("terms", {}).get("exp_x_postwar", {})
            if not t:
                continue
            t4b_rows.append({
                "cohort": "All-Registered MRCT (2017-19 -> 2020-25)",
                "destination_region": dest,
                "n": r.get("n"),
                "coef": t.get("coef"),
                "se": t.get("se"),
                "t": t.get("t"),
                "p": t.get("p"),
                "ci95_lo": t.get("ci95_lo"),
                "ci95_hi": t.get("ci95_hi"),
            })
        for dest, r in reg_blk["oos_did_2017_19_to_2020_25_randomized"].items():
            t = r.get("terms", {}).get("exp_x_postwar", {})
            if not t:
                continue
            t4b_rows.append({
                "cohort": "All-Registered Randomized MRCT (2017-19 -> 2020-25)",
                "destination_region": dest,
                "n": r.get("n"),
                "coef": t.get("coef"),
                "se": t.get("se"),
                "t": t.get("t"),
                "p": t.get("p"),
                "ci95_lo": t.get("ci95_lo"),
                "ci95_hi": t.get("ci95_hi"),
            })
        for dest, r in reg_blk["within_sponsor_postwar_shift_2017_2025"].items():
            t = r.get("terms", {}).get("post_war_2022", {})
            if not t:
                continue
            t4b_rows.append({
                "cohort": "All-Registered Within-Sponsor Shift (2017-25)",
                "destination_region": dest,
                "n": r.get("n"),
                "coef": t.get("coef"),
                "se": t.get("se"),
                "t": t.get("t"),
                "p": t.get("p"),
                "ci95_lo": t.get("ci95_lo"),
                "ci95_hi": t.get("ci95_hi"),
            })
        pd.DataFrame(t4b_rows).to_csv(TAB_DIR / "table4b_all_registered_war_2017_2025.csv", index=False)

    print(f"\n[DONE] Econometrics suite complete! JSON SHA-256: {sha}", flush=True)
    # Print crisp executive console summary of every key result
    print("\n=== HEADLINE SUMMARY ===", flush=True)
    for name, sec, term in [
        ("P3 Mol x Sponsor (EU-East)", results["block_a_core_twin_trial"]["p3_mol_sponsor_split"], "eu_east_sh"),
        ("P3 Mol x Sponsor (RU/UA)", results["block_a_core_twin_trial"]["p3_mol_sponsor_split"], "ru_ua_sh"),
        ("P3 Mol x Sponsor (All EE)", results["block_a_core_twin_trial"]["p3_mol_sponsor_ee"], "ee_sh"),
        ("P3 Mol x Cond (All EE)", results["block_a_core_twin_trial"]["p3_mol_cond_ee"], "ee_sh"),
        ("P3 Triplet MolxSpxCond (All EE)", results["block_a_core_twin_trial"]["p3_mol_sp_cond_ee"], "ee_sh"),
        ("P2 OOS Mol x Sponsor (All EE)", results["block_a_core_twin_trial"]["p2_standalone_mol_sponsor_ee"], "ee_sh"),
        ("P2+P3 Mol x Sponsor (EU-East)", results["block_a_core_twin_trial"]["p23_mol_sponsor_split"], "eu_east_sh"),
        ("P2+P3 Mol x Sponsor (All EE)", results["block_a_core_twin_trial"]["p23_mol_sponsor_ee"], "ee_sh"),
        ("P2+P3 Mol x Cond (All EE)", results["block_a_core_twin_trial"]["p23_mol_cond_ee"], "ee_sh"),
    ]:
        c = sec["ctrl_oth"].get("terms", {}).get(term, {})
        a = sec["act_oth"].get("terms", {}).get(term, {})
        rd = sec["oth_rd"].get("terms", {}).get(term, {})
        s = sec["ctrl_sae"].get("terms", {}).get(term, {})
        m = sec["ctrl_mort"].get("terms", {}).get(term, {})
        print(
            f"  {name:34s} (N={sec['ctrl_oth'].get('n',0):4d}): "
            f"ctrl_oth={c.get('coef', np.nan):+.4f}(p={c.get('p', np.nan):.3g}) | "
            f"act_oth={a.get('coef', np.nan):+.4f}(p={a.get('p', np.nan):.3g}) | "
            f"oth_rd={rd.get('coef', np.nan):+.4f}(p={rd.get('p', np.nan):.3g}) | "
            f"ctrl_sae={s.get('coef', np.nan):+.4f}(p={s.get('p', np.nan):.3g}) | "
            f"ctrl_mort={m.get('coef', np.nan):+.4f}(p={m.get('p', np.nan):.3g})",
            flush=True,
        )

    print("\n=== POST-2017 & FDAAA DECOMPOSITION (P2+P3 Mol x Sp) ===", flush=True)
    for y in ["ctrl_oth", "act_oth", "oth_rd"]:
        t_all = blk_c["p23_post2017_mol_sp"][y]["terms"]
        t_f5 = blk_c["p23_post2017_strict_freq5_mol_sp"][y]["terms"]
        t_hr = blk_c["p23_horserace_ich_vs_fdaaa_mol_sp"][y]["terms"]
        print(
            f"  {y:10s} | ALL: eu={t_all['eu_east_sh']['coef']:+.3f}(p={t_all['eu_east_sh']['p']:.3g}), "
            f"eu*post17={t_all['eu_x_post17']['coef']:+.3f}(p={t_all['eu_x_post17']['p']:.3g}) | "
            f"FREQ5: eu={t_f5['eu_east_sh']['coef']:+.3f}, eu*post17={t_f5['eu_x_post17']['coef']:+.3f}(p={t_f5['eu_x_post17']['p']:.3g}) | "
            f"HORSERACE: eu*post17={t_hr['eu_x_post17']['coef']:+.3f}(p={t_hr['eu_x_post17']['p']:.3g}), "
            f"eu*fdaaa17={t_hr['eu_x_fdaaa17']['coef']:+.3f}(p={t_hr['eu_x_fdaaa17']['p']:.3g}), "
            f"eu*freq0={t_hr['eu_x_freq0']['coef']:+.3f}(p={t_hr['eu_x_freq0']['p']:.3g})",
            flush=True,
        )
        t_3e = blk_c["p23_3era_lag_mol_sp"][y]["terms"]
        print(
            f"             | 3-ERA LAG: eu_pre17={t_3e['eu_east_sh']['coef']:+.3f}(p={t_3e['eu_east_sh']['p']:.3g}), "
            f"eu*17_19={t_3e['eu_x_17_19']['coef']:+.3f}(p={t_3e['eu_x_17_19']['p']:.3g}), "
            f"eu*20_24={t_3e['eu_x_20_24']['coef']:+.3f}(p={t_3e['eu_x_20_24']['p']:.3g}) | "
            f"ru*20_24={t_3e['ru_x_20_24']['coef']:+.3f}(p={t_3e['ru_x_20_24']['p']:.3g})",
            flush=True,
        )

    print("\n=== WAR 2022 REALLOCATION & ACCRUAL VELOCITY ===", flush=True)
    for dest, r in blk_d["within_sponsor_reallocation_did"].items():
        t = r.get("terms", {}).get("exp_x_postwar", {})
        print(f"  War DiD -> {dest:16s}: coef={t.get('coef', np.nan):+.4f} (t={t.get('t', np.nan):+.2f}, p={t.get('p', np.nan):.3g})", flush=True)
    print("  Implied per-site accrual ratios vs US:", blk_e["implied_accrual_ratios_vs_us"], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
