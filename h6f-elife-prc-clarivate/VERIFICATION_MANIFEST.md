# VERIFICATION MANIFEST — H6f `/boost` Flagship Build

**Project:** Intrinsic Revision Norms and Asymmetric Impact-Factor Dependence: Causal Evidence from the *eLife* Publish-Review-Curate Experiment and Clarivate's 2024 Delisting, 2021–2026
**Workspace:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126`
**Build Date:** 2026-11-26

## 1. Data Completeness & Alignment Invariants

- **Complete *eLife* PRC Census (`2023–2026`):** `N = 4,551` unique PRC papers.
- **True `v1` Assessment Recovery:** `4,541 / 4,551` (`99.78%`).
- **Zero `VoR`-Date Contamination:** `0` missing `v1` dates; `0` VoR-before-`v1` anomalies across `3,264` VoRs.
- **Live *eLife* Reader Telemetry (`page-views` & `downloads`):** `2,653 / 2,653` (`100.00%`) lifetime totals (`totalValue`, HTTP 200 verified); strictly untruncated monthly telemetry (`v1 >= 2023-11`, complete months `<= 2026-10`) = `1,852` (`801` left-truncated pre-Nov-2023 articles explicitly excluded from monthly rate models); clean local VoR event-study sample = `1,701`.
- **Expanded Clean OpenAlex Benchmark Panel (`2021H1–2026H1`):** Strict Primary `N = 30` clean journals (`>= 90%` TRUE geo coverage every half-year; min 1-sided `p = 0.0333`); Expanded Sensitivity `N = 35` (`mean >= 90%, min >= 85%`; min 1-sided `p = 0.0286`); `20` noisy/throttled candidates excluded transparently.
- **Live Crossref DOI Bibliography Verification:** `29 / 29` peer-reviewed DOIs verified HTTP 200 via `api.crossref.org/works/{doi}`.

## 2. Headline Empirical Receipts (Dynamically Extracted from JSON)

| Pillar | Estimator / Specification | Verified Estimate | Inference |
| :--- | :--- | ---: | :--- |
| **P1: Revision Norms** | `v1_Incomplete` VoR conversion & upgrade share | `82.3%` VoR; `81.2%` any (`78.3%` Solid+) | Mean lag `325.4` days (`N = 964`) |
| **P1: ESCI Solid-Cliff** | Fixed 450d Subject-FE DiD (`Post` vs `Pre` ESCI) | `+0.40` pp | `SE = 2.48`, `t = +0.16`, `p = 0.8729`, `p_WCB = 0.8640` |
| **P2: First-Impression Stigma** | True `v1_Incomplete` -> Post-`v1` OA Cites (PPML, `G=18`) | `-14.45%` (`beta=-0.1561`) | `t = -5.11`, `p = 8.67e-05` |
| **P2: VoR-Date Autopsy** | Flawed `VoR`-date `fin_Incomplete` -> OA Cites (PPML) | `+0.66%` (`beta=+0.0066`) | `t = +0.11`, `p = 0.9152` (erased!) |
| **P2: Reader Salience (`v1`)** | True `v1_Sig_Important` -> eLife Page-Views (PPML, `G=18`) | `+10.03%` (`beta=+0.0956`) | `t = +4.09`, `p = 0.0008` |
| **P2: Upgrade -> OA Cites** | Within `v1_Incomplete` VoRs: `Solid+` vs `Unchanged` (PPML, `G=18`) | `+3.18%` | `t = +0.46`, `p = 0.6540`, TOST `±20% p = 0.0125` |
| **P2: Upgrade -> Clean Views DiD** | Untruncated `v1 >= 2023-11` Monthly Rate DiD (`N=544`, `G=18`) | `+0.0577` log | `t = +1.14`, `p_WCB = 0.2555`, TOST `±15% p = 0.0426` |
| **P2: Local VoR Event Study** | Month `t=0` / Post `t=+1..+6` Views DiD (`N=619`, `G=17`) | `+0.0013` / `-0.1028` | `p_WCB = 0.9840` / `0.1710` (uniform VoR spike `+1.11` vs `+1.11`) |
| **P2: Version-Release Effect** | Per Extra Published Version (`cr_n_versions`, M`12–21`, `G=18`) | `+0.2341` log | `t = +2.83`, `p = 0.0116` |
| **P3: Editorial Cushioning** | 500-`eid` Acceptance Rate Jump (`eid >= 104,000`) | `15.44% -> 20.06%` (`+4.63` pp) | `HAC t = +3.41`, `Perm p = 0.0002`, `Sup-Wald F = 53.14` |
| **P3: Expanded SC (`log_n_all`)** | Unique Min-L2 ADH SC (`25H1–26H1` vs `23H2–24H2`) | `-0.5519` (`N=30`) / `-0.5407` (`N=35`) | Rank `1/30` (`p = 0.0333`); Exp35 Rank `1/35` (`p = 0.0286`) |
| **P3: Expanded SC (`log_n_CN`)** | Unique Min-L2 ADH SC China Output (`25H1–26H1`) | `-1.0913` (`N=30`) / `-1.0977` (`N=35`) | Rank `1/30` (`p = 0.0333`); Exp35 Rank `1/35` (`p = 0.0286`) |
| **P4: Blog Cross-Validation** | OpenAlex Phase-2 DiD vs *eLife* March 2026 Blog (`N=9`) | Spearman `rho = 0.6833` | `p = 0.0424` (Pearson `r = 0.4514`) |
| **P4: JIF vs DORA Regimes** | JIF-Codified (`CN,IT,ES`) vs DORA-Reformed (7 nations) | `-57.8%` vs `-36.6%` | Exact Perm 1-sided `p = 0.0167` (2-sided `p = 0.0167`) |

## 3. Reproducibility & Gate Checklist

- `ruff check scripts tests`: **0 errors**
- `pytest -v tests/test_h6f_boost.py`: **100% passing** (including non-nested LSDV WCB equivalence, rolling-window anti-truncation guard, SC uniqueness, GLM convergence, full Table 1–4 CSV/JSON parity, co-occurring body citation parity, zero-leak PDF, and live disk SHA-256)
- `manuscript_h6f_boost.pdf`: **0 leaked LaTeX/Markdown tokens**, visually verified across pages
- `SHA256SUMS.json`: **100% exact match** with live disk `Path.read_bytes()`
