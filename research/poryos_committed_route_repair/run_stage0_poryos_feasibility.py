"""
Stage-0 Decisive Feasibility Screen — Poryos2026 Committed-Route Suffix Repair (Erratum v1.1).

Pre-Locked Protocol + Pre-Scoring Erratum v1.1: `STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md`
Pinned Benchmark: ANR-MAMUT/MAMUT-routing-Poryos2026 @ 0400ed2c3a27ed36f725034a38873b69d3af1dea (ODbL-1.0)
Official Checker: mamut-routing-lib==0.12.0 (`td-fold/2`, `ObjectiveFunction.DURATION`, exact FIFO NDCPWLF)

Uniform leg-departure boundary convention across ALL legs (depot, customer-to-customer, homebound):
  - Leg departing at `dep <= T_shock`: ALREADY DISPATCHED under OLD overlay (`atfs_old`), never altered retroactively.
  - Leg departing at `dep > T_shock`: NOT YET DISPATCHED, evaluated prospectively under NEW overlay (`atfs_new`).
  - Four exhaustive route regimes:
      1. UNDEPARTED (`t_0 > T_shock`): editable_route=True, prefix=[], dep >= T_shock under NEW.
      2. ACTIVE_SUFFIX (`t_0 <= T_shock`, first p with `dep_p(old) > T_shock`): editable_route=True,
         prefix=r[:p] replayed under OLD through c_p; suffix legs from c_p onward under NEW.
      3. HOMEBOUND_LOCKED (`t_0 <= T_shock`, `dep_m(old) <= T_shock < ret_old`): editable_route=False,
         homebound leg already dispatched under OLD; retained unchanged at `ret_old - t_0`.
      4. RETIRED_OLD (`ret_old <= T_shock`): editable_route=False, whole OLD schedule retained unchanged.

Physical fleet fixed (`K <= K_inc`, editing ONLY `editable_route=True` routes) is REQUIRED for
`GENUINE_EDIT_REQUIRED_REPARABLE`. Extra-vehicle rescue is logged strictly separately as a diagnostic.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
import math
import os
import pathlib
import random
import time
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from mamut_routing_lib.artifacts import load_bks
from mamut_routing_lib.checker import SolutionCheckStatus
from mamut_routing_lib.models import BenchmarkSolution, ObjectiveFunction
from mamut_routing_lib.td import (
    InstanceATFs,
    LoadedTDInstance,
    NDCPWLF,
    apply_ready_time,
    check_td_solution,
    compute_route_duration,
    load_td_instance,
    restrict_domain,
)


ROOT = pathlib.Path(__file__).resolve().parent
PORYOS_ROOT = ROOT / "raw_poryos2026"
OUT_DIR = ROOT / "stage0_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

P_SHA = "0400ed2c3a27ed36f725034a38873b69d3af1dea"
RAW_BASE = f"https://raw.githubusercontent.com/ANR-MAMUT/MAMUT-routing-Poryos2026/{P_SHA}"

CITIES = ["hong_kong", "lyon", "paris", "san_francisco", "tokyo"]
METHODS = ["hyb", "poi"]
SIZES = [10, 25, 50]
TRANSITIONS = [("bpr-light", "bpr-heavy"), ("wave-light", "wave-heavy")]


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def fetch_poryos(rel_path: str) -> pathlib.Path:
    dst = PORYOS_ROOT / rel_path
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        url = f"{RAW_BASE}/{rel_path}"
        last_err = None
        for attempt in range(4):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
                with urllib.request.urlopen(req, timeout=60) as r:
                    dst.write_bytes(r.read())
                return dst
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        raise RuntimeError(f"Failed to download {url}: {last_err}")
    return dst


def route_duration_cached(
    inst,
    atfs: InstanceATFs,
    route: Tuple[int, ...],
    cache: Dict[Tuple[int, ...], Tuple[bool, float, float]],
) -> Tuple[bool, float, float]:
    if not route:
        return True, 0.0, 0.0
    if route in cache:
        return cache[route]
    ev = compute_route_duration(inst, atfs, list(route))
    res = (
        bool(ev.feasible),
        float(ev.duration) if ev.feasible else math.inf,
        float(ev.departure_time) if ev.feasible else 0.0,
    )
    cache[route] = res
    return res


def solve_light_incumbent_td_ils(
    loaded: LoadedTDInstance,
    time_budget_s: float,
    seed: int = 20261124,
) -> Tuple[List[List[int]], float, List[float]]:
    """
    Independent deterministic light-traffic incumbent solver (TD-ILS over official exact NDCPWLF).
    NEVER uses the benchmark anchor route or BKS.
    """
    inst = loaded.instance
    atfs = loaded.atfs
    n = inst.num_customers
    Q = inst.vehicle_capacity
    dem = inst.demands
    tw = inst.time_windows
    rng = random.Random(seed)
    cache: Dict[Tuple[int, ...], Tuple[bool, float, float]] = {}

    def r_eval(r: List[int]) -> Tuple[bool, float, float]:
        return route_duration_cached(inst, atfs, tuple(r), cache)

    def r_load(r: List[int]) -> int:
        return sum(dem[c] for c in r)

    def construct(order: List[int]) -> List[List[int]]:
        routes: List[List[int]] = []
        loads: List[int] = []
        durs: List[float] = []
        for c in order:
            best_delta = math.inf
            best_pos = None
            for ri, r in enumerate(routes):
                if loads[ri] + dem[c] > Q:
                    continue
                for pos in range(len(r) + 1):
                    cand = r[:pos] + [c] + r[pos:]
                    ok, dur, _ = r_eval(cand)
                    if ok:
                        delta = dur - durs[ri]
                        if delta < best_delta:
                            best_delta = delta
                            best_pos = (ri, pos, dur)
            ok_new, dur_new, _ = r_eval([c])
            if best_pos is None or (ok_new and dur_new < best_delta):
                routes.append([c])
                loads.append(dem[c])
                durs.append(dur_new)
            else:
                ri, pos, dur = best_pos
                routes[ri].insert(pos, c)
                loads[ri] += dem[c]
                durs[ri] = dur
        return routes

    def local_search(routes: List[List[int]], deadline: float) -> Tuple[List[List[int]], float]:
        routes = [list(r) for r in routes if r]
        loads = [r_load(r) for r in routes]
        durs = [r_eval(r)[1] for r in routes]
        improved = True
        while improved and time.perf_counter() < deadline:
            improved = False
            # 1. Intra-route 2-opt
            for ri in range(len(routes)):
                r = routes[ri]
                m = len(r)
                if m >= 2:
                    for i in range(m):
                        for j in range(i + 1, m):
                            cand = r[:i] + r[i : j + 1][::-1] + r[j + 1 :]
                            ok, dur, _ = r_eval(cand)
                            if ok and dur < durs[ri] - 1e-6:
                                routes[ri] = cand
                                durs[ri] = dur
                                r = cand
                                improved = True
                                break
                        if improved:
                            break
            if improved:
                continue

            # 2. Relocate single customer (intra & inter route)
            for ri in range(len(routes)):
                r1 = routes[ri]
                for i in range(len(r1)):
                    c = r1[i]
                    r1_rem = r1[:i] + r1[i + 1 :]
                    ok1, d1_new, _ = r_eval(r1_rem)
                    if not ok1:
                        continue
                    gain1 = durs[ri] - d1_new
                    best_move = None
                    best_save = 1e-6
                    for rj in range(len(routes)):
                        if rj != ri and loads[rj] + dem[c] > Q:
                            continue
                        r2 = r1_rem if rj == ri else routes[rj]
                        base_d2 = d1_new if rj == ri else durs[rj]
                        for pos in range(len(r2) + 1):
                            if rj == ri and pos == i:
                                continue
                            cand2 = r2[:pos] + [c] + r2[pos:]
                            ok2, d2_new, _ = r_eval(cand2)
                            if ok2:
                                save = (durs[ri] - d2_new) if rj == ri else (gain1 - (d2_new - base_d2))
                                if save > best_save:
                                    best_save = save
                                    best_move = (rj, cand2, d2_new)
                    if best_move is not None:
                        rj, cand2, d2_new = best_move
                        if rj == ri:
                            routes[ri] = cand2
                            durs[ri] = d2_new
                        else:
                            routes[ri] = r1_rem
                            loads[ri] -= dem[c]
                            durs[ri] = d1_new
                            routes[rj] = cand2
                            loads[rj] += dem[c]
                            durs[rj] = d2_new
                            if not routes[ri]:
                                routes.pop(ri)
                                loads.pop(ri)
                                durs.pop(ri)
                        improved = True
                        break
                if improved or time.perf_counter() >= deadline:
                    break
            if improved:
                continue

            # 3. Inter-route swap
            for ri in range(len(routes)):
                for rj in range(ri + 1, len(routes)):
                    r1, r2 = routes[ri], routes[rj]
                    for i, c1 in enumerate(r1):
                        for j, c2 in enumerate(r2):
                            if loads[ri] - dem[c1] + dem[c2] > Q or loads[rj] - dem[c2] + dem[c1] > Q:
                                continue
                            cand1 = r1[:i] + [c2] + r1[i + 1 :]
                            cand2 = r2[:j] + [c1] + r2[j + 1 :]
                            ok1, d1_new, _ = r_eval(cand1)
                            if not ok1:
                                continue
                            ok2, d2_new, _ = r_eval(cand2)
                            if ok2 and (d1_new + d2_new) < (durs[ri] + durs[rj]) - 1e-6:
                                routes[ri], routes[rj] = cand1, cand2
                                loads[ri] += dem[c2] - dem[c1]
                                loads[rj] += dem[c1] - dem[c2]
                                durs[ri], durs[rj] = d1_new, d2_new
                                improved = True
                                break
                        if improved:
                            break
                    if improved or time.perf_counter() >= deadline:
                        break
                if improved or time.perf_counter() >= deadline:
                    break

        return routes, sum(durs)

    t0 = time.perf_counter()
    deadline = t0 + time_budget_s
    custs = list(range(1, n + 1))

    init_orders = [
        sorted(custs, key=lambda c: (tw[c][1], tw[c][0], c)),
        sorted(custs, key=lambda c: (tw[c][0], tw[c][1], c)),
        sorted(custs, key=lambda c: (0.5 * (tw[c][0] + tw[c][1]), c)),
    ]
    best_routes: Optional[List[List[int]]] = None
    best_cost = math.inf

    iter_idx = 0
    while time.perf_counter() < deadline or iter_idx < len(init_orders):
        if iter_idx < len(init_orders):
            order = init_orders[iter_idx]
        else:
            if best_routes is not None and iter_idx % 2 == 1:
                k_rem = max(2, min(n, int(round(0.35 * n))))
                rem_set = set(rng.sample(custs, k_rem))
                partial = [[c for c in r if c not in rem_set] for r in best_routes]
                partial = [r for r in partial if r]
                rem_list = list(rem_set)
                rng.shuffle(rem_list)
                loads = [r_load(r) for r in partial]
                durs = [r_eval(r)[1] for r in partial]
                for c in rem_list:
                    best_d = math.inf
                    best_p = None
                    for ri, r in enumerate(partial):
                        if loads[ri] + dem[c] > Q:
                            continue
                        for pos in range(len(r) + 1):
                            cand = r[:pos] + [c] + r[pos:]
                            ok, dur, _ = r_eval(cand)
                            if ok and (dur - durs[ri]) < best_d:
                                best_d = dur - durs[ri]
                                best_p = (ri, pos, dur)
                    ok_new, dur_new, _ = r_eval([c])
                    if best_p is None or (ok_new and dur_new < best_d):
                        partial.append([c])
                        loads.append(dem[c])
                        durs.append(dur_new)
                    else:
                        ri, pos, dur = best_p
                        partial[ri].insert(pos, c)
                        loads[ri] += dem[c]
                        durs[ri] = dur
                cand_routes, cand_cost = local_search(partial, deadline)
                if cand_cost < best_cost - 1e-6:
                    best_cost = cand_cost
                    best_routes = cand_routes
                iter_idx += 1
                continue
            order = list(custs)
            rng.shuffle(order)

        cand_routes = construct(order)
        cand_routes, cand_cost = local_search(cand_routes, deadline)
        if cand_cost < best_cost - 1e-6:
            best_cost = cand_cost
            best_routes = cand_routes
        iter_idx += 1
        if iter_idx >= 25 and time.perf_counter() >= deadline:
            break

    assert best_routes is not None
    sol = BenchmarkSolution(instance_name=inst.instance_name, routes=best_routes)
    chk = check_td_solution(loaded, sol, objective_function=ObjectiveFunction.DURATION)
    if chk.status != SolutionCheckStatus.VALID:
        raise RuntimeError(f"Incumbent failed official checker: {chk}")
    deps = [ev.departure_time for ev in chk.route_evaluations]
    return best_routes, float(chk.routing_cost), deps


@dataclass
class PrefixState:
    route_idx: int
    route_regime: str         # UNDEPARTED | ACTIVE_SUFFIX | HOMEBOUND_LOCKED | RETIRED_OLD
    editable_route: bool      # False for HOMEBOUND_LOCKED and RETIRED_OLD
    prefix: List[int]
    orig_suffix: List[int]
    departed: bool
    frozen_t0: float          # fixed source depot dep if departed, else T_shock lower bound
    last_node: int            # prefix[-1] if ACTIVE_SUFFIX, 0 if UNDEPARTED / HOMEBOUND_LOCKED / RETIRED_OLD
    carried_dep_time: float   # finite carried departure time (> T_shock for ACTIVE_SUFFIX, T_shock for UNDEPARTED)
    carried_load: int         # finite carried load through prefix
    locked_old_duration: float  # exact (ret_old - t0) for HOMEBOUND_LOCKED / RETIRED_OLD; 0.0 otherwise
    locked_old_ret_time: float  # exact ret_old for HOMEBOUND_LOCKED / RETIRED_OLD; 0.0 otherwise


def replay_prefix_under_old_overlay(
    loaded_old: LoadedTDInstance,
    routes: List[List[int]],
    deps: List[float],
    t_shock: float,
) -> List[PrefixState]:
    """
    Uniform leg-departure convention (Erratum v1.1):
      - Any leg departing at `dep <= T_shock` is already dispatched under OLD overlay (`atfs_old`).
      - Any leg departing at `dep > T_shock` has not yet departed and runs prospectively under NEW (`atfs_new`).
    Classifies every route into exactly one of: UNDEPARTED, ACTIVE_SUFFIX, HOMEBOUND_LOCKED, RETIRED_OLD.
    """
    inst = loaded_old.instance
    atfs_old = loaded_old.atfs
    depot = inst.depot
    states: List[PrefixState] = []

    for ri, (r, t0) in enumerate(zip(routes, deps)):
        if t0 > t_shock:
            # 1. UNDEPARTED: depot departure strictly after T_shock
            states.append(
                PrefixState(
                    route_idx=ri,
                    route_regime="UNDEPARTED",
                    editable_route=True,
                    prefix=[],
                    orig_suffix=list(r),
                    departed=False,
                    frozen_t0=t_shock,
                    last_node=depot,
                    carried_dep_time=t_shock,
                    carried_load=0,
                    locked_old_duration=0.0,
                    locked_old_ret_time=0.0,
                )
            )
            continue

        # Route departed depot at t0 <= T_shock -> replay OLD overlay stop-by-stop
        t = t0
        prev = depot
        load = 0
        active_p: Optional[int] = None
        active_dep = 0.0
        active_load = 0
        for idx, c in enumerate(r):
            arr = atfs_old.arcs[(prev, c)].evaluate(t)
            e_c, l_c = inst.time_windows[c]
            st = max(arr, float(e_c))
            assert st <= float(l_c) + 1e-6
            dep = st + float(inst.service_times[c])
            load += inst.demands[c]
            prev = c
            t = dep
            if active_p is None and dep > t_shock:
                # Leg (prev_before_c -> c) departed <= T_shock, stop c finishes at dep > T_shock!
                active_p = idx + 1
                active_dep = dep
                active_load = load
                break

        if active_p is not None:
            # 2. ACTIVE_SUFFIX: stop c_{active_p} is last committed stop, leaving c_{active_p} at dep > T_shock
            assert math.isfinite(active_dep) and active_dep > t_shock
            states.append(
                PrefixState(
                    route_idx=ri,
                    route_regime="ACTIVE_SUFFIX",
                    editable_route=True,
                    prefix=list(r[:active_p]),
                    orig_suffix=list(r[active_p:]),
                    departed=True,
                    frozen_t0=t0,
                    last_node=r[active_p - 1],
                    carried_dep_time=active_dep,
                    carried_load=active_load,
                    locked_old_duration=0.0,
                    locked_old_ret_time=0.0,
                )
            )
            continue

        # Otherwise ALL customer departures satisfied dep_k(old) <= T_shock (including dep_m(old) <= T_shock)!
        # Therefore the homebound leg (c_m -> depot) ALSO departed at <= T_shock under OLD overlay!
        ret_old = atfs_old.arcs[(prev, depot)].evaluate(t)
        old_dur = float(ret_old - t0)
        assert math.isfinite(ret_old) and math.isfinite(old_dur)
        regime = "RETIRED_OLD" if ret_old <= t_shock else "HOMEBOUND_LOCKED"
        states.append(
            PrefixState(
                route_idx=ri,
                route_regime=regime,
                editable_route=False,
                prefix=list(r),
                orig_suffix=[],
                departed=True,
                frozen_t0=t0,
                last_node=depot,
                carried_dep_time=float(ret_old),
                carried_load=load,
                locked_old_duration=old_dur,
                locked_old_ret_time=float(ret_old),
            )
        )
    return states


def eval_prospective_suffix(
    loaded_new: LoadedTDInstance,
    ps: PrefixState,
    suffix: List[int],
) -> Tuple[bool, float, float, List[int]]:
    """
    Evaluates a suffix prospectively under NEW overlay from PrefixState using exact FIFO NDCPWLF.
    HOMEBOUND_LOCKED and RETIRED_OLD routes are immutable and retain their exact OLD schedule.
    Returns (feasible, total_tardiness_s, route_duration_s, violated_customers).
    """
    if not ps.editable_route:
        if suffix:
            return False, 1e12 + float(len(suffix)) * 1e6, math.inf, list(suffix)
        return True, 0.0, ps.locked_old_duration, []

    inst = loaded_new.instance
    atfs_new = loaded_new.atfs
    Q = inst.vehicle_capacity
    depot = inst.depot
    depot_due = float(inst.time_windows[depot][1])

    load = ps.carried_load + sum(inst.demands[c] for c in suffix)
    if load > Q:
        return False, 1e12 + float(load - Q) * 1e6, math.inf, list(suffix)

    if ps.route_regime == "UNDEPARTED":
        if not suffix:
            return True, 0.0, 0.0, []
        h_lo, h_hi = atfs_new.horizon
        dep_lo = max(h_lo, float(inst.time_windows[depot][0]), ps.frozen_t0)
        dep_hi = min(h_hi, depot_due)
        if dep_lo <= dep_hi:
            acc: Optional[NDCPWLF] = None
            prev = depot
            feasible_exact = True
            for v in suffix:
                arc = atfs_new.arcs[(prev, v)]
                acc = restrict_domain(arc, dep_lo, dep_hi) if acc is None else arc.compose(acc, slope_one_exact=True)
                if acc.is_empty():
                    feasible_exact = False
                    break
                e_v, l_v = inst.time_windows[v]
                acc = apply_ready_time(acc, earliest=float(e_v), latest=float(l_v), service_time=float(inst.service_times[v]))
                if acc.is_empty():
                    feasible_exact = False
                    break
                prev = v
            if feasible_exact and acc is not None:
                acc = atfs_new.arcs[(prev, depot)].compose(acc, slope_one_exact=True)
                if not acc.is_empty():
                    acc = apply_ready_time(acc, earliest=None, latest=depot_due, service_time=0.0)
                    if not acc.is_empty():
                        dur, _ = acc.min_shifted_image()
                        return True, 0.0, float(dur), []

        # Earliest-departure forward tardiness from dep_lo for repair guidance
        t = dep_lo
        prev = depot
        tard = 0.0
        viols: List[int] = []
        for c in suffix:
            arc = atfs_new.arcs[(prev, c)]
            if t > arc.max_domain:
                tard += (t - arc.max_domain) + 1e5
                arr = arc.evaluate(arc.max_domain) + (t - arc.max_domain)
            else:
                arr = arc.evaluate(max(t, arc.min_domain))
            e_c, l_c = inst.time_windows[c]
            st = max(arr, float(e_c))
            if st > float(l_c):
                tard += st - float(l_c)
                viols.append(c)
            t = st + float(inst.service_times[c])
            prev = c
        arc0 = atfs_new.arcs[(prev, depot)]
        ret = arc0.evaluate(min(max(t, arc0.min_domain), arc0.max_domain)) + max(0.0, t - arc0.max_domain)
        if ret > depot_due:
            tard += ret - depot_due
        return False, max(tard, 1e-3), float(ret - dep_lo), viols

    # ACTIVE_SUFFIX (departed route with frozen_t0 <= T_shock and carried_dep_time > T_shock)
    assert ps.route_regime == "ACTIVE_SUFFIX"
    t = ps.carried_dep_time
    prev = ps.last_node
    tard = 0.0
    viols = []
    for c in suffix:
        arc = atfs_new.arcs[(prev, c)]
        if t > arc.max_domain:
            tard += (t - arc.max_domain) + 1e5
            arr = arc.evaluate(arc.max_domain) + (t - arc.max_domain)
        else:
            arr = arc.evaluate(max(t, arc.min_domain))
        e_c, l_c = inst.time_windows[c]
        st = max(arr, float(e_c))
        if st > float(l_c):
            tard += st - float(l_c)
            viols.append(c)
        t = st + float(inst.service_times[c])
        prev = c
    arc0 = atfs_new.arcs[(prev, depot)]
    if t > arc0.max_domain:
        tard += (t - arc0.max_domain) + 1e5
        ret = arc0.evaluate(arc0.max_domain) + (t - arc0.max_domain)
    else:
        ret = arc0.evaluate(max(t, arc0.min_domain))
    if ret > depot_due:
        tard += ret - depot_due
        viols.append(depot)
    return (tard == 0.0), float(tard), float(ret - ps.frozen_t0), viols


def count_dispatch_edits(
    prefix_states: List[PrefixState],
    repaired_suffixes: List[List[int]],
) -> Tuple[int, int]:
    """Returns (changed_next_stop_arcs, changed_vehicle_assignments) across editable routes."""
    orig_next: Dict[Tuple[int, int], int] = {}
    orig_veh: Dict[int, int] = {}
    for ps in prefix_states:
        if not ps.editable_route:
            continue
        prev = ps.last_node
        for c in ps.orig_suffix:
            orig_next[(ps.route_idx, prev)] = c
            orig_veh[c] = ps.route_idx
            prev = c
        orig_next[(ps.route_idx, prev)] = 0

    new_next: Dict[Tuple[int, int], int] = {}
    new_veh: Dict[int, int] = {}
    for ri, suf in enumerate(repaired_suffixes):
        if ri < len(prefix_states) and not prefix_states[ri].editable_route:
            assert not suf, "Attempted edit on locked HOMEBOUND/RETIRED route!"
            continue
        prev = prefix_states[ri].last_node if ri < len(prefix_states) else 0
        for c in suf:
            new_next[(ri, prev)] = c
            new_veh[c] = ri
            prev = c
        if ri < len(prefix_states) or suf:
            new_next[(ri, prev)] = 0

    all_keys = set(orig_next.keys()) | set(new_next.keys())
    changed_arcs = sum(1 for k in all_keys if orig_next.get(k) != new_next.get(k))
    changed_veh = sum(1 for c in orig_veh if new_veh.get(c) != orig_veh[c])
    return changed_arcs, changed_veh


def repair_suffix_deterministic(
    loaded_new: LoadedTDInstance,
    prefix_states: List[PrefixState],
    t_shock: float,
    allow_extra_vehicle: bool = False,
    budget_s: float = 5.0,
) -> Tuple[bool, List[List[int]], float, int, int]:
    """
    Deterministic slack/tardiness-guided suffix repair keeping all committed prefixes and
    HOMEBOUND_LOCKED/RETIRED_OLD routes strictly frozen.
    """
    states = list(prefix_states)
    suffixes = [list(ps.orig_suffix) for ps in states]
    if allow_extra_vehicle:
        for _ in range(2):
            states.append(
                PrefixState(
                    route_idx=len(states),
                    route_regime="UNDEPARTED",
                    editable_route=True,
                    prefix=[],
                    orig_suffix=[],
                    departed=False,
                    frozen_t0=t_shock,
                    last_node=0,
                    carried_dep_time=t_shock,
                    carried_load=0,
                    locked_old_duration=0.0,
                    locked_old_ret_time=0.0,
                )
            )
            suffixes.append([])

    editable_route_ids = [i for i, st in enumerate(states) if st.editable_route]

    def eval_all(sufs: List[List[int]]) -> Tuple[bool, float, float, List[Tuple[bool, float, float, List[int]]]]:
        evs = [eval_prospective_suffix(loaded_new, states[i], sufs[i]) for i in range(len(states))]
        ok = all(e[0] for e in evs)
        tard = sum(e[1] for e in evs)
        dur = sum(e[2] for e in evs)
        return ok, tard, dur, evs

    ok, best_tard, best_dur, evs = eval_all(suffixes)
    best_arcs, best_veh = count_dispatch_edits(prefix_states, suffixes)
    best_sufs = [list(s) for s in suffixes]

    deadline = time.perf_counter() + budget_s
    improved = True
    while improved and time.perf_counter() < deadline:
        improved = False
        viol_routes = [i for i in editable_route_ids if not evs[i][0]]
        route_order = viol_routes + [i for i in editable_route_ids if i not in viol_routes]

        # 1. Relocate single editable customer across editable routes ONLY
        for ri in route_order:
            s1 = suffixes[ri]
            for i in range(len(s1)):
                c = s1[i]
                s1_rem = s1[:i] + s1[i + 1 :]
                e1 = eval_prospective_suffix(loaded_new, states[ri], s1_rem)
                for rj in editable_route_ids:
                    s2 = s1_rem if rj == ri else suffixes[rj]
                    for pos in range(len(s2) + 1):
                        if rj == ri and pos == i:
                            continue
                        cand2 = s2[:pos] + [c] + s2[pos:]
                        e2 = eval_prospective_suffix(loaded_new, states[rj], cand2)
                        if rj == ri:
                            new_tard = best_tard - evs[ri][1] + e2[1]
                            new_dur = best_dur - evs[ri][2] + e2[2]
                        else:
                            new_tard = best_tard - evs[ri][1] - evs[rj][1] + e1[1] + e2[1]
                            new_dur = best_dur - evs[ri][2] - evs[rj][2] + e1[2] + e2[2]
                        if new_tard > best_tard + 1e-6:
                            continue
                        cand_sufs = [list(s) for s in suffixes]
                        if rj == ri:
                            cand_sufs[ri] = cand2
                        else:
                            cand_sufs[ri] = s1_rem
                            cand_sufs[rj] = cand2
                        arcs, veh = count_dispatch_edits(prefix_states, cand_sufs)
                        better = (
                            (new_tard < best_tard - 1e-6)
                            or (new_tard == 0.0 and best_tard > 0.0)
                            or (new_tard == 0.0 and best_tard == 0.0 and (arcs, new_dur) < (best_arcs, best_dur - 1e-6))
                        )
                        if better:
                            suffixes = cand_sufs
                            ok, best_tard, best_dur, evs = eval_all(suffixes)
                            best_arcs, best_veh = arcs, veh
                            best_sufs = [list(s) for s in suffixes]
                            improved = True
                            break
                    if improved or time.perf_counter() >= deadline:
                        break
                if improved or time.perf_counter() >= deadline:
                    break
            if improved or time.perf_counter() >= deadline:
                break
        if improved:
            continue

        # 2. Swap two editable customers across editable routes ONLY
        for ri in route_order:
            for rj in editable_route_ids:
                if rj < ri and rj in viol_routes:
                    continue
                s1, s2 = suffixes[ri], suffixes[rj]
                for i, c1 in enumerate(s1):
                    j_start = i + 1 if rj == ri else 0
                    for j in range(j_start, len(s2)):
                        c2 = s2[j]
                        cand_sufs = [list(s) for s in suffixes]
                        if rj == ri:
                            cand_sufs[ri][i], cand_sufs[ri][j] = c2, c1
                            e1 = eval_prospective_suffix(loaded_new, states[ri], cand_sufs[ri])
                            new_tard = best_tard - evs[ri][1] + e1[1]
                            new_dur = best_dur - evs[ri][2] + e1[2]
                        else:
                            cand_sufs[ri][i] = c2
                            cand_sufs[rj][j] = c1
                            e1 = eval_prospective_suffix(loaded_new, states[ri], cand_sufs[ri])
                            e2 = eval_prospective_suffix(loaded_new, states[rj], cand_sufs[rj])
                            new_tard = best_tard - evs[ri][1] - evs[rj][1] + e1[1] + e2[1]
                            new_dur = best_dur - evs[ri][2] - evs[rj][2] + e1[2] + e2[2]
                        if new_tard > best_tard + 1e-6:
                            continue
                        arcs, veh = count_dispatch_edits(prefix_states, cand_sufs)
                        better = (
                            (new_tard < best_tard - 1e-6)
                            or (new_tard == 0.0 and best_tard > 0.0)
                            or (new_tard == 0.0 and best_tard == 0.0 and (arcs, new_dur) < (best_arcs, best_dur - 1e-6))
                        )
                        if better:
                            suffixes = cand_sufs
                            ok, best_tard, best_dur, evs = eval_all(suffixes)
                            best_arcs, best_veh = arcs, veh
                            best_sufs = [list(s) for s in suffixes]
                            improved = True
                            break
                    if improved or time.perf_counter() >= deadline:
                        break
                if improved or time.perf_counter() >= deadline:
                    break
            if improved or time.perf_counter() >= deadline:
                break

    return (best_tard == 0.0), best_sufs, best_dur, best_arcs, best_veh


def prove_suffix_infeasible_exact(
    loaded_new: LoadedTDInstance,
    prefix_states: List[PrefixState],
    max_nodes: int = 50000,
) -> str:
    """Bounded exact fixed-fleet feasibility prover over editable_route=True routes ONLY."""
    inst = loaded_new.instance
    atfs_new = loaded_new.atfs
    Q = inst.vehicle_capacity
    ed_states = [ps for ps in prefix_states if ps.editable_route]
    editable = [c for ps in ed_states for c in ps.orig_suffix]
    if not editable:
        return "FEASIBLE_EXACT"
    if not ed_states:
        return "PROVEN_INFEASIBLE"

    for c in editable:
        if not any(eval_prospective_suffix(loaded_new, ps, [c])[0] for ps in ed_states):
            return "PROVEN_INFEASIBLE"

    if len(editable) > 10:
        return "UNKNOWN"

    nodes_visited = 0
    K = len(ed_states)
    cur_node = [ps.last_node for ps in ed_states]
    cur_time = [ps.carried_dep_time for ps in ed_states]
    cur_load = [ps.carried_load for ps in ed_states]
    depot_due = float(inst.time_windows[0][1])

    def dfs(rem: Tuple[int, ...]) -> Optional[bool]:
        nonlocal nodes_visited
        nodes_visited += 1
        if nodes_visited > max_nodes:
            return None
        if not rem:
            for ri in range(K):
                arc0 = atfs_new.arcs[(cur_node[ri], 0)]
                if cur_time[ri] > arc0.max_domain or arc0.evaluate(max(cur_time[ri], arc0.min_domain)) > depot_due:
                    return False
            return True
        best_c = None
        best_opts = None
        for c in rem:
            opts = []
            for ri in range(K):
                if cur_load[ri] + inst.demands[c] > Q:
                    continue
                arc = atfs_new.arcs[(cur_node[ri], c)]
                if cur_time[ri] > arc.max_domain:
                    continue
                arr = arc.evaluate(max(cur_time[ri], arc.min_domain))
                e_c, l_c = inst.time_windows[c]
                st = max(arr, float(e_c))
                if st <= float(l_c):
                    dep = st + float(inst.service_times[c])
                    arc0 = atfs_new.arcs[(c, 0)]
                    if dep <= arc0.max_domain and arc0.evaluate(max(dep, arc0.min_domain)) <= depot_due:
                        opts.append((ri, dep))
            if not opts:
                return False
            if best_opts is None or len(opts) < len(best_opts):
                best_opts = opts
                best_c = c
        next_rem = tuple(x for x in rem if x != best_c)
        assert best_c is not None and best_opts is not None
        for ri, dep in best_opts:
            old_n, old_t, old_l = cur_node[ri], cur_time[ri], cur_load[ri]
            cur_node[ri], cur_time[ri], cur_load[ri] = best_c, dep, old_l + inst.demands[best_c]
            res = dfs(next_rem)
            cur_node[ri], cur_time[ri], cur_load[ri] = old_n, old_t, old_l
            if res is True:
                return True
            if res is None:
                return None
        return False

    ans = dfs(tuple(editable))
    if ans is True:
        return "FEASIBLE_EXACT"
    if ans is False:
        return "PROVEN_INFEASIBLE"
    return "UNKNOWN"


def run_boundary_self_test() -> None:
    """Verifies all 4 Erratum v1.1 route regimes + exact dep == T_shock boundary on lyon-n10-hyb."""
    vrp_l = fetch_poryos("TDVRPTW/lyon/n=10/poryos-lyon-n10-hyb/bpr-light/poryos-lyon-n10-hyb-bpr-light.vrp.json")
    vrp_h = fetch_poryos("TDVRPTW/lyon/n=10/poryos-lyon-n10-hyb/bpr-heavy/poryos-lyon-n10-hyb-bpr-heavy.vrp.json")
    bks_l = load_bks(fetch_poryos("TDVRPTW/lyon/n=10/poryos-lyon-n10-hyb/bpr-light/poryos-lyon-n10-hyb-bpr-light.bks.Duration.json"))
    fetch_poryos("sidecars/lyon/n=10/poryos-lyon-n10-hyb/poryos-lyon-n10-hyb.road.json.gz")
    fetch_poryos("sidecars/lyon/n=10/poryos-lyon-n10-hyb/poryos-lyon-n10-hyb.traffic-bpr-light.json.gz")
    fetch_poryos("sidecars/lyon/n=10/poryos-lyon-n10-hyb/poryos-lyon-n10-hyb.traffic-bpr-heavy.json.gz")
    loaded_l = load_td_instance(vrp_l)
    loaded_h = load_td_instance(vrp_h)
    r1 = bks_l.routes[1]  # single-stop route [5], dep=0.0, starts=[50.1], ret=572.9
    ev1 = compute_route_duration(loaded_l.instance, loaded_l.atfs, r1)
    # Exact dep_m(old) for r1:
    arr_c = loaded_l.atfs.arcs[(0, r1[0])].evaluate(ev1.departure_time)
    st_c = max(arr_c, float(loaded_l.instance.time_windows[r1[0]][0]))
    dep_m = st_c + float(loaded_l.instance.service_times[r1[0]])
    ret_old = ev1.departure_time + ev1.duration

    # Test 1: t_shock < dep_0 (impossible if dep_0=0, use synthetic shifted dep_0=100 -> UNDEPARTED)
    ps_u = replay_prefix_under_old_overlay(loaded_l, [r1], [100.0], t_shock=50.0)[0]
    assert ps_u.route_regime == "UNDEPARTED" and ps_u.editable_route is True and ps_u.prefix == []

    # Test 2: dep_0 <= t_shock < dep_m -> ACTIVE_SUFFIX
    ps_a = replay_prefix_under_old_overlay(loaded_l, [r1], [ev1.departure_time], t_shock=dep_m - 1.0)[0]
    assert ps_a.route_regime == "ACTIVE_SUFFIX" and ps_a.editable_route is True and ps_a.prefix == r1

    # Test 3: EXACT boundary t_shock == dep_m (< ret_old) -> HOMEBOUND_LOCKED (already dispatched return!)
    ps_hb = replay_prefix_under_old_overlay(loaded_l, [r1], [ev1.departure_time], t_shock=dep_m)[0]
    assert ps_hb.route_regime == "HOMEBOUND_LOCKED" and ps_hb.editable_route is False
    ok_hb, tard_hb, dur_hb, _ = eval_prospective_suffix(loaded_h, ps_hb, [])
    assert ok_hb and tard_hb == 0.0 and abs(dur_hb - ev1.duration) < 1e-9
    ok_bad, _, _, _ = eval_prospective_suffix(loaded_h, ps_hb, [1])
    assert not ok_bad, "Locked homebound route must reject appended customers!"

    # Test 4: EXACT boundary t_shock == ret_old -> RETIRED_OLD
    ps_ret = replay_prefix_under_old_overlay(loaded_l, [r1], [ev1.departure_time], t_shock=ret_old)[0]
    assert ps_ret.route_regime == "RETIRED_OLD" and ps_ret.editable_route is False
    ok_r, tard_r, dur_r, _ = eval_prospective_suffix(loaded_h, ps_ret, [])
    assert ok_r and tard_r == 0.0 and abs(dur_r - ev1.duration) < 1e-9
    print("ERRATUM v1.1 BOUNDARY SELF-TEST PASSED (UNDEPARTED, ACTIVE_SUFFIX, HOMEBOUND_LOCKED, RETIRED_OLD, exact dep==T_shock)!")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true", help="Run Erratum v1.1 boundary self-test only.")
    args = ap.parse_args()

    fetch_poryos("mamut-collection.json")
    fetch_poryos("LICENSE")
    run_boundary_self_test()
    if args.self_test:
        return

    t_wall0 = time.perf_counter()
    budgets = {10: 1.5, 25: 4.0, 50: 8.0}
    sidecar_hashes: Dict[str, str] = {}
    cases: List[Dict[str, Any]] = []

    case_idx = 0
    for n in SIZES:
        for city in CITIES:
            for meth in METHODS:
                base = f"poryos-{city}-n{n}-{meth}"
                road_rel = f"sidecars/{city}/n={n}/{base}/{base}.road.json.gz"
                loaded_ov: Dict[str, LoadedTDInstance] = {}
                bks_ov: Dict[str, Any] = {}
                source_err: Optional[str] = None
                try:
                    road_p = fetch_poryos(road_rel)
                    sidecar_hashes[road_rel] = sha256_file(road_p)
                    for ov in ["bpr-light", "bpr-heavy", "wave-light", "wave-heavy"]:
                        tf_rel = f"sidecars/{city}/n={n}/{base}/{base}.traffic-{ov}.json.gz"
                        tf_p = fetch_poryos(tf_rel)
                        sidecar_hashes[tf_rel] = sha256_file(tf_p)
                        vrp_p = fetch_poryos(f"TDVRPTW/{city}/n={n}/{base}/{ov}/{base}-{ov}.vrp.json")
                        bks_p = fetch_poryos(f"TDVRPTW/{city}/n={n}/{base}/{ov}/{base}-{ov}.bks.Duration.json")
                        loaded_ov[ov] = load_td_instance(vrp_p)
                        bks_ov[ov] = load_bks(bks_p)
                except Exception as e:
                    source_err = str(e)

                for src_ov, dst_ov in TRANSITIONS:
                    case_idx += 1
                    cohort = "primary_n10_n25" if n in (10, 25) else "optional_n50"
                    if source_err is not None:
                        rec = {
                            "case_id": f"{base}__{src_ov}_to_{dst_ov}",
                            "cohort": cohort,
                            "n": n,
                            "city": city,
                            "base": base,
                            "src_overlay": src_ov,
                            "dst_overlay": dst_ov,
                            "outcome": "INFRASTRUCTURE_OR_INFEASIBLE_SOURCE",
                            "reason": source_err,
                        }
                        cases.append(rec)
                        continue

                    loaded_src = loaded_ov[src_ov]
                    loaded_dst = loaded_ov[dst_ov]
                    bks_src = bks_ov[src_ov]
                    chk_bks_src = check_td_solution(loaded_src, bks_src, objective_function=ObjectiveFunction.DURATION)
                    if chk_bks_src.status != SolutionCheckStatus.VALID:
                        cases.append({
                            "case_id": f"{base}__{src_ov}_to_{dst_ov}",
                            "cohort": cohort, "n": n, "city": city, "base": base,
                            "src_overlay": src_ov, "dst_overlay": dst_ov,
                            "outcome": "INFRASTRUCTURE_OR_INFEASIBLE_SOURCE",
                            "reason": f"BKS invalid: {chk_bks_src.status}",
                        })
                        continue

                    # 1. Independently solve competitive light-traffic incumbent (NOT anchor, NOT BKS!)
                    try:
                        inc_routes, inc_cost_src, inc_deps_src = solve_light_incumbent_td_ils(
                            loaded_src,
                            time_budget_s=budgets[n],
                            seed=20261124 + case_idx,
                        )
                    except Exception as e:
                        cases.append({
                            "case_id": f"{base}__{src_ov}_to_{dst_ov}",
                            "cohort": cohort, "n": n, "city": city, "base": base,
                            "src_overlay": src_ov, "dst_overlay": dst_ov,
                            "outcome": "INFRASTRUCTURE_OR_INFEASIBLE_SOURCE",
                            "reason": f"Light incumbent failed: {e}",
                        })
                        continue

                    gap_vs_bks_pct = 100.0 * (inc_cost_src - float(chk_bks_src.routing_cost)) / float(chk_bks_src.routing_cost)

                    # 2. Precommitted shock cutoff T_shock = T_start + 0.30 * (T_end - T_start)
                    evs_src = [compute_route_duration(loaded_src.instance, loaded_src.atfs, r) for r in inc_routes]
                    t_start = min(ev.departure_time for ev in evs_src)
                    t_end = max(ev.departure_time + ev.duration for ev in evs_src)
                    t_shock = t_start + 0.30 * (t_end - t_start)

                    # 3. Replay OLD overlay using uniform Erratum v1.1 boundary rules
                    prefix_states = replay_prefix_under_old_overlay(loaded_src, inc_routes, inc_deps_src, t_shock)
                    regime_counts = dict(Counter(ps.route_regime for ps in prefix_states))
                    n_frozen = sum(len(ps.prefix) for ps in prefix_states)
                    n_editable = sum(len(ps.orig_suffix) for ps in prefix_states)

                    # 4. Exact fixed-order prospective FIFO evaluation under NEW overlay
                    fixed_evs = [eval_prospective_suffix(loaded_dst, ps, ps.orig_suffix) for ps in prefix_states]
                    fixed_ok = all(e[0] for e in fixed_evs)
                    fixed_tard = sum(e[1] for e in fixed_evs)
                    fixed_dur = sum(e[2] for e in fixed_evs)
                    fixed_viol_custs = sum(len(e[3]) for e in fixed_evs)

                    # Diagnostic check on shipped BKS routes under same T_shock
                    bks_deps = [ev.departure_time for ev in chk_bks_src.route_evaluations]
                    bks_ps = replay_prefix_under_old_overlay(loaded_src, bks_src.routes, bks_deps, t_shock)
                    bks_fixed_ok = all(eval_prospective_suffix(loaded_dst, ps, ps.orig_suffix)[0] for ps in bks_ps)

                    status = "NO_OP_RESCHEDULE_FEASIBLE"
                    rep_dur = fixed_dur
                    rep_arcs = 0
                    rep_veh = 0
                    exact_cert = None
                    extra_veh_diag: Optional[Dict[str, Any]] = None

                    if not fixed_ok:
                        # Fixed physical fleet (K <= K_inc, editable_route=True ONLY) qualifies for gate!
                        ok_rep, rep_sufs, rep_dur, rep_arcs, rep_veh = repair_suffix_deterministic(
                            loaded_dst, prefix_states, t_shock=t_shock, allow_extra_vehicle=False, budget_s=5.0
                        )
                        if ok_rep:
                            status = "GENUINE_EDIT_REQUIRED_REPARABLE"
                        else:
                            exact_cert = prove_suffix_infeasible_exact(loaded_dst, prefix_states)
                            if exact_cert == "FEASIBLE_EXACT":
                                status = "GENUINE_EDIT_REQUIRED_REPARABLE"
                            elif exact_cert == "PROVEN_INFEASIBLE":
                                status = "PROVEN_INFEASIBLE_PREFIX_LOCKED"
                            else:
                                status = "UNKNOWN_UNREPAIRED"

                            # Separate diagnostic ONLY: does an extra vehicle rescue it? (NEVER qualifies for gate!)
                            ok_ext, _, ext_dur, ext_arcs, ext_veh = repair_suffix_deterministic(
                                loaded_dst, prefix_states, t_shock=t_shock, allow_extra_vehicle=True, budget_s=3.0
                            )
                            extra_veh_diag = {
                                "extra_vehicle_reparable": bool(ok_ext),
                                "extra_vehicle_duration_s": round(ext_dur, 3) if ok_ext and math.isfinite(ext_dur) else None,
                                "extra_vehicle_changed_arcs": ext_arcs if ok_ext else None,
                                "extra_vehicle_changed_veh": ext_veh if ok_ext else None,
                            }

                    rec = {
                        "case_id": f"{base}__{src_ov}_to_{dst_ov}",
                        "cohort": cohort,
                        "n": n,
                        "city": city,
                        "base": base,
                        "src_overlay": src_ov,
                        "dst_overlay": dst_ov,
                        "inc_n_routes": len(inc_routes),
                        "inc_src_duration_s": round(inc_cost_src, 3),
                        "bks_src_duration_s": round(float(chk_bks_src.routing_cost), 3),
                        "inc_gap_vs_bks_pct": round(gap_vs_bks_pct, 3),
                        "t_start_s": round(t_start, 2),
                        "t_end_s": round(t_end, 2),
                        "t_shock_s": round(t_shock, 2),
                        "route_regime_counts": regime_counts,
                        "n_frozen_customers": n_frozen,
                        "n_editable_customers": n_editable,
                        "fixed_order_ok": fixed_ok,
                        "fixed_order_tardiness_s": round(fixed_tard, 3),
                        "fixed_order_violated_stops": fixed_viol_custs,
                        "fixed_order_duration_s": round(fixed_dur, 3) if math.isfinite(fixed_dur) else None,
                        "bks_fixed_order_ok_diag": bks_fixed_ok,
                        "outcome": status,
                        "repaired_duration_s": round(rep_dur, 3) if math.isfinite(rep_dur) else None,
                        "changed_next_stop_arcs": rep_arcs,
                        "changed_vehicle_assignments": rep_veh,
                        "exact_certificate": exact_cert,
                        "extra_vehicle_diag": extra_veh_diag,
                    }
                    cases.append(rec)
                    print(
                        f"[{case_idx:02d}/60] {base:28s} {src_ov:10s}->{dst_ov:10s} | "
                        f"gapBKS={gap_vs_bks_pct:+5.2f}% T_sh={t_shock/3600:.2f}h reg={regime_counts} | "
                        f"tard={fixed_tard:7.1f}s bksOK={str(bks_fixed_ok):5s} -> {status} (arcs={rep_arcs}, veh={rep_veh})",
                        flush=True,
                    )

    def summarize(sub: List[Dict[str, Any]]) -> Dict[str, Any]:
        c = Counter(x["outcome"] for x in sub)
        gen = [x for x in sub if x["outcome"] == "GENUINE_EDIT_REQUIRED_REPARABLE"]
        gen_cities = sorted({x["city"] for x in gen})
        gen_bases = sorted({x["base"] for x in gen})
        bases_per_city: Dict[str, List[str]] = defaultdict(list)
        for b in gen_bases:
            city_b = next(x["city"] for x in gen if x["base"] == b)
            bases_per_city[city_b].append(b)
        valid_sub = [x for x in sub if x["outcome"] != "INFRASTRUCTURE_OR_INFEASIBLE_SOURCE"]
        return {
            "n_cases": len(sub),
            "outcome_counts": dict(c),
            "n_genuine_reparable_pairs": len(gen),
            "n_genuine_unique_bases": len(gen_bases),
            "n_genuine_cities": len(gen_cities),
            "genuine_cities": gen_cities,
            "unique_genuine_bases_per_city": {k: sorted(v) for k, v in sorted(bases_per_city.items())},
            "n_unique_genuine_bases_per_city": {k: len(v) for k, v in sorted(bases_per_city.items())},
            "bks_violated_diag_count": sum(1 for x in valid_sub if not x["bks_fixed_order_ok_diag"]),
            "extra_vehicle_rescue_diag_count": sum(
                1 for x in valid_sub if x.get("extra_vehicle_diag") and x["extra_vehicle_diag"]["extra_vehicle_reparable"]
            ),
            "mean_inc_gap_vs_bks_pct": round(sum(x["inc_gap_vs_bks_pct"] for x in valid_sub) / len(valid_sub), 3) if valid_sub else None,
            "pass_published_gate_ge15_pairs_and_ge3_cities": (len(gen) >= 15 and len(gen_cities) >= 3),
            "pass_strict_unique_bases_ge15_and_ge3_cities": (len(gen_bases) >= 15 and len(gen_cities) >= 3),
        }

    prim = [x for x in cases if x["cohort"] == "primary_n10_n25"]
    opt50 = [x for x in cases if x["cohort"] == "optional_n50"]
    prim_sum = summarize(prim)
    opt50_sum = summarize(opt50)
    comb_sum = summarize(cases)

    decision = (
        "ADVANCE_TO_LEARNED_RANKER_PILOT"
        if (prim_sum["pass_published_gate_ge15_pairs_and_ge3_cities"] or comb_sum["pass_published_gate_ge15_pairs_and_ge3_cities"])
        else "STOP_STAGE0_INSUFFICIENT_GENUINE_REPAIR_CASES"
    )

    per_case_p = OUT_DIR / "stage0_poryos_per_case.jsonl"
    with per_case_p.open("w", encoding="utf-8") as f:
        for row in cases:
            f.write(json.dumps(row) + "\n")

    summary = {
        "protocol": "STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md (with Pre-Scoring Erratum v1.1)",
        "protocol_sha256": sha256_file(ROOT / "STAGE0_PORYOS_FEASIBILITY_PROTOCOL.md"),
        "pre_erratum_protocol_sha256": "28bc316cb87cb3389573481d5e163d6cf5b48265bdd4bc0c0fe55c490a4a61fb",
        "runner_sha256": sha256_file(pathlib.Path(__file__)),
        "poryos2026_commit": P_SHA,
        "mamut_routing_lib_version": "0.12.0",
        "real_pid": os.getpid(),
        "wall_time_s": round(time.perf_counter() - t_wall0, 3),
        "blauth2024_unopened": True,
        "primary_n10_n25_40": prim_sum,
        "optional_n50_20": opt50_sum,
        "combined_n10_n25_n50_60": comb_sum,
        "by_size": {str(sz): summarize([x for x in cases if x["n"] == sz]) for sz in SIZES},
        "by_transition": {f"{a}->{b}": summarize([x for x in cases if x["src_overlay"] == a and x["dst_overlay"] == b]) for a, b in TRANSITIONS},
        "decision": decision,
        "per_case_jsonl": per_case_p.name,
        "per_case_sha256": sha256_file(per_case_p),
        "n_sidecars_verified": len(sidecar_hashes),
        "sidecar_sha256": sidecar_hashes,
    }
    sum_p = OUT_DIR / "stage0_poryos_feasibility_summary.json"
    sum_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== STAGE-0 PORYOS2026 FEASIBILITY SCREEN COMPLETE ===")
    print(f"PID={os.getpid()} | Wall={summary['wall_time_s']}s | Summary SHA={sha256_file(sum_p)}")
    print("PRIMARY (n=10,25 | N=40):", prim_sum)
    print("OPTIONAL (n=50   | N=20):", opt50_sum)
    print("COMBINED (N=60):         ", comb_sum)
    print("DECISION:", decision)


if __name__ == "__main__":
    main()
