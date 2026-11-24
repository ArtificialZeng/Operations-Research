"""
Stage-1b Locked Multi-Seed Validation-Pinned Audit on Reserved Seeds 13, 14, 15
(`dfl_constraints_dual_pinball_20261124`).

Locked protocol: STAGE1B_PROTOCOL.md.
Pre-launch gates passed:
  - Stage-0 (seed 11) and Stage-1a (seed 12) sealed files preserved byte-for-byte.
  - MDKP_CAPACITY_SIGNAL_RECEIPT.json saved separately.
  - ODECE_PYTORCH_PARITY_RECEIPT.json verified float64 loss (1.96e-12 abs / 2.07e-13 rel),
    gradients (<=5.58e-12), clipping, and Adam step (<=5.96e-11) directly against
    unmodified pinned PyTorch official_odece_repo/src/odece.py (commit 1b432e03).

Features:
  - Fixed methods & parameters identical to Stage-1a (11 MSE+ValShift, 10 Uniform-Pinball,
    7 official ODECE alphas {0.8..0.2}; NO SW-Pinball).
  - Primary policy: P_le10pct_frac_p1 (val strict 0-1 infeas <= 10%, min frac_p1).
  - Secondary policies: P_le10pct_int_p1, P_le5pct_frac_p1, P_unconstrained_frac_p1.
  - Unrounded float64 HiGHS 1.16.0 cross-audit on 100% of offline test true OPT (500/seed)
    and 100% of unique val-pinned selected test models (500/model/seed).
  - Paired objective & realized-violation uncertainty (95% bootstrap CI, Wilcoxon, McNemar)
    per-seed (n=500) AND pooled across all 3 seeds (n=1,500) + 3-seed mean +/- SD.
  - Fair complete-hyperparameter-sweep training+validation solver calls & wall-clock times.
  - Durable per-arm JSONL + per-instance JSON + per-seed summary.json persistence (resumable).
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

import highspy
import numpy as np
from ortools.sat.python import cp_model
from scipy import stats

BASE = pathlib.Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
OUT_ROOT = BASE / "stage1b_multiseed_13_15"
sys.path.insert(0, str(BASE / "official_odece_repo"))
from OptProblems.knapsack.kpdata import genWeights  # type: ignore

SEEDS = [13, 14, 15]
N_WORKERS = 14
_SCALE = 10000

_CPSAT_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE_NONOPTIMAL",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}

# Precomputed HiGHS static arrays for 50-item 3D MDKP
_LOWER = np.zeros(50, dtype=np.float64)
_UPPER = np.ones(50, dtype=np.float64)
_COL_IDX = np.arange(50, dtype=np.int32)
_VTYPE = np.full(50, highspy.HighsVarType.kInteger)
_ROW_LO = np.full(3, -highspy.kHighsInf, dtype=np.float64)
_INDPTR = np.array([0, 50, 100, 150], dtype=np.int32)
_INDICES = np.tile(np.arange(50, dtype=np.int32), 3)


def safe_arm_filename(arm_id: str) -> str:
    return arm_id.replace("+", "plus").replace("(", "_").replace(")", "").replace("=", "_")


# =============================================================================
# 1. Exact Solvers (OR-Tools CP-SAT + Unrounded float64 HiGHS 1.16.0)
# =============================================================================

def solve_single_cpsat(args: Tuple[np.ndarray, np.ndarray, np.ndarray, float]) -> Tuple[str, np.ndarray, float, float, bool]:
    w_mat, cap_vec, cost_vec, time_lim = args
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
    solver.parameters.max_time_in_seconds = float(time_lim)
    st = solver.Solve(m)
    st_name = _CPSAT_STATUS_NAMES.get(st, f"OTHER_{st}")
    if st in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        sol = np.array([float(solver.Value(xs[j])) for j in range(50)], dtype=np.float64)
        obj_unr = float(np.dot(cost_vec, sol))
        bound_unr = float(solver.BestObjectiveBound()) / _SCALE
        quant_viol = bool(np.any((w_mat @ sol) > cap_vec))
        return st_name, sol, obj_unr, bound_unr, quant_viol
    return st_name, np.zeros(50, dtype=np.float64), float("nan"), float("nan"), False


def solve_single_highs(args: Tuple[np.ndarray, np.ndarray, np.ndarray, float]) -> Tuple[str, np.ndarray, float, float, float]:
    w_mat, cap_vec, cost_vec, time_lim = args
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("threads", 1)
    h.setOptionValue("mip_rel_gap", 1e-4)
    h.setOptionValue("time_limit", float(time_lim))
    h.addVars(50, _LOWER, _UPPER)
    h.changeColsIntegrality(50, _COL_IDX, _VTYPE)
    h.changeColsCost(50, _COL_IDX, (-cost_vec).astype(np.float64))
    h.addRows(3, _ROW_LO, cap_vec.astype(np.float64), 150, _INDPTR, _INDICES, w_mat.reshape(-1).astype(np.float64))
    h.run()
    st_name = str(h.getModelStatus()).replace("HighsModelStatus.", "")
    info = h.getInfo()
    sol_raw = np.array(h.getSolution().col_value, dtype=np.float64)
    if sol_raw.shape[0] == 50 and np.all(np.isfinite(sol_raw)) and st_name in ("kOptimal", "kTimeLimit"):
        sol_bin = np.round(sol_raw)
        int_err = float(np.max(np.abs(sol_raw - sol_bin)))
        obj_unr = float(np.dot(cost_vec, sol_bin))
        gap = float(info.mip_gap) if np.isfinite(info.mip_gap) else float("nan")
        return st_name, sol_bin, obj_unr, gap, int_err
    return st_name, np.zeros(50, dtype=np.float64), float("nan"), float("nan"), float("nan")


def batch_solve_cpsat(
    pool: ProcessPoolExecutor,
    W: np.ndarray,
    cap: np.ndarray,
    costs: np.ndarray,
    time_lim: float = 2.0,
) -> Dict:
    t0 = time.perf_counter()
    tasks = [(W[i], cap[i], costs[i], time_lim) for i in range(len(W))]
    res = list(pool.map(solve_single_cpsat, tasks, chunksize=max(1, len(tasks) // 28)))
    dt = time.perf_counter() - t0
    statuses = [r[0] for r in res]
    sols = np.stack([r[1] for r in res], axis=0)
    objs = np.array([r[2] for r in res], dtype=np.float64)
    bounds = np.array([r[3] for r in res], dtype=np.float64)
    quant_viols = [r[4] for r in res]
    status_counts: Dict[str, int] = {}
    for s in statuses:
        status_counts[s] = status_counts.get(s, 0) + 1
    ok_mask = np.array([s in ("OPTIMAL", "FEASIBLE_NONOPTIMAL") for s in statuses], dtype=bool)
    return {
        "n_calls": len(W),
        "wall_time_s": dt,
        "status_counts": status_counts,
        "quant_pred_violations": int(sum(quant_viols)),
        "ok_mask": ok_mask,
        "statuses": statuses,
        "sols": sols,
        "objs": objs,
        "bounds": bounds,
    }


def batch_solve_highs(
    pool: ProcessPoolExecutor,
    W: np.ndarray,
    cap: np.ndarray,
    costs: np.ndarray,
    time_lim: float = 5.0,
) -> Dict:
    t0 = time.perf_counter()
    tasks = [(W[i], cap[i], costs[i], time_lim) for i in range(len(W))]
    res = list(pool.map(solve_single_highs, tasks, chunksize=max(1, len(tasks) // 28)))
    dt = time.perf_counter() - t0
    statuses = [r[0] for r in res]
    sols = np.stack([r[1] for r in res], axis=0)
    objs = np.array([r[2] for r in res], dtype=np.float64)
    gaps = np.array([r[3] for r in res], dtype=np.float64)
    int_errs = np.array([r[4] for r in res], dtype=np.float64)
    status_counts: Dict[str, int] = {}
    for s in statuses:
        status_counts[s] = status_counts.get(s, 0) + 1
    ok_mask = np.array([s in ("kOptimal", "kTimeLimit") for s in statuses], dtype=bool)
    return {
        "n_calls": len(W),
        "wall_time_s": dt,
        "status_counts": status_counts,
        "max_mip_gap_solved": float(np.nanmax(gaps)) if np.any(np.isfinite(gaps)) else float("nan"),
        "max_integrality_err": float(np.nanmax(int_errs)) if np.any(np.isfinite(int_errs)) else float("nan"),
        "ok_mask": ok_mask,
        "statuses": statuses,
        "sols": sols,
        "objs": objs,
    }


# =============================================================================
# 2. Exact Linear Predictor + Adam + PyTorch-Verified ODECE Loss/Grad
# =============================================================================

class LinearMDKPPredictor:
    def __init__(self, num_feat: int = 10, dim: int = 3, num_items: int = 50, seed: int = 13):
        self.num_feat = num_feat
        self.dim = dim
        self.num_items = num_items
        out_dim = dim * num_items
        rng = np.random.default_rng(seed)
        lim = math.sqrt(6.0 / (num_feat + out_dim))
        self.W = rng.uniform(-lim, lim, size=(num_feat, out_dim)).astype(np.float64)
        self.b = np.zeros(out_dim, dtype=np.float64)
        self.mW = np.zeros_like(self.W)
        self.vW = np.zeros_like(self.W)
        self.mb = np.zeros_like(self.b)
        self.vb = np.zeros_like(self.b)
        self.t = 0

    def forward(self, X: np.ndarray) -> np.ndarray:
        return (X @ self.W + self.b[None, :]).reshape(-1, self.dim, self.num_items)

    def step_adam(self, X: np.ndarray, d_out: np.ndarray, lr: float, clip_norm: Optional[float] = None):
        d_flat = d_out.reshape(X.shape[0], -1)
        gW = X.T @ d_flat
        gb = np.sum(d_flat, axis=0)
        if clip_norm is not None:
            gnorm = math.sqrt(float(np.sum(gW * gW) + np.sum(gb * gb)))
            if gnorm > clip_norm:
                sc = clip_norm / (gnorm + 1e-6)  # exact PyTorch clip_grad_norm_ eps=1e-6
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


def softplus_beta(z: np.ndarray, beta: float = 5.0) -> np.ndarray:
    bz = beta * z
    return np.where(bz > 40.0, z, np.log1p(np.exp(np.minimum(bz, 40.0))) / beta)


def sigmoid_beta(z: np.ndarray, beta: float = 5.0) -> np.ndarray:
    bz = np.clip(beta * z, -60.0, 60.0)
    return 1.0 / (1.0 + np.exp(-bz))


def odece_loss_and_grad(
    w_hat: np.ndarray,
    wb: np.ndarray,
    capb: np.ndarray,
    solb: np.ndarray,
    pred_sols: np.ndarray,
    ok_mask: np.ndarray,
    alpha: float,
    margin: float = 2.0,
    beta: float = 5.0,
) -> Tuple[float, np.ndarray, int]:
    """PyTorch-verified ODECE loss & gradient (ODECE_PYTORCH_PARITY_RECEIPT.json).
    Returns (total_loss, d_total, n_neg_infeas_preds).
    """
    B, D, _ = w_hat.shape
    loss_wrt_true = np.einsum("bdj,bj->bd", w_hat, solb) - capb
    opl_val = float(np.mean(softplus_beta(loss_wrt_true + margin, beta)))
    d_opl = (sigmoid_beta(loss_wrt_true + margin, beta) / (B * D))[:, :, None] * solb[:, None, :]

    ial_val = 0.0
    d_ial = np.zeros_like(w_hat)
    n_neg = 0
    if np.any(ok_mask):
        true_exc = np.einsum("bdj,bj->bd", wb[ok_mask], pred_sols[ok_mask]) - capb[ok_mask]
        viol_pred = (true_exc > 0.0).astype(np.float64)
        viol_cnt = np.sum(viol_pred, axis=1)
        neg_mask = viol_cnt >= 1.0
        n_neg = int(np.sum(neg_mask))
        if n_neg > 0:
            pred_exc = np.einsum("bdj,bj->bd", w_hat[ok_mask][neg_mask], pred_sols[ok_mask][neg_mask]) - capb[ok_mask][neg_mask]
            vp_neg = viol_pred[neg_mask]
            vc_neg = np.maximum(viol_cnt[neg_mask], 1.0)[:, None]
            sp_ial = softplus_beta(-pred_exc + margin, beta)
            ial_per_inst = np.sum(vp_neg * sp_ial, axis=1) / vc_neg[:, 0]
            ial_val = float(np.mean(ial_per_inst))
            d_sp_ial = -sigmoid_beta(-pred_exc + margin, beta)
            coeff = (vp_neg * d_sp_ial) / (vc_neg * n_neg)
            d_ial_sub = coeff[:, :, None] * pred_sols[ok_mask][neg_mask][:, None, :]
            ok_idx = np.where(ok_mask)[0]
            d_ial[ok_idx[neg_mask]] = d_ial_sub

    total_loss = alpha * (ial_val + 1e-4) + (1.0 - alpha) * (opl_val + 1e-4)
    d_total = alpha * d_ial + (1.0 - alpha) * d_opl
    return total_loss, d_total, n_neg


def train_supervised(
    X_tr: np.ndarray,
    W_tr: np.ndarray,
    loss_type: str,
    tau: float = 0.5,
    lr: float = 0.05,
    epochs: int = 20,
    batch_size: int = 32,
    seed: int = 13,
) -> Tuple[LinearMDKPPredictor, float]:
    t0 = time.perf_counter()
    model = LinearMDKPPredictor(seed=seed)
    rng = np.random.default_rng(seed + 1000)
    N = len(X_tr)
    for _ in range(epochs):
        order = rng.permutation(N)
        for s in range(0, N, batch_size):
            idx = order[s : s + batch_size]
            xb, wb = X_tr[idx], W_tr[idx]
            pred = model.forward(xb)
            err = wb - pred
            denom = float(pred.size)
            if loss_type == "mse":
                d_out = (-2.0 * err) / denom
            elif loss_type == "pinball":
                d_out = np.where(err >= 0.0, -tau, 1.0 - tau) / denom
            else:
                raise ValueError(loss_type)
            model.step_adam(xb, d_out, lr=lr, clip_norm=None)
    return model, time.perf_counter() - t0


def train_odece(
    pool: ProcessPoolExecutor,
    X_tr: np.ndarray,
    W_tr: np.ndarray,
    cap_tr: np.ndarray,
    c_tr: np.ndarray,
    sols_tr: np.ndarray,
    alpha: float,
    lr: float = 0.05,
    epochs: int = 20,
    batch_size: int = 32,
    seed: int = 13,
) -> Tuple[LinearMDKPPredictor, Dict]:
    t0 = time.perf_counter()
    model = LinearMDKPPredictor(seed=seed)
    rng = np.random.default_rng(seed + 1000)
    N = len(X_tr)
    status_counts: Dict[str, int] = {}
    n_solves = 0
    solver_time = 0.0
    quant_viols = 0
    n_batches = 0
    n_zero_infeas_batches = 0

    for _ in range(epochs):
        order = rng.permutation(N)
        for s in range(0, N, batch_size):
            idx = order[s : s + batch_size]
            xb, wb, capb, cb, solb = X_tr[idx], W_tr[idx], cap_tr[idx], c_tr[idx], sols_tr[idx]
            w_hat = model.forward(xb)
            bs = batch_solve_cpsat(pool, w_hat, capb, cb, time_lim=2.0)
            n_solves += bs["n_calls"]
            solver_time += bs["wall_time_s"]
            quant_viols += bs["quant_pred_violations"]
            for k, v in bs["status_counts"].items():
                status_counts[k] = status_counts.get(k, 0) + v
            _, d_out, n_neg = odece_loss_and_grad(
                w_hat, wb, capb, solb, bs["sols"], bs["ok_mask"], alpha=alpha, margin=2.0, beta=5.0
            )
            n_batches += 1
            if n_neg == 0:
                n_zero_infeas_batches += 1
            model.step_adam(xb, d_out, lr=lr, clip_norm=0.5)

    return model, {
        "inloop_train_solves": n_solves,
        "inloop_solver_time_s": solver_time,
        "train_wall_time_s": time.perf_counter() - t0,
        "train_status_counts": status_counts,
        "train_quant_pred_violations": quant_viols,
        "n_batches": n_batches,
        "n_zero_infeas_batches": n_zero_infeas_batches,
    }


# =============================================================================
# 3. Exact Unrounded float64 Feasibility, Surrogate & True 0-1 Integer Repair
# =============================================================================

def greedy_strict_01_integer_repair(w_true: np.ndarray, cap_true: np.ndarray, cost_true: np.ndarray, sol: np.ndarray) -> np.ndarray:
    x = np.round(sol).astype(np.float64).copy()
    while True:
        usage = w_true @ x
        viol = usage - cap_true
        if np.all(viol <= 0.0):
            break
        sel = np.where(x > 0.5)[0]
        if len(sel) == 0:
            break
        pos_dims = viol > 0.0
        rel_contrib = np.sum(w_true[pos_dims][:, sel] / cap_true[pos_dims, None], axis=0)
        scores = np.where(rel_contrib > 0.0, cost_true[sel] / np.maximum(rel_contrib, 1e-12), np.inf)
        drop_idx = sel[int(np.argmin(scores))]
        x[drop_idx] = 0.0
    assert np.all((w_true @ x) <= cap_true), "Strict 0-1 integer repair failed feasibility assert!"
    return x


def evaluate_decisions(
    W_true: np.ndarray,
    cap_true: np.ndarray,
    costs_true: np.ndarray,
    true_objs: np.ndarray,
    W_pred: np.ndarray,
    sols: np.ndarray,
    ok_mask: np.ndarray,
    statuses: List[str],
) -> Tuple[Dict, List[Dict]]:
    N = len(W_true)
    per_inst = []
    feas_regrets = []
    frac_p1_list, frac_p021_list = [], []
    int_p1_list, int_p021_list = [], []
    n_infeas = 0
    n_unsolvable = 0

    for i in range(N):
        t_obj = float(true_objs[i])
        if not ok_mask[i]:
            n_unsolvable += 1
            n_infeas += 1
            per_inst.append({
                "idx": i, "status": statuses[i], "strict_01_feasible": False,
                "max_true_viol": float("nan"), "raw_regret": 1.0,
                "frac_p1": 1.0, "frac_p021": 1.0, "int_p1": 1.0, "int_p021": 1.0,
            })
            frac_p1_list.append(1.0); frac_p021_list.append(1.0)
            int_p1_list.append(1.0); int_p021_list.append(1.0)
            continue

        x = np.round(sols[i]).astype(np.float64)
        usage = W_true[i] @ x
        viol = usage - cap_true[i]
        max_viol = float(np.max(viol))
        strict_feas = bool(np.all(viol <= 0.0))
        real_obj = float(np.dot(costs_true[i], x))
        raw_reg = (t_obj - real_obj) / t_obj

        if strict_feas:
            feas_regrets.append(raw_reg)
            fp1 = fp021 = ip1 = ip021 = raw_reg
        else:
            n_infeas += 1
            # Official upstream fractional-scaling surrogate (kpsolver.py L81-88)
            max_tau = float(max(1.0, np.max(usage / cap_true[i])))
            x_frac = x / max_tau
            corr_frac = float(np.dot(costs_true[i], x_frac))
            fp1 = (t_obj - corr_frac) / t_obj + 1.0 * abs(real_obj - corr_frac) / t_obj
            fp021 = (t_obj - corr_frac) / t_obj + 0.21 * abs(real_obj - corr_frac) / t_obj

            # True strict 0-1 integer repair
            x_int = greedy_strict_01_integer_repair(W_true[i], cap_true[i], costs_true[i], x)
            corr_int = float(np.dot(costs_true[i], x_int))
            ip1 = (t_obj - corr_int) / t_obj + 1.0 * abs(real_obj - corr_int) / t_obj
            ip021 = (t_obj - corr_int) / t_obj + 0.21 * abs(real_obj - corr_int) / t_obj

        frac_p1_list.append(fp1); frac_p021_list.append(fp021)
        int_p1_list.append(ip1); int_p021_list.append(ip021)
        per_inst.append({
            "idx": i, "status": statuses[i], "strict_01_feasible": strict_feas,
            "max_true_viol": max_viol, "raw_regret": float(raw_reg),
            "frac_p1": float(fp1), "frac_p021": float(fp021),
            "int_p1": float(ip1), "int_p021": float(ip021),
        })

    metrics = {
        "strict_01_infeasibility_rate": float(n_infeas / N),
        "strict_01_feasible_count": int(N - n_infeas),
        "strict_01_feasible_regret": float(np.mean(feas_regrets)) if feas_regrets else float("nan"),
        "official_frac_surrogate_posthoc_p1": float(np.mean(frac_p1_list)),
        "official_frac_surrogate_posthoc_p021": float(np.mean(frac_p021_list)),
        "strict_01_int_repair_posthoc_p1": float(np.mean(int_p1_list)),
        "strict_01_int_repair_posthoc_p021": float(np.mean(int_p021_list)),
        "unsolvable_rate": float(n_unsolvable / N),
        "weight_mse": float(np.mean((W_pred - W_true) ** 2)),
    }
    return metrics, per_inst


# =============================================================================
# 4. Paired Statistical Comparison (Objective & Realized Violation Uncertainty)
# =============================================================================

def paired_compare(pa: List[Dict], pb: List[Dict], rng: np.random.Generator, n_boot: int = 10000) -> Dict:
    out: Dict = {"n_paired": len(pa)}
    n = len(pa)
    idx = rng.integers(0, n, size=(n_boot, n))
    for metric in ["frac_p1", "int_p1", "frac_p021", "int_p021"]:
        va = np.array([r[metric] for r in pa], dtype=np.float64)
        vb = np.array([r[metric] for r in pb], dtype=np.float64)
        diff = va - vb
        boot = diff[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        if np.any(diff != 0.0):
            _, p_wil = stats.wilcoxon(diff)
            p_wil = float(p_wil)
        else:
            p_wil = 1.0
        out[metric] = {
            "mean_a": float(va.mean()),
            "mean_b": float(vb.mean()),
            "mean_diff_a_minus_b": float(diff.mean()),
            "ci95_low": float(lo),
            "ci95_high": float(hi),
            "wilcoxon_p": p_wil,
        }

    ia = np.array([0.0 if r["strict_01_feasible"] else 1.0 for r in pa], dtype=np.float64)
    ib = np.array([0.0 if r["strict_01_feasible"] else 1.0 for r in pb], dtype=np.float64)
    idiff = ia - ib
    iboot = idiff[idx].mean(axis=1)
    ilo, ihi = np.percentile(iboot, [2.5, 97.5])
    n10 = int(np.sum((ia == 1.0) & (ib == 0.0)))
    n01 = int(np.sum((ia == 0.0) & (ib == 1.0)))
    p_mc = float(stats.binomtest(min(n10, n01), n10 + n01, 0.5).pvalue) if (n10 + n01) > 0 else 1.0
    out["strict_01_infeasibility"] = {
        "rate_a": float(ia.mean()),
        "rate_b": float(ib.mean()),
        "diff_a_minus_b": float(ia.mean() - ib.mean()),
        "ci95_low": float(ilo),
        "ci95_high": float(ihi),
        "discordant_a_infeas_only": n10,
        "discordant_b_infeas_only": n01,
        "mcnemar_exact_p": p_mc,
    }
    return out


# =============================================================================
# 5. Per-Seed Locked Execution (Resumable + Durable Persistence)
# =============================================================================

def select_val_pinned(arms: List[Dict], metric_key: str, max_val_infeas: Optional[float]) -> Dict:
    if max_val_infeas is None:
        return min(arms, key=lambda a: (a["val_metrics"][metric_key], a["val_metrics"]["strict_01_infeasibility_rate"]))
    qual = [a for a in arms if a["val_metrics"]["strict_01_infeasibility_rate"] <= max_val_infeas + 1e-12]
    if qual:
        return min(qual, key=lambda a: (a["val_metrics"][metric_key], a["val_metrics"]["strict_01_infeasibility_rate"]))
    return min(arms, key=lambda a: (a["val_metrics"]["strict_01_infeasibility_rate"], a["val_metrics"][metric_key]))


def run_one_seed(pool: ProcessPoolExecutor, seed: int) -> Dict:
    seed_dir = OUT_ROOT / f"seed_{seed}"
    summary_path = seed_dir / "summary.json"
    pi_dir = seed_dir / "per_instance"
    inc_path = seed_dir / "incremental.jsonl"

    if summary_path.exists():
        print(f"\n[Seed {seed}] Found completed checkpoint at {summary_path}; loading cleanly.", flush=True)
        return json.loads(summary_path.read_text(encoding="utf-8"))

    seed_dir.mkdir(parents=True, exist_ok=True)
    pi_dir.mkdir(parents=True, exist_ok=True)
    if inc_path.exists():
        inc_path.unlink()

    print(f"\n==================== STAGE-1B RESERVED SEED {seed} ====================", flush=True)
    cap_ratio = np.array([0.18, 0.20, 0.22], dtype=np.float64)
    X, w, costs, capacity = genWeights(1500, 10, 50, cap_ratio, 3, 6, 0.25, seed=seed)
    perm = np.random.RandomState(seed).permutation(1500)
    X, w, capacity, costs = X[perm], w[perm], capacity[perm], costs[perm]

    X_tr, W_tr, cap_tr, c_tr = X[:900], w[:900], capacity[:900], costs[:900]
    X_va, W_va, cap_va, c_va = X[900:1000], w[900:1000], capacity[900:1000], costs[900:1000]
    X_te, W_te, cap_te, c_te = X[1000:], w[1000:], capacity[1000:], costs[1000:]

    cpsat_calls_actual = 0
    highs_calls_actual = 0

    # Step 1: Offline true oracle MIPs (CP-SAT + full 500-instance HiGHS float64 audit on test)
    print(f"[Seed {seed} Step 1] Solving offline true oracle MIPs (900 tr / 100 va / 500 te) + HiGHS float64 test audit...", flush=True)
    off_tr = batch_solve_cpsat(pool, W_tr, cap_tr, c_tr, time_lim=5.0)
    off_va = batch_solve_cpsat(pool, W_va, cap_va, c_va, time_lim=5.0)
    off_te = batch_solve_cpsat(pool, W_te, cap_te, c_te, time_lim=5.0)
    cpsat_calls_actual += off_tr["n_calls"] + off_va["n_calls"] + off_te["n_calls"]

    off_te_h = batch_solve_highs(pool, W_te, cap_te, c_te, time_lim=5.0)
    highs_calls_actual += off_te_h["n_calls"]
    rel_diff_opt = float(np.max(np.abs(off_te["objs"] - off_te_h["objs"]) / np.maximum(np.abs(off_te_h["objs"]), 1e-12)))
    print(
        f"  Offline CP-SAT: tr={off_tr['status_counts']} ({off_tr['wall_time_s']:.2f}s), "
        f"va={off_va['status_counts']} ({off_va['wall_time_s']:.2f}s), te={off_te['status_counts']} ({off_te['wall_time_s']:.2f}s)",
        flush=True,
    )
    print(
        f"  Offline HiGHS-1.16.0 test: {off_te_h['status_counts']} ({off_te_h['wall_time_s']:.2f}s), "
        f"max_gap={off_te_h['max_mip_gap_solved']:.2e}, int_err={off_te_h['max_integrality_err']:.2e}, "
        f"CP-SAT vs HiGHS max rel diff={rel_diff_opt:.2e}",
        flush=True,
    )

    all_arms: List[Dict] = []
    test_preds_by_arm: Dict[str, np.ndarray] = {}

    def record_arm(arm_record: Dict, per_inst_test: List[Dict], w_pred_test: np.ndarray):
        all_arms.append(arm_record)
        test_preds_by_arm[arm_record["arm_id"]] = w_pred_test
        with inc_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(arm_record) + "\n")
            fh.flush()
        (pi_dir / f"{safe_arm_filename(arm_record['arm_id'])}.json").write_text(
            json.dumps(per_inst_test), encoding="utf-8"
        )

    # Family 1: MSE + Val-Shift (11 gammas)
    print(f"[Seed {seed} Step 2] Family 1: MSE + Val-Shift (11 gammas)...", flush=True)
    mse_model, mse_train_t = train_supervised(X_tr, W_tr, loss_type="mse", seed=seed)
    w_va_mse = mse_model.forward(X_va)
    w_te_mse = mse_model.forward(X_te)
    sigma_val = np.std(W_va - w_va_mse, axis=0, ddof=1)  # strictly on val!

    gammas = [0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00]
    for g in gammas:
        arm_id = "MSE" if g == 0.0 else f"MSE+ValShift(g={g:.2f})"
        wv = w_va_mse + g * sigma_val[None, :, :]
        wt = w_te_mse + g * sigma_val[None, :, :]
        sv = batch_solve_cpsat(pool, wv, cap_va, c_va, time_lim=2.0)
        st = batch_solve_cpsat(pool, wt, cap_te, c_te, time_lim=2.0)
        cpsat_calls_actual += sv["n_calls"] + st["n_calls"]
        vm, _ = evaluate_decisions(W_va, cap_va, c_va, off_va["objs"], wv, sv["sols"], sv["ok_mask"], sv["statuses"])
        tm, pi_t = evaluate_decisions(W_te, cap_te, c_te, off_te["objs"], wt, st["sols"], st["ok_mask"], st["statuses"])
        rec = {
            "arm_id": arm_id, "family": "MSE+ValShift", "param": g,
            "costs": {
                "offline_train_label_solves": 0, "offline_train_label_time_s": 0.0,
                "inloop_train_solves": 0, "train_wall_time_s": mse_train_t,
                "val_eval_solves": sv["n_calls"], "val_eval_time_s": sv["wall_time_s"],
                "test_eval_solves": st["n_calls"], "test_eval_time_s": st["wall_time_s"],
                "single_arm_train_plus_val_solves": sv["n_calls"],
            },
            "val_solver_audit": {"status_counts": sv["status_counts"], "quant_pred_violations": sv["quant_pred_violations"]},
            "test_solver_audit": {"status_counts": st["status_counts"], "quant_pred_violations": st["quant_pred_violations"]},
            "val_metrics": vm, "test_metrics": tm,
        }
        record_arm(rec, pi_t, wt)
        print(
            f"  {arm_id:24s} | VAL inf={vm['strict_01_infeasibility_rate']*100:5.1f}% fp1={vm['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
            f"| TEST inf={tm['strict_01_infeasibility_rate']*100:5.1f}% fp1={tm['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
            f"ip1={tm['strict_01_int_repair_posthoc_p1']*100:6.2f}% | st={st['status_counts']}",
            flush=True,
        )

    # Family 2: Uniform-Pinball (10 taus)
    print(f"[Seed {seed} Step 3] Family 2: Uniform-Pinball (10 taus)...", flush=True)
    taus = [0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]
    for tau in taus:
        arm_id = f"Uniform-Pinball(t={tau:.2f})"
        pm, p_train_t = train_supervised(X_tr, W_tr, loss_type="pinball", tau=tau, seed=seed)
        wv = pm.forward(X_va)
        wt = pm.forward(X_te)
        sv = batch_solve_cpsat(pool, wv, cap_va, c_va, time_lim=2.0)
        st = batch_solve_cpsat(pool, wt, cap_te, c_te, time_lim=2.0)
        cpsat_calls_actual += sv["n_calls"] + st["n_calls"]
        vm, _ = evaluate_decisions(W_va, cap_va, c_va, off_va["objs"], wv, sv["sols"], sv["ok_mask"], sv["statuses"])
        tm, pi_t = evaluate_decisions(W_te, cap_te, c_te, off_te["objs"], wt, st["sols"], st["ok_mask"], st["statuses"])
        rec = {
            "arm_id": arm_id, "family": "Uniform-Pinball", "param": tau,
            "costs": {
                "offline_train_label_solves": 0, "offline_train_label_time_s": 0.0,
                "inloop_train_solves": 0, "train_wall_time_s": p_train_t,
                "val_eval_solves": sv["n_calls"], "val_eval_time_s": sv["wall_time_s"],
                "test_eval_solves": st["n_calls"], "test_eval_time_s": st["wall_time_s"],
                "single_arm_train_plus_val_solves": sv["n_calls"],
            },
            "val_solver_audit": {"status_counts": sv["status_counts"], "quant_pred_violations": sv["quant_pred_violations"]},
            "test_solver_audit": {"status_counts": st["status_counts"], "quant_pred_violations": st["quant_pred_violations"]},
            "val_metrics": vm, "test_metrics": tm,
        }
        record_arm(rec, pi_t, wt)
        print(
            f"  {arm_id:24s} | VAL inf={vm['strict_01_infeasibility_rate']*100:5.1f}% fp1={vm['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
            f"| TEST inf={tm['strict_01_infeasibility_rate']*100:5.1f}% fp1={tm['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
            f"ip1={tm['strict_01_int_repair_posthoc_p1']*100:6.2f}% | st={st['status_counts']}",
            flush=True,
        )

    # Family 3: Official 7-alpha ODECE
    print(f"[Seed {seed} Step 4] Family 3: Official 7-alpha ODECE (900 offline + 18,000 in-loop per alpha)...", flush=True)
    alphas = [0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2]
    for alpha in alphas:
        arm_id = f"ODECE(alpha={alpha:.1f})"
        om, tr_info = train_odece(pool, X_tr, W_tr, cap_tr, c_tr, off_tr["sols"], alpha=alpha, seed=seed)
        cpsat_calls_actual += tr_info["inloop_train_solves"]
        wv = om.forward(X_va)
        wt = om.forward(X_te)
        sv = batch_solve_cpsat(pool, wv, cap_va, c_va, time_lim=2.0)
        st = batch_solve_cpsat(pool, wt, cap_te, c_te, time_lim=2.0)
        cpsat_calls_actual += sv["n_calls"] + st["n_calls"]
        vm, _ = evaluate_decisions(W_va, cap_va, c_va, off_va["objs"], wv, sv["sols"], sv["ok_mask"], sv["statuses"])
        tm, pi_t = evaluate_decisions(W_te, cap_te, c_te, off_te["objs"], wt, st["sols"], st["ok_mask"], st["statuses"])
        rec = {
            "arm_id": arm_id, "family": "ODECE", "param": alpha,
            "costs": {
                "offline_train_label_solves": off_tr["n_calls"], "offline_train_label_time_s": off_tr["wall_time_s"],
                "inloop_train_solves": tr_info["inloop_train_solves"],
                "inloop_solver_time_s": tr_info["inloop_solver_time_s"],
                "train_wall_time_s": tr_info["train_wall_time_s"],
                "val_eval_solves": sv["n_calls"], "val_eval_time_s": sv["wall_time_s"],
                "test_eval_solves": st["n_calls"], "test_eval_time_s": st["wall_time_s"],
                "single_arm_train_plus_val_solves": off_tr["n_calls"] + tr_info["inloop_train_solves"] + sv["n_calls"],
            },
            "train_solver_audit": {
                "status_counts": tr_info["train_status_counts"],
                "quant_pred_violations": tr_info["train_quant_pred_violations"],
                "n_batches": tr_info["n_batches"],
                "n_zero_infeas_batches": tr_info["n_zero_infeas_batches"],
            },
            "val_solver_audit": {"status_counts": sv["status_counts"], "quant_pred_violations": sv["quant_pred_violations"]},
            "test_solver_audit": {"status_counts": st["status_counts"], "quant_pred_violations": st["quant_pred_violations"]},
            "val_metrics": vm, "test_metrics": tm,
        }
        record_arm(rec, pi_t, wt)
        print(
            f"  {arm_id:24s} | train_t={tr_info['train_wall_time_s']:6.2f}s (st={tr_info['train_status_counts']}, z0={tr_info['n_zero_infeas_batches']}) "
            f"| VAL inf={vm['strict_01_infeasibility_rate']*100:5.1f}% fp1={vm['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
            f"| TEST inf={tm['strict_01_infeasibility_rate']*100:5.1f}% fp1={tm['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
            f"ip1={tm['strict_01_int_repair_posthoc_p1']*100:6.2f}%",
            flush=True,
        )

    # Step 5: Validation-Pinned Confirmatory Selection + Full 500-Instance Unrounded HiGHS 1.16.0 Cross-Audit
    print(f"[Seed {seed} Step 5] Validation-pinned confirmatory selection + HiGHS 1.16.0 float64 audit...", flush=True)
    policies = {
        "P_le10pct_frac_p1": ("official_frac_surrogate_posthoc_p1", 0.10),
        "P_le10pct_int_p1": ("strict_01_int_repair_posthoc_p1", 0.10),
        "P_le5pct_frac_p1": ("official_frac_surrogate_posthoc_p1", 0.05),
        "P_unconstrained_frac_p1": ("official_frac_surrogate_posthoc_p1", None),
    }
    families = ["MSE+ValShift", "Uniform-Pinball", "ODECE"]
    selected_by_pol: Dict[str, Dict[str, Dict]] = {}
    unique_selected_ids = set()
    for pol_name, (mkey, max_inf) in policies.items():
        selected_by_pol[pol_name] = {}
        for fam in families:
            fam_arms = [a for a in all_arms if a["family"] == fam]
            win = select_val_pinned(fam_arms, mkey, max_inf)
            selected_by_pol[pol_name][fam] = win
            unique_selected_ids.add(win["arm_id"])

    highs_audit: Dict[str, Dict] = {}
    highs_per_inst_by_arm: Dict[str, List[Dict]] = {}
    for arm_id in sorted(unique_selected_ids):
        wt = test_preds_by_arm[arm_id]
        sh = batch_solve_highs(pool, wt, cap_te, c_te, time_lim=5.0)
        highs_calls_actual += sh["n_calls"]
        hm, pi_h = evaluate_decisions(W_te, cap_te, c_te, off_te_h["objs"], wt, sh["sols"], sh["ok_mask"], sh["statuses"])
        highs_per_inst_by_arm[arm_id] = pi_h
        (pi_dir / f"highs_{safe_arm_filename(arm_id)}.json").write_text(json.dumps(pi_h), encoding="utf-8")
        # Compute exact CP-SAT vs HiGHS delta
        arm_rec = next(a for a in all_arms if a["arm_id"] == arm_id)
        cpsat_tm = arm_rec["test_metrics"]
        deltas = {
            k: abs(float(hm[k]) - float(cpsat_tm[k]))
            for k in ["strict_01_infeasibility_rate", "official_frac_surrogate_posthoc_p1", "strict_01_int_repair_posthoc_p1"]
        }
        highs_audit[arm_id] = {
            "highs_status_counts": sh["status_counts"],
            "highs_wall_time_s": sh["wall_time_s"],
            "highs_max_mip_gap": sh["max_mip_gap_solved"],
            "highs_max_integrality_err": sh["max_integrality_err"],
            "test_metrics_highs_float64": hm,
            "cpsat_vs_highs_abs_delta": deltas,
        }
        print(
            f"  [HiGHS float64] {arm_id:24s} | st={sh['status_counts']} ({sh['wall_time_s']:.2f}s, gap={sh['max_mip_gap_solved']:.2e}) "
            f"| inf={hm['strict_01_infeasibility_rate']*100:5.1f}% fp1={hm['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
            f"ip1={hm['strict_01_int_repair_posthoc_p1']*100:6.2f}% | max_delta={max(deltas.values()):.2e}",
            flush=True,
        )

    # Assemble confirmatory table & per-seed paired stats (on HiGHS float64 per-instance outcomes!)
    rng_stat = np.random.default_rng(20261124 + seed)
    confirmatory: Dict[str, Dict] = {}
    paired_stats: Dict[str, Dict] = {}
    for pol_name in policies:
        confirmatory[pol_name] = {}
        for fam in families:
            wrec = selected_by_pol[pol_name][fam]
            aid = wrec["arm_id"]
            confirmatory[pol_name][fam] = {
                "selected_arm": aid,
                "val_metrics": wrec["val_metrics"],
                "test_metrics_cpsat": wrec["test_metrics"],
                "test_metrics_highs_float64": highs_audit[aid]["test_metrics_highs_float64"],
                "costs": wrec["costs"],
            }
        id_up = selected_by_pol[pol_name]["Uniform-Pinball"]["arm_id"]
        id_od = selected_by_pol[pol_name]["ODECE"]["arm_id"]
        id_ms = selected_by_pol[pol_name]["MSE+ValShift"]["arm_id"]
        paired_stats[pol_name] = {
            "UniformPinball_minus_ODECE": {
                "arm_a": id_up, "arm_b": id_od,
                **paired_compare(highs_per_inst_by_arm[id_up], highs_per_inst_by_arm[id_od], rng_stat),
            },
            "UniformPinball_minus_MSEValShift": {
                "arm_a": id_up, "arm_b": id_ms,
                **paired_compare(highs_per_inst_by_arm[id_up], highs_per_inst_by_arm[id_ms], rng_stat),
            },
        }

    # Complete-hyperparameter-sweep training+validation costs per family
    sweep_costs: Dict[str, Dict] = {}
    for fam in families:
        fam_arms = [a for a in all_arms if a["family"] == fam]
        if fam == "MSE+ValShift":
            off_s, off_t, inl_s = 0, 0.0, 0
            tr_t = fam_arms[0]["costs"]["train_wall_time_s"]
        elif fam == "Uniform-Pinball":
            off_s, off_t, inl_s = 0, 0.0, 0
            tr_t = sum(a["costs"]["train_wall_time_s"] for a in fam_arms)
        else:
            off_s = fam_arms[0]["costs"]["offline_train_label_solves"]
            off_t = fam_arms[0]["costs"]["offline_train_label_time_s"]
            inl_s = sum(a["costs"]["inloop_train_solves"] for a in fam_arms)
            tr_t = sum(a["costs"]["train_wall_time_s"] for a in fam_arms)
        val_s = sum(a["costs"]["val_eval_solves"] for a in fam_arms)
        val_t = sum(a["costs"]["val_eval_time_s"] for a in fam_arms)
        sweep_costs[fam] = {
            "n_arms": len(fam_arms),
            "shared_offline_train_solves": off_s,
            "shared_offline_train_time_s": off_t,
            "total_inloop_train_solves": inl_s,
            "total_train_wall_time_s": tr_t,
            "total_val_selection_solves": val_s,
            "total_val_selection_time_s": val_t,
            "complete_sweep_train_plus_val_solves": off_s + inl_s + val_s,
            "complete_sweep_train_plus_val_wall_time_s": off_t + tr_t + val_t,
        }

    # Exact CP-SAT call parity check
    accounted_cpsat = (
        off_tr["n_calls"] + off_va["n_calls"] + off_te["n_calls"]
        + sum(a["costs"]["inloop_train_solves"] + a["costs"]["val_eval_solves"] + a["costs"]["test_eval_solves"] for a in all_arms)
    )
    assert accounted_cpsat == cpsat_calls_actual, f"CP-SAT parity mismatch: {accounted_cpsat} vs {cpsat_calls_actual}"

    seed_summary = {
        "protocol": "STAGE1B_PROTOCOL.md",
        "benchmark_label": "Aligned benchmark adaptation of official Apache-2.0 ODECE MDKP-Weights (commit 1b432e03)",
        "seed": seed,
        "n_workers": N_WORKERS,
        "offline_audit": {
            "train_cpsat": {"calls": off_tr["n_calls"], "wall_time_s": off_tr["wall_time_s"], "status_counts": off_tr["status_counts"]},
            "val_cpsat": {"calls": off_va["n_calls"], "wall_time_s": off_va["wall_time_s"], "status_counts": off_va["status_counts"]},
            "test_cpsat": {"calls": off_te["n_calls"], "wall_time_s": off_te["wall_time_s"], "status_counts": off_te["status_counts"]},
            "test_highs_float64": {
                "calls": off_te_h["n_calls"], "wall_time_s": off_te_h["wall_time_s"],
                "status_counts": off_te_h["status_counts"],
                "max_mip_gap": off_te_h["max_mip_gap_solved"],
                "max_integrality_err": off_te_h["max_integrality_err"],
                "cpsat_vs_highs_max_rel_diff": rel_diff_opt,
            },
        },
        "solver_call_parity": {
            "total_cpsat_calls_actual": cpsat_calls_actual,
            "total_cpsat_calls_accounted": accounted_cpsat,
            "parity_exact": True,
            "total_highs_float64_audit_calls": highs_calls_actual,
        },
        "complete_sweep_train_val_costs": sweep_costs,
        "confirmatory_val_pinned": confirmatory,
        "paired_test_stats_highs_float64": paired_stats,
        "highs_float64_winner_audit": highs_audit,
        "descriptive_all_arms": all_arms,
    }
    summary_path.write_text(json.dumps(seed_summary, indent=2), encoding="utf-8")
    p10 = confirmatory["P_le10pct_frac_p1"]
    print(f"\n[Seed {seed} DONE] Saved {summary_path} (CP-SAT={cpsat_calls_actual}, HiGHS={highs_calls_actual})", flush=True)
    for fam in families:
        hm = p10[fam]["test_metrics_highs_float64"]
        print(
            f"  PRIMARY P_le10pct | {fam:16s} -> {p10[fam]['selected_arm']:24s} | "
            f"HiGHS TEST inf={hm['strict_01_infeasibility_rate']*100:5.2f}% "
            f"fp1={hm['official_frac_surrogate_posthoc_p1']*100:6.3f}% "
            f"ip1={hm['strict_01_int_repair_posthoc_p1']*100:6.3f}%",
            flush=True,
        )
    return seed_summary


# =============================================================================
# 6. Multi-Seed Aggregate & Pooled Paired Statistics (Seeds 13, 14, 15)
# =============================================================================

def aggregate_multiseed(seed_summaries: List[Dict]) -> Dict:
    policies = ["P_le10pct_frac_p1", "P_le10pct_int_p1", "P_le5pct_frac_p1", "P_unconstrained_frac_p1"]
    families = ["MSE+ValShift", "Uniform-Pinball", "ODECE"]
    rng_pool = np.random.default_rng(2026112400)

    agg_policies: Dict[str, Dict] = {}
    for pol in policies:
        per_fam_agg: Dict[str, Dict] = {}
        pooled_pi_by_fam: Dict[str, List[Dict]] = {fam: [] for fam in families}
        for fam in families:
            per_seed_rows = []
            for ss in seed_summaries:
                s = ss["seed"]
                entry = ss["confirmatory_val_pinned"][pol][fam]
                aid = entry["selected_arm"]
                hm = entry["test_metrics_highs_float64"]
                per_seed_rows.append({
                    "seed": s, "selected_arm": aid,
                    "val_infeas": entry["val_metrics"]["strict_01_infeasibility_rate"],
                    "test_infeas_highs": hm["strict_01_infeasibility_rate"],
                    "test_frac_p1_highs": hm["official_frac_surrogate_posthoc_p1"],
                    "test_int_p1_highs": hm["strict_01_int_repair_posthoc_p1"],
                    "test_frac_p021_highs": hm["official_frac_surrogate_posthoc_p021"],
                    "test_int_p021_highs": hm["strict_01_int_repair_posthoc_p021"],
                    "test_feas_regret_highs": hm["strict_01_feasible_regret"],
                })
                pi_path = OUT_ROOT / f"seed_{s}" / "per_instance" / f"highs_{safe_arm_filename(aid)}.json"
                pooled_pi_by_fam[fam].extend(json.loads(pi_path.read_text(encoding="utf-8")))

            def m_sd(key: str) -> Dict:
                vals = np.array([r[key] for r in per_seed_rows], dtype=np.float64)
                return {"mean": float(vals.mean()), "sd_ddof1": float(vals.std(ddof=1)), "min": float(vals.min()), "max": float(vals.max())}

            per_fam_agg[fam] = {
                "per_seed": per_seed_rows,
                "across_3_seeds": {
                    "test_infeas_highs": m_sd("test_infeas_highs"),
                    "test_frac_p1_highs": m_sd("test_frac_p1_highs"),
                    "test_int_p1_highs": m_sd("test_int_p1_highs"),
                    "test_frac_p021_highs": m_sd("test_frac_p021_highs"),
                    "test_int_p021_highs": m_sd("test_int_p021_highs"),
                },
            }

        agg_policies[pol] = {
            "families": per_fam_agg,
            "pooled_paired_stats_n1500_highs_float64": {
                "UniformPinball_minus_ODECE": paired_compare(pooled_pi_by_fam["Uniform-Pinball"], pooled_pi_by_fam["ODECE"], rng_pool),
                "UniformPinball_minus_MSEValShift": paired_compare(pooled_pi_by_fam["Uniform-Pinball"], pooled_pi_by_fam["MSE+ValShift"], rng_pool),
            },
            "per_seed_paired_stats_n500_highs_float64": {
                str(ss["seed"]): ss["paired_test_stats_highs_float64"][pol] for ss in seed_summaries
            },
        }

    # Aggregate complete-hyperparameter-sweep training+validation costs across 3 seeds
    agg_sweep_costs: Dict[str, Dict] = {}
    for fam in families:
        rows = [ss["complete_sweep_train_val_costs"][fam] for ss in seed_summaries]
        agg_sweep_costs[fam] = {
            "n_arms_per_seed": rows[0]["n_arms"],
            "total_3seed_shared_offline_train_solves": int(sum(r["shared_offline_train_solves"] for r in rows)),
            "total_3seed_inloop_train_solves": int(sum(r["total_inloop_train_solves"] for r in rows)),
            "total_3seed_val_selection_solves": int(sum(r["total_val_selection_solves"] for r in rows)),
            "total_3seed_complete_sweep_train_plus_val_solves": int(sum(r["complete_sweep_train_plus_val_solves"] for r in rows)),
            "total_3seed_complete_sweep_wall_time_s": float(sum(r["complete_sweep_train_plus_val_wall_time_s"] for r in rows)),
            "per_seed_mean_sweep_wall_time_s": float(np.mean([r["complete_sweep_train_plus_val_wall_time_s"] for r in rows])),
        }

    return {
        "protocol": "STAGE1B_PROTOCOL.md",
        "benchmark_label": "Aligned benchmark adaptation of official Apache-2.0 ODECE MDKP-Weights (commit 1b432e03)",
        "seeds": [ss["seed"] for ss in seed_summaries],
        "total_test_instances_pooled": 500 * len(seed_summaries),
        "total_cpsat_calls_all_seeds": int(sum(ss["solver_call_parity"]["total_cpsat_calls_actual"] for ss in seed_summaries)),
        "total_highs_calls_all_seeds": int(sum(ss["solver_call_parity"]["total_highs_float64_audit_calls"] for ss in seed_summaries)),
        "all_seeds_parity_exact": bool(all(ss["solver_call_parity"]["parity_exact"] for ss in seed_summaries)),
        "complete_sweep_train_val_costs_3seeds": agg_sweep_costs,
        "policies": agg_policies,
    }


def main():
    t_all = time.perf_counter()
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    seed_summaries = []
    with ProcessPoolExecutor(max_workers=N_WORKERS) as pool:
        for seed in SEEDS:
            ss = run_one_seed(pool, seed)
            seed_summaries.append(ss)

    agg = aggregate_multiseed(seed_summaries)
    agg["total_script_wall_time_s"] = time.perf_counter() - t_all
    agg_path = OUT_ROOT / "stage1b_aggregate_summary.json"
    agg_path.write_text(json.dumps(agg, indent=2), encoding="utf-8")

    print("\n================ STAGE-1B 3-SEED AGGREGATE (SEEDS 13, 14, 15) ================", flush=True)
    p10 = agg["policies"]["P_le10pct_frac_p1"]
    for fam in ["MSE+ValShift", "Uniform-Pinball", "ODECE"]:
        a3 = p10["families"][fam]["across_3_seeds"]
        print(
            f"  PRIMARY P_le10pct | {fam:16s} | "
            f"infeas={a3['test_infeas_highs']['mean']*100:5.2f} +/- {a3['test_infeas_highs']['sd_ddof1']*100:4.2f}% | "
            f"frac_p1={a3['test_frac_p1_highs']['mean']*100:6.3f} +/- {a3['test_frac_p1_highs']['sd_ddof1']*100:5.3f}% | "
            f"int_p1={a3['test_int_p1_highs']['mean']*100:6.3f} +/- {a3['test_int_p1_highs']['sd_ddof1']*100:5.3f}%",
            flush=True,
        )
    po = p10["pooled_paired_stats_n1500_highs_float64"]["UniformPinball_minus_ODECE"]
    print(
        f"  POOLED (n=1500) Uniform-Pinball - ODECE: "
        f"frac_p1={po['frac_p1']['mean_diff_a_minus_b']*100:+.3f}pp [{po['frac_p1']['ci95_low']*100:+.3f}, {po['frac_p1']['ci95_high']*100:+.3f}] (p={po['frac_p1']['wilcoxon_p']:.2e}) | "
        f"int_p1={po['int_p1']['mean_diff_a_minus_b']*100:+.3f}pp [{po['int_p1']['ci95_low']*100:+.3f}, {po['int_p1']['ci95_high']*100:+.3f}] (p={po['int_p1']['wilcoxon_p']:.2e}) | "
        f"infeas={po['strict_01_infeasibility']['diff_a_minus_b']*100:+.2f}pp [{po['strict_01_infeasibility']['ci95_low']*100:+.2f}, {po['strict_01_infeasibility']['ci95_high']*100:+.2f}] (McNemar p={po['strict_01_infeasibility']['mcnemar_exact_p']:.2e})",
        flush=True,
    )
    print(f"Saved complete 3-seed aggregate to {agg_path} (total wall={agg['total_script_wall_time_s']:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
