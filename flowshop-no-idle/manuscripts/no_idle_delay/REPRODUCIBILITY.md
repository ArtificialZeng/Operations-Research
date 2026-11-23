# Reproducing the fixed-order timing comparison

The timing experiment compares four exact scoring algorithms on five public FrontierOR processing-time prefixes and four deterministic synthetic matrices. All algorithms see the same fixed permutation and experimental costs in each condition. The stored output contains the CPU samples, the exact objective values, the selected machine sets, and source hashes. [Original study record](../../experiments/flowshop_checkpoint_multiquery/results.json)

## Source files

Keep the paths in [the file manifest](REPRODUCIBILITY.sha256) relative to the project root. The main driver is `experiments/flowshop_checkpoint_multiquery/run_multiquery.py`. The original `PROTOCOL.md` beside the driver specifies all test conditions and the extraction of the processing-time prefixes. Refer to the [artifact index](ARTIFACT_INDEX.md) for the proof-related checks and the separate, exploratory permutation-search comparison.

The five public instances and the checker used for input provenance are from `tasks/ruiz2007` at FrontierOR revision `ef42a2eac13595453f986d9df0b62e86e75ab596`. The dataset is credited to Kong et al. and declares CC BY 4.0. Keep the original file bytes if downloading them. The benchmark driver extracts processing-time prefixes and applies its own permutations, costs, and budget queries. It generates the synthetic instances from fixed seeds. [Pinned source](https://huggingface.co/datasets/frontieror/FrontierOR/tree/ef42a2eac13595453f986d9df0b62e86e75ab596/tasks/ruiz2007) · [Dataset license](https://huggingface.co/datasets/frontieror/FrontierOR/blob/ef42a2eac13595453f986d9df0b62e86e75ab596/LICENSE.md)

## Replay in a clean working copy

Use Linux and Python 3.10 or later. These commands assume the current directory is the reproduction root. Pick an available logical CPU on a quiet physical core.

```sh
set -eu
input_dir=antigravity/data_confirmatory/ruiz2007
source_url=https://huggingface.co/datasets/frontieror/FrontierOR/resolve/ef42a2eac13595453f986d9df0b62e86e75ab596/tasks/ruiz2007
mkdir -p "$input_dir/instance"
for i in 1 2 3 4 5; do
  name="instance/large_instance_$i.json"
  curl -fL "$source_url/$name" -o "$input_dir/$name"
done
curl -fL "$source_url/feasibility_check.py" -o "$input_dir/feasibility_check.py"
sha256sum -c manuscripts/no_idle_delay/REPRODUCIBILITY.sha256
replay_cpu=26
taskset -c "$replay_cpu" python3 -B \
  experiments/flowshop_checkpoint_multiquery/run_multiquery.py \
  --cpu "$replay_cpu" > multiquery_replay.json
```

The driver checks 54 distinct budget-and-cost queries and recomputes the returned witnesses. Compare the exact scores, costs, and input hashes with the archived result. CPU times depend on the host. The command above writes a separate result file. The appendix validators are linked from the artifact index. Run older validators in a scratch copy when they write directly into their source directories.
