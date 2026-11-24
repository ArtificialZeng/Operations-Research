"""Project a numerical fractional location solution to exact primal and dual values."""

from fractions import Fraction
from math import isfinite

import numpy as np


OPEN_GRID = 10**9
DUAL_GRID = 10**8


def _ratio(value):
    value = float(value)
    if not isfinite(value):
        raise ValueError("A numerical LP value is not finite")
    return value.as_integer_ratio()


def _nearest(value, scale):
    numerator, denominator = _ratio(value)
    return round(Fraction(numerator * scale, denominator))


def _ceil_opening(value):
    numerator, denominator = _ratio(value)
    return min(OPEN_GRID, max(0, -((-numerator * OPEN_GRID) // denominator)))


def _floor_flow(value):
    numerator, denominator = _ratio(value)
    return max(0, (numerator * OPEN_GRID) // denominator)


def certify(data, x, shipping, demand_marginals, capacity_marginals=None, *, linked=False,
            shortage_marginals=None, eta=None):
    """Return exact objective endpoints for the LP represented by the supplied marginals.

    Shipping is in quantity ticks and includes real facilities in order, optionally
    followed by the dummy. Marginals have SciPy's sign and objective scaling. The
    exact units of their underlying RHS are quantity ticks. The returned upper is
    a feasible objective for the requested LP. The original-price value of the
    same repaired flow is given independently.
    """
    capacities = tuple(map(int, data.capacities))
    openings = tuple(map(Fraction, data.opening))
    demands = tuple(tuple(map(int, row)) for row in data.demands)
    rates = tuple(tuple(map(int, row)) for row in data.cost)
    divisor = int(data.divisor)
    n = len(capacities) - 1
    scenarios = len(demands)
    m = len(rates[-1])
    if not linked and (eta is not None or shortage_marginals is not None):
        raise ValueError("The separated certificate uses the proportional arc links")
    if (eta is None) != (shortage_marginals is None):
        raise ValueError("A separated certificate needs both its penalty and shortage marginals")
    if (n <= 0 or not m or not scenarios or divisor <= 0 or min(capacities) < 0
            or len(rates) != len(capacities) or len(openings) != len(capacities)
            or any(len(row) != m or min(row) < 0 for row in (*rates, *demands))
            or max(map(sum, demands)) > capacities[-1]):
        raise ValueError("The certificate expects complete nonnegative transport and complete dummy recourse")

    x = np.asarray(x)
    shipping = np.asarray(shipping)
    demand_marginals = np.asarray(demand_marginals)
    if (x.shape != (n,) or shipping.shape not in {(scenarios, n, m), (scenarios, n + 1, m)}
            or demand_marginals.shape != (scenarios, m)):
        raise ValueError("Unexpected opening, shipping, or demand marginal dimensions")
    if capacity_marginals is not None:
        capacity_marginals = np.asarray(capacity_marginals)
        if capacity_marginals.shape != (scenarios, n):
            raise ValueError("Unexpected facility marginal dimensions")
    separated = eta is not None
    if separated:
        shortage_marginals = np.asarray(shortage_marginals)
        if shortage_marginals.shape != (scenarios,):
            raise ValueError("Unexpected shortage marginal dimensions")
        dummy_rate, = set(rates[-1])
        eta = int(eta)
        if not 2 * max(map(max, rates[:-1])) <= eta <= dummy_rate:
            raise ValueError("The separation price is outside the exact linked regime")
        premium = dummy_rate - eta
        reduced = (eta,) * m
    else:
        premium = 0
        reduced = rates[-1]

    x_grid = tuple(_ceil_opening(value) for value in x)
    exact_sites = tuple(capacity * opened for capacity, opened in zip(capacities, x_grid))
    opening_value = openings[-1] + sum(cost * Fraction(opened, OPEN_GRID)
                                      for cost, opened in zip(openings, x_grid))
    per_site_dual = [0] * n
    dual_constant = 0
    dual_scale = divisor * DUAL_GRID
    dual_rates = tuple(tuple(c * DUAL_GRID for c in site) for site in rates[:-1])
    dummy_dual_rates = tuple(c * DUAL_GRID for c in reduced)
    primal_value = 0
    original_value = 0
    trimmed_grid = 0
    shortage_positive = 0

    for scenario, demand in enumerate(demands):
        priced_demand = tuple(min(_nearest(raw, dual_scale), cap)
                              for raw, cap in zip(demand_marginals[scenario], dummy_dual_rates, strict=True))
        dual_constant += sum(alpha * target for alpha, target in zip(priced_demand, demand, strict=True))
        total = sum(demand)
        if separated:
            loss_weight = min(premium * DUAL_GRID, max(0, -_nearest(shortage_marginals[scenario], dual_scale)))
            dual_constant += loss_weight * total
            minimum_shortage_grid = max(0, total * OPEN_GRID - sum(
                min(cap, total) * opened for cap, opened in zip(capacities, x_grid)))
            shortage_positive += int(minimum_shortage_grid > 0)
            primal_value += premium * minimum_shortage_grid

        remaining = [value * OPEN_GRID for value in demand]
        real_cost = 0
        for site, available in enumerate(exact_sites):
            slack = available
            differences = tuple(c - alpha for c, alpha in zip(dual_rates[site], priced_demand, strict=True))
            if linked and capacity_marginals is not None:
                cap_dual = min(0, _nearest(capacity_marginals[scenario, site], dual_scale))
                link_dual = tuple(min(0, difference - cap_dual) for difference in differences)
                per_site_dual[site] += sum(gamma * target for gamma, target in zip(link_dual, demand, strict=True))
            else:
                cap_dual = min(0, *differences)
            per_site_dual[site] += capacities[site] * cap_dual
            if separated:
                per_site_dual[site] -= loss_weight * min(capacities[site], total)

            for customer, quoted in enumerate(shipping[scenario, site]):
                rounded = _floor_flow(quoted)
                shipment = min(rounded, slack, remaining[customer])
                if linked:
                    shipment = min(shipment, x_grid[site] * demand[customer])
                trimmed_grid += rounded - shipment
                slack -= shipment
                remaining[customer] -= shipment
                real_cost += shipment * rates[site][customer]
        # Remaining demand goes to a fixed dummy with capacity for the entire row.
        primal_value += real_cost + sum(need * cost for need, cost in zip(remaining, reduced, strict=True))
        original_value += real_cost + sum(need * cost for need, cost in zip(remaining, rates[-1], strict=True))

    lower = openings[-1] + Fraction(dual_constant, dual_scale) + sum(
        min(0, cost + Fraction(coefficient, dual_scale))
        for cost, coefficient in zip(openings[:-1], per_site_dual, strict=True))
    upper = opening_value + Fraction(primal_value, divisor * OPEN_GRID)
    original = opening_value + Fraction(original_value, divisor * OPEN_GRID)
    if upper < lower or (separated and upper > original):
        raise ArithmeticError("The exact repaired endpoints are inconsistent")
    return {"lower": str(lower), "upper": str(upper), "relative_gap": str((upper - lower) / upper if upper else 0),
            "original_same_primal": str(original), "rounded_opening": x_grid, "grid": OPEN_GRID,
            "opening_cost": str(opening_value), "dual_grid": DUAL_GRID, "scenarios": scenarios,
            "trimmed_flow_grid_ticks": trimmed_grid, "positive_hinge_scenarios": shortage_positive if separated else None}
