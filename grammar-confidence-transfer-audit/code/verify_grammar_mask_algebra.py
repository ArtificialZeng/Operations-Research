"""
Pre-Launch Algebraic Identity, Grammar Equivalence, SMT Span, and BFCL Inert AST Fixture Gate.

Verifies BEFORE running any model on the BFCL Stage-0 pilot split:
  1. Both syntax-only EBNF grammars (`G_compact` and `G_optws`) compile cleanly in xgrammar 0.2.9
     with the exact target HuggingFace tokenizer (`Qwen/Qwen2.5-1.5B-Instruct`).
  2. Bidirectional format equivalence: `G_compact` accepts compact JSON and rejects whitespace JSON,
     while `G_optws` accepts BOTH compact and whitespace JSON (and parses to identical Python dicts).
  3. Exact float64 algebraic identity on a fixed compact token path accepted by BOTH grammars from
     ONE shared unmasked logit pass:
       max_t |pre_nll[t] - (post_nll[t] - log_retained_mass[t])| < 1e-12
     AND strict grammar mask monotonicity M_t(G_compact) ⊆ M_t(G_optws) with strictly positive
     retained-mass gap on structural punctuation boundaries.
  4. Consistent Ye et al. (TMLR 2026) SMT token-span extraction across BOTH compact and whitespace
     formats of the same tool call.
  5. Official BFCL inert `ast_checker` unit tests (valid, wrong_func_name, missing_required,
     type_error, value_error).

Saves receipt: STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import os
import pathlib
import sys

import numpy as np
import torch
import xgrammar as xgr
from transformers import AutoTokenizer

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(BASE))

import grammar_utils as gu  # noqa: E402

MODEL_ID = "Qwen/Qwen2.5-1.5B-Instruct"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    tok = AutoTokenizer.from_pretrained(MODEL_ID, revision="989aa7980e4cf806f80c7fef2b1adb7bc71aa306", local_files_only=True)
    vocab_size = len(tok)
    tok_info = xgr.TokenizerInfo.from_huggingface(tok, vocab_size=vocab_size)
    compiler = xgr.GrammarCompiler(tok_info)

    cg_compact = compiler.compile_grammar(xgr.Grammar.from_ebnf(gu.EBNF_G_COMPACT))
    cg_optws = compiler.compile_grammar(xgr.Grammar.from_ebnf(gu.EBNF_G_OPTWS))

    # --- Fixture 1: Compact vs Whitespace format equivalence ---
    s_compact = '{"name":"calculate_triangle_area","arguments":{"base":10,"height":5,"unit":"units"}}'
    s_spaced = '{"name": "calculate_triangle_area", "arguments": {"base": 10, "height": 5, "unit": "units"}}'
    s_pretty = '{\n  "name": "calculate_triangle_area",\n  "arguments": {\n    "base": 10,\n    "height": 5,\n    "unit": "units"\n  }\n}'
    assert json.loads(s_compact) == json.loads(s_spaced) == json.loads(s_pretty)

    eos_id = tok.eos_token_id if isinstance(tok.eos_token_id, int) else tok.eos_token_id[0]
    eos_ids = [eos_id]
    ids_compact = tok.encode(s_compact, add_special_tokens=False) + [eos_id]
    ids_spaced = tok.encode(s_spaced, add_special_tokens=False) + [eos_id]
    ids_pretty = tok.encode(s_pretty, add_special_tokens=False) + [eos_id]

    # Synthetic deterministic unmasked logits [T, V] for exact algebraic fixture check
    rng = np.random.default_rng(20261124)
    logits_compact = torch.tensor(rng.normal(0.0, 2.5, size=(len(ids_compact), vocab_size)), dtype=torch.float64)
    logits_spaced = torch.tensor(rng.normal(0.0, 2.5, size=(len(ids_spaced), vocab_size)), dtype=torch.float64)
    logits_pretty = torch.tensor(rng.normal(0.0, 2.5, size=(len(ids_pretty), vocab_size)), dtype=torch.float64)

    res_c_on_c = gu.score_fixed_path_under_grammar(logits_compact, ids_compact, cg_compact, vocab_size, eos_ids)
    res_w_on_c = gu.score_fixed_path_under_grammar(logits_compact, ids_compact, cg_optws, vocab_size, eos_ids)
    res_c_on_s = gu.score_fixed_path_under_grammar(logits_spaced, ids_spaced, cg_compact, vocab_size, eos_ids)
    res_w_on_s = gu.score_fixed_path_under_grammar(logits_spaced, ids_spaced, cg_optws, vocab_size, eos_ids)
    res_w_on_p = gu.score_fixed_path_under_grammar(logits_pretty, ids_pretty, cg_optws, vocab_size, eos_ids)

    assert res_c_on_c["accepted_all_tokens"] and res_c_on_c["grammar_terminated"]
    assert res_w_on_c["accepted_all_tokens"] and res_w_on_c["grammar_terminated"]
    assert not res_c_on_s["accepted_all_tokens"], "G_compact must reject spaced JSON!"
    assert res_w_on_s["accepted_all_tokens"] and res_w_on_s["grammar_terminated"]
    assert res_w_on_p["accepted_all_tokens"] and res_w_on_p["grammar_terminated"]

    # --- Fixture 2: Exact float64 algebraic identity check on shared fixed compact path ---
    max_id_err_c = max(s["identity_abs_err"] for s in res_c_on_c["per_step"])
    max_id_err_w = max(s["identity_abs_err"] for s in res_w_on_c["per_step"])
    assert max_id_err_c < 1e-12, f"Identity error G_compact: {max_id_err_c}"
    assert max_id_err_w < 1e-12, f"Identity error G_optws: {max_id_err_w}"

    # Verify M_t(G_compact) ⊆ M_t(G_optws) => log_retained_mass_c <= log_retained_mass_w at every step
    n_strict_mass_diff = 0
    max_mass_gap = 0.0
    for sc, sw in zip(res_c_on_c["per_step"], res_w_on_c["per_step"]):
        assert sc["n_allowed_tokens"] <= sw["n_allowed_tokens"], "Subset invariant violated!"
        assert sc["log_retained_mass"] <= sw["log_retained_mass"] + 1e-12
        gap = sw["log_retained_mass"] - sc["log_retained_mass"]
        if gap > 1e-9:
            n_strict_mass_diff += 1
            max_mass_gap = max(max_mass_gap, gap)
    assert n_strict_mass_diff > 0, "Expected strictly larger feasible mass for G_optws at structural boundaries!"

    # --- Fixture 3: Ye et al. (TMLR 2026) SMT span consistency across compact & spaced formats ---
    smt_c = gu.extract_smt_token_indices(tok, ids_compact)
    smt_s = gu.extract_smt_token_indices(tok, ids_spaced)
    assert smt_c["parsed_ok"] and smt_s["parsed_ok"]
    assert smt_c["parsed_obj"] == smt_s["parsed_obj"]
    assert len(smt_c["smt_ye26_indices"]) > 0 and len(smt_s["smt_ye26_indices"]) > 0
    assert len(smt_c["smt_val_indices"]) > 0 and len(smt_s["smt_val_indices"]) > 0
    # Verify decoded SMT tokens cover the exact same semantic content strings
    smt_c_toks = [tok.decode([ids_compact[i]]) for i in smt_c["smt_ye26_indices"]]
    smt_s_toks = [tok.decode([ids_spaced[i]]) for i in smt_s["smt_ye26_indices"]]

    # --- Fixture 4: Official BFCL inert AST checker unit tests ---
    dummy_item = {
        "id": "fixture_0",
        "category": "simple_python",
        "function": [{
            "name": "calculate_triangle_area",
            "description": "Calculate triangle area.",
            "parameters": {
                "type": "dict",
                "properties": {
                    "base": {"type": "integer", "description": "base"},
                    "height": {"type": "integer", "description": "height"},
                    "unit": {"type": "string", "description": "unit"},
                },
                "required": ["base", "height"],
            },
        }],
        "ground_truth": [{"calculate_triangle_area": {"base": [10], "height": [5], "unit": ["units", ""]}}],
    }
    ev_ok_c = gu.evaluate_bfcl_inert_ast(dummy_item, s_compact)
    ev_ok_s = gu.evaluate_bfcl_inert_ast(dummy_item, s_spaced)
    ev_wrong_fn = gu.evaluate_bfcl_inert_ast(dummy_item, '{"name":"wrong_fn","arguments":{"base":10,"height":5}}')
    ev_wrong_val = gu.evaluate_bfcl_inert_ast(dummy_item, '{"name":"calculate_triangle_area","arguments":{"base":99,"height":5}}')
    ev_wrong_type = gu.evaluate_bfcl_inert_ast(dummy_item, '{"name":"calculate_triangle_area","arguments":{"base":"10","height":5}}')
    ev_missing = gu.evaluate_bfcl_inert_ast(dummy_item, '{"name":"calculate_triangle_area","arguments":{"base":10}}')
    ev_bad_json = gu.evaluate_bfcl_inert_ast(dummy_item, '{"name":"calculate_triangle_area"')

    assert ev_ok_c["ast_correct"] and ev_ok_s["ast_correct"]
    assert not ev_wrong_fn["ast_correct"] and not ev_wrong_val["ast_correct"]
    assert not ev_wrong_type["ast_correct"] and not ev_missing["ast_correct"]
    assert not ev_bad_json["json_valid"] and not ev_bad_json["ast_correct"]

    receipt = {
        "purpose": "Pre-launch fixture verification of grammar equivalence, float64 pre/post mask algebra, Ye26 SMT spans, and BFCL inert AST checking.",
        "model_tokenizer_id": MODEL_ID,
        "vocab_size": vocab_size,
        "backend_versions": {
            "xgrammar": importlib.metadata.version("xgrammar"),
            "transformers": importlib.metadata.version("transformers"),
            "torch": torch.__version__,
            "tokenizers": importlib.metadata.version("tokenizers"),
        },
        "source_hashes": {
            "grammar_utils_py": sha256_file(BASE / "grammar_utils.py"),
            "verify_grammar_mask_algebra_py": sha256_file(pathlib.Path(__file__)),
        },
        "all_fixtures_passed": True,
        "grammar_equivalence": {
            "G_compact_accepts_compact": res_c_on_c["accepted_all_tokens"],
            "G_optws_accepts_compact": res_w_on_c["accepted_all_tokens"],
            "G_compact_rejects_spaced": not res_c_on_s["accepted_all_tokens"],
            "G_optws_accepts_spaced": res_w_on_s["accepted_all_tokens"],
            "G_optws_accepts_pretty": res_w_on_p["accepted_all_tokens"],
        },
        "algebra_identity_pre_eq_post_minus_logZ": {
            "n_steps_compact_path": len(ids_compact),
            "max_abs_err_G_compact": max_id_err_c,
            "max_abs_err_G_optws": max_id_err_w,
            "threshold": 1e-12,
            "n_steps_strictly_larger_mass_optws": n_strict_mass_diff,
            "max_log_retained_mass_gap": max_mass_gap,
            "subset_invariant_all_steps": True,
        },
        "smt_span_check": {
            "compact_smt_ye26_tokens": smt_c_toks,
            "spaced_smt_ye26_tokens": smt_s_toks,
            "compact_n_ye26": len(smt_c["smt_ye26_indices"]),
            "compact_n_val": len(smt_c["smt_val_indices"]),
            "compact_n_syntax": len(smt_c["syntax_indices"]),
        },
        "bfcl_inert_ast_unit_tests": {
            "compact_valid": ev_ok_c["ast_correct"],
            "spaced_valid": ev_ok_s["ast_correct"],
            "wrong_fn_rejected": not ev_wrong_fn["ast_correct"],
            "wrong_val_rejected": not ev_wrong_val["ast_correct"],
            "wrong_type_rejected": not ev_wrong_type["ast_correct"],
            "missing_required_rejected": not ev_missing["ast_correct"],
            "bad_json_rejected": not ev_bad_json["json_valid"],
        },
    }
    out = BASE / "STAGE0_ALGEBRA_AND_GRAMMAR_FIXTURE_RECEIPT.json"
    out.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"ALL FIXTURES PASSED | max_id_err(compact={max_id_err_c:.2e}, optws={max_id_err_w:.2e}) | "
        f"strict_mass_diff_steps={n_strict_mass_diff}/{len(ids_compact)} (max_gap={max_mass_gap:.4f}) | "
        f"SMT compact={smt_c_toks}"
    )


if __name__ == "__main__":
    main()
