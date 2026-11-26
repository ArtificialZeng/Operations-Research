# Point-by-Point Referee Response — Major Revision `v2` (`I4`: SEC Rule 35d-1 "80% Names Rule")

**Date:** November 26, 2026  
**Workspace:** `D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126`  
**Revised Manuscript:** `manuscript_i4_boost.md` & `manuscript_i4_boost.pdf` (20 pages, 0 leaked tokens)

We thank the external referee for an exceptionally sharp, constructive, and legally precise review. Every single critique pinpointed a concrete institutional, econometric, or framing defect. Rather than offering cosmetic prose tweaks, we executed a full code-backed **Major Revision (`v2`)** across our look-through holdings pipeline (`03`), econometric estimation suite (`04`), figures (`06`), manuscript generator (`07a`), live citation auditor (`07`), PDF compiler (`08`), regression test suite (`tests/test_i4_boost.py`), and cryptographic manifest (`SHA256SUMS.json`). Below is a point-by-point mapping of each referee critique to exact code changes, verified numerical outputs, and manuscript revisions.

---

## Critique 1: Statutory SEC Release Citation Error (`IC-35962` → `IC-35963`) and Missing Official SEC Sources (`33-11238`, `33-11368`, `2025–26 Names Rule FAQs`, `Press Release 2026-19`)

### Referee Concern
The previous draft cited Release No. `IC-35962` for the SEC's February 18, 2026 Form N-PORT Names-Rule compliance-date extension (whereas the actual official SEC release is **`IC-35963`**, with `ic-35962.pdf` returning HTTP `404` on `sec.gov`), and omitted direct citations to the full Release Numbers (`33-11238 / IC-35000`, `33-11368 / IC-35500`), the SEC Division of Investment Management's *2025–26 Names Rule FAQs*, and SEC Press Release `2026-19`.

### Exact Code & Manuscript Fixes
1. **Complete Elimination of `IC-35962` → `IC-35963`:** Replaced every occurrence of `IC-35962` with **`IC-35963`** across `scripts/07a_generate_manuscript_md.py`, `scripts/07_verify_citations.py`, `manuscript_i4_boost.md`, `manuscript_i4_boost.pdf`, `README.md`, and `results/07_verified_references_crossref.json`.
2. **Full Official SEC Citations (Live HTTP `200` Verified):** Upgraded References `#18–#23` in `scripts/07a_generate_manuscript_md.py` and added live HTTP `200` verification for all six official SEC URLs in `scripts/07_verify_citations.py`:
   - **Ref #18:** Release No. `IC-24828` (Jan 17, 2001) — `https://www.sec.gov/rules/final/ic-24828.htm` (`HTTP 200`)
   - **Ref #19:** Release No. `33-11238; 34-98438; IC-35000` (Sep 20, 2023) — `https://www.sec.gov/files/rules/final/2023/33-11238.pdf` (`HTTP 200`)
   - **Ref #20:** Release No. `33-11368; 34-102680; IC-35500` (Mar 14, 2025) — `https://www.sec.gov/files/rules/final/2025/33-11368.pdf` (`HTTP 200`)
   - **Ref #21:** Release No. `IC-35963` (Feb 18, 2026; extending Form N-PORT Names-Rule reporting to Nov 17, 2027 / May 18, 2028) — `https://www.sec.gov/files/rules/final/2026/ic-35963.pdf` (`HTTP 200`)
   - **Ref #22:** SEC Division of Investment Management, *2025–26 Names Rule FAQs* (updated Jan 8, 2025) — `https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/2025-26-names-rule-faqs` (`HTTP 200`)
   - **Ref #23:** SEC Press Release No. `2026-19` (Feb 18, 2026, proposing to reduce Form N-PORT burdens including removing Names-Rule reporting items) — `https://www.sec.gov/newsroom/press-releases/2026-19-sec-proposes-amendments-reduce-burdens-reporting-fund-portfolio-holdings` (`HTTP 200`)
3. **Automated Guardrails:** `scripts/07_verify_citations.py` and `tests/test_i4_boost.py::test_15_v2_sec_citations_ex_vanguard_and_sec_faq_robustness` now assert `0` occurrences of `35962` across all text/PDF/JSON deliverables and confirm `17/17` Crossref DOIs + `6/6` SEC URLs live HTTP `200` with `100%` two-way body-to-bibliography sync.

---

## Critique 2: Ex-Vanguard AUM Concentration Sensitivity (`57.7%` → `4.9%` of Renamed Multi-Asset AUM)

### Referee Concern
While numeric-ratio labeling represents `57.7%` (`$67.82B`) of renamed multi-asset GVI AUM overall, Vanguard's four LifeStrategy funds (`$65.26B`, EDGAR `497` Acc. `0000736054-26-000102`) drive nearly all of that dollar weight (`96.2%`), making it essential to quantify and highlight Ex-Vanguard sensitivity transparently rather than presenting the `57.7%` AUM share as a broad industry-wide wave.

### Exact Code, Econometric & Manuscript Fixes
1. **Programmatic Ex-Vanguard Decomposition & DiD (`scripts/04_econometrics_main_and_robustness.py` → `results/04_econometrics_results.json["ex_vanguard_sensitivity"]`, `tables/table1_main_did_bifurcation.csv`):**
   - **Vanguard Concentration Verified:** Vanguard accounts for **`96.2%`** (`$65.26B / $67.82B`) of the numeric-ratio arm's renamed AUM and `55.5%` (`$65.26B / $117.63B`) of total renamed multi-asset GVI AUM.
   - **Ex-Vanguard Multi-Asset Bifurcation (`n = 46` funds, `$52.36B`, `18` complexes):**
     - **Numeric Ratios:** drops from `57.7%` overall (`7/50` funds, `$67.82B`) to **`4.9%` of renamed AUM (`$2.56B` across `3/46 = 6.5%` of funds at BlackRock/iShares and Fidelity)**.
     - **Opaque Synonyms:** rises from `84.0%` of funds / `42.3%` of AUM overall to **`91.3%` of funds (`42/46`) and `95.1%` of renamed AUM (`$49.79B`) across `18` non-Vanguard complexes**.
   - **Ex-Vanguard DiD Estimations (added to Table 1 & Figure 3B):**
     - `A3_GVI_EX_VANGUARD` (`2020Q1–2026Q3`): **`+1.57 pp/qtr`** (`SE = 0.52`, `t = +3.04`, `p_WCB = 0.001`; complete `2020Q1–2026Q2`: `+1.64 pp`, `p_WCB = 0.002`; joint pre-trend `F = 1.06, p = 0.390`).
     - `A3_GVI_OPAQUE_EX_VANGUARD`: **`+1.58 pp/qtr`** (`SE = 0.49`, `t = +3.24`, `p_WCB = 0.002`; complete `2020Q1–2026Q2`: `+1.65 pp`, `p_WCB = 0.001`).
     - `A3_GVI_NUMERIC_EX_VANGUARD`: `+0.11 pp/qtr` (`SE = 0.09`, `t = +1.23`, `p_WCB = 0.315`).
2. **Visual & Narrative Candor:**
   - Added a dedicated **`Renamed AUM (Ex-VG)`** bar pair directly beside `Renamed AUM (All)` in **Figure 2 Panel A** (`42.3% vs. 57.7%` side-by-side with `95.1% vs. 4.9%`) and added `Ex-Vanguard: GVI Opaque Only` to **Figure 3 Panel B**.
   - Reframed the **Abstract**, **Section 1**, **Section 4.3** (new dedicated Ex-Vanguard Concentration Sensitivity bullet), **Table 1**, **Section 8 (Limitation #2)**, and **Policy Implications & Conclusion** to state explicitly that opaque-synonym evasion is broad-based across `18` non-Vanguard complexes (`91.3%` of funds / `95.1%` of AUM), whereas the AUM weight of numeric-ratio transparency is heavily concentrated in one index leader (Vanguard).

---

## Critique 3: Statutory 80% Basket Proxy Framing & SEC 2025–2026 FAQs Carve-Out (`Income` and `Growth and Income`)

### Referee Concern
First, amended Rule 35d-1 allows multi-asset funds to define a multi-asset 80% investment basket in their prospectus rather than requiring $\ge 80\%$ in a single asset class (pure stocks or pure bonds), so `max(%Eq, %Bond) < 80%` and the `-6.92 pp` differential should not be framed as proving literal statutory noncompliance by keepers. Second, the SEC Division of Investment Management's *2025–26 Names Rule FAQs* (January 8, 2025) clarify staff views that standalone non-fixed-income *"income"* and certain *"growth and income"* hybrids may convey portfolio-wide objectives rather than triggering an 80% policy.

### Exact Code, Econometric & Manuscript Fixes
1. **Accurate Reframing Throughout Text, Tables, and Figures:**
   - Removed every overclaiming phrase (including replacing `"<80% Non-Compliant Blended Zone"` on **Figure 4A** with `"<80% Single-Class Blended Zone"` and asserting `"Non-Compliant" not in pdf_txt` in `tests/test_i4_boost.py`).
   - Reframed `max(%Eq, %Bond) < 80%` and `ACTIVE_TOWARD_80` throughout the **Abstract**, **Section 1**, **Section 2**, **Table 1**, **Section 6**, **Table 4**, and **Figure 4** as a **single-asset-class concentration / stock-bond allocation inertia proxy**, explicitly acknowledging prospectus-defined multi-asset 80% baskets and showing that the `-6.92 pp` separation proves **differential stock-bond allocation inertia** between droppers and keepers (NOT literal statutory violations).
2. **New SEC-FAQ-Adjusted Strict Non-Exempt Robustness Suite (`scripts/04_econometrics_main_and_robustness.py` & `scripts/03_holdings_lookthrough_rebalancing.py`):**
   - **Dropper Audit Breakdown (`results/04_econometrics_results.json["sec_faq_robustness"]`):** Of our `50` multi-asset GVI droppers, **`35/50` (`70.0%`, `$104.55B` across `16` complexes)** are strictly non-FAQ-exempt *Growth*/*Value* funds containing neither *Income* nor *Growth and Income* (versus `13` *Income*-only bond-heavy funds such as 20/80 *LifeStrategy Income* and *Fidelity Freedom Income*, and `2` *Growth and Income* hybrids).
   - **Strict Non-FAQ DiD & High-Dimensional FE (Table 1 Panels B & D; Figure 3B):**
     - `FAQ1_GV_NO_GI` (excluding *Growth and Income* hybrids): **`+2.66 pp/qtr`** (`t = +3.01`, `p_WCB = 0.001`).
     - `FAQ2_GV_NO_INC` (excluding ALL *Income* and *Growth and Income* funds): **`+2.78 pp/qtr`** (`t = +3.00`, `p_WCB = 0.001`).
     - `FAQ3_GV_NO_INC_OPAQUE` (same, opaque synonyms only): **`+2.27 pp/qtr`** (`t = +2.68`, `p_WCB = 0.003`; joint pre-trend `F = 0.97, p = 0.472`).
     - `FAQ4_GV_NO_INC_HOLD_LT80` (strict non-FAQ `GV` + `<80%` single-class proxy): **`+1.83 pp/qtr`** (`t = +2.43`, `p_WCB = 0.008`).
     - `FE6` (`COMPLEX_ID × REP_YQ` identifying-only FE inside strict non-FAQ `GV`, `N = 26,462, G = 63`): **`+2.50 pp/qtr`** (`t = +2.70`, `p_WCB = 0.003`).
   - **Strict Non-FAQ Look-Through Portfolio Inertia (`results/03_holdings_lookthrough.json["inertia_cross_section"]["HOLD_LT_CONSTR_GV_NO_INC"]`, Table 4 Panel C, Figure 4B):**
     - Inside the strict non-FAQ `<80%` single-class proxy sample (`19` droppers vs. `132` keepers), droppers actively trimmed equity drift by **`-3.22 pp`** vs. **`+2.25 pp`** for keepers — a **`-5.47 pp` differential (`t = -2.02`, `p_WCB = 0.050`)**, alongside significantly lower absolute active equity rebalancing (**`-4.99 pp`, `t = -2.08`, `p_WCB = 0.041`**) and **`+12.31 pp`** higher `IS_FOF`-controlled CUSIP overlap (`74.9%` vs. `58.3%`).

---

## Critique 4: Exact On-Cycle Annual Prospectus Compliance Dates (`33-11368`), Removal of `2026Q4` Small-Group Overclaim, and SEC Press Release `2026-19`

### Referee Concern
Under Release No. `33-11368 / IC-35500` (March 14, 2025), ongoing open-end funds do not face a single calendar-quarter compliance cliff on June 11 or December 11, 2026; instead, compliance is tied to each fund's **first "on-cycle" annual prospectus update filed on or after June 11, 2026** ($\ge \$1$B) or **on or after December 11, 2026** ($< \$1$B). Claiming that adding `2026Q4` N-PORT alone will complete the `< $1B` small-group compliance wave was inaccurate. Additionally, SEC Press Release `2026-19` (February 18, 2026) proposes to eliminate Form N-PORT Names-Rule reporting items entirely.

### Exact Code & Manuscript Fixes
1. **Exact On-Cycle Compliance Mechanics (`Section 1`, `Section 4.4`, `Section 5`, `Section 8`, `Figures 1A & 2C`):**
   - Revised all institutional descriptions to reflect Release `33-11368 / IC-35500`'s exact **on-cycle annual prospectus update** rule.
   - Explicitly linked our empirical **May 1, 2025 lock-in wave** (`7/7` May-2025 effective dates on exact May 1, 2025) to Release `33-11368`'s own discussion noting that December-31 fiscal-year-end open-end funds file material on-cycle annual updates by March 2 for a May 1 effective date—12 days *before* the March 14, 2025 extension!
   - Removed every claim that `2026Q4` N-PORT alone completes the `< $1B` small-group rollout (enforced by pytest assertion in `test_15`), stating accurately that large-group on-cycle updates continue into mid-2027 and full small-group replication requires tracking **`2027Q1–2027Q4`** on-cycle updates beginning after December 11, 2026.
   - Updated chart labels on **Figure 1A** and **Figure 2C** from `"Binding Cliff"` / `"Statutory Cliff"` to `"On-Cycle Start (Jun 11, 2026)"`.
2. **SEC Press Release `2026-19` Policy Integration (`Section 1`, `Section 4.4`, `Section 8`):**
   - Documented that concurrently with `IC-35963`'s extension, **SEC Press Release `2026-19`** (Feb 18, 2026) proposed Form N-PORT amendments to reduce reporting burdens—including **proposing to remove Form N-PORT Names-Rule reporting fields altogether**—demonstrating why our prospectus-grounded (`497`/`485BPOS`) and 4-tier look-through holdings methodology is essential for future empirical and regulatory oversight.

---

## End-to-End Verification Summary (`v2`)

| Check | Status | Verified Result |
|---|---|---|
| `ruff check scripts/ tests/` | PASS | `0` errors |
| `pytest -v tests/test_i4_boost.py` | PASS | `15/15` tests passed (`100%`, including new `test_15`) |
| Live Crossref + SEC URL Audit (`07`) | PASS | `17/17` academic DOIs HTTP `200` + `6/6` official SEC URLs HTTP `200`; `0` occurrences of `IC-35962` |
| PDF Zero-Leak & Visual Inspection (`08`) | PASS | `20` pages, `0` leaked tokens, visual audit of Figures 1–5 & key pages clean |
| Cryptographic Manifest (`09`) | PASS | `SHA256SUMS.json` regenerated over all `43` LF-normalized artifacts |
