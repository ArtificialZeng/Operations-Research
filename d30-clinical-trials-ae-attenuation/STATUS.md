# STATUS — D30 (`v4` Submission-Ready Archive)

- **Revision:** `v4` (*Journal of Clinical Epidemiology* — Clinical-Trials Methodology)
- **Author:** Zijian Zeng, Institute of Computer Science and Digital Innovation, UCSI University, Kuala Lumpur, 56000, MALAYSIA (`zijianzeng@foxmail.com`; `1002266693@ucsiuniversity.edu.my`)
- **Primary Deliverables:**
  - Main Manuscript: `manuscript_d30_boost.md` / `manuscript_d30_boost.pdf` (4 main figures, 5 main tables, strictly scaled per `+10 pp` EU-East site share over observed `[0%, 35%]` support)
  - Supplementary Appendix: `supplementary_d30_jce.md` / `supplementary_d30_jce.pdf` (Appendices S1–S5, 4 supplementary figures, 6 supplementary tables)
  - Point-by-Point Referee Response: `REFEREE_RESPONSE_v4.md`
  - Frozen Verbatim MedDRA API Snapshot: `data/raw_ctgov/meddra_other_events_snapshot.jsonl.gz` (`2,771/2,771` trials, `SHA-256` `7eb1eefdeae3b188f262bd180b04dc568d808e6eee74b09883b94a27a4ee9b1e`) + `data/raw_ctgov/meddra_snapshot_manifest.json`
  - Machine-Readable Receipts: `results/d30_econometrics_results.json`, `results/08_reporting_sensitivity.json`, `results/d30_gate2_openfda_results.json`, `SHA256SUMS.json`, `VERIFICATION_MANIFEST.md`
- **Verification Gate:** All automated unit, panel, econometric, MedDRA four-state/Manski, TOST, PDF-leak, and SHA-256 manifest checks pass (`pytest -v` 100% pass; `ruff check` 0 errors; zero rank-deficient models; zero NaNs across all 11 CSV tables).
