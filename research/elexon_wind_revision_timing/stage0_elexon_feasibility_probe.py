"""
Stage-0 Real Data Feasibility Receipt Probe for GB Wind Forecast Revisions (Elexon BMRS).

Tests official public auth-free Elexon Insights BMRS endpoints across 5 prespecified historical dates
spanning 2024-2026 (GMT & BST):
  - 2024-11-15 (GMT)
  - 2025-05-15 (BST)
  - 2025-11-15 (GMT)
  - 2026-04-15 (BST)
  - 2026-10-15 (BST; tested reference example)

Verifies:
  1. `forecast/generation/wind/evolution` vintage counts & values.
  2. `datasets/WINDFOR/stream` vintage preservation by `publishDateTimeFrom/To` cross-checked against `evolution`.
  3. `datasets/FUELHH/stream` (`fuelType=WIND`) half-hourly outturns, UTC alignment (GMT vs BST),
     publishTime lags, duplicates/corrections, and MW alignment vs WINDFOR.
  4. Exact publication cadence, delivery time grid, identical-revision detection, and 2024-2026 operator changes.
Archives raw responses, request URLs, HTTP status, timestamps, and SHA-256 hashes under `raw_receipts/`.
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
import pathlib
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Tuple


ROOT = pathlib.Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_receipts"
RAW_DIR.mkdir(parents=True, exist_ok=True)

PRESPECIFIED_DATES = [
    "2024-11-15",
    "2025-05-15",
    "2025-11-15",
    "2026-04-15",
    "2026-10-15",
]

BASE = "https://data.elexon.co.uk/bmrs/api/v1"


def fetch_json(url: str, save_name: str) -> Tuple[Any, Dict[str, Any]]:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Python-urllib/3.12 (academic-research-feasibility)",
            "Accept": "application/json",
        },
    )
    t0 = datetime.now(timezone.utc).isoformat()
    with urllib.request.urlopen(req, timeout=60) as resp:
        raw = resp.read()
        status = resp.status
        ctype = resp.headers.get("Content-Type", "")
    sha = hashlib.sha256(raw).hexdigest()
    dst = RAW_DIR / save_name
    dst.write_bytes(raw)
    data = json.loads(raw.decode("utf-8"))
    meta = {
        "url": url,
        "saved_file": save_name,
        "fetched_utc": t0,
        "http_status": status,
        "content_type": ctype,
        "bytes": len(raw),
        "sha256": sha,
    }
    return data, meta


def extract_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and isinstance(obj.get("data"), list):
        return obj["data"]
    raise ValueError(f"Unexpected JSON structure: {type(obj)} keys={list(obj.keys()) if isinstance(obj, dict) else None}")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    receipt: Dict[str, Any] = {
        "purpose": "Stage-0 Authoritative Feasibility Receipt for Elexon BMRS WINDFOR x FUELHH",
        "prespecified_dates": PRESPECIFIED_DATES,
        "requests": [],
        "evolution_checks": {},
        "date_reports": {},
    }

    # 1. Tested reference evolution check: 2026-10-15T12:00:00Z + 15:00:00Z on all 5 dates
    evo_targets = [("2026-10-15T12:00:00Z", "evo_2026-10-15T12Z.json")]
    for d in PRESPECIFIED_DATES:
        evo_targets.append((f"{d}T15:00:00Z", f"evo_{d}T15Z.json"))

    evo_maps: Dict[str, Dict[str, float]] = {}
    for st, fname in evo_targets:
        q = urllib.parse.urlencode({"startTime": st, "format": "json"})
        url = f"{BASE}/forecast/generation/wind/evolution?{q}"
        obj, meta = fetch_json(url, fname)
        receipt["requests"].append(meta)
        rows = extract_rows(obj)
        pubs = [r["publishTime"] for r in rows]
        uniq_pubs = sorted(set(pubs))
        by_pub: Dict[str, List[float]] = defaultdict(list)
        for r in rows:
            by_pub[r["publishTime"]].append(float(r["generation"]))
        dup_pubs = {p: vs for p, vs in by_pub.items() if len(vs) > 1}
        evo_maps[st] = {p: vs[-1] for p, vs in by_pub.items()}
        receipt["evolution_checks"][st] = {
            "n_rows": len(rows),
            "n_unique_publishTime": len(uniq_pubs),
            "duplicate_publishTimes": dup_pubs,
            "fields": sorted(rows[0].keys()) if rows else [],
            "min_publishTime": uniq_pubs[0] if uniq_pubs else None,
            "max_publishTime": uniq_pubs[-1] if uniq_pubs else None,
            "publishTimes_le_11Z": [p for p in uniq_pubs if p <= f"{st[:10]}T11:00:00Z"],
        }
        print(
            f"[EVO {st}] rows={len(rows)} uniq_pub={len(uniq_pubs)} "
            f"dups={len(dup_pubs)} min={uniq_pubs[0] if uniq_pubs else None} max={uniq_pubs[-1] if uniq_pubs else None}"
        )

    # 2. For each prespecified date, test WINDFOR/stream & FUELHH/stream and cross-check vs evolution
    for d in PRESPECIFIED_DATES:
        dt = datetime.strptime(d, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        d_prev = (dt - timedelta(days=1)).strftime("%Y-%m-%d")
        d_next = (dt + timedelta(days=1)).strftime("%Y-%m-%d")
        cutoff_str = f"{d}T11:00:00Z"

        # 2a. WINDFOR/stream for publishDateTime in [D-1 00:00Z, D 11:00Z]
        q_wf = urllib.parse.urlencode(
            {
                "publishDateTimeFrom": f"{d_prev}T00:00:00Z",
                "publishDateTimeTo": cutoff_str,
            }
        )
        url_wf = f"{BASE}/datasets/WINDFOR/stream?{q_wf}"
        wf_obj, wf_meta = fetch_json(url_wf, f"windfor_stream_{d}.json")
        receipt["requests"].append(wf_meta)
        wf_rows = extract_rows(wf_obj)

        # Group by publishTime -> {startTime: [generations]}
        vintages: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
        for r in wf_rows:
            vintages[r["publishTime"]][r["startTime"]].append(float(r["generation"]))

        pub_times = sorted(vintages.keys())
        dup_pairs = []
        vintage_summaries = []
        for p in pub_times:
            st_map = vintages[p]
            for st, vals in st_map.items():
                if len(vals) > 1:
                    dup_pairs.append({"publishTime": p, "startTime": st, "values": vals})
            sts = sorted(st_map.keys())
            # Check step spacing between delivery startTimes
            steps_min = Counter(
                int((parse_iso(sts[i + 1]) - parse_iso(sts[i])).total_seconds() // 60)
                for i in range(len(sts) - 1)
            )
            # Check coverage of 11:00Z..23:00Z on date D
            day_hours = [f"{d}T{h:02d}:00:00Z" for h in range(11, 24)]
            cov_11_23 = sum(1 for h in day_hours if h in st_map)
            vintage_summaries.append(
                {
                    "publishTime": p,
                    "n_delivery_points": len(sts),
                    "min_startTime": sts[0],
                    "max_startTime": sts[-1],
                    "step_minutes_counts": dict(steps_min),
                    "covers_D_11Z_to_23Z_hourly": f"{cov_11_23}/13",
                    "gen_at_15Z": st_map.get(f"{d}T15:00:00Z", [None])[-1],
                    "gen_at_18Z": st_map.get(f"{d}T18:00:00Z", [None])[-1],
                }
            )

        # Detect identical consecutive intraday vintages (diff == 0 across shared delivery grid on D 11Z..23Z)
        consecutive_diffs = []
        for i in range(1, len(pub_times)):
            p_prev, p_cur = pub_times[i - 1], pub_times[i]
            shared = sorted(set(vintages[p_prev].keys()) & set(vintages[p_cur].keys()))
            shared_d = [s for s in shared if s.startswith(d)]
            max_abs_all = max((abs(vintages[p_cur][s][-1] - vintages[p_prev][s][-1]) for s in shared), default=None)
            max_abs_d = max((abs(vintages[p_cur][s][-1] - vintages[p_prev][s][-1]) for s in shared_d), default=None)
            dt_hours = round((parse_iso(p_cur) - parse_iso(p_prev)).total_seconds() / 3600.0, 3)
            consecutive_diffs.append(
                {
                    "prev_pub": p_prev,
                    "cur_pub": p_cur,
                    "gap_hours": dt_hours,
                    "n_shared_all": len(shared),
                    "max_abs_diff_all_MW": max_abs_all,
                    "n_shared_day_D": len(shared_d),
                    "max_abs_diff_day_D_MW": max_abs_d,
                    "identical_on_shared_all": (max_abs_all == 0.0 and len(shared) > 0),
                    "identical_on_day_D": (max_abs_d == 0.0 and len(shared_d) > 0),
                }
            )

        # Cross-check WINDFOR/stream against evolution for D T15:00:00Z (and 12:00:00Z on 2026-10-15)
        st15 = f"{d}T15:00:00Z"
        evo_15 = evo_maps[st15]
        stream_15 = {p: vintages[p][st15][-1] for p in pub_times if st15 in vintages[p]}
        evo_15_in_win = {p: v for p, v in evo_15.items() if f"{d_prev}T00:00:00Z" <= p <= cutoff_str}
        only_in_evo = sorted(set(evo_15_in_win.keys()) - set(stream_15.keys()))
        only_in_stream = sorted(set(stream_15.keys()) - set(evo_15_in_win.keys()))
        val_mismatches = [
            {"publishTime": p, "evo": evo_15_in_win[p], "stream": stream_15[p]}
            for p in sorted(set(evo_15_in_win.keys()) & set(stream_15.keys()))
            if evo_15_in_win[p] != stream_15[p]
        ]

        extra_12z_xcheck = None
        if d == "2026-10-15":
            st12 = "2026-10-15T12:00:00Z"
            evo_12 = {p: v for p, v in evo_maps[st12].items() if f"{d_prev}T00:00:00Z" <= p <= cutoff_str}
            stream_12 = {p: vintages[p][st12][-1] for p in pub_times if st12 in vintages[p]}
            extra_12z_xcheck = {
                "evo_vintages_in_window": len(evo_12),
                "stream_vintages_in_window": len(stream_12),
                "only_in_evo": sorted(set(evo_12) - set(stream_12)),
                "only_in_stream": sorted(set(stream_12) - set(evo_12)),
                "value_mismatches": [
                    {"publishTime": p, "evo": evo_12[p], "stream": stream_12[p]}
                    for p in sorted(set(evo_12) & set(stream_12))
                    if evo_12[p] != stream_12[p]
                ],
            }

        # 2b. FUELHH/stream for settlementDateFrom=D to D (and also D-1..D+1 to inspect UTC boundary on BST days!)
        q_fh_1 = urllib.parse.urlencode({"settlementDateFrom": d, "settlementDateTo": d, "fuelType": "WIND"})
        url_fh_1 = f"{BASE}/datasets/FUELHH/stream?{q_fh_1}"
        fh1_obj, fh1_meta = fetch_json(url_fh_1, f"fuelhh_single_{d}.json")
        receipt["requests"].append(fh1_meta)
        fh1_rows = extract_rows(fh1_obj)

        q_fh_3 = urllib.parse.urlencode({"settlementDateFrom": d_prev, "settlementDateTo": d_next, "fuelType": "WIND"})
        url_fh_3 = f"{BASE}/datasets/FUELHH/stream?{q_fh_3}"
        fh3_obj, fh3_meta = fetch_json(url_fh_3, f"fuelhh_3day_{d}.json")
        receipt["requests"].append(fh3_meta)
        fh3_rows = extract_rows(fh3_obj)

        fh_by_st: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        for r in fh3_rows:
            fh_by_st[r["startTime"]].append(r)

        fh_dups = {st: rs for st, rs in fh_by_st.items() if len(rs) > 1}
        fh_day_utc = sorted(st for st in fh_by_st if st.startswith(d))
        fh1_sts = sorted(r["startTime"] for r in fh1_rows)
        # Check publishTime lag on FUELHH
        fh_lags_min = [
            round((parse_iso(r["publishTime"]) - parse_iso(r["startTime"])).total_seconds() / 60.0, 2)
            for r in fh1_rows
        ]
        # Check FUELHH vs latest WINDFOR alignment (exact HH:00 vs avg(HH:00, HH:30) vs avg(HH-1:30, HH:00))
        latest_pub = pub_times[-1] if pub_times else None
        align_diag = {}
        if latest_pub:
            wf_lat = {st: vs[-1] for st, vs in vintages[latest_pub].items()}
            mae_exact = []
            mae_fwd_avg = []
            mae_bwd_avg = []
            for h in range(11, 24):
                st0 = f"{d}T{h:02d}:00:00Z"
                st_plus30 = f"{d}T{h:02d}:30:00Z"
                dt_h = parse_iso(st0)
                st_minus30 = (dt_h - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
                if st0 in wf_lat and st0 in fh_by_st and st_plus30 in fh_by_st and st_minus30 in fh_by_st:
                    g_wf = wf_lat[st0]
                    g0 = float(fh_by_st[st0][-1]["generation"])
                    gp = float(fh_by_st[st_plus30][-1]["generation"])
                    gm = float(fh_by_st[st_minus30][-1]["generation"])
                    mae_exact.append(abs(g_wf - g0))
                    mae_fwd_avg.append(abs(g_wf - 0.5 * (g0 + gp)))
                    mae_bwd_avg.append(abs(g_wf - 0.5 * (gm + g0)))
            align_diag = {
                "latest_pub_le_11Z": latest_pub,
                "n_hours_compared": len(mae_exact),
                "mae_vs_HH00_MW": round(sum(mae_exact) / len(mae_exact), 1) if mae_exact else None,
                "mae_vs_avg_HH00_HH30_MW": round(sum(mae_fwd_avg) / len(mae_fwd_avg), 1) if mae_fwd_avg else None,
                "mae_vs_avg_HHm30_HH00_MW": round(sum(mae_bwd_avg) / len(mae_bwd_avg), 1) if mae_bwd_avg else None,
                "wf_15Z_MW": wf_lat.get(f"{d}T15:00:00Z"),
                "fh_1500Z_MW": float(fh_by_st[f"{d}T15:00:00Z"][-1]["generation"]) if f"{d}T15:00:00Z" in fh_by_st else None,
                "fh_1530Z_MW": float(fh_by_st[f"{d}T15:30:00Z"][-1]["generation"]) if f"{d}T15:30:00Z" in fh_by_st else None,
                "wf_18Z_MW": wf_lat.get(f"{d}T18:00:00Z"),
                "fh_1800Z_MW": float(fh_by_st[f"{d}T18:00:00Z"][-1]["generation"]) if f"{d}T18:00:00Z" in fh_by_st else None,
            }

        receipt["date_reports"][d] = {
            "windfor_stream_rows": len(wf_rows),
            "windfor_fields": sorted(wf_rows[0].keys()) if wf_rows else [],
            "windfor_n_vintages_Dprev00Z_to_D11Z": len(pub_times),
            "windfor_publishTimes": pub_times,
            "windfor_duplicate_pub_start_pairs": len(dup_pairs),
            "windfor_vintages_summary": vintage_summaries[-6:],
            "windfor_consecutive_diffs_tail": consecutive_diffs[-6:],
            "windfor_identical_consecutive_count": sum(1 for x in consecutive_diffs if x["identical_on_day_D"]),
            "xcheck_stream_vs_evo_15Z": {
                "evo_vintages_in_window": len(evo_15_in_win),
                "stream_vintages_in_window": len(stream_15),
                "only_in_evo": only_in_evo,
                "only_in_stream": only_in_stream,
                "value_mismatches": val_mismatches,
            },
            "xcheck_stream_vs_evo_12Z": extra_12z_xcheck,
            "fuelhh_single_date_rows": len(fh1_rows),
            "fuelhh_fields": sorted(fh1_rows[0].keys()) if fh1_rows else [],
            "fuelhh_single_date_min_startTime": fh1_sts[0] if fh1_sts else None,
            "fuelhh_single_date_max_startTime": fh1_sts[-1] if fh1_sts else None,
            "fuelhh_utc_day_halfhours_from_3day": len(fh_day_utc),
            "fuelhh_3day_duplicate_startTimes": len(fh_dups),
            "fuelhh_publish_lag_min_minmax": [min(fh_lags_min), max(fh_lags_min)] if fh_lags_min else None,
            "windfor_vs_fuelhh_alignment": align_diag,
        }
        print(
            f"[DATE {d}] WF_vintages={len(pub_times)} identical_consec={sum(1 for x in consecutive_diffs if x['identical_on_day_D'])} "
            f"xcheck15(evo={len(evo_15_in_win)},str={len(stream_15)},mm={len(val_mismatches)},onlyE={len(only_in_evo)},onlyS={len(only_in_stream)}) | "
            f"FH_1d={len(fh1_rows)} [{fh1_sts[0]}..{fh1_sts[-1]}] FH_utc_day={len(fh_day_utc)} dups={len(fh_dups)} | "
            f"align={align_diag}"
        )

    out_path = ROOT / "STAGE0_DATA_FEASIBILITY_RECEIPT.json"
    out_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("\nSaved STAGE0_DATA_FEASIBILITY_RECEIPT.json | SHA-256:", hashlib.sha256(out_path.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
