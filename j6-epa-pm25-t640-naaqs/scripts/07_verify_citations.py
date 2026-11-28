"""Step 07 (v4 ES&T): Live Crossref REST API Verification of 100% of Academic DOIs
and Two-Way Citation Synchronization Check with manuscript_j6_boost.md.
"""

from __future__ import annotations

import re
import time
import urllib.parse
from pathlib import Path
from typing import Any

import requests
from econ_utils import RES_DIR, WS_DIR, save_json_lf

HEADERS = {
    "User-Agent": "J6ESTPm25MetrologyStudy/4.0 (https://github.com/ai-science; mailto:epastudy@academic-audit.org)"
}

# Canonical ES&T v4 bibliography registry (15 peer-reviewed DOIs + 6 official regulatory entries)
ACADEMIC_REFS: list[dict[str, Any]] = [
    {
        "key": "Long2023",
        "cite_pattern": r"Long et al\.\s*\(2023\)|Long et al\.,\s*2023|Long, Urbanski",
        "doi": "10.1080/10962247.2023.2171156",
        "expected_author": "Long",
        "expected_year": 2023,
    },
    {
        "key": "McClure2026",
        "cite_pattern": r"McClure et al\.\s*\(2026\)|McClure et al\.,\s*2026",
        "doi": "10.1080/10962247.2026.2639376",
        "expected_author": "McClure",
        "expected_year": 2026,
    },
    {
        "key": "Krupnick2025",
        "cite_pattern": r"Krupnick et al\.\s*\(2025\)|Krupnick et al\.,\s*2025",
        "doi": "10.1021/acs.est.4c08946",
        "expected_author": "Krupnick",
        "expected_year": 2025,
    },
    {
        "key": "Jaffe2026",
        "cite_pattern": r"Jaffe et al\.\s*\(2026\)|Jaffe et al\.,\s*2026",
        "doi": "10.1029/2025GH001576",
        "expected_author": "Jaffe",
        "expected_year": 2026,
    },
    {
        "key": "Burke2023",
        "cite_pattern": r"Burke et al\.\s*\(2023\)|Burke et al\.,\s*2023",
        "doi": "10.1038/s41586-023-06522-6",
        "expected_author": "Burke",
        "expected_year": 2023,
    },
    {
        "key": "Childs2022",
        "cite_pattern": r"Childs et al\.\s*\(2022\)|Childs et al\.,\s*2022",
        "doi": "10.1021/acs.est.2c02934",
        "expected_author": "Childs",
        "expected_year": 2022,
    },
    {
        "key": "Di2017",
        "cite_pattern": r"Di et al\.\s*\(2017\)|Di et al\.,\s*2017",
        "doi": "10.1056/NEJMoa1702747",
        "expected_author": "Di",
        "expected_year": 2017,
    },
    {
        "key": "Bland1986",
        "cite_pattern": r"Bland\s*(?:&|and)\s*Altman\s*\(1986\)|Bland\s*(?:&|and)\s*Altman,\s*1986",
        "doi": "10.1016/S0140-6736(86)90837-8",
        "expected_author": "Bland",
        "expected_year": 1986,
    },
    {
        "key": "Cameron2011",
        "cite_pattern": r"Cameron, Gelbach,?\s*(?:&|and)\s*Miller\s*\(2011\)|Cameron, Gelbach,?\s*(?:&|and)\s*Miller,\s*2011|Cameron et al\.\s*\(2011\)|Cameron et al\.,\s*2011",
        "doi": "10.1198/jbes.2010.07136",
        "expected_author": "Cameron",
        "expected_year": 2011,
    },
    {
        "key": "Cameron2008",
        "cite_pattern": r"Cameron, Gelbach,?\s*(?:&|and)\s*Miller\s*\(2008\)|Cameron, Gelbach,?\s*(?:&|and)\s*Miller,\s*2008|Cameron et al\.\s*\(2008\)|Cameron et al\.,\s*2008",
        "doi": "10.1162/rest.90.3.414",
        "expected_author": "Cameron",
        "expected_year": 2008,
    },
    {
        "key": "Roodman2019",
        "cite_pattern": r"Roodman et al\.\s*\(2019\)|Roodman et al\.,\s*2019",
        "doi": "10.1177/1536867X19830877",
        "expected_author": "Roodman",
        "expected_year": 2019,
    },
    {
        "key": "Fowlie2019",
        "cite_pattern": r"Fowlie, Rubin,?\s*(?:&|and)\s*Walker\s*\(2019\)|Fowlie et al\.\s*\(2019\)|Fowlie, Rubin,?\s*(?:&|and)\s*Walker,\s*2019",
        "doi": "10.1257/pandp.20191064",
        "expected_author": "Fowlie",
        "expected_year": 2019,
    },
    {
        "key": "Zou2021",
        "cite_pattern": r"Zou\s*\(2021\)|Zou,\s*2021",
        "doi": "10.1257/aer.20181346",
        "expected_author": "Zou",
        "expected_year": 2021,
    },
    {
        "key": "Grainger2019",
        "cite_pattern": r"Grainger\s*(?:&|and)\s*Schreiber\s*\(2019\)|Grainger\s*(?:&|and)\s*Schreiber,\s*2019",
        "doi": "10.1257/pandp.20191063",
        "expected_author": "Grainger",
        "expected_year": 2019,
    },
    {
        "key": "Abadie2023",
        "cite_pattern": r"Abadie et al\.\s*\(2023\)|Abadie et al\.,\s*2023",
        "doi": "10.1093/qje/qjac038",
        "expected_author": "Abadie",
        "expected_year": 2023,
    },
]

INSTITUTIONAL_REFS: list[dict[str, str]] = [
    {
        "key": "EPA2024NAAQS",
        "cite_pattern": r"89 FR 16202|U\.S\. EPA \(2024a\)|U\.S\. EPA, 2024a",
        "tok": "89 FR 16202",
        "citation": "U.S. Environmental Protection Agency (2024a). Reconsideration of the National Ambient Air Quality Standards for Particulate Matter. Final Rule, 89 FR 16202 (February 7, 2024; effective May 6, 2024).",
    },
    {
        "key": "EPA2024Tiering",
        "cite_pattern": r"EPA-457/R-24-001|U\.S\. EPA \(2024b\)|U\.S\. EPA, 2024b",
        "tok": "EPA-457/R-24-001",
        "citation": "U.S. Environmental Protection Agency (2024b). PM2.5 Wildland Fire Exceptional Events Tiering Document. EPA-457/R-24-001, Office of Air Quality Planning and Standards (April 30, 2024).",
    },
    {
        "key": "EPA2024T640",
        "cite_pattern": r"U\.S\. EPA \(2024c\)|U\.S\. EPA, 2024c|Quick Reference Guide to T640",
        "tok": "T640",
        "citation": "U.S. Environmental Protection Agency (2024c). Quick Reference Guide to T640/T640x Data and Network Alignment Memorandum (AQS Method Codes 636/638 and 736/738). Office of Air Quality Planning and Standards (May 13, 2024).",
    },
    {
        "key": "EPA2026TierTable",
        "cite_pattern": r"U\.S\. EPA \(2026\)|U\.S\. EPA, 2026|2026-09-14",
        "tok": "2026-09-14",
        "citation": "U.S. Environmental Protection Agency (2026). PM2.5 Tiering Tool for Exceptional Events Analysis: Site-Month Threshold Table (for_posting.csv), Certified Years 2021-2025, AQS Query Date 2026-09-14.",
    },
    {
        "key": "CFRAppN",
        "cite_pattern": r"40 CFR Part 50,?\s*Appendix N|Appendix N",
        "tok": "Appendix N",
        "citation": "U.S. Code of Federal Regulations (40 CFR Part 50, Appendix N). Interpretation of the National Ambient Air Quality Standards for PM2.5.",
    },
    {
        "key": "CFR5014",
        "cite_pattern": r"40 CFR §\s*50\.14|40 CFR 50\.14",
        "tok": "50.14",
        "citation": "U.S. Code of Federal Regulations (40 CFR § 50.14; 81 FR 68216). Treatment of Air Quality Monitoring Data Influenced by Exceptional Events.",
    },
]


def verify_one_doi(session: requests.Session, ref: dict[str, Any]) -> dict[str, Any]:
    """Verify a DOI live against Crossref REST API (with doi.org CSL-JSON fallback)."""
    doi = ref["doi"]
    enc = urllib.parse.quote(doi, safe="")
    cr_url = f"https://api.crossref.org/works/{enc}"
    csl_url = f"https://doi.org/{enc}"

    data = None
    source = None
    last_err = ""
    for attempt in range(1, 5):
        try:
            r = session.get(cr_url, headers=HEADERS, timeout=25)
            if r.status_code == 200:
                data = r.json()["message"]
                source = "crossref"
                break
            last_err = f"crossref HTTP {r.status_code}"
        except (requests.RequestException, ValueError, KeyError) as exc:
            last_err = f"crossref {exc}"
        try:
            r2 = session.get(
                csl_url,
                headers={**HEADERS, "Accept": "application/vnd.citationstyles.csl+json"},
                timeout=25,
                allow_redirects=True,
            )
            if r2.status_code == 200:
                data = r2.json()
                source = "doi_csl_json"
                break
            last_err = f"{last_err}; doi.org HTTP {r2.status_code}"
        except (requests.RequestException, ValueError, KeyError) as exc2:
            last_err = f"{last_err}; doi.org {exc2}"
        time.sleep(min(1.5 * attempt, 5.0))

    if data is None:
        return {
            "key": ref["key"],
            "doi": doi,
            "verified": False,
            "error": last_err,
        }

    authors_raw = data.get("author", [])
    surnames = [a.get("family", "") for a in authors_raw if a.get("family")]
    title = data.get("title", "")
    if isinstance(title, list):
        title = title[0] if title else ""
    journal = data.get("container-title", "")
    if isinstance(journal, list):
        journal = journal[0] if journal else ""
    yr = None
    for yk in ("published-print", "published-online", "issued", "published"):
        blk = data.get(yk)
        if isinstance(blk, dict) and blk.get("date-parts"):
            yr = blk["date-parts"][0][0]
            if yr:
                break
    vol = str(data.get("volume", "") or "")
    issue = str(data.get("issue", "") or "")
    page = str(data.get("page", "") or "")

    author_ok = any(ref["expected_author"].lower() in s.lower() for s in surnames)
    year_ok = (yr is not None) and (abs(int(yr) - int(ref["expected_year"])) <= 1)

    return {
        "key": ref["key"],
        "doi": doi,
        "verified": bool(author_ok and year_ok and len(title) > 5),
        "source": source,
        "authors": surnames,
        "author_first": surnames[0] if surnames else "",
        "year": int(yr) if yr else None,
        "title": title,
        "journal": journal,
        "volume": vol,
        "issue": issue,
        "page": page,
        "author_ok": author_ok,
        "year_ok": year_ok,
    }


def check_two_way_sync(md_path: Path, verified_acad: list[dict[str, Any]]) -> dict[str, Any]:
    """Verify 100% two-way citation sync between manuscript body and References section."""
    if not md_path.exists():
        return {"manuscript_exists": False}
    txt = md_path.read_text(encoding="utf-8")
    parts = re.split(r"\n##\s+References\s*\n", txt, maxsplit=1)
    body = parts[0]
    refs_sec = parts[1] if len(parts) > 1 else ""

    missing_in_body = []
    missing_in_refs = []
    for ref in ACADEMIC_REFS:
        if not re.search(ref["cite_pattern"], body):
            missing_in_body.append(ref["key"])
        if ref["doi"].lower() not in refs_sec.lower():
            missing_in_refs.append(ref["key"])
    for iref in INSTITUTIONAL_REFS:
        if not re.search(iref["cite_pattern"], body):
            missing_in_body.append(iref["key"])
        if iref["tok"] not in refs_sec:
            missing_in_refs.append(iref["key"])

    return {
        "manuscript_exists": True,
        "total_refs_checked": len(ACADEMIC_REFS) + len(INSTITUTIONAL_REFS),
        "missing_in_body": missing_in_body,
        "missing_in_refs": missing_in_refs,
        "two_way_sync_ok": bool(not missing_in_body and not missing_in_refs),
    }


def main() -> int:
    print("=== STEP 07: LIVE CROSSREF DOI VERIFICATION & CITATION SYNC (V4 ES&T) ===", flush=True)
    cache_path = RES_DIR / "07_citations_verified.json"
    session = requests.Session()
    verified: list[dict[str, Any]] = []
    for ref in ACADEMIC_REFS:
        res = verify_one_doi(session, ref)
        verified.append(res)
        status = "OK" if res["verified"] else "FAIL"
        print(
            f"  [{status}] {ref['key']:14s} | {ref['doi']:30s} | "
            f"{res.get('author_first', '?')} ({res.get('year', '?')}) — {res.get('journal', '')[:38]}",
            flush=True,
        )

    n_ok = sum(1 for r in verified if r["verified"])
    sync = check_two_way_sync(WS_DIR / "manuscript_j6_boost.md", verified)

    payload = {
        "n_academic_dois": len(ACADEMIC_REFS),
        "n_verified": n_ok,
        "verification_rate_pct": round(100.0 * n_ok / len(ACADEMIC_REFS), 2),
        "all_verified": bool(n_ok == len(ACADEMIC_REFS)),
        "academic_refs": verified,
        "institutional_refs": INSTITUTIONAL_REFS,
        "two_way_sync": sync,
    }
    sha = save_json_lf(cache_path, payload)
    print(
        f"[DONE STEP 07] Verified {n_ok}/{len(ACADEMIC_REFS)} DOIs ({payload['verification_rate_pct']}%); "
        f"two_way_sync={sync.get('two_way_sync_ok')}; SHA-256 LF: {sha}",
        flush=True,
    )
    return 0 if payload["all_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
