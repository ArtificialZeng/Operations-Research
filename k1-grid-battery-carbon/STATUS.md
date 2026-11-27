# Status & Freeze Record — Flagship `#8 K1` (Counterfactual Carbon Accounting & Diurnal Gas-Peaker Displacement of U.S. Utility-Scale Battery Storage)

- **State:** `FROZEN_SUBMISSION_READY_V3` (*Nature Energy* Analysis Submission Polish)
- **Revision Timestamp:** `2026-11-27`
- **Workspace:** `D:\AI_Science\antigravity\k1_boost_grid_battery_carbon_20261127`
- **Manuscript PDF (`v3`):** `manuscript_k1_boost_v3.pdf` (`15` pages, `2,994,428` bytes, `SHA-256: ec8ce8b12fa560b0ec45edd2d7dc54da86e684a03a81bb63546abf8b70142f2c`) *(Note: local `manuscript_k1_boost.pdf` was open/locked in an external viewer during compilation; Draft PR #29 contains the fresh `v3` PDF bytes synced to both `manuscript_k1_boost.pdf` and `manuscript_k1_boost_v3.pdf`.)*
- **Referee Response Records:** `REFEREE_RESPONSE_v2.md`, `REFEREE_RESPONSE_v3.md`
- **Independent Verification (`v3`):**
  - `ruff check scripts/ tests/`: `0` errors (`All checks passed!`)
  - `pytest -v tests/test_k1_boost.py`: `23/23` passed (`100%`)
  - `SHA256SUMS.json`: `32/32` disk-verified (`0` missing, `0` mismatches)
  - Crossref Live Citations: `18/18` academic DOIs HTTP-200 verified (`100%` two-way sync)
  - PDF Zero-Leak & Tone Guardrail Audit: `0` formatting leaks, `0` occurrences of `"carbon neutral"`, `"carbon neutrality"`, `"pure exogenous"`, `"spotless"`, `"proving rigorously"`, `"extraordinary"`, `"master forensic audit"`, or `"definitively"`
- **Submission Polish (`v3`) Scientific & Statistical Enhancements:**
  - Added `B = 1,000` joint contiguous moving-block bootstraps at `1d`, `7d`, and `14d` block lengths (`scripts/03_cems_carbon_and_caiso_curtailment.py`): CAISO Main System `-0.80 kg/MWh` (`14d 95% CI [-14.20, +12.58], SE = 6.85, p = 0.920`; `7d [-13.24, +9.83]`; `1d [-10.39, +8.15]`) vs. Observed-Load `ΔLoad` System `+1.34 kg/MWh` (`14d 95% CI [-21.86, +30.51], SE = 13.78, p = 0.764`), while domestic-only remains strictly negative across all block lengths (`-30.64`, `14d [-42.78, -17.48]`)
  - Unified all prose, captions, and Figure 4B to state **"accounting for cross-region imports, California's net emissions direction remains undetermined"** (removing neutrality-confirmation and `ΔLoad`-exogeneity assertions) and strictly keeping `+7.44 Mt CO2` as the counterfactual accounting discrepancy between two models
  - Centered Title, Abstract, and Section 1 squarely on the 14-BA counterfactual accounting comparison for *Nature Energy* (Analysis), added **Table 4b** (14-BA curtailment-absorption sensitivity: uniform break-even `18.9%`; hybrid empirical-CAISO + `0–15%` non-CAISO leaves `+5.59` to `+4.04 Mt CO2` discrepancy vs. AEF), added the **CAISO Congestion-Constrained Incremental Storage Saturation Frontier** (`κ = 0.25×/1.0×/2.0×`: `40.3%/18.2%/10.1%` total vs. `5.3%/2.8%/1.6%` system-only), and transparently disclosed marginal Table 3 WCB `p`-values (`0.075–0.130`) in Section 4.2 prose
