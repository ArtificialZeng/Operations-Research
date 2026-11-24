# Spectral Semi-Proximal Preconditioning for First-Order LP (`spectral_hpr_lp_20261124`) — Frozen Negative-Method Archive

**State:** **FROZEN (2026-11-24)** — Negative-method archive; do not scale.  
**Authoritative corrections:** See [ERRATA.md](ERRATA.md) for all scope, proof, and comparator corrections superseding pre-freeze wording.

## Summary
This directory archives a bounded Stage-0 investigation of replacing the scalar semi-proximal operator $\mathcal{T}_1^{(0)} = \lambda_A I_m - AA^*$ in Restarted `HPR-LP` (`doi:10.1007/s12532-025-00292-0`; `arXiv:2611.01872`) with a static, slack-converted, rank-$r$ non-diagonal spectral semi-proximal operator $\mathcal{T}_1^{(r)} = \mathcal{M}_y^{(r)} - AA^*$.

- **What holds (within corrected scope of `ERRATA.md`):**
  - Exact Loewner dominance and metric reduction outside the full top-singular-value eigenspace $\ker(s_1^2 I_m - AA^\top)$ (Theorem 1, with SPD floor $s_{r+1} > 0$).
  - Exact equicorrelation diagonal-preconditioning lower bounds for square $D_r M_\rho D_c$ and left-scaled rectangular $D_r A$ with $AA^\top = M_\rho$ (Theorem 2; unproved arbitrary $U_k$ and $[M_\rho, \gamma I]$ generalizations retracted).
  - Exact Schur-complement PSD sufficient condition given a genuine upper bound $\theta_\perp^2 \ge \|P_\perp A\|_2^2$ (Theorem 3, with SPD floor $\theta_\perp^2 > 0$). In code, $\theta_\perp^2$ is estimated heuristically via finite power/Ritz lower estimates $\times 1.02$, and the 12 dense `float64` eigenvalue checks ($\min \lambda_{\min}(\mathcal{T}_1) = +6.61 \times 10^{-3}$) are observed numerical checks on those 12 matrices, not a general exact certificate.
- **Why the route is frozen (broad speed claims fail):**
  - Pre-registered Stage-0 empirical gates failed (`F1_FactorEq` GM `1.62× iters / 1.52× time` vs `HPR-Native`, `1.11× / 1.06×` vs internal ASB-inspired reimplementation `cuPDLPx-ASB`; `F4_FlatControl` auto-gate overhead `1.108× > 1.05×`).
  - Converting inequality constraints to standard equality form with slacks imposed a `1.3×–2.2×` iteration and sparse-pass penalty (`HPR-Slack` vs `HPR-Native`), wiping out spectral gains on mixed (`F2_LinkedMCF`) and inequality (`F3_FactorIneq`) LPs.
  - Contextual CPU runs of official `HiGHS 1.16.0 PDLP` and `OR-Tools 9.15 PDLP` (under each solver's own stop rules, without matched post-solve KKT certification) further confirm strong adaptive/active-set dominance on inequality-coupled LPs (`f3_ineq_m500_k8`), while showing isolated wins for `Spec-HPR` only on high-spike equality-only instances (`f1_eq_m500_k8`).
  - CPU prototype results do not establish any GPU leaderboard claim (WSL sees `RTX 5060 Laptop 8 GiB`, with `NO_NVCC` and `NO_JULIA`).

## File Inventory
- [STATUS.md](STATUS.md) — Final frozen status and archival pointer.
- [ERRATA.md](ERRATA.md) — Authoritative scope, theorem, comparator, and provenance errata.
- [OVERLAP_AND_SELECTION.md](OVERLAP_AND_SELECTION.md) — Primary-literature overlap audit (read together with `ERRATA.md` Section 3).
- [THEORY_THEOREMS_1_TO_3.md](THEORY_THEOREMS_1_TO_3.md) — Proofs of Theorems 1–3 (read together with `ERRATA.md` Sections 1–3).
- [STAGE0_PROTOCOL.md](STAGE0_PROTOCOL.md) — Sealed pre-run protocol (byte-for-byte untouched).
- [stage0_cheap_failure_test.py](stage0_cheap_failure_test.py) — Sealed Stage-0 benchmark script (byte-for-byte untouched).
- [stage0_results.json](stage0_results.json) — Sealed Stage-0 results JSON (byte-for-byte untouched).
- [STAGE0_DIAGNOSTIC_RESULT.md](STAGE0_DIAGNOSTIC_RESULT.md) — Stage-0 outcome report.
- [stage0b_matched_spmv_ablation.py](stage0b_matched_spmv_ablation.py) — Matched internal SpMV-counted ablation + contextual official CPU PDLP script (untouched).
- [stage0b_matched_spmv_ablation.json](stage0b_matched_spmv_ablation.json) — Stage-0b compact JSON results (untouched).
- [STAGE0B_SPMV_ABLATION.md](STAGE0B_SPMV_ABLATION.md) — Stage-0b SpMV ablation and hardware/comparator summary.

## Reproduction (CPU, Single-Threaded, Read-Only Reference)
```powershell
$env:OMP_NUM_THREADS="1"; $env:MKL_NUM_THREADS="1"; $env:OPENBLAS_NUM_THREADS="1"
uv run --python 3.12 --with numpy --with scipy --with highspy python stage0_cheap_failure_test.py
uv run --python 3.12 --with numpy --with scipy --with highspy --with ortools python stage0b_matched_spmv_ablation.py
```
*(No PDF generated; historical prior use of `literature-search-arxiv` documented in `ERRATA.md` Section 5.)*
