"""Empirical capability probe for single-tree lazy integer Benders callbacks.

Tests installed, authorized open-source local solver APIs on tiny 2-binary-variable
toy MIPs requiring sequential lazy optimality cuts inside ONE single branch-and-bound
solve call (no outer MIP restarts). Does not run any benchmark instance.
"""

from __future__ import annotations

from datetime import timedelta
import importlib
import importlib.metadata
import inspect
import json
from pathlib import Path
import subprocess
import sys


def _pkg_version(name: str) -> str | None:
    try:
        return importlib.metadata.version(name)
    except Exception:
        try:
            mod = importlib.import_module(name)
            return str(getattr(mod, "__version__", "installed_unknown_version"))
        except Exception:
            return None


def probe_ortools_math_opt() -> dict:
    """Test ortools.math_opt single-tree lazy callbacks (single-cut, multi-cut, and SciPy LP inside cb)."""
    out: dict = {"available": False, "backends": {}}
    try:
        from ortools.math_opt.python import mathopt
    except Exception as exc:
        out["import_error"] = repr(exc)
        return out

    out["available"] = True
    out["solve_signature"] = str(inspect.signature(mathopt.solve))
    event_enum = getattr(mathopt, "Event", None) or getattr(mathopt, "CallbackEvent", None)
    out["event_enum_name"] = event_enum.__name__ if event_enum is not None else None
    out["callback_events"] = [e.name for e in event_enum] if event_enum is not None else []
    out["callback_result_methods"] = [a for a in dir(mathopt.CallbackResult) if not a.startswith("_")]
    out["callback_reg_fields"] = [a for a in dir(mathopt.CallbackRegistration) if not a.startswith("_")]
    out["solver_types"] = [s.name for s in mathopt.SolverType]

    solve_params = inspect.signature(mathopt.solve).parameters
    reg_kw = "callback_reg" if "callback_reg" in solve_params else "cb_reg"
    cb_kw = "cb" if "cb" in solve_params else "callback"
    mip_sol_event = getattr(event_enum, "MIP_SOLUTION")

    candidate_solvers = [
        name
        for name in ("GSCIP", "HIGHS", "GLPK", "CP_SAT")
        if hasattr(mathopt.SolverType, name)
    ]

    for sname in candidate_solvers:
        stype = getattr(mathopt.SolverType, sname)
        entry: dict = {"solver_type": sname, "single_tree_lazy_supported": False}
        try:
            model = mathopt.Model(name=f"toy_lazy_{sname}")
            x1 = model.add_binary_variable(name="x1")
            x2 = model.add_binary_variable(name="x2")
            theta = model.add_variable(lb=0.0, ub=100.0, name="theta")
            model.minimize(3.0 * x1 + 3.0 * x2 + theta)

            cb_calls = 0
            cuts_added = 0
            trace = []

            def cb(cb_data: mathopt.CallbackData) -> mathopt.CallbackResult:
                nonlocal cb_calls, cuts_added
                cb_calls += 1
                res = mathopt.CallbackResult()
                sol = cb_data.solution
                v1, v2, vt = float(sol[x1]), float(sol[x2]), float(sol[theta])
                added_here = None
                if vt + 1e-6 < 10.0 - 10.0 * v1:
                    res.add_lazy_constraint(theta + 10.0 * x1 >= 10.0)
                    cuts_added += 1
                    added_here = "theta + 10*x1 >= 10"
                elif vt + 1e-6 < 10.0 - 10.0 * v2:
                    res.add_lazy_constraint(theta + 10.0 * x2 >= 10.0)
                    cuts_added += 1
                    added_here = "theta + 10*x2 >= 10"
                trace.append({"call": cb_calls, "x1": v1, "x2": v2, "theta": vt, "cut": added_here})
                return res

            cb_reg = mathopt.CallbackRegistration(
                events={mip_sol_event},
                mip_solution_filter=mathopt.SparseVectorFilter(),
                add_lazy_constraints=True,
            )
            params = mathopt.SolveParameters(threads=1, time_limit=timedelta(seconds=5))
            result = mathopt.solve(model, stype, params=params, **{reg_kw: cb_reg, cb_kw: cb})
            term = result.termination.reason.name
            obj = float(result.objective_value()) if result.has_primal_feasible_solution() else None
            best_bound = float(result.best_objective_bound())
            sol_vals = (
                {
                    "x1": float(result.variable_values(x1)),
                    "x2": float(result.variable_values(x2)),
                    "theta": float(result.variable_values(theta)),
                }
                if result.has_primal_feasible_solution()
                else None
            )
            stats = result.solve_stats
            passed = (
                term == "OPTIMAL"
                and obj is not None
                and abs(obj - 6.0) < 1e-6
                and abs(best_bound - 6.0) < 1e-6
                and sol_vals is not None
                and abs(sol_vals["x1"] - 1.0) < 1e-6
                and abs(sol_vals["x2"] - 1.0) < 1e-6
                and abs(sol_vals["theta"] - 0.0) < 1e-6
                and cuts_added >= 2
            )
            entry.update(
                {
                    "single_tree_lazy_supported": passed,
                    "termination": term,
                    "objective": obj,
                    "best_objective_bound": best_bound,
                    "solution": sol_vals,
                    "callback_calls": cb_calls,
                    "lazy_cuts_added": cuts_added,
                    "solve_calls": 1,
                    "node_count": int(stats.node_count),
                    "simplex_iterations": int(stats.simplex_iterations),
                    "solve_time_seconds": float(stats.solve_time.total_seconds()),
                    "trace": trace,
                }
            )
        except Exception as exc:
            entry["error"] = f"{type(exc).__name__}: {exc}"
        out["backends"][sname] = entry

    # Test GSCIP multi-cut lazy callback + SciPy HiGHS subproblem inside callback.
    if out["backends"].get("GSCIP", {}).get("single_tree_lazy_supported"):
        try:
            import numpy as np
            from scipy.optimize import linprog

            model = mathopt.Model(name="toy_multicut_scipy_GSCIP")
            x1 = model.add_binary_variable(name="x1")
            x2 = model.add_binary_variable(name="x2")
            t1 = model.add_variable(lb=0.0, ub=100.0, name="t1")
            t2 = model.add_variable(lb=0.0, ub=100.0, name="t2")
            model.minimize(3.0 * x1 + 3.0 * x2 + t1 + t2)

            cb_calls = 0
            cuts_added = 0
            lp_solves_in_cb = 0

            def multi_cb(cb_data: mathopt.CallbackData) -> mathopt.CallbackResult:
                nonlocal cb_calls, cuts_added, lp_solves_in_cb
                cb_calls += 1
                res = mathopt.CallbackResult()
                sol = cb_data.solution
                v1, v2 = float(sol[x1]), float(sol[x2])
                vt1, vt2 = float(sol[t1]), float(sol[t2])
                # Solve tiny 2-variable transportation LP via SciPy highs-ds inside callback:
                # Scenario 1: min 0*y_real + 10*y_dummy s.t. y_real + y_dummy = 1, 0 <= y_real <= v1
                # Scenario 2: min 0*y_real + 10*y_dummy s.t. y_real + y_dummy = 1, 0 <= y_real <= v2
                for v_i, x_var, t_var, vt_i in ((v1, x1, t1, vt1), (v2, x2, t2, vt2)):
                    lp = linprog(
                        np.array([0.0, 10.0]),
                        A_eq=np.array([[1.0, 1.0]]),
                        b_eq=np.array([1.0]),
                        bounds=[(0.0, max(0.0, v_i)), (0.0, None)],
                        method="highs-ds",
                        options={"threads": 1},
                    )
                    lp_solves_in_cb += 1
                    q_val = float(lp.fun)
                    if vt_i + 1e-6 < q_val:
                        res.add_lazy_constraint(t_var + 10.0 * x_var >= 10.0)
                        cuts_added += 1
                return res

            cb_reg = mathopt.CallbackRegistration(
                events={mip_sol_event},
                mip_solution_filter=mathopt.SparseVectorFilter(),
                add_lazy_constraints=True,
            )
            result = mathopt.solve(
                model,
                mathopt.SolverType.GSCIP,
                params=mathopt.SolveParameters(threads=1, time_limit=timedelta(seconds=5)),
                **{reg_kw: cb_reg, cb_kw: multi_cb},
            )
            obj = float(result.objective_value())
            bb = float(result.best_objective_bound())
            out["gscip_multicut_with_scipy_lp"] = {
                "passed": result.termination.reason.name == "OPTIMAL"
                and abs(obj - 6.0) < 1e-6
                and abs(bb - 6.0) < 1e-6
                and cuts_added >= 2,
                "termination": result.termination.reason.name,
                "objective": obj,
                "best_objective_bound": bb,
                "callback_calls": cb_calls,
                "lazy_cuts_added": cuts_added,
                "scipy_lp_solves_inside_cb": lp_solves_in_cb,
                "node_count": int(result.solve_stats.node_count),
            }
        except Exception as exc:
            out["gscip_multicut_with_scipy_lp"] = {"passed": False, "error": f"{type(exc).__name__}: {exc}"}

    return out


def probe_highspy_lazy_standalone() -> dict:
    """Test highspy 1.15.1 cbMipDefineLazyConstraints in a clean subprocess (no ortools)."""
    code = r'''
import inspect, json, highspy
h = highspy.Highs()
out = {"available": True, "highs_version": h.version()}
out["cbMipDefineLazyConstraints_type"] = type(h.cbMipDefineLazyConstraints).__name__
out["cbMipDefineLazyConstraints_dir"] = [a for a in dir(h.cbMipDefineLazyConstraints) if not a.startswith("_")]
out["cbMipSolution_dir"] = [a for a in dir(h.cbMipSolution) if not a.startswith("_")]
out["callbacks_dir"] = [a for a in dir(h.callbacks) if not a.startswith("_")]

# Check coexistence with scipy.optimize.linprog
try:
    import numpy as np
    from scipy.optimize import linprog
    lp = linprog([0.0, 10.0], A_eq=[[1.0, 1.0]], b_eq=[1.0], bounds=[(0, 0), (0, None)], method="highs-ds")
    out["coexists_with_scipy"] = (lp.status == 0)
except Exception as exc:
    out["coexists_with_scipy"] = f"ERROR: {exc}"

# Check coexistence with ortools (in same process)
try:
    import ortools
    from ortools.graph.python import min_cost_flow
    out["coexists_with_ortools_after_highspy"] = True
except Exception as exc:
    out["coexists_with_ortools_after_highspy"] = f"ERROR: {exc}"

# Inspect HighsCallbackDataIn / Out via cbMipDefineLazyConstraints event subscription on toy MIP
try:
    h.setOptionValue("output_flag", False)
    h.setOptionValue("threads", 1)
    x1 = h.addBinary(name="x1")
    x2 = h.addBinary(name="x2")
    theta = h.addVariable(lb=0.0, ub=100.0, name="theta")
    h.minimize(3.0 * x1 + 3.0 * x2 + theta)

    cb_events = []
    def on_lazy(e):
        rec = {
            "event_type": type(e).__name__,
            "event_dir": [a for a in dir(e) if not a.startswith("_")],
        }
        if hasattr(e, "data_in"):
            rec["data_in_dir"] = [a for a in dir(e.data_in) if not a.startswith("_")]
        if hasattr(e, "data_out"):
            rec["data_out_dir"] = [a for a in dir(e.data_out) if not a.startswith("_")]
            sol = getattr(e.data_out, "mip_solution", None)
            if sol is not None:
                rec["mip_solution"] = [float(v) for v in sol]
        cb_events.append(rec)

    h.cbMipDefineLazyConstraints.subscribe(on_lazy)
    h.run()
    out["lazy_cb_invocations"] = len(cb_events)
    out["lazy_cb_first_event"] = cb_events[0] if cb_events else None
    out["model_status"] = str(h.getModelStatus())
    out["objective_without_cuts"] = float(h.getObjectiveValue())
except Exception as exc:
    out["lazy_cb_probe_error"] = f"{type(exc).__name__}: {exc}"

print(json.dumps(out))
'''
    proc = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=15)
    if proc.returncode == 0 and proc.stdout.strip():
        lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip().startswith("{")]
        data = json.loads(lines[-1])
        data["version"] = _pkg_version("highspy")
        return data
    return {
        "available": False,
        "version": _pkg_version("highspy"),
        "returncode": proc.returncode,
        "stdout": proc.stdout.strip(),
        "stderr": proc.stderr.strip(),
    }


def main() -> None:
    report = {
        "python": sys.version,
        "executable": sys.executable,
        "installed_versions": {
            pkg: _pkg_version(pkg)
            for pkg in ("numpy", "scipy", "highspy", "ortools", "pyscipopt", "pulp", "pyomo")
        },
        "ortools_math_opt": probe_ortools_math_opt(),
        "highspy_lazy_standalone": probe_highspy_lazy_standalone(),
    }
    out_path = Path(__file__).resolve().parent / "solver_capability_probe.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {out_path}")
    mo = report["ortools_math_opt"]
    for sname, info in mo.get("backends", {}).items():
        print(
            f"  math_opt[{sname}]: supported={info.get('single_tree_lazy_supported')} "
            f"term={info.get('termination')} obj={info.get('objective')} "
            f"nodes={info.get('node_count')} cuts={info.get('lazy_cuts_added')} err={info.get('error')}"
        )
    print("  gscip_multicut_with_scipy_lp:", mo.get("gscip_multicut_with_scipy_lp"))
    hs = report["highspy_lazy_standalone"]
    print("  highspy_lazy_standalone:", json.dumps({k: hs.get(k) for k in ("available", "highs_version", "coexists_with_scipy", "coexists_with_ortools_after_highspy", "lazy_cb_invocations", "lazy_cb_probe_error", "model_status")}))


if __name__ == "__main__":
    main()
