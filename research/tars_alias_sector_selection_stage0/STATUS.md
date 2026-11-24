# Status Ledger — TARS Retrospective Second-Sector Selection (Stage-0 Stop Archive)

- **Line Status:** **`STOP_STAGE0_INSUFFICIENT_SEPARABLE_AMBIGUOUS_CASES`** (frozen on 2026-11-24; zero numeric external `Prot` values read or scored).
- **Superseded Local Draft Notes:** Earlier local design/protocol drafts (`STAGE0_TARS_FEASIBILITY_RECEIPT.md`, `STAGE1_TARS_SECTOR_SELECTION_PROTOCOL.md`, `desktop_*.txt`) are superseded by this Stage-0 stop decision and are excluded from the frozen git archive.
- **Verified Native Stage-0 Artifacts:**
  - `stage0_tars_feasibility_audit.py`: `SHA-256` `118994c9cac73894361fa4490d6d28cf94740c582adb2d560e7c3e788abf26b1`
  - `stage0_ambiguity_and_shape_audit.py`: `SHA-256` `487bdcf9d40ea093d3087f721998b3c1544453711c33df4fe564f514f7dffd0b`
  - `stage0_outputs/stage0_fits_and_coverage_receipt.json`: `SHA-256` `df76c0603b74412fc0799a30ca9bbd6cec9930870556d2da85996d6b83a81919` (`13` spot-check FITS + catalog upper-coverage bounds + `0.0 s` co-located `TIME` audit)
  - `stage0_outputs/stage0_ambiguity_and_shape_summary.json`: `SHA-256` `1599fff502003c7b7727e1aad30006b18bfa452ed425b3efbbf73542d4e8aaf5` (`48` stars, `210` cohort FITS; `2/48` at `pow1 >= 0.10, pow2/pow1 >= 0.30`; `1/48` at `>= 0.40`; `0/2` disagreements vs. `max_cadences` and `farthest_temporally`)
  - `stage0_outputs/stage0_ambiguity_and_shape_stars.jsonl`: `SHA-256` `9086b148969a21e3cf83cb2787ee044628510c3a041b0b1b4e43b3adca4a8f67` (`48` star records; zero numeric `Prot` values)
- **Archive Target:** `research/tars_alias_sector_selection_stage0/` in `ArtificialZeng/Operations-Research` on clean branch `archive/tars-alias-sector-selection-stage0-20261124` from `main` (`940709d372ae3716e09daf771d5438d07232d022`).
- **PR Status:** No native authenticated GitHub PR tool (`NO_GH_CLI`, `list_plugin_accounts`: none); draft PR handoff prepared via local `PR_HANDOFF.md`, `PR_TITLE.txt`, and `PR_BODY.md`.
