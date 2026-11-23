# Exploratory CAP101 closure cuts and initialization

This post-trial comparison keeps the existing 1,500 CAP101 scenarios, all transport costs, eight scenario groups, original exact oracle checks and single-thread HiGHS settings. The original experiment and source remain frozen. Run both arms serially on CPU 22 under the same 30-second process limit, with `sequential` first. The corresponding original master comparison ran `batch` first. [Original master trial](MASTER_PROTOCOL.md)

Before the common master starts, consider all-open and each single-facility closure. Assign all demand at each customer to its cheapest remaining facility and resolve cost ties by source facility index. Check original facility capacity in every scenario. Use the lowest exact objective among the feasible assignments, breaking ties in enumeration order with all-open first. The shared fixed-layout assignment attains the uncapacitated transportation lower bound for its layout and is therefore optimal recourse for that layout.

For each group, let (A_g) be its probability-weighted all-open nearest-assignment transport cost. Let (\delta_{gi}) be the weighted increase in cost from the nearest to the second-nearest facility over customers whose original nearest facility is (i). For any first-stage vector, the group recourse cost is at least (A_g+\sum_i\delta_{gi}(1-x_i)). Each customer occurs in only one facility's term, and closing multiple facilities cannot make a next available unit of service cheaper. Both arms add the same valid group rows. Preserve the existing lifted Benders cuts, warm-start behavior, and rigorous bound arithmetic. The affine sum of the new rows also gives a separate exact lower bound after minimizing over the minimum open count.

The primary comparison is final exact objective against the common verified single-closure seed. Report both exact upper and lower bounds, comparisons with the original all-open trial, and the measured recourse and master costs. Treat timing and decision differences as descriptive single-pair outcomes. The extra cuts and initial layout are motivated by the already observed CAP101 results.

## Recorded outcome

All 26 candidate starting layouts passed every scenario capacity check. Both arms selected facility 4 as the single closure, yielding the exact seed objective `99102206886677/120000000` (825,851.7240556). Each arm then improved that seed nine times and returned the same 13-facility layout and exactly verified flows. The final objective was `19266820761473/24000000` (802,784.1983947), a 2.79318% decrease from the seed and approximately 3.49% below the original all-open trial. The two changes to the master were tested together across trials.

| Arm | Wall | Layouts checked | Transport LP calls | Exact batch hits | Recourse wall | Master MIP wall |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Sequential | 29.255 s | 78 | 117,000 | — | 11.659 s | 17.336 s |
| Batch | 29.256 s | 93 | 93 | 139,500 | 1.086 s | 28.016 s |

The common rigorous lower bound is `256587934295399627/327680000000` (783,044.2330792), giving a 2.459% certified final gap. The native numeric master bounds were 788,706.91 sequential and 788,910.01 batch. The verified open IDs are `[0, 1, 3, 5, 6, 8, 10, 12, 16, 17, 22, 23, 24]`. The common integer flow hash is `cd2ed9883e4e87747f3f95b487cdb7e8968b4a5317d2a6df1315fda1aca11467`.

The batched solver checked 15 additional layouts and used approximately 12.8 times less recourse wall time per layout. Each checked layout required one barycenter LP, with exact certificates for all of its 1,500 scenarios. The two arms finished with the same objective and rigorous bound under the matched budget. The stronger shared initialization and cuts improved the decisions relative to the seed and the original trial. The extra recourse throughput did not change the final decision in this pair.

Use `taskset -c 22 python closure_master_trial.py --arm sequential --seconds 30 --archive CAP101.txt` and then repeat with `--arm batch` using the same pinned file. The tested script SHA-256 is `7657d14e456d943012e71038a444bd76cb7b532f964dfa4e8fd2723aea9f7e3d`. The CAP101 file is the [original OR-Library download](https://people.brunel.ac.uk/~mastjjb/jeb/orlib/files/cap101.txt).
