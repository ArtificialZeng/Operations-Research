"""Exploratory CAP101 master strengthened by common nearest-closure cuts."""

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

import master_trial as trial
from probe import ARCHIVE_HASH, UNITS, URL, np, read_cap, sample


def nearest_seed(demands, capacities, costs, opening, groups, ranking):
    facilities = len(capacities)
    customers = np.arange(demands.shape[1])
    locations = tuple(range(facilities))
    best = None
    feasible = 0
    for closed in (None, *locations):
        layout = tuple(i for i in locations if i != closed)
        nearest = ranking[0].copy()
        if closed is not None:
            affected = nearest == closed
            nearest[affected] = ranking[1, affected]
        load = np.zeros((len(demands), facilities), dtype=np.int64)
        for j, i in enumerate(nearest):
            load[:, i] += demands[:, j]
        if np.any(load > capacities):
            continue
        feasible += 1
        scenario_costs = demands @ costs[nearest, customers]
        grouped = tuple(int(scenario_costs[group].sum()) for group in groups)
        objective = sum(grouped) + sum(opening[i] for i in layout)
        if best is None or objective < best[0]:
            best = objective, layout, grouped, nearest, load, closed
    if best is None:
        raise RuntimeError("No feasible nearest assignment among all-open and single closures")
    objective, layout, grouped, nearest, load, closed = best
    compact_index = {i: k for k, i in enumerate(layout)}
    shipments = np.zeros((len(demands), len(layout), demands.shape[1] + 1), dtype=np.int64)
    shipments[:, [compact_index[i] for i in nearest], customers] = demands
    shipments[:, :, -1] = capacities[list(layout)] - load[:, layout]
    digest = sha256(shipments.astype("<i8", copy=False).tobytes()).hexdigest()
    return (objective, layout, grouped, digest), closed, feasible


def closure_bounds(demands, costs, groups, ranking):
    customers = np.arange(demands.shape[1])
    primary = ranking[0]
    per_unit_floor = costs[primary, customers]
    per_unit_penalty = costs[ranking[1], customers] - per_unit_floor
    floors, cuts = [], []
    for group in groups:
        quantity = demands[group].sum(axis=0)
        penalties = [0] * len(costs)
        for facility, value in zip(primary, quantity * per_unit_penalty, strict=True):
            penalties[facility] += int(value)
        base = int(quantity @ per_unit_floor)
        floors.append(base)
        cuts.append((base + sum(penalties), tuple(-value for value in penalties)))
    return floors, cuts


def run(raw, arm, seconds):
    capacities, opening, nominal, costs, scale = read_cap(raw)
    demands = sample(nominal)
    capacities = capacities * UNITS
    costs = np.asarray(costs, dtype=np.int64)
    if not np.all(capacities == capacities[0]):
        raise ValueError("The exact master lower bound assumes equal facility capacities")
    peak = int(demands.sum(axis=1).max())
    count = (peak + int(capacities[0]) - 1) // int(capacities[0])
    objective_divisor = scale * UNITS * len(demands)
    if int(costs.max()) * int(capacities.sum()) * len(demands) > np.iinfo(np.int64).max:
        raise OverflowError("Integer recourse arithmetic would exceed int64")
    scaled_opening = tuple(int(price * objective_divisor) for price in opening)
    order, groups = trial.partition(demands)
    ranking = np.argsort(costs[:, :-1], axis=0, kind="stable")
    seed, closure, feasible_seed_count = nearest_seed(demands, capacities, costs, scaled_opening, groups, ranking)
    floors, closure_cuts = closure_bounds(demands, costs, groups, ranking)
    extra_cut_lb = sum(constant for constant, _ in closure_cuts) + trial.minimum_affine([
        price + sum(slopes[i] for _, slopes in closure_cuts)
        for i, price in enumerate(scaled_opening)
    ], count)
    closure_lb = Fraction(extra_cut_lb, objective_divisor)
    master = trial.Master(scaled_opening, floors, count, objective_divisor)
    master.add_cuts(closure_cuts)
    common_startup_wall = perf_counter() - START
    deadline = START + seconds - min(0.75, seconds / 5)
    best = seed
    layout = seed[1]
    evaluated = set()
    totals = Counter()
    recourse_wall = master_wall = 0.0
    native_bound = stop = None
    master_solves = 0
    accepted = 0
    trace = sha256()

    try:
        while perf_counter() < deadline:
            if layout in evaluated:
                stop = "repeated_master_layout"
                break
            started = perf_counter()
            cost, cuts, digest, stats = trial.oracle(
                layout, demands, order, groups, capacities, costs, scale, arm, deadline,
            )
            recourse_wall += perf_counter() - started
            evaluated.add(layout)
            objective = sum(cost) + sum(scaled_opening[i] for i in layout)
            if layout == seed[1] and objective != seed[0]:
                raise ArithmeticError("The common seed differs from its certified recourse evaluation")
            trace.update(json.dumps([layout, objective], separators=(",", ":")).encode())
            if objective < best[0]:
                best = objective, layout, cost, digest
                accepted += 1
            totals.update(stats)
            master.add_cuts(cuts)
            started = perf_counter()
            layout, bound, status = master.solve((best[1], best[2]), deadline)
            master_wall += perf_counter() - started
            master_solves += 1
            if isfinite(bound):
                native_bound = max(native_bound, bound) if native_bound is not None else bound
            if layout is None:
                stop = f"master_no_candidate_{status}"
                break
    except TimeoutError:
        stop = "search_budget"
    except RuntimeError as error:
        if "kTimeLimit" not in str(error):
            raise
        stop = "interrupted_transport_lp"

    lower, lower_source = master.exact_lower(START + seconds - 0.10)
    if closure_lb > lower:
        lower, lower_source = closure_lb, "nearest_closure_penalty"
    upper = Fraction(best[0], objective_divisor)
    start_value = Fraction(seed[0], objective_divisor)
    if lower > upper:
        raise ArithmeticError("The exact lower bound exceeds the certified incumbent")
    return {"arm": arm, "scenarios": len(demands), "source_sha256": ARCHIVE_HASH,
            "scenario_sha256": sha256(demands.astype("<i8").tobytes()).hexdigest(),
            "wall_limit_s": seconds, "wall_s": perf_counter() - START, "cpu_s": process_time() - CPU_START,
            "common_startup_wall_s": common_startup_wall, "cpu_affinity": sorted(os.sched_getaffinity(0)),
            "seed_tested_layouts": len(capacities) + 1, "seed_feasible_layouts": feasible_seed_count,
            "seed_closed_id_zero_based": closure, "seed_objective_fraction": str(start_value),
            "seed_objective": float(start_value), "seed_flow_sha256": seed[3],
            "incumbent_improvements": accepted, "feasible_ub_fraction": str(upper), "feasible_ub": float(upper),
            "improvement_from_seed": float(start_value - upper),
            "improvement_from_seed_ratio": float((start_value - upper) / start_value),
            "exact_lb_fraction": str(lower), "exact_lb": float(lower), "exact_lb_source": lower_source,
            "exact_gap_ratio": float((upper - lower) / upper), "native_numeric_master_bound": native_bound,
            "best_zero_based_open_ids": list(best[1]), "best_milliunit_flow_sha256": best[3],
            "master_mip_solves": master_solves, "master_cuts_including_closure": len(master.rows),
            "master_mip_wall_s": master_wall, "oracle_completed_sweeps": len(evaluated),
            "recourse_wall_s_complete_sweeps": recourse_wall, "oracle_completed_telemetry": dict(totals),
            "layout_objective_trace_sha256": trace.hexdigest(), "stop": stop or "search_budget"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=("sequential", "batch"), required=True)
    parser.add_argument("--seconds", type=float, default=30.0)
    parser.add_argument("--archive", type=Path)
    args = parser.parse_args()
    if not isfinite(args.seconds) or args.seconds <= 0:
        parser.error("--seconds must be finite and positive")
    if args.archive:
        raw = args.archive.read_bytes()
    else:
        with urlopen(URL, timeout=10) as response:
            raw = response.read()
    print(json.dumps(run(raw, args.arm, args.seconds), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
