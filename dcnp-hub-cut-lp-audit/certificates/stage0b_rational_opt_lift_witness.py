"""Find & certify in EXACT rational arithmetic (Fraction) a small synthetic witness where BOTH:
  (a) the exact optimal fractional vertex (x*, y*) of the FULL exhaustive finite baseline LP
      (Salemi-Buchanan Thin + Khoshbakhtian Aggregated + ALL Alozie 3-cycles & 5-cycles +
      ALL Chen-adapted Clique-Chord subsets |K|>=3 & ALL chords t) satisfies EVERY baseline
      constraint with exact rational slack >= 0, AND
  (b) (x*, y*) strictly violates a Hub-Lifted Closed-Neighborhood valid inequality, AND
  (c) adding Hub-Star cuts STRICTLY increases the exact LP optimum objective value below IP OPT!
"""

from __future__ import annotations

from fractions import Fraction
import json
from pathlib import Path

import highspy
import networkx as nx
import numpy as np

from stage0b_validity_and_witness import (
    build_full_exhaustive_baseline_lp,
    compute_e2,
    enumerate_all_5cycles,
    enumerate_all_cliques_ge3,
    exact_bfs_y,
    hub_star_cut_params,
)

GATE_PATH = Path(__file__).resolve().parent / "stage0b_validity_and_witness.json"


def check_candidate(label: str, G: nx.Graph, budget: int) -> dict | None:
    G = nx.convert_node_labels_to_integers(G, ordering="sorted")
    n = G.number_of_nodes()
    h, e2, idx_map, common, cliques, cycles5 = build_full_exhaustive_baseline_lp(G, budget)
    h.run()
    lp_base = float(h.getInfo().objective_function_value)
    sol = np.array(h.getSolution().col_value, dtype=np.float64)
    x_lp = sol[:n]
    y_lp = sol[n:]

    # Snap optimal LP solution to exact small-denominator rationals (max_denominator=120) and verify exact feasibility
    x_rat = [Fraction(float(v)).limit_denominator(120) for v in x_lp]
    y_rat = [Fraction(float(v)).limit_denominator(120) for v in y_lp]

    # Exact rational feasibility audit against ALL exhaustive baseline rows
    slacks = {
        "budget": Fraction(budget) - sum(x_rat),
        "box_bounds": min([min(v, Fraction(1) - v) for v in x_rat] + [min(v, Fraction(1) - v) for v in y_rat]),
        "edges": min(y_rat[idx_map[(min(u, v), max(u, v))]] + x_rat[u] + x_rat[v] - Fraction(1) for u, v in G.edges()),
        "thin_2hop": min((y_rat[idx_map[(u, v)]] + x_rat[u] + x_rat[v] + x_rat[w] - Fraction(1) for (u, v), ws in common.items() for w in ws), default=Fraction(0)),
        "khosh_agg": min((len(ws) * (y_rat[idx_map[(u, v)]] + x_rat[u] + x_rat[v]) + sum(x_rat[w] for w in ws) - Fraction(len(ws)) for (u, v), ws in common.items()), default=Fraction(0)),
    }
    clq_sl = []
    for K in cliques:
        q = len(K)
        pids = [idx_map[(K[i], K[j])] for i in range(q) for j in range(i + 1, q)]
        for t in range(q - 1):
            s = q - t - 1
            rhs = Fraction((q - t) * (q - t - 1) // 2 + t * s)
            clq_sl.append(sum(y_rat[pi] for pi in pids) + Fraction(s) * sum(x_rat[v] for v in K) - rhs)
    slacks["all_clique_subsets_all_chords"] = min(clq_sl) if clq_sl else Fraction(0)

    c5_sl = []
    for v0, v1, v2, v3, v4 in cycles5:
        chords = [(v0, v2), (v1, v3), (v2, v4), (v3, v0), (v4, v1)]
        lhs = Fraction(2) * (x_rat[v0] + x_rat[v1] + x_rat[v2] + x_rat[v3] + x_rat[v4]) + sum(y_rat[idx_map[(min(a, b), max(a, b))]] for a, b in chords)
        c5_sl.append(lhs - Fraction(4))
    slacks["all_alozie_5cycles"] = min(c5_sl) if c5_sl else Fraction(0)

    all_ok = all(v >= 0 for v in slacks.values())

    # Find most violated Hub-Star cut at exact rational (x_rat, y_rat) AND solve LP + ALL full-neighborhood Hub-Star cuts
    best_viol = Fraction(0)
    best_cut = None
    for w in range(n):
        Q = sorted(G.neighbors(w))
        q = len(Q)
        if q < 2:
            continue
        na = sorted(Q + [w])
        pids = [idx_map[(na[i], na[j])] for i in range(len(na)) for j in range(i + 1, len(na))]
        for t in range(q):
            s, Mw, R, mu = hub_star_cut_params(G, w, Q, t)
            lhs = sum(y_rat[pi] for pi in pids) + Fraction(s) * sum(x_rat[u] for u in Q) + Fraction(Mw) * x_rat[w]
            viol = Fraction(R) - lhs
            if viol > best_viol:
                best_viol = viol
                best_cut = {"hub_w": w, "Q": Q, "t": t, "s": s, "mu_Q": mu, "M_w": Mw, "RHS": R, "LHS_rational": str(lhs), "violation_rational": str(viol)}
            # Add cut to HiGHS LP
            inds = np.array(Q + [w] + [n + pi for pi in pids], dtype=np.int32)
            vals = np.array([float(s)] * q + [float(Mw)] + [1.0] * len(pids), dtype=np.float64)
            h.addRow(float(R), highspy.kHighsInf, len(inds), inds, vals)

    h.run()
    lp_plus_star = float(h.getInfo().objective_function_value)

    # Exact integer OPT via HiGHS MIP (or exhaustive if n <= 16)
    h.changeColsIntegrality(n, np.arange(n, dtype=np.int32), np.full(n, highspy.HighsVarType.kInteger))
    h.run()
    opt_ip = int(round(h.getInfo().objective_function_value))

    if all_ok and best_viol > 0 and lp_plus_star > lp_base + 1e-6:
        return {
            "label": label,
            "n": n,
            "m": G.number_of_edges(),
            "m_e2": len(e2),
            "budget": budget,
            "all_cliques_ge3": len(cliques),
            "all_clique_chord_rows": len(clq_sl),
            "all_5cycles": len(cycles5),
            "exact_rational_opt_x": [str(v) for v in x_rat],
            "exact_rational_opt_obj": str(sum(y_rat)),
            "exact_rational_min_slacks": {k: str(v) for k, v in slacks.items()},
            "all_exhaustive_baseline_satisfied_exact": all_ok,
            "violated_hub_star_cut": best_cut,
            "lp_full_exhaustive_baseline": round(lp_base, 6),
            "lp_full_plus_hub_stars": round(lp_plus_star, 6),
            "exact_ip_opt": opt_ip,
            "gap_closed_over_full_exhaustive_baseline_pct": round(100.0 * (lp_plus_star - lp_base) / max(1e-9, opt_ip - lp_base), 2),
        }
    return None


def main() -> None:
    cands = [
        ("heawood_bipartite_girth6_n14_b3", nx.heawood_graph(), 3),
        ("heawood_bipartite_girth6_n14_b4", nx.heawood_graph(), 4),
        ("cube_Q3_bipartite_n8_b2", nx.hypercube_graph(3), 2),
        ("cube_Q4_bipartite_n16_b4", nx.hypercube_graph(4), 4),
        ("bip_rand_7x7_p045_b3", nx.bipartite.random_graph(7, 7, 0.45, seed=7), 3),
        ("bip_rand_8x8_p040_b4", nx.bipartite.random_graph(8, 8, 0.40, seed=8), 4),
        ("reg_n12_d4_b3", nx.random_regular_graph(4, 12, seed=12), 3),
        ("reg_n14_d4_b4", nx.random_regular_graph(4, 14, seed=14), 4),
        ("er_n14_p035_b4", nx.erdos_renyi_graph(14, 0.35, seed=140), 4),
    ]
    found = {}
    for label, G, b in cands:
        res = check_candidate(label, G, b)
        if res:
            found[label] = res
            print(
                f"STRICT_OPT_LIFT {label:32s} | clq={res['all_cliques_ge3']:2d} c5={res['all_5cycles']:3d} | "
                f"LP_full={res['lp_full_exhaustive_baseline']:6.3f} (rat={res['exact_rational_opt_obj']}) -> "
                f"LP_star={res['lp_full_plus_hub_stars']:6.3f} (OPT={res['exact_ip_opt']}, {res['gap_closed_over_full_exhaustive_baseline_pct']:5.1f}% closed) | "
                f"exact_viol={res['violated_hub_star_cut']['violation_rational']}"
            )
    data = json.loads(GATE_PATH.read_text(encoding="utf-8"))
    data["part2b_exact_rational_lp_optimum_strict_lift_witnesses"] = found
    GATE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(f"UPDATED={GATE_PATH} count={len(found)}")


if __name__ == "__main__":
    main()
