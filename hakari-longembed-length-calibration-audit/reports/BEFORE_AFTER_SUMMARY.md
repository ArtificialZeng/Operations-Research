# Before/After Summary — Stage-0 (Empirical Count-Calibrated MaxP) vs. Stage-1 (Count-Calibrated Top-3)

**Frozen Verdict:** **`CLOSE_NO_MEANINGFUL_GAIN`** — All prespecified gates (`BOTH tasks improve` AND `macro >= +0.030`) failed across both Stage-0 and Stage-1.  
**Scope:** Strictly scoped to `QMSum` and `NarrativeQA` under a fixed CPU-only lexical `W = 256`-word chunk BM25 pipeline. No official leaderboard/contest entry, no GPU/neural baselines, no post-hoc method selection, no further lexical variants.

---

## 1. Before (Stage-0 Pilot) vs. After (Stage-1 Targeted Follow-Up)

| Dimension | Stage-0 Pilot (`PID = 55912`, `15.45 s`) | Stage-1 Targeted Follow-Up (`PID = 40612`, `18.16 s`) |
|---|---|---|
| **Evaluation Cohort** | `NanoQMSum` (`51q / 31` doc groups) & `NanoNarrativeQA` (`50q / 41` doc groups) from `hakari-bench/NanoLongEmbed` (`ec27cccf...`) | **Fresh independent** `QMSum` (`75q / 75` distinct fresh docs) & `NarrativeQA` (`75q / 75` distinct fresh docs) from `dwzhu/LongEmbed` (`10039a58...`); `150` fresh queries total, `0` overlap with all `200` Nano queries and all `122`/`163` Nano positive doc groups |
| **Calibration & Dev Splits** | Unlabeled bg (`98q`/`98q`, zero qrels); original `dev` (`51q`/`52q`) | Same original unlabeled bg (`98q`/`98q`, zero qrels); same original `dev` (`51q`/`52q`) |
| **Targeted Candidate Method** | `Empirical_CountCond_Null` on single-chunk `MaxP` (LODO z-score, count-dependent POT $\beta(n)$) | `CountCal_Top3` on multi-chunk `Top3_Mean` (5%-upper-trimmed score-only norm, top-1 bg outlier mask, fixed `h=0.50`, globally tied $\beta_{\text{global}}$, dev-locked $\gamma^*=0.25$) |
| **Natural Held-Out: Raw Passage Baselines** | `Raw_MaxP`: `0.7650` (`0.7444` / `0.7856`)<br>`Top3_Mean`: **`0.7925`** (`0.7563` / `0.8287`) | `Raw_MaxP`: `0.766074` (`0.774168` / `0.757979`)<br>`Raw_Top3`: **`0.797985`** (`0.818848` / `0.777123`) |
| **Natural Held-Out: Whole-Doc BM25** | Published official `Official_WholeDoc_BM25`: **`0.7983`** (`0.8065` / `0.7901`) | Same-scored `Local_WholeDoc_BM25` *(Lucene IDF, k1=1.2; differs from official HAKARI `bm25s`)*: `0.794546` (`0.844598` / `0.744493`) |
| **Natural Held-Out: Candidate Method** | `Empirical_CountCond_Null`: **`0.7474`** (`0.7193` / `0.7755`) — **`-0.0451`** vs. `Top3_Mean`, **`-0.0509`** vs. `Official_WholeDoc_BM25` | `CountCal_Top3`: **`0.800821`** (`0.826664` / `0.774978`) — **`+0.002836` macro** vs. `Raw_Top3` (**`+0.007816`** QMSum, **`-0.002144`** NarrativeQA; both 95% CIs straddle zero) |
| **Diagnostic Pure $\gamma=1.0$ Note** | N/A | `0.806162` (`0.834404` / `0.777921`) — **diagnostic only; NOT selected on dev and NOT used for post-hoc method choice** (still `+0.008177`, far below `+0.030`) |
| **Natural Held-Out: BM25 + RRF Fusion** | `RRF_BM25_plus_EmpiricalNull`: `0.8030` vs. `RRF_BM25_plus_MaxMinusLogN`: `0.8069` (`-0.0040`) and `RRF_BM25_plus_RawMaxP`: `0.8058` | `RRF_LocalBM25_plus_CountCalTop3`: **`0.823283`** (`0.875959` / `0.770607`) vs. `RRF_LocalBM25_plus_RawTop3`: **`0.824775`** (`0.880182` / `0.769368`) — **`-0.001492` macro** (`-0.004223` / `+0.001239`) |
| **Non-Rel Length Bias (Diagnostic Only)** | `Q4/Q1`: `1.34x -> 0.99x` (QMSum), `5.44x -> 2.05x` (NarrativeQA) | `Q4/Q1`: `1.55x -> 1.35x` (QMSum), `5.03x -> 3.22x` (NarrativeQA) |
| **Synthetic Suffix Stress** | Negative-only `+100`-chunk distractor padding (**label-dependent diagnostic only; NEVER benchmark progress**) | Omitted from Stage-1 evaluation (not valid benchmark evidence) |
| **Prespecified Gate Outcome** | **ALL 3 GATES FAILED (`STOP_OR_ADAPT`)** | **ALL 3 GATES FAILED (`CLOSE_NO_MEANINGFUL_GAIN`)** |
| **Sealed Summary SHA-256** | `2fee379490cd163d4924128822e8f6db40946f898cc6d13d13927c723cbb4876` | `22e10cfff3551ae0d7e8a771213202c855a8cf978014fc13ecd5a4ba2ccc7945` |

---

## 2. Key Scientific Takeaways

1. **Stage-0 failure modes were cleanly diagnosed and corrected, ruling out an implementation bug:** In Stage-0, fitting an unconstrained count-dependent POT scale $\beta(n)$ on an unlabeled background pool allowed true background matches (`17.1%` QMSum / `10.9%` NarrativeQA of the top-2% tail) to inflate $\beta(n)$ `2.45x` on long QMSum docs, causing sharp rank-1 drops. Stage-1's score-only top-1 background exclusion and globally tied $\beta_{\text{global}}$ eliminated the tail crossover completely (verified out to `r = 50`), reduced natural non-relevant length intrusion on both tasks, and ran in `6.7–11.8 ms` per 75 queries.
2. **Even after clean calibration fixes, count-conditional calibration adds near-zero natural accuracy on lexical BM25:** Across `150` fresh independent queries (`75/75` distinct positive-doc clusters), `CountCal_Top3` achieved `+0.002836` macro over `Raw_Top3` (`65/75` and `69/75` ties) and `-0.001492` macro when fused with `Local_WholeDoc_BM25` via RRF (`69/75` ties on each task).
3. **What actually worked on this fixed lexical pipeline was plain multi-passage evidence and RRF:** Uncalibrated `Raw_Top3` replicated a consistent natural gain over `Raw_MaxP` on both fresh tasks (`+0.044680` QMSum, `+0.019144` NarrativeQA; `+0.031912` macro), and plain `RRF(Local_WholeDoc_BM25, Raw_Top3)` reached `0.824775` macro (`0.880182` QMSum, `0.769368` NarrativeQA).
