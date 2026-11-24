"""
Stage-0 Cheap Failure Test & Exact Certificate Verification
Route: Certified Rank-r Spectral Semi-Proximal Preconditioning for HPR-LP (Spec-HPR)
Directory: D:/AI_Science/antigravity/spectral_hpr_lp_20261124/

Implements apples-to-apples CPU (float64) comparators in the same sparse CSR/CSC engine:
  1. HPR-Native    : Restarted HPR-LP (arXiv:2611.01872, Alg 2, eqs 4-5, 18-23), box form, r=0
  2. HPR-Slack     : Restarted HPR-LP on equality-slack form, r=0 (isolates slack conversion)
  3. cuPDLPx-ASB   : Reflected Halpern PDHG + PID primal weight + Active-Set Step Size Boost
                     (arXiv:2507.14051 & cuPDLPx/algorithm/step-size.html)
  4. OnlineDiag-HPR: Online diagonal preconditioned PDHG (Lu & Zhang, arXiv:2506.17650)
  5. Spec-HPR(r)   : Certified Rank-r Spectral Semi-Proximal HPR (Theorems 1 & 3),
                     including full SVD+certification setup time in wall-clock timing,
                     plus gap-gated auto-trigger variant Spec-HPR-Auto.
  Ref: HiGHS exact LP solver (highspy) + OR-Tools PDLP sanity check.
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import highspy
import numpy as np
import scipy.linalg as sla
import scipy.sparse as sp


# =============================================================================
# 1. Data structures & exact original-space KKT evaluation
# =============================================================================

@dataclass
class LPInstance:
    name: str
    family: str
    A: sp.csr_matrix      # m x n
    c: np.ndarray         # n
    lc: np.ndarray        # m (can contain -np.inf)
    uc: np.ndarray        # m (can contain +np.inf)
    lv: np.ndarray        # n (can contain -np.inf)
    uv: np.ndarray        # n (can contain +np.inf)
    true_rank_spike: int = 0


def solve_highs_reference(lp: LPInstance) -> Tuple[str, float, float]:
    t0 = time.perf_counter()
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("threads", 1)
    m, n = lp.A.shape
    inf = highspy.kHighsInf
    lv = np.where(np.isfinite(lp.lv), lp.lv, -inf)
    uv = np.where(np.isfinite(lp.uv), lp.uv, inf)
    lc = np.where(np.isfinite(lp.lc), lp.lc, -inf)
    uc = np.where(np.isfinite(lp.uc), lp.uc, inf)
    h.addVars(n, lv, uv)
    h.changeColsCost(n, np.arange(n, dtype=np.int32), lp.c.astype(np.float64))
    A_csr = lp.A.tocsr()
    h.addRows(
        m,
        lc,
        uc,
        A_csr.nnz,
        A_csr.indptr.astype(np.int32),
        A_csr.indices.astype(np.int32),
        A_csr.data.astype(np.float64),
    )
    h.run()
    dt = time.perf_counter() - t0
    status = str(h.getModelStatus())
    obj = float(h.getInfo().objective_function_value)
    return status, obj, dt


def compute_b_hat(lc: np.ndarray, uc: np.ndarray) -> np.ndarray:
    b_l = np.where(np.isfinite(lc), np.abs(lc), 0.0)
    b_u = np.where(np.isfinite(uc), np.abs(uc), 0.0)
    return np.maximum(b_l, b_u)


def project_dual_cone(v: np.ndarray, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """Project dual variable onto valid dual cone for primal box [lo, hi] in HPR-LP sign convention.
    In HPR-LP (arXiv:2611.01872): -y in N_{[lo, hi]}(s).
      lo=-inf, hi=+inf => y = 0
      lo=-inf, hi<+inf => y <= 0
      lo>-inf, hi=+inf => y >= 0
      both finite      => y free
    """
    out = v.copy()
    lo_inf = ~np.isfinite(lo)
    hi_inf = ~np.isfinite(hi)
    out = np.where(lo_inf & hi_inf, 0.0, out)
    out = np.where(lo_inf & ~hi_inf, np.minimum(out, 0.0), out)
    out = np.where(~lo_inf & hi_inf, np.maximum(out, 0.0), out)
    return out


def evaluate_kkt_original(
    lp: LPInstance,
    x: np.ndarray,
    y: np.ndarray,
    norm_b: float,
    norm_c: float,
    AT: Optional[sp.csc_matrix] = None,
) -> Tuple[float, float, float, float, float]:
    """Exact original-space relative KKT residuals (HPR-LP / cuPDLPx convention)."""
    x_proj = np.clip(x, lp.lv, lp.uv)
    y_proj = project_dual_cone(y, lp.lc, lp.uc)
    Ax = lp.A @ x_proj
    Ax_proj = np.clip(Ax, lp.lc, lp.uc)
    rel_p = float(np.linalg.norm(Ax - Ax_proj) / (1.0 + norm_b))

    ATy = (lp.A.T @ y_proj) if AT is None else (AT @ y_proj)
    rc = lp.c - ATy
    z_proj = project_dual_cone(rc, lp.lv, lp.uv)
    rel_d = float(np.linalg.norm(rc - z_proj) / (1.0 + norm_c))

    p_obj = float(lp.c @ x_proj)
    y_pos = np.maximum(y_proj, 0.0)
    y_neg = np.maximum(-y_proj, 0.0)
    z_pos = np.maximum(z_proj, 0.0)
    z_neg = np.maximum(-z_proj, 0.0)

    lc_safe = np.where(np.isfinite(lp.lc), lp.lc, 0.0)
    uc_safe = np.where(np.isfinite(lp.uc), lp.uc, 0.0)
    lv_safe = np.where(np.isfinite(lp.lv), lp.lv, 0.0)
    uv_safe = np.where(np.isfinite(lp.uv), lp.uv, 0.0)

    d_obj = float(
        np.dot(lc_safe, y_pos)
        - np.dot(uc_safe, y_neg)
        + np.dot(lv_safe, z_pos)
        - np.dot(uv_safe, z_neg)
    )
    rel_gap = float(abs(p_obj - d_obj) / (1.0 + abs(p_obj) + abs(d_obj)))
    return rel_p, rel_d, rel_gap, p_obj, d_obj


# =============================================================================
# 2. Diagonal scaling pipeline: Ruiz(10) -> Pock-Chambolle -> bc (HPR-LP Sec 6)
# =============================================================================

@dataclass
class ScaledLP:
    A_csr: sp.csr_matrix
    AT_csr: sp.csr_matrix
    c: np.ndarray
    lc: np.ndarray
    uc: np.ndarray
    lv: np.ndarray
    uv: np.ndarray
    dr: np.ndarray       # total row scaling: A_tilde = diag(dr) A diag(dc)
    dc: np.ndarray       # total col scaling
    beta_b: float
    beta_c: float


def scale_lp_ruiz_pc_bc(
    A: sp.csr_matrix,
    c: np.ndarray,
    lc: np.ndarray,
    uc: np.ndarray,
    lv: np.ndarray,
    uv: np.ndarray,
    ruiz_iters: int = 10,
) -> ScaledLP:
    m, n = A.shape
    dr = np.ones(m, dtype=np.float64)
    dc = np.ones(n, dtype=np.float64)
    A_work = A.tocsr().astype(np.float64).copy()

    # Ruiz L_inf scaling
    for _ in range(ruiz_iters):
        # row inf norms
        abs_A = np.abs(A_work)
        r_norm = np.asarray(abs_A.max(axis=1).toarray()).ravel()
        r_div = np.where(r_norm > 1e-12, np.sqrt(r_norm), 1.0)
        c_norm = np.asarray(abs_A.max(axis=0).toarray()).ravel()
        c_div = np.where(c_norm > 1e-12, np.sqrt(c_norm), 1.0)
        # clamp cumulative factors to [1e-8, 1e8]
        new_dr = np.clip(dr / r_div, 1e-8, 1e8)
        new_dc = np.clip(dc / c_div, 1e-8, 1e8)
        step_r = new_dr / dr
        step_c = new_dc / dc
        dr, dc = new_dr, new_dc
        A_work = sp.diags(step_r) @ A_work @ sp.diags(step_c)

    # Pock-Chambolle alpha=1 scaling (eq 33 of 2611.01872)
    abs_A = np.abs(A_work)
    r_l1 = np.asarray(abs_A.sum(axis=1)).ravel()
    c_l1 = np.asarray(abs_A.sum(axis=0)).ravel()
    p_div = np.where(r_l1 > 1e-12, np.sqrt(r_l1), 1.0)
    d_div = np.where(c_l1 > 1e-12, np.sqrt(c_l1), 1.0)
    new_dr = np.clip(dr / p_div, 1e-8, 1e8)
    new_dc = np.clip(dc / d_div, 1e-8, 1e8)
    step_r = new_dr / dr
    step_c = new_dc / dc
    dr, dc = new_dr, new_dc
    A_work = (sp.diags(step_r) @ A_work @ sp.diags(step_c)).tocsr()

    # Transform vectors (eq 24 of 2611.01872)
    c_s = dc * c
    lc_s = dr * lc
    uc_s = dr * uc
    lv_s = lv / dc
    uv_s = uv / dc

    # bc normalization (eq 34 of 2611.01872)
    b_hat = compute_b_hat(lc_s, uc_s)
    beta_b = float(1.0 + np.linalg.norm(b_hat))
    beta_c = float(1.0 + np.linalg.norm(c_s))

    c_f = c_s / beta_c
    lc_f = lc_s / beta_b
    uc_f = uc_s / beta_b
    lv_f = lv_s / beta_b
    uv_f = uv_s / beta_b

    return ScaledLP(
        A_csr=A_work,
        AT_csr=A_work.T.tocsr(),
        c=c_f,
        lc=lc_f,
        uc=uc_f,
        lv=lv_f,
        uv=uv_f,
        dr=dr,
        dc=dc,
        beta_b=beta_b,
        beta_c=beta_c,
    )


def recover_xy(sc: ScaledLP, x_s: np.ndarray, y_s: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    # eq 34 then eq 25 of 2611.01872
    x = sc.dc * (sc.beta_b * x_s)
    y = sc.dr * (sc.beta_c * y_s)
    return x, y


def to_slack_equality_form(lp: LPInstance) -> Tuple[sp.csr_matrix, np.ndarray, np.ndarray, np.ndarray, np.ndarray, int]:
    """Convert l_c <= A x <= u_c to exact equality form A_hat [x; s] = b_hat
    by adding slack variables ONLY for non-equality rows (lc < uc).
    """
    m, n = lp.A.shape
    eq_mask = np.isfinite(lp.lc) & np.isfinite(lp.uc) & (np.abs(lp.uc - lp.lc) <= 1e-12)
    ineq_idx = np.where(~eq_mask)[0]
    n_slack = len(ineq_idx)

    if n_slack == 0:
        b = lp.lc.copy()
        return lp.A.tocsr(), lp.c.copy(), b, lp.lv.copy(), lp.uv.copy(), 0

    # Build [A, S] where S_{ineq_idx[k], k} = -1
    S = sp.coo_matrix(
        (-np.ones(n_slack, dtype=np.float64), (ineq_idx, np.arange(n_slack))),
        shape=(m, n_slack),
    ).tocsr()
    A_hat = sp.hstack([lp.A.tocsr(), S], format="csr")
    c_hat = np.concatenate([lp.c, np.zeros(n_slack, dtype=np.float64)])
    b_hat = np.where(eq_mask, lp.lc, 0.0)
    lv_hat = np.concatenate([lp.lv, lp.lc[ineq_idx]])
    uv_hat = np.concatenate([lp.uv, lp.uc[ineq_idx]])
    return A_hat, c_hat, b_hat, lv_hat, uv_hat, n_slack


# =============================================================================
# 3. Spectral norm & Theorem 3 Certified Rank-r Spectral Operator
# =============================================================================

def power_iteration_norm2(
    A: sp.csr_matrix, AT: sp.csr_matrix, max_iter: int = 40, tol: float = 1e-5, seed: int = 0
) -> float:
    m, _ = A.shape
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(m)
    v /= np.linalg.norm(v) + 1e-30
    lam = 0.0
    for _ in range(max_iter):
        u = AT @ v
        w = A @ u
        lam_new = float(v @ w)
        nw = float(np.linalg.norm(w))
        if nw < 1e-30:
            return 0.0
        v = w / nw
        if abs(lam_new - lam) <= tol * max(1.0, lam_new):
            lam = lam_new
            break
        lam = lam_new
    return float(math.sqrt(max(lam, 0.0)))


@dataclass
class CertifiedSpectralOperator:
    r: int
    U: np.ndarray            # m x r orthonormal Ritz vectors
    mu_cert: np.ndarray      # r certified eigenvalues >= theta2_cert
    theta2_cert: float       # certified bulk eigenvalue >= ||P_perp A||_2^2 + beta^2/eps
    woodbury_c: np.ndarray   # 1 - theta2_cert / mu_cert
    metric_diff: np.ndarray  # mu_cert - theta2_cert
    inv_theta2: float
    beta_residual: float
    s1_est: float
    spectral_ratio: float    # sqrt(mu_cert[0] / theta2_cert)
    setup_time: float
    exact_min_eig_T1: Optional[float] = None  # filled by exact audit on Stage-0 sizes


def build_certified_spectral_operator(
    A: sp.csr_matrix,
    AT: sp.csr_matrix,
    r: int,
    oversample: int = 4,
    q_power: int = 2,
    safety: float = 1.02,
    seed: int = 42,
    verify_exact_eig: bool = True,
) -> CertifiedSpectralOperator:
    t0 = time.perf_counter()
    m, n = A.shape
    r_eff = min(r, max(1, m - 2), max(1, n - 1))
    k = min(r_eff + oversample, m, n)
    rng = np.random.default_rng(seed)

    # Randomized subspace iteration on A A^T
    Omega = rng.standard_normal((n, k))
    Y = A @ Omega
    Q, _ = np.linalg.qr(Y, mode="reduced")
    for _ in range(q_power):
        Z = AT @ Q
        Y = A @ Z
        Q, _ = np.linalg.qr(Y, mode="reduced")

    # Rayleigh-Ritz on H = Q^T A A^T Q = V^T V
    V = AT @ Q                    # n x k
    G = V.T @ V                   # k x k
    G = 0.5 * (G + G.T)
    evals, evecs = np.linalg.eigh(G)
    idx = np.argsort(evals)[::-1]
    evals = np.maximum(evals[idx], 0.0)
    evecs = evecs[:, idx]

    # Top-r Ritz vectors and exact block residual R = (I - U U^T) A A^T U
    U = Q @ evecs[:, :r_eff]      # m x r_eff (orthonormal)
    mu = evals[:r_eff]
    V_r = V @ evecs[:, :r_eff]    # A^T U (no extra SpMV!)
    W_r = A @ V_r                 # A A^T U (r_eff SpMVs)
    # Exact projection residual
    UtW = U.T @ W_r               # should equal diag(mu) up to fp noise
    H_exact = 0.5 * (UtW + UtW.T)
    # Re-diagonalize if slight numerical drift
    mu_e, Q_e = np.linalg.eigh(H_exact)
    ord_e = np.argsort(mu_e)[::-1]
    mu = np.maximum(mu_e[ord_e], 0.0)
    Q_e = Q_e[:, ord_e]
    U = U @ Q_e
    W_r = W_r @ Q_e
    R = W_r - U * mu[None, :]     # m x r_eff, orthogonal to U

    # Compute exact beta = ||R diag(mu^{-1/2})||_2 over positive mu_i
    pos = mu > 1e-14
    if np.any(pos):
        inv_sqrt_mu = np.zeros_like(mu)
        inv_sqrt_mu[pos] = 1.0 / np.sqrt(mu[pos])
        R_scaled = R[:, pos] * inv_sqrt_mu[None, pos]
        RtR = R_scaled.T @ R_scaled
        RtR = 0.5 * (RtR + RtR.T)
        beta = float(math.sqrt(max(float(np.linalg.eigvalsh(RtR)[-1]), 0.0)))
    else:
        beta = 0.0

    # Deflated power iteration for ||(I - U U^T) A||_2^2
    # Warm-start from (r_eff+1)-th Ritz vector if available
    if k > r_eff:
        v = Q @ evecs[:, r_eff]
    else:
        v = rng.standard_normal(m)
    v = v - U @ (U.T @ v)
    nv = float(np.linalg.norm(v))
    if nv < 1e-12:
        v = rng.standard_normal(m)
        v = v - U @ (U.T @ v)
        nv = float(np.linalg.norm(v))
    v /= nv + 1e-30

    lam_perp = 0.0
    for _ in range(30):
        u_tmp = AT @ v
        w_tmp = A @ u_tmp
        w_tmp = w_tmp - U @ (U.T @ w_tmp)
        lam_new = float(v @ w_tmp)
        nw = float(np.linalg.norm(w_tmp))
        if nw < 1e-30:
            lam_perp = 0.0
            break
        v = w_tmp / nw
        if abs(lam_new - lam_perp) <= 1e-5 * max(1.0, lam_new):
            lam_perp = lam_new
            break
        lam_perp = lam_new
    # Also lower-bound by (r+1)-th Ritz value if k > r_eff
    if k > r_eff:
        lam_perp = max(lam_perp, float(evals[r_eff]))
    theta2_perp = safety * max(lam_perp, 1e-12)

    # Theorem 3 exact Schur-complement certificate
    if beta > 1e-15:
        eps = min(0.5, max(1e-7, beta / math.sqrt(theta2_perp)))
        theta2_cert = theta2_perp + (beta * beta) / eps
        mu_cert = np.maximum((1.0 + eps) * mu, theta2_cert)
    else:
        theta2_cert = theta2_perp
        mu_cert = np.maximum(mu, theta2_cert)

    # Tiny safety margin against floating-point rounding
    theta2_cert *= 1.0001
    mu_cert = np.maximum(mu_cert * 1.0001, theta2_cert)

    woodbury_c = 1.0 - theta2_cert / mu_cert
    metric_diff = mu_cert - theta2_cert
    inv_theta2 = 1.0 / theta2_cert
    s1_est = math.sqrt(max(float(mu_cert[0]), theta2_cert))
    spectral_ratio = s1_est / math.sqrt(theta2_cert)
    setup_time = time.perf_counter() - t0

    exact_min_eig = None
    if verify_exact_eig and m <= 800:
        AAt = (A @ AT).toarray()
        My = theta2_cert * np.eye(m) + (U * metric_diff[None, :]) @ U.T
        T1 = My - AAt
        T1 = 0.5 * (T1 + T1.T)
        exact_min_eig = float(sla.eigvalsh(T1)[0])

    return CertifiedSpectralOperator(
        r=r_eff,
        U=U,
        mu_cert=mu_cert,
        theta2_cert=theta2_cert,
        woodbury_c=woodbury_c,
        metric_diff=metric_diff,
        inv_theta2=inv_theta2,
        beta_residual=beta,
        s1_est=s1_est,
        spectral_ratio=spectral_ratio,
        setup_time=setup_time,
        exact_min_eig_T1=exact_min_eig,
    )


# =============================================================================
# 4. Solvers (All in identical sparse CSR/CSC engine, float64)
# =============================================================================

@dataclass
class SolveResult:
    method: str
    status: str
    iters: int
    iters_1e4: Optional[int]
    time_setup: float
    time_solve: float
    time_total: float
    rel_p: float
    rel_d: float
    rel_gap: float
    p_obj: float
    d_obj: float
    obj_rel_err: float
    restarts: int
    extra: Dict


def solve_hpr_native(
    lp: LPInstance,
    tol: float = 1e-6,
    max_iter: int = 25000,
    check_every: int = 40,
    f_star: Optional[float] = None,
) -> SolveResult:
    """Algorithm 2 of HPR-LP (arXiv:2611.01872), direct box-projection form, r=0."""
    t0 = time.perf_counter()
    sc = scale_lp_ruiz_pc_bc(lp.A, lp.c, lp.lc, lp.uc, lp.lv, lp.uv)
    A, AT = sc.A_csr, sc.AT_csr
    m, n = A.shape
    norm_A = power_iteration_norm2(A, AT, seed=0)
    lam_A = 1.002 * max(norm_A * norm_A, 1e-12)
    t_setup = time.perf_counter() - t0

    norm_b_orig = float(np.linalg.norm(compute_b_hat(lp.lc, lp.uc)))
    norm_c_orig = float(np.linalg.norm(lp.c))
    AT_orig = lp.A.T.tocsr()

    # Initial penalty sigma (HPR-LP balancing)
    sigma = 1.0 / max(math.sqrt(lam_A), 1e-8)
    x = np.zeros(n, dtype=np.float64)
    y = np.zeros(m, dtype=np.float64)
    x0 = x.copy()
    y0 = y.copy()

    t_solve_start = time.perf_counter()
    t_cycle = 0
    restarts = 0
    eps_r1 = None
    eps_prev = None
    iters_1e4 = None
    status = "MAX_ITER"
    rel_p = rel_d = rel_gap = p_obj = d_obj = float("nan")
    x_bar = x.copy()
    y_bar = y.copy()

    alpha1, alpha2, alpha3 = 0.2, 0.8, 0.36

    for k in range(1, max_iter + 1):
        # One HPR sweep (eq 5 of 2611.01872)
        ATy = AT @ y
        xi = x + sigma * (ATy - sc.c)
        x_bar = np.clip(xi, sc.lv, sc.uv)
        # Dual update
        x_ext = 2.0 * x_bar - x
        Ax_ext = A @ x_ext
        zeta = Ax_ext - (sigma * lam_A) * y
        y_bar = (np.clip(zeta, sc.lc, sc.uc) - zeta) / (sigma * lam_A)

        t_cycle += 1

        # Reflection + Halpern anchoring (Alg 2 lines 6-7)
        x_hat = 2.0 * x_bar - x
        y_hat = 2.0 * y_bar - y
        w_anchor = 1.0 / (t_cycle + 1)
        w_step = t_cycle / (t_cycle + 1)
        x_next = w_anchor * x0 + w_step * x_hat
        y_next = w_anchor * y0 + w_step * y_hat

        # Periodic KKT & restart check (every check_every iters, matching HPR-LP GPU cadence)
        if k % check_every == 0 or k == max_iter:
            # Evaluate exact sweep residual in M_sigma norm (eq 18 & 20)
            dx_s = x_bar - x
            dy_s = y_bar - y
            ATdy_s = AT @ dy_s
            m_sq = sigma * lam_A * float(dy_s @ dy_s) + 2.0 * float(ATdy_s @ dx_s) + float(dx_s @ dx_s) / sigma
            eps_curr = math.sqrt(max(m_sq, 0.0))

            # Termination test in original coordinates on (x_bar, y_bar)
            x_orig, y_orig = recover_xy(sc, x_bar, y_bar)
            rel_p, rel_d, rel_gap, p_obj, d_obj = evaluate_kkt_original(
                lp, x_orig, y_orig, norm_b_orig, norm_c_orig, AT_orig
            )
            max_res = max(rel_p, rel_d, rel_gap)
            if iters_1e4 is None and max_res <= 1e-4:
                iters_1e4 = k
            if max_res <= tol:
                status = "OPTIMAL"
                x, y = x_next, y_next
                break

            # Adaptive restart check (eq 19)
            if eps_r1 is None:
                eps_r1 = max(eps_curr, 1e-30)
            do_restart = False
            if t_cycle >= 2 * check_every:
                if eps_curr <= alpha1 * eps_r1:
                    do_restart = True
                elif eps_prev is not None and eps_curr <= alpha2 * eps_r1 and eps_curr > eps_prev:
                    do_restart = True
                elif t_cycle >= alpha3 * k:
                    do_restart = True
            eps_prev = eps_curr

            if do_restart:
                dx_c = float(np.linalg.norm(x_bar - x0))
                dy_c = math.sqrt(lam_A) * float(np.linalg.norm(y_bar - y0))
                if dx_c > 1e-14 and dy_c > 1e-14:
                    sigma_cand = dx_c / dy_c
                    # Geometric smoothing & clamping safeguard (HPR-LP Sec 4.2)
                    sigma_new = math.exp(0.5 * math.log(sigma) + 0.5 * math.log(sigma_cand))
                    sigma = float(np.clip(sigma_new, 1e-7, 1e7))
                x0 = x_bar.copy()
                y0 = y_bar.copy()
                x = x_bar.copy()
                y = y_bar.copy()
                t_cycle = 0
                eps_r1 = None
                eps_prev = None
                restarts += 1
                continue

        x, y = x_next, y_next

    t_solve = time.perf_counter() - t_solve_start
    obj_err = abs(p_obj - f_star) / max(1.0, abs(f_star)) if f_star is not None else float("nan")
    return SolveResult(
        method="HPR-Native",
        status=status,
        iters=k,
        iters_1e4=iters_1e4,
        time_setup=t_setup,
        time_solve=t_solve,
        time_total=t_setup + t_solve,
        rel_p=rel_p,
        rel_d=rel_d,
        rel_gap=rel_gap,
        p_obj=p_obj,
        d_obj=d_obj,
        obj_rel_err=obj_err,
        restarts=restarts,
        extra={"norm_A_scaled": norm_A},
    )


def solve_hpr_slack_or_spectral(
    lp: LPInstance,
    rank: int = 0,
    gap_gate: Optional[float] = None,
    tol: float = 1e-6,
    max_iter: int = 25000,
    check_every: int = 40,
    f_star: Optional[float] = None,
    verify_exact_eig: bool = True,
) -> SolveResult:
    """Restarted HPR-LP on equality-slack standard form with either:
      - rank == 0 : scalar T1^(0) = lam_A I - A A^T  (HPR-Slack)
      - rank  > 0 : Certified Rank-r Spectral T1^(r,cert) = M_y^(r,cert) - A A^T (Spec-HPR)
    If gap_gate is set and spectral_ratio < gap_gate, falls back to HPR-Native (charging setup cost!).
    """
    t0 = time.perf_counter()
    n_orig = lp.A.shape[1]
    A_hat, c_hat, b_hat, lv_hat, uv_hat, n_slack = to_slack_equality_form(lp)
    sc = scale_lp_ruiz_pc_bc(A_hat, c_hat, b_hat, b_hat, lv_hat, uv_hat)
    A, AT = sc.A_csr, sc.AT_csr
    b_s = sc.lc  # equality constraint: lc == uc
    m, n = A.shape

    spec_op: Optional[CertifiedSpectralOperator] = None
    if rank > 0:
        spec_op = build_certified_spectral_operator(
            A, AT, r=rank, oversample=4, q_power=2, safety=1.02, seed=42, verify_exact_eig=verify_exact_eig
        )
        if gap_gate is not None and spec_op.spectral_ratio < gap_gate:
            # Pay the setup time honestly, then delegate to HPR-Native!
            t_gate = time.perf_counter() - t0
            res = solve_hpr_native(lp, tol=tol, max_iter=max_iter, check_every=check_every, f_star=f_star)
            res.method = f"Spec-HPR-Auto(r={rank})"
            res.time_setup += t_gate
            res.time_total = res.time_setup + res.time_solve
            res.extra["gate_triggered"] = False
            res.extra["spectral_ratio"] = spec_op.spectral_ratio
            res.extra["exact_min_eig_T1"] = spec_op.exact_min_eig_T1
            return res
        lam_ref = spec_op.theta2_cert
    else:
        norm_A = power_iteration_norm2(A, AT, seed=0)
        lam_ref = 1.002 * max(norm_A * norm_A, 1e-12)

    t_setup = time.perf_counter() - t0

    norm_b_orig = float(np.linalg.norm(compute_b_hat(lp.lc, lp.uc)))
    norm_c_orig = float(np.linalg.norm(lp.c))
    AT_orig = lp.A.T.tocsr()

    sigma = 1.0 / max(math.sqrt(lam_ref), 1e-8)
    x = np.zeros(n, dtype=np.float64)
    y = np.zeros(m, dtype=np.float64)
    x0 = x.copy()
    y0 = y.copy()

    t_solve_start = time.perf_counter()
    t_cycle = 0
    restarts = 0
    eps_r1 = None
    eps_prev = None
    iters_1e4 = None
    status = "MAX_ITER"
    rel_p = rel_d = rel_gap = p_obj = d_obj = float("nan")
    x_bar = x.copy()
    y_bar = y.copy()

    alpha1, alpha2, alpha3 = 0.2, 0.8, 0.36

    if spec_op is not None:
        U = spec_op.U
        UT = np.ascontiguousarray(U.T)
        wc = spec_op.woodbury_c
        md = spec_op.metric_diff
        th2 = spec_op.theta2_cert
        inv_th2 = spec_op.inv_theta2

    for k in range(1, max_iter + 1):
        ATy = AT @ y
        xi = x + sigma * (ATy - sc.c)
        x_bar = np.clip(xi, sc.lv, sc.uv)

        x_ext = 2.0 * x_bar - x
        res_p = b_s - (A @ x_ext)
        if spec_op is None:
            y_bar = y + (1.0 / (sigma * lam_ref)) * res_p
        else:
            # Matrix-free Woodbury dual sweep: M_y^{-1} res_p in 2*m*r FLOPs
            u_dot = UT @ res_p
            y_bar = y + (inv_th2 / sigma) * (res_p - U @ (wc * u_dot))

        t_cycle += 1

        x_hat = 2.0 * x_bar - x
        y_hat = 2.0 * y_bar - y
        w_anchor = 1.0 / (t_cycle + 1)
        w_step = t_cycle / (t_cycle + 1)
        x_next = w_anchor * x0 + w_step * x_hat
        y_next = w_anchor * y0 + w_step * y_hat

        if k % check_every == 0 or k == max_iter:
            dx_s = x_bar - x
            dy_s = y_bar - y
            ATdy_s = AT @ dy_s
            if spec_op is None:
                y_My_y = lam_ref * float(dy_s @ dy_s)
            else:
                u_dy = UT @ dy_s
                y_My_y = th2 * float(dy_s @ dy_s) + float(np.sum(md * (u_dy * u_dy)))
            m_sq = sigma * y_My_y + 2.0 * float(ATdy_s @ dx_s) + float(dx_s @ dx_s) / sigma
            eps_curr = math.sqrt(max(m_sq, 0.0))

            # Recover ORIGINAL LP variables (drop slacks; project y onto original dual cone)
            x_full_orig, y_orig = recover_xy(sc, x_bar, y_bar)
            x_orig = x_full_orig[:n_orig]
            rel_p, rel_d, rel_gap, p_obj, d_obj = evaluate_kkt_original(
                lp, x_orig, y_orig, norm_b_orig, norm_c_orig, AT_orig
            )
            max_res = max(rel_p, rel_d, rel_gap)
            if iters_1e4 is None and max_res <= 1e-4:
                iters_1e4 = k
            if max_res <= tol:
                status = "OPTIMAL"
                x, y = x_next, y_next
                break

            if eps_r1 is None:
                eps_r1 = max(eps_curr, 1e-30)
            do_restart = False
            if t_cycle >= 2 * check_every:
                if eps_curr <= alpha1 * eps_r1:
                    do_restart = True
                elif eps_prev is not None and eps_curr <= alpha2 * eps_r1 and eps_curr > eps_prev:
                    do_restart = True
                elif t_cycle >= alpha3 * k:
                    do_restart = True
            eps_prev = eps_curr

            if do_restart:
                dx_c = float(np.linalg.norm(x_bar - x0))
                dy_vec = y_bar - y0
                if spec_op is None:
                    dy_c = math.sqrt(lam_ref) * float(np.linalg.norm(dy_vec))
                else:
                    u_dyc = UT @ dy_vec
                    dy_c = math.sqrt(max(th2 * float(dy_vec @ dy_vec) + float(np.sum(md * (u_dyc * u_dyc))), 0.0))
                if dx_c > 1e-14 and dy_c > 1e-14:
                    sigma_cand = dx_c / dy_c
                    sigma_new = math.exp(0.5 * math.log(sigma) + 0.5 * math.log(sigma_cand))
                    sigma = float(np.clip(sigma_new, 1e-7, 1e7))
                x0 = x_bar.copy()
                y0 = y_bar.copy()
                x = x_bar.copy()
                y = y_bar.copy()
                t_cycle = 0
                eps_r1 = None
                eps_prev = None
                restarts += 1
                continue

        x, y = x_next, y_next

    t_solve = time.perf_counter() - t_solve_start
    obj_err = abs(p_obj - f_star) / max(1.0, abs(f_star)) if f_star is not None else float("nan")
    if rank == 0:
        mname = "HPR-Slack"
    elif gap_gate is not None:
        mname = f"Spec-HPR-Auto(r={rank})"
    else:
        mname = f"Spec-HPR(r={rank})"

    extra = {"n_slack": n_slack}
    if spec_op is not None:
        extra.update(
            {
                "gate_triggered": True,
                "spectral_ratio": spec_op.spectral_ratio,
                "beta_residual": spec_op.beta_residual,
                "s1_est": spec_op.s1_est,
                "theta_cert": math.sqrt(spec_op.theta2_cert),
                "exact_min_eig_T1": spec_op.exact_min_eig_T1,
            }
        )
    else:
        extra["norm_A_scaled"] = math.sqrt(lam_ref / 1.002)

    return SolveResult(
        method=mname,
        status=status,
        iters=k,
        iters_1e4=iters_1e4,
        time_setup=t_setup,
        time_solve=t_solve,
        time_total=t_setup + t_solve,
        rel_p=rel_p,
        rel_d=rel_d,
        rel_gap=rel_gap,
        p_obj=p_obj,
        d_obj=d_obj,
        obj_rel_err=obj_err,
        restarts=restarts,
        extra=extra,
    )


def solve_cupdlpx_asb(
    lp: LPInstance,
    tol: float = 1e-6,
    max_iter: int = 25000,
    check_every: int = 40,
    asb_window: int = 400,
    f_star: Optional[float] = None,
) -> SolveResult:
    """cuPDLPx-style Reflected Halpern PDHG (arXiv:2507.14051) + PID primal weight
    + Active-Set Step Size Boost (ASB) per mit-lu-lab.github.io/cuPDLPx/algorithm/step-size.html.
    """
    t0 = time.perf_counter()
    sc = scale_lp_ruiz_pc_bc(lp.A, lp.c, lp.lc, lp.uc, lp.lv, lp.uv)
    A, AT = sc.A_csr, sc.AT_csr
    m, n = A.shape
    norm_A = power_iteration_norm2(A, AT, seed=0)
    eta0 = 0.998 / max(norm_A, 1e-12)
    eta = eta0
    eta_ceil = float("inf")
    omega = 1.0
    t_setup = time.perf_counter() - t0

    norm_b_orig = float(np.linalg.norm(compute_b_hat(lp.lc, lp.uc)))
    norm_c_orig = float(np.linalg.norm(lp.c))
    AT_orig = lp.A.T.tocsr()

    # PID primal weight state
    KP, KI, KD = 0.3, 0.05, 0.05
    e_int = 0.0
    e_prev = 0.0

    # ASB tracking state
    var_excl_streak = np.zeros(n, dtype=np.int32)
    con_excl_streak = np.zeros(m, dtype=np.int32)
    finite_lv = np.isfinite(sc.lv)
    finite_uv = np.isfinite(sc.uv)
    fixed_v = finite_lv & finite_uv & (np.abs(sc.uv - sc.lv) <= 1e-12)
    finite_lc = np.isfinite(sc.lc)
    finite_uc = np.isfinite(sc.uc)
    ineq_c = ~(finite_lc & finite_uc & (np.abs(sc.uc - sc.lc) <= 1e-12))
    eps_r_asb = 1e-8
    eps_c_asb = 1e-8
    c_scale = np.maximum(1.0, np.abs(sc.c))

    asb_active = False
    asb_disabled = False
    asb_boosts = 0
    asb_rollbacks = 0
    asb_max_ratio = 1.0
    asb_power_iters = 0
    asb_v_warm = np.ones(m, dtype=np.float64) / math.sqrt(max(m, 1))
    saved_state = None
    epoch_r0 = None

    x = np.zeros(n, dtype=np.float64)
    y = np.zeros(m, dtype=np.float64)
    x0 = x.copy()
    y0 = y.copy()

    t_solve_start = time.perf_counter()
    t_cycle = 0
    restarts = 0
    r_first = None
    r_prev = None
    iters_1e4 = None
    status = "MAX_ITER"
    rel_p = rel_d = rel_gap = p_obj = d_obj = float("nan")
    x_bar = x.copy()
    y_bar = y.copy()

    def fixed_point_err(dx: np.ndarray, dy: np.ndarray, eta_eval: float, omega_eval: float) -> float:
        # P_{eta, omega} norm in cuPDLPx (same as M_sigma with sigma = eta/omega, lam_A = 1/eta^2)
        ATdy = AT @ dy
        val = (
            (omega_eval / eta_eval) * float(dx @ dx)
            + (1.0 / (eta_eval * omega_eval)) * float(dy @ dy)
            + 2.0 * float(ATdy @ dx)
        )
        return math.sqrt(max(val, 0.0))

    for k in range(1, max_iter + 1):
        tau = eta / omega
        sig = eta * omega

        ATy = AT @ y
        xi = x + tau * (ATy - sc.c)
        x_bar = np.clip(xi, sc.lv, sc.uv)
        x_ext = 2.0 * x_bar - x
        Ax_ext = A @ x_ext
        # cuPDLPx/HPR sign-equivalent dual projection
        zeta = Ax_ext - (1.0 / sig) * y
        y_bar = sig * (np.clip(zeta, sc.lc, sc.uc) - zeta)

        t_cycle += 1

        # Reflected Halpern (gamma = 1)
        x_hat = 2.0 * x_bar - x
        y_hat = 2.0 * y_bar - y
        w_a = 1.0 / (t_cycle + 1)
        w_s = t_cycle / (t_cycle + 1)
        x_next = w_a * x0 + w_s * x_hat
        y_next = w_a * y0 + w_s * y_hat

        if k % check_every == 0 or k == max_iter:
            # Update ASB exclusion streaks per cuPDLPx docs
            r_tilde = sc.c - ATy + (x_bar - x) / tau
            v_excl = fixed_v | (finite_lv & (r_tilde > eps_r_asb * c_scale)) | (
                finite_uv & (r_tilde < -eps_r_asb * c_scale)
            )
            var_excl_streak = np.where(v_excl, var_excl_streak + check_every, 0)

            # In HPR sign convention, zeta = A(2x_bar - x) - y/sig, interior of [lc, uc] gives y_bar=0
            c_excl = ineq_c.copy()
            c_excl &= (~finite_uc) | ((sc.uc - zeta) > eps_c_asb * np.maximum(1.0, np.maximum(np.abs(zeta), np.abs(sc.uc))))
            c_excl &= (~finite_lc) | ((zeta - sc.lc) > eps_c_asb * np.maximum(1.0, np.maximum(np.abs(zeta), np.abs(sc.lc))))
            con_excl_streak = np.where(c_excl, con_excl_streak + check_every, 0)

            dx_s = x_bar - x
            dy_s = y_bar - y
            r_curr = fixed_point_err(dx_s, dy_s, eta0, omega)

            # Divergence protection while eta > eta0 (cuPDLPx docs: r(z^k) > 1.05 * r(z^0))
            if eta > eta0 and saved_state is not None:
                if epoch_r0 is None:
                    epoch_r0 = max(r_curr, 1e-30)
                if (not np.isfinite(r_curr)) or (r_curr > 1.05 * epoch_r0):
                    # Rollback!
                    eta_ceil = min(eta_ceil, 0.7 * eta)
                    eta = eta0
                    x0, y0, omega, e_int, e_prev = saved_state
                    x0 = x0.copy()
                    y0 = y0.copy()
                    x = x0.copy()
                    y = y0.copy()
                    t_cycle = 0
                    r_first = None
                    r_prev = None
                    epoch_r0 = None
                    asb_rollbacks += 1
                    if asb_rollbacks >= 2:
                        asb_disabled = True
                    continue

            # Original-space KKT termination check
            x_orig, y_orig = recover_xy(sc, x_bar, y_bar)
            rel_p, rel_d, rel_gap, p_obj, d_obj = evaluate_kkt_original(
                lp, x_orig, y_orig, norm_b_orig, norm_c_orig, AT_orig
            )
            max_res = max(rel_p, rel_d, rel_gap)
            if iters_1e4 is None and max_res <= 1e-4:
                iters_1e4 = k
            if max_res <= tol:
                status = "OPTIMAL"
                x, y = x_next, y_next
                break

            if (not asb_disabled) and (not asb_active) and (max_res <= 1e-4):
                if np.any(var_excl_streak >= asb_window) or np.any(con_excl_streak >= asb_window):
                    asb_active = True

            if r_first is None:
                r_first = max(r_curr, 1e-30)
            do_restart = False
            if t_cycle >= 2 * check_every:
                if r_curr <= 0.2 * r_first:
                    do_restart = True
                elif r_prev is not None and r_curr <= 0.8 * r_first and r_curr > r_prev:
                    do_restart = True
                elif t_cycle >= 0.36 * k:
                    do_restart = True
            r_prev = r_curr

            if do_restart:
                dx_c = float(np.linalg.norm(x_bar - x0))
                dy_c = float(np.linalg.norm(y_bar - y0))
                if dx_c > 1e-14 and dy_c > 1e-14:
                    # cuPDLPx PID primal weight controller
                    e_n = math.log((math.sqrt(omega) * dx_c) / ((1.0 / math.sqrt(omega)) * dy_c))
                    e_int = float(np.clip(e_int + e_n, -20.0, 20.0))
                    de_n = e_n - e_prev
                    log_w = math.log(omega) - (KP * e_n + KI * e_int + KD * de_n)
                    omega = float(np.exp(np.clip(log_w, -12.0, 12.0)))
                    e_prev = e_n

                x0 = x_bar.copy()
                y0 = y_bar.copy()
                x = x_bar.copy()
                y = y_bar.copy()
                t_cycle = 0
                r_first = None
                r_prev = None
                epoch_r0 = None
                restarts += 1

                # ASB step-size boost at adaptive restart
                if asb_active and (not asb_disabled):
                    F_mask = (var_excl_streak < asb_window).astype(np.float64)
                    B_mask = (con_excl_streak < asb_window).astype(np.float64)
                    if np.sum(B_mask) > 0 and np.sum(F_mask) > 0:
                        # Masked warm-started power iteration for ||A_{B,F}||_2
                        v_m = asb_v_warm * B_mask
                        nv_m = float(np.linalg.norm(v_m))
                        if nv_m < 1e-12:
                            v_m = B_mask.copy()
                            nv_m = float(np.linalg.norm(v_m))
                        v_m /= nv_m + 1e-30
                        sig_est = 0.0
                        for _ in range(15):
                            asb_power_iters += 1
                            u_m = (AT @ v_m) * F_mask
                            w_m = (A @ u_m) * B_mask
                            lam_m = float(v_m @ w_m)
                            nw_m = float(np.linalg.norm(w_m))
                            if nw_m < 1e-30:
                                sig_est = 0.0
                                break
                            v_m = w_m / nw_m
                            sig_est = math.sqrt(max(lam_m, 0.0))
                        asb_v_warm = v_m
                        if sig_est > 1e-12:
                            eta_plus = max(eta0, min(0.9 / sig_est, eta_ceil))
                            if eta_plus > eta and eta_plus >= 1.1 * eta:
                                saved_state = (x0.copy(), y0.copy(), omega, e_int, e_prev)
                                eta = eta_plus
                                asb_boosts += 1
                                asb_max_ratio = max(asb_max_ratio, eta / eta0)
                continue

        x, y = x_next, y_next

    t_solve = time.perf_counter() - t_solve_start
    obj_err = abs(p_obj - f_star) / max(1.0, abs(f_star)) if f_star is not None else float("nan")
    return SolveResult(
        method="cuPDLPx-ASB",
        status=status,
        iters=k,
        iters_1e4=iters_1e4,
        time_setup=t_setup,
        time_solve=t_solve,
        time_total=t_setup + t_solve,
        rel_p=rel_p,
        rel_d=rel_d,
        rel_gap=rel_gap,
        p_obj=p_obj,
        d_obj=d_obj,
        obj_rel_err=obj_err,
        restarts=restarts,
        extra={
            "asb_boosts": asb_boosts,
            "asb_rollbacks": asb_rollbacks,
            "asb_max_eta_ratio": asb_max_ratio,
            "asb_power_iters": asb_power_iters,
        },
    )


def solve_online_diag_pdhg(
    lp: LPInstance,
    lr: float = 1e-3,
    phi: int = 20,
    tol: float = 1e-6,
    max_iter: int = 25000,
    check_every: int = 40,
    f_star: Optional[float] = None,
) -> SolveResult:
    """Lu & Zhang (arXiv:2506.17650) Online Diagonal Preconditioning with AdaGrad &
    normalized Lagrangian feedback, integrated on top of Ruiz+PC-scaled Halpern PDHG.
    """
    t0 = time.perf_counter()
    sc = scale_lp_ruiz_pc_bc(lp.A, lp.c, lp.lc, lp.uc, lp.lv, lp.uv)
    A, AT = sc.A_csr, sc.AT_csr
    m, n = A.shape
    norm_A = power_iteration_norm2(A, AT, seed=0)
    eta = 0.998 / max(norm_A, 1e-12)
    omega = 1.0
    t_setup = time.perf_counter() - t0

    norm_b_orig = float(np.linalg.norm(compute_b_hat(lp.lc, lp.uc)))
    norm_c_orig = float(np.linalg.norm(lp.c))
    AT_orig = lp.A.T.tocsr()

    # Diagonal relative preconditioner weights initialized to 1 (projected to [0.2, 5.0])
    dp = np.ones(n, dtype=np.float64)
    dd = np.ones(m, dtype=np.float64)
    Gp = np.full(n, 1e-8, dtype=np.float64)
    Gd = np.full(m, 1e-8, dtype=np.float64)

    x = np.zeros(n, dtype=np.float64)
    y = np.zeros(m, dtype=np.float64)
    x0 = x.copy()
    y0 = y.copy()

    t_solve_start = time.perf_counter()
    t_cycle = 0
    restarts = 0
    r_first = None
    r_prev = None
    iters_1e4 = None
    status = "MAX_ITER"
    rel_p = rel_d = rel_gap = p_obj = d_obj = float("nan")
    x_bar = x.copy()
    y_bar = y.copy()

    for k in range(1, max_iter + 1):
        # Conservative rescaling factor so diagonal updates preserve spectral bound
        scale_guard = 1.0 / math.sqrt(float(np.max(dp) * np.max(dd)))
        tau_vec = (eta * scale_guard / omega) * dp
        sig_vec = (eta * scale_guard * omega) * dd

        ATy = AT @ y
        grad_p = sc.c - ATy
        xi = x - tau_vec * grad_p
        x_bar = np.clip(xi, sc.lv, sc.uv)

        x_ext = 2.0 * x_bar - x
        Ax_ext = A @ x_ext
        inv_sig = 1.0 / sig_vec
        zeta = Ax_ext - inv_sig * y
        y_bar = sig_vec * (np.clip(zeta, sc.lc, sc.uc) - zeta)

        # Infrequent online diagonal preconditioner update (Lu & Zhang Sec 3.2)
        if k % phi == 0:
            active_p = ((xi >= sc.lv) & (xi <= sc.uv)).astype(np.float64)
            gp_raw = -(grad_p * active_p) * grad_p
            ngp = float(np.linalg.norm(gp_raw))
            if ngp > 1e-14:
                gp = gp_raw / ngp
                Gp += gp * gp
                dp = np.clip(dp - lr * gp / np.sqrt(Gp), 0.25, 4.0)
                dp /= float(np.mean(dp))

            Ax_cur = A @ x
            r_cur = np.clip(Ax_cur, sc.lc, sc.uc) - Ax_cur
            r_ext = np.clip(Ax_ext, sc.lc, sc.uc) - Ax_ext
            gd_raw = -(r_cur * r_ext)
            ngd = float(np.linalg.norm(gd_raw))
            if ngd > 1e-14:
                gd = gd_raw / ngd
                Gd += gd * gd
                dd = np.clip(dd - lr * gd / np.sqrt(Gd), 0.25, 4.0)
                dd /= float(np.mean(dd))

        t_cycle += 1
        x_hat = 2.0 * x_bar - x
        y_hat = 2.0 * y_bar - y
        w_a = 1.0 / (t_cycle + 1)
        w_s = t_cycle / (t_cycle + 1)
        x_next = w_a * x0 + w_s * x_hat
        y_next = w_a * y0 + w_s * y_hat

        if k % check_every == 0 or k == max_iter:
            dx_s = x_bar - x
            dy_s = y_bar - y
            ATdy_s = AT @ dy_s
            val = (omega / eta) * float(dx_s @ dx_s) + (1.0 / (eta * omega)) * float(dy_s @ dy_s) + 2.0 * float(ATdy_s @ dx_s)
            r_curr = math.sqrt(max(val, 0.0))

            x_orig, y_orig = recover_xy(sc, x_bar, y_bar)
            rel_p, rel_d, rel_gap, p_obj, d_obj = evaluate_kkt_original(
                lp, x_orig, y_orig, norm_b_orig, norm_c_orig, AT_orig
            )
            max_res = max(rel_p, rel_d, rel_gap)
            if iters_1e4 is None and max_res <= 1e-4:
                iters_1e4 = k
            if max_res <= tol:
                status = "OPTIMAL"
                x, y = x_next, y_next
                break

            if r_first is None:
                r_first = max(r_curr, 1e-30)
            do_restart = False
            if t_cycle >= 2 * check_every:
                if r_curr <= 0.2 * r_first:
                    do_restart = True
                elif r_prev is not None and r_curr <= 0.8 * r_first and r_curr > r_prev:
                    do_restart = True
                elif t_cycle >= 0.36 * k:
                    do_restart = True
            r_prev = r_curr

            if do_restart:
                dx_c = float(np.linalg.norm(x_bar - x0))
                dy_c = float(np.linalg.norm(y_bar - y0))
                if dx_c > 1e-14 and dy_c > 1e-14:
                    w_cand = dy_c / dx_c
                    omega = float(np.clip(math.exp(0.5 * math.log(omega) + 0.5 * math.log(w_cand)), 1e-5, 1e5))
                x0 = x_bar.copy()
                y0 = y_bar.copy()
                x = x_bar.copy()
                y = y_bar.copy()
                t_cycle = 0
                r_first = None
                r_prev = None
                restarts += 1
                continue

        x, y = x_next, y_next

    t_solve = time.perf_counter() - t_solve_start
    obj_err = abs(p_obj - f_star) / max(1.0, abs(f_star)) if f_star is not None else float("nan")
    return SolveResult(
        method="OnlineDiag-HPR",
        status=status,
        iters=k,
        iters_1e4=iters_1e4,
        time_setup=t_setup,
        time_solve=t_solve,
        time_total=t_setup + t_solve,
        rel_p=rel_p,
        rel_d=rel_d,
        rel_gap=rel_gap,
        p_obj=p_obj,
        d_obj=d_obj,
        obj_rel_err=obj_err,
        restarts=restarts,
        extra={"dp_spread": float(np.max(dp) / np.min(dp)), "dd_spread": float(np.max(dd) / np.min(dd))},
    )


# =============================================================================
# 5. Theorem-2 Numerical Verification & Synthetic Benchmark Generators
# =============================================================================

def verify_theorem2_numerically(m: int = 64, rho: float = 0.5, trials: int = 1000, seed: int = 123) -> Dict:
    rng = np.random.default_rng(seed)
    M = (1.0 - rho) * np.eye(m) + rho * np.ones((m, m))
    lb = (m - 1) * rho / (1.0 - rho)
    min_kappa = float("inf")
    violations = 0
    for _ in range(trials):
        r = np.exp(rng.uniform(-4.0, 4.0, size=m))
        c = np.exp(rng.uniform(-4.0, 4.0, size=m))
        s = np.linalg.svd((r[:, None] * M) * c[None, :], compute_uv=False)
        kappa = float(s[0] / s[-1])
        if kappa < min_kappa:
            min_kappa = kappa
        if kappa <= lb:
            violations += 1
    # Check Ruiz scaling on M_rho
    s_id = np.linalg.svd(M, compute_uv=False)
    # Check rank-1 spectral operator M_y^(1) on M_rho
    u1 = np.ones(m) / math.sqrt(m)
    s1, s2 = float(s_id[0]), float(s_id[1])
    My1 = (s2 ** 2) * np.eye(m) + (s1 ** 2 - s2 ** 2) * np.outer(u1, u1)
    T1 = My1 - M @ M.T
    T1_norm = float(np.linalg.norm(T1, 2))
    return {
        "m": m,
        "rho": rho,
        "theoretical_lower_bound": lb,
        "kappa_unscaled_identity": float(s_id[0] / s_id[-1]),
        "min_kappa_over_1000_random_diags": min_kappa,
        "violations": violations,
        "rank1_T1_spectral_norm": T1_norm,
    }


def make_f1_factor_eq(name: str, m: int, n: int, rank_k: int, factor_strength: float, seed: int) -> LPInstance:
    """Family 1: Equality-only factor-coupled resource allocation LP (Theorem 2 regime).
    Every row has a sparse local component + shared low-rank dense factor columns so Ruiz+PC
    leaves a clean rank-k spectral spike inside the equality block (ASB cannot drop any row).
    """
    rng = np.random.default_rng(seed)
    # Sparse balanced local block (m x (n - n_fac))
    n_fac = max(rank_k * 20, 40)
    n_loc = n - n_fac
    rows, cols, vals = [], [], []
    # Each local column touches 3 random rows
    for j in range(n_loc):
        r_idx = rng.choice(m, size=3, replace=False)
        rows.extend(r_idx.tolist())
        cols.extend([j] * 3)
        vals.extend(rng.uniform(0.5, 1.5, size=3).tolist())
    A_loc = sp.coo_matrix((vals, (rows, cols)), shape=(m, n_loc)).tocsr()

    # Low-rank factor columns coupling all m rows (structured nonnegative factors)
    P = np.abs(rng.standard_normal((m, rank_k))) + 0.5
    P /= np.linalg.norm(P, axis=0, keepdims=True)
    Q = rng.uniform(0.3, 1.2, size=(rank_k, n_fac))
    A_fac_dense = factor_strength * (P @ Q)
    A = sp.hstack([A_loc, sp.csr_matrix(A_fac_dense)], format="csr")

    # Guaranteed interior strictly feasible primal x_true in (0, u)
    uv = rng.uniform(2.0, 5.0, size=n)
    lv = np.zeros(n)
    x_true = rng.uniform(0.25, 0.75, size=n) * uv
    b = A @ x_true
    # Construct nontrivial dual-coupled cost so optimal vertex is nontrivial
    y_hint = rng.standard_normal(m)
    c = A.T @ y_hint + rng.uniform(-1.0, 2.0, size=n)
    return LPInstance(name=name, family="F1_FactorEq", A=A, c=c, lc=b, uc=b.copy(), lv=lv, uv=uv, true_rank_spike=rank_k)


def make_f2_linked_mcf(name: str, n_nodes: int, n_arcs: int, n_comm: int, n_hub_ineq: int, seed: int) -> LPInstance:
    """Family 2: Multi-commodity flow (equality flow conservation) + shared arc capacity
    and dense hub-budget inequality constraints (mixed equality + inequality LP).
    """
    rng = np.random.default_rng(seed)
    # Build connected directed graph
    edges = [(i, (i + 1) % n_nodes) for i in range(n_nodes)]
    edge_set = set(edges)
    while len(edges) < n_arcs:
        u = int(rng.integers(0, n_nodes))
        v = int(rng.integers(0, n_nodes))
        if u != v and (u, v) not in edge_set:
            edge_set.add((u, v))
            edges.append((u, v))
    n_arcs = len(edges)
    n = n_comm * n_arcs

    # Block-diagonal node-arc incidence (drop 1 redundant node per commodity)
    inc_rows, inc_cols, inc_vals = [], [], []
    for k in range(n_comm):
        r_off = k * (n_nodes - 1)
        c_off = k * n_arcs
        for e_idx, (u, v) in enumerate(edges):
            if u < n_nodes - 1:
                inc_rows.append(r_off + u)
                inc_cols.append(c_off + e_idx)
                inc_vals.append(1.0)
            if v < n_nodes - 1:
                inc_rows.append(r_off + v)
                inc_cols.append(c_off + e_idx)
                inc_vals.append(-1.0)
    m_eq = n_comm * (n_nodes - 1)
    A_eq = sp.coo_matrix((inc_vals, (inc_rows, inc_cols)), shape=(m_eq, n)).tocsr()

    # Shared arc capacity inequalities: sum_k x_{k,e} <= cap_e
    cap_rows, cap_cols, cap_vals = [], [], []
    for e_idx in range(n_arcs):
        for k in range(n_comm):
            cap_rows.append(e_idx)
            cap_cols.append(k * n_arcs + e_idx)
            cap_vals.append(1.0)
    A_cap = sp.coo_matrix((cap_vals, (cap_rows, cap_cols)), shape=(n_arcs, n)).tocsr()

    # Shared dense regional/hub budget constraints (coupling commodities & arcs)
    A_hub = sp.csr_matrix(rng.uniform(0.2, 1.0, size=(n_hub_ineq, n)))

    A = sp.vstack([A_eq, A_cap, A_hub], format="csr")
    uv = np.full(n, 4.0)
    lv = np.zeros(n)
    x_true = rng.uniform(0.15, 0.55, size=n) * uv
    b_eq = A_eq @ x_true
    cap_rhs = (A_cap @ x_true) * rng.uniform(1.05, 1.35, size=n_arcs)
    hub_rhs = (A_hub @ x_true) * rng.uniform(1.02, 1.15, size=n_hub_ineq)

    lc = np.concatenate([b_eq, np.full(n_arcs + n_hub_ineq, -np.inf)])
    uc = np.concatenate([b_eq, cap_rhs, hub_rhs])
    c = rng.uniform(0.5, 5.0, size=n)
    return LPInstance(name=name, family="F2_LinkedMCF", A=A, c=c, lc=lc, uc=uc, lv=lv, uv=uv, true_rank_spike=n_hub_ineq)


def make_f3_factor_ineq(name: str, m: int, n: int, rank_k: int, factor_strength: float, seed: int) -> LPInstance:
    """Family 3: 100% inequality LP (Ax <= b, 0 <= x <= u) with sparse local block +
    shared rank-k nonnegative factor coupling across rows (tests slack-conversion penalty!).
    """
    rng = np.random.default_rng(seed)
    n_fac = max(rank_k * 20, 40)
    n_loc = n - n_fac
    rows, cols, vals = [], [], []
    for j in range(n_loc):
        r_idx = rng.choice(m, size=4, replace=False)
        rows.extend(r_idx.tolist())
        cols.extend([j] * 4)
        vals.extend(rng.uniform(0.5, 1.5, size=4).tolist())
    A_loc = sp.coo_matrix((vals, (rows, cols)), shape=(m, n_loc)).tocsr()

    P = np.abs(rng.standard_normal((m, rank_k))) + 0.5
    P /= np.linalg.norm(P, axis=0, keepdims=True)
    Q = rng.uniform(0.3, 1.2, size=(rank_k, n_fac))
    A = sp.hstack([A_loc, sp.csr_matrix(factor_strength * (P @ Q))], format="csr")

    uv = rng.uniform(2.0, 5.0, size=n)
    lv = np.zeros(n)
    x_true = rng.uniform(0.3, 0.7, size=n) * uv
    # Make ~60% of rows tight or near-tight so active set retains the factor spike
    slack_mult = np.where(rng.random(m) < 0.65, rng.uniform(1.00, 1.04, size=m), rng.uniform(1.15, 1.5, size=m))
    b = (A @ x_true) * slack_mult
    # Maximize profit => minimize negative c
    c = -rng.uniform(0.5, 3.0, size=n)
    lc = np.full(m, -np.inf)
    return LPInstance(name=name, family="F3_FactorIneq", A=A, c=c, lc=lc, uc=b, lv=lv, uv=uv, true_rank_spike=rank_k)


def make_f4_flat_control(name: str, m: int, n: int, eq_frac: float, seed: int) -> LPInstance:
    """Family 4: Flat-spectrum sparse random LP control (no spectral spike after Ruiz+PC)."""
    rng = np.random.default_rng(seed)
    nnz_per_col = 5
    rows, cols, vals = [], [], []
    for j in range(n):
        r_idx = rng.choice(m, size=nnz_per_col, replace=False)
        rows.extend(r_idx.tolist())
        cols.extend([j] * nnz_per_col)
        vals.extend(rng.standard_normal(nnz_per_col).tolist())
    A = sp.coo_matrix((vals, (rows, cols)), shape=(m, n)).tocsr()

    uv = rng.uniform(2.0, 5.0, size=n)
    lv = np.zeros(n)
    x_true = rng.uniform(0.25, 0.75, size=n) * uv
    Ax = A @ x_true
    m_eq = int(round(m * eq_frac))
    lc = np.concatenate([Ax[:m_eq], np.full(m - m_eq, -np.inf)])
    uc = np.concatenate([Ax[:m_eq], Ax[m_eq:] + rng.uniform(0.2, 2.0, size=m - m_eq)])
    c = rng.standard_normal(n)
    return LPInstance(name=name, family="F4_FlatControl", A=A, c=c, lc=lc, uc=uc, lv=lv, uv=uv, true_rank_spike=0)


def build_stage0_suite() -> List[LPInstance]:
    return [
        # F1: Equality-only factor-coupled (Theorem 2 home turf)
        make_f1_factor_eq("f1_eq_m300_k1", m=300, n=900, rank_k=1, factor_strength=4.0, seed=101),
        make_f1_factor_eq("f1_eq_m400_k4", m=400, n=1200, rank_k=4, factor_strength=4.5, seed=102),
        make_f1_factor_eq("f1_eq_m500_k8", m=500, n=1500, rank_k=8, factor_strength=5.0, seed=103),
        # F2: Multi-commodity flow + shared arc capacities & dense hub budgets (mixed eq + ineq)
        make_f2_linked_mcf("f2_mcf_small", n_nodes=25, n_arcs=90, n_comm=8, n_hub_ineq=4, seed=201),
        make_f2_linked_mcf("f2_mcf_med", n_nodes=30, n_arcs=120, n_comm=10, n_hub_ineq=6, seed=202),
        make_f2_linked_mcf("f2_mcf_large", n_nodes=35, n_arcs=140, n_comm=10, n_hub_ineq=8, seed=203),
        # F3: 100% inequality factor-coupled allocation (slack-conversion stress test)
        make_f3_factor_ineq("f3_ineq_m300_k2", m=300, n=900, rank_k=2, factor_strength=4.0, seed=301),
        make_f3_factor_ineq("f3_ineq_m400_k4", m=400, n=1200, rank_k=4, factor_strength=4.5, seed=302),
        make_f3_factor_ineq("f3_ineq_m500_k8", m=500, n=1500, rank_k=8, factor_strength=5.0, seed=303),
        # F4: Flat-spectrum sparse controls (negative/overhead safety control)
        make_f4_flat_control("f4_flat_eq300", m=300, n=900, eq_frac=1.0, seed=401),
        make_f4_flat_control("f4_flat_mix400", m=400, n=1200, eq_frac=0.5, seed=402),
        make_f4_flat_control("f4_flat_ineq400", m=400, n=1200, eq_frac=0.0, seed=403),
    ]


# =============================================================================
# 6. Runner & Pre-Registered Gate Evaluation
# =============================================================================

def geom_mean(vals: List[float], shift: float = 0.0) -> float:
    arr = np.array(vals, dtype=np.float64) + shift
    return float(np.exp(np.mean(np.log(np.maximum(arr, 1e-12)))) - shift)


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\spectral_hpr_lp_20261124")
    out_dir.mkdir(parents=True, exist_ok=True)

    print("=== STEP 1: Theorem 2 Diagonal-Impossibility Numerical Verification ===")
    thm2 = verify_theorem2_numerically(m=64, rho=0.5, trials=1000, seed=123)
    print(json.dumps(thm2, indent=2))
    assert thm2["violations"] == 0, "Theorem 2 violated!"
    assert thm2["rank1_T1_spectral_norm"] < 1e-12, "Rank-1 collapse failed!"

    print("\n=== STEP 2: Running Stage-0 Bounded Suite (12 instances, tol=1e-6, max_iter=25000) ===")
    suite = build_stage0_suite()
    all_records = []
    min_eig_all = []

    for lp in suite:
        h_status, f_star, h_time = solve_highs_reference(lp)
        print(f"\n--- {lp.name} ({lp.family}) shape={lp.A.shape} nnz={lp.A.nnz} | HiGHS={h_status} f*={f_star:.6f} ({h_time:.3f}s) ---")
        assert "kOptimal" in h_status, f"HiGHS not optimal on {lp.name}: {h_status}"

        r_spec = 8 if lp.true_rank_spike <= 6 else 12
        runs = [
            solve_hpr_native(lp, tol=1e-6, max_iter=25000, f_star=f_star),
            solve_hpr_slack_or_spectral(lp, rank=0, tol=1e-6, max_iter=25000, f_star=f_star),
            solve_cupdlpx_asb(lp, tol=1e-6, max_iter=25000, asb_window=400, f_star=f_star),
            solve_online_diag_pdhg(lp, lr=1e-3, phi=20, tol=1e-6, max_iter=25000, f_star=f_star),
            solve_hpr_slack_or_spectral(lp, rank=r_spec, gap_gate=None, tol=1e-6, max_iter=25000, f_star=f_star, verify_exact_eig=True),
            solve_hpr_slack_or_spectral(lp, rank=r_spec, gap_gate=1.5, tol=1e-6, max_iter=25000, f_star=f_star, verify_exact_eig=True),
        ]

        inst_rec = {
            "name": lp.name,
            "family": lp.family,
            "m": lp.A.shape[0],
            "n": lp.A.shape[1],
            "nnz": int(lp.A.nnz),
            "r_spec": r_spec,
            "highs_f_star": f_star,
            "highs_time": h_time,
            "runs": {},
        }
        for res in runs:
            key = res.method.split("(")[0] if res.method.startswith("Spec-HPR-Auto") else (
                "Spec-HPR" if res.method.startswith("Spec-HPR(") else res.method
            )
            inst_rec["runs"][key] = asdict(res)
            if "exact_min_eig_T1" in res.extra and res.extra["exact_min_eig_T1"] is not None:
                min_eig_all.append(res.extra["exact_min_eig_T1"])
            extra_str = ""
            if "spectral_ratio" in res.extra:
                extra_str = f" ratio={res.extra['spectral_ratio']:.2f} gate={res.extra.get('gate_triggered')} minEigT1={res.extra.get('exact_min_eig_T1', 0):.2e}"
            elif "asb_boosts" in res.extra:
                extra_str = f" asb_boosts={res.extra['asb_boosts']} maxEta={res.extra['asb_max_eta_ratio']:.2f} rb={res.extra['asb_rollbacks']}"
            print(
                f"  {key:15s} | {res.status:8s} | it={res.iters:5d} (1e-4:{str(res.iters_1e4):>5s}) "
                f"| tot={res.time_total:6.3f}s (set={res.time_setup:.3f}s) "
                f"| kkt={max(res.rel_p, res.rel_d, res.rel_gap):.2e} | objErr={res.obj_rel_err:.2e}{extra_str}"
            )
        all_records.append(inst_rec)

    # Aggregate family summaries and gate verdicts
    families = ["F1_FactorEq", "F2_LinkedMCF", "F3_FactorIneq", "F4_FlatControl"]
    summary = {}
    print("\n=== STEP 3: Family-Level Geometric Mean Summaries ===")
    for fam in families:
        recs = [r for r in all_records if r["family"] == fam]
        fam_sum = {}
        for key in ["HPR-Native", "HPR-Slack", "cuPDLPx-ASB", "OnlineDiag-HPR", "Spec-HPR", "Spec-HPR-Auto"]:
            iters_list = [r["runs"][key]["iters"] for r in recs]
            time_list = [r["runs"][key]["time_total"] for r in recs]
            opt_cnt = sum(1 for r in recs if r["runs"][key]["status"] == "OPTIMAL")
            fam_sum[key] = {
                "opt_count": opt_cnt,
                "n_instances": len(recs),
                "gm_iters": geom_mean(iters_list),
                "gm_time": geom_mean(time_list),
            }
        # Speedups of Spec-HPR and Spec-HPR-Auto over HPR-Native and cuPDLPx-ASB
        fam_sum["speedup_Spec_vs_Native_iter"] = fam_sum["HPR-Native"]["gm_iters"] / fam_sum["Spec-HPR"]["gm_iters"]
        fam_sum["speedup_Spec_vs_Native_time"] = fam_sum["HPR-Native"]["gm_time"] / fam_sum["Spec-HPR"]["gm_time"]
        fam_sum["speedup_Spec_vs_ASB_iter"] = fam_sum["cuPDLPx-ASB"]["gm_iters"] / fam_sum["Spec-HPR"]["gm_iters"]
        fam_sum["speedup_Spec_vs_ASB_time"] = fam_sum["cuPDLPx-ASB"]["gm_time"] / fam_sum["Spec-HPR"]["gm_time"]
        fam_sum["overhead_Auto_vs_Native_time"] = fam_sum["Spec-HPR-Auto"]["gm_time"] / fam_sum["HPR-Native"]["gm_time"]
        summary[fam] = fam_sum
        print(
            f"{fam:14s} | Spec vs Native: {fam_sum['speedup_Spec_vs_Native_iter']:.2f}x iters, "
            f"{fam_sum['speedup_Spec_vs_Native_time']:.2f}x time | "
            f"Spec vs ASB: {fam_sum['speedup_Spec_vs_ASB_iter']:.2f}x iters, "
            f"{fam_sum['speedup_Spec_vs_ASB_time']:.2f}x time | "
            f"Auto/Native time: {fam_sum['overhead_Auto_vs_Native_time']:.3f}x"
        )

    # Pre-registered gate check
    cert_pass = (thm2["violations"] == 0) and (len(min_eig_all) > 0) and (min(min_eig_all) >= -1e-11)
    f1_pass = (
        summary["F1_FactorEq"]["speedup_Spec_vs_Native_iter"] >= 2.0
        and summary["F1_FactorEq"]["speedup_Spec_vs_Native_time"] >= 1.5
        and summary["F1_FactorEq"]["speedup_Spec_vs_ASB_iter"] >= 2.0
        and summary["F1_FactorEq"]["speedup_Spec_vs_ASB_time"] >= 1.5
    )
    f4_pass = summary["F4_FlatControl"]["overhead_Auto_vs_Native_time"] <= 1.05
    verdict = {
        "cert_pass": cert_pass,
        "min_exact_eig_T1_across_suite": float(min(min_eig_all)) if min_eig_all else None,
        "falsifier1_F1_home_turf_pass": f1_pass,
        "falsifier2_F4_flat_safety_pass": f4_pass,
        "F2_mcf_spec_vs_native_time": summary["F2_LinkedMCF"]["speedup_Spec_vs_Native_time"],
        "F3_ineq_spec_vs_native_time": summary["F3_FactorIneq"]["speedup_Spec_vs_Native_time"],
    }
    print("\n=== STEP 4: Pre-Registered Gate Verdicts ===")
    print(json.dumps(verdict, indent=2))

    payload = {
        "theorem2_verification": thm2,
        "verdict": verdict,
        "family_summary": summary,
        "instances": all_records,
    }
    res_path = out_dir / "stage0_results.json"
    res_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"\nSaved full JSON results to {res_path}")


if __name__ == "__main__":
    main()
