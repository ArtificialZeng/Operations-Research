# Stage-0 Bounded CPU Dev Pilot Report — GB Wind Forecast Intraday Signed Revision-Timing Signal (FROZEN LIMITED NEGATIVE / DIAGNOSTIC ARCHIVE)

**Date Sealed:** 2026-11-24  
**Authority Notice:** This report and [`README.md`](README.md) are the authoritative scientific record for this frozen negative/diagnostic archive. They explicitly supersede stale `"held_out_untouched": true` / `"held_out_untouched_span"` metadata fields preserved verbatim inside the unmodified hashed JSON outputs (`dev_pilot_summary.json`, `STAGE0_DEV_DATA_AUDIT.json`).  
**Pre-Locked Gate Decision:** **`STOP_DEV_PILOT_GATE_FAILED_NO_HELDOUT_TOUCHED`** (pre-locked stop respected; no tuning, no post-hoc drilling, no confirmatory fetch or scoring; no PDF, press, submission, leaderboard, priority, or novelty claims).

---

## 1. Executive Summary & Pre-Locked Stop Outcome

We tested whether adding **one pre-locked signed timing displacement feature** — `signed_timing_shift = t*(v_new) - t*(v_old)` (UTC-hour displacement of the predicted steepest 3-hour wind drop over `s ∈ {11..18}` UTC between two distinct pre-`11:00 UTC` `WINDFOR` vintages separated by `>= 4 h`, `5.0 h` on `589/594 = 99.2%` of Dev days) — improves real `15:00–18:00 UTC` metered wind-drop warnings beyond strong baselines using the same forecasts.

**Outcome:** Data feasibility passed on the `594`-day Dev span (`2024-10-15 .. 2026-05-31`), but the **pre-locked conjunctive Dev-Pilot gate FAILED** across the `298` disjoint chronological evaluation days (`61` events). We therefore freeze this study as a limited negative/diagnostic archive.

- **Primary `L2_LogReg` (`54 -> 55` features):** `ΔBrier = +0.004630` in `Dev-Val 1` (`N = 150`, `33` events) and **`+0.001655`** in `Dev-Val 2` (`N = 148`, `28` events; **fails** the pre-locked `+0.0020` per-block materiality bar); pooled `ΔBrier = +0.003153` with 5-day block-bootstrap 95% CI **`[-0.000696, +0.007509]`** (spans zero). The coarse 3-stratum conditioned shift-shuffle `p = 0.0149` (`0.0199` / `0.0398`) is strictly **descriptive alongside the failed gate — NOT evidence of a successful revision predictor**.
- **Strong Boosted Comparator (`HGB`, `54 -> 55` features):** `ΔBrier = 0.000000` in `Dev-Val 1` and `-0.000172` in `Dev-Val 2`; pooled **`-0.000085`** (95% CI `[-0.001384, +0.001236]`, placebo `p = 0.5522`).
- **Parsimonious Two-Vintage Lagged-Ensemble Baseline (`Simple_LagEns`, `3` features):** Achieved **`Brier = 0.090800`** pooled (`0.114918` in `Dev-Val 1`, `0.066357` in `Dev-Val 2`, `BSS = 0.4423`, `PR-AUC = 0.7389`) — outperforming `L2_LogReg_Cand` (`0.096167`) by `+0.005367` Brier points, `L2_LogReg_Base` (`0.099320`) by `+0.008520`, and both `HGB_Base`/`HGB_Cand` (`0.092324` / `0.092409`). Thus, the signed timing shift did **not** improve real outturn ramp warnings beyond genuinely strong baselines using the same forecasts.

---

## 2. Explicit Scope & Methodological Corrections (Overriding Stale JSON Metadata Without Rewriting Hashed Artifacts)

1. **Nominal Future Range (`2026-06-04 .. 2026-11-23`) Was NOT Literally Untouched:**
   - The nominal future range `2026-06-04 .. 2026-11-23` was **never bulk-fetched for modeling and never scored**.
   - However, during initial Stage-0 feasibility probing **before** the Dev Pilot lock, earlier probes inspected specific dates inside that nominal future window:
     - `stage0_elexon_feasibility_probe.py` fetched `2026-10-15` (`WINDFOR` `2026-10-14..2026-10-15` and raw 3-day `FUELHH` UTC actuals covering **`2026-10-13T23:00Z .. 2026-10-16T22:30Z`**, i.e., around Oct 14–16).
     - The multi-year availability check (`task-1945`) inspected single-day `WINDFOR`/`FUELHH` summaries on `2026-07-15`, `2026-09-15`, and `2026-11-15`, and the chunking-size test (`task-1955`) queried row counts for `2026-09-01 .. 2026-09-30` (unsaved).
   - Therefore, the nominal future range was **not literally untouched**; the `"held_out_untouched": true` / `"held_out_untouched_span"` strings inside the preserved hashed JSONs (`dev_pilot_summary.json`, `STAGE0_DEV_DATA_AUDIT.json`) are stale metadata labels superseded by this disclosure. Any hypothetical future confirmatory study (not prepared or run here) would have to exclude all UTC dates covered by those prior acquisitions.
2. **Unconditional Timing Correlation Mathematical Coupling (`g4` Is NOT Causal Evidence):**
   - The unconditional correlation reported in `dev_pilot_summary.json` (`corr(t*_new - t*_old, t*_actual - t*_new)`: `r = -0.4307` in `Dev-Val 1`, `-0.2651` in `Dev-Val 2`, `-0.3639` pooled; Spearman `-0.2917`, `-0.2112`, `-0.2573`) **shares `t*_new` on both sides with opposite signs** (`Cov(t*_new - t*_old, t*_actual - t*_new)` includes `-Var(t*_new)` mechanically).
   - Consequently, this unconditional correlation **cannot establish physical or causal mechanism**, and the code flag `g4_mechanism_same_nonzero_sign_both_blocks: true` must **not** be interpreted as causal mechanism evidence.
   - **No conditional timing mechanism test and no alternative first-half vs. second-half hour-alignment evaluation were scored or persisted in the locked pilot outputs.**
3. **Official Elexon Fleet Semantics, Hourly Target Definition & Exact 54-Column Enumeration:**
   - Official Elexon Insights pages explicitly document that [`bmrs.elexon.co.uk/wind-generation`](https://bmrs.elexon.co.uk/wind-generation) compares `WINDFOR` against `Generation by Fuel Type` (`FUELHH`/`FUELINST`), while [`bmrs.elexon.co.uk/generation-by-fuel-type`](https://bmrs.elexon.co.uk/generation-by-fuel-type) reports **30-minute average operational metering** — **not all GB wind** (excluding unmetered/non-BMU embedded wind).
   - Our observed hourly target is explicitly defined as `Actual_hr(D, h) = 0.5 * (FUELHH(h:00Z) + FUELHH(h:30Z))` (1-hour average operational metered MW over `[h:00, h+1:00)` UTC), with `Δ_actual(D) = Actual_hr(D, 18) - Actual_hr(D, 15)`. **Exact fleet equality** between `WINDFOR` and `FUELHH` and the **exact current `WINDFOR` hourly statistic** (hour-average vs. instantaneous) remain **unproven** in this pilot (we only checked descriptive Train-1 MAE against `HH:00`, forward 1h average, and trailing 1h average, which differed by `< 2 MW`).
   - **Exact 54-Column Implementation vs. Protocol Prose Miscount (`49` / `47`):** In [`STAGE0_DEV_PILOT_PROTOCOL.md`](STAGE0_DEV_PILOT_PROTOCOL.md) §2 (preserved byte-unmodified, SHA `08ee7169...`), the prose sum miscounted the five listed feature groups as `49` / `47`. Exact programmatic verification against [`run_dev_pilot.py`](run_dev_pilot.py) confirms the five listed groups total **`56`** items minus **`2`** duplicate level columns (`f_new_15Z`, `f_new_18Z` already included in `f_new_11Z..21Z`) = **`54` exact columns in `X_base`** (`55` in `X_cand` with `signed_timing_shift`):
     1. *Latest level, ramp & timing (`6` listed − `2` dupes = `4` unique):* `r_new_15_18`, `min_drop_new`, `t_star_new`, `abs_t_star_new_minus_15` (`f_new_15Z`, `f_new_18Z` deduplicated into Group 2).
     2. *Both raw trajectories & pointwise updates (`11 + 11 + 11 + 3 = 36` unique):* `f_new_11Z..21Z` (`11`), `f_old_11Z..21Z` (`11`), `df_11Z..21Z` (`11`), `r_old_15_18`, `dr_15_18`, `min_drop_old` (`3`).
     3. *Forecast spacing & seasonal UTC phase (`4` unique):* `lead_new_h`, `gap_pub_h`, `sin_doy`, `cos_doy`.
     4. *Two-version threshold agreement (NHESS 2025 persistence) & lagged ensemble (`6` unique):* `lag_ens_ramp`, `agree_new_flag`, `agree_old_flag`, `agree_both_flag`, `agree_min_new_flag`, `agree_min_old_flag`.
     5. *Strict causal pre-cutoff outturn lag (`4` unique, asserting `publishTime <= D 11:00:00Z`):* `actual_causal_last`, `actual_causal_age_h`, `actual_causal_3h_trend`, `causal_fcst_err`.
     - **Total:** `4 + 36 + 4 + 6 + 4 = 54` identical baseline columns in `X_base`, plus `+1` (`signed_timing_shift`) = `55` columns in `X_cand`.

---

## 3. Native Run Receipts & Reproducibility Inventory

- **Protocol (unmodified):** [`STAGE0_DEV_PILOT_PROTOCOL.md`](STAGE0_DEV_PILOT_PROTOCOL.md) — SHA-256 `08ee7169c7019335c69b43a4d6d528a0ab32bc575da3b5ff84891923d75b2361`
- **Runner (unmodified):** [`run_dev_pilot.py`](run_dev_pilot.py) — SHA-256 `d826b11e47c7157a6661b5bfec38a3c0c734a61b089631f02fc45dde7f0fa5fb`
- **Execution Receipt:** Native CPU run, **PID `17528`**, wall time **`26.606 s`**, `298` eval days (`61` positive events) across `2` disjoint chronological validation blocks (`3`-day purge gaps).
- **Hashed Outputs (unmodified):**
  - [`dev_pilot_outputs/dev_pilot_summary.json`](dev_pilot_outputs/dev_pilot_summary.json): SHA-256 `d58cfff7f1dcad4cd372fc30d8bb7351d3c82b93bde17d6771e371826a731458`
  - [`dev_pilot_outputs/dev_pilot_per_day_predictions.jsonl`](dev_pilot_outputs/dev_pilot_per_day_predictions.jsonl): SHA-256 `f01e70af2117553893d7bec31519c8675c6bc054062e496daf5bf4dfa960be46`
  - [`STAGE0_DATA_FEASIBILITY_RECEIPT.json`](STAGE0_DATA_FEASIBILITY_RECEIPT.json): SHA-256 `d9a9efbc3c0b0e4b794dd94c441d15ad360e531580c1443b29fd4b50298cf530`
  - [`STAGE0_DEV_DATA_AUDIT.json`](STAGE0_DEV_DATA_AUDIT.json): SHA-256 `3cd56379305a878e2960b2b2f2f77f596f78c38519998eabfe029eadd970ac2a`

---

## 4. Block-Wise & Pooled Results

### Table A: Probabilistic Accuracy, Calibration & Discrimination

| Block (`N`, Events, `τ_train`) | Model | Brier | `ΔBrier` vs. Base (95% 5d-Block CI) | BSS | Log-Loss | ECE (5-bin) | Cal Slope | ROC-AUC | PR-AUC | Coarse Placebo `p` (Desc.) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **`Dev-Val 1`** (`150`, `33` ev, `-755.1 MW`) | `Simple_LagEns` (`3`) | **0.114918** | — | 0.3319 | 0.3544 | 0.0384 | 0.910 | 0.8772 | 0.6720 | — |
| `Dev-Val 1` (`2025-08-04..2025-12-31`) | `L2_LogReg_Base` (`54`) | 0.125710 | — | 0.2691 | 0.3716 | 0.0501 | 0.821 | 0.8643 | 0.6312 | — |
| `Dev-Val 1` | `L2_LogReg_Cand` (`55`) | 0.121080 | `+0.004630` `[-0.00297, +0.01263]` | 0.2960 | 0.3651 | 0.0397 | 0.864 | 0.8669 | 0.6471 | `0.0199` |
| `Dev-Val 1` | `HGB_Base` (`54`) | 0.122251 | — | 0.2892 | 0.3636 | 0.0343 | 0.896 | 0.8726 | 0.6025 | — |
| `Dev-Val 1` | `HGB_Cand` (`55`) | 0.122251 | `0.000000` `[0.0, 0.0]` | 0.2892 | 0.3636 | 0.0343 | 0.896 | 0.8726 | 0.6025 | `0.7910` |
| **`Dev-Val 2`** (`148`, `28` ev, `-793.1 MW`) | `Simple_LagEns` (`3`) | 0.066357 | — | 0.5678 | 0.2250 | 0.0658 | 1.084 | 0.9580 | 0.8148 | — |
| `Dev-Val 2` (`2026-01-04..2026-05-31`) | `L2_LogReg_Base` (`54`) | 0.072574 | — | 0.5273 | 0.2343 | 0.0380 | 1.073 | 0.9482 | 0.8113 | — |
| `Dev-Val 2` | `L2_LogReg_Cand` (`55`) | 0.070919 | `+0.001655` `[-0.00246, +0.00429]` | 0.5381 | 0.2292 | 0.0354 | 1.066 | 0.9521 | 0.8100 | `0.0398` |
| `Dev-Val 2` | `HGB_Base` (`54`) | **0.061992** | — | 0.5962 | 0.2047 | 0.0507 | 1.193 | 0.9652 | 0.8282 | — |
| `Dev-Val 2` | `HGB_Cand` (`55`) | 0.062164 | `-0.000172` `[-0.00264, +0.00256]` | 0.5951 | 0.2046 | 0.0473 | 1.206 | 0.9658 | 0.8242 | `0.4876` |
| **`Pooled Dev`** (`298`, `61` ev) | `Simple_LagEns` (`3`) | **0.090800** | — | **0.4423** | 0.2902 | 0.0402 | **0.997** | 0.9174 | **0.7389** | — |
| `Pooled Dev` | `L2_LogReg_Base` (`54`) | 0.099320 | — | 0.3900 | 0.3034 | 0.0248 | 0.942 | 0.9074 | 0.7023 | — |
| `Pooled Dev` | `L2_LogReg_Cand` (`55`) | 0.096167 | `+0.003153` `[-0.00070, +0.00751]` | 0.4093 | 0.2976 | 0.0158 | 0.964 | 0.9110 | 0.7169 | `0.0149` |
| `Pooled Dev` | `HGB_Base` (`54`) | 0.092324 | — | 0.4330 | 0.2847 | 0.0152 | 1.043 | **0.9233** | 0.7156 | — |
| `Pooled Dev` | `HGB_Cand` (`55`) | 0.092409 | `-0.000085` `[-0.00138, +0.00124]` | 0.4324 | **0.2846** | **0.0135** | 1.048 | 0.9216 | 0.7048 | `0.5522` |

### Table B: Operational Warning Cost & False-Alarm Tradeoff (Pooled Dev `N = 298`, `61` Events)

| Model | `p >= 0.30` Hit Rate (TP/FN) | `p >= 0.30` FAR (FP) | `p >= 0.30` Cost (`C/L=0.25`) | `p >= 0.30` Rel. Econ. Value | `p >= 0.50` Hit Rate (TP/FN) | `p >= 0.50` FAR (FP) | `p >= 0.50` Cost (`C/L=0.50`) | `p >= 0.50` Rel. Econ. Value |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`Simple_LagEns`** | 78.7% (`48/13`) | **37.7% (`29`)** | **0.1082** | **0.6284** | **60.7% (`37/24`)** | **24.5% (`12`)** | **0.1628** | **0.4098** |
| `L2_LogReg_Base` | 77.0% (`47/14`) | 42.0% (`34`) | 0.1149 | 0.5847 | 50.8% (`31/30`) | 31.1% (`14`) | 0.1762 | 0.2787 |
| `L2_LogReg_Cand` | **80.3% (`49/12`)** | 43.0% (`37`) | 0.1124 | 0.6011 | 50.8% (`31/30`) | 27.9% (`12`) | 0.1728 | 0.3115 |
| `HGB_Base` | 70.5% (`43/18`) | 40.3% (`29`) | 0.1208 | 0.5464 | 55.7% (`34/27`) | 26.1% (`12`) | 0.1678 | 0.3607 |
| `HGB_Cand` | 73.8% (`45/16`) | 39.2% (`29`) | 0.1158 | 0.5792 | 55.7% (`34/27`) | 26.1% (`12`) | 0.1678 | 0.3607 |

---

## 5. Attribution & Licensing
*Contains BMRS data © Elexon Limited copyright and database right 2026.*  
*Contains BSC information licensed under the BSC Open Data Licence.*  
See [`LICENSES_AND_PROVENANCE.md`](LICENSES_AND_PROVENANCE.md) for official Elexon source URLs, licence links, and archival exclusions.
