"""Cold single-tree lazy integer linked Benders worker on Diaz p26 (OR-Tools GSCIP).

Strictly zero leakage: this worker NEVER opens or reads any prior seed, layout,
or sealed optimum file. It loads only `p26` via `experiments/linked_root/run_root.py`
and executes three cold, resource-matched binary MIP arms inside ONE GSCIP solve
each (`solve_calls == 1`, zero outer MIP restarts) on the identical proportional-arc
linked polytope (`y_{sij} <= x_i d_{sj}`):
  - `orig_single`:      plain original-price single-cut lazy comparator.
  - `orig_multi_floor`: strong original-price multi-cut baseline with direct valid
                        per-scenario floor theta_s >= (rho-eta)*(D_s - sum min(u_i,D_s)x_i)/div
                        (no extra hinge variables, no double charging).
  - `sep_single_hinge`: candidate separated residual single-cut arm with 200 upfront
                        scalar shortage hinges priced at (rho-eta)/div.

Post-run exact original-price repricing (via frozen `experiments/liu_lost_sales/solve.py:verify`)
and comparison against the separately sealed p26 optimum live strictly in the separate
script `evaluate_p26_integer_run.py`.
"""

from __future__ import annotations

import os

for _env_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_env_var, "1")

import argparse
from datetime import timedelta
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys
from time import perf_counter
import warnings

import numpy as np
from ortools.math_opt.python import mathopt
from scipy.optimize import OptimizeWarning, linprog
from scipy.sparse import coo_array

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
LINKED_ROOT_DIR = REPO_ROOT / "experiments" / "linked_root"
PILOT_ARCHIVE_DIR = REPO_ROOT / "antigravity" / "native_linked_root_execution_20261124"
for _p in (str(LINKED_ROOT_DIR), str(PILOT_ARCHIVE_DIR)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from certify import OPEN_GRID, certify
from linked_benders_pilot import ArmContext, CandidateEval, build_arm_context, evaluate_candidate
from run_root import load_case

ARM_SPECS = (
    ("orig_single", "linked", "single", False),
    ("orig_multi_floor", "linked", "multi", True),
    ("sep_single_hinge", "linked_separated", "single", False),
)


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _bits_key(x_bin: np.ndarray) -> str:
    return "".join("1" if int(v) == 1 else "0" for v in x_bin)


def build_input_only_cold_seed(data) -> np.ndarray:
    """Deterministic binary seed built solely from model inputs (capacities, openings, peak demand)."""
    n = len(data.capacities) - 1
    caps = [int(data.capacities[i]) for i in range(n)]
    openings = [Fraction(data.opening[i]) for i in range(n)]
    peak = int(np.asarray(data.demands, dtype=np.int64).sum(axis=1).max())
    order = sorted(range(n), key=lambda i: (openings[i] / caps[i], i))
    x_seed = np.zeros(n, dtype=np.int64)
    total_cap = 0
    for i in order:
        x_seed[i] = 1
        total_cap += caps[i]
        if total_cap >= peak:
            break
    if total_cap < peak:
        raise ValueError("Model capacities cannot cover peak demand even with all facilities open")
    return x_seed


def _solve_lp_quiet(c, *, A_ub=None, b_ub=None, bounds=None, time_limit=15.0):
    t_cap = float(max(0.05, time_limit))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=OptimizeWarning, message=r"Unrecognized options.*")
        res = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            bounds=bounds,
            method="highs-ds",
            options={"threads": 1, "time_limit": t_cap},
        )
        if res.status != 0 and res.status != 1:
            res = linprog(
                c,
                A_ub=A_ub,
                b_ub=b_ub,
                bounds=bounds,
                method="highs",
                options={"threads": 1, "time_limit": t_cap},
            )
    return res


def certify_grid_primal_fallback(data, ctx_orig: ArmContext, x_bin: np.ndarray) -> dict:
    """Feasible rational grid-repaired original-price upper fallback via frozen certify.py.

    Trimmed flow grid ticks are logged transparently and do not invalidate a repaired feasible flow.
    Exact zero incumbent gap qualification still requires full 200-scenario exact repricing in
    `evaluate_p26_integer_run.py` via `experiments/liu_lost_sales/solve.py:verify`.
    """
    x_f = x_bin.astype(np.float64)
    ev_orig, timed_out = evaluate_candidate(ctx_orig, x_f, perf_counter() + 60.0)
    if timed_out or ev_orig is None:
        raise RuntimeError("Failed to evaluate binary layout on original scenarios for grid fallback certification")
    cert = certify(
        data,
        x_f,
        ev_orig.shipping,
        ev_orig.alphas,
        ev_orig.betas,
        linked=True,
        shortage_marginals=None,
        eta=None,
    )
    is_binary = all(v in (0, OPEN_GRID) for v in cert["rounded_opening"])
    u_grid = Fraction(cert["original_same_primal"])
    l_fixed = Fraction(cert["lower"])
    if not is_binary:
        raise ArithmeticError("Certified incumbent rounded_opening is not strictly binary")
    if l_fixed > u_grid:
        raise ArithmeticError("Grid fallback exact lower exceeds exact repaired upper")
    return {
        "open_real_sites": [int(i) for i, v in enumerate(x_bin) if int(v) == 1],
        "open_count": int(x_bin.sum()),
        "bits": _bits_key(x_bin),
        "is_binary_opening": is_binary,
        "grid_repaired_original_upper": str(u_grid),
        "grid_repaired_original_upper_float": float(u_grid),
        "grid_fixed_x_lower": str(l_fixed),
        "trimmed_flow_grid_ticks": int(cert["trimmed_flow_grid_ticks"]),
        "certificate": cert,
    }


def certify_arm_cut_lp_lower(
    data,
    ctx: ArmContext,
    *,
    cut_mode: str,
    use_direct_floor: bool,
    floor_premium_price: float,
    cut_theta_idx: list[int],
    cut_a: list[float],
    cut_g: list[np.ndarray],
    cut_alphas: list[np.ndarray],
    cut_betas: list[np.ndarray],
    incumbent_x: np.ndarray,
    incumbent_shipping: np.ndarray,
) -> dict:
    """Certify an exact rational continuous-LP lower bound solely from this arm's cuts (+ direct floor / hinges)."""
    n, m, S = ctx.n, ctx.m, ctx.scenarios
    separated = ctx.eta_ticks is not None
    n_theta = 1 if cut_mode == "single" else S
    n_hinge = S if separated else 0
    n_vars = n + n_theta + n_hinge

    c_lp = np.empty(n_vars, dtype=np.float64)
    c_lp[:n] = ctx.opening_f
    c_lp[n : n + n_theta] = 1.0
    if separated:
        c_lp[n + n_theta :] = ctx.premium_price

    bounds = np.empty((n_vars, 2), dtype=np.float64)
    bounds[:, 0] = 0.0
    bounds[:, 1] = np.inf
    bounds[:n, 1] = 1.0

    row_parts: list[np.ndarray] = []
    col_parts: list[np.ndarray] = []
    val_parts: list[np.ndarray] = []
    rhs_parts: list[np.ndarray] = []
    row_cursor = 0

    # Separated arm hinge rows: -sum_i min(u_i, D_s) x_i - h_s <= -D_s.
    hinge_start = row_cursor
    if separated:
        h_ids = np.arange(row_cursor, row_cursor + S, dtype=np.int64)
        row_parts.extend([np.repeat(h_ids, n), h_ids])
        col_parts.extend([np.tile(np.arange(n, dtype=np.int64), S), n + n_theta + np.arange(S, dtype=np.int64)])
        val_parts.extend([-ctx.truncated_f.ravel(), np.full(S, -1.0, dtype=np.float64)])
        rhs_parts.append(-ctx.totals_f.copy())
        row_cursor += S

    # Amended A2 direct per-scenario floor rows (no extra hinge vars):
    # -floor_premium * sum_i min(u_i, D_s) x_i - theta_s <= -floor_premium * D_s.
    floor_start = row_cursor
    n_floor = S if (use_direct_floor and cut_mode == "multi" and not separated) else 0
    if n_floor > 0:
        f_ids = np.arange(row_cursor, row_cursor + S, dtype=np.int64)
        row_parts.extend([np.repeat(f_ids, n), f_ids])
        col_parts.extend([np.tile(np.arange(n, dtype=np.int64), S), n + np.arange(S, dtype=np.int64)])
        val_parts.extend([-(floor_premium_price * ctx.truncated_f).ravel(), np.full(S, -1.0, dtype=np.float64)])
        rhs_parts.append(-(floor_premium_price * ctx.totals_f))
        row_cursor += S

    # Generated Benders cut rows: sum_i g_i x_i - theta_idx <= -a.
    cut_start = row_cursor
    n_cuts = len(cut_a)
    if n_cuts > 0:
        c_ids = np.arange(row_cursor, row_cursor + n_cuts, dtype=np.int64)
        row_parts.extend([np.repeat(c_ids, n), c_ids])
        col_parts.extend(
            [np.tile(np.arange(n, dtype=np.int64), n_cuts), n + np.asarray(cut_theta_idx, dtype=np.int64)]
        )
        val_parts.extend([np.asarray(cut_g, dtype=np.float64).ravel(), np.full(n_cuts, -1.0, dtype=np.float64)])
        rhs_parts.append(-np.asarray(cut_a, dtype=np.float64))
        row_cursor += n_cuts

    if row_cursor == 0:
        A_ub, b_ub = None, None
    else:
        A_ub = coo_array(
            (np.concatenate(val_parts), (np.concatenate(row_parts), np.concatenate(col_parts))),
            shape=(row_cursor, n_vars),
        ).tocsc()
        b_ub = np.concatenate(rhs_parts)

    res = _solve_lp_quiet(c_lp, A_ub=A_ub, b_ub=b_ub, bounds=bounds, time_limit=15.0)
    if res.status != 0:
        raise RuntimeError(f"Cut-pool LP certification solve failed (status={res.status}, msg={res.message})")

    ineq = (
        np.asarray(res.ineqlin.marginals, dtype=np.float64)
        if row_cursor > 0 and res.ineqlin is not None and res.ineqlin.marginals is not None
        else np.zeros(0, dtype=np.float64)
    )
    shortage_m = ineq[hinge_start : hinge_start + S].copy() if separated else None
    w_floor = np.maximum(0.0, -ineq[floor_start : floor_start + n_floor]) if n_floor > 0 else np.zeros(0)
    w_cuts = np.maximum(0.0, -ineq[cut_start : cut_start + n_cuts]) if n_cuts > 0 else np.zeros(0)

    bar_alpha = np.zeros((S, m), dtype=np.float64)
    bar_beta = np.zeros((S, n), dtype=np.float64)

    if cut_mode == "single":
        w_sum = float(w_cuts.sum())
        scale = (1.0 / w_sum) if w_sum > 1.0 else 1.0
        for r in range(n_cuts):
            wr = float(w_cuts[r]) * scale
            if wr > 0.0:
                bar_alpha += wr * cut_alphas[r]
                bar_beta += wr * cut_betas[r]
    else:
        # Exact valid dual pair dominating direct floor floor_premium_price * (D_s - sum min(u_i, D_s) x_i):
        # alpha_fl[s, j] = floor_premium_price <= rho/div; beta_fl[s, i] = -floor_premium_price if u_i <= D_s else 0.
        alpha_fl = np.full((S, m), floor_premium_price, dtype=np.float64)
        beta_fl = np.where(ctx.caps_f[None, :] <= ctx.totals_f[:, None], -floor_premium_price, 0.0)
        by_scen: list[list[int]] = [[] for _ in range(S)]
        for r in range(n_cuts):
            by_scen[cut_theta_idx[r]].append(r)
        for s in range(S):
            wf = float(w_floor[s]) if n_floor > 0 else 0.0
            idxs = by_scen[s]
            ws = w_cuts[idxs] if idxs else np.zeros(0, dtype=np.float64)
            total_w = wf + float(ws.sum())
            scale = (1.0 / total_w) if total_w > 1.0 else 1.0
            if wf > 0.0:
                bar_alpha[s] += (wf * scale) * alpha_fl[s]
                bar_beta[s] += (wf * scale) * beta_fl[s]
            for r, wr_raw in zip(idxs, ws, strict=True):
                wr = float(wr_raw) * scale
                if wr > 0.0:
                    bar_alpha[s] += wr * cut_alphas[r]
                    bar_beta[s] += wr * cut_betas[r]

    cert = certify(
        data,
        incumbent_x.astype(np.float64),
        incumbent_shipping,
        bar_alpha,
        bar_beta,
        linked=True,
        shortage_marginals=shortage_m,
        eta=ctx.eta_ticks,
    )
    l_exact = Fraction(cert["lower"])
    return {
        "numeric_cut_pool_lp_objective": float(res.fun) + ctx.dummy_opening_f,
        "exact_certified_cut_lp_lower": str(l_exact),
        "exact_certified_cut_lp_lower_float": float(l_exact),
        "certificate_used_for_lower": cert,
    }


def run_single_tree_arm(
    data,
    ctx: ArmContext,
    ctx_orig: ArmContext,
    *,
    arm_name: str,
    cut_mode: str,
    use_direct_floor: bool,
    floor_premium_price: float,
    x_seed: np.ndarray,
    time_limit: float,
    cut_tol: float,
    rel_gap_tol: float,
) -> dict:
    """Run one cold single-tree GSCIP binary Benders arm without reading any external optima or layouts."""
    t_start = perf_counter()
    deadline = t_start + time_limit
    n, S = ctx.n, ctx.scenarios
    separated = ctx.eta_ticks is not None

    # 1. Equally charged deterministic input-only cold seed evaluation inside arm budget.
    seed_ev, seed_to = evaluate_candidate(ctx, x_seed.astype(np.float64), deadline)
    if seed_to or seed_ev is None:
        raise RuntimeError(f"Arm {arm_name} timed out during initial cold seed evaluation")
    seed_elapsed = perf_counter() - t_start

    eval_cache: dict[str, CandidateEval] = {_bits_key(x_seed): seed_ev}
    best_x_bin = x_seed.copy()
    best_ev: CandidateEval = seed_ev
    best_found_elapsed = seed_elapsed

    cut_theta_idx: list[int] = []
    cut_a: list[float] = []
    cut_g: list[np.ndarray] = []
    cut_alphas: list[np.ndarray] = []
    cut_betas: list[np.ndarray] = []

    # 2. Build single-tree GSCIP binary master.
    model = mathopt.Model(name=f"p26_{arm_name}")
    x_vars = [model.add_binary_variable(name=f"x_{i}") for i in range(n)]

    h_vars: list = []
    if separated:
        h_vars = [model.add_variable(lb=0.0, ub=float(ctx.totals_f[s]), name=f"h_{s}") for s in range(S)]
        for s in range(S):
            model.add_linear_constraint(
                mathopt.fast_sum(float(ctx.truncated_f[s, i]) * x_vars[i] for i in range(n)) + h_vars[s]
                >= float(ctx.totals_f[s])
            )

    max_recourse_ub = float(ctx.totals_f.sum()) * ctx.dummy_price
    if cut_mode == "single":
        theta_var = model.add_variable(lb=0.0, ub=max_recourse_ub, name="theta")
        theta_vars = [theta_var]
        a0 = float(seed_ev.a_vec.sum())
        g0 = seed_ev.g_mat.sum(axis=0)
        model.add_linear_constraint(
            theta_var - mathopt.fast_sum(float(g0[i]) * x_vars[i] for i in range(n)) >= a0
        )
        cut_theta_idx.append(0)
        cut_a.append(a0)
        cut_g.append(g0.copy())
        cut_alphas.append(seed_ev.alphas.copy())
        cut_betas.append(seed_ev.betas.copy())
    else:
        theta_vars = [
            model.add_variable(lb=0.0, ub=float(ctx.totals_f[s]) * ctx.dummy_price, name=f"theta_{s}")
            for s in range(S)
        ]
        for s in range(S):
            if use_direct_floor:
                # Direct valid per-scenario floor: theta_s >= (rho-eta)*(D_s - sum min(u_i, D_s) x_i)/div.
                model.add_linear_constraint(
                    theta_vars[s]
                    + mathopt.fast_sum(
                        float(floor_premium_price * ctx.truncated_f[s, i]) * x_vars[i] for i in range(n)
                    )
                    >= float(floor_premium_price * ctx.totals_f[s])
                )
            a_s = float(seed_ev.a_vec[s])
            g_s = seed_ev.g_mat[s]
            model.add_linear_constraint(
                theta_vars[s] - mathopt.fast_sum(float(g_s[i]) * x_vars[i] for i in range(n)) >= a_s
            )
            cut_theta_idx.append(s)
            cut_a.append(a_s)
            cut_g.append(g_s.copy())
            cut_alphas.append(seed_ev.alphas[s].copy())
            cut_betas.append(seed_ev.betas[s].copy())

    obj_expr = mathopt.fast_sum(float(ctx.opening_f[i]) * x_vars[i] for i in range(n)) + mathopt.fast_sum(theta_vars)
    if separated:
        obj_expr = obj_expr + mathopt.fast_sum(ctx.premium_price * h_vars[s] for s in range(S))
    model.minimize(obj_expr)

    # 3. Single-tree MIP_SOLUTION lazy Benders callback (strictly checking projected valid cut violation).
    cb_calls = 0
    cb_calls_no_violated_cut = 0
    cb_cache_hits = 0
    cb_unique_sweeps = 0
    cb_lazy_cuts_added = 0
    cb_subproblem_seconds = 0.0
    cb_deadline_interrupts = 0
    max_integrality_deviation = 0.0
    large_integrality_deviation_calls = 0
    unseparated_material_discrepancy_calls = 0
    max_unseparated_material_discrepancy = 0.0
    max_subproblem_duality_err = float(seed_ev.max_subproblem_duality_err)
    max_pointwise_identity_diff = float(seed_ev.pointwise_identity_diff)
    incumbent_log = [
        {
            "event": "cold_seed",
            "elapsed_seconds": float(seed_elapsed),
            "bits": _bits_key(x_seed),
            "numeric_total_ub": float(seed_ev.total_ub),
        }
    ]

    def lazy_cb(cb_data: mathopt.CallbackData) -> mathopt.CallbackResult:
        nonlocal cb_calls, cb_calls_no_violated_cut, cb_cache_hits, cb_unique_sweeps, cb_lazy_cuts_added
        nonlocal cb_subproblem_seconds, cb_deadline_interrupts
        nonlocal best_x_bin, best_ev, best_found_elapsed
        nonlocal max_integrality_deviation, large_integrality_deviation_calls
        nonlocal unseparated_material_discrepancy_calls, max_unseparated_material_discrepancy
        nonlocal max_subproblem_duality_err, max_pointwise_identity_diff

        cb_calls += 1
        res = mathopt.CallbackResult()
        if perf_counter() >= deadline:
            cb_deadline_interrupts += 1
            res.terminate = True
            return res

        sol = cb_data.solution
        x_raw = np.asarray([float(sol[x_vars[i]]) for i in range(n)], dtype=np.float64)
        # Normalize to binary ONLY to query the linked transportation subproblems.
        x_bin = np.rint(np.clip(x_raw, 0.0, 1.0)).astype(np.int64)
        int_dev = float(np.max(np.abs(x_raw - x_bin)))
        max_integrality_deviation = max(max_integrality_deviation, int_dev)
        if int_dev > 1e-5:
            large_integrality_deviation_calls += 1
        key = _bits_key(x_bin)

        if key in eval_cache:
            cb_cache_hits += 1
            ev = eval_cache[key]
        else:
            ev_new, timed_out = evaluate_candidate(ctx, x_bin.astype(np.float64), deadline)
            if timed_out or ev_new is None:
                cb_deadline_interrupts += 1
                res.terminate = True
                return res
            eval_cache[key] = ev_new
            cb_unique_sweeps += 1
            cb_subproblem_seconds += ev_new.elapsed_seconds
            max_subproblem_duality_err = max(max_subproblem_duality_err, ev_new.max_subproblem_duality_err)
            max_pointwise_identity_diff = max(max_pointwise_identity_diff, ev_new.pointwise_identity_diff)
            ev = ev_new
            if ev.total_ub < best_ev.total_ub - 1e-12:
                best_ev = ev
                best_x_bin = x_bin.copy()
                best_found_elapsed = perf_counter() - t_start
                incumbent_log.append(
                    {
                        "event": "callback_incumbent",
                        "cb_call": cb_calls,
                        "unique_sweep": cb_unique_sweeps,
                        "elapsed_seconds": float(best_found_elapsed),
                        "bits": key,
                        "numeric_total_ub": float(ev.total_ub),
                    }
                )

        added_here = 0
        if cut_mode == "single":
            vt = float(sol[theta_vars[0]])
            a_tot = float(ev.a_vec.sum())
            g_tot = ev.g_mat.sum(axis=0)
            # Test the ACTUAL generated valid cut row at callback values (x_raw, vt).
            projected_rhs_at_cb = a_tot + float(np.dot(g_tot, x_raw))
            if projected_rhs_at_cb - vt > cut_tol:
                res.add_lazy_constraint(
                    theta_vars[0] - mathopt.fast_sum(float(g_tot[i]) * x_vars[i] for i in range(n)) >= a_tot
                )
                added_here += 1
                cb_lazy_cuts_added += 1
                cut_theta_idx.append(0)
                cut_a.append(a_tot)
                cut_g.append(g_tot.copy())
                cut_alphas.append(ev.alphas.copy())
                cut_betas.append(ev.betas.copy())
            else:
                sub_discrepancy = float(ev.sub_total - vt)
                if sub_discrepancy > cut_tol:
                    unseparated_material_discrepancy_calls += 1
                    max_unseparated_material_discrepancy = max(max_unseparated_material_discrepancy, sub_discrepancy)
        else:
            max_unsep_s = 0.0
            for s in range(S):
                vt_s = float(sol[theta_vars[s]])
                a_s = float(ev.a_vec[s])
                g_s = ev.g_mat[s]
                projected_rhs_s = a_s + float(np.dot(g_s, x_raw))
                if projected_rhs_s - vt_s > cut_tol:
                    res.add_lazy_constraint(
                        theta_vars[s] - mathopt.fast_sum(float(g_s[i]) * x_vars[i] for i in range(n)) >= a_s
                    )
                    added_here += 1
                    cb_lazy_cuts_added += 1
                    cut_theta_idx.append(s)
                    cut_a.append(a_s)
                    cut_g.append(g_s.copy())
                    cut_alphas.append(ev.alphas[s].copy())
                    cut_betas.append(ev.betas[s].copy())
                else:
                    max_unsep_s = max(max_unsep_s, float(ev.sub_objs[s]) - vt_s)
            if added_here == 0 and max_unsep_s > cut_tol:
                unseparated_material_discrepancy_calls += 1
                max_unseparated_material_discrepancy = max(max_unseparated_material_discrepancy, max_unsep_s)

        if added_here == 0:
            cb_calls_no_violated_cut += 1

        return res

    cb_reg = mathopt.CallbackRegistration(
        events={mathopt.Event.MIP_SOLUTION},
        mip_solution_filter=mathopt.SparseVectorFilter(),
        add_lazy_constraints=True,
    )

    remaining_for_gscip = max(0.1, deadline - perf_counter())
    params = mathopt.SolveParameters(
        threads=1,
        time_limit=timedelta(seconds=remaining_for_gscip),
        relative_gap_tolerance=rel_gap_tol,
    )

    t_solve = perf_counter()
    result = mathopt.solve(
        model,
        mathopt.SolverType.GSCIP,
        params=params,
        callback_reg=cb_reg,
        cb=lazy_cb,
    )
    solve_wall = perf_counter() - t_solve
    wall_before_certification = perf_counter() - t_start

    term_reason = result.termination.reason.name
    term_limit = result.termination.limit.name if result.termination.limit is not None else None
    term_detail = str(result.termination.detail)
    hit_mathopt_time_limit = bool(term_limit == "TIME" and term_reason in ("FEASIBLE", "NO_SOLUTION_FOUND"))
    hit_own_callback_deadline = bool(cb_deadline_interrupts > 0 or term_limit == "INTERRUPTED")
    hit_any_deadline = bool(hit_mathopt_time_limit or term_limit == "TIME" or hit_own_callback_deadline)

    raw_bb = float(result.best_objective_bound()) + ctx.dummy_opening_f
    numeric_dual_bound = raw_bb if math.isfinite(raw_bb) else None
    solver_primal_obj = (
        float(result.objective_value()) + ctx.dummy_opening_f
        if result.has_primal_feasible_solution()
        else None
    )

    # 4. Worker-side rational grid fallback & cut-LP lower bound (outside single-tree clock).
    t_cert = perf_counter()
    grid_fallback = certify_grid_primal_fallback(data, ctx_orig, best_x_bin)
    cut_lp_cert = certify_arm_cut_lp_lower(
        data,
        ctx,
        cut_mode=cut_mode,
        use_direct_floor=use_direct_floor,
        floor_premium_price=floor_premium_price,
        cut_theta_idx=cut_theta_idx,
        cut_a=cut_a,
        cut_g=cut_g,
        cut_alphas=cut_alphas,
        cut_betas=cut_betas,
        incumbent_x=best_x_bin,
        incumbent_shipping=best_ev.shipping,
    )
    cert_seconds = perf_counter() - t_cert

    u_grid = Fraction(grid_fallback["grid_repaired_original_upper"])
    l_cert_lp = Fraction(cut_lp_cert["exact_certified_cut_lp_lower"])
    numeric_mip_gap = (
        (float(u_grid) - numeric_dual_bound) / float(u_grid)
        if numeric_dual_bound is not None
        else None
    )

    return {
        "arm": arm_name,
        "formulation": ctx.mode,
        "cut_mode": cut_mode,
        "uses_direct_per_scenario_floor": use_direct_floor,
        "uses_hinge_variables": separated,
        "eta_ticks": ctx.eta_ticks,
        "rho_ticks": ctx.rho_ticks,
        "solve_calls": 1,
        "worker_saw_reference_files": False,
        "termination": {
            "reason": term_reason,
            "limit": term_limit,
            "detail": term_detail,
            "reached_numeric_optimal": bool(term_reason == "OPTIMAL"),
            "hit_mathopt_time_limit": hit_mathopt_time_limit,
            "hit_own_callback_deadline": hit_own_callback_deadline,
            "hit_time_or_deadline": hit_any_deadline,
        },
        "gscip_stats": {
            "node_count": int(result.solve_stats.node_count),
            "simplex_iterations": int(result.solve_stats.simplex_iterations),
            "gscip_solve_time_seconds": float(result.solve_stats.solve_time.total_seconds()),
            "solver_primal_objective_numeric": solver_primal_obj,
            "numeric_mip_dual_bound_diagnostic_not_exact_proof": numeric_dual_bound,
            "numeric_mip_gap_diagnostic_against_grid_upper": numeric_mip_gap,
        },
        "callback_stats": {
            "total_callback_calls": cb_calls,
            "callback_calls_no_violated_cut": cb_calls_no_violated_cut,
            "cache_hits": cb_cache_hits,
            "unique_binary_sweeps_in_tree": cb_unique_sweeps,
            "total_unique_binary_layouts_evaluated_including_seed": len(eval_cache),
            "initial_seed_cuts": 1 if cut_mode == "single" else S,
            "lazy_cuts_added_in_tree": cb_lazy_cuts_added,
            "total_cuts_in_pool": len(cut_a),
            "deadline_interrupts": cb_deadline_interrupts,
            "max_integrality_deviation": max_integrality_deviation,
            "large_integrality_deviation_calls": large_integrality_deviation_calls,
            "unseparated_material_discrepancy_calls": unseparated_material_discrepancy_calls,
            "max_unseparated_material_discrepancy": max_unseparated_material_discrepancy,
            "max_subproblem_duality_err": max_subproblem_duality_err,
            "max_pointwise_identity_diff": max_pointwise_identity_diff,
        },
        "timing_seconds": {
            "cold_seed_eval": float(seed_elapsed),
            "gscip_wall": float(solve_wall),
            "callback_subproblem_total": float(cb_subproblem_seconds),
            "best_incumbent_found_at": float(best_found_elapsed),
            "before_certification": float(wall_before_certification),
            "worker_grid_and_cutlp_certification": float(cert_seconds),
        },
        "final_binary_layout": {
            "open_real_sites": grid_fallback["open_real_sites"],
            "open_count": grid_fallback["open_count"],
            "bits": grid_fallback["bits"],
            "is_binary_opening": grid_fallback["is_binary_opening"],
        },
        "grid_primal_fallback": grid_fallback,
        "exact_cut_lp_lower": {
            "numeric_cut_pool_lp_objective": cut_lp_cert["numeric_cut_pool_lp_objective"],
            "exact_certified_cut_lp_lower": cut_lp_cert["exact_certified_cut_lp_lower"],
            "exact_certified_cut_lp_lower_float": cut_lp_cert["exact_certified_cut_lp_lower_float"],
            "grid_root_to_incumbent_gap": str((u_grid - l_cert_lp) / u_grid),
            "grid_root_to_incumbent_gap_float": float((u_grid - l_cert_lp) / u_grid),
        },
        "incumbent_history": incumbent_log,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--time-limit", type=float, default=60.0, help="Per-arm wall-clock cap in seconds.")
    parser.add_argument("--cut-tol", type=float, default=1e-6)
    parser.add_argument("--rel-gap-tol", type=float, default=1e-6)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    t_global = perf_counter()
    data, profile = load_case("p26")
    x_seed = build_input_only_cold_seed(data)

    ctx_orig = build_arm_context(data, "linked")
    ctx_sep = build_arm_context(data, "linked_separated")
    floor_premium_price = ctx_sep.premium_price  # exact (rho - eta) / divisor

    arm_records: dict[str, dict] = {}
    for arm_name, form_mode, cut_mode, use_direct_floor in ARM_SPECS:
        ctx = ctx_orig if form_mode == "linked" else ctx_sep
        rec = run_single_tree_arm(
            data,
            ctx,
            ctx_orig,
            arm_name=arm_name,
            cut_mode=cut_mode,
            use_direct_floor=use_direct_floor,
            floor_premium_price=floor_premium_price,
            x_seed=x_seed,
            time_limit=args.time_limit,
            cut_tol=args.cut_tol,
            rel_gap_tol=args.rel_gap_tol,
        )
        arm_records[arm_name] = rec
        term = rec["termination"]
        print(
            f"[p26 worker | {arm_name}] reason={term['reason']} limit={term['limit']} "
            f"sweeps={rec['callback_stats']['total_unique_binary_layouts_evaluated_including_seed']} "
            f"cb={rec['callback_stats']['total_callback_calls']} "
            f"lazy={rec['callback_stats']['lazy_cuts_added_in_tree']} "
            f"nodes={rec['gscip_stats']['node_count']} "
            f"U_grid={rec['grid_primal_fallback']['grid_repaired_original_upper_float']:.6f} "
            f"L_cert_LP={rec['exact_cut_lp_lower']['exact_certified_cut_lp_lower_float']:.6f} "
            f"L_num_SCIP={rec['gscip_stats']['numeric_mip_dual_bound_diagnostic_not_exact_proof']} "
            f"t={rec['timing_seconds']['before_certification']:.3f}s"
        )

    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    payload = {
        "study": "single_tree_lazy_integer_linked_benders_p26_worker_raw",
        "case": "p26",
        "worker_saw_reference_files": False,
        "backend": "ortools.math_opt.SolverType.GSCIP + scipy.optimize.linprog(highs-ds)",
        "dual_bound_disclaimer": (
            "GSCIP best_objective_bound is a numeric floating-point solver diagnostic and is NEVER "
            "a new exact rational optimality proof. Exact 200-scenario original-price incumbent repricing "
            "and independent reference-gap scoring are executed strictly post-run by evaluate_p26_integer_run.py."
        ),
        "input_profile": profile,
        "shared_cold_seed": {
            "policy": "deterministic_greedy_unit_capacity_opening_cost_until_peak_demand",
            "uses_only_model_inputs": True,
            "bits": _bits_key(x_seed),
            "open_real_sites": [int(i) for i, v in enumerate(x_seed) if int(v) == 1],
            "open_count": int(x_seed.sum()),
        },
        "config": {
            "time_limit_seconds_per_arm": args.time_limit,
            "cut_tol": args.cut_tol,
            "rel_gap_tol": args.rel_gap_tol,
            "threads": 1,
            "arms": [spec[0] for spec in ARM_SPECS],
            "a2_direct_floor_premium_ticks": int(ctx_orig.rho_ticks - ctx_sep.eta_ticks),
        },
        "runtime": {
            "python": sys.version,
            "executable": sys.executable,
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "ortools": version("ortools"),
            "cpu_affinity": affinity,
            "worker_sha256": _file_sha256(Path(__file__).resolve()),
            "reused_pilot_module_sha256": _file_sha256(PILOT_ARCHIVE_DIR / "linked_benders_pilot.py"),
        },
        "arms": arm_records,
        "total_wall_seconds": float(perf_counter() - t_global),
    }

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2, allow_nan=False)
        fh.write("\n")
    print(f"Wrote cold worker raw JSON: {args.out}")


if __name__ == "__main__":
    main()
