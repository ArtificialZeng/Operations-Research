"""
Stage-2b Bounded Downstream Controlled Intervention for MDKP-Capacity Training-Label Mispairing
(`STAGE2B_CAPACITY_INTERVENTION_PROTOCOL.md`).

Controlled intervention on published MDKP-Capacity regime:
  num_items=50, dim=3, num_feat=10, deg=6, noise_width=0.25, seeds=[11, 12, 13, 14, 15].
Compares:
  - OLS-Clean vs OLS-Mispaired vs SharedMean
  - AdamMSE-Clean vs AdamMSE-Mispaired (published lr=0.005, bs=32, epochs=20)
Evaluated on IDENTICAL clean held-out test instances (w[idx_te], capacity[idx_te], costs[idx_te]),
under BOTH:
  - Policy A: Raw plug-in (gamma=0)
  - Policy B: Prespecified ValPinned_le10pct (pred - gamma * sigma_val selected on clean val)

All test evaluations (offline true OPT + every raw & val-pinned test arm) solved directly in
unrounded float64 HiGHS 1.16.0 (0 training ILPs; NO all-alpha ODECE retraining).
"""
from __future__ import annotations

import json
import math
import pathlib
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from typing import Dict, List, Optional, Tuple

import highspy
import numpy as np
from ortools.sat.python import cp_model
from scipy import stats
from sklearn.model_selection import train_test_split

BASE = pathlib.Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
sys.path.insert(0, str(BASE / "official_odece_repo"))
from OptProblems.knapsack.kpdata import genCapacity  # type: ignore

SEEDS = [11, 12, 13, 14, 15]
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


def solve_single_cpsat(args: Tuple[np.ndarray, np.ndarray, np.ndarray, float]) -> Tuple[str, np.ndarray, float]:
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
        return st_name, sol, float(np.dot(cost_vec, sol))
    return st_name, np.zeros(50, dtype=np.float64), float("nan")


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


class LinearCapacityPredictor:
    def __init__(self, num_feat: int = 10, dim: int = 3, seed: int = 11):
        rng = np.random.default_rng(seed)
        lim = math.sqrt(6.0 / (num_feat + dim))
        self.W = rng.uniform(-lim, lim, size=(num_feat, dim)).astype(np.float64)
        self.b = np.zeros(dim, dtype=np.float64)
        self.mW = np.zeros_like(self.W); self.vW = np.zeros_like(self.W)
        self.mb = np.zeros_like(self.b); self.vb = np.zeros_like(self.b)
        self.t = 0

    def forward(self, X: np.ndarray) -> np.ndarray:
        return X @ self.W + self.b[None, :]

    def step_adam(self, X: np.ndarray, d_out: np.ndarray, lr: float):
        gW = X.T @ d_out; gb = np.sum(d_out, axis=0)
        self.t += 1
        b1, b2, eps = 0.9, 0.999, 1e-8
        self.mW = b1 * self.mW + (1.0 - b1) * gW
        self.vW = b2 * self.vW + (1.0 - b2) * (gW * gW)
        self.mb = b1 * self.mb + (1.0 - b1) * gb
        self.vb = b2 * self.vb + (1.0 - b2) * (gb * gb)
        self.W -= lr * (self.mW / (1.0 - b1 ** self.t)) / (np.sqrt(self.vW / (1.0 - b2 ** self.t)) + eps)
        self.b -= lr * (self.mb / (1.0 - b1 ** self.t)) / (np.sqrt(self.vb / (1.0 - b2 ** self.t)) + eps)


def train_adam_mse(X_tr: np.ndarray, y_tr: np.ndarray, seed: int) -> LinearCapacityPredictor:
    m = LinearCapacityPredictor(num_feat=X_tr.shape[1], dim=y_tr.shape[1], seed=seed)
    rng = np.random.default_rng(seed + 1000)
    N = len(X_tr)
    for _ in range(20):
        order = rng.permutation(N)
        for s in range(0, N, 32):
            idx = order[s : s + 32]
            xb, yb = X_tr[idx], y_tr[idx]
            pred = m.forward(xb)
            m.step_adam(xb, (-2.0 * (yb - pred)) / float(pred.size), lr=0.005)
    return m


def fit_ols(X_tr: np.ndarray, y_tr: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    Xb = np.hstack([X_tr, np.ones((len(X_tr), 1))])
    B, _, _, _ = np.linalg.lstsq(Xb, y_tr, rcond=None)
    return B[:-1, :], B[-1, :]


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
    cap_pred: np.ndarray, sols: np.ndarray, ok_mask: np.ndarray, statuses: List[str]
) -> Tuple[Dict, List[Dict]]:
    N = len(W_true)
    per_inst = []
    feas_regrets = []
    fp1_l, fp021_l, ip1_l, ip021_l = [], [], [], []
    n_infeas = 0
    for i in range(N):
        t_obj = float(true_objs[i])
        if not ok_mask[i]:
            n_infeas += 1
            fp1 = fp021 = ip1 = ip021 = 1.0
            per_inst.append({"idx": i, "status": statuses[i], "strict_01_feasible": False, "frac_p1": 1.0, "frac_p021": 1.0, "int_p1": 1.0, "int_p021": 1.0})
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
            per_inst.append({"idx": i, "status": statuses[i], "strict_01_feasible": strict_feas, "frac_p1": float(fp1), "frac_p021": float(fp021), "int_p1": float(ip1), "int_p021": float(ip021)})
        fp1_l.append(fp1); fp021_l.append(fp021); ip1_l.append(ip1); ip021_l.append(ip021)
    return {
        "strict_01_infeasibility_rate": float(n_infeas / N),
        "strict_01_feasible_count": int(N - n_infeas),
        "strict_01_feasible_regret": float(np.mean(feas_regrets)) if feas_regrets else float("nan"),
        "official_frac_surrogate_posthoc_p1": float(np.mean(fp1_l)),
        "official_frac_surrogate_posthoc_p021": float(np.mean(fp021_l)),
        "strict_01_int_repair_posthoc_p1": float(np.mean(ip1_l)),
        "strict_01_int_repair_posthoc_p021": float(np.mean(ip021_l)),
        "capacity_mse": float(np.mean((cap_pred - cap_true) ** 2)),
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


def main():
    t_start = time.perf_counter()
    gammas = [0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00]
    arms = ["OLS-Clean", "OLS-Mispaired", "SharedMean", "AdamMSE-Clean", "AdamMSE-Mispaired"]
    per_seed_results = []
    pooled_pi: Dict[str, Dict[str, List[Dict]]] = {
        "Raw_Plugin": {a: [] for a in arms},
        "ValPinned_le10pct": {a: [] for a in arms},
    }
    total_cpsat = 0
    total_highs = 0
    rng_stat = np.random.default_rng(2026112402)

    with ProcessPoolExecutor(max_workers=N_WORKERS) as pool:
        for seed in SEEDS:
            print(f"\n=== Stage-2b Seed {seed} (MDKP-Capacity items=50, deg=6, noise=0.25) ===", flush=True)
            X, w, costs, capacity = genCapacity(1500, 10, 50, dim=3, deg=6, noise_width=0.25, seed=seed)
            idx_all = np.arange(1500)
            idx_tr_full, idx_te = train_test_split(idx_all, test_size=500, random_state=seed)
            idx_tr, idx_va = train_test_split(idx_tr_full, test_size=0.1, random_state=seed)

            X_tr, cap_tr_clean, cap_tr_misp = X[idx_tr], capacity[idx_tr], capacity[: len(idx_tr)]
            X_va, W_va, cap_va, c_va = X[idx_va], w[idx_va], capacity[idx_va], costs[idx_va]
            X_te, W_te, cap_te, c_te = X[idx_te], w[idx_te], capacity[idx_te], costs[idx_te]

            # Offline true oracle on clean val (CP-SAT) and clean test (HiGHS float64)
            off_va = batch_solve_cpsat(pool, W_va, cap_va, c_va, time_lim=5.0)
            total_cpsat += off_va["n_calls"]
            off_te_h = batch_solve_highs(pool, W_te, cap_te, c_te, time_lim=5.0)
            total_highs += off_te_h["n_calls"]
            print(f"  Offline clean oracle: val CP-SAT={off_va['status_counts']}, test HiGHS={off_te_h['status_counts']} ({off_te_h['wall_time_s']:.2f}s, gap={off_te_h['max_mip_gap']:.2e})", flush=True)

            # Fit the 5 predictors (0 training MIPs)
            W_oc, b_oc = fit_ols(X_tr, cap_tr_clean)
            W_om, b_om = fit_ols(X_tr, cap_tr_misp)
            y_bar = cap_tr_clean.mean(axis=0)
            m_ac = train_adam_mse(X_tr, cap_tr_clean, seed=seed)
            m_am = train_adam_mse(X_tr, cap_tr_misp, seed=seed)

            preds_va = {
                "OLS-Clean": X_va @ W_oc + b_oc[None, :],
                "OLS-Mispaired": X_va @ W_om + b_om[None, :],
                "SharedMean": np.tile(y_bar, (len(X_va), 1)),
                "AdamMSE-Clean": m_ac.forward(X_va),
                "AdamMSE-Mispaired": m_am.forward(X_va),
            }
            preds_te = {
                "OLS-Clean": X_te @ W_oc + b_oc[None, :],
                "OLS-Mispaired": X_te @ W_om + b_om[None, :],
                "SharedMean": np.tile(y_bar, (len(X_te), 1)),
                "AdamMSE-Clean": m_ac.forward(X_te),
                "AdamMSE-Mispaired": m_am.forward(X_te),
            }

            seed_raw = {}
            seed_valpin = {}
            highs_test_cache: Dict[Tuple[str, float], Tuple[Dict, List[Dict], Dict]] = {}

            def eval_test_highs(arm_name: str, gamma: float, pred_cap_te: np.ndarray) -> Tuple[Dict, List[Dict], Dict]:
                key = (arm_name, gamma)
                if key in highs_test_cache:
                    return highs_test_cache[key]
                nonlocal total_highs
                cap_clip = np.clip(pred_cap_te, 0.0, None)
                n_neg_clip = int(np.sum(pred_cap_te < 0.0))
                sh = batch_solve_highs(pool, W_te, cap_clip, c_te, time_lim=5.0)
                total_highs += sh["n_calls"]
                tm, pi_t = evaluate_decisions(W_te, cap_te, c_te, off_te_h["objs"], cap_clip, sh["sols"], sh["ok_mask"], sh["statuses"])
                audit = {
                    "highs_status_counts": sh["status_counts"],
                    "highs_wall_time_s": sh["wall_time_s"],
                    "highs_max_mip_gap": sh["max_mip_gap"],
                    "highs_max_integrality_err": sh["max_integrality_err"],
                    "n_neg_cap_dims_clipped": n_neg_clip,
                }
                highs_test_cache[key] = (tm, pi_t, audit)
                return tm, pi_t, audit

            seed_pi_raw: Dict[str, List[Dict]] = {}
            seed_pi_vp: Dict[str, List[Dict]] = {}

            for arm_name in arms:
                # Policy A: Raw plug-in (gamma = 0)
                tm_raw, pi_raw, aud_raw = eval_test_highs(arm_name, 0.0, preds_te[arm_name])
                seed_raw[arm_name] = {"gamma": 0.0, "test_metrics_highs": tm_raw, "highs_audit": aud_raw}
                seed_pi_raw[arm_name] = pi_raw
                pooled_pi["Raw_Plugin"][arm_name].extend(pi_raw)

                # Policy B: Prespecified ValPinned_le10pct on clean val
                sigma_va = np.std(cap_va - preds_va[arm_name], axis=0, ddof=1)
                val_candidates = []
                for g in gammas:
                    c_va_g = np.clip(preds_va[arm_name] - g * sigma_va[None, :], 0.0, None)
                    sv = batch_solve_cpsat(pool, W_va, c_va_g, c_va, time_lim=2.0)
                    total_cpsat += sv["n_calls"]
                    vm, _ = evaluate_decisions(W_va, cap_va, c_va, off_va["objs"], c_va_g, sv["sols"], sv["ok_mask"], sv["statuses"])
                    val_candidates.append({"gamma": g, "val_metrics": vm, "val_status_counts": sv["status_counts"]})

                qual = [c for c in val_candidates if c["val_metrics"]["strict_01_infeasibility_rate"] <= 0.10 + 1e-12]
                if qual:
                    best = min(qual, key=lambda c: (c["val_metrics"]["official_frac_surrogate_posthoc_p1"], c["val_metrics"]["strict_01_infeasibility_rate"]))
                    used_fallback = False
                else:
                    best = min(val_candidates, key=lambda c: (c["val_metrics"]["strict_01_infeasibility_rate"], c["val_metrics"]["official_frac_surrogate_posthoc_p1"]))
                    used_fallback = True
                g_star = best["gamma"]
                c_te_g = preds_te[arm_name] - g_star * sigma_va[None, :]
                tm_vp, pi_vp, aud_vp = eval_test_highs(arm_name, g_star, c_te_g)
                seed_valpin[arm_name] = {
                    "selected_gamma": g_star, "used_fallback": used_fallback,
                    "val_metrics_cpsat": best["val_metrics"],
                    "test_metrics_highs": tm_vp, "highs_audit": aud_vp,
                }
                seed_pi_vp[arm_name] = pi_vp
                pooled_pi["ValPinned_le10pct"][arm_name].extend(pi_vp)

                print(
                    f"  {arm_name:18s} | RAW(g=0): inf={tm_raw['strict_01_infeasibility_rate']*100:5.1f}% fp1={tm_raw['official_frac_surrogate_posthoc_p1']*100:6.2f}% ip1={tm_raw['strict_01_int_repair_posthoc_p1']*100:6.2f}% "
                    f"| VAL<=10%(g={g_star:.2f}, val_inf={best['val_metrics']['strict_01_infeasibility_rate']*100:4.1f}%): "
                    f"TEST inf={tm_vp['strict_01_infeasibility_rate']*100:5.1f}% fp1={tm_vp['official_frac_surrogate_posthoc_p1']*100:6.2f}% ip1={tm_vp['strict_01_int_repair_posthoc_p1']*100:6.2f}% | st={aud_vp['highs_status_counts']}",
                    flush=True,
                )

            per_seed_results.append({
                "seed": seed,
                "offline_clean_test_highs": {
                    "status_counts": off_te_h["status_counts"],
                    "max_mip_gap": off_te_h["max_mip_gap"],
                    "max_integrality_err": off_te_h["max_integrality_err"],
                },
                "Raw_Plugin": seed_raw,
                "ValPinned_le10pct": seed_valpin,
                "per_seed_paired_highs": {
                    "Raw_Plugin": {
                        "OLSClean_minus_OLSMispaired": paired_compare(seed_pi_raw["OLS-Clean"], seed_pi_raw["OLS-Mispaired"], rng_stat),
                        "OLSClean_minus_SharedMean": paired_compare(seed_pi_raw["OLS-Clean"], seed_pi_raw["SharedMean"], rng_stat),
                        "AdamClean_minus_AdamMispaired": paired_compare(seed_pi_raw["AdamMSE-Clean"], seed_pi_raw["AdamMSE-Mispaired"], rng_stat),
                    },
                    "ValPinned_le10pct": {
                        "OLSClean_minus_OLSMispaired": paired_compare(seed_pi_vp["OLS-Clean"], seed_pi_vp["OLS-Mispaired"], rng_stat),
                        "OLSClean_minus_SharedMean": paired_compare(seed_pi_vp["OLS-Clean"], seed_pi_vp["SharedMean"], rng_stat),
                        "AdamClean_minus_AdamMispaired": paired_compare(seed_pi_vp["AdamMSE-Clean"], seed_pi_vp["AdamMSE-Mispaired"], rng_stat),
                    },
                },
            })

    # 5-seed aggregate + conditional pooled (n=2500) paired stats
    agg_policies = {}
    for pol in ["Raw_Plugin", "ValPinned_le10pct"]:
        fam_agg = {}
        for arm_name in arms:
            rows = [r[pol][arm_name]["test_metrics_highs"] for r in per_seed_results]
            fam_agg[arm_name] = {
                k: {
                    "mean": float(np.mean([x[k] for x in rows])),
                    "sd_ddof1": float(np.std([x[k] for x in rows], ddof=1)),
                    "min": float(np.min([x[k] for x in rows])),
                    "max": float(np.max([x[k] for x in rows])),
                }
                for k in ["strict_01_infeasibility_rate", "official_frac_surrogate_posthoc_p1", "strict_01_int_repair_posthoc_p1", "official_frac_surrogate_posthoc_p021", "strict_01_int_repair_posthoc_p021"]
            }
        agg_policies[pol] = {
            "across_5_seeds_mean_sd": fam_agg,
            "pooled_n2500_conditional_on_5_fitted_pairs": {
                "OLSClean_minus_OLSMispaired": paired_compare(pooled_pi[pol]["OLS-Clean"], pooled_pi[pol]["OLS-Mispaired"], rng_stat),
                "OLSClean_minus_SharedMean": paired_compare(pooled_pi[pol]["OLS-Clean"], pooled_pi[pol]["SharedMean"], rng_stat),
                "AdamClean_minus_AdamMispaired": paired_compare(pooled_pi[pol]["AdamMSE-Clean"], pooled_pi[pol]["AdamMSE-Mispaired"], rng_stat),
            },
        }

    out = {
        "protocol": "STAGE2B_CAPACITY_INTERVENTION_PROTOCOL.md",
        "intervention_label": "Controlled downstream intervention on IDENTICAL clean held-out true MDKP-Capacity constraints/costs (items=50, deg=6, noise=0.25, seeds 11-15). Not a claim about published method rankings; 0 training MIPs / no all-alpha ODECE retraining.",
        "seeds": SEEDS,
        "total_cpsat_val_calls": total_cpsat,
        "total_highs_float64_test_calls": total_highs,
        "total_wall_time_s": time.perf_counter() - t_start,
        "aggregate_5seeds": agg_policies,
        "per_seed": per_seed_results,
    }
    out_path = BASE / "stage2b_capacity_downstream_results.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print("\n================ STAGE-2B 5-SEED SUMMARY (HI-GHS FLOAT64 CLEAN TEST) ================", flush=True)
    for pol in ["Raw_Plugin", "ValPinned_le10pct"]:
        print(f"\n--- {pol} ---", flush=True)
        for arm_name in arms:
            a5 = agg_policies[pol]["across_5_seeds_mean_sd"][arm_name]
            print(
                f"  {arm_name:18s} | infeas={a5['strict_01_infeasibility_rate']['mean']*100:5.2f} +/- {a5['strict_01_infeasibility_rate']['sd_ddof1']*100:4.2f}% "
                f"| frac_p1={a5['official_frac_surrogate_posthoc_p1']['mean']*100:6.3f} +/- {a5['official_frac_surrogate_posthoc_p1']['sd_ddof1']*100:5.3f}% "
                f"| int_p1={a5['strict_01_int_repair_posthoc_p1']['mean']*100:6.3f} +/- {a5['strict_01_int_repair_posthoc_p1']['sd_ddof1']*100:5.3f}%",
                flush=True,
            )
        p_ols = agg_policies[pol]["pooled_n2500_conditional_on_5_fitted_pairs"]["OLSClean_minus_OLSMispaired"]
        p_adm = agg_policies[pol]["pooled_n2500_conditional_on_5_fitted_pairs"]["AdamClean_minus_AdamMispaired"]
        print(
            f"  [Cond. n=2500] OLS-Clean - OLS-Mispaired : frac_p1={p_ols['frac_p1']['mean_diff']*100:+.3f}pp [{p_ols['frac_p1']['ci95_low']*100:+.3f}, {p_ols['frac_p1']['ci95_high']*100:+.3f}] (p={p_ols['frac_p1']['wilcoxon_p']:.2e}), "
            f"int_p1={p_ols['int_p1']['mean_diff']*100:+.3f}pp (p={p_ols['int_p1']['wilcoxon_p']:.2e}), "
            f"infeas={p_ols['strict_01_infeasibility']['diff']*100:+.2f}pp (McNemar p={p_ols['strict_01_infeasibility']['mcnemar_exact_p']:.2e})",
            flush=True,
        )
        print(
            f"  [Cond. n=2500] Adam-Clean - Adam-Mispaired: frac_p1={p_adm['frac_p1']['mean_diff']*100:+.3f}pp [{p_adm['frac_p1']['ci95_low']*100:+.3f}, {p_adm['frac_p1']['ci95_high']*100:+.3f}] (p={p_adm['frac_p1']['wilcoxon_p']:.2e}), "
            f"int_p1={p_adm['int_p1']['mean_diff']*100:+.3f}pp (p={p_adm['int_p1']['wilcoxon_p']:.2e}), "
            f"infeas={p_adm['strict_01_infeasibility']['diff']*100:+.2f}pp (McNemar p={p_adm['strict_01_infeasibility']['mcnemar_exact_p']:.2e})",
            flush=True,
        )
    print(f"\nSaved Stage-2b results to {out_path} (CP-SAT={total_cpsat}, HiGHS={total_highs}, wall={out['total_wall_time_s']:.1f}s)", flush=True)


if __name__ == "__main__":
    main()
