"""
Stage-3 Capacity Published-Comparison Bounded Intervention:
`ODECE(alpha=0.5)` vs. Upstream `PFL/MSE` Baseline in a 2 x 2 Train-Pairing x Test-Pairing Factorial
on Published Seed IDs `11` and `15` (diagnostic subset of `11-15`).

Locked protocol: STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md.
Pre-launch gates verified BEFORE running:
  1. ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json (`direct_pytorch_gate_pass_float64 == True`)
  2. STAGE3_SYNTHETIC_CHECK_RECEIPT.json (`all_checks_passed == True`)

CRITICAL ISOLATION GUARANTEE:
  - The prediction solver (`solve_single_highs`) receives ONLY:
    (a) evaluation row's known weights `W_te[i]`,
    (b) frozen model's PREDICTED capacity `cap_hat[i]`,
    (c) evaluation row's known costs `c_eval[i]`.
  - Evaluation row's TRUE capacity `cap_eval[i]` is used ONLY for:
    (a) true oracle solution `(x*_eval[i], obj*_eval[i])`,
    (b) realized feasibility check,
    (c) post-hoc repair and scoring.
  - NO gamma selection, NO margin tuning, NO thresholds: raw policy only.
  - Primary raw evaluation is unclipped (literal upstream solver behavior where negative predicted RHS
    yields `kInfeasible` / skip). When any negative predicted RHS occurs, a prediction-only `max(cap_hat, 0.0)`
    fallback (using ZERO true capacity) is also evaluated and documented alongside the unclipped result.
  - Treated strictly as a controlled adaptation (diagonal & cross-cells), NEVER reproduced paper scores.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import sys
import time
import types
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Tuple

import highspy
import numpy as np
import torch
from torch import nn
from ortools.sat.python import cp_model
from scipy import stats
from sklearn.model_selection import train_test_split

BASE = pathlib.Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
REPO = BASE / "official_odece_repo"

gp_stub = types.ModuleType("gurobipy")
gp_stub.GRB = types.SimpleNamespace(BINARY="B", MAXIMIZE=-1, OPTIMAL=2)
sys.modules["gurobipy"] = gp_stub
sys.path.insert(0, str(REPO))

from OptProblems.knapsack.kpdata import genCapacity  # type: ignore
from OptProblems.knapsack.kpsolver import knapsack_solver  # type: ignore
from ML.TorchML import LinearRegressionforKP_PredCapacity  # type: ignore
from src.odece import ODECE  # type: ignore

SEEDS = [11, 15]
ALPHA = 0.5
MARGIN = 2.0
LR = 0.005
BATCH_SIZE = 32
MAX_EPOCHS = 20
N_WORKERS = 14
_SCALE = 10000

_CPSAT_STATUS_NAMES = {
    cp_model.OPTIMAL: "OPTIMAL",
    cp_model.FEASIBLE: "FEASIBLE_NONOPTIMAL",
    cp_model.INFEASIBLE: "INFEASIBLE",
    cp_model.MODEL_INVALID: "MODEL_INVALID",
    cp_model.UNKNOWN: "UNKNOWN",
}

_LOWER = np.zeros(50, dtype=np.float64)
_UPPER = np.ones(50, dtype=np.float64)
_COL_IDX = np.arange(50, dtype=np.int32)
_VTYPE = np.full(50, highspy.HighsVarType.kInteger)
_ROW_LO = np.full(3, -highspy.kHighsInf, dtype=np.float64)
_INDPTR = np.array([0, 50, 100, 150], dtype=np.int32)
_INDICES = np.tile(np.arange(50, dtype=np.int32), 3)


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sha256_arrays(*arrs: np.ndarray) -> str:
    h = hashlib.sha256()
    for a in arrs:
        c = np.ascontiguousarray(a)
        h.update(str(c.shape).encode("utf-8"))
        h.update(str(c.dtype).encode("utf-8"))
        h.update(c.tobytes())
    return h.hexdigest()


def solve_single_cpsat(args: Tuple[np.ndarray, np.ndarray, np.ndarray, float]) -> Tuple[str, np.ndarray, float]:
    """Solves 0-1 MDKP using ONLY (w_mat, cap_vec, cost_vec)."""
    w_mat, cap_vec, cost_vec, time_lim = args
    if np.any(cap_vec < 0.0):
        return "INFEASIBLE", np.zeros(50, dtype=np.float64), float("nan")
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
        return st_name, sol, float(np.dot(cost_vec, sol))
    return st_name, np.zeros(50, dtype=np.float64), float("nan")


def solve_single_highs(args: Tuple[np.ndarray, np.ndarray, np.ndarray, float]) -> Tuple[str, np.ndarray, float, float, float]:
    """Solves 0-1 MDKP in float64 HiGHS using ONLY (w_mat, cap_vec, cost_vec).
    NOTE: `kOptimal` refers to HiGHS solver tolerance (`mip_rel_gap = 1e-4`).
    """
    w_mat, cap_vec, cost_vec, time_lim = args
    if np.any(cap_vec < 0.0):
        return "kInfeasible", np.zeros(50, dtype=np.float64), float("nan"), float("nan"), float("nan")
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


def batch_solve_cpsat(pool: ProcessPoolExecutor, W: np.ndarray, cap: np.ndarray, costs: np.ndarray, time_lim: float = 2.0) -> Dict:
    t0 = time.perf_counter()
    tasks = [(W[i], cap[i], costs[i], time_lim) for i in range(len(W))]
    res = list(pool.map(solve_single_cpsat, tasks, chunksize=max(1, len(tasks) // 28)))
    dt = time.perf_counter() - t0
    statuses = [r[0] for r in res]
    sols = np.stack([r[1] for r in res], axis=0)
    objs = np.array([r[2] for r in res], dtype=np.float64)
    sc: Dict[str, int] = {}
    for s in statuses:
        sc[s] = sc.get(s, 0) + 1
    ok = np.array([s in ("OPTIMAL", "FEASIBLE_NONOPTIMAL") for s in statuses], dtype=bool)
    return {"n_calls": len(W), "wall_time_s": dt, "status_counts": sc, "ok_mask": ok, "statuses": statuses, "sols": sols, "objs": objs}


def batch_solve_highs(pool: ProcessPoolExecutor, W: np.ndarray, cap: np.ndarray, costs: np.ndarray, time_lim: float = 5.0) -> Dict:
    t0 = time.perf_counter()
    tasks = [(W[i], cap[i], costs[i], time_lim) for i in range(len(W))]
    res = list(pool.map(solve_single_highs, tasks, chunksize=max(1, len(tasks) // 28)))
    dt = time.perf_counter() - t0
    statuses = [r[0] for r in res]
    sols = np.stack([r[1] for r in res], axis=0)
    objs = np.array([r[2] for r in res], dtype=np.float64)
    gaps = np.array([r[3] for r in res], dtype=np.float64)
    int_errs = np.array([r[4] for r in res], dtype=np.float64)
    sc: Dict[str, int] = {}
    for s in statuses:
        sc[s] = sc.get(s, 0) + 1
    ok = np.array([s in ("kOptimal", "kTimeLimit") for s in statuses], dtype=bool)
    return {
        "n_calls": len(W), "wall_time_s": dt, "status_counts": sc,
        "max_mip_gap": float(np.nanmax(gaps)) if np.any(np.isfinite(gaps)) else float("nan"),
        "max_integrality_err": float(np.nanmax(int_errs)) if np.any(np.isfinite(int_errs)) else float("nan"),
        "ok_mask": ok, "statuses": statuses, "sols": sols, "objs": objs,
    }


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
        x[sel[int(np.argmin(scores))]] = 0.0
    assert np.all((w_true @ x) <= cap_true)
    return x


def evaluate_decisions_stage3(
    W_true: np.ndarray,
    cap_true: np.ndarray,
    costs_true: np.ndarray,
    true_objs: np.ndarray,
    cap_pred: np.ndarray,
    sols: np.ndarray,
    ok_mask: np.ndarray,
    statuses: List[str],
    mse_cell_mean: float,
) -> Tuple[Dict, List[Dict]]:
    """
    Computes BOTH:
      (1) Source-defined metrics (`src/pfl.py:L321-382` exact definitions, instance-level pooled with explicit denominators):
          - source_raw_infeas_rate = n_infeas_solved / n_solved (skips excluded from denominator!)
          - source_feas_only_regret = mean((t_obj - real_obj) / t_obj) over n_strict_feasible
          - unsolvable_skip_count / rate
      (2) All-instance strict metrics (`denom = N = 500`):
          - strict_01_risk_all = (n_infeas_solved + n_unsolvable) / N
          - all_instance_int_repair_p1 (and p021), all_instance_frac_surr_p1 (and p021),
            with unsolvable instances assigned empty-knapsack normalized loss 1.0.
    """
    N = len(W_true)
    per_inst = []
    feas_regrets = []
    fp1_l, fp021_l, ip1_l, ip021_l = [], [], [], []
    n_solved = 0
    n_infeas_solved = 0
    n_strict_feasible = 0
    n_unsolvable = 0

    for i in range(N):
        t_obj = float(true_objs[i])
        if not ok_mask[i]:
            n_unsolvable += 1
            fp1 = fp021 = ip1 = ip021 = 1.0
            per_inst.append({
                "idx": i,
                "status": statuses[i],
                "solved": False,
                "unsolvable": True,
                "strict_01_feasible": False,
                "source_infeas_flag": None,
                "source_feas_regret": None,
                "frac_p1": 1.0,
                "frac_p021": 1.0,
                "int_p1": 1.0,
                "int_p021": 1.0,
            })
        else:
            n_solved += 1
            x = np.round(sols[i]).astype(np.float64)
            usage = W_true[i] @ x
            viol = usage - cap_true[i]
            strict_feas = bool(np.all(viol <= 0.0))
            real_obj = float(np.dot(costs_true[i], x))
            raw_reg = (t_obj - real_obj) / t_obj
            if strict_feas:
                n_strict_feasible += 1
                feas_regrets.append(raw_reg)
                fp1 = fp021 = ip1 = ip021 = raw_reg
                per_inst.append({
                    "idx": i,
                    "status": statuses[i],
                    "solved": True,
                    "unsolvable": False,
                    "strict_01_feasible": True,
                    "source_infeas_flag": 0,
                    "source_feas_regret": float(raw_reg),
                    "frac_p1": float(fp1),
                    "frac_p021": float(fp021),
                    "int_p1": float(ip1),
                    "int_p021": float(ip021),
                })
            else:
                n_infeas_solved += 1
                max_tau = float(max(1.0, np.max(usage / cap_true[i])))
                corr_frac = float(np.dot(costs_true[i], x / max_tau))
                fp1 = (t_obj - corr_frac) / t_obj + 1.0 * abs(real_obj - corr_frac) / t_obj
                fp021 = (t_obj - corr_frac) / t_obj + 0.21 * abs(real_obj - corr_frac) / t_obj
                x_int = greedy_strict_01_integer_repair(W_true[i], cap_true[i], costs_true[i], x)
                corr_int = float(np.dot(costs_true[i], x_int))
                ip1 = (t_obj - corr_int) / t_obj + 1.0 * abs(real_obj - corr_int) / t_obj
                ip021 = (t_obj - corr_int) / t_obj + 0.21 * abs(real_obj - corr_int) / t_obj
                per_inst.append({
                    "idx": i,
                    "status": statuses[i],
                    "solved": True,
                    "unsolvable": False,
                    "strict_01_feasible": False,
                    "source_infeas_flag": 1,
                    "source_feas_regret": None,
                    "frac_p1": float(fp1),
                    "frac_p021": float(fp021),
                    "int_p1": float(ip1),
                    "int_p021": float(ip021),
                })
        fp1_l.append(fp1); fp021_l.append(fp021); ip1_l.append(ip1); ip021_l.append(ip021)

    cap_mse = float(np.mean((cap_pred - cap_true) ** 2))
    n_dims = cap_true.shape[1]
    corrs = [
        float(np.corrcoef(cap_true[:, d], cap_pred[:, d])[0, 1])
        if np.std(cap_true[:, d]) > 0 and np.std(cap_pred[:, d]) > 0
        else float("nan")
        for d in range(n_dims)
    ]
    n_strict_fail_all = n_infeas_solved + n_unsolvable
    return {
        "n_total": N,
        "n_solved": n_solved,
        "unsolvable_skip_count": n_unsolvable,
        "unsolvable_skip_rate": float(n_unsolvable / N),
        "source_raw_infeas_num": n_infeas_solved,
        "source_raw_infeas_denom": n_solved,
        "source_raw_infeas_rate": float(n_infeas_solved / n_solved) if n_solved > 0 else float("nan"),
        "source_feas_only_regret_denom": n_strict_feasible,
        "source_feas_only_regret": float(np.mean(feas_regrets)) if n_strict_feasible > 0 else float("nan"),
        "strict_01_risk_all_num": n_strict_fail_all,
        "strict_01_risk_all_denom": N,
        "strict_01_risk_all": float(n_strict_fail_all / N),
        "strict_01_feasible_count": n_strict_feasible,
        "all_instance_int_repair_p1": float(np.mean(ip1_l)),
        "all_instance_int_repair_p021": float(np.mean(ip021_l)),
        "all_instance_frac_surr_p1": float(np.mean(fp1_l)),
        "all_instance_frac_surr_p021": float(np.mean(fp021_l)),
        "capacity_mse": cap_mse,
        "capacity_oos_r2_vs_cell_mean": float(1.0 - cap_mse / mse_cell_mean),
        "capacity_pearson_r_per_dim": corrs,
        "pred_cap_min": float(np.min(cap_pred)),
        "pred_cap_mean": float(np.mean(cap_pred)),
        "true_cap_mean": float(np.mean(cap_true)),
    }, per_inst


def classify_dominance(odece_m: Dict, pfl_m: Dict) -> str:
    r_o, r_p = odece_m["strict_01_risk_all"], pfl_m["strict_01_risk_all"]
    l_o, l_p = odece_m["all_instance_int_repair_p1"], pfl_m["all_instance_int_repair_p1"]
    eps = 1e-12
    if (r_o <= r_p + eps and l_o <= l_p + eps) and (r_o < r_p - eps or l_o < l_p - eps):
        return "ODECE_dominates_risk_and_repair"
    if (r_p <= r_o + eps and l_p <= l_o + eps) and (r_p < r_o - eps or l_p < l_o - eps):
        return "PFL_dominates_risk_and_repair"
    if r_o < r_p - eps and l_o > l_p + eps:
        return "tradeoff_ODECE_lower_risk_higher_repair"
    if r_o > r_p + eps and l_o < l_p - eps:
        return "tradeoff_ODECE_higher_risk_lower_repair"
    return "tied"


def paired_method_gap(
    pa_odece: List[Dict],
    pb_pfl: List[Dict],
    odece_m: Dict,
    pfl_m: Dict,
    rng: np.random.Generator,
    n_boot: int = 10000,
) -> Dict:
    """Computes paired ODECE minus PFL/MSE gaps within an identical (train, test) cell."""
    n = len(pa_odece)
    idx = rng.integers(0, n, size=(n_boot, n))
    out: Dict = {
        "n_paired": n,
        "risk_repair_dominance": classify_dominance(odece_m, pfl_m),
        "source_raw_infeas_gap_odece_minus_pfl": {
            "odece_rate": odece_m["source_raw_infeas_rate"],
            "odece_num_denom": f"{odece_m['source_raw_infeas_num']}/{odece_m['source_raw_infeas_denom']}",
            "pfl_rate": pfl_m["source_raw_infeas_rate"],
            "pfl_num_denom": f"{pfl_m['source_raw_infeas_num']}/{pfl_m['source_raw_infeas_denom']}",
            "diff": float(odece_m["source_raw_infeas_rate"] - pfl_m["source_raw_infeas_rate"]),
        },
        "source_feas_only_regret_gap_odece_minus_pfl": {
            "odece_val": odece_m["source_feas_only_regret"],
            "odece_denom": odece_m["source_feas_only_regret_denom"],
            "pfl_val": pfl_m["source_feas_only_regret"],
            "pfl_denom": pfl_m["source_feas_only_regret_denom"],
            "diff_marginal": float(odece_m["source_feas_only_regret"] - pfl_m["source_feas_only_regret"]),
        },
    }
    # Intersection paired feasible-only regret (instances feasible for BOTH ODECE and PFL)
    both_feas_diffs = [
        ra["source_feas_regret"] - rb["source_feas_regret"]
        for ra, rb in zip(pa_odece, pb_pfl)
        if ra["source_feas_regret"] is not None and rb["source_feas_regret"] is not None
    ]
    out["source_feas_only_regret_gap_odece_minus_pfl"]["paired_both_feasible_denom"] = len(both_feas_diffs)
    out["source_feas_only_regret_gap_odece_minus_pfl"]["paired_both_feasible_mean_diff"] = (
        float(np.mean(both_feas_diffs)) if both_feas_diffs else float("nan")
    )

    for m in ["int_p1", "frac_p1", "int_p021", "frac_p021"]:
        va = np.array([r[m] for r in pa_odece], dtype=np.float64)
        vb = np.array([r[m] for r in pb_pfl], dtype=np.float64)
        diff = va - vb
        boot = diff[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        p_wil = float(stats.wilcoxon(diff).pvalue) if np.any(diff != 0.0) else 1.0
        out[m] = {
            "odece_mean": float(va.mean()),
            "pfl_mean": float(vb.mean()),
            "mean_diff_odece_minus_pfl": float(diff.mean()),
            "ci95_low": float(lo),
            "ci95_high": float(hi),
            "wilcoxon_p": p_wil,
        }
    ia = np.array([0.0 if r["strict_01_feasible"] else 1.0 for r in pa_odece], dtype=np.float64)
    ib = np.array([0.0 if r["strict_01_feasible"] else 1.0 for r in pb_pfl], dtype=np.float64)
    iboot = (ia - ib)[idx].mean(axis=1)
    ilo, ihi = np.percentile(iboot, [2.5, 97.5])
    n10 = int(np.sum((ia == 1.0) & (ib == 0.0)))
    n01 = int(np.sum((ia == 0.0) & (ib == 1.0)))
    p_mc = float(stats.binomtest(min(n10, n01), n10 + n01, 0.5).pvalue) if (n10 + n01) > 0 else 1.0
    out["strict_01_risk_all"] = {
        "odece_rate": float(ia.mean()),
        "pfl_rate": float(ib.mean()),
        "diff_odece_minus_pfl": float(ia.mean() - ib.mean()),
        "ci95_low": float(ilo),
        "ci95_high": float(ihi),
        "discordant_odece_only_fail": n10,
        "discordant_pfl_only_fail": n01,
        "mcnemar_exact_p": p_mc,
    }
    return out


def train_pfl_mse_arm(
    seed: int,
    arm_name: str,
    init_state_dict: dict,
    X_tr: np.ndarray,
    cap_tr_target: np.ndarray,
) -> Tuple[LinearRegressionforKP_PredCapacity, Dict]:
    """
    Exact upstream PFL/MSE training loop (`official_odece_repo/src/pfl.py:L137-197, 465-481`) in float64:
      - Model: LinearRegressionforKP_PredCapacity(10, 50, 3).double(), paired init_state_dict
      - Loss: nn.MSELoss() (reduction='mean') against capacity target
      - Optimizer: torch.optim.Adam(lr=0.005), NO gradient clipping (exact upstream PFL)
      - Budget: batch_size=32, max_epochs=20, identical minibatch permutation rng(seed + 1000)
      - Solver calls during training: 0
    """
    t0 = time.perf_counter()
    reg = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    reg.load_state_dict(copy.deepcopy(init_state_dict))
    criterion = nn.MSELoss()
    optimizer = torch.optim.Adam(reg.parameters(), lr=LR)
    rng = np.random.default_rng(seed + 1000)
    N = len(X_tr)
    epoch_logs = []
    n_batches = 0

    for ep in range(MAX_EPOCHS):
        order = rng.permutation(N)
        ep_losses = []
        reg.train()
        for s in range(0, N, BATCH_SIZE):
            idx = order[s : s + BATCH_SIZE]
            x_t = torch.tensor(X_tr[idx], dtype=torch.float64)
            cap_t = torch.tensor(cap_tr_target[idx], dtype=torch.float64)
            optimizer.zero_grad()
            loss = criterion(reg(x_t), cap_t)
            assert torch.isfinite(loss), f"Non-finite PFL loss at seed={seed} {arm_name} ep={ep}"
            loss.backward()
            optimizer.step()
            ep_losses.append(float(loss.item()))
            n_batches += 1
        epoch_logs.append({"epoch": ep + 1, "mean_mse_loss": float(np.mean(ep_losses))})

    reg.eval()
    print(
        f"  [Seed {seed} {arm_name}] PFL/MSE 20ep DONE | ep1_mse={epoch_logs[0]['mean_mse_loss']:.3f} -> ep20_mse={epoch_logs[-1]['mean_mse_loss']:.3f} ({time.perf_counter()-t0:.2f}s)",
        flush=True,
    )
    return reg, {
        "method": "PFL_MSE",
        "inloop_train_solves": 0,
        "train_wall_time_s": time.perf_counter() - t0,
        "n_batches": n_batches,
        "grad_clip": None,
        "epoch_logs": epoch_logs,
    }


def train_odece_arm(
    seed: int,
    arm_name: str,
    pool: ProcessPoolExecutor,
    init_state_dict: dict,
    X_tr: np.ndarray,
    W_tr: np.ndarray,
    cap_tr_target: np.ndarray,
    c_tr_target: np.ndarray,
    sols_tr: np.ndarray,
    objs_tr: np.ndarray,
) -> Tuple[LinearRegressionforKP_PredCapacity, Dict]:
    """
    Exact validated direct-PyTorch upstream ODECE(alpha=0.5) loop (`src/odece.py`) in float64
    with original MARGIN=2.0, clip_grad_norm_(0.5), Guard 1 (`empty_ipl`), and Guard 2 (`mask==0`).
    """
    t0 = time.perf_counter()
    reg = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    reg.load_state_dict(copy.deepcopy(init_state_dict))

    solver = knapsack_solver(50)
    odece_pl = ODECE(
        [reg], predict_indices=1, optsolver=solver, num_predconstrsvar=1,
        infeasibility_aversion_coeff=ALPHA, margin_threshold=MARGIN,
        predict_cost=False, lr=LR, max_epochs=MAX_EPOCHS, seed=seed,
    )
    odece_pl.log = lambda *args, **kwargs: None
    optimizer = torch.optim.Adam(reg.parameters(), lr=LR)

    rng = np.random.default_rng(seed + 1000)
    N = len(X_tr)
    status_counts: Dict[str, int] = {}
    inloop_solves = 0
    inloop_solver_t = 0.0
    n_batches = 0
    n_zero_infeas_batches = 0
    n_mask_zero_batches = 0
    n_true_sol_ulp_viols = 0
    epoch_logs = []

    for ep in range(MAX_EPOCHS):
        order = rng.permutation(N)
        ep_losses = []
        ep_ok = 0
        ep_z0 = 0
        ep_m0 = 0
        for s in range(0, N, BATCH_SIZE):
            idx = order[s : s + BATCH_SIZE]
            xb, wb, capb, cb = X_tr[idx], W_tr[idx], cap_tr_target[idx], c_tr_target[idx]
            solb, objb = sols_tr[idx], objs_tr[idx]

            x_t = torch.tensor(xb, dtype=torch.float64)
            w_t = torch.tensor(wb, dtype=torch.float64)
            cap_t = torch.tensor(capb, dtype=torch.float64)
            c_t = torch.tensor(cb, dtype=torch.float64)
            sol_t = torch.tensor(solb, dtype=torch.float64)
            obj_t = torch.tensor(objb[:, None], dtype=torch.float64)

            with torch.no_grad():
                cap_hat_np = reg(x_t).cpu().numpy()
                vt = int(solver.constraint_wise_feasibility((w_t, cap_t), sol_t).sum().item())
                n_true_sol_ulp_viols += vt

            bs = batch_solve_cpsat(pool, wb, cap_hat_np, cb, time_lim=2.0)
            inloop_solves += bs["n_calls"]
            inloop_solver_t += bs["wall_time_s"]
            for k, v in bs["status_counts"].items():
                status_counts[k] = status_counts.get(k, 0) + v

            ok_mask = bs["ok_mask"]
            ep_ok += int(ok_mask.sum())
            mask_t = torch.tensor(ok_mask, dtype=torch.bool)
            pred_sol_masked_t = torch.tensor(bs["sols"][ok_mask], dtype=torch.float64)

            reg.train()
            optimizer.zero_grad()
            trueConstr_tuple = (w_t, cap_t)
            pred_list = odece_pl.forward(x_t)
            pred_params_tuple, _ = odece_pl._create_params_tuple(pred_list, trueConstr_tuple, c_t)

            loss_ipl, loss_opl = odece_pl.losses_computation(
                trueConstr_tuple, pred_params_tuple, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t
            )

            n_batches += 1
            if mask_t.sum() == 0:
                n_mask_zero_batches += 1
                ep_m0 += 1
                prev_ipl = loss_ipl.mean()
                prev_opl = loss_opl.mean()
            else:
                prev_opl = loss_opl.mean()
                if loss_ipl.numel() == 0:
                    n_zero_infeas_batches += 1
                    ep_z0 += 1
                    prev_ipl = torch.zeros((), dtype=torch.float64)
                else:
                    prev_ipl = loss_ipl.mean()

            total_loss = ALPHA * (prev_ipl + 1e-4).mean() + (1.0 - ALPHA) * (prev_opl + 1e-4).mean()
            assert torch.isfinite(total_loss), f"Non-finite ODECE loss at seed={seed} {arm_name} ep={ep}"
            total_loss.backward()
            nn.utils.clip_grad_norm_(reg.parameters(), 0.5)
            optimizer.step()
            ep_losses.append(float(total_loss.item()))

        epoch_logs.append({
            "epoch": ep + 1, "mean_loss": float(np.mean(ep_losses)),
            "solvable_train_instances_of_900": ep_ok, "zero_infeas_batches": ep_z0, "mask_zero_batches": ep_m0,
        })
        if (ep + 1) in (1, 10, 20):
            print(
                f"  [Seed {seed} {arm_name}] ep={ep+1:2d}/20 | loss={np.mean(ep_losses):8.4f} | solvable={ep_ok:3d}/900 | z0={ep_z0:2d} | m0={ep_m0:2d}",
                flush=True,
            )

    reg.eval()
    return reg, {
        "method": "ODECE_a0.5",
        "inloop_train_solves": inloop_solves,
        "inloop_solver_time_s": inloop_solver_t,
        "train_wall_time_s": time.perf_counter() - t0,
        "train_status_counts": status_counts,
        "n_batches": n_batches,
        "grad_clip": 0.5,
        "n_zero_infeas_batches_guard1": n_zero_infeas_batches,
        "n_mask_zero_batches_guard2": n_mask_zero_batches,
        "n_true_sol_ulp_viols_observed": n_true_sol_ulp_viols,
        "epoch_logs": epoch_logs,
    }


def run_seed(pool: ProcessPoolExecutor, seed: int, source_hashes: Dict[str, str], pid: int) -> Dict:
    t_seed = time.perf_counter()
    out_dir = BASE / f"stage3_capacity_factorial_seed{seed}"
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n==================== STAGE-3 PUBLISHED SEED {seed} (PID={pid}) ====================", flush=True)

    # Exact published MDKP_CapaExp.sh data generation
    X, w, costs, capacity = genCapacity(
        num_data=1500, num_features=10, num_items=50, dim=3, deg=6, noise_width=0.25, fixed_cost=False, seed=seed
    )
    idx_all = np.arange(1500)
    idx_tr_full, idx_te = train_test_split(idx_all, test_size=500, random_state=seed)
    idx_tr, idx_va = train_test_split(idx_tr_full, test_size=0.1, random_state=seed)

    # Raw generated data SHA-256 hashes (exact reproducibility receipt)
    raw_data_hashes = {
        "X_sha256": sha256_arrays(X),
        "w_sha256": sha256_arrays(w),
        "costs_sha256": sha256_arrays(costs),
        "capacity_sha256": sha256_arrays(capacity),
        "split_indices_sha256": sha256_arrays(idx_tr, idx_va, idx_te),
    }

    # Fixed (X, w) scenario rows per split
    X_tr, W_tr = X[idx_tr], w[idx_tr]
    X_te, W_te = X[idx_te], w[idx_te]

    # Two train pipelines:
    #   1) Released_Positional: literal KnapsackCapaExp.py:L69-75 (positional capacity[:900] & costs[:900])
    #   2) Aligned_Joint: same row indices idx_tr applied to EVERY field
    cap_tr_rel, c_tr_rel = capacity[: len(idx_tr)], costs[: len(idx_tr)]
    cap_tr_aln, c_tr_aln = capacity[idx_tr], costs[idx_tr]

    # Two test data interpretations (fixed X_te, W_te scenario order):
    #   1) Test_Released_Positional: positional capacity[:500] & costs[:500]
    #   2) Test_Aligned_Joint: same row indices idx_te applied to capacity & costs
    cap_te_rel, c_te_rel = capacity[: len(idx_te)], costs[: len(idx_te)]
    cap_te_aln, c_te_aln = capacity[idx_te], costs[idx_te]

    matched_keys = {
        "train_Released_matched_rows": f"{int(np.sum(idx_tr == np.arange(len(idx_tr))))}/{len(idx_tr)}",
        "train_Aligned_matched_rows": f"{len(idx_tr)}/{len(idx_tr)}",
        "val_Released_matched_rows": f"{int(np.sum(idx_va == np.arange(len(idx_va))))}/{len(idx_va)}",
        "val_Aligned_matched_rows": f"{len(idx_va)}/{len(idx_va)}",
        "test_Released_matched_rows": f"{int(np.sum(idx_te == np.arange(len(idx_te))))}/{len(idx_te)}",
        "test_Aligned_matched_rows": f"{len(idx_te)}/{len(idx_te)}",
        "test_indices_overlapping_train_prefix_0_899": f"{int(np.sum(idx_te < len(idx_tr)))}/{len(idx_te)}",
        "test_Released_prefix_0_499_subset_of_train_prefix_0_899": "500/500",
    }
    print(f"  Matched keys: train_Rel={matched_keys['train_Released_matched_rows']}, test_Rel={matched_keys['test_Released_matched_rows']}, train/test_Aln=100%", flush=True)

    # Paired identical float64 initialization across all 4 models per seed
    torch.manual_seed(seed)
    init_model = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    init_state = copy.deepcopy(init_model.state_dict())
    init_ckpt_path = out_dir / "paired_init_weights.json"
    init_ckpt_path.write_text(
        json.dumps({"weight": init_state["linear.weight"].tolist(), "bias": init_state["linear.bias"].tolist()}, indent=2),
        encoding="utf-8",
    )

    cpsat_total = 0
    highs_total = 0

    # Offline training oracles for ODECE (CP-SAT) & offline test oracles for BOTH test interpretations (HiGHS float64)
    off_tr_rel = batch_solve_cpsat(pool, W_tr, cap_tr_rel, c_tr_rel, time_lim=5.0)
    off_tr_aln = batch_solve_cpsat(pool, W_tr, cap_tr_aln, c_tr_aln, time_lim=5.0)
    cpsat_total += off_tr_rel["n_calls"] + off_tr_aln["n_calls"]
    assert off_tr_rel["status_counts"] == {"OPTIMAL": 900}, f"off_tr_rel not 900 OPT: {off_tr_rel['status_counts']}"
    assert off_tr_aln["status_counts"] == {"OPTIMAL": 900}, f"off_tr_aln not 900 OPT: {off_tr_aln['status_counts']}"

    off_te_rel = batch_solve_highs(pool, W_te, cap_te_rel, c_te_rel, time_lim=5.0)
    off_te_aln = batch_solve_highs(pool, W_te, cap_te_aln, c_te_aln, time_lim=5.0)
    highs_total += off_te_rel["n_calls"] + off_te_aln["n_calls"]
    assert off_te_rel["status_counts"] == {"kOptimal": 500}, f"off_te_rel not 500 kOptimal: {off_te_rel['status_counts']}"
    assert off_te_aln["status_counts"] == {"kOptimal": 500}, f"off_te_aln not 500 kOptimal: {off_te_aln['status_counts']}"
    print(
        f"  Offline oracles: tr_Rel=900 OPT, tr_Aln=900 OPT | test_Rel_HiGHS=500 kOpt (gap={off_te_rel['max_mip_gap']:.2e}), "
        f"test_Aln_HiGHS=500 kOpt (gap={off_te_aln['max_mip_gap']:.2e})",
        flush=True,
    )

    # Train 4 frozen models: {PFL, ODECE} x {Released, Aligned}
    models: Dict[Tuple[str, str], LinearRegressionforKP_PredCapacity] = {}
    train_audits: Dict[str, Dict] = {}
    ckpt_hashes: Dict[str, str] = {"paired_init_weights_json": sha256_file(init_ckpt_path)}

    for train_mode, cap_tr, c_tr, off_tr in [
        ("Released", cap_tr_rel, c_tr_rel, off_tr_rel),
        ("Aligned", cap_tr_aln, c_tr_aln, off_tr_aln),
    ]:
        # 1) PFL/MSE
        m_pfl, tr_pfl = train_pfl_mse_arm(seed, f"PFL_{train_mode}", init_state, X_tr, cap_tr)
        models[("PFL", train_mode)] = m_pfl
        train_audits[f"PFL_{train_mode}"] = tr_pfl
        p_ckpt = out_dir / f"final_weights_PFL_{train_mode}.json"
        p_ckpt.write_text(json.dumps({"weight": m_pfl.linear.weight.detach().tolist(), "bias": m_pfl.linear.bias.detach().tolist()}, indent=2), encoding="utf-8")
        ckpt_hashes[p_ckpt.name] = sha256_file(p_ckpt)

        # 2) ODECE(alpha=0.5)
        m_od, tr_od = train_odece_arm(seed, f"ODECE_{train_mode}", pool, init_state, X_tr, W_tr, cap_tr, c_tr, off_tr["sols"], off_tr["objs"])
        cpsat_total += tr_od["inloop_train_solves"]
        models[("ODECE", train_mode)] = m_od
        train_audits[f"ODECE_{train_mode}"] = tr_od
        o_ckpt = out_dir / f"final_weights_ODECE_{train_mode}.json"
        o_ckpt.write_text(json.dumps({"weight": m_od.linear.weight.detach().tolist(), "bias": m_od.linear.bias.detach().tolist()}, indent=2), encoding="utf-8")
        ckpt_hashes[o_ckpt.name] = sha256_file(o_ckpt)

    # Frozen predictions on fixed X_te (depends ONLY on X_te!)
    preds_te: Dict[Tuple[str, str], np.ndarray] = {}
    X_te_t = torch.tensor(X_te, dtype=torch.float64)
    with torch.no_grad():
        for key, mod in models.items():
            preds_te[key] = mod(X_te_t).cpu().numpy()

    # Evaluate 2 x 2 factorial cells: (train_mode, test_mode)
    test_specs = {
        "Released": {
            "cap_eval": cap_te_rel,
            "c_eval": c_te_rel,
            "oracle": off_te_rel,
            "mse_cell_mean": float(np.mean((cap_te_rel - cap_te_rel.mean(axis=0, keepdims=True)) ** 2)),
        },
        "Aligned": {
            "cap_eval": cap_te_aln,
            "c_eval": c_te_aln,
            "oracle": off_te_aln,
            "mse_cell_mean": float(np.mean((cap_te_aln - cap_te_aln.mean(axis=0, keepdims=True)) ** 2)),
        },
    }

    factorial_cells: Dict[str, Dict] = {}
    rng_stat = np.random.default_rng(2026112430 + seed)

    for train_mode in ["Released", "Aligned"]:
        for test_mode in ["Released", "Aligned"]:
            cell_id = f"Train_{train_mode}__Test_{test_mode}"
            ts = test_specs[test_mode]
            cap_eval = ts["cap_eval"]
            c_eval = ts["c_eval"]
            oracle_objs = ts["oracle"]["objs"]
            mse_cell_mean = ts["mse_cell_mean"]

            cell_arms_unclip: Dict[str, Dict] = {}
            cell_pi_unclip: Dict[str, List[Dict]] = {}
            cell_arms_zeroclip: Dict[str, Dict] = {}
            cell_pi_zeroclip: Dict[str, List[Dict]] = {}

            for method in ["PFL", "ODECE"]:
                cap_hat = preds_te[(method, train_mode)]
                n_neg_dims = int(np.sum(cap_hat < 0.0))
                n_neg_rows = int(np.sum(np.any(cap_hat < 0.0, axis=1)))

                # PRIMARY RAW UNCLIPPED SOLVE: passes ONLY (W_te, cap_hat, c_eval) -- NEVER cap_eval!
                sh_u = batch_solve_highs(pool, W_te, cap_hat, c_eval, time_lim=5.0)
                highs_total += sh_u["n_calls"]
                m_u, pi_u = evaluate_decisions_stage3(
                    W_te, cap_eval, c_eval, oracle_objs, cap_hat, sh_u["sols"], sh_u["ok_mask"], sh_u["statuses"], mse_cell_mean
                )
                pi_u_path = out_dir / f"per_instance_highs_{method}_{cell_id}_unclipped.json"
                pi_u_path.write_text(json.dumps(pi_u), encoding="utf-8")

                cell_arms_unclip[method] = {
                    "metrics": m_u,
                    "n_neg_pred_dims": n_neg_dims,
                    "n_neg_pred_rows": n_neg_rows,
                    "highs_status_counts": sh_u["status_counts"],
                    "highs_max_mip_gap": sh_u["max_mip_gap"],
                    "highs_max_integrality_err": sh_u["max_integrality_err"],
                    "per_instance_sha256": sha256_file(pi_u_path),
                }
                cell_pi_unclip[method] = pi_u

                # SECONDARY PREDICTION-ONLY ZERO-CLIP FALLBACK: max(cap_hat, 0.0) uses ZERO true capacity!
                if n_neg_rows == 0:
                    cell_arms_zeroclip[method] = {**cell_arms_unclip[method], "fallback_triggered": False}
                    cell_pi_zeroclip[method] = pi_u
                else:
                    cap_hat_clip = np.clip(cap_hat, 0.0, None)
                    sh_c = batch_solve_highs(pool, W_te, cap_hat_clip, c_eval, time_lim=5.0)
                    highs_total += sh_c["n_calls"]
                    m_c, pi_c = evaluate_decisions_stage3(
                        W_te, cap_eval, c_eval, oracle_objs, cap_hat_clip, sh_c["sols"], sh_c["ok_mask"], sh_c["statuses"], mse_cell_mean
                    )
                    pi_c_path = out_dir / f"per_instance_highs_{method}_{cell_id}_zeroclip_fallback.json"
                    pi_c_path.write_text(json.dumps(pi_c), encoding="utf-8")
                    cell_arms_zeroclip[method] = {
                        "metrics": m_c,
                        "n_neg_pred_dims_clipped": n_neg_dims,
                        "n_neg_pred_rows_clipped": n_neg_rows,
                        "fallback_triggered": True,
                        "highs_status_counts": sh_c["status_counts"],
                        "highs_max_mip_gap": sh_c["max_mip_gap"],
                        "highs_max_integrality_err": sh_c["max_integrality_err"],
                        "per_instance_sha256": sha256_file(pi_c_path),
                    }
                    cell_pi_zeroclip[method] = pi_c

            gap_unclip = paired_method_gap(
                cell_pi_unclip["ODECE"], cell_pi_unclip["PFL"],
                cell_arms_unclip["ODECE"]["metrics"], cell_arms_unclip["PFL"]["metrics"], rng_stat
            )
            gap_zeroclip = paired_method_gap(
                cell_pi_zeroclip["ODECE"], cell_pi_zeroclip["PFL"],
                cell_arms_zeroclip["ODECE"]["metrics"], cell_arms_zeroclip["PFL"]["metrics"], rng_stat
            )

            factorial_cells[cell_id] = {
                "train_pairing": train_mode,
                "test_pairing": test_mode,
                "raw_unclipped_primary": {
                    "PFL": cell_arms_unclip["PFL"],
                    "ODECE": cell_arms_unclip["ODECE"],
                    "method_gap_ODECE_minus_PFL": gap_unclip,
                },
                "pred_only_zeroclip_fallback": {
                    "PFL": cell_arms_zeroclip["PFL"],
                    "ODECE": cell_arms_zeroclip["ODECE"],
                    "method_gap_ODECE_minus_PFL": gap_zeroclip,
                },
            }

            po, pp = cell_arms_unclip["ODECE"]["metrics"], cell_arms_unclip["PFL"]["metrics"]
            print(
                f"  [{cell_id:29s}] "
                f"PFL: src_inf={pp['source_raw_infeas_rate']*100:5.1f}%({pp['source_raw_infeas_num']}/{pp['source_raw_infeas_denom']}) "
                f"feas_reg={pp['source_feas_only_regret']*100:5.2f}%({pp['source_feas_only_regret_denom']}) "
                f"risk={pp['strict_01_risk_all']*100:5.1f}% int_p1={pp['all_instance_int_repair_p1']*100:5.2f}% skip={pp['unsolvable_skip_count']} | "
                f"ODECE: src_inf={po['source_raw_infeas_rate']*100:5.1f}%({po['source_raw_infeas_num']}/{po['source_raw_infeas_denom']}) "
                f"feas_reg={po['source_feas_only_regret']*100:5.2f}%({po['source_feas_only_regret_denom']}) "
                f"risk={po['strict_01_risk_all']*100:5.1f}% int_p1={po['all_instance_int_repair_p1']*100:5.2f}% skip={po['unsolvable_skip_count']} | "
                f"DOM={gap_unclip['risk_repair_dominance']}",
                flush=True,
            )

    summary = {
        "protocol": "STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md",
        "real_pid": pid,
        "torch_version": torch.__version__,
        "seed": seed,
        "output_dir": str(out_dir),
        "hyperparams": {"alpha": ALPHA, "margin": MARGIN, "lr": LR, "batch_size": BATCH_SIZE, "max_epochs": MAX_EPOCHS, "highs_mip_rel_gap": 1e-4},
        "source_hashes": source_hashes,
        "raw_data_hashes": raw_data_hashes,
        "checkpoint_hashes": ckpt_hashes,
        "matched_keys": matched_keys,
        "offline_audit": {
            "train_Released_cpsat": {"calls": off_tr_rel["n_calls"], "status_counts": off_tr_rel["status_counts"]},
            "train_Aligned_cpsat": {"calls": off_tr_aln["n_calls"], "status_counts": off_tr_aln["status_counts"]},
            "test_Released_highs": {
                "calls": off_te_rel["n_calls"], "status_counts": off_te_rel["status_counts"],
                "max_mip_gap": off_te_rel["max_mip_gap"], "max_integrality_err": off_te_rel["max_integrality_err"],
            },
            "test_Aligned_highs": {
                "calls": off_te_aln["n_calls"], "status_counts": off_te_aln["status_counts"],
                "max_mip_gap": off_te_aln["max_mip_gap"], "max_integrality_err": off_te_aln["max_integrality_err"],
            },
        },
        "train_audits": train_audits,
        "total_cpsat_calls": cpsat_total,
        "total_highs_float64_calls": highs_total,
        "seed_wall_time_s": time.perf_counter() - t_seed,
        "factorial_cells": factorial_cells,
    }
    sum_path = out_dir / f"stage3_seed{seed}_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main():
    t_all = time.perf_counter()
    pid = os.getpid()

    # HARD PRE-LAUNCH GATES
    gate_path = BASE / "ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json"
    assert gate_path.exists() and json.loads(gate_path.read_text(encoding="utf-8")).get("direct_pytorch_gate_pass_float64") is True

    syn_path = BASE / "STAGE3_SYNTHETIC_CHECK_RECEIPT.json"
    assert syn_path.exists() and json.loads(syn_path.read_text(encoding="utf-8")).get("all_checks_passed") is True

    proto_path = BASE / "STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md"
    assert proto_path.exists(), f"Missing locked Stage-3 protocol: {proto_path}"

    source_hashes = {
        "official_KnapsackCapaExp_py": sha256_file(REPO / "KnapsackCapaExp.py"),
        "official_MDKP_CapaExp_sh": sha256_file(REPO / "MDKP_CapaExp.sh"),
        "official_src_pfl_py": sha256_file(REPO / "src" / "pfl.py"),
        "official_src_odece_py": sha256_file(REPO / "src" / "odece.py"),
        "official_kpdataset_py": sha256_file(REPO / "OptProblems" / "knapsack" / "kpdataset.py"),
        "official_kpsolver_py": sha256_file(REPO / "OptProblems" / "knapsack" / "kpsolver.py"),
        "official_kpdata_py": sha256_file(REPO / "OptProblems" / "knapsack" / "kpdata.py"),
        "official_TorchML_py": sha256_file(REPO / "ML" / "TorchML.py"),
        "ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT_json": sha256_file(gate_path),
        "STAGE3_SYNTHETIC_CHECK_RECEIPT_json": sha256_file(syn_path),
        "STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL_md": sha256_file(proto_path),
        "stage3_capacity_pfl_vs_odece_factorial_py": sha256_file(pathlib.Path(__file__)),
    }

    print(f"=== Stage-3 Capacity 2x2 Factorial: ODECE(a=0.5) vs PFL/MSE on Published Seeds {SEEDS} (PID={pid}) ===", flush=True)
    seed_summaries = []
    with ProcessPoolExecutor(max_workers=N_WORKERS) as pool:
        for seed in SEEDS:
            seed_summaries.append(run_seed(pool, seed, source_hashes, pid))

    agg = {
        "protocol": "STAGE3_CAPACITY_PFL_VS_ODECE_PROTOCOL.md",
        "real_pid": pid,
        "seeds_diagnostic_subset_of_11_15": SEEDS,
        "total_cpsat_calls": sum(ss["total_cpsat_calls"] for ss in seed_summaries),
        "total_highs_calls": sum(ss["total_highs_float64_calls"] for ss in seed_summaries),
        "total_wall_time_s": time.perf_counter() - t_all,
        "source_hashes": source_hashes,
        "per_seed_summaries": {str(ss["seed"]): ss for ss in seed_summaries},
    }
    agg_path = BASE / "stage3_capacity_factorial_summary.json"
    agg_path.write_text(json.dumps(agg, indent=2), encoding="utf-8")
    print(f"\n=== Stage-3 COMPLETE (PID={pid}, wall={agg['total_wall_time_s']:.1f}s) | Saved {agg_path} ===", flush=True)


if __name__ == "__main__":
    main()
