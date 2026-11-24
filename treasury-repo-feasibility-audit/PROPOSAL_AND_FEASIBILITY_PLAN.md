# Corrected Study Design & Stage 0 Feasibility Plan: Public-Data Treasury Auction Take-Up vs. Direct Repo Segment Pricing

**Working Directory:** `treasury-repo-feasibility-audit/`  
**Authoring Date:** 2026-11-24 (Corrected Pre-Modeling Design)  
**Domain:** Financial Economics / Short-Term Funding Microstructure (non-biology, non-offensive)  
**Stage:** **Stage 0 Corrected Data & Power Feasibility Only — STRICTLY NO OUTCOME REGRESSIONS OR REPO-RATE PEEKS.** Preserves raw first diagnostic `data_feasibility_pilot.json` untouched; writes corrected audit to `stage0_corrected_feasibility.json`.

---

## 1. Closest Recent Primary Literature & Honest Scientific Framing

1. **Glicoes, J., Petrasek, L., Saravay, Z., & Tian, M. (October 30, 2026).** *"Treasury Issuance and Dealer Balance Sheets."* Federal Reserve Board, *FEDS Notes*, DOI: `10.17016/2380-7172.4077`.
   - Directly studies primary dealer Treasury auction take-up, issuance-day inventory, and repo financing using confidential FR2052a, TRACE, and FR2004-WI data. Finds dealer balance sheets expand ~21 cents per dollar of issuance (~2/3 client repo financing, ~1/3 direct dealer inventory), that **most dealer auction allocations are presold (when-issued)** before settlement, and that Treasury buybacks partially offset balance-sheet pressure.
2. **Anbil, S., Anderson, A., Cordes, L., & Ruprecht, R. (August 26, 2026).** *"Repo Markets and the Fed's Balance Sheet: Implications for Monetary Policy Implementation."* Federal Reserve Board, *FEDS Notes*.
   - Analyzes overnight Treasury repo spread sensitivity (`TGCR - IORB`, etc.) controlling for **lagged dealer holdings** and **net Treasury bill/coupon issuance** across changing Federal Reserve liquidity buffers.
3. **Cordes, L., & Infante, S. (February 12, 2025; updated mid-2026).** *"Repo Rate Sensitivity to Treasury Issuance and Quantitative Tightening."* Federal Reserve Board, *FEDS Notes*, DOI: `10.17016/2380-7172.3707`.
   - Estimates repo spread sensitivity to net Treasury issuance across the 2017–2019 and 2022–2026 QT cycles.

### Critical Epistemic & Measurement Boundaries (No Causal Overclaim)
- **Pre-Observed, Not Exogenous**: Primary-dealer auction take-up (`primary_dealer_accepted`, observed on `auction_date` $2$–$14$ days before `issue_date`) is **predetermined** relative to settlement day, **NOT exogenous** (it is endogenous to market demand, volatility, and dealer when-issued positioning) and **distinct from settlement-day held inventory** (because most allocations are presold before settlement per Glicoes et al. 2026). This study makes **no causal identification claim**.
- **Direct Segment Measurements (OFR STFM) vs. Trimmed Pooled Median (SOFR)**: Under official NY Fed methodology, SOFR (`percentRate` = P50) is a volume-weighted median of a trimmed nested pool (Tri-Party + GCF + FICC DVP with the bottom 25% of DVP trimmed for specialness), so `SOFR - TGCR` is **not** a clean DVP or sponsored-repo rate. Primary segment targets therefore use the public **OFR Short-Term Funding Monitor (STFM)** U.S. Repo Markets dataset (`https://www.financialresearch.gov/short-term-funding-monitor/datasets/repo/`, API `https://data.financialresearch.gov/v1/`) providing direct **Treasury-collateral overnight FICC DVP** and **Tri-Party** average-rate and volume series, with NY Fed SOFR/TGCR/BGCR percentiles strictly secondary/contextual.
- **Strictly Pre-Known Information Set**: Every predictor in both the comparator and candidate models must be known strictly **prior** to the settlement-day repo session:
  - **Pre-known net Treasury settlement** on `issue_date`: scheduled private issuance (`total_accepted - soma_accepted` for auctions settling on `t`, determined prior to `t`), minus pre-known private maturing principal on `t` (determined from earlier issuances' `maturity_date` net of SOMA rollovers/redemptions), minus pre-known Treasury buybacks (`v1/accounting/od/buybacks_operations` settled on `t`).
  - **Pre-forecast lagged liquidity & dealer controls**: lagged **ON RRP** (`t - 1`), lagged weekly **NY Fed Primary Dealer holdings / net financing** (published prior to `t`), calendar reporting dummies (quarter-end, month-end, mid-month 15th, tax dates, day-of-week), and lagged segment spreads (`t - 1`). Never use contemporaneous same-day realized ON RRP or contemporaneous flows as controls.

---

## 2. One Discriminating Question & Cheapest Decisive Failure Tests

- **Research Question (Strict Out-of-Sample Incremental Value)**: On the **unique coupon settlement-date unit**, does adding predetermined public auction-composition signals (**value-weighted primary-dealer coupon share / dollar takedown** and **stop-out auction tail** `high_yield - avg_med_yield`) deliver meaningful, statistically reliable **out-of-sample forecasting power** for direct OFR STFM segment pricing (**overnight Treasury DVP rate**, **Tri-Party rate**, and **DVP minus Tri-Party segment wedge**) beyond the strong public comparator (**pre-known net settlement + tenor composition + lagged Primary Dealer holdings + lagged ON RRP + calendar dates + lagged segment spreads**)?
- **Stage 0 Feasibility & Power Kill-Gate (Executed Now — Pure $X$-Side & Metadata Audit, ZERO Outcome Regressions)**:
  1. **OFR STFM Direct Segment Coverage**: Confirm live public API access, exact Treasury-collateral overnight DVP and Tri-Party mnemonics (preliminary `-P` and final `-F`), start/end dates, missingness, and publication vintage availability.
  2. **Fiscal Data Pre-Known Net Settlement & Buyback Coverage**: Verify `auction_date` (strictly `< issue_date`), `median_yield` vs. `avg_med_yield`, `soma_accepted`, `maturity_date`, and `buybacks_operations` schema/coverage, plus NY Fed Primary Dealer holdings API availability.
  3. **Settlement-Date Unit Power & Conditional $X$-Side Variation (Zero $Y$ Touched)**: Across the full overlapping history (2018–2026), compute exact **unique coupon settlement-date count** (`N_settle_total`), **feasible strictly out-of-sample holdout settlement-date count** (`N_settle_holdout`, e.g., `2024–2026`), and **weighted settlement-level dealer-share residual variation** conditional on `log(total_settled_amount) + tenor_bucket_shares + calendar_dummies`. If conditional residual IQR collapses (`< 2.0 pp`) or holdout settlement dates are too sparse (`< 60` dates) or OFR direct segment history is inadequate, **close before modeling**.
- **Stage 1 Out-of-Sample Kill-Gate (Pending Stage 0 Clearance & Explicit Protocol Freeze)**:
  - Must beat the strong public comparator (Anbil–Anderson–Cordes–Ruprecht / Cordes–Infante public analog: pre-known net issuance + lagged PD holdings + lagged ON RRP + calendar + lagged spreads) on strict expanding-window out-of-sample RMSE (Diebold–Mariano one-sided `p < 0.05`) on direct OFR DVP / `DVP - Tri-Party` settlement-day rates. If it fails, close honestly and conclude public auction buyer composition adds no out-of-sample incremental signal beyond pre-known net settlement and lagged dealer/liquidity controls (consistent with Glicoes et al.'s finding that most allocations are presold).

---

## 3. Public Data Terms & Attribution Notice
- **U.S. Treasury Fiscal Data & OFR STFM**: U.S. Government public data (keyless official REST APIs; fetched reproducibly on demand).
- **NY Fed Markets Data API**: SOFR, TGCR, BGCR, EFFR, ON RRP, and Primary Dealer Statistics are subject to the Terms of Use posted at `newyorkfed.org`. The New York Fed is not responsible for any use of the data and does not sanction, endorse, or recommend this study.
