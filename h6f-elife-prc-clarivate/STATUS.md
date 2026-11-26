# STATUS — H6f `/boost` Flagship Build (`v2` Major Revision)

- **Project:** `#5 H6f` — *Voluntary Revision and Asymmetric Impact-Factor Dependence: Evidence from the eLife Publish-Review-Curate Experiment and Clarivate's 2024 Delisting, 2021–2026*
- **Build Date:** 2026-11-26 (Major Revision `v2`)
- **Status:** `VERIFIED_READY_FOR_COORDINATOR_FREEZE`
- **Manuscript Markdown:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126\manuscript_h6f_boost.md`
- **Compiled PDF:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126\manuscript_h6f_boost.pdf`
- **Referee Response:** `D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126\REFEREE_RESPONSE_v2.md`
- **Sealed Directories Touched:** None (`0` writes outside workspace)
- **Git Commits / PRs Created:** None (deferred to coordinator freeze / Draft PR #26)

## Completed Gates (`v2`)

- [x] Isolated `.venv` inside workspace with all required packages
- [x] **Code Bug Fix (`scripts/04_pillar1_2_revision_and_attention.py`)**: Aligned `post_esci` strictly to `v1_dt >= 2024-12-19` with Oct 1–Dec 18, 2024 transition donut excluded (+ sensitivities at `>= 2025-01-01`, `>= 2024-10-24` suspension date, and clean `2023`-only pre-cohort); replaced VoR-conditioned primary estimand with **unconditional ITT across all `v1` *Incomplete* preprints** (`P(VoR)`, `P(Solid+)`, `P(Unrevised <Solid)`) + **Kaplan–Meier / Aalen–Johansen competing-risks CIF** handling right-censoring transparently; retracted overclaims on ESCI/intrinsic norms
- [x] **Exact Denominators, Calendar Intervals & Transparent TOST**: Reported full funnel (`4,541/4,551` -> `964` -> `793` [`82.3%`] -> `644` [`81.2%` of VoRs; `66.8%` of all `964` `v1` *Incomplete* preprints]), defined `325.4` days explicitly as `v1`-to-VoR calendar-date interval, and reported both citation TOST bounds (`±20% p = 0.0125`, `±15% p = 0.0508` just above `0.05`) with 95% CIs and exact observation horizons
- [x] **Clean Separation of Submissions vs. Published Output vs. Policy-Label Groupings**: Contextualized `-56.3%` `eid` submission velocity against *eLife*'s official `6,396 -> 2,853` (`-55.4%`) baseline, clearly labeled Synthetic Control as published output (`Rank 1/30`, `Rank 1/35`), framed `-21.2` pp transparently as a small-sample `3` JIF-codified vs. `7` DORA-reformed comparison, and added explicit identification boundaries in Limitations
- [x] `5` 300-DPI PNG + vector PDF figures regenerated and visually inspected via `read_file`
- [x] `29/29` peer-reviewed bibliography DOIs live-verified HTTP 200 via Crossref API (`100%` co-occurring author+year body-text citations)
- [x] `manuscript_h6f_boost.pdf` compiled with `0` leaked tokens and visually inspected via rendered PNG pages
- [x] `REFEREE_RESPONSE_v2.md`, `VERIFICATION_MANIFEST.md`, and `SHA256SUMS.json` generated cleanly from live disk bytes
- [x] `ruff check scripts tests` (`0` errors) and `pytest -v tests/test_h6f_boost.py` (`100%` passing)
