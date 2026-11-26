"""Fetch ALL registered Phase II/III Industry Interventional trials (2017-2025) from ClinicalTrials.gov v2.

Includes ongoing, recruiting, active-not-recruiting, terminated, withdrawn, and completed trials
WITHOUT posted results (HasResults = true OR false) to eliminate post-2022 results-posting
right-censoring in the February 24, 2022 Russia-Ukraine War reallocation analysis.

Exports:
  - data/processed/ctgov_all_registered_war_2017_2025.parquet
  - data/processed/war_all_registered_summary.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")
SCRIPTS_DIR = BASE_DIR / "scripts"
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
QUERY_TERM = (
    "(AREA[Phase]PHASE2 OR AREA[Phase]PHASE3) "
    "AND AREA[StudyType]INTERVENTIONAL "
    "AND AREA[LeadSponsorClass]INDUSTRY "
    "AND AREA[StartDate]RANGE[2017-01-01,2025-12-31]"
)
FIELD_LIST = [
    "NCTId",
    "StartDate",
    "LeadSponsorName",
    "Phase",
    "LocationCountry",
    "HasResults",
    "OverallStatus",
    "EnrollmentCount",
    "DesignAllocation",
    "Condition",
]
FIELDS = ",".join(FIELD_LIST)


def _load_build_panel():
    spec = importlib.util.spec_from_file_location("build_panel_war", SCRIPTS_DIR / "02_build_panel.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_panel_war"] = mod
    spec.loader.exec_module(mod)
    return mod


def fetch_page(
    session: requests.Session,
    page_token: str | None,
    page_size: int,
    count_total: bool = False,
    max_retries: int = 5,
) -> dict:
    params: dict[str, str | int] = {
        "query.term": QUERY_TERM,
        "fields": FIELDS,
        "pageSize": page_size,
    }
    if count_total:
        params["countTotal"] = "true"
    if page_token:
        params["pageToken"] = page_token

    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(CTGOV_URL, params=params, timeout=45)
            if resp.status_code == 200:
                return resp.json()
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = min(30, 2 ** attempt)
                print(f"  [RETRY {attempt}/{max_retries}] HTTP {resp.status_code}, sleeping {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        except requests.RequestException as exc:
            wait = min(30, 2 ** attempt)
            print(f"  [RETRY {attempt}/{max_retries}] Network error: {exc}, sleeping {wait}s...", flush=True)
            time.sleep(wait)
    raise RuntimeError("Exceeded max_retries fetching all-registered CT.gov war cohort")


def parse_registered_study(st: dict, build_mod) -> dict | None:
    ps = st.get("protocolSection") or {}
    nct = (ps.get("identificationModule") or {}).get("nctId")
    if not nct:
        return None

    status_mod = ps.get("statusModule") or {}
    overall_status = (status_mod.get("overallStatus") or "").upper()
    start_iso, start_yr, _ = build_mod.parse_iso_date((status_mod.get("startDateStruct") or {}).get("date"))
    if start_iso is None or np.isnan(start_yr) or not (2017 <= int(start_yr) <= 2025):
        return None

    design = ps.get("designModule") or {}
    phases = [p.upper() for p in (design.get("phases") or [])]
    has_p3 = "PHASE3" in phases
    has_p2 = "PHASE2" in phases
    if not (has_p2 or has_p3):
        return None
    phase_group = "PHASE2_3" if (has_p2 and has_p3) else ("PHASE3" if has_p3 else "PHASE2")

    allocation = ((design.get("designInfo") or {}).get("allocation") or "").upper()
    is_randomized = int(allocation == "RANDOMIZED")
    enroll_raw = (design.get("enrollmentInfo") or {}).get("count")
    enrollment = float(enroll_raw) if (enroll_raw is not None and enroll_raw > 0) else np.nan

    smod = (ps.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}
    sponsor_nm = re.sub(r"\s+", " ", (smod.get("name") or "").strip().upper())[:60]

    conds = (ps.get("conditionsModule") or {}).get("conditions") or []
    therapeutic_area = build_mod.map_therapeutic_area(conds, [], [])

    locs = (ps.get("contactsLocationsModule") or {}).get("locations") or []
    countries = [loc.get("country").strip() for loc in locs if loc.get("country")]
    n_sites = len(countries)
    n_countries = len(set(countries))
    reg_shares = build_mod.compute_region_shares(countries) if n_sites > 0 else {}

    has_results = int(bool(st.get("hasResults")))

    rec = {
        "nct_id": nct,
        "start_date": start_iso,
        "start_year": int(start_yr),
        "post_war_2022": int(start_iso >= "2022-02-24"),
        "overall_status": overall_status,
        "has_results": has_results,
        "phase_group": phase_group,
        "is_phase3": int(has_p3),
        "is_randomized": is_randomized,
        "sponsor_nm": sponsor_nm,
        "therapeutic_area": therapeutic_area,
        "enrollment": enrollment,
        "n_sites": int(n_sites),
        "n_countries": int(n_countries),
        "has_ru_ua_site": int(any(c in build_mod.RU_UA_ONLY_SET for c in countries)),
        "has_ru_site": int(any(c in {"Russia", "Russian Federation"} for c in countries)),
        "has_ua_site": int("Ukraine" in countries),
    }
    for k in ["us_sh", "we_sh", "eu_east_sh", "ru_ua_sh", "ru_ua_strict_sh", "ee_sh", "latam_sh", "asia_sh", "other_sh"]:
        rec[k] = float(reg_shares.get(k, np.nan))
    return rec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--max-pages", type=int, default=50)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out_parquet = PROC_DIR / "ctgov_all_registered_war_2017_2025.parquet"
    out_summary = PROC_DIR / "war_all_registered_summary.json"
    if out_parquet.exists() and out_summary.exists() and not args.force:
        print(f"[SKIP] {out_parquet.name} already cached (use --force to re-fetch).", flush=True)
        return 0

    build_mod = _load_build_panel()
    session = requests.Session()
    session.headers.update({"User-Agent": "D30-Boost-WarCohort-AllRegistered/2.0"})

    rows: list[dict] = []
    seen_nct: set[str] = set()
    page_token: str | None = None
    total_expected: int | None = None
    total_raw = 0
    page_idx = 0
    t_start = time.time()

    print(f"[START] Fetching ALL registered Phase 2/3 Industry trials 2017-2025 (pageSize={args.page_size})...", flush=True)
    while page_idx < args.max_pages:
        page_idx += 1
        data = fetch_page(session, page_token=page_token, page_size=args.page_size, count_total=(page_idx == 1))
        if page_idx == 1:
            total_expected = data.get("totalCount")
            print(f"  Reported totalCount = {total_expected}", flush=True)
        studies = data.get("studies", [])
        next_token = data.get("nextPageToken")
        total_raw += len(studies)
        for st in studies:
            rec = parse_registered_study(st, build_mod)
            if rec is not None and rec["nct_id"] not in seen_nct:
                seen_nct.add(rec["nct_id"])
                rows.append(rec)
        print(
            f"  Page {page_idx:02d}: +{len(studies):4d} raw (cum_raw={total_raw:5d}/{total_expected}, parsed={len(rows):5d})",
            flush=True,
        )
        if not next_token or len(studies) == 0:
            break
        page_token = next_token
        time.sleep(0.15)

    df = pd.DataFrame(rows)
    df["log_enroll"] = np.log(df["enrollment"].where(df["enrollment"] > 0))
    df["log_sites"] = np.log(df["n_sites"].where(df["n_sites"] > 0))
    df["log_countries"] = np.log(df["n_countries"].where(df["n_countries"] > 0))
    df.to_parquet(out_parquet, index=False)
    sha = hashlib.sha256(out_parquet.read_bytes()).hexdigest()

    # Summary statistics across MRCTs (n_sites >= 5, n_countries >= 3)
    mrct = df[(df["n_sites"] >= 5) & (df["n_countries"] >= 3)]
    by_yr = []
    for yr in range(2017, 2026):
        g = mrct[mrct["start_year"] == yr]
        by_yr.append({
            "year": yr,
            "n_all_registered_trials": int((df["start_year"] == yr).sum()),
            "n_mrct": len(g),
            "n_with_ru_ua": int(g["has_ru_ua_site"].sum()),
            "pct_with_ru_ua": round(100.0 * float(g["has_ru_ua_site"].mean()), 2) if len(g) else None,
            "pct_has_results": round(100.0 * float(g["has_results"].mean()), 2) if len(g) else None,
            "mean_ru_ua_strict_pct": round(100.0 * float(g["ru_ua_strict_sh"].mean()), 3) if len(g) else None,
            "mean_us_pct": round(100.0 * float(g["us_sh"].mean()), 3) if len(g) else None,
        })

    summary = {
        "fetched_utc": datetime.now(UTC).isoformat(),
        "endpoint": CTGOV_URL,
        "query_term": QUERY_TERM,
        "fields": FIELDS,
        "total_expected": total_expected,
        "total_raw_fetched": int(total_raw),
        "parsed_unique_studies": len(df),
        "parsed_mrct_ge5sites_ge3countries": len(mrct),
        "elapsed_seconds": round(time.time() - t_start, 2),
        "annual_mrct_overview_2017_2025": by_yr,
        "sha256": sha,
    }
    out_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("[DONE] All-registered war cohort saved:", json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
