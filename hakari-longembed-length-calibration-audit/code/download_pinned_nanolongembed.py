"""
Downloads ONLY the pinned files necessary for NanoQMSum and NanoNarrativeQA
from hakari-bench/NanoLongEmbed at exact commit ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e,
verifies every LFS file's exact SHA-256 against hf_dataset_tree.json, and saves
DATASET_DOWNLOAD_RECEIPT.json. Keeps corpus text strictly local as inert data.
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess

BASE = pathlib.Path(__file__).resolve().parent.parent
REV = "ec27cccf70e6ac6afef6678b7645f0d2d02d3e1e"
URL_PREFIX = f"https://huggingface.co/datasets/hakari-bench/NanoLongEmbed/resolve/{REV}/"

NEEDED_PATHS = [
    "build_nanolongembed.py",
    "metadata/NanoQMSum.json",
    "metadata/NanoNarrativeQA.json",
    "reranking_hybrid_metadata.json",
    "corpus/NanoQMSum-00000-of-00001.parquet",
    "queries/NanoQMSum-00000-of-00001.parquet",
    "qrels/NanoQMSum-00000-of-00001.parquet",
    "bm25/NanoQMSum-00000-of-00001.parquet",
    "reranking_hybrid/NanoQMSum-00000-of-00001.parquet",
    "corpus/NanoNarrativeQA-00000-of-00001.parquet",
    "queries/NanoNarrativeQA-00000-of-00001.parquet",
    "qrels/NanoNarrativeQA-00000-of-00001.parquet",
    "bm25/NanoNarrativeQA-00000-of-00001.parquet",
    "reranking_hybrid/NanoNarrativeQA-00000-of-00001.parquet",
]


def sha256_file(p: pathlib.Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    tree = json.loads((BASE / "hf_dataset_tree.json").read_text(encoding="utf-8"))
    tree_by_path = {x["path"]: x for x in tree if x.get("type") == "file"}

    receipts = []
    for rel in NEEDED_PATHS:
        assert rel in tree_by_path, f"Missing in pinned HF tree: {rel}"
        info = tree_by_path[rel]
        expected_size = info["size"]
        expected_lfs_sha = info.get("lfs", {}).get("oid")

        dest = BASE / "data" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        url = URL_PREFIX + rel

        if not (dest.exists() and dest.stat().st_size == expected_size):
            cmd = ["curl.exe", "-fSL", "--retry", "2", "--max-time", "180", url, "-o", str(dest)]
            res = subprocess.run(cmd, capture_output=True, text=True)
            assert res.returncode == 0, f"Download failed for {rel}: {res.stderr}"

        obs_size = dest.stat().st_size
        obs_sha = sha256_file(dest)
        assert obs_size == expected_size, f"Size mismatch on {rel}: expected {expected_size}, got {obs_size}"
        if expected_lfs_sha:
            assert obs_sha == expected_lfs_sha, f"LFS SHA-256 mismatch on {rel}: expected {expected_lfs_sha}, got {obs_sha}"

        receipts.append({
            "path": rel,
            "url": url,
            "bytes": obs_size,
            "sha256": obs_sha,
            "verified_against_hf_lfs_oid": bool(expected_lfs_sha),
        })
        print(f"  OK {rel:52s} | {obs_size:10,d} B | sha256={obs_sha[:16]}...", flush=True)

    rec = {
        "dataset_id": "hakari-bench/NanoLongEmbed",
        "pinned_revision": REV,
        "tasks_downloaded": ["NanoQMSum", "NanoNarrativeQA"],
        "terms_note": "Derived dataset from dwzhu/LongEmbed; corpus text kept strictly local as inert data and never republished.",
        "files": receipts,
    }
    out_p = BASE / "DATASET_DOWNLOAD_RECEIPT.json"
    out_p.write_text(json.dumps(rec, indent=2) + "\n", encoding="utf-8")
    print(f"ALL {len(receipts)} PINNED FILES DOWNLOADED & VERIFIED -> {out_p}")


if __name__ == "__main__":
    main()
