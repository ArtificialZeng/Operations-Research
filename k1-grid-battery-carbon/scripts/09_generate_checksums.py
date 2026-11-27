"""Step 09 (Pillar 8): Generate LF-normalized disk-verified SHA256SUMS.json for all K1 /boost artifacts."""

from __future__ import annotations

import hashlib
from pathlib import Path

from econ_utils import FIG_DIR, RES_DIR, WS_DIR, save_json_lf

TEXT_EXTS = {".py", ".md", ".json", ".txt", ".csv"}


def sha256_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTS:
        norm = raw.replace(b"\r\n", b"\n")
        return hashlib.sha256(norm).hexdigest(), len(norm), "lf_text"
    return hashlib.sha256(raw).hexdigest(), len(raw), "raw_binary"


def main() -> int:
    print("=== STEP 09: GENERATING LF-NORMALIZED SHA256SUMS.json ===", flush=True)
    targets: list[Path] = [
        WS_DIR / "manuscript_k1_boost.md",
        WS_DIR / "manuscript_k1_boost_v3.pdf",
        WS_DIR / "REFEREE_RESPONSE_v2.md",
        WS_DIR / "REFEREE_RESPONSE_v3.md",
    ]
    targets.extend(sorted((WS_DIR / "scripts").glob("*.py")))
    targets.extend(sorted((WS_DIR / "tests").glob("*.py")))
    targets.extend(sorted(RES_DIR.glob("*.json")))
    targets.extend(sorted(FIG_DIR.glob("*.png")))
    targets.extend(sorted(FIG_DIR.glob("*.pdf")))

    entries: dict[str, dict[str, object]] = {}
    for p in targets:
        if not p.exists():
            raise FileNotFoundError(f"Missing expected artifact for checksum: {p}")
        rel = p.relative_to(WS_DIR).as_posix()
        digest, size_bytes, mode = sha256_file(p)
        entries[rel] = {
            "sha256": digest,
            "bytes": size_bytes,
            "mode": mode,
        }

    manifest = {
        "workspace": str(WS_DIR),
        "n_files": len(entries),
        "files": entries,
    }
    out_path = WS_DIR / "SHA256SUMS.json"
    sha_self = save_json_lf(out_path, manifest)
    print(
        f"[DONE STEP 09] Wrote {out_path.name} ({len(entries)} files, SHA-256 LF: {sha_self})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
