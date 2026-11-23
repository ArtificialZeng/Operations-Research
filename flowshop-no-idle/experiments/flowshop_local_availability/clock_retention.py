"""Select as few machine clock vectors as possible for budget-wide makespan accuracy."""

from dataclasses import dataclass
from itertools import accumulate

from local_timing import deletion_problem, guarded_envelopes


@dataclass(frozen=True)
class ClockCut:
    locks: frozenset[int]
    clocks: frozenset[int]
    full_makespan: int


@dataclass(frozen=True)
class RetentionCertificate:
    retained: frozenset[int]
    cuts: tuple[ClockCut, ...]


def terminal_clock_terms(machines, job_ready, locked):
    """Return the terminal contribution of the entry vector and of each local vector."""
    tail = [None] * (len(job_ready) - 1) + [0]
    terms = []
    for i in reversed(range(len(machines))):
        machine = machines[i]
        end_weights = [None if value is None else value + duration
                       for duration, value in zip(machine.duration_prefix, tail, strict=True)]
        # The last job always has a path to the terminal completion.
        if i in locked:
            peak = max(value for value in end_weights if value is not None)
            influence = [peak] * len(tail)
        else:
            last = end_weights[-1]
            reverse_weights = (last if value is None else value for value in reversed(end_weights))
            influence = list(accumulate(reverse_weights, max))[::-1]
        terms.append(max(bound + weight for bound, weight in zip(machine.absolute_clock, influence, strict=True)))
        tail = [weight - offset for weight, offset in zip(influence, machine.upstream_offset, strict=True)]
    entry = max(ready + weight for ready, weight in zip(job_ready, tail, strict=True))
    return entry, tuple(reversed(terms))


def coverage_order(clocks, uncovered):
    return sorted(clocks, key=lambda clock: (-sum(clock in cut for cut in uncovered), clock))


def minimum_hitting_set(cuts):
    """Solve the accumulated cardinality master by exact branch and bound."""
    uncovered = tuple(sorted(set(cuts), key=lambda cut: (len(cut), tuple(sorted(cut)))))
    if uncovered and not uncovered[0]:
        raise ValueError("An empty cut cannot be hit")
    remaining = uncovered
    greedy = set()
    while remaining:
        clock = coverage_order(frozenset().union(*remaining), remaining)[0]
        greedy.add(clock)
        remaining = tuple(cut for cut in remaining if clock not in cut)
    best = frozenset(greedy)

    stack = [(frozenset(), uncovered)]
    while stack:
        retained, remaining = stack.pop()
        if not remaining:
            if len(retained) < len(best):
                best = retained
            continue
        disjoint_clocks = set()
        lower = len(retained)
        for cut in remaining:
            if disjoint_clocks.isdisjoint(cut):
                disjoint_clocks.update(cut)
                lower += 1
        if lower >= len(best):
            continue
        for clock in reversed(coverage_order(remaining[0], remaining)):
            stack.append((retained | {clock}, tuple(cut for cut in remaining if clock not in cut)))
    return best


def minimum_clock_retention(model, costs, budget, *, protected=(), maximum_loss=0):
    """Return a minimum retained set and scenario cuts certifying its cardinality."""
    if type(maximum_loss) is not int or maximum_loss < 0:
        raise ValueError("Expected a nonnegative integer makespan tolerance")
    if type(budget) is not int or budget < 0 or any(type(price) is not int or price < 0 for price in costs.values()):
        raise ValueError("Expected nonnegative integer costs and budget")
    all_clocks = frozenset(range(len(model.machines)))
    protected = frozenset(protected)
    if not protected <= all_clocks:
        raise ValueError("Protected clocks must denote real machine indices")

    cuts = []
    while True:
        retained = protected | minimum_hitting_set(cut.clocks for cut in cuts)
        query = deletion_problem(model, costs, budget, all_clocks - retained)
        locks = guarded_envelopes(query, budget, maximum_loss + 1)
        if locks is None:
            return RetentionCertificate(retained, tuple(cuts))
        entry, terms = terminal_clock_terms(model.machines, model.job_ready, set(model.compulsory) | locks)
        full = max(entry, max(terms))
        threshold = full - maximum_loss
        supporting = frozenset(i for i, term in enumerate(terms) if term >= threshold)
        if entry >= threshold or not supporting or not supporting.isdisjoint(retained):
            raise RuntimeError("Deletion witness does not violate the proposed retained set")
        cuts.append(ClockCut(locks, supporting, full))
