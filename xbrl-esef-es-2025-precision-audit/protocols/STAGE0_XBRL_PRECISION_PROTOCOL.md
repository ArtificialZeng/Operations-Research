# Stage-0 Locked Feasibility Protocol — XBRL Financial Disclosure Precision & Threshold Identifiability

**Date Locked:** 2026-11-24 (BEFORE downloading or inspecting ANY of the 20 selected 2025 filings)  
**Scope:** Data-feasibility audit ONLY — **ZERO LLM calls, ZERO credentials/contact disclosure, ZERO PDF/media/submission**.  
**Prior Art (No Priority Claims):** FinQA point-estimate financial QA labels (Chen et al., EMNLP 2021), *Confidently Wrong: Detecting Hallucinations in Financial Question Answering from LLM Internal States* (Wang, `arXiv:2607.11414`), and official XBRL Calculations 1.1 fact-interval semantics (XBRL International REC).

---

## 1. Public Source, Snapshot & Outcome-Independent Cohort (`N = 20`)

- **API documentation checked:** `https://filings.xbrl.org/docs/api` (snapshotted locally).
- **Static filing index snapshot:** `https://filings.xbrl.org/indexes/filings-2025.json` (`3,851,051 B`, `Last-Modified: Thu, 19 Nov 2026 19:22:24 GMT`, `SHA-256: f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f`, `2,825` total filings, `122` ES rows).
- **Schema example ONLY (outside frozen 2025 sample):** `9598000ANNAL42UJ7X28-2026-09-30-1-es.xhtml` verified 4/4 exact value + `decimals` parity against official Arelle-parsed XBRL-JSON (`STAGE0_XBRL_FIXTURE_RECEIPT.json`, `057ac1b7...`).
- **Outcome-independent cohort selection ([`SPAIN_ESEF_2025_COHORT_20_RECEIPT.json`](../receipts/SPAIN_ESEF_2025_COHORT_20_RECEIPT.json), `d8d2829c...`):**
  - Filter strictly to `country == "ES"`, `fxo_id.endswith("-ESEF-ES-0")` (version-0 original ESEF filing), non-null `report_url`, deduplicated to **one original filing per distinct LEI** (`121` eligible Spanish ESEF 2025 LEIs).
  - Sort deterministically by `sha256("xbrl_precision_esef_es_2025_v1:" + lei)` and take the first **`N = 20`** independent LEIs.
- **Polite anonymous access:** Sequential single-threaded HTTP GET with `>= 1.5 s` delay, generic non-identifying User-Agent, immediate stop on HTTP `403`/`429`/`503` or challenge block.

---

## 2. Prespecified Extraction, Provenance & Conflict Rules

- **Primary source:** Each filing's `.xhtml` Inline XBRL (`ix:nonFraction`), parsed strictly with `lxml` (`recover=False`).
- **Preserved provenance per fact:** `name_raw`, `namespace`, `local_name`, `contextRef`, `period_start`, `period_end`, `duration_days`, `dimensions`, `entity_identifier`, `unitRef`, `currency`, `raw_text` (excluding `<ix:exclude>`), `format` (iXBRL `ixt` transform), `scale`, `sign`, `decimals`, exact transformed `Fraction` value.
- **Exact transform & sign discipline:** Exact `Decimal` -> `Fraction` via official `ixt` transform + explicit `sign="-"` + `10^scale`. **Zero sign inference from display scaling or parentheses**; unsupported transforms or missing `decimals` fail explicitly.
- **Consolidated consecutive-FY matching:** Undimensioned (`dimensions == []`) monetary facts (`iso4217:*`) for two consecutive full FYs (`350 <= duration_days <= 380`, `FY_t` ending in `2025`, `FY_{t-1}` ending exactly `1` day before `FY_t` start), same concept and same currency.
- **Zero silent duplicate conflicts:** Identical `(value, decimals)` duplicates are deduplicated with full provenance; same `decimals` with differing values or disjoint precision intervals under either rounding rule trigger explicit **exclusion** (`duplicate_conflict_*`); compatible mixed-precision duplicates (nested/overlapping intervals under both rules) select the strictly finest disclosed `decimals` while retaining all occurrences.

---

## 3. Prespecified Analytic Thresholds & XBRL Calculations 1.1 Interval Semantics

For each fact with exact transformed value $v \in \mathbb{Q}$ and `decimals` $= d$ (quantum $q = 10^{-d}$; point $[v, v]$ if $d = \text{INF}$), evaluated **SEPARATELY** under both official XBRL Calculations 1.1 rules:
- **`round_to_nearest`:** closed bound $[v - q/2,\; v + q/2]$; strict interior witnesses satisfy $|x - v| < q/2$ (valid under ALL tie-breaking conventions).
- **`truncation` (towards zero):** $[v, v + q)$ for $v > 0$, $(v - q, v]$ for $v < 0$, $(-q, q)$ for $v = 0$; exact forward verifier `Fraction(int(x / q)) * q == v`.
- **Conservative convention label:** Recorded separately when convention is unstated; **NEVER conflates cross-rule disagreement, exact displayed ties, or endpoint touches with same-rule strict non-tie flips**.

**Tests (strictly scoped to what quoted operands support — never claiming facts omitted from the report):**
1. **Primary — `1.00%` YoY Consolidated IFRS Revenue Growth (`ifrs-full:Revenue`):** Positive prior denominator ($B > 0$ across interval), exact test $L_{1\%}(A, B) = 100 A - 101 B > 0$.
2. **Secondary 1 — `0.00%` YoY Consolidated IFRS Revenue Growth (`ifrs-full:Revenue`):** Positive prior denominator, exact test $L_{0\%}(A, B) = A - B > 0$.
3. **Secondary 2 (Prespecified True Accounting Comparison) — Change in Gross Margin (`GM_t > GM_{t-1}`):** Strictly on filings having BOTH consistent `ifrs-full:GrossProfit` AND `ifrs-full:Revenue` for the exact same consecutive full FYs and currency ($R_t, R_{t-1} > 0$), exact test $G_t R_{t-1} - G_{t-1} R_t > 0$.

**Exact 5-way verdict per rule:** `exact_displayed_tie`, `strict_non_tie_flip` (requires programmatically verified exact `Fraction` witnesses strictly on BOTH sides of the SAME threshold under the SAME rule), `endpoint_touch_only`, `uniquely_identified_above`, `uniquely_identified_below`.

**Feasibility Stop/Go Criterion:** Proceed toward model research ONLY if this bounded audit uncovers several genuine non-tie strict flip cases across independent original reports (alongside a credible larger cohort in the `121`-LEI Spain / `2,825`-filing European index); otherwise **freeze this direction early**.

---

## 4. Pre-Launch Locked SHA-256 Manifest

| File | SHA-256 |
|---|---|
| `filings-2025.json` | `f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f` |
| `xbrl_interval_core.py` | `0d8235401b06ac3801c2a8700a51327ec36be575b0988e2d5f2116a963b3d024` |
| `verify_xbrl_interval_fixtures.py` | `928430a533ed4a12f6ea8764a4a399f3dd6c69557635e0a5a60aa4554c4421a6` |
| `STAGE0_XBRL_FIXTURE_RECEIPT.json` | `057ac1b77c2972f15316f5f82c7648e3c0679a98ae5827af9887cb856ae49999` |
| `select_esef_es_2025_cohort.py` | `1908b82f121f26318324ac6f27a4406e4127cc71d287ba571d3c971ccfed9627` |
| `SPAIN_ESEF_2025_COHORT_20_RECEIPT.json` | `d8d2829c10a2fa356bea238441e8b2aa368c8bc5af6046dd03ba443c983775e0` |
| `run_spain_esef_2025_audit.py` | `e7b693a4ff8ab176d580ae88080d73cd962660375334fd9ef8a2a05f6f58de42` |
