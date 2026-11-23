# Transportation-tree reuse on public Bodur instances

The exact tree reused zero certificates in 94,500 binary-scenario evaluations on the larger cases and did not meet the 20% recourse-time reduction threshold. On `tiny`, bounded pivoting avoided 30 of 500 binary LP calls, but binary recourse took 0.491 seconds versus 0.376 seconds with CLP. The independently checked objectives tied in every paired comparison. [Trial report](OFFICIAL_RESULT.md) · [Measured results](measured_results.json)

## Design

Both arms run the same expected-demand initializer, SCIP master, grouping, local branching and persistent CLP solver. `tree` attempts an exact transportation-tree certificate only at binary facility openings and uses CLP on misses. `tree-pivot` also attempts up to eight exact pivots following a failed certificate. Fractional separation always uses the original CLP path. The code reads original JSON decimal tokens for certificate arithmetic, uses the original probabilities and tests the dual extension over all facilities. Internal floating master bounds are numerical diagnostics.

The measured 60-second experiment used two opposite-order pairs on each of `large_1` and `large_4`, fixed core affinity within each pair, and the original public checker plus an independent Decimal audit. A passing pair required both timely feasible witnesses and no regression beyond `max(0.01, 1e-6 times baseline objective)`. The engineering time gate was at least 20% median reduction in binary recourse time. The measured bounded-pivot comparison used only `tiny` at 15 seconds. These are known public inputs. The live task lists `tiny` and `large_1` as contest development cases. [Official task](https://frontieror-challenge.com/problems/bodur2017)

## Linux replay

The measured solver runtime used CPython 3.14.10 with NumPy 2.5.3 and OR-Tools 9.15.6755. The checker used CPython 3.12.16. Create a Linux environment with CPython 3.14 and install the solver dependencies.

```sh
python3.14 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -B replay.py --case tiny --arm tree-pivot --checker-python python3.12 --output ../tiny-pivot-run
.venv/bin/python -B replay.py --case large_1 --arm clp --checker-python python3.12 --output ../large1-clp-run
.venv/bin/python -B replay.py --case large_1 --arm tree --checker-python python3.12 --output ../large1-tree-run
```

The runner fetches the public inputs and checker from the pinned FrontierOR revision in `inputs.json`. It verifies SHA-256 and size on every run, including cached reads. `--cache` accepts a prepopulated directory using the original upstream filenames. `--cpus` accepts a comma-separated Linux CPU list. Use the same cores for compared arms. The default budgets are 15 seconds for `tiny` and 60 seconds for the other cases. The runner writes the witness, logs and checker results into a new local output directory. The shipped results contain no witnesses or raw instances.

The local harness applies CPU affinity, a host wall deadline and a 16 MiB output cap. The measured runs used a Linux namespace sandbox with a private network, read-only code, input and runtime mounts, a 4 GiB cgroup memory cap, no swap and a 256-task cap. The measured solver timer began inside that sandbox. The local timer begins before spawning the solver. This replay inherits host filesystem and network access and does not reproduce those cgroup limits or the official leaderboard environment. Timings need not match the archived values.

The trace diagnostic is separate from the timed benchmark. It instruments tree learning and follows a previously failed basis for a fixed number of pivots. Run `python -B diagnose_tree.py --output ../tiny-diagnostic.json` in the solver environment for the single-pivot trace or add `--depth-probe 8` for the pivot depth profile. The default diagnostic cache is shared with the replay runner.

## Provenance

`base_solver.py`, `official_tree.py`, `tree_pivot.py`, and `audit_witness.py` are byte-for-byte copies of the project solver and audit sources used in the measurement. The baseline originates in Anti-Gravity's Bodur candidate and includes Codex's earlier expected-demand SCIP/CLP work. `instrument.py` recreates the measured integration and entry code, and `replay.py` checks the original instrumented-core digest before running. The bounded repair follows an Anti-Gravity proposal with the potential-shift correction recorded in the trial report. `diagnose_tree.py` has a portable input path. `SHA256SUMS` covers all shipped files other than itself.

The public inputs and official checker come from FrontierOR under CC BY 4.0 and are fetched without modification. The dataset license applies to these upstream artifacts. The underlying optimization problem is from Bodur, Dash, Günlük and Luedtke. [FrontierOR dataset](https://huggingface.co/datasets/frontieror/FrontierOR) · [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) · [Original paper](https://doi.org/10.1287/ijoc.2016.0717)
