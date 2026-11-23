"""Independently enumerate schedules with local dates and compare certificates."""

import argparse
from fractions import Fraction
from itertools import combinations, pairwise
import json
from pathlib import Path
import random
from statistics import median
from time import process_time

from local_timing import (all_clocks_redundant, approximate, arbitrary_clock_error, arbitrary_clock_witness,
                          checkpoint_graph, compile_machines, deletion_problem, evaluate, exact,
                          guarded_path, maximum_deletion_error, minimum_clock_support, preprocess_clock_deletions,
                          suffix_clock_error, suffix_clock_witness)
from monge_budget import solve_graph
from release_dates import simulate as former_model


def simulate_operations(problem, locked, source=None, *, profile=False, clocks=None):
    """Use operation start times directly, including for isolated sources."""
    unavailable = float("-inf")
    previous = problem["job_ready"] if source in (None, -1) else [unavailable] * len(problem["job_ready"])
    timeline = []
    for i, processing in enumerate(problem["processing"]):
        absolute = source is None or source == i
        offset, required, lengths = 0, [], []
        for t, duration in enumerate(processing):
            material = previous[t] + problem["transfer"][i][t]
            ready = setup_ready = unavailable
            if absolute and (clocks is None or (i, t) in clocks):
                ready = problem["machine_ready"][i]
                material = max(material, problem["material_ready"][i][t])
                setup_ready = problem["setup_ready"][i][t]
            release = max(ready, material - problem["lead"][i][t], setup_ready)
            required.append(release)
            lengths.append(duration + problem["setup"][i][t])
        finishes = []
        if i in locked:
            start = unavailable
            for release, length in zip(required, lengths):
                start = max(start, release - offset)
                offset += length
            current = start
            for length in lengths:
                current += length
                finishes.append(current)
        else:
            current = unavailable
            for release, length in zip(required, lengths):
                current = max(current, release) + length
                finishes.append(current)
        previous = finishes
        if profile:
            timeline.append(tuple(finishes))
    if profile:
        return timeline
    return int(previous[-1])


def compile_problem(problem):
    return compile_machines(**{name: values for name, values in problem.items() if name != "job_ready"})


def randomized_problem(rng, machines, jobs):
    def sample_matrix(high):
        return [[rng.randint(0, high) for _ in range(jobs)] for _ in range(machines)]

    setup = sample_matrix(16)
    return {"processing": sample_matrix(22), "setup": setup, "machine_ready": [rng.randint(0, 120) for _ in range(machines)],
            "job_ready": [rng.randint(0, 100) for _ in range(jobs)], "material_ready": sample_matrix(170),
            "setup_ready": sample_matrix(110), "transfer": sample_matrix(21),
            "lead": [[rng.randint(0, s) for s in row] for row in setup]}


def graphs_equal(problem, machines, fixed, costs, known):
    (mandatory, a, tail), floors = checkpoint_graph(machines, problem["job_ready"], fixed, costs)
    anti_monge, ordered = 0, 0
    for left, right in pairwise(mandatory):
        positions = [p for p in range(left, right + 1) if p in costs or p in mandatory]
        for i, j, k, ell in combinations(positions, 4):
            assert a[i, k] + a[j, ell] >= a[i, ell] + a[j, k]
            anti_monge += 1
        for i, j, k in combinations(positions, 3):
            assert floors[i, k] >= floors[j, k]
            ordered += 1
    for selected, scores in known.items():
        start = 0
        for edge in pairwise(sorted(set(mandatory) | selected)):
            start = max(start + a[edge], floors[edge])
        assert start + tail == scores[0]
    return anti_monge, ordered


def stress():
    rng = random.Random(2026112207)
    totals = {"cases": 360, "subsets": 0, "source_evaluations": 0, "anti_monge_quadrangles": 0,
              "floor_order_triples": 0, "exact_budget_queries": 0, "approximation_certificates": 0,
              "relative_positive_checks": 0, "former_model_matches": 0}
    for trial in range(totals["cases"]):
        count, jobs = rng.randint(1, 9), rng.randint(1, 7)
        problem = randomized_problem(rng, count, jobs)
        if trial % 6 == 0:
            for key in ("material_ready", "setup_ready", "transfer"):
                problem[key] = [[0] * jobs for _ in range(count)]
            problem["lead"] = problem["setup"]
        machines = compile_problem(problem)
        fixed = {i for i in range(count - 1) if rng.random() < 0.21}
        costs = {i: rng.randint(1, 18) for i in range(count - 1) if i not in fixed and rng.random() > 0.17}
        subsets = [frozenset(group) for size in range(len(costs) + 1) for group in combinations(costs, size)]
        known = {}
        for chosen in subsets:
            marks = fixed | chosen
            reference = simulate_operations(problem, marks)
            source_values = [simulate_operations(problem, marks, k) for k in range(-1, count)]
            assert evaluate(machines, problem["job_ready"], marks) == reference == max(source_values)
            known[chosen] = (reference, source_values)
            if trial % 6 == 0:
                assert reference == former_model(problem["processing"], problem["setup"], problem["machine_ready"],
                                                 marks, job_release=problem["job_ready"])
                totals["former_model_matches"] += 1
        totals["subsets"] += len(known)
        totals["source_evaluations"] += len(known) * (count + 1)
        quad, triple = graphs_equal(problem, machines, fixed, costs, known)
        totals["anti_monge_quadrangles"] += quad
        totals["floor_order_triples"] += triple

        base, base_components = known[frozenset()]
        for budget in {0, rng.randint(0, sum(costs.values())), sum(costs.values())}:
            feasible = [scores for chosen, scores in known.items() if sum(costs[j] for j in chosen) <= budget]
            optimum = max(reference for reference, _ in feasible)
            objectives = [max(sources[h] for _, sources in feasible) for h in range(count + 1)]
            for use_envelopes in (False, True):
                solved = exact(machines, problem["job_ready"], fixed, costs, budget, use_envelopes=use_envelopes)
                assert solved["objective"] == optimum == known[frozenset(solved["added"])][0]
                assert sum(costs[j] for j in solved["added"]) == solved["cost"] <= budget
            totals["exact_budget_queries"] += 1
            for eta in (Fraction(1, 4), Fraction(1, 10)):
                certificate = approximate(machines, problem["job_ready"], fixed, costs, budget, eta)
                lower, upper = certificate["lower"], certificate["upper"]
                assert lower <= optimum - base <= upper
                witness = frozenset(certificate["witness"])
                assert lower == known[witness][0] - base
                assert sum(costs[j] for j in witness) == certificate["cost"] <= budget
                for h in certificate["clock_certificates"]:
                    index = h["clock"] + 1
                    assert h["baseline_contribution"] == base_components[index]
                    assert h["upper"] >= objectives[index] - base
                totals["approximation_certificates"] += 1
                if optimum > base:
                    gain = min(objective - beta for objective, beta in zip(objectives, base_components) if objective == optimum)
                    assert lower >= optimum - base - eta * gain
                    totals["relative_positive_checks"] += 1
    return totals


def first_machine_choice():
    problem = {"processing": [[1, 1], [100, 1]], "setup": [[0, 0], [0, 0]], "machine_ready": [0, 0],
               "job_ready": [0, 0], "material_ready": [[0, 10], [0, 0]], "setup_ready": [[0, 0], [0, 0]],
               "transfer": [[0, 0], [0, 0]], "lead": [[0, 0], [0, 0]]}
    machines = compile_problem(problem)
    baseline = simulate_operations(problem, frozenset())
    with_lock = simulate_operations(problem, {0})
    costs = {0: 1}
    assert [baseline, with_lock] == [102, 111]
    assert exact(machines, problem["job_ready"], set(), costs, 0)["objective"] == baseline
    assert exact(machines, problem["job_ready"], set(), costs, 1)["objective"] == with_lock
    assert approximate(machines, problem["job_ready"], set(), costs, 1, Fraction(1, 4))["lower"] == 9
    deletion = preprocess_clock_deletions(machines, problem["job_ready"], set())
    for envelopes in (False, True):
        assert maximum_deletion_error(deletion, {0: 0}, 0, {0}, use_envelopes=envelopes) == (9, frozenset({0}))
    assert simulate_operations(problem, set(), -1) == baseline
    assert simulate_operations(problem, {0}, -1) == baseline
    assert not all_clocks_redundant(machines, problem["job_ready"], set())
    return {"input": problem, "idle_permitted": baseline, "paid_no_idle": with_lock,
            "job_source_only_both_modes": baseline}


def redundancy_checks():
    rng = random.Random(2026112243)
    checked = 0
    counts = {"positive": 0, "negative": 0}
    for index in range(120):
        count, jobs = rng.randint(1, 8), rng.randint(1, 7)
        problem = randomized_problem(rng, count, jobs)
        if index % 2 == 0:
            problem["job_ready"] = [t + 200 for t in problem["job_ready"]]
        fixed = {i for i in range(count) if rng.random() < 0.2}
        optional = sorted(set(range(count)) - fixed)
        cert = all_clocks_redundant(compile_problem(problem), problem["job_ready"], fixed)
        observed = True
        for size in range(len(optional) + 1):
            for choice in combinations(optional, size):
                locked = fixed | set(choice)
                full = simulate_operations(problem, locked, profile=True)
                homogeneous = simulate_operations(problem, locked, -1, profile=True)
                observed = observed and full == homogeneous
                checked += 1
        assert cert == observed
        counts["positive" if cert else "negative"] += 1
    return {"cases": sum(counts.values()), "subsets": checked, **counts}


def support_checks():
    rng = random.Random(2026112244)
    counts = {"cases": 72, "candidate_supports": 0, "witness_profiles": 0, "original_entries": 0, "retained_entries": 0}
    for trial in range(counts["cases"]):
        rows, cols = rng.randint(1, 3), rng.randint(1, 3)
        problem = randomized_problem(rng, rows, cols)
        if trial % 3 == 0:
            problem["job_ready"] = [v + 100 for v in problem["job_ready"]]
        fixed = {i for i in range(rows) if rng.random() < 0.4}
        support = set(minimum_clock_support(compile_problem(problem), problem["job_ready"], fixed))
        baseline = simulate_operations(problem, fixed, profile=True)
        positions = [(i, t) for i in range(rows) for t in range(cols)]
        for size in range(len(support)):
            for choice in combinations(positions, size):
                assert simulate_operations(problem, fixed, profile=True, clocks=set(choice)) != baseline
                counts["candidate_supports"] += 1
        optional = sorted(set(range(rows)) - fixed)
        for size in range(len(optional) + 1):
            for choice in combinations(optional, size):
                locked = fixed | set(choice)
                assert simulate_operations(problem, locked, profile=True, clocks=support) == simulate_operations(
                    problem, locked, profile=True)
                counts["witness_profiles"] += 1
        counts["original_entries"] += rows * cols
        counts["retained_entries"] += len(support)
    return counts


def makespan_only_case(profit, weight, target):
    items = len(profit)
    processing = [[1, profit[0] + 1]]
    for value, following in zip(profit, profit[1:] + [0]):
        processing.extend(([1, 1], [value + 1, following + 1]))
    rows = len(processing)
    shift = 1 + sum(profit)
    unconstrained = 2 * items + 2 + sum(profit)
    floor = unconstrained + shift + target - 1
    terminal_date = floor - sum(processing[-1])
    none = [[0, 0] for _ in range(rows)]
    setup = {"processing": processing, "setup": none, "job_ready": [0, 0], "setup_ready": none,
             "transfer": none, "lead": none}
    scalar = setup | {"machine_ready": [shift, *([0] * (rows - 2)), terminal_date], "material_ready": none}
    material = setup | {"machine_ready": [0] * rows,
                        "material_ready": [[shift, 0], *([[0, 0]] * (rows - 2)), [terminal_date, 0]]}
    position_costs = {2 * j + 1: fee for j, fee in enumerate(weight)}
    return scalar, material, position_costs, floor, unconstrained, shift


def makespan_only_knapsack_checks():
    rng = random.Random(2026112251)
    counts = {"cases": 144, "budget_feasible_sets": 0, "both_encodings_per_set": 0,
              "removal_changes_at_least_one_set": 0, "removal_safe_for_all_sets": 0}
    for _ in range(counts["cases"]):
        items = rng.randint(1, 7)
        profit = [rng.randint(1, 22) for _ in range(items)]
        weight = [rng.randint(1, 18) for _ in range(items)]
        budget = rng.randint(0, sum(weight))
        target = rng.randint(1, sum(profit) + 2)
        scalar, material, position_costs, floor, unconstrained, shift = makespan_only_case(profit, weight, target)
        deleted_scalar = scalar | {"machine_ready": [0, *scalar["machine_ready"][1:]]}
        deleted_material = material | {"material_ready": [[0, 0], *material["material_ready"][1:]]}
        changes = False
        for size in range(items + 1):
            for chosen in combinations(range(items), size):
                if sum(weight[j] for j in chosen) > budget:
                    continue
                paid = {2 * j + 1 for j in chosen}
                value = sum(profit[j] for j in chosen)
                assert simulate_operations(deleted_scalar, paid) == simulate_operations(deleted_material, paid) == floor
                expected = max(floor, unconstrained + shift + value)
                assert simulate_operations(scalar, paid) == simulate_operations(material, paid) == expected
                assert (expected > floor) == (value >= target)
                changes = changes or expected > floor
                counts["budget_feasible_sets"] += 1
                counts["both_encodings_per_set"] += 2
        for encoding in (scalar, material):
            witness = arbitrary_clock_witness(compile_problem(encoding), encoding["job_ready"], set(),
                                              position_costs, budget, {0})
            assert (witness is not None) == changes
            if witness is not None:
                assert sum(position_costs[j] for j in witness) <= budget
                assert sum(profit[(j - 1) // 2] for j in witness) >= target
        counts["removal_changes_at_least_one_set" if changes else "removal_safe_for_all_sets"] += 1
    return counts


def suffix_clock_checks():
    rng = random.Random(2026112257)
    counts = {"cases": 230, "budget_cut_queries": 0, "feasible_sets_compared": 0,
              "safe_suffix_queries": 0, "empty_witnesses": 0, "singleton_witnesses": 0}
    for trial in range(counts["cases"]):
        m, n = rng.randint(1, 8), rng.randint(1, 6)
        problem = randomized_problem(rng, m, n)
        # Mix highly binding clocks, nonbinding clocks, and clocks hidden in the terminal makespan.
        if trial % 3 == 0:
            problem["job_ready"] = [value + 100 for value in problem["job_ready"]]
        if trial % 3 == 1:
            problem["processing"][-1][0] += 150
        model = compile_problem(problem)
        fixed = {i for i in range(m - 1) if rng.random() < 0.2}
        costs = {i: rng.randint(1, 14) for i in range(m - 1) if i not in fixed and rng.random() < 0.8}
        subsets = [frozenset(choice) for k in range(len(costs) + 1) for choice in combinations(costs, k)]
        original = {s: simulate_operations(problem, fixed | s) for s in subsets}
        full_cost = sum(costs.values())
        budgets = {0, rng.randint(0, full_cost), full_cost}
        for cut in {0, rng.randint(0, m), m - 1, m}:
            retained = {(i, t) for i in range(cut) for t in range(n)}
            without_suffix = {s: simulate_operations(problem, fixed | s, clocks=retained) for s in subsets}
            for budget in budgets:
                eligible = [s for s in subsets if sum(costs[i] for i in s) <= budget]
                expected = max(original[s] - without_suffix[s] for s in eligible)
                maximum, witness = suffix_clock_error(model, problem["job_ready"], fixed, costs, budget, cut)
                assert maximum == expected
                assert (witness is not None) == (expected > 0)
                if witness is None:
                    counts["safe_suffix_queries"] += 1
                else:
                    assert witness in eligible and original[witness] - without_suffix[witness] == maximum
                    assert len(witness) <= 1
                    counts["singleton_witnesses" if witness else "empty_witnesses"] += 1
                counts["feasible_sets_compared"] += len(eligible)
                counts["budget_cut_queries"] += 1

    hidden = {"processing": [[1, 1], [1, 1], [100, 1]], "setup": [[0, 0]] * 3, "machine_ready": [0] * 3,
              "job_ready": [0, 3], "material_ready": [[0, 0], [0, 10], [0, 0]], "setup_ready": [[0, 0]] * 3,
              "transfer": [[0, 0]] * 3, "lead": [[0, 0]] * 3}
    model = compile_problem(hidden)
    assert not all_clocks_redundant(model, hidden["job_ready"], set())
    assert suffix_clock_witness(model, hidden["job_ready"], set(), {0: 1}, 1) is None
    assert [simulate_operations(hidden, s) for s in (set(), {0})] == [103, 105]
    assert [simulate_operations(hidden, s, -1) for s in (set(), {0})] == [103, 105]
    original = first_machine_choice()["input"]
    assert suffix_clock_witness(compile_problem(original), original["job_ready"], set(), {0: 1}, 1) == {0}
    return counts | {"intermediate_change_only_example": hidden}


def arbitrary_clock_checks():
    rng = random.Random(2026112267)
    counts = {"cases": 270, "budget_deletion_queries": 0, "feasible_sets_compared": 0,
              "deletions_preserving_makespan": 0, "empty_witnesses": 0, "singleton_witnesses": 0,
              "larger_witnesses": 0, "uniform_guard_bounds": 0, "baseline_starts_checked": 0}
    for trial in range(counts["cases"]):
        m, n = rng.randint(1, 9), rng.randint(1, 6)
        problem = randomized_problem(rng, m, n)
        if trial % 2 == 0:
            problem["job_ready"] = [value + 110 for value in problem["job_ready"]]
        model = compile_problem(problem)
        fixed = {i for i in range(m) if rng.random() < 0.18}
        preprocessed = preprocess_clock_deletions(model, problem["job_ready"], fixed)
        costs = {i: rng.randint(1, 14) for i in range(m - 1) if i not in fixed and rng.random() < 0.8}
        subsets = [frozenset(choice) for k in range(len(costs) + 1) for choice in combinations(costs, k)]
        original = {s: simulate_operations(problem, fixed | s) for s in subsets}
        full_cost = sum(costs.values())
        budgets = {0, rng.randint(0, full_cost), full_cost}
        alternate = frozenset(range(trial % 2, m, 2))
        scattered = frozenset(i for i in range(m) if rng.random() < 0.55)
        for deleted in {frozenset(), frozenset({0}), alternate, scattered}:
            retained_machines = set(range(m)) - deleted
            retained = {(i, t) for i in range(m) if i not in deleted for t in range(n)}
            reduced = {s: simulate_operations(problem, fixed | s, clocks=retained) for s in subsets}
            _, old_floor = checkpoint_graph(model, problem["job_ready"], fixed, range(m), retained=retained_machines)
            query = deletion_problem(preprocessed, costs, full_cost, deleted)
            for j, start in enumerate(query.baseline_start):
                profile = simulate_operations(problem, fixed | {j}, clocks=retained, profile=True)
                assert start == profile[j][-1] - model[j].duration_prefix[-1]
                counts["baseline_starts_checked"] += 1
            for budget in budgets:
                eligible = [s for s in subsets if sum(costs[i] for i in s) <= budget]
                expected = max(original[s] - reduced[s] for s in eligible)
                query = deletion_problem(preprocessed, costs, budget, deleted)
                assert query.baseline_start[-1] + model[-1].duration_prefix[-1] == reduced[frozenset()]
                for (i, j), bound in old_floor.items():
                    if i in {-1, *query.fees} and j in query.fees and bound is not None:
                        assert bound <= query.baseline_start[j]
                        counts["uniform_guard_bounds"] += 1
                assert guarded_path(query, budget, expected + 1, reference_floor=old_floor) is None
                if expected:
                    reference = guarded_path(query, budget, expected, reference_floor=old_floor)
                    assert reference in eligible and original[reference] - reduced[reference] == expected
                maximum, witness = maximum_deletion_error(preprocessed, costs, budget, deleted, use_envelopes=False)
                optimized, alternative = maximum_deletion_error(preprocessed, costs, budget, deleted, use_envelopes=True)
                assert expected == maximum
                assert optimized == expected
                assert (witness is not None) == (expected > 0)
                assert (alternative is not None) == (expected > 0)
                if witness is None:
                    counts["deletions_preserving_makespan"] += 1
                else:
                    assert witness in eligible and original[witness] - reduced[witness] == maximum
                    assert alternative in eligible and original[alternative] - reduced[alternative] == maximum
                    label = ("empty_witnesses", "singleton_witnesses", "larger_witnesses")[min(2, len(witness))]
                    counts[label] += 1
                counts["feasible_sets_compared"] += len(eligible)
                counts["budget_deletion_queries"] += 1
    zeros = [[0, 0]] * 5
    example = {"processing": [[1, 3], [1, 1], [3, 4], [1, 1], [4, 1]], "setup": zeros,
               "job_ready": [0, 0], "machine_ready": [6, 0, 0, 0, 16],
               "material_ready": zeros, "setup_ready": zeros, "transfer": zeros, "lead": zeros}
    model = compile_problem(example)
    costs = {1: 1, 3: 1}
    retained = {(i, t) for i in range(1, 5) for t in range(2)}
    options = [set(), {1}, {3}, {1, 3}]
    full = [simulate_operations(example, choice) for choice in options]
    reduced = [simulate_operations(example, choice, clocks=retained) for choice in options]
    assert full == [21, 21, 21, 22] and reduced == [21, 21, 21, 21]
    assert arbitrary_clock_witness(model, example["job_ready"], set(), costs, 1, {0}) is None
    assert arbitrary_clock_witness(model, example["job_ready"], set(), costs, 2, {0}) == {1, 3}

    # Finite integers must never be converted to IEEE floating point arithmetic.
    scale = 10**400
    wide = {key: [scale * x for x in row] if key.endswith("ready") and isinstance(row[0], int)
            else [[scale * x for x in values] for values in row] for key, row in example.items()}
    model = compile_problem(wide)
    assert exact(model, wide["job_ready"], set(), costs, 2)["objective"] == 22 * scale
    assert suffix_clock_witness(model, wide["job_ready"], set(), costs, 1, 5) is None
    assert arbitrary_clock_witness(model, wide["job_ready"], set(), costs, 2, {0}) == {1, 3}
    assert arbitrary_clock_witness(model, wide["job_ready"], set(), costs, 2, {0}, target=scale) == {1, 3}
    assert arbitrary_clock_witness(model, wide["job_ready"], set(), costs, 2, {0}, target=scale,
                                   use_envelopes=True) == {1, 3}
    assert arbitrary_clock_witness(model, wide["job_ready"], set(), costs, 2, {0}, target=scale + 1) is None
    assert arbitrary_clock_error(model, wide["job_ready"], set(), costs, 2, {0}) == (scale, frozenset({1, 3}))
    assert minimum_clock_support(model, wide["job_ready"], set())
    interval = approximate(model, wide["job_ready"], set(), costs, 2, Fraction(1, 4))
    assert interval["lower"] <= scale <= interval["upper"]
    counts["wide_integer_digits_checked"] = len(str(scale))
    return counts | {"two_lock_witness_example": {"input": example, "costs": costs, "with_clock": full,
                                                 "after_removal": reduced}}


def benchmark():
    rng = random.Random(2026112231)
    m, n = 80, 24
    problem = randomized_problem(rng, m, n)
    machines = compile_problem(problem)
    costs = {i: rng.randint(1, 24) for i in range(m - 1)}
    budget = sum(costs.values()) // 3
    timings = {"shape": [m, n], "budget": budget}
    duration = []
    for _ in range(3):
        started = process_time()
        graph, floor = checkpoint_graph(machines, problem["job_ready"], set(), costs)
        duration.append(process_time() - started)
    timings["preprocess_cpu_s"] = median(duration)
    for tag, use_envelopes in (("plain", False), ("envelope", True)):
        times = []
        for _ in range(3):
            started = process_time()
            answer = solve_graph(*graph, costs, budget, use_envelopes=use_envelopes, constants=floor)
            times.append(process_time() - started)
        assert simulate_operations(problem, set(answer["added"])) == answer["objective"]
        timings[tag] = answer | {"median_cpu_s": median(times)}
    assert timings["plain"]["objective"] == timings["envelope"]["objective"]
    return timings


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path(__file__).with_name("results.json"))
    args = parser.parse_args()
    report = {"randomized": stress(), "redundancy": redundancy_checks(), "minimal_support": support_checks(),
              "makespan_only_deletion": makespan_only_knapsack_checks(),
              "suffix_clock_deletion": suffix_clock_checks(), "arbitrary_clock_deletion": arbitrary_clock_checks(),
              "avoidable_anchor_counterexample": first_machine_choice(), "benchmark": benchmark()}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in ("randomized", "redundancy", "minimal_support", "makespan_only_deletion",
                                             "suffix_clock_deletion", "arbitrary_clock_deletion", "benchmark")}))
