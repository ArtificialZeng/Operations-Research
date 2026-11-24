"""Read-only audit script for Stage-0 bounded randomization-support screen outputs."""
from __future__ import annotations

from collections import Counter
import hashlib
import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parent
OUT = ROOT / "stage0_screen_outputs"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> None:
    summary_path = OUT / "stage0_screen_summary.json"
    per_case_path = OUT / "stage0_screen_per_case.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    per_case = json.loads(per_case_path.read_text(encoding="utf-8"))

    print("SUMMARY SHA-256:", sha256_file(summary_path))
    print("PER-CASE SHA-256:", sha256_file(per_case_path))
    print("REAL PID:", summary["real_pid"], "| WALL:", summary["wall_time_s"], "s")
    print("PROTOCOL SHA-256:", summary["protocol_sha256"])
    print("BENCHMARK SHA-256:", summary["benchmark_sha256"])
    print("RUNNER SHA-256:", summary["runner_sha256"])
    print("GATE DECISION:", summary["prespecified_conjunctive_gate"]["decision"])

    for fk in ["qwen25_1p5b", "granite31_2b"]:
        raw_path = OUT / f"raw_responses_{fk}.jsonl"
        recs = [json.loads(line) for line in raw_path.read_text(encoding="utf-8").splitlines()]
        ext_raw = {r["case_id"]: r["raw_response"] for r in recs if r["cond"] == "extract_schema"}
        print(f"\n=== FAMILY: {fk} (raw lines={len(recs)}, sha256={sha256_file(raw_path)}) ===")
        for trial in ["RockTheVote_2008", "Bangladesh_Mask_CRT_2022"]:
            sub = [x for x in per_case[fk] if x["trial"] == trial]
            n = len(sub)
            u_ok = sum(1 for x in sub if x["ev_diag"]["unit_col_ok"])
            b_ok = sum(1 for x in sub if x["ev_diag"]["block_col_ok"])
            q_ok = sum(1 for x in sub if x["ev_diag"]["quotas_ok"])
            gold_u = "market_id" if trial == "RockTheVote_2008" else "union"
            gold_b = "strata" if trial == "RockTheVote_2008" else "pairID"
            raw_ub = sum(
                1
                for x in sub
                if (f'"unit_col": "{gold_u}"' in ext_raw[x["case_id"]] and f'"block_col": "{gold_b}"' in ext_raw[x["case_id"]])
            )
            # Classify extraction failure reasons precisely
            reasons = Counter()
            for x in sub:
                if x["ev_paired_exact"]:
                    reasons["exact_schema_and_quotas_pass"] += 1
                elif x["ev_pos_code"] == "unparseable_schema_json":
                    reasons["truncated_or_unparseable_json"] += 1
                elif not x["ev_diag"]["block_col_ok"]:
                    reasons[f"wrong_block_col({x['ev_diag']['extracted_block_col']})+rule({x['ev_diag']['extracted_quota_rule']})"] += 1
                elif x["ev_pos_code"].startswith("incomplete_block_quotas_missing"):
                    reasons["right_unit_and_block_but_missing_or_unit_keyed_block_quotas"] += 1
                else:
                    reasons["right_unit_and_block_but_wrong_block_quota_values"] += 1
            print(
                f"  {trial} (N={n}): "
                f"Direct FA={sum(x['direct_false_accept'] for x in sub)}/{n}, "
                f"VAC={sum(x['direct_valid_accept'] for x in sub)}/{n}, "
                f"PEA={sum(x['direct_paired_exact'] for x in sub)}/{n} | "
                f"EV FA={sum(x['ev_false_accept'] for x in sub)}/{n}, "
                f"EV_PEA={sum(x['ev_paired_exact'] for x in sub)}/{n}, "
                f"EV_SchemaErr={sum(x['ev_schema_error'] for x in sub)}/{n} | "
                f"parsed(u_ok={u_ok}, b_ok={b_ok}, q_ok={q_ok}), raw_text_has_gold_u_and_b={raw_ub}/{n}"
            )
            for k, v in reasons.most_common():
                print(f"    - {k}: {v}/{n}")


if __name__ == "__main__":
    main()
