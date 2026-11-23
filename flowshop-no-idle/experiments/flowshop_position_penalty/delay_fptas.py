"""Budgeted longest path approximation with a relative extra-delay guarantee."""

from fractions import Fraction
from itertools import accumulate
from operator import index
from pathlib import Path
from runpy import run_path


_reference = run_path(str(Path(__file__).with_name("verify.py")))
_direct_makespan = _reference["direct_makespan"]


def all_enabled_heads(prefixes, enabled):
    jobs = len(prefixes[0]) - 1
    heads = [[0] * jobs]
    for machine, prefix in enumerate(prefixes):
        centered = [
            arrival - prefix[slot] for slot, arrival in enumerate(heads[-1])
        ]
        starts = (
            [max(centered)] * jobs if machine in enabled else accumulate(centered, max)
        )
        heads.append([load + start for load, start in zip(prefix[1:], starts)])
    return heads


def approximate_delay(times, locked, costs, budget, epsilon):
    """Return a feasible lock set and its certified weighted delay approximation."""
    epsilon = Fraction(epsilon)
    budget = index(budget)
    if not 0 < epsilon < 1 or budget < 0:
        raise ValueError("Require 0 < epsilon < 1 and a nonnegative budget.")
    costs = {machine: index(cost) for machine, cost in costs.items()}
    if any(cost <= 0 for cost in costs.values()):
        raise ValueError("New lock costs must be positive integers.")
    machines, jobs = len(times), len(times[0])
    eligible = {
        machine: cost for machine, cost in costs.items()
        if machine not in locked and cost <= budget
    }
    prefixes = [tuple(accumulate(row, initial=0)) for row in times]
    baseline = _direct_makespan(times, locked)
    lower = max(
        (_direct_makespan(times, locked | {machine}) - baseline for machine in eligible),
        default=0,
    )
    heads = all_enabled_heads(prefixes, locked | set(eligible))
    ceiling = heads[-1][-1]
    assert 0 <= ceiling - baseline <= len(eligible) * lower
    if lower == 0:
        return {
            "baseline": baseline,
            "lower_single_lock": 0,
            "loss_cap": 0,
            "additional_locks": [],
            "makespan": baseline,
            "path_weight": baseline,
        }

    scale = epsilon * lower / machines
    cap = (ceiling - baseline) * scale.denominator // scale.numerator
    # costs_at[j][q] is the cheapest exact lock cost to reach j at rounded loss q.
    costs_at = [{0: 0} for _ in range(jobs)]
    history = []
    for machine, prefix in enumerate(prefixes):
        next_costs = [{} for _ in range(jobs)]
        predecessors = {}
        for incoming, previous_costs in enumerate(costs_at):
            for outgoing in range(jobs):
                added = incoming > outgoing and machine not in locked
                if added and machine not in eligible:
                    continue
                edge_cost = eligible[machine] if added else 0
                weight = prefix[outgoing + 1] - prefix[incoming]
                length = heads[machine + 1][outgoing] - heads[machine][incoming] - weight
                assert length >= 0
                edge_loss = length * scale.denominator // scale.numerator
                for old_loss, old_cost in previous_costs.items():
                    loss = old_loss + edge_loss
                    cost = old_cost + edge_cost
                    if loss > cap or cost > budget:
                        continue
                    cheapest = next_costs[outgoing].get(loss)
                    if cheapest is None or cheapest > cost:
                        next_costs[outgoing][loss] = cost
                        predecessors[outgoing, loss] = (incoming, old_loss, added, weight)
        costs_at = next_costs
        history.append(predecessors)

    slot, q = jobs - 1, min(costs_at[-1])
    lock_set = []
    path_weight = 0
    for machine in reversed(range(machines)):
        slot, q, added, weight = history[machine][slot, q]
        path_weight += weight
        if added:
            lock_set.append(machine)
    lock_set.reverse()
    assert sum(eligible[machine] for machine in lock_set) <= budget
    achieved = _direct_makespan(times, locked | set(lock_set))
    assert achieved >= path_weight
    return {
        "baseline": baseline,
        "lower_single_lock": lower,
        "loss_cap": cap,
        "additional_locks": lock_set,
        "makespan": achieved,
        "path_weight": path_weight,
    }
