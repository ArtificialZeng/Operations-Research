"""Check baseline reduction and per-stage clock covers in a max-plus cascade."""

from itertools import combinations, product
import json
import random


def matrix(rng, size, extensive=False):
    return [[0 if extensive and i == j else rng.choice([None, -5, -1, 0, 2, 6])
             for j in range(size)] for i in range(size)]


def multiply(a, v):
    return tuple(max((coefficient + value for coefficient, value in zip(row, v)
                      if coefficient is not None and value is not None), default=float("-inf")) for row in a)


def stage_output(stage, upstream, kept, locked):
    a, b, tightening, clock = stage
    active = [value if j in kept else None for j, value in enumerate(clock)]
    before = tuple(map(max, multiply(a, upstream), multiply(b, active)))
    return multiply(tightening, before) if locked else before


def completions(stages, arrival, choices, retained):
    timeline = []
    for i, stage in enumerate(stages):
        keep_here = {j for row, j in retained if row == i}
        arrival = stage_output(stage, arrival, keep_here, i in choices)
        timeline.append(arrival)
    return timeline


def subsets(values):
    return [frozenset(items) for n in range(len(values) + 1) for items in combinations(values, n)]


def minimum_stage_cover(stage, upstream, desired, compulsory):
    all_clocks = range(len(stage[-1]))
    just_upstream = stage_output(stage, upstream, set(), compulsory)
    required = {j for j, (a, b) in enumerate(zip(just_upstream, desired)) if a < b}
    contacts = []
    for c in all_clocks:
        emitted = stage_output(stage, upstream, {c}, compulsory)
        contacts.append({j for j in required if emitted[j] == desired[j]})
    return next(keep for keep in subsets(all_clocks) if set().union(*(contacts[c] for c in keep)) == required)


def audit(cases=160):
    rng = random.Random(1795350904)
    counts = {"cascades": cases, "retention_sets": 0, "switch_patterns_replayed": 0,
              "safe_retention_sets": 0, "cover_optima_checked": 0}
    for _ in range(cases):
        m, n = rng.randint(1, 3), rng.randint(2, 3)
        stages = [(matrix(rng, n, True), matrix(rng, n), matrix(rng, n, True),
                   [rng.randint(0, 22) for _ in range(n)]) for _ in range(m)]
        arrival = [rng.randint(0, 16) for _ in range(n)]
        all_entries = frozenset(product(range(m), range(n)))
        fixed = {i for i in range(m) if rng.random() < 0.4}
        profiles = {choice: completions(stages, arrival, fixed | choice, all_entries)
                    for choice in subsets(sorted(set(range(m)) - fixed))}
        original = profiles[frozenset()]
        optimum = None
        for kept in subsets(sorted(all_entries)):
            base_matches = completions(stages, arrival, fixed, kept) == original
            if base_matches:
                for choice, reference in profiles.items():
                    assert completions(stages, arrival, fixed | choice, kept) == reference
                    counts["switch_patterns_replayed"] += 1
                optimum = len(kept) if optimum is None else min(optimum, len(kept))
                counts["safe_retention_sets"] += 1
            counts["retention_sets"] += 1
        stagewise = sum(len(minimum_stage_cover(stage, incoming, original[i], i in fixed))
                        for i, (stage, incoming) in enumerate(zip(stages, [arrival, *original[:-1]])))
        assert stagewise == optimum
        counts["cover_optima_checked"] += 1
    return counts


if __name__ == "__main__":
    print(json.dumps(audit()))
