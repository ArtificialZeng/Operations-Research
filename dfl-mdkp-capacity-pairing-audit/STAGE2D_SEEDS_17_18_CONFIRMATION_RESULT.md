# Stage-2d Untouched Reserved-Seed Confirmation Report (`seeds = 17, 18`): Direct Upstream `ODECE(alpha=0.5)` on `MDKP-Capacity`

**Status:** COMPLETE & SEALED (`PID = 59256`, `torch 2.15.0+cpu`, `HiGHS 1.16.0`, `float64`, wall time `204.7 s`, `80,200` CP-SAT calls + `4,000` HiGHS calls).
**Locked Pre-Launch Protocol:** [`STAGE2D_SEEDS_17_18_CONFIRMATION_PROTOCOL.md`](STAGE2D_SEEDS_17_18_CONFIRMATION_PROTOCOL.md) (`SHA-256: 72d9d7ba...`).
**Pre-Launch Direct Gate:** [`ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json`](ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json) (`direct_pytorch_gate_pass_float64 = true`, `all_four_fixtures_exercised = true`; auxiliary non-gating handwritten analytic check retained unrelaxed at `1e-10` -> `false`, `max |dW| = 1.583e-10`).
**Prior Supporting Evidence Preserved Byte-Identical:** Stage-2c (`seed = 16`, `stage2c_odece_capacity_seed16/`) and all earlier Stage-0/1a/1b/2a/2b receipts verified byte-for-byte intact (`ALL_SEALED_PRIOR_INTACT=True`). Seed `16` is kept strictly separate as supporting prior evidence; no seeds will be added to this confirmation.

---

## 1. Headline Verdict on Untouched Reserved Seeds `17` and `18`

- **Repaired-loss direction holds on BOTH untouched seeds `17` and `18`:** Under the locked `ValPinned_le10pct` policy (as well as `Raw_Plugin` unclipped and clipped), `ODECE-Clean(a=0.5)` achieves lower post-hoc loss than `ODECE-Mispaired(a=0.5)` on **both** fractional-surrogate `p=1` (`-4.440 pp` on seed `17`; `-8.888 pp` on seed `18`) and strict 0–1 greedy integer-repair `p=1` (`-4.411 pp` on seed `17`; `-8.977 pp` on seed `18`).
- **Observed strict 0–1 test risk RISES on BOTH untouched seeds `17` and `18` (risk–loss tradeoff, NOT simultaneous dominance):** `ODECE-Clean` produces higher observed test infeasibility than `ODECE-Mispaired` on **both** seed `17` (`11.80%` vs `3.80%`, `+8.00 pp`, exact McNemar $p = 1.82 \times 10^{-12}$) and seed `18` (`5.20%` vs `1.60%` clipped / `1.80%` unclipped, `+3.60 pp`, McNemar $p = 9.12 \times 10^{-4}$).
- **Realized test risk vs. `10%` validation threshold:** On **seed `17`**, `ODECE-Clean` meets the `<= 10%` validation selection criterion (`val_infeas = 8.0%`, `g* = 0.00`, `used_fallback = False`) yet **realizes `11.80%` strict 0–1 infeasibility on clean test (> `10%`)**. Validation pinning at `n_val = 100` does not guarantee out-of-sample realization `<= 10%`. On seed `18`, both arms realize `< 10%` (`5.20%` clean vs `1.60%` mispaired).
- **Mechanism & seed-`17` generator diagnostic:** Mispaired training labels (`capacity[:900]`, misaligned on `899/900` rows in both seeds) leave `ODECE`'s infeasibility-aversion term without coherent context-to-capacity signal, pushing predicted capacities conservatively lower (higher feasible regret `29.29%` / `38.65%`, lower infeasibility `3.80%` / `1.60%`). Note that `genCapacity(seed=17)` produces unusually low target capacity variance (`shared_mean_mse_clean_test = 0.09896`, with `val` dim 2 constant so `pearson_r[2] = NaN`) compared with `seed=18` (`5.26003`); the clean-vs-mispaired loss reduction and risk increase still appear on both untouched seeds (consistent in direction with supporting prior seed `16`, which showed `-14.687 pp` frac / `-14.707 pp` int and `+1.20 pp` clipped risk, $p = 0.307$).

---

## 2. Per-Seed Results (`n = 500` Clean Test Instances per Seed, `HiGHS 1.16.0` `float64`)

> **Solver-tolerance note:** `kOptimal` denotes HiGHS optimality within its configured tolerance (`mip_rel_gap = 1e-4`; observed max gap `<= 1.00e-4`, max integrality error `<= 1.10e-10`). All 95% intervals are 10,000-resample paired bootstrap intervals **conditional on each fitted seed pair**.

### 2.1 Arm-Level Metrics (`ValPinned_le10pct` and `Raw_Plugin`)

| Seed | Arm | Policy | Selected `g*` (Fallback) | Val Infeas (`n=100`) | Observed Test Strict 0–1 Risk (`n=500`) | Unsolvable (`kInfeasible`) | Frac Surr `p=1` (%) | Strict 0–1 Int Repair `p=1` (%) | Frac `p=0.21` / Int `p=0.21` (%) | Feas-Only Regret (%) | HiGHS Status (`n=500`) |
|---:|---|---|---|---:|---:|---:|---:|---:|---|---:|---|
| **17** | `ODECE-Clean` | `ValPinned_le10pct` (= `Raw` unclip/clip, `neg=0`) | `0.00` (`False`) | `8.0%` | **`11.80%`** *(> 10% target)* | `0` (`0.0%`) | `24.1792` | `24.3126` | `23.5588` / `23.6395` | `25.5926` | `500 kOptimal` |
| **17** | `ODECE-Mispaired` | `ValPinned_le10pct` (= `Raw` unclip/clip, `neg=0`) | `0.00` (`False`) | `2.0%` | `3.80%` | `0` (`0.0%`) | `28.6190` | `28.7237` | `28.4844` / `28.5478` | `29.2877` | `500 kOptimal` |
| **18** | `ODECE-Clean` | `ValPinned_le10pct` (= `Raw` unclip/clip, `neg=0`) | `0.00` (`False`) | `1.0%` | `5.20%` | `0` (`0.0%`) | `29.4830` | `29.5178` | `29.1888` / `29.2099` | `30.2022` | `500 kOptimal` |
| **18** | `ODECE-Mispaired` | `ValPinned_le10pct` (= `Raw` clip, `neg=1` clipped) | `0.00` (`False`) | `2.0%` | `1.60%` | `0` (`0.0%`) | `38.3706` | `38.4947` | `38.2706` / `38.3457` | `38.6477` | `500 kOptimal` |
| **18** | `ODECE-Mispaired` | `Raw_Plugin_unclipped` (`neg=1` unclipped) | — | — | `1.80%` | `1` (`0.2%`) | `38.3706` | `38.4947` | `38.2706` / `38.3457` | `38.5227` | `499 kOptimal, 1 kInfeasible` |

### 2.2 Paired Clean − Mispaired Contrasts (`ValPinned_le10pct`, `n = 500` per Seed)

| Seed | `frac_p1` Diff (`pp`) [95% Cond. CI] | Wilcoxon $p$ | `int_p1` Diff (`pp`) [95% Cond. CI] | Wilcoxon $p$ | Observed Strict 0–1 Risk Diff (`pp`) [95% Cond. CI] | Discordant (`C-only / M-only`) | Exact McNemar $p$ |
|---:|---|---:|---|---:|---|---:|---:|
| **17** | **`-4.440`** `[-4.797, -4.056]` | `2.41e-59` | **`-4.411`** `[-4.754, -4.050]` | `6.68e-61` | **`+8.00`** `[+5.60, +10.40]` | `40 / 0` | `1.82e-12` |
| **18** | **`-8.888`** `[-10.065, -7.796]` | `2.20e-40` | **`-8.977`** `[-10.129, -7.901]` | `9.76e-42` | **`+3.60`** `[+1.60, +5.60]` | `23 / 5` | `9.12e-04` |
| *18 (raw unclip)* | *`-8.888` `[-10.031, -7.715]`* | *`2.20e-40`* | *`-8.977` `[-10.107, -7.816]`* | *`9.76e-42`* | *`+3.40` `[+1.40, +5.40]`* | *`23 / 6`* | *`2.32e-03`* |
| *Prior Support: 16 (sealed)* | *`-14.687` `[-16.133, -13.264]`* | *`2.09e-53`* | *`-14.707` `[-16.143, -13.293]`* | *`1.85e-54`* | *`+1.20` (clip) / `+0.60` (unclip)* | *`14 / 8` (clip)* | *`0.307` (clip)* |

---

## 3. Solver Audit & Numerical Guard Prevalence (`580` Train Batches per Arm)

| Seed | Arm | Offline Oracles (`CP-SAT` / `HiGHS`) | In-Loop CP-SAT (`18,000` calls) | Val Grid CP-SAT (`1,100` calls) | Guard 1 (`empty_ipl`) | Guard 2 (`mask==0`, ep 1) | True-Sol IEEE-754 ULP Viols | Test Neg-Cap Dims |
|---:|---|---|---|---:|---:|---:|---:|---:|
| **17** | `ODECE-Clean` | `900 OPT` / `100 OPT` / `500 kOpt` | `17,533 OPT, 467 INFEAS` | `1,100 OPT` | `168` | `0` | `240` | `0` |
| **17** | `ODECE-Mispaired` | `900 OPT` / `100 OPT` / `500 kOpt` | `17,526 OPT, 474 INFEAS` | `1,100 OPT` | `164` | `0` | `220` | `0` |
| **18** | `ODECE-Clean` | `900 OPT` / `100 OPT` / `500 kOpt` | `16,499 OPT, 1,501 INFEAS` | `1,100 OPT` | `168` | `10` (`49/900` ep1) | `300` | `0` |
| **18** | `ODECE-Mispaired` | `900 OPT` / `100 OPT` / `500 kOpt` | `16,428 OPT, 1,572 INFEAS` | `1,100 OPT` | `148` | `10` (`49/900` ep1) | `340` | `1` (`1 kInfeasible` unclip) |

---

## 4. Sealed SHA-256 Artifact Manifest (Seeds `17` & `18` Separate Run Directories)

| Artifact | Bytes | SHA-256 |
|---|---:|---|
| [`verify_odece_capacity_direct_pytorch_gate.py`](verify_odece_capacity_direct_pytorch_gate.py) | 14,874 | `ee93240b91bcf51ddfb323540a063967113e7477641b18f16b4abff05f5f7071` |
| [`ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json`](ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json) | 5,529 | `573671e4875f3027620cf2971756df0fcb418de48bc47ccad09f5aa82cefd43a` |
| [`STAGE2D_SEEDS_17_18_CONFIRMATION_PROTOCOL.md`](STAGE2D_SEEDS_17_18_CONFIRMATION_PROTOCOL.md) | 9,229 | `72d9d7bab332183f742b0831b84bb516df416af7379bcd7a37396bd68422b77c` |
| [`stage2d_odece_capacity_seeds_17_18.py`](stage2d_odece_capacity_seeds_17_18.py) | 33,628 | `091194240f9749be211ee34218e4bbe60fb2546b84fa063bd901b4bd1d58621e` |
| [`stage2d_seeds_17_18_summary.json`](stage2d_seeds_17_18_summary.json) | 70,431 | `cb2c7ba107b97eb3461b78ad5d67c7ebb012efb1a1cb94f1e38a1fc057401ca0` |
| [`stage2d_odece_capacity_seed17/stage2d_seed17_summary.json`](stage2d_odece_capacity_seed17/stage2d_seed17_summary.json) | 30,941 | `4575b933de4fd08e2f719a737dffa55b57db695f0592e7fe11bfe6de7a121b42` |
| [`stage2d_odece_capacity_seed17/paired_init_weights.json`](stage2d_odece_capacity_seed17/paired_init_weights.json) | 952 | `a2935fdd54a84d927844cef5c6b8676f83557f89f6591debdfd03c2c40f613de` |
| [`stage2d_odece_capacity_seed17/final_weights_ODECE-Clean_a0.5.json`](stage2d_odece_capacity_seed17/final_weights_ODECE-Clean_a0.5.json) | 993 | `b96ca33107ef8b74eb18119015018ca1a4132bbb68578f617939d82cf4ca1d04` |
| [`stage2d_odece_capacity_seed17/final_weights_ODECE-Mispaired_a0.5.json`](stage2d_odece_capacity_seed17/final_weights_ODECE-Mispaired_a0.5.json) | 995 | `57dae728057256f7cfa7fb171cc908e1a660df2f2bd10d9c033553f5df091c77` |
| [`stage2d_odece_capacity_seed17/per_instance_highs_valpin_ODECE-Clean_a0.5.json`](stage2d_odece_capacity_seed17/per_instance_highs_valpin_ODECE-Clean_a0.5.json) | 106,676 | `2688dd6840b0855dd92bf4f8535a47dd1292e4178f6258a98de07e4e2b18e2bb` |
| [`stage2d_odece_capacity_seed17/per_instance_highs_valpin_ODECE-Mispaired_a0.5.json`](stage2d_odece_capacity_seed17/per_instance_highs_valpin_ODECE-Mispaired_a0.5.json) | 106,437 | `59cb8a58601455af51feab6c01e820de0de3d69b4b467b5d83ad0bebcbf6cb6d` |
| [`stage2d_odece_capacity_seed18/stage2d_seed18_summary.json`](stage2d_odece_capacity_seed18/stage2d_seed18_summary.json) | 30,884 | `4d158ca96b8cdb932325671e418c51ea3a35115b7e25f366946c4c0d0943b4ae` |
| [`stage2d_odece_capacity_seed18/paired_init_weights.json`](stage2d_odece_capacity_seed18/paired_init_weights.json) | 951 | `a7e55c2c94e5837ea6ab9b38212c92a576228cc80c76daad888c423b53ab0cc9` |
| [`stage2d_odece_capacity_seed18/final_weights_ODECE-Clean_a0.5.json`](stage2d_odece_capacity_seed18/final_weights_ODECE-Clean_a0.5.json) | 994 | `a067cca8182de0d43a2b527852de1705fb0136b66d607ce2da81c68e117a033d` |
| [`stage2d_odece_capacity_seed18/final_weights_ODECE-Mispaired_a0.5.json`](stage2d_odece_capacity_seed18/final_weights_ODECE-Mispaired_a0.5.json) | 1,003 | `6eb7f0533fb7a741b9ea57163ff118dda55dd4f0c387d5993533ea65a8a3ea45` |
| [`stage2d_odece_capacity_seed18/per_instance_highs_valpin_ODECE-Clean_a0.5.json`](stage2d_odece_capacity_seed18/per_instance_highs_valpin_ODECE-Clean_a0.5.json) | 106,398 | `c25e87e30f0d25943aaccea6afb8eb33b742f7540fc0bb6b69b3117a99cd31d5` |
| [`stage2d_odece_capacity_seed18/per_instance_highs_valpin_ODECE-Mispaired_a0.5.json`](stage2d_odece_capacity_seed18/per_instance_highs_valpin_ODECE-Mispaired_a0.5.json) | 105,983 | `69a78a8f5a79223822c227a8788a77bad996c488be3bb0d1cee53dcfcb9bea5f` |
| [`stage2d_odece_capacity_seed18/per_instance_highs_raw_unclipped_ODECE-Mispaired_a0.5.json`](stage2d_odece_capacity_seed18/per_instance_highs_raw_unclipped_ODECE-Mispaired_a0.5.json) | 105,986 | `27e5d322268cdd1a36afcf7ef607112d8f8818e1701a4d844a284c0629c4266d` |
