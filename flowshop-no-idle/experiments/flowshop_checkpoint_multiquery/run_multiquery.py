"""Paired exact fixed-order solvers with warm graphs and reusable terminal labels."""

from bisect import bisect_right
from hashlib import sha256
from inspect import getsource
from itertools import accumulate, combinations
from math import ceil
from pathlib import Path
from runpy import run_path
from statistics import median
from time import process_time_ns
import argparse
import json
import os
import random
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
POSITIONS = HERE.parent / "flowshop_deadline_certificate" / "run_certificate.py"
SPARSE = HERE.parent / "flowshop_checkpoint_graph" / "checkpoint.py"
MONGE = HERE.parent / "flowshop_monge_budget" / "monge_budget.py"
ORACLES = HERE.parent / "flowshop_position_penalty"
DENSE = ORACLES / "worst_lock.py"
CHECKER = ROOT / "antigravity" / "data_confirmatory" / "ruiz2007" / "feasibility_check.py"
PUBLIC = ROOT / "antigravity" / "data_confirmatory" / "ruiz2007" / "instance"
PUBLIC_HASHES = (
    "a5339af2edc0a08b59e59309c4215381ba840fc27364bed3d4244249652a1e64",
    "510b5d253e711ea0b4b16b511cd41f0f240cdd0efca888d795cd0148b18e36df",
    "0499b184331768ee26f1cc8184944e936e099457994b5777c8aa044603b082a3",
    "8d453c611ba621b4e305bf8ca388913cdf63d5df9c75330edf4d6297555d1f88",
    "c0e8d73abece021d175f1a3eed1fb4a96b54840fe33f694d53f26d3a825a5804",
)
METHODS = ("position_sparse", "checkpoint_sparse", "checkpoint_plain", "checkpoint_envelope")
PHASES = ("low", "scan", "alt", "wide")
REPEATS = 3


def digest(source):
    return sha256(source).hexdigest()


def returning_terminal(function, marker, output, changes=()):
    """Reuse an archived recurrence with a different terminal view."""
    source = getsource(function)
    assert source.count(marker) == 1
    body = source.split(marker, 1)[0]
    for original, replacement in changes:
        assert body.count(original) == 1
        body = body.replace(original, replacement)
    namespace = {}
    exec(compile(body + f"    return {output}\n", function.__code__.co_filename, "exec"), function.__globals__, namespace)
    return namespace[function.__name__]


ref = run_path(str(POSITIONS))
sparse = run_path(str(SPARSE))
monge = run_path(str(MONGE))
direct = ref["direct"]
position_terminal = returning_terminal(
    ref["sparse_exact"], "    cost, best, mask = previous[-1][-1]", "previous[-1], labels",
    (("def sparse_exact(times,", "def sparse_exact(prefixes,"),
     ("jobs = len(times[0])", "jobs = len(prefixes[0]) - 1"),
     ("for i, row in enumerate(times):\n        prefix = tuple(accumulate(row, initial=0))",
      "for i, prefix in enumerate(prefixes):")),
)
checkpoint_terminal = returning_terminal(
    sparse["checkpoint_exact"], "    cost, delay, mask = fronts[len(graph.incoming) - 1][-1]",
    "fronts[len(graph.incoming) - 1], retained",
)
budget_terminal = returning_terminal(
    monge["solve_graph"], "    spent, best = max(frontier.items()", "frontier, parent, len(parent)",
)
dense_terminal = returning_terminal(
    run_path(str(DENSE))["worst_lock_set"], "    slot = jobs - 1\n    remaining = budget",
    "tuple(by_slot[-1] for by_slot in values)",
)


def matrices():
    for i, expected_hash in enumerate(PUBLIC_HASHES, 1):
        path = PUBLIC / f"large_instance_{i}.json"
        data = path.read_bytes()
        assert digest(data) == expected_hash
        instance = json.loads(data)
        n, m = instance["n_jobs"], instance["n_machines"]
        processing = instance["processing_times"]
        locked = {m // 2}
        columns = [[processing[j][i] for j in range(n)] for i in range(m)]
        order = ref["neh"](n, m, columns, [i in locked for i in range(m)])
        times = [[row[j] for j in order] for row in columns]
        source = {"sha256": expected_hash, "raw_grid": [len(processing), len(processing[0])]}
        yield path.stem, "public", times, locked, list(order), source

    families = ((256, 24, ()), (384, 20, (5, 10, 15)), (192, 40, (20,)), (512, 16, (4, 8, 12)))
    for index, (jobs, machines, anchors) in enumerate(families, 1):
        seed = 2026112810 + index
        rng = random.Random(seed)
        rows = []
        for job in range(jobs):
            row = []
            for i in range(machines):
                value = rng.randint(5, 83)
                if index == 2 and job % 3 == (i // 3) % 3:
                    value += rng.randint(17, 57)
                if index == 3 and i in (8, 32):
                    value += rng.randint(20, 75)
                if index == 4:
                    value += ((job // 8) % 3) * (i // 4 + 1)
                row.append(value)
            rows.append(row)
        order = sorted(range(jobs), key=lambda j: (-sum(rows[j]), j))
        times = [[rows[j][i] for j in order] for i in range(machines)]
        yield f"synthetic_{jobs}x{machines}", "synthetic", times, set(anchors), order, {"seed": seed}


def price_queries(choices, index):
    rng = random.Random(2026112840 + index)
    base = {i: rng.randint(1, 9) for i in choices}
    cap = min(64, sum(base.values()) // 3)
    scan = tuple(sorted({max(1, cap // 6), cap // 3, 2 * cap // 3, cap}))
    alt = {i: rng.randint(1, 13) for i in choices}
    wide = {i: rng.randint(1 << 30, (1 << 31) - 1) for i in choices}
    return {"low": (base, (scan[0],)), "scan": (base, scan),
            "alt": (alt, (min(64, sum(alt.values()) // 3),)),
            "wide": (wide, (3 * (1 << 30) - 1,))}


def measure(function, *args):
    started = process_time_ns()
    result = function(*args)
    return result, process_time_ns() - started


def prefixes(times):
    return [tuple(accumulate(row, initial=0)) for row in times]


def prepare(times, locked, eligible):
    data, build_ns = {}, {}
    data["position_sparse"], build_ns["position_sparse"] = measure(prefixes, times)
    data["checkpoint_sparse"], build_ns["checkpoint_sparse"] = measure(sparse["checkpoint_graph"], times, locked)
    graph, graph_ns = measure(monge["build_graph"], times, locked, eligible)
    for arm in ("checkpoint_plain", "checkpoint_envelope"):
        data[arm], build_ns[arm] = graph, graph_ns
    return data, build_ns


def profiled(method, prepared, locked, costs, cap):
    if method == "position_sparse":
        labels, states = position_terminal(prepared, locked, costs, cap)
        return labels, None, None, states
    if method == "checkpoint_sparse":
        labels, states = checkpoint_terminal(prepared, costs, cap)
        makespans = [(cost, delta + prepared.baseline, mask) for cost, delta, mask in labels]
        return makespans, None, None, states

    compulsory, _, tail = prepared
    frontier, parent, states = budget_terminal(*prepared, costs, cap, use_envelopes=method == "checkpoint_envelope")
    labels = []
    for spent, value in sorted(frontier.items()):
        best = value + tail
        if not labels or best > labels[-1][1]:
            labels.append((spent, best, None))
    return labels, parent, compulsory, states


def query(profile, budgets, machines):
    labels, parent, compulsory, _ = profile
    ascending = [item[0] for item in labels]
    answers = []
    for cap in budgets:
        cost, value, mask = labels[bisect_right(ascending, cap) - 1]
        if parent is None:
            witness = [i for i in range(machines) if mask >> i & 1]
        else:
            witness = []
            vertex, spent = compulsory[-1], cost
            while vertex != compulsory[0]:
                if vertex not in compulsory:
                    witness.append(vertex)
                vertex, spent = parent[vertex, spent]
            witness.reverse()
        answers.append({"budget": cap, "cost": cost, "makespan": value, "witness": witness})
    return answers


def measured_block(method, prepared, locked, costs, budgets, machines):
    profile, solve = measure(profiled, method, prepared, locked, costs, budgets[-1])
    last_answer, single_lookup = measure(query, profile, budgets[-1:], machines)
    if len(budgets) == 1:
        answers, all_lookups = last_answer, single_lookup
    else:
        answers, all_lookups = measure(query, profile, budgets, machines)
    return {"solve_ns": solve, "largest_lookup_ns": single_lookup, "all_lookups_ns": all_lookups,
            "states": profile[-1], "terminal_nondominated": len(profile[0]), "answers": answers}


def rotate(values, offset):
    offset %= len(values)
    return values[offset:] + values[:offset]


def timed_repeat(times, locked, choices, tasks, spin):
    prepared, build_ns = prepare(times, locked, choices)
    result = {method: {} for method in METHODS}
    for col, phase in enumerate(rotate(PHASES, spin)):
        costs, budgets = tasks[phase]
        for method in rotate(METHODS, spin + col):
            result[method][phase] = measured_block(method, prepared[method], locked, costs, budgets, len(times))
    return {"build_ns": build_ns, "blocks": result,
            "graph_arcs": {"checkpoint_sparse": sum(map(len, prepared["checkpoint_sparse"].incoming)),
                           "monge": len(prepared["checkpoint_plain"][1])}}


def independent_references(times, locked, tasks):
    costs, all_budgets = tasks["scan"]
    base = dense_terminal(times, locked, set(costs), all_budgets[-1], lock_costs=costs)
    costs, caps = tasks["alt"]
    alt = dense_terminal(times, locked, set(costs), caps[-1], lock_costs=costs)
    costs, caps = tasks["wide"]
    assert min(costs.values()) * 3 > caps[0]
    values = [direct(times, locked | set(subset)) for n in (0, 1, 2) for subset in combinations(costs, n)
              if sum(costs[i] for i in subset) <= caps[0]]
    scan = [base[min(b, len(base) - 1)] for b in all_budgets]
    return {"low": scan[:1], "scan": scan, "alt": [alt[-1]], "wide": [max(values)]}, len(values)


def audit(times, locked, tasks, expected, raw, baseline):
    checked = set()
    for refit in raw:
        for blocks in refit["blocks"].values():
            for phase, block in blocks.items():
                costs, budgets = tasks[phase]
                for answer, budget, truth in zip(block["answers"], budgets, expected[phase], strict=True):
                    witness = set(answer["witness"])
                    assert set(costs) >= witness and not (locked & witness)
                    assert answer["budget"] == budget and answer["cost"] == sum(costs[i] for i in witness) <= budget
                    key = (tuple(sorted(witness)), truth)
                    if key not in checked:
                        assert direct(times, locked | witness) == truth
                        checked.add(key)
                    assert answer["makespan"] == truth
                    answer["extra_delay"] = truth - baseline
    return len(checked)


def workload(refit, method):
    blocks = refit["blocks"][method]
    prep = refit["build_ns"][method]
    hot = {phase: block["solve_ns"] + block["largest_lookup_ns"] for phase, block in blocks.items()}
    scan = blocks["scan"]["solve_ns"] + blocks["scan"]["all_lookups_ns"]
    return {"precompute": prep, "small_cold": prep + hot["low"], "large_cold": prep + hot["scan"],
            "same_tariff_scan_cold": prep + scan, "mixed_tariffs_cold": prep + scan + hot["alt"] + hot["wide"],
            "mean_warm_largest_budget": (hot["scan"] + hot["alt"] + hot["wide"]) / 3,
            "warm_wide": hot["wide"]}


def report(raw):
    samples = {method: [workload(refit, method) for refit in raw] for method in METHODS}
    medians = {method: {key: median(row[key] for row in by_repeat) for key in by_repeat[0]}
               for method, by_repeat in samples.items()}
    base = medians["position_sparse"]
    ratios = {}
    for method in METHODS[1:]:
        cost = medians[method]
        warm_saving = base["mean_warm_largest_budget"] - cost["mean_warm_largest_budget"]
        extra_prep = cost["precompute"] - base["precompute"]
        ratios[method] = {key: median(old[key] / new[key] for old, new in zip(samples["position_sparse"], samples[method]))
                          for key in ("small_cold", "large_cold", "same_tariff_scan_cold", "mixed_tariffs_cold", "warm_wide")}
        ratios[method]["modelled_break_even_queries"] = max(1, ceil(extra_prep / warm_saving)) if warm_saving > 0 else None
    return {"median_workload_cpu_ns": medians, "paired_speedup": ratios}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cpu", required=True, type=int)
    args = parser.parse_args()
    assert os.sched_getaffinity(0) == {args.cpu}
    started = process_time_ns()
    records = []
    for index, (name, origin, times, locked, order, source) in enumerate(matrices()):
        choices = tuple(i for i in range(1, len(times) - 1) if i not in locked)
        tasks = price_queries(choices, index)
        baseline = direct(times, locked)
        raw = [timed_repeat(times, locked, choices, tasks, index + repeat) for repeat in range(REPEATS)]
        expected, wide_subsets = independent_references(times, locked, tasks)
        dynamic_checks = audit(times, locked, tasks, expected, raw, baseline)
        records.append({"case": name, "origin": origin, "source": source, "jobs": len(times[0]), "machines": len(times),
                        "times_sha256": digest(json.dumps(times).encode()), "base": baseline, "order": order,
                        "locked": sorted(locked), "tasks": tasks, "independent_makespans": expected,
                        "wide_subsets": wide_subsets, "distinct_witness_checks": dynamic_checks,
                        "summary": report(raw), "raw_repeats": raw})
        print(f"Verified {name}", file=sys.stderr, flush=True)
    elapsed = process_time_ns() - started
    paths = (POSITIONS, SPARSE, MONGE, DENSE, CHECKER, HERE / "PROTOCOL.md", Path(__file__))
    print(json.dumps({"cpu": args.cpu, "elapsed_cpu_ns": elapsed, "sha256": {p.name: digest(p.read_bytes()) for p in paths},
                      "records": records}, indent=2))


if __name__ == "__main__":
    main()
