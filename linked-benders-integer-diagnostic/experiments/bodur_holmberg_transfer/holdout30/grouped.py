"""Exact affine transport cuts for grouped Jensen relaxations."""

from dataclasses import dataclass
from hashlib import sha256
import json
from time import perf_counter

import numpy as np
from ortools.graph.python import min_cost_flow


@dataclass(frozen=True)
class Group:
    indices: tuple[int, ...]
    demand: tuple[int, ...]

    @property
    def size(self):
        return len(self.indices)


@dataclass(frozen=True)
class GroupCut:
    constant: int
    coefficients: tuple[int, ...]
    primal: int
    exact: bool
    witness_sha256: str

    def value(self, layout):
        return self.constant + sum(self.coefficients[i] for i in layout)


def build_groups(data, count=8):
    """Split the stable total-demand ordering into nearly equal consecutive groups."""
    if not 1 <= count <= data.scenario_count == len(data.demands):
        raise ValueError("Invalid group or scenario count")
    if data.scenario_count * data.peak > np.iinfo(np.int64).max:
        raise ValueError("Group demand aggregation risks int64 overflow")
    totals = data.demands.sum(axis=1)
    ranked = sorted(range(data.scenario_count), key=lambda i: (int(totals[i]), i))
    size, extra = divmod(len(ranked), count)
    groups = []
    start = 0
    for g in range(count):
        stop = start + size + (g < extra)
        member = tuple(ranked[start:stop])
        demand = tuple(map(int, data.demands[list(member)].sum(axis=0)))
        groups.append(Group(member, demand))
        start = stop
    return tuple(groups)


def _demand_potentials(cost, supply, demand, shipments, used):
    """Recover potentials from the shipment support via residual difference constraints."""
    n = len(supply)
    weights = {}
    for i, j, _ in shipments:
        for k, row in enumerate(cost):
            difference = row[j] - cost[i][j]
            pair = (k, i)
            if pair not in weights or difference < weights[pair]:
                weights[pair] = difference
    edges = [(k, i, w) for (k, i), w in weights.items()]
    edges.extend((i, n, 0) for i in range(n))
    edges.extend((n, i, 0) for i in range(n) if used[i] < supply[i])
    distance = [0] * (n + 1)
    for _ in range(n + 1):
        changed = False
        for k, i, weight in edges:
            candidate = distance[k] + weight
            if candidate < distance[i]:
                distance[i] = candidate
                changed = True
        if not changed:
            break
    else:
        return None
    penalty = [value - distance[n] for value in distance[:n]]
    alpha = tuple(min(row[j] + beta for row, beta in zip(cost, penalty, strict=True))
                  for j in range(len(demand)))
    dual = sum(a * d for a, d in zip(alpha, demand, strict=True))
    dual -= sum(beta * cap for beta, cap in zip(penalty, supply, strict=True))
    primal = sum(cost[i][j] * amount for i, j, amount in shipments)
    if min(penalty) < 0 or dual != primal:
        raise ArithmeticError("Recovered transport dual did not certify its flow")
    return alpha


def _solve_group(data, layout, group, deadline):
    supply = tuple(int(data.capacities[i]) * group.size for i in layout)
    exact_cost = tuple(tuple(map(int, data.cost[i])) for i in layout)
    quantity = sum(group.demand)
    if quantity > sum(supply):
        raise ValueError("The selected facilities cannot supply grouped demand")
    if quantity == 0:
        return GroupCut(0, (0,) * len(data.capacities), 0, True, sha256(b"[]").hexdigest())

    # OR-Tools searches with int64 costs. Recover and verify any final cut in original units.
    maximum = max(map(max, exact_cost))
    safe_max = (2**60 - 1) // max(quantity, len(layout) + len(group.demand) + 1)
    use_exact_cost = maximum <= safe_max
    if use_exact_cost:
        search_cost = exact_cost
    else:
        precision = min(10**7, safe_max * data.cost_scale // maximum)
        if precision < 1:
            raise ValueError("Grouped min-cost flow exceeds the supported numeric search range")
        search_cost = tuple(tuple(c * precision // data.cost_scale for c in row) for row in exact_cost)

    n = len(layout)
    source = n + len(group.demand)
    oracle = min_cost_flow.SimpleMinCostFlow()
    for i, cap in enumerate(supply):
        oracle.add_arc_with_capacity_and_unit_cost(source, i, min(cap, quantity), 0)
    arcs = [(oracle.add_arc_with_capacity_and_unit_cost(i, n + j, quantity, cost), i, j)
            for i, row in enumerate(search_cost) for j, cost in enumerate(row)]
    ids = np.asarray([edge for edge, _, _ in arcs], dtype=np.int32)
    oracle.set_nodes_supplies(np.arange(n, source, dtype=np.int32), -np.asarray(group.demand, dtype=np.int64))
    oracle.set_node_supply(source, quantity)
    if perf_counter() >= deadline:
        return None
    status = oracle.solve()
    if status != oracle.OPTIMAL:
        raise ArithmeticError(f"Grouped integer min-cost flow failed: {status}")

    used = [0] * n
    delivered = [0] * len(group.demand)
    shipments = []
    primal = 0
    for (_, i, j), raw_amount in zip(arcs, oracle.flows(ids), strict=True):
        amount = int(raw_amount)
        if amount < 0:
            raise ArithmeticError("Grouped integer flow contains a negative shipment")
        if amount:
            shipments.append((i, j, amount))
            used[i] += amount
            delivered[j] += amount
            primal += exact_cost[i][j] * amount
    if (tuple(delivered) != group.demand
            or any(amount > cap for amount, cap in zip(used, supply, strict=True))):
        raise ArithmeticError("Grouped integer flow violates demand or capacity")

    alpha = _demand_potentials(exact_cost, supply, group.demand, shipments, used)
    if alpha is None:
        if use_exact_cost:
            raise ArithmeticError("Original-cost integer flow has no exact dual")
        rounded_alpha = _demand_potentials(search_cost, supply, group.demand, shipments, used)
        if rounded_alpha is None:
            raise ArithmeticError("The numeric search flow has no dual in its search costs")
        alpha = tuple(a * data.cost_scale // precision for a in rounded_alpha)

    # Extend the dual to every facility by enforcing all original-cost arc inequalities.
    beta = tuple(min(0, *(int(c) - a for c, a in zip(row, alpha, strict=True))) for row in data.cost)
    if any(b > 0 or any(b + a > c for a, c in zip(alpha, row, strict=True))
           for b, row in zip(beta, data.cost, strict=True)):
        raise ArithmeticError("Projected grouped dual violates an original-cost inequality")
    constant = sum(a * d for a, d in zip(alpha, group.demand, strict=True))
    coefficients = tuple(b * int(cap) * group.size for b, cap in zip(beta, data.capacities, strict=True))
    lower = constant + sum(coefficients[i] for i in layout)
    if lower > primal:
        raise ArithmeticError("Grouped dual exceeds the original-cost feasible flow")
    record = [(layout[i], j, amount) for i, j, amount in shipments]
    witness = sha256(json.dumps(record, separators=(",", ":")).encode("ascii")).hexdigest()
    if perf_counter() >= deadline:
        return None
    return GroupCut(constant, coefficients, primal, lower == primal, witness)


def grouped_cuts(data, layout, groups, deadline):
    """Return one certified scaled shipping cut per group, or None at the deadline.

    Multiply both mean demand and site capacity by group size. This yields the
    weighted group cost in integer units, before division by data.divisor.
    """
    layout = tuple(map(int, layout))
    if (not layout or tuple(sorted(set(layout))) != layout
            or layout[0] < 0 or layout[-1] >= len(data.capacities)):
        raise ValueError("Expected a sorted, unique, nonempty facility layout")
    cuts = []
    for group in groups:
        if perf_counter() >= deadline:
            return None
        cut = _solve_group(data, layout, group, deadline)
        if cut is None:
            return None
        cuts.append(cut)
    return tuple(cuts)
