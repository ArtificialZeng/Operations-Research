"""
Stage-2a Controlled Fixed-Clean-Target MDKP-Capacity Pairing Diagnostic
(`STAGE2A_CAPACITY_PAIRING_PROTOCOL.md`).

Published regime (official_odece_repo/MDKP_CapaExp.sh):
  num_items=50, dim=3, num_feat=10, deg=6, noise_width=0.25, seeds=[11, 12, 13, 14, 15],
  lr=0.005, batch_size=32, max_epochs=20.

Controlled intervention (0 MIP solves):
  - EXACT SAME clean test contexts X[idx_te], clean ground-truth capacity[idx_te],
    and shared constant-mean baseline capacity[idx_tr].mean(axis=0).
  - ONLY training labels change:
      CleanPair         : (X[idx_tr], capacity[idx_tr])
      MispairedUpstream : (X[idx_tr], capacity[:900])  [KnapsackCapaExp.py lines 69-73]
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
from typing import Dict, Tuple

import numpy as np
from scipy import stats
from sklearn.model_selection import train_test_split

BASE = pathlib.Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
sys.path.insert(0, str(BASE / "official_odece_repo"))
from OptProblems.knapsack.kpdata import genCapacity  # type: ignore

SEEDS = [11, 12, 13, 14, 15]


class LinearCapacityPredictor:
    """Exact numpy match to official_odece_repo/ML/TorchML.py LinearRegressionforKP_PredCapacity."""

    def __init__(self, num_feat: int = 10, dim: int = 3, seed: int = 11):
        rng = np.random.default_rng(seed)
        lim = math.sqrt(6.0 / (num_feat + dim))
        self.W = rng.uniform(-lim, lim, size=(num_feat, dim)).astype(np.float64)
        self.b = np.zeros(dim, dtype=np.float64)
        self.mW = np.zeros_like(self.W)
        self.vW = np.zeros_like(self.W)
        self.mb = np.zeros_like(self.b)
        self.vb = np.zeros_like(self.b)
        self.t = 0

    def forward(self, X: np.ndarray) -> np.ndarray:
        return X @ self.W + self.b[None, :]

    def step_adam(self, X: np.ndarray, d_out: np.ndarray, lr: float):
        gW = X.T @ d_out
        gb = np.sum(d_out, axis=0)
        self.t += 1
        b1, b2, eps = 0.9, 0.999, 1e-8
        self.mW = b1 * self.mW + (1.0 - b1) * gW
        self.vW = b2 * self.vW + (1.0 - b2) * (gW * gW)
        self.mb = b1 * self.mb + (1.0 - b1) * gb
        self.vb = b2 * self.vb + (1.0 - b2) * (gb * gb)
        mW_hat = self.mW / (1.0 - b1 ** self.t)
        vW_hat = self.vW / (1.0 - b2 ** self.t)
        mb_hat = self.mb / (1.0 - b1 ** self.t)
        vb_hat = self.vb / (1.0 - b2 ** self.t)
        self.W -= lr * mW_hat / (np.sqrt(vW_hat) + eps)
        self.b -= lr * mb_hat / (np.sqrt(vb_hat) + eps)


def train_adam_mse(
    X_tr: np.ndarray, y_tr: np.ndarray, lr: float = 0.005, epochs: int = 20, batch_size: int = 32, seed: int = 11
) -> LinearCapacityPredictor:
    model = LinearCapacityPredictor(num_feat=X_tr.shape[1], dim=y_tr.shape[1], seed=seed)
    rng = np.random.default_rng(seed + 1000)
    N = len(X_tr)
    for _ in range(epochs):
        order = rng.permutation(N)
        for s in range(0, N, batch_size):
            idx = order[s : s + batch_size]
            xb, yb = X_tr[idx], y_tr[idx]
            pred = model.forward(xb)
            d_out = (-2.0 * (yb - pred)) / float(pred.size)
            model.step_adam(xb, d_out, lr=lr)
    return model


def fit_ols(X_tr: np.ndarray, y_tr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    Xb = np.hstack([X_tr, np.ones((len(X_tr), 1))])
    B, _, _, _ = np.linalg.lstsq(Xb, y_tr, rcond=None)
    return B[:-1, :], B[-1, :]


def eval_on_fixed_clean_test(
    pred: np.ndarray, y_te_clean: np.ndarray, mse_shared_mean: float
) -> Tuple[Dict, np.ndarray]:
    se_per_inst = np.mean((pred - y_te_clean) ** 2, axis=1)  # (500,)
    ae_per_inst = np.mean(np.abs(pred - y_te_clean), axis=1)
    mse = float(np.mean(se_per_inst))
    mae = float(np.mean(ae_per_inst))
    ss_tot = float(np.sum((y_te_clean - y_te_clean.mean(axis=0, keepdims=True)) ** 2))
    r2_test = 1.0 - float(np.sum((pred - y_te_clean) ** 2)) / ss_tot
    oos_r2 = 1.0 - mse / mse_shared_mean
    corrs = [float(np.corrcoef(y_te_clean[:, d], pred[:, d])[0, 1]) for d in range(y_te_clean.shape[1])]
    return {
        "test_mse": mse,
        "test_mae": mae,
        "test_r2": r2_test,
        "oos_r2_vs_shared_mean": oos_r2,
        "pearson_r_per_dim": corrs,
        "pearson_r_mean": float(np.mean(corrs)),
    }, se_per_inst


def paired_se_stats(se_clean: np.ndarray, se_misp: np.ndarray, rng: np.random.Generator) -> Dict:
    diff = se_clean - se_misp  # negative = CleanPair has lower squared error
    n = len(diff)
    idx = rng.integers(0, n, size=(10000, n))
    boot = diff[idx].mean(axis=1)
    lo, hi = np.percentile(boot, [2.5, 97.5])
    _, p_wil = stats.wilcoxon(diff)
    return {
        "n_paired": n,
        "mean_se_diff_clean_minus_mispaired": float(diff.mean()),
        "ci95_low": float(lo),
        "ci95_high": float(hi),
        "wilcoxon_p": float(p_wil),
        "frac_instances_clean_better": float(np.mean(se_clean < se_misp)),
    }


def main():
    per_seed = []
    rng_boot = np.random.default_rng(20261124)

    print("=== Stage-2a Controlled Fixed-Clean-Target MDKP-Capacity Pairing Test (items=50, deg=6, noise=0.25) ===")
    for seed in SEEDS:
        X, w, costs, capacity = genCapacity(
            num_data=1500, num_features=10, num_items=50, dim=3, deg=6, noise_width=0.25, seed=seed
        )
        idx_all = np.arange(1500)
        idx_tr_full, idx_te = train_test_split(idx_all, test_size=500, random_state=seed)
        idx_tr, idx_va = train_test_split(idx_tr_full, test_size=0.1, random_state=seed)

        X_tr_clean = X[idx_tr]
        cap_tr_clean = capacity[idx_tr]
        cap_tr_misp = capacity[: len(idx_tr)]  # exact upstream KnapsackCapaExp.py:L73

        X_te_clean = X[idx_te]
        cap_te_clean = capacity[idx_te]

        # Shared constant-mean baseline from clean training split
        y_bar_shared = cap_tr_clean.mean(axis=0, keepdims=True)
        mse_shared_mean = float(np.mean((cap_te_clean - y_bar_shared) ** 2))
        mae_shared_mean = float(np.mean(np.abs(cap_te_clean - y_bar_shared)))
        # Also note mispaired train mean baseline for transparency
        y_bar_misp = cap_tr_misp.mean(axis=0, keepdims=True)
        mse_misp_mean = float(np.mean((cap_te_clean - y_bar_misp) ** 2))

        misaligned_train = int(np.sum(idx_tr != np.arange(len(idx_tr))))
        test_idx_in_0_899 = int(np.sum(idx_te < len(idx_tr)))

        # Predictor 1: Published Adam-MSE (lr=0.005, bs=32, epochs=20)
        m_adam_clean = train_adam_mse(X_tr_clean, cap_tr_clean, lr=0.005, epochs=20, batch_size=32, seed=seed)
        m_adam_misp = train_adam_mse(X_tr_clean, cap_tr_misp, lr=0.005, epochs=20, batch_size=32, seed=seed)
        adam_clean_res, se_ac = eval_on_fixed_clean_test(m_adam_clean.forward(X_te_clean), cap_te_clean, mse_shared_mean)
        adam_misp_res, se_am = eval_on_fixed_clean_test(m_adam_misp.forward(X_te_clean), cap_te_clean, mse_shared_mean)
        adam_pair = paired_se_stats(se_ac, se_am, rng_boot)

        # Predictor 2: Closed-form OLS
        W_oc, b_oc = fit_ols(X_tr_clean, cap_tr_clean)
        W_om, b_om = fit_ols(X_tr_clean, cap_tr_misp)
        ols_clean_res, se_oc = eval_on_fixed_clean_test(X_te_clean @ W_oc + b_oc[None, :], cap_te_clean, mse_shared_mean)
        ols_misp_res, se_om = eval_on_fixed_clean_test(X_te_clean @ W_om + b_om[None, :], cap_te_clean, mse_shared_mean)
        ols_pair = paired_se_stats(se_oc, se_om, rng_boot)

        row = {
            "seed": seed,
            "train_misaligned_count": f"{misaligned_train}/{len(idx_tr)}",
            "test_indices_falling_in_0_899": f"{test_idx_in_0_899}/{len(idx_te)}",
            "shared_mean_baseline": {
                "mse_on_clean_test": mse_shared_mean,
                "mae_on_clean_test": mae_shared_mean,
                "mispaired_train_mean_mse_on_clean_test": mse_misp_mean,
            },
            "adam_mse_published_lr0005_20ep": {
                "clean_trained": adam_clean_res,
                "mispaired_trained": adam_misp_res,
                "delta_oos_r2_clean_minus_mispaired": adam_clean_res["oos_r2_vs_shared_mean"] - adam_misp_res["oos_r2_vs_shared_mean"],
                "paired_se_clean_minus_mispaired": adam_pair,
            },
            "ols_closed_form": {
                "clean_trained": ols_clean_res,
                "mispaired_trained": ols_misp_res,
                "delta_oos_r2_clean_minus_mispaired": ols_clean_res["oos_r2_vs_shared_mean"] - ols_misp_res["oos_r2_vs_shared_mean"],
                "paired_se_clean_minus_mispaired": ols_pair,
            },
        }
        per_seed.append(row)
        print(
            f"  Seed {seed} (shared_mean MSE={mse_shared_mean:6.3f}) | "
            f"Adam-MSE: Clean MSE={adam_clean_res['test_mse']:6.3f} (OOS R2={adam_clean_res['oos_r2_vs_shared_mean']:+.4f}, r={adam_clean_res['pearson_r_mean']:+.3f}) "
            f"vs Misp MSE={adam_misp_res['test_mse']:6.3f} (OOS R2={adam_misp_res['oos_r2_vs_shared_mean']:+.4f}, r={adam_misp_res['pearson_r_mean']:+.3f}), p={adam_pair['wilcoxon_p']:.2e} | "
            f"OLS: Clean OOS R2={ols_clean_res['oos_r2_vs_shared_mean']:+.4f} vs Misp={ols_misp_res['oos_r2_vs_shared_mean']:+.4f} (p={ols_pair['wilcoxon_p']:.2e})"
        )

    def agg_stats(model_key: str) -> Dict:
        cm = np.array([r[model_key]["clean_trained"]["test_mse"] for r in per_seed])
        mm = np.array([r[model_key]["mispaired_trained"]["test_mse"] for r in per_seed])
        cr2 = np.array([r[model_key]["clean_trained"]["oos_r2_vs_shared_mean"] for r in per_seed])
        mr2 = np.array([r[model_key]["mispaired_trained"]["oos_r2_vs_shared_mean"] for r in per_seed])
        dr2 = cr2 - mr2
        cr = np.array([r[model_key]["clean_trained"]["pearson_r_mean"] for r in per_seed])
        mr = np.array([r[model_key]["mispaired_trained"]["pearson_r_mean"] for r in per_seed])
        pmax = float(max(r[model_key]["paired_se_clean_minus_mispaired"]["wilcoxon_p"] for r in per_seed))
        return {
            "clean_mse_mean_sd": [float(cm.mean()), float(cm.std(ddof=1))],
            "mispaired_mse_mean_sd": [float(mm.mean()), float(mm.std(ddof=1))],
            "clean_oos_r2_mean_sd": [float(cr2.mean()), float(cr2.std(ddof=1))],
            "mispaired_oos_r2_mean_sd": [float(mr2.mean()), float(mr2.std(ddof=1))],
            "delta_oos_r2_min_mean_max": [float(dr2.min()), float(dr2.mean()), float(dr2.max())],
            "clean_pearson_r_mean_sd": [float(cr.mean()), float(cr.std(ddof=1))],
            "mispaired_pearson_r_mean_sd": [float(mr.mean()), float(mr.std(ddof=1))],
            "clean_beats_mispaired_seeds": f"{int(np.sum(cm < mm))}/{len(per_seed)}",
            "max_per_seed_wilcoxon_p": pmax,
        }

    agg_adam = agg_stats("adam_mse_published_lr0005_20ep")
    agg_ols = agg_stats("ols_closed_form")
    gate_pass = bool(
        agg_adam["clean_beats_mispaired_seeds"] == "5/5"
        and agg_ols["clean_beats_mispaired_seeds"] == "5/5"
        and agg_adam["delta_oos_r2_min_mean_max"][0] >= 0.25
        and agg_ols["delta_oos_r2_min_mean_max"][0] >= 0.25
        and agg_adam["max_per_seed_wilcoxon_p"] < 1e-10
        and agg_ols["max_per_seed_wilcoxon_p"] < 1e-10
    )

    out = {
        "protocol": "STAGE2A_CAPACITY_PAIRING_PROTOCOL.md",
        "regime": "Published MDKP-Capacity (official_odece_repo/MDKP_CapaExp.sh: num_items=50, dim=3, num_feat=10, deg=6, noise_width=0.25, lr=0.005, bs=32, epochs=20)",
        "intervention_label": "Controlled training-label pairing intervention on IDENTICAL clean test contexts, ground truths, and shared constant-mean baseline. Does NOT claim impact on published method rankings.",
        "seeds": SEEDS,
        "gate_to_stage2b_pass": gate_pass,
        "aggregate_5seeds": {
            "adam_mse_published_lr0005_20ep": agg_adam,
            "ols_closed_form": agg_ols,
        },
        "per_seed": per_seed,
    }
    out_path = BASE / "stage2a_capacity_pairing_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(f"\n=== 5-Seed Summary (Stage-2b Gate Pass = {gate_pass}) ===")
    print(f"  Adam-MSE: Clean OOS R2 = {agg_adam['clean_oos_r2_mean_sd'][0]:+.4f} +/- {agg_adam['clean_oos_r2_mean_sd'][1]:.4f} vs Mispaired = {agg_adam['mispaired_oos_r2_mean_sd'][0]:+.4f} +/- {agg_adam['mispaired_oos_r2_mean_sd'][1]:.4f} (min delta = {agg_adam['delta_oos_r2_min_mean_max'][0]:+.4f}, max p = {agg_adam['max_per_seed_wilcoxon_p']:.2e})")
    print(f"  OLS     : Clean OOS R2 = {agg_ols['clean_oos_r2_mean_sd'][0]:+.4f} +/- {agg_ols['clean_oos_r2_mean_sd'][1]:.4f} vs Mispaired = {agg_ols['mispaired_oos_r2_mean_sd'][0]:+.4f} +/- {agg_ols['mispaired_oos_r2_mean_sd'][1]:.4f} (min delta = {agg_ols['delta_oos_r2_min_mean_max'][0]:+.4f}, max p = {agg_ols['max_per_seed_wilcoxon_p']:.2e})")
    print(f"Saved results to {out_path}")


if __name__ == "__main__":
    main()
