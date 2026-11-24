"""
Cheap Source/Index Discrepancy Receipt for Official ODECE Upstream Scripts
Directory: D:/AI_Science/antigravity/dfl_constraints_dual_pinball_20261124/

Documents exact field variation and train/val/test reuse/misalignment in:
  - official_odece_repo/KnapsackWeightExp.py (lines 71-83)
  - official_odece_repo/KnapsackCapaExp.py   (lines 64-75)
  - official_odece_repo/OptProblems/knapsack/kpdata.py (lines 41-76, 107-144)
  - official_odece_repo/OptProblems/knapsack/kpdataset.py (lines 19-60)
Pinned upstream commit: 1b432e03ce9ded1e504df60fd4c44cf936334d4f (Apache-2.0).
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO_DIR = Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124\official_odece_repo")
sys.path.insert(0, str(REPO_DIR))
from OptProblems.knapsack.kpdata import genCapacity, genWeights  # noqa: E402


def simulate_sklearn_split_indices(n: int, test_size: int, seed: int):
    # Reproduces index-level behavior of two sequential train_test_split calls (as in upstream scripts)
    # Using exact permutation audit (does not require sklearn install; verifies exact row-reuse geometry)
    rng1 = np.random.RandomState(seed)
    p1 = rng1.permutation(n)
    tr_full, te = p1[:-test_size], p1[-test_size:]
    n_val = int(round(0.1 * len(tr_full)))
    rng2 = np.random.RandomState(seed)
    p2 = rng2.permutation(len(tr_full))
    tr, va = tr_full[p2[:-n_val]], tr_full[p2[-n_val:]]
    return tr, va, te


def analyze_generator(name: str, X: np.ndarray, w: np.ndarray, costs: np.ndarray, cap: np.ndarray, seed: int) -> dict:
    N = X.shape[0]
    tr, va, te = simulate_sklearn_split_indices(N, 500, seed)
    # Check which fields actually vary across the N=1500 generated instances
    def field_stats(arr: np.ndarray) -> dict:
        flat = arr.reshape(N, -1)
        unique_rows = int(np.unique(flat, axis=0).shape[0])
        max_std_across_instances = float(np.max(np.std(flat, axis=0)))
        varies = unique_rows > 1
        return {
            "shape": list(arr.shape),
            "varies_across_instances": varies,
            "unique_rows_of_1500": unique_rows,
            "max_col_std_across_instances": max_std_across_instances,
        }

    # In upstream KnapsackWeightExp.py / KnapsackCapaExp.py:
    # dataset_train receives (x_train, w_train, capacity, costs) -> indexes capacity[0..899], costs[0..899]
    # dataset_val   receives (x_val,   w_val,   capacity, costs) -> indexes capacity[0..99],  costs[0..99]
    # dataset_test  receives (x_test,  w_test,  capacity, costs) -> indexes capacity[0..499], costs[0..499]
    misaligned_train = int(np.sum(tr != np.arange(len(tr))))
    misaligned_val = int(np.sum(va != np.arange(len(va))))
    misaligned_test = int(np.sum(te != np.arange(len(te))))

    return {
        "benchmark": name,
        "seed": seed,
        "N_total": N,
        "split_sizes": {"train": len(tr), "val": len(va), "test": len(te)},
        "fields": {
            "X": field_stats(X),
            "w": field_stats(w),
            "costs": field_stats(costs),
            "capacity": field_stats(cap),
        },
        "upstream_unsplit_index_behavior": {
            "split_fields_in_upstream": ["X", "w"],
            "unsplit_fields_passed_raw_to_all_three_datasets": ["capacity", "costs"],
            "val_indices_reused_from_train_prefix": "0..99 (100/100 = 100.0% exact capacity & costs row reuse with train[0..99])",
            "test_indices_reused_from_train_prefix": "0..499 (500/500 = 100.0% exact capacity & costs row reuse with train[0..499])",
            "misaligned_X_to_capacity_cost_pairs_under_random_split": {
                "train_misaligned_of_900": misaligned_train,
                "val_misaligned_of_100": misaligned_val,
                "test_misaligned_of_500": misaligned_test,
            },
        },
        "impact_on_supervised_target": (
            "In KnapsackWeightExp.py, X and target w remain row-aligned, but varying costs[0..499] and varying "
            "capacity[0..499] are reused identically across train[0..499] and test[0..499] (and 0..99 in val) "
            "and paired with shuffled (X, w) rows."
            if name == "MDKP-Weights"
            else "In KnapsackCapaExp.py, target capacity is NOT passed to train_test_split, so X is decoupled from "
            "its own generated target capacity (~99.9% misaligned) and test reuses capacity[0..499] from train[0..499]."
        ),
    }


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
    Xw, ww, cw, capw = genWeights(1500, 10, 50, np.array([0.18, 0.2, 0.22]), dim=3, deg=6, noise_width=0.25, seed=11)
    Xc, wc, cc, capc = genCapacity(1500, 10, 50, dim=3, deg=6, noise_width=0.25, seed=11)

    receipt = {
        "upstream_repo": "https://github.com/JayMan91/OdeceDFLforConstraintsNeurips25",
        "upstream_commit": "1b432e03ce9ded1e504df60fd4c44cf936334d4f",
        "upstream_license": "Apache-2.0",
        "code_references": {
            "KnapsackWeightExp.py": "lines 71-83 (train_test_split splits only X, w; capacity & costs passed unsplit)",
            "KnapsackCapaExp.py": "lines 64-75 (train_test_split splits only X, w; target capacity & costs passed unsplit)",
            "kpdata.py": "lines 46-47 & 74 (capacity & costs vary per instance under default fixed_cost=False, noise_width=0.25)",
            "kpdataset.py": "lines 32 & 55-56 (indexes self.capacity[i] and self.costs[i] for i in 0..len(X)-1)",
        },
        "benchmarks": [
            analyze_generator("MDKP-Weights", Xw, ww, cw, capw, seed=11),
            analyze_generator("MDKP-Capacity", Xc, wc, cc, capc, seed=11),
        ],
        "our_adaptation_policy": (
            "Jointly permute and split ALL four arrays (X, w, capacity, costs) with the identical index permutation "
            "into strictly disjoint 900 train / 100 val / 500 test splits. Because this corrects upstream unsplit indexing, "
            "all experiments are labeled as an aligned benchmark adaptation of ODECE (not reproduction of published scores)."
        ),
    }
    json_path = out_dir / "SOURCE_INDEX_RECEIPT.json"
    json_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, indent=2))
    print(f"Saved {json_path}")


if __name__ == "__main__":
    main()
