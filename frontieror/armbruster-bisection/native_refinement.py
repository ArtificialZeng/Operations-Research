import os
for _v in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
    os.environ.setdefault(_v, "2")

import argparse
import json
import math
import random
import time
from collections import defaultdict

try:
    import kahip
except ImportError:
    kahip = None

try:
    import highspy
except ImportError:
    highspy = None


def evaluate_and_validate(side, node_weights, edges, edge_weights, cap_f, total_w):
    n = len(node_weights)
    if len(side) != n:
        return False, float("inf"), 0, 0, side
    if n > 0 and side[0] != 0:
        side = [1 - s for s in side]
    w0 = 0
    for i, s in enumerate(side):
        if s == 0:
            w0 += node_weights[i]
    w1 = total_w - w0
    if w0 > cap_f or w1 > cap_f:
        return False, float("inf"), w0, w1, side
    cut = 0.0
    for (u, v), ew in zip(edges, edge_weights):
        if side[u] != side[v]:
            cut += ew
    return True, cut, w0, w1, side


def build_graph(n, edges, edge_weights, node_weights):
    adj_map = [dict() for _ in range(n)]
    for (u, v), ew in zip(edges, edge_weights):
        if u == v:
            continue
        adj_map[u][v] = adj_map[u].get(v, 0.0) + ew
        adj_map[v][u] = adj_map[v].get(u, 0.0) + ew
    adj = [list(d.items()) for d in adj_map]

    # Build symmetric CSR for KaHIP with positive integer weights
    vwgt = [max(1, int(w)) for w in node_weights]
    xadj = [0]
    adjncy = []
    adjcwgt = []
    for u in range(n):
        for v, ew in adj[u]:
            adjncy.append(v)
            adjcwgt.append(max(1, int(round(ew))) if ew > 0 else 1)
        xadj.append(len(adjncy))
    return adj, adj_map, (vwgt, xadj, adjcwgt, adjncy)


def compute_gains(side, adj):
    n = len(side)
    gains = [0.0] * n
    for u in range(n):
        su = side[u]
        g = 0.0
        for v, ew in adj[u]:
            if side[v] != su:
                g += ew
            else:
                g -= ew
        gains[u] = g
    return gains


def greedy_lpt_init(node_weights, adj, cap_f, total_w, rng):
    n = len(node_weights)
    order = list(range(n))
    rng.shuffle(order)
    order.sort(key=lambda u: node_weights[u], reverse=True)
    side = [0] * n
    assigned = [False] * n
    w = [0, 0]
    for u in order:
        wu = node_weights[u]
        c0 = c1 = 0.0
        for v, ew in adj[u]:
            if assigned[v]:
                if side[v] == 0:
                    c1 += ew
                else:
                    c0 += ew
        f0 = w[0] + wu <= cap_f
        f1 = w[1] + wu <= cap_f
        if f0 and f1:
            if c0 < c1 or (c0 == c1 and w[0] <= w[1]):
                s = 0
            else:
                s = 1
        elif f0:
            s = 0
        elif f1:
            s = 1
        else:
            s = 0 if w[0] <= w[1] else 1
        side[u] = s
        assigned[u] = True
        w[s] += wu
    if n > 0 and side[0] != 0:
        side = [1 - s for s in side]
    return side


def repair_partition(side, node_weights, adj, cap_f, total_w, rng):
    n = len(node_weights)
    side = list(side)
    w0 = sum(node_weights[i] for i in range(n) if side[i] == 0)
    w1 = total_w - w0
    if w0 <= cap_f and w1 <= cap_f:
        if n > 0 and side[0] != 0:
            side = [1 - s for s in side]
        return side

    gains = compute_gains(side, adj)
    for _ in range(n + 10):
        if w0 <= cap_f and w1 <= cap_f:
            break
        over = 0 if w0 > cap_f else 1
        excess = (w0 - cap_f) if over == 0 else (w1 - cap_f)
        slack = (cap_f - w1) if over == 0 else (cap_f - w0)
        best_u = -1
        best_score = -1e30
        for u in range(n):
            if side[u] != over or node_weights[u] <= 0:
                continue
            wu = node_weights[u]
            if wu <= slack:
                score = gains[u] / max(1.0, float(min(wu, excess)))
            else:
                score = -1e18 - abs(wu - excess)
            if score > best_score:
                best_score = score
                best_u = u
        if best_u < 0:
            break
        wu = node_weights[best_u]
        side[best_u] = 1 - over
        if over == 0:
            w0 -= wu
            w1 += wu
        else:
            w1 -= wu
            w0 += wu
        gains[best_u] = -gains[best_u]
        for v, ew in adj[best_u]:
            if side[v] == side[best_u]:
                gains[v] -= 2.0 * ew
            else:
                gains[v] += 2.0 * ew

    if w0 > cap_f or w1 > cap_f:
        # Try 1-1 swaps to reduce overload
        for _ in range(200):
            if w0 <= cap_f and w1 <= cap_f:
                break
            over = 0 if w0 > cap_f else 1
            c_over = [u for u in range(n) if side[u] == over]
            c_under = [u for u in range(n) if side[u] != over]
            rng.shuffle(c_over)
            rng.shuffle(c_under)
            improved = False
            for u in c_over[:80]:
                wu = node_weights[u]
                for v in c_under[:80]:
                    wv = node_weights[v]
                    if wu > wv:
                        nw0 = w0 - wu + wv if over == 0 else w0 + wu - wv
                        nw1 = total_w - nw0
                        if max(nw0, nw1) < max(w0, w1):
                            side[u], side[v] = side[v], side[u]
                            w0, w1 = nw0, nw1
                            improved = True
                            break
                if improved:
                    break
            if not improved:
                break

    if w0 > cap_f or w1 > cap_f:
        return greedy_lpt_init(node_weights, adj, cap_f, total_w, rng)
    if n > 0 and side[0] != 0:
        side = [1 - s for s in side]
    return side


def local_search_fm_swap(side, node_weights, adj, adj_map, cap_f, total_w, deadline, max_passes=12):
    n = len(node_weights)
    side = list(side)
    w0 = sum(node_weights[i] for i in range(n) if side[i] == 0)
    w1 = total_w - w0
    gains = compute_gains(side, adj)

    def flip_node(u):
        nonlocal w0, w1
        su = side[u]
        wu = node_weights[u]
        side[u] = 1 - su
        if su == 0:
            w0 -= wu
            w1 += wu
        else:
            w1 -= wu
            w0 += wu
        gains[u] = -gains[u]
        nsu = side[u]
        for v, ew in adj[u]:
            if side[v] == nsu:
                gains[v] -= 2.0 * ew
            else:
                gains[v] += 2.0 * ew

    for _ in range(max_passes):
        if time.monotonic() >= deadline:
            break
        improved = False

        # Phase 1: 1-node improving moves
        cands = [u for u in range(n) if gains[u] > 1e-9]
        cands.sort(key=lambda u: gains[u], reverse=True)
        for u in cands:
            if gains[u] <= 1e-9:
                continue
            wu = node_weights[u]
            if side[u] == 0:
                if w1 + wu <= cap_f:
                    flip_node(u)
                    improved = True
            else:
                if w0 + wu <= cap_f:
                    flip_node(u)
                    improved = True

        if time.monotonic() >= deadline:
            break

        # Collect boundary / high-gain nodes on each side
        b0 = []
        b1 = []
        for u in range(n):
            su = side[u]
            has_ext = False
            for v, _ in adj[u]:
                if side[v] != su:
                    has_ext = True
                    break
            if has_ext or gains[u] > -1e-9:
                if su == 0:
                    b0.append(u)
                else:
                    b1.append(u)

        b0.sort(key=lambda u: gains[u], reverse=True)
        b1.sort(key=lambda u: gains[u], reverse=True)
        b0_top = b0[:160]
        b1_top = b1[:160]

        # Phase 2: 1-1 feasible swaps (including exact-weight swaps)
        used = set()
        for u in b0_top:
            if u in used or side[u] != 0:
                continue
            wu = node_weights[u]
            gu = gains[u]
            mu = adj_map[u]
            best_v = -1
            best_g = 1e-9
            min_wv = wu + w0 - cap_f
            max_wv = cap_f - w1 + wu
            for v in b1_top:
                if v in used or side[v] != 1:
                    continue
                wv = node_weights[v]
                if wv < min_wv or wv > max_wv:
                    continue
                g = gu + gains[v]
                if g <= best_g:
                    if best_v == -1 and g <= 1e-9:
                        continue
                wuv = mu.get(v, 0.0)
                if wuv != 0.0:
                    g -= 2.0 * wuv
                if g > best_g:
                    best_g = g
                    best_v = v
            if best_v >= 0:
                flip_node(u)
                flip_node(best_v)
                used.add(u)
                used.add(best_v)
                improved = True

        if time.monotonic() >= deadline:
            break

        # Phase 3: 2-for-1 and 1-for-2 exact/feasible multi-vertex moves
        if not improved and len(b0_top) >= 2 and len(b1_top) >= 2:
            m0 = b0_top[:36]
            m1 = b1_top[:36]
            # 2 from side 0, 1 from side 1
            by_w1 = defaultdict(list)
            for v in b1_top[:100]:
                if side[v] == 1:
                    by_w1[node_weights[v]].append(v)
            found_21 = False
            for i in range(len(m0)):
                a = m0[i]
                if side[a] != 0:
                    continue
                wa = node_weights[a]
                ga = gains[a]
                ma = adj_map[a]
                for j in range(i + 1, len(m0)):
                    b = m0[j]
                    if side[b] != 0:
                        continue
                    wb = node_weights[b]
                    wab = ma.get(b, 0.0)
                    gab = ga + gains[b] + 2.0 * wab
                    dw = wa + wb
                    lo = dw + w0 - cap_f
                    hi = cap_f - w1 + dw
                    # Check exact weight first, then nearby weights
                    mb = adj_map[b]
                    for target_w in (dw, dw - 1, dw + 1):
                        if target_w < lo or target_w > hi:
                            continue
                        for c in by_w1.get(target_w, ()):
                            if side[c] != 1:
                                continue
                            g = gab + gains[c] - 2.0 * (ma.get(c, 0.0) + mb.get(c, 0.0))
                            if g > 1e-9:
                                flip_node(a)
                                flip_node(b)
                                flip_node(c)
                                improved = True
                                found_21 = True
                                break
                        if found_21:
                            break
                    if found_21:
                        break
                if found_21:
                    break

            # 1 from side 0, 2 from side 1
            if not found_21 and time.monotonic() < deadline:
                by_w0 = defaultdict(list)
                for u in b0_top[:100]:
                    if side[u] == 0:
                        by_w0[node_weights[u]].append(u)
                found_12 = False
                for i in range(len(m1)):
                    a = m1[i]
                    if side[a] != 1:
                        continue
                    wa = node_weights[a]
                    ga = gains[a]
                    ma = adj_map[a]
                    for j in range(i + 1, len(m1)):
                        b = m1[j]
                        if side[b] != 1:
                            continue
                        wb = node_weights[b]
                        wab = ma.get(b, 0.0)
                        gab = ga + gains[b] + 2.0 * wab
                        dw = wa + wb
                        lo = dw + w1 - cap_f
                        hi = cap_f - w0 + dw
                        mb = adj_map[b]
                        for target_w in (dw, dw - 1, dw + 1):
                            if target_w < lo or target_w > hi:
                                continue
                            for c in by_w0.get(target_w, ()):
                                if side[c] != 0:
                                    continue
                                g = gab + gains[c] - 2.0 * (ma.get(c, 0.0) + mb.get(c, 0.0))
                                if g > 1e-9:
                                    flip_node(a)
                                    flip_node(b)
                                    flip_node(c)
                                    improved = True
                                    found_12 = True
                                    break
                            if found_12:
                                break
                        if found_12:
                            break
                    if found_12:
                        break

        if not improved:
            break

    if n > 0 and side[0] != 0:
        side = [1 - s for s in side]
    return side


def milp_refine(side, subset, node_weights, adj, cap_f, total_w, tl):
    if highspy is None or tl <= 0.05 or len(subset) < 2:
        return None
    k = len(subset)
    idx_map = {u: i for i, u in enumerate(subset)}
    w_s_fix = 0
    w_t_fix = 0
    w_u = 0
    for u, wu in enumerate(node_weights):
        if u in idx_map:
            w_u += wu
        elif side[u] == 0:
            w_s_fix += wu
        else:
            w_t_fix += wu

    lo_w = w_s_fix + w_u - cap_f
    hi_w = cap_f - w_t_fix
    if lo_w > hi_w:
        return None

    lin_cost = [0.0] * k
    int_edges = []
    for i, u in enumerate(subset):
        for v, ew in adj[u]:
            if v in idx_map:
                j = idx_map[v]
                if i < j and ew != 0.0:
                    int_edges.append((i, j, ew))
            else:
                # x_u = 1 means side 1 (T), x_u = 0 means side 0 (S)
                if side[v] == 0:
                    lin_cost[i] += ew
                else:
                    lin_cost[i] -= ew

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("threads", 2)
    h.setOptionValue("time_limit", float(tl))

    num_e = len(int_edges)
    num_vars = k + num_e
    inf = highspy.kHighsInf

    for i in range(k):
        ub = 0.0 if (subset[i] == 0 and k == len(node_weights)) else 1.0
        h.addVar(0.0, ub)
        h.changeColCost(i, float(lin_cost[i]))
        h.changeColIntegrality(i, highspy.HighsVarType.kInteger)

    for e_idx, (i, j, ew) in enumerate(int_edges):
        v_idx = k + e_idx
        h.addVar(0.0, 1.0)
        h.changeColCost(v_idx, float(ew))

    # Balance constraint: lo_w <= sum(w[u] * x_u) <= hi_w
    h.addRow(float(lo_w), float(hi_w), k, list(range(k)), [float(node_weights[u]) for u in subset])

    # Cut linearization constraints
    for e_idx, (i, j, ew) in enumerate(int_edges):
        v_idx = k + e_idx
        if ew > 0:
            h.addRow(0.0, inf, 3, [v_idx, i, j], [1.0, -1.0, 1.0])
            h.addRow(0.0, inf, 3, [v_idx, i, j], [1.0, 1.0, -1.0])
        else:
            h.addRow(-inf, 0.0, 3, [v_idx, i, j], [1.0, -1.0, -1.0])
            h.addRow(-inf, 2.0, 3, [v_idx, i, j], [1.0, 1.0, 1.0])

    h.run()
    sol = h.getSolution()
    if not sol.value_valid or len(sol.col_value) < k:
        return None
    new_side = list(side)
    for i, u in enumerate(subset):
        new_side[u] = 1 if sol.col_value[i] >= 0.5 else 0
    if len(new_side) > 0 and new_side[0] != 0:
        new_side = [1 - s for s in new_side]
    return new_side


def select_boundary_subset(side, adj, max_k, rng):
    n = len(side)
    boundary = []
    for u in range(n):
        su = side[u]
        for v, _ in adj[u]:
            if side[v] != su:
                boundary.append(u)
                break
    if not boundary:
        return rng.sample(range(n), min(n, max_k))
    seed = rng.choice(boundary)
    chosen = {seed}
    frontier = [seed]
    while frontier and len(chosen) < max_k:
        u = frontier.pop(rng.randrange(len(frontier)))
        nbrs = [v for v, _ in adj[u] if v not in chosen]
        rng.shuffle(nbrs)
        for v in nbrs:
            if len(chosen) >= max_k:
                break
            chosen.add(v)
            frontier.append(v)
    if len(chosen) < max_k:
        rng.shuffle(boundary)
        for u in boundary:
            if len(chosen) >= max_k:
                break
            chosen.add(u)
    return list(chosen)


def _run_kahip_isolated(vwgt, xadj, adjcwgt, adjncy, imb, seed, mode, deadline):
    import select
    import signal
    import struct

    if time.monotonic() >= deadline:
        return "timeout", None

    r_fd, w_fd = os.pipe()
    try:
        pid = os.fork()
    except OSError:
        os.close(r_fd)
        os.close(w_fd)
        return "abort", None

    if pid == 0:
        os.close(r_fd)
        try:
            _, part = kahip.kaffpa(vwgt, xadj, adjcwgt, adjncy, 2, imb, True, seed, mode)
            payload = bytes(part)
            data = struct.pack("<I", len(payload)) + payload
            view = memoryview(data)
            sent = 0
            while sent < len(view):
                written = os.write(w_fd, view[sent:])
                if written <= 0:
                    os._exit(3)
                sent += written
            os.close(w_fd)
            os._exit(0)
        except BaseException:
            try:
                os.close(w_fd)
            except OSError:
                pass
            os._exit(2)

    os.close(w_fd)
    chunks = []
    timed_out = False
    reaped = False
    status = None
    try:
        while True:
            rem = deadline - time.monotonic()
            if rem <= 0.0:
                timed_out = True
                break
            try:
                ready, _, _ = select.select([r_fd], [], [], rem)
            except InterruptedError:
                continue
            if not ready:
                timed_out = True
                break
            try:
                chunk = os.read(r_fd, 65536)
            except InterruptedError:
                continue
            if not chunk:
                break
            chunks.append(chunk)
    finally:
        try:
            os.close(r_fd)
        except OSError:
            pass
        if not timed_out:
            grace_end = min(deadline, time.monotonic() + 0.05)
            while True:
                try:
                    wpid, st = os.waitpid(pid, os.WNOHANG)
                except ChildProcessError:
                    reaped = True
                    break
                if wpid == pid:
                    status = st
                    reaped = True
                    break
                if time.monotonic() >= grace_end:
                    break
                time.sleep(0.002)
        if not reaped:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            while True:
                try:
                    _, st = os.waitpid(pid, 0)
                    status = st
                    break
                except InterruptedError:
                    continue
                except ChildProcessError:
                    break

    if timed_out:
        return "timeout", None
    if status is None or not (os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0):
        return "abort", None
    buf = b"".join(chunks)
    if len(buf) < 4:
        return "abort", None
    plen = struct.unpack("<I", buf[:4])[0]
    if len(buf) != 4 + plen or plen != len(vwgt):
        return "abort", None
    return "ok", list(buf[4:])


def solve_instance(data, time_limit):
    t_start = time.monotonic()
    hard_deadline = t_start + max(1.0, time_limit - 1.2)
    n = int(data["num_nodes"])
    cap_f = int(data["bisection_capacity_F"])
    total_w = int(data["total_node_weight"])
    node_weights = [int(w) for w in data["node_weights"]]
    edges = data["edges"]
    edge_weights = [float(w) for w in data["edge_weights"]]

    if n <= 1:
        part_s = [0] if n == 1 else []
        return {"objective_value": 0.0, "partition_S": part_s, "partition_complement": []}

    rng = random.Random(42)
    adj, adj_map, csr = build_graph(n, edges, edge_weights, node_weights)
    vwgt, xadj, adjcwgt, adjncy = csr

    best_cut = float("inf")
    best_side = None
    pool = []  # list of (cut, side)
    pool_hashes = set()

    def try_accept(cand_side):
        nonlocal best_cut, best_side
        ok, cut, _, _, cand_side = evaluate_and_validate(
            cand_side, node_weights, edges, edge_weights, cap_f, total_w
        )
        if not ok:
            return False, cut
        hval = hash(tuple(cand_side))
        if hval not in pool_hashes:
            pool_hashes.add(hval)
            pool.append((cut, list(cand_side)))
            pool.sort(key=lambda x: x[0])
            if len(pool) > 16:
                pool.pop()
        if cut < best_cut - 1e-12:
            best_cut = cut
            best_side = list(cand_side)
            return True, cut
        return False, cut

    # 1. Guaranteed feasible initial incumbent
    init_side = greedy_lpt_init(node_weights, adj, cap_f, total_w, rng)
    init_side = repair_partition(init_side, node_weights, adj, cap_f, total_w, rng)
    init_side = local_search_fm_swap(
        init_side, node_weights, adj, adj_map, cap_f, total_w, min(hard_deadline, time.monotonic() + 2.0)
    )
    try_accept(init_side)

    # Small graph direct MILP
    if n <= 100 and highspy is not None and time.monotonic() < hard_deadline - 1.0:
        tl = min(8.0, (hard_deadline - time.monotonic()) * 0.35)
        m_side = milp_refine(best_side, list(range(n)), node_weights, adj, cap_f, total_w, tl)
        if m_side is not None:
            try_accept(m_side)

    # 2. Multistart KaHIP with adaptive mode control (~50% of budget)
    kahip_deadline = t_start + (hard_deadline - t_start) * 0.52
    if kahip is not None and len(adjncy) > 0:
        vwgt_sum = sum(vwgt)
        eps_slack = max(0.0, (2.0 * cap_f / max(1, total_w)) - 1.0 - 1e-5)
        if vwgt_sum != total_w:
            eps_slack = 0.0
        mode_times = {0: None, 1: None, 2: None}
        mode_failures = {0: 0, 1: 0, 2: 0}
        mode_disabled = {0: False, 1: False, 2: False}
        seed = 1
        while time.monotonic() < kahip_deadline:
            rem = kahip_deadline - time.monotonic()
            if rem <= 0.15:
                break
            # Choose mode safely based on observed runtimes and failures
            mode = None
            if not mode_disabled[0] and mode_times[0] is None:
                mode = 0
            elif not mode_disabled[1] and mode_times[1] is None and (
                mode_disabled[0] or (mode_times[0] is not None and mode_times[0] < rem * 0.15)
            ):
                mode = 1
            elif not mode_disabled[2] and mode_times[2] is None and (
                (mode_disabled[0] and mode_disabled[1]) or (mode_times[1] is not None and mode_times[1] < rem * 0.12)
            ):
                mode = 2
            else:
                avail = []
                if not mode_disabled[0] and (mode_times[0] is None or mode_times[0] * 1.5 < rem):
                    avail.append(0)
                if not mode_disabled[1] and mode_times[1] is not None and mode_times[1] * 1.5 < rem:
                    avail.append(1)
                if not mode_disabled[2] and mode_times[2] is not None and mode_times[2] * 1.5 < rem:
                    avail.append(2)
                if not avail:
                    avail = [m for m in (0, 1, 2) if not mode_disabled[m]]
                if not avail:
                    break
                mode = avail[seed % len(avail)]

            other_active = sum(1 for m in (0, 1, 2) if m != mode and not mode_disabled[m])
            if mode_times[mode] is None:
                call_budget = rem if other_active == 0 else min(rem, max(0.5, rem / (other_active + 1))) 
            else:
                call_budget = min(rem, max(1.0, mode_times[mode] * 4.0))
            call_deadline = min(kahip_deadline, time.monotonic() + call_budget)

            imb = 0.0 if (seed % 3 != 0 or eps_slack <= 1e-4) else min(0.05, eps_slack)
            t0 = time.monotonic()
            status, part = _run_kahip_isolated(vwgt, xadj, adjcwgt, adjncy, imb, seed, mode, call_deadline)
            dt = time.monotonic() - t0
            seed += 1

            if status != "ok":
                mode_failures[mode] += 1
                if mode_times[mode] is None or mode_failures[mode] >= 2:
                    mode_disabled[mode] = True
                continue

            mode_failures[mode] = 0
            mode_times[mode] = dt if mode_times[mode] is None else 0.7 * mode_times[mode] + 0.3 * dt

            cand = repair_partition(part, node_weights, adj, cap_f, total_w, rng)
            if time.monotonic() < hard_deadline:
                cand = local_search_fm_swap(
                    cand, node_weights, adj, adj_map, cap_f, total_w,
                    min(hard_deadline, time.monotonic() + max(0.2, min(1.5, dt * 2.0))),
                    max_passes=8
                )
            try_accept(cand)

    # 3. Refinement: Sparse Recombination + Boundary LNS MILP + Perturbed Local Search
    it = 0
    while time.monotonic() < hard_deadline:
        rem = hard_deadline - time.monotonic()
        if rem <= 0.15:
            break
        it += 1

        # A. Sparse Recombination of two strong partitions from pool
        if len(pool) >= 2 and it % 2 == 1:
            p1 = pool[0][1] if (it % 4 == 1) else pool[rng.randrange(len(pool))][1]
            p2 = pool[rng.randrange(len(pool))][1]
            if p1 is not p2:
                # Align p2 to p1
                same = sum(1 for a, b in zip(p1, p2) if a == b)
                if same < n - same:
                    p2_al = [1 - b for b in p2]
                else:
                    p2_al = p2
                diff = [u for u in range(n) if p1[u] != p2_al[u]]
                if 2 <= len(diff) <= 140 and highspy is not None:
                    tl = min(1.8, rem * 0.4)
                    child = milp_refine(p1, diff, node_weights, adj, cap_f, total_w, tl)
                    if child is not None:
                        child = repair_partition(child, node_weights, adj, cap_f, total_w, rng)
                        child = local_search_fm_swap(
                            child, node_weights, adj, adj_map, cap_f, total_w,
                            min(hard_deadline, time.monotonic() + 1.0), max_passes=6
                        )
                        try_accept(child)
                elif len(diff) > 140:
                    sub = rng.sample(diff, 100)
                    if highspy is not None:
                        tl = min(1.5, rem * 0.35)
                        child = milp_refine(p1, sub, node_weights, adj, cap_f, total_w, tl)
                        if child is not None:
                            child = repair_partition(child, node_weights, adj, cap_f, total_w, rng)
                            child = local_search_fm_swap(
                                child, node_weights, adj, adj_map, cap_f, total_w,
                                min(hard_deadline, time.monotonic() + 1.0), max_passes=6
                            )
                            try_accept(child)
                    else:
                        child = list(p1)
                        for u in sub:
                            child[u] = p2_al[u]
                        child = repair_partition(child, node_weights, adj, cap_f, total_w, rng)
                        child = local_search_fm_swap(
                            child, node_weights, adj, adj_map, cap_f, total_w,
                            min(hard_deadline, time.monotonic() + 1.0), max_passes=6
                        )
                        try_accept(child)

        if time.monotonic() >= hard_deadline:
            break

        # B. Boundary LNS MILP around incumbent
        if highspy is not None and it % 2 == 0:
            base = best_side if (it % 4 == 0 or not pool) else pool[rng.randrange(min(4, len(pool)))][1]
            k_sub = min(n, rng.randint(50, 110))
            sub = select_boundary_subset(base, adj, k_sub, rng)
            tl = min(1.6, max(0.2, (hard_deadline - time.monotonic()) * 0.35))
            cand = milp_refine(base, sub, node_weights, adj, cap_f, total_w, tl)
            if cand is not None:
                cand = local_search_fm_swap(
                    cand, node_weights, adj, adj_map, cap_f, total_w,
                    min(hard_deadline, time.monotonic() + 1.0), max_passes=8
                )
                try_accept(cand)
        else:
            # C. Perturbation + Local Search
            base = list(best_side)
            sub = select_boundary_subset(base, adj, min(n, max(4, n // 20)), rng)
            for u in sub:
                if rng.random() < 0.35:
                    base[u] = 1 - base[u]
            cand = repair_partition(base, node_weights, adj, cap_f, total_w, rng)
            cand = local_search_fm_swap(
                cand, node_weights, adj, adj_map, cap_f, total_w,
                min(hard_deadline, time.monotonic() + 1.0), max_passes=8
            )
            try_accept(cand)

    ok, final_cut, _, _, final_side = evaluate_and_validate(
        best_side, node_weights, edges, edge_weights, cap_f, total_w
    )
    if not ok:
        final_side = greedy_lpt_init(node_weights, adj, cap_f, total_w, rng)
        _, final_cut, _, _, final_side = evaluate_and_validate(
            final_side, node_weights, edges, edge_weights, cap_f, total_w
        )

    part_s = [i for i, s in enumerate(final_side) if s == 0]
    part_c = [i for i, s in enumerate(final_side) if s == 1]
    return {
        "objective_value": float(final_cut),
        "partition_S": part_s,
        "partition_complement": part_c,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--problem", required=True)
    parser.add_argument("--instance", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--time-limit", type=float, default=60.0)
    args = parser.parse_args()

    with open(args.instance, "r", encoding="utf-8") as f:
        data = json.load(f)

    result = solve_instance(data, args.time_limit)

    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(result, f)


if __name__ == "__main__":
    main()
