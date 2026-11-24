# Stage-2c Controlled Mechanism Confirmation: Actual Upstream `src/odece.py` (`alpha = 0.5`) on Fresh Seed `16` (`dfl_constraints_dual_pinball_20261124`)

**Date:** 2026-11-24  
**Real Process ID:** `PID = 33068` (`total_wall_time = 79.57 s`, `torch 2.15.0+cpu`, `torch.float64`)  
**Locked Protocol:** [STAGE2C_ODECE_CAPACITY_PROTOCOL.md](STAGE2C_ODECE_CAPACITY_PROTOCOL.md) (`sha256: d36e4d7117e3447c82a3ec7793faccc826d7e38618e7013beb81d9acb24247da`)  
**Pre-Launch Parity Receipt & Erratum:** [ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT.json](ODECE_CAPACITY_PYTORCH_PARITY_RECEIPT.json) (`sha256: 7207e16b...`) + full failure/pass history in [ODECE_CAPACITY_PARITY_AUDIT_LOG.json](ODECE_CAPACITY_PARITY_AUDIT_LOG.json) and [STAGE2C_PARITY_AND_TIMING_ERRATUM.md](STAGE2C_PARITY_AND_TIMING_ERRATUM.md). **Erratum:** Before the coordinator's `13:41:34` queued message was delivered, the auxiliary handwritten analytic check tolerance was relaxed from `1e-10` to `1e-9` (it had failed at `1.58e-10` due to PyTorch `nn.Softplus` `threshold=20`), and seed `16` was launched at `13:43:43`. Stage-2c itself executed **exclusively the authorized direct unmodified upstream PyTorch `src/odece.py` loss & autograd route** (never the handwritten analytic formula), whose 33-parameter FD parity passed without relaxation (`<= 2.14e-10`) across all 4 branch fixtures. Reserved seeds `17, 18` remain completely untouched.  
**Reserved Untouched Seeds:** Official-style seeds **`17, 18`** remain completely untouched.  
**Scope & Causal Label:** Strictly a single-seed (`seed = 16`) controlled mechanism confirmation testing the upstream training-label mispairing defect (`KnapsackCapaExp.py:L69-73`) inside **one upstream DFL loss recipe (`ODECE`, prespecified middle `alpha = 0.5`)** calling unmodified pinned `official_odece_repo/src/odece.py` directly in `torch.float64`. **Does NOT assert original published method rankings.** No all-alpha sweep; no PDF, publicity, or external correspondence.

---

## 1. Controlled Clean Held-Out Test Comparison (`n = 500`, `HiGHS 1.16.0` Unrounded `float64`)

Identical clean `(X_tr, w_tr, costs_tr)`, identical clean `val` (`100`) and clean `test` (`500`), paired identical initialization ([paired_init_weights.json](stage2c_odece_capacity_seed16/paired_init_weights.json), `sha256: d31f23cb...`), identical official `MDKP_CapaExp.sh` settings (`num_items=50, dim=3, deg=6, noise=0.25, lr=0.005, bs=32, max_epochs=20, margin=2.0, alpha=0.5`), and identical Stage-2b `ValPinned_le10pct` policy. *(Data sanity check on seed `16`: `900/900` train misaligned, `shared_mean MSE = 9.107`, `OLS-Clean OOS R^2 = +0.5589` vs `OLS-Mispaired = +0.0099`.)*

Because BOTH arms already achieved `val_infeas <= 10%` at `gamma = 0.00` (`5.0%` clean vs `2.0%` mispaired), the Stage-2b `ValPinned_le10pct` policy selected **`g* = 0.00` (zero fallback)** for both arms.

| Arm (`alpha = 0.5`) | Eval Mode | Val Infeas (`g*`) | Test Strict 0–1 Infeas | Test Unsolvable (`kInfeasible`) | Test Frac Surrogate `p=1.0` | Test Strict 0–1 Int-Repair `p=1.0` | Test Frac / Int `p=0.21` | Capacity Pearson $r$ (3 dims) | HiGHS Statuses |
|---|---|---:|---:|---:|---:|---:|---:|---|---|
| **`ODECE-Clean(a=0.5)`** | `ValPinned_le10pct` (`g*=0`) & `Raw` | 5.0% (`0.00`) | **3.20%** (`484/500` feas) | **0.0%** (`0` neg dims) | **27.8773%** | **28.0225%** | **27.7789% / 27.8668%** | `[0.539, 0.127, 0.800]` | `kOptimal: 500` |
| **`ODECE-Mispaired(a=0.5)`** | `ValPinned_le10pct` & `Raw` (Stage-2b clipped) | 2.0% (`0.00`) | 2.00% (`490/500` feas) | 0.0% (`3` neg dims clipped) | 42.5646% | 42.7295% | 42.4678% / 42.5675% | `[0.299, 0.040, 0.305]` | `kOptimal: 500` |
| **`ODECE-Mispaired(a=0.5)`** | `Raw` unclipped (exact upstream `kpsolver`) | — | 2.60% (`487/500` feas) | **0.6%** (`3` neg dims) | 42.5646% | 42.7295% | 42.4678% / 42.5675% | `[0.299, 0.040, 0.305]` | `kOptimal: 497, kInfeasible: 3` |

### Paired Clean Minus Mispaired Uncertainty (`n = 500`, Seed `16` HiGHS `float64`)
- **`ValPinned_le10pct` (and Stage-2b clipped `Raw_Plugin`):**
  - `official_frac_surrogate_p1`: **`-14.687 pp`** (`95% CI [-16.133, -13.264] pp`, Wilcoxon $p = 2.09 \times 10^{-53}$)
  - `strict_01_int_repair_p1`: **`-14.707 pp`** (`95% CI [-16.148, -13.305] pp`, Wilcoxon $p = 1.85 \times 10^{-54}$)
  - `p=0.21`: **`-14.689 pp`** frac / **`-14.701 pp`** int ($p < 10^{-51}$)
  - Realized strict 0–1 infeasibility: **`+1.20 pp`** (`3.20%` vs `2.00%`, `95% CI [-0.60, +3.20] pp`, discordant `15 vs 9`, exact McNemar $p = 0.307$).
- **Unclipped `Raw_Plugin`:** Identical regret difference **`-14.687 pp` frac / `-14.707 pp` int**; realized strict 0–1 infeasibility diff **`+0.60 pp`** (`3.20%` vs `2.60%`, `15 vs 12`, McNemar $p = 0.701$).

**Mechanism Conclusion:** Inside the actual pinned upstream `ODECE(alpha=0.5)` loss recipe (`float64`), changing **only** the training capacity targets to the upstream unsplit prefix (`capacity[:900]`) degrades held-out clean-test post-hoc regret by **`+14.69 pp` (`27.88%` -> `42.56%`)** at statistically indistinguishable strict 0–1 feasibility (`3.2%` vs `2.0–2.6%`), stalls epoch-20 training loss (`5.224` vs `3.748`), weakens capacity correlation across all 3 dimensions (`[0.539, 0.127, 0.800]` -> `[0.299, 0.040, 0.305]`), and leaves `3` unsolvable negative-capacity test instances.

---

## 2. Exact Solver Status Counts, Documented Guard Counts & Checkpoint SHA-256 Hashes

- **Offline true oracle:** `train_clean` `900/900 OPTIMAL`, `train_misp` `900/900 OPTIMAL`, `val_clean` `100/100 OPTIMAL` (CP-SAT); `test_clean` **`500/500 kOptimal`** (HiGHS `1.16.0`, `max_gap = 9.99e-5`, `int_err = 2.94e-12`).
- **In-loop training (`18,000` CP-SAT calls/arm; `0` timeouts / `FEASIBLE_NONOPTIMAL`):**
  - `ODECE-Clean(a=0.5)`: `OPTIMAL: 16,263`, `INFEASIBLE: 1,737` (early negative predicted capacities from Xavier init; `900/900` solvable at epochs 19–20); `n_zero_infeas_batches_guard1 = 156/580`, `n_mask_zero_batches_guard2 = 4/580` (all epoch 1), `n_true_sol_ulp_viols_observed = 260/54,000` (`0.48%`).
  - `ODECE-Mispaired(a=0.5)`: `OPTIMAL: 15,831`, `INFEASIBLE: 2,169` (`892/900` solvable at epoch 20); `n_zero_infeas_batches_guard1 = 174/580`, `n_mask_zero_batches_guard2 = 4/580` (all epoch 1), `n_true_sol_ulp_viols_observed = 160/54,000` (`0.30%`).
- **Clean validation sweep (`1,100` CP-SAT calls/arm):** `1,100/1,100 OPTIMAL` for both arms.
- **Total solver calls:** `40,100` CP-SAT + `2,500` unrounded `float64` `HiGHS 1.16.0` (`max_gap <= 9.99e-5`, `max_int_err <= 6.14e-12`).
- **Source & Output SHA-256 Receipts:**
  - Pinned upstream `src/odece.py`: `07c0161ba5bcbfae848ec68a90fa5d7d28567c42bec9161a089a81ff17bedf48`
  - Pinned upstream `OptProblems/knapsack/kpsolver.py`: `f1fc217c11daa5ab02e7de52c416428ce10016c1845b216e1faaea8c4beb63f5`
  - Pinned upstream `OptProblems/knapsack/kpdata.py`: `bd21081c6f1861c7c2d5421a29e1415832541ab08b0f528fdf6673c972a8ef30`
  - Pinned upstream `ML/TorchML.py`: `6cb64787154cde4a57bb35ddc3e4ae369901ed4ff394a40132ac7ec2d19f0775`
  - [stage2c_odece_capacity_seed16.py](stage2c_odece_capacity_seed16.py): `433d67566c8271e5c1259e4717c72b737bfc0f0f5ce7c4e3308e15a255f13f11`
  - [stage2c_seed16_summary.json](stage2c_odece_capacity_seed16/stage2c_seed16_summary.json) (`31,189 B`): `bf3baeb20567d811a7fe400586f3a1ff8df6986fe67f72f4a98cae8eb71b61c0`
  - [arm_output_ODECE-Clean_a0.5.json](stage2c_odece_capacity_seed16/arm_output_ODECE-Clean_a0.5.json) (`10,578 B`): `2996b5ad437613c4ac5735ef45a27b38fb53b69711f93c7236eb491c2cfe0624`
  - [arm_output_ODECE-Mispaired_a0.5.json](stage2c_odece_capacity_seed16/arm_output_ODECE-Mispaired_a0.5.json) (`10,616 B`): `e2fdca3b7717732dfec19bb797192a1f14100cec2639079e002a53a72081f43a`
  - Final weights checkpoints: Clean (`3f83de43...`), Mispaired (`2fb466e9...`); per-instance HiGHS JSONs persisted in `stage2c_odece_capacity_seed16/`.
