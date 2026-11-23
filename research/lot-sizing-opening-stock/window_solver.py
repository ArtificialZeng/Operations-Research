"""Overlapping-window fix-and-optimize for capacitated lot sizing."""

import argparse
import json
import math
from multiprocessing import get_context
from pathlib import Path
from time import perf_counter

STARTED = perf_counter()

from cutoff_solver import highspy, np, prepare_problem, run_model, submit_start, write_checkpoint
from opening_incumbent import TOL, _evaluate, build_incumbent


def emit(event, **fields):
    print(json.dumps({"event": event, **fields}, allow_nan=False), flush=True)


def require_ok(status, action):
    if status != highspy.HighsStatus.kOk:
        raise RuntimeError(f"HiGHS could not {action}: {status.name}")


def build_model(problem):
    d, h, s, c, a, b, cap, p, ub_x = problem
    products, periods = d.shape
    count = d.size
    opening = np.arange(products, dtype=np.int32)
    setup = products + np.arange(count, dtype=np.int32).reshape(d.shape)
    production, inventory = setup + count, setup + 2 * count
    costs = np.concatenate((p, s.ravel(), c.ravel(), h.ravel()))
    allowed = ub_x > 0
    upper = np.concatenate((np.full(products, np.inf), allowed.ravel(), ub_x.ravel(), np.full(count, np.inf)))

    previous = np.column_stack((opening, inventory[:, :-1]))
    balance_columns = np.column_stack((previous.ravel(), production.ravel(), inventory.ravel()))
    link_columns = np.column_stack((production[allowed], setup[allowed]))
    capacity_columns = np.column_stack((setup.T, production.T))
    columns = np.concatenate((balance_columns.ravel(), link_columns.ravel(), capacity_columns.ravel()))
    coefficients = np.concatenate((
        np.tile((1.0, 1.0, -1.0), count),
        np.column_stack((np.ones(len(link_columns)), -ub_x[allowed])).ravel(),
        np.column_stack((b.T, a.T)).ravel(),
    ))
    row_lengths = np.repeat((3, 2, 2 * products), (count, len(link_columns), periods))
    starts = np.empty(len(row_lengths), dtype=np.int32)
    starts[0] = 0
    np.cumsum(row_lengths[:-1], out=starts[1:])
    lower_rows = np.concatenate((d.ravel(), np.full(len(link_columns) + periods, -np.inf)))
    upper_rows = np.concatenate((d.ravel(), np.zeros(len(link_columns)), cap))

    model = highspy.Highs()
    model.setOptionValue("output_flag", False)
    model.setOptionValue("threads", 2)
    model.setOptionValue("mip_rel_gap", 1e-6)
    require_ok(model.addCols(
        len(costs), costs, np.zeros(len(costs)), upper, 0,
        np.empty(0, dtype=np.int32), np.empty(0, dtype=np.int32), np.empty(0),
    ), "add the lot-sizing columns")
    require_ok(model.changeColsIntegrality(
        count, setup.ravel(), np.full(count, highspy.HighsVarType.kInteger.value, dtype=np.uint8),
    ), "declare the setup binaries")
    require_ok(model.addRows(
        len(starts), lower_rows, upper_rows, len(columns), starts, columns, coefficients,
    ), "add the inventory, production link, and capacity rows")
    return model, costs, (opening, setup, production, inventory)


def output_candidate(plan):
    objective, production, setup, inventory, opening = plan
    return objective, opening.tolist(), setup.tolist(), production.tolist(), inventory.tolist()


def window_schedule(periods):
    width = min(periods, 12, max(4, (periods + 7) // 8))
    starts = list(range(0, periods - width + 1, max(1, width // 2)))
    if starts[-1] != periods - width:
        starts.append(periods - width)
    return width, starts


def policy_order(policy, best, problem, width, starts):
    if policy is None:
        return starts
    _, production, setup, _, opening = best
    d, _, s, _, a, b, cap, p, _ = problem
    original = (setup, production, opening, d, s, a, b, cap, p)
    inputs = [array.copy() for array in original]
    starts_array = np.asarray(starts, dtype=np.int32)
    for array in (*inputs, starts_array):
        array.flags.writeable = False
    order = np.asarray(policy(*inputs, width, starts_array))
    if order.ndim != 1 or order.dtype.kind not in "iu" or sorted(order.tolist()) != starts:
        raise ValueError("window_policy.window_order must return a permutation of starts")
    return order.tolist()


def optimize_window(model, costs, indices, problem, best, start, width, deadline):
    opening, setup, production, inventory = indices
    _, x, y, inv, stock = best
    free = np.zeros(setup.shape[1], dtype=bool)
    free[start:start + width] = True
    lower = np.where(free, 0, y)
    upper = np.where(free, problem[-1] > 0, y)
    require_ok(model.changeColsBounds(setup.size, setup.ravel(), lower.ravel(), upper.ravel()),
               "fix setup decisions outside the window")
    require_ok(model.clearSolver(), "reset the window solver state")
    values = np.empty(len(costs), dtype=np.float64)
    values[opening], values[setup], values[production], values[inventory] = stock, y, x, inv
    submit_start(model, values, costs, best[0])
    if not run_model(model, deadline):
        return None

    values = np.asarray(model.getSolution().col_value)
    y_raw = values[setup]
    y_new = np.rint(y_raw).astype(np.int8)
    if np.any(np.abs(y_raw - y_new) > TOL) or not np.array_equal(y[:, ~free], y_new[:, ~free]):
        return None
    x_new, stock_new = values[production], values[opening]
    if np.any(x_new < -TOL) or np.any(stock_new < -TOL):
        return None
    return _evaluate(*problem, np.maximum(x_new, 0), y_new, np.maximum(stock_new, 0))


def run_windows(sender, raw_problem, floor, arm, deadline):
    with sender:
        problem = tuple(np.asarray(array, dtype=np.float64) for array in raw_problem)
        best = build_incumbent(*problem, deadline)
        emit("initializer", objective=best[0], opening=float(np.sum(best[-1])))
        if best[0] < floor[0]:
            sender.send(("checkpoint", output_candidate(best)))
        if perf_counter() < deadline:
            policy = None
            if arm == "adaptive_window":
                from window_policy import window_order

                policy = window_order
            width, starts = window_schedule(problem[0].shape[1])
            model, costs, indices = build_model(problem)
            sweep = 0
            while perf_counter() < deadline:
                order = policy_order(policy, best, problem, width, starts)
                emit("sweep", sweep=sweep, width=width, starts=order)
                improved = False
                for i, start in enumerate(order):
                    now = perf_counter()
                    remaining = deadline - now
                    if remaining < 0.05:
                        break
                    allowance = min(remaining, max(0.10, remaining / (len(order) - i)))
                    candidate = optimize_window(model, costs, indices, problem, best, start, width, now + allowance)
                    previous = best[0]
                    if candidate is not None and candidate[0] < previous - 1e-6:
                        best = candidate
                        improved = True
                        sender.send(("checkpoint", output_candidate(best)))
                    emit("window", sweep=sweep, start=start, stop=start + width, allowance=allowance,
                         improved=bool(best[0] < previous), objective=best[0],
                         opening=float(np.sum(best[-1])))
                if not improved:
                    break
                sweep += 1
        sender.send(("done", output_candidate(best)))


def watch(output, problem, best, arm, solve_deadline, cutoff):
    context = get_context("spawn")
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=run_windows, args=(sender, problem, best, arm, solve_deadline))
    timed_out = False
    completed = False
    with receiver, sender:
        process.start()
        sender.close()
        try:
            while True:
                remaining = cutoff - perf_counter()
                if remaining <= 0 or not receiver.poll(remaining):
                    timed_out = True
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
            process.join(timeout=0.03)
            if process.is_alive():
                process.terminate()
                process.join(timeout=0.12)
            if process.is_alive():
                process.kill()
                process.join(timeout=0.12)
    emit("final", arm=arm, objective=best[0], opening=sum(best[1]), parent_cutoff=timed_out)
    if not completed and not timed_out:
        raise RuntimeError(f"Window worker exited before completion, exit={process.exitcode}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-limit", type=float, default=10.0)
    parser.add_argument("--experiment-arm", choices=("window", "adaptive_window"), default="window")
    args = parser.parse_args()
    if not math.isfinite(args.time_limit) or args.time_limit <= 0:
        parser.error("--time-limit must be finite and positive")
    data = json.loads(args.instance.read_text(encoding="utf-8"))
    problem, _, best = prepare_problem(data)
    write_checkpoint(args.output, best)
    outer = STARTED + args.time_limit
    solve_deadline = outer - min(1.5, args.time_limit / 4)
    cutoff = outer - min(0.55, args.time_limit / 8)
    if perf_counter() < solve_deadline:
        watch(args.output, problem, best, args.experiment_arm, solve_deadline, cutoff)
    else:
        emit("final", arm=args.experiment_arm, objective=best[0], opening=sum(best[1]), parent_cutoff=False)


if __name__ == "__main__":
    main()
