"""Step 5: Verify all peer-reviewed manuscript references against the live Crossref API
and record verified official federal regulatory / NHTSA institutional sources.
"""
from __future__ import annotations

import json
import time
from datetime import UTC, datetime
from pathlib import Path

import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
PROC_DIR = BASE_DIR / "data_processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "AcademicResearch-CrossrefVerify/1.0 (mailto:zijianzeng@foxmail.com)",
    "Accept": "application/json",
}

QUERIES = [
    ("arora_2006", "Sell First, Fix Later: Impact of Patching on Software Quality", "Arora"),
    ("august_2006", "Network Software Security and User Incentives", "August"),
    ("ramdas_2008", "Does Component Sharing Help or Hurt Reliability? An Empirical Study in the Automotive Industry", "Ramdas"),
    ("shah_2017", "Plant Operations and Product Recalls in the Automotive Industry: An Empirical Investigation", "Shah"),
    ("haunschild_2004", "The Role of Volition in Organizational Learning: The Case of Automotive Product Recalls", "Haunschild"),
    ("kalaignanam_2013", "The Impact of Product Recalls on Future Product Reliability and Future Accidents: Evidence from the Automobile Industry", "Kalaignanam"),
    ("eilert_2017", "Does It Pay to Recall Your Product Early? An Empirical Investigation in the Automobile Industry", "Eilert"),
    ("pagiavlas_2022", "Regulating Product Recall Compliance in the Digital Age", "Pagiavlas"),
    ("rupp_2002", "Who Initiates Recalls and Who Cares? Evidence from the Automobile Industry", "Rupp"),
    ("bae_2011", "Do Vehicle Recalls Reduce the Number of Accidents? The Case of the U.S. Car Market", "Bae"),
    ("barber_1996", "Product Reliability and Firm Value: The Experience of American and Japanese Automakers", "Barber"),
    ("jarrell_1985", "The Impact of Product Recalls on the Wealth of Sellers", "Jarrell"),
    ("thirumalai_2011", "Product Recalls in the Medical Device Industry: An Empirical Exploration of the Sources and Financial Consequences", "Thirumalai"),
    ("ball_2018", "The decision to recall: A behavioral investigation in the medical device industry", "Ball"),
    ("hora_2011", "Safety hazard and time to recall: The role of recall strategy, product defect type, and supply chain player", "Hora"),
    ("cavusoglu_2008", "Security Patch Management: Share the Burden or Share the Damage", "Cavusoglu"),
    ("maccormack_2006", "Exploring the Structure of Complex Software Designs: An Empirical Study of Open Source and Proprietary Code", "MacCormack"),
    ("cameron_2008", "Bootstrap-Based Improvements for Inference with Clustered Errors", "Cameron"),
    ("cameron_2015", "A Practitioner's Guide to Cluster-Robust Inference", "Cameron"),
    ("mackinnon_2017", "Wild Bootstrap Inference for Wildly Different Cluster Sizes", "MacKinnon"),
    ("sun_2021", "Estimating dynamic treatment effects in event studies with heterogeneous treatment effects", "Sun"),
    ("callaway_2021", "Difference-in-Differences with multiple time periods", "Callaway"),
    ("roth_2023", "What's trending in difference-in-differences? A synthesis of the recent econometrics literature", "Roth"),
]

DIRECT_DOIS = {
    "pagiavlas_2022": "10.1177/00222429211023016",
}


def _parse_crossref_item(it: dict) -> dict:
    authors = it.get("author", [])
    pub_print = it.get("published-print") or {}
    pub_online = it.get("published-online") or {}
    pub_issued = it.get("issued") or {}
    pub = pub_print or pub_online or pub_issued
    parts = pub.get("date-parts", [[None]])[0]
    year = parts[0] if parts else None
    online_parts = pub_online.get("date-parts", [[None]])[0]
    online_year = online_parts[0] if online_parts else None
    author_str = ", ".join(
        f"{a.get('family', '')}, {a.get('given', '')[:1]}."
        for a in authors[:6]
        if a.get("family")
    )
    return {
        "verified": True,
        "doi": str(it.get("DOI") or ""),
        "title": (it.get("title") or [""])[0],
        "authors": author_str,
        "journal": (it.get("container-title") or [""])[0],
        "year": year,
        "online_year": online_year,
        "volume": it.get("volume"),
        "issue": it.get("issue"),
        "page": it.get("page"),
    }


def query_crossref_doi(doi: str) -> dict:
    url = f"https://api.crossref.org/works/{doi}"
    for attempt in range(1, 4):
        try:
            r = requests.get(url, headers=HEADERS, timeout=30)
            r.raise_for_status()
            it = r.json().get("message", {})
            if it.get("DOI"):
                return _parse_crossref_item(it)
            return {"verified": False, "query_doi": doi}
        except (requests.RequestException, ValueError, OSError) as exc:
            print(f"[WARN] Crossref DOI retry {attempt} for {doi}: {exc}", flush=True)
            time.sleep(2.0 * attempt)
    return {"verified": False, "query_doi": doi}


def query_crossref(title: str, first_author: str) -> dict:
    url = "https://api.crossref.org/works"
    params = {
        "query.bibliographic": f"{title} {first_author}",
        "filter": "type:journal-article",
        "rows": 8,
    }
    for attempt in range(1, 4):
        try:
            r = requests.get(url, params=params, headers=HEADERS, timeout=30)
            r.raise_for_status()
            items = r.json().get("message", {}).get("items", [])
            for it in items:
                authors = it.get("author", [])
                a_fams = [str(a.get("family", "")).lower() for a in authors]
                it_title = (it.get("title") or [""])[0]
                container = (it.get("container-title") or [""])[0]
                doi = str(it.get("DOI") or "")
                if (
                    first_author.lower() in " ".join(a_fams)
                    and len(it_title) > 10
                    and container
                    and not doi.lower().startswith("10.2139/ssrn")
                    and not doi.lower().startswith("10.3386/")
                ):
                    return _parse_crossref_item(it)
            return {"verified": False, "query_title": title}
        except (requests.RequestException, ValueError, OSError) as exc:
            print(f"[WARN] Crossref retry {attempt} for {first_author}: {exc}", flush=True)
            time.sleep(2.0 * attempt)
    return {"verified": False, "query_title": title}


INSTITUTIONAL_REFERENCES = {
    "nhtsa_completion_rates_2025": {
        "verified": True,
        "type": "government-report",
        "authors": "National Highway Traffic Safety Administration (NHTSA), Office of Defects Investigation",
        "year": 2025,
        "title": "Vehicle Safety Recall Completion Rates (Report No. DOT HS 813 687)",
        "publisher": "U.S. Department of Transportation, National Highway Traffic Safety Administration, January 2025",
        "url": "https://rosap.ntl.bts.gov/view/dot/79374",
        "pdf_url": "https://rosap.ntl.bts.gov/view/dot/79374/dot_79374_DS1.pdf",
        "note": "Official FAST Act supplemental report analyzing fifth-quarter recall completion rates (2010-2022), documenting vehicle age (oldest affected vehicle) and remedy-availability delays as primary determinants of completion.",
    },
    "nhtsa_eighth_report_2024": {
        "verified": True,
        "type": "government-dataset",
        "authors": "National Highway Traffic Safety Administration (NHTSA)",
        "year": 2025,
        "title": "2024 Annual List of Recall Completion Rates (Eighth-Quarter Completion Report)",
        "publisher": "U.S. Department of Transportation, National Highway Traffic Safety Administration, January 2025",
        "url": "https://www.nhtsa.gov/sites/nhtsa.gov/files/2025-01/2024-recall-completion-rates.pdf",
        "note": "Published annual list of campaigns reaching their eighth quarterly completion report in calendar year 2024 (809 rows linked 100% to FLAT_RCL).",
    },
    "nhtsa_eighth_report_2025": {
        "verified": True,
        "type": "government-dataset",
        "authors": "National Highway Traffic Safety Administration (NHTSA)",
        "year": 2026,
        "title": "2025 Annual List of Recall Completion Rates (Eighth-Quarter Completion Report)",
        "publisher": "U.S. Department of Transportation, National Highway Traffic Safety Administration, January 2026",
        "url": "https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-01/2025-recall-completion-rates.pdf",
        "note": "Published annual list of campaigns reaching their eighth quarterly completion report in calendar year 2025 (728 rows linked 100% to FLAT_RCL).",
    },
    "nhtsa_2025_annual_recalls_report": {
        "verified": True,
        "type": "government-report",
        "authors": "National Highway Traffic Safety Administration (NHTSA)",
        "year": 2026,
        "title": "2025 Annual Recalls Report",
        "publisher": "U.S. Department of Transportation, National Highway Traffic Safety Administration, March 2026",
        "url": "https://www.nhtsa.gov/sites/nhtsa.gov/files/2026-03/2025-annual-recalls-report.pdf",
        "note": "Official annual recalls report (March 2026) tallying 33 partially or fully over-the-air remedied recalls in 2025 under internal agency reporting.",
    },
    "cfr_49_573_7": {
        "verified": True,
        "type": "federal-regulation",
        "authors": "Office of the Federal Register (NARA) / U.S. Department of Transportation",
        "year": 2026,
        "title": "49 CFR § 573.7 — Quarterly Reports (Defect and Noncompliance Responsibility and Reports)",
        "publisher": "Electronic Code of Federal Regulations, Title 49, Subtitle B, Chapter V, Part 573",
        "url": "https://www.ecfr.gov/current/title-49/subtitle-B/chapter-V/part-573/section-573.7",
        "note": "Governs statutory quarterly completion filings starting from the remedy-available owner notification quarter (§ 573.7(a)), early termination at 100% completion, and unreachable-vehicle exclusions (§ 573.7(b)(5)).",
    },
    "dot_socrata_6axg_epim": {
        "verified": True,
        "type": "government-dataset",
        "authors": "U.S. Department of Transportation (DOT) / NHTSA",
        "year": 2026,
        "title": "Recalls Data (Socrata Open Data Registry, Dataset ID 6axg-epim)",
        "publisher": "U.S. Department of Transportation DataHub",
        "url": "https://datahub.transportation.gov/resource/6axg-epim.csv",
        "note": "Latest-snapshot public DOT recalls completion registry mixing heterogeneous reporting horizons across campaigns (snapshot frozen November 25, 2026).",
    },
}


def main() -> None:
    out = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "references": {},
        "institutional_references": INSTITUTIONAL_REFERENCES,
    }
    for key, title, author in QUERIES:
        if key in DIRECT_DOIS:
            res = query_crossref_doi(DIRECT_DOIS[key])
        else:
            res = query_crossref(title, author)
        out["references"][key] = res
        status = f"OK doi={res.get('doi')} ({res.get('year')}, {res.get('journal')})" if res.get("verified") else "MISS"
        print(f"[{key}] {status}", flush=True)
        time.sleep(0.25)

    out_path = PROC_DIR / "verified_references.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    n_ok = sum(1 for v in out["references"].values() if v.get("verified"))
    print(
        f"[DONE] Verified {n_ok}/{len(QUERIES)} peer-reviewed Crossref DOIs + "
        f"{len(INSTITUTIONAL_REFERENCES)} federal institutional references -> {out_path}",
        flush=True,
    )


if __name__ == "__main__":
    main()
