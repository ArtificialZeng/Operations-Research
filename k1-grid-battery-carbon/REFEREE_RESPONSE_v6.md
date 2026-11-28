# Referee & Editorial Compliance Response — K1 `v6` (*Nature Energy* `Analysis` Double-Anonymized Submission Package)

**Date:** `2026-11-28`  
**Target Venue & Format:** *Nature Energy* — `Analysis` (**Double-Anonymized Peer Review / DAPR** opt-in)  
**Blinded Reviewer Upload Files:**
- Main Manuscript (Blinded, 0 author/affiliation/email/metadata traces): `manuscript_k1_nature_energy_blinded.pdf`
- Supplementary Information (Blinded, 0 author/affiliation/email/metadata traces): `supplementary_k1_nature_energy_blinded.pdf`
- Editor-Only Cover Letter (Full author identity + DAPR request + disclosures): `COVER_LETTER_NATURE_ENERGY.pdf`

**Archival Named Copies (Synchronized Identical Scientific Content):**
- `manuscript_k1_nature_energy.pdf` & `supplementary_k1_nature_energy.pdf`

---

## Point-by-Point Summary of `v6` Upgrades (Addressing All 11 Checklist Items & P0/P1 Scientific Issues)

### 1. Double-Anonymized Peer Review (DAPR) Package & Cover Letter
- Removed all author name (`Zijian Zeng`), institutional affiliation (`UCSI University`, `Kuala Lumpur, 56000, MALAYSIA`), email addresses, and identifying repository usernames (`ArtificialZeng`) from BOTH `manuscript_k1_nature_energy_blinded.pdf` and `supplementary_k1_nature_energy_blinded.pdf`.
- Programmatically stripped all embedded PDF document metadata (`/Author`, `/Creator`, `/Producer`, `/Subject`, `/Keywords`, XMP packets) via `pymupdf` (`strip_pdf_metadata()`) and verified zero identity traces in BOTH extracted text and PDF metadata via automated `pytest` assertions.
- Prepared a dedicated editor-only `COVER_LETTER_NATURE_ENERGY.pdf` containing complete sole-author contact details, formal DAPR selection, CRediT author contribution statement, competing interests, funding statement, transparent Nature Portfolio AI-assisted tools disclosure, non-duplicate confirmation, and full archival repository URL.

### 2. Official *Nature Energy* Numbered Citations & Required Editorial Declarations
- Converted all in-text citations from author-year parentheses to **official *Nature* superscript numbered citations** (`1–4`, `5–9`, `10–14`, `2,5,7–9`, `15,16`, `7,8`, `17,18`, `19–22`) strictly ordered by first appearance, programmatically verified by `scripts/07_verify_citations.py` (`nature_numbered_order_ok = True`).
- Expanded the bibliography from `18` to **`22` live Crossref HTTP-200 verified references** (well within the `<= 50` guideline), adding recent empirical real-world CAISO/ERCOT storage operation (**Peplinski et al., 2026**, *J. Energy Storage* `10.1016/j.est.2026.124812`), long-duration grid storage (**Staadecker et al., 2024**, *Nat. Commun.* `10.1038/s41467-024-53274-6`), and corporate Scope 2 vs. consequential accounting critiques (**Brander et al., 2018**, *Energy Policy* `10.1016/j.enpol.2017.09.051`; **Bjørn et al., 2022**, *Nat. Clim. Change* `10.1038/s41558-022-01379-5`).
- Added complete required *Nature Energy* declarations: **Data availability** (with explicit upstream URLs and archival repository/anonymized review package), **Code availability**, **Use of AI-assisted tools** (honest Nature Portfolio policy disclosure covering Python pipeline engineering, test scaffolding, and language editing under full author supervision and independent verification), **Author contributions** (full CRediT in Named/Cover Letter, cleanly redacted in Blinded), **Competing interests**, and **Funding**.

### 3. P0 Scientific Precision Fixes & Direct Unit-Level ERCOT EPA CEMS Physical Verification
- **P0 — Out-of-Sample vs. Counterfactual Precision:** Replaced `"actual"` for the held-out `4.38 Mt` discrepancy everywhere with **`held-out model-based estimate`** and explicitly stated that high out-of-sample predictability of observed generator emissions (`R^2 = 0.938`) does not equate to causal validation of a no-storage counterfactual without nodal SCED/OPF replay.
- **P0 — ERCOT Coal-Margin Precision + Direct Unit-Level EPA CEMS Operating-Envelope Verification (`scripts/03d_ercot_unit_level_cems_mechanism.py`):**
  - Replaced `"coal enters the margin above 60% renewables"` everywhere (Abstract, Main Text, Figure 4b, Discussion) with **`"coal's estimated marginal contribution increases under high renewable penetration"`** (recognizing coal already contributes `151 kg/MWh` below `20%` renewables).
  - Direct programmatic probes to `ercot.com` 60-day SCED MIS JSON endpoints (`reportTypeId 13052/12301/13060`) returned HTTP 403 anti-bot responses (honestly disclosed in Discussion without bypassing access gates). Instead, we extracted **6,965,982 hourly unit-level EPA CEMS smokestack records across 351 active ERCOT fossil generators (`25` coal, `140` NGCC, `186` NGCT; `2024-07-01..2026-09-30`)** via Catalyst PUDL `v2026.11.0`.
  - Within exact `Season × Hour × Load-Quartile` matched cells (`61` cells, `<40%` → `>60%` renewables), direct unit-level physical telemetry verifies: online gas peakers (`NGCT`) drop from **`33.3` → `15.3` units (`t = -9.1`)** and their share of total fossil ramping `|ΔMW|` plunges from **`25.1%` → `7.3%` (`t = -10.2`)**, while committed coal units exit their baseload ceiling (`41.2%` → `9.9%` at `>=95% HSL`, `t = -15.1`), expand part-loaded flexible operation (`56.1%` → `68.3%`, `t = +5.9`; active ramping `>=5 MW/h`: `30.8%` → `36.5%`, `t = +3.2`), and increase coal's share of total fossil ramping from **`22.1%` → `30.0%` (`t = +7.0`)** (`tables/table_ercot_unit_cems_mechanism.csv` & Supplementary Table 6).
- **P1 — Policy Framework Separation:** Revised Discussion to explicitly separate three distinct mechanisms—(1) capital investment tax credits (`IRC Section 48E`), (2) corporate GHG inventory protocols (`GHG Protocol Scope 2`), and (3) consequential avoided-emissions attribution—rather than conflating them as uniform "carbon credits", and reinforced that Figure 4a scenarios represent fixed-profile BA-level upper bounds rather than nodal physical deployment limits.
