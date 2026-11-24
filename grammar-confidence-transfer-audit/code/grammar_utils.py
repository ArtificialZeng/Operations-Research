"""
Core auditable utilities for the Offline Single-Turn Function-Call Confidence Transfer Study
(`grammar_confidence_transfer_20261124`).

Includes:
  1. Two syntax-only JSON call EBNF grammars (`G_compact` vs `G_optws`):
     - Identical parsed JSON call space `{"name": <string>, "arguments": <object>}`.
     - ZERO access to tool names, schemas, expected arguments, tool IDs, or ground truth.
     - Exact language inclusion: L(G_compact) ⊂ L(G_optws), so every compact token path
       accepted by G_compact is guaranteed accepted by G_optws.
  2. Exact float64 single-forward-pass mask normalization & algebra:
       pre_nll[t] = post_nll[t] - log_retained_mass[t]
     alongside Parvatikar (2026) pre/post entropy and Reddy et al. (2603.03305) feasible mass.
  3. Exact zero-execution JSON AST lexer for Ye et al. (TMLR 2026) G-NLL_SMT
     (Semantically Meaningful Tokens: function name + argument keys + argument values;
      plus value-only SMT sensitivity subset).
  4. Official BFCL inert AST evaluation wrapper (`bfcl_eval.eval_checker.ast_eval.ast_checker`)
     with ZERO code execution or tool invocation.
"""
from __future__ import annotations

import json
import math
import os
import pathlib
import sys
import types
from typing import Dict, List, Optional, Tuple

import numpy as np
import torch
import xgrammar as xgr

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
BFCL_ROOT = BASE / "bfcl_upstream" / "berkeley-function-call-leaderboard"

# --- Two Syntax-Only JSON Call EBNF Grammars (xgrammar GBNF/EBNF format) ---
# Both express the EXACT SAME parsed call schema {"name": <string>, "arguments": <object>}
# with ZERO access to tool names, argument schemas, expected arguments, tool IDs, or outputs.

EBNF_G_COMPACT = r"""
root ::= "{\"name\":" string ",\"arguments\":" object "}"
object ::= "{" "}" | "{" pair ("," pair)* "}"
pair ::= string ":" value
array ::= "[" "]" | "[" value ("," value)* "]"
value ::= string | number | object | array | "true" | "false" | "null"
string ::= "\"" ([^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\""
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
""".strip()

EBNF_G_OPTWS = r"""
root ::= ws "{" ws "\"name\"" ws ":" ws string ws "," ws "\"arguments\"" ws ":" ws object ws "}" ws
object ::= "{" ws "}" | "{" ws pair (ws "," ws pair)* ws "}"
pair ::= string ws ":" ws value
array ::= "[" ws "]" | "[" ws value (ws "," ws value)* ws "]"
value ::= string | number | object | array | "true" | "false" | "null"
string ::= "\"" ([^"\\\x00-\x1f] | "\\" (["\\/bfnrt] | "u" [0-9a-fA-F]{4}))* "\""
number ::= "-"? ("0" | [1-9] [0-9]*) ("." [0-9]+)? ([eE] [+-]? [0-9]+)?
ws ::= [ \t\n\r]*
""".strip()


# --- Neutral, Identical Single-Turn Prompt Builder (identical for Unconstrained, G_compact, G_optws) ---
SYSTEM_PROMPT = (
    "You are a precise function-calling assistant. "
    "Given the user's request and the available read-only function definitions, "
    "select the single appropriate function and output ONLY one JSON object of the form "
    '{"name": "<function_name>", "arguments": {<key>: <value>, ...}} '
    "with no markdown fences, no explanation, and no extra text."
)


def build_messages(item: Dict) -> List[Dict[str, str]]:
    user_q = item["question"][0][0]["content"]
    tools_json = json.dumps(item["function"], indent=2, ensure_ascii=False)
    user_content = (
        f"Available functions (JSON schemas):\n{tools_json}\n\n"
        f"User request:\n{user_q}\n\n"
        'Respond with ONLY the JSON object {"name": ..., "arguments": {...}}.'
    )
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_content},
    ]


# --- Exact xgrammar Bitmask Unpacker ---
def bitmask_to_bool(bitmask_row: torch.Tensor, vocab_size: int) -> torch.Tensor:
    """Unpacks int32 xgrammar bitmask row into exact bool tensor of shape [vocab_size]."""
    arr = bitmask_row.cpu().numpy().astype(np.uint32)
    bits = ((arr[:, None] >> np.arange(32, dtype=np.uint32)[None, :]) & 1).reshape(-1)
    return torch.from_numpy(bits[:vocab_size].astype(bool))


def step_mask_metrics_from_logits(
    logits_1d: torch.Tensor,
    allowed_bool: Optional[torch.Tensor],
    chosen_token_id: int,
) -> Dict[str, float]:
    """
    Computes exact float64 pre-mask and post-mask log-probabilities, retained feasible mass,
    and pre/post entropies from ONE unmasked logit vector `logits_1d` [V].
    Exact identity: pre_nll = post_nll - log_retained_mass.
    """
    z = logits_1d.detach().to(dtype=torch.float64, device="cpu")
    log_p_pre = torch.log_softmax(z, dim=-1)
    p_pre = torch.exp(log_p_pre)
    pre_nll = float(-log_p_pre[chosen_token_id].item())
    # H_pre = -sum p log p (avoid 0 * -inf via where)
    h_pre = float(-(torch.where(p_pre > 0, p_pre * log_p_pre, torch.zeros_like(p_pre))).sum().item())

    if allowed_bool is None:
        return {
            "pre_nll": pre_nll,
            "post_nll": pre_nll,
            "log_retained_mass": 0.0,
            "retained_mass": 1.0,
            "h_pre": h_pre,
            "h_post": h_pre,
            "n_allowed_tokens": int(z.numel()),
            "identity_abs_err": 0.0,
            "token_allowed": True,
        }

    mask = allowed_bool.to(dtype=torch.bool, device="cpu")
    token_allowed = bool(mask[chosen_token_id].item())
    n_allowed = int(mask.sum().item())
    assert n_allowed > 0, "Empty grammar mask!"

    log_z = float(torch.logsumexp(log_p_pre[mask], dim=-1).item())
    # Clamp tiny float64 rounding above 0.0 (e.g. +1e-16 when all tokens allowed)
    if log_z > 0.0 and log_z < 1e-12:
        log_z = 0.0
    retained_mass = float(math.exp(log_z))

    z_masked = z.masked_fill(~mask, float("-inf"))
    log_p_post = torch.log_softmax(z_masked, dim=-1)
    p_post = torch.exp(log_p_post)
    h_post = float(-(torch.where(p_post > 0, p_post * log_p_post, torch.zeros_like(p_post))).sum().item())

    if token_allowed:
        post_nll = float(-log_p_post[chosen_token_id].item())
        identity_err = abs(pre_nll - (post_nll - log_z))
    else:
        post_nll = float("inf")
        identity_err = float("nan")

    return {
        "pre_nll": pre_nll,
        "post_nll": post_nll,
        "log_retained_mass": log_z,
        "retained_mass": retained_mass,
        "h_pre": h_pre,
        "h_post": h_post,
        "n_allowed_tokens": n_allowed,
        "identity_abs_err": identity_err,
        "token_allowed": token_allowed,
    }


def score_fixed_path_under_grammar(
    step_logits: torch.Tensor,  # [T, V] unmasked logits from ONE forward pass
    token_ids: List[int],       # length T (excluding EOS unless appended; see include_eos)
    compiled_grammar: xgr.CompiledGrammar,
    vocab_size: int,
    eos_token_ids: List[int],
) -> Dict:
    """
    Replays `token_ids` through `GrammarMatcher(compiled_grammar)` and scores every step
    against the exact same `step_logits` tensor in float64.
    """
    matcher = xgr.GrammarMatcher(compiled_grammar)
    bitmask = xgr.allocate_token_bitmask(1, vocab_size)
    per_step = []
    accepted_all = True

    for t, tok in enumerate(token_ids):
        matcher.fill_next_token_bitmask(bitmask)
        allowed = bitmask_to_bool(bitmask[0], vocab_size)
        m = step_mask_metrics_from_logits(step_logits[t], allowed, tok)
        per_step.append(m)
        if not m["token_allowed"]:
            accepted_all = False
            break
        ok = matcher.accept_token(tok)
        if not ok:
            accepted_all = False
            break

    terminated = bool(accepted_all and matcher.is_terminated())
    # Note: if token_ids does not end with an EOS token, matcher may already be terminated after '}'
    return {
        "accepted_all_tokens": accepted_all,
        "grammar_terminated": terminated,
        "n_steps_scored": len(per_step),
        "per_step": per_step,
    }


# --- Zero-Execution Recursive-Descent JSON Span Lexer for Ye et al. (TMLR 2026) G-NLL_SMT ---
class _JsonSpanParser:
    """Parses a JSON call object {"name": "...", "arguments": {...}} and extracts exact
    character spans [start, end) for:
      - func_name_spans: string content inside quotes of "name" value
      - arg_key_spans: string content inside quotes of keys inside "arguments"
      - arg_val_spans: primitive values inside "arguments" (string content inside quotes, numbers, bools, null)
    """

    def __init__(self, text: str):
        self.s = text
        self.n = len(text)
        self.i = 0
        self.func_name_spans: List[Tuple[int, int]] = []
        self.arg_key_spans: List[Tuple[int, int]] = []
        self.arg_val_spans: List[Tuple[int, int]] = []

    def _ws(self):
        while self.i < self.n and self.s[self.i] in " \t\n\r":
            self.i += 1

    def _parse_string_span(self) -> Tuple[str, Tuple[int, int]]:
        assert self.i < self.n and self.s[self.i] == '"'
        start_quote = self.i
        self.i += 1
        inner_start = self.i
        while self.i < self.n:
            ch = self.s[self.i]
            if ch == "\\":
                self.i += 2
            elif ch == '"':
                inner_end = self.i
                self.i += 1
                raw = self.s[start_quote : self.i]
                return json.loads(raw), (inner_start, inner_end)
            else:
                self.i += 1
        raise ValueError("Unterminated JSON string")

    def _parse_value(self, in_args: bool, is_name_val: bool = False):
        self._ws()
        if self.i >= self.n:
            raise ValueError("Unexpected EOF in JSON value")
        ch = self.s[self.i]
        if ch == '"':
            val, span = self._parse_string_span()
            if is_name_val:
                self.func_name_spans.append(span)
            elif in_args:
                self.arg_val_spans.append(span)
            return val
        if ch == "{":
            return self._parse_object(in_args=in_args, is_root=False)
        if ch == "[":
            return self._parse_array(in_args=in_args)
        # number, true, false, null
        start = self.i
        while self.i < self.n and self.s[self.i] not in " \t\n\r,}]":
            self.i += 1
        end = self.i
        val = json.loads(self.s[start:end])
        if in_args:
            self.arg_val_spans.append((start, end))
        return val

    def _parse_array(self, in_args: bool):
        assert self.s[self.i] == "["
        self.i += 1
        self._ws()
        out = []
        if self.i < self.n and self.s[self.i] == "]":
            self.i += 1
            return out
        while True:
            out.append(self._parse_value(in_args=in_args))
            self._ws()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                continue
            assert self.i < self.n and self.s[self.i] == "]"
            self.i += 1
            return out

    def _parse_object(self, in_args: bool, is_root: bool):
        assert self.s[self.i] == "{"
        self.i += 1
        self._ws()
        out = {}
        if self.i < self.n and self.s[self.i] == "}":
            self.i += 1
            return out
        while True:
            self._ws()
            key, kspan = self._parse_string_span()
            if in_args:
                self.arg_key_spans.append(kspan)
            self._ws()
            assert self.i < self.n and self.s[self.i] == ":"
            self.i += 1
            if is_root and key == "name":
                val = self._parse_value(in_args=False, is_name_val=True)
            elif is_root and key == "arguments":
                val = self._parse_value(in_args=True, is_name_val=False)
            else:
                val = self._parse_value(in_args=in_args, is_name_val=False)
            out[key] = val
            self._ws()
            if self.i < self.n and self.s[self.i] == ",":
                self.i += 1
                continue
            assert self.i < self.n and self.s[self.i] == "}"
            self.i += 1
            return out

    def parse_root(self):
        self._ws()
        obj = self._parse_object(in_args=False, is_root=True)
        self._ws()
        if self.i != self.n:
            raise ValueError("Trailing characters after root JSON object")
        return obj


def extract_smt_token_indices(tokenizer, token_ids: List[int]) -> Dict:
    """
    Maps exact JSON SMT character spans to token indices using incremental decoded prefix lengths.
    Returns:
      - parsed_ok: bool
      - parsed_obj: dict or None
      - smt_ye26_indices: sorted token indices overlapping (func_name U arg_keys U arg_values)
      - smt_val_indices: sorted token indices overlapping (func_name U arg_values)
      - syntax_indices: complement of smt_ye26_indices over content tokens (excluding EOS)
    """
    # Strip trailing EOS tokens for JSON parsing while remembering token positions
    eos_set = set()
    if tokenizer.eos_token_id is not None:
        if isinstance(tokenizer.eos_token_id, list):
            eos_set.update(tokenizer.eos_token_id)
        else:
            eos_set.add(tokenizer.eos_token_id)
    content_ids = [t for t in token_ids if t not in eos_set]

    # Exact incremental character span of each token via cumulative decode
    token_char_spans: List[Tuple[int, int]] = []
    prev_text = ""
    for k in range(len(content_ids)):
        cur_text = tokenizer.decode(content_ids[: k + 1], skip_special_tokens=False)
        token_char_spans.append((len(prev_text), len(cur_text)))
        prev_text = cur_text
    full_text = prev_text

    try:
        parser = _JsonSpanParser(full_text)
        obj = parser.parse_root()
        if not (isinstance(obj, dict) and isinstance(obj.get("name"), str) and isinstance(obj.get("arguments"), dict)):
            return {"parsed_ok": False, "parsed_obj": None, "text": full_text, "smt_ye26_indices": [], "smt_val_indices": [], "syntax_indices": list(range(len(content_ids)))}
    except Exception:
        return {"parsed_ok": False, "parsed_obj": None, "text": full_text, "smt_ye26_indices": [], "smt_val_indices": [], "syntax_indices": list(range(len(content_ids)))}

    def overlaps(a: Tuple[int, int], b: Tuple[int, int]) -> bool:
        return max(a[0], b[0]) < min(a[1], b[1])

    ye26_spans = parser.func_name_spans + parser.arg_key_spans + parser.arg_val_spans
    val_spans = parser.func_name_spans + parser.arg_val_spans

    smt_ye26 = [idx for idx, sp in enumerate(token_char_spans) if any(overlaps(sp, s) for s in ye26_spans)]
    smt_val = [idx for idx, sp in enumerate(token_char_spans) if any(overlaps(sp, s) for s in val_spans)]
    smt_set = set(smt_ye26)
    syntax_idx = [idx for idx in range(len(content_ids)) if idx not in smt_set]

    return {
        "parsed_ok": True,
        "parsed_obj": obj,
        "text": full_text,
        "n_content_tokens": len(content_ids),
        "func_name_spans": parser.func_name_spans,
        "arg_key_spans": parser.arg_key_spans,
        "arg_val_spans": parser.arg_val_spans,
        "smt_ye26_indices": smt_ye26,
        "smt_val_indices": smt_val,
        "syntax_indices": syntax_idx,
    }


# --- Official BFCL Inert AST Evaluation Wrapper (ZERO execution!) ---
_BFCL_AST_FN = None
_BFCL_LANG_PY = None


def _load_official_bfcl_ast_checker():
    global _BFCL_AST_FN, _BFCL_LANG_PY
    if _BFCL_AST_FN is not None:
        return _BFCL_AST_FN, _BFCL_LANG_PY

    # Import official bfcl_eval.eval_checker.ast_eval.ast_checker with minimal stub for MODEL_CONFIG_MAPPING
    # (never executes any tool; purely inert Python AST/value comparison)
    if str(BFCL_ROOT) not in sys.path:
        sys.path.insert(0, str(BFCL_ROOT))

    # Inject a lightweight stub for bfcl_eval.constants.model_config BEFORE importing ast_checker
    # so official unmodified ast_checker.py loads cleanly with zero paid-API SDK imports (anthropic/openai).
    if "bfcl_eval.constants.model_config" not in sys.modules:
        mc_stub = types.ModuleType("bfcl_eval.constants.model_config")
        mc_stub.MODEL_CONFIG_MAPPING = {"local-inert-eval": types.SimpleNamespace(underscore_to_dot=False)}
        sys.modules["bfcl_eval.constants.model_config"] = mc_stub

    from bfcl_eval.constants.enums import Language  # type: ignore
    from bfcl_eval.eval_checker.ast_eval.ast_checker import ast_checker  # type: ignore

    _BFCL_AST_FN = ast_checker
    _BFCL_LANG_PY = Language.PYTHON
    return _BFCL_AST_FN, _BFCL_LANG_PY


def evaluate_bfcl_inert_ast(item: Dict, raw_text: str) -> Dict:
    """
    Inertly parses raw JSON text -> {"name": fn, "arguments": args} -> [{fn: args}]
    and evaluates with official BFCL `ast_checker`. ZERO execution.
    """
    ast_fn, lang_py = _load_official_bfcl_ast_checker()
    try:
        obj = json.loads(raw_text)
    except Exception as ex:
        return {
            "json_valid": False,
            "call_schema_valid": False,
            "ast_correct": False,
            "error_type": "json_parse_error",
            "error": [str(ex)],
            "parsed_call": None,
        }

    if not (isinstance(obj, dict) and set(obj.keys()) == {"name", "arguments"} and isinstance(obj["name"], str) and isinstance(obj["arguments"], dict)):
        return {
            "json_valid": True,
            "call_schema_valid": False,
            "ast_correct": False,
            "error_type": "call_envelope_schema_error",
            "error": [f"Expected dict with exact keys name(str) & arguments(dict); got {type(obj).__name__}"],
            "parsed_call": None,
        }

    model_output_bfcl = [{obj["name"]: obj["arguments"]}]
    res = ast_fn(
        func_description=item["function"],
        model_output=model_output_bfcl,
        possible_answer=item["ground_truth"],
        language=lang_py,
        test_category=item["category"],
        model_name="local-inert-eval",
    )
    return {
        "json_valid": True,
        "call_schema_valid": True,
        "ast_correct": bool(res["valid"]),
        "error_type": None if res["valid"] else res.get("error_type", "ast_error"),
        "error": [] if res["valid"] else res.get("error", []),
        "parsed_call": obj,
    }
