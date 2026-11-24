# Project Status — Elexon GB Wind Forecast Intraday Revision Timing (FROZEN LIMITED NEGATIVE / DIAGNOSTIC ARCHIVE)

- **State:** `FROZEN_LIMITED_NEGATIVE_DIAGNOSTIC_ARCHIVE` (`STOP_DEV_PILOT_GATE_FAILED_NO_HELDOUT_TOUCHED`)
- **Date Sealed:** 2026-11-24
- **Authority Notice:** Authored [`STAGE0_DEV_PILOT_RESULT.md`](STAGE0_DEV_PILOT_RESULT.md) and [`README.md`](README.md) supersede stale `"held_out_untouched": true` / `"held_out_untouched_span"` metadata labels inside unmodified hashed JSON artifacts (`dev_pilot_summary.json`, `STAGE0_DEV_DATA_AUDIT.json`).
- **Pre-Locked Stop Honored:** `L2_LogReg` `ΔBrier = +0.004630` / `+0.001655` (second block `< +0.0020`; pooled `+0.003153`, 95% CI `[-0.000696, +0.007509]`; coarse shuffle `p = 0.0149` descriptive only), `HGB` pooled `-0.000085`, parsimonious `Simple_LagEns` (`0.090800`) beats `L2_LogReg_Cand` (`0.096167`) and `HGB_Cand` (`0.092409`).
- **Scope Corrections Sealed:** (a) Nominal future range `2026-06-04 .. 2026-11-23` was never scored or bulk-fetched for modeling, but earlier feasibility probes inspected `2026-10-15` (with raw 3-day `FUELHH` actuals around Oct 14–16), single-day checks (`2026-07-15`, `2026-09-15`, `2026-11-15`), and unsaved Sept 2026 chunk counts; (b) unconditional `corr(t*_new - t*_old, t*_actual - t*_new)` shares `t*_new` mathematically and `g4: true` is NOT causal mechanism evidence (no conditional mechanism or alternative alignment was scored); (c) official Elexon docs (`wind-generation`, `generation-by-fuel-type`) confirm 30-min average operational metering (not all wind), exact fleet equality and current `WINDFOR` hour statistic remain unproven, and `run_dev_pilot.py` implements `54` exact `X_base` columns (`56 - 2` duplicate levels vs. protocol prose miscount `49`/`47`).
- **Guardrails:** Zero tuning, zero confirmatory fetch/scoring, zero PDF/press/submission/victory/priority claims; `main` (`940709d3...`) and unrelated branches/PRs `#13–#18` untouched.

## Sealed Unmodified SHA-256 Receipts
- 5-Date Feasibility Receipt (`STAGE0_DATA_FEASIBILITY_RECEIPT.json`): `d9a9efbc3c0b0e4b794dd94c441d15ad360e531580c1443b29fd4b50298cf530`
- 594-Day Dev Corpus Audit (`STAGE0_DEV_DATA_AUDIT.json`): `3cd56379305a878e2960b2b2f2f77f596f78c38519998eabfe029eadd970ac2a`
- Pre-Locked Protocol (`STAGE0_DEV_PILOT_PROTOCOL.md`): `08ee7169c7019335c69b43a4d6d528a0ab32bc575da3b5ff84891923d75b2361`
- Dev Pilot Runner (`run_dev_pilot.py`): `d826b11e47c7157a6661b5bfec38a3c0c734a61b089631f02fc45dde7f0fa5fb`
- Native Completed Summary (`PID = 17528`, `26.606 s`, `dev_pilot_outputs/dev_pilot_summary.json`): `d58cfff7f1dcad4cd372fc30d8bb7351d3c82b93bde17d6771e371826a731458`
- Per-Day Prediction Ledger (`298` eval days, `dev_pilot_outputs/dev_pilot_per_day_predictions.jsonl`): `f01e70af2117553893d7bec31519c8675c6bc054062e496daf5bf4dfa960be46`
