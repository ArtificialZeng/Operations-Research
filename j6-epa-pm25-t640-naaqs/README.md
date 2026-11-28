# Residual Optical PM₂.₅ Bias During Wildfire Smoke and Sensitivity of U.S. Exceptional-Event Tiering Thresholds (`J6`)

**Status:** `v4` SUBMISSION-READY REVISION (*Environmental Science & Technology*) — `2026-11-28`  
**Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com; 1002266693@ucsiuniversity.edu.my`)

## Overview
This archive contains the complete, reproducible field-metrology pipeline evaluating residual post-alignment bias of Teledyne API Model T640/T640x optical PM₂.₅ monitors (AQS method codes `636/638`) relative to collocated gravimetric Federal Reference Method (`FRM`) samplers (with pure Met One `BAM 170/209` as background reference comparator) under EPA's April 2024 *PM₂.₅ Wildland Fire Exceptional Events Tiering Document* (`EPA-457/R-24-001`).

### Headline Verified Findings (`v4`)
- **Common-Support Audit (`P0 #1`):** Across `63,951` `T640_FW–FRM` pairs (`234` sites) and `22,927` `BAM–FRM` pairs (`107` sites) in `2023–2025`, the two queues share `401` all-day same-site, same-day triple observations (`5` sites) but only **`4` Heavy-smoke triples (`27` overlapping dates)**, with `23.9%` of BAM Heavy pairs in EPA Regions `9–10` where T640 has zero Heavy pairs. `BAM–FRM` is therefore demoted to a background reference comparator; restricting to common support widens the T640 − BAM Tier-1 differential (`+7.93 pp` overlapping regions, `+11.07 pp` overlapping dates & regions, `+10.42 pp` overlap-weighted `Region × FRM-bin`, bootstrap 95% CI `[+1.43, +18.80]`).
- **Official Retrospective & Out-of-Time Prospective EPA Tier-1 Replays (`P0 #2`):**
  - **Official EPA `2021–2025` Snapshot (`for_posting.csv`, query `2026-09-14`):** Across `468` matched `T640_FW–FRM` Heavy-smoke pairs (`165` sites), T640 triggers **`123` vs. `89`** Tier-1 crossings (`36` T640-only vs. `2` FRM-only; **`+7.26 pp`**, 95% CI `[+4.15, +10.38]` across `27` national blocks; **`[+3.43, +11.10]`, `p = 0.0004`** under two-way `Site × Region-Smoke-Episode` clustering across `55` regional episodes; yearly `+6.77`, `+6.41`, `+8.08 pp`; leave-one-EPA-region-out `[+6.33, +9.15] pp`). Within `±20%` of Tier-1 by FRM, `32` vs. `2` (`+42.25 pp`; `36/36` by midpoint). Background `BAM–FRM`: `84` vs. `84` (`5` vs. `5`, `+0.00 pp`).
  - **Strictly Out-of-Time Prospective Rolling 5-Year Replays (`2018–2022 → 2023`, `2019–2023 → 2024`, `2020–2024 → 2025`, May 1 certification calendar):** Unidirectional excess triggering across all four flag-exclusion specifications (`OOT-A` conservative `R`-excl: **`+5.57 pp`**, `26/0`, 2-way `[+2.77, +8.37]`; `OOT-B` excl. HMS Heavy: **`+6.21 pp`**, `29/0`, `[+3.08, +9.34]`; `OOT-B2` excl. HMS Med+Heavy: **`+7.07 pp`**, `33/0`, `[+3.57, +10.56]`; `OOT-C` pure FRM-only: **`+5.70 pp`**, `26/0`, `[+2.17, +9.23]`; all `p <= 0.002`; BAM null `+0.00` to `+0.52 pp`). Appendix N reconstruction achieves `0.000 µg/m³` median error on clean sites against EPA's official `2021–2025` table.
- **Equal-Concentration Non-Smoke Controls & Surface Smoke Confirmation (`P1 #3`):** Non-smoke elevated days (`15–25 µg/m³`, primarily winter inorganic haze) exhibit modest two-sided baseline sensitivity (`+3.09` to `+9.02 pp`), but Heavy smoke amplifies T640 bias 3–5× (`Other-Site ≥ 15`: `+0.64` vs. `+5.18 µg/m³`, `p = 3.44 × 10⁻¹³`, Tier-1 `+3.43` vs. `+16.46 pp`, `p = 0.004`; `FRM ≥ 25`: `-2.81` vs. `+7.98 µg/m³`, `p = 1.19 × 10⁻⁷`). Discordance concentrates in surface-confirmed plumes (`FRM > site-month p90`: `+10.12 pp`, `36/2`; `OC ≥ 5 µg/m³`: `+12.05 pp`, `11/1`) and vanishes on aloft plumes (`FRM ≤ p90`: `0.00 pp`, `0/0`).
- **Supporting Information (`supplementary_j6_est.pdf`, `P1 #4`):** Documents screening-level `2021–2023` monitor DV threshold reclassifications (`47` counties, `18.39M` residents; explicitly distinct from formal CAA § 107(d) designations), same-rooftop `19` vs. `2` 3-year DV sensitivity, and archival EE flagging diagnostics including the within-county-year null (`+0.81 pp, p_WCB = 0.931`).

## Key Deliverables & Reproduction
- **Main Manuscript:** `manuscript_j6_boost.pdf` (`12` pages, `0` leaked tokens) & `manuscript_j6_boost.md`
- **Supporting Information:** `supplementary_j6_est.pdf` (`4` pages, `0` leaked tokens) & `supplementary_j6_est.md`
- **Referee Response:** `REFEREE_RESPONSE_v4.md`
- **Reproducible Exports (`tables/`):** `collocated_heavy_smoke_pairs_2023_2025.csv` (`673` pairs), `aqs_and_threshold_version_manifest.csv` (`19` pinned artifacts), `table1`–`table4` CSVs
- **Verification:**
  ```powershell
  ruff check scripts/ tests/
  pytest -v tests/test_j6_boost.py
  ```
