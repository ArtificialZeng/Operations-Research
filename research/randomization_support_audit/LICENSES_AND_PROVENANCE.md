# Licenses, Data Provenance & Archival Exclusions

## 1. Upstream Public Sources & Licenses (Not Redistributed in This Archive)

No third-party raw archives, datasets, `.rda`/`.dta`/`.do` files, or downloaded full-text papers are redistributed in this repository. Users reproduce local inputs directly from the official public upstream sources via the included download scripts:

1. **Trial 1 — `RockTheVote` (Green & Vavreck 2008, *Political Analysis* 16:138–152):**
   - **Official Package Source:** CRAN `pscl` v1.5.9 (`https://cran.r-project.org/src/contrib/pscl_1.5.9.tar.gz`), files `pscl/data/RockTheVote.rda` and `pscl/man/RockTheVote.Rd`, Simon Jackman et al., **GPL-2**.
   - **Cross-Referenced Archive:** Yale Dataverse CC0 (`https://dataverse.yale.edu/dataset.xhtml?persistentId=doi%3A10.60600%2FYU%2FOYIPLJ`; automated HTTP API returned HTTP 403 and was not bypassed).
   - **Attribution & Excerpt Scope:** `run_stage0_support_screen.py` contains a brief methods summary adapted from `pscl/man/RockTheVote.Rd` (GPL-2) solely as the exact frozen prompt string executed during the Stage-0 screen; no data tables or individual records are redistributed.
   - **Reproduction Script:** `fetch_pscl_rockthevote.py` (verifies exact raw CRAN tarball SHA-256 hashes `851400e2...` for `RockTheVote.rda` and `978b44ea...` for LF `RockTheVote.Rd`; Windows CRLF text write produces `0c80edd0...`).
2. **Trial 2 — `Bangladesh Mask Cluster-RCT` (Abaluck et al. 2022, *Science* 375(6577):eabi9069):**
   - **Official Archive:** Zenodo `doi:10.5281/zenodo.5703876` (`https://zenodo.org/records/5703876`, `bd-mask-rct.zip`), **CC-BY-4.0**.
   - **Privacy & Scope:** `extract_abaluck_metadata.py` downloads `< 160 KB` via HTTP Range consisting strictly of de-identified union-level aggregate tables (`union_reg_sample.dta`, `union_baseline_blood_stats.dta`), READMEs, and authors' randomization-inference `.do` scripts (`10a_reg_rand_inf_symp_sero.do`, `10b_reg_rand_inf_symp.do`, `02_bal_tests_vill.do`, `04_reg_vill_cross_rand.do`). **Zero individual survey, household, or blood-sample records are downloaded or used.** Per authors' `README.md`, villages are assigned de-identified random 7-digit codes (`union`).
3. **Open-Weights Local Models Evaluated (`BF16`, NOT Redistributed):**
   - `Qwen/Qwen2.5-1.5B-Instruct`, revision `989aa7980e4cf806f80c7fef2b1adb7bc71aa306` (**Apache-2.0**, ungated).
   - `ibm-granite/granite-3.1-2b-instruct`, revision `bbc2aed595bd38bd770263dc3ab831db9794441d` (**Apache-2.0**, ungated).
4. **First-Party Literature References Cited (Full Texts Kept Local-Only, NOT Redistributed):**
   - Gao & Xiao (2026), *"When AI Analysts Disagree: Agentic Multiverse Analysis and the Robustness of Empirical Research"*, `https://arxiv.org/html/2611.25198v1` (§4.1 & Appendix A; very close prior documenting an invalid permutation procedure used by an AI agent — no priority claimed).
   - CausalVerify (2026), `https://arxiv.org/abs/2609.07944`.
   - Bertrán, Fogliato & Wu (2026), *"Many AI analysts, one dataset: Navigating the agentic data science multiverse"*, *PNAS* (`https://pmc.ncbi.nlm.nih.gov/articles/PMC13393493/`).

---

## 2. Explicit Archival Exclusions (Kept Local-Only with SHA-256 Provenance in `MANIFEST.json`)

The following artifacts remain intact on the local research machine and are **excluded** from this git branch:
- `raw_sources/` (third-party `.rda`, `.Rd`, `.dta`, `.do`, and upstream `README.md` files)
- `literature_notes/` (downloaded HTML/XML text extracts of third-party papers)
- `STAGE0_ORACLE_CASES_12.json` and `STAGE0_MATCHED_40_CASES.json` (regenerable table subsets derived from upstream datasets; exact SHA-256 hashes sealed in `MANIFEST.json` and `stage0_screen_summary.json`)
- `stage0_screen_outputs/raw_responses_qwen25_1p5b.jsonl` and `stage0_screen_outputs/raw_responses_granite31_2b.jsonl` (full raw prompt/response payloads containing per-row prompt IDs; exact SHA-256 hashes `8aabba2e...` and `daf99f1b...` sealed in `MANIFEST.json` and `stage0_screen_summary.json`)
- `.venv/`, `__pycache__/`, Hugging Face model weights/caches, credentials, and any local steering notes.
