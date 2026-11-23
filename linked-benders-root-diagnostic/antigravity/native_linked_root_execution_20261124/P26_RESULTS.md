# Bounded Díaz `p26` Multi-Cut Linked Benders Stress Check — Results & Closure Decision

**Handoff Directory:** `D:\AI_Science\antigravity\native_linked_root_execution_20261124\`  
**Run Date:** 2026-11-24  
**Authoritative Evidence:**
- Result JSON: `p26_multicut_result.json`
- Pre-registered protocol (unchanged): `P26_MULTICUT_PROTOCOL.md` (SHA-256 `2111174e79ff1e251f8cde7d2501a10c3d15455be14a5c66e60778098cba11f2`)
- Wrapper script: `linked_benders_p26.py` (SHA-256 `37fa60b055a90fe8305c52bdc0920bbdfdec5002cf27557191ca4a26473aa0cf`, incorporating the pre-run 4-boolean `both_reached_target` alignment)
- Reused `p01` module (unchanged): `linked_benders_pilot.py` (SHA-256 `eff17d9a81ef08b06705b6d64034f18dedcc4577c7350779b1ddd4ea7be3ed53`)
- Independent sealed reference (frozen, read-only): `experiments/linked_root/runs_45s/p26_linked.json` & `p26_linked_separated.json`

---

## 1. Execution & Verification Summary

- **Command Executed**:
  ```bash
  wsl.exe -e /usr/bin/timeout --kill-after=2s 95s /usr/bin/taskset -c 26 /usr/bin/env \
    PYTHONPATH=/home/ailab/frontieror_letelier_runtime_20261124/site314 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 \
    /home/ailab/frontieror_letelier_runtime_20261124/python/cpython-3.14.10-linux-x86_64-gnu/bin/python3.14 \
    -B /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/linked_benders_p26.py \
    --out /mnt/d/AI_Science/antigravity/native_linked_root_execution_20261124/p26_multicut_result.json
  ```
- **Exit & Runtime**: Exit code `0`, total wall time `9.511 s` within the `95 s` outer timeout (`cpu_affinity: [26]`, Python `3.14.10`, NumPy `2.5.3`, SciPy `1.18.1`, secondary fixed-history pricing omitted).
- **Soundness & Reference Compatibility**: Both arms passed exact rational certification (`all_certificates_sound: true`, `trimmed_flow_grid_ticks: 0`) and overlapped the independent sealed `p26` reference intersection:
  $$I_{\mathrm{ref}}(\text{p26}) = \left[\frac{46331823944918700410161309}{8376550182000000000000},\; \frac{99105505765317713183013847}{17917754400000000000000}\right] \approx [5531.1342901615,\; 5531.1342902053] \quad (\text{width } 4.385 \times 10^{-8}).$$
- **Separate Candidate Paths**: Confirmed (`paths_distinct: true`, `first_differing_iter: 0`, `max_pointwise_l1_diff: 9.22`).

---

## 2. Paired `p26` Multi-Cut Results (`30 s` / `60` sweeps / `1e-6` target)

| Metric | `linked` (Original $\rho$) | `linked_separated` ($\eta + 200$ Hinges) |
|---|---:|---:|
| Stop Status | `converged_rel_tol` | `converged_rel_tol` |
| Completed Candidate Sweeps | **8** | **8** |
| Master Solves / Total Cuts | 9 / 1,447 | 9 / 1,447 |
| Observation Time (pre-cert / total, descriptive) | 4.540 s / 4.646 s (0.099 s master + 4.438 s sub) | 4.671 s / 4.779 s (0.124 s master + 4.544 s sub) |
| Exact Certified Lower $L_{\mathrm{cert}}$ | `5559818873390244018884300647/1005186021840000000000000` (`5531.1342901614935`) | `694977359173780068812450671/125648252730000000000000` (`5531.13429016149`) |
| Exact Certified Upper $U_{\mathrm{cert}}$ | `102959645268173326217151857/18614555960000000000000` (`5531.136251083226`) | `20660798394548330987036881/3735362400000000000000` (`5531.136254556808`) |
| Exact `original_same_primal` | `5531.136251083226` | `5531.136254608774` (`55` positive-hinge scenarios) |
| Exact Certified Rel. Gap (Width) | **`3.545e-07`** (`0.001961`) | **`3.552e-07`** (`0.001964`) |
| Sound / Overlaps $I_{\mathrm{ref}}(\text{p26})$ | `true` / `true` | `true` / `true` |
| Binary Opening? | `false` (`2` fractional sites) | `false` (`2` fractional sites) |

- **Fractional vs. Integer Scope**: Both terminal upper bounds are **continuous fractional root LP bounds** ($x \in [0, 1]^{20}$, `2` fractional facilities, `is_binary_opening: false`, `integer_incumbent_searched: false`), not integer incumbents. Both certified lower bounds are valid lower bounds for the continuous LP relaxation and the binary MIP. Single-run observation timings (`4.540 s` vs. `4.671 s`) are descriptive only.

---

## 3. Pre-Registered Gate Evaluation & Final Decision

- **Certificate Comparability**: `certificates_comparable = true`.
- **Target Attainment (All Four Booleans)**: `orig_cert_target_met = true`, `sep_cert_target_met = true`, `orig_stop_converged = true`, `sep_stop_converged = true` $\implies$ `both_reached_certified_target = true`.
- **Decision Branch (`both_reached_certified_target`)**:
  - Required threshold to motivate later replication: `sweeps_saved_by_separated >= 2`.
  - Observed: `orig_completed_sweeps = 8`, `sep_completed_sweeps = 8`, **`sweeps_saved_by_separated = 0`** (and certified terminal relative gap was essentially identical: `3.545e-07` vs. `3.552e-07`, difference `-6.28e-10`).
- **Gate Output**: `motivates_later_replication = false`, **`verdict = "close_fractional_root_scale_line"`**.

### Recommendation
**Close the fractional-root linked Benders scale line and preserve both arms' certified records.** Across both Díaz `p01` (`5` vs. `5` sweeps) and Díaz `p26` (`8` vs. `8` sweeps), equal-disaggregation multi-cut linked Benders with exact shortage separation saves **0** candidate sweeps over original-price multi-cut linked Benders once 200 per-scenario cuts are active in the master. No further fractional-root scaling runs (e.g., `p50`) are warranted under this hypothesis; both arms are archived cleanly as verified null-difference multi-cut evidence.
