"""Convert the original SuiteSparse Delaware MATLAB file and certify feasibility."""

import argparse
import hashlib
import json
import platform
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy
from scipy.io import loadmat
from scipy.sparse import triu


EXPECTED_VERTICES = 24_115
EXPECTED_DIRECTED_EDGES = 116_056
EXPECTED_POPULATION = 897_934
ARCHIVE_RECORD = "https://sparse.tamu.edu/DIMACS10/de2010"
CENSUS_TOTAL = (
    "https://www2.census.gov/programs-surveys/decennial/tables/2010/"
    "2010-apportionment/apport2010-table2.pdf"
)


def file_record(path):
    return {"file": path.name, "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def integer_values(values, minimum, label):
    if not (np.isfinite(values).all() and (values >= minimum).all()
            and (values == np.floor(values)).all()):
        raise ValueError(f"{label} contains a noninteger or out-of-range value")
    return [int(value) for value in values]


def convert(mat_path):
    problem = loadmat(mat_path, simplify_cells=True)["Problem"]
    if problem["name"] != "DIMACS10/de2010" or int(problem["id"]) != 2589:
        raise ValueError("Unexpected SuiteSparse matrix identity")
    adjacency = problem["A"].tocsr()
    if adjacency.shape != (EXPECTED_VERTICES, EXPECTED_VERTICES):
        raise ValueError("Unexpected matrix dimensions")
    if not adjacency.has_canonical_format or adjacency.nnz != EXPECTED_DIRECTED_EDGES:
        raise ValueError("Unexpected edge count or repeated sparse entries")
    if np.any(adjacency.diagonal()) or (adjacency != adjacency.T).nnz:
        raise ValueError("Expected an exactly symmetric matrix without self-loops")
    upper = triu(adjacency, k=1, format="csr").tocoo()
    if upper.nnz * 2 != adjacency.nnz:
        raise ValueError("Unexpected edge count after removing reverse storage")
    weights = integer_values(np.asarray(problem["aux"]["population"]).reshape(-1), 0, "POP100")
    total = sum(weights)
    if len(weights) != EXPECTED_VERTICES or total != EXPECTED_POPULATION or total % 2:
        raise ValueError(f"Unexpected population or parity: {total}")
    return {
        "num_nodes": EXPECTED_VERTICES,
        "num_edges": upper.nnz,
        "bisection_capacity_F": total // 2,
        "total_node_weight": total,
        "node_weights": weights,
        "edges": [[int(row), int(col)] for row, col in zip(upper.row, upper.col, strict=True)],
        "edge_weights": integer_values(upper.data, 1, "Rook boundary weights"),
    }


def feasible_partition(instance):
    """Use subset-sum reachability and blockwise reconstruction, with vertex 0 fixed."""
    weights = instance["node_weights"]
    capacity = instance["bisection_capacity_F"]
    target = capacity - weights[0]
    mask = (1 << (target + 1)) - 1
    candidates = [(index, weight) for index, weight in enumerate(weights) if index and weight]
    block_size = 128
    reachable = 1
    snapshots = []
    for start in range(0, len(candidates), block_size):
        block = candidates[start:start + block_size]
        snapshots.append((reachable, block))
        for _, weight in block:
            reachable = (reachable | (reachable << weight)) & mask
        if (reachable >> target) & 1:
            break
    else:
        raise ValueError("No feasible exact-weight partition contains vertex 0")

    selected = {0}
    remaining = target
    for earlier, block in reversed(snapshots):
        if (earlier >> remaining) & 1:
            continue
        states = [earlier]
        for _, weight in block:
            states.append((states[-1] | (states[-1] << weight)) & mask)
        for (node, weight), before in zip(reversed(block), reversed(states[:-1]), strict=True):
            if not ((before >> remaining) & 1):
                selected.add(node)
                remaining -= weight

    complement = [node for node in range(len(weights)) if node not in selected]
    if (remaining or sum(weights[node] for node in selected) != capacity
            or sum(weights[node] for node in complement) != capacity):
        raise ValueError("Reconstructed witness failed integer verification")
    cut = sum(weight for (a, b), weight in zip(instance["edges"], instance["edge_weights"], strict=True)
              if (a in selected) != (b in selected))
    return {"partition_S": sorted(selected), "partition_complement": complement, "objective_value": cut}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mat", type=Path)
    parser.add_argument("--source-url", required=True)
    args = parser.parse_args()
    instance = convert(args.mat)
    proof = feasible_partition(instance)
    output = args.mat.with_suffix(".json")
    witness = args.mat.with_name("de2010_feasibility.json")
    for path, data in ((output, instance), (witness, proof)):
        path.write_text(json.dumps(data, separators=(",", ":")) + "\n", encoding="utf-8")

    manifest = {
        "matrix": "DIMACS10/de2010",
        "archive_matrix_id": 2589,
        "archive_record": ARCHIVE_RECORD,
        "download_url": args.source_url,
        "population_reference": CENSUS_TOTAL,
        "converted_utc": datetime.now(timezone.utc).isoformat(),
        "python": platform.python_version(),
        "scipy": scipy.__version__,
        "numpy": np.__version__,
        "artifacts": [file_record(path) for path in (args.mat, output, witness, Path(__file__))],
        "statistics": {key: instance[key] for key in (
            "num_nodes", "num_edges", "total_node_weight", "bisection_capacity_F")},
        "zero_population_vertices": instance["node_weights"].count(0),
        "edge_weight_range": [min(instance["edge_weights"]), max(instance["edge_weights"])],
        "input_semantics": "0-based MATLAB row order, original POP100 and positive integer upper triangle of A",
        "feasibility": {
            "method": "integer subset-sum bitset independent of the edge objective",
            "partition_S_contains_node_0": proof["partition_S"][0] == 0,
            "side_weights": [instance["bisection_capacity_F"]] * 2,
            "witness_role": "Feasibility certificate only. Exclude from candidate inputs and warm starts.",
        },
    }
    args.mat.with_name("manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
