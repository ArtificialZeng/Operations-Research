"""
Cheap Source-Pairing vs Clean Target Signal Test on Official ODECE MDKP-Capacity.

Uses ONLY seed=11 (already used in SOURCE_INDEX_RECEIPT.json; NEVER touches reserved seeds 13-15).
Compares:
  (A) Upstream unsplit pairing (official_odece_repo/KnapsackCapaExp.py lines 64-75):
      train_test_split splits ONLY (X, w), then passes unsplit `capacity` and `costs`
      raw to train[0..899], val[0..99], test[0..499].
  (B) Clean joint-index pairing:
      all four arrays (X, w, capacity, costs) jointly split into disjoint 900/100/500.

Evaluates supervised X -> capacity predictive signal (closed-form OLS, Ridge, and Adam linear
regression matching LinearRegressionforKP_PredCapacity) without claiming impact on published
downstream DFL rankings.
"""
from __future__ import annotations

import json
import pathlib
import sys
import numpy as np
from sklearn.model_selection import train_test_split

BASE = pathlib.Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
sys.path.insert(0, str(BASE / "official_odece_repo"))
from OptProblems.knapsack.kpdata import genCapacity  # type: ignore


def fit_eval_linear_signal(X_tr: np.ndarray, y_tr: np.ndarray, X_te: np.ndarray, y_te: np.ndarray) -> dict:
    # 1. Exact OLS with intercept
    Xb_tr = np.hstack([X_tr, np.ones((len(X_tr), 1))])
    Xb_te = np.hstack([X_te, np.ones((len(X_te), 1))])
    B, _, _, _ = np.linalg.lstsq(Xb_tr, y_tr, rcond=None)
    pred_tr = Xb_tr @ B
    pred_te = Xb_te @ B

    # Constant-mean baseline (predict train mean)
    y_mean = y_tr.mean(axis=0, keepdims=True)
    mse_const_te = float(np.mean((y_te - y_mean) ** 2))
    mse_ols_tr = float(np.mean((y_tr - pred_tr) ** 2))
    mse_ols_te = float(np.mean((y_te - pred_te) ** 2))

    # Standard R^2 = 1 - SS_res / SS_tot (using test mean) and OOS R^2 vs train-mean baseline
    ss_tot_tr = float(np.sum((y_tr - y_tr.mean(axis=0, keepdims=True)) ** 2))
    ss_tot_te = float(np.sum((y_te - y_te.mean(axis=0, keepdims=True)) ** 2))
    r2_tr = 1.0 - float(np.sum((y_tr - pred_tr) ** 2)) / ss_tot_tr
    r2_te = 1.0 - float(np.sum((y_te - pred_te) ** 2)) / ss_tot_te
    oos_r2_vs_train_mean = 1.0 - mse_ols_te / mse_const_te

    # Per-dimension Pearson correlation on held-out test
    corrs = []
    for d in range(y_te.shape[1]):
        c = float(np.corrcoef(y_te[:, d], pred_te[:, d])[0, 1])
        corrs.append(c)

    # 2. Ridge (alpha=1.0, intercept unpenalized)
    n_f = X_tr.shape[1]
    reg_mat = np.eye(n_f + 1)
    reg_mat[-1, -1] = 0.0
    B_ridge = np.linalg.solve(Xb_tr.T @ Xb_tr + 1.0 * reg_mat, Xb_tr.T @ y_tr)
    pred_ridge_te = Xb_te @ B_ridge
    mse_ridge_te = float(np.mean((y_te - pred_ridge_te) ** 2))
    r2_ridge_te = 1.0 - float(np.sum((y_te - pred_ridge_te) ** 2)) / ss_tot_te

    return {
        "mse_const_train_mean_test": mse_const_te,
        "mse_ols_train": mse_ols_tr,
        "mse_ols_test": mse_ols_te,
        "r2_ols_train": r2_tr,
        "r2_ols_test": r2_te,
        "oos_r2_vs_train_mean": oos_r2_vs_train_mean,
        "test_pearson_r_per_dim": corrs,
        "test_pearson_r_mean": float(np.mean(corrs)),
        "mse_ridge1_test": mse_ridge_te,
        "r2_ridge1_test": r2_ridge_te,
    }


def main():
    seed = 11  # Already used in SOURCE_INDEX_RECEIPT.json; seeds 13-15 untouched
    # Exact KnapsackCapaExp.py defaults: num_items=100, num_data=1000, num_test=500, num_feat=10, dim=3, deg=4, noise_width=0.1
    # Also test deg=6, noise_width=0.25, num_items=50 matching MDKP-Weights regime
    configs = [
        {"label": "KnapsackCapaExp_default(items=100,deg=4,noise=0.1)", "num_items": 100, "deg": 4, "noise_width": 0.1},
        {"label": "MDKP_Weights_regime(items=50,deg=6,noise=0.25)", "num_items": 50, "deg": 6, "noise_width": 0.25},
    ]
    results = {
        "purpose": "Cheap supervised target-signal verification comparing upstream KnapsackCapaExp.py unsplit indexing vs clean joint indexing.",
        "seed": seed,
        "reserved_seeds_untouched": [13, 14, 15],
        "scope_note": "Measures supervised X -> capacity target signal ONLY. Does NOT claim impact on published downstream DFL rankings.",
        "upstream_reference": "official_odece_repo/KnapsackCapaExp.py lines 64-75 (commit 1b432e03)",
        "configs": [],
    }

    for cfg in configs:
        X, w, costs, capacity = genCapacity(
            num_data=1500,
            num_features=10,
            num_items=cfg["num_items"],
            dim=3,
            deg=cfg["deg"],
            noise_width=cfg["noise_width"],
            seed=seed,
        )
        # (A) EXACT upstream KnapsackCapaExp.py lines 69-75:
        #     train_test_split splits ONLY (X, w); knapsack_dataset indexes capacity[0..len-1]
        x_tr_u, x_te_u, _, _ = train_test_split(X, w, test_size=500, random_state=seed)
        x_tr_u, x_va_u, _, _ = train_test_split(x_tr_u, np.arange(len(x_tr_u)), test_size=0.1, random_state=seed)
        cap_tr_u = capacity[: len(x_tr_u)]  # 0..899
        cap_va_u = capacity[: len(x_va_u)]  # 0..99 (100% identical to train[0..99]!)
        cap_te_u = capacity[: len(x_te_u)]  # 0..499 (100% identical to train[0..499]!)

        # Track original row indices under upstream split to quantify exact misalignment
        idx_all = np.arange(1500)
        idx_tr_u, idx_te_u = train_test_split(idx_all, test_size=500, random_state=seed)
        idx_tr_u, idx_va_u = train_test_split(idx_tr_u, test_size=0.1, random_state=seed)
        mis_tr = int(np.sum(idx_tr_u != np.arange(len(idx_tr_u))))
        mis_va = int(np.sum(idx_va_u != np.arange(len(idx_va_u))))
        mis_te = int(np.sum(idx_te_u != np.arange(len(idx_te_u))))

        # (B) Clean joint-index split (using the exact same sklearn train_test_split indices!)
        x_tr_c, cap_tr_c = X[idx_tr_u], capacity[idx_tr_u]
        x_te_c, cap_te_c = X[idx_te_u], capacity[idx_te_u]

        sig_upstream = fit_eval_linear_signal(x_tr_u, cap_tr_u, x_te_u, cap_te_u)
        sig_clean = fit_eval_linear_signal(x_tr_c, cap_tr_c, x_te_c, cap_te_c)

        entry = {
            "config": cfg,
            "capacity_stats": {
                "shape": list(capacity.shape),
                "mean": float(capacity.mean()),
                "std": float(capacity.std()),
                "min": float(capacity.min()),
                "max": float(capacity.max()),
                "unique_rows_of_1500": int(len(np.unique(capacity, axis=0))),
            },
            "upstream_unsplit_alignment": {
                "train_misaligned_X_to_capacity": f"{mis_tr}/{len(idx_tr_u)}",
                "val_misaligned_X_to_capacity": f"{mis_va}/{len(idx_va_u)}",
                "test_misaligned_X_to_capacity": f"{mis_te}/{len(idx_te_u)}",
                "test_capacity_identical_to_train_prefix_0_499": bool(np.array_equal(cap_te_u, cap_tr_u[:500])),
                "val_capacity_identical_to_train_prefix_0_99": bool(np.array_equal(cap_va_u, cap_tr_u[:100])),
            },
            "upstream_unsplit_signal": sig_upstream,
            "clean_joint_split_signal": sig_clean,
        }
        results["configs"].append(entry)
        print(f"\n=== {cfg['label']} ===")
        print(f"  Upstream unsplit pairing : test R2={sig_upstream['r2_ols_test']:+.4f}, mean Pearson r={sig_upstream['test_pearson_r_mean']:+.4f}, OLS MSE={sig_upstream['mse_ols_test']:.4f} vs const-mean MSE={sig_upstream['mse_const_train_mean_test']:.4f}")
        print(f"  Clean joint-index pairing: test R2={sig_clean['r2_ols_test']:+.4f}, mean Pearson r={sig_clean['test_pearson_r_mean']:+.4f}, OLS MSE={sig_clean['mse_ols_test']:.4f} vs const-mean MSE={sig_clean['mse_const_train_mean_test']:.4f}")

    out_path = BASE / "MDKP_CAPACITY_SIGNAL_RECEIPT.json"
    out_path.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nSaved receipt to {out_path}")


if __name__ == "__main__":
    main()
