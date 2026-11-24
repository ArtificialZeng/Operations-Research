"""
Stage-0b Matched Internal Ablation (Exact Total Sparse-Pass Accounting) & Official Runnable Comparator Check
Directory: D:/AI_Science/antigravity/spectral_hpr_lp_20261124/

Does NOT modify any sealed stage0_* files; imports the exact 12 instances and unscaled KKT evaluator
from stage0_cheap_failure_test.py and wraps EVERY sparse matrix operation in a CountedSparseOp so that:
  - scaling passes (Ruiz + Pock-Chambolle sweeps),
  - setup passes (power iteration OR randomized SVD + exact Theorem-3 Schur certification + deflated power iter),
  - solve sweep passes (A @ x and A^T @ y),
  - KKT / restart residual check passes (A @ x, A^T @ y, A^T @ dy),
  - ASB masked power-iteration passes
are ALL counted explicitly in `spmv_total = spmv_setup + spmv_solve + spmv_kkt + spmv_asb`.

Also records official runnable C++ comparators on the exact same 12 unscaled LPs at tol=1e-6:
  - HiGHS 1.16.0 (`solver="pdlp"`, presolve="off" AND default)
  - Google OR-Tools 9.15.6755 (`PDLP`, presolve off AND default)
CPU prototype results do NOT establish a GPU leaderboard; hardware & comparator paths are recorded explicitly.
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
import scipy.sparse as sp
from ortools.linear_solver import pywraplp

from stage0_cheap_failure_test import (
    LPInstance,
    build_stage0_suite,
    compute_b_hat,
    evaluate_kkt_original,
    project_dual_cone,
    recover_xy,
    solve_highs_reference,
    to_slack_equality_form,
)


class SparsePassCounter:
    def __init__(self):
        self.scaling = 0
        self.setup = 0
        self.sweep = 0
        self.kkt_restart = 0
        self.asb_power = 0

    @property
    def total(self) -> int:
        return self.scaling + self.setup + self.sweep + self.kkt_restart + self.asb_power

    def to_dict(self) -> Dict[str, int]:
        return {
            "scaling": self.scaling,
            "setup": self.setup,
            "sweep": self.sweep,
            "kkt_restart": self.kkt_restart,
            "asb_power": self.asb_power,
            "total": self.total,
        }


def counted_matvec(M: sp.csr_matrix, v: np.ndarray, cnt: SparsePassCounter, bucket: str) -> np.ndarray:
    k = 1 if v.ndim == 1 else v.shape[1]
    setattr(cnt, bucket, getattr(cnt, bucket) + int(k))
    return M @ v


def scale_lp_counted(
    A: sp.csr_matrix,
    c: np.ndarray,
    lc: np.ndarray,
    uc: np.ndarray,
    lv: np.ndarray,
    uv: np.ndarray,
    cnt: SparsePassCounter,
    ruiz_iters: int = 10,
):
    from stage0_cheap_failure_test import ScaledLP

    m, n = A.shape
    dr = np.ones(m, dtype=np.float64)
    dc = np.ones(n, dtype=np.float64)
    A_work = A.tocsr().astype(np.float64).copy()

    # Each Ruiz iteration scans A once for row max & once for col max (2 sparse passes)
    for _ in range(ruiz_iters):
        cnt.scaling += 2
        abs_A = np.abs(A_work)
        r_norm = np.asarray(abs_A.max(axis=1).toarray()).ravel()
        r_div = np.where(r_norm > 1e-12, np.sqrt(r_norm), 1.0)
        c_norm = np.asarray(abs_A.max(axis=0).toarray()).ravel()
        c_div = np.where(c_norm > 1e-12, np.sqrt(c_norm), 1.0)
        new_dr = np.clip(dr / r_div, 1e-8, 1e8)
        new_dc = np.clip(dc / c_div, 1e-8, 1e8)
        step_r = new_dr / dr
        step_c = new_dc / dc
        dr, dc = new_dr, new_dc
        A_work = sp.diags(step_r) @ A_work @ sp.diags(step_c)

    # Pock-Chambolle scan (2 sparse passes)
    cnt.scaling += 2
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

    c_s = dc * c
    lc_s = dr * lc
    uc_s = dr * uc
    lv_s = lv / dc
    uv_s = uv / dc

    b_hat = compute_b_hat(lc_s, uc_s)
    beta_b = float(1.0 + np.linalg.norm(b_hat))
    beta_c = float(1.0 + np.linalg.norm(c_s))
    return ScaledLP(
        A_csr=A_work,
        AT_csr=A_work.T.tocsr(),
        c=c_s / beta_c,
        lc=lc_s / beta_b,
        uc=uc_s / beta_b,
        lv=lv_s / beta_b,
        uv=uv_s / beta_b,
        dr=dr,
        dc=dc,
        beta_b=beta_b,
        beta_c=beta_c,
    )


def power_norm_counted(A: sp.csr_matrix, AT: sp.csr_matrix, cnt: SparsePassCounter, max_iter: int = 40) -> float:
    m, _ = A.shape
    rng = np.random.default_rng(0)
    v = rng.standard_normal(m)
    v /= np.linalg.norm(v) + 1e-30
    lam = 0.0
    for _ in range(max_iter):
        u = counted_matvec(AT, v, cnt, "setup")
        w = counted_matvec(A, u, cnt, "setup")
        lam_new = float(v @ w)
        nw = float(np.linalg.norm(w))
        if nw < 1e-30:
            return 0.0
        v = w / nw
        if abs(lam_new - lam) <= 1e-5 * max(1.0, lam_new):
            lam = lam_new
            break
        lam = lam_new
    return float(math.sqrt(max(lam, 0.0)))


def build_spec_counted(A: sp.csr_matrix, AT: sp.csr_matrix, r: int, cnt: SparsePassCounter, q_power: int = 2):
    m, n = A.shape
    r_eff = min(r, max(1, m - 2), max(1, n - 1))
    k = min(r_eff + 4, m, n)
    rng = np.random.default_rng(42)

    Omega = rng.standard_normal((n, k))
    Y = counted_matvec(A, Omega, cnt, "setup")
    Q, _ = np.linalg.qr(Y, mode="reduced")
    for _ in range(q_power):
        Z = counted_matvec(AT, Q, cnt, "setup")
        Y = counted_matvec(A, Z, cnt, "setup")
        Q, _ = np.linalg.qr(Y, mode="reduced")

    V = counted_matvec(AT, Q, cnt, "setup")
    G = 0.5 * (V.T @ V + (V.T @ V).T)
    evals, evecs = np.linalg.eigh(G)
    idx = np.argsort(evals)[::-1]
    evals = np.maximum(evals[idx], 0.0)
    evecs = evecs[:, idx]

    U = Q @ evecs[:, :r_eff]
    V_r = V @ evecs[:, :r_eff]
    W_r = counted_matvec(A, V_r, cnt, "setup")
    H_exact = 0.5 * (U.T @ W_r + (U.T @ W_r).T)
    mu_e, Q_e = np.linalg.eigh(H_exact)
    ord_e = np.argsort(mu_e)[::-1]
    mu = np.maximum(mu_e[ord_e], 0.0)
    Q_e = Q_e[:, ord_e]
    U = U @ Q_e
    W_r = W_r @ Q_e
    R = W_r - U * mu[None, :]

    pos = mu > 1e-14
    if np.any(pos):
        inv_sqrt_mu = np.zeros_like(mu)
        inv_sqrt_mu[pos] = 1.0 / np.sqrt(mu[pos])
        R_scaled = R[:, pos] * inv_sqrt_mu[None, pos]
        RtR = 0.5 * (R_scaled.T @ R_scaled + (R_scaled.T @ R_scaled).T)
        beta = float(math.sqrt(max(float(np.linalg.eigvalsh(RtR)[-1]), 0.0)))
    else:
        beta = 0.0

    v = (Q @ evecs[:, r_eff]) if k > r_eff else rng.standard_normal(m)
    v = v - U @ (U.T @ v)
    v /= np.linalg.norm(v) + 1e-30
    lam_perp = 0.0
    for _ in range(30):
        u_t = counted_matvec(AT, v, cnt, "setup")
        w_t = counted_matvec(A, u_t, cnt, "setup")
        w_t = w_t - U @ (U.T @ w_t)
        lam_new = float(v @ w_t)
        nw = float(np.linalg.norm(w_t))
        if nw < 1e-30:
            lam_perp = 0.0
            break
        v = w_t / nw
        if abs(lam_new - lam_perp) <= 1e-5 * max(1.0, lam_new):
            lam_perp = lam_new
            break
        lam_perp = lam_new
    if k > r_eff:
        lam_perp = max(lam_perp, float(evals[r_eff]))
    theta2_perp = 1.02 * max(lam_perp, 1e-12)
    if beta > 1e-15:
        eps = min(0.5, max(1e-7, beta / math.sqrt(theta2_perp)))
        theta2_cert = (theta2_perp + (beta * beta) / eps) * 1.0001
        mu_cert = np.maximum((1.0 + eps) * mu * 1.0001, theta2_cert)
    else:
        theta2_cert = theta2_perp * 1.0001
        mu_cert = np.maximum(mu * 1.0001, theta2_cert)

    return {
        "U": U,
        "UT": np.ascontiguousarray(U.T),
        "theta2": theta2_cert,
        "inv_theta2": 1.0 / theta2_cert,
        "wc": 1.0 - theta2_cert / mu_cert,
        "md": mu_cert - theta2_cert,
        "ratio": math.sqrt(max(float(mu_cert[0]), theta2_cert) / theta2_cert),
    }


def eval_kkt_counted(lp: LPInstance, x: np.ndarray, y: np.ndarray, norm_b: float, norm_c: float, AT_orig: sp.csr_matrix, cnt: SparsePassCounter):
    cnt.kkt_restart += 2  # A @ x_proj and AT @ y_proj
    return evaluate_kkt_original(lp, x, y, norm_b, norm_c, AT_orig)


def run_internal_ablation_arm(
    lp: LPInstance,
    mode: str,  # "HPR-Native", "HPR-Slack", "Spec-HPR", "cuPDLPx-ASB"
    rank: int = 8,
    tol: float = 1e-6,
    max_iter: int = 25000,
    check_every: int = 40,
    asb_window: int = 400,
) -> Dict:
    cnt = SparsePassCounter()
    t0 = time.perf_counter()
    n_orig = lp.A.shape[1]
    norm_b_orig = float(np.linalg.norm(compute_b_hat(lp.lc, lp.uc)))
    norm_c_orig = float(np.linalg.norm(lp.c))
    AT_orig = lp.A.T.tocsr()

    use_slack = mode in ("HPR-Slack", "Spec-HPR")
    if use_slack:
        A_hat, c_hat, b_hat, lv_hat, uv_hat, _ = to_slack_equality_form(lp)
        sc = scale_lp_counted(A_hat, c_hat, b_hat, b_hat, lv_hat, uv_hat, cnt)
    else:
        sc = scale_lp_counted(lp.A, lp.c, lp.lc, lp.uc, lp.lv, lp.uv, cnt)

    A, AT = sc.A_csr, sc.AT_csr
    m, n = A.shape

    spec = None
    if mode == "Spec-HPR":
        spec = build_spec_counted(A, AT, rank, cnt)
        lam_ref = spec["theta2"]
        eta0 = 1.0 / math.sqrt(lam_ref)
    else:
        norm_A = power_norm_counted(A, AT, cnt)
        lam_ref = 1.002 * max(norm_A * norm_A, 1e-12)
        eta0 = 0.998 / max(norm_A, 1e-12)

    t_setup = time.perf_counter() - t0
    t_solve_start = time.perf_counter()

    x = np.zeros(n, dtype=np.float64)
    y = np.zeros(m, dtype=np.float64)
    x0 = x.copy()
    y0 = y.copy()

    sigma = 1.0 / max(math.sqrt(lam_ref), 1e-8)
    eta = eta0
    eta_ceil = float("inf")
    omega = 1.0
    e_int = 0.0
    e_prev = 0.0

    # ASB state (only used when mode == "cuPDLPx-ASB")
    var_excl = np.zeros(n, dtype=np.int32)
    con_excl = np.zeros(m, dtype=np.int32)
    finite_lv, finite_uv = np.isfinite(sc.lv), np.isfinite(sc.uv)
    fixed_v = finite_lv & finite_uv & (np.abs(sc.uv - sc.lv) <= 1e-12)
    finite_lc, finite_uc = np.isfinite(sc.lc), np.isfinite(sc.uc)
    ineq_c = ~(finite_lc & finite_uc & (np.abs(sc.uc - sc.lc) <= 1e-12))
    c_scale = np.maximum(1.0, np.abs(sc.c))
    asb_active = False
    asb_disabled = False
    asb_boosts = 0
    asb_rollbacks = 0
    asb_v_warm = np.ones(m, dtype=np.float64) / math.sqrt(max(m, 1))
    saved_state = None
    epoch_r0 = None

    t_cycle = 0
    restarts = 0
    r_first = None
    r_prev = None
    spmv_1e4 = None
    iters_1e4 = None
    status = "MAX_ITER"
    rel_p = rel_d = rel_gap = p_obj = d_obj = float("nan")

    for k in range(1, max_iter + 1):
        ATy = counted_matvec(AT, y, cnt, "sweep")
        if mode == "cuPDLPx-ASB":
            tau = eta / omega
            sig_d = eta * omega
            xi = x + tau * (ATy - sc.c)
            x_bar = np.clip(xi, sc.lv, sc.uv)
            Ax_ext = counted_matvec(A, 2.0 * x_bar - x, cnt, "sweep")
            zeta = Ax_ext - (1.0 / sig_d) * y
            y_bar = sig_d * (np.clip(zeta, sc.lc, sc.uc) - zeta)
        else:
            xi = x + sigma * (ATy - sc.c)
            x_bar = np.clip(xi, sc.lv, sc.uv)
            Ax_ext = counted_matvec(A, 2.0 * x_bar - x, cnt, "sweep")
            if mode == "HPR-Native":
                zeta = Ax_ext - (sigma * lam_ref) * y
                y_bar = (np.clip(zeta, sc.lc, sc.uc) - zeta) / (sigma * lam_ref)
            elif mode == "HPR-Slack":
                y_bar = y + (1.0 / (sigma * lam_ref)) * (sc.lc - Ax_ext)
            else:
                res_p = sc.lc - Ax_ext
                u_dot = spec["UT"] @ res_p
                y_bar = y + (spec["inv_theta2"] / sigma) * (res_p - spec["U"] @ (spec["wc"] * u_dot))

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
            ATdy_s = counted_matvec(AT, dy_s, cnt, "kkt_restart")

            if mode == "cuPDLPx-ASB":
                r_tilde = sc.c - ATy + (x_bar - x) / tau
                v_excl = fixed_v | (finite_lv & (r_tilde > 1e-8 * c_scale)) | (finite_uv & (r_tilde < -1e-8 * c_scale))
                var_excl = np.where(v_excl, var_excl + check_every, 0)
                c_excl = ineq_c.copy()
                c_excl &= (~finite_uc) | ((sc.uc - zeta) > 1e-8 * np.maximum(1.0, np.maximum(np.abs(zeta), np.abs(sc.uc))))
                c_excl &= (~finite_lc) | ((zeta - sc.lc) > 1e-8 * np.maximum(1.0, np.maximum(np.abs(zeta), np.abs(sc.lc))))
                con_excl = np.where(c_excl, con_excl + check_every, 0)

                r_curr = math.sqrt(
                    max(
                        (omega / eta0) * float(dx_s @ dx_s)
                        + (1.0 / (eta0 * omega)) * float(dy_s @ dy_s)
                        + 2.0 * float(ATdy_s @ dx_s),
                        0.0,
                    )
                )
                if eta > eta0 and saved_state is not None:
                    if epoch_r0 is None:
                        epoch_r0 = max(r_curr, 1e-30)
                    if (not np.isfinite(r_curr)) or (r_curr > 1.05 * epoch_r0):
                        eta_ceil = min(eta_ceil, 0.7 * eta)
                        eta = eta0
                        x0, y0, omega, e_int, e_prev = saved_state
                        x0, y0 = x0.copy(), y0.copy()
                        x, y = x0.copy(), y0.copy()
                        t_cycle = 0
                        r_first = r_prev = epoch_r0 = None
                        asb_rollbacks += 1
                        if asb_rollbacks >= 2:
                            asb_disabled = True
                        continue
            elif mode == "Spec-HPR":
                u_dy = spec["UT"] @ dy_s
                y_My_y = spec["theta2"] * float(dy_s @ dy_s) + float(np.sum(spec["md"] * (u_dy * u_dy)))
                r_curr = math.sqrt(max(sigma * y_My_y + 2.0 * float(ATdy_s @ dx_s) + float(dx_s @ dx_s) / sigma, 0.0))
            else:
                r_curr = math.sqrt(
                    max(sigma * lam_ref * float(dy_s @ dy_s) + 2.0 * float(ATdy_s @ dx_s) + float(dx_s @ dx_s) / sigma, 0.0)
                )

            x_rec, y_rec = recover_xy(sc, x_bar, y_bar)
            rel_p, rel_d, rel_gap, p_obj, d_obj = eval_kkt_counted(
                lp, x_rec[:n_orig], y_rec, norm_b_orig, norm_c_orig, AT_orig, cnt
            )
            max_res = max(rel_p, rel_d, rel_gap)
            if iters_1e4 is None and max_res <= 1e-4:
                iters_1e4 = k
                spmv_1e4 = cnt.total
            if max_res <= tol:
                status = "OPTIMAL"
                break

            if mode == "cuPDLPx-ASB" and (not asb_disabled) and (not asb_active) and max_res <= 1e-4:
                if np.any(var_excl >= asb_window) or np.any(con_excl >= asb_window):
                    asb_active = True

            if r_first is None:
                r_first = max(r_curr, 1e-30)
            do_restart = False
            if t_cycle >= 2 * check_every:
                if r_curr <= 0.2 * r_first or (r_prev is not None and r_curr <= 0.8 * r_first and r_curr > r_prev) or t_cycle >= 0.36 * k:
                    do_restart = True
            r_prev = r_curr

            if do_restart:
                dx_c = float(np.linalg.norm(x_bar - x0))
                if mode == "cuPDLPx-ASB":
                    dy_c = float(np.linalg.norm(y_bar - y0))
                    if dx_c > 1e-14 and dy_c > 1e-14:
                        e_n = math.log((math.sqrt(omega) * dx_c) / ((1.0 / math.sqrt(omega)) * dy_c))
                        e_int = float(np.clip(e_int + e_n, -20.0, 20.0))
                        omega = float(np.exp(np.clip(math.log(omega) - (0.3 * e_n + 0.05 * e_int + 0.05 * (e_n - e_prev)), -12.0, 12.0)))
                        e_prev = e_n
                else:
                    dy_vec = y_bar - y0
                    if mode == "Spec-HPR":
                        u_dyc = spec["UT"] @ dy_vec
                        dy_c = math.sqrt(max(spec["theta2"] * float(dy_vec @ dy_vec) + float(np.sum(spec["md"] * (u_dyc * u_dyc))), 0.0))
                    else:
                        dy_c = math.sqrt(lam_ref) * float(np.linalg.norm(dy_vec))
                    if dx_c > 1e-14 and dy_c > 1e-14:
                        sigma = float(np.clip(math.exp(0.5 * math.log(sigma) + 0.5 * math.log(dx_c / dy_c)), 1e-7, 1e7))

                x0, y0 = x_bar.copy(), y_bar.copy()
                x, y = x_bar.copy(), y_bar.copy()
                t_cycle = 0
                r_first = r_prev = epoch_r0 = None
                restarts += 1

                if mode == "cuPDLPx-ASB" and asb_active and (not asb_disabled):
                    F_mask = (var_excl < asb_window).astype(np.float64)
                    B_mask = (con_excl < asb_window).astype(np.float64)
                    if np.sum(B_mask) > 0 and np.sum(F_mask) > 0:
                        v_m = asb_v_warm * B_mask
                        nv = float(np.linalg.norm(v_m))
                        v_m = (B_mask / (float(np.linalg.norm(B_mask)) + 1e-30)) if nv < 1e-12 else (v_m / (nv + 1e-30))
                        sig_est = 0.0
                        for _ in range(15):
                            u_m = counted_matvec(AT, v_m, cnt, "asb_power") * F_mask
                            w_m = counted_matvec(A, u_m, cnt, "asb_power") * B_mask
                            lam_m = float(v_m @ w_m)
                            nw = float(np.linalg.norm(w_m))
                            if nw < 1e-30:
                                sig_est = 0.0
                                break
                            v_m = w_m / nw
                            sig_est = math.sqrt(max(lam_m, 0.0))
                        asb_v_warm = v_m
                        if sig_est > 1e-12:
                            eta_plus = max(eta0, min(0.9 / sig_est, eta_ceil))
                            if eta_plus > eta and eta_plus >= 1.1 * eta:
                                saved_state = (x0.copy(), y0.copy(), omega, e_int, e_prev)
                                eta = eta_plus
                                asb_boosts += 1
                continue

        x, y = x_next, y_next

    t_solve = time.perf_counter() - t_solve_start
    return {
        "mode": mode,
        "status": status,
        "iters": k,
        "iters_1e4": iters_1e4,
        "spmv_1e4": spmv_1e4,
        "spmv": cnt.to_dict(),
        "time_setup": t_setup,
        "time_solve": t_solve,
        "time_total": t_setup + t_solve,
        "max_kkt": max(rel_p, rel_d, rel_gap),
        "p_obj": p_obj,
        "restarts": restarts,
        "extra": {"spectral_ratio": spec["ratio"]} if spec else ({"asb_boosts": asb_boosts} if mode == "cuPDLPx-ASB" else {}),
    }


def run_official_highs_pdlp(lp: LPInstance, presolve: str = "off", tol: float = 1e-6) -> Dict:
    t0 = time.perf_counter()
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("threads", 1)
    h.setOptionValue("solver", "pdlp")
    h.setOptionValue("presolve", presolve)
    h.setOptionValue("pdlp_d_gap_tol", tol)
    h.setOptionValue("primal_feasibility_tolerance", tol)
    h.setOptionValue("dual_feasibility_tolerance", tol)
    h.setOptionValue("time_limit", 15.0)
    m, n = lp.A.shape
    inf = highspy.kHighsInf
    lv = np.where(np.isfinite(lp.lv), lp.lv, -inf)
    uv = np.where(np.isfinite(lp.uv), lp.uv, inf)
    lc = np.where(np.isfinite(lp.lc), lp.lc, -inf)
    uc = np.where(np.isfinite(lp.uc), lp.uc, inf)
    h.addVars(n, lv, uv)
    h.changeColsCost(n, np.arange(n, dtype=np.int32), lp.c.astype(np.float64))
    A_csr = lp.A.tocsr()
    h.addRows(m, lc, uc, A_csr.nnz, A_csr.indptr.astype(np.int32), A_csr.indices.astype(np.int32), A_csr.data.astype(np.float64))
    h.run()
    dt = time.perf_counter() - t0
    info = h.getInfo()
    return {
        "solver": f"HiGHS-1.16.0-PDLP(presolve={presolve})",
        "status": str(h.getModelStatus()),
        "iters": int(info.pdlp_iteration_count),
        "time_total": dt,
        "obj": float(info.objective_function_value),
    }


def run_official_ortools_pdlp(lp: LPInstance, tol: float = 1e-6) -> Dict:
    t0 = time.perf_counter()
    s = pywraplp.Solver.CreateSolver("PDLP")
    s.SetNumThreads(1)
    s.SetTimeLimit(15000)
    # Set relative tolerances via solver-specific params
    s.SetSolverSpecificParametersAsString(
        f"termination_criteria {{ eps_optimal_relative: {tol} eps_optimal_absolute: {tol} }} "
        "presolve_options { use_glop: false }"
    )
    m, n = lp.A.shape
    inf = s.infinity()
    xs = [
        s.NumVar(float(lp.lv[j]) if np.isfinite(lp.lv[j]) else -inf, float(lp.uv[j]) if np.isfinite(lp.uv[j]) else inf, f"x{j}")
        for j in range(n)
    ]
    obj = s.Objective()
    for j in range(n):
        if lp.c[j] != 0.0:
            obj.SetCoefficient(xs[j], float(lp.c[j]))
    obj.SetMinimization()
    A_csr = lp.A.tocsr()
    for i in range(m):
        lo = float(lp.lc[i]) if np.isfinite(lp.lc[i]) else -inf
        hi = float(lp.uc[i]) if np.isfinite(lp.uc[i]) else inf
        ct = s.RowConstraint(lo, hi, f"c{i}")
        for idx in range(A_csr.indptr[i], A_csr.indptr[i + 1]):
            ct.SetCoefficient(xs[int(A_csr.indices[idx])], float(A_csr.data[idx]))
    t_build = time.perf_counter() - t0
    t_s = time.perf_counter()
    st = s.Solve()
    t_solve = time.perf_counter() - t_s
    st_map = {pywraplp.Solver.OPTIMAL: "OPTIMAL", pywraplp.Solver.FEASIBLE: "FEASIBLE", pywraplp.Solver.NOT_SOLVED: "NOT_SOLVED"}
    return {
        "solver": "OR-Tools-9.15-PDLP(no_glop_presolve)",
        "status": st_map.get(st, str(st)),
        "iters": int(s.iterations()),
        "time_solve": t_solve,
        "time_build": t_build,
        "obj": float(s.Objective().Value()) if st in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE) else float("nan"),
    }


def gm(xs: List[float]) -> float:
    return float(np.exp(np.mean(np.log(np.maximum(np.array(xs, dtype=np.float64), 1e-12)))))


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\spectral_hpr_lp_20261124")
    suite = build_stage0_suite()
    records = []

    print("=== Stage-0b Matched Internal SpMV-Counted Ablation + Official C++ PDLP Reference ===")
    for lp in suite:
        h_st, f_star, _ = solve_highs_reference(lp)
        r_spec = 8 if lp.true_rank_spike <= 6 else 12
        arms = {}
        for mode in ["HPR-Native", "HPR-Slack", "cuPDLPx-ASB", "Spec-HPR"]:
            arms[mode] = run_internal_ablation_arm(lp, mode=mode, rank=r_spec, tol=1e-6, max_iter=25000)
        off_highs_pdlp = run_official_highs_pdlp(lp, presolve="off", tol=1e-6)
        off_ortools_pdlp = run_official_ortools_pdlp(lp, tol=1e-6)

        print(f"\n--- {lp.name} ({lp.family}) f*={f_star:.4f} ---")
        for mode in ["HPR-Native", "HPR-Slack", "cuPDLPx-ASB", "Spec-HPR"]:
            a = arms[mode]
            sp_d = a["spmv"]
            print(
                f"  {mode:12s} | {a['status']:8s} | it={a['iters']:5d} | SpMV_tot={sp_d['total']:6d} "
                f"(scale={sp_d['scaling']:2d} set={sp_d['setup']:3d} swp={sp_d['sweep']:5d} kkt={sp_d['kkt_restart']:4d} asb={sp_d['asb_power']:3d}) "
                f"| SpMV@1e-4={str(a['spmv_1e4']):>6s} | t={a['time_total']:.3f}s"
            )
        print(
            f"  [Official C++] HiGHS-PDLP(off): {off_highs_pdlp['status']} it={off_highs_pdlp['iters']} t={off_highs_pdlp['time_total']:.3f}s | "
            f"OR-Tools-PDLP(off): {off_ortools_pdlp['status']} it={off_ortools_pdlp['iters']} t={off_ortools_pdlp['time_solve']:.3f}s"
        )
        records.append({
            "name": lp.name,
            "family": lp.family,
            "f_star": f_star,
            "arms": arms,
            "official": {"highs_pdlp_off": off_highs_pdlp, "ortools_pdlp_off": off_ortools_pdlp},
        })

    print("\n=== Family GM Total-SpMV Speedups (All Sparse Passes Counted, incl. Setup & Scaling) ===")
    fam_summary = {}
    for fam in ["F1_FactorEq", "F2_LinkedMCF", "F3_FactorIneq", "F4_FlatControl"]:
        recs = [r for r in records if r["family"] == fam]
        gm_spmv = {m: gm([r["arms"][m]["spmv"]["total"] for r in recs]) for m in ["HPR-Native", "HPR-Slack", "cuPDLPx-ASB", "Spec-HPR"]}
        gm_spmv_1e4 = {
            m: gm([r["arms"][m]["spmv_1e4"] or r["arms"][m]["spmv"]["total"] for r in recs])
            for m in ["HPR-Native", "HPR-Slack", "cuPDLPx-ASB", "Spec-HPR"]
        }
        fam_summary[fam] = {
            "gm_spmv_1e6": gm_spmv,
            "gm_spmv_1e4": gm_spmv_1e4,
            "spmv_speedup_Spec_vs_Native_1e6": gm_spmv["HPR-Native"] / gm_spmv["Spec-HPR"],
            "spmv_speedup_Spec_vs_Slack_1e6": gm_spmv["HPR-Slack"] / gm_spmv["Spec-HPR"],
            "spmv_speedup_Spec_vs_ASB_1e6": gm_spmv["cuPDLPx-ASB"] / gm_spmv["Spec-HPR"],
            "spmv_speedup_Spec_vs_Native_1e4": gm_spmv_1e4["HPR-Native"] / gm_spmv_1e4["Spec-HPR"],
            "spmv_speedup_Spec_vs_ASB_1e4": gm_spmv_1e4["cuPDLPx-ASB"] / gm_spmv_1e4["Spec-HPR"],
        }
        s = fam_summary[fam]
        print(
            f"{fam:14s} | @1e-6 SpMV Spec vs Native={s['spmv_speedup_Spec_vs_Native_1e6']:.2f}x, "
            f"vs Slack={s['spmv_speedup_Spec_vs_Slack_1e6']:.2f}x, vs ASB={s['spmv_speedup_Spec_vs_ASB_1e6']:.2f}x | "
            f"@1e-4 vs Native={s['spmv_speedup_Spec_vs_Native_1e4']:.2f}x, vs ASB={s['spmv_speedup_Spec_vs_ASB_1e4']:.2f}x"
        )

    out_path = out_dir / "stage0b_matched_spmv_ablation.json"
    out_path.write_text(json.dumps({"family_summary": fam_summary, "instances": records}, indent=2), encoding="utf-8")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
