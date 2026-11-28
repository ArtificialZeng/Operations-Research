# D4 (`v4`): Equal-Budget Monitoring Protocols for Nocturnal River Hypoxia Across U.S. and English Networks

**Author:** Zijian Zeng — Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)  
**Revision:** `v4` *Nature Water* Submission-Ready Revision (strictly addressing every item in `D4.md`; see `REFEREE_RESPONSE_v4.md`)  
**Deliverables:** Reproducible raw UTC USGS STAC + UK Environment Agency + U.S. Water Quality Portal (WQP) discrete grab-log pipeline (`scripts/00`–`14`), 4 *Nature Water* main figures (`350 DPI PNG` + vector `PDF`), 7 new zero-NaN Main/Supplementary CSV tables (plus 9 archived daily-extremes CSVs), compiled zero-leak Main Manuscript (`manuscript_d4_boost.pdf` & `manuscript_d4_nature_water.pdf`) and separate Supplementary Information (`supplementary_d4_nature_water.pdf`), automated `pytest` suite (`100%` passing), `0` `ruff` errors, and cryptographic manifest (`SHA256SUMS.json`).

---

## Core Findings at a Glance (`v4`)

- **Real-World Agency Sampling Clock & Co-Located Field-Meter Validation (`scripts/10_fetch_wqp_grab_logs.py`):**
  - Across **`10,019` timestamped warm-season U.S. WQP discrete DO agency visits** (`205` screened rivers, 2015–2024; `1,391` visits on `76` of our `139` subdaily rivers, 2021–2024), agency sampling peaks near **11:00 local civil time (`09:50` solar; IQR `09:30–12:40` civil)** with `92.9%` in `08:00–17:00` and only **`0.51%`** in the 2 h before sunrise.
  - Across **`1,287` paired independent field-meter vs. continuous USGS sonde readings (`|Δt| ≤ 30 min`, median `0.0 min`, `76` sites)**, continuous probes match independent field meters with **Pearson `r = 0.961`**, bias `-0.027 mg/L`, and median absolute error **`0.20 mg/L`** (USGS Wagner et al. 2006 tolerance). On `1,112` matched agency visit days, actual field visits missed **`61.0%`** (`50/82`) of LORO `<5 mg/L` nights and **`57.7%`** (`41/71`) of `≥2 h` actionable episodes (vs. `93.0%` detected pre-dawn).
- **Primary Leave-One-Reading-Out (`LORO`) Cross-Network Validation (`scripts/11_loro_and_sensitivity_analysis.py`):**
  - Raw UTC common-support panels: **`87,785` U.S. site-nights** (`139` USGS STAC stations, `93.8%` entry rate) and **`27,635` English site-nights** (`65` EA stations, `82.2%` entry rate).
  - Removing the candidate pre-dawn reading drops `37 / 8,499` U.S. (to `8,462`) and `112 / 2,472` English (to `2,360`) `<5 mg/L` reference positives, preserving LORO pre-dawn gains over `14:30` of **`+49.47 pp [+36.87, +62.07]`** (U.S.) and **`+35.13 pp [+22.69, +47.57]`** (England) with transparent LORO reference-negative alarm rates of **`0.047%`** and **`0.443%`**.
  - Robust across `±30 min` LORO exclusion (`+49.63` / `+34.77 pp`), persistence (`≥2` readings / `≥2 h`: `+51.54`–`+53.58` / `+34.98`–`+38.09 pp`), `±0.2 mg/L` sensor tolerance & independent MC probe noise (`+46.55` / `+33.29 pp`), `15/30/60 min` downsampling (`+50.88`–`+51.97 pp` U.S., proving England's higher alarm rate is a cadence artifact), equal-site weighting (`+46.26` / `+30.47 pp`), chronic-site exclusion (`+57.04` / `+37.83 pp`), and out-of-sample LOO-Region, 5-Fold Site, and Cross-Atlantic transfer (`+50.56` / `+36.03 pp`).
  - **First-Light Daylight Plateau:** Out-of-sample optimization independently selects geometric sunrise (`SR + 0 min`: `84.46%` U.S., `80.02%` England), and safe civil daylight (`SR + 30 min`) retains `83.85%` (U.S.) / `78.80%` (England) LORO recall (`89.8%` / `85.3%` on `≥2 h` actionable episodes).
- **Censoring Diagnosis & Episodic Lead Time:**
  - Only `14.7%` (`1,246 / 8,499` U.S.) and `15.3%` (`378 / 2,472` England) of `<5 mg/L` nights close at both ends inside darkness; `80.1%` (U.S.) and `76.7%` (England) remain hypoxic past sunrise. Unbroken continuous-series medians are **`13.5 h`** (U.S.) and **`13.0 h`** (England), compared to severely biased closed-in-night medians (`1.0–2.0 h`).
  - On episodic `2–24 h` events, pre-dawn/first-light grabs arrive near/after nadir (`-1.18` to `+0.50 h`), whereas **telemetered continuous sondes provide `+4.5 h` (U.S.) and `+3.5 h` (England) pre-nadir warning (`94.2%–95.8%` pre-nadir)**.
- **Equal-Budget Operational Protocol & Cost-Effectiveness Frontier (`scripts/12_operational_protocol_decision_analysis.py`):**
  - Under realistic nocturnal two-person safety surcharges (`m_night = 1.75×`, budget `24` day-eq/site-yr = `\$4,800/site-yr`, `K_sonde = 40`), **dark pre-dawn grabs underperform the existing empirical WQP clock** on distinct non-overlapping episodes per dollar (breakeven `m* = 1.53×` U.S., `1.38×` England).
  - **First-light daylight grabs (`SR + 30 min`, `1.15×`) dominate all grab-only protocols** (`2.56` U.S. / `2.06` England distinct ep/100 eq; `\$7,813` / `\$9,729` per episode; `55.2%` / `54.2%` impaired site-years flagged).
  - **Risk-stratified continuous sondes (top-20% sites via strictly out-of-sample Year-1 daytime screening) + first-light grabs elsewhere dominate the entire frontier under the identical budget:** **`6.71` (U.S.) / `7.11` (England) distinct episodes/100 eq (`3.5×–4.7×` WQP; `72%–79%` unit cost cut to `\$2,980` / `\$2,812`/episode)** and **`63.8%` / `60.6%`** impaired site-years flagged.

---

## Reproducible Pipeline Execution Order

Run inside `.venv`:
```powershell
.venv\Scripts\python.exe scripts\09_fetch_usgs_stac.py
.venv\Scripts\python.exe scripts\10_fetch_wqp_grab_logs.py
.venv\Scripts\python.exe scripts\11_loro_and_sensitivity_analysis.py
.venv\Scripts\python.exe scripts\12_operational_protocol_decision_analysis.py
.venv\Scripts\python.exe scripts\13_generate_v4_figures_tables.py
.venv\Scripts\python.exe scripts\14_generate_v4_manuscript_and_supplement.py
.venv\Scripts\python.exe scripts\08_compile_manuscript_pdf.py
.venv\Scripts\python.exe scripts\07_build_manifest.py
.venv\Scripts\pytest.exe -v tests\test_d4_pipeline.py
.venv\Scripts\ruff.exe check scripts tests
```
