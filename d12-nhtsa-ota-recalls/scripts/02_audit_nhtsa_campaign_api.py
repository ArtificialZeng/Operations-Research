"""Step 2: Pull official NHTSA Campaign API ground truth for 100% of software & OTA-candidate
Vehicle campaigns (2018-2026) plus a stratified audit sample of 250 non-software physical campaigns.
Saves incremental JSONL cache and produces a complete Measurement-Integrity Audit reconciling
api.overTheAirUpdate against text-based 4-way remedy classification.
"""
from __future__ import annotations

import json
import re
import threading
import time
import zipfile
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")
RAW_DIR = BASE_DIR / "data_raw"
PROC_DIR = BASE_DIR / "data_processed"
RES_DIR = BASE_DIR / "results"
PROC_DIR.mkdir(parents=True, exist_ok=True)
RES_DIR.mkdir(parents=True, exist_ok=True)

RCL_COLS = [
    "RECORD_ID", "CAMPNO", "MAKETXT", "MODELTXT", "YEARTXT", "MFGCAMPNO",
    "COMPNAME", "MFGNAME", "BGMAN", "ENDMAN", "RCLTYPECD", "POTAFF",
    "ODATE", "INFLUENCED_BY", "MFGTXT", "RCDATE", "DATEA", "RPNO", "FMVSS",
    "DESC_DEFECT", "CONEQUENCE_DEFECT", "CORRECTIVE_ACTION", "NOTES",
    "RCL_CMPT_ID", "MFR_COMP_NAME", "MFR_COMP_DESC", "MFR_COMP_PTNO",
    "DO_NOT_DRIVE", "PARK_OUTSIDE",
]

# Broad candidate detection to ensure ~0% missed OTA/software recalls when querying API
CAND_OTA_PAT = re.compile(
    r"\bover[- ]the[- ]air\b|\bota\b|\bwireless(?:ly)?\b|\bremote(?:ly)?\s+(?:update|push|remedy|download|software|fix)|\bcloud\b|\bcellular\b",
    re.IGNORECASE,
)
CAND_SW_PAT = re.compile(
    r"\bsoftware\b|\bfirmware\b|\breprogram\w*|\b(?:re)?calibrat\w*|\bre-?flash\w*"
    r"|\bflash\w*\s+(?:the\s+)?(?:[\w-]+\s+){0,3}(?:module|ecu|ecm|pcm|bcm|tcm|software|controller)"
    r"|\bupdate\s+(?:the\s+)?(?:[\w-]+\s+){0,4}(?:software|firmware|control\s+module|module|ecu|ecm|pcm|bcm|tcm|abs|infotainment|telematics|head\s+unit|display|camera|calibration|data\s+set|program|parameter|configuration|controller)"
    r"|\bautopilot\b|\bautosteer\b|\bfull\s+self[- ]driving\b",
    re.IGNORECASE,
)

# Audited remedy-text classifier (strictly on CORRECTIVE_ACTION, explicitly catching negations)
OTA_REMEDY_PAT = re.compile(
    r"\bover[- ]the[- ]air\b|\bota\s+(?:software\s+)?(?:update|remedy|release|fix|patch|download)"
    r"|\bvia\s+ota\b|\bthrough\s+ota\b|\bwireless(?:ly)?\s+(?:update|push|download|install|remedy)"
    r"|\bremote(?:ly)?\s+(?:update|push|download|install)",
    re.IGNORECASE,
)
OTA_NEG_PAT = re.compile(
    r"(?:not\s+(?:eligible|capable|equipped|able)\s+(?:for|to\s+receive)\s+(?:an?\s+)?(?:over[- ]the[- ]air|ota))"
    r"|(?:cannot\s+be\s+(?:updated|remedied|fixed|completed)\s+(?:over[- ]the[- ]air|via\s+ota))"
    r"|(?:unable\s+to\s+(?:receive|complete)\s+(?:an?\s+)?(?:over[- ]the[- ]air|ota))",
    re.IGNORECASE,
)
DEALER_VISIT_PAT = re.compile(
    r"\bdealers?\s+will\b|\bdealership\b|\bservice\s+center\b|\bbring\s+(?:their|the)\s+vehicle\b"
    r"|\bat\s+(?:a|an|the)\s+dealer|\bvisit\s+(?:a|an|the)\s+dealer|\breplace\b|\binspect\b|\binstall\s+(?:a|an|new)\b",
    re.IGNORECASE,
)

HEADERS = {
    "User-Agent": "AcademicResearch-NHTSAAudit/2.0 (OperationsManagementStudy; contact: research@university.edu)",
    "Accept": "application/json",
}
API_URL = "https://api.nhtsa.gov/recalls/campaignNumber"

_TLS = threading.local()


def get_session() -> requests.Session:
    sess = getattr(_TLS, "session", None)
    if sess is None:
        sess = requests.Session()
        sess.headers.update(HEADERS)
        _TLS.session = sess
    return sess


def load_2018_2026_campaigns() -> pd.DataFrame:
    zip_path = RAW_DIR / "FLAT_RCL_POST_2010.zip"
    with zipfile.ZipFile(zip_path) as zf:
        txt_name = next(n for n in zf.namelist() if n.lower().endswith(".txt"))
        raw_bytes = zf.read(txt_name)

    lines = raw_bytes.decode("latin-1", errors="replace").splitlines()
    parsed = []
    for ln in lines:
        parts = ln.split("\t")
        if len(parts) < 23:
            continue
        if len(parts) < 29:
            parts = parts + [""] * (29 - len(parts))
        parsed.append(parts[:29])

    df = pd.DataFrame(parsed, columns=RCL_COLS)
    df["RCDATE_dt"] = pd.to_datetime(df["RCDATE"].astype(str).str.strip(), format="%Y%m%d", errors="coerce")
    df["rec_year"] = df["RCDATE_dt"].dt.year
    v = df[(df["RCLTYPECD"].str.strip() == "V") & (df["rec_year"].between(2018, 2026))].copy()
    v["CAMPNO"] = v["CAMPNO"].str.strip()

    camp = v.groupby("CAMPNO", as_index=False).agg(
        mfg=("MFGNAME", "first"),
        rec_year=("rec_year", "min"),
        rec_date=("RCDATE_dt", "min"),
        potaff=("POTAFF", lambda s: pd.to_numeric(s, errors="coerce").max()),
        desc_defect=("DESC_DEFECT", "first"),
        corrective_action=("CORRECTIVE_ACTION", "first"),
        consequence=("CONEQUENCE_DEFECT", "first"),
    )

    dot = pd.read_csv(RAW_DIR / "dot_6axg_epim_recalls.csv", low_memory=False)
    dot["CAMPNO"] = dot["nhtsa_id"].astype(str).str.strip()
    dot_sub = dot.drop_duplicates("CAMPNO")[
        ["CAMPNO", "subject", "defect_summary", "corrective_action", "completion_rate"]
    ].rename(columns={"corrective_action": "dot_corrective_action"})

    camp = camp.merge(dot_sub, on="CAMPNO", how="left")
    all_text = (
        camp["desc_defect"].fillna("")
        + " "
        + camp["corrective_action"].fillna("")
        + " "
        + camp["subject"].fillna("")
        + " "
        + camp["defect_summary"].fillna("")
        + " "
        + camp["dot_corrective_action"].fillna("")
    )
    act_text = camp["corrective_action"].fillna("") + " " + camp["dot_corrective_action"].fillna("")

    camp["cand_ota"] = all_text.str.contains(CAND_OTA_PAT).astype(int)
    camp["cand_sw"] = all_text.str.contains(CAND_SW_PAT).astype(int)
    camp["is_candidate"] = ((camp["cand_ota"] == 1) | (camp["cand_sw"] == 1)).astype(int)

    # Wave-1 style regex vs audited regex
    camp["txt_ota_raw"] = act_text.str.contains(OTA_REMEDY_PAT).astype(int)
    camp["txt_ota_neg"] = act_text.str.contains(OTA_NEG_PAT).astype(int)
    camp["txt_dealer"] = act_text.str.contains(DEALER_VISIT_PAT).astype(int)
    return camp


def fetch_one_campaign(campno: str) -> dict:
    sess = get_session()
    last_err = None
    for attempt in range(1, 5):
        try:
            r = sess.get(API_URL, params={"campaignNumber": campno}, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                time.sleep(1.5 * attempt)
                continue
            if r.status_code == 400 or r.status_code == 404:
                return {
                    "campno": campno,
                    "http_status": r.status_code,
                    "n_results": 0,
                    "api_ota_any": None,
                    "api_ota_all": None,
                    "api_ota_share": None,
                    "api_park_it": None,
                    "api_park_outside": None,
                    "nhtsa_action_number": "",
                    "api_remedy": "",
                    "api_manufacturer": "",
                }
            r.raise_for_status()
            payload = r.json()
            results = payload.get("results") or []
            if not results:
                return {
                    "campno": campno,
                    "http_status": r.status_code,
                    "n_results": 0,
                    "api_ota_any": None,
                    "api_ota_all": None,
                    "api_ota_share": None,
                    "api_park_it": None,
                    "api_park_outside": None,
                    "nhtsa_action_number": "",
                    "api_remedy": "",
                    "api_manufacturer": "",
                }
            ota_flags = [int(bool(it.get("overTheAirUpdate"))) for it in results]
            park_it_flags = [int(bool(it.get("parkIt"))) for it in results]
            park_out_flags = [int(bool(it.get("parkOutSide"))) for it in results]
            actions = sorted({str(it.get("NHTSAActionNumber") or "").strip() for it in results if str(it.get("NHTSAActionNumber") or "").strip()})
            remedies = [str(it.get("Remedy") or "").strip() for it in results if str(it.get("Remedy") or "").strip()]
            mfrs = [str(it.get("Manufacturer") or "").strip() for it in results if str(it.get("Manufacturer") or "").strip()]
            return {
                "campno": campno,
                "http_status": r.status_code,
                "n_results": len(results),
                "api_ota_any": int(max(ota_flags)),
                "api_ota_all": int(min(ota_flags)),
                "api_ota_share": round(float(np.mean(ota_flags)), 4),
                "api_park_it": int(max(park_it_flags)),
                "api_park_outside": int(max(park_out_flags)),
                "nhtsa_action_number": ";".join(actions),
                "api_remedy": remedies[0][:1200] if remedies else "",
                "api_manufacturer": mfrs[0] if mfrs else "",
            }
        except (requests.RequestException, ValueError, OSError) as exc:
            last_err = str(exc)
            time.sleep(1.5 * attempt)
    return {
        "campno": campno,
        "http_status": -1,
        "error": last_err,
        "n_results": 0,
        "api_ota_any": None,
        "api_ota_all": None,
        "api_ota_share": None,
        "api_park_it": None,
        "api_park_outside": None,
        "nhtsa_action_number": "",
        "api_remedy": "",
        "api_manufacturer": "",
    }


def main() -> None:
    camp = load_2018_2026_campaigns()
    print(
        f"[LOAD] 2018-2026 Vehicle campaigns: {len(camp):,} | "
        f"SW/OTA candidates: {int(camp['is_candidate'].sum()):,} "
        f"(cand_ota={int(camp['cand_ota'].sum())}, cand_sw={int(camp['cand_sw'].sum())})",
        flush=True,
    )

    # Select 100% of software & OTA candidates + 250 stratified non-software physical campaigns
    rng = np.random.default_rng(20261125)
    cand_df = camp[camp["is_candidate"] == 1].copy()
    phys_df = camp[camp["is_candidate"] == 0].copy()

    # Stratified sample across rec_year (2018-2026) so every year is audited proportionally (~250 total)
    target_phys = 250
    phys_sample_ids: list[str] = []
    yr_counts = phys_df["rec_year"].value_counts().sort_index()
    alloc = np.maximum(10, np.round(yr_counts / yr_counts.sum() * target_phys).astype(int))
    diff = int(alloc.sum() - target_phys)
    if diff != 0:
        idx_max = alloc.idxmax()
        alloc.loc[idx_max] = max(1, int(alloc.loc[idx_max] - diff))

    for yr, k in alloc.items():
        pool = phys_df[phys_df["rec_year"] == yr]["CAMPNO"].sort_values().to_numpy()
        take = min(int(k), len(pool))
        chosen = rng.choice(pool, size=take, replace=False)
        phys_sample_ids.extend(chosen.tolist())

    query_meta: dict[str, str] = {}
    for cno in cand_df["CAMPNO"].tolist():
        query_meta[cno] = "sw_ota_candidate"
    for cno in phys_sample_ids:
        query_meta[cno] = "physical_audit_sample"

    cache_path = RAW_DIR / "nhtsa_api_campaign_groundtruth.jsonl"
    cached: dict[str, dict] = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            if rec.get("http_status", -1) >= 200:
                cached[rec["campno"]] = rec

    todo = [cno for cno in sorted(query_meta) if cno not in cached]
    print(
        f"[API] Target campaigns: {len(query_meta):,} "
        f"(candidates={len(cand_df):,}, phys_audit={len(phys_sample_ids)}) | "
        f"cached={len(cached):,}, remaining={len(todo):,}",
        flush=True,
    )

    if todo:
        t0 = time.time()
        lock = threading.Lock()
        done_count = 0
        with cache_path.open("a", encoding="utf-8") as fh, ThreadPoolExecutor(max_workers=6) as ex:
            fut_map = {ex.submit(fetch_one_campaign, cno): cno for cno in todo}
            for fut in as_completed(fut_map):
                rec = fut.result()
                rec["sample_stratum"] = query_meta[rec["campno"]]
                with lock:
                    fh.write(json.dumps(rec) + "\n")
                    fh.flush()
                    cached[rec["campno"]] = rec
                    done_count += 1
                    if done_count % 150 == 0 or done_count == len(todo):
                        elapsed = time.time() - t0
                        rate = done_count / max(elapsed, 0.1)
                        print(
                            f"[API] {done_count}/{len(todo)} fetched "
                            f"({elapsed:.1f}s, {rate:.1f} req/s)",
                            flush=True,
                        )

    # Ensure sample_stratum is attached to every cached record and save clean CSV
    api_rows = []
    for cno, stratum in query_meta.items():
        rec = dict(cached.get(cno, {"campno": cno, "http_status": -1}))
        rec["sample_stratum"] = stratum
        api_rows.append(rec)
    api_df = pd.DataFrame(api_rows)
    api_df.to_csv(PROC_DIR / "nhtsa_api_campaign_groundtruth.csv", index=False)

    # Measurement-Integrity Reconciliation Audit
    merged = camp.merge(api_df, left_on="CAMPNO", right_on="campno", how="inner")
    valid = merged[merged["api_ota_any"].notna()].copy()
    valid["api_ota_any"] = valid["api_ota_any"].astype(int)
    valid["api_ota_all"] = valid["api_ota_all"].astype(int)

    # Diagnose discrepancies!
    valid["txt_ota_pure_raw"] = ((valid["txt_ota_raw"] == 1) & (valid["txt_dealer"] == 0)).astype(int)
    valid["txt_ota_hybrid_raw"] = ((valid["txt_ota_raw"] == 1) & (valid["txt_dealer"] == 1)).astype(int)

    # Check API overTheAirUpdate rate by rec_year among text-OTA recalls (did NHTSA add/enforce field in 2022/2023?)
    txt_ota = valid[valid["txt_ota_raw"] == 1].copy()
    by_year_reconcil = (
        txt_ota.groupby("rec_year")
        .agg(
            n_txt_ota=("CAMPNO", "count"),
            n_api_true=("api_ota_any", "sum"),
            api_true_rate=("api_ota_any", "mean"),
            n_pure_txt=("txt_ota_pure_raw", "sum"),
            n_hybrid_txt=("txt_ota_hybrid_raw", "sum"),
        )
        .reset_index()
        .to_dict("records")
    )
    by_oem_reconcil = (
        txt_ota.groupby("mfg")
        .agg(
            n_txt_ota=("CAMPNO", "count"),
            n_api_true=("api_ota_any", "sum"),
            api_true_rate=("api_ota_any", "mean"),
        )
        .sort_values("n_txt_ota", ascending=False)
        .head(15)
        .reset_index()
        .to_dict("records")
    )

    # Physical audit false-negative check
    phys_val = valid[valid["sample_stratum"] == "physical_audit_sample"]
    cand_val = valid[valid["sample_stratum"] == "sw_ota_candidate"]

    # Check campaigns where API=True but text-OTA=0 (missed by regex!)
    api_true_txt_zero = valid[(valid["api_ota_any"] == 1) & (valid["txt_ota_raw"] == 0)]
    # Check campaigns where text-OTA=1 (pure) but API=False (Wave-1 discrepancy!)
    txt_pure_api_zero = valid[(valid["txt_ota_pure_raw"] == 1) & (valid["api_ota_any"] == 0)]
    txt_hyb_api_zero = valid[(valid["txt_ota_hybrid_raw"] == 1) & (valid["api_ota_any"] == 0)]
    partial_ota = valid[(valid["api_ota_any"] == 1) & (valid["api_ota_all"] == 0)]

    # Chronological 2025-2026 cutoff split around final API=True filing (May 8, 2025)
    txt_ota_2025_26 = txt_ota[txt_ota["rec_year"].isin([2025, 2026])].copy()
    cutoff_dt = pd.Timestamp("2025-05-08")
    pre_cut = txt_ota_2025_26[txt_ota_2025_26["rec_date"] <= cutoff_dt]
    post_cut = txt_ota_2025_26[txt_ota_2025_26["rec_date"] > cutoff_dt]
    last_api_true_row = (
        txt_ota[txt_ota["api_ota_any"] == 1].sort_values("rec_date").tail(1)[["CAMPNO", "mfg", "rec_date"]]
    )
    last_api_true_info = (
        {
            "campno": str(last_api_true_row["CAMPNO"].iloc[0]),
            "mfg": str(last_api_true_row["mfg"].iloc[0]),
            "rec_date": str(last_api_true_row["rec_date"].iloc[0].date()),
        }
        if len(last_api_true_row)
        else None
    )

    audit = {
        "generated_utc": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "n_total_queried": len(api_df),
        "n_http_200_valid": len(valid),
        "n_http_errors": int((api_df["http_status"] != 200).sum()),
        "candidates_valid": len(cand_val),
        "candidates_api_ota_true": int(cand_val["api_ota_any"].sum()),
        "candidates_api_ota_partial_across_models": len(partial_ota),
        "physical_audit_valid": len(phys_val),
        "physical_audit_api_ota_true_false_negatives": int(phys_val["api_ota_any"].sum()),
        "physical_audit_fn_rate": round(float(phys_val["api_ota_any"].mean()), 5) if len(phys_val) else None,
        "txt_ota_raw_total": len(txt_ota),
        "txt_ota_raw_api_true": int(txt_ota["api_ota_any"].sum()),
        "txt_ota_pure_total": int((valid["txt_ota_pure_raw"] == 1).sum()),
        "txt_ota_pure_api_true": int(valid[valid["txt_ota_pure_raw"] == 1]["api_ota_any"].sum()),
        "txt_ota_hybrid_total": int((valid["txt_ota_hybrid_raw"] == 1).sum()),
        "txt_ota_hybrid_api_true": int(valid[valid["txt_ota_hybrid_raw"] == 1]["api_ota_any"].sum()),
        "last_api_ota_true_campaign": last_api_true_info,
        "cutoff_2025_early_jan1_to_may8": {
            "n_txt_ota": len(pre_cut),
            "n_api_true": int(pre_cut["api_ota_any"].sum()),
            "api_true_rate": round(float(pre_cut["api_ota_any"].mean()), 4) if len(pre_cut) else None,
        },
        "cutoff_post_may8_2025_through_2026": {
            "n_txt_ota": len(post_cut),
            "n_api_true": int(post_cut["api_ota_any"].sum()),
            "api_true_rate": round(float(post_cut["api_ota_any"].mean()), 4) if len(post_cut) else None,
        },
        "api_true_but_txt_zero_count": len(api_true_txt_zero),
        "api_true_but_txt_zero_examples": api_true_txt_zero[
            ["CAMPNO", "mfg", "rec_year", "corrective_action"]
        ].head(10).to_dict("records"),
        "txt_pure_but_api_zero_count": len(txt_pure_api_zero),
        "txt_pure_but_api_zero_by_year": txt_pure_api_zero["rec_year"].value_counts().sort_index().to_dict(),
        "txt_pure_but_api_zero_examples": txt_pure_api_zero[
            ["CAMPNO", "mfg", "rec_year", "corrective_action"]
        ].head(12).to_dict("records"),
        "txt_hybrid_but_api_zero_count": len(txt_hyb_api_zero),
        "txt_hybrid_but_api_zero_by_year": txt_hyb_api_zero["rec_year"].value_counts().sort_index().to_dict(),
        "txt_ota_reconciliation_by_year": by_year_reconcil,
        "txt_ota_reconciliation_by_top_oem": by_oem_reconcil,
        "n_with_odi_action_number": int((valid["nhtsa_action_number"].fillna("") != "").sum()),
        "n_api_park_it": int(valid["api_park_it"].sum()),
        "n_api_park_outside": int(valid["api_park_outside"].sum()),
    }
    out_audit = RES_DIR / "api_reconciliation_audit.json"
    out_audit.write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print(f"[DONE] Saved API reconciliation audit -> {out_audit}", flush=True)
    print(
        json.dumps(
            {
                k: v
                for k, v in audit.items()
                if not k.endswith("_examples") and not k.endswith("_by_top_oem")
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
