"""Matched fixed-budget CAP101 Benders master with two recourse implementations."""

import argparse
from collections import Counter
from fractions import Fraction
from hashlib import sha256
import json
from math import isfinite
import os
from pathlib import Path
from time import perf_counter, process_time
from urllib.request import urlopen

START, CPU_START = perf_counter(), process_time()

from probe import ARCHIVE_HASH, MAX_TREES, UNITS, URL, HighsTransport, certify_tree, np, read_cap, require_ok, sample

import highspy


GROUPS = 8
MASTER_SCALE = 1_000_000
WEIGHT_SCALE = 65536
RANDOM_SEED = 42


def partition(demands):
    order = np.argsort(demands.sum(axis=1), kind="stable")
    return order, np.array_split(order, GROUPS)


def oracle(layout, demands, order, groups, capacities, original_costs, scale, arm, deadline):
    active_caps, active_costs = capacities[list(layout)], original_costs[list(layout)]
    solver = HighsTransport(active_caps, active_costs.tolist(), scale)
    facilities, width = active_costs.shape
    count = len(demands)
    flows = np.zeros((count, facilities, width), dtype=np.int64)
    source_dual = np.empty((count, facilities), dtype=np.int64)
    customer_dual = np.empty_like(demands)
    stats = Counter(lp_calls=0, tree_attempts=0, trees_rejected=0, certificate_hits=0, fallback_calls=0)

    def solve(index):
        solver.solve(demands[index], deadline)
        solution = solver.model.getSolution()
        flows[index] = np.rint(np.asarray(solution.col_value).reshape(active_costs.shape) * UNITS)
        dual = np.rint(np.asarray(solution.row_dual) * scale).astype(np.int64)
        source_dual[index], customer_dual[index] = dual[:facilities], np.maximum(dual[facilities:], 0)
        stats["lp_calls"] += 1

    remaining = order.copy()
    if arm == "batch":
        for attempt in range(MAX_TREES):
            if len(remaining) == 0:
                break
            stats["tree_attempts"] += 1
            if attempt == 0:
                mean = (demands.sum(axis=0) + count // 2) // count
                solver.solve(mean, deadline)
                stats["lp_calls"] += 1
            else:
                middle = len(remaining) // 2
                solve(remaining[middle])
                remaining = np.delete(remaining, middle)
            tree = certify_tree(solver.tree_columns(), active_caps, active_costs.tolist())
            if tree is None:
                stats["trees_rejected"] += 1
                continue
            tree_flows = demands[remaining] @ tree.demand_map.T + tree.initial_flow
            complete = np.all(tree_flows >= 0, axis=1)
            hits = remaining[complete]
            i, j = np.asarray(tree.arcs).T
            flows[hits[:, None], i[None, :], j[None, :]] = tree_flows[complete]
            source_dual[hits] = tree.source_dual
            customer_dual[hits] = np.maximum(tree.customer_dual[:-1], 0)
            stats["certificate_hits"] += len(hits)
            remaining = remaining[~complete]
        stats["fallback_calls"] = len(remaining)
    for index in remaining:
        solve(index)

    if np.any(flows < 0) or not np.all(flows.sum(axis=2) == active_caps):
        raise ArithmeticError("Primal tree or LP flows violate the original facility capacities")
    if not np.array_equal(flows[:, :, :-1].sum(axis=1), demands):
        raise ArithmeticError("Primal tree or LP flows violate the original demands")
    if np.any(source_dual > 0) or np.any(customer_dual < 0):
        raise ArithmeticError("Invalid dual signs")
    # Extend the common demand dual to every facility, preserving the anchor coefficients.
    reach = np.min(original_costs[None, :, :-1] - customer_dual[:, None, :], axis=2)
    if np.any(source_dual > reach[:, layout]):
        raise ArithmeticError("Original-cost reduced-cost inequality is violated")
    full_dual = np.minimum(reach, 0)
    full_dual[:, layout] = source_dual
    rhs = np.einsum("kj,kj->k", demands, customer_dual)
    slopes = full_dual * capacities[None, :]
    primal = np.einsum("kij,ij->k", flows, active_costs)
    if not np.array_equal(primal, rhs + slopes[:, layout].sum(axis=1)):
        raise ArithmeticError("Original-cost primal and dual objective integers differ")

    cuts = [(int(rhs[group].sum()), tuple(int(v) for v in slopes[group].sum(axis=0))) for group in groups]
    cost = tuple(int(primal[group].sum()) for group in groups)
    flow_hash = sha256(flows.astype("<i8", copy=False).tobytes()).hexdigest()
    stats["simplex_iterations"] = solver.iterations
    stats["certified_scenarios"] = len(demands)
    return cost, cuts, flow_hash, stats


def minimum_affine(values, count):
    """Exact minimum of a separable binary linear function with at least `count` ones."""
    ranked = sorted(values)
    return sum(v for i, v in enumerate(ranked) if i < count or v < 0)


class Master:
    def __init__(self, opening, floors, count, divisor):
        self.n = len(opening)
        self.opening = opening
        self.floors = floors
        self.minimum_count = count
        self.divisor = divisor
        self.model_divisor = divisor * MASTER_SCALE
        self.rows = []
        self.known_cuts = set()
        self.model = highspy.Highs()
        for option, value in (("output_flag", False), ("threads", 1), ("random_seed", RANDOM_SEED),
                              ("mip_rel_gap", 1e-8), ("small_matrix_value", 1e-12)):
            require_ok(self.model.setOptionValue(option, value), f"master setting {option}")
        obj = np.asarray([v / self.model_divisor for v in opening] + [1.0] * len(floors))
        low = np.asarray([0.0] * self.n + [v / self.model_divisor for v in floors])
        upp = np.asarray([1.0] * self.n + [np.inf] * len(floors))
        ints, floats = np.empty(0, np.int32), np.empty(0)
        require_ok(self.model.addCols(len(obj), obj, low, upp, 0, ints, ints, floats), "adding master columns")
        self.locations = np.arange(self.n, dtype=np.int32)
        require_ok(self.model.changeColsIntegrality(self.n, self.locations,
            np.full(self.n, highspy.HighsVarType.kInteger.value, dtype=np.uint8)), "setting binaries")
        require_ok(self.model.addRow(float(count), np.inf, self.n, self.locations, np.ones(self.n)),
                   "adding the peak capacity count")

    def add_cuts(self, cuts):
        for group, (constant, slopes) in enumerate(cuts):
            key = group, constant, slopes
            if key in self.known_cuts:
                continue
            idx = [i for i, v in enumerate(slopes) if v]
            col = np.asarray([*idx, self.n + group], dtype=np.int32)
            vals = np.asarray([-slopes[i] / self.model_divisor for i in idx] + [1.0])
            require_ok(self.model.addRow(constant / self.model_divisor, np.inf, len(col), col, vals),
                       "adding an optimality cut")
            self.known_cuts.add(key)
            self.rows.append(key)

    def solve(self, incumbent, deadline):
        remaining = deadline - perf_counter()
        if remaining <= 0:
            raise TimeoutError("Master search deadline reached")
        layout, cost = incumbent
        values = np.asarray([float(i in layout) for i in range(self.n)]
                            + [v / self.model_divisor for v in cost])
        require_ok(self.model.setSolution(len(values), np.arange(len(values), dtype=np.int32), values),
                   "setting the common incumbent")
        self.model.setOptionValue("time_limit", remaining)
        self.model.run()
        status = self.model.getModelStatus()
        info = self.model.getInfo()
        bound = info.mip_dual_bound * MASTER_SCALE
        if info.primal_solution_status != highspy.SolutionStatus.kSolutionStatusFeasible:
            return None, bound, status.name
        incumbent = self.model.getSolution().col_value
        layout = tuple(i for i, x in enumerate(incumbent[:self.n]) if x > 0.5)
        if len(layout) < self.minimum_count:
            raise ArithmeticError("Master returned an infeasible warehouse count")
        return layout, bound, status.name

    def exact_lower(self, deadline):
        floor = sum(self.floors) + minimum_affine(self.opening, self.minimum_count)
        best = Fraction(floor, self.divisor)
        elapsed = deadline - perf_counter()
        if elapsed <= 0 or not self.rows:
            return best, "cost_and_capacity_floor"
        relax = highspy.Highs()
        relax.setOptionValue("output_flag", False)
        relax.setOptionValue("threads", 1)
        relax.setOptionValue("solve_relaxation", True)
        require_ok(relax.passModel(self.model.getLp()), "cloning cut master for the LP")
        relax.setOptionValue("time_limit", max(0.01, deadline - perf_counter()))
        relax.run()
        if relax.getModelStatus() != highspy.HighsModelStatus.kOptimal:
            return best, "cost_and_capacity_floor"
        dual = relax.getSolution().row_dual
        by_group = [[] for _ in self.floors]
        for (group, constant, slopes), weight in zip(self.rows, dual[1:], strict=True):
            by_group[group].append((min(WEIGHT_SCALE, max(0, int(weight * WEIGHT_SCALE))), constant, slopes))
        result_slopes = [value * WEIGHT_SCALE for value in self.opening]
        intercept = 0
        for floor, candidates in zip(self.floors, by_group, strict=True):
            total = sum(weight for weight, _, _ in candidates)
            used = 0
            for weight, constant, slopes in candidates:
                if total > WEIGHT_SCALE:
                    weight = weight * WEIGHT_SCALE // total
                used += weight
                intercept += weight * constant
                for i, slope in enumerate(slopes):
                    result_slopes[i] += weight * slope
            intercept += (WEIGHT_SCALE - used) * floor
        certified = Fraction(intercept + minimum_affine(result_slopes, self.minimum_count),
                             self.divisor * WEIGHT_SCALE)
        if certified > best:
            return certified, "rational_lp_dual_cut_mixture"
        return best, "cost_and_capacity_floor"


def run(raw, count, arm, seconds):
    caps, opening, nominal, costs, scale = read_cap(raw)
    scenarios = sample(nominal)[:count]
    caps = caps * UNITS
    costs = np.asarray(costs, dtype=np.int64)
    peak = int(scenarios.sum(axis=1).max())
    if not np.all(caps == caps[0]):
        raise ValueError("The exact master lower bound assumes equal source capacities")
    min_count = (peak + int(caps[0]) - 1) // int(caps[0])
    if int(costs.max()) * int(caps.sum()) * count > np.iinfo(np.int64).max:
        raise OverflowError("Integer recourse arithmetic would exceed int64")
    divisor = scale * UNITS * count
    priced_openings = tuple(int(price * divisor) for price in opening)
    order, groups = partition(scenarios)
    floor_values = scenarios @ costs[:, :-1].min(axis=0)
    floors = [int(floor_values[group].sum()) for group in groups]
    master = Master(priced_openings, floors, min_count, divisor)
    absolute_deadline = START + seconds
    deadline = absolute_deadline - min(0.75, seconds / 5)

    layout = tuple(range(len(caps)))
    best = None
    evaluated = set()
    telemetry = Counter()
    cut_solves = 0
    recourse_wall = master_wall = 0.0
    reason, native_bound = None, None
    trace_hash = sha256()
    try:
        while perf_counter() < deadline:
            if layout in evaluated:
                reason = "repeated_master_layout"
                break
            started = perf_counter()
            cost, cuts, digest, stats = oracle(layout, scenarios, order, groups, caps, costs, scale, arm, deadline)
            recourse_wall += perf_counter() - started
            evaluated.add(layout)
            total = sum(cost) + sum(priced_openings[i] for i in layout)
            trace_hash.update(json.dumps([layout, total], separators=(",", ":")).encode())
            if best is None or total < best[0]:
                best = total, layout, cost, digest
            telemetry.update(stats)
            master.add_cuts(cuts)
            started = perf_counter()
            layout, bound, status = master.solve((best[1], best[2]), deadline)
            master_wall += perf_counter() - started
            cut_solves += 1
            if isfinite(bound):
                native_bound = max(native_bound, bound) if native_bound is not None else bound
            if layout is None:
                reason = f"master_no_candidate_{status}"
                break
    except TimeoutError:
        reason = "search_budget"
    except RuntimeError as error:
        if "kTimeLimit" not in str(error):
            raise
        reason = "interrupted_transport_lp"

    if best is None:
        raise RuntimeError("The initial all-open recourse sweep did not finish")
    lower, lower_source = master.exact_lower(absolute_deadline - 0.10)
    upper = Fraction(best[0], divisor)
    if lower > upper:
        raise ArithmeticError("The exact lower bound exceeds the certified incumbent")
    return {"arm": arm, "scenarios": count, "source_sha256": ARCHIVE_HASH,
            "scenario_sha256": sha256(scenarios.astype("<i8").tobytes()).hexdigest(),
            "group_count": GROUPS, "peak_demand_milliunits": peak, "minimum_open_count": min_count,
            "wall_limit_s": seconds, "wall_s": perf_counter() - START, "cpu_s": process_time() - CPU_START,
            "recourse_wall_s_complete_sweeps": recourse_wall, "master_mip_wall_s": master_wall,
            "oracle_completed_sweeps": len(evaluated), "master_mip_solves": cut_solves,
            "master_cuts": len(master.rows), "oracle_completed_telemetry": dict(telemetry),
            "native_numeric_master_bound": native_bound, "exact_lb_source": lower_source,
            "exact_lb_fraction": str(lower), "exact_lb": float(lower), "feasible_ub_fraction": str(upper),
            "feasible_ub": float(upper), "exact_gap_ratio": float((upper - lower) / upper),
            "best_zero_based_open_ids": list(best[1]), "best_milliunit_flow_sha256": best[3],
            "layout_objective_trace_sha256": trace_hash.hexdigest(), "stop": reason or "search_budget",
            "cpu_affinity": sorted(os.sched_getaffinity(0)), "highs_version": highspy.Highs().version()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("sequential", "batch"), required=True)
    parser.add_argument("--scenarios", type=int, choices=(250, 1500), required=True)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--archive", type=Path, help="Read the pinned CAP101 from disk instead of downloading")
    args = parser.parse_args()
    if not isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be finite and positive")
    if args.archive:
        raw = args.archive.read_bytes()
    else:
        with urlopen(URL, timeout=10) as response:
            raw = response.read()
    print(json.dumps(run(raw, args.scenarios, args.arm, args.seconds), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
