"""Compare cold queries, shared preprocessing, and a single envelope per fee."""

import argparse
import json
from pathlib import Path
import random
from statistics import median
from time import process_time

from validate import compile_problem, randomized_problem
from local_timing import evaluate, maximum_deletion_error, preprocess_clock_deletions


HERE = Path(__file__).resolve().parent
MODES = ("cold_scan", "shared_scan", "shared_single_envelope")
CASES = ((2026112291, 37, 220, 2), (2026112292, 47, 96, 4),
         (2026112293, 73, 32, 2), (2026112294, 101, 42, 37))


def batch(machines, release, fixed, queries, mode):
    started = process_time()
    if mode == "cold_scan":
        answers = [maximum_deletion_error(preprocess_clock_deletions(machines, release, fixed),
                                          fees, budget, removed, use_envelopes=False)
                   for fees, budget, removed in queries]
    else:
        coefficients = preprocess_clock_deletions(machines, release, fixed)
        answers = [maximum_deletion_error(coefficients, fees, budget, removed,
                                          use_envelopes=mode == "shared_single_envelope")
                   for fees, budget, removed in queries]
    return process_time() - started, answers


def data(seed, m, n, k):
    rng = random.Random(seed)
    raw = randomized_problem(rng, m, n)
    fixed = {m // 3, 2 * m // 3}
    candidates = sorted(set(range(m - 1)) - fixed)
    queries = []
    for position in range(8):
        retained = set(rng.sample(range(m), k))
        if position % 2 == 0:
            retained.add(m - 1)
        removed = set(range(m)) - retained
        fees = {i: rng.randint(1, 22) for i in candidates if rng.random() > 0.15}
        queries.append((fees, (14, 35, 65, 110)[position % 4], removed))
    return compile_problem(raw), raw["job_ready"], fixed, queries


def check(answers, machines, release, fixed, queries):
    values = []
    for (error, witness), (fees, budget, removed) in zip(answers, queries):
        if witness is None:
            assert error == 0
            witness = frozenset()
        retained = set(range(len(machines))) - removed
        complete = fixed | witness
        assert sum(fees[i] for i in witness) <= budget
        assert evaluate(machines, release, complete) - evaluate(machines, release, complete, retained=retained) == error
        values.append(error)
    return values


def experiment():
    trials = []
    for seed, m, n, k in CASES:
        machines, release, fixed, queries = data(seed, m, n, k)
        raw = {mode: [] for mode in MODES}
        baseline = None
        for rep in range(3):
            for mode in MODES[rep:] + MODES[:rep]:
                elapsed, answers = batch(machines, release, fixed, queries, mode)
                values = check(answers, machines, release, fixed, queries)
                if baseline is None:
                    baseline = values
                assert values == baseline
                raw[mode].append(elapsed)
        trials.append({"seed": seed, "machines": m, "jobs": n, "compulsory": sorted(fixed), "queries": len(queries),
                       "retained_count": sorted({m - len(one[2]) for one in queries}), "max_errors": baseline,
                       "measurements_cpu_s": raw, "median_cpu_s": {mode: median(raw[mode]) for mode in MODES}})
    return trials


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=HERE / "deletion_query_benchmarks.json")
    args = parser.parse_args()
    measurements = experiment()
    with args.output.open("x", encoding="utf-8") as f:
        json.dump(measurements, f, indent=2)
        f.write("\n")
    for trial in measurements:
        print(trial["machines"], trial["jobs"], trial["retained_count"], trial["median_cpu_s"])
