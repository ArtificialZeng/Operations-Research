"""Separate no-leakage post-run evaluator for the Diaz p50 4-arm single-tree integer validation.

Runs strictly AFTER the cold worker (`linked_benders_integer_p50.py`) exits:
  1. Reprices each DISTINCT recorded final binary layout ONCE (with equal bounded
     post-processing budget outside search clocks) using frozen
     `experiments/liu_lost_sales/solve.py:verify(data, layout, deadline)` across all
     200 original scenarios, including fixed dummy index 30.
  2. Preserves the worker's grid-repaired feasible upper bound strictly as an auxiliary
     fallback if exact repricing is incomplete, marking incomplete exact repricing
     explicitly inconclusive.
  3. Compares exact-repriced incumbents against the separately sealed exact p50 IP
     reference (`experiments/diaz_lost_sales/p50_rival_continuation.json`) strictly
     post-run as an independent incumbent evaluation, never conflated with numeric
     GSCIP dual bounds or termination diagnostics.
  4. Evaluates the pre-specified 4-arm gate (`orig_single`, `orig_multi_floor`,
     matched control `orig_single_hinge_floor`, and candidate `sep_single_hinge`),
     separating Branch 1 (qualifying-optimality antecedent holds) from Branch 2
     (timeout / incomplete / exact-incumbent-tie rules).
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

ORIG_ARMS = ("orig_single", "orig_multi_floor", "orig_single_hinge_floor")
CAND_ARM = "sep_single_hinge"
ALL_ARMS = (*ORIG_ARMS, CAND_ARM)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-json", type=Path, required=True, help="Raw JSON from linked_benders_integer_p50.py")
    parser.add_argument(
        "--reprice-seconds-per-layout",
        type=float,
        default=60.0,
        help="Equal post-processing cap (seconds) per distinct final binary layout for liu_lost_sales.solve.verify.",
    )
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    t0 = perf_counter()
    raw = json.loads(args.raw_json.read_text(encoding="utf-8"))
    if raw.get("case") != "p50":
        raise ValueError(f"Expected p50 raw worker JSON, got case={raw.get('case')}")

    data, profile = load_case("p50")
    if raw["input_profile"]["instance_sha256"] != profile["instance_sha256"]:
        raise ValueError("Worker JSON instance_sha256 does not match sealed p50")
    dummy_idx = len(data.capacities) - 1

    # Load separately sealed post-run exact p50 reference ONLY here (never inside cold worker).
    diaz_dir = REPO_ROOT / "experiments" / "diaz_lost_sales"
    ref_ip_path = diaz_dir / "p50_rival_continuation.json"
    ref_lp_path = REPO_ROOT / "experiments" / "linked_root" / "runs_45s" / "p50_linked_separated.json"
    expected_ref_sha = "571642a37fc74ef660c6e356b9f9443b26e4db65cae142e175655f14e79b8d4c"
    observed_ref_sha = _file_sha256(ref_ip_path)
    if observed_ref_sha != expected_ref_sha:
        raise ValueError(
            f"Sealed p50 continuation SHA-256 mismatch: observed={observed_ref_sha} expected={expected_ref_sha}"
        )
    ref_ip = json.loads(ref_ip_path.read_text(encoding="utf-8"))

    # Follow lock_sha256 -> lock.json -> manifest_sha256 -> manifest.json -> p50 instance_sha256.
    lock_path = diaz_dir / "lock.json"
    lock_sha = _file_sha256(lock_path)
    if ref_ip.get("lock_sha256") != lock_sha:
        raise ValueError("Sealed p50 continuation lock_sha256 does not match lock.json")
    lock_obj = json.loads(lock_path.read_text(encoding="utf-8"))

    manifest_path = diaz_dir / "manifest.json"
    manifest_sha = _file_sha256(manifest_path)
    if lock_obj.get("manifest_sha256") != manifest_sha:
        raise ValueError("Sealed p50 lock.json manifest_sha256 does not match manifest.json")
    manifest_obj = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest_obj["cases"]["p50"]["instance_sha256"] != profile["instance_sha256"]:
        raise ValueError("Sealed manifest.json p50 instance_sha256 does not match loaded p50")

    # Follow prior_sha256 -> p50_separated.json -> same instance_sha256.
    prior_path = diaz_dir / "p50_separated.json"
    prior_sha = _file_sha256(prior_path)
    if ref_ip.get("prior_sha256") != prior_sha:
        raise ValueError("Sealed p50 continuation prior_sha256 does not match p50_separated.json")
    prior_obj = json.loads(prior_path.read_text(encoding="utf-8"))
    if prior_obj.get("instance_sha256") != profile["instance_sha256"]:
        raise ValueError("Sealed p50_separated.json instance_sha256 does not match loaded p50")

    if ref_ip.get("global_optimum_certified") is not True:
        raise ValueError("Sealed p50 IP reference does not assert global_optimum_certified == true")
    z_ref_ip = Fraction(ref_ip["global_upper"])
    if z_ref_ip != Fraction(ref_ip["global_lower"]):
        raise ValueError("Sealed p50 IP reference does not have equal exact global_lower and global_upper")

    u_ref_lp: Fraction | None = None
    if ref_lp_path.exists():
        ref_lp = json.loads(ref_lp_path.read_text(encoding="utf-8"))
        cert_obj = ref_lp.get("certificate")
        if isinstance(cert_obj, dict) and cert_obj.get("upper") is not None:
            u_ref_lp = Fraction(cert_obj["upper"])

    # 1. Exact neutral repricing of each DISTINCT final binary layout once under equal post-run cap.
    arms = raw["arms"]
    for name in ALL_ARMS:
        if name not in arms:
            raise ValueError(f"Missing required arm in raw JSON: {name}")

    distinct_repricing: dict[str, dict] = {}
    for arm_name in ALL_ARMS:
        rec = arms[arm_name]
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
                "note": "Exact 200-scenario repricing incomplete within post-processing cap; falling back to auxiliary grid-repaired upper bound (cannot qualify for exact zero incumbent gap).",
            }

    # Also exact-reprice the shared cold seed ONCE post-run so we can tell truthfully if the cold seed itself was optimal.
    seed_info = raw["shared_cold_seed"]
    seed_bits = seed_info["bits"]
    if seed_bits in distinct_repricing:
        seed_reprice = {**distinct_repricing[seed_bits], "reused_from_final_layout_repricing": True}
    else:
        seed_layout = tuple(int(i) for i in seed_info["open_real_sites"]) + (dummy_idx,)
        t_srep = perf_counter()
        swit = liu_solve.verify(data, seed_layout, t_srep + float(args.reprice_seconds_per_layout))
        srep_elapsed = perf_counter() - t_srep
        if swit is not None and int(swit["exact_scenarios"]) == int(data.scenario_count):
            sobj = Fraction(swit["objective"])
            seed_reprice = {
                "bits": seed_bits,
                "layout_with_dummy": list(seed_layout),
                "exact_repricing_complete": True,
                "exact_scenarios": int(swit["exact_scenarios"]),
                "exact_original_objective": str(sobj),
                "exact_original_objective_float": float(sobj),
                "witness_sha256": swit["witness_sha256"],
                "reprice_seconds": float(srep_elapsed),
                "reused_from_final_layout_repricing": False,
            }
        else:
            seed_reprice = {
                "bits": seed_bits,
                "layout_with_dummy": list(seed_layout),
                "exact_repricing_complete": False,
                "exact_scenarios": None if swit is None else int(swit["exact_scenarios"]),
                "exact_original_objective": None,
                "exact_original_objective_float": None,
                "witness_sha256": None,
                "reprice_seconds": float(srep_elapsed),
                "reused_from_final_layout_repricing": False,
            }
    cold_seed_already_optimal = bool(
        seed_reprice["exact_repricing_complete"] and Fraction(seed_reprice["exact_original_objective"]) == z_ref_ip
    )

    # 2. Per-arm post-run scoring & validity/numerical integrity checks.
    per_arm: dict[str, dict] = {}
    all_valid = True
    for arm_name in ALL_ARMS:
        rec = arms[arm_name]
        bits = rec["final_binary_layout"]["bits"]
        rep = distinct_repricing[bits]
        u_grid = Fraction(rec["grid_primal_fallback"]["grid_repaired_original_upper"])
        l_cert_lp = Fraction(rec["exact_cut_lp_lower"]["exact_certified_cut_lp_lower"])
        numeric_bb = rec["gscip_stats"]["numeric_mip_dual_bound_diagnostic_not_exact_proof"]
        cb_stats = rec["callback_stats"]

        exact_complete = bool(rep["exact_repricing_complete"])
        u_eval = Fraction(rep["exact_original_objective"]) if exact_complete else u_grid
        inc_source = (
            "exact_200_scenario_liu_verify"
            if exact_complete
            else "grid_repaired_fallback_incomplete_exact_repricing"
        )

        ref_gap = (u_eval - z_ref_ip) / z_ref_ip
        exact_zero_gap_qualified = bool(exact_complete and u_eval == z_ref_ip)
        sound_inc_ge_opt = bool(u_eval >= z_ref_ip)
        sound_grid_ge_exact = bool((not exact_complete) or (u_grid >= u_eval))
        sound_lp_le_inc = bool(l_cert_lp <= u_eval)
        sound_lp_le_ref_lp = True if u_ref_lp is None else bool(l_cert_lp <= u_ref_lp)
        num_integrity_ok = bool(
            int(cb_stats["large_integrality_deviation_calls"]) == 0
            and float(cb_stats["max_unseparated_material_discrepancy"]) <= 1e-4
        )
        seed_matched = bool(rec["initial_seed_identity"]["matches_shared_cold_seed"])

        valid = bool(
            rec["solve_calls"] == 1
            and rec["final_binary_layout"]["is_binary_opening"]
            and seed_matched
            and sound_inc_ge_opt
            and sound_grid_ge_exact
            and sound_lp_le_inc
            and sound_lp_le_ref_lp
            and num_integrity_ok
        )
        if not valid:
            all_valid = False

        numeric_mip_gap_against_eval = (
            (float(u_eval) - numeric_bb) / float(u_eval) if numeric_bb is not None else None
        )

        per_arm[arm_name] = {
            "valid": valid,
            "seed_matched": seed_matched,
            "numerical_integrity_ok": num_integrity_ok,
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
            "sound_cut_lp_le_incumbent": sound_lp_le_inc,
            "sound_cut_lp_le_sealed_lp_upper": sound_lp_le_ref_lp,
            "termination": rec["termination"],
            "unique_binary_layouts_evaluated": int(
                cb_stats["total_unique_binary_layouts_evaluated_including_seed"]
            ),
            "before_certification_seconds": float(rec["timing_seconds"]["before_certification"]),
            "worker_total_certification_seconds": float(rec["timing_seconds"]["worker_total_certification"]),
            "observed_sampled_hinge_activity": rec["observed_sampled_hinge_activity"],
            "discrepancy_summary": {
                "max_integrality_deviation": cb_stats["max_integrality_deviation"],
                "large_integrality_deviation_calls": cb_stats["large_integrality_deviation_calls"],
                "unseparated_material_discrepancy_calls": cb_stats["unseparated_material_discrepancy_calls"],
                "max_unseparated_material_discrepancy": cb_stats["max_unseparated_material_discrepancy"],
                "max_unseparated_sum_discrepancy": cb_stats["max_unseparated_sum_discrepancy"],
                "max_subproblem_duality_err": cb_stats["max_subproblem_duality_err"],
                "max_pointwise_identity_diff": cb_stats["max_pointwise_identity_diff"],
            },
        }

    # 3. Pre-specified 4-arm gate (strictly separating Branch 1 antecedent from Branch 2 rules).
    all_exact_repricing_complete = all(per_arm[name]["exact_repricing_complete"] for name in ALL_ARMS)
    all_four_tie_exact_opt = all(per_arm[name]["qualifies_exact_zero_incumbent_gap"] for name in ALL_ARMS)

    if not all_valid:
        gate = {
            "branch": "invalid_or_numerically_suspect_arm",
            "verdict": "inconclusive_invalid_or_suspect_arm",
            "passed_p50_attribution_gate": False,
        }
    elif not all_exact_repricing_complete:
        gate = {
            "branch": "incomplete_exact_repricing",
            "verdict": "inconclusive_incomplete_exact_repricing",
            "passed_p50_attribution_gate": False,
            "note": "Exact 200-scenario original-price repricing did not complete for all 4 arms; auxiliary grid-repaired uppers are retained for feasibility only.",
        }
    else:
        opt_flags = {
            name: bool(
                per_arm[name]["termination"]["reached_numeric_optimal_diagnostic"]
                and per_arm[name]["qualifies_exact_zero_incumbent_gap"]
            )
            for name in ALL_ARMS
        }
        sweeps = {name: per_arm[name]["unique_binary_layouts_evaluated"] for name in ALL_ARMS}
        secs = {name: per_arm[name]["before_certification_seconds"] for name in ALL_ARMS}
        sw_b = sweeps[CAND_ARM]
        t_b = secs[CAND_ARM]
        any_orig_opt = any(opt_flags[name] for name in ORIG_ARMS)

        if opt_flags[CAND_ARM] and any_orig_opt:
            # Branch 1: qualifying-optimality antecedent holds. Compare B against ALL THREE original arms.
            meets_sw = {
                name: bool((sweeps[name] - sw_b >= 5) and (sw_b * 4 <= sweeps[name] * 3))
                for name in ORIG_ARMS
            }
            meets_t = {name: bool(t_b <= 0.80 * secs[name]) for name in ORIG_ARMS}
            all_sw_pass = all(meets_sw.values())
            all_t_pass = all(meets_t.values())
            passed = bool(all_sw_pass and all_t_pass)
            a3_blocked = not (meets_sw["orig_single_hinge_floor"] and meets_t["orig_single_hinge_floor"])
            gate = {
                "branch": "branch_1_qualifying_optimality_antecedent_holds",
                "opt_flags_numeric_plus_exact_zero_gap": opt_flags,
                "cold_seed_already_optimal": cold_seed_already_optimal,
                "all_four_tie_exact_optimum": all_four_tie_exact_opt,
                "sweeps": sweeps,
                "seconds": secs,
                "meets_sweep_reduction_vs_orig": meets_sw,
                "meets_time_reduction_vs_orig": meets_t,
                "a3_control_blocked_separation_attribution_on_p50": a3_blocked,
                "passed_p50_attribution_gate": passed,
                "verdict": "pass_p50_4arm_attribution" if passed else "close_separation_superiority_on_p50",
            }
        else:
            # Branch 2: qualifying-optimality antecedent does NOT hold (timeout / mixed / incomplete).
            gaps = {name: per_arm[name]["numeric_mip_gap_diagnostic"] for name in ALL_ARMS}
            u_map = {name: Fraction(per_arm[name]["evaluated_incumbent_objective"]) for name in ALL_ARMS}
            g_b = gaps[CAND_ARM]
            u_b = u_map[CAND_ARM]
            min_orig_u = min(u_map[name] for name in ORIG_ARMS)

            orig_all_incomplete_bad = all(
                (not opt_flags[name])
                and (
                    (not per_arm[name]["qualifies_exact_zero_incumbent_gap"])
                    or (gaps[name] is None or gaps[name] >= 0.0025)
                )
                for name in ORIG_ARMS
            )
            cond_2a = bool(opt_flags[CAND_ARM] and orig_all_incomplete_bad)

            all_gaps_present = all(gaps[name] is not None for name in ALL_ARMS)
            min_orig_gap = min(gaps[name] for name in ORIG_ARMS) if all_gaps_present else None
            gap_beats_all_orig_by_25bp = bool(
                all_gaps_present and g_b is not None and min_orig_gap is not None and (min_orig_gap - g_b >= 0.0025)
            )
            cond_2b = bool((min_orig_u - u_b) * 1000 >= z_ref_ip and gap_beats_all_orig_by_25bp)
            cond_2c_tie = bool(
                all_four_tie_exact_opt
                and (not any(opt_flags.values()))
                and gap_beats_all_orig_by_25bp
                and all(sw_b <= sweeps[name] for name in ORIG_ARMS)
            )
            passed = bool(cond_2a or cond_2b or cond_2c_tie)

            if passed:
                verdict = "pass_p50_4arm_attribution"
            elif all_gaps_present and g_b is not None and (
                (gaps["orig_single_hinge_floor"] <= g_b) or (gaps["orig_multi_floor"] <= g_b)
            ):
                verdict = "close_separation_superiority_on_p50"
            elif all_four_tie_exact_opt and (not any(opt_flags.values())):
                verdict = "inconclusive_non_separating_exact_tie_at_cap"
            else:
                verdict = "close_separation_superiority_on_p50"

            gate = {
                "branch": "branch_2_timeout_or_mixed_numeric_diagnostics",
                "opt_flags_numeric_plus_exact_zero_gap": opt_flags,
                "cold_seed_already_optimal": cold_seed_already_optimal,
                "all_four_tie_exact_optimum": all_four_tie_exact_opt,
                "numeric_mip_gaps_diagnostic": gaps,
                "cond_2a_sep_numeric_optimal_while_all_orig_incomplete": cond_2a,
                "cond_2b_sep_exact_incumbent_and_numeric_gap_dominance": cond_2b,
                "cond_2c_exact_tie_timeout_numeric_gap_dominance": cond_2c_tie,
                "sweeps": sweeps,
                "seconds": secs,
                "passed_p50_attribution_gate": passed,
                "verdict": verdict,
            }

    out_payload = {
        "evaluator": "post_run_p50_4arm_integer_evaluator",
        "note": (
            "Executed strictly after cold worker termination. Independently reprices distinct final binary "
            "layouts on all 200 original scenarios via frozen experiments/liu_lost_sales/solve.py:verify. "
            "All GSCIP termination statuses, dual bounds, and MIP gaps are numeric floating-point diagnostics "
            "and not exact rational global proofs. Smoke runs carry zero scientific gate decision."
        ),
        "raw_worker_json": str(args.raw_json),
        "raw_worker_sha256": _file_sha256(args.raw_json),
        "evaluator_sha256": _file_sha256(Path(__file__).resolve()),
        "reused_verifier_file": str(LIU_DIR / "solve.py"),
        "reused_verifier_sha256": _file_sha256(LIU_DIR / "solve.py"),
        "sealed_ip_reference_file": str(ref_ip_path),
        "sealed_ip_reference_sha256": observed_ref_sha,
        "sealed_ip_reference_provenance": {
            "lock_file": str(lock_path),
            "lock_sha256": lock_sha,
            "manifest_file": str(manifest_path),
            "manifest_sha256": manifest_sha,
            "prior_file": str(prior_path),
            "prior_sha256": prior_sha,
            "instance_sha256": profile["instance_sha256"],
            "global_optimum_certified": True,
        },
        "sealed_p50_exact_ip_optimum": str(z_ref_ip),
        "sealed_p50_exact_ip_optimum_float": float(z_ref_ip),
        "sealed_p50_lp_upper": None if u_ref_lp is None else str(u_ref_lp),
        "reprice_seconds_cap_per_layout": float(args.reprice_seconds_per_layout),
        "cold_seed_post_run_repricing": seed_reprice,
        "cold_seed_already_optimal": cold_seed_already_optimal,
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

    for arm_name in ALL_ARMS:
        p = per_arm[arm_name]
        print(
            f"[p50 post-run | {arm_name}] valid={p['valid']} exact_reprice={p['exact_repricing_complete']} "
            f"U={p['evaluated_incumbent_objective_float']:.6f} ref_gap={p['post_run_exact_reference_incumbent_gap_float']:.3e} "
            f"zero_gap={p['qualifies_exact_zero_incumbent_gap']} sweeps={p['unique_binary_layouts_evaluated']} "
            f"term={p['termination']['reason']}/{p['termination']['limit']}"
        )
    print(f"[p50 post-run | cold_seed_already_optimal={cold_seed_already_optimal}] gate={gate['verdict']} passed={gate['passed_p50_attribution_gate']}")
    print(f"Wrote post-run evaluation JSON: {args.out}")


if __name__ == "__main__":
    main()
