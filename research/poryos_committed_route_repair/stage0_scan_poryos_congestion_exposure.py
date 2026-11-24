"""
Stage-0 Decisive Structural Exposure Scan across Poryos2026 TDVRPTW (`td-shared`):
  5 cities (hong_kong, lyon, paris, san_francisco, tokyo) x 2 methods (hyb, poi) x n in {10, 25, 50, 100}.
Fetches ONLY tiny `.vrp.json` and `.bks.Duration.json` files (no heavy sidecars yet) to measure:
  1. Time-window bounds (min/max earliest & latest in hours from 00:00, mean width in hours).
  2. Official BKS Duration costs under `bpr-light` vs `bpr-heavy` and `wave-light` vs `wave-heavy`,
     relative cost increase `(heavy - light) / light`, and whether `light` and `heavy` BKS even differ!
  3. Number of routes K and exact `tw_repair` counts recorded by the benchmark authors.
"""
from __future__ import annotations

import json
import pathlib
import urllib.request


ROOT = pathlib.Path(__file__).resolve().parent
PORYOS_ROOT = ROOT / "raw_poryos2026"
P_SHA = "0400ed2c3a27ed36f725034a38873b69d3af1dea"
RAW_BASE = f"https://raw.githubusercontent.com/ANR-MAMUT/MAMUT-routing-Poryos2026/{P_SHA}"

CITIES = ["hong_kong", "lyon", "paris", "san_francisco", "tokyo"]
METHODS = ["hyb", "poi"]
SIZES = [10, 25, 50, 100]


def fetch_json(rel_path: str):
    dst = PORYOS_ROOT / rel_path
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        url = f"{RAW_BASE}/{rel_path}"
        req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
        with urllib.request.urlopen(req, timeout=30) as r:
            dst.write_bytes(r.read())
    return json.loads(dst.read_text(encoding="utf-8"))


def main() -> None:
    rows = []
    for n in SIZES:
        print(f"\n==================== n = {n} ====================", flush=True)
        for city in CITIES:
            for meth in METHODS:
                base = f"poryos-{city}-n{n}-{meth}"
                # Try both city_slug and city if needed; Poryos README says san-francisco / hong-kong in filename, underscore in dir
                try:
                    vrp_bl = fetch_json(f"TDVRPTW/{city}/n={n}/{base}/bpr-light/{base}-bpr-light.vrp.json")
                except Exception as e:
                    print(f"  MISS {city} n={n} {base}: {e}", flush=True)
                    continue
                bks = {}
                for ov in ["bpr-light", "bpr-heavy", "wave-light", "wave-heavy"]:
                    try:
                        bks[ov] = fetch_json(f"TDVRPTW/{city}/n={n}/{base}/{ov}/{base}-{ov}.bks.Duration.json")
                    except Exception:
                        bks[ov] = None
                tws = vrp_bl["time_windows"][1:]
                e_max = max(a for a, b in tws) / 3600.0
                l_min = min(b for a, b in tws) / 3600.0
                l_max = max(b for a, b in tws) / 3600.0
                w_mean = sum(b - a for a, b in tws) / len(tws) / 3600.0
                tw_rep = vrp_bl.get("metadata", {}).get("tw_repair")

                def cost(ov):
                    if bks[ov] is None:
                        return None
                    return float(bks[ov].get("routing_cost", bks[ov].get("cost", bks[ov].get("objective_value", -1))))

                def routes(ov):
                    return bks[ov].get("routes") if bks[ov] else None

                c_bl, c_bh = cost("bpr-light"), cost("bpr-heavy")
                c_wl, c_wh = cost("wave-light"), cost("wave-heavy")
                pct_b = 100.0 * (c_bh - c_bl) / c_bl if (c_bl and c_bh) else None
                pct_w = 100.0 * (c_wh - c_wl) / c_wl if (c_wl and c_wh) else None
                same_b = (routes("bpr-light") == routes("bpr-heavy"))
                same_w = (routes("wave-light") == routes("wave-heavy"))
                K_bl = len(routes("bpr-light")) if routes("bpr-light") else 0

                rec = {
                    "n": n,
                    "city": city,
                    "base": base,
                    "K_bl": K_bl,
                    "e_max_h": round(e_max, 2),
                    "l_min_h": round(l_min, 2),
                    "l_max_h": round(l_max, 2),
                    "w_mean_h": round(w_mean, 2),
                    "c_bl": round(c_bl, 1) if c_bl else None,
                    "c_bh": round(c_bh, 1) if c_bh else None,
                    "pct_bpr": round(pct_b, 2) if pct_b is not None else None,
                    "same_routes_bpr": same_b,
                    "c_wl": round(c_wl, 1) if c_wl else None,
                    "c_wh": round(c_wh, 1) if c_wh else None,
                    "pct_wave": round(pct_w, 2) if pct_w is not None else None,
                    "same_routes_wave": same_w,
                    "tw_repair": tw_rep,
                }
                rows.append(rec)
                print(
                    f"  {base:30s} K={K_bl:2d} e_max={e_max:4.1f}h l=[{l_min:4.1f}..{l_max:4.1f}h] w={w_mean:4.1f}h | "
                    f"BPR: {pct_b:+6.2f}% (sameR={str(same_b):5s}) | WAVE: {pct_w:+6.2f}% (sameR={str(same_w):5s}) | tw_rep={tw_rep}",
                    flush=True,
                )

    out_p = ROOT / "STAGE0_PORYOS_EXPOSURE_SCAN.json"
    out_p.write_text(json.dumps(rows, indent=2), encoding="utf-8")
    print(f"\nSaved {len(rows)} bases to {out_p.name}")


if __name__ == "__main__":
    main()
