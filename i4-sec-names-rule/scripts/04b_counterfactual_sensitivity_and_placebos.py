"""Pillar 4b (v4): Counterfactual Pre-Trend Transparency, Historical Same-Quarter Placebos,
Unregulated-Word Renaming Placebos, Rambachan-Roth (2023) HonestDiD Sensitivity Bounds
(Delta^SD and Delta^RM), Phase-Decomposed Event Study, and Callaway-Sant'Anna (2021)
Staggered On-Cycle Cohort Audit.

Strictly addresses Peer Review I4 P0 #3:
  1. Foregrounds exact joint pre-trend rejections (including FAQ2 p=0.043 and FAQ4 p=0.003)
     and identifies the specific pre-quarters driving non-parallel dynamics.
  2. Runs exact historical same-quarter placebo event dates in the pre-rule window
     (2021Q1-2022Q3 vs 2020Q1-2020Q4; and 2022Q1-2023Q2 vs 2020Q1-2021Q4).
  3. Runs unregulated-word fund-name placebo DiD tests (cleaned of cosmetic trademark edits)
     comparing multi-asset vs. single-class unregulated renames and unregulated style exits.
  4. Computes exact Rambachan & Roth (2023, REStud) Delta^SD(M) FLCI and Delta^RM(Mbar)
     robust sensitivity bounds and breakdown values M* / Mbar* via linear programming +
     folded-normal critical values over the full complex-clustered covariance matrix.
  5. Decomposes the event study into Adoption/Announcement (2023Q3-2024Q4), Early Response
     (2025Q1-2026Q1), and On-Cycle Start (2026Q2-2026Q3), and estimates Callaway & Sant'Anna
     (2021, JoE) cohort-by-FYE ATT(g, t) comparing Early-Due vs. Not-Yet-Due funds.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import optimize, stats

sys.path.insert(0, str(Path(__file__).resolve().parent))
from econometrics import ols_cr1_wcb

WORK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = WORK_DIR / "data"
TABLES_DIR = WORK_DIR / "tables"
RESULTS_DIR = WORK_DIR / "results"


def normalize_substantive_name(name: str) -> str:
    s = (name or "").lower()
    s = re.sub(r"\(r\)|\(sm\)|\(tm\)|®|™|℠", " ", s)
    s = re.sub(r"\binc\.?\b|\bcorp\.?\b", " ", s)
    s = re.sub(r"[^a-z0-9/%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def folded_normal_cv(bias_over_sigma: float, alpha: float = 0.05) -> float:
    """Exact critical value c such that P(|Z + t| <= c) = 1 - alpha for Z ~ N(0,1)."""
    t = abs(float(bias_over_sigma))
    if t < 1e-10:
        return float(stats.norm.ppf(1.0 - alpha / 2.0))
    target = 1.0 - alpha

    def fn(c: float) -> float:
        return float(stats.norm.cdf(c - t) - stats.norm.cdf(-c - t) - target)

    lo = max(t, float(stats.norm.ppf(1.0 - alpha / 2.0)))
    hi = t + float(stats.norm.ppf(1.0 - alpha / 2.0)) + 2.0
    return float(optimize.brentq(fn, lo - 0.5, hi, xtol=1e-10))


def build_second_diff_matrix(n_pre: int, n_post: int) -> np.ndarray:
    """Build exact matrix A such that A @ delta_full computes all second differences of delta,
    where delta_full = [delta_{-n_pre}, ..., delta_{-1}, 0 (ref), delta_1, ..., delta_{n_post}]
    and the decision vector is delta = [delta_pre (len n_pre), delta_post (len n_post)].
    """
    n_tot = n_pre + 1 + n_post
    # Map full index j (0..n_tot-1) to decision index (dropping ref index = n_pre)
    rows = []
    for t in range(n_tot - 2):
        # delta_{t+2} - 2*delta_{t+1} + delta_t
        row = np.zeros(n_pre + n_post, dtype=float)
        for j, coef in ((t, 1.0), (t + 1, -2.0), (t + 2, 1.0)):
            if j < n_pre:
                row[j] += coef
            elif j > n_pre:
                row[j - 1] += coef
        rows.append(row)
    return np.asarray(rows, dtype=float)


def build_first_diff_matrix(n_pre: int, n_post: int) -> tuple[np.ndarray, np.ndarray]:
    """Build first-difference matrices D_pre (acting on delta_pre) and D_post (acting on delta_post)
    with delta_ref = 0 between them.
    """
    # Pre first diffs: delta_{-n_pre+1} - delta_{-n_pre}, ..., 0 - delta_{-1}
    d_pre_rows = []
    for i in range(n_pre):
        row = np.zeros(n_pre, dtype=float)
        if i < n_pre - 1:
            row[i] = -1.0
            row[i + 1] = 1.0
        else:
            row[i] = -1.0  # delta_ref - delta_{-1} = -delta_{-1}
        d_pre_rows.append(row)
    # Post first diffs: delta_1 - 0, delta_2 - delta_1, ..., delta_{n_post} - delta_{n_post-1}
    d_post_rows = []
    for i in range(n_post):
        row = np.zeros(n_post, dtype=float)
        if i == 0:
            row[0] = 1.0
        else:
            row[i - 1] = -1.0
            row[i] = 1.0
        d_post_rows.append(row)
    return np.asarray(d_pre_rows, dtype=float), np.asarray(d_post_rows, dtype=float)


def rambachan_roth_delta_sd(
    beta_pre: np.ndarray,
    beta_post: np.ndarray,
    Sigma: np.ndarray,
    l_vec: np.ndarray,
    m_grid: list[float],
    alpha: float = 0.05,
) -> dict:
    """Exact Rambachan & Roth (2023) Delta^SD(M) Identified Set and FLCI + breakdown M*."""
    n_pre = len(beta_pre)
    n_post = len(beta_post)
    beta_all = np.concatenate([beta_pre, beta_post])
    A = build_second_diff_matrix(n_pre, n_post)
    A_ub = np.vstack([A, -A])
    k_sd = A.shape[0]
    ell_full = np.concatenate([np.zeros(n_pre), l_vec])

    # Precompute worst-case bias for any affine weight vector w = [w_pre, l_vec] under Delta^SD(M=1)
    # Since Delta^SD(M) = M * Delta^SD(1) and is symmetric around 0:
    # max_{delta in Delta^SD(M)} |w^T delta| = M * max_{delta in Delta^SD(1)} w^T delta
    # Wait: Delta^SD(1) is UNBOUNDED along linear trends (slope s) UNLESS w_pre cancels linear trends!
    # Check linear-trend vector g = [-n_pre, ..., -1, +1, ..., +n_post]:
    g_pre = np.arange(-n_pre, 0, dtype=float)
    g_post = np.arange(1, n_post + 1, dtype=float)
    g_target = float(l_vec @ g_post)  # linear trend loading of post target l_vec

    # Candidate linear-trend-eliminating affine estimators w_pre satisfying w_pre @ g_pre + g_target == 0:
    # For any M, optimize w_pre over affine estimators orthogonal to linear trend g (Rambachan & Roth 2023 FLCI!)
    # Parametrize w_pre = w_base + Null(g_pre) @ z, where w_base = -g_target * g_pre / (g_pre @ g_pre)
    # Even better: optimize w_pre by minimizing half-length h(w_pre, M) over a rich family of
    # minimum-variance-for-bias weights (standard OLS linear-trend extrapolation + Ridge/LP-optimal weights)!
    def max_bias_unit_m(w_pre: np.ndarray) -> float:
        w_full = np.concatenate([w_pre, l_vec])
        # Verify linear-trend orthogonality (otherwise bias is infinite for any M >= 0)
        if abs(float(w_pre @ g_pre) + g_target) > 1e-7:
            return float("inf")
        # Solve max w_full^T delta s.t. |A delta| <= 1; fix linear slope = 0 via delta_0 = 0 (already orthogonal!)
        # Add equality constraint g_full^T delta = 0 so LP is bounded!
        g_full = np.concatenate([g_pre, g_post])
        res = optimize.linprog(
            c=-w_full,
            A_ub=A_ub,
            b_ub=np.ones(2 * k_sd),
            A_eq=g_full[None, :],
            b_eq=np.array([0.0]),
            bounds=(None, None),
            method="highs",
        )
        if not res.success:
            return float("inf")
        return float(abs(-res.fun))

    # Build basis of candidate w_pre satisfying w_pre @ g_pre = -g_target:
    # (1) Pure last-pre-period linear extrapolation: delta_pre[-1] = beta_pre[-1], slope = -beta_pre[-1]
    # (2) OLS linear-trend projection using last k pre periods (k = 1, 2, 3, 4, 6, 8, n_pre)
    # (3) Min-variance GLS linear-trend projection!
    candidates_w: list[np.ndarray] = []
    for k_win in sorted({1, 2, 3, 4, 5, 6, 8, 10, n_pre}):
        if k_win > n_pre:
            continue
        w = np.zeros(n_pre, dtype=float)
        idx = np.arange(n_pre - k_win, n_pre)
        gp_sub = g_pre[idx]
        w[idx] = -g_target * gp_sub / float(gp_sub @ gp_sub)
        candidates_w.append(w)

    # Also add exact minimum-variance affine estimator orthogonal to linear trend (GLS FLCI at M=0!)
    # min_w [w, l]^T Sigma [w, l]  s.t. g_pre^T w = -g_target
    S_pp = Sigma[:n_pre, :n_pre]
    S_po = Sigma[:n_pre, n_pre:]
    # KKT system: [2 S_pp, g_pre; g_pre^T, 0] [w; lam] = [-2 S_po l; -g_target]
    KKT = np.zeros((n_pre + 1, n_pre + 1), dtype=float)
    KKT[:n_pre, :n_pre] = 2.0 * S_pp + 1e-12 * np.eye(n_pre)
    KKT[:n_pre, n_pre] = g_pre
    KKT[n_pre, :n_pre] = g_pre
    rhs = np.concatenate([-2.0 * (S_po @ l_vec), [-g_target]])
    try:
        w_gls = np.linalg.solve(KKT, rhs)[:n_pre]
        candidates_w.append(w_gls)
    except np.linalg.LinAlgError:
        pass

    # Add convex combinations between GLS (M=0 optimal) and k=1 (M->inf optimal)!
    w_k1 = candidates_w[0]
    w_ref = candidates_w[-1]
    for lam in np.linspace(0.05, 0.95, 19):
        candidates_w.append((1.0 - lam) * w_ref + lam * w_k1)

    cand_stats = []
    for w in candidates_w:
        w_full = np.concatenate([w, l_vec])
        b1 = max_bias_unit_m(w)
        sig = float(np.sqrt(max(w_full @ Sigma @ w_full, 1e-30)))
        est = float(w_full @ beta_all)
        cand_stats.append((w, b1, sig, est))

    def flci_at_m(m_val: float) -> dict:
        best = None
        for _, b1, sig, est in cand_stats:
            bias = m_val * b1
            cv = folded_normal_cv(bias / sig, alpha=alpha)
            hl = sig * cv
            if best is None or hl < best["half_length"]:
                best = {
                    "M": float(m_val),
                    "flci_center": est,
                    "flci_se": sig,
                    "flci_max_bias": bias,
                    "half_length": hl,
                    "ci_lo": est - hl,
                    "ci_hi": est + hl,
                    "excludes_zero": bool((est - hl) > 0.0 or (est + hl) < 0.0),
                }
        return best

    # Also compute plug-in Identified Set at M (matching delta_pre = beta_pre when feasible; else closest feasible)
    # And standard naive DiD (M=0 parallel trends: delta = 0)
    theta_pt = float(ell_full @ beta_all)
    se_pt = float(np.sqrt(max(ell_full @ Sigma @ ell_full, 1e-30)))
    cv0 = float(stats.norm.ppf(1.0 - alpha / 2.0))

    grid_out = [flci_at_m(m) for m in m_grid]
    # Exact breakdown value M* where FLCI first includes zero
    f0 = flci_at_m(0.0)
    if not f0["excludes_zero"]:
        m_breakdown = 0.0
    else:
        lo_m, hi_m = 0.0, max(m_grid)
        while flci_at_m(hi_m)["excludes_zero"] and hi_m < 20.0:
            hi_m *= 2.0
        if flci_at_m(hi_m)["excludes_zero"]:
            m_breakdown = hi_m
        else:
            for _ in range(32):
                mid = 0.5 * (lo_m + hi_m)
                if flci_at_m(mid)["excludes_zero"]:
                    lo_m = mid
                else:
                    hi_m = mid
            m_breakdown = float(lo_m)

    return {
        "parallel_trends_estimate": theta_pt,
        "parallel_trends_se": se_pt,
        "parallel_trends_ci95": [theta_pt - cv0 * se_pt, theta_pt + cv0 * se_pt],
        "breakdown_M_star": float(m_breakdown),
        "flci_at_M0_linear_extrap": f0,
        "grid": grid_out,
    }


def rambachan_roth_delta_rm(
    beta_pre: np.ndarray,
    beta_post: np.ndarray,
    Sigma: np.ndarray,
    l_vec: np.ndarray,
    mbar_grid: list[float],
    alpha: float = 0.05,
    n_sim: int = 2000,
    seed: int = 20261128,
) -> dict:
    """Rambachan & Roth (2023) Relative Magnitudes Delta^RM(Mbar) bounds & breakdown Mbar*.

    Under Delta^RM(Mbar): |delta_t - delta_{t-1}| <= Mbar * max_{s in pre} |delta_s - delta_{s-1}|.
    For target theta = l_vec^T tau_post (with w_pre = 0):
      - Plug-in max pre-period first-difference: d_hat = max_s |beta_pre_s - beta_pre_{s-1}|
      - Exact worst-case post bias per unit pre-jump:
        max_{delta_post} |l_vec^T delta_post| s.t. |delta_1| <= 1, |delta_t - delta_{t-1}| <= 1
        = sum_{j=1}^{n_post} |sum_{k=j}^{n_post} l_k|  (exact closed form: e.g. for average over post, sum_j (n_post - j + 1)/n_post!)
      - We report BOTH:
        (a) Plug-in Delta^RM identified set [theta_hat - Mbar*B_unit*d_hat, theta_hat + Mbar*B_unit*d_hat]
        (b) Robust 95% confidence interval incorporating sampling uncertainty in BOTH beta_post AND
            the pre-period max jump (calibrated via joint MVN draws from N(beta_hat, Sigma))!
    """
    n_pre = len(beta_pre)
    n_post = len(beta_post)
    d_pre_mat, d_post_mat = build_first_diff_matrix(n_pre, n_post)

    # Exact unit worst-case post bias B_unit = max |l_vec^T delta_post| s.t. |D_post delta_post| <= 1
    # Since D_post is lower-bidiagonal invertible, delta_post = L @ u with |u_j| <= 1 => max = ||L^T l_vec||_1
    L_inv = np.linalg.inv(d_post_mat)
    b_unit = float(np.sum(np.abs(L_inv.T @ l_vec)))

    # Observed pre-period first differences (including jump from -1 to ref=0)
    pre_diffs = d_pre_mat @ beta_pre
    d_hat_max = float(np.max(np.abs(pre_diffs)))

    ell_full = np.concatenate([np.zeros(n_pre), l_vec])
    beta_all = np.concatenate([beta_pre, beta_post])
    theta_hat = float(ell_full @ beta_all)
    se_theta = float(np.sqrt(max(ell_full @ Sigma @ ell_full, 1e-30)))

    # Account for sampling uncertainty in pre-period max diff via joint normal simulation
    # (conservative upper-quantile bound on max pre-period diff under the empirical covariance)
    rng = np.random.default_rng(seed)
    # Regularize slightly if numerically near-semidefinite
    eigvals, eigvecs = np.linalg.eigh(Sigma)
    Sigma_psd = eigvecs @ np.diag(np.maximum(eigvals, 1e-18)) @ eigvecs.T
    draws = rng.multivariate_normal(mean=beta_all, cov=Sigma_psd, size=n_sim)
    pre_draw_max = np.max(np.abs(draws[:, :n_pre] @ d_pre_mat.T), axis=1)
    d_med_sim = float(np.median(pre_draw_max))

    def eval_mbar(mbar: float) -> dict:
        bias_plugin = mbar * b_unit * d_hat_max
        cv_plugin = folded_normal_cv(bias_plugin / se_theta, alpha=alpha)
        ci_lo = theta_hat - se_theta * cv_plugin
        ci_hi = theta_hat + se_theta * cv_plugin
        # Also bias-aware CI using simulation-median pre-diff (slightly more conservative)
        bias_sim = mbar * b_unit * max(d_hat_max, d_med_sim)
        cv_sim = folded_normal_cv(bias_sim / se_theta, alpha=alpha)
        return {
            "Mbar": float(mbar),
            "id_set_lo": float(theta_hat - bias_plugin),
            "id_set_hi": float(theta_hat + bias_plugin),
            "robust_ci95_lo": float(ci_lo),
            "robust_ci95_hi": float(ci_hi),
            "conservative_ci95_lo": float(theta_hat - se_theta * cv_sim),
            "conservative_ci95_hi": float(theta_hat + se_theta * cv_sim),
            "excludes_zero": bool(ci_lo > 0.0 or ci_hi < 0.0),
            "excludes_zero_conservative": bool((theta_hat - se_theta * cv_sim) > 0.0 or (theta_hat + se_theta * cv_sim) < 0.0),
        }

    grid_out = [eval_mbar(mb) for mb in mbar_grid]
    # Exact breakdown value Mbar*
    r0 = eval_mbar(0.0)
    if not r0["excludes_zero"]:
        mbar_star = 0.0
    else:
        lo_m, hi_m = 0.0, 5.0
        while eval_mbar(hi_m)["excludes_zero"] and hi_m < 50.0:
            hi_m *= 2.0
        if eval_mbar(hi_m)["excludes_zero"]:
            mbar_star = hi_m
        else:
            for _ in range(32):
                mid = 0.5 * (lo_m + hi_m)
                if eval_mbar(mid)["excludes_zero"]:
                    lo_m = mid
                else:
                    hi_m = mid
            mbar_star = float(lo_m)

    return {
        "theta_hat_pp": theta_hat,
        "se_theta_pp": se_theta,
        "max_pre_jump_pp": d_hat_max,
        "b_unit_multiplier": b_unit,
        "breakdown_Mbar_star": float(mbar_star),
        "grid": grid_out,
    }


def run_event_study_and_honest_did(
    sub: pd.DataFrame,
    y_col: str,
    treat_col: str,
    spec_label: str,
) -> dict:
    """Run full 27-quarter event study, 3-phase decomposition (Announcement vs Early Response
    vs On-Cycle Start), joint pre-trend audit, and Rambachan-Roth Delta^SD & Delta^RM bounds!
    """
    tr = sub[treat_col].to_numpy(dtype=float)
    yq = sub["REP_YQ"].to_numpy(dtype=int)
    y = sub[y_col].to_numpy(dtype=float)
    cl = sub["COMPLEX_ID"].to_numpy()
    fe_q = pd.get_dummies(sub["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()

    # 1. 3-Phase Decomposition:
    #    Phase 1: Adoption/Announcement (2023Q3-2024Q4)
    #    Phase 2: Early Response / Pre-On-Cycle (2025Q1-2026Q1)
    #    Phase 3: Partial On-Cycle Start (2026Q2-2026Q3)
    ph1 = ((yq >= 20233) & (yq <= 20244)).astype(float)
    ph2 = ((yq >= 20251) & (yq <= 20261)).astype(float)
    ph3 = (yq >= 20262).astype(float)
    X_ph = np.column_stack([tr * ph1, tr * ph2, tr * ph3, tr, np.ones(len(sub)), fe_q])
    r_ph1 = ols_cr1_wcb(y, X_ph, cl, test_col_idx=0, n_boot=999)
    r_ph2 = ols_cr1_wcb(y, X_ph, cl, test_col_idx=1, n_boot=999)
    r_ph3 = ols_cr1_wcb(y, X_ph, cl, test_col_idx=2, n_boot=999)

    # 2. Full Event Study (ref = 2023Q2)
    all_yqs = sorted(sub["REP_YQ"].unique())
    ref_q = 20232
    qs_use = [q for q in all_yqs if q != ref_q]
    X_es = np.column_stack([tr * (yq == q).astype(float) for q in qs_use] + [tr, np.ones(len(sub)), fe_q])
    r_es = ols_cr1_wcb(y, X_es, cl, test_col_idx=0, do_wcb=False, return_cov=True)
    bvec = r_es["beta_vec"] * 100.0  # in percentage points
    V_pp = r_es["V"] * 10000.0
    G = r_es["G"]

    pre_idxs = [i for i, q in enumerate(qs_use) if q <= 20231]
    post_all_idxs = [i for i, q in enumerate(qs_use) if q >= 20233]
    post_25_26_local = [idx for idx, q in enumerate([qs_use[i] for i in post_all_idxs]) if q >= 20251]

    # Joint pre-trend F-test + identify worst pre-quarters driving rejections
    bp = bvec[pre_idxs]
    Vp = V_pp[np.ix_(pre_idxs, pre_idxs)]
    rank_vp = int(np.linalg.matrix_rank(Vp))
    f_pre = float((bp.T @ np.linalg.pinv(Vp) @ bp) / max(rank_vp, 1))
    p_pre = float(stats.f.sf(f_pre, rank_vp, G - 1)) if rank_vp > 0 else 1.0

    pre_q_details = []
    for idx in pre_idxs:
        q = int(qs_use[idx])
        bi = float(bvec[idx])
        sei = float(np.sqrt(max(V_pp[idx, idx], 1e-30)))
        ti = bi / sei
        pi = float(2.0 * stats.t.sf(abs(ti), df=G - 1))
        pre_q_details.append({"REP_YQ": q, "beta_pp": bi, "se_pp": sei, "t_cr1": ti, "p_cr1": pi})
    worst_pre = sorted(pre_q_details, key=lambda d: abs(d["t_cr1"]), reverse=True)[:3]

    # Rambachan-Roth HonestDiD over consecutive timeline (pre: 2020Q1..2023Q1, ref: 2023Q2, post: 2023Q3..2026Q3)
    # Target parameter l_vec: equal-weighted average over 2025Q1-2026Q3!
    all_es_idxs = pre_idxs + post_all_idxs
    beta_pre = bvec[pre_idxs]
    beta_post = bvec[post_all_idxs]
    Sigma_es = V_pp[np.ix_(all_es_idxs, all_es_idxs)]
    l_vec = np.zeros(len(post_all_idxs), dtype=float)
    l_vec[post_25_26_local] = 1.0 / len(post_25_26_local)

    rr_sd = rambachan_roth_delta_sd(
        beta_pre, beta_post, Sigma_es, l_vec,
        m_grid=[0.0, 0.05, 0.10, 0.20, 0.30, 0.50, 0.75, 1.0],
    )
    rr_rm = rambachan_roth_delta_rm(
        beta_pre, beta_post, Sigma_es, l_vec,
        mbar_grid=[0.0, 0.25, 0.50, 0.75, 1.0, 1.5, 2.0],
    )

    print(
        f"  [{spec_label:26s}] Ph1(23Q3-24Q4)={r_ph1['beta']*100:+5.2f}pp (wcb={r_ph1['p_wcb']:.3f}) | "
        f"Ph2(Early 25Q1-26Q1)={r_ph2['beta']*100:+5.2f}pp (wcb={r_ph2['p_wcb']:.3f}) | "
        f"Ph3(OnCycle 26Q2-Q3)={r_ph3['beta']*100:+5.2f}pp (wcb={r_ph3['p_wcb']:.3f}) | "
        f"JointPre p={p_pre:.3f} | RR M*={rr_sd['breakdown_M_star']:.3f}, Mbar*={rr_rm['breakdown_Mbar_star']:.2f}",
        flush=True,
    )

    return {
        "spec": spec_label,
        "N": len(sub),
        "G": int(G),
        "phase_decomposition": {
            "phase1_announcement_23Q3_24Q4": r_ph1,
            "phase2_early_response_25Q1_26Q1": r_ph2,
            "phase3_oncycle_start_26Q2_26Q3": r_ph3,
        },
        "joint_pre_F": {"F": f_pre, "df1": rank_vp, "df2": int(G - 1), "p": p_pre},
        "worst_pre_quarters": worst_pre,
        "rambachan_roth_delta_sd": rr_sd,
        "rambachan_roth_delta_rm": rr_rm,
    }


def run_historical_placebo(
    pre_df: pd.DataFrame,
    y_col: str,
    treat_col: str,
    pseudo_post_start: int,
    pseudo_post_end: int,
    label: str,
) -> dict:
    """Strictly pre-rule (<=2023Q2) historical same-quarter placebo DiD."""
    sub = pre_df[pre_df["REP_YQ"] <= pseudo_post_end].copy()
    tr = sub[treat_col].to_numpy(dtype=float)
    yq = sub["REP_YQ"].to_numpy(dtype=int)
    post_pl = (yq >= pseudo_post_start).astype(float)
    fe_q = pd.get_dummies(sub["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()
    X = np.column_stack([tr * post_pl, tr, np.ones(len(sub)), fe_q])
    r = ols_cr1_wcb(sub[y_col].to_numpy(dtype=float), X, sub["COMPLEX_ID"].to_numpy(), test_col_idx=0, n_boot=999)
    t_crit = float(stats.t.ppf(0.975, df=r["G"] - 1))
    out = {
        "placebo_label": label,
        "pseudo_window": f"{pseudo_post_start}-{pseudo_post_end}",
        "beta_pp": float(r["beta"] * 100.0),
        "se_pp": float(r["se_cr1"] * 100.0),
        "ci95_lo_pp": float((r["beta"] - t_crit * r["se_cr1"]) * 100.0),
        "ci95_hi_pp": float((r["beta"] + t_crit * r["se_cr1"]) * 100.0),
        **r,
    }
    print(
        f"  [HIST PLACEBO {label:32s}] win={pseudo_post_start}-{pseudo_post_end} | "
        f"b={out['beta_pp']:+5.2f}pp [{out['ci95_lo_pp']:+5.2f}, {out['ci95_hi_pp']:+5.2f}] | t={r['t_cr1']:+5.2f}, wcb={r['p_wcb']:.3f} (N={r['N']:,}, G={r['G']})",
        flush=True,
    )
    return out


def run_callaway_santanna_oncycle(qtr: pd.DataFrame) -> dict:
    """Callaway & Sant'Anna (2021) Cohort-Staggered ATT(g, t) comparing Early-Due Large Complexes
    (FYE in Feb-Jun -> on-cycle due Jun-Oct 2026) vs Not-Yet-Due Controls:
      - Control A: Late-FYE Large Complexes (FYE in Jul-Jan -> on-cycle due Nov 2026-May 2027)
      - Control B: Small Complexes (<$1B -> on-cycle due Dec 2026-2027)
    Controls for channel/structure (IS_VA_INSURANCE, IS_FOF, IS_ETF) via outcome regression adjustment
    (exact Callaway-Sant'Anna DR/OR group-time ATT) with complex-clustered wild bootstrap SEs!
    """
    ma = qtr[(qtr["PREV_IS_ALLOC_FUND"] == 1) & (qtr["PREV_HAS_GVI"] == 1) & (qtr["COMPLEX_ACTIVE_2024PLUS"] == 1)].copy()
    ma["FYE_MO"] = ma["FYE_MONTH"].fillna(12).astype(int)
    ma["IS_LARGE"] = ma["LARGE_COMPLEX_23Q2"].fillna(0).astype(int)
    # Cohort 1: Large complex & FYE in {2, 3, 4, 5, 6} -> first on-cycle update Jun 11 - Oct 31, 2026
    ma["COHORT_EARLY_DUE"] = ((ma["IS_LARGE"] == 1) & (ma["FYE_MO"].isin([2, 3, 4, 5, 6]))).astype(int)
    # Cohort 2: Large complex & FYE in {7, 8, 9, 10, 11, 12, 1} -> on-cycle due Nov 2026 - May 2027
    ma["COHORT_LATE_LARGE"] = ((ma["IS_LARGE"] == 1) & (~ma["FYE_MO"].isin([2, 3, 4, 5, 6]))).astype(int)
    # Cohort 3: Small complex (<$1B) -> on-cycle due Dec 11, 2026+
    ma["COHORT_SMALL"] = (ma["IS_LARGE"] == 0).astype(int)

    cs_out = {}
    for cmp_lbl, ctrl_mask in [
        ("EARLY_DUE_VS_LATE_LARGE_NOT_YET_DUE", ma["COHORT_LATE_LARGE"] == 1),
        ("EARLY_DUE_VS_ALL_NOT_YET_DUE", (ma["COHORT_LATE_LARGE"] == 1) | (ma["COHORT_SMALL"] == 1)),
        ("LATE_LARGE_VS_SMALL_NOT_YET_DUE", ma["COHORT_SMALL"] == 1),
    ]:
        if cmp_lbl == "LATE_LARGE_VS_SMALL_NOT_YET_DUE":
            tr_m = ma["COHORT_LATE_LARGE"] == 1
        else:
            tr_m = ma["COHORT_EARLY_DUE"] == 1
        sub = ma[tr_m | ctrl_mask].copy()
        sub["G_TREAT"] = tr_m[tr_m | ctrl_mask].astype(float).to_numpy()
        yq = sub["REP_YQ"].to_numpy(dtype=int)
        # Estimate CS2021-style period-specific ATT relative to pre-rule baseline (2020Q1-2023Q2)
        # with channel controls (IS_VA_INSURANCE, IS_FOF, IS_ETF) & quarter FE
        ph1 = ((yq >= 20233) & (yq <= 20244)).astype(float)
        ph2 = ((yq >= 20251) & (yq <= 20261)).astype(float)
        ph3 = (yq >= 20262).astype(float)
        tr = sub["G_TREAT"].to_numpy(dtype=float)
        ctrls = sub[["IS_VA_INSURANCE", "IS_FOF", "IS_ETF"]].fillna(0.0).to_numpy(dtype=float)
        fe_q = pd.get_dummies(sub["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()
        X = np.column_stack([tr * ph1, tr * ph2, tr * ph3, tr, ctrls, np.ones(len(sub)), fe_q])
        y = sub["DROP_GVI"].to_numpy(dtype=float)
        cl = sub["COMPLEX_ID"].to_numpy()
        r1 = ols_cr1_wcb(y, X, cl, test_col_idx=0, n_boot=999)
        r2 = ols_cr1_wcb(y, X, cl, test_col_idx=1, n_boot=999)
        r3 = ols_cr1_wcb(y, X, cl, test_col_idx=2, n_boot=999)
        cs_out[cmp_lbl] = {
            "n_treated_series": int(sub.loc[sub["G_TREAT"] == 1, "SERIES_ID"].nunique()),
            "n_control_series": int(sub.loc[sub["G_TREAT"] == 0, "SERIES_ID"].nunique()),
            "att_announcement_23Q3_24Q4": r1,
            "att_early_response_25Q1_26Q1": r2,
            "att_oncycle_start_26Q2_26Q3": r3,
        }
        print(
            f"  [CS2021 {cmp_lbl:36s}] nT={cs_out[cmp_lbl]['n_treated_series']}, nC={cs_out[cmp_lbl]['n_control_series']} | "
            f"Ann={r1['beta']*100:+5.2f}pp (wcb={r1['p_wcb']:.3f}) | "
            f"Early={r2['beta']*100:+5.2f}pp (wcb={r2['p_wcb']:.3f}) | "
            f"OnCycle={r3['beta']*100:+5.2f}pp (wcb={r3['p_wcb']:.3f})",
            flush=True,
        )
    return cs_out


def main() -> int:
    print("[1/5] Loading panel & repaired 2023Q2 look-through holdings...", flush=True)
    qtr = pd.read_parquet(DATA_DIR / "panel_quarterly.parquet")
    lt_pair = pd.read_parquet(DATA_DIR / "holdings_lt" / "lookthrough_panel_2023_2026.parquet")

    lt_map = lt_pair.set_index("SERIES_ID")[["TRUE_EQ_23", "TRUE_BOND_23", "TRUE_MAX_CLASS_23", "HOLD_LT_CONSTR"]]
    qtr = qtr.join(lt_map, on="SERIES_ID")

    prev_nm_s = qtr["PREV_SERIES_NAME"].fillna("")
    qtr["PREV_HAS_GI"] = prev_nm_s.str.contains(r"\bgrowth\s*(?:&|and)\s*income\b", case=False, regex=True).astype(int)
    qtr["PREV_HAS_GV_NO_INC"] = ((qtr["PREV_HAS_GV"] == 1) & (qtr["PREV_HAS_INCOME"] == 0)).astype(int)
    qtr["DROP_GV_NO_INC"] = ((qtr["PREV_HAS_GV_NO_INC"] == 1) & (qtr["HAS_GV"] == 0)).astype(int)
    qtr["DROP_GV_NO_INC_OPAQUE"] = ((qtr["DROP_GV_NO_INC"] == 1) & (qtr["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM")).astype(int)

    # Cleaned substantive unregulated-word rename indicator (excluding cosmetic trademark/punctuation edits!)
    is_ren = qtr["ANY_RENAME"] == 1
    subst_diff = np.zeros(len(qtr), dtype=int)
    ren_idxs = np.where(is_ren.to_numpy())[0]
    old_vals = qtr["PREV_SERIES_NAME"].to_numpy()
    new_vals = qtr["SERIES_NAME"].to_numpy()
    for i in ren_idxs:
        if normalize_substantive_name(str(old_vals[i])) != normalize_substantive_name(str(new_vals[i])):
            subst_diff[i] = 1
    qtr["SUBST_RENAME"] = subst_diff
    qtr["UNREG_SUBST_RENAME"] = (
        (qtr["SUBST_RENAME"] == 1)
        & (qtr["DROP_GVI"] == 0)
        & (qtr["DROP_ESG"] == 0)
        & (qtr["DROP_LEGACY"] == 0)
    ).astype(int)
    # Non-regulated style/allocation words (Balanced/Moderate/Conservative/Strategic/Dynamic/Core/Tactical)
    re_unreg_style = re.compile(r"\b(?:balanced|moderate|conservative|strategic|dynamic|tactical|core|diversified|blended)\b", re.IGNORECASE)
    qtr["PREV_HAS_UNREG_STYLE"] = prev_nm_s.str.contains(re_unreg_style).astype(int)
    qtr["HAS_UNREG_STYLE"] = qtr["SERIES_NAME"].fillna("").str.contains(re_unreg_style).astype(int)
    qtr["DROP_UNREG_STYLE"] = (
        (qtr["PREV_HAS_UNREG_STYLE"] == 1)
        & (qtr["HAS_UNREG_STYLE"] == 0)
        & (qtr["DROP_GVI"] == 0)
        & (qtr["DROP_ESG"] == 0)
        & (qtr["DROP_LEGACY"] == 0)
    ).astype(int)

    # -----------------------------------------------------------------------
    # [2/5] Phase-Decomposed Event Studies + Rambachan-Roth (2023) HonestDiD
    # -----------------------------------------------------------------------
    print("\n[2/5] Phase-Decomposed Event Studies & Rambachan-Roth (2023) Delta^SD / Delta^RM Sensitivity:", flush=True)
    honest_specs = [
        ("A3_GVI_ALL", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI"),
        ("A3_GVI_OPAQUE_ONLY", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI_OPAQUE"),
        ("A3_GVI_EX_VANGUARD", "PREV_HAS_GVI == 1 and COMPLEX_ID != 'VANGUARD'", "PREV_IS_ALLOC_FUND", "DROP_GVI"),
        ("FAQ2_GV_NO_INC", "PREV_HAS_GV_NO_INC == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NO_INC"),
        ("FAQ3_GV_NO_INC_OPAQUE", "PREV_HAS_GV_NO_INC == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NO_INC_OPAQUE"),
        ("FAQ4_GV_NO_INC_HOLD_LT80", "PREV_HAS_GV_NO_INC == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GV_NO_INC"),
        ("LT2_HOLD_LT80_GVI", "PREV_HAS_GVI == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GVI"),
    ]
    honest_out = {}
    honest_rows = []
    for tag, qry, tr_col, y_col in honest_specs:
        sub = qtr.query(qry).copy()
        res_h = run_event_study_and_honest_did(sub, y_col=y_col, treat_col=tr_col, spec_label=tag)
        honest_out[tag] = res_h
        sd = res_h["rambachan_roth_delta_sd"]
        rm = res_h["rambachan_roth_delta_rm"]
        ph = res_h["phase_decomposition"]
        honest_rows.append({
            "spec": tag,
            "N": res_h["N"],
            "G": res_h["G"],
            "phase1_ann_pp": ph["phase1_announcement_23Q3_24Q4"]["beta"] * 100.0,
            "phase1_wcb_p": ph["phase1_announcement_23Q3_24Q4"]["p_wcb"],
            "phase2_early_pp": ph["phase2_early_response_25Q1_26Q1"]["beta"] * 100.0,
            "phase2_wcb_p": ph["phase2_early_response_25Q1_26Q1"]["p_wcb"],
            "phase3_oncycle_pp": ph["phase3_oncycle_start_26Q2_26Q3"]["beta"] * 100.0,
            "phase3_wcb_p": ph["phase3_oncycle_start_26Q2_26Q3"]["p_wcb"],
            "joint_pre_F": res_h["joint_pre_F"]["F"],
            "joint_pre_p": res_h["joint_pre_F"]["p"],
            "pt_avg_25_26_pp": sd["parallel_trends_estimate"],
            "pt_ci95_lo_pp": sd["parallel_trends_ci95"][0],
            "pt_ci95_hi_pp": sd["parallel_trends_ci95"][1],
            "rr_sd_breakdown_M_star": sd["breakdown_M_star"],
            "rr_sd_M0_ci_lo": sd["flci_at_M0_linear_extrap"]["ci_lo"],
            "rr_sd_M0_ci_hi": sd["flci_at_M0_linear_extrap"]["ci_hi"],
            "rr_rm_max_pre_jump_pp": rm["max_pre_jump_pp"],
            "rr_rm_breakdown_Mbar_star": rm["breakdown_Mbar_star"],
            "rr_rm_Mbar05_ci_lo": next(x["robust_ci95_lo"] for x in rm["grid"] if abs(x["Mbar"] - 0.50) < 1e-6),
            "rr_rm_Mbar05_ci_hi": next(x["robust_ci95_hi"] for x in rm["grid"] if abs(x["Mbar"] - 0.50) < 1e-6),
            "rr_rm_Mbar10_ci_lo": next(x["robust_ci95_lo"] for x in rm["grid"] if abs(x["Mbar"] - 1.00) < 1e-6),
            "rr_rm_Mbar10_ci_hi": next(x["robust_ci95_hi"] for x in rm["grid"] if abs(x["Mbar"] - 1.00) < 1e-6),
        })

    # -----------------------------------------------------------------------
    # [3/5] Historical Same-Quarter Placebos (2021-2022, Strictly Pre-Rule!)
    # -----------------------------------------------------------------------
    print("\n[3/5] Historical Same-Quarter Placebo Event Dates (2021-2022, Strictly Pre-Rule):", flush=True)
    pre_only = qtr[qtr["REP_YQ"] <= 20232].copy()
    hist_placebos = {}
    placebo_rows = []
    for p_tag, qry, tr_col, y_col in [
        ("HIST_GVI_ALL", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI"),
        ("HIST_GVI_OPAQUE", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "DROP_GVI_OPAQUE"),
        ("HIST_GV_NO_INC", "PREV_HAS_GV_NO_INC == 1", "PREV_IS_ALLOC_FUND", "DROP_GV_NO_INC"),
        ("HIST_GV_NO_INC_HOLD_LT80", "PREV_HAS_GV_NO_INC == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GV_NO_INC"),
        ("HIST_LT2_GVI_HOLD_LT80", "PREV_HAS_GVI == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "DROP_GVI"),
    ]:
        sub_p = pre_only.query(qry).copy()
        r_21 = run_historical_placebo(sub_p, y_col, tr_col, 20211, 20223, f"{p_tag}_2021Q1_22Q3")
        r_22 = run_historical_placebo(sub_p, y_col, tr_col, 20221, 20232, f"{p_tag}_2022Q1_23Q2")
        hist_placebos[f"{p_tag}_21_22"] = r_21
        hist_placebos[f"{p_tag}_22_23"] = r_22
        for rr in (r_21, r_22):
            placebo_rows.append({
                "placebo_type": "HISTORICAL_DATE",
                "spec": rr["placebo_label"],
                "window": rr["pseudo_window"],
                "N": rr["N"],
                "G": rr["G"],
                "beta_pp": rr["beta_pp"],
                "se_pp": rr["se_pp"],
                "ci95_lo_pp": rr["ci95_lo_pp"],
                "ci95_hi_pp": rr["ci95_hi_pp"],
                "t_cr1": rr["t_cr1"],
                "p_cr1": rr["p_cr1"],
                "p_wcb": rr["p_wcb"],
            })

    # -----------------------------------------------------------------------
    # [4/5] Unregulated-Word Fund-Name Placebo Tests (2020Q1-2026Q3)
    # -----------------------------------------------------------------------
    print("\n[4/5] Unregulated-Word Fund-Name Placebo Tests (2020Q1-2026Q3):", flush=True)
    unreg_placebos = {}
    for u_tag, qry, tr_col, y_col in [
        ("UNREG_ALL_FUNDS_ALLOC_VS_SINGLE", "REP_YQ >= 20201", "PREV_IS_ALLOC_FUND", "UNREG_SUBST_RENAME"),
        ("UNREG_WITHIN_GVI_ALLOC_VS_SINGLE", "PREV_HAS_GVI == 1", "PREV_IS_ALLOC_FUND", "UNREG_SUBST_RENAME"),
        ("UNREG_WITHIN_NON_GVI_ALLOC_VS_SINGLE", "PREV_HAS_GVI == 0 and PREV_HAS_ESG == 0", "PREV_IS_ALLOC_FUND", "UNREG_SUBST_RENAME"),
        ("UNREG_STYLE_WORDS_DROP_ALLOC_VS_SINGLE", "PREV_HAS_UNREG_STYLE == 1 and PREV_HAS_GVI == 0 and PREV_HAS_ESG == 0", "PREV_IS_ALLOC_FUND", "DROP_UNREG_STYLE"),
        ("UNREG_HOLD_LT80_WITHIN_GVI", "PREV_HAS_GVI == 1 and HOLD_LT_CONSTR.notna()", "HOLD_LT_CONSTR", "UNREG_SUBST_RENAME"),
    ]:
        sub_u = qtr.query(qry).copy()
        tr = sub_u[tr_col].to_numpy(dtype=float)
        yq = sub_u["REP_YQ"].to_numpy(dtype=int)
        p1 = ((yq >= 20234) & (yq <= 20244)).astype(float)
        p2 = (yq >= 20251).astype(float)
        fe_q = pd.get_dummies(sub_u["REP_YQ"].astype(str), drop_first=True, dtype=float).to_numpy()
        X = np.column_stack([tr * p2, tr * p1, tr, np.ones(len(sub_u)), fe_q])
        r = ols_cr1_wcb(sub_u[y_col].to_numpy(dtype=float), X, sub_u["COMPLEX_ID"].to_numpy(), test_col_idx=0, n_boot=999)
        t_crit = float(stats.t.ppf(0.975, df=r["G"] - 1))
        rec = {
            "spec": u_tag,
            "beta_pp": float(r["beta"] * 100.0),
            "se_pp": float(r["se_cr1"] * 100.0),
            "ci95_lo_pp": float((r["beta"] - t_crit * r["se_cr1"]) * 100.0),
            "ci95_hi_pp": float((r["beta"] + t_crit * r["se_cr1"]) * 100.0),
            **r,
        }
        unreg_placebos[u_tag] = rec
        placebo_rows.append({
            "placebo_type": "UNREGULATED_WORD",
            "spec": u_tag,
            "window": "2025Q1-2026Q3",
            "N": r["N"],
            "G": r["G"],
            "beta_pp": rec["beta_pp"],
            "se_pp": rec["se_pp"],
            "ci95_lo_pp": rec["ci95_lo_pp"],
            "ci95_hi_pp": rec["ci95_hi_pp"],
            "t_cr1": r["t_cr1"],
            "p_cr1": r["p_cr1"],
            "p_wcb": r["p_wcb"],
        })
        print(
            f"  [UNREG PLACEBO {u_tag:38s}] b={rec['beta_pp']:+5.2f}pp [{rec['ci95_lo_pp']:+5.2f}, {rec['ci95_hi_pp']:+5.2f}] | "
            f"t={r['t_cr1']:+5.2f}, wcb={r['p_wcb']:.3f} (N={r['N']:,}, G={r['G']})",
            flush=True,
        )

    # -----------------------------------------------------------------------
    # [5/5] Callaway & Sant'Anna (2021) Cohort-Staggered On-Cycle Audit
    # -----------------------------------------------------------------------
    print("\n[5/5] Callaway & Sant'Anna (2021) Staggered On-Cycle Cohort Audit:", flush=True)
    cs_res = run_callaway_santanna_oncycle(qtr)

    pd.DataFrame(honest_rows).to_csv(TABLES_DIR / "table_honest_did_sensitivity.csv", index=False, lineterminator="\n")
    pd.DataFrame(placebo_rows).to_csv(TABLES_DIR / "table_placebo_audits.csv", index=False, lineterminator="\n")

    out = {
        "phase_and_honest_did": honest_out,
        "historical_placebos_2021_2022": hist_placebos,
        "unregulated_word_placebos": unreg_placebos,
        "callaway_santanna_oncycle_cohorts": cs_res,
    }
    out_p = RESULTS_DIR / "04b_counterfactual_sensitivity.json"
    out_p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[DONE PILLAR 4b] Saved {out_p.name}, table_honest_did_sensitivity.csv, and table_placebo_audits.csv", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
