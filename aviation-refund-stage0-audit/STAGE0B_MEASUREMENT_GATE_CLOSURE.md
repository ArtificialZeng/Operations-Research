# Stage 0B Legal & Measurement-Gate Closure: U.S. DOT Automatic Cash Refund Rule (`14 CFR Part 260` / FAA § 503)

**Date:** 2026-11-24  
**Status:** **FORMALLY CLOSED AT STAGE 0B MEASUREMENT GATE — ZERO POST-`2024-04` BTS OUTCOME BYTES DOWNLOADED OR ANALYZED.**

---

## 1. Executive Verdict

Following the strictly post-rule-blind Stage 0 (`stage0_bts_and_statute_audit.json`) and Stage 0B (`stage0b_legal_and_measurement_gate.json`) legal-timeline, BTS data-dictionary, OIG tarmac-rule, precedent (*Xing, JEMS*), and pre-rule (`2024-03`) confounder/tail-selection audits, **the statutory refund-notch causal design does not survive the measurement and identification gate** and is **formally closed prior to any post-policy data download or outcome regression**.

- **Explicit Scope Statement:** The published U.S. DOT BTS On-Time Performance dataset supports **descriptive segment operations only**. Both the **statutory policy effect** and **passenger refund receipt** are **unestimated** (zero post-`2024-04` bytes downloaded or analyzed). Prior carrier policies, preexisting `14 CFR § 259.4` tarmac delay rules, and threshold/completion censoring all matter and prevent a credible independent discrepancy estimand from the currently evidenced public data.

---

## 2. Six Verified Stage 0B Measurement & Identification Findings

### 1. Statutory Trigger vs. BTS Segment Delay Universe (`14 CFR §§ 260.2 / 260.6` & FR Footnote 30 vs. BTS `FGJ`)
- **Verified Official Regulatory Text (`FR-2024-04-26/html/2024-07177.htm`, `89 FR 32760`):**
  - Under `14 CFR § 260.2`, `"Significant change of flight itinerary or significantly changed flight"` defines the domestic `3-hour` (`180`-minute) threshold relative to the passenger's **originally purchased itinerary** for **(1) earlier scheduled origination departure (`>= 3h` earlier)** or **(2) later scheduled final-destination arrival (`>= 3h` later)** (`6h` international) — *not* realized positive nonstop `DepDelay`.
  - Under `14 CFR § 260.6`, automatic fare refunds apply only when the passenger declines / does not accept alternative transportation.
  - **FR `2024-07177` Footnote 30** explicitly distinguishes `14 CFR Part 234`'s within-7-day CRS cancellation reporting universe (underlying BTS On-Time Performance) from `14 CFR Part 260`'s purchase-time passenger refund universe.
- **Verified BTS Table `FGJ` Scope (`TableInfo.asp?QO_fu146_anzr=b0-gvzr&gnoyr_VQ=FGJ`):**
  - BTS On-Time Performance records realized nonstop flight segments against the carrier's CRS schedule (`Cancelled Flight`: listed in CRS during the 7 calendar days prior to scheduled departure and not operated). Completed flight clocks cannot mark Part 260 eligibility, and **no defensible untreated comparison or versioned purchased-itinerary data was verified in this audit**.

### 2. Multi-Date Staggered Legal Timeline (No Single Clean Oct 28 Onset)
- `2024-04-26`: Final Rule `89 FR 32760` (`2024-07177`) published.
- `2024-05-16`: **FAA Reauthorization Act of 2024 § 503** (`49 U.S.C. § 42305`) required eligible automatic ticket refunds for cancellations and significant delays starting `May 16, 2024` (per official DOT Small Business Compliance Guidance).
- `2024-06-25`: Final Rule effective date; `2024-10-28`: compliance date for remaining regulatory/ancillary provisions; `2026-07-07`: `91 FR 41556` (`2026-13675`) enforcement discretion pause for *merely renumbered* flights through `2027-07-07`.

### 3. Contrast with Closest Precedent Xing (*JEMS*, `DOI: 10.1111/jems.70019`)
- **Xing, J. (online Dec 2025; *JEMS* Vol. 35(4), pp. 639–655, Oct 2026, `DOI: 10.1111/jems.70019`):** Studies the 2009-era EU rule (EC 261/2004 as interpreted in CJEU *Sturgeon*, Joined Cases C-402/07 & C-432/07, `https://eur-lex.europa.eu/legal-content/en/ALL/?uri=CELEX%3A62007CJ0402`), which establishes **compensation eligibility for covered travelers delayed at the final destination by at least three hours, subject to extraordinary-circumstance exceptions**, and leverages **the paper's eligible/exempt carrier comparison**.
- **U.S. `14 CFR Part 260` / FAA § 503 contrast:** By contrast, **the U.S. rule being studied provides fare refunds in eligible nontravel cases** (not delay compensation to travelers who complete a delayed trip), applies across all U.S. domestic Part 234 reporting carriers simultaneously, and sits atop discretionary pre-2024 carrier Contracts of Carriage; **no defensible untreated comparison or versioned purchased-itinerary data was verified in this audit**.

### 4. Retraction of Invalid "Pure Airborne Placebo" & Exogenous Tail-Shock Claims (Pre-Rule `2024-03` Proof)
- Conditioning on `DepDelay < 120` & `ArrDelay in [120, 240]` (`1,691` flights in `2024-03`; `52` with `DepDelay < 15`) is a completion-conditioned control proxy, not known zero exposure for an entire flight or itinerary.
- Pre-rule `2024-03` tail audit proves severe cancellation-tail missingness: **`1,021 / 5,377` (`18.99%`) of cancelled flights have missing `Tail_Number` vs. `0 / 623,409` (`0.0000%`) of operating flights**. High airport continuity (`467,278 / 474,993` = `98.38%`, with `7,715` discontinuous records) of realized day-tail sequences still reflects **post-assignment** realized rotations on local airport clocks (not UTC) and does not supply pre-assignment or an exogenous pre-cancellation shock.

### 5. Preexisting `14 CFR § 259.4` 3-Hour Tarmac Delay Rule & Denominator Overlap (`2024-03` Pre-Rule Audit)
- Official **DOT OIG Audit `ST2017003`** (Oct 26, 2016, `https://www.oig.dot.gov/library-item/33850`) and **Fukui & Nagata (2014, `DOI: 10.1016/j.ecotra.2014.02.004`)** document cancellation and delay responses to the preexisting domestic 3-hour tarmac delay rule (`14 CFR § 259.4`).
- In pre-rule `2024-03` (`628,786` scheduled: `622,080` completed, `5,377` cancelled, `1,329` diverted): `8.06%` (`1,033 / 12,818`) of completed flights with `DepDelay in [120, 240]` recorded gate-return tarmac time (`TotalAddGTime/LongestAddGTime > 0`), `211` had `TaxiOut >= 60` min (`10 >= 120` min), `189` cancelled flights had non-null pushback `DepDelay` (`49 >= 120` min), and `171` cancelled flights recorded gate-return tarmac time.

### 6. Heterogeneous Clock Heaping & Shifting Carrier Panel (`2022–2026`)
- Pre-rule `2024-03` `[120, 240]`-min `ArrDelay % 5 == 0` varies across carriers (`25.17%` `NK`, `22.10%` `WN`, `21.62%` `AS`, `21.14%` `AA` vs. `19.11%` `DL`, `18.39%` `G4`; cf. Forbes, Lederman & Tombe 2015, `DOI: 10.1257/mic.20130164`).
- Within `2022–2026`, the Part 234 reporting panel shifts due to Alaska–Hawaiian Single Operating Certificate consolidation (`Oct 2025`) and Spirit (`NK`) cessation (`mid-2026`).
- Earlier optimistic Poisson scenario calculations established pre-rule flight-count capacity only (`48/48` `HTTP 200` monthly archives `2022-09`–`2026-08`; `632,162` avg flights/month in `2023-10` & `2024-03`), not causal identifiability.

---

## 3. Closure Decision

The statutory refund-notch causal design is **formally closed at Stage 0B** prior to downloading or analyzing any post-`2024-04` BTS flight data.
