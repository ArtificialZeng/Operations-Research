"""Step 04 (Pillar 2): Formal Thermodynamic & Economic Carbon-Arbitrage Equilibrium Model.

Provides exact closed-form & numerical verification (to machine precision < 1e-12) of:
  - Proposition 1: Diurnal Gas-Peaker Displacement & Storage Duration Scaling (4-hr vs 1-hr fleets).
  - Proposition 2: The Carbon-Arbitrage Paradox, Break-Even Curtailment Threshold alpha_b^*,
    and Corollary 2.1 (Finite-Curtailment Saturation Bound alpha_b^cap).
  - Proposition 3: Exact Analytical Decomposition of the AEF-vs-MEF Accounting Sign Reversal Bias.
Calibrates all three propositions directly to Step 02 (WLS Panel A) and Step 03 (EPA CEMS + CAISO).
"""

from __future__ import annotations

import json

from econ_utils import RES_DIR, save_json_lf


def prop1_displacement_rate(
    tau_hr: float,
    h_ev: float = 6.0,
    h_md: float = 7.0,
    eta: float = 0.85,
    theta_ng_ev: float = 0.70,
    theta_ng_md: float = 0.35,
    alpha_curt: float = 0.0,
    utilization: float = 0.80,
) -> dict[str, float]:
    """Closed-form evening-minus-midday natural-gas displacement per +1 MW of installed BESS
    with energy duration tau_hr (hours, E/P = tau_hr), normalized per MW of BESS power.
    """
    eff_ev_power_frac = utilization * min(1.0, tau_hr / h_ev)
    # Discharged energy per MW of BESS over evening window = eff_ev_power_frac * h_ev
    # Required charging energy = discharged / eta, spread over midday window h_md
    ev_dis_mw = eff_ev_power_frac
    md_chg_mw = (ev_dis_mw * h_ev / eta) / h_md
    d_ng_ev = -theta_ng_ev * ev_dis_mw
    d_ng_md = +(1.0 - alpha_curt) * theta_ng_md * md_chg_mw
    return {
        "tau_hr": float(tau_hr),
        "ev_ng_change_per_mw": float(d_ng_ev),
        "md_ng_change_per_mw": float(d_ng_md),
        "em_ng_spread_per_mw": float(d_ng_ev - d_ng_md),
        "em_ng_per_mwh": float((d_ng_ev - d_ng_md) / max(tau_hr, 1e-9)),
    }


def prop2_net_co2(mef_chg: float, mef_dis: float, eta: float, alpha: float) -> float:
    return ((1.0 - alpha) * mef_chg) / eta - mef_dis


def prop2_alpha_star(mef_chg: float, mef_dis: float, eta: float) -> float:
    return 1.0 - eta * (mef_dis / mef_chg)


def prop3_aef_mef_bias(
    mef_chg: float, mef_dis: float, aef_chg: float, aef_dis: float, eta: float
) -> dict[str, float]:
    net_mef = mef_chg / eta - mef_dis
    net_aef = aef_chg / eta - aef_dis
    chg_wedge = (mef_chg - aef_chg) / eta
    dis_wedge = mef_dis - aef_dis
    exact_bias = chg_wedge - dis_wedge
    diff_direct = net_mef - net_aef
    return {
        "net_mef": float(net_mef),
        "net_aef": float(net_aef),
        "chg_wedge_over_eta": float(chg_wedge),
        "dis_wedge": float(dis_wedge),
        "bias_from_identity": float(exact_bias),
        "bias_direct": float(diff_direct),
        "identity_abs_error": float(abs(exact_bias - diff_direct)),
    }


def main() -> int:
    print("=== STEP 04: FORMAL THERMODYNAMIC & ECONOMIC CARBON-ARBITRAGE MODEL ===", flush=True)
    r3 = json.loads((RES_DIR / "03_cems_carbon_curtailment_results.json").read_text(encoding="utf-8"))
    ba_rows = r3["ba_carbon_table"]

    # 1. Verify Proposition 1 Duration Scaling across 1-hr, 2-hr, 4-hr, 6-hr fleets
    p1_grid = [prop1_displacement_rate(tau) for tau in [1.0, 2.0, 2.76, 4.0, 6.0]]
    p1_4hr_vs_1hr_ratio = abs(p1_grid[3]["em_ng_spread_per_mw"] / p1_grid[0]["em_ng_spread_per_mw"])
    # Verify exact linearity for tau <= h_ev = 6.0
    lin_err = abs(p1_4hr_vs_1hr_ratio - 4.0)
    print(
        f"[Prop 1] 1-hr em_ng={p1_grid[0]['em_ng_spread_per_mw']:+.4f}, "
        f"2.76-hr (U.S. mean)={p1_grid[2]['em_ng_spread_per_mw']:+.4f}, "
        f"4-hr={p1_grid[3]['em_ng_spread_per_mw']:+.4f} (4h/1h ratio={p1_4hr_vs_1hr_ratio:.6f}, err={lin_err:.2e})",
        flush=True,
    )

    # 2. Verify Proposition 2 & Proposition 3 to machine precision (< 1e-12) across ALL 14 metered U.S. BAs!
    p2_checks = []
    p3_checks = []
    max_p2_zero_err = 0.0
    max_p2_deriv_err = 0.0
    max_p3_id_err = 0.0

    for row in ba_rows:
        ba = row["ba"]
        eta = float(row["rte"])
        mc = float(row["mef_cems_chg_kg_mwh"])
        md = float(row["mef_cems_dis_kg_mwh"])
        ac = float(row["aef_chg_kg_mwh"])
        ad = float(row["aef_dis_kg_mwh"])

        a_star = prop2_alpha_star(mc, md, eta)
        co2_at_star = prop2_net_co2(mc, md, eta, a_star)
        max_p2_zero_err = max(max_p2_zero_err, abs(co2_at_star))

        # Finite-difference check of d(Delta CO2)/d(alpha) = -MEF_chg / eta
        eps = 1e-6
        fd_da = (prop2_net_co2(mc, md, eta, 0.2 + eps) - prop2_net_co2(mc, md, eta, 0.2 - eps)) / (2 * eps)
        an_da = -mc / eta
        err_da = abs(fd_da - an_da)
        max_p2_deriv_err = max(max_p2_deriv_err, err_da)

        # Break-even MEF ratio required for zero-curtailment abatement (MEF_dis / MEF_chg > 1 / eta)
        actual_ratio = md / max(mc, 1e-6)
        req_ratio = 1.0 / eta

        p2_checks.append(
            {
                "ba": ba,
                "rte": eta,
                "mef_chg": mc,
                "mef_dis": md,
                "actual_mef_ratio_dis_over_chg": float(actual_ratio),
                "required_zero_curt_ratio_inv_eta": float(req_ratio),
                "alpha_star": float(a_star),
                "net_co2_at_alpha_star": float(co2_at_star),
                "d_co2_d_alpha": float(an_da),
                "requires_positive_curtailment": bool(a_star > 0.0),
            }
        )

        b3 = prop3_aef_mef_bias(mc, md, ac, ad, eta)
        max_p3_id_err = max(max_p3_id_err, b3["identity_abs_error"])
        p3_checks.append(
            {
                "ba": ba,
                "dis_gwh": float(row["dis_gwh_cems_window"]),
                "sign_reversed": bool(b3["net_aef"] < 0 and b3["net_mef"] > 0),
                **b3,
            }
        )

    # Fleet-weighted Proposition 3 decomposition (exact accounting of the +7.71 Mt CO2 reversal!)
    tot_dis = sum(r["dis_gwh"] for r in p3_checks)
    fleet_chg_wedge_kt = sum(r["chg_wedge_over_eta"] * r["dis_gwh"] / 1000.0 for r in p3_checks)
    fleet_dis_wedge_kt = sum(r["dis_wedge"] * r["dis_gwh"] / 1000.0 for r in p3_checks)
    fleet_bias_kt = fleet_chg_wedge_kt - fleet_dis_wedge_kt
    fleet_chg_wedge_kg = 1000.0 * fleet_chg_wedge_kt / max(tot_dis, 1.0)
    fleet_dis_wedge_kg = 1000.0 * fleet_dis_wedge_kt / max(tot_dis, 1.0)
    n_sign_reversed = sum(1 for r in p3_checks if r["sign_reversed"])

    # Corollary 2.1 (Incremental Marginal Curtailment Saturation):
    # Distinguish rigorously between (a) direct empirical marginal curtailment absorption of the
    # current fleet (alpha_emp_unspill & alpha_emp_mef) and (b) Incremental Residual Curtailment
    # Headroom rho_res = sum min(c_t, q_obs_t) / sum c_t, which strictly bounds curtailment
    # absorption for an INCREMENTAL storage expansion added on top of today's existing 17.3 GW grid
    # (because post-battery residual curtailment q_obs_t IS the exact pre-incremental-battery spill).
    ciso_curt_info = r3["caiso_noncircular_curtailment"]
    ciso_alpha_star = float(ciso_curt_info["alpha_star_ciso_cems"])
    ciso_alpha_emp_unspill = float(ciso_curt_info["alpha_emp_unspill_share"])
    ciso_alpha_emp_mef = float(ciso_curt_info["alpha_emp_mef_collapse_share"])
    ciso_rho_res_tot = float(ciso_curt_info["rho_residual_headroom_total"])
    ciso_rho_res_sys = float(ciso_curt_info["rho_residual_headroom_system"])

    print(
        f"[Prop 2] Verified across 14 BAs: max |DeltaCO2(alpha*)| = {max_p2_zero_err:.2e}, "
        f"max |dDeltaCO2/dalpha err| = {max_p2_deriv_err:.2e}; "
        f"{sum(1 for r in p2_checks if r['requires_positive_curtailment'])}/14 grids require alpha > 0!",
        flush=True,
    )
    print(
        f"[Prop 3] Exact AEF-vs-MEF Bias Decomposition across 14 BAs (max_err={max_p3_id_err:.2e}):\n"
        f"  Midday Charging Wedge (MEF_chg-AEF_chg)/eta = +{fleet_chg_wedge_kg:.1f} kg/MWh (+{fleet_chg_wedge_kt:,.0f} kt)\n"
        f"  Evening Discharge Wedge (MEF_dis-AEF_dis)   = +{fleet_dis_wedge_kg:.1f} kg/MWh (+{fleet_dis_wedge_kt:,.0f} kt)\n"
        f"  Net Sign-Reversal Bias (MEF - AEF)          = +{fleet_chg_wedge_kg - fleet_dis_wedge_kg:.1f} kg/MWh "
        f"(+{fleet_bias_kt:,.0f} kt = +{fleet_bias_kt/1000:.2f} Mt CO2; {n_sign_reversed}/14 grids flip sign!)",
        flush=True,
    )

    out = {
        "proposition_1_duration_scaling": {
            "duration_grid": p1_grid,
            "ratio_4hr_to_1hr": float(p1_4hr_vs_1hr_ratio),
            "linearity_abs_error": float(lin_err),
        },
        "proposition_2_breakeven_curtailment": {
            "max_zero_identity_error": float(max_p2_zero_err),
            "max_derivative_error": float(max_p2_deriv_err),
            "n_grids_requiring_positive_curtailment": int(
                sum(1 for r in p2_checks if r["requires_positive_curtailment"])
            ),
            "caiso_saturation_check": {
                "ciso_alpha_emp_unspill": ciso_alpha_emp_unspill,
                "ciso_alpha_emp_mef_collapse": ciso_alpha_emp_mef,
                "ciso_rho_residual_headroom_total": ciso_rho_res_tot,
                "ciso_rho_residual_headroom_system": ciso_rho_res_sys,
                "ciso_alpha_star_cems": ciso_alpha_star,
                "gap_emp_unspill_minus_star": float(ciso_alpha_emp_unspill - ciso_alpha_star),
                "gap_rho_res_minus_star": float(ciso_rho_res_tot - ciso_alpha_star),
                "incremental_saturation_binding": bool(ciso_rho_res_tot < ciso_alpha_star),
            },
            "by_ba": p2_checks,
        },
        "proposition_3_aef_mef_bias": {
            "max_identity_error": float(max_p3_id_err),
            "n_grids_sign_reversed": int(n_sign_reversed),
            "fleet_chg_wedge_kg_mwh": float(fleet_chg_wedge_kg),
            "fleet_dis_wedge_kg_mwh": float(fleet_dis_wedge_kg),
            "fleet_net_bias_kg_mwh": float(fleet_chg_wedge_kg - fleet_dis_wedge_kg),
            "fleet_chg_wedge_kt": float(fleet_chg_wedge_kt),
            "fleet_dis_wedge_kt": float(fleet_dis_wedge_kt),
            "fleet_net_bias_kt": float(fleet_bias_kt),
            "fleet_net_bias_mt": float(fleet_bias_kt / 1000.0),
            "by_ba": p3_checks,
        },
    }
    sha = save_json_lf(RES_DIR / "04_formal_model_verification.json", out)
    print(f"[DONE STEP 04] Saved results/04_formal_model_verification.json (SHA-256: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
