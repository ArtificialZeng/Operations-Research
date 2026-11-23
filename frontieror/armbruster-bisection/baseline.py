"""Time-limited KaHIP 3.30 multi-start baseline for FrontierOR Armbruster."""

import argparse
from contextlib import closing
from importlib.metadata import PackageNotFoundError, version
import json
from math import isfinite
from multiprocessing import get_context
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
from time import perf_counter


SEEDS = range(4096)
MODES = ("strong", "ultra", "eco", "fast")


def load_graph(path):
    instance = json.loads(path.read_text(encoding="utf-8"))
    nodes = instance["num_nodes"]
    weights = instance["node_weights"]
    total = sum(weights)
    capacity = instance["bisection_capacity_F"]
    if (
        type(nodes) is not int or nodes < 1 or len(weights) != nodes
        or any(type(weight) is not int or weight < 0 for weight in weights)
        or total != instance["total_node_weight"]
        or type(capacity) is not int or not (total + 1) // 2 <= capacity <= total
    ):
        raise ValueError("Invalid node weights or bisection capacity")

    edges = []
    for (u, v), cost in zip(instance["edges"], instance["edge_weights"], strict=True):
        if (
            type(u) is not int or type(v) is not int
            or not 0 <= u < nodes or not 0 <= v < nodes
            or type(cost) is not int or cost < 0
        ):
            raise ValueError("Expected valid endpoints and nonnegative integer edge costs")
        edges.append((u, v, cost))
    if len(edges) != instance["num_edges"]:
        raise ValueError("Edge count does not match the instance")
    return weights, capacity, edges


def csr(nodes, edges):
    adjacency = [{} for _ in range(nodes)]
    for u, v, cost in edges:
        if u != v and cost:
            adjacency[u][v] = adjacency[u].get(v, 0) + cost
            adjacency[v][u] = adjacency[v].get(u, 0) + cost
    offsets, costs, targets = [0], [], []
    for neighbors in adjacency:
        for target, cost in sorted(neighbors.items()):
            targets.append(target)
            costs.append(cost)
        offsets.append(len(targets))
    return offsets, costs, targets


def feasible_start(weights, capacity, deadline):
    """Get a weight-only incumbent, without inspecting edge costs."""
    order = sorted(range(len(weights)), key=weights.__getitem__, reverse=True)
    labels = bytearray(len(weights))
    loads = [0, 0]
    for node in order:
        side = int(loads[1] < loads[0])
        labels[node] = side
        loads[side] += weights[node]
    if max(loads) <= capacity:
        return bytes(labels)

    # Reserve a fallback for weighted graphs that defeat greedy bin filling.
    minimum = sum(weights) - capacity
    predecessors = {0: None}
    for node in order:
        weight = weights[node]
        additions = {}
        for step, previous in enumerate(predecessors):
            if step % 256 == 0 and perf_counter() >= deadline:
                return None
            load = previous + weight
            if load > capacity or load in predecessors:
                continue
            if load >= minimum:
                labels = bytearray(len(weights))
                labels[node] = 1
                while previous:
                    previous, member = predecessors[previous]
                    labels[member] = 1
                return bytes(labels)
            additions[load] = (previous, node)
        predecessors.update(additions)
    return None


def checked_solution(labels, weights, capacity, edges, reported=None):
    if len(labels) != len(weights) or set(labels) - {0, 1}:
        return None
    reference = labels[0]
    left = [node for node, side in enumerate(labels) if side == reference]
    right = [node for node, side in enumerate(labels) if side != reference]
    if max(sum(weights[node] for node in left), sum(weights[node] for node in right)) > capacity:
        return None
    cut = sum(cost for u, v, cost in edges if labels[u] != labels[v])
    if reported is not None and reported != cut:
        return None
    return {"objective_value": cut, "partition_S": left, "partition_complement": right}


def checkpoint(path, solution):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as pending:
            temporary = Path(pending.name)
            json.dump(solution, pending, separators=(",", ":"))
            pending.write("\n")
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def kahip_worker(connection, weights, capacity, graph):
    if sys.platform == "linux":
        import resource

        _, hard_limit = resource.getrlimit(resource.RLIMIT_CORE)
        resource.setrlimit(resource.RLIMIT_CORE, (0, hard_limit))

    import kahip

    offsets, costs, targets = graph
    # KaHIP normalizes the allowable load by ceil(total node weight / 2).
    half = (sum(weights) + 1) // 2
    imbalance = (capacity - half) / half if half else 0.0
    modes = {
        "strong": getattr(kahip, "STRONG", 2),
        "ultra": getattr(kahip, "ULTRA", None),
        "eco": getattr(kahip, "ECO", 1),
        "fast": getattr(kahip, "FAST", 0),
    }
    with connection:
        while True:
            try:
                seed, mode = connection.recv()
            except (EOFError, ConnectionError):
                return
            setting = modes[mode]
            result = None
            if setting is not None:
                cut, labels = kahip.kaffpa(
                    weights, offsets, costs, targets, 2, imbalance, True, seed, setting
                )
                result = cut, bytes(labels)
            try:
                connection.send(result)
            except ConnectionError:
                return


def start_worker(context, weights, capacity, graph):
    parent, child = context.Pipe()
    process = context.Process(target=kahip_worker, args=(child, weights, capacity, graph))
    try:
        process.start()
    except BaseException:
        parent.close()
        raise
    finally:
        child.close()
    return parent, process


def stop_worker(worker):
    connection, process = worker
    connection.close()
    process.join(timeout=0.05)
    if process.is_alive():
        process.terminate()
        process.join(timeout=0.25)
    if process.is_alive():
        process.kill()
        process.join(timeout=0.25)
    status = process.exitcode
    if status is not None:
        process.close()
    return status


def kahip_results(weights, capacity, graph, deadline):
    context = get_context("spawn")
    worker = None
    disabled_modes = set()
    recovering = False
    try:
        for seed in SEEDS:
            for mode in MODES:
                # Retain the original schedule on healthy runs. Add FAST after a failure.
                if mode in disabled_modes or (mode == "fast" and not recovering):
                    continue
                if perf_counter() >= deadline:
                    return
                if worker is None:
                    worker = start_worker(context, weights, capacity, graph)
                connection, _ = worker
                remaining = deadline - perf_counter()
                if remaining <= 0:
                    return
                wait = min(remaining, max(2.0, remaining / 2))
                try:
                    connection.send((seed, mode))
                    if connection.poll(wait):
                        result = connection.recv()
                    elif wait == remaining:
                        print(f"KaHIP {mode} seed={seed} reached the deadline", file=sys.stderr)
                        return
                    else:
                        raise TimeoutError(f"exceeded {wait:.2f}s call budget")
                except (EOFError, OSError) as error:
                    status = stop_worker(worker)
                    worker = None
                    disabled_modes.add(mode)
                    recovering = True
                    detail = f"{type(error).__name__} {error}".strip()
                    print(
                        f"KaHIP {mode} seed={seed} worker failed ({detail}, "
                        f"exit={status}); skipping {mode} for this run",
                        file=sys.stderr,
                    )
                    if len(disabled_modes) == len(MODES):
                        return
                    continue
                if result is None:
                    disabled_modes.add(mode)
                    print(f"KaHIP {mode} is unavailable in this build", file=sys.stderr)
                    continue
                cut, labels = result
                yield seed, mode, cut, labels
    finally:
        if worker is not None:
            stop_worker(worker)


def solve(instance_path, output, deadline):
    weights, capacity, edges = load_graph(instance_path)
    best = None
    initial = feasible_start(weights, capacity, deadline)
    if initial is not None:
        best = checked_solution(initial, weights, capacity, edges)
        checkpoint(output, best)
        if best["objective_value"] == 0:
            return
    if perf_counter() >= deadline:
        if best is None:
            raise RuntimeError("No feasible partition found within the time limit")
        return

    try:
        installed_version = version("kahip")
    except PackageNotFoundError:
        if best is None:
            raise RuntimeError("KaHIP is unavailable and no feasible partition was found") from None
        print("KaHIP is unavailable; using the weight-only fallback", file=sys.stderr)
        return
    print(f"KaHIP version={installed_version}", file=sys.stderr)
    graph = csr(len(weights), edges)
    attempts = 0
    best_source = "weight-only fallback"
    with closing(kahip_results(weights, capacity, graph, deadline)) as results:
        for seed, mode, cut, labels in results:
            attempts += 1
            if best is not None and cut >= best["objective_value"]:
                continue
            candidate = checked_solution(labels, weights, capacity, edges, cut)
            if candidate is not None:
                best = candidate
                best_source = f"{mode} seed={seed}"
                checkpoint(output, best)
                print(f"KaHIP {mode} seed={seed} cut={cut}", file=sys.stderr)
                if cut == 0:
                    break

    if best is None:
        raise RuntimeError("No feasible partition found within the time limit")
    print(
        f"KaHIP calls returned={attempts} final_cut={best['objective_value']} source={best_source}",
        file=sys.stderr,
    )


def main():
    started = perf_counter()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=60.0)
    args = parser.parse_args()
    if not isfinite(args.time_limit) or args.time_limit <= 0:
        parser.error("--time-limit must be a finite positive number")
    margin = min(2.0, args.time_limit / 5)
    solve(args.instance, args.output, started + args.time_limit - margin)


if __name__ == "__main__":
    main()
