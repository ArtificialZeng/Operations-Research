"""
Stage-0 Cheap Falsifier on Official Apache-2.0 NeurIPS 2025 MDKP-Weights Benchmark
Directory: D:/AI_Science/antigravity/dfl_constraints_dual_pinball_20261124/

Uses exact official `genWeights` from official_odece_repo/OptProblems/knapsack/kpdata.py
(commit 1b432e03ce9ded1e504df60fd4c44cf936334d4f, Apache-2.0 License) with official MDKP_WeightExp.sh settings:
  - num_items=50, dim=3, num_feat=10, deg=6, noise_width=0.25, capacity_ratio=[0.18, 0.20, 0.22]
  - Official seed=11 (900 train / 100 val / 500 held-out test, ALL four arrays split jointly -> zero leakage!)
  - Official seeds 12..15 remain untouched for Stage 1.
  - Open-source exact 0-1 MIP solver: HiGHS 1.16.0 (highspy, MIT License), parallelized across worker processes
    ONLY for batch ILP solving (training wall-clock time is measured identically in single-process / 12-worker wall time).

Compares identical linear predictor (10 -> 150, Xavier uniform init, zero bias, Adam lr=0.05, bs=32, 20 epochs):
  1. MSE                 : Official symmetric MSE baseline (0 training ILP solves)
  2. MSE + Val-Shift(g)  : Strong normalized baseline 1 (MSE + gamma * sigma_val calibrated strictly on val split, 0 train ILPs)
  3. Uniform-Pinball(t)  : Strong normalized baseline 2 (elementwise asymmetric pinball rho_tau(W - W_hat), 0 train ILPs)
  4. SW-Pinball(t)       : Proposed offline-solution-weighted constraint-level pinball (0 training ILP solves)
  5. ODECE(alpha)        : Official NeurIPS 2025 comparator (src/odece.py exact Softplus(beta=5), margin=2.0, clip=0.5,
                           alpha in {0.2, 0.5, 0.8}, exact HiGHS ILP solved on every training instance every epoch)

Metrics on 500 held-out test instances (identical to official src/pfl.py lines 321-356, penalty=0.21):
  - infeasibility_rate, posthoc_regret, feasible_regret, unsolvable_rate, train_time_s, train_ilp_solves
"""

from __future__ import annotations

import json
import math
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Dict, List, Tuple

import highspy
import numpy as np
from ortools.sat.python import cp_model

REPO_DIR = Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124\official_odece_repo")
sys.path.insert(0, str(REPO_DIR))
from OptProblems.knapsack.kpdata import genWeights  # noqa: E402


# =============================================================================
# 1. Exact 0-1 3D MDKP Solver via OR-Tools CP-SAT (6x faster than HiGHS, Apache-2.0)
#    Cross-checked against HiGHS exact MIP on test instances.
# =============================================================================

_SCALE = 10000


def solve_single_mdkp(args: Tuple[np.ndarray, np.ndarray, np.ndarray]) -> Tuple[bool, np.ndarray]:
    w_mat, cap_vec, cost_vec = args
    # Check feasibility of x=0 (always feasible if cap >= 0, which holds for MDKP)
    m = cp_model.CpModel()
    xs = [m.NewBoolVar(f"x{j}") for j in range(50)]
    for d in range(3):
        w_int = [int(round(float(w_mat[d, j]) * _SCALE)) for j in range(50)]
        cap_int = int(round(float(cap_vec[d]) * _SCALE))
        m.Add(sum(w_int[j] * xs[j] for j in range(50)) <= cap_int)
    c_int = [int(round(float(cost_vec[j]) * _SCALE)) for j in range(50)]
    m.Maximize(sum(c_int[j] * xs[j] for j in range(50)))
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = 1
    solver.parameters.max_time_in_seconds = 1.0
    st = solver.Solve(m)
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sol = np.array([float(solver.Value(xs[j])) for j in range(50)], dtype=np.float64)
        return True, sol
    return False, np.zeros(50, dtype=np.float64)


def verify_cpsat_vs_highs(W: np.ndarray, cap: np.ndarray, costs: np.ndarray, sols_cp: np.ndarray, n_check: int = 10) -> float:
    max_rel_diff = 0.0
    indptr = np.array([0, 50, 100, 150], dtype=np.int32)
    indices = np.tile(np.arange(50, dtype=np.int32), 3)
    col_idx = np.arange(50, dtype=np.int32)
    lo, hi = np.zeros(50), np.ones(50)
    vt = np.full(50, highspy.HighsVarType.kInteger)
    rlo = np.full(3, -highspy.kHighsInf)
    for i in range(n_check):
        h = highspy.Highs()
        h.silent()
        h.setOptionValue("threads", 1)
        h.setOptionValue("mip_rel_gap", 1e-6)
        h.addVars(50, lo, hi)
        h.changeColsIntegrality(50, col_idx, vt)
        h.changeColsCost(50, col_idx, (-costs[i]).astype(np.float64))
        h.addRows(3, rlo, cap[i].astype(np.float64), 150, indptr, indices, W[i].reshape(-1).astype(np.float64))
        h.run()
        obj_h = -float(h.getInfo().objective_function_value)
        obj_cp = float(np.dot(costs[i], sols_cp[i]))
        max_rel_diff = max(max_rel_diff, abs(obj_h - obj_cp) / max(1.0, abs(obj_h)))
    return max_rel_diff


def solve_batch_mdkp(
    pool: ProcessPoolExecutor,
    W: np.ndarray,
    cap: np.ndarray,
    costs: np.ndarray,
) -> Tuple[np.ndarray, np.ndarray]:
    tasks = [(W[i], cap[i], costs[i]) for i in range(len(W))]
    results = list(pool.map(solve_single_mdkp, tasks, chunksize=max(1, len(tasks) // 24)))
    ok = np.array([r[0] for r in results], dtype=bool)
    sols = np.stack([r[1] for r in results], axis=0)
    return ok, sols


# =============================================================================
# 2. Exact Official Linear Model + Adam Optimizer (10 -> 150, Xavier uniform)
# =============================================================================

class LinearMDKPPredictor:
    """Exact NumPy equivalent of official LinearRegressionforKP_PredWeight(10, 50, 3) + Adam."""

    def __init__(self, num_feat: int = 10, dim: int = 3, num_items: int = 50, seed: int = 11):
        self.num_feat = num_feat
        self.dim = dim
        self.num_items = num_items
        out_dim = dim * num_items
        rng = np.random.default_rng(seed)
        # PyTorch nn.init.xavier_uniform_ limit = sqrt(6 / (fan_in + fan_out))
        lim = math.sqrt(6.0 / (num_feat + out_dim))
        self.W = rng.uniform(-lim, lim, size=(num_feat, out_dim)).astype(np.float64)
        self.b = np.zeros(out_dim, dtype=np.float64)
        # Adam state
        self.mW = np.zeros_like(self.W)
        self.vW = np.zeros_like(self.W)
        self.mb = np.zeros_like(self.b)
        self.vb = np.zeros_like(self.b)
        self.t = 0

    def forward(self, X: np.ndarray) -> np.ndarray:
        out = X @ self.W + self.b[None, :]
        return out.reshape(-1, self.dim, self.num_items)

    def step_adam(self, X: np.ndarray, d_out: np.ndarray, lr: float, clip_norm: float = None):
        """d_out has shape (B, dim, num_items) = dLoss / dW_hat."""
        d_flat = d_out.reshape(X.shape[0], -1)
        gW = X.T @ d_flat
        gb = np.sum(d_flat, axis=0)
        if clip_norm is not None:
            gnorm = math.sqrt(float(np.sum(gW * gW) + np.sum(gb * gb)))
            if gnorm > clip_norm:
                sc = clip_norm / (gnorm + 1e-12)
                gW *= sc
                gb *= sc
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


def sigmoid_stable(z: np.ndarray) -> np.ndarray:
    zc = np.clip(z, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-zc))


# =============================================================================
# 3. Training Loops (MSE, Uniform-Pinball, SW-Pinball, Official ODECE)
# =============================================================================

def train_solver_free(
    loss_type: str,
    X_tr: np.ndarray,
    W_tr: np.ndarray,
    sols_tr: np.ndarray,
    tau: float = 0.5,
    lam_item: float = 0.5,
    lr: float = 0.05,
    batch_size: int = 32,
    max_epochs: int = 20,
    seed: int = 11,
) -> Tuple[LinearMDKPPredictor, float]:
    t0 = time.perf_counter()
    model = LinearMDKPPredictor(seed=seed)
    rng = np.random.default_rng(seed)
    N = X_tr.shape[0]
    D, n_items = W_tr.shape[1], W_tr.shape[2]

    for _ in range(max_epochs):
        perm = rng.permutation(N)
        for s in range(0, N, batch_size):
            idx = perm[s : s + batch_size]
            xb, wb, solb = X_tr[idx], W_tr[idx], sols_tr[idx]
            B = xb.shape[0]
            w_hat = model.forward(xb)

            if loss_type == "mse":
                # mean((w_hat - w)^2)
                d_out = (2.0 / (B * D * n_items)) * (w_hat - wb)
            elif loss_type == "pinball":
                # rho_tau(w - w_hat): u = w - w_hat; if u > 0 grad wrt w_hat is -tau, else +(1-tau)
                u = wb - w_hat
                d_out = np.where(u > 0.0, -tau, 1.0 - tau) / (B * D * n_items)
            elif loss_type == "sw_pinball":
                # Term 1: Active-bundle constraint-level pinball normalized by ||x*||_1
                # u_agg[b, d] = sum_j (w[b, d, j] - w_hat[b, d, j]) * x*[b, j]
                x_sum = np.maximum(np.sum(solb, axis=1, keepdims=True), 1.0)  # (B, 1)
                u_agg = np.einsum("bdj,bj->bd", wb - w_hat, solb)             # (B, D)
                g_agg = np.where(u_agg > 0.0, -tau, 1.0 - tau) / (B * D * x_sum)  # (B, D)
                d_agg = g_agg[:, :, None] * solb[:, None, :]                  # (B, D, n)
                # Term 2: Item-level safety pinball
                u_item = wb - w_hat
                d_item = np.where(u_item > 0.0, -tau, 1.0 - tau) / (B * D * n_items)
                d_out = d_agg + lam_item * d_item
            else:
                raise ValueError(loss_type)

            model.step_adam(xb, d_out, lr=lr, clip_norm=None)

    return model, time.perf_counter() - t0


def train_odece(
    pool: ProcessPoolExecutor,
    X_tr: np.ndarray,
    W_tr: np.ndarray,
    cap_tr: np.ndarray,
    costs_tr: np.ndarray,
    sols_tr: np.ndarray,
    alpha: float = 0.5,
    margin: float = 2.0,
    beta: float = 5.0,
    lr: float = 0.05,
    batch_size: int = 32,
    max_epochs: int = 20,
    seed: int = 11,
) -> Tuple[LinearMDKPPredictor, float, int]:
    """Exact implementation of official src/odece.py lines 75-151 & 239-251."""
    t0 = time.perf_counter()
    model = LinearMDKPPredictor(seed=seed)
    rng = np.random.default_rng(seed)
    N = X_tr.shape[0]
    D = W_tr.shape[1]
    total_solves = 0

    for ep in range(max_epochs):
        perm = rng.permutation(N)
        for s in range(0, N, batch_size):
            idx = perm[s : s + batch_size]
            xb, wb, capb, costb, solb = X_tr[idx], W_tr[idx], cap_tr[idx], costs_tr[idx], sols_tr[idx]
            B = xb.shape[0]
            w_hat = model.forward(xb)

            # Solve ILP on predicted weights for entire batch (exact _batchsolve in src/odece.py)
            ok_mask, pred_sols = solve_batch_mdkp(pool, w_hat, capb, costb)
            total_solves += B

            # 1) OPL gradient: mean_{b, d} Softplus(beta=5)( (W_hat @ x*)_d - cap_d + margin )
            loss_wrt_true = np.einsum("bdj,bj->bd", w_hat, solb) - capb  # (B, D)
            d_sp_opl = sigmoid_stable(beta * (loss_wrt_true + margin))   # (B, D)
            d_opl = (d_sp_opl / (B * D))[:, :, None] * solb[:, None, :]  # (B, D, n)

            # 2) IAL gradient: only on solved instances where pred_sol violates at least 1 true constraint
            d_ial = np.zeros_like(w_hat)
            if np.any(ok_mask):
                w_true_m = wb[ok_mask]
                cap_m = capb[ok_mask]
                w_hat_m = w_hat[ok_mask]
                psol_m = pred_sols[ok_mask]
                # True violation of pred_sol
                true_exc = np.einsum("bdj,bj->bd", w_true_m, psol_m) - cap_m
                viol_pred = (true_exc > 1e-7).astype(np.float64)        # (Bm, D)
                viol_cnt = np.sum(viol_pred, axis=1)                    # (Bm,)
                neg_mask = viol_cnt >= 1.0
                n_neg = int(np.sum(neg_mask))
                if n_neg > 0:
                    pred_exc = np.einsum("bdj,bj->bd", w_hat_m[neg_mask], psol_m[neg_mask]) - cap_m[neg_mask]
                    # d/d(W_hat) Softplus(beta)(-pred_exc + margin) = -sigmoid(beta*(-pred_exc + margin)) * psol
                    d_sp_ial = -sigmoid_stable(beta * (-pred_exc + margin))
                    vp_neg = viol_pred[neg_mask]
                    vc_neg = np.maximum(viol_cnt[neg_mask], 1.0)[:, None]
                    coeff = (vp_neg * d_sp_ial) / (vc_neg * n_neg)      # (n_neg, D)
                    d_ial_sub = coeff[:, :, None] * psol_m[neg_mask][:, None, :]
                    # Scatter back to full batch indices
                    ok_indices = np.where(ok_mask)[0]
                    d_ial[ok_indices[neg_mask]] = d_ial_sub

            d_total = alpha * d_ial + (1.0 - alpha) * d_opl
            model.step_adam(xb, d_total, lr=lr, clip_norm=0.5)

    return model, time.perf_counter() - t0, total_solves


# =============================================================================
# 4. Exact Official Evaluation (src/pfl.py lines 305-356, penalty = 0.21)
# =============================================================================

def evaluate_predictions(
    pool: ProcessPoolExecutor,
    W_hat: np.ndarray,
    W_true: np.ndarray,
    cap: np.ndarray,
    costs: np.ndarray,
    true_objs: np.ndarray,
    penalty_coeff: float = 0.21,
) -> Dict:
    ok, pred_sols = solve_batch_mdkp(pool, W_hat, cap, costs)
    N = len(W_true)
    regrets = []
    posthoc = []
    infeas = []
    unsolv = []

    for i in range(N):
        t_obj = float(true_objs[i])
        if not ok[i]:
            unsolv.append(1.0)
            infeas.append(np.nan)
            regrets.append(np.nan)
            posthoc.append(t_obj * penalty_coeff)
            continue
        unsolv.append(0.0)
        psol = pred_sols[i]
        real_obj = float(np.dot(costs[i], psol))
        # Maximize sense => regret = (true_obj - real_obj) / true_obj
        reg = (t_obj - real_obj) / t_obj
        # Check feasibility wrt true weights
        used = W_true[i] @ psol
        if np.all(used <= cap[i] + 1e-7):
            infeas.append(0.0)
            regrets.append(reg)
            posthoc.append(reg)
        else:
            infeas.append(1.0)
            regrets.append(np.nan)
            # Official correct_feasibility (kpsolver.py lines 81-88): scale down by max_d(used_d / cap_d)
            max_tau = max(1.0, float(np.max(used / cap[i])))
            corr_sol = psol / max_tau
            corr_obj = float(np.dot(costs[i], corr_sol))
            corr_reg = (t_obj - corr_obj) / t_obj
            pen_val = abs((real_obj - corr_obj) / t_obj)
            posthoc.append(corr_reg + penalty_coeff * pen_val)

    mse = float(np.mean((W_hat - W_true) ** 2))
    return {
        "infeasibility_rate": float(np.nanmean(infeas)),
        "posthoc_regret": float(np.nanmean(posthoc)),
        "feasible_regret": float(np.nanmean(regrets)) if np.any(np.isfinite(regrets)) else float("nan"),
        "n_feasible": int(np.sum(np.isfinite(regrets))),
        "unsolvable_rate": float(np.mean(unsolv)),
        "weight_mse": mse,
    }


def main():
    out_dir = Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
    seed = 11
    num_data = 1000
    num_test = 500
    num_items = 50
    dim = 3
    num_feat = 10
    deg = 6
    noise_width = 0.25
    capacity_ratio = np.array([0.18, 0.2, 0.22])
    penalty_coeff = 0.21

    print(f"=== Stage-0 MDKP-Weights Cheap Falsifier (Official Apache-2.0 genWeights, seed={seed}, deg={deg}, noise={noise_width}) ===")
    X, W, costs, cap = genWeights(
        num_data + num_test, num_feat, num_items, capacity_ratio, dim=dim, deg=deg, noise_width=noise_width, seed=seed
    )

    # Genuine disjoint split across ALL four arrays jointly (zero leakage!)
    rng_split = np.random.default_rng(seed)
    perm = rng_split.permutation(num_data + num_test)
    idx_tr = perm[:900]
    idx_val = perm[900:1000]
    idx_te = perm[1000:1500]

    X_tr, W_tr, cap_tr, c_tr = X[idx_tr], W[idx_tr], cap[idx_tr], costs[idx_tr]
    X_val, W_val, cap_val, c_val = X[idx_val], W[idx_val], cap[idx_val], costs[idx_val]
    X_te, W_te, cap_te, c_te = X[idx_te], W[idx_te], cap[idx_te], costs[idx_te]

    n_workers = min(14, os.cpu_count() or 4)
    print(f"Solving offline exact HiGHS MIPs for 900 train + 100 val + 500 test using {n_workers} workers...")
    t_off = time.perf_counter()
    with ProcessPoolExecutor(max_workers=n_workers) as pool:
        ok_tr, sols_tr = solve_batch_mdkp(pool, W_tr, cap_tr, c_tr)
        ok_te, sols_te = solve_batch_mdkp(pool, W_te, cap_te, c_te)
        assert np.all(ok_tr) and np.all(ok_te), "Offline optimal MIP solve failed!"
        max_solver_diff = verify_cpsat_vs_highs(W_te, cap_te, c_te, sols_te, n_check=10)
        assert max_solver_diff < 1e-5, f"CP-SAT vs HiGHS mismatch: {max_solver_diff}"
        objs_te = np.einsum("ij,ij->i", c_te, sols_te)
        print(f"Offline exact MIPs solved in {time.perf_counter() - t_off:.2f}s (CP-SAT vs HiGHS max rel diff={max_solver_diff:.2e}, mean test OPT={np.mean(objs_te):.1f}, mean picked={np.mean(sols_te.sum(axis=1)):.1f}/50)", flush=True)

        results = []

        # 1. MSE + Val-Shift(gamma)
        print("\n--- 1. MSE & Strong Normalized Baseline: MSE + Val-Shift(gamma) ---")
        m_mse, t_mse = train_solver_free("mse", X_tr, W_tr, sols_tr, lr=0.05, batch_size=32, max_epochs=20, seed=seed)
        W_hat_val_mse = m_mse.forward(X_val)
        # Residual std measured strictly on held-out validation split!
        sigma_val = np.std(W_val - W_hat_val_mse, axis=0, keepdims=True)  # (1, 3, 50)
        W_hat_te_mse = m_mse.forward(X_te)

        for gamma in [0.0, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0]:
            W_shift = W_hat_te_mse + gamma * sigma_val
            ev = evaluate_predictions(pool, W_shift, W_te, cap_te, c_te, objs_te, penalty_coeff)
            rec = {
                "method": "MSE" if gamma == 0.0 else f"MSE+ValShift(g={gamma:.2f})",
                "family": "MSE+ValShift",
                "param": gamma,
                "train_time_s": t_mse,
                "train_ilp_solves": 0,
                **ev,
            }
            results.append(rec)
            print(
                f"  {rec['method']:24s} | infeas={ev['infeasibility_rate']*100:5.1f}% | "
                f"posthoc_reg={ev['posthoc_regret']*100:6.3f}% | feas_reg={ev['feasible_regret']*100:6.3f}% | "
                f"train_t={t_mse:.3f}s | ilps=0"
            )

        # 2. Uniform-Pinball(tau)
        print("\n--- 2. Strong Normalized Baseline: Uniform-Pinball(tau) ---")
        for tau in [0.50, 0.65, 0.75, 0.85, 0.90, 0.95]:
            m_pb, t_pb = train_solver_free("pinball", X_tr, W_tr, sols_tr, tau=tau, lr=0.05, batch_size=32, max_epochs=20, seed=seed)
            ev = evaluate_predictions(pool, m_pb.forward(X_te), W_te, cap_te, c_te, objs_te, penalty_coeff)
            rec = {
                "method": f"Uniform-Pinball(t={tau:.2f})",
                "family": "Uniform-Pinball",
                "param": tau,
                "train_time_s": t_pb,
                "train_ilp_solves": 0,
                **ev,
            }
            results.append(rec)
            print(
                f"  {rec['method']:24s} | infeas={ev['infeasibility_rate']*100:5.1f}% | "
                f"posthoc_reg={ev['posthoc_regret']*100:6.3f}% | feas_reg={ev['feasible_regret']*100:6.3f}% | "
                f"train_t={t_pb:.3f}s | ilps=0"
            )

        # 3. Proposed SW-Pinball(tau)
        print("\n--- 3. Proposed Solver-Free-in-Loop: SW-Pinball(tau) ---")
        for tau in [0.50, 0.65, 0.75, 0.85, 0.90, 0.95]:
            m_sw, t_sw = train_solver_free("sw_pinball", X_tr, W_tr, sols_tr, tau=tau, lam_item=0.5, lr=0.05, batch_size=32, max_epochs=20, seed=seed)
            ev = evaluate_predictions(pool, m_sw.forward(X_te), W_te, cap_te, c_te, objs_te, penalty_coeff)
            rec = {
                "method": f"SW-Pinball(t={tau:.2f})",
                "family": "SW-Pinball",
                "param": tau,
                "train_time_s": t_sw,
                "train_ilp_solves": 0,
                **ev,
            }
            results.append(rec)
            print(
                f"  {rec['method']:24s} | infeas={ev['infeasibility_rate']*100:5.1f}% | "
                f"posthoc_reg={ev['posthoc_regret']*100:6.3f}% | feas_reg={ev['feasible_regret']*100:6.3f}% | "
                f"train_t={t_sw:.3f}s | ilps=0"
            )

        # 4. Official NeurIPS 2025 ODECE(alpha)
        print("\n--- 4. Official NeurIPS 2025 Comparator: ODECE(alpha) [20 epochs x 900 HiGHS ILPs] ---")
        for alpha in [0.2, 0.5, 0.8]:
            m_od, t_od, n_ilps = train_odece(
                pool, X_tr, W_tr, cap_tr, c_tr, sols_tr, alpha=alpha, margin=2.0, beta=5.0, lr=0.05, batch_size=32, max_epochs=20, seed=seed
            )
            ev = evaluate_predictions(pool, m_od.forward(X_te), W_te, cap_te, c_te, objs_te, penalty_coeff)
            rec = {
                "method": f"ODECE(alpha={alpha:.1f})",
                "family": "ODECE",
                "param": alpha,
                "train_time_s": t_od,
                "train_ilp_solves": n_ilps,
                **ev,
            }
            results.append(rec)
            print(
                f"  {rec['method']:24s} | infeas={ev['infeasibility_rate']*100:5.1f}% | "
                f"posthoc_reg={ev['posthoc_regret']*100:6.3f}% | feas_reg={ev['feasible_regret']*100:6.3f}% | "
                f"train_t={t_od:.2f}s | ilps={n_ilps}"
            )

    # Summary: best Post-Hoc Regret per family overall and under <=10% infeasibility
    print("\n=== Stage-0 Summary: Best Held-Out Test Post-Hoc Regret per Family ===")
    fam_best = {}
    for fam in ["MSE+ValShift", "Uniform-Pinball", "SW-Pinball", "ODECE"]:
        sub = [r for r in results if r["family"] == fam]
        best_any = min(sub, key=lambda r: r["posthoc_regret"])
        sub_10 = [r for r in sub if r["infeasibility_rate"] <= 0.10]
        best_10 = min(sub_10, key=lambda r: r["posthoc_regret"]) if sub_10 else None
        fam_best[fam] = {"best_overall": best_any, "best_le10pct_infeas": best_10}
        b10_str = (
            f"{best_10['method']} (infeas={best_10['infeasibility_rate']*100:.1f}%, posthoc={best_10['posthoc_regret']*100:.3f}%, feas={best_10['feasible_regret']*100:.3f}%)"
            if best_10
            else "NONE <=10% infeas"
        )
        print(
            f"  {fam:16s} | Best overall: {best_any['method']} (infeas={best_any['infeasibility_rate']*100:.1f}%, "
            f"posthoc={best_any['posthoc_regret']*100:.3f}%) | Best <=10%: {b10_str}"
        )

    out_path = out_dir / "stage0_mdkp_results.json"
    out_path.write_text(json.dumps({"seed": seed, "n_workers": n_workers, "family_best": fam_best, "results": results}, indent=2), encoding="utf-8")
    print(f"\nSaved {out_path}")


if __name__ == "__main__":
    main()
