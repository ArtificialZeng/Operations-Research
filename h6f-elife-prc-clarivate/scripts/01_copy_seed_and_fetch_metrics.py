"""Step 1: Copy verified read-only Wave-4B seed caches into local data/ and fetch
live eLife article-level monthly page-views and downloads for all mature 2023-2024
v1 PRC papers (N ~ 2,653) via api.elifesciences.org/metrics/article/{eid}/.
"""
from __future__ import annotations

import hashlib
import json
import shutil
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126")
DATA_DIR = BASE_DIR / "data"
SEED_DIR = Path(r"D:\AI_Science\antigravity\frontier_discovery_20261126_wave4b_clean\h6f_clean")

UA = "H6fBoostResearch/1.0 (academic-science-of-science; mailto:research@university.edu)"

SEED_FILES = [
    "elife_prc_search_census.json",
    "elife_v1_assessments.json",
    "crossref_elife_2023_2026.json",
    "openalex_elife_prc_dois.json",
    "openalex_preprint_dois.json",
    "elife_blog_7da92a51_ground_truth.json",
    "r2_sent_for_review_sample.json",
    "r2_elife_110392_editorial.json",
    "r2_elife_openalex_all_2021_2026.json",
]


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def copy_seed_caches() -> dict[str, str]:
    """Read-only copy of verified Wave-4B raw JSON caches into local data/."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    receipts: dict[str, str] = {}
    for fname in SEED_FILES:
        src = SEED_DIR / fname
        dst = DATA_DIR / fname
        if not src.exists():
            raise FileNotFoundError(f"Missing required seed cache: {src}")
        if not dst.exists() or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        receipts[fname] = sha256_bytes(dst)
        print(f"  [Seed Copy] {fname:40s} | {dst.stat().st_size:>10,} bytes", flush=True)
    return receipts


def get_mature_2023_2024_eids() -> list[str]:
    """Return sorted unique eids with true v1 date in 2023-01-01..2024-12-31."""
    prc = json.loads((DATA_DIR / "elife_prc_search_census.json").read_bytes().decode("utf-8"))
    v1_map = json.loads((DATA_DIR / "elife_v1_assessments.json").read_bytes().decode("utf-8"))
    eids: list[str] = []
    for it in prc:
        eid = str(it.get("id") or "").strip()
        v1 = v1_map.get(eid, {})
        if v1.get("v1_status") != 200:
            continue
        v1_dt = (v1.get("v1_reviewedDate") or v1.get("v1_published") or "")[:10]
        if "2023-01-01" <= v1_dt <= "2024-12-31":
            eids.append(eid)
    return sorted(set(eids))


def fetch_one_metric_pair(eid: str) -> dict:
    """Fetch monthly page-views and downloads for one eLife article eid."""
    sess = requests.Session()
    sess.headers.update({"User-Agent": UA})
    out: dict = {"eid": eid}
    for key, endpoint in [("pv", "page-views"), ("dl", "downloads")]:
        url = f"https://api.elifesciences.org/metrics/article/{eid}/{endpoint}"
        status = -1
        total_val = None
        periods: list[dict] = []
        for attempt in range(5):
            try:
                r = sess.get(url, params={"by": "month", "per-page": 100}, timeout=30)
                status = r.status_code
                if status == 200:
                    j = r.json()
                    total_val = int(j.get("totalValue", 0))
                    periods = [
                        {"p": str(x.get("period", "")), "v": int(x.get("value", 0))}
                        for x in (j.get("periods") or [])
                    ]
                    break
                if status == 404:
                    break
                time.sleep(1.0 * (attempt + 1))
            except (requests.RequestException, ValueError, KeyError):
                time.sleep(1.2 * (attempt + 1))
        out[f"{key}_status"] = status
        out[f"{key}_total"] = total_val
        out[f"{key}_periods"] = periods
    return out


def fetch_all_article_metrics(eids: list[str]) -> Path:
    """Fetch and checkpoint live eLife page-views & downloads to JSONL."""
    cache_jsonl = DATA_DIR / "elife_article_metrics_2023_2024.jsonl"
    existing: dict[str, dict] = {}
    if cache_jsonl.exists():
        for line in cache_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("pv_status") == 200 and rec.get("dl_status") == 200:
                existing[str(rec["eid"])] = rec

    todo = [e for e in eids if e not in existing]
    print(
        f"[eLife Metrics] Total mature 2023-2024 eids={len(eids):,} | cached OK={len(existing):,} | to fetch={len(todo):,}",
        flush=True,
    )
    if not todo:
        return cache_jsonl

    t0 = time.time()
    done = 0
    ok_new = 0
    with cache_jsonl.open("a", encoding="utf-8", newline="\n") as fh, ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_one_metric_pair, eid): eid for eid in todo}
        for fut in as_completed(futs):
            rec = fut.result()
            done += 1
            if rec.get("pv_status") == 200 and rec.get("dl_status") == 200:
                ok_new += 1
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if done % 200 == 0 or done == len(todo):
                fh.flush()
                el = time.time() - t0
                rate = done / max(el, 0.1)
                print(
                    f"  metrics fetched {done:,}/{len(todo):,} (200 OK={ok_new:,}) | {el:.1f}s ({rate:.1f}/s)",
                    flush=True,
                )

    # Deduplicate JSONL cleanly in sorted eid order so file is deterministic and clean
    dedup: dict[str, dict] = {}
    for line in cache_jsonl.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        rec = json.loads(line)
        eid = str(rec["eid"])
        if eid not in dedup or (rec.get("pv_status") == 200 and dedup[eid].get("pv_status") != 200):
            dedup[eid] = rec
    clean_lines = [json.dumps(dedup[k], ensure_ascii=False) for k in sorted(dedup)]
    cache_jsonl.write_bytes(("\n".join(clean_lines) + "\n").encode("utf-8"))
    n_ok = sum(1 for v in dedup.values() if v.get("pv_status") == 200 and v.get("dl_status") == 200)
    print(
        f"[eLife Metrics] Finalized {cache_jsonl.name}: {n_ok:,}/{len(eids):,} ({100.0*n_ok/max(len(eids),1):.2f}%) HTTP 200!",
        flush=True,
    )
    return cache_jsonl


def main() -> None:
    t0 = time.time()
    print("=== STEP 1: COPY VERIFIED SEED CACHES & FETCH LIVE eLIFE ARTICLE METRICS ===", flush=True)
    seed_receipts = copy_seed_caches()
    eids = get_mature_2023_2024_eids()
    cache_jsonl = fetch_all_article_metrics(eids)

    # Also save summary receipt
    rec_out = {
        "n_mature_eids": len(eids),
        "seed_files_sha256": seed_receipts,
        "metrics_jsonl": cache_jsonl.name,
        "metrics_jsonl_sha256": sha256_bytes(cache_jsonl),
        "elapsed_sec": round(time.time() - t0, 2),
    }
    res_path = BASE_DIR / "results" / "01_seed_and_metrics_receipt.json"
    res_path.write_bytes((json.dumps(rec_out, indent=2) + "\n").encode("utf-8"))
    print(f"[DONE STEP 1] Elapsed {rec_out['elapsed_sec']}s -> {res_path.name}", flush=True)


if __name__ == "__main__":
    main()
