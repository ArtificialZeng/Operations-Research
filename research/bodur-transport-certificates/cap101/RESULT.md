# CAP101 fixed-layout recourse pilot

The 1,500-scenario capacity-cover test met its prespecified recourse gate. Integer tree certificates evaluated 1,489 of 1,500 scenarios without their own LP solve. The first tree covered 1,209 scenarios. The full batch made 12 LP calls, including the barycenter. Wall time was 0.0214 seconds, compared with 0.0527 for persistent HiGHS and 0.1173 for persistent CLP. The maximum absolute difference in scenario recourse cost against sequential HiGHS was (6.99\times10^{-10}). Every accepted tree passed the exact nonnegativity, original-cost dual feasibility, flow conservation and primal–dual objective checks. [Measurements](result.json) · [Frozen protocol](PROTOCOL.md)

| Layout | Scenarios | Exact certificate hits | LP calls | Batched wall | Persistent HiGHS | Persistent CLP |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| All open | 250 | 250 | 1 | 0.0080 s | 0.0317 s | 0.1005 s |
| Capacity cover | 250 | 240 | 11 | 0.0064 s | 0.0091 s | 0.0204 s |
| All open | 1,500 | 1,500 | 1 | 0.0231 s | 0.1651 s | 0.5664 s |
| Capacity cover | 1,500 | 1,489 | 12 | 0.0214 s | 0.0527 s | 0.1173 s |

The all-open layout has 21.04 times peak demand in supply. The capacity-cover layout opens facilities 0 and 10 and has 1.683 times peak demand. The same capacity-cover policy at 250 scenarios was 1.42 times faster than sequential HiGHS, below the twofold 1,500-scenario gate. These are four single-core measurements on one dataset and two fixed layouts. The observations establish a recourse timing gain in this setting. They leave end-to-end master search, substantially tighter capacity, and other source geometries open.

The pilot ran on Linux under CPython 3.14.10, CPU 22, NumPy 2.5.3, HiGHS 1.15.1 and CLP 1.17.10 from OR-Tools 9.15.6755. CLP runs in a spawned process because the installed OR-Tools and HiGHS wheels expose incompatible shared-library symbols in one process. The reported solver timings start after the process and library startup. They include model setup, tree checks, and all applicable LP calls.

With that runtime, use `python probe.py --output result.json` to fetch the pinned CAP101 data and rerun the four measurements. `--archive PATH` uses an independently obtained copy after verifying its SHA-256. The script records fresh timings, so use a separate output path to preserve the archived pilot. [Public CAP101](https://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/cap101.txt)

## Near-tight follow-up

The 1,500 original scenarios peak at 69,245.200 units. Every source facility can ship 58,268 units, so a single open facility is infeasible and any legal open subset has at least 68.29% headroom. The frozen follow-up keeps facilities 0 and 10 open, scales all realized demands by a common multiplier, and retains the original unit transportation costs. Headroom after rounding was 5.00%. [Frozen stress design](NEAR_TIGHT_PROTOCOL.md)

In all three alternating repetitions, the first tree covered 1,470 scenarios, and exact certificates covered 1,498. The batch made three LP calls including the barycenter. Its median wall time was 0.01858 seconds versus 0.05072 for persistent HiGHS, a 2.73-fold speedup. The largest absolute recourse-cost difference was (1.86\times10^{-9}). The stress test keeps the same two-facility layout and demand directions, so it measures the timing margin under a controlled peak-load change. The evidence concerns fixed opening decisions. Benders cuts valid across different opening vectors and unrounded official inputs require separate tests. [Follow-up measurements](near_tight.json)

Run the follow-up with `python probe_near_tight.py --output near_tight.json` using the same runtime and optional `--archive` path.
