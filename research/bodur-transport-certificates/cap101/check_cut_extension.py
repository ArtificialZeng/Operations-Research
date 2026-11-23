"""Check one exact extension of a fixed-layout transportation dual on CAP101."""

import argparse
from fractions import Fraction
from hashlib import sha256
import json
from pathlib import Path
from time import perf_counter
from urllib.request import urlopen

from probe import (
    ARCHIVE_HASH, UNITS, URL, HighsTransport, apply_certificate, certify_tree,
    open_sets, read_cap, sample,
)


def exact_recourse(layout, capacity, costs, cost_scale, demand):
    caps = capacity[layout] * UNITS
    active_costs = [costs[i] for i in layout]
    solver = HighsTransport(caps, active_costs, cost_scale)
    floating = solver.solve(demand, perf_counter() + 2.0)
    tree = certify_tree(solver.tree_columns(), caps, active_costs)
    if tree is None:
        raise ArithmeticError("The solver basis did not yield an exact transportation tree")
    hits, values = apply_certificate(tree, caps, demand[None, :], cost_scale)
    if hits.tolist() != [0] or abs(values[0] - floating) > max(1e-6, 1e-9 * abs(floating)):
        raise ArithmeticError("The exact transportation tree does not match the LP")
    flow = tree.initial_flow + tree.demand_map @ demand
    exact = sum(cost * int(quantity) for cost, quantity in zip(tree.edge_costs, flow, strict=True))
    return exact, tree


def exact_value(scaled, divisor):
    return {"scaled_integer": str(scaled), "fraction": str(Fraction(scaled, divisor)),
            "decimal_approximation": scaled / divisor}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.archive:
        raw = args.archive.read_bytes()
    else:
        with urlopen(URL, timeout=10) as reply:
            raw = reply.read()
    capacity, opening, nominal, costs, cost_scale = read_cap(raw)
    scenarios = sample(nominal)
    scenario_index = int(scenarios.sum(axis=1).argmax())
    demand = scenarios[scenario_index]
    anchor = open_sets(capacity, opening, scenarios)["capacity_cover"]
    replacement = next(i for i in range(len(capacity)) if i not in anchor)
    alternative = sorted([replacement, *anchor[1:]])
    if int(capacity[alternative].sum()) * UNITS < int(demand.sum()):
        raise ValueError("The alternate layout cannot cover the selected scenario")

    anchor_exact, tree = exact_recourse(anchor, capacity, costs, cost_scale, demand)
    alternative_exact, _ = exact_recourse(alternative, capacity, costs, cost_scale, demand)
    if tree.customer_dual[-1] != 0:
        raise ArithmeticError("The unused-capacity sink was not normalized to zero")
    v = [max(0, value) for value in tree.customer_dual[:-1]]
    active = dict(zip(anchor, tree.source_dual, strict=True))
    u = [active[i] if i in active else min(0, min(c - y for c, y in zip(row[:-1], v, strict=True)))
         for i, row in enumerate(costs)]
    slack = [c - x - y for x, row in zip(u, costs, strict=True) for c, y in zip(row[:-1], v, strict=True)]
    if max(u) > 0 or min(v) < 0 or min(slack) < 0:
        raise ArithmeticError("Extended dual was not globally feasible")

    intercept = sum(y * int(q) for y, q in zip(v, demand, strict=True))
    slope = [x * int(cap) * UNITS for x, cap in zip(u, capacity, strict=True)]
    anchor_bound = intercept + sum(slope[i] for i in anchor)
    alternate_bound = intercept + sum(slope[i] for i in alternative)
    if anchor_bound != anchor_exact or alternate_bound > alternative_exact:
        raise ArithmeticError("Extended cut failed anchor tightness or alternate validity")

    divisor = cost_scale * UNITS
    record = {"source": URL, "source_sha256": ARCHIVE_HASH, "scenarios": len(scenarios),
              "frozen_demands_sha256": sha256(scenarios.astype("<i8").tobytes()).hexdigest(),
              "selected_scenario_zero_based": scenario_index, "selection": "first maximum total demand",
              "demand_milliunits": int(demand.sum()), "opening_indices_zero_based": anchor,
              "alternative_opening_indices_zero_based": alternative, "unit_cost_scale": cost_scale,
              "capacity_dual_scaled": u, "demand_dual_scaled": v, "arcs_checked": len(slack),
              "minimum_arc_slack_scaled": min(slack), "max_capacity_dual_scaled": max(u),
              "min_demand_dual_scaled": min(v), "anchor_exact_recourse": exact_value(anchor_exact, divisor),
              "anchor_cut": exact_value(anchor_bound, divisor),
              "alternative_exact_recourse": exact_value(alternative_exact, divisor),
              "alternative_cut": exact_value(alternate_bound, divisor),
              "alternative_cut_slack": exact_value(alternative_exact - alternate_bound, divisor)}
    args.output.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(f"{len(slack)} exact dual inequalities; anchor tight; "
          f"alternative lower bound {alternate_bound / divisor:.6f} ≤ {alternative_exact / divisor:.6f}")


if __name__ == "__main__":
    main()
