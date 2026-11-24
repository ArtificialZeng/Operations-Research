"""
Stage-0 Bounded Pilot: Offline Single-Turn Function-Call Confidence Transfer Across
Syntax-Only JSON Grammars (`G_compact` vs `G_optws`) + Unconstrained Baseline.

Dataset: Preselected strictly benign, neutral read-only, tool-family-disjoint BFCL v4
Simple Python (60) + Multiple (40) pilot split (`bfcl_stage0_pilot_dataset.json`, N=100).
Future blind test (`416` examples, `74` disjoint clusters) remains 100% untouched.

Locked protocol: STAGE0_PROTOCOL.md
Pre-launch gates asserted BEFORE running:
  1. BFCL_PILOT_SPLIT_RECEIPT.json (`zero_tool_family_root_overlap == True`)
  2. STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json (`all_fixtures_passed == True`)

Mandatory primary comparators included:
  - Unconstrained greedy baseline (`G-NLL` all tokens & `G-NLL_SMT`)
  - Ye et al. (TMLR 2026, arXiv:2604.22985v2) `G-NLL_SMT` (both unmasked & post-mask)
  - Reddy et al. (arXiv:2603.03305) Feasible Mass (`log Z_t`, mean & min retained mass)
  - Parvatikar (UncertaiNLP 2026) First-token & mean pre/post entropy shift

Evaluates BOTH:
  (A) Fixed-path paired scoring on identical token paths accepted by BOTH `G_compact` and `G_optws`
      from ONE shared unmasked forward pass (exact float64 algebra verified every step).
  (B) Separate all-generated-cases evaluation (`N=100`, ZERO cherry-picking) under:
      (1) Unconstrained greedy, (2) `G_compact` constrained greedy, (3) `G_optws` constrained greedy.
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
from sklearn.metrics import roc_auc_score
from transformers import AutoModelForCausalLM, AutoTokenizer

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(BASE))

import grammar_utils as gu  # noqa: E402

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"
MODEL_LICENSE = "Apache-2.0"
MAX_NEW_TOKENS = 192
TARGET_COVERAGE = 0.80


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def decode_greedy_stepwise(
    model,
    tokenizer,
    input_ids: torch.Tensor,
    compiled_grammar: Optional[xgr.CompiledGrammar],
    vocab_size: int,
    eos_token_ids: List[int],
    max_new_tokens: int = MAX_NEW_TOKENS,
) -> Dict:
    """
    Exact KV-cached greedy decoding recording float64 pre-mask & post-mask NLL,
    retained feasible mass, pre/post entropy, and algebraic identity residual at every step.
    """
    device = next(model.parameters()).device
    matcher = xgr.GrammarMatcher(compiled_grammar) if compiled_grammar is not None else None
    bitmask = xgr.allocate_token_bitmask(1, vocab_size) if compiled_grammar is not None else None

    generated_ids: List[int] = []
    per_step: List[Dict[str, float]] = []
    stopped_reason = "max_new_tokens"

    with torch.no_grad():
        out = model(input_ids=input_ids.to(device), use_cache=True)
        past_key_values = out.past_key_values
        next_logits = out.logits[0, -1, :]  # [V]

        for step in range(max_new_tokens):
            if matcher is not None:
                matcher.fill_next_token_bitmask(bitmask)
                allowed_bool = gu.bitmask_to_bool(bitmask[0], vocab_size)
                masked_logits = next_logits.detach().to(dtype=torch.float64, device="cpu").masked_fill(~allowed_bool, float("-inf"))
                tok_id = int(torch.argmax(masked_logits).item())
            else:
                allowed_bool = None
                tok_id = int(torch.argmax(next_logits.detach().to(dtype=torch.float64, device="cpu")).item())

            sm = gu.step_mask_metrics_from_logits(next_logits, allowed_bool, tok_id)
            per_step.append(sm)
            generated_ids.append(tok_id)

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
            out = model(input_ids=next_inp, past_key_values=past_key_values, use_cache=True)
            past_key_values = out.past_key_values
            next_logits = out.logits[0, -1, :]

    # Strip trailing EOS token for text decode
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
    }


def teacher_force_logits(model, prompt_ids: torch.Tensor, target_ids: List[int]) -> torch.Tensor:
    """Single forward pass over prompt + target_ids returning exact unmasked logits [T, V] for target_ids."""
    device = next(model.parameters()).device
    T = len(target_ids)
    assert T > 0
    tgt = torch.tensor([target_ids], dtype=torch.long, device=device)
    full = torch.cat([prompt_ids.to(device), tgt], dim=1)
    p_len = prompt_ids.shape[1]
    with torch.no_grad():
        logits = model(input_ids=full, use_cache=False).logits[0]  # [p_len + T, V]
    # Position p_len - 1 predicts target_ids[0], ..., p_len + T - 2 predicts target_ids[T - 1]
    return logits[p_len - 1 : p_len + T - 1, :].detach().cpu()


def aggregate_step_scores(per_step: List[Dict[str, float]], smt_info: Dict, n_content: int) -> Dict[str, float]:
    """Aggregates uncertainty scores (HIGHER = MORE UNCERTAIN) over all, SMT_ye26, SMT_val, and syntax subsets."""
    # Restrict to content tokens (exclude trailing EOS if present)
    steps = per_step[:n_content]
    T = len(steps)
    if T == 0:
        return {"valid_scores": False}

    pre = np.array([s["pre_nll"] for s in steps], dtype=np.float64)
    post = np.array([s["post_nll"] for s in steps], dtype=np.float64)
    logz = np.array([s["log_retained_mass"] for s in steps], dtype=np.float64)
    mass = np.array([s["retained_mass"] for s in steps], dtype=np.float64)
    hpre = np.array([s["h_pre"] for s in steps], dtype=np.float64)
    hpost = np.array([s["h_post"] for s in steps], dtype=np.float64)
    id_err = np.array([s["identity_abs_err"] for s in steps], dtype=np.float64)

    def sub_mean_sum(arr: np.ndarray, idxs: List[int]) -> Tuple[float, float]:
        if not idxs:
            return float("nan"), float("nan")
        vals = arr[idxs]
        return float(np.mean(vals)), float(np.sum(vals))

    ye26_idx = [i for i in smt_info.get("smt_ye26_indices", []) if i < T]
    val_idx = [i for i in smt_info.get("smt_val_indices", []) if i < T]
    syn_idx = [i for i in smt_info.get("syntax_indices", []) if i < T]

    pre_ye26_m, pre_ye26_s = sub_mean_sum(pre, ye26_idx)
    post_ye26_m, post_ye26_s = sub_mean_sum(post, ye26_idx)
    logz_ye26_m, logz_ye26_s = sub_mean_sum(logz, ye26_idx)

    pre_val_m, pre_val_s = sub_mean_sum(pre, val_idx)
    post_val_m, post_val_s = sub_mean_sum(post, val_idx)

    pre_syn_m, pre_syn_s = sub_mean_sum(pre, syn_idx)
    post_syn_m, post_syn_s = sub_mean_sum(post, syn_idx)
    logz_syn_m, logz_syn_s = sub_mean_sum(logz, syn_idx)

    return {
        "valid_scores": True,
        "n_content_tokens": T,
        "n_smt_ye26": len(ye26_idx),
        "n_smt_val": len(val_idx),
        "n_syntax": len(syn_idx),
        "max_identity_abs_err": float(np.nanmax(id_err)),
        # All-token G-NLL (higher = more uncertain)
        "pre_nll_all_mean": float(np.mean(pre)),
        "pre_nll_all_sum": float(np.sum(pre)),
        "post_nll_all_mean": float(np.mean(post)),
        "post_nll_all_sum": float(np.sum(post)),
        # Mandatory Ye et al. (TMLR 2026) G-NLL_SMT (higher = more uncertain)
        "pre_gnll_smt_mean": pre_ye26_m,
        "pre_gnll_smt_sum": pre_ye26_s,
        "post_gnll_smt_mean": post_ye26_m,
        "post_gnll_smt_sum": post_ye26_s,
        "neg_logz_smt_mean": float(-logz_ye26_m) if math.isfinite(logz_ye26_m) else float("nan"),
        "neg_logz_smt_sum": float(-logz_ye26_s) if math.isfinite(logz_ye26_s) else float("nan"),
        # Value-only SMT sensitivity subset
        "pre_gnll_smt_val_mean": pre_val_m,
        "post_gnll_smt_val_mean": post_val_m,
        # Syntax-only complement
        "pre_nll_syntax_mean": pre_syn_m,
        "post_nll_syntax_mean": post_syn_m,
        "neg_logz_syntax_mean": float(-logz_syn_m) if math.isfinite(logz_syn_m) else float("nan"),
        "neg_logz_syntax_sum": float(-logz_syn_s) if math.isfinite(logz_syn_s) else float("nan"),
        # Reddy et al. (2603.03305) feasible mass (neg log retained mass: higher = more mass lost = more uncertain)
        "neg_logz_all_mean": float(-np.mean(logz)),
        "neg_logz_all_sum": float(-np.sum(logz)),
        "min_retained_mass": float(np.min(mass)),
        "mean_retained_mass": float(np.mean(mass)),
        # Parvatikar (UncertaiNLP 2026) first-token & mean entropy
        "h_pre_first": float(hpre[0]),
        "h_post_first": float(hpost[0]),
        "h_pre_mean": float(np.mean(hpre)),
        "h_post_mean": float(np.mean(hpost)),
    }


def compute_aurc_and_risk_at_cov(uncertainties: np.ndarray, errors: np.ndarray, target_cov: float = 0.80) -> Dict[str, float]:
    """
    Computes AURC and selective risk at `target_cov`.
    `uncertainties`: higher = more uncertain (abstain first).
    `errors`: 1.0 if incorrect, 0.0 if correct.
    """
    n = len(errors)
    # Sort ascending by uncertainty (deterministic tie-break via mergesort)
    order = np.argsort(uncertainties, kind="mergesort")
    err_sorted = errors[order]
    cum_err = np.cumsum(err_sorted)
    ks = np.arange(1, n + 1, dtype=np.float64)
    risks = cum_err / ks
    aurc = float(np.mean(risks))

    k_cov = max(1, int(math.floor(target_cov * n + 1e-12)))
    risk_at_cov = float(cum_err[k_cov - 1] / k_cov)
    # Exact threshold = k_cov-th smallest uncertainty
    thresh = float(uncertainties[order[k_cov - 1]])

    # AUROC for detecting errors (error=1 vs correct=0) using uncertainty
    n_err = int(np.sum(errors == 1.0))
    n_cor = int(np.sum(errors == 0.0))
    if n_err > 0 and n_cor > 0:
        auroc = float(roc_auc_score(errors, uncertainties))
    else:
        auroc = float("nan")

    # Oracle AURC (all correct ranked before all errors)
    oracle_err = np.sort(errors)
    oracle_aurc = float(np.mean(np.cumsum(oracle_err) / ks))
    e_aurc = aurc - oracle_aurc

    return {
        "n": n,
        "n_correct": n_cor,
        "n_error": n_err,
        "base_error_rate": float(n_err / n),
        "auroc": auroc,
        "aurc": aurc,
        "e_aurc": e_aurc,
        "risk_at_target_cov": risk_at_cov,
        "target_cov": target_cov,
        "k_at_target_cov": k_cov,
        "threshold_at_target_cov": thresh,
    }


def eval_threshold_transfer(
    u_src: np.ndarray, err_src: np.ndarray,
    u_tgt: np.ndarray, err_tgt: np.ndarray,
    target_cov: float = 0.80,
) -> Dict[str, float]:
    """
    Learns abstention threshold `tau_src` achieving `target_cov` on source grammar `u_src`,
    then applies `tau_src` verbatim (accept iff u_tgt <= tau_src) on target grammar `u_tgt`.
    """
    src_m = compute_aurc_and_risk_at_cov(u_src, err_src, target_cov)
    tgt_m = compute_aurc_and_risk_at_cov(u_tgt, err_tgt, target_cov)
    tau = src_m["threshold_at_target_cov"]
    accepted = u_tgt <= tau
    n_acc = int(np.sum(accepted))
    cov_realized = float(n_acc / len(u_tgt))
    risk_realized = float(np.mean(err_tgt[accepted])) if n_acc > 0 else float("nan")
    return {
        "tau_from_source": tau,
        "source_in_grammar_risk_at_80": src_m["risk_at_target_cov"],
        "target_in_grammar_risk_at_80": tgt_m["risk_at_target_cov"],
        "transferred_n_accepted": n_acc,
        "transferred_coverage": cov_realized,
        "coverage_shift_vs_80": cov_realized - target_cov,
        "transferred_selective_risk": risk_realized,
        "risk_shift_vs_target_in_grammar": (risk_realized - tgt_m["risk_at_target_cov"]) if math.isfinite(risk_realized) else float("nan"),
    }


def cluster_bootstrap_metric_diff(
    clusters: List[str],
    u_a: np.ndarray, err_a: np.ndarray,
    u_b: np.ndarray, err_b: np.ndarray,
    n_boot: int = 2000,
    seed: int = 20261124,
) -> Dict:
    """Cluster bootstrap by tool_family_cluster for AUROC/AURC/risk@80% and A->B transfer shift."""
    rng = np.random.default_rng(seed)
    c_to_idx: Dict[str, List[int]] = {}
    for i, c in enumerate(clusters):
        c_to_idx.setdefault(c, []).append(i)
    c_keys = sorted(c_to_idx.keys())
    n_c = len(c_keys)

    d_auroc, d_aurc, d_risk80, cov_a2b, cov_b2a = [], [], [], [], []
    for _ in range(n_boot):
        drawn = rng.integers(0, n_c, size=n_c)
        idxs = [i for k in drawn for i in c_to_idx[c_keys[k]]]
        ea, eb = err_a[idxs], err_b[idxs]
        ua, ub = u_a[idxs], u_b[idxs]
        ma = compute_aurc_and_risk_at_cov(ua, ea, TARGET_COVERAGE)
        mb = compute_aurc_and_risk_at_cov(ub, eb, TARGET_COVERAGE)
        if math.isfinite(ma["auroc"]) and math.isfinite(mb["auroc"]):
            d_auroc.append(ma["auroc"] - mb["auroc"])
        d_aurc.append(ma["aurc"] - mb["aurc"])
        d_risk80.append(ma["risk_at_target_cov"] - mb["risk_at_target_cov"])
        cov_a2b.append(eval_threshold_transfer(ua, ea, ub, eb, TARGET_COVERAGE)["transferred_coverage"])
        cov_b2a.append(eval_threshold_transfer(ub, eb, ua, ea, TARGET_COVERAGE)["transferred_coverage"])

    def ci(vals):
        if not vals:
            return [float("nan"), float("nan")]
        lo, hi = np.percentile(vals, [2.5, 97.5])
        return [float(lo), float(hi)]

    return {
        "n_clusters": n_c,
        "n_boot": n_boot,
        "diff_auroc_A_minus_B_ci95": ci(d_auroc),
        "diff_aurc_A_minus_B_ci95": ci(d_aurc),
        "diff_risk80_A_minus_B_ci95": ci(d_risk80),
        "transfer_A_to_B_cov_ci95": ci(cov_a2b),
        "transfer_B_to_A_cov_ci95": ci(cov_b2a),
    }


def main():
    t0 = time.perf_counter()
    pid = os.getpid()

    # HARD PRE-LAUNCH GATES
    split_rec_p = BASE / "BFCL_PILOT_SPLIT_RECEIPT.json"
    alg_rec_p = BASE / "STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json"
    proto_p = BASE / "STAGE0_PROTOCOL.md"
    assert split_rec_p.exists() and json.loads(split_rec_p.read_text(encoding="utf-8"))["clustering_and_disjoint_split"]["zero_tool_family_root_overlap"] is True
    assert alg_rec_p.exists() and json.loads(alg_rec_p.read_text(encoding="utf-8"))["all_fixtures_passed"] is True
    assert proto_p.exists(), "Missing locked STAGE0_PROTOCOL.md!"

    pilot_data_p = BASE / "bfcl_stage0_pilot_dataset.json"
    pilot_items = json.loads(pilot_data_p.read_text(encoding="utf-8"))
    N = len(pilot_items)

    device_str = "cuda" if torch.cuda.is_available() else "cpu"
    dtype = torch.bfloat16 if device_str == "cuda" else torch.float32
    gpu_name = torch.cuda.get_device_name(0) if device_str == "cuda" else "CPU"
    print(f"=== Stage-0 Grammar Confidence Transfer Pilot (PID={pid}, N={N}, model={MODEL_ID}, dev={gpu_name}, dtype={dtype}) ===", flush=True)

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

    eos_ids = []
    if isinstance(tokenizer.eos_token_id, list):
        eos_ids.extend(tokenizer.eos_token_id)
    elif tokenizer.eos_token_id is not None:
        eos_ids.append(tokenizer.eos_token_id)
    if getattr(model.config, "eos_token_id", None) is not None:
        ce = model.config.eos_token_id
        for x in (ce if isinstance(ce, list) else [ce]):
            if x not in eos_ids:
                eos_ids.append(x)

    print(f"  Loaded model & compiled G_compact/G_optws in {load_s:.2f}s (vocab={vocab_size}, eos={eos_ids})", flush=True)

    out_dir = BASE / "stage0_pilot_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    inc_path = out_dir / "stage0_pilot_per_instance.jsonl"
    per_instance_records: List[Dict] = []

    max_id_err_all = 0.0
    t_gen = time.perf_counter()

    with inc_path.open("w", encoding="utf-8") as fout:
        for i, item in enumerate(pilot_items):
            msgs = gu.build_messages(item)
            prompt_text = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
            prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False, return_tensors="pt")

            # 1) Unconstrained greedy
            dec_u = decode_greedy_stepwise(model, tokenizer, prompt_ids, None, vocab_size, eos_ids)
            ev_u = gu.evaluate_bfcl_inert_ast(item, dec_u["text"])
            smt_u = gu.extract_smt_token_indices(tokenizer, dec_u["generated_ids"])
            sc_u = aggregate_step_scores(dec_u["per_step"], smt_u, dec_u["n_content_tokens"])

            # 2) G_compact constrained greedy
            dec_c = decode_greedy_stepwise(model, tokenizer, prompt_ids, cg_compact, vocab_size, eos_ids)
            ev_c = gu.evaluate_bfcl_inert_ast(item, dec_c["text"])
            smt_c = gu.extract_smt_token_indices(tokenizer, dec_c["generated_ids"])
            sc_c = aggregate_step_scores(dec_c["per_step"], smt_c, dec_c["n_content_tokens"])
            if sc_c.get("valid_scores"):
                max_id_err_all = max(max_id_err_all, sc_c["max_identity_abs_err"])

            # 3) G_optws constrained greedy
            dec_w = decode_greedy_stepwise(model, tokenizer, prompt_ids, cg_optws, vocab_size, eos_ids)
            ev_w = gu.evaluate_bfcl_inert_ast(item, dec_w["text"])
            smt_w = gu.extract_smt_token_indices(tokenizer, dec_w["generated_ids"])
            sc_w = aggregate_step_scores(dec_w["per_step"], smt_w, dec_w["n_content_tokens"])
            if sc_w.get("valid_scores"):
                max_id_err_all = max(max_id_err_all, sc_w["max_identity_abs_err"])

            # 4) Fixed-path paired scoring on `dec_c["generated_ids"]` (including terminating EOS) from ONE shared unmasked forward pass
            fixed_path_rec: Dict = {"both_grammars_accept": False}
            if dec_c["stopped_reason"] == "grammar_terminated" and dec_c["n_content_tokens"] > 0:
                shared_logits = teacher_force_logits(model, prompt_ids, dec_c["generated_ids"])
                fp_c = gu.score_fixed_path_under_grammar(shared_logits, dec_c["generated_ids"], cg_compact, vocab_size, eos_ids)
                fp_w = gu.score_fixed_path_under_grammar(shared_logits, dec_c["generated_ids"], cg_optws, vocab_size, eos_ids)
                both_ok = bool(fp_c["accepted_all_tokens"] and fp_c["grammar_terminated"] and fp_w["accepted_all_tokens"] and fp_w["grammar_terminated"])
                if both_ok:
                    fsc_c = aggregate_step_scores(fp_c["per_step"], smt_c, dec_c["n_content_tokens"])
                    fsc_w = aggregate_step_scores(fp_w["per_step"], smt_c, dec_c["n_content_tokens"])
                    fsc_c["post_nll_with_eos_mean"] = float(np.mean([s["post_nll"] for s in fp_c["per_step"]]))
                    fsc_w["post_nll_with_eos_mean"] = float(np.mean([s["post_nll"] for s in fp_w["per_step"]]))
                    max_id_err_all = max(max_id_err_all, fsc_c["max_identity_abs_err"], fsc_w["max_identity_abs_err"])
                    assert fsc_c["max_identity_abs_err"] < 1e-11 and fsc_w["max_identity_abs_err"] < 1e-11
                    fixed_path_rec = {
                        "both_grammars_accept": True,
                        "n_content_tokens": dec_c["n_content_tokens"],
                        "n_total_tokens_with_eos": len(dec_c["generated_ids"]),
                        "ast_correct": ev_c["ast_correct"],
                        "G_compact": fsc_c,
                        "G_optws": fsc_w,
                    }

            rec = {
                "idx": i,
                "id": item["id"],
                "category": item["category"],
                "tool_family_cluster": item["tool_family_cluster"],
                "prompt_len_tokens": int(prompt_ids.shape[1]),
                "unconstrained": {
                    "text": dec_u["text"], "stopped_reason": dec_u["stopped_reason"],
                    "n_content_tokens": dec_u["n_content_tokens"],
                    "eval": ev_u, "scores": sc_u,
                },
                "G_compact": {
                    "text": dec_c["text"], "stopped_reason": dec_c["stopped_reason"],
                    "n_content_tokens": dec_c["n_content_tokens"],
                    "eval": ev_c, "scores": sc_c,
                },
                "G_optws": {
                    "text": dec_w["text"], "stopped_reason": dec_w["stopped_reason"],
                    "n_content_tokens": dec_w["n_content_tokens"],
                    "eval": ev_w, "scores": sc_w,
                },
                "parsed_call_equal_compact_vs_optws": (
                    ev_c["parsed_call"] is not None and ev_c["parsed_call"] == ev_w["parsed_call"]
                ),
                "fixed_path_shared_forward": fixed_path_rec,
            }
            per_instance_records.append(rec)
            fout.write(json.dumps(rec) + "\n")
            fout.flush()

            if (i + 1) % 20 == 0 or (i + 1) == N:
                c_ok = sum(1 for r in per_instance_records if r["G_compact"]["eval"]["ast_correct"])
                w_ok = sum(1 for r in per_instance_records if r["G_optws"]["eval"]["ast_correct"])
                u_ok = sum(1 for r in per_instance_records if r["unconstrained"]["eval"]["ast_correct"])
                eq = sum(1 for r in per_instance_records if r["parsed_call_equal_compact_vs_optws"])
                print(
                    f"  [{i+1:3d}/{N}] elapsed={time.perf_counter()-t_gen:5.1f}s | "
                    f"AST correct: Unc={u_ok}/{i+1}, G_comp={c_ok}/{i+1}, G_optws={w_ok}/{i+1} | "
                    f"same_parsed_call(C==W)={eq}/{i+1} | max_id_err={max_id_err_all:.2e}",
                    flush=True,
                )

    # --- Comprehensive Statistical & Transfer Analysis ---
    # 1) All-generated-cases evaluation (N=100, ZERO cherry-picking!)
    def mode_summary(mode_key: str) -> Dict:
        evs = [r[mode_key]["eval"] for r in per_instance_records]
        scs = [r[mode_key]["scores"] for r in per_instance_records]
        errs = np.array([0.0 if e["ast_correct"] else 1.0 for e in evs], dtype=np.float64)
        stopped = {}
        for r in per_instance_records:
            st = r[mode_key]["stopped_reason"]
            stopped[st] = stopped.get(st, 0) + 1

        score_keys = [
            "pre_nll_all_mean", "pre_nll_all_sum",
            "post_nll_all_mean", "post_nll_all_sum",
            "pre_gnll_smt_mean", "pre_gnll_smt_sum",
            "post_gnll_smt_mean", "post_gnll_smt_sum",
            "pre_gnll_smt_val_mean", "post_gnll_smt_val_mean",
            "pre_nll_syntax_mean", "post_nll_syntax_mean",
            "neg_logz_all_mean", "neg_logz_all_sum",
            "h_pre_first", "h_post_first", "h_pre_mean", "h_post_mean",
        ]
        score_metrics = {}
        for sk in score_keys:
            vals = np.array([s.get(sk, float("nan")) for s in scs], dtype=np.float64)
            # For non-parseable cases where SMT is NaN, assign +inf (maximum uncertainty = abstain first) so ALL N=100 are scored with zero cherry-picking!
            n_nan = int(np.sum(~np.isfinite(vals)))
            finite_max = float(np.nanmax(vals)) if np.any(np.isfinite(vals)) else 1e6
            vals_filled = np.where(np.isfinite(vals), vals, finite_max + 100.0)
            m = compute_aurc_and_risk_at_cov(vals_filled, errs, TARGET_COVERAGE)
            m["n_nan_filled_max_unc"] = n_nan
            m["mean_finite"] = float(np.nanmean(vals)) if np.any(np.isfinite(vals)) else float("nan")
            m["std_finite"] = float(np.nanstd(vals)) if np.any(np.isfinite(vals)) else float("nan")
            score_metrics[sk] = m

        return {
            "n_total": N,
            "json_valid_count": sum(1 for e in evs if e["json_valid"]),
            "call_schema_valid_count": sum(1 for e in evs if e["call_schema_valid"]),
            "ast_correct_count": sum(1 for e in evs if e["ast_correct"]),
            "ast_correct_simple": sum(1 for r in per_instance_records if r["category"] == "simple_python" and r[mode_key]["eval"]["ast_correct"]),
            "ast_correct_multiple": sum(1 for r in per_instance_records if r["category"] == "multiple" and r[mode_key]["eval"]["ast_correct"]),
            "stopped_reason_counts": stopped,
            "score_metrics_all_N": score_metrics,
        }

    all_gen_summary = {
        "unconstrained": mode_summary("unconstrained"),
        "G_compact": mode_summary("G_compact"),
        "G_optws": mode_summary("G_optws"),
        "parsed_call_equal_compact_vs_optws_count": sum(1 for r in per_instance_records if r["parsed_call_equal_compact_vs_optws"]),
        "ast_flip_compact_correct_optws_wrong": sum(1 for r in per_instance_records if r["G_compact"]["eval"]["ast_correct"] and not r["G_optws"]["eval"]["ast_correct"]),
        "ast_flip_optws_correct_compact_wrong": sum(1 for r in per_instance_records if r["G_optws"]["eval"]["ast_correct"] and not r["G_compact"]["eval"]["ast_correct"]),
    }

    # 2) Cross-grammar transfer on ALL N=100 generated cases (G_compact <-> G_optws)
    clusters_all = [r["tool_family_cluster"] for r in per_instance_records]
    err_c_all = np.array([0.0 if r["G_compact"]["eval"]["ast_correct"] else 1.0 for r in per_instance_records], dtype=np.float64)
    err_w_all = np.array([0.0 if r["G_optws"]["eval"]["ast_correct"] else 1.0 for r in per_instance_records], dtype=np.float64)

    def get_filled_vec(recs, mode_key, sk):
        vals = np.array([r[mode_key]["scores"].get(sk, float("nan")) for r in recs], dtype=np.float64)
        fmax = float(np.nanmax(vals)) if np.any(np.isfinite(vals)) else 1e6
        return np.where(np.isfinite(vals), vals, fmax + 100.0)

    all_gen_transfer = {}
    for sk in ["post_nll_all_mean", "post_nll_all_sum", "post_gnll_smt_mean", "post_gnll_smt_sum", "pre_nll_all_mean", "pre_gnll_smt_mean", "neg_logz_all_mean", "h_post_first"]:
        uc = get_filled_vec(per_instance_records, "G_compact", sk)
        uw = get_filled_vec(per_instance_records, "G_optws", sk)
        all_gen_transfer[sk] = {
            "spearman_rho_C_vs_W": float(stats.spearmanr(uc, uw).statistic),
            "kendall_tau_C_vs_W": float(stats.kendalltau(uc, uw).statistic),
            "mean_diff_C_minus_W": float(np.mean(uc - uw)),
            "transfer_compact_to_optws": eval_threshold_transfer(uc, err_c_all, uw, err_w_all, TARGET_COVERAGE),
            "transfer_optws_to_compact": eval_threshold_transfer(uw, err_w_all, uc, err_c_all, TARGET_COVERAGE),
            "cluster_bootstrap": cluster_bootstrap_metric_diff(clusters_all, uc, err_c_all, uw, err_w_all),
        }

    # 3) Fixed-path paired scoring analysis (identical token paths accepted by BOTH grammars from ONE shared forward pass!)
    fp_recs = [r for r in per_instance_records if r["fixed_path_shared_forward"]["both_grammars_accept"]]
    fp_clusters = [r["tool_family_cluster"] for r in fp_recs]
    fp_err = np.array([0.0 if r["fixed_path_shared_forward"]["ast_correct"] else 1.0 for r in fp_recs], dtype=np.float64)
    fixed_path_analysis: Dict = {
        "n_fixed_paths_both_accepted": len(fp_recs),
        "n_of_total": N,
        "n_correct": int(np.sum(fp_err == 0.0)),
        "n_error": int(np.sum(fp_err == 1.0)),
        "scores": {},
    }
    if len(fp_recs) > 0:
        for sk in [
            "pre_nll_all_mean", "post_nll_all_mean", "post_nll_all_sum",
            "pre_gnll_smt_mean", "post_gnll_smt_mean", "post_gnll_smt_sum",
            "pre_gnll_smt_val_mean", "post_gnll_smt_val_mean",
            "pre_nll_syntax_mean", "post_nll_syntax_mean",
            "neg_logz_all_mean", "neg_logz_all_sum", "neg_logz_smt_mean", "neg_logz_syntax_mean",
            "h_post_first", "h_post_mean",
        ]:
            uc = np.array([r["fixed_path_shared_forward"]["G_compact"][sk] for r in fp_recs], dtype=np.float64)
            uw = np.array([r["fixed_path_shared_forward"]["G_optws"][sk] for r in fp_recs], dtype=np.float64)
            mc = compute_aurc_and_risk_at_cov(uc, fp_err, TARGET_COVERAGE)
            mw = compute_aurc_and_risk_at_cov(uw, fp_err, TARGET_COVERAGE)
            fixed_path_analysis["scores"][sk] = {
                "G_compact": mc,
                "G_optws": mw,
                "mean_C": float(np.mean(uc)),
                "mean_W": float(np.mean(uw)),
                "mean_diff_C_minus_W": float(np.mean(uc - uw)),
                "spearman_rho_C_vs_W": float(stats.spearmanr(uc, uw).statistic) if np.std(uc) > 0 and np.std(uw) > 0 else float("nan"),
                "kendall_tau_C_vs_W": float(stats.kendalltau(uc, uw).statistic) if np.std(uc) > 0 and np.std(uw) > 0 else float("nan"),
                "transfer_compact_to_optws": eval_threshold_transfer(uc, fp_err, uw, fp_err, TARGET_COVERAGE),
                "transfer_optws_to_compact": eval_threshold_transfer(uw, fp_err, uc, fp_err, TARGET_COVERAGE),
                "cluster_bootstrap": cluster_bootstrap_metric_diff(fp_clusters, uc, fp_err, uw, fp_err),
            }

    # Exact Hanly-McNeil standard error estimate for pilot AUROC power check
    n_err_c = all_gen_summary["G_compact"]["n_total"] - all_gen_summary["G_compact"]["ast_correct_count"]
    n_cor_c = all_gen_summary["G_compact"]["ast_correct_count"]
    se_auroc_approx = math.sqrt((0.25 + (n_err_c + n_cor_c - 2) * (0.0833)) / max(1, n_err_c * n_cor_c)) if n_err_c > 0 and n_cor_c > 0 else float("nan")

    summary = {
        "protocol": "STAGE0_PROTOCOL.md",
        "real_pid": pid,
        "wall_time_s": time.perf_counter() - t0,
        "model_metadata": {
            "model_id": MODEL_ID,
            "license": MODEL_LICENSE,
            "commit_hash": getattr(model.config, "_commit_hash", "unknown"),
            "dtype": str(dtype),
            "device": gpu_name,
            "vocab_size": vocab_size,
            "eos_token_ids": eos_ids,
            "max_new_tokens": MAX_NEW_TOKENS,
        },
        "backend_versions_and_licenses": {
            "xgrammar": {"version": importlib.metadata.version("xgrammar"), "license": "Apache-2.0"},
            "transformers": {"version": importlib.metadata.version("transformers"), "license": "Apache-2.0"},
            "torch": {"version": torch.__version__, "license": "BSD-3-Clause"},
            "tokenizers": {"version": importlib.metadata.version("tokenizers"), "license": "Apache-2.0"},
            "bfcl_upstream": {"commit": "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8", "license": "Apache-2.0"},
        },
        "source_and_input_hashes": {
            "grammar_utils_py": sha256_file(BASE / "grammar_utils.py"),
            "stage0_grammar_confidence_pilot_py": sha256_file(pathlib.Path(__file__)),
            "STAGE0_PROTOCOL_md": sha256_file(proto_p),
            "BFCL_PILOT_SPLIT_RECEIPT_json": sha256_file(split_rec_p),
            "STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT_json": sha256_file(alg_rec_p),
            "bfcl_stage0_pilot_dataset_json": sha256_file(pilot_data_p),
            "stage0_pilot_per_instance_jsonl": sha256_file(inc_path),
        },
        "max_algebra_identity_abs_err_observed": max_id_err_all,
        "power_diagnostic": {
            "pilot_n": N,
            "n_tool_family_clusters": len(set(clusters_all)),
            "G_compact_n_correct": n_cor_c,
            "G_compact_n_error": n_err_c,
            "approx_unpaired_auroc_se_at_0.5": se_auroc_approx,
            "note": "Small pilot (N=100, 70 tool-family clusters); underpowered for subtle AUROC differences (<0.08), informative for large scale/calibration/threshold-transfer shifts.",
        },
        "all_generated_cases_N100": all_gen_summary,
        "all_generated_cross_grammar_transfer_N100": all_gen_transfer,
        "fixed_path_paired_shared_forward": fixed_path_analysis,
    }

    sum_path = out_dir / "stage0_pilot_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n=== Stage-0 Pilot COMPLETE (PID={pid}, wall={summary['wall_time_s']:.1f}s, max_id_err={max_id_err_all:.2e}) ===", flush=True)
    print(f"Saved {sum_path} (sha256={sha256_file(sum_path)[:16]}...)", flush=True)


if __name__ == "__main__":
    main()
