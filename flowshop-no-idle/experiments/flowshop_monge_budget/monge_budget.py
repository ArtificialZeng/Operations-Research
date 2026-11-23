"""Exact paid-lock budget recurrence on a machine checkpoint graph."""

from collections import deque
from itertools import accumulate, pairwise


def build_graph(times, mandatory, locked_candidates):
    """Return earliest block-start differences with no other locks inside a block."""
    m = len(times)
    compulsory = sorted(set(mandatory) | {0, m - 1})
    promising = set(locked_candidates) | set(compulsory)
    arcs = {}
    for left, right in pairwise(compulsory):
        for start in range(left, right):
            if start not in promising:
                continue
            prev = list(accumulate(times[start]))
            for end in range(start + 1, right + 1):
                row = times[end]
                if end in promising:
                    prefix = accumulate(row, initial=0)
                    arc = max(value - offset for value, offset in zip(prev, prefix))
                    arcs[start, end] = arc
                if end != right:
                    finish = 0
                    current = []
                    for upper, proc in zip(prev, row):
                        finish = max(finish, upper) + proc
                        current.append(finish)
                    prev = current
    return compulsory, arcs, sum(times[-1])


class Envelope:
    """Rows arrive in increasing order and are considered only to their right."""

    def __init__(self, arcs, positions):
        self.arcs = arcs
        self.positions = positions
        self.first = deque()
        self.rows = deque()

    def value(self, row, target):
        return row[1] + self.arcs[row[0], self.positions[target]]

    def add(self, row, start):
        last = len(self.positions) - 1
        if start > last:
            return
        while self.rows:
            previous = self.rows[-1]
            lo = max(start, self.first[-1])
            # Monge means the new row's advantage is nondecreasing.
            if self.value(row, lo) >= self.value(previous, lo):
                self.rows.pop()
                self.first.pop()
                continue
            if self.value(row, last) < self.value(previous, last):
                return
            lo += 1
            hi = last
            while lo < hi:
                mid = (lo + hi) // 2
                if self.value(row, mid) >= self.value(previous, mid):
                    hi = mid
                else:
                    lo = mid + 1
            self.rows.append(row)
            self.first.append(lo)
            return
        self.rows.append(row)
        self.first.append(start)

    def best(self, target):
        while len(self.rows) >= 2 and self.first[1] <= target:
            self.rows.popleft()
            self.first.popleft()
        row = self.rows[0]
        return row[0], self.value(row, target)


def solve_graph(compulsory, arcs, tail, costs, budget, *, use_envelopes=True, constants=None, origin=0):
    allowed = set(costs) - set(compulsory)
    paid = {v: costs[v] for v in allowed if costs[v] <= budget}
    budget = min(budget, sum(paid.values()))
    frontier = {0: origin}
    parent = {}
    for begin, end in pairwise(compulsory):
        positions = [begin, *sorted(v for v in paid if begin < v < end), end]
        histories = {begin: frontier}
        envelopes = {}
        earliest = {}

        def add(v, scores, start):
            for spent, value in scores.items():
                hull = envelopes.get(spent)
                if hull is None:
                    hull = envelopes[spent] = Envelope(arcs, positions)
                    earliest[spent] = v
                hull.add((v, value), start)

        if use_envelopes:
            add(begin, frontier, 1)
        for slot, j in enumerate(positions[1:], 1):
            charge = paid.get(j, 0)
            scores = {}
            if use_envelopes:
                for spent, hull in envelopes.items():
                    if spent + charge <= budget:
                        i, value = hull.best(slot)
                        if constants is not None:
                            first = earliest[spent]
                            if constants[first, j] > value:
                                i, value = first, constants[first, j]
                        scores[spent + charge] = value
                        parent[j, spent + charge] = (i, spent)
            else:
                for i, row in histories.items():
                    edge = arcs[i, j]
                    for spent, value in row.items():
                        amount = spent + charge
                        candidate = value + edge
                        if constants is not None:
                            candidate = max(candidate, constants[i, j])
                        if amount <= budget and (amount not in scores or candidate > scores[amount]):
                            scores[amount] = candidate
                            parent[j, amount] = (i, spent)
            if j == end:
                frontier = scores
            elif use_envelopes:
                add(j, scores, slot + 1)
            else:
                histories[j] = scores

    spent, best = max(frontier.items(), key=lambda pair: (pair[1], -pair[0]))
    vertex, paid_total = compulsory[-1], spent
    locks = []
    while vertex != compulsory[0]:
        if vertex in paid:
            locks.append(vertex)
        vertex, spent = parent[vertex, spent]
    return {"objective": best + tail, "cost": paid_total, "added": sorted(locks), "states": len(parent)}
