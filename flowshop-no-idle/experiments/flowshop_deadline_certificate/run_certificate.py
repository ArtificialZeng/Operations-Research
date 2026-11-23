"""Paired certificates for fixed-order mixed no-idle deadline queries."""

from fractions import Fraction
from functools import reduce
from hashlib import sha256
from heapq import merge
from itertools import accumulate, combinations, groupby
from math import gcd
from pathlib import Path
from runpy import run_path
from statistics import median
from time import process_time_ns
import json
import os
import random


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ORACLES = HERE.parent / "flowshop_position_penalty"
REFERENCE = run_path(str(ORACLES / "verify.py"))
direct = REFERENCE["direct_makespan"]
all_penalties = REFERENCE["all_penalties"]
approximate = run_path(str(ORACLES / "delay_fptas.py"))["approximate_delay"]
CLASSIC = ROOT / "antigravity" / "solvers" / "ruiz2007_classics.py"
neh = run_path(str(CLASSIC))["solve_neh_mnpfsp"]
PUBLIC = ROOT / "antigravity" / "data_confirmatory" / "ruiz2007" / "instance"
PUBLIC_HASHES = {
    "large_instance_1.json": "a5339af2edc0a08b59e59309c4215381ba840fc27364bed3d4244249652a1e64",
    "large_instance_2.json": "510b5d253e711ea0b4b16b511cd41f0f240cdd0efca888d795cd0148b18e36df",
    "large_instance_4.json": "8d453c611ba621b4e305bf8ca388913cdf63d5df9c75330edf4d6297555d1f88",
}
EPSILON = Fraction(1, 2)
PRICE_GROUPS = {"moderate": (12, 71), "wide": (1 << 30, (1 << 34) - 1)}


def digest(data):
    return sha256(data).hexdigest()


def cases():
    for name, expected_hash in PUBLIC_HASHES.items():
        data = (PUBLIC / name).read_bytes()
        assert digest(data) == expected_hash
        instance = json.loads(data)
        matrix = [row[:instance["n_machines"]]
                  for row in instance["processing_times"][:instance["n_jobs"]]]
        yield name, "public", matrix, None, expected_hash

    rng = random.Random(2026112391)
    yield "uniform", "synthetic", [[rng.randint(2, 115) for _ in range(10)]
                                   for _ in range(52)], None, None
    rng = random.Random(2026112392)
    yield "interaction", "synthetic", [
        [rng.randint(7, 33) + 40 * (job % 2 == (machine // 2) % 2)
         for machine in range(12)] for job in range(64)
    ], None, None
    for seed, count in ((2026112393, 10), (2026112394, 16)):
        rng = random.Random(seed)
        values = [rng.randint(1, 1400) for _ in range(count)] + [0]
        machines = [(1, values[0] + 1)]
        for value, next_value in zip(values, values[1:]):
            machines.extend([(1, 1), (value + 1, next_value + 1)])
        yield f"anchors_{count}", "synthetic", list(zip(*machines)), values[:-1], None


def prices(eligible, case_index, mode_index, bounds):
    rng = random.Random(2026112400 + 2 * case_index + mode_index)
    costs = {i: rng.randint(*bounds) for i in sorted(eligible)}
    last = max(costs)
    while reduce(gcd, costs.values()) > 1:
        costs[last] += 1
    return costs, 36 * sum(costs.values()) // 100


def cheap_bounds(times, locked, costs, budget):
    base, penalties = all_penalties(times, locked)
    eligible = {i for i, cost in costs.items() if cost <= budget}
    values = {i: penalties[i][0] for i in eligible}
    ordered = sorted(eligible, key=lambda i: (-Fraction(values[i], costs[i]), i))
    singleton = max(eligible, key=lambda i: (values[i], -i), default=None)
    single_value = values[singleton] if singleton is not None else 0
    budget_left = budget
    fractional = Fraction(0)
    for i in ordered:
        spend = min(costs[i], budget_left)
        fractional += Fraction(spend * values[i], costs[i])
        budget_left -= spend
        if not budget_left:
            break

    budget_left = budget
    density_set = []
    for i in ordered:
        if values[i] and costs[i] <= budget_left:
            density_set.append(i)
            budget_left -= costs[i]

    density_value = direct(times, locked | set(density_set)) - base
    all_lock = direct(times, locked | eligible) - base
    lower_set = density_set if density_value > single_value else ([] if singleton is None else [singleton])
    upper = min(all_lock, fractional.numerator // fractional.denominator)
    return {
        "low": max(single_value, density_value), "high": upper, "witness": lower_set,
        "base": base, "single": single_value, "all_lock": all_lock,
        "singleton_values": values, "fractional_upper_exact": str(fractional),
    }


def pareto_merge(left, right):
    """Keep ascending costs with strictly increasing scores."""
    if not left:
        return right
    if not right:
        return left
    front = []
    for _, items in groupby(merge(left, right), key=lambda label: label[0]):
        candidate = max(items, key=lambda label: (label[1], -label[2]))
        if not front or candidate[1] > front[-1][1]:
            front.append(candidate)
    return front


def sparse_exact(times, locked, costs, budget):
    jobs = len(times[0])
    previous = [[(0, 0, 0)]] * jobs
    peak, labels = 1, jobs
    for i, row in enumerate(times):
        prefix = tuple(accumulate(row, initial=0))
        centered = [[(cost, value - prefix[j], mask) for cost, value, mask in front]
                    for j, front in enumerate(previous)]

        starts, running = [], []
        for front in centered:
            running = pareto_merge(running, front)
            starts.append(running)

        if i in locked:
            starts = [running] * jobs
        elif i in costs and costs[i] <= budget:
            running = []
            price = costs[i]
            for j in reversed(range(jobs)):
                shifted = [(cost + price, value, mask | (1 << i)) for cost, value, mask in running
                           if cost + price <= budget]
                starts[j] = pareto_merge(starts[j], shifted)
                running = pareto_merge(running, centered[j])

        previous = [[(cost, value + prefix[j + 1], mask) for cost, value, mask in front]
                    for j, front in enumerate(starts)]
        peak = max(peak, max(map(len, previous)))
        labels += sum(map(len, previous))

    cost, best, mask = previous[-1][-1]
    witness = [i for i in range(len(times)) if mask >> i & 1]
    return {"makespan": best, "cost": cost, "witness": witness,
            "peak_frontier": peak, "retained_labels_including_layer_zero": labels}


def measured(function, *args):
    started = process_time_ns()
    result = function(*args)
    return result, process_time_ns() - started


def assess(times, locked, costs, budget, exact_first, check_subsets):
    cheap, cheap_ns = measured(cheap_bounds, times, locked, costs, budget)
    if exact_first:
        exact, exact_ns = measured(sparse_exact, times, locked, costs, budget)
        approx, approx_ns = measured(approximate, times, locked, costs, budget, EPSILON)
    else:
        approx, approx_ns = measured(approximate, times, locked, costs, budget, EPSILON)
        exact, exact_ns = measured(sparse_exact, times, locked, costs, budget)

    base = cheap["base"]
    assert base == approx["baseline"] == direct(times, locked)
    approx_delay = approx["makespan"] - base
    true_delay = exact["makespan"] - base
    upper = approx_delay + int(EPSILON * cheap["single"])
    low = max(cheap["low"], approx_delay)
    high = min(cheap["high"], upper)
    assert cheap["low"] <= low <= true_delay <= high <= cheap["high"]
    for witness, value in ((cheap["witness"], cheap["low"]),
                           (approx["additional_locks"], approx_delay),
                           (exact["witness"], true_delay)):
        assert sum(costs[i] for i in witness) <= budget
        assert direct(times, locked | set(witness)) - base == value
    assert exact["cost"] == sum(costs[i] for i in exact["witness"])

    subsets = 0
    if check_subsets:
        evaluated = []
        for count in range(len(costs) + 1):
            for subset in combinations(costs, count):
                if sum(costs[i] for i in subset) <= budget:
                    evaluated.append(direct(times, locked | set(subset)))
        assert exact["makespan"] == max(evaluated)
        subsets = len(evaluated)

    deadline = sorted({base * points // 10_000 for points in (0, 25, 50, 100, 200, 400, 800)})
    width = cheap["high"] - cheap["low"]
    targeted = sorted({cheap["low"] + width * step // 4 for step in range(5)})
    panels = {}
    for name, thresholds in (("deadline_ratio", deadline), ("cheap_gap", targeted)):
        records = []
        for threshold in thresholds:
            truth = "late" if true_delay > threshold else "within"
            cheap_answer = classify(cheap["low"], cheap["high"], threshold)
            approx_answer = classify(low, high, threshold)
            assert cheap_answer in (None, truth) and approx_answer in (None, truth)
            records.append({"threshold": threshold, "exact": truth, "cheap": cheap_answer,
                            "cheap_then_fptas": approx_answer})
        panels[name] = records

    return {"cheap": cheap, "approx": {**approx, "low": low, "high": high, "raw_upper": upper},
            "exact": {**exact, "delay": true_delay, "exhaustive_feasible_sets": subsets},
            "queries": panels, "cpu_ns": {"cheap": cheap_ns, "approx": approx_ns, "exact": exact_ns}}


def classify(low, high, threshold):
    if low > threshold:
        return "late"
    if high <= threshold:
        return "within"
    return None


def summarize(records):
    result = {}
    for panel in ("deadline_ratio", "cheap_gap"):
        queries = [query for rec in records for query in rec["queries"][panel]]
        lookup = [rec for rec in records if any(q["cheap"] is None for q in rec["queries"][panel])]
        fallback = [rec for rec in lookup if any(q["cheap_then_fptas"] is None for q in rec["queries"][panel])]
        cheap_ns = sum(rec["cpu_ns"]["cheap"] for rec in records)
        approx_ns = sum(rec["cpu_ns"]["approx"] for rec in lookup)
        exact_ns = sum(rec["cpu_ns"]["exact"] for rec in lookup)
        fallback_ns = sum(rec["cpu_ns"]["exact"] for rec in fallback)
        result[panel] = {
            "queries": len(queries), "late_by_exact": sum(q["exact"] == "late" for q in queries),
            "cheap_resolved": sum(q["cheap"] is not None for q in queries),
            "cheap_then_fptas_resolved": sum(q["cheap_then_fptas"] is not None for q in queries),
            "expensive_scenarios_after_cheap": len(lookup),
            "exact_fallback_scenarios_after_fptas": len(fallback),
            "projected_pipeline_cpu_ns": {
                "cheap_only": cheap_ns, "cheap_then_fptas": cheap_ns + approx_ns,
                "cheap_then_exact": cheap_ns + exact_ns,
                "cheap_then_fptas_then_exact": cheap_ns + approx_ns + fallback_ns,
            },
        }
    return {"panels": result, "scenario_count": len(records),
            "median_cpu_ns": {method: median(rec["cpu_ns"][method] for rec in records)
                              for method in ("cheap", "approx", "exact")},
            "median_cheap_width": median(rec["cheap"]["high"] - rec["cheap"]["low"] for rec in records),
            "median_fptas_width": median(rec["approx"]["high"] - rec["approx"]["low"] for rec in records)}


def main():
    records = []
    for case_index, (name, source, rows, values, raw_hash) in enumerate(cases()):
        machines, jobs = len(rows[0]), len(rows)
        columns = tuple(zip(*rows))
        locked = {machines // 2} if values is None else set()
        eligible = set(range(1, machines - 1)) - locked if values is None else set(range(1, machines, 2))
        order = neh(jobs, machines, columns, [i in locked for i in range(machines)]) if values is None else (0, 1)
        times = [[column[job] for job in order] for column in columns]
        for mode_index, (mode, bounds) in enumerate(PRICE_GROUPS.items()):
            costs, budget = prices(eligible, case_index, mode_index, bounds)
            record = assess(times, locked, costs, budget, bool((case_index + mode_index) % 2),
                            source == "synthetic" and len(costs) <= 10)
            records.append({"case": name, "source": source, "prices": mode, "jobs": jobs,
                            "machines": machines, "public_sha256": raw_hash,
                            "ordered_times_sha256": digest(json.dumps(times).encode()), "order": list(order),
                            "locked": sorted(locked), "costs": costs, "budget": budget, **record})

    groups = {"overall": records}
    for field in ("source", "prices"):
        for group in sorted({rec[field] for rec in records}):
            groups[group] = [rec for rec in records if rec[field] == group]
    print(json.dumps({"epsilon": str(EPSILON), "cpu_affinity": sorted(os.sched_getaffinity(0)),
                      "source_sha256": {path.name: digest(path.read_bytes()) for path in
                                        (ORACLES / "verify.py", ORACLES / "delay_fptas.py", CLASSIC,
                                         HERE / "PROTOCOL.md", Path(__file__))},
                      "summary": {key: summarize(group) for key, group in groups.items()},
                      "scenarios": records}, indent=2))


if __name__ == "__main__":
    main()
