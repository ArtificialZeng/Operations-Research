"""Convert the pinned public Fragkos archive into the 44 benchmark instances."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile

from historical.convert import convert_instance


HERE = Path(__file__).resolve().parent
LOCK_HASH = "b263139c1a2a92cd9fad5a12a39f41dfbd229229433eccb356ee6246f3d5b949"


def convert(archive_path):
    lock_bytes = (HERE / "provenance/conversion_manifest.json").read_bytes()
    if sha256(lock_bytes).hexdigest() != LOCK_HASH:
        raise ValueError("The frozen conversion manifest has changed")
    locked = json.loads(lock_bytes)
    if sha256(archive_path.read_bytes()).hexdigest() != locked["source_archive_sha256"]:
        raise ValueError("The archive differs from the frozen public download")
    cases = locked["cases"]
    all_cases = {**cases, **locked["excluded_cases"]}
    converted = {}
    with ZipFile(archive_path) as archive:
        if sha256(archive.read("README.txt")).hexdigest() != locked["source_archive_readme_sha256"]:
            raise ValueError("The author README has changed")
        members = [name for name in archive.namelist()
                   if name.startswith("Section 6.5 Instances/") and name.endswith(".dat")]
        if len(members) != 50 or set(members) != {item["source_member"] for item in all_cases.values()}:
            raise ValueError("The archive has a different Section 6.5 roster")
        for label, item in all_cases.items():
            raw = archive.read(item["source_member"])
            if sha256(raw).hexdigest() != item["source_sha256"]:
                raise ValueError(f"Raw bytes differ for {label}")
            instance = convert_instance(raw, item["num_products"])
            payload = (json.dumps(instance, separators=(",", ":"), allow_nan=False) + "\n").encode()
            if sha256(payload).hexdigest() != item["sha256"]:
                raise ValueError(f"Converted bytes differ for {label}")
            if label in cases:
                converted[item["file"]] = payload
    return converted


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--check", action="store_true", help="Verify an existing conversion without writing")
    args = parser.parse_args()
    instances = convert(args.archive)
    if args.check:
        actual = {path.name for path in args.output_dir.glob("*.json")}
        if actual != set(instances):
            raise ValueError("The output directory has a different instance roster")
        for name, content in instances.items():
            if (args.output_dir / name).read_bytes() != content:
                raise ValueError(f"Existing converted bytes differ for {name}")
    else:
        args.output_dir.mkdir(parents=True, exist_ok=True)
        if any((args.output_dir / name).exists() for name in instances):
            raise FileExistsError("Output instances already exist. Use --check or a new directory.")
        for name, content in instances.items():
            (args.output_dir / name).write_bytes(content)
    print(f"{'Verified' if args.check else 'Wrote'} {len(instances)} exact converted instances")


if __name__ == "__main__":
    main()
