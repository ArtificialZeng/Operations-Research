"""
Workspace-only portable Tesseract 5.5.3 provisioning (ZERO global install, ZERO UAC, ZERO registry writes):
  1. Downloads official `RayanA07/LinePilot` release `v2.17.1` `Digitizer.exe` (Apache-2.0, built from
     pinned commit `8fb89a62fb0565290b72ba61cb073d732d8e7578`).
  2. Extracts ONLY `vendor/tesseract/*` from its PyInstaller CArchive purely via Python
     (`PyInstaller.archive.readers.CArchiveReader`) directly into
     `upstream_linepilot/Digitizer/vendor/tesseract/`.
  3. Verifies exact pinned version (`5.5.3`), required features (`libarchive`, `libcurl`),
     `eng`/`osd` language listing, and exact SHA-256 checksums of `eng.traineddata` and
     `osd.traineddata` against `upstream_linepilot/Digitizer/tesseract-lock.json`.
  4. Persists `PORTABLE_OCR_RECEIPT.json` and removes the temporary `Digitizer.exe` download.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from pathlib import Path

from PyInstaller.archive.readers import CArchiveReader

PROJ = Path(r"D:\AI_Science\antigravity\linepilot_axis_calibration_stage0_20261124")
DIGITIZER_DIR = PROJ / "upstream_linepilot" / "Digitizer"
VENDOR_DIR = DIGITIZER_DIR / "vendor" / "tesseract"
TMP_EXE = PROJ / "_tmp_Digitizer_v2.17.1.exe"
RELEASE_URL = "https://github.com/RayanA07/LinePilot/releases/download/v2.17.1/Digitizer.exe"


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    lock = json.loads((DIGITIZER_DIR / "tesseract-lock.json").read_text(encoding="utf-8"))
    expected_ver = lock["version"]

    if not TMP_EXE.exists():
        print(f"Downloading official LinePilot v2.17.1 Digitizer.exe from {RELEASE_URL} ...", flush=True)
        subprocess.run(
            ["curl.exe", "-fL", "--retry", "3", "--connect-timeout", "30", "-o", str(TMP_EXE), RELEASE_URL],
            check=True,
        )
    exe_size = TMP_EXE.stat().st_size
    exe_sha = sha256_file(TMP_EXE)
    print(f"Downloaded Digitizer.exe: {exe_size:,} B, SHA-256={exe_sha}", flush=True)

    # Extract ONLY vendor/tesseract/* purely in Python (never executing Digitizer.exe!)
    reader = CArchiveReader(str(TMP_EXE))
    extracted_files = []
    for name in reader.toc:
        norm = name.replace("\\", "/")
        if norm.startswith("vendor/tesseract/"):
            rel = norm[len("vendor/tesseract/"):]
            if not rel or rel.endswith("/"):
                continue
            dest = VENDOR_DIR / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            data = reader.extract(name)
            dest.write_bytes(data)
            extracted_files.append({
                "rel_path": rel,
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            })

    assert extracted_files, "No vendor/tesseract/* entries found in Digitizer.exe CArchive!"
    tess_exe = VENDOR_DIR / "tesseract.exe"
    assert tess_exe.is_file(), f"tesseract.exe missing at {tess_exe}"

    # Verify tessdata checksums against tesseract-lock.json
    for model_name, meta in lock["tessdata"].items():
        mp = VENDOR_DIR / "tessdata" / model_name
        assert mp.is_file(), f"Missing {mp}"
        got = sha256_file(mp)
        assert got == meta["sha256"], f"Checksum mismatch for {model_name}: {got} != {meta['sha256']}"

    # Execute vendored tesseract.exe --version and --list-langs with workspace-only TESSDATA_PREFIX
    env = os.environ.copy()
    env["TESSDATA_PREFIX"] = str(VENDOR_DIR / "tessdata")
    ver_out = subprocess.check_output([str(tess_exe), "--version"], env=env, text=True, stderr=subprocess.STDOUT)
    langs_out = subprocess.check_output([str(tess_exe), "--list-langs"], env=env, text=True, stderr=subprocess.STDOUT)

    first_line = ver_out.splitlines()[0].strip()
    assert expected_ver in first_line, f"Expected Tesseract {expected_ver}, got: {first_line}"
    for feat in lock["required_features"]:
        assert f"Found {feat}" in ver_out, f"Missing required feature {feat}"
    for lang in ("eng", "osd"):
        assert any(line.strip() == lang for line in langs_out.splitlines()), f"Missing lang {lang}"

    # Clean up temporary Digitizer.exe once extraction & verification succeed
    TMP_EXE.unlink(missing_ok=True)

    receipt = {
        "route": "Official workspace-only portable extraction of vendor/tesseract/* from RayanA07/LinePilot v2.17.1 release Digitizer.exe via PyInstaller CArchiveReader (zero global install, zero registry edits, zero UAC).",
        "source_release_url": RELEASE_URL,
        "source_digitizer_exe_bytes": exe_size,
        "source_digitizer_exe_sha256": exe_sha,
        "tesseract_version_line": first_line,
        "tesseract_version_full": ver_out.strip(),
        "tesseract_langs": [l.strip() for l in langs_out.splitlines() if l.strip()],
        "tesseract_exe_sha256": sha256_file(tess_exe),
        "eng_traineddata_sha256_verified": True,
        "osd_traineddata_sha256_verified": True,
        "extracted_file_count": len(extracted_files),
        "dll_count": sum(1 for f in extracted_files if f["rel_path"].lower().endswith(".dll")),
        "extracted_files": sorted(extracted_files, key=lambda x: x["rel_path"]),
    }
    (PROJ / "PORTABLE_OCR_RECEIPT.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"SUCCESS: Vendored {first_line} ({receipt['dll_count']} DLLs, {receipt['extracted_file_count']} files) at {VENDOR_DIR}")


if __name__ == "__main__":
    main()
