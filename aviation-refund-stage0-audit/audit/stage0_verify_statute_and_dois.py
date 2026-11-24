"""Stage 0B exact verification of 89 FR 32760 (14 CFR Part 260) and exact Tarmac Delay Rule Crossref DOIs (non-outcome)."""

from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "stage0_bts_and_statute_audit.json"
HEADERS = {"User-Agent": "Academic-Research-DOT260-Stage0B/1.0"}


def get_json(url: str) -> dict:
    with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def get_text(url: str) -> str:
    with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> None:
    data = json.loads(OUT_PATH.read_text(encoding="utf-8"))

    # 1. Exact 89 FR 32760 (published 2024-04-26) via Federal Register API
    qs = urlencode(
        {
            "conditions[publication_date][is]": "2024-04-26",
            "conditions[agencies][]": "transportation-department",
            "conditions[type][]": "RULE",
        }
    )
    fr_res = get_json(f"https://www.federalregister.gov/api/v1/documents.json?{qs}")
    rule_89 = None
    for item in fr_res.get("results", []):
        if "Refunds" in str(item.get("title", "")):
            doc_num = item["document_number"]
            det = get_json(f"https://www.federalregister.gov/api/v1/documents/{doc_num}.json")
            rule_89 = {
                "document_number": det.get("document_number"),
                "citation": det.get("citation"),
                "title": det.get("title"),
                "publication_date": det.get("publication_date"),
                "effective_on": det.get("effective_on"),
                "dates_text": det.get("dates"),
                "cfr_references": det.get("cfr_references"),
                "html_url": det.get("html_url"),
                "body_html_url": det.get("body_html_url"),
            }
            # Inspect official body_html_url for exact statutory 3-hour trigger & carrier pre-rule delay policy mentions
            if det.get("body_html_url"):
                body = re.sub(r"<[^>]+>", " ", get_text(det["body_html_url"]))
                body = " ".join(body.split())
                rule_89["body_chars"] = len(body)
                rule_89["mentions_three_hours_domestic"] = bool(re.search(r"3 hours|three hours", body, re.I))
                rule_89["mentions_october_28_2024"] = bool(re.search(r"October 28, 2024", body, re.I))
                # Check if preamble lists specific carrier pre-rule thresholds (just count matches, do not copy long text)
                carrier_hits = {}
                for c in ["American", "Delta", "United", "Southwest", "Alaska", "JetBlue", "Spirit", "Frontier"]:
                    carrier_hits[c] = len(re.findall(rf"\b{c}\b", body))
                rule_89["carrier_mention_counts_in_89FR32760"] = carrier_hits
            break

    data["federal_register_89_FR_32760_exact"] = rule_89
    data["federal_register_91_FR_41556_enforcement_note"] = data.pop("federal_register_89_FR_32760").get("matched_rule")

    # 2. Exact Crossref title search for Tarmac Delay Rule & Aviation Delay empirical benchmarks
    queries = {
        "forbes_lederman_tombe_2015_aej": "Quality Disclosure Programs and Internal Organizational Practices Evidence from Airline Flight Delays Forbes Lederman Tombe",
        "kleven_2016_are_bunching": "Bunching Henrik Jacobsen Kleven Annual Review of Economics 2016",
        "tarmac_delay_rule_cancellations_empirical": "Tarmac Delay Rule airline cancellations",
        "tarmac_delay_rule_fukui_nagata": "Tarmac Delay Rule Fukui Nagata",
    }
    verified_lit = {}
    for k, q in queries.items():
        cr = get_json(f"https://api.crossref.org/works?{urlencode({'query.bibliographic': q, 'rows': 2})}")
        items = cr.get("message", {}).get("items", [])
        if items:
            top = items[0]
            verified_lit[k] = {
                "doi": top.get("DOI"),
                "title": top.get("title", []),
                "container_title": top.get("container-title", []),
                "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in top.get("author", [])],
                "published": top.get("published") or top.get("issued"),
            }
    data["primary_literature_crossref"] = verified_lit

    OUT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("RULE_89:", json.dumps(rule_89, indent=2))
    print("VERIFIED_LIT:", json.dumps(verified_lit, indent=2))


if __name__ == "__main__":
    main()
