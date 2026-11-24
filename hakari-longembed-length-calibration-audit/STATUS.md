# Status — HAKARI / LongEmbed Length-Calibrated Retrieval Audit (FROZEN)

- **State:** **`FROZEN — CLOSE_NO_MEANINGFUL_GAIN` (2026-11-24)** — Both Stage-0 and Stage-1 failed all prespecified `>= +0.030` both-task natural `nDCG@10` gates. No further lexical variants, reruns, tuning, GPU runs, PDFs, or media.
- **Stage-0 Pilot (`PID = 55912`, `15.45 s` CPU):**
  - Source: `hakari-bench/NanoLongEmbed` (`ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e`), `NanoQMSum` (`51q/31d`) & `NanoNarrativeQA` (`50q/41d`).
  - Summary: [`outputs/hakari_stage0_summary.json`](./outputs/hakari_stage0_summary.json) (`SHA-256: 2fee379490cd163d4924128822e8f6db40946f898cc6d13d13927c723cbb4876`).
  - Natural held-out macro: `Empirical_CountCond_Null = 0.7474` vs. `Top3_Mean = 0.7925` and published `Official_WholeDoc_BM25 = 0.7983`; `RRF_BM25_plus_EmpiricalNull = 0.8030` vs. `RRF_BM25_plus_MaxMinusLogN = 0.8069`. Artificial `+100`-chunk suffix stress was negative-only padding and label-dependent (diagnostic only).
- **Stage-1 Follow-Up (`PID = 40612`, `18.16 s` CPU):**
  - Source: fresh independent query groups from `dwzhu/LongEmbed` (`10039a580487dacecf79db69166e17ace3ede392`), `75q / 75` distinct fresh positive-doc groups per task (`150` fresh queries total, `0` overlap with all `200` Nano queries and all `122`/`163` Nano positive doc groups).
  - Summary: [`outputs/hakari_stage1_summary.json`](./outputs/hakari_stage1_summary.json) (`SHA-256: 22e10cfff3551ae0d7e8a771213202c855a8cf978014fc13ecd5a4ba2ccc7945`).
  - Natural fresh held-out macro: `CountCal_Top3 = 0.800821` vs. `Raw_Top3 = 0.797985` (`+0.002836` macro; `+0.007816` QMSum / `-0.002144` NarrativeQA); `RRF_LocalBM25_plus_CountCalTop3 = 0.823283` vs. `RRF_LocalBM25_plus_RawTop3 = 0.824775` (`-0.001492` macro). Pure $\gamma=1.0$ (`0.806162`) remains diagnostic only. `Local_WholeDoc_BM25` uses Lucene IDF (`k1=1.2`) and differs from HAKARI's reference `bm25s` (no official score or contest entry).
- **Reports & Manifest:** [`reports/BEFORE_AFTER_SUMMARY.md`](./reports/BEFORE_AFTER_SUMMARY.md), [`reports/STAGE0_HAKARI_RESULT.md`](./reports/STAGE0_HAKARI_RESULT.md), [`reports/STAGE1_COUNTCAL_TOP3_RESULT.md`](./reports/STAGE1_COUNTCAL_TOP3_RESULT.md), [`PROVENANCE_AND_SCOPE.md`](./PROVENANCE_AND_SCOPE.md), [`MANIFEST.json`](./MANIFEST.json).
