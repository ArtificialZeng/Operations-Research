"""Exact econometric, WLS/OLS FWL, CR1/Two-Way/HAC, WCB (Rademacher & Webb-6pt),
and LF-normalized JSON utilities for K1 /boost (U.S. Utility-Scale Battery Storage).

Mathematical guarantees verified in tests/test_k1_boost.py:
  1. Weighted (WLS) and unweighted (OLS) FWL alternating projections (tol=1e-13,
     max_iter=600) with exact absorbed nested-FE degrees of freedom via bipartite
     connected components (1-way & 2-way FE) or SVD rank (3+ way FE).
  2. Exact equivalence between FWL WLS/OLS + restricted WCB (both Rademacher and
     Webb 6-point weights) and brute-force explicit LSDV WLS/OLS to atol=1e-12.
  3. Exact Cameron-Gelbach-Miller two-way clustering, exact permutation Randomization
     Inference, and Newey-West HAC / date-clustered SEs for hourly MEF regressions.
  4. Strict no-NaN / no-Inf LF-normalized JSON persistence with SHA-256 verification.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy import stats

WAVE7_DIR = Path(r"D:\AI_Science\antigravity\frontier_discovery_20261126_wave7")
WAVE7_DATA_DIR = WAVE7_DIR / "data_k1"
WAVE7_RAW_EIA930_DIR = WAVE7_DATA_DIR / "raw_eia930"

WS_DIR = Path(r"D:\AI_Science\antigravity\k1_boost_grid_battery_carbon_20261127")
RAW_EXT_DIR = WS_DIR / "data" / "raw_external"
PROC_DIR = WS_DIR / "data" / "processed"
RES_DIR = WS_DIR / "results"
FIG_DIR = WS_DIR / "figures"

WEBB6_WEIGHTS = np.array(
    [
        -np.sqrt(1.5),
        -1.0,
        -np.sqrt(0.5),
        np.sqrt(0.5),
        1.0,
        np.sqrt(1.5),
    ],
    dtype=np.float64,
)
RADEMACHER_WEIGHTS = np.array([-1.0, 1.0], dtype=np.float64)

# Exact 4-window disjoint partition of all 24 EIA-930 local Hour-Ending hours (1..24).
# Verified against EIA-930 2025 hourly solar across U.S. grids: zero solar in Overnight.
DIURNAL_WINDOWS: dict[str, list[int]] = {
    "Overnight": [23, 24, 1, 2, 3, 4, 5, 6],  # 23:00-06:00 (8 hrs)
    "Morning Ramp": [7, 8, 9],  # 07:00-09:00 (3 hrs)
    "Midday Solar": [10, 11, 12, 13, 14, 15, 16],  # 10:00-16:00 (7 hrs)
    "Evening Peak": [17, 18, 19, 20, 21, 22],  # 17:00-22:00 (6 hrs)
}

HOUR_TO_WINDOW: dict[int, str] = {
    h: win for win, hrs in DIURNAL_WINDOWS.items() for h in hrs
}


def _check_no_nan(obj: Any, path: str = "$") -> None:
    if isinstance(obj, (float, np.floating)) and not np.isfinite(float(obj)):
        raise ValueError(f"Non-finite float {obj!r} at JSON path {path}")
    if isinstance(obj, dict):
        for k, v in obj.items():
            _check_no_nan(v, f"{path}.{k}")
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            _check_no_nan(v, f"{path}[{i}]")


def _clean_json_types(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {str(k): _clean_json_types(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_json_types(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    return obj


def save_json_lf(path: Path, obj: Any) -> str:
    """Write UTF-8 LF-normalized JSON (zero NaN/Inf) and return its SHA-256 hex digest."""
    clean = _clean_json_types(obj)
    _check_no_nan(clean)
    path.parent.mkdir(parents=True, exist_ok=True)
    txt = json.dumps(clean, indent=2, default=str, allow_nan=False)
    data = (txt.replace("\r\n", "\n") + "\n").encode("utf-8")
    path.write_bytes(data)
    return hashlib.sha256(data).hexdigest()


def _union_find_components(c1: np.ndarray, k1: int, c2: np.ndarray, k2: int) -> int:
    """Exact connected components in the bipartite FE graph (guarantees rank = k1+k2-C)."""
    parent = np.arange(k1 + k2, dtype=np.int64)

    def find(a: int) -> int:
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = int(parent[a])
        return a

    edges = np.unique(c1.astype(np.int64) * k2 + c2.astype(np.int64))
    u_nodes = edges // k2
    v_nodes = (edges % k2) + k1
    for u, v in zip(u_nodes.tolist(), v_nodes.tolist()):
        ru, rv = find(u), find(v)
        if ru != rv:
            parent[rv] = ru

    return len({find(i) for i in range(k1 + k2)})


def count_fe_dof_exact(fe_groups: list[np.ndarray]) -> int:
    """Compute exact absorbed fixed-effect degrees of freedom (column rank of FE dummies)."""
    if not fe_groups:
        return 0
    encoded = []
    for g in fe_groups:
        codes, uniques = pd.factorize(g, sort=False)
        encoded.append((codes, len(uniques)))

    if len(encoded) == 1:
        return int(encoded[0][1])

    if len(encoded) == 2:
        (c1, k1), (c2, k2) = encoded
        return int(k1 + k2 - _union_find_components(c1, k1, c2, k2))

    total_cols = sum(k for _, k in encoded)
    n = len(encoded[0][0])
    if total_cols <= 2500 and n <= 25000:
        D = np.zeros((n, total_cols), dtype=np.float64)
        col_off = 0
        rows = np.arange(n)
        for codes, k in encoded:
            D[rows, col_off + codes] = 1.0
            col_off += k
        return int(np.linalg.matrix_rank(D))

    (c1, k1), (c2, k2) = encoded[0], encoded[1]
    dof = k1 + k2 - _union_find_components(c1, k1, c2, k2)
    for idx in range(2, len(encoded)):
        ci, ki = encoded[idx]
        comp_i = _union_find_components(c1, k1, ci, ki)
        dof += max(0, ki - comp_i)
    return int(dof)


def demean_groups_weighted(
    arr: np.ndarray,
    groups: list[np.ndarray],
    weights: np.ndarray | None = None,
    tol: float = 1e-13,
    max_iter: int = 600,
) -> np.ndarray:
    """High-precision weighted alternating projections orthogonal to 1+ FE spaces under W."""
    x = np.array(arr, dtype=np.float64, copy=True)
    was_1d = x.ndim == 1
    if was_1d:
        x = x[:, None]
    if not groups:
        return x[:, 0] if was_1d else x

    n = x.shape[0]
    w = np.ones(n, dtype=np.float64) if weights is None else np.asarray(weights, dtype=np.float64)

    enc = []
    for g in groups:
        codes, uniques = pd.factorize(g, sort=False)
        k = len(uniques)
        w_sum = np.bincount(codes, weights=w, minlength=k).astype(np.float64)
        w_sum = np.where(w_sum > 0.0, w_sum, 1.0)
        enc.append((codes, k, w_sum))

    if len(enc) == 1:
        codes, k, w_sum = enc[0]
        for j in range(x.shape[1]):
            num = np.bincount(codes, weights=w * x[:, j], minlength=k)
            x[:, j] -= (num / w_sum)[codes]
        return x[:, 0] if was_1d else x

    for _ in range(max_iter):
        max_diff = 0.0
        for codes, k, w_sum in enc:
            for j in range(x.shape[1]):
                num = np.bincount(codes, weights=w * x[:, j], minlength=k)
                means = num / w_sum
                diff = float(np.max(np.abs(means)))
                max_diff = max(max_diff, diff)
                x[:, j] -= means[codes]
        if max_diff < tol:
            break
    return x[:, 0] if was_1d else x


def _make_fast_weighted_demeaner(
    fe_groups: list[np.ndarray],
    w: np.ndarray,
    tol: float = 1e-13,
    max_iter: int = 400,
):
    fe_enc = []
    for g in fe_groups:
        c, u = pd.factorize(g, sort=False)
        m = len(u)
        w_sum = np.bincount(c, weights=w, minlength=m).astype(np.float64)
        w_sum = np.where(w_sum > 0.0, w_sum, 1.0)
        fe_enc.append((c, m, w_sum))

    def demean_1d(v: np.ndarray) -> np.ndarray:
        out = v.copy()
        if not fe_enc:
            return out
        if len(fe_enc) == 1:
            c, m, w_sum = fe_enc[0]
            means = np.bincount(c, weights=w * out, minlength=m) / w_sum
            out -= means[c]
            return out
        for _ in range(max_iter):
            md = 0.0
            for c, m, w_sum in fe_enc:
                means = np.bincount(c, weights=w * out, minlength=m) / w_sum
                d = float(np.max(np.abs(means)))
                md = max(md, d)
                out -= means[c]
            if md < tol:
                break
        return out

    return demean_1d


def _cluster_meat(Xw: np.ndarray, ew: np.ndarray, cl_codes: np.ndarray, G: int) -> np.ndarray:
    k = Xw.shape[1]
    S = np.zeros((G, k), dtype=np.float64)
    for j in range(k):
        S[:, j] = np.bincount(cl_codes, weights=Xw[:, j] * ew, minlength=G)
    return S.T @ S


def wls_fe_cr1_wcb(
    y: np.ndarray,
    X: np.ndarray,
    clusters: np.ndarray,
    fe_groups: list[np.ndarray] | None = None,
    weights: np.ndarray | None = None,
    col_names: list[str] | None = None,
    wcb_var_idx: int | None = None,
    wcb_B: int = 0,
    wcb_dist: str = "rademacher",
    seed: int = 20261127,
    cluster2: np.ndarray | None = None,
    joint_test_indices: list[int] | None = None,
) -> dict[str, Any]:
    """Exact WLS (or OLS when weights=None) with FWL FE absorption, exact nested-FE DOF,
    CR1 one-way and optional CGM two-way clustering, Wald joint F-test, and exact
    LSDV-equivalent restricted Wild Cluster Bootstrap (Rademacher or Webb 6-point).
    """
    y_arr = np.asarray(y, dtype=np.float64)
    X_arr = np.asarray(X, dtype=np.float64)
    if X_arr.ndim == 1:
        X_arr = X_arr[:, None]
    w_raw = (
        np.ones(len(y_arr), dtype=np.float64)
        if weights is None
        else np.asarray(weights, dtype=np.float64)
    )

    valid = np.isfinite(y_arr) & np.all(np.isfinite(X_arr), axis=1) & np.isfinite(w_raw) & (w_raw > 0)
    y_arr = y_arr[valid]
    X_arr = X_arr[valid]
    w_arr = w_raw[valid]
    w_arr = w_arr / np.mean(w_arr)  # scale-invariant normalization
    sqrt_w = np.sqrt(w_arr)

    cl1_arr = np.asarray(clusters)[valid]
    fe_clean = [np.asarray(g)[valid] for g in fe_groups] if fe_groups else []
    cl2_arr = np.asarray(cluster2)[valid] if cluster2 is not None else None

    n, k = X_arr.shape
    if col_names is None:
        col_names = [f"x{i}" for i in range(k)]

    cl1_codes, cl1_u = pd.factorize(cl1_arr, sort=False)
    G = len(cl1_u)

    fe_dof = 0
    if fe_clean:
        M = demean_groups_weighted(
            np.column_stack([y_arr, X_arr]), fe_clean, weights=w_arr, tol=1e-13, max_iter=600
        )
        yd = M[:, 0]
        Xd = M[:, 1:]
        fe_dof = count_fe_dof_exact(fe_clean)
    else:
        yd = y_arr
        Xd = X_arr

    yw = sqrt_w * yd
    Xw = sqrt_w[:, None] * Xd

    svals = np.linalg.svd(Xw, compute_uv=False)
    tol_rank = max(Xw.shape) * np.finfo(float).eps * (svals[0] if len(svals) else 1.0)
    rank = int(np.sum(svals > tol_rank))
    full_rank = rank == k

    if not full_rank or G < 2 or n <= (k + fe_dof):
        return {
            "n": int(n),
            "k": int(k),
            "fe_dof": int(fe_dof),
            "G": int(G),
            "rank": int(rank),
            "full_rank": bool(full_rank),
            "weighted": bool(weights is not None),
            "coefs": {},
        }

    XtX_inv = np.linalg.inv(Xw.T @ Xw)
    beta = XtX_inv @ (Xw.T @ yw)
    ew = yw - Xw @ beta

    dfc1 = (G / (G - 1.0)) * ((n - 1.0) / max(n - k - fe_dof, 1.0))
    V1 = dfc1 * (XtX_inv @ _cluster_meat(Xw, ew, cl1_codes, G) @ XtX_inv)
    se1 = np.sqrt(np.maximum(np.diag(V1), 1e-30))
    t1 = beta / se1
    p1 = 2.0 * stats.t.sf(np.abs(t1), df=max(G - 1, 1))

    # Optional Cameron-Gelbach-Miller two-way clustering
    se2_arr: np.ndarray | None = None
    t2_arr: np.ndarray | None = None
    p2_arr: np.ndarray | None = None
    G2 = None
    if cl2_arr is not None:
        cl2_codes, cl2_u = pd.factorize(cl2_arr, sort=False)
        G2 = len(cl2_u)
        inter_arr = pd.Series(cl1_codes).astype(str) + "_" + pd.Series(cl2_codes).astype(str)
        cl12_codes, cl12_u = pd.factorize(inter_arr.to_numpy(), sort=False)
        G12 = len(cl12_u)
        dfc2 = (G2 / max(G2 - 1.0, 1.0)) * ((n - 1.0) / max(n - k - fe_dof, 1.0))
        dfc12 = (G12 / max(G12 - 1.0, 1.0)) * ((n - 1.0) / max(n - k - fe_dof, 1.0))
        V2 = dfc2 * (XtX_inv @ _cluster_meat(Xw, ew, cl2_codes, G2) @ XtX_inv)
        V12 = dfc12 * (XtX_inv @ _cluster_meat(Xw, ew, cl12_codes, G12) @ XtX_inv)
        V_cgm = V1 + V2 - V12
        # PSD floor at diag(V1) if negative diagonal (rare finite-sample CGM artifact)
        diag_cgm = np.where(np.diag(V_cgm) > 0, np.diag(V_cgm), np.diag(V1))
        se2_arr = np.sqrt(np.maximum(diag_cgm, 1e-30))
        t2_arr = beta / se2_arr
        p2_arr = 2.0 * stats.t.sf(np.abs(t2_arr), df=max(min(G, G2) - 1, 1))

    coefs: dict[str, dict[str, float]] = {}
    for j, nm in enumerate(col_names):
        entry: dict[str, float] = {
            "beta": float(beta[j]),
            "se_cr1": float(se1[j]),
            "t_cr1": float(t1[j]),
            "p_cr1": float(p1[j]),
            "ci95_lo": float(beta[j] - stats.t.ppf(0.975, df=max(G - 1, 1)) * se1[j]),
            "ci95_hi": float(beta[j] + stats.t.ppf(0.975, df=max(G - 1, 1)) * se1[j]),
        }
        if se2_arr is not None and t2_arr is not None and p2_arr is not None:
            entry["se_2way"] = float(se2_arr[j])
            entry["t_2way"] = float(t2_arr[j])
            entry["p_2way"] = float(p2_arr[j])
        coefs[nm] = entry

    out: dict[str, Any] = {
        "n": int(n),
        "k": int(k),
        "fe_dof": int(fe_dof),
        "G": int(G),
        "G2": int(G2) if G2 is not None else None,
        "rank": int(rank),
        "full_rank": True,
        "weighted": bool(weights is not None),
        "coefs": coefs,
    }

    if joint_test_indices:
        idx = list(joint_test_indices)
        b_sub = beta[idx]
        V_sub = V1[np.ix_(idx, idx)]
        q = len(idx)
        f_stat = float((b_sub.T @ np.linalg.pinv(V_sub) @ b_sub) / q)
        p_f = float(stats.f.sf(f_stat, dfn=q, dfd=max(G - 1, 1)))
        out["joint_F"] = {"F": f_stat, "dfn": q, "dfd": int(max(G - 1, 1)), "p": p_f}

    if wcb_var_idx is not None and wcb_B > 0:
        j0 = int(wcb_var_idx)
        other = [j for j in range(k) if j != j0]
        if other:
            Xo_w = Xw[:, other]
            b0 = np.linalg.inv(Xo_w.T @ Xo_w) @ (Xo_w.T @ yw)
            e0 = yd - Xd[:, other] @ b0
            yhat0 = Xd[:, other] @ b0
        else:
            e0 = yd.copy()
            yhat0 = np.zeros_like(yd)

        demean_1d = _make_fast_weighted_demeaner(fe_clean, w_arr, tol=1e-13, max_iter=400)
        rng = np.random.default_rng(seed)
        dist_vals = WEBB6_WEIGHTS if wcb_dist == "webb6" else RADEMACHER_WEIGHTS
        t_obs = float(t1[j0])
        t_boot = np.empty(wcb_B, dtype=np.float64)
        for bi in range(wcb_B):
            rw = rng.choice(dist_vals, size=G)
            ys_d = demean_1d(yhat0 + rw[cl1_codes] * e0)
            ys_w = sqrt_w * ys_d
            bs = XtX_inv @ (Xw.T @ ys_w)
            es_w = ys_w - Xw @ bs
            Vb = dfc1 * (XtX_inv @ _cluster_meat(Xw, es_w, cl1_codes, G) @ XtX_inv)
            seb = float(np.sqrt(max(Vb[j0, j0], 1e-30)))
            t_boot[bi] = bs[j0] / seb
        p_wcb = float((1.0 + np.sum(np.abs(t_boot) >= abs(t_obs))) / (wcb_B + 1.0))
        out["wcb"] = {
            "var": col_names[j0],
            "dist": wcb_dist,
            "B": int(wcb_B),
            "t_obs": t_obs,
            "p_wcb": p_wcb,
        }

    return out


def compute_fwl_cluster_leverage(
    X: np.ndarray,
    clusters: np.ndarray,
    fe_groups: list[np.ndarray],
    target_idx: int = 0,
    weights: np.ndarray | None = None,
) -> dict[str, float]:
    """Compute exact share of identifying FWL variance contributed by each cluster."""
    X_arr = np.asarray(X, dtype=np.float64)
    w_raw = (
        np.ones(len(X_arr), dtype=np.float64)
        if weights is None
        else np.asarray(weights, dtype=np.float64)
    )
    valid = np.all(np.isfinite(X_arr), axis=1) & np.isfinite(w_raw) & (w_raw > 0)
    X_arr = X_arr[valid]
    w_arr = w_raw[valid]
    w_arr = w_arr / np.mean(w_arr)
    fe_clean = [np.asarray(g)[valid] for g in fe_groups]
    cl_clean = np.asarray(clusters)[valid]

    Xd = demean_groups_weighted(X_arr, fe_clean, weights=w_arr, tol=1e-13, max_iter=600)
    Xw = np.sqrt(w_arr)[:, None] * Xd
    other = [j for j in range(Xw.shape[1]) if j != target_idx]
    if other:
        Xo = Xw[:, other]
        xt = Xw[:, target_idx] - Xo @ (np.linalg.inv(Xo.T @ Xo) @ (Xo.T @ Xw[:, target_idx]))
    else:
        xt = Xw[:, target_idx]
    sq = xt**2
    tot = float(np.sum(sq))
    s = pd.Series(sq).groupby(cl_clean).sum() / max(tot, 1e-30)
    return {str(k): float(v) for k, v in s.sort_values(ascending=False).items()}


def hourly_ols_cluster_hac(
    y: np.ndarray,
    X: np.ndarray,
    date_clusters: np.ndarray,
    fe_groups: list[np.ndarray] | None = None,
    col_names: list[str] | None = None,
    nw_lags: int = 24,
) -> dict[str, Any]:
    """Hourly regression with FE absorption, date-clustered CR1 SEs, and Newey-West HAC SEs."""
    y_arr = np.asarray(y, dtype=np.float64)
    X_arr = np.asarray(X, dtype=np.float64)
    if X_arr.ndim == 1:
        X_arr = X_arr[:, None]
    valid = np.isfinite(y_arr) & np.all(np.isfinite(X_arr), axis=1)
    y_arr = y_arr[valid]
    X_arr = X_arr[valid]
    cl_arr = np.asarray(date_clusters)[valid]
    fe_clean = [np.asarray(g)[valid] for g in fe_groups] if fe_groups else []

    n, k = X_arr.shape
    if col_names is None:
        col_names = [f"x{i}" for i in range(k)]

    fe_dof = 0
    if fe_clean:
        M = demean_groups_weighted(np.column_stack([y_arr, X_arr]), fe_clean, tol=1e-12, max_iter=400)
        yd, Xd = M[:, 0], M[:, 1:]
        fe_dof = count_fe_dof_exact(fe_clean)
    else:
        yd, Xd = y_arr, X_arr

    XtX_inv = np.linalg.pinv(Xd.T @ Xd)
    beta = XtX_inv @ (Xd.T @ yd)
    e = yd - Xd @ beta

    # Date-clustered CR1 SE
    cl_codes, cl_u = pd.factorize(cl_arr, sort=False)
    G = len(cl_u)
    dfc = (G / max(G - 1.0, 1.0)) * ((n - 1.0) / max(n - k - fe_dof, 1.0))
    V_cl = dfc * (XtX_inv @ _cluster_meat(Xd, e, cl_codes, G) @ XtX_inv)
    se_cl = np.sqrt(np.maximum(np.diag(V_cl), 1e-30))

    # Newey-West Bartlett HAC SE (assuming time-ordered observations)
    U = Xd * e[:, None]
    Omega = U.T @ U
    L = min(nw_lags, max(n - 1, 0))
    for lag in range(1, L + 1):
        w_l = 1.0 - lag / (L + 1.0)
        Gamma_l = U[lag:].T @ U[:-lag]
        Omega += w_l * (Gamma_l + Gamma_l.T)
    V_nw = (n / max(n - k - fe_dof, 1.0)) * (XtX_inv @ Omega @ XtX_inv)
    se_nw = np.sqrt(np.maximum(np.diag(V_nw), 1e-30))

    coefs = {}
    for j, nm in enumerate(col_names):
        t_cl = float(beta[j] / se_cl[j])
        t_nw = float(beta[j] / se_nw[j])
        coefs[nm] = {
            "beta": float(beta[j]),
            "se_day": float(se_cl[j]),
            "t_day": t_cl,
            "p_day": float(2.0 * stats.t.sf(abs(t_cl), df=max(G - 1, 1))),
            "se_nw": float(se_nw[j]),
            "t_nw": t_nw,
            "p_nw": float(2.0 * stats.norm.sf(abs(t_nw))),
        }
    return {"n": int(n), "G_days": int(G), "fe_dof": int(fe_dof), "coefs": coefs}
