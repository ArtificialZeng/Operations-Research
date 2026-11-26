"""Pillar 7: Live Crossref DOI Verification & 100% Body-to-Bibliography Citation Audit.

Verifies every academic DOI in manuscript_i4_boost.md live via Crossref REST API
(https://api.crossref.org/works/{doi}), records official SEC Release citations, and
asserts 100% two-way consistency between in-text citations and the References section.
"""

from __future__ import annotations

import json
import re
import time
from pathlib import Path

import requests

WORK_DIR = Path(r"D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126")
MD_PATH = WORK_DIR / "manuscript_i4_boost.md"
OUT_PATH = WORK_DIR / "results" / "07_verified_references_crossref.json"

HEADERS = {"User-Agent": "AcademicResearch/1.0 (mailto:research@university.edu)"}

# Expected citation match tokens (author surname + year or SEC release number) for each bibliography entry
REF_MATCH_SPECS = [
    ("Abadie et al., 2023", r"Abadie et al\., 2023", "10.1093/qje/qjac038"),
    ("Allcott, Egan, Smeets, and Yang, 2026", r"Allcott, Egan, Smeets, and Yang, 2026", "10.3386/w34624"),
    ("Barber, Huang, and Odean, 2016", r"Barber, Huang, and Odean, 2016", "10.1093/rfs/hhw054"),
    ("Berk and Green, 2004", r"Berk and Green, 2004", "10.1086/424739"),
    ("Cameron, Gelbach, and Miller, 2008", r"Cameron, Gelbach, and Miller, 2008", "10.1162/rest.90.3.414"),
    ("Chevalier and Ellison, 1997", r"Chevalier and Ellison, 1997", "10.1086/516389"),
    ("Cooper, Gulen, and Rau, 2005", r"Cooper, Gulen, and Rau(?:\s*\(2005\)|,\s*2005)", "10.1111/j.1540-6261.2005.00818.x"),
    ("Espenlaub, ul Haq, and Khurshed, 2017", r"Espenlaub, ul Haq, and Khurshed, 2017", "10.1016/j.jbankfin.2017.07.008"),
    ("Fisch and Robertson, 2023", r"Fisch and Robertson, 2023", "10.2139/ssrn.4398419"),
    ("Gibson Brandon et al., 2022", r"Gibson Brandon et al\., 2022", "10.1093/rof/rfac064"),
    ("Hartzmark and Sussman, 2019", r"Hartzmark and Sussman, 2019", "10.1111/jofi.12841"),
    ("Kacperczyk, Sialm, and Zheng, 2008", r"Kacperczyk, Sialm, and Zheng, 2008", "10.1093/rfs/hhl041"),
    ("Kim and Yoon, 2023", r"Kim and Yoon, 2023", "10.1287/mnsc.2022.4394"),
    ("Pástor, Stambaugh, and Taylor, 2021", r"Pástor, Stambaugh, and Taylor, 2021", "10.1016/j.jfineco.2020.12.011"),
    ("Roodman et al., 2019", r"Roodman et al\., 2019", "10.1177/1536867X19830877"),
    ("Sensoy, 2009", r"Sensoy, 2009", "10.1016/j.jfineco.2008.02.011"),
    ("Sirri and Tufano, 1998", r"Sirri and Tufano, 1998", "10.1111/0022-1082.00066"),
    ("SEC IC-24828 (2001)", r"IC-24828", None),
    ("SEC IC-35000 (2023)", r"IC-35000", None),
    ("SEC IC-35500 (2025)", r"IC-35500", None),
    ("SEC IC-35962 (2026)", r"IC-35962", None),
]


def main() -> int:
    md_text = MD_PATH.read_text(encoding="utf-8")
    parts = md_text.split("## References")
    assert len(parts) == 2, "Expected exactly one '## References' section in manuscript."
    body_text, refs_text = parts[0], parts[1]

    ref_lines = [ln.strip() for ln in refs_text.splitlines() if re.match(r"^\d+\.\s+", ln.strip())]
    assert len(ref_lines) == len(REF_MATCH_SPECS), f"Ref count mismatch: {len(ref_lines)} vs {len(REF_MATCH_SPECS)}"

    # Extract all DOIs listed in References
    dois_in_refs = re.findall(r"DOI:\s*`([^`]+)`", refs_text)
    expected_dois = [d for _, _, d in REF_MATCH_SPECS if d is not None]
    assert set(dois_in_refs) == set(expected_dois), f"DOI set mismatch: {set(dois_in_refs) ^ set(expected_dois)}"

    sess = requests.Session()
    sess.headers.update(HEADERS)

    verified_dois = []
    uncited_in_body = []
    for label, pat, doi in REF_MATCH_SPECS:
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
                    "crossref_year": (msg.get("published-print") or msg.get("published-online") or msg.get("issued") or {}).get("date-parts", [[None]])[0][0],
                    "body_citation_count": cited_hits,
                }
            )
            time.sleep(0.08)
        else:
            verified_dois.append(
                {
                    "label": label,
                    "doi": None,
                    "official_sec_release": True,
                    "body_citation_count": cited_hits,
                }
            )

    # Check that NO uncited bibliography items exist
    assert len(uncited_in_body) == 0, f"Uncited bibliography items found: {uncited_in_body}"

    # Check that every `Author, YYYY` citation in body matches a verified Crossref author-year pair!
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
        f"[DONE STEP 7] Verified {out['n_academic_dois_verified_live_crossref']}/{out['n_academic_dois_verified_live_crossref']} academic DOIs live via Crossref "
        f"+ {out['n_official_sec_releases']} SEC Releases; 100% two-way citation sync confirmed!",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
