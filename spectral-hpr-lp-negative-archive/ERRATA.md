# Authoritative Errata & Scope Corrections (`spectral_hpr_lp_20261124`)

**Date:** 2026-11-24  
**Status:** Route **FROZEN** as a negative-method archive. Sealed Stage-0 files (`STAGE0_PROTOCOL.md`, `stage0_cheap_failure_test.py`, `stage0_results.json`) and `stage0b_*` files are preserved **byte-for-byte** without rerun or modification. This errata supersedes any stronger wording in those earlier pre-freeze files.

---

## 1. Theorem 3 & Numerical PSD Check Scope Correction
- **Mathematical hypothesis vs. code:** Theorem 3 in [THEORY_THEOREMS_1_TO_3.md](THEORY_THEOREMS_1_TO_3.md) requires a **genuine upper bound** $\theta_\perp^2 \ge \|P_\perp A\|_2^2$. The prototype code (`build_certified_spectral_operator` in `stage0_cheap_failure_test.py` and `build_spec_counted` in `stage0b_matched_spmv_ablation.py`) instead computes finite power-iteration / Ritz **lower** estimates of $\|P_\perp A\|_2^2$ multiplied by a heuristic safety factor `1.02`.
- **Correct label:** The implemented construction is a **heuristic upper-bound estimate**, NOT a guaranteed general certificate. Likewise, the 12 dense `float64` eigenvalue evaluations via `scipy.linalg.eigvalsh` ($\min \lambda_{\min}(\mathcal{T}_1) = +6.61 \times 10^{-3}$) are **observed numerical checks on the 12 Stage-0 matrices**, NOT a general exact certificate of $\mathcal{T}_1 \succeq 0$.
- **SPD floor / HPR admissibility assumption:** Invoking `HPR-LP` Algorithm 1 (`arXiv:2611.01872`, Sec. 2.1) requires both $\mathcal{T}_1 \succeq 0$ and **strict positive definiteness** $\mathcal{M}_y = \mathcal{T}_1 + AA^* \succ 0$. Whenever Theorem 1 or Theorem 3 is invoked inside HPR, a strictly positive floor $\theta_\perp^2 > 0$ (corresponding to $s_{r+1} > 0$ in Theorem 1, or the explicit numerical floor `max(lam_perp, 1e-12)` in code) is required as an explicit assumption so that $\mathcal{M}_y \succ 0$.

## 2. Theorem 1 Strict Reduction Conditions
- **Strict metric-distance reduction (eigenspace multiplicity):** Strict inequality $\|w^0 - w^*\|_{\mathcal{M}_\sigma^{(r)}} < \|w^0 - w^*\|_{\mathcal{M}_\sigma^{(0)}}$ requires **both** $s_{r+1} < s_1$ **and** a nonzero component of $\Delta y = y^0 - y^*$ **outside the full largest-singular-value eigenspace** $\mathcal{E}_{s_1} := \ker(s_1^2 I_m - A A^\top)$ (earlier prose wrote $\Delta y \notin \operatorname{span}(u_1)$, which overlooks the case where $s_1$ has multiplicity $> 1$).
- **Separate proximal operator-norm comparison:** The strict inequality $\|\sqrt{\mathcal{T}_1^{(r)}}\|_2 = \sqrt{s_{r+1}^2 - s_m^2} < \sqrt{s_1^2 - s_m^2} = \|\sqrt{\mathcal{T}_1^{(0)}}\|_2$ is a **separate** operator-norm comparison that depends only on $s_{r+1} < s_1$ (independent of $\Delta y$). Moreover, in `HPR-LP` Theorem 2 (eq. 10b), the $\|A\|$ term inside $\sigma(\|A\| + \|\sqrt{\mathcal{T}_1}\|) + 1$ remains unchanged at $s_1$.

## 3. Theorem 2 Scope Restriction (Retain Precisely Proved Cases Only)
- **Removed unproved generalizations:** Earlier informal text in `OVERLAP_AND_SELECTION.md` mentioned arbitrary rectangular extensions $A = [M_\rho \;\; \gamma I_m]$ and arbitrary low-rank factor forms $AA^\top = (1-\rho)I_m + \rho U_k \Lambda_k U_k^\top$. Those generalized claims are **not proved** and are formally retracted.
- **Retained proved results:** Only the two equicorrelation bounds proved in `THEORY_THEOREMS_1_TO_3.md` remain in scope for $M_\rho = (1-\rho)I_m + \rho \mathbf{1}_m \mathbf{1}_m^\top$ ($m \ge 2$, $\rho \in (0,1)$):
  1. Two-sided arbitrary positive diagonal scaling on square $M_\rho$: $\kappa_2(D_r M_\rho D_c) > \frac{(m-1)\rho}{1-\rho}$.
  2. Left arbitrary positive diagonal scaling on rectangular $A$ satisfying $AA^\top = M_\rho$: $\kappa_2(D_r A) > \sqrt{\frac{(m-1)\rho}{1-\rho}}$.

## 4. Comparator Scope & Failure of Broad Speed Claims
- **Official CPU solvers are contextual only:** `HiGHS 1.16.0` (`solver="pdlp"`) and `OR-Tools 9.15.6755` (`PDLP`) reported in `stage0b_matched_spmv_ablation.*` terminate under each solver's own internal stopping rules without identical post-solve unscaled KKT certification. Their timings and iteration counts are **contextual references only**, not identically certified apples-to-apples comparisons.
- **Internal ASB reimplementation vs. official `cuPDLPx`:** The `cuPDLPx-ASB` arm in `stage0_cheap_failure_test.py` and `stage0b_matched_spmv_ablation.py` is an **internal Python/CPU ASB-inspired reimplementation** (using a shortened trailing window `asb_window=400` on Stage-0 sizes), NOT the official C/CUDA `cuPDLPx` solver.
- **Broad speed claims fail:** Static, slack-converted `Spec-HPR` fails the pre-registered Stage-0 empirical gates (`F1_FactorEq` GM `1.62× iters / 1.52× time` vs `HPR-Native` and `1.11× / 1.06×` vs internal `cuPDLPx-ASB`; severe `1.3×–2.2×` slack-conversion penalty on mixed/inequality families `F2`/`F3`/`F4`; `10.8%` probe overhead on small flat controls `F4`). No GPU leaderboard claim is supported (WSL sees an RTX 5060 Laptop GPU, with `NO_NVCC` and `NO_JULIA`).

## 5. Historical Provenance Note
Initial arXiv metadata/HTML retrieval for this frozen route used the local `literature-search-arxiv` skill (`D:/AI_Science/.licenses/literature_search_arxiv_LICENSE.txt`). That historical provenance is preserved accurately here; per coordinator policy, subsequent research routes do not invoke local skill workflows and rely on native direct reading.
