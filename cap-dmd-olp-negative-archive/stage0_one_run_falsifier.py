"""
Stage-0 One-Run Falsifier: CAP-DMD vs Published Multi-Resource OLP Comparators
Directory: D:/AI_Science/antigravity/cap_dmd_olp_20261124/

Compares 5 algorithms on identical arrival streams against exact offline LP optimum (HiGHS):
  1. DMD           : Balseiro, Lu & Mirrokni (2023, Management Science), mu_1 = 0, eta = eta0 / sqrt(T)
  2. WS-DMD        : Warm-Start DMD, mu_1 = mu_hat, eta = eta0 / sqrt(T)
  3. An24-SA       : An, Li, Moseley & Visotsky (2024, arXiv:2402.13530 Alg 2), warm-start + global doubling step size
  4. An24-MainALG  : An et al. (2024, Alg 4), warm-start + epoch offline-LP (HiGHS) checkpoint switch to DMD
  5. CAP-DMD       : Proposed Coordinate-Wise Anchored Parameter-Free Dual Mirror Descent
                     (1D FreeGrad [Mhammedi & Koolen 2020] anchored at mu_hat_i + exact Cutkosky-Orabona 2018
                      1D box reduction, O(m)/arrival, zero offline LP solves, single frozen epsilon across all 4 regimes)

Four simultaneous regimes (5 seeds each = 20 instances, m=20, T=5000):
  R1_Accurate_IID           : i.i.d. arrivals, accurate prediction mu_hat = mu* + 1% noise
  R2_SparseCorrupt_IID      : i.i.d. arrivals, 2/20 resources poisoned (1 high 5*max(mu*,1), 1 zero), 18 accurate
  R3_FullPoison_IID         : i.i.d. arrivals, all 20/20 resources poisoned (10 high, 10 zero)
  R4_AdversarialShift_Poison: non-stationary front-loaded low-reward (40%) -> high-reward (60%) + mu_hat = 0
"""

from __future__ import annotations

import json
import math
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

import highspy
import numpy as np
import scipy.sparse as sp


@dataclass
class OLPInstance:
    regime: str
    seed: int
    m: int
    T: int
    r: np.ndarray          # (T,) rewards
    A_rows: np.ndarray     # (T, k_max) resource indices
    A_vals: np.ndarray     # (T, k_max) consumption weights (0 for unused slots)
    rho: np.ndarray        # (m,) per-period budget rate (B = T * rho)
    a_bar: np.ndarray      # (m,) coordinate-wise max consumption
    r_bar: float           # max reward


def generate_instance(regime: str, seed: int, m: int = 20, T: int = 5000) -> OLPInstance:
    rng = np.random.default_rng(seed)
    # Heterogeneous resource tightness so mu* has rich spread across resources
    rho = rng.uniform(0.15, 0.35, size=m)
    k_max = 3
    A_rows = np.zeros((T, k_max), dtype=np.int32)
    A_vals = np.zeros((T, k_max), dtype=np.float64)

    # Resource base popularity/value weights so resources have distinct shadow prices
    res_value = rng.uniform(0.6, 2.2, size=m)

    if regime == "R4_AdversarialShift_Poison":
        # Non-stationary adversarial shift: first 40% low reward, last 60% high reward
        t_split = int(0.4 * T)
        r = np.empty(T, dtype=np.float64)
        for t in range(T):
            k = 2 if rng.random() < 0.5 else 3
            idx = rng.choice(m, size=k, replace=False)
            w = rng.uniform(0.25, 1.0, size=k)
            A_rows[t, :k] = idx
            A_vals[t, :k] = w
            base_val = float(np.dot(w, res_value[idx]))
            if t < t_split:
                r[t] = base_val * rng.uniform(0.45, 0.75)
            else:
                r[t] = base_val * rng.uniform(1.50, 2.60)
    else:
        r = np.empty(T, dtype=np.float64)
        for t in range(T):
            k = 2 if rng.random() < 0.5 else 3
            idx = rng.choice(m, size=k, replace=False)
            w = rng.uniform(0.25, 1.0, size=k)
            A_rows[t, :k] = idx
            A_vals[t, :k] = w
            base_val = float(np.dot(w, res_value[idx]))
            r[t] = base_val * rng.uniform(0.5, 2.2)

    a_bar = np.ones(m, dtype=np.float64)
    r_bar = float(np.max(r))
    return OLPInstance(regime=regime, seed=seed, m=m, T=T, r=r, A_rows=A_rows, A_vals=A_vals, rho=rho, a_bar=a_bar, r_bar=r_bar)


def solve_offline_lp_prefix(inst: OLPInstance, t_end: int) -> Tuple[float, np.ndarray]:
    """Solve exact offline fractional packing LP on arrivals 0..t_end-1 with budget t_end * rho via HiGHS."""
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("threads", 1)
    m = inst.m
    n = t_end
    # Maximize r^T x  <=> minimize -r^T x s.t. 0 <= x <= 1, A x <= t_end * rho
    h.addVars(n, np.zeros(n, dtype=np.float64), np.ones(n, dtype=np.float64))
    h.changeColsCost(n, np.arange(n, dtype=np.int32), (-inst.r[:n]).astype(np.float64))

    # Build sparse CSR for m rows x n cols
    rows_sub = inst.A_rows[:n]
    vals_sub = inst.A_vals[:n]
    mask = vals_sub > 0.0
    t_idx = np.broadcast_to(np.arange(n, dtype=np.int32)[:, None], rows_sub.shape)[mask]
    r_idx = rows_sub[mask]
    v_dat = vals_sub[mask]
    A_csr = sp.coo_matrix((v_dat, (r_idx, t_idx)), shape=(m, n)).tocsr()

    inf = highspy.kHighsInf
    lc = np.full(m, -inf, dtype=np.float64)
    uc = (t_end * inst.rho).astype(np.float64)
    h.addRows(m, lc, uc, A_csr.nnz, A_csr.indptr.astype(np.int32), A_csr.indices.astype(np.int32), A_csr.data.astype(np.float64))
    h.run()
    assert "kOptimal" in str(h.getModelStatus()), f"Offline LP status: {h.getModelStatus()}"
    opt_val = -float(h.getInfo().objective_function_value)
    # In HiGHS minimization of -r^T x s.t. Ax <= B, row duals are <= 0; shadow price mu* = -row_dual >= 0
    row_dual = np.array(h.getSolution().row_dual, dtype=np.float64)
    mu_star = np.maximum(-row_dual, 0.0)
    return opt_val, mu_star


def build_prediction(inst: OLPInstance, mu_star: np.ndarray) -> np.ndarray:
    rng = np.random.default_rng(inst.seed + 77777)
    m = inst.m
    if inst.regime == "R1_Accurate_IID":
        noise = rng.normal(0.0, 0.01, size=m)
        return np.maximum(mu_star * (1.0 + noise), 0.0)
    elif inst.regime == "R2_SparseCorrupt_IID":
        mu_hat = mu_star.copy()
        # Pick the 2 resources with largest dual impact (binding shadow prices) to poison honestly!
        top_idx = np.argsort(mu_star)[::-1][:2]
        mu_hat[top_idx[0]] = 5.0 * max(float(mu_star[top_idx[0]]), 1.0)  # severe overestimate
        mu_hat[top_idx[1]] = 0.0                                          # severe underestimate
        return mu_hat
    elif inst.regime == "R3_FullPoison_IID":
        mu_hat = np.empty(m, dtype=np.float64)
        for i in range(m):
            if i % 2 == 0:
                mu_hat[i] = 5.0 * max(float(mu_star[i]), 1.0)
            else:
                mu_hat[i] = 0.0
        return mu_hat
    elif inst.regime == "R4_AdversarialShift_Poison":
        # Poisoned zero price encouraging early depletion on low-value wave
        return np.zeros(m, dtype=np.float64)
    else:
        raise ValueError(inst.regime)


# =============================================================================
# Online Algorithms
# =============================================================================

def run_dmd(inst: OLPInstance, mu_init: np.ndarray, eta0: float = 1.0) -> Tuple[float, float, np.ndarray]:
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    mu = mu_init.copy()
    eta = eta0 / math.sqrt(T)
    reward = 0.0
    A_rows, A_vals, r, rho = inst.A_rows, inst.A_vals, inst.r, inst.rho

    for t in range(T):
        idx = A_rows[t]
        w = A_vals[t]
        # Compute r_t - mu^T a_t
        cost = 0.0
        for j in range(3):
            if w[j] > 0.0:
                cost += mu[idx[j]] * w[j]
        if r[t] > cost:
            # Check remaining budget (fractional acceptance up to max feasible x in [0,1])
            x_t = 1.0
            for j in range(3):
                if w[j] > 0.0:
                    cap = B[idx[j]] / w[j]
                    if cap < x_t:
                        x_t = cap
            if x_t < 0.0:
                x_t = 0.0
        else:
            x_t = 0.0

        reward += r[t] * x_t
        # Dual subgradient g_t = rho - a_t * x_t; mu <- max(0, mu - eta * g_t)
        mu -= eta * rho
        if x_t > 0.0:
            for j in range(3):
                if w[j] > 0.0:
                    B[idx[j]] -= w[j] * x_t
                    mu[idx[j]] += eta * (w[j] * x_t)
        np.maximum(mu, 0.0, out=mu)
    return reward, time.perf_counter() - t0, B


def run_an24_sa(inst: OLPInstance, mu_hat: np.ndarray, eta_init_mult: float = 0.25) -> Tuple[float, float, np.ndarray]:
    """An, Li, Moseley & Visotsky (2024, arXiv:2402.13530 Alg 2): warm-start DMD with
    global scalar doubling step size across epochs whenever cumulative dual drift exceeds threshold.
    """
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    mu = mu_hat.copy()
    mu_anchor = mu_hat.copy()
    eta = eta_init_mult / math.sqrt(T)
    eta_max = 4.0 / math.sqrt(T)
    # Doubling trigger radius (scales with step size)
    drift_thresh = 0.5
    reward = 0.0
    A_rows, A_vals, r, rho = inst.A_rows, inst.A_vals, inst.r, inst.rho

    for t in range(T):
        idx = A_rows[t]
        w = A_vals[t]
        cost = 0.0
        for j in range(3):
            if w[j] > 0.0:
                cost += mu[idx[j]] * w[j]
        if r[t] > cost:
            x_t = 1.0
            for j in range(3):
                if w[j] > 0.0:
                    cap = B[idx[j]] / w[j]
                    if cap < x_t:
                        x_t = cap
            if x_t < 0.0:
                x_t = 0.0
        else:
            x_t = 0.0

        reward += r[t] * x_t
        mu -= eta * rho
        if x_t > 0.0:
            for j in range(3):
                if w[j] > 0.0:
                    B[idx[j]] -= w[j] * x_t
                    mu[idx[j]] += eta * (w[j] * x_t)
        np.maximum(mu, 0.0, out=mu)

        # Global doubling check every 100 steps
        if (t + 1) % 100 == 0 and eta < eta_max:
            if float(np.linalg.norm(mu - mu_anchor, 1)) > drift_thresh * math.sqrt(m):
                eta = min(2.0 * eta, eta_max)
                drift_thresh *= 2.0
                mu_anchor = mu.copy()
    return reward, time.perf_counter() - t0, B


def run_an24_mainalg(inst: OLPInstance, mu_hat: np.ndarray, tau_sw: float = 0.05) -> Tuple[float, float, int]:
    """An, Li, Moseley & Visotsky (2024, arXiv:2402.13530 Alg 4): warm-start SA with
    epoch-based offline LP checkpoint tests OPT_{t-1}; switches globally to prediction-blind DMD
    if realized prefix revenue lags (1 - tau_sw) * OPT_{t-1}.
    """
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    mu = mu_hat.copy()
    mu_anchor = mu_hat.copy()
    eta = 0.25 / math.sqrt(T)
    eta_max = 4.0 / math.sqrt(T)
    drift_thresh = 0.5
    switched = False
    checkpoints = {250, 500, 1000, 2000}
    lp_solves = 0
    reward = 0.0
    A_rows, A_vals, r, rho = inst.A_rows, inst.A_vals, inst.r, inst.rho

    for t in range(T):
        idx = A_rows[t]
        w = A_vals[t]
        cost = 0.0
        for j in range(3):
            if w[j] > 0.0:
                cost += mu[idx[j]] * w[j]
        if r[t] > cost:
            x_t = 1.0
            for j in range(3):
                if w[j] > 0.0:
                    cap = B[idx[j]] / w[j]
                    if cap < x_t:
                        x_t = cap
            if x_t < 0.0:
                x_t = 0.0
        else:
            x_t = 0.0

        reward += r[t] * x_t
        mu -= eta * rho
        if x_t > 0.0:
            for j in range(3):
                if w[j] > 0.0:
                    B[idx[j]] -= w[j] * x_t
                    mu[idx[j]] += eta * (w[j] * x_t)
        np.maximum(mu, 0.0, out=mu)

        if not switched:
            if (t + 1) % 100 == 0 and eta < eta_max:
                if float(np.linalg.norm(mu - mu_anchor, 1)) > drift_thresh * math.sqrt(m):
                    eta = min(2.0 * eta, eta_max)
                    drift_thresh *= 2.0
                    mu_anchor = mu.copy()
            if (t + 1) in checkpoints:
                opt_pref, _ = solve_offline_lp_prefix(inst, t + 1)
                lp_solves += 1
                if reward < (1.0 - tau_sw) * opt_pref:
                    # Global switch to prediction-blind DMD!
                    switched = True
                    mu = np.zeros(m, dtype=np.float64)
                    eta = 1.0 / math.sqrt(T)
    return reward, time.perf_counter() - t0, lp_solves


def run_cap_dmd(inst: OLPInstance, mu_hat: np.ndarray) -> Tuple[float, float, np.ndarray]:
    """Proposed CAP-DMD: Coordinate-wise 1D FreeGrad (Mhammedi & Koolen 2020) anchored at mu_hat_i
    with exact Cutkosky-Orabona (2018) 1D box reduction onto [0, U_i].
    Single frozen initialization eps_i = G_i / sqrt(T), zero offline LP solves, O(m) per arrival.
    """
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    rho = inst.rho
    A_rows, A_vals, r = inst.A_rows, inst.A_vals, inst.r

    # Coordinate-wise gradient bound G_i = max(rho_i, a_bar_i - rho_i) and dual upper box U_i = r_bar / rho_i
    G = np.maximum(rho, inst.a_bar - rho)
    inv_G = 1.0 / G
    U = inst.r_bar / rho
    mu_anchor = np.clip(mu_hat, 0.0, U)
    L_box = -mu_anchor          # lower bound on w_i = mu_i - mu_anchor_i
    R_box = U - mu_anchor       # upper bound on w_i

    # Single frozen scale-free wealth parameter (protocol Section 2): eps_i = G_i / sqrt(T)
    eps = G / math.sqrt(T)

    # Dimensionless FreeGrad state per coordinate (normalized by G_i so |g_norm| <= 1)
    S = np.zeros(m, dtype=np.float64)
    V = np.ones(m, dtype=np.float64)   # V_0 = 1 in normalized units (G=1)
    w_tilde = np.zeros(m, dtype=np.float64)
    mu = mu_anchor.copy()

    reward = 0.0
    g_vec = np.empty(m, dtype=np.float64)

    for t in range(T):
        idx = A_rows[t]
        w = A_vals[t]
        cost = 0.0
        for j in range(3):
            if w[j] > 0.0:
                cost += mu[idx[j]] * w[j]
        if r[t] > cost:
            x_t = 1.0
            for j in range(3):
                if w[j] > 0.0:
                    cap = B[idx[j]] / w[j]
                    if cap < x_t:
                        x_t = cap
            if x_t < 0.0:
                x_t = 0.0
        else:
            x_t = 0.0

        reward += r[t] * x_t

        # True dual subgradient g_t = rho - a_t * x_t
        g_vec[:] = rho
        if x_t > 0.0:
            for j in range(3):
                if w[j] > 0.0:
                    B[idx[j]] -= w[j] * x_t
                    g_vec[idx[j]] -= w[j] * x_t

        # Exact 1D Cutkosky-Orabona (2018) constraint reduction preserving |g_tilde| <= |g|
        g_tilde = g_vec.copy()
        out_hi = (w_tilde > R_box) & (g_vec < 0.0)
        out_lo = (w_tilde < L_box) & (g_vec > 0.0)
        g_tilde[out_hi | out_lo] = 0.0

        # Normalize to [-1, 1] and update FreeGrad state
        gn = g_tilde * inv_G
        S -= gn
        V += gn * gn

        abs_S = np.abs(S)
        denom_exp = 2.0 * V + 2.0 * abs_S
        exp_arg = np.minimum((S * S) / denom_exp, 40.0)
        num = S * (2.0 * V + abs_S)
        den = 2.0 * ((V + abs_S) ** 2) * np.sqrt(V)
        w_tilde = eps * (num / den) * np.exp(exp_arg)

        # Project onto [L_box, R_box] -> mu in [0, U]
        w_proj = np.clip(w_tilde, L_box, R_box)
        mu = mu_anchor + w_proj

    return reward, time.perf_counter() - t0, B


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\cap_dmd_olp_20261124")
    out_dir.mkdir(parents=True, exist_ok=True)

    regimes = [
        "R1_Accurate_IID",
        "R2_SparseCorrupt_IID",
        "R3_FullPoison_IID",
        "R4_AdversarialShift_Poison",
    ]
    seeds = [1001, 1002, 1003, 1004, 1005]
    all_rows = []
    summary = {}

    print("=== Stage-0 One-Run Falsifier: CAP-DMD vs DMD / WS-DMD / An24-SA / An24-MainALG (m=20, T=5000) ===")
    for reg in regimes:
        reg_rows = []
        for seed in seeds:
            inst = generate_instance(reg, seed, m=20, T=5000)
            opt_val, mu_star = solve_offline_lp_prefix(inst, inst.T)
            mu_hat = build_prediction(inst, mu_star)

            rew_dmd, t_dmd, _ = run_dmd(inst, np.zeros(inst.m), eta0=1.0)
            rew_ws, t_ws, _ = run_dmd(inst, mu_hat, eta0=1.0)
            rew_sa, t_sa, _ = run_an24_sa(inst, mu_hat)
            rew_main, t_main, lp_cnt = run_an24_mainalg(inst, mu_hat)
            rew_cap, t_cap, _ = run_cap_dmd(inst, mu_hat)

            row = {
                "regime": reg,
                "seed": seed,
                "opt": opt_val,
                "mu_hat_l1_err": float(np.linalg.norm(mu_hat - mu_star, 1)),
                "rewards": {
                    "DMD": rew_dmd,
                    "WS-DMD": rew_ws,
                    "An24-SA": rew_sa,
                    "An24-MainALG": rew_main,
                    "CAP-DMD": rew_cap,
                },
                "regrets": {
                    "DMD": opt_val - rew_dmd,
                    "WS-DMD": opt_val - rew_ws,
                    "An24-SA": opt_val - rew_sa,
                    "An24-MainALG": opt_val - rew_main,
                    "CAP-DMD": opt_val - rew_cap,
                },
                "times_s": {
                    "DMD": t_dmd,
                    "WS-DMD": t_ws,
                    "An24-SA": t_sa,
                    "An24-MainALG": t_main,
                    "CAP-DMD": t_cap,
                },
                "mainalg_lp_solves": lp_cnt,
            }
            reg_rows.append(row)
            all_rows.append(row)

        methods = ["DMD", "WS-DMD", "An24-SA", "An24-MainALG", "CAP-DMD"]
        mean_opt = float(np.mean([r["opt"] for r in reg_rows]))
        mean_reg = {m: float(np.mean([r["regrets"][m] for r in reg_rows])) for m in methods}
        mean_rew = {m: float(np.mean([r["rewards"][m] for r in reg_rows])) for m in methods}
        mean_cr = {m: mean_rew[m] / mean_opt for m in methods}
        mean_time = {m: float(np.mean([r["times_s"][m] for r in reg_rows])) for m in methods}
        summary[reg] = {
            "mean_opt": mean_opt,
            "mean_regret": mean_reg,
            "mean_reward": mean_rew,
            "mean_competitive_ratio": mean_cr,
            "mean_time_s": mean_time,
        }
        print(f"\n--- {reg} (mean OPT={mean_opt:.1f}) ---")
        for m in methods:
            print(f"  {m:13s} | Regret={mean_reg[m]:8.2f} | Reward={mean_rew[m]:8.1f} | Ratio={mean_cr[m]:.4f} | Time={mean_time[m]*1000:6.1f}ms")

    # Pre-registered Gate Verdicts
    g1_ratio = summary["R1_Accurate_IID"]["mean_regret"]["DMD"] / max(summary["R1_Accurate_IID"]["mean_regret"]["CAP-DMD"], 1e-9)
    g1_pass = g1_ratio >= 2.0

    r2 = summary["R2_SparseCorrupt_IID"]["mean_regret"]
    g2_vs_dmd = r2["DMD"] / max(r2["CAP-DMD"], 1e-9)
    g2_vs_main = r2["An24-MainALG"] / max(r2["CAP-DMD"], 1e-9)
    g2_vs_ws = r2["WS-DMD"] / max(r2["CAP-DMD"], 1e-9)
    g2_vs_sa = r2["An24-SA"] / max(r2["CAP-DMD"], 1e-9)
    g2_pass = (g2_vs_dmd >= 1.5) and (g2_vs_main >= 1.5) and (g2_vs_ws >= 2.0) and (g2_vs_sa > 1.0)

    r3 = summary["R3_FullPoison_IID"]["mean_regret"]
    g3_vs_dmd_ratio = r3["CAP-DMD"] / max(r3["DMD"], 1e-9)
    g3_vs_ws_gain = r3["WS-DMD"] / max(r3["CAP-DMD"], 1e-9)
    g3_pass = (g3_vs_dmd_ratio <= 1.35) and (g3_vs_ws_gain >= 2.5)

    r4 = summary["R4_AdversarialShift_Poison"]["mean_reward"]
    g4_rew_frac = r4["CAP-DMD"] / max(r4["DMD"], 1e-9)
    g4_pass = g4_rew_frac >= 0.95

    verdict = {
        "gate1_R1_accurate_pass": g1_pass,
        "gate1_DMD_over_CAP_regret": g1_ratio,
        "gate2_R2_sparse_corrupt_pass": g2_pass,
        "gate2_DMD_over_CAP": g2_vs_dmd,
        "gate2_MainALG_over_CAP": g2_vs_main,
        "gate2_WSDMD_over_CAP": g2_vs_ws,
        "gate2_SA_over_CAP": g2_vs_sa,
        "gate3_R3_full_poison_pass": g3_pass,
        "gate3_CAP_over_DMD_regret": g3_vs_dmd_ratio,
        "gate3_WSDMD_over_CAP_regret": g3_vs_ws_gain,
        "gate4_R4_adversarial_pass": g4_pass,
        "gate4_CAP_over_DMD_reward": g4_rew_frac,
        "ALL_FOUR_GATES_PASS": bool(g1_pass and g2_pass and g3_pass and g4_pass),
    }
    print("\n=== Pre-Registered One-Run Falsifier Verdicts ===")
    print(json.dumps(verdict, indent=2))

    res_path = out_dir / "stage0_falsifier_results.json"
    res_path.write_text(json.dumps({"verdict": verdict, "summary": summary, "runs": all_rows}, indent=2), encoding="utf-8")
    print(f"Saved {res_path}")


if __name__ == "__main__":
    main()
