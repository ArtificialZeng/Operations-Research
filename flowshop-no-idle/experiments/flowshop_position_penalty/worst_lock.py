"""Exact worst added lock set at fixed permutation and cardinality budget."""

from itertools import accumulate
from operator import index


def prefix_winners(values):
    best = 0
    winners = []
    for slot, value in enumerate(values):
        if value > values[best]:
            best = slot
        winners.append(best)
    return winners


def strict_suffix_winners(values):
    best = None
    winners = [None] * len(values)
    for slot in reversed(range(len(values))):
        winners[slot] = best
        if best is None or values[slot] >= values[best]:
            best = slot
    return winners


def worst_lock_set(times, locked, eligible, budget, *, lock_costs=None):
    """Return the worst makespan, paid locks and path under an integer budget.

    New locks cost one by default. If provided, lock_costs maps each eligible
    unlocked machine to its positive integer cost.
    """
    budget = index(budget)
    if budget < 0:
        raise ValueError("budget must be nonnegative")
    costs = {
        machine: 1 if lock_costs is None else index(lock_costs[machine])
        for machine in range(len(times))
        if machine in eligible and machine not in locked
    }
    if any(cost <= 0 for cost in costs.values()):
        raise ValueError("new lock costs must be positive")
    budget = min(budget, sum(costs.values()))
    jobs = len(times[0])
    values = [[0] * jobs for _ in range(budget + 1)]
    machine_predecessors = []

    for machine, durations in enumerate(times):
        prefix = list(accumulate(durations, initial=0))
        centered = [
            [value - prefix[slot] for slot, value in enumerate(by_slot)]
            for by_slot in values
        ]
        next_values = []
        predecessors = []
        cost = costs.get(machine)
        for remaining, current in enumerate(centered):
            prefix_choices = prefix_winners(current)
            if machine in locked:
                prefix_choices = [prefix_choices[-1]] * jobs

            if cost is not None and remaining >= cost:
                lower_budget = centered[remaining - cost]
                suffix_choices = strict_suffix_winners(lower_budget)
            else:
                suffix_choices = [None] * jobs

            best_values = []
            best_predecessors = []
            for slot, (before, backward) in enumerate(zip(prefix_choices, suffix_choices)):
                best = current[before]
                predecessor = (before, remaining, False)
                if backward is not None and lower_budget[backward] > best:
                    best = lower_budget[backward]
                    predecessor = (backward, remaining - cost, True)
                best_values.append(prefix[slot + 1] + best)
                best_predecessors.append(predecessor)
            next_values.append(best_values)
            predecessors.append(best_predecessors)
        values = next_values
        machine_predecessors.append(predecessors)

    slot = jobs - 1
    remaining = budget
    added = []
    path = [slot]
    for machine in reversed(range(len(times))):
        slot, remaining, used_lock = machine_predecessors[machine][remaining][slot]
        path.append(slot)
        if used_lock:
            added.append(machine)
    return {
        "makespan": values[budget][-1],
        "additional_locks_0indexed": list(reversed(added)),
        "job_positions_0indexed": list(reversed(path)),
    }
