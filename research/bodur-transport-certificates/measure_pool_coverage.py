"""Measure exact reuse away from chronological neighbors on the public examples."""

import argparse
from decimal import Decimal
import json
from pathlib import Path

import numpy as np
from ortools.linear_solver import pywraplp

from official_tree import ExactRecourse


def coverage(path, opening):
    raw = path.read_bytes()
    instance = json.loads(raw)
    exact = ExactRecourse(json.loads(raw, parse_float=Decimal))
    costs = np.asarray(instance["transportation_costs"])
    demands = np.asarray([scenario["demands"] for scenario in instance["scenarios"]])
    capacity = np.asarray([facility["capacity"] for facility in instance["facilities"]])
    opened = np.zeros(len(capacity))
    opened[opening] = 1
    sub = pywraplp.Solver.CreateSolver("CLP")
    sub.SetNumThreads(1)
    objective = sub.Objective()
    objective.SetMinimization()
    cap_rows = [sub.Constraint(0, float(value)) for value in capacity * opened]
    dem_rows = [sub.Constraint(0, sub.infinity()) for _ in demands[0]]
    variables = []
    for i, cap_row in enumerate(cap_rows):
        row = []
        for j, dem_row in enumerate(dem_rows):
            variable = sub.NumVar(0, sub.infinity(), "")
            cap_row.SetCoefficient(variable, 1)
            dem_row.SetCoefficient(variable, 1)
            objective.SetCoefficient(variable, float(costs[i, j]))
            row.append(variable)
        variables.append(row)
    ranks = np.argsort(demands.sum(axis=1), kind="stable")
    anchors = list(map(int, ranks[np.linspace(0, len(ranks) - 1, 24, dtype=int)]))
    trees, checks = [], []
    for k in anchors:
        for constraint, rhs in zip(dem_rows, demands[k], strict=True):
            constraint.SetLb(float(rhs))
        if sub.Solve() != sub.OPTIMAL:
            raise RuntimeError(f"Fixed layout not solved for scenario {k}")
        alpha = np.maximum(0, np.asarray([row.DualValue() for row in dem_rows]))
        beta = np.maximum(0, np.max(alpha - costs, axis=1))
        exact.begin(opened)
        exact.learn(alpha, beta, variables)
        if exact.tree is None:
            continue
        value = exact.tree.evaluate(exact.demands[k], False)
        if value is not None and abs(value[0] - objective.Value()) >= 1e-6:
            raise ValueError(f"Anchor objective disagreement at scenario {k}")
        checks.append({"scenario": k, "self_certified": value is not None})
        trees.append(exact.tree)
    others = sorted(set(range(len(demands))) - set(anchors))
    covered = [k for k in others if any(tree.evaluate(exact.demands[k], False) is not None for tree in trees)]
    return {"layout": opening, "attempted_anchors": anchors, "learned_anchors": checks,
            "other_cases": len(others), "covered_other_cases": covered}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--instance-dir", required=True, type=Path)
    sources = parser.add_mutually_exclusive_group(required=True)
    sources.add_argument("--summary", type=Path)
    sources.add_argument("--layout-report", type=Path, help="Use only the recorded initial layout from each case")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.summary:
        rows = json.loads(args.summary.read_bytes())["results"]
        layouts = {row["case"]: row["trace"]["initial_open"] for row in rows
                   if row["repeat"] == 1 and row["arm"] == "clp"}
    else:
        records = json.loads(args.layout_report.read_bytes())
        layouts = {label: row["layout"] for label, row in records.items()}
    report = {label: coverage(args.instance_dir / (label.replace("large_", "large_instance_") + ".json"), layout)
              for label, layout in layouts.items()}
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(report, file, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
