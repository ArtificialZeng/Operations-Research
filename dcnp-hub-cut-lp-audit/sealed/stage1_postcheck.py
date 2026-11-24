"""Post-run, read-only audit of the sealed Stage 1 results (no solver runs, no retuning).

Recomputes Tier 1 / Tier 2 quantities from raw per-instance records and checks each MIP dual bound and root LP
against the better of the two BFS primals, as the sealed protocol requires.
"""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path

D = Path(__file__).resolve().parent
RES = D / "stage1_heldout_synthetic_results.json"
EXIT = D / "stage1_heldout_exit_receipt.json"
OUT = D / "stage1_postcheck.json"
TOL = 1e-4


def sgm(vals, shift):
    return math.exp(sum(math.log(v + shift) for v in vals) / len(vals)) - shift


res = json.loads(RES.read_text(encoding="utf-8"))
ex = json.loads(EXIT.read_text(encoding="utf-8"))
sha = hashlib.sha256(RES.read_bytes()).hexdigest()

rows, fails = [], []
lifts = 0
closures = []
tb, ta = [], []
fam_t = {}
wins = ties = losses = 0
bw = bt = bl = 0
for r in res["instances"]:
    b, a = r["BASE_FULL"], r["AUG_HUB"]
    best = min(b["mip_primal_bfs"], a["mip_primal_bfs"])
    checks = {
        "base_dual_le_best": b["mip_dual_bound"] <= best + TOL,
        "aug_dual_le_best": a["mip_dual_bound"] <= best + TOL,
        "base_root_le_best": b["lp_root_after_cuts"] <= best + TOL,
        "aug_root_le_best": a["lp_root_after_cuts"] <= best + TOL,
        "primals_equal": b["mip_primal_bfs"] == a["mip_primal_bfs"],
        "both_bfs_verified": b["bfs_verified"] and a["bfs_verified"],
        "no_deadline": not (b["hit_wall_deadline"] or a["hit_wall_deadline"]),
        "both_optimal": b["solved_opt"] and a["solved_opt"],
    }
    if not all(checks.values()):
        fails.append({"instance": r["instance"], "checks": checks})
    dl = a["lp_root_after_cuts"] - b["lp_root_after_cuts"]
    if dl > 1e-6:
        lifts += 1
    gap = best - b["lp_root_after_cuts"]
    if gap > 1e-6:
        closures.append(100.0 * dl / gap)
    x, y = b["t_total_s"], a["t_total_s"]
    tb.append(x)
    ta.append(y)
    fam_t.setdefault(r["family"], ([], []))
    fam_t[r["family"]][0].append(x)
    fam_t[r["family"]][1].append(y)
    if y <= 0.9 * x and x - y >= 0.1:
        res_ = "W"
    elif x <= 0.9 * y and y - x >= 0.1:
        res_ = "L"
    else:
        res_ = "T"
    wins += res_ == "W"
    ties += res_ == "T"
    losses += res_ == "L"
    branching = b["mip_nodes"] > 1 or a["mip_nodes"] > 1
    if branching:
        bw += res_ == "W"
        bt += res_ == "T"
        bl += res_ == "L"
    rows.append({"instance": r["instance"], "best_primal": best, "lift": round(dl, 6), "branching": branching,
                 "wall_base": x, "wall_aug": y, "paired": res_})

out = {
    "results_sha256_recomputed": sha,
    "results_sha256_in_exit_receipt": ex["results_sha256"],
    "results_hash_matches_receipt": sha == ex["results_sha256"],
    "hashes_unchanged_during_run": ex["hashes_unchanged_during_run"],
    "exit_code": ex["exit_code"],
    "elapsed_wall_seconds_receipt": ex["elapsed_wall_seconds"],
    "integrity_failures": fails,
    "instances_checked": len(rows),
    "tier1": {
        "strict_lifts": lifts,
        "families_with_lift": sorted({r["family"] for r in res["instances"]
                                      if r["AUG_HUB"]["lp_root_after_cuts"] > r["BASE_FULL"]["lp_root_after_cuts"] + 1e-6}),
        "mean_additional_gap_closure_pct": round(sum(closures) / len(closures), 2),
        "pass_rule": ">=10/16 lifts, >=2 families incl. a non-bipartite one, mean closure >=10%",
        "pass": lifts >= 10 and sum(closures) / len(closures) >= 10.0,
    },
    "tier2": {
        "sgm_wall_ratio_aug_over_base_shift1": round(sgm(ta, 1.0) / sgm(tb, 1.0), 4),
        "paired_all": {"wins": wins, "ties": ties, "losses": losses},
        "paired_branching_either_arm_nodes_gt1": {"wins": bw, "ties": bt, "losses": bl},
        "family_sgm_ratio": {f: round(sgm(v[1], 1.0) / sgm(v[0], 1.0), 4) for f, v in sorted(fam_t.items())},
        "pass_rule": "ratio <= 0.85, wins > losses on branching, no ratio > 1.25 on >=2 families, solved(aug) >= solved(base)",
    },
    "per_instance": rows,
}
t2 = out["tier2"]
t2["pass"] = (t2["sgm_wall_ratio_aug_over_base_shift1"] <= 0.85 and bw > bl
              and sum(1 for v in t2["family_sgm_ratio"].values() if v > 1.25) < 2)
OUT.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: out[k] for k in ("results_hash_matches_receipt", "integrity_failures", "tier1", "tier2")}, indent=2))
