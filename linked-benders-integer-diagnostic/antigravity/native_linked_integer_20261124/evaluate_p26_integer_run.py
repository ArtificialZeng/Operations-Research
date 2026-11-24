"""Separate no-leakage post-run evaluator for the Diaz p26 single-tree integer pilot.

Runs strictly AFTER the cold worker (`linked_benders_integer_p26.py`) exits:
  1. Reprices each DISTINCT recorded final binary layout ONCE (with equal bounded
     post-processing budget outside search clocks) using frozen
     `experiments/liu_lost_sales/solve.py:verify(data, layout, deadline)` across all
     200 original scenarios, including the fixed dummy facility.
  2. Preserves the worker's grid-repaired feasible upper bound as an explicit fallback
     if exact repricing does not finish within its post-processing cap, while requiring
     complete 200-scenario exact repricing to qualify for exact zero incumbent gap.
  3. Compares verified incumbents against the separately sealed exact p26 optimum in
     `experiments/diaz_lost_sales/p26_class9_finite.json` strictly as an independent
     post-run incumbent evaluation (never conflated with SCIP's numeric dual bound).
  4. Evaluates the pre-registered advancement vs. closure gate against both plain A1
     (`orig_single`) and amended strong baseline A2 (`orig_multi_floor`).
"""

from __future__ import annotations

import os

for _env_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_env_var, "1")

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
import sys
from time import perf_counter

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
LINKED_ROOT_DIR = REPO_ROOT / "experiments" / "linked_root"
LIU_DIR = REPO_ROOT / "experiments" / "liu_lost_sales"
for _p in (str(LINKED_ROOT_DIR), str(LIU_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from run_root import load_case
import solve as liu_solve  # frozen experiments/liu_lost_sales/solve.py


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-json", type=Path, required=True, help="Raw JSON produced by linked_benders_integer_p26.py")
    parser.add_argument(
        "--reprice-seconds-per-layout",
        type=float,
        default=30.0,
        help="Equal post-processing cap (seconds) per distinct final binary layout for liu_lost_sales.solve.verify.",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    t0 = perf_counter()
    raw = json.loads(args.raw_json.read_text(encoding="utf-8"))
    if raw.get("case") != "p26":
        raise ValueError(f"Expected p26 raw worker JSON, got case={raw.get('case')}")

    data, profile = load_case("p26")
    if raw["input_profile"]["instance_sha256"] != profile["instance_sha256"]:
        raise ValueError("Worker JSON input_sha256 does not match sealed p26")
    dummy_idx = len(data.capacities) - 1

    # Load separately sealed post-run exact references (never accessible to cold workers).
    ref_ip_path = REPO_ROOT / "experiments" / "diaz_lost_sales" / "p26_class9_finite.json"
    ref_lp_path = REPO_ROOT / "experiments" / "linked_root" / "runs_45s" / "p26_linked_separated.json"
    ref_ip = json.loads(ref_ip_path.read_text(encoding="utf-8"))
    ref_lp = json.loads(ref_lp_path.read_text(encoding="utf-8"))
    z_ref_ip = Fraction(ref_ip["global_upper"])
    if z_ref_ip != Fraction(ref_ip["global_lower"]):
        raise ValueError("Sealed p26 IP reference does not have equal exact lower and upper bounds")
    u_ref_lp = Fraction(ref_lp["certificate"]["upper"])

    # 1. Exact neutral repricing of each DISTINCT final binary layout once under equal post-run budget.
    arms = raw["arms"]
    distinct_repricing: dict[str, dict] = {}
    for arm_name, rec in arms.items():
        bits = rec["final_binary_layout"]["bits"]
        if bits in distinct_repricing:
            distinct_repricing[bits]["arms_sharing_layout"].append(arm_name)
            continue
        open_real = tuple(int(i) for i in rec["final_binary_layout"]["open_real_sites"])
        layout_with_dummy = open_real + (dummy_idx,)
        t_rep = perf_counter()
        deadline = t_rep + float(args.reprice_seconds_per_layout)
        witness = liu_solve.verify(data, layout_with_dummy, deadline)
        rep_elapsed = perf_counter() - t_rep
        if witness is not None and int(witness["exact_scenarios"]) == int(data.scenario_count):
            exact_obj = Fraction(witness["objective"])
            distinct_repricing[bits] = {
                "bits": bits,
                "layout_with_dummy": list(layout_with_dummy),
                "arms_sharing_layout": [arm_name],
                "exact_repricing_complete": True,
                "exact_scenarios": int(witness["exact_scenarios"]),
                "exact_original_objective": str(exact_obj),
                "exact_original_objective_float": float(exact_obj),
                "witness_sha256": witness["witness_sha256"],
                "reprice_seconds": float(rep_elapsed),
            }
        else:
            distinct_repricing[bits] = {
                "bits": bits,
                "layout_with_dummy": list(layout_with_dummy),
                "arms_sharing_layout": [arm_name],
                "exact_repricing_complete": False,
                "exact_scenarios": None if witness is None else int(witness["exact_scenarios"]),
                "exact_original_objective": None,
                "exact_original_objective_float": None,
                "witness_sha256": None,
                "reprice_seconds": float(rep_elapsed),
                "note": "Exact 200-scenario repricing incomplete within post-processing cap; falling back to grid-repaired upper bound (cannot qualify for exact zero incumbent gap).",
            }

    # 2. Per-arm post-run scoring & soundness checks.
    per_arm: dict[str, dict] = {}
    all_valid = True
    for arm_name, rec in arms.items():
        bits = rec["final_binary_layout"]["bits"]
        rep = distinct_repricing[bits]
        u_grid = Fraction(rec["grid_primal_fallback"]["grid_repaired_original_upper"])
        l_cert_lp = Fraction(rec["exact_cut_lp_lower"]["exact_certified_cut_lp_lower"])
        numeric_bb = rec["gscip_stats"]["numeric_mip_dual_bound_diagnostic_not_exact_proof"]

        exact_complete = bool(rep["exact_repricing_complete"])
        u_eval = Fraction(rep["exact_original_objective"]) if exact_complete else u_grid
        inc_source = "exact_200_scenario_liu_verify" if exact_complete else "grid_repaired_fallback_incomplete_exact_repricing"

        ref_gap = (u_eval - z_ref_ip) / z_ref_ip
        exact_zero_gap_qualified = bool(exact_complete and u_eval == z_ref_ip)
        sound_inc_ge_opt = bool(u_eval >= z_ref_ip)
        sound_grid_ge_exact = bool((not exact_complete) or (u_grid >= u_eval))
        sound_lp = bool(l_cert_lp <= u_ref_lp and l_cert_lp <= u_eval)
        valid = bool(
            rec["solve_calls"] == 1
            and rec["final_binary_layout"]["is_binary_opening"]
            and sound_inc_ge_opt
            and sound_grid_ge_exact
            and sound_lp
        )
        if not valid:
            all_valid = False

        numeric_mip_gap_against_eval = (
            (float(u_eval) - numeric_bb) / float(u_eval) if numeric_bb is not None else None
        )

        per_arm[arm_name] = {
            "valid": valid,
            "incumbent_objective_source": inc_source,
            "exact_repricing_complete": exact_complete,
            "evaluated_incumbent_objective": str(u_eval),
            "evaluated_incumbent_objective_float": float(u_eval),
            "grid_repaired_fallback_objective": str(u_grid),
            "trimmed_flow_grid_ticks": int(rec["grid_primal_fallback"]["trimmed_flow_grid_ticks"]),
            "exact_certified_cut_lp_lower": str(l_cert_lp),
            "exact_certified_cut_lp_lower_float": float(l_cert_lp),
            "numeric_mip_dual_bound_diagnostic_not_exact_proof": numeric_bb,
            "numeric_mip_gap_diagnostic": numeric_mip_gap_against_eval,
            "post_run_exact_reference_incumbent_gap": str(ref_gap),
            "post_run_exact_reference_incumbent_gap_float": float(ref_gap),
            "qualifies_exact_zero_incumbent_gap": exact_zero_gap_qualified,
            "sound_incumbent_ge_sealed_ip_opt": sound_inc_ge_opt,
            "sound_grid_ge_exact_reprice": sound_grid_ge_exact,
            "sound_cut_lp_le_sealed_lp_upper": sound_lp,
            "termination": rec["termination"],
            "unique_binary_layouts_evaluated": int(
                rec["callback_stats"]["total_unique_binary_layouts_evaluated_including_seed"]
            ),
            "before_certification_seconds": float(rec["timing_seconds"]["before_certification"]),
        }

    # 3. Pre-registered advancement vs. closure gate (comparing B against BOTH A1 and strong A2).
    a1_name, a2_name, b_name = "orig_single", "orig_multi_floor", "sep_single_hinge"
    p_a1, p_a2, p_b = per_arm[a1_name], per_arm[a2_name], per_arm[b_name]
    all_exact_repricing_complete = all(per_arm[name]["exact_repricing_complete"] for name in (a1_name, a2_name, b_name))

    if not all_valid:
        gate = {
            "verdict": "inconclusive_invalid_arm",
            "advance_to_p50": False,
        }
    elif not all_exact_repricing_complete:
        gate = {
            "verdict": "inconclusive_incomplete_exact_repricing",
            "advance_to_p50": False,
            "note": "Exact 200-scenario original-price repricing did not complete for all arms; auxiliary grid-repaired uppers are retained for feasibility only and cannot decide advancement.",
        }
    else:
        opt_a1 = bool(p_a1["termination"]["reached_numeric_optimal"] and p_a1["qualifies_exact_zero_incumbent_gap"])
        opt_a2 = bool(p_a2["termination"]["reached_numeric_optimal"] and p_a2["qualifies_exact_zero_incumbent_gap"])
        opt_b = bool(p_b["termination"]["reached_numeric_optimal"] and p_b["qualifies_exact_zero_incumbent_gap"])
        best_orig_opt = opt_a1 or opt_a2

        sw_a1 = p_a1["unique_binary_layouts_evaluated"]
        sw_a2 = p_a2["unique_binary_layouts_evaluated"]
        sw_b = p_b["unique_binary_layouts_evaluated"]
        t_a1 = p_a1["before_certification_seconds"]
        t_a2 = p_a2["before_certification_seconds"]
        t_b = p_b["before_certification_seconds"]

        if opt_b and best_orig_opt:
            # Protocol Branch 1: compare Arm B against BOTH original arms (A1 and A2),
            # not only the subset of original arms that returned OPTIMAL.
            min_orig_sw = min(sw_a1, sw_a2)
            min_orig_t = min(t_a1, t_a2)
            meets_sw_vs_a1 = bool((sw_a1 - sw_b >= 5) and (sw_b * 4 <= sw_a1 * 3))
            meets_sw_vs_a2 = bool((sw_a2 - sw_b >= 5) and (sw_b * 4 <= sw_a2 * 3))
            meets_t_vs_a1 = bool(t_b <= 0.80 * t_a1)
            meets_t_vs_a2 = bool(t_b <= 0.80 * t_a2)
            meets_sw = bool(meets_sw_vs_a1 and meets_sw_vs_a2)
            meets_t = bool(meets_t_vs_a1 and meets_t_vs_a2)
            advance = bool(meets_sw and meets_t)
            gate = {
                "branch": "branch_1_both_optimal_with_exact_zero_incumbent_gap",
                "opt_flags": {a1_name: opt_a1, a2_name: opt_a2, b_name: opt_b},
                "sweeps": {a1_name: sw_a1, a2_name: sw_a2, b_name: sw_b},
                "seconds": {a1_name: t_a1, a2_name: t_a2, b_name: t_b},
                "min_orig_sweeps_all": min_orig_sw,
                "min_orig_seconds_all": min_orig_t,
                "meets_sweep_reduction_vs_a1": meets_sw_vs_a1,
                "meets_sweep_reduction_vs_a2": meets_sw_vs_a2,
                "meets_time_reduction_vs_a1": meets_t_vs_a1,
                "meets_time_reduction_vs_a2": meets_t_vs_a2,
                "meets_sweep_reduction_gate": meets_sw,
                "meets_time_reduction_gate": meets_t,
                "advance_to_p50": advance,
                "verdict": "advance_to_p50" if advance else "close_single_tree_integer_line",
            }
        else:
            g_a1 = p_a1["numeric_mip_gap_diagnostic"]
            g_a2 = p_a2["numeric_mip_gap_diagnostic"]
            g_b = p_b["numeric_mip_gap_diagnostic"]
            u_a1 = Fraction(p_a1["evaluated_incumbent_objective"])
            u_a2 = Fraction(p_a2["evaluated_incumbent_objective"])
            u_b = Fraction(p_b["evaluated_incumbent_objective"])
            min_orig_u = min(u_a1, u_a2)
            orig_both_bad_timeout = (
                (not opt_a1)
                and (not opt_a2)
                and ((not p_a1["qualifies_exact_zero_incumbent_gap"]) or (g_a1 is None or g_a1 >= 0.0025))
                and ((not p_a2["qualifies_exact_zero_incumbent_gap"]) or (g_a2 is None or g_a2 >= 0.0025))
            )
            cond_2a = bool(opt_b and orig_both_bad_timeout)
            cond_2b = bool(
                p_b["exact_repricing_complete"]
                and (min_orig_u - u_b) * 1000 >= z_ref_ip
                and g_b is not None
                and g_a1 is not None
                and g_a2 is not None
                and (min(g_a1, g_a2) - g_b >= 0.0025)
            )
            advance = bool(cond_2a or cond_2b)
            gate = {
                "branch": "branch_2_incomplete_or_mixed",
                "opt_flags": {a1_name: opt_a1, a2_name: opt_a2, b_name: opt_b},
                "cond_2a_sep_optimal_while_both_orig_incomplete": cond_2a,
                "cond_2b_sep_exact_incumbent_and_gap_dominance": cond_2b,
                "sweeps": {a1_name: sw_a1, a2_name: sw_a2, b_name: sw_b},
                "seconds": {a1_name: t_a1, a2_name: t_a2, b_name: t_b},
                "advance_to_p50": advance,
                "verdict": "advance_to_p50" if advance else "close_single_tree_integer_line",
            }

    out_payload = {
        "evaluator": "post_run_p26_integer_evaluator",
        "note": (
            "Executed strictly after cold worker termination. Independently reprices distinct final binary "
            "layouts on all 200 original scenarios via frozen experiments/liu_lost_sales/solve.py:verify. "
            "Post-run reference incumbent gap is separate from SCIP floating-point dual bounds and does not "
            "constitute a solver-side exact optimality proof."
        ),
        "raw_worker_json": str(args.raw_json),
        "raw_worker_sha256": _file_sha256(args.raw_json),
        "evaluator_sha256": _file_sha256(Path(__file__).resolve()),
        "reused_verifier_file": str(LIU_DIR / "solve.py"),
        "reused_verifier_sha256": _file_sha256(LIU_DIR / "solve.py"),
        "sealed_ip_reference_file": str(ref_ip_path),
        "sealed_ip_reference_sha256": _file_sha256(ref_ip_path),
        "sealed_p26_exact_ip_optimum": str(z_ref_ip),
        "sealed_p26_exact_ip_optimum_float": float(z_ref_ip),
        "sealed_p26_lp_upper": str(u_ref_lp),
        "reprice_seconds_cap_per_layout": float(args.reprice_seconds_per_layout),
        "distinct_final_layouts_repriced": distinct_repricing,
        "all_arms_valid": all_valid,
        "per_arm": per_arm,
        "preregistered_gate": gate,
        "evaluator_wall_seconds": float(perf_counter() - t0),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        json.dump(out_payload, fh, indent=2, allow_nan=False)
        fh.write("\n")

    for arm_name in (a1_name, a2_name, b_name):
        p = per_arm[arm_name]
        print(
            f"[post-run | {arm_name}] valid={p['valid']} exact_reprice={p['exact_repricing_complete']} "
            f"U={p['evaluated_incumbent_objective_float']:.6f} ref_gap={p['post_run_exact_reference_incumbent_gap_float']:.3e} "
            f"zero_gap={p['qualifies_exact_zero_incumbent_gap']} sweeps={p['unique_binary_layouts_evaluated']} "
            f"term={p['termination']['reason']}/{p['termination']['limit']}"
        )
    print(f"[post-run | gate] verdict={gate['verdict']} advance_to_p50={gate['advance_to_p50']}")
    print(f"Wrote post-run evaluation JSON: {args.out}")


if __name__ == "__main__":
    main()
