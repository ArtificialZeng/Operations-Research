#!/usr/bin/env python3
"""FrontierOR Main-Track Candidate for bodur2017: Stochastic Capacitated Facility Location (SCFLP).

Algorithm:
  - Guaranteed feasible floor: all-open configuration (plus deterministic greedy transportation
    fallback if any LP call were ever interrupted), ensuring a valid decision witness under any budget.
  - Phase 1: In-Out Stabilized Multi-Cut LP-Relaxation Benders Decomposition (Bodur et al. 2017 /
    Fischetti, Ljubic, Sinnl 2016) with 1 exact Jensen aggregate transportation block inside the
    LP master and Pareto-tightened closed-facility duals beta_i = max(0, max_j(alpha_j - q_ij))
    extracted from a persistent warm-started CLP dual-simplex subproblem solver sorted by demand.
  - Phase 2: Exact compact (I + G)-variable SCIP Master MIP with multi-cut Benders cuts and
    Fischetti-Lodi Local Branching (Hamming <= 2, <= 4) probes around the incumbent (global LB
    updated strictly on unrestricted global solves).
  - Final stage: Measured-reserve wall-clock guard extracts exact sparse CLP primal flows y[k][i][j]
    for best_x, recomputes objective_value directly from the serialized sparse witness (0 discrepancy),
    and writes compact JSON complying with FrontierOR Release Contract v2.

Dependencies: Python stdlib, numpy, ortools (open-source PyPI packages only).
"""

import argparse
import json
from pathlib import Path
import time
import numpy as np
from ortools.linear_solver import pywraplp


def fallback_greedy_flows(x_bin, s_cap, lam, q):
    """Deterministic feasible transportation fallback if LP extraction is ever unavailable.
    Valid whenever sum_i s_i * x_i >= max_k sum_j lam[k, j]."""
    I, J = q.shape
    K = lam.shape[0]
    open_idx = [i for i in range(I) if x_bin[i] > 0.5]
    # Pre-sort open facilities by cost for each customer
    pref = [sorted(open_idx, key=lambda i: (float(q[i, j]), i)) for j in range(J)]
    flows = {}
    for k in range(K):
        rem_cap = {i: float(s_cap[i]) for i in open_idx}
        lk = lam[k]
        scen_dict = {}
        # Serve customers in descending demand order; exact feasibility guaranteed since sum(rem_cap) >= sum(lk)
        for j in sorted(range(J), key=lambda idx: -float(lk[idx])):
            need = float(lk[j])
            if need <= 1e-12:
                continue
            for i in pref[j]:
                avail = rem_cap[i]
                if avail <= 1e-12:
                    continue
                ship = min(need, avail)
                rem_cap[i] -= ship
                need -= ship
                scen_dict.setdefault(str(i), {})[str(j)] = ship
                if need <= 1e-12:
                    break
        flows[str(k)] = scen_dict
    return flows


def recompute_objective_from_sparse(x_bin, flows, f_cost, probs, q):
    opening = float(sum(float(f_cost[i]) for i in range(len(f_cost)) if x_bin[i] > 0.5))
    transport = 0.0
    for k_str, scen_data in flows.items():
        pk = float(probs[int(k_str)])
        for i_str, row_data in scen_data.items():
            qi = q[int(i_str)]
            for j_str, val in row_data.items():
                transport += pk * float(qi[int(j_str)]) * float(val)
    return opening + transport


def expected_demand_seed(f_cost, capacity, q, mean, max_dem, deadline):
    """Minimize deterministic mean-demand costs subject to peak recourse capacity."""
    started = time.process_time()
    sites, customers = q.shape
    model = pywraplp.Solver.CreateSolver("SCIP")
    model.SetNumThreads(1)
    model.SuppressOutput()
    opened = [model.BoolVar("") for _ in range(sites)]
    peak = model.Constraint(max_dem, model.infinity())
    shipments = [[model.NumVar(0, model.infinity(), "") for _ in range(customers)]
                 for _ in range(sites)]
    needs = [model.Constraint(float(amount), float(amount)) for amount in mean]
    objective = model.Objective()
    for i, facility in enumerate(opened):
        peak.SetCoefficient(facility, float(capacity[i]))
        available = model.Constraint(-model.infinity(), 0)
        available.SetCoefficient(facility, -float(capacity[i]))
        objective.SetCoefficient(facility, float(f_cost[i]))
        for j, flow in enumerate(shipments[i]):
            available.SetCoefficient(flow, 1)
            needs[j].SetCoefficient(flow, 1)
            objective.SetCoefficient(flow, float(q[i, j]))
    objective.SetMinimization()
    remaining = deadline - time.perf_counter()
    meta = {"mean_cflp_status": "budget_exhausted"}
    selected = None
    if remaining > 0:
        model.SetTimeLimit(max(1, int(remaining * 1000)))
        status = model.Solve()
        meta["mean_cflp_status"] = {model.OPTIMAL: "optimal", model.FEASIBLE: "feasible",
                                   model.NOT_SOLVED: "no_incumbent"}.get(status, str(status))
        if status in (model.OPTIMAL, model.FEASIBLE):
            pattern = np.array([round(var.solution_value()) for var in opened], dtype=np.float64)
            if float(capacity @ pattern) >= max_dem - 1e-9:
                selected = pattern
                meta["mean_cflp_objective"] = objective.Value()
                meta["mean_cflp_open"] = int(pattern.sum())
            else:
                meta["mean_cflp_status"] = "peak_capacity_guard"
    meta["mean_cflp_cpu_seconds"] = time.process_time() - started
    return selected, meta


def solve(instance: dict, time_limit_s: float = 60.0, t_entry: float = None,
          initializer="all-open", trace=None) -> dict:
    t0 = time.perf_counter() if t_entry is None else float(t_entry)
    if trace is None:
        trace = {}
    I = int(instance["num_facilities"])
    J = int(instance["num_customers"])
    K = int(instance["num_scenarios"])
    f_cost = np.array([float(f["opening_cost"]) for f in instance["facilities"]], dtype=np.float64)
    s_cap = np.array([float(f["capacity"]) for f in instance["facilities"]], dtype=np.float64)
    q = np.array(instance["transportation_costs"], dtype=np.float64)
    lam = np.array([sc["demands"] for sc in instance["scenarios"]], dtype=np.float64)
    probs = np.array([float(sc["probability"]) for sc in instance["scenarios"]], dtype=np.float64)

    tot_dem = lam.sum(axis=1)
    max_dem = float(tot_dem.max())

    # Guaranteed feasible initial solution: all facilities open
    best_x = np.ones(I, dtype=np.float64)
    if float(np.dot(s_cap, best_x)) < max_dem - 1e-9:
        raise ValueError("Instance total facility capacity is below maximum scenario demand")
    trace["initializer"] = initializer
    if initializer == "expected-demand":
        expected = probs @ lam
        seed_deadline = t0 + min(0.7, 0.35 * time_limit_s)
        seed, metadata = expected_demand_seed(f_cost, s_cap, q, expected, max_dem, seed_deadline)
        trace.update(metadata)
        if seed is not None:
            best_x = seed
    trace["initial_open"] = [i for i in range(I) if best_x[i] > 0.5]
    trace["peak_demand"] = max_dem
    trace["initial_capacity"] = float(s_cap @ best_x)
    trace["initial_opening_cost"] = float(f_cost @ best_x)
    trace["recourse_sweeps"] = 0
    trace["master_solves"] = 0

    # Sort scenarios by total demand so warm-started CLP dual simplex shares optimal basis across neighbors
    order = np.argsort(tot_dem)
    G = min(30, K)
    groups = [order[g * K // G : (g + 1) * K // G] for g in range(G)]
    scen_to_g = np.empty(K, dtype=np.int32)
    for g, idxs in enumerate(groups):
        scen_to_g[idxs] = g

    # Persistent warm-started CLP transportation subproblem solver
    sub = pywraplp.Solver.CreateSolver("CLP")
    sub.SetNumThreads(1)
    y_vars = [[sub.NumVar(0.0, sub.infinity(), "") for j in range(J)] for i in range(I)]
    dem_con = [sub.Constraint(0.0, sub.infinity()) for j in range(J)]
    cap_con = [sub.Constraint(-sub.infinity(), 0.0) for i in range(I)]
    sub_obj = sub.Objective()
    for i in range(I):
        qi = q[i]
        yi = y_vars[i]
        ci = cap_con[i]
        for j in range(J):
            v = yi[j]
            dem_con[j].SetCoefficient(v, 1.0)
            ci.SetCoefficient(v, 1.0)
            sub_obj.SetCoefficient(v, float(qi[j]))
    sub_obj.SetMinimization()

    def eval_and_cuts(x_vec, extract_flows=False):
        trace["recourse_sweeps"] += 1
        for i in range(I):
            cap_con[i].SetUb(float(s_cap[i] * x_vec[i]))
        exp_trans = 0.0
        c0 = np.zeros(G, dtype=np.float64)
        coeff = np.zeros((G, I), dtype=np.float64)
        flows = {} if extract_flows else None
        for k in order:
            lk = lam[k]
            for j in range(J):
                dem_con[j].SetLb(float(lk[j]))
            st = sub.Solve()
            if st != pywraplp.Solver.OPTIMAL:
                return None, None, None, None
            val = sub_obj.Value()
            pk = probs[k]
            exp_trans += pk * val
            alpha = np.fromiter((dem_con[j].DualValue() for j in range(J)), dtype=np.float64, count=J)
            np.maximum(alpha, 0.0, out=alpha)
            beta = np.maximum(0.0, np.max(alpha[None, :] - q, axis=1))
            g = scen_to_g[k]
            c0[g] += pk * float(np.dot(lk, alpha))
            coeff[g] += pk * s_cap * beta
            if extract_flows:
                scen_dict = {}
                for i in range(I):
                    if x_vec[i] < 0.5:
                        continue
                    row = {}
                    yi = y_vars[i]
                    for j in range(J):
                        v = yi[j].solution_value()
                        if v > 1e-9:
                            row[str(j)] = float(v)
                    if row:
                        scen_dict[str(i)] = row
                flows[str(int(k))] = scen_dict
        return exp_trans, c0, coeff, flows

    # Evaluate the chosen seed for a feasible upper bound, initial cuts and measured sweep time.
    t_eval0 = time.perf_counter()
    t_trans, c0, coeff, _ = eval_and_cuts(best_x, extract_flows=False)
    t_eval = max(0.05, time.perf_counter() - t_eval0)

    if t_trans is None:
        # Ultra-safe fallback
        flows = fallback_greedy_flows(best_x, s_cap, lam, q)
        obj_val = recompute_objective_from_sparse(best_x, flows, f_cost, probs, q)
        return {
            "objective_value": obj_val,
            "open_facilities": [i for i in range(I) if best_x[i] > 0.5],
            "x": {str(i): int(round(best_x[i])) for i in range(I)},
            "y": flows,
        }

    best_ub = float(np.dot(f_cost, best_x) + t_trans)
    trace["initial_stochastic_objective"] = best_ub
    best_lb = 0.0
    evaluated = {tuple(int(round(v)) for v in best_x): best_ub}

    def calc_search_deadline(cur_t_eval):
        res_s = min(max(4.0, 2.2 * cur_t_eval + 2.8), max(2.5, 0.35 * time_limit_s))
        return t0 + max(0.0, time_limit_s - res_s)

    # Dynamic wall-clock reserve strictly protecting final exact flow extraction + JSON serialization
    search_deadline = calc_search_deadline(t_eval)

    if time.perf_counter() < search_deadline:
        def build_master(backend, binary=True, with_jensen=True):
            m = pywraplp.Solver.CreateSolver(backend)
            m.SetNumThreads(1)
            xm = [m.BoolVar(f"x_{i}") if binary else m.NumVar(0.0, 1.0, f"x_{i}") for i in range(I)]
            thm = [m.NumVar(0.0, m.infinity(), f"th_{g}") for g in range(G)]
            c_tot = m.Constraint(max_dem, m.infinity())
            for i in range(I):
                c_tot.SetCoefficient(xm[i], float(s_cap[i]))
            if with_jensen:
                agg_dem = (probs[:, None] * lam).sum(axis=0)
                w_tot = float(probs.sum())
                yb = [[m.NumVar(0.0, m.infinity(), "") for j in range(J)] for i in range(I)]
                for j in range(J):
                    cj = m.Constraint(float(agg_dem[j]), m.infinity())
                    for i in range(I):
                        cj.SetCoefficient(yb[i][j], 1.0)
                for i in range(I):
                    ci = m.Constraint(-m.infinity(), 0.0)
                    ci.SetCoefficient(xm[i], -float(w_tot * s_cap[i]))
                    for j in range(J):
                        ci.SetCoefficient(yb[i][j], 1.0)
                ct = m.Constraint(0.0, m.infinity())
                for g in range(G):
                    ct.SetCoefficient(thm[g], 1.0)
                for i in range(I):
                    for j in range(J):
                        ct.SetCoefficient(yb[i][j], -float(q[i, j]))
            obj = m.Objective()
            for i in range(I):
                obj.SetCoefficient(xm[i], float(f_cost[i]))
            for g in range(G):
                obj.SetCoefficient(thm[g], 1.0)
            obj.SetMinimization()
            return m, xm, thm, obj

        lp_m, x_lp, th_lp, obj_lp = build_master("CLP", binary=False, with_jensen=True)
        mip_m, x_mip, th_mip, obj_mip = build_master("SCIP", binary=True, with_jensen=False)
        mip_m.SuppressOutput()
        lb_con = mip_m.Constraint(-mip_m.infinity(), mip_m.infinity())

        def add_cuts_both(c0_v, coeff_v):
            for m, xm, thm in ((lp_m, x_lp, th_lp), (mip_m, x_mip, th_mip)):
                for g in range(G):
                    c = m.Constraint(float(c0_v[g]), m.infinity())
                    c.SetCoefficient(thm[g], 1.0)
                    for i in range(I):
                        if coeff_v[g, i] > 1e-12:
                            c.SetCoefficient(xm[i], float(coeff_v[g, i]))

        add_cuts_both(c0, coeff)

        # Phase 1: In-Out Stabilized LP-Relaxation Benders
        lp_deadline = min(search_deadline, t0 + max(2.0, 0.22 * time_limit_s))
        x_stab = np.ones(I, dtype=np.float64)
        tot_cap_all = float(s_cap.sum())
        lp_lb = 0.0
        for it in range(1, 15):
            if time.perf_counter() + t_eval >= lp_deadline:
                break
            if lp_m.Solve() != pywraplp.Solver.OPTIMAL:
                break
            lp_lb = max(lp_lb, obj_lp.Value())
            x_hat = np.array([x_lp[i].solution_value() for i in range(I)], dtype=np.float64)
            alpha_io = 0.5 if it <= 5 else 0.9 if it <= 8 else 1.0
            x_sep = np.clip(alpha_io * x_hat + (1.0 - alpha_io) * x_stab, 0.0, 1.0)
            if float(np.dot(s_cap, x_sep)) < max_dem + 1e-5:
                if tot_cap_all > max_dem + 1e-4:
                    x_sep = np.clip(0.9999 * x_hat + 0.0001 * np.ones(I, dtype=np.float64), 0.0, 1.0)
                else:
                    x_sep = x_hat.copy()
            te0 = time.perf_counter()
            tt_s, c0_s, cf_s, _ = eval_and_cuts(x_sep, extract_flows=False)
            dt_s = time.perf_counter() - te0
            if dt_s > t_eval:
                t_eval = dt_s
                search_deadline = calc_search_deadline(t_eval)
                lp_deadline = min(lp_deadline, search_deadline)
            if tt_s is None:
                break
            add_cuts_both(c0_s, cf_s)
            sep_ub = float(np.dot(f_cost, x_sep) + tt_s)
            x_stab = 0.5 * x_stab + 0.5 * x_hat
            lp_gap = (sep_ub - lp_lb) / max(abs(sep_ub), 1.0) * 100.0
            if lp_gap < 0.06 and it >= 6:
                break
        best_lb = max(best_lb, lp_lb)

        # Phase 2: Exact Compact SCIP Master MIP + Local-Branching Probes
        stall = 0
        lb_tried = set()
        global_cap = 8.0
        for _ in range(250):
            rem = search_deadline - time.perf_counter()
            if rem <= max(0.6, t_eval + 0.3):
                break
            use_local = False
            radius = 0
            if stall >= 2 and len(evaluated) >= 2:
                for r_cand in (2, 4, 6):
                    tag = (tuple(int(round(v)) for v in best_x), r_cand)
                    if tag not in lb_tried:
                        use_local = True
                        radius = r_cand
                        lb_tried.add(tag)
                        break

            if use_local:
                n_open = int(round(best_x.sum()))
                for i in range(I):
                    lb_con.SetCoefficient(x_mip[i], -1.0 if best_x[i] > 0.5 else 1.0)
                lb_con.SetUb(float(radius - n_open))
            else:
                for i in range(I):
                    lb_con.SetCoefficient(x_mip[i], 0.0)
                lb_con.SetUb(mip_m.infinity())

            mip_cap = max(0.3, min(rem - t_eval - 0.15, 6.0 if use_local else global_cap))
            mip_m.SetTimeLimit(int(mip_cap * 1000))
            trace["master_solves"] += 1
            st = mip_m.Solve()
            if st not in (pywraplp.Solver.OPTIMAL, pywraplp.Solver.FEASIBLE):
                if use_local:
                    continue
                break
            if (not use_local) and st == pywraplp.Solver.OPTIMAL:
                best_lb = max(best_lb, obj_mip.Value())

            x_cur = np.array([float(round(x_mip[i].solution_value())) for i in range(I)], dtype=np.float64)
            # Guard numerical capacity edge case
            if float(np.dot(s_cap, x_cur)) < max_dem - 1e-7:
                continue
            key = tuple(int(v) for v in x_cur)
            if key in evaluated:
                if use_local:
                    continue
                if st == pywraplp.Solver.OPTIMAL:
                    best_lb = max(best_lb, obj_mip.Value())
                    break
                # Unrestricted MIP hit time cap without escaping evaluated set: try local branching or longer cap
                stall += 1
                bx_key = tuple(int(round(v)) for v in best_x)
                if any((bx_key, rc) not in lb_tried for rc in (2, 4, 6)):
                    continue
                if global_cap < 18.0:
                    global_cap = 18.0
                    continue
                break

            if time.perf_counter() + t_eval >= search_deadline:
                break
            te0 = time.perf_counter()
            tt_c, c0_c, cf_c, _ = eval_and_cuts(x_cur, extract_flows=False)
            dt_c = time.perf_counter() - te0
            if dt_c > t_eval:
                t_eval = dt_c
                search_deadline = calc_search_deadline(t_eval)
            if tt_c is None:
                break
            ub_cur = float(np.dot(f_cost, x_cur) + tt_c)
            evaluated[key] = ub_cur
            add_cuts_both(c0_c, cf_c)
            if ub_cur < best_ub - 1e-7:
                best_ub = ub_cur
                best_x = x_cur.copy()
                stall = 0
                global_cap = 8.0
            else:
                stall += 1
            if (best_ub - best_lb) / max(abs(best_ub), 1.0) < 1e-7:
                break

    # Final exact sparse flow extraction for best_x (guaranteed exact & zero-violation!)
    _, _, _, flows = eval_and_cuts(best_x, extract_flows=True)
    if flows is None:
        flows = fallback_greedy_flows(best_x, s_cap, lam, q)
    exact_obj = recompute_objective_from_sparse(best_x, flows, f_cost, probs, q)

    return {
        "objective_value": exact_obj,
        "open_facilities": [i for i in range(I) if best_x[i] > 0.5],
        "x": {str(i): int(round(best_x[i])) for i in range(I)},
        "y": flows,
    }


def main():
    t_entry = time.perf_counter()
    parser = argparse.ArgumentParser(description="FrontierOR Main-track solver for bodur2017 (SCFLP).")
    parser.add_argument("--problem", choices=("bodur2017",), required=True)
    parser.add_argument("--instance", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--time-limit", type=int, default=60)
    parser.add_argument("--initializer", choices=("all-open", "expected-demand"), default="all-open")
    parser.add_argument("--trace", type=Path)
    args = parser.parse_args()
    if args.time_limit <= 0:
        parser.error("--time-limit must be positive")
    instance = json.loads(args.instance.read_text(encoding="utf-8"))
    trace = {}
    solution = solve(instance, float(args.time_limit), t_entry=t_entry,
                     initializer=args.initializer, trace=trace)
    args.output.write_text(json.dumps(solution, allow_nan=False, separators=(",", ":")) + "\n", encoding="utf-8")
    if args.trace:
        trace["wall_seconds_since_cli_entry"] = time.perf_counter() - t_entry
        args.trace.write_text(json.dumps(trace, allow_nan=False, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
