"""Fetch complete ClinicalTrials.gov v2 Industry Phase 2 + Phase 3 universe with results.

Pulls all interventional Industry-sponsored Phase 2 and/or Phase 3 trials with posted results
(all overall statuses so primary analyses use COMPLETED while sensitivity checks test TERMINATED
survivorship bias), saving compact gzipped raw JSON pages + SHA-256 fetch manifest.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = BASE_DIR / "data" / "raw_ctgov"
RAW_DIR.mkdir(parents=True, exist_ok=True)

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
QUERY_TERM = (
    "(AREA[Phase]PHASE2 OR AREA[Phase]PHASE3) "
    "AND AREA[StudyType]INTERVENTIONAL "
    "AND AREA[LeadSponsorClass]INDUSTRY "
    "AND AREA[HasResults]true"
)

# Concise field selection omitting bulky per-term stats arrays while retaining full
# eventGroups, frequencyThreshold, assessmentType, organSystem, terms, conditions,
# interventions, locations, and standardized MeSH browse modules.
FIELD_LIST = [
    "protocolSection.identificationModule.nctId",
    "protocolSection.identificationModule.briefTitle",
    "protocolSection.identificationModule.officialTitle",
    "protocolSection.statusModule.overallStatus",
    "protocolSection.statusModule.startDateStruct",
    "protocolSection.statusModule.primaryCompletionDateStruct",
    "protocolSection.statusModule.completionDateStruct",
    "protocolSection.statusModule.resultsFirstPostDateStruct",
    "protocolSection.designModule",
    "protocolSection.conditionsModule",
    "protocolSection.armsInterventionsModule.interventions",
    "protocolSection.sponsorCollaboratorsModule.leadSponsor",
    "protocolSection.contactsLocationsModule.locations",
    "resultsSection.adverseEventsModule.frequencyThreshold",
    "resultsSection.adverseEventsModule.timeFrame",
    "resultsSection.adverseEventsModule.eventGroups",
    "resultsSection.adverseEventsModule.otherEvents.term",
    "resultsSection.adverseEventsModule.otherEvents.organSystem",
    "resultsSection.adverseEventsModule.otherEvents.assessmentType",
    "resultsSection.adverseEventsModule.seriousEvents.term",
    "resultsSection.adverseEventsModule.seriousEvents.organSystem",
    "resultsSection.adverseEventsModule.seriousEvents.assessmentType",
    "derivedSection.conditionBrowseModule.meshes",
    "derivedSection.conditionBrowseModule.ancestors",
    "derivedSection.interventionBrowseModule.meshes",
]
FIELDS = ",".join(FIELD_LIST)


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
                print(
                    f"  [RETRY {attempt}/{max_retries}] HTTP {resp.status_code}, sleeping {wait}s...",
                    flush=True,
                )
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:400]}")
        except requests.RequestException as exc:
            wait = min(30, 2 ** attempt)
            print(
                f"  [RETRY {attempt}/{max_retries}] Network error: {exc}, sleeping {wait}s...",
                flush=True,
            )
            time.sleep(wait)
    raise RuntimeError("Exceeded max_retries fetching ClinicalTrials.gov page")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page-size", type=int, default=500)
    parser.add_argument("--max-pages", type=int, default=100)
    parser.add_argument("--test-one-page", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    manifest_path = RAW_DIR / "ctgov_fetch_manifest.json"
    if manifest_path.exists() and not args.force and not args.test_one_page:
        prev = json.loads(manifest_path.read_text(encoding="utf-8"))
        if prev.get("completed"):
            print(
                f"[SKIP] Complete pull already cached: {prev['total_studies_fetched']} studies "
                f"across {prev['pages']} pages (use --force to re-pull).",
                flush=True,
            )
            return 0

    session = requests.Session()
    session.headers.update({"User-Agent": "D30-Boost-Research-Audit/1.0"})

    if args.test_one_page:
        t0 = time.time()
        data = fetch_page(session, None, page_size=5, count_total=True)
        elapsed = time.time() - t0
        studies = data.get("studies", [])
        print(
            f"[TEST OK] totalCount={data.get('totalCount')} pulled={len(studies)} "
            f"in {elapsed:.2f}s nextToken={bool(data.get('nextPageToken'))}",
            flush=True,
        )
        if studies:
            s0 = studies[0]
            print("  sample NCT:", s0.get("protocolSection", {}).get("identificationModule", {}).get("nctId"), flush=True)
            print("  derived keys:", list((s0.get("derivedSection") or {}).keys()), flush=True)
            ae = (s0.get("resultsSection") or {}).get("adverseEventsModule") or {}
            print(
                f"  ae keys={list(ae.keys())} n_groups={len(ae.get('eventGroups') or [])} "
                f"n_oth={len(ae.get('otherEvents') or [])} n_ser={len(ae.get('seriousEvents') or [])}",
                flush=True,
            )
            if ae.get("otherEvents"):
                print("  otherEvents[0]:", ae["otherEvents"][0], flush=True)
        return 0

    # Clean old pages if forcing
    if args.force:
        for old in RAW_DIR.glob("page_*.json.gz"):
            old.unlink()

    page_idx = 0
    page_token: str | None = None
    total_expected: int | None = None
    total_fetched = 0
    page_records: list[dict] = []
    t_start = time.time()

    print(f"[START] Fetching full CT.gov v2 Phase 2+3 Industry universe (pageSize={args.page_size})...", flush=True)
    while page_idx < args.max_pages:
        page_idx += 1
        t0 = time.time()
        data = fetch_page(
            session,
            page_token=page_token,
            page_size=args.page_size,
            count_total=(page_idx == 1),
        )
        if page_idx == 1:
            total_expected = data.get("totalCount")
            print(f"  Reported totalCount = {total_expected}", flush=True)

        studies = data.get("studies", [])
        next_token = data.get("nextPageToken")
        out_path = RAW_DIR / f"page_{page_idx:04d}.json.gz"
        raw_bytes = json.dumps({"studies": studies}, separators=(",", ":")).encode("utf-8")
        with gzip.open(out_path, "wb", compresslevel=6) as fh:
            fh.write(raw_bytes)
        file_sha = hashlib.sha256(out_path.read_bytes()).hexdigest()
        total_fetched += len(studies)
        dt = time.time() - t0
        page_records.append({
            "page": page_idx,
            "file": out_path.name,
            "n_studies": len(studies),
            "gz_bytes": out_path.stat().st_size,
            "sha256": file_sha,
        })
        print(
            f"  Page {page_idx:02d}: +{len(studies):4d} studies (cum={total_fetched:5d}/{total_expected}) "
            f"| {out_path.stat().st_size/1024:6.1f} KB gz | {dt:.2f}s",
            flush=True,
        )
        if not next_token or len(studies) == 0:
            break
        page_token = next_token
        time.sleep(0.15)

    manifest = {
        "fetched_utc": datetime.now(UTC).isoformat(),
        "endpoint": CTGOV_URL,
        "query_term": QUERY_TERM,
        "fields": FIELDS,
        "page_size": args.page_size,
        "total_expected": total_expected,
        "total_studies_fetched": total_fetched,
        "pages": len(page_records),
        "elapsed_seconds": round(time.time() - t_start, 2),
        "completed": (page_token is None) or (total_expected is not None and total_fetched >= total_expected),
        "page_files": page_records,
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(
        f"[DONE] Fetched {total_fetched} studies across {len(page_records)} pages in "
        f"{manifest['elapsed_seconds']}s. Manifest: {manifest_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
