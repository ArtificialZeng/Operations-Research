"""Step 07 (Pillar 6): Live Crossref REST API DOI verification and two-way manuscript
citation synchronization audit for K1 /boost.
"""

from __future__ import annotations

import html
import re
import time
from typing import Any

import requests
from econ_utils import RES_DIR, WS_DIR, save_json_lf

HEADERS = {
    "User-Agent": "K1BoostGridBatteryCarbon/1.0 (mailto:research@example.org)"
}

# Authoritative 18-reference bibliography (every entry verified live via Crossref REST API)
REFERENCES: list[dict[str, str]] = [
    {
        "key": "carson2013",
        "cite_token": "Carson & Novan (2013)",
        "alt_token": "Carson & Novan, 2013",
        "authors": "Carson, R. T., & Novan, K.",
        "year": "2013",
        "title": "The private and social economics of bulk electricity storage",
        "journal": "Journal of Environmental Economics and Management",
        "vol_pages": "66(3), 404-423",
        "doi": "10.1016/j.jeem.2013.06.002",
        "expect_author": "Carson",
        "expect_word": "storage",
    },
    {
        "key": "graffzivin2014",
        "cite_token": "Graff Zivin et al. (2014)",
        "alt_token": "Graff Zivin et al., 2014",
        "authors": "Graff Zivin, J. S., Kotchen, M. J., & Mansur, E. T.",
        "year": "2014",
        "title": "Spatial and temporal heterogeneity of marginal emissions: Implications for electric cars and other electricity-shifting policies",
        "journal": "Journal of Economic Behavior & Organization",
        "vol_pages": "107(Part A), 248-268",
        "doi": "10.1016/j.jebo.2014.03.010",
        "expect_author": "Graff Zivin",
        "expect_word": "marginal",
    },
    {
        "key": "hittinger2015",
        "cite_token": "Hittinger & Azevedo (2015)",
        "alt_token": "Hittinger & Azevedo, 2015",
        "authors": "Hittinger, E. S., & Azevedo, I. M. L.",
        "year": "2015",
        "title": "Bulk energy storage increases United States electricity system emissions",
        "journal": "Environmental Science & Technology",
        "vol_pages": "49(5), 3203-3210",
        "doi": "10.1021/es505027p",
        "expect_author": "Hittinger",
        "expect_word": "storage",
    },
    {
        "key": "holland2016",
        "cite_token": "Holland et al. (2016)",
        "alt_token": "Holland et al., 2016",
        "authors": "Holland, S. P., Mansur, E. T., Muller, N. Z., & Yates, A. J.",
        "year": "2016",
        "title": "Are there environmental benefits from driving electric vehicles? The importance of local factors",
        "journal": "American Economic Review",
        "vol_pages": "106(12), 3700-3729",
        "doi": "10.1257/aer.20150897",
        "expect_author": "Holland",
        "expect_word": "electric",
    },
    {
        "key": "fares2017",
        "cite_token": "Fares & Webber (2017)",
        "alt_token": "Fares & Webber, 2017",
        "authors": "Fares, R. L., & Webber, M. E.",
        "year": "2017",
        "title": "The impacts of storing solar energy in the home to reduce reliance on the utility",
        "journal": "Nature Energy",
        "vol_pages": "2(2), 17001",
        "doi": "10.1038/nenergy.2017.1",
        "expect_author": "Fares",
        "expect_word": "solar",
    },
    {
        "key": "fisher2017",
        "cite_token": "Fisher & Apt (2017)",
        "alt_token": "Fisher & Apt, 2017",
        "authors": "Fisher, M. J., & Apt, J.",
        "year": "2017",
        "title": "Emissions and economics of behind-the-meter electricity storage",
        "journal": "Environmental Science & Technology",
        "vol_pages": "51(3), 1094-1101",
        "doi": "10.1021/acs.est.6b03536",
        "expect_author": "Fisher",
        "expect_word": "storage",
    },
    {
        "key": "callaway2018",
        "cite_token": "Callaway et al. (2018)",
        "alt_token": "Callaway et al., 2018",
        "authors": "Callaway, D. S., Fowlie, M., & McCormick, G.",
        "year": "2018",
        "title": "Location, location, location: The variable value of renewable energy and demand-side efficiency resources",
        "journal": "Journal of the Association of Environmental and Resource Economists",
        "vol_pages": "5(1), 39-75",
        "doi": "10.1086/694179",
        "expect_author": "Callaway",
        "expect_word": "renewable",
    },
    {
        "key": "arbabzadeh2019",
        "cite_token": "Arbabzadeh et al. (2019)",
        "alt_token": "Arbabzadeh et al., 2019",
        "authors": "Arbabzadeh, M., Sioshansi, R., Johnson, J. X., & Keoleian, G. A.",
        "year": "2019",
        "title": "The role of energy storage in deep decarbonization of electricity production",
        "journal": "Nature Communications",
        "vol_pages": "10(1), 3413",
        "doi": "10.1038/s41467-019-11161-5",
        "expect_author": "Arbabzadeh",
        "expect_word": "storage",
    },
    {
        "key": "dechalendar2019",
        "cite_token": "de Chalendar et al. (2019)",
        "alt_token": "de Chalendar et al., 2019",
        "authors": "de Chalendar, J. A., Taggart, J., & Benson, S. M.",
        "year": "2019",
        "title": "Tracking emissions in the US electricity system",
        "journal": "Proceedings of the National Academy of Sciences",
        "vol_pages": "116(51), 25497-25502",
        "doi": "10.1073/pnas.1912950116",
        "expect_author": "Chalendar",
        "expect_word": "emissions",
    },
    {
        "key": "holland2022",
        "cite_token": "Holland et al. (2022)",
        "alt_token": "Holland et al., 2022",
        "authors": "Holland, S. P., Kotchen, M. J., Mansur, E. T., & Yates, A. J.",
        "year": "2022",
        "title": "Why marginal CO2 emissions are not decreasing for US electricity: Estimates and implications for climate policy",
        "journal": "Proceedings of the National Academy of Sciences",
        "vol_pages": "119(8), e2116632119",
        "doi": "10.1073/pnas.2116632119",
        "expect_author": "Holland",
        "expect_word": "marginal",
    },
    {
        "key": "butters2025",
        "cite_token": "Butters et al. (2025)",
        "alt_token": "Butters et al., 2025",
        "authors": "Butters, R. A., Dorsey, J., & Gowrisankaran, G.",
        "year": "2025",
        "title": "Soaking up the sun: Battery investment, renewable energy, and market equilibrium",
        "journal": "Econometrica",
        "vol_pages": "93(3), 891-927",
        "doi": "10.3982/ECTA20411",
        "expect_author": "Butters",
        "expect_word": "battery",
    },
    {
        "key": "dupont2026",
        "cite_token": "Dupont et al. (2026)",
        "alt_token": "Dupont et al., 2026",
        "authors": "Dupont, C., Heijmans-Kuryatnikova, O., Ghiassi-Farrokhfal, Y., & Bunn, D.",
        "year": "2026",
        "title": "The unintended carbon impacts of large-scale electricity storage",
        "journal": "Manufacturing & Service Operations Management",
        "vol_pages": "28(2), 663-685",
        "doi": "10.1287/msom.2024.1411",
        "expect_author": "Dupont",
        "expect_word": "storage",
    },
    {
        "key": "cgm2008",
        "cite_token": "Cameron et al. (2008)",
        "alt_token": "Cameron et al., 2008",
        "authors": "Cameron, A. C., Gelbach, J. B., & Miller, D. L.",
        "year": "2008",
        "title": "Bootstrap-based improvements for inference with clustered errors",
        "journal": "Review of Economics and Statistics",
        "vol_pages": "90(3), 414-427",
        "doi": "10.1162/rest.90.3.414",
        "expect_author": "Cameron",
        "expect_word": "bootstrap",
    },
    {
        "key": "cgm2011",
        "cite_token": "Cameron et al. (2011)",
        "alt_token": "Cameron et al., 2011",
        "authors": "Cameron, A. C., Gelbach, J. B., & Miller, D. L.",
        "year": "2011",
        "title": "Robust inference with multiway clustering",
        "journal": "Journal of Business & Economic Statistics",
        "vol_pages": "29(2), 238-249",
        "doi": "10.1198/jbes.2010.07136",
        "expect_author": "Cameron",
        "expect_word": "clustering",
    },
    {
        "key": "mw2018",
        "cite_token": "MacKinnon & Webb (2018)",
        "alt_token": "MacKinnon & Webb, 2018",
        "authors": "MacKinnon, J. G., & Webb, M. D.",
        "year": "2018",
        "title": "The wild bootstrap for few (treated) clusters",
        "journal": "The Econometrics Journal",
        "vol_pages": "21(2), 114-135",
        "doi": "10.1111/ectj.12107",
        "expect_author": "MacKinnon",
        "expect_word": "bootstrap",
    },
    {
        "key": "roodman2019",
        "cite_token": "Roodman et al. (2019)",
        "alt_token": "Roodman et al., 2019",
        "authors": "Roodman, D., Nielsen, M. O., MacKinnon, J. G., & Webb, M. D.",
        "year": "2019",
        "title": "Fast and wild: Bootstrap inference in Stata using boottest",
        "journal": "The Stata Journal",
        "vol_pages": "19(1), 4-60",
        "doi": "10.1177/1536867X19830877",
        "expect_author": "Roodman",
        "expect_word": "bootstrap",
    },
    {
        "key": "abadie2023",
        "cite_token": "Abadie et al. (2023)",
        "alt_token": "Abadie et al., 2023",
        "authors": "Abadie, A., Athey, S., Imbens, G. W., & Wooldridge, J. M.",
        "year": "2023",
        "title": "When should you adjust standard errors for clustering?",
        "journal": "The Quarterly Journal of Economics",
        "vol_pages": "138(1), 1-35",
        "doi": "10.1093/qje/qjac038",
        "expect_author": "Abadie",
        "expect_word": "clustering",
    },
    {
        "key": "webb2023",
        "cite_token": "Webb (2023)",
        "alt_token": "Webb, 2023",
        "authors": "Webb, M. D.",
        "year": "2023",
        "title": "Reworking wild bootstrap-based inference for clustered errors",
        "journal": "Canadian Journal of Economics",
        "vol_pages": "56(3), 839-858",
        "doi": "10.1111/caje.12661",
        "expect_author": "Webb",
        "expect_word": "bootstrap",
    },
]


def verify_all_dois() -> dict[str, Any]:
    results = []
    n_verified = 0
    sess = requests.Session()
    for ref in REFERENCES:
        doi = ref["doi"]
        status = 0
        cr_title = ""
        cr_authors: list[str] = []
        cr_journal = ""
        ok = False
        for attempt in range(1, 6):
            try:
                r = sess.get(f"https://api.crossref.org/works/{doi}", headers=HEADERS, timeout=25)
                status = r.status_code
                if status == 200:
                    msg = r.json()["message"]
                    cr_title = html.unescape(re.sub(r"<[^>]+>", "", (msg.get("title") or [""])[0]))
                    cr_title = re.sub(r"\s+", " ", cr_title).strip()
                    cr_authors = [a.get("family", "") for a in (msg.get("author") or [])]
                    cr_journal = html.unescape((msg.get("container-title") or [""])[0])
                    auth_ok = any(ref["expect_author"].lower() in a.lower() for a in cr_authors)
                    word_ok = ref["expect_word"].lower() in cr_title.lower()
                    ok = bool(auth_ok and word_ok)
                    break
                time.sleep(0.8 * attempt)
            except (requests.RequestException, ValueError, KeyError):
                time.sleep(1.2 * attempt)
        if not ok:
            # Live fallback to official doi.org CSL-JSON content negotiation on transient Crossref timeout
            try:
                r2 = sess.get(
                    f"https://doi.org/{doi}",
                    headers={**HEADERS, "Accept": "application/vnd.citationstyles.csl+json"},
                    timeout=25,
                )
                status = r2.status_code
                if status == 200:
                    msg2 = r2.json()
                    cr_title = re.sub(r"\s+", " ", html.unescape(str(msg2.get("title", "")))).strip()
                    cr_authors = [a.get("family", "") for a in (msg2.get("author") or [])]
                    cr_journal = html.unescape(str(msg2.get("container-title", "")))
                    auth_ok = any(ref["expect_author"].lower() in a.lower() for a in cr_authors)
                    word_ok = ref["expect_word"].lower() in cr_title.lower()
                    ok = bool(auth_ok and word_ok)
            except (requests.RequestException, ValueError, KeyError):
                pass
        if ok:
            n_verified += 1
        results.append(
            {
                "key": ref["key"],
                "doi": doi,
                "http_status": status,
                "verified": ok,
                "crossref_title": cr_title,
                "crossref_authors": cr_authors,
                "crossref_journal": cr_journal,
            }
        )
        print(f"  [{'OK' if ok else 'FAIL'}] {ref['key']:15s} | {doi:28s} | {cr_title[:60]}", flush=True)
        time.sleep(0.05)

    return {
        "n_total": len(REFERENCES),
        "n_verified": n_verified,
        "all_verified": n_verified == len(REFERENCES),
        "entries": results,
    }


def check_manuscript_two_way_sync() -> dict[str, Any]:
    md_path = WS_DIR / "manuscript_k1_boost.md"
    if not md_path.exists():
        return {"checked": False, "reason": "manuscript_k1_boost.md not yet generated"}
    txt = md_path.read_text(encoding="utf-8")
    parts = txt.split("## References")
    if len(parts) != 2:
        raise ValueError("Manuscript must have exactly one '## References' section")
    body, ref_sec = parts[0], parts[1]

    missing_in_body = []
    missing_in_refs = []
    for ref in REFERENCES:
        in_body = (ref["cite_token"] in body) or (ref["alt_token"] in body)
        in_refs = ref["doi"] in ref_sec
        if not in_body:
            missing_in_body.append(ref["key"])
        if not in_refs:
            missing_in_refs.append(ref["key"])

    # Also ensure every DOI in References is in REFERENCES
    dois_in_refs = set(re.findall(r"10\.\d{4,9}/[^\s\)]+", ref_sec))
    known_dois = {r["doi"] for r in REFERENCES}
    unverified_extra = sorted(d.rstrip(".") for d in dois_in_refs if d.rstrip(".") not in known_dois)

    return {
        "checked": True,
        "n_refs": len(REFERENCES),
        "missing_in_body": missing_in_body,
        "missing_in_refs": missing_in_refs,
        "unverified_extra_dois": unverified_extra,
        "two_way_sync_ok": (
            len(missing_in_body) == 0 and len(missing_in_refs) == 0 and len(unverified_extra) == 0
        ),
    }


def main() -> int:
    print("=== STEP 07: LIVE CROSSREF DOI VERIFICATION & TWO-WAY CITATION SYNC ===", flush=True)
    res = verify_all_dois()
    sync = check_manuscript_two_way_sync()
    out = {"crossref": res, "two_way_sync": sync}
    sha = save_json_lf(RES_DIR / "07_citation_verification.json", out)
    print(
        f"[DONE STEP 07] Verified {res['n_verified']}/{res['n_total']} DOIs live via Crossref; "
        f"sync={sync} (SHA-256: {sha})",
        flush=True,
    )
    if not res["all_verified"]:
        return 1
    if sync.get("checked") and not sync.get("two_way_sync_ok"):
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
