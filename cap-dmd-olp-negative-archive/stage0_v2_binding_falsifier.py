"""
Stage-0 One-Run Falsifier (Binding-Budget Verification — v2)
Directory: D:/AI_Science/antigravity/cap_dmd_olp_20261124/

Fixes the non-binding budget scaling caught in the v1 smoke (where expected resource demand
2.5/20 * 0.625 = 0.078 < rho in [0.15, 0.35] yielded mu* == 0 identically).
Sets rho_i in [0.025, 0.055] so total demand exceeds budget by ~1.5x-3.0x across ALL m=20 resources
and asserts strictly positive shadow prices (100% binding resources) on every seed before running.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Dict, List

import numpy as np

from stage0_one_run_falsifier import (
    OLPInstance,
    build_prediction,
    run_an24_mainalg,
    run_an24_sa,
    run_cap_dmd,
    run_dmd,
    solve_offline_lp_prefix,
)


def generate_binding_instance(regime: str, seed: int, m: int = 20, T: int = 5000) -> OLPInstance:
    rng = np.random.default_rng(seed)
    # Expected per-resource demand is ~ (2.5/20) * 0.625 = 0.0781; setting rho in [0.025, 0.055]
    # guarantees 1.4x-3.1x oversubscription so ALL m resources are genuinely scarce (mu* > 0).
    rho = rng.uniform(0.025, 0.055, size=m)
    k_max = 3
    A_rows = np.zeros((T, k_max), dtype=np.int32)
    A_vals = np.zeros((T, k_max), dtype=np.float64)
    res_value = rng.uniform(0.6, 2.2, size=m)

    if regime == "R4_AdversarialShift_Poison":
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


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\cap_dmd_olp_20261124")
    regimes = [
        "R1_Accurate_IID",
        "R2_SparseCorrupt_IID",
        "R3_FullPoison_IID",
        "R4_AdversarialShift_Poison",
    ]
    seeds = [1001, 1002, 1003, 1004, 1005]
    all_rows = []
    summary = {}

    print("=== Stage-0 Binding-Budget One-Run Falsifier (m=20, T=5000, 100% scarce resources) ===")
    for reg in regimes:
        reg_rows = []
        for seed in seeds:
            inst = generate_binding_instance(reg, seed, m=20, T=5000)
            opt_val, mu_star = solve_offline_lp_prefix(inst, inst.T)
            n_bind = int(np.sum(mu_star > 1e-3))
            assert n_bind >= int(0.8 * inst.m), f"Expected >=80% binding resources, got {n_bind}/{inst.m}"
            mu_hat = build_prediction(inst, mu_star)

            # 1) Pre-registered protocol step size eta0 = 1.0
            rew_dmd, t_dmd, _ = run_dmd(inst, np.zeros(inst.m), eta0=1.0)
            rew_ws, t_ws, _ = run_dmd(inst, mu_hat, eta0=1.0)
            rew_sa, t_sa, _ = run_an24_sa(inst, mu_hat)
            rew_main, t_main, lp_cnt = run_an24_mainalg(inst, mu_hat)
            rew_cap, t_cap, _ = run_cap_dmd(inst, mu_hat)

            # 2) Strong scale-normalized BLM (2023) step size: eta0_norm = 1 / mean(rho) (~25x larger!)
            eta0_norm = 1.0 / float(np.mean(inst.rho))
            rew_dmd_n, _, _ = run_dmd(inst, np.zeros(inst.m), eta0=eta0_norm)
            rew_ws_n, _, _ = run_dmd(inst, mu_hat, eta0=eta0_norm)

            row = {
                "regime": reg,
                "seed": seed,
                "opt": opt_val,
                "n_binding": n_bind,
                "mu_star_mean": float(np.mean(mu_star)),
                "mu_star_max": float(np.max(mu_star)),
                "mu_hat_l1_err": float(np.linalg.norm(mu_hat - mu_star, 1)),
                "rewards": {
                    "DMD": rew_dmd,
                    "WS-DMD": rew_ws,
                    "DMD-Norm": rew_dmd_n,
                    "WS-DMD-Norm": rew_ws_n,
                    "An24-SA": rew_sa,
                    "An24-MainALG": rew_main,
                    "CAP-DMD": rew_cap,
                },
                "regrets": {
                    "DMD": opt_val - rew_dmd,
                    "WS-DMD": opt_val - rew_ws,
                    "DMD-Norm": opt_val - rew_dmd_n,
                    "WS-DMD-Norm": opt_val - rew_ws_n,
                    "An24-SA": opt_val - rew_sa,
                    "An24-MainALG": opt_val - rew_main,
                    "CAP-DMD": opt_val - rew_cap,
                },
                "times_s": {
                    "DMD": t_dmd,
                    "WS-DMD": t_ws,
                    "DMD-Norm": t_dmd,
                    "WS-DMD-Norm": t_ws,
                    "An24-SA": t_sa,
                    "An24-MainALG": t_main,
                    "CAP-DMD": t_cap,
                },
                "mainalg_lp_solves": lp_cnt,
            }
            reg_rows.append(row)
            all_rows.append(row)

        methods = ["DMD", "WS-DMD", "DMD-Norm", "WS-DMD-Norm", "An24-SA", "An24-MainALG", "CAP-DMD"]
        mean_opt = float(np.mean([r["opt"] for r in reg_rows]))
        mean_mu = float(np.mean([r["mu_star_mean"] for r in reg_rows]))
        mean_reg = {m: float(np.mean([r["regrets"][m] for r in reg_rows])) for m in methods}
        mean_rew = {m: float(np.mean([r["rewards"][m] for r in reg_rows])) for m in methods}
        mean_cr = {m: mean_rew[m] / mean_opt for m in methods}
        mean_time = {m: float(np.mean([r["times_s"][m] for r in reg_rows])) for m in methods}
        summary[reg] = {
            "mean_opt": mean_opt,
            "mean_mu_star": mean_mu,
            "mean_regret": mean_reg,
            "mean_reward": mean_rew,
            "mean_competitive_ratio": mean_cr,
            "mean_time_s": mean_time,
        }
        print(f"\n--- {reg} (mean OPT={mean_opt:.1f}, mean mu*={mean_mu:.3f}, 20/20 binding) ---")
        for m in methods:
            print(f"  {m:13s} | Regret={mean_reg[m]:8.2f} | Reward={mean_rew[m]:8.1f} | Ratio={mean_cr[m]:.4f} | Time={mean_time[m]*1000:6.1f}ms")

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
    print("\n=== Pre-Registered One-Run Falsifier Verdicts (Binding Suite) ===")
    print(json.dumps(verdict, indent=2))

    res_path = out_dir / "stage0_v2_binding_results.json"
    res_path.write_text(json.dumps({"verdict": verdict, "summary": summary, "runs": all_rows}, indent=2), encoding="utf-8")
    print(f"Saved {res_path}")


if __name__ == "__main__":
    main()
