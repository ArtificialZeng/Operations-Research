# MLIP Selective Soft-Mode Verification — Limited Diagnostic / Negative Allocation Archive

**Archive State:** `FROZEN_LIMITED_DIAGNOSTIC_NEGATIVE_ALLOCATION_ARCHIVE` (`STOP_STAGE1_EQUAL_BUDGET_GATE_FAILED`)  
**Scope:** Bounded Stage-0 mechanics smoke (`6` initial + `2` non-cubic crystals, strictly separated) and pre-locked Stage-1 label-blind grouped development pilot (`N = 36` Alexandria PBE crystals, `9` per crystal-system group) testing budgeted minimal-repeat Bloch Rayleigh rechecks under `mace-omat-0-small.model` (`float64`, `phonopy==4.11.0`, `NAC = False`, zero ML relaxation) against same-model commensurate Hessians and independent archived PBE DFT.

## Headline Verified Outcome (`PID 3568`, `111.768 s`, `N = 36`, `tau = 0.25 THz`)
- **Mechanics Parity:** Median `|f_Ray(h1=0.001) - f_MACE_full_proj| = 0.000008 THz` (`max = 0.000269 THz`) across all `36` crystals (`|cos - sin| <= 6e-6 THz` on non-self-conjugate `q`).
- **Coarse-Flagged Regime (`14/36`, all non-commensurate):** `6` same-model robust coarse false positives (`4` identity `[1,1,1]` + `2` non-identity coarse boxes across `3` crystal groups); `5` coarse false positives against independent archived PBE (separate count); `1` MACE and `3` DFT coarse misses; `15/36` crystals have residual force `max |F(0)| > 0.05 eV/Å`.
- **Why the Pre-Locked Equal-Budget Stage-1 Gate Failed:**
  - `Rayleigh_Only` has poor `NEG` recall (`4/9` vs. `MACE_full`, `4/11` vs. `DFT`; `DFT F1 = 0.5333` vs. `0.6667` unverified) because `4/10` Rayleigh-rejected crystals harbor rotated/hidden negative modes.
  - Conservative `Rayleigh_Gated_Full` nudged `50%` atom-eval decisive DFT accuracy `0.8438 -> 0.8750` due to 1 crystal with unchanged `8/11` recall, **tied at `50%` wall time** (`0.8438`) while **worse at `10%`/`25%` wall time**, **worse on force calls (`214` vs. `180` full)**, and saved only **`~11.2%` atom-force evaluations** (`17,656` vs. `19,874`) and **`~4.3%` recorded wall time** (`18.444 s` vs. `19.275 s`) at full coverage.
- **Close Priors Cited (No Priority/PDF/Media Claims):** `da Silva, Wang & Marques` (`https://arxiv.org/abs/2610.23545`), `Grandel, Benner & George` (*npj Comput. Mater.*, `10.1038/s41524-026-02338-w`), `PESCert` (`https://arxiv.org/abs/2610.00585`).

## Archived Files (`research/mlip_soft_mode_selective_validation/`)
- [`STAGE0_SMOKE_RECEIPT.md`](STAGE0_SMOKE_RECEIPT.md) — Separated Stage-0 smoke receipt (`6` initial + `2` non-cubic incl. `TiO2` hidden negative direction).
- [`STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md`](STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md) — Unmodified pre-locked Stage-1 protocol (`84e460a2...`).
- [`STAGE1_SELECTIVE_VALIDATION_RESULT.md`](STAGE1_SELECTIVE_VALIDATION_RESULT.md) — Complete Stage-1 negative allocation report, tables, and caveats.
- [`STATUS.md`](STATUS.md) — Frozen archive status ledger.
- [`LICENSES_AND_PROVENANCE.md`](LICENSES_AND_PROVENANCE.md) — Upstream licenses (`CC BY 4.0`, `CC BY`, `ASL` model exclusion, `MIT`/`BSD` tools) and excluded assets.
- [`MANIFEST.json`](MANIFEST.json) — Exact SHA-256 manifest of all archived files.
- [`requirements.lock.txt`](requirements.lock.txt) — Exact `Python 3.12.16` + `torch==2.11.0+cu128` + `mace-torch==0.3.17` + `phonopy==4.11.0` pins.
- [`stage0_verify_mechanics.py`](stage0_verify_mechanics.py), [`stage1_select_cohort.py`](stage1_select_cohort.py), [`run_stage1_selective_validation.py`](run_stage1_selective_validation.py) — Unmodified reproduction scripts.
- [`stage1_cohort_manifest.json`](stage1_cohort_manifest.json) — Locked 36-crystal label-blind cohort (`d3b965b6...`).
- [`stage0_smoke_outputs/stage0_mechanics_verification_receipt.json`](stage0_smoke_outputs/stage0_mechanics_verification_receipt.json), [`stage0_smoke_outputs/stage0_noncubic_mechanics_receipt.json`](stage0_smoke_outputs/stage0_noncubic_mechanics_receipt.json) — Unmodified Stage-0 numeric receipts.
- [`stage1_outputs/stage1_selective_validation_summary.json`](stage1_outputs/stage1_selective_validation_summary.json), [`stage1_outputs/stage1_per_material.jsonl`](stage1_outputs/stage1_per_material.jsonl) — Unmodified Stage-1 summary (`df60cc5d...`) and 36-crystal ledger (`8df67580...`).

## Reproduction Notes (Excluded Upstream Assets)
Official `ASL` model weights (`mace-omat-0-small.model`), raw reference YAML archives, `pbe.csv` catalog, copied literature, and `.venv` are **excluded** from git. To reproduce, install `requirements.lock.txt`, download `mace-omat-0-small.model` (`SHA-256`: `0abfde07862cf1e93b8b4d03cb702f29ce9c344ff2fc4de2ec0d7166d6c113a5`) under its Academic Software Licence into `models/`, and run `stage1_select_cohort.py` followed by `run_stage1_selective_validation.py`.
