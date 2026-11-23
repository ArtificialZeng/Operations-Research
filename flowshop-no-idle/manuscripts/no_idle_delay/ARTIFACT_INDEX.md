# Code and data index

The results in the main manuscript use the fixed order supplied with each instance. The reported timing ratios concern scoring at that fixed order. All figure and table values in this draft refer to existing study outputs.

The central timing result has a [standalone replay procedure](REPRODUCIBILITY.md) and a [source-and-input manifest](REPRODUCIBILITY.sha256).

| Manuscript result | Source and artifacts |
| --- | --- |
| Manuscript PDFs | [Main manuscript](submission_pdf/manuscript.pdf) · [Electronic companion](submission_pdf/technical_appendix.pdf) |
| Standalone INFORMS referee replication suite | [Self-contained Python verifier and report](replication_package/README.md) · [Verification script](replication_package/verify_all.py) · [Max-plus cascade module](replication_package/maxplus_cascades.py) · [Latest run output](replication_package/REPLICATION_REPORT.json) |
| Synchronized Markdown and LaTeX sources | [Main manuscript](manuscript.md) · [Technical appendix](technical_appendix.md) · [Main manuscript LaTeX](latex/manuscript.tex) · [Technical appendix LaTeX](latex/technical_appendix.tex) · [Bibliography](latex/references.bib) |
| Machine-index recurrence and witness recovery | [Proof, implementation and small instances](../../experiments/flowshop_monge_budget/PROOF.md) |
| Initial machine availability and the two-job construction | [Models and exact release-date checks](../../experiments/flowshop_monge_budget/RELEASE_DATES.md) |
| Source-wise bounds and approximation | [Algorithm and certificate archive](../../experiments/flowshop_release_approx/README.md) |
| Timing comparison and public processing-time prefixes | [Input provenance, isolated timing protocol and data](../../experiments/flowshop_checkpoint_multiquery/README.md) |
| Time-limited permutation search in the appendix | [Isolated CPU-limited comparison](../../experiments/flowshop_checkpoint_outer_search/isolated_cpu28.json) |
| Suffix deletion, arbitrary deletion and minimum retention | [Definitions, implementations and stored verification](../../experiments/flowshop_local_availability/README.md) |
| Prior-work positioning | [Primary literature notes](../../experiments/flowshop_manuscript_audit/README.md) |

The repository README describes the reproduction files and third-party attribution.
