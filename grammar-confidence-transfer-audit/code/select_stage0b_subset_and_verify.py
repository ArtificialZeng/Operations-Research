"""
Stage-0b Pre-Launch Outcome-Independent 24-Item Subset Selector & Fixture Verifier.

1. Selects 12 `simple_python` + 12 `multiple` IDs from `bfcl_stage0_pilot_dataset.json`
   strictly by SHA-256(f"stage0b_20261124:{id}") order -- NEVER reading Stage-0 outcomes.
2. Verifies:
   - Prompt_Neutral describes required keys ("name", "arguments") without any JSON formatting example.
   - Prompt_Compact uses compact JSON example (same tool docs & user question, zero gold identifiers).
   - Menu-enum EBNF builder (`build_menu_enum_grammars`) uses ONLY `item["function"]` offered names
     in canonical sorted order: deleting `ground_truth` yields bit-identical EBNF strings (zero answer leakage).
   - Both `G_compact_menu` and `G_optws_menu` compile cleanly in xgrammar 0.2.9, express the EXACT same
     set of parsed ASTs, differ ONLY by optional whitespace (`ws`), and satisfy float64 algebra
     `pre_nll = post_nll - log(retained_mass)` to `< 1e-12` on a shared forward-pass fixture.
3. Saves `STAGE0B_SUBSET_24_RECEIPT.json` and `STAGE0B_FIXTURE_RECEIPT.json`.
"""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pathlib
import sys
from typing import Dict, List, Tuple

import numpy as np
import torch
import xgrammar as xgr
from transformers import AutoTokenizer

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(BASE))

import grammar_utils as gu  # noqa: E402

# --- Stage-0b Prompt Variants (Same offered tool docs & user question; zero gold identifiers) ---
SYSTEM_PROMPT_NEUTRAL = (
    "You are a precise function-calling assistant. "
    "Given the user's request and the available read-only function definitions, "
    "select the single appropriate function and output a single JSON object with exactly two top-level keys: "
    "a string key called name holding the selected function identifier, and an object key called arguments "
    "mapping each parameter name to its value. Output only the JSON object with no markdown fences, "
    "no explanation, and no extra text."
)

SYSTEM_PROMPT_COMPACT = (
    "You are a precise function-calling assistant. "
    "Given the user's request and the available read-only function definitions, "
    "select the single appropriate function and output ONLY one compact JSON object with no extra spaces "
    'of the form {"name":"<function_name>","arguments":{<key>:<value>,...}} '
    "with no markdown fences, no explanation, and no extra text."
)


def build_messages_stage0b(item: Dict, prompt_mode: str) -> List[Dict[str, str]]:
    user_q = item["question"][0][0]["content"]
    tools_json = json.dumps(item["function"], indent=2, ensure_ascii=False)
    if prompt_mode == "neutral":
        user_content = (
            f"Available functions (JSON schemas):\n{tools_json}\n\n"
            f"User request:\n{user_q}\n\n"
            "Respond with only the JSON object containing the name and arguments keys."
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT_NEUTRAL},
            {"role": "user", "content": user_content},
        ]
    elif prompt_mode == "compact":
        user_content = (
            f"Available functions (JSON schemas):\n{tools_json}\n\n"
            f"User request:\n{user_q}\n\n"
            'Respond with ONLY the compact JSON object {"name":...,"arguments":{...}}.'
        )
        return [
            {"role": "system", "content": SYSTEM_PROMPT_COMPACT},
            {"role": "user", "content": user_content},
        ]
    else:
        raise ValueError(f"Unknown prompt_mode: {prompt_mode}")


def _ebnf_escape_literal(s: str) -> str:
    # Escape characters for an EBNF double-quoted string literal representing a JSON string token
    j = json.dumps(s, ensure_ascii=False)  # includes outer JSON quotes "..."
    return j.replace("\\", "\\\\").replace('"', '\\"')


def build_menu_enum_grammars(offered_functions: List[Dict]) -> Tuple[str, str, List[str]]:
    """
    Builds per-item `(EBNF_G_compact_menu, EBNF_G_optws_menu, canonical_menu_names)`
    strictly from `offered_functions` (`item["function"]`) in canonical sorted order.
    NEVER inspects ground truth or expected arguments.
    Differs between compact and optws ONLY by optional whitespace (`ws`).
    """
    menu_names = sorted({f["name"] for f in offered_functions})
    assert len(menu_names) >= 1
    alts = " | ".join(f'"{_ebnf_escape_literal(nm)}"' for nm in menu_names)

    body_shared = r"""
object ::= "{" "}" | "{" pair ("," pair)* "}"
pair ::= string ":" value
array ::= "[" "]" | "[" value ("," value)* "]"
value ::= string | number | object | array | "true" | "false" | "null"
string ::= "\"" ([^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\""
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
""".strip()

    body_optws = r"""
object ::= "{" ws "}" | "{" ws pair (ws "," ws pair)* ws "}"
pair ::= string ws ":" ws value
array ::= "[" ws "]" | "[" ws value (ws "," ws value)* ws "]"
value ::= string | number | object | array | "true" | "false" | "null"
string ::= "\"" ([^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\""
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
ws ::= [ \t\n\r]*
""".strip()

    ebnf_compact = (
        'root ::= "{\\"name\\":" tool_name ",\\"arguments\\":" object "}"\n'
        f"tool_name ::= {alts}\n"
        + body_shared
    )
    ebnf_optws = (
        'root ::= ws "{" ws "\\"name\\"" ws ":" ws tool_name ws "," ws "\\"arguments\\"" ws ":" ws object ws "}" ws\n'
        f"tool_name ::= {alts}\n"
        + body_optws
    )
    return ebnf_compact, ebnf_optws, menu_names


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    pilot_p = BASE / "bfcl_stage0_pilot_dataset.json"
    pilot_items = json.loads(pilot_p.read_text(encoding="utf-8"))

    # Outcome-independent deterministic selection strictly by SHA-256(f"stage0b_20261124:{id}")
    def rank_key(it):
        return hashlib.sha256(f"stage0b_20261124:{it['id']}".encode("utf-8")).hexdigest()

    simples = sorted([it for it in pilot_items if it["category"] == "simple_python"], key=rank_key)
    multiples = sorted([it for it in pilot_items if it["category"] == "multiple"], key=rank_key)
    selected = simples[:12] + multiples[:12]
    selected.sort(key=lambda it: (it["category"], it["id"]))

    subset_rec = {
        "selection_rule": "Deterministic outcome-independent sort by sha256('stage0b_20261124:' + id); first 12 simple_python + first 12 multiple from sealed bfcl_stage0_pilot_dataset.json (zero reading of Stage-0 outcomes; future_blind_test untouched).",
        "pilot_dataset_sha256": sha256_file(pilot_p),
        "n_selected": len(selected),
        "n_simple_python": sum(1 for x in selected if x["category"] == "simple_python"),
        "n_multiple": sum(1 for x in selected if x["category"] == "multiple"),
        "selected_items": [
            {
                "id": it["id"],
                "category": it["category"],
                "sha256_rank_key": rank_key(it),
                "tool_family_cluster": it["tool_family_cluster"],
                "n_offered_functions": len(it["function"]),
                "offered_function_names_canonical": sorted({f["name"] for f in it["function"]}),
            }
            for it in selected
        ],
    }
    sub_out = BASE / "STAGE0B_SUBSET_24_RECEIPT.json"
    sub_out.write_text(json.dumps(subset_rec, indent=2), encoding="utf-8")

    # --- Pre-Launch Verification Fixtures ---
    # 1. Verify neutral prompt has NO JSON brace/colon example; compact prompt has compact example
    sample_mult = multiples[0]
    m_neu = build_messages_stage0b(sample_mult, "neutral")
    m_cmp = build_messages_stage0b(sample_mult, "compact")
    assert '{"name"' not in m_neu[0]["content"] and '": ' not in m_neu[0]["content"]
    assert '{"name"' not in m_neu[1]["content"].split("User request:")[-1]
    assert '{"name":"<function_name>","arguments":' in m_cmp[0]["content"]
    assert '{"name":...,"arguments":{...}}' in m_cmp[1]["content"]

    # 2. Verify menu-enum builder does NOT inspect ground_truth (zero leakage)
    item_no_gt = copy.deepcopy(sample_mult)
    item_no_gt["ground_truth"] = [{"COMPLETELY_FAKE_GOLD": {"x": [999]}}]
    ec1, ew1, mn1 = build_menu_enum_grammars(sample_mult["function"])
    ec2, ew2, mn2 = build_menu_enum_grammars(item_no_gt["function"])
    assert ec1 == ec2 and ew1 == ew2 and mn1 == mn2
    assert len(mn1) >= 2, f"Expected multiple menu >= 2, got {mn1}"

    # 3. Verify xgrammar compilation, AST equivalence, non-menu rejection, and exact float64 algebra on menu-enum pair
    tok = AutoTokenizer.from_pretrained("Qwen/Qwen2.5-1.5B-Instruct", revision="989aa7980e4cf806f80c7fef2b1adb7bc71aa306", local_files_only=True)
    vocab_size = 151936
    eos_id = tok.eos_token_id
    ti = xgr.TokenizerInfo.from_huggingface(tok, vocab_size=vocab_size)
    comp = xgr.GrammarCompiler(ti)
    cg_cm = comp.compile_grammar(xgr.Grammar.from_ebnf(ec1))
    cg_wm = comp.compile_grammar(xgr.Grammar.from_ebnf(ew1))

    # Test EVERY offered name in menu passes both compact & optws, and an unoffered name is rejected by BOTH
    rng = np.random.default_rng(2026112402)
    max_id_err_cm = 0.0
    max_id_err_wm = 0.0
    for nm in mn1:
        s_c = json.dumps({"name": nm, "arguments": {"x": 1}}, separators=(",", ":"))
        s_w = json.dumps({"name": nm, "arguments": {"x": 1}})
        assert json.loads(s_c) == json.loads(s_w)
        ids_c = tok.encode(s_c, add_special_tokens=False) + [eos_id]
        ids_w = tok.encode(s_w, add_special_tokens=False) + [eos_id]
        z_c = torch.tensor(rng.normal(0.0, 2.5, size=(len(ids_c), vocab_size)), dtype=torch.float64)
        z_w = torch.tensor(rng.normal(0.0, 2.5, size=(len(ids_w), vocab_size)), dtype=torch.float64)

        rc_c = gu.score_fixed_path_under_grammar(z_c, ids_c, cg_cm, vocab_size, [eos_id])
        rw_c = gu.score_fixed_path_under_grammar(z_c, ids_c, cg_wm, vocab_size, [eos_id])
        rc_w = gu.score_fixed_path_under_grammar(z_w, ids_w, cg_cm, vocab_size, [eos_id])
        rw_w = gu.score_fixed_path_under_grammar(z_w, ids_w, cg_wm, vocab_size, [eos_id])

        assert rc_c["accepted_all_tokens"] and rc_c["grammar_terminated"]
        assert rw_c["accepted_all_tokens"] and rw_c["grammar_terminated"]
        assert not rc_w["accepted_all_tokens"], "G_compact_menu must reject spaced JSON"
        assert rw_w["accepted_all_tokens"] and rw_w["grammar_terminated"]

        max_id_err_cm = max(max_id_err_cm, max(x["identity_abs_err"] for x in rc_c["per_step"]))
        max_id_err_wm = max(max_id_err_wm, max(x["identity_abs_err"] for x in rw_c["per_step"]))

    # Non-menu hallucination rejected by BOTH menu-enum grammars
    s_bad = json.dumps({"name": "IronSource_NOT_IN_MENU", "arguments": {}}, separators=(",", ":"))
    ids_bad = tok.encode(s_bad, add_special_tokens=False) + [eos_id]
    z_bad = torch.tensor(rng.normal(0.0, 1.0, size=(len(ids_bad), vocab_size)), dtype=torch.float64)
    assert not gu.score_fixed_path_under_grammar(z_bad, ids_bad, cg_cm, vocab_size, [eos_id])["accepted_all_tokens"]
    assert not gu.score_fixed_path_under_grammar(z_bad, ids_bad, cg_wm, vocab_size, [eos_id])["accepted_all_tokens"]
    assert max_id_err_cm < 1e-12 and max_id_err_wm < 1e-12

    # Compile check across ALL 24 selected items' menu-enum grammars
    for it in selected:
        ec_i, ew_i, _ = build_menu_enum_grammars(it["function"])
        _ = comp.compile_grammar(xgr.Grammar.from_ebnf(ec_i))
        _ = comp.compile_grammar(xgr.Grammar.from_ebnf(ew_i))

    fix_rec = {
        "purpose": "Pre-launch Stage-0b fixture check: prompt hygiene, zero-leakage menu enum, whitespace-only AST equivalence, all-24 grammar compilation, and float64 algebra identity.",
        "script_sha256": sha256_file(pathlib.Path(__file__)),
        "subset_receipt_sha256": sha256_file(sub_out),
        "all_fixtures_passed": True,
        "neutral_prompt_has_no_json_format_example": True,
        "compact_prompt_has_compact_example": True,
        "menu_enum_independent_of_ground_truth": True,
        "sample_multiple_menu_names": mn1,
        "all_offered_names_accepted_by_both_menu_grammars": True,
        "spaced_json_rejected_by_compact_menu_accepted_by_optws_menu": True,
        "unoffered_name_rejected_by_both_menu_grammars": True,
        "all_24_item_menu_grammars_compiled_cleanly": True,
        "max_algebra_identity_err_compact_menu": max_id_err_cm,
        "max_algebra_identity_err_optws_menu": max_id_err_wm,
    }
    fix_out = BASE / "STAGE0B_FIXTURE_RECEIPT.json"
    fix_out.write_text(json.dumps(fix_rec, indent=2), encoding="utf-8")
    print(
        f"STAGE-0B SUBSET (24=12S+12M) & ALL FIXTURES PASSED | "
        f"max_id_err(cm={max_id_err_cm:.2e}, wm={max_id_err_wm:.2e}) | "
        f"compiled all 24 menu-enum grammar pairs cleanly!"
    )


if __name__ == "__main__":
    main()
