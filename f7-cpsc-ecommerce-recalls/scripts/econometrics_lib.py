"""Core full-rank econometric inference library for F7 Boost.

Implements:
  - Strict full-rank design matrix construction (asserting matrix_rank == K)
  - Exact CR1 cluster-robust OLS with t(G - 1) inference
  - Exact linear-contrast Wald tests (e.g. Mkt_FD_China - Mkt_True_US)
  - Exact Restricted Rademacher Wild Cluster Bootstrap-t (Cameron-Gelbach-Miller 2008)
  - Exact Stratified Permutation test
  - Firm-clustered Binomial Logit with Odds Ratios
  - Newey-West HAC OLS for quarterly interrupted time-series analysis
"""
from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats


def build_full_rank_design(
    df: pd.DataFrame,
    numeric_cols: list[str],
    cat_cols: list[str],
) -> tuple[np.ndarray, list[str]]:
    """Construct an explicit intercept + numeric + reference-coded categorical
    design matrix, pruning any zero-variance or strictly collinear columns
    (e.g. in narrow subsamples) and asserting exact full column rank.
    """
    n = len(df)
    parts: list[np.ndarray] = [np.ones((n, 1), dtype=float)]
    names: list[str] = ["const"]

    for col in numeric_cols:
        arr = df[col].astype(float).to_numpy()
        if np.nanstd(arr) > 1e-12:
            parts.append(arr.reshape(-1, 1))
            names.append(col)

    for col in cat_cols:
        cats = sorted(df[col].astype(str).unique())
        if len(cats) <= 1:
            continue
        # Drop first category as reference
        for cval in cats[1:]:
            ind = (df[col].astype(str).to_numpy() == cval).astype(float)
            if ind.sum() > 0 and ind.sum() < n:
                parts.append(ind.reshape(-1, 1))
                names.append(f"{col}::{cval}")

    X_raw = np.hstack(parts)
    # QR / SVD rank pruning if any exact linear dependency exists across FE sets
    keep_idx: list[int] = []
    cur_rank = 0
    for j in range(X_raw.shape[1]):
        cand = X_raw[:, keep_idx + [j]]
        r = int(np.linalg.matrix_rank(cand))
        if r > cur_rank:
            keep_idx.append(j)
            cur_rank = r

    X = X_raw[:, keep_idx]
    kept_names = [names[j] for j in keep_idx]
    final_rank = int(np.linalg.matrix_rank(X))
    if final_rank != X.shape[1]:
        raise RuntimeError(f"Design matrix rank deficiency: rank={final_rank} != K={X.shape[1]}")
    return X, kept_names


def fit_cr1_ols(
    y: np.ndarray,
    X: np.ndarray,
    col_names: list[str],
    clusters: np.ndarray,
) -> dict[str, Any]:
    """Exact OLS with CR1 cluster-robust covariance and t(G - 1) inference."""
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    rank = int(np.linalg.matrix_rank(X))
    if rank != k:
        raise ValueError(f"Non-full-rank design matrix passed to fit_cr1_ols: rank={rank}, K={k}")

    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta

    # Cluster meat matrix
    _, inv_idx = np.unique(clusters, return_inverse=True)
    G = int(inv_idx.max() + 1)
    if G < 2:
        raise ValueError(f"Need at least 2 clusters for CR1; got G={G}")

    # Vectorized cluster score aggregation: S[g] = sum_{i in g} X_i * e_i
    Xe = X * resid[:, None]
    scores = np.zeros((G, k), dtype=float)
    np.add.at(scores, inv_idx, Xe)
    meat = scores.T @ scores

    # Exact CR1 finite-sample adjustment matching statsmodels cov_type="cluster"
    dof_mult = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    vcov = dof_mult * (XtX_inv @ meat @ XtX_inv)
    se = np.sqrt(np.maximum(np.diag(vcov), 1e-30))
    t_vals = beta / se
    df_t = G - 1
    p_vals = 2.0 * stats.t.sf(np.abs(t_vals), df=df_t)
    t_crit = float(stats.t.ppf(0.975, df=df_t))

    tss = float(np.sum((y - np.mean(y)) ** 2))
    rss = float(np.sum(resid ** 2))
    r2 = 1.0 - rss / tss if tss > 0 else 0.0

    params_dict = {}
    for idx, nm in enumerate(col_names):
        b = float(beta[idx])
        s = float(se[idx])
        params_dict[nm] = {
            "beta": b,
            "se": s,
            "t": float(t_vals[idx]),
            "p": float(p_vals[idx]),
            "ci_lo": b - t_crit * s,
            "ci_hi": b + t_crit * s,
        }

    return {
        "n": int(n),
        "k": int(k),
        "rank": int(rank),
        "n_clusters": int(G),
        "df_t": int(df_t),
        "r2": float(r2),
        "beta": beta,
        "vcov": vcov,
        "resid": resid,
        "XtX_inv": XtX_inv,
        "col_names": col_names,
        "params": params_dict,
    }


def wald_linear_contrast(
    fit: dict[str, Any],
    contrast_weights: dict[str, float],
) -> dict[str, float]:
    """Exact CR1 linear contrast R'beta with t(G - 1) inference."""
    k = fit["k"]
    r_vec = np.zeros(k, dtype=float)
    name_to_idx = {nm: i for i, nm in enumerate(fit["col_names"])}
    for nm, w in contrast_weights.items():
        if nm not in name_to_idx:
            return {"diff": float("nan"), "se": float("nan"), "t": float("nan"), "p": float("nan"), "ci_lo": float("nan"), "ci_hi": float("nan")}
        r_vec[name_to_idx[nm]] = w

    diff = float(r_vec @ fit["beta"])
    var = float(r_vec @ fit["vcov"] @ r_vec)
    se = float(np.sqrt(max(var, 1e-30)))
    t_val = diff / se
    df_t = fit["df_t"]
    p_val = float(2.0 * stats.t.sf(abs(t_val), df=df_t))
    t_crit = float(stats.t.ppf(0.975, df=df_t))
    return {
        "diff": diff,
        "se": se,
        "t": t_val,
        "p": p_val,
        "ci_lo": diff - t_crit * se,
        "ci_hi": diff + t_crit * se,
    }


def wild_cluster_bootstrap_t(
    y: np.ndarray,
    X: np.ndarray,
    col_names: list[str],
    clusters: np.ndarray,
    contrast_weights: dict[str, float],
    B: int = 999,
    seed: int = 20261126,
) -> dict[str, float]:
    """Restricted Rademacher Wild Cluster Bootstrap-t (WCB-r) for H0: r'beta = 0
    following Cameron, Gelbach & Miller (2008, REStat).
    """
    y = np.asarray(y, dtype=float)
    X = np.asarray(X, dtype=float)
    n, k = X.shape
    name_to_idx = {nm: i for i, nm in enumerate(col_names)}

    r_vec = np.zeros(k, dtype=float)
    for nm, w in contrast_weights.items():
        if nm not in name_to_idx:
            return {"t_obs": float("nan"), "p_wcb": float("nan"), "B": int(B)}
        r_vec[name_to_idx[nm]] = w

    # Unrestricted fit & observed CR1 t-statistic
    XtX_inv = np.linalg.inv(X.T @ X)
    beta_u = XtX_inv @ (X.T @ y)
    e_u = y - X @ beta_u

    _, inv_idx = np.unique(clusters, return_inverse=True)
    G = int(inv_idx.max() + 1)
    dof_mult = (G / (G - 1.0)) * ((n - 1.0) / (n - k))

    # Precompute projection vector h = XtX_inv @ r_vec (size k) and M_r = X @ h (size n)
    h_vec = XtX_inv @ r_vec
    r_XtXinv_r = float(r_vec @ h_vec)

    # Unrestricted CR1 t-stat via fast scalar cluster scores:
    # r' V_CR1 r = dof_mult * sum_g (sum_{i in g} (X_i @ h_vec) * e_i)^2
    Xh = X @ h_vec  # shape (n,)
    s_obs = np.zeros(G, dtype=float)
    np.add.at(s_obs, inv_idx, Xh * e_u)
    se_obs = float(np.sqrt(max(dof_mult * float(np.sum(s_obs ** 2)), 1e-30)))
    t_obs = float((r_vec @ beta_u) / se_obs)

    # Restricted OLS enforcing r'beta = 0:
    # beta_r = beta_u - XtX_inv r (r' XtX_inv r)^{-1} (r' beta_u)
    beta_r = beta_u - h_vec * (float(r_vec @ beta_u) / r_XtXinv_r)
    yhat_r = X @ beta_r
    e_r = y - yhat_r

    # Precompute P_X = X @ XtX_inv (n x k) for ultra-fast residual computation across B draws
    # Actually: for each bootstrap draw y* = yhat_r + w_g * e_r,
    # e* = M_X y* = M_X (w_g * e_r) = (w_g * e_r) - X (XtX_inv (X' (w_g * e_r)))
    # AND r' beta* = r' XtX_inv X' y* = h_vec' X' (yhat_r + w_g * e_r) = Xh' (w_g * e_r) (since r'beta_r = 0!)
    # That makes B=999 exact WCB-r blazing fast (~0.08s for N=1800, K=60)!
    rng = np.random.default_rng(seed)
    W_draws = rng.choice(np.array([-1.0, 1.0]), size=(B, G))

    # Vectorized in chunks to stay memory-light
    abs_t_boot = np.empty(B, dtype=float)
    chunk = 100
    for start in range(0, B, chunk):
        end = min(B, start + chunk)
        Wb = W_draws[start:end]  # (c, G)
        # Expand cluster weights to observations: (c, n)
        W_obs = Wb[:, inv_idx]
        u_star = W_obs * e_r[None, :]  # (c, n)
        # Numerator: r'beta* = u_star @ Xh
        num = u_star @ Xh  # (c,)
        # Residuals: e* = u_star - (u_star @ X) @ (XtX_inv @ X.T)
        coef_u = (u_star @ X) @ XtX_inv.T  # (c, k)
        e_star = u_star - coef_u @ X.T  # (c, n)
        # Cluster scores for each draw: sum_{i in g} Xh_i * e*_bi
        z_star = e_star * Xh[None, :]  # (c, n)
        c_len = end - start
        sc_boot = np.zeros((c_len, G), dtype=float)
        # Aggregate per cluster
        for bi in range(c_len):
            np.add.at(sc_boot[bi], inv_idx, z_star[bi])
        se_boot = np.sqrt(np.maximum(dof_mult * np.sum(sc_boot ** 2, axis=1), 1e-30))
        abs_t_boot[start:end] = np.abs(num / se_boot)

    # Exact symmetric bootstrap p-value: (1 + #{|t*| >= |t_obs|}) / (B + 1)
    p_wcb = float((1 + np.sum(abs_t_boot >= abs(t_obs))) / (B + 1))
    return {"t_obs": t_obs, "p_wcb": p_wcb, "B": int(B)}


def stratified_permutation_test(
    y: np.ndarray,
    treat: np.ndarray,
    strata: np.ndarray,
    B: int = 1000,
    seed: int = 20261126,
) -> dict[str, float]:
    """Exact within-stratum permutation test of difference in means."""
    y = np.asarray(y, dtype=float)
    treat = np.asarray(treat, dtype=int)
    obs_diff = float(y[treat == 1].mean() - y[treat == 0].mean())

    rng = np.random.default_rng(seed)
    strata_indices = [np.where(strata == s)[0] for s in np.unique(strata)]
    perm_diffs = np.empty(B, dtype=float)
    n1_tot = int(treat.sum())
    n0_tot = int(len(treat) - n1_tot)

    for b in range(B):
        t_perm = np.empty_like(treat)
        for idx in strata_indices:
            t_perm[idx] = rng.permutation(treat[idx])
        s1 = float(y[t_perm == 1].sum()) / n1_tot
        s0 = float(y[t_perm == 0].sum()) / n0_tot
        perm_diffs[b] = s1 - s0

    p_two = float((1 + np.sum(np.abs(perm_diffs) >= abs(obs_diff))) / (B + 1))
    return {
        "obs_diff": obs_diff,
        "perm_mean": float(perm_diffs.mean()),
        "perm_sd": float(perm_diffs.std(ddof=1)),
        "p_perm": p_two,
        "B": int(B),
    }


def fit_clustered_logit(
    y: np.ndarray,
    X: np.ndarray,
    col_names: list[str],
    clusters: np.ndarray,
) -> dict[str, Any]:
    """Firm-clustered Binomial Logit returning log-odds, ORs, z, p."""
    model = sm.GLM(y.astype(float), X, family=sm.families.Binomial())
    res = model.fit(cov_type="cluster", cov_kwds={"groups": clusters}, maxiter=200)
    out_params = {}
    for i, nm in enumerate(col_names):
        b = float(res.params[i])
        se = float(res.bse[i])
        z = float(res.tvalues[i])
        p = float(res.pvalues[i])
        out_params[nm] = {
            "log_odds": b,
            "se": se,
            "z": z,
            "p": p,
            "or": float(np.exp(np.clip(b, -20, 20))),
            "or_ci_lo": float(np.exp(np.clip(b - 1.959964 * se, -20, 20))),
            "or_ci_hi": float(np.exp(np.clip(b + 1.959964 * se, -20, 20))),
        }
    return {
        "n": len(y),
        "k": int(X.shape[1]),
        "converged": bool(res.converged),
        "llf": float(res.llf),
        "params": out_params,
    }


def fit_newey_west_ols(
    y: np.ndarray,
    X: np.ndarray,
    col_names: list[str],
    maxlags: int = 4,
) -> dict[str, Any]:
    """OLS with Newey-West (1987) HAC covariance matrix."""
    model = sm.OLS(y.astype(float), X)
    res = model.fit(cov_type="HAC", cov_kwds={"maxlags": maxlags})
    params = {}
    for i, nm in enumerate(col_names):
        b = float(res.params[i])
        se = float(res.bse[i])
        params[nm] = {
            "beta": b,
            "se": se,
            "t": float(res.tvalues[i]),
            "p": float(res.pvalues[i]),
            "ci_lo": float(b - 1.959964 * se),
            "ci_hi": float(b + 1.959964 * se),
        }
    return {
        "n": len(y),
        "k": int(X.shape[1]),
        "maxlags": int(maxlags),
        "r2": float(res.rsquared),
        "params": params,
    }
