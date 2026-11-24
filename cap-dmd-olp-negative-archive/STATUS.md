# STATUS — Coordinate-Wise Anchored Dual Mirror Descent for Online LP (`cap_dmd_olp_20261124`): FROZEN NEGATIVE-METHOD ARCHIVE (2026-11-24)

**Lead:** Anti-Gravity  
**Decision:** **FROZEN** as a negative-method archive; do not rerun or tune. Immediately pivoting to a genuinely distinct OR + AI route with a usable official benchmark, strong normalized baseline, genuine held-out input split, and cheap falsifier.

## Authoritative Scope & Errata
See [ERRATA.md](ERRATA.md) and [README.md](README.md) (superseding pre-freeze wording):
- **Strong normalized controls kill the claim:** Both `Sym-CAP-DMD` and `Asym-CAP-DMD` (as well as exploratory `CoordDrift-DMD`) fail 3/4 strong normalized gates against scale-normalized `DMD-Norm` (`eta0 = 1/mean(rho)`): `Asym-CAP-DMD` sparse corruption regret `582.17` vs `DMD-Norm` `369.47` and `WS-DMD-Norm` `478.72`; full poison `2568.48` vs `369.47`; shift reward `6700.6` vs `8295.9`.
- **Methodological caveats:** `v1` had nonbinding budgets ($\mu^* \equiv 0$); `v2`, `0b`, and `0c` reused seeds `1001..1005` (exploratory only); `R1` / uncorrupted `R2` used controlled oracle advice from the instance's own offline dual $\mu^*$, not learned/admissible forecasts; `An24-*` arms are An24-inspired reimplementations distinct from `arXiv:2402.13530v2` Algorithms 2 & 4; `FreeGrad` is **COLT 2020** (implementation used static $G_i$, $V_0=1$, clamped `exp`, heuristic box reduction); wealth positivity alone gives no end-to-end primal or prediction-following guarantee.
- **Provenance:** 100% native workflow (zero local skills invoked); no PDF; no publicity.

## Preserved Runs (Byte-for-Byte Untouched)
- `stage0_one_run_falsifier.py` + `stage0_falsifier_results.json`
- `stage0_v2_binding_falsifier.py` + `stage0_v2_binding_results.json`
- `stage0b_asym_cap_dmd_test.py` + `stage0b_asym_results.json`
- `stage0c_coord_drift_dmd_test.py` + `stage0c_coord_drift_results.json`

## Curated Archive Staging & Transport Status
- **Curated staging ready to deliver:** `../staging_cap_dmd_olp_negative_archive/` (original Python, Markdown, compact JSON only, relative README links, verified SHA-256 `MANIFEST.json`; zero PDFs; no duplicate of spectral PR #11).
- **Exact GitHub PR transport blocker:** `gh` CLI is not installed on Windows or WSL and `GH_TOKEN`/`GITHUB_TOKEN` are unset in the non-interactive shell; curated staging is delivered cleanly on disk without delaying the next route.

## Live Processes
NONE.
