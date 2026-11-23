"""KaHIP starts followed by balance-preserving exact boundary search."""

import argparse
import heapq
from importlib.util import find_spec
import json
from math import fsum
import multiprocessing
from pathlib import Path
import random
import sys
from time import monotonic


SEEDS = (7, 31, 101, 257, 509, 1021, 2053, 4099)
ZONE_SIZES = (46, 70, 94, 118)


class Graph:
    def __init__(self, data):
        self.count = data["num_nodes"]
        self.weights = data["node_weights"]
        self.capacity = data["bisection_capacity_F"]
        self.total = sum(self.weights)
        self.minimum = self.total - self.capacity
        self.adj = [[] for _ in range(self.count)]
        self.edges = []
        for (u, v), weight in zip(data["edges"], data["edge_weights"], strict=True):
            if u != v and weight:
                self.edges.append((u, v, weight))
                self.adj[u].append((v, weight))
                self.adj[v].append((u, weight))
        self.integer_edges = all(isinstance(weight, int) for _, _, weight in self.edges)

    def load(self, side):
        return sum(weight for weight, chosen in zip(self.weights, side, strict=True) if chosen)

    def cut(self, side):
        weights = (weight for u, v, weight in self.edges if side[u] != side[v])
        return sum(weights) if self.integer_edges else fsum(weights)

    def feasible(self, side):
        return len(side) == self.count and self.minimum <= self.load(side) <= self.capacity

    def flip_cost(self, side, vertex):
        return sum(weight if side[vertex] == side[other] else -weight for other, weight in self.adj[vertex])


def greedy_balance(graph):
    side = [0] * graph.count
    load = [0, 0]
    order = sorted(range(graph.count), key=lambda vertex: (-graph.weights[vertex], vertex))
    for vertex in order:
        group = int(load[1] < load[0])
        side[vertex] = group
        load[group] += graph.weights[vertex]
    return side


def repair_seed(graph, side):
    """Try an exact-capacity repair by one flip or one opposing pair."""
    load = graph.load(side)
    if graph.minimum <= load <= graph.capacity:
        return side
    heavy = int(load > graph.capacity)
    heavy_load = load if heavy else graph.total - load
    low = heavy_load - graph.capacity
    high = heavy_load - graph.minimum
    heavy_vertices = [vertex for vertex, group in enumerate(side) if group == heavy]
    light_vertices = [vertex for vertex, group in enumerate(side) if group != heavy]
    single = [vertex for vertex in heavy_vertices if low <= graph.weights[vertex] <= high]
    fixed = side.copy()
    if single:
        fixed[min(single, key=lambda vertex: (graph.flip_cost(side, vertex), vertex))] ^= 1
        return fixed

    def choices(vertices):
        # Keep the best proposals at each distinct weight so uncommon weights
        # still have a chance to restore feasibility.
        best = {}
        for vertex in vertices:
            weight = graph.weights[vertex]
            change = graph.flip_cost(side, vertex)
            best.setdefault(weight, []).append((change, vertex))
        representatives = [item for rows in best.values() for item in sorted(rows)[:2]]
        return sorted(representatives)[:48]

    swaps = []
    light = choices(light_vertices)
    for change_u, u in choices(heavy_vertices):
        shared = {}
        for v, weight in graph.adj[u]:
            shared[v] = shared.get(v, 0) + weight
        for change_v, v in light:
            if low <= graph.weights[u] - graph.weights[v] <= high:
                swaps.append((change_u + change_v + 2 * shared.get(v, 0), u, v))
    if not swaps:
        return None
    _, u, v = min(swaps)
    fixed[u] ^= 1
    fixed[v] ^= 1
    return fixed


def kahip_worker(graph, connection):
    import kahip

    # The exact verifier still uses the original signed weights. Unweighted and
    # signed edges are projected onto positive integer weights only for seeding.
    total_cost = fsum(max(1.0, float(w)) for _, _, w in graph.edges)
    adjustment = min(1.0, 500_000_000 / max(1.0, total_cost))
    xadj = [0]
    neighbors = []
    costs = []
    for row in graph.adj:
        for other, weight in row:
            neighbors.append(other)
            costs.append(max(1, round(weight * adjustment)))
        xadj.append(len(neighbors))
    node_weights = [max(1, weight) for weight in graph.weights]
    slack = max(0.0, min(0.015, 2 * graph.capacity / max(1, graph.total) - 1))
    try:
        for index, seed in enumerate(SEEDS):
            mode = getattr(kahip, "ECO", 1) if index % 3 == 0 else getattr(kahip, "STRONG", 2)
            _, groups = kahip.kaffpa(node_weights, xadj, costs, neighbors, 2, slack, True, seed, mode)
            connection.send(list(groups))
    finally:
        connection.close()


def kahip_seeds(graph, deadline):
    if not graph.edges or sum(max(1, w) for w in graph.weights) > 2_000_000_000:
        return
    if find_spec("kahip") is None or deadline <= monotonic():
        return
    method = "fork" if "fork" in multiprocessing.get_all_start_methods() else "spawn"
    context = multiprocessing.get_context(method)
    receiver, sender = context.Pipe(duplex=False)
    worker = context.Process(target=kahip_worker, args=(graph, sender), daemon=True)
    worker.start()
    sender.close()
    try:
        while receiver.poll(max(0, deadline - monotonic())):
            try:
                side = receiver.recv()
            except EOFError:
                break
            if len(side) == graph.count and all(group in (0, 1) for group in side):
                yield side
            if monotonic() >= deadline:
                break
    finally:
        receiver.close()
        if worker.is_alive():
            worker.terminate()
        worker.join(0.15)
        if worker.is_alive():
            worker.kill()
            worker.join(0.15)


def balanced_fallback(graph, hint, cp, deadline):
    model = cp.CpModel()
    vertices = [model.new_bool_var("") for _ in graph.weights]
    load = sum(weight * variable for weight, variable in zip(graph.weights, vertices, strict=True))
    model.add_linear_constraint(load, graph.minimum, graph.capacity)
    for var, group in zip(vertices, hint, strict=True):
        model.add_hint(var, group)
    seconds = deadline - monotonic()
    if seconds <= 0:
        return None
    solver = cp.CpSolver()
    solver.parameters.num_workers = 2
    solver.parameters.random_seed = SEEDS[0]
    solver.parameters.max_time_in_seconds = seconds
    solver.parameters.stop_after_first_solution = True
    status = solver.solve(model)
    if status in (cp.OPTIMAL, cp.FEASIBLE):
        return [int(solver.value(var)) for var in vertices]
    return None


def boundary_ranking(graph, side):
    scores = []
    boundary = [[], []]
    for vertex, group in enumerate(side):
        same = 0
        across = 0
        touches_other = False
        for other, weight in graph.adj[vertex]:
            if side[other] == group:
                same += weight
            else:
                across += weight
                touches_other = True
        scores.append(across - same)
        if touches_other:
            boundary[group].append(vertex)
    for group in range(2):
        boundary[group].sort(key=lambda v: (-scores[v], v))
        if not boundary[group]:
            boundary[group] = [v for v, value in enumerate(side) if value == group]
    return scores, boundary


def select_zone(graph, side, scores, boundary, size, iteration, rng):
    if graph.count <= size:
        return list(range(graph.count))
    group = iteration % 2
    starts = boundary[group]
    if not starts:
        starts = sorted(range(graph.count), key=lambda v: (-scores[v], v))
    root = starts[0] if iteration == 0 else rng.choice(starts[:32])
    opposite = [(weight, scores[v], -v) for v, weight in graph.adj[root] if side[v] != side[root]]
    seeds = [root]
    if opposite:
        seeds.append(-max(opposite)[2])
    elif boundary[1 - side[root]]:
        seeds.append(boundary[1 - side[root]][0])

    # Start at a boundary edge and grow the zone through heavy adjacent edges.
    ordered = list(seeds)
    selected = set(ordered)
    todo = []
    affinity = {}
    for u in seeds:
        for v, weight in graph.adj[u]:
            if v not in selected:
                affinity[v] = affinity.get(v, 0) + abs(weight)
    for v, strength in affinity.items():
        heapq.heappush(todo, (-strength, -scores[v], v))
    while todo and len(selected) < size:
        negative_strength, _, u = heapq.heappop(todo)
        if u in selected or affinity[u] != -negative_strength:
            continue
        selected.add(u)
        ordered.append(u)
        for v, weight in graph.adj[u]:
            if v not in selected:
                affinity[v] = affinity.get(v, 0) + abs(weight)
                heapq.heappush(todo, (-affinity[v], -scores[v], v))
    if len(selected) < size:
        supplemental = sorted(boundary[0] + boundary[1], key=lambda v: (-scores[v], v))
        ordered.extend(v for v in supplemental if v not in selected)
    return ordered[:size]


def weight_complement_zone(graph, side, scores, boundary, zone):
    """Reserve a few slots for off-boundary one- or two-vertex weight matches."""
    if len(zone) < 16 or len(zone) == graph.count:
        return zone, 0
    reserve = 6
    boundary_nodes = set(boundary[0]) | set(boundary[1])
    original = set(zone)
    core = zone[:-reserve]
    present = [{graph.weights[v] for v in core if side[v] == group} for group in (0, 1)]
    pools = [{}, {}]
    for vertex, group in enumerate(side):
        if vertex not in original and vertex not in boundary_nodes and graph.weights[vertex] > 0:
            pools[group].setdefault(graph.weights[vertex], []).append(vertex)
    for pool in pools:
        for vertices in pool.values():
            vertices.sort(key=lambda v: (-scores[v], v))
    anchors = sorted(core, key=lambda u: (graph.weights[u] in present[1 - side[u]], -scores[u], u))

    extras = []
    used = set()
    for u in anchors[:16]:
        if len(extras) == reserve:
            break
        target = graph.weights[u]
        pool = pools[1 - side[u]]
        equal = next((v for v in pool.get(target, ()) if v not in used), None)
        if equal is not None:
            extras.append(equal)
            used.add(equal)
            continue
        if reserve - len(extras) < 2:
            continue
        best = None
        for weight, vertices in pool.items():
            other_weight = target - weight
            if weight > other_weight or other_weight not in pool:
                continue
            first = next((v for v in vertices if v not in used), None)
            second = next((v for v in pool[other_weight] if v not in used and v != first), None)
            if first is not None and second is not None:
                option = (-scores[first] - scores[second], first, second)
                if best is None or option < best:
                    best = option
        if best is not None:
            _, first, second = best
            extras.extend((first, second))
            used.update((first, second))
    return core + extras + zone[len(core):len(zone) - len(extras)], len(extras)


def optimize_zone(graph, side, zone, cp, deadline, seed):
    model = cp.CpModel()
    variables = {u: model.new_bool_var("") for u in zone}
    model.add(
        sum(graph.weights[u] * variables[u] for u in zone)
        == sum(graph.weights[u] for u in zone if side[u])
    )
    terms = []
    for u in zone:
        unary = 0
        for v, weight in graph.adj[u]:
            if v not in variables:
                unary += weight * (1 - 2 * side[v])
            elif u < v:
                cut = model.new_bool_var("")
                model.add_bool_xor((variables[u], variables[v], cut.Not()))
                model.add_hint(cut, int(side[u] != side[v]))
                terms.append(weight * cut)
        if unary:
            terms.append(unary * variables[u])
        model.add_hint(variables[u], side[u])
        if monotonic() >= deadline:
            return None, False
    model.minimize(sum(terms))
    remaining = deadline - monotonic()
    if remaining <= 0:
        return None, False
    solver = cp.CpSolver()
    solver.parameters.num_workers = 2
    solver.parameters.random_seed = seed
    solver.parameters.max_time_in_seconds = remaining
    status = solver.solve(model)
    if status not in (cp.OPTIMAL, cp.FEASIBLE):
        return None, False
    result = side.copy()
    for u in zone:
        result[u] = int(solver.value(variables[u]))
    return result, status == cp.OPTIMAL


def solve(graph, time_limit, deadline, use_complements, stats):
    fallback = greedy_balance(graph)
    best = fallback if graph.feasible(fallback) else None
    value = graph.cut(best) if best is not None else None
    seed_deadline = min(deadline, monotonic() + min(14, 0.24 * time_limit))
    for seed in kahip_seeds(graph, seed_deadline):
        stats["kahip_seeds"] += 1
        candidate = repair_seed(graph, seed)
        if candidate is not None and graph.feasible(candidate):
            stats["feasible_kahip_starts"] += 1
            cost = graph.cut(candidate)
            if value is None or cost < value:
                best, value = candidate, cost

    if monotonic() >= deadline:
        return best
    try:
        from ortools.sat.python import cp_model as cp
    except ImportError:
        return best

    if best is None:
        best = balanced_fallback(graph, fallback, cp, min(deadline, monotonic() + 8))
        if best is None or not graph.feasible(best):
            return None
        value = graph.cut(best)

    if not graph.edges:
        return best
    rng = random.Random(SEEDS[0])
    scores, boundary = boundary_ranking(graph, best)
    stalled = 0
    for iteration in range(48):
        remaining = deadline - monotonic()
        if remaining < 0.20:
            break
        zone = select_zone(graph, best, scores, boundary, ZONE_SIZES[iteration % len(ZONE_SIZES)], iteration, rng)
        added = 0
        if use_complements and stalled >= 2:
            zone, added = weight_complement_zone(graph, best, scores, boundary, zone)
        stats["boundary_rounds"] += 1
        stats["complement_rounds"] += bool(added)
        stats["complement_vertices"] += added
        seconds = min(4.0, remaining, max(0.25, time_limit / 18))
        improved, optimal = optimize_zone(
            graph, best, zone, cp, min(deadline, monotonic() + seconds), SEEDS[iteration % len(SEEDS)]
        )
        stalled += 1
        if improved is not None and graph.feasible(improved) and graph.load(improved) == graph.load(best):
            cost = graph.cut(improved)
            if cost < value:
                best, value = improved, cost
                scores, boundary = boundary_ranking(graph, best)
                stalled = 0
                stats["improving_rounds"] += 1
                stats["complement_improving_rounds"] += bool(added)
        if optimal and len(zone) == graph.count:
            break
    return best


def main():
    started = monotonic()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", choices=("armbruster2012",), required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=60)
    parser.add_argument("--weight-complements", action="store_true")
    args = parser.parse_args()
    if args.time_limit <= 0:
        parser.error("--time-limit must be positive")
    graph = Graph(json.loads(args.instance.read_bytes()))
    reserve = min(1.45, max(0.20, args.time_limit / 35))
    stats = dict.fromkeys(("kahip_seeds", "feasible_kahip_starts", "boundary_rounds", "improving_rounds",
                           "complement_rounds", "complement_vertices", "complement_improving_rounds"), 0)
    best = solve(graph, args.time_limit, started + args.time_limit - reserve, args.weight_complements, stats)
    if best is None or not graph.feasible(best):
        raise SystemExit("No verified capacity-feasible partition was found")
    root_group = best[0]
    solution = {
        "objective_value": graph.cut(best),
        "partition_S": [u for u, group in enumerate(best) if group == root_group],
        "partition_complement": [u for u, group in enumerate(best) if group != root_group],
    }
    args.output.write_text(json.dumps(solution, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")
    print(json.dumps(stats, sort_keys=True), file=sys.stderr)


if __name__ == "__main__":
    main()
