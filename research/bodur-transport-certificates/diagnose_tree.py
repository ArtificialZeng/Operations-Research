"""Measure why exact transport certificates miss on the public tiny case."""

import argparse
from collections import Counter
from decimal import Decimal
import inspect
import json
from pathlib import Path
import sys

from official_tree import ExactRecourse
from instrument import integrated_source
from replay import fetch_input
from tree_pivot import pivot_once


class Instrumented(ExactRecourse):
    def __init__(self, instance, repair, depth_probe):
        super().__init__(instance)
        self.events = Counter()
        self.repair = repair
        self.depth_probe = depth_probe

    def learn(self, alpha, beta, y_vars):
        if not self.layout or self.attempts >= 16:
            return
        return_line = None

        def monitor(frame, event, arg):
            nonlocal return_line
            if frame.f_code is not ExactRecourse.learn.__code__:
                return None
            if event == "return":
                return_line = frame.f_lineno
            return monitor

        old_trace = sys.gettrace()
        sys.settrace(monitor)
        try:
            super().learn(alpha, beta, y_vars)
        finally:
            sys.settrace(old_trace)
        if self.tree is not None:
            self.events["learned_tree"] += 1
        elif return_line is not None:
            lines, start = inspect.getsourcelines(ExactRecourse.learn)
            reason = lines[return_line - start - 1].strip()
            self.events[f"learning_stop_line_{return_line}"] += 1
            self.events[f"condition: {reason}"] += 1

    def try_scenario(self, index, extract_flows):
        tree = self.tree
        result = super().try_scenario(index, extract_flows)
        if tree is None or result is not None:
            return result
        self.events["infeasible_rhs"] += 1
        if self.depth_probe:
            self.count_pivots(tree, self.demands[index])
        if not self.repair:
            return None
        self.tree = pivot_once(tree, self.demands[index], self.costs, self.capacities)
        if self.tree is None:
            self.events["pivot_rejected"] += 1
            return None
        result = super().try_scenario(index, extract_flows)
        self.events["pivot_success" if result is not None else "pivot_still_infeasible"] += 1
        return result

    def count_pivots(self, tree, demand):
        seen = {frozenset((i, j) for _, _, i, j in tree.rooted_edges)}
        for depth in range(1, self.depth_probe + 1):
            tree = pivot_once(tree, demand, self.costs, self.capacities)
            if tree is None:
                self.events["depth_probe_rejected"] += 1
                return
            signature = frozenset((i, j) for _, _, i, j in tree.rooted_edges)
            if signature in seen:
                self.events["depth_probe_cycle"] += 1
                return
            if tree.evaluate(demand, False) is not None:
                self.events[f"feasible_after_{depth}_pivots"] += 1
                return
            seen.add(signature)
        self.events["depth_probe_exhausted"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cache", type=Path, default=Path(".bodur-inputs"))
    parser.add_argument("--depth-probe", type=int, choices=(0, 8), default=0)
    args = parser.parse_args()
    source = integrated_source()
    namespace = {"__name__": "bodur_diagnostic"}
    exec(compile(source, "solver_core.py", "exec"), namespace)
    raw = fetch_input("tiny", args.cache).read_bytes()
    data = json.loads(raw)
    exact = json.loads(raw, parse_float=Decimal)
    report = {}
    for repair in ((False,) if args.depth_probe else (False, True)):
        instrumented = Instrumented(exact, repair, args.depth_probe)
        trace = {}
        witness = namespace["solve"](data, 15, initializer="expected-demand", trace=trace, exact_transport=instrumented)
        report["one_pivot" if repair else "no_repair"] = {"diagnostic_counts": dict(instrumented.events),
            "trace": trace, "objective": witness["objective_value"]}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, allow_nan=False, indent=2)
        stream.write("\n")
    print(json.dumps({arm: row["diagnostic_counts"] for arm, row in report.items()}))


if __name__ == "__main__":
    main()
