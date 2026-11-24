"""Exact whole-family LP reduction for Theorem 1 cuts on d-regular graphs of girth >= 6 (synthetic only).

Claim (proved in THEOREM doc, Prop. 2'): for such G with n vertices and budget b = alpha n (alpha <= 1/3), the LP value of
  Thin + {Hub-Lifted cuts over a row family F that is closed under hub/subset averaging}
equals n * v_F(alpha), where v_F is the optimum of a 2-variable LP in (Y_e, Y_p) obtained by AVERAGING (valid lower bound,
no symmetry assumed) and attained by the UNIFORM point (valid upper bound). Everything below is exact Fraction arithmetic:
  * piecewise-linear v_F breakpoints (exact, via convex tangent refinement),
  * graph-level exact primal (uniform point vs. every explicit row) and exact nonnegative dual (aggregated multipliers
    spread over rows) for Heawood, Tutte-Coxeter, PG(2,3) and PG(2,5) Levi graphs.
"""
from __future__ import annotations

import json
from fractions import Fraction as F
from math import comb
from pathlib import Path
from time import perf_counter

import networkx as nx

from stage0b_exact_rational_certificate import (
    build_explicit_rational_constraints,
    build_pg2_levi_graph,
    verify_dual_exact,
    verify_primal_exact,
)

OUT = Path(__file__).resolve().parent / "stage2_family_reduction_certificate.json"


def Rv(q: int, t: int) -> F:
    return F((q - t) * (q + t + 1), 2)


def agg_rows(n: int, d: int, family: str):
    """Aggregated rows (name, c_Ye, c_Yp, c_X, rhs, meta) valid for ANY feasible point (averaging, no symmetry)."""
    rows = [
        ("edge", F(1), F(0), F(d), F(n * d, 2), None),
        ("thin", F(0), F(1), F(3 * d * (d - 1), 2), F(n * d * (d - 1), 2), None),
    ]
    if family == "base":
        return rows
    for q in range(2, d + 1):
        for t in range(q):
            if family == "t1full" and not (q == d and t == 1):
                continue
            if family == "full_nbr" and q != d:
                continue
            s = q - t
            r = Rv(q, t)
            rows.append((f"cut_q{q}_t{t}", F(2 * q, d), F(q * (q - 1), d * (d - 1)), F(s * q) + r, n * r, (q, t)))
    return rows


def solve_agg(n: int, d: int, b: F, family: str) -> dict:
    """Exact optimum of: min Ye+Yp s.t. aggregated rows at X=b, Ye,Yp>=0. Returns primal vertex and exact dual."""
    rows = agg_rows(n, d, family)
    lines = [(ce, cp, rhs - cx * b, i) for i, (_, ce, cp, cx, rhs, _) in enumerate(rows)]
    lines += [(F(1), F(0), F(0), None), (F(0), F(1), F(0), None)]
    best = None
    L = len(lines)
    for i in range(L):
        for j in range(i + 1, L):
            a1, b1, r1, _ = lines[i]
            a2, b2, r2, _ = lines[j]
            det = a1 * b2 - a2 * b1
            if det == 0:
                continue
            ye = (r1 * b2 - r2 * b1) / det
            yp = (a1 * r2 - a2 * r1) / det
            if ye < 0 or yp < 0:
                continue
            obj = ye + yp
            if best is not None and obj >= best[0]:
                continue
            if all(l[0] * ye + l[1] * yp >= l[2] for l in lines):
                best = (obj, ye, yp)
    obj, ye, yp = best
    tight = [k for k, l in enumerate(lines) if l[0] * ye + l[1] * yp == l[2]]
    cands = [(k,) for k in tight] + [(tight[i], tight[j]) for i in range(len(tight)) for j in range(i + 1, len(tight))]
    dual = None
    for c in cands:
        if len(c) == 1:
            a1, b1, _, _ = lines[c[0]]
            if a1 == b1 and a1 > 0:
                dual = {c[0]: F(1) / a1}
                break
        else:
            a1, b1, _, _ = lines[c[0]]
            a2, b2, _, _ = lines[c[1]]
            det = a1 * b2 - a2 * b1
            if det == 0:
                continue
            m1 = (b2 - a2) / det
            m2 = (a1 - b1) / det
            if m1 >= 0 and m2 >= 0:
                dual = {c[0]: m1, c[1]: m2}
                break
    assert dual is not None
    m = {}
    inter = F(0)
    mb = F(0)
    for k, mk in dual.items():
        if lines[k][3] is None or mk == 0:
            continue
        nm, _, _, cx, rhs, _ = rows[lines[k][3]]
        m[nm] = mk
        inter += mk * rhs
        mb += mk * cx
    assert inter - mb * b == obj, "strong duality (exact) failed"
    return {"obj": obj, "ye": ye, "yp": yp, "m": m, "inter": inter, "mb": mb, "family": family}


def breakpoints(d: int, family: str) -> dict:
    """Exact breakpoints of v_F(alpha) on [1/(d+1), 1/3] (n = 1) by convex tangent refinement."""
    lo, hi = F(1, d + 1), F(1, 3)

    def piece(x):
        s = solve_agg(1, d, x, family)
        assert s["ye"] <= F(d, 2) and s["yp"] <= F(d * (d - 1), 2)  # upper-bound rows inactive
        return (s["inter"], -s["mb"], tuple(sorted(s["m"])))

    out = []

    def refine(lo_, plo, hi_, phi):
        if plo[:2] == phi[:2]:
            return
        x = (plo[0] - phi[0]) / (phi[1] - plo[1])
        pm = piece(x)
        if pm[0] + pm[1] * x == plo[0] + plo[1] * x:
            out.append(x)
            return
        refine(lo_, plo, x, pm)
        refine(x, pm, hi_, phi)

    p_lo, p_hi = piece(lo), piece(hi)
    refine(lo, p_lo, hi, p_hi)
    xs = [lo] + out + [hi]
    pieces = []
    for a, b in zip(xs[:-1], xs[1:]):
        p = piece((a + b) / 2)
        pieces.append({"from": str(a), "to": str(b), "intercept": str(p[0]), "slope": str(p[1]), "active": list(p[2])})
    return {"d": d, "family": family, "breakpoints": [str(x) for x in out], "pieces": pieces}


def t1_closed_form(d: int, alpha: F) -> F:
    """Earlier dual lower bound (q=d, t=1 only), per vertex: (d^2-1)/2 - (d-1)(3d+1)/2 * alpha."""
    return F(d * d - 1, 2) - F((d - 1) * (3 * d + 1), 2) * alpha


def graph_cert(label: str, G: nx.Graph, d: int, b: int, family: str) -> dict:
    G = nx.convert_node_labels_to_integers(G, ordering="sorted")
    n = G.number_of_nodes()
    assert set(dict(G.degree()).values()) == {d} and nx.girth(G) >= 6
    mode = {"base": "none", "t1full": "full_nbr", "full_nbr": "full_nbr", "all": "all_subsets"}[family]
    afam = "all" if family == "all" else family
    sol = solve_agg(n, d, F(b), afam)
    e2, _, rows = build_explicit_rational_constraints(G, b, include_hub_mode=mode)
    if family == "t1full":
        rows = [r for r in rows if r["family"] != "hub_star" or r["meta"]["t"] == 1]
    edges = {(min(u, v), max(u, v)) for u, v in G.edges()}
    nE, nP = len(edges), len(e2) - len(edges)
    a, c = sol["ye"] / nE, sol["yp"] / nP
    alpha = F(b, n)
    z = [alpha] * n + [a if p in edges else c for p in e2]
    chk_p = verify_primal_exact(n, len(e2), rows, z)
    dual = {"budget": sol["mb"]}
    for r in rows:
        if r["family"] == "edge":
            dual[r["name"]] = sol["m"].get("edge", F(0))
        elif r["family"] == "thin_2hop":
            dual[r["name"]] = sol["m"].get("thin", F(0))
        elif r["family"] == "hub_star":
            q, t = len(r["meta"]["Q"]), r["meta"]["t"]
            mm = sol["m"].get(f"cut_q{q}_t{t}", F(0))
            if mm:
                dual[r["name"]] = mm / comb(d, q)
    chk_d = verify_dual_exact(n, len(e2), rows, dual)
    ok = (chk_p["feasible_exact"] and chk_d["dual_feasible_exact"]
          and F(chk_p["exact_obj"]) == F(chk_d["exact_dual_lower_bound"]) == sol["obj"])
    return {
        "label": label, "family": family, "n": n, "d": d, "budget": b, "alpha": str(alpha),
        "rows_checked": len(rows), "hub_rows": sum(1 for r in rows if r["family"] == "hub_star"),
        "exact_lp_value": str(sol["obj"]), "primal_obj": chk_p["exact_obj"],
        "dual_lb": chk_d["exact_dual_lower_bound"], "primal_feasible_exact": chk_p["feasible_exact"],
        "dual_feasible_exact": chk_d["dual_feasible_exact"], "exact_both_sides_equal": ok,
        "active_cut_classes": sorted(k for k in sol["m"] if k.startswith("cut")),
        "t1_closed_form_lb": str(n * t1_closed_form(d, alpha)),
    }


def main() -> None:
    t0 = perf_counter()
    # 1. Exact breakpoints per d and row family
    sweeps = []
    for d in range(3, 9):
        for fam in ("base", "t1full", "full_nbr", "all"):
            sw = breakpoints(d, fam)
            sweeps.append(sw)
            print(f"d={d} {fam:9s} breakpoints={sw['breakpoints']}", flush=True)

    # 2. Where does the whole family beat the t=1 full-neighborhood bound? exact comparison at each breakpoint/endpoint
    cmp = []
    for d in range(3, 9):
        xs = {F(1, d + 1), F(1, 3)}
        for sw in sweeps:
            if sw["d"] == d:
                xs |= {F(x) for x in sw["breakpoints"]}
        for x in sorted(xs):
            vb = solve_agg(1, d, x, "base")["obj"]
            v1 = solve_agg(1, d, x, "t1full")["obj"]
            vf = solve_agg(1, d, x, "full_nbr")["obj"]
            va = solve_agg(1, d, x, "all")["obj"]
            cmp.append({"d": d, "alpha": str(x), "base": str(vb), "t1_exact": str(v1), "t1_closed_form": str(t1_closed_form(d, x)),
                        "full_nbr_all_t": str(vf), "all_subsets": str(va),
                        "lift_all_over_base": str(va - vb), "all_minus_t1": str(va - v1)})

    # 3. Graph-level exact certificates
    G_h = nx.heawood_graph()
    G_t = nx.LCF_graph(30, [-13, -9, 7, -7, 9, 13], 5)
    G_p3 = build_pg2_levi_graph(3)
    G_p5 = build_pg2_levi_graph(5)
    insts = [("heawood_n14_b4", G_h, 3, 4), ("tutte_coxeter_n30_b9", G_t, 3, 9), ("tutte_coxeter_n30_b10", G_t, 3, 10),
             ("pg2_3_levi_n26_b6", G_p3, 4, 6), ("pg2_3_levi_n26_b8", G_p3, 4, 8),
             ("pg2_5_levi_n62_b15", G_p5, 6, 15), ("pg2_5_levi_n62_b20", G_p5, 6, 20)]
    certs = []
    for label, G, d, b in insts:
        for fam in ("t1full", "full_nbr", "all"):
            c = graph_cert(label, G, d, b, fam)
            certs.append(c)
            print(f"CERT {label:22s} {fam:8s} rows={c['rows_checked']:6d} exact={c['exact_lp_value']:>8s} "
                  f"both_sides={c['exact_both_sides_equal']} active={c['active_cut_classes']}", flush=True)
            assert c["exact_both_sides_equal"], c
    out = {"stage": "stage2_family_reduction_certificate", "arithmetic": "exact Fraction",
           "sweeps": sweeps, "comparison_at_breakpoints": cmp, "graph_certificates": certs,
           "elapsed_seconds": round(perf_counter() - t0, 3)}
    OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT} elapsed={out['elapsed_seconds']}s")


if __name__ == "__main__":
    main()
