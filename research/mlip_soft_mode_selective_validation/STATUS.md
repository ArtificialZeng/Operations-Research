# Status Ledger — MLIP Selective Soft-Mode Verification (FROZEN LIMITED DIAGNOSTIC / NEGATIVE ARCHIVE)

- **State:** **`FROZEN_LIMITED_DIAGNOSTIC_NEGATIVE_ALLOCATION_ARCHIVE`** (`STOP_STAGE1_EQUAL_BUDGET_GATE_FAILED`)
- **Date Sealed:** 2026-11-24
- **Target Archive Path:** `research/mlip_soft_mode_selective_validation/`

## Verified Receipts & Immutable Checksums
- **Model Pin (Excluded Under ASL):** `mace-omat-0-small.model` (`67,630,500 B`, `SHA-256`: `0abfde07862cf1e93b8b4d03cb702f29ce9c344ff2fc4de2ec0d7166d6c113a5`, CUDA `float64` on RTX 5060, `torch==2.11.0+cu128`, `mace-torch==0.3.17`, `phonopy==4.11.0`)
- **Stage-0 Separated Smoke (`6` initial + `2` non-cubic incl. `TiO2` hidden negative direction):**
  - `stage0_mechanics_verification_receipt.json`: `7b367ec9e3152c1288f75da4694eb6c268f39fe3606c7348b52aadb937d5f2d9`
  - `stage0_noncubic_mechanics_receipt.json`: `00fc56c449ed00c88eae81abbc3ed425520d788089f388ca7bc0a33894f76b65`
- **Stage-1 Pre-Locked Protocol (`STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md`):** `84e460a2ed71e1be9f49a1ff86c01196a6fa088a92700bc3d39bf7ce349af002`
- **Stage-1 Label-Blind 36-Crystal Manifest (`stage1_cohort_manifest.json`):** `d3b965b6cb8034e1462fec3fa35ef2783e20ee2151188eb749b4f80333310a0a`
- **Stage-1 Runner (`run_stage1_selective_validation.py`):** `b3b63f6de9a844dff18443d266c3f6eb5d62298d9b6ce53b369364fb303251cb`
- **Stage-1 Native Execution:** `PID 3568`, wall `111.768 s`, exit code `0`
- **Stage-1 Summary JSON (`stage1_outputs/stage1_selective_validation_summary.json`):** `df60cc5daaabadbe241997aaeebf07aaba50f5969f45345fb176a83846587429`
- **Stage-1 Per-Material Ledger (`stage1_outputs/stage1_per_material.jsonl`):** `8df67580ab5b83bf39a4652a2342903b0fbaa2c4e147c6b2f857d69e68fc3a64`

## Key Stage-1 Outcomes (`N = 36`, `9`/group, `tau = 0.25 THz`)
- **Directional Parity:** Median `0.000008 THz` / max `0.000269 THz` vs. full commensurate same-model Hessian (`|cos - sin| <= 6e-6 THz`).
- **Separate FP/Miss Counts:** `14` coarse flags; `6` same-model robust coarse FPs (`4` identity `[1,1,1]`, `2` non-identity; `3` crystal groups); `5` coarse FPs against independent archived PBE (separate count); `1` MACE and `3` DFT coarse misses; `15/36` residual forces `> 0.05 eV/Å`.
- **Gate Failed:** `50%` atom-eval decisive DFT accuracy `0.8438 -> 0.8750` (1 crystal, recall unchanged `8/11`); `50%` wall-time tied (`0.8438`), earlier wall tiers worse (`10%`/`25%`); force calls worse (`214` vs. `180` full); full coverage saves only `~11.2%` atom-evals and `~4.3%` wall time. `Rayleigh_Only` has poor `NEG` recall (`4/9` MACE, `4/11` DFT).
- **Guardrails & Priors:** Cites `da Silva et al.` (`2610.23545`), `Grandel et al.` (`10.1038/s41524-026-02338-w`), `PESCert` (`2610.00585`). Intended dev sample, no training OOD claim, same-geometry archived periodic PBE/`NAC=False` grid (not arbitrary-`q` or physical stability). No tuning, no weights/raw YAMLs/literature/venvs/desktop-steering in archive, no PDF/media/priority claims; `main` (`940709d3...`) and PRs `#13–#20` untouched.
