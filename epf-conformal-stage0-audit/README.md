# EPF Conformal & Information-Boundary Stage 0 Closure Audit (`epf-conformal-stage0-audit`)

Standalone, formally **closed Stage 0** literature-frontier and information-boundary audit for a prospective online conformal / isotonic day-ahead electricity price forecasting proposal.

**Status:** **Formally Closed at Stage 0B (2026-11-24).**  
**Zero real electricity price outcomes were fitted, ranked, or archived.** No raw datasets, no real price series, no model-author/score-bearing samples, no long copied abstracts/README excerpts, and no PDFs are included.

---

## Why Closed at Stage 0 (No Renaming of Overlapping Ideas)

1. **Pre-Gate Information Boundary, Resolution & Support Limits:**
   - Official Bundesnetzagentur SMARD documentation (`https://www.smard.de/home/neu-prognostizierte-pv-und-windenergieeinspeisung-208702`) states next-day PV/wind generation forecasts are submitted by **`18.00 Uhr`** (6 hours after the `12:00` CET SDAC day-ahead auction gate). Present-day HTTP availability does not certify historical publication timing, and EU Reg 543/2013 Art. 6 does not certify stored SMARD load vintages.
   - Foretec EnergyBench (`ujohn33/foretec-energy-bench`, DOI `10.57967/hf/11052`) freezes pre-`11:30` CET inputs across `39` models (`6` zones, `60,480` actuals rows), split into **`17` live issue days (`2026-10-02`–`2026-10-18`)** and **`18` separate backtest issue days (`2026-09-14`–`2026-10-01`)**. Seventeen live issue days are smoke-sized and cannot support ranking. Per NEMO/SDAC schedule, 15-minute MTU delivery began `2025-10-01`, preventing unmapped historical hourly aggregates from entering a 15-minute live board.
   - Legacy `epftoolbox` (`Zenodo 4624805`, `5` markets × `52,416` hourly rows = `2,184` **nominal** 24-hour days/market, `730` **nominal** 24-hour holdout days/market) ends in `2016–2018`, lacks archival pre-gate vintage certification on historical TSO forecast columns, and represents serially dependent daily vectors rather than independent observations.
2. **Directly Overlapping 2022–2026 Primary Literature (12 Audited Works):**
   - **Brusaferri et al.** (*Applied Energy* 2025, `DOI: 10.1016/j.apenergy.2025.126412`, `https://github.com/bruale/PefCodeBench`): online conformal recalibration of day-ahead electricity price distributions (DE+IT), improved hourly coverage and stable proper scores.
   - **Ding, Gibbs & Tibshirani** (`MultiQT`, `arXiv:2512.23671v2`): monotone multi-quantile online calibration under delayed feedback, bounded outcomes, and energy forecasting.
   - **Li, Menacho & Rodríguez** (`O2CP`, `arXiv:2508.13362v3`): joint multi-horizon online interval optimization under coverage preservation.
   - **He et al.** (*Processes* 2026, `DOI: 10.3390/pr14193119`): batched group feedback in renewable energy forecasting.
   - **Agrawal & O'Sullivan** (`arXiv:2611.03661v1`), **Lipiecki, Uniejewski & Weron** (*Energy Economics* 2024, `arXiv:2404.02270v2`), **Lipiecki & Uniejewski** (`arXiv:2507.15079v2`), **Wu et al.** (*ACM e-Energy* 2026, `DOI: 10.1145/3744255.3798116`), **Hoxha et al.** (`DOI: 10.2139/ssrn.6731093`), **Bastani et al.** (NeurIPS 2022, `arXiv:2206.01067v1`), **Angelopoulos et al.** (NeurIPS 2023, `arXiv:2307.16895v1`), **Gibbs & Candès** (JMLR 2024, `arXiv:2208.08401v3`).
3. **Methodological Precision:** Marginal CRPS requires a valid marginal forecast distribution (monotonic/non-crossing quantiles); cross-hour dependence is separately needed for joint multi-hour dispatch scenarios. Standard ACI does not guarantee per-hour or conditional coverage.

---

## Metadata-Only Projection Notice & Integrity Verification

To avoid republishing third-party copied text or score/model metadata, the staged `audit/stage0b_frontier_and_boundary_audit.json` is a documented **metadata-only projection** of the original local Stage 0B audit (stripping copied arXiv `summary_snippet` abstracts, copied EnergyBench `hf_readme_excerpt`, `hf_card_data`, `hf_tags`, model/family listings, and score-table column lists while preserving all provenance URLs, DOIs/arXiv IDs, short titles/dates, exact split counts, and the SMARD `18.00 Uhr` deadline finding). Exact projection details and digests are recorded in `ARCHIVE_MANIFEST.json`.

Verify exact archived bytes:
```bash
python3 -c '
import hashlib, json, pathlib
m = json.loads(pathlib.Path("ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
for e in m["files"]:
    raw = pathlib.Path(e["path"]).read_bytes()
    assert len(raw) == e["bytes"] and hashlib.sha256(raw).hexdigest() == e["sha256"], e["path"]
print(f"Verified {len(m["files"])} allowlisted files successfully.")
'
```
