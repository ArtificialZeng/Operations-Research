"""Audit F-only seeds and one-envelope deletion queries against operation simulation."""

from argparse import ArgumentParser
from dataclasses import dataclass
from hashlib import sha256
from itertools import accumulate, combinations, pairwise
import json
from pathlib import Path
from random import Random
import sys


HERE = Path(__file__).resolve().parent
ENVELOPE_SOURCE = HERE.parent / "flowshop_monge_budget/monge_budget.py"
sys.path.insert(0, str(ENVELOPE_SOURCE.parent))
from monge_budget import Envelope


SEED = 44872229
TRIALS = 180


@dataclass(frozen=True)
class Row:
    prefix: tuple
    upstream_offset: tuple
    local: tuple

    def advance(self, incoming, retained):
        normalized = [value - offset for value, offset in zip(incoming, self.upstream_offset)]
        if retained:
            normalized = [max(value, local) for value, local in zip(normalized, self.local)]
        partial = list(accumulate(normalized, max))
        return partial[-1], [start + length for start, length in zip(partial, self.prefix)]

    def locked(self, start):
        return [start + length for length in self.prefix]


def compile_rows(problem):
    rows = []
    for i, processing in enumerate(problem["processing"]):
        setup = problem["setup"][i]
        after = tuple(accumulate(p + s for p, s in zip(processing, setup)))
        before = (0, *after[:-1])
        anticipate = [v + lead for v, lead in zip(before, problem["lead"][i])]
        upstream = tuple(offset - delay for offset, delay in zip(anticipate, problem["transfer"][i]))
        local = tuple(max(problem["machine_ready"][i], material - offset, ready - prefix)
                      for material, offset, ready, prefix in zip(
                          problem["material_ready"][i], anticipate, problem["setup_ready"][i], before))
        rows.append(Row(after, upstream, local))
    return rows


def prefix_starts(rows, source, forced, retained):
    starts = []
    incoming = source
    for i, row in enumerate(rows):
        start, incoming = row.advance(incoming, i in retained)
        if i in forced:
            incoming = row.locked(start)
        starts.append(start)
    return starts


def homogeneous_arcs(rows, compulsory):
    """Store coordinate shifts only between actual machines."""
    arcs = {}
    for left, right in pairwise(compulsory):
        for i in range(max(left, 0), right):
            incoming = rows[i].prefix
            for j in range(i + 1, right + 1):
                arcs[i, j], incoming = rows[j].advance(incoming, False)
    return arcs


def record(states, spent, start, predecessor):
    if spent not in states or start > states[spent][0]:
        states[spent] = start, predecessor


def prefix_envelope(compulsory, arcs, fees, budget, full, reduced, threshold):
    """Return added locks and the represented trace for a successful threshold."""
    histories = {-1: {}}
    forced = set(compulsory)
    for left, right in pairwise(compulsory):
        points = [left, *(i for i in range(left + 1, right) if i in fees and fees[i] <= budget), right]
        envelopes = {}

        def insert(i, states, first_column):
            for spent, (start, _) in states.items():
                if spent not in envelopes:
                    envelopes[spent] = Envelope(arcs, points)
                envelopes[spent].add((i, start), first_column)

        insert(left, histories[left], 1)
        for column, j in enumerate(points[1:], 1):
            charge = 0 if j in forced else fees[j]
            bound = reduced[j] + threshold
            state = {charge: (full[j], None)} if full[j] >= bound else {}
            for spent, envelope in envelopes.items():
                if spent + charge <= budget:
                    predecessor, candidate = envelope.best(column)
                    if candidate >= bound:
                        record(state, spent + charge, candidate, predecessor)
            histories[j] = state
            if j < right:
                insert(j, state, column + 1)

    j = compulsory[-1]
    if not histories[j]:
        return None
    spent = min(histories[j])
    chosen, trace = set(), []
    while j is not None:
        start, incoming = histories[j][spent]
        trace.append((j, start, spent))
        if j not in forced:
            chosen.add(j)
            spent -= fees[j]
        j = incoming
    assert spent == 0
    return frozenset(chosen), tuple(reversed(trace))


def direct_operations(problem, locked, retained):
    """Simulate each operation using its physical start constraints."""
    previous = problem["job_ready"]
    finishes = []
    for i, processing in enumerate(problem["processing"]):
        lengths = [duration + setup for duration, setup in zip(processing, problem["setup"][i])]
        releases = []
        for t, incoming in enumerate(previous):
            material = incoming + problem["transfer"][i][t]
            if i in retained:
                material = max(material, problem["material_ready"][i][t])
            ready = material - problem["lead"][i][t]
            if i in retained:
                ready = max(ready, problem["machine_ready"][i], problem["setup_ready"][i][t])
            releases.append(ready)
        if i in locked:
            row_start = max(ready - executed for ready, executed in zip(releases, accumulate(lengths, initial=0)))
            ends = [row_start + elapsed for elapsed in accumulate(lengths)]
        else:
            clock = releases[0]
            ends = []
            for earliest, work in zip(releases, lengths):
                clock = max(clock, earliest) + work
                ends.append(clock)
        finishes.append(tuple(ends))
        previous = ends
    return tuple(finishes)


def subsets(items):
    return [frozenset(row) for size in range(len(items) + 1) for row in combinations(items, size)]


def random_problem(rng, m, n, zero_work=False):
    def matrix(high):
        return [[rng.randrange(high + 1) for _ in range(n)] for _ in range(m)]

    setup = matrix(0 if zero_work else 16)
    return {"processing": matrix(0 if zero_work else 22), "setup": setup,
            "machine_ready": [rng.randrange(121) for _ in range(m)],
            "material_ready": matrix(170), "setup_ready": matrix(110), "transfer": matrix(21),
            "job_ready": [rng.randrange(101) for _ in range(n)],
            "lead": [[rng.randrange(s + 1) for s in row] for row in setup]}


def audit_trace(certificate, threshold, rows, compulsory, arcs, fees, budget, full_schedules, reduced_schedules):
    chosen, trace = certificate
    assert sum(fees[j] for j in chosen) == trace[-1][2] <= budget
    assert trace[-1][0] == compulsory[-1]
    full, reduced = full_schedules[chosen], reduced_schedules[chosen]
    for j, lower, _ in trace:
        tail = rows[j].prefix[-1]
        full_start, reduced_start = full[j][-1] - tail, reduced[j][-1] - tail
        assert full_start >= lower >= reduced_start + threshold
    seed, initial, _ = trace[0]
    assert initial == full[seed][-1] - rows[seed].prefix[-1]
    assert all(j >= seed for j in chosen)
    assert {j for j, _, _ in trace} == chosen | {j for j in compulsory if j >= seed}
    for (i, start, spent), (j, after, next_spent) in pairwise(trace):
        assert start + arcs[i, j] == after
        assert spent + (fees[j] if j in chosen else 0) == next_spent
    return full[-1][-1] - reduced[-1][-1]


def audit_suite():
    rng = Random(SEED)
    totals = {"matrices": TRIALS, "budget_deletion_queries": 0, "threshold_tests": 0,
              "independent_schedule_pairs": 0, "positive_certificates": 0, "trace_states": 0,
              "certificates_with_zero_fee_lock": 0, "certificates_crossing_forced_machine": 0,
              "queries_with_zero_fee_candidates": 0, "queries_with_retained_terminal": 0,
              "real_arc_anti_monge_checks": 0}
    for case in range(TRIALS):
        m, n = rng.randrange(1, 9), rng.randrange(1, 6)
        problem = random_problem(rng, m, n, zero_work=case % 8 == 0)
        forced = {i for i in range(m) if rng.random() < 0.40} | {m - 1}
        fees = {i: rng.randrange(8) for i in range(m - 1) if i not in forced and rng.random() < 0.85}
        possible = subsets(fees)
        rows = compile_rows(problem)
        actual = set(range(m))
        compulsory = (-1, *sorted(forced))
        arcs = homogeneous_arcs(rows, compulsory)
        assert all(i >= 0 for i, _ in arcs)
        for left, right in pairwise(compulsory):
            for i, j, k, ell in combinations(range(max(left, 0), right + 1), 4):
                assert arcs[i, k] + arcs[j, ell] >= arcs[i, ell] + arcs[j, k]
                totals["real_arc_anti_monge_checks"] += 1
        full_starts = prefix_starts(rows, problem["job_ready"], forced, actual)
        full = {extra: direct_operations(problem, forced | extra, actual) for extra in possible}
        for j in actual:
            profile = direct_operations(problem, forced | {j}, actual)
            assert full_starts[j] + rows[j].prefix[-1] == profile[j][-1]
        for scenario in range(9):
            retained = set() if scenario == 0 else actual if scenario == 1 else {i for i in actual if rng.getrandbits(1)}
            reduced_starts = prefix_starts(rows, problem["job_ready"], forced, retained)
            reduced = {extra: direct_operations(problem, forced | extra, retained) for extra in possible}
            error = {extra: original[-1][-1] - reduced[extra][-1][-1] for extra, original in full.items()}
            totals["independent_schedule_pairs"] += len(error)
            assert error[frozenset()] == full_starts[-1] - reduced_starts[-1]
            for j in actual:
                if j in forced:
                    assert reduced_starts[j] + rows[j].prefix[-1] == reduced[frozenset()][j][-1]
                else:
                    profile = direct_operations(problem, forced | {j}, retained)
                    assert reduced_starts[j] + rows[j].prefix[-1] == profile[j][-1]
            for budget in {0, rng.randrange(18), sum(fees.values())}:
                eligible = {choice: d for choice, d in error.items() if sum(fees[j] for j in choice) <= budget}
                best = max(eligible.values())
                totals["budget_deletion_queries"] += 1
                totals["queries_with_zero_fee_candidates"] += int(0 in fees.values())
                totals["queries_with_retained_terminal"] += int(m - 1 in retained)
                for target in {1, max(1, best // 2), max(1, best), best + 1}:
                    result = prefix_envelope(compulsory, arcs, fees, budget, full_starts, reduced_starts, target)
                    totals["threshold_tests"] += 1
                    assert (result is None) == (best < target)
                    if result is not None:
                        achieved = audit_trace(result, target, rows, compulsory, arcs, fees, budget, full, reduced)
                        assert target <= achieved <= best
                        chosen, trace = result
                        totals["positive_certificates"] += 1
                        totals["trace_states"] += len(trace)
                        totals["certificates_with_zero_fee_lock"] += int(any(fees[j] == 0 for j in chosen))
                        totals["certificates_crossing_forced_machine"] += int(any(j in forced for j, _, _ in trace[1:-1]))
    return totals


def fixture(durations, machine_ready, material_ready=None):
    n, m = len(durations[0]), len(durations)
    zeros = [[0] * n for _ in durations]
    return {"processing": durations, "setup": zeros, "machine_ready": machine_ready,
            "material_ready": zeros if material_ready is None else material_ready,
            "setup_ready": zeros, "transfer": zeros, "lead": zeros, "job_ready": [0] * n}


def audit_fixture(problem, forced, fees, deleted, budget, threshold, expected):
    rows = compile_rows(problem)
    all_machines = set(range(len(rows)))
    forced = forced | {len(rows) - 1}
    retained = all_machines - deleted
    compulsory = (-1, *sorted(forced))
    arcs = homogeneous_arcs(rows, compulsory)
    z0 = prefix_starts(rows, problem["job_ready"], forced, all_machines)
    r0 = prefix_starts(rows, problem["job_ready"], forced, retained)
    achieved = prefix_envelope(compulsory, arcs, fees, budget, z0, r0, threshold)
    assert (None if achieved is None else achieved[0]) == expected
    full = {extra: direct_operations(problem, forced | extra, all_machines) for extra in subsets(fees)}
    reduced = {extra: direct_operations(problem, forced | extra, retained) for extra in subsets(fees)}
    schedules = {str(sorted(extra)): [full[extra][-1][-1], reduced[extra][-1][-1]] for extra in full}
    if achieved is not None:
        audit_trace(achieved, threshold, rows, compulsory, arcs, fees, budget, full, reduced)
    else:
        assert all(full[extra][-1][-1] - reduced[extra][-1][-1] < threshold
                   for extra in full if sum(fees[j] for j in extra) <= budget)
    return {"fixture": problem, "forced": sorted(forced), "costs": fees, "deleted": sorted(deleted),
            "budget": budget, "threshold": threshold, "full_and_reduced_makespans": schedules,
            "Z0": z0, "R0": r0, "added": None if achieved is None else sorted(achieved[0]),
            "trace_machine_start_spend": None if achieved is None else achieved[1]}


def corners():
    free = fixture([[1, 1], [100, 1]], [0, 0], [[0, 10], [0, 0]])
    rolled = fixture([[1, 3], [0, 3], [1, 1], [3, 4], [1, 1], [4, 1]], [6, 0, 0, 0, 0, 19])
    large = 10**400
    wide = audit_fixture(fixture([[1, 1]], [large]), {0}, {}, {0}, 0, large, set())
    wide_full, wide_reduced = wide["full_and_reduced_makespans"]["[]"]
    return {
        "zero_fee_optional_first_machine": audit_fixture(free, set(), {0: 0}, {0}, 0, 9, {0}),
        "compulsory_prefix_then_two_optional_locks": audit_fixture(rolled, {1}, {2: 0, 4: 1}, {0}, 1, 1, {2, 4}),
        "compulsory_prefix_insufficient_budget": audit_fixture(rolled, {1}, {2: 0, 4: 1}, {0}, 0, 1, None),
        "compulsory_terminal_only_wide_integer": {
            "processing": [[1, 1]], "forced": [0], "deleted": [0], "budget": 0,
            "machine_ready_decimal_exponent": 400, "threshold_decimal": str(large),
            "full_makespan_decimal": str(wide_full), "reduced_makespan": wide_reduced, "added": wide["added"],
        },
        "retained_terminal_no_error": audit_fixture(fixture([[1, 1]], [10]), {0}, {}, set(), 0, 1, None),
    }


def main():
    parser = ArgumentParser()
    parser.add_argument("--output", type=Path, default=HERE / "results.json")
    args = parser.parse_args()
    result = {"seed": SEED, "envelope_sha256": sha256(ENVELOPE_SOURCE.read_bytes()).hexdigest(),
              "solver_source_sha256": sha256(Path(__file__).read_bytes()).hexdigest(),
              "corners": corners(), "randomized": audit_suite()}
    with args.output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2)
        stream.write("\n")


if __name__ == "__main__":
    main()
