"""Approximation certificates indexed by the exogenous clock source."""

from fractions import Fraction
from itertools import pairwise
from pathlib import Path
import sys


sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "flowshop_monge_budget"))
from release_dates import affine_graph, simulate


def source_problem(anchor, compulsory, a, tail, availability, costs, budget):
    """Build homogeneous reward arcs for schedules originating at one clock."""
    must_visit = {anchor, *(j for j in compulsory if j > anchor)}
    payable = {j: fee for j, fee in costs.items() if j > anchor and j not in must_visit and fee <= budget}
    vertices = sorted(must_visit | payable.keys())
    charge = {j: payable.get(j, 0) for j in vertices}
    baseline_start = {anchor: 0}
    latest = anchor
    for j in vertices[1:]:
        baseline_start[j] = baseline_start[latest] + a[latest, j]
        if j in must_visit:
            latest = j
    beta = baseline_start[vertices[-1]] + tail + (availability[anchor] if anchor >= 0 else 0)

    usable = {}
    for j in vertices[1:]:
        row = {}
        for i in vertices:
            if i >= j:
                break
            if (i, j) not in a or charge[i] + charge[j] > budget:
                continue
            value = baseline_start[i] + a[i, j] - baseline_start[j]
            if value < 0:
                raise ArithmeticError("A homogeneous contribution produced a negative reduced reward")
            row[i] = value
        usable[j] = row

    # Consecutive selected vertices form the all-affordable-lock path. Its
    # value bounds the budget optimum even when those locks cannot coexist.
    cap = sum(baseline_start[i] + a[i, j] - baseline_start[j] for i, j in pairwise(vertices))
    return vertices, charge, usable, beta, cap


def rounded_reward_path(vertices, charge, edges, budget, unit):
    """Minimize cost per exact rounded reward and reconstruct the best path."""
    dist = {vertices[0]: {0: 0}}
    parent = {}
    for j in vertices[1:]:
        current = {}
        for i, gain in edges[j].items():
            scaled = gain * unit.denominator // unit.numerator
            for reward_before, cost_before in dist[i].items():
                required = cost_before + charge[j]
                if required <= budget:
                    reward = reward_before + scaled
                    if reward not in current or required < current[reward]:
                        current[reward] = required
                        parent[j, reward] = (i, reward_before)
        dist[j] = current

    j = vertices[-1]
    rounded = max(dist[j])
    reward, spent, actual_gain = rounded, dist[j][rounded], 0
    chosen = []
    while j != vertices[0]:
        if charge[j]:
            chosen.append(j)
        i, reward_before = parent[j, reward]
        actual_gain += edges[j][i]
        j, reward = i, reward_before
    return actual_gain, sorted(chosen), spent, rounded


def approximate(work, setup, availability, job_release, fixed, costs, budget, eta):
    """Return a physically scored feasible lower bound and an additive upper bound."""
    eta = Fraction(eta)
    if not 0 < eta < 1 or budget < 0 or any(cost <= 0 for cost in costs.values()):
        raise ValueError("Expected 0 < eta < 1, a nonnegative budget and positive costs")

    (compulsory, a, tail), _ = affine_graph(work, setup, availability, fixed, range(len(work)),
                                            job_release=job_release)
    baseline = simulate(work, setup, availability, fixed, job_release=job_release)
    problems = []
    for clock in range(-1, len(work)):
        vertices, charge, edges, beta, cap = source_problem(clock, compulsory, a, tail, availability, costs, budget)
        problems.append((beta + cap - baseline, clock, vertices, charge, edges, beta, cap))

    def physical_value(chosen):
        return simulate(work, setup, availability, fixed | set(chosen), job_release=job_release) - baseline

    return certify_sources(problems, baseline, budget, eta, physical_value)


def certify_sources(problems, baseline, budget, eta, physical_value):
    """Solve and score per-source problems with a shared physical objective."""
    if max(row[5] for row in problems) != baseline:
        raise ArithmeticError("External-clock decomposition does not reconstruct the baseline")

    best_value, best_locks, best_cost = 0, [], 0
    records = []
    for optimistic, clock, vertices, charge, edges, beta, raw_cap in sorted(problems, reverse=True):
        d = baseline - beta
        largest = max((gain for row in edges.values() for gain in row.values()), default=0)
        record = {"clock": clock, "baseline_contribution": beta, "slack": d, "largest_edge_reward": largest}
        if optimistic <= best_value or largest == 0:
            records.append(record | {"upper": min(raw_cap, (len(vertices) - 1) * largest) - d, "status": "pruned"})
            continue

        path_length = len(vertices) - 1
        unit = eta * largest / path_length
        gain, chosen, cost, rounded = rounded_reward_path(vertices, charge, edges, budget, unit)
        physical = physical_value(chosen)
        if physical < gain - d:
            raise ArithmeticError("Replayed physical schedule falls below its source witness")
        if physical > best_value:
            best_value, best_locks, best_cost = physical, chosen, cost
        # Every feasible path has floor-rounded value at most 'rounded'.
        # Rounding loses at most one unit per edge. The physical reward is integral.
        upper = min(raw_cap, (len(vertices) - 1) * largest, int((rounded + path_length) * unit)) - d
        records.append(record | {"source_gain": gain, "physical": physical, "upper": upper, "status": "approximate"})

    upper = max(row["upper"] for row in records)
    if not best_value <= upper:
        raise ArithmeticError("Failed to bound the physical optimum")
    return {"lower": best_value, "upper": upper, "baseline": baseline, "witness": best_locks, "cost": best_cost,
            "eta": str(eta), "clock_certificates": records}
