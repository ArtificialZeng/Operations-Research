# Stage-1b Locked Multi-Seed Protocol: Validation-Pinned Audit on Reserved Seeds `13, 14, 15` (`dfl_constraints_dual_pinball_20261124`)

**Status:** LOCKED BEFORE EXECUTION (2026-11-24)  
**Pre-Launch Gates Verified:**
1. Stage-0 seed-`11` and Stage-1a seed-`12` files preserved byte-for-byte (SHA-256 receipts in [STAGE1A_SEED12_RESULT.md](STAGE1A_SEED12_RESULT.md)).
2. Cheap `MDKP-Capacity` source-pairing vs. clean target-signal receipt saved ([MDKP_CAPACITY_SIGNAL_RECEIPT.json](MDKP_CAPACITY_SIGNAL_RECEIPT.json)) as a separate defect receipt without claiming downstream published ranking impact.
3. Independent numerical loss, gradient, clipping, and Adam step parity verified directly against **ACTUAL unmodified pinned PyTorch `official_odece_repo/src/odece.py`** (commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`, [ODECE_PYTORCH_PARITY_RECEIPT.json](ODECE_PYTORCH_PARITY_RECEIPT.json)): `float64` loss abs err `1.96e-12` (`2.07e-13` rel), raw `d_w_hat`/`gW`/`gb` max abs err `<= 5.58e-12`, post-clip + 1 Adam step max abs err `<= 5.96e-11` across both branches (`0, 1, 2, 3` violations + masked instances).

---

## 1. Benchmark Scope & Reserved Held-Out Seeds
- **Benchmark:** **Aligned benchmark adaptation** of official Apache-2.0 NeurIPS 2025 `ODECE` `MDKP-Weights` (`genWeights`, `num_items=50`, `dim=3`, `num_feat=10`, `deg=6`, `noise_width=0.25`, `capacity_ratio=[0.18, 0.20, 0.22]`), jointly permuting and splitting all four arrays `(X, w, capacity, costs)` via `np.random.RandomState(seed).permutation(1500)` into strictly disjoint `900 train / 100 val / 500 held-out test`. Explicitly **not** a reproduction of published upstream unsplit scores.
- **Reserved Seeds Evaluated:** Official seeds **`13, 14, 15`** (completely untouched prior to this locked run; `3 x 500 = 1,500` held-out test instances total).

---

## 2. Fixed Methods, Hyperparameter Grids & Identical Budget (No Modifications from Stage-1a)
All models use the identical linear predictor (`10 -> 150`, Xavier uniform init, zero bias, Adam `lr=0.05`, `batch_size=32`, `max_epochs=20`, seeded per run with `seed`):
1. **`MSE + Val-Shift(gamma)` (`11` arms):** Single `MSE` linear model shifted by $+\gamma \hat{\sigma}_{\text{val}}$ (`sigma_val` computed strictly on the `100`-instance `val` split) over $\gamma \in \{0.00, 0.15, 0.30, 0.45, 0.60, 0.75, 0.90, 1.05, 1.25, 1.50, 2.00\}$.
2. **`Uniform-Pinball(tau)` (`10` arms):** Elementwise asymmetric pinball loss over $\tau \in \{0.50, 0.55, 0.60, 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95\}$.
3. **`ODECE(alpha)` (`7` official arms):** Exact `src/odece.py` loss (`Softplus(beta=5)`, `margin_threshold=2.0`, `clip_grad_norm_(0.5)`) across all seven official $\alpha \in \{0.8, 0.7, 0.6, 0.5, 0.4, 0.3, 0.2\}$. Also logs `n_zero_infeas_batches` per arm to audit the empty-`violation_pred_mask` edge case documented in `ODECE_PYTORCH_PARITY_RECEIPT.json`.
- **Excluded:** `SW-Pinball` is NOT run (did not beat plain `Uniform-Pinball` in Stage-0).

---

## 3. Pre-Registered Validation-Pinned Selection Policies (Zero Test-Based Choice)
For each seed `s in {13, 14, 15}`, each method family selects its single confirmatory arm strictly on the `100`-instance `val` split:
- **PRIMARY — `P_le10pct_frac_p1`:** Minimize val `official_frac_surrogate_posthoc_p1` subject to val `strict_01_infeasibility_rate <= 0.10` (fallback if none qualifies: lowest val infeasibility, tie-broken by lowest val `official_frac_surrogate_posthoc_p1`).
- **Secondary Policies (also cross-audited in HiGHS `float64`):**
  - `P_le10pct_int_p1`: Minimize val `strict_01_int_repair_posthoc_p1` subject to val `strict_01_infeasibility_rate <= 0.10`.
  - `P_le5pct_frac_p1`: Minimize val `official_frac_surrogate_posthoc_p1` subject to val `strict_01_infeasibility_rate <= 0.05`.
  - `P_unconstrained_frac_p1`: Minimize val `official_frac_surrogate_posthoc_p1` (unconstrained).

---

## 4. Exact Metrics, Unrounded `HiGHS 1.16.0` Audit & Paired Uncertainty
- **Primary Penalty:** Official `kpdataset.py:L26` **`penalty = 1.0`**; **Secondary Penalty:** **`0.21`** evaluated from the exact same binary decisions.
- **Unrounded `float64` Feasibility & Repair:**
  - `strict_01_infeasibility_rate`: Exact unrounded `(W_true @ x) <= cap_true` across all 3 dimensions, zero padding.
  - `official_frac_surrogate_posthoc`: Clearly labeled **surrogate** (`sol / max_tau`, upstream `kpsolver.py:L81-88`).
  - `strict_01_int_repair_posthoc`: True greedy 0–1 binary item removal (`assert` verified strictly 0–1 feasible on 100% of instances).
- **Unrounded `float64` `HiGHS 1.16.0` Cross-Audit (Every Seed):**
  - Re-solve `100%` of offline true test instances (`500 / seed`) AND `100%` of every unique validation-pinned selected test model across all 4 policies (`500 / model / seed`) in unrounded `float64` `HiGHS 1.16.0` (`mip_rel_gap=1e-4`, `time_limit=5.0`). Report exact `kOptimal` / `kTimeLimit` counts, max MIP gap, max integrality error, and CP-SAT vs. HiGHS metric deltas. Never label `FEASIBLE`/timeout solves as exact.
- **Paired Objective & Realized-Violation Uncertainty (Per-Seed `n=500` AND Pooled `n=1,500` + 3-Seed Mean $\pm$ SD):**
  - Computed directly from the HiGHS-verified per-instance test outcomes for `Uniform-Pinball - ODECE` and `Uniform-Pinball - MSE+ValShift`:
    - Mean paired difference + 95% paired bootstrap CI (`10,000` resamples) + Wilcoxon signed-rank $p$ for `official_frac_surrogate_p1`, `strict_01_int_repair_p1`, `official_frac_surrogate_p021`, `strict_01_int_repair_p021`.
    - Mean realized strict 0–1 infeasibility difference + 95% paired bootstrap CI + discordant counts + exact McNemar $p$. Realized risk differences are always reported side-by-side with regret differences.
- **Fair Complete-Hyperparameter-Sweep Training + Validation Cost Accounting:**
  - Report BOTH single-arm AND complete-family-sweep training + validation costs per seed and summed across 3 seeds: shared offline train oracle solves/time, total in-loop train solves/time, total val selection solves/time, total `complete_sweep_train_plus_val_solves` & wall-clock time, plus exact emitted-vs-actual solver-call parity.

---

## 5. Durability & Persistence
- Output directory: `./stage1b_multiseed_13_15\`
- Per-seed incremental persistence:
  - `seed_<S>\incremental.jsonl` (appended & flushed after every completed arm)
  - `seed_<S>\per_instance\<arm>.json` and `seed_<S>\per_instance\highs_<arm>.json`
  - `seed_<S>\summary.json` (written immediately upon completion of each seed `13`, `14`, `15`; resumable without redoing completed seeds)
- Aggregate output: `stage1b_aggregate_summary.json` (written upon completion of all 3 seeds).
