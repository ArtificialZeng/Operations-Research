"""Fetch arm-level per-term MedDRA SOC adverse-event stats from ClinicalTrials.gov v2.

Computes ABSOLUTE arm-level non-serious AE rates separately for Subjective-Symptom MedDRA SOCs
versus Objective Laboratory/Organ MedDRA SOCs (resolving the compositional sum-to-100% constraint
of SOC share regressions!).

Queries ClinicalTrials.gov REST API v2 in polite batches (filter.ids, 50 NCTs/request) for every
trial in data/processed/d30_mrct_placebo_panel.parquet, reusing the exact arm classification and
MedDRA SOC sets from 02_build_panel.py.

Exports:
  - data/processed/d30_meddra_soc_abs_rates.parquet
  - data/processed/meddra_soc_abs_summary.json
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")
SCRIPTS_DIR = BASE_DIR / "scripts"
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
FIELD_LIST = [
    "protocolSection.identificationModule.nctId",
    "resultsSection.adverseEventsModule.eventGroups",
    "resultsSection.adverseEventsModule.otherEvents",
]
FIELDS = ",".join(FIELD_LIST)


def _load_build_panel():
    spec = importlib.util.spec_from_file_location("build_panel_v2", SCRIPTS_DIR / "02_build_panel.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_panel_v2"] = mod
    spec.loader.exec_module(mod)
    return mod


def fetch_batch(session: requests.Session, nct_ids: list[str], max_retries: int = 5) -> list[dict]:
    params = {
        "filter.ids": ",".join(nct_ids),
        "fields": FIELDS,
        "pageSize": max(len(nct_ids), 100),
    }
    for attempt in range(1, max_retries + 1):
        try:
            resp = session.get(CTGOV_URL, params=params, timeout=45)
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


def compute_trial_soc_rates(st: dict, build_mod) -> dict | None:
    """Compute arm-level absolute Subjective vs Objective MedDRA SOC rates for one trial."""
    ps = st.get("protocolSection") or {}
    rs = st.get("resultsSection") or {}
    nct = (ps.get("identificationModule") or {}).get("nctId")
    if not nct:
        return None

    ae_mod = rs.get("adverseEventsModule") or {}
    egroups = ae_mod.get("eventGroups") or []
    other_events = ae_mod.get("otherEvents") or []

    # Map eventGroup id -> ('placebo'|'active', arm_at_risk) matching 02_build_panel.py exactly
    ctrl_ids: dict[str, float] = {}
    act_ids: dict[str, float] = {}
    for g in egroups:
        gid = g.get("id")
        if not gid:
            continue
        sr = g.get("seriousNumAtRisk")
        orisk = g.get("otherNumAtRisk")
        if not sr or sr < 20:
            continue
        at_risk = float(orisk) if (orisk and orisk >= 20) else float(sr)
        cls, _ = build_mod.classify_event_group(g.get("title") or "", g.get("description") or "")
        if cls == "placebo":
            ctrl_ids[gid] = at_risk
        elif cls == "active":
            act_ids[gid] = at_risk

    if not ctrl_ids or not act_ids:
        return None

    ctrl_denom_tot = sum(ctrl_ids.values())
    act_denom_tot = sum(act_ids.values())

    # Accumulators per (arm_class, soc_class):
    # - sum_aff_num: sum across preferred terms of affected participants in that SOC class
    # - sum_evt_num: sum across preferred terms of event counts (when numEvents reported)
    # - max_term_rate: maximum single-term affected proportion in that SOC class (lower bound on any-SOC-AE rate)
    # - n_terms_pos: number of reported terms with >= 1 affected participant in that arm & SOC class
    acc = {
        ("ctrl", "subj"): {"aff_num": 0.0, "evt_num": 0.0, "has_evt": 0, "max_r": 0.0, "n_pos": 0, "n_terms": 0},
        ("ctrl", "obj"): {"aff_num": 0.0, "evt_num": 0.0, "has_evt": 0, "max_r": 0.0, "n_pos": 0, "n_terms": 0},
        ("act", "subj"): {"aff_num": 0.0, "evt_num": 0.0, "has_evt": 0, "max_r": 0.0, "n_pos": 0, "n_terms": 0},
        ("act", "obj"): {"aff_num": 0.0, "evt_num": 0.0, "has_evt": 0, "max_r": 0.0, "n_pos": 0, "n_terms": 0},
    }

    n_terms_subj_all = 0
    n_terms_obj_all = 0
    n_terms_unmapped = 0

    for ev in other_events:
        soc = (ev.get("organSystem") or "").strip().lower()
        if soc in build_mod.SUBJECTIVE_SOCS:
            soc_cls = "subj"
            n_terms_subj_all += 1
        elif soc in build_mod.OBJECTIVE_SOCS:
            soc_cls = "obj"
            n_terms_obj_all += 1
        else:
            n_terms_unmapped += 1
            continue

        # Aggregate this preferred term across all placebo arms and all active arms
        c_aff, c_den, c_evt, c_evt_ok = 0.0, 0.0, 0.0, False
        a_aff, a_den, a_evt, a_evt_ok = 0.0, 0.0, 0.0, False
        for s_item in (ev.get("stats") or []):
            gid = s_item.get("groupId")
            naff = s_item.get("numAffected")
            nrisk = s_item.get("numAtRisk")
            nevt = s_item.get("numEvents")
            if gid in ctrl_ids:
                den_g = float(nrisk) if (nrisk and nrisk > 0) else ctrl_ids[gid]
                if naff is not None and 0 <= naff <= den_g:
                    c_aff += float(naff)
                    c_den += den_g
                if nevt is not None and nevt >= 0:
                    c_evt += float(nevt)
                    c_evt_ok = True
            elif gid in act_ids:
                den_g = float(nrisk) if (nrisk and nrisk > 0) else act_ids[gid]
                if naff is not None and 0 <= naff <= den_g:
                    a_aff += float(naff)
                    a_den += den_g
                if nevt is not None and nevt >= 0:
                    a_evt += float(nevt)
                    a_evt_ok = True

        for arm_lbl, aff, den, evt, evt_ok, fallback_den in [
            ("ctrl", c_aff, c_den, c_evt, c_evt_ok, ctrl_denom_tot),
            ("act", a_aff, a_den, a_evt, a_evt_ok, act_denom_tot),
        ]:
            bucket = acc[(arm_lbl, soc_cls)]
            bucket["n_terms"] += 1
            d_eff = den if den >= 20 else fallback_den
            if d_eff > 0:
                rate = aff / d_eff
                bucket["aff_num"] += rate
                bucket["max_r"] = max(bucket["max_r"], rate)
                if aff > 0:
                    bucket["n_pos"] += 1
                if evt_ok:
                    bucket["evt_num"] += evt / d_eff
                    bucket["has_evt"] += 1

    rec = {
        "nct_id": nct,
        "soc_n_subj_terms_api": int(n_terms_subj_all),
        "soc_n_obj_terms_api": int(n_terms_obj_all),
        "soc_n_unmapped_terms_api": int(n_terms_unmapped),
    }
    for arm_lbl in ("ctrl", "act"):
        for soc_cls in ("subj", "obj"):
            b = acc[(arm_lbl, soc_cls)]
            sum_aff = float(b["aff_num"])
            max_r = float(min(1.0, b["max_r"]))
            rec[f"{arm_lbl}_{soc_cls}_sum_aff_rate"] = sum_aff
            rec[f"log_{arm_lbl}_{soc_cls}_sum_aff_rate"] = float(np.log(0.01 + sum_aff))
            rec[f"{arm_lbl}_{soc_cls}_max_pct"] = max_r
            rec[f"{arm_lbl}_{soc_cls}_n_pos_terms"] = int(b["n_pos"])
            rec[f"log_{arm_lbl}_{soc_cls}_n_pos_terms"] = float(np.log1p(b["n_pos"]))
            rec[f"{arm_lbl}_{soc_cls}_has_any"] = int(b["n_pos"] > 0)
            rec[f"{arm_lbl}_{soc_cls}_evt_rate"] = float(b["evt_num"]) if b["has_evt"] > 0 else np.nan
    return rec


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    out_parquet = PROC_DIR / "d30_meddra_soc_abs_rates.parquet"
    out_summary = PROC_DIR / "meddra_soc_abs_summary.json"
    if out_parquet.exists() and out_summary.exists() and not args.force:
        print(f"[SKIP] {out_parquet.name} already cached (use --force to re-fetch).", flush=True)
        return 0

    build_mod = _load_build_panel()
    panel = pd.read_parquet(PROC_DIR / "d30_mrct_placebo_panel.parquet")
    nct_ids = sorted(panel["nct_id"].unique().tolist())

    session = requests.Session()
    session.headers.update({"User-Agent": "D30-Boost-MedDRA-AbsRates/2.0"})

    rows: list[dict] = []
    t0 = time.time()
    n_batches = (len(nct_ids) + args.batch_size - 1) // args.batch_size
    print(f"[START] Fetching per-term MedDRA otherEvents.stats for {len(nct_ids)} MRCTs ({n_batches} batches)...", flush=True)

    for b_idx in range(n_batches):
        batch = nct_ids[b_idx * args.batch_size : (b_idx + 1) * args.batch_size]
        studies = fetch_batch(session, batch)
        for st in studies:
            rec = compute_trial_soc_rates(st, build_mod)
            if rec is not None:
                rows.append(rec)
        if (b_idx + 1) % 10 == 0 or (b_idx + 1) == n_batches:
            print(
                f"  Batch {b_idx + 1:02d}/{n_batches}: parsed={len(rows)}/{len(nct_ids)} "
                f"| elapsed={time.time() - t0:.1f}s",
                flush=True,
            )
        time.sleep(0.12)

    df_soc = pd.DataFrame(rows).drop_duplicates(subset=["nct_id"]).reset_index(drop=True)
    df_soc.to_parquet(out_parquet, index=False)
    sha = hashlib.sha256(out_parquet.read_bytes()).hexdigest()

    summary = {
        "fetched_utc": datetime.now(UTC).isoformat(),
        "endpoint": CTGOV_URL,
        "panel_nct_requested": len(nct_ids),
        "parsed_trials": len(df_soc),
        "coverage_pct": round(100.0 * len(df_soc) / max(1, len(nct_ids)), 2),
        "elapsed_seconds": round(time.time() - t0, 2),
        "means": {
            k: round(float(df_soc[k].mean()), 4)
            for k in [
                "ctrl_subj_sum_aff_rate", "act_subj_sum_aff_rate",
                "ctrl_obj_sum_aff_rate", "act_obj_sum_aff_rate",
                "ctrl_subj_max_pct", "act_subj_max_pct",
                "ctrl_obj_max_pct", "act_obj_max_pct",
                "ctrl_subj_n_pos_terms", "ctrl_obj_n_pos_terms",
            ]
        },
        "sha256": sha,
    }
    out_summary.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("[DONE] MedDRA SOC absolute rates saved:", json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
