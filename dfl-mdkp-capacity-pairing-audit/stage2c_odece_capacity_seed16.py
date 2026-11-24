"""
Stage-2c Locked Mechanism Confirmation: ACTUAL Pinned Upstream PyTorch `src/odece.py`
on MDKP-Capacity (`alpha=0.5`, fresh seed=16; reserved seeds 17-18 untouched).

Locked protocol: STAGE2C_ODECE_CAPACITY_PROTOCOL.md.
Pre-launch parity receipt: ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT.json.

Calls ACTUAL unmodified `official_odece_repo/src/odece.py` (`ODECE.losses_computation`),
`OptProblems/knapsack/kpsolver.py` (`knapsack_solver`), and `ML/TorchML.py`
(`LinearRegressionforKP_PredCapacity`) directly in `torch.float64` with documented guards:
  - Guard 1: empty `violation_pred_mask` (`loss_ipl.numel() == 0`) -> `prev_ipl = 0.0`
  - Guard 2: `mask.sum() == 0` -> unmodified `src/odece.py:L95-106` (symmetric at alpha=0.5)
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
OUT_DIR = BASE / "stage2c_odece_capacity_seed16"

# Stub gurobipy ONLY for module top-level import in kpsolver.py; kpsolver.solve() is NOT called.
gp_stub = types.ModuleType("gurobipy")
gp_stub.GRB = types.SimpleNamespace(BINARY="B", MAXIMIZE=-1, OPTIMAL=2)
sys.modules["gurobipy"] = gp_stub
sys.path.insert(0, str(REPO))

from OptProblems.knapsack.kpdata import genCapacity  # type: ignore
from OptProblems.knapsack.kpsolver import knapsack_solver  # type: ignore
from ML.TorchML import LinearRegressionforKP_PredCapacity  # type: ignore
from src.odece import ODECE  # type: ignore

SEED = 16
RESERVED_SEEDS = [17, 18]
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


def solve_single_cpsat(args: Tuple[np.ndarray, np.ndarray, np.ndarray, float]) -> Tuple[str, np.ndarray, float]:
    w_mat, cap_vec, cost_vec, time_lim = args
    # If any predicted RHS capacity is strictly negative with positive weights w >= 1.0,
    # problem is genuinely INFEASIBLE (exact match to Gurobi INFEASIBLE -> mask[b]=False).
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


def evaluate_decisions(
    W_true: np.ndarray, cap_true: np.ndarray, costs_true: np.ndarray, true_objs: np.ndarray,
    cap_pred: np.ndarray, sols: np.ndarray, ok_mask: np.ndarray, statuses: List[str], mse_shared_mean: float
) -> Tuple[Dict, List[Dict]]:
    N = len(W_true)
    per_inst = []
    feas_regrets = []
    fp1_l, fp021_l, ip1_l, ip021_l = [], [], [], []
    n_infeas = 0
    n_unsolvable = 0
    for i in range(N):
        t_obj = float(true_objs[i])
        if not ok_mask[i]:
            n_unsolvable += 1
            n_infeas += 1
            fp1 = fp021 = ip1 = ip021 = 1.0
            per_inst.append({"idx": i, "status": statuses[i], "strict_01_feasible": False, "unsolvable": True, "frac_p1": 1.0, "frac_p021": 1.0, "int_p1": 1.0, "int_p021": 1.0})
        else:
            x = np.round(sols[i]).astype(np.float64)
            usage = W_true[i] @ x
            viol = usage - cap_true[i]
            strict_feas = bool(np.all(viol <= 0.0))
            real_obj = float(np.dot(costs_true[i], x))
            raw_reg = (t_obj - real_obj) / t_obj
            if strict_feas:
                feas_regrets.append(raw_reg)
                fp1 = fp021 = ip1 = ip021 = raw_reg
            else:
                n_infeas += 1
                max_tau = float(max(1.0, np.max(usage / cap_true[i])))
                corr_frac = float(np.dot(costs_true[i], x / max_tau))
                fp1 = (t_obj - corr_frac) / t_obj + 1.0 * abs(real_obj - corr_frac) / t_obj
                fp021 = (t_obj - corr_frac) / t_obj + 0.21 * abs(real_obj - corr_frac) / t_obj
                x_int = greedy_strict_01_integer_repair(W_true[i], cap_true[i], costs_true[i], x)
                corr_int = float(np.dot(costs_true[i], x_int))
                ip1 = (t_obj - corr_int) / t_obj + 1.0 * abs(real_obj - corr_int) / t_obj
                ip021 = (t_obj - corr_int) / t_obj + 0.21 * abs(real_obj - corr_int) / t_obj
            per_inst.append({"idx": i, "status": statuses[i], "strict_01_feasible": strict_feas, "unsolvable": False, "frac_p1": float(fp1), "frac_p021": float(fp021), "int_p1": float(ip1), "int_p021": float(ip021)})
        fp1_l.append(fp1); fp021_l.append(fp021); ip1_l.append(ip1); ip021_l.append(ip021)

    cap_mse = float(np.mean((cap_pred - cap_true) ** 2))
    corrs = [float(np.corrcoef(cap_true[:, d], cap_pred[:, d])[0, 1]) if np.std(cap_true[:, d]) > 0 and np.std(cap_pred[:, d]) > 0 else float("nan") for d in range(3)]
    return {
        "strict_01_infeasibility_rate": float(n_infeas / N),
        "strict_01_feasible_count": int(N - n_infeas),
        "unsolvable_rate": float(n_unsolvable / N),
        "strict_01_feasible_regret": float(np.mean(feas_regrets)) if feas_regrets else float("nan"),
        "official_frac_surrogate_posthoc_p1": float(np.mean(fp1_l)),
        "official_frac_surrogate_posthoc_p021": float(np.mean(fp021_l)),
        "strict_01_int_repair_posthoc_p1": float(np.mean(ip1_l)),
        "strict_01_int_repair_posthoc_p021": float(np.mean(ip021_l)),
        "capacity_mse": cap_mse,
        "capacity_oos_r2_vs_shared_mean": float(1.0 - cap_mse / mse_shared_mean),
        "capacity_pearson_r_per_dim": corrs,
    }, per_inst


def paired_compare(pa: List[Dict], pb: List[Dict], rng: np.random.Generator, n_boot: int = 10000) -> Dict:
    n = len(pa)
    idx = rng.integers(0, n, size=(n_boot, n))
    out: Dict = {"n_paired": n}
    for m in ["frac_p1", "int_p1", "frac_p021", "int_p021"]:
        va = np.array([r[m] for r in pa], dtype=np.float64)
        vb = np.array([r[m] for r in pb], dtype=np.float64)
        diff = va - vb
        boot = diff[idx].mean(axis=1)
        lo, hi = np.percentile(boot, [2.5, 97.5])
        p_wil = float(stats.wilcoxon(diff).pvalue) if np.any(diff != 0.0) else 1.0
        out[m] = {"mean_a": float(va.mean()), "mean_b": float(vb.mean()), "mean_diff": float(diff.mean()), "ci95_low": float(lo), "ci95_high": float(hi), "wilcoxon_p": p_wil}
    ia = np.array([0.0 if r["strict_01_feasible"] else 1.0 for r in pa], dtype=np.float64)
    ib = np.array([0.0 if r["strict_01_feasible"] else 1.0 for r in pb], dtype=np.float64)
    iboot = (ia - ib)[idx].mean(axis=1)
    ilo, ihi = np.percentile(iboot, [2.5, 97.5])
    n10 = int(np.sum((ia == 1.0) & (ib == 0.0)))
    n01 = int(np.sum((ia == 0.0) & (ib == 1.0)))
    p_mc = float(stats.binomtest(min(n10, n01), n10 + n01, 0.5).pvalue) if (n10 + n01) > 0 else 1.0
    out["strict_01_infeasibility"] = {
        "rate_a": float(ia.mean()), "rate_b": float(ib.mean()), "diff": float(ia.mean() - ib.mean()),
        "ci95_low": float(ilo), "ci95_high": float(ihi),
        "discordant_a_only": n10, "discordant_b_only": n01, "mcnemar_exact_p": p_mc,
    }
    return out


def train_upstream_odece_capacity_arm(
    arm_name: str,
    pool: ProcessPoolExecutor,
    init_state_dict: dict,
    X_tr: np.ndarray,
    W_tr: np.ndarray,
    cap_tr_target: np.ndarray,
    c_tr: np.ndarray,
    sols_tr: np.ndarray,
    objs_tr: np.ndarray,
) -> Tuple[LinearRegressionforKP_PredCapacity, Dict]:
    t0 = time.perf_counter()
    reg = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    reg.load_state_dict(copy.deepcopy(init_state_dict))

    solver = knapsack_solver(50)
    odece_pl = ODECE(
        [reg],
        predict_indices=1,
        optsolver=solver,
        num_predconstrsvar=1,
        infeasibility_aversion_coeff=ALPHA,
        margin_threshold=MARGIN,
        predict_cost=False,
        lr=LR,
        max_epochs=MAX_EPOCHS,
        seed=SEED,
    )
    odece_pl.log = lambda *args, **kwargs: None
    optimizer = torch.optim.Adam(reg.parameters(), lr=LR)

    rng = np.random.default_rng(SEED + 1000)
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
            xb, wb, capb, cb = X_tr[idx], W_tr[idx], cap_tr_target[idx], c_tr[idx]
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

            # Direct call to ACTUAL unmodified pinned official_odece_repo/src/odece.py!
            loss_ipl, loss_opl = odece_pl.losses_computation(
                trueConstr_tuple, pred_params_tuple, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t
            )

            n_batches += 1
            if mask_t.sum() == 0:
                # Documented Guard 2: unmodified src/odece.py:L103-106 returns (OPL, 0), symmetric at alpha=0.5
                n_mask_zero_batches += 1
                ep_m0 += 1
                prev_ipl = loss_ipl.mean()
                prev_opl = loss_opl.mean()
            else:
                prev_opl = loss_opl.mean()
                if loss_ipl.numel() == 0:
                    # Documented Guard 1: empty violation_pred_mask -> 0.0 instead of NaN
                    n_zero_infeas_batches += 1
                    ep_z0 += 1
                    prev_ipl = torch.zeros((), dtype=torch.float64)
                else:
                    prev_ipl = loss_ipl.mean()

            total_loss = ALPHA * (prev_ipl + 1e-4).mean() + (1.0 - ALPHA) * (prev_opl + 1e-4).mean()
            assert torch.isfinite(total_loss), f"Non-finite loss at {arm_name} ep={ep}"
            total_loss.backward()
            nn.utils.clip_grad_norm_(reg.parameters(), 0.5)
            optimizer.step()
            ep_losses.append(float(total_loss.item()))

        epoch_logs.append({
            "epoch": ep + 1,
            "mean_loss": float(np.mean(ep_losses)),
            "solvable_train_instances_of_900": ep_ok,
            "zero_infeas_batches": ep_z0,
            "mask_zero_batches": ep_m0,
        })
        if (ep + 1) in (1, 5, 10, 15, 20):
            print(
                f"  [{arm_name}] ep={ep+1:2d}/20 | loss={np.mean(ep_losses):8.4f} | solvable={ep_ok:3d}/900 | z0={ep_z0:2d} | m0={ep_m0:2d}",
                flush=True,
            )

    reg.eval()
    return reg, {
        "inloop_train_solves": inloop_solves,
        "inloop_solver_time_s": inloop_solver_t,
        "train_wall_time_s": time.perf_counter() - t0,
        "train_status_counts": status_counts,
        "n_batches": n_batches,
        "n_zero_infeas_batches_guard1": n_zero_infeas_batches,
        "n_mask_zero_batches_guard2": n_mask_zero_batches,
        "n_true_sol_ulp_viols_observed": n_true_sol_ulp_viols,
        "epoch_logs": epoch_logs,
    }


def main():
    t_all = time.perf_counter()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    pid = os.getpid()
    print(f"=== Stage-2c Upstream ODECE(alpha=0.5) Capacity Mechanism Confirmation (seed={SEED}, PID={pid}) ===", flush=True)

    # Record exact source checkpoint hashes
    source_hashes = {
        "official_src_odece_py": sha256_file(REPO / "src" / "odece.py"),
        "official_kpsolver_py": sha256_file(REPO / "OptProblems" / "knapsack" / "kpsolver.py"),
        "official_kpdata_py": sha256_file(REPO / "OptProblems" / "knapsack" / "kpdata.py"),
        "official_TorchML_py": sha256_file(REPO / "ML" / "TorchML.py"),
        "STAGE2C_ODECE_CAPACITY_PROTOCOL_md": sha256_file(BASE / "STAGE2C_ODECE_CAPACITY_PROTOCOL.md"),
        "stage2c_odece_capacity_seed16_py": sha256_file(pathlib.Path(__file__)),
        "ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT_json": sha256_file(BASE / "ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT.json"),
    }

    # Generate fresh seed 16 data with exact published MDKP_CapaExp.sh flags
    X, w, costs, capacity = genCapacity(
        num_data=1500, num_features=10, num_items=50, dim=3, deg=6, noise_width=0.25, fixed_cost=False, seed=SEED
    )
    idx_all = np.arange(1500)
    idx_tr_full, idx_te = train_test_split(idx_all, test_size=500, random_state=SEED)
    idx_tr, idx_va = train_test_split(idx_tr_full, test_size=0.1, random_state=SEED)

    X_tr, W_tr, c_tr = X[idx_tr], w[idx_tr], costs[idx_tr]
    cap_tr_clean = capacity[idx_tr]
    cap_tr_misp = capacity[: len(idx_tr)]  # exact upstream KnapsackCapaExp.py:L73

    X_va, W_va, cap_va, c_va = X[idx_va], w[idx_va], capacity[idx_va], costs[idx_va]
    X_te, W_te, cap_te, c_te = X[idx_te], w[idx_te], capacity[idx_te], costs[idx_te]

    y_bar_shared = cap_tr_clean.mean(axis=0, keepdims=True)
    mse_shared_mean_te = float(np.mean((cap_te - y_bar_shared) ** 2))
    mse_shared_mean_va = float(np.mean((cap_va - y_bar_shared) ** 2))

    # 0-MIP supervised OLS sanity check on fresh seed 16
    Xb_tr = np.hstack([X_tr, np.ones((len(X_tr), 1))])
    Xb_te = np.hstack([X_te, np.ones((len(X_te), 1))])
    B_oc, _, _, _ = np.linalg.lstsq(Xb_tr, cap_tr_clean, rcond=None)
    B_om, _, _, _ = np.linalg.lstsq(Xb_tr, cap_tr_misp, rcond=None)
    ols_clean_mse = float(np.mean((Xb_te @ B_oc - cap_te) ** 2))
    ols_misp_mse = float(np.mean((Xb_te @ B_om - cap_te) ** 2))
    print(
        f"  [Seed 16 Supervised Sanity] shared_mean MSE={mse_shared_mean_te:.3f} | "
        f"OLS-Clean OOS R2={1.0 - ols_clean_mse/mse_shared_mean_te:+.4f} vs OLS-Mispaired OOS R2={1.0 - ols_misp_mse/mse_shared_mean_te:+.4f}",
        flush=True,
    )

    # Paired identical PyTorch initialization (saved to disk with SHA-256)
    torch.manual_seed(SEED)
    init_model = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    init_state = copy.deepcopy(init_model.state_dict())
    init_ckpt_path = OUT_DIR / "paired_init_weights.json"
    init_ckpt_path.write_text(
        json.dumps({"weight": init_state["linear.weight"].tolist(), "bias": init_state["linear.bias"].tolist()}, indent=2),
        encoding="utf-8",
    )

    cpsat_total = 0
    highs_total = 0
    gammas = [0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00]

    with ProcessPoolExecutor(max_workers=N_WORKERS) as pool:
        # Offline oracle solves: train_clean, train_misp, clean_val (CP-SAT), clean_test (HiGHS float64)
        print("[Step 1] Computing offline true oracle MIPs (train clean/misp, clean val CP-SAT, clean test HiGHS float64)...", flush=True)
        off_tr_clean = batch_solve_cpsat(pool, W_tr, cap_tr_clean, c_tr, time_lim=5.0)
        off_tr_misp = batch_solve_cpsat(pool, W_tr, cap_tr_misp, c_tr, time_lim=5.0)
        off_va = batch_solve_cpsat(pool, W_va, cap_va, c_va, time_lim=5.0)
        cpsat_total += off_tr_clean["n_calls"] + off_tr_misp["n_calls"] + off_va["n_calls"]
        off_te_h = batch_solve_highs(pool, W_te, cap_te, c_te, time_lim=5.0)
        highs_total += off_te_h["n_calls"]
        print(
            f"  Offline statuses: tr_clean={off_tr_clean['status_counts']}, tr_misp={off_tr_misp['status_counts']}, "
            f"val={off_va['status_counts']}, test_HiGHS={off_te_h['status_counts']} ({off_te_h['wall_time_s']:.2f}s, gap={off_te_h['max_mip_gap']:.2e})",
            flush=True,
        )

        # Train both arms with paired identical init and actual upstream src/odece.py in float64
        arm_specs = [
            ("ODECE-Clean(a=0.5)", cap_tr_clean, off_tr_clean),
            ("ODECE-Mispaired(a=0.5)", cap_tr_misp, off_tr_misp),
        ]
        arm_outputs: Dict[str, Dict] = {}
        pi_highs_raw_clip: Dict[str, List[Dict]] = {}
        pi_highs_raw_unclip: Dict[str, List[Dict]] = {}
        pi_highs_vp: Dict[str, List[Dict]] = {}

        for arm_name, cap_tr_tgt, off_tr_arm in arm_specs:
            print(f"\n[Step 2] Training {arm_name} via ACTUAL pinned upstream src/odece.py (float64)...", flush=True)
            model, tr_info = train_upstream_odece_capacity_arm(
                arm_name, pool, init_state, X_tr, W_tr, cap_tr_tgt, c_tr, off_tr_arm["sols"], off_tr_arm["objs"]
            )
            cpsat_total += tr_info["inloop_train_solves"]

            # Save final model weights checkpoint
            safe_name = arm_name.replace("(", "_").replace(")", "").replace("=", "")
            ckpt_p = OUT_DIR / f"final_weights_{safe_name}.json"
            ckpt_p.write_text(
                json.dumps({"weight": model.linear.weight.detach().tolist(), "bias": model.linear.bias.detach().tolist()}, indent=2),
                encoding="utf-8",
            )

            with torch.no_grad():
                pred_va = model(torch.tensor(X_va, dtype=torch.float64)).cpu().numpy()
                pred_te = model(torch.tensor(X_te, dtype=torch.float64)).cpu().numpy()

            # Policy A1: Raw plug-in UNCLIPPED (exact upstream kpsolver behavior if negative -> INFEASIBLE/unsolvable)
            sh_raw_unclip = batch_solve_highs(pool, W_te, pred_te, c_te, time_lim=5.0)
            highs_total += sh_raw_unclip["n_calls"]
            tm_raw_unclip, pi_ru = evaluate_decisions(W_te, cap_te, c_te, off_te_h["objs"], pred_te, sh_raw_unclip["sols"], sh_raw_unclip["ok_mask"], sh_raw_unclip["statuses"], mse_shared_mean_te)
            pi_highs_raw_unclip[arm_name] = pi_ru

            # Policy A2: Raw plug-in Stage-2b clipped >= 0.0 (reuses unclipped if 0 negatives!)
            n_neg_raw = int(np.sum(pred_te < 0.0))
            if n_neg_raw == 0:
                sh_raw_clip = sh_raw_unclip
                tm_raw_clip, pi_rc = tm_raw_unclip, pi_ru
            else:
                cap_te_clip = np.clip(pred_te, 0.0, None)
                sh_raw_clip = batch_solve_highs(pool, W_te, cap_te_clip, c_te, time_lim=5.0)
                highs_total += sh_raw_clip["n_calls"]
                tm_raw_clip, pi_rc = evaluate_decisions(W_te, cap_te, c_te, off_te_h["objs"], cap_te_clip, sh_raw_clip["sols"], sh_raw_clip["ok_mask"], sh_raw_clip["statuses"], mse_shared_mean_te)
            pi_highs_raw_clip[arm_name] = pi_rc

            # Policy B: Exact Stage-2b ValPinned_le10pct on CLEAN validation
            sigma_va = np.std(cap_va - pred_va, axis=0, ddof=1)
            val_candidates = []
            for g in gammas:
                c_va_g = np.clip(pred_va - g * sigma_va[None, :], 0.0, None)
                sv = batch_solve_cpsat(pool, W_va, c_va_g, c_va, time_lim=2.0)
                cpsat_total += sv["n_calls"]
                vm, _ = evaluate_decisions(W_va, cap_va, c_va, off_va["objs"], c_va_g, sv["sols"], sv["ok_mask"], sv["statuses"], mse_shared_mean_va)
                val_candidates.append({"gamma": g, "val_metrics": vm, "val_status_counts": sv["status_counts"]})

            qual = [c for c in val_candidates if c["val_metrics"]["strict_01_infeasibility_rate"] <= 0.10 + 1e-12]
            if qual:
                best = min(qual, key=lambda c: (c["val_metrics"]["official_frac_surrogate_posthoc_p1"], c["val_metrics"]["strict_01_infeasibility_rate"]))
                used_fallback = False
            else:
                best = min(val_candidates, key=lambda c: (c["val_metrics"]["strict_01_infeasibility_rate"], c["val_metrics"]["official_frac_surrogate_posthoc_p1"]))
                used_fallback = True
            g_star = best["gamma"]
            c_te_vp_raw = pred_te - g_star * sigma_va[None, :]
            n_neg_vp = int(np.sum(c_te_vp_raw < 0.0))
            c_te_vp = np.clip(c_te_vp_raw, 0.0, None)
            if g_star == 0.0 and n_neg_raw == 0:
                sh_vp = sh_raw_clip
                tm_vp, pi_v = tm_raw_clip, pi_rc
            else:
                sh_vp = batch_solve_highs(pool, W_te, c_te_vp, c_te, time_lim=5.0)
                highs_total += sh_vp["n_calls"]
                tm_vp, pi_v = evaluate_decisions(W_te, cap_te, c_te, off_te_h["objs"], c_te_vp, sh_vp["sols"], sh_vp["ok_mask"], sh_vp["statuses"], mse_shared_mean_te)
            pi_highs_vp[arm_name] = pi_v

            # Persist per-instance HiGHS test outcomes
            (OUT_DIR / f"per_instance_highs_raw_{safe_name}.json").write_text(json.dumps(pi_rc), encoding="utf-8")
            (OUT_DIR / f"per_instance_highs_valpin_{safe_name}.json").write_text(json.dumps(pi_v), encoding="utf-8")

            arm_rec = {
                "arm_name": arm_name,
                "checkpoint_sha256": sha256_file(ckpt_p),
                "train_audit": tr_info,
                "Raw_Plugin_unclipped_highs": {
                    "test_metrics": tm_raw_unclip,
                    "highs_status_counts": sh_raw_unclip["status_counts"],
                    "highs_max_mip_gap": sh_raw_unclip["max_mip_gap"],
                    "highs_max_integrality_err": sh_raw_unclip["max_integrality_err"],
                    "n_neg_cap_dims_raw": n_neg_raw,
                },
                "Raw_Plugin_stage2b_clipped_highs": {
                    "test_metrics": tm_raw_clip,
                    "highs_status_counts": sh_raw_clip["status_counts"],
                    "highs_max_mip_gap": sh_raw_clip["max_mip_gap"],
                    "highs_max_integrality_err": sh_raw_clip["max_integrality_err"],
                    "n_neg_cap_dims_clipped": n_neg_raw,
                },
                "ValPinned_le10pct_highs": {
                    "selected_gamma": g_star,
                    "used_fallback": used_fallback,
                    "val_metrics_cpsat": best["val_metrics"],
                    "val_grid_summary": [
                        {
                            "gamma": c["gamma"],
                            "val_infeas": c["val_metrics"]["strict_01_infeasibility_rate"],
                            "val_frac_p1": c["val_metrics"]["official_frac_surrogate_posthoc_p1"],
                            "val_int_p1": c["val_metrics"]["strict_01_int_repair_posthoc_p1"],
                            "status_counts": c["val_status_counts"],
                        }
                        for c in val_candidates
                    ],
                    "test_metrics": tm_vp,
                    "highs_status_counts": sh_vp["status_counts"],
                    "highs_max_mip_gap": sh_vp["max_mip_gap"],
                    "highs_max_integrality_err": sh_vp["max_integrality_err"],
                    "n_neg_cap_dims_clipped": n_neg_vp,
                },
            }
            arm_outputs[arm_name] = arm_rec
            (OUT_DIR / f"arm_output_{safe_name}.json").write_text(json.dumps(arm_rec, indent=2), encoding="utf-8")

            print(
                f"  ==> {arm_name:22s} | RAW(g=0, neg={n_neg_raw}): inf={tm_raw_clip['strict_01_infeasibility_rate']*100:5.1f}% "
                f"fp1={tm_raw_clip['official_frac_surrogate_posthoc_p1']*100:6.2f}% ip1={tm_raw_clip['strict_01_int_repair_posthoc_p1']*100:6.2f}% "
                f"cap_OOS_R2={tm_raw_clip['capacity_oos_r2_vs_shared_mean']:+.4f} | "
                f"VAL<=10%(g={g_star:.2f}, val_inf={best['val_metrics']['strict_01_infeasibility_rate']*100:4.1f}%, fb={used_fallback}): "
                f"TEST inf={tm_vp['strict_01_infeasibility_rate']*100:5.1f}% fp1={tm_vp['official_frac_surrogate_posthoc_p1']*100:6.2f}% "
                f"ip1={tm_vp['strict_01_int_repair_posthoc_p1']*100:6.2f}% | HiGHS={sh_vp['status_counts']}",
                flush=True,
            )

    rng_stat = np.random.default_rng(2026112416)
    paired = {
        "Raw_Plugin_unclipped": paired_compare(pi_highs_raw_unclip["ODECE-Clean(a=0.5)"], pi_highs_raw_unclip["ODECE-Mispaired(a=0.5)"], rng_stat),
        "Raw_Plugin_stage2b_clipped": paired_compare(pi_highs_raw_clip["ODECE-Clean(a=0.5)"], pi_highs_raw_clip["ODECE-Mispaired(a=0.5)"], rng_stat),
        "ValPinned_le10pct": paired_compare(pi_highs_vp["ODECE-Clean(a=0.5)"], pi_highs_vp["ODECE-Mispaired(a=0.5)"], rng_stat),
    }

    summary = {
        "protocol": "STAGE2C_ODECE_CAPACITY_PROTOCOL.md",
        "real_pid": pid,
        "torch_version": torch.__version__,
        "seed": SEED,
        "reserved_untouched_seeds": RESERVED_SEEDS,
        "alpha": ALPHA,
        "lr": LR,
        "batch_size": BATCH_SIZE,
        "max_epochs": MAX_EPOCHS,
        "intervention_label": "Controlled single-seed (seed=16) mechanism confirmation calling ACTUAL pinned upstream src/odece.py in float64 (alpha=0.5) on MDKP-Capacity. Tests the training-label mispairing effect inside one upstream loss recipe; NOT a claim about published method rankings.",
        "source_checkpoint_hashes": {
            **source_hashes,
            "paired_init_weights_json": sha256_file(init_ckpt_path),
        },
        "seed16_alignment_and_ols_sanity": {
            "train_misaligned_count": f"{int(np.sum(idx_tr != np.arange(len(idx_tr))))}/{len(idx_tr)}",
            "test_indices_in_0_899": f"{int(np.sum(idx_te < len(idx_tr)))}/{len(idx_te)}",
            "shared_mean_mse_clean_test": mse_shared_mean_te,
            "ols_clean_mse": ols_clean_mse,
            "ols_clean_oos_r2": float(1.0 - ols_clean_mse / mse_shared_mean_te),
            "ols_mispaired_mse": ols_misp_mse,
            "ols_mispaired_oos_r2": float(1.0 - ols_misp_mse / mse_shared_mean_te),
        },
        "offline_audit": {
            "train_clean_cpsat": {"calls": off_tr_clean["n_calls"], "status_counts": off_tr_clean["status_counts"]},
            "train_misp_cpsat": {"calls": off_tr_misp["n_calls"], "status_counts": off_tr_misp["status_counts"]},
            "val_clean_cpsat": {"calls": off_va["n_calls"], "status_counts": off_va["status_counts"]},
            "test_clean_highs_float64": {
                "calls": off_te_h["n_calls"], "wall_time_s": off_te_h["wall_time_s"],
                "status_counts": off_te_h["status_counts"],
                "max_mip_gap": off_te_h["max_mip_gap"],
                "max_integrality_err": off_te_h["max_integrality_err"],
            },
        },
        "total_cpsat_calls": cpsat_total,
        "total_highs_float64_calls": highs_total,
        "total_wall_time_s": time.perf_counter() - t_all,
        "arms": arm_outputs,
        "paired_clean_minus_mispaired_highs_n500": paired,
    }
    out_path = OUT_DIR / "stage2c_seed16_summary.json"
    out_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    p_raw = paired["Raw_Plugin_stage2b_clipped"]
    p_vp = paired["ValPinned_le10pct"]
    print(f"\n================ STAGE-2C SEED-16 SUMMARY (PID={pid}, wall={summary['total_wall_time_s']:.1f}s) ================", flush=True)
    print(
        f"  [Raw_Plugin] ODECE-Clean - ODECE-Mispaired (n=500 HiGHS): "
        f"frac_p1={p_raw['frac_p1']['mean_diff']*100:+.3f}pp [{p_raw['frac_p1']['ci95_low']*100:+.3f}, {p_raw['frac_p1']['ci95_high']*100:+.3f}] (p={p_raw['frac_p1']['wilcoxon_p']:.2e}) | "
        f"int_p1={p_raw['int_p1']['mean_diff']*100:+.3f}pp (p={p_raw['int_p1']['wilcoxon_p']:.2e}) | "
        f"infeas={p_raw['strict_01_infeasibility']['diff']*100:+.2f}pp (McNemar p={p_raw['strict_01_infeasibility']['mcnemar_exact_p']:.2e})",
        flush=True,
    )
    print(
        f"  [ValPinned<=10%] ODECE-Clean - ODECE-Mispaired (n=500 HiGHS): "
        f"frac_p1={p_vp['frac_p1']['mean_diff']*100:+.3f}pp [{p_vp['frac_p1']['ci95_low']*100:+.3f}, {p_vp['frac_p1']['ci95_high']*100:+.3f}] (p={p_vp['frac_p1']['wilcoxon_p']:.2e}) | "
        f"int_p1={p_vp['int_p1']['mean_diff']*100:+.3f}pp (p={p_vp['int_p1']['wilcoxon_p']:.2e}) | "
        f"infeas={p_vp['strict_01_infeasibility']['diff']*100:+.2f}pp (McNemar p={p_vp['strict_01_infeasibility']['mcnemar_exact_p']:.2e})",
        flush=True,
    )
    print(f"Saved Stage-2c summary to {out_path} (CP-SAT={cpsat_total}, HiGHS={highs_total})", flush=True)


if __name__ == "__main__":
    main()
