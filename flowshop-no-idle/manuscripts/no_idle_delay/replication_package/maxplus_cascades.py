"""Reference implementation for Appendices E and F:
General switched max-plus cascades, projective-diameter suffix deletion bounds
(Proposition E.1), and Lagrangian budget error certificates for nonconsecutive
clock deletion (Proposition F.1) including exact 1D convex dual minimization.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

from flowshop_core import NEG_INF


def _add(a: Fraction, b: Fraction) -> Fraction:
    if a <= NEG_INF // 2 or b <= NEG_INF // 2:
        return Fraction(NEG_INF)
    return a + b


def mp_mat_vec(M: Sequence[Sequence[Fraction]], x: Sequence[Fraction]) -> List[Fraction]:
    out: List[Fraction] = []
    for row in M:
        best = Fraction(NEG_INF)
        for a, b in zip(row, x):
            v = _add(a, b)
            if v > best:
                best = v
        out.append(best)
    return out


def mp_row_mat(r: Sequence[Fraction], M: Sequence[Sequence[Fraction]]) -> List[Fraction]:
    ncols = len(M[0])
    out: List[Fraction] = []
    for j in range(ncols):
        best = Fraction(NEG_INF)
        for i, rv in enumerate(r):
            v = _add(rv, M[i][j])
            if v > best:
                best = v
        out.append(best)
    return out


def mp_dot(r: Sequence[Fraction], x: Sequence[Fraction]) -> Fraction:
    best = Fraction(NEG_INF)
    for a, b in zip(r, x):
        v = _add(a, b)
        if v > best:
            best = v
    return best


def projective_diameter(K: Sequence[Sequence[Fraction]]) -> Fraction:
    """D(K) = max_{r,s,p,q} (K_{rp} + K_{sq} - K_{rq} - K_{sp}) for finite K."""
    nrows = len(K)
    ncols = len(K[0])
    best = Fraction(0)
    for r in range(nrows):
        for s in range(nrows):
            if r == s:
                continue
            diffs = [K[r][p] - K[s][p] for p in range(ncols)]
            span = max(diffs) - min(diffs)
            if span > best:
                best = span
    return best


@dataclass(frozen=True)
class SwitchedCascade:
    """Feedforward switched max-plus cascade (Appendices E and F)."""

    x0: Tuple[Fraction, ...]
    A: Tuple[Tuple[Tuple[Fraction, ...], ...], ...]  # m stages
    K: Tuple[Tuple[Tuple[Fraction, ...], ...], ...]  # m finite switch matrices
    b_ret: Tuple[Tuple[Fraction, ...], ...]          # retained clock vectors (NEG_INF where absent)
    b_del: Tuple[Tuple[Fraction, ...], ...]          # deleted clock vectors (NEG_INF where absent)
    readout: Tuple[Fraction, ...]                    # max-plus linear readout row vector
    compulsory: frozenset[int]
    costs: Tuple[int, ...]                           # nonnegative integer costs
    budget: int

    @property
    def m(self) -> int:
        return len(self.A)

    def b_full(self, i: int) -> List[Fraction]:
        return [max(a, b) for a, b in zip(self.b_ret[i], self.b_del[i])]

    def simulate(self, selected: Iterable[int], reduced: bool = False) -> Tuple[Fraction, List[List[Fraction]]]:
        locked = set(self.compulsory) | set(selected)
        x = list(self.x0)
        states: List[List[Fraction]] = []
        for i in range(self.m):
            Ax = mp_mat_vec(self.A[i], x)
            bi = list(self.b_ret[i]) if reduced else self.b_full(i)
            y = [max(u, v) for u, v in zip(Ax, bi)]
            x = mp_mat_vec(self.K[i], y) if i in locked else y
            states.append(x)
        return mp_dot(self.readout, x), states

    def error(self, selected: Iterable[int]) -> Fraction:
        return self.simulate(selected, reduced=False)[0] - self.simulate(selected, reduced=True)[0]


def enumerate_cascade_max_error(casc: SwitchedCascade) -> Tuple[Fraction, Tuple[int, ...]]:
    opts = [i for i in range(casc.m) if i not in casc.compulsory and casc.costs[i] <= casc.budget]
    best_e = casc.error(())
    best_s: Tuple[int, ...] = ()
    for mask in range(1 << len(opts)):
        chosen = [opts[k] for k in range(len(opts)) if (mask >> k) & 1]
        if sum(casc.costs[x] for x in chosen) > casc.budget:
            continue
        e = casc.error(chosen)
        if e > best_e:
            best_e = e
            best_s = tuple(chosen)
    return best_e, best_s


def linear_singleton_errors(casc: SwitchedCascade) -> Tuple[Fraction, Dict[int, Fraction]]:
    """O(N) forward/backward evaluation of compulsory-only error E_0 and every
    individually affordable singleton error E(S_j) (Appendices E and F).
    """
    m = casc.m
    # Forward compulsory-only sweeps saving open outputs y_i:
    yf: List[List[Fraction]] = []
    yr: List[List[Fraction]] = []
    xf = list(casc.x0)
    xr = list(casc.x0)
    for i in range(m):
        Axf = mp_mat_vec(casc.A[i], xf)
        Axr = mp_mat_vec(casc.A[i], xr)
        y_fi = [max(u, v) for u, v in zip(Axf, casc.b_full(i))]
        y_ri = [max(u, v) for u, v in zip(Axr, casc.b_ret[i])]
        yf.append(y_fi)
        yr.append(y_ri)
        if i in casc.compulsory:
            xf = mp_mat_vec(casc.K[i], y_fi)
            xr = mp_mat_vec(casc.K[i], y_ri)
        else:
            xf, xr = y_fi, y_ri

    e0 = mp_dot(casc.readout, xf) - mp_dot(casc.readout, xr)

    # Single common backward sweep computing suffix row H_j (after stage j) and later clock scalars
    row = list(casc.readout)
    sf = Fraction(NEG_INF)  # full clocks strictly after current stage
    sr = Fraction(NEG_INF)  # retained clocks strictly after current stage
    singleton_err: Dict[int, Fraction] = {}

    for i in range(m - 1, -1, -1):
        # Evaluate candidate stage i (uses row mapping x_i -> terminal observation, plus sf/sr)
        if i in casc.compulsory:
            singleton_err[i] = e0
        elif casc.costs[i] <= casc.budget:
            cf = max(mp_dot(row, mp_mat_vec(casc.K[i], yf[i])), sf)
            cr = max(mp_dot(row, mp_mat_vec(casc.K[i], yr[i])), sr)
            singleton_err[i] = cf - cr
        # Propagate backward across stage i (compulsory-only mode)
        row_y = mp_row_mat(row, casc.K[i]) if i in casc.compulsory else row
        sf = max(sf, mp_dot(row_y, casc.b_full(i)))
        sr = max(sr, mp_dot(row_y, casc.b_ret[i]))
        row = mp_row_mat(row_y, casc.A[i])

    E1 = max([e0] + list(singleton_err.values()))
    return E1, singleton_err


def lagrangian_backward_eval(
    casc: SwitchedCascade, lam: Fraction
) -> List[List[Fraction]]:
    """Compute penalized backward rows R_j^lam (just after stage j) for all j=0..m-1 in O(N)."""
    m = casc.m
    rows: List[List[Fraction]] = [[] for _ in range(m)]
    row = list(casc.readout)
    for i in range(m - 1, -1, -1):
        rows[i] = list(row)
        if i in casc.compulsory:
            row = mp_row_mat(mp_row_mat(row, casc.K[i]), casc.A[i])
        elif casc.costs[i] <= casc.budget:
            r_open = mp_row_mat(row, casc.A[i])
            r_lock = mp_row_mat(mp_row_mat(row, casc.K[i]), casc.A[i])
            pen = lam * casc.costs[i]
            row = [max(o, _add(l, -pen)) for o, l in zip(r_open, r_lock)]
        else:
            row = mp_row_mat(row, casc.A[i])
    return rows


def exact_lagrangian_bound_for_stage(
    casc: SwitchedCascade, j: int, U_j: Sequence[Fraction], rem_budget: int
) -> Tuple[Fraction, Fraction]:
    """Exact 1D convex minimization of phi_j(lam) = R_j^lam U_j + lam * rem_budget over lam >= 0
    using Handler-Zang (1980) chord search over exact rational breakpoints.
    Returns (best_F_j, optimal_lambda).
    """
    m = casc.m

    def eval_with_subgrad(lam: Fraction) -> Tuple[Fraction, int, Fraction]:
        """Return (phi(lam), cost_of_maximizing_suffix_T, raw_H(T))."""
        # Backward DP storing (best_penalized_val, cost_sum, raw_H_val) per coordinate at each stage
        # Wait: standard backward row gives R_i^lam; forward greedy backtracking from U_j recovers
        # exact maximizing suffix selection T*(lam) in O(N)!
        rows = lagrangian_backward_eval(casc, lam)
        # Forward trace from stage j+1 to m-1 with vector x = U_j:
        # At each optional stage i > j, pick K_i iff R_i^lam(K_i A_i x) - lam*c_i >= R_i^lam(A_i x)
        # (Wait: because R_i^lam is max-plus linear, max_T (H_j^T(x) - lam c(T)) decomposes stage-by-stage
        # ONLY along an optimal coordinate path! Let's backtrack exact maximizing (coord, T) cleanly!)
        # Actually, backward pass computes exact R_j^lam; to extract exact (H_j^T(U_j), c(T)),
        # note we only need to track along the optimal switch sequence via forward DP on stage-coord pairs:
        # Even cleaner: R_j^lam U_j is attained by a specific suffix subset T; since we have the exact
        # backward rows R_i^lam, the exact value is R_j^lam U_j, and a maximizing T is obtained by
        # choosing at each optional stage i whether K_i improves R_i^lam(x) by >= lam * c_i!
        # Let's verify: by max-plus linearity of R_i^lam, R_i^lam(K_i y) = max_r (R_i^lam[r] + (K_i y)[r]),
        # and R_{i-1}^lam(x) = max(R_i^lam(A_i x), R_i^lam(K_i A_i x) - lam*c_i) — YES, that's exact!
        x = list(U_j)
        tot_cost = 0
        for i in range(j + 1, m):
            y = mp_mat_vec(casc.A[i], x)
            if i in casc.compulsory:
                x = mp_mat_vec(casc.K[i], y)
            elif casc.costs[i] <= casc.budget:
                x_lock = mp_mat_vec(casc.K[i], y)
                v_open = mp_dot(rows[i], y)
                v_lock = _add(mp_dot(rows[i], x_lock), -lam * casc.costs[i])
                if v_lock > v_open:
                    x = x_lock
                    tot_cost += casc.costs[i]
                else:
                    x = y
            else:
                x = y
        raw_h = mp_dot(casc.readout, x)
        phi = raw_h - lam * tot_cost + lam * rem_budget
        # Verify exact equality with backward evaluation R_j^lam U_j + lam * rem_budget
        phi_back = mp_dot(rows[j], U_j) + lam * rem_budget
        assert phi == phi_back, f"Backtrack mismatch: {phi} vs {phi_back}"
        return phi, tot_cost, raw_h

    # Evaluate at lam = 0 (all individually affordable switches selected)
    phi0, c0, h0 = eval_with_subgrad(Fraction(0))
    if c0 <= rem_budget:
        return phi0, Fraction(0)

    # Evaluate at lam_hi sufficiently large that no optional switch is taken (T = empty)
    # Upper bound on gain per unit cost: (h0 - h_empty) / min_pos_cost
    x_empty = list(U_j)
    for i in range(j + 1, m):
        y = mp_mat_vec(casc.A[i], x_empty)
        x_empty = mp_mat_vec(casc.K[i], y) if i in casc.compulsory else y
    h_empty = mp_dot(casc.readout, x_empty)
    min_pos_c = min(
        (casc.costs[i] for i in range(j + 1, m) if i not in casc.compulsory and 0 < casc.costs[i] <= casc.budget),
        default=1,
    )
    lam_hi = max(Fraction(1), Fraction(h0 - h_empty + 1, min_pos_c))
    phi_hi, c_hi, h_hi = eval_with_subgrad(lam_hi)

    best_phi, best_lam = (phi0, Fraction(0)) if phi0 <= phi_hi else (phi_hi, lam_hi)
    # Chord search (Handler-Zang 1980): maintain left point (c_L > rem_budget, h_L) and right (c_R <= rem_budget, h_R)
    c_L, h_L = c0, h0
    c_R, h_R = c_hi, h_hi
    if c_R > rem_budget:
        # Even at lam_hi, zero-cost switches exceeded? Impossible since zero-cost has c=0 <= rem_budget
        return best_phi, best_lam

    for _ in range(64):
        if c_L == c_R:
            break
        lam_mid = Fraction(h_L - h_R, c_L - c_R)
        phi_m, c_m, h_m = eval_with_subgrad(lam_mid)
        if phi_m < best_phi:
            best_phi, best_lam = phi_m, lam_mid
        # Check if (h_m, c_m) lies on the chord connecting L and R -> exact optimum reached!
        if h_m - lam_mid * c_m == h_L - lam_mid * c_L:
            break
        if c_m > rem_budget:
            c_L, h_L = c_m, h_m
        else:
            c_R, h_R = c_m, h_m
    return best_phi, best_lam


def nonconsecutive_deletion_certificate(
    casc: SwitchedCascade,
    multipliers: Optional[Sequence[Fraction]] = None,
    use_exact_dual: bool = True,
) -> Dict[str, object]:
    """Proposition F.1 certificate Q >= E* with optional exact Handler-Zang dual minimization."""
    m = casc.m
    E1, singleton_err = linear_singleton_errors(casc)

    # Forward pass for U_j (pooled deleted inputs since previous compulsory stage) and V_j (reduced state under S_j)
    U_list: List[Optional[List[Fraction]]] = [None] * m
    V_list: List[Optional[List[Fraction]]] = [None] * m
    d_state = [Fraction(NEG_INF)] * len(casc.x0)
    xr = list(casc.x0)
    for i in range(m):
        # Deleted-source open update
        Ad = mp_mat_vec(casc.A[i], d_state)
        yd = [max(u, v) for u, v in zip(Ad, casc.b_del[i])]
        # Reduced compulsory-only open update
        Axr = mp_mat_vec(casc.A[i], xr)
        yr = [max(u, v) for u, v in zip(Axr, casc.b_ret[i])]

        if i in casc.compulsory or casc.costs[i] <= casc.budget:
            if any(v > NEG_INF // 2 for v in yd):
                U_list[i] = mp_mat_vec(casc.K[i], yd)
            V_list[i] = mp_mat_vec(casc.K[i], yr)

        if i in casc.compulsory:
            xr = mp_mat_vec(casc.K[i], yr)
            # Clear deleted-source state after recording compulsory candidate
            d_state = [Fraction(NEG_INF)] * len(casc.x0)
        else:
            xr = yr
            d_state = yd

    # Backward compulsory-only pass for H_j (row) and C_j (retained clocks strictly after j)
    H_rows: List[List[Fraction]] = [[] for _ in range(m)]
    C_after: List[Fraction] = [Fraction(NEG_INF)] * m
    row = list(casc.readout)
    sr = Fraction(NEG_INF)
    for i in range(m - 1, -1, -1):
        H_rows[i] = list(row)
        C_after[i] = sr
        row_y = mp_row_mat(row, casc.K[i]) if i in casc.compulsory else row
        sr = max(sr, mp_dot(row_y, casc.b_ret[i]))
        row = mp_row_mat(row_y, casc.A[i])

    # Precompute fixed multiplier rows if provided
    fixed_rows = [
        (lam, lagrangian_backward_eval(casc, lam))
        for lam in (multipliers if multipliers is not None else [Fraction(0)])
    ]

    Q = E1
    per_stage: Dict[int, Dict[str, Fraction]] = {}
    for j in range(m):
        Uj = U_list[j]
        Vj = V_list[j]
        if Uj is None or Vj is None:
            continue
        cj = 0 if j in casc.compulsory else casc.costs[j]
        rem_B = casc.budget - cj
        gj = max(u - v for u, v in zip(Uj, Vj))
        Cj = C_after[j]
        Hj_U = mp_dot(H_rows[j], Uj)

        best_F = min(mp_dot(rows[j], Uj) + lam * rem_B for lam, rows in fixed_rows)
        if use_exact_dual:
            F_exact, _ = exact_lagrangian_bound_for_stage(casc, j, Uj, rem_B)
            if F_exact < best_F:
                best_F = F_exact

        if Cj > NEG_INF // 2:
            qj = min(gj, best_F - Cj)
            aj = best_F - Hj_U
        else:
            qj = gj
            aj = Fraction(0)

        # Verify Proposition F.1 additive decomposition q_j <= E(S_j) + max(D(K_j), a_j)
        Dj = projective_diameter(casc.K[j])
        assert qj <= singleton_err[j] + max(Dj, aj), (
            f"Additive decomposition violated at j={j}: qj={qj}, E(Sj)={singleton_err[j]}, Dj={Dj}, aj={aj}"
        )
        per_stage[j] = {"q_j": qj, "g_j": gj, "F_j": best_F, "C_j": Cj, "a_j": aj, "D_j": Dj}
        if qj > Q:
            Q = qj

    return {"E1": E1, "Q": Q, "per_stage": per_stage}
