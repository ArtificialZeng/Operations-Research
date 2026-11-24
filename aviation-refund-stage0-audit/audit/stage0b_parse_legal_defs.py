"""Extract exact § 260.2 'Significant change of flight itinerary' definition & BTS FGJ field definitions (non-outcome)."""

from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
GATE_PATH = HERE / "stage0b_legal_and_measurement_gate.json"
HEADERS = {"User-Agent": "Academic-Research-DOT260-Stage0B-Parse/1.0"}


def get_text(url: str) -> str:
    with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def main() -> None:
    data = json.loads(GATE_PATH.read_text(encoding="utf-8"))

    # 1. Exact 'Significant change of flight itinerary' in 2024-07177.htm
    fr_html = get_text("https://www.govinfo.gov/content/pkg/FR-2024-04-26/html/2024-07177.htm")
    fr_plain = " ".join(re.sub(r"<[^>]+>", " ", fr_html).split())
    m_sig = re.search(r"(Significant\s+change\s+of\s+flight\s+itinerary\s+means.{0,1400})", fr_plain)
    if m_sig:
        s = m_sig.group(1)
        data["govinfo_fr_2024_07177_part260"]["sec_260_2_significant_change_verified"] = {
            "found": True,
            "original_itinerary_referenced": bool(re.search(r"original\s+itinerary|originally\s+scheduled", s, re.I)),
            "earlier_origin_departure_3h": bool(re.search(r"depart\s+from\s+the\s+origination\s+airport\s+three\s+hours\s+or\s+more\s+earlier", s, re.I)),
            "later_destination_arrival_3h": bool(re.search(r"arrive\s+at\s+the\s+destination\s+airport\s+three\s+hours\s+or\s+more\s+later", s, re.I)),
            "international_6h": bool(re.search(r"six\s+hours\s+or\s+more", s, re.I)),
            "char_len": len(s),
            "short_clause_summary": s[:700],
        }

    # 2. Exact BTS FGJ field definitions (strip <script> and <style> first)
    bts_html = get_text("https://www.transtats.bts.gov/TableInfo.asp?QO_fu146_anzr=b0-gvzr&gnoyr_VQ=FGJ")
    bts_clean = re.sub(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", " ", bts_html, flags=re.I | re.S)
    bts_plain = " ".join(re.sub(r"<[^>]+>", " ", bts_clean).split())
    defs = {}
    for field in ["CRSDepTime", "DepDelay", "CRSArrTime", "ArrDelay", "TotalAddGTime", "LongestAddGTime", "Cancelled", "Diverted"]:
        m = re.search(rf"({field}\b.{{0,220}})", bts_plain)
        defs[field] = m.group(1) if m else None
    data["bts_table_info_fgj_dictionary"]["parsed_field_definitions"] = defs

    # 3. Exact DOT OIG 33850 body summary (strip nav/header)
    oig_html = get_text("https://www.oig.dot.gov/library-item/33850")
    oig_clean = re.sub(r"<(?:script|style|header|nav)[^>]*>.*?</(?:script|style|header|nav)>", " ", oig_html, flags=re.I | re.S)
    oig_plain = " ".join(re.sub(r"<[^>]+>", " ", oig_clean).split())
    m_oig = re.search(r"(Effects\s+of\s+the\s+Tarmac\s+Delay\s+Rule.{0,800})", oig_plain, re.I)
    data["dot_oig_tarmac_report_33850"]["parsed_summary"] = m_oig.group(1) if m_oig else oig_plain[:600]

    GATE_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("SIG_CHANGE:", json.dumps(data["govinfo_fr_2024_07177_part260"].get("sec_260_2_significant_change_verified"), indent=2))
    print("BTS_DEFS:", json.dumps(defs, indent=2))
    print("OIG_SUMMARY:", data["dot_oig_tarmac_report_33850"].get("parsed_summary"))


if __name__ == "__main__":
    main()
