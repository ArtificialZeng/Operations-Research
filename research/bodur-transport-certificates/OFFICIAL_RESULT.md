# Integrated transportation-tree reuse on public Bodur instances

## 60-second paired runs

The eight runs on `large_1` and `large_4` exited normally within 60 seconds and passed the original public checker and independent Decimal accounting. Both arms and both repetitions returned 63,726.6060063786 on `large_1` and 48,495.8815487029 on `large_4`, using the independently recomputed objectives. The tree arm accepted zero certificates in 94,500 binary scenario evaluations. Its median paired reduction in binary-recourse time was 1.3%, with the four comparisons ranging from a 5.1% reduction to a 7.8% increase. Thus it missed the frozen 20% time threshold. The only numerical master-bound difference was about 0.98 on one `large_1` pair; no scenario used a tree in that comparison. [Frozen design](README.md#design) · [Machine-readable executions](measured_results.json)

| Public input | Repetition | CLP binary recourse | Tree binary recourse | Common objective |
|---|---:|---:|---:|---:|
| `large_1` | 1 | 31.55 s | 29.95 s | 63,726.6060 |
| `large_1` | 2 | 30.06 s | 28.76 s | 63,726.6060 |
| `large_4` | 1 | 19.13 s | 20.62 s | 48,495.8815 |
| `large_4` | 2 | 18.99 s | 19.32 s | 48,495.8815 |

The baseline and candidate keep the same SCIP/CLP master and expected-demand start. Certification uses exact JSON decimal tokens represented with Python integers, including the original probabilities. The instances are public and known. The live contest task lists `tiny` and `large_1` as its public development cases. [Official task](https://frontieror-challenge.com/problems/bodur2017)

## Diagnosing the infeasible trees

On the `tiny` diagnostic, the learner built 32 exact dual-feasible trees and every tree failed the next right-hand side through a negative edge flow. The first dual pivot reached a valid but still primal-infeasible tree on all 32. A separate probe held the original sequence of misses fixed. Fourteen of the 32 trees became primal-feasible within eight pivots. The counts by first successful depth were two at four pivots, two at five, two at seven, and eight at eight. [Single-pivot diagnostic and fixed-miss depth profile](measured_results.json)

A post-trial diagnostic kept the observed common initial facility layout on each large input and constructed trees at 24 equally spaced total-demand ranks. Every selected tree certified its own source scenario. Across all 1,476 remaining scenarios, testing the entire pool certified zero on `large_1` and six on `large_4`. This checks a substantially broader reuse policy than adjacent-only lookup for those fixed layouts. [Pool counts](sampled_tree_pool.json) · [Pool evaluator](measure_pool_coverage.py)

Anti-Gravity proposed replacing a negative-flow tree edge with an arc of minimum reduced slack. The entering arc can have strictly positive slack, so it needs a potential shift before becoming tight. In the directed convention `p_i − p_j ≤ c_ij`, take the leaving edge's child subtree `S`, rooted away from the dummy sink. Shift its potentials by `sign(b(S))` times the minimum slack among arcs whose constraint tightens under that shift. Arcs within or outside `S` are unaffected, and the other crossing arcs relax. The implementation then checks the new tree equalities, dual signs, and full dual extension across original facilities. Accept a scenario only after nonnegative exact flows can be recovered. [Corrected pivot](tree_pivot.py)

## Bounded repair in the full tiny solver

With at most eight pivots per miss, the candidate reached 30 repair hits from 62 attempts, saving 30 of the baseline's 500 binary LP calls. Both arms passed both checkers and returned the same objective, 74,706.08988139463 as serialized. The binary-recourse stage increased from 0.376 s to 0.491 s. Repair consumed 0.125 s. At this problem size, the implementation's exact repairs cost more than the CLP calls they remove. [Paired executable smoke test](measured_results.json)

The exact one-tree and bounded-pivot variants are frozen as comparison artifacts. In the 1,500-scenario external CAP101 trial, certified reuse sped up transportation by 9.60-fold per layout while both complete solvers tied at a cost of 831,805.09. In a later exploratory pair, adding a shared feasible single-closure initializer and stronger nearest-facility cuts gave both arms an exact cost of 802,784.20 and a rigorous lower bound of 783,044.23. The final gap was 2.459%. The bundled initialization and master changes improved the decision on that workload. The recourse-only arm choice did not change the result. General basis reuse and exact active-region evaluation have prior art. [Stronger shared CAP101 master](CLOSURE_MASTER_PROTOCOL.md) · [Multiple-RHS basis reuse](https://doi.org/10.1007/BF02187648) · [Exact multiparametric Benders lookup](https://doi.org/10.1021/acs.iecr.5c03189)
