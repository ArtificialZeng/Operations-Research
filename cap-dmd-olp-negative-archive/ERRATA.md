# Authoritative Errata & Scope Corrections (`cap_dmd_olp_20261124`)

**Date:** 2026-11-24  
**Status:** Route **FROZEN** as a negative-method archive. All four code/JSON runs (`stage0_one_run_falsifier.*`, `stage0_v2_binding_falsifier.*`, `stage0b_asym_cap_dmd_test.*`, `stage0c_coord_drift_dmd_test.*`) are preserved **byte-for-byte** without rerunning or tuning. This errata supersedes any stronger wording in pre-freeze drafts (`SELECTION_AND_GAP.md`, `STAGE0_FALSIFIER_PROTOCOL.md`, `STAGE0_DIAGNOSTIC_AND_ASYM_HYPOTHESIS.md`).

---

## 1. v1 Nonbinding Instance Bug & Reused-Seed Exploratory Status (`v2`, `0b`, `0c`)
- **v1 (`stage0_one_run_falsifier.py` / `stage0_falsifier_results.json`) was nonbinding:** Setting `rho in [0.15, 0.35]` exceeded expected per-resource demand (`~0.078`), yielding $\mu^* \equiv 0$ and trivial `DMD Regret = 0`.
- **Reused seeds after v1:** `stage0_v2_binding_falsifier.py`, `stage0b_asym_cap_dmd_test.py`, and `stage0c_coord_drift_dmd_test.py` all reused seeds `1001..1005` after observing v1. They are strictly **exploratory diagnostics**, NOT independent held-out test evaluations.

## 2. Controlled Oracle Advice vs. Admissible / Learned Advice
- In `R1_Accurate_IID` ($\hat{\mu} = \mu^*(1 + \mathcal{N}(0, 0.01^2))$) and the uncorrupted coordinates of `R2_SparseCorrupt_IID` ($\hat{\mu}_j = \mu^*_j$), predictions were constructed directly from the **same instance's offline LP dual $\mu^*$**.
- This is **controlled oracle advice**, NOT learned or admissible out-of-sample predictions from an independent historical/training split. No claim of learned-advice performance on real/held-out prediction streams is supported.

## 3. Comparator Scope Differences vs. Primary `arXiv:2402.13530v2`
- The `An24-SA`, `An24-MainALG`, `An24-SA-Norm`, and `An24-MainALG-Norm` arms are **An24-inspired internal reimplementations**, NOT exact reproductions of Algorithms 2 and 4 of An, Li, Moseley & Visotsky (`arXiv:2402.13530v2`).
- Specifically, our code used periodic 100-step $\ell_1$-drift doubling capped at `4 * eta0 / sqrt(T)` and fixed prefix LP checkpoints `{250, 500, 1000, 2000}` comparing realized revenue against `(1 - 0.05) * OPT_{t-1}`, rather than the exact `GRD_mu` / $\epsilon(T)$-parametrized doubling and nonstationarity epoch tests of `arXiv:2402.13530v2`.

## 4. `FreeGrad` Citation, Implementation Scope, and Missing End-to-End Primal Guarantee
- **Venue correction:** Mhammedi & Koolen's `FreeGrad` was published at **COLT 2020** (not NeurIPS 2020 as misstated in `SELECTION_AND_GAP.md` and `STAGE0_DIAGNOSTIC_AND_ASYM_HYPOTHESIS.md`).
- **Implementation & constant scope:** `run_cap_dmd` normalized gradients by static $G_i = \max(\rho_i, \bar{a}_i - \rho_i)$, initialized normalized $V_0 = 1$, clamped the exponential argument at `40.0`, and applied a heuristic 1D box projection with Cutkosky–Orabona gradient zeroing; `run_asym_cap_dmd` further capped wealth at `1e6`. These prototype choices do not instantiate a formally verified end-to-end COLT 2020 theorem proof.
- **Wealth positivity is NOT an end-to-end primal guarantee:** While `Asym-CAP-DMD` maintained $1 - \beta u \ge 1/2$ and $1 - \gamma v \ge 1/2$ (`min_wealth_factor = 0.5003`), wealth positivity alone does **not** establish an end-to-end primal regret bound or a guarantee against the prediction-following benchmark (`PRD` / `OPT` under unknown arrival models).

## 5. Failure Under Strong Scale-Normalized Controls
Against strong scale-normalized baselines (`eta0_scale = 1 / mean(rho)`), all tested variants failed 3 of 4 strong gates:
- **`Asym-CAP-DMD` (`stage0b_asym_results.json`):** `R2` sparse corruption regret `582.17` vs `DMD-Norm` `369.47` and `WS-DMD-Norm` `478.72`; `R3` full poison regret `2568.48` vs `DMD-Norm` `369.47`; `R4` shift reward `6700.6` vs `DMD-Norm` `8295.9`. Only `R1` oracle advice (`72.01` vs `369.47`) passed.
- **`Sym-CAP-DMD` (`stage0b_asym_results.json`):** `R2` `608.62`, `R3` `2614.99`, `R4` reward `6341.2` — failed the same 3 of 4 strong gates.
- **`CoordDrift-DMD` (`stage0c_coord_drift_results.json`):** `R2` `276.96` vs `DMD-Norm` `369.47` (`1.33× < 1.5×` gate), `R3` `990.26` vs `369.47`, `R4` reward `6762.1` vs `8295.9` — also failed 3 of 4 strong gates.

## 6. Provenance
Zero local skill workflows were invoked in this route; primary sources were consulted natively via browser (`arxiv.org`) and native web search. No PDF generated; no publicity claims.
