"""Step 1: Full 48-state CONUS (+DC) USGS continuous DO site discovery & rigorous exclusion audit."""
from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pandas as pd
import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
META_DIR = BASE_DIR / "data" / "raw_usgs_meta"
PROC_DIR = BASE_DIR / "data" / "processed"
UA = {"User-Agent": "AcademicResearch-NocturnalRiverHypoxiaAudit/2.0 (contact: hydrology-audit@research.org)"}

CONUS_STATES = [
    "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA",
    "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME",
    "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ",
    "NM", "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD",
    "TN", "TX", "UT", "VA", "VT", "WA", "WI", "WV", "WY",
]

# Known forensic Round-1 dam/lake sites (must be caught automatically by general regex too)
KNOWN_FORENSIC_EXCLUDED = {"0212880025", "03220510", "421401121480900", "03036000"}

# Systematic hydrologic exclusion rules (applied to uppercased station_nm)
# Carefully uses word boundaries so town names like "DAMASCUS" or "AMSTERDAM" are NOT false-flagged.
EXCLUSION_RULES: list[tuple[str, re.Pattern[str]]] = [
    (
        "klamath_system",
        re.compile(r"\b(KLAMATH|LINK\s+R|LINK\s+RIVER|KENO|UPPER\s+KLAMATH|AGENCY\s+LAKE)\b"),
    ),
    (
        "dam_tailrace_lock_infra",
        re.compile(
            r"\b(DAM|TAILRACE|TAILWATER|POWERHOUSE|PWRHOUSE|POWER\s*PLANT|SPILLWAY|"
            r"FOREBAY|AFTERBAY|OUTFLOW|OUTLET|LOCK\s*(?:AND|&)?\s*DAM|L\s*&\s*D\d*|L&D\d*|"
            r"LOCK\s+NO\.?|LOCK\s+\d+|LOCK\s+CHANNEL|HYDRO|TURBINE|PENSTOCK|SLUICE|WEIR|BARRAGE|"
            r"DIVERSION|INTAKE|OUTFALL|RELEASE|CONTROL\s+STRUCT|STRUCTURE\s+S-?\d+|"
            r"(?:AT|NR|NEAR|BELOW|BLW|ABOVE|ABV)\s+S-\d+|BUGGS\s+ISLAND|"
            r"SPILL\s*WAY|POWER\s*STA|GENERATING|WWTP|WASTEWATER|EFFLUENT|SEWAGE|"
            r"TREATMENT\s*PL(?:A?NT|T)|WTR\s*PL(?:A?NT|T)|STP|WRF|WRP|"
            r"BLW\s+.*RES|BELOW\s+.*RES|BLW\s+.*LK|BELOW\s+.*LK|"
            r"BLW\s+.*LAKE|BELOW\s+.*LAKE|BELOW\s+.*POOL|BLW\s+.*POOL|DISCHARGE\s+CANAL)\b"
        ),
    ),
    (
        "lake_reservoir_impoundment",
        re.compile(
            r"\b(LAKE|LK|RESERVOIR|RES|IMPOUNDMENT|POND|POOL\s+\d+|POOL\s+NO|"
            r"LOWER\s+POOL|UPPER\s+POOL|UPSTREAM\s+POOL|DOWNSTREAM\s+POOL|"
            r"BACKWATER|BASIN\s+OUTFLOW|RETENTION|DETENTION|QUARRY|PIT|"
            r"AT\s+[A-Z]+\s+SPRING\b)\b"
        ),
    ),
    (
        "estuary_tidal_coastal",
        re.compile(
            r"\b(TIDAL|ESTUARY|ESTUARINE|INTRACOASTAL|ICW|SOUND|HARBOR|HARBOUR|MARINA|"
            r"INLET|SLOUGH|BRACKISH|SALTWATER|SALT\s+WATER|OCEAN|GULF|COVE|"
            r"STRAIT|SHIP\s+CHANNEL|NAVIGATION\s+CHANNEL|BAYOU|LAGOON|BIGHT|"
            r"PASS\s+AT|MARSH|SWAMP|MANGROVE|DELAWARE\s+BAY|DELAWARE\s+RIVER\s+AT\s+CHESTER|"
            r"CHESAPEAKE\s+BAY|TAMPA\s+BAY|MOBILE\s+BAY|GALVESTON\s+BAY|SAN\s+FRANCISCO\s+BAY|"
            r"PUGET\s+SOUND|ALBEMARLE\s+SOUND|PAMLICO\s+SOUND|GREEN\s+BAY|DAMES\s+POINT|"
            r"CAPE\s+FEAR.*EST|AT\s+MOUTH|NR\s+MOUTH|NEAR\s+MOUTH|BAY\s+AT|BAY\s+NR|BAY\s+NEAR)\b"
        ),
    ),
    (
        "canal_ditch_conveyance",
        re.compile(
            r"\b(CANAL|DITCH|AQUEDUCT|FLUME|BYPASS|FLOODWAY|CONVEYANCE|"
            r"LATERAL|SIPHON|PUMP\s*STA|PUMPING|DRAINAGE\s+DITCH|DRAIN\s+AT|DRAIN\s+NR|"
            r"WATERWAY|CUTOFF|CHANNELIZATION|STORM\s*DRAIN|CULVERT|SEWER)\b"
        ),
    ),
]

# Secondary ultra-strict flag (for sensitivity check: flags even weak hints like SPRING, BAY, POOL, LOCK, GATE)
ULTRA_STRICT_RE = re.compile(
    r"\b(SPRING|SPRINGS|BAY|POOL|LOCK|GATE|GATES|MILL|MILLPOND|PLANT|STATION|"
    r"BRIDGE\s+AT\s+DAM|FALLS\s+DAM|HEADRACE|RACEWAY|LEVEE|DIKE|JETTY|PIER|WHARF|DOCK)\b"
)


def fetch_rdb(url: str, timeout: tuple[int, int] = (10, 45)) -> str | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r.text
            if r.status_code == 404:
                return ""
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2.5 * (attempt + 1))
            else:
                return None
        except requests.RequestException:
            time.sleep(2.5 * (attempt + 1))
    return None


def parse_rdb_table(text: str) -> tuple[list[str], list[list[str]]]:
    lines = [ln for ln in text.splitlines() if not ln.startswith("#") and ln.strip()]
    if len(lines) < 3:
        return [], []
    hdr = lines[0].split("\t")
    rows = [ln.split("\t") for ln in lines[2:]]
    return hdr, rows


def discover_state(st: str) -> dict:
    exp_cache = META_DIR / f"site_exp_{st}.rdb"
    cat_cache = META_DIR / f"site_cat_{st}.rdb"

    if exp_cache.exists():
        exp_txt = exp_cache.read_text(encoding="utf-8", errors="replace")
    else:
        url_exp = (
            f"https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd={st}"
            "&parameterCd=00300&hasDataTypeCd=dv&siteStatus=all&siteOutput=expanded"
        )
        exp_txt = fetch_rdb(url_exp) or ""
        exp_cache.write_text(exp_txt, encoding="utf-8")

    if cat_cache.exists():
        cat_txt = cat_cache.read_text(encoding="utf-8", errors="replace")
    else:
        url_cat = (
            f"https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd={st}"
            "&parameterCd=00300&hasDataTypeCd=dv&siteType=ST&siteStatus=all&seriesCatalogOutput=true"
        )
        cat_txt = fetch_rdb(url_cat) or ""
        cat_cache.write_text(cat_txt, encoding="utf-8")

    # Parse expanded metadata
    exp_hdr, exp_rows = parse_rdb_table(exp_txt)
    exp_map: dict[str, dict] = {}
    if exp_hdr:
        eidx = {h: i for i, h in enumerate(exp_hdr)}
        for parts in exp_rows:
            if len(parts) <= eidx.get("site_no", 1):
                continue
            sno = parts[eidx["site_no"]].strip()
            def _g(col: str, _parts: list[str] = parts) -> str:
                j = eidx.get(col, -1)
                return _parts[j].strip() if 0 <= j < len(_parts) else ""
            exp_map[sno] = {
                "site_no": sno,
                "state": st,
                "station_nm": _g("station_nm"),
                "site_tp_cd": _g("site_tp_cd"),
                "lat": _g("dec_lat_va"),
                "lon": _g("dec_long_va"),
                "alt_va": _g("alt_va"),
                "alt_datum_cd": _g("alt_datum_cd"),
                "huc_cd": _g("huc_cd"),
                "drain_area_va": _g("drain_area_va"),
                "tz_cd": _g("tz_cd"),
                "county_cd": _g("county_cd"),
            }

    # Parse series catalog across parameters (00300, 00010, 00060, 00095, 63680)
    cat_hdr, cat_rows = parse_rdb_table(cat_txt)
    series: dict[str, dict] = {}
    if cat_hdr:
        cidx = {h: i for i, h in enumerate(cat_hdr)}
        for parts in cat_rows:
            if len(parts) <= cidx.get("site_no", 1):
                continue
            sno = parts[cidx["site_no"]].strip()
            def _cg(col: str, _parts: list[str] = parts) -> str:
                j = cidx.get(col, -1)
                return _parts[j].strip() if 0 <= j < len(_parts) else ""
            dt_cd = _cg("data_type_cd")
            if dt_cd != "dv":
                continue
            pcode = _cg("parm_cd")
            scd = _cg("stat_cd")
            bdt = _cg("begin_date")
            edt = _cg("end_date")
            cnt = int(_cg("count_nu")) if _cg("count_nu").isdigit() else 0

            rec = series.setdefault(
                sno,
                {
                    "do_stats": set(),
                    "do_counts": {},
                    "do_begin": "9999-99-99",
                    "do_end": "0000-00-00",
                    "temp_mean_cnt": 0,
                    "temp_minmax_ok": False,
                    "temp_stats": set(),
                    "q_mean_cnt": 0,
                    "spcond_cnt": 0,
                    "turb_cnt": 0,
                },
            )
            if pcode == "00300" and scd in ("00001", "00002", "00003"):
                rec["do_stats"].add(scd)
                rec["do_counts"][scd] = max(rec["do_counts"].get(scd, 0), cnt)
                if bdt and bdt < rec["do_begin"]:
                    rec["do_begin"] = bdt
                if edt and edt > rec["do_end"]:
                    rec["do_end"] = edt
            elif pcode == "00010":
                rec["temp_stats"].add(scd)
                if scd == "00003":
                    rec["temp_mean_cnt"] = max(rec["temp_mean_cnt"], cnt)
            elif pcode == "00060" and scd == "00003":
                rec["q_mean_cnt"] = max(rec["q_mean_cnt"], cnt)
            elif pcode == "00095" and scd == "00003":
                rec["spcond_cnt"] = max(rec["spcond_cnt"], cnt)
            elif pcode == "63680" and scd == "00003":
                rec["turb_cnt"] = max(rec["turb_cnt"], cnt)

    merged = []
    for sno, meta in exp_map.items():
        sr = series.get(sno)
        if sr is None:
            # Non-ST site (excluded at catalog level because siteType=ST filtered) — still record for audit!
            row = dict(meta)
            row.update(
                {
                    "has_all_do_stats": 0,
                    "min_do_cnt": 0,
                    "do_begin": "",
                    "do_end": "",
                    "temp_mean_cnt": 0,
                    "has_temp_minmax": 0,
                    "q_mean_cnt": 0,
                    "spcond_cnt": 0,
                    "turb_cnt": 0,
                }
            )
            merged.append(row)
            continue
        do_stats = sr["do_stats"]
        has_all_do = len(do_stats) == 3
        min_do_cnt = min(sr["do_counts"].values()) if has_all_do else 0
        row = dict(meta)
        row.update(
            {
                "has_all_do_stats": int(has_all_do),
                "min_do_cnt": int(min_do_cnt),
                "do_begin": sr["do_begin"],
                "do_end": sr["do_end"],
                "temp_mean_cnt": int(sr["temp_mean_cnt"]),
                "has_temp_minmax": int({"00001", "00002"}.issubset(sr["temp_stats"])),
                "q_mean_cnt": int(sr["q_mean_cnt"]),
                "spcond_cnt": int(sr["spcond_cnt"]),
                "turb_cnt": int(sr["turb_cnt"]),
            }
        )
        merged.append(row)
    return {"state": st, "n_raw_sites": len(exp_map), "n_dv_sites": len(merged), "rows": merged}


def classify_site(row: dict) -> tuple[bool, list[str]]:
    """Return (is_eligible_clean_river, list_of_exclusion_reasons)."""
    reasons: list[str] = []

    # 1. Strict site_tp_cd == ST (excludes ST-TS tidal, ST-CA canal, ST-DCH ditch, LK lake, ES estuary, SP spring, etc.)
    if row["site_tp_cd"] != "ST":
        reasons.append(f"site_type_{row['site_tp_cd'] or 'EMPTY'}")

    # 2. Record completeness (pre-locked metadata rules, zero outcome peeking)
    if not row["has_all_do_stats"]:
        reasons.append("missing_do_max_min_mean")
    if row["min_do_cnt"] < 1000:
        reasons.append("short_do_record_lt_1000d")
    if row["temp_mean_cnt"] < 1000:
        reasons.append("short_temp_record_lt_1000d")
    if row["do_end"] < "2010-01-01" or row["do_begin"] > "2023-01-01":
        reasons.append("outside_2005_2025_window")

    # 3. Geographic CONUS & HUC-2 validity
    try:
        lat = float(row["lat"])
        lon = float(row["lon"])
        if not (24.0 <= lat <= 49.5 and -125.0 <= lon <= -66.5):
            reasons.append("outside_conus_bbox")
    except (ValueError, TypeError):
        reasons.append("invalid_coords")

    huc2 = str(row.get("huc_cd", "")).strip()[:2]
    if not (huc2.isdigit() and 1 <= int(huc2) <= 18):
        reasons.append("invalid_huc2")

    # 4. Systematic dam / tailrace / lake / reservoir / estuary / canal / Klamath exclusion
    nm_up = str(row.get("station_nm", "")).upper()
    for tag, pat in EXCLUSION_RULES:
        if pat.search(nm_up):
            reasons.append(tag)

    # Check if any Round-1 known forensic site somehow slipped past regex (belt-and-suspenders)
    sno_z = str(row["site_no"]).strip()
    if sno_z in KNOWN_FORENSIC_EXCLUDED and not any(
        r in ("dam_tailrace_lock_infra", "lake_reservoir_impoundment", "klamath_system", "estuary_tidal_coastal")
        or r.startswith("site_type_")
        for r in reasons
    ):
        reasons.append("known_forensic_dam_site")

    return (len(reasons) == 0), reasons


def main() -> None:
    print(f"Discovering USGS continuous DO sites across {len(CONUS_STATES)} CONUS jurisdictions...", flush=True)
    all_rows: list[dict] = []
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, res in enumerate(ex.map(discover_state, CONUS_STATES), 1):
            all_rows.extend(res["rows"])
            if i % 5 == 0 or i == len(CONUS_STATES):
                print(
                    f"  [{i:2d}/{len(CONUS_STATES)}] last={res['state']} "
                    f"(raw={res['n_raw_sites']}, dv={res['n_dv_sites']}) | cumulative={len(all_rows)}",
                    flush=True,
                )

    raw_df = pd.DataFrame(all_rows).drop_duplicates(subset=["site_no"]).copy()
    raw_df["huc2"] = raw_df["huc_cd"].astype(str).str.strip().str[:2]
    raw_df["hash_key"] = raw_df["site_no"].astype(str).map(lambda s: hashlib.sha256(s.encode()).hexdigest())
    raw_df["ultra_strict_flagged"] = raw_df["station_nm"].astype(str).str.upper().map(
        lambda nm: int(bool(ULTRA_STRICT_RE.search(nm)))
    )

    clean_rows = []
    excluded_rows = []
    forensic_audit = {}

    for rec in raw_df.to_dict("records"):
        ok, reasons = classify_site(rec)
        rec["exclusion_reasons"] = ";".join(reasons)
        sno_s = str(rec["site_no"]).strip()
        if sno_s in KNOWN_FORENSIC_EXCLUDED:
            forensic_audit[sno_s] = {
                "station_nm": rec["station_nm"],
                "site_tp_cd": rec["site_tp_cd"],
                "excluded": not ok,
                "reasons": reasons,
            }
        if ok:
            clean_rows.append(rec)
        else:
            # Log excluded sites that had >= 1000 DO days (hydrologically relevant exclusions) OR all exclusions
            excluded_rows.append(rec)

    clean_df = pd.DataFrame(clean_rows).sort_values(["state", "huc2", "site_no"]).reset_index(drop=True)
    excl_df = pd.DataFrame(excluded_rows).sort_values(["state", "site_no"]).reset_index(drop=True)

    # Save tables
    raw_df.to_csv(PROC_DIR / "conus_all_discovered_do_sites.csv", index=False)
    clean_df.to_csv(PROC_DIR / "conus_clean_eligible_rivers.csv", index=False)
    excl_df.to_csv(PROC_DIR / "excluded_sites_audit.csv", index=False)

    # Compute exclusion breakdown among sites that passed basic >=1000d DO+Temp record length
    long_enough = raw_df[
        (raw_df["has_all_do_stats"] == 1)
        & (raw_df["min_do_cnt"] >= 1000)
        & (raw_df["temp_mean_cnt"] >= 1000)
        & (raw_df["do_end"] >= "2010-01-01")
        & (raw_df["do_begin"] <= "2023-01-01")
    ].copy()
    excl_hydro_only = excl_df[excl_df["site_no"].isin(long_enough["site_no"])]
    reason_counts: dict[str, int] = {}
    for rs in excl_hydro_only["exclusion_reasons"]:
        for tok in str(rs).split(";"):
            if tok:
                reason_counts[tok] = reason_counts.get(tok, 0) + 1

    summary = {
        "n_jurisdictions_queried": len(CONUS_STATES),
        "n_total_discovered_dv_do_sites": len(raw_df),
        "n_meeting_record_length_before_hydro_filter": len(long_enough),
        "n_excluded_by_hydro_or_type_filter": len(excl_hydro_only),
        "hydro_exclusion_reason_counts": dict(sorted(reason_counts.items(), key=lambda kv: -kv[1])),
        "n_clean_eligible_rivers": len(clean_df),
        "n_clean_states": int(clean_df["state"].nunique()),
        "n_clean_huc2_basins": int(clean_df["huc2"].nunique()),
        "n_clean_with_q_catalog": int((clean_df["q_mean_cnt"] >= 1000).sum()),
        "n_clean_with_temp_minmax": int((clean_df["has_temp_minmax"] == 1).sum()),
        "n_clean_with_spcond": int((clean_df["spcond_cnt"] >= 1000).sum()),
        "n_clean_with_turb": int((clean_df["turb_cnt"] >= 1000).sum()),
        "n_clean_long_10yr_3000d": int((clean_df["min_do_cnt"] >= 3000).sum()),
        "n_clean_ultra_strict_zero_infra": int((clean_df["ultra_strict_flagged"] == 0).sum()),
        "clean_rivers_by_huc2": clean_df["huc2"].value_counts().sort_index().to_dict(),
        "clean_rivers_by_state": clean_df["state"].value_counts().to_dict(),
        "known_forensic_round1_audit": forensic_audit,
    }
    out_js = PROC_DIR / "step1_site_discovery_summary.json"
    out_js.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== STEP 1 CONUS SITE DISCOVERY SUMMARY ===", flush=True)
    print(json.dumps(summary, indent=2), flush=True)


if __name__ == "__main__":
    main()
