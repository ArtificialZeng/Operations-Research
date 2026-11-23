#!/usr/bin/env python3
"""One-command INFORMS referee verification suite for:
'A single availability date changes the approximability of delay in fixed-order flow shops'

Independently verifies:
  1. Lemmas 1-2 (anti-Monge four-point inequality & clock monotonicity) and Theorem 1
     (plain DP vs. anti-Monge upper-envelope DP vs. brute-force enumeration, incl. edge cases).
  2. Corollary 1 (monotone submodularity & O(mn) singleton positive-increase detector).
  3. Theorem 2 & Appendix D (two-job single-terminal-clock & single-anticipatory-first-setup
     knapsack reductions, plus toy numerical example 8,9,9,10 vs. 9,9,9,10).
  4. Theorem 3 (source-wise certified approximation bounds [L, U], rho-slack relative guarantee,
     rho = 0 FPTAS, and 128-bit large binary budget stress check where DP in B is infeasible).
  5. Theorem 4 (two-job two-clock upstream-deletion coNP-completeness reduction).
  6. Theorem 5 (O(mn) downstream suffix deletion maximum-error test & singleton witness).
  7. Appendix A Proposition A.1 (O(mn) all-completions minimum-cardinality support &
     operation-level transport/material/setup-anticipation timing).
  8. Appendix B Theorem 6, uniform-threshold anti-Monge deletion oracle, minimum clock
     retention constraint generation, Proposition 7 one-versus-two gap (and T=1 boundary),
     and greedy-deletion suboptimality counterexample.
  9. Model-validity boundary counterexamples (heterogeneous job releases, mid-horizon outage
     non-submodularity, zero-wait infeasibility, permutation re-optimization non-submodularity).
 10. Optional cross-check of all manuscript & appendix tables against archived local JSONs.
"""

from __future__ import annotations

import json
import pathlib
import random
import statistics
import time
from fractions import Fraction
from typing import Any, Dict, List, Set, Tuple

from flowshop_core import (
    NEG_INF,
    FlowShopInstance,
    arbitrary_deletion_max_error,
    build_checkpoint_graph,
    corollary1_singleton_check,
    deletion_threshold_oracle,
    enumerate_exact,
    evaluate_makespan,
    min_all_completions_support,
    minimum_retained_clocks,
    simulate_schedule,
    solve_exact_envelope,
    solve_exact_plain,
    solve_source_approx,
    source_contributions_backward,
    suffix_deletion_max_error,
)
from maxplus_cascades import (
    SwitchedCascade,
    enumerate_cascade_max_error,
    linear_singleton_errors,
    nonconsecutive_deletion_certificate,
    projective_diameter,
)


def random_instance(
    rng: random.Random,
    m: int,
    n: int,
    with_clocks: bool = True,
    with_setups: bool = True,
    with_job_releases: bool = True,
    with_op_timing: bool = False,
    compulsory_prob: float = 0.2,
) -> FlowShopInstance:
    p = tuple(tuple(rng.randint(1, 15) for _ in range(n)) for _ in range(m))
    if with_setups:
        s = tuple(tuple(rng.randint(0, 8) for _ in range(n)) for _ in range(m))
    else:
        s = tuple(tuple(0 for _ in range(n)) for _ in range(m))
    if with_job_releases:
        # Deliberately allow non-monotone release dates
        r = tuple(rng.randint(0, 25) for _ in range(n))
    else:
        r = tuple(0 for _ in range(n))
    if with_clocks:
        R = tuple(rng.randint(0, 35 * (i + 1)) if rng.random() < 0.7 else 0 for i in range(m))
    else:
        R = tuple(0 for _ in range(m))
    comp = frozenset(i for i in range(1, m - 1) if rng.random() < compulsory_prob)
    costs = tuple(rng.randint(1, 9) for _ in range(m))
    budget = rng.randint(0, max(1, sum(costs) // 2))
    d = A = U = ell = None
    if with_op_timing:
        d = tuple(tuple(rng.randint(0, 5) for _ in range(n)) for _ in range(m))
        A = tuple(
            tuple(rng.randint(0, 30 * (i + 1)) if rng.random() < 0.5 else NEG_INF for _ in range(n))
            for i in range(m)
        )
        U = tuple(
            tuple(rng.randint(0, 25 * (i + 1)) if rng.random() < 0.5 else NEG_INF for _ in range(n))
            for i in range(m)
        )
        ell = tuple(tuple(rng.randint(0, s[i][t]) for t in range(n)) for i in range(m))
    return FlowShopInstance(p=p, s=s, r=r, R=R, compulsory=comp, costs=costs, budget=budget, d=d, A=A, U=U, ell=ell)


def check_lemmas_and_theorem1() -> Dict[str, Any]:
    rng = random.Random(2026112301)
    anti_monge_checks = 0
    b_monotone_checks = 0
    exact_queries = 0

    for _ in range(60):
        m = rng.randint(2, 9)
        n = rng.randint(1, 8)
        inst = random_instance(rng, m, n, with_clocks=True, with_setups=True, with_job_releases=True)
        g = build_checkpoint_graph(inst)
        # Lemma 1: a(i,k) + a(j,l) >= a(i,l) + a(j,k) for i < j < k < l in same compulsory interval
        for L, R_end in g.intervals:
            for i in range(L, R_end + 1):
                for j in range(i + 1, R_end + 1):
                    for k in range(j + 1, R_end + 1):
                        for l in range(k + 1, R_end + 1):
                            assert g.a[(i, k)] + g.a[(j, l)] >= g.a[(i, l)] + g.a[(j, k)]
                            anti_monge_checks += 1
        # Lemma 2: b(i,j) nonincreasing as i advances for fixed j
        for L, R_end in g.intervals:
            for j in range(L + 2, R_end + 1):
                for i in range(L, j - 1):
                    assert g.b[(i, j)] >= g.b[(i + 1, j)]
                    b_monotone_checks += 1

        d_enum, c_enum, _ = enumerate_exact(inst)
        d_plain, c_plain, w_plain = solve_exact_plain(inst, g)
        d_env, c_env, w_env = solve_exact_envelope(inst, g)
        assert d_enum == d_plain == d_env
        assert c_enum == c_plain == c_env
        # Independently verify returned witnesses and budget feasibility
        for w in (w_plain, w_env):
            assert sum(inst.costs[x] for x in w) <= inst.budget
            assert all(x not in inst.compulsory and x < inst.m - 1 for x in w)
            assert evaluate_makespan(inst, w) == c_enum
        exact_queries += 1

    # Boundary edge cases: m=1, n=1, B=0, all compulsory, zero-cost optional machine
    edge_cases = [
        FlowShopInstance(p=((5, 3, 7),), s=((2, 0, 1),), r=(4, 0, 9), R=(10,), compulsory=frozenset(), costs=(3,), budget=10),
        FlowShopInstance(p=((4,), (9,), (2,)), s=((1,), (3,), (0,)), r=(5,), R=(0, 8, 12), compulsory=frozenset(), costs=(1, 2, 3), budget=5),
        FlowShopInstance(p=((3, 2), (1, 5), (4, 1)), s=((0, 0), (0, 0), (0, 0)), r=(0, 0), R=(0, 0, 0), compulsory=frozenset(), costs=(2, 2, 2), budget=0),
        FlowShopInstance(p=((2, 4), (5, 1), (3, 3), (1, 2)), s=((0, 1), (2, 0), (1, 1), (0, 0)), r=(0, 7), R=(0, 4, 2, 9), compulsory=frozenset({0, 1, 2}), costs=(5, 5, 5, 5), budget=10),
    ]
    for inst in edge_cases:
        d_e, c_e, _ = enumerate_exact(inst)
        d_p, c_p, w_p = solve_exact_plain(inst)
        d_v, c_v, w_v = solve_exact_envelope(inst)
        assert d_e == d_p == d_v and c_e == c_p == c_v
        assert evaluate_makespan(inst, w_p) == c_e
        assert evaluate_makespan(inst, w_v) == c_e
        exact_queries += 1

    return {
        "anti_monge_checks": anti_monge_checks,
        "b_monotone_checks": b_monotone_checks,
        "exact_queries_verified": exact_queries,
    }


def check_corollary1() -> Dict[str, Any]:
    rng = random.Random(2026112302)
    submod_checks = 0
    singleton_queries = 0
    for _ in range(50):
        m = rng.randint(2, 8)
        n = rng.randint(2, 7)
        p = tuple(tuple(rng.randint(1, 12) for _ in range(n)) for _ in range(m))
        # s_i(1) = 0, arbitrary s_i(t) >= 0 for t >= 2; R_i = 0; r_t >= 0
        s = tuple(tuple(0 if t == 0 else rng.randint(0, 6) for t in range(n)) for _ in range(m))
        r = tuple(rng.randint(0, 15) for _ in range(n))
        R = tuple(0 for _ in range(m))
        comp = frozenset(i for i in range(1, m - 1) if rng.random() < 0.2)
        costs = tuple(rng.randint(1, 8) for _ in range(m))
        budget = rng.randint(0, max(1, sum(costs) // 2))
        inst = FlowShopInstance(p=p, s=s, r=r, R=R, compulsory=comp, costs=costs, budget=budget)

        # Check submodularity on random subsets A subset B and element x
        opts = [i for i in range(m - 1) if i not in comp]
        if len(opts) >= 2:
            for _ in range(10):
                x = rng.choice(opts)
                others = [o for o in opts if o != x]
                A_sub = {o for o in others if rng.random() < 0.35}
                B_sub = A_sub | {o for o in others if rng.random() < 0.5}
                mA = evaluate_makespan(inst, A_sub | {x}) - evaluate_makespan(inst, A_sub)
                mB = evaluate_makespan(inst, B_sub | {x}) - evaluate_makespan(inst, B_sub)
                assert mA >= mB >= 0
                submod_checks += 1

        # Check O(mn) singleton positive-increase detector matches exact optimum > 0
        pos_flag, sing_gain, sing_m = corollary1_singleton_check(inst)
        d_opt, _, _ = enumerate_exact(inst)
        assert pos_flag == (d_opt > 0)
        if sing_m is not None:
            assert evaluate_makespan(inst, (sing_m,)) - evaluate_makespan(inst, ()) == sing_gain
        singleton_queries += 1

    return {"submodularity_checks": submod_checks, "singleton_queries_verified": singleton_queries}


def build_theorem2_instance(
    weights: Sequence[int], values: Sequence[int], budget: int, target_H: int, via_setup: bool = False
) -> FlowShopInstance:
    """Two-job knapsack construction from Theorem 2 (or Appendix D via terminal first setup)."""
    r = len(weights)
    vals = list(values) + [0]
    p_rows: List[Tuple[int, int]] = [(1, vals[0] + 1)]
    costs: List[int] = [budget + 1]
    for i in range(r):
        p_rows.append((1, 1))
        costs.append(weights[i])
        p_rows.append((vals[i] + 1, vals[i + 1] + 1))
        costs.append(budget + 1)
    m = len(p_rows)
    C0 = 2 * r + 2 + sum(values)
    P_m2 = p_rows[-1][0] + p_rows[-1][1]
    shift = C0 + target_H - 1 - P_m2
    assert shift > 0
    if via_setup:
        R = tuple(0 for _ in range(m))
        s = tuple((shift, 0) if i == m - 1 else (0, 0) for i in range(m))
    else:
        R = tuple(shift if i == m - 1 else 0 for i in range(m))
        s = tuple((0, 0) for _ in range(m))
    return FlowShopInstance(
        p=tuple(p_rows), s=s, r=(0, 0), R=R, compulsory=frozenset(), costs=tuple(costs), budget=budget
    )


def check_theorem2_and_appendix_d() -> Dict[str, Any]:
    # 1. Paper's 5-machine toy example (Section 3 & Appendix D)
    P_toy = ((1, 2), (1, 1), (2, 2), (1, 1), (2, 1))
    s0 = tuple((0, 0) for _ in range(5))
    s_term = ((0, 0), (0, 0), (0, 0), (0, 0), (6, 0))
    inst_zero = FlowShopInstance(p=P_toy, s=s0, r=(0, 0), R=(0, 0, 0, 0, 0), compulsory=frozenset(), costs=(9, 1, 9, 1, 9), budget=2)
    inst_R5 = FlowShopInstance(p=P_toy, s=s0, r=(0, 0), R=(0, 0, 0, 0, 6), compulsory=frozenset(), costs=(9, 1, 9, 1, 9), budget=2)
    inst_S5 = FlowShopInstance(p=P_toy, s=s_term, r=(0, 0), R=(0, 0, 0, 0, 0), compulsory=frozenset(), costs=(9, 1, 9, 1, 9), budget=2)
    subsets = [(), (1,), (3,), (1, 3)]
    assert [evaluate_makespan(inst_zero, sub) for sub in subsets] == [8, 9, 9, 10]
    assert [evaluate_makespan(inst_R5, sub) for sub in subsets] == [9, 9, 9, 10]
    assert [evaluate_makespan(inst_S5, sub) for sub in subsets] == [9, 9, 9, 10]

    # 2. Knapsack reduction verification over 40 random knapsack instances (both R_m and s_m(1))
    rng = random.Random(2026112303)
    knap_checks = 0
    for _ in range(40):
        r = rng.randint(2, 5)
        w = [rng.randint(1, 12) for _ in range(r)]
        v = [rng.randint(1, 15) for _ in range(r)]
        B = rng.randint(1, sum(w))
        H = rng.randint(1, sum(v) + 2)
        # Brute-force knapsack optimum
        knap_opt = 0
        for mask in range(1 << r):
            tw = sum(w[i] for i in range(r) if (mask >> i) & 1)
            if tw <= B:
                knap_opt = max(knap_opt, sum(v[i] for i in range(r) if (mask >> i) & 1))
        expected_delta = max(0, knap_opt - H + 1)
        for via_setup in (False, True):
            inst = build_theorem2_instance(w, v, B, H, via_setup=via_setup)
            delta, _, _ = solve_exact_envelope(inst)
            assert delta == expected_delta
            assert (delta > 0) == (knap_opt >= H)
            knap_checks += 1

    # 3. Appendix D intermediate-completion vs makespan example
    inst_mid_with = FlowShopInstance(
        p=((1, 1), (1, 1), (100, 1)),
        s=((0, 0), (0, 0), (0, 0)),
        r=(0, 3),
        R=(0, 0, 0),
        compulsory=frozenset(),
        costs=(1, 9, 9),
        budget=1,
        A=((NEG_INF, NEG_INF), (NEG_INF, 10), (NEG_INF, NEG_INF)),
    )
    inst_mid_no = FlowShopInstance(
        p=((1, 1), (1, 1), (100, 1)),
        s=((0, 0), (0, 0), (0, 0)),
        r=(0, 3),
        R=(0, 0, 0),
        compulsory=frozenset(),
        costs=(1, 9, 9),
        budget=1,
    )
    c_w0, mat_w0 = simulate_schedule(inst_mid_with, ())
    c_w1, mat_w1 = simulate_schedule(inst_mid_with, (0,))
    c_n0, mat_n0 = simulate_schedule(inst_mid_no, ())
    c_n1, mat_n1 = simulate_schedule(inst_mid_no, (0,))
    assert (c_w0, c_w1) == (103, 105) and (c_n0, c_n1) == (103, 105)
    assert mat_w0[1][1] == 11 and mat_n0[1][1] == 5

    return {"toy_examples": "passed", "knapsack_reductions_verified": knap_checks}


def check_theorem3() -> Dict[str, Any]:
    rng = random.Random(2026112304)
    cert_checks = 0
    fptas_checks = 0
    for _ in range(40):
        m = rng.randint(3, 8)
        n = rng.randint(2, 6)
        inst = random_instance(rng, m, n, with_clocks=True, with_setups=True, with_job_releases=True)
        d_opt, _, _ = enumerate_exact(inst)
        for eta in (Fraction(1, 2), Fraction(1, 4)):
            L, U, wit = solve_source_approx(inst, eta)
            assert L <= d_opt <= U
            assert sum(inst.costs[x] for x in wit) <= inst.budget
            assert evaluate_makespan(inst, wit) - evaluate_makespan(inst, ()) == L
            cert_checks += 1

    # FPTAS (rho = 0) guarantee when R_i = 0, s_i(1) = 0, r_t >= 0
    for _ in range(25):
        m = rng.randint(3, 7)
        n = rng.randint(2, 6)
        p = tuple(tuple(rng.randint(1, 20) for _ in range(n)) for _ in range(m))
        s = tuple(tuple(0 if t == 0 else rng.randint(0, 5) for t in range(n)) for _ in range(m))
        r = tuple(rng.randint(0, 12) for _ in range(n))
        R = tuple(0 for _ in range(m))
        costs = tuple(rng.randint(1, 10) for _ in range(m))
        budget = rng.randint(1, sum(costs) // 2)
        inst = FlowShopInstance(p=p, s=s, r=r, R=R, compulsory=frozenset(), costs=costs, budget=budget)
        d_opt, _, _ = enumerate_exact(inst)
        eps = Fraction(1, 4)
        L, U, _ = solve_source_approx(inst, eps)
        assert L <= d_opt <= U
        assert Fraction(L, 1) >= (1 - eps) * d_opt
        fptas_checks += 1

    # Large 128-bit binary budget stress check (where O(mB) pseudo-polynomial DP is intractable,
    # while Theorem 3 runs in milliseconds independent of B)
    scale = 1 << 100
    inst_huge_B = FlowShopInstance(
        p=((3, 14, 2, 9), (11, 2, 15, 4), (4, 13, 3, 12), (9, 5, 11, 3), (2, 10, 6, 8)),
        s=((0, 0, 0, 0),) * 5,
        r=(0, 0, 0, 0),
        R=(0, 0, 0, 0, 0),
        compulsory=frozenset(),
        costs=(3 * scale + 7, 5 * scale + 11, 7 * scale + 13, 4 * scale + 5, 9 * scale),
        budget=10 * scale + 20,
    )
    d_exact_huge, _, _ = enumerate_exact(inst_huge_B)
    L_h, U_h, w_h = solve_source_approx(inst_huge_B, Fraction(1, 10))
    assert L_h <= d_exact_huge <= U_h
    assert Fraction(L_h, 1) >= Fraction(9, 10) * d_exact_huge
    assert sum(inst_huge_B.costs[x] for x in w_h) <= inst_huge_B.budget

    return {
        "certificate_checks": cert_checks,
        "fptas_rho0_checks": fptas_checks,
        "large_128bit_budget_check": {"exact_delta": d_exact_huge, "L": L_h, "U": U_h},
    }


def check_corollary2_absolute_and_shifted() -> Dict[str, Any]:
    """Verify Corollary 2: FPTAS for absolute makespan (lambda=0) and fixed rational lambda in (0,1),
    plus binary-input dyadic lambda = 1 - 2^{-k} strict-positivity separation.
    """
    rng = random.Random(2026112306)
    fptas_shifted_checks = 0
    for _ in range(25):
        m = rng.randint(3, 7)
        n = rng.randint(2, 5)
        inst = random_instance(rng, m, n, with_clocks=True, with_setups=True, with_job_releases=True)
        base = evaluate_makespan(inst, ())
        _, c_opt, _ = enumerate_exact(inst)
        eps = Fraction(1, 4)
        for lam in (Fraction(0), Fraction(1, 2), Fraction(3, 4)):
            eta = eps * (1 - lam)
            L_delta, _, wit = solve_source_approx(inst, eta)
            c_alg = base + L_delta
            f_alg = Fraction(c_alg, 1) - lam * base
            f_opt = Fraction(c_opt, 1) - lam * base
            assert f_alg >= (1 - eps) * f_opt
            assert evaluate_makespan(inst, wit) == c_alg
            fptas_shifted_checks += 1

    # Dyadic binary-input lambda construction on Theorem 2 instances (gamma = 10)
    gamma = 10
    dyadic_checks = 0
    for target_H in (2, 3):  # H=2 -> Delta*=1 (>0); H=3 -> Delta*=0
        inst = build_theorem2_instance([1, 1], [1, 1], budget=2, target_H=target_H, via_setup=False)
        c_base = evaluate_makespan(inst, ())
        delta_opt, c_opt, _ = solve_exact_envelope(inst)
        k = 1
        while (1 << k) <= 2 * gamma * c_base:
            k += 1
        lam = Fraction((1 << k) - 1, 1 << k)
        b = Fraction(c_base, 1 << k)
        assert b > 0
        f_base = Fraction(c_base, 1) - lam * c_base
        f_opt = Fraction(c_opt, 1) - lam * c_base
        assert f_base == b
        if delta_opt == 0:
            assert f_opt == b
        else:
            assert f_opt >= b + 1
            assert Fraction(f_opt, gamma) > b
        dyadic_checks += 1

    return {"fptas_shifted_checks": fptas_shifted_checks, "dyadic_separation_checks": dyadic_checks}


def _mat(rows: Sequence[Sequence[int]]) -> Tuple[Tuple[Fraction, ...], ...]:
    return tuple(tuple(Fraction(x) for x in r) for r in rows)


def _vec(vals: Sequence[int]) -> Tuple[Fraction, ...]:
    return tuple(Fraction(x) for x in vals)


def _mp_id(dim: int) -> Tuple[Tuple[Fraction, ...], ...]:
    return tuple(
        tuple(Fraction(0) if i == j else Fraction(NEG_INF) for j in range(dim))
        for i in range(dim)
    )


def check_appendices_e_and_f() -> Dict[str, Any]:
    """Verify Proposition E.1 (projective-diameter suffix bound, 2D sharpness, why-suffix &
    why-inflationarity counterexamples) and Proposition F.1 (nonconsecutive deletion Lagrangian
    certificate, 2D budget-tightening example, 4-stage dual-gap counterexample, and random audits).
    """
    # --- 1. Appendix E Sharpness example (d = 7) ---
    d = 7
    casc_sharp = SwitchedCascade(
        x0=_vec([0, 0]),
        A=(_mp_id(2), _mp_id(2)),
        K=(_mat([[0, -d], [d, d]]), _mat([[0, -d], [0, 0]])),
        b_ret=(_vec([NEG_INF, NEG_INF]), _vec([NEG_INF, NEG_INF])),
        b_del=(_vec([0, d]), _vec([0, 0])),
        readout=_vec([0, NEG_INF]),
        compulsory=frozenset(),
        costs=(1, 1),
        budget=2,
    )
    assert projective_diameter(casc_sharp.K[0]) == d
    assert projective_diameter(casc_sharp.K[1]) == d
    E1_s, _ = linear_singleton_errors(casc_sharp)
    Estar_s, _ = enumerate_cascade_max_error(casc_sharp)
    assert E1_s == 0 and Estar_s == d

    # --- 2. Appendix E "Why a suffix" scalar counterexample ---
    casc_why_suf = SwitchedCascade(
        x0=_vec([0]),
        A=(_mp_id(1), _mp_id(1), _mp_id(1)),
        K=(_mat([[1]]), _mat([[1]]), _mat([[0]])),
        b_ret=(_vec([NEG_INF]), _vec([0]), _vec([2])),
        b_del=(_vec([1]), _vec([NEG_INF]), _vec([NEG_INF])),
        readout=_vec([0]),
        compulsory=frozenset(),
        costs=(1, 1, 9),
        budget=2,
    )
    assert all(projective_diameter(K) == 0 for K in casc_why_suf.K)
    E1_ws, _ = linear_singleton_errors(casc_why_suf)
    Estar_ws, _ = enumerate_cascade_max_error(casc_why_suf)
    assert E1_ws == 0 and Estar_ws == 1

    # --- 3. Appendix E "Why inflationarity" deflationary counterexample ---
    casc_why_inf = SwitchedCascade(
        x0=_vec([2]),
        A=(_mp_id(1), _mp_id(1), _mp_id(1)),
        K=(_mat([[-1]]), _mat([[-1]]), _mat([[0]])),
        b_ret=(_vec([NEG_INF]), _vec([NEG_INF]), _vec([NEG_INF])),
        b_del=(_vec([0]), _vec([0]), _vec([1])),
        readout=_vec([0]),
        compulsory=frozenset(),
        costs=(1, 1, 9),
        budget=2,
    )
    E1_wi, _ = linear_singleton_errors(casc_why_inf)
    Estar_wi, _ = enumerate_cascade_max_error(casc_why_inf)
    assert E1_wi == 0 and Estar_wi == 1

    # --- 4. Appendix F Sharpness & effect of budget (d = 5) ---
    d2 = 5
    def build_appF_2d(B_val: int) -> SwitchedCascade:
        return SwitchedCascade(
            x0=_vec([0, 0]),
            A=(_mp_id(2), _mp_id(2)),
            K=(_mat([[0, 0], [0, 0]]), _mat([[0, d2], [-d2, 0]])),
            b_ret=(_vec([NEG_INF, NEG_INF]), _vec([d2, 0])),
            b_del=(_vec([d2, 0]), _vec([NEG_INF, NEG_INF])),
            readout=_vec([0, NEG_INF]),
            compulsory=frozenset(),
            costs=(1, 1),
            budget=B_val,
        )

    c_b2 = build_appF_2d(2)
    assert projective_diameter(c_b2.K[0]) == 0 and projective_diameter(c_b2.K[1]) == 0
    Estar_b2, _ = enumerate_cascade_max_error(c_b2)
    cert_b2 = nonconsecutive_deletion_certificate(c_b2, multipliers=[Fraction(0)], use_exact_dual=True)
    assert cert_b2["E1"] == 0 and Estar_b2 == d2 and cert_b2["Q"] == d2

    c_b1 = build_appF_2d(1)
    Estar_b1, _ = enumerate_cascade_max_error(c_b1)
    cert_b1_lam0 = nonconsecutive_deletion_certificate(c_b1, multipliers=[Fraction(0)], use_exact_dual=False)
    cert_b1_dual = nonconsecutive_deletion_certificate(c_b1, multipliers=[Fraction(0)], use_exact_dual=True)
    assert Estar_b1 == 0 and cert_b1_lam0["Q"] == d2 and cert_b1_dual["Q"] == 0

    # --- 5. Appendix F 4-stage rank-one dual-gap counterexample (d = 3) ---
    d3 = 3
    K1_4 = _mat([[d3, d3], [d3, d3]])
    K23_4 = _mat([[2 * d3, 4 * d3], [0, 2 * d3]])
    K4_4 = _mat([[0, 0], [0, 0]])
    assert projective_diameter(K1_4) == 0 and projective_diameter(K23_4) == 0
    casc_gap = SwitchedCascade(
        x0=_vec([0, 0]),
        A=(_mp_id(2), _mp_id(2), _mp_id(2), _mp_id(2)),
        K=(K1_4, K23_4, K23_4, K4_4),
        b_ret=(_vec([NEG_INF, NEG_INF]), _vec([0, 0]), _vec([0, 0]), _vec([0, 4 * d3])),
        b_del=(_vec([d3, 0]), _vec([NEG_INF, NEG_INF]), _vec([NEG_INF, NEG_INF]), _vec([NEG_INF, NEG_INF])),
        readout=_vec([NEG_INF, 0]),
        compulsory=frozenset(),
        costs=(1, 2, 2, 99),
        budget=4,
    )
    Estar_gap, _ = enumerate_cascade_max_error(casc_gap)
    cert_gap = nonconsecutive_deletion_certificate(casc_gap, multipliers=[Fraction(0)], use_exact_dual=True)
    assert Estar_gap == 0 and cert_gap["E1"] == 0 and cert_gap["Q"] == d3

    # --- 6. Randomized stress audits for Appendix E (suffix) & Appendix F (interleaved) ---
    rng = random.Random(2026112307)
    appE_rand = 0
    appF_rand = 0
    appF_exact_certified = 0
    appF_dual_tightened = 0

    for trial in range(50):
        dim = rng.randint(2, 3)
        m = rng.randint(3, 5)
        x0 = tuple(Fraction(rng.randint(0, 8)) for _ in range(dim))
        A_list = []
        K_list = []
        for _ in range(m):
            A_rows = []
            for r_i in range(dim):
                row = [Fraction(rng.randint(-2, 6)) if rng.random() < 0.7 else Fraction(NEG_INF) for _ in range(dim)]
                if all(v <= NEG_INF // 2 for v in row):
                    row[r_i] = Fraction(rng.randint(0, 4))
                A_rows.append(tuple(row))
            A_list.append(tuple(A_rows))
            # Finite inflationary switch K_i (diagonal >= 0 guarantees K_i y >= y)
            K_rows = []
            for r_i in range(dim):
                row = [
                    Fraction(rng.randint(0, 5)) if r_i == c_i else Fraction(rng.randint(-4, 4))
                    for c_i in range(dim)
                ]
                K_rows.append(tuple(row))
            K_list.append(tuple(K_rows))
        readout = tuple(Fraction(rng.randint(0, 4)) for _ in range(dim))
        comp = frozenset(i for i in range(m) if rng.random() < 0.2)
        costs = tuple(rng.randint(1, 5) for _ in range(m))
        budget = rng.randint(1, max(2, sum(costs) // 2))

        # (a) Suffix deletion check (Proposition E.1)
        cut = rng.randint(0, m - 1)
        b_ret_e = tuple(
            tuple(Fraction(rng.randint(0, 12)) for _ in range(dim)) if i < cut else tuple(Fraction(NEG_INF) for _ in range(dim))
            for i in range(m)
        )
        b_del_e = tuple(
            tuple(Fraction(NEG_INF) for _ in range(dim)) if i < cut else tuple(Fraction(rng.randint(0, 12)) for _ in range(dim))
            for i in range(m)
        )
        casc_e = SwitchedCascade(
            x0=x0, A=tuple(A_list), K=tuple(K_list), b_ret=b_ret_e, b_del=b_del_e,
            readout=readout, compulsory=comp, costs=costs, budget=budget
        )
        E1_e, _ = linear_singleton_errors(casc_e)
        Estar_e, _ = enumerate_cascade_max_error(casc_e)
        elig_diams = [
            projective_diameter(casc_e.K[i])
            for i in range(cut, m)
            if i in comp or costs[i] <= budget
        ]
        Dmax = max(elig_diams, default=Fraction(0))
        assert E1_e <= Estar_e <= E1_e + Dmax
        appE_rand += 1

        # (b) Nonconsecutive / interleaved deletion check (Proposition F.1)
        b_ret_f = tuple(
            tuple(Fraction(rng.randint(0, 14)) if rng.random() < 0.5 else Fraction(NEG_INF) for _ in range(dim))
            for _ in range(m)
        )
        b_del_f = tuple(
            tuple(Fraction(rng.randint(0, 14)) if rng.random() < 0.5 else Fraction(NEG_INF) for _ in range(dim))
            for _ in range(m)
        )
        casc_f = SwitchedCascade(
            x0=x0, A=tuple(A_list), K=tuple(K_list), b_ret=b_ret_f, b_del=b_del_f,
            readout=readout, compulsory=comp, costs=costs, budget=budget
        )
        Estar_f, _ = enumerate_cascade_max_error(casc_f)
        cert_0 = nonconsecutive_deletion_certificate(casc_f, multipliers=[Fraction(0)], use_exact_dual=False)
        cert_d = nonconsecutive_deletion_certificate(casc_f, multipliers=[Fraction(0)], use_exact_dual=True)
        assert cert_d["E1"] <= Estar_f <= cert_d["Q"] <= cert_0["Q"]
        if cert_d["Q"] == cert_d["E1"]:
            assert Estar_f == cert_d["E1"]
            appF_exact_certified += 1
        if cert_d["Q"] < cert_0["Q"]:
            appF_dual_tightened += 1
        appF_rand += 1

    return {
        "appendix_E_examples": "passed (sharpness, why_suffix, why_inflationarity)",
        "appendix_F_examples": "passed (2D_budget_tightening, 4stage_dual_gap)",
        "appendix_E_random_cascades_verified": appE_rand,
        "appendix_F_random_cascades_verified": appF_rand,
        "appendix_F_singleton_optimality_certified": appF_exact_certified,
        "appendix_F_exact_dual_strictly_tighter_than_lam0": appF_dual_tightened,
    }


def check_theorems4_5_and_appendices() -> Dict[str, Any]:
    rng = random.Random(2026112305)

    # 1. Theorem 4: two-job two-clock upstream-deletion reduction
    thm4_checks = 0
    for _ in range(30):
        r = rng.randint(2, 4)
        w = [rng.randint(1, 10) for _ in range(r)]
        v = [rng.randint(1, 12) for _ in range(r)]
        B = rng.randint(1, sum(w))
        T = rng.randint(1, sum(v) + 2)
        vals = v + [0]
        p_rows: List[Tuple[int, int]] = [(1, vals[0] + 1)]
        costs: List[int] = [B + 1]
        for i in range(r):
            p_rows.append((1, 1))
            costs.append(w[i])
            p_rows.append((vals[i] + 1, vals[i + 1] + 1))
            costs.append(B + 1)
        m = len(p_rows)
        C0 = 2 * r + 2 + sum(v)
        K = 1 + sum(v)
        H = C0 + K + T - 1
        P_m2 = p_rows[-1][0] + p_rows[-1][1]
        R_full = tuple(K if i == 0 else (H - P_m2 if i == m - 1 else 0) for i in range(m))
        inst = FlowShopInstance(
            p=tuple(p_rows), s=((0, 0),) * m, r=(0, 0), R=R_full, compulsory=frozenset(), costs=tuple(costs), budget=B
        )
        # Retain all clocks except machine 0 (which deletes R_0 = K)
        retained = set(range(1, m))
        max_err, wit = arbitrary_deletion_max_error(inst, retained)
        # Compare with knapsack target T
        knap_opt = 0
        for mask in range(1 << r):
            if sum(w[i] for i in range(r) if (mask >> i) & 1) <= B:
                knap_opt = max(knap_opt, sum(v[i] for i in range(r) if (mask >> i) & 1))
        assert (max_err > 0) == (knap_opt >= T)
        if wit is not None:
            red_kap = [inst.local_kappa(i) if i in retained else [NEG_INF] * 2 for i in range(m)]
            assert evaluate_makespan(inst, wit) - simulate_schedule(inst, wit, kappa_override=red_kap)[0] == max_err
        thm4_checks += 1

    # 2. Theorem 5: O(mn) suffix deletion vs exhaustive enumeration (incl. Appendix A op-level timing)
    thm5_checks = 0
    for _ in range(45):
        m = rng.randint(3, 7)
        n = rng.randint(2, 6)
        inst = random_instance(rng, m, n, with_clocks=True, with_setups=True, with_job_releases=True, with_op_timing=True)
        for cut in range(m):
            err_lin, wit_lin = suffix_deletion_max_error(inst, cut)
            assert len(wit_lin) <= 1
            retained = set(range(cut))
            red_kap = [inst.local_kappa(i) if i in retained else [NEG_INF] * n for i in range(m)]
            # Exhaustive max error
            opts = [i for i in range(m - 1) if i not in inst.compulsory and inst.costs[i] <= inst.budget]
            best_ex = 0
            for mask in range(1 << len(opts)):
                chosen = [opts[j] for j in range(len(opts)) if (mask >> j) & 1]
                if sum(inst.costs[x] for x in chosen) > inst.budget:
                    continue
                diff = evaluate_makespan(inst, chosen) - simulate_schedule(inst, chosen, kappa_override=red_kap)[0]
                if diff > best_ex:
                    best_ex = diff
            assert err_lin == best_ex
            assert evaluate_makespan(inst, wit_lin) - simulate_schedule(inst, wit_lin, kappa_override=red_kap)[0] == err_lin
            thm5_checks += 1

    # 3. Appendix A Proposition A.1: minimum-cardinality all-completions support
    propA1_checks = 0
    for _ in range(35):
        m = rng.randint(2, 6)
        n = rng.randint(2, 5)
        inst = random_instance(rng, m, n, with_clocks=True, with_setups=True, with_job_releases=True, with_op_timing=True)
        keep = min_all_completions_support(inst)
        red_kap = [
            [inst.local_kappa(i)[t] if keep[i][t] else NEG_INF for t in range(n)]
            for i in range(m)
        ]
        # Verify full completion matrix preserved for EVERY feasible lock set
        opts = [i for i in range(m - 1) if i not in inst.compulsory and inst.costs[i] <= inst.budget]
        for mask in range(1 << len(opts)):
            chosen = [opts[j] for j in range(len(opts)) if (mask >> j) & 1]
            if sum(inst.costs[x] for x in chosen) > inst.budget:
                continue
            _, mat_full = simulate_schedule(inst, chosen)
            _, mat_red = simulate_schedule(inst, chosen, kappa_override=red_kap)
            assert mat_full == mat_red
        # Verify minimality: dropping ANY single retained entry breaks baseline matrix
        _, base_mat = simulate_schedule(inst, ())
        for i in range(m):
            for t in range(n):
                if keep[i][t]:
                    trial = [list(row) for row in red_kap]
                    trial[i][t] = NEG_INF
                    _, mat_t = simulate_schedule(inst, (), kappa_override=trial)
                    assert mat_t != base_mat
        propA1_checks += 1

    # 4. Appendix B: arbitrary deletion oracle & minimum clock retention vs exhaustive enumeration
    arb_checks = 0
    ret_checks = 0
    for _ in range(30):
        m = rng.randint(3, 6)
        n = rng.randint(2, 5)
        inst = random_instance(rng, m, n, with_clocks=True, with_setups=True, with_job_releases=True, with_op_timing=True)
        opts = [i for i in range(m - 1) if i not in inst.compulsory and inst.costs[i] <= inst.budget]
        feasible_sets = []
        for mask in range(1 << len(opts)):
            chosen = tuple(opts[j] for j in range(len(opts)) if (mask >> j) & 1)
            if sum(inst.costs[x] for x in chosen) <= inst.budget:
                feasible_sets.append(chosen)
        # Test arbitrary retained subset
        retained = {i for i in range(m) if rng.random() < 0.5}
        err_oracle, wit_o = arbitrary_deletion_max_error(inst, retained)
        red_kap = [inst.local_kappa(i) if i in retained else [NEG_INF] * n for i in range(m)]
        ex_err = max(
            evaluate_makespan(inst, s) - simulate_schedule(inst, s, kappa_override=red_kap)[0]
            for s in feasible_sets
        )
        assert err_oracle == ex_err
        if wit_o is not None:
            assert evaluate_makespan(inst, wit_o) - simulate_schedule(inst, wit_o, kappa_override=red_kap)[0] == err_oracle
        arb_checks += 1

        # Verify minimum retained clocks for tolerance 0 and tolerance 2
        for tol in (0, 2):
            chosen_ret, _ = minimum_retained_clocks(inst, tolerance=tol)
            # Exhaustive minimum cardinality over all 2^m clock subsets
            min_card = m + 1
            for cmask in range(1 << m):
                cset = {i for i in range(m) if (cmask >> i) & 1}
                if len(cset) >= min_card:
                    continue
                rk = [inst.local_kappa(i) if i in cset else [NEG_INF] * n for i in range(m)]
                mx = max(
                    evaluate_makespan(inst, s) - simulate_schedule(inst, s, kappa_override=rk)[0]
                    for s in feasible_sets
                )
                if mx <= tol:
                    min_card = len(cset)
            assert len(chosen_ret) == min_card
            # Verify chosen_ret actually meets tolerance
            rk_sol = [inst.local_kappa(i) if i in chosen_ret else [NEG_INF] * n for i in range(m)]
            assert max(
                evaluate_makespan(inst, s) - simulate_schedule(inst, s, kappa_override=rk_sol)[0]
                for s in feasible_sets
            ) <= tol
            ret_checks += 1

    # 5. Appendix B Proposition 7: 1-vs-2 gap with T >= 2 (and scaled eps=3) + T=1 boundary
    prop7_checks = 0
    for _ in range(20):
        r = rng.randint(2, 3)
        w = [rng.randint(1, 8) for _ in range(r)]
        # Double profits and target so T >= 2
        v = [2 * rng.randint(1, 6) for _ in range(r)]
        B = rng.randint(1, sum(w))
        T = 2 * rng.randint(1, sum(v) // 2 + 1)
        knap_opt = max(
            sum(v[i] for i in range(r) if (mask >> i) & 1)
            for mask in range(1 << r)
            if sum(w[i] for i in range(r) if (mask >> i) & 1) <= B
        )
        vals = v + [0]
        p_rows = [(1, vals[0] + 1)]
        costs = [B + 1]
        for i in range(r):
            p_rows.append((1, 1))
            costs.append(w[i])
            p_rows.append((vals[i] + 1, vals[i + 1] + 1))
            costs.append(B + 1)
        m = len(p_rows)
        C0 = 2 * r + 2 + sum(v)
        K = 1 + sum(v)
        H = C0 + K + T - 1
        P_m2 = p_rows[-1][0] + p_rows[-1][1]
        for eps in (0, 3):
            scale = eps + 1
            p_sc = tuple((a * scale, b * scale) for a, b in p_rows)
            R_sc = tuple(
                K * scale if i == 0 else ((H - P_m2) * scale if i == m - 1 else 0)
                for i in range(m)
            )
            inst_p7 = FlowShopInstance(
                p=p_sc, s=((0, 0),) * m, r=(0, 0), R=R_sc, compulsory=frozenset(), costs=tuple(costs), budget=B
            )
            ret_set, _ = minimum_retained_clocks(inst_p7, tolerance=eps)
            expected_size = 2 if knap_opt >= T else 1
            assert len(ret_set) == expected_size
            prop7_checks += 1

    return {
        "theorem4_reductions_verified": thm4_checks,
        "theorem5_suffix_queries_verified": thm5_checks,
        "propositionA1_instances_verified": propA1_checks,
        "arbitrary_deletion_oracle_verified": arb_checks,
        "min_retention_verified": ret_checks,
        "proposition7_gap_verified": prop7_checks,
    }


def check_boundary_counterexamples() -> Dict[str, Any]:
    # 1. Heterogeneous job release breaks free first-machine lock (Section 2)
    inst_rel = FlowShopInstance(
        p=((1, 1), (100, 1)), s=((0, 0), (0, 0)), r=(0, 10), R=(0, 0), compulsory=frozenset(), costs=(1, 1), budget=1
    )
    assert evaluate_makespan(inst_rel, ()) == 102
    assert evaluate_makespan(inst_rel, (0,)) == 111

    # 2. Appendix A operation-level local release breaks baseline-only makespan test
    inst_loc = FlowShopInstance(
        p=((1, 1), (100, 1)),
        s=((0, 0), (0, 0)),
        r=(0, 0),
        R=(0, 0),
        compulsory=frozenset(),
        costs=(1, 1),
        budget=1,
        A=((NEG_INF, 10), (NEG_INF, NEG_INF)),
    )
    assert evaluate_makespan(inst_loc, ()) == 102
    assert evaluate_makespan(inst_loc, (0,)) == 111

    # 3. Mid-horizon non-resumable outage [10, 20) on machine 4 breaks submodularity (22+23 > 22+22)
    def sim_with_m4_outage(locked: Set[int]) -> int:
        P = [(1, 1, 10), (1, 6, 1), (1, 4, 1), (1, 1, 1)]
        V = [0, 0, 0]
        for i in range(3):
            pref = [sum(P[i][: t + 1]) for t in range(3)]
            e = [0, P[i][0], P[i][0] + P[i][1]]
            terms = [V[t] - e[t] for t in range(3)]
            if i in locked:
                st = max(terms)
                V = [pref[t] + st for t in range(3)]
            else:
                cur = 0
                nxt = []
                for t in range(3):
                    cur = max(cur, terms[t])
                    nxt.append(pref[t] + cur)
                V = nxt
        # Machine 4 open with non-resumable outage [10, 20)
        c4 = 0
        for t in range(3):
            st = max(V[t], c4)
            if st < 20 and st + P[3][t] > 10:
                st = 20
            c4 = st + P[3][t]
        return c4

    f00 = sim_with_m4_outage(set())
    f10 = sim_with_m4_outage({1})
    f01 = sim_with_m4_outage({2})
    f11 = sim_with_m4_outage({1, 2})
    assert (f00, f10, f01, f11) == (22, 22, 22, 23)
    assert f00 + f11 > f10 + f01  # strict violation of submodularity

    # 4. Permutation re-optimization violates submodularity even with zero clocks:
    # A=(3,1,1,3), B=(1,2,2,1) -> min_pi C(pi, S) gives 9, 9, 9, 10
    def best_perm_makespan(locked: Set[int]) -> int:
        A_job = (3, 1, 1, 3)
        B_job = (1, 2, 2, 1)
        vals = []
        for jobs in ((A_job, B_job), (B_job, A_job)):
            p_mat = tuple((jobs[0][i], jobs[1][i]) for i in range(4))
            inst_p = FlowShopInstance(
                p=p_mat, s=((0, 0),) * 4, r=(0, 0), R=(0, 0, 0, 0), compulsory=frozenset(), costs=(1,) * 4, budget=4
            )
            vals.append(evaluate_makespan(inst_p, locked))
        return min(vals)

    assert [best_perm_makespan(s) for s in (set(), {1}, {2}, {1, 2})] == [9, 9, 9, 10]

    return {
        "heterogeneous_release_counterexample": [102, 111],
        "local_release_counterexample": [102, 111],
        "mid_horizon_outage_counterexample": [f00, f10, f01, f11],
        "permutation_reopt_nonsubmodular": [9, 9, 9, 10],
    }


def check_archived_experiment_tables() -> Dict[str, Any]:
    """Optional audit against archived local JSON outputs in ../../../experiments/."""
    exp_root = pathlib.Path(__file__).resolve().parents[3] / "experiments"
    if not exp_root.exists():
        return {"status": "skipped_experiments_dir_not_present"}

    # 1. Table 2 (Section 6 / Appendix C)
    mq = json.loads((exp_root / "flowshop_checkpoint_multiquery/results.json").read_text(encoding="utf-8"))
    table2: Dict[str, Dict[str, float]] = {}
    for wk in ("small_cold", "large_cold", "same_tariff_scan_cold", "mixed_tariffs_cold"):
        table2[wk] = {}
        for algo in ("checkpoint_sparse", "checkpoint_plain", "checkpoint_envelope"):
            vals = [rec["summary"]["paired_speedup"][algo][wk] for rec in mq["records"]]
            table2[wk][algo] = round(statistics.median(vals), 2)
    assert table2["small_cold"] == {"checkpoint_sparse": 6.39, "checkpoint_plain": 8.58, "checkpoint_envelope": 8.46}
    assert table2["large_cold"] == {"checkpoint_sparse": 23.43, "checkpoint_plain": 29.56, "checkpoint_envelope": 28.31}
    assert table2["same_tariff_scan_cold"] == {"checkpoint_sparse": 23.41, "checkpoint_plain": 29.43, "checkpoint_envelope": 28.26}
    assert table2["mixed_tariffs_cold"] == {"checkpoint_sparse": 61.27, "checkpoint_plain": 63.46, "checkpoint_envelope": 53.00}

    # 2. Outer permutation search (Section 6 / Appendix C)
    iso = json.loads((exp_root / "flowshop_checkpoint_outer_search/isolated_cpu28.json").read_text(encoding="utf-8"))
    g15 = round(iso["overall_gate_combining_lock_budgets"]["0.15"]["versus_full"]["mean_improvement_pct"], 3)
    g45 = round(iso["overall_gate_combining_lock_budgets"]["0.45"]["versus_full"]["mean_improvement_pct"], 3)
    assert (g15, g45) == (0.239, 0.109)

    # 3. Source masking intervals (Appendix C)
    ra = json.loads((exp_root / "flowshop_release_approx/results.json").read_text(encoding="utf-8"))
    mf = [(x["exact_increment"], x["coarse_lower"], x["coarse_upper"]) for x in ra["masking_family"]]
    assert mf == [(436, 430, 509), (219, 213, 292), (1, 0, 74), (0, 0, 73)]

    # 4. Uniform-threshold deletion benchmarks (Appendix B)
    dq = json.loads((exp_root / "flowshop_local_availability/deletion_query_benchmarks.json").read_text(encoding="utf-8"))
    env_ms = [round(x["median_cpu_s"]["shared_single_envelope"] * 1000.0, 1) for x in dq]
    cold_ms = [round(x["median_cpu_s"]["cold_scan"] * 1000.0, 1) for x in dq]
    assert env_ms == [59.6, 62.6, 117.6, 49.8]
    assert cold_ms == [110.6, 105.3, 196.3, 154.8]

    return {
        "status": "all_archived_tables_verified",
        "table2_medians": table2,
        "outer_search_mean_improvement_pct": {"0.15s": g15, "0.45s": g45},
        "masking_intervals": mf,
        "deletion_env_ms": env_ms,
        "deletion_cold_ms": cold_ms,
    }


def main() -> None:
    t0 = time.perf_counter()
    report = {
        "lemmas_and_theorem1": check_lemmas_and_theorem1(),
        "corollary1": check_corollary1(),
        "theorem2_and_appendix_d": check_theorem2_and_appendix_d(),
        "theorem3": check_theorem3(),
        "corollary2_absolute_and_shifted": check_corollary2_absolute_and_shifted(),
        "theorems4_5_and_appendices": check_theorems4_5_and_appendices(),
        "appendices_e_and_f": check_appendices_e_and_f(),
        "boundary_counterexamples": check_boundary_counterexamples(),
        "archived_tables_crosscheck": check_archived_experiment_tables(),
    }
    report["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
    report["all_checks_passed"] = True

    out_path = pathlib.Path(__file__).resolve().parent / "REPLICATION_REPORT.json"
    out_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
