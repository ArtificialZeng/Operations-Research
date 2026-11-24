"""Stage 0 bounded PRE-RULE-ONLY feasibility, statute, literature, and BTS schema/power audit.

STRICTLY POST-RULE BLIND:
  * ZERO bytes of any post-announcement (2024-04+) or post-compliance (2024-10-28+) BTS flight file
    are downloaded or analyzed!
  * Checks ONLY:
      1. Live Federal Register API metadata for 89 FR 32760 (14 CFR Part 260) exact publication & effective dates.
      2. Live Crossref metadata for closest primary sources (Forbes-Lederman-Tombe 2015, Kleven 2016, Ater-Orlov 2015).
      3. Pure HTTP HEAD inventory across 48 monthly BTS PREZIP archives (2022-09 to 2026-08) for both
         Marketing_Carrier and Reporting_Carrier tables (recording exact availability, sizes, Last-Modified).
      4. Streaming in-memory schema, carrier-roster, 5-minute rounding/heaping, TAIL_NUM prior-leg linkage,
         and pre-rule [120, 240]-minute flight-count & MDE power audit on TWO pre-rule months ONLY
         (`2023_10` and `2024_03`, Marketing_Carrier) — zero raw files written to disk!
"""

from __future__ import annotations

import csv
import io
import json
import math
from pathlib import Path
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
import zipfile

import numpy as np

OUT_PATH = Path(__file__).resolve().parent / "stage0_bts_and_statute_audit.json"
HEADERS = {"User-Agent": "Academic-Research-DOT260-Stage0/1.0"}


def req_bytes(url: str, method: str = "GET", timeout: float = 30.0) -> tuple[int, bytes | None, dict, str | None, float]:
    t0 = perf_counter()
    try:
        with urlopen(Request(url, headers=HEADERS, method=method), timeout=timeout) as r:
            body = None if method == "HEAD" else r.read()
            return int(r.status), body, dict(r.headers), None, round(perf_counter() - t0, 3)
    except HTTPError as e:
        return int(e.code), None, {}, f"HTTPError {e.code}: {e.reason}", round(perf_counter() - t0, 3)
    except URLError as e:
        return 0, None, {}, f"URLError: {e.reason}", round(perf_counter() - t0, 3)
    except Exception as e:  # noqa: BLE001
        return 0, None, {}, f"{type(e).__name__}: {e}", round(perf_counter() - t0, 3)


def check_federal_register() -> dict:
    # Search Federal Register API for Refunds and Other Consumer Protections (89 FR 32760)
    qs = urlencode(
        {
            "conditions[term]": "Refunds and Other Consumer Protections 32760",
            "conditions[agencies][]": "transportation-department",
            "conditions[type][]": "RULE",
            "per_page": 5,
        }
    )
    url = f"https://www.federalregister.gov/api/v1/documents.json?{qs}"
    st, raw, _, err, dt = req_bytes(url)
    out = {"search_url": url, "http_status": st, "error": err, "elapsed_seconds": dt, "matched_rule": None}
    if st == 200 and raw:
        results = json.loads(raw.decode("utf-8")).get("results", [])
        chosen = None
        for r in results:
            if "32760" in str(r.get("citation", "")) or "Refunds and Other Consumer Protections" in str(r.get("title", "")):
                chosen = r
                break
        if chosen is None and results:
            chosen = results[0]
        if chosen:
            doc_num = chosen.get("document_number")
            detail_url = f"https://www.federalregister.gov/api/v1/documents/{doc_num}.json"
            dst, draw, _, derr, ddt = req_bytes(detail_url)
            if dst == 200 and draw:
                det = json.loads(draw.decode("utf-8"))
                out["matched_rule"] = {
                    "document_number": det.get("document_number"),
                    "citation": det.get("citation"),
                    "title": det.get("title"),
                    "publication_date": det.get("publication_date"),
                    "effective_on": det.get("effective_on"),
                    "dates_text": det.get("dates"),
                    "cfr_references": det.get("cfr_references"),
                    "html_url": det.get("html_url"),
                    "body_html_url": det.get("body_html_url"),
                }
            else:
                out["detail_error"] = derr
    return out


def check_primary_literature() -> dict:
    dois = {
        "forbes_lederman_tombe_2015_aej": "10.1257/mic.20130164",
        "kleven_2016_are_bunching": "10.1146/annurev-economics-080315-015234",
        "ater_orlov_2015_restat": "10.1162/REST_a_00478",
        "marks_2019_tarmac_rule": "10.1016/j.tra.2019.01.015",
    }
    res = {}
    for key, doi in dois.items():
        st, raw, _, err, dt = req_bytes(f"https://api.crossref.org/works/{doi}")
        if st == 200 and raw:
            msg = json.loads(raw.decode("utf-8")).get("message", {})
            res[key] = {
                "doi": doi,
                "http_status": st,
                "title": msg.get("title", []),
                "container_title": msg.get("container-title", []),
                "authors": [f"{a.get('given', '')} {a.get('family', '')}".strip() for a in msg.get("author", [])],
                "published": msg.get("published") or msg.get("issued"),
            }
        else:
            res[key] = {"doi": doi, "http_status": st, "error": err}
    return res


def check_bts_head_inventory() -> dict:
    # Check 48 months: 2022-09 through 2026-08 via HTTP HEAD ONLY (ZERO post-rule bytes downloaded!)
    months = []
    y, m = 2022, 9
    for _ in range(48):
        months.append((y, m))
        m += 1
        if m == 13:
            m = 1
            y += 1
    inv = {"marketing_carrier": {}, "reporting_carrier": {}}
    for kind, prefix in [
        ("marketing_carrier", "On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018"),
        ("reporting_carrier", "On_Time_Reporting_Carrier_On_Time_Performance_1987_present"),
    ]:
        ok_months = []
        missing_months = []
        sample_headers = {}
        for y, m in months:
            ym = f"{y}-{m:02d}"
            url = f"https://transtats.bts.gov/PREZIP/{prefix}_{y}_{m}.zip"
            st, _, hdrs, err, _ = req_bytes(url, method="HEAD", timeout=15.0)
            if st == 200:
                ok_months.append(ym)
                if ym in ("2022-09", "2023-10", "2024-03", "2024-10", "2024-11", "2025-10", "2026-06", "2026-08"):
                    sample_headers[ym] = {
                        "bytes": int(hdrs.get("Content-Length", 0)) if hdrs.get("Content-Length") else None,
                        "last_modified": hdrs.get("Last-Modified"),
                    }
            else:
                missing_months.append({"ym": ym, "status": st, "error": err})
        inv[kind] = {
            "total_months_checked": len(months),
            "http_200_count": len(ok_months),
            "first_available": ok_months[0] if ok_months else None,
            "last_available": ok_months[-1] if ok_months else None,
            "pre_announcement_2022_09_to_2024_03_count": sum(1 for x in ok_months if x <= "2024-03"),
            "transition_2024_04_to_2024_10_count": sum(1 for x in ok_months if "2024-04" <= x <= "2024-10"),
            "post_compliance_2024_11_to_2026_08_count": sum(1 for x in ok_months if x >= "2024-11"),
            "missing_months": missing_months,
            "sample_month_headers": sample_headers,
        }
    return inv


def _to_float(v: str) -> float | None:
    s = v.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


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


def audit_prerule_two_months_only() -> dict:
    """Stream ONLY TWO pre-rule months (`2023_10` & `2024_03`) in memory (ZERO post-rule bytes touched!)."""
    months = [(2023, 10), (2024, 3)]
    target_cols = [
        "FlightDate",
        "Marketing_Airline_Network",
        "Operating_Airline ",
        "Operating_Airline",
        "Tail_Number",
        "Origin",
        "Dest",
        "CRSDepTime",
        "DepDelay",
        "DepTime",
        "CRSArrTime",
        "ArrDelay",
        "ArrTime",
        "Cancelled",
        "CancellationCode",
        "Diverted",
        "CRSElapsedTime",
        "ActualElapsedTime",
        "TaxiOut",
        "TaxiIn",
        "CarrierDelay",
        "WeatherDelay",
        "NASDelay",
        "SecurityDelay",
        "LateAircraftDelay",
    ]
    monthly_reports = {}
    agg_dep_120_240 = 0
    agg_dep_165_179 = 0
    agg_dep_180_194 = 0
    agg_airborne_placebo_120_240 = 0
    agg_total_flights = 0
    agg_cancelled = 0
    agg_tail_total = 0
    agg_tail_linked = 0

    for y, m in months:
        ym = f"{y}-{m:02d}"
        url = f"https://transtats.bts.gov/PREZIP/On_Time_Marketing_Carrier_On_Time_Performance_Beginning_January_2018_{y}_{m}.zip"
        st, raw, _, err, dt = req_bytes(url, method="GET", timeout=90.0)
        if st != 200 or not raw:
            monthly_reports[ym] = {"http_status": st, "error": err}
            continue
        zf = zipfile.ZipFile(io.BytesIO(raw))
        csv_name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
        with zf.open(csv_name) as f:
            reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8", errors="replace"))
            cols = [c.strip() for c in (reader.fieldnames or [])]
            # Map stripped column name to exact header name
            col_map = {c.strip(): c for c in (reader.fieldnames or [])}

            n_rows = 0
            n_cancelled = 0
            n_diverted = 0
            n_dep_nonnull = 0
            n_arr_nonnull = 0
            n_tail_nonnull = 0
            mkt_counts: dict[str, int] = {}
            op_counts: dict[str, int] = {}
            cancel_codes: dict[str, int] = {}

            dep_120_240 = 0
            dep_165_179 = 0
            dep_180_194 = 0
            dep_mod5_in_120_240 = 0
            arr_120_240 = 0
            arr_mod5_in_120_240 = 0
            airborne_placebo_120_240 = 0

            # Track same-day tail chains: (FlightDate, Tail_Number) -> list of (crs_dep_min, crs_arr_min)
            tail_legs: dict[tuple[str, str], list[int]] = {}

            for row in reader:
                n_rows += 1
                mkt = row.get(col_map.get("Marketing_Airline_Network", ""), "").strip()
                op = row.get(col_map.get("Operating_Airline", ""), "").strip()
                if mkt:
                    mkt_counts[mkt] = mkt_counts.get(mkt, 0) + 1
                if op:
                    op_counts[op] = op_counts.get(op, 0) + 1

                canc = _to_float(row.get(col_map.get("Cancelled", ""), "")) or 0.0
                div = _to_float(row.get(col_map.get("Diverted", ""), "")) or 0.0
                if canc == 1.0:
                    n_cancelled += 1
                    cc = row.get(col_map.get("CancellationCode", ""), "").strip() or "NULL"
                    cancel_codes[cc] = cancel_codes.get(cc, 0) + 1
                if div == 1.0:
                    n_diverted += 1

                dep_d = _to_float(row.get(col_map.get("DepDelay", ""), ""))
                arr_d = _to_float(row.get(col_map.get("ArrDelay", ""), ""))
                tail = row.get(col_map.get("Tail_Number", ""), "").strip()
                fdate = row.get(col_map.get("FlightDate", ""), "").strip()
                crs_dep = _hhmm_to_min(row.get(col_map.get("CRSDepTime", ""), ""))

                if tail and fdate and crs_dep is not None:
                    n_tail_nonnull += 1
                    tail_legs.setdefault((fdate, tail), []).append(crs_dep)

                if dep_d is not None:
                    n_dep_nonnull += 1
                    if 120.0 <= dep_d <= 240.0:
                        dep_120_240 += 1
                        if int(round(dep_d)) % 5 == 0:
                            dep_mod5_in_120_240 += 1
                    if 165.0 <= dep_d <= 179.0:
                        dep_165_179 += 1
                    if 180.0 <= dep_d <= 194.0:
                        dep_180_194 += 1

                if arr_d is not None:
                    n_arr_nonnull += 1
                    if 120.0 <= arr_d <= 240.0:
                        arr_120_240 += 1
                        if int(round(arr_d)) % 5 == 0:
                            arr_mod5_in_120_240 += 1
                    if dep_d is not None and dep_d < 120.0 and 120.0 <= arr_d <= 240.0:
                        airborne_placebo_120_240 += 1

            # Count flights with at least one prior same-day leg on same tail
            n_with_prior_leg = sum(max(0, len(legs) - 1) for legs in tail_legs.values())

            agg_total_flights += n_rows
            agg_cancelled += n_cancelled
            agg_dep_120_240 += dep_120_240
            agg_dep_165_179 += dep_165_179
            agg_dep_180_194 += dep_180_194
            agg_airborne_placebo_120_240 += airborne_placebo_120_240
            agg_tail_total += n_tail_nonnull
            agg_tail_linked += n_with_prior_leg

            monthly_reports[ym] = {
                "download_seconds": dt,
                "zip_bytes": len(raw),
                "csv_name": csv_name,
                "num_columns": len(cols),
                "verified_key_columns_present": {
                    c: (c in col_map)
                    for c in [
                        "FlightDate",
                        "Marketing_Airline_Network",
                        "Operating_Airline",
                        "Tail_Number",
                        "Origin",
                        "Dest",
                        "CRSDepTime",
                        "DepDelay",
                        "CRSArrTime",
                        "ArrDelay",
                        "Cancelled",
                        "CancellationCode",
                        "Diverted",
                        "CRSElapsedTime",
                        "ActualElapsedTime",
                        "TaxiOut",
                        "TaxiIn",
                        "CarrierDelay",
                        "WeatherDelay",
                        "NASDelay",
                        "SecurityDelay",
                        "LateAircraftDelay",
                    ]
                },
                "total_flights": n_rows,
                "cancelled_flights": n_cancelled,
                "cancellation_rate_pct": round(100.0 * n_cancelled / n_rows, 3),
                "cancellation_codes": cancel_codes,
                "diverted_flights": n_diverted,
                "dep_delay_nonnull_rate_operating": round(n_dep_nonnull / max(1, n_rows - n_cancelled), 5),
                "arr_delay_nonnull_rate_completed": round(n_arr_nonnull / max(1, n_rows - n_cancelled - n_diverted), 5),
                "tail_nonnull_rate": round(n_tail_nonnull / n_rows, 5),
                "same_day_prior_leg_tail_linkage_rate": round(n_with_prior_leg / max(1, n_tail_nonnull), 4),
                "marketing_carriers_count": len(mkt_counts),
                "marketing_carriers_flights": dict(sorted(mkt_counts.items(), key=lambda kv: -kv[1])),
                "operating_carriers_count": len(op_counts),
                "prerule_window_counts": {
                    "dep_delay_120_to_240_min": dep_120_240,
                    "dep_delay_165_to_179_min": dep_165_179,
                    "dep_delay_180_to_194_min": dep_180_194,
                    "dep_delay_mod5_share_in_120_240_exact_null_is_0.20": round(dep_mod5_in_120_240 / max(1, dep_120_240), 4),
                    "arr_delay_120_to_240_min": arr_120_240,
                    "arr_delay_mod5_share_in_120_240_exact_null_is_0.20": round(arr_mod5_in_120_240 / max(1, arr_120_240), 4),
                    "pure_airborne_placebo_dep_lt120_arr_120_240": airborne_placebo_120_240,
                },
            }

    # Pre-rule outcome-blind planning MDE over 22 post-compliance months (2024-11 to 2026-08) vs 19 pre-announcement months (2022-09 to 2024-03)
    # Using ONLY pre-rule monthly baseline counts (zero post-rule outcomes read!)
    avg_165_179_per_month = agg_dep_165_179 / 2.0
    avg_180_194_per_month = agg_dep_180_194 / 2.0
    avg_120_240_per_month = agg_dep_120_240 / 2.0
    proj_post_22m_165_179 = avg_165_179_per_month * 22.0
    proj_pre_19m_165_179 = avg_165_179_per_month * 19.0
    # Poisson SE on log(ratio) for difference-in-bunching excess mass in [165,179] vs [180,194]
    # Under day/airport-day clustering inflation factor (design effect DEFF in {1, 2, 4}):
    se_base_excess_share = math.sqrt(1.0 / max(1.0, proj_post_22m_165_179) + 1.0 / max(1.0, proj_pre_19m_165_179))
    mde_planning = {}
    for deff in [1.0, 2.0, 4.0]:
        se_eff = se_base_excess_share * math.sqrt(deff)
        # 80% power, two-sided alpha=0.05 => (1.96 + 0.8416) = 2.8016 * SE
        mde_rel_pct = 2.8016 * se_eff * 100.0
        mde_planning[f"cluster_deff_{int(deff)}x"] = {
            "se_log_excess_mass": round(se_eff, 5),
            "mde_80pct_twosided_pct_excess_mass_in_165_179": round(mde_rel_pct, 2),
        }

    return {
        "note": "Strictly pre-rule months ONLY (2023-10, 2024-03); zero post-announcement or post-compliance bytes downloaded.",
        "monthly_audits": monthly_reports,
        "projected_planning_power_from_prerule_counts_only": {
            "avg_monthly_total_flights_prerule": round(agg_total_flights / 2.0, 1),
            "avg_monthly_dep_120_240_prerule": round(avg_120_240_per_month, 1),
            "avg_monthly_dep_165_179_prerule": round(avg_165_179_per_month, 1),
            "avg_monthly_dep_180_194_prerule": round(avg_180_194_per_month, 1),
            "avg_monthly_pure_airborne_placebo_120_240_prerule": round(agg_airborne_placebo_120_240 / 2.0, 1),
            "projected_22m_post_dep_120_240_flights": int(round(avg_120_240_per_month * 22.0)),
            "projected_22m_post_dep_165_179_flights": int(round(proj_post_22m_165_179)),
            "projected_19m_pre_dep_165_179_flights": int(round(proj_pre_19m_165_179)),
            "planning_assumption_mde_diff_in_bunching": mde_planning,
        },
    }


def main() -> None:
    t0 = perf_counter()
    report = {
        "stage": "stage_0_prerule_only_dot_refund_rule_and_bts_audit",
        "zero_post_rule_bytes_downloaded_or_analyzed": True,
        "federal_register_89_FR_32760": check_federal_register(),
        "primary_literature_crossref": check_primary_literature(),
        "bts_48month_head_inventory": check_bts_head_inventory(),
        "prerule_2month_schema_and_power_audit": audit_prerule_two_months_only(),
        "total_elapsed_seconds": round(perf_counter() - t0, 3),
    }
    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"WROTE={OUT_PATH} elapsed={report['total_elapsed_seconds']}s")
    print("FR_RULE:", report["federal_register_89_FR_32760"].get("matched_rule"))
    print("BTS_MKT_INV:", {k: v for k, v in report["bts_48month_head_inventory"]["marketing_carrier"].items() if k != "sample_month_headers"})
    print("PRERULE_POWER:", json.dumps(report["prerule_2month_schema_and_power_audit"]["projected_planning_power_from_prerule_counts_only"], indent=2))


if __name__ == "__main__":
    main()
