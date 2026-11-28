"""Step 09 (v4 ES&T): Generate LF-normalized disk-verified SHA256SUMS.json for all J6 v4 deliverables."""

from __future__ import annotations

import hashlib
from pathlib import Path

from econ_utils import FIG_DIR, RES_DIR, WS_DIR, save_json_lf

TEXT_EXTS = {".py", ".md", ".json", ".txt", ".csv"}
TABLES_DIR = WS_DIR / "tables"


def sha256_file(path: Path) -> tuple[str, int, str]:
    raw = path.read_bytes()
    if path.suffix.lower() in TEXT_EXTS:
        norm = raw.replace(b"\r\n", b"\n")
        return hashlib.sha256(norm).hexdigest(), len(norm), "lf_text"
    return hashlib.sha256(raw).hexdigest(), len(raw), "raw_binary"


def main() -> int:
    print("=== STEP 09: GENERATING LF-NORMALIZED SHA256SUMS.json (V4 ES&T) ===", flush=True)
    targets: list[Path] = [
        WS_DIR / "manuscript_j6_boost.md",
        WS_DIR / "manuscript_j6_boost.pdf",
        WS_DIR / "supplementary_j6_est.md",
        WS_DIR / "supplementary_j6_est.pdf",
        WS_DIR / "REFEREE_RESPONSE_v4.md",
        WS_DIR / "README.md",
        WS_DIR / "STATUS.md",
    ]
    targets.extend(sorted((WS_DIR / "scripts").glob("*.py")))
    targets.extend(sorted((WS_DIR / "tests").glob("*.py")))
    targets.extend(sorted(RES_DIR.glob("*.json")))
    targets.extend(sorted(TABLES_DIR.glob("*.csv")))
    for stem in (
        "fig1_est_caseflow_and_common_support",
        "fig2_est_official_and_oot_tier_replay",
        "fig3_est_smoke_vs_nonsmoke_and_ground_truth",
        "fig4_est_inference_loro_and_speciation",
        "figS1_si_dv_reclassification_and_rooftop_lottery",
        "figS2_si_oot_reconstruction_and_ee_nulls",
    ):
        targets.append(FIG_DIR / f"{stem}.png")
        targets.append(FIG_DIR / f"{stem}.pdf")

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
        "version": "v4_est_submission",
        "n_files": len(entries),
        "files": entries,
    }
    out_path = WS_DIR / "SHA256SUMS.json"
    sha_self = save_json_lf(out_path, manifest)
    print(f"[DONE STEP 09] Wrote {out_path.name} ({len(entries)} files, SHA-256 LF: {sha_self})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
