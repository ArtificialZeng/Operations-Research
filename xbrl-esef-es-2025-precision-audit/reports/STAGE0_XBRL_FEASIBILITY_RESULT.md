# Stage-0 Feasibility Audit Result — Spain ESEF 2025 XBRL Precision & Threshold Identifiability

**Date Sealed:** 2026-11-24  
**Verdict:** **FROZEN EARLY — FEASIBILITY CRITERION FAILED** (`0/12` strict non-tie flips on `1.00%` YoY revenue growth, `0/12` on `0.00%`, `0/2` on gross margin; zero LLM calls, zero PDFs/media).  
**Locked Protocol (Unmodified):** [`STAGE0_XBRL_PRECISION_PROTOCOL.md`](../protocols/STAGE0_XBRL_PRECISION_PROTOCOL.md) (`SHA-256: 63e909a2d24d5e48555cb4b15d81c835211e5b7595c822bf9d0db4d3f3b9e49c`)  
**Fixture Gate:** [`STAGE0_XBRL_FIXTURE_RECEIPT.json`](../receipts/STAGE0_XBRL_FIXTURE_RECEIPT.json) (`057ac1b7...`, all synthetic XBRL Calculations 1.1 fixtures & 4/4 external 2026 schema-example XHTML-vs-OIM-JSON parity passed)  
**Locked Cohort (`N = 20 / 121`):** [`SPAIN_ESEF_2025_COHORT_20_RECEIPT.json`](../receipts/SPAIN_ESEF_2025_COHORT_20_RECEIPT.json) (`d8d2829c...`, derived deterministically from `filings-2025.json` *(omitted raw mirror; official URL `https://filings.xbrl.org/indexes/filings-2025.json`, snapshot SHA-256 `f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f`)* `f74e1da4...`)  
**Native Execution & Interruption Record:**
- First launch `PID = 40104` ran the prelaunch runner `run_spain_esef_2025_audit.py` (`e7b693a4ff8ab176d580ae88080d73cd962660375334fd9ef8a2a05f6f58de42`), cleanly downloaded and parsed `[1..16]`, and interrupted on `[17/20]` (`MINERALES Y PRODUCTOS DERIVADOS`) with `http.client.InvalidURL` due to unencoded spaces in its `report_url` folder (`'2026-04-24 10-46-29 - Merged'`).
- Resumed launch `PID = 29936` ran the URL-encoding-only patched runner (`44de79af5d3dc2f6b53138f0cc9d99d515dc56c68d65ad5409522432d6604bca`; exact patch scope: `import urllib.parse` + `urllib.parse.quote` on URL path inside `polite_download_xhtml`, zero changes to locked protocol, cohort, iXBRL parser, or Calculations 1.1 interval engine; see [`STAGE0_RUNNER_PATCH_AND_PROVENANCE_NOTE.md`](../PROVENANCE_AND_ERRATA.md)) and completed `20/20` in `54.8 s` (`HTTP 200`, `0` rate-limit/CAPTCHA blocks, `0` XML/iXBRL parse errors, `0` duplicate conflicts).
- Sealed outputs: [`spain_esef_2025_per_filing.jsonl`](../outputs/spain_esef_2025_per_filing.jsonl) (`8d659e930335a288a7ac468afd052c4c150bd69bc68a6a745dbb24be383b7f37`), [`spain_esef_2025_summary.json`](../outputs/spain_esef_2025_summary.json) (`ed644fd17fe6ee58841ad7b3e4f37e5082089f368e374a22c8dbd7d6ea01c6ce`).

---

## 1. Executive Feasibility Verdict: **FROZEN EARLY**

Across **`20`** independently selected original Spanish ESEF 2025 reports (`12` eligible for consolidated `ifrs-full:Revenue`, `2` eligible for `ifrs-full:GrossProfit` + `ifrs-full:Revenue`), exact `Fraction` interval evaluation under **official XBRL Calculations 1.1** (`round_to_nearest` and `truncation` evaluated separately, plus conservative convention-uncertainty labels) yielded:

| Prespecified Test | Eligible Denominator | Strict Non-Tie Flips (`round_to_nearest`) | Strict Non-Tie Flips (`truncation`) | Exact Displayed Ties | Endpoint Touches | Uniquely Identified (`Above` / `Below`) |
|---|---:|---:|---:|---:|---:|---:|
| **Primary: `1.00%` YoY Revenue Growth (`100*A - 101*B > 0`)** | **`12 / 20`** | **`0`** | **`0`** | `0` | `0` | `12 / 12` (`5` above, `7` below) |
| Secondary 1: `0.00%` YoY Revenue Growth (`A - B > 0`) | `12 / 20` | `0` | `0` | `0` | `0` | `12 / 12` (`6` above, `6` below) |
| Secondary 2: Change in Gross Margin (`GM_t > GM_{t-1}`) | `2 / 20` *(very little evidence)* | `0` | `0` | `0` | `0` | `2 / 2` (`0` above, `2` below) |

**Sample-Scoped Explanation & Strict Boundaries:**
- All `12/12` eligible Spanish ESEF 2025 Revenue filers in this conditional sample disclose consolidated `ifrs-full:Revenue` at `decimals = (-3, -3)` (nearest thousand EUR, `scale = 3`, quantum $q = 1{,}000\text{ EUR}$) across revenues of `33.3M–4,930.3M EUR` (`5–7` significant digits), giving exact YoY growth interval widths (`max - min`) of **`0.000041 pp` to `0.004654 pp`** (median `~0.0002 pp`).
- On Gross Margin, only **`2/20`** filings were eligible (`0/2` flips), providing very little evidence on that endpoint.
- **No Population-Absence Claim:** These findings are scoped strictly to the selected quoted operands (`ifrs-full:Revenue`, and `ifrs-full:GrossProfit` on `2/20`) and this small, conditional 20-LEI Spain ESEF 2025 sample — **not** to full filings, omitted disclosures, other rounding scales, or the broader filing population. Because the locked feasibility criterion failed, this direction is **frozen early** with no further research, firms, models, or endpoints.
- **Prior Art & Comparators (No Priority Claims):** Official XBRL International public filing index (`https://filings.xbrl.org/docs/api`, `https://filings.xbrl.org/indexes/filings-2025.json`) and XBRL Calculations 1.1 REC; nearest direct prior comparator **XBRL US `DQC_0227`** (`https://xbrl.us/data-rule/dqc_0227/`, validating ratios using precision-interval consistency); **Cedergren & Li** (`https://link.springer.com/article/10.1007/s11142-023-09780-x`, known round-number effects in financial reporting — distinct question); FinQA; and Wang (`arXiv:2607.11414`, *Confidently Wrong*).

---

## 2. Exact Per-Filing Ledger (`12/20` Eligible Consolidated IFRS Revenue Filings, `EUR`)

All `12` eligible filings reported consecutive full FYs (`2025-01-01..2025-12-31` vs `2024-01-01..2024-12-31`, `dims == []`, `iso4217:EUR`, `scale = 3`, `decimals = -3`, `sign = None`, `num-comma-decimal` transform, `0` duplicate conflicts).

| # | LEI | Entity | FY25 Revenue (`EUR`) | FY24 Revenue (`EUR`) | Displayed YoY Growth | Full Width (`N` / `T`, pp) | `1.00%` Verdict (`N` & `T`) |
|---:|---|---|---:|---:|---:|---:|---|
| 02 | `959800RG37G8456RGX60` | IBERPAPEL GESTION, S.A. | `216,735,000` | `238,189,000` | `-9.007132%` | `0.000801` / `0.000802` | `uniquely_identified_below` |
| 03 | `959800XKAB9VNAVN9425` | SACYR SA | `4,659,539,000` | `4,571,004,000` | `+1.936883%` | `0.000045` / `0.000044` | `uniquely_identified_above` |
| 04 | `9598005HY5DEFPU2SM35` | PROSEGUR CASH, S.A.* | `1,987,329,000` | `2,089,879,000` | `-4.906982%` | `0.000094` / `0.000094` | `uniquely_identified_below` |
| 05 | `95980020140005491929` | ATRESMEDIA CORPORACION DE MEDIOS | `893,745,000` | `918,954,000` | `-2.743227%` | `0.000214` / `0.000215` | `uniquely_identified_below` |
| 06 | `959800EXHG00L95ZAK22` | NICOLAS CORREA S.A. | `119,093,000` | `121,485,000` | `-1.968967%` | `0.001630` / `0.001630` | `uniquely_identified_below` |
| 07 | `95980020140005684765` | VISCOFAN SA | `1,251,983,000` | `1,203,994,000` | `+3.985817%` | `0.000169` / `0.000170` | `uniquely_identified_above` |
| 09 | `549300N94L4D5NDBFG97` | PROSEGUR COMPAÑIA DE SEGURIDAD* | `4,930,329,000` | `4,907,928,000` | `+0.456424%` | `0.000041` / `0.000041` | `uniquely_identified_below` |
| 11 | `95980020140005204809` | MIQUEL Y COSTAS & MIQUEL S.A. | `313,841,000` | `309,170,000` | `+1.510819%` | `0.000652` / `0.000652` | `uniquely_identified_above` |
| 13 | `959800QETXHEMRSX9V59` | COMPAÑÍA ESPAÑOLA DE VIVIENDAS | `33,321,000` | `39,580,000` | `-15.813542%` | `0.004653` / `0.004654` | `uniquely_identified_below` |
| 16 | `95980020140005319366` | DEOLEO SA | `820,946,000` | `996,649,000` | `-17.629376%` | `0.000183` / `0.000183` | `uniquely_identified_below` |
| 17 | `95980020140005436930` | MINERALES Y PRODUCTOS DERIVADOS | `460,992,000` | `447,293,000` | `+3.062645%` | `0.000454` / `0.000454` | `uniquely_identified_above` |
| 20 | `95980020140005491250` | ELECNOR SA | `4,387,250,000` | `3,810,102,000` | `+15.147835%` | `0.000057` / `0.000057` | `uniquely_identified_above` |

*\*Gross Margin eligible (`2/20`): `#04 PROSEGUR CASH` (`GM25 = 34.487%`, `GM24 = 36.187%`, `dGM = -1.7000 pp`, interval `[-1.7001, -1.6999] pp` -> `uniquely_identified_below`); `#09 PROSEGUR` (`GM25 = 23.437%`, `GM24 = 25.007%`, `dGM = -1.5697 pp`, interval `[-1.5697, -1.5697] pp` -> `uniquely_identified_below`). `#04` and `#20` had exact identical duplicates; all other `10` were unique.*

---

## 3. Exact Accounting of the `8/20` Excluded Filings (`no_undimensioned_full_fy_Revenue_facts`)

None of the `8` excluded filings contained undimensioned full-FY `ifrs-full:Revenue` facts (no post-hoc concept switching):
- **5 Financial / Insurance filers** (IFRS 17 / IFRS 9 income statements): `#01 LINEA DIRECTA ASEGURADORA` (`ifrs-full:InsuranceRevenue`, `d=-3`), `#12 OPEN BANK` (`ifrs-full:RevenueFromInterest`, `d=-3`), `#14 CAIXABANK` (`ifrs-full:RevenueFromInterest`, `d=-6`), `#15 GRUPO CATALANA OCCIDENTE` (`ifrs-full:InsuranceRevenue`, `d=-3`), `#19 MAPFRE` (`ifrs-full:InsuranceRevenueOtherAmounts`, `d=-5`).
- **3 Non-financial filers using alternative IFRS revenue sub-concepts** (all at `decimals = -3`): `#08 MELIA HOTELS` (`ifrs-full:RevenueAndOperatingIncome`), `#10 TALGO` (`ifrs-full:RevenueFromContractsWithCustomers`), `#18 MONTEBALITO` (`ifrs-full:RevenueFromSaleOfGoods`).
- **Gross Margin exclusions (`18/20`):** `8` revenue-ineligible + `10` with `no_undimensioned_full_fy_GrossProfit_facts` (nature-of-expense income statements).
