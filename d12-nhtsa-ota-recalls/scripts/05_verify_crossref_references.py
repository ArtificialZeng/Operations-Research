"""Step 5: Verify all peer-reviewed manuscript references against the live Crossref API."""
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
    "User-Agent": "AcademicResearch-CrossrefVerify/1.0 (mailto:research@university.edu)",
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
                    pub = (
                        it.get("published-print")
                        or it.get("published-online")
                        or it.get("issued")
                        or {}
                    )
                    parts = pub.get("date-parts", [[None]])[0]
                    year = parts[0] if parts else None
                    author_str = ", ".join(
                        f"{a.get('family', '')}, {a.get('given', '')[:1]}."
                        for a in authors[:6]
                        if a.get("family")
                    )
                    return {
                        "verified": True,
                        "doi": doi,
                        "title": it_title,
                        "authors": author_str,
                        "journal": container,
                        "year": year,
                        "volume": it.get("volume"),
                        "issue": it.get("issue"),
                        "page": it.get("page"),
                    }
            return {"verified": False, "query_title": title}
        except (requests.RequestException, ValueError, OSError) as exc:
            print(f"[WARN] Crossref retry {attempt} for {first_author}: {exc}", flush=True)
            time.sleep(2.0 * attempt)
    return {"verified": False, "query_title": title}


def main() -> None:
    out = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "references": {},
    }
    for key, title, author in QUERIES:
        res = query_crossref(title, author)
        out["references"][key] = res
        status = f"OK doi={res.get('doi')} ({res.get('year')}, {res.get('journal')})" if res.get("verified") else "MISS"
        print(f"[{key}] {status}", flush=True)
        time.sleep(0.25)

    out_path = PROC_DIR / "verified_references.json"
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    n_ok = sum(1 for v in out["references"].values() if v.get("verified"))
    print(f"[DONE] Verified {n_ok}/{len(QUERIES)} references -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
