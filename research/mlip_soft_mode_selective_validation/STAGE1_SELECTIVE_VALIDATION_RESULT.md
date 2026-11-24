# Stage-1 Grouped Development Pilot Result — Selective Verification of Soft Phonon Modes (Limited Diagnostic / Negative Allocation Archive)

**Status / Decision:** **`STOP_STAGE1_EQUAL_BUDGET_GATE_FAILED`** (`FROZEN_LIMITED_DIAGNOSTIC_NEGATIVE_ALLOCATION_ARCHIVE`)  
**Date Completed & Sealed:** 2026-11-24  
**Archive Target Path:** `research/mlip_soft_mode_selective_validation/`  
**Pre-Locked Stop Rule Honored:** Stopped cleanly after the pre-locked `N = 36` label-blind grouped pilot. No tuning of step sizes/phases, no cohort narrowing, no cherry-picking of a favorable budget point, no silent ML relaxation, no cluster-scale DFT, and no paper, PDF, media, leaderboard, or priority claims.

---

## 1. Executive Verdict

Across **`N = 36` label-blind, crystal-system-grouped inorganic crystals** (`9` per group across `4` groups: Cubic, Tetragonal, Trigonal/Hexagonal, Orthorhombic/Monoclinic/Triclinic) from official Alexandria PBE (`CC BY 4.0`, non-`+U` PBE aligned, matched `NAC = False`, exact DFT-commensurate grid $Q_{\text{exact}}(m) = \{\mathbf{q} \in [0, 1)^3 : S_{\text{DFT,rel}}^T \mathbf{q} \in \mathbb{Z}^3\}$, zero ML relaxation; evaluated with `mace-omat-0-small.model` in `float64` on CUDA, **`PID 3568`**, **`111.768 s`**):

1. **Exact Directional Curvature Parity (`36/36`):** Minimal index-$L$ reduced-HNF Bloch Rayleigh curvature (`h_1 = 0.001 Å`, `h_2 = 0.002 Å`, `C-type` gauge, central forces) matched the explicit full same-model commensurate Phonopy Hessian projection $\mathbf{e}^{*\dagger} D_{\text{MACE,full}}(\mathbf{q}^*) \mathbf{e}^*$ with **median error `0.000008 THz`** and **max error `0.000269 THz`** across all `36` crystals (`|cos - sin| <= 6 × 10^-6 THz` on non-self-conjugate $\mathbf{q}^*$).
2. **Real Coarse-Supercell False-Positive Regime (Separate Same-Model vs. Archived-PBE Counts, `tau = 0.25 THz`):**
   - **`14 / 36`** crystals were coarse-flagged unstable (`f_coarse_min < -0.25 THz`, all `14/14` at non-commensurate $\mathbf{q}^*$).
   - **`6`** were **same-model robust coarse false positives** (`MACE_full > +0.25 THz`): **`4`** from identity coarse boxes (`[1,1,1]`: `HgNa2O2`, `BiFO`, `O8P2RbTa`, `Cl2CsCu2I`) and **`2`** from non-identity coarse boxes (`CdH2O2` `[2,2,1]`, `B2O3` `[1,1,2]`), spanning **`3`** crystal-system groups (`Tetragonal`, `Trigonal_Hexagonal`, `Orthorhombic_Monoclinic_Triclinic`).
   - **`5`** were **coarse false positives against independent archived PBE** (`DFT > +0.25 THz`, tracked as a separate non-nested count: `HgNa2O2`, `CdH2O2`, `B2O3`, `Cl2CsCu2I`, plus `H6Mg2Os` where `MACE_full = -7.80` itself disagrees with `DFT = +2.97`; conversely, `BiFO` is `DFT_NEAR_ZERO` `+0.06` and `O8P2RbTa` is `DFT_NEG` `-1.11`).
   - **Coarse misses (false negatives at `B = 0`):** **`1`** vs. `MACE_full` (`mp-552729 IKO3`, `coarse = -0.00` vs. `MACE_full = -1.71`) and **`3`** vs. archived PBE `DFT` (`IKO3`, `AuCa2Sb`, `AgBiS2`).
3. **Why the Pre-Locked Equal-Budget Stage-1 Gate FAILED (Strong Same-Cost Comparisons Including Real Wall Time):**
   - At **`50%` atom-force evaluation budget (`9,937`)**, `Rayleigh_Gated_Full` nudged decisive DFT accuracy from **`0.8438 -> 0.8750`** due to **one single crystal** (`FP: 2 -> 1`), with **`NEG` recall completely unchanged at `8/11`** (`0.7273`).
   - On **real GPU wall time (`19.2746 s` total full flagged)**, the **`50%` wall-time tier tied identically** (`0.8438` decisive DFT accuracy, identical `FPR = 0.0952` and recall `8/11`), while **earlier wall-time tiers were worse** (`10%`: `0.7500` vs. `0.7812`; `25%`: `0.7812` vs. `0.8125`) because upfront small-cell Rayleigh checks (`2.37 s`) pay GPU launch overhead before confirming a single full rerun.
   - On **force calls (`180` total full flagged)**, `Rayleigh_Gated_Full` was **strictly worse across `10%`, `25%`, `50%`, and `100%`** (`66` Rayleigh calls + `148` escalated full calls = **`214` total calls** vs. `180` for running full commensurate Phonopy on all `14` flagged crystals!).
   - At **full coverage (`100%` budget)**, `Rayleigh_Gated_Full` achieved **identical accuracy/FPR/recall** to full reruns with only **`~11.2%` fewer atomic evaluations** (`17,656` vs. `19,874`) and **`~4.3%` less recorded wall time** (`18.444 s` vs. `19.275 s`) — **not** an advancement over simple equal-cost priority controls (`NearZero_Mag_Full_Recheck` / `NonComm_Only_Full_Recheck`).
   - Direct **`Rayleigh_Only`** triage suffered **poor `NEG` recall** (`4/9 = 0.4444` vs. `MACE_full`, `4/11 = 0.3636` vs. `DFT`; `DFT F1` dropped from `0.6667` to `0.5333`) because `4/10` Rayleigh-rejected crystals (`H6Mg2Os`, `CaCu2O2`, `F`, `BiLi5O5`) harbored genuine negative modes along rotated eigenvectors / other bands (`3/4` also `DFT_NEG`).

Per the pre-locked stop rule (§4 of [STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md](STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md)), we **stop cleanly and freeze Stage-0 + Stage-1 as a limited diagnostic/negative allocation archive**.

---

## 2. Verified Receipts, Pinned Sources & Close Prior Citations

| Artifact / Pin | Verified Value |
|---|---|
| Stage-0 Smoke Receipt (Strictly Separate `6 + 2` Crystals) | [STAGE0_SMOKE_RECEIPT.md](STAGE0_SMOKE_RECEIPT.md) (`stage0_mechanics_verification_receipt.json` `7b367ec9...`; `stage0_noncubic_mechanics_receipt.json` `00fc56c4...`) |
| Stage-1 Pre-Locked Protocol (Unmodified) | [STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md](STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md) (`SHA-256`: `84e460a2ed71e1be9f49a1ff86c01196a6fa088a92700bc3d39bf7ce349af002`) |
| Label-Blind 36-Crystal Manifest (Unmodified) | [stage1_cohort_manifest.json](stage1_cohort_manifest.json) (`SHA-256`: `d3b965b6cb8034e1462fec3fa35ef2783e20ee2151188eb749b4f80333310a0a`) |
| Stage-1 Runner (Unmodified) | [run_stage1_selective_validation.py](run_stage1_selective_validation.py) (`SHA-256`: `b3b63f6de9a844dff18443d266c3f6eb5d62298d9b6ce53b369364fb303251cb`) |
| Native Execution Receipt | **`PID 3568`**, wall **`111.768 s`**, `NVIDIA GeForce RTX 5060 Laptop GPU`, `torch==2.11.0+cu128`, `mace-torch==0.3.17`, `phonopy==4.11.0`, `float64` |
| Stage-1 Summary JSON (Unmodified) | [stage1_outputs/stage1_selective_validation_summary.json](stage1_outputs/stage1_selective_validation_summary.json) (`SHA-256`: `df60cc5daaabadbe241997aaeebf07aaba50f5969f45345fb176a83846587429`) |
| Stage-1 Per-Material Ledger (Unmodified, `36` rows) | [stage1_outputs/stage1_per_material.jsonl](stage1_outputs/stage1_per_material.jsonl) (`SHA-256`: `8df67580ab5b83bf39a4652a2342903b0fbaa2c4e147c6b2f857d69e68fc3a64`) |
| Model Pin (Weights Excluded Under ASL) | `mace-omat-0-small.model` (`67,630,500 B`, `SHA-256`: `0abfde07862cf1e93b8b4d03cb702f29ce9c344ff2fc4de2ec0d7166d6c113a5`, `ASL`) |
| Independent DFT Source (Raw YAMLs Excluded) | Official Alexandria PBE (`https://alexandria.icams.rub.de/data/phonon_benchmark/pbe/`, `CC BY 4.0`, `NAC = False` matched) |

**Close Priors Explicitly Cited (No Priority Claims):**
- **da Silva, Wang & Marques (2026):** *Linear response for machine-learned interatomic potentials: phonons at arbitrary wave vectors from the primitive cell*, [`https://arxiv.org/abs/2610.23545`](https://arxiv.org/abs/2610.23545) (already derives primitive-cell linear response and finds spurious small-supercell instabilities).
- **Grandel, Benner & George (2026):** *Targeted fine-tuning of machine-learning interatomic potentials for phonons and phase transitions*, *npj Computational Materials*, DOI **`10.1038/s41524-026-02338-w`** (`PMC13713550`, source data `10.5281/zenodo.22180297`; uses commensurate crystals and DFT-vs-ML soft-mode curves).
- **Hänseroth & Dreßler (2026):** *Reference-free certification of machine-learning interatomic potentials (`PESCert`)*, [`https://arxiv.org/abs/2610.00585`](https://arxiv.org/abs/2610.00585).
- **PhononBench-MP40:** [`https://arxiv.org/html/2607.22573v1`](https://arxiv.org/html/2607.22573v1) (context only; zero MatterSim labels treated as DFT truth).

---

## 3. Equal-Budget Verification Allocation Results (`tau = 0.25 THz`, `N = 36`, `14` Flagged)

`MACE_full` labels (`32` decisive + `4` `NEAR_ZERO`): `23` `POS`, `9` `NEG`.  
Archived PBE `DFT` labels (`32` decisive + `4` `NEAR_ZERO`): `21` `POS`, `11` `NEG`.  
Because all `14/14` coarse flags occurred at non-commensurate $\mathbf{q}^*$, `NonComm_Only_Full_Recheck` was identical to `NearZero_Mag_Full_Recheck`.

### 3.1 Atom-Force Evaluations (`100% Full Flagged = 19,874`)

| Budget | Policy | Spent (at-evals) | `n_ray / n_full` | `MACE_full` FPR (`POS`) | `MACE_full` Dec. Acc (`FP/FN`) | `DFT` FPR (`POS`) | `DFT` Dec. Acc (`FP/FN`) | `DFT` Recall (`NEG`) | `DFT` F1 (`NEG`) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `0%` (`0`) | `No_Recheck` | 0 | `0 / 0` | `0.2609` | `0.7812` (`6/1`) | `0.2381` | `0.7500` (`5/3`) | `8/11` (`0.7273`) | `0.6667` |
| `10%` (`1,987`) | `Random_Full` (200-seed mean) | — | — | `0.2165` | `0.8131` | `0.2086` | `0.7694` | — | `0.6849` |
| `10%` (`1,987`) | `NearZero_Mag` / `NonComm_Only` | 1,900 | `0 / 3` | `0.2174` | `0.8125` (`5/1`) | `0.1905` | `0.7812` (`4/3`) | `8/11` (`0.7273`) | `0.6957` |
| `10%` (`1,987`) | `Rayleigh_Gated_Full` | 1,782 | `14 / 1` | `0.2174` | `0.8125` (`5/1`) | `0.1905` | `0.7812` (`4/3`) | `8/11` (`0.7273`) | `0.6957` |
| `10%` (`1,987`) | `Rayleigh_Only` | 1,242 | `14 / 0` | `0.0000` | `0.8438` (`0/5`) | `0.0000` | `0.7812` (`0/7`) | **`4/11` (`0.3636`)** | **`0.5333`** |
| `25%` (`4,969`) | `Random_Full` (200-seed mean) | — | — | `0.1667` | `0.8489` | `0.1705` | `0.7870` | — | `0.6955` |
| `25%` (`4,969`) | `NearZero_Mag` / `NonComm_Only` | 4,860 | `0 / 4` | `0.1304` | `0.8750` (`3/1`) | `0.1429` | `0.8125` (`3/3`) | `8/11` (`0.7273`) | `0.7273` |
| `25%` (`4,969`) | `Rayleigh_Gated_Full` | 4,950 | `14 / 2` | `0.1739` | `0.8438` (`4/1`) | `0.1429` | `0.8125` (`3/3`) | `8/11` (`0.7273`) | `0.7273` |
| `50%` (`9,937`) | `Random_Full` (200-seed mean) | — | — | `0.1102` | `0.8895` | `0.1312` | `0.8042` | — | `0.7061` |
| `50%` (`9,937`) | `NearZero_Mag` / `NonComm_Only` | 9,480 | `0 / 10` | `0.0870` | `0.9062` (`2/1`) | `0.0952` | `0.8438` (`2/3`) | `8/11` (`0.7273`) | `0.7619` |
| `50%` (`9,937`) | `Rayleigh_Gated_Full` | 9,352 | `14 / 8` | `0.0435` | `0.9375` (`1/1`) | `0.0476` | `0.8750` (`1/3`) | `8/11` (`0.7273`) | `0.8000` |
| `75%` (`14,906`) | `Random_Full` (200-seed mean) | — | — | `0.0535` | `0.9303` | `0.0874` | `0.8256` | — | `0.7229` |
| `75%` (`14,906`) | `NearZero_Mag` / `NonComm_Only` | 14,066 | `0 / 13` | `0.0000` | `0.9688` (`0/1`) | `0.0476` | `0.8438` (`1/4`) | `7/11` (`0.6364`) | `0.7368` |
| `75%` (`14,906`) | `Rayleigh_Gated_Full` | 13,880 | `14 / 8` | `0.0870` | `0.9062` (`2/1`) | `0.0952` | `0.8438` (`2/3`) | `8/11` (`0.7273`) | `0.7619` |
| `100%` (`19,874`) | `NearZero_Mag` / `NonComm_Only` | 19,874 | `0 / 14` | `0.0000` | `0.9688` (`0/1`) | `0.0476` | `0.8438` (`1/4`) | `7/11` (`0.6364`) | `0.7368` |
| `100%` (`19,874`) | `Rayleigh_Gated_Full` | 17,656 | `14 / 10` | `0.0000` | `0.9688` (`0/1`) | `0.0476` | `0.8438` (`1/4`) | `7/11` (`0.6364`) | `0.7368` |

### 3.2 Real GPU Wall Time (`100% Full Flagged = 19.2746 s`) & Force Calls (`100% = 180`)

| Budget | `Wall`: `NearZero_Mag` (`DFT_acc` / `FPR` / `Rec`) | `Wall`: `Rayleigh_Gated_Full` (`DFT_acc` / `FPR` / `Rec`) | `Calls`: `NearZero_Mag` (`DFT_acc` / `FPR`) | `Calls`: `Rayleigh_Gated_Full` (`DFT_acc` / `FPR`) |
|---|---|---|---|---|
| `10%` | `0.7812` / `0.1905` / `8/11` | **`0.7500` / `0.2381` / `8/11` (worse)** | `0.7812` / `0.1905` | **`0.7500` / `0.2381` (worse)** |
| `25%` | `0.8125` / `0.1429` / `8/11` | **`0.7812` / `0.1905` / `8/11` (worse)** | `0.8125` / `0.1429` | **`0.7500` / `0.2381` (worse)** |
| `50%` | `0.8438` / `0.0952` / `8/11` | **`0.8438` / `0.0952` / `8/11` (tie)** | `0.8438` / `0.0952` | **`0.7812` / `0.1905` (worse)** |
| `75%` | `0.8438` / `0.0952` / `8/11` | `0.8438` / `0.0952` / `8/11` (tie) | `0.8438` / `0.0952` | `0.8438` / `0.0952` (tie) |
| `100%` | `0.8438` / `0.0476` / `7/11` (`19.27 s`) | `0.8438` / `0.0476` / `7/11` (`18.44 s`, `-4.3%`) | `0.8438` / `0.0476` (`180` calls) | **`0.8438` / `0.0952` (`172/180`; full needs `214` calls!)** |

Threshold sensitivity (`tau = 0.10 THz` & `0.50 THz`, preserved unmodified in `stage1_selective_validation_summary.json`) exhibits the same pattern: `Rayleigh_Only` consistently degrades `DFT F1` (`0.5882` / `0.5333`), while `Rayleigh_Gated_Full` yields only `9.6%` (`tau=0.10`) to `14.6%` (`tau=0.50`) full-coverage atom-eval savings.

---

## 4. Complete Table of the `14` Coarse-Flagged Crystals (`tau = 0.25 THz`)

| `mp_id` | Formula | Group | `S_c` | `max\|F0\|` (eV/Å) | `f_coarse` | `q*` (`L`) | `f_Ray` (`h1/h2`) | `f_MACE_full` | `f_DFT` | Cost `ray / full` (at-evals) | Status |
|---|---|---|---|---:|---:|---|---:|---:|---:|---:|---|
| `mp-579536` | `Cl2CsCu2I` | Orth | `[1,1,1]` | 0.045 | -0.40 | `(0,2/3,0)` (3) | `+1.37/+1.37` | `+0.33` (`POS`) | `+0.41` (`POS`) | `216 / 3,168` | MACE & DFT coarse FP |
| `mp-22991` | `CsI3V` | Trig | `[1,1,1]` | 0.069 | -0.63 | `(1/2,0,0)` (2) | **`-0.52/-0.52`** | `-0.62` (`NEG`) | `-9.37` (`NEG`) | `80 / 720` | Confirmed negative |
| `mp-4961` | `HgNa2O2` | Tetr | `[1,1,1]` | 0.044 | -1.20 | `(1/2,1/2,1/2)` (2) | `+1.91/+1.91` | `+1.21` (`POS`) | `+1.28` (`POS`) | `40 / 540` | MACE & DFT coarse FP |
| `mp-754501` | `CaCu2O2` | Tetr | `[1,1,1]` | 0.011 | -1.84 | `(1/2,1/2,1/2)` (2) | `+3.79/+3.79` | `-2.89` (`NEG`) | `-2.94` (`NEG`) | `80 / 640` | Unconfirmed -> hidden NEG |
| `mp-561367` | `F` | Orth | `[2,2,1]` | 0.135 | -2.02 | `(0,1/2,1/2)` (2) | `+0.59/+0.59` | `-1.96` (`NEG`) | `-0.85` (`NEG`) | `32 / 1,024` | Unconfirmed -> hidden NEG |
| `mp-625548` | `CdH2O2` | Trig | `[2,2,1]` | 0.024 | -2.13 | `(0,0,2/3)` (3) | `+2.11/+2.11` | `+0.74` (`POS`) | `+0.91` (`POS`) | `90 / 810` | MACE & DFT coarse FP |
| `mp-752949` | `BiFO` | Trig | `[1,1,1]` | 0.095 | -2.23 | `(2/3,2/3,2/3)` (3) | `+1.16/+1.16` | `+0.36` (`POS`) | `+0.06` (`NZ`) | `108 / 432` | MACE FP; DFT near-zero |
| `mp-39542` | `F5KORb2Zr` | Tetr | `[1,1,1]` | 0.135 | -2.55 | `(1/2,1/2,1/2)` (2) | **`-0.50/-0.50`** | `-2.41` (`NEG`) | `-2.11` (`NEG`) | `80 / 1,120` | Confirmed negative |
| `mp-14099` | `AgF3Zn` | Cubi | `[2,2,2]` | 0.000 | -3.58 | `(2/3,1/3,1/3)` (3) | **`-3.38/-3.38`** | `-3.38` (`NEG`) | `-3.22` (`NEG`) | `90 / 810` | Confirmed negative |
| `mp-29365` | `BiLi5O5` | Orth | `[1,1,1]` | 0.046 | -3.78 | `(1/2,1/2,0)` (2) | `+2.64/+2.64` | `-3.31` (`NEG`) | `-3.52` (`NEG`) | `88 / 5,808` | Unconfirmed -> hidden NEG |
| `mp-546973` | `O3SnSr` | Cubi | `[2,2,2]` | 0.000 | -4.06 | `(2/3,2/3,1/3)` (3) | **`-4.00/-4.00`** | `-4.00` (`NEG`) | `-3.94` (`NEG`) | `90 / 810` | Confirmed negative |
| `mp-554412` | `O8P2RbTa` | Orth | `[1,1,1]` | 0.150 | -4.31 | `(1/2,1/2,0)` (2) | `+3.18/+3.18` | `+0.72` (`POS`) | `-1.11` (`NEG`) | `96 / 2,496` | MACE FP; DFT NEG |
| `mp-717` | `B2O3` | Orth | `[1,1,2]` | 0.177 | -5.38 | `(1/2,1/2,0)` (2) | `+6.97/+6.97` | `+3.51` (`POS`) | `+3.76` (`POS`) | `80 / 1,280` | MACE & DFT coarse FP |
| `mp-643002` | `H6Mg2Os` | Cubi | `[1,1,1]` | 0.087 | -7.86 | `(0,1/2,1/2)` (2) | `+20.36/+20.36` | `-7.80` (`NEG`) | `+2.97` (`POS`) | `72 / 216` | Hidden MACE NEG; DFT FP |

---

## 5. Scope Boundaries, Equilibrium Residual Forces & Technical Caveats (No Results Altered)

1. **Directional Unconfirmed Semantics:** Near-zero, nonconfirming (`>= -tau`), or `h1`/`h2`-disagreeing directional projections are strictly **unconfirmed** — never evidence of dynamical or physical stability (empirically underscored by `4/10` Stage-1 hidden-mode cases plus Stage-0 exploratory `TiO2`).
2. **Residual Forces & Intended Dev Scope (No OOD Claim):** **`15 / 36` (`41.7%`)** crystals had `max |F(0)| > 0.05 eV/Å` on the pinned archived PBE geometry (median `0.0452 eV/Å`, max `0.365 eV/Å`). On `max |F(0)| <= 0.05 eV/Å` (`n = 21`), `MACE_full` agreed with archived PBE DFT on `18/19` (`94.7%`), dropping to `10/13` (`76.9%`) for `max |F(0)| > 0.05 eV/Å` (`n = 15`). Furthermore, `mace-omat-0-small.model` was trained on `OMat24` (which overlaps Materials Project crystal structures); this `N = 36` set is an intended development diagnostic sample with **no out-of-distribution (OOD) generalization claim**.
3. **Archived Periodic PBE / `NAC = False` Grid Scope:** All ground-truth comparisons are strictly on the **same-geometry archived periodic PBE commensurate grid `Q_exact(m)` with `NAC = False`** — NOT arbitrary-`q` continuous Brillouin-zone dispersion and NOT a claim of experimental/physical crystal stability (quantum/anharmonic/stress/NAC/functional effects excluded).
4. **$\Gamma$-Degeneracy & Allocation-Cost Caveats (Documented Without Changing Results):**
   - At $\mathbf{q} = \Gamma$, acoustic modes were excluded by mass-weighted uniform-translation projection (`p_tr > 0.5`), and `min_non_acoustic_on_qgrid` extracts a single lowest eigenvector `(q*, band*)` rather than scanning a full degenerate subspace.
   - In `run_equal_budget_benchmark`, `Rayleigh_Gated_Full` runs all affordable non-commensurate Rayleigh checks upfront (`66` calls / `1,242` atom-evals / `2.37 s`) before greedy skip-if-too-large full-rerun allocation (`if spent + cf <= budget`), which causes discrete knapsack-boundary skips at intermediate budgets (e.g., `75%` atom-evals and `100%` force calls where `214 > 180`).
   - Recorded `wall_s` reflects single-GPU (`RTX 5060`, `float64`) sequential execution where small minimal supercells incur fixed kernel-launch overhead; however, even on hardware-independent atom-force evaluations, full-coverage savings are only `11.2%` (`17,656` vs. `19,874`).
