"""Exact closed-form check: for d-regular girth>=6 graphs, on each interval t/(d+t) <= alpha <= (t+1)/(d+t+1) (capped at 1/3)
the 2-variable aggregated LP optimum equals v_t(alpha) = I_t - S_t*alpha with
  I_t = (2d^2 - t(t+1))/4,  S_t = (6d^2 - 2d - 2dt - t^2 - t)/4.
Lower bound: dual (mu_{q=d,t} = 1/2, thin = 1/2, budget multiplier = S_t) is nonnegative and dual-feasible for every alpha.
Upper bound: the point c = 1-3alpha, a from cut(d,t) at equality satisfies EVERY aggregated row (checked exactly at the interval
endpoints; all rows are affine in alpha so endpoints suffice). Hence exact value, for each d tested.
"""
from __future__ import annotations

import json
from fractions import Fraction as F
from math import comb
from pathlib import Path

from stage2_family_reduction_certificate import agg_rows

OUT = Path(__file__).resolve().parent / "stage2b_closed_form_check.json"


def I(d, t): return F(2 * d * d - t * (t + 1), 4)
def S(d, t): return F(6 * d * d - 2 * d - 2 * d * t - t * t - t, 4)


def feasible_point(d, t, al):
    c = 1 - 3 * al
    rhs = F(d - t) * ((d + t + 1) - (3 * d + t + 1) * al) / 2
    a = (rhs - comb(d, 2) * c) / d
    return a, c


def check_d(d: int) -> dict:
    rows = agg_rows(1, d, "all")
    res = []
    for t in range(0, d):
        lo = max(F(t, d + t), F(1, d + 1)) if t >= 1 else F(1, d + 1)
        hi = min(F(t + 1, d + t + 1), F(1, 3))
        if lo >= hi and not (t == 0):
            if lo > F(1, 3) or lo >= hi:
                continue
        ok_rows, ok_box = True, True
        for al in (lo, hi):
            a, c = feasible_point(d, t, al)
            ye, yp = F(d, 2) * a, F(d * (d - 1), 2) * c
            if not (0 <= a <= 1 and 0 <= c <= 1):
                ok_box = False
            for _, ce, cp, cx, rhs, _m in rows:
                if ce * ye + cp * yp + cx * al < rhs:
                    ok_rows = False
            if ye + yp != I(d, t) - S(d, t) * al:
                ok_rows = False
        ok = ok_rows and ok_box
        res.append({"t": t, "alpha_from": str(lo), "alpha_to": str(hi), "exact_optimum_is_v_t": ok,
                    "aggregated_rows_ok": ok_rows, "box_y_le_1_ok": ok_box})
        if hi >= F(1, 3):
            break
    return {"d": d, "intervals": res, "all_ok": all(r["exact_optimum_is_v_t"] for r in res)}


def main():
    out, bad = [], []
    for d in range(3, 41):
        r = check_d(d)
        out.append(r)
        if not r["all_ok"]:
            bad.append(d)
    rows_bad = [r["d"] for r in out if not all(i["aggregated_rows_ok"] for i in r["intervals"])]
    print("d with any aggregated-row violation (should be empty):", rows_bad)
    print("first d where box y<=1 blocks the unboxed point:", bad[:1], "exact range d in [3,%d]" % (bad[0] - 1 if bad else 40))
    # alpha = 1/3 consequence: v_all = floor((d+1)^2/4)/6, v_base = d/6, v_t1 = (d-1)/3
    lim = []
    for d in range(3, 41):
        v = max((d - t) * (t + 1) for t in range(d)) / 6
        lim.append({"d": d, "v_all_at_third": str(F(max((d - t) * (t + 1) for t in range(d)), 6)),
                    "floor_formula": str(F((d + 1) ** 2 // 4, 6)),
                    "v_base": str(F(d, 6)), "v_t1": str(F(d - 1, 3)),
                    "ratio_all_over_base": round(float(F(max((d - t) * (t + 1) for t in range(d)), d)), 4)})
        assert F(max((d - t) * (t + 1) for t in range(d)), 6) == F((d + 1) ** 2 // 4, 6)
    OUT.write_text(json.dumps({"d_range": [3, 40], "failed_d": bad, "per_d": out, "alpha_one_third": lim}, indent=1) + "\n", encoding="utf-8")
    print("failed_d =", bad)
    for r in lim[:8] + lim[-2:]:
        print(r)


if __name__ == "__main__":
    main()
