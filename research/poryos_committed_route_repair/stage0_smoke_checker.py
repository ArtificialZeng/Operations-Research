"""
Stage-0 Smoke Check v2: Inspect `n=10, 25, 50` on `lyon` (`bpr-light/heavy`, `wave-light/heavy`):
  - Exact traffic speed-bin hours (when does congestion occur in [0, 86400]s?)
  - Customer time-window distribution & BKS route start/end hours
  - Cross-overlay feasibility of light BKS routes under heavy overlays (rescheduling vs fixed departure!)
  - Exact official checker agreement (`< 1e-6s`).
"""
from __future__ import annotations

import gzip
import json
import pathlib
import time
import urllib.request

from mamut_routing_lib.artifacts import load_bks
from mamut_routing_lib.models import BenchmarkSolution, ObjectiveFunction
from mamut_routing_lib.td import (
    check_td_solution,
    compute_route_duration,
    load_td_instance,
)


ROOT = pathlib.Path(__file__).resolve().parent
PORYOS_ROOT = ROOT / "raw_poryos2026"
P_SHA = "0400ed2c3a27ed36f725034a38873b69d3af1dea"
RAW_BASE = f"https://raw.githubusercontent.com/ANR-MAMUT/MAMUT-routing-Poryos2026/{P_SHA}"


def fetch_poryos(rel_path: str) -> pathlib.Path:
    dst = PORYOS_ROOT / rel_path
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        url = f"{RAW_BASE}/{rel_path}"
        req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
        with urllib.request.urlopen(req, timeout=60) as r:
            dst.write_bytes(r.read())
    return dst


def main() -> None:
    fetch_poryos("mamut-collection.json")
    fetch_poryos("LICENSE")

    smoke_specs = [
        ("lyon", 10, "poryos-lyon-n10-hyb"),
        ("lyon", 25, "poryos-lyon-n25-hyb"),
        ("lyon", 50, "poryos-lyon-n50-hyb"),
    ]
    for city, n, base in smoke_specs:
        fetch_poryos(f"sidecars/{city}/n={n}/{base}/{base}.road.json.gz")
        loaded_by_ov = {}
        bks_by_ov = {}
        for ov in ["bpr-light", "bpr-heavy", "wave-light", "wave-heavy"]:
            tf_p = fetch_poryos(f"sidecars/{city}/n={n}/{base}/{base}.traffic-{ov}.json.gz")
            vrp_p = fetch_poryos(f"TDVRPTW/{city}/n={n}/{base}/{ov}/{base}-{ov}.vrp.json")
            bks_p = fetch_poryos(f"TDVRPTW/{city}/n={n}/{base}/{ov}/{base}-{ov}.bks.Duration.json")

            t0 = time.perf_counter()
            loaded = load_td_instance(vrp_p)
            dt = time.perf_counter() - t0
            inst = loaded.instance
            bks = load_bks(bks_p)
            loaded_by_ov[ov] = loaded
            bks_by_ov[ov] = bks
            chk_bks = check_td_solution(loaded, bks, objective_function=ObjectiveFunction.DURATION)

            # Check route departure & return hour ranges
            evs = [compute_route_duration(inst, loaded.atfs, r) for r in bks.routes]
            max_ret = max(ev.departure_time + ev.duration for ev in evs)
            min_dep = min(ev.departure_time for ev in evs)
            max_dep = max(ev.departure_time for ev in evs)
            tws = [inst.time_windows[i] for i in range(1, inst.num_customers + 1)]
            print(
                f"[{base} | {ov:10s}] load={dt:.2f}s | status={chk_bks.status.name} cost={chk_bks.routing_cost:.1f}s "
                f"K={chk_bks.num_routes} dep=[{min_dep/3600:.2f}h..{max_dep/3600:.2f}h] max_ret={max_ret/3600:.2f}h | "
                f"TWs e=[{min(a for a,b in tws)/3600:.2f}h..{max(a for a,b in tws)/3600:.2f}h] "
                f"l=[{min(b for a,b in tws)/3600:.2f}h..{max(b for a,b in tws)/3600:.2f}h]"
            )
            if n == 10 and ov in ("bpr-heavy", "wave-heavy"):
                tf_data = json.loads(gzip.decompress(tf_p.read_bytes()).decode("utf-8"))
                print("   traffic json keys:", list(tf_data.keys()), "meta:", {k: tf_data[k] for k in tf_data if k not in ("edges", "speeds", "multipliers", "factors", "bins", "profiles")})

        # Cross-overlay feasibility of light BKS under heavy (BOTH free-reschedule AND fixed-dep_0!)
        for fam in ("bpr", "wave"):
            src_ov = f"{fam}-light"
            dst_ov = f"{fam}-heavy"
            sol_src = BenchmarkSolution(instance_name=loaded_by_ov[dst_ov].instance.instance_name, routes=bks_by_ov[src_ov].routes)
            chk_resched = check_td_solution(loaded_by_ov[dst_ov], sol_src, objective_function=ObjectiveFunction.DURATION)
            # Also check with FIXED source departure time t*_r (zero rescheduling of depot departure!)
            fixed_viol = 0
            for r in bks_by_ov[src_ov].routes:
                ev_old = compute_route_duration(loaded_by_ov[src_ov].instance, loaded_by_ov[src_ov].atfs, r)
                t = ev_old.departure_time
                prev = 0
                ok = True
                for c in r:
                    arc = loaded_by_ov[dst_ov].atfs.arcs[(prev, c)]
                    if t < arc.min_domain or t > arc.max_domain:
                        ok = False
                        break
                    arr = arc.evaluate(t)
                    e_c, l_c = loaded_by_ov[dst_ov].instance.time_windows[c]
                    st = max(arr, float(e_c))
                    if st > float(l_c):
                        ok = False
                        break
                    t = st + float(loaded_by_ov[dst_ov].instance.service_times[c])
                    prev = c
                if ok:
                    arc = loaded_by_ov[dst_ov].atfs.arcs[(prev, 0)]
                    if t > arc.max_domain or arc.evaluate(t) > float(loaded_by_ov[dst_ov].instance.time_windows[0][1]):
                        ok = False
                if not ok:
                    fixed_viol += 1
            print(
                f"  CROSS {src_ov} -> {dst_ov}: free_resched={chk_resched.status.name} "
                f"(cost={chk_resched.routing_cost}) | fixed_dep0_violated_routes={fixed_viol}/{len(bks_by_ov[src_ov].routes)}"
            )


if __name__ == "__main__":
    main()
