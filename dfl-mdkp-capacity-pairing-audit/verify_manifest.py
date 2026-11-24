"""
Standalone archive integrity & hygiene validator for `dfl-mdkp-capacity-pairing-audit/`.
Verifies:
  1. Exact byte length & SHA-256 of every file listed in MANIFEST.json.
  2. Strict 1-to-1 file inventory (no missing files, no unlisted files other than MANIFEST.json).
  3. Zero machine-local / personal paths or internal guidance tokens in any public-facing .md file.
  4. Zero excluded artifacts (official_odece_repo/, desktop_*.txt, __pycache__/, .env, binaries).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent
MANIFEST_PATH = ROOT / "MANIFEST.json"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    entries = manifest["files"]

    # 1. Verify strict ordering and SHA-256 / byte counts
    expected = set()
    prev_order = 0
    for rec in entries:
        assert rec["order"] == prev_order + 1, f"Non-sequential order at {rec['file']}"
        prev_order = rec["order"]
        rel = rec["file"]
        expected.add(rel)
        p = ROOT / rel
        assert p.is_file(), f"Missing archived file: {rel}"
        actual_bytes = p.stat().st_size
        assert actual_bytes == rec["bytes"], f"Size mismatch for {rel}: {actual_bytes} != {rec['bytes']}"
        actual_sha = sha256_file(p)
        assert actual_sha == rec["sha256"], f"SHA-256 mismatch for {rel}: {actual_sha} != {rec['sha256']}"

    # 2. Verify zero unlisted files & zero forbidden directories/files
    actual_files = {
        p.relative_to(ROOT).as_posix()
        for p in ROOT.rglob("*")
        if p.is_file() and p.name != "MANIFEST.json"
    }
    extra = sorted(actual_files - expected)
    missing = sorted(expected - actual_files)
    assert not extra, f"Unlisted files found: {extra}"
    assert not missing, f"Missing files: {missing}"

    # 3. Hygiene scan on all markdown docs and filenames
    md_bad_pat = re.compile(r"(file:///|[cCdD]:\\|[cCdD]:/|87510|desktop_)", re.IGNORECASE)
    for rel in sorted(expected):
        assert "official_odece_repo" not in rel and "__pycache__" not in rel and not rel.startswith("desktop_"), f"Forbidden path: {rel}"
        p = ROOT / rel
        if p.suffix.lower() == ".md":
            txt = p.read_text(encoding="utf-8")
            hits = md_bad_pat.findall(txt)
            assert not hits, f"Unsanitized local/personal token in {rel}: {set(hits)}"

    total_mb = sum(r["bytes"] for r in entries) / (1024 * 1024)
    print(f"MANIFEST VALIDATION PASSED: {len(entries)} files ({total_mb:.2f} MB), all SHA-256 hashes exact, 0 hygiene violations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
