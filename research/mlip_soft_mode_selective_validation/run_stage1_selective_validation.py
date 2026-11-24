"""
Stage-1 Pre-Locked Grouped Development Pilot Runner — Selective Verification of Soft Phonon Modes.

Strictly implements STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md:
  - Fixed PBE non-+U label-blind grouped cohort (N = 36 Alexandria PBE crystals, stage1_cohort_manifest.json).
  - Official mace-omat-0-small.model (float64, CUDA), phonopy==4.11.0, ZERO ML relaxation, matched NAC=False.
  - Exact DFT-commensurate q-grid Q_exact(m) = {q in [0,1)^3 : S_DFT_rel^T q in Z^3}.
  - Coarse small-supercell MACE Phonopy -> Minimal index-L commensurate two-h Bloch Rayleigh recheck
    (h1=0.001 A, h2=0.002 A + non-self-conjugate quadrature cross-check) -> Full commensurate MACE Phonopy
    (S_DFT_rel) -> Independent same-geometry PBE DFT reference.
  - Equal-budget selective allocation benchmark across atom-force evaluations, wall time, and force calls.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction
import hashlib
import json
import math
import os
import pathlib
import random
import time
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import phonopy
from phonopy import Phonopy
from phonopy.physical_units import get_physical_units
from phonopy.structure.atoms import PhonopyAtoms
from ase import Atoms
import torch
from mace.calculators import MACECalculator


ROOT = pathlib.Path(__file__).resolve().parent
CACHE_DIR = ROOT / "raw_stage1_pbe"
MODEL_PATH = ROOT / "models" / "mace-omat-0-small.model"
MANIFEST_PATH = ROOT / "stage1_cohort_manifest.json"
PROTO_PATH = ROOT / "STAGE1_SELECTIVE_VALIDATION_PROTOCOL.md"
OUT_DIR = ROOT / "stage1_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VASP_TO_THZ = float(get_physical_units().DefaultToTHz)
TAU_MAIN = 0.25
H1_ANG = 0.001
H2_ANG = 0.002


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def signed_sqrt_freq(omega2_thz2: float) -> float:
    return math.copysign(math.sqrt(abs(omega2_thz2)), omega2_thz2)


def ph_cell_to_ase(cell: PhonopyAtoms) -> Atoms:
    return Atoms(
        symbols=list(cell.symbols),
        cell=np.array(cell.cell, dtype=np.float64),
        scaled_positions=np.array(cell.scaled_positions, dtype=np.float64),
        pbc=True,
    )


def exact_commensurate_qpoints(S_rel: np.ndarray) -> List[Tuple[Fraction, Fraction, Fraction]]:
    det = int(round(abs(np.linalg.det(S_rel))))
    S_T = S_rel.T.astype(int)
    adj = np.round(np.linalg.inv(S_T) * np.linalg.det(S_T)).astype(int)
    assert np.allclose(S_T @ adj, int(round(np.linalg.det(S_T))) * np.eye(3))
    gens = [tuple(Fraction(int(adj[r, c]), det) % 1 for r in range(3)) for c in range(3)]
    seen = {(Fraction(0), Fraction(0), Fraction(0))}
    frontier = list(seen)
    while frontier:
        cur = frontier.pop()
        for g in gens:
            nxt = tuple((cur[i] + g[i]) % 1 for i in range(3))
            if nxt not in seen:
                seen.add(nxt)
                frontier.append(nxt)
    assert len(seen) == det, f"Expected {det} q-points, got {len(seen)}"
    return sorted(seen)


def minimal_commensurate_supercell_matrix(q_frac: Tuple[Fraction, Fraction, Fraction], prim_cell: np.ndarray) -> np.ndarray:
    dens = [f.denominator for f in q_frac]
    L = math.lcm(*dens)
    m = [int(f * L) % L for f in q_frac]

    def egcd(a: int, b: int) -> Tuple[int, int, int]:
        if b == 0:
            return (abs(a), 1 if a >= 0 else -1, 0)
        g, x1, y1 = egcd(b, a % b)
        return (g, y1, x1 - (a // b) * y1)

    g0 = math.gcd(m[0], L)
    h00 = L // g0

    g01 = math.gcd(g0, m[1])
    h11 = g0 // g01
    rhs1 = (-m[1] * h11) % L
    _, inv0, _ = egcd(m[0] // g0, h00)
    h01 = ((rhs1 // g0) * inv0) % h00

    g012 = math.gcd(g01, m[2])
    h22 = g01 // g012
    rhs2 = (-m[2] * h22) % L
    g_ab, xa, yb = egcd(m[0], m[1])
    _, inv_ab, _ = egcd(g_ab // g01, L // g01)
    scale = ((rhs2 // g01) * inv_ab) % (L // g01)
    h02_raw = (xa * scale) % L
    h12_raw = (yb * scale) % L
    k1 = h12_raw // h11
    h12 = h12_raw - k1 * h11
    h02 = (h02_raw - k1 * h01) % h00

    S = np.array([[h00, h01, h02], [0, h11, h12], [0, 0, h22]], dtype=int)
    for _ in range(30):
        changed = False
        vecs = [prim_cell.T @ S[:, j] for j in range(3)]
        for i in range(3):
            for j in range(3):
                if i == j:
                    continue
                vi, vj = vecs[i], vecs[j]
                denom = float(np.dot(vj, vj))
                if denom < 1e-12:
                    continue
                mu = int(round(float(np.dot(vi, vj)) / denom))
                if mu != 0:
                    S[:, i] -= mu * S[:, j]
                    changed = True
                    vecs[i] = prim_cell.T @ S[:, i]
        if not changed:
            break
    if np.linalg.det(S) < 0:
        S[:, 0] = -S[:, 0]
    assert int(round(np.linalg.det(S))) == L
    q_arr = np.array([float(f) for f in q_frac], dtype=np.float64)
    stq = S.T @ q_arr
    assert np.allclose(stq, np.round(stq), atol=1e-10)
    return S


def compute_mace_phonopy(
    prim: PhonopyAtoms,
    supercell_matrix: np.ndarray,
    calc: MACECalculator,
    disp_dist: float = 0.002,
) -> Tuple[Phonopy, Dict[str, Any]]:
    ph = Phonopy(unitcell=prim, supercell_matrix=supercell_matrix, primitive_matrix=np.eye(3, dtype=np.float64))
    ph.generate_displacements(distance=disp_dist, is_plusminus=True)
    scs = ph.supercells_with_displacements
    n_sc = len(ph.supercell)
    t0 = time.perf_counter()
    forces_list = []
    for sc in scs:
        atoms = ph_cell_to_ase(sc)
        atoms.calc = calc
        forces_list.append(np.array(atoms.get_forces(), dtype=np.float64))
    wall_s = time.perf_counter() - t0
    ph.forces = forces_list
    ph.produce_force_constants()
    ph.symmetrize_force_constants()
    return ph, {
        "n_supercell_atoms": int(n_sc),
        "n_force_calls": int(len(scs)),
        "atom_force_evals": int(len(scs) * n_sc),
        "wall_s": round(wall_s, 4),
    }


def min_non_acoustic_on_qgrid(
    ph: Phonopy,
    q_list: List[Tuple[Fraction, Fraction, Fraction]],
    S_comm_check: Optional[np.ndarray] = None,
) -> Dict[str, Any]:
    n_p = len(ph.primitive)
    masses_p = np.array(ph.primitive.masses, dtype=np.float64)
    q_arr = np.array([[float(x) for x in q] for q in q_list], dtype=np.float64)
    ph.run_qpoints(q_arr, with_eigenvectors=True)
    freqs = ph.qpoints.frequencies
    evecs = ph.qpoints.eigenvectors

    best_f = 1e9
    best_q = None
    best_b = -1
    best_ev = None
    best_comm_f = 1e9
    n_neg_025 = 0

    for qi, qf in enumerate(q_list):
        is_gamma = all(x == 0 for x in qf)
        if S_comm_check is not None:
            stq = S_comm_check.T @ q_arr[qi]
            is_comm = bool(np.allclose(stq, np.round(stq), atol=1e-10))
        else:
            is_comm = True

        q_min = 1e9
        for bi in range(3 * n_p):
            if is_gamma:
                ev = evecs[qi][:, bi].reshape(n_p, 3)
                p_tr = float(np.sum(np.abs(np.sum(np.sqrt(masses_p)[:, None] * ev, axis=0)) ** 2) / np.sum(masses_p))
                if p_tr > 0.5:
                    continue
            fval = float(freqs[qi, bi])
            if fval < q_min:
                q_min = fval
            if fval < best_f:
                best_f = fval
                best_q = qf
                best_b = bi
                best_ev = evecs[qi][:, bi]
            if is_comm and fval < best_comm_f:
                best_comm_f = fval
        if q_min < -TAU_MAIN:
            n_neg_025 += 1

    return {
        "q_frac": best_q,
        "band": int(best_b),
        "min_freq_thz": float(best_f),
        "eigvec": best_ev,
        "comm_min_freq_thz": float(best_comm_f) if best_comm_f < 1e8 else None,
        "n_neg_qpoints_025": int(n_neg_025),
    }


def build_bloch_quadratures(
    prim: PhonopyAtoms,
    S_comm: np.ndarray,
    q_vec: np.ndarray,
    eigvec: np.ndarray,
) -> Tuple[PhonopyAtoms, np.ndarray, np.ndarray, np.ndarray]:
    ph_sc = Phonopy(unitcell=prim, supercell_matrix=S_comm, primitive_matrix=np.eye(3, dtype=np.float64))
    sc = ph_sc.supercell
    n_prim = len(prim)
    n_sc = len(sc)
    e_mat = np.asarray(eigvec, dtype=np.complex128).reshape(n_prim, 3)
    prim_masses = np.array(prim.masses, dtype=np.float64)
    sc_masses = np.array(sc.masses, dtype=np.float64)
    x_prim_all = np.array(sc.scaled_positions, dtype=np.float64) @ S_comm.T
    s2p = ph_sc.primitive.s2p_map
    p2p = ph_sc.primitive.p2p_map
    kappa_of_I = np.array([p2p[s2p[I]] for I in range(n_sc)], dtype=int)

    w = np.zeros((n_sc, 3), dtype=np.complex128)
    for I in range(n_sc):
        k = kappa_of_I[I]
        phase = np.exp(1j * 2.0 * math.pi * float(np.dot(q_vec, x_prim_all[I])))
        w[I, :] = (e_mat[k, :] / math.sqrt(prim_masses[k])) * phase
    return sc, sc_masses, np.real(w), np.imag(w)


def eval_rayleigh_single(
    sc: PhonopyAtoms,
    sc_masses: np.ndarray,
    u_dir: np.ndarray,
    h_ang: float,
    calc: MACECalculator,
) -> Dict[str, Any]:
    max_amp = float(np.max(np.linalg.norm(u_dir, axis=1)))
    if max_amp < 1e-12:
        return {"valid": False}
    u_hat = u_dir / max_amp
    mass_norm = float(np.sum(sc_masses[:, None] * (u_hat ** 2)))
    base = ph_cell_to_ase(sc)
    pos0 = base.get_positions().copy()

    t0 = time.perf_counter()
    ap = base.copy()
    ap.set_positions(pos0 + h_ang * u_hat)
    ap.calc = calc
    fp = np.array(ap.get_forces(), dtype=np.float64)

    am = base.copy()
    am.set_positions(pos0 - h_ang * u_hat)
    am.calc = calc
    fm = np.array(am.get_forces(), dtype=np.float64)
    wall_s = time.perf_counter() - t0

    omega2_thz2 = (-float(np.sum(u_hat * (fp - fm))) / (2.0 * h_ang * mass_norm)) * (VASP_TO_THZ ** 2)
    return {
        "valid": True,
        "freq_thz": float(signed_sqrt_freq(omega2_thz2)),
        "omega2_thz2": float(omega2_thz2),
        "n_force_calls": 2,
        "atom_force_evals": int(2 * len(sc)),
        "wall_s": float(wall_s),
    }


def three_way_label(f_thz: float, tau: float) -> str:
    if f_thz < -tau:
        return "NEG"
    if f_thz > tau:
        return "POS"
    return "NEAR_ZERO"


def eval_predictions_vs_truth(records: List[Dict[str, Any]], pred_unstable: Dict[str, bool], truth_key: str, tau: float) -> Dict[str, Any]:
    tp = fp = tn = fn = 0
    nz_pred_neg = nz_pred_pos = 0
    for r in records:
        p = pred_unstable[r["mp_id"]]
        tl = three_way_label(r[truth_key], tau)
        if tl == "NEG":
            if p:
                tp += 1
            else:
                fn += 1
        elif tl == "POS":
            if p:
                fp += 1
            else:
                tn += 1
        else:
            if p:
                nz_pred_neg += 1
            else:
                nz_pred_pos += 1
    n_dec = tp + fp + tn + fn
    acc_dec = (tp + tn) / n_dec if n_dec > 0 else None
    fpr_pos = fp / (fp + tn) if (fp + tn) > 0 else None
    rec_neg = tp / (tp + fn) if (tp + fn) > 0 else None
    prec_neg = tp / (tp + fp) if (tp + fp) > 0 else None
    f1_neg = (2 * prec_neg * rec_neg / (prec_neg + rec_neg)) if (prec_neg and rec_neg and (prec_neg + rec_neg) > 0) else 0.0
    # Also strict binary over ALL 36 crystals (< -tau vs >= -tau)
    btp = sum(1 for r in records if pred_unstable[r["mp_id"]] and r[truth_key] < -tau)
    bfp = sum(1 for r in records if pred_unstable[r["mp_id"]] and r[truth_key] >= -tau)
    btn = sum(1 for r in records if (not pred_unstable[r["mp_id"]]) and r[truth_key] >= -tau)
    bfn = sum(1 for r in records if (not pred_unstable[r["mp_id"]]) and r[truth_key] < -tau)
    return {
        "decisive_counts": {"TP": tp, "FP": fp, "TN": tn, "FN": fn, "NZ_pred_neg": nz_pred_neg, "NZ_pred_pos": nz_pred_pos},
        "decisive_acc": round(acc_dec, 4) if acc_dec is not None else None,
        "fpr_on_POS": round(fpr_pos, 4) if fpr_pos is not None else None,
        "recall_on_NEG": round(rec_neg, 4) if rec_neg is not None else None,
        "f1_on_NEG_decisive": round(f1_neg, 4),
        "all36_binary_acc": round((btp + btn) / len(records), 4),
        "all36_binary_FP": bfp,
        "all36_binary_FN": bfn,
    }


def run_equal_budget_benchmark(records: List[Dict[str, Any]], tau: float, cost_axis: str) -> Dict[str, Any]:
    """
    cost_axis in {'atom_force_evals', 'wall_s', 'n_force_calls'}.
    Evaluates all 6 pre-locked policies across budgets B in {10%, 25%, 50%, 75%, 100%} of total flagged full-rerun cost.
    """
    flagged = [r for r in records if r["f_coarse_min_thz"] < -tau]
    full_cost_key = f"mace_full_{cost_axis}"
    ray_cost_key = f"ray_{cost_axis}"
    total_full_flagged = sum(float(r[full_cost_key]) for r in flagged)

    def base_preds() -> Dict[str, bool]:
        return {r["mp_id"]: (r["f_coarse_min_thz"] < -tau) for r in records}

    def eval_policy_on_order(order: List[Dict[str, Any]], budget: float) -> Tuple[Dict[str, bool], float, int]:
        preds = base_preds()
        spent = 0.0
        n_checked = 0
        for r in order:
            c = float(r[full_cost_key])
            if spent + c <= budget + 1e-9:
                spent += c
                n_checked += 1
                preds[r["mp_id"]] = (r["f_mace_full_min_thz"] < -tau)
        return preds, spent, n_checked

    def eval_rayleigh_gated(budget: float, require_full_confirm: bool) -> Tuple[Dict[str, bool], float, int, int]:
        """
        Non-commensurate flagged crystals prioritized by smallest |f_coarse_min|.
        Step 1: Cheap minimal-repeat Rayleigh check.
          - If confirmed negative (both h1 & h2 < -tau and quad ok): keep unstable, SKIP full rerun!
          - If rejected nonnegative:
              * If require_full_confirm=True (`Rayleigh_Gated_Full`): schedule full commensurate rerun!
              * If require_full_confirm=False (`Rayleigh_Only`): mark stable immediately without full rerun.
        Step 2 (if budget remains for `Rayleigh_Gated_Full`): spend remaining budget on full commensurate reruns
        for Rayleigh-rejected candidates first, then commensurate flagged crystals (smallest |f_coarse_min|).
        """
        preds = base_preds()
        spent = 0.0
        n_ray = 0
        n_full = 0

        noncomm = sorted([r for r in flagged if not r["is_q_star_commensurate"]], key=lambda x: abs(x["f_coarse_min_thz"]))
        comm = sorted([r for r in flagged if r["is_q_star_commensurate"]], key=lambda x: abs(x["f_coarse_min_thz"]))

        rejected_queue: List[Dict[str, Any]] = []
        for r in noncomm:
            cr = float(r[ray_cost_key])
            if spent + cr > budget + 1e-9:
                continue
            spent += cr
            n_ray += 1
            ray_conf_neg = (
                r["f_ray_h1_thz"] < -tau
                and r["f_ray_h2_thz"] < -tau
                and (r["ray_quad_diff_h1_thz"] is None or r["ray_quad_diff_h1_thz"] < 0.05)
            )
            if ray_conf_neg:
                preds[r["mp_id"]] = True  # Confirmed negative direction -> save full rerun!
            else:
                if require_full_confirm:
                    rejected_queue.append(r)
                else:
                    preds[r["mp_id"]] = False

        if require_full_confirm:
            for r in rejected_queue + comm:
                cf = float(r[full_cost_key])
                if spent + cf <= budget + 1e-9:
                    spent += cf
                    n_full += 1
                    preds[r["mp_id"]] = (r["f_mace_full_min_thz"] < -tau)
        return preds, spent, n_ray, n_full

    budget_fracs = [0.0, 0.10, 0.25, 0.50, 0.75, 1.00]
    out: Dict[str, Any] = {
        "cost_axis": cost_axis,
        "tau_thz": tau,
        "n_flagged": len(flagged),
        "n_flagged_noncomm": sum(1 for r in flagged if not r["is_q_star_commensurate"]),
        "total_full_rerun_cost_flagged": round(total_full_flagged, 4),
        "budgets": {},
    }
    if not flagged or total_full_flagged <= 0:
        return out

    order_nearzero = sorted(flagged, key=lambda x: abs(x["f_coarse_min_thz"]))
    order_noncomm = sorted(flagged, key=lambda x: (1 if x["is_q_star_commensurate"] else 0, abs(x["f_coarse_min_thz"])))

    for bf in budget_fracs:
        B = bf * total_full_flagged
        bkey = f"{int(round(bf * 100))}%"
        res_b: Dict[str, Any] = {"budget_value": round(B, 4)}

        # 1. No_Recheck (only at 0%)
        if bf == 0.0:
            p0 = base_preds()
            res_b["No_Recheck"] = {
                "spent": 0.0,
                "vs_MACE_full": eval_predictions_vs_truth(records, p0, "f_mace_full_min_thz", tau),
                "vs_DFT": eval_predictions_vs_truth(records, p0, "f_dft_min_thz", tau),
            }
            out["budgets"][bkey] = res_b
            continue

        # 2. Random_Full_Recheck (200 seeds)
        rng = random.Random(20261124 + int(round(bf * 1000)))
        rand_mace_fpr, rand_dft_fpr, rand_mace_acc, rand_dft_acc, rand_dft_f1 = [], [], [], [], []
        for _ in range(200):
            ord_r = list(flagged)
            rng.shuffle(ord_r)
            pr, _, _ = eval_policy_on_order(ord_r, B)
            em = eval_predictions_vs_truth(records, pr, "f_mace_full_min_thz", tau)
            ed = eval_predictions_vs_truth(records, pr, "f_dft_min_thz", tau)
            if em["fpr_on_POS"] is not None:
                rand_mace_fpr.append(em["fpr_on_POS"])
            if ed["fpr_on_POS"] is not None:
                rand_dft_fpr.append(ed["fpr_on_POS"])
            if em["decisive_acc"] is not None:
                rand_mace_acc.append(em["decisive_acc"])
            if ed["decisive_acc"] is not None:
                rand_dft_acc.append(ed["decisive_acc"])
            rand_dft_f1.append(ed["f1_on_NEG_decisive"])
        res_b["Random_Full_Recheck_200seeds"] = {
            "mean_MACE_fpr_POS": round(float(np.mean(rand_mace_fpr)), 4) if rand_mace_fpr else None,
            "mean_MACE_dec_acc": round(float(np.mean(rand_mace_acc)), 4) if rand_mace_acc else None,
            "mean_DFT_fpr_POS": round(float(np.mean(rand_dft_fpr)), 4) if rand_dft_fpr else None,
            "mean_DFT_dec_acc": round(float(np.mean(rand_dft_acc)), 4) if rand_dft_acc else None,
            "mean_DFT_f1_NEG": round(float(np.mean(rand_dft_f1)), 4),
        }

        # 3. NearZero_Mag_Full_Recheck
        p_nz, s_nz, n_nz = eval_policy_on_order(order_nearzero, B)
        res_b["NearZero_Mag_Full_Recheck"] = {
            "spent": round(s_nz, 4), "n_full": n_nz,
            "vs_MACE_full": eval_predictions_vs_truth(records, p_nz, "f_mace_full_min_thz", tau),
            "vs_DFT": eval_predictions_vs_truth(records, p_nz, "f_dft_min_thz", tau),
        }

        # 4. NonComm_Only_Full_Recheck
        p_nc, s_nc, n_nc = eval_policy_on_order(order_noncomm, B)
        res_b["NonComm_Only_Full_Recheck"] = {
            "spent": round(s_nc, 4), "n_full": n_nc,
            "vs_MACE_full": eval_predictions_vs_truth(records, p_nc, "f_mace_full_min_thz", tau),
            "vs_DFT": eval_predictions_vs_truth(records, p_nc, "f_dft_min_thz", tau),
        }

        # 5. Rayleigh_Gated_Full (Conservative)
        p_rg, s_rg, nr_rg, nf_rg = eval_rayleigh_gated(B, require_full_confirm=True)
        res_b["Rayleigh_Gated_Full"] = {
            "spent": round(s_rg, 4), "n_ray": nr_rg, "n_full": nf_rg,
            "vs_MACE_full": eval_predictions_vs_truth(records, p_rg, "f_mace_full_min_thz", tau),
            "vs_DFT": eval_predictions_vs_truth(records, p_rg, "f_dft_min_thz", tau),
        }

        # 6. Rayleigh_Only (Pure Cheap Triage)
        p_ro, s_ro, nr_ro, nf_ro = eval_rayleigh_gated(B, require_full_confirm=False)
        res_b["Rayleigh_Only"] = {
            "spent": round(s_ro, 4), "n_ray": nr_ro, "n_full": nf_ro,
            "vs_MACE_full": eval_predictions_vs_truth(records, p_ro, "f_mace_full_min_thz", tau),
            "vs_DFT": eval_predictions_vs_truth(records, p_ro, "f_dft_min_thz", tau),
        }
        out["budgets"][bkey] = res_b

    return out


def main() -> None:
    t_wall0 = time.perf_counter()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mats = manifest["materials"]
    assert len(mats) == 36

    device = "cuda" if torch.cuda.is_available() else "cpu"
    calc = MACECalculator(model_paths=str(MODEL_PATH), device=device, default_dtype="float64")
    print(f"Running Stage-1 Pilot on {len(mats)} crystals | device={device} | dtype=float64 | PID={os.getpid()}", flush=True)

    records: List[Dict[str, Any]] = []
    for idx, m in enumerate(mats, 1):
        mid = m["mp_id"]
        yp = CACHE_DIR / f"{mid}.yaml.bz2"
        assert sha256_file(yp) == m["yaml_bz2_sha256"], f"Checksum mismatch on {mid}!"

        ph_dft = phonopy.load(str(yp))
        if ph_dft.force_constants is None:
            ph_dft.produce_force_constants()
        ph_dft.symmetrize_force_constants()
        assert ph_dft.nac_params is None, f"Unexpected NAC on {mid}!"

        prim = ph_dft.primitive
        prim_cell = np.array(prim.cell, dtype=np.float64)
        S_dft_rel = np.array(m["S_dft_rel"], dtype=int)
        assert np.allclose(ph_dft.supercell.cell, S_dft_rel.T @ prim_cell, atol=1e-5)
        S_coarse = np.diag(m["S_coarse_diag"])
        q_exact = exact_commensurate_qpoints(S_dft_rel)

        # Residual force on pinned DFT primitive cell (NO relaxation!)
        a0 = ph_cell_to_ase(prim)
        a0.calc = calc
        max_f0 = float(np.abs(a0.get_forces()).max())

        # 1. Coarse MACE screen on S_coarse
        ph_c, st_c = compute_mace_phonopy(prim, S_coarse, calc, disp_dist=0.002)
        c_min = min_non_acoustic_on_qgrid(ph_c, q_exact, S_comm_check=S_coarse)
        q_star = c_min["q_frac"]
        q_star_vec = np.array([float(x) for x in q_star], dtype=np.float64)
        e_star = c_min["eigvec"]
        is_comm = bool(np.allclose(S_coarse.T @ q_star_vec, np.round(S_coarse.T @ q_star_vec), atol=1e-10))
        is_self_conj = all((2 * f).denominator == 1 for f in q_star)

        # 2. Minimal-repeat two-h Bloch Rayleigh along nominated (q*, e*)
        S_min = minimal_commensurate_supercell_matrix(q_star, prim_cell)
        L_min = int(round(np.linalg.det(S_min)))
        sc_min, sc_m, u_cos, u_sin = build_bloch_quadratures(prim, S_min, q_star_vec, e_star)
        amp_c = float(np.max(np.linalg.norm(u_cos, axis=1)))
        amp_s = float(np.max(np.linalg.norm(u_sin, axis=1)))
        u_prim_q, u_sec_q = (u_cos, u_sin) if amp_c >= amp_s else (u_sin, u_cos)

        r_h1 = eval_rayleigh_single(sc_min, sc_m, u_prim_q, H1_ANG, calc)
        r_h2 = eval_rayleigh_single(sc_min, sc_m, u_prim_q, H2_ANG, calc)
        ray_calls = r_h1["n_force_calls"] + r_h2["n_force_calls"]
        ray_at = r_h1["atom_force_evals"] + r_h2["atom_force_evals"]
        ray_wall = r_h1["wall_s"] + r_h2["wall_s"]
        quad_diff = None
        if not is_self_conj:
            r_sec = eval_rayleigh_single(sc_min, sc_m, u_sec_q, H1_ANG, calc)
            if r_sec["valid"]:
                quad_diff = abs(r_h1["freq_thz"] - r_sec["freq_thz"])
                ray_calls += r_sec["n_force_calls"]
                ray_at += r_sec["atom_force_evals"]
                ray_wall += r_sec["wall_s"]

        # 3. Full commensurate same-model MACE Phonopy on S_dft_rel
        ph_f, st_f = compute_mace_phonopy(prim, S_dft_rel, calc, disp_dist=0.002)
        f_min = min_non_acoustic_on_qgrid(ph_f, q_exact)
        ph_f.run_qpoints([q_star_vec], with_dynamical_matrices=True)
        D_f = ph_f.qpoints.dynamical_matrices[0]
        f_mace_full_proj = signed_sqrt_freq(float(np.real(np.vdot(e_star, D_f @ e_star))) * (VASP_TO_THZ ** 2))

        # 4. Independent same-geometry PBE DFT reference on exact same Q_exact
        d_min = min_non_acoustic_on_qgrid(ph_dft, q_exact)
        ph_dft.run_qpoints([q_star_vec], with_dynamical_matrices=True)
        D_d = ph_dft.qpoints.dynamical_matrices[0]
        f_dft_proj = signed_sqrt_freq(float(np.real(np.vdot(e_star, D_d @ e_star))) * (VASP_TO_THZ ** 2))

        ray_err = abs(r_h1["freq_thz"] - f_mace_full_proj)
        rec = {
            "mp_id": mid,
            "group": m["group"],
            "sg_num": m["sg_num"],
            "reduced_formula": m["reduced_formula"],
            "n_prim": m["n_prim"],
            "V_dft": m["V_dft"],
            "n_sc_dft": m["n_sc_dft"],
            "S_coarse_diag": m["S_coarse_diag"],
            "max_residual_force_eV_A": round(max_f0, 6),
            "coarse_n_force_calls": st_c["n_force_calls"],
            "coarse_atom_force_evals": st_c["atom_force_evals"],
            "coarse_wall_s": st_c["wall_s"],
            "f_coarse_min_thz": round(c_min["min_freq_thz"], 5),
            "f_coarse_comm_min_thz": round(c_min["comm_min_freq_thz"], 5) if c_min["comm_min_freq_thz"] is not None else None,
            "n_coarse_neg_qpoints_025": c_min["n_neg_qpoints_025"],
            "q_star_frac": [str(x) for x in q_star],
            "band_star": c_min["band"],
            "is_q_star_commensurate": is_comm,
            "is_q_star_self_conjugate": is_self_conj,
            "L_minimal": L_min,
            "n_atoms_minimal_sc": len(sc_min),
            "f_ray_h1_thz": round(r_h1["freq_thz"], 5),
            "f_ray_h2_thz": round(r_h2["freq_thz"], 5),
            "ray_quad_diff_h1_thz": round(quad_diff, 6) if quad_diff is not None else None,
            "ray_n_force_calls": int(ray_calls),
            "ray_atom_force_evals": int(ray_at),
            "ray_wall_s": round(ray_wall, 4),
            "ray_1h_atom_force_evals": int(r_h1["atom_force_evals"]),
            "mace_full_n_force_calls": st_f["n_force_calls"],
            "mace_full_atom_force_evals": st_f["atom_force_evals"],
            "mace_full_wall_s": st_f["wall_s"],
            "f_mace_full_proj_thz": round(f_mace_full_proj, 5),
            "f_mace_full_min_thz": round(f_min["min_freq_thz"], 5),
            "q_mace_full_min_frac": [str(x) for x in f_min["q_frac"]],
            "ray_err_vs_mace_full_proj_thz": round(ray_err, 6),
            "f_dft_proj_thz": round(f_dft_proj, 5),
            "f_dft_min_thz": round(d_min["min_freq_thz"], 5),
            "q_dft_min_frac": [str(x) for x in d_min["q_frac"]],
            "mace_full_label_025": three_way_label(f_min["min_freq_thz"], TAU_MAIN),
            "dft_label_025": three_way_label(d_min["min_freq_thz"], TAU_MAIN),
        }
        records.append(rec)
        print(
            f"[{idx:02d}/36] {mid:10s} {m['reduced_formula']:10s} ({m['group'][:4]}) | "
            f"F0={max_f0:.3f} | c={rec['f_coarse_min_thz']:+6.2f} comm={str(is_comm)[0]} L={L_min} | "
            f"Ray={rec['f_ray_h1_thz']:+6.2f}/{rec['f_ray_h2_thz']:+6.2f} (proj={rec['f_mace_full_proj_thz']:+6.2f} err={ray_err:.4f}) | "
            f"MACE_full={rec['f_mace_full_min_thz']:+6.2f} | DFT={rec['f_dft_min_thz']:+6.2f} | "
            f"at: ray={ray_at:4d} vs full={st_f['atom_force_evals']:5d}",
            flush=True,
        )

    # Save per-material JSONL
    jsonl_p = OUT_DIR / "stage1_per_material.jsonl"
    with jsonl_p.open("w", encoding="utf-8") as f:
        for r in records:
            f.write(json.dumps(r) + "\n")

    # Compute diagnostics & equal-budget benchmarks across all 3 cost axes and 3 tau thresholds
    ray_errs = [r["ray_err_vs_mace_full_proj_thz"] for r in records]
    coarse_flagged = [r for r in records if r["f_coarse_min_thz"] < -TAU_MAIN]
    genuine_mace_false_instab = [
        r for r in coarse_flagged if r["f_mace_full_min_thz"] > TAU_MAIN
    ]
    genuine_dft_false_instab = [
        r for r in coarse_flagged if r["f_dft_min_thz"] > TAU_MAIN
    ]
    noncomm_mace_false_instab = [r for r in genuine_mace_false_instab if not r["is_q_star_commensurate"]]

    bench = {
        axis: run_equal_budget_benchmark(records, TAU_MAIN, axis)
        for axis in ["atom_force_evals", "wall_s", "n_force_calls"]
    }
    bench_tau_sens = {
        f"tau={t}": run_equal_budget_benchmark(records, t, "atom_force_evals")
        for t in [0.10, 0.50]
    }

    summary = {
        "protocol_sha256": sha256_file(PROTO_PATH),
        "manifest_sha256": sha256_file(MANIFEST_PATH),
        "runner_sha256": sha256_file(pathlib.Path(__file__)),
        "model_sha256": sha256_file(MODEL_PATH),
        "device": device,
        "dtype": "float64",
        "real_pid": os.getpid(),
        "wall_time_s": round(time.perf_counter() - t_wall0, 3),
        "n_materials": len(records),
        "mechanics_parity": {
            "median_abs_ray_err_thz": round(float(np.median(ray_errs)), 6),
            "max_abs_ray_err_thz": round(float(np.max(ray_errs)), 6),
            "median_max_residual_force_eV_A": round(float(np.median([r["max_residual_force_eV_A"] for r in records])), 6),
            "n_high_residual_force_gt_0p05": sum(1 for r in records if r["max_residual_force_eV_A"] > 0.05),
        },
        "regime_counts_tau_025": {
            "mace_full_labels": dict(Counter(r["mace_full_label_025"] for r in records)),
            "dft_labels": dict(Counter(r["dft_label_025"] for r in records)),
            "n_coarse_flagged": len(coarse_flagged),
            "n_coarse_flagged_noncomm": sum(1 for r in coarse_flagged if not r["is_q_star_commensurate"]),
            "n_genuine_mace_false_instab": len(genuine_mace_false_instab),
            "n_noncomm_mace_false_instab": len(noncomm_mace_false_instab),
            "n_genuine_dft_false_instab": len(genuine_dft_false_instab),
            "n_coarse_missed_mace_neg": sum(1 for r in records if r["f_coarse_min_thz"] >= -TAU_MAIN and r["f_mace_full_min_thz"] < -TAU_MAIN),
            "n_coarse_missed_dft_neg": sum(1 for r in records if r["f_coarse_min_thz"] >= -TAU_MAIN and r["f_dft_min_thz"] < -TAU_MAIN),
        },
        "equal_budget_benchmarks_tau_025": bench,
        "tau_sensitivity_atom_evals": bench_tau_sens,
        "per_material_jsonl": jsonl_p.name,
        "per_material_sha256": sha256_file(jsonl_p),
    }
    sum_p = OUT_DIR / "stage1_selective_validation_summary.json"
    sum_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(f"\n=== STAGE-1 PILOT COMPLETE | PID={os.getpid()} | Wall={summary['wall_time_s']}s ===")
    print(f"Summary SHA256: {sha256_file(sum_p)}")
    print("Mechanics parity:", summary["mechanics_parity"])
    print("Regime counts (tau=0.25 THz):", summary["regime_counts_tau_025"])


if __name__ == "__main__":
    main()
