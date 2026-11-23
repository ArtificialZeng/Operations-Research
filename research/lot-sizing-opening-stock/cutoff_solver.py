"""Explicit objective-bound controls for the frozen Degraeve experiment."""

import argparse
from collections import deque
import json
import math
from multiprocessing import get_context
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile
import time

STARTED = time.perf_counter()

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("OPENBLAS_NUM_THREADS", "2")
os.environ.setdefault("MKL_NUM_THREADS", "2")

import highspy
import numpy as np


def compute_objective(init_inv, y, x, inv, p, s, c, h):
    n_prod = len(p)
    n_per = len(s[0])
    total = 0.0
    for i in range(n_prod):
        total += p[i] * init_inv[i]
        si = s[i]
        ci = c[i]
        hi = h[i]
        yi = y[i]
        xi = x[i]
        invi = inv[i]
        for t in range(n_per):
            total += si[t] * yi[t] + ci[t] * xi[t] + hi[t] * invi[t]
    return float(total)


def repair_and_evaluate(y_raw, x_raw, d, h, s, c, a, b, cap, p, ub_x):
    n_prod = len(d)
    n_per = len(cap)
    y = [[1 if y_raw[i][t] >= 0.5 and ub_x[i][t] > 0.0 else 0 for t in range(n_per)] for i in range(n_prod)]
    x = [[0.0] * n_per for _ in range(n_prod)]
    for i in range(n_prod):
        for t in range(n_per):
            if y[i][t]:
                val = float(x_raw[i][t])
                if val < 0.0:
                    val = 0.0
                elif val > ub_x[i][t]:
                    val = ub_x[i][t]
                x[i][t] = val

    for t in range(n_per):
        ct = float(cap[t])
        setup_used = sum(b[i][t] * y[i][t] for i in range(n_prod))
        if setup_used > ct:
            active = sorted(
                (i for i in range(n_prod) if y[i][t]),
                key=lambda i: x[i][t],
            )
            for i in active:
                if setup_used <= ct:
                    break
                y[i][t] = 0
                x[i][t] = 0.0
                setup_used -= b[i][t]
        prod_used = sum(a[i][t] * x[i][t] for i in range(n_prod))
        if setup_used + prod_used > ct:
            avail = max(0.0, ct - setup_used)
            if prod_used > 0.0:
                scale = max(0.0, (avail - 1e-11) / prod_used)
                for i in range(n_prod):
                    x[i][t] *= scale
            else:
                for i in range(n_prod):
                    x[i][t] = 0.0

    init_inv = [0.0] * n_prod
    inv = [[0.0] * n_per for _ in range(n_prod)]
    for i in range(n_prod):
        bal = 0.0
        min_bal = 0.0
        for t in range(n_per):
            bal += x[i][t] - d[i][t]
            if bal < min_bal:
                min_bal = bal
        i0 = -min_bal if min_bal < 0.0 else 0.0
        cur = i0
        for t in range(n_per):
            cur = cur + x[i][t] - d[i][t]
            if cur < 0.0:
                i0 += -cur
                cur = 0.0
            inv[i][t] = cur
        if i0 != (-min_bal if min_bal < 0.0 else 0.0):
            cur = i0
            for t in range(n_per):
                cur = cur + x[i][t] - d[i][t]
                inv[i][t] = 0.0 if cur < 0.0 else cur
        init_inv[i] = i0

    obj = compute_objective(init_inv, y, x, inv, p, s, c, h)
    return obj, init_inv, y, x, inv


def log(message):
    print(message, file=sys.stderr, flush=True)


def facility_start(warm, n_cols, d, y_idx, w_init, w_prod):
    _, stock, setup, production, _ = warm
    values = np.zeros(n_cols, dtype=np.float64)
    values[np.asarray(y_idx)] = setup
    for i, demands in enumerate(d):
        lots = deque()
        if stock[i] > 0:
            lots.append((-1, stock[i]))
        for k, demand in enumerate(demands):
            if production[i][k] > 0:
                lots.append((k, production[i][k]))
            remaining = float(demand)
            while remaining > 0 and lots:
                t, available = lots.popleft()
                amount = min(remaining, available)
                column = w_init.get((i, k)) if t == -1 else w_prod.get((i, t, k))
                if column is None:
                    if amount > 1e-8:
                        raise ValueError("Warm solution requires a missing facility arc")
                else:
                    values[column] = amount
                remaining -= amount
                if available > amount:
                    lots.appendleft((t, available - amount))
            if remaining > 1e-7:
                raise ValueError("Warm solution does not cover its declared demand")
        if sum(amount for _, amount in lots) > 1e-7:
            raise ValueError("Facility columns cannot represent remaining terminal stock")
    return values


def submit_start(model, values, costs, expected):
    objective = float(np.dot(values, costs))
    if not math.isclose(objective, expected, rel_tol=1e-10, abs_tol=1e-4):
        raise ValueError(f"Warm column objective {objective} differs from witness {expected}")
    indices = np.arange(len(values), dtype=np.int32)
    status = model.setSolution(len(values), indices, values)
    native = model.getSolution()
    accepted = (
        status == highspy.HighsStatus.kOk
        and native.value_valid
        and np.array_equal(native.col_value, values)
    )
    log(f"native_start_accepted={int(accepted)} status={status.name} objective={objective:.12g}")
    if not accepted:
        raise RuntimeError("HiGHS did not retain the full warm-start column vector")


def add_objective_cutoff(model, upper_bound):
    lp = model.getLp()
    costs = np.asarray(lp.col_cost_, dtype=np.float64)
    nonzero = np.flatnonzero(costs).astype(np.int32)
    slack = max(1e-4, 1e-10 * max(abs(upper_bound), abs(lp.offset_)))
    rhs = upper_bound - lp.offset_ + slack
    status = model.addRow(-highspy.kHighsInf, rhs, len(nonzero), nonzero, costs[nonzero])
    if status != highspy.HighsStatus.kOk:
        raise RuntimeError(f"HiGHS did not add the objective cutoff row: {status.name}")
    log(f"objective_cutoff={upper_bound:.12g} cutoff_slack={slack:.12g}")


def run_model(model, deadline):
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        return False
    model.setOptionValue("time_limit", remaining)
    model.run()
    return model.getInfo().primal_solution_status == highspy.SolutionStatus.kSolutionStatusFeasible


def solve_fl_milp(d, h, s, c, a, b, cap, p, ub_x, deadline, warm=None, cutoff=None):
    n_prod = len(d)
    n_per = len(cap)
    inf = highspy.kHighsInf

    costs = []
    lbs = []
    ubs = []

    y_idx = [[-1] * n_per for _ in range(n_prod)]
    for i in range(n_prod):
        for t in range(n_per):
            y_idx[i][t] = len(costs)
            costs.append(float(s[i][t]))
            lbs.append(0.0)
            ubs.append(1.0 if ub_x[i][t] > 0.0 else 0.0)

    w_init = {}
    w_prod = {}
    for i in range(n_prod):
        hi = h[i]
        ci = c[i]
        di = d[i]
        pref_h = [0.0] * (n_per + 1)
        for t in range(n_per):
            pref_h[t + 1] = pref_h[t] + hi[t]
        for k in range(n_per):
            dk = float(di[k])
            if dk <= 0.0:
                continue
            w_init[(i, k)] = len(costs)
            costs.append(float(p[i]) + pref_h[k])
            lbs.append(0.0)
            ubs.append(dk)
            for t in range(k + 1):
                u = min(dk, ub_x[i][t])
                if u <= 0.0:
                    continue
                w_prod[(i, t, k)] = len(costs)
                costs.append(float(ci[t]) + (pref_h[k] - pref_h[t]))
                lbs.append(0.0)
                ubs.append(u)

    n_cols = len(costs)
    row_lhs = []
    row_rhs = []
    row_starts = []
    row_idx = []
    row_val = []

    for i in range(n_prod):
        for k in range(n_per):
            dk = float(d[i][k])
            if dk <= 0.0:
                continue
            row_starts.append(len(row_idx))
            row_lhs.append(dk)
            row_rhs.append(dk)
            row_idx.append(w_init[(i, k)])
            row_val.append(1.0)
            for t in range(k + 1):
                col = w_prod.get((i, t, k))
                if col is not None:
                    row_idx.append(col)
                    row_val.append(1.0)

    for (i, t, k), col in w_prod.items():
        u = min(float(d[i][k]), ub_x[i][t])
        row_starts.append(len(row_idx))
        row_lhs.append(-inf)
        row_rhs.append(0.0)
        row_idx.append(col)
        row_val.append(1.0)
        row_idx.append(y_idx[i][t])
        row_val.append(-u)

    for t in range(n_per):
        row_starts.append(len(row_idx))
        row_lhs.append(-inf)
        row_rhs.append(float(cap[t]))
        for i in range(n_prod):
            bt = float(b[i][t])
            if bt != 0.0 and ub_x[i][t] > 0.0:
                row_idx.append(y_idx[i][t])
                row_val.append(bt)
            at = float(a[i][t])
            if at != 0.0:
                for k in range(t, n_per):
                    col = w_prod.get((i, t, k))
                    if col is not None:
                        row_idx.append(col)
                        row_val.append(at)

    h_mod = highspy.Highs()
    h_mod.setOptionValue("output_flag", False)
    h_mod.setOptionValue("threads", 2)
    h_mod.setOptionValue("mip_rel_gap", 1e-6)

    empty_i = np.array([], dtype=np.int32)
    empty_f = np.array([], dtype=np.float64)
    h_mod.addCols(
        n_cols,
        np.asarray(costs, dtype=np.float64),
        np.asarray(lbs, dtype=np.float64),
        np.asarray(ubs, dtype=np.float64),
        0,
        empty_i,
        empty_i,
        empty_f,
    )
    for i in range(n_prod):
        for t in range(n_per):
            h_mod.changeColIntegrality(y_idx[i][t], highspy.HighsVarType.kInteger)

    h_mod.addRows(
        len(row_lhs),
        np.asarray(row_lhs, dtype=np.float64),
        np.asarray(row_rhs, dtype=np.float64),
        len(row_idx),
        np.asarray(row_starts, dtype=np.int32),
        np.asarray(row_idx, dtype=np.int32),
        np.asarray(row_val, dtype=np.float64),
    )

    if cutoff is not None:
        add_objective_cutoff(h_mod, cutoff)
    if warm is not None and time.perf_counter() < deadline:
        values = facility_start(warm, n_cols, d, y_idx, w_init, w_prod)
        submit_start(h_mod, values, costs, warm[0])
    if not run_model(h_mod, deadline):
        return None
    sol = h_mod.getSolution().col_value
    y_raw = [[sol[y_idx[i][t]] for t in range(n_per)] for i in range(n_prod)]
    x_raw = [[0.0] * n_per for _ in range(n_prod)]
    for (i, t, k), col in w_prod.items():
        x_raw[i][t] += sol[col]
    return y_raw, x_raw


def solve_agg_milp(d, h, s, c, a, b, cap, p, ub_x, deadline, warm=None, cutoff=None):
    n_prod = len(d)
    n_per = len(cap)
    inf = highspy.kHighsInf

    costs = []
    lbs = []
    ubs = []

    y_idx = [[-1] * n_per for _ in range(n_prod)]
    x_idx = [[-1] * n_per for _ in range(n_prod)]
    inv_idx = [[-1] * n_per for _ in range(n_prod)]
    init_idx = [-1] * n_prod

    for i in range(n_prod):
        init_idx[i] = len(costs)
        costs.append(float(p[i]))
        lbs.append(0.0)
        ubs.append(inf)
        for t in range(n_per):
            y_idx[i][t] = len(costs)
            costs.append(float(s[i][t]))
            lbs.append(0.0)
            ubs.append(1.0 if ub_x[i][t] > 0.0 else 0.0)

            x_idx[i][t] = len(costs)
            costs.append(float(c[i][t]))
            lbs.append(0.0)
            ubs.append(ub_x[i][t])

            inv_idx[i][t] = len(costs)
            costs.append(float(h[i][t]))
            lbs.append(0.0)
            ubs.append(inf)

    row_lhs = []
    row_rhs = []
    row_starts = []
    row_idx = []
    row_val = []

    for i in range(n_prod):
        for t in range(n_per):
            row_starts.append(len(row_idx))
            dt = float(d[i][t])
            row_lhs.append(dt)
            row_rhs.append(dt)
            row_idx.append(init_idx[i] if t == 0 else inv_idx[i][t - 1])
            row_val.append(1.0)
            row_idx.append(x_idx[i][t])
            row_val.append(1.0)
            row_idx.append(inv_idx[i][t])
            row_val.append(-1.0)

            if ub_x[i][t] > 0.0:
                row_starts.append(len(row_idx))
                row_lhs.append(-inf)
                row_rhs.append(0.0)
                row_idx.append(x_idx[i][t])
                row_val.append(1.0)
                row_idx.append(y_idx[i][t])
                row_val.append(-ub_x[i][t])

    for t in range(n_per):
        row_starts.append(len(row_idx))
        row_lhs.append(-inf)
        row_rhs.append(float(cap[t]))
        for i in range(n_prod):
            if b[i][t] != 0.0 and ub_x[i][t] > 0.0:
                row_idx.append(y_idx[i][t])
                row_val.append(float(b[i][t]))
            if a[i][t] != 0.0 and ub_x[i][t] > 0.0:
                row_idx.append(x_idx[i][t])
                row_val.append(float(a[i][t]))

    h_mod = highspy.Highs()
    h_mod.setOptionValue("output_flag", False)
    h_mod.setOptionValue("threads", 2)
    h_mod.setOptionValue("mip_rel_gap", 1e-6)

    empty_i = np.array([], dtype=np.int32)
    empty_f = np.array([], dtype=np.float64)
    h_mod.addCols(
        len(costs),
        np.asarray(costs, dtype=np.float64),
        np.asarray(lbs, dtype=np.float64),
        np.asarray(ubs, dtype=np.float64),
        0,
        empty_i,
        empty_i,
        empty_f,
    )
    for i in range(n_prod):
        for t in range(n_per):
            h_mod.changeColIntegrality(y_idx[i][t], highspy.HighsVarType.kInteger)

    h_mod.addRows(
        len(row_lhs),
        np.asarray(row_lhs, dtype=np.float64),
        np.asarray(row_rhs, dtype=np.float64),
        len(row_idx),
        np.asarray(row_starts, dtype=np.int32),
        np.asarray(row_idx, dtype=np.int32),
        np.asarray(row_val, dtype=np.float64),
    )

    if cutoff is not None:
        add_objective_cutoff(h_mod, cutoff)
    if warm is not None and time.perf_counter() < deadline:
        _, stock, setup, production, inventory = warm
        values = np.zeros(len(costs), dtype=np.float64)
        values[init_idx] = stock
        values[np.asarray(y_idx)] = setup
        values[np.asarray(x_idx)] = production
        values[np.asarray(inv_idx)] = inventory
        submit_start(h_mod, values, costs, warm[0])
    if not run_model(h_mod, deadline):
        return None
    sol = h_mod.getSolution().col_value
    y_raw = [[sol[y_idx[i][t]] for t in range(n_per)] for i in range(n_prod)]
    x_raw = [[sol[x_idx[i][t]] for t in range(n_per)] for i in range(n_prod)]
    return y_raw, x_raw


def prepare_problem(data):
    params = data["parameters"]
    d = params["demand"]
    h = params["holding_cost"]
    s = params["setup_cost"]
    c = params["variable_production_cost"]
    a = params["variable_production_time"]
    b = params["setup_time"]
    cap = params["capacity"]
    p = params["initial_inventory_cost"]

    n_prod = len(d)
    n_per = len(cap)

    ub_x = [[0.0] * n_per for _ in range(n_prod)]
    for i in range(n_prod):
        rem_d = 0.0
        for t in range(n_per - 1, -1, -1):
            rem_d += float(d[i][t])
            avail = float(cap[t]) - float(b[i][t])
            if avail < 0.0:
                ub_x[i][t] = 0.0
            elif a[i][t] > 0.0:
                ub_x[i][t] = min(avail / float(a[i][t]), rem_d)
            else:
                ub_x[i][t] = rem_d

    zero_y = [[0] * n_per for _ in range(n_prod)]
    zero_x = [[0.0] * n_per for _ in range(n_prod)]
    best = repair_and_evaluate(zero_y, zero_x, d, h, s, c, a, b, cap, p, ub_x)

    nonneg_costs = (
        all(val >= 0.0 for val in p)
        and all(val >= 0.0 for row in h for val in row)
        and all(val >= 0.0 for row in c for val in row)
        and all(val >= 0 for row in d for val in row)
    )
    use_fl = nonneg_costs and (n_prod * n_per * (n_per + 1) // 2 <= 45000)

    return (d, h, s, c, a, b, cap, p, ub_x), use_fl, best


def write_checkpoint(path, candidate):
    obj, init_inv, y, x, inv = candidate
    out = {
        "objective_value": obj,
        "variables": {
            "production": x,
            "setup": y,
            "inventory": inv,
            "initial_inventory": init_inv,
        },
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False
        ) as handle:
            temporary = Path(handle.name)
            json.dump(out, handle, allow_nan=False)
        temporary.replace(path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def run_arm(sender, problem, use_fl, best, arm, deadline):
    with sender:
        if arm != "cold" and time.perf_counter() < deadline:
            from opening_incumbent import build_incumbent

            obj, x, y, inv, stock = build_incumbent(*problem, deadline)
            log(f"initializer_objective={obj:.12g} initializer_opening_units={sum(stock):.12g}")
            if obj < best[0]:
                best = obj, stock.tolist(), y.tolist(), x.tolist(), inv.tolist()
                sender.send(("initializer", best))

        if time.perf_counter() < deadline:
            solve = solve_fl_milp if use_fl else solve_agg_milp
            warm = best if arm in ("warm", "warm_cutoff") else None
            cutoff = best[0] if arm in ("cutoff", "warm_cutoff") else None
            result = solve(*problem, deadline, warm=warm, cutoff=cutoff)
            if result is not None:
                candidate = repair_and_evaluate(*result, *problem)
                if candidate[0] < best[0]:
                    best = candidate
        sender.send(("done", best))


def run_with_watchdog(output, problem, use_fl, best, arm, solver_deadline, cutoff_deadline):
    context = get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    child = context.Process(target=run_arm, args=(sender, problem, use_fl, best, arm, solver_deadline))
    cutoff = False
    completed = False
    with receiver, sender:
        child.start()
        sender.close()
        try:
            while True:
                remaining = cutoff_deadline - time.perf_counter()
                if remaining <= 0 or not receiver.poll(remaining):
                    cutoff = True
                    break
                try:
                    event, candidate = receiver.recv()
                except EOFError:
                    break
                if candidate[0] < best[0]:
                    write_checkpoint(output, candidate)
                    best = candidate
                if event == "done":
                    completed = True
                    break
        finally:
            child.join(timeout=0.03)
            if child.is_alive():
                child.terminate()
                child.join(timeout=0.12)
            if child.is_alive():
                child.kill()
                child.join(timeout=0.12)
    log(f"parent_cutoff={int(cutoff)} final_objective={best[0]:.12g} final_opening_units={sum(best[1]):.12g}")
    if not completed and not cutoff:
        raise RuntimeError(f"Solver child exited before reporting completion, exit={child.exitcode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=60.0)
    parser.add_argument(
        "--experiment-arm", choices=("cold", "fallback", "warm", "cutoff", "warm_cutoff"), default="cold"
    )
    args = parser.parse_args()
    if not math.isfinite(args.time_limit) or args.time_limit <= 0:
        parser.error("--time-limit must be finite and positive")

    data = json.loads(args.instance.read_text(encoding="utf-8"))
    problem, use_fl, best = prepare_problem(data)
    write_checkpoint(args.output, best)
    log(f"experiment_arm={args.experiment_arm} model={'facility' if use_fl else 'aggregate'}")
    outer_deadline = STARTED + args.time_limit
    solver_deadline = outer_deadline - min(1.5, args.time_limit / 4)
    cutoff_deadline = outer_deadline - min(0.55, args.time_limit / 8)
    if time.perf_counter() < solver_deadline:
        run_with_watchdog(args.output, problem, use_fl, best, args.experiment_arm, solver_deadline, cutoff_deadline)
    else:
        log(f"parent_cutoff=0 solver_budget_exhausted=1 final_objective={best[0]:.12g} final_opening_units={sum(best[1]):.12g}")


if __name__ == "__main__":
    main()
