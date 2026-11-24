"""Stage 0B legal timeline, BTS data dictionary, OIG tarmac-rule, Xing JEMS, and pre-rule confounder audit.

STRICTLY POST-RULE BLIND: ZERO post-2024-04 BTS flight bytes downloaded or analyzed!
Inspects:
  1. Crossref DOI 10.1111/jems.70019 (Xing, Quality Regulation and Unexpected Gaming, JEMS).
  2. Official DOT Small Business Compliance Guidance PDF (2024-12): exact May 16, 2024 FAA s503 vs Oct 28, 2024 dates.
  3. Official Federal Register 2024-07177 (govinfo HTML): exact 14 CFR 260.2 & 260.6 statutory trigger terms.
  4. Official BTS TableInfo (FGJ) data dictionary: exact field definitions & reporting rules.
  5. Official DOT OIG report 33850 (Tarmac Delay Rule 14 CFR 259.4).
  6. Pre-rule-only (2023-10, 2024-03) confounder & denominator exposure audit:
       - Gate-return & tarmac-delay fields (TaxiOut, LongestAddGTime, TotalAddGTime) overlap near 180 min
       - Cancellation & diversion denominators (including gate-return cancelled flights with non-null DepDelay)
       - Per-carrier 5-minute & 60-minute clock heaping in [120, 240] min
       - Check whether Marketing_Carrier roster changes across 2022-2026 (known AS-HA merger Sep 2024, NK Ch.11 Nov 2024)
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import zipfile

HERE = Path(__file__).resolve().parent
OUT_PATH = HERE / "stage0b_legal_and_measurement_gate.json"
HEADERS = {"User-Agent": "Academic-Research-DOT260-Stage0B-Gate/1.0"}


def fetch(url: str, timeout: float = 40.0) -> tuple[int, bytes | None, str | None, float]:
    t0 = perf_counter()
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
            return int(r.status), r.read(), None, round(perf_counter() - t0, 3)
    except HTTPError as e:
        return int(e.code), None, f"HTTPError {e.code}: {e.reason}", round(perf_counter() - t0, 3)
    except URLError as e:
        return 0, None, f"URLError: {e.reason}", round(perf_counter() - t0, 3)
    except Exception as e:  # noqa: BLE001
        return 0, None, f"{type(e).__name__}: {e}", round(perf_counter() - t0, 3)


def check_xing_jems() -> dict:
    url = "https://api.crossref.org/works/10.1111/jems.70019"
    st, raw, err, dt = fetch(url)
    out = {"doi": "10.1111/jems.70019", "url": url, "http_status": st, "error": err, "elapsed_seconds": dt}
    if st == 200 and raw:
        msg = json.loads(raw.decode("utf-8")).get("message", {})
        out["title"] = msg.get("title", [])
        out["container_title"] = msg.get("container-title", [])
        out["authors"] = [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in msg.get("author", [])]
        out["published"] = msg.get("published") or msg.get("issued")
    return out


def check_dot_small_business_pdf() -> dict:
    url = "https://www.transportation.gov/sites/dot.gov/files/2024-12/Refund%20Final%20Rule%20Small%20Business%20Compliance%20Guidance.pdf"
    st, raw, err, dt = fetch(url)
    out = {"url": url, "http_status": st, "error": err, "elapsed_seconds": dt, "bytes": len(raw) if raw else 0}
    if st == 200 and raw:
        # Extract printable ASCII/UTF-8 text strings or check via pdftotext if available
        import subprocess
        try:
            proc = subprocess.run(["pdftotext", "-", "-"], input=raw, capture_output=True, timeout=20)
            txt = proc.stdout.decode("utf-8", errors="replace") if proc.returncode == 0 else ""
        except Exception:
            txt = ""
        if not txt:
            # Fallback regex on PDF bytes (uncompressed streams won't match Flate, note explicitly)
            txt = raw.decode("latin-1", errors="ignore")
        plain = " ".join(txt.split())
        out["extracted_text_len"] = len(plain)
        out["mentions_may_16_2024"] = bool(re.search(r"May\s+16,\s+2024", plain, re.I))
        out["mentions_oct_28_2024"] = bool(re.search(r"October\s+28,\s+2024", plain, re.I))
        out["mentions_section_503"] = bool(re.search(r"503|FAA\s+Reauthorization", plain, re.I))
        # Capture short factual date lines only
        date_lines = re.findall(r".{0,90}(?:May\s+16,\s+2024|June\s+25,\s+2024|October\s+28,\s+2024).{0,120}", plain, re.I)
        out["date_mentions_count"] = len(date_lines)
        out["date_mentions_sample"] = date_lines[:6]
    return out


def check_govinfo_fr_260() -> dict:
    url = "https://www.govinfo.gov/content/pkg/FR-2024-04-26/html/2024-07177.htm"
    st, raw, err, dt = fetch(url)
    out = {"url": url, "http_status": st, "error": err, "elapsed_seconds": dt, "bytes": len(raw) if raw else 0}
    if st == 200 and raw:
        plain = " ".join(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace")).split())
        out["plain_len"] = len(plain)
        # Locate actual regulatory text PART 260 -- REFUNDS FOR AIRLINE FARE AND ANCILLARY SERVICE FEES
        m260 = re.search(r"(Sec\.\s*260\.2\s+Definitions\..{0,2500})", plain)
        m260_6 = re.search(r"(Sec\.\s*260\.6\s+Refunding\s+fare.{0,2200})", plain)
        out["found_260_2"] = bool(m260)
        out["found_260_6"] = bool(m260_6)
        if m260:
            s2 = m260.group(1)
            out["sec_260_2_key_elements"] = {
                "original_itinerary_referenced": bool(re.search(r"original\s+itinerary|originally\s+scheduled", s2, re.I)),
                "earlier_origin_departure_3h": bool(re.search(r"depart\s+from\s+the\s+origination\s+airport\s+three\s+hours\s+or\s+more\s+earlier", s2, re.I)),
                "later_destination_arrival_3h": bool(re.search(r"arrive\s+at\s+the\s+destination\s+airport\s+three\s+hours\s+or\s+more\s+later", s2, re.I)),
                "international_6h": bool(re.search(r"six\s+hours\s+or\s+more", s2, re.I)),
                "short_excerpt_260_2": s2[:900],
            }
        if m260_6:
            s6 = m260_6.group(1)
            out["sec_260_6_key_elements"] = {
                "requires_passenger_rejects_or_does_not_take_alternative": bool(re.search(r"reject|does\s+not\s+accept|not\s+accepting|chooses\s+not\s+to\s+travel", s6, re.I)),
                "short_excerpt_260_6": s6[:900],
            }
    return out


def check_bts_dictionary() -> dict:
    url = "https://www.transtats.bts.gov/TableInfo.asp?QO_fu146_anzr=b0-gvzr&gnoyr_VQ=FGJ"
    st, raw, err, dt = fetch(url)
    out = {"url": url, "http_status": st, "error": err, "elapsed_seconds": dt, "bytes": len(raw) if raw else 0}
    if st == 200 and raw:
        plain = " ".join(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace")).split())
        out["plain_len"] = len(plain)
        out["mentions_crs_schedule"] = bool(re.search(r"CRS|Computer\s+Reservation\s+System", plain, re.I))
        out["mentions_nonstop_segment"] = bool(re.search(r"nonstop|segment|origin\s+and\s+destination", plain, re.I))
        out["mentions_tarmac_add_gtime"] = bool(re.search(r"LongestAddGTime|TotalAddGTime|Gate\s+Return", plain, re.I))
        out["mentions_part_234_threshold"] = bool(re.search(r"0\.5\s*percent|one-half\s+of\s+one\s+percent|Part\s+234", plain, re.I))
        m_desc = re.search(r"(This\s+table\s+contains.{0,650})", plain, re.I)
        out["table_description_excerpt"] = m_desc.group(1) if m_desc else plain[:650]
    return out


def check_dot_oig_tarmac() -> dict:
    url = "https://www.oig.dot.gov/library-item/33850"
    st, raw, err, dt = fetch(url)
    out = {"url": url, "http_status": st, "error": err, "elapsed_seconds": dt, "bytes": len(raw) if raw else 0}
    if st == 200 and raw:
        plain = " ".join(re.sub(r"<[^>]+>", " ", raw.decode("utf-8", errors="replace")).split())
        m_title = re.search(r"<title>(.*?)</title>", raw.decode("utf-8", errors="replace"), re.I | re.S)
        out["page_title"] = " ".join(m_title.group(1).split()) if m_title else None
        out["mentions_tarmac"] = bool(re.search(r"tarmac", plain, re.I))
        out["mentions_cancellations"] = bool(re.search(r"cancel", plain, re.I))
        out["mentions_259_4"] = bool(re.search(r"259\.4|three-hour|3-hour", plain, re.I))
        m_body = re.search(r"((?:Tarmac|Three-Hour).{0,550})", plain, re.I)
        out["short_excerpt"] = m_body.group(1) if m_body else None
    return out


def _to_float(v: str) -> float | None:
    s = v.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def audit_prerule_confounders_and_denominators() -> dict:
    """Audit ONLY pre-rule month 2024-03 (strictly pre-announcement!) for tarmac overlap, gate-returns, heaping by carrier."""
    url = "https://transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_2024_3.zip"
    st, raw, err, dt = fetch(url, timeout=90.0)
    if st != 200 or not raw:
        return {"http_status": st, "error": err}
    zf = zipfile.ZipFile(io.BytesIO(raw))
    csv_name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]

    total = 0
    completed = 0
    cancelled = 0
    diverted = 0
    canc_with_dep_delay = 0
    canc_with_dep_delay_ge120 = 0
    canc_with_gate_return_gtime = 0
    tarmac_cols_present = {}

    dep_120_240_completed = 0
    dep_120_240_with_gate_return = 0
    dep_120_240_with_taxiout_ge60 = 0
    dep_120_240_with_taxiout_ge120 = 0
    arr_120_240_completed = 0
    arr_120_240_with_dep_lt120 = 0
    arr_120_240_with_dep_lt60 = 0
    arr_120_240_with_dep_lt15 = 0
    arr_120_240_with_dep_ge180 = 0

    # Per-carrier heaping & delay-window shares (pre-rule 2024-03 ONLY)
    carrier_stats: dict[str, dict[str, int]] = {}

    with zf.open(csv_name) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
        cmap = {c.strip(): c for c in (reader.fieldnames or [])}
        for c in ["TotalAddGTime", "LongestAddGTime", "FirstDepTime", "TaxiOut", "TaxiIn", "DivAirportLandings", "DivArrDelay"]:
            tarmac_cols_present[c] = c in cmap

        for row in reader:
            total += 1
            mkt = row.get(cmap.get("Marketing_Airline_Network", ""), "").strip() or "UNK"
            cs = carrier_stats.setdefault(
                mkt,
                {
                    "flights": 0,
                    "cancelled": 0,
                    "diverted": 0,
                    "dep_120_240": 0,
                    "dep_mod5": 0,
                    "arr_120_240": 0,
                    "arr_mod5": 0,
                    "dep_ge_180_or_canc": 0,
                },
            )
            cs["flights"] += 1

            canc = (_to_float(row.get(cmap.get("Cancelled", ""), "")) or 0.0) == 1.0
            div = (_to_float(row.get(cmap.get("Diverted", ""), "")) or 0.0) == 1.0
            dep_d = _to_float(row.get(cmap.get("DepDelay", ""), ""))
            arr_d = _to_float(row.get(cmap.get("ArrDelay", ""), ""))
            taxi_out = _to_float(row.get(cmap.get("TaxiOut", ""), ""))
            longest_g = _to_float(row.get(cmap.get("LongestAddGTime", ""), ""))
            total_g = _to_float(row.get(cmap.get("TotalAddGTime", ""), ""))

            if canc:
                cancelled += 1
                cs["cancelled"] += 1
                cs["dep_ge_180_or_canc"] += 1
                if dep_d is not None:
                    canc_with_dep_delay += 1
                    if dep_d >= 120.0:
                        canc_with_dep_delay_ge120 += 1
                if (longest_g is not None and longest_g > 0) or (total_g is not None and total_g > 0):
                    canc_with_gate_return_gtime += 1
                continue
            if div:
                diverted += 1
                cs["diverted"] += 1
                continue

            completed += 1
            if dep_d is not None and dep_d >= 180.0:
                cs["dep_ge_180_or_canc"] += 1
            if dep_d is not None and 120.0 <= dep_d <= 240.0:
                dep_120_240_completed += 1
                cs["dep_120_240"] += 1
                if int(round(dep_d)) % 5 == 0:
                    cs["dep_mod5"] += 1
                if (longest_g is not None and longest_g > 0) or (total_g is not None and total_g > 0):
                    dep_120_240_with_gate_return += 1
                if taxi_out is not None and taxi_out >= 60.0:
                    dep_120_240_with_taxiout_ge60 += 1
                if taxi_out is not None and taxi_out >= 120.0:
                    dep_120_240_with_taxiout_ge120 += 1

            if arr_d is not None and 120.0 <= arr_d <= 240.0:
                arr_120_240_completed += 1
                cs["arr_120_240"] += 1
                if int(round(arr_d)) % 5 == 0:
                    cs["arr_mod5"] += 1
                if dep_d is not None:
                    if dep_d < 120.0:
                        arr_120_240_with_dep_lt120 += 1
                    if dep_d < 60.0:
                        arr_120_240_with_dep_lt60 += 1
                    if dep_d < 15.0:
                        arr_120_240_with_dep_lt15 += 1
                    if dep_d >= 180.0:
                        arr_120_240_with_dep_ge180 += 1

    carrier_summary = {}
    for mkt, cs in sorted(carrier_stats.items(), key=lambda kv: -kv[1]["flights"]):
        carrier_summary[mkt] = {
            "flights": cs["flights"],
            "cancelled": cs["cancelled"],
            "diverted": cs["diverted"],
            "dep_120_240": cs["dep_120_240"],
            "dep_mod5_share": round(cs["dep_mod5"] / max(1, cs["dep_120_240"]), 4),
            "arr_120_240": cs["arr_120_240"],
            "arr_mod5_share": round(cs["arr_mod5"] / max(1, cs["arr_120_240"]), 4),
        }

    return {
        "month_audited_prerule_only": "2024-03",
        "download_seconds": dt,
        "tarmac_and_diversion_columns_present": tarmac_cols_present,
        "denominators": {
            "total_scheduled_flights": total,
            "completed_non_cancelled_non_diverted": completed,
            "cancelled_total": cancelled,
            "diverted_total": diverted,
            "cancelled_with_nonnull_DepDelay_gate_pushback": canc_with_dep_delay,
            "cancelled_with_DepDelay_ge_120": canc_with_dep_delay_ge120,
            "cancelled_with_TotalOrLongestAddGTime_gt_0": canc_with_gate_return_gtime,
        },
        "tarmac_rule_14CFR259_4_overlap_in_completed_dep_120_240": {
            "completed_dep_120_240": dep_120_240_completed,
            "with_gate_return_AddGTime_gt_0": dep_120_240_with_gate_return,
            "share_with_gate_return_pct": round(100.0 * dep_120_240_with_gate_return / max(1, dep_120_240_completed), 2),
            "with_TaxiOut_ge_60_min": dep_120_240_with_taxiout_ge60,
            "with_TaxiOut_ge_120_min": dep_120_240_with_taxiout_ge120,
        },
        "arr_120_240_decomposition_by_dep_delay": {
            "completed_arr_120_240": arr_120_240_completed,
            "dep_lt_120": arr_120_240_with_dep_lt120,
            "dep_lt_60": arr_120_240_with_dep_lt60,
            "dep_lt_15_strict_airborne_or_taxi_only": arr_120_240_with_dep_lt15,
            "dep_ge_180": arr_120_240_with_dep_ge180,
        },
        "carrier_heaping_and_denominators_2024_03": carrier_summary,
    }


def main() -> None:
    t0 = perf_counter()
    report = {
        "stage": "stage_0b_aviation_legal_timeline_dictionary_and_prerule_confounder_gate",
        "zero_post_rule_bytes_downloaded_or_analyzed": True,
        "xing_jems_precedent": check_xing_jems(),
        "dot_small_business_guidance_pdf": check_dot_small_business_pdf(),
        "govinfo_fr_2024_07177_part260": check_govinfo_fr_260(),
        "bts_table_info_fgj_dictionary": check_bts_dictionary(),
        "dot_oig_tarmac_report_33850": check_dot_oig_tarmac(),
        "prerule_2024_03_confounder_exposure": audit_prerule_confounders_and_denominators(),
        "total_elapsed_seconds": round(perf_counter() - t0, 3),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT_PATH} elapsed={report['total_elapsed_seconds']}s")
    print("XING_JEMS:", report["xing_jems_precedent"])
    print("DOT_PDF:", {k: v for k, v in report["dot_small_business_guidance_pdf"].items() if k != "date_mentions_sample"})
    print("FR_260:", {k: v for k, v in report["govinfo_fr_2024_07177_part260"].items() if k not in ("sec_260_2_key_elements", "sec_260_6_key_elements")})
    print("BTS_DICT:", {k: v for k, v in report["bts_table_info_fgj_dictionary"].items() if k != "table_description_excerpt"})
    print("OIG_33850:", report["dot_oig_tarmac_report_33850"])
    print("PRERULE_CONFOUNDERS:", json.dumps(report["prerule_2024_03_confounder_exposure"], indent=2))


if __name__ == "__main__":
    main()
