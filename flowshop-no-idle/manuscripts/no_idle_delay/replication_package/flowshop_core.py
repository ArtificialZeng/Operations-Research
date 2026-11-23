"""Reference implementation for:
'A single availability date changes the approximability of delay in fixed-order flow shops'

Pure Python standard-library implementation (exact arbitrary-precision integer arithmetic,
plus exact rational scaling via fractions.Fraction for Theorem 3) covering:
  - Direct physical operation-level simulator (Section 2 & Appendix A)
  - Machine-index checkpoint graph (a(i,j), b(i,j)), Lemmas 1-2
  - O(mn) submodular singleton detector (Corollary 1)
  - Exact plain and anti-Monge binary-search envelope DP (Theorem 1)
  - Source-wise certified approximation and posterior bounds [L, U] (Theorem 3)
  - O(mn) downstream suffix deletion maximum-error test (Theorem 5)
  - O(mn) all-completions minimum-cardinality local support (Proposition A.1)
  - Uniform-threshold anti-Monge arbitrary clock deletion oracle (Appendix B / Theorem 6)
  - Backward max-plus transpose & exact constraint-generation minimum clock retention (Appendix B)
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

NEG_INF = -(10**30)


@dataclass(frozen=True)
class FlowShopInstance:
    """Fixed-order mixed no-idle flow shop with optional operation-level timing."""

    p: Tuple[Tuple[int, ...], ...]          # m x n processing times >= 0
    s: Tuple[Tuple[int, ...], ...]          # m x n setup times >= 0
    r: Tuple[int, ...]                      # n job release dates at machine 0
    R: Tuple[int, ...]                      # m machine initial availability dates (or NEG_INF if removed)
    compulsory: frozenset[int]              # compulsory no-idle machine indices in {0, ..., m-1}
    costs: Tuple[int, ...]                  # length m; positive integer costs for optional machines
    budget: int                             # integer budget B >= 0
    # Optional Appendix A operation-level extensions (defaults reduce to main-text model):
    d: Optional[Tuple[Tuple[int, ...], ...]] = None      # transport lags d_i(t) >= 0
    A: Optional[Tuple[Tuple[int, ...], ...]] = None      # material availability A_i(t)
    U: Optional[Tuple[Tuple[int, ...], ...]] = None      # setup availability U_i(t)
    ell: Optional[Tuple[Tuple[int, ...], ...]] = None    # setup anticipation allowance in [0, s_i(t)]

    @property
    def m(self) -> int:
        return len(self.p)

    @property
    def n(self) -> int:
        return len(self.p[0])

    def occupied_prefix(self, i: int) -> List[int]:
        acc = 0
        out = []
        for t in range(self.n):
            acc += self.s[i][t] + self.p[i][t]
            out.append(acc)
        return out

    def upstream_offset(self, i: int) -> List[int]:
        """Return E_i(t) - d_i(t) so upstream term is V(t) - offset[t]."""
        acc = 0
        out = []
        for t in range(self.n):
            allow = self.s[i][t] if self.ell is None else self.ell[i][t]
            lag = 0 if self.d is None else self.d[i][t]
            out.append(acc + allow - lag)
            acc += self.s[i][t] + self.p[i][t]
        return out

    def local_kappa(self, i: int) -> List[int]:
        """Merged local lower-bound vector kappa_i(t) (Appendix A)."""
        acc = 0
        out = []
        for t in range(self.n):
            allow = self.s[i][t] if self.ell is None else self.ell[i][t]
            val = self.R[i]
            if self.A is not None and self.A[i][t] > NEG_INF // 2:
                cand = self.A[i][t] - (acc + allow)
                if cand > val:
                    val = cand
            if self.U is not None and self.U[i][t] > NEG_INF // 2:
                cand = self.U[i][t] - acc
                if cand > val:
                    val = cand
            out.append(val)
            acc += self.s[i][t] + self.p[i][t]
        return out

    def effective_cost(self, i: int) -> int:
        """Cost of selecting machine i (0 for compulsory machines or free terminal sink m-1)."""
        if i in self.compulsory or i == self.m - 1:
            return 0
        return self.costs[i]


def simulate_schedule(
    inst: FlowShopInstance,
    selected: Iterable[int],
    kappa_override: Optional[Sequence[Sequence[int]]] = None,
) -> Tuple[int, List[List[int]]]:
    """Direct physical forward simulation returning (makespan, full m x n completion matrix)."""
    m, n = inst.m, inst.n
    locked = set(inst.compulsory) | set(selected)
    V = list(inst.r)
    matrix: List[List[int]] = []
    for i in range(m):
        P = inst.occupied_prefix(i)
        off = inst.upstream_offset(i)
        kap = list(inst.local_kappa(i)) if kappa_override is None else list(kappa_override[i])
        terms = [max(V[t] - off[t], kap[t]) for t in range(n)]
        if i in locked:
            st = max(terms)
            V = [P[t] + st for t in range(n)]
        else:
            cur = NEG_INF
            V_next = []
            for t in range(n):
                if terms[t] > cur:
                    cur = terms[t]
                V_next.append(P[t] + cur)
            V = V_next
        matrix.append(V)
    return V[-1], matrix


def evaluate_makespan(inst: FlowShopInstance, selected: Iterable[int]) -> int:
    return simulate_schedule(inst, selected)[0]


def enumerate_exact(inst: FlowShopInstance) -> Tuple[int, int, Tuple[int, ...]]:
    """Brute-force reference solver over all budget-feasible optional subsets (small m)."""
    base = evaluate_makespan(inst, ())
    opts = [
        i
        for i in range(inst.m - 1)
        if i not in inst.compulsory and inst.costs[i] <= inst.budget
    ]
    best_c = base
    best_set: Tuple[int, ...] = ()
    k = len(opts)
    for mask in range(1 << k):
        cost = 0
        chosen = []
        for idx in range(k):
            if (mask >> idx) & 1:
                mi = opts[idx]
                cost += inst.costs[mi]
                if cost > inst.budget:
                    break
                chosen.append(mi)
        else:
            c = evaluate_makespan(inst, chosen)
            if c > best_c:
                best_c = c
                best_set = tuple(chosen)
    return best_c - base, best_c, best_set


# ---------------------------------------------------------------------------
# Section 2: Machine-index checkpoint graph (a(i,j), b(i,j)) & Theorem 1
# Nodes are indexed 0..m where 0 is virtual job-arrival origin and 1..m are
# physical machines 0..m-1.
# ---------------------------------------------------------------------------

@dataclass
class CheckpointGraph:
    m: int
    compulsory_nodes: List[int]  # sorted mandatory nodes including 0 and m
    intervals: List[Tuple[int, int]]  # consecutive compulsory pairs (L, R)
    a: Dict[Tuple[int, int], int]
    b: Dict[Tuple[int, int], int]
    P_last: int


def build_checkpoint_graph(
    inst: FlowShopInstance,
    kappa_override: Optional[Sequence[Sequence[int]]] = None,
) -> CheckpointGraph:
    """O(m^2 n) preprocessing computing homogeneous a(i,j) and clock floor b(i,j)."""
    m, n = inst.m, inst.n
    P_all = [inst.occupied_prefix(i) for i in range(m)]
    off_all = [inst.upstream_offset(i) for i in range(m)]
    kap_all = (
        [inst.local_kappa(i) for i in range(m)]
        if kappa_override is None
        else [list(row) for row in kappa_override]
    )

    # Nodes: 0 (virtual origin), 1..m (physical machines 0..m-1). Terminal m is always a free sink.
    comp_set = {0, m} | {c + 1 for c in inst.compulsory}
    comp_nodes = sorted(comp_set)
    intervals = [(comp_nodes[idx], comp_nodes[idx + 1]) for idx in range(len(comp_nodes) - 1)]

    a: Dict[Tuple[int, int], int] = {}
    b: Dict[Tuple[int, int], int] = {}

    for left, right in intervals:
        for u in range(left, right):
            # Initial homogeneous vector exiting node u at start shift 0:
            V_hom = list(inst.r) if u == 0 else list(P_all[u - 1])
            # Initial clock-only vector exiting node u (no clocks from u or earlier):
            V_clk = [NEG_INF] * n
            for v in range(u + 1, right + 1):
                mi = v - 1
                P = P_all[mi]
                off = off_all[mi]
                kap = kap_all[mi]
                # Lock start at destination v:
                a_uv = max(V_hom[t] - off[t] for t in range(n))
                b_uv = max(max(V_clk[t] - off[t], kap[t]) for t in range(n))
                a[(u, v)] = a_uv
                b[(u, v)] = b_uv
                if v < right:
                    # Propagate open mode through machine mi:
                    cur_h = NEG_INF
                    cur_c = NEG_INF
                    next_h = []
                    next_c = []
                    for t in range(n):
                        xh = V_hom[t] - off[t]
                        if xh > cur_h:
                            cur_h = xh
                        next_h.append(P[t] + cur_h)
                        xc = max(V_clk[t] - off[t], kap[t])
                        if xc > cur_c:
                            cur_c = xc
                        next_c.append(P[t] + cur_c)
                    V_hom = next_h
                    V_clk = next_c

    return CheckpointGraph(
        m=m,
        compulsory_nodes=comp_nodes,
        intervals=intervals,
        a=a,
        b=b,
        P_last=P_all[m - 1][-1],
    )


def solve_exact_plain(inst: FlowShopInstance, graph: Optional[CheckpointGraph] = None) -> Tuple[int, int, Tuple[int, ...]]:
    """Exact machine-index DP without envelope pruning (O(m^2 (B+1)))."""
    if graph is None:
        graph = build_checkpoint_graph(inst)
    m, B = inst.m, inst.budget
    base = evaluate_makespan(inst, ())
    # D[node][cost] = best start time; pred[node][cost] = (prev_node, prev_cost)
    D: List[Dict[int, int]] = [{} for _ in range(m + 1)]
    pred: List[Dict[int, Tuple[int, int]]] = [{} for _ in range(m + 1)]
    D[0][0] = 0

    for left, right in graph.intervals:
        for v in range(left + 1, right + 1):
            w_v = inst.effective_cost(v - 1)
            if w_v > B:
                continue
            for u in range(left, v):
                a_uv = graph.a[(u, v)]
                b_uv = graph.b[(u, v)]
                for q, val_u in D[u].items():
                    nb = q + w_v
                    if nb > B:
                        continue
                    cand = max(val_u + a_uv, b_uv)
                    if nb not in D[v] or cand > D[v][nb]:
                        D[v][nb] = cand
                        pred[v][nb] = (u, q)

    best_q = max(D[m], key=lambda q: D[m][q])
    best_c = D[m][best_q] + graph.P_last
    # Backtrack optional machines
    witness: List[int] = []
    cur_v, cur_q = m, best_q
    while cur_v > 0:
        if 1 <= cur_v < m and (cur_v - 1) not in inst.compulsory:
            witness.append(cur_v - 1)
        cur_v, cur_q = pred[cur_v][cur_q]
    witness.reverse()
    return best_c - base, best_c, tuple(witness)


class AntiMongeUpperEnvelope:
    """Online upper envelope for anti-Monge matrix f(i, j) = row_const[i] + a(i, j).

    By Lemma 1, for i1 < i2 and j1 < j2:
        a(i1, j1) + a(i2, j2) >= a(i1, j2) + a(i2, j1)
    equivalently:
        f(i2, j2) - f(i1, j2) >= f(i2, j1) - f(i1, j1).
    Hence a newer row i2 overtakes an older row i1 on a suffix of columns j.
    """

    def __init__(self, a: Dict[Tuple[int, int], int], right: int) -> None:
        self.a = a
        self.right = right
        # Deque of tuples (row_idx, row_const, start_col_inclusive)
        self.hull: List[Tuple[int, int, int]] = []
        self.head = 0

    def _eval(self, row: int, const: int, col: int) -> int:
        return const + self.a[(row, col)]

    def _crossing(self, r_old: int, c_old: int, r_new: int, c_new: int, lo_col: int) -> int:
        """Smallest col in [lo_col, right] where r_new >= r_old, or right + 1 if never."""
        lo, hi = lo_col, self.right
        if self._eval(r_new, c_new, hi) < self._eval(r_old, c_old, hi):
            return self.right + 1
        ans = hi
        while lo <= hi:
            mid = (lo + hi) // 2
            if self._eval(r_new, c_new, mid) >= self._eval(r_old, c_old, mid):
                ans = mid
                hi = mid - 1
            else:
                lo = mid + 1
        return ans

    def insert(self, row: int, const: int, min_future_col: int) -> None:
        if min_future_col > self.right:
            return
        while len(self.hull) > self.head:
            r_prev, c_prev, s_prev = self.hull[-1]
            lo_col = max(s_prev, min_future_col)
            cross = self._crossing(r_prev, c_prev, row, const, lo_col)
            if cross <= lo_col:
                self.hull.pop()
            else:
                if cross <= self.right:
                    self.hull.append((row, const, cross))
                return
        self.hull.append((row, const, min_future_col))

    def query(self, col: int) -> Optional[Tuple[int, int]]:
        """Return (best_val, best_row) for column col (monotonically increasing queries)."""
        if self.head >= len(self.hull):
            return None
        while self.head + 1 < len(self.hull) and self.hull[self.head + 1][2] <= col:
            self.head += 1
        r, c, _ = self.hull[self.head]
        return self._eval(r, c, col), r


def solve_exact_envelope(
    inst: FlowShopInstance, graph: Optional[CheckpointGraph] = None
) -> Tuple[int, int, Tuple[int, ...]]:
    """Exact Theorem 1 algorithm using binary-search anti-Monge upper envelopes
    and earliest-reachable predecessor for b(i,j): O(m (B+1) log(m+1)) post-preprocessing.
    """
    if graph is None:
        graph = build_checkpoint_graph(inst)
    m, B = inst.m, inst.budget
    base = evaluate_makespan(inst, ())
    D: List[Dict[int, int]] = [{} for _ in range(m + 1)]
    pred: List[Dict[int, Tuple[int, int]]] = [{} for _ in range(m + 1)]
    D[0][0] = 0

    for left, right in graph.intervals:
        envs: Dict[int, AntiMongeUpperEnvelope] = {}
        earliest: Dict[int, int] = {}

        # Publish left endpoint states for this interval
        for q, val_l in D[left].items():
            env = AntiMongeUpperEnvelope(graph.a, right)
            env.insert(left, val_l, left + 1)
            envs[q] = env
            earliest[q] = left

        for v in range(left + 1, right + 1):
            w_v = inst.effective_cost(v - 1)
            # Query all reachable previous costs q before publishing row v (handles w_v == 0 too)
            if w_v <= B:
                new_states: List[Tuple[int, int, int, int]] = []
                for q, env in envs.items():
                    nb = q + w_v
                    if nb > B:
                        continue
                    res = env.query(v)
                    assert res is not None
                    hom_val, hom_u = res
                    e_u = earliest[q]
                    clk_val = graph.b[(e_u, v)]
                    if clk_val > hom_val:
                        new_states.append((nb, clk_val, e_u, q))
                    else:
                        new_states.append((nb, hom_val, hom_u, q))
                for nb, val_v, u_best, q_prev in new_states:
                    if nb not in D[v] or val_v > D[v][nb]:
                        D[v][nb] = val_v
                        pred[v][nb] = (u_best, q_prev)

            # Publish newly computed states at v if v < right
            if v < right:
                for q, val_v in D[v].items():
                    if q not in envs:
                        env = AntiMongeUpperEnvelope(graph.a, right)
                        env.insert(v, val_v, v + 1)
                        envs[q] = env
                        earliest[q] = v
                    else:
                        envs[q].insert(v, val_v, v + 1)

    best_q = max(D[m], key=lambda q: D[m][q])
    best_c = D[m][best_q] + graph.P_last
    witness: List[int] = []
    cur_v, cur_q = m, best_q
    while cur_v > 0:
        if 1 <= cur_v < m and (cur_v - 1) not in inst.compulsory:
            witness.append(cur_v - 1)
        cur_v, cur_q = pred[cur_v][cur_q]
    witness.reverse()
    return best_c - base, best_c, tuple(witness)


# ---------------------------------------------------------------------------
# Corollary 1: O(mn) backward sweep & singleton positive-increase test
# ---------------------------------------------------------------------------

def backward_tail_weights(inst: FlowShopInstance, selected: Iterable[int]) -> List[List[int]]:
    """Compute tail weights W[i][t] (exiting machine i) via O(mn) backward max-plus transpose."""
    m, n = inst.m, inst.n
    locked = set(inst.compulsory) | set(selected)
    W: List[List[int]] = [[NEG_INF] * n for _ in range(m)]
    W[m - 1][n - 1] = 0
    for i in range(m - 1, 0, -1):
        P = inst.occupied_prefix(i)
        off = inst.upstream_offset(i)
        u_vals = [W[i][t] + P[t] for t in range(n)]
        if i in locked:
            mx = max(u_vals)
            W[i - 1] = [mx - off[t] for t in range(n)]
        else:
            suf = [NEG_INF] * n
            cur = NEG_INF
            for t in range(n - 1, -1, -1):
                if u_vals[t] > cur:
                    cur = u_vals[t]
                suf[t] = cur
            W[i - 1] = [suf[t] - off[t] for t in range(n)]
    return W


def corollary1_singleton_check(inst: FlowShopInstance) -> Tuple[bool, int, Optional[int]]:
    """O(mn) test of whether any affordable singleton yields positive increase (Corollary 1)."""
    base, mat = simulate_schedule(inst, ())
    W = backward_tail_weights(inst, ())
    m, n = inst.m, inst.n
    best_gain = 0
    best_m: Optional[int] = None
    for i in range(m - 1):
        if i in inst.compulsory or inst.costs[i] > inst.budget:
            continue
        V_in = list(inst.r) if i == 0 else mat[i - 1]
        P = inst.occupied_prefix(i)
        off = inst.upstream_offset(i)
        start_i = max(V_in[t] - off[t] for t in range(n))
        c_sing = start_i + max(P[t] + W[i][t] for t in range(n))
        gain = c_sing - base
        if gain > best_gain:
            best_gain = gain
            best_m = i
    return (best_gain > 0), best_gain, best_m


# ---------------------------------------------------------------------------
# Theorem 3: Source-wise certified approximation with exact rational scaling
# ---------------------------------------------------------------------------

def solve_source_approx(
    inst: FlowShopInstance,
    eta: Fraction,
    graph: Optional[CheckpointGraph] = None,
) -> Tuple[int, int, Tuple[int, ...]]:
    """Theorem 3 algorithm for machine availability dates (and job arrivals).

    Returns (L, U, witness) satisfying L <= Delta* <= U and L >= Delta* - eta * G_h*
    for every optimizing source h*.
    """
    if graph is None:
        graph = build_checkpoint_graph(inst)
    m, n, B = inst.m, inst.n, inst.budget
    base = evaluate_makespan(inst, ())
    P_all = [inst.occupied_prefix(i) for i in range(m)]
    off_all = [inst.upstream_offset(i) for i in range(m)]

    # Sources h in {0 (virtual job arrival), 1..m (machine clocks R[h-1])}:
    best_L = 0
    best_witness: Tuple[int, ...] = ()
    best_U = 0

    for h in range(0, m + 1):
        if h > 0 and inst.R[h - 1] <= NEG_INF // 2:
            continue
        # Compulsory-only start q_h(j) for j in {h, ..., m} using ONLY source h:
        q_h: Dict[int, int] = {}
        if h == 0:
            q_h[0] = 0
            V = list(inst.r)
            start_idx = 1
        else:
            q_h[h] = inst.R[h - 1]
            V = [inst.R[h - 1] + x for x in P_all[h - 1]]
            start_idx = h + 1

        for j in range(start_idx, m + 1):
            mi = j - 1
            P = P_all[mi]
            off = off_all[mi]
            terms = [V[t] - off[t] for t in range(n)]
            q_h[j] = max(terms)
            if mi in inst.compulsory or j == m:
                st = q_h[j]
                V = [P[t] + st for t in range(n)]
            else:
                cur = NEG_INF
                V_next = []
                for t in range(n):
                    if terms[t] > cur:
                        cur = terms[t]
                    V_next.append(P[t] + cur)
                V = V_next

        c_h_base = q_h[m] + graph.P_last
        delta_h = base - c_h_base
        if h == m:
            # Terminal clock cannot be increased by downstream locks
            u_h = 0 - delta_h
            if u_h > best_U:
                best_U = u_h
            continue

        # Build reweighted edges within compulsory intervals from h onward:
        # Note: source vertex h has cost 0 for source h (output R_h + P_h independent of locking h).
        def node_cost(v: int) -> int:
            if v == h or v == 0 or v == m or (v - 1) in inst.compulsory:
                return 0
            return inst.costs[v - 1]

        # Valid compulsory intervals starting at or after h:
        # Split the interval containing h so path starts cleanly at h.
        comp_after = sorted({h, m} | {c for c in graph.compulsory_nodes if c > h})
        edges: List[Tuple[int, int, int]] = []  # (u, v, reward)
        max_rew = 0
        for idx in range(len(comp_after) - 1):
            L_int, R_int = comp_after[idx], comp_after[idx + 1]
            for u in range(L_int, R_int):
                cu = node_cost(u)
                for v in range(u + 1, R_int + 1):
                    cv = node_cost(v)
                    if cu + cv > B:
                        continue
                    rew = q_h[u] + graph.a[(u, v)] - q_h[v]
                    assert rew >= 0, f"Negative reweighted edge reward {rew}"
                    edges.append((u, v, rew))
                    if rew > max_rew:
                        max_rew = rew

        if max_rew == 0:
            u_h = 0 - delta_h
            if u_h > best_U:
                best_U = u_h
            continue

        ell_h = m - h  # upper bound on edges on any path from h to m
        unit = eta * Fraction(max_rew, ell_h)
        # DP: min_cost[v][rounded_reward] = min expenditure to reach v with exact rounded reward
        # Track predecessor (u, prev_r)
        adj: Dict[int, List[Tuple[int, int, int]]] = {v: [] for v in range(h, m + 1)}
        for u, v, rew in edges:
            r_scaled = int(Fraction(rew, 1) // unit)
            adj[u].append((v, r_scaled, node_cost(v)))

        dp: Dict[int, Dict[int, int]] = {v: {} for v in range(h, m + 1)}
        pred: Dict[int, Dict[int, Tuple[int, int]]] = {v: {} for v in range(h, m + 1)}
        dp[h][0] = 0

        for u in range(h, m):
            if not dp[u]:
                continue
            for r_u, cost_u in dp[u].items():
                for v, r_e, c_v in adj[u]:
                    nc = cost_u + c_v
                    if nc > B:
                        continue
                    nr = r_u + r_e
                    if nr not in dp[v] or nc < dp[v][nr]:
                        dp[v][nr] = nc
                        pred[v][nr] = (u, r_u)

        best_r = max(dp[m].keys())
        # Upper bound on G_h: floor((best_r + ell_h) * unit)
        g_h_upper = int((Fraction(best_r + ell_h, 1) * unit))
        u_h = g_h_upper - delta_h
        if u_h > best_U:
            best_U = u_h

        # Recover feasible witness and evaluate under true physical recurrence
        wit: List[int] = []
        cur_v, cur_r = m, best_r
        while cur_v != h:
            if 1 <= cur_v < m and (cur_v - 1) not in inst.compulsory:
                wit.append(cur_v - 1)
            cur_v, cur_r = pred[cur_v][cur_r]
        wit.reverse()
        phys_gain = evaluate_makespan(inst, wit) - base
        if phys_gain > best_L:
            best_L = phys_gain
            best_witness = tuple(wit)

    return best_L, best_U, best_witness


# ---------------------------------------------------------------------------
# Theorem 5: O(mn) downstream suffix deletion maximum-error test
# ---------------------------------------------------------------------------

def suffix_deletion_max_error(
    inst: FlowShopInstance, cut_machine: int
) -> Tuple[int, Tuple[int, ...]]:
    """O(mn) exact maximum makespan error when removing all local clocks on machines >= cut_machine.

    Returns (max_error, witness_subset) where witness_subset is () or (j,).
    """
    m, n = inst.m, inst.n
    full_kap = [inst.local_kappa(i) for i in range(m)]
    red_kap = [
        [NEG_INF] * n if i >= cut_machine else list(full_kap[i])
        for i in range(m)
    ]

    V_f = list(inst.r)
    V_r = list(inst.r)
    best_err = 0
    best_wit: Tuple[int, ...] = ()

    for i in range(m):
        P = inst.occupied_prefix(i)
        off = inst.upstream_offset(i)
        terms_f = [max(V_f[t] - off[t], full_kap[i][t]) for t in range(n)]
        terms_r = [max(V_r[t] - off[t], red_kap[i][t]) for t in range(n)]

        st_f = max(terms_f)
        st_r = max(terms_r)
        if i >= cut_machine:
            # Eligible checkpoints: compulsory, free terminal sink m-1, or affordable optional machine
            if i in inst.compulsory or i == m - 1 or inst.costs[i] <= inst.budget:
                diff = st_f - st_r
                if diff > best_err:
                    best_err = diff
                    best_wit = () if (i in inst.compulsory or i == m - 1) else (i,)

        if i in inst.compulsory:
            V_f = [P[t] + st_f for t in range(n)]
            V_r = [P[t] + st_r for t in range(n)]
        else:
            cur_f, cur_r = NEG_INF, NEG_INF
            next_f, next_r = [], []
            for t in range(n):
                if terms_f[t] > cur_f:
                    cur_f = terms_f[t]
                if terms_r[t] > cur_r:
                    cur_r = terms_r[t]
                next_f.append(P[t] + cur_f)
                next_r.append(P[t] + cur_r)
            V_f, V_r = next_f, next_r

    return best_err, best_wit


# ---------------------------------------------------------------------------
# Appendix A (Proposition A.1): O(mn) minimum all-completions local support
# ---------------------------------------------------------------------------

def min_all_completions_support(inst: FlowShopInstance) -> List[List[bool]]:
    """Return m x n boolean mask of minimum-cardinality retained kappa_i(t) entries
    preserving every completion time under every feasible lock subset.
    """
    m, n = inst.m, inst.n
    V = list(inst.r)
    keep: List[List[bool]] = [[False] * n for _ in range(m)]
    for i in range(m):
        P = inst.occupied_prefix(i)
        off = inst.upstream_offset(i)
        kap = inst.local_kappa(i)
        up = [V[t] - off[t] for t in range(n)]
        if i in inst.compulsory:
            up_max = max(up)
            kap_max = max(kap)
            if kap_max > up_max:
                idx = kap.index(kap_max)
                keep[i][idx] = True
            st = max(up_max, kap_max)
            V = [P[t] + st for t in range(n)]
        else:
            H_prev = NEG_INF
            V_next = []
            for t in range(n):
                if kap[t] > max(H_prev, up[t]):
                    keep[i][t] = True
                H_cur = max(H_prev, up[t], kap[t])
                V_next.append(P[t] + H_cur)
                H_prev = H_cur
            V = V_next
    return keep


# ---------------------------------------------------------------------------
# Appendix B: Uniform-threshold anti-Monge arbitrary clock deletion oracle
# & Exact constraint-generation minimum clock retention
# ---------------------------------------------------------------------------

def baseline_hypothetical_starts(
    inst: FlowShopInstance,
    kappa_override: Optional[Sequence[Sequence[int]]] = None,
) -> List[int]:
    """Compute Z_0(j) (or R_0(j)): start at machine j when only F union {j} is locked."""
    m, n = inst.m, inst.n
    V = list(inst.r)
    starts = [0] * m
    for i in range(m):
        P = inst.occupied_prefix(i)
        off = inst.upstream_offset(i)
        kap = inst.local_kappa(i) if kappa_override is None else kappa_override[i]
        terms = [max(V[t] - off[t], kap[t]) for t in range(n)]
        st = max(terms)
        starts[i] = st
        if i in inst.compulsory:
            V = [P[t] + st for t in range(n)]
        else:
            cur = NEG_INF
            V_next = []
            for t in range(n):
                if terms[t] > cur:
                    cur = terms[t]
                V_next.append(P[t] + cur)
            V = V_next
    return starts


def deletion_threshold_oracle(
    inst: FlowShopInstance,
    retained_machines: Set[int],
    threshold_d: int,
    graph: Optional[CheckpointGraph] = None,
    Z0: Optional[List[int]] = None,
) -> Optional[Tuple[int, ...]]:
    """Uniform-threshold anti-Monge oracle (Appendix B): returns a budget-feasible witness S
    with C_full(S) - C_red(S) >= threshold_d, or None if no such S exists.
    """
    assert threshold_d >= 1
    if graph is None:
        graph = build_checkpoint_graph(inst)
    m, n, B = inst.m, inst.n, inst.budget
    if Z0 is None:
        Z0 = baseline_hypothetical_starts(inst)
    red_kap = [
        inst.local_kappa(i) if i in retained_machines else [NEG_INF] * n
        for i in range(m)
    ]
    R0 = baseline_hypothetical_starts(inst, kappa_override=red_kap)

    # DP states on physical machines 1..m (node v corresponds to machine v-1)
    # State value is largest surviving full-schedule lower bound z_v.
    D: List[Dict[int, int]] = [{} for _ in range(m + 1)]
    pred: List[Dict[int, Optional[Tuple[int, int]]]] = [{} for _ in range(m + 1)]

    for left, right in graph.intervals:
        envs: Dict[int, AntiMongeUpperEnvelope] = {}
        # If left >= 1 (compulsory physical checkpoint), publish surviving states from previous interval
        if left >= 1:
            for q, val_l in D[left].items():
                env = AntiMongeUpperEnvelope(graph.a, right)
                env.insert(left, val_l, left + 1)
                envs[q] = env

        for v in range(max(1, left + 1), right + 1):
            mi = v - 1
            w_v = inst.effective_cost(mi)
            if w_v <= B:
                # 1. Seed at v if Z0[mi] >= R0[mi] + d
                if Z0[mi] >= R0[mi] + threshold_d:
                    if w_v not in D[v] or Z0[mi] > D[v][w_v]:
                        D[v][w_v] = Z0[mi]
                        pred[v][w_v] = None

                # 2. Extend from earlier surviving checkpoints in same interval via uniform threshold
                updates: List[Tuple[int, int, int, int]] = []
                req = R0[mi] + threshold_d
                for q, env in envs.items():
                    nb = q + w_v
                    if nb > B:
                        continue
                    res = env.query(v)
                    assert res is not None
                    val_v, u_best = res
                    if val_v >= req:
                        updates.append((nb, val_v, u_best, q))
                for nb, val_v, u_best, q_prev in updates:
                    if nb not in D[v] or val_v > D[v][nb]:
                        D[v][nb] = val_v
                        pred[v][nb] = (u_best, q_prev)

            if v < right:
                for q, val_v in D[v].items():
                    if q not in envs:
                        env = AntiMongeUpperEnvelope(graph.a, right)
                        env.insert(v, val_v, v + 1)
                        envs[q] = env
                    else:
                        envs[q].insert(v, val_v, v + 1)

    if not D[m]:
        return None
    best_q = max(D[m], key=lambda q: D[m][q])
    wit: List[int] = []
    cur_v, cur_q = m, best_q
    while True:
        if 1 <= cur_v < m and (cur_v - 1) not in inst.compulsory:
            wit.append(cur_v - 1)
        prev = pred[cur_v][cur_q]
        if prev is None:
            break
        cur_v, cur_q = prev
    wit.reverse()
    return tuple(wit)


def arbitrary_deletion_max_error(
    inst: FlowShopInstance,
    retained_machines: Set[int],
    graph: Optional[CheckpointGraph] = None,
) -> Tuple[int, Optional[Tuple[int, ...]]]:
    """Exact maximum makespan error for arbitrary clock deletion via bisection over the
    uniform-threshold anti-Monge oracle (Appendix B).
    """
    if graph is None:
        graph = build_checkpoint_graph(inst)
    Z0 = baseline_hypothetical_starts(inst)
    # Upper bound U: lock all individually affordable machines in full vs compulsory-only in reduced
    all_aff = [
        i for i in range(inst.m - 1) if i not in inst.compulsory and inst.costs[i] <= inst.budget
    ]
    c_upper = evaluate_makespan(inst, all_aff)
    red_kap = [
        inst.local_kappa(i) if i in retained_machines else [NEG_INF] * inst.n
        for i in range(inst.m)
    ]
    c_red_base = simulate_schedule(inst, (), kappa_override=red_kap)[0]
    hi = max(0, c_upper - c_red_base)
    if hi == 0:
        return 0, None

    wit1 = deletion_threshold_oracle(inst, retained_machines, 1, graph=graph, Z0=Z0)
    if wit1 is None:
        return 0, None

    lo = 1
    best_wit = wit1
    while lo < hi:
        mid = (lo + hi + 1) // 2
        w = deletion_threshold_oracle(inst, retained_machines, mid, graph=graph, Z0=Z0)
        if w is not None:
            lo = mid
            best_wit = w
        else:
            hi = mid - 1
    return lo, best_wit


def source_contributions_backward(inst: FlowShopInstance, selected: Iterable[int]) -> Tuple[int, List[int]]:
    """Compute entry contribution v_{-1}(S) and every machine clock contribution v_h(S) in O(mn)."""
    m, n = inst.m, inst.n
    locked = set(inst.compulsory) | set(selected)
    W = backward_tail_weights(inst, selected)
    # Contribution of machine clock h is max_t (kappa_h(t) + coeff_h(t))
    v_clocks: List[int] = []
    for i in range(m):
        P = inst.occupied_prefix(i)
        kap = inst.local_kappa(i)
        u_vals = [W[i][t] + P[t] for t in range(n)]
        if i in locked:
            mx = max(u_vals)
            v_clocks.append(max(kap) + mx)
        else:
            suf = [NEG_INF] * n
            cur = NEG_INF
            for t in range(n - 1, -1, -1):
                if u_vals[t] > cur:
                    cur = u_vals[t]
                suf[t] = cur
            v_clocks.append(max(kap[t] + suf[t] for t in range(n)))
    # Entry contribution via machine 0 incoming weights:
    P0 = inst.occupied_prefix(0)
    off0 = inst.upstream_offset(0)
    u0 = [W[0][t] + P0[t] for t in range(n)]
    if 0 in locked:
        mx0 = max(u0)
        v_entry = max(inst.r[t] - off0[t] for t in range(n)) + mx0
    else:
        suf0 = [NEG_INF] * n
        cur = NEG_INF
        for t in range(n - 1, -1, -1):
            if u0[t] > cur:
                cur = u0[t]
            suf0[t] = cur
        v_entry = max(inst.r[t] - off0[t] + suf0[t] for t in range(n))
    return v_entry, v_clocks


def minimum_hitting_set(cuts: List[Set[int]]) -> Set[int]:
    """Exact branch-and-bound minimum hitting set over a family of nonempty cuts."""
    if not cuts:
        return set()
    best: List[Optional[Set[int]]] = [None]

    def dfs(rem_cuts: List[Set[int]], chosen: Set[int]) -> None:
        if best[0] is not None and len(chosen) >= len(best[0]):
            return
        if not rem_cuts:
            best[0] = set(chosen)
            return
        # Lower bound via greedy maximal disjoint cut packing
        used: Set[int] = set()
        disjoint = 0
        for c in sorted(rem_cuts, key=len):
            if c.isdisjoint(used):
                disjoint += 1
                used |= c
        if best[0] is not None and len(chosen) + disjoint >= len(best[0]):
            return
        pivot = min(rem_cuts, key=len)
        # Branch on elements of smallest uncovered cut, ordered by frequency
        freq = {x: sum(1 for c in rem_cuts if x in c) for x in pivot}
        for x in sorted(pivot, key=lambda e: -freq[e]):
            chosen.add(x)
            next_cuts = [c for c in rem_cuts if x not in c]
            dfs(next_cuts, chosen)
            chosen.remove(x)

    dfs(cuts, set())
    assert best[0] is not None
    return best[0]


def minimum_retained_clocks(
    inst: FlowShopInstance,
    tolerance: int = 0,
    protected: Optional[Set[int]] = None,
) -> Tuple[Set[int], int]:
    """Exact constraint-generation algorithm for minimum-cardinality retained clock vectors
    (Appendix B). Returns (additional_retained_set, iterations).
    """
    prot = set() if protected is None else set(protected)
    graph = build_checkpoint_graph(inst)
    Z0 = baseline_hypothetical_starts(inst)
    cuts: List[Set[int]] = []
    iters = 0
    while True:
        iters += 1
        cand = minimum_hitting_set(cuts)
        retained = prot | cand
        wit = deletion_threshold_oracle(
            inst, retained, tolerance + 1, graph=graph, Z0=Z0
        )
        if wit is None:
            return cand, iters
        v_entry, v_clocks = source_contributions_backward(inst, wit)
        c_full = max(v_entry, max(v_clocks))
        req = c_full - tolerance
        cut = {h for h in range(inst.m) if h not in prot and v_clocks[h] >= req}
        assert cut and cut.isdisjoint(cand), "Violated cut must be nonempty and disjoint from candidate"
        cuts.append(cut)
