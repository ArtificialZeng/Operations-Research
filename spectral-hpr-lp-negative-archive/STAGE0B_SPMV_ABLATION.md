# Stage-0b Matched Internal SpMV Ablation & Official Comparator Checkpoint (`spectral_hpr_lp_20261124`)

**Date:** 2026-11-24  
**Script & Data:** [stage0b_matched_spmv_ablation.py](file:///d:/AI_Science/antigravity/spectral_hpr_lp_20261124/stage0b_matched_spmv_ablation.py) · [stage0b_matched_spmv_ablation.json](file:///d:/AI_Science/antigravity/spectral_hpr_lp_20261124/stage0b_matched_spmv_ablation.json)  
*(All sealed `stage0_*` files remain untouched.)*

---

## 1. Hardware & Official Runnable Comparator Record
- **Host CPU:** AMD Ryzen 9 8945HX (16 physical cores / 32 threads), 31.3 GiB RAM. All runs single-threaded (`OMP/MKL/OPENBLAS_NUM_THREADS=1`, `threads=1`, `float64`).
- **GPU / CUDA Status:** WSL Ubuntu 22.04 sees `NVIDIA GeForce RTX 5060 Laptop GPU` (8,151 MiB, driver `582.05`), with **`NO_NVCC` and `NO_JULIA`**. No CUDA solver build (`cuPDLPx` / `HPR-LP-C` / `H-PDLP`) is installed or verified. **CPU prototype numbers do NOT establish a GPU leaderboard claim.**
- **Official Runnable Comparators Verified Locally (CPU):**
  - `HiGHS 1.16.0` (`highspy`, MIT, Windows `uv` Python 3.12): exact reference solver **and** native C++ `solver="pdlp"` (`presolve="off"` verified runnable).
  - `Google OR-Tools 9.15.6755` (`ortools`, Apache 2.0, Windows `uv` Python 3.12): official C++ `PDLP` (`use_glop: false` verified runnable, implementing Applegate et al. `arXiv:2501.07018`).
  - WSL pinned Python 3.14.10 path verified read-only: `/home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14` (not modified).

---

## 2. Matched Internal Ablation — Total Sparse-Pass (SpMV) Accounting
Every sparse matrix pass is explicitly counted (`SpMV_tot = scaling + setup + sweep + kkt_restart + asb_power`) at identical original-space unscaled KKT stopping tolerances (`1e-4` and `1e-6`, `max_iter = 25,000`):

### Family-Level Geometric Mean Total-SpMV Speedups (`Spec-HPR` vs. Baselines)
| Family | `Spec` vs `HPR-Native` (`@1e-6` SpMV) | `Spec` vs `HPR-Slack` (`@1e-6` SpMV, pure $\mathcal{T}_1^{(r)}$ vs $\mathcal{T}_1^{(0)}$) | `Spec` vs `cuPDLPx-ASB` (`@1e-6` SpMV) | `Spec` vs `HPR-Native` (`@1e-4` SpMV) | `Spec` vs `cuPDLPx-ASB` (`@1e-4` SpMV) |
|---|---|---|---|---|---|
| `F1_FactorEq` (equality-only) | **1.61×** | **1.61×** | **1.11×** | **1.72×** | **4.02×** |
| `F2_LinkedMCF` (mixed) | 0.92× | 1.19× | 0.86× | 0.49× | 0.49× |
| `F3_FactorIneq` (100% ineq) | 0.98× | 1.45× | 0.46× | 0.56× | 0.71× |
| `F4_FlatControl` (flat) | 0.70× | 0.93× | 0.71× | 0.74× | 0.72× |

### Key Instance Contrasts (Matched Internal SpMVs + Official C++ PDLP Reference, `tol=1e-6`)
| Instance | `HPR-Native` it (`SpMV_tot`) | `HPR-Slack` it (`SpMV_tot`) | `cuPDLPx-ASB` it (`SpMV_tot`) | `Spec-HPR` it (`SpMV_tot`, `setup`) | Official C++ `HiGHS-PDLP(off)` it (time) | Official C++ `OR-Tools-PDLP(off)` it (time) |
|---|---|---|---|---|---|---|
| `f1_eq_m300_k1` | 6,080 (12,656) | 6,080 (12,656) | **3,160 (6,657)** | 4,480 (9,458, set=140) | 4,840 (0.088s) | 4,736 (0.131s) |
| `f1_eq_m400_k4` | 18,320 (38,048) | 18,320 (38,048) | 11,320 (23,703) | **7,440 (15,600, set=140)** | 10,640 (0.411s) | 15,104 (0.816s) |
| `f1_eq_m500_k8` | MAX 25k (51,907) | MAX 25k (51,907) | MAX 25k (51,997) | **19,560 (40,777, set=168; @1e-4: 1,601)** | 51,680 (4.413s) | 55,744 (6.653s) |
| `f3_ineq_m500_k8` | 17,560 (36,469) | MAX 25k (51,907) | **3,920 (8,256)** | 17,840 (37,208, set=168) | 2,920 (0.258s) | **896 (0.121s)** |
| `f4_flat_mix400` | **6,880 (14,378)** | 12,160 (25,334) | 8,360 (17,659) | 12,760 (26,639, set=140) | 7,960 (0.104s) | 7,168 (0.141s) |

---

## 3. Compact Checkpoint Takeaway (Before Any Scaling)
1. **Setup SpMV cost is small (`140–168` SpMVs):** On high-spike equality LPs (`f1_eq_m400_k4`, `f1_eq_m500_k8`), `Spec-HPR` achieves a genuine, setup-inclusive SpMV and iteration reduction — even solving `f1_eq_m500_k8` in **19,560 iters (`40,777` SpMVs, 2.48s Python)** vs official C++ `HiGHS-PDLP` (**51,680 iters, 4.41s**) and C++ `OR-Tools-PDLP` (**55,744 iters, 6.65s**).
2. **However, slack-converted `Spec-HPR` fails as a general LP preconditioner:** On mixed/inequality LPs (`F2`, `F3`, `F4`), converting inequalities to equalities with slacks inflates base `HPR-LP` SpMVs by `1.3×–2.2×` (`HPR-Slack` vs `HPR-Native`), and adaptive/active-set scalar step solvers (`cuPDLPx-ASB`, official `OR-Tools PDLP`, `HiGHS-PDLP`) dominate `f3_ineq_m500_k8` by **4.5×–20×** via clamped-column exclusion and adaptive steps.
3. **Checkpoint Verdict:** **Keep paused / do not scale** the slack-converted static `Spec-HPR` variant. Any re-open requires a **slack-free** formulation (or strict restriction to equality-form / unclamped-active spectral LPs) passing a new pre-registered SpMV-counted gate against `HPR-Native`, `cuPDLPx-ASB`, `HiGHS-PDLP`, and `OR-Tools-PDLP`.
