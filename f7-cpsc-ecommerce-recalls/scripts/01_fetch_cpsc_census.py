"""Step 1: Fetch the complete 2000-2026 U.S. CPSC SaferProducts Recall Census
via the official open HTTP-200 REST Web Services API.

Access-Control Compliance:
  Uses ONLY https://www.saferproducts.gov/RestWebServices/Recall?format=json
  (100% open official public REST API). Never touches HTTP-403 endpoints.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path

import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\f7_boost_cpsc_ecommerce_recalls_20261126")
DATA_DIR = BASE_DIR / "data"
RESULTS_DIR = BASE_DIR / "results"
RAW_JSON_PATH = DATA_DIR / "cpsc_recalls_2000_2026.json"
MANIFEST_PATH = RESULTS_DIR / "01_fetch_manifest.json"

API_URL = "https://www.saferproducts.gov/RestWebServices/Recall"
HEADERS = {
    "User-Agent": "F7BoostAcademicResearch/1.0 (U.S. CPSC Public Recall API Study)",
    "Accept": "application/json",
}
START_YEAR = 2000
END_YEAR = 2026


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch_year(session: requests.Session, year: int) -> list[dict]:
    params = {
        "format": "json",
        "RecallDateStart": f"{year}-01-01",
        "RecallDateEnd": f"{year}-12-31",
    }
    last_err = None
    for attempt in range(1, 5):
        try:
            resp = session.get(API_URL, params=params, headers=HEADERS, timeout=60)
            if resp.status_code == 200:
                payload = resp.json()
                if isinstance(payload, list):
                    return payload
                raise ValueError(f"Unexpected JSON type {type(payload)} for year {year}")
            last_err = f"HTTP {resp.status_code}"
            print(f"  [WARN] Year {year} attempt {attempt}: {last_err}", flush=True)
        except (requests.RequestException, ValueError) as exc:
            last_err = str(exc)
            print(f"  [WARN] Year {year} attempt {attempt}: {last_err}", flush=True)
        time.sleep(1.5 * attempt)
    raise RuntimeError(f"Failed to fetch CPSC year {year} after 4 attempts: {last_err}")


def main() -> int:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    force_refetch = "--force" in sys.argv
    if RAW_JSON_PATH.exists() and not force_refetch:
        print(f"[INFO] Loading cached census from {RAW_JSON_PATH}", flush=True)
        all_records = json.loads(RAW_JSON_PATH.read_text(encoding="utf-8"))
        yearly_fetched: dict[str, int] = {}
    else:
        print(f"[STEP 1] Fetching CPSC SaferProducts Recall Census {START_YEAR}-{END_YEAR}...", flush=True)
        session = requests.Session()
        all_records = []
        seen_ids: set[int] = set()
        yearly_fetched = {}
        for yr in range(START_YEAR, END_YEAR + 1):
            recs = fetch_year(session, yr)
            added = 0
            for rec in recs:
                rid = rec.get("RecallID")
                if rid is not None and rid not in seen_ids:
                    seen_ids.add(rid)
                    all_records.append(rec)
                    added += 1
            yearly_fetched[str(yr)] = added
            print(f"  Year {yr}: returned={len(recs):4d}, added_unique={added:4d}", flush=True)
            time.sleep(0.25)

        # Sort deterministically by RecallDate then RecallID
        all_records.sort(key=lambda r: (str(r.get("RecallDate") or ""), int(r.get("RecallID") or 0)))
        RAW_JSON_PATH.write_text(json.dumps(all_records, ensure_ascii=False), encoding="utf-8")

    raw_sha = sha256_file(RAW_JSON_PATH)

    # Audit schema coverage and date bounds
    year_counts: Counter[int] = Counter()
    dates: list[str] = []
    field_nonempty: Counter[str] = Counter()
    late2026_retailer_only = 0
    late2026_total = 0

    check_fields = [
        "Products", "ProductUPCs", "Remedies", "RemedyOptions", "Retailers",
        "Importers", "Manufacturers", "Distributors", "ManufacturerCountries",
        "Hazards", "Injuries", "Inconjunctions", "ConsumerContact", "Description",
    ]
    for rec in all_records:
        rd = str(rec.get("RecallDate") or "")[:10]
        if len(rd) == 10 and rd[:4].isdigit():
            yr = int(rd[:4])
            year_counts[yr] += 1
            dates.append(rd)
            if yr == 2026:
                late2026_total += 1
                if not (rec.get("Importers") or rec.get("Manufacturers") or rec.get("Distributors")) and rec.get("Retailers"):
                    late2026_retailer_only += 1
        for fld in check_fields:
            val = rec.get(fld)
            if isinstance(val, list) and len(val) > 0 or isinstance(val, str) and val.strip():
                field_nonempty[fld] += 1

    # Inspect specific known late-2026 audit recall IDs (11067, 11068) if present
    spot_ids = {}
    for rec in all_records:
        if rec.get("RecallID") in (11067, 11068):
            spot_ids[str(rec["RecallID"])] = {
                "RecallDate": rec.get("RecallDate"),
                "Title": rec.get("Title"),
                "Importers": rec.get("Importers"),
                "Manufacturers": rec.get("Manufacturers"),
                "Distributors": rec.get("Distributors"),
                "Retailers": rec.get("Retailers"),
                "ProductUPCs": rec.get("ProductUPCs"),
                "Inconjunctions": rec.get("Inconjunctions"),
            }

    manifest = {
        "api_url": API_URL,
        "year_range_requested": [START_YEAR, END_YEAR],
        "total_unique_recalls": len(all_records),
        "min_recall_date": min(dates) if dates else None,
        "max_recall_date": max(dates) if dates else None,
        "raw_json_path": str(RAW_JSON_PATH),
        "raw_json_bytes": RAW_JSON_PATH.stat().st_size,
        "raw_json_sha256": raw_sha,
        "counts_by_year": {str(y): year_counts[y] for y in sorted(year_counts)},
        "field_nonempty_counts": dict(field_nonempty),
        "year_2026_schema_audit": {
            "total_2026_recalls": late2026_total,
            "zero_imp_mfr_dist_but_has_retailers": late2026_retailer_only,
            "share_retailer_only_2026": round(late2026_retailer_only / max(late2026_total, 1), 4),
        },
        "spot_check_ids": spot_ids,
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    print(
        f"[DONE] Saved {len(all_records):,} unique recalls ({manifest['min_recall_date']} to "
        f"{manifest['max_recall_date']}) | SHA-256: {raw_sha}",
        flush=True,
    )
    print(
        f"  2026 schema audit: {late2026_retailer_only}/{late2026_total} recalls have empty "
        f"Importers/Manufacturers/Distributors with entity info inside Retailers.",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
