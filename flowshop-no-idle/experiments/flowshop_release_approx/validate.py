"""Recompute physical schedules and source-wise certificates independently."""

from fractions import Fraction
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
import random
from time import process_time

from source_approx import affine_graph, approximate, simulate
from monge_budget import solve_graph


HERE = Path(__file__).resolve().parent


def homogeneous_clock(work, setup, availability, job_release, locked, anchor):
    """Direct completion recursion, without using checkpoint arcs or potentials."""
    if anchor < 0:
        arrivals = job_release
    else:
        clock = availability[anchor]
        arrivals = []
        for duration, preparation in zip(work[anchor], setup[anchor]):
            clock += duration + preparation
            arrivals.append(clock)
    for i in range(anchor + 1, len(work)):
        row, preparations = work[i], setup[i]
        if i in locked:
            planned = 0
            offsets = []
            for duration, preparation in zip(row, preparations):
                offsets.append(planned + preparation)
                planned += preparation + duration
            clock = max(arrival - start for arrival, start in zip(arrivals, offsets))
            result = []
            for duration, preparation in zip(row, preparations):
                clock += duration + preparation
                result.append(clock)
        else:
            clock = float("-inf")
            result = []
            for arrival, duration, preparation in zip(arrivals, row, preparations):
                clock = max(clock + preparation, arrival) + duration
                result.append(clock)
        arrivals = result
    return arrivals[-1]


def exact_enumeration(work, setup, availability, job_release, fixed, costs, budget):
    clocks = range(-1, len(work))
    beta = [homogeneous_clock(work, setup, availability, job_release, fixed, h) for h in clocks]
    reference = max(beta)
    source_absolute = beta.copy()
    checks = 0
    for size in range(len(costs) + 1):
        for choice in combinations(costs, size):
            if sum(costs[j] for j in choice) > budget:
                continue
            locked = fixed | set(choice)
            contributions = [homogeneous_clock(work, setup, availability, job_release, locked, h) for h in clocks]
            assert max(contributions) == simulate(work, setup, availability, locked, job_release=job_release)
            assert all(value >= base for value, base in zip(contributions, beta))
            source_absolute = [max(so_far, value) for so_far, value in zip(source_absolute, contributions)]
            checks += 1
    true = max(source_absolute) - reference
    best_slack = min(reference - b for b, z in zip(beta, source_absolute) if z - reference == true)
    return true, checks, best_slack, {h: val - reference for h, val in zip(clocks, source_absolute)}


def verify_certificate(problem, epsilon, truth, source_truth=None):
    report = approximate(*problem, epsilon)
    work, setup, dates, jobs, fixed, costs, budget = problem
    selected = set(report["witness"])
    assert selected <= set(costs) and sum(costs[j] for j in selected) == report["cost"] <= budget
    actual = simulate(work, setup, dates, fixed | selected, job_release=jobs) - report["baseline"]
    assert actual == report["lower"] <= truth <= report["upper"]
    if source_truth is not None:
        for row in report["clock_certificates"]:
            assert source_truth[row["clock"]] <= row["upper"]
        error = min(epsilon * row["largest_edge_reward"] for row in report["clock_certificates"]
                    if source_truth[row["clock"]] == truth)
        assert report["lower"] >= truth - error
    return report


def randomized():
    rng = random.Random(460977)
    result = {"matrices": 200, "feasible_lock_sets": 0, "approximation_certificates": 0,
              "positive_instances": 0, "conditional_relative_certificates": 0, "zero_certified": 0}
    for _ in range(result["matrices"]):
        m, n = rng.randint(2, 10), rng.randint(2, 8)
        work = [[rng.randrange(1, 27) for _ in range(n)] for _ in range(m)]
        setup = [[rng.randrange(0, 22) for _ in range(n)] for _ in range(m)]
        dates = [rng.randrange(0, 150) for _ in range(m)]
        jobs = [rng.randrange(0, 96) for _ in range(n)]
        fixed = {j for j in range(m - 1) if rng.random() < 0.18}
        costs = {j: rng.randint(1, 15) for j in range(m - 1) if j not in fixed and rng.random() < 0.91}
        budget = rng.randint(0, max(1, sum(costs.values())))
        problem = work, setup, dates, jobs, fixed, costs, budget
        full, choices, slack, by_source = exact_enumeration(*problem)
        result["feasible_lock_sets"] += choices
        for epsilon in (Fraction(1, 3), Fraction(1, 7)):
            cert = verify_certificate(problem, epsilon, full, by_source)
            result["approximation_certificates"] += 1
            result["zero_certified"] += int(full == 0 and cert["upper"] == 0)
        if full > 0:
            rho = Fraction(slack, full)
            epsilon = Fraction(1, 6)
            cert = verify_certificate(problem, epsilon / (1 + rho), full, by_source)
            assert cert["lower"] >= (1 - epsilon) * full
            result["positive_instances"] += 1
            result["conditional_relative_certificates"] += 1
    return result


def evaluate_materialized(problem, tag, checksum=None):
    work, setup, dates, jobs, fixed, costs, budget = problem
    start = process_time()
    graph, floor = affine_graph(work, setup, dates, fixed, set(costs), job_release=jobs)
    exact = solve_graph(*graph, costs, budget, constants=floor)
    exact_seconds = process_time() - start
    assert simulate(work, setup, dates, fixed | set(exact["added"]), job_release=jobs) == exact["objective"]
    baseline = simulate(work, setup, dates, fixed, job_release=jobs)
    start = process_time()
    cert = verify_certificate(problem, Fraction(1, 4), exact["objective"] - baseline)
    return {"case": tag, "source_sha256": checksum, "n_machines": len(work), "n_jobs": len(work[0]),
            "budget": budget, "worst_delay": exact["objective"] - baseline, "exact_cpu_seconds": exact_seconds,
            "approx_cpu_seconds": process_time() - start, **cert}


def comparisons():
    rng = random.Random(461158)
    public = HERE.parents[1] / "antigravity/data_confirmatory/ruiz2007/instance"
    cases = []
    for ident in (1, 2, 3):
        payload = (public / f"large_instance_{ident}.json").read_bytes()
        data = json.loads(payload)
        n, m = data["n_jobs"], data["n_machines"]
        work = list(zip(*[row[:m] for row in data["processing_times"][:n]]))
        cases.append((f"ruiz_{ident}_with_synthetic_clock_data", work, sha256(payload).hexdigest()))
    for m in (18, 25, 32):
        work = [[rng.randint(3, 120) for _ in range(36)] for _ in range(m)]
        cases.append((f"synthetic_{m}_machines", work, None))
    out = []
    for tag, work, digest in cases:
        m, n = len(work), len(work[0])
        setup = [[rng.randrange(24) for _ in range(n)] for _ in range(m)]
        dates = [rng.randrange(440) for _ in range(m)]
        jobs = [rng.randrange(240) for _ in range(n)]
        fixed = {m // 3, 2 * m // 3}
        costs = {i: rng.randint(5, 50) for i in range(m - 1) if i not in fixed}
        out.append(evaluate_materialized((work, setup, dates, jobs, fixed, costs, sum(costs.values()) // 3), tag, digest))
    return out


def masking_family():
    values = [13, 29, 48, 61, 103, 149, 239, 353]
    work = [[1, values[0] + 1]]
    for v, after in zip(values, values[1:] + [0]):
        work.extend(([1, 1], [v + 1, after + 1]))
    setup = [[0, 0] for _ in work]
    jobs = [0, 0]
    costs = {2 * i + 1: v + 2 for i, v in enumerate(values)}
    dates = [0] * len(work)
    budget = 443
    absolute_base = simulate(work, setup, dates, set(), job_release=jobs)
    true_without_mask, _, _, _ = exact_enumeration(work, setup, dates, jobs, set(), costs, budget)
    rows = []
    for threshold in (1, true_without_mask // 2, true_without_mask, true_without_mask + 1):
        dates = [0] * len(work)
        dates[-1] = absolute_base + threshold - 1 - sum(work[-1])
        problem = work, setup, dates, jobs, set(), costs, budget
        truth, _, slack, by_source = exact_enumeration(*problem)
        assert truth == max(0, true_without_mask - threshold + 1)
        cert = verify_certificate(problem, Fraction(1, 4), truth, by_source)
        rows.append({"masking_threshold": threshold, "exact_increment": truth, "best_source_slack": slack,
                     "coarse_lower": cert["lower"], "coarse_upper": cert["upper"]})
    return rows


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run independent fixed-order approximation checks")
    parser.add_argument("--output", type=Path, default=HERE / "results.json")
    options = parser.parse_args()
    result = {"randomized": randomized(), "masking_family": masking_family(), "case_comparisons": comparisons()}
    with options.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"randomized": result["randomized"], "masking_family": result["masking_family"],
                      "cases": [{k: row[k] for k in ("case", "worst_delay", "lower", "upper", "exact_cpu_seconds",
                                                        "approx_cpu_seconds")} for row in result["case_comparisons"]]}))
