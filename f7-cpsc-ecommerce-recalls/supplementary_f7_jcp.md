# Supplementary Material: Who Bears the Burden of Product Recall Remedies? Notice-Level Duties, Channel Classification, and Institutional Governance in U.S. Third-Party E-Commerce Recalls, 2000–2026

**Zijian Zeng**  
Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA  
`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`

---

## Supplementary Appendix A. Conceptual Principal–Agent and Reverse-Logistics Contract Model

To organize why notice-level duties vary across supply-chain architectures, consider a firm recalling a defective product held by a unit mass of affected U.S. consumers owed refund/replacement value $p > 0$. Selecting a remedy contract $m \in \{R, D/U, P\}$ (physical return $R$, direct/unverified first-party remedy $D/U$, or photographic verification $P$) imposes consumer compliance hassle $k_P > k_R > k_{D/U} \approx 0$, yielding participation probabilities $q_P < q_R < q_0$. Let $\theta \in [0, 1]$ denote first-party buyer-record observability ($\theta_{\text{DTC}} \to 1$, $\theta_{\text{3P}} \ll 1$), $\alpha(1-\theta)p$ moral-hazard claim inflation under unverified remedies, $c_{\text{rev}}$ per-unit reverse-logistics cost, $a > 0$ per-claim seller verification/audit cost, and $\lambda > 0$ expected domestic legal/reputational liability per unremedied unit ($\lambda_{\text{FD}} < \lambda_{\text{US}}$; Shavell 1986). Expected per-unit seller costs are:

$$C_R = q_R (p + c_{\text{rev}}) + \lambda (1 - q_R)$$

$$C_{D/U}(\theta) = q_0 p + \alpha (1 - \theta) p + \lambda \big[(1 - q_0) + \phi(1 - \theta)\big]$$

$$C_P = q_P (p + a) + \lambda (1 - q_P)$$

Equating $C_P = C_R$ and $C_P = C_{D/U}(\theta)$ yields closed-form adoption thresholds:

$$c_{\text{rev}}^*(p, a, \lambda) \equiv \frac{q_P}{q_R} a + \frac{q_R - q_P}{q_R}(\lambda - p)$$

$$\theta^*(p, a, \lambda) \equiv 1 - \frac{q_P a - (q_0 - q_P)(p - \lambda)}{\alpha p + \lambda \phi}$$

Under calibrated durable-product parameters ($p = \$60$, $\lambda_{\text{US}} = \$140$, $\lambda_{\text{FD}} = \$35$, $q_0 = 0.780$, $q_R = 0.684$, $q_P = 0.540$, $\alpha = 0.35$, $\phi = 0.25$, $H = \$240$, $e_{\text{haz}} = \$18$), reducing institutional template/audit friction from $a_{2022} = \$18$ to $a_{2026} = \$6$ shifts the domestic cutoff $c_{\text{rev}}^*/p$ from 0.517 to 0.360 and raises $\theta^*$ from 0.484 to 0.599 (Figure S1A), illustrating how template standardization pulls domestic retailers toward photographic verification while leaving high-observability DTC brands shielded inside $D/U$. All numerical proposition verifications are stored in `results/03_theory_equilibrium.json`.

<!-- FIGURE:fig2_theory_equilibrium_and_archetype_gaps.png -->

---

## Supplementary Appendix B. Underpowered Sub-Comparisons and Full All-Channel Robustness Battery

Per journal reporting standards, narrow sub-comparisons with insufficient within-cell sample size ($N < 100$) are moved out of the main text and reported transparently in Table S1 below. Specifically, inside multi-channel online notices including Amazon (**Def 3**), requiring both `1_Mkt_FD_China` and `3_Mkt_True_US` inside identical `fine_noun_yr` cells retains only **$N = 55$ notices across 11 cells** (23 China-direct vs. 32 U.S.-entity), yielding wide confidence intervals (SE = 13.2–34.2 pp). Similarly, restricting to strict durables priced $\ge \$100$ inside Amazon channels leaves only 91 (Def 1), 73 (Def 2a), and 49 (Def 2b: 38 China-direct vs. 11 U.S.-entity) notices—showing consistently positive `photo_language` point estimates (+21.55 to +22.76 pp) with wide CIs crossing zero ($p_{\text{WCB}} = 0.124$ to $0.364$).

**Table S1. Underpowered Narrow Sub-Comparisons (`Def 3` Multi-Channel Online Common Support & Strict Durables $\ge \$100$ Inside Amazon Channels).**

| Underpowered Sub-Comparison & Outcome | $N$ | Clusters / Cells | $\beta$ (pp) | CR1 SE (pp) | 95% CR1 CI (pp) | $p_{\text{WCB}}$ |
|:---|---:|---:|---:|---:|---:|---:|
| Def 3 Multi-Ch Online CS: Photo Language | 55 | 52 / 11 cells | -15.61 | 17.17 | [-50.08, +18.86] | 0.446 |
| Def 3 Multi-Ch Online CS: Mandatory Photo | 55 | 52 / 11 cells | +5.63 | 26.98 | [-48.53, +59.79] | 0.796 |
| Def 3 Multi-Ch Online CS: Direct Return | 55 | 52 / 11 cells | -19.90 | 13.20 | [-46.39, +6.59] | 0.207 |
| Def 3 Multi-Ch Online CS: Physical Destruction | 55 | 52 / 11 cells | -12.01 | 34.15 | [-80.57, +56.55] | 0.754 |
| Def 3 Multi-Ch Online CS: Permanent Marking | 55 | 52 / 11 cells | +12.19 | 18.92 | [-25.78, +50.17] | 0.528 |
| Def 3 Multi-Ch Online CS: Photo-Only | 55 | 52 / 11 cells | -13.65 | 21.78 | [-57.39, +30.08] | 0.641 |
| Strict Durables >=\$100 in Def 1 Broad Amz: Photo Language | 91 | 85 firms | +21.55 | 13.82 | [-5.94, +49.04] | 0.124 |
| Strict Durables >=\$100 in Def 1 Broad Amz: Direct Return | 91 | 85 firms | -2.50 | 11.20 | [-24.78, +19.77] | 0.838 |
| Strict Durables >=\$100 in Def 1 Broad Amz: Physical Destruction | 91 | 85 firms | -1.27 | 12.70 | [-26.54, +23.99] | 0.905 |
| Strict Durables >=\$100 in Def 2a No Other 3P: Photo Language | 73 | 68 firms | +22.24 | 15.67 | [-9.04, +53.53] | 0.203 |
| Strict Durables >=\$100 in Def 2a No Other 3P: Direct Return | 73 | 68 firms | -11.57 | 12.84 | [-37.20, +14.06] | 0.488 |
| Strict Durables >=\$100 in Def 2a No Other 3P: Physical Destruction | 73 | 68 firms | -9.35 | 15.51 | [-40.30, +21.60] | 0.600 |
| Strict Durables >=\$100 in Def 2b Strict Amz-Excl: Photo Language | 49 | 44 firms | +22.76 | 16.72 | [-10.97, +56.48] | 0.364 |
| Strict Durables >=\$100 in Def 2b Strict Amz-Excl: Direct Return | 49 | 44 firms | -25.47 | 22.51 | [-70.87, +19.93] | 0.773 |
| Strict Durables >=\$100 in Def 2b Strict Amz-Excl: Physical Destruction | 49 | 44 firms | -2.01 | 19.82 | [-41.97, +37.96] | 0.932 |

*Notes:* Directly from `results/09_v4_channel_remedy_audit.json`. Narrow Amazon strict-durable regressions control for `hazard_cat`, `year`, and `is_china_mfr` with firm-clustered CR1 SEs and $B = 999$ Rademacher WCB.

Table S2 and Figure S2 present the complete 17-specification all-channel robustness battery (2022–2026) plus identical fine-product-noun head-to-head comparisons.

**Table S2. Complete All-Channel Robustness Battery on `photo_verify` (2022–2026).**

| All-Channel Specification (`photo_verify`, 2022–2026 unless noted) | $N$ | Clusters | `1_Mkt_FD_China` (pp) | CR1 $t$ | $p_{\text{WCB}}$ | Within-Mkt $\Delta_{\text{FD}-\text{US}}$ (pp) | $\Delta$ $t$ | $p_{\text{WCB}}$ | `4_DTC` (pp) |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| R1. Baseline Ultra-Saturated (Firm CR1) | 1,822 | 1,414 | +35.35 | +8.83 | 0.001 | +29.03 | +7.23 | 0.001 | +3.38 |
| R2. `Product_Cat` $\times$ `Year` Clustering | 1,822 | 75 | +35.35 | +8.67 | 0.001 | +29.03 | +6.40 | 0.001 | +3.38 |
| R3. `Fine-Product-Noun` $\times$ `Year` FE | 1,822 | 1,414 | +30.47 | +7.53 | 0.001 | +22.43 | +5.35 | 0.001 | +1.05 |
| R5. Within `Refund_Only` Recalls | 995 | 861 | +30.25 | +6.08 | 0.001 | +22.05 | +4.86 | 0.001 | +4.99 |
| R6. Within `Repair/Replace` Recalls | 815 | 597 | +38.41 | +5.17 | 0.001 | +30.28 | +3.72 | 0.001 | +3.45 |
| R7. Products Priced $\ge \$100$ (All Categories) | 794 | 571 | +45.17 | +6.72 | 0.001 | +40.70 | +5.97 | 0.001 | -6.09 |
| R7b. Strict Durables ($\ge \$100$) | 685 | 481 | +41.39 | +5.44 | 0.001 | +36.57 | +4.64 | 0.001 | -4.41 |
| R8. Large Batches ($\ge 10{,}000$ Units) | 767 | 613 | +35.52 | +5.77 | 0.001 | +22.92 | +3.44 | 0.002 | +8.67 |
| R9. Strictly Within Made-in-China | 1,203 | 1,015 | +27.88 | +5.89 | 0.001 | +25.84 | +5.72 | 0.001 | +5.59 |
| R10. Mediation (`+ free_webmail + no_phone`) | 1,822 | 1,414 | +29.95 | +6.18 | 0.001 | +24.75 | +5.39 | 0.001 | +2.05 |
| R11. Shell-Front Audit (FD China vs. Legacy U.S.) | 1,822 | 1,414 | +35.63 | +8.88 | 0.001 | +30.79 | +6.95 | 0.001 | +3.53 |
| R12. General Non-Rule Safety Defects | 1,116 | 798 | +32.30 | +5.14 | 0.001 | +24.65 | +3.67 | 0.003 | +9.96 |
| R13. Mandatory Federal Safety-Rule Violations | 706 | 639 | +20.13 | +3.62 | 0.002 | +20.75 | +4.55 | 0.001 | -10.31 |
| R16a. Era Sensitivity (2021–2026) | 2,034 | 1,543 | +34.64 | +9.23 | 0.001 | +27.98 | +7.34 | 0.001 | +3.85 |
| R16b. Era Sensitivity (2018–2026) | 2,739 | 1,962 | +36.19 | +10.90 | 0.001 | +31.14 | +8.97 | 0.001 | +1.74 |

*Notes:* Directly from `tables/table3_robustness_battery_2022_2026.csv` and `results/04_pillar1_econometrics.json`. Additional tests: **R4 Binomial Logit** ($N = 1{,}822$) yields `1_Mkt_FD_China` $\text{OR} = 5.41\times$ ($z = +7.01$) vs. `4_DTC_Online_Only` $\text{OR} = 1.04\times$; **R14 Stratified Permutation** ($B = 1{,}000$, Year $\times$ China strata, $N = 681$) gives observed gap +40.75 pp vs. null SD 3.16 pp ($p = 0.0010$); **R15a Leave-One-Category-Out** across all 15 categories keeps $\beta_{\text{FD}} \in [+27.46, +38.40]$ pp ($\min t = +6.70$); **R15b Leave-One-Year-Out** across 2022–2026 keeps $\beta_{\text{FD}} \in [+33.18, +38.04]$ pp ($\min t = +7.54$).

<!-- FIGURE:fig5_robustness_forest_and_platforms.png -->

---

## Supplementary Appendix C. Full *In re Amazon.com* HAC Time-Series Stress Tests, Diffusion Decomposition, and Honest Null Audits

Table S3 reproduces the complete Newey–West (1987) HAC interrupted time-series battery (2021Q1–2026Q3, $T = 23$ complete quarters) programmatically synced from `tables/table5_amazon_hac_shock_and_persistence.csv`. Across alternative lag lengths $L \in \{1, 2, 3, 4, 6\}$, `log(Amazon_Only / Brick_and_Mortar)` 2024Q3 slope $t$-statistics remain between +5.95 and +8.78. Adding STURDY Act (2023Q4+) and Reese's Law (2024Q2+) statutory dummies preserves the Amazon-over-brick-and-mortar slope (+0.1999/qtr, $t = +8.18$) while attenuating Amazon-over-other-3P (+0.0281/qtr, $t = +0.56$), honestly reflecting shared statutory rule sweeps across all 3P marketplaces.

**Table S3. Complete Descriptive Newey–West HAC Interrupted Time-Series Stress Tests (`tables/table5_canonical.md`).**

| Policy Cutoff & Relative Series | Pre-Slope | Pre $t$ | Level Jump | Level $t$ | Slope Change | HAC SE | Slope $t$ | Slope $p$ | $R^2$ |
|:---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| **Jul 30, 2024 (`2024Q3`) — FBA Distributor Order** | | | | | | | | | |
| `log(Amazon_Only / Brick_and_Mortar)` | +0.0159 | +1.49 | +0.3056 | +2.64 | **+0.1831** | 0.0229 | **+8.00** | 1.30e-15 | 0.894 |
| `log(Amazon_Only / NonAmazon_3P)` | -0.0083 | -0.18 | -1.0379 | -2.18 | **+0.1400** | 0.0556 | **+2.52** | 0.0118 | 0.277 |
| `log(1 + Amazon_Only)` | +0.0488 | +4.76 | -0.2153 | -1.94 | **+0.1840** | 0.0203 | **+9.09** | 1.01e-19 | 0.873 |
| `log(1 + Brick_and_Mortar)` *(Placebo)* | +0.0343 | +4.53 | -0.5169 | -6.30 | +0.0023 | 0.0118 | +0.20 | 0.8449 | 0.346 |
| **Jan 16, 2025 (`2025Q1`) — Final Remedy Order** | | | | | | | | | |
| `log(Amazon_Only / Brick_and_Mortar)` | +0.0318 | +2.47 | +0.4931 | +2.36 | **+0.1669** | 0.0377 | **+4.43** | 9.40e-06 | 0.881 |
| `log(Amazon_Only / NonAmazon_3P)` | -0.0454 | -1.12 | -0.4064 | -1.06 | **+0.1972** | 0.0824 | **+2.39** | 0.0166 | 0.184 |
| **Post-Lag Ramp (`2025Q2–2026Q3`)** | | | | | | | | | |
| `log(Amazon_Only / Brick_and_Mortar)` | +0.0350 | +2.91 | **+0.8384** | **+5.36** | **+0.0984** | 0.0285 | **+3.45** | 0.0006 | 0.896 |
| **Stress Tests (Statutory Controls & Monthly)** | | | | | | | | | |
| `+ STURDY (23Q4) & Reese's (24Q2)`: `Amz/BM` | -0.0009 | -0.06 | +0.3479 | +4.22 | **+0.1999** | 0.0244 | **+8.18** | 2.82e-16 | 0.902 |
| `Monthly (T=70, L=6, 2024-08)`: `Amz/BM` (/mo) | +0.0045 | +1.12 | +0.3754 | +2.33 | **+0.0525** | 0.0119 | **+4.40** | 1.07e-05 | 0.629 |
| `Monthly (T=70, L=6, 2024-08)`: `Amz/NonAmz` (/mo) | -0.0066 | -0.59 | -0.1583 | -0.29 | **+0.0324** | 0.0163 | **+1.99** | 0.0470 | 0.030 |

*Notes:* Directly from `tables/table5_amazon_hac_shock_and_persistence.csv`. As documented in Main Section 4.2, public CPSC notices contain 0/601 explicit "Fulfilled by Amazon" mentions (1/601 standalone "FBA" model suffix on TADAKAZU 10317); these series represent descriptive structural accelerations rather than causal FBA order evaluations.

**Brick-and-Mortar Diffusion Decomposition (2022–2026):** Inside `6_Brick_and_Mortar`, `photo_verify` adoption progressed at **+11.33 pp/yr** ($t = +5.29$, 14.9% → 60.0%) among China-manufactured retail imports ($n = 244$) versus only **+1.55 pp/yr** ($t = +1.43$, 6.8% → 10.5%, insignificant) among non-China goods ($n = 383$), and +7.66 pp/yr (price below \$100) vs. +3.39 pp/yr (price $\ge \$100$).

**August 2025 CPSC Universal `direct_contact` Boilerplate Edit:** Across 2024–2026, the phrase *"contacting all known purchasers directly"* dropped simultaneously to near zero on August 1, 2025 in every channel: `1_Mkt_FD_China` 59.3% → 0.0%, `3_Mkt_True_US` 45.5% → 2.0%, `5_Omnichannel` 21.9% → 0.0%, and `6_Brick_and_Mortar` 22.9% → 0.7%, confirming an agency press-release template revision excluded from all channel inferences.

---

## Supplementary Appendix D. Coding Codebook, Verbatim Edge-Case Excerpts, and Legacy Parser Consistency Audits

### D.1 Verbatim Benchmark Edge Cases Audited in Code and `pytest`

1. **Jugader Zipline Kits (`RecallID 9924`, Recall 24-199, 2024-04-11):** *Retailers:* "Amazon.com from March 2020 through June 2023 for about \$140." *Remedies:* "Consumers must submit a photo of the cable and the trolley or their online purchase order number to receive a free repair kit..." **Audit Labels:** `strict_amazon_exclusive`, `photo_language = 1`, `proof_alternative_path = 1`, `proof_status = optional_or_alternative_proof`, `photo_mandatory = 0`, `physically_disabled = 0`.
2. **UVIPC Baby Gates (`RecallID 10148`, Recall 25-122, 2025-02-06):** *Retailers:* "http://www.amazon.com from November 2022 through September 2024 for between \$186 and \$230." *Remedies:* "...contact Xianshengyouli via email at xianshengyouli@outlook.com for information on how to dispose of the product and submit proof of destruction to obtain a full refund." **Audit Labels:** `strict_amazon_exclusive`, `photo_language = 0`, `destruction_proof = 1`, `destruction_proof_without_photo = 1`, `proof_status = mandatory_proof`, `physically_disabled = 1`.
3. **Anker PowerCore 10000 (`RecallID 10311`, Recall 25-338, 2025-06-12, 1,158,000 units):** *Retailers:* "Online at Anker, Amazon, Newegg and Ebay from June 2016 through December 2022 for about \$27." **Audit Labels:** `multi_channel_with_amazon`, `photo_language = 1`, `photo_mandatory = 1`, `permanent_marking = 1`, `physically_disabled = 0`, `warning_remedy = 0`, `warning_full_notice = 1`.
4. **OCOOPA Hand Warmers (`RecallID 10895`, Recall 26-659, 2026-07-30, 1,500,000 units):** *Retailers:* "Online at Amazon.com, Ocoopa.com, Ocoopa.net and Walmart.com..." **Audit Labels:** `multi_channel_with_amazon`, `photo_language = 1`, `photo_mandatory = 1`, `permanent_marking = 1`, `physically_disabled = 0`, `warning_remedy = 1`, `warning_full_notice = 1` (explicitly prohibits household trash, curbside bins, and retail drop-boxes).
5. **TADAKAZU Baby Loungers (`RecallID 10317`, Recall 25-345, 2025-06-18):** *Retailers:* "Exclusively on Amazon from September 2024 through May 2025..." **Audit Labels:** `strict_amazon_exclusive`, `photo_language = 1`, `photo_mandatory = 1`, `physically_disabled = 1`, `explicit_fba = 0`, `fba_token = 1` (model-name suffix only).
6. **Ambiguous Channel Cases (5 in 2022–2026):** `RecallID 9234` (Shop LC airing on "Amazon Fire" TV app), `RecallID 10238` (Retailers says exclusively Walmart.com while Remedies says Costway and Amazon contact purchasers), `RecallID 10245` (Title says Sold on Amazon.com while Retailers says Rooms To Go), `RecallID 10276` (Title says Sold on Amazon.com while Retailers says exclusively FidgetThings.com), and `RecallID 10494` (Title says magnet fidget spinner sold on Amazon while Retailers lists Spartan dealers at \$16,400–\$19,700).

### D.2 Legacy Author-Reviewed Parser Consistency Audits (150 Census + 50 Disjoint OOS 2025–2026)

For full provenance alongside our v4 stratified $N = 150$ remedy-duty audit (`tables/table_remedy_duty_coding_audit.csv`), the legacy 150-recall census consistency audit (`tables/table_parser_audit_150.csv`, `seed = 20261126`) achieved `archetype_6` exact consistency 99.33% (149/150), `has_injury` F1 0.9730 (97.33% exact injury count; 100.0% exact `price` and `units`), while the disjoint 50-recall out-of-sample 2025–2026 consistency stress-test (`seed = 9992026`) achieved 100.0% on `archetype_6`, `photo_verify` (32 TP, 18 TN), and `direct_return` (6 TP, 44 TN), 94.0% (F1 = 0.9362) on `physical_mutilate`, and 98.0% (F1 = 0.9474) on `has_injury`. Both legacy audits and the v4 structured audit are author-reviewed consistency checks rather than independent double-blind multi-coder annotations.
