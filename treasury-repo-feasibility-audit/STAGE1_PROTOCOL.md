> **STATUS: SUPERSEDED AND UNEXECUTED (2026-11-24).**  
> This initial Stage 1 draft was **never executed** (zero repo rate outcomes read, inspected, or fitted) and is **superseded and formally closed pre-outcome** by `CLOSURE_PRE_OUTCOME_POWER.md` and `stage0c_availability_and_power_audit.json`. Specifically, this draft mistakenly treated backfilled pre-launch OFR STFM Preliminary (`-P`) observations (`2018-05`–`2020-09-08`, prior to the official `2020-09-09` public launch) as real-time public predictors, omitted the OFR Final (`-F`) quarterly release embargo (first release `2021-06-30`), and did not reflect the NY Fed Primary Dealer Statistics revision/vintage limitation. Retained verbatim below for transparent audit history only.

---

# Stage 1 Pre-Outcome Protocol: Public Auction Take-Up vs. Direct OFR Repo Segment Pricing

**Directory:** `treasury-repo-feasibility-audit/`  
**Date:** 2026-11-24 | **Status:** **PRE-OUTCOME PROTOCOL — ZERO REPO OUTCOMES FITTED OR INSPECTED.**  
**Audited Support Basis:** `stage0b_precision_overlap_audit.json` (preserving `data_feasibility_pilot.json` and `stage0_corrected_feasibility.json`).

---

## 1. Prospective Public-Signal Estimator Gap (Zero Causation Claim)

Three primary Federal Reserve studies establish the settlement-day Treasury-repo facts:
1. **Glicoes, Petrasek, Saravay & Tian (2026-10-30, *FEDS Notes*, DOI `10.17016/2380-7172.4077`)** use confidential FR2052a, TRACE, and FR2004-WI data to show primary dealer balance sheets expand ~21 cents per issued dollar (~2/3 client repo financing, ~1/3 direct inventory) and that **most auction allocations are presold** before settlement.
2. **Anbil, Anderson, Macchiavelli & Xia (ECB-hosted, *"Treasury Financing by Hedge Funds: A Tale of Three Channels"*, Table 2)** use entity-level repo data on net Treasury settlement days, documenting +0.28 bps average repo rates, +0.06 bps hedge-fund spreads, and +1% hedge-fund borrowing per `$10B` net issuance.
3. **Anbil, Anderson, Cordes & Ruprecht (2026-08-26, *FEDS Notes*)** and **Cordes & Infante (2025/2026, DOI `10.17016/2380-7172.3707`)** model repo spreads controlling for lagged dealer holdings, net Treasury issuance, and QT liquidity.

**Narrow Estimator Gap Tested Here**: Because primary-dealer auction take-up is pre-observed (`auction_date < issue_date`) yet **endogenous** and **largely presold**, this study makes **no causal claim**. It tests strictly whether **publicly released auction buyer composition** provides **incremental, real-time out-of-sample forecasting accuracy** for direct OFR repo segment pricing beyond timestamp-safe public supply, lagged dealer holdings, and liquidity benchmarks.

---

## 2. Fixed Primary Outcome, Collateral Scope, and Matched Support

- **Primary Retrospective Outcome ($Y_t$)**: Like-tenor, same-release-class OFR STFM Final spread in basis points:
  $$Y_t \;=\; 100 \times \bigl(\text{REPO-DVP\_AR\_OO-F}_t \;-\; \text{REPO-TRI\_AR\_OO-F}_t\bigr)$$
  on clean **nominal fixed-rate coupon** settlement dates (`security_type in {Note, Bond}`, excluding TIPS, FRNs, and operational `< $1B` `$25M` test reopenings; `0` duplicate `(cusip, auction_date, issue_date)` keys).
- **Explicit OFR Collateral-Scope Limit**: Official OFR metadata confirms `REPO-DVP_AR_OO-F` (`1,947` non-null, `87` disclosure-edit/no-trade nulls, `2018-05-08`–`2026-06-30`) and `REPO-TRI_AR_OO-F` (`2,942` non-null, `0` nulls) are **tenor-subsetted (`OO`)**, not collateral×tenor cross-subsetted: `REPO-TRI_AR_OO-F` covers all tri-party collateral (including non-Treasury and Fed ON RRP), whereas `REPO-DVP_AR_OO-F` covers FICC DVP (predominantly Treasury). Separately pre-declared robustness checks (never overriding the primary gate): (i) paired Preliminary vintage `REPO-DVP_AR_OO-P - REPO-TRI_AR_OO-P` (`2018-05`–`2026-11`), (ii) ex-Fed `REPO-DVP_AR_OO-F - REPO-TRIV1_AR_OO-F`, and (iii) NY Fed `SOFR`/`TGCR` P50 context.
- **Audited Sample Support (`stage0b_precision_overlap_audit.json`)**: `211` nominal coupon `issue_date`s (`2018-04`–`2026-10`) → `198` paired NON-NULL `-F` dates (`-3` pre-`2018-05-07`, `-1` `2018-12-31` OFR DVP null, `-9` post-`2026-06-30` Final cutoff) → `187` under strict exact `t-2` DVP `-P` lag (dropping `11` quarter-end/month-end dates where `t-2` had a DVP disclosure-edit null). Using a timestamp-safe bounded lookback `[t-5, t-2]` for DVP `-P` and `[t-5, t-3]` for TRI `-P` (still strictly `<= (t-1, 17:00 ET)`, zero unpublished forward-fill, plus staleness indicator) preserves those `11` quarter-end/month-end dates (`196` clean non-test dates); **both** bounded-lookback (primary, zero selective quarter-end loss) and strict exact `t-2`/`t-3` (`N=185` excl. 2 `$25M` test dates) are reported identically.

---

## 3. Named Forecast Cutoff (`t - 1` at `5:00 PM ET`) & Timestamp-Safe Inputs

Every feature for settlement date $t$ must be publicly released by **`5:00 PM ET` on prior NY business day $t - 1$** (zero forward-fill of unpublished data):
- **Auction Results**: `auction_date <= t - 1` (released `~1:00 PM ET` on `auction_date`; verified `100%` `2–15` days pre-settlement).
- **Treasury Buybacks**: `operation_date <= t - 1` (`buybacks_operations`, closes `2:00 PM ET`; `185/185` pre-settlement).
- **Pre-Known Net Supply (Timestamp-Safe Construction & SOMA Disclosure)**: `net_supply_safe_t = gross_private_coupon_t - scheduled_maturing_coupon_par_t - pre_known_buybacks_t`, where `gross_private_coupon_t = sum(total_accepted - soma_accepted)` for auctions settling on $t$ and `scheduled_maturing_coupon_par_t` sums prior issued Note/Bond par with `maturity_date == t` (`734` historical issues back to `1988-05-16`). *Disclosed limitation*: exact SOMA holdings at maturity of older CUSIPs altered by secondary-market QE/QT are not provable from `auctions_query.soma_accepted` alone; therefore `gross_private_coupon_t` and `net_supply_safe_t` enter separately as the provably timestamp-safe supply benchmark.
- **Lagged ON RRP**: `operationDate == t - 1` (closes `1:15 PM ET` on `t - 1`).
- **Lagged OFR Segment Persistence**: Latest published non-null `REPO-DVP_AR_OO-P` in `[t-5, t-2]` (1-bday lag, published `3:00 PM ET` on `t - 1`) and `REPO-TRI_AR_OO-P` in `[t-5, t-3]` (2-bday lag, published `3:00 PM ET` on `t - 1`).
- **Lagged NY Fed Primary Dealer Holdings**: Latest Wednesday `asofdate` of `PDPOSGST-TOT` whose official Thursday `4:15 PM ET` release (next NY business day `>= asofdate + 8` cal days) is `<= t - 1` (`staleness <= 21` days).

---

## 4. Fixed Time Split, Three Comparators, and Nested-Model Inference

- **Fixed Chronological Expanding-Window Split (Consistent Loss Support Across All Models)**:
  - Initial training sample: `2018-05-15` through `2023-06-30` (`N_train_init ≈ 118–124` clean dates).
  - **Primary Fixed Holdout**: **`2023-07-01` through `2026-06-30`** (`N_holdout = 69` strict / `74` bounded-lookback; with the `2024-01-01`–`2026-06-30` sub-window `N = 58` / `62` reported alongside, and `-P` robustness extending through `2026-11-19`).
- **Three Documented Comparators + Parsimonious Candidate**:
  - **C0 (Persistence + Calendar)**: Lagged published OFR segment spread + calendar indicators (`quarter_end`, `month_end`, `mid_month_15`, `dow`).
  - **C1 (Strong Public Supply + Macro-Liquidity + Lagged PD Benchmark)**: `C0` + `net_supply_safe_t` + `gross_private_coupon_t` + value-weighted coupon duration `WAM_t` + lagged `log(1 + ON_RRP_{t-1})` + lagged published `PDPOSGST-TOT`.
  - **C2 (Regularized Strong Benchmark)**: L2-Ridge version of `C1` (penalty selected strictly via expanding-window inner chronological CV inside training dates only).
  - **M_PD (Nested Candidate)**: Adds **1 primary pre-registered scalar signal** — value-weighted settlement-level private primary-dealer coupon share `w_pd_share_private_t` — nested in `C1` (`M_PD_OLS`) and in `C2` (`M_PD_Ridge`). *(Secondary pre-declared 2-feature check adds `w_tail_bps_t = high_yield - avg_med_yield`.)*
- **Pre-Specified Nested Inference & Closure Rule (No Lone DM Gate)**:
  1. **Clark & West (2007) MSPE-adjusted test** with Newey–West HAC variance (`L = 4` settlement dates) for nested `M_PD_OLS` vs. `C1`.
  2. **Moving block-bootstrap** (`B = 5,000`, block length `b = 4` settlement dates) 95% CI on **raw MSE difference** `MSE(C1) - MSE(M_PD)` and **raw MAE difference**, plus raw `R²_OOS = 1 - MSE(M_PD) / MSE(benchmark)` against `C0`, `C1`, and `C2`.
  3. **Pass vs. Closure Gate**: Advance **only if** `M_PD` delivers raw `R²_OOS >= 2.0%` against **both** `C1` and `C2`, Clark–West HAC one-sided `p < 0.05`, AND moving block-bootstrap 95% CI for raw MSE reduction is strictly positive (with consistent direction on `-P` vintage robustness). Otherwise **close formally** without retuning or drafting a manuscript.
