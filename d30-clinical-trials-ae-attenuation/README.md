# Geographic Site Mix and Registered Non-Serious Adverse Events in Multiregional Drug Trials (`D30`, `v4`)

**Author:** Zijian Zeng — Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)

Reproducible clinical-trials methodology archive evaluating within-program associations between regional site composition and registered non-serious adverse-event (AE) proportions across `2,771` completed placebo-controlled multiregional clinical trials (`1,842` Phase 3) from ClinicalTrials.gov v2, alongside extensive/intensive support diagnostics, four-state MedDRA threshold-censoring Manski bounds, AE time-frame audits, and pre-specified clinical equivalence (TOST) tests.

## Core Empirical Summary (Scaled Strictly per `+10 pp` Eastern European EU Site Share)

- **Within-Program Association & Two-Way Counterfactuals:** In Phase 3 `drug × sponsor` fixed-effects models (`N = 1,282`, `328` programs, `129` sponsor clusters), each `+10 pp` higher Eastern European EU site share (replacing U.S. sites) is associated with **`-2.48 pp`** (`95% CI [-3.61, -1.35]`, `p = 2.88e-5`) in placebo arms and **`-2.67 pp`** (`95% CI [-3.80, -1.54]`, `p = 7.47e-6`) in active arms (`p_WCB = 0.001 / 0.001`). Two-way counterfactual contrasts replacing North America (`-2.68 / -2.92 pp`), Western Europe EU/EEA (`-2.39 / -2.83 pp`), Latin America (`-3.02 / -3.41 pp`), and Emerging Asia (`-2.69 / -2.71 pp`) are consistent (`all p < 0.001`).
- **Support, Extensive vs. Intensive Margin, Splines & Effective Weights:** Among `1,842` Phase 3 trials, `504` (`27.36%`) have `0%` EU-East sites and `25` (`1.36%`) have `>= 50%` (median `8.45%`, 95th percentile `35.29%`). Across `[0%, 35%]` (`N = 1,211`, `310` programs), adding `I(share = 0)` yields positive-share slopes of `-2.11 pp [-4.24, +0.02]` (placebo, `p = 0.052`) and `-2.50 pp [-4.64, -0.36]` (active, `p = 0.022`) with non-significant zero-share intercepts (`p >= 0.495`); restricting strictly to positive `(0, 35%]` (`N = 870`, `236` programs) attenuates slopes to `-1.14 / -1.84 pp` (95% CIs crossing zero). Restricted cubic splines show no nonlinearity (`Wald p = 0.548 / 0.681`), and dropping the top-10 (`32.0%` FWL weight) or top-20 (`47.5%` weight) weighted programs yields `-2.51 / -2.67 pp` and `-2.67 / -2.84 pp`.
- **MedDRA Four-State Audit, Sharp Manski Bounds & AE Time Frames:** Verbatim per-term `otherEvents.stats` snapshot archived for `2,771/2,771` trials (`data/raw_ctgov/meddra_other_events_snapshot.jsonl.gz`, `SHA-256` `7eb1eefdeae3b188...`). Removing silent denominator fallbacks (`278` anomalous denominator cells, `69` missing-count cells across `210,424` reported cells) preserves paired `Subj − Obj` (`-0.0660 / -0.0743`, `p <= 5.10e-4`) and `Subj − Investigations` (`-0.0774 / -0.0847`, `p <= 8.69e-4`) contrasts. Sharp Manski FWL bounds on peak single-term rates (`72%–88%` point-identified) exclude zero (`Imbens–Manski 95% CI [-1.69, -0.17] pp` placebo, `[-1.79, -0.39] pp` active), whereas 15-term sums lose point identification under `5%` left-censoring (`69.04%` of cells). Documenting the `369/2,771` (`13.32%`) trials missing structured AE `timeFrame` and restricting to documented-`timeFrame` trials preserves `-2.33 / -2.50 pp` in Phase 3 (`N = 1,110`).
- **Pre-Specified TOST Equivalence:** SAEs (`+0.06 / +0.15 pp`) and within-trial RD (`-0.19 pp`) establish formal TOST equivalence at `±2.0 pp` and `±1.0 pp` (`all p_TOST <= 0.0032`), whereas all-cause mortality (`N = 679`, `+0.18 / +0.36 pp`) fails equivalence at `±0.5 pp` (`p_TOST = 0.249 / 0.370`).
- **Supplementary Appendix (`supplementary_d30_jce.pdf`):** Extended sensitivities & accrual bounds (`S1`), overlapping 2017 temporal patterns (`S2`), uncensored `2017–2025` all-registered war footprints (`N = 20,649` / `6,011` MRCTs; `S3`), exploratory openFDA/FAERS audit (`N = 229` drugs; `S4`), and EMA Policy 0070 CSR validation schema & snapshot provenance (`S5`).

## Verification & Reproduction

```powershell
# Verify all receipts, tests, code style, and SHA-256 manifest
.venv\Scripts\pytest.exe -v tests\test_d30_pipeline.py
.venv\Scripts\ruff.exe check --select E,F,I,W,B --ignore E501 scripts tests
```

Full deterministic replay from archived raw snapshots:
```powershell
.venv\Scripts\python.exe scripts\02_build_panel.py
.venv\Scripts\python.exe scripts\02b_fetch_meddra_soc_stats.py
.venv\Scripts\python.exe scripts\03_econometrics_suite.py
.venv\Scripts\python.exe scripts\08_reporting_sensitivity.py
.venv\Scripts\python.exe scripts\05_generate_figures_tables.py
.venv\Scripts\python.exe scripts\07_compile_manuscript_pdf.py
.venv\Scripts\python.exe scripts\06_build_manifest.py
```
