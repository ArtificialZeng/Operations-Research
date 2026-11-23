#!/usr/bin/env python3
"""Classical open-source non-LLM baselines for FrontierOR ruiz2007
(Mixed No-Idle Permutation Flowshop Scheduling, MNPFSP, minimize makespan).
Written purely from OR literature prior to any ruiz2007 solver runs.
"""

import argparse
import json
import math
import random
import time


def compute_mnpfsp_schedule(perm, p_m_j, no_idle, m):
    """Exact minimum feasible completion matrix C[i][k] for MNPFSP given permutation perm."""
    n = len(perm)
    if n == 0:
        return [], 0
    C = [[0] * n for _ in range(m)]
    p0 = p_m_j[0]
    acc = 0
    for k, j in enumerate(perm):
        acc += p0[j]
        C[0][k] = acc

    for i in range(1, m):
        pi = p_m_j[i]
        prev = C[i - 1]
        ci = C[i]
        if no_idle[i]:
            cumsum = 0
            s_i = prev[0]
            for k in range(1, n):
                cumsum += pi[perm[k - 1]]
                need = prev[k] - cumsum
                if need > s_i:
                    s_i = need
            acc = s_i
            for k, j in enumerate(perm):
                acc += pi[j]
                ci[k] = acc
        else:
            acc = prev[0] + pi[perm[0]]
            ci[0] = acc
            for k in range(1, n):
                j = perm[k]
                pv = prev[k]
                acc = (pv if pv > acc else acc) + pi[j]
                ci[k] = acc
    return C, C[m - 1][n - 1]


def mnpfsp_makespan_fast(perm, p_m_j, no_idle, m):
    """Fast scalar makespan evaluation for MNPFSP."""
    n = len(perm)
    if n == 0:
        return 0
    prev = [0] * n
    p0 = p_m_j[0]
    acc = 0
    for k, j in enumerate(perm):
        acc += p0[j]
        prev[k] = acc

    for i in range(1, m):
        pi = p_m_j[i]
        cur = [0] * n
        if no_idle[i]:
            cumsum = 0
            s_i = prev[0]
            for k in range(1, n):
                cumsum += pi[perm[k - 1]]
                need = prev[k] - cumsum
                if need > s_i:
                    s_i = need
            acc = s_i
            for k, j in enumerate(perm):
                acc += pi[j]
                cur[k] = acc
        else:
            acc = prev[0] + pi[perm[0]]
            cur[0] = acc
            for k in range(1, n):
                j = perm[k]
                pv = prev[k]
                acc = (pv if pv > acc else acc) + pi[j]
                cur[k] = acc
        prev = cur
    return prev[n - 1]


def regular_pfsp_makespan(perm, p_m_j, m):
    """Classical PFSP makespan ignoring no-idle constraints (all machines regular)."""
    n = len(perm)
    if n == 0:
        return 0
    prev = [0] * n
    p0 = p_m_j[0]
    acc = 0
    for k, j in enumerate(perm):
        acc += p0[j]
        prev[k] = acc
    for i in range(1, m):
        pi = p_m_j[i]
        acc = prev[0] + pi[perm[0]]
        prev[0] = acc
        for k in range(1, n):
            j = perm[k]
            pv = prev[k]
            acc = (pv if pv > acc else acc) + pi[j]
            prev[k] = acc
    return prev[n - 1]


def format_solution(perm, p_m_j, no_idle, m):
    C, ms = compute_mnpfsp_schedule(perm, p_m_j, no_idle, m)
    return {
        "objective_value": float(ms),
        "sequence": [int(j) for j in perm],
        "completion_times": {f"machine_{i}": [float(x) for x in C[i]] for i in range(m)},
    }


def solve_palmer_cds(n, m, p_m_j, no_idle):
    """Best of Palmer (1965) slope index and Campbell-Dudek-Smith (1970) Johnson-rule passes."""
    candidates = []
    # Palmer slope index
    slopes = []
    for j in range(n):
        s = sum((2 * (i + 1) - m - 1) * p_m_j[i][j] for i in range(m))
        slopes.append((-s, j))
    slopes.sort()
    candidates.append([j for _, j in slopes])

    # CDS: for k = 1..m-1, virtual 2-machine Johnson's rule
    for k_split in range(1, m):
        left = []
        right = []
        for j in range(n):
            a = sum(p_m_j[i][j] for i in range(k_split))
            b = sum(p_m_j[i][j] for i in range(m - k_split, m))
            if a <= b:
                left.append((a, j))
            else:
                right.append((b, j))
        left.sort(key=lambda x: (x[0], x[1]))
        right.sort(key=lambda x: (-x[0], x[1]))
        candidates.append([j for _, j in left] + [j for _, j in right])

    # Pick candidate minimizing true MNPFSP makespan
    best_perm = min(candidates, key=lambda seq: mnpfsp_makespan_fast(seq, p_m_j, no_idle, m))
    return best_perm


def solve_neh_regular(n, m, p_m_j, no_idle):
    """Standard NEH (1983) evaluating insertions under classical PFSP (ignores no-idle during build)."""
    totals = sorted(range(n), key=lambda j: (-sum(p_m_j[i][j] for i in range(m)), j))
    seq = [totals[0]]
    for job in totals[1:]:
        best_pos = 0
        best_ms = math.inf
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            ms = regular_pfsp_makespan(cand, p_m_j, m)
            if ms < best_ms:
                best_ms = ms
                best_pos = pos
        seq.insert(best_pos, job)
    return seq


def solve_neh_mnpfsp(n, m, p_m_j, no_idle):
    """Mixed No-Idle NEH (Pan & Ruiz 2014) using exact MNPFSP evaluation at every insertion."""
    totals = sorted(range(n), key=lambda j: (-sum(p_m_j[i][j] for i in range(m)), j))
    seq = [totals[0]]
    for job in totals[1:]:
        best_pos = 0
        best_ms = math.inf
        for pos in range(len(seq) + 1):
            cand = seq[:pos] + [job] + seq[pos:]
            ms = mnpfsp_makespan_fast(cand, p_m_j, no_idle, m)
            if ms < best_ms:
                best_ms = ms
                best_pos = pos
        seq.insert(best_pos, job)
    return seq


def insertion_local_search(seq, p_m_j, no_idle, m, deadline, rng):
    """First-improvement insertion neighborhood local search until local optimum or deadline."""
    cur = list(seq)
    cur_ms = mnpfsp_makespan_fast(cur, p_m_j, no_idle, m)
    n = len(cur)
    improved = True
    while improved and time.perf_counter() < deadline:
        improved = False
        order = list(range(n))
        rng.shuffle(order)
        for idx in order:
            if time.perf_counter() >= deadline:
                break
            job = cur[idx]
            rem = cur[:idx] + cur[idx + 1:]
            best_pos = idx
            best_ms = cur_ms
            for pos in range(n):
                if pos == idx:
                    continue
                cand = rem[:pos] + [job] + rem[pos:]
                ms = mnpfsp_makespan_fast(cand, p_m_j, no_idle, m)
                if ms < best_ms:
                    best_ms = ms
                    best_pos = pos
            if best_ms < cur_ms:
                cur = rem[:best_pos] + [job] + rem[best_pos:]
                cur_ms = best_ms
                improved = True
                break
    return cur, cur_ms


def solve_ig_ruiz(n, m, p_m_j, no_idle, time_limit, seed=42):
    """Ruiz & Stutzle (2007) / Pan & Ruiz (2014) Iterated Greedy with exact MNPFSP objective."""
    t0 = time.perf_counter()
    deadline = t0 + max(0.05, time_limit * 0.90)
    rng = random.Random(seed)

    # Temperature calibration (standard Ruiz & Stutzle formula T = 0.4 * mean(p) / 10)
    mean_p = sum(sum(row) for row in p_m_j) / max(1, n * m)
    temp = max(1.0, 0.4 * mean_p / 10.0)

    seq = solve_neh_mnpfsp(n, m, p_m_j, no_idle)
    seq, cur_ms = insertion_local_search(seq, p_m_j, no_idle, m, deadline, rng)
    best_seq = list(seq)
    best_ms = cur_ms

    d_remove = min(4, max(2, n // 10))
    while time.perf_counter() < deadline:
        # Destruction: remove d_remove distinct jobs
        rem_indices = sorted(rng.sample(range(n), d_remove), reverse=True)
        partial = list(seq)
        removed = [partial.pop(idx) for idx in rem_indices]

        # Construction: greedy best-insertion under exact MNPFSP makespan
        for job in removed:
            best_pos = 0
            best_c = math.inf
            for pos in range(len(partial) + 1):
                cand = partial[:pos] + [job] + partial[pos:]
                ms = mnpfsp_makespan_fast(cand, p_m_j, no_idle, m)
                if ms < best_c:
                    best_c = ms
                    best_pos = pos
            partial.insert(best_pos, job)

        # Local search
        cand_seq, cand_ms = insertion_local_search(partial, p_m_j, no_idle, m, deadline, rng)

        if cand_ms < best_ms:
            best_ms = cand_ms
            best_seq = list(cand_seq)
            seq = list(cand_seq)
            cur_ms = cand_ms
        elif cand_ms <= cur_ms or rng.random() < math.exp(-(cand_ms - cur_ms) / temp):
            seq = list(cand_seq)
            cur_ms = cand_ms

    return best_seq


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--algo", type=str, required=True,
                        choices=["classic_palmer_cds", "classic_neh_regular", "classic_neh_mnpfsp", "classic_ig_ruiz"])
    parser.add_argument("--instance_path", type=str, required=True)
    parser.add_argument("--solution_path", type=str, required=True)
    parser.add_argument("--time_limit", type=int, default=5)
    parser.add_argument("--log_path", type=str, default=None)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    inst = json.load(open(args.instance_path))
    n = int(inst["n_jobs"])
    m = int(inst["n_machines"])
    no_idle = [bool(x) for x in inst["no_idle_flags"][:m]]
    pt = inst["processing_times"]
    p_m_j = [[int(pt[j][i]) for j in range(n)] for i in range(m)]

    if args.algo == "classic_palmer_cds":
        perm = solve_palmer_cds(n, m, p_m_j, no_idle)
    elif args.algo == "classic_neh_regular":
        perm = solve_neh_regular(n, m, p_m_j, no_idle)
    elif args.algo == "classic_neh_mnpfsp":
        perm = solve_neh_mnpfsp(n, m, p_m_j, no_idle)
    else:
        perm = solve_ig_ruiz(n, m, p_m_j, no_idle, args.time_limit, seed=args.seed)

    sol = format_solution(perm, p_m_j, no_idle, m)
    with open(args.solution_path, "w") as f:
        json.dump(sol, f, indent=2)


if __name__ == "__main__":
    main()
