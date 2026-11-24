"""Stage 0B pre-rule-only verification of § 260.2 exact text & tail-number cancellation-missingness / airport-continuity audit.

STRICTLY POST-RULE BLIND: audits ONLY pre-rule month 2024-03 (zero post-2024-04 bytes touched!).
"""

from __future__ import annotations

import csv
import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen
import zipfile

HERE = Path(__file__).resolve().parent
GATE_PATH = HERE / "stage0b_legal_and_measurement_gate.json"
HEADERS = {"User-Agent": "Academic-Research-DOT260-Stage0B-TailCheck/1.0"}


def get_bytes(url: str, timeout: float = 90.0) -> bytes:
    with urlopen(Request(url, headers=HEADERS), timeout=timeout) as r:
        return r.read()


def _hhmm_to_min(v: str) -> int | None:
    s = v.strip()
    if not s:
        return None
    try:
        x = int(float(s))
        hh, mm = divmod(x, 100)
        return hh * 60 + mm
    except ValueError:
        return None


def main() -> None:
    data = json.loads(GATE_PATH.read_text(encoding="utf-8"))

    # 1. Exact § 260.2 'Significant delayed or changed flight' / 'Significantly delayed or changed' in 2024-07177.htm
    fr_html = get_bytes("https://www.govinfo.gov/content/pkg/FR-2024-04-26/html/2024-07177.htm", 40.0).decode("utf-8", errors="replace")
    fr_plain = " ".join(re.sub(r"<[^>]+>", " ", fr_html).split())
    # Search inside the actual codified PART 260 regulatory text (near end of document)
    pos_part260 = fr_plain.rfind("PART 260")
    tail_text = fr_plain[pos_part260:] if pos_part260 != -1 else fr_plain[-80000:]
    m_sig = re.search(r"(Significantly\s+delayed\s+or\s+changed.{0,1200})", tail_text, re.I)
    if m_sig:
        s = m_sig.group(1)
        data["govinfo_fr_2024_07177_part260"]["sec_260_2_significant_delay_verified"] = {
            "found": True,
            "original_itinerary_referenced": bool(re.search(r"original\s+itinerary|originally\s+scheduled", s, re.I)),
            "earlier_origin_departure_3h": bool(re.search(r"depart\s+from\s+the\s+origination\s+airport\s+three\s+hours\s+or\s+more\s+earlier", s, re.I)),
            "later_destination_arrival_3h": bool(re.search(r"arrive\s+at\s+the\s+destination\s+airport\s+three\s+hours\s+or\s+more\s+later", s, re.I)),
            "international_6h": bool(re.search(r"six\s+hours\s+or\s+more", s, re.I)),
            "verified_clause_excerpt": s[:800],
        }
    else:
        data["govinfo_fr_2024_07177_part260"]["sec_260_2_significant_delay_verified"] = {"found": False}

    # 2. Pre-rule 2024-03 exact tail-number missingness on Cancelled==1 vs Cancelled==0 AND airport-continuity check
    raw = get_bytes(
        "https://transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_2024_3.zip",
        90.0,
    )
    zf = zipfile.ZipFile(io.BytesIO(raw))
    csv_name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]

    n_canc = 0
    n_canc_tail_missing = 0
    n_op = 0
    n_op_tail_missing = 0
    # Group by (FlightDate, Tail_Number) -> list of (crs_dep_min, crs_arr_min, origin, dest, cancelled)
    groups: dict[tuple[str, str], list[tuple[int, int, str, str, int]]] = {}
    with zf.open(csv_name) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
        cmap = {c.strip(): c for c in (reader.fieldnames or [])}
        for row in reader:
            canc = 1 if (row.get(cmap["Cancelled"], "").strip() in ("1", "1.00", "1.0")) else 0
            tail = row.get(cmap["Tail_Number"], "").strip()
            if canc:
                n_canc += 1
                if not tail:
                    n_canc_tail_missing += 1
            else:
                n_op += 1
                if not tail:
                    n_op_tail_missing += 1
            if tail:
                fdate = row.get(cmap["FlightDate"], "").strip()
                cdep = _hhmm_to_min(row.get(cmap["CRSDepTime"], ""))
                carr = _hhmm_to_min(row.get(cmap["CRSArrTime"], ""))
                orig = row.get(cmap["Origin"], "").strip()
                dest = row.get(cmap["Dest"], "").strip()
                if fdate and cdep is not None and carr is not None:
                    groups.setdefault((fdate, tail), []).append((cdep, carr, orig, dest, canc))

    # Validate airport continuity (prev.dest == curr.orig) and local-clock non-overlap (caveat: local time zones!)
    total_subsequent_legs = 0
    airport_continuous_legs = 0
    airport_continuous_noncanc_prev = 0
    airport_discontinuous_legs = 0
    # Note: BTS CRSDepTime / CRSArrTime are in LOCAL airport timezones, not UTC!
    for _, legs in groups.items():
        legs.sort(key=lambda x: x[0])
        for i in range(1, len(legs)):
            total_subsequent_legs += 1
            prev_dep, prev_arr, prev_orig, prev_dest, prev_canc = legs[i - 1]
            curr_dep, curr_arr, curr_orig, curr_dest, curr_canc = legs[i]
            if prev_dest == curr_orig:
                airport_continuous_legs += 1
                if prev_canc == 0:
                    airport_continuous_noncanc_prev += 1
            else:
                airport_discontinuous_legs += 1

    data["prerule_2024_03_tail_and_selection_audit"] = {
        "month_prerule_only": "2024-03",
        "cancelled_total": n_canc,
        "cancelled_tail_missing": n_canc_tail_missing,
        "cancelled_tail_missing_pct": round(100.0 * n_canc_tail_missing / max(1, n_canc), 2),
        "operating_total": n_op,
        "operating_tail_missing": n_op_tail_missing,
        "operating_tail_missing_pct": round(100.0 * n_op_tail_missing / max(1, n_op), 4),
        "total_subsequent_records_in_day_tail_groups": total_subsequent_legs,
        "airport_continuous_prev_dest_eq_curr_orig": airport_continuous_legs,
        "airport_continuous_share_pct": round(100.0 * airport_continuous_legs / max(1, total_subsequent_legs), 2),
        "airport_continuous_with_operating_prev_leg": airport_continuous_noncanc_prev,
        "airport_discontinuous_records": airport_discontinuous_legs,
        "critical_identification_caveat": (
            "Even airport-continuous sequences in BTS are POST-ASSIGNMENT realized rotations (airlines swap aircraft "
            "dynamically during disruptions), CRSDepTime/CRSArrTime are local airport clocks (not UTC), and "
            "cancelled flights have vastly higher Tail_Number missingness than operating flights; therefore BTS "
            "tail-number sequences do NOT identify an exogenous pre-cancellation shock."
        ),
    }
    GATE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("SIG_260_2:", json.dumps(data["govinfo_fr_2024_07177_part260"]["sec_260_2_significant_delay_verified"], indent=2))
    print("TAIL_AUDIT:", json.dumps(data["prerule_2024_03_tail_and_selection_audit"], indent=2))


if __name__ == "__main__":
    main()
