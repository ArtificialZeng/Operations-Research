"""
Stage-1 Label-Blind Grouped Cohort Selector (N = 36 Alexandria PBE crystals).
Strictly follows STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md §1:
  - Reads ONLY `mp_id` and `nsites` from Alexandria `pbe.csv` (all phonon/stability columns discarded immediately).
  - Deterministically orders candidates by SHA-256("mlip_soft_mode_stage1_v1:" + mp_id).
  - Inspects ONLY geometry/composition/space-group headers of each .yaml.bz2 (NEVER reads force_constants,
    displacements, phonon_freq, or stability labels!).
  - Fills 4 balanced crystal-system groups (9 each = 36 distinct reduced formulas, PBE non-+U aligned).
"""
from __future__ import annotations

import bz2
from collections import Counter
import csv
import hashlib
import io
import json
import math
import pathlib
import time
import urllib.request
from typing import Any, Dict, List, Optional

import numpy as np
import yaml
from ase.data import atomic_numbers


ROOT = pathlib.Path(__file__).resolve().parent
CACHE_DIR = ROOT / "raw_stage1_pbe"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

SMOKE_EXCLUDE = {"mp-149", "mp-1265", "mp-2998", "mp-5229", "mp-2657", "mp-7000"}
HUBBARD_U_METALS = {"Co", "Cr", "Fe", "Mn", "Mo", "Ni", "V", "W"}
HUBBARD_U_ANIONS = {"O", "F"}
PER_GROUP = 9
GROUPS = ["Cubic", "Tetragonal", "Trigonal_Hexagonal", "Orthorhombic_Monoclinic_Triclinic"]


def sg_to_group(sg_num: int) -> str:
    if 195 <= sg_num <= 230:
        return "Cubic"
    if 75 <= sg_num <= 142:
        return "Tetragonal"
    if 143 <= sg_num <= 194:
        return "Trigonal_Hexagonal"
    if 1 <= sg_num <= 74:
        return "Orthorhombic_Monoclinic_Triclinic"
    raise ValueError(f"Invalid space group number: {sg_num}")


def reduced_formula(symbols: List[str]) -> str:
    counts = Counter(symbols)
    g = math.gcd(*counts.values())
    return "".join(f"{el}{counts[el]//g if counts[el]//g > 1 else ''}" for el in sorted(counts))


def parse_geometry_header_only(bz2_bytes: bytes) -> Optional[Dict[str, Any]]:
    """
    Strictly label-blind YAML header extractor: skips force_constants, displacements,
    phonon_freq, group_velocities, entropy, heat_capacity, free_energy, energy, temperatures.
    """
    raw_text = bz2.decompress(bz2_bytes).decode("utf-8", errors="replace")
    keep_sections = {
        "space_group", "primitive_matrix", "supercell_matrix",
        "primitive_cell", "unit_cell", "supercell",
        "born_effective_charge", "dielectric_constant", "nsites",
    }
    kept_lines: List[str] = []
    keeping = False
    has_nac = False
    for line in raw_text.splitlines():
        if line and not line[0].isspace() and ":" in line:
            key = line.split(":", 1)[0].strip()
            if key in ("born_effective_charge", "dielectric_constant"):
                has_nac = True
                keeping = False
            elif key in keep_sections:
                keeping = True
                kept_lines.append(line)
            else:
                keeping = False
        elif keeping:
            kept_lines.append(line)

    hdr = yaml.safe_load("\n".join(kept_lines))
    if not isinstance(hdr, dict):
        return None
    if has_nac or "primitive_cell" not in hdr or "supercell_matrix" not in hdr or "space_group" not in hdr:
        return None

    sg_num = int(hdr["space_group"]["number"])
    prim_cell_blk = hdr["primitive_cell"]
    prim_lat = np.array(prim_cell_blk["lattice"], dtype=np.float64)
    prim_pts = prim_cell_blk["points"]
    prim_syms = [pt["symbol"] for pt in prim_pts]
    n_prim = len(prim_syms)

    # Primitive matrix (defaults to I_3 if absent)
    pm = np.array(hdr.get("primitive_matrix", np.eye(3)), dtype=np.float64)
    sm = np.array(hdr["supercell_matrix"], dtype=np.float64)
    # Exact integer S_DFT_rel such that supercell.cell == S_DFT_rel.T @ prim.cell
    S_dft_rel_f = np.linalg.inv(pm) @ sm
    S_dft_rel = np.round(S_dft_rel_f).astype(int)
    if not np.allclose(S_dft_rel_f, S_dft_rel, atol=1e-5):
        return None
    V_dft = int(round(abs(np.linalg.det(S_dft_rel))))
    n_sc = len(hdr["supercell"]["points"]) if "supercell" in hdr and "points" in hdr["supercell"] else V_dft * n_prim

    return {
        "sg_num": sg_num,
        "sg_type": str(hdr["space_group"].get("type", "")),
        "n_prim": n_prim,
        "prim_symbols": prim_syms,
        "reduced_formula": reduced_formula(prim_syms),
        "prim_lengths": [round(float(x), 5) for x in np.linalg.norm(prim_lat, axis=1)],
        "V_dft": V_dft,
        "n_sc_dft": n_sc,
        "S_dft_rel": S_dft_rel.tolist(),
        "has_nac": has_nac,
    }


def main() -> None:
    proto_p = ROOT / "STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md"
    proto_sha = hashlib.sha256(proto_p.read_bytes()).hexdigest()
    print(f"Protocol SHA-256: {proto_sha}")

    # 1. Fetch pbe.csv and IMMEDIATELY strip all columns except mp_id and nsites!
    idx_p = CACHE_DIR / "pbe_id_nsites_labelblind.csv"
    if not idx_p.exists():
        url = "https://alexandria.icams.rub.de/data/phonon_benchmark/pbe.csv"
        req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
        raw_csv = urllib.request.urlopen(req, timeout=60).read().decode("utf-8", errors="replace")
        reader = csv.DictReader(io.StringIO(raw_csv))
        rows_clean = [(r["mp_id"].strip(), int(float(r["nsites"]))) for r in reader if r.get("mp_id") and r.get("nsites")]
        with idx_p.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(["mp_id", "nsites"])
            w.writerows(rows_clean)
        del raw_csv

    candidates = []
    with idx_p.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            mid = row["mp_id"]
            ns = int(row["nsites"])
            if mid in SMOKE_EXCLUDE or ns > 160:
                continue
            hkey = hashlib.sha256(f"mlip_soft_mode_stage1_v1:{mid}".encode("utf-8")).hexdigest()
            candidates.append((hkey, mid, ns))
    candidates.sort(key=lambda x: x[0])
    print(f"Eligible label-blind pool (nsites<=160, excl. 6 smoke): {len(candidates)} candidates")

    selected_by_group: Dict[str, List[Dict[str, Any]]] = {g: [] for g in GROUPS}
    seen_formulas = set()
    inspected = 0
    rejected_reasons: Counter = Counter()

    for hkey, mid, ns in candidates:
        if all(len(selected_by_group[g]) >= PER_GROUP for g in GROUPS):
            break
        inspected += 1
        dst = CACHE_DIR / f"{mid}.yaml.bz2"
        try:
            if not dst.exists():
                url = f"https://alexandria.icams.rub.de/data/phonon_benchmark/pbe/{mid}.yaml.bz2"
                req = urllib.request.Request(url, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
                data = urllib.request.urlopen(req, timeout=30).read()
                dst.write_bytes(data)
            else:
                data = dst.read_bytes()
        except Exception as e:
            rejected_reasons["download_err"] += 1
            continue

        info = parse_geometry_header_only(data)
        if info is None:
            rejected_reasons["header_invalid_or_nac"] += 1
            dst.unlink(missing_ok=True)
            continue

        grp = sg_to_group(info["sg_num"])
        if len(selected_by_group[grp]) >= PER_GROUP:
            rejected_reasons["group_already_full"] += 1
            dst.unlink(missing_ok=True)
            continue

        elems = set(info["prim_symbols"])
        zs = [atomic_numbers[el] for el in elems]
        if any(z > 83 or (57 <= z <= 71) for z in zs):
            rejected_reasons["heavy_or_lanthanide"] += 1
            dst.unlink(missing_ok=True)
            continue
        if (elems & HUBBARD_U_METALS) and (elems & HUBBARD_U_ANIONS):
            rejected_reasons["hubbard_U_oxide_fluoride"] += 1
            dst.unlink(missing_ok=True)
            continue
        if not (2 <= info["n_prim"] <= 12):
            rejected_reasons["n_prim_out_of_range"] += 1
            dst.unlink(missing_ok=True)
            continue
        if not (4 <= info["V_dft"] <= 64) or info["n_sc_dft"] > 160:
            rejected_reasons["V_dft_or_nsc_out_of_range"] += 1
            dst.unlink(missing_ok=True)
            continue
        if info["reduced_formula"] in seen_formulas:
            rejected_reasons["duplicate_formula"] += 1
            dst.unlink(missing_ok=True)
            continue

        # Compute pre-locked S_coarse
        ks = [1 if a >= 4.5 else 2 for a in info["prim_lengths"]]
        if ks[0] * ks[1] * ks[2] >= info["V_dft"]:
            ks = [1, 1, 1]
        if ks[0] * ks[1] * ks[2] >= info["V_dft"]:
            rejected_reasons["coarse_not_smaller_than_dft"] += 1
            dst.unlink(missing_ok=True)
            continue

        seen_formulas.add(info["reduced_formula"])
        entry = {
            "mp_id": mid,
            "hash_key": hkey[:16],
            "group": grp,
            "sg_num": info["sg_num"],
            "sg_type": info["sg_type"],
            "reduced_formula": info["reduced_formula"],
            "n_prim": info["n_prim"],
            "prim_lengths": info["prim_lengths"],
            "V_dft": info["V_dft"],
            "n_sc_dft": info["n_sc_dft"],
            "S_dft_rel": info["S_dft_rel"],
            "S_coarse_diag": ks,
            "yaml_bz2_bytes": len(data),
            "yaml_bz2_sha256": hashlib.sha256(data).hexdigest(),
        }
        selected_by_group[grp].append(entry)
        counts_str = " ".join(f"{g[:4]}={len(selected_by_group[g])}/{PER_GROUP}" for g in GROUPS)
        print(f"  ACCEPT [{sum(len(v) for v in selected_by_group.values()):02d}/36] {mid:10s} {info['reduced_formula']:12s} {grp:12s} SG={info['sg_num']:3d} n_p={info['n_prim']:2d} V_dft={info['V_dft']:2d} S_c={ks} | {counts_str}", flush=True)

    flat = [x for g in GROUPS for x in selected_by_group[g]]
    assert len(flat) == 36, f"Only selected {len(flat)}/36!"
    manifest = {
        "protocol_sha256": proto_sha,
        "selection_seed": "mlip_soft_mode_stage1_v1",
        "source_url": "https://alexandria.icams.rub.de/data/phonon_benchmark/pbe/",
        "source_license": "CC BY 4.0",
        "label_blind_verified": True,
        "n_candidates_inspected": inspected,
        "rejected_reasons": dict(rejected_reasons),
        "group_counts": {g: len(selected_by_group[g]) for g in GROUPS},
        "n_selected": len(flat),
        "materials": flat,
    }
    out_p = ROOT / "stage1_cohort_manifest.json"
    out_p.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nLOCKED 36-MATERIAL LABEL-BLIND COHORT -> {out_p.name} (SHA256={hashlib.sha256(out_p.read_bytes()).hexdigest()})")
    print("Rejected reasons:", dict(rejected_reasons))


if __name__ == "__main__":
    main()
