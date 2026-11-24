"""
Stage-0b Diagnostic: Asymmetric Two-Sided Coin-Betting Dual Mirror Descent (Asym-CAP-DMD)
vs Strong Scale-Normalized Published Baselines (DMD-Norm, WS-DMD-Norm, An24-SA-Norm, An24-MainALG-Norm)
Directory: D:/AI_Science/antigravity/cap_dmd_olp_20261124/

Tests the exact asymmetric packing-gradient bound g_{t,i} in [-(a_bar_i - rho_i), +rho_i]:
  - Upward ONS coin-betting expert (w^+ >= 0) uses exact positive ceiling G_i^+ = rho_i
    (unconditional wealth safety: 1 - beta * g/rho >= 1/2 since g <= rho!).
  - Downward ONS coin-betting expert (w^- >= 0) uses exact negative floor G_i^- = a_bar_i - rho_i
    (unconditional wealth safety: 1 + gamma * g/G^- >= 1/2 since g >= -G^-!).
  - Exact 1D Cutkosky-Orabona (2018) box reduction onto [-mu_hat_i, U_i - mu_hat_i].
  - Single frozen initialization eps_i = rho_i / sqrt(T) across ALL 4 regimes, zero offline LP solves.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Dict, Tuple

import numpy as np

from stage0_one_run_falsifier import (
    OLPInstance,
    build_prediction,
    run_cap_dmd,
    run_dmd,
    solve_offline_lp_prefix,
)
from stage0_v2_binding_falsifier import generate_binding_instance


def run_an24_sa_scaled(inst: OLPInstance, mu_hat: np.ndarray, eta0_scale: float) -> Tuple[float, float]:
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    mu = mu_hat.copy()
    mu_anchor = mu_hat.copy()
    eta = 0.25 * eta0_scale / math.sqrt(T)
    eta_max = 4.0 * eta0_scale / math.sqrt(T)
    drift_thresh = 0.5
    reward = 0.0
    A_rows, A_vals, r, rho = inst.A_rows, inst.A_vals, inst.r, inst.rho
    for t in range(T):
        idx, w = A_rows[t], A_vals[t]
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
        if (t + 1) % 100 == 0 and eta < eta_max:
            if float(np.linalg.norm(mu - mu_anchor, 1)) > drift_thresh * math.sqrt(m):
                eta = min(2.0 * eta, eta_max)
                drift_thresh *= 2.0
                mu_anchor = mu.copy()
    return reward, time.perf_counter() - t0


def run_an24_mainalg_scaled(inst: OLPInstance, mu_hat: np.ndarray, eta0_scale: float, tau_sw: float = 0.05) -> Tuple[float, float, int]:
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    mu = mu_hat.copy()
    mu_anchor = mu_hat.copy()
    eta = 0.25 * eta0_scale / math.sqrt(T)
    eta_max = 4.0 * eta0_scale / math.sqrt(T)
    drift_thresh = 0.5
    switched = False
    checkpoints = {250, 500, 1000, 2000}
    lp_solves = 0
    reward = 0.0
    A_rows, A_vals, r, rho = inst.A_rows, inst.A_vals, inst.r, inst.rho
    for t in range(T):
        idx, w = A_rows[t], A_vals[t]
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
                    switched = True
                    mu = np.zeros(m, dtype=np.float64)
                    eta = eta0_scale / math.sqrt(T)
    return reward, time.perf_counter() - t0, lp_solves


def run_asym_cap_dmd(inst: OLPInstance, mu_hat: np.ndarray) -> Tuple[float, float, float]:
    """Asymmetric Two-Sided ONS Coin-Betting Dual Mirror Descent (Asym-CAP-DMD).
    Exact wealth conservation on both sides:
      - Upward expert (w^+ >= 0): u_t = g_tilde / G_plus <= 1, beta in [0, 0.5], W^+ <- W^+ * (1 - beta * u_t) >= 0.5 W^+ > 0
      - Downward expert (w^- >= 0): v_t = -g_tilde / G_minus <= 1, gamma in [0, 0.5], W^- <- W^- * (1 - gamma * v_t) >= 0.5 W^- > 0
    ONS update on log-wealth per Cutkosky & Orabona (ICML 2018, Algorithm 1):
      z_t = u_t / (1 - beta * u_t), A_t = A_{t-1} + z_t^2, beta <- clip(beta - (2 / (2 - ln 3)) * z_t / A_t, 0, 0.5)
    """
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    rho = inst.rho
    A_rows, A_vals, r = inst.A_rows, inst.A_vals, inst.r

    G_plus = rho.copy()                   # exact upper bound on g_{t,i} = rho_i - a_{t,i} x_t
    G_minus = np.maximum(inst.a_bar - rho, 1e-8)  # exact lower magnitude bound on -g_{t,i}
    U = inst.r_bar / rho
    mu_anchor = np.clip(mu_hat, 0.0, U)
    L_box = -mu_anchor
    R_box = U - mu_anchor

    # Initial wealth in objective/Lagrangian units: W0_i = rho_i / sqrt(T) (total initial wealth O(m*rho/sqrt(T)) << 1)
    W_pos = rho / math.sqrt(T)
    W_neg = rho / math.sqrt(T)
    beta = np.zeros(m, dtype=np.float64)    # in [0, 0.5]
    gamma = np.zeros(m, dtype=np.float64)   # in [0, 0.5]
    A_pos = np.ones(m, dtype=np.float64)    # ONS Hessian accumulator (init 1)
    A_neg = np.ones(m, dtype=np.float64)
    ons_step = 2.0 / (2.0 - math.log(3.0))  # exact Cutkosky-Orabona ONS constant ~ 2.2188

    mu = mu_anchor.copy()
    w_tilde = np.zeros(m, dtype=np.float64)
    reward = 0.0
    g_vec = np.empty(m, dtype=np.float64)
    min_wealth_factor = 1.0

    for t in range(T):
        idx, w = A_rows[t], A_vals[t]
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

        # True subgradient g_t = rho - a_t * x_t in [-G_minus, +G_plus]
        g_vec[:] = rho
        if x_t > 0.0:
            for j in range(3):
                if w[j] > 0.0:
                    B[idx[j]] -= w[j] * x_t
                    g_vec[idx[j]] -= w[j] * x_t

        # Exact 1D Cutkosky-Orabona constraint reduction preserving g_tilde in [-G_minus, +G_plus]
        g_tilde = g_vec.copy()
        out_hi = (w_tilde > R_box) & (g_vec < 0.0)
        out_lo = (w_tilde < L_box) & (g_vec > 0.0)
        g_tilde[out_hi | out_lo] = 0.0

        # Upward expert (w^+ = beta * W_pos / G_plus >= 0): normalized gradient u = g_tilde / G_plus <= 1
        u = g_tilde / G_plus
        fac_pos = 1.0 - beta * u
        min_wealth_factor = min(min_wealth_factor, float(np.min(fac_pos)))
        W_pos *= fac_pos
        z_pos = u / fac_pos
        A_pos += z_pos * z_pos
        beta = np.clip(beta - ons_step * z_pos / A_pos, 0.0, 0.5)

        # Downward expert (w^- = gamma * W_neg / G_minus >= 0, enters mu as -w^-):
        # Loss for w^- is (-g_tilde) * w^-, so normalized gradient v = -g_tilde / G_minus <= 1
        v = -g_tilde / G_minus
        fac_neg = 1.0 - gamma * v
        min_wealth_factor = min(min_wealth_factor, float(np.min(fac_neg)))
        W_neg *= fac_neg
        z_neg = v / fac_neg
        A_neg += z_neg * z_neg
        gamma = np.clip(gamma - ons_step * z_neg / A_neg, 0.0, 0.5)

        # Combine experts: w_tilde = w^+ - w^- (capped wealth avoids float overflow once pinned to box)
        W_pos = np.minimum(W_pos, 1e6)
        W_neg = np.minimum(W_neg, 1e6)
        w_tilde = (beta * W_pos / G_plus) - (gamma * W_neg / G_minus)
        mu = mu_anchor + np.clip(w_tilde, L_box, R_box)

    return reward, time.perf_counter() - t0, min_wealth_factor


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\cap_dmd_olp_20261124")
    regimes = [
        "R1_Accurate_IID",
        "R2_SparseCorrupt_IID",
        "R3_FullPoison_IID",
        "R4_AdversarialShift_Poison",
    ]
    seeds = [1001, 1002, 1003, 1004, 1005]
    methods = ["DMD-Norm", "WS-DMD-Norm", "An24-SA-Norm", "An24-MainALG-Norm", "Sym-CAP-DMD", "Asym-CAP-DMD"]
    summary = {}
    all_rows = []
    min_wf_global = 1.0

    print("=== Stage-0b Diagnostic: Asym-CAP-DMD vs STRONG Scale-Normalized Published Baselines (m=20, T=5000) ===")
    for reg in regimes:
        reg_rows = []
        for seed in seeds:
            inst = generate_binding_instance(reg, seed, m=20, T=5000)
            opt_val, mu_star = solve_offline_lp_prefix(inst, inst.T)
            mu_hat = build_prediction(inst, mu_star)
            eta0_scale = 1.0 / float(np.mean(inst.rho))

            r_dmd, t_dmd, _ = run_dmd(inst, np.zeros(inst.m), eta0=eta0_scale)
            r_ws, t_ws, _ = run_dmd(inst, mu_hat, eta0=eta0_scale)
            r_sa, t_sa = run_an24_sa_scaled(inst, mu_hat, eta0_scale)
            r_main, t_main, lp_cnt = run_an24_mainalg_scaled(inst, mu_hat, eta0_scale)
            r_sym, t_sym, _ = run_cap_dmd(inst, mu_hat)
            r_asym, t_asym, min_wf = run_asym_cap_dmd(inst, mu_hat)
            min_wf_global = min(min_wf_global, min_wf)

            rews = {
                "DMD-Norm": r_dmd,
                "WS-DMD-Norm": r_ws,
                "An24-SA-Norm": r_sa,
                "An24-MainALG-Norm": r_main,
                "Sym-CAP-DMD": r_sym,
                "Asym-CAP-DMD": r_asym,
            }
            ts = {
                "DMD-Norm": t_dmd,
                "WS-DMD-Norm": t_ws,
                "An24-SA-Norm": t_sa,
                "An24-MainALG-Norm": t_main,
                "Sym-CAP-DMD": t_sym,
                "Asym-CAP-DMD": t_asym,
            }
            reg_rows.append({"regime": reg, "seed": seed, "opt": opt_val, "rewards": rews, "regrets": {k: opt_val - v for k, v in rews.items()}, "times_s": ts, "mainalg_lp_solves": lp_cnt})
            all_rows.append(reg_rows[-1])

        mean_opt = float(np.mean([r["opt"] for r in reg_rows]))
        mean_reg = {m: float(np.mean([r["regrets"][m] for r in reg_rows])) for m in methods}
        mean_rew = {m: float(np.mean([r["rewards"][m] for r in reg_rows])) for m in methods}
        mean_cr = {m: mean_rew[m] / mean_opt for m in methods}
        mean_t = {m: float(np.mean([r["times_s"][m] for r in reg_rows])) for m in methods}
        summary[reg] = {"mean_opt": mean_opt, "mean_regret": mean_reg, "mean_reward": mean_rew, "mean_competitive_ratio": mean_cr, "mean_time_s": mean_t}

        print(f"\n--- {reg} (mean OPT={mean_opt:.1f}) ---")
        for m in methods:
            print(f"  {m:18s} | Regret={mean_reg[m]:8.2f} | Reward={mean_rew[m]:8.1f} | Ratio={mean_cr[m]:.4f} | Time={mean_t[m]*1000:6.1f}ms")

    r1 = summary["R1_Accurate_IID"]["mean_regret"]
    r2 = summary["R2_SparseCorrupt_IID"]["mean_regret"]
    r3 = summary["R3_FullPoison_IID"]["mean_regret"]
    r4 = summary["R4_AdversarialShift_Poison"]["mean_reward"]

    verdict = {
        "min_wealth_factor_observed": min_wf_global,
        "gate1_R1_vs_DMDNorm": r1["DMD-Norm"] / max(r1["Asym-CAP-DMD"], 1e-9),
        "gate1_R1_vs_WSNorm": r1["WS-DMD-Norm"] / max(r1["Asym-CAP-DMD"], 1e-9),
        "gate1_pass": (r1["DMD-Norm"] / r1["Asym-CAP-DMD"] >= 3.0) and (r1["WS-DMD-Norm"] / r1["Asym-CAP-DMD"] >= 2.0),
        "gate2_R2_vs_DMDNorm": r2["DMD-Norm"] / max(r2["Asym-CAP-DMD"], 1e-9),
        "gate2_R2_vs_WSNorm": r2["WS-DMD-Norm"] / max(r2["Asym-CAP-DMD"], 1e-9),
        "gate2_R2_vs_SANorm": r2["An24-SA-Norm"] / max(r2["Asym-CAP-DMD"], 1e-9),
        "gate2_R2_vs_MainNorm": r2["An24-MainALG-Norm"] / max(r2["Asym-CAP-DMD"], 1e-9),
        "gate2_pass": all(r2[k] / r2["Asym-CAP-DMD"] >= 1.5 for k in ["DMD-Norm", "WS-DMD-Norm", "An24-SA-Norm", "An24-MainALG-Norm"]),
        "gate3_R3_Asym_over_DMDNorm": r3["Asym-CAP-DMD"] / max(r3["DMD-Norm"], 1e-9),
        "gate3_R3_WSNorm_over_Asym": r3["WS-DMD-Norm"] / max(r3["Asym-CAP-DMD"], 1e-9),
        "gate3_pass": (r3["Asym-CAP-DMD"] / r3["DMD-Norm"] <= 1.35) and (r3["WS-DMD-Norm"] / r3["Asym-CAP-DMD"] >= 2.0),
        "gate4_R4_Asym_over_DMDNorm_rew": r4["Asym-CAP-DMD"] / max(r4["DMD-Norm"], 1e-9),
        "gate4_pass": (r4["Asym-CAP-DMD"] / r4["DMD-Norm"]) >= 0.95,
    }
    verdict["ALL_FOUR_STRONG_GATES_PASS"] = bool(verdict["gate1_pass"] and verdict["gate2_pass"] and verdict["gate3_pass"] and verdict["gate4_pass"])
    print("\n=== Stage-0b Strong Normalized-Baseline Gate Verdicts ===")
    print(json.dumps(verdict, indent=2))
    out_path = out_dir / "stage0b_asym_results.json"
    out_path.write_text(json.dumps({"verdict": verdict, "summary": summary, "runs": all_rows}, indent=2), encoding="utf-8")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
