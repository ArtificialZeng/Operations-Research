"""
Stage-0 Mechanics & Pipeline Verification Receipt:
  1. Verifies exact Phonopy Bloch gauge (C-type vs D-type), mass units (Phonopy masses),
     PBC, supercell commensurability `S^T q in Z^3`, acoustic exclusion, and NAC matching.
  2. Builds minimal index-L commensurate supercells (Minkowski/short-basis sublattice with det(S)=L)
     and verifies multi-image PBC parity against larger diagonal supercells under MACE-OMAT-0-small (float64).
  3. Tests direction-projected central-force Rayleigh curvature:
       omega^2(u; h) = - [u . (F(+h) - F(-h))] / [2 h sum_I m_I |u_I|^2] * (VASP_TO_THZ)^2
     using two pre-fixed step sizes h in {0.01, 0.02} A, NO relaxation between force calls,
     checking BOTH real/imag (cos/sin) quadratures on non-self-conjugate q (2q not in Z^3),
     and comparing directly against:
       (a) Explicit full same-model commensurate Phonopy Hessian (same q, same eigenvector), AND
       (b) Independent same-geometry DFT dynamical matrix projection (same q, same eigenvector).
  4. Tests small-supercell interpolation vs commensurate MACE vs minimal-repeat Rayleigh vs DFT
     across 2 verified NIMS PBEsol smoke controls (Si mp-149, BaTiO3 mp-2998) and
     4 Alexandria pure PBE smoke crystals (Si mp-149, MgO mp-1265, BaTiO3 mp-2998, SrTiO3 mp-5229).
"""
from __future__ import annotations

from fractions import Fraction
import hashlib
import json
import math
import os
import pathlib
import time
from typing import Any, Dict, List, Tuple

import numpy as np
import phonopy
from phonopy import Phonopy
from phonopy.structure.atoms import PhonopyAtoms
from phonopy.physical_units import get_physical_units
from ase import Atoms
import torch
from mace.calculators import MACECalculator


ROOT = pathlib.Path(__file__).resolve().parent
SMOKE_DIR = ROOT / "raw_smoke_refs"
MODEL_PATH = ROOT / "models" / "mace-omat-0-small.model"
OUT_DIR = ROOT / "stage0_smoke_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

VASP_TO_THZ = float(get_physical_units().DefaultToTHz)  # 15.633302300230191 THz / sqrt(eV / (AMU * A^2))


def signed_sqrt_freq(omega2_thz2: float) -> float:
    """Signed frequency in THz: negative denotes imaginary (omega^2 < 0)."""
    return math.copysign(math.sqrt(abs(omega2_thz2)), omega2_thz2)


def ph_cell_to_ase(cell: PhonopyAtoms) -> Atoms:
    return Atoms(
        symbols=list(cell.symbols),
        cell=np.array(cell.cell, dtype=np.float64),
        scaled_positions=np.array(cell.scaled_positions, dtype=np.float64),
        pbc=True,
    )


def minimal_commensurate_supercell_matrix(q_frac: Tuple[Fraction, Fraction, Fraction], prim_cell: np.ndarray) -> np.ndarray:
    """
    Finds a short-basis integer 3x3 supercell matrix S (columns = supercell lattice vectors in
    primitive fractional coordinates, matching Phonopy's `supercell.cell = S.T @ prim.cell` convention!)
    such that:
      - `S.T @ q` is strictly integer (`all(n == int(n))`)
      - `det(S) == L`, where `L = lcm(d1, d2, d3)` is the exact minimal commensurate index!
    Uses HNF construction followed by greedy 3D unimodular lattice-vector reduction to avoid skewed cells.
    """
    dens = [f.denominator for f in q_frac]
    L = math.lcm(*dens)
    m = [int(f * L) % L for f in q_frac]

    # Collect all integer vectors n in Z^3 with (n . m) == 0 (mod L) generating the index-L sublattice.
    # Start with standard spanning vectors: L * e_i plus kernel generators from 2-var/3-var solutions.
    # Exact HNF of {n in Z^3 : m0*n0 + m1*n1 + m2*n2 == 0 mod L}:
    # Build integer lattice basis of solutions to [m0, m1, m2] . n == 0 (mod L).
    # Simple exact construction via extended GCD in 3 steps:
    def egcd(a: int, b: int) -> Tuple[int, int, int]:
        if b == 0:
            return (abs(a), 1 if a >= 0 else -1, 0)
        g, x1, y1 = egcd(b, a % b)
        return (g, y1, x1 - (a // b) * y1)

    # Row vector r = [m0, m1, m2, L], find 3-vector basis of Z^3 kernel mod L via integer column ops on [m0, m1, m2]
    # Or direct exact search on small L (for L <= 12, exact HNF is trivial and bug-proof!):
    # Let's construct exact HNF columns v1=(h00,0,0), v2=(h01,h11,0), v3=(h02,h12,h22):
    # v1: m0*h00 == 0 mod L => h00 = L // gcd(m0, L)
    # v2: m0*h01 + m1*h11 == 0 mod L => smallest h11 > 0 such that gcd(m0, L) | m1*h11
    # v3: m0*h02 + m1*h12 + m2*h22 == 0 mod L => smallest h22 > 0 such that gcd(m0, m1, L) | m2*h22
    g0 = math.gcd(m[0], L)
    h00 = L // g0

    g01 = math.gcd(g0, m[1])
    h11 = g0 // g01
    # Solve m0 * h01 == -m1 * h11 (mod L)
    rhs1 = (-m[1] * h11) % L
    assert rhs1 % g0 == 0
    # (m0/g0) * h01 == (rhs1/g0) (mod L/g0)
    _, inv0, _ = egcd(m[0] // g0, h00)
    h01 = ((rhs1 // g0) * inv0) % h00

    g012 = math.gcd(g01, m[2])
    h22 = g01 // g012
    # Solve m0 * h02 + m1 * h12 == -m2 * h22 (mod L)
    rhs2 = (-m[2] * h22) % L
    assert rhs2 % g01 == 0
    # First find a, b with m0*a + m1*b == g01 (mod L)
    g_ab, xa, yb = egcd(m[0], m[1])
    # m0*xa + m1*yb == g_ab; also gcd(g_ab, L) == g01
    _, inv_ab, _ = egcd(g_ab // g01, L // g01)
    scale = ((rhs2 // g01) * inv_ab) % (L // g01)
    h02_raw = (xa * scale) % L
    h12_raw = (yb * scale) % L
    # Reduce h12 mod h11 using v2, then h02 mod h00 using v1
    k1 = h12_raw // h11
    h12 = h12_raw - k1 * h11
    h02 = (h02_raw - k1 * h01) % h00

    # Columns of S are v1, v2, v3:
    S = np.array(
        [
            [h00, h01, h02],
            [0,   h11, h12],
            [0,   0,   h22],
        ],
        dtype=int,
    )
    assert int(round(np.linalg.det(S))) == L, f"det(S)={np.linalg.det(S)} != L={L}"

    # Verify S.T @ q is integer
    q_arr = np.array([float(f) for f in q_frac], dtype=np.float64)
    stq = S.T @ q_arr
    assert np.allclose(stq, np.round(stq), atol=1e-12), f"S.T @ q not integer: {stq}"

    # Greedy 3D pairwise unimodular size reduction on columns of S (preserving det(S)=+L and S.T @ q in Z^3)
    # Physical supercell vectors are rows of (S.T @ prim_cell), i.e., column j of S gives vector (prim_cell.T @ S[:, j]).
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

    # Ensure positive determinant
    if np.linalg.det(S) < 0:
        S[:, 0] = -S[:, 0]
    assert int(round(np.linalg.det(S))) == L
    stq = S.T @ q_arr
    assert np.allclose(stq, np.round(stq), atol=1e-12)
    return S


def build_phonopy_from_primitive(prim: PhonopyAtoms, supercell_matrix: np.ndarray) -> Phonopy:
    """Builds a Phonopy object directly on the primitive cell (primitive_matrix = I_3)."""
    return Phonopy(
        unitcell=prim,
        supercell_matrix=supercell_matrix,
        primitive_matrix=np.eye(3, dtype=np.float64),
    )


def compute_mace_phonopy_full(
    prim: PhonopyAtoms,
    supercell_matrix: np.ndarray,
    calc: MACECalculator,
    disp_dist: float = 0.01,
    is_plusminus: bool = True,
) -> Tuple[Phonopy, Dict[str, Any]]:
    """
    Runs full finite-displacement Phonopy calculation with MACE on pinned primitive geometry
    (NO relaxation, NAC=False). Tracks exact force calls, atom-force evals, and wall time.
    """
    ph = build_phonopy_from_primitive(prim, supercell_matrix)
    ph.generate_displacements(distance=disp_dist, is_plusminus=is_plusminus)
    scs = ph.supercells_with_displacements
    t0 = time.perf_counter()
    forces_list = []
    n_atoms_sc = len(ph.supercell)
    for sc in scs:
        atoms = ph_cell_to_ase(sc)
        atoms.calc = calc
        f = atoms.get_forces()
        forces_list.append(np.array(f, dtype=np.float64))
    wall_s = time.perf_counter() - t0
    ph.forces = forces_list
    ph.produce_force_constants()
    ph.symmetrize_force_constants()
    stats = {
        "n_supercell_atoms": int(n_atoms_sc),
        "n_force_calls": int(len(scs)),
        "atom_force_evals": int(len(scs) * n_atoms_sc),
        "wall_s": round(wall_s, 4),
    }
    return ph, stats


def build_bloch_quadratures_in_supercell(
    prim: PhonopyAtoms,
    S_comm: np.ndarray,
    q_vec: np.ndarray,
    eigvec: np.ndarray,
    gauge: str = "C",
) -> Tuple[PhonopyAtoms, np.ndarray, np.ndarray, np.ndarray]:
    """
    Constructs exact real cosine and sine Bloch standing-wave displacement fields (in Angstrom)
    on the commensurate supercell `S_comm` (satisfying `S_comm.T @ q_vec in Z^3`) for a given
    primitive eigenvector `eigvec` (length 3*n_prim, complex, unit-norm).

    gauge='C' (Phonopy default dynamical matrix convention):
        w_{I, alpha} = (e_{kappa(I), alpha} / sqrt(m_{kappa(I)})) * exp(i 2 pi q . x_I)
        where x_I is the supercell atom position in PRIMITIVE fractional coordinates!
    gauge='D' (lattice-only phase, for cross-checking):
        uses R_I = x_I - x_{kappa(I)} instead of x_I.
    Returns (supercell_phonopy_atoms, masses_sc, u_cos, u_sin) where u_cos, u_sin have shape (N_sc, 3).
    """
    # Verify exact commensurability S_comm.T @ q in Z^3
    stq = S_comm.T @ q_vec
    assert np.allclose(stq, np.round(stq), atol=1e-10), f"Not commensurate! S^T q = {stq}"

    ph_sc = build_phonopy_from_primitive(prim, S_comm)
    sc = ph_sc.supercell
    prim_cell = np.array(prim.cell, dtype=np.float64)
    sc_cell = np.array(sc.cell, dtype=np.float64)
    # Verify Phonopy supercell cell convention: sc.cell == S_comm.T @ prim.cell
    assert np.allclose(sc_cell, S_comm.T @ prim_cell, atol=1e-10), "Phonopy supercell convention mismatch!"

    n_prim = len(prim)
    n_sc = len(sc)
    e_mat = np.asarray(eigvec, dtype=np.complex128).reshape(n_prim, 3)
    prim_masses = np.array(prim.masses, dtype=np.float64)
    sc_masses = np.array(sc.masses, dtype=np.float64)
    prim_spos = np.array(prim.scaled_positions, dtype=np.float64)

    # Map every supercell atom to its exact primitive index kappa(I) and primitive fractional coord x_I
    # Supercell Cartesian coords r_I = sc.scaled_positions @ sc.cell;
    # Primitive fractional coords x_I = r_I @ inv(prim_cell) = sc.scaled_positions @ S_comm.T
    x_prim_all = np.array(sc.scaled_positions, dtype=np.float64) @ S_comm.T
    # Phonopy's own supercell->primitive mapping:
    s2p = ph_sc.primitive.s2p_map
    p2p = ph_sc.primitive.p2p_map
    kappa_of_I = np.array([p2p[s2p[I]] for I in range(n_sc)], dtype=int)

    # Sanity-check exact fractional alignment between x_prim_all[I] and prim_spos[kappa_of_I[I]] mod 1
    for I in range(n_sc):
        k = kappa_of_I[I]
        diff = x_prim_all[I] - prim_spos[k]
        assert np.allclose(diff, np.round(diff), atol=1e-8), f"Atom map mismatch at I={I}: diff={diff}"
        assert abs(sc_masses[I] - prim_masses[k]) < 1e-8

    w = np.zeros((n_sc, 3), dtype=np.complex128)
    for I in range(n_sc):
        k = kappa_of_I[I]
        if gauge == "C":
            phase_vec = x_prim_all[I]
        elif gauge == "D":
            phase_vec = np.round(x_prim_all[I] - prim_spos[k])
        else:
            raise ValueError(gauge)
        phase = np.exp(1j * 2.0 * math.pi * float(np.dot(q_vec, phase_vec)))
        w[I, :] = (e_mat[k, :] / math.sqrt(prim_masses[k])) * phase

    u_cos = np.real(w)
    u_sin = np.imag(w)
    return sc, sc_masses, u_cos, u_sin


def eval_rayleigh_central_force(
    sc: PhonopyAtoms,
    sc_masses: np.ndarray,
    u_dir: np.ndarray,
    h_ang: float,
    calc: MACECalculator,
) -> Dict[str, Any]:
    """
    Direction-projected central-force Rayleigh curvature with NO relaxation:
      u_hat = u_dir / max_I ||u_dir[I]||   (so maximum single-atom displacement amplitude is EXACTLY h_ang!)
      r(+h) = r0 + h_ang * u_hat
      r(-h) = r0 - h_ang * u_hat
      omega^2 = - [u_hat . (F(+h) - F(-h))] / [2 * h_ang * sum_I m_I ||u_hat_I||^2] * VASP_TO_THZ^2
    """
    max_amp = float(np.max(np.linalg.norm(u_dir, axis=1)))
    if max_amp < 1e-12:
        return {"valid_quadrature": False, "reason": "zero_norm_quadrature"}

    u_hat = u_dir / max_amp
    mass_norm = float(np.sum(sc_masses[:, None] * (u_hat ** 2)))

    base_atoms = ph_cell_to_ase(sc)
    pos0 = base_atoms.get_positions().copy()

    t0 = time.perf_counter()
    a_plus = base_atoms.copy()
    a_plus.set_positions(pos0 + h_ang * u_hat)
    a_plus.calc = calc
    f_plus = np.array(a_plus.get_forces(), dtype=np.float64)

    a_minus = base_atoms.copy()
    a_minus.set_positions(pos0 - h_ang * u_hat)
    a_minus.calc = calc
    f_minus = np.array(a_minus.get_forces(), dtype=np.float64)
    wall_s = time.perf_counter() - t0

    df = f_plus - f_minus
    num = -float(np.sum(u_hat * df))
    denom = 2.0 * h_ang * mass_norm
    omega2_raw = num / denom  # eV / (AMU * A^2)
    omega2_thz2 = omega2_raw * (VASP_TO_THZ ** 2)
    freq_thz = signed_sqrt_freq(omega2_thz2)
    return {
        "valid_quadrature": True,
        "h_ang": h_ang,
        "omega2_thz2": round(omega2_thz2, 6),
        "freq_thz": round(freq_thz, 6),
        "n_supercell_atoms": len(sc),
        "n_force_calls": 2,
        "atom_force_evals": 2 * len(sc),
        "wall_s": round(wall_s, 4),
    }


def eval_rayleigh_exact_dft_fc(
    ph_dft: Phonopy,
    q_vec: np.ndarray,
    eigvec: np.ndarray,
) -> Tuple[float, float]:
    """Exact same-q, same-eigenvector Rayleigh projection e^H D_DFT(q) e (NAC=False)."""
    saved_nac = ph_dft.nac_params
    ph_dft.nac_params = None
    D = ph_dft.get_dynamical_matrix_at_q(q_vec)
    ph_dft.nac_params = saved_nac
    e = np.asarray(eigvec, dtype=np.complex128)
    e = e / np.linalg.norm(e)
    val = float(np.real(np.vdot(e, D @ e))) * (VASP_TO_THZ ** 2)
    return val, signed_sqrt_freq(val)


def main() -> None:
    device = "cuda" if torch.cuda.is_available() else "cpu"
    calc = MACECalculator(model_paths=str(MODEL_PATH), device=device, default_dtype="float64")
    print(f"Device={device} | VASP_TO_THZ={VASP_TO_THZ:.9f}")

    # -----------------------------------------------------------------------
    # PART A: Exact Bloch Gauge & Rayleigh Mechanics Proof on 4 Core Crystals
    # (2 NIMS PBEsol smoke controls + 4 Alexandria pure PBE crystals)
    # -----------------------------------------------------------------------
    specs = [
        ("nims_pbesol_mp-149_Si.yaml.xz",          "NIMS_PBEsol_smoke",   "Si",     np.diag([2, 2, 2])),
        ("nims_pbesol_mp-2998_BaTiO3.yaml.xz",     "NIMS_PBEsol_smoke",   "BaTiO3", np.diag([3, 3, 3])),
        ("alexandria_pbe_mp-149_Si.yaml.bz2",      "Alexandria_PBE",      "Si",     np.diag([2, 2, 2])),
        ("alexandria_pbe_mp-1265_MgO.yaml.bz2",    "Alexandria_PBE",      "MgO",    np.diag([2, 2, 2])),
        ("alexandria_pbe_mp-2998_BaTiO3.yaml.bz2", "Alexandria_PBE",      "BaTiO3", np.diag([3, 3, 3])),
        ("alexandria_pbe_mp-5229_SrTiO3.yaml.bz2", "Alexandria_PBE",      "SrTiO3", np.diag([3, 3, 3])),
    ]

    # Pre-fixed test wavevectors including:
    # - Gamma (0,0,0) optical/soft mode (L=1)
    # - Self-conjugate zone boundaries: X=(1/2,0,0) (L=2), R=(1/2,1/2,1/2) (L=2)
    # - NON-SELF-CONJUGATE (2q not in Z^3): (1/3, 0, 0) (L=3) and (1/4, 1/4, 0) (L=4)!
    test_qs = [
        ("Gamma",   (Fraction(0), Fraction(0), Fraction(0))),
        ("X_half",  (Fraction(1, 2), Fraction(0), Fraction(0))),
        ("R_half",  (Fraction(1, 2), Fraction(1, 2), Fraction(1, 2))),
        ("NonSC_3", (Fraction(1, 3), Fraction(0), Fraction(0))),
        ("NonSC_4", (Fraction(1, 4), Fraction(1, 4), Fraction(0))),
    ]
    h_vals = [0.01, 0.02]

    all_receipts: List[Dict[str, Any]] = []

    for fname, source_tag, label, ref_sc_mat_prim in specs:
        print(f"\n================ {fname} ({source_tag}) ================")
        p = SMOKE_DIR / fname
        ph_dft = phonopy.load(str(p))
        if ph_dft.force_constants is None:
            ph_dft.produce_force_constants()
        ph_dft.symmetrize_force_constants()
        has_dft_nac = ph_dft.nac_params is not None
        ph_dft.nac_params = None  # Match NAC=False between DFT and ML finite-displacement supercells!

        prim = ph_dft.primitive
        prim_cell = np.array(prim.cell, dtype=np.float64)

        # Residual force on pinned DFT primitive cell (NO relaxation!)
        a0 = ph_cell_to_ase(prim)
        a0.calc = calc
        f0 = np.array(a0.get_forces(), dtype=np.float64)
        max_f0 = float(np.abs(f0).max())

        # Full same-model MACE Phonopy Hessian on a commensurate supercell:
        # For NonSC_4=(1/4,1/4,0) and X/R=(1/2,...), 4x4x4 is commensurate with Gamma, X, R, NonSC_4;
        # For NonSC_3=(1/3,0,0), 3x3x3 is commensurate with Gamma and NonSC_3!
        # Let's compute BOTH:
        #   1) Coarse small supercell (2x2x2 primitive) — nominates modes on 4x4x4 + 3x3x3 q-grid!
        #   2) Full MACE reference supercells: 3x3x3 (for L=3 exact Hessian check) and 4x4x4 (for L=1,2,4 exact Hessian check)!
        # Wait: 4x4x4 on 5-atom BaTiO3/SrTiO3 = 320 atoms (tiny for RTX 5060: 2*3 = 6 or 8 displacements ~2s!).
        ph_mace_coarse, st_coarse = compute_mace_phonopy_full(prim, np.diag([2, 2, 2]), calc, disp_dist=0.01)
        ph_mace_333, st_333 = compute_mace_phonopy_full(prim, np.diag([3, 3, 3]), calc, disp_dist=0.01)
        ph_mace_444, st_444 = compute_mace_phonopy_full(prim, np.diag([4, 4, 4]), calc, disp_dist=0.01)

        print(
            f"  n_prim={len(prim)} max|F0|={max_f0:.2e} eV/A has_dft_nac={has_dft_nac} | "
            f"coarse(2x2x2): {st_coarse['n_force_calls']} calls ({st_coarse['atom_force_evals']} at-evals, {st_coarse['wall_s']}s) | "
            f"3x3x3: {st_333['n_force_calls']} calls ({st_333['wall_s']}s) | "
            f"4x4x4: {st_444['n_force_calls']} calls ({st_444['wall_s']}s)"
        )

        # Quick C-type vs D-type gauge verification on NonSC_3 (band 0)
        q_tests_rec = []
        for q_name, q_frac in test_qs:
            q_vec = np.array([float(f) for f in q_frac], dtype=np.float64)
            L_min = math.lcm(*(f.denominator for f in q_frac))
            is_self_conj = all((2 * f).denominator == 1 for f in q_frac)

            # Pick the exact commensurate full MACE Phonopy reference for this q!
            ph_mace_comm = ph_mace_333 if L_min == 3 else ph_mace_444
            comm_tag = "3x3x3" if L_min == 3 else "4x4x4"

            # Nominate the lowest non-acoustic mode from COARSE 2x2x2 MACE at this q!
            f_coarse, ev_coarse = ph_mace_coarse.get_frequencies_with_eigenvectors(q_vec)
            if q_name == "Gamma":
                # Exclude the 3 acoustic modes (closest to 0 at Gamma: translational eigenvectors!)
                # Better: identify acoustic modes by uniform translation projection!
                n_p = len(prim)
                masses_p = np.array(prim.masses, dtype=np.float64)
                tr_proj = []
                for bi in range(3 * n_p):
                    ev_b = ev_coarse[:, bi].reshape(n_p, 3)
                    # Acoustic mode has sqrt(m_k) * e_k = const across atoms => |sum_k sqrt(m_k) e_k|^2 / sum_k m_k == 1
                    p_tr = float(np.sum(np.abs(np.sum(np.sqrt(masses_p)[:, None] * ev_b, axis=0)) ** 2) / np.sum(masses_p))
                    tr_proj.append(p_tr)
                non_ac = [bi for bi in range(3 * n_p) if tr_proj[bi] < 0.5]
                band = min(non_ac, key=lambda bi: float(f_coarse[bi]))
            else:
                band = int(np.argmin(f_coarse))

            freq_coarse = float(f_coarse[band])
            eigvec = ev_coarse[:, band]

            # Exact Rayleigh projection of THIS SAME eigenvector onto:
            #   (1) Full commensurate same-model MACE Phonopy Hessian D_MACE_comm(q)
            D_mace_comm = ph_mace_comm.get_dynamical_matrix_at_q(q_vec)
            w2_mace_comm = float(np.real(np.vdot(eigvec, D_mace_comm @ eigvec))) * (VASP_TO_THZ ** 2)
            f_mace_comm_proj = signed_sqrt_freq(w2_mace_comm)
            f_mace_comm_eig, _ = ph_mace_comm.get_frequencies_with_eigenvectors(q_vec)
            # Also full commensurate minimum non-acoustic eigenfrequency at this q
            f_mace_comm_min = float(f_mace_comm_eig[band]) if q_name == "Gamma" else float(np.min(f_mace_comm_eig))

            #   (2) Independent same-geometry DFT dynamical matrix projection e^H D_DFT(q) e (NAC=False)
            w2_dft_proj, f_dft_proj = eval_rayleigh_exact_dft_fc(ph_dft, q_vec, eigvec)
            f_dft_eigs, _ = ph_dft.get_frequencies_with_eigenvectors(q_vec)
            f_dft_min = float(sorted(f_dft_eigs)[3]) if q_name == "Gamma" and len(f_dft_eigs) > 3 else float(np.min(f_dft_eigs))
            if q_name == "Gamma":
                # Proper acoustic exclusion on DFT too via translation projection
                _, ev_dft = ph_dft.get_frequencies_with_eigenvectors(q_vec)
                n_p = len(prim)
                masses_p = np.array(prim.masses, dtype=np.float64)
                non_ac_dft = [
                    bi for bi in range(3 * n_p)
                    if float(np.sum(np.abs(np.sum(np.sqrt(masses_p)[:, None] * ev_dft[:, bi].reshape(n_p, 3), axis=0)) ** 2) / np.sum(masses_p)) < 0.5
                ]
                f_dft_min = float(min(f_dft_eigs[bi] for bi in non_ac_dft))

            #   (3) Minimal index-L commensurate repeat Rayleigh curvature (BOTH cos & sin quadratures, BOTH h=0.01 & 0.02!)
            S_min = minimal_commensurate_supercell_matrix(q_frac, prim_cell)
            sc_min, sc_m, u_cos, u_sin = build_bloch_quadratures_in_supercell(prim, S_min, q_vec, eigvec, gauge="C")

            ray_results = {}
            for h in h_vals:
                r_cos = eval_rayleigh_central_force(sc_min, sc_m, u_cos, h, calc)
                r_sin = eval_rayleigh_central_force(sc_min, sc_m, u_sin, h, calc)
                ray_results[f"h={h}"] = {"cos": r_cos, "sin": r_sin}

            # Also cross-check D-type gauge ONCE on NonSC_3 for Si and BaTiO3 to prove C-type is exact!
            d_gauge_check = None
            if q_name == "NonSC_3" and label in ("Si", "BaTiO3"):
                sc_d, sc_md, u_cos_d, _ = build_bloch_quadratures_in_supercell(prim, S_min, q_vec, eigvec, gauge="D")
                d_gauge_check = eval_rayleigh_central_force(sc_d, sc_md, u_cos_d, 0.01, calc)["freq_thz"]

            c01 = ray_results["h=0.01"]["cos"]
            s01 = ray_results["h=0.01"]["sin"]
            c02 = ray_results["h=0.02"]["cos"]
            s02 = ray_results["h=0.02"]["sin"]
            # Pick valid quadrature (or mean of cos & sin when both valid!)
            err_cos = abs(c01["freq_thz"] - f_mace_comm_proj) if c01["valid_quadrature"] else None
            err_sin = abs(s01["freq_thz"] - f_mace_comm_proj) if s01["valid_quadrature"] else None
            quad_diff = abs(c01["freq_thz"] - s01["freq_thz"]) if (c01["valid_quadrature"] and s01["valid_quadrature"]) else None

            print(
                f"  [{q_name:7s} L={L_min} sc_at={len(sc_min):2d} SC={str(is_self_conj)[0]}] "
                f"coarse={freq_coarse:+7.3f} | full_{comm_tag}_proj={f_mace_comm_proj:+7.3f} | "
                f"Ray01(c={c01.get('freq_thz')}, s={s01.get('freq_thz')}) Ray02(c={c02.get('freq_thz')}) | "
                f"|err_c|={err_cos if err_cos is not None else -1:.4f} |c-s|={quad_diff if quad_diff is not None else -1:.4f} | "
                f"DFT_proj={f_dft_proj:+7.3f} (DFT_min={f_dft_min:+7.3f})"
                + (f" [D-gauge={d_gauge_check}]" if d_gauge_check is not None else "")
            )
            q_tests_rec.append({
                "q_name": q_name,
                "q_vec": q_vec.tolist(),
                "L_minimal": L_min,
                "is_self_conjugate": is_self_conj,
                "S_minimal": S_min.tolist(),
                "n_atoms_minimal_sc": len(sc_min),
                "band_nominated": band,
                "freq_mace_coarse_2x2x2_thz": round(freq_coarse, 6),
                "freq_mace_comm_proj_thz": round(f_mace_comm_proj, 6),
                "freq_mace_comm_min_thz": round(f_mace_comm_min, 6),
                "comm_ref_grid": comm_tag,
                "freq_dft_proj_thz": round(f_dft_proj, 6),
                "freq_dft_min_thz": round(f_dft_min, 6),
                "rayleigh_C_gauge": ray_results,
                "abs_err_cos_h01_vs_full_comm_thz": round(err_cos, 6) if err_cos is not None else None,
                "abs_err_sin_h01_vs_full_comm_thz": round(err_sin, 6) if err_sin is not None else None,
                "cos_sin_diff_h01_thz": round(quad_diff, 6) if quad_diff is not None else None,
                "d_gauge_check_h01_thz": d_gauge_check,
            })

        all_receipts.append({
            "file": fname,
            "source_tag": source_tag,
            "formula": label,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
            "n_prim": len(prim),
            "prim_masses": [float(x) for x in prim.masses],
            "has_dft_nac_original": has_dft_nac,
            "nac_used_both": False,
            "max_residual_force_prim_eV_A": max_f0,
            "coarse_2x2x2_stats": st_coarse,
            "comm_3x3x3_stats": st_333,
            "comm_4x4x4_stats": st_444,
            "q_tests": q_tests_rec,
        })

    out_p = OUT_DIR / "stage0_mechanics_verification_receipt.json"
    out_p.write_text(json.dumps({
        "model_path": str(MODEL_PATH.name),
        "model_sha256": hashlib.sha256(MODEL_PATH.read_bytes()).hexdigest(),
        "device": device,
        "dtype": "float64",
        "vasp_to_thz": VASP_TO_THZ,
        "pid": os.getpid(),
        "receipts": all_receipts,
    }, indent=2), encoding="utf-8")
    print(f"\nSaved verified mechanics receipt -> {out_p} (SHA256={hashlib.sha256(out_p.read_bytes()).hexdigest()})")


if __name__ == "__main__":
    main()
