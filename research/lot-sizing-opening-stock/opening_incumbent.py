"""Feasible opening-stock and production starts for capacitated lot sizing."""

from time import perf_counter

import numpy as np


TOL = 1e-6


def _evaluate(d, h, s, c, a, b, cap, p, ub_x, production, setup, initial):
    """Rebuild inventory and accept only an original-model feasible plan."""
    inventory = initial[:, None] + np.cumsum(production - d, axis=1)
    if np.any(inventory < -TOL) or np.any(production < -TOL) or np.any(initial < -TOL):
        return None
    inventory = np.maximum(inventory, 0)
    previous = np.column_stack((initial, inventory[:, :-1]))
    if (
        np.any(np.abs(previous + production - d - inventory) > TOL)
        or np.any(production > ub_x * setup + TOL)
        or np.any(np.sum(a * production + b * setup, axis=0) > cap + TOL)
        or np.any((setup != 0) & (setup != 1))
    ):
        return None
    objective = float(np.sum(h * inventory + s * setup + c * production) + p @ initial)
    if not np.isfinite(objective):
        return None
    return objective, production, setup, inventory, initial


def _uncapacitated_lots(d, h, s, c, p, deadline):
    """Solve the relaxed single-product problems with an opening-stock prefix."""
    if np.any(h < 0) or np.any(s < 0) or np.any(p < 0) or np.any(c < 0):
        return None
    products, periods = d.shape
    cumulative_demand = np.column_stack((np.zeros(products), np.cumsum(d, axis=1)))
    cumulative_holding = np.column_stack((np.zeros(products), np.cumsum(h, axis=1)))
    weighted_demand = d * cumulative_holding[:, :-1]
    cumulative_weighted = np.column_stack((np.zeros(products), np.cumsum(weighted_demand, axis=1)))

    # Prefix state t covers the demands in periods 0 through t-1.
    value = p[:, None] * cumulative_demand + cumulative_weighted
    predecessor = np.full(value.shape, -1, dtype=int)
    for period in range(periods):
        if perf_counter() >= deadline:
            return None
        quantity = cumulative_demand[:, period + 1:] - cumulative_demand[:, [period]]
        holding = cumulative_weighted[:, period + 1:] - cumulative_weighted[:, [period]]
        order = (
            value[:, [period]] + holding
            + (c[:, [period]] - cumulative_holding[:, [period]]) * quantity
            + np.where(quantity > 0, s[:, [period]], 0)
        )
        improve = order < value[:, period + 1:]
        np.copyto(value[:, period + 1:], order, where=improve)
        predecessor[:, period + 1:][improve] = period

    production = np.zeros_like(d)
    initial = np.zeros(products)
    for product in range(products):
        end = periods
        while predecessor[product, end] >= 0:
            period = predecessor[product, end]
            production[product, period] = cumulative_demand[product, end] - cumulative_demand[product, period]
            end = period
        initial[product] = cumulative_demand[product, end]
    return production, initial


def _production_sweep(d, h, s, c, a, b, cap, p, ub_x, order, density, planned, deadline):
    """Replace opening-supplied demand with whole or partial feasible lots."""
    products, periods = d.shape
    production = np.zeros_like(d)
    setup = np.zeros(d.shape, dtype=np.int8)
    opening = d.copy()
    before = np.column_stack((np.zeros(products), np.cumsum(h[:, :-1], axis=1)))
    saving = p[:, None] + before - c
    for period in order:
        if perf_counter() >= deadline:
            break
        room = cap[period]
        possible = np.minimum(ub_x[:, period], np.sum(opening[:, period:], axis=1))
        unit_time, setup_time = a[:, period], b[:, period]
        for _ in range(products):
            if perf_counter() >= deadline:
                break
            can_set_up = room >= setup_time
            after_setup = np.maximum(room - setup_time, 0)
            time_limit = np.divide(after_setup, unit_time, out=np.full(products, np.inf), where=unit_time > 0)
            quantity = np.where(can_set_up, np.minimum(possible, time_limit), 0)
            use = setup_time + unit_time * quantity
            gain = saving[:, period] * quantity - s[:, period]
            scores = gain / np.maximum(use, 1e-12) if density else gain
            if planned is not None:
                scores = scores * np.where(planned[:, period] > 0, 1.5, 1.0)
            scores = np.where((quantity > 0) & (gain > 0), scores, -np.inf)
            product = int(np.argmax(scores))
            if not np.isfinite(scores[product]):
                break

            amount = quantity[product]
            production[product, period] = amount
            setup[product, period] = 1
            possible[product] = 0
            room = max(0, room - use[product])
            # Opening units in this ledger have explicit demand dates. A new
            # lot replaces only units with demand no earlier than production.
            outstanding = amount
            for due in range(period, periods):
                covered = min(outstanding, opening[product, due])
                opening[product, due] -= covered
                outstanding -= covered
                if outstanding <= 0:
                    break
    return production, setup, np.sum(opening, axis=1)


def build_incumbent(d, h, s, c, a, b, cap, p, ub_x, deadline):
    """Return (objective, production, setup, inventory, initial) within a short budget.

    Matrices use product-major order, and deadline is an absolute perf_counter
    value. The all-opening plan is the feasibility floor.
    """
    end = min(deadline, perf_counter() + 2.0)
    d, h, s, c, a, b, ub_x = (np.asarray(matrix, dtype=float) for matrix in (d, h, s, c, a, b, ub_x))
    cap = np.asarray(cap, dtype=float).reshape(-1)
    p = np.asarray(p, dtype=float).reshape(-1)
    empty = np.zeros_like(d)
    best = _evaluate(d, h, s, c, a, b, cap, p, ub_x, empty, np.zeros(d.shape, dtype=np.int8), np.sum(d, axis=1))
    if best is None:
        raise ValueError("All-opening feasible floor failed the original lot-sizing constraints")

    # Removing the shared capacity limits and the production upper bounds gives
    # independent uncapacitated lot-sizing problems. A relaxation minimizer
    # that is also feasible for the original problem is globally optimal.
    relaxed = _uncapacitated_lots(d, h, s, c, p, min(end - 0.03, perf_counter() + 0.35))
    planned = None
    if relaxed is not None:
        planned, initial = relaxed
        plan = _evaluate(d, h, s, c, a, b, cap, p, ub_x, planned, (planned > 0).astype(np.int8), initial)
        if plan is not None and plan[0] <= best[0]:
            return plan

    periods = d.shape[1]
    latest = range(periods - 1, -1, -1)
    variants = ((latest, True, planned), (range(periods), True, None), (latest, False, None))
    for order, density, preferred in variants:
        if perf_counter() >= end - 0.03:
            break
        production, setup, initial = _production_sweep(
            d, h, s, c, a, b, cap, p, ub_x, order, density, preferred, end - 0.025
        )
        plan = _evaluate(d, h, s, c, a, b, cap, p, ub_x, production, setup, initial)
        if plan is not None and plan[0] < best[0]:
            best = plan
    return best
