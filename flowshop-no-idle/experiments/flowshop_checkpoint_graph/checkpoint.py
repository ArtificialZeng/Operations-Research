"""Collapse fixed-order no-idle constraints to machine checkpoint transitions."""

from dataclasses import dataclass
from fractions import Fraction
from itertools import accumulate


@dataclass(frozen=True)
class CheckpointGraph:
    baseline: int | Fraction
    anchored: frozenset
    start_potential: tuple
    incoming: tuple


def checkpoint_graph(times, locked):
    """Return baseline and nonnegative net-delay arcs for fixed ordered jobs."""
    machines = len(times)
    anchored = frozenset(locked) | {0, machines - 1}
    prefixes = [tuple(accumulate(row, initial=0)) for row in times]
    heads = [0] * len(times[0])
    potential = []
    for i, prefix in enumerate(prefixes):
        starts = [arrival - load for arrival, load in zip(heads, prefix)]
        start = max(starts)
        potential.append(start)
        free_starts = [start] * len(heads) if i in anchored else accumulate(starts, max)
        heads = [load + start for load, start in zip(prefix[1:], free_starts)]
    baseline = heads[-1]

    incoming = [[] for _ in range(machines)]
    previous_anchor = 0
    for next_anchor in sorted(anchored - {0}):
        for i in range(previous_anchor, next_anchor):
            arrivals = prefixes[i][1:]
            for j in range(i + 1, next_anchor + 1):
                prefix = prefixes[j]
                starts = [arrival - load for arrival, load in zip(arrivals, prefix)]
                offset = max(starts)
                gain = potential[i] + offset - potential[j]
                assert gain >= 0
                incoming[j].append((i, gain))
                arrivals = [load + start for load, start in zip(prefix[1:], accumulate(starts, max))]
        previous_anchor = next_anchor
    return CheckpointGraph(baseline, anchored, tuple(potential), tuple(map(tuple, incoming)))


def path_gain(graph, added):
    value = 0
    ordered = sorted(graph.anchored | set(added))
    for left, right in zip(ordered, ordered[1:]):
        value += dict(graph.incoming[right])[left]
    return value


def checkpoint_exact(graph, costs, budget):
    """Exact positive-increment budgeted path using explicit Pareto fronts."""
    fronts = {0: [(0, 0, 0)]}
    peak = retained = 1
    for j, incoming in enumerate(graph.incoming[1:], start=1):
        required = j in graph.anchored
        price = 0 if required else costs.get(j)
        if price is None or price > budget:
            continue
        cutoff = budget - price
        paid = 0 if required else 1 << j
        possibilities = {}
        for i, gain in incoming:
            for cost, delay, mask in fronts.get(i, ()):
                if cost > cutoff:
                    break
                total_cost = cost + price
                candidate = (delay + gain, mask | paid)
                current = possibilities.get(total_cost)
                if current is None or candidate[0] > current[0]:
                    possibilities[total_cost] = candidate
        front = []
        for cost, (delay, mask) in sorted(possibilities.items()):
            if not front or delay > front[-1][1]:
                front.append((cost, delay, mask))
        fronts[j] = front
        peak = max(peak, len(front))
        retained += len(front)

    cost, delay, mask = fronts[len(graph.incoming) - 1][-1]
    witness = [i for i in range(len(graph.incoming)) if mask >> i & 1]
    return {"makespan": graph.baseline + delay, "delay": delay, "cost": cost,
            "witness": witness, "peak_frontier": peak, "retained_labels": retained}
