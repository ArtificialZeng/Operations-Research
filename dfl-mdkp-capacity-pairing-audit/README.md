# Decision-Focused Learning Under Unknown Constraints: Scenario-Row Indexing Audit & Controlled Capacity-Pairing Study (`ODECE` MDKP Benchmark)

**State:** **FROZEN (2026-11-24)** — Auditable benchmark-integrity research artifact (no additional training, reruns, or tuning).  
**Upstream Reference:** [`JayMan91/OdeceDFLforConstraintsNeurips25`](https://github.com/JayMan91/OdeceDFLforConstraintsNeurips25) (NeurIPS 2025, commit `1b432e03ce9ded1e504df60fd4c44cf936334d4f`, **Apache-2.0**; full upstream checkout excluded — pinned by commit and file SHA-256 in [MANIFEST.json](MANIFEST.json)).

---

## 1. Epistemic Scope Separation (Read Before Citing)

This archive deliberately separates three distinct kinds of evidence and **makes no reproduction claim about original published NeurIPS Table 2 numbers**:

1. **Direct Source/Index Proof (Exact Code Audit):** Programmatic inspection of pinned upstream `KnapsackWeightExp.py` (L71–83), `KnapsackCapaExp.py` (L64–75), and `OptProblems/knapsack/kpdataset.py` (L19–60) proves that both released MDKP scripts pass only `(X, w)` to `train_test_split`, while passing unsplit `(capacity, costs)` to `knapsack_dataset(...)` for `train` (`0:900`), `val` (`0:100`), and `test` (`0:500`). Under official defaults (`fixed_cost=False`, `deg=6`, `noise_width=0.25`, `N=1500`), all four fields vary across instances, so `KnapsackCapaExp.py` misaligns `899–900/900` train rows and `500/500` test rows while reusing `0:499` inside `0:899` ([SOURCE_INDEX_RECEIPT.json](SOURCE_INDEX_RECEIPT.json)).
2. **Controlled Interventions (Paired Counterfactuals):** Stages 2a–2d isolate training capacity-label pairing while holding clean `(X, w, costs)` and clean validation/test data fixed; Stage 3 runs a `2 × 2` train-pairing × test-pairing factorial comparing `ODECE(alpha=0.5)` against upstream `PFL/MSE` on published diagnostic seeds `11` and `15` (raw policy only, strict prediction-solver isolation).
3. **Adapted Metrics & Solver Scaffold (Not Published Paper Scores):** Because commercial Gurobi is unavailable, training uses OR-Tools `CP-SAT` (`_SCALE=10000`) and all confirmatory test oracles/evaluations use unrounded `float64` `HiGHS 1.16.0` (`mip_rel_gap=1e-4`; **`kOptimal` denotes HiGHS optimality within `1e-4` solver tolerance**, not exact rational optimality). Training runs in `torch.float64` with paired identical initialization, deterministic minibatch permutations, documented `ODECE` numerical guards (`Guard 1`: empty-IPL `0.0` preventing upstream `NaN`; `Guard 2`: `mask==0`, symmetric at `alpha=0.5`), exact instance-level denominators, and all-instance strict 0–1 greedy integer-repair scoring alongside source-defined metrics.

---

## 2. Summary of Findings & Required Audit Disclosures

### Track B — `MDKP-Capacity` Indexing-Defect Interventions & `2 × 2` Factorial

| Stage | Seeds & Design | Headline Result | Explicit Caveat / Audit Disclosure |
|---|---|---|---|
| **Provenance** | Commit `1b432e03...` | Direct source proof: `KnapsackCapaExp.py` misaligns `899–900/900` train & `500/500` test rows; clean OLS signal `+0.538` `OOS R^2` vs mispaired `-0.005` | Exact code & signal receipt ([SOURCE_INDEX_RECEIPT.json](SOURCE_INDEX_RECEIPT.json), [MDKP_CAPACITY_SIGNAL_RECEIPT.json](MDKP_CAPACITY_SIGNAL_RECEIPT.json)) |
| **Stage-2a** | `11–15` (0 MIPs) | Clean > mispaired on `5/5` seeds for OLS (`+0.538` vs `-0.005`) and 20-ep `Adam-MSE` (`-0.774` vs `-1.093`) | **Raw compound gate evaluated `False`** (20-ep `Adam-MSE` under-converged; OLS seed-15 $p=2.78\times 10^{-8} > 10^{-10}$) |
| **Stage-2b** | `11–15` (`ValPinned<=10%`) | `OLS` clean vs mispaired: `16.38%` vs `26.15%` frac (`16.96%` vs `26.59%` int, risk `9.96%` vs `11.24%`); `Adam-MSE`: `24.07%` vs `27.22%` | **Post-deviation predeclared exploratory** downstream intervention (not a confirmatory gate pass; [STAGE2_CAPACITY_INTERVENTION_RESULT.md](STAGE2_CAPACITY_INTERVENTION_RESULT.md)) |
| **Stage-2c** | `16` (supporting prior, `ODECE a=0.5`) | `ODECE-Clean` `27.88%` frac / `28.02%` int (`3.20%` risk) vs `ODECE-Mispaired` `42.56%` / `42.73%` (`2.00%` clipped / `2.60%` unclipped) -> **`-14.71 pp` int** | **Parity & timing erratum** ([STAGE2C_PARITY_AND_TIMING_ERRATUM.md](STAGE2C_PARITY_AND_TIMING_ERRATUM.md), [ODECE_CAPACITY_PARITY_AUDIT_LOG.json](ODECE_CAPACITY_PARITY_AUDIT_LOG.json)): auxiliary handwritten check relaxed `1e-10 -> 1e-9` at `13:41:07` (measured `1.58e-10`); production Stage-2c ran strictly on direct PyTorch `src/odece.py` autograd (`<=2.14e-10` vs FD) |
| **Stage-2d** | Untouched `17, 18` (direct-only gate `true`) | `ValPinned<=10%` (`g*=0.00`, no fallback): Seed `17` **`-4.411 pp`** int (`24.31%` vs `28.72%`), risk **`+8.00 pp`** (**`11.80%`** vs `3.80%`); Seed `18` **`-8.977 pp`** int (`29.52%` vs `38.49%`), risk **`+3.60 pp`** (`5.20%` vs `1.60%`) | **Consistent risk increase on BOTH held-out seeds; seed `17` exceeds the `10%` validation threshold on test (`11.80%`).** Seed `16` kept separate as supporting prior evidence; no seeds added ([STAGE2D_SEEDS_17_18_CONFIRMATION_RESULT.md](STAGE2D_SEEDS_17_18_CONFIRMATION_RESULT.md)) |
| **Stage-3** | Published diagnostic subset `11, 15` (`2 × 2` factorial, raw policy, `0` test skips) | Diagonal `ODECE(0.5) - PFL/MSE` integer-repair `p=1` gap shrinks by >50% under full row alignment: **Seed `11`: `+19.042 -> +9.104 pp`** (`-9.938 pp`; risk `-49.80 -> -44.20 pp`); **Seed `15`: `+15.298 -> +7.082 pp`** (`-8.216 pp`; risk `-50.80 -> -54.60 pp`) | **Neither seed reverses the relative feasibility/repair tradeoff** (`8/8` cells `tradeoff_ODECE_lower_risk_higher_repair`). Controlled adaptation only, never reproduced paper scores ([STAGE3_CAPACITY_PFL_VS_ODECE_RESULT.md](STAGE3_CAPACITY_PFL_VS_ODECE_RESULT.md)) |

### Track A — Aligned `MDKP-Weights` Audit (Negative / Null Stable-Dominance Archive)

- **Stage-0 (seed `11`, exploratory):** `SW-Pinball` failed to beat ordinary `Uniform-Pinball`; frontiers crossed (`<=10%` risk `Uniform` `11.22%` vs `ODECE` `15.11%`; `<=5%` `ODECE` `15.11%` vs `Uniform` `16.05%`); CP-SAT swap and penalty `0.21` vs `1.0` documented in [STAGE0_EXPLORATORY_ERRATA.md](STAGE0_EXPLORATORY_ERRATA.md).
- **Stage-1a (seed `12`, validation-pinned `10%`):** `Uniform-Pinball` `9.4172%` frac / `9.5291%` int (`9.4%` strict risk) vs `ODECE` `10.5186%` / `10.7449%` (`7.2%` risk); at `5%` both missed on test; independent `float64` weights PyTorch parity passed ([ODECE_PYTORCH_PARITY_RECEIPT.json](ODECE_PYTORCH_PARITY_RECEIPT.json)).
- **Stage-1b (reserved seeds `13–15`, validation-pinned `10%` HiGHS):** Uniform / ODECE loss (risk): Seed `13` `13.13% / 12.55%` (`3.4% / 5.0%`); Seed `14` `12.86% / 14.15%` (`3.8% / 6.0%`, ODECE val fallback `11%`); Seed `15` `8.55% / 10.81%` (`18.2% / 12.4%`, both miss `10%`). Train+val compute `10.35 s` (`3,000` ILPs) vs `1,969.69 s` (`382,800` ILPs). **No stable per-seed dominance**; pooled uncertainty strictly conditional on the 3 fitted pairs ([STAGE1B_MULTISEED_13_15_RESULT.md](STAGE1B_MULTISEED_13_15_RESULT.md)).

---

## 3. Dependencies, Upstream Pin & Reproducibility Instructions

### 3.1 Verify Archive Integrity (Zero External Dependencies)
```bash
python verify_manifest.py
```
Verifies exact byte sizes and SHA-256 hashes for every file in [MANIFEST.json](MANIFEST.json), confirms zero unlisted files, and checks that public-facing `.md` files contain zero machine-local paths or excluded guidance.

### 3.2 Environment & Pinned Upstream Checkout
```bash
# 1. Clone pinned upstream repo (Apache-2.0) into ./official_odece_repo
git clone https://github.com/JayMan91/OdeceDFLforConstraintsNeurips25.git official_odece_repo
git -C official_odece_repo checkout 1b432e03ce9ded1e504df60fd4c44cf936334d4f

# 2. Install Python 3.12 dependencies (see requirements.txt)
uv venv --python 3.12
uv pip install --index-strategy unsafe-best-match \
  --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt
```
*(Sealed `.py` runners are preserved **byte-for-byte** to match the original SHA-256 hashes embedded in the sealed summary JSONs. Because their original `BASE` constant points to the execution directory, update `BASE = pathlib.Path(__file__).resolve().parent` on a local copy before re-executing in a different working directory.)*

### 3.3 Key Verification & Audit Entrypoints
- Direct upstream source/index receipt: `python source_index_discrepancy_receipt.py`
- Direct `float64` `ODECE` PyTorch parity gate: `python verify_odece_capacity_direct_pytorch_gate.py`
- Stage-3 synthetic loading/isolation/metric & `PFL/MSE` check: `python verify_stage3_synthetic_loading_metrics.py`
- Stage-2d (`seeds 17–18`) & Stage-3 (`seeds 11, 15` factorial): `python stage2d_odece_capacity_seeds_17_18.py`, `python stage3_capacity_pfl_vs_odece_factorial.py`

---

## 4. Ordered Archive Inventory & Exclusions

All `145` archived files (`~8.8 MB`) are indexed in strict stage order in [MANIFEST.json](MANIFEST.json):
- **Overview & Provenance:** [STATUS.md](STATUS.md), [SELECTION_AND_OVERLAP.md](SELECTION_AND_OVERLAP.md), [SOURCE_INDEX_RECEIPT.json](SOURCE_INDEX_RECEIPT.json), [MDKP_CAPACITY_SIGNAL_RECEIPT.json](MDKP_CAPACITY_SIGNAL_RECEIPT.json)
- **Track A (`MDKP-Weights`):** [STAGE0_PROTOCOL.md](STAGE0_PROTOCOL.md) · [STAGE0_EXPLORATORY_ERRATA.md](STAGE0_EXPLORATORY_ERRATA.md) · [STAGE1A_SEED12_RESULT.md](STAGE1A_SEED12_RESULT.md) · [ODECE_PYTORCH_PARITY_RECEIPT.json](ODECE_PYTORCH_PARITY_RECEIPT.json) · [STAGE1B_MULTISEED_13_15_RESULT.md](STAGE1B_MULTISEED_13_15_RESULT.md) + `stage1b_multiseed_13_15/` (aggregate, per-seed summaries/logs, and all `25` confirmatory HiGHS per-instance JSONs)
- **Track B (`MDKP-Capacity`):** [STAGE2A_CAPACITY_PAIRING_PROTOCOL.md](STAGE2A_CAPACITY_PAIRING_PROTOCOL.md) · [STAGE2_CAPACITY_INTERVENTION_RESULT.md](STAGE2_CAPACITY_INTERVENTION_RESULT.md) · [STAGE2C_PARITY_AND_TIMING_ERRATUM.md](STAGE2C_PARITY_AND_TIMING_ERRATUM.md) · [STAGE2C_ODECE_CAPACITY_SEED16_RESULT.md](STAGE2C_ODECE_CAPACITY_SEED16_RESULT.md) · [ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json](ODECE_CAPACITY_DIRECT_PYTORCH_GATE_RECEIPT.json) · [STAGE2D_SEEDS_17_18_CONFIRMATION_RESULT.md](STAGE2D_SEEDS_17_18_CONFIRMATION_RESULT.md) · [STAGE3_SYNTHETIC_CHECK_RECEIPT.json](STAGE3_SYNTHETIC_CHECK_RECEIPT.json) · [STAGE3_CAPACITY_PFL_VS_ODECE_RESULT.md](STAGE3_CAPACITY_PFL_VS_ODECE_RESULT.md) + complete per-seed directories (`stage2c_odece_capacity_seed16/`, `stage2d_odece_capacity_seed17/`, `stage2d_odece_capacity_seed18/`, `stage3_capacity_factorial_seed11/`, `stage3_capacity_factorial_seed15/`) containing all checkpoints, arm outputs, summaries, and raw per-instance HiGHS JSONs.

**Explicit Exclusions:** upstream checkout (`official_odece_repo/`), internal coordination notes, `__pycache__/`, binaries, caches, secrets, editor files, and `112` intermediate CP-SAT grid-sweep per-instance JSONs from Stage-1a (`28` files, `3.67 MB`) and Stage-1b (`84` non-HiGHS files, `10.52 MB`, reproducible from included scripts; all summaries, incremental logs, and confirmatory HiGHS per-instance JSONs are retained).
