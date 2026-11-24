"""Download and seal exact Díaz adaptations without invoking a solver."""

from concurrent.futures import ThreadPoolExecutor
from fractions import Fraction
from hashlib import sha256
from math import ceil, gcd, lcm
import json
from pathlib import Path
from urllib.request import Request, urlopen


HERE = Path(__file__).resolve().parent
REPO = "MCDMSociety/MOrepo-Gadegaard16"
COMMIT = "5d5a64e1f9e43a2484de52dacc9148a81df5d30d"
SOURCE = f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/instances/raw/SSCFLP/"
RAW = {
    "p01": (10, 20, "9ce4bf0cdf7f9eec5fa28ba52d6ef905fef20beaae71a9e588fbe9156e321d6e"),
    "p26": (20, 50, "2a4681f0f23ff40e9ed8c80d6af9b99eb78b5b09c9211c29ac3363a275c1ba3c"),
    "p50": (30, 90, "ce29c3e32f4fb5815b8c3d1ea5a870bd6f483cf9a5efae5289bd89211d45fa41"),
}


def sha(raw):
    return sha256(raw).hexdigest()


def encode(record):
    return (json.dumps(record, separators=(",", ":"), allow_nan=False) + "\n").encode("ascii")


def raw_source(case):
    name = f"Gadegaard16_SSCFLP_Diaz_{case}_0.raw"
    url = SOURCE + name
    with urlopen(Request(url, headers={"User-Agent": "Diaz-research-replay"}), timeout=15) as response:
        raw = response.read(100_001)
    if len(raw) > 100_000 or sha(raw) != RAW[case][2]:
        raise ValueError(f"Pinned raw bytes changed for {case}")
    return case, name, url, raw


def sign(case, pair, label):
    key = f"diaz-lost-sales-v1/{case}/{pair}/{label}".encode("ascii")
    return 1 if sha256(key).digest()[0] & 1 else -1


def adapt(case, raw):
    values = tuple(map(int, raw.split()))
    n, m = values[:2]
    if (n, m) != RAW[case][:2] or len(values) != 2 + 2 * n + m + 2 * n * m:
        raise ValueError("Source dimensions or token count changed")
    cap = values[2:2 + 2 * n:2]
    fixed = values[3:2 + 2 * n:2]
    nominal = values[2 + 2 * n:2 + 2 * n + m]
    cost_start = 2 + 2 * n + m
    assignment = tuple(values[cost_start + i * m:cost_start + (i + 1) * m] for i in range(n))
    if min(cap) <= 0 or min(fixed) <= 0 or min(nominal) <= 0 or min(map(min, assignment)) < 0:
        raise ValueError("Unexpected source cost, capacity or demand sign")
    rates = tuple(tuple(Fraction(v, d) for v, d in zip(row, nominal, strict=True)) for row in assignment)
    rho = max(map(max, rates)) + 2 * max(Fraction(f, u) for f, u in zip(fixed, cap, strict=True))
    cost_scale = lcm(rho.denominator, *(v.denominator for row in rates for v in row))
    scenario = []
    for pair in range(100):
        common = 2 * sign(case, pair, "common")
        local = tuple(sign(case, pair, f"customer-{j}") for j in range(m))
        for direction in (1, -1):
            scenario.append(tuple(d * (10 + direction * (common + noise)) for d, noise in zip(nominal, local, strict=True)))
    if len(scenario) != 200 or any(sum(col) != 2000 * d for d, col in zip(nominal, zip(*scenario, strict=True), strict=True)):
        raise ValueError("Scenario count or exact empirical means disagree")
    peak = max(map(sum, scenario))
    dummy = ceil(Fraction(peak, 10))
    quantity_gcd = gcd(10, *(v for row in scenario for v in row))
    units = 10 // quantity_gcd
    ticks = tuple(tuple(v // quantity_gcd for v in row) for row in scenario)
    demand_scale = lcm(*(Fraction(v, 10).denominator for row in scenario for v in row))
    if units != demand_scale:
        raise ArithmeticError("Unexpected exact quantity reduction")
    reachable = 1
    lattice = gcd(*cap)
    for u in cap:
        reachable |= reachable << (u // lattice)
    data = {"case": case, "dummy": n, "units": units, "cost_scale": cost_scale, "scenario_count": 200,
            "facilities": n, "customers": m, "capacities": [*(v * units for v in cap), dummy * units],
            "opening_costs": [*fixed, 0], "original_nominal_demand": nominal, "original_assignment_costs": assignment,
            "shipping_cost_numerators": [[int(v * cost_scale) for v in row] for row in (*rates, (rho,) * m)],
            "scenario_demands": ticks, "peak": peak // quantity_gcd, "uniform_penalty_exact": str(rho)}
    profile = {"dimensions": [n, m, 200], "nominal_total": sum(nominal), "all_open_real_capacity": sum(cap),
               "nominal_capacity_ratio": str(Fraction(sum(cap), sum(nominal))),
               "minimum_total_demand": str(Fraction(min(map(sum, scenario)), 10)),
               "peak_demand": str(Fraction(peak, 10)), "dummy_capacity": dummy,
               "uniform_penalty_exact": str(rho), "quantity_scale": units, "cost_scale": cost_scale,
               "capacity_lattice_source_units": lattice, "exact_reachable_capacities": reachable.bit_count(),
               "scenario_sha256": sha(encode(ticks)), "distinct_scenario_rows": len(set(scenario)),
               "scenarios_have_exact_nominal_means": True}
    return data, profile


def main():
    if (HERE / "lock.json").exists():
        raise FileExistsError("The prospective lock already exists")
    with ThreadPoolExecutor(max_workers=3) as pool:
        sources = list(pool.map(raw_source, RAW))
    artifacts = {}
    cases = {}
    for case, name, url, raw in sources:
        instance, profile = adapt(case, raw)
        instance_path = f"{case}.json"
        artifacts.update({name: raw, instance_path: encode(instance)})
        cases[case] = {"raw_file": name, "raw_sha256": sha(raw), "raw_url": url, "raw_bytes": len(raw),
                       "file": instance_path, "instance_sha256": sha(artifacts[instance_path]), **profile}
    previous_lock = HERE.parent / "scotland_lost_sales" / "adaptive_60s" / "lock.json"
    previous = json.loads(previous_lock.read_bytes())
    source_paths = ["PROTOCOL.md", "seal_inputs.py", "run_diaz.py", "finish_small.py",
                    "../scotland_lost_sales/adaptive_60s/derived_upper.py"]
    for name, digest in previous["source_sha256"].items():
        rel = "../scotland_lost_sales/" + name
        if sha((HERE / rel).read_bytes()) != digest:
            raise ValueError(f"A frozen Scotland dependency changed: {name}")
        source_paths.append(rel)
    manifest = {"repo": f"https://github.com/{REPO}", "source_commit": COMMIT, "case_order": list(RAW), "cases": cases}
    artifacts["manifest.json"] = encode(manifest)
    lock = {"method": "original_adaptive_vs_separated_derived", "cpu": 26, "budget_seconds": 60.0,
            "case_order": list(RAW), "arm_order": {"p01": ["original", "separated"],
                    "p26": ["separated", "original"], "p50": ["original", "separated"]},
            "probability_denominator": 200, "manifest_sha256": sha(artifacts["manifest.json"]),
            "source_sha256": {name: sha((HERE / name).read_bytes()) for name in source_paths}}
    artifacts["lock.json"] = encode(lock)
    if any((HERE / name).exists() for name in artifacts):
        raise FileExistsError("A prospective artifact already exists")
    for name, raw in artifacts.items():
        with (HERE / name).open("xb") as stream:
            stream.write(raw)
    print(json.dumps({"lock_sha256": sha(artifacts["lock.json"]), "manifest_sha256": lock["manifest_sha256"],
                      "cases": cases}, indent=2))


if __name__ == "__main__":
    main()
