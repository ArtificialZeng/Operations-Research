# Pre-Outcome Design Closure: Public Treasury Auction Take-Up vs. Direct OFR Repo Segment Pricing

**Date:** 2026-11-24  
**Status:** **FORMALLY CLOSED PRE-OUTCOME AT STAGE 0C — ZERO REPO RATE OUTCOMES READ, INSPECTED, OR FITTED; ZERO RETUNING; NO MANUSCRIPT.**

---

## 1. Executive Decision & Epistemic Precision

This prospective study is **closed prior to any Stage 1 outcome fitting** on the basis of the strictly outcome-blind Stage 0B (`stage0b_precision_overlap_audit.json`) and Stage 0C (`stage0c_availability_and_power_audit.json`) real-time availability, accounting-identity, and planning-power audits.

Two strict epistemic boundaries govern this closure:
1. **Planning Assumptions, Not a Detected Null or Power Proof:** Because zero repo rate outcome series ($Y$) were ever read, inspected, or fitted, the Minimum Detectable Effect (MDE) and power tables below are **analytical planning assumptions** conditional on hypothetical residual noise scales ($\sigma_\varepsilon \in \{1, 2, 3, 5\}$ bps) and the audited $X$-side dispersion of primary-dealer take-up. They are **not** an empirically detected null effect and **not** a formal statistical proof of zero power.
2. **External Effect Analogies Are Distinct Signals:** References to **Anbil, Anderson, Macchiavelli & Xia** (*"Treasury Financing by Hedge Funds: A Tale of Three Channels"*, Table 2: `+0.28 bps` average repo rate and `+0.06 bps` hedge-fund spread per `$10B` net issuance) serve strictly as **net-issuance / hedge-fund funding order-of-magnitude analogies**, **not** estimates of this specific public primary-dealer auction-allocation signal. Together with **Glicoes, Petrasek, Saravay & Tian** (2026-10-30, *FEDS Notes*, DOI `10.17016/2380-7172.4077`, documenting with confidential FR2052a/TRACE/FR2004-WI data that most primary-dealer auction allocations are presold before settlement), **Anbil, Anderson, Cordes & Ruprecht** (2026-08-26, *FEDS Notes*), and **Cordes & Infante** (DOI `10.17016/2380-7172.3707`), these analogies indicate that a realistic incremental public-data auction-allocation effect is far smaller than what `62` post-2024 settlement dates can reliably detect.

---

## 2. Supersession of Initial Stage 1 Draft

The pre-Stage-0C draft (`STAGE1_PROTOCOL.md`) is formally marked **SUPERSEDED AND UNEXECUTED**:
- It treated backfilled pre-launch OFR STFM Preliminary (`-P`) observations (`2018-05`–`2020-09-08`) as real-time public predictors, whereas official OFR STFM documentation establishes that daily `-P` public publication began on **`2020-09-09`** and the first Final (`-F`) quarterly release occurred on **`2021-06-30`**.
- It did not enforce an explicit `-F` quarterly release embargo / released-label mask when expanding the estimation window.
- It was **never executed** (no Stage 1 outcome-fitting script was authored or run).

---

## 3. Verified Outcome-Blind Audit Findings (`stage0c_availability_and_power_audit.json`)

### A. Real-Time Availability & Usable Settlement-Date Support
Across clean nominal fixed-rate U.S. Treasury coupons (`security_type in {Note, Bond}`, excluding TIPS, FRNs, and `< $1B` `$25M` operational test auctions; `209` unique `issue_date`s in `2018-04`–`2026-10`; `196` in the paired non-null OFR `-F` sample `REPO-DVP_AR_OO-F` ∩ `REPO-TRI_AR_OO-F`, `205` in `-P`):
- **OFR STFM Collateral-Scope Disclosure:** Official OFR metadata confirms `REPO-DVP_AR_OO-F` (`1,947` non-null, `87` disclosure-edit/no-trade nulls, `2018-05-08`–`2026-06-30`) and `REPO-TRI_AR_OO-F` (`2,942` non-null, `0` nulls) are tenor-subsetted (`OO`), not collateral×tenor cross-subsetted (`REPO-TRI_AR_OO-F` covers all tri-party collateral including Fed ON RRP; `REPO-TRIV1_AR_OO-F` excludes Fed transactions).
- **NY Fed Primary Dealer Statistics Vintage Disclosure:** The NY Fed Primary Dealer Statistics API (`PDPOSGST-TOT`) serves latest revised values without archival vintages; exact real-time archival availability cannot be claimed without external point-in-time snapshots.
- **Conservative `180`-Day `-F` Release Embargo** (matching the `2026-06-30` `-F` lock observed on `2026-11-24`, so initial training outcomes observably released by `2023-12-31` satisfy `issue_date <= 2023-06-30`):

| Real-Time Compliant Design | Public Predictor Launch | Initial Train (`<= 2023-06-30`) | Final Train (`<= 2026-01-01`) | Usable Post-2024 `-F` Holdout (`2024-01`–`2026-06`) | Usable Post-2024 `-P` Holdout (`2024-01`–`2026-11`) |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Design A** (Real-time OFR `-P` lags + `-F` embargo) | `2020-09-09` | **68** | **128** | **62** | **71** |
| **Design B** (Simpler NY Fed live-since-`2018-04` lags + `-F` embargo; drops backfilled OFR `-P` & revisable PD holdings) | `2018-04-02` | **123** | **183** | **62** | **71** |

### B. Exact Treasury Auction Accounting Identity & Net-Flow Proxy Limit
Verified across `695` settled nominal fixed-rate coupons `>= $1B` (`2018-04`–`2026-11`):
- `primary_dealer_accepted + direct_bidder_accepted + indirect_bidder_accepted == comp_accepted`: **max absolute discrepancy `$0.00`**.
- `comp_accepted + noncomp_accepted + soma_accepted + fima_noncomp_accepted == total_accepted`: **max absolute discrepancy `$0.00`** (omitting `soma_accepted` creates discrepancies up to **`$32,393,526,800.00`** across `551/695` auctions).
- Consequently `private_accepted = total_accepted - soma_accepted` is exact at issuance. However, `buybacks_operations` reports maturity-bucket totals without CUSIP-level retired par (`buybacks_operations_has_cusip_level_retirements = false`), and secondary-market QE/QT alters SOMA holdings between issuance and maturity; therefore scheduled par net flow is strictly a **proxy**, not exact private net cash.

### C. Outcome-Blind Planning-Assumption MDE & Power Table
Using the Stage 0B audited post-2024 clean nominal conditional primary-dealer dollar residual `SD = $3.30B` (`2.21 pp` share residual SD), under the more favorable **Design B** (`N_train = 123 -> 183`, 1-parameter finite-sample OLS estimation penalty `0.65%` vs. `1.02%` in Design A):
- **Required true incremental partial $R^2$ for 80% one-sided $\alpha = 0.05$ Clark–West power**:
  - `N_holdout = 62` (`-F`): **`9.97%`** i.i.d. (**`12.96%`** under mild `1.3x` HAC variance inflation; **`10.63%`** for 80% raw MSE-reduction power under Design B, **`10.99%`** under Design A).
  - `N_holdout = 71` (`-P`): **`8.71%`** i.i.d. (**`11.32%`** HAC; **`9.36%`** raw MSE under Design B).

| Assumed Residual Noise Scale ($\sigma_\varepsilon$) | 80% CW MDE (`N = 62` `-F`, bps per `$10B` PD) | 80% Raw MSE MDE (`N = 62`, Design B) | Multiple of Net-Issuance Analogy (`0.28 bps/$10B`) | Multiple of HF-Spread Analogy (`0.06 bps/$10B`) | Planning Implied $R^2$ at `0.28 bps/$10B` Analogy | Optimistic CW Power at `0.28 bps/$10B` Analogy |
| :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `1.0 bps` | `0.957 bps` | `0.988 bps` | `3.42x` | `15.95x` | `0.854%` | `17.95%` |
| `2.0 bps` | `1.914 bps` | `1.976 bps` | `6.84x` | `31.90x` | `0.213%` | `10.01%` |
| `3.0 bps` | `2.871 bps` | `2.963 bps` | `10.25x` | `47.85x` | `0.095%` | `8.04%` |
| `5.0 bps` | `4.785 bps` | `4.939 bps` | `17.09x` | `79.74x` | `0.034%` | `6.69%` |

Even under the most optimistic `1.0 bps` noise assumption, detecting an effect comparable to the entire net-issuance analogy (`0.28 bps/$10B`) yields under `18%` planning power (`<= 19.3%` on `N = 71` `-P`); under `2.0–3.0 bps` noise, the implied partial $R^2$ (`0.095%–0.213%`) falls strictly below the 1-parameter OLS estimation penalty (`0.65%`–`1.02%`), leaving optimistic planning power at `8.0%–10.0%` (barely above the `5%` Type I error floor).

---

## 4. Closure Verdict & Archival Hygiene

- **Verdict:** **CLOSED PRE-OUTCOME.** No Stage 1 regression or forecast evaluation will be run on this low-$N$ settlement-date public-proxy design.
- **Preserved Diagnostics:** All four outcome-blind audit scripts and summary JSONs (`data_feasibility_pilot.json`, `stage0_corrected_feasibility.json`, `stage0b_precision_overlap_audit.json`, `stage0c_availability_and_power_audit.json`) are archived unmodified as a reproducible pre-outcome feasibility audit without raw rate extracts or outcome peeking.
- **Data Terms Attribution:** U.S. Treasury Fiscal Data and OFR STFM are U.S. government public datasets. NY Fed Markets Data API series (SOFR, TGCR, BGCR, EFFR, ON RRP, and Primary Dealer Statistics) are subject to the Terms of Use posted at `https://www.newyorkfed.org/`; the Federal Reserve Bank of New York is not responsible for any use of the data and does not sanction, endorse, or recommend this audit.
