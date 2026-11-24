# Stage-2d Locked Confirmation Protocol: Direct Upstream `ODECE(alpha=0.5)` on Untouched Reserved Seeds `17` and `18` (`MDKP-Capacity`)

**Status:** LOCKED PRE-LAUNCH — written and hashed **before** generating any data or creating any run directory for reserved seeds `17` or `18` (`seed17_exists=False`, `seed18_exists=False` verified prior to lock).
**Prior Supporting Evidence Kept Byte-Identical:** Stage-2c (`seed=16`, `PID=33068`, `stage2c_odece_capacity_seed16/`), all Stage-2a/2b (`seeds 11–15`), Stage-1b (`seeds 13–15`), Stage-1a (`seed 12`), Stage-0 (`seed 11`), and prior parity receipts remain sealed byte-for-byte. Seed `16` is retained strictly as supporting prior evidence and is **not** pooled into the untouched Stage-2d direction check.

---

## 1. Pre-Launch Direct-Only PyTorch Parity Gate (Pinned `src/odece.py`, `float64`)

- **Gate script:** [`verify_odece_capacity_direct_pytorch_gate.py`](verify_odece_capacity_direct_pytorch_gate.py)
  - `SHA-256`: `ee93240b91bcf51ddfb323540a063967113e7477641b18f16b4abff05f5f7071` (`14,874 B`)
- **Gate receipt:** [`ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json`](ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json)
  - `SHA-256`: `573671e4875f3027620cf2971756df0fcb418de48bc47ccad09f5aa82cefd43a` (`5,529 B`)
- **Pinned upstream repo commit:** `1b432e03ce9ded1e504df60fd4c44cf936334d4f` (`torch 2.15.0+cpu`, `dtype=torch.float64`, `alpha=0.5`, fixture `seed=11`):
  - `direct_pytorch_gate_pass_float64`: **`true`**
  - `all_four_fixtures_exercised`: **`true`**
  - **Gating criterion (actual unmodified `ODECE.losses_computation` autograd vs. exhaustive 33-parameter central finite differences, original unrelaxed thresholds `W < 1e-7`, `b < 1e-8`):**
    1. `realistic_mixed_capacity_batch_float64` (`n_ok=32`, pred viols `0:16, 1:14, 2:2, 3:0`): `max |dW| = 2.138e-10`, `max |db| = 1.952e-10` — **PASS**
    2. `partial_masked_infeasible_batch_float64` (`n_ok=30`, pred viols `0:15, 1:13, 2:2, 3:0`): `max |dW| = 2.030e-10`, `max |db| = 1.864e-10` — **PASS**
    3. `all_masked_zero_branch_float64` (`n_ok=0`): `max |dW| = 8.930e-11`, `max |db| = 8.994e-11` — **PASS**
    4. `all_pred_feasible_empty_ipl_guard_float64` (`n_ok=32`, `0:32`, `unmodified_empty_ipl_is_nan=true`, Guard 1 triggered): `max |dW| = 8.930e-11`, `max |db| = 8.994e-11` — **PASS**
  - **Auxiliary non-gating handwritten analytic diagnostic (retained at original unrelaxed thresholds `W < 1e-10`, `b < 1e-11`, NOT used in Stage-2d training):**
    - `auxiliary_handwritten_original_1e_10_pass`: **`false`** (`max |dW| = 1.583e-10`, `max |db| = 7.301e-12` across all 4 fixtures due to PyTorch `nn.Softplus(beta=5)` default `threshold=20` linear switch vs. unclipped NumPy `sigmoid`; zero tolerance relaxation).

---

## 2. Locked Pre-Launch Runner & Pinned Upstream Source SHA-256 Manifest

| File | Bytes | SHA-256 |
|---|---:|---|
| `verify_odece_capacity_direct_pytorch_gate.py` | 14,874 | `ee93240b91bcf51ddfb323540a063967113e7477641b18f16b4abff05f5f7071` |
| `ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json` | 5,529 | `573671e4875f3027620cf2971756df0fcb418de48bc47ccad09f5aa82cefd43a` |
| `stage2d_odece_capacity_seeds_17_18.py` | 33,628 | `091194240f9749be211ee34218e4bbe60fb2546b84fa063bd901b4bd1d58621e` |
| `official_odece_repo/src/odece.py` | 12,415 | `07c0161ba5bcbfae848ec68a90fa5d7d28567c42bec9161a089a81ff17bedf48` |
| `official_odece_repo/OptProblems/knapsack/kpsolver.py` | 8,912 | `f1fc217c11daa5ab02e7de52c416428ce10016c1845b216e1faaea8c4beb63f5` |
| `official_odece_repo/OptProblems/knapsack/kpdata.py` | 5,708 | `bd21081c6f1861c7c2d5421a29e1415832541ab08b0f528fdf6673c972a8ef30` |
| `official_odece_repo/ML/TorchML.py` | 6,871 | `6cb64787154cde4a57bb35ddc3e4ae369901ed4ff394a40132ac7ec2d19f0775` |

---

## 3. Exact Prespecified Intervention & Pairing (Identical to Stage-2c; Only Seed & Output Path Change)

- **Untouched reserved seeds & separate output directories:**
  - `seed = 17` -> `./stage2d_odece_capacity_seed17\`
  - `seed = 18` -> `./stage2d_odece_capacity_seed18\`
- **Data generator & splits (exact published `MDKP_CapaExp.sh` flags):**
  - `genCapacity(num_data=1500, num_features=10, num_items=50, dim=3, deg=6, noise_width=0.25, fixed_cost=False, seed=seed)`
  - `train_test_split(np.arange(1500), test_size=500, random_state=seed)` -> `train_test_split(idx_tr_full, test_size=0.1, random_state=seed)` (`900` train / `100` clean validation / `500` clean test).
- **Controlled two-arm intervention (NO optional arms):**
  - `ODECE-Clean(a=0.5)`: training target `capacity[idx_tr]`.
  - `ODECE-Mispaired(a=0.5)`: training target `capacity[:900]` (exact upstream `KnapsackCapaExp.py:L73` unsplit prefix defect).
  - **Held 100% identical across both arms per seed:** clean `X_tr`, `W_tr`, `c_tr`; clean validation `(X_va, W_va, cap_va, c_va)`; clean test `(X_te, W_te, cap_te, c_te)`; paired identical `LinearRegressionforKP_PredCapacity(10, 50, 3).double()` initialization (`torch.manual_seed(seed)`, saved to `paired_init_weights.json`); identical minibatch permutation sequence (`np.random.default_rng(seed + 1000)`).
- **Loss, optimizer, budget, and documented numerical guards:**
  - Direct call to unmodified pinned `ODECE.losses_computation` (`torch.float64`, `infeasibility_aversion_coeff=0.5`, `margin_threshold=2.0`, `predict_cost=False`), `torch.optim.Adam(lr=0.005)`, `batch_size=32`, `max_epochs=20`, `clip_grad_norm_(0.5)`.
  - **Guard 1 (`empty_ipl`):** when `mask_t.sum() > 0` and `loss_ipl.numel() == 0`, set `prev_ipl = 0.0` (avoiding upstream empty-tensor `.mean() -> NaN`) and record `n_zero_infeas_batches_guard1`.
  - **Guard 2 (`mask == 0`):** when `mask_t.sum() == 0`, unmodified `src/odece.py:L103-106` returns `(loss_withtruesol, loss_ial)` in swapped order, which is algebraically symmetric at prespecified `alpha = 0.5`; record `n_mask_zero_batches_guard2`.
  - **Audit counter:** log `n_true_sol_ulp_viols_observed` (IEEE-754 float64 binding ULP excess on true optimal solutions).
- **Solvers & precision:**
  - Offline training/validation targets, in-loop training solves, and validation grid sweeps: OR-Tools `CP-SAT` (`_SCALE=10000`, single-threaded per solve, `time_limit=5.0s` offline / `2.0s` in-loop & val). Require `900/900 OPTIMAL` for `tr_clean`, `tr_misp`, and `100/100 OPTIMAL` for `val`.
  - Clean test oracle & all final test policy evaluations: unrounded `float64` `HiGHS 1.16.0` (`mip_rel_gap=1e-4`, `time_limit=5.0s`, single-threaded per solve). Require `500/500 kOptimal` on offline test oracle; record exact status counts, max MIP gap, max integrality error, and negative capacity counts for every arm and policy.
- **Validation-only calibration & evaluation policies:**
  - **Primary prespecified policy (`ValPinned_le10pct`):** 11-point safety-margin grid `gamma in [0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00]` evaluated on **clean validation only** using `clip(pred - gamma * sigma_va, 0, None)` (`sigma_va = std(cap_va - pred_va, ddof=1)`). Select minimum `official_frac_surrogate_posthoc_p1` among `val_infeas <= 0.10 + 1e-12` (tie-break: lower `val_infeas`); if none qualify, trigger fallback (`used_fallback=True`, minimum `val_infeas`, tie-break lower `val_frac_p1`).
  - **Secondary diagnostic policies:** `Raw_Plugin_unclipped` (exact upstream negative-capacity behavior) and `Raw_Plugin_stage2b_clipped` (`clip(pred, 0, None)`).
  - **Primary paired endpoints (per seed, `n=500` clean test instances, `ODECE-Clean - ODECE-Mispaired`):**
    1. Official fractional-surrogate post-hoc loss (`penalty=1.0`, plus `0.21` reported).
    2. Strict 0–1 greedy integer-repair post-hoc loss (`penalty=1.0`, plus `0.21` reported).
    3. Observed strict 0–1 test infeasibility rate (explicitly distinguished from the `10%` validation selection threshold).
    - Paired uncertainty: 10,000-resample paired bootstrap 95% intervals conditional on each fitted seed pair, two-sided Wilcoxon signed-rank $p$, and exact McNemar $p$.

---

## 4. Strict Non-Deviation Rules

1. **No optional arms** and **no tuning or reruns** after inspecting seed `17` or seed `18`.
2. **No filling in a failed dispatch** as an empirical result: if any step fails or errors, report the exact failure honestly and stop.
3. **Direction confirmation criterion:** report explicitly whether `ODECE-Clean` achieves lower `ValPinned_le10pct` test loss than `ODECE-Mispaired` (both fractional-surrogate `p=1` and strict 0–1 integer-repair `p=1`) on **both** untouched seeds `17` and `18`, while reporting observed strict 0–1 test risk alongside any risk-loss tradeoff and keeping seed `16` explicitly labeled as supporting prior evidence.
4. **Full sealing:** persist raw per-instance HiGHS JSONs (`raw_unclipped`, `raw_clipped`, `valpin`), checkpoints, arm outputs, and per-seed summaries for both seeds `17` and `18`, compute SHA-256 hashes for all new artifacts, and re-verify Stage-2c seed-`16` hashes remain byte-identical.
