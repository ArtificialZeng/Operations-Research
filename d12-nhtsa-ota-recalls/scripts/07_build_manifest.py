"""Step 7: Generate SHA256SUMS.json and VERIFICATION_MANIFEST.md for all project artifacts (v4)."""
from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> None:
    targets: list[Path] = []
    for sub in ("scripts", "results", "tables", "figures", "tests"):
        d = BASE_DIR / sub
        if d.exists():
            targets.extend(sorted(p for p in d.rglob("*") if p.is_file() and "__pycache__" not in str(p)))

    proc_dir = BASE_DIR / "data_processed"
    if proc_dir.exists():
        targets.extend(sorted(p for p in proc_dir.glob("*") if p.is_file()))

    for raw_name in ("raw_download_receipts.json", "nhtsa_annual_eighth_report_2024_2025.csv", "dot_79374_DS1.pdf"):
        raw_p = BASE_DIR / "data_raw" / raw_name
        if raw_p.exists():
            targets.append(raw_p)

    for root_f in (
        "manuscript_d12_boost.md",
        "manuscript_d12_boost.pdf",
        "supplementary_d12_jsr.md",
        "supplementary_d12_jsr.pdf",
        "REFEREE_RESPONSE_v2.md",
        "REFEREE_RESPONSE_v4.md",
        "README.md",
        "STATUS.md",
    ):
        p = BASE_DIR / root_f
        if p.exists():
            targets.append(p)

    manifest = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "project": "d12_boost_nhtsa_ota_recalls_20261125",
        "revision": "v4",
        "n_files_hashed": len(set(targets)),
        "files": {},
    }
    for p in sorted(set(targets)):
        rel = p.relative_to(BASE_DIR).as_posix()
        manifest["files"][rel] = {
            "bytes": p.stat().st_size,
            "sha256": sha256_file(p),
        }

    sha_path = BASE_DIR / "SHA256SUMS.json"
    sha_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    lines = [
        "# Verification Manifest — Vehicle Recall Completion at a Fixed Reporting Horizon (v4)",
        "",
        f"- **Generated (UTC):** `{manifest['generated_utc']}`",
        f"- **Hashed Artifacts:** `{manifest['n_files_hashed']}`",
        "- **Integrity File:** `SHA256SUMS.json`",
        "",
        "## Core Data, Results, Tables, Figures, Manuscripts & Verification Checksums",
        "",
        "| Artifact | Size (bytes) | SHA-256 (prefix 16) |",
        "|---|---:|---|",
    ]
    for rel, info in manifest["files"].items():
        lines.append(f"| `{rel}` | {info['bytes']:,} | `{info['sha256'][:16]}...` |")
    lines.append("")
    (BASE_DIR / "VERIFICATION_MANIFEST.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"[DONE] Hashed {manifest['n_files_hashed']} files -> {sha_path}", flush=True)


if __name__ == "__main__":
    main()
