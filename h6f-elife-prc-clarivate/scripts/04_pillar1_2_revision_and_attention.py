"""Step 4: Pillars 1 & 2 Econometric Engine.
- Pillar 1: Complete true v1 -> VoR transition dynamics, intrinsic revision norms,
  and the Clarivate Dec 2024 ESCI Solid-threshold natural experiment (fixed 365d/450d/540d windows).
- Pillar 2: Evaluation-Market Paradox across strictly post-v1 OpenAlex citations,
  Crossref citations, AND live eLife reader page-views & downloads (cumulative,
  strictly post-VoR, fixed 12m post-VoR, and within-paper post-vs-pre VoR rate DiD),
  plus Methodological VoR-Date Alignment Autopsy, TOST equivalence, WCB, and 18-subject LOSO.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import stats

BASE_DIR = Path(r"D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126")
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_lf(path: Path, obj) -> str:
    txt = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(txt.encode("utf-8"))
    return sha256_bytes(path)


def fe_ols_cr1(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    fe_col: str,
    cluster_col: str,
    wcb_target: str | None = None,
    wcb_B: int = 1999,
    seed: int = 2026,
) -> dict:
    """Exact within-FE OLS with CR1 small-sample cluster-robust SEs, rank check, and optional WCB."""
    cols = list(dict.fromkeys([y_col] + list(x_cols) + [fe_col, cluster_col]))
    sub = df[cols].dropna().copy()
    vc = sub[fe_col].value_counts()
    sub = sub[sub[fe_col].isin(vc[vc >= 2].index)].copy()
    if len(sub) < 25:
        return {"n": len(sub), "error": "too_few"}

    g = sub.groupby(fe_col)
    y_dm = (sub[y_col] - g[y_col].transform("mean")).to_numpy(dtype=float)
    X_dm_df = pd.DataFrame({c: sub[c] - g[c].transform("mean") for c in x_cols}, index=sub.index)
    keep = [c for c in x_cols if X_dm_df[c].std() > 1e-10]
    if not keep:
        return {"n": len(sub), "error": "collinear"}
    X_dm = X_dm_df[keep].to_numpy(dtype=float)

    N = len(sub)
    M = int(sub[fe_col].nunique())
    K = len(keep)
    rank = int(np.linalg.matrix_rank(X_dm))
    if rank < K:
        return {"n": N, "rank": rank, "k": K, "error": "rank_deficient"}

    clusters = sub[cluster_col].to_numpy()
    uniq_cl, inv_cl = np.unique(clusters, return_inverse=True)
    G = len(uniq_cl)

    # Exact OLS + manual CR1 sandwich (guaranteed exact DOF = N - M - K!)
    XtX_inv = np.linalg.inv(X_dm.T @ X_dm)
    beta = XtX_inv @ (X_dm.T @ y_dm)
    resid = y_dm - X_dm @ beta

    # Meat matrix summed by cluster
    meat = np.zeros((K, K), dtype=float)
    for cl_idx in range(G):
        mask = inv_cl == cl_idx
        sc = X_dm[mask].T @ resid[mask]
        meat += np.outer(sc, sc)
    cr1_scale = (G / max(G - 1.0, 1.0)) * ((N - 1.0) / max(N - M - K, 1.0))
    V_cr1 = cr1_scale * (XtX_inv @ meat @ XtX_inv)
    se = np.sqrt(np.maximum(np.diag(V_cr1), 0.0))

    out: dict = {"n": N, "G": G, "M_fe": M, "K": K, "rank": rank, "params": {}}
    for idx, c in enumerate(keep):
        b = float(beta[idx])
        s = float(se[idx])
        tval = b / s if s > 0 else float("nan")
        pval = float(2.0 * stats.t.sf(abs(tval), df=max(G - 1, 1)))
        out["params"][c] = {"beta": b, "se": s, "t": float(tval), "p": pval}

    # Optional Restricted Wild Cluster Bootstrap (Rademacher weights) on wcb_target
    if wcb_target and wcb_target in keep and G >= 4:
        t_idx = keep.index(wcb_target)
        t_obs = abs(out["params"][wcb_target]["t"])
        other_idx = [i for i in range(K) if i != t_idx]
        if other_idx:
            Xo = X_dm[:, other_idx]
            b_r = np.linalg.lstsq(Xo, y_dm, rcond=None)[0]
            yhat_r = Xo @ b_r
            e_r = y_dm - yhat_r
        else:
            yhat_r = np.zeros_like(y_dm)
            e_r = y_dm.copy()

        # Precompute cluster & FE slices for exact LSDV-equivalent vectorized WCB
        cl_slices = [np.where(inv_cl == c_i)[0] for c_i in range(G)]
        _, inv_fe = np.unique(sub[fe_col].to_numpy(), return_inverse=True)
        fe_slices = [np.where(inv_fe == f_i)[0] for f_i in range(M)]
        v_obs = X_dm @ XtX_inv[t_idx, :]  # (N,)
        rng = np.random.default_rng(seed)
        signs = rng.choice([-1.0, 1.0], size=(wcb_B, G))
        exceed = 0
        batch = 200
        for b0 in range(0, wcb_B, batch):
            b1 = min(b0 + batch, wcb_B)
            S = signs[b0:b1, :]  # (B_sub, G)
            W_obs = S[:, inv_cl]  # (B_sub, N)
            # Exact projection M_fe @ Y_star (critical whenever FE cells are not nested in clusters!)
            Y_star_dm = yhat_r[None, :] + W_obs * e_r[None, :]  # (B_sub, N)
            for f_idx in fe_slices:
                Y_star_dm[:, f_idx] -= Y_star_dm[:, f_idx].mean(axis=1, keepdims=True)
            B_star = (XtX_inv @ (X_dm.T @ Y_star_dm.T)).T  # (B_sub, K)
            R_star = Y_star_dm - B_star @ X_dm.T  # (B_sub, N)
            VR = R_star * v_obs[None, :]  # (B_sub, N)
            var_t = np.zeros(b1 - b0, dtype=float)
            for idx_arr in cl_slices:
                sc_g = VR[:, idx_arr].sum(axis=1)
                var_t += sc_g * sc_g
            se_star = np.sqrt(np.maximum(cr1_scale * var_t, 1e-18))
            t_star = np.abs(B_star[:, t_idx] / se_star)
            exceed += int(np.sum(t_star >= t_obs))
        out["params"][wcb_target]["p_wcb"] = float((exceed + 1) / (wcb_B + 1))
        out["params"][wcb_target]["wcb_B"] = int(wcb_B)
    return out


def fe_ppml_cr1(
    df: pd.DataFrame,
    y_col: str,
    x_cols: list[str],
    fe_col: str,
    cluster_col: str,
) -> dict:
    """Exact Chen-Roth (2024) scale-invariant Poisson PPML with FE dummies & cluster-robust SEs."""
    cols = list(dict.fromkeys([y_col] + list(x_cols) + [fe_col, cluster_col]))
    sub = df[cols].dropna().copy()
    sub = sub[sub[y_col] >= 0].copy()
    sub = sub[sub.groupby(fe_col)[y_col].transform("sum") > 0].copy()
    vc = sub[fe_col].value_counts()
    sub = sub[sub[fe_col].isin(vc[vc >= 2].index)].copy()
    if len(sub) < 25:
        return {"n": len(sub), "error": "too_few"}

    g = sub.groupby(fe_col)
    keep = [c for c in x_cols if (sub[c] - g[c].transform("mean")).std() > 1e-10]
    if not keep:
        return {"n": len(sub), "error": "collinear"}

    fe_d = pd.get_dummies(sub[fe_col], prefix="fe", drop_first=False, dtype=float)
    X = pd.concat([sub[keep].astype(float), fe_d], axis=1)
    y = sub[y_col].astype(float)
    try:
        glm = sm.GLM(y, X, family=sm.families.Poisson()).fit(
            cov_type="cluster",
            cov_kwds={"groups": sub[cluster_col], "use_correction": True},
            maxiter=120,
        )
        if not bool(glm.converged):
            return {"n": len(sub), "converged": False, "error": "non_converged"}
        G = int(sub[cluster_col].nunique())
        out: dict = {
            "n": len(sub),
            "G": G,
            "M_fe": int(sub[fe_col].nunique()),
            "converged": True,
            "params": {},
        }
        for c in keep:
            b = float(glm.params[c])
            se = float(glm.bse[c])
            tval = b / se if se > 0 else float("nan")
            pval = float(2.0 * stats.t.sf(abs(tval), df=max(G - 1, 1)))
            out["params"][c] = {
                "beta": b,
                "pct": float(100.0 * (np.exp(b) - 1.0)),
                "se": se,
                "t": float(tval),
                "p": pval,
            }
        return out
    except (ValueError, np.linalg.LinAlgError, RuntimeError) as exc:
        return {"n": len(sub), "error": str(exc)}


def perm_test_within_fe(
    df: pd.DataFrame,
    y_col: str,
    treat_col: str,
    fe_col: str,
    B: int = 2000,
    seed: int = 42,
) -> dict:
    """Exact within-FE-cell randomization inference permutation test."""
    sub = df[[y_col, treat_col, fe_col]].dropna().copy()
    vc = sub[fe_col].value_counts()
    sub = sub[sub[fe_col].isin(vc[vc >= 2].index)].copy()
    if len(sub) < 20:
        return {"obs": None, "p_perm": None, "z_perm": None, "B": B}
    g = sub.groupby(fe_col)
    y_dm = (sub[y_col] - g[y_col].transform("mean")).to_numpy(dtype=float)
    t_raw = sub[treat_col].to_numpy(dtype=float)
    t_dm = (sub[treat_col] - g[treat_col].transform("mean")).to_numpy(dtype=float)
    denom = float(np.dot(t_dm, t_dm))
    if denom < 1e-12:
        return {"obs": None, "p_perm": None, "z_perm": None, "B": B}
    obs = float(np.dot(t_dm, y_dm) / denom)
    pos_map = {orig: i for i, orig in enumerate(sub.index)}
    grp_pos = [np.array([pos_map[x] for x in idx.to_numpy()], dtype=int) for _, idx in sub.groupby(fe_col).groups.items()]
    t_means = t_raw - t_dm
    rng = np.random.default_rng(seed)
    nulls = np.empty(B, dtype=float)
    for b in range(B):
        tp = t_raw.copy()
        for gp in grp_pos:
            tp[gp] = rng.permutation(tp[gp])
        nulls[b] = float(np.dot(tp - t_means, y_dm) / denom)
    p_perm = float((np.sum(np.abs(nulls) >= abs(obs)) + 1) / (B + 1))
    sd = float(np.std(nulls))
    z_perm = float((obs - np.mean(nulls)) / sd) if sd > 0 else float("nan")
    return {"obs": obs, "p_perm": p_perm, "z_perm": z_perm, "B": B}


def compute_tost(beta: float, se: float, df_t: int, bounds: tuple[float, ...] = (0.15, 0.20)) -> dict:
    """Lakens (2017) Two One-Sided Tests (TOST) equivalence p-values."""
    out = {}
    if not (np.isfinite(beta) and np.isfinite(se) and se > 0):
        return out
    for bnd in bounds:
        t_hi = (beta - bnd) / se
        t_lo = (beta + bnd) / se
        p_tost = float(max(stats.t.cdf(t_hi, df=max(df_t, 1)), stats.t.sf(t_lo, df=max(df_t, 1))))
        out[f"tost_pm{round(bnd * 100)}"] = p_tost
    return out


def add_within_cell_ranks(df: pd.DataFrame, cols: list[str], cell_col: str) -> pd.DataFrame:
    out = df.copy()
    for c in cols:
        if c not in out.columns:
            continue
        out[f"rank_{c}"] = out.groupby(cell_col)[c].rank(pct=True)
        q90 = out.groupby(cell_col)[c].transform(lambda s: s.quantile(0.90))
        out[f"top10_{c}"] = ((out[c] >= q90) & (out[c] > 0)).astype(float)
    return out


def main() -> None:
    t0 = time.time()
    print("=== STEP 4: PILLARS 1 & 2 (INTRINSIC REVISION NORMS, CITATIONS & LIVE READER ATTENTION) ===", flush=True)
    RES_DIR.mkdir(parents=True, exist_ok=True)
    TBL_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_DIR / "h6f_boost_v1_panel.csv.gz").copy()
    df["v1_dt"] = pd.to_datetime(df["v1_date"], errors="coerce")
    df["fin_dt"] = pd.to_datetime(df["fin_date"], errors="coerce")
    geo_cols = pd.DataFrame(
        {
            "is_CN": df["countries"].fillna("").str.contains(r"\bCN\b", regex=True).astype(float),
            "is_US": df["countries"].fillna("").str.contains(r"\bUS\b", regex=True).astype(float),
            "is_GB": df["countries"].fillna("").str.contains(r"\bGB\b", regex=True).astype(float),
        },
        index=df.index,
    )
    df = pd.concat([df, geo_cols], axis=1)

    # =========================================================================
    # PILLAR 1: COMPLETE v1 -> VoR TRANSITION MATRIX & CLARIVATE ESCI SOLID-CLIFF TEST
    # =========================================================================
    mat = df[(df["v1_dt"] >= "2023-01-01") & (df["v1_dt"] <= "2024-12-31") & df["v1_str_min"].notna()].copy()
    mat = add_within_cell_ranks(mat, ["oa_post_v1_cites", "cr_cites", "pv_total", "dl_total", "pv_post_vor", "dl_post_vor"], "subj_v1q")

    for c in ["oa_post_v1_cites", "oa_elife_cites", "cr_cites", "cr_cites_sum", "pv_total", "dl_total", "pv_post_vor", "dl_post_vor"]:
        if c in mat.columns and mat[c].notna().sum() > 20:
            q99 = float(mat[c].quantile(0.99))
            mat[f"{c}_w99"] = mat[c].clip(upper=q99)

    print(f"[Pillar 1] Full v1 census={len(df):,} | Mature 2023-2024 v1 cohort={len(mat):,} (live metrics={int((mat['has_metrics']==1).sum()):,})", flush=True)

    trans_mature: dict = {}
    trans_all_4541: dict = {}
    tiers = [
        ("v1_Incomp_Inad", lambda d: d["v1_str_min"] <= 2),
        ("v1_Solid", lambda d: d["v1_str_min"] == 3),
        ("v1_Convincing", lambda d: d["v1_str_min"] == 4),
        ("v1_Compel_Excep", lambda d: d["v1_str_min"] >= 5),
    ]

    for lbl, fn in tiers:
        g = mat[fn(mat)]
        vg = g[g["is_vor"] == 1]
        up = vg[vg["str_upgraded"] == 1]
        un = vg[vg["str_upgraded"] == 0]
        rp = g[g["is_vor"] == 0]
        trans_mature[lbl] = {
            "n_total": len(g),
            "n_vor": len(vg),
            "pct_vor": float(100.0 * len(vg) / max(len(g), 1)),
            "n_vor_upgraded": len(up),
            "pct_all_upgraded_vor": float(100.0 * len(up) / max(len(g), 1)),
            "pct_vor_upgraded": float(100.0 * len(up) / max(len(vg), 1)),
            "n_vor_upgraded_to_solid": int(vg["str_upgraded_to_solid"].sum()),
            "pct_vor_upgraded_to_solid": float(100.0 * vg["str_upgraded_to_solid"].mean()) if len(vg) else 0.0,
            "n_vor_unchanged": len(un),
            "n_rp_only": len(rp),
            "mean_rev_lag_up": float(up["rev_lag_days"].mean()) if len(up) else 0.0,
            "med_rev_lag_up": float(up["rev_lag_days"].median()) if len(up) else 0.0,
            "mean_rev_lag_unch": float(un["rev_lag_days"].mean()) if len(un) else 0.0,
            "mean_oa_post_up": float(up["oa_post_v1_cites"].mean()) if len(up) else 0.0,
            "mean_oa_post_unch": float(un["oa_post_v1_cites"].mean()) if len(un) else 0.0,
            "mean_cr_up": float(up["cr_cites"].mean()) if len(up) else 0.0,
            "mean_cr_unch": float(un["cr_cites"].mean()) if len(un) else 0.0,
            "mean_pv_up": float(up["pv_total"].mean()) if up["pv_total"].notna().any() else 0.0,
            "med_pv_up": float(up["pv_total"].median()) if up["pv_total"].notna().any() else 0.0,
            "mean_pv_unch": float(un["pv_total"].mean()) if un["pv_total"].notna().any() else 0.0,
            "med_pv_unch": float(un["pv_total"].median()) if un["pv_total"].notna().any() else 0.0,
            "mean_pv_rp": float(rp["pv_total"].mean()) if rp["pv_total"].notna().any() else 0.0,
            "mean_dl_up": float(up["dl_total"].mean()) if up["dl_total"].notna().any() else 0.0,
            "med_dl_up": float(up["dl_total"].median()) if up["dl_total"].notna().any() else 0.0,
            "mean_dl_unch": float(un["dl_total"].mean()) if un["dl_total"].notna().any() else 0.0,
            "med_dl_unch": float(un["dl_total"].median()) if un["dl_total"].notna().any() else 0.0,
            "mean_dl_rp": float(rp["dl_total"].mean()) if rp["dl_total"].notna().any() else 0.0,
        }
        ga = df[df["v1_str_min"].notna() & fn(df)]
        vga = ga[ga["is_vor"] == 1]
        trans_all_4541[lbl] = {
            "n_total": len(ga),
            "n_vor": len(vga),
            "pct_vor": float(100.0 * len(vga) / max(len(ga), 1)),
            "pct_vor_upgraded": float(100.0 * vga["str_upgraded"].mean()) if len(vga) else 0.0,
        }
        tm = trans_mature[lbl]
        print(
            f"  {lbl:16s}: N={tm['n_total']:4d} | VoR={tm['pct_vor']:5.1f}% | Up/VoR={tm['pct_vor_upgraded']:5.1f}% | "
            f"OA_post Up={tm['mean_oa_post_up']:5.2f} vs Unch={tm['mean_oa_post_unch']:5.2f} | "
            f"PV Up={tm['mean_pv_up']:6.0f} vs Unch={tm['mean_pv_unch']:6.0f} (RP={tm['mean_pv_rp']:5.0f}) | "
            f"DL Up={tm['mean_dl_up']:5.0f} vs Unch={tm['mean_dl_unch']:5.0f}",
            flush=True,
        )

    # Clarivate Dec 2024 ESCI Solid-Threshold Natural Experiment (365d, 450d primary, 540d windows + clean 2023-only pre!)
    esci_results: dict = {}
    for win_days, max_v1_dt in [(365, "2025-10-01"), (450, "2025-07-01"), (540, "2025-04-01")]:
        d_rev = df[(df["v1_dt"] >= "2023-04-01") & (df["v1_dt"] <= max_v1_dt) & (df["v1_str_min"] <= 2)].copy()
        d_rev["vor_win"] = ((d_rev["is_vor"] == 1) & (d_rev["rev_lag_days"] <= win_days)).astype(float)
        d_rev["up_win"] = ((d_rev["vor_win"] == 1) & (d_rev["str_upgraded_to_solid"] == 1)).astype(float)
        d_rev["unrev_win"] = ((d_rev["vor_win"] == 1) & (d_rev["str_upgraded_to_solid"] == 0)).astype(float)
        d_rev["post_esci"] = (d_rev["v1_dt"] >= "2024-10-01").astype(float)
        d_rev["post_x_CN"] = d_rev["post_esci"] * d_rev["is_CN"]
        pre_e = d_rev[d_rev["v1_dt"] < "2024-07-01"]
        post_e = d_rev[d_rev["v1_dt"] >= "2024-10-01"]
        vors_win = d_rev[d_rev["vor_win"] == 1].copy()
        vors_donut = d_rev[(d_rev["vor_win"] == 1) & ((d_rev["v1_dt"] < "2024-07-01") | (d_rev["v1_dt"] >= "2024-10-01"))].copy()
        vors_2023_only = d_rev[(d_rev["vor_win"] == 1) & ((d_rev["v1_dt"] < "2024-01-01") | (d_rev["v1_dt"] >= "2024-10-01"))].copy()
        esci_results[f"win_{win_days}d"] = {
            "window_days": win_days,
            "max_v1_date": max_v1_dt,
            "pre_n": len(pre_e),
            "pre_vor_pct": float(100.0 * pre_e["vor_win"].mean()),
            "pre_up_all_pct": float(100.0 * pre_e["up_win"].mean()),
            "pre_up_among_vor_pct": float(100.0 * pre_e[pre_e["vor_win"] == 1]["str_upgraded_to_solid"].mean()) if (pre_e["vor_win"] == 1).any() else 0.0,
            "pre_unrev_pct": float(100.0 * pre_e["unrev_win"].mean()),
            "post_n": len(post_e),
            "post_vor_pct": float(100.0 * post_e["vor_win"].mean()),
            "post_up_all_pct": float(100.0 * post_e["up_win"].mean()),
            "post_up_among_vor_pct": float(100.0 * post_e[post_e["vor_win"] == 1]["str_upgraded_to_solid"].mean()) if (post_e["vor_win"] == 1).any() else 0.0,
            "post_unrev_pct": float(100.0 * post_e["unrev_win"].mean()),
            "fe_up_among_vors": fe_ols_cr1(vors_win, "str_upgraded_to_solid", ["post_esci", "v1_sig_rank"], "primary_subject", "primary_subject", wcb_target="post_esci"),
            "fe_up_among_vors_donut": fe_ols_cr1(vors_donut, "str_upgraded_to_solid", ["post_esci", "v1_sig_rank"], "primary_subject", "primary_subject", wcb_target="post_esci"),
            "fe_up_among_vors_2023_only_pre": fe_ols_cr1(vors_2023_only, "str_upgraded_to_solid", ["post_esci", "v1_sig_rank"], "primary_subject", "primary_subject", wcb_target="post_esci"),
            "fe_up_all_incomp": fe_ols_cr1(d_rev, "up_win", ["post_esci", "v1_sig_rank"], "primary_subject", "primary_subject", wcb_target="post_esci"),
            "fe_up_among_vors_cn_het": fe_ols_cr1(vors_win, "str_upgraded_to_solid", ["post_esci", "is_CN", "post_x_CN", "v1_sig_rank"], "primary_subject", "primary_subject", wcb_target="post_x_CN"),
        }
    e450 = esci_results["win_450d"]
    p450 = e450["fe_up_among_vors"]["params"]["post_esci"]
    p450_d = e450["fe_up_among_vors_donut"]["params"]["post_esci"]
    p450_23 = e450["fe_up_among_vors_2023_only_pre"]["params"]["post_esci"]
    print(
        f"[ESCI 450d Natural Experiment] Pre(n={e450['pre_n']}): Up/VoR={e450['pre_up_among_vor_pct']:.1f}% -> "
        f"Post(n={e450['post_n']}): Up/VoR={e450['post_up_among_vor_pct']:.1f}% | "
        f"Full FE={100*p450['beta']:+.2f} pp (p_WCB={p450.get('p_wcb', np.nan):.4f}) | "
        f"Donut FE={100*p450_d['beta']:+.2f} pp (p_WCB={p450_d.get('p_wcb', np.nan):.4f}) | "
        f"2023-Only Pre={100*p450_23['beta']:+.2f} pp (p_WCB={p450_23.get('p_wcb', np.nan):.4f})",
        flush=True,
    )

    # =========================================================================
    # PILLAR 2A: FIRST-IMPRESSION v1 ASSESSMENT GRADIENT (CITATIONS + PAGE-VIEWS + DOWNLOADS + VoR LOCK-IN)
    # =========================================================================
    mat["v1_incomp_d"] = (mat["v1_str_min"] <= 2).astype(float)
    mat["v1_conv_d"] = (mat["v1_str_min"] == 4).astype(float)
    mat["v1_comp_d"] = (mat["v1_str_min"] >= 5).astype(float)
    mat["v1_sig_imp"] = ((mat["v1_sig_rank"] >= 3.0) & (mat["v1_sig_rank"] < 4.0)).astype(float)
    mat["v1_sig_fund"] = (mat["v1_sig_rank"] >= 4.0).astype(float)

    mat["fin_incomp_d"] = (mat["fin_str_min"] <= 2).astype(float)
    mat["fin_conv_d"] = (mat["fin_str_min"] == 4).astype(float)
    mat["fin_comp_d"] = (mat["fin_str_min"] >= 5).astype(float)
    mat["fin_sig_imp"] = ((mat["fin_sig_rank"] >= 3.0) & (mat["fin_sig_rank"] < 4.0)).astype(float)
    mat["fin_sig_fund"] = (mat["fin_sig_rank"] >= 4.0).astype(float)

    x_grad = ["v1_incomp_d", "v1_conv_d", "v1_comp_d", "v1_sig_imp", "v1_sig_fund", "v1_age_days", "log_authors", "log1p_pre_before_v1"]
    x_grad_flawed = ["fin_incomp_d", "fin_conv_d", "fin_comp_d", "fin_sig_imp", "fin_sig_fund", "log_authors", "log1p_pre_before_v1"]

    mat_v = mat[mat["is_vor"] == 1].copy()
    mat_v["upgraded_incomp_to_solid"] = ((mat_v["v1_str_min"] <= 2) & (mat_v["fin_str_min"] >= 3)).astype(float)
    mat_cm = mat[mat["has_complete_monthly_metrics"] == 1].copy()

    gradient_res = {
        # All mature v1 papers (VoR + RP-only): VoR lock-in + Citations + Reader Views + Downloads
        "all_v1_vor_lockin_ols": fe_ols_cr1(mat, "is_vor", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "all_v1_oa_post_ppml": fe_ppml_cr1(mat, "oa_post_v1_cites", x_grad, "subj_v1q", "primary_subject"),
        "all_v1_pv_total_ppml": fe_ppml_cr1(mat[mat["has_metrics"] == 1], "pv_total", x_grad, "subj_v1q", "primary_subject"),
        "all_v1_dl_total_ppml": fe_ppml_cr1(mat[mat["has_metrics"] == 1], "dl_total", x_grad, "subj_v1q", "primary_subject"),
        "all_v1_pv_total_ols": fe_ols_cr1(mat[mat["has_metrics"] == 1], "log1p_pv_total", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "all_v1_dl_total_ols": fe_ols_cr1(mat[mat["has_metrics"] == 1], "log1p_dl_total", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        # Untruncated first-3m traffic (strictly v1 >= 2023-11!)
        "all_v1_pv_first3m_ols": fe_ols_cr1(mat_cm, "log1p_pv_first_3m", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "all_v1_dl_first3m_ols": fe_ols_cr1(mat_cm, "log1p_dl_first_3m", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        # Mature VoRs (True v1-date + v1-rating, Subject-clustered G=18!)
        "vor_true_v1_oa_post_ppml": fe_ppml_cr1(mat_v, "oa_post_v1_cites", x_grad, "subj_v1q", "primary_subject"),
        "vor_true_v1_oa_post_ols": fe_ols_cr1(mat_v, "log1p_oa_post_v1", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "vor_true_v1_oa_post_rank": fe_ols_cr1(mat_v, "rank_oa_post_v1_cites", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "vor_true_v1_oa_post_top10": fe_ols_cr1(mat_v, "top10_oa_post_v1_cites", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "vor_true_v1_cr_ppml": fe_ppml_cr1(mat_v, "cr_cites", x_grad, "subj_v1q", "primary_subject"),
        "vor_true_v1_pv_ppml": fe_ppml_cr1(mat_v[mat_v["has_metrics"] == 1], "pv_total", x_grad, "subj_v1q", "primary_subject"),
        "vor_true_v1_pv_ols": fe_ols_cr1(mat_v[mat_v["has_metrics"] == 1], "log1p_pv_total", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "vor_true_v1_pv_rank": fe_ols_cr1(mat_v[mat_v["has_metrics"] == 1], "rank_pv_total", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "vor_true_v1_dl_ppml": fe_ppml_cr1(mat_v[mat_v["has_metrics"] == 1], "dl_total", x_grad, "subj_v1q", "primary_subject"),
        "vor_true_v1_dl_ols": fe_ols_cr1(mat_v[mat_v["has_metrics"] == 1], "log1p_dl_total", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        "vor_true_v1_dl_rank": fe_ols_cr1(mat_v[mat_v["has_metrics"] == 1], "rank_dl_total", x_grad, "subj_v1q", "primary_subject", wcb_target="v1_incomp_d"),
        # Split v1_Incomplete VoRs into Unrevised vs Upgraded-to-Solid vs Always-Solid baseline!
        "vor_split_incomp_oa_ppml": fe_ppml_cr1(
            mat_v, "oa_post_v1_cites",
            ["fin_incomp_d", "upgraded_incomp_to_solid", "v1_conv_d", "v1_comp_d", "v1_sig_imp", "v1_sig_fund", "v1_age_days", "log_authors", "log1p_pre_before_v1"],
            "subj_v1q", "primary_subject",
        ),
        "vor_split_incomp_pv_ppml": fe_ppml_cr1(
            mat_v[mat_v["has_metrics"] == 1], "pv_total",
            ["fin_incomp_d", "upgraded_incomp_to_solid", "v1_conv_d", "v1_comp_d", "v1_sig_imp", "v1_sig_fund", "v1_age_days", "log_authors", "log1p_pre_before_v1"],
            "subj_v1q", "primary_subject",
        ),
        "vor_split_incomp_dl_ppml": fe_ppml_cr1(
            mat_v[mat_v["has_metrics"] == 1], "dl_total",
            ["fin_incomp_d", "upgraded_incomp_to_solid", "v1_conv_d", "v1_comp_d", "v1_sig_imp", "v1_sig_fund", "v1_age_days", "log_authors", "log1p_pre_before_v1"],
            "subj_v1q", "primary_subject",
        ),
        # Flawed VoR-date + Final-rating Methodological Autopsy (exact same VoRs!)
        "vor_flawed_vor_oa_post_ppml": fe_ppml_cr1(mat_v, "oa_post_v1_cites", x_grad_flawed, "subj_finq", "primary_subject"),
        "vor_flawed_vor_pv_ppml": fe_ppml_cr1(mat_v[mat_v["has_metrics"] == 1], "pv_total", x_grad_flawed, "subj_finq", "primary_subject"),
        "vor_flawed_vor_dl_ppml": fe_ppml_cr1(mat_v[mat_v["has_metrics"] == 1], "dl_total", x_grad_flawed, "subj_finq", "primary_subject"),
    }

    # 18-Subject Leave-One-Subject-Out (LOSO) on v1_incomp_d for Citations, Page-Views, and Downloads!
    loso_grad: dict = {"oa_post_v1_cites": [], "pv_total": [], "dl_total": []}
    for subj in sorted(mat_v["primary_subject"].unique()):
        sub_l = mat_v[mat_v["primary_subject"] != subj]
        for yk in ("oa_post_v1_cites", "pv_total", "dl_total"):
            sl = sub_l[sub_l["has_metrics"] == 1] if yk != "oa_post_v1_cites" else sub_l
            r_l = fe_ppml_cr1(sl, yk, x_grad, "subj_v1q", "primary_subject")
            if "params" in r_l and "v1_incomp_d" in r_l["params"]:
                p = r_l["params"]["v1_incomp_d"]
                loso_grad[yk].append({"dropped_subject": subj, "beta": p["beta"], "pct": p["pct"], "t": p["t"]})

    print("\n[Pillar 2A: First-Impression v1 Gradient & VoR-Date Autopsy (VoRs, Subject-Clustered G=18)]:", flush=True)
    for lbl, rkey, tkey in [
        ("TRUE v1 -> OA Post-v1 Cites (PPML)", "vor_true_v1_oa_post_ppml", "v1_incomp_d"),
        ("FLAWED VoR -> OA Post-v1 Cites (PPML)", "vor_flawed_vor_oa_post_ppml", "fin_incomp_d"),
        ("TRUE v1 -> eLife Page-Views (PPML)", "vor_true_v1_pv_ppml", "v1_incomp_d"),
        ("FLAWED VoR -> eLife Page-Views (PPML)", "vor_flawed_vor_pv_ppml", "fin_incomp_d"),
        ("TRUE v1 -> eLife Downloads (PPML)", "vor_true_v1_dl_ppml", "v1_incomp_d"),
        ("FLAWED VoR -> eLife Downloads (PPML)", "vor_flawed_vor_dl_ppml", "fin_incomp_d"),
    ]:
        p = gradient_res[rkey]["params"][tkey]
        print(f"  {lbl:40s}: beta={p['beta']:+.4f} ({p['pct']:+5.1f}%, t={p['t']:+.2f}, p={p['p']:.4g})", flush=True)

    for ylbl, rkey in [("OA_Post", "vor_true_v1_oa_post_ppml"), ("PV_Tot", "vor_true_v1_pv_ppml"), ("DL_Tot", "vor_true_v1_dl_ppml")]:
        pr = gradient_res[rkey]["params"]
        print(
            f"  [{ylbl:7s} full gradient] Incomp={pr['v1_incomp_d']['pct']:+5.1f}% (p={pr['v1_incomp_d']['p']:.3g}) | "
            f"Conv={pr['v1_conv_d']['pct']:+5.1f}% (p={pr['v1_conv_d']['p']:.3g}) | "
            f"Comp={pr['v1_comp_d']['pct']:+5.1f}% (p={pr['v1_comp_d']['p']:.3g}) | "
            f"SigImp={pr['v1_sig_imp']['pct']:+5.1f}% (p={pr['v1_sig_imp']['p']:.3g}) | "
            f"SigFund={pr['v1_sig_fund']['pct']:+5.1f}% (p={pr['v1_sig_fund']['p']:.3g})",
            flush=True,
        )

    # =========================================================================
    # PILLAR 2B: REVISION-UPGRADE PAYOFF TEST — CITATIONS + UNTRUNCATED LIVE READER ATTENTION!
    # =========================================================================
    covs = ["v1_sig_rank", "v1_age_days", "log_authors", "log1p_pre_before_v1"]

    # First: VoR conversion vs RP-only attention premium inside v1_Incomplete (N = 964)
    inc_all = mat[mat["v1_str_min"] <= 2].copy()
    vor_vs_rp_incomp = {
        "n_total": len(inc_all),
        "n_vor": int((inc_all["is_vor"] == 1).sum()),
        "n_rp_only": int((inc_all["is_vor"] == 0).sum()),
        "ppml_oa_post_v1": fe_ppml_cr1(inc_all, "oa_post_v1_cites", ["is_vor"] + covs, "subj_v1q", "primary_subject"),
        "ppml_pv_total": fe_ppml_cr1(inc_all[inc_all["has_metrics"] == 1], "pv_total", ["is_vor"] + covs, "subj_v1q", "primary_subject"),
        "ppml_dl_total": fe_ppml_cr1(inc_all[inc_all["has_metrics"] == 1], "dl_total", ["is_vor"] + covs, "subj_v1q", "primary_subject"),
        "ols_log1p_pv_total": fe_ols_cr1(inc_all[inc_all["has_metrics"] == 1], "log1p_pv_total", ["is_vor"] + covs, "subj_v1q", "primary_subject", wcb_target="is_vor"),
        "ols_log1p_dl_total": fe_ols_cr1(inc_all[inc_all["has_metrics"] == 1], "log1p_dl_total", ["is_vor"] + covs, "subj_v1q", "primary_subject", wcb_target="is_vor"),
    }

    upgrade_res: dict = {}
    for grp_lbl, sub_raw, tvar in [
        ("v1_Incomp_VoRs", mat[(mat["v1_str_min"] <= 2) & (mat["is_vor"] == 1)], "str_upgraded_to_solid"),
        ("v1_Solid_VoRs", mat[(mat["v1_str_min"] == 3) & (mat["is_vor"] == 1)], "str_upgraded"),
        ("v1_IncompOrSolid_VoRs", mat[(mat["v1_str_min"] <= 3) & (mat["is_vor"] == 1)], "str_upgraded"),
    ]:
        sub = sub_raw.copy()
        sub["v1_incomp_ctrl"] = (sub["v1_str_min"] <= 2).astype(float)
        sub["post_dec2024_vor"] = (sub["fin_dt"] >= "2024-12-01").astype(float)
        x_base = [tvar] + covs + (["v1_incomp_ctrl"] if "OrSolid" in grp_lbl else [])
        x_post_vor = x_base + ["n_months_post_vor"]
        x_with_lag = x_base + ["rev_lag_days"]
        x_with_ver = x_base + ["cr_n_versions"]
        x_ev = [tvar, "v1_sig_rank", "v1_age_days", "log_authors", "rev_lag_days"] + (["v1_incomp_ctrl"] if "OrSolid" in grp_lbl else [])

        # Lifetime totals (untruncated for 100% of mature papers)
        sub_m = sub[sub["has_metrics"] == 1].copy()
        sub_m_nonaledi = sub_m[~sub_m["eid"].astype(str).isin(["89106", "89102"])].copy()
        sub_nonaledi = sub[~sub["eid"].astype(str).isin(["89106", "89102"])].copy()

        # STRICTLY UNTRUNCATED monthly telemetry cohorts:
        # (a) Complete monthly v1 >= 2023-11 (zero rolling-window left-truncation!)
        sub_cm = sub[sub["has_complete_monthly_metrics"] == 1].copy()
        # (b) Clean local VoR event study (fin_m in 2024-03..2026-04, lag >= 4m -> zero left- or right-truncation!)
        sub_ev = sub[sub["has_clean_vor_ev"] == 1].copy()

        # Raw uniform VoR release-month spikes (Upgraded vs Unchanged)
        ev_raw_summary: dict = {}
        if len(sub_ev) >= 20:
            for yk in ("dlog_pv_ev_m0", "dlog_pv_ev_p13", "dlog_pv_ev_p16", "dlog_dl_ev_m0", "dlog_dl_ev_p13", "dlog_dl_ev_p16"):
                ev_raw_summary[yk] = {
                    "upgraded_mean": float(sub_ev.loc[sub_ev[tvar] == 1, yk].mean()),
                    "unchanged_mean": float(sub_ev.loc[sub_ev[tvar] == 0, yk].mean()),
                }

        # Month-by-month local event study around VoR month (t = -3..+6)
        ev_monthly_pv: dict = {}
        ev_monthly_dl: dict = {}
        if len(sub_ev) >= 30:
            for k in range(-3, 7):
                r_p = fe_ols_cr1(sub_ev, f"dlog_pv_ev_t{k}", x_ev, "subj_v1q", "primary_subject")
                r_d = fe_ols_cr1(sub_ev, f"dlog_dl_ev_t{k}", x_ev, "subj_v1q", "primary_subject")
                if "params" in r_p and tvar in r_p["params"]:
                    ev_monthly_pv[f"t{k:+d}"] = r_p["params"][tvar]
                if "params" in r_d and tvar in r_d["params"]:
                    ev_monthly_dl[f"t{k:+d}"] = r_d["params"][tvar]

        # Pre-Dec-2024 vs Post-Dec-2024 VoR ESCI mechanism split on local VoR event study
        ev_pre_esci = sub_ev[sub_ev["post_dec2024_vor"] == 0].copy()
        ev_post_esci = sub_ev[sub_ev["post_dec2024_vor"] == 1].copy()

        res_g: dict = {
            "n_total": len(sub),
            "n_with_metrics": len(sub_m),
            "n_complete_monthly_ge_2023_11": len(sub_cm),
            "n_clean_vor_ev": len(sub_ev),
            "n_upgraded": int(sub[tvar].sum()),
            "n_unchanged": int((sub[tvar] == 0).sum()),
            "mean_cr_n_versions_up": float(sub_cm.loc[sub_cm[tvar] == 1, "cr_n_versions"].mean()) if len(sub_cm) else float("nan"),
            "mean_cr_n_versions_unch": float(sub_cm.loc[sub_cm[tvar] == 0, "cr_n_versions"].mean()) if len(sub_cm) else float("nan"),
            # --- Citations (Subject-clustered G=18 primary + subj_v1q sensitivity) ---
            "ppml_oa_post_v1": fe_ppml_cr1(sub, "oa_post_v1_cites", x_base, "subj_v1q", "primary_subject"),
            "ppml_oa_post_v1_cell_cl": fe_ppml_cr1(sub, "oa_post_v1_cites", x_base, "subj_v1q", "subj_v1q"),
            "ppml_oa_post_v1_nonaledi": fe_ppml_cr1(sub_nonaledi, "oa_post_v1_cites", x_base, "subj_v1q", "primary_subject"),
            "ppml_oa_post_v1_w99": fe_ppml_cr1(sub, "oa_post_v1_cites_w99", x_base, "subj_v1q", "primary_subject"),
            "ppml_oa_total": fe_ppml_cr1(sub, "oa_elife_cites", x_base, "subj_v1q", "primary_subject"),
            "ppml_cr_max": fe_ppml_cr1(sub, "cr_cites", x_base, "subj_v1q", "primary_subject"),
            "ppml_cr_sum": fe_ppml_cr1(sub, "cr_cites_sum", x_base, "subj_v1q", "primary_subject"),
            "ols_log1p_oa_post_v1": fe_ols_cr1(sub, "log1p_oa_post_v1", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_log1p_cr": fe_ols_cr1(sub, "log1p_cr", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_rank_oa_post_v1": fe_ols_cr1(sub, "rank_oa_post_v1_cites", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_top10_oa_post_v1": fe_ols_cr1(sub, "top10_oa_post_v1_cites", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            # --- Untruncated Lifetime Cumulative Reader Totals (totalValue, N=766 inside FE) ---
            "ppml_pv_total": fe_ppml_cr1(sub_m, "pv_total", x_base, "subj_v1q", "primary_subject"),
            "ppml_pv_total_w99": fe_ppml_cr1(sub_m, "pv_total_w99", x_base, "subj_v1q", "primary_subject"),
            "ppml_pv_total_nonaledi": fe_ppml_cr1(sub_m_nonaledi, "pv_total", x_base, "subj_v1q", "primary_subject"),
            "ols_log1p_pv_total": fe_ols_cr1(sub_m, "log1p_pv_total", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_rank_pv_total": fe_ols_cr1(sub_m, "rank_pv_total", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_rank_pv_total_cell_cl": fe_ols_cr1(sub_m, "rank_pv_total", x_base, "subj_v1q", "subj_v1q", wcb_target=tvar),
            "ppml_dl_total": fe_ppml_cr1(sub_m, "dl_total", x_base, "subj_v1q", "primary_subject"),
            "ppml_dl_total_w99": fe_ppml_cr1(sub_m, "dl_total_w99", x_base, "subj_v1q", "primary_subject"),
            "ppml_dl_total_nonaledi": fe_ppml_cr1(sub_m_nonaledi, "dl_total", x_base, "subj_v1q", "primary_subject"),
            "ols_log1p_dl_total": fe_ols_cr1(sub_m, "log1p_dl_total", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_rank_dl_total": fe_ols_cr1(sub_m, "rank_dl_total", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            # --- CLEAN UNTRUNCATED Monthly Rate DiD (strictly v1 >= 2023-11, complete months <= 2026-10!) ---
            "ols_did_log_pv_rate_clean": fe_ols_cr1(sub_cm, "delta_log_pv_rate", x_post_vor, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_did_log_pv_rate_strict_clean": fe_ols_cr1(sub_cm, "delta_log_pv_rate_strict", x_post_vor, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_did_log_dl_rate_clean": fe_ols_cr1(sub_cm, "delta_log_dl_rate", x_post_vor, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ols_did_log_dl_rate_strict_clean": fe_ols_cr1(sub_cm, "delta_log_dl_rate_strict", x_post_vor, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ppml_pv_post_vor_clean": fe_ppml_cr1(sub_cm, "pv_post_vor", x_post_vor, "subj_v1q", "primary_subject"),
            "ppml_dl_post_vor_clean": fe_ppml_cr1(sub_cm, "dl_post_vor", x_post_vor, "subj_v1q", "primary_subject"),
            # --- CLEAN UNTRUNCATED Local VoR Event Study (t = -3..+6 around exact VoR month!) ---
            "ev_raw_summary": ev_raw_summary,
            "ev_pv_m0": fe_ols_cr1(sub_ev, "dlog_pv_ev_m0", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_pv_p13": fe_ols_cr1(sub_ev, "dlog_pv_ev_p13", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_pv_p16": fe_ols_cr1(sub_ev, "dlog_pv_ev_p16", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_pv_p46": fe_ols_cr1(sub_ev, "dlog_pv_ev_p46", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_dl_m0": fe_ols_cr1(sub_ev, "dlog_dl_ev_m0", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_dl_p13": fe_ols_cr1(sub_ev, "dlog_dl_ev_p13", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_dl_p16": fe_ols_cr1(sub_ev, "dlog_dl_ev_p16", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_dl_p46": fe_ols_cr1(sub_ev, "dlog_dl_ev_p46", x_ev, "subj_v1q", "primary_subject", wcb_target=tvar),
            "ev_monthly_pv": ev_monthly_pv,
            "ev_monthly_dl": ev_monthly_dl,
            "ev_pv_p16_pre_dec2024": fe_ols_cr1(ev_pre_esci, "dlog_pv_ev_p16", [tvar, "v1_sig_rank", "log_authors", "rev_lag_days"], "primary_subject", "primary_subject", wcb_target=tvar),
            "ev_pv_p16_post_dec2024": fe_ols_cr1(ev_post_esci, "dlog_pv_ev_p16", [tvar, "v1_sig_rank", "log_authors", "rev_lag_days"], "primary_subject", "primary_subject", wcb_target=tvar),
            # --- CLEAN UNTRUNCATED Balanced 22-Month Post-v1 Trajectory (tau=0..21) & Version-Release Decomposition ---
            "traj_pv_m0_2": fe_ols_cr1(sub_cm, "log1p_pv_m0_2", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_pv_m3_11": fe_ols_cr1(sub_cm, "log1p_pv_m3_11", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_pv_m12_21": fe_ols_cr1(sub_cm, "log1p_pv_m12_21", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dlog_pv_3_11": fe_ols_cr1(sub_cm, "dlog_pv_3_11_vs_0_2", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dlog_pv_12_21": fe_ols_cr1(sub_cm, "dlog_pv_12_21_vs_0_2", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dlog_pv_3_11_ctrl_ver": fe_ols_cr1(sub_cm, "dlog_pv_3_11_vs_0_2", x_with_ver, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dlog_pv_12_21_ctrl_ver": fe_ols_cr1(sub_cm, "dlog_pv_12_21_vs_0_2", x_with_ver, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dl_m0_2": fe_ols_cr1(sub_cm, "log1p_dl_m0_2", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dl_m3_11": fe_ols_cr1(sub_cm, "log1p_dl_m3_11", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dl_m12_21": fe_ols_cr1(sub_cm, "log1p_dl_m12_21", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dlog_dl_3_11": fe_ols_cr1(sub_cm, "dlog_dl_3_11_vs_0_2", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dlog_dl_12_21": fe_ols_cr1(sub_cm, "dlog_dl_12_21_vs_0_2", x_base, "subj_v1q", "primary_subject", wcb_target=tvar),
            "traj_dlog_dl_12_21_ctrl_ver": fe_ols_cr1(sub_cm, "dlog_dl_12_21_vs_0_2", x_with_ver, "subj_v1q", "primary_subject", wcb_target=tvar),
            # --- Clean Untruncated Pre-v1 & First-3m Balance Checks + Revision Lag Control ---
            "bal_pre_v1_cites": fe_ols_cr1(sub, "log1p_pre_before_v1", [tvar, "v1_sig_rank", "v1_age_days"], "subj_v1q", "primary_subject"),
            "bal_pv_first_3m_clean": fe_ols_cr1(sub_cm, "log1p_pv_first_3m", [tvar, "v1_sig_rank", "v1_age_days", "log_authors"], "subj_v1q", "primary_subject"),
            "bal_dl_first_3m_clean": fe_ols_cr1(sub_cm, "log1p_dl_first_3m", [tvar, "v1_sig_rank", "v1_age_days", "log_authors"], "subj_v1q", "primary_subject"),
            "ols_log1p_oa_with_revlag": fe_ols_cr1(sub, "log1p_oa_post_v1", x_with_lag, "subj_v1q", "primary_subject"),
            "ols_log1p_pv_with_revlag": fe_ols_cr1(sub_m, "log1p_pv_total", x_with_lag, "subj_v1q", "primary_subject"),
            "ols_log1p_dl_with_revlag": fe_ols_cr1(sub_m, "log1p_dl_total", x_with_lag, "subj_v1q", "primary_subject"),
            # --- Within-FE Exact Permutation Tests (B=2000) ---
            "perm_log1p_oa_post_v1": perm_test_within_fe(sub, "log1p_oa_post_v1", tvar, "subj_v1q", B=2000),
            "perm_log1p_pv_total": perm_test_within_fe(sub_m, "log1p_pv_total", tvar, "subj_v1q", B=2000),
            "perm_ev_pv_p16": perm_test_within_fe(sub_ev, "dlog_pv_ev_p16", tvar, "subj_v1q", B=2000),
            "perm_ev_dl_p16": perm_test_within_fe(sub_ev, "dlog_dl_ev_p16", tvar, "subj_v1q", B=2000),
        }

        # TOST Equivalence bounds (±15% & ±20%) for key PPML and clean event-study models
        tost_map = {}
        for mk in ["ppml_oa_post_v1", "ppml_oa_total", "ppml_cr_max", "ols_log1p_pv_total", "ols_log1p_dl_total", "ev_pv_m0", "ev_pv_p16", "ev_dl_p16", "ols_did_log_pv_rate_clean"]:
            r_m = res_g[mk]
            p_m = r_m.get("params", {}).get(tvar, {})
            if p_m.get("se"):
                tost_map[mk] = compute_tost(p_m["beta"], p_m["se"], r_m.get("G", 18) - 1)
        res_g["tost"] = tost_map
        upgrade_res[grp_lbl] = res_g

        print(f"\n[Pillar 2B Untruncated Upgrade Payoff: {grp_lbl}] (N={len(sub)}, CleanMonthly={len(sub_cm)}, CleanEv={len(sub_ev)}, Up={int(sub[tvar].sum())}):", flush=True)
        for mk in [
            "ppml_oa_post_v1", "ppml_cr_max", "ols_log1p_oa_post_v1",
            "ppml_pv_total_w99", "ols_log1p_pv_total", "ols_did_log_pv_rate_clean", "ols_did_log_pv_rate_strict_clean",
            "ev_pv_m0", "ev_pv_p16", "ev_dl_m0", "ev_dl_p16",
            "traj_pv_m3_11", "traj_dlog_pv_12_21_ctrl_ver",
            "bal_pv_first_3m_clean", "bal_dl_first_3m_clean",
        ]:
            p = res_g[mk].get("params", {}).get(tvar, {})
            extra = f" | p_WCB={p['p_wcb']:.4f}" if "p_wcb" in p else ""
            pct_s = f" ({p['pct']:+5.1f}%)" if "pct" in p else ""
            print(f"  {mk:32s}: beta={p.get('beta', np.nan):+.4f}{pct_s:9s} SE={p.get('se', np.nan):.4f} t={p.get('t', np.nan):+.2f} p={p.get('p', np.nan):.4f}{extra}", flush=True)

    # =========================================================================
    # BUILD PUBLICATION CSV TABLES (ZERO NaN, UNAMBIGUOUS UNITS!)
    # =========================================================================
    # Table 1: Transition Matrix & ESCI Natural Experiment (both any-step upgrade AND Solid+ threshold!)
    t1_rows = []
    for lbl, _ in tiers:
        tm = trans_mature[lbl]
        t1_rows.append({
            "v1_strength_tier": lbl,
            "n_mature_2023_2024": tm["n_total"],
            "n_vor": tm["n_vor"],
            "vor_conversion_pct": round(tm["pct_vor"], 2),
            "n_vor_upgraded_any": tm["n_vor_upgraded"],
            "vor_upgrade_any_pct": round(tm["pct_vor_upgraded"], 2),
            "n_vor_upgraded_to_solid": tm["n_vor_upgraded_to_solid"],
            "vor_upgrade_to_solid_pct": round(tm["pct_vor_upgraded_to_solid"], 2),
            "mean_rev_lag_up_days": round(tm["mean_rev_lag_up"], 1),
            "mean_rev_lag_unch_days": round(tm["mean_rev_lag_unch"], 1),
            "mean_oa_post_up": round(tm["mean_oa_post_up"], 2),
            "mean_oa_post_unch": round(tm["mean_oa_post_unch"], 2),
            "mean_pv_up": round(tm["mean_pv_up"], 1),
            "mean_pv_unch": round(tm["mean_pv_unch"], 1),
            "mean_dl_up": round(tm["mean_dl_up"], 1),
            "mean_dl_unch": round(tm["mean_dl_unch"], 1),
        })
    t1_df = pd.DataFrame(t1_rows)
    t1_path = TBL_DIR / "table1_transition_and_esci.csv"
    t1_df.to_csv(t1_path, index=False, lineterminator="\n")

    # Table 2: Pillar 2 Gradient, VoR-Date Autopsy, and Clean Untruncated Upgrade Payoff
    t2_rows = []
    for panel_lbl, rkey, tkey, outcome_lbl in [
        ("A_True_v1_Gradient", "vor_true_v1_oa_post_ppml", "v1_incomp_d", "OA_Post_v1_Cites_PPML"),
        ("A_True_v1_Gradient", "vor_true_v1_oa_post_ppml", "v1_comp_d", "OA_Post_v1_Cites_PPML"),
        ("A_True_v1_Gradient", "vor_true_v1_pv_ppml", "v1_incomp_d", "eLife_PageViews_Total_PPML"),
        ("A_True_v1_Gradient", "vor_true_v1_pv_ppml", "v1_sig_imp", "eLife_PageViews_Total_PPML"),
        ("A_True_v1_Gradient", "vor_true_v1_dl_ppml", "v1_incomp_d", "eLife_Downloads_Total_PPML"),
        ("A_True_v1_Gradient", "vor_true_v1_dl_ppml", "v1_sig_imp", "eLife_Downloads_Total_PPML"),
        ("B_Flawed_VoR_Autopsy", "vor_flawed_vor_oa_post_ppml", "fin_incomp_d", "OA_Post_v1_Cites_PPML"),
        ("B_Flawed_VoR_Autopsy", "vor_flawed_vor_pv_ppml", "fin_incomp_d", "eLife_PageViews_Total_PPML"),
        ("B_Flawed_VoR_Autopsy", "vor_flawed_vor_dl_ppml", "fin_incomp_d", "eLife_Downloads_Total_PPML"),
    ]:
        r = gradient_res[rkey]
        p = r["params"][tkey]
        t2_rows.append({
            "panel": panel_lbl,
            "outcome": outcome_lbl,
            "term": tkey,
            "n_obs": int(r["n"]),
            "n_clusters": int(r["G"]),
            "beta": round(float(p["beta"]), 4),
            "effect_magnitude": round(float(p["pct"]), 2),
            "effect_unit": "pct",
            "se": round(float(p["se"]), 4),
            "t_stat": round(float(p["t"]), 3),
            "p_value": float(p["p"]),
            "p_wcb": float(p.get("p_wcb", p["p"])),
        })

    # Panel C: Within-v1_Incomplete Upgrade Payoff (Citations + Untruncated Live Reader Attention, G=18!)
    u_inc = upgrade_res["v1_Incomp_VoRs"]
    for mk, olbl, unit in [
        ("ppml_oa_post_v1", "OA_Post_v1_Cites_PPML", "pct"),
        ("ppml_oa_post_v1_nonaledi", "OA_Post_v1_Cites_PPML_ExNaledi", "pct"),
        ("ppml_cr_max", "Crossref_Cites_PPML", "pct"),
        ("ols_log1p_oa_post_v1", "OA_Post_v1_log1p_OLS", "pct"),
        ("ols_rank_oa_post_v1", "OA_Post_v1_PctRank_OLS", "pct_rank_pp"),
        ("ppml_pv_total", "eLife_PageViews_Total_PPML", "pct"),
        ("ppml_pv_total_w99", "eLife_PageViews_Total_W99_PPML", "pct"),
        ("ols_log1p_pv_total", "eLife_PageViews_Total_log1p_OLS", "pct"),
        ("ols_did_log_pv_rate_clean", "eLife_PageViews_CleanRateDiD_v1ge2311", "pct"),
        ("ols_did_log_pv_rate_strict_clean", "eLife_PageViews_CleanStrictRateDiD_v1ge2311", "pct"),
        ("ev_pv_m0", "eLife_PageViews_LocalVoR_Month0_DiD", "pct"),
        ("ev_pv_p16", "eLife_PageViews_LocalVoR_Post1to6m_DiD", "pct"),
        ("traj_pv_m3_11", "eLife_PageViews_22mTraj_Months3to11", "pct"),
        ("traj_dlog_pv_12_21_ctrl_ver", "eLife_PageViews_22mTraj_M12to21_CtrlVer", "pct"),
        ("ppml_dl_total", "eLife_Downloads_Total_PPML", "pct"),
        ("ppml_dl_total_w99", "eLife_Downloads_Total_W99_PPML", "pct"),
        ("ols_log1p_dl_total", "eLife_Downloads_Total_log1p_OLS", "pct"),
        ("ols_did_log_dl_rate_clean", "eLife_Downloads_CleanRateDiD_v1ge2311", "pct"),
        ("ev_dl_m0", "eLife_Downloads_LocalVoR_Month0_DiD", "pct"),
        ("ev_dl_p16", "eLife_Downloads_LocalVoR_Post1to6m_DiD", "pct"),
    ]:
        r = u_inc[mk]
        p = r["params"]["str_upgraded_to_solid"]
        mag = float(p["pct"]) if "pct" in p else (100.0 * float(p["beta"]) if unit == "pct_rank_pp" else float(100.0 * (np.exp(p["beta"]) - 1.0)))
        t2_rows.append({
            "panel": "C_Upgrade_Payoff_v1Incomp",
            "outcome": olbl,
            "term": "str_upgraded_to_solid",
            "n_obs": int(r["n"]),
            "n_clusters": int(r["G"]),
            "beta": round(float(p["beta"]), 4),
            "effect_magnitude": round(mag, 2),
            "effect_unit": unit,
            "se": round(float(p["se"]), 4),
            "t_stat": round(float(p["t"]), 3),
            "p_value": float(p["p"]),
            "p_wcb": float(p.get("p_wcb", p["p"])),
        })

    # Panel D: VoR Publication & Version-Release Events (What DOES Move Reader Attention!)
    for r_obj, tkey, olbl in [
        (vor_vs_rp_incomp["ols_log1p_pv_total"], "is_vor", "eLife_PageViews_VoR_vs_RPOnly_v1Incomp"),
        (vor_vs_rp_incomp["ols_log1p_dl_total"], "is_vor", "eLife_Downloads_VoR_vs_RPOnly_v1Incomp"),
        (u_inc["traj_dlog_pv_12_21_ctrl_ver"], "cr_n_versions", "eLife_PageViews_PerPublishedVersion_v1Incomp"),
        (upgrade_res["v1_Solid_VoRs"]["traj_dlog_pv_12_21_ctrl_ver"], "cr_n_versions", "eLife_PageViews_PerPublishedVersion_v1Solid"),
    ]:
        p = r_obj["params"][tkey]
        mag = float(100.0 * (np.exp(p["beta"]) - 1.0))
        t2_rows.append({
            "panel": "D_Version_Release_Events",
            "outcome": olbl,
            "term": tkey,
            "n_obs": int(r_obj["n"]),
            "n_clusters": int(r_obj["G"]),
            "beta": round(float(p["beta"]), 4),
            "effect_magnitude": round(mag, 2),
            "effect_unit": "pct",
            "se": round(float(p["se"]), 4),
            "t_stat": round(float(p["t"]), 3),
            "p_value": float(p["p"]),
            "p_wcb": float(p.get("p_wcb", p["p"])),
        })

    t2_df = pd.DataFrame(t2_rows)
    t2_path = TBL_DIR / "table2_v1_gradient_upgrade_autopsy.csv"
    t2_df.to_csv(t2_path, index=False, lineterminator="\n")

    out_obj = {
        "n_full_v1_panel": len(df),
        "n_mature_2023_2024": len(mat),
        "n_mature_with_metrics": int((mat["has_metrics"] == 1).sum()),
        "n_mature_complete_monthly_ge_2023_11": int((mat["has_complete_monthly_metrics"] == 1).sum()),
        "n_mature_vors": len(mat_v),
        "pillar1_transition_mature": trans_mature,
        "pillar1_transition_all_4541": trans_all_4541,
        "pillar1_esci_solid_cliff": esci_results,
        "pillar2_v1_gradient_and_autopsy": gradient_res,
        "pillar2_loso_18subj": loso_grad,
        "pillar2_vor_vs_rp_incomp": vor_vs_rp_incomp,
        "pillar2_upgrade_payoff": upgrade_res,
        "tables_sha256": {
            t1_path.name: sha256_bytes(t1_path),
            t2_path.name: sha256_bytes(t2_path),
        },
        "elapsed_sec": round(time.time() - t0, 2),
    }
    sha = write_json_lf(RES_DIR / "04_pillar1_2_results.json", out_obj)
    print(f"[DONE STEP 4] Elapsed {out_obj['elapsed_sec']}s | SHA-256: {sha}", flush=True)


if __name__ == "__main__":
    main()
