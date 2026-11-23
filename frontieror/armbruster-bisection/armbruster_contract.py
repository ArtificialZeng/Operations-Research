"""Recompute the graph bisection declared by an Armbruster solution."""

from math import fsum, isclose, isfinite


def _reported_objective(solution):
    value = solution.get("objective_value")
    if type(value) not in (int, float):
        return None
    try:
        return float(value) if isfinite(value) else None
    except OverflowError:
        return None


def verify(instance, solution):
    """Report canonical partition feasibility and objective accuracy independently."""
    if not isinstance(solution, dict):
        solution = {}
    reported = _reported_objective(solution)
    result = {
        "feasible": False,
        "objective_accurate": False,
        "computed_objective": None,
        "reported_objective": reported,
        "objective_error": None,
        "violations": [],
    }

    sides = []
    for key in ("partition_S", "partition_complement"):
        side = solution.get(key)
        if not isinstance(side, list) or any(type(node) is not int for node in side):
            result["violations"].append(f"{key} must be a list of integer vertex IDs")
            return result
        side_set = set(side)
        if len(side_set) != len(side):
            result["violations"].append(f"{key} contains a duplicate vertex")
            return result
        sides.append(side_set)

    left, right = sides
    nodes = set(range(instance["num_nodes"]))
    if left & right or left | right != nodes:
        result["violations"].append("Declared sides must partition all instance vertices")
        return result
    if 0 not in left:
        result["violations"].append("partition_S must contain vertex 0")

    weights = instance["node_weights"]
    if len(weights) != len(nodes):
        raise ValueError("Instance node weights do not match the vertex count")
    capacity = instance["bisection_capacity_F"]
    left_load = sum(weights[node] for node in left)
    right_load = sum(weights[node] for node in right)
    result["side_weights"] = [left_load, right_load]
    if max(left_load, right_load) > capacity:
        result["violations"].append("A declared side exceeds bisection capacity")
    result["feasible"] = not result["violations"]

    computed = fsum(
        weight
        for (start, end), weight in zip(instance["edges"], instance["edge_weights"], strict=True)
        if (start in left) != (end in left)
    )
    result["computed_objective"] = computed
    if reported is not None:
        result["objective_error"] = abs(reported - computed)
        result["objective_accurate"] = isclose(reported, computed, rel_tol=1e-10, abs_tol=1e-8)
    return result


def verify_strict(instance, solution):
    result = verify(instance, solution)
    if not result["feasible"] or not result["objective_accurate"]:
        raise ValueError(f"Independent strict bisection check failed: {result}")
    return result["computed_objective"]
