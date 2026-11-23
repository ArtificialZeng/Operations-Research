"""Independent full-recourse audit for FrontierOR Bodur witnesses."""

import argparse
from decimal import Decimal
import json
from pathlib import Path


TOL = Decimal("1e-5")


def read(path):
    return json.loads(path.read_bytes(), parse_float=Decimal)


def numeric(value):
    if type(value) not in (int, Decimal) or not Decimal(value).is_finite():
        raise ValueError(f"Expected a finite number, got {value}")
    return Decimal(value)


def sparse_indices(data, size):
    for key, value in data.items():
        index = int(key)
        if str(index) != key or not 0 <= index < size:
            raise ValueError(f"Index {key!r} outside [0,{size}) or noncanonical")
        yield index, value


def audit(instance, solution):
    facilities = instance["facilities"]
    n_customers = instance["num_customers"]
    scenarios = instance["scenarios"]
    if (len(facilities) != instance["num_facilities"] or len(scenarios) != instance["num_scenarios"]
            or any(f["id"] != i for i, f in enumerate(facilities)) or any(s["id"] != k for k, s in enumerate(scenarios))):
        raise ValueError("Unexpected instance dimensions or identifiers")
    flags = [0] * len(facilities)
    for i, flag in sparse_indices(solution["x"], len(facilities)):
        if type(flag) not in (int, Decimal) or flag not in (0, 1):
            raise ValueError(f"Facility {i} has a nonbinary decision")
        flags[i] = int(flag)
    open_set = [i for i, flag in enumerate(flags) if flag]
    if sorted(solution["open_facilities"]) != open_set:
        raise ValueError("Open-facility list disagrees with x")

    capacity = [numeric(f["capacity"]) * flag for f, flag in zip(facilities, flags)]
    max_demand = max(sum(numeric(demand) for demand in s["demands"]) for s in scenarios)
    if sum(capacity) + TOL < max_demand:
        raise ValueError("Open capacity insufficient for peak scenario")
    active_flows = dict(sparse_indices(solution["y"], len(scenarios)))
    expected_ship_cost = Decimal(0)
    worst_shortage = Decimal(0)
    worst_excess = Decimal(0)
    positive_flows = 0
    for k, scenario in enumerate(scenarios):
        demand = list(map(numeric, scenario["demands"]))
        if len(demand) != n_customers:
            raise ValueError(f"Scenario {k} has the wrong demand vector length")
        received = [Decimal(0)] * n_customers
        for i, deliveries in sparse_indices(active_flows.get(k, {}), len(facilities)):
            shipped = Decimal(0)
            for j, qty in sparse_indices(deliveries, n_customers):
                qty = numeric(qty)
                if qty < -TOL:
                    raise ValueError(f"Negative shipment for scenario {k}, facility {i}, customer {j}")
                positive_flows += qty > 0
                received[j] += qty
                shipped += qty
                expected_ship_cost += qty * numeric(instance["transportation_costs"][i][j]) * numeric(scenario["probability"])
            worst_excess = max(worst_excess, shipped - capacity[i])
        worst_shortage = max(worst_shortage, max(d - satisfied for d, satisfied in zip(demand, received)))
    fixed = sum(numeric(facilities[i]["opening_cost"]) for i in open_set)
    objective = fixed + expected_ship_cost
    error = abs(objective - numeric(solution["objective_value"]))
    ok = max(worst_shortage, worst_excess) <= TOL and error <= max(TOL, abs(objective) * Decimal("1e-8"))
    return {"valid": ok, "objective": float(objective), "expected_transport_cost": float(expected_ship_cost),
            "fixed_cost": float(fixed), "absolute_objective_error": float(error), "worst_shortage": float(worst_shortage),
            "worst_excess": float(worst_excess), "open_facility_count": len(open_set),
            "positive_flows": positive_flows, "scenarios_verified": len(scenarios)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("instance", type=Path)
    parser.add_argument("solution", type=Path)
    args = parser.parse_args()
    result = audit(read(args.instance), read(args.solution))
    print(json.dumps(result, indent=2))
    if not result["valid"]:
        raise SystemExit(1)
