"""Run the frozen, near-tight CAP101 recourse falsification."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.request import urlopen

from probe import ARCHIVE_HASH, UNITS, URL, HighsTransport, batch, np, ordinary, read_cap, sample


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--archive", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.archive:
        raw = args.archive.read_bytes()
    else:
        with urlopen(URL, timeout=10) as reply:
            raw = reply.read()
    capacity, _, nominal, costs, scale = read_cap(raw)
    original = sample(nominal)
    peak = int(original.sum(axis=1).max())
    layout = [0, 10]
    cap = capacity[layout] * UNITS
    selected_costs = [costs[i] for i in layout]
    total = int(cap.sum())
    numerator, denominator = 100 * total, 105 * peak
    stressed = (original * numerator + denominator // 2) // denominator
    stressed_peak = int(stressed.sum(axis=1).max())
    if not 1.01 <= total / stressed_peak <= 1.10:
        raise ValueError("Stressed scenarios are outside the frozen headroom interval")

    import highspy

    highs_version = highspy.Highs().version()
    order = np.argsort(stressed.sum(axis=1), kind="stable")
    deadline = perf_counter() + 20.0
    records = []
    for repeat in range(3):
        if repeat % 2:
            certified, tree_metrics = batch(cap, selected_costs, scale, stressed, order, deadline)
            sequential, ordinary_metrics = ordinary(HighsTransport, cap, selected_costs, scale, stressed, order, deadline)
        else:
            sequential, ordinary_metrics = ordinary(HighsTransport, cap, selected_costs, scale, stressed, order, deadline)
            certified, tree_metrics = batch(cap, selected_costs, scale, stressed, order, deadline)
        error = np.abs(sequential - certified)
        if np.any(error > np.maximum(1e-6, 1e-9 * np.abs(sequential))):
            raise ArithmeticError("Disagreement in original recourse cost")
        records.append({"repeat": repeat + 1, "first_arm": "batch" if repeat % 2 else "highs",
                        "tree_batch": tree_metrics, "highs_sequential": ordinary_metrics,
                        "max_abs_cost_error": float(error.max())})
    batch_wall = median(row["tree_batch"]["wall_s"] for row in records)
    highs_wall = median(row["highs_sequential"]["wall_s"] for row in records)
    result = {"source": URL, "source_sha256": ARCHIVE_HASH, "highs": highs_version,
              "scenario_sha256": sha256(stressed.astype("<i8").tobytes()).hexdigest(),
              "count": len(stressed), "original_peak_milliunits": peak,
              "original_one_facility_milliunits": int(cap[0]), "open_zero_based": layout,
              "open_capacity_milliunits": total, "original_capacity_to_peak": total / peak,
              "stressed_peak_milliunits": stressed_peak, "capacity_to_peak": total / stressed_peak,
              "demand_multiplier": [numerator, denominator], "runs": records,
              "batch_median_wall_s": batch_wall, "highs_median_wall_s": highs_wall,
              "wall_speedup": highs_wall / batch_wall}
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
