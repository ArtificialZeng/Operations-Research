"""Pillar 7 (v4): Live Crossref DOI Verification & 100% Body-to-Bibliography Citation Audit.

Verifies every academic DOI in manuscript_i4_boost.md live via Crossref REST API
(https://api.crossref.org/works/{doi}), verifies every official SEC Release/FAQ URL live
(HTTP 200), asserts zero occurrences of deprecated IC-35962, and enforces 100% two-way
consistency between in-text citations and the References section.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

WORK_DIR = Path(__file__).resolve().parents[1]
MD_PATH = WORK_DIR / "manuscript_i4_boost.md"
OUT_PATH = WORK_DIR / "results" / "07_verified_references_crossref.json"

HEADERS = {"User-Agent": "AcademicResearch/1.0 (mailto:zijianzeng@foxmail.com)"}

REF_MATCH_SPECS: list[tuple[str, str, str | None, str | None]] = [
    ("Abadie et al., 2023", r"Abadie et al\.(?:\s*\(2023\)|,\s*2023)", "10.1093/qje/qjac038", None),
    ("Barber, Huang, and Odean, 2016", r"Barber, Huang, and Odean(?:\s*\(2016\)|,\s*2016)", "10.1093/rfs/hhw054", None),
    ("Berk and Green, 2004", r"Berk and Green(?:\s*\(2004\)|,\s*2004)", "10.1086/424739", None),
    ("Callaway and Sant'Anna, 2021", r"Callaway and Sant(?:'|\u2019)Anna(?:\s*\(2021\)|,\s*2021)", "10.1016/j.jeconom.2020.12.001", None),
    ("Cameron, Gelbach, and Miller, 2008", r"Cameron, Gelbach, and Miller(?:\s*\(2008\)|,\s*2008)", "10.1162/rest.90.3.414", None),
    ("Chevalier and Ellison, 1997", r"Chevalier and Ellison(?:\s*\(1997\)|,\s*1997)", "10.1086/516389", None),
    ("Cooper, Gulen, and Rau, 2005", r"Cooper, Gulen, and Rau(?:\s*\(2005\)|,\s*2005)", "10.1111/j.1540-6261.2005.00818.x", None),
    ("Espenlaub, ul Haq, and Khurshed, 2017", r"Espenlaub, ul Haq, and Khurshed(?:\s*\(2017\)|,\s*2017)", "10.1016/j.jbankfin.2017.07.008", None),
    ("Fisch and Robertson, 2023", r"Fisch and Robertson(?:\s*\(2023\)|,\s*2023)", "10.2139/ssrn.4398419", None),
    ("Gibson Brandon et al., 2022", r"Gibson Brandon et al\.(?:\s*\(2022\)|,\s*2022)", "10.1093/rof/rfac064", None),
    ("Hartzmark and Sussman, 2019", r"Hartzmark and Sussman(?:\s*\(2019\)|,\s*2019)", "10.1111/jofi.12841", None),
    ("He, Wang, and Ward, 2025", r"He, Wang, and Ward(?:\s*\(2025\)|,\s*2025)", "10.2139/ssrn.5844262", None),
    ("Imbens and Manski, 2004", r"Imbens and Manski(?:\s*\(2004\)|,\s*2004)", "10.1111/j.1468-0262.2004.00555.x", None),
    ("Kacperczyk, Sialm, and Zheng, 2008", r"Kacperczyk, Sialm, and Zheng(?:\s*\(2008\)|,\s*2008)", "10.1093/rfs/hhl041", None),
    ("Kim and Yoon, 2023", r"Kim and Yoon(?:\s*\(2023\)|,\s*2023)", "10.1287/mnsc.2022.4394", None),
    ("Rambachan and Roth, 2023", r"Rambachan and Roth(?:\s*\(2023\)|,\s*2023)", "10.1093/restud/rdad018", None),
    ("Roodman et al., 2019", r"Roodman et al\.(?:\s*\(2019\)|,\s*2019)", "10.1177/1536867X19830877", None),
    ("Sensoy, 2009", r"Sensoy(?:\s*\(2009\)|,\s*2009)", "10.1016/j.jfineco.2008.02.011", None),
    ("Sirri and Tufano, 1998", r"Sirri and Tufano(?:\s*\(1998\)|,\s*1998)", "10.1111/0022-1082.00066", None),
    ("SEC IC-24828 (2001)", r"IC-24828", None, "https://www.sec.gov/rules/final/ic-24828.htm"),
    ("SEC 33-11238 / IC-35000 (2023)", r"33-11238|IC-35000", None, "https://www.sec.gov/files/rules/final/2023/33-11238.pdf"),
    (
        "SEC 2025-26 Names Rule FAQs (2025a)",
        r"Names Rule FAQs",
        None,
        "https://www.sec.gov/rules-regulations/staff-guidance/division-investment-management-frequently-asked-questions/2025-26-names-rule-faqs",
    ),
    ("SEC 33-11368 / IC-35500 (2025b)", r"33-11368|IC-35500", None, "https://www.sec.gov/files/rules/final/2025/33-11368.pdf"),
    ("SEC IC-35963 (2026a)", r"IC-35963", None, "https://www.sec.gov/files/rules/final/2026/ic-35963.pdf"),
    (
        "SEC Press Release 2026-19 (2026b)",
        r"2026-19",
        None,
        "https://www.sec.gov/newsroom/press-releases/2026-19-sec-proposes-amendments-reduce-burdens-reporting-fund-portfolio-holdings",
    ),
]


def main() -> int:
    md_text = MD_PATH.read_text(encoding="utf-8")
    assert "35962" not in md_text, "Deprecated/invalid SEC release IC-35962 found in manuscript!"
    parts = md_text.split("## References")
    assert len(parts) == 2, "Expected exactly one '## References' section in manuscript."
    body_text, refs_text = parts[0], parts[1]

    ref_lines = [ln.strip() for ln in refs_text.splitlines() if re.match(r"^\d+\.\s+", ln.strip())]
    assert len(ref_lines) == len(REF_MATCH_SPECS), f"Ref count mismatch: {len(ref_lines)} vs {len(REF_MATCH_SPECS)}"

    dois_in_refs = re.findall(r"DOI:\s*`([^`]+)`", refs_text)
    expected_dois = [d for _, _, d, _ in REF_MATCH_SPECS if d is not None]
    assert set(dois_in_refs) == set(expected_dois), f"DOI set mismatch: {set(dois_in_refs) ^ set(expected_dois)}"

    sess = requests.Session()
    sess.headers.update(HEADERS)

    verified_dois = []
    uncited_in_body = []
    for label, pat, doi, sec_url in REF_MATCH_SPECS:
        cited_hits = len(re.findall(pat, body_text))
        if cited_hits == 0:
            uncited_in_body.append(label)
        if doi is not None:
            r = None
            for att in range(3):
                try:
                    r = sess.get(f"https://api.crossref.org/works/{doi}", timeout=20)
                    if r.status_code == 200:
                        break
                except (requests.RequestException, ValueError):
                    time.sleep(1.5 * (att + 1))
            assert r is not None and r.status_code == 200, f"Crossref verification FAILED for {doi} ({label})"
            msg = r.json()["message"]
            verified_dois.append(
                {
                    "label": label,
                    "doi": doi,
                    "http_status": 200,
                    "crossref_title": (msg.get("title") or [""])[0],
                    "crossref_container": (msg.get("container-title") or [""])[0],
                    "crossref_authors": [a.get("family", "") for a in msg.get("author", [])],
                    "crossref_year": (
                        msg.get("published-print") or msg.get("published-online") or msg.get("posted") or msg.get("issued") or {}
                    ).get("date-parts", [[None]])[0][0],
                    "body_citation_count": cited_hits,
                }
            )
            time.sleep(0.08)
        else:
            sec_status = None
            if sec_url:
                for att in range(3):
                    try:
                        r_sec = sess.head(sec_url, timeout=20, allow_redirects=True)
                        if r_sec.status_code == 405:
                            r_sec = sess.get(sec_url, timeout=20, stream=True)
                            r_sec.close()
                        sec_status = int(r_sec.status_code)
                        if sec_status == 200:
                            break
                    except requests.RequestException:
                        time.sleep(1.5 * (att + 1))
                assert sec_status == 200, f"Live SEC URL verification FAILED (HTTP {sec_status}) for {sec_url} ({label})"
                assert sec_url in refs_text, f"Expected verified SEC URL {sec_url} in References section!"
                time.sleep(0.12)
            verified_dois.append(
                {
                    "label": label,
                    "doi": None,
                    "official_sec_release": True,
                    "sec_url": sec_url,
                    "http_status": sec_status,
                    "body_citation_count": cited_hits,
                }
            )

    assert len(uncited_in_body) == 0, f"Uncited bibliography items found: {uncited_in_body}"

    verified_author_years: set[tuple[str, int]] = set()
    for ref in verified_dois:
        yr_m = re.search(r"(\d{4})", ref["label"])
        if not yr_m:
            continue
        yr = int(yr_m.group(1))
        for tok in re.findall(r"[A-ZĽ][A-Za-zÀ-ÿ]+", ref["label"]):
            verified_author_years.add((tok.lower(), yr))
        for fam in ref.get("crossref_authors", []):
            for tok in re.findall(r"[A-ZĽ][A-Za-zÀ-ÿ]+", fam):
                verified_author_years.add((tok.lower(), yr))

    orphan_body_cites = []
    for m in re.finditer(r"\b([A-ZĽ][A-Za-zÀ-ÿ]+)(?:\s+et\s+al\.)?,\s*(199\d|20[012]\d)\b", body_text):
        word, yr_s = m.group(1), int(m.group(2))
        if word in {
            "January", "February", "March", "April", "May", "June", "July", "August",
            "September", "October", "November", "December", "Release", "Rule", "Section",
            "Table", "Figure", "Panel", "Draft", "Nov", "Dec", "Jun", "Sep",
            "Aug", "Feb", "Mar", "Apr", "Jul", "Oct", "Complete", "Full", "Large",
            "Small", "Pre", "Post", "Effective", "Dated", "Overhaul", "SEC", "Inc",
            "FAQs", "Guidance", "Commission", "Extension", "Update", "Jan", "Press",
            "Appendix", "Malaysia", "Kuala", "Lumpur",
        }:
            continue
        if (word.lower(), yr_s) not in verified_author_years:
            orphan_body_cites.append(m.group(0))

    assert len(orphan_body_cites) == 0, f"Unmatched body citations: {orphan_body_cites}"

    out = {
        "n_total_references": len(REF_MATCH_SPECS),
        "n_academic_dois_verified_live_crossref": sum(1 for x in verified_dois if x.get("doi")),
        "n_official_sec_releases": sum(1 for x in verified_dois if x.get("official_sec_release")),
        "all_bibliography_cited_in_body": len(uncited_in_body) == 0,
        "all_body_citations_in_bibliography": len(orphan_body_cites) == 0,
        "references": verified_dois,
    }
    OUT_PATH.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        f"[DONE STEP 7 v4] Verified {out['n_academic_dois_verified_live_crossref']} academic DOIs live via Crossref "
        f"+ {out['n_official_sec_releases']} SEC Releases; 100% two-way citation sync confirmed!",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
