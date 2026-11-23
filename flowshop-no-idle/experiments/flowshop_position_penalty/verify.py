import argparse
import itertools
import json
import random
import time


def machine_times(jobs, order):
    return list(zip(*(jobs[job] for job in order)))


def direct_makespan(times, locked):
    """Forward scheduling oracle using completion times and the first start."""
    completed = [0] * len(times[0])
    for machine, durations in enumerate(times):
        if machine in locked:
            start = 0
            elapsed = 0
            for arrival, duration in zip(completed, durations):
                start = max(start, arrival - elapsed)
                elapsed += duration
            finished = []
            for duration in durations:
                start += duration
                finished.append(start)
        else:
            finished = []
            clock = 0
            for arrival, duration in zip(completed, durations):
                clock = max(clock, arrival) + duration
                finished.append(clock)
        completed = finished
    return completed[-1]


def all_penalties(times, locked):
    """Return the marginal penalty, earliest arrival maximizer and latest tail maximizer."""
    jobs = len(times[0])
    prefixes = [(0, *itertools.accumulate(durations)) for durations in times]
    arrivals = [0] * jobs
    centered_arrivals = []
    for machine, prefix in enumerate(prefixes):
        centered = [arrival - prefix[slot] for slot, arrival in enumerate(arrivals)]
        centered_arrivals.append(centered)
        start_by_slot = (
            [max(centered)] * jobs if machine in locked else itertools.accumulate(centered, max)
        )
        arrivals = [load + start for load, start in zip(prefix[1:], start_by_slot)]
    makespan = arrivals[-1]

    # Only the final slot has an edge to the makespan before any backward step.
    tails = [None] * (jobs - 1) + [0]
    penalties = {}
    for machine in reversed(range(len(times))):
        prefix = prefixes[machine]
        weights = [
            None if tail is None else load + tail
            for load, tail in zip(prefix[1:], tails)
        ]
        best_weight = max(weight for weight in weights if weight is not None)
        if machine not in locked:
            centered = centered_arrivals[machine]
            best_arrival = max(centered)
            earliest = centered.index(best_arrival)
            latest = max(slot for slot, weight in enumerate(weights) if weight == best_weight)
            penalties[machine] = (best_arrival + best_weight - makespan, earliest, latest)

        if machine in locked:
            tails = [best_weight - load for load in prefix[:-1]]
        else:
            right_maximum = weights[-1]
            for slot in reversed(range(jobs)):
                weight = weights[slot]
                if weight is not None:
                    right_maximum = max(right_maximum, weight)
                tails[slot] = right_maximum - prefix[slot]
    return makespan, penalties


def exact_checks():
    randomizer = random.Random(2026112201)
    cases = [(1, 1), (1, 5), (2, 3), (2, 4), (3, 3), (4, 5), (6, 7), (7, 9)]
    schedules = zero = positive = submodular_checks = zero_set_checks = 0
    for jobs, machines in cases:
        for _ in range(3):
            durations = [
                tuple(randomizer.randint(1, 30) for _ in range(machines))
                for _ in range(jobs)
            ]
            for _ in range(3):
                permutation = randomizer.sample(range(jobs), jobs)
                times = machine_times(durations, permutation)
                baseline_by_mask = []
                for mask in range(1 << machines):
                    locks = {machine for machine in range(machines) if mask & (1 << machine)}
                    baseline, penalties = all_penalties(times, locks)
                    assert baseline == direct_makespan(times, locks)
                    baseline_by_mask.append(baseline)
                    assert set(penalties) == set(range(machines)) - locks
                    for machine, (delta, earliest, latest) in penalties.items():
                        assert delta == direct_makespan(times, locks | {machine}) - baseline
                        assert (delta == 0) == (earliest <= latest)
                        assert delta >= 0
                        if machine in (0, machines - 1):
                            assert delta == 0
                        zero += delta == 0
                        positive += delta > 0
                    schedules += 1
                for mask, baseline in enumerate(baseline_by_mask):
                    available = ((1 << machines) - 1) ^ mask
                    remaining = [
                        1 << machine for machine in range(machines)
                        if available & (1 << machine)
                    ]
                    for left, right in itertools.combinations(remaining, 2):
                        assert baseline + baseline_by_mask[mask | left | right] <= (
                            baseline_by_mask[mask | left] + baseline_by_mask[mask | right]
                        )
                        submodular_checks += 1
                    zero_set = sum(
                        bit for bit in remaining if baseline_by_mask[mask | bit] == baseline
                    )
                    extension = available
                    while extension:
                        assert (baseline_by_mask[mask | extension] == baseline) == (
                            (extension & zero_set) == extension
                        )
                        zero_set_checks += 1
                        extension = (extension - 1) & available
    return {
        "schedules": schedules,
        "zero": zero,
        "positive": positive,
        "submodular_checks": submodular_checks,
        "zero_set_checks": zero_set_checks,
    }


def endpoint_values(jobs, locks):
    orders = list(itertools.permutations(range(len(jobs))))
    return [direct_makespan(machine_times(jobs, order), locks) for order in orders]


def small_witnesses():
    checks = 0
    for a, b, c, d, e, f in itertools.product(range(1, 6), repeat=6):
        jobs = [(a, b, c), (d, e, f)]
        before = endpoint_values(jobs, set())
        after = endpoint_values(jobs, {1})
        assert after[0] - before[0] == min(max(0, d - b), max(0, c - e))
        assert after[1] - before[1] == min(max(0, a - e), max(0, f - b))
        difference = after[0] - after[1]
        assert difference * (before[0] - before[1]) >= 0
        if before[0] == before[1]:
            assert difference == 0
        checks += 1

    same_geometry = [(1, 3, 1, 1), (2, 1, 1, 3)]
    early, late = [endpoint_values(same_geometry, {machine}) for machine in (1, 2)]
    assert (early, late) == ([9, 8], [9, 10])
    three_by_three = [(1, 2, 2), (3, 1, 2), (2, 1, 1)]
    before = endpoint_values(three_by_three, set())
    after = endpoint_values(three_by_three, {1})
    assert (before, after) == ([8, 9, 9, 10, 9, 10], [10, 10, 9, 10, 10, 10])
    no_optimal_submodularity = [(3, 1, 1, 3), (1, 2, 2, 1)]
    landscapes = [
        endpoint_values(no_optimal_submodularity, locks)
        for locks in (set(), {1}, {2}, {1, 2})
    ]
    assert landscapes == [[9, 9], [9, 10], [10, 9], [10, 10]]
    return {
        "two_jobs_three_machines_checks": checks,
        "same_geometry": {"jobs": same_geometry, "second_machine": early, "third_machine": late},
        "three_by_three": {"jobs": three_by_three, "no_locks": before, "second_machine": after},
        "optimal_values_are_not_submodular": {
            "jobs": no_optimal_submodularity,
            "landscapes": landscapes,
            "optimal_values": [min(values) for values in landscapes],
        },
    }


def probe_comparison():
    randomizer = random.Random(2026112202)
    jobs, machines = 7, 8
    geometry = [min(machine, machines - 1 - machine) for machine in range(machines)]
    accounts = {
        name: {"correct": 0, "incorrect": 0, "tied_prediction": 0}
        for name in ("geometry", "probe_marginal")
    }
    tied_target = 0
    matrix_comparison = {"probe_better": 0, "geometry_better": 0, "tied": 0}
    for _ in range(40):
        durations = [
            [randomizer.randint(1, 30) for _ in range(machines)] for _ in range(jobs)
        ]
        locks = {randomizer.randrange(1, machines - 1)}
        orders = set()
        ordered_samples = []
        while len(ordered_samples) < 10:
            order = tuple(randomizer.sample(range(jobs), jobs))
            if order not in orders:
                ordered_samples.append(order)
                orders.add(order)
        probes, targets = ordered_samples[:5], ordered_samples[5:]
        candidates = sorted(set(range(1, machines - 1)) - locks)
        probe_sums = {machine: 0 for machine in candidates}
        target_sums = {machine: 0 for machine in candidates}
        for order in probes:
            _, marginal = all_penalties(machine_times(durations, order), locks)
            for machine in candidates:
                probe_sums[machine] += marginal[machine][0]
        for order in targets:
            times = machine_times(durations, order)
            base = direct_makespan(times, locks)
            for machine in candidates:
                target_sums[machine] += direct_makespan(times, locks | {machine}) - base
        matrix_score = dict.fromkeys(accounts, 0)
        for left, right in itertools.combinations(candidates, 2):
            truth = target_sums[left] - target_sums[right]
            if truth == 0:
                tied_target += 1
                continue
            for name, guess in (
                ("geometry", geometry[left] - geometry[right]),
                ("probe_marginal", probe_sums[left] - probe_sums[right]),
            ):
                outcome = "tied_prediction" if guess == 0 else (
                    "correct" if truth * guess > 0 else "incorrect"
                )
                accounts[name][outcome] += 1
                matrix_score[name] += {"correct": 2, "incorrect": 0, "tied_prediction": 1}[outcome]
        comparison = matrix_score["probe_marginal"] - matrix_score["geometry"]
        winner = "tied" if comparison == 0 else (
            "probe_better" if comparison > 0 else "geometry_better"
        )
        matrix_comparison[winner] += 1
    return {
        "matrix_count": 40,
        "tied_target": tied_target,
        "comparisons": accounts,
        "matrix_comparison": matrix_comparison,
    }


def timing_check():
    randomizer = random.Random(2026112203)
    timings = []
    repeats = 30
    for machines in (12, 24, 48, 96):
        times = [[randomizer.randint(1, 100) for _ in range(64)] for _ in range(machines)]
        locks = set(range(2, machines, 4))
        started = time.perf_counter()
        for _ in range(repeats):
            all_penalties(times, locks)
        scan = (time.perf_counter() - started) / repeats

        started = time.perf_counter()
        for _ in range(repeats):
            baseline = direct_makespan(times, locks)
            for machine in set(range(machines)) - locks:
                direct_makespan(times, locks | {machine}) - baseline
        reruns = (time.perf_counter() - started) / repeats
        timings.append({"machines": machines, "scan_ms": 1e3 * scan, "reruns_ms": 1e3 * reruns})
    return timings


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timing", action="store_true")
    args = parser.parse_args()
    output = {
        "exact_checks": exact_checks(),
        "witnesses": small_witnesses(),
        "probing": probe_comparison(),
    }
    if args.timing:
        output["illustrative_timing"] = timing_check()
    print(json.dumps(output, indent=2))
