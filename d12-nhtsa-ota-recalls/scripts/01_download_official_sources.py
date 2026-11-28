"""Step 1: Download all 4 official public NHTSA / U.S. DOT datasets with SHA-256 receipts."""
from __future__ import annotations

import hashlib
import io
import json
import time
import zipfile
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
RAW_DIR = BASE_DIR / "data_raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "AcademicResearch-NHTSAAudit/2.0 (OperationsManagementStudy; contact: research@university.edu)",
    "Accept": "*/*",
}

BULK_FILES = {
    "FLAT_RCL_POST_2010.zip": "https://static.nhtsa.gov/odi/ffdd/rcl/FLAT_RCL_POST_2010.zip",
    "COMPLAINTS_RECEIVED_2020-2024.zip": "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2020-2024.zip",
    "COMPLAINTS_RECEIVED_2025-2026.zip": "https://static.nhtsa.gov/odi/ffdd/cmpl/COMPLAINTS_RECEIVED_2025-2026.zip",
}

DOT_SOCRATA_URL = "https://datahub.transportation.gov/resource/6axg-epim.csv"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def download_stream(url: str, dest: Path, max_retries: int = 4, timeout: int = 60) -> dict:
    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"[CACHE] {dest.name} already exists ({dest.stat().st_size:,} bytes)", flush=True)
        return {
            "url": url,
            "file": dest.name,
            "bytes": dest.stat().st_size,
            "sha256": sha256_file(dest),
            "cached": True,
        }

    part = dest.with_suffix(dest.suffix + ".part")
    last_err: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            print(f"[GET] {dest.name} (attempt {attempt}/{max_retries}) <- {url}", flush=True)
            t0 = time.time()
            with requests.get(url, headers=HEADERS, stream=True, timeout=timeout) as r:
                r.raise_for_status()
                total = 0
                with part.open("wb") as fh:
                    for chunk in r.iter_content(chunk_size=1 << 20):
                        if chunk:
                            fh.write(chunk)
                            total += len(chunk)
                meta = {
                    "url": url,
                    "file": dest.name,
                    "http_status": r.status_code,
                    "last_modified": r.headers.get("Last-Modified"),
                    "etag": r.headers.get("ETag"),
                    "bytes": total,
                    "elapsed_sec": round(time.time() - t0, 2),
                    "cached": False,
                }
            part.replace(dest)
            meta["sha256"] = sha256_file(dest)
            print(
                f"[OK] {dest.name}: {total / 1e6:.2f} MB in {meta['elapsed_sec']}s "
                f"(sha256={meta['sha256'][:16]}...)",
                flush=True,
            )
            return meta
        except (requests.RequestException, OSError) as exc:
            last_err = exc
            print(f"[WARN] Attempt {attempt} failed for {dest.name}: {exc}", flush=True)
            time.sleep(2.5 * attempt)
    raise RuntimeError(f"Failed to download {url}: {last_err}")


def download_dot_socrata_full(dest: Path, page_size: int = 50000) -> dict:
    if dest.exists() and dest.stat().st_size > 1_000_000:
        df_chk = pd.read_csv(dest, low_memory=False)
        print(f"[CACHE] {dest.name} already exists ({len(df_chk):,} rows)", flush=True)
        return {
            "url": DOT_SOCRATA_URL,
            "file": dest.name,
            "rows": len(df_chk),
            "columns": list(df_chk.columns),
            "bytes": dest.stat().st_size,
            "sha256": sha256_file(dest),
            "cached": True,
        }

    frames: list[pd.DataFrame] = []
    offset = 0
    t0 = time.time()
    while True:
        params = {"$limit": str(page_size), "$offset": str(offset), "$order": ":id"}
        last_err: Exception | None = None
        resp_text: str | None = None
        for attempt in range(1, 5):
            try:
                print(
                    f"[GET] DOT Socrata 6axg-epim offset={offset} limit={page_size} (attempt {attempt})",
                    flush=True,
                )
                r = requests.get(DOT_SOCRATA_URL, params=params, headers=HEADERS, timeout=60)
                r.raise_for_status()
                resp_text = r.text
                break
            except (requests.RequestException, OSError) as exc:
                last_err = exc
                print(f"[WARN] Socrata attempt {attempt} failed: {exc}", flush=True)
                time.sleep(2.5 * attempt)
        if resp_text is None:
            raise RuntimeError(f"Failed Socrata fetch at offset={offset}: {last_err}")

        df_page = pd.read_csv(io.StringIO(resp_text), low_memory=False)
        n_rows = len(df_page)
        print(f"[OK] Socrata page offset={offset}: {n_rows:,} rows", flush=True)
        if n_rows == 0:
            break
        frames.append(df_page)
        if n_rows < page_size:
            break
        offset += page_size

    full_df = pd.concat(frames, ignore_index=True)
    part = dest.with_suffix(".csv.part")
    full_df.to_csv(part, index=False, encoding="utf-8")
    part.replace(dest)
    sha = sha256_file(dest)
    elapsed = round(time.time() - t0, 2)
    print(
        f"[OK] {dest.name}: {len(full_df):,} rows, {len(full_df.columns)} cols in {elapsed}s "
        f"(sha256={sha[:16]}...)",
        flush=True,
    )
    return {
        "url": DOT_SOCRATA_URL,
        "file": dest.name,
        "rows": len(full_df),
        "columns": list(full_df.columns),
        "bytes": dest.stat().st_size,
        "elapsed_sec": elapsed,
        "sha256": sha,
        "cached": False,
    }


def inspect_zip_contents(zip_path: Path) -> dict:
    with zipfile.ZipFile(zip_path) as zf:
        infos = [{"name": zi.filename, "uncompressed_bytes": zi.file_size} for zi in zf.infolist()]
        txt_files = [zi.filename for zi in zf.infolist() if zi.filename.lower().endswith(".txt")]
        sample_cols = 0
        line_count = 0
        if txt_files:
            with zf.open(txt_files[0]) as fh:
                first_line = fh.readline().decode("latin-1", errors="replace").rstrip("\r\n")
                sample_cols = len(first_line.split("\t"))
                line_count = 1 + sum(1 for _ in fh)
        return {"members": infos, "txt_file": txt_files[0] if txt_files else None, "n_lines": line_count, "first_line_tab_cols": sample_cols}


def main() -> None:
    receipts: dict = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": {},
    }

    for fname, url in BULK_FILES.items():
        dest = RAW_DIR / fname
        meta = download_stream(url, dest)
        meta["zip_inspection"] = inspect_zip_contents(dest)
        receipts["sources"][fname] = meta

    socrata_dest = RAW_DIR / "dot_6axg_epim_recalls.csv"
    socrata_meta = download_dot_socrata_full(socrata_dest)
    df_dot = pd.read_csv(socrata_dest, low_memory=False)
    socrata_meta["non_null_completion_rate"] = int(df_dot["completion_rate"].notna().sum()) if "completion_rate" in df_dot.columns else 0
    if "recall_type" in df_dot.columns:
        socrata_meta["recall_type_counts"] = df_dot["recall_type"].value_counts(dropna=False).to_dict()
    receipts["sources"]["dot_6axg_epim_recalls.csv"] = socrata_meta

    receipt_path = RAW_DIR / "raw_download_receipts.json"
    receipt_path.write_text(json.dumps(receipts, indent=2), encoding="utf-8")
    print(f"[DONE] Saved receipts -> {receipt_path}", flush=True)
    print(json.dumps(receipts, indent=2), flush=True)


if __name__ == "__main__":
    main()
