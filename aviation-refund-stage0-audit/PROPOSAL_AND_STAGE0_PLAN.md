> **STATUS: SUPERSEDED AND FORMALLY CLOSED AT STAGE 0B MEASUREMENT GATE (2026-11-24).**  
> This initial Stage 0 draft was **never executed on post-rule data** (zero post-`2024-04` BTS bytes downloaded or analyzed) and is **formally closed** by `STAGE0B_MEASUREMENT_GATE_CLOSURE.md` and `stage0b_legal_and_measurement_gate.json`. Four initial framing errors are explicitly retracted: (1) `14 CFR § 260.2` triggers on scheduled origination departure `>= 3h` earlier or scheduled final destination arrival `>= 3h` later vs. the originally purchased itinerary (NOT realized positive nonstop `DepDelay`); (2) automatic ticket refunds took effect `May 16, 2024` under FAA Reauthorization Act § 503 (NOT a clean single `Oct 28` onset); (3) conditioning on `DepDelay < 120` is a completion-conditioned proxy, not a known zero-exposure placebo; and (4) BTS day-tail records suffer `18.99%` missing `Tail_Number` on cancelled flights (vs. `0.00%` operating), local-clock/airport discontinuities, and post-assignment tail swapping. Also corrected DOI citation errors (`Ater & Orlov` / `Marks` replaced by verified `Fukui & Nagata 2014, DOI: 10.1016/j.ecotra.2014.02.004`, `DOT OIG ST2017003`, and `Xing, JEMS, DOI: 10.1111/jems.70019`). Retained verbatim below for audit history only.

---

# Stage 0 Research Proposal & Pre-Outcome Feasibility Plan: Operational & Bunching Responses to the U.S. DOT 3-Hour Automatic Cash Refund Rule (`14 CFR Part 260`)

**Directory:** `aviation-refund-stage0-audit/`  
**Date:** 2026-11-24  
**Domain:** Empirical Industrial Organization / Aviation Operations & Regulatory Econometrics (non-biology, non-offensive)  
**Stage:** **Stage 0 Strictly Pre-Rule Statute, Literature, Availability & Schema/Power Audit (ZERO post-`2024-04` or post-`2024-10-28` flight outcome bytes downloaded or analyzed).**

---

## 1. Regulatory Shock & Clean Quasi-Experimental Identification

- **Statutory Event:** On **April 26, 2024**, the U.S. Department of Transportation published its Final Rule *Refunds and Other Consumer Protections* (**89 FR 32760**, codified at **14 CFR Part 260**; reinforced by the FAA Reauthorization Act of 2024, Pub. L. 118-63, Sec. 503, enacted May 16, 2024), with **binding compliance effective October 28, 2024**.
- **Bright-Line Financial Notch:** For the first time in U.S. aviation regulation, federal law codifies a uniform **`3-hour` (`180`-minute)** domestic departure or arrival delay threshold triggering **mandatory automatic cash refunds** (within 7 business days for credit cards / 20 calendar days for cash) whenever a passenger declines alternative transportation or vouchers.
- **Closest Primary Literature:**
  1. **Forbes, S. J., Lederman, M., & Tombe, T. (2015).** *"Quality Disclosure Programs and Internal Organizational Practices: Evidence from Airline Flight Delays."* *American Economic Journal: Microeconomics*, 7(2), 1–26 (`DOI: 10.1257/mic.20130164`) — establishes threshold bunching and ACARS vs. manual reporting dynamics at the DOT `15`-minute on-time cutoff using U.S. DOT BTS On-Time Performance microdata.
  2. **Kleven, H. J. (2016).** *"Bunching."* *Annual Review of Economics*, 8, 435–464 (`DOI: 10.1146/annurev-economics-080315-015234`) & **DOT 3-Hour Tarmac Delay Rule literature** (e.g., Marks 2019, *Transportation Research Part A*; Ater & Orlov 2015, *Review of Economics and Statistics*, `DOI: 10.1162/REST_a_00478`) — documents how rigid 3-hour aviation thresholds can induce pre-threshold bunching, strategic cancellations, and schedule padding.
- **Built-In Institutional Placebo & Pre-Determined Operational Shock:**
  - Under `14 CFR Part 260`, an automatic cash refund is triggered ONLY if the passenger chooses **not to travel** due to a significant delay/change.
  - **Treatment Margin 1 (`DEP_DELAY` at `180` minutes):** Pre-departure gate delays reaching `>= 180` minutes directly expose carriers to passenger opt-out and automatic cash refunds.
  - **Built-In Institutional Placebo (`Pure Airborne Delay`):** Flights that depart with `DEP_DELAY < 120` minutes (passengers already boarded and flew) yet arrive with `ARR_DELAY` around `180` minutes due to en-route weather/ATC holding incur **zero** automatic refund liability under `14 CFR Part 260` — providing a sharp within-carrier, within-date placebo around `180` minutes!
  - **Treatment Margin 2 (Predetermined Incoming-Aircraft Shock → Strategic Cancellation):** Matching same-day prior legs via exact aircraft tail number (`TAIL_NUM`) constructs a predetermined incoming-aircraft delay shock to test whether carrier-controlled cancellation hazards (`CANCELLATION_CODE == 'A'`) shift discontinuously around the `180`-minute predicted departure-delay threshold post-`2024-10-28`.
  - **Treatment Margin 3 (Cross-Carrier Pre-Rule Policy Heterogeneity):** Contrasting major carriers whose documented pre-2024 Contract of Carriage / DOT Dashboard refund threshold was strictly looser (`> 3h` or undefined) vs. carriers already at `<= 2h–3h` pre-October 2024 (to be verified directly from official Federal Register `89 FR 32760` text before any Stage 1 lock).

---

## 2. Stage 0 Bounded Non-Outcome Audit (`stage0_bts_and_statute_audit.py`)

Before touching any post-announcement (`2024-04`–`2024-10`) or post-compliance (`2024-11`–`2026-08`) flight files, Stage 0 verifies:
1. Live Federal Register API metadata for `89 FR 32760` (`14 CFR Part 260`) and exact effective dates.
2. Live Crossref metadata for Forbes–Lederman–Tombe (2015), Kleven (2016), and Ater–Orlov (2015).
3. Pure `HTTP HEAD` availability inventory across all `48` monthly BTS `PREZIP` archives (`2022-09` through `2026-08`) for both `Marketing_Carrier` and `Reporting_Carrier` tables (verifying publication lag and byte sizes with **zero post-rule bytes downloaded**).
4. Bounded **2-month pre-rule-only** (`2023-10` and `2024-03`) schema, carrier-roster, 5-minute clock-heaping, `TAIL_NUM` turnaround chain linkage, and `[120, 240]`-minute sample-count & MDE power audit (**100% blind to post-rule outcomes**).
