# Elexon GB Wind Forecast Intraday Revision Timing — Stage-0 Limited Negative / Diagnostic Archive

**Status:** `FROZEN_LIMITED_NEGATIVE_DIAGNOSTIC_ARCHIVE` (`STOP_DEV_PILOT_GATE_FAILED_NO_HELDOUT_TOUCHED`)  
**Authority Notice:** This `README.md` and [`STAGE0_DEV_PILOT_RESULT.md`](STAGE0_DEV_PILOT_RESULT.md) are the authoritative record for this frozen archive, superseding stale `"held_out_untouched": true` / `"held_out_untouched_span"` metadata fields inside the unmodified hashed JSON outputs (`dev_pilot_summary.json`, `STAGE0_DEV_DATA_AUDIT.json`). **No tuning, no post-hoc drilling, no confirmatory fetch or scoring, and no PDF, press, submission, benchmark victory, priority, or novelty claims.**

## Sealed Outcome (`PID = 17528`, `26.61 s`, Summary SHA `d58cfff7...`)
- **Evaluation:** `298` disjoint chronological Dev evaluation days (`Dev-Val 1`: `2025-08-04..2025-12-31`, `150` d, `33` events; `Dev-Val 2`: `2026-01-04..2026-05-31`, `148` d, `28` events; total `61` events, `q20` drop threshold fit strictly per fold's training set).
- **Pre-Locked Gate Failed (`G2`):**
  - `L2_LogReg` (`54 -> 55` features): `ΔBrier = +0.004630` (`Dev-Val 1`) and **`+0.001655`** (`Dev-Val 2` `< +0.0020` bar); pooled `+0.003153`, 5-day block-bootstrap 95% CI **`[-0.000696, +0.007509]`**. The coarse conditioned shift-shuffle `p = 0.0149` is strictly descriptive alongside the failed gate, not a successful revision predictor.
  - `HGB` (`54 -> 55` features): `ΔBrier = 0.000000` (`Dev-Val 1`) and `-0.000172` (`Dev-Val 2`); pooled **`-0.000085`** (`p_placebo = 0.5522`).
  - **Strong Parsimonious Baseline (`Simple_LagEns`, `3` features):** **`Brier = 0.090800`** pooled (`0.114918` / `0.066357`) — outperforming `L2_LogReg_Cand` (`0.096167`) and `HGB_Base`/`HGB_Cand` (`0.092324` / `0.092409`).
- **Key Scope Disclosures:**
  1. **Nominal Future Range (`2026-06-04 .. 2026-11-23`) Not Literally Untouched:** Never scored or bulk-fetched for modeling, but earlier feasibility probes inspected `2026-10-15` (with raw 3-day `FUELHH` actuals around Oct 14–16), single-day checks on `2026-07-15`, `2026-09-15`, `2026-11-15`, and unsaved 30-day chunk counts for Sept 2026; any future confirmation would have to exclude all UTC dates covered by those prior acquisitions.
  2. **Mechanism Non-Claim:** The unconditional correlation `corr(t*_new - t*_old, t*_actual - t*_new)` shares `t*_new` with opposite signs mathematically and cannot establish mechanism (the code boolean `g4: true` is not causal evidence; no conditional mechanism or first/second-half alignment test was scored or persisted).
  3. **Elexon Semantics & Exact 54 Columns:** [`bmrs.elexon.co.uk/wind-generation`](https://bmrs.elexon.co.uk/wind-generation) compares `WINDFOR` against `Generation by Fuel Type`, and [`bmrs.elexon.co.uk/generation-by-fuel-type`](https://bmrs.elexon.co.uk/generation-by-fuel-type) reports 30-minute average operational metering (not all GB wind). Target is `0.5*(FUELHH(h:00Z)+FUELHH(h:30Z))`; exact fleet equality and current `WINDFOR` hour statistic remain unproven. `run_dev_pilot.py` implements `54` exact columns in `X_base` (`56` listed items in `STAGE0_DEV_PILOT_PROTOCOL.md` §2 minus `2` duplicate level columns `f_new_15Z`, `f_new_18Z`; protocol prose miscounted `49`/`47`).

## Reproduction Order
1. Isolated Python 3.12 CPU environment (`numpy`, `pandas`, `scipy`, `scikit-learn`).
2. `python stage0_elexon_feasibility_probe.py` (5-date cross-check of `WINDFOR/stream`, `evolution`, and `FUELHH/stream`).
3. `python fetch_and_audit_dev_corpus.py` (downloads the 20 Dev chunks covering `2024-10-14 .. 2026-06-01` from official public Elexon BMRS API — zero keys/accounts).
4. `python run_dev_pilot.py` (reproduces `dev_pilot_summary.json` and `dev_pilot_per_day_predictions.jsonl`).

## Data Attribution & Licence
*Contains BMRS data © Elexon Limited copyright and database right 2026.*  
*Contains BSC information licensed under the BSC Open Data Licence.*  
See [`LICENSES_AND_PROVENANCE.md`](LICENSES_AND_PROVENANCE.md) and [`MANIFEST.json`](MANIFEST.json).
