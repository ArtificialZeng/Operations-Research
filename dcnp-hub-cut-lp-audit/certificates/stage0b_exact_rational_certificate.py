"""Exact rational (fractions.Fraction) Primal + Dual LP certificates for 2-DCNP Hub-Lifted cuts.

ZERO floating-point reliance in any certificate verification step:
  1. Witness A — Heawood graph (n=14, 3-regular bipartite, girth 6, b=4):
     - Exact rational Baseline LP Primal (both the existing Stage 0B primal AND symmetric x=2/7) -> z*_base <= 15
     - Exact nonnegative rational Baseline LP Dual -> z*_base >= 15  ==>  z*_base = 15 (exact)
     - Exact nonnegative rational Augmented LP Dual (using Hub-Lifted N[w] cuts t=1 + Thin 2-hop + Budget)
       -> z*_aug >= 16
     - Exact rational Augmented LP Primal (x=2/7, y_e=10/21, y_p=1/7) verified feasible against ALL
       baseline constraints AND ALL 126 exhaustive Hub-Lifted cuts (all hubs, all Q subseteq N(w) |Q|>=2, all t)
       -> z*_aug <= 16  ==>  z*_aug = 16 (exact)
     - Exact integer optimum z*_IP = 17 certified by exhaustive enumeration of all sum_{k<=4} C(14,k) = 1,471
       feasible binary deletion vectors with exact BFS.
  2. Witness B — Non-bipartite 4-regular graph reg_n12_d4_b3 (n=12, b=3, 3 triangles / 6 clique-chord rows,
     31 Alozie C_5 rows):
     - Exact rational Primal + exact nonnegative rational Dual for FULL exhaustive Baseline LP -> z*_base = 227/10
     - Exact nonnegative rational Dual + exact rational Primal for Augmented LP -> z*_aug = 23
     - Exact integer optimum z*_IP = 25 certified by exhaustive enumeration of all 299 feasible binary vectors.
  3. Infinite Graph-Family Consequence Verification (d-regular graphs of girth >= 6, n/(d+1) < b <= n/3):
     - Closed-form exact rational Primal & Dual verification on Heawood (n=14, d=3, b=4),
       Tutte-Coxeter / Levi graph of W(2) (n=30, d=3, b=9 and b=10), and Projective-Plane Levi graph
       PG(2,3) (n=26, d=4, b=6 and b=8).
  4. Mutual Non-Implication Boundary Verification:
     - C_5 (n=5, b=1): verifies Alozie C_5 strictly cuts a point feasible for Thin + ALL Hub-Star cuts.
     - K_5 (n=5, b=2): verifies Chen Clique-Chord strictly cuts a point feasible for Thin + ALL L_Q-based Hub-Star cuts.
  5. Exhaustive Simplicial Independent-Set Fixing Verification:
     - Verifies across all 15 Part-1 synthetic graphs and every budget b in 0..n that fixing a greedy
       independent set F of simplicial vertices to x_v = 0 preserves the exact integer optimum (0 discrepancies).
"""

from __future__ import annotations

from fractions import Fraction
import itertools
import json
from pathlib import Path
from time import perf_counter

import highspy
import networkx as nx
import numpy as np

from stage0b_validity_and_witness import (
    build_full_exhaustive_baseline_lp,
    compute_e2,
    enumerate_all_5cycles,
    enumerate_all_cliques_ge3,
    exact_bfs_obj,
    hub_star_cut_params,
)

OUT_PATH = Path(__file__).resolve().parent / "stage0b_exact_rational_certificate.json"


def build_explicit_rational_constraints(
    G: nx.Graph, budget: int, include_hub_mode: str = "none"
) -> tuple[list[tuple[int, int]], dict[tuple[int, int], int], list[dict]]:
    """Return all linear constraints in standard >= form:
         sum_{j} a_j * var_j >= rhs
       with exact integer/Fraction coefficients.
       Variables: 0..n-1 are x_v; n..n+m2-1 are y_p for p in e2.
       Note: upper bounds x_v <= 1, y_p <= 1 are written as -var_j >= -1;
             budget sum x_v <= b is written as -sum x_v >= -b.
             Lower bounds var_j >= 0 are implicit (standard LP min c^T z s.t. A z >= rhs, z >= 0).
    """
    n = G.number_of_nodes()
    e2, idx_map, common = compute_e2(G)
    m2 = len(e2)
    rows: list[dict] = []

    # Budget: -sum x_v >= -b
    rows.append({
        "name": "budget",
        "family": "budget",
        "coeffs": {v: Fraction(-1) for v in range(n)},
        "rhs": Fraction(-budget),
    })

    # Upper bounds: -x_v >= -1, -y_p >= -1
    for v in range(n):
        rows.append({"name": f"ub_x_{v}", "family": "ub_x", "coeffs": {v: Fraction(-1)}, "rhs": Fraction(-1)})
    for i in range(m2):
        rows.append({"name": f"ub_y_{i}", "family": "ub_y", "coeffs": {n + i: Fraction(-1)}, "rhs": Fraction(-1)})

    # Edges: x_u + x_v + y_uv >= 1
    for u, v in sorted(G.edges()):
        p = (u, v) if u < v else (v, u)
        rows.append({
            "name": f"edge_{p[0]}_{p[1]}",
            "family": "edge",
            "coeffs": {u: Fraction(1), v: Fraction(1), n + idx_map[p]: Fraction(1)},
            "rhs": Fraction(1),
        })

    # Salemi-Buchanan Thin 2-hop & Khoshbakhtian Aggregated
    for (u, v), ws in sorted(common.items()):
        yi = n + idx_map[(u, v)]
        for w in ws:
            rows.append({
                "name": f"thin_{u}_{v}_via_{w}",
                "family": "thin_2hop",
                "coeffs": {u: Fraction(1), v: Fraction(1), w: Fraction(1), yi: Fraction(1)},
                "rhs": Fraction(1),
            })
        c = len(ws)
        agg = {u: Fraction(c), v: Fraction(c), yi: Fraction(c)}
        for w in ws:
            agg[w] = Fraction(1)
        rows.append({
            "name": f"khosh_{u}_{v}",
            "family": "khosh_agg",
            "coeffs": agg,
            "rhs": Fraction(c),
        })

    # Exhaustive ALL Chen-adapted Clique-Chord rows (|K|>=3, all chords t; includes Alozie Prop. 3.4.1 K_3)
    for K in enumerate_all_cliques_ge3(G):
        q = len(K)
        pids = [n + idx_map[(K[i], K[j])] for i in range(q) for j in range(i + 1, q)]
        for t in range(q - 1):
            s = q - t - 1
            rhs = (q - t) * (q - t - 1) // 2 + t * s
            coeffs = {v: Fraction(s) for v in K}
            for pi in pids:
                coeffs[pi] = Fraction(1)
            rows.append({
                "name": f"clique_{'_'.join(map(str, K))}_t{t}",
                "family": "clique_chord",
                "coeffs": coeffs,
                "rhs": Fraction(rhs),
            })

    # Exhaustive ALL Alozie Prop. 3.4.2 5-cycles
    for idx_c, cyc in enumerate(enumerate_all_5cycles(G)):
        v0, v1, v2, v3, v4 = cyc
        chords = [(v0, v2), (v1, v3), (v2, v4), (v3, v0), (v4, v1)]
        coeffs = {v0: Fraction(2), v1: Fraction(2), v2: Fraction(2), v3: Fraction(2), v4: Fraction(2)}
        for a, b in chords:
            pi = n + idx_map[(min(a, b), max(a, b))]
            coeffs[pi] = coeffs.get(pi, Fraction(0)) + Fraction(1)
        rows.append({
            "name": f"alozie_c5_{idx_c}_{'_'.join(map(str, cyc))}",
            "family": "alozie_c5",
            "coeffs": coeffs,
            "rhs": Fraction(4),
        })

    # Hub-Lifted Closed-Neighborhood cuts
    if include_hub_mode in ("full_nbr", "all_subsets"):
        for w in range(n):
            nbrs = sorted(G.neighbors(w))
            if len(nbrs) < 2:
                continue
            if include_hub_mode == "full_nbr":
                q_list = [nbrs]
            else:
                q_list = [list(Q) for sz in range(2, len(nbrs) + 1) for Q in itertools.combinations(nbrs, sz)]
            for Q in q_list:
                na = sorted(Q + [w])
                pids = [n + idx_map[(na[i], na[j])] for i in range(len(na)) for j in range(i + 1, len(na))]
                for t in range(len(Q)):
                    s, Mw, R, mu = hub_star_cut_params(G, w, Q, t)
                    coeffs = {u: Fraction(s) for u in Q}
                    coeffs[w] = Fraction(Mw)
                    for pi in pids:
                        coeffs[pi] = Fraction(1)
                    rows.append({
                        "name": f"hub_w{w}_Q{'_'.join(map(str, Q))}_t{t}",
                        "family": "hub_star",
                        "coeffs": coeffs,
                        "rhs": Fraction(R),
                        "meta": {"w": w, "Q": Q, "t": t, "s": s, "mu_Q": mu, "M_w": Mw, "R": R},
                    })
    return e2, idx_map, rows


def verify_primal_exact(
    n: int, m2: int, rows: list[dict], z_vec: list[Fraction]
) -> dict:
    """Pure Fraction check of primal feasibility z >= 0, A z >= rhs, and exact objective sum y."""
    assert len(z_vec) == n + m2
    min_nonneg = min(z_vec)
    min_slack_by_family: dict[str, Fraction] = {}
    overall_min_slack = min_nonneg
    first_viol = None
    for row in rows:
        lhs = sum(coef * z_vec[j] for j, coef in row["coeffs"].items())
        slack = lhs - row["rhs"]
        fam = row["family"]
        if fam not in min_slack_by_family or slack < min_slack_by_family[fam]:
            min_slack_by_family[fam] = slack
        if slack < overall_min_slack:
            overall_min_slack = slack
        if slack < 0 and first_viol is None:
            first_viol = {"row": row["name"], "family": fam, "slack": str(slack)}
    obj = sum(z_vec[n:])
    return {
        "feasible_exact": (min_nonneg >= 0) and (first_viol is None),
        "exact_obj": str(obj),
        "min_var_value": str(min_nonneg),
        "min_slack_by_family": {k: str(v) for k, v in sorted(min_slack_by_family.items())},
        "first_violation": first_viol,
    }


def verify_dual_exact(
    n: int, m2: int, rows: list[dict], dual_by_name: dict[str, Fraction]
) -> dict:
    """Pure Fraction check of LP dual feasibility for min c^T z s.t. A z >= rhs, z >= 0:
       Dual is max rhs^T lam s.t. A^T lam <= c, lam >= 0.
       Here c_j = 0 for j < n (x vars), c_j = 1 for j >= n (y vars).
    """
    row_by_name = {r["name"]: r for r in rows}
    lam_nonneg = True
    min_lam = Fraction(0)
    col_sum = [Fraction(0)] * (n + m2)
    dual_obj = Fraction(0)
    active_families: dict[str, int] = {}

    for rname, lam in dual_by_name.items():
        if lam < min_lam:
            min_lam = lam
        if lam < 0:
            lam_nonneg = False
        if lam == 0:
            continue
        row = row_by_name[rname]
        fam = row["family"]
        active_families[fam] = active_families.get(fam, 0) + 1
        dual_obj += lam * row["rhs"]
        for j, coef in row["coeffs"].items():
            col_sum[j] += lam * coef

    c_vec = [Fraction(0)] * n + [Fraction(1)] * m2
    # Reduced cost slacks: c_j - (A^T lam)_j >= 0
    rc_x = [c_vec[j] - col_sum[j] for j in range(n)]
    rc_y = [c_vec[j] - col_sum[j] for j in range(n, n + m2)]
    min_rc_x = min(rc_x)
    min_rc_y = min(rc_y)
    feasible = lam_nonneg and (min_rc_x >= 0) and (min_rc_y >= 0)
    return {
        "dual_feasible_exact": feasible,
        "exact_dual_lower_bound": str(dual_obj),
        "min_multiplier": str(min_lam),
        "min_reduced_cost_x": str(min_rc_x),
        "min_reduced_cost_y": str(min_rc_y),
        "nonzero_dual_rows_count": sum(active_families.values()),
        "nonzero_dual_rows_by_family": dict(sorted(active_families.items())),
    }


def solve_and_snap_exact_primal_dual(
    G: nx.Graph, budget: int, include_hub_mode: str, max_denom: int = 240
) -> tuple[list[Fraction], dict[str, Fraction], list[dict], list[tuple[int, int]]]:
    """Use HiGHS ONLY as an oracle to discover a candidate rational primal & dual;
    correctness is certified 100% independently in pure Fraction arithmetic afterwards."""
    n = G.number_of_nodes()
    e2, idx_map, rows = build_explicit_rational_constraints(G, budget, include_hub_mode=include_hub_mode)
    m2 = len(e2)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.setOptionValue("threads", 1)
    h.setOptionValue("presolve", "off")  # keeps exact unpresolved simplex duals clean
    h.addCols(
        n + m2,
        np.concatenate([np.zeros(n), np.ones(m2)]),
        np.zeros(n + m2),
        np.full(n + m2, highspy.kHighsInf),  # explicit <=1 rows already included
        0,
        np.array([], dtype=np.int32),
        np.array([], dtype=np.int32),
        np.array([], dtype=np.float64),
    )
    for r in rows:
        inds = np.array(list(r["coeffs"].keys()), dtype=np.int32)
        vals = np.array([float(v) for v in r["coeffs"].values()], dtype=np.float64)
        h.addRow(float(r["rhs"]), highspy.kHighsInf, len(inds), inds, vals)
    h.run()
    sol = h.getSolution()
    z_rat = [Fraction(float(v)).limit_denominator(max_denom) for v in sol.col_value]
    dual_rat: dict[str, Fraction] = {}
    for r, dval in zip(rows, sol.row_dual):
        if dval > 1e-10:
            frac = Fraction(float(dval)).limit_denominator(max_denom)
            if frac > 0:
                dual_rat[r["name"]] = frac
    return z_rat, dual_rat, rows, e2


def exhaustive_ip_opt(G: nx.Graph, budget: int) -> tuple[int, int, list[int]]:
    """Exact IP optimum by brute-force enumeration of ALL subsets of size <= budget (exact BFS)."""
    n = G.number_of_nodes()
    best_obj = 10**18
    best_S: list[int] = []
    checked = 0
    for k in range(budget + 1):
        for comb in itertools.combinations(range(n), k):
            checked += 1
            obj = exact_bfs_obj(G, set(comb))
            if obj < best_obj:
                best_obj = obj
                best_S = list(comb)
    return best_obj, checked, best_S


def certify_d_regular_girth6_instance(label: str, G: nx.Graph, d: int, budget: int, verify_all_subsets: bool = False) -> dict:
    """Closed-form exact rational Primal + Dual certificate for any d-regular graph of girth >= 6
    with n/(d+1) < b <= n/3 (no HiGHS needed at all!)."""
    G = nx.convert_node_labels_to_integers(G, ordering="sorted")
    n = G.number_of_nodes()
    degs = sorted(set(dict(G.degree()).values()))
    girth = nx.girth(G)
    assert degs == [d], f"Expected {d}-regular, got {degs}"
    assert girth >= 6, f"Expected girth >= 6, got {girth}"
    assert Fraction(budget, n) > Fraction(1, d + 1) and Fraction(budget, n) <= Fraction(1, 3)

    alpha = Fraction(budget, n)
    hub_mode = "all_subsets" if verify_all_subsets else "full_nbr"
    e2, idx_map, rows_base = build_explicit_rational_constraints(G, budget, include_hub_mode="none")
    _, _, rows_aug = build_explicit_rational_constraints(G, budget, include_hub_mode=hub_mode)
    m2 = len(e2)
    edge_set = {(min(u, v), max(u, v)) for u, v in G.edges()}

    # 1. Baseline uniform exact rational primal: x_v = alpha, y_e = 1 - 2*alpha, y_p = 1 - 3*alpha
    z_base_primal = [alpha] * n + [
        (Fraction(1) - 2 * alpha) if p in edge_set else (Fraction(1) - 3 * alpha) for p in e2
    ]
    chk_base_primal = verify_primal_exact(n, m2, rows_base, z_base_primal)

    # 2. Baseline exact nonnegative dual: lam_edge = 1, lam_2hop = 1, lam_budget = d(3d-1)/2
    dual_base: dict[str, Fraction] = {"budget": Fraction(d * (3 * d - 1), 2)}
    for r in rows_base:
        if r["family"] in ("edge", "thin_2hop"):
            dual_base[r["name"]] = Fraction(1)
    chk_base_dual = verify_dual_exact(n, m2, rows_base, dual_base)

    # 3. Augmented exact nonnegative dual: lam_star(w, N(w), t=1) = 1/2, lam_2hop = 1/2, lam_budget = (d-1)(3d+1)/2
    dual_aug: dict[str, Fraction] = {"budget": Fraction((d - 1) * (3 * d + 1), 2)}
    for r in rows_aug:
        if r["family"] == "thin_2hop":
            dual_aug[r["name"]] = Fraction(1, 2)
        elif r["family"] == "hub_star" and r["meta"]["t"] == 1 and len(r["meta"]["Q"]) == d:
            dual_aug[r["name"]] = Fraction(1, 2)
    chk_aug_dual = verify_dual_exact(n, m2, rows_aug, dual_aug)

    # 4. Augmented uniform exact rational primal (exact optimum whenever alpha <= 2/(d+2)):
    #    x_v = alpha, y_e = ((d-1)/d)*(1 - alpha), y_p = 1 - 3*alpha
    z_aug_primal = [alpha] * n + [
        (Fraction(d - 1, d) * (Fraction(1) - alpha)) if p in edge_set else (Fraction(1) - 3 * alpha)
        for p in e2
    ]
    chk_aug_primal = verify_primal_exact(n, m2, rows_aug, z_aug_primal)

    formula_base = Fraction(n * d * d, 2) - Fraction(d * (3 * d - 1), 2) * budget
    formula_aug_lb = Fraction(n * (d * d - 1), 2) - Fraction((d - 1) * (3 * d + 1), 2) * budget
    formula_lift = Fraction((d + 1) * budget - n, 2)

    assert chk_base_primal["feasible_exact"] and chk_base_dual["dual_feasible_exact"]
    assert Fraction(chk_base_primal["exact_obj"]) == formula_base
    assert Fraction(chk_base_dual["exact_dual_lower_bound"]) == formula_base
    assert chk_aug_dual["dual_feasible_exact"]
    assert Fraction(chk_aug_dual["exact_dual_lower_bound"]) == formula_aug_lb
    assert formula_aug_lb - formula_base == formula_lift and formula_lift > 0

    return {
        "label": label,
        "n": n,
        "d": d,
        "girth": girth,
        "m": G.number_of_edges(),
        "m_e2": m2,
        "budget": budget,
        "alpha": str(alpha),
        "cliques_ge3_count": 0,
        "alozie_5cycles_count": 0,
        "hub_rows_checked": sum(1 for r in rows_aug if r["family"] == "hub_star"),
        "hub_mode_checked": hub_mode,
        "exact_z_base": str(formula_base),
        "exact_z_aug_dual_lb": str(formula_aug_lb),
        "exact_strict_lift_lb": str(formula_lift),
        "baseline_primal_check": chk_base_primal,
        "baseline_dual_check": chk_base_dual,
        "augmented_dual_check": chk_aug_dual,
        "augmented_uniform_primal_check": chk_aug_primal,
        "exact_z_aug_pinned_equality": chk_aug_primal["feasible_exact"]
        and (Fraction(chk_aug_primal["exact_obj"]) == formula_aug_lb),
    }


def build_pg2_levi_graph(q: int) -> nx.Graph:
    """Incidence (Levi) graph of projective plane PG(2, q) over prime field GF(q):
    d = q + 1 regular bipartite graph of girth 6 with n = 2(q^2 + q + 1) vertices."""
    # Points = 1D subspaces of GF(q)^3; lines = 1D subspaces of dual GF(q)^3
    def canonical_vec(a: int, b: int, c: int) -> tuple[int, int, int]:
        for x in (a, b, c):
            if x != 0:
                inv = pow(x, -1, q)
                return ((a * inv) % q, (b * inv) % q, (c * inv) % q)
        raise ValueError

    pts = sorted({canonical_vec(a, b, c) for a in range(q) for b in range(q) for c in range(q) if (a, b, c) != (0, 0, 0)})
    m = len(pts)
    G = nx.Graph()
    G.add_nodes_from(range(2 * m))
    for i, p in enumerate(pts):
        for j, l in enumerate(pts):
            if (p[0] * l[0] + p[1] * l[1] + p[2] * l[2]) % q == 0:
                G.add_edge(i, m + j)
    return G


def greedy_independent_simplicial_set(G: nx.Graph) -> list[int]:
    """Deterministic greedy independent set F of simplicial vertices (x_v = 0 is valid for ALL G and b)."""
    n = G.number_of_nodes()
    adj = [set(G.neighbors(u)) for u in range(n)]
    fixed: set[int] = set()
    for v in range(n):
        nbrs = list(adj[v])
        # Check if N(v) is a clique (empty or size 1 is trivially a clique)
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


def verify_simplicial_fixing_exhaustive() -> dict:
    """Exhaustively check independent-set simplicial fixing across all 15 Part-1 graphs & ALL budgets b=0..n."""
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
    total_graph_budget_pairs = 0
    total_fixed_vertices = 0
    discrepancies = 0
    first_discrepancy = None
    for gname, G in graphs:
        G = nx.convert_node_labels_to_integers(G, ordering="sorted")
        n = G.number_of_nodes()
        F = set(greedy_independent_simplicial_set(G))
        total_fixed_vertices += len(F)
        # Compute exact min obj for each cardinality k=0..n both unrestricted and with S cap F = empty
        best_all = [10**18] * (n + 1)
        best_fix = [10**18] * (n + 1)
        for mask in range(1 << n):
            S = {v for v in range(n) if (mask >> v) & 1}
            k = len(S)
            obj = exact_bfs_obj(G, S)
            if obj < best_all[k]:
                best_all[k] = obj
            if not (S & F) and obj < best_fix[k]:
                best_fix[k] = obj
        # Cumulative min over |S| <= b
        cur_all = 10**18
        cur_fix = 10**18
        for b in range(n + 1):
            total_graph_budget_pairs += 1
            cur_all = min(cur_all, best_all[b])
            cur_fix = min(cur_fix, best_fix[b])
            if cur_fix != cur_all:
                discrepancies += 1
                if first_discrepancy is None:
                    first_discrepancy = {"graph": gname, "b": b, "opt_all": cur_all, "opt_fixed": cur_fix, "F": sorted(F)}
    return {
        "graphs_checked": len(graphs),
        "graph_budget_pairs_checked": total_graph_budget_pairs,
        "total_simplicial_vertices_fixed": total_fixed_vertices,
        "discrepancies": discrepancies,
        "first_discrepancy": first_discrepancy,
    }


def verify_mutual_non_implication_boundaries() -> dict:
    """Exact rational witnesses showing:
      (1) On C_5 (n=5, b=1): Hub-Star cuts do NOT imply Alozie's 5-cycle inequality (mutual non-domination!).
      (2) On K_5 (n=5, b=2): L_Q-based Hub-Star cuts do NOT imply Chen's Clique-Chord inequality for cliques |K|>=5.
    """
    # (1) C_5: x_v = 1/3 for all v, y_edge = 1/3, y_2hop = 0 (since 1 - 3*(1/3) = 0).
    # Check ALL Thin + Aggregated + ALL Hub-Star cuts on C_5 (q=2, t in {0,1}):
    #   q=2, t=0 (s=2, R=3, M_w=3): 2*(1/3) + 0 + (4 + 3)*(1/3) = 9/3 = 3 >= 3!
    #   q=2, t=1 (s=1, R=2, M_w=2): 2*(1/3) + 0 + (2 + 2)*(1/3) = 6/3 = 2 >= 2!
    # Check Alozie C_5: 2*(5/3) + 5*(0) = 10/3 < 4 (violated by 2/3!!).
    G_c5 = nx.cycle_graph(5)
    e2_c5, _, rows_c5_hub = build_explicit_rational_constraints(G_c5, budget=2, include_hub_mode="all_subsets")
    rows_c5_no_alozie = [r for r in rows_c5_hub if r["family"] != "alozie_c5"]
    edge_c5 = {(min(u, v), max(u, v)) for u, v in G_c5.edges()}
    z_c5 = [Fraction(1, 3)] * 5 + [Fraction(1, 3) if p in edge_c5 else Fraction(0) for p in e2_c5]
    chk_c5_no_alozie = verify_primal_exact(5, len(e2_c5), rows_c5_no_alozie, z_c5)
    alozie_row = [r for r in rows_c5_hub if r["family"] == "alozie_c5"][0]
    alozie_lhs = sum(c * z_c5[j] for j, c in alozie_row["coeffs"].items())
    alozie_viol = alozie_row["rhs"] - alozie_lhs

    # (2) K_5 (n=5, b=3): x_v = 1/2 for all v, y_uv = 1/6 for all 10 edges -> sum y = 5/3.
    # Every K_4 subset cut (q=3, t=1, s=2, R=5) has LHS = 6*(1/6) + 2*(2) = 5 >= 5 (satisfied!).
    # Every K_5 L_Q Hub-Star cut (q=4, t=2, s=2, mu_Q=4, M_w=3, R=7) has LHS = 5/3 + 4 + 3/2 = 43/6 > 7 (satisfied!).
    # Yet Chen Clique-Chord on K_5 (t=2, s=2, R=7) has LHS = 5/3 + 5 = 20/3 < 7 (violated by 1/3!).
    G_k5 = nx.complete_graph(5)
    e2_k5, _, rows_k5_hub = build_explicit_rational_constraints(G_k5, budget=3, include_hub_mode="all_subsets")
    rows_k5_no_clq = [r for r in rows_k5_hub if r["family"] not in ("clique_chord", "alozie_c5")]
    z_k5 = [Fraction(1, 2)] * 5 + [Fraction(1, 6)] * len(e2_k5)
    chk_k5_no_clq = verify_primal_exact(5, len(e2_k5), rows_k5_no_clq, z_k5)
    chen_k5_row = [r for r in rows_k5_hub if r["name"] == "clique_0_1_2_3_4_t2"][0]
    chen_k5_lhs = sum(c * z_k5[j] for j, c in chen_k5_row["coeffs"].items())
    chen_k5_viol = chen_k5_row["rhs"] - chen_k5_lhs

    assert chk_c5_no_alozie["feasible_exact"] and alozie_viol > 0
    assert chk_k5_no_clq["feasible_exact"] and chen_k5_viol > 0

    return {
        "hub_star_does_not_imply_alozie_c5_witness": {
            "graph": "C_5",
            "budget": 2,
            "x_rational": ["1/3"] * 5,
            "y_edge_rational": "1/3",
            "y_2hop_rational": "0",
            "satisfies_thin_agg_and_all_hub_star_cuts_exact": chk_c5_no_alozie["feasible_exact"],
            "alozie_c5_lhs_rational": str(alozie_lhs),
            "alozie_c5_rhs_rational": str(alozie_row["rhs"]),
            "alozie_c5_violation_rational": str(alozie_viol),
        },
        "L_Q_hub_star_does_not_imply_chen_K5_clique_witness": {
            "graph": "K_5",
            "budget": 3,
            "x_rational": ["1/2"] * 5,
            "y_all_rational": "1/6",
            "satisfies_thin_agg_and_all_L_Q_hub_star_cuts_exact": chk_k5_no_clq["feasible_exact"],
            "chen_K5_t2_lhs_rational": str(chen_k5_lhs),
            "chen_K5_t2_rhs_rational": str(chen_k5_row["rhs"]),
            "chen_K5_t2_violation_rational": str(chen_k5_viol),
        },
    }


def main() -> None:
    t0 = perf_counter()

    # 1. Witness A: Heawood (n=14, d=3, girth=6, b=4) — FULL exact rational primal + dual + exhaustive IP!
    G_heawood = nx.convert_node_labels_to_integers(nx.heawood_graph(), ordering="sorted")
    heawood_cert = certify_d_regular_girth6_instance("heawood_bipartite_girth6_n14_b4", G_heawood, d=3, budget=4, verify_all_subsets=True)

    # Also cross-check the EXISTING Stage 0B rational baseline primal from stage0b_validity_and_witness.json
    e2_h, idx_h, rows_h_base = build_explicit_rational_constraints(G_heawood, 4, include_hub_mode="none")
    x_existing = [Fraction(0) if v in (0, 6) else Fraction(1, 3) for v in range(14)]
    edge_h = {(min(u, v), max(u, v)) for u, v in G_heawood.edges()}
    _, _, common_h = compute_e2(G_heawood)
    y_existing = []
    for p in e2_h:
        u, v = p
        if p in edge_h:
            val = max(Fraction(0), Fraction(1) - x_existing[u] - x_existing[v])
        else:
            val = max([Fraction(0)] + [Fraction(1) - x_existing[u] - x_existing[v] - x_existing[w] for w in common_h[p]])
        y_existing.append(val)
    chk_existing = verify_primal_exact(14, len(e2_h), rows_h_base, x_existing + y_existing)
    assert chk_existing["feasible_exact"] and Fraction(chk_existing["exact_obj"]) == Fraction(15)
    heawood_ip_opt, heawood_ip_checked, heawood_ip_sol = exhaustive_ip_opt(G_heawood, 4)
    assert heawood_ip_opt == 17
    heawood_cert["existing_stage0b_baseline_primal_check"] = chk_existing
    heawood_cert["exact_ip_opt_exhaustive_bfs"] = {
        "opt": heawood_ip_opt,
        "feasible_vectors_checked": heawood_ip_checked,
        "sample_opt_deletion_set": heawood_ip_sol,
    }
    print(
        f"CERTIFIED Heawood (n=14,d=3,b=4): z*_base={heawood_cert['exact_z_base']} (exact primal+dual), "
        f"z*_aug={heawood_cert['exact_z_aug_dual_lb']} (exact dual+primal pinned={heawood_cert['exact_z_aug_pinned_equality']}, "
        f"all {heawood_cert['hub_rows_checked']} hub rows checked), z*_IP={heawood_ip_opt} (exhaustive {heawood_ip_checked} vecs)"
    )

    # 2. Witness B: Non-bipartite reg_n12_d4_b3 (3 triangles / 6 clique-chord rows, 31 Alozie C_5 rows)
    G_r12 = nx.convert_node_labels_to_integers(nx.random_regular_graph(4, 12, seed=12), ordering="sorted")
    z_r12_base, d_r12_base, rows_r12_base, e2_r12 = solve_and_snap_exact_primal_dual(G_r12, 3, "none", max_denom=240)
    chk_r12_bp = verify_primal_exact(12, len(e2_r12), rows_r12_base, z_r12_base)
    chk_r12_bd = verify_dual_exact(12, len(e2_r12), rows_r12_base, d_r12_base)

    z_r12_aug, d_r12_aug, rows_r12_aug, _ = solve_and_snap_exact_primal_dual(G_r12, 3, "full_nbr", max_denom=240)
    chk_r12_ap = verify_primal_exact(12, len(e2_r12), rows_r12_aug, z_r12_aug)
    chk_r12_ad = verify_dual_exact(12, len(e2_r12), rows_r12_aug, d_r12_aug)
    r12_ip_opt, r12_ip_checked, r12_ip_sol = exhaustive_ip_opt(G_r12, 3)

    assert chk_r12_bp["feasible_exact"] and chk_r12_bd["dual_feasible_exact"]
    assert Fraction(chk_r12_bp["exact_obj"]) == Fraction(chk_r12_bd["exact_dual_lower_bound"]) == Fraction(227, 10)
    assert chk_r12_ap["feasible_exact"] and chk_r12_ad["dual_feasible_exact"]
    assert Fraction(chk_r12_ap["exact_obj"]) == Fraction(chk_r12_ad["exact_dual_lower_bound"]) == Fraction(23)
    assert r12_ip_opt == 25

    reg12_cert = {
        "label": "reg_n12_d4_b3",
        "n": 12,
        "m": G_r12.number_of_edges(),
        "m_e2": len(e2_r12),
        "budget": 3,
        "cliques_ge3_count": len(enumerate_all_cliques_ge3(G_r12)),
        "clique_chord_rows_count": sum(1 for r in rows_r12_base if r["family"] == "clique_chord"),
        "alozie_5cycles_count": len(enumerate_all_5cycles(G_r12)),
        "exact_z_base": str(Fraction(227, 10)),
        "exact_z_aug": str(Fraction(23)),
        "exact_strict_lift": str(Fraction(3, 10)),
        "baseline_primal_check": chk_r12_bp,
        "baseline_dual_check": chk_r12_bd,
        "augmented_primal_check": chk_r12_ap,
        "augmented_dual_check": chk_r12_ad,
        "augmented_dual_multipliers": {k: str(v) for k, v in sorted(d_r12_aug.items())},
        "exact_ip_opt_exhaustive_bfs": {
            "opt": r12_ip_opt,
            "feasible_vectors_checked": r12_ip_checked,
            "sample_opt_deletion_set": r12_ip_sol,
        },
    }
    print(
        f"CERTIFIED reg_n12_d4_b3 (clq={reg12_cert['cliques_ge3_count']}, c5={reg12_cert['alozie_5cycles_count']}): "
        f"z*_base={reg12_cert['exact_z_base']} (exact primal+dual), "
        f"z*_aug={reg12_cert['exact_z_aug']} (exact primal+dual, hub_duals={chk_r12_ad['nonzero_dual_rows_by_family'].get('hub_star', 0)}), "
        f"z*_IP={r12_ip_opt} (exhaustive {r12_ip_checked} vecs)"
    )

    # 3. Infinite Graph-Family Consequence Additional Verified Members (Tutte-Coxeter 8-cage & PG(2,q) Levi)
    G_tutte = nx.LCF_graph(30, [-13, -9, 7, -7, 9, 13], 5)  # Tutte-Coxeter 8-cage: n=30, d=3, girth=8!
    G_pg3 = build_pg2_levi_graph(3)     # n=26, d=4, girth=6!
    G_pg5 = build_pg2_levi_graph(5)     # n=62, d=6, girth=6!
    family_checks = [
        certify_d_regular_girth6_instance("tutte_coxeter_n30_d3_girth8_b9", G_tutte, d=3, budget=9, verify_all_subsets=True),
        certify_d_regular_girth6_instance("tutte_coxeter_n30_d3_girth8_b10", G_tutte, d=3, budget=10, verify_all_subsets=True),
        certify_d_regular_girth6_instance("pg2_3_levi_n26_d4_girth6_b6", G_pg3, d=4, budget=6, verify_all_subsets=False),
        certify_d_regular_girth6_instance("pg2_3_levi_n26_d4_girth6_b8", G_pg3, d=4, budget=8, verify_all_subsets=False),
        certify_d_regular_girth6_instance("pg2_5_levi_n62_d6_girth6_b15", G_pg5, d=6, budget=15, verify_all_subsets=False),
        certify_d_regular_girth6_instance("pg2_5_levi_n62_d6_girth6_b20", G_pg5, d=6, budget=20, verify_all_subsets=False),
    ]
    for fc in family_checks:
        print(
            f"FAMILY_CERT {fc['label']:34s} | d={fc['d']} g={fc['girth']} b={fc['budget']:2d} | "
            f"z*_base={fc['exact_z_base']:>6s} -> z*_aug>={fc['exact_z_aug_dual_lb']:>6s} "
            f"(lift>={fc['exact_strict_lift_lb']:>5s}, exact_pinned={fc['exact_z_aug_pinned_equality']})"
        )

    # 4. Mutual Non-Implication Boundaries
    boundaries = verify_mutual_non_implication_boundaries()
    print(
        f"BOUNDARIES VERIFIED: C_5 Alozie viol={boundaries['hub_star_does_not_imply_alozie_c5_witness']['alozie_c5_violation_rational']}, "
        f"K_5 Chen viol={boundaries['L_Q_hub_star_does_not_imply_chen_K5_clique_witness']['chen_K5_t2_violation_rational']}"
    )

    # 5. Exhaustive Independent-Set Simplicial Fixing Check
    simp_check = verify_simplicial_fixing_exhaustive()
    assert simp_check["discrepancies"] == 0
    print(
        f"SIMPLICIAL_CHECK VERIFIED: {simp_check['graphs_checked']} graphs, "
        f"{simp_check['graph_budget_pairs_checked']} (graph, b) pairs, "
        f"{simp_check['total_simplicial_vertices_fixed']} fixed vertices, 0 discrepancies"
    )

    out = {
        "stage": "stage_0b_exact_rational_primal_dual_certificates",
        "arithmetic": "100% exact Python fractions.Fraction verification (zero float reliance in certificates)",
        "witness_a_heawood": heawood_cert,
        "witness_b_nonbipartite_reg_n12_d4_b3": reg12_cert,
        "infinite_family_d_regular_girth6_verified_members": family_checks,
        "mutual_non_implication_boundaries": boundaries,
        "simplicial_independent_set_fixing_exhaustive_check": simp_check,
        "elapsed_seconds": round(perf_counter() - t0, 3),
    }
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT_PATH} elapsed={out['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
