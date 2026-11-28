# Manager Choice Under the 2023 SEC Names Rule Rollout: Fund Renaming, Statutory Verification, and Multi-Asset Portfolio Paths (`I4`)

**Status:** MAJOR REVISION `v4` — SUBMISSION-READY ARCHIVE (`2026-11-28`)  
**Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)

## Overview
This archive contains the complete, reproducible empirical pipeline, per-fund EDGAR statutory verification audit, repaired zero-leakage look-through holdings and partial-identification framework, counterfactual placebo and Rambachan–Roth (2023) sensitivity suite, exploratory monthly investor-flow regressions, 5 publication figures (`300 DPI PNG` + vector `PDF`), 18 zero-NaN CSV tables, 9 JSON audit receipts, automated `pytest` verification suite, `REFEREE_RESPONSE_v4.md`, the streamlined 12-page main manuscript (`manuscript_i4_boost.pdf`), and the separate Data & Measurement Appendix (`supplementary_i4_jbf.pdf`) evaluating U.S. multi-asset fund manager choices during the rollout of the SEC's 2023 Rule 35d-1 amendments (Release No. `33-11238 / IC-35000`, extended via `33-11368 / IC-35500` to each fund's first on-cycle annual prospectus update on or after June 11, 2026 for $\ge \$1\text{B}$ groups and December 11, 2026 for $< \$1\text{B}$ groups; *2025–26 Names Rule FAQs*; N-PORT reporting extension `IC-35963` and proposed elimination in Press Release `2026-19`).

### Headline Verified Findings (`v4`)
- **Panel & Reconciliation (`2019Q4–2026Q3`):** `307,298` `REPORT_DATE`-aligned fund-quarters (`303,372` complete `2020Q1–2026Q2`), `935,950` fund-months, `17,151` unique series, `1,027` unified complexes. Complete-quarter `2026Q2` gross sum = **`$44.31T`** (`12,696` series); cross-period latest-record total = **`$46.20T`** (reconciled in Supplementary Appendix A alongside the `18.61%` N-PORT negative-redemption sign harmonization lifting flow concordance from `r = 0.088` to `r = 0.955`).
- **Per-Fund EDGAR Statutory Verification & Concentration (`50` Primary MA GVI Renamers, `$117.63B`, `19` Complexes):**
  - **Label Concentration & Ex-Vanguard:** Non-numeric descriptors account for `84.0%` of funds (`42/50`, `$49.79B`, `42.3%` AUM; `52.4%` VA/insurance). Numeric ratios account for `14.0%` of funds (`7/50`, `3` complexes, `$67.82B`, `57.7%` AUM), of which Vanguard's four LifeStrategy funds represent **`96.2%`** (`$65.26B`). **Excluding Vanguard (`46` funds, `$52.36B`, `18` complexes):** numeric ratios fall to **`4.9%`** of renamed assets (`$2.56B`, `3/46` funds), whereas non-numeric descriptors comprise **`91.3%`** of funds (`42/46`) and **`95.1%`** of assets (`$49.79B`).
  - **Early Timing & Unchanged-Policy Disclosures:** Pass 2 verified effective dates for `50/50` renamers (`49/50` Large $\ge \$1\text{B}$, `1/50` Small $< \$1\text{B}$ under `33-11368`): **`49/50` (`98.0%`)** preceded June 11, 2026, **`49/50`** preceded their own first statutory on-cycle update, and **`36/50` (`72.0%`)** do not reach on-cycle compliance until **2027**. Filings covering `7/50` funds (`$66.67B`, `56.7%` AUM, led by Vanguard `497` `0000736054-26-000102`) explicitly confirmed unchanged objectives/strategies/policies; `2/50` (`$2.28B`, iShares `497` `0001193125-25-028799`) paired with simultaneous benchmark-index renames; `25/50` were silent on statutory basis. Against audited EDGAR disclosures, the `35/50` *Growth*/*Value* lexical screen has **`8.6%` precision** (`100.0%` recall) for Pass-2 fund-scoped Rule 35d-1 citations and is strictly framed as a lexical screen. Same-date unregulated-word control group: **`164`** substantive multi-asset renames (`$287.16B`, `46` complexes).
- **Pre-Trend Transparency, Null Placebos & Sensitivity Bounds:** All **`10/10` historical same-quarter placebos (`2021–2022`, `p_WCB >= 0.214`)** and **`5/5` unregulated-word placebos (`p_WCB >= 0.251`)** are null. Simultaneously, joint pre-trends reject in the *Growth*/*Value* lexical screen (`FAQ2 p = 0.043`; `FAQ4 p = 0.003`), Rambachan–Roth (2023) breakdown values are narrow ($M^* \in [0.002, 0.018]$, $\bar{M}^* \in [0.02, 0.18]$), and Callaway–Sant'Anna (2021) early-due vs. late-FYE large cohort contrasts are null in `2026Q2–Q3` (`-2.82 pp, p_WCB = 0.261`)—mandating a disciplined institutional/descriptive interpretation.
- **Repaired Zero-Leakage Look-Through Holdings & Partial-Identification Bounds:** Streaming `109` amended `REP_YQ = 2023Q2` filings resolved *Capital Income Builder* (`74.9%` Eq / `20.4%` Bond) and *Income Fund of America* (`68.2%` Eq / `24.3%` Bond) directly from historical N-PORT reports and eliminated the silent 100%-equity fallback (`TIER_UNMAPPED` reduced from `5.25%` to **`1.53%`**, **`0/100`** unmapped in top-100; boundary crossers across `2,502` paired GVI funds reduced from `41` to `21`, `0` renamers). Repaired `<80%` GVI largest-class active drift = **`-7.19 pp` (`p_WCB = 0.001`)**, fund-level realized-return drift = **`-6.59 pp` (`p = 0.005`)**, sharp Manski PI set = **`[-11.33, -3.24]` pp** (outer 95% CI `[-15.36, +0.13]` pp). Four-point trajectories (`2023Q2 → 2024Q2 → 2025Q2 → 2026Q2/Q3`) show **`-4.56 pp` (`p_WCB = 0.002`)** already emerged by **`2024Q2`** prior to 2025–2026 renames.
- **Strictly Exploratory Investor Flows:** Pooled MA GVI (`-0.20 pp/mo, p_WCB = 0.404`), Non-numeric (`-0.29 pp/mo, p_WCB = 0.264`), Captive VA (`+0.16 pp/mo, p_WCB = 0.622`), Retail gross sales (`-0.57 pp/mo, p_WCB = 0.025`), Numeric (`+0.92 pp/mo, p_WCB = 0.170`, `7` funds / `3` complexes, Wilcoxon `p = 0.375`). Strictly exploratory descriptive evidence; zero investor-welfare claims.

## Verification & Reproduction Order
1. **Verify Code Lint, Frozen Checksums & Automated Regression Suite First:**
   ```powershell
   .venv\Scripts\ruff.exe check scripts/ tests/
   .venv\Scripts\pytest.exe -v tests/test_i4_boost.py
   ```
2. **Full End-to-End Regeneration:**
   ```powershell
   .venv\Scripts\python.exe scripts/01_build_clean_panel.py
   .venv\Scripts\python.exe scripts/02_edgar_prospectus_audit.py
   .venv\Scripts\python.exe scripts/02b_per_fund_statutory_audit.py
   .venv\Scripts\python.exe scripts/03_holdings_lookthrough_rebalancing.py
   .venv\Scripts\python.exe scripts/04_econometrics_main_and_robustness.py
   .venv\Scripts\python.exe scripts/04b_counterfactual_sensitivity_and_placebos.py
   .venv\Scripts\python.exe scripts/05_monthly_flow_event_study.py
   .venv\Scripts\python.exe scripts/06_generate_figures.py
   .venv\Scripts\python.exe scripts/07a_generate_manuscript_md.py
   .venv\Scripts\python.exe scripts/07_verify_citations.py
   .venv\Scripts\python.exe scripts/08_compile_manuscript_pdf.py
   .venv\Scripts\python.exe scripts/09_generate_checksums.py
   ```

## Curated Archive Scope
Heavy intermediate caches (`>1.2 GB` raw EDGAR HTML cache, compiled parquet panels, raw SEC zips, `.venv`) are deterministically reproducible via `scripts/01..03`. All core v4 deliverables (12 scripts, test suite, 9 JSON receipts, 18 CSV tables, 5 PNG + 5 vector PDF figures, `manuscript_i4_boost.{md,pdf}`, `supplementary_i4_jbf.{md,pdf}`, `REFEREE_RESPONSE_v4.md`, `README.md`, `STATUS.md`) are pinned in `SHA256SUMS.json`.
