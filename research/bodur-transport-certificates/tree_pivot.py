"""One exact dual-simplex transportation pivot for a failed tree certificate."""

from time import perf_counter

from official_tree import ExactRecourse, Tree


def violated_subtree(tree, demand):
    balances = [*tree.supplies, *(-d for d in demand), sum(demand) - sum(tree.supplies)]
    children = [[] for _ in balances]
    worst = 0
    leaving = None
    for node, parent, supplier, customer in tree.rooted_edges:
        children[parent].append(node)
        flow = balances[node] if node == supplier else -balances[node]
        if flow < worst:
            worst = flow
            leaving = node, (supplier, customer), balances[node]
        balances[parent] += balances[node]
    if leaving is None:
        return None
    node, edge, net = leaving
    subtree = set()
    pending = [node]
    while pending:
        item = pending.pop()
        subtree.add(item)
        pending.extend(children[item])
    return subtree, edge, 1 if net > 0 else -1


def orient(arcs, sink):
    edges = [[] for _ in range(sink + 1)]
    for supplier, customer in arcs:
        edges[supplier].append((customer, supplier, customer))
        edges[customer].append((supplier, supplier, customer))
    visited = {sink}
    order = []
    stack = [sink]
    while stack:
        parent = stack.pop()
        for node, supplier, customer in edges[parent]:
            if node not in visited:
                visited.add(node)
                stack.append(node)
                order.append((node, parent, supplier, customer))
    return tuple(reversed(order)) if len(visited) == sink + 1 and len(arcs) == sink else None


def pivot_once(tree, demand, costs, capacities):
    split = violated_subtree(tree, demand)
    if split is None:
        return None
    subtree, leaving, direction = split
    m = len(tree.facilities)
    sink = m + len(demand)
    p = [-max(0, max(v - c for v, c in zip(tree.demands_price, costs[i], strict=True)))
         for i in tree.facilities]
    p.extend(-v for v in tree.demands_price)
    p.append(0)
    candidates = []
    for supplier, i in enumerate(tree.facilities):
        for customer, cost in enumerate((*costs[i], 0), start=m):
            if direction * (int(supplier in subtree) - int(customer in subtree)) != 1:
                continue
            slack = cost - p[supplier] + p[customer]
            if slack < 0:
                return None
            candidates.append((slack, supplier, customer))
    if not candidates:
        return None
    shift, supplier, customer = min(candidates)
    for node in subtree:
        p[node] += direction * shift
    arcs = {(i, j) for _, _, i, j in tree.rooted_edges}
    arcs.remove(leaving)
    arcs.add((supplier, customer))
    order = orient(sorted(arcs), sink)
    alpha = tuple(-value for value in p[m:sink])
    if order is None or min(alpha) < 0 or any(value > 0 for value in p[:m]):
        return None
    beta = tuple(max(0, max(v - c for v, c in zip(alpha, row, strict=True))) for row in costs)
    if any(p[supplier] != -beta[i] for supplier, i in enumerate(tree.facilities)):
        return None
    if any(p[i] - p[j] != (0 if j == sink else costs[tree.facilities[i]][j - m]) for i, j in arcs):
        return None
    slopes = tuple(value * cap for value, cap in zip(beta, capacities, strict=True))
    return Tree(order, tree.facilities, tree.supplies, alpha, slopes, tree.objective_scale, tree.quantity_scale)


class RepairingRecourse(ExactRecourse):
    def __init__(self, instance):
        super().__init__(instance)
        self.telemetry = {"repair_attempts": 0, "repair_hits": 0, "repair_pivots": 0, "repair_seconds": 0.0}

    def try_scenario(self, index, extract_flows):
        tree = self.tree
        ordinary = super().try_scenario(index, extract_flows)
        if tree is None or ordinary is not None:
            return ordinary
        self.telemetry["repair_attempts"] += 1
        started = perf_counter()
        try:
            demand = self.demands[index]
            seen = {frozenset((i, j) for _, _, i, j in tree.rooted_edges)}
            for _ in range(8):
                self.telemetry["repair_pivots"] += 1
                tree = pivot_once(tree, demand, self.costs, self.capacities)
                if tree is None:
                    break
                signature = frozenset((i, j) for _, _, i, j in tree.rooted_edges)
                if signature in seen:
                    break
                if tree.evaluate(demand, False) is not None:
                    self.tree = tree
                    self.telemetry["repair_hits"] += 1
                    return super().try_scenario(index, extract_flows)
                seen.add(signature)
            return None
        finally:
            self.telemetry["repair_seconds"] += perf_counter() - started
