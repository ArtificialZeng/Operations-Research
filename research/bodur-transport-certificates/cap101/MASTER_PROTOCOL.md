# CAP101 end-to-end oracle comparison

Freeze the original sampled CAP101 demands, exact rational transportation costs, and original 25 facilities from the recourse pilot. Use the 250-scenario prefix for a short smoke check, then all 1,500 scenarios for a matched comparison under two 30-second process budgets. Run both arms serially on CPU 22 with one HiGHS thread. There is one fixed paired run per workload. The 250-scenario smoke runs `sequential` first, and the 1,500-scenario comparison runs `batch` first. No thresholds, seed, or formulation change after the smoke results. [Frozen CAP101 data specification](PROTOCOL.md)

The common integer Benders master has eight probability-weighted scenario groups. Sort scenarios by increasing total demand with stable ties, then split the ordering into consecutive equal-size groups. Start by evaluating all facilities open. The groups use valid minimum-unit-cost recourse floors. Add a shared lifted optimality cut per group and update the incumbent using the same exact scaled integer arithmetic. Extend closed-facility capacity duals by the largest nonpositive coefficient allowed by the original shipping costs and the selected demand dual. Because the warehouse capacities are equal on CAP101, the peak capacity requirement is an exact minimum open-facility count. HiGHS uses a fixed seed of 42. Different optimal transportation bases can produce different valid cuts, even when the oracle costs agree. [Cut extension](CUT_EXTENSION.md)

`sequential` solves each scenario with the same persistent transportation LP within a layout. `batch` uses the original at-most-24 network bases to recover integer flows where a certificate is available, and uses that same LP on all unresolved scenarios. Both verify every original-cost primal and dual in integer arithmetic and form group cuts through the same code. Each arm submits its best certified layout and group costs to the master as a warm start. The clock includes input loading, cut construction, solving, and witness checking. Keep the last verified upper bound on a budget stop. Reserve 0.75 seconds of the 30 seconds for the final lower-bound check and output.

Report the native master bound separately from a rigorous lower bound. For the latter, solve the final master LP relaxation and use its cut duals only to propose nonnegative rational weights with sum at most one in each group. Assign remaining weight to the group's constant minimum-cost floor. The resulting affine lower bound on cost is minimized exactly over binary layouts satisfying the minimum facility count. All weight and floor arithmetic is performed in integers. The base floor remains valid if no stronger bound is obtained. Report exact objective fractions, wall and CPU time, master iterations, recourse fallback and certificate counts, and the best incumbent flow hash. This is a public-source methods trial with no official competition score.

## Recorded outcome

All four runs exited normally within their measured process budgets. Both 1,500-scenario arms were run serially under CPython 3.14.10 and HiGHS 1.15.1 on CPU 22. They returned the same exactly verified all-open witness and cost. The 250-scenario smoke also returned the same witness and cost in both arms.

| Scenarios | Arm | Wall | Completed layouts | Master cuts | Transport LP calls | Exact batch hits | Uncovered LPs after tree attempts | Recourse wall | Master MIP wall |
| ---: | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 250 | Sequential | 4.254 s | 55 | 440 | 13,750 | 0 | — | 0.778 s | 3.271 s |
| 250 | Batch | 4.255 s | 58 | 464 | 141 | 14,417 | 0 | 0.148 s | 3.993 s |
| 1,500 | Sequential | 29.259 s | 100 | 800 | 150,000 | 0 | — | 8.260 s | 20.874 s |
| 1,500 | Batch | 29.265 s | 113 | 904 | 285 | 169,328 | 0 | 0.972 s | 28.164 s |

On 1,500 scenarios, the common certified upper bound is `49908305511361/60000000` (831,805.0918560). The rigorous lower bound is `39558305511361/60000000` (659,305.0918560), based on the constant cost and capacity-count floors. The solver-reported master bound is 674,305.0918560. The rational LP-dual calculation returned no stronger exact bound. The best witness flow hash for both arms is `8fa5678fae7669df7c1d299382b1a10e5bb21f62a695267a28cdd5aa15760472`. At 250 scenarios the common feasible objective was 833,314.7999004 and the rigorous lower bound was 660,814.7999004.

Per completed 1,500-scenario layout, recourse was 9.60 times faster in the batched arm. The batched arm evaluated 13 additional layouts and spent 28.164 seconds in the master. The final objective, bound, and witness tied. This pair isolates the computational effect of recourse certificates under the tested master and budget. It leaves the quality of a strengthened master open.

## Post-trial check of the master gap

On the same 1,500 scenarios, assigning each customer to the globally cheapest facility is feasible for all-open, with peak facility utilization 36.02%. Break cheapest-facility ties by source index. For each facility (i), define (delta_i) as the mean-demand-weighted increase from the cheapest unit cost to the next-cheapest unit cost over customers assigned to (i). Closing (i) increases transport cost by at least (delta_i), regardless of other closures. The customer sets for different (i) are disjoint. A separate exact lower bound is therefore the all-open cost minus (sum_i\max(0,f_i-\delta_i)), which gives `46974141608881/60000000` (782,902.3601480). This bound uses the original costs and nonnegative demand and drops facility capacity only for the cost lower bound.

Closing facility 4 and assigning each customer to its cheapest open facility is capacity-feasible on every scenario. It costs `99102206886677/120000000` (825,851.7240556), below both timed incumbents. This check was computed after the frozen runs and was outside their budgets. It provides a common stronger seed and a stronger lower bound for a future matched master comparison.
