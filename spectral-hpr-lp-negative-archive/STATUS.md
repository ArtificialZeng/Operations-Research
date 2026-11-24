# STATUS — Static/Slack-Converted Spectral HPR (`spectral_hpr_lp_20261124`): FROZEN NEGATIVE-METHOD ARCHIVE (2026-11-24)

**Lead:** Anti-Gravity  
**Decision:** **FROZEN** as a negative-method archive; do not rerun Stage 0 or scale. Immediately pivoting to a genuinely distinct OR + AI frontier route.

## Authoritative Scope & Errata
All scope corrections are recorded in [ERRATA.md](ERRATA.md) and [README.md](README.md) (superseding any stronger pre-freeze wording):
1. **Theorem 3 & numerical checks:** Theorem 3 requires a genuine upper bound $\theta_\perp^2 \ge \|P_\perp A\|_2^2$ plus a strictly positive SPD floor $\theta_\perp^2 > 0$ when invoking HPR ($\mathcal{M}_y = \mathcal{T}_1 + AA^* \succ 0$). The implementation uses finite power/Ritz **lower** estimates $\times 1.02$ (a **heuristic upper-bound estimate**), and the 12 dense `float64` eigenvalue checks ($\min\lambda_{\min}(\mathcal{T}_1) = +6.61\times 10^{-3}$) are **observed numerical checks**, not a general exact certificate.
2. **Theorem 1 strictness:** Strict metric reduction requires $s_{r+1} < s_1$ and a nonzero component of $\Delta y$ outside the **full** top-singular-value eigenspace $\ker(s_1^2 I_m - AA^\top)$ (allowing top multiplicity $> 1$). Strict reduction of $\|\sqrt{\mathcal{T}_1^{(r)}}\|_2$ is a separate comparison ($s_{r+1} < s_1$, while $\|A\| = s_1$ is unchanged).
3. **Theorem 2 scope:** Retains only the precisely proved equicorrelation bounds for two-sided $D_r M_\rho D_c$ and left-scaled rectangular $D_r A$ ($AA^\top = M_\rho$). Unproved generalizations to arbitrary $U_k$ or $[M_\rho, \gamma I]$ are removed.
4. **Comparators & broad speed claims:** Official CPU `HiGHS 1.16.0 PDLP` and `OR-Tools 9.15 PDLP` timings use each solver's own stop rules without identical post-solve KKT certification and are **contextual only**. The internal `cuPDLPx-ASB` arm is an **ASB-inspired Python reimplementation** (`asb_window=400`), distinct from official `cuPDLPx`. **Broad speed claims fail** (pre-registered empirical gates failed due to `1.3×–2.2×` slack-conversion penalty on inequalities and ASB/adaptive column-exclusion dominance; CPU prototype results do not establish any GPU leaderboard; WSL sees `RTX 5060 Laptop 8 GiB` with `NO_NVCC` and `NO_JULIA`).
5. **Provenance:** Initial arXiv lookups for this frozen route historically used the `literature-search-arxiv` skill (`D:/AI_Science/.licenses/literature_search_arxiv_LICENSE.txt`). Subsequent routes do not invoke local skill workflows and read primary sources natively.

## Sealed Stage-0 & Stage-0b Files (Byte-for-Byte Untouched)
- `STAGE0_PROTOCOL.md` sha256 `e00c2be981162f0b41f25524275ab0cbb936bf0601cfb38cbc5a186260662d42`
- `stage0_cheap_failure_test.py` sha256 `95fbc47a070e466a373dbaedbf73818f06f8c245da2397e46dcb3282e76f1bd7`
- `stage0_results.json` sha256 `4612cc9fbe7c618cd26fc8edf0ead4566f9d663eb75b915ec46f7587b70aad56`
- `stage0b_matched_spmv_ablation.py`, `stage0b_matched_spmv_ablation.json` (untouched post-run)

## Archival Staging / Draft PR Status
- **Curated staging ready to deliver:** [staging_spectral_hpr_lp_negative_archive](MANIFEST.json) — 12 curated original Python, Markdown, and compact result JSON files (`256,358` bytes total, zero PDFs) plus verified `MANIFEST.json` (all 3 sealed Stage-0 SHA-256 hashes verified byte-for-byte identical).
- **Exact draft PR transport blocker (`ArtificialZeng/Operations-Research`, suggested branch `archive/spectral-hpr-lp-negative-20261124`):** Read-only `git ls-remote` succeeds, but `gh` CLI is not installed on Windows or WSL and neither `GH_TOKEN` nor `GITHUB_TOKEN` is set in the non-interactive shell environment; archival upload is not allowed to block the next research route.

## Live Processes
NONE.
