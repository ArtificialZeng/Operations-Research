"""Pillar 9 (v4): Generate LF-normalized disk-verified SHA256SUMS.json manifest for all deliverables."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

WORK_DIR = Path(__file__).resolve().parents[1]
OUT_PATH = WORK_DIR / "SHA256SUMS.json"

TEXT_EXTS = {".py", ".md", ".json", ".csv", ".txt", ".toml", ".yml", ".yaml"}


def sha256_disk(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest().upper()


def ensure_lf_if_text(path: Path) -> None:
    if path.suffix.lower() in TEXT_EXTS:
        raw = path.read_bytes()
        if b"\r\n" in raw:
            path.write_bytes(raw.replace(b"\r\n", b"\n"))


def main() -> int:
    targets: list[Path] = []
    for rel_dir in ("scripts", "tests", "tables", "results", "figures"):
        d = WORK_DIR / rel_dir
        if d.exists():
            for p in sorted(d.rglob("*")):
                if p.is_file() and "__pycache__" not in p.parts:
                    targets.append(p)
    for top_fn in (
        "manuscript_i4_boost.md",
        "manuscript_i4_boost.pdf",
        "supplementary_i4_jbf.md",
        "supplementary_i4_jbf.pdf",
        "REFEREE_RESPONSE_v4.md",
        "REFEREE_RESPONSE_v2.md",
        "README.md",
        "STATUS.md",
    ):
        p = WORK_DIR / top_fn
        if p.exists():
            targets.append(p)
    edgar_audit = WORK_DIR / "data" / "edgar_prospectus_audit.json"
    if edgar_audit.exists():
        targets.append(edgar_audit)

    entries = {}
    for p in targets:
        ensure_lf_if_text(p)
        rel = p.relative_to(WORK_DIR).as_posix()
        entries[rel] = {
            "bytes": p.stat().st_size,
            "sha256": sha256_disk(p),
        }

    manifest = {
        "workspace": str(WORK_DIR),
        "revision": "v4",
        "n_files": len(entries),
        "line_endings_policy": "LF-normalized for all text files; raw disk bytes hashed",
        "files": entries,
    }
    OUT_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"[DONE STEP 9 v4] Wrote {OUT_PATH} covering {len(entries)} artifacts.", flush=True)
    for k in (
        "manuscript_i4_boost.pdf",
        "manuscript_i4_boost.md",
        "supplementary_i4_jbf.pdf",
        "supplementary_i4_jbf.md",
        "REFEREE_RESPONSE_v4.md",
        "results/02b_per_fund_statutory_audit.json",
        "results/03_holdings_lookthrough.json",
        "results/04b_counterfactual_sensitivity.json",
        "results/07_verified_references_crossref.json",
        "results/10_v4_manuscript_receipt.json",
    ):
        if k in entries:
            print(f"  {k:46s} | {entries[k]['bytes']:10,d} B | {entries[k]['sha256']}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
