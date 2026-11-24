"""Verified feasible-mask bounds and transportation witnesses for locked Holmberg adaptations."""

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
import json
from math import lcm
from pathlib import Path
from time import perf_counter

import numpy as np
from ortools.graph.python import min_cost_flow


HERE = Path(__file__).resolve().parent
MANIFEST_SHA = "c526bc8fba081d322f59d99ebf3b5b58b8198c11d771a8fcb6a4d20058f6084a"
SEARCH_SCALE = 10**7


@dataclass
class Instance:
    name: str
    sha256: str
    capacities: tuple
    opening: tuple
    cost: tuple
    cost_scale: int
    demands: np.ndarray
    total_by_customer: tuple
    units: int
    peak: int
    scenario_count: int

    @property
    def divisor(self):
        return self.cost_scale * self.units * self.scenario_count


def load(name):
    directory = HERE / "instances"
    manifest_bytes = (directory / "manifest.json").read_bytes()
    if sha256(manifest_bytes).hexdigest() != MANIFEST_SHA:
        raise ValueError("Locked Holmberg manifest changed")
    source = json.loads(manifest_bytes)["cases"][name]
    raw = (directory / source["file"]).read_bytes()
    if sha256(raw).hexdigest() != source["sha256"]:
        raise ValueError(f"Locked input changed for {name}")
    data = json.loads(raw)
    f, c, k = (data[key] for key in ("num_facilities", "num_customers", "num_scenarios"))
    unit = data["demand_units_per_source_unit"]
    cap = tuple(x * unit for x in data["facility_capacities"])
    opening = tuple(map(Fraction, data["opening_costs_exact"]))
    rational_cost = tuple(tuple(map(Fraction, row)) for row in data["unit_costs_exact"])
    scale = lcm(*(x.denominator for row in rational_cost for x in row))
    costs = tuple(tuple(int(x * scale) for x in row) for row in rational_cost)
    quantity = data["scenario_demands_milliunits"]
    if (not 2 <= f <= 10 or len(cap) != f or len(opening) != f or len(costs) != f
            or any(len(row) != c for row in costs) or min(opening) < 0 or min(cap) <= 0
            or any(min(row) < 0 for row in costs) or not k or len(quantity) != k
            or any(len(row) != c or any(type(q) is not int or q < 0 for q in row) for row in quantity)
            or data["probability_denominator"] != k):
        raise ValueError("Unexpected locked transport dimensions or sign pattern")
    peak = max(map(sum, quantity))
    if peak != source["peak_demand_milliunits"] or k * peak > np.iinfo(np.int64).max:
        raise ValueError("Unsafe quantity aggregation or unexpected peak")
    demand = np.asarray(quantity, dtype=np.int64)
    return Instance(name, source["sha256"], cap, opening, costs, scale, demand,
                    tuple(map(int, demand.sum(axis=0))), unit, peak, k)


def nearest_bounds(data, layout, full_ranks):
    """Charge original nearest cost, then independent forced diversion by owner."""
    opened = set(layout)
    groups = {i: [] for i in layout}
    all_open_base = 0
    closure_penalty = 0
    nearest_cost = 0
    for j, ranking in enumerate(full_ranks):
        first, second = ranking[:2]
        demand = data.total_by_customer[j]
        all_open_base += data.cost[first][j] * demand
        if first not in opened:
            closure_penalty += (data.cost[second][j] - data.cost[first][j]) * demand
        nearest = [i for i in ranking if i in opened][:2]
        owner = nearest[0]
        price = data.cost[owner][j]
        nearest_cost += price * demand
        gap = data.cost[nearest[1]][j] - price if len(nearest) > 1 else 0
        groups[owner].append((gap, j))

    spill = 0
    for i, customers in groups.items():
        if not customers:
            continue
        columns = [j for _, j in customers]
        excess = np.maximum(data.demands[:, columns].sum(axis=1) - data.capacities[i], 0)
        if not excess.any():
            continue
        if len(layout) == 1:
            raise ArithmeticError("Capacity-feasible singleton showed excess")
        for gap, j in sorted(customers):
            moved = np.minimum(excess, data.demands[:, j])
            spill += gap * int(moved.sum())
            excess -= moved
            if not excess.any():
                break
    opening = sum((data.opening[i] for i in layout), Fraction())
    return tuple(opening + Fraction(v, data.divisor)
                 for v in (all_open_base + closure_penalty, nearest_cost, nearest_cost + spill))


def check_dual(cost, supply, demand, positive, row_totals):
    """Use residual difference constraints to verify a dual from an integer shipment support."""
    n = len(supply)
    weights = [[None] * n for _ in range(n)]
    for i, j, _ in positive:
        for k, row in enumerate(cost):
            difference = row[j] - cost[i][j]
            bound = weights[k][i]
            if bound is None or difference < bound:
                weights[k][i] = difference
    edges = [(i, j, w) for i, row in enumerate(weights) for j, w in enumerate(row) if w is not None]
    edges.extend((i, n, 0) for i in range(n))
    edges.extend((n, i, 0) for i, shipped in enumerate(row_totals) if shipped < supply[i])
    distance = [0] * (n + 1)
    for _ in range(n + 1):
        changed = False
        for start, end, bound in edges:
            value = distance[start] + bound
            if value < distance[end]:
                distance[end] = value
                changed = True
        if not changed:
            break
    else:
        return None
    beta = [b - distance[n] for b in distance[:n]]
    if min(beta) < 0 or any(beta[i] and row_totals[i] < supply[i] for i in range(n)):
        raise ArithmeticError("Invalid capacity dual signs or complementary slackness")
    alpha = [min(row[j] + beta[i] for i, row in enumerate(cost)) for j in range(len(demand))]
    if min(alpha) < 0 or any(alpha[j] - beta[i] > c for i, row in enumerate(cost) for j, c in enumerate(row)):
        raise ArithmeticError("Invalid demand or transportation dual")
    return sum(a * int(d) for a, d in zip(alpha, demand)) - sum(b * q for b, q in zip(beta, supply))


def verified_transport(data, layout, deadline, show_witness):
    n = len(layout)
    c = data.demands.shape[1]
    source = n + c
    supply = tuple(data.capacities[i] for i in layout)
    exact_cost = tuple(data.cost[i] for i in layout)
    rounded = tuple(tuple(q * SEARCH_SCALE // data.cost_scale for q in row) for row in exact_cost)
    if max(map(max, rounded)) * data.peak > 2**60:
        raise ValueError("Unsafe OR-Tools min-cost-flow integer range")
    solver = min_cost_flow.SimpleMinCostFlow()
    map_edges = []
    for i, cap in enumerate(supply):
        solver.add_arc_with_capacity_and_unit_cost(source, i, cap, 0)
        for j, unit_cost in enumerate(rounded[i]):
            edge = solver.add_arc_with_capacity_and_unit_cost(i, n + j, data.peak, unit_cost)
            map_edges.append((edge, i, j))
    ids = np.asarray([edge for edge, _, _ in map_edges], dtype=np.int32)
    demand_nodes = np.arange(n, n + c, dtype=np.int32)
    opening = sum((data.opening[i] for i in layout), Fraction())
    elapsed_started = perf_counter()
    exact_value = 0
    floor_value = 0
    upper = 0
    exact_hits = 0
    witness_hash = sha256()
    witness = []
    for demand in data.demands:
        if perf_counter() >= deadline:
            return None
        solver.set_nodes_supplies(demand_nodes, -demand)
        solver.set_node_supply(source, int(demand.sum()))
        status = solver.solve()
        if status != solver.OPTIMAL:
            raise ArithmeticError(f"Integer routing solver failed: {status}")
        origins, destinations = [0] * n, [0] * c
        shipments = []
        cost = 0
        for (_, i, j), quantity in zip(map_edges, solver.flows(ids), strict=True):
            units = int(quantity)
            if units < 0:
                raise ArithmeticError("Negative integer shipment")
            if units:
                origins[i] += units
                destinations[j] += units
                cost += exact_cost[i][j] * units
                shipments.append((i, j, units))
        if destinations != list(map(int, demand)) or any(a > b for a, b in zip(origins, supply)):
            raise ArithmeticError("Constructive shipment violates capacity or demand")
        upper += cost
        dual = check_dual(exact_cost, supply, demand, shipments, origins)
        if dual is None:
            floored = check_dual(rounded, supply, demand, shipments, origins)
            rounded_primal = sum(rounded[i][j] * units for i, j, units in shipments)
            if floored != rounded_primal:
                raise ArithmeticError("Failed to verify the rounded-cost lower certificate")
            floor_value += floored
        else:
            if dual != cost:
                raise ArithmeticError("Original-cost primal and dual objectives disagree")
            exact_value += dual
            exact_hits += 1
        record = [(layout[i], j, units) for i, j, units in shipments]
        witness_hash.update((json.dumps(record, separators=(",", ":")) + "\n").encode("ascii"))
        if show_witness:
            witness.append(record)
    lower = opening + Fraction(exact_value, data.divisor) + Fraction(
        floor_value, SEARCH_SCALE * data.units * data.scenario_count)
    objective = opening + Fraction(upper, data.divisor)
    return {"layout": layout, "exact_dual_scenarios": exact_hits,
            "floor_cost_dual_scenarios": data.scenario_count - exact_hits,
            "lower": lower, "upper": objective, "witness_sha256": witness_hash.hexdigest(),
            "seconds": perf_counter() - elapsed_started, **({"shipments_milliunits": witness} if show_witness else {})}


def report(data, max_layouts, seconds, show_witness):
    start = perf_counter()
    deadline = start + seconds
    facility_count = len(data.capacities)
    group_ranks = [sorted(range(facility_count), key=lambda i: (data.cost[i][j], i))
                   for j in range(data.demands.shape[1])]
    bounds = {}
    for mask in range(1, 1 << facility_count):
        layout = tuple(i for i in range(facility_count) if (mask >> i) & 1)
        if sum(data.capacities[i] for i in layout) >= data.peak:
            bounds[layout] = nearest_bounds(data, layout, group_ranks)

    certificates = []
    tightened = {layout: entry[-1] for layout, entry in bounds.items()}
    incumbent = None
    for layout in sorted(bounds, key=lambda row: (bounds[row][-1], row)):
        if len(certificates) >= max_layouts or (incumbent is not None and tightened[layout] > incumbent):
            break
        certificate = verified_transport(data, layout, deadline, show_witness)
        if certificate is None:
            break
        new_lower = max(tightened[layout], certificate["lower"])
        if new_lower > certificate["upper"]:
            raise ArithmeticError("Contradictory transportation bounds")
        tightened[layout] = new_lower
        certificates.append(certificate)
        incumbent = certificate["upper"] if incumbent is None else min(incumbent, certificate["upper"])

    final_lower = min(tightened.values())
    best = min(certificates, key=lambda x: x["upper"]) if certificates else None
    rivals = min((bound for layout, bound in tightened.items() if best and layout != best["layout"]), default=None)
    return {"case": data.name, "input_sha256": data.sha256, "total_capacity_feasible_masks": len(bounds),
            "global_directional_nearest_closure_lower": min(x[0] for x in bounds.values()),
            "global_nearest_open_lower": min(x[1] for x in bounds.values()),
            "global_independent_capacity_spill_lower": min(x[2] for x in bounds.values()),
            "global_final_lower": final_lower, "global_feasible_upper": incumbent,
            "best_layout": best["layout"] if best else None, "lower_for_any_rival_layout": rivals,
            "unique_best_layout_certified": incumbent is not None and (rivals is None or incumbent < rivals),
            "global_exact_objective_certified": incumbent is not None and final_lower == incumbent,
            "original_cost_integer_scale": data.cost_scale, "rounding_down_search_cost_scale": SEARCH_SCALE,
            "certificates": certificates, "seconds": perf_counter() - start}


def json_fraction(obj):
    if not isinstance(obj, Fraction):
        raise TypeError(type(obj))
    return {"exact": str(obj), "decimal_approx": float(obj)}


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--case", choices=("p1", "p41"), required=True)
    cli.add_argument("--max-layouts", type=int, default=3)
    cli.add_argument("--seconds", type=float, default=25)
    cli.add_argument("--include-witness", action="store_true", help="Include all verified shipment triples in stdout JSON")
    args = cli.parse_args()
    print(json.dumps(report(load(args.case), args.max_layouts, args.seconds, args.include_witness),
                     default=json_fraction, indent=2))


if __name__ == "__main__":
    main()
