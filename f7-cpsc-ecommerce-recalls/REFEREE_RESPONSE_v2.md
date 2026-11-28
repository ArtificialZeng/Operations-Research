# Referee Response & Revision Audit Log (`v2` Major Revision — F7)

**Manuscript:** *The Asset-Light Safety Gap: Cross-Border Platform Disintermediation, Reverse-Logistics Collapse, and "Proof-of-Destruction" Recall Contracts in U.S. Consumer Markets, 2000–2026*  
**Workspace:** `D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126`  
**Revision Scope:** Code-backed surgical Major Revision (`v2`) addressing every concrete methodological, econometric, table-sync, legal-scope, and framing concern identified in external peer review.

---

## Point-by-Point Summary of Referee Findings & Code-Backed Fixes

### 1. Subsample Label Bug (`R7_high_price_ge_100`) & New Deterministic Strict Durables (`>= $100`) Subsample (`R7b_strict_durables_ge_100`)

- **Referee Critique:** `scripts/04_pillar1_contract_econometrics.py:291` labeled `R7_high_price_ge_100` as *"High-Price Durables ($\ge \$100$)"* even though the code filtered solely on `price >= 100.0`, retaining apparel/footwear, child sleepwear/apparel, textiles/bedding, personal care, and chemical/packaging recalls.
- **Code & Manuscript Fixes:**
  1. **Honest Rename of `R7`:** Renamed `R7_high_price_ge_100` across `scripts/04_pillar1_contract_econometrics.py`, `scripts/07_generate_figures_and_tables.py`, `scripts/08_compile_manuscript_pdf.py`, `tables/table3_robustness_battery_2022_2026.csv`, Figure 3A, and `manuscript_f7_boost.md` (Abstract, Section 4.2, Table 3) to **"Products Priced >= $100 (All Categories)"**, explicitly noting that it includes apparel, textiles/bedding, personal care, and chemical categories (`N = 794`, `G = 571` firm clusters; `1_Mkt_FD_China` = `+45.17 pp`, `SE = 6.72 pp`, `t = +6.72`, `p_WCB = 0.001`; within-marketplace `Δ = +40.70 pp`, `t = +5.97`, `p_WCB = 0.001`; `4_DTC_Online_Only = -6.09 pp`, `95% CI [-14.22, +2.04] pp`).
  2. **New Deterministic `R7b_strict_durables_ge_100` Subsample:** Implemented in `scripts/04_pillar1_contract_econometrics.py`, deterministically excluding non-durable `prod_cat` categories (`Adult_Apparel_Footwear` [`10`], `Child_Sleepwear_Apparel` [`53`], `Chemicals_Medicine_Packaging` [`10`]), non-durable `fine_noun` categories (`Mattress_Bedding` [`28`], `Hair_Dryer_PersonalCare` [`5`], plus overlapping apparel/chemical nouns), and residual apparel/textile/bedding/cosmetics/food/chemical product titles (`RecallID 9771` heated blankets and `RecallID 10868` women's sweaters, safeguarding furniture such as `"clothing storage units"`). Exact rule-by-rule exclusion counts (`109` excluded out of `794`, leaving **`N = 685`**, **`G = 481` firm clusters**, exact full rank `63 == 63`) are logged in `results/04_pillar1_econometrics.json` (`R7b_strict_durables_ge_100["exclusion_audit"]`).
  3. **Verified Results (Reported Side-by-Side with `R7` in Table 3, Figure 3A, and Prose):** Under the exact same ultra-saturated FE + firm CR1 + Rademacher WCB (`B = 999`) specification, **`R7b_strict_durables_ge_100`** yields:
     - `1_Mkt_FD_China`: **`+41.39 pp`** (`SE = 7.60 pp`, `95% CI [+26.45, +56.32] pp`, `t = +5.44`, `p_WCB = 0.001`)
     - Within-marketplace contrast `Δ(FD_China - Mkt_True_US)`: **`+36.57 pp`** (`SE = 7.89 pp`, `t = +4.64`, `p_WCB = 0.001`)
     - `4_DTC_Online_Only`: **`-4.41 pp`** (`SE = 4.86 pp`, `95% CI [-13.96, +5.13] pp`, `t = -0.91`, `p_WCB = 0.390`)

---

### 2. Parser Audit Honesty, Exact 4-Way Remedy Disaggregation (`118/371`), Observational Framing, and `4_DTC_Online_Only` Precision

- **Referee Critique:**
  - `scripts/02_parse_and_audit.py` initializes `gt_*` columns from frozen parser outputs before applying manual edits, so it must NOT be framed as independent blind ground-truth validation.
  - `photo_verify` is broader than `physical_mutilate` (with `118/371` cross-border `photo_verify` recalls not triggering `physical_mutilate`), requiring exact disaggregation across photo-only, marking/defacing, physical destruction, and local hazardous-waste/recycling disposal instructions.
  - `4_DTC_Online_Only` (`+3.38 pp`, `p_WCB = 0.523`) has a wide confidence interval and must be framed as an imprecisely estimated null rather than proof of exact zero; Pillar 1 regressions are conditional observational associations rather than causal estimates.
- **Code & Manuscript Fixes:**
  1. **Audit Honesty (`02_parse_and_audit.py`, `02_parser_audit_metrics.json`, Section 3.2, Table 7, Limitations):** Relabeled both the 150-recall stratified batch and the disjoint 50-recall out-of-sample batch throughout code, JSON (`audit_methodology.independent_blind_annotation = false`), manuscript, and tests as an **"author-reviewed parser consistency audit"**. Explicitly disclosed initialization from frozen `parser_lib.py` outputs prior to author edits and stated that independent double-blind human annotation of remedy classifications and seller legal entities is required prior to formal journal submission. Also synchronized two OOS-50 TP/TN cell counts in Table 7 to match `tables/table7_parser_audit_summary_150.csv` (`photo_verify`: `32` TP / `18` TN; `direct_return`: `6` TP / `44` TN).
  2. **Exact 4-Way Remedy Disaggregation (`04_pillar1_contract_econometrics.py`, `04_pillar1_econometrics.json`, Abstract, Section 4.1):** Computed directly from raw CPSC JSON remedy text across all `371` `1_Mkt_FD_China` `photo_verify` notices (`2022–2026`):
     - Triggering `physical_mutilate`: **`253 / 371` (`68.2%`)** = **`202 / 371` (`54.4%`)** `photo + physical destruction` (cutting, breaking, disassembling, submerging, destroying/disabling; `63` also require permanent marking/defacing) + **`51 / 371` (`13.8%`)** `photo + permanent marking/defacing only` (without physical destruction).
     - **NOT** triggering `physical_mutilate`: **`118 / 371` (`31.8%`)** = **`26 / 371` (`7.0%`)** `photo + local HHW/recycling disposal instructions only` + **`92 / 371` (`24.8%`)** `photo-only` (without destruction, marking, or HHW/recycling text).
     - Across all `371` notices, `51 / 371` (`13.8%`) carry explicit local HHW/recycling disposal instructions. (Full `2022–2026` classified `photo_verify = 1` universe `N = 719`: `364` physical destruction [`50.6%`], `108` marking-only [`15.0%`], `54` HHW/recycling-only [`7.5%`], `193` photo-only [`26.8%`].)
  3. **Honest Observational & Precision Framing:** Reframed Pillar 1 estimates (`+35.35 pp`, `+25.48 pp`, `-35.07 pp`) throughout Abstract, Section 4, Figure 2–3, and Limitations as **conditional observational associations** controlling for observables. Reframed `4_DTC_Online_Only` (`+3.38 pp`, `SE = 5.03 pp`, **`95% CI [-6.48, +13.24] pp`**, `t = +0.67`, `p_WCB = 0.523`) explicitly as an **imprecisely estimated null**—never claiming proof of exact zero—while documenting its sharp separation from `1_Mkt_FD_China` (`+35.35 pp`, `95% CI [+27.50, +43.20] pp`).

---

### 3. `3,947,390` Recalled Hazardous-Product Units Reframing & Concentration Audit

- **Referee Critique:** Claiming that `3.95M` hazardous-waste units were *"externalized into household municipal trash / municipal solid-waste systems"* overstates what CPSC recall notices observe: two recalls (OCOOPA `1.5M`, Anker `1.158M`) drive ~67% of volume, OCOOPA explicitly prohibits ordinary household trash/recycling bins and directs consumers to municipal HHW collection programs, and actual completion rates and waste-stream routing are unobserved.
- **Code & Manuscript Fixes:**
  1. **Logged Exact Concentration & HHW Audit (`05_pillar2_3_4_mechanisms_shocks_safety.py`, `05_pillars_2_3_4.json["pillar4"]["hazwaste_concentration_audit"]`):**
     - `1_Mkt_FD_China` hazardous-product recalls assigned to consumer self-disposal (`N = 67`, `0.0%` firm direct return): **`3,947,390` total recalled units**.
     - **OCOOPA Direct (`RecallID 10895`, `1,500,000` units, `38.00%`) + Anker PowerCore 10000 (`RecallID 10311`, `1,158,000` units, `29.34%`) = `2,658,000` units (`67.34%`)**; top four (`+ Charmast 488,000 + Baseus 132,000`) = `83.04%`.
     - Programmatically verified that OCOOPA's CPSC notice expressly prohibits placing defective lithium-ion devices in ordinary household trash, curbside recycling bins, or retail battery-recycling boxes while directing consumers to local HHW collection centers (`ocoopa_10895_prohibits_ordinary_trash_and_curbside_bins = true`), that Anker requires confirming disposal per applicable laws and regulations (`anker_10311_requires_disposal_per_applicable_laws = true`), and that `52/67` recalls (`77.6%`, `2,697,571` units or `68.34%`) carry explicit local HHW/regulatory warnings.
  2. **Exact Defensible Wording Across Abstract, Section 2, Section 6, Figure 5, Section 7, Limitations:** Replaced every *"externalized into municipal trash / municipal solid-waste"* phrasing with **`3,947,390` recalled hazardous-product units assigned to consumer self-disposal remedies (with `0.0%` firm direct-return programs)**, explicitly stating that without recall completion rates or downstream waste-stream tracking, actual improper disposal or trash leakage cannot be quantified from CPSC notices alone.

---

### 4. Programmatic Table 5 Parity Fix & *In re Amazon.com* FBA Legal-Scope Correction

- **Referee Critique:**
  - Table 5 (Page 12) had pre-slope, level-jump, and $R^2$ mismatches on the statutory-control and monthly rows relative to `tables/table5_amazon_hac_shock_and_persistence.csv` and `results/05_pillars_2_3_4.json`.
  - *In re Amazon.com* (CPSC orders and Nov 24, 2026 D. Md. ruling) legally governs **Fulfilled-by-Amazon (`FBA`)** third-party products, whereas public CPSC `Amazon-only` notices pool all Amazon-exclusive announcements; thus the post-order slope cannot be claimed as a clean causal estimate of the FBA ruling.
- **Code & Manuscript Fixes:**
  1. **100% Programmatic Table 5 Sync (`07_generate_figures_and_tables.py`):** Added `build_canonical_table5_markdown()` and `sync_table5_markdown_from_canonical_csv()`, which generate `tables/table5_canonical.md` directly from canonical `tables/table5_amazon_hac_shock_and_persistence.csv` and programmatically overwrite Table 5 inside `manuscript_f7_boost.md`. Fixed all three mismatched rows (`+ STURDY & Reese's`: pre-slope `-0.0009` [`t = -0.06`], level jump `+0.3479` [`t = +4.22`], `R² = 0.902`; `Monthly Amz/BM`: pre `t = +1.12`, level jump `+0.3754` [`t = +2.33`], `R² = 0.629`; `Monthly Amz/NonAmz`: pre-slope `-0.0066` [`t = -0.59`], level jump `-0.1583` [`t = -0.29`], `R² = 0.030`; plus `log(1 + Brick_and_Mortar)` placebo `p = 0.8449`). Also audited and synchronized all remaining tables (Table 3 subsample cluster counts and Table 4 Walmart `No Phone = 29.5%`).
  2. **FBA Public-Data Scope Audit (`05_pillar2_3_4_mechanisms_shocks_safety.py`, `05_pillars_2_3_4.json["pillar3"]["fba_scope_audit"]`):** Audited all `601` `Amazon_Only` notices (`2022–2026`; `646` in `2021–2026`) in raw CPSC JSON and verified that explicit `"Fulfilled by Amazon"` / `"FBA"` language appears in only **`1 / 601` (`0.17%`)** public notices. Explicitly documented the FBA legal scope vs. pooled public `Amazon-only` series across Abstract, Section 5.2, Figure 4, Section 7, and Limitations, framing the Newey–West HAC `log(Amz/B&M)` acceleration (`+0.1831/qtr`, `t = +8.00`) strictly as a **descriptive structural acceleration / associative time-series break**.

---

### 5. Automated Verification, Visual PDF Inspection, and Reproducibility Gates

- **Expanded `tests/test_f7_boost.py`:** Enforces `R7b_strict_durables_ge_100` full-rank & exclusion-audit receipts, 4-way remedy disaggregation & hazwaste concentration receipts, **100% cell-by-cell numeric parity** between Table 5 in `manuscript_f7_boost.md` and canonical `table5_amazon_hac_shock_and_persistence.csv` (plus Table 3 & Table 7 parity), **zero overclaims** (blocking `"ground-truth"`, `"independent blind"`, `"municipal trash"`, `"municipal solid-waste"`, `"isolate the causal effect"`, `"High-Price Durables"`), `0` PDF token leaks, and live `SHA256SUMS.json` integrity.
- **Visual Inspection:** Re-rendered updated 300-DPI figures (`fig2`–`fig5`) and compiled `manuscript_f7_boost.pdf`; visually inspected rendered PDF pages covering Abstract, Tables 1–3, Table 5, Section 6 (`3.95M` consumer self-disposal), Table 7, and Limitations via `read_file` with zero formatting defects, then removed temporary preview PNGs before regenerating `SHA256SUMS.json`.
- **Quality Gates:** `ruff check scripts tests` = `0` errors; `pytest -v` = `100%` passing.
