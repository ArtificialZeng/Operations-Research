"""Stage 0B frontier literature & information-boundary audit (strictly non-outcome).

Fetches exact metadata (zero real holdout price fitting) for:
  1. Close 2022-2026 conformal EPF / multivalid / online storage papers:
       - arXiv:2611.03661 (Agrawal & O'Sullivan, UK GB tail reliability)
       - Crossref DOI 10.1145/3744255.3798116 (ACM conformal risk-aware online storage)
       - Crossref DOI 10.2139/ssrn.6731093 (decision-level conformal BESS)
       - arXiv:2206.01067 (Bastani et al., NeurIPS 2022 MVP) & arXiv:2208.08401 (Gibbs & Candes, JMLR 2024)
  2. Official SMARD PV/wind forecast deadline page verifying 18:00 next-day submission vs 12:00 auction gate.
  3. EnergyBench (`ujohn33/foretec-energy-bench` HuggingFace & GitHub) frozen pre-gate dataset audit:
     exact files, sizes, README pre-gate spec, and date coverage (zero holdout modeling).
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET

OUT_PATH = Path(__file__).resolve().parent / "stage0b_frontier_and_boundary_audit.json"
HEADERS = {"User-Agent": "Academic-Research-Stage0B-Audit/1.0"}


def fetch(url: str, timeout: float = 25.0) -> tuple[int, bytes | None, str | None, float]:
    t0 = perf_counter()
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
            return int(r.status), r.read(), None, round(perf_counter() - t0, 3)
    except HTTPError as e:
        return int(e.code), None, f"HTTPError {e.code}: {e.reason}", round(perf_counter() - t0, 3)
    except URLError as e:
        return 0, None, f"URLError: {e.reason}", round(perf_counter() - t0, 3)
    except Exception as e:  # noqa: BLE001
        return 0, None, f"{type(e).__name__}: {e}", round(perf_counter() - t0, 3)


def check_arxiv() -> dict:
    ids = ["2611.03661", "2206.01067", "2208.08401"]
    url = f"https://export.arxiv.org/api/query?id_list={','.join(ids)}"
    st, raw, err, dt = fetch(url)
    papers = []
    if st == 200 and raw:
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        root = ET.fromstring(raw.decode("utf-8"))
        for entry in root.findall("atom:entry", ns):
            papers.append(
                {
                    "id": entry.findtext("atom:id", "", ns).strip(),
                    "title": " ".join(entry.findtext("atom:title", "", ns).split()),
                    "authors": [a.findtext("atom:name", "", ns).strip() for a in entry.findall("atom:author", ns)],
                    "published": entry.findtext("atom:published", "", ns).strip(),
                    "updated": entry.findtext("atom:updated", "", ns).strip(),
                    "summary_snippet": " ".join(entry.findtext("atom:summary", "", ns).split())[:500],
                }
            )
    return {"url": url, "http_status": st, "error": err, "elapsed_seconds": dt, "papers": papers}


def check_crossref(doi: str) -> dict:
    url = f"https://api.crossref.org/works/{doi}"
    st, raw, err, dt = fetch(url)
    out = {"doi": doi, "url": url, "http_status": st, "error": err, "elapsed_seconds": dt}
    if st == 200 and raw:
        msg = json.loads(raw.decode("utf-8")).get("message", {})
        out["title"] = msg.get("title", [])
        out["container_title"] = msg.get("container-title", [])
        out["authors"] = [
            f"{a.get('given', '')} {a.get('family', '')}".strip() for a in msg.get("author", [])
        ]
        out["published"] = msg.get("published") or msg.get("created")
    return out


def check_smard_release_page() -> dict:
    url = "https://www.smard.de/home/neu-prognostizierte-pv-und-windenergieeinspeisung-208702"
    st, raw, err, dt = fetch(url)
    out = {"url": url, "http_status": st, "error": err, "elapsed_seconds": dt}
    if st == 200 and raw:
        txt = raw.decode("utf-8", errors="replace")
        plain = re.sub(r"<[^>]+>", " ", txt)
        plain = " ".join(plain.split())
        m = re.search(r"(.{0,180}18:00.{0,220})", plain)
        out["mentions_18_00"] = bool(m)
        out["excerpt_around_18_00"] = m.group(1) if m else None
    return out


def check_energybench() -> dict:
    hf_meta_url = "https://huggingface.co/api/datasets/ujohn33/foretec-energy-bench"
    hf_tree_url = "https://huggingface.co/api/datasets/ujohn33/foretec-energy-bench/tree/main"
    hf_readme_url = "https://huggingface.co/datasets/ujohn33/foretec-energy-bench/raw/main/README.md"
    gh_url = "https://api.github.com/repos/ujohn33/foretec-energy-bench"

    st_m, raw_m, err_m, dt_m = fetch(hf_meta_url)
    st_t, raw_t, err_t, dt_t = fetch(hf_tree_url)
    st_r, raw_r, err_r, dt_r = fetch(hf_readme_url)
    st_g, raw_g, err_g, dt_g = fetch(gh_url)

    out: dict = {
        "hf_meta_status": st_m,
        "hf_tree_status": st_t,
        "hf_readme_status": st_r,
        "github_status": st_g,
    }
    if st_m == 200 and raw_m:
        m = json.loads(raw_m.decode("utf-8"))
        out["hf_last_modified"] = m.get("lastModified")
        out["hf_tags"] = m.get("tags", [])[:20]
        out["hf_card_data"] = m.get("cardData")
    if st_t == 200 and raw_t:
        items = json.loads(raw_t.decode("utf-8"))
        out["hf_root_items"] = [{"path": x.get("path"), "type": x.get("type"), "size": x.get("size")} for x in items]
        # Also inspect subdirectories one level deep
        sub_trees = {}
        for x in items:
            if x.get("type") == "directory":
                dpath = x.get("path")
                sst, sraw, _, _ = fetch(f"https://huggingface.co/api/datasets/ujohn33/foretec-energy-bench/tree/main/{dpath}")
                if sst == 200 and sraw:
                    sitems = json.loads(sraw.decode("utf-8"))
                    sub_trees[dpath] = {
                        "count": len(sitems),
                        "sample": [{"path": s.get("path"), "type": s.get("type"), "size": s.get("size")} for s in sitems[:15]],
                    }
        out["hf_subtrees"] = sub_trees
    if st_r == 200 and raw_r:
        out["hf_readme_excerpt"] = raw_r.decode("utf-8", errors="replace")[:3500]
    if st_g == 200 and raw_g:
        g = json.loads(raw_g.decode("utf-8"))
        out["github_license"] = (g.get("license") or {}).get("spdx_id")
        out["github_updated_at"] = g.get("updated_at")
        out["github_description"] = g.get("description")
    return out


def main() -> None:
    t0 = perf_counter()
    report = {
        "stage": "stage_0b_frontier_literature_and_information_boundary_audit",
        "zero_real_holdout_outcomes_fitted_or_inspected": True,
        "arxiv_close_papers": check_arxiv(),
        "crossref_acm_storage": check_crossref("10.1145/3744255.3798116"),
        "crossref_ssrn_bess": check_crossref("10.2139/ssrn.6731093"),
        "smard_official_release_deadline": check_smard_release_page(),
        "energybench_frozen_inputs": check_energybench(),
        "total_elapsed_seconds": round(perf_counter() - t0, 3),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT_PATH} elapsed={report['total_elapsed_seconds']}s")
    print("ARXIV:", [(p["id"], p["title"]) for p in report["arxiv_close_papers"]["papers"]])
    print("ACM:", report["crossref_acm_storage"].get("title"), report["crossref_acm_storage"].get("container_title"))
    print("SSRN:", report["crossref_ssrn_bess"].get("title"))
    print("SMARD_18_00:", report["smard_official_release_deadline"].get("mentions_18_00"), report["smard_official_release_deadline"].get("excerpt_around_18_00"))
    print("ENERGYBENCH_ROOT:", report["energybench_frozen_inputs"].get("hf_root_items"))


if __name__ == "__main__":
    main()
