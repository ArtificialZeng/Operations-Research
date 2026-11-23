"""Fixed-permutation checkpoint optimization with local material and setup dates."""

from collections import ChainMap
from dataclasses import dataclass
from fractions import Fraction
from itertools import accumulate, pairwise
from pathlib import Path
import sys


EXPERIMENTS = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(EXPERIMENTS / directory) for directory in ("flowshop_monge_budget", "flowshop_release_approx")]
from monge_budget import Envelope, solve_graph
from source_approx import certify_sources, source_problem


@dataclass(frozen=True)
class Machine:
    duration_prefix: tuple[int, ...]
    upstream_offset: tuple[int, ...]
    absolute_clock: tuple[int, ...]


@dataclass(frozen=True)
class ClockDeletionModel:
    machines: tuple[Machine, ...]
    job_ready: tuple[int, ...]
    compulsory: tuple[int, ...]
    homogeneous: dict[tuple[int, int], int]
    full_baseline: tuple[int, ...]


@dataclass(frozen=True)
class ClockDeletionQuery:
    compulsory: tuple[int, ...]
    homogeneous: dict[tuple[int, int], int]
    fees: dict[int, int]
    origins: dict[int, tuple[int, int]]
    baseline_start: tuple[int, ...]


def compile_machines(processing, setup, machine_ready, material_ready, setup_ready, transfer, lead):
    machines = []
    for i, durations in enumerate(processing):
        if any(not 0 <= ahead <= s for ahead, s in zip(lead[i], setup[i])):
            raise ValueError("Setup anticipation must lie between zero and the setup duration")
        prefix = tuple(accumulate(p + s for p, s in zip(durations, setup[i])))
        prior = (0, *prefix[:-1])
        relative = tuple(p + ahead for p, ahead in zip(prior, lead[i]))
        upstream = tuple(offset - transit for offset, transit in zip(relative, transfer[i]))
        clock = tuple(max(machine_ready[i], supply - offset, preparation - p)
                      for supply, offset, preparation, p in zip(material_ready[i], relative, setup_ready[i], prior))
        machines.append(Machine(prefix, upstream, clock))
    return machines


def advance(machine, incoming, inject):
    """Return the start if locked and the completion vector if it may idle."""
    if incoming is None:
        if not inject:
            return None, None
        clocks = machine.absolute_clock
    else:
        clocks = [value - offset for value, offset in zip(incoming, machine.upstream_offset)]
        if inject:
            clocks = [max(upstream, local) for upstream, local in zip(clocks, machine.absolute_clock)]
    starts = list(accumulate(clocks, max))
    return starts[-1], [left + length for left, length in zip(starts, machine.duration_prefix)]


def evaluate(machines, job_ready, locked, *, retained=None):
    incoming = job_ready
    for i, machine in enumerate(machines):
        start, incoming = advance(machine, incoming, retained is None or i in retained)
        if i in locked:
            incoming = [start + p for p in machine.duration_prefix]
    return incoming[-1]


def minimum_clock_support(machines, job_ready, fixed):
    """Find the smallest set of local bounds preserving all completions."""
    incoming = job_ready
    support = []
    for i, machine in enumerate(machines):
        full_start, opened = advance(machine, incoming, True)
        arrivals = [v - offset for v, offset in zip(incoming, machine.upstream_offset)]
        if i in fixed:
            if full_start > max(arrivals):
                support.append((i, machine.absolute_clock.index(full_start)))
            incoming = [full_start + p for p in machine.duration_prefix]
        else:
            previous = None
            for t, (value, clock) in enumerate(zip(arrivals, machine.absolute_clock)):
                prefix = value if previous is None else max(previous, value)
                if clock > prefix:
                    support.append((i, t))
                previous = max(prefix, clock)
            incoming = opened
    return support


def all_clocks_redundant(machines, job_ready, fixed):
    return not minimum_clock_support(machines, job_ready, fixed)


def suffix_clock_error(machines, job_ready, fixed, costs, budget, first_removed=0):
    """Maximize the makespan change from deleting a suffix of local clocks."""
    full = reduced = job_ready
    terminal = len(machines) - 1
    maximum, witness = 0, None
    for i, machine in enumerate(machines):
        full_start, full = advance(machine, full, True)
        reduced_start, reduced = advance(machine, reduced, i < first_removed)
        difference = full_start - reduced_start
        if difference > maximum:
            if i in fixed or i == terminal:
                maximum, witness = difference, frozenset()
            elif i in costs and costs[i] <= budget:
                maximum, witness = difference, frozenset({i})
        if i in fixed:
            full = [full_start + duration for duration in machine.duration_prefix]
            reduced = [reduced_start + duration for duration in machine.duration_prefix]
    return maximum, witness


def suffix_clock_witness(machines, job_ready, fixed, costs, budget, first_removed=0):
    """Find an empty or singleton lock set witnessing a makespan change."""
    return suffix_clock_error(machines, job_ready, fixed, costs, budget, first_removed)[1]


def checkpoint_graph(machines, job_ready, fixed, candidates, *, retained=None, record_floor=True):
    compulsory = sorted(set(fixed) | {-1, len(machines) - 1})
    eligible = set(compulsory) | set(candidates)
    homogeneous, floor = {}, {}
    for left, right in pairwise(compulsory):
        for i in range(left, right):
            if i not in eligible:
                continue
            from_start = job_ready if i < 0 else machines[i].duration_prefix
            from_local = None
            for j in range(i + 1, right + 1):
                start, from_start = advance(machines[j], from_start, False)
                if record_floor:
                    clock, from_local = advance(machines[j], from_local, retained is None or j in retained)
                if j in eligible:
                    homogeneous[i, j] = start
                    if record_floor:
                        floor[i, j] = clock
    return (compulsory, homogeneous, machines[-1].duration_prefix[-1]), floor


def compulsory_clock_starts(machines, job_ready, compulsory, deleted):
    """Record the hypothetical locked start at each machine, advancing in compulsory-only mode."""
    incoming = job_ready
    locked = set(compulsory)
    starts = []
    for i, machine in enumerate(machines):
        start, incoming = advance(machine, incoming, i not in deleted)
        starts.append(start)
        if i in locked:
            incoming = [start + p for p in machine.duration_prefix]
    return tuple(starts)


def preprocess_clock_deletions(machines, job_ready, fixed):
    """Store the homogeneous arcs and full compulsory baseline for repeated queries."""
    machines, job_ready = tuple(machines), tuple(job_ready)
    graph, _ = checkpoint_graph(machines, job_ready, fixed, range(len(machines)), record_floor=False)
    compulsory, homogeneous, _ = graph
    full_baseline = compulsory_clock_starts(machines, job_ready, compulsory, frozenset())
    return ClockDeletionModel(machines, job_ready, tuple(compulsory), homogeneous, full_baseline)


def deletion_problem(model, costs, budget, deleted):
    deleted = frozenset(deleted)
    compulsory = model.compulsory
    mandatory = set(compulsory)
    fee = {i: 0 if i in mandatory else costs[i] for i in range(compulsory[-1] + 1)
           if i in mandatory or (i in costs and costs[i] <= budget)}
    baseline = compulsory_clock_starts(model.machines, model.job_ready, compulsory, deleted)
    origins = {j: (model.full_baseline[j], model.full_baseline[j] - baseline[j])
               for j in fee if model.full_baseline[j] > baseline[j]}
    return ClockDeletionQuery(compulsory, model.homogeneous, fee, origins, baseline)


def seed_states(problem, j, target):
    if j in problem.origins:
        start, difference = problem.origins[j]
        if difference >= target:
            return {problem.fees[j]: (start, None)}
    return {}


def record_start(current, paid, start, predecessor):
    if paid not in current or start > current[paid][0]:
        current[paid] = (start, predecessor)


def guarded_path(problem, budget, target, *, reference_floor=None):
    states = {}
    for j, price in problem.fees.items():
        current = seed_states(problem, j, target)
        for i, previous in states.items():
            edge = i, j
            if edge not in problem.homogeneous:
                continue
            for spend, (start, _) in previous.items():
                arriving = start + problem.homogeneous[edge]
                paid = spend + price
                retained_start = problem.baseline_start[j] if reference_floor is None else reference_floor[edge]
                if paid > budget or (retained_start is not None and arriving - retained_start < target):
                    continue
                record_start(current, paid, arriving, i)
        states[j] = current
    return reconstruct_path(states, problem.fees, problem.compulsory)


def guarded_envelopes(problem, budget, target):
    """Use one envelope per cost because the baseline guard is independent of the predecessor."""
    states = {-1: {}}
    for left, right in pairwise(problem.compulsory):
        positions = [left, *(j for j in range(left + 1, right + 1) if j in problem.fees)]
        hulls = {}

        def add_rows(i, scores, first_column):
            for spent, (start, _) in scores.items():
                if spent not in hulls:
                    hulls[spent] = Envelope(problem.homogeneous, positions)
                hulls[spent].add((i, start), first_column)

        add_rows(left, states[left], 1)
        for slot, j in enumerate(positions[1:], 1):
            current = seed_states(problem, j, target)
            threshold = problem.baseline_start[j] + target
            for spent, hull in hulls.items():
                paid = spent + problem.fees[j]
                if paid > budget:
                    continue
                i, start = hull.best(slot)
                if start >= threshold:
                    record_start(current, paid, start, i)
            states[j] = current
            if j < right:
                add_rows(j, current, slot + 1)
    return reconstruct_path(states, problem.fees, problem.compulsory)


def reconstruct_path(states, fees, compulsory):
    terminal = compulsory[-1]
    if not states[terminal]:
        return None
    required = set(compulsory)
    added = set()
    spend = min(states[terminal])
    pos = terminal
    while pos is not None:
        if pos not in required:
            added.add(pos)
        _, previous = states[pos][spend]
        spend -= fees[pos]
        pos = previous
    return frozenset(added)


def arbitrary_clock_witness(machines, job_ready, fixed, costs, budget, deleted, *, target=1, use_envelopes=True):
    """Find a feasible lock set with makespan change at least a positive target."""
    if type(target) is not int or target < 1:
        raise ValueError("Expected a positive integer target")
    model = preprocess_clock_deletions(machines, job_ready, fixed)
    problem = deletion_problem(model, costs, budget, deleted)
    solver = guarded_envelopes if use_envelopes else guarded_path
    return solver(problem, budget, target)


def arbitrary_clock_error(machines, job_ready, fixed, costs, budget, deleted):
    """Return the maximum discrepancy and its witness for arbitrary deletion."""
    model = preprocess_clock_deletions(machines, job_ready, fixed)
    return maximum_deletion_error(model, costs, budget, deleted)


def maximum_deletion_error(model, costs, budget, deleted, *, use_envelopes=True):
    """Run one exact error query against a preprocessed line."""
    problem = deletion_problem(model, costs, budget, deleted)
    full_makespan = evaluate(model.machines, model.job_ready, problem.fees)
    reduced_makespan = problem.baseline_start[-1] + model.machines[-1].duration_prefix[-1]
    upper = full_makespan - reduced_makespan
    solver = guarded_envelopes if use_envelopes else guarded_path
    lower, witness = 0, None
    while lower < upper:
        target = (lower + upper + 1) // 2
        candidate = solver(problem, budget, target)
        if candidate is None:
            upper = target - 1
        else:
            lower, witness = target, candidate
    return lower, witness


def local_origin_arcs(machines, compulsory, source):
    """Create the first arcs of the material/setup source at a real machine."""
    anchor = source - 1
    until = next(j for j in compulsory if j >= source)
    incoming = None
    first = {}
    for j in range(source, until + 1):
        start, incoming = advance(machines[j], incoming, j == source)
        first[anchor, j] = start
    return first


def exact(machines, job_ready, fixed, costs, budget, *, use_envelopes=True):
    graph, floor = checkpoint_graph(machines, job_ready, fixed, costs)
    return solve_graph(*graph, costs, budget, use_envelopes=use_envelopes, constants=floor)


def approximate(machines, job_ready, fixed, costs, budget, eta):
    eta = Fraction(eta)
    if not 0 < eta < 1 or budget < 0 or any(cost <= 0 for cost in costs.values()):
        raise ValueError("Expected 0 < eta < 1, a nonnegative budget and positive costs")

    (compulsory, homogeneous, tail), _ = checkpoint_graph(machines, job_ready, fixed, costs)
    baseline = evaluate(machines, job_ready, fixed)
    start_offsets = [0] * len(machines)
    problems = []
    for clock in range(-1, len(machines)):
        if clock == -1:
            anchor, arcs = -1, homogeneous
        else:
            anchor = clock - 1
            arcs = ChainMap(local_origin_arcs(machines, compulsory, clock), homogeneous)
        vertices, charge, edges, beta, cap = source_problem(anchor, compulsory, arcs, tail, start_offsets, costs, budget)
        problems.append((beta + cap - baseline, clock, vertices, charge, edges, beta, cap))

    def physical_value(chosen):
        return evaluate(machines, job_ready, fixed | set(chosen)) - baseline

    return certify_sources(problems, baseline, budget, eta, physical_value)
