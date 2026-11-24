"""
Deterministically builds a strictly benign, neutral read-only, tool-family-disjoint
BFCL v4 Simple Python + Multiple pilot split (`pilot_dev`) vs untouched `future_blind_test`.

Provenance pinned:
  - Repo: ShishirPatil/gorilla (Apache-2.0)
  - Commit: 6ea57973c7a6097fd7c5915698c54c17c5b1b6c8
  - Files: BFCL_v4_simple_python.json, BFCL_v4_multiple.json (+ possible_answer/*)

Guarantees:
  1. Neutral read-only benign schema & prompt filter (excludes write/delete/pay/send/auth/exec/sensitive actions).
  2. Connected-component tool-family clustering over ALL function names and normalized domain roots:
     ZERO overlap in exact function names OR domain roots between `pilot_dev` and `future_blind_test`.
  3. Bounded Stage-0 pilot size: target 100 examples (~60 simple_python + ~40 multiple) sampled strictly
     at the tool-family component level (seed=20261124). `future_blind_test` IDs are sealed by SHA-256
     and NOT inspected or executed in Stage-0.
"""
from __future__ import annotations

import collections
import hashlib
import json
import os
import pathlib
import random
import re

BASE = pathlib.Path(os.environ.get("GRAMMAR_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
BFCL_DATA = BASE / "bfcl_upstream" / "berkeley-function-call-leaderboard" / "bfcl_eval" / "data"

DENY_RE = re.compile(
    r"\b(delete|remove|drop|erase|kill|destroy|shutdown|reboot|exec|execute|shell|cmd|bash|sudo|chmod|chown|"
    r"transfer|wire|withdraw|deposit|pay|payment|charge|purchase|buy|sell|trade|order|book|booking|reserve|cancel|"
    r"send|email|mail|sms|text|message|post|tweet|publish|upload|write|modify|update|edit|patch|create_user|"
    r"password|passwd|token|secret|credential|api_key|auth|login|hack|exploit|attack|weapon|drug|diagnos|prescrib|"
    r"lawsuit|sue|arrest|crime|criminal|police|court|fire|terminate_employee|ban|block_user|install|uninstall)\b",
    re.IGNORECASE,
)

GENERIC_VERBS = {
    "calculate", "calc", "compute", "get", "find", "fetch", "retrieve", "check", "search",
    "list", "convert", "estimate", "predict", "measure", "analyze", "analyse", "count",
    "generate", "simulate", "solve", "determine", "identify", "evaluate", "compare",
    "lookup", "query", "read", "show", "display", "format", "parse", "extract", "sort",
    "filter", "rank", "recommend", "suggest", "plan", "create", "make", "build", "draw",
}


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def func_domain_family(fn_name: str) -> str:
    fn = fn_name.strip().lower()
    if "." in fn:
        return fn.split(".")[0]
    parts = [t for t in fn.split("_") if t]
    while len(parts) > 1 and parts[0] in GENERIC_VERBS:
        parts = parts[1:]
    return parts[0] if parts else fn


def load_jsonl(p: pathlib.Path):
    return [json.loads(line) for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    sources = [
        ("simple_python", "BFCL_v4_simple_python.json"),
        ("multiple", "BFCL_v4_multiple.json"),
    ]
    source_hashes = {}
    all_benign = []
    dropped_log = []

    for cat, fname in sources:
        qp = BFCL_DATA / fname
        ap = BFCL_DATA / "possible_answer" / fname
        source_hashes[f"data/{fname}"] = {"bytes": qp.stat().st_size, "sha256": sha256_file(qp)}
        source_hashes[f"possible_answer/{fname}"] = {"bytes": ap.stat().st_size, "sha256": sha256_file(ap)}
        qs = load_jsonl(qp)
        ans = {r["id"]: r["ground_truth"] for r in load_jsonl(ap)}
        assert len(qs) == len(ans)
        for q in qs:
            prompt_text = q["question"][0][0]["content"]
            fn_blob = " ".join(
                f["name"] + " " + f.get("description", "") + " " + " ".join(f.get("parameters", {}).get("properties", {}).keys())
                for f in q["function"]
            )
            m = DENY_RE.search(prompt_text + " " + fn_blob)
            if m:
                dropped_log.append({"id": q["id"], "category": cat, "matched_token": m.group(0)})
                continue
            fn_names = [f["name"] for f in q["function"]]
            fams = sorted({func_domain_family(fn) for fn in fn_names})
            all_benign.append({
                "id": q["id"],
                "category": cat,
                "question": q["question"],
                "function": q["function"],
                "ground_truth": ans[q["id"]],
                "fn_names": fn_names,
                "tool_families": fams,
            })

    # Union-Find over examples sharing ANY exact function name OR domain tool-family root
    parent = list(range(len(all_benign)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    key_owner = {}
    for i, item in enumerate(all_benign):
        keys = set(item["fn_names"]) | {f"fam:{f}" for f in item["tool_families"]}
        for k in keys:
            if k in key_owner:
                union(i, key_owner[k])
            else:
                key_owner[k] = i

    comp_map = collections.defaultdict(list)
    for i in range(len(all_benign)):
        comp_map[find(i)].append(i)

    # Canonical deterministic component list sorted by smallest example id
    components = []
    for idxs in comp_map.values():
        idxs_sorted = sorted(idxs, key=lambda j: all_benign[j]["id"])
        comp_id = all_benign[idxs_sorted[0]]["id"]
        n_s = sum(1 for j in idxs_sorted if all_benign[j]["category"] == "simple_python")
        n_m = sum(1 for j in idxs_sorted if all_benign[j]["category"] == "multiple")
        components.append({"comp_id": comp_id, "indices": idxs_sorted, "n_simple": n_s, "n_multiple": n_m, "size": len(idxs_sorted)})
    components.sort(key=lambda c: c["comp_id"])

    # Deterministically select small/medium components into pilot_dev (target ~60 simple, ~40 multiple -> ~100 total)
    # Exclude giant mega-components (>15 examples) from pilot so pilot spans many diverse tool families!
    rng = random.Random(20261124)
    eligible = [c for c in components if c["size"] <= 15]
    rng.shuffle(eligible)

    pilot_comp_ids = set()
    p_s = 0
    p_m = 0
    # First add components containing multiple examples until p_m reaches ~40
    for c in eligible:
        if c["n_multiple"] > 0 and p_m + c["n_multiple"] <= 42 and p_s + c["n_simple"] <= 62:
            pilot_comp_ids.add(c["comp_id"])
            p_s += c["n_simple"]
            p_m += c["n_multiple"]
        if p_m >= 40:
            break
    # Then fill simple_python components until p_s reaches ~60
    for c in eligible:
        if c["comp_id"] in pilot_comp_ids:
            continue
        if c["n_multiple"] == 0 and p_s + c["n_simple"] <= 60:
            pilot_comp_ids.add(c["comp_id"])
            p_s += c["n_simple"]
        if p_s >= 60:
            break

    pilot_items = []
    blind_items = []
    for c in components:
        target = pilot_items if c["comp_id"] in pilot_comp_ids else blind_items
        for j in c["indices"]:
            rec = dict(all_benign[j])
            rec["tool_family_cluster"] = c["comp_id"]
            target.append(rec)

    pilot_items.sort(key=lambda r: r["id"])
    blind_items.sort(key=lambda r: r["id"])

    # HARD ZERO-LEAKAGE ASSERTION: zero overlap in IDs, exact function names, or domain families!
    pilot_ids = {r["id"] for r in pilot_items}
    blind_ids = {r["id"] for r in blind_items}
    pilot_fns = {fn for r in pilot_items for fn in r["fn_names"]}
    blind_fns = {fn for r in blind_items for fn in r["fn_names"]}
    pilot_fams = {f for r in pilot_items for f in r["tool_families"]}
    blind_fams = {f for r in blind_items for f in r["tool_families"]}

    assert not (pilot_ids & blind_ids), "ID overlap!"
    assert not (pilot_fns & blind_fns), f"Function name overlap: {pilot_fns & blind_fns}"
    assert not (pilot_fams & blind_fams), f"Tool family overlap: {pilot_fams & blind_fams}"

    # Persist pilot dataset & sealed blind-test ID manifest (blind test examples themselves are NOT printed/inspected)
    pilot_path = BASE / "bfcl_stage0_pilot_dataset.json"
    pilot_path.write_text(json.dumps(pilot_items, indent=2), encoding="utf-8")

    blind_ids_sorted = sorted(blind_ids)
    blind_manifest_path = BASE / "bfcl_future_blind_test_ids_sealed.json"
    blind_manifest_path.write_text(json.dumps({
        "status": "SEALED_UNTOUCHED_FUTURE_BLIND_TEST",
        "n_total": len(blind_items),
        "n_simple_python": sum(1 for r in blind_items if r["category"] == "simple_python"),
        "n_multiple": sum(1 for r in blind_items if r["category"] == "multiple"),
        "n_clusters": len(components) - len(pilot_comp_ids),
        "ids": blind_ids_sorted,
    }, indent=2), encoding="utf-8")

    receipt = {
        "upstream_repo": "https://github.com/ShishirPatil/gorilla",
        "upstream_commit": "6ea57973c7a6097fd7c5915698c54c17c5b1b6c8",
        "upstream_license": "Apache-2.0",
        "source_file_hashes": source_hashes,
        "benign_screen": {
            "total_raw_examples": len(all_benign) + len(dropped_log),
            "kept_benign_examples": len(all_benign),
            "dropped_non_readonly_or_sensitive": len(dropped_log),
            "dropped_examples": dropped_log,
        },
        "clustering_and_disjoint_split": {
            "split_seed": 20261124,
            "total_connected_tool_family_clusters": len(components),
            "pilot_dev": {
                "n_examples": len(pilot_items),
                "n_simple_python": sum(1 for r in pilot_items if r["category"] == "simple_python"),
                "n_multiple": sum(1 for r in pilot_items if r["category"] == "multiple"),
                "n_clusters": len(pilot_comp_ids),
                "n_distinct_tool_families": len(pilot_fams),
                "file": pilot_path.name,
                "sha256": sha256_file(pilot_path),
            },
            "future_blind_test": {
                "n_examples": len(blind_items),
                "n_simple_python": sum(1 for r in blind_items if r["category"] == "simple_python"),
                "n_multiple": sum(1 for r in blind_items if r["category"] == "multiple"),
                "n_clusters": len(components) - len(pilot_comp_ids),
                "n_distinct_tool_families": len(blind_fams),
                "sealed_ids_file": blind_manifest_path.name,
                "sealed_ids_sha256": sha256_file(blind_manifest_path),
            },
            "zero_id_overlap": True,
            "zero_exact_function_name_overlap": True,
            "zero_tool_family_root_overlap": True,
        },
    }
    rec_path = BASE / "BFCL_PILOT_SPLIT_RECEIPT.json"
    rec_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(
        f"BUILT DISJOINT BFCL SPLIT: pilot={len(pilot_items)} "
        f"(simple={receipt['clustering_and_disjoint_split']['pilot_dev']['n_simple_python']}, "
        f"multiple={receipt['clustering_and_disjoint_split']['pilot_dev']['n_multiple']}, "
        f"clusters={len(pilot_comp_ids)}, fams={len(pilot_fams)}) | "
        f"blind_sealed={len(blind_items)} (clusters={len(components)-len(pilot_comp_ids)}, fams={len(blind_fams)}) | "
        f"ZERO overlap verified!"
    )


if __name__ == "__main__":
    main()
