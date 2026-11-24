"""
Stage-0 Bounded Randomization-Support Screen Runner (N = 40 Non-Overlapping Matched Cases).

Locked Protocol: `STAGE0_SCREEN_PROTOCOL.md`
Runs TWO distinct pinned auth-free local model families on local hardware (zero paid APIs,
zero secret discovery, zero simulated scores):
  - Family 1: Qwen/Qwen2.5-1.5B-Instruct (rev 989aa7980e4cf806f80c7fef2b1adb7bc71aa306)
  - Family 2: ibm-granite/granite-3.1-2b-instruct (rev bbc2aed595bd38bd770263dc3ab831db9794441d)

Conditions per model family (all greedy deterministic do_sample=False, raw outputs & SHA-256 saved):
  1. Direct (`direct`): 40 admissible + 40 matched-total illegal (80 calls).
  2. Neutral Reorder + ID-Renaming Control (`direct_reordered`): 20 balanced cases (7 RTV + 13 BDM)
     x 2 (admissible + illegal) = 40 calls.
  3. Automatic Structured Unit/Block/Quota Extraction + Deterministic Verifier (`extract_verify`):
     40 extraction calls on original artifacts -> deterministic Python verification of admissible & illegal.
  4. Gold-Schema Deterministic Verifier (`gold_verify`): exact oracle check asserting 100.0% accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import gc
import hashlib
import json
import os
import pathlib
import re
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple


ROOT = pathlib.Path(__file__).resolve().parent
BENCH_PATH = ROOT / "STAGE0_MATCHED_40_CASES.json"
OUT_DIR = ROOT / "stage0_screen_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


RTV_METHODS_EXCERPT = (
    "Green and Vavreck (2008) implemented a cluster-randomized experimental design in assessing the "
    "effects of a voter mobilization treatment in the 2004 U.S. Presidential election. The clusters in "
    "this design are geographic areas served by a single cable television system (small cable systems "
    "whose reach is limited to a single zip code). Eighty-five cable systems were available for "
    "randomization and were assigned to treatment after stratification on previous turnout levels in "
    "presidential elections. Each cable system was matched with one or sometimes two other cable systems "
    "in the same state, yielding 40 strata. Then within each strata, cable systems were randomly assigned "
    "to treatment and control conditions. Strata 3, 8 and 25 have two control cable systems and 1 treated "
    "system each, while strata 6 and 20 have two treated cable systems and one control system. The "
    "remaining 35 strata have 1 treated cable system and 1 control system. In this way there are "
    "38 + 4 = 42 treated systems, spanning 40 experiment strata."
)

BDM_METHODS_EXCERPT = (
    "Abaluck et al. (2022, Science), 'The Impact of Community Masking on COVID-19: A Cluster-Randomized "
    "Trial in Bangladesh'. Our intervention was conducted at the village level across rural Bangladesh, "
    "rolling out over 7 waves. We enrolled multiple villages in each division, district, and upazila; "
    "however, in a given union, we only enrolled one unique village, so villages are referred to as "
    "`union` in the replication code and assigned de-identified random codes. Prior to randomization, "
    "villages were grouped into matched pairs within districts based on baseline characteristics; within "
    "each matched pair, one village was randomly assigned to the mask-promotion intervention "
    "(`treatment = 1`) and the other to control (`treatment = 0`). Sub-interventions such as surgical "
    "vs. cloth masks (`surgical_pair`, `cloth_pair`) were also tracked across pairs."
)


MODEL_SPECS = [
    {
        "family_key": "qwen25_1p5b",
        "model_id": "Qwen/Qwen2.5-1.5B-Instruct",
        "revision": "989aa7980e4cf806f80c7fef2b1adb7bc71aa306",
    },
    {
        "family_key": "granite31_2b",
        "model_id": "ibm-granite/granite-3.1-2b-instruct",
        "revision": "bbc2aed595bd38bd770263dc3ab831db9794441d",
    },
]


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def sha256_file(p: pathlib.Path) -> str:
    return sha256_bytes(p.read_bytes())


def sha256_text(s: str) -> str:
    return sha256_bytes(s.encode("utf-8"))


def format_table_tsv(rows: Sequence[Dict[str, Any]]) -> str:
    if not rows:
        return "(empty)"
    cols = list(rows[0].keys())
    lines = ["\t".join(cols)]
    for r in rows:
        lines.append("\t".join(str(r[c]) for c in cols))
    return "\n".join(lines)


def get_case_tables_and_text(case: Dict[str, Any], reordered: bool = False) -> Tuple[str, str, List[Dict[str, Any]], str, List[Dict[str, Any]], str]:
    """Returns (methods_excerpt, t1_name, t1_rows, t2_name, t2_rows, treat_col)."""
    if case["trial"] == "RockTheVote_2008":
        if reordered:
            t1 = case["neutral_reorder_control"]["table_metadata_rows"]
            t2 = case["neutral_reorder_control"]["table_outcome_rows"]
        else:
            t1 = case["table_metadata_rows"]
            t2 = case["table_outcome_rows"]
        return RTV_METHODS_EXCERPT, "Table 1 (market_metadata)", t1, "Table 2 (turnout_and_observed_assignment)", t2, "treated"
    else:
        if reordered:
            t1 = case["neutral_reorder_control"]["table_union_reg_rows"]
            t2 = case["neutral_reorder_control"]["table_blood_base_rows"]
        else:
            t1 = case["table_union_reg_rows"]
            t2 = case["table_blood_base_rows"]
        return BDM_METHODS_EXCERPT, "Table 1 (union_reg_sample)", t1, "Table 2 (union_baseline_blood_stats)", t2, "treatment"


def build_direct_prompt(case: Dict[str, Any], candidate_assignment: Dict[str, int], reordered: bool = False) -> str:
    methods, t1_name, t1_rows, t2_name, t2_rows, _ = get_case_tables_and_text(case, reordered=reordered)
    cand_lines = ", ".join(f"{k}: {v}" for k, v in candidate_assignment.items())
    return (
        "You are auditing the statistical validity of a randomization-inference reassignment from a real field experiment.\n\n"
        f"METHODS EXCERPT:\n{methods}\n\n"
        f"{t1_name}:\n{format_table_tsv(t1_rows)}\n\n"
        f"{t2_name}:\n{format_table_tsv(t2_rows)}\n\n"
        f"CANDIDATE REASSIGNMENT (same total treated count = {case['total_treated']} out of {case['n_units']} units):\n"
        f"{{{cand_lines}}}\n\n"
        "QUESTION:\n"
        "Could this exact candidate reassignment occur under the trial's original randomization design (respecting the true randomized unit, block/stratum/pair structure, and allowed treated count per block)?\n"
        "Respond with ONLY a single JSON object using exact keys:\n"
        '{"verdict": "ADMISSIBLE" or "ILLEGAL", "reason": "<brief 1-sentence reason>"}'
    )


def build_extraction_prompt(case: Dict[str, Any]) -> str:
    methods, t1_name, t1_rows, t2_name, t2_rows, _ = get_case_tables_and_text(case, reordered=False)
    return (
        "You are extracting the exact randomization-design schema from a real field experiment's methods excerpt and joined replication tables.\n\n"
        f"METHODS EXCERPT:\n{methods}\n\n"
        f"{t1_name}:\n{format_table_tsv(t1_rows)}\n\n"
        f"{t2_name}:\n{format_table_tsv(t2_rows)}\n\n"
        "TASK:\n"
        "Identify the EXACT column names from the tables above that define the randomization support:\n"
        "- unit_col: exact column name uniquely identifying each randomized unit (cluster/market/village).\n"
        "- block_col: exact column name defining the randomization block/stratum/pair within which treatment was assigned, or null if completely unblocked.\n"
        "- quota_rule: one of \"fixed_per_block\", \"observed_per_block\", or \"total_only\".\n"
        "- block_quotas: JSON object mapping each block value (as string) to its exact integer number of treated units, or null if total_only.\n\n"
        "Respond with ONLY a single JSON object using exact keys:\n"
        '{"unit_col": "<col>", "block_col": "<col or null>", "quota_rule": "fixed_per_block|observed_per_block|total_only", "block_quotas": {"<block_val>": <int>}}'
    )


def extract_json_object(raw_text: str) -> Optional[Dict[str, Any]]:
    txt = raw_text.strip()
    # Strip markdown fences if present
    m_fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", txt, re.S | re.I)
    candidates = []
    if m_fence:
        candidates.append(m_fence.group(1))
    # Also scan balanced braces
    start = txt.find("{")
    if start != -1:
        depth = 0
        for idx in range(start, len(txt)):
            if txt[idx] == "{":
                depth += 1
            elif txt[idx] == "}":
                depth -= 1
                if depth == 0:
                    candidates.append(txt[start : idx + 1])
                    break
    for cand in candidates:
        try:
            obj = json.loads(cand)
            if isinstance(obj, dict):
                return obj
        except Exception:
            continue
    return None


def parse_direct_verdict(raw_text: str) -> Tuple[str, str]:
    obj = extract_json_object(raw_text)
    if obj is not None:
        v = str(obj.get("verdict", "")).strip().upper()
        reason = str(obj.get("reason", "")).strip()
        if v in ("ADMISSIBLE", "VALID", "TRUE", "YES"):
            return "ADMISSIBLE", reason
        if v in ("ILLEGAL", "INVALID", "INADMISSIBLE", "FALSE", "NO"):
            return "ILLEGAL", reason
    # Fallback regex ONLY if exact JSON key wasn't valid JSON
    m = re.search(r'"verdict"\s*:\s*"?(ADMISSIBLE|ILLEGAL|INADMISSIBLE|VALID|INVALID)"?', raw_text, re.I)
    if m:
        tok = m.group(1).upper()
        return ("ADMISSIBLE" if tok in ("ADMISSIBLE", "VALID") else "ILLEGAL"), "regex_parsed"
    return "PARSE_FAIL", "unparseable_output"


def _normalize_block_key(val: Any) -> str:
    s = str(val).strip()
    # Normalize "1.0" -> "1" and "P17"/"S3" -> "17"/"3" when comparing against integer table values
    if re.fullmatch(r"\d+\.0", s):
        s = s[:-2]
    return s


def verify_from_extracted_schema(
    case: Dict[str, Any],
    schema: Optional[Dict[str, Any]],
    candidate_assignment: Dict[str, int],
) -> Tuple[str, str, Dict[str, Any]]:
    """Deterministic verifier consuming ONLY the model's extracted schema + raw tables.
    Returns (verdict: ADMISSIBLE|ILLEGAL|SCHEMA_ERROR, detail_code, diag_dict)."""
    _, _, t1_rows, _, t2_rows, treat_col = get_case_tables_and_text(case, reordered=False)
    if schema is None:
        return "SCHEMA_ERROR", "unparseable_schema_json", {
            "extracted_unit_col": None,
            "extracted_block_col": None,
            "extracted_quota_rule": None,
            "unit_col_ok": False,
            "block_col_ok": False,
            "quotas_ok": False,
        }

    unit_col = schema.get("unit_col")
    block_col = schema.get("block_col")
    quota_rule = str(schema.get("quota_rule", "observed_per_block") or "observed_per_block").strip().lower()
    raw_quotas = schema.get("block_quotas")

    t1_cols = set(t1_rows[0].keys())
    t2_cols = set(t2_rows[0].keys())
    gold_unit_col = case["gold_schema"]["unit_col"]
    gold_block_col = case["gold_schema"]["block_col"]
    unit_col_ok = (unit_col == gold_unit_col)
    block_col_ok = (block_col == gold_block_col)

    diag: Dict[str, Any] = {
        "extracted_unit_col": unit_col,
        "extracted_block_col": block_col,
        "extracted_quota_rule": quota_rule,
        "unit_col_ok": unit_col_ok,
        "block_col_ok": block_col_ok,
        "quotas_ok": False,
    }

    if not isinstance(unit_col, str) or unit_col not in t1_cols or unit_col not in t2_cols:
        return "SCHEMA_ERROR", f"invalid_unit_col:{unit_col}", diag

    # Join Table 1 and Table 2 on extracted unit_col
    t1_by_u: Dict[str, Dict[str, Any]] = {}
    for r in t1_rows:
        uk = _normalize_block_key(r[unit_col])
        if uk in t1_by_u:
            return "SCHEMA_ERROR", f"nonunique_unit_col_t1:{unit_col}", diag
        t1_by_u[uk] = r

    t2_by_u: Dict[str, Dict[str, Any]] = {}
    for r in t2_rows:
        uk = _normalize_block_key(r[unit_col])
        if uk in t2_by_u:
            return "SCHEMA_ERROR", f"nonunique_unit_col_t2:{unit_col}", diag
        t2_by_u[uk] = r

    if set(t1_by_u.keys()) != set(t2_by_u.keys()):
        return "SCHEMA_ERROR", "table_join_key_mismatch", diag

    cand_norm = {_normalize_block_key(k): int(v) for k, v in candidate_assignment.items()}
    if set(cand_norm.keys()) != set(t1_by_u.keys()):
        return "SCHEMA_ERROR", "candidate_unit_id_mismatch", diag

    joined: Dict[str, Dict[str, Any]] = {}
    for uk in t1_by_u:
        merged = dict(t1_by_u[uk])
        merged.update(t2_by_u[uk])
        joined[uk] = merged

    all_cols = set(next(iter(joined.values())).keys())
    obs_total = sum(int(joined[uk][treat_col]) for uk in joined)

    # Case 1: Model claims unblocked / total_only design
    if block_col is None or str(block_col).strip().lower() in ("", "none", "null") or quota_rule == "total_only":
        cand_total = sum(cand_norm.values())
        v = "ADMISSIBLE" if cand_total == obs_total else "ILLEGAL"
        return v, f"unblocked_total_only_check({cand_total}=={obs_total})", diag

    # Case 2: Model names a block_col
    if not isinstance(block_col, str) or block_col not in all_cols:
        return "SCHEMA_ERROR", f"missing_block_col:{block_col}", diag

    # Group units by extracted block_col
    groups: Dict[str, List[str]] = {}
    for uk, row in joined.items():
        bk = _normalize_block_key(row[block_col])
        groups.setdefault(bk, []).append(uk)

    # Determine target quotas strictly from extracted schema
    target_quotas: Dict[str, int] = {}
    if quota_rule == "fixed_per_block" and isinstance(raw_quotas, dict) and len(raw_quotas) > 0:
        # Normalize keys (allow "S1"/"P17" or raw "1"/"17")
        norm_q: Dict[str, int] = {}
        for rk, rv in raw_quotas.items():
            try:
                ival = int(round(float(rv)))
            except Exception:
                continue
            rk_clean = _normalize_block_key(rk)
            norm_q[rk_clean] = ival
            m_num = re.fullmatch(r"[A-Za-z_]+(\d+)", rk_clean)
            if m_num:
                norm_q[m_num.group(1)] = ival
        missing = [b for b in groups if b not in norm_q]
        if missing:
            # If model provided a single constant quota or partial dict that fails to cover extracted blocks -> schema error
            return "SCHEMA_ERROR", f"incomplete_block_quotas_missing:{missing[:3]}", diag
        target_quotas = {b: norm_q[b] for b in groups}
    else:
        # observed_per_block (or empty block_quotas with valid block_col)
        target_quotas = {b: sum(int(joined[uk][treat_col]) for uk in uks) for b, uks in groups.items()}

    # Check if extracted quotas match gold quotas (diagnostic only, never used to alter verdict!)
    gold_q_norm = {re.sub(r"^[SP]", "", k): int(v) for k, v in case["gold_schema"]["block_quotas"].items()}
    diag["quotas_ok"] = bool(unit_col_ok and block_col_ok and target_quotas == gold_q_norm)

    # Deterministic block-quota verification
    bad = []
    for b in sorted(groups.keys()):
        got_t = sum(cand_norm[uk] for uk in groups[b])
        if got_t != target_quotas[b]:
            bad.append(f"{b}:{got_t}!={target_quotas[b]}")
    if bad:
        return "ILLEGAL", "extracted_block_violation(" + ",".join(bad) + ")", diag
    return "ADMISSIBLE", "extracted_block_satisfied", diag


def verify_gold_oracle_100pct(cases: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Asserts that the exact same deterministic verifier achieves 100.0% accuracy given gold schemas."""
    pos_ok = 0
    neg_ok = 0
    for c in cases:
        gs = c["gold_schema"]
        gold_schema = {
            "unit_col": gs["unit_col"],
            "block_col": gs["block_col"],
            "quota_rule": "fixed_per_block",
            "block_quotas": gs["block_quotas"],
        }
        vp, dp, diagp = verify_from_extracted_schema(c, gold_schema, c["positive_admissible"]["assignment"])
        vn, dn, diagn = verify_from_extracted_schema(c, gold_schema, c["matched_illegal"]["assignment"])
        assert vp == "ADMISSIBLE" and diagp["quotas_ok"], f"Gold positive failed on {c['case_id']}: {vp} {dp}"
        assert vn == "ILLEGAL" and diagn["quotas_ok"], f"Gold illegal failed on {c['case_id']}: {vn} {dn}"
        pos_ok += 1
        neg_ok += 1
    return {"gold_pos_accepted": pos_ok, "gold_neg_rejected": neg_ok, "gold_false_acceptances": 0, "gold_paired_accuracy": 1.0}


def run_generation(model, tokenizer, prompt: str, max_new_tokens: int = 180) -> Tuple[str, float]:
    import torch

    msgs = [{"role": "user", "content": prompt}]
    txt = tokenizer.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True)
    inp = tokenizer(txt, return_tensors="pt").to(model.device)
    t0 = time.perf_counter()
    with torch.no_grad():
        out = model.generate(
            **inp,
            max_new_tokens=max_new_tokens,
            do_sample=False,
            pad_token_id=tokenizer.eos_token_id,
        )
    dt = time.perf_counter() - t0
    ans = tokenizer.decode(out[0][inp["input_ids"].shape[1] :], skip_special_tokens=True)
    return ans, dt


def score_family(
    spec: Dict[str, str],
    cases: List[Dict[str, Any]],
    reorder_case_ids: set[str],
) -> Dict[str, Any]:
    import torch
    import transformers

    fkey = spec["family_key"]
    mid = spec["model_id"]
    rev = spec["revision"]
    print(f"\n=== LOADING MODEL FAMILY: {fkey} ({mid} @ {rev[:12]}) ===", flush=True)
    t_load0 = time.perf_counter()
    tok = transformers.AutoTokenizer.from_pretrained(mid, revision=rev, local_files_only=True)
    mdl = transformers.AutoModelForCausalLM.from_pretrained(
        mid,
        revision=rev,
        local_files_only=True,
        dtype=torch.bfloat16,
        device_map="cuda",
    )
    mdl.eval()
    load_s = time.perf_counter() - t_load0
    print(f"Loaded {fkey} in {load_s:.2f}s | VRAM={torch.cuda.memory_allocated()/1e9:.2f}GB", flush=True)

    raw_records: List[Dict[str, Any]] = []
    per_case_summary: List[Dict[str, Any]] = []
    t_run0 = time.perf_counter()

    for idx, c in enumerate(cases, start=1):
        cid = c["case_id"]
        # 1. Direct admissible
        p_pos = build_direct_prompt(c, c["positive_admissible"]["assignment"], reordered=False)
        raw_pos, dt_pos = run_generation(mdl, tok, p_pos, max_new_tokens=140)
        v_pos, r_pos = parse_direct_verdict(raw_pos)

        # 2. Direct matched-total illegal
        p_neg = build_direct_prompt(c, c["matched_illegal"]["assignment"], reordered=False)
        raw_neg, dt_neg = run_generation(mdl, tok, p_neg, max_new_tokens=140)
        v_neg, r_neg = parse_direct_verdict(raw_neg)

        # 3. Neutral reorder + ID-renaming control (on 20 pre-locked balanced cases)
        reord_info = None
        if cid in reorder_case_ids:
            p_rpos = build_direct_prompt(c, c["neutral_reorder_control"]["positive_admissible"]["assignment"], reordered=True)
            raw_rpos, dt_rpos = run_generation(mdl, tok, p_rpos, max_new_tokens=140)
            v_rpos, r_rpos = parse_direct_verdict(raw_rpos)

            p_rneg = build_direct_prompt(c, c["neutral_reorder_control"]["matched_illegal"]["assignment"], reordered=True)
            raw_rneg, dt_rneg = run_generation(mdl, tok, p_rneg, max_new_tokens=140)
            v_rneg, r_rneg = parse_direct_verdict(raw_rneg)

            reord_info = {
                "pos_verdict": v_rpos,
                "neg_verdict": v_rneg,
                "pos_flip": (v_rpos != v_pos),
                "neg_flip": (v_rneg != v_neg),
                "raw_pos_sha256": sha256_text(raw_rpos),
                "raw_neg_sha256": sha256_text(raw_rneg),
                "elapsed_s": round(dt_rpos + dt_rneg, 3),
            }
            raw_records.extend([
                {"family": fkey, "case_id": cid, "trial": c["trial"], "cond": "direct_reord_pos", "prompt_sha256": sha256_text(p_rpos), "raw_response": raw_rpos, "raw_sha256": sha256_text(raw_rpos), "parsed_verdict": v_rpos, "elapsed_s": round(dt_rpos, 3)},
                {"family": fkey, "case_id": cid, "trial": c["trial"], "cond": "direct_reord_neg", "prompt_sha256": sha256_text(p_rneg), "raw_response": raw_rneg, "raw_sha256": sha256_text(raw_rneg), "parsed_verdict": v_rneg, "elapsed_s": round(dt_rneg, 3)},
            ])

        # 4. Structured extraction + deterministic verifier
        p_ext = build_extraction_prompt(c)
        raw_ext, dt_ext = run_generation(mdl, tok, p_ext, max_new_tokens=200)
        ext_schema = extract_json_object(raw_ext)
        ev_pos, ev_pos_code, ev_diag = verify_from_extracted_schema(c, ext_schema, c["positive_admissible"]["assignment"])
        ev_neg, ev_neg_code, _ = verify_from_extracted_schema(c, ext_schema, c["matched_illegal"]["assignment"])

        raw_records.extend([
            {"family": fkey, "case_id": cid, "trial": c["trial"], "cond": "direct_pos", "prompt_sha256": sha256_text(p_pos), "raw_response": raw_pos, "raw_sha256": sha256_text(raw_pos), "parsed_verdict": v_pos, "elapsed_s": round(dt_pos, 3)},
            {"family": fkey, "case_id": cid, "trial": c["trial"], "cond": "direct_neg", "prompt_sha256": sha256_text(p_neg), "raw_response": raw_neg, "raw_sha256": sha256_text(raw_neg), "parsed_verdict": v_neg, "elapsed_s": round(dt_neg, 3)},
            {"family": fkey, "case_id": cid, "trial": c["trial"], "cond": "extract_schema", "prompt_sha256": sha256_text(p_ext), "raw_response": raw_ext, "raw_sha256": sha256_text(raw_ext), "parsed_schema": ext_schema, "ev_pos": ev_pos, "ev_neg": ev_neg, "ev_pos_code": ev_pos_code, "ev_neg_code": ev_neg_code, "elapsed_s": round(dt_ext, 3)},
        ])

        case_row = {
            "case_id": cid,
            "trial": c["trial"],
            "direct_pos": v_pos,
            "direct_neg": v_neg,
            "direct_false_accept": (v_neg == "ADMISSIBLE"),
            "direct_valid_accept": (v_pos == "ADMISSIBLE"),
            "direct_paired_exact": (v_pos == "ADMISSIBLE" and v_neg == "ILLEGAL"),
            "direct_parse_fail": (v_pos == "PARSE_FAIL" or v_neg == "PARSE_FAIL"),
            "reordered": reord_info,
            "extract_schema": ext_schema,
            "ev_pos": ev_pos,
            "ev_neg": ev_neg,
            "ev_pos_code": ev_pos_code,
            "ev_neg_code": ev_neg_code,
            "ev_false_accept": (ev_neg == "ADMISSIBLE"),
            "ev_valid_accept": (ev_pos == "ADMISSIBLE"),
            "ev_paired_exact": (ev_pos == "ADMISSIBLE" and ev_neg == "ILLEGAL"),
            "ev_schema_error": (not ev_diag["quotas_ok"]) or (ev_pos == "SCHEMA_ERROR") or (ev_neg == "SCHEMA_ERROR"),
            "ev_diag": ev_diag,
        }
        per_case_summary.append(case_row)
        print(
            f"[{fkey}] [{idx:02d}/40] {cid} ({c['trial'][:4]}) "
            f"DIR: pos={v_pos[:3]} neg={v_neg[:3]} | "
            f"EV: pos={ev_pos[:3]} neg={ev_neg[:3]} (u={ev_diag['extracted_unit_col']},b={ev_diag['extracted_block_col']}) "
            f"{'REORD_FLIP=' + str(int(reord_info['pos_flip']) + int(reord_info['neg_flip'])) if reord_info else ''}",
            flush=True,
        )

    run_s = time.perf_counter() - t_run0

    # Save raw responses JSONL
    raw_path = OUT_DIR / f"raw_responses_{fkey}.jsonl"
    with raw_path.open("w", encoding="utf-8") as f:
        for rr in raw_records:
            f.write(json.dumps(rr) + "\n")
    raw_sha = sha256_file(raw_path)

    # Free GPU cleanly before next family
    del mdl
    del tok
    gc.collect()
    torch.cuda.empty_cache()

    def summarize_subset(sub: List[Dict[str, Any]]) -> Dict[str, Any]:
        n = len(sub)
        reord_sub = [x for x in sub if x["reordered"] is not None]
        n_reord_items = 2 * len(reord_sub)
        flips = sum(int(x["reordered"]["pos_flip"]) + int(x["reordered"]["neg_flip"]) for x in reord_sub)
        pos_flips = sum(int(x["reordered"]["pos_flip"]) for x in reord_sub)
        neg_flips = sum(int(x["reordered"]["neg_flip"]) for x in reord_sub)
        return {
            "n_cases": n,
            "direct_false_accept_count": sum(1 for x in sub if x["direct_false_accept"]),
            "direct_false_accept_rate": round(sum(1 for x in sub if x["direct_false_accept"]) / n, 4),
            "direct_valid_accept_count": sum(1 for x in sub if x["direct_valid_accept"]),
            "direct_valid_accept_coverage": round(sum(1 for x in sub if x["direct_valid_accept"]) / n, 4),
            "direct_paired_exact_count": sum(1 for x in sub if x["direct_paired_exact"]),
            "direct_paired_exact_accuracy": round(sum(1 for x in sub if x["direct_paired_exact"]) / n, 4),
            "direct_parse_fail_cases": sum(1 for x in sub if x["direct_parse_fail"]),
            "reord_items_checked": n_reord_items,
            "reord_total_flips": flips,
            "reord_pos_flips": pos_flips,
            "reord_neg_flips": neg_flips,
            "ev_false_accept_count": sum(1 for x in sub if x["ev_false_accept"]),
            "ev_false_accept_rate": round(sum(1 for x in sub if x["ev_false_accept"]) / n, 4),
            "ev_valid_accept_count": sum(1 for x in sub if x["ev_valid_accept"]),
            "ev_valid_accept_coverage": round(sum(1 for x in sub if x["ev_valid_accept"]) / n, 4),
            "ev_paired_exact_count": sum(1 for x in sub if x["ev_paired_exact"]),
            "ev_paired_exact_accuracy": round(sum(1 for x in sub if x["ev_paired_exact"]) / n, 4),
            "ev_schema_error_count": sum(1 for x in sub if x["ev_schema_error"]),
            "ev_extracted_block_cols": dict(Counter(str(x["ev_diag"]["extracted_block_col"]) for x in sub)),
            "ev_extracted_unit_cols": dict(Counter(str(x["ev_diag"]["extracted_unit_col"]) for x in sub)),
            "ev_neg_detail_codes": dict(Counter(x["ev_neg_code"] for x in sub)),
        }

    return {
        "family_key": fkey,
        "model_id": mid,
        "revision": rev,
        "load_s": round(load_s, 3),
        "inference_s": round(run_s, 3),
        "raw_responses_jsonl": raw_path.name,
        "raw_responses_sha256": raw_sha,
        "overall_40": summarize_subset(per_case_summary),
        "by_trial_descriptive": {
            "RockTheVote_2008": summarize_subset([x for x in per_case_summary if x["trial"] == "RockTheVote_2008"]),
            "Bangladesh_Mask_CRT_2022": summarize_subset([x for x in per_case_summary if x["trial"] == "Bangladesh_Mask_CRT_2022"]),
        },
        "per_case": per_case_summary,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gold-only", action="store_true", help="Only run CPU gold-schema oracle self-check (0 LLM calls).")
    args = ap.parse_args()

    bench = json.loads(BENCH_PATH.read_text(encoding="utf-8"))
    cases = bench["cases"]
    assert len(cases) == 40

    gold_res = verify_gold_oracle_100pct(cases)
    print("GOLD DETERMINISTIC VERIFIER CHECK:", gold_res, flush=True)
    if args.gold_only:
        return

    t_wall0 = time.perf_counter()
    # Pre-locked 20 balanced neutral reorder/ID-renaming control cases (7 RTV + 13 BDM = 40 candidate judgments)
    reorder_ids = {f"RTV_{i:02d}" for i in range(1, 8)} | {f"BDM_{i:02d}" for i in range(1, 14)}
    assert len(reorder_ids) == 20

    family_results: Dict[str, Any] = {}
    for spec in MODEL_SPECS:
        family_results[spec["family_key"]] = score_family(spec, cases, reorder_ids)

    # Evaluate pre-locked conjunctive advance gate (STAGE0_SCREEN_PROTOCOL.md §3)
    gate_checks: Dict[str, Any] = {}
    all_pass = True
    for fk, fres in family_results.items():
        ov = fres["overall_40"]
        rtv = fres["by_trial_descriptive"]["RockTheVote_2008"]
        bdm = fres["by_trial_descriptive"]["Bangladesh_Mask_CRT_2022"]

        c1_fa = ov["direct_false_accept_count"] >= 8 and ov["direct_valid_accept_coverage"] >= 0.40
        c2_reord = ov["reord_total_flips"] <= 2
        c3_both_trials = (rtv["direct_false_accept_count"] >= 2) and (bdm["direct_false_accept_count"] >= 4)
        c4_ev_persist = (ov["ev_false_accept_count"] >= 4) or (ov["ev_schema_error_count"] >= 4)
        fam_pass = bool(c1_fa and c2_reord and c3_both_trials and c4_ev_persist)
        if not fam_pass:
            all_pass = False
        gate_checks[fk] = {
            "pass_direct_fa_ge_8_and_vac_ge_40pct": c1_fa,
            "pass_reord_flips_le_2": c2_reord,
            "pass_both_trials_signal": c3_both_trials,
            "pass_ev_persistence_ge_4": c4_ev_persist,
            "family_all_pass": fam_pass,
        }

    decision = "ADVANCE_TO_MULTI_TRIAL_STAGE1_PENDING_REVIEW" if all_pass else "STOP_OR_REFRAME_STAGE0_GATE_FAILED"
    summary = {
        "protocol": "STAGE0_SCREEN_PROTOCOL.md",
        "protocol_sha256": sha256_file(ROOT / "STAGE0_SCREEN_PROTOCOL.md"),
        "benchmark_file": BENCH_PATH.name,
        "benchmark_sha256": sha256_file(BENCH_PATH),
        "runner_sha256": sha256_file(pathlib.Path(__file__)),
        "real_pid": os.getpid(),
        "wall_time_s": round(time.perf_counter() - t_wall0, 3),
        "gold_oracle_verifier_check": gold_res,
        "families": {
            fk: {k: v for k, v in fres.items() if k != "per_case"}
            for fk, fres in family_results.items()
        },
        "prespecified_conjunctive_gate": {
            "per_family": gate_checks,
            "all_families_pass": all_pass,
            "decision": decision,
        },
    }

    # Save full per-case scored ledger separately and summary JSON
    per_case_path = OUT_DIR / "stage0_screen_per_case.json"
    per_case_path.write_text(
        json.dumps({fk: fres["per_case"] for fk, fres in family_results.items()}, indent=2),
        encoding="utf-8",
    )
    summary["per_case_json"] = per_case_path.name
    summary["per_case_json_sha256"] = sha256_file(per_case_path)

    sum_path = OUT_DIR / "stage0_screen_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== STAGE-0 BOUNDED SCREEN COMPLETE ===")
    print(f"PID={os.getpid()} | Wall={summary['wall_time_s']}s | Summary SHA={sha256_file(sum_path)}")
    for fk, fres in summary["families"].items():
        ov = fres["overall_40"]
        print(
            f"  {fk:15s} | Direct FA={ov['direct_false_accept_count']}/40 VAC={ov['direct_valid_accept_count']}/40 "
            f"PEA={ov['direct_paired_exact_count']}/40 Flips={ov['reord_total_flips']}/40 | "
            f"EV FA={ov['ev_false_accept_count']}/40 EV_PEA={ov['ev_paired_exact_count']}/40 EV_SchemaErr={ov['ev_schema_error_count']}/40"
        )
    print(f"GATE DECISION: {decision}")


if __name__ == "__main__":
    main()
