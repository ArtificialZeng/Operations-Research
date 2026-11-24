"""
Stage-0c Bounded Exploratory Canonical Replay Pilot (Teacher-Forced Only; ZERO New Decoding or Labels).

Locked Protocol: STAGE0C_CANONICAL_REPLAY_PROTOCOL.md
Pre-Launch Fixture Receipt: STAGE0C_CANONICAL_FIXTURE_RECEIPT.json

Scope & Hard Exclusions:
  - Uses ONLY the 24 sealed Stage-0b `neutral_menu` outputs (`neutral_menu__G_compact_menu` and
    `neutral_menu__G_optws_menu`) and their identical frozen BFCL inert AST verdicts.
  - Does NOT open, load, or split `bfcl_future_blind_test_ids_sealed.json` (416 blind IDs untouched;
    SHA-256 verified before and after).
  - Does NOT start a second model (uses the identical verified local Qwen/Qwen2.5-1.5B-Instruct snapshot).
  - Applies fixed, typed parsed-call canonicalization (`canonicalize_parsed_call`: ordinary JSON
    serialization, standard spaces, fixed root key order `"name"` then `"arguments"`, recursively sorted
    argument-map keys, preserving scalar types, list order, and semantics; zero hindsight or gold).
  - Runs ONE unmasked teacher-forced forward pass per unique canonical string under the exact same
    Stage-0b format-neutral prompt (`Prompt_Neutral`), deduplicating equal canonical calls within each
    prompt (27 unique passes vs 48 undeduplicated).
  - Compares `raw_post_gnll_smt_mean`, `raw_pre_gnll_smt_mean`, and `canon_gnll_smt_mean`
    (plus secondary sensitivity on `*_all_mean` and `*_smt_sum`) on ALL 24 free-generated pairs
    using:
      (1) PRIMARY: Leave-One-Tool-Family-Out (LOFO) source calibration (18 disjoint tool-family clusters)
          with target in-grammar LOFO controls (`W->W`, `C->C`), plus cluster-bootstrap CIs.
      (2) COMPANION: Full-sample in-sample source calibration with target in-grammar controls.
  - Evaluates the locked prespecified decision gate (`>= 8 pp` smaller worst-direction coverage error
    over strongest raw post baseline without worse mean error and without new operational harm).
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import math
import os
import pathlib
import sys
import time
from typing import Dict, List, Tuple

import numpy as np
import torch
from scipy import stats
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(BASE))

import grammar_utils as gu  # noqa: E402
import select_stage0b_subset_and_verify as s0b  # noqa: E402
import stage0_grammar_confidence_pilot as s0  # noqa: E402
import verify_stage0c_canonical_fixture as v0c  # noqa: E402

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
MODEL_LICENSE = "Apache-2.0"
TARGET_COVERAGE = 0.80
MINORITY_UNSTABLE_THRESH = 5
GATE_MIN_WORST_DIR_GAIN = 0.08  # >= 8 pp smaller worst-direction absolute coverage error

SEALED_HASHES = {
    "bfcl_stage0_pilot_dataset.json": "191e8e8c8c9c00f0f7dacd0a98b6f592b02e878e444da0016e99f1e31c1cd446",
    "bfcl_future_blind_test_ids_sealed.json": "64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a",
    "grammar_utils.py": "d063e5e347bf2928f1c6f22becafd67611f711842960276e1399359dab966423",
    "MODEL_TRANSPORT_RECEIPT.json": "74cdd02fae04f8328eef6a323f3e80e2f02d52a2b0f8d200c2674b629071c8ad",
    "stage0_pilot_outputs/stage0_pilot_per_instance.jsonl": "06c90359910592d3d43916c50479abadc15a5cac2d9600ada8b2b0e2566b6aa8",
    "stage0_pilot_outputs/stage0_pilot_summary.json": "a39963f0cf7d00a1ef4c2c0864708883a7f01072e364580c6e7fd3d4e7b8af6c",
    "select_stage0b_subset_and_verify.py": "0a0d9b95cedc580b8fdff00ac44277b6e0409c411dcc0dc4138a1fed168defa1",
    "STAGE0B_SUBSET_24_RECEIPT.json": "65bcba4a28ee39bf3ff7f4173e773c110c076a136f663cda7dcde57f928cbf46",
    "STAGE0B_FIXTURE_RECEIPT.json": "04ee945695311cc738406e5a769556b14ed0bbc7e8212b85ac86cdc36d456d65",
    "stage0b_outputs/stage0b_per_instance.jsonl": "724e921058677ee9b32d5a2e1fc74083af9d6dd29717c32bd6a9bc33ce489c9e",
    "stage0b_outputs/stage0b_summary.json": "9036772bb510bac388dc123dadaef89a1cf037a40ba0806ecef0cbc5b352812d",
}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_sealed_hashes(label: str) -> Dict[str, str]:
    out = {}
    for rel, exp in SEALED_HASHES.items():
        p = BASE / rel
        assert p.exists(), f"[{label}] Missing sealed file: {rel}"
        got = sha256_file(p)
        assert got == exp, f"[{label}] SHA-256 mismatch on {rel}: expected {exp}, got {got}"
        out[rel] = got
    return out


def order_stat_threshold(vals: np.ndarray, target_cov: float = TARGET_COVERAGE) -> float:
    """Exact deterministic order-statistic threshold achieving `target_cov` on `vals`."""
    n = len(vals)
    assert n > 0
    k = max(1, int(math.floor(target_cov * n + 1e-12)))
    order = np.argsort(vals, kind="mergesort")
    return float(vals[order[k - 1]])


def eval_lofo_direction(
    u_src: np.ndarray,
    u_tgt: np.ndarray,
    err_tgt: np.ndarray,
    clusters: List[str],
    target_cov: float = TARGET_COVERAGE,
) -> Dict:
    """
    Leave-One-Tool-Family-Out (LOFO) source calibration:
    For each item i with tool-family cluster g(i), fits threshold `tau_src` on all items j
    with cluster(j) != g(i), and evaluates `u_tgt[i] <= tau_src`.
    Also computes the exact target in-grammar LOFO control (`tau_tgt` fit on `u_tgt[j]` for cluster(j) != g(i)).
    """
    n = len(u_tgt)
    acc_xfer = np.zeros(n, dtype=bool)
    acc_ctrl = np.zeros(n, dtype=bool)
    taus_src = np.zeros(n, dtype=np.float64)
    taus_ctrl = np.zeros(n, dtype=np.float64)
    cal_sizes = []

    for i in range(n):
        gi = clusters[i]
        cal_idx = [j for j in range(n) if clusters[j] != gi]
        cal_sizes.append(len(cal_idx))
        t_src = order_stat_threshold(u_src[cal_idx], target_cov)
        t_ctrl = order_stat_threshold(u_tgt[cal_idx], target_cov)
        taus_src[i] = t_src
        taus_ctrl[i] = t_ctrl
        acc_xfer[i] = bool(u_tgt[i] <= t_src)
        acc_ctrl[i] = bool(u_tgt[i] <= t_ctrl)

    n_acc = int(np.sum(acc_xfer))
    n_ctrl = int(np.sum(acc_ctrl))
    cov = float(n_acc / n)
    ctrl_cov = float(n_ctrl / n)
    risk = float(np.mean(err_tgt[acc_xfer])) if n_acc > 0 else float("nan")
    ctrl_risk = float(np.mean(err_tgt[acc_ctrl])) if n_ctrl > 0 else float("nan")
    n_err_tgt = int(np.sum(err_tgt == 1.0))

    return {
        "n_total": n,
        "n_clusters": len(set(clusters)),
        "cal_set_size_min": int(min(cal_sizes)),
        "cal_set_size_max": int(max(cal_sizes)),
        "n_accepted": n_acc,
        "empirical_coverage": cov,
        "signed_cov_err_vs_target": cov - target_cov,
        "abs_cov_err_vs_target": abs(cov - target_cov),
        "n_accepted_errors": int(np.sum(err_tgt[acc_xfer] == 1.0)),
        "empirical_selective_risk": risk,
        "target_in_grammar_lofo_control": {
            "n_accepted": n_ctrl,
            "empirical_coverage": ctrl_cov,
            "signed_cov_err_vs_target": ctrl_cov - target_cov,
            "abs_cov_err_vs_target": abs(ctrl_cov - target_cov),
            "n_accepted_errors": int(np.sum(err_tgt[acc_ctrl] == 1.0)),
            "empirical_selective_risk": ctrl_risk,
        },
        "cov_shift_vs_target_control": cov - ctrl_cov,
        "abs_cov_shift_vs_target_control": abs(cov - ctrl_cov),
        "risk_shift_vs_target_control": (risk - ctrl_risk) if (math.isfinite(risk) and math.isfinite(ctrl_risk)) else float("nan"),
        "tau_src_mean": float(np.mean(taus_src)),
        "tau_src_std": float(np.std(taus_src)),
        "tau_ctrl_mean": float(np.mean(taus_ctrl)),
        "tau_ctrl_std": float(np.std(taus_ctrl)),
        "n_target_errors_total": n_err_tgt,
        "risk_claim_prohibited_caveat": (
            f"ONLY {n_err_tgt} error(s) in target arm out of {n} (minority <= {MINORITY_UNSTABLE_THRESH}); "
            "NO claim of improved selective risk is valid."
        ),
        "accepted_mask": [bool(x) for x in acc_xfer],
        "control_accepted_mask": [bool(x) for x in acc_ctrl],
    }


def eval_fullsample_direction(
    u_src: np.ndarray,
    u_tgt: np.ndarray,
    err_tgt: np.ndarray,
    target_cov: float = TARGET_COVERAGE,
) -> Dict:
    """Full-sample in-sample source calibration (exact audit companion to Stage-0b)."""
    n = len(u_tgt)
    t_src = order_stat_threshold(u_src, target_cov)
    t_ctrl = order_stat_threshold(u_tgt, target_cov)
    acc_xfer = u_tgt <= t_src
    acc_ctrl = u_tgt <= t_ctrl
    n_acc = int(np.sum(acc_xfer))
    n_ctrl = int(np.sum(acc_ctrl))
    cov = float(n_acc / n)
    ctrl_cov = float(n_ctrl / n)
    risk = float(np.mean(err_tgt[acc_xfer])) if n_acc > 0 else float("nan")
    ctrl_risk = float(np.mean(err_tgt[acc_ctrl])) if n_ctrl > 0 else float("nan")
    n_err_tgt = int(np.sum(err_tgt == 1.0))

    return {
        "n_total": n,
        "tau_src": t_src,
        "tau_ctrl": t_ctrl,
        "n_accepted": n_acc,
        "empirical_coverage": cov,
        "signed_cov_err_vs_target": cov - target_cov,
        "abs_cov_err_vs_target": abs(cov - target_cov),
        "n_accepted_errors": int(np.sum(err_tgt[acc_xfer] == 1.0)),
        "empirical_selective_risk": risk,
        "target_in_grammar_fullsample_control": {
            "n_accepted": n_ctrl,
            "empirical_coverage": ctrl_cov,
            "signed_cov_err_vs_target": ctrl_cov - target_cov,
            "abs_cov_err_vs_target": abs(ctrl_cov - target_cov),
            "n_accepted_errors": int(np.sum(err_tgt[acc_ctrl] == 1.0)),
            "empirical_selective_risk": ctrl_risk,
        },
        "cov_shift_vs_target_control": cov - ctrl_cov,
        "abs_cov_shift_vs_target_control": abs(cov - ctrl_cov),
        "risk_shift_vs_target_control": (risk - ctrl_risk) if (math.isfinite(risk) and math.isfinite(ctrl_risk)) else float("nan"),
        "n_target_errors_total": n_err_tgt,
        "risk_claim_prohibited_caveat": (
            f"ONLY {n_err_tgt} error(s) in target arm out of {n}; in-sample self-calibration caveat applies; "
            "NO claim of improved selective risk is valid."
        ),
    }


def eval_scorer_full_suite(
    name: str,
    u_c: np.ndarray,
    u_w: np.ndarray,
    err_c: np.ndarray,
    err_w: np.ndarray,
    clusters: List[str],
    equal_canon_mask: np.ndarray,
) -> Dict:
    """Computes LOFO (primary), full-sample (companion), and score-variation diagnostics."""
    lofo_cw = eval_lofo_direction(u_c, u_w, err_w, clusters, TARGET_COVERAGE)
    lofo_wc = eval_lofo_direction(u_w, u_c, err_c, clusters, TARGET_COVERAGE)
    lofo_worst_err = max(lofo_cw["abs_cov_err_vs_target"], lofo_wc["abs_cov_err_vs_target"])
    lofo_mean_err = 0.5 * (lofo_cw["abs_cov_err_vs_target"] + lofo_wc["abs_cov_err_vs_target"])
    lofo_worst_shift_ctrl = max(lofo_cw["abs_cov_shift_vs_target_control"], lofo_wc["abs_cov_shift_vs_target_control"])
    lofo_mean_shift_ctrl = 0.5 * (lofo_cw["abs_cov_shift_vs_target_control"] + lofo_wc["abs_cov_shift_vs_target_control"])

    fs_cw = eval_fullsample_direction(u_c, u_w, err_w, TARGET_COVERAGE)
    fs_wc = eval_fullsample_direction(u_w, u_c, err_c, TARGET_COVERAGE)
    fs_worst_err = max(fs_cw["abs_cov_err_vs_target"], fs_wc["abs_cov_err_vs_target"])
    fs_mean_err = 0.5 * (fs_cw["abs_cov_err_vs_target"] + fs_wc["abs_cov_err_vs_target"])
    fs_worst_shift_ctrl = max(fs_cw["abs_cov_shift_vs_target_control"], fs_wc["abs_cov_shift_vs_target_control"])
    fs_mean_shift_ctrl = 0.5 * (fs_cw["abs_cov_shift_vs_target_control"] + fs_wc["abs_cov_shift_vs_target_control"])

    diff = u_c - u_w
    abs_diff = np.abs(diff)
    eq_abs = abs_diff[equal_canon_mask]
    neq_abs = abs_diff[~equal_canon_mask]

    def dist_stats(x: np.ndarray) -> Dict[str, float]:
        q25, q50, q75 = np.percentile(x, [25, 50, 75])
        return {
            "mean": float(np.mean(x)),
            "std": float(np.std(x)),
            "min": float(np.min(x)),
            "q25": float(q25),
            "median": float(q50),
            "q75": float(q75),
            "iqr": float(q75 - q25),
            "max": float(np.max(x)),
        }

    return {
        "scorer_name": name,
        "distribution_C": dist_stats(u_c),
        "distribution_W": dist_stats(u_w),
        "paired_variation_C_minus_W": {
            "mean_diff": float(np.mean(diff)),
            "std_diff": float(np.std(diff)),
            "median_diff": float(np.median(diff)),
            "mean_abs_diff_all_24": float(np.mean(abs_diff)),
            "max_abs_diff_all_24": float(np.max(abs_diff)),
            "max_abs_diff_on_21_equal_canonical_pairs": float(np.max(eq_abs)) if len(eq_abs) else float("nan"),
            "mean_abs_diff_on_21_equal_canonical_pairs": float(np.mean(eq_abs)) if len(eq_abs) else float("nan"),
            "max_abs_diff_on_3_distinct_canonical_pairs": float(np.max(neq_abs)) if len(neq_abs) else float("nan"),
            "mean_abs_diff_on_3_distinct_canonical_pairs": float(np.mean(neq_abs)) if len(neq_abs) else float("nan"),
            "spearman_rho_C_vs_W": float(stats.spearmanr(u_c, u_w).statistic) if np.std(u_c) > 0 and np.std(u_w) > 0 else float("nan"),
            "kendall_tau_C_vs_W": float(stats.kendalltau(u_c, u_w).statistic) if np.std(u_c) > 0 and np.std(u_w) > 0 else float("nan"),
        },
        "lofo_primary": {
            "C_to_W": lofo_cw,
            "W_to_C": lofo_wc,
            "worst_direction_abs_cov_err": lofo_worst_err,
            "mean_abs_cov_err": lofo_mean_err,
            "worst_direction_abs_shift_vs_ctrl": lofo_worst_shift_ctrl,
            "mean_abs_shift_vs_ctrl": lofo_mean_shift_ctrl,
        },
        "fullsample_companion": {
            "C_to_W": fs_cw,
            "W_to_C": fs_wc,
            "worst_direction_abs_cov_err": fs_worst_err,
            "mean_abs_cov_err": fs_mean_err,
            "worst_direction_abs_shift_vs_ctrl": fs_worst_shift_ctrl,
            "mean_abs_shift_vs_ctrl": fs_mean_shift_ctrl,
        },
    }


def cluster_bootstrap_lofo_comparison(
    clusters: List[str],
    u_cand_c: np.ndarray,
    u_cand_w: np.ndarray,
    u_base_c: np.ndarray,
    u_base_w: np.ndarray,
    err_c: np.ndarray,
    err_w: np.ndarray,
    n_boot: int = 2000,
    seed: int = 20261124,
) -> Dict:
    """
    Cluster bootstrap over the 18 tool-family clusters for LOFO coverage error & paired difference
    (canonical vs raw post baseline). Because each bootstrap resample assigns unique synthetic cluster
    IDs to each drawn cluster copy, LOFO holds out one original tool-family cluster group at a time
    (all items sharing the same drawn cluster identity).
    """
    rng = np.random.default_rng(seed)
    c_to_idx: Dict[str, List[int]] = {}
    for i, c in enumerate(clusters):
        c_to_idx.setdefault(c, []).append(i)
    c_keys = sorted(c_to_idx.keys())
    n_c = len(c_keys)

    cand_cw, cand_wc, cand_worst, cand_mean = [], [], [], []
    base_cw, base_wc, base_worst, base_mean = [], [], [], []
    gain_worst, gain_mean = [], []

    for _ in range(n_boot):
        drawn = rng.integers(0, n_c, size=n_c)
        idxs: List[int] = []
        b_clusters: List[str] = []
        for k in drawn:
            ck = c_keys[k]
            for idx in c_to_idx[ck]:
                idxs.append(idx)
                b_clusters.append(ck)
        if len(set(b_clusters)) < 2:
            continue

        # Fast LOFO on bootstrap sample
        def lofo_covs(us, ut):
            n_b = len(ut)
            n_acc = 0
            # Group by unique cluster in bootstrap draw
            unique_cl = set(b_clusters)
            for cl in unique_cl:
                cal = [p for p, c_p in enumerate(b_clusters) if c_p != cl]
                tau = order_stat_threshold(us[cal], TARGET_COVERAGE)
                for p, c_p in enumerate(b_clusters):
                    if c_p == cl and ut[p] <= tau:
                        n_acc += 1
            return n_acc / n_b

        ccw = lofo_covs(u_cand_c[idxs], u_cand_w[idxs])
        cwc = lofo_covs(u_cand_w[idxs], u_cand_c[idxs])
        bcw = lofo_covs(u_base_c[idxs], u_base_w[idxs])
        bwc = lofo_covs(u_base_w[idxs], u_base_c[idxs])

        cw_err = max(abs(ccw - TARGET_COVERAGE), abs(cwc - TARGET_COVERAGE))
        cm_err = 0.5 * (abs(ccw - TARGET_COVERAGE) + abs(cwc - TARGET_COVERAGE))
        bw_err = max(abs(bcw - TARGET_COVERAGE), abs(bwc - TARGET_COVERAGE))
        bm_err = 0.5 * (abs(bcw - TARGET_COVERAGE) + abs(bwc - TARGET_COVERAGE))

        cand_cw.append(ccw)
        cand_wc.append(cwc)
        cand_worst.append(cw_err)
        cand_mean.append(cm_err)
        base_cw.append(bcw)
        base_wc.append(bwc)
        base_worst.append(bw_err)
        base_mean.append(bm_err)
        gain_worst.append(bw_err - cw_err)  # positive = canonical has SMALLER worst-dir error
        gain_mean.append(bm_err - cm_err)   # positive = canonical has SMALLER mean error

    def ci95(arr):
        lo, hi = np.percentile(arr, [2.5, 97.5])
        return [float(lo), float(hi)]

    return {
        "n_clusters": n_c,
        "n_boot_completed": len(gain_worst),
        "seed": seed,
        "caveat": (
            "Small exploratory sample (N=24 across 18 tool-family clusters; only 1 error in W and 2 errors in C). "
            "Bootstrap intervals reflect wide finite-sample uncertainty and discrete 1/24 (4.17 pp) granularity; "
            "NO selective-risk bootstrap claims are made."
        ),
        "cand_lofo_cov_C_to_W_ci95": ci95(cand_cw),
        "cand_lofo_cov_W_to_C_ci95": ci95(cand_wc),
        "cand_lofo_worst_dir_abs_err_ci95": ci95(cand_worst),
        "cand_lofo_mean_abs_err_ci95": ci95(cand_mean),
        "base_lofo_cov_C_to_W_ci95": ci95(base_cw),
        "base_lofo_cov_W_to_C_ci95": ci95(base_wc),
        "base_lofo_worst_dir_abs_err_ci95": ci95(base_worst),
        "base_lofo_mean_abs_err_ci95": ci95(base_mean),
        "worst_dir_err_reduction_base_minus_cand_ci95": ci95(gain_worst),
        "mean_err_reduction_base_minus_cand_ci95": ci95(gain_mean),
        "frac_boot_worst_dir_reduction_ge_8pp": float(np.mean(np.array(gain_worst) >= GATE_MIN_WORST_DIR_GAIN)),
    }


def main():
    t0 = time.perf_counter()
    pid = os.getpid()

    # 1) HARD PRE-LAUNCH INTEGRITY & PROTOCOL GATES
    pre_hashes = verify_sealed_hashes("PRE-LAUNCH")
    fix_p = BASE / "STAGE0C_CANONICAL_FIXTURE_RECEIPT.json"
    proto_p = BASE / "STAGE0C_CANONICAL_REPLAY_PROTOCOL.md"
    assert fix_p.exists(), "Missing STAGE0C_CANONICAL_FIXTURE_RECEIPT.json!"
    assert proto_p.exists(), "Missing locked STAGE0C_CANONICAL_REPLAY_PROTOCOL.md!"
    fix_rec = json.loads(fix_p.read_text(encoding="utf-8-sig"))
    assert fix_rec["all_fixtures_passed"] is True
    assert fix_rec["all_48_canonical_ast_verdicts_identical_to_sealed_stage0b"] is True
    proto_sha = sha256_file(proto_p)
    fix_sha = sha256_file(fix_p)
    transport_rec = json.loads((BASE / "MODEL_TRANSPORT_RECEIPT.json").read_text(encoding="utf-8-sig"))
    assert transport_rec["verified_exact_match"] is True

    pilot_by_id = {
        it["id"]: it
        for it in json.loads((BASE / "bfcl_stage0_pilot_dataset.json").read_text(encoding="utf-8"))
    }
    s0b_recs = [
        json.loads(l)
        for l in (BASE / "stage0b_outputs" / "stage0b_per_instance.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(s0b_recs) == 24

    device_str = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device_str == "cuda" else torch.float32
    gpu_name = torch.cuda.get_device_name(0) if device_str == "cuda" else "CPU"
    print(
        f"=== Stage-0c Canonical Replay Pilot (PID={pid}, N=24 sealed neutral_menu pairs, model={MODEL_ID}, dev={gpu_name}, dtype={dtype}) ===",
        flush=True,
    )

    t_load = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision="989aa7980e4cf806f80c7fef2b1adb7bc71aa306", local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision="989aa7980e4cf806f80c7fef2b1adb7bc71aa306", dtype=dtype, local_files_only=True).to(device_str)
    model.eval()
    load_s = time.perf_counter() - t_load
    eos_id = tokenizer.eos_token_id if isinstance(tokenizer.eos_token_id, int) else tokenizer.eos_token_id[0]
    is_cuda = device_str == "cuda"
    print(f"  Loaded local snapshot in {load_s:.2f}s (eos_id={eos_id})", flush=True)

    # 2) ONE UNMASKED TEACHER-FORCED FORWARD PASS PER UNIQUE CANONICAL CALL WITHIN EACH PROMPT
    out_dir = BASE / "stage0c_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    inc_path = out_dir / "stage0c_per_instance.jsonl"

    per_instance_records: List[Dict] = []
    unique_tf_times_ms: List[float] = []
    unique_tf_tokens: List[int] = []
    n_unique_passes = 0
    n_dedup_hits = 0

    t_score0 = time.perf_counter()
    with inc_path.open("w", encoding="utf-8") as fout:
        for i, rec in enumerate(s0b_recs):
            iid = rec["id"]
            item = pilot_by_id[iid]

            # Exact Stage-0b format-neutral prompt for BOTH arms
            msgs_neu = s0b.build_messages_stage0b(item, "neutral")
            prompt_neu_text = tokenizer.apply_chat_template(msgs_neu, tokenize=False, add_generation_prompt=True)
            prompt_neu_ids = tokenizer.encode(prompt_neu_text, add_special_tokens=False, return_tensors="pt")
            assert int(prompt_neu_ids.shape[1]) == rec["prompt_len_tokens"]["neutral"], "Neutral prompt token length mismatch!"

            arm_c = rec["arms"]["neutral_menu__G_compact_menu"]
            arm_w = rec["arms"]["neutral_menu__G_optws_menu"]

            canon_c_str = v0c.canonicalize_parsed_call(arm_c["eval"]["parsed_call"])
            canon_w_str = v0c.canonicalize_parsed_call(arm_w["eval"]["parsed_call"])
            equal_canon = (canon_c_str == canon_w_str)

            # Per-prompt deduplication cache (equal canonical calls within prompt scored once)
            prompt_cache: Dict[str, Dict] = {}

            def score_canonical(c_str: str) -> Tuple[Dict, bool]:
                nonlocal n_unique_passes, n_dedup_hits
                if c_str in prompt_cache:
                    n_dedup_hits += 1
                    return prompt_cache[c_str], True

                c_ids = tokenizer.encode(c_str, add_special_tokens=False) + [eos_id]
                n_content = len(c_ids) - 1
                if is_cuda:
                    torch.cuda.synchronize()
                t_f0 = time.perf_counter()
                logits_tv = s0.teacher_force_logits(model, prompt_neu_ids, c_ids)
                if is_cuda:
                    torch.cuda.synchronize()
                tf_ms = (time.perf_counter() - t_f0) * 1000.0

                per_step = [
                    gu.step_mask_metrics_from_logits(logits_tv[t], None, tok)
                    for t, tok in enumerate(c_ids)
                ]
                smt_info = gu.extract_smt_token_indices(tokenizer, c_ids)
                assert smt_info["parsed_ok"] is True
                agg = s0.aggregate_step_scores(per_step, smt_info, n_content)
                assert agg["valid_scores"] is True

                res = {
                    "canonical_text": c_str,
                    "n_content_tokens": n_content,
                    "n_total_tokens_with_eos": len(c_ids),
                    "n_smt_ye26": agg["n_smt_ye26"],
                    "n_smt_val": agg["n_smt_val"],
                    "n_syntax": agg["n_syntax"],
                    "tf_forward_ms": tf_ms,
                    "scores": {
                        "canon_gnll_smt_mean": agg["pre_gnll_smt_mean"],
                        "canon_gnll_smt_sum": agg["pre_gnll_smt_sum"],
                        "canon_gnll_smt_val_mean": agg["pre_gnll_smt_val_mean"],
                        "canon_nll_all_mean": agg["pre_nll_all_mean"],
                        "canon_nll_all_sum": agg["pre_nll_all_sum"],
                        "canon_nll_syntax_mean": agg["pre_nll_syntax_mean"],
                        "canon_h_pre_first": agg["h_pre_first"],
                        "canon_h_pre_mean": agg["h_pre_mean"],
                    },
                }
                prompt_cache[c_str] = res
                n_unique_passes += 1
                unique_tf_times_ms.append(tf_ms)
                unique_tf_tokens.append(len(c_ids))
                return res, False

            sc_c, hit_c = score_canonical(canon_c_str)
            sc_w, hit_w = score_canonical(canon_w_str)

            row = {
                "idx": i,
                "id": iid,
                "category": rec["category"],
                "tool_family_cluster": rec["tool_family_cluster"],
                "prompt_len_tokens_neutral": int(prompt_neu_ids.shape[1]),
                "canonical_strings_equal": equal_canon,
                "frozen_ast_correct": {
                    "C_compact_menu": bool(arm_c["eval"]["ast_correct"]),
                    "W_optws_menu": bool(arm_w["eval"]["ast_correct"]),
                },
                "raw_stage0b_scores": {
                    "C_compact_menu": {
                        "raw_post_gnll_smt_mean": arm_c["scores"]["post_gnll_smt_mean"],
                        "raw_pre_gnll_smt_mean": arm_c["scores"]["pre_gnll_smt_mean"],
                        "raw_post_gnll_smt_sum": arm_c["scores"]["post_gnll_smt_sum"],
                        "raw_pre_gnll_smt_sum": arm_c["scores"]["pre_gnll_smt_sum"],
                        "raw_post_nll_all_mean": arm_c["scores"]["post_nll_all_mean"],
                        "raw_pre_nll_all_mean": arm_c["scores"]["pre_nll_all_mean"],
                        "stage0b_n_content_tokens": arm_c["n_content_tokens"],
                        "stage0b_prefill_ms": arm_c["prefill_ms"],
                    },
                    "W_optws_menu": {
                        "raw_post_gnll_smt_mean": arm_w["scores"]["post_gnll_smt_mean"],
                        "raw_pre_gnll_smt_mean": arm_w["scores"]["pre_gnll_smt_mean"],
                        "raw_post_gnll_smt_sum": arm_w["scores"]["post_gnll_smt_sum"],
                        "raw_pre_gnll_smt_sum": arm_w["scores"]["pre_gnll_smt_sum"],
                        "raw_post_nll_all_mean": arm_w["scores"]["post_nll_all_mean"],
                        "raw_pre_nll_all_mean": arm_w["scores"]["pre_nll_all_mean"],
                        "stage0b_n_content_tokens": arm_w["n_content_tokens"],
                        "stage0b_prefill_ms": arm_w["prefill_ms"],
                    },
                },
                "canonical_replay": {
                    "C_compact_menu": {"deduplicated_hit": hit_c, **sc_c},
                    "W_optws_menu": {"deduplicated_hit": hit_w, **sc_w},
                },
            }
            per_instance_records.append(row)
            fout.write(json.dumps(row) + "\n")
            fout.flush()

    total_scoring_wall_s = time.perf_counter() - t_score0
    print(
        f"  Scored all 24 pairs in {total_scoring_wall_s:.2f}s | "
        f"unique_tf_passes={n_unique_passes}, deduplicated_hits={n_dedup_hits}, "
        f"mean_tf_ms={np.mean(unique_tf_times_ms):.2f}ms",
        flush=True,
    )

    # 3) LOCKED SCORE & THRESHOLD TRANSFER ANALYSIS
    clusters = [r["tool_family_cluster"] for r in per_instance_records]
    err_c = np.array([0.0 if r["frozen_ast_correct"]["C_compact_menu"] else 1.0 for r in per_instance_records], dtype=np.float64)
    err_w = np.array([0.0 if r["frozen_ast_correct"]["W_optws_menu"] else 1.0 for r in per_instance_records], dtype=np.float64)
    eq_mask = np.array([r["canonical_strings_equal"] for r in per_instance_records], dtype=bool)

    def extract_pair_vecs(source_block: str, score_key: str) -> Tuple[np.ndarray, np.ndarray]:
        if source_block == "raw":
            uc = np.array([r["raw_stage0b_scores"]["C_compact_menu"][score_key] for r in per_instance_records], dtype=np.float64)
            uw = np.array([r["raw_stage0b_scores"]["W_optws_menu"][score_key] for r in per_instance_records], dtype=np.float64)
        else:
            uc = np.array([r["canonical_replay"]["C_compact_menu"]["scores"][score_key] for r in per_instance_records], dtype=np.float64)
            uw = np.array([r["canonical_replay"]["W_optws_menu"]["scores"][score_key] for r in per_instance_records], dtype=np.float64)
        return uc, uw

    # Primary prespecified Ye26 SMT-mean family
    primary_specs = [
        ("raw_post_gnll_smt_mean", "raw", "raw_post_gnll_smt_mean"),
        ("raw_pre_gnll_smt_mean", "raw", "raw_pre_gnll_smt_mean"),
        ("canon_gnll_smt_mean", "canon", "canon_gnll_smt_mean"),
    ]
    # Secondary sensitivity families (clearly labeled secondary)
    secondary_specs = [
        ("raw_post_gnll_smt_sum", "raw", "raw_post_gnll_smt_sum"),
        ("raw_pre_gnll_smt_sum", "raw", "raw_pre_gnll_smt_sum"),
        ("canon_gnll_smt_sum", "canon", "canon_gnll_smt_sum"),
        ("raw_post_nll_all_mean", "raw", "raw_post_nll_all_mean"),
        ("raw_pre_nll_all_mean", "raw", "raw_pre_nll_all_mean"),
        ("canon_nll_all_mean", "canon", "canon_nll_all_mean"),
    ]

    primary_results = {}
    vecs_cache = {}
    for nm, blk, sk in primary_specs:
        uc, uw = extract_pair_vecs(blk, sk)
        vecs_cache[nm] = (uc, uw)
        primary_results[nm] = eval_scorer_full_suite(nm, uc, uw, err_c, err_w, clusters, eq_mask)

    secondary_results = {}
    for nm, blk, sk in secondary_specs:
        uc, uw = extract_pair_vecs(blk, sk)
        secondary_results[nm] = eval_scorer_full_suite(nm, uc, uw, err_c, err_w, clusters, eq_mask)

    # Cluster bootstrap comparing canonical SMT-mean vs strongest raw post baseline (`raw_post_gnll_smt_mean`)
    boot_lofo_canon_vs_rawpost = cluster_bootstrap_lofo_comparison(
        clusters,
        vecs_cache["canon_gnll_smt_mean"][0],
        vecs_cache["canon_gnll_smt_mean"][1],
        vecs_cache["raw_post_gnll_smt_mean"][0],
        vecs_cache["raw_post_gnll_smt_mean"][1],
        err_c,
        err_w,
        n_boot=2000,
        seed=20261124,
    )

    # Evaluate locked prespecified decision gate on BOTH LOFO (primary) and full-sample (companion)
    base_lofo = primary_results["raw_post_gnll_smt_mean"]["lofo_primary"]
    cand_lofo = primary_results["canon_gnll_smt_mean"]["lofo_primary"]
    lofo_worst_gain = base_lofo["worst_direction_abs_cov_err"] - cand_lofo["worst_direction_abs_cov_err"]
    lofo_mean_gain = base_lofo["mean_abs_cov_err"] - cand_lofo["mean_abs_cov_err"]
    lofo_passes_gate = bool(
        (lofo_worst_gain >= GATE_MIN_WORST_DIR_GAIN - 1e-12)
        and (cand_lofo["mean_abs_cov_err"] <= base_lofo["mean_abs_cov_err"] + 1e-12)
    )

    base_fs = primary_results["raw_post_gnll_smt_mean"]["fullsample_companion"]
    cand_fs = primary_results["canon_gnll_smt_mean"]["fullsample_companion"]
    fs_worst_gain = base_fs["worst_direction_abs_cov_err"] - cand_fs["worst_direction_abs_cov_err"]
    fs_mean_gain = base_fs["mean_abs_cov_err"] - cand_fs["mean_abs_cov_err"]
    fs_passes_gate = bool(
        (fs_worst_gain >= GATE_MIN_WORST_DIR_GAIN - 1e-12)
        and (cand_fs["mean_abs_cov_err"] <= base_fs["mean_abs_cov_err"] + 1e-12)
    )

    # Detailed table of the 3 distinct-canonical pairs
    distinct_pair_inspection = []
    for r in per_instance_records:
        if not r["canonical_strings_equal"]:
            distinct_pair_inspection.append({
                "id": r["id"],
                "category": r["category"],
                "tool_family_cluster": r["tool_family_cluster"],
                "frozen_ast_correct": r["frozen_ast_correct"],
                "canonical_C": r["canonical_replay"]["C_compact_menu"]["canonical_text"],
                "canonical_W": r["canonical_replay"]["W_optws_menu"]["canonical_text"],
                "raw_post_gnll_smt_mean_C": r["raw_stage0b_scores"]["C_compact_menu"]["raw_post_gnll_smt_mean"],
                "raw_post_gnll_smt_mean_W": r["raw_stage0b_scores"]["W_optws_menu"]["raw_post_gnll_smt_mean"],
                "raw_pre_gnll_smt_mean_C": r["raw_stage0b_scores"]["C_compact_menu"]["raw_pre_gnll_smt_mean"],
                "raw_pre_gnll_smt_mean_W": r["raw_stage0b_scores"]["W_optws_menu"]["raw_pre_gnll_smt_mean"],
                "canon_gnll_smt_mean_C": r["canonical_replay"]["C_compact_menu"]["scores"]["canon_gnll_smt_mean"],
                "canon_gnll_smt_mean_W": r["canonical_replay"]["W_optws_menu"]["scores"]["canon_gnll_smt_mean"],
            })

    # Operational cost accounting
    mean_stage0b_prefill_ms = float(np.mean([
        0.5 * (r["raw_stage0b_scores"]["C_compact_menu"]["stage0b_prefill_ms"] + r["raw_stage0b_scores"]["W_optws_menu"]["stage0b_prefill_ms"])
        for r in per_instance_records
    ]))
    cost_accounting = {
        "n_pairs_evaluated": 24,
        "n_undeduplicated_calls": 48,
        "n_unique_teacher_forced_passes": n_unique_passes,
        "n_within_prompt_deduplicated_hits": n_dedup_hits,
        "benchmark_pass_reduction_pct": float(100.0 * n_dedup_hits / 48.0),
        "total_scoring_wall_s": total_scoring_wall_s,
        "tf_forward_ms_mean": float(np.mean(unique_tf_times_ms)),
        "tf_forward_ms_median": float(np.median(unique_tf_times_ms)),
        "tf_forward_ms_max": float(np.max(unique_tf_times_ms)),
        "tf_target_tokens_mean": float(np.mean(unique_tf_tokens)),
        "stage0b_mean_prefill_ms_reference": mean_stage0b_prefill_ms,
        "single_arm_deployment_overhead_note": (
            "In real single-arm deployment (one generated call per user request), canonical replay requires "
            "1 extra unmasked teacher-forced forward pass (~1x prefill+call forward pass, ~"
            f"{float(np.mean(unique_tf_times_ms)):.1f} ms on RTX 5060 for 1.5B) whenever the emitted surface "
            "serialization differs from canonical JSON (or unconditionally to guarantee grammar-invariant scoring). "
            "Within-prompt deduplication (21/24 pairs saved) applies to paired offline evaluation or multi-sample deduplication, "
            "NOT to single-sample production calls."
        ),
    }

    # 4) POST-RUN INTEGRITY CHECK ON ALL SEALED FILES & BLIND TEST
    post_hashes = verify_sealed_hashes("POST-RUN")
    assert pre_hashes == post_hashes

    summary = {
        "protocol": "STAGE0C_CANONICAL_REPLAY_PROTOCOL.md",
        "protocol_sha256": proto_sha,
        "fixture_receipt": "STAGE0C_CANONICAL_FIXTURE_RECEIPT.json",
        "fixture_receipt_sha256": fix_sha,
        "real_pid": pid,
        "wall_time_s": time.perf_counter() - t0,
        "model_metadata": {
            "model_id": MODEL_ID,
            "license": MODEL_LICENSE,
            "verified_commit_hash": transport_rec["pinned_commit"],
            "verified_safetensors_sha256": transport_rec["expected_sha256_x_linked_etag"],
            "dtype": str(dtype),
            "device": gpu_name,
            "offline_local_files_only": True,
        },
        "backend_versions_and_licenses": {
            "transformers": {"version": importlib.metadata.version("transformers"), "license": "Apache-2.0"},
            "torch": {"version": torch.__version__, "license": "BSD-3-Clause"},
            "tokenizers": {"version": importlib.metadata.version("tokenizers"), "license": "Apache-2.0"},
        },
        "integrity_verification": {
            "all_sealed_stage0_stage0b_and_blind_test_hashes_verified_before_and_after": True,
            "sealed_hashes": post_hashes,
            "verify_stage0c_canonical_fixture_py_sha256": sha256_file(BASE / "verify_stage0c_canonical_fixture.py"),
            "stage0c_canonical_replay_pilot_py_sha256": sha256_file(pathlib.Path(__file__)),
            "stage0c_per_instance_jsonl_sha256": sha256_file(inc_path),
        },
        "frozen_outcomes_summary": {
            "n_total": 24,
            "n_tool_family_clusters": len(set(clusters)),
            "C_compact_menu_ast_correct": int(np.sum(err_c == 0.0)),
            "C_compact_menu_ast_error": int(np.sum(err_c == 1.0)),
            "W_optws_menu_ast_correct": int(np.sum(err_w == 0.0)),
            "W_optws_menu_ast_error": int(np.sum(err_w == 1.0)),
            "n_equal_canonical_pairs": int(np.sum(eq_mask)),
            "n_distinct_canonical_pairs": int(np.sum(~eq_mask)),
            "epistemic_note": (
                "Identical-serialization score equality on the 21/24 equal-canonical pairs is by construction "
                "and is NOT empirical novelty."
            ),
        },
        "cost_accounting": cost_accounting,
        "primary_ye26_smt_mean_comparison": primary_results,
        "secondary_sensitivity_comparisons": secondary_results,
        "cluster_bootstrap_lofo_canon_vs_raw_post": boot_lofo_canon_vs_rawpost,
        "distinct_canonical_pairs_detail": distinct_pair_inspection,
        "prespecified_decision_gate": {
            "criterion": (
                "Canon Ye26 SMT-mean beats strongest raw post-mask baseline (`raw_post_gnll_smt_mean`) on "
                "free-generation coverage transfer by >= 8 pp smaller worst-direction |cov - 0.80| "
                "WITHOUT worse mean |cov - 0.80| and WITHOUT a new operational harm."
            ),
            "lofo_primary": {
                "raw_post_worst_dir_abs_err": base_lofo["worst_direction_abs_cov_err"],
                "canon_worst_dir_abs_err": cand_lofo["worst_direction_abs_cov_err"],
                "worst_dir_err_reduction_pp": 100.0 * lofo_worst_gain,
                "raw_post_mean_abs_err": base_lofo["mean_abs_cov_err"],
                "canon_mean_abs_err": cand_lofo["mean_abs_cov_err"],
                "mean_err_reduction_pp": 100.0 * lofo_mean_gain,
                "passes_numeric_gate_lofo": lofo_passes_gate,
            },
            "fullsample_companion": {
                "raw_post_worst_dir_abs_err": base_fs["worst_direction_abs_cov_err"],
                "canon_worst_dir_abs_err": cand_fs["worst_direction_abs_cov_err"],
                "worst_dir_err_reduction_pp": 100.0 * fs_worst_gain,
                "raw_post_mean_abs_err": base_fs["mean_abs_cov_err"],
                "canon_mean_abs_err": cand_fs["mean_abs_cov_err"],
                "mean_err_reduction_pp": 100.0 * fs_mean_gain,
                "passes_numeric_gate_fullsample": fs_passes_gate,
            },
            "recommended_action_from_lofo_primary": (
                "ELIGIBLE_TO_DESIGN_INDEPENDENT_TEST" if lofo_passes_gate else "RECOMMEND_FREEZING"
            ),
        },
    }

    sum_path = out_dir / "stage0c_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n=== Stage-0c Canonical Replay Pilot COMPLETE (PID={pid}, wall={summary['wall_time_s']:.2f}s) ===", flush=True)
    print(f"Saved {sum_path} (sha256={sha256_file(sum_path)[:16]}...)", flush=True)
    print(
        f"LOFO PRIMARY GATE: raw_post worst={base_lofo['worst_direction_abs_cov_err']*100:.2f}pp (mean={base_lofo['mean_abs_cov_err']*100:.2f}pp) "
        f"vs canon worst={cand_lofo['worst_direction_abs_cov_err']*100:.2f}pp (mean={cand_lofo['mean_abs_cov_err']*100:.2f}pp) "
        f"| gain={lofo_worst_gain*100:+.2f}pp -> {summary['prespecified_decision_gate']['recommended_action_from_lofo_primary']}",
        flush=True,
    )
    print(
        f"FULL-SAMPLE COMPANION: raw_post worst={base_fs['worst_direction_abs_cov_err']*100:.2f}pp (mean={base_fs['mean_abs_cov_err']*100:.2f}pp) "
        f"vs canon worst={cand_fs['worst_direction_abs_cov_err']*100:.2f}pp (mean={cand_fs['mean_abs_cov_err']*100:.2f}pp) "
        f"| gain={fs_worst_gain*100:+.2f}pp -> passes={fs_passes_gate}",
        flush=True,
    )


if __name__ == "__main__":
    main()
