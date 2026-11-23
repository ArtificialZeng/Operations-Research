"""Check affine checkpoint arcs with absolute machine release dates."""

from itertools import accumulate, combinations, pairwise
import json
from pathlib import Path
import random
from statistics import median
from time import process_time

from monge_budget import solve_graph


def affine_graph(processing, setup, release, mandatory, candidates, *, job_release=None):
    occupied = [[d + s for d, s in zip(row, preparations)] for row, preparations in zip(processing, setup)]
    m = len(occupied)
    start = -1 if job_release is not None else 0
    compulsory = sorted(set(mandatory) | {start, m - 1})
    eligible = set(compulsory) | set(candidates)
    arcs, constants = {}, {}
    for left, right in pairwise(compulsory):
        for source in range(left, right):
            if source not in eligible:
                continue
            upstream_from_start = list(job_release) if source < 0 else list(accumulate(occupied[source]))
            upstream_from_release = None
            for target in range(source + 1, right + 1):
                next_from_start = []
                next_from_release = []
                slope_offset = None
                floor = release[target]
                elapsed = 0
                for position, (duration, prep) in enumerate(zip(occupied[target], setup[target])):
                    offset = elapsed + prep
                    value = upstream_from_start[position] - offset
                    slope_offset = value if slope_offset is None else max(slope_offset, value)
                    if upstream_from_release is not None:
                        floor = max(floor, upstream_from_release[position] - offset)
                    elapsed += duration
                    next_from_start.append(slope_offset + elapsed)
                    next_from_release.append(floor + elapsed)
                if target in eligible:
                    arcs[source, target] = slope_offset
                    constants[source, target] = floor
                upstream_from_start = next_from_start
                upstream_from_release = next_from_release
    return (compulsory, arcs, sum(occupied[-1])), constants


def simulate(processing, setup, release, locked, *, job_release=None):
    arrivals = [0] * len(processing[0]) if job_release is None else list(job_release)
    for i, (work, preparations) in enumerate(zip(processing, setup)):
        clock, finishes = release[i], []
        if i in locked:
            offsets = []
            planned = 0
            for p, s in zip(work, preparations):
                planned += s
                offsets.append(planned)
                planned += p
            clock = max(clock, max(arrival - offset for arrival, offset in zip(arrivals, offsets)))
            for p, s in zip(work, preparations):
                clock += p + s
                finishes.append(clock)
        else:
            for arrival, p, s in zip(arrivals, work, preparations):
                clock = max(arrival, clock + s) + p
                finishes.append(clock)
        arrivals = finishes
    return arrivals[-1]


def audit():
    rng = random.Random(192596)
    counts = {"matrices": 320, "subsets": 0, "quadrangles": 0, "floor_order_checks": 0, "budgets": 0}
    counterexample = None
    for _ in range(counts["matrices"]):
        m, n = rng.randint(1, 10), rng.randint(2, 8)
        work = [[rng.randint(0, 18) for _ in range(n)] for _ in range(m)]
        setup = [[rng.randint(0, 18) for _ in range(n)] for _ in range(m)]
        releases = [rng.randint(0, 120) for _ in range(m)]
        old = {i for i in range(1, m - 1) if rng.random() < 0.15}
        costs = {i: rng.randint(1, 11) for i in range(1, m - 1) if i not in old}
        graph, floors = affine_graph(work, setup, releases, old, costs)
        compulsory, arcs, tail = graph
        for left, right in pairwise(compulsory):
            for i, j, k, ell in combinations(range(left, right + 1), 4):
                assert arcs[i, k] + arcs[j, ell] >= arcs[i, ell] + arcs[j, k]
                counts["quadrangles"] += 1
            for i, j, k in combinations(range(left, right + 1), 3):
                assert floors[i, k] >= floors[j, k]
                counts["floor_order_checks"] += 1
        evaluations = {}
        for size in range(len(costs) + 1):
            for mask in combinations(costs, size):
                marked = frozenset(mask)
                actual = simulate(work, setup, releases, old | marked)
                path = sorted(set(compulsory) | marked)
                value = releases[0]
                for edge in pairwise(path):
                    value = max(value + arcs[edge], floors[edge])
                assert value + tail == actual
                evaluations[marked] = actual
                counts["subsets"] += 1
        if counterexample is None:
            for group, original in evaluations.items():
                for j, k in combinations(set(costs) - group, 2):
                    p, q = evaluations[group | {j}], evaluations[group | {k}]
                    pq = evaluations[group | {j, k}]
                    if p + q < original + pq:
                        counterexample = {"processing": work, "setup": setup, "release": releases,
                                          "always_locked": sorted(old | set(group)), "toggled": [j, k],
                                          "makespans": [original, p, q, pq]}
                        break
                if counterexample is not None:
                    break
        full_cost = sum(costs.values())
        for budget in {0, rng.randint(0, full_cost), full_cost}:
            optimum = max(value for s, value in evaluations.items() if sum(costs[i] for i in s) <= budget)
            for use_envelopes in (True, False):
                result = solve_graph(*graph, costs, budget, use_envelopes=use_envelopes, constants=floors,
                                     origin=releases[0])
                assert result["cost"] <= budget
                assert result["objective"] == optimum == evaluations[frozenset(result["added"])]
            counts["budgets"] += 1
    work = [(1, 2), (1, 1), (2, 2), (1, 1), (2, 1)]
    zero_setup = [(0, 0)] * len(work)
    subsets = [set(), {1}, {3}, {1, 3}]
    plain = [simulate(work, zero_setup, [0] * len(work), subset) for subset in subsets]
    final_release = [simulate(work, zero_setup, [0, 0, 0, 0, 6], subset) for subset in subsets]
    final_setup = [simulate(work, [*zero_setup[:-1], (6, 0)], [0] * len(work), subset) for subset in subsets]
    assert plain == [8, 9, 9, 10] and final_release == final_setup == [9, 9, 9, 10]
    return {"audit": counts, "two_job_example": {"makespans_without_absolute_limits": plain,
                                                 "with_last_machine_release": final_release,
                                                 "with_last_machine_first_setup": final_setup},
            "submodularity_counterexample": counterexample, "individual_job_release": audit_individual_jobs()}


def audit_individual_jobs():
    rng = random.Random(195700)
    n_test = 190
    n_paths = 0
    n_witnesses = 0
    for _ in range(n_test):
        m, n = rng.randint(2, 9), rng.randint(2, 7)
        work = [[rng.randint(0, 15) for _ in range(n)] for _ in range(m)]
        setup = [[rng.randint(0, 15) for _ in range(n)] for _ in range(m)]
        releases = [rng.randint(0, 65) for _ in range(m)]
        job_release = [rng.randint(0, 180) for _ in range(n)]
        old = {i for i in range(m - 1) if rng.random() < 0.12}
        costs = {i: rng.randint(1, 11) for i in range(m - 1) if i not in old}
        graph, floors = affine_graph(work, setup, releases, old, costs, job_release=job_release)
        compulsory, arcs, tail = graph
        reference = {}
        for size in range(len(costs) + 1):
            for values in combinations(costs, size):
                chosen = frozenset(values)
                result = simulate(work, setup, releases, old | chosen, job_release=job_release)
                clock = 0
                for edge in pairwise(sorted(set(compulsory) | chosen)):
                    clock = max(clock + arcs[edge], floors[edge])
                assert tail + clock == result
                reference[chosen] = result
                n_paths += 1
        maximum_cost = sum(costs.values())
        for budget in {0, rng.randint(0, maximum_cost), maximum_cost}:
            solution = solve_graph(*graph, costs, budget, constants=floors)
            expected = max(value for chosen, value in reference.items() if sum(costs[i] for i in chosen) <= budget)
            assert solution["objective"] == expected == reference[frozenset(solution["added"])]
            n_witnesses += 1
    work = [(1, 1), (100, 1)]
    no_setup = [(0, 0)] * 2
    r = [0, 10]
    left_open = simulate(work, no_setup, [0, 0], set(), job_release=r)
    left_locked = simulate(work, no_setup, [0, 0], {0}, job_release=r)
    assert (left_open, left_locked) == (102, 111)
    return {"matrices": n_test, "subsets": n_paths, "budget_certificates": n_witnesses,
            "first_machine_counterexample": {"first_open": left_open, "first_locked": left_locked}}


def benchmark():
    rng = random.Random(50721)
    machines, jobs = 80, 24
    work = [[rng.randint(0, 55) for _ in range(jobs)] for _ in range(machines)]
    setup = [[rng.randint(0, 23) for _ in range(jobs)] for _ in range(machines)]
    release = [rng.randint(0, 360) for _ in range(machines)]
    job_release = [rng.randint(0, 220) for _ in range(jobs)]
    costs = {i: rng.randint(1, 22) for i in range(machines - 1)}
    budget = sum(costs.values()) // 3
    start = process_time()
    graph, floors = affine_graph(work, setup, release, set(), costs, job_release=job_release)
    build_cpu = process_time() - start
    result = {"machines": machines, "jobs": jobs, "budget": budget, "build_cpu_s": build_cpu}
    for tag, efficient in (("plain", False), ("envelope", True)):
        elapsed = []
        for _ in range(3):
            start = process_time()
            schedule = solve_graph(*graph, costs, budget, use_envelopes=efficient, constants=floors)
            elapsed.append(process_time() - start)
        exact_value = simulate(work, setup, release, set(schedule["added"]), job_release=job_release)
        assert exact_value == schedule["objective"]
        result[tag] = {"median_cpu_s": median(elapsed), **schedule}
    assert result["plain"]["objective"] == result["envelope"]["objective"]
    return result


if __name__ == "__main__":
    report = audit()
    report["benchmark"] = benchmark()
    (Path(__file__).resolve().parent / "release_dates_results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report))
