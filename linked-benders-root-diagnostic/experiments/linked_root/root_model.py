"""Sparse deterministic equivalents of the plain and linked fractional relaxations."""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import OptimizeWarning, linprog
from scipy.sparse import coo_array
import warnings


@dataclass(frozen=True)
class RootModel:
    objective: np.ndarray
    demand_rows: object
    demand_rhs: np.ndarray
    inequality_rows: object
    inequality_rhs: np.ndarray
    bounds: np.ndarray
    shape: tuple[int, int, int]
    eta: int | None

    def optimize(self, seconds):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=OptimizeWarning, message=r"Unrecognized options.*")
            return linprog(self.objective, A_ub=self.inequality_rows, b_ub=self.inequality_rhs,
                           A_eq=self.demand_rows, b_eq=self.demand_rhs, bounds=self.bounds, method="highs-ipm",
                           options={"threads": 1, "time_limit": seconds, "ipm_optimality_tolerance": 1e-10})

    def split(self, result):
        scenarios, real, customers = self.shape
        limit = real + scenarios * (real + 1) * customers
        opening = result.x[:real]
        shipping = result.x[real:limit].reshape(scenarios, real + 1, customers)
        demand = result.eqlin.marginals.reshape(scenarios, customers)
        capacity = result.ineqlin.marginals[:scenarios * real].reshape(scenarios, real)
        shortage = None if self.eta is None else result.ineqlin.marginals[-scenarios:]
        return opening, shipping, demand, capacity, shortage


def matrix(parts, shape):
    row, col, val = (np.concatenate(block) for block in zip(*parts, strict=True))
    return coo_array((val, (row, col)), shape=shape).tocsc()


def formulate(data, mode):
    if mode not in {"plain", "linked", "linked_separated"}:
        raise ValueError("Unknown fractional root mode")
    demands = np.asarray(data.demands, dtype=np.int64)
    scenarios, customers = demands.shape
    real = len(data.capacities) - 1
    caps = np.asarray(data.capacities[:real], dtype=np.int64)
    costs = np.asarray(data.cost, dtype=object).copy()
    totals = demands.sum(axis=1)
    rho = int(costs[-1, 0])
    if not np.all(costs[-1] == rho) or min(data.capacities) < 0 or data.capacities[-1] < int(totals.max()):
        raise ValueError("Expected complete split transport and a sufficiently large uniform dummy")
    eta = None
    if mode == "linked_separated":
        eta = int(costs[:real].max()) * 2
        if rho < eta:
            raise ValueError("The original price is below the sharp uniform linked threshold")
        costs[-1] = eta
    flow = np.arange(real, real + scenarios * (real + 1) * customers, dtype=np.int64).reshape(scenarios, real + 1, customers)
    real_flow = flow[:, :real, :]
    count = real + flow.size
    if eta is not None:
        hinge = np.arange(count, count + scenarios)
        count += scenarios
    objective = np.empty(count)
    objective[:real] = [float(f) for f in data.opening[:real]]
    prices = np.asarray([int(v) / data.divisor for v in costs.ravel()])
    objective[real:real + flow.size] = np.tile(prices, scenarios)
    if eta is not None:
        objective[hinge] = (rho - eta) / data.divisor
    bounds = np.empty((count, 2))
    bounds[:, 0] = 0
    bounds[:, 1] = np.inf
    bounds[:real, 1] = 1

    demand_index = np.arange(scenarios * customers).reshape(scenarios, 1, customers)
    eq = matrix([(np.broadcast_to(demand_index, flow.shape).ravel(), flow.ravel(), np.ones(flow.size))],
                (demands.size, count))
    row_count = scenarios * real
    site_idx = np.arange(real)
    capacity_index = np.arange(row_count).reshape(scenarios, real, 1)
    blocks = [(np.broadcast_to(capacity_index, real_flow.shape).ravel(), real_flow.ravel(), np.ones(real_flow.size)),
              (capacity_index.ravel(), np.tile(site_idx, scenarios), -np.tile(caps, scenarios))]
    rhs = np.zeros(row_count)
    if mode != "plain":
        link_index = np.arange(row_count, row_count + real_flow.size)
        x_idx = np.broadcast_to(site_idx[None, :, None], real_flow.shape).ravel()
        d_values = np.broadcast_to(demands[:, None, :], real_flow.shape).ravel()
        blocks.extend([(link_index, real_flow.ravel(), np.ones(real_flow.size)), (link_index, x_idx, -d_values)])
        row_count += real_flow.size
        rhs = np.r_[rhs, np.zeros(real_flow.size)]
    if eta is not None:
        hinge_index = np.arange(row_count, row_count + scenarios)
        truncated = np.minimum(totals[:, None], caps[None, :])
        blocks.extend([(np.repeat(hinge_index, real), np.tile(site_idx, scenarios), -truncated.ravel()),
                       (hinge_index, hinge, -np.ones(scenarios))])
        row_count += scenarios
        rhs = np.r_[rhs, -totals]
    ub = matrix(blocks, (row_count, count))
    return RootModel(objective, eq, demands.ravel(), ub, rhs, bounds, (scenarios, real, customers), eta)
