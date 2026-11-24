"""Append live arXiv/Crossref metadata for the 4 decisive overlapping EPF works to stage0b_frontier_and_boundary_audit.json."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE / "stage0b_frontier_and_boundary_audit.json"
HEADERS = {"User-Agent": "Academic-Research-EPF-Closure-Audit/1.0"}


def fetch(url: str) -> tuple[int, bytes | None, str | None]:
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=25) as r:
            return int(r.status), r.read(), None
    except Exception as e:
        return 0, None, str(e)


def main() -> None:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    extra = {"arxiv": [], "crossref": {}}

    st, raw, err = fetch("https://export.arxiv.org/api/query?id_list=2512.23671,2508.13362")
    if st == 200 and raw:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw.decode("utf-8"))
        for entry in root.findall("atom:entry", ns):
            extra["arxiv"].append(
                {
                    "id": entry.findtext("atom:id", "", ns).strip(),
                    "title": " ".join(entry.findtext("atom:title", "", ns).split()),
                    "authors": [a.findtext("atom:name", "", ns).strip() for a in entry.findall("atom:author", ns)],
                    "published": entry.findtext("atom:published", "", ns).strip(),
                    "updated": entry.findtext("atom:updated", "", ns).strip(),
                }
            )
    else:
        extra["arxiv_error"] = err

    for doi in ["10.1016/j.apenergy.2025.126412", "10.3390/pr14193119"]:
        cst, craw, cerr = fetch(f"https://api.crossref.org/works/{doi}")
        if cst == 200 and craw:
            msg = json.loads(craw.decode("utf-8")).get("message", {})
            extra["crossref"][doi] = {
                "http_status": cst,
                "title": msg.get("title", []),
                "container_title": msg.get("container-title", []),
                "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in msg.get("author", [])],
                "published": msg.get("published") or msg.get("created"),
            }
        else:
            extra["crossref"][doi] = {"http_status": cst, "error": cerr}

    data["additional_directly_overlapping_works"] = extra
    data["sdac_15min_mtu_launch_note"] = (
        "Per NEMO/SDAC official go-live schedule, European SDAC 15-minute MTU day-ahead delivery began "
        "2025-10-01; historical hourly aggregates cannot enter a 15-minute live evaluation board without "
        "native delivery-slot mapping."
    )
    data["stage_0b_decision"] = "FORMALLY_CLOSED_AT_STAGE_0_NO_OUTCOME_MODELING"
    AUDIT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(extra, indent=2))


if __name__ == "__main__":
    main()
