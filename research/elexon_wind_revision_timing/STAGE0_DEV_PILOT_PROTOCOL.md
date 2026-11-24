# Stage-0 Locked Bounded CPU Dev Pilot Protocol — GB Wind Forecast Signed Revision-Timing Signal

**Date Locked:** 2026-11-24 (BEFORE running ANY model training, validation scoring, or falsifier test)  
**Scope:** Bounded CPU Dev Pilot on `2024-10-15 .. 2026-05-31` (`594` days) across two strictly disjoint chronological validation blocks. **Held-out span `2026-06-04 .. 2026-11-23` (`173` days) is NOT downloaded and NOT touched in this Dev Pilot.** No large hyperparameter tuning, no simulated wins, no PDF/media/journal/priority/novelty claims.

---

## 1. Exact Target, Cutoff, Vintage Selection & Single Signed Timing Feature

- **Research Cutoff:** `T_cut(D) = D 11:00:00 UTC` (research cutoff, not an official market gate). **Hard causal rule:** Every predictor uses ONLY records with `publishTime <= D 11:00:00Z` (asserted in code on every day and every feature, including optional outturn lags).
- **Fixed Shared Hourly Delivery Grid (`G`):** `11` UTC hours `h ∈ {11, 12, ..., 21}` (`D 11:00:00Z .. D 21:00:00Z`).
- **Two Timed Complete Distinct Vintages:**
  - `v_new`: Latest complete `WINDFOR` vintage with `publishTime <= D 11:00:00Z` containing all `11` hourly points in `G`.
  - `v_old`: Latest complete `WINDFOR` vintage with `publishTime <= v_new.publishTime - 4h` (60s tolerance) whose forecast trajectory over `G` is strictly distinct (`v_old != v_new`). On `589/594` (`99.2%`) Dev days, `gap = 5.0 h` (`09:30Z` vs `04:30Z` GMT; `10:30Z` vs `05:30Z` BST).
- **Primary Target (`15:00–18:00 UTC` 3-Hour Wind Drop Warning):**
  - Hourly metered outturn: `Actual_hr(D, h) = 0.5 * (FUELHH(h:00Z) + FUELHH(h:30Z))` (MW).
  - Realized 3h change: `Δ_actual(D) = Actual_hr(D, 18) - Actual_hr(D, 15)` (MW; negative = wind drop).
  - Binary event: `Y(D) = 1[Δ_actual(D) <= τ_train]`, where `τ_train` is the **20th percentile (`q20`) of `Δ_actual` computed STRICTLY on that fold's training set** (`~ -755 MW` on Train-1 -> `~20%` prevalence -> `~30` independent event days per validation block).
- **Common Prespecified Adjacent Timing Search Window & Tie-Break:**
  - Search starts `s ∈ {11, 12, 13, 14, 15, 16, 17, 18}` UTC (`8` overlapping 3-hour windows `[s, s+3]` spanning `11:00–14:00` through `18:00–21:00 UTC`, centered on `15:00–18:00 UTC`).
  - Steepest 3h drop start hour: `t*(v) = argmin_{s ∈ {11..18}} [F_v(s+3) - F_v(s)]`, with **earliest-hour tie-break** (minimum `s`).
- **Single Pre-Locked Signed Timing Feature (`+1` feature only):**
  - `signed_timing_shift = t*(v_new) - t*(v_old)` (integer UTC hours; `> 0` = predicted steepest drop shifted later, `< 0` = shifted earlier).

---

## 2. Genuinely Strong Baseline (`X_base`) vs. Candidate (`X_cand = [X_base, signed_timing_shift]`)

Identical learner, identical hyperparameters, and identical `X_base` inputs are used for Baseline vs. Candidate. `X_base` (`49` features) includes:
1. **Latest level, ramp & timing (`6`):** `f_new(15)`, `f_new(18)`, `r_new_15_18 = f_new(18) - f_new(15)`, `min_drop_new`, `t*(v_new)`, `|t*(v_new) - 15|`.
2. **Both complete raw forecast trajectories (`22`) & pointwise updates (`11`):** `f_new(11..21)`, `f_old(11..21)`, `f_new(h) - f_old(h)` for `h = 11..21`, plus `r_old_15_18`, `r_new_15_18 - r_old_15_18`, `min_drop_old` (`+3`).
3. **Forecast spacing & seasonal UTC phase (`4`):** `lead_new_h` (`15:00Z - pub_new`), `gap_pub_h` (`pub_new - pub_old`), `sin(2π·doy/365.25)`, `cos(2π·doy/365.25)`.
4. **Two-version threshold agreement (NHESS 2025 persistence) & lagged ensemble (`6`):** `lag_ens_ramp = 0.5*(r_new_15_18 + r_old_15_18)`, `1[r_new_15_18 <= τ_train]`, `1[r_old_15_18 <= τ_train]`, `1[both <= τ_train]`, `1[min_drop_new <= τ_train]`, `1[min_drop_old <= τ_train]`.
5. **Strict causal pre-cutoff outturn lag (`4`, asserting `publishTime <= D 11:00:00Z`):** latest causally published `FUELHH` MW, age before `11:00Z` (hours), causal 3h outturn trend, and causal forecast error at nearest causal hour `<= 10:00Z`. *(Note: `f_new(15)` and `f_new(18)` are deduplicated with `f_new(11..21)` so `X_base` has `47` non-redundant features.)*

### Learners (Fixed, Zero Hyperparameter Search)
- **Reference Simple Lagged-Ensemble Benchmark (`Simple_LagEns`):** Standardized L2 `LogisticRegression(C=1.0)` on `[r_new_15_18, r_old_15_18, lag_ens_ramp]` only (shows how much stronger `X_base` already is).
- **Primary Learner (`L2_LogReg`):** Standardized `LogisticRegression(C=0.2, max_iter=1000)` on `X_base` vs. `[X_base, signed_timing_shift]`.
- **Strong Boosted Comparator (`HGB`):** `HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=100, min_samples_leaf=20, l2_regularization=2.0, random_state=42)` on `X_base` vs. `[X_base, signed_timing_shift]`.

---

## 3. Disjoint Chronological Dev Validation Blocks (3-Day Purge Gap)

| Block | Train Span (`N` days) | Purge Gap | Eval Span (`N` days) | Seasonality Covered |
|---|---:|---:|---:|---|
| **`Dev-Val 1`** | `2024-10-15 .. 2025-07-31` (`290`) | `2025-08-01 .. 2025-08-03` (`3`) | **`2025-08-04 .. 2025-12-31` (`150`)** | Late Summer / Autumn / Early Winter |
| **`Dev-Val 2`** | `2024-10-15 .. 2025-12-31` (`443`) | `2026-01-01 .. 2026-01-03` (`3`) | **`2026-01-04 .. 2026-05-31` (`148`)** | Winter / Spring |
| **`Held-Out` (UNTOUCHED)** | — | `2026-06-01 .. 2026-06-03` (`3`) | `2026-06-04 .. 2026-11-23` (`173`) | Summer / Autumn (Locked until Dev PASS) |

---

## 4. Two Pre-Locked Falsifiers & Conjunctive Advance Gate

1. **Falsifier 1 — Conditioned Shift Shuffle / Placebo (`N_perm = 200`, seed `20261124`):**
   - Permute `signed_timing_shift` **conditionally within strata of `t*(v_new)`** (`<=13`, `14..16`, `>=17`) independently on Train and Eval, preserving identical `X_base` and feasible shift support while breaking the real vintage shift.
   - Compute one-sided empirical `p_placebo = (1 + #{ΔBrier_placebo >= ΔBrier_real}) / 201` per block and pooled.
2. **Falsifier 2 — Planned Mechanism Test (Signed Direction vs. Actual Realized Relative Timing):**
   - Compute actual realized steepest 3h drop start hour `t*_actual = argmin_{s ∈ {11..18}} [Actual_hr(s+3) - Actual_hr(s)]` (earliest tie-break).
   - Measure Spearman & Pearson correlation between `signed_timing_shift = t*(v_new) - t*(v_old)` and actual relative timing offset `t*_actual - t*(v_new)` across all eval days AND on predicted-ramp days (`min_drop_new <= τ_train`) in `Dev-Val 1` and `Dev-Val 2`.

### Metrics & Pre-Locked Conjunctive Dev-Pilot Advance Gate (ALL 4 Required to Unlock Held-Out)
Reported per block and pooled (`298` days): Brier score, `ΔBrier = Brier(Base) - Brier(Cand)` (+5-day block-bootstrap 95% CI, `B = 2,000`), BSS, Log-Loss, ECE (5 bins), PR-AUC, ROC-AUC, and operational warning cost / false alarms at `p >= 0.30` and `p >= 0.50` (Hit Rate, FAR, Precision, Cost-Loss Value at `C/L = 0.25` and `0.50`).

1. **Sufficient Independent Events:** `>= 20` positive events in EACH of `Dev-Val 1` and `Dev-Val 2`.
2. **Repeatable Material Brier Benefit Across BOTH Chronological Blocks:** Primary `L2_LogReg` achieves `ΔBrier >= +0.0020` in **EACH** of `Dev-Val 1` AND `Dev-Val 2`, AND boosted comparator `HGB` is non-degrading (pooled `ΔBrier >= 0.0`).
3. **Placebo Falsifier Rejection:** Conditioned shift-shuffle placebo `p_placebo < 0.05` pooled (and `p_placebo < 0.15` in EACH block) on primary `L2_LogReg`.
4. **Consistent Mechanism Sign:** `corr(Δt*, t*_actual - t*_new)` has the same non-zero sign in both `Dev-Val 1` and `Dev-Val 2` (or if Brier passes without mechanism sign consistency, flag explicitly before unlocking held-out).

If ANY conjunctive gate fails -> **STOP cleanly after the Dev Pilot** (do NOT download/score Held-Out `2026-06-04 .. 2026-11-23` and do NOT retune).
