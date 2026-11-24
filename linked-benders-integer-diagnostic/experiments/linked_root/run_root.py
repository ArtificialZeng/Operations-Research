"""Execute one sealed full-scenario root relaxation and certify its interval."""

from time import perf_counter

START = perf_counter()

import argparse
from fractions import Fraction
from hashlib import sha256
from importlib.metadata import version
import json
import os
from pathlib import Path
import sys

import numpy as np

from certify import certify
from root_model import formulate


HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "diaz_lost_sales"
OUT = HERE / "runs_45s"
LOCK = OUT / "lock.json"
SECONDS = 45
MODES = ("plain", "linked", "linked_separated")
PLAN = {"p01": (18, MODES), "p26": (22, ("linked_separated", "plain", "linked")),
        "p50": (26, ("linked", "linked_separated", "plain"))}
MANIFEST_SHA256 = "9be4fb7962061b5b5a42fc2ff5f67add0788f7e199bc7b577e9c7779aaeeb126"
sys.path.insert(0, str(HERE.parent / "bodur_holmberg_transfer"))
from independent import Instance


def digest(bytestring):
    return sha256(bytestring).hexdigest()


def write_new(path, record):
    with path.open("x", encoding="utf-8") as file:
        json.dump(record, file, indent=2, allow_nan=False)
        file.write("\n")


def load_case(case):
    manifest = (DATA / "manifest.json").read_bytes()
    if digest(manifest) != MANIFEST_SHA256:
        raise ValueError("Díaz manifest differs from the earlier sealed source")
    profile = json.loads(manifest)["cases"][case]
    payload = (DATA / profile["file"]).read_bytes()
    if digest(payload) != profile["instance_sha256"]:
        raise ValueError("Díaz case differs from its source hash")
    item = json.loads(payload)
    demands = np.asarray(item["scenario_demands"], dtype=np.int64)
    prices = np.asarray(item["shipping_cost_numerators"], dtype=object)
    data = Instance(case, profile["instance_sha256"], tuple(item["capacities"]), tuple(map(Fraction, item["opening_costs"])),
                    prices, item["cost_scale"], demands, tuple(map(int, demands.sum(axis=0))), item["units"],
                    item["peak"], item["scenario_count"])
    if list((*prices[:-1].shape, len(demands))) != profile["dimensions"] or item["dummy"] != len(data.capacities) - 1:
        raise ValueError("Díaz case has unexpected dimensions")
    return data, profile


def seal():
    cases = {}
    for case, (cpu, order) in PLAN.items():
        _, profile = load_case(case)
        cases[case] = {"cpu": cpu, "order": order, "profile": profile}
    filenames = ("run_root.py", "root_model.py", "certify.py", "PROTOCOL.md", "../bodur_holmberg_transfer/independent.py")
    OUT.mkdir(exist_ok=True)
    write_new(LOCK, {"cases": cases, "seconds": SECONDS, "input_manifest_sha256": MANIFEST_SHA256,
                     "runtime": {package: version(package) for package in ("numpy", "scipy")},
                     "source_sha256": {filename: digest((HERE / filename).read_bytes()) for filename in filenames}})
    print(digest(LOCK.read_bytes()))


def run(case, mode, expected):
    path = OUT / f"{case}_{mode}.json"
    if path.exists():
        raise FileExistsError(path)
    allowed = {LOCK, DATA / "manifest.json", DATA / f"{case}.json"}

    def guard(event, args):
        if event != "open":
            return
        filename, _, flags = args
        if isinstance(filename, (str, bytes)) and flags & os.O_ACCMODE != os.O_WRONLY:
            resolved = Path(os.path.abspath(os.fsdecode(filename)))
            if resolved.suffix.lower() == ".json" and HERE.parent in resolved.parents and resolved not in allowed:
                raise PermissionError(f"Unregistered input: {resolved}")

    sys.addaudithook(guard)
    raw = LOCK.read_bytes()
    lock = json.loads(raw)
    plan = lock["cases"][case]
    if digest(raw) != expected or lock["seconds"] != SECONDS or os.sched_getaffinity(0) != {plan["cpu"]}:
        raise ValueError("CPU assignment or clock differs from the sealed comparison")
    for package, pinned in lock["runtime"].items():
        if version(package) != pinned:
            raise ValueError(f"Runtime changed for {package}")
    for filename, pinned in lock["source_sha256"].items():
        if digest((HERE / filename).read_bytes()) != pinned:
            raise ValueError(f"Source changed for {filename}")
    data, profile = load_case(case)
    if plan["profile"] != profile:
        raise ValueError("Input profile differs from the lock")
    model = formulate(data, mode)
    remaining = max(0.01, START + SECONDS - perf_counter() - 4.5)
    solved = model.optimize(remaining)
    numerical = {"status": int(solved.status), "message": solved.message,
                 "iterations": None if solved.nit is None else int(solved.nit),
                 "objective": None if solved.fun is None or not np.isfinite(solved.fun) else float(solved.fun),
                 "seconds_before_certificate": perf_counter() - START}
    certificate = None
    if solved.status == 0:
        opening, shipping, demand, capacity, shortage = model.split(solved)
        certificate = certify(data, opening, shipping, demand, capacity, linked=mode != "plain",
                              shortage_marginals=shortage, eta=model.eta)
    charged = perf_counter() - START
    record = {"case": case, "mode": mode, "lock_sha256": expected, "cpu": plan["cpu"],
              "input_sha256": profile["instance_sha256"], "eta_ticks": model.eta,
              "variables": len(model.objective), "equations": model.demand_rows.shape[0],
              "inequalities": model.inequality_rows.shape[0], "numeric": numerical, "certificate": certificate,
              "elapsed_seconds": charged, "within_budget": charged <= SECONDS}
    write_new(path, record)
    print(case, mode, numerical["status"], f"{charged:.3f}s", "bounded" if certificate else "no full certificate")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("seal", *MODES))
    parser.add_argument("--case", choices=PLAN)
    parser.add_argument("--lock-sha")
    args = parser.parse_args()
    if args.mode == "seal":
        seal()
        return
    if not args.case or not args.lock_sha:
        parser.error("A worker requires --case and --lock-sha")
    run(args.case, args.mode, args.lock_sha)


if __name__ == "__main__":
    main()
