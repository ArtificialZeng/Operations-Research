# Status — LinePilot Axis-Calibration Dev Pilot Archive (FROZEN)

- **State:** `FROZEN_LIMITED_DEV_ARCHIVE_GATE_FAILED` (2026-11-24; stop rule honored — no retuning, no held-out selection/download/scoring, no PDF/paper/leaderboard/news/novelty claims).
- **Workspace:** `D:\AI_Science\antigravity\linepilot_axis_calibration_stage0_20261124`
- **Pinned Public Sources (Apache-2.0 / CC BY 4.0):**
  - Benchmark: `LinePilot/DigitizerBench` (`8b4a3190d5991414dad92049671de75754dd9f44`, Apache-2.0)
  - Baseline Code: `RayanA07/LinePilot` (`8fb89a62fb0565290b72ba61cb073d732d8e7578`, `v2.17.1`, single-slot CLI, Apache-2.0)
  - Paper Protocol: `arXiv:2609.19377v1` (§3.1, §4.3, Table 3, CC BY 4.0)
  - Workspace-only portable OCR: vendored Tesseract `v5.5.3.20260724` (`PORTABLE_OCR_RECEIPT.json`, `a8f3d81f...`; zero global install/PATH/registry changes)

## Sealed Stage-0 Receipt (Fixed-Tracker Oracle Bottleneck Diagnostic — Separate from Deployed Arms)
- **Protocol:** `STAGE0_LINEPILOT_PROTOCOL.md` (`b05506fb7c112e35d16075cf052041019a7ce55198f868d90ae2fd081e9ec518`, preserved unmodified)
- **Native Run:** `PID = 53928` | CPU-only | Wall `26.58 s` | Summary SHA-256: `74aedcb5a9c98bdad37cf1ddb102b540f00111b0c29b77b4f526c72081f3eaf5`
- **Results (`N = 30` balanced single-line non-bridge dev split; `2,470` Full `base_id`s untouched):**
  - Released Default OCR (`Arm A`): `FPC-NRMSE = 0.937580`, `TU = 3/30` (`4/4` valid outputs verified `0.0 px` pixel-identical; errors: `14` snap-to-black, `7` OCR missing ticks, `5` degenerate endpoints).
  - Separate Diagnostic Oracle-Axis (`Arm B`): `FPC-NRMSE = 0.119598`, `TU = 30/30` (`30/30` verified `0.0 px` pixel-identical); paired delta `+0.817982`, `+27/30` TU -> Stage-0 feasibility gate `PASS`.
- **Revisions Disclosed:** Persistent HTTP-Range transport (`KeepAliveRangeClient`, `9.09 MB`, `30/2,980` row groups); first-run interruption on `[03/30] A0250__single__matplotlib` (`zero_span_confinement=True`) fixed via scoped denominator-only patch (`eval_digitizerbench_sec43.py`: `d4c59352... -> b0f1aea6...`; `run_linepilot_stage0_diagnostic.py`: `5b19cc0f... -> 13bc671f...`).

## Sealed Stage-1 Receipt (Dev-Only Deployed Matched-Call-Budget Pilot — Gate FAILED)
- **Protocol:** `STAGE1_DEV_PROTOCOL.md` (`27922a5722704aefd77344e69dc243eeba8fbb987bf74a53ab9f0cf38ce5e916`, preserved unmodified)
- **Calibration Engine:** `stage1_axis_calibration.py` (`3f6d8c957cece1b9a4c2f3b0e1087bc09fc576b2d2230ec44de8749c5ea9dadd`, preserved unmodified; `7/7` synthetic unit fixtures passed)
- **Original-Run Interruption & Symbol-Only Fix:** Initial Stage-1 run (`run_stage1_dev_pilot.py` `5191a160...`) wrote all 30 forward per-image records cleanly and hit an aggregation-symbol typo (`ev.aggregate_sec43` -> `ev.summarize_sec43`). Fixed ONLY that symbol (`5191a160... -> dbb2c060...`; zero change to preregistered method, protocol, or scorer) and re-ran cleanly (`PID = 62340`, exit `0`, wall `82.35 s`).
- **Native Completed Receipt:** `PID = 62340` | Summary SHA-256: `d07078e39b5b99588aa525dda7a1b9c428d1a651c12f9281e42264ce8d003dbb` | Per-Image JSONL SHA-256: `527d1945e1a923f69eba6c4e3a5ef24e4029d9349ee07289740ce3b1ea9302a1`
- **Dev-Only Deployed Results (`N = 30`, exact `max_abs_px_diff = 0.0 px` on `4/4` A, `17/17` B, `19/19` C):**
  - **Arm A (Released Default, `2` calls/img):** `FPC = 0.937580`, `TU = 3/30`, mean wall `0.511 s/img`
  - **Arm B (Single-Res `1.0x` Control, `8` pre-fallback calls / `8.87` eff. w/ fallback):** `FPC = 0.590085925`, `TU = 16/30`, mean wall `0.982 s/img` (`+0.347494` FPC and `+13` TU over Arm A — captures `78.3%` of C's total gain)
  - **Arm C (Two-Res `1.0x + 2.0x` Candidate, `8` pre-fallback calls / `8.80` eff. w/ fallback, `4×` px in View 2):** `FPC = 0.493545253`, `TU = 18/30`, mean wall `1.112 s/img`
  - **Primary C vs. B:** paired gain `+0.096540672` (curve-span sensitivity `+0.096156`), **95% bootstrap CI `[-0.0006114, +0.2234884]`** (includes zero!), `+2` net TU (`16 -> 18`), `3` plots improve `> 0.01`, `1` worsens `> 0.01`.
  - **Conjunctive Gate Decision:** **`NO_MATERIAL_MULTISCALE_GAIN_OVER_CONTROL`** (CI includes zero -> **STOP RULE HONORED**).

## Guardrails Preserved
- **No official `DigitizerBench-Full` comparison** (single-slot `8fb89a62` single-line dev subset only; never equated with Paper Table 3 Full `0.672` / `38.2%` TU).
- **Zero held-out data accessed:** all `2,470` untouched Full `base_id`s (`2,950` images) remain un-downloaded.
- **Prior frozen archives untouched:** `main` and PRs `#13`, `#14`, `#15`, `#16` unchanged.
