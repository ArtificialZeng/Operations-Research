# Opening-stock signal in fixed-and-optimize

The 44-case comparison of `adaptive_window` and chronological windows is complete. The adaptive ordering improved all 16 instances with positive cumulative processing-workload deficit. These follow-up ablations reuse the 44 cases, so they diagnose the observed effect on the same cohort. An independent benchmark will be needed to test generalization.

Compare the repaired full score against two policies derived by removing score terms. The stock-only policy retains the purchased-stock value term and sets the capacity multiplier to one. The policy without stock uses the original setup-cost term and capacity multiplier. Both retain the full policy's normalization, overlap penalty, coverage decay, and tie rule. Reuse the exact solver, initialization, window set, time limit, checker, and input hashes. Run both controls at ten seconds per instance with disjoint two-CPU lanes. Use the earlier chronological and repaired full scores for context. Distinct batches and a single solve per cell leave timing noise in small differences.

Report paired costs and validation for every case, with the same tolerance and one-percent counts as the original protocol. The main diagnostic is full versus each ablation on the 16 positive-deficit cases. Report the complementary 28 and the aggregate. Cost decomposition and completed windows are secondary. If simpler scoring matches the benefit, pursue the opening-stock mechanism with a simpler policy. A consistent gain over both controls would justify sealing the full rule for an independent transfer test.

## Results and decision

The setup-and-capacity score without the stock term passed all 44 checks. It improved 32 cases over chronology, tied 5, and lost 7. Across the 16 cases with positive prefix deficit, it improved all 16 by a median 2.14%. The full score improved the same 16 by a median 1.11%. On a direct pairing within that stratum, the full score won 6 and lost 10, with a median 0.42% cost increase. The median number of completed windows was 16 for each score. [Full score results](fragkos_reserved_window_repair_10s/summary.json) · [Setup and capacity results](fragkos_followup_without_stock_10s/summary.json)

| Ten-second comparison | All cases | Median cost change | Positive prefix deficit | Median cost change |
|---|---:|---:|---:|---:|
| Stock-only vs chronological | 29 / 6 / 9 | −1.02% | 14 / 0 / 2 | −1.85% |
| Setup and capacity vs chronological | 32 / 5 / 7 | −1.12% | 16 / 0 / 0 | −2.14% |
| Full score vs stock-only | 13 / 10 / 21 | 0.00% | 6 / 2 / 8 | +0.03% |
| Full score vs setup and capacity | 15 / 7 / 22 | +0.02% | 6 / 0 / 10 | +0.42% |

Win/tie/loss includes feasibility. Median changes use pairs with two validated costs. The stock-only score passed 43 cases. On `four8` the worker retained an improved checkpoint, then stopped when HiGHS rejected the next full warm start. That failure is counted as a loss to chronological order and omitted from cost-magnitude comparisons. [Stock-only results](fragkos_followup_stock_only_10s/summary.json) · [Worker log](fragkos_followup_stock_only_10s/adaptive_window/degraeve2007_four8/solver.log)

The hypothesized incremental benefit of the full score did not survive term removal. Use the setup-and-capacity score as the strongest validated window baseline from this experiment. Freeze the ordering study as a benchmark comparison. The finding provides no basis to advance a standalone manuscript on inventory-guided ordering. The next lot-sizing question concerns the effect of capacity changes on the economically optimal opening-stock decision.
