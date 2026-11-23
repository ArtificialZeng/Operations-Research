"""Verify clock retention against direct operation simulation and exhaustive subsets."""

import argparse
from itertools import combinations
import json
from pathlib import Path
import random

from validate import compile_problem, makespan_only_case, randomized_problem, simulate_operations
from clock_retention import minimum_clock_retention, minimum_hitting_set, terminal_clock_terms
from local_timing import preprocess_clock_deletions


def subsets(elements):
    items = sorted(elements)
    for size in range(len(items) + 1):
        yield from map(frozenset, combinations(items, size))


def sampled_problem(rng, m, n, trial):
    raw = randomized_problem(rng, m, n)
    if trial % 3 == 0:
        for key, rows in raw.items():
            if isinstance(rows[0], int):
                raw[key] = [value // 10 for value in rows]
            else:
                raw[key] = [[value // 10 for value in row] for row in rows]
    if trial % 4 == 0:
        raw["job_ready"] = [ready + 150 for ready in raw["job_ready"]]
    return raw


def greedy_retention(clocks, protected, preserves, order):
    retained = clocks
    for clock in order:
        if clock not in protected and preserves(retained - {clock}):
            retained -= {clock}
    return retained


def direct_checks():
    rng = random.Random(20261122091)
    counts = {"models": 160, "queries": 0, "source_terms": 0, "source_decompositions": 0,
              "retention_sets_tested": 0, "cuts": 0, "multi_clock_cuts": 0, "protected_queries": 0,
              "positive_tolerances": 0, "maximum_cuts": 0}
    for trial in range(counts["models"]):
        m, n = rng.randint(1, 7), rng.randint(1, 5)
        clocks = frozenset(range(m))
        raw = sampled_problem(rng, m, n, trial)
        machines = compile_problem(raw)
        releases = raw["job_ready"]
        fixed = frozenset(i for i in clocks if rng.random() < 0.15)
        protected = frozenset(i for i in clocks if trial % 2 and rng.random() < 0.25)
        costs = {i: rng.randrange(6) for i in clocks - fixed if rng.random() < 0.85}
        model = preprocess_clock_deletions(machines, releases, fixed)
        scenario_cost = {locks: sum(costs[i] for i in locks) for locks in subsets(costs)}
        full = {locks: simulate_operations(raw, fixed | locks) for locks in scenario_cost}
        by_source = {}
        for locks in scenario_cost:
            active = fixed | locks
            independent = tuple(simulate_operations(raw, active, source) for source in range(-1, m))
            entry, terms = terminal_clock_terms(machines, releases, active)
            assert (entry, *terms) == independent and max(independent) == full[locks]
            by_source[locks] = independent
            counts["source_terms"] += m + 1
            counts["source_decompositions"] += 1

        budgets = {0, rng.randint(0, sum(costs.values())), sum(costs.values())}
        for budget in sorted(budgets):
            eligible = [locks for locks, fee in scenario_cost.items() if fee <= budget]
            tolerance = (0, 1, 5)[(trial + budget) % 3]

            def preserves(retained):
                return all(full[locks] - max(by_source[locks][i + 1] for i in {-1, *retained}) <= tolerance
                           for locks in eligible)

            retained_sets = [protected | extra for extra in subsets(clocks - protected)]
            expected = next(retained for retained in retained_sets if preserves(retained))
            certificate = minimum_clock_retention(model, costs, budget, protected=protected, maximum_loss=tolerance)
            assert len(certificate.retained) == len(expected) and protected <= certificate.retained
            assert preserves(certificate.retained)
            retained_entries = {(i, j) for i in certificate.retained for j in range(n)}
            for locks in eligible:
                reduced = simulate_operations(raw, fixed | locks, clocks=retained_entries)
                assert full[locks] - reduced <= tolerance
            for cut in certificate.cuts:
                assert cut.locks in eligible and full[cut.locks] == cut.full_makespan
                floor = cut.full_makespan - tolerance
                assert by_source[cut.locks][0] < floor
                assert cut.clocks == {i for i in clocks if by_source[cut.locks][i + 1] >= floor}
                assert cut.clocks & certificate.retained
            witnesses = [cut.clocks for cut in certificate.cuts]
            assert min(len(retained) for retained in retained_sets if all(retained & cut for cut in witnesses)) == len(expected)

            counts["queries"] += 1
            counts["cuts"] += len(witnesses)
            counts["multi_clock_cuts"] += sum(len(cut) > 1 for cut in witnesses)
            counts["maximum_cuts"] = max(counts["maximum_cuts"], len(witnesses))
            counts["protected_queries"] += bool(protected)
            counts["positive_tolerances"] += tolerance > 0
            counts["retention_sets_tested"] += len(retained_sets)
    return counts


def master_checks():
    rng = random.Random(20261122092)
    trials = 240
    try:
        minimum_hitting_set([frozenset()])
    except ValueError:
        pass
    else:
        raise AssertionError("The hitting-set master accepted an impossible cut")
    for _ in range(trials):
        clocks = set(range(rng.randint(1, 10)))
        cuts = [frozenset(rng.sample(sorted(clocks), rng.randint(1, len(clocks)))) for _ in range(rng.randrange(13))]
        expected = next(chosen for chosen in subsets(clocks) if all(chosen & cut for cut in cuts))
        found = minimum_hitting_set(cuts)
        assert len(found) == len(expected) and all(found & cut for cut in cuts)
    return trials


def overlapping_clock_supports():
    zero = [[0, 0] for _ in range(5)]
    raw = {"processing": [[6, 2], [3, 6], [4, 2], [1, 1], [6, 1]], "job_ready": [0, 0],
           "machine_ready": [0, 100, 100, 107, 0],
           "material_ready": [[0, 0], [100, 106], [108, 105], [112, 110], [0, 0]],
           "setup": zero, "setup_ready": zero, "transfer": zero, "lead": zero}
    machines = compile_problem(raw)
    fixed, costs, budget = frozenset(), {3: 1}, 1
    all_clocks = frozenset(range(len(machines)))
    scenarios = (frozenset(), frozenset({3}))
    originals = [simulate_operations(raw, locks) for locks in scenarios]
    assert originals == [120, 121]

    def preserves(retained):
        entries = {(i, t) for i in retained for t in range(2)}
        return [simulate_operations(raw, locks, clocks=entries) for locks in scenarios] == originals

    optimum = minimum_clock_retention(preprocess_clock_deletions(machines, raw["job_ready"], fixed), costs, budget)
    greedy = greedy_retention(all_clocks, fixed, preserves, [2, 0, 1, 3, 4])
    assert optimum.retained == {2} and greedy == {1, 3}
    cuts = []
    for locks, full in zip(scenarios, originals, strict=True):
        terms = [simulate_operations(raw, locks, source) for source in range(-1, len(machines))]
        assert terms[0] < full
        cuts.append([i for i in sorted(all_clocks) if terms[i + 1] == full])
    assert cuts == [[2, 3], [1, 2]]
    return {"problem": raw, "optional_lock": 3, "makespans": originals, "scenario_supports": cuts,
            "minimum_retained": sorted(optimum.retained), "greedy_retained": sorted(greedy)}


def retention_gap_checks():
    rng = random.Random(20261122094)
    counts = {"models": 96, "one_clock": 0, "two_clocks": 0, "encodings_checked": 0}
    for _ in range(counts["models"]):
        items = rng.randint(1, 6)
        profits = [2 * rng.randint(1, 16) for _ in range(items)]
        weights = [rng.randint(1, 14) for _ in range(items)]
        target = 2 * rng.randint(1, sum(profits) // 2 + 2)
        budget = rng.randint(0, sum(weights))
        scalar, material, costs, floor, base, shift = makespan_only_case(profits, weights, target)
        eligible = [choice for choice in subsets(range(items)) if sum(weights[i] for i in choice) <= budget]
        reaches = any(sum(profits[i] for i in choice) >= target for choice in eligible)
        terminal = len(scalar["processing"]) - 1
        needed = {0, terminal} if reaches else {terminal}
        for raw in (scalar, material):
            assert simulate_operations(raw, frozenset()) == floor > base + shift
            terminal_clock = {(terminal, t) for t in range(2)}
            entry_and_first = {(0, t) for t in range(2)}
            assert simulate_operations(raw, frozenset(), clocks=entry_and_first) < floor
            for choice in eligible:
                locks = {2 * i + 1 for i in choice}
                assert simulate_operations(raw, locks, clocks=terminal_clock) == floor
                assert simulate_operations(raw, locks) == max(floor, base + shift + sum(profits[i] for i in choice))
            model = preprocess_clock_deletions(compile_problem(raw), raw["job_ready"], frozenset())
            assert minimum_clock_retention(model, costs, budget).retained == needed
            counts["encodings_checked"] += 1
        counts["two_clocks" if reaches else "one_clock"] += 1
    return counts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = direct_checks() | {"hitting_set_instances": master_checks(),
                                "overlapping_clock_supports": overlapping_clock_supports(),
                                "cardinality_gap": retention_gap_checks()}
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
        f.write("\n")
    print(json.dumps({key: value for key, value in result.items() if isinstance(value, int)}))
