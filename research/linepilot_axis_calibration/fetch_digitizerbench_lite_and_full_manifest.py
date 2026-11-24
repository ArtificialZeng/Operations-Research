"""
1. Download pinned `lite.zip` (17,094,028 B) from `LinePilot/DigitizerBench` commit
   `8b4a3190d5991414dad92049671de75754dd9f44`, verify exact HF LFS SHA-256, and inspect its schema.
2. Read ONLY the remote ZIP Central Directory + `full/manifest.parquet` + `full/factor_levels.json`
   from `full.zip` (749,958,209 B) via HTTP Range requests (206 Partial Content) WITHOUT downloading
   any untouched Full images!
"""
from __future__ import annotations

import hashlib
import io
import json
import struct
import urllib.request
import zipfile
from pathlib import Path

PROJ = Path(r"D:\AI_Science\antigravity\linepilot_axis_calibration_stage0_20261124")
DATA_DIR = PROJ / "data_digitizerbench"
DATA_DIR.mkdir(parents=True, exist_ok=True)

DS_REV = "8b4a3190d5991414dad92049671de75754dd9f44"
LITE_URL = f"https://huggingface.co/datasets/LinePilot/DigitizerBench/resolve/{DS_REV}/lite.zip"
LITE_SHA = "2127fde88c7a1f9475f782c8e610a25c32df05c82fcdc39c5f2d199222e698ab"
FULL_URL = f"https://huggingface.co/datasets/LinePilot/DigitizerBench/resolve/{DS_REV}/full.zip"
FULL_SIZE = 749958209


class HTTPRangeFile(io.RawIOBase):
    """Read-only seekable file-like object backed by HTTP Range requests."""

    def __init__(self, url: str, size: int):
        self.url = url
        self.size = size
        self.pos = 0
        self.bytes_fetched = 0
        self.requests_made = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.size + offset
        self.pos = max(0, min(self.size, self.pos))
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.size:
            return b""
        if n is None or n < 0:
            end = self.size - 1
        else:
            end = min(self.size - 1, self.pos + n - 1)
        if end < self.pos:
            return b""
        req = urllib.request.Request(
            self.url,
            headers={
                "Range": f"bytes={self.pos}-{end}",
                "User-Agent": "linepilot-stage0/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            chunk = resp.read()
        self.pos += len(chunk)
        self.bytes_fetched += len(chunk)
        self.requests_made += 1
        return chunk


def main() -> None:
    # 1. Download & verify lite.zip for smoke tests
    lite_zip = DATA_DIR / "lite.zip"
    if not lite_zip.exists():
        req = urllib.request.Request(LITE_URL, headers={"User-Agent": "linepilot-stage0/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        lite_zip.write_bytes(data)
    got_sha = hashlib.sha256(lite_zip.read_bytes()).hexdigest()
    assert got_sha == LITE_SHA, f"lite.zip SHA mismatch: {got_sha} != {LITE_SHA}"
    print(f"Verified lite.zip ({lite_zip.stat().st_size} B, SHA-256={got_sha})")

    lite_dir = DATA_DIR / "lite_extracted"
    if not lite_dir.exists():
        with zipfile.ZipFile(lite_zip, "r") as zf:
            zf.extractall(lite_dir)
    print("lite.zip top entries:", sorted(p.name for p in (lite_dir / "lite").iterdir()))

    # 2. Fetch ONLY metadata files from full.zip via HTTP Range (never downloading held-out Full PNGs!)
    rf = HTTPRangeFile(FULL_URL, FULL_SIZE)
    full_meta_dir = DATA_DIR / "full_metadata_only"
    full_meta_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(rf, "r") as zf:
        names = zf.namelist()
        non_imgs = [n for n in names if not n.lower().endswith((".png", ".jpg", ".jpeg")) and not n.endswith("/")]
        print(f"full.zip total entries={len(names)}, non-image files={non_imgs}")
        for target in ["full/manifest.parquet", "full/factor_levels.json"]:
            if target in names:
                raw = zf.read(target)
                dest = full_meta_dir / Path(target).name
                dest.write_bytes(raw)
                print(f"  Extracted {target} ({len(raw)} B, SHA-256={hashlib.sha256(raw).hexdigest()})")
        for n in non_imgs:
            if n.startswith("full/design/"):
                raw = zf.read(n)
                dest = full_meta_dir / "design" / Path(n).name
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(raw)
                print(f"  Extracted {n} ({len(raw)} B)")
    print(f"HTTP Range bytes fetched from 750 MB full.zip: {rf.bytes_fetched:,} B across {rf.requests_made} requests")


if __name__ == "__main__":
    main()
