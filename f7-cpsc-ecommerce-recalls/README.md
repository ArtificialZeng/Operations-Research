# F7 Boost — The Asset-Light Safety Gap: Cross-Border Platform Disintermediation, Reverse-Logistics Collapse, and "Proof-of-Destruction" Recall Contracts (U.S. CPSC, 2000–2026)

**Target Venues:** *Management Science* / *Marketing Science* / *Manufacturing & Service Operations Management (M&SOM)* (UTD24 + FT50)  
**Workspace Root:** `D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\`  
**Camera-Ready Manuscript PDF:** [`manuscript_f7_boost.pdf`](file:///D:/AI_Science/antigravity/f7_boost_cpsc_ecommerce_recalls_20261126/manuscript_f7_boost.pdf) (embedded 300-DPI figures, 7 programmatically synchronized tables, 20 Crossref-verified journal DOIs + 5 verified legal/preprint/policy records, 0 leaked tokens; see [`REFEREE_RESPONSE_v2.md`](file:///D:/AI_Science/antigravity/f7_boost_cpsc_ecommerce_recalls_20261126/REFEREE_RESPONSE_v2.md) for the complete `v2` major-revision audit trail)

## Overview

Using the complete 27-year official U.S. Consumer Product Safety Commission (CPSC) SaferProducts Recall Census (`2000–2026`, $N = 8{,}386$ unique recalls) and a formal principal–agent and reverse-logistics contract model, this project documents how cross-border third-party (3P) e-commerce platform disintermediation generated a new equilibrium recall contract—**Consumer Self-Destruction with Photographic Verification ("Proof-of-Destruction")**—characterized by:

- **22-fold expansion** of Marketplace-Only recalls (`2.62%` in 2015 → `58.30%` in 2026) and surge of Foreign-Direct China recalls listing zero U.S. entities (`0.00%` → `41.70%`).
- **Strict-Era (`2022–2026`, $N = 1{,}822$, $G = 1{,}414$ firm clusters) Conditional Observational Associations:** Controlling for observables under full-rank ultra-saturated fixed effects, `1_Mkt_FD_China` is associated with **`+35.35 pp`** higher `photo_verify` ($t = +8.83$, $p_{\text{WCB}} = 0.001$; Logit $\text{OR} = 5.41\times$; within-marketplace $\Delta_{\text{FD}-\text{US}} = +29.03\text{ pp}$, $t = +7.23$), **`+25.48 pp`** higher `physical_mutilate` ($t = +7.07$), **`-35.07 pp`** lower `direct_return` ($t = -9.19$), and **`+61.01 pp`** free webmail / **`+57.07 pp`** zero phone hotlines. Disaggregating the `371` `1_Mkt_FD_China` `photo_verify` notices separates `253/371` (`68.2%`) triggering `physical_mutilate` (`202` physical destruction + `51` marking/defacing only) from `118/371` (`31.8%`) without `physical_mutilate` (`26` local HHW/recycling only + `92` photo-only). The `photo_verify` gap reaches **`+45.17 pp`** ($t = +6.72$, within-marketplace $+40.70\text{ pp}$) across all products priced $\ge \$100$ (`R7`, $N = 794$) and remains **`+41.39 pp`** ($t = +5.44$, within-marketplace $+36.57\text{ pp}$) in deterministic **Strict Durables ($\ge \$100$)** (`R7b`, $N = 685$, excluding apparel, textiles/bedding, personal care, and chemicals), while pure first-party `4_DTC_Online_Only` brands show an imprecisely estimated null (`+3.38 pp`, $95\%\text{ CI }[-6.48, +13.24]\text{ pp}$, $t = +0.67$, $p_{\text{WCB}} = 0.523$; `-6.09 pp` in products $\ge \$100$; `-4.41 pp` in strict durables $\ge \$100$; `-4.73 pp`, $p_{\text{WCB}} = 0.047$ on `free_webmail`).
- **Pioneer-to-Domestic Diffusion & Platform Generality:** Cross-border pioneers (`46.7%` in 2022 → `87.8%` in 2026) preceded sequential diffusion into U.S.-entity 3P (`20.7%` → `59.0%`) and Brick-and-Mortar (`9.6%` → `34.8%`, advancing **7× faster in China-manufactured imports** at `+11.33 pp/yr`, $t = +5.29$ vs. `+1.55 pp/yr`, $t = +1.43$ non-China); effects generalize across every 3P platform (even stronger off-Amazon at `+43.36 pp` vs. `+34.23 pp`).
- **Descriptive Structural Acceleration Around *In re Amazon.com* (`2021Q1–2026Q3`, Newey–West HAC $L = 4$):** *In re Amazon.com* legally governs Fulfilled-by-Amazon (`FBA`) products whereas public CPSC notices pool all Amazon-exclusive announcements (`1/601` explicit FBA mentions). In this pooled public series, `log(Amazon_Only / Brick_and_Mortar)` exhibits a sharp associative post-order slope acceleration of **`+0.1831/qtr`** ($t = +8.00$; **`+0.1999/qtr`, $t = +8.18$** controlling for STURDY Act & Reese's Law; **`+0.0525/mo`, $t = +4.40$** over $T = 70$ complete months), while post-order `photo_verify` entrenched (`60.2%` → `89.4%`, FE `+31.01 pp`).
- **Hazardous-Product Consumer Self-Disposal Remedies:** Inside hazard-gated lithium-ion, button-cell, and lead/chemical recalls ($N = 74$), `1_Mkt_FD_China` exhibits **`0.0%` firm direct-return programs**, **`79.7%` photo-verified non-return remedies**, and **`90.5%` consumer self-disposal remedies** (`FE +22.33 pp, p_WCB = 0.021`), covering **`3,947,390` recalled hazardous-product units** (`3,578,154` lithium-ion; `67.34%` concentrated in OCOOPA `1.50M` and Anker `1.16M`, where OCOOPA explicitly directs consumers to local HHW programs and prohibits household trash/recycling bins; actual waste-stream leakage is unobserved in CPSC notices), alongside a 17-fold collapse in joint Canada/Mexico recalls (`2.0%` vs. `34.8%`) and GS1 UPC listing (`0.2%` vs. `5.4%`).

## Reproducible Pipeline

All scripts run cleanly inside the isolated virtual environment `.venv`:

```powershell
$PY = "D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\.venv\Scripts\python.exe"
& $PY scripts\01_fetch_cpsc_census.py
& $PY scripts\02_parse_and_audit.py
& $PY scripts\03_formal_theory_model.py
& $PY scripts\04_pillar1_contract_econometrics.py
& $PY scripts\05_pillar2_3_4_mechanisms_shocks_safety.py
& $PY scripts\06_verify_references_crossref.py
& $PY scripts\07_generate_figures_and_tables.py
& $PY scripts\08_compile_manuscript_pdf.py
& D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\.venv\Scripts\ruff.exe check scripts tests
& D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126\.venv\Scripts\pytest.exe -v
```
