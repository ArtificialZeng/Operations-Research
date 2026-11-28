"""Step 2: Fetch expanded 52-journal candidate peer life-science OpenAlex benchmark
panel (2021H1-2026H1 complete half-years) AND eLife 2021H1-2022H2 with 16 major
research nations via single-call OpenAlex `group_by=authorships.countries:include_unknown`.
Exact country-affiliation coverage is computed directly as `n_has_geo = n_all - n_unknown`
(verified to the exact integer against `institutions.country_code:!null`).
"""
from __future__ import annotations

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126")
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"

UA = "H6fBoostResearch/1.0 (academic-science-of-science; mailto:research@university.edu)"
MAILTO = "research@university.edu"

COUNTRIES = [
    "US", "CN", "GB", "DE", "FR", "NL", "ES", "IT",
    "IN", "JP", "CA", "CH", "AU", "BR", "KR", "SE",
]

# 52 premier life-science peer journals (18 Wave-4B + 34 expanded research journals)
# Programmatically filtered in Step 3 strictly to >=90% true country-affiliation coverage
# across EVERY complete half-year 2021H1-2026H1 and >=40 articles/half-year!
CANDIDATE_JOURNALS: dict[str, str] = {
    # Original 18 Wave-4B peer biology journals
    "PLOS Biology": "1545-7885",
    "Nature Communications": "2041-1723",
    "Cell Reports": "2211-1247",
    "PNAS": "0027-8424",
    "Science Advances": "2375-2548",
    "EMBO Journal": "0261-4189",
    "EMBO Reports": "1469-221X",
    "PLOS Genetics": "1553-7404",
    "Molecular Biology and Evolution": "0737-4038",
    "Genome Biology": "1474-760X",
    "Genome Research": "1088-9051",
    "Nucleic Acids Research": "0305-1048",
    "Development": "0950-1991",
    "Genes & Development": "0890-9369",
    "Communications Biology": "2399-3642",
    "PLOS Pathogens": "1553-7374",
    "PLOS Computational Biology": "1553-7358",
    "BMC Biology": "1741-7007",
    # Expanded 34 flagship & society life-science journals
    "Nature": "0028-0836",
    "Science": "0036-8075",
    "Cell": "0092-8674",
    "Current Biology": "0960-9822",
    "Molecular Cell": "1097-2765",
    "Developmental Cell": "1534-5807",
    "Cell Systems": "2405-4712",
    "Nature Cell Biology": "1465-7392",
    "Nature Genetics": "1061-4036",
    "Nature Neuroscience": "1097-6256",
    "Nature Immunology": "1529-2908",
    "Nature Structural & Molecular Biology": "1545-9993",
    "Nature Microbiology": "2058-5276",
    "Nature Metabolism": "2522-5812",
    "Nature Ecology & Evolution": "2397-334X",
    "Nature Chemical Biology": "1552-4450",
    "Nature Plants": "2055-0278",
    "Neuron": "0896-6273",
    "Immunity": "1074-7613",
    "Cell Metabolism": "1550-4131",
    "Cell Host & Microbe": "1931-3128",
    "Journal of Cell Biology": "0021-9525",
    "Journal of Experimental Medicine": "0022-1007",
    "Journal of Neuroscience": "0270-6474",
    "Journal of Cell Science": "0021-9533",
    "Molecular Biology of the Cell": "1059-1524",
    "Proc. R. Soc. B": "0962-8452",
    "iScience": "2589-0042",
    "Cell Death & Differentiation": "1350-9047",
    "mBio": "2150-7511",
    "Genetics": "0016-6731",
    "Open Biology": "2046-2441",
    "Journal of Biological Chemistry": "0021-9258",
    "Life Science Alliance": "2575-1077",
    "Molecular Systems Biology": "1744-4292",
    "EMBO Molecular Medicine": "1757-4676",
    # Additional 12 selective society & disciplinary life-science research journals (high geo metadata fidelity)
    "eNeuro": "2373-2822",
    "G3 Genes|Genomes|Genetics": "2160-1836",
    "RNA": "1355-8382",
    "The Plant Cell": "1040-4651",
    "Plant Physiology": "0032-0889",
    "Journal of Molecular Biology": "0022-2836",
    "Biophysical Journal": "0006-3495",
    "Journal of Virology": "0022-538X",
    "Journal of Bacteriology": "0021-9193",
    "Journal of Immunology": "0022-1767",
    "Molecular Ecology": "0962-1083",
    "BMC Genomics": "1471-2164",
}


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_lf(path: Path, obj) -> str:
    txt = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(txt.encode("utf-8"))
    return sha256_bytes(path)


def build_complete_periods() -> list[tuple[str, str, str, int, int]]:
    periods: list[tuple[str, str, str, int, int]] = []
    for yr in range(2021, 2027):
        periods.append((f"{yr}H1", f"{yr}-01-01", f"{yr}-06-30", yr, 1))
        if yr < 2026:
            periods.append((f"{yr}H2", f"{yr}-07-01", f"{yr}-12-31", yr, 2))
    return periods


def verify_source_issns() -> dict[str, dict]:
    """Verify every candidate journal ISSN in OpenAlex /sources (batch-cached)."""
    cache = DATA_DIR / "openalex_candidate_sources_verified.json"
    existing: dict[str, dict] = {}
    if cache.exists():
        existing = json.loads(cache.read_bytes().decode("utf-8"))

    all_j = {"eLife": "2050-084X", **CANDIDATE_JOURNALS}
    todo = {k: v for k, v in all_j.items() if k not in existing}
    if todo:
        sess = requests.Session()
        sess.headers.update({"User-Agent": UA})
        print(f"[OpenAlex Sources] Verifying {len(todo)} additional journal ISSNs...", flush=True)
        for name, issn in todo.items():
            for attempt in range(4):
                try:
                    r = sess.get(
                        "https://api.openalex.org/sources",
                        params={"filter": f"issn:{issn}", "per-page": 1, "mailto": MAILTO},
                        timeout=30,
                    )
                    if r.status_code == 200:
                        res = r.json().get("results") or []
                        if res:
                            s = res[0]
                            existing[name] = {
                                "issn": issn,
                                "openalex_id": s.get("id", ""),
                                "display_name": s.get("display_name", ""),
                                "works_count": int(s.get("works_count") or 0),
                                "issn_l": s.get("issn_l", ""),
                                "host_org": s.get("host_organization_name", ""),
                            }
                            break
                    time.sleep(1.0 * (attempt + 1))
                except (requests.RequestException, ValueError, KeyError):
                    time.sleep(1.2 * (attempt + 1))
        write_json_lf(cache, existing)
    print(f"[OpenAlex Sources] Total verified: {len(existing)}/{len(all_j)} journals.", flush=True)
    return existing


def query_one_cell(jname: str, issn: str, plabel: str, d1: str, d2: str, yr: int, half: int) -> dict:
    """Single-call OpenAlex group_by=authorships.countries:include_unknown for exact counts & geo coverage."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    base = f"primary_location.source.issn:{issn},type:article,from_publication_date:{d1},to_publication_date:{d2}"
    for attempt in range(6):
        try:
            r = sess.get(
                "https://api.openalex.org/works",
                params={"filter": base, "group_by": "authorships.countries:include_unknown", "mailto": MAILTO},
                timeout=35,
            )
            if r.status_code == 429:
                time.sleep(3.0 * (attempt + 1))
                continue
            if r.status_code == 200:
                time.sleep(0.15)
                j = r.json()
                tot = int(j.get("meta", {}).get("count", 0))
                cdict: dict[str, int] = {}
                n_unknown = 0
                for g in j.get("group_by", []):
                    k = str(g.get("key") or "").split("/")[-1].upper()
                    cnt = int(g.get("count") or 0)
                    if k == "UNKNOWN":
                        n_unknown = cnt
                    else:
                        cdict[k] = cnt
                n_has_geo = max(tot - n_unknown, 0)
                rec: dict = {
                    "journal": jname,
                    "issn": issn,
                    "period": plabel,
                    "year": yr,
                    "half": half,
                    "n_all": tot,
                    "n_unknown_geo": n_unknown,
                    "n_has_geo": n_has_geo,
                    "error": False,
                }
                for cc in COUNTRIES:
                    rec[f"n_{cc}"] = cdict.get(cc, 0)
                return rec
            time.sleep(1.5 * (attempt + 1))
        except (requests.RequestException, ValueError, KeyError):
            time.sleep(1.5 * (attempt + 1))
    return {
        "journal": jname,
        "issn": issn,
        "period": plabel,
        "year": yr,
        "half": half,
        "error": True,
    }


def fetch_expanded_panel(verified_sources: dict[str, dict]) -> list[dict]:
    """Fetch and checkpoint all journal x complete half-year OpenAlex cells cleanly."""
    cache_jsonl = DATA_DIR / "expanded_openalex_panel_v2.jsonl"
    existing: dict[tuple[str, str], dict] = {}
    if cache_jsonl.exists():
        for line in cache_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if not rec.get("error") and "n_unknown_geo" in rec:
                existing[(rec["journal"], rec["period"])] = rec

    periods = build_complete_periods()
    tasks: list[tuple[str, str, str, str, str, int, int]] = []

    for pl, d1, d2, yr, h in periods:
        if yr <= 2022 and ("eLife", pl) not in existing:
            tasks.append(("eLife", "2050-084X", pl, d1, d2, yr, h))

    for jname, issn in CANDIDATE_JOURNALS.items():
        if jname not in verified_sources:
            continue
        for pl, d1, d2, yr, h in periods:
            if (jname, pl) not in existing:
                tasks.append((jname, issn, pl, d1, d2, yr, h))

    print(
        f"[OpenAlex Expanded Panel v2] Candidate donors={len(CANDIDATE_JOURNALS)} | cached={len(existing):,} | to fetch={len(tasks):,}",
        flush=True,
    )
    if tasks:
        t0 = time.time()
        done = 0
        ok_cnt = 0
        with cache_jsonl.open("a", encoding="utf-8", newline="\n") as fh, ThreadPoolExecutor(max_workers=3) as ex:
            futs = {ex.submit(query_one_cell, *t): t for t in tasks}
            for fut in as_completed(futs):
                rec = fut.result()
                done += 1
                if not rec.get("error"):
                    ok_cnt += 1
                fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if done % 60 == 0 or done == len(tasks):
                    fh.flush()
                    print(
                        f"  OpenAlex cells {done:,}/{len(tasks):,} (OK={ok_cnt:,}) | {time.time()-t0:.1f}s",
                        flush=True,
                    )

    dedup: dict[tuple[str, str], dict] = {}
    for line in cache_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        key = (rec["journal"], rec["period"])
        if key not in dedup or (not rec.get("error") and dedup[key].get("error")):
            dedup[key] = rec
    rows = [dedup[k] for k in sorted(dedup)]
    out_json = DATA_DIR / "expanded_openalex_panel_2021_2026.json"
    write_json_lf(out_json, rows)
    n_err = sum(1 for r in rows if r.get("error"))
    print(f"[OpenAlex Expanded Panel v2] Saved {len(rows):,} cells ({n_err} errors) -> {out_json.name}", flush=True)
    return rows


def main() -> None:
    t0 = time.time()
    print("=== STEP 2: FETCH EXPANDED 54-JOURNAL CANDIDATE OPENALEX PANEL (EXACT SINGLE-CALL GEO AUDIT) ===", flush=True)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    RES_DIR.mkdir(parents=True, exist_ok=True)
    # Remove stale partial v1 cache if present
    stale = DATA_DIR / "expanded_openalex_panel_cells.jsonl"
    if stale.exists():
        stale.unlink()

    verified = verify_source_issns()
    rows = fetch_expanded_panel(verified)

    by_j: dict[str, list[dict]] = {}
    for r in rows:
        if r.get("error"):
            continue
        by_j.setdefault(r["journal"], []).append(r)

    clean_list = []
    excluded_list = []
    for jn, recs in sorted(by_j.items()):
        if jn == "eLife":
            continue
        if len(recs) < 11:
            excluded_list.append({"journal": jn, "reason": f"incomplete_periods({len(recs)})"})
            continue
        covs = [100.0 * r["n_has_geo"] / max(r["n_all"], 1) for r in recs]
        n_alls = [r["n_all"] for r in recs]
        min_cov = min(covs)
        min_n = min(n_alls)
        med_n = sorted(n_alls)[len(n_alls) // 2]
        min_ratio = min_n / max(med_n, 1)
        if min_cov >= 90.0 and min_n >= 40 and min_ratio >= 0.30:
            clean_list.append({
                "journal": jn,
                "min_geo_cov": round(min_cov, 2),
                "mean_geo_cov": round(sum(covs) / len(covs), 2),
                "min_n_half": int(min_n),
                "mean_n_half": round(sum(n_alls) / len(n_alls), 1),
            })
        else:
            excluded_list.append({
                "journal": jn,
                "min_geo_cov": round(min_cov, 2),
                "min_n_half": int(min_n),
                "min_ratio": round(min_ratio, 3),
                "reason": "failed_strict_audit",
            })

    print(
        f"[Donor Audit] Clean donors (>=90% TRUE geo cov, >=40 arts/half, no break): "
        f"{len(clean_list)} / {len(CANDIDATE_JOURNALS)} (Excluded: {len(excluded_list)})",
        flush=True,
    )
    for ex_r in excluded_list:
        print(f"  EXCLUDED: {ex_r}", flush=True)

    receipt = {
        "n_candidates": len(CANDIDATE_JOURNALS),
        "n_verified_sources": len(verified),
        "n_clean_donors": len(clean_list),
        "n_total_with_elife": len(clean_list) + 1,
        "clean_donors": clean_list,
        "excluded_donors": excluded_list,
        "panel_json_sha256": sha256_bytes(DATA_DIR / "expanded_openalex_panel_2021_2026.json"),
        "elapsed_sec": round(time.time() - t0, 2),
    }
    write_json_lf(RES_DIR / "02_expanded_openalex_receipt.json", receipt)
    print(f"[DONE STEP 2] Elapsed {receipt['elapsed_sec']}s | Total clean panel N={receipt['n_total_with_elife']} journals!", flush=True)


if __name__ == "__main__":
    main()
