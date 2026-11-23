# Opening stock and window order in capacitated lot sizing

This package contains the frozen solver sources and 396 recorded ten-second runs on 44 public, 100-period instances from Section 6.5 of Fragkos, Degraeve, and De Reyck. The six development instances are listed in the conversion manifest. The objective retains the authors' opening inventory penalty and the original setup and holding costs. The release supports empirical comparison of whole-model starts, fixed overlapping windows, and alternative window orders on this cohort. [Paper](https://doi.org/10.1287/ijoc.2016.0691) · [Published supplement](https://pubsonline.informs.org/doi/suppl/10.1287/ijoc.2016.0691)

## Results

[results.csv](results.csv) has one row per variant and case. A clean result required normal solver exit and a feasible verdict from the pinned public checker. The 351 clean rows carry the recorded objective and cost breakdown. The remaining 45 rows keep their original failure statuses. The original adaptive policy failed with a matrix broadcasting error on all 44 cases. The stock-only policy failed to retain the warm-start vector on `four8`, after three completed windows. Its saved checkpoint was excluded under the normal-exit rule. Every variant has all 44 case keys, and the no-stock control has 44 clean results.

| Variant | Clean | Failed |
| --- | ---: | ---: |
| `cold` | 44 | 0 |
| `fallback` | 44 | 0 |
| `warm` | 44 | 0 |
| `cutoff` | 44 | 0 |
| `window` | 44 | 0 |
| `adaptive_original` | 0 | 44 |
| `adaptive_repaired` | 44 | 0 |
| `adaptive_stock_only` | 43 | 1 |
| `adaptive_without_stock` | 44 | 0 |

Fixed-order windows beat the per-case minimum of four whole-model arms on 38 of 44 cases, with a median cost reduction of 11.80%. Relative to fixed order, the repaired adaptive policy recorded 30 wins, 6 ties, and 8 losses, with a median cost reduction of 0.79%. The per-case minimum pools four separate ten-second runs. Each CSV cell is a single run on the recorded machine. Follow-up ablations reuse the same cases and diagnose the ordering mechanism within this cohort. [Recorded comparison](RESERVED_RESULT.md) · [Protocol](RESERVED_PROTOCOL.md) · [Ablation protocol](WINDOW_ABLATION.md)

The setup-cost and capacity ablation (`adaptive_without_stock`) passed the checker after normal exit on all 44 cases. On the 16 positive-prefix-deficit cases, it improved on fixed order in all 16. The median paired cost change was −2.14%, compared with −1.11% for the repaired full score. The full score lost 10 of 16 direct comparisons against this ablation. [Recorded ablation rows](results.csv)

`variant` identifies the distinct comparison arm, and `arm` records the solver's original CLI label. The prefix deficit is the maximum positive cumulative gap between the processing time required by demand and available capacity, before setup time. A positive gap certifies that opening stock is necessary. `completed_windows` counts logged completions, including windows completed before a failure. Empty objective fields mark cases without a counted solution. The older original policy was staged with the fixed-order runs and appears as a loaded-file hash in those rows. Its code was only called in the adaptive arm.

## Data and runtime

The archive and instance bytes can be obtained and regenerated locally. The converter checks the SHA-256 of the public author archive, the original README, all 50 source members and all 50 converted byte sequences. It writes only the 44 benchmark cases. Decimal input values and the original capacity profile are preserved. The omitted variable production cost is zero, and each unit of opening stock costs setup cost plus holding cost plus one, matching the author README. The author archive is publicly downloadable and its redistribution license was not established. [Author archive](https://www.dropbox.com/sh/qrlkspnlfmty4fb/AACJuf7uC4v-LAMNyXG9mqvia) · [Conversion lock](provenance/conversion_manifest.json)

The recorded runs used Linux x86-64, CPython 3.14.10, HiGHS 1.15.1, NumPy 2.5.3, two logical CPUs per run and a 4 GiB memory limit with swap disabled. The solver ran in a networkless scope. The checker used CPython 3.12.16. Exact source and runtime metadata for all five batches are in [provenance/replays.json](provenance/replays.json). The portable runner pins two permitted CPUs and applies the same solver process limit. For a resource-matched replay, launch it in a networkless scope with 4 GiB memory, zero swap and a 256-process limit. Host timing and scheduling can affect the outcome.

The original public checker comes from the pinned FrontierOR `degraeve2007` revision. Its SHA-256 is `852bfa355d8d4a1eba3371c32e34cee6c74bd0fc25939a971fedea3f8e78a0fb`. [Public checker](https://huggingface.co/datasets/frontieror/FrontierOR/resolve/ef42a2eac13595453f986d9df0b62e86e75ab596/tasks/degraeve2007/feasibility_check.py)

## Replay one case

Run from this directory on Linux. Use exact Python versions for parity with the recorded package. Replace `two3` with any case key and `adaptive_repaired` with any variant in the table. Use a new output directory for each run. The runner verifies the exact input and checker before execution and writes the verdict and process status separately from the solver's checkpoint.

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p work
curl -fL 'https://www.dropbox.com/sh/qrlkspnlfmty4fb/AACJuf7uC4v-LAMNyXG9mqvia?dl=1' \
  -o work/fragkos2016_horizon_decomposition.zip
REV=ef42a2eac13595453f986d9df0b62e86e75ab596
curl -fL "https://huggingface.co/datasets/frontieror/FrontierOR/resolve/$REV/tasks/degraeve2007/feasibility_check.py" \
  -o work/feasibility_check.py
python convert_fragkos.py work/fragkos2016_horizon_decomposition.zip work/instances
python replay_case.py --case two3 --variant adaptive_repaired --instances work/instances \
  --checker work/feasibility_check.py --checker-python python3.12 \
  --output work/replays/two3-adaptive_repaired
```

Add `--cpus 0,2` using a pair available on the machine to set the affinity explicitly. Use `python convert_fragkos.py work/fragkos2016_horizon_decomposition.zip work/instances --check` to verify an existing conversion. The frozen source and protocol documents retain project-relative references. The executable replay uses only this release, the public archive, and the pinned checker. Raw inputs, locally converted instances, solver witnesses and run logs remain in their original archives or local output directories.
