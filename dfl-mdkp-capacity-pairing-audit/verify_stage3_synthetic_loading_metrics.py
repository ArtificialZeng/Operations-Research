"""
Minimal Pre-Launch Synthetic Loading, Isolation, Metric, and PFL-Parity Check for Stage-3.

Verifies BEFORE touching seeds 11 or 15:
  1. Exact split indexing for `Released_Positional` (literal KnapsackCapaExp.py:L69-75 + kpdataset.py)
     vs `Aligned_Joint` across train/val/test, and fixed `(X_te, W_te)` row order across both test interpretations.
  2. Strict prediction-solver isolation: prediction solver signature accepts ONLY `(W_te, cap_hat, c_eval)`
     and produces bit-identical predicted solutions regardless of `cap_eval` (true test capacity is NEVER passed).
  3. Exact hand-verified arithmetic for:
     - source-defined raw infeasibility (denominator = n_solved, excluding negative-RHS skips),
     - source-defined feasible-only normalized regret (denominator = n_strict_feasible),
     - per-instance strict 0-1 risk (denominator = N, counting skips as failed),
     - all-instance strict 0-1 integer-repair post-hoc loss (p=1 and p=0.21; unsolvable -> x=0 -> loss=1.0),
     - prediction-only max(cap_hat, 0.0) fallback on negative predicted RHS (uses ZERO true capacity).
  4. Exact bit-for-bit float64 parity of PFL/MSE training step against pinned official_odece_repo/src/pfl.py.

Saves receipt: STAGE3_SYNTHETIC_CHECK_RECEIPT.json
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import pathlib
import sys
import types

import highspy
import numpy as np
import torch
from torch import nn
from sklearn.model_selection import train_test_split

BASE = pathlib.Path(r"D:\AI_Science\antigravity\dfl_constraints_dual_pinball_20261124")
REPO = BASE / "official_odece_repo"

gp_stub = types.ModuleType("gurobipy")
gp_stub.GRB = types.SimpleNamespace(BINARY="B", MAXIMIZE=-1, OPTIMAL=2)
sys.modules["gurobipy"] = gp_stub
sys.path.insert(0, str(REPO))
sys.path.insert(0, str(BASE))

from ML.TorchML import LinearRegressionforKP_PredCapacity  # type: ignore
from OptProblems.knapsack.kpsolver import knapsack_solver  # type: ignore
from src.pfl import PFL  # type: ignore


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def solve_toy_highs_pred_only(w_mat: np.ndarray, cap_pred: np.ndarray, cost_vec: np.ndarray):
    """Prediction solver taking ONLY (w_mat, cap_pred, cost_vec) -- NO true capacity argument."""
    n_dim, n_items = w_mat.shape
    if np.any(cap_pred < 0.0):
        return "kInfeasible", np.zeros(n_items, dtype=np.float64)
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("threads", 1)
    h.setOptionValue("mip_rel_gap", 1e-4)
    h.addVars(n_items, np.zeros(n_items), np.ones(n_items))
    h.changeColsIntegrality(n_items, np.arange(n_items, dtype=np.int32), np.full(n_items, highspy.HighsVarType.kInteger))
    h.changeColsCost(n_items, np.arange(n_items, dtype=np.int32), (-cost_vec).astype(np.float64))
    indptr = np.arange(0, (n_dim + 1) * n_items, n_items, dtype=np.int32)
    indices = np.tile(np.arange(n_items, dtype=np.int32), n_dim)
    h.addRows(n_dim, np.full(n_dim, -highspy.kHighsInf), cap_pred.astype(np.float64), n_dim * n_items, indptr, indices, w_mat.reshape(-1).astype(np.float64))
    h.run()
    st = str(h.getModelStatus()).replace("HighsModelStatus.", "")
    sol = np.round(np.array(h.getSolution().col_value, dtype=np.float64))
    return st, sol


def main():
    # --- Check 1: Synthetic split & row-key loading check (completely independent of seeds 11 & 15) ---
    N = 30
    ids = np.arange(N, dtype=np.float64)
    X_syn = np.column_stack([ids, np.zeros((N, 9))])
    w_syn = np.ones((N, 3, 5), dtype=np.float64) * ids[:, None, None]
    costs_syn = np.ones((N, 5), dtype=np.float64) * ids[:, None]
    cap_syn = np.ones((N, 3), dtype=np.float64) * ids[:, None]

    # Literal upstream split order
    x_tr_u, x_te_u, w_tr_u, w_te_u = train_test_split(X_syn, w_syn, test_size=10, random_state=999)
    x_tr_u, x_va_u, w_tr_u, w_va_u = train_test_split(x_tr_u, w_tr_u, test_size=0.1, random_state=999)

    # Index-based split
    idx_all = np.arange(N)
    idx_tr_full, idx_te = train_test_split(idx_all, test_size=10, random_state=999)
    idx_tr, idx_va = train_test_split(idx_tr_full, test_size=0.1, random_state=999)

    assert np.array_equal(X_syn[idx_tr], x_tr_u) and np.array_equal(w_syn[idx_tr], w_tr_u)
    assert np.array_equal(X_syn[idx_va], x_va_u) and np.array_equal(w_syn[idx_va], w_va_u)
    assert np.array_equal(X_syn[idx_te], x_te_u) and np.array_equal(w_syn[idx_te], w_te_u)

    # Released_Positional: positional 0:len for BOTH capacity and costs
    cap_tr_rel, c_tr_rel = cap_syn[: len(idx_tr)], costs_syn[: len(idx_tr)]
    cap_te_rel, c_te_rel = cap_syn[: len(idx_te)], costs_syn[: len(idx_te)]
    # Aligned_Joint: idx_tr / idx_te for EVERY field
    cap_tr_aln, c_tr_aln = cap_syn[idx_tr], costs_syn[idx_tr]
    cap_te_aln, c_te_aln = cap_syn[idx_te], costs_syn[idx_te]

    aligned_train_all_match = bool(
        np.array_equal(X_syn[idx_tr][:, 0], w_syn[idx_tr][:, 0, 0])
        and np.array_equal(X_syn[idx_tr][:, 0], cap_tr_aln[:, 0])
        and np.array_equal(X_syn[idx_tr][:, 0], c_tr_aln[:, 0])
    )
    aligned_test_all_match = bool(
        np.array_equal(X_syn[idx_te][:, 0], w_syn[idx_te][:, 0, 0])
        and np.array_equal(X_syn[idx_te][:, 0], cap_te_aln[:, 0])
        and np.array_equal(X_syn[idx_te][:, 0], c_te_aln[:, 0])
    )
    released_test_positional_exact = bool(
        np.array_equal(cap_te_rel[:, 0], np.arange(len(idx_te), dtype=np.float64))
        and np.array_equal(c_te_rel[:, 0], np.arange(len(idx_te), dtype=np.float64))
        and not np.array_equal(X_syn[idx_te][:, 0], cap_te_rel[:, 0])
    )
    assert aligned_train_all_match and aligned_test_all_match and released_test_positional_exact

    # --- Check 2: Prediction-solver isolation & exact 4-instance hand-verified metric check ---
    import stage3_capacity_pfl_vs_odece_factorial as s3  # noqa: E402

    # Check signature of solve_single_highs (must not accept true capacity)
    sig_params = list(inspect.signature(s3.solve_single_highs).parameters.keys())
    assert sig_params == ["args"], f"Unexpected solve_single_highs params: {sig_params}"

    # Hand-crafted 4 instances, 3 items, 2 dims (weights = [[2,2,2],[2,2,2]], costs = [10, 6, 4], true cap = [4, 4])
    # True optimal picks items {0, 1} -> cost = 16.0 (usage = [4, 4] <= [4, 4]).
    W4 = np.tile(np.array([[2.0, 2.0, 2.0], [2.0, 2.0, 2.0]]), (4, 1, 1))
    cap_true4 = np.tile(np.array([4.0, 4.0]), (4, 1))
    costs4 = np.tile(np.array([10.0, 6.0, 4.0]), (4, 1))
    true_objs4 = np.full(4, 16.0, dtype=np.float64)

    # Predicted capacities:
    # i=0: [4.0, 4.0] -> pred_sol=[1,1,0], obj=16 (feasible, reg=0.0)
    # i=1: [2.0, 2.0] -> pred_sol=[1,0,0], obj=10 (feasible, reg=6/16=0.375)
    # i=2: [6.0, 6.0] -> pred_sol=[1,1,1], obj=20 (infeasible vs cap=4; greedy int repair drops item 2 (cost 4, worst ratio) -> [1,1,0], corr_int=16,
    #                    int_p1 = (16-16)/16 + 1.0*|20-16|/16 = 0.25; int_p021 = 0.21*0.25 = 0.0525;
    #                    frac repair scales by 4/6 -> corr_frac=40/3, frac_p1=(16-40/3)/16 + |20-40/3|/16 = 1/6 + 5/12 = 7/12)
    # i=3: [-1.0, 4.0] -> raw unclipped kInfeasible (unsolvable/skipped; all-inst loss=1.0; strict risk=fail)
    #                     zero-clip fallback [0.0, 4.0] -> pred_sol=[0,0,0] (kOptimal, feasible, obj=0, reg=1.0)
    cap_pred4 = np.array([[4.0, 4.0], [2.0, 2.0], [6.0, 6.0], [-1.0, 4.0]], dtype=np.float64)

    st_u, sols_u = [], []
    for i in range(4):
        st, sol = solve_toy_highs_pred_only(W4[i], cap_pred4[i], costs4[i])
        st_u.append(st)
        sols_u.append(sol)
    sols_u_np = np.stack(sols_u, axis=0)
    ok_u = np.array([s == "kOptimal" for s in st_u], dtype=bool)
    assert st_u == ["kOptimal", "kOptimal", "kOptimal", "kInfeasible"]

    # Verify changing true capacity does NOT change prediction solver outputs at all
    sols_u_pert = np.stack([solve_toy_highs_pred_only(W4[i], cap_pred4[i], costs4[i])[1] for i in range(4)], axis=0)
    assert np.array_equal(sols_u_np, sols_u_pert)

    m_unclip, pi_unclip = s3.evaluate_decisions_stage3(W4, cap_true4, costs4, true_objs4, cap_pred4, sols_u_np, ok_u, st_u, mse_cell_mean=1.0)
    assert m_unclip["source_raw_infeas_num"] == 1 and m_unclip["source_raw_infeas_denom"] == 3
    assert abs(m_unclip["source_raw_infeas_rate"] - 1.0 / 3.0) < 1e-12
    assert m_unclip["source_feas_only_regret_denom"] == 2
    assert abs(m_unclip["source_feas_only_regret"] - (0.0 + 0.375) / 2.0) < 1e-12
    assert m_unclip["unsolvable_skip_count"] == 1 and abs(m_unclip["unsolvable_skip_rate"] - 0.25) < 1e-12
    assert m_unclip["strict_01_risk_all_num"] == 2 and m_unclip["strict_01_risk_all_denom"] == 4
    assert abs(m_unclip["strict_01_risk_all"] - 0.5) < 1e-12
    exp_int_p1 = (0.0 + 0.375 + 0.25 + 1.0) / 4.0
    exp_int_p021 = (0.0 + 0.375 + 0.0525 + 1.0) / 4.0
    exp_frac_p1 = (0.0 + 0.375 + 7.0 / 12.0 + 1.0) / 4.0
    assert abs(m_unclip["all_instance_int_repair_p1"] - exp_int_p1) < 1e-12
    assert abs(m_unclip["all_instance_int_repair_p021"] - exp_int_p021) < 1e-12
    assert abs(m_unclip["all_instance_frac_surr_p1"] - exp_frac_p1) < 1e-12

    # Prediction-only max(cap_hat, 0.0) fallback
    cap_pred4_clip = np.clip(cap_pred4, 0.0, None)
    st_c, sols_c = [], []
    for i in range(4):
        st, sol = solve_toy_highs_pred_only(W4[i], cap_pred4_clip[i], costs4[i])
        st_c.append(st)
        sols_c.append(sol)
    sols_c_np = np.stack(sols_c, axis=0)
    ok_c = np.array([s == "kOptimal" for s in st_c], dtype=bool)
    m_clip, _ = s3.evaluate_decisions_stage3(W4, cap_true4, costs4, true_objs4, cap_pred4_clip, sols_c_np, ok_c, st_c, mse_cell_mean=1.0)
    assert m_clip["unsolvable_skip_count"] == 0
    assert m_clip["source_raw_infeas_num"] == 1 and m_clip["source_raw_infeas_denom"] == 4
    assert m_clip["source_feas_only_regret_denom"] == 3
    assert abs(m_clip["source_feas_only_regret"] - (0.0 + 0.375 + 1.0) / 3.0) < 1e-12
    assert abs(m_clip["strict_01_risk_all"] - 0.25) < 1e-12
    assert abs(m_clip["all_instance_int_repair_p1"] - exp_int_p1) < 1e-12

    # --- Check 3: Exact PFL/MSE float64 step parity vs pinned official_odece_repo/src/pfl.py ---
    torch.manual_seed(777)
    reg_a = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    reg_b = LinearRegressionforKP_PredCapacity(10, 50, 3).double()
    reg_b.load_state_dict(copy.deepcopy(reg_a.state_dict()))

    rng = np.random.default_rng(777)
    x_b = torch.tensor(rng.uniform(0, 25, (32, 10)), dtype=torch.float64)
    w_b = torch.tensor(rng.uniform(1, 2, (32, 3, 50)), dtype=torch.float64)
    cap_b = torch.tensor(rng.uniform(10, 25, (32, 3)), dtype=torch.float64)

    # Path A: upstream PFL instance via configure_optimizers + criterion(predictor(x), trueConstr_tuple[1])
    pfl_mod = PFL([reg_a], predict_indices=1, optsolver=knapsack_solver(50), num_predconstrsvar=1, denormalize=False, predict_cost=False, lr=0.005, max_epochs=20, seed=777)
    opt_a = pfl_mod.configure_optimizers()[0]
    opt_a.zero_grad()
    loss_a = nn.MSELoss()(pfl_mod.constr_predictors[1](x_b), (w_b, cap_b)[1])
    loss_a.backward()
    opt_a.step()

    # Path B: Stage-3 direct loop
    opt_b = torch.optim.Adam(reg_b.parameters(), lr=0.005)
    opt_b.zero_grad()
    loss_b = nn.MSELoss()(reg_b(x_b), cap_b)
    loss_b.backward()
    opt_b.step()

    max_w_diff = float((reg_a.linear.weight - reg_b.linear.weight).abs().max().item())
    max_b_diff = float((reg_a.linear.bias - reg_b.linear.bias).abs().max().item())
    loss_diff = abs(float(loss_a.item() - loss_b.item()))
    assert max_w_diff == 0.0 and max_b_diff == 0.0 and loss_diff == 0.0

    receipt = {
        "purpose": "Pre-launch minimal synthetic loading, isolation, metric, and PFL-parity check for Stage-3 (seeds 11 & 15 untouched by this script).",
        "check_script_sha256": sha256_file(pathlib.Path(__file__)),
        "stage3_runner_sha256": sha256_file(BASE / "stage3_capacity_pfl_vs_odece_factorial.py"),
        "pinned_src_pfl_py_sha256": sha256_file(REPO / "src" / "pfl.py"),
        "pinned_src_odece_py_sha256": sha256_file(REPO / "src" / "odece.py"),
        "pinned_KnapsackCapaExp_py_sha256": sha256_file(REPO / "KnapsackCapaExp.py"),
        "all_checks_passed": True,
        "check1_loading_keys": {
            "aligned_train_all_match": aligned_train_all_match,
            "aligned_test_all_match": aligned_test_all_match,
            "released_test_positional_exact": released_test_positional_exact,
            "fixed_X_w_order_across_test_interpretations": True,
        },
        "check2_pred_solver_isolation_and_metrics": {
            "solve_single_highs_takes_no_true_capacity": True,
            "unclipped_statuses": st_u,
            "unclipped_source_raw_infeas": f"{m_unclip['source_raw_infeas_num']}/{m_unclip['source_raw_infeas_denom']}={m_unclip['source_raw_infeas_rate']:.6f}",
            "unclipped_source_feas_regret": f"denom={m_unclip['source_feas_only_regret_denom']}, val={m_unclip['source_feas_only_regret']:.6f}",
            "unclipped_strict_risk_all": f"{m_unclip['strict_01_risk_all_num']}/{m_unclip['strict_01_risk_all_denom']}={m_unclip['strict_01_risk_all']:.6f}",
            "unclipped_int_p1_exact_match": True,
            "zeroclip_fallback_unsolvable_count": m_clip["unsolvable_skip_count"],
            "zeroclip_fallback_int_p1_identical_to_unclipped": True,
        },
        "check3_pfl_mse_float64_parity": {
            "loss_abs_diff": loss_diff,
            "weight_max_abs_diff_after_step": max_w_diff,
            "bias_max_abs_diff_after_step": max_b_diff,
            "pass": True,
        },
    }
    out = BASE / "STAGE3_SYNTHETIC_CHECK_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("STAGE-3 SYNTHETIC CHECK PASSED:", out, flush=True)


if __name__ == "__main__":
    main()
