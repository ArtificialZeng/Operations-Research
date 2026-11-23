"""Independent checks and CPU comparison for the checkpoint budget envelope."""

from hashlib import sha256
from itertools import combinations, pairwise
import json
from pathlib import Path
import random
from runpy import run_path
from statistics import median
from time import process_time

from monge_budget import build_graph, solve_graph


HERE = Path(__file__).resolve().parent
REFERENCE = HERE.parent / "flowshop_position_penalty"
direct = run_path(str(REFERENCE / "verify.py"))["direct_makespan"]
dense = run_path(str(REFERENCE / "worst_lock.py"))["worst_lock_set"]


def checked(result, times, locked, costs, budget, objective):
    selected = set(result["added"])
    assert selected <= set(costs) - locked
    assert sum(costs[i] for i in selected) == result["cost"] <= budget
    assert direct(times, locked | selected) == result["objective"] == objective


def exhaustive_tests():
    rng = random.Random(1781952)
    subsets = quadrangles = checks = 0
    for _ in range(375):
        m, n = rng.randint(1, 11), rng.randint(1, 9)
        times = [[rng.randrange(21) for _ in range(n)] for _ in range(m)]
        locked = {i for i in range(1, m - 1) if rng.random() < 0.26}
        costs = {i: rng.randint(1, 13) for i in range(1, m - 1) if i not in locked and rng.random() < 0.82}
        graph = build_graph(times, locked, costs)
        compulsory, arcs, _ = graph
        for left, right in pairwise(compulsory):
            choices = [left, *(i for i in sorted(costs) if left < i < right), right]
            for a, b, c, d in combinations(choices, 4):
                assert arcs[a, c] + arcs[b, d] >= arcs[a, d] + arcs[b, c]
                quadrangles += 1
        possibilities = []
        for k in range(len(costs) + 1):
            for subset in combinations(costs, k):
                possibilities.append((sum(costs[i] for i in subset), direct(times, locked | set(subset))))
        subsets += len(possibilities)
        for budget in sorted({0, rng.randrange(max(1, sum(costs.values()) + 1)), sum(costs.values()) + 1}):
            wanted = max(value for spend, value in possibilities if spend <= budget)
            checked(solve_graph(*graph, costs, budget), times, locked, costs, budget, wanted)
            checked(solve_graph(*graph, costs, budget, use_envelopes=False), times, locked, costs, budget, wanted)
            checks += 1
    return {"matrices": 375, "subsets": subsets, "budget_checks": checks, "monge_checks": quadrangles}


def measured(call, repeats):
    samples = []
    for _ in range(repeats):
        start = process_time()
        value = call()
        samples.append(process_time() - start)
    return value, median(samples)


def benchmark_inputs():
    public = HERE.parents[1] / "antigravity/data_confirmatory/ruiz2007/instance"
    for k in (1, 2, 3, 4, 5):
        path = public / f"large_instance_{k}.json"
        data = path.read_bytes()
        case = json.loads(data)
        n, m = case["n_jobs"], case["n_machines"]
        rows = [row[:m] for row in case["processing_times"][:n]]
        times = list(zip(*rows))
        locked = {i for i, flag in enumerate(case["no_idle_flags"][:m]) if flag}
        yield f"public_ruiz_{k}", times, locked, sha256(data).hexdigest()
    for seed, m, n in ((17, 36, 200), (18, 80, 22), (19, 50, 60)):
        rng = random.Random(seed)
        times = [[rng.randint(0, 120) for _ in range(n)] for _ in range(m)]
        yield f"synthetic_{seed}", times, {m // 2} if seed == 19 else set(), None


def benchmark():
    rng = random.Random(8112506)
    rows = []
    for label, times, locked, digest in benchmark_inputs():
        m, n = len(times), len(times[0])
        costs = {i: rng.randint(1, 25) for i in range(1, m - 1) if i not in locked}
        graph, build_seconds = measured(lambda: build_graph(times, locked, costs), 3)
        for budget in (12, sum(costs.values()) // 3):
            expected, dense_seconds = measured(lambda: dense(times, locked, set(costs), budget, lock_costs=costs), 3)
            plain, plain_seconds = measured(lambda: solve_graph(*graph, costs, budget, use_envelopes=False), 3)
            fast, monge_seconds = measured(lambda: solve_graph(*graph, costs, budget), 3)
            for result in (plain, fast):
                checked(result, times, locked, costs, budget, expected["makespan"])
            rows.append({"case": label, "dimensions": [m, n], "source_sha256": digest, "budget": budget,
                         "graph_arcs": len(graph[1]), "build_cpu": build_seconds, "dense_cpu": dense_seconds,
                         "checkpoint_cpu": plain_seconds, "envelope_cpu": monge_seconds, **fast})
    return rows


if __name__ == "__main__":
    data = {"exhaustive": exhaustive_tests(), "paired": benchmark()}
    result = HERE / "results.json"
    result.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(data))
