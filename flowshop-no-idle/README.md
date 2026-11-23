# Fixed-order flow-shop delay

- [Manuscript PDF](manuscripts/no_idle_delay/submission_pdf/manuscript.pdf)
- [Electronic companion PDF](manuscripts/no_idle_delay/submission_pdf/technical_appendix.pdf)
- [Code and data index](manuscripts/no_idle_delay/ARTIFACT_INDEX.md)

# Referee materials for fixed-order no-idle delay

Companion to *A single availability date changes the approximability of delay in fixed-order flow shops*. Extract the archive and run the commands from its root. Paths in the archive match the research workspace layout. The manuscript and appendix PDFs are supplied separately.

## Archive contents and scope

- `manuscripts/no_idle_delay/replication_package/` contains the independent Python reference implementations, a verifier and its archived report. The verifier checks finite instances and counterexamples for the analytical results, including the general max-plus cascades in Appendices E and F. The mathematical proofs are in the manuscript and appendix.
- `experiments/flowshop_checkpoint_multiquery/` contains the raw timings, exact values and witnesses behind the central timing table, together with the protocol, driver and all of its source and data dependencies. The source-and-input manifest is `manuscripts/no_idle_delay/REPRODUCIBILITY.sha256`.
- The Monge, release-approximation, local-availability, deletion and clock-retention directories include the source, validators and archived JSON for the proof examples and supporting computations. The exploratory outer permutation-search result is included as archived JSON and protocol. The ZIP supports checking its reported numbers, and does not include a standalone replay of that outer search.
- `SHA256SUMS` lists every other file in this ZIP. No credentials, private competition instances or benchmark reference solutions are included.

## Verification and timing replay

The verifier uses Python 3.10 or newer and the Python standard library. Run it in a scratch extraction because it writes a report next to its script.

```sh
sha256sum -c SHA256SUMS
python3 -B manuscripts/no_idle_delay/replication_package/verify_all.py
```

The timing replay uses Linux and `taskset`. The public matrices are already in the archive. Choose one available logical CPU on a quiet physical core. The original timing used CPU 26.

```sh
sha256sum -c manuscripts/no_idle_delay/REPRODUCIBILITY.sha256
replay_cpu=26
taskset -c "$replay_cpu" python3 -B experiments/flowshop_checkpoint_multiquery/run_multiquery.py   --cpu "$replay_cpu" > multiquery_replay.json
```

Compare the replay's exact scores, costs and input hashes with those in the archived JSON. CPU times depend on the host. The linked experiment READMEs describe the supplementary validators. Use a scratch copy for any validator that writes beside its source file.

## Input attribution and research code

The five public `ruiz2007` instance JSON files and the provenance checker are credited to Kong et al., FrontierOR. They are unchanged copies of the audited release at revision `ef42a2eac13595453f986d9df0b62e86e75ab596`. The timing driver extracts the declared processing-time prefixes and uses derived permutations and experimental budget and cost queries. Synthetic inputs are generated from fixed seeds. The upstream dataset declares CC BY 4.0. [Pinned task files](https://huggingface.co/datasets/frontieror/FrontierOR/tree/ef42a2eac13595453f986d9df0b62e86e75ab596/tasks/ruiz2007) · [License notice](https://huggingface.co/datasets/frontieror/FrontierOR/blob/ef42a2eac13595453f986d9df0b62e86e75ab596/LICENSE.md)

The research code and outputs are supplied here for referee evaluation. Public redistribution and any separate reuse license for these project-authored files are subject to confirmation by the corresponding author.
