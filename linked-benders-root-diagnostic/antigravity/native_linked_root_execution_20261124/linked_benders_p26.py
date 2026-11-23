"""Bounded Diaz p26 paired multi-cut linked Benders stress check wrapper.

Reuses the frozen generic routines from `linked_benders_pilot.py` and the
read-only sealed loader `experiments/linked_root/run_root.py:load_case("p26")`
without modifying `linked_benders_pilot.py`, any `p01` output, or any frozen
input. Evaluates only the paired `multi`-cut regime (`linked` vs.
`linked_separated`) under equal cold caps (30 s/arm, 60 candidates/arm,
1e-6 relative gap target) and omits secondary fixed-history trajectory pricing.
"""

from __future__ import annotations

import os

for _env_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_env_var, "1")

import argparse
from fractions import Fraction
from importlib.metadata import version
import json
from pathlib import Path
import sys
from time import perf_counter

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
LINKED_ROOT_DIR = REPO_ROOT / "experiments" / "linked_root"
for _path in (str(HERE), str(LINKED_ROOT_DIR)):
    if _path not in sys.path:
        sys.path.insert(0, _path)

from linked_benders_pilot import (
    _file_sha256,
    build_arm_context,
    compare_paths,
    load_reference_interval,
    run_benders_arm,
)
from run_root import load_case


def evaluate_preregistered_gate(rec_orig: dict, rec_sep: dict, rel_tol: float) -> dict:
    """Evaluate the pre-registered p26 multi-cut decision rule using exact Fractions."""
    v_o = rec_orig["verification"]
    v_s = rec_sep["verification"]
    c_o = rec_orig["certificate"]
    c_s = rec_sep["certificate"]

    comparable = (
        c_o is not None
        and c_s is not None
        and v_o is not None
        and v_s is not None
        and bool(v_o["sound_lower_le_upper"])
        and bool(v_s["sound_lower_le_upper"])
        and bool(v_o["overlaps_sealed_reference"])
        and bool(v_s["overlaps_sealed_reference"])
    )
    if not comparable:
        return {
            "certificates_comparable": False,
            "verdict": "inconclusive_certificate_failure",
            "motivates_later_replication": False,
            "note": "A missing, unsound, or non-overlapping certificate is inconclusive and cannot justify a speed or bound claim.",
        }

    g_orig = Fraction(c_o["relative_gap"])
    g_sep = Fraction(c_s["relative_gap"])
    tol_frac = Fraction(str(rel_tol))

    orig_cert_target_met = bool(g_orig <= tol_frac)
    sep_cert_target_met = bool(g_sep <= tol_frac)
    orig_stop_converged = bool(rec_orig["stop_reason"] == "converged_rel_tol")
    sep_stop_converged = bool(rec_sep["stop_reason"] == "converged_rel_tol")
    both_reached_target = bool(
        orig_cert_target_met and sep_cert_target_met and orig_stop_converged and sep_stop_converged
    )

    sweeps_orig = int(rec_orig["candidate_evaluations"])
    sweeps_sep = int(rec_sep["candidate_evaluations"])
    sweeps_saved_by_sep = sweeps_orig - sweeps_sep

    abs_gap_reduction = g_orig - g_sep
    rel_gap_reduction = (abs_gap_reduction / g_orig) if g_orig > 0 else Fraction(0)
    meets_20pct = bool(g_orig > 0 and abs_gap_reduction * 5 >= g_orig)
    meets_abs_1e4 = bool(abs_gap_reduction >= Fraction(1, 10000))

    if both_reached_target:
        motivates = bool(sweeps_saved_by_sep >= 2)
        branch = "both_reached_certified_target"
        verdict = "motivate_later_replication_sweeps" if motivates else "close_fractional_root_scale_line"
    else:
        motivates = bool(meets_20pct and meets_abs_1e4)
        branch = "not_both_reached_certified_target"
        verdict = "motivate_later_replication_gap" if motivates else "close_fractional_root_scale_line"

    return {
        "certificates_comparable": True,
        "decision_branch": branch,
        "orig_certified_rel_gap": str(g_orig),
        "sep_certified_rel_gap": str(g_sep),
        "orig_certified_rel_gap_float": float(g_orig),
        "sep_certified_rel_gap_float": float(g_sep),
        "orig_certified_target_met": orig_cert_target_met,
        "sep_certified_target_met": sep_cert_target_met,
        "orig_stop_converged": orig_stop_converged,
        "sep_stop_converged": sep_stop_converged,
        "both_reached_certified_target": both_reached_target,
        "orig_completed_sweeps": sweeps_orig,
        "sep_completed_sweeps": sweeps_sep,
        "sweeps_saved_by_separated": sweeps_saved_by_sep,
        "abs_rel_gap_reduction": str(abs_gap_reduction),
        "abs_rel_gap_reduction_float": float(abs_gap_reduction),
        "rel_gap_reduction_fraction_float": float(rel_gap_reduction),
        "meets_20pct_gap_reduction": meets_20pct,
        "meets_0p0001_abs_gap_reduction": meets_abs_1e4,
        "motivates_later_replication": motivates,
        "verdict": verdict,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-iters", type=int, default=60)
    parser.add_argument("--time-limit", type=float, default=30.0, help="Per-arm wall-clock cap in seconds.")
    parser.add_argument("--rel-tol", type=float, default=1e-6)
    parser.add_argument("--cut-tol", type=float, default=1e-7)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    t_global = perf_counter()
    data, profile = load_case("p26")
    ref_info = load_reference_interval("p26", profile["instance_sha256"])
    ref_lower = Fraction(ref_info["intersection_lower"])
    ref_upper = Fraction(ref_info["intersection_upper"])

    ctx_orig = build_arm_context(data, "linked")
    ctx_sep = build_arm_context(data, "linked_separated")

    rec_orig, vis_orig = run_benders_arm(
        data,
        ctx_orig,
        "multi",
        max_iters=args.max_iters,
        time_limit=args.time_limit,
        rel_tol=args.rel_tol,
        cut_tol=args.cut_tol,
        ref_lower=ref_lower,
        ref_upper=ref_upper,
    )
    rec_sep, vis_sep = run_benders_arm(
        data,
        ctx_sep,
        "multi",
        max_iters=args.max_iters,
        time_limit=args.time_limit,
        rel_tol=args.rel_tol,
        cut_tol=args.cut_tol,
        ref_lower=ref_lower,
        ref_upper=ref_upper,
    )

    path_cmp = compare_paths(vis_orig, vis_sep)
    gate = evaluate_preregistered_gate(rec_orig, rec_sep, args.rel_tol)

    all_sound = all(
        rec["verification"] is not None and bool(rec["verification"]["sound_lower_le_upper"])
        for rec in (rec_orig, rec_sep)
    )
    all_overlap_ref = all(
        rec["verification"] is not None and bool(rec["verification"]["overlaps_sealed_reference"])
        for rec in (rec_orig, rec_sep)
    )

    for label, rec, extra in (
        ("linked", rec_orig, ""),
        ("linked_separated", rec_sep, f" | paths_distinct={path_cmp['paths_distinct']}"),
    ):
        ver = rec["verification"]
        if ver is not None:
            print(
                f"[p26 | cut_mode=multi] "
                f"{label}: sweeps={rec['candidate_evaluations']} stop={rec['stop_reason']} "
                f"L={ver['certified_lower_float']:.6f} U={ver['certified_upper_float']:.6f} "
                f"gap={ver['certified_relative_gap_float']:.3e} t={rec['timing_seconds']['before_certificate']:.3f}s "
                f"ref_ok={ver['overlaps_sealed_reference']}{extra}"
            )
        else:
            print(
                f"[p26 | cut_mode=multi] "
                f"{label}: sweeps={rec['candidate_evaluations']} stop={rec['stop_reason']} "
                f"no_certificate t={rec['timing_seconds']['before_certificate']:.3f}s{extra}"
            )
    print(f"[p26 | gate] verdict={gate['verdict']} motivates_later_replication={gate['motivates_later_replication']}")

    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    pilot_mod_path = HERE / "linked_benders_pilot.py"
    payload = {
        "pilot": "paired_iterative_linked_benders_root_p26_multicut",
        "case": "p26",
        "cut_mode": "multi",
        "secondary_fixed_history_omitted": True,
        "bound_scope_warning": (
            "All upper bounds reported here evaluate continuous fractional openings x in [0, 1]^20 "
            "and are NOT integer feasible incumbents unless verification.bound_classification.is_binary_opening is true. "
            "Single-run wall-clock timing is descriptive only."
        ),
        "input_profile": profile,
        "sealed_reference_interval": ref_info,
        "config": {
            "cut_mode": "multi",
            "max_iters_per_arm": args.max_iters,
            "time_limit_seconds_per_arm": args.time_limit,
            "rel_tol": args.rel_tol,
            "cut_tol": args.cut_tol,
            "threads": 1,
            "cold_start": True,
            "initial_benders_cuts": 0,
            "scenario_cuts_per_full_sweep": int(ctx_orig.scenarios),
        },
        "runtime": {
            "python": sys.version,
            "executable": sys.executable,
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "cpu_affinity": affinity,
            "wrapper_sha256": _file_sha256(Path(__file__).resolve()),
            "pilot_module_sha256": _file_sha256(pilot_mod_path),
        },
        "overall_verification": {
            "all_certificates_sound": all_sound,
            "all_certificates_overlap_sealed_reference": all_overlap_ref,
        },
        "preregistered_gate": gate,
        "paired_run": {
            "linked": rec_orig,
            "linked_separated": rec_sep,
            "separate_path_check": path_cmp,
        },
        "total_wall_seconds": float(perf_counter() - t_global),
    }

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, allow_nan=False)
            fh.write("\n")
        print(f"Wrote p26 multi-cut result JSON: {args.out}")
    else:
        print(json.dumps(payload["preregistered_gate"], indent=2))


if __name__ == "__main__":
    main()
