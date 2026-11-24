"""
Stage-0c Diagnostic: Coordinate-Wise Complementary-Slackness Drift-Gated DMD (CoordDrift-DMD)
vs Strong Scale-Normalized Published Baselines (DMD-Norm, WS-DMD-Norm, An24-SA-Norm, An24-MainALG-Norm)
Directory: D:/AI_Science/antigravity/cap_dmd_olp_20261124/

Key mechanism (directly fixing the multiplicative wake-up lag discovered in Stage-0 / Stage-0b):
  Under an accurate shadow price mu_hat_i == mu*_i, complementary slackness implies:
    - Over-consumption drift D_{t,i} = sum_{s<=t} (rho_i - a_{s,i} x_s) cannot go strongly negative
      beyond the empirical-Bernstein tube -(c * sqrt(V_{t,i} * L) + G_i^- * L) for ANY i.
    - Under-consumption drift D_{t,i} cannot go strongly positive beyond +(c * sqrt(V_{t,i} * L) + rho_i * L)
      whenever mu_{t,i} > 0 (since mu*_i > 0 requires resource i to be binding!).
  Therefore, each coordinate i independently tracks its cumulative drift D_{t,i} and empirical variance V_{t,i}
  in O(1) time (ZERO offline LP solves!):
    - While UNLOCKED == False (trusting mu_hat_i): uses tight low-variance step eta_fine_i = eta_base_i / kappa_fine
      (preserving near-zero regret on accurately predicted resources!).
    - The moment coordinate i exits its per-resource empirical-Bernstein complementary-slackness tube:
        * If under-consuming while mu_{t,i} > 0 (overpriced): immediately drop mu_{t,i} -> 0 and switch
          ONLY coordinate i to full DMD-Norm step eta_base_i!
        * If over-consuming (underpriced / adversarial wave): immediately switch ONLY coordinate i to
          full DMD-Norm step eta_base_i (and apply cumulative-drift catch-up step -eta_base_i * D_{t,i})!
  All other m - |S| accurate coordinates remain untouched in tight low-noise mode around mu_hat_j!
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
    run_dmd,
    solve_offline_lp_prefix,
)
from stage0_v2_binding_falsifier import generate_binding_instance
from stage0b_asym_cap_dmd_test import (
    run_an24_mainalg_scaled,
    run_an24_sa_scaled,
)


def run_coord_drift_dmd(
    inst: OLPInstance,
    mu_hat: np.ndarray,
    eta0_scale: float,
    kappa_fine: float = 10.0,
    z_thresh: float = 2.5,
) -> Tuple[float, float, int]:
    """Coordinate-Wise Complementary-Slackness Drift-Gated DMD (CoordDrift-DMD).
    O(m) arithmetic per arrival, zero offline LP solves, single frozen configuration across all 4 regimes.
    """
    t0 = time.perf_counter()
    m, T = inst.m, inst.T
    B = inst.T * inst.rho.copy()
    rho = inst.rho
    A_rows, A_vals, r = inst.A_rows, inst.A_vals, inst.r

    eta_full = eta0_scale / math.sqrt(T)
    eta_fine = eta_full / kappa_fine
    G_plus = rho.copy()
    G_minus = np.maximum(inst.a_bar - rho, 1e-8)

    mu = np.maximum(mu_hat.copy(), 0.0)
    unlocked = np.zeros(m, dtype=bool)
    D = np.zeros(m, dtype=np.float64)    # cumulative drift sum (rho_i - a_{s,i} x_s)
    V = np.zeros(m, dtype=np.float64)    # cumulative empirical squared gradient sum g_{s,i}^2
    log_factor = math.log(max(m, 2) * 10.0)
    g_vec = np.empty(m, dtype=np.float64)
    reward = 0.0

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

        # Dual subgradient g_t = rho - a_t * x_t
        g_vec[:] = rho
        if x_t > 0.0:
            for j in range(3):
                if w[j] > 0.0:
                    B[idx[j]] -= w[j] * x_t
                    g_vec[idx[j]] -= w[j] * x_t

        # Per-coordinate step size (fine while locked, full DMD-Norm once unlocked)
        eta_vec = np.where(unlocked, eta_full, eta_fine)
        mu -= eta_vec * g_vec
        np.maximum(mu, 0.0, out=mu)

        # Update drift/variance and test complementary-slackness tube ONLY on still-locked coordinates
        if not np.all(unlocked):
            locked_mask = ~unlocked
            D[locked_mask] += g_vec[locked_mask]
            V[locked_mask] += g_vec[locked_mask] * g_vec[locked_mask]

            # Empirical-Bernstein half-widths (asymmetric: G_plus on positive under-consumption side,
            # G_minus on negative over-consumption side)
            # Only test after tiny burn-in t >= 20 so initial discrete arrivals don't false-trip
            if t >= 20:
                rad_pos = z_thresh * np.sqrt(V * log_factor) + 1.5 * G_plus * log_factor
                rad_neg = z_thresh * np.sqrt(V * log_factor) + 1.5 * G_minus * log_factor

                # Case A: Systematic under-consumption while mu_i > 0 => overpriced coordinate i!
                trip_overpriced = locked_mask & (mu > 1e-6) & (D > rad_pos)
                if np.any(trip_overpriced):
                    unlocked[trip_overpriced] = True
                    # Reset ONLY overpriced coordinates to prediction-blind mu=0
                    mu[trip_overpriced] = 0.0

                # Case B: Systematic over-consumption => underpriced coordinate i!
                trip_underpriced = locked_mask & (~trip_overpriced) & (D < -rad_neg)
                if np.any(trip_underpriced):
                    unlocked[trip_underpriced] = True
                    # Catch up ONLY underpriced coordinates by applying missed full-step drift
                    mu[trip_underpriced] = np.maximum(
                        mu[trip_underpriced] - (eta_full - eta_fine) * D[trip_underpriced],
                        0.0,
                    )

    return reward, time.perf_counter() - t0, int(np.sum(unlocked))


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\cap_dmd_olp_20261124")
    regimes = [
        "R1_Accurate_IID",
        "R2_SparseCorrupt_IID",
        "R3_FullPoison_IID",
        "R4_AdversarialShift_Poison",
    ]
    seeds = [1001, 1002, 1003, 1004, 1005]
    methods = ["DMD-Norm", "WS-DMD-Norm", "An24-SA-Norm", "An24-MainALG-Norm", "CoordDrift-DMD"]
    summary = {}
    all_rows = []

    print("=== Stage-0c Diagnostic: CoordDrift-DMD vs STRONG Scale-Normalized Published Baselines (m=20, T=5000) ===")
    for reg in regimes:
        reg_rows = []
        unlocked_counts = []
        for seed in seeds:
            inst = generate_binding_instance(reg, seed, m=20, T=5000)
            opt_val, mu_star = solve_offline_lp_prefix(inst, inst.T)
            mu_hat = build_prediction(inst, mu_star)
            eta0_scale = 1.0 / float(np.mean(inst.rho))

            r_dmd, t_dmd, _ = run_dmd(inst, np.zeros(inst.m), eta0=eta0_scale)
            r_ws, t_ws, _ = run_dmd(inst, mu_hat, eta0=eta0_scale)
            r_sa, t_sa = run_an24_sa_scaled(inst, mu_hat, eta0_scale)
            r_main, t_main, lp_cnt = run_an24_mainalg_scaled(inst, mu_hat, eta0_scale)
            r_cd, t_cd, n_unlk = run_coord_drift_dmd(inst, mu_hat, eta0_scale)
            unlocked_counts.append(n_unlk)

            rews = {
                "DMD-Norm": r_dmd,
                "WS-DMD-Norm": r_ws,
                "An24-SA-Norm": r_sa,
                "An24-MainALG-Norm": r_main,
                "CoordDrift-DMD": r_cd,
            }
            ts = {
                "DMD-Norm": t_dmd,
                "WS-DMD-Norm": t_ws,
                "An24-SA-Norm": t_sa,
                "An24-MainALG-Norm": t_main,
                "CoordDrift-DMD": t_cd,
            }
            reg_rows.append({
                "regime": reg,
                "seed": seed,
                "opt": opt_val,
                "rewards": rews,
                "regrets": {k: opt_val - v for k, v in rews.items()},
                "times_s": ts,
                "coord_drift_unlocked": n_unlk,
                "mainalg_lp_solves": lp_cnt,
            })
            all_rows.append(reg_rows[-1])

        mean_opt = float(np.mean([r["opt"] for r in reg_rows]))
        mean_reg = {m: float(np.mean([r["regrets"][m] for r in reg_rows])) for m in methods}
        mean_rew = {m: float(np.mean([r["rewards"][m] for r in reg_rows])) for m in methods}
        mean_cr = {m: mean_rew[m] / mean_opt for m in methods}
        mean_t = {m: float(np.mean([r["times_s"][m] for r in reg_rows])) for m in methods}
        mean_unlk = float(np.mean(unlocked_counts))
        summary[reg] = {
            "mean_opt": mean_opt,
            "mean_regret": mean_reg,
            "mean_reward": mean_rew,
            "mean_competitive_ratio": mean_cr,
            "mean_time_s": mean_t,
            "mean_unlocked_coords": mean_unlk,
        }
        print(f"\n--- {reg} (mean OPT={mean_opt:.1f}, CoordDrift mean unlocked={mean_unlk:.1f}/20) ---")
        for m in methods:
            print(f"  {m:18s} | Regret={mean_reg[m]:8.2f} | Reward={mean_rew[m]:8.1f} | Ratio={mean_cr[m]:.4f} | Time={mean_t[m]*1000:6.1f}ms")

    r1 = summary["R1_Accurate_IID"]["mean_regret"]
    r2 = summary["R2_SparseCorrupt_IID"]["mean_regret"]
    r3 = summary["R3_FullPoison_IID"]["mean_regret"]
    r4 = summary["R4_AdversarialShift_Poison"]["mean_reward"]

    verdict = {
        "gate1_R1_vs_DMDNorm": r1["DMD-Norm"] / max(r1["CoordDrift-DMD"], 1e-9),
        "gate1_R1_vs_WSNorm": r1["WS-DMD-Norm"] / max(r1["CoordDrift-DMD"], 1e-9),
        "gate1_pass": (r1["DMD-Norm"] / r1["CoordDrift-DMD"] >= 3.0) and (r1["WS-DMD-Norm"] / r1["CoordDrift-DMD"] >= 2.0),
        "gate2_R2_vs_DMDNorm": r2["DMD-Norm"] / max(r2["CoordDrift-DMD"], 1e-9),
        "gate2_R2_vs_WSNorm": r2["WS-DMD-Norm"] / max(r2["CoordDrift-DMD"], 1e-9),
        "gate2_R2_vs_SANorm": r2["An24-SA-Norm"] / max(r2["CoordDrift-DMD"], 1e-9),
        "gate2_R2_vs_MainNorm": r2["An24-MainALG-Norm"] / max(r2["CoordDrift-DMD"], 1e-9),
        "gate2_pass": all(r2[k] / r2["CoordDrift-DMD"] >= 1.5 for k in ["DMD-Norm", "WS-DMD-Norm", "An24-SA-Norm", "An24-MainALG-Norm"]),
        "gate3_R3_CD_over_DMDNorm": r3["CoordDrift-DMD"] / max(r3["DMD-Norm"], 1e-9),
        "gate3_R3_WSNorm_over_CD": r3["WS-DMD-Norm"] / max(r3["CoordDrift-DMD"], 1e-9),
        "gate3_pass": (r3["CoordDrift-DMD"] / r3["DMD-Norm"] <= 1.35) and (r3["WS-DMD-Norm"] / r3["CoordDrift-DMD"] >= 2.0),
        "gate4_R4_CD_over_DMDNorm_rew": r4["CoordDrift-DMD"] / max(r4["DMD-Norm"], 1e-9),
        "gate4_pass": (r4["CoordDrift-DMD"] / r4["DMD-Norm"]) >= 0.95,
    }
    verdict["ALL_FOUR_STRONG_GATES_PASS"] = bool(verdict["gate1_pass"] and verdict["gate2_pass"] and verdict["gate3_pass"] and verdict["gate4_pass"])
    print("\n=== Stage-0c Strong Normalized-Baseline Gate Verdicts ===")
    print(json.dumps(verdict, indent=2))
    out_path = out_dir / "stage0c_coord_drift_results.json"
    out_path.write_text(json.dumps({"verdict": verdict, "summary": summary, "runs": all_rows}, indent=2), encoding="utf-8")
    print(f"Saved {out_path}")


if __name__ == "__main__":
    main()
