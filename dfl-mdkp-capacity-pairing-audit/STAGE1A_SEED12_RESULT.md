# Stage-1a Fresh Seed-12 Audited Result (`dfl_constraints_dual_pinball_20261124`)

**Date:** 2026-11-24  
**Protocol:** [STAGE1A_PROTOCOL.md](STAGE1A_PROTOCOL.md) (locked prior to execution; all Stage-0 seed-11 and Stage-1a seed-12 files preserved byte-for-byte)  
**Benchmark Scope:** **Aligned benchmark adaptation** of official Apache-2.0 NeurIPS 2025 `ODECE` `MDKP-Weights` (`JayMan91/OdeceDFLforConstraintsNeurips25`, commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`; `num_items=50`, `dim=3`, `num_feat=10`, `deg=6`, `noise_width=0.25`, `capacity_ratio=[0.18, 0.20, 0.22]`), jointly splitting all four arrays `(X, w, capacity, costs)` into `900 train / 100 val / 500 held-out test`. **Not a reproduction of published upstream unsplit scores** (see [SOURCE_INDEX_RECEIPT.json](SOURCE_INDEX_RECEIPT.json); upstream indexing defect is preserved strictly as a separate question and we make no claim about its impact on published rankings from aligned-only runs).  
**Reserved Sealed Seeds:** Official seeds **`13, 14, 15`** were **NOT** touched or inspected during Stage-1a.

---

## 1. Concise Verdict (No Broad Dominance Claim)

On fresh seed `12` (`penalty = 1.0` primary, `0.21` secondary; all validation-pinned confirmatory test selections verified in unrounded `float64` `HiGHS 1.16.0` with `500/500 kOptimal` each):

1. **Primary `<= 10%` Validation-Pinned Policy (`P_le10pct_frac_p1`):**
   - `Uniform-Pinball(t=0.70)` achieves **lower held-out test post-hoc regret** than `ODECE(alpha=0.6)`: **`9.4172%` vs `10.5186%`** (`-1.101 pp`, 95% paired bootstrap CI `[-1.387, -0.804] pp`, Wilcoxon $p = 1.02 \times 10^{-15}$) on the official fractional-scaling surrogate (`p=1.0`), and **`9.5291%` vs `10.7449%`** (`-1.216 pp`, CI `[-1.533, -0.903] pp`, $p = 3.41 \times 10^{-15}$) on true strict 0–1 integer repair (`p=1.0`).
   - **Important realized-risk caveat:** Both arms satisfy strict 0–1 test infeasibility $\le 10\%$, **but they do NOT realize the same test risk**: `Uniform-Pinball(t=0.70)` has **`9.40%`** strict 0–1 test infeasibility vs `ODECE(alpha=0.6)` at **`7.20%`** (`+2.20 pp`, 95% CI `[0.00, +4.40] pp`, exact McNemar $p = 0.0708$). Comparing closer-risk arms descriptively (`Uniform-Pinball(t=0.75)` at `5.80%` infeas vs `ODECE(alpha=0.6)` at `7.20%` infeas) yields `10.787%` vs `10.519%` frac (`+0.268 pp`, CI `[-0.024, +0.550]`) and `10.819%` vs `10.745%` int (`+0.074 pp`, CI `[-0.250, +0.385]`).
   - Against `MSE+ValShift(g=0.45)`, `Uniform-Pinball(t=0.70)` is lower on both regret (`9.4172%` vs `10.3104%` frac; `9.5291%` vs `10.5749%` int) and infeasibility (`9.40%` vs `12.80%`, McNemar $p = 7.63 \times 10^{-5}$).
2. **`<= 5%` Validation-Pinned Policy (`P_le5pct_frac_p1`):**
   - **Both methods miss the `5%` strict infeasibility target on held-out test** (`Uniform-Pinball(t=0.75)` `5.80%`, `ODECE(alpha=0.7)` `9.00%`, `MSE+ValShift(g=0.60)` `9.20%`), reflecting finite-sample `n_val = 100` selection variance. On test metrics for this policy, `Uniform-Pinball(t=0.75)` is lower than `ODECE(alpha=0.7)` on infeasibility (`-3.20 pp`, McNemar $p = 0.0113$), frac regret (`10.7869%` vs `11.8107%`), and int-repair regret (`10.8192%` vs `12.0309%`).
3. **Unconstrained Validation-Pinned Policy (`P_unconstrained_frac_p1` & `P_unconstrained_int_p1`):**
   - Both criteria select the same arms (`MSE`, `Uniform-Pinball(t=0.50)`, `ODECE(alpha=0.4)`).
   - `ODECE(alpha=0.4)` has **slightly lower fractional-surrogate post-hoc regret** (`6.4406%` HiGHS / `6.4399%` CP-SAT vs `Uniform-Pinball(t=0.50)` `6.6871%`, diff `+0.247 pp`, CI `[-0.091, +0.584] pp`, Wilcoxon $p = 0.0847$) at **`57.60%` vs `44.80%` strict 0–1 infeasibility** (`-12.80 pp` lower infeas for Pinball, McNemar $p = 4.75 \times 10^{-8}$).
   - Under **true strict 0–1 integer repair**, `Uniform-Pinball(t=0.50)` is slightly lower (`6.7801%` vs `7.0710%` HiGHS / `7.0723%` CP-SAT, diff `-0.292 pp`, CI `[-0.628, +0.045] pp`, $p = 0.168$).
4. **No Broad Dominance & Complete-Sweep Cost Gap:**
   - **There is no universal dominance across all operating points/metrics.** Across the full validation-pinned hyperparameter sweep (complete training + validation cost), `Uniform-Pinball` uses **`1,000` total CP-SAT ILPs (`2.60 s`)** and `MSE+ValShift` uses **`1,100` ILPs (`2.63 s`)**, vs **`127,600` ILPs (`535.34 s`)** for the 7-$\alpha$ `ODECE` sweep (`900` shared offline train labels + `126,000` in-loop train ILPs + `700` val ILPs — **`127.6x` more solver calls and `206x` higher wall-clock time**).

---

## 2. Confirmatory Validation-Pinned Held-Out Test Table (Verified in Unrounded `float64` `HiGHS 1.16.0`)

All metrics below are computed against **original unrounded `float64` true `(W, cap, costs)`** using `HiGHS 1.16.0` (`500/500 kOptimal` for every selected arm, `mip_rel_gap <= 1.00e-4`, max integrality error `<= 1.36e-7`). Fractional scaling (`sol / max_tau`, upstream `kpsolver.py:L81-88`) is explicitly labeled as a **surrogate** separate from **strict 0–1 feasibility** and **true strict 0–1 integer repair**.

| Policy (Val-Pinned) | Family | Selected Arm | Val Strict 0–1 Infeas | Test Strict 0–1 Infeas (HiGHS) | Test Official Frac Surrogate `p=1.0` | Test Strict 0–1 Int-Repair `p=1.0` | Test Frac / Int `p=0.21` | Test Feasible-Only Regret (`n/500`) | HiGHS Statuses |
|---|---|---|---:|---:|---:|---:|---:|---:|---|
| **`P_le10pct_frac_p1`** (Primary) | `MSE+ValShift` | `MSE+ValShift(g=0.45)` | 10.0% | 12.80% | 10.3104% | 10.5749% | 9.8242% / 9.9842% | 10.2833% (`436/500`) | `kOptimal: 500` |
| **`P_le10pct_frac_p1`** (Primary) | `Uniform-Pinball` | `Uniform-Pinball(t=0.70)` | 7.0% | **9.40%** | **9.4172%** | **9.5291%** | **9.0372% / 9.1049%** | **9.2229%** (`453/500`) | `kOptimal: 500` |
| **`P_le10pct_frac_p1`** (Primary) | `ODECE` | `ODECE(alpha=0.6)` | 6.0% | **7.20%** | 10.5186% | 10.7449% | 10.3071% / 10.4440% | 10.3242% (`464/500`) | `kOptimal: 500` |
| `P_le5pct_frac_p1` | `MSE+ValShift` | `MSE+ValShift(g=0.60)` | 5.0% | 9.20% (miss) | 11.5931% | 11.8748% | 11.2675% / 11.4380% | 11.7272% (`454/500`) | `kOptimal: 500` |
| `P_le5pct_frac_p1` | `Uniform-Pinball` | `Uniform-Pinball(t=0.75)` | 5.0% | 5.80% (miss) | 10.7869% | 10.8192% | 10.5638% / 10.5833% | 10.7373% (`471/500`) | `kOptimal: 500` |
| `P_le5pct_frac_p1` | `ODECE` | `ODECE(alpha=0.7)` | 4.0% | 9.00% (miss) | 11.8107% | 12.0309% | 11.5526% / 11.6858% | 11.5507% (`455/500`) | `kOptimal: 500` |
| `P_unconstrained` (`frac` & `int`) | `MSE+ValShift` | `MSE` (`g=0.00`) | 33.0% | 35.00% | 7.8410% | 7.7902% | 6.1388% / 6.1080% | 5.8711% (`325/500`) | `kOptimal: 500` |
| `P_unconstrained` (`frac` & `int`) | `Uniform-Pinball` | `Uniform-Pinball(t=0.50)` | 41.0% | 44.80% | 6.6871% | 6.7801% | 4.6925% / 4.7487% | 4.0079% (`276/500`) | `kOptimal: 500` |
| `P_unconstrained` (`frac` & `int`) | `ODECE` | `ODECE(alpha=0.4)` | 60.0% | 57.60% | 6.4406% | 7.0710% | 4.7247% / 5.1060% | 3.7531% (`212/500`) | `kOptimal: 500` |

*(CP-SAT vs. unrounded `float64` HiGHS `1.16.0` exact delta on all 9 selected models: `0.000000` on 6/9 models including both `P_le10pct` winners, and max `1.24e-05` on the remaining 3 with identical strict 0–1 feasibility counts.)*

---

## 3. Complete-Hyperparameter-Sweep & Per-Arm Solver Accounting

Exact CP-SAT call counter parity: **`144,332` actual == `144,332` accounted (`parity_exact = True`)**; **`100% OPTIMAL` across all `144,332` CP-SAT solves (`0` `FEASIBLE`/timeout, `0` `INFEASIBLE`, `0` `UNKNOWN`)**; plus **`5,000 / 5,000 kOptimal`** unrounded `float64` `HiGHS 1.16.0` cross-audit solves (`500` offline true oracle with `0.00e+00` max rel diff vs CP-SAT, plus `4,500` across the 9 unique selected test models). Quantization violations under CP-SAT `_SCALE=10000` against unrounded predicted `W_hat @ x <= cap`: `16 / 126,000` (`0.0127%`) in ODECE in-loop train, `0 / 2,800` in val, `1 / 14,000` in test (`MSE+ValShift(g=0.60)`, zero metric delta under HiGHS `float64`).

| Family | Arms in Sweep | Shared Offline Train Oracle Solves (Time) | Total In-Loop Train Solves (Train Wall Time) | Total Val Selection Solves (Val Wall Time) | **Full-Sweep Train+Val Solves (Wall Time)** | Single-Arm Train+Val Solves |
|---|---:|---:|---:|---:|---:|---:|
| `MSE+ValShift` | 11 | `0` (`0.00 s`) | `0` (`0.02 s` single train) | `1,100` (`2.61 s`) | **`1,100` (`2.63 s`)** | `100` |
| `Uniform-Pinball` | 10 | `0` (`0.00 s`) | `0` (`0.27 s` 10 trains) | `1,000` (`2.33 s`) | **`1,000` (`2.60 s`)** | `100` |
| `ODECE` (7-$\alpha$) | 7 | `900` (`4.18 s`) | `126,000` (`528.76 s`) | `700` (`2.40 s`) | **`127,600` (`535.34 s`)** | `19,000` |

*Note on Stage-1a self-check vs. independent PyTorch parity:* Stage-1a included a NumPy analytic-vs-central-finite-difference self-test (`max_abs_err = 2.82e-08`, `max_rel_err = 3.52e-07`), which does **not** independently verify parity against the pinned PyTorch `official_odece_repo/src/odece.py` module. Independent PyTorch parity verification is executed separately before touching reserved seeds `13–15` (see `ODECE_PYTORCH_PARITY_RECEIPT.json`).

---

## 4. Descriptive Full 28-Arm Held-Out Test Frontier (Seed `12`, CP-SAT `500/500 OPTIMAL` Each)

*Descriptive only — no model selection was performed on test.*

| Arm | Val Infeas | Test Strict 0–1 Infeas | Test Frac Surrogate `p=1.0` | Test Strict 0–1 Int-Repair `p=1.0` | Test Frac `p=0.21` | Test Weight MSE |
|---|---:|---:|---:|---:|---:|---:|
| `MSE` (`g=0.00`) | 33.0% | 35.0% | 7.841% | 7.790% | 6.139% | 19.98 |
| `MSE+ValShift(g=0.15)` | 22.0% | 25.6% | 8.401% | 8.566% | 7.240% | 20.68 |
| `MSE+ValShift(g=0.30)` | 15.0% | 18.0% | 9.312% | 9.411% | 8.518% | 22.12 |
| `MSE+ValShift(g=0.45)` | 10.0% | 12.8% | 10.310% | 10.575% | 9.824% | 24.31 |
| `MSE+ValShift(g=0.60)` | 5.0% | 9.2% | 11.593% | 11.875% | 11.267% | 27.23 |
| `MSE+ValShift(g=0.75)` | 4.0% | 6.0% | 13.019% | 13.087% | 12.779% | 30.89 |
| `MSE+ValShift(g=0.90)` | 2.0% | 4.0% | 14.379% | 14.482% | 14.220% | 35.29 |
| `MSE+ValShift(g=1.05)` | 2.0% | 2.4% | 15.775% | 15.807% | 15.661% | 40.42 |
| `MSE+ValShift(g=1.25)` | 1.0% | 1.8% | 17.566% | 17.659% | 17.503% | 48.42 |
| `MSE+ValShift(g=1.50)` | 0.0% | 1.2% | 19.767% | 19.828% | 19.730% | 60.27 |
| `MSE+ValShift(g=2.00)` | 0.0% | 0.4% | 23.896% | 23.880% | 23.874% | 90.12 |
| `Uniform-Pinball(t=0.50)` | 41.0% | 44.8% | 6.687% | 6.780% | 4.692% | 17.05 |
| `Uniform-Pinball(t=0.55)` | 24.0% | 31.4% | 6.922% | 6.980% | 5.530% | 16.89 |
| `Uniform-Pinball(t=0.60)` | 18.0% | 20.6% | 7.215% | 7.282% | 6.370% | 17.24 |
| `Uniform-Pinball(t=0.65)` | 11.0% | 15.6% | 8.218% | 8.511% | 7.664% | 18.26 |
| `Uniform-Pinball(t=0.70)` | 7.0% | 9.4% | 9.417% | 9.529% | 9.037% | 20.11 |
| `Uniform-Pinball(t=0.75)` | 5.0% | 5.8% | 10.787% | 10.819% | 10.564% | 23.24 |
| `Uniform-Pinball(t=0.80)` | 2.0% | 3.2% | 12.537% | 12.630% | 12.421% | 28.53 |
| `Uniform-Pinball(t=0.85)` | 0.0% | 1.8% | 15.102% | 15.169% | 15.047% | 37.78 |
| `Uniform-Pinball(t=0.90)` | 0.0% | 0.4% | 19.023% | 19.049% | 19.022% | 55.73 |
| `Uniform-Pinball(t=0.95)` | 0.0% | 0.0% | 25.504% | 25.504% | 25.504% | 95.33 |
| `ODECE(alpha=0.8)` | 10.0% | 9.6% | 11.403% | 11.554% | 11.072% | 40.15 |
| `ODECE(alpha=0.7)` | 4.0% | 9.0% | 11.811% | 12.031% | 11.553% | 39.53 |
| `ODECE(alpha=0.6)` | 6.0% | 7.2% | 10.519% | 10.745% | 10.307% | 35.09 |
| `ODECE(alpha=0.5)` | 22.0% | 21.6% | 7.646% | 7.974% | 7.038% | 31.79 |
| `ODECE(alpha=0.4)` | 60.0% | 57.6% | 6.440% | 7.072% | 4.724% | 27.27 |
| `ODECE(alpha=0.3)` | 84.0% | 83.6% | 8.538% | 8.159% | 4.934% | 28.04 |
| `ODECE(alpha=0.2)` | 95.0% | 95.8% | 11.660% | 9.700% | 6.066% | 30.56 |

---

## 5. Preserved Sealed File SHA-256 Receipts (Byte-for-Byte Verified)

- Stage-0 sealed files (unchanged):
  - `STAGE0_PROTOCOL.md` (`4,864 B`): `3ec85d5fe838ae002b8c5059a674478aaeffd778221ac537882a782921cf5dc1`
  - `stage0_mdkp_falsifier.py` (`23,298 B`): `11b9599c164052f3372934f71ac42ddfaf5c728f72c9545dfe37273d5521db74`
  - `stage0_mdkp_results.json` (`12,780 B`): `cbdd69a4625f312df8e4b74b47aeb3df1db03af5b66f50a503836f535f8557c4`
- Stage-1a sealed files (preserved byte-for-byte):
  - `SOURCE_INDEX_RECEIPT.json` (`5,463 B`): `9b181f19ab9af5747ad6755427ab52c0f9d3dbc942210737a96f94f5b9af54b9`
  - `STAGE0_EXPLORATORY_ERRATA.md` (`4,425 B`): `1c7aaf19a771d9a2f198927930a3340075c2b50abb7baba5867cc0c60b3e3483`
  - `STAGE1A_PROTOCOL.md` (`6,525 B`): `00298b70f21d2797f7059c5ab3bfefce3dc3a0aed3072d877ec3449706b98993`
  - `stage1a_fresh_seed12_audit.py` (`44,345 B`): `9f7d618136944ce47e40b7eafcb906379ec068604a9f854ae4ebbc31db79496d`
  - `stage1a_seed12_summary.json` (`89,026 B`): `48eb3a20b48cd7a8d50fa9e2950143cb6f0823d6ff1dd0c555604e76e5386c54`
  - `stage1a_seed12_incremental.jsonl` (`40,831 B`, 28 lines): `5ebd08636c4094bdd339a9994599f230a280ee597ef6e4a2b324a0d0161a7f0f`
  - `stage1a_seed12_per_instance/`: 28 JSON files (500 test instances each).
