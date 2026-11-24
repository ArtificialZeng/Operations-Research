# Stage 1 Locked Held-Out Synthetic Protocol (Pre-Registered — NOT YET EXECUTED)

**Directory:** `d:\AI_Science\antigravity\dcnp_polyhedral_cuts_20261124\`  
**Benchmark Script (Locked Source):** [stage1_heldout_synthetic_benchmark.py](file:///d:/AI_Science/antigravity/dcnp_polyhedral_cuts_20261124/stage1_heldout_synthetic_benchmark.py)  
**Date Locked:** 2026-11-24  
**Execution Status:** **LOCKED & UNEXECUTED** — awaiting explicit coordinator approval before running any held-out solver trials.  
**Scope:** Simple, undirected, unweighted, fixed-budget `2-DCNP` on **independently generated synthetic graphs ONLY** (zero real infrastructure/telecom/power/transport/biological graphs; zero third-party code or datasets from `halisalemi/DCNP`).

---

## 1. Exact Two-Arm Matched Design (`BASE_FULL` vs. `AUG_HUB`)

Both arms execute the **exact same** graph representation, **exact same** deterministic independent-set simplicial vertex fixing ($x_v = 0$ for $v \in F$, exhaustively verified with `0` discrepancies across `132` `(graph, b)` pairs in [stage0b_exact_rational_certificate.json](file:///d:/AI_Science/antigravity/dcnp_polyhedral_cuts_20261124/stage0b_exact_rational_certificate.json)), **exact same** single-threaded `HiGHS 1.15.1` engine (`threads = 1`, `random_seed = 20261124`, `presolve = "on"`, `mip_rel_gap = 1e-6`, `mip_abs_gap = 1e-6`), **exact same** bounded root separation loop for Clique-Chord and Alozie $C_5$ inequalities, and **exact same** monotone wall-clock deadline (`WALL_LIMIT_S = 60.0s` per arm per instance):

| Component | Arm 1: `BASE_FULL` (Full Credible Baseline) | Arm 2: `AUG_HUB` (Baseline + Hub Cuts ONLY) |
| :--- | :---: | :---: |
| Salemi–Buchanan Thin `d = 2` formulation | Identical | Identical |
| Independent-set simplicial vertex fixing (`x_v = 0`) | Identical | Identical |
| Chen et al. (2025) analogously adapted Clique-Chord separator (exact all triangles `|K| = 3` incl. Alozie Prop. 3.4.1 `t = 1` + bounded maximal-clique subsets `|K| >= 4`, `<= 20` cuts/round, `viol >= 0.05`, `viol/RHS >= 0.01`) | Identical | Identical |
| Alozie (2021/2024) Prop. 3.4.2 5-cycle (`C_5`) separator (branch-and-bound pruned deterministic search capped at `250,000` visits/round, `<= 20` cuts/round, `viol >= 0.05`, `viol/4 >= 0.01`) | Identical | Identical |
| **Theorem 1 Hub-Lifted Closed-Neighborhood (`N[w]`) separator** (pre-registered density/sparsity cap: `2 <= |Q| <= 8`, `viol >= 0.05`, `viol/RHS >= 0.01`, `<= 15` cuts/round, `<= 30` hub cuts total) | **Disabled (`0` hub cuts)** | **Enabled** |
| Root separation loop limits (`max_rounds = 6`, tailing-off stop `lp_gain < 1e-3` after round 1, reserve `>= 5.0s` for MIP) | Identical | Identical |
| Common actual monotone wall deadline (`deadline = perf_counter() + 60.0s` covering build + simplicial fixing + LP/cut cycles + MIP search) | Identical (`60.0s`) | Identical (`60.0s`) |

**Why this single-intervention control is sharp:** Any difference between `AUG_HUB` and `BASE_FULL` is attributable **solely** to adding Theorem 1 Hub-Lifted Closed-Neighborhood valid inequalities on top of a complete modern `2-DCNP` baseline (Thin + simplicial fixing + Clique-Chord + Alozie $C_5$). The initial Thin LP value (`lp_thin_init`, before any cuts) is also recorded inside `BASE_FULL` for transparent reference without adding a separate arm.

---

## 2. Predetermined Small Held-Out Synthetic Matrix (`16` Instances, Fresh Unseen Seeds)

Zero overlap with any Stage 0 or Stage 0B graph, size, or random seed (`seeds 501–534` reserved exclusively for this sealed suite):

| Family (4 instances each) | Instance ID | Generator & Fixed Parameters | `n` | Fixed Budget `b` | Active Baseline Cuts in `BASE_FULL` |
| :--- | :--- | :--- | :---: | :---: | :--- |
| **1. Bipartite (Triangle-Free)** | `bip_36x36_p012_s501` | `bipartite.random_graph(36, 36, 0.12, seed=501)` | `72` | `12` | Clique = `0`, $C_5$ = `0` (pure star regime) |
| | `bip_36x36_p012_s502` | `bipartite.random_graph(36, 36, 0.12, seed=502)` | `72` | `12` | Clique = `0`, $C_5$ = `0` |
| | `bip_44x44_p010_s503` | `bipartite.random_graph(44, 44, 0.10, seed=503)` | `88` | `15` | Clique = `0`, $C_5$ = `0` |
| | `bip_44x44_p010_s504` | `bipartite.random_graph(44, 44, 0.10, seed=504)` | `88` | `15` | Clique = `0`, $C_5$ = `0` |
| **2. Sparse Random Regular (`d = 4`)** | `reg_n64_d4_s511` | `random_regular_graph(4, 64, seed=511)` | `64` | `11` | Rare cliques, **many Alozie $C_5$** |
| | `reg_n64_d4_s512` | `random_regular_graph(4, 64, seed=512)` | `64` | `11` | Rare cliques, **many Alozie $C_5$** |
| | `reg_n80_d4_s513` | `random_regular_graph(4, 80, seed=513)` | `80` | `14` | Rare cliques, **many Alozie $C_5$** |
| | `reg_n80_d4_s514` | `random_regular_graph(4, 80, seed=514)` | `80` | `14` | Rare cliques, **many Alozie $C_5$** |
| **3. Watts–Strogatz (`k = 6, p = 0.20`)** | `ws_n64_k6_p020_s521` | `watts_strogatz_graph(64, 6, 0.20, seed=521)` | `64` | `11` | **Rich Clique-Chord + Alozie $C_5$** |
| | `ws_n64_k6_p020_s522` | `watts_strogatz_graph(64, 6, 0.20, seed=522)` | `64` | `11` | **Rich Clique-Chord + Alozie $C_5$** |
| | `ws_n80_k6_p020_s523` | `watts_strogatz_graph(80, 6, 0.20, seed=523)` | `80` | `14` | **Rich Clique-Chord + Alozie $C_5$** |
| | `ws_n80_k6_p020_s524` | `watts_strogatz_graph(80, 6, 0.20, seed=524)` | `80` | `14` | **Rich Clique-Chord + Alozie $C_5$** |
| **4. Stochastic Block Model (`4` blocks)** | `sbm_4x16_s531` | `stochastic_block_model([16]*4, p_in=0.35, p_out=0.04, seed=531)` | `64` | `11` | **Dense cliques + $C_5$** (density stress test) |
| | `sbm_4x16_s532` | `stochastic_block_model([16]*4, p_in=0.35, p_out=0.04, seed=532)` | `64` | `11` | **Dense cliques + $C_5$** |
| | `sbm_4x20_s533` | `stochastic_block_model([20]*4, p_in=0.35, p_out=0.04, seed=533)` | `80` | `14` | **Dense cliques + $C_5$** |
| | `sbm_4x20_s534` | `stochastic_block_model([20]*4, p_in=0.35, p_out=0.04, seed=534)` | `80` | `14` | **Dense cliques + $C_5$** |

**Maximum total runtime bound:** `16` instances $\times$ `2` arms $\times$ `60.0s` $\le$ `32 minutes` hard cap.

---

## 3. Per-Instance Reporting & Neutral Post-Run Aggregates

For **every** instance and arm, the script logs and preserves separately:
- **Timings (all inside the common monotone wall clock):** `t_build_and_simp_s`, `t_lp_and_sep_s`, `t_mip_s`, `t_total_s`, `hit_wall_deadline`;
- **Bounds & Verification:** `lp_thin_init`, `lp_root_after_cuts`, `cuts_clique`, `cuts_c5`, `cuts_hub`, `sep_rounds`, `mip_dual_bound`, `mip_primal_bfs` (independently recomputed via exact BFS on the raw graph, asserting `|S| <= b`, `S cap F = empty`, and `lp_root_after_cuts <= mip_dual_bound + 1e-4 <= mip_primal_bfs + 1e-4`), `mip_raw_gap_pct`, `mip_nodes`, `status`.

**Neutral Post-Run Aggregates (computed identically across all `16` instances AND stratified per `4`-instance family):**
1. **Dual/Root Bound Aggregate:** Count of strict root LP lifts (`lp_aug > lp_base + 1e-6`), mean absolute LP lift, and mean additional relative root gap closed (over instances where `best_primal - lp_base > 1e-6`);
2. **Integer Search & Optimality Aggregate:** Instances solved to optimality within `60s` (`BASE_FULL` vs. `AUG_HUB`), mean final raw MIP gap (`%`) across all `16` instances (and across instances unsolved by at least one arm);
3. **Total Monotone Wall-Time & Node Aggregate:** Shifted geometric mean (`shift = 1.0s`) of `t_total_s` (all `16` instances censored at `60.0s`, AND common-solved subset), shifted geometric mean (`shift = 10.0`) of `mip_nodes` (common-solved subset), and paired win / tie / loss counts (`>= 10%` relative AND `>= 0.10s` absolute difference in `t_total_s`).

---

## 4. Pre-Registered Two-Tier Pass vs. Honest-Closure Criteria (Zero Post-Hoc Retuning)

1. **Mandatory Integrity Gate (hard fail if violated):** `0` independent BFS primal discrepancies and `0` dual-validity violations (`lp_root_after_cuts <= mip_primal_bfs + 1e-4` and `mip_dual_bound <= best_primal + 1e-4`) across all `32` arm-instance runs.
2. **Tier 1 — Material Held-Out Polyhedral / Dual-Bound Lift Pass:**
   - `AUG_HUB` strictly lifts the post-cut root LP bound above `BASE_FULL` (`> 1e-6`) on **`>= 10 / 16`** held-out instances, spanning at least `2` distinct families (including at least one non-bipartite family where Clique-Chord and Alozie $C_5$ are active); AND
   - Mean additional root integrality-gap closure over `BASE_FULL` is **`>= 10.0%`** overall (across instances with positive `BASE_FULL` root gap).
3. **Tier 2 — Practical Total-Search Speed / Solve-Capacity Pass (strictly separate from Tier 1!):**
   - `AUG_HUB` solves **`>=`** as many instances to certified optimality within the common `60.0s` monotone wall deadline as `BASE_FULL` (and achieves strictly lower or equal mean final MIP gap if any instances time out); AND
   - Shifted geometric mean of **total monotone wall time** `t_total_s` (build + simplicial + LP/sep + MIP) improves by **`>= 15%`** (`sgm_ratio <= 0.85`), with wins strictly exceeding losses on genuinely branching instances (`mip_nodes > 1`) and without severe regression (`sgm_ratio > 1.25`) on `>= 2` of the `4` families.
4. **Honest Closure Rule:**
   - If Tier 1 passes while Tier 2 fails (e.g., tighter root LP bounds accompanied by neutral or slower total wall time due to LP row density), **NO practical speed claim is permitted**: report the exact numbers transparently as a polyhedral dual-bound tightening result with an empirical LP-density vs. branch-and-bound tradeoff, and **do not retune** cut caps or thresholds on the same `16` held-out seeds.
   - If Tier 1 fails as well, close the held-out computational claim outright.
