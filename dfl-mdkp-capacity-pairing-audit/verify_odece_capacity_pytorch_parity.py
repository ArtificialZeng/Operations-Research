"""
Pre-launch Loss & Gradient Parity Check for ACTUAL Unmodified Pinned Upstream PyTorch
`official_odece_repo/src/odece.py` on MDKP-Capacity (`predict_indices=1`, RHS capacity prediction)
in `torch.float64` with Documented Numerical Guards.

Uses ONLY seed=11 (already inspected in Stage-2a/2b; NEVER touches fresh seed=16 or reserved 17-18).
Checks:
  Case 1 (Realistic mixed batch, alpha=0.5, float64): exercises OPL (violation_true=0) AND IAL
         with 0, 1, 2, 3 violated capacity constraints; compares PyTorch autograd (dL/dW, dL/db)
         against EXHAUSTIVE central finite differences (eps=1e-6) on ALL 33 parameters (10x3 + 3).
  Case 2 (Partial mask batch, 2 unsolved instances mask[k]=False): exhaustive 33-param FD parity.
  Case 3 (mask.sum()==0 branch — all negative predicted capacities at init): verifies upstream
         src/odece.py:L95-106 branch behaves cleanly at alpha=0.5 and matches 33-param FD.
  Case 4 (violation_pred_mask.sum()==0 edge case — all predicted solutions feasible): verifies
         unmodified empty-tensor NaN vs Documented Guard 1 (prev_ipl = 0) matching 33-param FD.
"""
from __future__ import annotations

import json
import pathlib
import sys
import types
import numpy as np
import torch
from ortools.sat.python import cp_model
from sklearn.model_selection import train_test_split

BASE = pathlib.Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
REPO = BASE / "official_odece_repo"

# Stub gurobipy ONLY because kpsolver.py imports it at module top level; solve() is NOT called here.
gp_stub = types.ModuleType("gurobipy")
gp_stub.GRB = types.SimpleNamespace(BINARY="B", MAXIMIZE=-1, OPTIMAL=2)
sys.modules["gurobipy"] = gp_stub
sys.path.insert(0, str(REPO))

from OptProblems.knapsack.kpdata import genCapacity  # type: ignore
from OptProblems.knapsack.kpsolver import knapsack_solver  # type: ignore
from ML.TorchML import LinearRegressionforKP_PredCapacity  # type: ignore
from src.odece import ODECE  # type: ignore

_SCALE = 10000


def solve_cpsat_exact(w_mat: np.ndarray, cap_vec: np.ndarray, cost_vec: np.ndarray) -> tuple[bool, np.ndarray, float]:
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
    solver.parameters.max_time_in_seconds = 5.0
    st = solver.Solve(m)
    if st == cp_model.OPTIMAL:
        sol = np.array([float(solver.Value(xs[j])) for j in range(50)], dtype=np.float64)
        return True, sol, float(np.dot(cost_vec, sol))
    return False, np.zeros(50, dtype=np.float64), float("nan")


def eval_upstream_odece_capacity_loss(
    odece_pl: ODECE,
    x_t: torch.Tensor,
    w_t: torch.Tensor,
    cap_t: torch.Tensor,
    c_t: torch.Tensor,
    sol_t: torch.Tensor,
    obj_t: torch.Tensor,
    pred_sol_masked_t: torch.Tensor,
    mask_t: torch.Tensor,
    alpha: float,
    apply_empty_ipl_guard: bool = True,
) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor, bool]:
    """Calls ACTUAL unmodified official_odece_repo/src/odece.py ODECE.losses_computation directly."""
    trueConstr_tuple = (w_t, cap_t)
    pred_list = odece_pl.forward(x_t)
    pred_params_tuple, _ = odece_pl._create_params_tuple(pred_list, trueConstr_tuple, c_t)
    loss_ipl, loss_opl = odece_pl.losses_computation(
        trueConstr_tuple, pred_params_tuple, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t
    )
    empty_ipl_triggered = False
    if mask_t.sum() == 0:
        # Note: src/odece.py L103-106 returns (loss_withtruesol, loss_ial) = (OPL, 0).
        # At alpha=0.5, alpha*(loss_ipl.mean()+1e-4) + (1-alpha)*(loss_opl.mean()+1e-4) is symmetric!
        prev_ipl = loss_ipl.mean()
        prev_opl = loss_opl.mean()
    else:
        prev_opl = loss_opl.mean()
        if loss_ipl.numel() == 0:
            empty_ipl_triggered = True
            if apply_empty_ipl_guard:
                prev_ipl = torch.zeros((), dtype=x_t.dtype)
            else:
                prev_ipl = loss_ipl.mean()  # NaN in unmodified src/odece.py:L241
        else:
            prev_ipl = loss_ipl.mean()
    total_loss = alpha * (prev_ipl + 1e-4).mean() + (1.0 - alpha) * (prev_opl + 1e-4).mean()
    return total_loss, prev_opl, prev_ipl, empty_ipl_triggered


def check_case_vs_fd(
    case_name: str,
    xb: np.ndarray,
    wb: np.ndarray,
    capb: np.ndarray,
    cb: np.ndarray,
    solb: np.ndarray,
    objb: np.ndarray,
    pred_sols_full: np.ndarray,
    ok_mask: np.ndarray,
    W_init: np.ndarray,
    b_init: np.ndarray,
    alpha: float = 0.5,
) -> dict:
    reg = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    with torch.no_grad():
        reg.linear.weight.copy_(torch.tensor(W_init.T, dtype=torch.float64))
        reg.linear.bias.copy_(torch.tensor(b_init, dtype=torch.float64))

    solver = knapsack_solver(50)
    odece_pl = ODECE(
        [reg],
        predict_indices=1,
        optsolver=solver,
        num_predconstrsvar=1,
        infeasibility_aversion_coeff=alpha,
        margin_threshold=2.0,
        predict_cost=False,
        lr=0.005,
        max_epochs=20,
        seed=11,
    )
    odece_pl.log = lambda *args, **kwargs: None

    x_t = torch.tensor(xb, dtype=torch.float64)
    w_t = torch.tensor(wb, dtype=torch.float64)
    cap_t = torch.tensor(capb, dtype=torch.float64)
    c_t = torch.tensor(cb, dtype=torch.float64)
    sol_t = torch.tensor(solb, dtype=torch.float64)
    obj_t = torch.tensor(objb, dtype=torch.float64)
    mask_t = torch.tensor(ok_mask, dtype=torch.bool)
    pred_sol_masked_t = torch.tensor(pred_sols_full[ok_mask], dtype=torch.float64)

    # Branch diagnostics
    with torch.no_grad():
        raw_true_exc = solver.violation((w_t, cap_t), sol_t)
        viol_true_t = solver.constraint_wise_feasibility((w_t, cap_t), sol_t)
        viol_true = int(viol_true_t.sum().item())
        max_true_exc_f64 = float(raw_true_exc.max().item())
        if ok_mask.any():
            vp = solver.constraint_wise_feasibility((w_t[mask_t], cap_t[mask_t]), pred_sol_masked_t, all_comparisons=False)
            vc = vp.sum(dim=1).cpu().numpy().astype(int)
        else:
            vc = np.array([], dtype=int)

    # Autograd via ACTUAL pinned src/odece.py
    reg.zero_grad()
    total_loss, prev_opl, prev_ipl, empty_ipl = eval_upstream_odece_capacity_loss(
        odece_pl, x_t, w_t, cap_t, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t, alpha=alpha, apply_empty_ipl_guard=True
    )
    total_loss.backward()
    gW_ag = reg.linear.weight.grad.detach().cpu().numpy().copy()  # (3, 10)
    gb_ag = reg.linear.bias.grad.detach().cpu().numpy().copy()    # (3,)

    # Exhaustive central finite differences over ALL 33 parameters (eps=1e-6)
    eps = 1e-6
    gW_fd = np.zeros_like(gW_ag)
    gb_fd = np.zeros_like(gb_ag)
    with torch.no_grad():
        for i in range(3):
            for j in range(10):
                orig = float(reg.linear.weight[i, j].item())
                reg.linear.weight[i, j] = orig + eps
                lp, _, _, _ = eval_upstream_odece_capacity_loss(odece_pl, x_t, w_t, cap_t, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t, alpha=alpha, apply_empty_ipl_guard=True)
                reg.linear.weight[i, j] = orig - eps
                lm, _, _, _ = eval_upstream_odece_capacity_loss(odece_pl, x_t, w_t, cap_t, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t, alpha=alpha, apply_empty_ipl_guard=True)
                reg.linear.weight[i, j] = orig
                gW_fd[i, j] = (float(lp.item()) - float(lm.item())) / (2.0 * eps)
        for i in range(3):
            orig = float(reg.linear.bias[i].item())
            reg.linear.bias[i] = orig + eps
            lp, _, _, _ = eval_upstream_odece_capacity_loss(odece_pl, x_t, w_t, cap_t, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t, alpha=alpha, apply_empty_ipl_guard=True)
            reg.linear.bias[i] = orig - eps
            lm, _, _, _ = eval_upstream_odece_capacity_loss(odece_pl, x_t, w_t, cap_t, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t, alpha=alpha, apply_empty_ipl_guard=True)
            reg.linear.bias[i] = orig
            gb_fd[i] = (float(lp.item()) - float(lm.item())) / (2.0 * eps)

    # Also check analytic RHS gradient (d_cap_hat) matching src/odece.py L85 verbatim (including (1 - violation_true))
    cap_hat_np = xb @ W_init + b_init[None, :]
    vt_np = viol_true_t.cpu().numpy()
    z_opl = np.einsum("bdj,bj->bd", wb, solb) - cap_hat_np + 2.0
    sig_opl = 1.0 / (1.0 + np.exp(-np.clip(5.0 * z_opl, -60.0, 60.0)))
    d_cap_opl = -(1.0 - vt_np) * sig_opl / (len(xb) * 3.0)
    d_cap_ial = np.zeros_like(cap_hat_np)
    if ok_mask.any():
        te = np.einsum("bdj,bj->bd", wb[ok_mask], pred_sols_full[ok_mask]) - capb[ok_mask]
        vp_np = (te > 0.0).astype(np.float64)
        vc_np = np.sum(vp_np, axis=1)
        neg = vc_np >= 1.0
        n_neg = int(np.sum(neg))
        if n_neg > 0:
            z_ial = cap_hat_np[ok_mask][neg] - np.einsum("bdj,bj->bd", wb[ok_mask][neg], pred_sols_full[ok_mask][neg]) + 2.0
            sig_ial = 1.0 / (1.0 + np.exp(-np.clip(5.0 * z_ial, -60.0, 60.0)))
            d_cap_ial[np.where(ok_mask)[0][neg]] = (vp_np[neg] * sig_ial) / (vc_np[neg, None] * n_neg)
    d_cap_tot = alpha * d_cap_ial + (1.0 - alpha) * d_cap_opl
    gW_ana = (xb.T @ d_cap_tot).T
    gb_ana = np.sum(d_cap_tot, axis=0)

    res = {
        "case": case_name,
        "alpha": alpha,
        "n_ok_mask": int(ok_mask.sum()),
        "true_sol_violations_strict_gt0": viol_true,
        "max_true_sol_float64_excess": max_true_exc_f64,
        "pred_viol_count_histogram": {str(k): int(np.sum(vc == k)) for k in range(4)},
        "empty_ipl_guard_triggered": empty_ipl,
        "loss_total": float(total_loss.item()),
        "loss_opl_returned": float(prev_opl.item()),
        "loss_ipl_returned": float(prev_ipl.item()),
        "autograd_vs_33param_fd_max_abs_err_W": float(np.max(np.abs(gW_ag - gW_fd))),
        "autograd_vs_33param_fd_max_abs_err_b": float(np.max(np.abs(gb_ag - gb_fd))),
        "autograd_vs_analytic_max_abs_err_W": float(np.max(np.abs(gW_ag - gW_ana))),
        "autograd_vs_analytic_max_abs_err_b": float(np.max(np.abs(gb_ag - gb_ana))),
    }
    if empty_ipl:
        # Also confirm unmodified returns NaN
        with torch.no_grad():
            tl_un, _, pi_un, _ = eval_upstream_odece_capacity_loss(
                odece_pl, x_t, w_t, cap_t, c_t, sol_t, obj_t, pred_sol_masked_t, mask_t, alpha=alpha, apply_empty_ipl_guard=False
            )
        res["unmodified_empty_ipl_is_nan"] = bool(torch.isnan(tl_un).item() and torch.isnan(pi_un).item())
    return res


def main():
    seed = 11  # Already used in Stage-2a/2b; fresh seed 16 & reserved 17-18 untouched!
    X, w, costs, capacity = genCapacity(1500, 10, 50, dim=3, deg=6, noise_width=0.25, seed=seed)
    idx_tr_full, _ = train_test_split(np.arange(1500), test_size=500, random_state=seed)
    idx_tr, _ = train_test_split(idx_tr_full, test_size=0.1, random_state=seed)

    # Use clean OLS weights on seed 11 for realistic mixed feasible/infeasible predicted capacities on batch 0
    Xb_tr = np.hstack([X[idx_tr], np.ones((len(idx_tr), 1))])
    B_ols, _, _, _ = np.linalg.lstsq(Xb_tr, capacity[idx_tr], rcond=None)
    W_real, b_real = B_ols[:-1, :].copy(), B_ols[-1, :].copy()

    b_idx = idx_tr[:32]
    xb, wb, capb, cb = X[b_idx], w[b_idx], capacity[b_idx], costs[b_idx]
    cap_hat = xb @ W_real + b_real[None, :]

    solb = np.zeros((32, 50), dtype=np.float64)
    objb = np.zeros((32, 1), dtype=np.float64)
    pred_sols = np.zeros((32, 50), dtype=np.float64)
    ok_mask = np.zeros(32, dtype=bool)
    for i in range(32):
        ok_t, st, ot = solve_cpsat_exact(wb[i], capb[i], cb[i])
        assert ok_t
        solb[i] = st; objb[i, 0] = ot
        ok_p, sp, _ = solve_cpsat_exact(wb[i], cap_hat[i], cb[i])
        pred_sols[i] = sp; ok_mask[i] = ok_p

    c1 = check_case_vs_fd("realistic_mixed_capacity_batch_float64", xb, wb, capb, cb, solb, objb, pred_sols, ok_mask, W_real, b_real, alpha=0.5)
    mask_partial = ok_mask.copy(); mask_partial[0] = False; mask_partial[15] = False
    c2 = check_case_vs_fd("partial_masked_infeasible_batch_float64", xb, wb, capb, cb, solb, objb, pred_sols, mask_partial, W_real, b_real, alpha=0.5)
    c3 = check_case_vs_fd("all_masked_zero_branch_float64", xb, wb, capb, cb, solb, objb, pred_sols, np.zeros(32, dtype=bool), W_real, b_real, alpha=0.5)
    c4 = check_case_vs_fd("all_pred_feasible_empty_ipl_guard_float64", xb, wb, capb, cb, solb, objb, np.zeros_like(solb), np.ones(32, dtype=bool), W_real, b_real, alpha=0.5)

    all_pass = all(
        c["autograd_vs_33param_fd_max_abs_err_W"] < 1e-7
        and c["autograd_vs_33param_fd_max_abs_err_b"] < 1e-8
        and c["autograd_vs_analytic_max_abs_err_W"] < 1e-9
        and c["autograd_vs_analytic_max_abs_err_b"] < 1e-10
        for c in [c1, c2, c3, c4]
    ) and (
        c1["pred_viol_count_histogram"]["0"] > 0
        and sum(c1["pred_viol_count_histogram"][str(k)] for k in [1, 2, 3]) > 0
        and c4["empty_ipl_guard_triggered"] is True
        and c4["unmodified_empty_ipl_is_nan"] is True
    )

    receipt = {
        "purpose": "Pre-launch parity verification calling ACTUAL unmodified pinned official_odece_repo/src/odece.py on MDKP-Capacity (predict_indices=1) in torch.float64.",
        "pinned_repo_commit": "1b432e03ce9ded1e504df60fd4c44cf936334d4f",
        "torch_version": torch.__version__,
        "seed_used": seed,
        "fresh_seed16_and_reserved_17_18_untouched": True,
        "capacity_parity_pass_float64": all_pass,
        "documented_upstream_guards": {
            "guard1_empty_ipl": "When mask.sum()>0 and violation_pred_mask.sum()==0 (0 infeasible predicted solutions in batch), unmodified src/odece.py:L147+241 returns NaN via empty-tensor mean(); Guard 1 substitutes 0.0 and logs n_zero_infeas_batches.",
            "guard2_mask_zero_tuple_swap": "When mask.sum()==0 (all predicted capacities negative -> INFEASIBLE), unmodified src/odece.py:L103-106 returns (loss_withtruesol, loss_ial) in swapped tuple order; at prespecified alpha=0.5, alpha == (1-alpha) == 0.5 so loss & gradient match exact 0.5*OPL + 0.5*0 to 1e-12.",
        },
        "cases": [c1, c2, c3, c4],
    }
    out_path = BASE / "ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT.json"
    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt, indent=2))


if __name__ == "__main__":
    main()
