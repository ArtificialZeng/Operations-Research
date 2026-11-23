"""Convert the unused Section 6.5 inputs without touching the initial six."""

import argparse
from collections import Counter
from decimal import Decimal
from hashlib import sha256
import json
from pathlib import Path
from zipfile import ZipFile


DESTINATION = Path(__file__).resolve().parent
SOURCE = DESTINATION.parent
ARCHIVE = SOURCE / "fragkos2016_horizon_decomposition.zip"
SOURCE_MANIFEST = SOURCE / "manifest.json"
INITIAL = SOURCE / "instances"
INITIAL_MANIFEST = INITIAL / "conversion_manifest.json"
ARCHIVE_SHA = "0c05853fb22ebe3888c374e724fa679536aede59f964a5c701b046485a1512ec"
SOURCE_MANIFEST_SHA = "e7203e06b1de232aa79e1d2fcda2c7a9f9639664447cc3a6f1337b1178e3ff9c"
INITIAL_MANIFEST_SHA = "4753536432364edad6e4f0bdb7309ef5ae5861398a3a3c8878591fafcf5a8a13"
README_SHA = "fecfdeaabf06f65d5f48c27498db7ae482823cf6c7fcb24bf99fdd157e845562"
SECTION = "Section 6.5 Instances/"
FAMILIES = (("two", 2), ("four", 4), ("six", 6), ("eight", 8), ("ten", 10))
EXCLUDED = ("two1", "two2", "six1", "six2", "ten1", "ten2")


def digest(blob):
    return sha256(blob).hexdigest()


def verified_file(path, expected):
    blob = path.read_bytes()
    if digest(blob) != expected:
        raise ValueError(f"Frozen source hash changed: {path.name}")
    return blob


def numeric_float(value):
    encoded = float(value)
    if Decimal(str(encoded)) != value:
        raise ValueError(f"Cannot preserve exact source decimal {value} in JSON")
    return encoded


def convert_instance(raw, count):
    lines = [line.split() for line in raw.decode("ascii").splitlines() if line.split()]
    products, periods = map(int, lines[0])
    if products != count or periods != 100 or lines[1] != ["1"] or len(lines) != 3 + 2 * products:
        raise ValueError("Unexpected Section 6.5 dimensions or dummy field")
    if len(lines[2]) != periods or any(len(row) != 4 for row in lines[3:3 + products]):
        raise ValueError("Unexpected capacity or product parameter row length")
    capacity = list(map(int, lines[2]))
    demand = [list(map(int, row)) for row in lines[3 + products:]]
    if any(len(row) != periods or min(row) < 0 for row in demand) or min(capacity) < 0:
        raise ValueError("Invalid demand or capacity")
    item_rows = [tuple(map(Decimal, row)) for row in lines[3:3 + products]]
    unit_time, holding, setup_time, setup_cost = zip(*item_rows, strict=True)

    def constant_rows(column):
        return [[numeric_float(value)] * periods for value in column]

    instance = {
        "dimensions": {"num_products": products, "num_periods": periods},
        "parameters": {
            "demand": demand,
            "holding_cost": constant_rows(holding),
            "setup_cost": constant_rows(setup_cost),
            "variable_production_cost": [[0] * periods for _ in range(products)],
            "variable_production_time": constant_rows(unit_time),
            "setup_time": constant_rows(setup_time),
            "capacity": capacity,
            "initial_inventory_cost": [
                numeric_float(sc + hc + 1) for sc, hc in zip(setup_cost, holding, strict=True)
            ],
        },
    }
    return instance


def build():
    verified_file(ARCHIVE, ARCHIVE_SHA)
    source_manifest = json.loads(verified_file(SOURCE_MANIFEST, SOURCE_MANIFEST_SHA))
    initial_manifest = json.loads(verified_file(INITIAL_MANIFEST, INITIAL_MANIFEST_SHA))
    if set(initial_manifest["cases"]) != set(EXCLUDED):
        raise ValueError("Existing six-case scope differs from the fixed exclusion")
    if {path.stem for path in INITIAL.glob("*.json")} != set(EXCLUDED) | {"conversion_manifest"}:
        raise ValueError("Existing six-case input files differ from the fixed exclusion")

    roster = {f"{name}{index}": count for name, count in FAMILIES for index in range(1, 11)}
    manifest_files = source_manifest["files"]
    if set(manifest_files) != {f"{label}.dat" for label in roster}:
        raise ValueError("Source manifest does not enumerate exactly the expected fifty files")
    payloads = {}
    cases = {}
    excluded_records = {}
    with ZipFile(ARCHIVE) as archive:
        members = [name for name in archive.namelist() if name.startswith(SECTION) and name.endswith(".dat")]
        if len(members) != 50 or set(members) != {f"{SECTION}{label}.dat" for label in roster}:
            raise ValueError("Raw archive does not enumerate exactly the expected fifty files")
        if digest(archive.read("README.txt")) != README_SHA:
            raise ValueError("Author README hash changed")
        for label, count in roster.items():
            source_info = manifest_files[f"{label}.dat"]
            name = f"{SECTION}{label}.dat"
            raw = archive.read(name)
            raw_hash = digest(raw)
            if (
                source_info["member"] != name
                or source_info["sha256"] != raw_hash
                or source_info["bytes"] != len(raw)
                or source_info["items_from_filename"] != count
            ):
                raise ValueError(f"Source member does not match its frozen manifest: {name}")
            instance = convert_instance(raw, count)
            payload = (json.dumps(instance, separators=(",", ":"), allow_nan=False) + "\n").encode()
            filename = f"{label}.json"
            output_hash = digest(payload)
            record = {
                "file": filename,
                "sha256": output_hash,
                "bytes": len(payload),
                **instance["dimensions"],
                "source_member": name,
                "source_sha256": raw_hash,
                "source_bytes": len(raw),
                "sum_period_capacity": sum(instance["parameters"]["capacity"]),
                "total_demand": sum(map(sum, instance["parameters"]["demand"])),
                "opening_cost_rule": "setup cost + inventory holding cost + 1",
            }
            if label in EXCLUDED:
                frozen = initial_manifest["cases"][label]
                if frozen["source_sha256"] != raw_hash or frozen["sha256"] != output_hash:
                    raise ValueError(f"Conversion no longer reproduces historical instance {label}")
                if verified_file(INITIAL / filename, frozen["sha256"]) != payload:
                    raise ValueError(f"Existing excluded instance does not round-trip byte-for-byte: {label}")
                excluded_records[label] = record
            else:
                payloads[filename] = payload
                cases[label] = record

    if len(cases) != 44 or set(cases) != set(roster) - set(EXCLUDED):
        raise ValueError("Remaining roster must contain exactly 44 cases")
    manifest = {
        "scope": "All remaining Section 6.5 inputs. Original six excluded and verified byte-for-byte.",
        "source_doi": source_manifest["paper_doi"],
        "source_download": source_manifest["author_download"],
        "source_archive": ARCHIVE.name,
        "source_archive_sha256": ARCHIVE_SHA,
        "source_archive_readme_sha256": README_SHA,
        "source_manifest_sha256": SOURCE_MANIFEST_SHA,
        "excluded_conversion_manifest_sha256": INITIAL_MANIFEST_SHA,
        "converter_sha256": digest(Path(__file__).read_bytes()),
        "license_status": source_manifest["license_status"],
        "source_instances": len(roster),
        "converted_instances": len(cases),
        "converted_counts_by_num_products": dict(sorted(Counter(roster[label] for label in cases).items())),
        "mapping": initial_manifest["mapping"],
        "excluded_cases": excluded_records,
        "cases": cases,
    }
    payloads["conversion_manifest.json"] = (json.dumps(manifest, indent=2, allow_nan=False) + "\n").encode()
    return payloads


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify existing outputs without writing")
    args = parser.parse_args()
    payloads = build()
    expected = set(payloads)
    existing = {path.name for path in DESTINATION.glob("*.json")}
    if args.check:
        if existing != expected:
            raise ValueError("Output directory does not contain exactly the expected JSON files")
        for name, payload in payloads.items():
            if (DESTINATION / name).read_bytes() != payload:
                raise ValueError(f"Converted output drifted: {name}")
    else:
        if existing:
            raise FileExistsError("Refusing to overwrite existing conversion outputs; use --check")
        for name, payload in payloads.items():
            with (DESTINATION / name).open("xb") as output:
                output.write(payload)
    print(f"{'Verified' if args.check else 'Wrote'} {len(payloads) - 1} remaining instances; "
          f"manifest SHA256 {digest(payloads['conversion_manifest.json'])}")


if __name__ == "__main__":
    main()
