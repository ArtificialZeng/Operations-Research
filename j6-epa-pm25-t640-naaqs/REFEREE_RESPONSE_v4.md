# Point-by-Point Referee Response (`v4` *Environmental Science & Technology* Submission) — Flagship `J6`

**Manuscript:** *Residual Optical PM₂.₅ Bias During Wildfire Smoke and Sensitivity of U.S. Exceptional-Event Tiering Thresholds*  
**Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my`)  
**Workspace:** `D:\AI_Science\antigravity\j6_boost_epa_pm25_t640_naaqs_20261126`  
**Revision Date:** `2026-11-28`

We thank the reviewer for an exceptionally thorough, concrete, and scientifically sharp evaluation (`J6.md`). Every P0 and P1 requirement—as well as the structural recommendation to refocus the main manuscript tightly as a field-metrology and screening-threshold contribution for *Environmental Science & Technology* (`ES&T`)—has been implemented directly in reproducible Python code, machine-readable JSON receipts, exported CSV pair/manifest tables, publication figures, automated regression tests, main manuscript (`manuscript_j6_boost.pdf`), and Supporting Information (`supplementary_j6_est.pdf`).

---

## Response to Evidence Calibration (`v1`/`v2` vs. `v3` Official EPA Tiering Replay)

- **Action Taken:** We integrated EPA's exact April 2024 *PM₂.₅ Wildland Fire Exceptional Events Tiering Document* (`EPA-457/R-24-001`) algorithm and pinned EPA's live public site-month threshold snapshot (`for_posting.csv`, AQS query date `2026-09-14`, `13,138` rows, `R` and fire-`I` flags excluded, SHA-256 `ac314789d31b89fd93f044e01d71affd9af3bf0454dae1c685adfc5348cf40e4`) directly into the primary workspace via `scripts/10_official_tier_replay.py` → `results/10_official_tier_replay.json`.
- **Exact Reproduction:** Across `468` threshold-matched `T640_FW–FRM` Heavy-smoke pairs (`165` sites, `45` dates), aligned `T640_FW` triggers **`123`** Tier-1 crossings versus **`89`** on collocated FRM (**`36` T640-only vs. `2` FRM-only**, paired difference **`+7.26 pp`**, 95% CI **`[+4.15, +10.38] pp`** across `27` national smoke-date blocks). The retired custom `v2` pooled `min(p98, 35)` proxy is no longer used in the main manuscript; the fixed daily `>35 µg/m³` level-equivalent benchmark (`51` vs. `26` matched; `+5.34 pp`, national-block CI `[-0.63, +11.31]`) is explicitly presented as episodic and secondary to the official EPA Tier-1 threshold.

---

## P0 #1: Common-Support Audit Between `T640_FW–FRM` and `BAM–FRM` Queues

**Referee Critique:**  
`T640–FRM` and `BAM–FRM` share only `4` same-site, same-day triple observations (`27` overlapping dates) under Heavy smoke, so BAM's `84` vs. `84` belongs to a different geographic/concentration queue. Either establish common support (reporting overlap rates and differential CIs) or demote BAM to a background reference comparator while retaining each instrument's clean within-site comparison against its own collocated FRM.

**Actions Taken (`scripts/11_v4_est_audit_and_exports.py`, Section 2.2, Section 3.1, Table 1, Figure 1, SI Table S1):**
1. **Transparent Triple & Overlap Audit:** Explicitly audited and reported exact overlap across both all `2023–2025` pairs (`63,951` T640 vs. `22,927` BAM: **`401` same-site, same-day triples across `5` sites**, where mean `T640 − BAM` rises monotonically from `+0.41` non-smoke to `+0.71` Medium to `+2.88 µg/m³` Heavy) and NOAA HMS Heavy smoke (**exact `4` Heavy-smoke triples across `4` sites, `6` overlapping sites, `27` overlapping dates**; all 4 individual triple records published in SI Table S1). Explicitly documented the geographic and reference-concentration disjointness (`47/197 = 23.9%` of BAM Heavy pairs sit in EPA Regions 9–10 where T640 has zero Heavy pairs; median FRM `12.25` T640 vs. `16.70 µg/m³` BAM).
2. **Common-Support Matched Benchmarks with Differential Clustered CIs (Table 1, Figure 1B):**
   - Full Matched Heavy: `+7.26 pp` T640 vs. `+0.00 pp` BAM → Diff **`+7.26 pp`** (`[+3.13, +11.40]`, `p = 0.0009`).
   - Overlapping EPA Regions (`R1–5, R7–8`; `100.0%` T640 / `76.1%` BAM): `+7.26` vs. `-0.67 pp` → Diff **`+7.93 pp`** (`[+3.50, +12.36]`, `p = 0.0009`).
   - Overlapping Smoke Dates (`27` dates; `89.1%` T640 / `56.9%` BAM): `+7.91` vs. `-2.68 pp` → Diff **`+10.59 pp`** (`[+4.55, +16.63]`, `p = 0.002`).
   - Overlapping Dates & Regions (`89.1%` T640 / `48.2%` BAM): `+7.91` vs. `-3.16 pp` → Diff **`+11.07 pp`** (`[+4.48, +17.66]`, `p = 0.003`).
   - Overlapping Dates, Regions & `FRM ≤ 50 µg/m³` (`88.0%` / `47.2%`): `+8.01` vs. `-3.23 pp` → Diff **`+11.24 pp`** (`[+4.43, +18.04]`, `p = 0.003`).
   - Exact Overlap-Weighted (`EPA Region × FRM-bin`, `29` shared cells covering `100.0%` T640 / `66.0%` BAM): `+9.22` vs. `-1.21 pp` → Diff **`+10.42 pp`** (`1,000`-block bootstrap 95% CI **`[+1.43, +18.80] pp`**).
3. **Explicit Demotion of `BAM–FRM`:** Because Heavy-smoke triple support is `n = 4`, the Abstract, Methods, Results, Table 1, and Discussion explicitly retain each instrument's clean within-site pairing against its own collocated FRM as primary and **demote `BAM–FRM` strictly to a background reference comparator**.

---

## P0 #2: Strictly Out-of-Time Prospective Official EPA April 2024 Tier-1 Replay

**Referee Critique:**  
`v3`'s official EPA `2021–2025` table overlaps the `2023–2025` observation window. Reconstruct site-month thresholds strictly out-of-time from historical certified 5-year windows following EPA's formula and flag rules, benchmark against the published table, and compare contemporaneous out-of-time vs. fixed versions alongside bidirectional and near-threshold discordance.

**Actions Taken (`scripts/11_v4_est_audit_and_exports.py`, Section 2.3, Section 3.2, Table 2, Figure 2, SI Table S2 & Figure S2A):**
1. **Exact Appendix N Reconstruction & Validation (`2021–2025` Benchmark):** Implemented EPA-457/R-24-001's exact formula (`1.5 × min(5-yr same-month P98, min of 5 annual P98s)`) using 40 CFR Part 50 Appendix N § 3.0(d) combined-site primary-POC aggregation and § 4.5(a) Table 1 order statistics. Validated directly against EPA's published `2021–2025` `for_posting.csv`: across `1,160` zero-event clean site-months, median absolute Tier-1 error is exactly **`0.000 µg/m³`** (`r = 0.876`–`0.896`).
2. **True Out-of-Time Prospective Rolling 5-Year Replays (May 1 Certified Calendar: `2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`):** Because public AirData bulk CSVs expose AQS `Excluded` daily records and `Events Excluded` annual 98th percentiles (`R`-flagged days removed, matching EPA-457/R-24-001 p. 16's AMP480 conservative bound) but omit individual-day `I`-qualifier flags, we report all four transparent prospective specifications (`Table 2`, `Figure 2A`):
   - **`OOT-A` (Conservative `R`-Excl AQS / AMP480):** `116` vs. `90` (**`26` vs. `0`**), **`+5.57 pp`** (Nat. Block `[+1.63, +9.50]`; 2-Way `Site × Region-Ep.` **`[+2.77, +8.37]`**, `p = 0.0002`; yearly: `+8.25`, `+5.13`, `+3.08 pp`); BAM `72` vs. `72` (`+0.00 pp`, `p = 1.000`).
   - **`OOT-B` (Fire-Screen Proxy excl. HMS Heavy + `R`-Excl):** `119` vs. `90` (**`29` vs. `0`**), **`+6.21 pp`** (Nat. Block `[+1.35, +11.07]`; 2-Way **`[+3.08, +9.34]`**, `p = 0.0002`); BAM `73` vs. `73` (`+0.00 pp`).
   - **`OOT-B2` (Expanded Fire-Screen excl. HMS Med+Heavy + `R`-Excl):** `124` vs. `91` (**`33` vs. `0`**), **`+7.07 pp`** (Nat. Block `[+1.94, +12.19]`; 2-Way **`[+3.57, +10.56]`**, `p = 0.0002`); BAM `80` vs. `79` (`+0.52 pp`, `p = 0.663`).
   - **`OOT-C` (Pure Gravimetric FRM-Only Baseline):** `116` vs. `90` (**`26` vs. `0`**), **`+5.70 pp`** (Nat. Block `[+0.43, +10.97]`; 2-Way **`[+2.17, +9.23]`**, `p = 0.002`); BAM `64` vs. `64` (`+0.00 pp`).
3. **Bidirectional & Near-Threshold Band Audit (`Figure 2B`):** Explicitly reported both directions (`36` vs. `2` official; `26–33` vs. `0` OOT) and near-threshold bands: within `±10%` of Tier-1 by FRM (`n = 34`): `21` vs. `2` (`+55.88 pp`); by symmetric midpoint (`n = 34`): `30` vs. `2` (`+82.35 pp`). Within `±20%` by FRM (`n = 71`): `32` of `36` T640-only crossings vs. `2` FRM-only (`+42.25 pp`); by midpoint (`n = 92`): `36/36` (`100%`) vs. `2` (`+36.96 pp`); BAM within `±20%`: `5` vs. `5` (`+0.00 pp`). Transparently explained why 2025 OOT estimates are narrower than fixed `2021–2025` (the 2023 Canadian wildfire season enters `2020–2024` without raw `I`-flag removal, matching EPA p. 16's conservative AMP480 behavior).

---

## P1 #3: Ground-Level Smoke Specificity, Non-Smoke High-PM Controls & Event-Level Two-Way Inference

**Referee Critique:**  
National consecutive smoke blocks can mix geographically independent plumes; report year-by-year stability, two-way site × event inference, leave-region-out validation, independent ground-level smoke verification, and equal-concentration non-smoke controls—calibrating whether discordance is smoke-specific or generic threshold sensitivity.

**Actions Taken (`scripts/11_v4_est_audit_and_exports.py`, Section 2.4, Section 3.3, Tables 3–4, Figures 3–4):**
1. **Multi-Dimensional Event-Level Inference & Spatial Generalizability (`Table 4`, `Figure 4A`):**
   - Separated simultaneous plumes into `55` geographically distinct `EPA-Region × Smoke-Episode` clusters ($\le 2$-day gap within region) and computed Cameron–Gelbach–Miller (2011) two-way `Site × Region-Smoke-Episode` 95% CI: **`[+3.43, +11.10] pp` (`p = 0.0004`)** (and two-way `Site × National Block`: **`[+4.26, +10.27] pp`, `p = 3.68 × 10⁻⁵`**).
   - **Year-by-year stability (`2023 / 2024 / 2025`):** `+6.77 / +6.41 / +8.08 pp` (`n = 192 / 78 / 198`).
   - **Leave-One-EPA-Region-Out (`7` regions):** Range **`[+6.33, +9.15] pp`**, with all 7 leave-region-out two-way 95% CIs strictly positive.
2. **Equal-Concentration Non-Smoke (`HMS = 0`) vs. Heavy Smoke Controls (`Table 3`, `Figure 3A`):**
   - Evaluated across ALL three concentration metrics (`FRM`, strictly EIV-robust `Other-Site FRM/BAM`, and `Bland–Altman Midpoint` at `≥15`, `15–25`, `≥20`, `≥25 µg/m³`).
   - **Honest Two-Layer Calibration:** (i) Residual baseline bias generates genuine modest two-sided threshold sensitivity on elevated non-smoke days at `15–25 µg/m³` (`+3.09` to `+9.02 pp`, concentrated in humid winter `DJF` inorganic haze: `+4.06 pp`, `22` vs. `11`; whereas warm-season non-smoke `FRM ≥ 20` is negative `-20.93 pp`, bias `-6.15 µg/m³`); AND (ii) **wildfire smoke amplifies optical bias three- to fivefold across every matched stratum** (`Other-Site ≥ 15`: `+0.64` non-smoke vs. `+5.18 µg/m³` Heavy, `p = 3.44 × 10⁻¹³`, Tier-1 `+3.43` vs. `+16.46 pp`, `p = 0.004`; `FRM ≥ 25`: `-2.81` vs. `+7.98 µg/m³`, `p = 1.19 × 10⁻⁷`, Tier-1 `-0.74` vs. `+9.59 pp`, `p = 0.049`).
3. **Independent Ground-Level Smoke Confirmation (`Figure 3B`):**
   - `HMS Heavy & FRM > site-month non-smoke p90` (`n = 336`): bias `+3.78 µg/m³`, Tier-1 **`+10.12 pp` (`36` vs. `2`)**, vs. aloft plumes (`FRM ≤ p90`, `n = 119`): **`0` vs. `0` (`0.00 pp`)**.
   - `HMS Heavy & Surface OC ≥ 5 µg/m³` (`n = 83`): bias **`+5.65 µg/m³`**, Tier-1 **`+12.05 pp` (`11` vs. `1`)**, vs. `OC < 5` (`n = 67`): `+1.49 pp` (`1` vs. `0`); `OC/EC ≥ 5` (`n = 110`): bias `+4.28 µg/m³`, Tier-1 `+8.18 pp` (`10` vs. `1`).

---

## P1 #4: Restructuring Strictly for *Environmental Science & Technology* (`ES&T`) & Reproducible Archive

**Actions Taken:**
1. **Tight *ES&T* Main Manuscript (`manuscript_j6_boost.pdf`, 12 pages, 4 figures, 4 tables):** Restructured strictly around `(1) Collocated Pairing Quality & Common Support → (2) Official EPA Tier-1 & Out-of-Time Prospective Replay → (3) Smoke-vs-Non-Smoke Controls, Ground-Level Confirmation, Speciation, & Event-Level Robustness`. Removed all `Target Venues`/`Track A`/`Track B` metadata and applied exact authorship formatting. Positioned sharply against **Long et al. (2023)**, **McClure et al. (2026)** (`10.1080/10962247.2026.2639376`), **Krupnick et al. (2025)** (`10.1021/acs.est.4c08946`), and **U.S. EPA (2024b)** (`EPA-457/R-24-001`), with `15/15` Crossref DOIs live-verified (`100%`) and `21/21` two-way citation sync.
2. **Supporting Information (`supplementary_j6_est.pdf`, 4 pages, 2 SI figures, 4 SI tables):** Moved the `47`-county `2021–2023` monitor Design Value threshold reclassification waterfall (`18.39M` residents) and `19` vs. `2` same-rooftop annual DV sensitivity cleanly into SI Section S3 with explicit disclaimers distinguishing screening-level monitor DV cross-overs from EPA CAA § 107(d) designations, and archived observational EE flagging context with the explicit within-county-year null disclosure (`+0.81 pp, p_WCB = 0.931`) in SI Section S4 (removing any causal claim of instrument-induced EE filings).
3. **Reproducible Exports (`tables/`):** Exported `collocated_heavy_smoke_pairs_2023_2025.csv` (`673` site-days), `aqs_and_threshold_version_manifest.csv` (`19` pinned input files with SHA-256 digests), and `table1`–`table4` CSVs.
