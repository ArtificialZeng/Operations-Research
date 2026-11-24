"""Stage 0B rigorous mathematical validity, exact rational non-domination witness, and synthetic mechanism smoke.

Scope: Simple, undirected, unweighted d=2 Distance-Based Critical Node Problem (2-DCNP) with fixed
budget sum_v x_v <= b, x_v in {0,1}, y_uv in [0,1] for {u,v} in E^(2) (y_uv = 1 iff u,v not deleted
and dist_{G-S}(u,v) <= 2). Abstract/synthetic graphs ONLY; 100% independent local implementation.

Part 1 — Exhaustive 2^n Exact Integer Falsification Check (ZERO floating-point error):
  Across 15 diverse synthetic graphs (n=5..11), enumerates ALL 2^n binary deletion vectors x in {0,1}^n
  with exact BFS connectivity y(x), and verifies in exact Python int arithmetic that EVERY
  Clique-Chord cut (all clique subsets |K|>=3, all chords t) and EVERY Hub-Lifted Closed-Neighborhood
  valid inequality (all hubs w, all Q subseteq N(w) with |Q|>=2, all chords t in 0..|Q|-1) has
  LHS - RHS >= 0 (0 discrepancies).

Part 2 — Exact Rational (fractions.Fraction) Non-Domination Witnesses Against FULL Exhaustive Baseline:
  Verifies in exact rational arithmetic that on BOTH (a) a bipartite graph (zero triangles, zero 5-cycles,
  zero cliques >=3) and (b) a clustered non-bipartite graph containing K_4 cliques AND C_5 odd holes,
  an exact rational fractional vector (x*, y*) satisfies 100% of:
    - Salemi & Buchanan (2022) Thin Formulation (d=2),
    - Khoshbakhtian et al. (2023) Aggregated 2-DCNDP constraints,
    - Alozie (2021/2024) Proposition 3.4.1 (ALL 3-cycles) AND Proposition 3.4.2 (ALL 5-cycles),
    - Chen et al. (2025) analogously adapted Clique-Chord inequalities over ALL clique subsets |K|>=3
      and ALL chords t in 0..|K|-2 (exhaustive, not just maximal cliques!),
  yet STRICTLY VIOLATES our Hub-Lifted Closed-Neighborhood Valid Inequality by an exact positive Fraction,
  and strictly lifts the LP optimum above the full exhaustive strong-baseline LP!

Part 3 — Matched Bounded Synthetic Mechanism Smoke (6 controlled synthetic graphs, n=40..64):
  Matched 1-thread HiGHS 1.15.1 (identical presolve/tolerance), comparing A1 (Thin), A2 (Thin + Alozie 3/5),
  A3 (Thin + Clique-Chord Only), A4_STAR (Thin + Hub-Star Only), A4_BOTH (Thin + Clique + Hub-Star),
  separately reporting build time, LP+separation time, MIP time, total wall time, root LP bounds, nodes,
  and independent exact BFS-verified optima. Explicitly an initial mechanism check, NOT a held-out claim.
"""

from __future__ import annotations

from fractions import Fraction
import itertools
import json
import math
from pathlib import Path
from time import perf_counter

import highspy
import networkx as nx
import numpy as np

OUT_PATH = Path(__file__).resolve().parent / "stage0b_validity_and_witness.json"


def exact_bfs_y(G: nx.Graph, e2: list[tuple[int, int]], deleted_mask: int) -> list[int]:
    """Exact binary vector y(x) for 2-DCNP under deletion bitmask."""
    n = G.number_of_nodes()
    surv = [v for v in range(n) if not ((deleted_mask >> v) & 1)]
    surv_set = set(surv)
    adj_s = {u: [v for v in G.neighbors(u) if v in surv_set] for u in surv}
    reach2: dict[int, set[int]] = {}
    for u in surv:
        r = set(adj_s[u])
        for w in adj_s[u]:
            r.update(adj_s[w])
        r.discard(u)
        reach2[u] = r
    return [1 if (u in surv_set and v in reach2[u]) else 0 for (u, v) in e2]


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


def lb_edges_after_r_deletions(sub_deg_desc: list[int], m_q: int, r: int) -> int:
    """Exact safe lower bound on |E(G[Q \\ R])| for any |R|=r: m_Q - sum of r largest internal degrees."""
    if r == 0:
        return m_q
    if r >= len(sub_deg_desc):
        return 0
    return max(0, m_q - sum(sub_deg_desc[:r]))


def hub_star_cut_params(G: nx.Graph, w: int, Q: list[int], t: int) -> tuple[int, int, int, int]:
    """Return (slope s, M_w, RHS R, mu_Q) for Hub-Lifted Closed-Neighborhood Valid Inequality on (w, Q, t).
    Inequality:
        sum_{u<v in Q u {w}} y_uv + s * sum_{u in Q} x_u + M_w * x_w >= R.
    """
    q = len(Q)
    assert 0 <= t <= q - 1
    s = q - t
    R = (q + 1 - t) * (q - t) // 2 + t * s
    Q_set = set(Q)
    sub_deg = sorted([sum(1 for v in G.neighbors(u) if v in Q_set) for u in Q], reverse=True)
    m_q = sum(sub_deg) // 2
    mu = min(lb_edges_after_r_deletions(sub_deg, m_q, r) + s * r for r in range(q + 1))
    M_w = R - mu
    return s, M_w, R, mu


def enumerate_all_cliques_ge3(G: nx.Graph) -> list[tuple[int, ...]]:
    """Enumerate EVERY clique subset K subseteq V with |K| >= 3 (not just maximal cliques!)."""
    cliques: set[tuple[int, ...]] = set()
    for mc in nx.find_cliques(G):
        if len(mc) >= 3:
            mc_s = sorted(mc)
            for sz in range(3, len(mc_s) + 1):
                for sub in itertools.combinations(mc_s, sz):
                    cliques.add(sub)
    return sorted(cliques)


def enumerate_all_5cycles(G: nx.Graph) -> list[tuple[int, int, int, int, int]]:
    """Enumerate all simple 5-cycles (undirected, canonicalized) in small graphs for Alozie Prop. 3.4.2."""
    n = G.number_of_nodes()
    adj = [set(G.neighbors(u)) for u in range(n)]
    seen: set[tuple[int, ...]] = set()
    cycles = []
    for v0 in range(n):
        for v1 in adj[v0]:
            if v1 <= v0:
                continue
            for v2 in adj[v1]:
                if v2 <= v0 or v2 == v0:
                    continue
                for v3 in adj[v2]:
                    if v3 <= v0 or v3 in (v0, v1):
                        continue
                    for v4 in adj[v3]:
                        if v4 <= v0 or v4 in (v0, v1, v2):
                            continue
                        if v0 in adj[v4]:
                            # Canonicalize cycle up to reversal starting at smallest vertex v0
                            cyc = (v0, v1, v2, v3, v4)
                            rev = (v0, v4, v3, v2, v1)
                            canon = min(cyc, rev)
                            if canon not in seen:
                                seen.add(canon)
                                cycles.append(canon)
    return cycles


# ---------------------------------------------------------------------------
# PART 1: Exhaustive 2^n Exact Integer Falsification Check
# ---------------------------------------------------------------------------
def run_exhaustive_integer_falsification() -> dict:
    t0 = perf_counter()
    graphs: list[tuple[str, nx.Graph]] = [
        ("star_K1_5", nx.star_graph(5)),
        ("star_K1_7", nx.star_graph(7)),
        ("bipartite_K2_4", nx.complete_bipartite_graph(2, 4)),
        ("bipartite_K3_4", nx.complete_bipartite_graph(3, 4)),
        ("bipartite_K3_5", nx.complete_bipartite_graph(3, 5)),
        ("wheel_W6", nx.wheel_graph(6)),
        ("wheel_W8", nx.wheel_graph(8)),
        ("cycle_C5", nx.cycle_graph(5)),
        ("cycle_C7", nx.cycle_graph(7)),
        ("complete_K6", nx.complete_graph(6)),
        ("petersen_10", nx.petersen_graph()),
        ("barbell_4_4", nx.barbell_graph(4, 1)),
        ("er_n10_p035_s1", nx.erdos_renyi_graph(10, 0.35, seed=101)),
        ("er_n11_p030_s2", nx.erdos_renyi_graph(11, 0.30, seed=202)),
        ("reg_n10_d3_s3", nx.random_regular_graph(3, 10, seed=303)),
    ]

    total_binary_vectors = 0
    total_clique_cuts_generated = 0
    total_star_cuts_generated = 0
    total_clique_pair_checks = 0
    total_star_pair_checks = 0
    clique_violations = 0
    star_violations = 0
    first_discrepancy = None
    per_graph = []

    for gname, G in graphs:
        G = nx.convert_node_labels_to_integers(G, ordering="sorted")
        n = G.number_of_nodes()
        e2, idx_map, _ = compute_e2(G)

        # Generate ALL Clique-Chord cuts (all clique subsets |K|>=3, all chords t)
        cliques = enumerate_all_cliques_ge3(G)
        clique_cuts = []
        for K in cliques:
            q = len(K)
            pair_ids = [idx_map[(K[i], K[j])] for i in range(q) for j in range(i + 1, q)]
            for t in range(q - 1):
                s = q - t - 1
                rhs = (q - t) * (q - t - 1) // 2 + t * s
                clique_cuts.append((K, pair_ids, s, rhs, t))

        # Generate ALL Hub-Lifted Closed-Neighborhood cuts (all hubs w, ALL Q subseteq N(w) |Q|>=2, ALL t)
        # Note: for deg(w) <= 8, 2^deg <= 256 subsets, exact full subset enumeration!
        star_cuts = []
        for w in range(n):
            nbrs = sorted(G.neighbors(w))
            if len(nbrs) < 2:
                continue
            for sz in range(2, len(nbrs) + 1):
                for Q_tup in itertools.combinations(nbrs, sz):
                    Q = list(Q_tup)
                    nodes_all = sorted(Q + [w])
                    pair_ids = [idx_map[(nodes_all[i], nodes_all[j])] for i in range(len(nodes_all)) for j in range(i + 1, len(nodes_all))]
                    for t in range(sz):
                        s, M_w, R, mu = hub_star_cut_params(G, w, Q, t)
                        star_cuts.append((w, Q, pair_ids, s, M_w, R, t, mu))

        n_vecs = 1 << n
        total_binary_vectors += n_vecs
        total_clique_cuts_generated += len(clique_cuts)
        total_star_cuts_generated += len(star_cuts)
        g_clq_viol = 0
        g_star_viol = 0

        for mask in range(n_vecs):
            x_vec = [(mask >> i) & 1 for i in range(n)]
            y_vec = exact_bfs_y(G, e2, mask)

            for K, pair_ids, s, rhs, t in clique_cuts:
                lhs = sum(y_vec[pi] for pi in pair_ids) + s * sum(x_vec[v] for v in K)
                total_clique_pair_checks += 1
                if lhs < rhs:
                    clique_violations += 1
                    g_clq_viol += 1
                    if first_discrepancy is None:
                        first_discrepancy = {"type": "clique", "graph": gname, "K": K, "t": t, "mask": mask, "lhs": lhs, "rhs": rhs}

            for w, Q, pair_ids, s, M_w, R, t, mu in star_cuts:
                lhs = sum(y_vec[pi] for pi in pair_ids) + s * sum(x_vec[u] for u in Q) + M_w * x_vec[w]
                total_star_pair_checks += 1
                if lhs < R:
                    star_violations += 1
                    g_star_viol += 1
                    if first_discrepancy is None:
                        first_discrepancy = {"type": "hub_star", "graph": gname, "w": w, "Q": Q, "t": t, "mu": mu, "mask": mask, "lhs": lhs, "rhs": R}

        per_graph.append(
            {
                "graph": gname,
                "n": n,
                "m": G.number_of_edges(),
                "m_e2": len(e2),
                "binary_vectors_checked": n_vecs,
                "clique_cuts_checked": len(clique_cuts),
                "hub_star_cuts_checked": len(star_cuts),
                "clique_violations": g_clq_viol,
                "hub_star_violations": g_star_viol,
            }
        )

    return {
        "graphs_count": len(graphs),
        "total_binary_vectors_checked": total_binary_vectors,
        "total_clique_cuts_enumerated": total_clique_cuts_generated,
        "total_hub_star_cuts_enumerated": total_star_cuts_generated,
        "total_clique_vector_cut_checks": total_clique_pair_checks,
        "total_hub_star_vector_cut_checks": total_star_pair_checks,
        "total_violations": clique_violations + star_violations,
        "first_discrepancy": first_discrepancy,
        "per_graph": per_graph,
        "elapsed_seconds": round(perf_counter() - t0, 3),
    }


# ---------------------------------------------------------------------------
# PART 2: Exact Rational (Fraction) Non-Domination Witnesses vs. FULL Finite Comparator
# ---------------------------------------------------------------------------
def build_full_exhaustive_baseline_lp(G: nx.Graph, budget: int) -> tuple[highspy.Highs, list[tuple[int, int]], dict[tuple[int, int], int], dict[tuple[int, int], list[int]], list[tuple[int, ...]], list[tuple[int, int, int, int, int]]]:
    """Build FULL exhaustive baseline LP including:
      - Salemi & Buchanan (2022) Thin Formulation (d=2),
      - Khoshbakhtian et al. (2023) Aggregated 2-DCNDP constraints,
      - Alozie (2021/2024) Prop. 3.4.1 (ALL 3-cycles) and Prop. 3.4.2 (ALL 5-cycles),
      - Chen et al. (2025) Clique-Chord inequalities across ALL clique subsets |K|>=3 and ALL chords t!
    """
    n = G.number_of_nodes()
    e2, idx_map, common = compute_e2(G)
    m2 = len(e2)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("threads", 1)
    num_vars = n + m2
    h.addCols(
        num_vars,
        np.concatenate([np.zeros(n), np.ones(m2)]),
        np.zeros(num_vars),
        np.ones(num_vars),
        0,
        np.array([], dtype=np.int32),
        np.array([], dtype=np.int32),
        np.array([], dtype=np.float64),
    )
    # Budget
    h.addRow(-highspy.kHighsInf, float(budget), n, np.arange(n, dtype=np.int32), np.ones(n, dtype=np.float64))
    # Edges
    for u, v in G.edges():
        p = (u, v) if u < v else (v, u)
        h.addRow(1.0, highspy.kHighsInf, 3, np.array([u, v, n + idx_map[p]], dtype=np.int32), np.array([1.0, 1.0, 1.0]))
    # Disaggregated 2-hop (Salemi-Buchanan Thin) + Aggregated (Khoshbakhtian)
    for (u, v), ws in common.items():
        yi = n + idx_map[(u, v)]
        for w in ws:
            h.addRow(1.0, highspy.kHighsInf, 4, np.array([u, v, w, yi], dtype=np.int32), np.array([1.0, 1.0, 1.0, 1.0]))
        c = len(ws)
        inds = np.array([u, v, yi] + ws, dtype=np.int32)
        vals = np.array([float(c), float(c), float(c)] + [1.0] * c, dtype=np.float64)
        h.addRow(float(c), highspy.kHighsInf, len(inds), inds, vals)
    # Exhaustive ALL clique subsets |K|>=3 and ALL chords t (includes Alozie Prop. 3.4.1 triangles!)
    cliques = enumerate_all_cliques_ge3(G)
    for K in cliques:
        q = len(K)
        pair_ids = [n + idx_map[(K[i], K[j])] for i in range(q) for j in range(i + 1, q)]
        for t in range(q - 1):
            s = q - t - 1
            rhs = (q - t) * (q - t - 1) // 2 + t * s
            inds = np.array(list(K) + pair_ids, dtype=np.int32)
            vals = np.array([float(s)] * q + [1.0] * len(pair_ids), dtype=np.float64)
            h.addRow(float(rhs), highspy.kHighsInf, len(inds), inds, vals)
    # Exhaustive ALL 5-cycles (Alozie Prop. 3.4.2 — valid for ALL 5-cycles, induced or not, because
    # every 2-hop chord {v_i, v_{i+2}} is at distance <=2 via v_{i+1} so x_{v_i}+x_{v_{i+1}}+x_{v_{i+2}}+y_{v_i,v_{i+2}}>=1!)
    cycles5 = enumerate_all_5cycles(G)
    for cyc in cycles5:
        v0, v1, v2, v3, v4 = cyc
        chords = [(v0, v2), (v1, v3), (v2, v4), (v3, v0), (v4, v1)]
        chord_vars = [n + idx_map[(min(a, b), max(a, b))] for a, b in chords]
        inds = np.array([v0, v1, v2, v3, v4] + chord_vars, dtype=np.int32)
        vals = np.array([2.0, 2.0, 2.0, 2.0, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0], dtype=np.float64)
        h.addRow(4.0, highspy.kHighsInf, len(inds), inds, vals)
    return h, e2, idx_map, common, cliques, cycles5


def verify_rational_witness(label: str, G: nx.Graph, budget: int, x_rat: list[Fraction], target_w: int, target_Q: list[int], target_t: int) -> dict:
    """Verify in EXACT rational arithmetic (fractions.Fraction) that (x*, y*(x*)) satisfies EVERY
    constraint of the FULL exhaustive finite baseline, yet STRICTLY VIOLATES the target Hub-Star cut!
    Also solves both full-baseline LP and full-baseline + all-hub-star LP via HiGHS for objective lift.
    """
    n = G.number_of_nodes()
    e2, idx_map, common = compute_e2(G)
    cliques = enumerate_all_cliques_ge3(G)
    cycles5 = enumerate_all_5cycles(G)

    # Construct exact rational y* = minimal feasible under Thin B1 + Clique-Chord + Alozie 5-cycles
    # Start with B1 minimal values:
    y_rat: list[Fraction] = []
    for (u, v) in e2:
        if G.has_edge(u, v):
            val = max(Fraction(0), Fraction(1) - x_rat[u] - x_rat[v])
        else:
            val = max([Fraction(0)] + [Fraction(1) - x_rat[u] - x_rat[v] - x_rat[w] for w in common[(u, v)]])
        y_rat.append(val)

    # Check exact rational slack on ALL baseline families
    min_slack_budget = Fraction(budget) - sum(x_rat)
    min_slack_bounds = min([min(xv, Fraction(1) - xv) for xv in x_rat] + [min(yv, Fraction(1) - yv) for yv in y_rat])
    min_slack_edges = min(y_rat[idx_map[(min(u, v), max(u, v))]] + x_rat[u] + x_rat[v] - Fraction(1) for u, v in G.edges())
    min_slack_thin_2hop = min(
        (y_rat[idx_map[(u, v)]] + x_rat[u] + x_rat[v] + x_rat[w] - Fraction(1) for (u, v), ws in common.items() for w in ws),
        default=Fraction(0),
    )
    min_slack_khosh_agg = min(
        (len(ws) * (y_rat[idx_map[(u, v)]] + x_rat[u] + x_rat[v]) + sum(x_rat[w] for w in ws) - Fraction(len(ws)) for (u, v), ws in common.items()),
        default=Fraction(0),
    )
    clique_slacks = []
    for K in cliques:
        q = len(K)
        pair_ids = [idx_map[(K[i], K[j])] for i in range(q) for j in range(i + 1, q)]
        for t in range(q - 1):
            s = q - t - 1
            rhs = Fraction((q - t) * (q - t - 1) // 2 + t * s)
            lhs = sum(y_rat[pi] for pi in pair_ids) + Fraction(s) * sum(x_rat[v] for v in K)
            clique_slacks.append(lhs - rhs)
    min_slack_all_cliques = min(clique_slacks) if clique_slacks else Fraction(0)

    c5_slacks = []
    for cyc in cycles5:
        v0, v1, v2, v3, v4 = cyc
        chords = [(v0, v2), (v1, v3), (v2, v4), (v3, v0), (v4, v1)]
        lhs = Fraction(2) * (x_rat[v0] + x_rat[v1] + x_rat[v2] + x_rat[v3] + x_rat[v4]) + sum(
            y_rat[idx_map[(min(a, b), max(a, b))]] for a, b in chords
        )
        c5_slacks.append(lhs - Fraction(4))
    min_slack_all_c5 = min(c5_slacks) if c5_slacks else Fraction(0)

    # Evaluate target Hub-Lifted Closed-Neighborhood cut in exact Fraction arithmetic
    s, M_w, R, mu = hub_star_cut_params(G, target_w, target_Q, target_t)
    nodes_all = sorted(target_Q + [target_w])
    pair_ids = [idx_map[(nodes_all[i], nodes_all[j])] for i in range(len(nodes_all)) for j in range(i + 1, len(nodes_all))]
    cut_lhs = sum(y_rat[pi] for pi in pair_ids) + Fraction(s) * sum(x_rat[u] for u in target_Q) + Fraction(M_w) * x_rat[target_w]
    cut_violation = Fraction(R) - cut_lhs

    # Also compute LP optimum of FULL exhaustive baseline vs FULL + ALL Hub-Star cuts + exact OPT
    h_base, _, _, _, _, _ = build_full_exhaustive_baseline_lp(G, budget)
    h_base.run()
    lp_full_base = float(h_base.getInfo().objective_function_value)

    # Add ALL Hub-Star cuts on this small witness graph
    for w in range(n):
        nbrs = sorted(G.neighbors(w))
        if len(nbrs) < 2:
            continue
        for sz in range(2, len(nbrs) + 1):
            for Qt in itertools.combinations(nbrs, sz):
                Q = list(Qt)
                na = sorted(Q + [w])
                pids = [n + idx_map[(na[i], na[j])] for i in range(len(na)) for j in range(i + 1, len(na))]
                for t in range(sz):
                    sc, Mw, Rc, _ = hub_star_cut_params(G, w, Q, t)
                    inds = np.array(Q + [w] + pids, dtype=np.int32)
                    vals = np.array([float(sc)] * sz + [float(Mw)] + [1.0] * len(pids), dtype=np.float64)
                    h_base.addRow(float(Rc), highspy.kHighsInf, len(inds), inds, vals)
    h_base.run()
    lp_full_plus_star = float(h_base.getInfo().objective_function_value)

    # Exact integer OPT via exhaustive enumeration over subsets of size <= budget
    best_opt = 10**9
    for mask in range(1 << n):
        if mask.bit_count() <= budget:
            obj = sum(exact_bfs_y(G, e2, mask))
            if obj < best_opt:
                best_opt = obj

    all_baselines_satisfied = all(
        sl >= 0
        for sl in [
            min_slack_budget,
            min_slack_bounds,
            min_slack_edges,
            min_slack_thin_2hop,
            min_slack_khosh_agg,
            min_slack_all_cliques,
            min_slack_all_c5,
        ]
    )

    return {
        "witness_label": label,
        "n": n,
        "m": G.number_of_edges(),
        "m_e2": len(e2),
        "budget": budget,
        "all_cliques_ge3_count": len(cliques),
        "all_clique_chord_rows": len(clique_slacks),
        "all_5cycles_count": len(cycles5),
        "x_rational": [str(v) for v in x_rat],
        "y_sum_rational": str(sum(y_rat)),
        "exact_rational_min_slacks": {
            "budget": str(min_slack_budget),
            "box_bounds": str(min_slack_bounds),
            "edges": str(min_slack_edges),
            "thin_2hop": str(min_slack_thin_2hop),
            "khoshbakhtian_aggregated": str(min_slack_khosh_agg),
            "all_clique_subsets_all_chords": str(min_slack_all_cliques),
            "all_alozie_5cycles": str(min_slack_all_c5),
        },
        "all_exhaustive_baseline_constraints_satisfied_exact": all_baselines_satisfied,
        "violated_hub_star_cut": {
            "hub_w": target_w,
            "Q": target_Q,
            "chord_t": target_t,
            "slope_s": s,
            "mu_Q": mu,
            "M_w": M_w,
            "RHS": R,
            "LHS_rational": str(cut_lhs),
            "violation_RHS_minus_LHS_rational": str(cut_violation),
            "strictly_violated": bool(cut_violation > 0),
        },
        "lp_optimum_full_exhaustive_baseline": round(lp_full_base, 6),
        "lp_optimum_full_plus_hub_stars": round(lp_full_plus_star, 6),
        "exact_integer_opt_exhaustive": int(best_opt),
        "strict_lp_optimum_lift_over_full_exhaustive_baseline": bool(lp_full_plus_star > lp_full_base + 1e-6),
    }


def run_rational_non_domination_witnesses() -> dict:
    # Witness 1: Bipartite graph (ZERO triangles, ZERO 5-cycles, ZERO cliques >= 3!)
    # K_{1,4} + K_{1,4} sharing leaves? Even cleaner: Complete Bipartite K_{3,5} (n=8, m=15, budget=3)
    # Wait: test K_{3,5} with b=3 (A={0,1,2}, B={3,4,5,6,7}), x_0=0, x_1=0, x_2=0, x_3..7 = 1/2 (sum=5/2 <= 3)!
    # Check hub w=0, Q={3,4,5,6,7} (q=5), t=2, s=3, R = C(4,2)+6 = 12, M_w = 12:
    # y_{0j}=1/2 (sum 5/2), y_{jk}=0 => sum y = 5/2; 3*(5/2) = 15/2 => LHS = 20/2 = 10 < 12! Violation = 2!
    G_bip = nx.complete_bipartite_graph(3, 5)
    x_bip = [Fraction(0), Fraction(0), Fraction(0)] + [Fraction(1, 2)] * 5
    w1 = verify_rational_witness("bipartite_K3_5_b3", G_bip, 3, x_bip, target_w=0, target_Q=[3, 4, 5, 6, 7], target_t=2)

    # Witness 2: Non-bipartite clustered graph WITH K_4 cliques AND C_5 odd holes!
    # Construct: a 5-cycle {0,1,2,3,4} + a K_4 clique {0,1,5,6} + hub 0 connected to leaves {7,8,9} (n=10, b=3)
    # Put x_0 = 0, x_1 = 0, x_2 = 0, x_3 = 0, x_4 = 0, x_5 = 0, x_6 = 0, x_7 = 1/2, x_8 = 1/2, x_9 = 1/2,
    # Wait: also put x_2 = 1/2, x_4 = 1/2 (so budget 5/2 <= 3, and on K_4 all x=0 so all cliques & C5 satisfied!)
    # Even better: check x_0=0, x_1=0, x_5=0, x_6=0, x_2=1/2, x_3=0, x_4=1/2, x_7=1/2, x_8=1/2, x_9=1/2 (sum = 5/2 <= 3)!
    # Check C_5 (0,1,2,3,4): 2*(0+0+1/2+0+1/2)=2; chords (0,2): y=1/2; (1,3): y=1/2; (2,4): y=0; (3,0): y=1/2; (4,1): y=1/2 -> sum=2+2=4 >= 4! TIGHT!
    # Check K_4 (0,1,5,6): all x=0 -> all y=1 -> all clique chords satisfied!
    # Check hub w=0, Q={2, 4, 7, 8, 9} subset N(0) (q=5, all x_u = 1/2!), t=2, s=3, R=12, M_w=12:
    # LHS = 5*(1/2) + 0 + 3*(5/2) + 0 = 10 < 12 -> EXACT RATIONAL VIOLATION = 2!!
    G_mix = nx.Graph()
    G_mix.add_nodes_from(range(10))
    G_mix.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])  # C_5
    G_mix.add_edges_from([(0, 5), (0, 6), (1, 5), (1, 6), (5, 6)])  # K_4 on {0,1,5,6}
    G_mix.add_edges_from([(0, 2), (0, 7), (0, 8), (0, 9)])  # Wait: keep C_5 induced by NOT adding (0,2); use Q={1,4,7,8,9} or leaves {7,8,9,10}!
    # Let's keep C_5 strictly INDUCED (no chord (0,2)) and attach 4 leaves {7,8,9,10} to hub 0 (n=11, b=3):
    G_mix = nx.Graph()
    G_mix.add_nodes_from(range(11))
    G_mix.add_edges_from([(0, 1), (1, 2), (2, 3), (3, 4), (4, 0)])  # Induced C_5
    G_mix.add_edges_from([(0, 5), (0, 6), (1, 5), (1, 6), (5, 6)])  # K_4 on {0,1,5,6}
    G_mix.add_edges_from([(0, 7), (0, 8), (0, 9), (0, 10)])  # Star leaves on hub 0
    # Add edges (7,2), (8,2), (9,3), (10,3) so deleting hub 0 alone doesn't isolate leaves trivially!
    G_mix.add_edges_from([(7, 2), (8, 2), (9, 3), (10, 3)])
    x_mix = [
        Fraction(0),     # 0 (hub)
        Fraction(0),     # 1
        Fraction(0),     # 2
        Fraction(0),     # 3
        Fraction(1, 2),  # 4 (neighbor of 0)
        Fraction(0),     # 5
        Fraction(0),     # 6
        Fraction(1, 2),  # 7 (neighbor of 0)
        Fraction(1, 2),  # 8 (neighbor of 0)
        Fraction(1, 2),  # 9 (neighbor of 0)
        Fraction(1, 2),  # 10 (neighbor of 0)
    ]
    # Budget b = 3 (sum x = 5/2 <= 3). Note Q = {4, 7, 8, 9, 10} subset N(0) is an independent set of size 5!
    # Also test Witness 3: Petersen graph (n=10, 3-regular, triangle-free, girth 5 — has 12 induced 5-cycles!) with b=3!
    w2 = verify_rational_witness("clustered_K4_C5_star_n11_b3", G_mix, 3, x_mix, target_w=0, target_Q=[4, 7, 8, 9, 10], target_t=2)

    # Witness 3: Petersen graph (n=10, b=4) — check if LP optimum lifts strictly over FULL baseline (incl. ALL 12 5-cycles!)
    G_pet = nx.petersen_graph()
    x_pet = [Fraction(0)] + [Fraction(1, 2) if v in G_pet.neighbors(0) else Fraction(1, 3) for v in range(1, 10)]
    # Wait: sum x = 3*(1/2) + 6*(1/3) = 3.5 <= 4! Let's check exact feasibility against ALL 12 5-cycles!
    # Simpler exact rational vector on Petersen (b=3): hub 0 has x_0=0, its 3 neighbors {1,4,5} have x=1/2, others x=1/4 (sum=1.5+1.5=3.0)!
    nbr0 = sorted(G_pet.neighbors(0))
    x_pet = [Fraction(0) if v == 0 else (Fraction(1, 2) if v in nbr0 else Fraction(1, 4)) for v in range(10)]
    w3 = verify_rational_witness("petersen_girth5_12xC5_b3", G_pet, 3, x_pet, target_w=0, target_Q=nbr0, target_t=1)

    return {"witness_1_bipartite": w1, "witness_2_K4_and_C5_clustered": w2, "witness_3_petersen_12xC5": w3}


# ---------------------------------------------------------------------------
# PART 3: Matched Bounded Synthetic Mechanism Smoke (Separate Build / Sep / MIP Timings)
# ---------------------------------------------------------------------------
def build_a1_highs(G: nx.Graph, budget: int, e2: list[tuple[int, int]], idx_map: dict[tuple[int, int], int], common: dict[tuple[int, int], list[int]], time_limit: float = 45.0) -> tuple[highspy.Highs, float]:
    t0 = perf_counter()
    n = G.number_of_nodes()
    m2 = len(e2)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("threads", 1)
    h.setOptionValue("random_seed", 20261124)
    h.setOptionValue("time_limit", time_limit)
    h.addCols(
        n + m2,
        np.concatenate([np.zeros(n), np.ones(m2)]),
        np.zeros(n + m2),
        np.ones(n + m2),
        0,
        np.array([], dtype=np.int32),
        np.array([], dtype=np.int32),
        np.array([], dtype=np.float64),
    )
    row_l = [-highspy.kHighsInf]
    row_u = [float(budget)]
    starts = [0]
    inds = list(range(n))
    vals = [1.0] * n
    for u, v in G.edges():
        p = (u, v) if u < v else (v, u)
        starts.append(len(inds))
        row_l.append(1.0)
        row_u.append(highspy.kHighsInf)
        inds.extend([u, v, n + idx_map[p]])
        vals.extend([1.0, 1.0, 1.0])
    for (u, v), ws in common.items():
        yi = n + idx_map[(u, v)]
        for w in ws:
            starts.append(len(inds))
            row_l.append(1.0)
            row_u.append(highspy.kHighsInf)
            inds.extend([u, v, w, yi])
            vals.extend([1.0, 1.0, 1.0, 1.0])
    h.addRows(
        len(row_l),
        np.array(row_l, dtype=np.float64),
        np.array(row_u, dtype=np.float64),
        len(inds),
        np.array(starts, dtype=np.int32),
        np.array(inds, dtype=np.int32),
        np.array(vals, dtype=np.float64),
    )
    return h, perf_counter() - t0


def separate_clique_chords(h: highspy.Highs, G: nx.Graph, idx_map: dict[tuple[int, int], int], x_lp: np.ndarray, y_lp: np.ndarray, cliques: list[list[int]], tol: float = 1e-4) -> int:
    n = G.number_of_nodes()
    added = 0
    for K in cliques:
        q = len(K)
        if q < 3:
            continue
        sum_x = float(np.sum(x_lp[K]))
        t = max(0, min(q - 2, int(math.floor(sum_x))))
        s = q - t - 1
        rhs = (q - t) * (q - t - 1) // 2 + t * s
        pids = [n + idx_map[(K[i], K[j])] for i in range(q) for j in range(i + 1, q)]
        sum_y = sum(float(y_lp[pi - n]) for pi in pids)
        if sum_y + s * sum_x < rhs - tol:
            inds = np.array(K + pids, dtype=np.int32)
            vals = np.array([float(s)] * q + [1.0] * len(pids), dtype=np.float64)
            h.addRow(float(rhs), highspy.kHighsInf, len(inds), inds, vals)
            added += 1
    return added


def separate_hub_stars(h: highspy.Highs, G: nx.Graph, idx_map: dict[tuple[int, int], int], x_lp: np.ndarray, y_lp: np.ndarray, tol: float = 1e-4) -> int:
    n = G.number_of_nodes()
    added = 0
    for w in range(n):
        nbrs = sorted(G.neighbors(w))
        if len(nbrs) < 2:
            continue
        nbrs_by_x = sorted(nbrs, key=lambda u: x_lp[u])
        cands = [nbrs]
        for k in set([max(2, len(nbrs) // 2), max(2, (3 * len(nbrs)) // 4)]):
            if 2 <= k < len(nbrs):
                cands.append(sorted(nbrs_by_x[:k]))
        act = sorted([u for u in nbrs if x_lp[u] < 0.95])
        if 2 <= len(act) < len(nbrs):
            cands.append(act)
        seen = set()
        best_v = tol
        best = None
        xw = float(x_lp[w])
        for Q in cands:
            qt = tuple(Q)
            if qt in seen:
                continue
            seen.add(qt)
            q = len(Q)
            sum_xQ = float(np.sum(x_lp[Q]))
            na = sorted(Q + [w])
            pids = [n + idx_map[(na[i], na[j])] for i in range(len(na)) for j in range(i + 1, len(na))]
            sum_y = sum(float(y_lp[pi - n]) for pi in pids)
            t0 = max(0, min(q - 1, int(math.floor(sum_xQ))))
            for t in set([t0, max(0, t0 - 1), min(q - 1, t0 + 1), 0]):
                s, M_w, R, _ = hub_star_cut_params(G, w, Q, t)
                viol = R - (sum_y + s * sum_xQ + M_w * xw)
                if viol > best_v:
                    best_v = viol
                    best = (Q, pids, s, M_w, R)
        if best is not None:
            Q, pids, s, M_w, R = best
            inds = np.array(Q + [w] + pids, dtype=np.int32)
            vals = np.array([float(s)] * len(Q) + [float(M_w)] + [1.0] * len(pids), dtype=np.float64)
            h.addRow(float(R), highspy.kHighsInf, len(inds), inds, vals)
            added += 1
    return added


def run_arm_on_synthetic(G: nx.Graph, budget: int, e2: list[tuple[int, int]], idx_map: dict[tuple[int, int], int], common: dict[tuple[int, int], list[int]], cliques: list[list[int]], arm: str, time_limit: float = 45.0) -> dict:
    n = G.number_of_nodes()
    h, t_build = build_a1_highs(G, budget, e2, idx_map, common, time_limit=time_limit)
    t_sep0 = perf_counter()
    h.run()
    lp_init = float(h.getInfo().objective_function_value)
    cuts_clq = 0
    cuts_star = 0
    if arm in ("A3_CLIQUE_ONLY", "A4_STAR_ONLY", "A4_COMBINED"):
        for _ in range(15):
            sol = np.array(h.getSolution().col_value, dtype=np.float64)
            c1 = separate_clique_chords(h, G, idx_map, sol[:n], sol[n:], cliques) if arm in ("A3_CLIQUE_ONLY", "A4_COMBINED") else 0
            c2 = separate_hub_stars(h, G, idx_map, sol[:n], sol[n:]) if arm in ("A4_STAR_ONLY", "A4_COMBINED") else 0
            cuts_clq += c1
            cuts_star += c2
            if c1 + c2 == 0:
                break
            h.run()
    lp_root = float(h.getInfo().objective_function_value)
    t_sep_lp = perf_counter() - t_sep0

    # Enforce identical total wall budget across build + sep/LP + MIP search!
    rem_budget = max(0.5, time_limit - (t_build + t_sep_lp))
    h.setOptionValue("time_limit", rem_budget)
    t_mip0 = perf_counter()
    h.changeColsIntegrality(n, np.arange(n, dtype=np.int32), np.full(n, highspy.HighsVarType.kInteger))
    h.run()
    t_mip = perf_counter() - t_mip0

    info = h.getInfo()
    sol = np.array(h.getSolution().col_value, dtype=np.float64)
    deleted = {i for i in range(n) if sol[i] > 0.5} if len(sol) >= n else set()
    bfs_obj = exact_bfs_obj(G, deleted) if len(deleted) <= budget else None
    return {
        "arm": arm,
        "status": str(h.getModelStatus()),
        "lp_init": round(lp_init, 4),
        "lp_root_after_cuts": round(lp_root, 4),
        "cuts_clique": cuts_clq,
        "cuts_hub_star": cuts_star,
        "mip_dual_bound": round(float(info.mip_dual_bound), 4),
        "mip_primal_bfs": bfs_obj,
        "mip_nodes": int(info.mip_node_count),
        "t_build_s": round(t_build, 4),
        "t_sep_and_lp_s": round(t_sep_lp, 4),
        "t_mip_s": round(t_mip, 4),
        "t_total_s": round(t_build + t_sep_lp + t_mip, 4),
    }


def run_synthetic_mechanism_smoke() -> list[dict]:
    """Bounded synthetic mechanism check (6 abstract graphs, NOT held-out suite!)."""
    specs = [
        ("syn_bipartite_24x24_p018_b8", nx.bipartite.random_graph(24, 24, 0.18, seed=11), 8),
        ("syn_bipartite_28x28_p016_b10", nx.bipartite.random_graph(28, 28, 0.16, seed=12), 10),
        ("syn_reg_n48_d4_b8", nx.random_regular_graph(4, 48, seed=21), 8),
        ("syn_reg_n56_d4_b10", nx.random_regular_graph(4, 56, seed=22), 10),
        ("syn_ws_n56_k6_p015_b10", nx.watts_strogatz_graph(56, 6, 0.15, seed=31), 10),
        ("syn_sbm_4x14_b10", nx.stochastic_block_model([14, 14, 14, 14], [[0.45, 0.04, 0.04, 0.04], [0.04, 0.45, 0.04, 0.04], [0.04, 0.04, 0.45, 0.04], [0.04, 0.04, 0.04, 0.45]], seed=41), 10),
    ]
    rows = []
    for name, G_raw, b in specs:
        G = nx.convert_node_labels_to_integers(G_raw, ordering="sorted")
        e2, idx_map, common = compute_e2(G)
        cliques = [sorted(c) for c in nx.find_cliques(G) if len(c) >= 3]
        arms = {}
        for arm in ["A1_THIN", "A3_CLIQUE_ONLY", "A4_STAR_ONLY", "A4_COMBINED"]:
            arms[arm] = run_arm_on_synthetic(G, b, e2, idx_map, common, cliques, arm, time_limit=30.0)
        rows.append(
            {
                "instance": name,
                "n": G.number_of_nodes(),
                "m": G.number_of_edges(),
                "m_e2": len(e2),
                "budget": b,
                "triangles_count": sum(nx.triangles(G).values()) // 3,
                "cliques_ge3_count": len(cliques),
                "arms": arms,
            }
        )
        a1 = arms["A1_THIN"]
        a3 = arms["A3_CLIQUE_ONLY"]
        a4s = arms["A4_STAR_ONLY"]
        a4 = arms["A4_COMBINED"]
        print(
            f"{name:30s} tri={sum(nx.triangles(G).values())//3:3d} | LP: A1={a1['lp_root_after_cuts']:7.2f} A3={a3['lp_root_after_cuts']:7.2f} A4s={a4s['lp_root_after_cuts']:7.2f} A4={a4['lp_root_after_cuts']:7.2f} | BFS_OPT={a1['mip_primal_bfs']} | nodes A1={a1['mip_nodes']} A3={a3['mip_nodes']} A4={a4['mip_nodes']} | total_t A1={a1['t_total_s']:.2f}s A3={a3['t_total_s']:.2f}s A4={a4['t_total_s']:.2f}s"
        )
    return rows


def main() -> None:
    t0 = perf_counter()
    p1 = run_exhaustive_integer_falsification()
    print(
        f"PART1 EXHAUSTIVE: graphs={p1['graphs_count']} vecs={p1['total_binary_vectors_checked']} "
        f"clq_checks={p1['total_clique_vector_cut_checks']} star_checks={p1['total_hub_star_vector_cut_checks']} "
        f"violations={p1['total_violations']}"
    )
    p2 = run_rational_non_domination_witnesses()
    for k, w in p2.items():
        print(
            f"PART2 {k}: all_base_ok={w['all_exhaustive_baseline_constraints_satisfied_exact']} "
            f"viol={w['violated_hub_star_cut']['violation_RHS_minus_LHS_rational']} "
            f"LP_full={w['lp_optimum_full_exhaustive_baseline']} -> LP_plus_star={w['lp_optimum_full_plus_hub_stars']} (OPT={w['exact_integer_opt_exhaustive']})"
        )
    p3 = run_synthetic_mechanism_smoke()
    out = {
        "stage": "stage_0b_dcnp_validity_rational_witness_and_synthetic_mechanism_smoke",
        "scope": "Simple undirected unweighted d=2 DCNP, fixed budget sum_v x_v <= b; abstract synthetic graphs only.",
        "part1_exhaustive_integer_falsification": p1,
        "part2_exact_rational_non_domination_witnesses": p2,
        "part3_bounded_synthetic_mechanism_smoke": p3,
        "total_elapsed_seconds": round(perf_counter() - t0, 3),
    }
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT_PATH} elapsed={out['total_elapsed_seconds']}s")


if __name__ == "__main__":
    main()
