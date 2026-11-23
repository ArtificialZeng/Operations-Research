"""Checksum-verified reconstruction of adapted Diaz JSON inputs for clean-clone replay.

Reconstructs `experiments/diaz_lost_sales/{p01,p26,p50}.json` from the pinned
public raw files in MCDMSociety/MOrepo-Gadegaard16 (commit 5d5a64e1f9e43a2484de52dacc9148a81df5d30d)
using the frozen `experiments/diaz_lost_sales/manifest.json` and
`experiments/diaz_lost_sales/seal_inputs.py` adapter, without republishing raw
matrix bytes in the archive repository and without touching unrelated experiment
directories.
"""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

EXPECTED_MANIFEST_SHA256 = "9be4fb7962061b5b5a42fc2ff5f67add0788f7e199bc7b577e9c7779aaeeb126"
EXPECTED_ADAPTER_SHA256 = "0d11f6b2c08d406f145647b6303fc0fa81c3701ed53ab658e98ea23216704ca3"
DEFAULT_CASES = ("p01", "p26", "p50")


def _locate_archive_root() -> Path:
    here = Path(__file__).resolve().parent
    for candidate in (here, here.parent.parent):
        if (candidate / "experiments" / "diaz_lost_sales" / "manifest.json").exists():
            return candidate
    raise FileNotFoundError(
        "Could not locate experiments/diaz_lost_sales/manifest.json relative to prepare_archive_inputs.py"
    )


def _sha256_bytes(raw: bytes) -> str:
    return sha256(raw).hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases",
        nargs="+",
        choices=DEFAULT_CASES,
        default=list(DEFAULT_CASES),
        help="Diaz cases to reconstruct or verify (default: p01 p26 p50).",
    )
    parser.add_argument(
        "--raw-dir",
        type=Path,
        default=None,
        help="Optional local directory containing previously downloaded Gadegaard16_SSCFLP_Diaz_*_0.raw files.",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Only verify checksums of existing reconstructed JSON files; do not download or write.",
    )
    args = parser.parse_args()

    root = _locate_archive_root()
    diaz_dir = root / "experiments" / "diaz_lost_sales"
    manifest_path = diaz_dir / "manifest.json"
    adapter_path = diaz_dir / "seal_inputs.py"

    manifest_bytes = manifest_path.read_bytes()
    if _sha256_bytes(manifest_bytes) != EXPECTED_MANIFEST_SHA256:
        raise ValueError(f"Pinned manifest SHA-256 mismatch at {manifest_path}")
    if _sha256_bytes(adapter_path.read_bytes()) != EXPECTED_ADAPTER_SHA256:
        raise ValueError(f"Pinned adapter SHA-256 mismatch at {adapter_path}")

    manifest = json.loads(manifest_bytes.decode("utf-8"))

    if str(diaz_dir) not in sys.path:
        sys.path.insert(0, str(diaz_dir))
    import seal_inputs  # noqa: E402

    summary = {}
    for case in args.cases:
        profile = manifest["cases"][case]
        out_path = diaz_dir / profile["file"]
        expected_sha = profile["instance_sha256"]

        if out_path.exists():
            actual_sha = _sha256_bytes(out_path.read_bytes())
            if actual_sha == expected_sha:
                summary[case] = {"status": "verified_existing", "path": str(out_path), "instance_sha256": actual_sha}
                continue
            raise ValueError(
                f"Refusing to overwrite existing checksum-mismatched target {out_path}: "
                f"expected {expected_sha}, got {actual_sha}"
            )

        if args.verify_only:
            raise FileNotFoundError(f"Missing reconstructed input for --verify-only: {out_path}")

        if args.raw_dir is not None:
            raw_path = args.raw_dir / profile["raw_file"]
            raw_bytes = raw_path.read_bytes()
        else:
            _, _, _, raw_bytes = seal_inputs.raw_source(case)

        if len(raw_bytes) != int(profile["raw_bytes"]) or _sha256_bytes(raw_bytes) != profile["raw_sha256"]:
            raise ValueError(f"Raw source checksum or byte length mismatch for {case}")

        instance, computed_profile = seal_inputs.adapt(case, raw_bytes)
        encoded = seal_inputs.encode(instance)
        reconstructed_sha = _sha256_bytes(encoded)
        if reconstructed_sha != expected_sha:
            raise ValueError(
                f"Reconstructed {case}.json SHA-256 mismatch: expected {expected_sha}, got {reconstructed_sha}"
            )
        for key, expected_val in computed_profile.items():
            if profile.get(key) != expected_val:
                raise ValueError(f"Reconstructed profile mismatch on {case}.{key}")

        out_path.write_bytes(encoded)
        summary[case] = {
            "status": "reconstructed_and_verified",
            "path": str(out_path),
            "raw_sha256": profile["raw_sha256"],
            "instance_sha256": reconstructed_sha,
        }

    print(json.dumps({"archive_root": str(root), "cases": summary}, indent=2))


if __name__ == "__main__":
    main()
