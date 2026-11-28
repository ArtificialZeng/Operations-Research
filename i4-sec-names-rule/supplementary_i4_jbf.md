# Online Supplementary Information & Data Appendix: Manager Choice Under the 2023 SEC Names Rule Rollout

Zijian Zeng  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my

---

## Appendix A. Form N-PORT Data Harmonization, Negative-Redemption Sign Audit, and AUM Reconciliation

### A.1. Gross Complete-Quarter Assets (`$44.31T`) vs. Latest-Record Cross-Period Totals (`$46.20T`)

Form N-PORT is filed monthly by registered management investment companies on a staggered fiscal-quarter schedule, meaning portfolio `REPORT_DATE` values fall on different month-ends across registrants within any calendar quarter. Table A1 reconciles panel construction counts from raw SEC bulk extracts through our final deduplicated `REPORT_DATE`-aligned panel (`307,298` fund-quarters) and documents the exact distinction between the `2026Q2` complete-quarter gross sum (`$44.31` trillion across 12,696 covered series) and the cross-period latest-record total (`$46.20` trillion across all 17,151 unique series ever active in `2020Q1–2026Q3`, which retains exited/merged funds at their final reported net assets and includes double-counted fund-of-funds layers).

**Table A1. SEC Form N-PORT Panel Deduplication and Net-Asset Reconciliation**

| Pipeline Audit Stage | Observation / Series Count | Notes |
| --- | ---: | --- |
| Raw Form N-PORT rows (`2019Q4–2026Q3`) | 355,115 | All `NPORT-P` and `NPORT-P/A` filings |
| Excluded blank `SERIES_ID` & closed-end sentinel `S000000000` | 18,862 | Prevents cross-CIK sentinel collisions |
| `NPORT-P/A` amendments & within-quarter duplicates replaced | 5,451 | Latest amendment retained per `(SERIES_ID, REPORT_DATE)` |
| Final `REPORT_DATE`-aligned panel (`2020Q1–2026Q3`, excl. MMFs) | 307,298 | `303,372` complete `2020Q1–2026Q2`; `17,151` unique series |
| Complete-quarter `2026Q2` gross sum of net assets | `$44.31T` | `12,696` active series in `REP_YQ = 2026Q2` (incl. FOF positions) |
| Cross-period latest-record sum across all `17,151` series | `$46.20T` | Each series' latest report across `2020Q1–2026Q3` (incl. pre-2026 exits) |

### A.2. Form N-PORT Negative-Redemption Sign Convention Audit (`18.61%`, $r: 0.088 \to 0.955$)

SEC Form N-PORT Item B.6 instructs filers to report monthly share sales (`SALES_FLOW_MON1–3`), dividend reinvestments (`REINVESTMENT_FLOW_MON1–3`), and share redemptions (`REDEMPTION_FLOW_MON1–3`). Across 1,006,141 non-missing monthly redemption entries in our panel, **187,263 records (`18.61%` of non-missing; `22.01%` of non-zero)** are reported with negative signs rather than positive magnitudes (consistent across Month 1 `18.53%`, Month 2 `18.60%`, and Month 3 `18.71%`). Computing net flow naively as `SALES + REINVEST - REDEMPTION` double-counts outflows as positive inflows on those 18.61% of records, collapsing Pearson agreement with TNA-and-return-implied quarterly flows (`(TNA_t - TNA_{t-1}(1+R_t)) / TNA_{t-1}`) to **`r = 0.088`** (`r = 0.611` after clipping, Spearman $\rho = 0.632$). Harmonizing redemption magnitudes via `NET_FLOW = SALES + REINVEST - |REDEMPTION|` lifts concordance to **`r = 0.955`** (Spearman $\rho = 0.902$) across 299,416 fund-quarters, and from `r = 0.185` to **`r = 0.958`** inside the 58,750 negative-redemption quarters (Figure A1). This is strictly a measurement harmonization result and does not infer filer intent.

<!-- FIGURE:figA1_redemption_sign_audit.png -->

---

## Appendix B. Per-Fund Statutory EDGAR Audit Ledger (All 50 Primary Multi-Asset Renamers)

Table B1 lists all 50 primary multi-asset `GVI` renamers (`2025Q1–2026Q3`), sorted by prior-report net assets, showing exact `SERIES_ID`, unified complex, pre- and post-rename titles, fiscal-year-end month and statutory `$1B` tier under SEC Release `33-11368`, Pass-2 verified effective date, computed first eligible on-cycle annual prospectus update date, and verified EDGAR disclosure category. The complete machine-readable ledger with full `CIK10`, SEC EDGAR filing URLs, Pass-1/Pass-2 disagreement notes, and verbatim text snippets is archived in `tables/table_50_renamers_statutory_audit.csv`, alongside the 50 stratified retained controls in `tables/table_50_retained_statutory_audit.csv` and the 164 substantive unregulated-word multi-asset renames in `tables/table_unregulated_renamers_control.csv`.

**Table B1. Complete Per-Fund Statutory Verification Ledger (`N = 50` Primary Multi-Asset GVI Renamers)**

| Series ID | Complex | Pre-Name -> Post-Name | AUM ($M) | FYE (Tier) | Verified Eff. Date | First On-Cycle Date | Audit Category |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| `S000002928` | VANGUARD | VANGUARD LIFESTRATEGY GROWTH FUND -> VANGUARD LIFESTRATEGY 80/20 FUND | 26164.5 | M10 (Large) | 2026-05-12 | 2027-02-28 | Unchanged policy confirmed |
| `S000002930` | VANGUARD | VANGUARD LIFESTRATEGY MODERATE GROWTH FUND -> VANGUARD LIFESTRATEGY 60/40 FUND | 23887.0 | M10 (Large) | 2026-05-12 | 2027-02-28 | Unchanged policy confirmed |
| `S000006796` | PRUDENTIAL / PGIM | AST Prudential Growth Allocation Portfolio -> AST PGIM Aggressive Multi-Asset Portfolio | 13176.3 | M12 (Large) | 2025-05-01 | 2027-04-30 | Multi-fund rebrand w/ unreg. |
| `S000006791` | PRUDENTIAL / PGIM | AST Capital Growth Asset Allocation Portfolio -> AST Aggressive Asset Allocation Portfolio | 11308.8 | M12 (Large) | 2025-05-01 | 2027-04-30 | Fund cites 35d-1 (silent) |
| `S000002927` | VANGUARD | VANGUARD LIFESTRATEGY CONSERVATIVE GROWTH FUND -> VANGUARD LIFESTRATEGY 40/60 FUND | 11181.4 | M10 (Large) | 2026-05-12 | 2027-02-28 | Unchanged policy confirmed |
| `S000002929` | VANGUARD | VANGUARD LIFESTRATEGY INCOME FUND -> VANGUARD LIFESTRATEGY 20/80 FUND | 4031.2 | M10 (Large) | 2026-05-12 | 2027-02-28 | Unchanged policy confirmed |
| `S000021944` | BRIGHTHOUSE | American Funds Growth Allocation Portfolio -> American Funds Aggressive Allocation Portfolio | 2711.4 | M12 (Large) | 2025-02-26 | 2027-04-30 | Strategy/adviser change |
| `S000004876` | FIDELITY | Fidelity Freedom Income Fund -> Fidelity Freedom Retirement Fund | 2394.6 | M3 (Large) | 2025-09-09 | 2026-07-29 | Silent on statutory basis |
| `S000023587` | BLACKROCK / ISHARES | iShares Core Growth Allocation ETF -> iShares Core 60/40 Balanced Allocation ETF | 2259.5 | M7 (Large) | 2025-02-19 | 2026-11-28 | Paired benchmark rename |
| `S000045942` | HOWARD CAPITAL (HCM) | HCM Tactical Growth Fund -> HCM Tactical Plus Fund | 1785.2 | M6 (Large) | 2025-07-21 | 2026-10-28 | Multi-fund rebrand w/ unreg. |
| `S000026411` | FIDELITY | Fidelity Freedom Index Income Fund -> Fidelity Freedom Index Retirement Fund | 1763.1 | M3 (Large) | 2025-09-09 | 2026-07-29 | Silent on statutory basis |
| `S000026281` | VOYA | VOYA RETIREMENT GROWTH PORTFOLIO -> Voya Retirement Aggressive Portfolio | 1669.3 | M12 (Large) | 2025-04-28 | 2027-04-30 | Silent on statutory basis |
| `S000011112` | BRIGHTHOUSE | SSGA Growth and Income ETF Portfolio -> State Street Moderate ETF Portfolio | 1606.5 | M12 (Large) | 2025-11-06 | 2027-04-30 | Strategy/adviser change |
| `S000026282` | VOYA | VOYA RETIREMENT MODERATE GROWTH PORTFOLIO -> Voya Retirement Moderately Aggressive Portfolio | 1142.3 | M12 (Large) | 2025-04-28 | 2027-04-30 | Silent on statutory basis |
| `S000007932` | TRANSAMERICA | Transamerica JPMorgan Asset Allocation - Growth VP -> Transamerica JPMorgan Diversified Equity Allocation VP | 1137.9 | M12 (Large) | 2025-08-01 | 2027-04-30 | Silent on statutory basis |
| `S000009325` | GOLDMAN SACHS | Goldman Sachs Growth and Income Strategy Portfolio -> Goldman Sachs Moderate Allocation Fund | 1064.3 | M12 (Large) | 2025-12-16 | 2027-04-30 | Unchanged policy confirmed |
| `S000001163` | GUIDESTONE CAPITAL | Growth Allocation Fund -> Moderately Aggressive Allocation Fund | 1056.8 | M12 (Large) | 2025-05-01 | 2027-04-30 | Strategy/adviser change |
| `S000059204` | SUNAMERICA / COREBRIDGE | SA T. Rowe Price Asset Allocation Growth Portfolio -> SA T. Rowe Price Allocation Moderately Aggressive Portfolio | 774.0 | M1 (Large) | 2025-04-28 | 2027-05-31 | Silent on statutory basis |
| `S000055429` | HOWARD CAPITAL (HCM) | HCM Income Plus Fund -> HCM Multi-Asset Plus Fund | 749.1 | M6 (Large) | 2025-07-21 | 2026-10-28 | Multi-fund rebrand w/ unreg. |
| `S000011113` | BRIGHTHOUSE | SSGA Growth ETF Portfolio -> State Street Moderately Aggressive ETF Portfolio | 733.2 | M12 (Large) | 2025-11-06 | 2027-04-30 | Strategy/adviser change |
| `S000001575` | RUSSELL INVESTMENTS | Growth Strategy Fund -> Aggressive Strategy Fund | 606.7 | M10 (Large) | 2025-03-01 | 2027-02-28 | Fund cites 35d-1 (silent) |
| `S000055522` | RUSSELL INVESTMENTS | Multi-Asset Growth Strategy Fund -> Multi-Asset Strategy Fund | 575.8 | M10 (Large) | 2025-03-01 | 2027-02-28 | Fund cites 35d-1 (silent) |
| `S000003579` | HARTFORD | THE HARTFORD GROWTH ALLOCATION FUND -> Hartford Moderately Aggressive Allocation Fund | 519.0 | M10 (Large) | 2025-05-01 | 2027-02-28 | Silent on statutory basis |
| `S000008049` | SUNAMERICA / COREBRIDGE | SA Allocation Moderate Growth Portfolio -> SA Allocation Moderately Aggressive Portfolio | 465.2 | M3 (Large) | 2025-04-28 | 2026-07-29 | Silent on statutory basis |
| `S000008048` | SUNAMERICA / COREBRIDGE | SA Allocation Growth Portfolio -> SA Allocation Aggressive Portfolio | 457.2 | M3 (Large) | 2025-04-28 | 2026-07-29 | Silent on statutory basis |
| `S000000701` | THRIVENT | THRIVENT BALANCED INCOME PLUS FUND -> THRIVENT DYNAMIC ALLOCATION FUND | 418.5 | M10 (Large) | 2025-02-28 | 2027-02-28 | Multi-fund rebrand w/ unreg. |
| `S000001432` | THRIVENT | THRIVENT BALANCED INCOME PLUS PORTFOLIO -> THRIVENT DYNAMIC ALLOCATION PORTFOLIO | 393.1 | M12 (Large) | 2025-04-30 | 2027-04-30 | Multi-fund rebrand w/ unreg. |
| `S000031505` | VALMARK / TOPS | TOPS Growth ETF Portfolio -> TOPS Moderately Aggressive  ETF Portfolio | 332.4 | M12 (Large) | 2026-05-01 | 2027-04-30 | Silent on statutory basis |
| `S000001580` | RUSSELL INVESTMENTS | Equity Growth Strategy Fund -> Equity Aggressive Strategy Fund | 313.4 | M10 (Large) | 2025-03-01 | 2027-02-28 | Silent on statutory basis |
| `S000031506` | VALMARK / TOPS | TOPS Aggressive Growth ETF Portfolio -> TOPS Aggressive ETF Portfolio | 308.4 | M12 (Large) | 2026-05-01 | 2027-04-30 | Silent on statutory basis |
| `S000017667` | FIDELITY | VIP Asset Manager Growth Portfolio -> VIP Asset Manager 70% Portfolio | 277.6 | M12 (Large) | 2025-04-30 | 2027-04-30 | Multi-fund rebrand w/ unreg. |
| `S000080071` | ARISTOTLE / PACIFIC | Aristotle Portfolio Optimization Aggressive Growth Fund -> Aristotle Multi-Asset Capital Opportunities Fund | 272.2 | M3 (Large) | 2026-07-29 | 2026-07-29 | Multi-fund rebrand w/ unreg. |
| `S000045294` | GLOBAL ATLANTIC | Global Atlantic Growth Managed Risk Portfolio -> Global Atlantic Moderately Aggressive Managed Risk Portfolio | 254.8 | M12 (Large) | 2025-05-01 | 2027-04-30 | Unchanged policy confirmed |
| `S000031504` | VALMARK / TOPS | TOPS Moderate Growth ETF Portfolio -> TOPS Moderate ETF Portfolio | 250.2 | M12 (Large) | 2026-05-01 | 2027-04-30 | Silent on statutory basis |
| `S000004884` | FIDELITY | Fidelity Advisor Freedom Income Fund -> Fidelity Advisor Freedom Retirement Fund | 223.8 | M3 (Large) | 2025-09-09 | 2026-07-29 | Silent on statutory basis |
| `S000008054` | SUNAMERICA / COREBRIDGE | SA Putnam Asset Allocation Diversified Growth Portfolio -> SA Franklin Allocation Moderately Aggressive Portfolio | 198.6 | M3 (Large) | 2025-04-28 | 2026-07-29 | Strategy/adviser change |
| `S000062977` | FIDELITY | Fidelity Freedom Blend Income Fund -> Fidelity Freedom Blend Retirement Fund | 187.4 | M3 (Large) | 2025-09-09 | 2026-07-29 | Silent on statutory basis |
| `S000017039` | RUSSELL INVESTMENTS | Growth Strategy Fund -> Aggressive Strategy Fund | 173.8 | M12 (Large) | 2025-05-01 | 2027-04-30 | Silent on statutory basis |
| `S000031509` | VALMARK / TOPS | TOPS Managed Risk Growth ETF Portfolio -> TOPS Managed Risk Moderately Aggressive ETF Portfolio | 161.2 | M12 (Large) | 2026-05-01 | 2027-04-30 | Silent on statutory basis |
| `S000081700` | HARTFORD | Hartford Schroders Diversified Growth Fund -> Hartford Schroders Diversified Opportunities Fund | 126.5 | M10 (Large) | 2025-05-01 | 2027-02-28 | Silent on statutory basis |
| `S000017650` | FIDELITY | VIP Freedom Income Portfolio -> VIP Freedom Retirement Portfolio | 113.2 | M12 (Large) | 2026-04-20 | 2027-04-30 | Silent on statutory basis |
| `S000031508` | VALMARK / TOPS | TOPS Managed Risk Moderate Growth ETF Portfolio -> TOPS Managed Risk Moderate ETF Portfolio | 102.4 | M12 (Large) | 2026-05-01 | 2027-04-30 | Silent on statutory basis |
| `S000045293` | GLOBAL ATLANTIC | Global Atlantic Moderate Growth Managed Risk Portfolio -> Global Atlantic Moderate Managed Risk Portfolio | 84.8 | M12 (Large) | 2025-05-01 | 2027-04-30 | Unchanged policy confirmed |
| `S000017665` | FIDELITY | VIP Investor Freedom Income Portfolio -> VIP Investor Freedom Retirement Portfolio | 74.5 | M12 (Large) | 2026-04-30 | 2027-04-30 | Silent on statutory basis |
| `S000059058` | DONOGHUE FORLINES | Donoghue Forlines Risk Managed Income Fund -> DF Tactical Yield Fund | 53.2 | M6 (Small (<$1B)) | 2025-10-31 | 2027-10-28 | Multi-fund rebrand w/ unreg. |
| `S000017040` | RUSSELL INVESTMENTS | Equity Growth Strategy Fund -> Equity Aggressive Strategy Fund | 48.3 | M12 (Large) | 2025-05-01 | 2027-04-30 | Silent on statutory basis |
| `S000068731` | BLACKROCK / ISHARES | iShares ESG Aware Growth Allocation ETF -> iShares ESG Aware 60/40 Balanced Allocation ETF | 22.4 | M7 (Large) | 2025-02-19 | 2026-11-28 | Paired benchmark rename |
| `S000066527` | GLOBAL X | Global X Thematic Growth ETF -> Global X Dorsey Wright Thematic ETF | 10.6 | M11 (Large) | 2026-03-05 | 2027-03-30 | Silent on statutory basis |
| `S000056412` | FIDELITY | Fidelity Flex Freedom Blend Income Fund -> Fidelity Flex Freedom Blend Retirement Fund | 2.9 | M3 (Large) | 2025-09-09 | 2026-07-29 | Silent on statutory basis |
| `S000080299` | FIDELITY | Fidelity Sustainable Target Date Income Fund -> Fidelity Sustainable Target Date Retirement Fund | 1.3 | M3 (Large) | 2025-09-09 | 2026-07-29 | Silent on statutory basis |

---

## Appendix C. Repaired Look-Through Partial-Identification Regimes and High-Dimensional Fixed Effects

### C.1. Repaired Historical Underlying Holdings Verification (`2023Q2`)

Streaming the 109 amended `REP_YQ = 2023Q2` filings filed in `2023Q4–2024Q2` resolved the four top-100 default-equity misclassifications identified in peer review directly from same-period historical N-PORT direct holdings: *Capital Income Builder* (`S000009000`: `74.9%` Eq / `20.4%` Bond / `8.0%` Cash), *AFIS Capital Income Builder* (`S000045163`: `75.4%` / `20.2%` / `8.7%`), and *Income Fund of America* (`S000008814`: `68.2%` / `24.3%` / `8.9%`). Table C1 reports every partial-identification regime across both paired universes (`2,502` GVI and `1,550` GV-without-Income), and Table C2 reports high-dimensional `SERIES_ID + REP_YQ` and identifying-only `COMPLEX_ID × REP_YQ` fixed-effects robustness.

**Table C1. Complete Partial-Identification Sensitivity Regimes Across Paired GVI (`N = 2,502`) and GV-Screen (`N = 1,550`) Universes**

| Universe | Metric | Identification Regime | Drop / Keep | Diff, pp [95% CR1 CI] | $p_{\text{WCB}}$ |
| --- | --- | --- | ---: | ---: | ---: |
| GVI (<80%) | Largest-class drift | Repaired neutral point | 39/350 | -7.19 [-10.77, -3.60] | 0.001 |
| GVI (<80%) | Largest-class drift | 50/50 unmapped split | 39/340 | -7.35 [-10.76, -3.95] | 0.001 |
| GVI (<80%) | Largest-class drift | Delete all boundary crossers | 39/329 | -7.54 [-11.26, -3.81] | 0.001 |
| GVI (<80%) | Largest-class drift | Sharp PI lower bound | 39/347 | -11.33 [-15.36, -7.30] | 0.001 |
| GVI (<80%) | Largest-class drift | Sharp PI upper bound | 39/346 | -3.24 [-6.62, +0.13] | 0.073 |
| GVI (<80%) | Signed equity drift | Repaired neutral point | 39/350 | -1.49 [-6.00, +3.02] | 0.544 |
| GVI (<80%) | Signed equity drift | 50/50 unmapped split | 39/340 | -1.04 [-5.24, +3.15] | 0.682 |
| GVI (<80%) | Signed equity drift | Delete all boundary crossers | 39/329 | -1.21 [-5.79, +3.37] | 0.671 |
| GVI (<80%) | Signed equity drift | Sharp PI lower bound | 39/348 | -5.55 [-10.63, -0.47] | 0.061 |
| GVI (<80%) | Signed equity drift | Sharp PI upper bound | 39/343 | +2.93 [-0.99, +6.84] | 0.205 |
| GV Screen (<80%) | Largest-class drift | Repaired neutral point | 22/143 | -5.66 [-10.95, -0.37] | 0.039 |
| GV Screen (<80%) | Largest-class drift | 50/50 unmapped split | 22/138 | -5.48 [-10.67, -0.30] | 0.032 |
| GV Screen (<80%) | Largest-class drift | Delete all boundary crossers | 22/132 | -5.90 [-11.51, -0.30] | 0.044 |
| GV Screen (<80%) | Largest-class drift | Sharp PI lower bound | 22/141 | -9.42 [-15.22, -3.61] | 0.010 |
| GV Screen (<80%) | Largest-class drift | Sharp PI upper bound | 22/139 | -1.40 [-6.70, +3.91] | 0.640 |
| GV Screen (<80%) | Signed equity drift | Repaired neutral point | 22/143 | -6.11 [-11.45, -0.77] | 0.031 |
| GV Screen (<80%) | Signed equity drift | 50/50 unmapped split | 22/138 | -5.84 [-11.12, -0.56] | 0.028 |
| GV Screen (<80%) | Signed equity drift | Delete all boundary crossers | 22/132 | -6.23 [-11.90, -0.56] | 0.031 |
| GV Screen (<80%) | Signed equity drift | Sharp PI lower bound | 22/141 | -9.85 [-15.77, -3.94] | 0.011 |
| GV Screen (<80%) | Signed equity drift | Sharp PI upper bound | 22/139 | -1.75 [-7.20, +3.70] | 0.559 |

**Table C2. High-Dimensional Fixed-Effects Robustness (`SERIES_ID + REP_YQ` FE and Identifying-Only `COMPLEX_ID × REP_YQ` FE)**

| Specification | Fund-Qtrs ($N$) | Clusters ($G$) | Absorbed FE | 2025–26 Δ, pp (SE) | $p_{\text{WCB}}$ |
| --- | ---: | ---: | ---: | ---: | ---: |
| GV All: Series + Quarter FE | 48,160 | 391 | 2,442 | +3.05 (SE 1.03) | 0.001 |
| GV All: Complex × Quarter FE (identifying) | 27,744 | 65 | 1,348 | +2.54 (SE 0.87) | 0.002 |
| GV Screen (excl. Inc.): Series + Quarter FE | 46,165 | 377 | 2,338 | +3.21 (SE 1.11) | 0.001 |
| GV Screen (excl. Inc.): Complex × Quarter FE | 26,462 | 63 | 1,338 | +2.50 (SE 0.93) | 0.003 |
| GVI All: Series + Quarter FE | 76,293 | 524 | 4,086 | +2.03 (SE 0.66) | 0.001 |
| GVI All: Complex × Quarter FE (identifying) | 50,660 | 105 | 1,956 | +1.75 (SE 0.59) | 0.003 |
| GVI Non-Numeric Exit: Series + Quarter FE | 76,293 | 524 | 4,086 | +1.88 (SE 0.59) | 0.001 |
| GVI Non-Numeric Exit: Complex × Quarter FE | 50,660 | 105 | 1,956 | +1.52 (SE 0.52) | 0.002 |
| GVI + <80% Holdings: Series + Quarter FE | 69,549 | 411 | 3,029 | +1.50 (SE 0.57) | 0.005 |
| GVI + <80% Holdings: Complex × Quarter FE | 50,935 | 121 | 2,748 | +1.36 (SE 0.58) | 0.005 |
| GV Screen + <80% Holdings: Series + Quarter FE | 44,916 | 312 | 1,943 | +2.12 (SE 0.83) | 0.008 |
| GV Screen + <80% Holdings: Complex × Quarter FE | 24,896 | 60 | 1,439 | +1.93 (SE 0.81) | 0.006 |
