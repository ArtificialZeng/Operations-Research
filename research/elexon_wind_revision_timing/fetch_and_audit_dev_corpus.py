"""
Stage-0 Dev Corpus Fetcher & Authoritative Data-Integrity Audit (2024-10-15 .. 2026-05-31).

Strictly respects held-out isolation:
  - Downloads ONLY the Dev span (2024-10-14 .. 2026-06-01) from official public Elexon BMRS:
      * datasets/WINDFOR/stream (by publishDateTimeFrom/To; NEVER latest-only)
      * datasets/FUELHH/stream (fuelType=WIND)
  - Does NOT download Held-Out dates (2026-06-04 .. 2026-11-23).
  - Archives exact request URLs, HTTP status, timestamps, byte counts, and SHA-256 hashes.
  - Cross-checks WINDFOR/stream against forecast/generation/wind/evolution on 6 stratified Dev dates
    (including UK DST clock-change days).
  - Audits vintage completeness, duplicate/correction counts, identical intraday revisions,
    UTC/BST alignment, monthly 2024-2026 stability, and Dev-Train-1-only (2024-10-15..2025-07-31)
    ramp prevalence and signed timing-shift variation (zero peeking at Dev-Val outcomes!).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import pathlib
import time
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

import numpy as np


ROOT = pathlib.Path(__file__).resolve().parent
RAW_DEV = ROOT / "raw_dev_chunks"
RAW_DEV.mkdir(parents=True, exist_ok=True)
BASE = "https://data.elexon.co.uk/bmrs/api/v1"

# Dev span: 2024-10-15 (exact first day of 73-pt WINDFOR regime) through 2026-05-31 (594 days)
# Held-out span (2026-06-04 .. 2026-11-23) is NOT downloaded here.
DEV_START = date(2024, 10, 15)
DEV_END = date(2026, 5, 31)
DEV_TRAIN1_END = date(2025, 7, 31)  # Used ONLY for label-based prevalence/alignment check (zero Val peeking)


def month_chunks(start_d: date, end_d: date) -> List[Tuple[date, date]]:
    chunks = []
    cur = start_d
    while cur <= end_d:
        nxt = min(end_d, cur + timedelta(days=29))
        chunks.append((cur, nxt))
        cur = nxt + timedelta(days=1)
    return chunks


def fetch_cached(url: str, path: pathlib.Path) -> Tuple[Any, Dict[str, Any]]:
    if path.exists():
        raw = path.read_bytes()
        meta = {
            "url": url,
            "file": path.name,
            "cached": True,
            "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest(),
        }
        return json.loads(raw.decode("utf-8")), meta
    last_err = None
    for attempt in range(4):
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Python-urllib/3.12 (academic-research)", "Accept": "application/json"},
            )
            t0 = datetime.now(timezone.utc).isoformat()
            with urllib.request.urlopen(req, timeout=60) as resp:
                raw = resp.read()
                status = resp.status
            path.write_bytes(raw)
            meta = {
                "url": url,
                "file": path.name,
                "cached": False,
                "fetched_utc": t0,
                "http_status": status,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            }
            return json.loads(raw.decode("utf-8")), meta
        except Exception as e:
            last_err = e
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError(f"Failed fetching {url}: {last_err}")


def extract_rows(obj: Any) -> List[Dict[str, Any]]:
    if isinstance(obj, list):
        return obj
    if isinstance(obj, dict) and isinstance(obj.get("data"), list):
        return obj["data"]
    raise ValueError(f"Unexpected JSON type {type(obj)}")


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def main() -> None:
    t0 = time.perf_counter()
    # Need D-1 for WINDFOR publish window & FUELHH BST boundary, and D+1 for FUELHH BST boundary
    fetch_start = DEV_START - timedelta(days=1)
    fetch_end = DEV_END + timedelta(days=1)
    chunks = month_chunks(fetch_start, fetch_end)
    print(f"Fetching {len(chunks)} chunks covering {fetch_start} .. {fetch_end} (Dev={DEV_START}..{DEV_END})", flush=True)

    req_log: List[Dict[str, Any]] = []
    # Store WINDFOR: vintages[pub_iso][start_iso] = list of generation values (to detect duplicates!)
    wf_vintages: Dict[str, Dict[str, List[float]]] = defaultdict(lambda: defaultdict(list))
    # Store FUELHH: fuel_by_st[start_iso] = list of (publishTime, generation, settlementDate, settlementPeriod)
    fh_by_st: Dict[str, List[Tuple[str, float, str, int]]] = defaultdict(list)

    for idx, (c0, c1) in enumerate(chunks, start=1):
        # WINDFOR chunk
        q_wf = urllib.parse.urlencode(
            {
                "publishDateTimeFrom": f"{c0}T00:00:00Z",
                "publishDateTimeTo": f"{c1}T23:59:59Z",
            }
        )
        wf_url = f"{BASE}/datasets/WINDFOR/stream?{q_wf}"
        wf_obj, wf_meta = fetch_cached(wf_url, RAW_DEV / f"windfor_{c0}_{c1}.json")
        req_log.append(wf_meta)
        wf_rows = extract_rows(wf_obj)
        for r in wf_rows:
            wf_vintages[r["publishTime"]][r["startTime"]].append(float(r["generation"]))

        # FUELHH chunk
        q_fh = urllib.parse.urlencode(
            {
                "settlementDateFrom": str(c0),
                "settlementDateTo": str(c1),
                "fuelType": "WIND",
            }
        )
        fh_url = f"{BASE}/datasets/FUELHH/stream?{q_fh}"
        fh_obj, fh_meta = fetch_cached(fh_url, RAW_DEV / f"fuelhh_{c0}_{c1}.json")
        req_log.append(fh_meta)
        fh_rows = extract_rows(fh_obj)
        for r in fh_rows:
            fh_by_st[r["startTime"]].append(
                (r["publishTime"], float(r["generation"]), str(r["settlementDate"]), int(r["settlementPeriod"]))
            )
        print(f"  [{idx:02d}/{len(chunks)}] {c0}..{c1} | WF rows={len(wf_rows):5d} | FH rows={len(fh_rows):4d}", flush=True)

    # Deduplication & anomaly check on raw streams
    wf_dup_exact = 0
    wf_dup_conflict = 0
    wf_clean: Dict[str, Dict[str, float]] = {}
    for p, smap in wf_vintages.items():
        wf_clean[p] = {}
        for st, vals in smap.items():
            if len(vals) > 1:
                if len(set(vals)) == 1:
                    wf_dup_exact += 1
                else:
                    wf_dup_conflict += 1
            wf_clean[p][st] = vals[-1]

    fh_dup_exact = 0
    fh_dup_conflict = 0
    fh_clean: Dict[str, Tuple[str, float]] = {}
    fh_lags_min: List[float] = []
    for st, recs in fh_by_st.items():
        # Sort by publishTime
        recs_sorted = sorted(recs, key=lambda x: x[0])
        if len(recs_sorted) > 1:
            gens = {x[1] for x in recs_sorted}
            if len(gens) == 1:
                fh_dup_exact += 1
            else:
                fh_dup_conflict += 1
        pub, gen, _, _ = recs_sorted[-1]
        fh_clean[st] = (pub, gen)
        fh_lags_min.append((parse_iso(pub) - parse_iso(st)).total_seconds() / 60.0)

    # Cross-check WINDFOR/stream against evolution on 6 stratified Dev dates (including UK clock-change days!)
    xcheck_dates = [
        "2024-10-27",  # BST -> GMT clock change
        "2025-01-20",  # Winter GMT
        "2025-03-30",  # GMT -> BST clock change
        "2025-07-10",  # Summer BST
        "2025-10-26",  # BST -> GMT clock change
        "2026-03-29",  # GMT -> BST clock change
    ]
    evo_xchecks = {}
    for d in xcheck_dates:
        st15 = f"{d}T15:00:00Z"
        q_ev = urllib.parse.urlencode({"startTime": st15, "format": "json"})
        ev_url = f"{BASE}/forecast/generation/wind/evolution?{q_ev}"
        ev_obj, ev_meta = fetch_cached(ev_url, RAW_DEV / f"evo_xcheck_{d}T15Z.json")
        req_log.append(ev_meta)
        ev_rows = extract_rows(ev_obj)
        d_prev = str(date.fromisoformat(d) - timedelta(days=1))
        cutoff = f"{d}T11:00:00Z"
        ev_map = {r["publishTime"]: float(r["generation"]) for r in ev_rows if f"{d_prev}T00:00:00Z" <= r["publishTime"] <= cutoff}
        st_map = {p: wf_clean[p][st15] for p in wf_clean if f"{d_prev}T00:00:00Z" <= p <= cutoff and st15 in wf_clean[p]}
        mismatches = [p for p in set(ev_map) & set(st_map) if ev_map[p] != st_map[p]]
        evo_xchecks[d] = {
            "evo_n": len(ev_map),
            "stream_n": len(st_map),
            "only_in_evo": sorted(set(ev_map) - set(st_map)),
            "only_in_stream": sorted(set(st_map) - set(ev_map)),
            "n_value_mismatches": len(mismatches),
        }

    # Index sorted publishTimes for fast per-day lookup
    all_pubs = sorted(wf_clean.keys())
    all_pubs_dt = [parse_iso(p) for p in all_pubs]

    # Per-day audit across all 594 Dev days (2024-10-15 .. 2026-05-31)
    # Fixed delivery search grid for steepest 3h drop: start hours s in [11, 12, 13, 14, 15, 16, 17, 18]
    # covering 3h drops [s -> s+3] from [11->14] through [18->21] UTC (centered around primary [15->18] UTC!)
    # Requires hourly forecast points 11:00Z .. 21:00Z (11 hours).
    search_starts = list(range(11, 19))  # 11..18 -> endpoints 14..21
    req_hours = list(range(11, 22))      # 11..21 UTC inclusive (11 hourly points)

    missing_reasons = Counter()
    gap_hist_2latest = Counter()
    gap_hist_sep4h = Counter()
    identical_latest_pair = 0
    identical_any_day_consec = 0
    monthly_stats: Dict[str, Dict[str, Any]] = defaultdict(lambda: {"days": 0, "valid": 0, "n_pubs_list": [], "ident_latest": 0})

    # Dev-Train-1-only diagnostics (NO peeking at Dev-Val 1 or Dev-Val 2 outcomes!)
    tr1_align_err = {"HH00": [], "avg_fwd": [], "avg_bwd": []}
    tr1_bias_wf_minus_fh = []
    tr1_bias_by_month = defaultdict(list)
    tr1_y_raw_hh00 = []
    tr1_y_raw_avg_fwd = []
    # Check signed shift distribution on Dev-Train-1 ONLY (label-free timing shift check for two candidate vintage pairs!)
    # Pair A: two latest distinct complete vintages (typically 2h apart: 09:30/07:30 GMT, 10:30/08:30 BST)
    # Pair B: latest complete vintage vs latest distinct complete vintage >= 4h earlier (typically 5h apart: 09:30/04:30 GMT, 10:30/05:30 BST)
    # Pair C: latest complete vintage vs latest distinct complete vintage >= 10h earlier (overnight/previous evening: ~11-15h apart)
    shift_stats_tr1 = {"pair_latest2": [], "pair_ge4h": [], "pair_ge10h": []}

    valid_days = 0
    total_days = 0
    cur_d = DEV_START
    while cur_d <= DEV_END:
        total_days += 1
        ds = str(cur_d)
        ym = ds[:7]
        monthly_stats[ym]["days"] += 1
        cutoff_dt = datetime(cur_d.year, cur_d.month, cur_d.day, 11, 0, 0, tzinfo=timezone.utc)
        win_start_dt = cutoff_dt - timedelta(hours=36)
        # Candidate vintages published in [cutoff - 36h, cutoff] that have all 11 required hourly points D 11:00Z..21:00Z
        req_sts = [f"{ds}T{h:02d}:00:00Z" for h in req_hours]
        cands = []
        for p, pdt in zip(all_pubs, all_pubs_dt):
            if win_start_dt <= pdt <= cutoff_dt:
                smap = wf_clean[p]
                if all(st in smap for st in req_sts):
                    vec = [smap[st] for st in req_sts]
                    cands.append((p, pdt, vec))
        # Check same-day count of vintages <= 11:00Z
        same_day_cands = [c for c in cands if c[0].startswith(ds)]
        monthly_stats[ym]["n_pubs_list"].append(len(same_day_cands))

        # Check FUELHH completeness for D 10:00Z..21:30Z (for causal lag + target + alignment)
        fh_req_sts = [f"{ds}T{h:02d}:{m:02d}:00Z" for h in range(10, 22) for m in (0, 30)]
        fh_ok = all(st in fh_clean for st in fh_req_sts)
        # Also verify causal FUELHH lag at 10:30Z has publishTime <= 11:00Z
        fh_1030_causal = (f"{ds}T10:30:00Z" in fh_clean) and (fh_clean[f"{ds}T10:30:00Z"][0] <= f"{ds}T11:00:00Z")

        if len(cands) < 2:
            missing_reasons["lt2_complete_windfor_vintages"] += 1
            cur_d += timedelta(days=1)
            continue
        if not fh_ok:
            missing_reasons["missing_fuelhh_halfhours"] += 1
            cur_d += timedelta(days=1)
            continue
        if not fh_1030_causal:
            missing_reasons["fuelhh_1030_not_causal_le_11Z"] += 1

        # Count identical consecutive vintages among same-day candidates
        for i in range(1, len(cands)):
            if cands[i][2] == cands[i - 1][2]:
                identical_any_day_consec += 1

        v_new = cands[-1]
        # Latest strictly distinct vintage (non-identical on D 11Z..21Z)
        if cands[-1][2] == cands[-2][2]:
            identical_latest_pair += 1
            monthly_stats[ym]["ident_latest"] += 1
        distinct_prior = [c for c in cands[:-1] if c[2] != v_new[2]]
        if not distinct_prior:
            missing_reasons["all_prior_vintages_identical_to_latest"] += 1
            cur_d += timedelta(days=1)
            continue

        v_old_latest = distinct_prior[-1]
        gap_latest = round((v_new[1] - v_old_latest[1]).total_seconds() / 3600.0, 2)
        gap_hist_2latest[gap_latest] += 1

        sep4 = [c for c in distinct_prior if (v_new[1] - c[1]).total_seconds() >= 4 * 3600 - 60]
        v_old_4h = sep4[-1] if sep4 else None
        if v_old_4h:
            gap_hist_sep4h[round((v_new[1] - v_old_4h[1]).total_seconds() / 3600.0, 2)] += 1
        else:
            missing_reasons["no_distinct_vintage_ge4h_prior"] += 1

        sep10 = [c for c in distinct_prior if (v_new[1] - c[1]).total_seconds() >= 10 * 3600 - 60]
        v_old_10h = sep10[-1] if sep10 else None

        valid_days += 1
        monthly_stats[ym]["valid"] += 1

        # Train-1-only diagnostics (STRICTLY cur_d <= DEV_TRAIN1_END = 2025-07-31!)
        if cur_d <= DEV_TRAIN1_END:
            # Alignment check on 11:00..21:00Z
            for h_idx, h in enumerate(req_hours):
                g_wf = v_new[2][h_idx]
                g0 = fh_clean[f"{ds}T{h:02d}:00:00Z"][1]
                gp = fh_clean[f"{ds}T{h:02d}:30:00Z"][1]
                dt_m = datetime(cur_d.year, cur_d.month, cur_d.day, h, 0, tzinfo=timezone.utc) - timedelta(minutes=30)
                gm = fh_clean[dt_m.strftime("%Y-%m-%dT%H:%M:%SZ")][1]
                tr1_align_err["HH00"].append(abs(g_wf - g0))
                tr1_align_err["avg_fwd"].append(abs(g_wf - 0.5 * (g0 + gp)))
                tr1_align_err["avg_bwd"].append(abs(g_wf - 0.5 * (gm + g0)))
                tr1_bias_wf_minus_fh.append(g_wf - 0.5 * (g0 + gp))
                tr1_bias_by_month[ym].append(g_wf - 0.5 * (g0 + gp))

            # Actual 15:00 -> 18:00 UTC 3-hour change (negative = wind drop!)
            y_hh00 = fh_clean[f"{ds}T18:00:00Z"][1] - fh_clean[f"{ds}T15:00:00Z"][1]
            a15_fwd = 0.5 * (fh_clean[f"{ds}T15:00:00Z"][1] + fh_clean[f"{ds}T15:30:00Z"][1])
            a18_fwd = 0.5 * (fh_clean[f"{ds}T18:00:00Z"][1] + fh_clean[f"{ds}T18:30:00Z"][1])
            tr1_y_raw_hh00.append(y_hh00)
            tr1_y_raw_avg_fwd.append(a18_fwd - a15_fwd)

            # Signed displacement of steepest 3h drop over fixed search grid s in 11..18 (earliest tie-break)
            def argmin_3h_drop(vec11: List[float]) -> int:
                drops = [vec11[i + 3] - vec11[i] for i in range(8)]  # s=11..18
                min_val = min(drops)
                for i, dv in enumerate(drops):
                    if dv == min_val:
                        return 11 + i
                return 11

            t_new = argmin_3h_drop(v_new[2])
            shift_stats_tr1["pair_latest2"].append(t_new - argmin_3h_drop(v_old_latest[2]))
            if v_old_4h:
                shift_stats_tr1["pair_ge4h"].append(t_new - argmin_3h_drop(v_old_4h[2]))
            if v_old_10h:
                shift_stats_tr1["pair_ge10h"].append(t_new - argmin_3h_drop(v_old_10h[2]))

        cur_d += timedelta(days=1)

    # Summarize Train-1-only quantiles & shift distribution
    y_arr = np.array(tr1_y_raw_avg_fwd)
    y_hh00_arr = np.array(tr1_y_raw_hh00)

    def summarize_shifts(vals: List[int]) -> Dict[str, Any]:
        c = Counter(vals)
        n = len(vals)
        return {
            "n": n,
            "frac_nonzero": round(sum(1 for v in vals if v != 0) / n, 4) if n else 0.0,
            "frac_pos_later": round(sum(1 for v in vals if v > 0) / n, 4) if n else 0.0,
            "frac_neg_earlier": round(sum(1 for v in vals if v < 0) / n, 4) if n else 0.0,
            "mean": round(float(np.mean(vals)), 3) if n else 0.0,
            "std": round(float(np.std(vals)), 3) if n else 0.0,
            "counts": {str(k): int(c[k]) for k in sorted(c)},
        }

    audit = {
        "dev_span": [str(DEV_START), str(DEV_END)],
        "held_out_untouched_span": ["2026-06-04", "2026-11-23"],
        "dev_train1_end_for_threshold_and_alignment": str(DEV_TRAIN1_END),
        "wall_time_s": round(time.perf_counter() - t0, 2),
        "n_chunks_fetched": len(chunks),
        "total_dev_days": total_days,
        "valid_complete_dev_days": valid_days,
        "missing_reasons": dict(missing_reasons),
        "windfor_duplicate_exact_count": wf_dup_exact,
        "windfor_duplicate_value_conflict_count": wf_dup_conflict,
        "fuelhh_duplicate_exact_count": fh_dup_exact,
        "fuelhh_duplicate_value_conflict_count": fh_dup_conflict,
        "fuelhh_publish_lag_min_minmax": [round(min(fh_lags_min), 2), round(max(fh_lags_min), 2)],
        "identical_latest_pair_days": identical_latest_pair,
        "identical_any_consecutive_vintages": identical_any_day_consec,
        "gap_hours_latest2_distinct_counts": {str(k): int(v) for k, v in sorted(gap_hist_2latest.items())},
        "gap_hours_ge4h_distinct_counts": {str(k): int(v) for k, v in sorted(gap_hist_sep4h.items())},
        "evolution_crosscheck_6_dates": evo_xchecks,
        "monthly_coverage_summary": {
            ym: {
                "days": st["days"],
                "valid": st["valid"],
                "same_day_pubs_le_11Z_counts": dict(Counter(st["n_pubs_list"])),
                "ident_latest": st["ident_latest"],
            }
            for ym, st in sorted(monthly_stats.items())
        },
        "dev_train1_only_diagnostics": {
            "n_days": len(y_arr),
            "alignment_mae_MW": {k: round(float(np.mean(v)), 1) for k, v in tr1_align_err.items()},
            "mean_bias_wf_minus_fh_avgfwd_MW": round(float(np.mean(tr1_bias_wf_minus_fh)), 1),
            "monthly_mean_bias_train1_MW": {ym: round(float(np.mean(vs)), 1) for ym, vs in sorted(tr1_bias_by_month.items())},
            "actual_15_to_18_avgfwd_quantiles_MW": {
                f"q{int(q*100):02d}": round(float(np.quantile(y_arr, q)), 1)
                for q in [0.05, 0.10, 0.15, 0.20, 0.25, 0.50]
            },
            "actual_15_to_18_hh00_quantiles_MW": {
                f"q{int(q*100):02d}": round(float(np.quantile(y_hh00_arr, q)), 1)
                for q in [0.05, 0.10, 0.15, 0.20, 0.25, 0.50]
            },
            "signed_shift_distribution_train1": {k: summarize_shifts(v) for k, v in shift_stats_tr1.items()},
        },
        "request_log": req_log,
    }

    out_p = ROOT / "STAGE0_DEV_DATA_AUDIT.json"
    out_p.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print("\n=== STAGE-0 DEV CORPUS AUDIT COMPLETE ===")
    print(f"Days: {valid_days}/{total_days} valid | Missing: {dict(missing_reasons)}")
    print(f"WF dups: exact={wf_dup_exact}, conflict={wf_dup_conflict} | FH dups: exact={fh_dup_exact}, conflict={fh_dup_conflict}")
    print(f"Identical latest pair days={identical_latest_pair} | Identical any consec={identical_any_day_consec}")
    print(f"Gap latest2: {audit['gap_hours_latest2_distinct_counts']}")
    print(f"Gap >=4h:    {audit['gap_hours_ge4h_distinct_counts']}")
    print(f"Evo xchecks: {evo_xchecks}")
    print(f"Train-1 align MAE (MW): {audit['dev_train1_only_diagnostics']['alignment_mae_MW']}")
    print(f"Train-1 15->18Z quantiles (avg_fwd MW): {audit['dev_train1_only_diagnostics']['actual_15_to_18_avgfwd_quantiles_MW']}")
    print(f"Train-1 signed shift (latest2): {audit['dev_train1_only_diagnostics']['signed_shift_distribution_train1']['pair_latest2']}")
    print(f"Train-1 signed shift (>=4h):    {audit['dev_train1_only_diagnostics']['signed_shift_distribution_train1']['pair_ge4h']}")
    print(f"Train-1 signed shift (>=10h):   {audit['dev_train1_only_diagnostics']['signed_shift_distribution_train1']['pair_ge10h']}")
    print("Audit SHA-256:", hashlib.sha256(out_p.read_bytes()).hexdigest())


if __name__ == "__main__":
    main()
