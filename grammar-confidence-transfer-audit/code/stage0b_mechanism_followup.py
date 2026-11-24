"""
Stage-0b Bounded Exploratory Mechanism Follow-Up: Isolating the Stage-0 95->2 G_compact Effect.

Locked Amendment Protocol: STAGE0B_AMENDMENT_PROTOCOL.md
Selected Subset (24 = 12 simple_python + 12 multiple, outcome-independent SHA-256 order):
  STAGE0B_SUBSET_24_RECEIPT.json
Pre-Launch Fixture Verification Receipt:
  STAGE0B_FIXTURE_RECEIPT.json

Experimental Design (strictly bounded; NO fit/retune, NO held-out data, NO extra arms):
  - Reuses sealed Stage-0 `Prompt_Spaced` outputs (`unconstrained`, `G_optws`, `G_compact`,
    and `fixed_path_shared_forward`) BYTE-FOR-BYTE for the 24 selected IDs.
  - Runs 6 prespecified new arms across the exact 24 items (144 greedy generations total):
      (A1) Prompt_Neutral (key names in prose, NO JSON formatting example) x {G_optws, G_compact}
      (A2) Prompt_Compact (compact JSON example) x {G_optws, G_compact}
      (B)  Prompt_Neutral x per-item offered-menu enum {G_optws_menu, G_compact_menu}
           (canonical sorted union of item["function"] names only; zero gold leakage;
            differs between compact and optws ONLY by optional whitespace)
  - Preserves ALL raw outputs, AST verdicts, 3-way error taxonomy
    (unknown_func_not_in_menu vs offered_but_wrong_func vs right_func_wrong_args + parse_or_envelope_fail),
    overall (24) and split (12 simple_python vs 12 multiple) breakdowns,
    matched vs confounded prompt cells, prefix-logit timing & top-5 inspection of steps 0..7
    (including first tool-name token boundary), and strictly separated fixed-path shared-forward scores.
  - Flags conditional confidence metrics (AUROC/AURC/risk@80%) as UNSTABLE whenever minority class <= 5.
  - Verifies sealed Stage-0 logs and 416-item blind test file remain 100% byte-identical before & after.
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
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import xgrammar as xgr
from scipy import stats
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(BASE))

import grammar_utils as gu  # noqa: E402
import select_stage0b_subset_and_verify as s0b  # noqa: E402
import stage0_grammar_confidence_pilot as s0  # noqa: E402

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
MODEL_LICENSE = "Apache-2.0"
MAX_NEW_TOKENS = 192
TARGET_COVERAGE = 0.80
PREFIX_INSPECT_STEPS = 8
MINORITY_UNSTABLE_THRESH = 5

# Expected sealed SHA-256 hashes (asserted BEFORE and AFTER execution)
SEALED_HASHES = {
    "bfcl_stage0_pilot_dataset.json": "191e8e8c8c9c00f0f7dacd0a98b6f592b02e878e444da0016e99f1e31c1cd446",
    "bfcl_future_blind_test_ids_sealed.json": "64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a",
    "grammar_utils.py": "d063e5e347bf2928f1c6f22becafd67611f711842960276e1399359dab966423",
    "STAGE0_PROTOCOL.md": "9c4573d847d18a683c22440390d6e9b11d44691d45321e6ede5217894ec065b6",
    "MODEL_TRANSPORT_RECEIPT.json": "74cdd02fae04f8328eef6a323f3e80e2f02d52a2b0f8d200c2674b629071c8ad",
    "stage0_pilot_outputs/stage0_pilot_per_instance.jsonl": "06c90359910592d3d43916c50479abadc15a5cac2d9600ada8b2b0e2566b6aa8",
    "stage0_pilot_outputs/stage0_pilot_summary.json": "a39963f0cf7d00a1ef4c2c0864708883a7f01072e364580c6e7fd3d4e7b8af6c",
    "select_stage0b_subset_and_verify.py": "0a0d9b95cedc580b8fdff00ac44277b6e0409c411dcc0dc4138a1fed168defa1",
    "STAGE0B_SUBSET_24_RECEIPT.json": "65bcba4a28ee39bf3ff7f4173e773c110c076a136f663cda7dcde57f928cbf46",
    "STAGE0B_FIXTURE_RECEIPT.json": "04ee945695311cc738406e5a769556b14ed0bbc7e8212b85ac86cdc36d456d65",
}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def verify_sealed_hashes(stage_label: str) -> Dict[str, str]:
    observed = {}
    for rel, expected in SEALED_HASHES.items():
        p = BASE / rel
        assert p.exists(), f"[{stage_label}] Missing sealed file: {rel}"
        got = sha256_file(p)
        assert got == expected, f"[{stage_label}] SHA-256 MISMATCH on {rel}: expected {expected}, got {got}"
        observed[rel] = got
    return observed


def classify_call_outcome(item: Dict, ev: Dict) -> Dict:
    """
    Mutually exclusive outcome classification preserving EVERY failure:
      - ast_correct
      - unknown_func_not_in_menu
      - offered_but_wrong_func
      - right_func_wrong_args
      - parse_or_envelope_fail
    """
    offered_menu = sorted({f["name"] for f in item["function"]})
    offered_set = set(offered_menu)
    gold_names = sorted({next(iter(g.keys())) for g in item["ground_truth"]})
    gold_set = set(gold_names)

    if not ev.get("json_valid") or not ev.get("call_schema_valid") or ev.get("parsed_call") is None:
        return {
            "predicted_func_name": None,
            "in_provided_menu": False,
            "gold_func_name_match": False,
            "outcome_class": "parse_or_envelope_fail",
            "n_offered_functions": len(offered_menu),
        }

    pred_name = ev["parsed_call"]["name"]
    in_menu = pred_name in offered_set
    gold_match = pred_name in gold_set

    if ev.get("ast_correct"):
        outcome_class = "ast_correct"
    elif not in_menu:
        outcome_class = "unknown_func_not_in_menu"
    elif not gold_match:
        outcome_class = "offered_but_wrong_func"
    else:
        outcome_class = "right_func_wrong_args"

    return {
        "predicted_func_name": pred_name,
        "in_provided_menu": bool(in_menu),
        "gold_func_name_match": bool(gold_match),
        "outcome_class": outcome_class,
        "n_offered_functions": len(offered_menu),
    }


def _topk_prefix_info(
    logits_1d: torch.Tensor,
    allowed_bool: Optional[torch.Tensor],
    tokenizer,
    k: int = 5,
) -> Tuple[List[Dict], List[Dict]]:
    z = logits_1d.detach().to(dtype=torch.float64, device="cpu")
    p_pre = torch.softmax(z, dim=-1)
    top_pre_vals, top_pre_idx = torch.topk(p_pre, k=k)
    top5_unmasked = []
    for val, idx in zip(top_pre_vals.tolist(), top_pre_idx.tolist()):
        is_all = True if allowed_bool is None else bool(allowed_bool[idx].item())
        top5_unmasked.append({
            "id": int(idx),
            "text": tokenizer.decode([int(idx)], skip_special_tokens=False),
            "prob_pre": float(val),
            "allowed_by_grammar": is_all,
        })

    if allowed_bool is not None:
        mask = allowed_bool.to(dtype=torch.bool, device="cpu")
        n_all = int(mask.sum().item())
        kk = min(k, n_all)
        z_masked = z.masked_fill(~mask, float("-inf"))
        p_post = torch.softmax(z_masked, dim=-1)
        top_post_vals, top_post_idx = torch.topk(p_post, k=kk)
        top5_masked = []
        for val, idx in zip(top_post_vals.tolist(), top_post_idx.tolist()):
            top5_masked.append({
                "id": int(idx),
                "text": tokenizer.decode([int(idx)], skip_special_tokens=False),
                "prob_post": float(val),
                "prob_pre": float(p_pre[int(idx)].item()),
            })
    else:
        top5_masked = [
            {
                "id": x["id"],
                "text": x["text"],
                "prob_post": x["prob_pre"],
                "prob_pre": x["prob_pre"],
            }
            for x in top5_unmasked
        ]
    return top5_unmasked, top5_masked


def decode_greedy_with_prefix_inspect(
    model,
    tokenizer,
    input_ids: torch.Tensor,
    compiled_grammar: Optional[xgr.CompiledGrammar],
    vocab_size: int,
    eos_token_ids: List[int],
    max_new_tokens: int = MAX_NEW_TOKENS,
    prefix_inspect_steps: int = PREFIX_INSPECT_STEPS,
) -> Dict:
    """
    Exact KV-cached greedy decoding (identical arithmetic to Stage-0) plus
    step-level timing (forward_ms, mask_ms) and top-5 unmasked/masked probability inspection
    over steps `0 .. prefix_inspect_steps - 1`.
    """
    device = next(model.parameters()).device
    is_cuda = device.type == "cuda"
    matcher = xgr.GrammarMatcher(compiled_grammar) if compiled_grammar is not None else None
    bitmask = xgr.allocate_token_bitmask(1, vocab_size) if compiled_grammar is not None else None

    generated_ids: List[int] = []
    per_step: List[Dict[str, float]] = []
    prefix_trace: List[Dict] = []
    stopped_reason = "max_new_tokens"

    with torch.no_grad():
        if is_cuda:
            torch.cuda.synchronize()
        t_prefill0 = time.perf_counter()
        out = model(input_ids=input_ids.to(device), use_cache=True)
        if is_cuda:
            torch.cuda.synchronize()
        prefill_ms = (time.perf_counter() - t_prefill0) * 1000.0
        past_key_values = out.past_key_values
        next_logits = out.logits[0, -1, :]

        for step in range(max_new_tokens):
            inspect_this = step < prefix_inspect_steps
            t_mask0 = time.perf_counter()
            if matcher is not None:
                matcher.fill_next_token_bitmask(bitmask)
                allowed_bool = gu.bitmask_to_bool(bitmask[0], vocab_size)
                masked_logits = next_logits.detach().to(dtype=torch.float64, device="cpu").masked_fill(~allowed_bool, float("-inf"))
                tok_id = int(torch.argmax(masked_logits).item())
            else:
                allowed_bool = None
                tok_id = int(torch.argmax(next_logits.detach().to(dtype=torch.float64, device="cpu")).item())
            mask_ms = (time.perf_counter() - t_mask0) * 1000.0

            sm = gu.step_mask_metrics_from_logits(next_logits, allowed_bool, tok_id)
            per_step.append(sm)
            generated_ids.append(tok_id)

            if inspect_this:
                top5_u, top5_m = _topk_prefix_info(next_logits, allowed_bool, tokenizer, k=5)
                cum_text = tokenizer.decode([t for t in generated_ids if t not in eos_token_ids], skip_special_tokens=False)
                prefix_trace.append({
                    "step": step,
                    "forward_ms": prefill_ms if step == 0 else step_fwd_ms,  # noqa: F821
                    "mask_ms": mask_ms,
                    "chosen_token_id": tok_id,
                    "chosen_token_text": tokenizer.decode([tok_id], skip_special_tokens=False),
                    "cumulative_text": cum_text,
                    "n_allowed_tokens": sm["n_allowed_tokens"],
                    "retained_mass": sm["retained_mass"],
                    "log_retained_mass": sm["log_retained_mass"],
                    "pre_nll": sm["pre_nll"],
                    "post_nll": sm["post_nll"],
                    "h_pre": sm["h_pre"],
                    "h_post": sm["h_post"],
                    "top5_unmasked": top5_u,
                    "top5_masked": top5_m,
                })

            if matcher is not None:
                ok = matcher.accept_token(tok_id)
                assert ok, f"xgrammar matcher rejected allowed token {tok_id} at step {step}"
                if matcher.is_terminated():
                    stopped_reason = "grammar_terminated"
                    break

            if tok_id in eos_token_ids:
                stopped_reason = "eos"
                break

            next_inp = torch.tensor([[tok_id]], dtype=torch.long, device=device)
            if inspect_this and is_cuda:
                torch.cuda.synchronize()
            t_f0 = time.perf_counter()
            out = model(input_ids=next_inp, past_key_values=past_key_values, use_cache=True)
            if inspect_this and is_cuda:
                torch.cuda.synchronize()
            step_fwd_ms = (time.perf_counter() - t_f0) * 1000.0
            past_key_values = out.past_key_values
            next_logits = out.logits[0, -1, :]

    content_ids = [t for t in generated_ids if t not in eos_token_ids]
    text = tokenizer.decode(content_ids, skip_special_tokens=False)
    return {
        "generated_ids": generated_ids,
        "content_ids": content_ids,
        "text": text,
        "stopped_reason": stopped_reason,
        "n_tokens": len(generated_ids),
        "n_content_tokens": len(content_ids),
        "per_step": per_step,
        "prefill_ms": prefill_ms,
        "prefix_trace": prefix_trace,
    }


def locate_first_tool_name_step(tokenizer, content_ids: List[int], smt_info: Dict) -> Optional[int]:
    """Returns exact token step index where the first character of the parsed tool name begins."""
    if not smt_info.get("parsed_ok") or not smt_info.get("func_name_spans"):
        return None
    fn_start, fn_end = smt_info["func_name_spans"][0]
    prev = ""
    for k in range(len(content_ids)):
        cur = tokenizer.decode(content_ids[: k + 1], skip_special_tokens=False)
        sp = (len(prev), len(cur))
        prev = cur
        if max(sp[0], fn_start) < min(sp[1], fn_end):
            return k
    return None


def annotate_stability(metric_dict: Dict) -> Dict:
    """Explicitly marks conditional confidence metrics as unstable when minority class <= 5."""
    n_cor = int(metric_dict["n_correct"])
    n_err = int(metric_dict["n_error"])
    minority = min(n_cor, n_err)
    unstable = bool(minority <= MINORITY_UNSTABLE_THRESH)
    out = dict(metric_dict)
    out["minority_class_count"] = minority
    out["conditional_metrics_unstable"] = unstable
    if unstable:
        out["stability_note"] = (
            f"UNSTABLE (minority_class_count={minority} <= {MINORITY_UNSTABLE_THRESH}): "
            "do NOT over-interpret conditional ranking/AUROC/risk@80%."
        )
    else:
        out["stability_note"] = f"exploratory_n24 (minority_class_count={minority}); still small exploratory pilot."
    return out


def summarize_arm_records(records: List[Dict], arm_key: str, category_filter: Optional[str] = None) -> Dict:
    sub = [r for r in records if (category_filter is None or r["category"] == category_filter)]
    n = len(sub)
    evs = [r["arms"][arm_key]["eval"] for r in sub]
    clss = [r["arms"][arm_key]["classification"] for r in sub]
    scs = [r["arms"][arm_key]["scores"] for r in sub]

    counts_cls = {
        "ast_correct": 0,
        "unknown_func_not_in_menu": 0,
        "offered_but_wrong_func": 0,
        "right_func_wrong_args": 0,
        "parse_or_envelope_fail": 0,
    }
    for c in clss:
        counts_cls[c["outcome_class"]] += 1
    assert sum(counts_cls.values()) == n, f"Taxonomy count mismatch on {arm_key}"

    stopped_counts: Dict[str, int] = {}
    for r in sub:
        st = r["arms"][arm_key]["stopped_reason"]
        stopped_counts[st] = stopped_counts.get(st, 0) + 1

    errs = np.array([0.0 if e["ast_correct"] else 1.0 for e in evs], dtype=np.float64)

    score_keys = [
        "pre_nll_all_mean",
        "post_nll_all_mean",
        "pre_gnll_smt_mean",
        "post_gnll_smt_mean",
        "neg_logz_all_mean",
        "min_retained_mass",
        "mean_retained_mass",
        "h_pre_first",
        "h_post_first",
    ]
    score_metrics = {}
    for sk in score_keys:
        vals = np.array([s.get(sk, float("nan")) for s in scs], dtype=np.float64)
        n_nan = int(np.sum(~np.isfinite(vals)))
        fmax = float(np.nanmax(vals)) if np.any(np.isfinite(vals)) else 1e6
        vals_filled = np.where(np.isfinite(vals), vals, fmax + 100.0)
        m = annotate_stability(s0.compute_aurc_and_risk_at_cov(vals_filled, errs, TARGET_COVERAGE))
        m["n_nan_filled_max_unc"] = n_nan
        m["mean_finite"] = float(np.nanmean(vals)) if np.any(np.isfinite(vals)) else float("nan")
        m["std_finite"] = float(np.nanstd(vals)) if np.any(np.isfinite(vals)) else float("nan")
        score_metrics[sk] = m

    return {
        "n_total": n,
        "json_valid_count": sum(1 for e in evs if e["json_valid"]),
        "call_schema_valid_count": sum(1 for e in evs if e["call_schema_valid"]),
        "in_provided_menu_count": sum(1 for c in clss if c["in_provided_menu"]),
        "gold_func_name_match_count": sum(1 for c in clss if c["gold_func_name_match"]),
        "ast_correct_count": counts_cls["ast_correct"],
        "error_taxonomy": {
            "unknown_func_not_in_menu": counts_cls["unknown_func_not_in_menu"],
            "offered_but_wrong_func": counts_cls["offered_but_wrong_func"],
            "right_func_wrong_args": counts_cls["right_func_wrong_args"],
            "parse_or_envelope_fail": counts_cls["parse_or_envelope_fail"],
        },
        "stopped_reason_counts": stopped_counts,
        "conditional_score_metrics": score_metrics,
    }


def summarize_pair_free_gen(records: List[Dict], arm_c: str, arm_w: str) -> Dict:
    """Pair comparison on free-generated outputs (strictly separate from fixed-path scoring)."""
    err_c = np.array([0.0 if r["arms"][arm_c]["eval"]["ast_correct"] else 1.0 for r in records], dtype=np.float64)
    err_w = np.array([0.0 if r["arms"][arm_w]["eval"]["ast_correct"] else 1.0 for r in records], dtype=np.float64)
    flips_w_ok_c_err = sum(
        1 for r in records
        if r["arms"][arm_w]["eval"]["ast_correct"] and not r["arms"][arm_c]["eval"]["ast_correct"]
    )
    flips_c_ok_w_err = sum(
        1 for r in records
        if r["arms"][arm_c]["eval"]["ast_correct"] and not r["arms"][arm_w]["eval"]["ast_correct"]
    )
    parsed_eq = sum(
        1 for r in records
        if r["arms"][arm_c]["eval"]["parsed_call"] is not None
        and r["arms"][arm_c]["eval"]["parsed_call"] == r["arms"][arm_w]["eval"]["parsed_call"]
    )

    def vec(ak, sk):
        vals = np.array([r["arms"][ak]["scores"].get(sk, float("nan")) for r in records], dtype=np.float64)
        fmax = float(np.nanmax(vals)) if np.any(np.isfinite(vals)) else 1e6
        return np.where(np.isfinite(vals), vals, fmax + 100.0)

    transfer = {}
    for sk in ["post_nll_all_mean", "post_gnll_smt_mean", "pre_nll_all_mean", "pre_gnll_smt_mean", "neg_logz_all_mean"]:
        uc = vec(arm_c, sk)
        uw = vec(arm_w, sk)
        transfer[sk] = {
            "mean_compact": float(np.mean(uc)),
            "mean_optws": float(np.mean(uw)),
            "mean_diff_C_minus_W": float(np.mean(uc - uw)),
            "spearman_rho_C_vs_W": float(stats.spearmanr(uc, uw).statistic) if np.std(uc) > 0 and np.std(uw) > 0 else float("nan"),
            "transfer_compact_to_optws": s0.eval_threshold_transfer(uc, err_c, uw, err_w, TARGET_COVERAGE),
            "transfer_optws_to_compact": s0.eval_threshold_transfer(uw, err_w, uc, err_c, TARGET_COVERAGE),
            "minority_C": int(min(np.sum(err_c == 0.0), np.sum(err_c == 1.0))),
            "minority_W": int(min(np.sum(err_w == 0.0), np.sum(err_w == 1.0))),
            "conditional_metrics_unstable": bool(
                min(int(np.sum(err_c == 0.0)), int(np.sum(err_c == 1.0))) <= MINORITY_UNSTABLE_THRESH
                or min(int(np.sum(err_w == 0.0)), int(np.sum(err_w == 1.0))) <= MINORITY_UNSTABLE_THRESH
            ),
        }

    return {
        "n_total": len(records),
        "parsed_call_equal_count": parsed_eq,
        "ast_flip_optws_correct_compact_wrong": flips_w_ok_c_err,
        "ast_flip_compact_correct_optws_wrong": flips_c_ok_w_err,
        "cross_grammar_transfer_free_gen": transfer,
    }


def summarize_fixed_path_pair(records: List[Dict], fp_key: str) -> Dict:
    """Strictly separate fixed-path shared-forward-pass paired analysis."""
    fps = [r["fixed_path_pairs"][fp_key] for r in records if r["fixed_path_pairs"][fp_key].get("both_grammars_accept")]
    n_acc = len(fps)
    out: Dict = {
        "n_both_accepted": n_acc,
        "n_of_total": len(records),
        "scores": {},
    }
    if n_acc == 0:
        return out

    errs = np.array([0.0 if fp["ast_correct"] else 1.0 for fp in fps], dtype=np.float64)
    n_cor = int(np.sum(errs == 0.0))
    n_err = int(np.sum(errs == 1.0))
    minority = min(n_cor, n_err)
    out["n_correct"] = n_cor
    out["n_error"] = n_err
    out["minority_class_count"] = minority
    out["conditional_metrics_unstable"] = bool(minority <= MINORITY_UNSTABLE_THRESH)

    for sk in [
        "pre_nll_all_mean",
        "post_nll_all_mean",
        "pre_gnll_smt_mean",
        "post_gnll_smt_mean",
        "pre_nll_syntax_mean",
        "post_nll_syntax_mean",
        "neg_logz_all_mean",
        "neg_logz_smt_mean",
        "neg_logz_syntax_mean",
        "min_retained_mass",
        "mean_retained_mass",
    ]:
        uc = np.array([fp["G_compact"][sk] for fp in fps], dtype=np.float64)
        uw = np.array([fp["G_optws"][sk] for fp in fps], dtype=np.float64)
        mc = annotate_stability(s0.compute_aurc_and_risk_at_cov(uc, errs, TARGET_COVERAGE))
        mw = annotate_stability(s0.compute_aurc_and_risk_at_cov(uw, errs, TARGET_COVERAGE))
        out["scores"][sk] = {
            "G_compact": mc,
            "G_optws": mw,
            "mean_C": float(np.mean(uc)),
            "mean_W": float(np.mean(uw)),
            "mean_diff_C_minus_W": float(np.mean(uc - uw)),
            "spearman_rho_C_vs_W": float(stats.spearmanr(uc, uw).statistic) if np.std(uc) > 0 and np.std(uw) > 0 else float("nan"),
            "kendall_tau_C_vs_W": float(stats.kendalltau(uc, uw).statistic) if np.std(uc) > 0 and np.std(uw) > 0 else float("nan"),
            "transfer_compact_to_optws": s0.eval_threshold_transfer(uc, errs, uw, errs, TARGET_COVERAGE),
            "transfer_optws_to_compact": s0.eval_threshold_transfer(uw, errs, uc, errs, TARGET_COVERAGE),
        }
    return out


def run_fixed_path_pair(
    model,
    prompt_ids: torch.Tensor,
    dec_compact: Dict,
    smt_compact: Dict,
    ev_compact: Dict,
    cg_compact: xgr.CompiledGrammar,
    cg_optws: xgr.CompiledGrammar,
    vocab_size: int,
    eos_ids: List[int],
) -> Tuple[Dict, float]:
    """Single shared unmasked forward pass over `dec_compact["generated_ids"]` scored under both grammars."""
    if dec_compact["stopped_reason"] != "grammar_terminated" or dec_compact["n_content_tokens"] <= 0:
        return {"both_grammars_accept": False, "reason": dec_compact["stopped_reason"]}, 0.0

    shared_logits = s0.teacher_force_logits(model, prompt_ids, dec_compact["generated_ids"])
    fp_c = gu.score_fixed_path_under_grammar(shared_logits, dec_compact["generated_ids"], cg_compact, vocab_size, eos_ids)
    fp_w = gu.score_fixed_path_under_grammar(shared_logits, dec_compact["generated_ids"], cg_optws, vocab_size, eos_ids)
    both_ok = bool(
        fp_c["accepted_all_tokens"] and fp_c["grammar_terminated"]
        and fp_w["accepted_all_tokens"] and fp_w["grammar_terminated"]
    )
    if not both_ok:
        return {
            "both_grammars_accept": False,
            "compact_accepted": bool(fp_c["accepted_all_tokens"] and fp_c["grammar_terminated"]),
            "optws_accepted": bool(fp_w["accepted_all_tokens"] and fp_w["grammar_terminated"]),
        }, 0.0

    fsc_c = s0.aggregate_step_scores(fp_c["per_step"], smt_compact, dec_compact["n_content_tokens"])
    fsc_w = s0.aggregate_step_scores(fp_w["per_step"], smt_compact, dec_compact["n_content_tokens"])
    max_err = max(fsc_c["max_identity_abs_err"], fsc_w["max_identity_abs_err"])
    assert max_err < 1e-11, f"Float64 identity residual violated: {max_err}"
    return {
        "both_grammars_accept": True,
        "n_content_tokens": dec_compact["n_content_tokens"],
        "n_total_tokens_with_eos": len(dec_compact["generated_ids"]),
        "ast_correct": bool(ev_compact["ast_correct"]),
        "G_compact": fsc_c,
        "G_optws": fsc_w,
    }, max_err


def main():
    t0 = time.perf_counter()
    pid = os.getpid()

    # 1) HARD PRE-LAUNCH INTEGRITY & PROTOCOL GATES
    pre_hashes = verify_sealed_hashes("PRE-LAUNCH")
    proto_p = BASE / "STAGE0B_AMENDMENT_PROTOCOL.md"
    assert proto_p.exists(), "Missing locked STAGE0B_AMENDMENT_PROTOCOL.md before launch!"
    proto_sha = sha256_file(proto_p)

    subset_rec = json.loads((BASE / "STAGE0B_SUBSET_24_RECEIPT.json").read_text(encoding="utf-8-sig"))
    fixture_rec = json.loads((BASE / "STAGE0B_FIXTURE_RECEIPT.json").read_text(encoding="utf-8-sig"))
    transport_rec = json.loads((BASE / "MODEL_TRANSPORT_RECEIPT.json").read_text(encoding="utf-8-sig"))
    assert subset_rec["n_selected"] == 24 and subset_rec["n_simple_python"] == 12 and subset_rec["n_multiple"] == 12
    assert fixture_rec["all_fixtures_passed"] is True
    assert transport_rec["verified_exact_match"] is True

    selected_ids = [x["id"] for x in subset_rec["selected_items"]]
    selected_id_set = set(selected_ids)
    assert len(selected_ids) == 24 and len(selected_id_set) == 24

    # Load selected 24 items from sealed Stage-0 pilot dataset (NEVER touching 416 blind test!)
    pilot_items = json.loads((BASE / "bfcl_stage0_pilot_dataset.json").read_text(encoding="utf-8"))
    pilot_by_id = {it["id"]: it for it in pilot_items}
    selected_items = [pilot_by_id[iid] for iid in selected_ids]

    # Load sealed Stage-0 `Prompt_Spaced` outputs BYTE-FOR-BYTE for the 24 selected IDs
    stage0_by_id: Dict[str, Dict] = {}
    with (BASE / "stage0_pilot_outputs" / "stage0_pilot_per_instance.jsonl").open("r", encoding="utf-8") as fin:
        for line in fin:
            rec = json.loads(line)
            if rec["id"] in selected_id_set:
                stage0_by_id[rec["id"]] = rec
    assert len(stage0_by_id) == 24, f"Expected 24 reused Stage-0 records, found {len(stage0_by_id)}"

    # Pick fixed deterministic 6-item inspection subset (first 3 multiple + first 3 simple_python in canonical ID order)
    insp_mult_ids = [it["id"] for it in selected_items if it["category"] == "multiple"][:3]
    insp_simp_ids = [it["id"] for it in selected_items if it["category"] == "simple_python"][:3]
    inspect_6_ids = set(insp_simp_ids + insp_mult_ids)

    device_str = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device_str == "cuda" else torch.float32
    gpu_name = torch.cuda.get_device_name(0) if device_str == "cuda" else "CPU"
    print(
        f"=== Stage-0b Mechanism Follow-Up (PID={pid}, N=24=12S+12M, model={MODEL_ID}, dev={gpu_name}, dtype={dtype}) ===",
        flush=True,
    )

    t_load = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, revision="989aa7980e4cf806f80c7fef2b1adb7bc71aa306", local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(MODEL_ID, revision="989aa7980e4cf806f80c7fef2b1adb7bc71aa306", dtype=dtype, local_files_only=True).to(device_str)
    model.eval()
    load_s = time.perf_counter() - t_load

    vocab_size = model.config.vocab_size
    tok_info = xgr.TokenizerInfo.from_huggingface(tokenizer, vocab_size=vocab_size)
    compiler = xgr.GrammarCompiler(tok_info)
    cg_compact = compiler.compile_grammar(xgr.Grammar.from_ebnf(gu.EBNF_G_COMPACT))
    cg_optws = compiler.compile_grammar(xgr.Grammar.from_ebnf(gu.EBNF_G_OPTWS))

    eos_ids: List[int] = []
    if isinstance(tokenizer.eos_token_id, list):
        eos_ids.extend(tokenizer.eos_token_id)
    elif tokenizer.eos_token_id is not None:
        eos_ids.append(tokenizer.eos_token_id)
    if getattr(model.config, "eos_token_id", None) is not None:
        ce = model.config.eos_token_id
        for x in (ce if isinstance(ce, list) else [ce]):
            if x not in eos_ids:
                eos_ids.append(x)

    print(f"  Loaded local snapshot & compiled global grammars in {load_s:.2f}s (vocab={vocab_size}, eos={eos_ids})", flush=True)

    out_dir = BASE / "stage0b_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    inc_path = out_dir / "stage0b_per_instance.jsonl"

    per_instance_records: List[Dict] = []
    prefix_inspection_records: List[Dict] = []
    max_id_err_all = 0.0
    menu_compile_times_ms: List[float] = []
    t_gen = time.perf_counter()

    def pack_new_arm(item: Dict, dec: Dict) -> Tuple[Dict, Dict, Dict, Optional[int]]:
        ev = gu.evaluate_bfcl_inert_ast(item, dec["text"])
        cls = classify_call_outcome(item, ev)
        smt = gu.extract_smt_token_indices(tokenizer, dec["generated_ids"])
        sc = s0.aggregate_step_scores(dec["per_step"], smt, dec["n_content_tokens"])
        fn_step = locate_first_tool_name_step(tokenizer, dec["content_ids"], smt)
        arm_dict = {
            "text": dec["text"],
            "stopped_reason": dec["stopped_reason"],
            "n_content_tokens": dec["n_content_tokens"],
            "prefill_ms": dec["prefill_ms"],
            "first_tool_name_token_step": fn_step,
            "eval": ev,
            "classification": cls,
            "scores": sc,
        }
        return arm_dict, ev, smt, fn_step

    with inc_path.open("w", encoding="utf-8") as fout:
        for i, item in enumerate(selected_items):
            iid = item["id"]
            s0_rec = stage0_by_id[iid]

            # Build the two new prompt tokenizations (exact same offered tool docs & question; zero gold leakage)
            msgs_neu = s0b.build_messages_stage0b(item, "neutral")
            prompt_neu_text = tokenizer.apply_chat_template(msgs_neu, tokenize=False, add_generation_prompt=True)
            prompt_neu_ids = tokenizer.encode(prompt_neu_text, add_special_tokens=False, return_tensors="pt")

            msgs_cmp = s0b.build_messages_stage0b(item, "compact")
            prompt_cmp_text = tokenizer.apply_chat_template(msgs_cmp, tokenize=False, add_generation_prompt=True)
            prompt_cmp_ids = tokenizer.encode(prompt_cmp_text, add_special_tokens=False, return_tensors="pt")

            # Compile per-item offered-menu enum grammars (Control B; canonical sorted union of item["function"] ONLY)
            ebnf_cm, ebnf_wm, canonical_menu = s0b.build_menu_enum_grammars(item["function"])
            t_mc0 = time.perf_counter()
            cg_cm = compiler.compile_grammar(xgr.Grammar.from_ebnf(ebnf_cm))
            cg_wm = compiler.compile_grammar(xgr.Grammar.from_ebnf(ebnf_wm))
            mc_ms = (time.perf_counter() - t_mc0) * 1000.0
            menu_compile_times_ms.append(mc_ms)

            # --- Arm 1 & 2: Prompt_Neutral x {G_optws, G_compact} ---
            dec_n_w = decode_greedy_with_prefix_inspect(model, tokenizer, prompt_neu_ids, cg_optws, vocab_size, eos_ids)
            arm_n_w, _, _, fn_n_w = pack_new_arm(item, dec_n_w)

            dec_n_c = decode_greedy_with_prefix_inspect(model, tokenizer, prompt_neu_ids, cg_compact, vocab_size, eos_ids)
            arm_n_c, ev_n_c, smt_n_c, fn_n_c = pack_new_arm(item, dec_n_c)

            fp_neu, err_fp_neu = run_fixed_path_pair(
                model, prompt_neu_ids, dec_n_c, smt_n_c, ev_n_c, cg_compact, cg_optws, vocab_size, eos_ids
            )

            # --- Arm 3 & 4: Prompt_Compact x {G_optws, G_compact} ---
            dec_c_w = decode_greedy_with_prefix_inspect(model, tokenizer, prompt_cmp_ids, cg_optws, vocab_size, eos_ids)
            arm_c_w, _, _, fn_c_w = pack_new_arm(item, dec_c_w)

            dec_c_c = decode_greedy_with_prefix_inspect(model, tokenizer, prompt_cmp_ids, cg_compact, vocab_size, eos_ids)
            arm_c_c, ev_c_c, smt_c_c, fn_c_c = pack_new_arm(item, dec_c_c)

            fp_cmp, err_fp_cmp = run_fixed_path_pair(
                model, prompt_cmp_ids, dec_c_c, smt_c_c, ev_c_c, cg_compact, cg_optws, vocab_size, eos_ids
            )

            # --- Arm 5 & 6: Prompt_Neutral x {G_optws_menu, G_compact_menu} ---
            dec_m_w = decode_greedy_with_prefix_inspect(model, tokenizer, prompt_neu_ids, cg_wm, vocab_size, eos_ids)
            arm_m_w, _, _, fn_m_w = pack_new_arm(item, dec_m_w)

            dec_m_c = decode_greedy_with_prefix_inspect(model, tokenizer, prompt_neu_ids, cg_cm, vocab_size, eos_ids)
            arm_m_c, ev_m_c, smt_m_c, fn_m_c = pack_new_arm(item, dec_m_c)

            fp_menu, err_fp_menu = run_fixed_path_pair(
                model, prompt_neu_ids, dec_m_c, smt_m_c, ev_m_c, cg_cm, cg_wm, vocab_size, eos_ids
            )

            for a in (arm_n_w, arm_n_c, arm_c_w, arm_c_c, arm_m_w, arm_m_c):
                if a["scores"].get("valid_scores"):
                    max_id_err_all = max(max_id_err_all, a["scores"]["max_identity_abs_err"])
            max_id_err_all = max(max_id_err_all, err_fp_neu, err_fp_cmp, err_fp_menu)

            # Reuse sealed Stage-0 `Prompt_Spaced` arms BYTE-FOR-BYTE (only adding outcome classification)
            reused_spaced_u = {
                "reused_byte_for_byte_from_stage0": True,
                "text": s0_rec["unconstrained"]["text"],
                "stopped_reason": s0_rec["unconstrained"]["stopped_reason"],
                "n_content_tokens": s0_rec["unconstrained"]["n_content_tokens"],
                "eval": s0_rec["unconstrained"]["eval"],
                "classification": classify_call_outcome(item, s0_rec["unconstrained"]["eval"]),
                "scores": s0_rec["unconstrained"]["scores"],
            }
            reused_spaced_w = {
                "reused_byte_for_byte_from_stage0": True,
                "text": s0_rec["G_optws"]["text"],
                "stopped_reason": s0_rec["G_optws"]["stopped_reason"],
                "n_content_tokens": s0_rec["G_optws"]["n_content_tokens"],
                "eval": s0_rec["G_optws"]["eval"],
                "classification": classify_call_outcome(item, s0_rec["G_optws"]["eval"]),
                "scores": s0_rec["G_optws"]["scores"],
            }
            reused_spaced_c = {
                "reused_byte_for_byte_from_stage0": True,
                "text": s0_rec["G_compact"]["text"],
                "stopped_reason": s0_rec["G_compact"]["stopped_reason"],
                "n_content_tokens": s0_rec["G_compact"]["n_content_tokens"],
                "eval": s0_rec["G_compact"]["eval"],
                "classification": classify_call_outcome(item, s0_rec["G_compact"]["eval"]),
                "scores": s0_rec["G_compact"]["scores"],
            }

            # Prefix-logit timing & first-tool-name-token inspection (compact 6-item full trace including Prompt_Spaced probe,
            # plus concise first-tool-name step summary on ALL 24 items)
            spaced_probe = None
            if iid in inspect_6_ids:
                msgs_sp = gu.build_messages(item)
                prompt_sp_text = tokenizer.apply_chat_template(msgs_sp, tokenize=False, add_generation_prompt=True)
                prompt_sp_ids = tokenizer.encode(prompt_sp_text, add_special_tokens=False, return_tensors="pt")
                pr_sp_w = decode_greedy_with_prefix_inspect(
                    model, tokenizer, prompt_sp_ids, cg_optws, vocab_size, eos_ids,
                    max_new_tokens=PREFIX_INSPECT_STEPS, prefix_inspect_steps=PREFIX_INSPECT_STEPS,
                )
                pr_sp_c = decode_greedy_with_prefix_inspect(
                    model, tokenizer, prompt_sp_ids, cg_compact, vocab_size, eos_ids,
                    max_new_tokens=PREFIX_INSPECT_STEPS, prefix_inspect_steps=PREFIX_INSPECT_STEPS,
                )
                # Verify read-only 8-step replay matches the exact sealed Stage-0 prefix text
                w_prefix_match = bool(s0_rec["G_optws"]["text"].startswith(pr_sp_w["text"]))
                c_prefix_match = bool(s0_rec["G_compact"]["text"].startswith(pr_sp_c["text"]))
                spaced_probe = {
                    "spaced__G_optws": {
                        "matches_sealed_stage0_prefix": w_prefix_match,
                        "prefill_ms": pr_sp_w["prefill_ms"],
                        "prefix_trace": pr_sp_w["prefix_trace"],
                    },
                    "spaced__G_compact": {
                        "matches_sealed_stage0_prefix": c_prefix_match,
                        "prefill_ms": pr_sp_c["prefill_ms"],
                        "prefix_trace": pr_sp_c["prefix_trace"],
                    },
                }

                prefix_inspection_records.append({
                    "id": iid,
                    "category": item["category"],
                    "offered_menu_canonical": canonical_menu,
                    "gold_func_names": sorted({next(iter(g.keys())) for g in item["ground_truth"]}),
                    "menu_pair_compile_ms": mc_ms,
                    "prompt_spaced_readonly_8step_probe": spaced_probe,
                    "neutral__G_optws": {"first_tool_name_step": fn_n_w, "prefill_ms": dec_n_w["prefill_ms"], "prefix_trace": dec_n_w["prefix_trace"]},
                    "neutral__G_compact": {"first_tool_name_step": fn_n_c, "prefill_ms": dec_n_c["prefill_ms"], "prefix_trace": dec_n_c["prefix_trace"]},
                    "compact__G_optws": {"first_tool_name_step": fn_c_w, "prefill_ms": dec_c_w["prefill_ms"], "prefix_trace": dec_c_w["prefix_trace"]},
                    "compact__G_compact": {"first_tool_name_step": fn_c_c, "prefill_ms": dec_c_c["prefill_ms"], "prefix_trace": dec_c_c["prefix_trace"]},
                    "neutral_menu__G_optws_menu": {"first_tool_name_step": fn_m_w, "prefill_ms": dec_m_w["prefill_ms"], "prefix_trace": dec_m_w["prefix_trace"]},
                    "neutral_menu__G_compact_menu": {"first_tool_name_step": fn_m_c, "prefill_ms": dec_m_c["prefill_ms"], "prefix_trace": dec_m_c["prefix_trace"]},
                })

            # Extract compact step-summary for the exact first tool-name step across ALL 24 items
            def fn_step_snapshot(dec_obj: Dict, fn_step: Optional[int]) -> Optional[Dict]:
                if fn_step is None or fn_step >= len(dec_obj["prefix_trace"]):
                    return None
                st = dec_obj["prefix_trace"][fn_step]
                prev_st = dec_obj["prefix_trace"][fn_step - 1] if fn_step > 0 else None
                return {
                    "first_tool_name_step": fn_step,
                    "prev_step_token": prev_st["chosen_token_text"] if prev_st else None,
                    "prev_step_retained_mass": prev_st["retained_mass"] if prev_st else None,
                    "prev_step_n_allowed": prev_st["n_allowed_tokens"] if prev_st else None,
                    "chosen_token": st["chosen_token_text"],
                    "retained_mass": st["retained_mass"],
                    "n_allowed_tokens": st["n_allowed_tokens"],
                    "pre_nll": st["pre_nll"],
                    "post_nll": st["post_nll"],
                    "forward_ms": st["forward_ms"],
                    "mask_ms": st["mask_ms"],
                    "top1_unmasked": st["top5_unmasked"][0] if st["top5_unmasked"] else None,
                    "top1_masked": st["top5_masked"][0] if st["top5_masked"] else None,
                }

            rec = {
                "idx": i,
                "id": iid,
                "category": item["category"],
                "tool_family_cluster": item["tool_family_cluster"],
                "offered_menu_canonical": canonical_menu,
                "n_offered_functions": len(canonical_menu),
                "prompt_len_tokens": {
                    "spaced_reused": s0_rec["prompt_len_tokens"],
                    "neutral": int(prompt_neu_ids.shape[1]),
                    "compact": int(prompt_cmp_ids.shape[1]),
                },
                "menu_pair_compile_ms": mc_ms,
                "arms": {
                    "spaced__unconstrained_reused": reused_spaced_u,
                    "spaced__G_optws_reused": reused_spaced_w,
                    "spaced__G_compact_reused": reused_spaced_c,
                    "neutral__G_optws": arm_n_w,
                    "neutral__G_compact": arm_n_c,
                    "compact__G_optws": arm_c_w,
                    "compact__G_compact": arm_c_c,
                    "neutral_menu__G_optws_menu": arm_m_w,
                    "neutral_menu__G_compact_menu": arm_m_c,
                },
                "first_tool_name_step_snapshots": {
                    "neutral__G_optws": fn_step_snapshot(dec_n_w, fn_n_w),
                    "neutral__G_compact": fn_step_snapshot(dec_n_c, fn_n_c),
                    "compact__G_optws": fn_step_snapshot(dec_c_w, fn_c_w),
                    "compact__G_compact": fn_step_snapshot(dec_c_c, fn_c_c),
                    "neutral_menu__G_optws_menu": fn_step_snapshot(dec_m_w, fn_m_w),
                    "neutral_menu__G_compact_menu": fn_step_snapshot(dec_m_c, fn_m_c),
                },
                "fixed_path_pairs": {
                    "spaced_reused": s0_rec["fixed_path_shared_forward"],
                    "neutral": fp_neu,
                    "compact": fp_cmp,
                    "neutral_menu": fp_menu,
                },
            }
            per_instance_records.append(rec)
            fout.write(json.dumps(rec) + "\n")
            fout.flush()

            if (i + 1) % 6 == 0 or (i + 1) == 24:
                def ok_cnt(ak):
                    return sum(1 for r in per_instance_records if r["arms"][ak]["eval"]["ast_correct"])
                print(
                    f"  [{i+1:2d}/24] elapsed={time.perf_counter()-t_gen:5.1f}s | AST ok: "
                    f"Spaced(W={ok_cnt('spaced__G_optws_reused')},C={ok_cnt('spaced__G_compact_reused')}) | "
                    f"Neutral(W={ok_cnt('neutral__G_optws')},C={ok_cnt('neutral__G_compact')}) | "
                    f"Compact(W={ok_cnt('compact__G_optws')},C={ok_cnt('compact__G_compact')}) | "
                    f"NeuMenu(W={ok_cnt('neutral_menu__G_optws_menu')},C={ok_cnt('neutral_menu__G_compact_menu')}) | "
                    f"max_id_err={max_id_err_all:.2e}",
                    flush=True,
                )

    # Save prefix inspection JSON
    insp_path = out_dir / "stage0b_prefix_logit_inspection.json"
    insp_payload = {
        "description": "Step-by-step (steps 0..7) timing & top-5 unmasked/masked probability inspection across all 4 conditions on fixed 6-item subset (3 simple_python + 3 multiple), plus per-arm summary across all 24 items.",
        "inspect_6_ids": sorted(list(inspect_6_ids)),
        "mean_menu_pair_compile_ms_all_24": float(np.mean(menu_compile_times_ms)),
        "max_menu_pair_compile_ms_all_24": float(np.max(menu_compile_times_ms)),
        "six_item_full_prefix_traces": prefix_inspection_records,
        "all_24_first_tool_name_step_summary": {},
    }

    for ak in [
        "neutral__G_optws", "neutral__G_compact",
        "compact__G_optws", "compact__G_compact",
        "neutral_menu__G_optws_menu", "neutral_menu__G_compact_menu",
    ]:
        snaps = [r["first_tool_name_step_snapshots"][ak] for r in per_instance_records if r["first_tool_name_step_snapshots"][ak] is not None]
        if snaps:
            insp_payload["all_24_first_tool_name_step_summary"][ak] = {
                "n_located_within_first_8_steps": len(snaps),
                "median_step_index": float(np.median([s["first_tool_name_step"] for s in snaps])),
                "median_n_allowed_tokens": float(np.median([s["n_allowed_tokens"] for s in snaps])),
                "median_retained_mass": float(np.median([s["retained_mass"] for s in snaps])),
                "min_retained_mass": float(np.min([s["retained_mass"] for s in snaps])),
                "mean_forward_ms": float(np.mean([s["forward_ms"] for s in snaps])),
                "mean_mask_ms": float(np.mean([s["mask_ms"] for s in snaps])),
                "frac_top1_unmasked_allowed": float(np.mean([1.0 if s["top1_unmasked"]["allowed_by_grammar"] else 0.0 for s in snaps])),
                "prev_step_token_counts": {
                    tok: sum(1 for s in snaps if s["prev_step_token"] == tok)
                    for tok in sorted({s["prev_step_token"] for s in snaps if s["prev_step_token"] is not None})
                },
            }

    insp_path.write_text(json.dumps(insp_payload, indent=2), encoding="utf-8")

    # Build comprehensive structured summary (overall 24, split 12 simple vs 12 multiple,
    # matched vs confounded prompt cells, free-gen transfer, and STRICTLY SEPARATE fixed-path scores)
    arm_keys = [
        "spaced__unconstrained_reused",
        "spaced__G_optws_reused",
        "spaced__G_compact_reused",
        "neutral__G_optws",
        "neutral__G_compact",
        "compact__G_optws",
        "compact__G_compact",
        "neutral_menu__G_optws_menu",
        "neutral_menu__G_compact_menu",
    ]
    arm_summaries_all = {ak: summarize_arm_records(per_instance_records, ak, None) for ak in arm_keys}
    arm_summaries_simple = {ak: summarize_arm_records(per_instance_records, ak, "simple_python") for ak in arm_keys}
    arm_summaries_multiple = {ak: summarize_arm_records(per_instance_records, ak, "multiple") for ak in arm_keys}

    # Explicit matched vs confounded prompt cell matrix
    cell_specs = [
        ("spaced__G_optws_reused", "Prompt_Spaced (reused)", "G_optws (global)", "MATCHED (spaced example + optional-ws grammar)"),
        ("spaced__G_compact_reused", "Prompt_Spaced (reused)", "G_compact (global)", "CONFOUNDED / MISMATCHED (spaced example + no-ws grammar)"),
        ("neutral__G_optws", "Prompt_Neutral (no example)", "G_optws (global)", "FORMAT-NEUTRAL (no example + optional-ws grammar)"),
        ("neutral__G_compact", "Prompt_Neutral (no example)", "G_compact (global)", "FORMAT-NEUTRAL (no example + no-ws grammar)"),
        ("compact__G_optws", "Prompt_Compact (compact example)", "G_optws (global)", "SUPERSET-COMPATIBLE (compact example + optional-ws grammar)"),
        ("compact__G_compact", "Prompt_Compact (compact example)", "G_compact (global)", "MATCHED (compact example + no-ws grammar)"),
        ("neutral_menu__G_optws_menu", "Prompt_Neutral (no example)", "G_optws_menu (offered enum)", "FORMAT-NEUTRAL + MENU-ENUM (optional-ws)"),
        ("neutral_menu__G_compact_menu", "Prompt_Neutral (no example)", "G_compact_menu (offered enum)", "FORMAT-NEUTRAL + MENU-ENUM (compact no-ws)"),
    ]
    prompt_cell_matrix = []
    for ak, p_lbl, g_lbl, match_lbl in cell_specs:
        a_all = arm_summaries_all[ak]
        a_s = arm_summaries_simple[ak]
        a_m = arm_summaries_multiple[ak]
        prompt_cell_matrix.append({
            "arm_key": ak,
            "prompt": p_lbl,
            "grammar": g_lbl,
            "cell_type": match_lbl,
            "all_24": {
                "json_valid": a_all["json_valid_count"],
                "schema_valid": a_all["call_schema_valid_count"],
                "in_menu": a_all["in_provided_menu_count"],
                "ast_correct": a_all["ast_correct_count"],
                "error_taxonomy": a_all["error_taxonomy"],
            },
            "simple_12_menu_size_1": {
                "in_menu": a_s["in_provided_menu_count"],
                "ast_correct": a_s["ast_correct_count"],
                "error_taxonomy": a_s["error_taxonomy"],
            },
            "multiple_12_menu_size_2_to_3": {
                "in_menu": a_m["in_provided_menu_count"],
                "ast_correct": a_m["ast_correct_count"],
                "error_taxonomy": a_m["error_taxonomy"],
            },
        })

    # Post-run integrity verification of ALL sealed Stage-0 files & 416 blind test
    post_hashes = verify_sealed_hashes("POST-RUN")
    assert pre_hashes == post_hashes

    summary = {
        "protocol": "STAGE0B_AMENDMENT_PROTOCOL.md",
        "protocol_sha256": proto_sha,
        "real_pid": pid,
        "wall_time_s": time.perf_counter() - t0,
        "model_metadata": {
            "model_id": MODEL_ID,
            "license": MODEL_LICENSE,
            "verified_commit_hash": transport_rec["pinned_commit"],
            "verified_safetensors_sha256": transport_rec["expected_sha256_x_linked_etag"],
            "dtype": str(dtype),
            "device": gpu_name,
            "vocab_size": vocab_size,
            "eos_token_ids": eos_ids,
            "max_new_tokens": MAX_NEW_TOKENS,
            "offline_local_files_only": True,
        },
        "backend_versions_and_licenses": {
            "xgrammar": {"version": importlib.metadata.version("xgrammar"), "license": "Apache-2.0"},
            "transformers": {"version": importlib.metadata.version("transformers"), "license": "Apache-2.0"},
            "torch": {"version": torch.__version__, "license": "BSD-3-Clause"},
            "tokenizers": {"version": importlib.metadata.version("tokenizers"), "license": "Apache-2.0"},
            "bfcl_upstream": {"commit": "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8", "license": "Apache-2.0"},
        },
        "integrity_verification": {
            "all_sealed_stage0_and_blind_test_hashes_verified_before_and_after": True,
            "sealed_hashes": post_hashes,
            "stage0b_mechanism_followup_py_sha256": sha256_file(pathlib.Path(__file__)),
            "stage0b_per_instance_jsonl_sha256": sha256_file(inc_path),
            "stage0b_prefix_logit_inspection_json_sha256": sha256_file(insp_path),
        },
        "max_algebra_identity_abs_err_observed": max_id_err_all,
        "matched_vs_confounded_prompt_cell_matrix": prompt_cell_matrix,
        "free_generation_all_24": {
            "overall_24": arm_summaries_all,
            "split_simple_python_12": arm_summaries_simple,
            "split_multiple_12": arm_summaries_multiple,
            "pairwise_comparisons_free_gen": {
                "spaced_reused": summarize_pair_free_gen(per_instance_records, "spaced__G_compact_reused", "spaced__G_optws_reused"),
                "neutral": summarize_pair_free_gen(per_instance_records, "neutral__G_compact", "neutral__G_optws"),
                "compact": summarize_pair_free_gen(per_instance_records, "compact__G_compact", "compact__G_optws"),
                "neutral_menu": summarize_pair_free_gen(per_instance_records, "neutral_menu__G_compact_menu", "neutral_menu__G_optws_menu"),
            },
        },
        "fixed_path_paired_shared_forward_SEPARATE": {
            "note": "STRICTLY SEPARATE from free-generation scores: scores identical compact-generated token paths under both grammars from ONE shared unmasked forward pass.",
            "spaced_reused": summarize_fixed_path_pair(per_instance_records, "spaced_reused"),
            "neutral": summarize_fixed_path_pair(per_instance_records, "neutral"),
            "compact": summarize_fixed_path_pair(per_instance_records, "compact"),
            "neutral_menu": summarize_fixed_path_pair(per_instance_records, "neutral_menu"),
        },
        "prefix_logit_first_tool_name_summary": insp_payload["all_24_first_tool_name_step_summary"],
    }

    sum_path = out_dir / "stage0b_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n=== Stage-0b Mechanism Follow-Up COMPLETE (PID={pid}, wall={summary['wall_time_s']:.1f}s, max_id_err={max_id_err_all:.2e}) ===", flush=True)
    print(f"Saved {sum_path} (sha256={sha256_file(sum_path)[:16]}...)", flush=True)


if __name__ == "__main__":
    main()
