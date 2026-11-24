# Licenses, Provenance & Exclusions — MLIP Selective Soft-Mode Validation Archive

## 1. Upstream Public Sources & Licenses
- **Alexandria PBE Phonon Benchmark (Numeric Derived Summaries Archived Under CC BY 4.0; Raw YAMLs & Catalog Excluded):**
  - Source URL: `https://alexandria.icams.rub.de/data/phonon_benchmark/pbe/`
  - License: **Creative Commons Attribution 4.0 International (`CC BY 4.0`)** — `https://creativecommons.org/licenses/by/4.0/`
  - Attribution: Alexandria Materials Database (ICAMS, Ruhr University Bochum). Exact per-file SHA-256s for all `36` Stage-1 `.yaml.bz2` crystals are recorded in `stage1_cohort_manifest.json`.
- **NIMS MDR PBEsol Smoke Controls (Stage-0 Pipeline Smoke Only; Raw `.yaml.xz` Excluded):**
  - `Si mp-149` (`1,472 B`, MD5 `f805da3aab84b22d96bdd610ae41bc10`, `https://mdr.nims.go.jp/filesets/d7366223-c1b4-4047-aca3-bb65855dfdbb/download`)
  - `BaTiO3 mp-2998` (`3,400 B`, MD5 `1c9f4c01cbe2ba2f9ec9220765721d9a`, `https://mdr.nims.go.jp/filesets/22d46eb7-bd11-4db0-9e6a-d4aa3e0ca2c7/download`)
  - License: **CC BY** (NIMS Materials Data Repository; `doi:10.48505/nims.4197`). Kept strictly separate from PBE paired labels.
- **MACE Foundation Model Weights (Strictly Excluded from Git Archive):**
  - Release: `https://github.com/ACEsuit/mace-foundations/releases/download/mace_omat_0/mace-omat-0-small.model`
  - Size & SHA-256: `67,630,500 B`, `0abfde07862cf1e93b8b4d03cb702f29ce9c344ff2fc4de2ec0d7166d6c113a5`
  - License: **Academic Software Licence (`ASL`)** (academic non-commercial use only; not redistributed here).
- **Software Dependencies:** Pinned in `requirements.lock.txt` (`phonopy==4.11.0` BSD-3-Clause, `ase==3.29.0` LGPL-2.1+, `mace-torch==0.3.17` MIT, `torch==2.11.0+cu128` BSD-3-Clause, `spglib==2.8.0` BSD-3-Clause).

## 2. Explicit Archive Exclusions
The following files and directories are strictly **excluded** from the archive branch:
- Official `ASL` model weights (`models/mace-omat-0-small.model`, `*.model`, `*.pt`).
- Raw reference YAML files, archives, and catalogs (`raw_smoke_refs/`, `raw_stage1_pbe/`, `*.yaml.xz`, `*.yaml.bz2`, `*.csv`).
- Copied literature, virtual environments (`.venv/`, `__pycache__/`), secrets, desktop steering notes (`desktop_*.txt`), local PR handoff helper notes, PDFs, and unrelated changes.
