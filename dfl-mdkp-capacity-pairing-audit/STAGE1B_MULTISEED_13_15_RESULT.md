# Stage-1b Multi-Seed Validation-Pinned Audit Result: Reserved Seeds `13, 14, 15` (`dfl_constraints_dual_pinball_20261124`)

**Date:** 2026-11-24  
**Locked Protocol:** [STAGE1B_PROTOCOL.md](STAGE1B_PROTOCOL.md) (`sha256: b32aa18cd76d396aa1a0e8f156ac09d83b5a23a22ecfb5610600344908a1c4e8`)  
**Runner:** [stage1b_multiseed_13_15.py](stage1b_multiseed_13_15.py) (`sha256: 8097ce79825eec64010900c0cbd886ac89103369ece8b8e29d762998a6d2a4b5`)  
**Benchmark Scope:** **Aligned benchmark adaptation** of official Apache-2.0 NeurIPS 2025 `ODECE` `MDKP-Weights` (`JayMan91/OdeceDFLforConstraintsNeurips25`, commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`; `num_items=50`, `dim=3`, `num_feat=10`, `deg=6`, `noise_width=0.25`, `capacity_ratio=[0.18, 0.20, 0.22]`), jointly permuting and splitting `(X, w, capacity, costs)` into `900 train / 100 val / 500 test` per seed (`1,500` pooled held-out test instances across reserved seeds `13, 14, 15`). **Not a reproduction of published upstream unsplit scores** (upstream indexing defect preserved separately in [SOURCE_INDEX_RECEIPT.json](SOURCE_INDEX_RECEIPT.json) and [MDKP_CAPACITY_SIGNAL_RECEIPT.json](MDKP_CAPACITY_SIGNAL_RECEIPT.json); zero claims about published rankings from aligned-only runs).  
**Pre-Launch Parity Gate:** Passed prior to touching seeds `13–15` against unmodified pinned PyTorch `official_odece_repo/src/odece.py` ([ODECE_PYTORCH_PARITY_RECEIPT.json](ODECE_PYTORCH_PARITY_RECEIPT.json): `float64` loss abs err `1.96e-12`, raw grads `<= 5.58e-12`, 1 Adam step `<= 5.96e-11`).

---

## 1. Executive Summary & Honest Interpretation (No Stable Dominance Claim)

Across all three previously untouched reserved seeds (`13, 14, 15`; `1,500` held-out test instances, `100%` cross-audited in unrounded `float64` `HiGHS 1.16.0` with **`14,000 / 14,000 kOptimal`** and **`432,900 / 432,900 OPTIMAL`** CP-SAT solves, exact call parity):

> **Scope & Uncertainty Discipline:** Do **NOT** claim stable per-seed dominance from Stage-1b. Realized loss-vs-risk trade-offs flip across individual seeds under `n_val = 100` validation gating, and **all pooled `n = 1,500` paired confidence intervals and Wilcoxon/McNemar p-values below are strictly conditional on the three fitted seed pairs (`13, 14, 15`)**, not unconditional across-seed inference. Stage-1b weight runs are sealed and will not be rerun or retuned.

1. **Primary `<= 10%` Validation-Pinned Policy (`P_le10pct_frac_p1`; `P_le10pct_int_p1` selected the identical arms on all 3 seeds):**
   - **Per-seed HiGHS `Uniform-Pinball` vs. `ODECE` loss & risk:**
     - Seed `13`: loss `13.1317%` vs `12.5522%`, strict 0–1 risk `3.4%` vs `5.0%`.
     - Seed `14`: loss `12.8609%` vs `14.1468%`, strict 0–1 risk `3.8%` vs `6.0%` (`ODECE` validation fallback at `11%`).
     - Seed `15`: loss `8.5501%` vs `10.8084%`, strict 0–1 risk `18.2%` vs `12.4%` (both miss realized `10%`).
   - **3-Seed Pooled (`n = 1,500`, conditional on the 3 fitted seed pairs; HiGHS `float64`, official `penalty = 1.0`):** `Uniform-Pinball` achieves **`11.514%` (`+/- 2.571%` across-seed SD)** fractional-surrogate post-hoc regret and **`11.549%` (`+/- 2.569%`)** true strict 0–1 integer-repair regret vs. `ODECE` at **`12.502%` (`+/- 1.670%`)** frac / **`12.637%` (`+/- 1.569%`)** int and `MSE+ValShift` at **`12.319%` (`+/- 1.462%`)** frac / **`12.441%` (`+/- 1.364%`)** int.
   - **Pooled Paired `Uniform-Pinball - ODECE` (`n = 1,500`, conditional on the 3 fitted seed pairs):** **`-0.988 pp`** frac (`95% CI [-1.180, -0.801] pp`, Wilcoxon $p = 1.51 \times 10^{-26}$), **`-1.088 pp`** strict 0–1 integer repair (`[-1.278, -0.898] pp`, $p = 1.34 \times 10^{-27}$), at realized strict 0–1 infeasibility **`8.47%` vs `7.80%`** (diff **`+0.67 pp`**, CI `[-0.60, +2.00] pp`, discordant `54 vs 44`, exact McNemar $p = 0.363$).
   - **Pooled Paired `Uniform-Pinball - MSE+ValShift` (`n = 1,500`, conditional on the 3 fitted seed pairs):** **`-0.805 pp`** frac (`[-0.928, -0.683] pp`, $p = 7.77 \times 10^{-41}$), **`-0.893 pp`** int (`[-1.017, -0.769] pp`, $p = 7.81 \times 10^{-44}$), at realized infeasibility `8.47%` vs `8.20%` (diff `+0.27 pp`, McNemar $p = 0.694$).
   - **CRITICAL Per-Seed Calibration Nuance (Do Not Overstate Uniform Per-Seed Dominance!):** Point-estimate validation gating (`val_infeas <= 10%` on `n_val = 100`) exhibits substantial per-seed realized-risk variance across all families:
     - **Seed `13`:** `Uniform-Pinball(t=0.80)` was more conservative (`3.40%` vs `ODECE(0.6)` `5.00%` infeas, `-1.60 pp`, McNemar $p = 0.0768$) with **`+0.579 pp` higher frac regret** (`13.132%` vs `12.552%`) and `+0.512 pp` higher int-repair regret (`13.218%` vs `12.706%`).
     - **Seed `14`:** `ODECE` had **0 of 7 official alphas** meeting `val_infeas <= 10%` (fallback selected `ODECE(0.8)` at `11.0%` val infeas). `Uniform-Pinball(t=0.80)` strictly beat `ODECE(0.8)` on every metric (`3.80%` vs `6.00%` infeas, McNemar $p = 0.0347$; `12.861%` vs `14.147%` frac, `-1.286 pp`, $p = 1.07 \times 10^{-18}$; `12.838%` vs `14.171%` int, `-1.333 pp`).
     - **Seed `15`:** **All 3 families overshot `10%` on held-out test**, and `Uniform-Pinball(t=0.65)` overshot most severely (**`18.20%`** vs `ODECE(0.6)` **`12.40%`**, **`+5.80 pp` higher violation rate**, McNemar $p = 2.04 \times 10^{-4}$, driving its `-2.258 pp` frac / `-2.444 pp` int lower regret on Seed `15`). Thus Seed `15`'s lower regret is confounded by higher realized risk under naive `n_val = 100` point-estimate thresholding. *(Descriptively at matched risk on Seed `15`, `Uniform-Pinball(t=0.70)` at `12.6%` infeas gets `9.692%` frac / `9.930%` int vs `ODECE(0.6)` at `12.4%` infeas with `10.808%` frac / `11.035%` int.)*
2. **Secondary `<= 5%` Validation-Pinned Policy (`P_le5pct_frac_p1`):**
   - `Uniform-Pinball` satisfied strict 0–1 test infeasibility `<= 5%` on **3/3 seeds** (`1.0%, 3.8%, 3.6%`, mean **`2.80%`**) vs `ODECE` (`5.0%, 6.0%, 4.2%`, mean **`5.07%`**; fallback triggered on Seeds `14` and `15`). Pooled (`n = 1,500`): `Uniform-Pinball` achieved **`-2.27 pp` lower infeas** (McNemar $p = 5.38 \times 10^{-6}$), **`-0.629 pp` lower frac_p1** ($p = 1.40 \times 10^{-8}$), and **`-0.704 pp` lower int_p1** ($p = 3.16 \times 10^{-9}$) than `ODECE`, and beat `MSE+ValShift` by `-0.87 pp` infeas ($p = 0.0241$) and `-2.004 pp` frac_p1 ($p = 1.67 \times 10^{-178}$).
3. **Secondary Unconstrained Policy (`P_unconstrained_frac_p1`):**
   - Pooled (`n = 1,500`): `Uniform-Pinball` (`t=0.50/0.55`) achieved **`-20.60 pp` lower strict 0–1 infeasibility** than `ODECE(alpha=0.4)` (`40.40%` vs `61.00%`, McNemar $p = 2.41 \times 10^{-55}$), **`-0.416 pp` lower true strict 0–1 int-repair regret** (`7.168%` vs `7.584%`, Wilcoxon $p = 0.00182$; lower on 3/3 seeds), and `-0.271 pp` lower mean frac_p1 (`7.247%` vs `7.519%`, Wilcoxon $p = 0.348$; ODECE was lower on frac_p1 on Seed `14` by `-0.453 pp`).
4. **Complete-Hyperparameter-Sweep Compute Gap (3 Seeds Combined):**
   - Complete train + val sweep cost across all 3 seeds: `Uniform-Pinball` **`3,000` ILPs (`10.35 s`)** and `MSE+ValShift` **`3,300` ILPs (`11.15 s`)** vs. `ODECE` **`382,800` ILPs (`1,969.69 s` = `32.8 min`)** — **`127.6x` fewer solver calls and `190.3x` faster wall-clock time** for `Uniform-Pinball`.

---

## 2. Primary Policy (`P_le10pct_frac_p1`): Per-Seed & 3-Seed Aggregate (HiGHS `1.16.0` Unrounded `float64`)

*(Note: `P_le10pct_int_p1` selected the exact same 9 models across Seeds `13, 14, 15`; all metrics below are `500/500 kOptimal` HiGHS `float64` verified.)*

### 2A. Per-Seed & 3-Seed Mean $\pm$ SD
| Seed | Family | Selected Arm | Val Infeas | Test Strict 0–1 Infeas | Test Frac Surrogate `p=1.0` | Test Strict 0–1 Int-Repair `p=1.0` | Test Frac / Int `p=0.21` |
|---|---|---|---:|---:|---:|---:|---:|
| 13 | `MSE+ValShift` | `MSE+ValShift(g=0.60)` | 10.0% | 6.80% | 12.507% | 12.709% | 12.280% / 12.403% |
| 13 | `Uniform-Pinball` | `Uniform-Pinball(t=0.80)` | 8.0% | **3.40%** | 13.132% | 13.218% | 13.046% / 13.099% |
| 13 | `ODECE` | `ODECE(alpha=0.6)` | 8.0% | 5.00% | **12.552%** | **12.706%** | **12.432% / 12.525%** |
| 14 | `MSE+ValShift` | `MSE+ValShift(g=0.75)` | 10.0% | 4.60% | 13.678% | 13.652% | 13.443% / 13.427% |
| 14 | `Uniform-Pinball` | `Uniform-Pinball(t=0.80)` | 5.0% | **3.80%** | **12.861%** | **12.838%** | **12.677% / 12.663%** |
| 14 | `ODECE` | `ODECE(alpha=0.8)` *(fallback)* | 11.0% | 6.00% | 14.147% | 14.171% | 13.918% / 13.932% |
| 15 | `MSE+ValShift` | `MSE+ValShift(g=0.45)` | 9.0% | 13.20% *(miss)* | 10.773% | 10.964% | 10.274% / 10.390% |
| 15 | `Uniform-Pinball` | `Uniform-Pinball(t=0.65)` | 9.0% | 18.20% *(miss)* | **8.550%** | **8.591%** | **7.829% / 7.853%** |
| 15 | `ODECE` | `ODECE(alpha=0.6)` | 7.0% | 12.40% *(miss)* | 10.808% | 11.035% | 10.406% / 10.543% |
| **3-Seed Mean $\pm$ SD** | `MSE+ValShift` | — | — | `8.20 ± 4.47%` | `12.319 ± 1.462%` | `12.441 ± 1.364%` | `11.999% / 12.073%` |
| **3-Seed Mean $\pm$ SD** | `Uniform-Pinball` | — | — | `8.47 ± 8.43%` | **`11.514 ± 2.571%`** | **`11.549 ± 2.569%`** | **`11.184% / 11.205%`** |
| **3-Seed Mean $\pm$ SD** | `ODECE` | — | — | `7.80 ± 4.01%` | `12.502 ± 1.670%` | `12.637 ± 1.569%` | `12.252% / 12.333%` |

### 2B. Paired Objective & Realized-Violation Uncertainty (`Uniform-Pinball - Comparator`, HiGHS `float64`)
| Scope | Comparison (`A - B`) | `frac_p1` Diff [95% CI] (Wilcoxon $p$) | `int_p1` Diff [95% CI] (Wilcoxon $p$) | Realized Strict 0–1 Infeas Diff [95% CI] (Discordant `A/B`, McNemar $p$) |
|---|---|---:|---:|---:|
| **Pooled (`n=1500`)** | `Uniform-Pinball - ODECE` | **`-0.988 pp`** `[-1.180, -0.801]` (`1.51e-26`) | **`-1.088 pp`** `[-1.278, -0.898]` (`1.34e-27`) | `+0.67 pp` `[-0.60, +2.00]` (`54 / 44`, `p=0.363`) |
| **Pooled (`n=1500`)** | `Uniform-Pinball - MSE+ValShift` | **`-0.805 pp`** `[-0.928, -0.683]` (`7.77e-41`) | **`-0.893 pp`** `[-1.017, -0.769]` (`7.81e-44`) | `+0.27 pp` `[-0.73, +1.27]` (`31 / 27`, `p=0.694`) |
| Seed `13` (`n=500`) | `Pinball(0.80) - ODECE(0.6)` | `+0.579 pp` `[+0.296, +0.865]` (`2.98e-05`) | `+0.512 pp` `[+0.216, +0.809]` (`1.06e-04`) | `-1.60 pp` `[-3.20, 0.00]` (`4 / 12`, `p=0.0768`) |
| Seed `14` (`n=500`) | `Pinball(0.80) - ODECE(0.8)` | **`-1.286 pp`** `[-1.579, -1.000]` (`1.07e-18`) | **`-1.333 pp`** `[-1.646, -1.029]` (`5.16e-18`) | **`-2.20 pp`** `[-4.20, -0.40]` (`6 / 17`, `p=0.0347`) |
| Seed `15` (`n=500`) | `Pinball(0.65) - ODECE(0.6)` | `-2.258 pp` `[-2.623, -1.893]` (`3.01e-35`) | `-2.444 pp` `[-2.769, -2.114]` (`3.19e-38`) | **`+5.80 pp`** `[+2.80, +8.80]` (`44 / 15`, `p=2.04e-04`) |

---

## 3. Secondary Policies Aggregate (`n = 1,500` Pooled, HiGHS `float64`)

| Policy | Family | 3-Seed Mean $\pm$ SD Infeas | 3-Seed Mean $\pm$ SD `frac_p1` | 3-Seed Mean $\pm$ SD `int_p1` | Pooled `Uniform-Pinball - ODECE` (`frac_p1` / `int_p1` / `infeas`) |
|---|---|---:|---:|---:|---|
| `P_le5pct_frac_p1` | `MSE+ValShift` | `3.67 ± 2.60%` | `15.905 ± 2.928%` | `15.981 ± 2.899%` | — |
| `P_le5pct_frac_p1` | `Uniform-Pinball` | **`2.80 ± 1.56%`** *(3/3 ≤5%)* | **`13.901 ± 1.676%`** | **`13.918 ± 1.711%`** | **`-0.629 pp`** (`1.40e-08`) / **`-0.704 pp`** (`3.16e-09`) / **`-2.27 pp`** (McNemar `5.38e-06`) |
| `P_le5pct_frac_p1` | `ODECE` | `5.07 ± 0.90%` *(2/3 fallback)* | `14.530 ± 1.302%` | `14.622 ± 1.285%` | *(Seed 13: Pinball `1.0%` vs `5.0%` inf at `+2.37 pp` frac; Seeds 14–15: Pinball lower on all metrics)* |
| `P_unconstrained_frac_p1` | `MSE+ValShift` | `30.27 ± 8.08%` | `8.415 ± 0.165%` | `8.241 ± 0.081%` | — |
| `P_unconstrained_frac_p1` | `Uniform-Pinball` | `40.40 ± 8.21%` | **`7.247 ± 0.293%`** | **`7.168 ± 0.319%`** | `-0.271 pp` (`p=0.348`) / **`-0.416 pp`** (`p=0.00182`) / **`-20.60 pp`** (McNemar `2.41e-55`) |
| `P_unconstrained_frac_p1` | `ODECE` | `61.00 ± 7.27%` | `7.519 ± 0.849%` | `7.584 ± 0.535%` | *(Seed 14: ODECE `-0.453 pp` lower on frac_p1 at `+21.4 pp` higher infeas)* |

---

## 4. Fair Complete-Hyperparameter-Sweep Training + Validation Cost Accounting (Seeds `13, 14, 15`)

| Family | Arms / Seed | 3-Seed Shared Offline Train Labels | 3-Seed Total In-Loop Train ILPs | 3-Seed Total Val Selection ILPs | **3-Seed Complete-Sweep Train+Val ILPs** | **3-Seed Complete-Sweep Wall Time (Per-Seed Mean)** | Relative Cost vs. `Uniform-Pinball` |
|---|---:|---:|---:|---:|---:|---:|---:|
| `MSE+ValShift` | 11 | `0` | `0` | `3,300` | **`3,300`** | **`11.15 s`** (`3.72 s/seed`) | `1.10x` ILPs / `1.08x` time |
| `Uniform-Pinball` | 10 | `0` | `0` | `3,000` | **`3,000`** | **`10.35 s`** (`3.45 s/seed`) | `1.00x` |
| `ODECE` (7-$\alpha$) | 7 | `2,700` | `378,000` | `2,100` | **`382,800`** | **`1,969.69 s`** (`656.56 s/seed`) | **`127.6x` ILPs / `190.3x` time** |

---

## 5. Exact Solver, Quantization & Edge-Case Audit + SHA-256 Receipts

- **CP-SAT (`OR-Tools 9.15.6755`, `_SCALE=10000`, `14` workers):** **`432,900 / 432,900 OPTIMAL`** across all 3 seeds (`144,300` per seed; `0` `FEASIBLE_NONOPTIMAL`, `0` `INFEASIBLE`, `0` `UNKNOWN`; `parity_exact = True` on all 3 seeds). Quantization violations (`W_hat @ x > cap`): `38 / 378,000` (`0.010%`) in ODECE train, `0 / 8,400` in val, `1 / 42,000` in test.
- **Unrounded `float64` `HiGHS 1.16.0`:** **`14,000 / 14,000 kOptimal`** (`5,000` seed 13 + `4,000` seed 14 + `5,000` seed 15; `0` `kTimeLimit`). Offline true OPT CP-SAT vs. HiGHS max rel diff: `2.09e-05` (seed 13), `0.00e+00` (seeds 14–15). Confirmatory val-pinned winner CP-SAT vs. HiGHS max metric abs delta: `<= 7.83e-05`.
- **Empty-`violation_pred_mask` (`z0`) batches in ODECE training (out of `580` batches per arm):** `alpha=0.8`: `138 / 137 / 136` (`23.6%`); `alpha=0.7`: `115 / 116 / 117` (`20.0%`); `alpha=0.6`: `66 / 68 / 76` (`12.1%`); `alpha=0.5`: `7 / 11 / 11` (`1.7%`); `alpha <= 0.4`: `0 / 0 / 0`. Guarded via `ial = 0` to prevent the unmodified `src/odece.py:L147+241` empty-tensor `.mean() -> NaN` edge case.
- **Stage-1b Output SHA-256 Receipts (`stage1b_multiseed_13_15/`):**
  - [stage1b_aggregate_summary.json](stage1b_multiseed_13_15/stage1b_aggregate_summary.json) (`96,349 B`): `60936fcd183d68944610a8b3acb87f4da9926765c59211b48c9630209a86c634`
  - [seed_13/summary.json](stage1b_multiseed_13_15/seed_13/summary.json) (`106,760 B`): `31f0c1cd7da72c46d625b0e521065df566bebbbb46538c8226f8556640a7170b`
  - [seed_13/incremental.jsonl](stage1b_multiseed_13_15/seed_13/incremental.jsonl) (`41,187 B`): `83d35680aca5fb2372cd970b220c56e294ee1a1b6dc89c332f3881b8c2c62b13`
  - [seed_14/summary.json](stage1b_multiseed_13_15/seed_14/summary.json) (`104,554 B`): `adf078f7343a9f47cea56fa56b4862b3cdc1bd49ed93c9c6527810b72ccaf022`
  - [seed_14/incremental.jsonl](stage1b_multiseed_13_15/seed_14/incremental.jsonl) (`41,173 B`): `db2385ddb0be257116f228aa7ed3b85c2eadb248766fd444399bdba973e42995`
  - [seed_15/summary.json](stage1b_multiseed_13_15/seed_15/summary.json) (`106,729 B`): `0dd0d88ef8d08e3c04da05b0ba404d41f253c2c1764a350813484d02796d2256`
  - [seed_15/incremental.jsonl](stage1b_multiseed_13_15/seed_15/incremental.jsonl) (`41,159 B`): `312dc6a86d016a3acb9e1ff245be76ee8d6b53efb0304e6f0c60967df01c1220`
