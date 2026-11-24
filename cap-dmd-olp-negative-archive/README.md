# Coordinate-Wise Anchored Dual Mirror Descent for Online LP (`cap_dmd_olp_20261124`) — Frozen Negative-Method Archive

**State:** **FROZEN (2026-11-24)** — Negative-method archive; do not rerun or tune.  
**Authoritative corrections:** Read [ERRATA.md](ERRATA.md) before citing any claim or number from pre-freeze notes.

## Summary
This directory archives exploratory CPU diagnostics of symmetric (`Sym-CAP-DMD`), asymmetric two-sided ONS coin-betting (`Asym-CAP-DMD`), and empirical-Bernstein drift-gated (`CoordDrift-DMD`) coordinate-wise variants of Dual Mirror Descent for multi-resource online packing LP ($m=20$, $T=5000$).

### Why the Route Is Frozen
Once strong scale-normalized baselines (`DMD-Norm`, `WS-DMD-Norm`, and An24-inspired `An24-MainALG-Norm` with $\eta_0 = 1/\bar{\rho}$) were included, **all three proposed variants failed 3 of 4 strong gates**:

| Method (`m=20, T=5000`, exploratory seeds `1001..1005`) | `R1` Oracle Advice Regret | `R2` Sparse Corrupt (2/20) Regret | `R3` Full Poison (20/20) Regret | `R4` Shift + Poison Reward (of `10840.1`) |
|---|---|---|---|---|
| `DMD-Norm` (Balseiro–Lu–Mirrokni scaled) | 369.47 | **369.47** | **369.47** | **8295.9** |
| `WS-DMD-Norm` (scaled warm start) | 265.48 | 478.72 | 991.81 | **8295.9** |
| `An24-MainALG-Norm` (An24-inspired, scaled) | 537.50 | 483.18 | 494.33 | 7838.9 |
| `Sym-CAP-DMD` (symmetric FreeGrad prototype) | 74.03 | 608.62 | 2614.99 | 6341.2 |
| `Asym-CAP-DMD` (two-sided ONS coin betting) | 72.01 | 582.17 | 2568.48 | 6700.6 |
| `CoordDrift-DMD` (per-coord Bernstein gate) | 113.15 | 276.96 | 990.26 | 6762.1 |

Key scope caveats documented in [ERRATA.md](ERRATA.md):
- `v1` had nonbinding budgets ($\mu^* \equiv 0$); `v2`, `0b`, and `0c` reused seeds `1001..1005` (exploratory only).
- `R1` and uncorrupted `R2` coordinates used controlled **oracle** dual advice from the same instance's offline LP, not learned/admissible out-of-sample forecasts.
- `An24-*` arms are An24-inspired internal reimplementations, not exact reproductions of `arXiv:2402.13530v2` Algorithms 2 & 4.
- `FreeGrad` is COLT 2020 (Mhammedi & Koolen); wealth positivity alone is not an end-to-end primal regret proof.

## File Inventory (Relative Links)
- [STATUS.md](STATUS.md) — Final frozen status and curated staging pointer.
- [ERRATA.md](ERRATA.md) — Authoritative scope, methodology, citation, and proof-boundary errata.
- [SELECTION_AND_GAP.md](SELECTION_AND_GAP.md) — Pre-run literature note (superseded where corrected by [ERRATA.md](ERRATA.md)).
- [STAGE0_FALSIFIER_PROTOCOL.md](STAGE0_FALSIFIER_PROTOCOL.md) — Pre-run v1 protocol (nonbinding budget bug documented in [ERRATA.md](ERRATA.md)).
- [STAGE0_DIAGNOSTIC_AND_ASYM_HYPOTHESIS.md](STAGE0_DIAGNOSTIC_AND_ASYM_HYPOTHESIS.md) — Pre-0b asymmetry hypothesis note (superseded by [ERRATA.md](ERRATA.md)).
- [stage0_one_run_falsifier.py](stage0_one_run_falsifier.py) · [stage0_falsifier_results.json](stage0_falsifier_results.json) — v1 run (nonbinding budgets; preserved byte-for-byte).
- [stage0_v2_binding_falsifier.py](stage0_v2_binding_falsifier.py) · [stage0_v2_binding_results.json](stage0_v2_binding_results.json) — v2 binding exploratory run (preserved byte-for-byte).
- [stage0b_asym_cap_dmd_test.py](stage0b_asym_cap_dmd_test.py) · [stage0b_asym_results.json](stage0b_asym_results.json) — 0b asymmetric coin-betting exploratory run (preserved byte-for-byte).
- [stage0c_coord_drift_dmd_test.py](stage0c_coord_drift_dmd_test.py) · [stage0c_coord_drift_results.json](stage0c_coord_drift_results.json) — 0c coordinate-drift exploratory run (preserved byte-for-byte).

*(Zero local skill workflows used; no PDF generated.)*
