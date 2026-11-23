"""Exact decimal transportation-tree reuse for binary facility layouts."""

from dataclasses import dataclass
from decimal import Decimal
from math import fsum

import numpy as np


def integer_table(rows):
    decimals = [[Decimal(value) for value in row] for row in rows]
    digits = max(max(0, -value.as_tuple().exponent) for row in decimals for value in row)
    scale = 10 ** digits
    table = []
    for row in decimals:
        converted = []
        for value in row:
            numerator, denominator = value.as_integer_ratio()
            number, remainder = divmod(numerator * scale, denominator)
            if remainder or number < 0:
                raise ValueError("Nonnegative exact decimal inputs are required")
            converted.append(number)
        table.append(tuple(converted))
    return scale, table


@dataclass
class Tree:
    rooted_edges: tuple
    facilities: tuple
    supplies: tuple
    demands_price: tuple
    capacity_shadow: tuple
    objective_scale: int
    quantity_scale: int

    def evaluate(self, demand, extract_flows):
        balances = [*self.supplies, *(-value for value in demand), sum(demand) - sum(self.supplies)]
        shipments = []
        facilities = len(self.facilities)
        for node, parent, supplier, customer in self.rooted_edges:
            quantity = balances[node] if node == supplier else -balances[node]
            if quantity < 0:
                return None
            balances[parent] += balances[node]
            if extract_flows and quantity and customer != len(balances) - 1:
                shipments.append((self.facilities[supplier], customer - facilities, quantity))
        if balances[-1] != 0:
            return None
        intercept = sum(value * price for value, price in zip(demand, self.demands_price, strict=True))
        slope = sum(self.capacity_shadow[i] for i in self.facilities)
        value = (intercept - slope) / self.objective_scale
        witness = None
        if extract_flows:
            witness = {}
            for i, j, quantity in shipments:
                witness.setdefault(str(i), {})[str(j)] = quantity / self.quantity_scale
        return value, intercept, witness


class ExactRecourse:
    def __init__(self, instance):
        capacity = [f["capacity"] for f in instance["facilities"]]
        demands = [s["demands"] for s in instance["scenarios"]]
        self.quantity_scale, table = integer_table([capacity, *demands])
        self.capacities, *self.demands = table
        cost_scale, self.costs = integer_table(instance["transportation_costs"])
        self.objective_scale = cost_scale * self.quantity_scale
        self.probability_scale, probability_rows = integer_table([[s["probability"] for s in instance["scenarios"]]])
        self.probability_numerators = probability_rows[0]
        self.float_costs = np.asarray(instance["transportation_costs"], dtype=np.float64)
        self.tree = None
        self.layout = ()
        self.attempts = 0

    def begin(self, x):
        self.tree = None
        self.attempts = 0
        if not np.all((x == 0) | (x == 1)):
            self.layout = ()
        else:
            self.layout = tuple(np.flatnonzero(x).tolist())

    def learn(self, alpha, beta, y_vars):
        if not self.layout or self.attempts >= 16:
            return
        self.attempts += 1
        supplies = tuple(self.capacities[i] for i in self.layout)
        customers = len(alpha)
        facilities = len(self.layout)
        sink = facilities + customers
        rows = [[variable.solution_value() for variable in y_vars[i]] for i in self.layout]
        graph = [[] for _ in range(sink + 1)]
        parents = list(range(sink + 1))

        def root(node):
            while parents[node] != node:
                node = parents[node]
            return node

        def join(supplier, customer, cost):
            left, right = root(supplier), root(customer)
            if left == right:
                return False
            parents[left] = right
            graph[supplier].append((customer, supplier, customer, cost))
            graph[customer].append((supplier, supplier, customer, cost))
            return True

        for supplier, i in enumerate(self.layout):
            for j, flow in enumerate(rows[supplier]):
                if flow > 1e-9 and not join(supplier, facilities + j, self.costs[i][j]):
                    return
            spare = supplies[supplier] / self.quantity_scale - fsum(rows[supplier])
            if spare > 1e-9 and not join(supplier, sink, 0):
                return
        if sum(len(edges) for edges in graph) != 2 * sink:
            for supplier, i in enumerate(self.layout):
                if beta[i] < 1e-9:
                    join(supplier, sink, 0)
                tight = np.flatnonzero(np.abs(self.float_costs[i] - alpha + beta[i]) <= 1e-8)
                for j in tight:
                    join(supplier, facilities + int(j), self.costs[i][j])
        potentials = {sink: 0}
        rooted_edges = []
        stack = [sink]
        while stack:
            node = stack.pop()
            for child, supplier, customer, cost in graph[node]:
                if child in potentials:
                    continue
                potentials[child] = cost - potentials[node]
                stack.append(child)
                rooted_edges.append((child, node, supplier, customer))
        if len(potentials) != sink + 1:
            return
        alpha_exact = tuple(potentials[facilities + j] for j in range(customers))
        if min(alpha_exact) < 0:
            return
        beta_exact = tuple(max(0, max(price - cost for price, cost in zip(alpha_exact, row, strict=True)))
                           for row in self.costs)
        if any(potentials[supplier] != -beta_exact[i] for supplier, i in enumerate(self.layout)):
            return
        shadow = tuple(beta * capacity for beta, capacity in zip(beta_exact, self.capacities, strict=True))
        self.tree = Tree(tuple(reversed(rooted_edges)), self.layout, supplies, alpha_exact, shadow,
                         self.objective_scale, self.quantity_scale)

    def try_scenario(self, index, extract_flows):
        if self.tree is None:
            return None
        result = self.tree.evaluate(self.demands[index], extract_flows)
        if result is None:
            self.tree = None
            return None
        value, intercept, witness = result
        probability = self.probability_numerators[index]
        scale = self.objective_scale * self.probability_scale
        intercept = np.nextafter((probability * intercept) / scale, -np.inf) if intercept and probability else 0.0
        coefficients = np.asarray([np.nextafter((probability * coefficient) / scale, np.inf) if coefficient and probability else 0.0
                                   for coefficient in self.tree.capacity_shadow])
        return value, intercept, coefficients, witness
