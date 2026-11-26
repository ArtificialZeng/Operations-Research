"""Core econometric engine for I4 SEC Rule 35d-1 analysis.

Guarantees:
1. Strict full-rank design matrix assertion (rank(X) == K); never silent pinv.
2. Iterative singleton FE removal prior to estimation.
3. Exact small-sample CR1 adjustment: (G / (G - 1)) * ((N - 1) / (N - K - N_fe_eff)).
4. Exact LSDV-equivalent Roodman (2019) restricted Wild Cluster Bootstrap (WCB)
   using Rademacher weights when absorbed FE are strictly nested inside clusters
   (verified against explicit LSDV to atol=1e-12 in pytest).
5. Exact complex-clustered randomization inference (2-sided) and Fisher exact tests.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats


def drop_singletons_iterative(df: pd.DataFrame, fe_cols: list[str]) -> tuple[pd.DataFrame, int]:
    """Iteratively remove singleton FE cells across all specified FE columns."""
    out = df.copy()
    n_start = len(out)
    while True:
        before = len(out)
        for col in fe_cols:
            cnt = out.groupby(col)[col].transform("size")
            out = out[cnt > 1]
        if len(out) == before:
            break
    return out.reset_index(drop=True), n_start - len(out)


def assert_nested_in_cluster(fe_ids: np.ndarray, cluster_ids: np.ndarray) -> None:
    """Assert every absorbed FE group maps to exactly one cluster."""
    s = pd.DataFrame({"fe": fe_ids, "cl": cluster_ids})
    n_cl_per_fe = s.groupby("fe")["cl"].nunique()
    if (n_cl_per_fe > 1).any():
        bad = int((n_cl_per_fe > 1).sum())
        raise ValueError(f"Absorbed FE is NOT nested in cluster: {bad} FE groups span >1 cluster.")


def demean_by_group(arr: np.ndarray, group_ids: np.ndarray) -> np.ndarray:
    """Exact within-group demeaning for 1D or 2D float arrays."""
    _, inv = np.unique(group_ids, return_inverse=True)
    n_g = int(inv.max()) + 1
    counts = np.bincount(inv, minlength=n_g).astype(float)
    if arr.ndim == 1:
        sums = np.bincount(inv, weights=arr, minlength=n_g)
        means = sums / counts
        return arr - means[inv]
    out = np.empty_like(arr, dtype=float)
    for j in range(arr.shape[1]):
        sums = np.bincount(inv, weights=arr[:, j], minlength=n_g)
        means = sums / counts
        out[:, j] = arr[:, j] - means[inv]
    return out


def ols_cr1_wcb(
    y: np.ndarray,
    X: np.ndarray,
    clusters: np.ndarray,
    test_col_idx: int = 0,
    n_fe_absorbed: int = 0,
    n_boot: int = 999,
    seed: int = 20261126,
    do_wcb: bool = True,
    return_cov: bool = False,
) -> dict:
    """Full-rank OLS with CR1 clustered SEs and exact Roodman (2019) restricted WCB.

    When absorbed FE are nested within `clusters` and `y`, `X` have been demeaned
    within those FE groups (with singletons dropped), setting `n_fe_absorbed` to the
    number of absorbed FE groups makes beta, SE_CR1, t_CR1, p_CR1, and p_WCB
    mathematically identical to brute-force explicit LSDV (up to machine precision).
    """
    y = np.asarray(y, dtype=float).ravel()
    X = np.asarray(X, dtype=float)
    if X.ndim == 1:
        X = X[:, None]
    clusters = np.asarray(clusters)
    n, k = X.shape
    if n != len(y) or n != len(clusters):
        raise ValueError(f"Length mismatch: y={len(y)}, X={n}, clusters={len(clusters)}")

    rank = int(np.linalg.matrix_rank(X))
    if rank < k:
        raise ValueError(
            f"Rank-deficient design matrix detected: rank={rank} < k={k} (n={n}). "
            "Drop collinear regressors before estimation."
        )

    k_total = k + int(n_fe_absorbed)
    if n <= k_total:
        raise ValueError(f"Insufficient degrees of freedom: N={n} <= K_total={k_total}")

    XtX = X.T @ X
    XtX_inv = np.linalg.inv(XtX)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta

    uniq_g, g_idx = np.unique(clusters, return_inverse=True)
    G = len(uniq_g)
    if G < 2:
        raise ValueError(f"Need at least 2 clusters for CR1 variance, got G={G}")

    scores = np.zeros((G, k), dtype=float)
    np.add.at(scores, g_idx, X * resid[:, None])
    meat = scores.T @ scores
    dof_scale = (G / (G - 1.0)) * ((n - 1.0) / (n - k_total))
    V = dof_scale * (XtX_inv @ meat @ XtX_inv)
    se = np.sqrt(np.maximum(np.diag(V), 1e-30))

    b_hat = float(beta[test_col_idx])
    se_hat = float(se[test_col_idx])
    t_stat = float(b_hat / se_hat)
    p_cr1 = float(2.0 * stats.t.sf(abs(t_stat), df=G - 1))

    p_wcb = None
    if do_wcb:
        mask_r = np.ones(k, dtype=bool)
        mask_r[test_col_idx] = False
        if mask_r.any():
            Xr = X[:, mask_r]
            beta_r = np.linalg.solve(Xr.T @ Xr, Xr.T @ y)
            e_r = y - Xr @ beta_r
        else:
            e_r = y.copy()

        # Fast exact Roodman (2019) matrix identity for restricted WCB
        # Equivalent to full LSDV when absorbed FE are nested in clusters!
        S = np.zeros((G, k), dtype=float)
        np.add.at(S, g_idx, X * e_r[:, None])
        u = XtX_inv[test_col_idx, :]
        Xu = X @ u
        B_mat = np.zeros((G, k), dtype=float)
        np.add.at(B_mat, g_idx, X * Xu[:, None])
        a_g = S @ u

        rng = np.random.default_rng(seed)
        W = rng.choice([-1.0, 1.0], size=(G, n_boot))
        delta_beta = XtX_inv @ (S.T @ W)
        b_star = delta_beta[test_col_idx, :]
        score_star = a_g[:, None] * W - B_mat @ delta_beta
        se_star = np.sqrt(np.maximum(dof_scale * np.sum(score_star**2, axis=0), 1e-30))
        t_boots = b_star / se_star
        p_wcb = float((np.sum(np.abs(t_boots) >= abs(t_stat)) + 1.0) / (n_boot + 1.0))

    res = {
        "beta": b_hat,
        "se_cr1": se_hat,
        "t_cr1": t_stat,
        "p_cr1": p_cr1,
        "p_wcb": p_wcb,
        "G": int(G),
        "N": int(n),
        "rank": int(rank),
        "k": int(k),
        "n_fe_absorbed": int(n_fe_absorbed),
        "k_total": int(k_total),
        "dof_t": int(G - 1),
    }
    if return_cov:
        res["V"] = V
        res["beta_vec"] = beta
    return res


def run_absorbed_twfe(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    absorb_fe_col: str,
    cluster_col: str,
    time_fe_col: str | None = None,
    test_col_idx: int = 0,
    n_boot: int = 999,
    seed: int = 20261126,
    do_wcb: bool = True,
    return_cov: bool = False,
) -> dict:
    """Run exact LSDV-equivalent absorbed FE regression.

    Drops singletons iteratively on absorb_fe_col (and time_fe_col if provided),
    asserts absorb_fe_col is strictly nested in cluster_col, demeans y, X, and
    time_fe dummies within absorb_fe_col, verifies full rank (dropping zero-variance
    time dummies if any after singleton drop), and calls ols_cr1_wcb with exact
    absorbed degrees of freedom.
    """
    fe_check = [absorb_fe_col] + ([time_fe_col] if time_fe_col is not None else [])
    sub, n_singletons = drop_singletons_iterative(df, fe_check)
    fe_ids = sub[absorb_fe_col].to_numpy()
    cl_ids = sub[cluster_col].to_numpy()
    assert_nested_in_cluster(fe_ids, cl_ids)

    y_dm = demean_by_group(sub[y_col].to_numpy(dtype=float), fe_ids)
    X_core = sub[x_cols].to_numpy(dtype=float)
    X_core_dm = demean_by_group(X_core, fe_ids)

    if time_fe_col is not None:
        t_dum = pd.get_dummies(sub[time_fe_col].astype(str), drop_first=True, dtype=float).to_numpy()
        t_dum_dm = demean_by_group(t_dum, fe_ids)
        # Keep only non-collinear time dummies if any disconnected component exists
        keep_t = [j for j in range(t_dum_dm.shape[1]) if np.linalg.norm(t_dum_dm[:, j]) > 1e-10]
        X_full = np.column_stack([X_core_dm, t_dum_dm[:, keep_t]]) if keep_t else X_core_dm
    else:
        X_full = X_core_dm

    n_fe = int(sub[absorb_fe_col].nunique())
    res = ols_cr1_wcb(
        y=y_dm,
        X=X_full,
        clusters=cl_ids,
        test_col_idx=test_col_idx,
        n_fe_absorbed=n_fe,
        n_boot=n_boot,
        seed=seed,
        do_wcb=do_wcb,
        return_cov=return_cov,
    )
    res["n_singletons_dropped"] = int(n_singletons)
    return res


def exact_cluster_ri_did(
    df: pd.DataFrame,
    y_col: str,
    treat_col: str,
    post2_col: str,
    post1_col: str | None,
    time_col: str,
    cluster_col: str,
    n_perm: int = 2000,
    seed: int = 20261126,
) -> dict:
    """Exact complex-clustered Randomization Inference (2-sided and 1-sided).

    Permutes binary cluster-level treatment assignment `treat_col` across clusters
    preserving exact number of treated clusters, re-estimates DiD beta and CR1 t-stat.
    """
    cl_treat = df.groupby(cluster_col)[treat_col].first()
    cl_names = cl_treat.index.to_numpy()
    orig_tr = cl_treat.to_numpy(dtype=float)
    n_cl = len(cl_names)
    cl_map = {c: i for i, c in enumerate(cl_names)}
    row_cl_idx = df[cluster_col].map(cl_map).to_numpy()

    y = df[y_col].to_numpy(dtype=float)
    p2 = df[post2_col].to_numpy(dtype=float)
    p1 = df[post1_col].to_numpy(dtype=float) if post1_col is not None else None
    fe_t = pd.get_dummies(df[time_col].astype(str), drop_first=True, dtype=float).to_numpy()
    ones = np.ones(len(df), dtype=float)

    def _fit(tr_vec: np.ndarray) -> tuple[float, float]:
        tr_row = tr_vec[row_cl_idx]
        cols = [tr_row * p2]
        if p1 is not None:
            cols.append(tr_row * p1)
        cols.extend([tr_row, ones, fe_t])
        X = np.column_stack(cols)
        XtX_inv = np.linalg.inv(X.T @ X)
        beta = XtX_inv @ (X.T @ y)
        resid = y - X @ beta
        scores = np.zeros((n_cl, X.shape[1]), dtype=float)
        np.add.at(scores, row_cl_idx, X * resid[:, None])
        dof = (n_cl / (n_cl - 1.0)) * ((len(y) - 1.0) / (len(y) - X.shape[1]))
        V00 = float(dof * (XtX_inv[0, :] @ (scores.T @ scores) @ XtX_inv[0, :]))
        se0 = np.sqrt(max(V00, 1e-30))
        return float(beta[0]), float(beta[0] / se0)

    obs_b, obs_t = _fit(orig_tr)
    rng = np.random.default_rng(seed)
    perm_bs = np.empty(n_perm, dtype=float)
    perm_ts = np.empty(n_perm, dtype=float)
    for b in range(n_perm):
        p_tr = rng.permutation(orig_tr)
        perm_bs[b], perm_ts[b] = _fit(p_tr)

    p_2sided_b = float((np.sum(np.abs(perm_bs) >= abs(obs_b)) + 1.0) / (n_perm + 1.0))
    p_1sided_b = float((np.sum(perm_bs >= obs_b) + 1.0) / (n_perm + 1.0))
    p_2sided_t = float((np.sum(np.abs(perm_ts) >= abs(obs_t)) + 1.0) / (n_perm + 1.0))
    p_1sided_t = float((np.sum(perm_ts >= obs_t) + 1.0) / (n_perm + 1.0))
    return {
        "obs_beta": obs_b,
        "obs_t": obs_t,
        "n_clusters": int(n_cl),
        "n_treated_clusters": int(orig_tr.sum()),
        "n_control_clusters": int(n_cl - orig_tr.sum()),
        "n_perm": int(n_perm),
        "ri_p_2sided_beta": p_2sided_b,
        "ri_p_1sided_beta": p_1sided_b,
        "ri_p_2sided_t": p_2sided_t,
        "ri_p_1sided_t": p_1sided_t,
    }


def exact_fisher_2sided(a: int, b: int, c: int, d: int) -> dict:
    """2x2 exact Fisher test (2-sided and 1-sided greater) for [[a, b], [c, d]]."""
    tbl = [[int(a), int(b)], [int(c), int(d)]]
    odds, p2 = stats.fisher_exact(tbl, alternative="two-sided")
    _, p1 = stats.fisher_exact(tbl, alternative="greater")
    return {
        "table": tbl,
        "odds_ratio": float(odds) if np.isfinite(odds) else None,
        "p_2sided": float(p2),
        "p_1sided_greater": float(p1),
    }
