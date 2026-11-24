# Stage-0c Canonical Replay Pilot Result — Native Receipt & Freeze Recommendation

**Status:** **COMPLETE & SEALED — RECOMMEND FREEZING** (Exploratory teacher-forced replay on `24` sealed Stage-0b `neutral_menu` pairs; **zero new decoding, zero new labels, zero second model**; sealed `N = 416` blind test `bfcl_future_blind_test_ids_sealed.json` *(omitted from public archive; SHA-256 `64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a`)* remains **100% untouched**).  
**Locked Protocol:** [`STAGE0C_CANONICAL_REPLAY_PROTOCOL.md`](../protocols/STAGE0C_CANONICAL_REPLAY_PROTOCOL.md) (`eafecf8ff023f800e78a10fa63dddc8bfc38cf941d8b31f2b525fad3c50f3efe`)  
**Fixture Receipt:** [`STAGE0C_CANONICAL_FIXTURE_RECEIPT.json`](../receipts/STAGE0C_CANONICAL_FIXTURE_RECEIPT.json) (`a24f4885af86a03fd2b9481e02e5872eae57a04be97b4d46d354eb843307c172`, `48/48` exact AST match)  
**Native Execution Receipt:** Real OS `PID = 11724`, total wall time `7.74 s` (`3.00 s` scoring `27` unique teacher-forced forward passes, `21` within-prompt deduplicated hits), verified local snapshot `Qwen/Qwen2.5-1.5B-Instruct` (`989aa7980e4cf806f80c7fef2b1adb7bc71aa306`, `bfloat16`, `RTX 5060 Laptop GPU`, `HF_HUB_OFFLINE=1`, `local_files_only=True`).  
**Integrity Gate:** All 11 sealed Stage-0, Stage-0b, and blind-test SHA-256 hashes verified **byte-identical before and after execution** ([`stage0c_summary.json`](../outputs/stage0c/stage0c_summary.json)).

---

## 1. Prespecified Decision Gate Verdict: **RECOMMEND FREEZING**

Against the locked prespecified gate (*canonical Ye26 SMT-mean beats strongest raw post-mask baseline `raw_post_gnll_smt_mean` on free-generation coverage transfer by `>= 8 pp` smaller worst-direction `|cov - 0.80|`, without worse mean `|cov - 0.80|` and without a new operational harm*):

- **PRIMARY (Leave-One-Tool-Family-Out [LOFO] across `18` tool-family clusters): FAILS (`-4.17 pp` worse worst-direction error, `-8.33 pp` worse mean error).**
  - `raw_post_gnll_smt_mean`: worst-dir `|cov - 0.80| = 9.17 pp`, mean `= 5.00 pp`.
  - `canon_gnll_smt_mean`: worst-dir `|cov - 0.80| = 13.33 pp`, mean `= 13.33 pp` (`95%` cluster-bootstrap CI on worst-dir reduction `[-14.55 pp, +25.00 pp]`; only `40.7%` of `2000` draws `>= 8 pp`).
- **COMPANION (Full-sample in-sample calibration): ALSO FAILS (`+4.17 pp < 8 pp` gate).**
  - `raw_post_gnll_smt_mean`: worst-dir `= 9.17 pp`, mean `= 5.00 pp`.
  - `canon_gnll_smt_mean`: worst-dir `= 5.00 pp`, mean `= 2.92 pp` (`+4.17 pp` reduction, below the `8 pp` gate even with `21/24` identical-pair self-calibration).
- **NEW OPERATIONAL HARMS IDENTIFIED:**
  1. **~100× synthetic NLL inflation from alphabetical argument-key sorting:** Re-serializing arguments in sorted key order contradicts schema parameter order on `12/24` items, inflating `canon_gnll_smt_mean` from `~0.00001–0.04` to `0.77–1.66` (`mean: 0.005 -> 0.556`). This degrades target in-grammar LOFO coverage (`16/24 = 66.7%` vs. `18/24 = 75.0%` for raw post-mask) and swamps genuine semantic uncertainty (on `simple_python_202`, the **correct** `W` call scores `1.030` vs. `1.015` for the **incorrect** `C` call).
  2. **Extra single-arm inference cost:** Requires `+1` extra unmasked teacher-forced forward pass per production call (`mean = 92.38 ms`, `median = 80.93 ms`, `max = 285.95 ms` on RTX 5060 for 1.5B, comparable to `77.79 ms` prefill). The `21/48 = 43.75%` pass savings from within-prompt deduplication apply only to paired offline evaluation, not single-call deployment.

**Recommendation:** Freeze this study line cleanly without opening the `416`-item blind test or launching a second model.

---

## 2. Primary Ye26 Semantic-Span Comparison (All 24 Sealed `neutral_menu` Free-Generated Pairs)

Frozen BFCL inert AST outcomes: `W = neutral_menu__G_optws_menu` (`23/24` correct, **`1` error**: `simple_python_334`), `C = neutral_menu__G_compact_menu` (`22/24` correct, **`2` errors**: `simple_python_334`, `simple_python_202`).  
*Epistemic note:* Identical-serialization score equality on the `21/24` equal-canonical pairs (`max |C - W| = 0.0` on those `21` pairs) is by construction and is NOT empirical novelty. Prior art: **Ye et al. (TMLR 2026, `arXiv:2604.22985v2`)** (`G-NLL_SMT` and AST structural clustering) and **Kim & Kang (`arXiv:2605.27752`)** (*"Same Answer, Different Confidence: Protocol Sensitivity in LLM Confidence Calibration"*).

> [!WARNING]
> **Selective-Risk & Bootstrap Caveat:** Target arms contain only **`1` error (`W`)** and **`2` errors (`C`)** across `24` items (`18` tool-family clusters, discrete `1/24 = 4.17 pp` granularity). **NO claims of improved selective risk are made.**

### A. PRIMARY: Leave-One-Tool-Family-Out (LOFO) Source Calibration (`18` clusters, target coverage `80%`)

| Scorer (Ye26 SMT-Mean) | `C -> W` Cov (`|err|`) | `W -> W` LOFO Ctrl (Shift) | `C -> W` Risk (Caveated) | `W -> C` Cov (`|err|`) | `C -> C` LOFO Ctrl (Shift) | `W -> C` Risk (Caveated) | Worst `|err|` | Mean `|err|` |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| **`raw_post_gnll_smt_mean`** (baseline) | **`19/24` (`79.2%`, `0.83 pp`)** | `18/24` (`75.0%`, `+4.17 pp`) | `0/19` (`0.0%`) | **`17/24` (`70.8%`, `9.17 pp`)** | `18/24` (`75.0%`, `-4.17 pp`) | `0/17` (`0.0%`) | **`9.17 pp`** | **`5.00 pp`** |
| `raw_pre_gnll_smt_mean` | `21/24` (`87.5%`, `7.50 pp`) | `18/24` (`75.0%`, `+12.50 pp`) | `1/21` (`4.8%`) | `15/24` (`62.5%`, `17.50 pp`) | `18/24` (`75.0%`, `-12.50 pp`) | `0/15` (`0.0%`) | `17.50 pp` | `12.50 pp` |
| **`canon_gnll_smt_mean`** (Stage-0c) | `16/24` (`66.7%`, `13.33 pp`) | `16/24` (`66.7%`, `0.00 pp`) | `0/16` (`0.0%`) | `16/24` (`66.7%`, `13.33 pp`) | `16/24` (`66.7%`, `0.00 pp`) | `0/16` (`0.0%`) | `13.33 pp` | `13.33 pp` |

*LOFO Cluster Bootstrap (`2000` draws, `18` clusters, `canon_gnll_smt_mean` vs. `raw_post_gnll_smt_mean`):*
- `canon` LOFO cov 95% CI: `C -> W [55.2%, 80.8%]`, `W -> C [55.2%, 80.0%]`, worst `|err| [0.83 pp, 24.83 pp]`.
- `raw_post` LOFO cov 95% CI: `C -> W [64.0%, 94.7%]`, `W -> C [47.6%, 81.8%]`, worst `|err| [2.73 pp, 32.38 pp]`.
- Reduction (`raw_post - canon`) 95% CI: worst-dir `[-14.55 pp, +25.00 pp]`, mean-dir `[-15.22 pp, +16.68 pp]`.

### B. COMPANION: Full-Sample In-Sample Source Calibration (Audit Match to Stage-0b)

| Scorer (Ye26 SMT-Mean) | `C -> W` Cov (`|err|`) | `W -> W` Ctrl | `W -> C` Cov (`|err|`) | `C -> C` Ctrl | Worst `|err|` | Mean `|err|` |
|---|---:|---:|---:|---:|---:|---:|
| `raw_post_gnll_smt_mean` | `19/24` (`79.2%`, `0.83 pp`) | `19/24` (`79.2%`) | `17/24` (`70.8%`, `9.17 pp`) | `19/24` (`79.2%`) | `9.17 pp` | `5.00 pp` |
| `raw_pre_gnll_smt_mean` | `24/24` (`100.0%`, `20.00 pp`) | `19/24` (`79.2%`) | `16/24` (`66.7%`, `13.33 pp`) | `19/24` (`79.2%`) | `20.00 pp` | `16.67 pp` |
| `canon_gnll_smt_mean` | `18/24` (`75.0%`, `5.00 pp`) | `19/24` (`79.2%`) | `19/24` (`79.2%`, `0.83 pp`) | `19/24` (`79.2%`) | `5.00 pp` | `2.92 pp` |

### C. Score Variation & the `3/24` Distinct-Canonical Pairs

| Scorer | Mean (`C` / `W`) | Median (`C` / `W`) | IQR (`C` / `W`) | Max `|C-W|` (`21` eq pairs) | Max `|C-W|` (`3` diff pairs) | Spearman $\rho$ |
|---|---:|---:|---:|---:|---:|---:|
| `raw_post_gnll_smt_mean` | `0.0072` / `0.0047` | `0.00028` / `0.00008` | `0.0026` / `0.0017` | `0.0413` | `0.0776` | `+0.874` |
| `raw_pre_gnll_smt_mean` | `0.4976` / `0.0050` | `0.00152` / `0.00022` | `0.0288` / `0.0029` | `4.0847` | `0.0777` | `+0.520` |
| `canon_gnll_smt_mean` | `0.5583` / `0.5563` | `0.4176` / `0.3911` | `0.9841` / `0.9880` | `0.0000` *(by construction)* | `0.0649` | `+0.997` |

*Exact scores on the `3` distinct-canonical pairs:*
- `multiple_25` (`C_ok=True`, `W_ok=True`, optional `region` omitted in `C`): `raw_post` (`0.00237` / `0.00160`), `canon` (`0.00208` / `0.00185`).
- `multiple_48` (`C_ok=True`, `W_ok=True`, `"New York City, NY"` vs `"New York City"`): `raw_post` (`0.00883` / `0.00037`), `canon` (`0.06538` / `0.00052`).
- `simple_python_202` (`C_ok=False`, `W_ok=True`, `"renewable energy sources"` vs `"renewable"`): `raw_post` (`0.08858` / `0.01097`), `canon` (`1.01451` / `1.03040` — key-sorting NLL dominates and flips `C < W`).

### D. Secondary Sensitivity (`*_gnll_smt_sum`, `*_nll_all_mean`, LOFO)
- `canon_gnll_smt_sum`: `17/24` (`70.8%`) both ways (`worst = 9.17 pp`, `mean = 9.17 pp`, ctrl `17/24`) vs. `raw_post_gnll_smt_sum` (`20/24` & `17/24`, `worst = 9.17 pp`, `mean = 6.25 pp`) — `0.00 pp` worst-dir gain, worse mean.
- `canon_nll_all_mean`: `16/24` (`66.7%`) both ways (`worst = 13.33 pp`) — beats unnormalized `raw_post_nll_all_mean` (`59.17 pp`), still loses to strongest raw post baseline `raw_post_gnll_smt_mean` (`9.17 pp`).

---

## 3. Sealed Stage-0c File Manifest

| File | SHA-256 |
|---|---|
| [`verify_stage0c_canonical_fixture.py`](../code/verify_stage0c_canonical_fixture.py) | `90bd257794ee9bbcd7d06e28223713bf019aa42781c989d699774f92df8320cc` |
| [`STAGE0C_CANONICAL_FIXTURE_RECEIPT.json`](../receipts/STAGE0C_CANONICAL_FIXTURE_RECEIPT.json) | `a24f4885af86a03fd2b9481e02e5872eae57a04be97b4d46d354eb843307c172` |
| [`STAGE0C_CANONICAL_REPLAY_PROTOCOL.md`](../protocols/STAGE0C_CANONICAL_REPLAY_PROTOCOL.md) | `eafecf8ff023f800e78a10fa63dddc8bfc38cf941d8b31f2b525fad3c50f3efe` |
| [`stage0c_canonical_replay_pilot.py`](../code/stage0c_canonical_replay_pilot.py) | `13d25dd12dbfb34b88a30b67f15a04cd36c8c9ac2eee9731a8c81d665aec24e0` |
| [`stage0c_outputs/stage0c_per_instance.jsonl`](../outputs/stage0c/stage0c_per_instance.jsonl) | `1f8528905f5e1c15a1e000299a36b0ef3f23f39ea8f726af2e4e06673d991fb5` |
| [`stage0c_outputs/stage0c_summary.json`](../outputs/stage0c/stage0c_summary.json) | `d47422dfdba372826c53097481032ba5b31a5c8df38e3a1038809649b8c4b797` |
