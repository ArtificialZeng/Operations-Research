"""Step 4: Complete 4-Pillar Econometric Suite for D12 Boost.
Implements exact full-rank design-matrix verification, finite-sample CR1 t(G-1) cluster-robust
inference, and exact Cameron-Gelbach-Miller (2008) null-imposed B=999 Rademacher Wild Cluster
Bootstrap p-values across all 4 research pillars.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
PROC_DIR = BASE_DIR / "data_processed"
RES_DIR = BASE_DIR / "results"
RES_DIR.mkdir(parents=True, exist_ok=True)


def _prune_to_full_rank(
    X_keep: np.ndarray,
    keep_names: list[str],
    X_fe: np.ndarray,
    fe_names: list[str],
    tol: float = 1e-10,
) -> tuple[np.ndarray, list[str], int]:
    """Ensure [1, X_keep, X_fe_pruned] is strictly full column rank while keeping all target regressors."""
    n = X_keep.shape[0]
    intercept = np.ones((n, 1), dtype=np.float64)
    if X_keep.shape[1] > 0:
        base = np.hstack([intercept, X_keep])
        base_names = ["Intercept"] + list(keep_names)
    else:
        base = intercept
        base_names = ["Intercept"]

    # Verify base itself is full rank
    r_base = np.linalg.matrix_rank(base, tol=tol)
    if r_base < base.shape[1]:
        raise ValueError(f"Target regressors are rank-deficient: rank={r_base} < cols={base.shape[1]} ({base_names})")

    if X_fe.shape[1] == 0:
        return base, base_names, 0

    # Gram-Schmidt / QR column selection preserving base columns first
    Q_base, _ = np.linalg.qr(base, mode="reduced")
    # Project FE columns orthogonal to base
    fe_orth = X_fe - Q_base @ (Q_base.T @ X_fe)
    col_norms = np.linalg.norm(fe_orth, axis=0)
    nonzero_mask = col_norms > tol
    if not nonzero_mask.any():
        return base, base_names, int(X_fe.shape[1])

    cand_idx = np.where(nonzero_mask)[0]
    fe_sub = fe_orth[:, cand_idx]
    # QR with pivoting via scipy.linalg.qr
    from scipy.linalg import qr as scipy_qr

    _, R, piv = scipy_qr(fe_sub, mode="economic", pivoting=True)
    diag = np.abs(np.diag(R))
    max_diag = diag[0] if len(diag) else 0.0
    fe_rank = int(np.sum(diag > max(tol, max_diag * 1e-10)))
    chosen_local = np.sort(piv[:fe_rank])
    chosen_idx = cand_idx[chosen_local]

    X_full = np.hstack([base, X_fe[:, chosen_idx]])
    names_full = base_names + [fe_names[i] for i in chosen_idx]
    n_dropped = int(X_fe.shape[1] - len(chosen_idx))

    final_rank = int(np.linalg.matrix_rank(X_full, tol=1e-9))
    if final_rank != X_full.shape[1]:
        # Fallback tighter tolerance
        fe_rank = int(np.sum(diag > max(1e-7, max_diag * 1e-7)))
        chosen_local = np.sort(piv[:fe_rank])
        chosen_idx = cand_idx[chosen_local]
        X_full = np.hstack([base, X_fe[:, chosen_idx]])
        names_full = base_names + [fe_names[i] for i in chosen_idx]
        n_dropped = int(X_fe.shape[1] - len(chosen_idx))
        final_rank = int(np.linalg.matrix_rank(X_full, tol=1e-8))
        if final_rank != X_full.shape[1]:
            raise ValueError(f"Full-rank assertion failed: rank={final_rank} vs cols={X_full.shape[1]}")

    return X_full, names_full, n_dropped


def _drop_fe_singletons(df: pd.DataFrame, fe_cols: list[str]) -> tuple[pd.DataFrame, int]:
    """Iteratively remove singleton fixed-effect cells (Correia 2015 / reghdfe convention)."""
    if not fe_cols:
        return df, 0
    sub = df
    prev = len(sub) + 1
    while len(sub) < prev:
        prev = len(sub)
        for fc in fe_cols:
            vc = sub[fc].value_counts()
            sub = sub[sub[fc].isin(vc[vc > 1].index)]
    return sub.copy(), int(len(df) - len(sub))


def fit_ols_cr1_wcb(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    fe_cols: list[str],
    cluster_col: str,
    target_vars: list[str] | None = None,
    n_boot: int = 999,
    seed: int = 20261125,
    drop_singletons: bool = False,
) -> dict:
    """Fit full-rank OLS with CR1 cluster-robust SEs, finite-sample t(G-1) p-values/CIs,
    and exact Cameron-Gelbach-Miller (2008) null-imposed Rademacher Wild Cluster Bootstrap p-values.
    """
    if target_vars is None:
        target_vars = list(x_cols)

    req_cols = list(dict.fromkeys([y_col] + x_cols + fe_cols + [cluster_col]))
    sub = df.dropna(subset=req_cols).copy()
    n_singletons_dropped = 0
    if drop_singletons and fe_cols:
        sub, n_singletons_dropped = _drop_fe_singletons(sub, fe_cols)
    if len(sub) < 25:
        return {"skipped": True, "reason": "n<25", "n": len(sub)}

    # Ensure every target var has non-zero variance
    active_x = [c for c in x_cols if sub[c].nunique(dropna=True) > 1]
    active_targets = [c for c in target_vars if c in active_x]
    if not active_targets:
        return {"skipped": True, "reason": "no_target_variation", "n": len(sub)}

    y = sub[y_col].to_numpy(dtype=np.float64)
    X_keep = sub[active_x].to_numpy(dtype=np.float64)

    fe_blocks = []
    fe_names: list[str] = []
    for fc in fe_cols:
        if sub[fc].nunique(dropna=True) > 1:
            dum = pd.get_dummies(sub[fc].astype(str), prefix=fc, drop_first=True, dtype=np.float64)
            fe_blocks.append(dum.to_numpy(dtype=np.float64))
            fe_names.extend(list(dum.columns))
    X_fe = np.hstack(fe_blocks) if fe_blocks else np.empty((len(sub), 0), dtype=np.float64)

    X, names, n_dropped_fe = _prune_to_full_rank(X_keep, active_x, X_fe, fe_names)
    n, k = X.shape
    if n <= k + 2:
        return {"skipped": True, "reason": f"insufficient_df(n={n},k={k})", "n": int(n), "k": int(k)}

    # Factorize clusters
    cl_codes, cl_uniques = pd.factorize(sub[cluster_col].astype(str))
    G = len(cl_uniques)
    if G < 4:
        return {"skipped": True, "reason": f"G<4(G={G})", "n": int(n), "G": int(G)}

    # OLS fit via QR/SVD-safe solve
    XtX = X.T @ X
    P = np.linalg.inv(XtX)
    beta = P @ (X.T @ y)
    resid = y - X @ beta
    tss = float(np.sum((y - y.mean()) ** 2))
    rss = float(np.sum(resid**2))
    r2 = 1.0 - rss / tss if tss > 0 else np.nan

    # CR1 cluster-robust variance (Stata finite-sample scaling)
    # Aggregate X_g' u_g by cluster using np.add.at
    Xu = X * resid[:, None]
    cluster_scores = np.zeros((G, k), dtype=np.float64)
    np.add.at(cluster_scores, cl_codes, Xu)
    meat = cluster_scores.T @ cluster_scores
    scale_cr1 = (G / (G - 1.0)) * ((n - 1.0) / (n - k))
    V_cr1 = scale_cr1 * (P @ meat @ P)
    se_cr1 = np.sqrt(np.maximum(np.diag(V_cr1), 1e-24))

    # Exact null-imposed Rademacher Wild Cluster Bootstrap (B = n_boot)
    rng = np.random.default_rng(seed)
    W = rng.choice(np.array([-1.0, 1.0]), size=(n_boot, G))

    t_crit = float(stats.t.ppf(0.975, df=G - 1))
    name_to_idx = {nm: idx for idx, nm in enumerate(names)}

    # Precompute cluster-indexed XtX pieces? Actually we only need cluster sums for each target j!
    results_terms: dict[str, dict] = {}
    for j_name in active_targets:
        j = name_to_idx[j_name]
        b_hat = float(beta[j])
        se_hat = float(se_cr1[j])
        t_obs = b_hat / se_hat if se_hat > 0 else np.nan
        p_t = float(2.0 * stats.t.sf(abs(t_obs), df=G - 1))
        ci_lo = b_hat - t_crit * se_hat
        ci_hi = b_hat + t_crit * se_hat

        # Null-imposed restricted residuals (H0: beta_j = 0)
        mask_rest = np.ones(k, dtype=bool)
        mask_rest[j] = False
        X_r = X[:, mask_rest]
        beta_r = np.linalg.lstsq(X_r, y, rcond=None)[0]
        u_tilde = y - X_r @ beta_r

        # Vectorized EXACT CR1 Wild Cluster Bootstrap (algebraically identical to re-estimating OLS + CR1)
        a_j = P[:, j]  # shape (k,)
        z_j = X @ a_j  # shape (n,)

        c_g = np.zeros(G, dtype=np.float64)
        np.add.at(c_g, cl_codes, z_j * u_tilde)

        V_g = np.zeros((G, k), dtype=np.float64)
        np.add.at(V_g, cl_codes, X * u_tilde[:, None])

        Q_g = np.zeros((G, k), dtype=np.float64)
        np.add.at(Q_g, cl_codes, X * z_j[:, None])

        beta_b = W @ c_g  # (B,)
        dbeta_b = (W @ V_g) @ P  # (B, k)
        score_bg = W * c_g[None, :] - dbeta_b @ Q_g.T  # (B, G)
        se_b = np.sqrt(np.maximum(scale_cr1 * np.sum(score_bg**2, axis=1), 1e-24))
        t_b = beta_b / se_b
        p_wcb = float((1 + np.sum(np.abs(t_b) >= abs(t_obs))) / (n_boot + 1))

        results_terms[j_name] = {
            "coef": round(b_hat, 4),
            "se_cr1": round(se_hat, 4),
            "t_cr1": round(float(t_obs), 3),
            "p_t_G1": round(p_t, 6),
            "p_wcb": round(p_wcb, 4),
            "ci95_lo": round(float(ci_lo), 4),
            "ci95_hi": round(float(ci_hi), 4),
        }

    return {
        "skipped": False,
        "y": y_col,
        "n": int(n),
        "k": int(k),
        "full_rank_verified": True,
        "n_collinear_fe_dropped": int(n_dropped_fe),
        "n_singletons_dropped": int(n_singletons_dropped),
        "G_clusters": int(G),
        "df_t": int(G - 1),
        "r2": round(float(r2), 4),
        "y_mean": round(float(y.mean()), 4),
        "terms": results_terms,
        "_beta": beta,
        "_V_cr1": V_cr1,
        "_name_to_idx": name_to_idx,
    }


def strip_private(res: dict) -> dict:
    return {k: v for k, v in res.items() if not k.startswith("_")}


def wald_joint_test(res: dict, var_list: list[str]) -> dict:
    """Cluster-robust Wald F-test for joint null beta[var_list] == 0 with F(q, G-1) p-value."""
    if res.get("skipped"):
        return {"skipped": True}
    idx_map = res["_name_to_idx"]
    present = [v for v in var_list if v in idx_map]
    if not present:
        return {"skipped": True}
    idxs = [idx_map[v] for v in present]
    b = res["_beta"][idxs]
    V = res["_V_cr1"][np.ix_(idxs, idxs)]
    q = len(idxs)
    G = res["G_clusters"]
    try:
        W = float(b.T @ np.linalg.inv(V) @ b)
        F_stat = W / q
        p_val = float(stats.f.sf(F_stat, q, max(1, G - 1)))
        return {"q": q, "F_stat": round(F_stat, 3), "df2": int(G - 1), "p_value": round(p_val, 5)}
    except np.linalg.LinAlgError:
        return {"skipped": True, "reason": "singular_submatrix"}


def fit_absorbed_2way_fe_did(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    unit_col: str,
    time_cols: list[str],
    cluster_col: str,
    n_boot: int = 999,
    seed: int = 20261125,
) -> dict:
    """Fast exact within-unit demeaning (Frisch-Waugh-Lovell) + explicit time FE dummies for large
    balanced/unbalanced event-study panels (e.g., 114,000 campaign-month rows with 4,560 Campaign FEs),
    with CR1 SEs, finite-sample t(G-1), and exact Rademacher Wild Cluster Bootstrap!
    """
    req = list(dict.fromkeys([y_col] + x_cols + [unit_col] + time_cols + [cluster_col]))
    sub = df.dropna(subset=req).copy()
    if len(sub) < 100:
        return {"skipped": True, "n": len(sub)}

    active_x = [c for c in x_cols if sub[c].nunique(dropna=True) > 1]
    if not active_x:
        return {"skipped": True, "n": len(sub)}

    # Build time FE dummies (rel_month, cal_ym)
    fe_blocks = []
    fe_names: list[str] = []
    for tc in time_cols:
        if sub[tc].nunique(dropna=True) > 1:
            d = pd.get_dummies(sub[tc].astype(str), prefix=tc, drop_first=True, dtype=np.float64)
            fe_blocks.append(d.to_numpy(dtype=np.float64))
            fe_names.extend(list(d.columns))
    X_raw = np.hstack([sub[active_x].to_numpy(dtype=np.float64)] + fe_blocks)
    list(active_x) + fe_names
    y_raw = sub[y_col].to_numpy(dtype=np.float64)

    # Exact within-unit (Campaign FE) demeaning via pandas/numpy group means
    u_codes, u_uniques = pd.factorize(sub[unit_col].astype(str))
    n_units = len(u_uniques)
    counts_u = np.bincount(u_codes).astype(np.float64)

    y_sum = np.bincount(u_codes, weights=y_raw)
    y_dm = y_raw - (y_sum / counts_u)[u_codes]

    X_dm = np.empty_like(X_raw)
    for col_i in range(X_raw.shape[1]):
        csum = np.bincount(u_codes, weights=X_raw[:, col_i])
        X_dm[:, col_i] = X_raw[:, col_i] - (csum / counts_u)[u_codes]

    # Prune any time FE collinear after unit demeaning (keep active_x strictly intact)
    n_x = len(active_x)
    X_keep_dm = X_dm[:, :n_x]
    X_fe_dm = X_dm[:, n_x:]

    from scipy.linalg import qr as scipy_qr

    Q_base, _ = np.linalg.qr(X_keep_dm, mode="reduced")
    fe_orth = X_fe_dm - Q_base @ (Q_base.T @ X_fe_dm)
    cnorms = np.linalg.norm(fe_orth, axis=0)
    nz = np.where(cnorms > 1e-9)[0]
    if len(nz):
        _, R, piv = scipy_qr(fe_orth[:, nz], mode="economic", pivoting=True)
        diag = np.abs(np.diag(R))
        r_fe = int(np.sum(diag > max(1e-9, diag[0] * 1e-10)))
        chosen = nz[np.sort(piv[:r_fe])]
        X = np.hstack([X_keep_dm, X_fe_dm[:, chosen]])
        names = list(active_x) + [fe_names[i] for i in chosen]
    else:
        X = X_keep_dm
        names = list(active_x)

    n, k_explicit = X.shape
    k_eff = k_explicit + n_units  # absorbed unit FEs count toward DOF!
    assert np.linalg.matrix_rank(X, tol=1e-8) == k_explicit

    cl_codes, cl_uniques = pd.factorize(sub[cluster_col].astype(str))
    G = len(cl_uniques)

    XtX = X.T @ X
    P = np.linalg.inv(XtX)
    beta = P @ (X.T @ y_dm)
    resid = y_dm - X @ beta

    Xu = X * resid[:, None]
    cl_scores = np.zeros((G, k_explicit), dtype=np.float64)
    np.add.at(cl_scores, cl_codes, Xu)
    meat = cl_scores.T @ cl_scores
    scale_cr1 = (G / (G - 1.0)) * ((n - 1.0) / max(1.0, n - k_eff))
    V_cr1 = scale_cr1 * (P @ meat @ P)
    se_cr1 = np.sqrt(np.maximum(np.diag(V_cr1), 1e-24))

    rng = np.random.default_rng(seed)
    W = rng.choice(np.array([-1.0, 1.0]), size=(n_boot, G))
    t_crit = float(stats.t.ppf(0.975, df=G - 1))

    terms = {}
    for j, nm in enumerate(active_x):
        b_hat = float(beta[j])
        se_hat = float(se_cr1[j])
        t_obs = b_hat / se_hat if se_hat > 0 else np.nan
        p_t = float(2.0 * stats.t.sf(abs(t_obs), df=G - 1))

        # Exact null-imposed WCB on demeaned model (valid when units are nested within clusters!)
        mask_r = np.ones(k_explicit, dtype=bool)
        mask_r[j] = False
        X_r = X[:, mask_r]
        b_r = np.linalg.lstsq(X_r, y_dm, rcond=None)[0]
        u_tilde = y_dm - X_r @ b_r

        a_j = P[:, j]
        z_j = X @ a_j
        c_g = np.zeros(G, dtype=np.float64)
        np.add.at(c_g, cl_codes, z_j * u_tilde)
        V_g = np.zeros((G, k_explicit), dtype=np.float64)
        np.add.at(V_g, cl_codes, X * u_tilde[:, None])
        Q_g = np.zeros((G, k_explicit), dtype=np.float64)
        np.add.at(Q_g, cl_codes, X * z_j[:, None])

        beta_b = W @ c_g
        dbeta_b = (W @ V_g) @ P
        score_bg = W * c_g[None, :] - dbeta_b @ Q_g.T
        se_b = np.sqrt(np.maximum(scale_cr1 * np.sum(score_bg**2, axis=1), 1e-24))
        t_b = beta_b / se_b
        p_wcb = float((1 + np.sum(np.abs(t_b) >= abs(t_obs))) / (n_boot + 1))

        terms[nm] = {
            "coef": round(b_hat, 5),
            "se_cr1": round(se_hat, 5),
            "t_cr1": round(float(t_obs), 3),
            "p_t_G1": round(p_t, 6),
            "p_wcb": round(p_wcb, 4),
            "ci95_lo": round(float(b_hat - t_crit * se_hat), 5),
            "ci95_hi": round(float(b_hat + t_crit * se_hat), 5),
        }

    return {
        "skipped": False,
        "y": y_col,
        "n_obs": int(n),
        "n_units": int(n_units),
        "k_explicit": int(k_explicit),
        "G_clusters": int(G),
        "df_t": int(G - 1),
        "full_rank_verified": True,
        "terms": terms,
        "_beta": beta,
        "_V_cr1": V_cr1,
        "_name_to_idx": {nm: i for i, nm in enumerate(names)},
    }


def add_common_fe_helpers(df: pd.DataFrame) -> pd.DataFrame:
    d = df.copy()
    top_comps = d["comp_top"].value_counts().head(14).index
    d["comp_fe"] = np.where(d["comp_top"].isin(top_comps), d["comp_top"], "OTHER")
    d["mfg_yr"] = d["mfg"].astype(str) + "__" + d["rec_year"].astype(str)
    d["min_my_fe"] = d["min_my"].clip(lower=2008, upper=2026).round().astype("Int64").astype(str)
    # Collapse rare primary_make_model (<3 campaigns) into OEM_OTHER for stable Make-Model FE
    mm_vc = d["primary_make_model"].value_counts()
    keep_mm = mm_vc[mm_vc >= 3].index
    d["mm_fe"] = np.where(d["primary_make_model"].isin(keep_mm), d["primary_make_model"], "OTHER__" + d["mfg"].astype(str))
    # Age polynomials (scaled in years for numeric conditioning)
    d["age_yr"] = d["days_since_recall"] / 365.25
    d["age_yr2"] = d["age_yr"] ** 2
    d["age_yr3"] = d["age_yr"] ** 3
    return d


def run_pillar1_blast_radius_and_selection(df_all: pd.DataFrame) -> dict:
    """Pillar 1: Blast-Radius Concentration & Endogenous Remedy Selection vs Architectural Decomposition."""
    c18 = add_common_fe_helpers(df_all[df_all["rec_year"].between(2018, 2026)].copy())
    ota_oems = set(c18[c18["is_ota_audited"] == 1]["mfg"].unique())
    sw_all = c18[c18["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])].copy()
    sw_ota_oems = sw_all[sw_all["mfg"].isin(ota_oems)].copy()
    sw_mod = sw_ota_oems[sw_ota_oems["min_my"].between(2020, 2026)].copy()
    sw_2018_24 = sw_ota_oems[sw_ota_oems["rec_year"].between(2018, 2024)].copy()

    # 1A. Main Blast-Radius Regressions (both Audited 4-Way & Official API OTA)
    p1_main: dict = {}
    outcomes = ["log_potaff", "n_models", "n_mys", "log_potaff_per_my"]
    for y in outcomes:
        p1_main[f"sw_ota_oems_4way_{y}"] = strip_private(
            fit_ols_cr1_wcb(sw_ota_oems, y, ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        )
        p1_main[f"sw_ota_oems_anyota_{y}"] = strip_private(
            fit_ols_cr1_wcb(sw_ota_oems, y, ["is_ota_audited"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        )
        p1_main[f"sw_ota_oems_api2018_24_{y}"] = strip_private(
            fit_ols_cr1_wcb(sw_2018_24, y, ["is_ota_api_full"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        )
        p1_main[f"sw_ota_oems_apifull_{y}"] = strip_private(
            fit_ols_cr1_wcb(sw_ota_oems, y, ["is_ota_api_full"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        )

    # All-Vehicle benchmark (Pure_OTA, Hybrid_OTA, Dealer_Software vs Physical_Hardware)
    p1_allveh = {}
    for y in outcomes:
        p1_allveh[f"all_vehicles_4way_{y}"] = strip_private(
            fit_ols_cr1_wcb(c18, y, ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        )
        p1_allveh[f"all_vehicles_api2018_24_{y}"] = strip_private(
            fit_ols_cr1_wcb(
                c18[c18["rec_year"].between(2018, 2024)],
                y,
                ["is_ota_api_full", "is_dealer_sw"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
            )
        )

    # Robustness ladder on log_potaff (SW within OTA-OEMs)
    p1_robust = {
        "modern_MY2020plus_4way": strip_private(
            fit_ols_cr1_wcb(sw_mod, "log_potaff", ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        ),
        "modern_MY2020plus_anyota": strip_private(
            fit_ols_cr1_wcb(sw_mod, "log_potaff", ["is_ota_audited"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        ),
        "oem_x_year_fe_4way": strip_private(
            fit_ols_cr1_wcb(sw_ota_oems, "log_potaff", ["is_ota_pure", "is_ota_hybrid"], ["mfg_yr", "min_my_fe", "comp_fe"], "mfg")
        ),
        "make_x_model_fe_4way": strip_private(
            fit_ols_cr1_wcb(sw_ota_oems, "log_potaff", ["is_ota_pure", "is_ota_hybrid"], ["mm_fe", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        ),
        "breadth_controlled_4way": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems,
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid", "log_n_models", "log_n_mys"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
                target_vars=["is_ota_pure", "is_ota_hybrid"],
            )
        ),
        "excl_tesla_4way": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems[sw_ota_oems["is_tesla"] == 0],
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "excl_tesla_ford_4way": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems[~sw_ota_oems["mfg"].isin(["Tesla, Inc.", "Ford Motor Company"])],
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "hybrid_swchoice_vs_hwmixed": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems,
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid_swchoice", "is_ota_hybrid_hwmixed"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "light_duty_passenger_4way": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems[sw_ota_oems["is_light_duty_passenger"] == 1],
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "singleton_dropped_main_4way": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems,
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
                drop_singletons=True,
            )
        ),
        "singleton_dropped_oem_x_year_4way": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems,
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg_yr", "min_my_fe", "comp_fe"],
                "mfg",
                drop_singletons=True,
            )
        ),
        "singleton_dropped_make_x_model_4way": strip_private(
            fit_ols_cr1_wcb(
                sw_ota_oems,
                "log_potaff",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mm_fe", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
                drop_singletons=True,
            )
        ),
    }

    # 1B. Endogenous Fixed-Cost Selection vs Architectural Blast-Radius Decomposition
    # (1) Fleet-size quantile & threshold distribution across modalities
    dist_tbl = {}
    for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
        s = c18[c18["modality4"] == mod]["potaff"].dropna()
        dist_tbl[mod] = {
            "n": len(s),
            "p10": round(float(np.percentile(s, 10)), 1),
            "p25": round(float(np.percentile(s, 25)), 1),
            "p50": round(float(np.percentile(s, 50)), 1),
            "p75": round(float(np.percentile(s, 75)), 1),
            "p90": round(float(np.percentile(s, 90)), 1),
            "mean": round(float(s.mean()), 1),
            "pct_ge_10k": round(100.0 * float((s >= 10_000).mean()), 2),
            "pct_ge_50k": round(100.0 * float((s >= 50_000).mean()), 2),
            "pct_ge_100k": round(100.0 * float((s >= 100_000).mean()), 2),
        }

    # (2) Intent-to-Treat (ITT) Staggered OEM OTA-Capability Adoption Event Study (ALL Software 2015-2026!)
    # NO conditioning on remedy choice — pools OTA + Dealer-SW across ALL OEMs (including never-OTA controls!)
    sw15 = add_common_fe_helpers(df_all[(df_all["rec_year"].between(2015, 2026)) & (df_all["is_sw_any"] == 1)].copy())
    # Keep OEMs with >= 3 software recalls over 2015-2026 so OEM FE is well-identified
    oem_sw_cnt = sw15["mfg"].value_counts()
    sw15_es = sw15[sw15["mfg"].isin(oem_sw_cnt[oem_sw_cnt >= 3].index)].copy()

    ev_bins = [-3, -2, 0, 1, 2, 3]  # omit -1 as reference; never-OTA OEMs have all 0
    ev_cols = []
    for k in ev_bins:
        cname = f"ev_m{abs(k)}" if k < 0 else f"ev_p{k}"
        if k == -3:
            sw15_es[cname] = ((sw15_es["oem_ever_ota"] == 1) & (sw15_es["event_time_yr"] <= -3)).astype(float)
        elif k == 3:
            sw15_es[cname] = ((sw15_es["oem_ever_ota"] == 1) & (sw15_es["event_time_yr"] >= 3)).astype(float)
        else:
            sw15_es[cname] = ((sw15_es["oem_ever_ota"] == 1) & (sw15_es["event_time_yr"] == k)).astype(float)
        ev_cols.append(cname)

    sw15_es["post_ota_adopt"] = ((sw15_es["oem_ever_ota"] == 1) & (sw15_es["event_time_yr"] >= 0)).astype(float)

    itt_es_raw = fit_ols_cr1_wcb(sw15_es, "log_potaff", ev_cols, ["mfg", "rec_year", "comp_fe"], "mfg")
    itt_pre_wald = wald_joint_test(itt_es_raw, ["ev_m3", "ev_m2"])
    itt_post_wald = wald_joint_test(itt_es_raw, ["ev_p0", "ev_p1", "ev_p2", "ev_p3"])

    itt_did_pooled = strip_private(
        fit_ols_cr1_wcb(sw15_es, "log_potaff", ["post_ota_adopt"], ["mfg", "rec_year", "comp_fe"], "mfg")
    )
    itt_did_with_myfe = strip_private(
        fit_ols_cr1_wcb(sw15_es, "log_potaff", ["post_ota_adopt"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
    )
    itt_did_nmodels = strip_private(
        fit_ols_cr1_wcb(sw15_es, "n_models", ["post_ota_adopt"], ["mfg", "rec_year", "comp_fe"], "mfg")
    )
    itt_did_excl_tesla = strip_private(
        fit_ols_cr1_wcb(
            sw15_es[sw15_es["is_tesla"] == 0],
            "log_potaff",
            ["post_ota_adopt"],
            ["mfg", "rec_year", "comp_fe"],
            "mfg",
        )
    )

    # True Sun & Abraham (2021) Saturated Cohort x Relative-Time Interaction-Weighted (IW) Estimator!
    # Exclude partial-year cohort 2026 (1 OEM, 0 obs at ell = -1) so ZERO post-adoption obs leak into controls.
    sw15_sa = sw15_es[sw15_es["oem_first_ota_year"] != 2026].copy()
    sw15_sa["ev_bin"] = sw15_sa["event_time_yr"].clip(lower=-3, upper=3)
    cohorts = sorted(sw15_sa[sw15_sa["oem_ever_ota"] == 1]["oem_first_ota_year"].dropna().unique().astype(int))
    sa_cell_cols: list[str] = []
    sa_cell_meta: list[tuple[str, int, int, int]] = []  # (col, cohort, ell, n_obs)
    for c_yr in cohorts:
        for ell in [-3, -2, 0, 1, 2, 3]:
            ind = ((sw15_sa["oem_first_ota_year"] == c_yr) & (sw15_sa["ev_bin"] == ell)).astype(float)
            cnt = int(ind.sum())
            if cnt > 0:
                col_c = f"sa_c{c_yr}_m{abs(ell)}" if ell < 0 else f"sa_c{c_yr}_p{ell}"
                sw15_sa[col_c] = ind
                sa_cell_cols.append(col_c)
                sa_cell_meta.append((col_c, int(c_yr), int(ell), cnt))

    sa_res = fit_ols_cr1_wcb(
        sw15_sa,
        "log_potaff",
        sa_cell_cols,
        ["mfg", "rec_year", "comp_fe"],
        "mfg",
        target_vars=[sa_cell_cols[0]],
        n_boot=19,
    )
    sa_iw_summary: dict = {"skipped": True}
    if not sa_res.get("skipped"):
        t_crit_sa = float(stats.t.ppf(0.975, df=sa_res["G_clusters"] - 1))
        iw_dynamic: dict[str, dict] = {}
        for ell in [-3, -2, 0, 1, 2, 3]:
            cells = [(c, cnt) for c, _, e_l, cnt in sa_cell_meta if e_l == ell]
            w_l = np.array([cnt for _, cnt in cells], dtype=np.float64)
            w_l = w_l / w_l.sum()
            idxs_l = [sa_res["_name_to_idx"][c] for c, _ in cells]
            est_l = float(w_l @ sa_res["_beta"][idxs_l])
            se_l = float(np.sqrt(max(float(w_l @ sa_res["_V_cr1"][np.ix_(idxs_l, idxs_l)] @ w_l), 1e-24)))
            t_l = est_l / se_l
            p_l = float(2.0 * stats.t.sf(abs(t_l), df=sa_res["G_clusters"] - 1))
            lbl_l = f"ev_m{abs(ell)}" if ell < 0 else f"ev_p{ell}"
            iw_dynamic[lbl_l] = {
                "ell": ell,
                "n_cohorts": len(cells),
                "coef": round(est_l, 4),
                "se_cr1": round(se_l, 4),
                "t_cr1": round(t_l, 3),
                "p_t_G1": round(p_l, 6),
                "ci95_lo": round(est_l - t_crit_sa * se_l, 4),
                "ci95_hi": round(est_l + t_crit_sa * se_l, 4),
            }

        # Pooled post-adoption IW (observation-weighted across all post cohort x relative-time cells)
        post_cells = [(c, cnt) for c, _, e_l, cnt in sa_cell_meta if e_l >= 0]
        w_p = np.array([cnt for _, cnt in post_cells], dtype=np.float64)
        w_p = w_p / w_p.sum()
        idxs_p = [sa_res["_name_to_idx"][c] for c, _ in post_cells]
        iw_est = float(w_p @ sa_res["_beta"][idxs_p])
        iw_se = float(np.sqrt(max(float(w_p @ sa_res["_V_cr1"][np.ix_(idxs_p, idxs_p)] @ w_p), 1e-24)))
        iw_t = iw_est / iw_se
        iw_p = float(2.0 * stats.t.sf(abs(iw_t), df=sa_res["G_clusters"] - 1))

        # Joint pre-trend Wald test F(2, G-1) on IW leads ell = -3 and ell = -2
        k_sa = len(sa_res["_beta"])
        L_pre = np.zeros((2, k_sa), dtype=np.float64)
        for ri, ell in enumerate([-3, -2]):
            cells = [(c, cnt) for c, _, e_l, cnt in sa_cell_meta if e_l == ell]
            tot_c = float(sum(cnt for _, cnt in cells))
            for c, cnt in cells:
                L_pre[ri, sa_res["_name_to_idx"][c]] = cnt / tot_c
        Lb = L_pre @ sa_res["_beta"]
        LV = L_pre @ sa_res["_V_cr1"] @ L_pre.T
        F_pre = float(Lb.T @ np.linalg.inv(LV) @ Lb) / 2.0
        p_pre = float(stats.f.sf(F_pre, 2, sa_res["G_clusters"] - 1))

        sa_iw_summary = {
            "skipped": False,
            "full_rank_verified": sa_res["full_rank_verified"],
            "n": sa_res["n"],
            "k": sa_res["k"],
            "G_clusters": sa_res["G_clusters"],
            "n_cohorts": len(cohorts),
            "cohorts": [int(c) for c in cohorts],
            "n_cohort_period_cells": len(sa_cell_cols),
            "n_post_cells": len(post_cells),
            "excluded_partial_cohort": 2026,
            "iw_pre_trend_wald_m3_m2": {
                "q": 2,
                "F_stat": round(F_pre, 3),
                "df2": int(sa_res["G_clusters"] - 1),
                "p_value": round(p_pre, 5),
            },
            "iw_dynamic_terms": iw_dynamic,
            "iw_post_coef": round(iw_est, 4),
            "iw_se_cr1": round(iw_se, 4),
            "iw_t": round(iw_t, 3),
            "iw_p_t_G1": round(iw_p, 6),
        }

    # (3) Within-OEM Modern SDV Model-Year Cohort Shift (Unconditional Software Recalls, 2015-2026)
    # Compares MY >= 2021 vs MY <= 2019 (and cohort bins) holding OEM + Recall-Year + Component FE fixed!
    sw_coh = sw15[sw15["min_my"].between(2012, 2026)].copy()
    sw_coh["coh_2018_19"] = sw_coh["min_my"].between(2018, 2019).astype(float)
    sw_coh["coh_2020_21"] = sw_coh["min_my"].between(2020, 2021).astype(float)
    sw_coh["coh_2022_23"] = sw_coh["min_my"].between(2022, 2023).astype(float)
    sw_coh["coh_2024_26"] = sw_coh["min_my"].between(2024, 2026).astype(float)
    sw_coh["is_sdv_my2021p"] = (sw_coh["min_my"] >= 2021).astype(float)

    sdv_cohort_bins = strip_private(
        fit_ols_cr1_wcb(
            sw_coh,
            "log_potaff",
            ["coh_2018_19", "coh_2020_21", "coh_2022_23", "coh_2024_26"],
            ["mfg", "rec_year", "comp_fe"],
            "mfg",
        )
    )
    sdv_cohort_2021p_vs_pre20 = strip_private(
        fit_ols_cr1_wcb(
            sw_coh[sw_coh["min_my"] != 2020],
            "log_potaff",
            ["is_sdv_my2021p"],
            ["mfg", "rec_year", "comp_fe"],
            "mfg",
        )
    )
    # Also check same MY >= 2021 shift on PHYSICAL HARDWARE recalls as a placebo / fleet-age benchmark!
    phys15 = add_common_fe_helpers(
        df_all[(df_all["rec_year"].between(2015, 2026)) & (df_all["modality4"] == "Physical_Hardware") & (df_all["min_my"].between(2012, 2026))].copy()
    )
    phys15["is_sdv_my2021p"] = (phys15["min_my"] >= 2021).astype(float)
    phys_placebo_cohort = strip_private(
        fit_ols_cr1_wcb(
            phys15[phys15["min_my"] != 2020],
            "log_potaff",
            ["is_sdv_my2021p"],
            ["mfg", "rec_year", "comp_fe"],
            "mfg",
        )
    )

    # Also check formal Difference-in-Differences (Software x Modern SDV MY>=2021 vs Physical Hardware)
    all15 = add_common_fe_helpers(
        df_all[(df_all["rec_year"].between(2015, 2026)) & (df_all["min_my"].between(2012, 2026)) & (df_all["min_my"] != 2020)].copy()
    )
    all15["is_sdv_my2021p"] = (all15["min_my"] >= 2021).astype(float)
    all15["sw_x_sdv_my2021p"] = all15["is_sw_any"] * all15["is_sdv_my2021p"]
    sw_vs_phys_sdv_did = strip_private(
        fit_ols_cr1_wcb(
            all15,
            "log_potaff",
            ["is_sw_any", "is_sdv_my2021p", "sw_x_sdv_my2021p"],
            ["mfg", "rec_year", "comp_fe"],
            "mfg",
        )
    )

    # Formal Wald test H0: beta(Pure_OTA) == beta(Hybrid_OTA) in main SW blast-radius regression
    p1_raw_4way = fit_ols_cr1_wcb(
        sw_ota_oems, "log_potaff", ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg", n_boot=99
    )
    idx_p = p1_raw_4way["_name_to_idx"]["is_ota_pure"]
    idx_h = p1_raw_4way["_name_to_idx"]["is_ota_hybrid"]
    diff_ph = float(p1_raw_4way["_beta"][idx_h] - p1_raw_4way["_beta"][idx_p])
    c_vec = np.array([-1.0, 1.0])
    V_ph = p1_raw_4way["_V_cr1"][np.ix_([idx_p, idx_h], [idx_p, idx_h])]
    se_ph = float(np.sqrt(max(float(c_vec @ V_ph @ c_vec), 1e-24)))
    t_ph = diff_ph / se_ph
    p_ph = float(2.0 * stats.t.sf(abs(t_ph), df=p1_raw_4way["G_clusters"] - 1))
    hybrid_minus_pure_blast = {
        "diff_hybrid_minus_pure": round(diff_ph, 4),
        "se_cr1": round(se_ph, 4),
        "t_cr1": round(t_ph, 3),
        "p_t_G1": round(p_ph, 6),
    }

    # (4) Transparent reporting of distinct conditional vs. unconditional estimands
    # (No invalid percentage-share subtraction across distinct estimands or zero-clipping of negative ITT!)
    cond_any_beta = p1_main["sw_ota_oems_anyota_log_potaff"]["terms"]["is_ota_audited"]["coef"]
    cond_hyb_beta = p1_main["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_hybrid"]["coef"]
    cond_pure_beta = p1_main["sw_ota_oems_4way_log_potaff"]["terms"]["is_ota_pure"]["coef"]
    itt_beta = itt_did_pooled["terms"]["post_ota_adopt"]["coef"]

    return {
        "main_sw_ota_oems": p1_main,
        "hybrid_minus_pure_blast_wald": hybrid_minus_pure_blast,
        "all_vehicles_benchmark": p1_allveh,
        "robustness_ladder": p1_robust,
        "fleet_size_distributions": dist_tbl,
        "itt_staggered_adoption": {
            "event_study": strip_private(itt_es_raw),
            "pre_trend_wald_m3_m2": itt_pre_wald,
            "post_joint_wald_p0_p3": itt_post_wald,
            "pooled_did": itt_did_pooled,
            "pooled_did_with_myfe": itt_did_with_myfe,
            "pooled_did_n_models": itt_did_nmodels,
            "pooled_did_excl_tesla": itt_did_excl_tesla,
            "sun_abraham_iw": sa_iw_summary,
        },
        "unconditional_sdv_cohort_shift": {
            "sw_cohort_bins_vs_pre2018": sdv_cohort_bins,
            "sw_my2021plus_vs_pre2020": sdv_cohort_2021p_vs_pre20,
            "physical_hardware_placebo_my2021plus": phys_placebo_cohort,
            "sw_vs_physical_sdv_did": sw_vs_phys_sdv_did,
        },
        "conditional_vs_unconditional_estimands": {
            "conditional_ota_vs_dealersw_log_potaff": cond_any_beta,
            "conditional_hybrid_vs_dealersw_log_potaff": cond_hyb_beta,
            "conditional_pure_vs_dealersw_log_potaff": cond_pure_beta,
            "unconditional_twfe_itt_log_potaff": itt_beta,
            "unconditional_sun_abraham_iw_log_potaff": sa_iw_summary.get("iw_post_coef"),
            "unconditional_sun_abraham_iw_p_t": sa_iw_summary.get("iw_p_t_G1"),
            "unconditional_sw_vs_phys_sdv_cohort_did": sw_vs_phys_sdv_did["terms"]["sw_x_sdv_my2021p"]["coef"],
            "estimand_note": (
                "Conditional within-OEM modality differentials and unconditional OEM-level first-OTA ITT "
                "estimates measure distinct estimands; no percentage selection-share decomposition is computed."
            ),
        },
    }


def run_pillar2_remediation_velocity(df_all: pd.DataFrame) -> dict:
    """Pillar 2: Frictionless Remediation Velocity (DOT 6axg-epim completion_rate)."""
    c18 = add_common_fe_helpers(df_all[df_all["rec_year"].between(2018, 2026)].copy())
    c18_cr = c18[c18["completion_rate"].notna()].copy()
    mat = c18_cr[c18_cr["is_mature_18m"] == 1].copy()
    mat12 = c18_cr[c18_cr["is_mature_12m"] == 1].copy()

    ota_oems = set(c18[c18["is_ota_audited"] == 1]["mfg"].unique())
    mat_sw = mat[(mat["mfg"].isin(ota_oems)) & (mat["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]))].copy()
    mat_sw_all_oems = mat[mat["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])].copy()
    full_sw = c18_cr[(c18_cr["mfg"].isin(ota_oems)) & (c18_cr["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]))].copy()

    # 2A. Primary Mature (>= 18m) Completion-Rate Regressions
    p2_mature = {
        "sw_ota_oems_4way": strip_private(
            fit_ols_cr1_wcb(mat_sw, "completion_rate", ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
        ),
        "sw_ota_oems_anyota": strip_private(
            fit_ols_cr1_wcb(mat_sw, "completion_rate", ["is_ota_audited"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
        ),
        "sw_ota_oems_api_ota": strip_private(
            fit_ols_cr1_wcb(mat_sw, "completion_rate", ["is_ota_api_full"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
        ),
        "sw_ota_oems_4way_ctrl_potaff": strip_private(
            fit_ols_cr1_wcb(
                mat_sw,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "log_potaff"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                target_vars=["is_ota_pure", "is_ota_hybrid", "log_potaff"],
            )
        ),
        "sw_all_oems_4way": strip_private(
            fit_ols_cr1_wcb(mat_sw_all_oems, "completion_rate", ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
        ),
        "all_vehicles_4way_vs_phys": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "all_vehicles_api_vs_phys": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "completion_rate",
                ["is_ota_api_full", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "strict_drop_cr_gt100_all_veh": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "completion_rate_strict",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "mature_12m_sw_4way": strip_private(
            fit_ols_cr1_wcb(
                mat12[(mat12["mfg"].isin(ota_oems)) & (mat12["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]))],
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "excl_tesla_sw_4way": strip_private(
            fit_ols_cr1_wcb(
                mat_sw[mat_sw["is_tesla"] == 0],
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "excl_tesla_ford_sw_4way": strip_private(
            fit_ols_cr1_wcb(
                mat_sw[~mat_sw["mfg"].isin(["Tesla, Inc.", "Ford Motor Company"])],
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "oem_x_year_fe_sw_4way": strip_private(
            fit_ols_cr1_wcb(mat_sw, "completion_rate", ["is_ota_pure", "is_ota_hybrid"], ["mfg_yr", "min_my_fe", "comp_fe"], "mfg")
        ),
        "hybrid_swchoice_vs_hwmixed_sw": strip_private(
            fit_ols_cr1_wcb(
                mat_sw,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid_swchoice", "is_ota_hybrid_hwmixed"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "light_duty_passenger_sw_4way": strip_private(
            fit_ols_cr1_wcb(
                mat_sw[mat_sw["is_light_duty_passenger"] == 1],
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "singleton_dropped_sw_4way": strip_private(
            fit_ols_cr1_wcb(
                mat_sw,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                drop_singletons=True,
            )
        ),
        "singleton_dropped_all_veh_4way": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                drop_singletons=True,
            )
        ),
    }

    # 2B. Full-Sample Age-Controlled (2018-2026) with cubic age spline + quarter FE
    p2_full_age = {
        "sw_ota_oems_4way_agepoly": strip_private(
            fit_ols_cr1_wcb(
                full_sw,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "age_yr", "age_yr2", "age_yr3"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                target_vars=["is_ota_pure", "is_ota_hybrid"],
            )
        ),
        "all_vehicles_4way_agepoly": strip_private(
            fit_ols_cr1_wcb(
                c18_cr,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw", "age_yr", "age_yr2", "age_yr3"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                target_vars=["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"],
            )
        ),
    }

    # 2C. Campaign-Age Maturation Curve (0-3m, 3-6m, 6-12m, 12-18m, 18-24m, >24m)
    age_bins_order = ["0-3m", "3-6m", "6-12m", "12-18m", "18-24m", ">24m"]
    maturation_curve = []
    for ab in age_bins_order:
        row_d: dict = {"age_bin": ab}
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
            s = c18_cr[(c18_cr["age_bin"] == ab) & (c18_cr["modality4"] == mod)]["completion_rate"]
            row_d[mod] = {
                "n": len(s),
                "mean": round(float(s.mean()), 2) if len(s) else None,
                "median": round(float(s.median()), 2) if len(s) else None,
                "p25": round(float(np.percentile(s, 25)), 2) if len(s) >= 2 else None,
                "p75": round(float(np.percentile(s, 75)), 2) if len(s) >= 2 else None,
            }
        # Also Official API OTA
        s_api = c18_cr[(c18_cr["age_bin"] == ab) & (c18_cr["is_ota_api_full"] == 1)]["completion_rate"]
        row_d["API_OTA"] = {
            "n": len(s_api),
            "mean": round(float(s_api.mean()), 2) if len(s_api) else None,
            "median": round(float(s_api.median()), 2) if len(s_api) else None,
        }
        maturation_curve.append(row_d)

    # 2D. OTA x Vehicle-Age Compliance-Decay Mitigation (Mature >= 18m)
    mat_age = mat.dropna(subset=["vehicle_age_years"]).copy()
    mat_age["veh_age"] = mat_age["vehicle_age_years"].clip(lower=0, upper=15)
    mat_age["ota_any_x_age"] = mat_age["is_ota_audited"] * mat_age["veh_age"]
    mat_age["api_ota_x_age"] = mat_age["is_ota_api_full"] * mat_age["veh_age"]
    mat_age["pure_x_age"] = mat_age["is_ota_pure"] * mat_age["veh_age"]
    mat_age["hybrid_x_age"] = mat_age["is_ota_hybrid"] * mat_age["veh_age"]
    mat_age["dealer_sw_x_age"] = mat_age["is_dealer_sw"] * mat_age["veh_age"]

    mat_sw_age = mat_age[
        (mat_age["mfg"].isin(ota_oems)) & (mat_age["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]))
    ].copy()

    # Descriptive binned vehicle age decay across modalities (0-1y, 2-3y, 4-5y, 6+y)
    mat_age["veh_age_bin"] = pd.cut(
        mat_age["veh_age"], bins=[-0.5, 1.5, 3.5, 5.5, 20.0], labels=["0-1 yr", "2-3 yr", "4-5 yr", "6+ yr"]
    ).astype(str)
    veh_age_profile = []
    for vb in ["0-1 yr", "2-3 yr", "4-5 yr", "6+ yr"]:
        rd: dict = {"veh_age_bin": vb}
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
            s = mat_age[(mat_age["veh_age_bin"] == vb) & (mat_age["modality4"] == mod)]["completion_rate"]
            rd[mod] = {
                "n": len(s),
                "mean": round(float(s.mean()), 2) if len(s) else None,
                "median": round(float(s.median()), 2) if len(s) else None,
            }
        veh_age_profile.append(rd)

    age_decay_regs = {
        "sw_ota_oems_anyota_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age,
                "completion_rate",
                ["is_ota_audited", "veh_age", "ota_any_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "sw_ota_oems_4way_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "veh_age", "pure_x_age", "hybrid_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "sw_ota_oems_api_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age,
                "completion_rate",
                ["is_ota_api_full", "veh_age", "api_ota_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "sw_excl_tesla_anyota_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age[mat_sw_age["is_tesla"] == 0],
                "completion_rate",
                ["is_ota_audited", "veh_age", "ota_any_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "sw_excl_tesla_4way_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age[mat_sw_age["is_tesla"] == 0],
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "veh_age", "pure_x_age", "hybrid_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "sw_excl_tesla_api_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age[mat_sw_age["is_tesla"] == 0],
                "completion_rate",
                ["is_ota_api_full", "veh_age", "api_ota_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "sw_light_duty_4way_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age[mat_sw_age["is_light_duty_passenger"] == 1],
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "veh_age", "pure_x_age", "hybrid_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "sw_light_duty_api_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_sw_age[mat_sw_age["is_light_duty_passenger"] == 1],
                "completion_rate",
                ["is_ota_api_full", "veh_age", "api_ota_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
        "all_vehicles_4way_x_age": strip_private(
            fit_ols_cr1_wcb(
                mat_age,
                "completion_rate",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw", "veh_age", "pure_x_age", "hybrid_x_age", "dealer_sw_x_age"],
                ["mfg", "rec_quarter", "comp_fe"],
                "mfg",
            )
        ),
    }

    # 2E. Tesla vs Non-Tesla Pure-OTA vs Legacy Hybrid-OTA Execution Gap (Mature >= 18m)
    mat["exec_tier"] = np.where(
        (mat["modality4"] == "Pure_OTA") & (mat["is_tesla"] == 1),
        "Tesla_Pure_OTA",
        np.where(
            (mat["modality4"] == "Pure_OTA") & (mat["is_tesla"] == 0),
            "NonTesla_Pure_OTA",
            np.where(
                mat["modality4"] == "Hybrid_OTA",
                "Legacy_Hybrid_OTA",
                np.where(mat["modality4"] == "Dealer_Software", "Dealer_Software", "Physical_Hardware"),
            ),
        ),
    )
    exec_tiers = {}
    for tier in ["Tesla_Pure_OTA", "NonTesla_Pure_OTA", "Legacy_Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
        sub = mat[mat["exec_tier"] == tier]
        tot_pa = float(sub["potaff"].sum())
        tot_unrem = float(sub["unremedied_vehicles"].sum())
        exec_tiers[tier] = {
            "n": len(sub),
            "median_potaff": round(float(sub["potaff"].median()), 1) if len(sub) else None,
            "mean_potaff": round(float(sub["potaff"].mean()), 1) if len(sub) else None,
            "total_potaff": round(tot_pa),
            "mean_cr": round(float(sub["completion_rate"].mean()), 2) if len(sub) else None,
            "median_cr": round(float(sub["completion_rate"].median()), 2) if len(sub) else None,
            "fleet_weighted_cr": round(100.0 * (1.0 - tot_unrem / tot_pa), 2) if tot_pa > 0 else None,
            "total_unremedied": round(tot_unrem),
            "median_unremedied": round(float(sub["unremedied_vehicles"].median()), 1) if len(sub) else None,
            "mean_log_unremedied": round(float(sub["log_unremedied"].mean()), 3) if len(sub) else None,
        }

    # Formal regression contrasting Tesla Pure-OTA vs Non-Tesla Pure-OTA vs Legacy Hybrid-OTA vs Dealer-SW (no OEM FE since Tesla is an OEM, using Quarter + Min-MY + Comp FE)
    mat_sw_tier = mat[mat["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])].copy()
    mat_sw_tier["is_tesla_pure"] = (mat_sw_tier["exec_tier"] == "Tesla_Pure_OTA").astype(float)
    mat_sw_tier["is_nontesla_pure"] = (mat_sw_tier["exec_tier"] == "NonTesla_Pure_OTA").astype(float)
    mat_sw_tier["is_legacy_hybrid"] = (mat_sw_tier["exec_tier"] == "Legacy_Hybrid_OTA").astype(float)
    tier_reg_cr = strip_private(
        fit_ols_cr1_wcb(
            mat_sw_tier,
            "completion_rate",
            ["is_tesla_pure", "is_nontesla_pure", "is_legacy_hybrid"],
            ["rec_quarter", "min_my_fe", "comp_fe"],
            "mfg",
        )
    )
    tier_reg_cr_ld = strip_private(
        fit_ols_cr1_wcb(
            mat_sw_tier[mat_sw_tier["is_light_duty_passenger"] == 1],
            "completion_rate",
            ["is_tesla_pure", "is_nontesla_pure", "is_legacy_hybrid"],
            ["rec_quarter", "min_my_fe", "comp_fe"],
            "mfg",
        )
    )
    # Also formal test of Pure-OTA vs Hybrid-OTA directly (restricting strictly to mature OTA campaigns!)
    mat_ota_only = mat[mat["modality4"].isin(["Pure_OTA", "Hybrid_OTA"])].copy()
    pure_vs_hybrid_cr = strip_private(
        fit_ols_cr1_wcb(
            mat_ota_only,
            "completion_rate",
            ["is_ota_pure"],
            ["rec_year", "comp_fe"],
            "mfg",
        )
    )

    return {
        "mature_18m_regressions": p2_mature,
        "full_sample_age_controlled": p2_full_age,
        "maturation_curve": maturation_curve,
        "vehicle_age_decay": {
            "descriptive_bins": veh_age_profile,
            "regressions": age_decay_regs,
        },
        "tesla_vs_legacy_execution_gap": {
            "descriptive_tiers": exec_tiers,
            "tier_reg_completion_rate_no_oem_fe": tier_reg_cr,
            "tier_reg_completion_rate_light_duty": tier_reg_cr_ld,
            "pure_vs_hybrid_ota_only_cr": pure_vs_hybrid_cr,
        },
    }


def run_pillar3_net_unremedied_exposure(df_all: pd.DataFrame) -> dict:
    """Pillar 3: Net Unremedied Fleet Exposure, Public-Safety Inversion, and Break-Even Frontier."""
    c18 = add_common_fe_helpers(df_all[df_all["rec_year"].between(2018, 2026)].copy())
    c18_u = c18[c18["log_unremedied"].notna()].copy()
    mat = c18_u[c18_u["is_mature_18m"] == 1].copy()

    ota_oems = set(c18[c18["is_ota_audited"] == 1]["mfg"].unique())
    mat_sw = mat[(mat["mfg"].isin(ota_oems)) & (mat["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]))].copy()
    full_sw = c18_u[(c18_u["mfg"].isin(ota_oems)) & (c18_u["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]))].copy()

    # 3A. Net Unremedied Regressions: log(1 + unremedied_vehicles)
    p3_regs = {
        # Primary mature >= 18m (Unconditional on fleet size -> NET effect of blast radius + velocity!)
        "mature_sw_ota_oems_4way": strip_private(
            fit_ols_cr1_wcb(mat_sw, "log_unremedied", ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
        ),
        "mature_sw_ota_oems_anyota": strip_private(
            fit_ols_cr1_wcb(mat_sw, "log_unremedied", ["is_ota_audited"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
        ),
        "mature_sw_ota_oems_api_ota": strip_private(
            fit_ols_cr1_wcb(mat_sw, "log_unremedied", ["is_ota_api_full"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
        ),
        # Controlling for log_potaff -> isolates pure remediation-velocity residual compression holding fleet size constant!
        "mature_sw_ota_oems_4way_ctrl_potaff": strip_private(
            fit_ols_cr1_wcb(
                mat_sw,
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid", "log_potaff"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                target_vars=["is_ota_pure", "is_ota_hybrid", "log_potaff"],
            )
        ),
        "mature_sw_excl_tesla_4way": strip_private(
            fit_ols_cr1_wcb(
                mat_sw[mat_sw["is_tesla"] == 0],
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "mature_sw_excl_tesla_ford_4way": strip_private(
            fit_ols_cr1_wcb(
                mat_sw[~mat_sw["mfg"].isin(["Tesla, Inc.", "Ford Motor Company"])],
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "mature_all_vehicles_4way_vs_phys": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "mature_all_vehicles_api_vs_phys": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "log_unremedied",
                ["is_ota_api_full", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "mature_strict_drop_cr_gt100": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "log_unremedied_strict",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "full_agepoly_sw_ota_oems_4way": strip_private(
            fit_ols_cr1_wcb(
                full_sw,
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid", "age_yr", "age_yr2", "age_yr3"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                target_vars=["is_ota_pure", "is_ota_hybrid"],
            )
        ),
        "mature_sw_oem_x_year_fe_4way": strip_private(
            fit_ols_cr1_wcb(mat_sw, "log_unremedied", ["is_ota_pure", "is_ota_hybrid"], ["mfg_yr", "min_my_fe", "comp_fe"], "mfg")
        ),
        "mature_sw_hybrid_swchoice_vs_hwmixed": strip_private(
            fit_ols_cr1_wcb(
                mat_sw,
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid_swchoice", "is_ota_hybrid_hwmixed"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "mature_all_vehicles_hybrid_swchoice_vs_hwmixed": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid_swchoice", "is_ota_hybrid_hwmixed", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
            )
        ),
        "mature_sw_singleton_dropped_4way": strip_private(
            fit_ols_cr1_wcb(
                mat_sw,
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                drop_singletons=True,
            )
        ),
        "mature_all_vehicles_singleton_dropped_4way": strip_private(
            fit_ols_cr1_wcb(
                mat,
                "log_unremedied",
                ["is_ota_pure", "is_ota_hybrid", "is_dealer_sw"],
                ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
                "mfg",
                drop_singletons=True,
            )
        ),
    }

    # Tier regression (no OEM FE so Tesla Pure-OTA can be directly compared to Non-Tesla Pure-OTA & Legacy Hybrid-OTA!)
    mat_sw_all = mat[mat["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])].copy()
    mat_sw_all["is_tesla_pure"] = ((mat_sw_all["modality4"] == "Pure_OTA") & (mat_sw_all["is_tesla"] == 1)).astype(float)
    mat_sw_all["is_nontesla_pure"] = ((mat_sw_all["modality4"] == "Pure_OTA") & (mat_sw_all["is_tesla"] == 0)).astype(float)
    mat_sw_all["is_legacy_hybrid"] = (mat_sw_all["modality4"] == "Hybrid_OTA").astype(float)
    p3_regs["mature_sw_tiers_no_oem_fe"] = strip_private(
        fit_ols_cr1_wcb(
            mat_sw_all,
            "log_unremedied",
            ["is_tesla_pure", "is_nontesla_pure", "is_legacy_hybrid"],
            ["rec_quarter", "min_my_fe", "comp_fe"],
            "mfg",
        )
    )
    p3_regs["mature_sw_tiers_light_duty"] = strip_private(
        fit_ols_cr1_wcb(
            mat_sw_all[mat_sw_all["is_light_duty_passenger"] == 1],
            "log_unremedied",
            ["is_tesla_pure", "is_nontesla_pure", "is_legacy_hybrid"],
            ["rec_quarter", "min_my_fe", "comp_fe"],
            "mfg",
        )
    )

    # 3B. Aggregate Fleet Accounting (Mature >= 18m)
    tot_all_aff = float(mat["potaff"].sum())
    tot_all_unrem = float(mat["unremedied_vehicles"].sum())

    def _agg_row(sub: pd.DataFrame) -> dict:
        aff = float(sub["potaff"].sum())
        unrem = float(sub["unremedied_vehicles"].sum())
        return {
            "n_campaigns": len(sub),
            "total_affected": round(aff),
            "share_total_affected_pct": round(100.0 * aff / tot_all_aff, 3),
            "total_unremedied": round(unrem),
            "share_total_unremedied_pct": round(100.0 * unrem / tot_all_unrem, 3),
            "unremedied_rate_fleet_weighted_pct": round(100.0 * unrem / aff, 3) if aff > 0 else None,
            "completion_rate_fleet_weighted_pct": round(100.0 * (1.0 - unrem / aff), 3) if aff > 0 else None,
            "mean_cr_pct": round(float(sub["completion_rate"].mean()), 2) if len(sub) else None,
            "median_affected": round(float(sub["potaff"].median()), 1) if len(sub) else None,
            "median_unremedied": round(float(sub["unremedied_vehicles"].median()), 1) if len(sub) else None,
            "mean_log_unremedied": round(float(sub["log_unremedied"].mean()), 3) if len(sub) else None,
        }

    agg_accounting = {}
    for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
        agg_accounting[mod] = _agg_row(mat[mat["modality4"] == mod])
    # Supplementary non-additive reference slices
    agg_accounting["Official_API_OTA"] = _agg_row(mat[mat["is_ota_api_full"] == 1])
    agg_accounting["Hybrid_SW_Choice"] = _agg_row(mat[mat["is_ota_hybrid_swchoice"] == 1])
    agg_accounting["Hybrid_HW_Mixed"] = _agg_row(mat[mat["is_ota_hybrid_hwmixed"] == 1])
    agg_accounting["OTA_OEMs_Dealer_Software"] = _agg_row(mat_sw[mat_sw["modality4"] == "Dealer_Software"])

    # 3B-2. Explicit Mature OTA Sample Composition & OEM Vehicle-Recall Weight Disclosure
    # Confirms exact Tesla 98.7% share of mature Pure-OTA affected vehicle-recall instances and Non-Tesla subsamples.
    def _oem_composition(sub: pd.DataFrame) -> list[dict]:
        tot_n = len(sub)
        tot_pa = float(sub["potaff"].sum())
        tot_un = float(sub["unremedied_vehicles"].sum())
        rows = []
        for oem_name, grp in sub.groupby("mfg"):
            pa = float(grp["potaff"].sum())
            un = float(grp["unremedied_vehicles"].sum())
            vage = grp["vehicle_age_years"].dropna()
            rows.append(
                {
                    "oem": str(oem_name),
                    "is_light_duty_passenger": int(grp["is_light_duty_passenger"].iloc[0]),
                    "n_campaigns": len(grp),
                    "share_campaigns_pct": round(100.0 * len(grp) / max(1, tot_n), 2),
                    "affected_vehicle_instances": round(pa),
                    "share_affected_pct": round(100.0 * pa / max(1.0, tot_pa), 3),
                    "unremedied_instance_proxy": round(un),
                    "share_unremedied_pct": round(100.0 * un / max(1.0, tot_un), 3),
                    "mean_cr_pct": round(float(grp["completion_rate"].mean()), 2),
                    "median_cr_pct": round(float(grp["completion_rate"].median()), 2),
                    "fleet_weighted_cr_pct": round(100.0 * (1.0 - un / pa), 2) if pa > 0 else None,
                    "median_affected": round(float(grp["potaff"].median()), 1),
                    "median_unremedied_proxy": round(float(grp["unremedied_vehicles"].median()), 1),
                    "max_vehicle_age_yr": round(float(vage.max()), 1) if len(vage) else None,
                    "n_age_6plus_yr": int((vage >= 6).sum()),
                }
            )
        return sorted(rows, key=lambda r: r["affected_vehicle_instances"], reverse=True)

    mat_pure = mat[mat["modality4"] == "Pure_OTA"].copy()
    mat_hyb = mat[mat["modality4"] == "Hybrid_OTA"].copy()
    pure_tot_pa = float(mat_pure["potaff"].sum())
    pure_tot_un = float(mat_pure["unremedied_vehicles"].sum())

    def _pure_slice_stats(sub: pd.DataFrame) -> dict:
        pa = float(sub["potaff"].sum())
        un = float(sub["unremedied_vehicles"].sum())
        vage = sub["vehicle_age_years"].dropna()
        return {
            "n_campaigns": len(sub),
            "n_oems": int(sub["mfg"].nunique()),
            "share_pure_campaigns_pct": round(100.0 * len(sub) / max(1, len(mat_pure)), 2),
            "affected_vehicle_instances": round(pa),
            "share_pure_affected_pct": round(100.0 * pa / max(1.0, pure_tot_pa), 2),
            "unremedied_instance_proxy": round(un),
            "share_pure_unremedied_pct": round(100.0 * un / max(1.0, pure_tot_un), 2),
            "mean_cr_pct": round(float(sub["completion_rate"].mean()), 2),
            "median_cr_pct": round(float(sub["completion_rate"].median()), 2),
            "fleet_weighted_cr_pct": round(100.0 * (1.0 - un / pa), 2) if pa > 0 else None,
            "median_affected": round(float(sub["potaff"].median()), 1),
            "median_unremedied_proxy": round(float(sub["unremedied_vehicles"].median()), 1),
            "max_vehicle_age_yr": round(float(vage.max()), 1) if len(vage) else None,
            "n_age_6plus_yr": int((vage >= 6).sum()),
        }

    mature_sample_composition = {
        "pure_ota_total_n": len(mat_pure),
        "pure_ota_n_oems": int(mat_pure["mfg"].nunique()),
        "pure_ota_tesla_subsample": _pure_slice_stats(mat_pure[mat_pure["is_tesla"] == 1]),
        "pure_ota_nontesla_subsample": _pure_slice_stats(mat_pure[mat_pure["is_tesla"] == 0]),
        "pure_ota_nontesla_light_duty_subsample": _pure_slice_stats(
            mat_pure[(mat_pure["is_tesla"] == 0) & (mat_pure["is_light_duty_passenger"] == 1)]
        ),
        "pure_ota_by_oem": _oem_composition(mat_pure),
        "hybrid_ota_total_n": len(mat_hyb),
        "hybrid_ota_n_oems": int(mat_hyb["mfg"].nunique()),
        "hybrid_ota_by_oem": _oem_composition(mat_hyb),
    }

    # 3C. Sample-Matched Break-Even Completion-Rate Frontier Analysis
    # Given Dealer-SW baseline completion rate r0 and blast-radius multiplier M = potaff_OTA / potaff_DealerSW,
    # break-even completion rate r*(M) = 1 - (1 - r0) / M
    dsw_ota_sub = mat_sw[mat_sw["modality4"] == "Dealer_Software"]
    dsw_all_sub = mat[mat["modality4"] == "Dealer_Software"]
    r0_ota_oems = float(dsw_ota_sub["completion_rate"].mean()) / 100.0
    r0_unw = float(dsw_all_sub["completion_rate"].mean()) / 100.0
    r0_fw = agg_accounting["Dealer_Software"]["completion_rate_fleet_weighted_pct"] / 100.0
    r0_med = float(dsw_all_sub["completion_rate"].median()) / 100.0
    dsw_ota_med_pa = float(dsw_ota_sub["potaff"].median())
    dsw_med_pa = float(dsw_all_sub["potaff"].median())

    # Within-OEM mature blast-radius multipliers on the exact mat_sw sample
    br_mat = strip_private(
        fit_ols_cr1_wcb(mat_sw, "log_potaff", ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
    )
    br_mat_split = strip_private(
        fit_ols_cr1_wcb(
            mat_sw,
            "log_potaff",
            ["is_ota_pure", "is_ota_hybrid_swchoice", "is_ota_hybrid_hwmixed"],
            ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
            "mfg",
        )
    )
    cr_mat_fe = strip_private(
        fit_ols_cr1_wcb(mat_sw, "completion_rate", ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_quarter", "min_my_fe", "comp_fe"], "mfg")
    )
    m_pure_fe = float(np.exp(br_mat["terms"]["is_ota_pure"]["coef"]))
    m_hyb_fe = float(np.exp(br_mat["terms"]["is_ota_hybrid"]["coef"]))
    m_hyb_sw_fe = float(np.exp(br_mat_split["terms"]["is_ota_hybrid_swchoice"]["coef"]))

    def breakeven(M: float, r0: float) -> float:
        return round(100.0 * (1.0 - (1.0 - r0) / max(M, 1e-6)), 2)

    tesla_pure = mat[(mat["modality4"] == "Pure_OTA") & (mat["is_tesla"] == 1)]
    nontesla_pure = mat[(mat["modality4"] == "Pure_OTA") & (mat["is_tesla"] == 0)]
    all_pure = mat[mat["modality4"] == "Pure_OTA"]
    all_hyb = mat[mat["modality4"] == "Hybrid_OTA"]
    hyb_sw = mat[mat["is_ota_hybrid_swchoice"] == 1]

    r_pure_obs = float(all_pure["completion_rate"].mean())
    r_hyb_obs = float(all_hyb["completion_rate"].mean())
    r_hyb_sw_obs = float(hyb_sw["completion_rate"].mean())
    r_hyb_fe_implied = 100.0 * r0_ota_oems + float(cr_mat_fe["terms"]["is_ota_hybrid"]["coef"])

    frontier_points = {
        "baseline_dealer_sw": {
            "r0_ota_oems_unweighted_pct": round(100.0 * r0_ota_oems, 2),
            "r0_all_oems_unweighted_pct": round(100.0 * r0_unw, 2),
            "r0_fleet_weighted_pct": round(100.0 * r0_fw, 2),
            "r0_median_pct": round(100.0 * r0_med, 2),
            "ota_oems_median_potaff": dsw_ota_med_pa,
            "all_oems_median_potaff": dsw_med_pa,
        },
        # Primary sample-matched within-OTA-OEM frontier (both M_FE and r0_ota_oems from exact same mat_sw sample!)
        "within_ota_oem_matched_frontier": {
            "r0_pct": round(100.0 * r0_ota_oems, 2),
            "pure_ota_M": round(m_pure_fe, 2),
            "pure_ota_breakeven_r_pct": breakeven(m_pure_fe, r0_ota_oems),
            "pure_ota_observed_mean_r_pct": round(r_pure_obs, 2),
            "pure_ota_margin_above_frontier_pp": round(r_pure_obs - breakeven(m_pure_fe, r0_ota_oems), 2),
            "hybrid_ota_M": round(m_hyb_fe, 2),
            "hybrid_ota_breakeven_r_pct": breakeven(m_hyb_fe, r0_ota_oems),
            "hybrid_ota_observed_mean_r_pct": round(r_hyb_obs, 2),
            "hybrid_ota_margin_above_frontier_pp": round(r_hyb_obs - breakeven(m_hyb_fe, r0_ota_oems), 2),
            "hybrid_ota_fe_implied_r_pct": round(r_hyb_fe_implied, 2),
            "hybrid_ota_fe_implied_margin_pp": round(r_hyb_fe_implied - breakeven(m_hyb_fe, r0_ota_oems), 2),
            "hybrid_swchoice_M": round(m_hyb_sw_fe, 2),
            "hybrid_swchoice_breakeven_r_pct": breakeven(m_hyb_sw_fe, r0_ota_oems),
            "hybrid_swchoice_observed_mean_r_pct": round(r_hyb_sw_obs, 2),
            "hybrid_swchoice_margin_above_frontier_pp": round(r_hyb_sw_obs - breakeven(m_hyb_sw_fe, r0_ota_oems), 2),
        },
        # Secondary sensitivity using All-OEM unweighted baseline r0_unw
        "within_oem_fe_multipliers_mature": {
            "r0_all_oems_pct": round(100.0 * r0_unw, 2),
            "pure_ota_M": round(m_pure_fe, 2),
            "pure_ota_breakeven_r_pct": breakeven(m_pure_fe, r0_unw),
            "pure_ota_observed_mean_r_pct": round(r_pure_obs, 2),
            "pure_ota_margin_above_frontier_pp": round(r_pure_obs - breakeven(m_pure_fe, r0_unw), 2),
            "hybrid_ota_M": round(m_hyb_fe, 2),
            "hybrid_ota_breakeven_r_pct": breakeven(m_hyb_fe, r0_unw),
            "hybrid_ota_observed_mean_r_pct": round(r_hyb_obs, 2),
            "hybrid_ota_margin_above_frontier_pp": round(r_hyb_obs - breakeven(m_hyb_fe, r0_unw), 2),
        },
        "raw_median_multiplier_coordinates": {
            "Tesla_Pure_OTA": {
                "M_vs_ota_oems_dsw_median": round(float(tesla_pure["potaff"].median()) / dsw_ota_med_pa, 2),
                "M_vs_all_dsw_median": round(float(tesla_pure["potaff"].median()) / dsw_med_pa, 2),
                "observed_mean_r_pct": round(float(tesla_pure["completion_rate"].mean()), 2),
                "observed_median_r_pct": round(float(tesla_pure["completion_rate"].median()), 2),
                "breakeven_r_pct_ota_oems": breakeven(float(tesla_pure["potaff"].median()) / dsw_ota_med_pa, r0_ota_oems),
            },
            "NonTesla_Pure_OTA": {
                "M_vs_ota_oems_dsw_median": round(float(nontesla_pure["potaff"].median()) / dsw_ota_med_pa, 2),
                "M_vs_all_dsw_median": round(float(nontesla_pure["potaff"].median()) / dsw_med_pa, 2),
                "observed_mean_r_pct": round(float(nontesla_pure["completion_rate"].mean()), 2),
                "observed_median_r_pct": round(float(nontesla_pure["completion_rate"].median()), 2),
                "breakeven_r_pct_ota_oems": breakeven(float(nontesla_pure["potaff"].median()) / dsw_ota_med_pa, r0_ota_oems),
            },
            "All_Pure_OTA": {
                "M_vs_ota_oems_dsw_median": round(float(all_pure["potaff"].median()) / dsw_ota_med_pa, 2),
                "M_vs_all_dsw_median": round(float(all_pure["potaff"].median()) / dsw_med_pa, 2),
                "observed_mean_r_pct": round(r_pure_obs, 2),
                "observed_median_r_pct": round(float(all_pure["completion_rate"].median()), 2),
                "breakeven_r_pct_ota_oems": breakeven(float(all_pure["potaff"].median()) / dsw_ota_med_pa, r0_ota_oems),
            },
            "Legacy_Hybrid_OTA": {
                "M_vs_ota_oems_dsw_median": round(float(all_hyb["potaff"].median()) / dsw_ota_med_pa, 2),
                "M_vs_all_dsw_median": round(float(all_hyb["potaff"].median()) / dsw_med_pa, 2),
                "observed_mean_r_pct": round(r_hyb_obs, 2),
                "observed_median_r_pct": round(float(all_hyb["completion_rate"].median()), 2),
                "breakeven_r_pct_ota_oems": breakeven(float(all_hyb["potaff"].median()) / dsw_ota_med_pa, r0_ota_oems),
            },
        },
    }

    # Formal Wald test + EXACT null-imposed WCB (B=999) for H0: beta(Hybrid_OTA) - beta(Pure_OTA) == 0
    # Reparameterizing [is_ota_audited, is_ota_hybrid, ...] yields exact beta_hybrid - beta_pure on is_ota_hybrid!
    p3_diff_sw = fit_ols_cr1_wcb(
        mat_sw,
        "log_unremedied",
        ["is_ota_audited", "is_ota_hybrid"],
        ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
        "mfg",
        target_vars=["is_ota_hybrid"],
    )
    p3_diff_all = fit_ols_cr1_wcb(
        mat,
        "log_unremedied",
        ["is_ota_audited", "is_ota_hybrid", "is_dealer_sw"],
        ["mfg", "rec_quarter", "min_my_fe", "comp_fe"],
        "mfg",
        target_vars=["is_ota_hybrid"],
    )
    wald_p3_diff = {}
    for lbl, r_obj in [("sw_ota_oems", p3_diff_sw), ("all_vehicles", p3_diff_all)]:
        trm = r_obj["terms"]["is_ota_hybrid"]
        wald_p3_diff[lbl] = {
            "diff_hybrid_minus_pure": trm["coef"],
            "se_cr1": trm["se_cr1"],
            "t_cr1": trm["t_cr1"],
            "p_t_G1": trm["p_t_G1"],
            "p_wcb": trm["p_wcb"],
            "ci95_lo": trm["ci95_lo"],
            "ci95_hi": trm["ci95_hi"],
        }

    return {
        "regressions": p3_regs,
        "hybrid_minus_pure_unremedied_wald": wald_p3_diff,
        "mature_blast_radius_same_sample": br_mat,
        "aggregate_fleet_accounting_mature18m": agg_accounting,
        "mature_sample_composition": mature_sample_composition,
        "breakeven_frontier": frontier_points,
    }


def run_pillar4_safety_cascades_and_complaints(df_all: pd.DataFrame, es_df: pd.DataFrame) -> dict:
    """Pillar 4: Safety Severity, Regulatory Oversight, Repeat Cascades & Real-World Complaint-Decay DiD."""
    c18 = add_common_fe_helpers(df_all[df_all["rec_year"].between(2018, 2026)].copy())
    ota_oems = set(c18[c18["is_ota_audited"] == 1]["mfg"].unique())
    sw = c18[(c18["mfg"].isin(ota_oems)) & (c18["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"]))].copy()
    sw_u365 = sw[sw["uncensored_365d"] == 1].copy()
    sw_u730 = sw[sw["uncensored_730d"] == 1].copy()

    # 4A. Safety Severity, Oversight, Lifecycle Lag (confirming MY-FE null!), and Repeat Cascades
    safety_outcomes = [
        ("do_not_drive", sw),
        ("park_outside", sw),
        ("has_fmvss", sw),
        ("has_odi_action", sw),
        ("is_regulator_forced", sw),
        ("con_crash", sw),
        ("con_fire", sw),
        ("days_recall_to_owner", sw),
        ("days_mfg_to_recall", sw),
        ("still_in_production", sw),
        ("any_repeat_365d", sw_u365),
        ("any_repeat_730d", sw_u730),
    ]
    p4_safety: dict = {}
    for y, src in safety_outcomes:
        p4_safety[f"4way_{y}"] = strip_private(
            fit_ols_cr1_wcb(src, y, ["is_ota_pure", "is_ota_hybrid"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        )
        p4_safety[f"anyota_{y}"] = strip_private(
            fit_ols_cr1_wcb(src, y, ["is_ota_audited"], ["mfg", "rec_year", "min_my_fe", "comp_fe"], "mfg")
        )
        p4_safety[f"apiota2018_24_{y}"] = strip_private(
            fit_ols_cr1_wcb(
                src[src["rec_year"].between(2018, 2024)],
                y,
                ["is_ota_api_full"],
                ["mfg", "rec_year", "min_my_fe", "comp_fe"],
                "mfg",
            )
        )

    # Descriptive means across 4 modalities (2018-2026)
    safety_desc = {}
    for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
        s = c18[c18["modality4"] == mod]
        s365 = s[s["uncensored_365d"] == 1]
        s730 = s[s["uncensored_730d"] == 1]
        safety_desc[mod] = {
            "n": len(s),
            "do_not_drive_pct": round(100.0 * float(s["do_not_drive"].mean()), 2),
            "park_outside_pct": round(100.0 * float(s["park_outside"].mean()), 2),
            "fmvss_pct": round(100.0 * float(s["has_fmvss"].mean()), 2),
            "odi_action_pct": round(100.0 * float(s["has_odi_action"].mean()), 2),
            "regulator_forced_pct": round(100.0 * float(s["is_regulator_forced"].mean()), 2),
            "con_crash_pct": round(100.0 * float(s["con_crash"].mean()), 2),
            "con_fire_pct": round(100.0 * float(s["con_fire"].mean()), 2),
            "median_days_mfg_to_recall": round(float(s["days_mfg_to_recall"].median()), 1) if s["days_mfg_to_recall"].notna().any() else None,
            "median_days_recall_to_owner": round(float(s["days_recall_to_owner"].median()), 1) if s["days_recall_to_owner"].notna().any() else None,
            "repeat_365d_pct": round(100.0 * float(s365["any_repeat_365d"].mean()), 2) if len(s365) else None,
            "repeat_730d_pct": round(100.0 * float(s730["any_repeat_730d"].mean()), 2) if len(s730) else None,
        }

    # 4B. Pre-Recall Safety-Complaint Buildup ([-12m, -1m]) & Exact Crashes/Fires/Injuries/Deaths
    # across all 4,560 balanced 2021-2025 campaigns (deduplicated by unique ODINO per campaign)
    c_bal = df_all[df_all["cmpl_pre12m_comp"].notna()].copy()
    pre_m_es = es_df[es_df["rel_month"].between(-12, -1)].copy()
    early_pre = pre_m_es[pre_m_es["rel_month"].between(-12, -4)].groupby("CAMPNO")["cmpl_comp_fail"].mean()
    late_pre = pre_m_es[pre_m_es["rel_month"].between(-3, -1)].groupby("CAMPNO")["cmpl_comp_fail"].mean()
    c_bal["early_pre_monthly_fail"] = c_bal["CAMPNO"].map(early_pre).fillna(0.0)
    c_bal["late_pre_monthly_fail"] = c_bal["CAMPNO"].map(late_pre).fillna(0.0)

    def _pre_summary(sub: pd.DataFrame) -> dict:
        n_c = len(sub)
        if n_c == 0:
            return {"n_campaigns": 0}
        early_m = float(sub["early_pre_monthly_fail"].mean())
        late_m = float(sub["late_pre_monthly_fail"].mean())
        return {
            "n_campaigns": n_c,
            "pct_with_ge1_pre12m_fail": round(100.0 * float((sub["cmpl_pre12m_fail"] > 0).mean()), 2),
            "mean_pre12m_fail_cmpl": round(float(sub["cmpl_pre12m_fail"].mean()), 2),
            "median_pre12m_fail_cmpl": round(float(sub["cmpl_pre12m_fail"].median()), 1),
            "mean_post12m_fail_cmpl": round(float(sub["cmpl_post12m_fail"].mean()), 2),
            "pre_buildup_ratio_m3m1_vs_m12m4": round(late_m / max(early_m, 1e-6), 2),
            "pct_with_ge1_pre12m_crash": round(100.0 * float((sub["cmpl_pre12m_crash"] > 0).mean()), 2),
            "pct_with_ge1_pre12m_fire": round(100.0 * float((sub["cmpl_pre12m_fire"] > 0).mean()), 2),
            "pct_with_ge1_pre12m_inj_cmpl": round(100.0 * float((sub["cmpl_pre12m_inj_cmpl"] > 0).mean()), 2),
            "pct_with_ge1_pre12m_fatal_cmpl": round(100.0 * float((sub["cmpl_pre12m_fatal_cmpl"] > 0).mean()), 2),
            "mean_pre12m_crash_cmpl": round(float(sub["cmpl_pre12m_crash"].mean()), 2),
            "mean_pre12m_fire_cmpl": round(float(sub["cmpl_pre12m_fire"].mean()), 2),
            "mean_pre12m_inj_cmpl": round(float(sub["cmpl_pre12m_inj_cmpl"].mean()), 2),
            "mean_pre12m_fatal_cmpl": round(float(sub["cmpl_pre12m_fatal_cmpl"].mean()), 2),
        }

    prerecall_buildup_summary = {
        mod: _pre_summary(c_bal[c_bal["modality4"] == mod])
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]
    }
    prerecall_buildup_summary["Official_API_OTA"] = _pre_summary(c_bal[c_bal["is_ota_api_full"] == 1])

    # 4C. Real-World Consumer Complaint-Decay Event-Study DiD ([-12m, +12m], 2021-2025 Balanced Panel)
    es = es_df.copy()
    es["log_cmpl_ldate"] = np.log1p(es["cmpl_comp_ldate"].clip(lower=0))
    es["log_cmpl_fail"] = np.log1p(es["cmpl_comp_fail"].clip(lower=0))
    es["log_cmpl_ldate_sev"] = np.log1p(es["cmpl_comp_ldate_sev"].clip(lower=0))
    es["log_cmpl_fail_sev"] = np.log1p(es["cmpl_comp_fail_sev"].clip(lower=0))
    es["log_cmpl_veh"] = np.log1p(es["cmpl_veh_ldate"].clip(lower=0))
    es["rate_fail_per_100k"] = 100_000.0 * es["cmpl_comp_fail"] / es["potaff"].clip(lower=1.0)
    es["log_rate_fail_100k"] = np.log1p(es["rate_fail_per_100k"].clip(lower=0))
    es["post"] = (es["rel_month"] >= 1).astype(float)
    es["post_inc0"] = (es["rel_month"] >= 0).astype(float)
    es["is_ota_post"] = es["is_ota_audited"] * es["post"]
    es["is_pure_post"] = es["is_ota_pure"] * es["post"]
    es["is_hybrid_post"] = es["is_ota_hybrid"] * es["post"]
    es["is_dsw_post"] = es["is_dealer_sw"] * es["post"]
    es["is_api_post"] = es["is_ota_api_full"] * es["post"]

    # Identify active-signal campaigns (at least 1 matched component complaint in [-12, +12])
    camp_tot_ld = es.groupby("CAMPNO")["cmpl_comp_ldate"].transform("sum")
    camp_tot_fl = es.groupby("CAMPNO")["cmpl_comp_fail"].transform("sum")
    es["has_comp_cmpl"] = ((camp_tot_ld > 0) | (camp_tot_fl > 0)).astype(int)

    # Software-only complaint sample (within OTA-capable OEMs AND all software recalls)
    es_sw = es[es["modality4"].isin(["Pure_OTA", "Hybrid_OTA", "Dealer_Software"])].copy()
    es_sw_no0 = es_sw[es_sw["rel_month"] != 0].copy()  # exclude announcement month 0 cleanly for Pre vs Post DiD!
    es_sw_act = es_sw_no0[es_sw_no0["has_comp_cmpl"] == 1].copy()
    es_sw_short = es_sw[es_sw["rel_month"].isin([-3, -2, -1, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12])].copy()
    es_sw_short_act = es_sw_short[es_sw_short["has_comp_cmpl"] == 1].copy()
    es_all_no0 = es[es["rel_month"] != 0].copy()
    es_all_act = es_all_no0[es_all_no0["has_comp_cmpl"] == 1].copy()

    cmpl_did: dict = {}
    for label, dsub, x_terms in [
        ("sw_all_anyota_oemcl", es_sw_no0, ["is_ota_post"]),
        ("sw_all_4way_oemcl", es_sw_no0, ["is_pure_post", "is_hybrid_post"]),
        ("sw_all_api_oemcl", es_sw_no0, ["is_api_post"]),
        ("sw_active_anyota_oemcl", es_sw_act, ["is_ota_post"]),
        ("sw_active_4way_oemcl", es_sw_act, ["is_pure_post", "is_hybrid_post"]),
        ("sw_active_api_oemcl", es_sw_act, ["is_api_post"]),
        ("sw_short_m3m1_p1p12_4way_oemcl", es_sw_short_act, ["is_pure_post", "is_hybrid_post"]),
        ("sw_short_m3m1_p1p12_anyota_oemcl", es_sw_short_act, ["is_ota_post"]),
        ("allveh_active_4way_oemcl", es_all_act, ["is_pure_post", "is_hybrid_post", "is_dsw_post"]),
    ]:
        for y in ["log_cmpl_fail", "log_cmpl_ldate", "log_cmpl_fail_sev", "log_cmpl_ldate_sev", "log_rate_fail_100k"]:
            cmpl_did[f"{label}__{y}"] = strip_private(
                fit_absorbed_2way_fe_did(dsub, y, x_terms, "CAMPNO", ["rel_month", "cal_ym"], "mfg")
            )
    # Also Campaign-clustered SEs on headline specs
    for y in ["log_cmpl_fail", "log_cmpl_ldate"]:
        cmpl_did[f"sw_all_4way_campcl__{y}"] = strip_private(
            fit_absorbed_2way_fe_did(es_sw_no0, y, ["is_pure_post", "is_hybrid_post"], "CAMPNO", ["rel_month", "cal_ym"], "CAMPNO", n_boot=499)
        )
        cmpl_did[f"sw_active_4way_campcl__{y}"] = strip_private(
            fit_absorbed_2way_fe_did(es_sw_act, y, ["is_pure_post", "is_hybrid_post"], "CAMPNO", ["rel_month", "cal_ym"], "CAMPNO", n_boot=499)
        )

    # Full dynamic monthly event-study curve (quarterly/bi-monthly + exact monthly -12..+12, ref = -1) on software recalls
    rel_months = [m for m in range(-12, 13) if m != -1]
    dyn_cols = []
    for m in rel_months:
        col = f"ota_m{abs(m)}" if m < 0 else f"ota_p{m}"
        es_sw[col] = (es_sw["is_ota_audited"] * (es_sw["rel_month"] == m)).astype(float)
        dyn_cols.append(col)

    dyn_fail = fit_absorbed_2way_fe_did(es_sw, "log_cmpl_fail", dyn_cols, "CAMPNO", ["rel_month", "cal_ym"], "mfg", n_boot=499)
    dyn_ldate = fit_absorbed_2way_fe_did(es_sw, "log_cmpl_ldate", dyn_cols, "CAMPNO", ["rel_month", "cal_ym"], "mfg", n_boot=499)
    pre_cols = [f"ota_m{abs(m)}" for m in range(-12, -1)]
    post_cols = [f"ota_p{m}" for m in range(1, 13)]

    # Descriptive normalized trajectory by modality (mean monthly complaints per campaign & indexed to pre-mean [-6,-1])
    traj = []
    for rel_m in range(-12, 13):
        rd: dict = {"rel_month": rel_m}
        for mod in ["Pure_OTA", "Hybrid_OTA", "Dealer_Software", "Physical_Hardware"]:
            sub = es[(es["rel_month"] == rel_m) & (es["modality4"] == mod)]
            rd[mod] = {
                "n_camp": len(sub),
                "mean_fail": round(float(sub["cmpl_comp_fail"].mean()), 4) if len(sub) else None,
                "mean_ldate": round(float(sub["cmpl_comp_ldate"].mean()), 4) if len(sub) else None,
                "mean_log_fail": round(float(sub["log_cmpl_fail"].mean()), 4) if len(sub) else None,
                "mean_log_ldate": round(float(sub["log_cmpl_ldate"].mean()), 4) if len(sub) else None,
                "mean_sev_fail": round(float(sub["cmpl_comp_fail_sev"].mean()), 4) if len(sub) else None,
            }
        traj.append(rd)

    return {
        "safety_descriptive_2018_2026": safety_desc,
        "safety_fe_regressions": p4_safety,
        "prerecall_buildup_and_hazards": prerecall_buildup_summary,
        "complaint_did_summary": {
            "n_sw_campaigns": int(es_sw["CAMPNO"].nunique()),
            "n_sw_active_campaigns": int(es_sw_act["CAMPNO"].nunique()),
            "n_all_campaigns": int(es["CAMPNO"].nunique()),
            "n_all_active_campaigns": int(es_all_act["CAMPNO"].nunique()),
            "did_regressions": cmpl_did,
            "dynamic_event_study_fail": strip_private(dyn_fail),
            "dynamic_event_study_fail_pre_wald": wald_joint_test(dyn_fail, pre_cols),
            "dynamic_event_study_fail_post_wald": wald_joint_test(dyn_fail, post_cols),
            "dynamic_event_study_ldate": strip_private(dyn_ldate),
            "dynamic_event_study_ldate_pre_wald": wald_joint_test(dyn_ldate, pre_cols),
            "dynamic_event_study_ldate_post_wald": wald_joint_test(dyn_ldate, post_cols),
            "descriptive_monthly_trajectory": traj,
        },
    }


def main() -> None:
    t0 = time.time()
    df_all = pd.read_csv(PROC_DIR / "campaigns_2015_2026.csv")
    es_df = pd.read_csv(PROC_DIR / "complaint_event_study_panel.csv")
    print(f"[LOAD] Campaigns: {len(df_all):,} | Complaint ES rows: {len(es_df):,}", flush=True)

    print("[RUN] Pillar 1: Blast-Radius Concentration & Endogenous Selection Decomposition...", flush=True)
    p1 = run_pillar1_blast_radius_and_selection(df_all)

    print("[RUN] Pillar 2: Frictionless Remediation Velocity & Vehicle-Age Decay...", flush=True)
    p2 = run_pillar2_remediation_velocity(df_all)

    print("[RUN] Pillar 3: Net Unremedied Fleet Exposure & Break-Even Frontier...", flush=True)
    p3 = run_pillar3_net_unremedied_exposure(df_all)

    print("[RUN] Pillar 4: Safety Severity, Cascades & Real-World Complaint-Decay DiD...", flush=True)
    p4 = run_pillar4_safety_cascades_and_complaints(df_all, es_df)

    full = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "elapsed_sec": round(time.time() - t0, 2),
        "pillar1_blast_radius": p1,
        "pillar2_remediation_velocity": p2,
        "pillar3_net_unremedied_exposure": p3,
        "pillar4_safety_and_complaints": p4,
    }
    out_path = RES_DIR / "d12_econometric_results.json"
    out_path.write_text(json.dumps(full, indent=2), encoding="utf-8")
    print(f"[DONE] Saved complete 4-pillar econometric suite in {full['elapsed_sec']}s -> {out_path}", flush=True)

    # Print crisp executive readout of all 4 pillars
    print("\n=== HEADLINE READOUT ===", flush=True)
    print("P1 Blast Radius (SW OTA-OEMs, 4way log_potaff):", p1["main_sw_ota_oems"]["sw_ota_oems_4way_log_potaff"]["terms"], flush=True)
    print("P1 Blast Radius (SW OTA-OEMs, API 2018-24 log_potaff):", p1["main_sw_ota_oems"]["sw_ota_oems_api2018_24_log_potaff"]["terms"], flush=True)
    print("P1 ITT Staggered Adoption (pooled DiD log_potaff):", p1["itt_staggered_adoption"]["pooled_did"]["terms"], flush=True)
    print("P1 ITT Pre-trend Wald:", p1["itt_staggered_adoption"]["pre_trend_wald_m3_m2"], flush=True)
    print("P1 Sun-Abraham IW:", p1["itt_staggered_adoption"]["sun_abraham_iw"], flush=True)
    print("P1 Unconditional SDV MY>=2021 shift (SW):", p1["unconditional_sdv_cohort_shift"]["sw_my2021plus_vs_pre2020"]["terms"], flush=True)
    print("P1 Placebo Physical MY>=2021 shift:", p1["unconditional_sdv_cohort_shift"]["physical_hardware_placebo_my2021plus"]["terms"], flush=True)
    print("P2 Mature Completion Rate (SW OTA-OEMs, 4way):", p2["mature_18m_regressions"]["sw_ota_oems_4way"]["terms"], flush=True)
    print("P2 Mature Completion Rate (SW OTA-OEMs, API OTA):", p2["mature_18m_regressions"]["sw_ota_oems_api_ota"]["terms"], flush=True)
    print("P2 Vehicle-Age Decay Interaction (SW 4way):", p2["vehicle_age_decay"]["regressions"]["sw_ota_oems_4way_x_age"]["terms"], flush=True)
    print("P2 Vehicle-Age Decay Excl. Tesla (Any OTA / API):", p2["vehicle_age_decay"]["regressions"]["sw_excl_tesla_anyota_x_age"]["terms"]["ota_any_x_age"], p2["vehicle_age_decay"]["regressions"]["sw_excl_tesla_api_x_age"]["terms"]["api_ota_x_age"], flush=True)
    print("P3 Mature Pure-OTA Composition (Tesla vs Non-Tesla):", p3["mature_sample_composition"]["pure_ota_tesla_subsample"], p3["mature_sample_composition"]["pure_ota_nontesla_subsample"], flush=True)
    print("P3 Mature Net Unremedied Proxy (SW OTA-OEMs, 4way):", p3["regressions"]["mature_sw_ota_oems_4way"]["terms"], flush=True)
    print("P3 Mature Net Unremedied Proxy (SW OTA-OEMs, API OTA):", p3["regressions"]["mature_sw_ota_oems_api_ota"]["terms"], flush=True)
    print("P3 Mature Net Unremedied Proxy (All Vehicles vs Phys):", p3["regressions"]["mature_all_vehicles_4way_vs_phys"]["terms"], flush=True)
    print("P3 Hybrid minus Pure Contrast (Exact WCB):", p3["hybrid_minus_pure_unremedied_wald"], flush=True)
    print("P3 Break-Even Frontier (OTA-OEM Matched):", p3["breakeven_frontier"]["within_ota_oem_matched_frontier"], flush=True)
    print("P4 Complaint DiD SW All (log_cmpl_fail, 4way):", p4["complaint_did_summary"]["did_regressions"]["sw_all_4way_oemcl__log_cmpl_fail"]["terms"], flush=True)
    print("P4 Complaint DiD SW Active (log_cmpl_fail, 4way):", p4["complaint_did_summary"]["did_regressions"]["sw_active_4way_oemcl__log_cmpl_fail"]["terms"], flush=True)
    print("P4 Complaint DiD SW Active (log_cmpl_ldate, 4way):", p4["complaint_did_summary"]["did_regressions"]["sw_active_4way_oemcl__log_cmpl_ldate"]["terms"], flush=True)


if __name__ == "__main__":
    main()
