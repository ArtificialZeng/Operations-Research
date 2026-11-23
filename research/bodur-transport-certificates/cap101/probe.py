"""Compare sequential LP recourse with exact, batched tree certificates."""

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from math import isfinite, lcm
from multiprocessing import get_context
import os
from pathlib import Path
from time import perf_counter, process_time
from urllib.request import urlopen

os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["OMP_NUM_THREADS"] = "1"

import numpy as np


URL = "https://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/cap101.txt"
ARCHIVE_HASH = "7f1d0e32808b8c1bd9e3f49ee42dd758abb5a157da63ed52182f22bd14919ebe"
UNITS = 1000
SEED = 20261124
MAX_TREES = 24
CASES = (250, 1500)


def read_cap(raw):
    if sha256(raw).hexdigest() != ARCHIVE_HASH:
        raise ValueError("CAP101 data do not match the public source hash")
    fields = iter(raw.decode("ascii").split())
    facilities, customers = int(next(fields)), int(next(fields))
    if (facilities, customers) != (25, 50):
        raise ValueError("Unexpected CAP101 dimensions")
    caps, opening = zip(*((int(next(fields)), Fraction(next(fields))) for _ in range(facilities)))
    nominal = []
    costs_by_customer = []
    for _ in range(customers):
        demand = int(next(fields))
        nominal.append(demand)
        costs_by_customer.append([Fraction(next(fields)) / demand for _ in range(facilities)])
    if next(fields, None) is not None:
        raise ValueError("Unexpected trailing CAP101 fields")
    scale = lcm(*(cost.denominator for row in costs_by_customer for cost in row))
    costs = [tuple(int(cost * scale) for cost in row) + (0,) for row in zip(*costs_by_customer)]
    return np.asarray(caps, dtype=np.int64), opening, np.asarray(nominal, dtype=np.int64), costs, scale


def sample(nominal):
    rng = np.random.default_rng(SEED)
    std = rng.uniform(0.1, 0.3, size=len(nominal)) * nominal
    draws = np.maximum(rng.normal(nominal, std, size=(max(CASES), len(nominal))), 0)
    return np.rint(draws * UNITS).astype(np.int64)


def open_sets(capacity, opening, scenarios):
    peak = int(scenarios.sum(axis=1).max())
    tight = []
    running = 0
    for i in sorted(range(len(capacity)), key=lambda i: (opening[i], i)):
        tight.append(i)
        running += int(capacity[i]) * UNITS
        if 10 * running >= 11 * peak:
            break
    if 10 * running < 11 * peak:
        raise ValueError("The full facility set lacks the target capacity")
    return {"all_open": list(range(len(capacity))), "capacity_cover": sorted(tight)}


def require_ok(status, action):
    if status.name != "kOk":
        raise RuntimeError(f"HiGHS {action}: {status.name}")


class HighsTransport:
    def __init__(self, caps, costs, scale):
        import highspy

        self.api = highspy
        facilities, width = len(costs), len(costs[0])
        customers = width - 1
        columns = facilities * width
        count_rows = facilities + customers
        self.rhs_rows = np.arange(facilities, count_rows, dtype=np.int32)
        model = highspy.Highs()
        for key, value in (("output_flag", False), ("threads", 1), ("presolve", "off"),
                           ("solver", "simplex"), ("simplex_strategy", 1)):
            require_ok(model.setOptionValue(key, value), f"setting {key}")
        empty_idx, empty_val = np.empty(0, dtype=np.int32), np.empty(0)
        rhs = np.concatenate((caps / UNITS, np.zeros(customers)))
        require_ok(model.addRows(count_rows, rhs, rhs, 0, empty_idx, empty_idx, empty_val), "adding rows")
        starts, indices = [], []
        for i in range(facilities):
            for j in range(width):
                starts.append(len(indices))
                indices.append(i)
                if j < customers:
                    indices.append(facilities + j)
        obj = np.asarray([value / scale for row in costs for value in row])
        require_ok(model.addCols(columns, obj, np.zeros(columns), np.full(columns, np.inf),
            len(indices), np.asarray(starts, dtype=np.int32), np.asarray(indices, dtype=np.int32),
            np.ones(len(indices))), "adding flow columns")
        self.model = model
        self.iterations = 0

    def solve(self, demand, deadline):
        remaining = deadline - perf_counter()
        if remaining <= 0:
            raise TimeoutError("Pilot wall deadline reached")
        rhs = demand / UNITS
        require_ok(self.model.changeRowsBounds(len(rhs), self.rhs_rows, rhs, rhs), "setting demand")
        require_ok(self.model.setOptionValue("time_limit", min(remaining, 2.0)), "setting solve budget")
        self.model.run()
        status = self.model.getModelStatus()
        if status != self.api.HighsModelStatus.kOptimal:
            raise RuntimeError(f"Unexpected transportation solve state: {status.name}")
        self.iterations += self.model.getInfo().simplex_iteration_count
        return self.model.getObjectiveValue()

    def tree_columns(self):
        return [i for i, status in enumerate(self.model.getBasis().col_status)
                if status == self.api.HighsBasisStatus.kBasic]


class ClpTransport:
    def __init__(self, caps, costs, scale):
        from ortools.linear_solver import pywraplp

        self.api = pywraplp
        solver = pywraplp.Solver.CreateSolver("CLP")
        solver.SetNumThreads(1)
        self.cap_rows = [solver.Constraint(cap / UNITS, cap / UNITS) for cap in caps]
        self.dem_rows = [solver.Constraint(0.0, 0.0) for _ in costs[0][:-1]]
        objective = solver.Objective()
        for i, cost_row in enumerate(costs):
            for j, cost in enumerate(cost_row):
                variable = solver.NumVar(0.0, solver.infinity(), "")
                objective.SetCoefficient(variable, cost / scale)
                self.cap_rows[i].SetCoefficient(variable, 1.0)
                if j < len(self.dem_rows):
                    self.dem_rows[j].SetCoefficient(variable, 1.0)
        objective.SetMinimization()
        self.solver, self.objective = solver, objective
        self.iterations = 0

    def solve(self, demand, deadline):
        remaining = deadline - perf_counter()
        if remaining <= 0:
            raise TimeoutError("Pilot wall deadline reached")
        self.solver.SetTimeLimit(max(1, int(1000 * min(remaining, 2.0))))
        for row, quantity in zip(self.dem_rows, demand, strict=True):
            value = float(quantity) / UNITS
            row.SetBounds(value, value)
        if self.solver.Solve() != self.api.Solver.OPTIMAL:
            raise RuntimeError("CLP did not finish transportation recourse")
        self.iterations += self.solver.iterations()
        return self.objective.Value()


@dataclass(frozen=True)
class Certificate:
    initial_flow: np.ndarray
    demand_map: np.ndarray
    arcs: list
    edge_costs: list
    source_dual: list
    customer_dual: list


def certify_tree(columns, caps, costs):
    facilities, width = len(costs), len(costs[0])
    root = facilities + width - 1
    if len(columns) != root:
        return None
    graph = [[] for _ in range(root + 1)]
    for edge, column in enumerate(columns):
        i, j = divmod(column, width)
        customer = facilities + j
        graph[i].append((customer, edge, costs[i][j]))
        graph[customer].append((i, edge, costs[i][j]))
    order = [root]
    parent = {root: None}
    potentials = {root: 0}
    for u in order:
        for v, edge, cost in graph[u]:
            if v not in parent:
                order.append(v)
                parent[v] = u, edge
                potentials[v] = cost - potentials[u]
    if len(order) != root + 1:
        return None
    source_dual = [potentials[i] for i in range(facilities)]
    customer_dual = [potentials[facilities + j] for j in range(width)]
    if any(source_dual[i] + customer_dual[j] > costs[i][j]
           for i in range(facilities) for j in range(width)):
        return None

    rhs_constant = np.zeros(root + 1, dtype=np.int64)
    rhs_constant[:facilities] = caps
    rhs_demand = np.zeros((root + 1, width - 1), dtype=np.int64)
    rhs_demand[facilities:root] = -np.eye(width - 1, dtype=np.int64)
    initial_flow = np.empty(root, dtype=np.int64)
    demand_map = np.empty((root, width - 1), dtype=np.int64)
    for node in reversed(order[1:]):
        u, edge = parent[node]
        sign = 1 if node < facilities else -1
        initial_flow[edge] = sign * rhs_constant[node]
        demand_map[edge] = sign * rhs_demand[node]
        rhs_constant[u] += rhs_constant[node]
        rhs_demand[u] += rhs_demand[node]
    arcs = [divmod(column, width) for column in columns]
    return Certificate(initial_flow, demand_map, arcs, [costs[i][j] for i, j in arcs], source_dual, customer_dual)


def apply_certificate(tree, caps, demands, scale):
    potential_flows = demands @ tree.demand_map.T + tree.initial_flow
    hits = np.flatnonzero(np.all(potential_flows >= 0, axis=1))
    values = np.empty(len(hits))
    source_value = sum(int(cap) * potential for cap, potential in zip(caps, tree.source_dual, strict=True))
    for h, i in enumerate(hits):
        source_balance = [0] * len(caps)
        customer_balance = [0] * len(tree.customer_dual)
        primal = 0
        for (facility, customer), cost, shipment in zip(tree.arcs, tree.edge_costs, potential_flows[i], strict=True):
            amount = int(shipment)
            source_balance[facility] += amount
            customer_balance[customer] += amount
            primal += cost * amount
        demand = demands[i].tolist()
        dual = source_value + sum(q * p for q, p in zip(demand, tree.customer_dual[:-1], strict=True))
        if source_balance != caps.tolist() or customer_balance[:-1] != demand or primal != dual:
            raise ArithmeticError("Exact certificate failed flow balance or primal–dual equality")
        values[h] = primal / (scale * UNITS)
    return hits, values


def ordinary(backend, caps, costs, scale, demands, order, deadline):
    start, cpu = perf_counter(), process_time()
    model = backend(caps, costs, scale)
    values = np.empty(len(demands))
    for i in order:
        values[i] = model.solve(demands[i], deadline)
    return values, {"wall_s": perf_counter() - start, "cpu_s": process_time() - cpu,
                    "lp_calls": len(order), "simplex_iterations": model.iterations}


def batch(caps, costs, scale, demands, order, deadline):
    start, cpu = perf_counter(), process_time()
    model = HighsTransport(caps, costs, scale)
    values = np.empty(len(demands))
    remaining = order.copy()
    certified = first_hits = rejected = attempts = calls = 0
    for attempt in range(MAX_TREES):
        if len(remaining) == 0:
            break
        if attempt == 0:
            demand = (demands.sum(axis=0) + len(demands) // 2) // len(demands)
            model.solve(demand, deadline)
        else:
            slot = len(remaining) // 2
            anchor = remaining[slot]
            values[anchor] = model.solve(demands[anchor], deadline)
            remaining = np.delete(remaining, slot)
        calls += 1
        attempts += 1
        tree = certify_tree(model.tree_columns(), caps, costs)
        if tree is None:
            rejected += 1
            continue
        hits, recourse = apply_certificate(tree, caps, demands[remaining], scale)
        values[remaining[hits]] = recourse
        certified += len(hits)
        if attempt == 0:
            first_hits = len(hits)
        remaining = np.delete(remaining, hits)
    fallback = len(remaining)
    for i in remaining:
        values[i] = model.solve(demands[i], deadline)
    return values, {"wall_s": perf_counter() - start, "cpu_s": process_time() - cpu,
                    "lp_calls": calls + fallback, "fallback_calls": fallback,
                    "simplex_iterations": model.iterations, "tree_attempts": attempts,
                    "trees_rejected": rejected, "first_tree_hits": first_hits, "certified_hits": certified}


def clp_all(sender, cases, scale, deadline):
    from ortools.linear_solver import pywraplp

    version_text = pywraplp.Solver.CreateSolver("CLP").SolverVersion()
    with sender:
        results = []
        for _, _, caps, costs, demands in cases:
            order = np.argsort(demands.sum(axis=1), kind="stable")
            results.append(ordinary(ClpTransport, caps, costs, scale, demands, order, deadline))
        sender.send((version_text, results))


def measured_clp(cases, scale, deadline):
    context = get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    child = context.Process(target=clp_all, args=(sender, cases, scale, deadline))
    with receiver, sender:
        child.start()
        sender.close()
        try:
            if not receiver.poll(max(0, deadline - perf_counter())):
                raise TimeoutError("CLP baseline exceeded the pilot budget")
            return receiver.recv()
        finally:
            child.join(timeout=0.1)
            if child.is_alive():
                child.kill()
                child.join(timeout=0.25)


def probe(caps, costs, scale, demands, clp_record, deadline):
    order = np.argsort(demands.sum(axis=1), kind="stable")
    highs_value, highs = ordinary(HighsTransport, caps, costs, scale, demands, order, deadline)
    clp_value, clp = clp_record
    batch_value, tested = batch(caps, costs, scale, demands, order, deadline)
    diff_clp = np.abs(highs_value - clp_value)
    diff = np.abs(highs_value - batch_value)
    tolerance = np.maximum(1e-6, 1e-9 * np.abs(highs_value))
    if np.any(diff > tolerance) or np.any(diff_clp > tolerance):
        raise ArithmeticError("Scenario objective disagreement exceeds the prespecified tolerance")
    return {"scenarios": len(demands), "highs_sequential": highs, "clp_sequential": clp,
            "tree_batch": tested, "exact_certificate_hit_fraction": tested["certified_hits"] / len(demands),
            "first_tree_hit_fraction": tested["first_tree_hits"] / len(demands),
            "highs_wall_speedup": highs["wall_s"] / tested["wall_s"],
            "clp_wall_speedup": clp["wall_s"] / tested["wall_s"],
            "max_abs_cost_error_vs_highs": float(diff.max()),
            "max_abs_clp_cost_error_vs_highs": float(diff_clp.max())}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path, help="Reuse a byte-identical local CAP101 file")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seconds", type=float, default=35.0)
    args = parser.parse_args()
    if not isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be finite and positive")
    if args.archive:
        raw = args.archive.read_bytes()
    else:
        with urlopen(URL, timeout=10) as reply:
            raw = reply.read()
    caps, opening, nominal, costs, scale = read_cap(raw)
    demands = sample(nominal)
    opened = open_sets(caps, opening, demands)
    deadline = perf_counter() + args.seconds
    cases = [(name, ids, caps[ids] * UNITS, [costs[i] for i in ids], demands[:count])
             for count in CASES for name, ids in opened.items()]
    clp_version, clp_records = measured_clp(cases, scale, deadline)
    import highspy

    highs_version = highspy.Highs().version()
    results = []
    for (name, ids, cap, cost, requested), clp_record in zip(cases, clp_records, strict=True):
        result = probe(cap, cost, scale, requested, clp_record, deadline)
        results.append({"open_set": name, "open_ids_zero_based": ids,
                        "capacity_to_peak": int(cap.sum()) / int(requested.sum(axis=1).max()), **result})
    record = {"source": URL, "source_sha256": ARCHIVE_HASH, "seed": SEED, "quantity_scale": UNITS,
              "scenario_sha256": sha256(demands.astype("<i8").tobytes()).hexdigest(),
              "cost_integer_scale": str(scale), "highs": highs_version, "numpy": np.__version__,
              "clp": clp_version, "ortools": version("ortools"),
              "max_tree_attempts": MAX_TREES, "metrics": results}
    args.output.write_text(json.dumps(record, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
