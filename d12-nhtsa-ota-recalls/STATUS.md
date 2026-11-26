# Project Status — D12 Boost (NHTSA Software-Defined Vehicle OTA Recalls — `v2` Major Revision)

- **Status:** `v2 MAJOR REVISION COMPLETE — REFEREE-HARDENED & VERIFIED`
- **Last Verified (UTC):** `2026-11-27`
- **Workspace:** `D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125`
- **Isolated Environment:** `.venv` (Python 3.15.2)

## `v2` Referee-Driven Verification Checklist

- [x] **Public NHTSA Campaign API Metadata Anomaly Reframing:** Documented May 8, 2025 (`25V282000`, 36/36 `True`) vs. May 9, 2025 (`25V315000`, 44/44 `False`) public API flag drop (`0/68` post-May 8) reconciled explicitly against NHTSA's *2025 Annual Recalls Report* (March 2026; 33 OTA recalls tallied internally).
- [x] **Unidentified `85–90%` Selection-Share Claim Permanently Removed:** Eliminated `implied_endogenous_selection_gap` and zero-clipped ITT subtraction across `scripts/04_econometric_core_analysis.py`, `d12_econometric_results.json`, tables, figures, and manuscript; conditional campaign-size differentials (`Hybrid-OTA +1.947, p_WCB=0.006`) and unconditional OEM-level first-OTA ITT (`Sun–Abraham IW -0.532, p_t=0.470`) are reported transparently as distinct estimands.
- [x] **Transparent Recall-Level Proxy, Tesla `98.7%` Weight Disclosure, & Exact `p_WCB`:** Added dedicated mature OEM composition audit (`tables/table4c_mature_ota_oem_composition.csv` & Manuscript Table 4B confirming Tesla = `98.7%` of mature Pure-OTA affected vehicle-instances; Non-Tesla `N=19` = `1.3%`, `99.11%` mean CR); prominently reported exact `p_WCB` (`0.065`, `0.055`, `0.401`, `0.097`, plus reparameterized Hybrid-minus-Pure contrasts `0.007` all-veh / `0.079` SW-only) across Abstract, Tables, Figures, and Text; standardized **49 CFR § 573.7** recall-level vehicle-instance proxy terminology throughout.
- [x] **Primary Empirical Anchor Hardened (Vehicle-Age Compliance Decay):** Added non-Tesla (`Any OTA × Age +2.37 pp/yr, p_WCB=0.030`; `API OTA × Age +1.96 pp/yr, p_WCB=0.023`) and light-duty passenger (`Pure-OTA × Age +3.22, p_WCB=0.032`; `Hybrid-OTA × Age +2.36, p_WCB=0.007`) sensitivity regressions in `scripts/04_econometric_core_analysis.py` and Table 3.
- [x] **References, Figures, PDF, Tests, Manifest & Referee Response:** 22/22 Crossref-verified peer-reviewed DOIs + 2 federal institutional citations (`NHTSA 2026`, `49 CFR § 573.7`), 9 zero-NaN CSV tables, 5 visually inspected figures, visually inspected zero-leak PDF, `ruff check` = 0 errors, expanded `pytest` = 100% pass, regenerated `SHA256SUMS.json`, and `REFEREE_RESPONSE_v2.md`.
