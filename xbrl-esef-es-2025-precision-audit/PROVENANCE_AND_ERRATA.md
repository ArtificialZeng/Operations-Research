# Stage-0 Runner Interruption, URL-Encoding Patch, and Provenance Note

**Date Sealed:** 2026-11-24  
**Policy:** Immutable provenance & erratum note; the locked pre-launch protocol [`STAGE0_XBRL_PRECISION_PROTOCOL.md`](./protocols/STAGE0_XBRL_PRECISION_PROTOCOL.md) (`SHA-256: 63e909a2d24d5e48555cb4b15d81c835211e5b7595c822bf9d0db4d3f3b9e49c`) is **not** modified.

---

## 1. Exact First-Run Interruption & Resumed Execution Record

1. **First Native Launch (`PID = 40104`):**
   - Executed pre-launch locked runner `run_spain_esef_2025_audit.py` (`SHA-256: e7b693a4ff8ab176d580ae88080d73cd962660375334fd9ef8a2a05f6f58de42`, as recorded in `STAGE0_XBRL_PRECISION_PROTOCOL.md`).
   - Cleanly fetched (`HTTP 200`), cached, and audited filings `[1/20]` through `[16/20]`.
   - Interrupted with `http.client.InvalidURL` on filing `[17/20]` (`LEI 95980020140005436930`, `MINERALES Y PRODUCTOS DERIVADOS`) because `report_url` in `filings-2025.json` contained literal unencoded ASCII spaces in the folder segment: `'/95980020140005436930/2025-12-31/ESEF/ES/0/2026-04-24 10-46-29 - Merged/reports/95980020140005436930-2025-12-31-1-es.xhtml'`.
2. **Scoped Transport-Only Patch & Resumed Launch (`PID = 29936`):**
   - Patched `run_spain_esef_2025_audit.py` (`SHA-256` changed from `e7b693a4ff8ab176d580ae88080d73cd962660375334fd9ef8a2a05f6f58de42` to `44de79af5d3dc2f6b53138f0cc9d99d515dc56c68d65ad5409522432d6604bca`).
   - **Exact affected code scope (URL percent-encoding ONLY):** Added `import urllib.parse` and replaced raw `HOST + report_url` inside `polite_download_xhtml` with `urllib.parse.quote(report_url, safe="/:@!$&'()*+,;=-._~%")` (and equivalent path quoting for absolute URLs).
   - **Unchanged components:** Zero modifications to `STAGE0_XBRL_PRECISION_PROTOCOL.md` (`63e909a2...`), `SPAIN_ESEF_2025_COHORT_20_RECEIPT.json` (`d8d2829c...`), `xbrl_interval_core.py` (`0d8235401b06ac3801c2a8700a51327ec36be575b0988e2d5f2116a963b3d024`), `STAGE0_XBRL_FIXTURE_RECEIPT.json` (`057ac1b7...`), or any XML/iXBRL extraction, duplicate-check, or XBRL Calculations 1.1 interval calculation logic.
   - Resumed run `PID = 29936` (wall time `54.8 s`) reused cached `[1..16]` and politely fetched `[17..20]`, producing [`spain_esef_2025_per_filing.jsonl`](./outputs/spain_esef_2025_per_filing.jsonl) (`8d659e93...`) and [`spain_esef_2025_summary.json`](./outputs/spain_esef_2025_summary.json) (`ed644fd17fe6ee58841ad7b3e4f37e5082089f368e374a22c8dbd7d6ea01c6ce`).

---

## 2. Prior Art & Strict Conditional Scope

- **Official Filing Source & Standard:** XBRL International public filing repository (`https://filings.xbrl.org/docs/api`, static snapshot `https://filings.xbrl.org/indexes/filings-2025.json`, `SHA-256: f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f`) and official **XBRL Calculations 1.1** fact-interval semantics (`round-to-nearest` and `truncation` evaluated separately).
- **Nearest Direct Prior Comparators (No Priority Claims):**
  - **XBRL US Data Quality Committee rule `DQC_0227`** (`https://xbrl.us/data-rule/dqc_0227/`): directly validates reported ratios using precision-interval consistency.
  - **Cedergren & Li** (`https://link.springer.com/article/10.1007/s11142-023-09780-x`): studies known round-number effects in financial reporting (a distinct empirical question from stated-`decimals` interval non-identifiability).
  - **FinQA** point-estimate financial QA labels (Chen et al., EMNLP 2021) and **Wang (`arXiv:2607.11414`, *Confidently Wrong*)**.
- **Strict Scope Boundary:** Findings apply **strictly to the selected quoted operands (`ifrs-full:Revenue`, and `ifrs-full:GrossProfit` where eligible on only `2/20` filings — very little evidence on Gross Margin) within this small, conditional 20-LEI Spain ESEF 2025 sample (`12` eligible Revenue)**. They do **not** evaluate full filings, omitted footnotes, or other jurisdictions/scales, and make **no claim that precision-induced threshold non-identifiability is absent in the broader population**.
