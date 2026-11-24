# Licenses, Public Source Pins & Archival Exclusions

## 1. Official Public Data Sources & Elexon Licence (Auth-Free, No Key, No Account)

All empirical data were retrieved directly from Elexon's official public Insights Solution (BMRS) API v1:
- **API Base:** `https://data.elexon.co.uk/bmrs/api/v1`
  - Forecast vintages: `GET /datasets/WINDFOR/stream?publishDateTimeFrom=...&publishDateTimeTo=...` (cross-checked against `GET /forecast/generation/wind/evolution?startTime=...&format=json`)
  - Metered outturns: `GET /datasets/FUELHH/stream?settlementDateFrom=...&settlementDateTo=...&fuelType=WIND`
- **Official Dataset Documentation Pages:**
  - Wind Generation (`WINDFOR` vs. `Generation by Fuel Type`): `https://bmrs.elexon.co.uk/wind-generation`
  - Generation by Fuel Type (`FUELHH` / `FUELINST`, 30-minute average operational metering, excluding unmetered embedded wind): `https://bmrs.elexon.co.uk/generation-by-fuel-type`
- **Data Licence & Mandatory Attribution:**
  - Elexon BMRS / BSC Open Data Licence (`https://www.elexon.co.uk/data/balancing-mechanism-reporting-agent/copyright-licence-bmrs-data/` and BSC Open Data Licence under BSC Modification P398; worldwide, royalty-free, perpetual, non-exclusive right to copy, publish, distribute, and adapt Open BMRS / BSC data with attribution):
  - **Required Attribution:**
    > *Contains BMRS data © Elexon Limited copyright and database right 2026.*  
    > *Contains BSC information licensed under the BSC Open Data Licence.*
  - Under this open licence with attribution, this archive includes ONLY bounded metadata/hash receipts (`STAGE0_DATA_FEASIBILITY_RECEIPT.json`, `STAGE0_DEV_DATA_AUDIT.json`) and bounded derived summary/per-day scoring outputs (`dev_pilot_summary.json`, `dev_pilot_per_day_predictions.jsonl`), while **excluding all ~44 MB of raw `WINDFOR`/`FUELHH` stream chunks and raw single-date receipt payloads**.

## 2. Literature Citations (Copied Paper Texts Kept Local-Only, NOT Redistributed)
- **EnergyBench:** Genov, Alonso & Bergmeir (2026), `https://arxiv.org/abs/2611.07784`
- **Kolkmann et al. (2024):** *Energy Economics* 139:107890, `https://www.sciencedirect.com/science/article/pii/S014098832400598X`
- **Meng et al.:** *Meteorological Applications*, `https://doi.org/10.1002/met.70203`
- **Marchal, Bouttier & Nuissier (2025):** *Natural Hazards and Earth System Sciences*, 25:2613–2628, `https://nhess.copernicus.org/articles/25/2613/2025/#section5`

## 3. Explicit Archival Exclusions (Not Pushed to GitHub)
- `raw_dev_chunks/` (~44 MB of raw Elexon JSON stream chunks; exact per-chunk URLs and SHA-256 hashes are sealed inside `STAGE0_DEV_DATA_AUDIT.json` and `MANIFEST.json`)
- `raw_receipts/` (raw Elexon single-date JSON receipts; exact URLs and SHA-256 hashes are sealed inside `STAGE0_DATA_FEASIBILITY_RECEIPT.json` and `MANIFEST.json`)
- `literature_notes/` (local text extracts of third-party papers)
- `.venv/`, `__pycache__/`, credentials, caches, local steering notes, and unrelated files.
