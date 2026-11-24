"""Paired iterative linked Benders root pilot on Diaz p01.

Compares original-price linked Benders (`linked`) against shortage-separated
linked Benders (`linked_separated`) on the exact same proportional-arc linked
polytope (`y_{sij} <= x_i d_{sj}`), starting strictly cold with identical
candidate budgets, wall-clock caps, and single-threaded HiGHS solves.

All interim and final bounds are certified on the continuous fractional root
relaxation (`x in [0, 1]^n`) via the frozen `experiments/linked_root/certify.py`
rational projection and cross-checked against the independent sealed `p01`
deterministic-equivalent reference interval in `experiments/linked_root/runs_45s/`.
"""

from __future__ import annotations

import os

for _env_var in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_env_var, "1")

import argparse
from dataclasses import dataclass
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import sys
from time import perf_counter
import warnings

import numpy as np
from scipy.optimize import OptimizeWarning, linprog
from scipy.sparse import coo_array

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
LINKED_ROOT_DIR = REPO_ROOT / "experiments" / "linked_root"
if str(LINKED_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(LINKED_ROOT_DIR))

from certify import OPEN_GRID, certify
from run_root import load_case

ARMS = ("linked", "linked_separated")
CUT_MODES = ("multi", "single")


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _x_digest(x: np.ndarray) -> str:
    rounded = [round(float(v), 8) for v in x]
    return sha256(json.dumps(rounded).encode("utf-8")).hexdigest()[:16]


def _solve_lp(c, *, A_ub=None, b_ub=None, A_eq=None, b_eq=None, bounds=None, time_limit=30.0):
    """Single-threaded HiGHS dual-simplex solve with automatic default-HiGHS fallback."""
    t_cap = float(max(0.05, time_limit))
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=OptimizeWarning, message=r"Unrecognized options.*")
        res = linprog(
            c,
            A_ub=A_ub,
            b_ub=b_ub,
            A_eq=A_eq,
            b_eq=b_eq,
            bounds=bounds,
            method="highs-ds",
            options={"threads": 1, "time_limit": t_cap},
        )
        if res.status != 0 and res.status != 1:
            res = linprog(
                c,
                A_ub=A_ub,
                b_ub=b_ub,
                A_eq=A_eq,
                b_eq=b_eq,
                bounds=bounds,
                method="highs",
                options={"threads": 1, "time_limit": t_cap},
            )
    return res


def tightest_capacity_dual(diff_row: np.ndarray, demand_row: np.ndarray, cap: float) -> float:
    """Exact 1D waterfilling maximizer beta* <= 0 of cap*beta + sum_j d_j * min(0, diff_j - beta).

    For any dual-feasible demand prices alpha_s, this preserves dual feasibility
    (beta* <= 0, gamma_ij = min(0, diff_ij - beta*)) and exact tightness at x_k
    while eliminating arbitrary degenerate capacity duals when x_i = 0.
    """
    neg_mask = (diff_row < 0.0) & (demand_row > 0.0)
    if not np.any(neg_mask):
        return 0.0
    diffs = diff_row[neg_mask]
    dems = demand_row[neg_mask]
    order = np.argsort(diffs)
    cum = 0.0
    for idx in order:
        cum += float(dems[idx])
        if cum > cap:
            return float(diffs[idx])
    return 0.0


@dataclass(frozen=True)
class ArmContext:
    mode: str
    n: int
    m: int
    scenarios: int
    divisor: int
    rho_ticks: int
    eta_ticks: int | None
    dummy_price: float
    orig_dummy_price: float
    premium_price: float
    opening_f: np.ndarray
    dummy_opening_f: float
    caps_f: np.ndarray
    demands_f: np.ndarray
    totals_f: np.ndarray
    truncated_f: np.ndarray
    c_real: np.ndarray
    c_vec: np.ndarray
    orig_prices: np.ndarray
    A_eq: object
    A_ub: object


def build_arm_context(data, mode: str) -> ArmContext:
    if mode not in ARMS:
        raise ValueError(f"Unknown arm mode: {mode}")
    demands_i = np.asarray(data.demands, dtype=np.int64)
    scenarios, m = demands_i.shape
    n = len(data.capacities) - 1
    caps_i = np.asarray(data.capacities[:n], dtype=np.int64)
    costs_obj = np.asarray(data.cost, dtype=object)
    totals_i = demands_i.sum(axis=1)
    rho_ticks = int(costs_obj[-1, 0])
    if (
        not np.all(costs_obj[-1] == rho_ticks)
        or min(data.capacities) < 0
        or data.capacities[-1] < int(totals_i.max())
    ):
        raise ValueError("Expected complete split transport and a sufficiently large uniform dummy")

    divisor = int(data.divisor)
    eta_ticks: int | None = None
    if mode == "linked_separated":
        eta_ticks = int(costs_obj[:n].max()) * 2
        if rho_ticks < eta_ticks:
            raise ValueError("Original shortage price is below the sharp uniform linked threshold")

    c_real = np.asarray(
        [[int(costs_obj[i, j]) / divisor for j in range(m)] for i in range(n)],
        dtype=np.float64,
    )
    orig_dummy_price = rho_ticks / divisor
    dummy_price = (eta_ticks / divisor) if eta_ticks is not None else orig_dummy_price
    premium_price = ((rho_ticks - eta_ticks) / divisor) if eta_ticks is not None else 0.0

    c_mat = np.empty((n + 1, m), dtype=np.float64)
    c_mat[:n] = c_real
    c_mat[n] = dummy_price

    orig_prices = np.empty((n + 1, m), dtype=np.float64)
    orig_prices[:n] = c_real
    orig_prices[n] = orig_dummy_price

    opening_f = np.asarray([float(f) for f in data.opening[:n]], dtype=np.float64)
    dummy_opening_f = float(data.opening[-1])
    caps_f = caps_i.astype(np.float64)
    demands_f = demands_i.astype(np.float64)
    totals_f = totals_i.astype(np.float64)
    truncated_f = np.minimum(totals_i[:, None], caps_i[None, :]).astype(np.float64)

    n_vars = (n + 1) * m
    eq_rows = np.tile(np.arange(m, dtype=np.int64), n + 1)
    eq_cols = np.arange(n_vars, dtype=np.int64)
    A_eq = coo_array((np.ones(n_vars, dtype=np.float64), (eq_rows, eq_cols)), shape=(m, n_vars)).tocsc()

    ub_rows = np.repeat(np.arange(n, dtype=np.int64), m)
    ub_cols = np.arange(n * m, dtype=np.int64)
    A_ub = coo_array((np.ones(n * m, dtype=np.float64), (ub_rows, ub_cols)), shape=(n, n_vars)).tocsc()

    return ArmContext(
        mode=mode,
        n=n,
        m=m,
        scenarios=scenarios,
        divisor=divisor,
        rho_ticks=rho_ticks,
        eta_ticks=eta_ticks,
        dummy_price=dummy_price,
        orig_dummy_price=orig_dummy_price,
        premium_price=premium_price,
        opening_f=opening_f,
        dummy_opening_f=dummy_opening_f,
        caps_f=caps_f,
        demands_f=demands_f,
        totals_f=totals_f,
        truncated_f=truncated_f,
        c_real=c_real,
        c_vec=c_mat.ravel(),
        orig_prices=orig_prices,
        A_eq=A_eq,
        A_ub=A_ub,
    )


@dataclass
class CandidateEval:
    x: np.ndarray
    shipping: np.ndarray
    sub_objs: np.ndarray
    alphas: np.ndarray
    betas: np.ndarray
    a_vec: np.ndarray
    g_mat: np.ndarray
    opening_cost: float
    sub_total: float
    hinge_cost: float
    total_ub: float
    orig_same_primal: float
    pointwise_identity_diff: float
    max_subproblem_duality_err: float
    elapsed_seconds: float


def evaluate_candidate(ctx: ArmContext, x: np.ndarray, deadline: float) -> tuple[CandidateEval | None, bool]:
    """Solve all S linked transportation scenario subproblems at fractional x."""
    t_eval = perf_counter()
    x_clean = np.clip(np.asarray(x, dtype=np.float64), 0.0, 1.0)
    n, m, S = ctx.n, ctx.m, ctx.scenarios
    n_vars = (n + 1) * m

    shipping = np.empty((S, n + 1, m), dtype=np.float64)
    sub_objs = np.empty(S, dtype=np.float64)
    alphas = np.empty((S, m), dtype=np.float64)
    betas = np.empty((S, n), dtype=np.float64)
    a_vec = np.empty(S, dtype=np.float64)
    g_mat = np.empty((S, n), dtype=np.float64)

    bounds = np.empty((n_vars, 2), dtype=np.float64)
    bounds[:, 0] = 0.0
    bounds[n * m :, 1] = np.inf
    b_ub = ctx.caps_f * x_clean
    max_duality_err = 0.0

    for s in range(S):
        remaining = deadline - perf_counter()
        if remaining <= 0.0:
            return None, True
        bounds[: n * m, 1] = (x_clean[:, None] * ctx.demands_f[s][None, :]).ravel()
        res = _solve_lp(
            ctx.c_vec,
            A_ub=ctx.A_ub,
            b_ub=b_ub,
            A_eq=ctx.A_eq,
            b_eq=ctx.demands_f[s],
            bounds=bounds,
            time_limit=remaining,
        )
        if res.status != 0:
            if res.status == 1 or perf_counter() >= deadline:
                return None, True
            raise RuntimeError(
                f"Subproblem failed (mode={ctx.mode}, scenario={s}, status={res.status}, msg={res.message})"
            )

        flow_s = res.x.reshape(n + 1, m)
        shipping[s] = flow_s
        sub_obj = float(res.fun)
        sub_objs[s] = sub_obj

        alpha_s = np.clip(np.asarray(res.eqlin.marginals, dtype=np.float64), 0.0, ctx.dummy_price)
        diff = ctx.c_real - alpha_s[None, :]
        beta_s = np.empty(n, dtype=np.float64)
        for i in range(n):
            beta_s[i] = tightest_capacity_dual(diff[i], ctx.demands_f[s], float(ctx.caps_f[i]))
        gamma_s = np.minimum(0.0, diff - beta_s[:, None])

        a_s = float(np.dot(alpha_s, ctx.demands_f[s]))
        g_s = ctx.caps_f * beta_s + gamma_s @ ctx.demands_f[s]
        cut_val = a_s + float(np.dot(g_s, x_clean))
        max_duality_err = max(max_duality_err, abs(cut_val - sub_obj))

        alphas[s] = alpha_s
        betas[s] = beta_s
        a_vec[s] = a_s
        g_mat[s] = g_s

    opening_cost = ctx.dummy_opening_f + float(np.dot(ctx.opening_f, x_clean))
    sub_total = float(sub_objs.sum())
    if ctx.eta_ticks is not None:
        hinge_vals = np.maximum(0.0, ctx.totals_f - ctx.truncated_f @ x_clean)
        hinge_cost = float(hinge_vals.sum()) * ctx.premium_price
    else:
        hinge_cost = 0.0

    total_ub = opening_cost + sub_total + hinge_cost
    orig_same_primal = opening_cost + float(np.sum(shipping * ctx.orig_prices[None, :, :]))
    pointwise_diff = abs(orig_same_primal - total_ub)

    return (
        CandidateEval(
            x=x_clean,
            shipping=shipping,
            sub_objs=sub_objs,
            alphas=alphas,
            betas=betas,
            a_vec=a_vec,
            g_mat=g_mat,
            opening_cost=opening_cost,
            sub_total=sub_total,
            hinge_cost=hinge_cost,
            total_ub=total_ub,
            orig_same_primal=orig_same_primal,
            pointwise_identity_diff=pointwise_diff,
            max_subproblem_duality_err=max_duality_err,
            elapsed_seconds=perf_counter() - t_eval,
        ),
        False,
    )


def load_reference_interval(case: str, expected_input_sha: str) -> dict:
    """Read independent sealed deterministic-equivalent p01 reference interval."""
    runs_dir = LINKED_ROOT_DIR / "runs_45s"
    p_linked = runs_dir / f"{case}_linked.json"
    p_sep = runs_dir / f"{case}_linked_separated.json"
    rec_linked = json.loads(p_linked.read_text(encoding="utf-8"))
    rec_sep = json.loads(p_sep.read_text(encoding="utf-8"))
    for label, rec in (("linked", rec_linked), ("linked_separated", rec_sep)):
        if rec["input_sha256"] != expected_input_sha:
            raise ValueError(f"Sealed reference {label} input_sha256 mismatch")
        if rec["certificate"] is None:
            raise ValueError(f"Sealed reference {label} has no certificate")

    l_linked = Fraction(rec_linked["certificate"]["lower"])
    u_linked = Fraction(rec_linked["certificate"]["upper"])
    l_sep = Fraction(rec_sep["certificate"]["lower"])
    u_sep = Fraction(rec_sep["certificate"]["upper"])
    l_ref = max(l_linked, l_sep)
    u_ref = min(u_linked, u_sep)
    if l_ref > u_ref:
        raise ArithmeticError("Sealed reference intervals do not overlap")

    return {
        "source_files": {
            "linked": str(p_linked),
            "linked_sha256": _file_sha256(p_linked),
            "linked_separated": str(p_sep),
            "linked_separated_sha256": _file_sha256(p_sep),
        },
        "intersection_lower": str(l_ref),
        "intersection_upper": str(u_ref),
        "intersection_lower_float": float(l_ref),
        "intersection_upper_float": float(u_ref),
        "intersection_width_float": float(u_ref - l_ref),
        "de_wall_seconds": {
            "linked": float(rec_linked["elapsed_seconds"]),
            "linked_separated": float(rec_sep["elapsed_seconds"]),
        },
    }


def run_benders_arm(
    data,
    ctx: ArmContext,
    cut_mode: str,
    *,
    max_iters: int,
    time_limit: float,
    rel_tol: float,
    cut_tol: float,
    ref_lower: Fraction,
    ref_upper: Fraction,
) -> tuple[dict, list[np.ndarray]]:
    """Run one strictly cold iterative linked Benders arm and certify its bounds."""
    if cut_mode not in CUT_MODES:
        raise ValueError(f"Unknown cut mode: {cut_mode}")

    t_start = perf_counter()
    deadline = t_start + time_limit
    n, m, S = ctx.n, ctx.m, ctx.scenarios
    separated = ctx.eta_ticks is not None
    n_theta = 1 if cut_mode == "single" else S
    n_hinge = S if separated else 0
    n_vars = n + n_theta + n_hinge

    c_master = np.empty(n_vars, dtype=np.float64)
    c_master[:n] = ctx.opening_f
    c_master[n : n + n_theta] = 1.0
    if separated:
        c_master[n + n_theta :] = ctx.premium_price

    bounds_master = np.empty((n_vars, 2), dtype=np.float64)
    bounds_master[:, 0] = 0.0
    bounds_master[:, 1] = np.inf
    bounds_master[:n, 1] = 1.0

    # Constant scalar shortage hinge rows for separated arm (0 rows for original arm).
    if separated:
        hinge_row_ids = np.arange(S, dtype=np.int64)
        hinge_rows = np.concatenate([np.repeat(hinge_row_ids, n), hinge_row_ids])
        hinge_cols = np.concatenate([np.tile(np.arange(n, dtype=np.int64), S), n + n_theta + hinge_row_ids])
        hinge_vals = np.concatenate([-ctx.truncated_f.ravel(), np.full(S, -1.0, dtype=np.float64)])
        hinge_rhs = -ctx.totals_f.copy()
    else:
        hinge_rows = np.zeros(0, dtype=np.int64)
        hinge_cols = np.zeros(0, dtype=np.int64)
        hinge_vals = np.zeros(0, dtype=np.float64)
        hinge_rhs = np.zeros(0, dtype=np.float64)

    cut_theta_idx: list[int] = []
    cut_a: list[float] = []
    cut_g: list[np.ndarray] = []
    cut_alphas: list[np.ndarray] = []
    cut_betas: list[np.ndarray] = []

    def solve_current_master() -> tuple[object | None, int, float]:
        t_m = perf_counter()
        remaining = deadline - t_m
        if remaining <= 0.0:
            return None, len(cut_a), 0.0
        n_cuts = len(cut_a)
        n_rows = n_hinge + n_cuts
        if n_rows == 0:
            A_ub_m, b_ub_m = None, None
        else:
            row_parts = []
            col_parts = []
            val_parts = []
            rhs_parts = []
            if n_hinge > 0:
                row_parts.append(hinge_rows)
                col_parts.append(hinge_cols)
                val_parts.append(hinge_vals)
                rhs_parts.append(hinge_rhs)
            if n_cuts > 0:
                cut_row_ids = np.arange(n_hinge, n_hinge + n_cuts, dtype=np.int64)
                row_parts.extend([np.repeat(cut_row_ids, n), cut_row_ids])
                col_parts.extend(
                    [np.tile(np.arange(n, dtype=np.int64), n_cuts), n + np.asarray(cut_theta_idx, dtype=np.int64)]
                )
                val_parts.extend([np.asarray(cut_g, dtype=np.float64).ravel(), np.full(n_cuts, -1.0, dtype=np.float64)])
                rhs_parts.append(-np.asarray(cut_a, dtype=np.float64))
            A_ub_m = coo_array(
                (np.concatenate(val_parts), (np.concatenate(row_parts), np.concatenate(col_parts))),
                shape=(n_rows, n_vars),
            ).tocsc()
            b_ub_m = np.concatenate(rhs_parts)
        res = _solve_lp(c_master, A_ub=A_ub_m, b_ub=b_ub_m, bounds=bounds_master, time_limit=remaining)
        return res, n_cuts, perf_counter() - t_m

    history: list[dict] = []
    visited_x: list[np.ndarray] = []
    best_eval: CandidateEval | None = None
    best_iter: int | None = None
    last_valid_master: tuple[object, int] | None = None
    master_lb = -np.inf
    total_master_time = 0.0
    total_sub_time = 0.0
    master_solves = 0
    candidate_evals = 0
    max_duality_err_all = 0.0
    max_pointwise_diff_all = 0.0
    stop_reason = "max_iters"
    cuts_added_since_master = False

    for k in range(max_iters):
        if perf_counter() >= deadline:
            stop_reason = "time_limit"
            break

        master_res, n_cuts_at_solve, dt_m = solve_current_master()
        total_master_time += dt_m
        if master_res is None or master_res.status != 0:
            stop_reason = "master_time_limit" if (master_res is None or master_res.status == 1) else f"master_status_{master_res.status}"
            break
        master_solves += 1
        last_valid_master = (master_res, n_cuts_at_solve)
        cuts_added_since_master = False

        x_k = np.clip(np.asarray(master_res.x[:n], dtype=np.float64), 0.0, 1.0)
        master_lb = float(master_res.fun) + ctx.dummy_opening_f

        ev, timed_out = evaluate_candidate(ctx, x_k, deadline)
        if timed_out or ev is None:
            stop_reason = "subproblem_time_limit"
            break
        total_sub_time += ev.elapsed_seconds
        candidate_evals += 1
        visited_x.append(ev.x.copy())
        max_duality_err_all = max(max_duality_err_all, ev.max_subproblem_duality_err)
        max_pointwise_diff_all = max(max_pointwise_diff_all, ev.pointwise_identity_diff)

        if best_eval is None or ev.total_ub < best_eval.total_ub:
            best_eval = ev
            best_iter = k

        # Add violated Benders cuts.
        cuts_this_iter = 0
        if cut_mode == "single":
            theta_val = float(master_res.x[n])
            if k == 0 or ev.sub_total > theta_val + cut_tol:
                cut_theta_idx.append(0)
                cut_a.append(float(ev.a_vec.sum()))
                cut_g.append(ev.g_mat.sum(axis=0))
                cut_alphas.append(ev.alphas.copy())
                cut_betas.append(ev.betas.copy())
                cuts_this_iter = 1
        else:
            theta_vals = np.asarray(master_res.x[n : n + S], dtype=np.float64)
            for s in range(S):
                if k == 0 or float(ev.sub_objs[s]) > float(theta_vals[s]) + cut_tol:
                    cut_theta_idx.append(s)
                    cut_a.append(float(ev.a_vec[s]))
                    cut_g.append(ev.g_mat[s].copy())
                    cut_alphas.append(ev.alphas[s].copy())
                    cut_betas.append(ev.betas[s].copy())
                    cuts_this_iter += 1

        if cuts_this_iter > 0:
            cuts_added_since_master = True

        rel_gap = (best_eval.total_ub - master_lb) / max(1.0, abs(best_eval.total_ub))
        frac_entries = int(np.sum((ev.x > 1e-6) & (ev.x < 1.0 - 1e-6)))
        history.append(
            {
                "iter": k,
                "elapsed_seconds": perf_counter() - t_start,
                "master_lb_fractional": master_lb,
                "candidate_ub_fractional": ev.total_ub,
                "best_ub_fractional": best_eval.total_ub,
                "numeric_rel_gap_fractional": rel_gap,
                "cuts_added": cuts_this_iter,
                "total_cuts_after_iter": len(cut_a),
                "x_l1_sum": float(ev.x.sum()),
                "x_fractional_entries": frac_entries,
                "x_hash": _x_digest(ev.x),
                "master_seconds": dt_m,
                "subproblem_seconds": ev.elapsed_seconds,
            }
        )

        if rel_gap <= rel_tol:
            stop_reason = "converged_rel_tol"
            break
        if cuts_this_iter == 0:
            stop_reason = "no_violated_cuts"
            break

    # One final master LP solve (no extra subproblem sweeps) to incorporate the last batch of cuts into L_cert.
    if cuts_added_since_master and perf_counter() < deadline:
        post_res, post_n_cuts, dt_post = solve_current_master()
        total_master_time += dt_post
        if post_res is not None and post_res.status == 0:
            master_solves += 1
            last_valid_master = (post_res, post_n_cuts)
            master_lb = float(post_res.fun) + ctx.dummy_opening_f

    seconds_before_certificate = perf_counter() - t_start

    # Exact rational certification via frozen certify.py (outside numerical loop, charged to total arm elapsed).
    certificate = None
    verification = None
    if best_eval is not None and last_valid_master is not None:
        final_master, n_cuts_used = last_valid_master
        n_ub = n_hinge + n_cuts_used
        if n_ub > 0 and final_master.ineqlin is not None and final_master.ineqlin.marginals is not None:
            ineq_m = np.asarray(final_master.ineqlin.marginals, dtype=np.float64)
        else:
            ineq_m = np.zeros(0, dtype=np.float64)

        shortage_m = ineq_m[:S].copy() if separated else None
        cut_m = ineq_m[n_hinge : n_hinge + n_cuts_used]
        weights = np.maximum(0.0, -cut_m)

        bar_alpha = np.zeros((S, m), dtype=np.float64)
        bar_beta = np.zeros((S, n), dtype=np.float64)
        if n_cuts_used > 0:
            if cut_mode == "single":
                w_sum = float(weights.sum())
                if w_sum > 1.0:
                    weights = weights / w_sum
                for r in range(n_cuts_used):
                    wr = float(weights[r])
                    if wr > 0.0:
                        bar_alpha += wr * cut_alphas[r]
                        bar_beta += wr * cut_betas[r]
            else:
                by_scen: list[list[int]] = [[] for _ in range(S)]
                for r in range(n_cuts_used):
                    by_scen[cut_theta_idx[r]].append(r)
                for s in range(S):
                    idxs = by_scen[s]
                    if not idxs:
                        continue
                    w_s = weights[idxs]
                    w_sum = float(w_s.sum())
                    if w_sum > 1.0:
                        w_s = w_s / w_sum
                    for r, wr in zip(idxs, w_s, strict=True):
                        wr_f = float(wr)
                        if wr_f > 0.0:
                            bar_alpha[s] += wr_f * cut_alphas[r]
                            bar_beta[s] += wr_f * cut_betas[r]

        certificate = certify(
            data,
            best_eval.x,
            best_eval.shipping,
            bar_alpha,
            bar_beta,
            linked=True,
            shortage_marginals=shortage_m,
            eta=ctx.eta_ticks,
        )
        l_cert = Fraction(certificate["lower"])
        u_cert = Fraction(certificate["upper"])
        u_orig = Fraction(certificate["original_same_primal"])
        is_binary = all(v in (0, OPEN_GRID) for v in certificate["rounded_opening"])
        frac_count = sum(1 for v in certificate["rounded_opening"] if 0 < v < OPEN_GRID)
        overlaps_ref = (l_cert <= ref_upper) and (u_cert >= ref_lower)
        verification = {
            "certified_lower_float": float(l_cert),
            "certified_upper_float": float(u_cert),
            "certified_original_same_primal_float": float(u_orig),
            "certified_interval_width_float": float(u_cert - l_cert),
            "certified_relative_gap_float": float((u_cert - l_cert) / u_cert) if u_cert else 0.0,
            "sound_lower_le_upper": bool(l_cert <= u_cert),
            "overlaps_sealed_reference": bool(overlaps_ref),
            "certified_lower_le_ref_upper": bool(l_cert <= ref_upper),
            "certified_upper_ge_ref_lower": bool(u_cert >= ref_lower),
            "lower_shortfall_below_ref_lower_float": float(ref_lower - l_cert),
            "upper_excess_above_ref_upper_float": float(u_cert - ref_upper),
            "bound_classification": {
                "domain": "continuous_fractional_root_relaxation",
                "lower_bound_valid_for": ["continuous_fractional_lp_relaxation", "binary_integer_mip"],
                "upper_bound_valid_for": (
                    ["continuous_fractional_lp_relaxation", "binary_integer_mip"]
                    if is_binary
                    else ["continuous_fractional_lp_relaxation_only_NOT_integer_feasible"]
                ),
                "is_binary_opening": is_binary,
                "fractional_facility_count": frac_count,
                "integer_incumbent_searched": False,
            },
        }

    total_elapsed = perf_counter() - t_start
    record = {
        "arm": ctx.mode,
        "cut_mode": cut_mode,
        "eta_ticks": ctx.eta_ticks,
        "rho_ticks": ctx.rho_ticks,
        "stop_reason": stop_reason,
        "candidate_evaluations": candidate_evals,
        "master_solves": master_solves,
        "total_cuts_generated": len(cut_a),
        "best_candidate_iter": best_iter,
        "numeric_final": {
            "master_lb_fractional": float(master_lb) if np.isfinite(master_lb) else None,
            "best_ub_fractional": float(best_eval.total_ub) if best_eval is not None else None,
            "best_orig_same_primal": float(best_eval.orig_same_primal) if best_eval is not None else None,
            "rel_gap_fractional": (
                float((best_eval.total_ub - master_lb) / max(1.0, abs(best_eval.total_ub)))
                if (best_eval is not None and np.isfinite(master_lb))
                else None
            ),
            "max_subproblem_duality_err": float(max_duality_err_all),
            "max_pointwise_identity_diff": float(max_pointwise_diff_all),
        },
        "timing_seconds": {
            "master_total": float(total_master_time),
            "subproblem_total": float(total_sub_time),
            "before_certificate": float(seconds_before_certificate),
            "total_including_certificate": float(total_elapsed),
            "within_time_limit_before_certificate": bool(seconds_before_certificate <= time_limit + 1e-6),
        },
        "certificate": certificate,
        "verification": verification,
        "iteration_trace": history,
    }
    return record, visited_x


def compare_paths(visited_orig: list[np.ndarray], visited_sep: list[np.ndarray]) -> dict:
    """Summarize whether the two arms traversed genuinely separate candidate paths."""
    common = min(len(visited_orig), len(visited_sep))
    first_diff_iter = None
    max_l1 = 0.0
    max_linf = 0.0
    for k in range(common):
        diff = np.abs(visited_orig[k] - visited_sep[k])
        l1 = float(diff.sum())
        linf = float(diff.max())
        max_l1 = max(max_l1, l1)
        max_linf = max(max_linf, linf)
        if first_diff_iter is None and linf > 1e-6:
            first_diff_iter = k
    return {
        "orig_candidates": len(visited_orig),
        "sep_candidates": len(visited_sep),
        "common_prefix_checked": common,
        "first_differing_iter": first_diff_iter,
        "paths_distinct": bool(first_diff_iter is not None or len(visited_orig) != len(visited_sep)),
        "max_pointwise_l1_diff": max_l1,
        "max_pointwise_linf_diff": max_linf,
    }


def run_fixed_history_diagnostic(
    ctx_orig: ArmContext,
    ctx_sep: ArmContext,
    visited_orig: list[np.ndarray],
    visited_sep: list[np.ndarray],
    *,
    max_points: int = 6,
    time_limit: float = 15.0,
) -> dict:
    """Secondary diagnostic (outside primary arm clocks): verify pointwise identity on shared visited iterates."""
    t0 = perf_counter()
    deadline = t0 + time_limit
    unique_pts: list[tuple[str, np.ndarray]] = []
    seen: set[str] = set()
    for tag, seq in (("linked", visited_orig), ("linked_separated", visited_sep)):
        for x in seq:
            h = _x_digest(x)
            if h not in seen:
                seen.add(h)
                unique_pts.append((tag, x))
            if len(unique_pts) >= max_points:
                break
        if len(unique_pts) >= max_points:
            break

    rows = []
    max_abs_diff = 0.0
    for source_arm, x in unique_pts:
        ev_o, to_o = evaluate_candidate(ctx_orig, x, deadline)
        ev_s, to_s = evaluate_candidate(ctx_sep, x, deadline)
        if to_o or to_s or ev_o is None or ev_s is None:
            break
        diff = abs(ev_o.total_ub - ev_s.total_ub)
        max_abs_diff = max(max_abs_diff, diff)
        rows.append(
            {
                "source_arm": source_arm,
                "x_hash": _x_digest(x),
                "orig_total_ub_fractional": float(ev_o.total_ub),
                "sep_total_ub_fractional": float(ev_s.total_ub),
                "sep_hinge_cost": float(ev_s.hinge_cost),
                "abs_pointwise_diff": float(diff),
            }
        )
    return {
        "note": "Secondary diagnostic outside primary arm budgets; evaluates exact pointwise identity on visited fractional iterates.",
        "points_evaluated": len(rows),
        "max_abs_pointwise_diff": float(max_abs_diff),
        "elapsed_seconds": float(perf_counter() - t0),
        "points": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("smoke", "full"), default="smoke")
    parser.add_argument("--cut-mode", choices=("multi", "single", "both"), default=None)
    parser.add_argument("--max-iters", type=int, default=None)
    parser.add_argument("--time-limit", type=float, default=None, help="Per-arm wall-clock cap in seconds.")
    parser.add_argument("--rel-tol", type=float, default=1e-6)
    parser.add_argument("--cut-tol", type=float, default=1e-7)
    parser.add_argument("--skip-fixed-history", action="store_true")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.mode == "smoke":
        cut_modes = (args.cut_mode,) if args.cut_mode in CUT_MODES else (("multi", "single") if args.cut_mode == "both" else ("multi",))
        max_iters = args.max_iters if args.max_iters is not None else 4
        time_limit = args.time_limit if args.time_limit is not None else 15.0
    else:
        cut_modes = (args.cut_mode,) if args.cut_mode in CUT_MODES else ("multi", "single")
        max_iters = args.max_iters if args.max_iters is not None else 60
        time_limit = args.time_limit if args.time_limit is not None else 30.0

    t_global = perf_counter()
    data, profile = load_case("p01")
    ref_info = load_reference_interval("p01", profile["instance_sha256"])
    ref_lower = Fraction(ref_info["intersection_lower"])
    ref_upper = Fraction(ref_info["intersection_upper"])

    ctx_orig = build_arm_context(data, "linked")
    ctx_sep = build_arm_context(data, "linked_separated")

    affinity = sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None
    paired_results: dict[str, dict] = {}
    all_sound = True
    all_overlap_ref = True

    for cm in cut_modes:
        rec_orig, vis_orig = run_benders_arm(
            data,
            ctx_orig,
            cm,
            max_iters=max_iters,
            time_limit=time_limit,
            rel_tol=args.rel_tol,
            cut_tol=args.cut_tol,
            ref_lower=ref_lower,
            ref_upper=ref_upper,
        )
        rec_sep, vis_sep = run_benders_arm(
            data,
            ctx_sep,
            cm,
            max_iters=max_iters,
            time_limit=time_limit,
            rel_tol=args.rel_tol,
            cut_tol=args.cut_tol,
            ref_lower=ref_lower,
            ref_upper=ref_upper,
        )
        path_cmp = compare_paths(vis_orig, vis_sep)
        fixed_diag = (
            None
            if args.skip_fixed_history
            else run_fixed_history_diagnostic(ctx_orig, ctx_sep, vis_orig, vis_sep)
        )
        for rec in (rec_orig, rec_sep):
            ver = rec["verification"]
            if ver is None or not ver["sound_lower_le_upper"]:
                all_sound = False
            if ver is None or not ver["overlaps_sealed_reference"]:
                all_overlap_ref = False

        paired_results[cm] = {
            "linked": rec_orig,
            "linked_separated": rec_sep,
            "separate_path_check": path_cmp,
            "secondary_fixed_history_diagnostic": fixed_diag,
        }

        for label, rec, extra in (
            ("linked", rec_orig, ""),
            ("linked_separated", rec_sep, f" | paths_distinct={path_cmp['paths_distinct']}"),
        ):
            ver = rec["verification"]
            if ver is not None:
                print(
                    f"[p01 | cut_mode={cm}] "
                    f"{label}: iters={rec['candidate_evaluations']} stop={rec['stop_reason']} "
                    f"L={ver['certified_lower_float']:.6f} U={ver['certified_upper_float']:.6f} "
                    f"gap={ver['certified_relative_gap_float']:.3e} t={rec['timing_seconds']['before_certificate']:.3f}s "
                    f"ref_ok={ver['overlaps_sealed_reference']}{extra}"
                )
            else:
                print(
                    f"[p01 | cut_mode={cm}] "
                    f"{label}: iters={rec['candidate_evaluations']} stop={rec['stop_reason']} "
                    f"no_certificate t={rec['timing_seconds']['before_certificate']:.3f}s{extra}"
                )

    payload = {
        "pilot": "paired_iterative_linked_benders_root_p01",
        "mode": args.mode,
        "case": "p01",
        "bound_scope_warning": (
            "All upper bounds reported here evaluate continuous fractional openings x in [0, 1]^n "
            "and are NOT integer feasible incumbents unless verification.bound_classification.is_binary_opening is true."
        ),
        "input_profile": profile,
        "sealed_reference_interval": ref_info,
        "config": {
            "cut_modes": list(cut_modes),
            "max_iters_per_arm": max_iters,
            "time_limit_seconds_per_arm": time_limit,
            "rel_tol": args.rel_tol,
            "cut_tol": args.cut_tol,
            "threads": 1,
            "cold_start": True,
        },
        "runtime": {
            "python": sys.version,
            "executable": sys.executable,
            "numpy": version("numpy"),
            "scipy": version("scipy"),
            "cpu_affinity": affinity,
            "script_sha256": _file_sha256(Path(__file__).resolve()),
        },
        "overall_verification": {
            "all_certificates_sound": all_sound,
            "all_certificates_overlap_sealed_reference": all_overlap_ref,
        },
        "paired_runs": paired_results,
        "total_wall_seconds": float(perf_counter() - t_global),
    }

    if args.out is not None:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=2, allow_nan=False)
            fh.write("\n")
        print(f"Wrote pilot result JSON: {args.out}")
    else:
        print(json.dumps(payload["overall_verification"], indent=2))


if __name__ == "__main__":
    main()
