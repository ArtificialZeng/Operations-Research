"""
Stage-0c Pre-Launch Fixture Verifier: Fixed, Typed Parsed-Call Canonicalization,
Canonical AST Equivalence across ALL 48 Sealed Stage-0b `neutral_menu` Outputs,
and Exact Stage-0b Prompt Neutrality Verification.

Does NOT touch `bfcl_future_blind_test_ids_sealed.json` (only verifies its SHA-256 unchanged),
does NOT load or run any LLM, and does NOT inspect gold labels inside canonicalization.
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import sys
from typing import Any, Dict

from transformers import AutoTokenizer

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(BASE))

import grammar_utils as gu  # noqa: E402
import select_stage0b_subset_and_verify as s0b  # noqa: E402

EXPECTED_SEALED = {
    "bfcl_stage0_pilot_dataset.json": "191e8e8c8c9c00f0f7dacd0a98b6f592b02e878e444da0016e99f1e31c1cd446",
    "bfcl_future_blind_test_ids_sealed.json": "64268a3c286eaacd45f51a470cb619ff3027019e27f7f5632b7d1f7a56139e0a",
    "grammar_utils.py": "d063e5e347bf2928f1c6f22becafd67611f711842960276e1399359dab966423",
    "select_stage0b_subset_and_verify.py": "0a0d9b95cedc580b8fdff00ac44277b6e0409c411dcc0dc4138a1fed168defa1",
    "STAGE0B_SUBSET_24_RECEIPT.json": "65bcba4a28ee39bf3ff7f4173e773c110c076a136f663cda7dcde57f928cbf46",
    "STAGE0B_FIXTURE_RECEIPT.json": "04ee945695311cc738406e5a769556b14ed0bbc7e8212b85ac86cdc36d456d65",
    "stage0b_outputs/stage0b_per_instance.jsonl": "724e921058677ee9b32d5a2e1fc74083af9d6dd29717c32bd6a9bc33ce489c9e",
    "stage0b_outputs/stage0b_summary.json": "9036772bb510bac388dc123dadaef89a1cf037a40ba0806ecef0cbc5b352812d",
}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def sort_arg_map_recursively(obj: Any) -> Any:
    """
    Recursively sorts dict keys in lexicographic order while preserving:
      - exact list element order (recursively sorting any dicts inside list elements)
      - exact Python/JSON scalar types (bool, int, float, str, None)
    """
    if isinstance(obj, dict):
        return {k: sort_arg_map_recursively(obj[k]) for k in sorted(obj.keys())}
    if isinstance(obj, list):
        return [sort_arg_map_recursively(el) for el in obj]
    return obj


def canonicalize_parsed_call(parsed_call: Dict[str, Any]) -> str:
    """
    Fixed, typed parsed-call canonicalization:
      - Ordinary JSON serialization (`json.dumps`), standard spaces `separators=(", ", ": ")`
      - Fixed root key order: `"name"` first, `"arguments"` second (`sort_keys=False`)
      - Recursively sorted argument-map keys inside `"arguments"`
      - Preserves exact function name, scalar value types (bool/int/float/str/None), list order, and semantics
      - Zero hindsight or gold labels.
    """
    assert isinstance(parsed_call, dict), f"Expected dict parsed_call, got {type(parsed_call).__name__}"
    assert set(parsed_call.keys()) == {"name", "arguments"}, f"Unexpected root keys: {list(parsed_call.keys())}"
    assert isinstance(parsed_call["name"], str), "name must be str"
    assert isinstance(parsed_call["arguments"], dict), "arguments must be dict"
    canon_obj = {
        "name": parsed_call["name"],
        "arguments": sort_arg_map_recursively(parsed_call["arguments"]),
    }
    return json.dumps(canon_obj, ensure_ascii=False, separators=(", ", ": "), sort_keys=False)


def _exact_typed_equal(a: Any, b: Any) -> bool:
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a.keys()) == set(b.keys()) and all(_exact_typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(_exact_typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def main():
    # 1. Verify all sealed Stage-0 / Stage-0b / blind-test SHA-256 hashes
    for rel, exp in EXPECTED_SEALED.items():
        got = sha256_file(BASE / rel)
        assert got == exp, f"SHA-256 mismatch on {rel}: expected {exp}, got {got}"

    # 2. Synthetic unit fixtures for canonicalization
    # (a) Fixed root key order ("name" before "arguments") even when reversed
    syn_in = {
        "arguments": {
            "z_nested": {"b": 1.0, "a": 1, "c": True, "d": None, "e": "1"},
            "a_list": [3, 1, {"k2": "y", "k1": "x"}, 2],
        },
        "name": "demo.tool",
    }
    syn_out = canonicalize_parsed_call(syn_in)
    expected_syn = (
        '{"name": "demo.tool", "arguments": {'
        '"a_list": [3, 1, {"k1": "x", "k2": "y"}, 2], '
        '"z_nested": {"a": 1, "b": 1.0, "c": true, "d": null, "e": "1"}}}'
    )
    assert syn_out == expected_syn, f"Synthetic canonical mismatch:\n  got: {syn_out}\n  exp: {expected_syn}"
    rt = json.loads(syn_out)
    assert list(rt.keys()) == ["name", "arguments"], "Root key order not fixed!"
    assert _exact_typed_equal(rt, syn_in), "Round-trip scalar/type/list equality violated!"

    # (b) Verify Ye26 SMT span extraction parses canonical JSON cleanly with Qwen2.5 tokenizer
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct", revision="989aa7980e4cf806f80c7fef2b1adb7bc71aa306", local_files_only=True)
    syn_ids = tok.encode(syn_out, add_special_tokens=False) + [tok.eos_token_id]
    syn_smt = gu.extract_smt_token_indices(tok, syn_ids)
    assert syn_smt["parsed_ok"] is True and len(syn_smt["smt_ye26_indices"]) > 0

    # 3. Verify canonical AST equivalence and Stage-0b neutrality across ALL 48 sealed `neutral_menu` outputs
    pilot_by_id = {
        it["id"]: it
        for it in json.loads((BASE / "bfcl_stage0_pilot_dataset.json").read_text(encoding="utf-8"))
    }
    s0b_recs = [
        json.loads(l)
        for l in (BASE / "stage0b_outputs" / "stage0b_per_instance.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert len(s0b_recs) == 24

    n_pairs_canon_equal = 0
    non_equal_pair_details = []
    neutral_prompt_verified_all_24 = True

    for rec in s0b_recs:
        iid = rec["id"]
        item = pilot_by_id[iid]

        # Verify exact Stage-0b format-neutral prompt hygiene (zero JSON formatting example, zero gold leakage)
        msgs_neu = s0b.build_messages_stage0b(item, "neutral")
        assert '{"name"' not in msgs_neu[0]["content"] and '": ' not in msgs_neu[0]["content"]
        assert '{"name"' not in msgs_neu[1]["content"].split("User request:")[-1]

        canon_by_arm = {}
        for ak in ("neutral_menu__G_compact_menu", "neutral_menu__G_optws_menu"):
            arm = rec["arms"][ak]
            orig_ev = arm["eval"]
            parsed_raw = json.loads(arm["text"])
            assert _exact_typed_equal(parsed_raw, orig_ev["parsed_call"])
            canon_text = canonicalize_parsed_call(parsed_raw)
            canon_rt = json.loads(canon_text)
            assert list(canon_rt.keys()) == ["name", "arguments"]
            assert _exact_typed_equal(canon_rt, parsed_raw), f"Typed round-trip failed on {iid} {ak}"

            # Official BFCL inert AST equivalence check
            ev_canon = gu.evaluate_bfcl_inert_ast(item, canon_text)
            assert ev_canon["json_valid"] == orig_ev["json_valid"] is True
            assert ev_canon["call_schema_valid"] == orig_ev["call_schema_valid"] is True
            assert ev_canon["ast_correct"] == orig_ev["ast_correct"], f"AST verdict changed on {iid} {ak}!"
            assert ev_canon["error_type"] == orig_ev["error_type"], f"error_type changed on {iid} {ak}!"
            assert _exact_typed_equal(ev_canon["parsed_call"], orig_ev["parsed_call"])

            # Verify Ye26 SMT span parser accepts canonical tokens
            c_ids = tok.encode(canon_text, add_special_tokens=False) + [tok.eos_token_id]
            c_smt = gu.extract_smt_token_indices(tok, c_ids)
            assert c_smt["parsed_ok"] is True and len(c_smt["smt_ye26_indices"]) > 0

            canon_by_arm[ak] = canon_text

        c_str = canon_by_arm["neutral_menu__G_compact_menu"]
        w_str = canon_by_arm["neutral_menu__G_optws_menu"]
        if c_str == w_str:
            n_pairs_canon_equal += 1
        else:
            non_equal_pair_details.append({
                "id": iid,
                "category": rec["category"],
                "tool_family_cluster": rec["tool_family_cluster"],
                "compact_ast_correct": rec["arms"]["neutral_menu__G_compact_menu"]["eval"]["ast_correct"],
                "optws_ast_correct": rec["arms"]["neutral_menu__G_optws_menu"]["eval"]["ast_correct"],
                "canonical_compact": c_str,
                "canonical_optws": w_str,
            })

    receipt = {
        "purpose": "Pre-launch Stage-0c fixture gate: fixed typed JSON canonicalization, exact AST equivalence on all 48 sealed neutral_menu outputs, Ye26 SMT span compatibility, and Stage-0b prompt neutrality.",
        "script_sha256": sha256_file(pathlib.Path(__file__)),
        "all_fixtures_passed": True,
        "sealed_hashes_verified": EXPECTED_SEALED,
        "unit_fixture_fixed_root_order_sorted_args_list_order_types_passed": True,
        "neutral_prompt_hygiene_verified_all_24": neutral_prompt_verified_all_24,
        "n_sealed_outputs_ast_verified": 48,
        "all_48_canonical_ast_verdicts_identical_to_sealed_stage0b": True,
        "all_48_canonical_smt_spans_parsed_ok": True,
        "n_items_total": 24,
        "n_pairs_identical_canonical_string_deduplicated": n_pairs_canon_equal,
        "n_pairs_distinct_canonical_strings": len(non_equal_pair_details),
        "n_unique_canonical_strings_to_score": n_pairs_canon_equal + 2 * len(non_equal_pair_details),
        "non_equal_canonical_pairs": non_equal_pair_details,
        "epistemic_note": "Identical-serialization score equality on deduplicated pairs is by construction and is NOT empirical novelty.",
    }
    out_p = BASE / "STAGE0C_CANONICAL_FIXTURE_RECEIPT.json"
    out_p.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"STAGE-0C CANONICAL FIXTURE PASSED (48/48 exact AST match) | "
        f"equal_canon_pairs={n_pairs_canon_equal}/24, distinct_pairs={len(non_equal_pair_details)}/24, "
        f"unique_forward_passes={receipt['n_unique_canonical_strings_to_score']} (vs 48 undeduplicated)"
    )
    for d in non_equal_pair_details:
        print(f"  DIFF {d['id']} (C_ok={d['compact_ast_correct']}, W_ok={d['optws_ast_correct']}):")
        print(f"    C: {d['canonical_compact']!r}")
        print(f"    W: {d['canonical_optws']!r}")


if __name__ == "__main__":
    main()
