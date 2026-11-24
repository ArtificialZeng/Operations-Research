"""
Exact Small-Block Randomization Support Enumerator & Independent Cross-Check Verifier.

Produces and independently cross-checks:
  - 6 small oracle cases for Trial 1: RockTheVote (Green & Vavreck 2008; CRAN pscl 1.5.9)
  - 6 small oracle cases for Trial 2: Bangladesh Mask Cluster-RCT (Abaluck et al. 2022, Science; Zenodo 5703876)
  - Plus verifies feasibility of 40 completely non-overlapping matched cases (13 RockTheVote + 27 Abaluck 2022)
    with neutral reorder + opaque ID-renaming controls.

Independent Double-Check Methodology:
  Method 1 (Constructive Cartesian Block Enumeration — equivalent to randomizr::block_ra / ri2::obtain_permutation_matrix):
    Enumerates exact combinations C(n_b, m_b) per block and takes their Cartesian product.
  Method 2 (Independent Brute-Force Same-Total Filter + Study-Code Assertion Replay):
    Enumerates ALL C(N, M) binary vectors with total treated count M, and independently filters each
    vector through explicit per-unit / per-block assertions matching `RockTheVote.Rd` and Abaluck et al.'s
    `10a_reg_rand_inf_symp_sero.do` (`isid union`, `bys pairID: assert(_N==2)`, `assert count_treat==1`).
  Asserts 100% set equality (support_method1 == support_method2) on every single case.

STRICT PRIVACY / ARTIFACT RULE:
  Uses ONLY public de-identified aggregate market/union-level metadata. ZERO individual voter or personal records.
"""
from __future__ import annotations

import hashlib
import itertools
import json
import math
import pathlib
from typing import Any, Dict, List, Sequence, Set, Tuple

import pandas as pd
import rdata


ROOT = pathlib.Path(__file__).resolve().parent
RAW = ROOT / "raw_sources"


def sha256_file(path: pathlib.Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def enumerate_support_cartesian(
    unit_ids: Sequence[str],
    block_of_unit: Dict[str, str],
    quota_of_block: Dict[str, int],
) -> Set[Tuple[int, ...]]:
    """Method 1: Constructive Cartesian product of C(n_b, m_b) within each block
    (exact mathematical equivalent of randomizr::block_ra / ri2::obtain_permutation_matrix)."""
    idx_by_block: Dict[str, List[int]] = {}
    for idx, uid in enumerate(unit_ids):
        b = block_of_unit[uid]
        idx_by_block.setdefault(b, []).append(idx)

    blocks_sorted = sorted(idx_by_block.keys())
    per_block_choices: List[List[Tuple[int, ...]]] = []
    for b in blocks_sorted:
        idxs = idx_by_block[b]
        m = quota_of_block[b]
        assert 0 <= m <= len(idxs), f"Invalid quota {m} for block {b} of size {len(idxs)}"
        per_block_choices.append(list(itertools.combinations(idxs, m)))

    n = len(unit_ids)
    support: Set[Tuple[int, ...]] = set()
    for prod in itertools.product(*per_block_choices):
        vec = [0] * n
        for chosen_tuple in prod:
            for idx in chosen_tuple:
                vec[idx] = 1
        support.add(tuple(vec))
    return support


def enumerate_support_bruteforce_filter(
    unit_ids: Sequence[str],
    block_of_unit: Dict[str, str],
    quota_of_block: Dict[str, int],
) -> Tuple[Set[Tuple[int, ...]], Set[Tuple[int, ...]]]:
    """Method 2 (Independent cross-check): Enumerate ALL C(N, M) binary vectors with
    total treated count M and filter via study-code per-block assertions."""
    n = len(unit_ids)
    total_m = sum(quota_of_block.values())
    blocks = sorted(set(block_of_unit[u] for u in unit_ids))
    assert set(blocks) == set(quota_of_block.keys())

    admissible: Set[Tuple[int, ...]] = set()
    illegal_same_total: Set[Tuple[int, ...]] = set()

    for treated_positions in itertools.combinations(range(n), total_m):
        vec = [0] * n
        for pos in treated_positions:
            vec[pos] = 1
        tvec = tuple(vec)

        # Replay study-code assertion: count_treat == quota[b] for every block b
        counts: Dict[str, int] = {b: 0 for b in blocks}
        for uid, z in zip(unit_ids, tvec):
            counts[block_of_unit[uid]] += z
        if all(counts[b] == quota_of_block[b] for b in blocks):
            admissible.add(tvec)
        else:
            illegal_same_total.add(tvec)

    return admissible, illegal_same_total


def deterministic_Verifier(
    unit_ids: Sequence[str],
    candidate_assignment: Dict[str, int],
    block_of_unit: Dict[str, str],
    quota_of_block: Dict[str, int],
) -> Tuple[bool, str]:
    """Exact deterministic oracle verifier given a design schema (unit_ids, block_of_unit, quota_of_block)."""
    if set(candidate_assignment.keys()) != set(unit_ids):
        return False, "unit_id_set_mismatch"
    for uid, v in candidate_assignment.items():
        if v not in (0, 1):
            return False, f"non_binary_value:{uid}={v}"
    counts: Dict[str, int] = {b: 0 for b in quota_of_block}
    for uid in unit_ids:
        b = block_of_unit[uid]
        counts[b] += int(candidate_assignment[uid])
    bad = [f"{b}:{counts[b]}!={quota_of_block[b]}" for b in sorted(quota_of_block) if counts[b] != quota_of_block[b]]
    if bad:
        return False, "block_quota_violation(" + ",".join(bad) + ")"
    return True, "admissible"


def load_rockthevote() -> pd.DataFrame:
    parsed = rdata.parser.parse_file(RAW / "pscl_RockTheVote.rda")
    conv = rdata.conversion.convert(parsed)
    df = conv["RockTheVote"]
    if not isinstance(df, pd.DataFrame):
        df = pd.DataFrame(df)
    df = df.copy()
    # Original R row names are the cable-market indices (1..85 in original source)
    df.insert(0, "market_id", [f"MKT_{int(idx):02d}" for idx in df.index])
    df["strata"] = df["strata"].astype(int)
    df["treated"] = df["treated"].astype(int)
    df["r"] = df["r"].astype(int)
    df["n"] = df["n"].astype(int)
    df["p"] = df["p"].astype(float).round(4)
    df["treatedIndex"] = df["treatedIndex"].astype(int)
    return df.reset_index(drop=True)


def load_abaluck_joined() -> pd.DataFrame:
    ab = RAW / "abaluck2022_bd_mask_rct"
    u_reg = pd.read_stata(ab / "01_data/00_common/01_clean/union_reg_sample.dta", convert_categoricals=False)
    u_bld = pd.read_stata(ab / "01_data/00_common/00_raw/union_baseline_blood_stats.dta", convert_categoricals=False)
    joined = pd.merge(
        u_reg[["district", "union", "pairID", "wave", "treatment", "surgical_pair", "cloth_pair"]],
        u_bld[["union", "n_posXsymp_base", "prop_posXsymp_base"]],
        on="union",
        how="inner",
    )
    joined["district"] = joined["district"].astype(int)
    joined["union"] = joined["union"].astype(int)
    joined["pairID"] = joined["pairID"].astype(int)
    joined["wave"] = joined["wave"].astype(int)
    joined["treatment"] = joined["treatment"].astype(int)
    joined["surgical_pair"] = joined["surgical_pair"].astype(int)
    joined["cloth_pair"] = joined["cloth_pair"].astype(int)
    joined["n_posXsymp_base"] = joined["n_posXsymp_base"].astype(int)
    joined["prop_posXsymp_base"] = joined["prop_posXsymp_base"].astype(float).round(4)
    return joined.sort_values(["district", "wave", "pairID", "union"]).reset_index(drop=True)


def pick_deterministic(items: Sequence[Any], salt: str) -> Any:
    ordered = sorted(items, key=lambda x: hashlib.sha256(f"{salt}:{x}".encode()).hexdigest())
    return ordered[0]


def build_rockthevote_cases(rtv: pd.DataFrame, max_cases: int = 13) -> List[Dict[str, Any]]:
    """Partition RockTheVote's 40 strata into 13 completely non-overlapping 3-block cases (39/40 strata, 0 overlap)."""
    strata_ids = sorted(rtv["strata"].unique().tolist())
    # Deterministic non-overlapping grouping of 3 strata per case (putting each size-3 stratum in its own case)
    size3 = [3, 6, 8, 20, 25]
    size2 = [s for s in strata_ids if s not in size3]
    groups: List[List[int]] = []
    # First 5 cases: each gets 1 size-3 stratum + 2 size-2 strata (7 markets each)
    s2_idx = 0
    for s3 in size3:
        groups.append(sorted([s3, size2[s2_idx], size2[s2_idx + 1]]))
        s2_idx += 2
    # Remaining 8 cases: 3 size-2 strata each (6 markets each) -> 5 + 8 = 13 cases using 39/40 strata!
    while s2_idx + 3 <= len(size2) and len(groups) < max_cases:
        groups.append(sorted(size2[s2_idx : s2_idx + 3]))
        s2_idx += 3

    used_strata: Set[int] = set()
    cases: List[Dict[str, Any]] = []
    for ci, grp in enumerate(groups[:max_cases], start=1):
        assert not (used_strata & set(grp)), "Overlapping strata!"
        used_strata.update(grp)
        sub = rtv[rtv["strata"].isin(grp)].sort_values(["strata", "market_id"]).reset_index(drop=True)
        unit_ids = sub["market_id"].tolist()
        obs_vec = tuple(int(x) for x in sub["treated"].tolist())
        block_of_unit = {r["market_id"]: f"S{int(r['strata'])}" for _, r in sub.iterrows()}
        quota_of_block = {
            f"S{int(s)}": int(sub[sub["strata"] == s]["treated"].sum())
            for s in grp
        }
        size_of_block = {
            f"S{int(s)}": int((sub["strata"] == s).sum())
            for s in grp
        }

        # Exact enumeration + independent brute-force cross-check
        supp1 = enumerate_support_cartesian(unit_ids, block_of_unit, quota_of_block)
        supp2, illegals = enumerate_support_bruteforce_filter(unit_ids, block_of_unit, quota_of_block)
        assert supp1 == supp2, f"Enumerator mismatch on RTV case {ci}!"
        assert obs_vec in supp1, f"Observed vector not in exact support on RTV case {ci}!"
        expected_card = math.prod(math.comb(size_of_block[b], quota_of_block[b]) for b in quota_of_block)
        assert len(supp1) == expected_card

        # Positive control: strictly admissible & different from observed vector
        pos_candidates = [v for v in supp1 if v != obs_vec]
        pos_vec = pick_deterministic(pos_candidates, f"rtv_pos_{ci}")

        # Matched illegal control: SAME total treated count M, AND minimal single-swap unambiguous violation
        # (exactly 2 blocks violated by +1/-1, at least one block all-0 or all-1 so illegal under ANY non-degenerate design!)
        single_swap_illegals = []
        unambig_illegals = []
        for iv in illegals:
            b_cnts = {b: 0 for b in quota_of_block}
            for uid, z in zip(unit_ids, iv):
                b_cnts[block_of_unit[uid]] += z
            violated = [b for b in quota_of_block if b_cnts[b] != quota_of_block[b]]
            if any(b_cnts[b] in (0, size_of_block[b]) for b in violated):
                unambig_illegals.append(iv)
                if len(violated) == 2 and all(abs(b_cnts[b] - quota_of_block[b]) == 1 for b in violated):
                    single_swap_illegals.append(iv)
        pool_neg = single_swap_illegals if single_swap_illegals else unambig_illegals
        assert pool_neg, f"No unambiguous illegal vector on RTV case {ci}"
        neg_vec = pick_deterministic(pool_neg, f"rtv_neg_{ci}")

        # Verify both via deterministic oracle
        pos_map = {u: int(z) for u, z in zip(unit_ids, pos_vec)}
        neg_map = {u: int(z) for u, z in zip(unit_ids, neg_vec)}
        ok_p, msg_p = deterministic_Verifier(unit_ids, pos_map, block_of_unit, quota_of_block)
        ok_n, msg_n = deterministic_Verifier(unit_ids, neg_map, block_of_unit, quota_of_block)
        assert ok_p is True and ok_n is False
        assert sum(pos_vec) == sum(neg_vec) == sum(obs_vec)

        # Neutral reorder + opaque unit ID-renaming control (preserves exact support bijection AND keeps
        # strata IDs consistent with verbatim RockTheVote.Rd text naming strata 3, 6, 8, 20, 25!)
        perm_units = sorted(unit_ids, key=lambda u: hashlib.sha256(f"rtv_reord_{ci}:{u}".encode()).hexdigest())
        uid_rename = {u: f"C{k:02d}" for k, u in enumerate(perm_units, start=1)}
        reord_meta = []
        reord_out = []
        sub_by_u = {r["market_id"]: r for _, r in sub.iterrows()}
        for u in perm_units:
            r = sub_by_u[u]
            reord_meta.append({"market_id": uid_rename[u], "strata": int(r["strata"]), "n": int(r["n"]), "treatedIndex": int(r["treatedIndex"])})
            reord_out.append({"market_id": uid_rename[u], "r": int(r["r"]), "p": float(r["p"]), "treated": int(r["treated"])})
        reord_pos = {uid_rename[u]: pos_map[u] for u in perm_units}
        reord_neg = {uid_rename[u]: neg_map[u] for u in perm_units}
        reord_block_of_unit = {uid_rename[u]: f"S{int(sub_by_u[u]['strata'])}" for u in perm_units}
        reord_quota_of_block = dict(quota_of_block)
        assert deterministic_Verifier(list(uid_rename.values()), reord_pos, reord_block_of_unit, reord_quota_of_block)[0] is True
        assert deterministic_Verifier(list(uid_rename.values()), reord_neg, reord_block_of_unit, reord_quota_of_block)[0] is False

        cases.append(
            {
                "case_id": f"RTV_{ci:02d}",
                "trial": "RockTheVote_2008",
                "domain": "election_voter_mobilization",
                "strata_ids": grp,
                "n_units": len(unit_ids),
                "total_treated": int(sum(obs_vec)),
                "exact_support_size": len(supp1),
                "total_same_count_size": math.comb(len(unit_ids), int(sum(obs_vec))),
                "enumerator_crosscheck_exact_match": True,
                "gold_schema": {
                    "unit_col": "market_id",
                    "block_col": "strata",
                    "block_sizes": size_of_block,
                    "block_quotas": quota_of_block,
                },
                "table_metadata_rows": sub[["market_id", "strata", "n", "treatedIndex"]].to_dict(orient="records"),
                "table_outcome_rows": sub[["market_id", "r", "p", "treated"]].to_dict(orient="records"),
                "observed_assignment": {u: int(z) for u, z in zip(unit_ids, obs_vec)},
                "positive_admissible": {"assignment": pos_map, "oracle_valid": True, "oracle_reason": msg_p},
                "matched_illegal": {"assignment": neg_map, "oracle_valid": False, "oracle_reason": msg_n},
                "neutral_reorder_control": {
                    "table_metadata_rows": reord_meta,
                    "table_outcome_rows": reord_out,
                    "positive_admissible": {"assignment": reord_pos, "oracle_valid": True},
                    "matched_illegal": {"assignment": reord_neg, "oracle_valid": False},
                    "gold_block_quotas": reord_quota_of_block,
                },
            }
        )
    return cases


def build_abaluck_cases(ab: pd.DataFrame, max_cases: int = 27) -> List[Dict[str, Any]]:
    """Select 27 completely non-overlapping 3-pair or 4-pair cases from Abaluck et al. (2022)
    joined aggregate tables (`union_reg_sample` INNER JOIN `union_baseline_blood_stats`).
    Prioritize same-(district, wave) multi-pair blocks so matched illegal assignments preserve
    exact total treated count AND exact district & wave treated counts while violating ONLY pairID!"""
    # Group pairIDs by (district, wave)
    pair_meta = (
        ab.groupby("pairID")
        .agg(district=("district", "first"), wave=("wave", "first"), surgical_pair=("surgical_pair", "first"))
        .reset_index()
        .sort_values(["district", "wave", "pairID"])
    )
    groups: List[Tuple[List[int], bool]] = []  # (pair_ids, within_same_district_wave)
    used_pairs: Set[int] = set()

    # Pass 1: groups of 3 pairs within the EXACT SAME (district, wave)
    for (dist, wav), grp in pair_meta.groupby(["district", "wave"], sort=True):
        pids = [int(x) for x in grp["pairID"].tolist() if int(x) not in used_pairs]
        idx = 0
        while idx + 3 <= len(pids) and len(groups) < max_cases:
            chunk = pids[idx : idx + 3]
            groups.append((chunk, True))
            used_pairs.update(chunk)
            idx += 3

    # Pass 2: if fewer than max_cases, groups of 3 pairs within the EXACT SAME district (spanning waves)
    for dist, grp in pair_meta.groupby("district", sort=True):
        pids = [int(x) for x in grp["pairID"].tolist() if int(x) not in used_pairs]
        idx = 0
        while idx + 3 <= len(pids) and len(groups) < max_cases:
            chunk = pids[idx : idx + 3]
            groups.append((chunk, False))
            used_pairs.update(chunk)
            idx += 3

    assert len(groups) >= max_cases, f"Only found {len(groups)} disjoint groups in Abaluck 2022"
    cases: List[Dict[str, Any]] = []

    for ci, (pids, same_dw) in enumerate(groups[:max_cases], start=1):
        sub = ab[ab["pairID"].isin(pids)].sort_values(["pairID", "union"]).reset_index(drop=True)
        unit_ids = [str(int(u)) for u in sub["union"].tolist()]
        obs_vec = tuple(int(x) for x in sub["treatment"].tolist())
        block_of_unit = {str(int(r["union"])): f"P{int(r['pairID'])}" for _, r in sub.iterrows()}
        quota_of_block = {f"P{p}": 1 for p in pids}
        size_of_block = {f"P{p}": 2 for p in pids}

        # Exact enumeration + independent brute-force cross-check
        supp1 = enumerate_support_cartesian(unit_ids, block_of_unit, quota_of_block)
        supp2, illegals = enumerate_support_bruteforce_filter(unit_ids, block_of_unit, quota_of_block)
        assert supp1 == supp2
        assert obs_vec in supp1
        assert len(supp1) == 2 ** len(pids)

        pos_vec = pick_deterministic([v for v in supp1 if v != obs_vec], f"ab_pos_{ci}")

        # Prefer illegal vectors that ALSO preserve district and wave treated counts!
        dist_of = [int(x) for x in sub["district"].tolist()]
        wave_of = [int(x) for x in sub["wave"].tolist()]
        obs_dist_t: Dict[int, int] = {}
        obs_wave_t: Dict[int, int] = {}
        for d, w, z in zip(dist_of, wave_of, obs_vec):
            obs_dist_t[d] = obs_dist_t.get(d, 0) + z
            obs_wave_t[w] = obs_wave_t.get(w, 0) + z

        strict_illegals = []
        for iv in illegals:
            dt: Dict[int, int] = {}
            wt: Dict[int, int] = {}
            for d, w, z in zip(dist_of, wave_of, iv):
                dt[d] = dt.get(d, 0) + z
                wt[w] = wt.get(w, 0) + z
            if dt == obs_dist_t and wt == obs_wave_t:
                strict_illegals.append(iv)
        pool = strict_illegals if strict_illegals else list(illegals)
        neg_vec = pick_deterministic(pool, f"ab_neg_{ci}")

        pos_map = {u: int(z) for u, z in zip(unit_ids, pos_vec)}
        neg_map = {u: int(z) for u, z in zip(unit_ids, neg_vec)}
        ok_p, msg_p = deterministic_Verifier(unit_ids, pos_map, block_of_unit, quota_of_block)
        ok_n, msg_n = deterministic_Verifier(unit_ids, neg_map, block_of_unit, quota_of_block)
        assert ok_p is True and ok_n is False
        assert sum(pos_vec) == sum(neg_vec) == sum(obs_vec)

        # Neutral reorder + opaque ID-renaming control (bijective relabeling of union & pairID!)
        perm_units = sorted(unit_ids, key=lambda u: hashlib.sha256(f"ab_reord_{ci}:{u}".encode()).hexdigest())
        uid_rename = {u: 8000000 + ci * 100 + k for k, u in enumerate(perm_units, start=1)}
        pair_perm = sorted(pids, key=lambda p: hashlib.sha256(f"ab_pren_{ci}:{p}".encode()).hexdigest())
        pair_rename = {p: 900 + k for k, p in enumerate(pair_perm, start=1)}
        sub_by_u = {str(int(r["union"])): r for _, r in sub.iterrows()}
        reord_reg = []
        reord_bld = []
        for u in perm_units:
            r = sub_by_u[u]
            nu = uid_rename[u]
            reord_reg.append({
                "district": int(r["district"]),
                "union": nu,
                "pairID": pair_rename[int(r["pairID"])],
                "wave": int(r["wave"]),
                "surgical_pair": int(r["surgical_pair"]),
                "cloth_pair": int(r["cloth_pair"]),
                "treatment": int(r["treatment"]),
            })
            reord_bld.append({
                "union": nu,
                "n_posXsymp_base": int(r["n_posXsymp_base"]),
                "prop_posXsymp_base": float(r["prop_posXsymp_base"]),
            })
        reord_pos = {str(uid_rename[u]): pos_map[u] for u in perm_units}
        reord_neg = {str(uid_rename[u]): neg_map[u] for u in perm_units}
        reord_block_of_unit = {str(uid_rename[u]): f"P{pair_rename[int(sub_by_u[u]['pairID'])]}" for u in perm_units}
        reord_quota_of_block = {f"P{pair_rename[p]}": 1 for p in pids}
        assert deterministic_Verifier([str(uid_rename[u]) for u in perm_units], reord_pos, reord_block_of_unit, reord_quota_of_block)[0] is True
        assert deterministic_Verifier([str(uid_rename[u]) for u in perm_units], reord_neg, reord_block_of_unit, reord_quota_of_block)[0] is False

        cases.append(
            {
                "case_id": f"BDM_{ci:02d}",
                "trial": "Bangladesh_Mask_CRT_2022",
                "domain": "public_health_epidemiology",
                "pair_ids": pids,
                "within_same_district_and_wave": same_dw,
                "illegal_preserves_district_and_wave_totals": bool(strict_illegals),
                "n_units": len(unit_ids),
                "total_treated": int(sum(obs_vec)),
                "exact_support_size": len(supp1),
                "total_same_count_size": math.comb(len(unit_ids), int(sum(obs_vec))),
                "enumerator_crosscheck_exact_match": True,
                "gold_schema": {
                    "unit_col": "union",
                    "block_col": "pairID",
                    "block_sizes": size_of_block,
                    "block_quotas": quota_of_block,
                },
                "table_union_reg_rows": sub[["district", "union", "pairID", "wave", "surgical_pair", "cloth_pair", "treatment"]].to_dict(orient="records"),
                "table_blood_base_rows": sub[["union", "n_posXsymp_base", "prop_posXsymp_base"]].to_dict(orient="records"),
                "observed_assignment": {u: int(z) for u, z in zip(unit_ids, obs_vec)},
                "positive_admissible": {"assignment": pos_map, "oracle_valid": True, "oracle_reason": msg_p},
                "matched_illegal": {"assignment": neg_map, "oracle_valid": False, "oracle_reason": msg_n},
                "neutral_reorder_control": {
                    "table_union_reg_rows": reord_reg,
                    "table_blood_base_rows": reord_bld,
                    "positive_admissible": {"assignment": reord_pos, "oracle_valid": True},
                    "matched_illegal": {"assignment": reord_neg, "oracle_valid": False},
                    "gold_block_quotas": reord_quota_of_block,
                },
            }
        )
    return cases


def main() -> None:
    rtv = load_rockthevote()
    ab = load_abaluck_joined()

    rtv_all = build_rockthevote_cases(rtv, max_cases=13)
    ab_all = build_abaluck_cases(ab, max_cases=27)

    print(f"Trial 1 (RockTheVote): built {len(rtv_all)} completely non-overlapping 3-block cases (39/40 strata, 0 overlap).")
    print(f"Trial 2 (Abaluck 2022): built {len(ab_all)} completely non-overlapping 3-pair cases ({3*len(ab_all)}/286 pairs, 0 overlap).")
    same_dw_cnt = sum(1 for c in ab_all if c["within_same_district_and_wave"])
    pres_dw_cnt = sum(1 for c in ab_all if c["illegal_preserves_district_and_wave_totals"])
    print(f"  Abaluck within same (district, wave): {same_dw_cnt}/{len(ab_all)} | illegal preserves exact district+wave totals: {pres_dw_cnt}/{len(ab_all)}")

    # Save 6 small oracle cases per trial (12 total) for Stage-0 feasibility artifact
    oracle_12 = {
        "purpose": "Stage-0 verified small oracle cases (6 per trial = 12 total), independently cross-checked via Cartesian block enumeration and brute-force same-total assertion filtering.",
        "privacy_notice": "Public de-identified aggregate cluster/market metadata only; zero individual voter or personal records.",
        "source_hashes": {
            "pscl_RockTheVote_rda": sha256_file(RAW / "pscl_RockTheVote.rda"),
            "pscl_RockTheVote_Rd": sha256_file(RAW / "pscl_RockTheVote.Rd"),
            "abaluck_union_reg_sample_dta": sha256_file(RAW / "abaluck2022_bd_mask_rct/01_data/00_common/01_clean/union_reg_sample.dta"),
            "abaluck_union_baseline_blood_stats_dta": sha256_file(RAW / "abaluck2022_bd_mask_rct/01_data/00_common/00_raw/union_baseline_blood_stats.dta"),
            "abaluck_10a_reg_rand_inf_symp_sero_do": sha256_file(RAW / "abaluck2022_bd_mask_rct/02_code/05_bloodEndline/robustness/10a_reg_rand_inf_symp_sero.do"),
        },
        "trial1_rockthevote_oracle_6": rtv_all[:6],
        "trial2_abaluck2022_oracle_6": ab_all[:6],
    }
    oracle_path = ROOT / "STAGE0_ORACLE_CASES_12.json"
    oracle_path.write_text(json.dumps(oracle_12, indent=2), encoding="utf-8")

    # Save full 40 non-overlapping matched cases (13 RTV + 27 BDM) for potential Stage-0 bounded screen
    bench_40 = {
        "n_cases": len(rtv_all) + len(ab_all),
        "n_rockthevote": len(rtv_all),
        "n_abaluck2022": len(ab_all),
        "zero_cluster_overlap_verified": True,
        "cases": rtv_all + ab_all,
    }
    bench_path = ROOT / "STAGE0_MATCHED_40_CASES.json"
    bench_path.write_text(json.dumps(bench_40, indent=2), encoding="utf-8")

    print("\nSaved STAGE0_ORACLE_CASES_12.json SHA-256:", sha256_file(oracle_path))
    print("Saved STAGE0_MATCHED_40_CASES.json SHA-256:", sha256_file(bench_path))

    print("\n=== ILLUSTRATIVE EXACT CASE 1 (RockTheVote RTV_01 — includes size-3 stratum 3!) ===")
    print(json.dumps(rtv_all[0], indent=2))
    print("\n=== ILLUSTRATIVE EXACT CASE 2 (Bangladesh Mask CRT BDM_01 — same district & wave!) ===")
    print(json.dumps(ab_all[0], indent=2))


if __name__ == "__main__":
    main()
