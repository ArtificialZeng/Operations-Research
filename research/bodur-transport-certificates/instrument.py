"""Frozen instrumentation extracted from the measured official run harness."""

from hashlib import sha256
from pathlib import Path

BASE = Path(__file__).resolve().with_name("base_solver.py")
BASE_SHA = "58152d18d16e7a5904ea7926bb74e5e51b76852c7813cab2870fc05bc6e5e5a5"


def integrated_source():
    raw = BASE.read_bytes()
    if sha256(raw).hexdigest() != BASE_SHA:
        raise ValueError("Frozen warm-start solver changed")
    source = raw.decode().replace("\r\n", "\n")

    def insert(old, new):
        nonlocal source
        if source.count(old) != 1:
            raise ValueError(f"Could not locate integration seam: {old}")
        source = source.replace(old, new)

    insert('initializer="all-open", trace=None) -> dict:',
           'initializer="all-open", trace=None, exact_transport=None) -> dict:')
    insert('    trace["master_solves"] = 0', '''    trace["master_solves"] = 0
    trace["binary_recourse_seconds"] = 0.0
    trace["binary_lp_calls"] = 0
    trace["fractional_lp_calls"] = 0
    trace["certified_scenarios"] = 0''')
    insert('        trace["recourse_sweeps"] += 1', '''        trace["recourse_sweeps"] += 1
        sweep_started = time.perf_counter()
        binary = bool(np.all((x_vec == 0) | (x_vec == 1)))
        lp_counter = "binary_lp_calls" if binary else "fractional_lp_calls"
        if exact_transport is not None:
            exact_transport.begin(x_vec)''')
    insert('            lk = lam[k]\n            for j in range(J):', '''            lk = lam[k]
            certified = exact_transport.try_scenario(k, extract_flows) if binary and exact_transport is not None else None
            if certified is not None:
                value, intercept, slopes, witness = certified
                group = scen_to_g[k]
                exp_trans += probs[k] * value
                c0[group] += intercept
                coeff[group] += slopes
                trace["certified_scenarios"] += 1
                if extract_flows:
                    flows[str(int(k))] = witness
                continue
            for j in range(J):''')
    insert('            st = sub.Solve()\n            if st != pywraplp.Solver.OPTIMAL:\n                return None, None, None, None', '''            trace[lp_counter] += 1
            st = sub.Solve()
            if st != pywraplp.Solver.OPTIMAL:
                if binary:
                    trace["binary_recourse_seconds"] += time.perf_counter() - sweep_started
                return None, None, None, None''')
    insert('            g = scen_to_g[k]\n            c0[g]', '''            if binary and exact_transport is not None:
                exact_transport.learn(alpha, beta, y_vars)
            g = scen_to_g[k]
            c0[g]''')
    insert('        return exp_trans, c0, coeff, flows', '''        if binary:
            trace["binary_recourse_seconds"] += time.perf_counter() - sweep_started
        factor = 64 * np.finfo(float).eps * (K + 1)
        return exp_trans, c0 * (1 - factor), coeff * (1 + factor), flows''')
    insert('    exact_obj = recompute_objective_from_sparse(best_x, flows, f_cost, probs, q)',
           '''    exact_obj = recompute_objective_from_sparse(best_x, flows, f_cost, probs, q)
    trace["internal_numerical_lower_bound"] = best_lb
    trace["witness_objective"] = exact_obj''')
    compile(source, "solver_core.py", "exec")
    return source


ENTRY = '''import argparse
import json
from pathlib import Path
from time import perf_counter

from solver_core import solve


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", choices=("bodur2017",), required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-limit", type=int, default=60)
    args = parser.parse_args()
    raw = args.instance.read_bytes()
    instance = json.loads(raw)
    trace = {"oracle": __ARM__}
    tree = None
    if __ARM__ != "clp":
        from decimal import Decimal
        from official_tree import ExactRecourse
        exact = json.loads(raw, parse_float=Decimal)
        if __ARM__ == "tree-pivot":
            from tree_pivot import RepairingRecourse
            tree = RepairingRecourse(exact)
        else:
            tree = ExactRecourse(exact)
    witness = solve(instance, args.time_limit, t_entry=started, initializer="expected-demand",
                    trace=trace, exact_transport=tree)
    args.output.write_text(json.dumps(witness, allow_nan=False, separators=(",", ":")) + "\\n")
    if __ARM__ == "tree-pivot":
        trace.update(tree.telemetry)
    trace["end_to_end_seconds_after_import"] = perf_counter() - started
    print("BODUR_TRACE " + json.dumps(trace, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
'''

