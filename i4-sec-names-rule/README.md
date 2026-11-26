# Bifurcated Regulatory Name Arbitrage: Evidence from the SEC's 2023 "80% Names Rule" Overhaul (`I4`)

**Status:** FROZEN SUBMISSION-READY ARCHIVE (`2026-11-26`)  
**Target Journals:** *Review of Financial Studies* / *Journal of Financial Economics* / *Management Science* (stretch: *Journal of Finance* with `2026Q4` N-PORT Small-Group catch-up cliff)

## Overview
This archive contains the complete, reproducible empirical pipeline, formal equilibrium model, live SEC EDGAR `497`/`485BPOS` prospectus audit, 4-tier cross-quarter CUSIP-consensus look-through holdings analysis, monthly/quarterly investor flow event study, 5 publication figures (`300 DPI PNG` + vector `PDF`), 11 zero-NaN CSV tables, 14-test regression suite, and 17-page camera-ready manuscript PDF evaluating the SEC's September 20, 2023 overhaul of Rule 35d-1 (Release No. IC-35000, extended via IC-35500 to June 11, 2026 for $\ge \$1\text{B}$ complexes; N-PORT reporting delayed separately via IC-35962).

### Headline Verified Findings
- **Universe (`2019Q4–2026Q3`):** `307,298` `REPORT_DATE`-aligned fund-quarters (`303,372` complete `2020Q1–2026Q2`), `935,950` fund-months, `17,151` unique U.S. open-end funds/ETFs across `1,027` unified Rule 0-10(a) complexes (`$46.20T` AUM).
- **Bifurcated Compliance Equilibrium (`2025Q1–2026Q3`):** `161` unique funds (`$299.03B`, `65` complexes) completely stripped newly regulated terms, including `50` non-political constrained multi-asset *Growth*/*Value*/*Income* (`GVI`) funds (`$117.63B`, `19` complexes):
  - **Opaque SEC-Exempt Near-Synonyms:** `84.0%` by fund count (`42/50`, `$49.79B`, `52.4%` captive VA/insurance trusts, `0.0%` index/ETF).
  - **Transparency-Enhancing Numeric Ratios:** `14.0%` by fund count (`7/50`, Vanguard/iShares/Fidelity) representing **`57.7%` of renamed multi-asset AUM (`$67.82B`)** (`85.7%` passive/index-FOF, Fisher `p < 0.0001`).
- **Causal Identification:** `A3_GVI_ALL = +1.71 pp/qtr` (`t = +3.23, p_WCB = 0.002`; joint 13-qtr pre-trend `F = 1.06, p = 0.392`; complete `20Q1–26Q2` `+1.62 pp, p_WCB = 0.002`), driven by opaque synonyms (`+1.55 pp, p_WCB = 0.001`), surviving `COMPLEX_ID × REP_YQ` identifying-only FE (`+1.75 pp, p_WCB = 0.003`), zero-keyword 4-tier look-through `<80%` (`+1.27 pp, p_WCB = 0.003`; `60%–80%` bin jumps `37.2x`), LOFO worst-case (`+1.43 pp, p_WCB = 0.002`), and local `$1B–$10B` Legacy-2001 placebo (`+0.16 pp, p_WCB = 0.346, RI p = 0.206/0.321`).
- **Symmetric Live SEC EDGAR Audit (`N = 211`):** Keepers cite trust-level Rule 35d-1 more often (`66.0%` vs. `42.0%`, Fisher `p = 0.0268`), whereas multi-asset droppers concentrate in name-change filings (`80.0%` vs. `26.0%`, `p < 0.001`; `57.1%` of numeric droppers swear strategies remain unchanged) across April–May 2025 (`7/7` May-2025 on May 1, 2025), Sept 2025, and May 2026 (`28/36 = 77.8%`).
- **Zero Active Rebalancing Toward 80%:** Across `100/100` verified top-100 multi-asset underlying holdings and non-overlapping monthly drift benchmarks (`+55.6%` Eq vs. `+14.2%` Bond), constrained `<80%` droppers shifted `-2.82 pp` away from 80% vs. `+4.10 pp` toward 80% for keepers (**diff `-6.92 pp, t = -4.00, p_WCB = 0.001`**) with **`+13.26 pp` higher `IS_FOF`-controlled 3-year CUSIP overlap (`p_WCB = 0.033`)**.
- **N-PORT Redemption-Sign Correction & Monthly Flows:** Fixing `18.61%` negative-redemption records lifts N-PORT vs. TNA-implied flow correlation from `r = 0.0882` to `r = 0.9546` (`N = 299,416`); monthly event studies (`m = -12..+12`) show flat pre-trends (`MA_GVI p_WCB = 0.70`, `ESG p_WCB = 0.52`), zero redemption runs, dead-flat captive VA flows (`+0.156%/mo, p_WCB = 0.622`), retail gross-sales drag (`-0.566%/mo, t = -2.28`), and positive numeric-ratio flows (`+0.922%/mo, t = +2.00; Qtr +4.40% / +4.52%`).

## Verification & Reproduction Order
1. **Verify Frozen Checksums & Automated Tests First** (before rerunning scripts that regenerate outputs):
   ```powershell
   ruff check scripts/ tests/
   pytest -v tests/test_i4_boost.py
   ```
2. **Optional Full End-to-End Regeneration** (requires official SEC EDGAR N-PORT `2019q4–2026q3` & N-CEN `2020q1–2026q3` bulk extracts and live SEC EDGAR access with compliant `User-Agent`):
   ```powershell
   python scripts/01_build_clean_panel.py
   python scripts/02_edgar_prospectus_audit.py
   python scripts/03_holdings_lookthrough_rebalancing.py
   python scripts/04_econometrics_main_and_robustness.py
   python scripts/05_monthly_flow_event_study.py
   python scripts/06_generate_figures.py
   python scripts/07a_generate_manuscript_md.py
   python scripts/07_verify_citations.py
   python scripts/08_compile_manuscript_pdf.py
   python scripts/09_generate_checksums.py
   ```

## Curated Archive Scope
Heavy intermediate caches omitted from git (`>1.2 GB` raw EDGAR HTML cache, compiled parquet panels, raw SEC zips, `.venv`) are deterministically reproducible via `scripts/01..03`. All 42 core deliverables (scripts, tests, JSON receipts, 11 CSV tables, 5 PNG + 5 vector PDF figures, `manuscript_i4_boost.md`, and 17-page `manuscript_i4_boost.pdf`) are pinned in `SHA256SUMS.json`.
