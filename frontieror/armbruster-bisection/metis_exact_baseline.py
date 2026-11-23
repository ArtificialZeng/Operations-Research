"""PyMetis recursive bisection followed by deterministic integer-capacity repair."""

import argparse
from multiprocessing import get_context
from pathlib import Path
import sys
from time import perf_counter

from baseline import checked_solution, checkpoint, csr, load_graph, stop_worker


MAX_SUBSET_WEIGHT = 8192


def metis_worker(connection, weights, graph, seed):
    import pymetis

    offsets, costs, targets = graph
    width = pymetis.zero_copy_dtype().itemsize * 8
    limit = (1 << (width - 1)) - 1
    if sum(weights) > limit or len(costs) > limit:
        raise ValueError("Graph size or original population exceeds the installed METIS integer range")
    directed_total = sum(costs)
    factor = max(1, (directed_total + limit - 1) // limit)
    if factor > 1:
        scaled = [max(1, cost // factor) for cost in costs]
        while sum(scaled) > limit:
            factor *= 2
            scaled = [max(1, cost // factor) for cost in costs]
        costs = scaled
    with connection:
        _, labels = pymetis.part_graph(
            2, adjacency=pymetis.CSRAdjacency(offsets, targets), vweights=weights,
            eweights=costs, recursive=True, options=pymetis.Options(seed=seed, ufactor=1),
        )
        connection.send((bytes(int(side) for side in labels), factor))


def metis_seed(weights, graph, seed, deadline):
    context = get_context("spawn")
    parent, child = context.Pipe(duplex=False)
    process = context.Process(target=metis_worker, args=(child, weights, graph, seed))
    try:
        process.start()
    except BaseException:
        parent.close()
        raise
    finally:
        child.close()
    try:
        if not parent.poll(max(0, deadline - perf_counter())):
            raise TimeoutError("METIS seed exceeded its budget")
        return parent.recv()
    finally:
        stop_worker((parent, process))


def transfer_subset(nodes, weights, lower, upper, deadline):
    """Find the first reachable transfer in the given cost-ordered search."""
    if upper < lower:
        return None
    mask = (1 << (upper + 1)) - 1
    acceptable = mask ^ ((1 << lower) - 1)
    reachable = 1
    predecessor = [-1] * (upper + 1)
    for node in nodes:
        if perf_counter() >= deadline:
            return None
        weight = weights[node]
        if weight > upper:
            continue
        added = ((reachable << weight) & mask) & ~reachable
        reachable |= added
        transferred = added & acceptable
        while added:
            low_bit = added & -added
            predecessor[low_bit.bit_length() - 1] = node
            added ^= low_bit
        if transferred:
            total = (transferred & -transferred).bit_length() - 1
            selected = []
            while total:
                member = predecessor[total]
                selected.append(member)
                total -= weights[member]
            return selected
    return None


def repair(labels, weights, capacity, edges, deadline):
    loads = [0, 0]
    for side, weight in zip(labels, weights, strict=True):
        loads[side] += weight
    source = int(loads[1] > loads[0])
    excess = loads[source] - capacity
    if excess <= 0:
        return labels, "already_exact"
    spare = capacity - loads[1 - source]

    change = [0] * len(labels)
    crossings = {}
    for u, v, cost in edges:
        if u == v:
            continue
        if labels[u] != labels[v]:
            pair = (min(u, v), max(u, v))
            crossings[pair] = crossings.get(pair, 0) + cost
            cost = -cost
        change[u] += cost
        change[v] += cost

    donors = [node for node, side in enumerate(labels) if side == source and weights[node] > 0]
    direct = min((node for node in donors if excess <= weights[node] <= spare),
                 key=lambda node: (change[node], node), default=None)
    donors.sort(key=lambda node: (change[node] / weights[node], change[node], node))
    subset = transfer_subset(donors, weights, excess, min(spare, MAX_SUBSET_WEIGHT), deadline)
    moves = []
    if direct is not None:
        moves.append(("direct", [direct]))
    if subset:
        moves.append(("subset", subset))

    # An exact two-sided exchange can succeed when no donor subset has the needed weight.
    receivers = {}
    for node, side in enumerate(labels):
        if side == source:
            continue
        incumbent = receivers.get(weights[node])
        if incumbent is None or change[node] < change[incumbent]:
            receivers[weights[node]] = node
    if perf_counter() < deadline:
        def swap_cost(pair):
            a, b = pair
            crossing = crossings.get((min(a, b), max(a, b)), 0)
            return change[a] + change[b] + 2 * crossing, a, b

        swaps = ((a, receivers[weights[a] - excess]) for a in donors if weights[a] - excess in receivers)
        exchange = min(swaps, key=swap_cost, default=None)
        if exchange:
            moves.append(("exchange", exchange))

    solutions = []
    for name, nodes in moves:
        amended = bytearray(labels)
        for node in nodes:
            amended[node] ^= 1
        result = checked_solution(amended, weights, capacity, edges)
        if result is not None:
            solutions.append((result["objective_value"], name, amended))
    if not solutions:
        raise ValueError(f"No deterministic exact repair found for overload {excess}")
    _, name, amended = min(solutions)
    return amended, name


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--instance", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--time-limit", required=True, type=float)
    parser.add_argument("--seed", default=0, type=int)
    args = parser.parse_args()
    started = perf_counter()
    margin = min(0.50, args.time_limit * 0.1)
    deadline = started + args.time_limit - margin
    weights, capacity, edges = load_graph(args.instance)
    graph = csr(len(weights), edges)
    seed_deadline = max(started + (deadline - started) * 0.8, deadline - 2.0)
    labels, factor = metis_seed(weights, graph, args.seed, seed_deadline)
    if len(labels) != len(weights) or any(side not in (0, 1) for side in labels):
        raise ValueError("METIS seed returned an invalid label vector")
    amended, status = repair(labels, weights, capacity, edges, deadline)
    checked = checked_solution(amended, weights, capacity, edges)
    if checked is None:
        raise ValueError("Repaired result failed exact native-weight and original-cut verification")
    checkpoint(args.output, checked)
    print(f"seed={args.seed} edge_cost_divisor={factor} repair={status}", file=sys.stderr)


if __name__ == "__main__":
    main()
