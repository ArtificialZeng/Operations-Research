"""Generate cryptographic SHA-256 verification manifest for all D30 /boost deliverables."""
from __future__ import annotations

import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    patterns = [
        "scripts/*.py",
        "tests/*.py",
        "data/raw_ctgov/ctgov_fetch_manifest.json",
        "data/processed/*.parquet",
        "data/processed/*.csv",
        "data/processed/*.json",
        "data/raw_openfda/*.json",
        "results/*.json",
        "tables/*.csv",
        "figures/*.png",
        "figures/*.pdf",
        "manuscript_d30_boost.md",
        "manuscript_d30_boost.pdf",
    ]
    files_map: dict[str, str] = {}
    meta_rows: list[dict] = []
    for pat in patterns:
        for fp in sorted(BASE_DIR.glob(pat)):
            if fp.is_file():
                rel = fp.relative_to(BASE_DIR).as_posix()
                digest = sha256_file(fp)
                files_map[rel] = digest
                meta_rows.append({
                    "file": rel,
                    "bytes": fp.stat().st_size,
                    "sha256": digest,
                })

    manifest = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "project_dir": str(BASE_DIR),
        "n_files": len(files_map),
        "files": files_map,
        "details": meta_rows,
    }
    out_json = BASE_DIR / "SHA256SUMS.json"
    out_json.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    # Also write a human-readable VERIFICATION_MANIFEST.md
    lines = [
        "# D30 `/boost` Cryptographic Verification Manifest",
        "",
        f"- **Generated (UTC):** `{manifest['generated_utc']}`",
        f"- **Verified Artifacts:** `{len(meta_rows)}` files",
        "",
        "| Relative Path | Size (Bytes) | SHA-256 Digest |",
        "| :--- | ---: | :--- |",
    ]
    for r in meta_rows:
        lines.append(f"| `{r['file']}` | {r['bytes']:,} | `{r['sha256']}` |")
    (BASE_DIR / "VERIFICATION_MANIFEST.md").write_text("\n".join(lines) + "\n", encoding="utf-8")

    print(f"[DONE] Wrote SHA256SUMS.json + VERIFICATION_MANIFEST.md ({len(meta_rows)} files verified).", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
