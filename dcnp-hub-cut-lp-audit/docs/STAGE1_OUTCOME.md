# Stage 1 Outcome vs. Pre-Run Criteria (sealed synthetic benchmark; read-only audit)

Scope: 16 synthetic instances, two arms, one run. No rerun, no tuning. No PDF, no publicity.

## Integrity (from stage1_postcheck.json, recomputed from raw JSON)
- Exit code 0, python PID 418, wrapper PID 309, 168.974 s measured wall (sum of the 32 arm runs, max single arm 38.67 s; the 60 s per-arm limit was enforced inside the script, not by an outer guard; no deadline hit).
- Hashes (pre == post): protocol `cf81fad4d2a32aedb8851f8e694ee552f3f0ec5a176763ba230b2186f4ca71f5`, script `e958589fd83ce94b52b6cff1d8bb295453f69a1351d07568ae6efcc7e3b05b5f`.
- Results `8dbfd8f31dd68614d6e0d89af00a7c720b5c9351997bff5bcad1a05ae6e89700` (recomputed, matches exit receipt); log `44f0836935fdf6107803874d507bbb011ff8ab38748125d2fcdec461235822f9`.
- **Dual check, as the protocol requires:** for all 16 instances, both arms' `mip_dual_bound` and `lp_root_after_cuts` are `<=` the better of the two BFS primals (+1e-4); both primals are equal; BFS-verified; both arms optimal; 0 integrity failures.

## Tier 1 — PASS
16/16 strict root-LP lifts; all 4 families (including the non-bipartite WS, SBM, regular); mean extra gap closure 47.09% (threshold 10%).

## Tier 2 — FAIL
| Criterion | Result |
| :--- | :--- |
| solved(AUG) >= solved(BASE) | 16 / 16 vs 16 / 16 (met) |
| shifted-geomean total wall ratio <= 0.85 | **0.9907 (not met)** |
| wins > losses on branching instances (either arm nodes > 1: #07, #08, #15, #16) | **1 W / 1 T / 2 L (not met)** |
| ratio > 1.25 on < 2 families | SBM 1.4471, WS 1.0484, bipartite 0.7458, regular 0.6705 (met) |
All pairs: 7 W / 4 T / 5 L. **No practical speed claim.**

## What the data say (estimates, not certificates)
- Node counts fall where the baseline branches (regular: 11 -> 1, 31 -> 1; SBM: 49 -> 25, 143 -> 99), but on SBM total wall time rises (22.5 -> 38.7 s, 23.3 -> 32.6 s), i.e. cost per node rises with the added dense rows. This is a post-hoc observation from 4 branching instances.

## Limitations
Synthetic only; one fixed instance order and solver seed; BASE_FULL is the *specified bounded comparator* (thin + simplicial fixing + bounded clique/C5 separation, caps in the script), not all published formulations; only 4 branching instances; hub cap (`|Q|<=8`, 30 cuts) was fixed in advance and not varied; HiGHS only.

## Is a new preregistered harder suite justified?
**Not now.** (1) Novelty is unverified: the key primary source (Chen et al. 2025) was not accessible, so an equivalent projected star statement is not excluded. (2) The theory gate gives an exact LP result only for $d$-regular girth $\ge 6$ graphs ($d\le10$ exact), where all clique/C5 baseline rows are empty — a regime that Stage 1 samples only through the 4 regular $d=4$ graphs (girth not enforced). (3) The only mechanism that survives is "lift reduces nodes but dense rows raise per-node cost", which came from the same 4 branching instances and would be tuned on Stage 1 if used for design.

**Condition to revisit:** if Chen et al. full text rules out an equivalent inequality, one small suite could test a single falsifiable hypothesis on fresh seeds: on sparse regular graphs of girth $\ge 6$ with $d\in\{5,6\}$ and $\alpha>\frac{2}{d+2}$ (where $t\ge2$ rows matter), the augmented arm cuts shifted-geomean nodes by $\ge50\%$ **and** total wall ratio $\le0.85$ with a $\ge$ 8 branching instances; failure of either closes the speed question. Not proposed for execution.
