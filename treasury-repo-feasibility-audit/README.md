# Treasury Repo Feasibility Audit (`treasury-repo-feasibility-audit`)

Standalone, closed **pre-outcome** real-time availability, accounting-identity, and analytical planning-power audit for a prospective public-data U.S. Treasury coupon auction take-up vs. direct OFR Short-Term Funding Monitor (STFM) overnight repo segment pricing study (`REPO-DVP_AR_OO-F` vs. `REPO-TRI_AR_OO-F`).

**Status:** **Formally Closed Pre-Outcome at Stage 0C (2026-11-24).**  
**Zero repo rate outcomes ($Y$) were ever read, inspected, or fitted.** No Stage 1 regression or forecast evaluation was executed, no retuning occurred, and no manuscript is submitted.

---

## Key Epistemic Disclosures

1. **Planning Assumptions, Not a Detected Null or Power Proof:** All Minimum Detectable Effect (MDE) and power figures in `audit/stage0c_availability_and_power_audit.json` and `CLOSURE_PRE_OUTCOME_POWER.md` are strictly outcome-blind analytical planning assumptions across hypothetical residual noise scales ($\sigma_\varepsilon \in \{1, 2, 3, 5\}$ bps) combined with audited $X$-side dispersion of primary-dealer auction take-up. They are **not** an empirically detected null effect and **not** a formal proof of zero power.
2. **External Effect Analogies Are Distinct Signals:** References to Anbil, Anderson, Macchiavelli & Xia (*"Treasury Financing by Hedge Funds: A Tale of Three Channels"*, Table 2: `+0.28 bps` average repo rate / `+0.06 bps` hedge-fund spread per `$10B` net issuance) are **net-issuance / hedge-fund funding analogies**, not estimates of this specific public primary-dealer auction-allocation signal.
3. **Initial Stage 1 Draft Superseded and Unexecuted:** `STAGE1_PROTOCOL.md` is retained verbatim with an explicit **SUPERSEDED AND UNEXECUTED** banner because it mistakenly treated backfilled pre-launch OFR STFM Preliminary (`-P`) rows (`2018-05`–`2020-09-08`, before the official `2020-09-09` public launch) as real-time predictors and omitted the OFR Final (`-F`) quarterly release embargo (first release `2021-06-30`).
4. **Zero Raw Rate Extracts / Data Terms Hygiene:** Zero raw rate files and zero individual NY Fed or OFR observation values are included in this archive. All four JSON files contain only API schema/catalog metadata, non-null date counts, aggregate $X$-side quantiles, auction accounting-identity max discrepancies, and analytical planning-power tables (the sole row-level identifiers in `audit/stage0b_precision_overlap_audit.json` are five public-domain U.S. Treasury Fiscal Data `$25M` operational test-auction rows from `api.fiscaldata.treasury.gov`).

---

## Summary of Audited Pre-Outcome Findings (`2026-11-24` Snapshot)

- **Official Real-Time Availability & Support (`clean nominal fixed-rate coupons >= $1B`, `2018-04`–`2026-10`):**
  - OFR STFM `-P` daily public release began `2020-09-09`; first `-F` quarterly release occurred `2021-06-30`. Under a conservative `180`-day `-F` embargo (matching the `2026-06-30` lock observed on `2026-11-24`), initial training outcomes observably released by `2023-12-31` satisfy `issue_date <= 2023-06-30`.
  - **Design A** (real-time post-`2020-09-09` OFR `-P` lags + `-F` embargo): `N_train = 68 -> 128`, **`N_holdout = 62`** post-2024 `-F` settlement dates (`71` on `-P`).
  - **Design B** (live-since-`2018-04` NY Fed published lags + `-F` embargo, dropping backfilled OFR `-P` and unarchived revisable NY Fed Primary Dealer Statistics): `N_train = 123 -> 183`, **`N_holdout = 62`** post-2024 `-F` dates (`71` on `-P`).
- **Exact Treasury Auction Accounting Identity (`695` settled nominal `>= $1B` coupons):**
  - `primary_dealer_accepted + direct_bidder_accepted + indirect_bidder_accepted == comp_accepted` (max abs discrepancy `$0.00`).
  - `comp_accepted + noncomp_accepted + soma_accepted + fima_noncomp_accepted == total_accepted` (max abs discrepancy `$0.00`; omitting `soma_accepted` misses up to `$32.39B` across `551/695` auctions).
  - Scheduled par net flow remains strictly a **proxy** because `buybacks_operations` lacks CUSIP-level retired par and secondary-market QE/QT alters SOMA holdings between issuance and maturity.
- **Planning-Assumption MDE (`N_holdout = 62` `-F`, audited conditional PD residual `SD = $3.30B`):**
  - 80% one-sided `alpha = 0.05` Clark–West power requires true incremental partial `R^2 >= 9.97%` i.i.d. (`12.96%` with `1.3x` HAC; `10.63%` raw MSE under Design B).
  - Across planning noise scales `sigma_eps in {1, 2, 3, 5}` bps, 80% CW MDE is `0.96–4.79 bps` per `$10B` PD (`3.4x–17.1x` the `0.28 bps/$10B` net-issuance rate analogy). Even at the optimistic `1.0 bps` scale, planning power at `0.28 bps/$10B` is `< 18%` (`8.0%–10.0%` at `2.0–3.0 bps`).

---

## Package Contents

- `CLOSURE_PRE_OUTCOME_POWER.md` — Formal Stage 0C pre-outcome closure memo.
- `PROPOSAL_AND_FEASIBILITY_PLAN.md` — Corrected Stage 0 feasibility design and literature grounding.
- `STAGE1_PROTOCOL.md` — Superseded, unexecuted initial Stage 1 draft (retained for audit history).
- `audit/data_feasibility_pilot.py` & `.json` — Initial bounded `2024–2025` API schema/lag check (preserved untouched).
- `audit/stage0_corrected_feasibility.py` & `.json` — Full `2018–2026` OFR/Fiscal Data/NY Fed catalog and provisional overlap check (preserved untouched).
- `audit/stage0b_precision_overlap_audit.py` & `.json` — Strict non-null like-tenor paired OFR metadata/collateral audit, key/reopening audit, drop waterfall, and pure $X$-side dispersion.
- `audit/stage0c_availability_and_power_audit.py` & `.json` — Real-time OFR launch & `-F` embargo audit, exact `$0.00` Treasury auction identity check, buyback granularity check, and analytical planning-power calculations.
- `ARCHIVE_MANIFEST.json` — Exact byte-count and SHA-256 allowlist for all staged files.
- `requirements.txt` & `.gitattributes` — Minimal pinned dependencies and `* -text` line-ending lock.

---

## Reproducibility & Rerun Instructions

No API keys or credentials are required. Tested on Python `3.14.10` with `requirements.txt` (`numpy==2.5.3`, `scipy==1.18.1`).

### 1. Verify Exact Archived Byte Integrity
```bash
python3 -c '
import hashlib, json, pathlib
m = json.loads(pathlib.Path("ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
for entry in m["files"]:
    p = pathlib.Path(entry["path"])
    raw = p.read_bytes()
    assert len(raw) == entry["bytes"], f"size mismatch: {p}"
    assert hashlib.sha256(raw).hexdigest() == entry["sha256"], f"sha256 mismatch: {p}"
print(f"Verified {len(m["files"])} allowlisted files successfully.")
'
```

### 2. Re-Execute Live Outcome-Blind Audits (Optional)
Running the four scripts re-queries live public government REST APIs (note that counts for `2026+` will advance if rerun after `2026-11-24`, so run inside a temporary copy if you wish to keep the frozen `2026-11-24` JSONs intact):
```bash
pip install -r requirements.txt
python3 audit/data_feasibility_pilot.py
python3 audit/stage0_corrected_feasibility.py
python3 audit/stage0b_precision_overlap_audit.py
python3 audit/stage0c_availability_and_power_audit.py
```

---

## Official Primary Sources & Data Terms

- **OFR Short-Term Funding Monitor (STFM) Documentation & Repo Dataset:**  
  https://www.financialresearch.gov/short-term-funding-monitor/documentation/  
  https://www.financialresearch.gov/short-term-funding-monitor/datasets/repo/
- **U.S. Treasury Fiscal Data API (`auctions_query`, `buybacks_operations`):**  
  https://fiscaldata.treasury.gov/api-documentation/
- **Federal Reserve Bank of New York Markets Data API, Primary Dealer Statistics & Terms of Use:**  
  https://markets.newyorkfed.org/static/docs/markets-api.html  
  https://www.newyorkfed.org/markets/counterparties/primary-dealers-statistics  
  https://www.newyorkfed.org/termsofuse
- **Primary Literature References:**
  - Glicoes, J., Petrasek, L., Saravay, Z., & Tian, M. (2026-10-30). *"Treasury Issuance and Dealer Balance Sheets."* Federal Reserve Board, *FEDS Notes*. https://doi.org/10.17016/2380-7172.4077
  - Anbil, S., Anderson, A., Cordes, L., & Ruprecht, R. (2026-08-26). *"Repo Markets and the Fed's Balance Sheet: Implications for Monetary Policy Implementation."* Federal Reserve Board, *FEDS Notes*.
  - Cordes, L., & Infante, S. (2025-02-12; updated 2026). *"Repo Rate Sensitivity to Treasury Issuance and Quantitative Tightening."* Federal Reserve Board, *FEDS Notes*. https://doi.org/10.17016/2380-7172.3707
  - Anbil, S., Anderson, A., Macchiavelli, M., & Xia, F. *"Treasury Financing by Hedge Funds: A Tale of Three Channels."* (Table 2 net-issuance / hedge-fund funding analogies).

**Data Terms Attribution:** U.S. Treasury Fiscal Data and OFR STFM are U.S. government public datasets. SOFR, TGCR, BGCR, EFFR, ON RRP, and Primary Dealer Statistics endpoints queried by the audit scripts are subject to the Terms of Use posted at `newyorkfed.org`; the Federal Reserve Bank of New York is not responsible for any use of the data and does not sanction, endorse, or recommend this audit.
