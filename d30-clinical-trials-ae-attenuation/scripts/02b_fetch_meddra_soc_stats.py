"""Fetch, archive, and audit per-term MedDRA adverse-event stats from ClinicalTrials.gov v2.

Upgrades for v4 (JCE methodology revision):
  1. Archives the complete raw ClinicalTrials.gov v2 API response for all 2,771 panel trials
     to data/raw_ctgov/meddra_other_events_snapshot.jsonl.gz with a cryptographic manifest
     (data/raw_ctgov/meddra_snapshot_manifest.json: UTC timestamp, endpoint, fields, counts,
     byte sizes, and SHA-256 digests). Subsequent runs re-parse deterministically from the
     archived snapshot unless --force-fetch is passed.
  2. Eliminates silent denominator fallbacks and missing-as-zero recoding: audits every
     reported trial-arm-term cell explicitly into valid positive, valid zero, missing/low
     denominator (<20 or naff > nrisk), and missing affected count / omitted groupId.
  3. Recodes a pre-defined common MedDRA preferred-term panel (derived deterministically
     from uncensored freq_thr == 0% trials) into four mutually exclusive cell states:
       - true_zero (or observed_positive)
       - below_threshold (left-censored in [0, min(freq_thr/100, arm_any_oth_rate)])
       - missing_unreliable_denom
       - missing_term
     and exports exact trial-level interval bounds [L_i, U_i] for Manski / interval slope
     propagation.
  4. Audits AE observation time-frame completeness (timeFrame) and sourceVocabulary coverage.

Exports:
  - data/raw_ctgov/meddra_other_events_snapshot.jsonl.gz
  - data/raw_ctgov/meddra_snapshot_manifest.json
  - data/processed/d30_meddra_soc_abs_rates.parquet
  - data/processed/meddra_soc_abs_summary.json
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import importlib.util
import json
import sys
import time
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BASE_DIR / "scripts"
RAW_DIR = BASE_DIR / "data" / "raw_ctgov"
PROC_DIR = BASE_DIR / "data" / "processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROC_DIR.mkdir(parents=True, exist_ok=True)

SNAPSHOT_PATH = RAW_DIR / "meddra_other_events_snapshot.jsonl.gz"
SNAPSHOT_MANIFEST_PATH = RAW_DIR / "meddra_snapshot_manifest.json"

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
FIELD_LIST = [
    "protocolSection.identificationModule.nctId",
    "resultsSection.adverseEventsModule.frequencyThreshold",
    "resultsSection.adverseEventsModule.timeFrame",
    "resultsSection.adverseEventsModule.description",
    "resultsSection.adverseEventsModule.eventGroups",
    "resultsSection.adverseEventsModule.otherEvents",
    "resultsSection.adverseEventsModule.seriousEvents.term",
    "resultsSection.adverseEventsModule.seriousEvents.organSystem",
    "resultsSection.adverseEventsModule.seriousEvents.assessmentType",
]
FIELDS = ",".join(FIELD_LIST)

# Objective lab/organ SOCs strictly excluding Infections and Infestations (for lab-only sensitivity)
OBJECTIVE_LAB_STRICT_SOCS = {
    "investigations",
    "blood and lymphatic system disorders",
    "metabolism and nutrition disorders",
    "cardiac disorders",
    "vascular disorders",
    "renal and urinary disorders",
    "hepatobiliary disorders",
}


def _load_build_panel():
    spec = importlib.util.spec_from_file_location("build_panel_v4", SCRIPTS_DIR / "02_build_panel.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_panel_v4"] = mod
    spec.loader.exec_module(mod)
    return mod


# Canonical MedDRA UK-English spelling aliases for common US-English trial submissions
SPELLING_ALIASES = {
    "diarrhea": "diarrhoea",
    "anemia": "anaemia",
    "hyperglycemia": "hyperglycaemia",
    "hypoglycemia": "hypoglycaemia",
    "hypokalemia": "hypokalaemia",
    "hyperkalemia": "hyperkalaemia",
    "hematuria": "haematuria",
    "hemoglobin decreased": "haemoglobin decreased",
    "hyperuricemia": "hyperuricaemia",
    "edema": "oedema",
    "edema peripheral": "oedema peripheral",
    "dyspnea": "dyspnoea",
    "leukopenia": "leucopenia",
}


def _norm_term(term: str | None) -> str:
    if not term:
        return ""
    norm = " ".join(term.strip().lower().split())
    return SPELLING_ALIASES.get(norm, norm)


def fetch_batch(session: requests.Session, nct_ids: list[str], max_retries: int = 5) -> list[dict]:
    params = {
        "filter.ids": ",".join(nct_ids),
        "fields": FIELDS,
        "pageSize": max(len(nct_ids), 100),
    }
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(CTGOV_URL, params=params, timeout=60)
            if resp.status_code == 200:
                return resp.json().get("studies", [])
            if resp.status_code in (429, 500, 502, 503, 504):
                wait = min(30, 2 ** attempt)
                print(f"  [RETRY {attempt}/{max_retries}] HTTP {resp.status_code}, sleeping {wait}s...", flush=True)
                time.sleep(wait)
                continue
            raise RuntimeError(f"HTTP {resp.status_code}: {resp.text[:300]}")
        except requests.RequestException as exc:
            wait = min(30, 2 ** attempt)
            print(f"  [RETRY {attempt}/{max_retries}] Network error: {exc}, sleeping {wait}s...", flush=True)
            time.sleep(wait)
    raise RuntimeError("Exceeded max_retries fetching CT.gov MedDRA SOC stats batch")


def fetch_and_archive_snapshot(nct_ids: list[str], batch_size: int = 50) -> dict:
    """Query ClinicalTrials.gov v2 API and write deterministic gzipped JSONL + manifest."""
    session = requests.Session()
    session.headers.update({"User-Agent": "D30-JCE-MedDRA-Audit/4.0"})

    studies_by_nct: dict[str, dict] = {}
    t0 = time.time()
    n_batches = (len(nct_ids) + batch_size - 1) // batch_size
    print(
        f"[FETCH] Archiving live CT.gov v2 MedDRA snapshot for {len(nct_ids)} MRCTs ({n_batches} batches)...",
        flush=True,
    )
    for b_idx in range(n_batches):
        batch = nct_ids[b_idx * batch_size : (b_idx + 1) * batch_size]
        studies = fetch_batch(session, batch)
        for st in studies:
            nct = (st.get("protocolSection") or {}).get("identificationModule", {}).get("nctId")
            if nct:
                studies_by_nct[nct] = st
        if (b_idx + 1) % 10 == 0 or (b_idx + 1) == n_batches:
            print(
                f"  Batch {b_idx + 1:02d}/{n_batches}: fetched={len(studies_by_nct)}/{len(nct_ids)} "
                f"| elapsed={time.time() - t0:.1f}s",
                flush=True,
            )
        time.sleep(0.12)

    sorted_ncts = sorted(studies_by_nct.keys())
    raw_hasher = hashlib.sha256()
    raw_bytes_total = 0
    with gzip.open(SNAPSHOT_PATH, "wb", compresslevel=6) as fh:
        for nct in sorted_ncts:
            line = (json.dumps(studies_by_nct[nct], sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
            raw_hasher.update(line)
            raw_bytes_total += len(line)
            fh.write(line)

    gz_sha = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
    manifest = {
        "fetched_utc": datetime.now(UTC).isoformat(),
        "endpoint": CTGOV_URL,
        "fields": FIELD_LIST,
        "nct_requested": len(nct_ids),
        "nct_returned": len(sorted_ncts),
        "missing_ncts": sorted(set(nct_ids) - set(sorted_ncts)),
        "snapshot_file": SNAPSHOT_PATH.relative_to(BASE_DIR).as_posix(),
        "gz_bytes": SNAPSHOT_PATH.stat().st_size,
        "uncompressed_bytes": raw_bytes_total,
        "sha256_gz": gz_sha,
        "sha256_uncompressed": raw_hasher.hexdigest(),
        "elapsed_seconds": round(time.time() - t0, 2),
    }
    SNAPSHOT_MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(
        f"[ARCHIVED] {SNAPSHOT_PATH.name} ({manifest['gz_bytes'] / 1e6:.2f} MB gz, "
        f"{len(sorted_ncts)}/{len(nct_ids)} trials, sha256={gz_sha[:16]}...)",
        flush=True,
    )
    return manifest


def load_archived_studies() -> list[dict]:
    studies: list[dict] = []
    with gzip.open(SNAPSHOT_PATH, "rb") as fh:
        for raw_line in fh:
            line = raw_line.decode("utf-8").strip()
            if line:
                studies.append(json.loads(line))
    return studies


def _extract_arm_maps(ae_mod: dict, build_mod) -> tuple[dict[str, dict], dict[str, dict]]:
    """Map eventGroup id -> arm metadata matching 02_build_panel.py arm classification."""
    ctrl_arms: dict[str, dict] = {}
    act_arms: dict[str, dict] = {}
    for g in (ae_mod.get("eventGroups") or []):
        gid = g.get("id")
        if not gid:
            continue
        sr = g.get("seriousNumAtRisk")
        orisk = g.get("otherNumAtRisk")
        oa = g.get("otherNumAffected")
        if not sr or sr < 20:
            continue
        has_valid_orisk = bool(orisk is not None and orisk >= 20)
        at_risk_legacy = float(orisk) if has_valid_orisk else float(sr)
        cls, _ = build_mod.classify_event_group(g.get("title") or "", g.get("description") or "")
        info = {
            "other_at_risk": float(orisk) if has_valid_orisk else np.nan,
            "other_affected": float(oa) if (oa is not None and has_valid_orisk and 0 <= oa <= orisk) else np.nan,
            "serious_at_risk": float(sr),
            "at_risk_legacy": at_risk_legacy,
            "has_valid_orisk": has_valid_orisk,
        }
        if cls == "placebo":
            ctrl_arms[gid] = info
        elif cls == "active":
            act_arms[gid] = info
    return ctrl_arms, act_arms


def select_predefined_common_terms(studies: list[dict], build_mod, k_per_group: int = 15) -> dict:
    """Select top-K subjective and objective MedDRA preferred terms strictly inside freq_thr == 0% trials.

    Defining the common preferred-term panel from uncensored 0%-threshold studies prevents
    selection bias induced by 5% reporting thresholds.
    """
    subj_counts: Counter[str] = Counter()
    obj_counts: Counter[str] = Counter()
    obj_lab_counts: Counter[str] = Counter()
    inv_counts: Counter[str] = Counter()
    n_freq0_trials = 0

    for st in studies:
        ae_mod = (st.get("resultsSection") or {}).get("adverseEventsModule") or {}
        f_raw = ae_mod.get("frequencyThreshold")
        try:
            f_val = float(f_raw) if f_raw is not None else np.nan
        except (TypeError, ValueError):
            f_val = np.nan
        if f_val != 0.0:
            continue
        n_freq0_trials += 1
        seen_s: set[str] = set()
        seen_o: set[str] = set()
        seen_ol: set[str] = set()
        seen_inv: set[str] = set()
        for ev in (ae_mod.get("otherEvents") or []):
            soc = (ev.get("organSystem") or "").strip().lower()
            term = _norm_term(ev.get("term"))
            if not term:
                continue
            if soc in build_mod.SUBJECTIVE_SOCS:
                seen_s.add(term)
            elif soc in build_mod.OBJECTIVE_SOCS:
                seen_o.add(term)
                if soc in OBJECTIVE_LAB_STRICT_SOCS:
                    seen_ol.add(term)
                if soc == "investigations":
                    seen_inv.add(term)
        for t in seen_s:
            subj_counts[t] += 1
        for t in seen_o:
            obj_counts[t] += 1
        for t in seen_ol:
            obj_lab_counts[t] += 1
        for t in seen_inv:
            inv_counts[t] += 1

    subj_panel = [t for t, _ in subj_counts.most_common(k_per_group)]
    obj_panel = [t for t, _ in obj_counts.most_common(k_per_group)]
    obj_lab_panel = [t for t, _ in obj_lab_counts.most_common(k_per_group)]
    inv_panel = [t for t, _ in inv_counts.most_common(k_per_group)]
    return {
        "selection_basis": "Top preferred terms by trial prevalence strictly inside freq_thr == 0% uncensored trials",
        "n_freq0_trials_used": n_freq0_trials,
        "k_per_group": k_per_group,
        "subjective_terms": [{"term": t, "freq0_trials": int(subj_counts[t])} for t in subj_panel],
        "objective_terms": [{"term": t, "freq0_trials": int(obj_counts[t])} for t in obj_panel],
        "objective_lab_only_terms": [{"term": t, "freq0_trials": int(obj_lab_counts[t])} for t in obj_lab_panel],
        "investigations_terms": [{"term": t, "freq0_trials": int(inv_counts[t])} for t in inv_panel],
        "subjective_set": subj_panel,
        "objective_set": obj_panel,
        "objective_lab_set": obj_lab_panel,
        "investigations_set": inv_panel,
    }


def _evaluate_arm_event_cell(
    ev_stats: list[dict],
    arm_map: dict[str, dict],
) -> dict:
    """Strictly audit one trial's otherEvents term for one arm class (placebo or active).

    Zero silent fallback: separates valid_positive, valid_zero, missing_unreliable_denom,
    and missing_affected_or_group. Also computes legacy v2/v3 fallback rate for exact diff audit.
    """
    stats_by_gid = {s.get("groupId"): s for s in (ev_stats or []) if s.get("groupId")}
    n_expected_groups = len(arm_map)

    # Strict audit across arm groups
    strict_aff = 0.0
    strict_den = 0.0
    strict_ok_groups = 0
    n_missing_group = 0
    n_missing_aff = 0
    n_missing_or_low_denom = 0
    n_denom_mismatch_vs_arm = 0

    # Legacy v2/v3 accumulation (for exact comparison with prior implementation)
    leg_aff = 0.0
    leg_den = 0.0
    leg_evt = 0.0
    leg_evt_ok = False
    leg_fallback_den = sum(v["at_risk_legacy"] for v in arm_map.values())

    for gid, info in arm_map.items():
        s_item = stats_by_gid.get(gid)
        if s_item is None:
            n_missing_group += 1
            continue
        naff = s_item.get("numAffected")
        nrisk = s_item.get("numAtRisk")
        nevt = s_item.get("numEvents")

        # Legacy behavior
        den_g_leg = float(nrisk) if (nrisk and nrisk > 0) else info["at_risk_legacy"]
        if naff is not None and 0 <= naff <= den_g_leg:
            leg_aff += float(naff)
            leg_den += den_g_leg
        if nevt is not None and nevt >= 0:
            leg_evt += float(nevt)
            leg_evt_ok = True

        # Strict audit: require explicit or arm-consistent valid numAtRisk >= 20 and valid numAffected
        if naff is None:
            n_missing_aff += 1
            continue
        # Check term-level numAtRisk explicitly first; if absent, do NOT silently fall back!
        if nrisk is None or nrisk < 20 or naff < 0 or naff > nrisk:
            n_missing_or_low_denom += 1
            continue
        if info["has_valid_orisk"] and abs(float(nrisk) - info["other_at_risk"]) > 0.5:
            n_denom_mismatch_vs_arm += 1
        strict_aff += float(naff)
        strict_den += float(nrisk)
        strict_ok_groups += 1

    # Strict cell status for this (trial, arm_class, term)
    if strict_ok_groups == n_expected_groups and strict_den >= 20:
        strict_rate = strict_aff / strict_den
        strict_state = "observed_pos" if strict_aff > 0 else "true_zero"
    elif n_missing_or_low_denom > 0:
        strict_rate = np.nan
        strict_state = "missing_unreliable_denom"
    else:
        strict_rate = np.nan
        strict_state = "missing_term"

    # Legacy rate (with fallback_den when leg_den < 20)
    leg_used_fallback = bool(leg_den < 20)
    d_eff_leg = leg_den if leg_den >= 20 else leg_fallback_den
    leg_rate = (leg_aff / d_eff_leg) if d_eff_leg > 0 else np.nan
    leg_evt_rate = (leg_evt / d_eff_leg) if (leg_evt_ok and d_eff_leg > 0) else np.nan

    return {
        "strict_state": strict_state,
        "strict_rate": strict_rate,
        "strict_aff": strict_aff,
        "strict_den": strict_den,
        "n_missing_group": n_missing_group,
        "n_missing_aff": n_missing_aff,
        "n_missing_or_low_denom": n_missing_or_low_denom,
        "n_denom_mismatch_vs_arm": n_denom_mismatch_vs_arm,
        "leg_rate": leg_rate,
        "leg_aff": leg_aff,
        "leg_used_fallback": leg_used_fallback,
        "leg_evt_rate": leg_evt_rate,
        "leg_evt_ok": leg_evt_ok,
    }


def compute_trial_meddra_audit(
    st: dict,
    build_mod,
    panel_terms: dict,
    global_counters: dict,
) -> dict | None:
    """Compute both strict four-state audited MedDRA metrics and legacy metrics for one trial."""
    ps = st.get("protocolSection") or {}
    rs = st.get("resultsSection") or {}
    nct = (ps.get("identificationModule") or {}).get("nctId")
    if not nct:
        return None

    ae_mod = rs.get("adverseEventsModule") or {}
    ctrl_arms, act_arms = _extract_arm_maps(ae_mod, build_mod)
    if not ctrl_arms or not act_arms:
        return None

    f_raw = ae_mod.get("frequencyThreshold")
    try:
        freq_thr = float(f_raw) if f_raw is not None else np.nan
    except (TypeError, ValueError):
        freq_thr = np.nan

    tf_raw = ae_mod.get("timeFrame")
    has_tf = int(isinstance(tf_raw, str) and len(tf_raw.strip()) > 0)
    ae_desc_raw = ae_mod.get("description")
    has_ae_desc = int(isinstance(ae_desc_raw, str) and len(ae_desc_raw.strip()) > 0)

    other_events = ae_mod.get("otherEvents") or []

    # Arm-level overall other-AE denominators and observed any-other-AE ceiling rates
    arm_meta = {}
    for arm_lbl, amap in [("ctrl", ctrl_arms), ("act", act_arms)]:
        all_valid_orisk = all(v["has_valid_orisk"] for v in amap.values())
        tot_orisk = sum(v["other_at_risk"] for v in amap.values() if v["has_valid_orisk"])
        tot_oaff = sum(
            v["other_affected"] for v in amap.values()
            if v["has_valid_orisk"] and not np.isnan(v["other_affected"])
        )
        any_oth_rate = (tot_oaff / tot_orisk) if (all_valid_orisk and tot_orisk >= 20) else np.nan
        arm_meta[arm_lbl] = {
            "all_valid_orisk": all_valid_orisk,
            "tot_orisk": tot_orisk,
            "any_oth_rate": any_oth_rate,
        }

    # Accumulators for legacy vs strict SOC metrics
    leg_acc = {
        (a, s): {"aff_num": 0.0, "evt_num": 0.0, "has_evt": 0, "max_r": 0.0, "n_pos": 0}
        for a in ("ctrl", "act")
        for s in ("subj", "obj")
    }
    strict_acc = {
        (a, s): {
            "aff_num": 0.0,
            "max_r": 0.0,
            "n_valid_cells": 0,
            "n_pos": 0,
            "n_true_zero": 0,
            "n_missing_denom": 0,
            "n_missing_term": 0,
            "n_fallback_triggered": 0,
            "n_denom_mismatch": 0,
        }
        for a in ("ctrl", "act")
        for s in ("subj", "obj", "obj_lab", "inv")
    }

    # Index reported terms by normalized preferred term for the pre-defined common-term panel
    # If the exact same normalized preferred term appears twice in a trial, keep the max/aggregated strict cell.
    reported_term_cells: dict[tuple[str, str], dict] = {}
    n_terms_subj_all = 0
    n_terms_obj_all = 0
    n_terms_obj_lab_all = 0
    n_terms_unmapped = 0
    n_meddra_vocab = 0
    n_vocab_present = 0

    for ev in other_events:
        vocab = (ev.get("sourceVocabulary") or "").strip().lower()
        if vocab:
            n_vocab_present += 1
            if "meddra" in vocab:
                n_meddra_vocab += 1

        soc = (ev.get("organSystem") or "").strip().lower()
        term_norm = _norm_term(ev.get("term"))
        if soc in build_mod.SUBJECTIVE_SOCS:
            soc_cls = "subj"
            n_terms_subj_all += 1
        elif soc in build_mod.OBJECTIVE_SOCS:
            soc_cls = "obj"
            n_terms_obj_all += 1
            if soc in OBJECTIVE_LAB_STRICT_SOCS:
                n_terms_obj_lab_all += 1
        else:
            n_terms_unmapped += 1
            continue

        ev_stats = ev.get("stats") or []
        for arm_lbl, amap in [("ctrl", ctrl_arms), ("act", act_arms)]:
            cell = _evaluate_arm_event_cell(ev_stats, amap)
            global_counters["reported_cells_total"] += 1
            global_counters[f"reported_cell_{cell['strict_state']}"] += 1
            if cell["leg_used_fallback"]:
                global_counters["reported_cells_legacy_fallback_triggered"] += 1
            if cell["n_denom_mismatch_vs_arm"] > 0:
                global_counters["reported_cells_denom_differs_from_arm_otherNumAtRisk"] += 1

            # Legacy accumulation (exact compatibility)
            lb = leg_acc[(arm_lbl, soc_cls)]
            if not np.isnan(cell["leg_rate"]):
                lb["aff_num"] += cell["leg_rate"]
                lb["max_r"] = max(lb["max_r"], cell["leg_rate"])
                if cell["leg_aff"] > 0:
                    lb["n_pos"] += 1
                if cell["leg_evt_ok"] and not np.isnan(cell["leg_evt_rate"]):
                    lb["evt_num"] += cell["leg_evt_rate"]
                    lb["has_evt"] += 1

            # Strict accumulation (NO fallback, NO missing-as-zero!)
            soc_targets = [soc_cls]
            if soc_cls == "obj" and soc in OBJECTIVE_LAB_STRICT_SOCS:
                soc_targets.append("obj_lab")
            if soc == "investigations":
                soc_targets.append("inv")
            for stgt in soc_targets:
                sb = strict_acc[(arm_lbl, stgt)]
                if cell["leg_used_fallback"]:
                    sb["n_fallback_triggered"] += 1
                if cell["n_denom_mismatch_vs_arm"] > 0:
                    sb["n_denom_mismatch"] += 1
                if cell["strict_state"] in ("observed_pos", "true_zero"):
                    sb["n_valid_cells"] += 1
                    sb["aff_num"] += cell["strict_rate"]
                    sb["max_r"] = max(sb["max_r"], cell["strict_rate"])
                    if cell["strict_state"] == "observed_pos":
                        sb["n_pos"] += 1
                    else:
                        sb["n_true_zero"] += 1
                elif cell["strict_state"] == "missing_unreliable_denom":
                    sb["n_missing_denom"] += 1
                else:
                    sb["n_missing_term"] += 1

            if term_norm:
                key = (arm_lbl, term_norm)
                prev = reported_term_cells.get(key)
                if prev is None or (
                    np.isnan(prev["strict_rate"]) and not np.isnan(cell["strict_rate"])
                ) or (
                    not np.isnan(cell["strict_rate"])
                    and not np.isnan(prev["strict_rate"])
                    and cell["strict_rate"] > prev["strict_rate"]
                ):
                    reported_term_cells[key] = cell

    rec: dict = {
        "nct_id": nct,
        "freq_thr_snap": freq_thr,
        "has_ae_timeframe_snap": has_tf,
        "has_ae_desc_snap": has_ae_desc,
        "ae_timeframe_len_snap": len(tf_raw.strip()) if has_tf else 0,
        "meddra_vocab_share": float(n_meddra_vocab / n_vocab_present) if n_vocab_present > 0 else np.nan,
        "soc_n_subj_terms_api": int(n_terms_subj_all),
        "soc_n_obj_terms_api": int(n_terms_obj_all),
        "soc_n_obj_lab_terms_api": int(n_terms_obj_lab_all),
        "soc_n_unmapped_terms_api": int(n_terms_unmapped),
    }

    # Export legacy + strict SOC columns
    for arm_lbl in ("ctrl", "act"):
        for soc_cls in ("subj", "obj"):
            lb = leg_acc[(arm_lbl, soc_cls)]
            sum_aff = float(lb["aff_num"])
            max_r = float(min(1.0, lb["max_r"]))
            rec[f"{arm_lbl}_{soc_cls}_sum_aff_rate"] = sum_aff
            rec[f"log_{arm_lbl}_{soc_cls}_sum_aff_rate"] = float(np.log(0.01 + sum_aff))
            rec[f"{arm_lbl}_{soc_cls}_max_pct"] = max_r
            rec[f"{arm_lbl}_{soc_cls}_n_pos_terms"] = int(lb["n_pos"])
            rec[f"log_{arm_lbl}_{soc_cls}_n_pos_terms"] = float(np.log1p(lb["n_pos"]))
            rec[f"{arm_lbl}_{soc_cls}_has_any"] = int(lb["n_pos"] > 0)
            rec[f"{arm_lbl}_{soc_cls}_evt_rate"] = float(lb["evt_num"]) if lb["has_evt"] > 0 else np.nan

        for stgt in ("subj", "obj", "obj_lab", "inv"):
            sb = strict_acc[(arm_lbl, stgt)]
            has_anom = (sb["n_missing_denom"] + sb["n_missing_term"]) > 0
            any_oth = arm_meta[arm_lbl]["any_oth_rate"]
            tau_loc = float(freq_thr / 100.0) if (not np.isnan(freq_thr) and freq_thr >= 0) else np.nan
            max_lo_s = float(min(1.0, sb["max_r"]))
            if not np.isnan(tau_loc) and max_lo_s < tau_loc:
                ub_s = min(tau_loc, any_oth) if not np.isnan(any_oth) else tau_loc
                max_hi_s = float(min(1.0, max(max_lo_s, ub_s)))
            else:
                max_hi_s = max_lo_s
            rec[f"{arm_lbl}_{stgt}_strict_sum_rate"] = float(sb["aff_num"])
            rec[f"{arm_lbl}_{stgt}_strict_max_pct"] = max_lo_s
            rec[f"{arm_lbl}_{stgt}_strict_max_hi_cap"] = max_hi_s
            rec[f"{arm_lbl}_{stgt}_strict_n_valid"] = int(sb["n_valid_cells"])
            rec[f"{arm_lbl}_{stgt}_strict_n_pos"] = int(sb["n_pos"])
            rec[f"{arm_lbl}_{stgt}_strict_n_true_zero"] = int(sb["n_true_zero"])
            rec[f"{arm_lbl}_{stgt}_strict_n_miss_denom"] = int(sb["n_missing_denom"])
            rec[f"{arm_lbl}_{stgt}_strict_n_miss_term"] = int(sb["n_missing_term"])
            rec[f"{arm_lbl}_{stgt}_strict_has_anom"] = int(has_anom)
            rec[f"{arm_lbl}_{stgt}_legacy_fallback_n"] = int(sb["n_fallback_triggered"])

    # Four-state recoding on pre-defined common MedDRA term panels (K=15 subj, K=15 obj, K=15 inv)
    tau = float(freq_thr / 100.0) if (not np.isnan(freq_thr) and freq_thr >= 0) else np.nan
    has_other_table = len(other_events) > 0

    for panel_name, term_list in [
        ("cpanel_subj", panel_terms["subjective_set"]),
        ("cpanel_obj", panel_terms["objective_set"]),
        ("cpanel_obj_lab", panel_terms["objective_lab_set"]),
        ("cpanel_inv", panel_terms["investigations_set"]),
    ]:
        for arm_lbl in ("ctrl", "act"):
            am = arm_meta[arm_lbl]
            any_oth = am["any_oth_rate"]
            st_counts = Counter()
            sum_lo = 0.0
            sum_mid = 0.0
            sum_hi_raw = 0.0
            sum_hi_capped = 0.0
            max_lo = 0.0
            max_hi_capped = 0.0
            n_unresolved = 0

            for term_k in term_list:
                cell = reported_term_cells.get((arm_lbl, term_k))
                if cell is not None:
                    st_lbl = cell["strict_state"]
                    if st_lbl in ("observed_pos", "true_zero"):
                        r_val = float(cell["strict_rate"])
                        st_counts[st_lbl] += 1
                        sum_lo += r_val
                        sum_mid += r_val
                        sum_hi_raw += r_val
                        sum_hi_capped += r_val
                        max_lo = max(max_lo, r_val)
                        max_hi_capped = max(max_hi_capped, r_val)
                    elif st_lbl == "missing_unreliable_denom":
                        st_counts["missing_unreliable_denom"] += 1
                        n_unresolved += 1
                    else:
                        st_counts["missing_term"] += 1
                        n_unresolved += 1
                else:
                    # Term not listed in otherEvents for this trial: classify strictly into 4 states!
                    if not am["all_valid_orisk"] or am["tot_orisk"] < 20:
                        st_counts["missing_unreliable_denom"] += 1
                        n_unresolved += 1
                    elif np.isnan(tau):
                        st_counts["missing_term"] += 1
                        n_unresolved += 1
                    elif (not has_other_table) and (not np.isnan(any_oth)) and (any_oth > tau + 1e-9):
                        # Trial reports affected participants exceeding threshold yet posted empty otherEvents table
                        st_counts["missing_term"] += 1
                        n_unresolved += 1
                    elif tau == 0.0:
                        # 0% reporting threshold with valid denominator & posted table => TRUE ZERO!
                        st_counts["true_zero"] += 1
                    else:
                        # >0% reporting threshold => BELOW-THRESHOLD LEFT-CENSORED in [0, min(tau, any_oth)]!
                        st_counts["below_threshold"] += 1
                        ub_raw = tau
                        ub_cap = min(tau, any_oth) if not np.isnan(any_oth) else tau
                        sum_mid += 0.5 * ub_cap
                        sum_hi_raw += ub_raw
                        sum_hi_capped += ub_cap
                        max_hi_capped = max(max_hi_capped, ub_cap)

            # Update global audit counts for main subjective & objective panels
            if panel_name in ("cpanel_subj", "cpanel_obj"):
                stratum = "freq0" if tau == 0.0 else ("freq5" if abs(tau - 0.05) < 1e-9 else "other_thr")
                for k_st, v_ct in st_counts.items():
                    global_counters[f"cpanel_all_{k_st}"] += v_ct
                    global_counters[f"cpanel_{stratum}_{k_st}"] += v_ct
                    global_counters[f"{panel_name}_{stratum}_{k_st}"] += v_ct

            pfx = f"{arm_lbl}_{panel_name}"
            # If any panel cell is unresolved (missing_unreliable_denom or missing_term), flag explicitly
            rec[f"{pfx}_n_obs_pos"] = int(st_counts["observed_pos"])
            rec[f"{pfx}_n_true_zero"] = int(st_counts["true_zero"])
            rec[f"{pfx}_n_below_thr"] = int(st_counts["below_threshold"])
            rec[f"{pfx}_n_miss_denom"] = int(st_counts["missing_unreliable_denom"])
            rec[f"{pfx}_n_miss_term"] = int(st_counts["missing_term"])
            rec[f"{pfx}_is_complete_4state"] = int(n_unresolved == 0)
            rec[f"{pfx}_sum_lo"] = float(sum_lo) if n_unresolved == 0 else np.nan
            rec[f"{pfx}_sum_mid"] = float(sum_mid) if n_unresolved == 0 else np.nan
            rec[f"{pfx}_sum_hi_raw"] = float(sum_hi_raw) if n_unresolved == 0 else np.nan
            rec[f"{pfx}_sum_hi_cap"] = float(sum_hi_capped) if n_unresolved == 0 else np.nan
            rec[f"{pfx}_max_lo"] = float(min(1.0, max_lo)) if n_unresolved == 0 else np.nan
            rec[f"{pfx}_max_hi_cap"] = float(min(1.0, max_hi_capped)) if n_unresolved == 0 else np.nan

    return rec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--force-fetch", action="store_true", help="Re-fetch live snapshot from CT.gov v2 API")
    args = parser.parse_args()

    build_mod = _load_build_panel()
    panel = pd.read_parquet(PROC_DIR / "d30_mrct_placebo_panel.parquet")
    nct_ids = sorted(panel["nct_id"].unique().tolist())

    if args.force_fetch or not SNAPSHOT_PATH.exists() or not SNAPSHOT_MANIFEST_PATH.exists():
        snap_manifest = fetch_and_archive_snapshot(nct_ids, batch_size=args.batch_size)
    else:
        snap_manifest = json.loads(SNAPSHOT_MANIFEST_PATH.read_text(encoding="utf-8"))
        actual_sha = hashlib.sha256(SNAPSHOT_PATH.read_bytes()).hexdigest()
        if actual_sha != snap_manifest.get("sha256_gz"):
            raise RuntimeError("Archived MedDRA snapshot SHA-256 mismatch!")
        print(
            f"[REPLAY] Re-parsing verified archived snapshot {SNAPSHOT_PATH.name} "
            f"(fetched {snap_manifest['fetched_utc']}, {snap_manifest['nct_returned']} trials)",
            flush=True,
        )

    t0 = time.time()
    studies = load_archived_studies()
    panel_terms = select_predefined_common_terms(studies, build_mod, k_per_group=15)

    global_counters: Counter[str] = Counter()
    rows: list[dict] = []
    for st in studies:
        rec = compute_trial_meddra_audit(st, build_mod, panel_terms, global_counters)
        if rec is not None:
            rows.append(rec)

    df_soc = pd.DataFrame(rows).drop_duplicates(subset=["nct_id"]).sort_values("nct_id").reset_index(drop=True)
    out_parquet = PROC_DIR / "d30_meddra_soc_abs_rates.parquet"
    df_soc.to_parquet(out_parquet, index=False)
    pq_sha = hashlib.sha256(out_parquet.read_bytes()).hexdigest()

    # Quantify exact difference between legacy fallback and strict zero-fallback rates
    diff_audit = {}
    for arm in ("ctrl", "act"):
        for soc in ("subj", "obj"):
            leg_col = f"{arm}_{soc}_sum_aff_rate"
            str_col = f"{arm}_{soc}_strict_sum_rate"
            abs_diff = (df_soc[leg_col] - df_soc[str_col]).abs()
            diff_audit[f"{arm}_{soc}"] = {
                "n_trials_any_diff": int((abs_diff > 1e-9).sum()),
                "pct_trials_any_diff": round(100.0 * float((abs_diff > 1e-9).mean()), 2),
                "max_abs_diff": round(float(abs_diff.max()), 5),
                "mean_abs_diff": round(float(abs_diff.mean()), 5),
                "n_trials_legacy_fallback_triggered": int((df_soc[f"{arm}_{soc}_legacy_fallback_n"] > 0).sum()),
                "n_trials_missing_denom_cells": int((df_soc[f"{arm}_{soc}_strict_n_miss_denom"] > 0).sum()),
                "n_trials_missing_term_cells": int((df_soc[f"{arm}_{soc}_strict_n_miss_term"] > 0).sum()),
            }

    summary = {
        "parsed_utc": datetime.now(UTC).isoformat(),
        "snapshot_manifest": snap_manifest,
        "panel_nct_requested": len(nct_ids),
        "parsed_trials": len(df_soc),
        "coverage_pct": round(100.0 * len(df_soc) / max(1, len(nct_ids)), 2),
        "elapsed_parse_seconds": round(time.time() - t0, 2),
        "ae_timeframe_audit": {
            "n_with_timeframe": int(df_soc["has_ae_timeframe_snap"].sum()),
            "n_missing_timeframe": int((df_soc["has_ae_timeframe_snap"] == 0).sum()),
            "pct_missing_timeframe": round(100.0 * float((df_soc["has_ae_timeframe_snap"] == 0).mean()), 2),
            "n_with_ae_description": int(df_soc["has_ae_desc_snap"].sum()),
            "mean_meddra_vocab_share": round(float(df_soc["meddra_vocab_share"].mean()), 4),
        },
        "reported_cell_audit": {
            k: int(v) for k, v in sorted(global_counters.items()) if k.startswith("reported_cell")
        },
        "legacy_vs_strict_diff_audit": diff_audit,
        "predefined_common_term_panel": {
            "selection_basis": panel_terms["selection_basis"],
            "n_freq0_trials_used": panel_terms["n_freq0_trials_used"],
            "k_per_group": panel_terms["k_per_group"],
            "subjective_terms": panel_terms["subjective_terms"],
            "objective_terms": panel_terms["objective_terms"],
            "objective_lab_only_terms": panel_terms["objective_lab_only_terms"],
            "investigations_terms": panel_terms["investigations_terms"],
        },
        "common_panel_four_state_counts": {
            k: int(v) for k, v in sorted(global_counters.items()) if k.startswith(("cpanel_",))
        },
        "means": {
            k: round(float(df_soc[k].mean()), 4)
            for k in [
                "ctrl_subj_sum_aff_rate", "act_subj_sum_aff_rate",
                "ctrl_obj_sum_aff_rate", "act_obj_sum_aff_rate",
                "ctrl_subj_strict_sum_rate", "act_subj_strict_sum_rate",
                "ctrl_obj_strict_sum_rate", "act_obj_strict_sum_rate",
                "ctrl_subj_max_pct", "act_subj_max_pct",
                "ctrl_obj_max_pct", "act_obj_max_pct",
                "ctrl_cpanel_subj_sum_lo", "ctrl_cpanel_subj_sum_mid", "ctrl_cpanel_subj_sum_hi_cap",
                "ctrl_cpanel_obj_sum_lo", "ctrl_cpanel_obj_sum_mid", "ctrl_cpanel_obj_sum_hi_cap",
            ]
        },
        "sha256": pq_sha,
    }
    out_summary = PROC_DIR / "meddra_soc_abs_summary.json"
    out_summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print("[DONE] Audited MedDRA snapshot & four-state tables saved.", flush=True)
    print("  Reported cell audit:", json.dumps(summary["reported_cell_audit"], indent=2), flush=True)
    print("  AE timeframe audit:", json.dumps(summary["ae_timeframe_audit"], indent=2), flush=True)
    print("  Legacy vs Strict diff:", json.dumps(summary["legacy_vs_strict_diff_audit"], indent=2), flush=True)
    print("  Top 15 Subj terms (freq==0%):", [x["term"] for x in panel_terms["subjective_terms"]], flush=True)
    print("  Top 15 Obj terms (freq==0%):", [x["term"] for x in panel_terms["objective_terms"]], flush=True)
    print("  Top 15 Obj-Lab-Only terms (freq==0%):", [x["term"] for x in panel_terms["objective_lab_only_terms"]], flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
