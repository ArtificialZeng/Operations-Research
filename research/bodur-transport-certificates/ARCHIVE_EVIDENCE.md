# Additional case diagnostics and CAP101 comparisons

The public benchmark summary and replay live in the same directory as this note. The sampled-tree-pool diagnostic retains the same expected-demand initial layout on each public large case. It fits one tree at each of 24 equally spaced total-demand ranks, verifies the tree on its own scenario, then tries the full pool against every non-anchor scenario. The number of certified non-anchors is zero of 1,476 on `large_1` and six of 1,476 on `large_4`. These are known public instances and one fixed layout per case. [Initial layouts and full counts](sampled_tree_pool.json)

Fetch and verify the public inputs using `replay.py` and specify a shared `--cache` directory containing both input files. Use the solver interpreter and the pinned dependencies from the release README.

```sh
python -B measure_pool_coverage.py --instance-dir public-cache \
  --layout-report sampled_tree_pool.json --output pool_recomputed.json
```

The `cap101` directory contains independent fixed-layout and complete Benders comparisons on the original OR-Library cost geometry and locally generated 1,500-scenario draws. The strengthened-master comparison shares its better seed and nearest-facility cuts across both arms. It reaches an objective of 802,784.1983947 and a rigorous lower bound of 783,044.2330792 in both arms. It is an exploratory follow-up. [External source-scale recourse](cap101/RESULT.md) · [Matched master comparison](cap101/MASTER_PROTOCOL.md) · [Exploratory common-master improvement](cap101/CLOSURE_MASTER_PROTOCOL.md)
