"""Step 3: Formal Analytical Principal-Agent & Reverse-Logistics Recall Contract
Model (Section 2).

Solves closed-form equilibrium boundaries across the 3 recall contract regimes:
  - R: Physical Return (store / prepaid mail-back reverse logistics)
  - D/U: Direct First-Party / Unverified Refund (indexed by buyer observability theta)
  - P: Proof-of-Destruction (consumer physical mutilation + photographic verification)

Verifies Propositions 1-4 numerically and exports exact phase-diagram coordinates
to results/03_theory_equilibrium.json for Figure 2A.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
OUT_JSON = BASE_DIR / "results" / "03_theory_equilibrium.json"


def contract_costs(
    p: float,
    c_rev: float,
    theta: float,
    a: float,
    lam: float,
    q0: float = 0.78,
    gamma: float = 0.012,
    k_r: float = 8.0,
    k_p: float = 20.0,
    alpha: float = 0.35,
    phi: float = 0.25,
) -> dict[str, float]:
    """Evaluate closed-form per-unit seller cost under R, D/U, and P."""
    q_r = max(0.05, q0 - gamma * k_r)
    q_p = max(0.05, q0 - gamma * k_p)

    c_R = q_r * (p + c_rev) + lam * (1.0 - q_r)
    c_DU = q0 * p + alpha * (1.0 - theta) * p + lam * ((1.0 - q0) + phi * (1.0 - theta))
    c_P = q_p * (p + a) + lam * (1.0 - q_p)
    return {
        "q_0": q0,
        "q_R": q_r,
        "q_P": q_p,
        "C_R": c_R,
        "C_DU": c_DU,
        "C_P": c_P,
    }


def closed_form_cutoffs(
    p: float,
    a: float,
    lam: float,
    q0: float = 0.78,
    gamma: float = 0.012,
    k_r: float = 8.0,
    k_p: float = 20.0,
    alpha: float = 0.35,
    phi: float = 0.25,
) -> dict[str, float]:
    """Closed-form indifference boundaries:
      c_rev*(p, a, lam): P beats R iff c_rev > c_rev*
      theta*(p, a, lam): P beats D/U iff theta < theta*
      theta_RD(c_rev):   D/U beats R iff theta > theta_RD
    """
    q_r = max(0.05, q0 - gamma * k_r)
    q_p = max(0.05, q0 - gamma * k_p)

    c_rev_star = (q_p / q_r) * a + ((q_r - q_p) / q_r) * (lam - p)
    denom = alpha * p + lam * phi
    theta_star = 1.0 - (q_p * a - (q0 - q_p) * (p - lam)) / denom
    return {
        "q_0": q0,
        "q_R": q_r,
        "q_P": q_p,
        "c_rev_star": float(c_rev_star),
        "theta_star": float(theta_star),
        "d_crev_d_lam": float((q_r - q_p) / q_r),
        "d_crev_d_a": float(q_p / q_r),
        "d_crev_d_p": float(-(q_r - q_p) / q_r),
        "d_margin_PU_d_p": float(alpha + (q0 - q_p)),  # at theta=0
    }


def main() -> int:
    # Baseline calibrated parameters (illustrative durable consumer product p = $60)
    params = {
        "p_base": 60.0,
        "a_2022": 18.0,
        "a_2026": 6.0,
        "lam_us": 140.0,
        "lam_fd": 35.0,
        "q0": 0.78,
        "gamma": 0.012,
        "k_r": 8.0,
        "k_p": 20.0,
        "alpha": 0.35,
        "phi": 0.25,
        "H_social": 240.0,
        "e_haz_lithium": 18.0,
    }

    # 1. Exact closed-form cutoffs for domestic (lam_us) vs foreign-direct (lam_fd) in 2022 vs 2026
    cut_us_2022 = closed_form_cutoffs(params["p_base"], params["a_2022"], params["lam_us"])
    cut_us_2026 = closed_form_cutoffs(params["p_base"], params["a_2026"], params["lam_us"])
    cut_fd_2022 = closed_form_cutoffs(params["p_base"], params["a_2022"], params["lam_fd"])
    cut_fd_2026 = closed_form_cutoffs(params["p_base"], params["a_2026"], params["lam_fd"])

    # 2. Verify all 4 theoretical propositions numerically
    # Prop 1: c_rev_star_FD < c_rev_star_US AND (C_DU - C_P) strictly increasing in p
    prop1_crev_gap = cut_fd_2022["c_rev_star"] < cut_us_2022["c_rev_star"]
    prices = [20.0, 50.0, 100.0, 200.0, 400.0]
    pu_margins_p = []
    pr_margins_p = []
    for pv in prices:
        c_lo = contract_costs(pv, c_rev=45.0, theta=0.05, a=params["a_2026"], lam=params["lam_fd"])
        pu_margins_p.append(round(c_lo["C_DU"] - c_lo["C_P"], 4))
        pr_margins_p.append(round(c_lo["C_R"] - c_lo["C_P"], 4))
    prop1_price_monotone = all(pu_margins_p[i + 1] > pu_margins_p[i] for i in range(len(pu_margins_p) - 1))

    # Prop 2 (DTC First-Party Observability Shield): For domestic seller (lam_us, a_2026),
    # high-theta DTC (theta=0.92) chooses D/U over P even with high c_rev, while low-theta
    # anonymous retail/3P (theta=0.10) with high c_rev chooses P!
    c_dtc = contract_costs(params["p_base"], c_rev=35.0, theta=0.92, a=params["a_2026"], lam=params["lam_us"])
    c_3p_us = contract_costs(params["p_base"], c_rev=35.0, theta=0.10, a=params["a_2026"], lam=params["lam_us"])
    c_bm = contract_costs(params["p_base"], c_rev=10.0, theta=0.12, a=params["a_2026"], lam=params["lam_us"])
    prop2_dtc_shield = (c_dtc["C_DU"] < c_dtc["C_P"]) and (c_3p_us["C_P"] < c_3p_us["C_DU"])

    # Prop 3 (Audit-Cost Diffusion): Lowering a from a_2022 to a_2026 strictly reduces c_rev_star
    # and strictly raises theta_star (expanding the P equilibrium region into domestic channels)
    prop3_diffusion = (cut_us_2026["c_rev_star"] < cut_us_2022["c_rev_star"]) and (
        cut_us_2026["theta_star"] > cut_us_2022["theta_star"]
    )

    # Prop 4 (Social Welfare & Hazardous-Waste Externalization Wedge):
    q_r, q_p = cut_fd_2026["q_R"], cut_fd_2026["q_P"]
    c_fd_2026 = contract_costs(params["p_base"], c_rev=45.0, theta=0.05, a=params["a_2026"], lam=params["lam_fd"])
    private_gain_P_over_R = c_fd_2026["C_R"] - c_fd_2026["C_P"]
    social_wedge_P_over_R = (
        (q_p * params["a_2026"] - q_r * 45.0)
        + (q_p * params["k_p"] - q_r * params["k_r"])
        + params["H_social"] * (q_r - q_p)
        + q_p * params["e_haz_lithium"]
    )
    prop4_socially_excessive = (private_gain_P_over_R > 0) and (social_wedge_P_over_R > 0)

    # 3. Phase-diagram grid in (c_rev / p, theta) space for Figure 2A (domestic 2026 & 2022 shift)
    crev_ratio_grid = np.linspace(0.0, 1.25, 126)
    theta_grid = np.linspace(0.0, 1.0, 101)
    # Regime map under 2026 institutional audit cost a_2026 (0=R, 1=D/U, 2=P) using lam_us
    regime_grid_us_2026 = np.zeros((len(theta_grid), len(crev_ratio_grid)), dtype=int)
    for i, th in enumerate(theta_grid):
        for j, cr_rat in enumerate(crev_ratio_grid):
            cc = contract_costs(params["p_base"], c_rev=cr_rat * params["p_base"], theta=th, a=params["a_2026"], lam=params["lam_us"])
            vals = [cc["C_R"], cc["C_DU"], cc["C_P"]]
            regime_grid_us_2026[i, j] = int(np.argmin(vals))

    # Exact analytical boundary curves for clean plotting in (c_rev/p, theta) coordinates:
    # 1) R vs D/U boundary: C_R = C_DU => theta_RD(c_rev)
    q0 = params["q0"]
    denom_us = params["alpha"] * params["p_base"] + params["lam_us"] * params["phi"]
    theta_RD_curve = []
    for cr_rat in crev_ratio_grid:
        cr = cr_rat * params["p_base"]
        # C_R - C_DU = 0 => (1 - theta) * denom = q_r*(p+cr) - q0*p + lam*(q0 - q_r)
        rhs = q_r * (params["p_base"] + cr) - q0 * params["p_base"] + params["lam_us"] * (q0 - q_r)
        th_val = 1.0 - rhs / denom_us
        theta_RD_curve.append(float(th_val))

    # Empirical archetype positions in conceptual (c_rev/p, theta) space for Figure 2A overlay
    archetype_markers = {
        "1_Mkt_FD_China": {"crev_ratio": 1.05, "theta": 0.08, "label": "Mkt FD (China)"},
        "2_Mkt_FD_NonChina": {"crev_ratio": 0.78, "theta": 0.18, "label": "Mkt FD (Non-China)"},
        "3_Mkt_True_US": {"crev_ratio": 0.52, "theta": 0.22, "label": "Mkt U.S. Entity"},
        "4_DTC_Online_Only": {"crev_ratio": 0.42, "theta": 0.88, "label": "DTC Online-Only"},
        "5_Omnichannel": {"crev_ratio": 0.24, "theta": 0.35, "label": "Omnichannel"},
        "6_Brick_and_Mortar": {"crev_ratio": 0.16, "theta": 0.15, "label": "Brick & Mortar"},
    }

    payload = {
        "parameters": params,
        "cutoffs": {
            "us_2022": cut_us_2022,
            "us_2026": cut_us_2026,
            "fd_2022": cut_fd_2022,
            "fd_2026": cut_fd_2026,
            "us_2022_crev_ratio": round(cut_us_2022["c_rev_star"] / params["p_base"], 4),
            "us_2026_crev_ratio": round(cut_us_2026["c_rev_star"] / params["p_base"], 4),
            "fd_2026_crev_ratio": round(cut_fd_2026["c_rev_star"] / params["p_base"], 4),
        },
        "proposition_verifications": {
            "prop1_fd_cutoff_lower_than_us": bool(prop1_crev_gap),
            "prop1_price_monotonicity_PU": bool(prop1_price_monotone),
            "prop1_price_grid": prices,
            "prop1_PU_cost_advantage_by_price": pu_margins_p,
            "prop1_PR_cost_advantage_by_price": pr_margins_p,
            "prop2_dtc_observability_shield": bool(prop2_dtc_shield),
            "prop2_dtc_costs": {k: round(v, 3) for k, v in c_dtc.items()},
            "prop2_3p_us_costs": {k: round(v, 3) for k, v in c_3p_us.items()},
            "prop2_bm_costs": {k: round(v, 3) for k, v in c_bm.items()},
            "prop3_audit_cost_diffusion": bool(prop3_diffusion),
            "prop4_private_vs_social_wedge": bool(prop4_socially_excessive),
            "prop4_private_seller_gain_P_over_R": round(private_gain_P_over_R, 3),
            "prop4_social_cost_excess_P_over_R": round(social_wedge_P_over_R, 3),
        },
        "phase_diagram": {
            "crev_ratio_grid": [round(float(x), 4) for x in crev_ratio_grid],
            "theta_grid": [round(float(x), 4) for x in theta_grid],
            "theta_RD_curve": [round(float(x), 4) for x in theta_RD_curve],
            "regime_grid_us_2026": regime_grid_us_2026.tolist(),
            "archetype_markers": archetype_markers,
        },
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    print("[DONE STEP 3] Formal Principal-Agent & Reverse-Logistics Equilibrium Verified:", flush=True)
    print(f"  q_0={q0:.3f}, q_R={q_r:.3f}, q_P={q_p:.3f}", flush=True)
    print(f"  c_rev*/p (US 2022) = {payload['cutoffs']['us_2022_crev_ratio']:.3f} -> (US 2026) = {payload['cutoffs']['us_2026_crev_ratio']:.3f} | (FD 2026) = {payload['cutoffs']['fd_2026_crev_ratio']:.3f}", flush=True)
    print(f"  theta*   (US 2022) = {cut_us_2022['theta_star']:.3f} -> (US 2026) = {cut_us_2026['theta_star']:.3f} | (FD 2026) = {cut_fd_2026['theta_star']:.3f}", flush=True)
    for k, v in payload["proposition_verifications"].items():
        if isinstance(v, bool):
            print(f"  [CHECK] {k}: {v}", flush=True)
    assert all(v for v in payload["proposition_verifications"].values() if isinstance(v, bool)), "A theoretical proposition failed!"
    return 0


if __name__ == "__main__":
    sys.exit(main())
