# Stage-0 Exploratory Verdict, Source-Index Receipt & Solver-Swap Errata (`dfl_constraints_dual_pinball_20261124`)

**Date:** 2026-11-24  
**Status:** Stage-0 (official seed `11`) preserved **byte-for-byte** as a one-seed **exploratory** diagnostic (descriptive test-frontier sweep; NOT a validation-pinned confirmatory claim).

---

## 1. Preserved Sealed Stage-0 Artifacts (Byte-for-Byte Untouched)
- `STAGE0_PROTOCOL.md` sha256 `3ec85d5fe838ae002b8c5059a674478aaeffd778221ac537882a782921cf5dc1`
- `stage0_mdkp_falsifier.py` sha256 `11b9599c164052f3372934f71ac42ddfaf5c728f72c9545dfe37273d5521db74`
- `stage0_mdkp_results.json` sha256 `cbdd69a4625f312df8e4b74b47aeb3df1db03af5b66f50a503836f535f8557c4`

## 2. Earlier Canceled HiGHS Run & CP-SAT Solver-Swap Receipt
1. **Canceled HiGHS run (`task-284`):** The initial version of `stage0_mdkp_falsifier.py` used `HiGHS 1.16.0` (`highspy`) for all 0-1 MDKP solves (~`87–101 ms/solve` single-threaded) and triggered `RuntimeWarning: overflow/invalid value` in `sigmoid_stable`. After running past `300 s` during `ODECE` training, `task-284` was terminated cleanly without writing a results JSON.
2. **Swap to `OR-Tools CP-SAT` (`task-298`, completed):** `solve_single_mdkp` was switched to `OR-Tools CP-SAT` (`_SCALE = 10000`, `17 ms/solve`, `14` workers), cross-checked against `HiGHS 1.16.0` on 10 test instances (`max rel diff = 1.73e-15`), and `sigmoid_stable` was clipped cleanly.
3. **Emitted-log vs. actual-solver discrepancy in sealed `stage0_mdkp_falsifier.py`:** Line 385 and line 456 still printed `"Solving offline exact HiGHS MIPs..."` and `"20 epochs x 900 HiGHS ILPs"` even though `solve_single_mdkp` executed **`OR-Tools CP-SAT`** (with `HiGHS` used only in `verify_cpsat_vs_highs` for 10 instances). Additionally, `solve_single_mdkp` accepted `cp_model.FEASIBLE` alongside `cp_model.OPTIMAL` without logging separate timeout/non-optimal counts. Both defects are fixed in Stage-1a.

## 3. Upstream Source/Index Discrepancy Receipt (`SOURCE_INDEX_RECEIPT.json`)
Verified programmatically by `source_index_discrepancy_receipt.py` on pinned Apache-2.0 upstream commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`:
- Both `KnapsackWeightExp.py` (lines 71–83) and `KnapsackCapaExp.py` (lines 64–75) pass only `(X, w)` to `train_test_split`, while passing raw unsplit `(capacity, costs)` to `knapsack_dataset(...)` for `train`, `val`, and `test`.
- Under official defaults (`fixed_cost=False`, `noise_width=0.25`, `deg=6`, `N=1500`), **all four fields vary across instances**: `X` (`1500` unique rows), `w` (`1500`), `costs` (`1500`), and `capacity` (`1500` unique in `MDKP-Weights`, `483` unique in `MDKP-Capacity`).
- Consequently, upstream `val` reuses `capacity[0..99]` & `costs[0..99]` (`100%` overlap with `train[0..99]`), upstream `test` reuses `capacity[0..499]` & `costs[0..499]` (`100%` overlap with `train[0..499]`), and in `KnapsackCapaExp.py` the predicted target `capacity` is misaligned with shuffled features `X` (`899/900` train, `100/100` val, `500/500` test misaligned).
- **Benchmark labeling:** Because our harness jointly splits all four arrays `(X, w, capacity, costs)` with one index permutation, all our experiments are strictly an **aligned benchmark adaptation**, NOT a reproduction of published scores.

## 4. Honest One-Seed Exploratory Verdict (Seed `11`, `penalty = 0.21`)
- **Penalty correction:** Official `kpdataset.py` line 26 sets `penaltyVector = np.ones_like(costs)` (`penalty = 1.0`), whereas Stage 0 used `0.21` (the `TwoStagePtO` CLI parameter in `KnapsackWeightExp.py` line 41). Stage 1a uses **`penalty = 1.0`** as primary (and also reports `0.21` from identical decisions).
- **Crossing frontiers & no `SW-Pinball` method win:** On seed `11` (`penalty = 0.21`, descriptive test sweep), at `<= 10%` test infeasibility `Uniform-Pinball(0.75)` achieved `11.22%` post-hoc loss (`6.6%` infeas) vs `SW-Pinball(0.90)` `11.82%` (`9.0%`) and `ODECE(0.8)` `15.11%` (`3.8%`), whereas at `<= 5%` infeasibility `ODECE(0.8)` (`15.11%`, `3.8%`) beat `Uniform-Pinball(0.85)` (`16.05%`, `1.8%`) — **frontiers can cross**, and `SW-Pinball` did NOT beat plain `Uniform-Pinball`.
- **Decision:** Do NOT scale `SW-Pinball`. Advance **only** the ordinary `Uniform-Pinball` / `MSE+ValShift` vs. official `ODECE` baseline audit to a strict, validation-pinned, 7-$\alpha$ fresh-seed check (`seed = 12`, keeping seeds `13, 14, 15` untouched).
