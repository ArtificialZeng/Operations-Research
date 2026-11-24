# Stage-0 Cheap Failure Test Outcome (`spectral_hpr_lp_20261124`)

**Date:** 2026-11-24  
**Verdict:** **STAGE-0 FALSIFIER TRIGGERED (FAIL ON EMPIRICAL GATES; PASS ON EXACT MATHEMATICAL CERTIFICATES) — ROUTE PAUSED / DO NOT SCALE.**  
**Execution:** Single-threaded CPU (`float64`, `OMP/MKL/OPENBLAS_NUM_THREADS=1`, Python 3.12 via `uv`, `numpy 2.5.5`, `scipy 1.18.1`, `highspy` / HiGHS 1.16.0).  
**Sealed Artifacts (untouched post-run):**
- `STAGE0_PROTOCOL.md` sha256 `e00c2be981162f0b41f25524275ab0cbb936bf0601cfb38cbc5a186260662d42`
- `stage0_cheap_failure_test.py` sha256 `95fbc47a070e466a373dbaedbf73818f06f8c245da2397e46dcb3282e76f1bd7`
- `stage0_results.json` sha256 `4612cc9fbe7c618cd26fc8edf0ead4566f9d663eb75b915ec46f7587b70aad56`

---

## 1. Pre-Registered Gate Summary

| Gate | Requirement | Observed | Verdict |
|---|---|---|---|
| **Exact Certificates (Theorems 1–3)** | 0 violations of Thm 2 over 1,000 random $(D_r, D_c)$; 100% $\lambda_{\min}(\mathcal{T}_1^{(r,\text{cert})}) \ge -10^{-11}$; HiGHS obj match | Thm 2: **0/1000 violations** (LB `63.0`, identity `65.0`, min random `1.19e6`, rank-1 $\|\mathcal{T}_1\|_2 = 4.55\times 10^{-13}$); Thm 3: **12/12 strictly PSD** ($\min \lambda_{\min}(\mathcal{T}_1) = +6.61\times 10^{-3}$); all solved KKT runs match HiGHS to $\le 1.5\times 10^{-5}$ | **PASS** |
| **Falsifier 1 (`F1_FactorEq` home turf)** | GM iter speedup $\ge 2.0\times$ and GM wall speedup $\ge 1.5\times$ vs **both** `HPR-Native` and `cuPDLPx-ASB` at $10^{-6}$ | `Spec-HPR` vs `HPR-Native`: **1.62× iters / 1.52× time**; vs `cuPDLPx-ASB`: **1.11× iters / 1.06× time** | **FAIL** |
| **Falsifier 2 (`F2`/`F3` mixed & ineq, `F4` flat control)** | Slack conversion must not erase gain on `F2`/`F3`; `Spec-HPR-Auto` overhead on `F4` $\le 1.05\times$ | `F2_LinkedMCF`: **0.87×** vs Native (`0.81×` vs ASB); `F3_FactorIneq`: **0.87×** vs Native (`0.42×` vs ASB); `F4_FlatControl`: `Auto/Native = 1.108×` ($>1.05\times$) | **FAIL** |

---

## 2. Per-Instance Diagnostic Table (`tol = 1e-6`, `max_iter = 25,000`, total wall-clock includes setup)

| Instance (Family) | Certified Ratio $\hat{s}_1/\tilde{\theta}$ | `HPR-Native` it (time) | `HPR-Slack` it (time) | `cuPDLPx-ASB` it (time, max $\eta/\eta^0$) | `OnlineDiag` it (time) | `Spec-HPR` it (time, 1e-4 it) | `Spec-Auto` it (time, gate) |
|---|---|---|---|---|---|---|---|
| `f1_eq_m300_k1` (`F1`) | 1.78 | 6,080 (0.243s) | 6,080 (0.222s) | **3,160 (0.130s, 2.09×)** | 6,120 (0.283s) | 4,480 (0.191s, 1,360) | 4,480 (0.190s, True) |
| `f1_eq_m400_k4` (`F1`) | 2.78 | 18,320 (1.182s) | 18,320 (1.125s) | 11,320 (0.746s, 3.05×) | 16,960 (1.227s) | **7,440 (0.513s, 1,960)** | **7,440 (0.511s, True)** |
| `f1_eq_m500_k8` (`F1`) | 4.66 | MAX 25k (3.174s) | MAX 25k (3.079s) | MAX 25k (3.202s, 2.38×) | MAX 25k (3.383s) | **19,560 (2.634s, 680)** | **19,560 (2.597s, True)** |
| `f2_mcf_small` (`F2`) | 1.11 | 5,120 (0.155s) | 3,920 (0.110s) | 3,880 (0.122s, 1.52×) | 5,000 (0.182s) | **3,520 (0.115s, 920)** | 5,120 (0.163s, False) |
| `f2_mcf_med` (`F2`) | 1.31 | **2,160 (0.087s)** | 2,680 (0.100s) | 2,120 (0.088s, 2.19×) | 2,240 (0.106s) | 2,360 (0.106s, 1,400) | 2,160 (0.101s, False) |
| `f2_mcf_large` (`F2`) | 1.48 | **3,560 (0.164s)** | 7,960 (0.337s) | 3,560 (0.168s, 1.92×) | 5,200 (0.274s) | 5,720 (0.280s, 2,680) | 3,560 (0.181s, False) |
| `f3_ineq_m300_k2` (`F3`) | 1.95 | 1,080 (0.049s) | 1,320 (0.057s) | **640 (0.032s, 3.23×)** | 1,080 (0.056s) | 1,280 (0.069s, 480) | 1,280 (0.069s, True) |
| `f3_ineq_m400_k4` (`F3`) | 2.81 | 1,800 (0.126s) | 3,360 (0.226s) | **1,320 (0.096s, 5.99×)** | 1,720 (0.134s) | 1,440 (0.129s, 1,240) | 1,440 (0.130s, True) |
| `f3_ineq_m500_k8` (`F3`) | 4.28 | 17,560 (2.261s) | MAX 25k (3.175s) | **3,920 (0.524s, 17.24×)** | 20,440 (2.818s) | 17,840 (2.408s, 2,160) | 17,840 (2.405s, True) |
| `f4_flat_eq300` (`F4`) | 1.00 | 3,960 (0.120s) | 3,960 (0.108s) | **3,680 (0.115s, 1.17×)** | 3,960 (0.146s) | 4,240 (0.135s, 680) | 3,960 (0.130s, False) |
| `f4_flat_mix400` (`F4`) | 1.00 | **6,880 (0.228s)** | 12,160 (0.373s) | 8,360 (0.284s, 1.26×) | 7,120 (0.284s) | 12,760 (0.444s, 680) | 6,880 (0.242s, False) |
| `f4_flat_ineq400` (`F4`) | 1.00 | 1,840 (0.065s) | 2,400 (0.082s) | **1,560 (0.058s, 1.43×)** | 1,840 (0.077s) | 2,640 (0.106s, 840) | 1,840 (0.078s, False) |

---

## 3. Root-Cause Scientific Diagnosis (Why Stage 0 Failed Empirically Despite Valid Theory)

The bounded Stage-0 experiment cleanly separated **three distinct mechanisms**:

1. **Where `Spec-HPR` genuinely works (high-spike equality LPs, $s_1/\tilde{\theta} \ge 2.7$):**
   - On `f1_eq_m400_k4` (ratio 2.78): `Spec-HPR` beats `HPR-Native` by **2.46× iters / 2.30× time** and beats `cuPDLPx-ASB` by **1.52× iters / 1.45× time**.
   - On `f1_eq_m500_k8` (ratio 4.66): **only** `Spec-HPR` reaches $10^{-6}$ within 25,000 iterations (`19,560 iters, 2.63s`); all four baselines hit `MAX_ITER = 25,000`. Notably, `Spec-HPR` reaches $10^{-4}$ in **680 iterations** versus `HPR-Native` (2,000) and `cuPDLPx-ASB` (17,200 — a **25× speedup to $10^{-4}$**).
2. **Structural Failure Mode 1 — Severe Slack-Conversion Penalty on Mixed & Inequality LPs:**
   - Comparing `HPR-Slack` ($r=0$) directly against `HPR-Native` ($r=0$) exposes a **1.3×–2.2× iteration penalty** purely from converting inequalities $Ax \le b$ to equalities $Ax - s = 0, s \le b$: `f2_mcf_large` (`3,560 → 7,960`), `f3_ineq_m400_k4` (`1,800 → 3,360`), `f3_ineq_m500_k8` (`17,560 → >25,000`), `f4_flat_mix400` (`6,880 → 12,160`).
   - Although `Spec-HPR` consistently beats `HPR-Slack` whenever $\hat{s}_1/\tilde{\theta} \ge 2.0$ (`f3_ineq_m400_k4`: `3,360 → 1,440`, **2.33×**; `f3_ineq_m500_k8`: `>25,000 → 17,840`, **>1.40×**), the slack-conversion penalty eats the spectral gain relative to `HPR-Native`!
3. **Structural Failure Mode 2 — Column-Exclusion Dominance of `cuPDLPx` ASB:**
   - Even on equality-only LPs where *zero* rows can be excluded from $B$, `cuPDLPx-ASB` can exclude **clamped primal variables** from $F$. When the spectral spike comes from dense factor columns that clamp at $[0, u]$ (`f1_eq_m300_k1`, `f3_ineq_m500_k8`), ASB excludes those columns and achieves a **2.09×–17.24×** scalar step-size boost on $A_{B,F}$ without paying any slack-conversion penalty.
   - Conversely, on `f4_flat_control` (small $m \le 400$, 65–228 ms total runtime), the fixed randomized-SVD probe (~12 ms) accounts for ~10.8% overhead, violating the $\le 5\%$ overhead gate on tiny solves.

---

## 4. Decision & Re-Open / Pivot Rule
- **Action:** **DO NOT SCALE** slack-converted static `Spec-HPR` to large LP suites or CUDA. Keep Theorems 1–3 and `stage0_results.json` archived as an exact theoretical + diagnostic negative checkpoint.
- **Single Re-Open Criterion (if staying on FOM LP):** Re-open only with a concrete, **slack-free** mechanism (applying rank-$r$ spectral $\mathcal{M}_y^{(r)}$ natively without slack-conversion degradation — e.g., equality-block-only or active-set-combined spectral operator on free-variable/unclamped equality submatrices where `cuPDLPx-ASB` cannot exclude either rows or columns) and a fresh pre-registered falsifier.
- **Recommended Pivot:** Pivot to a distinct OR & AI frontier route with no active-set-boost or slack-conversion entanglement (for example: **Decision-Focused Learning under Uncertain Constraints** extending `arXiv:2505.22881` / `arXiv:2510.04951`, or **Learning-Augmented Online Resource Allocation / Online LP with Untrusted Predictions**).
