"""Matched exact two-group tests on the sealed empirical Liu inputs."""

from time import perf_counter

START = perf_counter()

import argparse
from dataclasses import replace
from fractions import Fraction
from hashlib import sha256
from heapq import heapify, heappop, heappush
import json
from math import lcm
import os
from pathlib import Path
import sys

import networkx as nx
import numpy as np


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "bodur_holmberg_transfer"))
from holdout30.grouped import _demand_potentials, build_groups
from independent import Instance


MANIFEST_SHA256 = "89bd25716bbc06b499ed638551cfa3956744052ec7a12ab24e233dfb05625052"
CASES = {"liu_saa36": 36, "liu_2019_quarters4": 4}
OFFSET = 500
BUDGET = 60.0


def load(case):
    count = CASES[case]
    manifest = (HERE / "manifest.json").read_bytes()
    if sha256(manifest).hexdigest() != MANIFEST_SHA256:
        raise ValueError("Liu manifest bytes changed")
    entry = json.loads(manifest)["cases"][case]
    raw = (HERE / entry["file"]).read_bytes()
    if sha256(raw).hexdigest() != entry["sha256"]:
        raise ValueError("Liu instance bytes changed")
    model = json.loads(raw)
    dummy, = model["fixed_open_facilities"]
    cap = tuple(map(Fraction, model["facility_capacities_exact"]))
    opening = tuple(map(Fraction, model["opening_costs_exact"]))
    raw_cost = tuple(tuple(map(Fraction, row)) for row in model["unit_costs_exact"])
    demand = tuple(tuple(map(Fraction, row)) for row in model["scenario_demands_exact"])
    peak = max(map(sum, demand))
    if (dummy != 10 or not len(cap) == len(opening) == len(raw_cost) == 11
            or not len(demand) == count == model["probability_denominator"]
            or any(len(row) != 20 or min(row) < 0 for row in (*raw_cost, *demand))
            or tuple(map(Fraction, model["scenario_probabilities_exact"])) != (Fraction(1, count),) * count
            or cap[dummy] < peak or min(cap) <= 0 or opening[dummy] or min(opening) < 0
            or peak != Fraction(model["peak_demand_exact"]) or model["real_capacity_cover_required"]
            or raw_cost[dummy] != tuple(map(Fraction, model["lost_sale_costs_exact"]))
            or min(r - c for row in raw_cost[:dummy] for r, c in zip(raw_cost[dummy], row, strict=True))
            != Fraction(model["common_shortage_offset_exact"]) or Fraction(model["common_shortage_offset_exact"]) != OFFSET):
        raise ValueError("Liu dimensions, probabilities, or decomposition assumptions changed")
    units = lcm(*(q.denominator for row in (cap, *demand) for q in row))
    scale = lcm(*(q.denominator for row in (opening, *raw_cost) for q in row))
    if max(max(cap), sum(map(sum, demand))) * units > np.iinfo(np.int64).max:
        raise ValueError("Quantity matrix exceeds exact int64 aggregation")
    quantities = np.asarray([[int(q * units) for q in row] for row in demand], dtype=np.int64)
    costs = tuple(tuple(int(c * scale) for c in row) for row in raw_cost)
    return Instance(case, entry["sha256"], tuple(int(c * units) for c in cap), opening, costs, scale,
                    quantities, tuple(map(int, quantities.sum(axis=0))), units, int(peak * units), count), dummy


def exact_flow(data, layout, demand, group_size, deadline):
    """Use unbounded Python integers and independently check primal and dual."""
    if perf_counter() >= deadline:
        return None
    total = sum(demand)
    used = [0] * len(layout)
    delivered = [0] * len(demand)
    caps = tuple(int(data.capacities[i]) * group_size for i in layout)
    cost = tuple(data.cost[i] for i in layout)
    n = len(layout)
    source = n + len(demand)
    graph = nx.DiGraph()
    graph.add_node(source, demand=-total)
    graph.add_nodes_from((n + j, {"demand": q}) for j, q in enumerate(demand))
    for i, cap in enumerate(caps):
        graph.add_edge(source, i, capacity=min(cap, total), weight=0)
        for j, price in enumerate(cost[i]):
            if demand[j]:
                graph.add_edge(i, n + j, capacity=demand[j], weight=price)
    optimum, flow = nx.network_simplex(graph)
    shipments = []
    primal = 0
    for i in range(n):
        for destination, quantity in flow[i].items():
            j = destination - n
            if quantity < 0:
                raise ArithmeticError("Negative shipment in the integer flow")
            if quantity:
                used[i] += quantity
                delivered[j] += quantity
                shipments.append((i, j, quantity))
                primal += cost[i][j] * quantity
    if (primal != optimum or tuple(delivered) != demand
            or any(a > b for a, b in zip(used, caps, strict=True))):
        raise ArithmeticError("Exact transportation witness violates flow or cost")
    alpha = _demand_potentials(cost, caps, demand, shipments, used)
    if alpha is None:
        raise ArithmeticError("Integer transportation optimum failed exact dual verification")
    beta = tuple(min(0, *(price - a for price, a in zip(row, alpha, strict=True))) for row in cost)
    lower = sum(a * q for a, q in zip(alpha, demand, strict=True))
    lower += sum(b * cap for b, cap in zip(beta, caps, strict=True))
    if lower != primal:
        raise ArithmeticError("Original-cost primal and dual disagree")
    record = [(layout[i], j, amount) for i, j, amount in shipments]
    witness = sha256(json.dumps(record, separators=(",", ":")).encode("ascii")).digest()
    return (primal, witness) if perf_counter() < deadline else None


def verify(data, layout, deadline):
    total = 0
    witness = sha256()
    for row in data.demands:
        result = exact_flow(data, layout, tuple(map(int, row)), 1, deadline)
        if result is None:
            return None
        cost, flow_hash = result
        total += cost
        witness.update(flow_hash)
    opening = sum((data.opening[i] for i in layout), Fraction())
    return {"objective": opening + Fraction(total, data.divisor),
            "witness_sha256": witness.hexdigest(), "exact_scenarios": data.scenario_count}


def prepare(data, dummy, deadline):
    layout = tuple(range(len(data.capacities)))
    witness = verify(data, layout, deadline)
    if witness is None:
        raise TimeoutError("Common all-open layout could not be verified")
    return {"case": data.name, "instance_sha256": data.sha256, "open": layout, "fixed_open": [dummy], **witness}


def solve(data, dummy, deadline, arm, seed=None):
    started = perf_counter()
    if arm not in ("original", "residual"):
        raise ValueError(arm)
    if seed is None:
        seed = prepare(data, dummy, deadline)
    best = tuple(seed["open"])
    upper = Fraction(seed["objective"])
    if (seed["case"] != data.name or seed["instance_sha256"] != data.sha256
            or seed["fixed_open"] != [dummy] or best != tuple(range(len(data.capacities)))
            or seed["exact_scenarios"] != data.scenario_count):
        raise ValueError("Unexpected independent all-open seed")
    witness = seed["witness_sha256"]
    real = tuple(i for i in range(len(data.capacities)) if i != dummy)
    delta = OFFSET * data.cost_scale
    if any(r - c < delta for i in real for r, c in zip(data.cost[dummy], data.cost[i], strict=True)):
        raise ValueError("Invalid exact shortage offset")
    costs = tuple(tuple(v - delta for v in row) if i == dummy else row for i, row in enumerate(data.cost))
    relaxation = replace(data, cost=costs) if arm == "residual" else data
    groups = build_groups(data, 2)
    totals = tuple(sum(map(int, row)) for row in data.demands)
    opening = tuple(int(value * data.divisor) for value in data.opening)
    if any(Fraction(q, data.divisor) != v for q, v in zip(opening, data.opening, strict=True)):
        raise ValueError("Opening cost does not fit exact denominator")

    pending = []
    layouts = []
    included_costs = []
    real_caps = []
    fixed_costs = []
    all_open_mask = (1 << len(real)) - 1
    for mask in range(all_open_mask + 1):
        if perf_counter() >= deadline:
            break
        if not mask:
            layout, nearest, capacity, fixed = (dummy,), data.cost[dummy], 0, opening[dummy]
        else:
            bit = mask & -mask
            previous, i = mask ^ bit, real[bit.bit_length() - 1]
            layout = tuple(sorted((*layouts[previous], i)))
            nearest = tuple(min(a, b) for a, b in zip(included_costs[previous], data.cost[i], strict=True))
            capacity = real_caps[previous] + data.capacities[i]
            fixed = fixed_costs[previous] + opening[i]
        layouts.append(layout)
        included_costs.append(nearest)
        real_caps.append(capacity)
        fixed_costs.append(fixed)
        if mask != all_open_mask:
            cheap = fixed + sum(c * int(q) for c, q in zip(nearest, data.total_by_customer, strict=True))
            pending.append((cheap, 0, mask))
    unknown = max(0, all_open_mask - len(layouts))
    heapify(pending)
    built = perf_counter()
    counts = {"cheap_pruned": 0, "grouped_pruned": 0, "grouped_layouts": 0, "full_scenario_sweeps": 0}
    times = {"setup_seconds": built - started, "grouped_seconds": 0.0, "full_scenario_seconds": 0.0}

    while pending and perf_counter() < deadline:
        bound, stage, mask = heappop(pending)
        if bound >= upper * data.divisor:
            counts["cheap_pruned"] += stage == 0
            counts["grouped_pruned"] += stage != 0
            continue
        layout = layouts[mask]
        clock = perf_counter()
        if stage == 0:
            grouped_bound = fixed_costs[mask]
            for group in groups:
                flow = exact_flow(relaxation, layout, group.demand, group.size, deadline)
                if flow is None:
                    break
                grouped_bound += flow[0]
            times["grouped_seconds"] += perf_counter() - clock
            if flow is None:
                heappush(pending, (bound, stage, mask))
                break
            if arm == "residual":
                grouped_bound += delta * sum(max(0, d - real_caps[mask]) for d in totals)
            counts["grouped_layouts"] += 1
            heappush(pending, (max(bound, grouped_bound), 1, mask))
        else:
            certificate = verify(data, layout, deadline)
            times["full_scenario_seconds"] += perf_counter() - clock
            if certificate is None:
                heappush(pending, (bound, stage, mask))
                break
            counts["full_scenario_sweeps"] += 1
            if Fraction(bound, data.divisor) > certificate["objective"]:
                raise ArithmeticError("Grouped bound exceeds exact original-scenario recourse")
            if certificate["objective"] < upper:
                upper, best, witness = certificate["objective"], layout, certificate["witness_sha256"]

    lower = Fraction() if unknown else upper
    if pending:
        lower = min(lower, Fraction(pending[0][0], data.divisor))
    retired = counts["cheap_pruned"] + counts["grouped_pruned"] + counts["full_scenario_sweeps"] + 1
    if unknown + len(pending) + retired != all_open_mask + 1:
        raise ArithmeticError("A layout was lost or duplicated in the exact enumeration")
    return {"arm": arm, "global_lower": lower, "global_upper": upper, "open": best, "fixed_open": [dummy],
            "witness_sha256": witness, "global_optimum_certified": lower == upper,
            "group_sizes": [group.size for group in groups], "unprocessed_layouts": unknown + len(pending),
            "total_layouts": all_open_mask + 1, **counts, **times, "solve_seconds": perf_counter() - started}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--case", required=True, choices=CASES)
    parser.add_argument("--arm", required=True, choices=("prepare", "original", "residual"))
    parser.add_argument("--seed", type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    affinity = sorted(os.sched_getaffinity(0))
    if len(affinity) != 1 or args.out.exists():
        raise ValueError("Use a single pinned CPU and a fresh output path")
    data, dummy = load(args.case)
    deadline = START + BUDGET - 0.5
    if args.arm == "prepare":
        result = prepare(data, dummy, deadline)
        result["shared_seconds"] = perf_counter() - START
    else:
        if args.seed is None:
            seed = prepare(data, dummy, deadline)
            setup = perf_counter() - START
            seed_hash = None
            charge = 0.0
        else:
            raw_seed = args.seed.read_bytes()
            seed = json.loads(raw_seed)
            seed_hash = sha256(raw_seed).hexdigest()
            setup = charge = seed["shared_seconds"]
        result = solve(data, dummy, deadline - charge, args.arm, seed)
        result.update(shared_seconds=setup, charged_seconds=charge + perf_counter() - START, seed_sha256=seed_hash)
    result.update(case=data.name, instance_sha256=data.sha256, manifest_sha256=MANIFEST_SHA256,
                  cost_scale=data.cost_scale, quantity_scale=data.units, cpu_affinity=affinity,
                  source_sha256=sha256(Path(__file__).read_bytes()).hexdigest(),
                  verifier_sha256=sha256(Path(_demand_potentials.__code__.co_filename).read_bytes()).hexdigest(),
                  networkx_version=nx.__version__)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, default=str, indent=2, allow_nan=False)
        stream.write("\n")


if __name__ == "__main__":
    main()
