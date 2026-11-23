"""Independent physical and combinatorial audit of minimum clock retention."""

from argparse import ArgumentParser
from hashlib import sha256
from itertools import combinations
import json
from pathlib import Path
from random import Random
import sys


HERE = Path(__file__).resolve().parent
LOCAL = HERE.parent / "flowshop_local_availability"
sys.path.insert(0, str(LOCAL))
from clock_retention import minimum_clock_retention, minimum_hitting_set, terminal_clock_terms
from local_timing import compile_machines, preprocess_clock_deletions


SEED = 874392031
GAP_CASES = 112
GENERAL_CASES = 84


def subsets(elements):
    elements = sorted(elements)
    return [frozenset(s) for size in range(len(elements) + 1) for s in combinations(elements, size)]


def latest(values):
    return max((v for v in values if v is not None), default=None)


def add(a, b):
    return None if a is None else a + b


def operate(problem, locked, retained, *, entry=True):
    """Track operation starts directly, with None for unreachable completions."""
    previous = problem["job_ready"] if entry else [None] * len(problem["job_ready"])
    for machine, processing in enumerate(problem["processing"]):
        releases, work = [], []
        for job, duration in enumerate(processing):
            transit = problem["transfer"][machine][job]
            anticipation = problem["lead"][machine][job]
            material = add(previous[job], transit)
            if machine in retained:
                material = latest((material, problem["material_ready"][machine][job]))
                release = latest((add(material, -anticipation), problem["setup_ready"][machine][job],
                                  problem["machine_ready"][machine]))
            else:
                release = add(material, -anticipation)
            releases.append(release)
            work.append(duration + problem["setup"][machine][job])
        occupied = 0
        if machine in locked:
            anchor = None
            for release, duration in zip(releases, work):
                anchor = latest((anchor, add(release, -occupied)))
                occupied += duration
            results = []
            for duration in work:
                anchor = add(anchor, duration)
                results.append(anchor)
        else:
            clock = None
            results = []
            for release, duration in zip(releases, work):
                clock = add(latest((clock, release)), duration)
                results.append(clock)
        previous = results
    return previous[-1]


def compile_line(problem, no_idle):
    rows = compile_machines(**{key: value for key, value in problem.items() if key != "job_ready"})
    return preprocess_clock_deletions(rows, problem["job_ready"], no_idle)


def knapsack_line(profits, weights, target, *, material=False):
    rows = [(1, 1 + profits[0])]
    for i, profit in enumerate(profits):
        rows.extend(((1, 1), (profit + 1, 1 + (profits[i + 1] if i + 1 < len(profits) else 0))))
    base = 2 * len(profits) + 2 + sum(profits)
    initial = 1 + sum(profits)
    terminal_floor = base + initial + target - 1
    final_clock = terminal_floor - sum(rows[-1])
    zero = [(0, 0)] * len(rows)
    machine_ready = [0] * len(rows)
    material_ready = list(zero)
    if material:
        material_ready[0], material_ready[-1] = (initial, 0), (final_clock, 0)
    else:
        machine_ready[0], machine_ready[-1] = initial, final_clock
    problem = {"processing": rows, "setup": zero, "setup_ready": zero, "lead": zero, "transfer": zero,
               "machine_ready": machine_ready, "material_ready": material_ready, "job_ready": [0, 0]}
    return problem, {2 * i + 1: w for i, w in enumerate(weights)}, base, initial, terminal_floor


def gap_check(rng):
    counts = {"models": GAP_CASES, "machine_and_material_encodings": 0, "optimum_one": 0,
              "optimum_two": 0, "feasible_scenarios": 0, "sub_one_retention_candidates_checked": 0}
    for _ in range(GAP_CASES):
        count = rng.randrange(1, 7)
        profit = [2 * rng.randrange(1, 21) for _ in range(count)]
        weight = [rng.randrange(1, 18) for _ in range(count)]
        budget = rng.randrange(sum(weight) + 1)
        target = 2 * rng.randrange(1, sum(profit) // 2 + 4)
        eligible = [s for s in subsets(range(count)) if sum(weight[i] for i in s) <= budget]
        reachable = any(sum(profit[i] for i in s) >= target for s in eligible)
        counts["optimum_two" if reachable else "optimum_one"] += 1
        for material in (False, True):
            problem, fees, base, first, floor = knapsack_line(profit, weight, target, material=material)
            terminal = len(problem["processing"]) - 1
            clocks = set(range(terminal + 1))
            tests = [frozenset(2 * i + 1 for i in s) for s in eligible]
            originals = [operate(problem, locked, clocks) for locked in tests]
            assert originals[0] == floor > base + first
            for scenario, (chosen, locked) in enumerate(zip(eligible, tests)):
                gains = sum(profit[i] for i in chosen)
                assert originals[scenario] == max(floor, base + first + gains)
                assert operate(problem, locked, {terminal}) == floor
                assert operate(problem, locked, {0, terminal}) == originals[scenario]
            accepted = []
            for kept in [frozenset(), *(frozenset({i}) for i in clocks)]:
                if [operate(problem, s, kept) for s in tests] == originals:
                    accepted.append(kept)
                counts["sub_one_retention_candidates_checked"] += 1
            assert accepted == ([] if reachable else [{terminal}])
            certificate = minimum_clock_retention(compile_line(problem, set()), fees, budget)
            assert certificate.retained == ({0, terminal} if reachable else {terminal})
            counts["feasible_scenarios"] += len(tests)
            counts["machine_and_material_encodings"] += 1
    return counts


def target_one_corner():
    problem, fees, base, first, floor = knapsack_line([2], [1], 1)
    terminal = len(problem["processing"]) - 1
    assignments = [set(), {1}]
    full = [operate(problem, s, {0, terminal}) for s in assignments]
    upstream = [operate(problem, s, {0}) for s in assignments]
    downstream = [operate(problem, s, {terminal}) for s in assignments]
    assert full == upstream == [9, 11] and downstream == [9, 9] and floor == base + first
    found = minimum_clock_retention(compile_line(problem, set()), fees, 1)
    assert found.retained == {0}
    return {"target": 1, "feasible_item_sets": [[], [0]], "full": full, "first_only": upstream,
            "terminal_only": downstream, "retained": sorted(found.retained)}


def positive_tolerance_corner():
    tolerance = 5
    scale = tolerance + 1
    problem, fees, _, _, _ = knapsack_line([2, 4], [1, 2], 4)
    scaled = {}
    for key, values in problem.items():
        if isinstance(values[0], int):
            scaled[key] = [value * scale for value in values]
        else:
            scaled[key] = [[value * scale for value in row] for row in values]
    terminal = len(problem["processing"]) - 1
    clocks = set(range(terminal + 1))
    model = compile_line(scaled, set())
    winners = []
    for budget, expected in ((1, {terminal}), (2, {0, terminal})):
        scopes = [s for s in subsets(fees) if sum(fees[i] for i in s) <= budget]
        full = {s: operate(scaled, s, clocks) for s in scopes}
        direct = next(keep for keep in subsets(clocks)
                      if all(full[s] - operate(scaled, s, keep) <= tolerance for s in scopes))
        result = minimum_clock_retention(model, fees, budget, maximum_loss=tolerance)
        assert result.retained == direct == expected
        winners.append({"budget": budget, "retained": sorted(result.retained)})
    return {"profits": [2, 4], "weights": [1, 2], "target_profit": 4,
            "tolerance": tolerance, "time_scale": scale, "cases": winners}


def sample_problem(rng, m, n, trial):
    def matrix(limit):
        return [[rng.randrange(limit) for _ in range(n)] for _ in range(m)]

    scale = 1 if trial % 3 else 10
    setup = matrix(1 if trial % 7 == 0 else 1 + 10 // scale)
    return {"processing": matrix(1 + 13 // scale), "setup": setup,
            "machine_ready": [rng.randrange(1 + 45 // scale) for _ in range(m)],
            "material_ready": matrix(1 + 60 // scale), "setup_ready": matrix(1 + 50 // scale),
            "transfer": matrix(1 + 11 // scale),
            "job_ready": [rng.randrange(1 + 80 // scale) for _ in range(n)],
            "lead": [[rng.randrange(work + 1) for work in row] for row in setup]}


def retention_check(rng):
    result = {"models": GENERAL_CASES, "retention_queries": 0, "isolated_sources": 0,
              "lock_scenarios": 0, "direct_retention_evaluations": 0, "violated_master_cuts": 0,
              "nonzero_tolerances": 0, "protected_cases": 0, "zero_price_lock_cases": 0}
    for trial in range(GENERAL_CASES):
        m, n = rng.randrange(1, 7), rng.randrange(1, 6)
        all_clocks = frozenset(range(m))
        problem = sample_problem(rng, m, n, trial)
        no_idle = {i for i in all_clocks if rng.randrange(4) == 0}
        protected = {i for i in all_clocks if rng.randrange(5) == 0}
        fees = {i: rng.randrange(5) for i in all_clocks - no_idle if rng.randrange(6)}
        model = compile_line(problem, no_idle)
        possible = subsets(fees)
        retained_options = [protected | subset for subset in subsets(all_clocks - protected)]
        sources = {}
        full = {}
        for locks in possible:
            actual = no_idle | locks
            direct_entry = operate(problem, actual, set())
            direct_terms = tuple(operate(problem, actual, {i}, entry=False) for i in range(m))
            assert terminal_clock_terms(model.machines, model.job_ready, actual) == (direct_entry, direct_terms)
            full[locks] = operate(problem, actual, all_clocks)
            assert max(direct_entry, *direct_terms) == full[locks]
            sources[locks] = direct_entry, direct_terms
            result["isolated_sources"] += m + 1
            result["lock_scenarios"] += 1
        for budget in sorted({0, sum(fees.values()), rng.randrange(sum(fees.values()) + 1)}):
            eps = (trial + budget) % 5
            ready = [locks for locks in possible if sum(fees[i] for i in locks) <= budget]

            def really_valid(retained):
                for locks in ready:
                    result["direct_retention_evaluations"] += 1
                    if full[locks] - operate(problem, no_idle | locks, retained) > eps:
                        return False
                return True

            independent = next(choice for choice in retained_options if really_valid(choice))
            certificate = minimum_clock_retention(model, fees, budget, protected=protected, maximum_loss=eps)
            assert protected <= certificate.retained and len(independent) == len(certificate.retained)
            assert really_valid(certificate.retained)
            supports = []
            for cut in certificate.cuts:
                assert cut.locks in ready and cut.full_makespan == full[cut.locks]
                entry, terms = sources[cut.locks]
                threshold = cut.full_makespan - eps
                assert entry < threshold and protected.isdisjoint(cut.clocks)
                assert cut.clocks == {i for i, value in enumerate(terms) if value >= threshold}
                assert cut.clocks & certificate.retained
                supports.append(cut.clocks)
            assert len(supports) == len(set(supports))
            assert all(not earlier <= later for i, later in enumerate(supports) for earlier in supports[:i])
            from_cuts = next(choice for choice in retained_options if all(choice & cut for cut in supports))
            assert len(from_cuts) == len(independent)
            result["retention_queries"] += 1
            result["violated_master_cuts"] += len(supports)
            result["nonzero_tolerances"] += int(eps > 0)
            result["protected_cases"] += int(bool(protected))
            result["zero_price_lock_cases"] += int(0 in fees.values())
    return result


def all_four_clock_masters():
    candidates = subsets(range(4))
    supports = candidates[1:]
    for choice in subsets(range(len(supports))):
        cuts = [supports[i] for i in choice]
        expected = next(retained for retained in candidates if all(retained & cut for cut in cuts))
        actual = minimum_hitting_set(cuts)
        assert len(actual) == len(expected) and all(actual & cut for cut in cuts)
    return 1 << len(supports)


def sources():
    files = [Path(__file__).resolve(), LOCAL / "clock_retention.py", LOCAL / "local_timing.py",
             HERE.parent / "flowshop_monge_budget/monge_budget.py"]
    return {str(path.relative_to(HERE.parent)): sha256(path.read_bytes()).hexdigest() for path in files}


def main():
    parser = ArgumentParser()
    parser.add_argument("--output", default=HERE / "results.json", type=Path)
    args = parser.parse_args()
    rng = Random(SEED)
    fingerprints = sources()
    results = {"seed": SEED, "sources": fingerprints, "cardinality_gap": gap_check(rng),
               "target_one_corner": target_one_corner(), "positive_tolerance_corner": positive_tolerance_corner(),
               "retention": retention_check(rng),
               "complete_four_clock_hypergraphs": all_four_clock_masters()}
    assert sources() == fingerprints
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(results, stream, indent=2)
        stream.write("\n")
    print(json.dumps({key: results[key] for key in ("cardinality_gap", "retention", "complete_four_clock_hypergraphs")}))


if __name__ == "__main__":
    main()
