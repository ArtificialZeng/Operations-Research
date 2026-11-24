"""Stage 0 corrected bounded feasibility audit (ZERO outcome regressions / ZERO repo-rate correlations).

Preserves the raw first diagnostic (`data_feasibility_pilot.json`) untouched and writes
`stage0_corrected_feasibility.json`, splitting strictly into:
  Part A — Outcome-Independent Field Coverage & Schema Audit:
    * U.S. Treasury `auctions_query` (`auction_date`, `issue_date`, `maturity_date`, `soma_accepted`,
      `primary_dealer_accepted`, `direct_bidder_accepted`, `indirect_bidder_accepted`, `total_accepted`,
      `high_yield`, `median_yield` vs `avg_med_yield`, `low_yield`).
    * U.S. Treasury `buybacks_operations` endpoint schema & date coverage.
    * OFR Short-Term Funding Monitor (STFM) `dataset=repo` catalog discovery for direct Treasury-collateral
      overnight DVP and Tri-Party average-rate & volume series (exact mnemonics, start/end dates, counts,
      missingness, preliminary `-P` vs final `-F` vintage availability — strictly metadata/counts only).
    * NY Fed Markets API full availability dates for `sofr`, `tgcr`, `bgcr`, `onrrp`, and Primary Dealer
      Statistics (`pd`) lagged holdings endpoints.
  Part B — Full Time-Series & Settlement-Date Unit Feasibility (Pure X-Side Only):
    * Full 2018-04-01 to 2026-11-24 coupon (`Note`, `Bond`) auctions aggregated to UNIQUE `issue_date`s.
    * Exact count of unique coupon settlement dates (`N_settle_total`) overlapping OFR direct DVP/Tri-Party
      and NY Fed lagged ON RRP, plus feasible strictly out-of-sample holdout settlement-date counts
      (e.g., 2024-01-01+ and 2023-07-01+ holdout windows).
    * Value-weighted settlement-level primary-dealer coupon share variation RAW vs. CONDITIONAL ON
      total settled amount, tenor composition shares, and calendar structure (pure X-side OLS residual
      SD / IQR / R^2 — ZERO repo rates Y accessed or correlated!).

NY Fed Terms Notice:
  SOFR, TGCR, BGCR, EFFR, ON RRP, and Primary Dealer Statistics are subject to the Terms of Use posted
  at newyorkfed.org. The New York Fed is not responsible for any use of the data and does not sanction,
  endorse, or recommend this study.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import math
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

OUT_PATH = Path(__file__).resolve().parent / "stage0_corrected_feasibility.json"
HEADERS = {"User-Agent": "Academic-Research-Stage0-Audit/1.0", "Accept": "application/json"}
START_FULL = "2018-04-01"
END_FULL = "2026-11-24"


def fetch_json(url: str, timeout: float = 25.0) -> tuple[int, dict | list | None, str | None, float]:
    t0 = perf_counter()
    try:
        with urlopen(Request(url, headers=HEADERS), timeout=timeout) as resp:
            status = int(resp.status)
            body = json.loads(resp.read().decode("utf-8"))
            return status, body, None, perf_counter() - t0
    except HTTPError as exc:
        return int(exc.code), None, f"HTTPError {exc.code}: {exc.reason}", perf_counter() - t0
    except URLError as exc:
        return 0, None, f"URLError: {exc.reason}", perf_counter() - t0
    except Exception as exc:  # noqa: BLE001
        return 0, None, f"{type(exc).__name__}: {exc}", perf_counter() - t0


def _to_float(val) -> float | None:
    if val is None:
        return None
    s = str(val).strip()
    if not s or s.lower() == "null":
        return None
    try:
        return float(s)
    except ValueError:
        return None


def _tenor_bucket(term: str | None) -> str:
    if not term:
        return "other"
    t = str(term).strip().upper()
    if "2-YEAR" in t:
        return "2Y"
    if "3-YEAR" in t:
        return "3Y"
    if "5-YEAR" in t:
        return "5Y"
    if "7-YEAR" in t:
        return "7Y"
    if "10-YEAR" in t:
        return "10Y"
    if "20-YEAR" in t:
        return "20Y"
    if "30-YEAR" in t:
        return "30Y"
    return "other"


def _is_month_end_window(d: date) -> int:
    # Last 2 calendar days or 1st-2nd business day of month when month-end falls on weekend
    return 1 if (d.day >= 28 or d.day <= 2) else 0


def _is_quarter_end_window(d: date) -> int:
    return 1 if ((d.month in (3, 6, 9, 12) and d.day >= 28) or (d.month in (1, 4, 7, 10) and d.day <= 2)) else 0


def _is_mid_month_15_window(d: date) -> int:
    return 1 if (14 <= d.day <= 17) else 0


def _quantiles(arr: np.ndarray) -> dict:
    if len(arr) == 0:
        return {}
    q = np.percentile(arr, [0, 10, 25, 50, 75, 90, 100])
    return {
        "n": int(len(arr)),
        "mean": round(float(np.mean(arr)), 6),
        "std": round(float(np.std(arr, ddof=1)), 6) if len(arr) > 1 else 0.0,
        "min": round(float(q[0]), 6),
        "p10": round(float(q[1]), 6),
        "p25": round(float(q[2]), 6),
        "p50": round(float(q[3]), 6),
        "p75": round(float(q[4]), 6),
        "p90": round(float(q[5]), 6),
        "max": round(float(q[6]), 6),
        "iqr": round(float(q[4] - q[2]), 6),
    }


def main() -> None:
    t_all = perf_counter()
    report: dict = {
        "stage": "stage_0_corrected_feasibility_audit_zero_outcome_regressions",
        "preserved_first_diagnostic": "data_feasibility_pilot.json",
        "window_full": {"start": START_FULL, "end": END_FULL},
        "nyfed_terms_notice": (
            "SOFR, TGCR, BGCR, EFFR, ON RRP, and Primary Dealer Statistics are subject to the Terms of "
            "Use posted at newyorkfed.org. The New York Fed is not responsible for any use of the data "
            "and does not sanction, endorse, or recommend this study."
        ),
        "part_a_outcome_independent_field_coverage": {},
        "part_b_time_series_and_settlement_unit_feasibility": {},
    }

    # =========================================================================
    # PART A.1 — OFR STFM Direct Repo Segment Series Discovery & Date Coverage
    # =========================================================================
    ofr_catalog_url = "https://data.financialresearch.gov/v1/metadata/mnemonics?dataset=repo"
    st_cat, cat_body, err_cat, dt_cat = fetch_json(ofr_catalog_url)
    ofr_audit: dict = {
        "catalog_url": ofr_catalog_url,
        "http_status": st_cat,
        "error": err_cat,
        "elapsed_seconds": round(dt_cat, 3),
        "total_repo_mnemonics": 0,
        "candidate_treasury_overnight_series": {},
    }
    ofr_dvp_dates: set[str] = set()
    ofr_tri_dates: set[str] = set()

    if st_cat == 200 and isinstance(cat_body, list):
        ofr_audit["total_repo_mnemonics"] = len(cat_body)
        # Filter catalog entries mentioning DVP or TRI and Treasury/Overnight/Sponsored
        relevant_mnemonics = []
        for entry in cat_body:
            if isinstance(entry, dict):
                mn = str(entry.get("mnemonic", ""))
                sname = str(entry.get("series_name", ""))
            else:
                mn = str(entry)
                sname = ""
            u = (mn + " " + sname).upper()
            if ("REPO-DVP" in mn or "REPO-TRI" in mn) and ("OO" in mn or "OVERNIGHT" in u or "TREASURY" in u or "SPONSOR" in u):
                relevant_mnemonics.append({"mnemonic": mn, "series_name": sname})
        ofr_audit["matching_dvp_tri_overnight_catalog_count"] = len(relevant_mnemonics)
        ofr_audit["matching_dvp_tri_overnight_catalog_sample"] = relevant_mnemonics[:40]

        # Prioritize direct overnight/open average-rate (AR) and volume (VOL) DVP & TRI series (Treasury/all-collateral)
        # Check exact metadata & date ranges for top candidate mnemonics (strictly NO values analyzed — dates/counts only!)
        priority_patterns = [
            "REPO-DVP_AR_OO-P",
            "REPO-DVP_AR_OO-F",
            "REPO-DVP_OV_OO-P",
            "REPO-DVP_OV_OO-F",
            "REPO-DVP_TV_OO-P",
            "REPO-DVP_TV_OO-F",
            "REPO-TRI_AR_OO-P",
            "REPO-TRI_AR_OO-F",
            "REPO-TRI_TV_OO-P",
            "REPO-TRI_TV_OO-F",
        ]
        all_mn_set = {
            (e.get("mnemonic") if isinstance(e, dict) else str(e)): (e.get("series_name", "") if isinstance(e, dict) else "")
            for e in cat_body
        }
        selected_mnemonics: list[str] = []
        for p in priority_patterns:
            if p in all_mn_set and p not in selected_mnemonics:
                selected_mnemonics.append(p)
        # Also include any Treasury-specific overnight DVP / TRI rate & volume series
        for mn, sname in sorted(all_mn_set.items()):
            su = sname.upper()
            if ("REPO-DVP" in mn or "REPO-TRI" in mn) and (
                ("TREASURY" in su and ("OVERNIGHT" in su or "RATE" in su or "VOLUME" in su))
                or ("SPONSOR" in su and ("RATE" in su or "VOLUME" in su))
            ):
                if mn not in selected_mnemonics and len(selected_mnemonics) < 16:
                    selected_mnemonics.append(mn)
        # Fallback if names weren't in list: pick first 10 matching DVP/TRI OO series
        if len(selected_mnemonics) < 6:
            for item in relevant_mnemonics:
                mn = item["mnemonic"]
                if mn not in selected_mnemonics and len(selected_mnemonics) < 12:
                    selected_mnemonics.append(mn)

        for mn in selected_mnemonics:
            # Fetch metadata and series dates ONLY (do NOT summarize rate levels — purely coverage dates & counts!)
            m_url = f"https://data.financialresearch.gov/v1/metadata/query?mnemonic={mn}"
            d_url = f"https://data.financialresearch.gov/v1/series/timeseries?mnemonic={mn}"
            st_m, m_body, err_m, _ = fetch_json(m_url)
            st_d, d_body, err_d, dt_d = fetch_json(d_url)
            # Alternative OFR data path fallback if timeseries returns non-200
            if st_d != 200:
                d_url = f"https://data.financialresearch.gov/v1/series/data?mnemonic={mn}"
                st_d, d_body, err_d, dt_d = fetch_json(d_url)
            desc = None
            unit = None
            freq = None
            if isinstance(m_body, list) and m_body and isinstance(m_body[0], dict):
                m0 = m_body[0]
                desc = (m0.get("description") or {}).get("name") or m0.get("mnemonic")
                unit = (m0.get("rights") or {}).get("description") or (m0.get("description") or {}).get("unit")
                freq = (m0.get("schedule") or {}).get("observation_frequency")
            elif isinstance(m_body, dict):
                desc = (m_body.get("description") or {}).get("name") or m_body.get("series_name")

            obs_dates: list[str] = []
            non_null_obs = 0
            if st_d == 200 and isinstance(d_body, list):
                for row in d_body:
                    if isinstance(row, list) and len(row) >= 2:
                        dt_s = str(row[0])[:10]
                        obs_dates.append(dt_s)
                        if _to_float(row[1]) is not None:
                            non_null_obs += 1
                    elif isinstance(row, dict):
                        dt_s = str(row.get("date") or row.get("observation_date") or "")[:10]
                        if dt_s:
                            obs_dates.append(dt_s)
                        if _to_float(row.get("value")) is not None:
                            non_null_obs += 1

            obs_set = set(obs_dates)
            if mn.startswith("REPO-DVP") and "_AR_" in mn and len(obs_set) > len(ofr_dvp_dates):
                ofr_dvp_dates = obs_set
            if mn.startswith("REPO-TRI") and "_AR_" in mn and len(obs_set) > len(ofr_tri_dates):
                ofr_tri_dates = obs_set

            ofr_audit["candidate_treasury_overnight_series"][mn] = {
                "series_name": all_mn_set.get(mn) or desc,
                "frequency": freq,
                "data_http_status": st_d,
                "data_error": err_d,
                "elapsed_seconds": round(dt_d, 3),
                "total_obs": len(obs_dates),
                "non_null_obs": non_null_obs,
                "min_date": min(obs_dates) if obs_dates else None,
                "max_date": max(obs_dates) if obs_dates else None,
                "obs_from_2018_04": sum(1 for d in obs_dates if d >= START_FULL),
                "obs_from_2024_01": sum(1 for d in obs_dates if d >= "2024-01-01"),
            }
    report["part_a_outcome_independent_field_coverage"]["ofr_stfm_direct_repo"] = ofr_audit

    # =========================================================================
    # PART A.2 — Treasury Buybacks & NY Fed Primary Dealer Lagged Holdings APIs
    # =========================================================================
    buyback_url = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/buybacks_operations"
        "?sort=-operation_date&page[number]=1&page[size]=500"
    )
    st_bb, bb_body, err_bb, dt_bb = fetch_json(buyback_url)
    bb_info: dict = {"url": buyback_url, "http_status": st_bb, "error": err_bb, "elapsed_seconds": round(dt_bb, 3)}
    if st_bb == 200 and isinstance(bb_body, dict) and isinstance(bb_body.get("data"), list):
        bb_rows = bb_body["data"]
        bb_info["total_count_meta"] = bb_body.get("meta", {}).get("total-count")
        bb_info["fetched_count"] = len(bb_rows)
        if bb_rows:
            bb_info["sample_keys"] = sorted(bb_rows[0].keys())
            op_dates = [str(r.get("operation_date")) for r in bb_rows if r.get("operation_date")]
            st_dates = [str(r.get("settlement_date")) for r in bb_rows if r.get("settlement_date")]
            bb_info["min_operation_date"] = min(op_dates) if op_dates else None
            bb_info["max_operation_date"] = max(op_dates) if op_dates else None
            bb_info["distinct_settlement_dates"] = len(set(st_dates))
    report["part_a_outcome_independent_field_coverage"]["treasury_buybacks"] = bb_info

    # NY Fed Primary Dealer Statistics API (weekly lagged dealer Treasury holdings / financing)
    pd_list_url = "https://markets.newyorkfed.org/api/pd/list/timeseries.json"
    st_pd, pd_body, err_pd, dt_pd = fetch_json(pd_list_url)
    pd_info: dict = {"url": pd_list_url, "http_status": st_pd, "error": err_pd, "elapsed_seconds": round(dt_pd, 3)}
    if st_pd == 200 and isinstance(pd_body, dict):
        ts_list = pd_body.get("pd", {}).get("timeseries", [])
        pd_info["total_timeseries_count"] = len(ts_list)
        treasury_pos = [
            {"keyid": t.get("keyid"), "description": t.get("description")}
            for t in ts_list
            if isinstance(t, dict)
            and ("TREASURY" in str(t.get("description", "")).upper() or "PDPOSGST" in str(t.get("keyid", "")).upper())
            and ("POSITION" in str(t.get("description", "")).upper() or "NET" in str(t.get("description", "")).upper() or "REPO" in str(t.get("description", "")).upper())
        ]
        pd_info["matching_treasury_position_or_repo_series_count"] = len(treasury_pos)
        pd_info["sample_series"] = treasury_pos[:12]
    report["part_a_outcome_independent_field_coverage"]["nyfed_primary_dealer_stats"] = pd_info

    # NY Fed full-history availability (dates & counts ONLY — ZERO rate values read!)
    nyfed_full_audit: dict = {}
    nyfed_sofr_dates: set[str] = set()
    nyfed_onrrp_dates: set[str] = set()
    for name, url in (
        ("sofr", f"https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate={START_FULL}&endDate={END_FULL}"),
        ("tgcr", f"https://markets.newyorkfed.org/api/rates/secured/tgcr/search.json?startDate={START_FULL}&endDate={END_FULL}"),
        ("onrrp", f"https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?startDate={START_FULL}&endDate={END_FULL}"),
    ):
        st_n, n_body, err_n, dt_n = fetch_json(url)
        n_info: dict = {"http_status": st_n, "error": err_n, "elapsed_seconds": round(dt_n, 3)}
        if st_n == 200 and isinstance(n_body, dict):
            if name != "onrrp":
                rows = n_body.get("refRates", [])
                dts = [str(r.get("effectiveDate")) for r in rows if r.get("effectiveDate")]
                n_info["record_count"] = len(rows)
                n_info["min_date"] = min(dts) if dts else None
                n_info["max_date"] = max(dts) if dts else None
                if name == "sofr":
                    nyfed_sofr_dates = set(dts)
            else:
                ops = n_body.get("repo", {}).get("operations", [])
                dts = [str(r.get("operationDate")) for r in ops if r.get("operationDate")]
                n_info["record_count"] = len(ops)
                n_info["min_date"] = min(dts) if dts else None
                n_info["max_date"] = max(dts) if dts else None
                nyfed_onrrp_dates = set(dts)
        nyfed_full_audit[name] = n_info
    report["part_a_outcome_independent_field_coverage"]["nyfed_full_history_dates"] = nyfed_full_audit

    # =========================================================================
    # PART A.3 & PART B — Full 2018-2026 Treasury Coupon Auctions & Settlement Unit
    # =========================================================================
    all_coupons: list[dict] = []
    page_num = 1
    total_pages = 1
    t_auct = perf_counter()
    auct_err = None
    auct_status = 200
    while page_num <= total_pages and page_num <= 10:
        url = (
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
            f"?filter=issue_date:gte:{START_FULL},issue_date:lte:{END_FULL},security_type:in:(Note,Bond)"
            f"&sort=issue_date&page[number]={page_num}&page[size]=500"
        )
        st_a, a_body, err_a, _ = fetch_json(url)
        auct_status = st_a
        if st_a != 200 or not isinstance(a_body, dict):
            auct_err = err_a
            break
        all_coupons.extend(a_body.get("data", []))
        total_pages = int(a_body.get("meta", {}).get("total-pages", 1))
        page_num += 1

    # Check exact field names & coverage on coupon auctions
    field_coverage: dict = {
        "http_status": auct_status,
        "error": auct_err,
        "elapsed_seconds": round(perf_counter() - t_auct, 3),
        "pages_fetched": page_num - 1,
        "total_coupon_auction_rows": len(all_coupons),
    }
    if all_coupons:
        sample_keys = set(all_coupons[0].keys())
        inspect_fields = [
            "auction_date",
            "record_date",
            "issue_date",
            "maturity_date",
            "security_type",
            "security_term",
            "offering_amt",
            "total_accepted",
            "soma_accepted",
            "primary_dealer_accepted",
            "direct_bidder_accepted",
            "indirect_bidder_accepted",
            "high_yield",
            "median_yield",
            "avg_med_yield",
            "low_yield",
            "bid_to_cover_ratio",
        ]
        field_coverage["field_presence_and_non_null_counts"] = {
            f: {
                "in_schema": (f in sample_keys),
                "non_null_count": sum(
                    1
                    for r in all_coupons
                    if r.get(f) is not None and str(r.get(f)).strip() != "" and str(r.get(f)).strip().lower() != "null"
                ),
            }
            for f in inspect_fields
        }
        # Exact lag using returned auction_date (NOT record_date!)
        lags_ad: list[int] = []
        lags_rd: list[int] = []
        for r in all_coupons:
            id_s = r.get("issue_date")
            ad_s = r.get("auction_date")
            rd_s = r.get("record_date")
            if id_s and ad_s and str(ad_s).lower() != "null":
                lags_ad.append((date.fromisoformat(str(id_s)) - date.fromisoformat(str(ad_s))).days)
            if id_s and rd_s and str(rd_s).lower() != "null":
                lags_rd.append((date.fromisoformat(str(id_s)) - date.fromisoformat(str(rd_s))).days)
        field_coverage["lag_issue_minus_auction_date"] = {
            "count": len(lags_ad),
            "positive_count": sum(1 for x in lags_ad if x > 0),
            "min_median_max_days": [min(lags_ad), median(lags_ad), max(lags_ad)] if lags_ad else None,
        }
        field_coverage["lag_issue_minus_record_date_contrast"] = {
            "count": len(lags_rd),
            "positive_count": sum(1 for x in lags_rd if x > 0),
            "min_median_max_days": [min(lags_rd), median(lags_rd), max(lags_rd)] if lags_rd else None,
        }
    report["part_a_outcome_independent_field_coverage"]["treasury_coupon_auctions_full"] = field_coverage

    # =========================================================================
    # PART B — Settlement-Date Unit Aggregation & Pure X-Side Conditional Variation
    # =========================================================================
    # Aggregate coupon auctions by unique `issue_date`, excluding SOMA from private settled volume
    # so we inspect BOTH total_accepted and private_accepted (= total_accepted - soma_accepted).
    by_settle: dict[str, list[dict]] = defaultdict(list)
    for r in all_coupons:
        id_s = r.get("issue_date")
        ad_s = r.get("auction_date")
        if not id_s or not ad_s or str(ad_s).lower() == "null":
            continue
        if (date.fromisoformat(str(id_s)) - date.fromisoformat(str(ad_s))).days <= 0:
            continue
        pd_acc = _to_float(r.get("primary_dealer_accepted"))
        tot_acc = _to_float(r.get("total_accepted"))
        if pd_acc is None or tot_acc is None or tot_acc <= 0:
            continue
        soma_acc = _to_float(r.get("soma_accepted")) or 0.0
        priv_acc = max(0.0, tot_acc - soma_acc)
        hy = _to_float(r.get("high_yield"))
        amy = _to_float(r.get("avg_med_yield"))
        tail_bps = (hy - amy) * 100.0 if (hy is not None and amy is not None) else None
        by_settle[str(id_s)].append(
            {
                "term": _tenor_bucket(r.get("security_term")),
                "pd_acc": pd_acc,
                "tot_acc": tot_acc,
                "soma_acc": soma_acc,
                "priv_acc": priv_acc,
                "tail_bps": tail_bps,
            }
        )

    settle_rows = []
    buckets = ("2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y", "other")
    for id_s in sorted(by_settle.keys()):
        items = by_settle[id_s]
        tot_sum = sum(x["tot_acc"] for x in items)
        priv_sum = sum(x["priv_acc"] for x in items)
        pd_sum = sum(x["pd_acc"] for x in items)
        if tot_sum <= 0 or priv_sum <= 0:
            continue
        d_obj = date.fromisoformat(id_s)
        tenor_shares = {b: sum(x["tot_acc"] for x in items if x["term"] == b) / tot_sum for b in buckets}
        tails = [x["tail_bps"] for x in items if x["tail_bps"] is not None]
        w_tail = (
            sum(x["tail_bps"] * x["tot_acc"] for x in items if x["tail_bps"] is not None)
            / sum(x["tot_acc"] for x in items if x["tail_bps"] is not None)
            if tails
            else None
        )
        settle_rows.append(
            {
                "issue_date": id_s,
                "year": d_obj.year,
                "n_auctions": len(items),
                "tot_billions": tot_sum / 1e9,
                "priv_billions": priv_sum / 1e9,
                "pd_billions": pd_sum / 1e9,
                "w_pd_share_total": pd_sum / tot_sum,
                "w_pd_share_private": pd_sum / priv_sum,
                "w_tail_bps": w_tail,
                "tenor_shares": tenor_shares,
                "month_end": _is_month_end_window(d_obj),
                "quarter_end": _is_quarter_end_window(d_obj),
                "mid_month_15": _is_mid_month_15_window(d_obj),
                "dow": d_obj.weekday(),
                "in_sofr": id_s in nyfed_sofr_dates,
                "in_ofr_dvp": id_s in ofr_dvp_dates,
                "in_ofr_tri": id_s in ofr_tri_dates,
            }
        )

    # Pure X-side conditional variation: regress settlement-level weighted dealer share (in %)
    # on log(priv_billions) + tenor_shares (excluding reference 'other'/first present) + calendar dummies.
    # ZERO repo outcomes Y are read or touched!
    y_pd_pct = np.asarray([100.0 * r["w_pd_share_private"] for r in settle_rows], dtype=np.float64)
    y_pd_bn = np.asarray([r["pd_billions"] for r in settle_rows], dtype=np.float64)

    def _cond_residual_stats(sub_rows: list[dict], label: str) -> dict:
        if len(sub_rows) < 20:
            return {"label": label, "n_unique_issue_dates": len(sub_rows), "note": "too_few_dates"}
        sp = np.asarray([100.0 * r["w_pd_share_private"] for r in sub_rows], dtype=np.float64)
        db = np.asarray([r["pd_billions"] for r in sub_rows], dtype=np.float64)
        # Design matrix: intercept + log(priv_billions) + priv_billions + 6 tenor shares + calendar (ME, QE, mid15, DOW)
        X_cols = [
            np.ones(len(sub_rows)),
            np.log(np.asarray([r["priv_billions"] for r in sub_rows])),
            np.asarray([r["priv_billions"] for r in sub_rows]),
        ]
        for b in ("2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y"):
            X_cols.append(np.asarray([r["tenor_shares"][b] for r in sub_rows]))
        X_cols.extend(
            [
                np.asarray([r["month_end"] for r in sub_rows], dtype=np.float64),
                np.asarray([r["quarter_end"] for r in sub_rows], dtype=np.float64),
                np.asarray([r["mid_month_15"] for r in sub_rows], dtype=np.float64),
                np.asarray([1.0 if r["dow"] == 0 else 0.0 for r in sub_rows]),
                np.asarray([1.0 if r["dow"] == 1 else 0.0 for r in sub_rows]),
                np.asarray([1.0 if r["dow"] == 2 else 0.0 for r in sub_rows]),
                np.asarray([1.0 if r["dow"] == 3 else 0.0 for r in sub_rows]),
            ]
        )
        X = np.column_stack(X_cols)
        beta_sp, _, _, _ = np.linalg.lstsq(X, sp, rcond=None)
        resid_sp = sp - X @ beta_sp
        r2_sp = 1.0 - float(np.sum(resid_sp**2) / np.sum((sp - np.mean(sp)) ** 2))

        beta_db, _, _, _ = np.linalg.lstsq(X, db, rcond=None)
        resid_db = db - X @ beta_db
        r2_db = 1.0 - float(np.sum(resid_db**2) / np.sum((db - np.mean(db)) ** 2))

        tails_present = np.asarray([r["w_tail_bps"] for r in sub_rows if r["w_tail_bps"] is not None], dtype=np.float64)
        return {
            "label": label,
            "n_unique_issue_dates": len(sub_rows),
            "min_issue_date": sub_rows[0]["issue_date"],
            "max_issue_date": sub_rows[-1]["issue_date"],
            "raw_weighted_pd_share_private_pct": _quantiles(sp),
            "conditional_residual_pd_share_private_pct": _quantiles(resid_sp),
            "r2_amount_tenor_calendar_on_pd_share": round(r2_sp, 4),
            "raw_pd_billions": _quantiles(db),
            "conditional_residual_pd_billions": _quantiles(resid_db),
            "r2_amount_tenor_calendar_on_pd_billions": round(r2_db, 4),
            "weighted_tail_bps_high_minus_avg_med": _quantiles(tails_present) if len(tails_present) else None,
        }

    overlap_ofr = [r for r in settle_rows if r["in_ofr_dvp"] and r["in_ofr_tri"]]
    overlap_sofr = [r for r in settle_rows if r["in_sofr"]]
    holdout_2024_ofr = [r for r in overlap_ofr if r["issue_date"] >= "2024-01-01"]
    holdout_2023h2_ofr = [r for r in overlap_ofr if r["issue_date"] >= "2023-07-01"]
    holdout_2024_sofr = [r for r in overlap_sofr if r["issue_date"] >= "2024-01-01"]

    by_year_counts: dict[str, dict] = {}
    for yr in sorted({r["year"] for r in settle_rows}):
        yr_rows = [r for r in settle_rows if r["year"] == yr]
        by_year_counts[str(yr)] = {
            "unique_coupon_issue_dates": len(yr_rows),
            "coupon_auction_rows": int(sum(r["n_auctions"] for r in yr_rows)),
            "matched_to_ofr_dvp_and_tri": int(sum(1 for r in yr_rows if r["in_ofr_dvp"] and r["in_ofr_tri"])),
            "matched_to_nyfed_sofr": int(sum(1 for r in yr_rows if r["in_sofr"])),
        }

    report["part_b_time_series_and_settlement_unit_feasibility"] = {
        "total_unique_coupon_issue_dates_2018_2026": len(settle_rows),
        "total_unique_dates_overlapping_ofr_dvp_and_tri": len(overlap_ofr),
        "total_unique_dates_overlapping_nyfed_sofr": len(overlap_sofr),
        "feasible_holdout_counts_ofr_overlap": {
            "from_2023_07_01": len(holdout_2023h2_ofr),
            "from_2024_01_01": len(holdout_2024_ofr),
        },
        "feasible_holdout_counts_nyfed_overlap": {
            "from_2024_01_01": len(holdout_2024_sofr),
        },
        "by_year_settlement_date_counts": by_year_counts,
        "conditional_variation_full_2018_2026": _cond_residual_stats(settle_rows, "all_2018_2026_coupon_issue_dates"),
        "conditional_variation_ofr_overlap": _cond_residual_stats(overlap_ofr, "ofr_dvp_tri_overlap_coupon_issue_dates"),
        "conditional_variation_2024_plus_ofr": _cond_residual_stats(holdout_2024_ofr, "2024_plus_ofr_holdout_coupon_issue_dates"),
    }

    # Explicit Stage 0 feasibility summary
    cond_ofr = report["part_b_time_series_and_settlement_unit_feasibility"]["conditional_variation_ofr_overlap"]
    cond_iqr_ofr = (cond_ofr.get("conditional_residual_pd_share_private_pct") or {}).get("iqr")
    report["stage_0_corrected_summary"] = {
        "ofr_catalog_http_200": (st_cat == 200),
        "ofr_dvp_dates_count": len(ofr_dvp_dates),
        "ofr_tri_dates_count": len(ofr_tri_dates),
        "treasury_buybacks_http_200": (st_bb == 200),
        "nyfed_pd_stats_http_200": (st_pd == 200),
        "unique_coupon_issue_dates_ofr_overlap": len(overlap_ofr),
        "feasible_holdout_2024_plus_ofr_dates": len(holdout_2024_ofr),
        "feasible_holdout_2023h2_plus_ofr_dates": len(holdout_2023h2_ofr),
        "conditional_residual_pd_share_iqr_pp_ofr_overlap": cond_iqr_ofr,
        "r2_amount_tenor_calendar_ofr_overlap": cond_ofr.get("r2_amount_tenor_calendar_on_pd_share"),
        "zero_outcome_regressions_executed": True,
    }
    report["total_elapsed_seconds"] = round(perf_counter() - t_all, 3)

    OUT_PATH.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["stage_0_corrected_summary"], indent=2))
    print(f"Wrote corrected Stage 0 feasibility audit: {OUT_PATH}")


if __name__ == "__main__":
    main()
