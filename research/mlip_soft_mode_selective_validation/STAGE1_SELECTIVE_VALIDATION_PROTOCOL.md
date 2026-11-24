# Stage-1 Pre-Locked Grouped Development Pilot Protocol — Selective Verification of Soft Phonon Modes

**Date Locked:** 2026-11-24 (BEFORE selecting, downloading, or inspecting any Stage-1 material or DFT phonon label)  
**Workspace:** `D:\AI_Science\antigravity\mlip_soft_mode_selective_validation_20261124`  
**Scope:** Bounded GPU/CPU development pilot on `N = 36` label-blind, crystal-system-grouped inorganic crystals from official Alexandria PBE (`CC BY 4.0`). No cluster-scale DFT, no tuning, no ML relaxation, no PDF/news/PR/priority claims.

---

## 1. Label-Blind Grouped Material Selection (`N = 36` Materials)

- **Source Pool:** `https://alexandria.icams.rub.de/data/phonon_benchmark/pbe/` (`CC BY 4.0`) + `pbe.csv` (**strictly reading ONLY columns `mp_id` and `nsites`; all frequency/thermodynamic/`stable` columns are discarded immediately on read and NEVER inspected during selection**).
- **Zero Overlap with Stage-0 Smoke:** Exclude `{mp-149, mp-1265, mp-2998, mp-5229, mp-2657, mp-7000}`.
- **Deterministic Candidate Ordering:** Filter `nsites <= 160` (from `pbe.csv` `nsites` column only), then sort by `SHA-256("mlip_soft_mode_stage1_v1:" + mp_id)`.
- **Geometry/Composition-Only Eligibility Filters (ZERO inspection of `force_constants`, `displacements`, `phonon_freq`, or `stable` during selection):**
  1. **PBE Functional Alignment (No OMat24 `+U` Mismatch):** Exclude materials containing `{Co, Cr, Fe, Mn, Mo, Ni, V, W}` combined with `{O, F}` (MP/OMat24 Hubbard `+U` anions), and restrict atomic numbers to `Z <= 83` excluding lanthanides (`57 <= Z <= 71`).
  2. **Tractability & Matched NAC:** `2 <= n_prim <= 12`, `4 <= V_DFT <= 64` (`V_DFT = |det(S_DFT_rel)|`), `len(DFT supercell) <= 160`, `has_nac == False` (matching `NAC = False` identically between DFT and MLIP), and `det(S_coarse) < V_DFT` (coarse screening box strictly smaller than DFT supercell).
  3. **Reduced-Formula Deduplication:** At most 1 polymorph per reduced chemical formula across the entire cohort.
- **4 Balanced Crystal-System Groups (`9` per group = `36` total):**
  - `Cubic` (`SG 195–230`): `9` materials
  - `Tetragonal` (`SG 75–142`): `9` materials
  - `Trigonal_Hexagonal` (`SG 143–194`): `9` materials
  - `Orthorhombic_Monoclinic_Triclinic` (`SG 1–74`): `9` materials
- Selection writes a sealed `stage1_cohort_manifest.json` before any phonon evaluation begins.

---

## 2. Exact Per-Crystal Evaluation Protocol (Zero ML Relaxation, Matched `q`-Grid & `NAC = False`)

For every selected crystal `m` (using `mace-omat-0-small.model`, `SHA-256`: `0abfde07...`, `default_dtype="float64"` on CUDA; `phonopy==4.11.0`; exact `ph.primitive.masses`):

1. **Exact Shared DFT-Commensurate `q`-Grid:**
   - $Q_{\text{exact}}(m) = \{ \mathbf{q} \in [0, 1)^3 : S_{\text{DFT,rel}}^T \mathbf{q} \in \mathbb{Z}^3 \}$ (`|Q_exact(m)| = V_DFT`), where $S_{\text{DFT,rel}} = \text{round}(P^{-1} M_u)$ satisfies `supercell.cell == S_DFT_rel^T @ prim.cell`. Every `q` in $Q_{\text{exact}}(m)$ has **zero DFT Fourier-interpolation error**.
   - Acoustic translation exclusion at $\Gamma = (0, 0, 0)$ via exact mass-weighted uniform-translation projection `p_tr > 0.5` (always excluding exactly 3 acoustic modes at $\Gamma$).
2. **Residual Force Audit (No Relaxation):** Log `max |F(0)|` (`eV/Å`) of `MACE-OMAT-0-small` on the exact pinned PBE primitive geometry (no silent ML relaxation; high-force non-equilibrium crystals are explicitly flagged and analyzed in sensitivity checks!).
3. **Coarse Screening Supercell (`S_coarse`):**
   - `S_coarse = diag(k_1, k_2, k_3)` where `k_i = 1` if primitive axis length `|a_i| >= 4.5 Å` else `2` (falling back to `I_3` if `k_1 k_2 k_3 >= V_DFT`).
   - Run full `MACE-OMAT-0-small` Phonopy on `S_coarse` (`disp_dist = 0.002 Å`, `is_plusminus = True`). Record `f_coarse_min`, nominated `(q*, band*, e*)`, `is_q_commensurate_with_coarse`, force calls, atom-force evals, and wall time.
4. **Minimal-Repeat Bloch Rayleigh Recheck (On Every Coarse-Flagged Crystal `f_coarse_min < -tau_neg`, with pre-locked `tau_neg = 0.25 THz`, plus secondary threshold sensitivity at `0.10 THz` and `0.50 THz`):**
   - Construct reduced HNF minimal commensurate supercell `S_min(q*)` (`det(S_min) == L`, `S_min^T q* ∈ Z^3`).
   - Evaluate central-force Rayleigh curvature with **two pre-fixed step sizes `h_1 = 0.001 Å` and `h_2 = 0.002 Å`** (NO relaxation between calls!) along the larger-amplitude real quadrature (`cos` or `sin`), PLUS cross-check the second quadrature (`sin`) at `h_1 = 0.001 Å` whenever `q*` is non-self-conjugate (`2q* ∉ Z^3`).
   - Record exact `rayleigh_force_calls`, `rayleigh_atom_force_evals`, `rayleigh_wall_s`, `f_ray_h1`, `f_ray_h2`, `quad_diff_h1`, and exact `e*^H D_MACE_full(q*) e*` parity error.
   - **Asymmetric Interpretation Rule:**
     - `RAYLEIGH_CONFIRMED_NEGATIVE`: both `f_ray_h1 < -tau_neg` and `f_ray_h2 < -tau_neg` (and quadrature agreement `|cos - sin| < 0.05 THz` when checked) -> evidence of a negative curvature direction for THIS MLIP.
     - `RAYLEIGH_REJECTED_NONNEGATIVE`: nominated coarse negative mode fails confirmation (`max(f_ray_h1, f_ray_h2) >= -tau_neg`) -> coarse interpolation artifact rejected along `(q*, e*)`, **NOT** a proof of material stability.
5. **Same-Model Full Commensurate Reference (`MACE_full` on `S_DFT_rel`) & Independent Same-Geometry PBE DFT Reference:**
   - Run full `MACE-OMAT-0-small` Phonopy on `S_DFT_rel` (`disp_dist = 0.002 Å`, `is_plusminus = True`), recording `f_mace_full_min`, `f_mace_full_proj`, force calls, atom-force evals, and wall time.
   - Evaluate independent PBE DFT (`NAC = False`) on exact same `Q_exact(m)`, recording `f_dft_min`, `f_dft_proj`, and 3-way DFT regime:
     - `DFT_NEG` (`f_dft_min < -0.25 THz`)
     - `DFT_NEAR_ZERO` (`-0.25 <= f_dft_min <= +0.25 THz`, explicitly separated near-zero uncertainty band)
     - `DFT_POS` (`f_dft_min > +0.25 THz`, meaningfully stable on `Q_exact(m)`)

---

## 3. Pre-Locked Equal-Budget Selective Allocation Policies & Evaluation Endpoints

Across all coarse-flagged crystals (`f_coarse_min < -0.25 THz`), evaluate verification allocation under **exact equal verification budgets `B ∈ {10%, 25%, 50%, 75%, 100%}`** of total flagged full-rerun cost (primary budget axis: **atom-force evaluations**; also reported in **force calls** and **wall time**):

1. **`No_Recheck`** (`B = 0`): Keep all coarse flags unchanged.
2. **`Random_Full_Recheck`** (`200` seeds, mean ± 95% CI): Randomly select flagged crystals for full commensurate `MACE_full` rerun within budget `B`.
3. **`NearZero_Mag_Full_Recheck`**: Prioritize flagged crystals by smallest `|f_coarse_min|` for full commensurate `MACE_full` rerun within budget `B`.
4. **`NonComm_Only_Full_Recheck`**: Prioritize flagged crystals with non-commensurate `q*` (`S_coarse^T q* ∉ Z^3`, ties by smallest `|f_coarse_min|`) for full commensurate `MACE_full` rerun within budget `B`.
5. **`Rayleigh_Gated_Full` (Proposed Conservative Allocation)**: Run cheap minimal-repeat two-`h` Bloch Rayleigh on non-commensurate flagged crystals (ties by smallest `|f_coarse_min|`); skip full rerun when Rayleigh confirms negative (`RAYLEIGH_CONFIRMED_NEGATIVE`), and spend remaining budget on full commensurate `MACE_full` confirmation **only** for `RAYLEIGH_REJECTED_NONNEGATIVE` candidates (never certifying stability from one nonnegative projection alone!).
6. **`Rayleigh_Only` (Proposed Pure Cheap Triage, Auxiliary Comparison)**: Reclassify `RAYLEIGH_REJECTED_NONNEGATIVE` directly without full confirmation, explicitly tracking false-negative risk if a hidden second mode exists.

**Primary Endpoints:**
- (E1) **Same-Model False-Instability Rejection & Macro-F1 / Error vs. `MACE_full`** at equal atom-force evaluations (and equal wall time / force calls).
- (E2) **External DFT Classification Accuracy, False-Instability Rejection Rate (FPR on `DFT_POS`), and Recall on `DFT_NEG`** at equal budget and equal coverage (separating `DFT_NEAR_ZERO` uncertainty cases from decisive `DFT_POS` / `DFT_NEG` cases!).

---

## 4. Pre-Locked Stop / Advance Gate

**STOP cleanly (do NOT claim a positive result or scale further) if ANY of the following occur:**
1. **Insufficient Signal:** Fewer than `6` coarse-flagged crystals (`f_coarse_min < -0.25 THz`) OR fewer than `4` genuine same-model coarse false instabilities (`f_coarse_min < -0.25` while `f_mace_full_min > +0.25 THz`) across the `36` crystals.
2. **Mechanics Breakdown:** Median `|f_ray_h1 - f_mace_full_proj| > 0.05 THz` across evaluated modes.
3. **Full Recheck / Simple Priority Dominates:** Under equal atom-force evaluations (and wall time), `Rayleigh_Gated_Full` fails to beat ALL three same-budget controls (`Random_Full_Recheck`, `NearZero_Mag_Full_Recheck`, `NonComm_Only_Full_Recheck`) in false-instability rejection at equal coverage on **both** same-model `MACE_full` **and** independent PBE DFT (`DFT_POS` vs `DFT_NEG`).
4. **No External DFT Gain:** Gain only separates same-model numerical instability with **zero net DFT classification gain** (e.g., if `MACE_full` itself disagrees with DFT on the rejected cases or equilibrium residual forces dominate errors).
