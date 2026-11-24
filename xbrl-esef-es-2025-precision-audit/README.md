# Frozen Feasibility Archive: Spain ESEF 2025 XBRL Disclosure Precision & Threshold Identifiability

**Status:** **FROZEN EARLY — STAGE-0 FEASIBILITY CRITERION FAILED (2026-11-24)**  
**Scope:** Data-feasibility audit ONLY — **zero LLM calls, zero PDFs/media, zero additional firms/models/endpoints**.  
**Official Public Data Source:** XBRL International public filing index (`https://filings.xbrl.org/docs/api`, static snapshot `https://filings.xbrl.org/indexes/filings-2025.json`, `3,851,051 B`, `Last-Modified: Thu, 19 Nov 2026 19:22:24 GMT`, `SHA-256: f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f`).

---

## 1. Executive Result & Early-Freeze Verdict

From `121` distinct Spanish ESEF 2025 original version-0 LEIs in `filings-2025.json`, `N = 20` independent public filings were selected in a locked outcome-independent deterministic SHA-256 order (`receipts/SPAIN_ESEF_2025_COHORT_20_RECEIPT.json`) prior to downloading any 2025 filing. All `20/20` filings were retrieved (`HTTP 200`, zero parse errors, zero duplicate conflicts) and evaluated using exact `Decimal`/`Fraction` arithmetic under **official XBRL Calculations 1.1** fact-interval bounds (`round_to_nearest` and `truncation` evaluated separately):

| Prespecified Test | Eligible Denominator | Strict Non-Tie Flips (`round_to_nearest`) | Strict Non-Tie Flips (`truncation`) | Exact Displayed Ties | Endpoint Touches | Uniquely Identified (`Above` / `Below`) |
|---|---:|---:|---:|---:|---:|---:|
| **Primary: `1.00%` YoY Consolidated IFRS Revenue Growth (`100*A - 101*B > 0`)** | **`12 / 20`** | **`0`** | **`0`** | `0` | `0` | `12 / 12` (`5` / `7`) |
| Secondary 1: `0.00%` YoY Consolidated IFRS Revenue Growth (`A - B > 0`) | `12 / 20` | `0` | `0` | `0` | `0` | `12 / 12` (`6` / `6`) |
| Secondary 2: Change in Gross Margin (`GM_t > GM_{t-1}`) | `2 / 20` *(very little evidence)* | `0` | `0` | `0` | `0` | `2 / 2` (`0` / `2`) |

- **Precision & exclusion accounting:** All `12/12` eligible Revenue filers disclose consolidated `ifrs-full:Revenue` at `decimals = (-3, -3)` (thousands of EUR, `5–7` significant digits; exact full growth-interval widths `0.000041 pp` to `0.004654 pp`). The `8/20` Revenue exclusions all lacked undimensioned full-FY `ifrs-full:Revenue` facts (`5` financials/insurers under IFRS 17/IFRS 9; `3` non-financials using narrower/alternative IFRS revenue concepts, all at `decimals = -3`). Only `2/20` filings reported `ifrs-full:GrossProfit` alongside `ifrs-full:Revenue` (`0/2` flips; very little evidence on Gross Margin).
- **Strict scoping (no population-absence claim):** Results are scoped strictly to the selected quoted operands (`ifrs-full:Revenue`, and `ifrs-full:GrossProfit` on `2/20`) within this small, conditional 20-LEI Spain ESEF 2025 sample — **not** to full filings, omitted disclosures, coarser rounding scales, or the broader filing population. Because the locked Stage-0 feasibility criterion failed, this direction is frozen early.

---

## 2. Execution Interruption & Runner Hash Erratum (Transparent Record)

- **Locked pre-launch protocol** (`protocols/STAGE0_XBRL_PRECISION_PROTOCOL.md`, local locked SHA-256 `63e909a2d24d5e48555cb4b15d81c835211e5b7595c822bf9d0db4d3f3b9e49c`) was **not** rewritten.
- **First launch (`PID = 40104`):** Executed prelaunch `run_spain_esef_2025_audit.py` (`e7b693a4ff8ab176d580ae88080d73cd962660375334fd9ef8a2a05f6f58de42`), cleanly processed filings `[1..16]`, and interrupted on `[17/20]` (`MINERALES Y PRODUCTOS DERIVADOS`) with `http.client.InvalidURL` due to unencoded literal spaces in its `report_url` path segment (`'2026-04-24 10-46-29 - Merged'`).
- **Resumed launch (`PID = 29936`):** Executed patched `run_spain_esef_2025_audit.py` (`44de79af5d3dc2f6b53138f0cc9d99d515dc56c68d65ad5409522432d6604bca`, wall `54.8 s`), completing `20/20`. **Affected code scope was strictly URL percent-encoding only** (`import urllib.parse` + `urllib.parse.quote` inside `polite_download_xhtml`); `xbrl_interval_core.py` (`0d823540...`), cohort receipt (`d8d2829c...`), fixture receipt (`057ac1b7...`), and protocol (`63e909a2...`) were untouched. Full details: [`PROVENANCE_AND_ERRATA.md`](./PROVENANCE_AND_ERRATA.md).

---

## 3. Prior Art & Comparators (No Priority Claims)

- **Official Filing Source & Calculations Standard:** XBRL International (`https://filings.xbrl.org/docs/api`, `https://filings.xbrl.org/indexes/filings-2025.json`) and **XBRL Calculations 1.1 REC** fact-interval semantics.
- **Nearest Direct Comparator:** **XBRL US Data Quality Committee rule `DQC_0227`** (`https://xbrl.us/data-rule/dqc_0227/`), which validates ratios using interval consistency.
- **Related Literature:** **Cedergren & Li** (`https://link.springer.com/article/10.1007/s11142-023-09780-x`, round-number effects in financial reporting — distinct question), **FinQA** (Chen et al., EMNLP 2021), and **Wang (`arXiv:2607.11414`, *Confidently Wrong*)**.

---

## 4. Archive Map & Excluded Large Raw Mirrors

- **Provenance & erratum:** [`PROVENANCE_AND_ERRATA.md`](./PROVENANCE_AND_ERRATA.md)
- **Locked pre-launch protocol:** [`protocols/STAGE0_XBRL_PRECISION_PROTOCOL.md`](./protocols/STAGE0_XBRL_PRECISION_PROTOCOL.md)
- **Feasibility report:** [`reports/STAGE0_XBRL_FEASIBILITY_RESULT.md`](./reports/STAGE0_XBRL_FEASIBILITY_RESULT.md)
- **Derived ledgers (byte-identical):** [`outputs/spain_esef_2025_per_filing.jsonl`](./outputs/spain_esef_2025_per_filing.jsonl) (`8d659e93...`, includes exact public URLs and SHA-256s of all 20 downloaded `.xhtml` filings), [`outputs/spain_esef_2025_summary.json`](./outputs/spain_esef_2025_summary.json) (`ed644fd17fe6ee58841ad7b3e4f37e5082089f368e374a22c8dbd7d6ea01c6ce`)
- **Pre-launch receipts (byte-identical):** [`receipts/STAGE0_XBRL_FIXTURE_RECEIPT.json`](./receipts/STAGE0_XBRL_FIXTURE_RECEIPT.json), [`receipts/SPAIN_ESEF_2025_COHORT_20_RECEIPT.json`](./receipts/SPAIN_ESEF_2025_COHORT_20_RECEIPT.json)
- **Runnable code:** [`code/`](./code/), [`requirements.txt`](./requirements.txt)
- **Complete ordered SHA-256 manifest:** [`MANIFEST.json`](./MANIFEST.json)

*Excluded from archive to keep it compact:* the `3.85 MB` raw `filings-2025.json` index mirror, the `20` raw `.xhtml` filings, the `7.91 MB` external 2026 schema-example `.xhtml`/`.json`, HTML doc mirror, `.venv/`, caches, private local paths, and author contacts. Every excluded public filing's exact URL and SHA-256 is preserved in [`outputs/spain_esef_2025_per_filing.jsonl`](./outputs/spain_esef_2025_per_filing.jsonl) and [`MANIFEST.json`](./MANIFEST.json).
