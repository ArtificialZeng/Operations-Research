"""Check the checkpoint reduction when internal setups may start in advance."""

from itertools import accumulate, combinations, pairwise
import json
from pathlib import Path
import random

from monge_budget import solve_graph


def build_setup_graph(processing, setup, mandatory, candidates):
    if any(row[0] for row in setup):
        raise ValueError("The first setup must take zero time")
    occupied = [[duration + preparation for duration, preparation in zip(p, s)]
                for p, s in zip(processing, setup)]
    m = len(processing)
    compulsory = sorted(set(mandatory) | {0, m - 1})
    eligible = set(candidates) | set(compulsory)
    arcs = {}
    for begin, end in pairwise(compulsory):
        for source in range(begin, end):
            if source not in eligible:
                continue
            upper = list(accumulate(occupied[source]))
            for target in range(source + 1, end + 1):
                elapsed = 0
                running = None
                completions = []
                for available, p, s in zip(upper, processing[target], setup[target]):
                    slack = available - elapsed - s
                    running = slack if running is None else max(running, slack)
                    elapsed += p + s
                    completions.append(elapsed + running)
                if target in eligible:
                    arcs[source, target] = running
                upper = completions
    return compulsory, arcs, sum(occupied[-1])


def simulate(processing, setup, locked):
    arrivals = [0] * len(processing[0])
    for i, (row, preparations) in enumerate(zip(processing, setup)):
        machine_clock = 0
        finished = []
        if i in locked:
            processing_starts = []
            for task, (p, s) in enumerate(zip(row, preparations)):
                machine_clock += s
                processing_starts.append(machine_clock)
                machine_clock += p
                finished.append(machine_clock)
            shift = max(a - h for a, h in zip(arrivals, processing_starts))
            arrivals = [point + shift for point in finished]
        else:
            for available, p, s in zip(arrivals, row, preparations):
                machine_clock = max(available, machine_clock + s) + p
                finished.append(machine_clock)
            arrivals = finished
    return arrivals[-1]


def audit():
    rng = random.Random(115820)
    counts = {"arrays": 280, "subsets": 0, "four_point_checks": 0, "budget_certificates": 0}
    for _ in range(counts["arrays"]):
        m, n = rng.randint(2, 10), rng.randint(2, 9)
        processing = [[rng.randrange(29) for _ in range(n)] for _ in range(m)]
        preparations = [[0, *(rng.randrange(29) for _ in range(n - 1))] for _ in range(m)]
        locked = {i for i in range(1, m - 1) if rng.random() < 0.14}
        costs = {i: rng.randint(1, 12) for i in range(1, m - 1) if i not in locked}
        graph = build_setup_graph(processing, preparations, locked, costs)
        compulsory, arcs, tail = graph
        true = []
        for size in range(len(costs) + 1):
            for signature in combinations(costs, size):
                full = locked | set(signature)
                path = sorted(set(compulsory) | set(signature))
                value = simulate(processing, preparations, full)
                assert tail + sum(arcs[edge] for edge in pairwise(path)) == value
                true.append((sum(costs[j] for j in signature), value))
                counts["subsets"] += 1
        for a, b in pairwise(compulsory):
            for i, j, k, ell in combinations(range(a, b + 1), 4):
                assert arcs[i, k] + arcs[j, ell] >= arcs[i, ell] + arcs[j, k]
                counts["four_point_checks"] += 1
        for budget in {0, rng.randint(0, sum(costs.values())), sum(costs.values())}:
            got = solve_graph(*graph, costs, budget)
            assert got["cost"] <= budget
            assert (simulate(processing, preparations, locked | set(got["added"])) == got["objective"]
                    == max(time for spend, time in true if spend <= budget))
            counts["budget_certificates"] += 1
    return counts


if __name__ == "__main__":
    counts = audit()
    result = Path(__file__).resolve().with_name("anticipatory_setup_results.json")
    result.write_text(json.dumps(counts, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(counts))
