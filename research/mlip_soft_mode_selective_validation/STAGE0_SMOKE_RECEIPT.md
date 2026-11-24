# Stage-0 Pipeline & Mechanics Verification Receipt — MLIP Selective Soft-Mode Validation

**Date Verified:** 2026-11-24  
**Archive Path:** `research/mlip_soft_mode_selective_validation/`  
**Scope Notice:** **Stage-0 smoke results (`6` initial cubic crystals + `2` non-cubic crystals = `8` exploratory smoke structures) are strictly separated from the pre-locked `N = 36` Stage-1 cohort.** Stage-0 verifies units, Bloch gauge, PBC, residual forces, NAC matching, and directional Rayleigh curvature mechanics only.

---

## 1. Pinned Public Sources, Model & Isolated Software Environment

- **Isolated Workspace Environment (`.venv`, exact pins in [`requirements.lock.txt`](requirements.lock.txt), zero global installs, zero paid APIs):**
  - `Python 3.12.16`, `torch==2.11.0+cu128` on `NVIDIA GeForce RTX 5060 Laptop GPU` (capability `12.0`, `8151 MiB`), `mace-torch==0.3.17`, `phonopy==4.11.0`, `ase==3.29.0`, `spglib==2.8.0`, `symfc==1.8.0`, `scipy==1.18.1`, `numpy==2.5.5`.
  - Exact Phonopy frequency conversion factor verified: `DefaultToTHz = 15.633302300230191` (`THz / sqrt(eV / (AMU * A^2))`).
  - **Mass-table audit:** Phonopy uses `Si = 28.0855`, `O = 15.9994` (`ph.primitive.masses`), whereas ASE uses `Si = 28.085`, `O = 15.999`. All Rayleigh calculations strictly use `ph.primitive.masses` for exact dynamical-matrix parity.
- **Approved Public MLIP Weights (Excluded from Git Archive Under ASL):**
  - `mace-omat-0-small.model` (`ACEsuit/mace-foundations` release `mace_omat_0`, Academic Software Licence `ASL`, academic non-commercial research).
  - Exact size & checksum verified byte-for-byte: **`67,630,500 B`**, `SHA-256`: `0abfde07862cf1e93b8b4d03cb702f29ce9c344ff2fc4de2ec0d7166d6c113a5`.
  - Executed in double precision (`default_dtype="float64"`) on CUDA (`~25 ms` per primitive call, `64–135 ms` per `64–135`-atom supercell call).
- **Initial Six Smoke Structures (`stage0_smoke_outputs/stage0_mechanics_verification_receipt.json`, `SHA-256`: `7b367ec9e3152c1288f75da4694eb6c268f39fe3606c7348b52aadb937d5f2d9`):**
  - `2` NIMS MDR **PBEsol** pipeline smoke controls (`CC BY`, **NOT mixed with PBE for paired decision labels**):
    - `nims_pbesol_mp-149_Si.yaml.xz` (`1,472 B`, MD5 `f805da3aab84b22d96bdd610ae41bc10`, `a = 5.43457 Å`, `has_nac = True`, DFT `Gamma` optical `+15.2872 THz`).
    - `nims_pbesol_mp-2998_BaTiO3.yaml.xz` (`3,400 B`, MD5 `1c9f4c01cbe2ba2f9ec9220765721d9a`, `a = 3.98629 Å`, `has_nac = True`, DFT `Gamma` soft mode `-6.0487 THz`).
  - `4` Official Alexandria **pure PBE** cubic crystals (`CC BY 4.0`, `https://alexandria.icams.rub.de/data/phonon_benchmark/pbe/`, `has_nac = False`):
    - `mp-149` (`Si`, `a = 5.46722 Å`), `mp-1265` (`MgO`, `a = 4.25595 Å`), `mp-2998` (`BaTiO3`, `a = 4.03491 Å`, `-7.5098 THz` — `1.46 THz` softer than PBEsol, proving why PBEsol/PBE must never be mixed!), `mp-5229` (`SrTiO3`, `a = 3.94385 Å`, `-4.1067 THz`).
- **Two Additional Non-Cubic Smoke Structures (`stage0_smoke_outputs/stage0_noncubic_mechanics_receipt.json`, `SHA-256`: `00fc56c449ed00c88eae81abbc3ed425520d788089f388ca7bc0a33894f76b65`):**
  - `mp-2657` (tetragonal rutile `TiO2`, `n_prim = 6`, `max |F(0)| = 0.02006 eV/Å`, DFT `2×2×4`).
  - `mp-7000` (trigonal alpha-quartz `SiO2`, `n_prim = 9`, `max |F(0)| = 0.03032 eV/Å`, DFT `2×2×2`).
- **Close Priors Cited (No Priority Claims):**
  - `da Silva, Wang & Marques` (`https://arxiv.org/abs/2610.23545`): primitive-cell Bloch linear response for MLIPs showing spurious small-supercell instabilities.
  - `Grandel, Benner & George` (*npj Computational Materials*, `10.1038/s41524-026-02338-w`, `PMC13713550`, Zenodo `10.5281/zenodo.22180297`): commensurate supercells and DFT-vs-ML soft-mode energy curves.
  - `Hänseroth & Dreßler` (`https://arxiv.org/abs/2610.00585`, `PESCert`): inexpensive reference-free PES physical-law checks.
  - `PhononBench-MP40` (`https://arxiv.org/html/2607.22573v1`): context only; zero MatterSim labels used as DFT ground truth.

---

## 2. Verified Physics, Bloch Gauge & Exploratory Smoke Findings

1. **Forward Force & PBC Parity (Zero ML Relaxation):** Energy scaling `|E_sc / N_sc - E_prim / N_prim| <= 8.9e-15 eV/atom` and force sum `|sum F| <= 8.9e-15 eV/Å`. Nonzero residual forces on non-cubic pinned PBE geometries (`TiO2` `0.02006 eV/Å`, `SiO2` `0.03032 eV/Å`) cancel in central differences `F(+h) - F(-h)`.
2. **Exact `C-type` Bloch Gauge & Minimal Index-$L$ Repeat (`S^T q ∈ Z^3`):** Using Phonopy's convention `supercell.cell = S^T @ prim.cell` and `C-type` phase $\exp(i 2\pi \mathbf{q} \cdot \mathbf{x}_I)$, reduced-HNF minimal repeats (`det(S) == L`) match full commensurate MACE Phonopy Hessians (`3×3×3` / `4×4×4`, up to `320` atoms) to **`0.0001–0.0006 THz`** under multi-image PBC; wrong `D-type` gauge failed by `1.59 THz` on `Si NonSC_3`.
3. **Non-Self-Conjugate Quadratures (`cos` vs. `sin`) & `float64` Two-`h` Convergence:** Collective ferroelectric modes (`BaTiO3`, `SrTiO3`) exhibited quartic `O(h^2)` hardening at `h = 0.01–0.02 Å` (`+0.15` to `+0.31 THz`). Using `h_1 = 0.001 Å` and `h_2 = 0.002 Å` in `float64` achieved `0.00010–0.00036 THz` parity and `|cos - sin| <= 0.00009 THz` on `NonSC_3 (1/3,0,0)` and `NonSC_4 (1/4,1/4,0)`.
4. **Exploratory Non-Cubic Findings (Separated from Stage-1):**
   - **`SiO2` alpha-quartz (`mp-7000`):** Coarse `1×1×1` interpolated a fake `-3.554 THz` mode at `R=(1/2,1/2,1/2)` (and `-3.63 THz` at `(0,0,1/2)`), rejected by minimal-repeat Rayleigh (`+1.5585` / `+3.43 THz`, error `0.00030 THz`, matching DFT `+1.871` / `+3.36 THz`).
   - **`TiO2` rutile (`mp-2657`) Hidden Negative Direction:** At `NonSC_3b = (1/3, 1/3, 0)`, projecting the coarse `2×2×2` eigenvector yielded **`+2.2267 THz`** (`full_3x3x3_proj = +2.227 THz`, exact `0.00021 THz` parity), **yet `full_3x3x3` harbored a hidden negative mode at `-1.701 THz` along a different eigenvector** (DFT `min = -1.253 THz`). This exploratory Stage-0 smoke directly demonstrated why a nonnegative single-direction projection is **unconfirmed** and cannot certify material stability.
