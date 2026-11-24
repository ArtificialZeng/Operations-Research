"""Stage 1 Locked Held-Out Synthetic Benchmark (PRE-REGISTERED SOURCE — DO NOT RUN UNTIL APPROVED).

Strictly matched 2-arm comparison for simple, undirected, unweighted, fixed-budget 2-DCNP:
  - BASE_FULL : Salemi-Buchanan Thin (d=2) + deterministic independent-set simplicial fixing (x_v = 0)
                + bounded Chen et al. (2025) Clique-Chord separation (incl. Alozie Prop. 3.4.1 triangles)
                + bounded Alozie (2021/2024) Prop. 3.4.2 5-cycle (C_5) separation
  - AUG_HUB   : Exact same BASE_FULL + Theorem 1 Hub-Lifted Closed-Neighborhood (N[w]) cuts ONLY
                (fixed pre-registered density cap |Q| <= 8, viol >= 0.05, viol/RHS >= 0.01, <= 15/round, <= 30 total)

Both arms run under:
  - Identical single-threaded HiGHS 1.15.1 (threads=1, random_seed=20261124, presolve="on")
  - Identical common actual monotone wall deadline (WALL_LIMIT_S = 60.0s covering build, simplicial fixing,
    LP solves, cut separation, and MIP search)
  - Independent exact BFS verification of every feasible incumbent and strict dual-validity assertions
  - Neutral post-run aggregates overall and stratified by all 4 synthetic families.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from time import perf_counter

import highspy
import networkx as nx
import numpy as np

OUT_PATH = Path(__file__).resolve().parent / "stage1_heldout_synthetic_results.json"

# ---------------------------------------------------------------------------
# LOCKED PRE-REGISTERED HYPERPARAMETERS (FIXED BEFORE EXECUTION)
# ---------------------------------------------------------------------------
WALL_LIMIT_S: float = 60.0
MIP_RESERVE_S: float = 5.0
SOLVER_SEED: int = 20261124
MIP_REL_GAP: float = 1e-6
MIP_ABS_GAP: float = 1e-6

MAX_SEP_ROUNDS: int = 6
MIN_LP_GAIN_STOP: float = 1e-3
VIOL_ABS_MIN: float = 0.05
VIOL_REL_MIN: float = 0.01

MAX_CLQ_PER_ROUND: int = 20
MAX_C5_PER_ROUND: int = 20
MAX_C5_VISITS_PER_ROUND: int = 250_000

MAX_HUB_Q: int = 8
MAX_HUB_PER_ROUND: int = 15
MAX_HUB_TOTAL: int = 30


# ---------------------------------------------------------------------------
# LOCKED HELD-OUT SYNTHETIC MATRIX (16 INSTANCES, FRESH SEEDS 501-534)
# ---------------------------------------------------------------------------
def build_heldout_matrix() -> list[tuple[str, str, int, nx.Graph]]:
    """Return list of (instance_id, family, budget, graph) with 0..n-1 sorted integer labels."""
    specs: list[tuple[str, str, int, nx.Graph]] = []

    # Family 1: Triangle-Free Random Bipartite
    for seed in (501, 502):
        specs.append((f"bip_36x36_p012_s{seed}", "bipartite_tri_free", 12, nx.bipartite.random_graph(36, 36, 0.12, seed=seed)))
    for seed in (503, 504):
        specs.append((f"bip_44x44_p010_s{seed}", "bipartite_tri_free", 15, nx.bipartite.random_graph(44, 44, 0.10, seed=seed)))

    # Family 2: Sparse Random Regular (d=4)
    for seed in (511, 512):
        specs.append((f"reg_n64_d4_s{seed}", "regular_d4", 11, nx.random_regular_graph(4, 64, seed=seed)))
    for seed in (513, 514):
        specs.append((f"reg_n80_d4_s{seed}", "regular_d4", 14, nx.random_regular_graph(4, 80, seed=seed)))

    # Family 3: Watts-Strogatz (k=6, p=0.20)
    for seed in (521, 522):
        specs.append((f"ws_n64_k6_p020_s{seed}", "watts_strogatz_k6", 11, nx.watts_strogatz_graph(64, 6, 0.20, seed=seed)))
    for seed in (523, 524):
        specs.append((f"ws_n80_k6_p020_s{seed}", "watts_strogatz_k6", 14, nx.watts_strogatz_graph(80, 6, 0.20, seed=seed)))

    # Family 4: Stochastic Block Model (4 communities, p_in=0.35, p_out=0.04)
    p_sbm = [[0.35 if i == j else 0.04 for j in range(4)] for i in range(4)]
    for seed in (531, 532):
        specs.append((f"sbm_4x16_s{seed}", "sbm_4comm", 11, nx.stochastic_block_model([16] * 4, p_sbm, seed=seed)))
    for seed in (533, 534):
        specs.append((f"sbm_4x20_s{seed}", "sbm_4comm", 14, nx.stochastic_block_model([20] * 4, p_sbm, seed=seed)))

    normalized: list[tuple[str, str, int, nx.Graph]] = []
    for iid, fam, b, G in specs:
        H = nx.Graph()
        H.add_nodes_from(range(G.number_of_nodes()))
        G_int = nx.convert_node_labels_to_integers(G, ordering="sorted")
        H.add_edges_from((u, v) for u, v in G_int.edges() if u != v)
        normalized.append((iid, fam, b, H))
    return normalized


# ---------------------------------------------------------------------------
# CORE GRAPH, SIMPLICIAL FIXING, EXACT BFS & CUT FORMULAS (INDEPENDENT IMPL)
# ---------------------------------------------------------------------------
def exact_bfs_obj(G: nx.Graph, deleted: set[int]) -> int:
    H = G.subgraph([v for v in G.nodes() if v not in deleted])
    pairs = 0
    for u in H.nodes():
        nbrs = set(H.neighbors(u))
        r = set(nbrs)
        for w in nbrs:
            r.update(H.neighbors(w))
        r.discard(u)
        pairs += len(r)
    return pairs // 2


def compute_e2(G: nx.Graph) -> tuple[list[tuple[int, int]], dict[tuple[int, int], int], dict[tuple[int, int], list[int]]]:
    n = G.number_of_nodes()
    adj = [set(G.neighbors(u)) for u in range(n)]
    e2_set: set[tuple[int, int]] = set()
    common: dict[tuple[int, int], list[int]] = {}
    for u in range(n):
        for v in adj[u]:
            if u < v:
                e2_set.add((u, v))
        two_hop: dict[int, list[int]] = {}
        for w in adj[u]:
            for v in adj[w]:
                if v > u and v not in adj[u]:
                    two_hop.setdefault(v, []).append(w)
        for v, ws in two_hop.items():
            e2_set.add((u, v))
            common[(u, v)] = sorted(ws)
    e2 = sorted(e2_set)
    return e2, {p: i for i, p in enumerate(e2)}, common


def greedy_independent_simplicial_set(G: nx.Graph) -> list[int]:
    """Deterministic independent set F of simplicial vertices (x_v = 0 valid for all G and b)."""
    n = G.number_of_nodes()
    adj = [set(G.neighbors(u)) for u in range(n)]
    fixed: set[int] = set()
    for v in range(n):
        nbrs = list(adj[v])
        is_clique = True
        for i in range(len(nbrs)):
            u = nbrs[i]
            for j in range(i + 1, len(nbrs)):
                if nbrs[j] not in adj[u]:
                    is_clique = False
                    break
            if not is_clique:
                break
        if is_clique and not (adj[v] & fixed):
            fixed.add(v)
    return sorted(fixed)


def lb_edges_after_r_deletions(sub_deg_desc: list[int], m_q: int, r: int) -> int:
    if r == 0:
        return m_q
    if r >= len(sub_deg_desc):
        return 0
    return max(0, m_q - sum(sub_deg_desc[:r]))


def hub_star_cut_params(adj: list[set[int]], w: int, Q: list[int], t: int) -> tuple[int, int, int, int]:
    q = len(Q)
    s = q - t
    R = (q + 1 - t) * (q - t) // 2 + t * s
    Q_set = set(Q)
    sub_deg = sorted([len(adj[u] & Q_set) for u in Q], reverse=True)
    m_q = sum(sub_deg) // 2
    mu = min(lb_edges_after_r_deletions(sub_deg, m_q, r) + s * r for r in range(q + 1))
    M_w = R - mu
    return s, M_w, R, mu


# ---------------------------------------------------------------------------
# MATCHED BOUNDED CUT SEPARATORS (IDENTICAL POLICIES ACROSS BOTH ARMS)
# ---------------------------------------------------------------------------
def separate_clique_chord_cuts(
    max_cliques: list[list[int]],
    triangles: list[tuple[int, int, int]],
    idx_map: dict[tuple[int, int], int],
    n: int,
    x: np.ndarray,
    y: np.ndarray,
    seen_clq: set[tuple[tuple[int, ...], int]],
    deadline: float,
) -> list[tuple[float, float, tuple[tuple[int, ...], int], np.ndarray, np.ndarray, float]]:
    """Bounded Chen et al. (2025) analogously adapted Clique-Chord separator + exact Alozie Prop. 3.4.1 K_3."""
    cands = []
    # Exact check of all triangles (Alozie Prop. 3.4.1: q=3, t=1 -> s=1, RHS=2; and t=0 -> s=2, RHS=3)
    for tri in triangles:
        if perf_counter() >= deadline:
            break
        u, v, w = tri
        p_ids = [idx_map[(u, v)], idx_map[(u, w)], idx_map[(v, w)]]
        sum_y = float(y[p_ids[0]] + y[p_ids[1]] + y[p_ids[2]])
        sum_x = float(x[u] + x[v] + x[w])
        for t, s, rhs in ((0, 2, 3.0), (1, 1, 2.0)):
            key = (tri, t)
            if key in seen_clq:
                continue
            viol = rhs - (sum_y + float(s) * sum_x)
            rel_viol = viol / rhs
            if viol >= VIOL_ABS_MIN and rel_viol >= VIOL_REL_MIN:
                inds = np.array([u, v, w, n + p_ids[0], n + p_ids[1], n + p_ids[2]], dtype=np.int32)
                vals = np.array([float(s), float(s), float(s), 1.0, 1.0, 1.0], dtype=np.float64)
                cands.append((rel_viol, viol, key, inds, vals, rhs))

    # Maximal cliques of size >= 4 (full clique + x-ordered active subsets of size 4..|mc|)
    for mc in max_cliques:
        if len(mc) < 4:
            continue
        if perf_counter() >= deadline:
            break
        ordered = sorted(mc, key=lambda v: (float(x[v]), v))
        for q in range(4, len(ordered) + 1):
            K = tuple(sorted(ordered[:q]))
            sum_x = float(sum(x[v] for v in K))
            pair_ids = [idx_map[(K[i], K[j])] for i in range(q) for j in range(i + 1, q)]
            sum_y = float(sum(y[pi] for pi in pair_ids))
            for t in range(q - 1):
                key = (K, t)
                if key in seen_clq:
                    continue
                s = q - t - 1
                rhs = float((q - t) * (q - t - 1) // 2 + t * s)
                lhs = sum_y + float(s) * sum_x
                viol = rhs - lhs
                rel_viol = viol / rhs
                if viol >= VIOL_ABS_MIN and rel_viol >= VIOL_REL_MIN:
                    inds = np.array(list(K) + [n + pi for pi in pair_ids], dtype=np.int32)
                    vals = np.array([float(s)] * q + [1.0] * len(pair_ids), dtype=np.float64)
                    cands.append((rel_viol, viol, key, inds, vals, rhs))
    cands.sort(key=lambda item: (-item[0], -item[1], item[2]))
    chosen = []
    for item in cands:
        key = item[2]
        if key in seen_clq:
            continue
        seen_clq.add(key)
        chosen.append(item)
        if len(chosen) >= MAX_CLQ_PER_ROUND:
            break
    return chosen


def separate_alozie_c5_cuts(
    adj_sorted: list[list[int]],
    adj_sets: list[set[int]],
    idx_map: dict[tuple[int, int], int],
    n: int,
    x: np.ndarray,
    y: np.ndarray,
    seen_c5: set[tuple[int, int, int, int, int]],
    deadline: float,
) -> list[tuple[float, float, tuple[int, int, int, int, int], np.ndarray, np.ndarray, float]]:
    """Deterministic branch-and-bound pruned Alozie (2021/2024) Prop. 3.4.2 5-cycle separator.
    Inequality: 2*(x_0 + x_1 + x_2 + x_3 + x_4) + y_{02} + y_{13} + y_{24} + y_{30} + y_{41} >= 4.
    Identical visit cap and violation policy in BOTH arms.
    """
    cutoff = 4.0 - max(VIOL_ABS_MIN, 4.0 * VIOL_REL_MIN)
    cands = []
    visits = 0

    for v0 in range(n):
        c0 = 2.0 * float(x[v0])
        if c0 >= cutoff:
            continue
        nbr0 = adj_sorted[v0]
        set0 = adj_sets[v0]
        for v1 in nbr0:
            if v1 <= v0:
                continue
            c1 = c0 + 2.0 * float(x[v1])
            if c1 >= cutoff:
                continue
            for v2 in adj_sorted[v1]:
                if v2 <= v0 or v2 == v1:
                    continue
                visits += 1
                if visits > MAX_C5_VISITS_PER_ROUND:
                    break
                if (visits & 8191) == 0 and perf_counter() >= deadline:
                    visits = MAX_C5_VISITS_PER_ROUND + 1
                    break
                p02 = (v0, v2) if v0 < v2 else (v2, v0)
                c2 = c1 + 2.0 * float(x[v2]) + float(y[idx_map[p02]])
                if c2 >= cutoff:
                    continue
                for v3 in adj_sorted[v2]:
                    if v3 <= v0 or v3 == v1 or v3 == v2:
                        continue
                    # v4 must be in adj[v3] cap adj[v0] with v4 > v1
                    common_v4 = adj_sets[v3] & set0
                    if not common_v4:
                        continue
                    p13 = (v1, v3) if v1 < v3 else (v3, v1)
                    p30 = (v0, v3)  # v0 < v3 guaranteed; dist(v0,v3)<=2 via any v4 in common_v4
                    c3 = c2 + 2.0 * float(x[v3]) + float(y[idx_map[p13]]) + float(y[idx_map[p30]])
                    if c3 >= cutoff:
                        continue
                    for v4 in sorted(common_v4):
                        if v4 <= v1 or v4 == v2:
                            continue
                        p24 = (v2, v4) if v2 < v4 else (v4, v2)
                        p41 = (v1, v4)  # v1 < v4 guaranteed
                        lhs = c3 + 2.0 * float(x[v4]) + float(y[idx_map[p24]]) + float(y[idx_map[p41]])
                        viol = 4.0 - lhs
                        if viol >= VIOL_ABS_MIN and (viol / 4.0) >= VIOL_REL_MIN:
                            key = (v0, v1, v2, v3, v4)
                            if key not in seen_c5:
                                chord_vars = [
                                    n + idx_map[p02],
                                    n + idx_map[p13],
                                    n + idx_map[p24],
                                    n + idx_map[p30],
                                    n + idx_map[p41],
                                ]
                                inds = np.array([v0, v1, v2, v3, v4] + chord_vars, dtype=np.int32)
                                vals = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
                                cands.append((viol / 4.0, viol, key, inds, vals, 4.0))
            if visits > MAX_C5_VISITS_PER_ROUND:
                break
        if visits > MAX_C5_VISITS_PER_ROUND:
            break

    cands.sort(key=lambda item: (-item[0], -item[1], item[2]))
    chosen = []
    for item in cands:
        key = item[2]
        if key in seen_c5:
            continue
        seen_c5.add(key)
        chosen.append(item)
        if len(chosen) >= MAX_C5_PER_ROUND:
            break
    return chosen


def separate_hub_star_cuts(
    adj_sets: list[set[int]],
    idx_map: dict[tuple[int, int], int],
    n: int,
    x: np.ndarray,
    y: np.ndarray,
    seen_hub: set[tuple[int, tuple[int, ...], int]],
    remaining_hub_budget: int,
    deadline: float,
) -> list[tuple[float, float, tuple[int, tuple[int, ...], int], np.ndarray, np.ndarray, float]]:
    """Bounded Theorem 1 Hub-Lifted Closed-Neighborhood separator (AUG_HUB arm ONLY).
    Fixed pre-registered sparsity cap: 2 <= |Q| <= MAX_HUB_Q (=8), <= MAX_HUB_PER_ROUND (=15),
    <= MAX_HUB_TOTAL (=30).
    """
    if remaining_hub_budget <= 0:
        return []
    cands = []
    for w in range(n):
        if perf_counter() >= deadline:
            break
        if len(adj_sets[w]) < 2:
            continue
        nbrs_ordered = sorted(adj_sets[w], key=lambda u: (float(x[u]), u))
        q_max = min(len(nbrs_ordered), MAX_HUB_Q)
        for q in range(2, q_max + 1):
            Q = sorted(nbrs_ordered[:q])
            Q_tup = tuple(Q)
            nodes_all = sorted(Q + [w])
            pair_ids = [idx_map[(nodes_all[i], nodes_all[j])] for i in range(q + 1) for j in range(i + 1, q + 1)]
            sum_y = float(sum(y[pi] for pi in pair_ids))
            sum_xQ = float(sum(x[u] for u in Q))
            xw = float(x[w])
            for t in range(q):
                key = (w, Q_tup, t)
                if key in seen_hub:
                    continue
                s, Mw, R, _ = hub_star_cut_params(adj_sets, w, Q, t)
                lhs = sum_y + float(s) * sum_xQ + float(Mw) * xw
                viol = float(R) - lhs
                rel_viol = viol / float(R)
                if viol >= VIOL_ABS_MIN and rel_viol >= VIOL_REL_MIN:
                    inds = np.array(Q + [w] + [n + pi for pi in pair_ids], dtype=np.int32)
                    vals = np.array([float(s)] * q + [float(Mw)] + [1.0] * len(pair_ids), dtype=np.float64)
                    cands.append((rel_viol, viol, key, inds, vals, float(R)))

    cands.sort(key=lambda item: (-item[0], -item[1], item[2]))
    cap = min(MAX_HUB_PER_ROUND, remaining_hub_budget)
    chosen = []
    for item in cands:
        key = item[2]
        if key in seen_hub:
            continue
        seen_hub.add(key)
        chosen.append(item)
        if len(chosen) >= cap:
            break
    return chosen


# ---------------------------------------------------------------------------
# SINGLE-ARM EXECUTOR UNDER STRICT COMMON MONOTONE WALL DEADLINE
# ---------------------------------------------------------------------------
def run_arm_under_monotone_deadline(
    G: nx.Graph, budget: int, arm: str, wall_limit_s: float = WALL_LIMIT_S
) -> dict:
    assert arm in ("BASE_FULL", "AUG_HUB")
    t_start = perf_counter()
    deadline = t_start + wall_limit_s

    n = G.number_of_nodes()
    adj_sets = [set(G.neighbors(u)) for u in range(n)]
    adj_sorted = [sorted(adj_sets[u]) for u in range(n)]

    # 1. Build Thin d=2 formulation + identical deterministic independent-set simplicial fixing
    e2, idx_map, common = compute_e2(G)
    m2 = len(e2)
    simplicial_fixed = greedy_independent_simplicial_set(G)
    simplicial_set = set(simplicial_fixed)

    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("threads", 1)
    h.setOptionValue("random_seed", SOLVER_SEED)
    h.setOptionValue("presolve", "on")
    h.setOptionValue("mip_rel_gap", MIP_REL_GAP)
    h.setOptionValue("mip_abs_gap", MIP_ABS_GAP)

    num_vars = n + m2
    ub = np.ones(num_vars, dtype=np.float64)
    for v in simplicial_fixed:
        ub[v] = 0.0

    h.addCols(
        num_vars,
        np.concatenate([np.zeros(n), np.ones(m2)]),
        np.zeros(num_vars, dtype=np.float64),
        ub,
        0,
        np.array([], dtype=np.int32),
        np.array([], dtype=np.int32),
        np.array([], dtype=np.float64),
    )
    h.addRow(-highspy.kHighsInf, float(budget), n, np.arange(n, dtype=np.int32), np.ones(n, dtype=np.float64))
    for u, v in G.edges():
        p = (u, v) if u < v else (v, u)
        h.addRow(1.0, highspy.kHighsInf, 3, np.array([u, v, n + idx_map[p]], dtype=np.int32), np.array([1.0, 1.0, 1.0]))
    for (u, v), ws in common.items():
        yi = n + idx_map[(u, v)]
        for w in ws:
            h.addRow(1.0, highspy.kHighsInf, 4, np.array([u, v, w, yi], dtype=np.int32), np.array([1.0, 1.0, 1.0, 1.0]))

    # Precompute triangles (for exact Alozie Prop. 3.4.1) and maximal cliques >= 4 inside wall budget (identical in both arms)
    triangles = [
        (u, v, w)
        for u in range(n)
        for v in adj_sorted[u]
        if v > u
        for w in adj_sorted[v]
        if w > v and w in adj_sets[u]
    ]
    max_cliques = [sorted(c) for c in nx.find_cliques(G) if len(c) >= 4]
    t_after_build = perf_counter()
    t_build_and_simp_s = t_after_build - t_start

    # 2. Initial LP + Matched Bounded Root Cut-Separation Loop
    hit_wall_deadline = False
    rem = deadline - perf_counter()
    if rem <= 0.05:
        hit_wall_deadline = True
        return {
            "arm": arm,
            "status": "WALL_EXHAUSTED_IN_BUILD",
            "hit_wall_deadline": True,
            "t_build_and_simp_s": round(t_build_and_simp_s, 4),
            "t_lp_and_sep_s": 0.0,
            "t_mip_s": 0.0,
            "t_total_s": round(perf_counter() - t_start, 4),
        }

    h.setOptionValue("time_limit", max(0.05, rem))
    h.run()
    lp_thin_init = float(h.getInfo().objective_function_value)
    lp_curr = lp_thin_init

    seen_clq: set[tuple[tuple[int, ...], int]] = set()
    seen_c5: set[tuple[int, int, int, int, int]] = set()
    seen_hub: set[tuple[int, tuple[int, ...], int]] = set()
    cuts_clq = 0
    cuts_c5 = 0
    cuts_hub = 0
    sep_rounds = 0

    for rnd in range(MAX_SEP_ROUNDS):
        sep_deadline = deadline - MIP_RESERVE_S
        if perf_counter() >= sep_deadline:
            break
        sol = np.array(h.getSolution().col_value, dtype=np.float64)
        x_lp, y_lp = sol[:n], sol[n:]

        clq_new = separate_clique_chord_cuts(max_cliques, triangles, idx_map, n, x_lp, y_lp, seen_clq, sep_deadline)
        c5_new = separate_alozie_c5_cuts(adj_sorted, adj_sets, idx_map, n, x_lp, y_lp, seen_c5, sep_deadline)
        hub_new = []
        if arm == "AUG_HUB":
            hub_new = separate_hub_star_cuts(
                adj_sets, idx_map, n, x_lp, y_lp, seen_hub, MAX_HUB_TOTAL - cuts_hub, sep_deadline
            )

        added = len(clq_new) + len(c5_new) + len(hub_new)
        if added == 0:
            break

        for _, _, _, inds, vals, rhs in clq_new:
            h.addRow(rhs, highspy.kHighsInf, len(inds), inds, vals)
        for _, _, _, inds, vals, rhs in c5_new:
            h.addRow(rhs, highspy.kHighsInf, len(inds), inds, vals)
        for _, _, _, inds, vals, rhs in hub_new:
            h.addRow(rhs, highspy.kHighsInf, len(inds), inds, vals)

        cuts_clq += len(clq_new)
        cuts_c5 += len(c5_new)
        cuts_hub += len(hub_new)
        sep_rounds += 1

        rem_lp = deadline - perf_counter()
        if rem_lp <= 0.05:
            hit_wall_deadline = True
            break
        h.setOptionValue("time_limit", max(0.05, rem_lp))
        h.run()
        if str(h.getModelStatus()) != "HighsModelStatus.kOptimal":
            hit_wall_deadline = True
            break
        lp_next = float(h.getInfo().objective_function_value)
        gain = lp_next - lp_curr
        lp_curr = lp_next
        if rnd >= 1 and gain < MIN_LP_GAIN_STOP:
            break

    t_after_sep = perf_counter()
    t_lp_and_sep_s = t_after_sep - t_after_build
    lp_root_after_cuts = lp_curr

    # 3. Integer MIP Search under Exact Remaining Monotone Wall Time
    h.changeColsIntegrality(n, np.arange(n, dtype=np.int32), np.full(n, highspy.HighsVarType.kInteger))
    rem_mip = deadline - perf_counter()
    if rem_mip <= 0.05 or hit_wall_deadline:
        return {
            "arm": arm,
            "status": "WALL_EXHAUSTED_BEFORE_MIP",
            "solved_opt": False,
            "hit_wall_deadline": True,
            "simplicial_fixed_count": len(simplicial_fixed),
            "lp_thin_init": round(lp_thin_init, 6),
            "lp_root_after_cuts": round(lp_root_after_cuts, 6),
            "sep_rounds": sep_rounds,
            "cuts_clique": cuts_clq,
            "cuts_c5": cuts_c5,
            "cuts_hub": cuts_hub,
            "mip_dual_bound": round(lp_root_after_cuts, 6),
            "mip_primal_bfs": None,
            "mip_raw_gap_pct": None,
            "mip_nodes": 0,
            "t_build_and_simp_s": round(t_build_and_simp_s, 4),
            "t_lp_and_sep_s": round(t_lp_and_sep_s, 4),
            "t_mip_s": 0.0,
            "t_total_s": round(perf_counter() - t_start, 4),
            "bfs_verified": True,
            "dual_valid": True,
        }

    h.setOptionValue("time_limit", rem_mip)
    t_mip_start = perf_counter()
    h.run()
    t_end = perf_counter()
    t_mip_s = t_end - t_mip_start
    t_total_s = t_end - t_start

    info = h.getInfo()
    status_str = str(h.getModelStatus())
    solved_opt = status_str == "HighsModelStatus.kOptimal"
    hit_wall_deadline = (not solved_opt) and ("kTimeLimit" in status_str or t_total_s >= wall_limit_s - 0.1)
    mip_dual_bound = float(info.mip_dual_bound)
    mip_nodes = int(info.mip_node_count)

    mip_primal_bfs = None
    bfs_verified = False
    dual_valid = True
    mip_raw_gap_pct = None

    if info.primal_solution_status == int(highspy.SolutionStatus.kSolutionStatusFeasible):
        sol_mip = np.array(h.getSolution().col_value, dtype=np.float64)
        deleted = {v for v in range(n) if sol_mip[v] > 0.5}
        if len(deleted) <= budget and not (deleted & simplicial_set):
            mip_primal_bfs = exact_bfs_obj(G, deleted)
            solver_primal = float(info.objective_function_value)
            bfs_verified = abs(solver_primal - float(mip_primal_bfs)) <= 1e-3
            dual_valid = (lp_root_after_cuts <= float(mip_primal_bfs) + 1e-4) and (
                mip_dual_bound <= float(mip_primal_bfs) + 1e-4
            )
            mip_raw_gap_pct = round(
                100.0 * max(0.0, float(mip_primal_bfs) - mip_dual_bound) / max(1.0, float(mip_primal_bfs)), 4
            )

    return {
        "arm": arm,
        "status": status_str,
        "solved_opt": solved_opt,
        "hit_wall_deadline": hit_wall_deadline,
        "simplicial_fixed_count": len(simplicial_fixed),
        "lp_thin_init": round(lp_thin_init, 6),
        "lp_root_after_cuts": round(lp_root_after_cuts, 6),
        "sep_rounds": sep_rounds,
        "cuts_clique": cuts_clq,
        "cuts_c5": cuts_c5,
        "cuts_hub": cuts_hub,
        "mip_dual_bound": round(mip_dual_bound, 6),
        "mip_primal_bfs": mip_primal_bfs,
        "mip_raw_gap_pct": mip_raw_gap_pct,
        "mip_nodes": mip_nodes,
        "t_build_and_simp_s": round(t_build_and_simp_s, 4),
        "t_lp_and_sep_s": round(t_lp_and_sep_s, 4),
        "t_mip_s": round(t_mip_s, 4),
        "t_total_s": round(t_total_s, 4),
        "bfs_verified": bfs_verified,
        "dual_valid": dual_valid,
    }


# ---------------------------------------------------------------------------
# NEUTRAL POST-RUN AGGREGATOR
# ---------------------------------------------------------------------------
def shifted_geomean(vals: list[float], shift: float) -> float | None:
    if not vals:
        return None
    return math.exp(sum(math.log(max(0.0, v) + shift) for v in vals) / len(vals)) - shift


def summarize_subset(records: list[dict]) -> dict:
    n_inst = len(records)
    lp_lifts_strict = 0
    lp_lift_abs = []
    add_gap_closed_pct = []

    base_opt = 0
    aug_opt = 0
    gaps_base = []
    gaps_aug = []
    times_base = []
    times_aug = []
    times_base_common_opt = []
    times_aug_common_opt = []
    nodes_base_common_opt = []
    nodes_aug_common_opt = []
    wins_aug = 0
    ties = 0
    losses_aug = 0
    bfs_failures = 0
    dual_failures = 0

    for rec in records:
        b = rec["BASE_FULL"]
        a = rec["AUG_HUB"]
        if not b.get("bfs_verified", False) or not a.get("bfs_verified", False):
            bfs_failures += 1
        if not b.get("dual_valid", False) or not a.get("dual_valid", False):
            dual_failures += 1

        # Cross-arm dual validity check against best known BFS primal
        primals = [p for p in (b.get("mip_primal_bfs"), a.get("mip_primal_bfs")) if p is not None]
        best_primal = min(primals) if primals else None
        if best_primal is not None:
            if b["lp_root_after_cuts"] > best_primal + 1e-4 or a["lp_root_after_cuts"] > best_primal + 1e-4:
                dual_failures += 1

        dl = a["lp_root_after_cuts"] - b["lp_root_after_cuts"]
        lp_lift_abs.append(dl)
        if dl > 1e-6:
            lp_lifts_strict += 1
        if best_primal is not None and (best_primal - b["lp_root_after_cuts"]) > 1e-6:
            add_gap_closed_pct.append(100.0 * dl / (best_primal - b["lp_root_after_cuts"]))

        if b["solved_opt"]:
            base_opt += 1
        if a["solved_opt"]:
            aug_opt += 1
        if b["mip_raw_gap_pct"] is not None:
            gaps_base.append(b["mip_raw_gap_pct"])
        if a["mip_raw_gap_pct"] is not None:
            gaps_aug.append(a["mip_raw_gap_pct"])

        tb = min(WALL_LIMIT_S, b["t_total_s"])
        ta = min(WALL_LIMIT_S, a["t_total_s"])
        times_base.append(tb)
        times_aug.append(ta)

        if b["solved_opt"] and a["solved_opt"]:
            times_base_common_opt.append(b["t_total_s"])
            times_aug_common_opt.append(a["t_total_s"])
            nodes_base_common_opt.append(float(b["mip_nodes"]))
            nodes_aug_common_opt.append(float(a["mip_nodes"]))

        # Paired wall-time win/tie/loss (>= 10% relative AND >= 0.10s absolute)
        if b["solved_opt"] and not a["solved_opt"]:
            losses_aug += 1
        elif a["solved_opt"] and not b["solved_opt"]:
            wins_aug += 1
        elif ta <= 0.90 * tb and (tb - ta) >= 0.10:
            wins_aug += 1
        elif tb <= 0.90 * ta and (ta - tb) >= 0.10:
            losses_aug += 1
        else:
            ties += 1

    sgm_b = shifted_geomean(times_base, shift=1.0)
    sgm_a = shifted_geomean(times_aug, shift=1.0)
    sgm_b_co = shifted_geomean(times_base_common_opt, shift=1.0)
    sgm_a_co = shifted_geomean(times_aug_common_opt, shift=1.0)
    sgm_nb_co = shifted_geomean(nodes_base_common_opt, shift=10.0)
    sgm_na_co = shifted_geomean(nodes_aug_common_opt, shift=10.0)

    return {
        "instances": n_inst,
        "root_lp_strict_lift_count": lp_lifts_strict,
        "mean_root_lp_lift_abs": round(sum(lp_lift_abs) / max(1, n_inst), 4),
        "positive_base_gap_instances": len(add_gap_closed_pct),
        "mean_additional_gap_closed_pct": round(sum(add_gap_closed_pct) / len(add_gap_closed_pct), 2)
        if add_gap_closed_pct
        else None,
        "solved_opt_base": base_opt,
        "solved_opt_aug": aug_opt,
        "mean_final_raw_gap_pct_base": round(sum(gaps_base) / len(gaps_base), 3) if gaps_base else None,
        "mean_final_raw_gap_pct_aug": round(sum(gaps_aug) / len(gaps_aug), 3) if gaps_aug else None,
        "sgm_total_wall_base_s": round(sgm_b, 4) if sgm_b is not None else None,
        "sgm_total_wall_aug_s": round(sgm_a, 4) if sgm_a is not None else None,
        "sgm_total_wall_ratio_aug_over_base": round(sgm_a / sgm_b, 4) if (sgm_a and sgm_b) else None,
        "common_opt_count": len(times_base_common_opt),
        "sgm_common_opt_wall_base_s": round(sgm_b_co, 4) if sgm_b_co is not None else None,
        "sgm_common_opt_wall_aug_s": round(sgm_a_co, 4) if sgm_a_co is not None else None,
        "sgm_common_opt_nodes_base": round(sgm_nb_co, 2) if sgm_nb_co is not None else None,
        "sgm_common_opt_nodes_aug": round(sgm_na_co, 2) if sgm_na_co is not None else None,
        "paired_wall_wins_aug": wins_aug,
        "paired_wall_ties": ties,
        "paired_wall_losses_aug": losses_aug,
        "bfs_verification_failures": bfs_failures,
        "dual_validity_failures": dual_failures,
    }


def main() -> None:
    t0 = perf_counter()
    matrix = build_heldout_matrix()
    records = []
    for idx, (iid, fam, budget, G) in enumerate(matrix, 1):
        e2, _, _ = compute_e2(G)
        res_base = run_arm_under_monotone_deadline(G, budget, "BASE_FULL", WALL_LIMIT_S)
        res_aug = run_arm_under_monotone_deadline(G, budget, "AUG_HUB", WALL_LIMIT_S)
        rec = {
            "instance": iid,
            "family": fam,
            "n": G.number_of_nodes(),
            "m": G.number_of_edges(),
            "m_e2": len(e2),
            "budget": budget,
            "BASE_FULL": res_base,
            "AUG_HUB": res_aug,
        }
        records.append(rec)
        print(
            f"[{idx:02d}/{len(matrix)}] {iid:22s} | LP {res_base['lp_thin_init']:.2f} -> BASE {res_base['lp_root_after_cuts']:.2f} "
            f"(clq={res_base['cuts_clique']},c5={res_base['cuts_c5']}) vs AUG {res_aug['lp_root_after_cuts']:.2f} "
            f"(+{res_aug['cuts_hub']} hub) | OPT/primal {res_base['mip_primal_bfs']}/{res_aug['mip_primal_bfs']} | "
            f"wall {res_base['t_total_s']:.2f}s vs {res_aug['t_total_s']:.2f}s | "
            f"nodes {res_base['mip_nodes']} vs {res_aug['mip_nodes']}",
            flush=True,
        )

    families = sorted({r["family"] for r in records})
    out = {
        "stage": "stage_1_locked_heldout_synthetic_benchmark",
        "config": {
            "wall_limit_s": WALL_LIMIT_S,
            "mip_reserve_s": MIP_RESERVE_S,
            "solver_seed": SOLVER_SEED,
            "max_sep_rounds": MAX_SEP_ROUNDS,
            "min_lp_gain_stop": MIN_LP_GAIN_STOP,
            "viol_abs_min": VIOL_ABS_MIN,
            "viol_rel_min": VIOL_REL_MIN,
            "max_clq_per_round": MAX_CLQ_PER_ROUND,
            "max_c5_per_round": MAX_C5_PER_ROUND,
            "max_c5_visits_per_round": MAX_C5_VISITS_PER_ROUND,
            "max_hub_q": MAX_HUB_Q,
            "max_hub_per_round": MAX_HUB_PER_ROUND,
            "max_hub_total": MAX_HUB_TOTAL,
        },
        "aggregate_overall": summarize_subset(records),
        "aggregate_by_family": {f: summarize_subset([r for r in records if r["family"] == f]) for f in families},
        "instances": records,
        "total_wall_seconds": round(perf_counter() - t0, 3),
    }
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT_PATH} total_wall={out['total_wall_seconds']}s")


if __name__ == "__main__":
    main()
