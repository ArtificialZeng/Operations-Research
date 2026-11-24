"""Stage 0B outcome-blind precision overlap, OFR collateral-scope, and pre-cutoff timestamp audit.

Preserves `data_feasibility_pilot.json` and `stage0_corrected_feasibility.json` untouched.
Writes `stage0b_precision_overlap_audit.json`.

STRICTLY OUTCOME-BLIND:
  * NEVER computes repo rate levels, averages, spreads, correlations, or regressions.
  * Inspects ONLY OFR official metadata (collateral scope & lags), strict NON-NULL observation
    date sets for explicit like-tenor paired same-release-class OFR series:
      - Primary retrospective pair (-F): REPO-DVP_AR_OO-F AND REPO-TRI_AR_OO-F
        (plus separately audited ex-Fed Tri-Party REPO-TRIV1_AR_OO-F)
      - Robustness / vintage pair (-P): REPO-DVP_AR_OO-P AND REPO-TRI_AR_OO-P
  * Audits Treasury duplicate/reopening keys `(cusip, auction_date, issue_date)`, nominal vs.
    TIPS/FRN classification, maturing-principal & SOMA timestamp provability, and buybacks.
  * Maps every control to a named prior-business-day New York forecast cutoff:
    `t_cutoff = prior business day (t - 1) at 5:00 PM ET` with ZERO forward-fill of unpublished data.
  * Reports step-by-step drop attribution, per-year support, effective post-2024 holdout count,
    and pure X-side conditional dealer-share variation on the clean nominal-coupon matched sample.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import numpy as np

OUT_PATH = Path(__file__).resolve().parent / "stage0b_precision_overlap_audit.json"
HEADERS = {"User-Agent": "Academic-Research-Stage0B-PrecisionAudit/1.0", "Accept": "application/json"}
START_FULL = "2018-04-01"
END_FULL = "2026-11-24"


def fetch_json(url: str, timeout: float = 30.0) -> tuple[int, dict | list | None, str | None, float]:
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
    for tag in ("2-YEAR", "3-YEAR", "5-YEAR", "7-YEAR", "10-YEAR", "20-YEAR", "30-YEAR"):
        if tag in t:
            return tag.replace("-YEAR", "Y")
    return "other"


def _is_nominal_fixed_coupon(r: dict) -> tuple[bool, str]:
    """Classify Note/Bond row cleanly into nominal fixed-rate coupon vs TIPS/FRN/other."""
    stype = str(r.get("security_type") or "").strip()
    sterm = str(r.get("security_term") or "").strip().upper()
    if stype not in ("Note", "Bond"):
        return False, f"other_type:{stype}"
    # Fiscal Data marks TIPS with inflation_index_security == 'Yes' or tips_cpi_index / 'TIPS' in term
    if str(r.get("tips") or "").strip().lower() == "yes" or "TIPS" in sterm:
        return False, "tips"
    if str(r.get("inflation_index_security") or "").strip().lower() == "yes":
        return False, "tips"
    if str(r.get("floating_rate") or "").strip().lower() == "yes" or "FRN" in sterm:
        return False, "frn"
    if r.get("ref_cpi_on_issue_date") not in (None, "", "null"):
        return False, "tips_via_cpi"
    if r.get("frn_index_determination_date") not in (None, "", "null"):
        return False, "frn_via_det_date"
    return True, "nominal_fixed_coupon"


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


def fetch_ofr_series_dates_and_meta(mnemonic: str) -> dict:
    """Fetch official OFR metadata + STRICT NON-NULL vs NULL date sets (ZERO rate values stored!)."""
    m_url = f"https://data.financialresearch.gov/v1/metadata/query?mnemonic={mnemonic}"
    d_url = f"https://data.financialresearch.gov/v1/series/timeseries?mnemonic={mnemonic}"
    st_m, m_body, err_m, _ = fetch_json(m_url)
    st_d, d_body, err_d, dt_d = fetch_json(d_url)

    meta_extracted: dict = {}
    if st_m == 200:
        m0 = m_body[0] if (isinstance(m_body, list) and m_body) else (m_body if isinstance(m_body, dict) else {})
        meta_extracted = {
            "description": m0.get("description"),
            "release": m0.get("release"),
            "schedule": m0.get("schedule"),
            "rights": m0.get("rights"),
            "notes": m0.get("notes"),
            "raw_top_keys": sorted(m0.keys()) if isinstance(m0, dict) else [],
        }

    nonnull_dates: set[str] = set()
    null_dates: set[str] = set()
    if st_d == 200 and isinstance(d_body, list):
        for row in d_body:
            if isinstance(row, list) and len(row) >= 2:
                dt_s = str(row[0])[:10]
                if _to_float(row[1]) is not None:
                    nonnull_dates.add(dt_s)
                else:
                    null_dates.add(dt_s)
    return {
        "mnemonic": mnemonic,
        "meta_http_status": st_m,
        "data_http_status": st_d,
        "error": err_m or err_d,
        "elapsed_seconds": round(dt_d, 3),
        "official_metadata": meta_extracted,
        "nonnull_count_total": len(nonnull_dates),
        "null_count_total": len(null_dates),
        "nonnull_min_date": min(nonnull_dates) if nonnull_dates else None,
        "nonnull_max_date": max(nonnull_dates) if nonnull_dates else None,
        "null_dates_sample": sorted(null_dates)[:25],
        "_nonnull_set": nonnull_dates,
        "_null_set": null_dates,
    }


def main() -> None:
    t_all = perf_counter()

    # =========================================================================
    # 1. Explicit Like-Tenor Paired OFR STFM Series (Strict Non-Null + Metadata)
    # =========================================================================
    ofr_mnemonics = [
        "REPO-DVP_AR_OO-F",     # Fixed primary retrospective outcome leg 1
        "REPO-TRI_AR_OO-F",     # Fixed primary retrospective outcome leg 2 (like-tenor, same release class)
        "REPO-TRIV1_AR_OO-F",   # Ex-Fed Tri-Party overnight/open (collateral/scope comparator)
        "REPO-DVP_AR_OO-P",     # Separately declared robustness/vintage pair leg 1 + pre-cutoff lagged control
        "REPO-TRI_AR_OO-P",     # Separately declared robustness/vintage pair leg 2 + pre-cutoff lagged control
        "REPO-TRIV1_AR_OO-P",   # Ex-Fed Tri-Party preliminary
        "REPO-TRI_AR_T-F",      # All-tenor Treasury Tri-Party (to contrast official collateral metadata ONLY)
    ]
    ofr_raw = {mn: fetch_ofr_series_dates_and_meta(mn) for mn in ofr_mnemonics}
    ofr_sets = {mn: ofr_raw[mn]["_nonnull_set"] for mn in ofr_mnemonics}
    ofr_nulls = {mn: ofr_raw[mn]["_null_set"] for mn in ofr_mnemonics}

    # Explicit paired non-null date intersections
    pair_f_nonnull = ofr_sets["REPO-DVP_AR_OO-F"] & ofr_sets["REPO-TRI_AR_OO-F"]
    pair_f_exfed_nonnull = ofr_sets["REPO-DVP_AR_OO-F"] & ofr_sets["REPO-TRIV1_AR_OO-F"]
    pair_p_nonnull = ofr_sets["REPO-DVP_AR_OO-P"] & ofr_sets["REPO-TRI_AR_OO-P"]

    # =========================================================================
    # 2. Pre-Cutoff Controls: NY Fed ON RRP, SOFR/TGCR calendar, and PD Holdings
    # =========================================================================
    # Use NY Fed SOFR + ON RRP dates to establish the exact official NY trading business-day calendar.
    st_sofr, sofr_body, _, _ = fetch_json(
        f"https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate={START_FULL}&endDate={END_FULL}"
    )
    sofr_nonnull = {
        str(r["effectiveDate"])
        for r in (sofr_body or {}).get("refRates", [])
        if r.get("effectiveDate") and _to_float(r.get("percentRate")) is not None
    }
    st_tgcr, tgcr_body, _, _ = fetch_json(
        f"https://markets.newyorkfed.org/api/rates/secured/tgcr/search.json?startDate={START_FULL}&endDate={END_FULL}"
    )
    tgcr_nonnull = {
        str(r["effectiveDate"])
        for r in (tgcr_body or {}).get("refRates", [])
        if r.get("effectiveDate") and _to_float(r.get("percentRate")) is not None
    }
    st_rrp, rrp_body, _, _ = fetch_json(
        f"https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?startDate={START_FULL}&endDate={END_FULL}"
    )
    onrrp_nonnull = {
        str(r["operationDate"])
        for r in (rrp_body or {}).get("repo", {}).get("operations", [])
        if r.get("operationDate") and _to_float(r.get("totalAmtAccepted")) is not None
    }

    # Canonical NY repo business-day calendar (sorted union of NY Fed SOFR + ON RRP trading days)
    bday_list = sorted(sofr_nonnull | onrrp_nonnull)
    bday_idx = {d: i for i, d in enumerate(bday_list)}

    def prev_bday(d_str: str, k: int = 1) -> str | None:
        if d_str in bday_idx:
            pos = bday_idx[d_str] - k
            return bday_list[pos] if pos >= 0 else None
        # Fallback: find largest business day strictly < d_str, then step back k-1
        prior = [x for x in bday_list if x < d_str]
        return prior[-k] if len(prior) >= k else None

    # NY Fed Primary Dealer Statistics: actual weekly observations & release dates (Thursday 4:15 PM ET, +8 calendar days)
    pd_url = "https://markets.newyorkfed.org/api/pd/get/PDPOSGST-TOT.json"
    st_pd, pd_body, err_pd, dt_pd = fetch_json(pd_url)
    pd_obs_dates: list[str] = []
    pd_sample_record = None
    if st_pd == 200 and isinstance(pd_body, dict):
        ts_rows = pd_body.get("pd", {}).get("timeseries", [])
        if ts_rows:
            pd_sample_record = {k: v for k, v in ts_rows[0].items() if k != "value"}
        for r in ts_rows:
            if r.get("asofdate") and _to_float(r.get("value")) is not None:
                pd_obs_dates.append(str(r["asofdate"])[:10])
    pd_obs_dates = sorted(set(pd_obs_dates))
    # Map each Wednesday asofdate to its official public release date: following-week Thursday 4:15 PM ET (+8 cal days).
    # Note: if Thursday is a federal holiday (e.g. Thanksgiving), release moves to Friday (+9 cal days);
    # to be conservatively timestamp-safe with ZERO unpublished leakage, require release_date_safe = asofdate + 9 days
    # (or check exact next NY business day >= asofdate + 8 days) <= t_prev_bday!
    pd_with_release: list[tuple[str, str]] = []
    for asof_s in pd_obs_dates:
        d_asof = date.fromisoformat(asof_s)
        rel_nominal = (d_asof + timedelta(days=8)).isoformat()
        # First NY business day >= rel_nominal (handles Thursday holidays like Thanksgiving -> Friday)
        rel_actual = next((b for b in bday_list if b >= rel_nominal), rel_nominal)
        pd_with_release.append((asof_s, rel_actual))

    def latest_published_pd_asof(cutoff_bday: str) -> tuple[str | None, int | None]:
        """Return latest PD asofdate whose official Thursday 4:15 PM ET release is <= (cutoff_bday, 17:00 ET)."""
        eligible = [(a, rel) for a, rel in pd_with_release if rel <= cutoff_bday]
        if not eligible:
            return None, None
        asof_s, _ = eligible[-1]
        stale_days = (date.fromisoformat(cutoff_bday) - date.fromisoformat(asof_s)).days
        return asof_s, stale_days

    # =========================================================================
    # 3. Treasury Coupon Duplicate/Reopening Audit & Pre-Known Net Supply Audit
    # =========================================================================
    all_coupons: list[dict] = []
    page_num, total_pages = 1, 1
    while page_num <= total_pages and page_num <= 10:
        url = (
            "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
            f"?filter=issue_date:gte:{START_FULL},issue_date:lte:{END_FULL},security_type:in:(Note,Bond)"
            f"&sort=issue_date&page[number]={page_num}&page[size]=500"
        )
        st_a, a_body, _, _ = fetch_json(url)
        if st_a != 200 or not isinstance(a_body, dict):
            break
        all_coupons.extend(a_body.get("data", []))
        total_pages = int(a_body.get("meta", {}).get("total-pages", 1))
        page_num += 1

    # Audit duplicate keys, reopenings, TIPS/FRN, and tiny outliers
    key_counts = Counter(
        (str(r.get("cusip")), str(r.get("auction_date")), str(r.get("issue_date"))) for r in all_coupons
    )
    dup_keys = {str(k): v for k, v in key_counts.items() if v > 1}
    cusip_counts = Counter(str(r.get("cusip")) for r in all_coupons)
    reopening_flag_counts = Counter(str(r.get("reopening")) for r in all_coupons)
    class_counts = Counter()
    hy_null_by_class = Counter()
    tiny_rows = []
    nominal_coupons: list[dict] = []

    for r in all_coupons:
        is_nom, cls_name = _is_nominal_fixed_coupon(r)
        class_counts[cls_name] += 1
        if _to_float(r.get("high_yield")) is None:
            hy_null_by_class[cls_name] += 1
        tot_acc = _to_float(r.get("total_accepted"))
        pd_acc = _to_float(r.get("primary_dealer_accepted"))
        if tot_acc is not None and tot_acc < 1e9:
            tiny_rows.append(
                {
                    "cusip": r.get("cusip"),
                    "security_type": r.get("security_type"),
                    "security_term": r.get("security_term"),
                    "class": cls_name,
                    "auction_date": r.get("auction_date"),
                    "issue_date": r.get("issue_date"),
                    "total_accepted": tot_acc,
                    "primary_dealer_accepted": pd_acc,
                }
            )
        if is_nom:
            nominal_coupons.append(r)

    # Check pre-known net supply / redemptions / SOMA / buybacks timestamp provability
    # (a) Check historical maturing Note/Bond/TIPS/FRN issuances with maturity_date in 2018-04..2026-11
    mat_url_check = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
        f"?filter=maturity_date:gte:{START_FULL},maturity_date:lte:{END_FULL},security_type:in:(Note,Bond)"
        "&sort=maturity_date&page[number]=1&page[size]=50"
    )
    st_mat, mat_body, err_mat, _ = fetch_json(mat_url_check)
    mat_meta_count = (mat_body or {}).get("meta", {}).get("total-count") if st_mat == 200 else None
    # Check earliest issue_date available for maturing bonds (e.g., 30-year bonds issued 1988-1996 maturing 2018-2026)
    mat_sample_earliest = None
    if st_mat == 200 and isinstance((mat_body or {}).get("data"), list) and mat_body["data"]:
        m_dates_iss = [str(r.get("issue_date")) for r in mat_body["data"] if r.get("issue_date")]
        mat_sample_earliest = min(m_dates_iss) if m_dates_iss else None

    # (b) Check NY Fed SOMA holdings API availability (weekly snapshots of SOMA CUSIP-level holdings)
    soma_url = "https://markets.newyorkfed.org/api/soma/summary.json"
    st_soma, soma_body, err_soma, _ = fetch_json(soma_url)
    soma_summary_count = len((soma_body or {}).get("soma", {}).get("summary", [])) if st_soma == 200 else 0

    # (c) Check Treasury Buybacks settlement dates and operation_date < settlement_date
    bb_url = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/buybacks_operations"
        "?filter=settlement_date:gte:2018-04-01&sort=settlement_date&page[number]=1&page[size]=500"
    )
    st_bb, bb_body, _, _ = fetch_json(bb_url)
    bb_rows = (bb_body or {}).get("data", []) if st_bb == 200 else []
    bb_lag_pos = sum(
        1
        for r in bb_rows
        if r.get("settlement_date")
        and r.get("operation_date")
        and date.fromisoformat(str(r["settlement_date"])) > date.fromisoformat(str(r["operation_date"]))
    )

    # =========================================================================
    # 4. Aggregate Nominal Fixed-Rate Coupons to Unique `issue_date` & Drop Waterfall
    # =========================================================================
    raw_unique_dates = sorted({str(r["issue_date"]) for r in all_coupons if r.get("issue_date")})

    by_settle: dict[str, list[dict]] = defaultdict(list)
    nom_dropped_reasons = Counter()
    for r in nominal_coupons:
        id_s = str(r.get("issue_date") or "")
        ad_s = str(r.get("auction_date") or "")
        if not id_s or not ad_s or ad_s.lower() == "null":
            nom_dropped_reasons["missing_dates"] += 1
            continue
        if (date.fromisoformat(id_s) - date.fromisoformat(ad_s)).days <= 0:
            nom_dropped_reasons["non_positive_auction_lag"] += 1
            continue
        pd_acc = _to_float(r.get("primary_dealer_accepted"))
        tot_acc = _to_float(r.get("total_accepted"))
        soma_acc = _to_float(r.get("soma_accepted"))
        if pd_acc is None or tot_acc is None or tot_acc <= 0 or soma_acc is None:
            nom_dropped_reasons["pending_or_null_accepted"] += 1
            continue
        priv_acc = tot_acc - soma_acc
        if priv_acc <= 0:
            nom_dropped_reasons["non_positive_private_accepted"] += 1
            continue
        hy = _to_float(r.get("high_yield"))
        amy = _to_float(r.get("avg_med_yield"))
        by_settle[id_s].append(
            {
                "cusip": r.get("cusip"),
                "term": _tenor_bucket(r.get("security_term")),
                "auction_date": ad_s,
                "pd_acc": pd_acc,
                "tot_acc": tot_acc,
                "soma_acc": soma_acc,
                "priv_acc": priv_acc,
                "tail_bps": (hy - amy) * 100.0 if (hy is not None and amy is not None) else None,
            }
        )

    # Evaluate each unique nominal coupon settlement date against:
    # (1) Fixed primary retrospective paired non-null OFR -F outcomes (REPO-DVP_AR_OO-F & REPO-TRI_AR_OO-F)
    # (2) Robustness paired non-null OFR -P outcomes (REPO-DVP_AR_OO-P & REPO-TRI_AR_OO-P)
    # (3) Verified pre-cutoff controls as of `(prev_bday(t, 1), 17:00 ET)`:
    #     - ON RRP non-null at `prev_bday(t, 1)` (published 1:15 PM ET on t-1)
    #     - Lagged OFR DVP -P non-null at `prev_bday(t, 2)` (1-bday lag, published 3:00 PM ET on t-1)
    #     - Lagged OFR TRI -P non-null at `prev_bday(t, 3)` (2-bday lag, published 3:00 PM ET on t-1)
    #     - Lagged NY Fed PD `PDPOSGST-TOT` published (Thursday 4:15 PM ET) on or before `prev_bday(t, 1)`
    #       AND staleness <= 21 calendar days (no stale/unpublished forward-fill!)
    #     - All settling auctions strictly have `auction_date <= prev_bday(t, 1)` (results ~1:00 PM ET on auction_date)
    nom_dates = sorted(by_settle.keys())
    drop_f_reasons = Counter()
    drop_p_reasons = Counter()
    dropped_f_examples: dict[str, list[str]] = defaultdict(list)
    matched_f_rows: list[dict] = []
    matched_p_rows: list[dict] = []

    buckets = ("2Y", "3Y", "5Y", "7Y", "10Y", "20Y", "30Y")
    for id_s in nom_dates:
        items = by_settle[id_s]
        pb1 = prev_bday(id_s, 1)
        pb2 = prev_bday(id_s, 2)
        pb3 = prev_bday(id_s, 3)

        all_auct_pre_cutoff = bool(pb1 is not None and all(x["auction_date"] <= pb1 for x in items))
        has_onrrp_t1 = bool(pb1 is not None and pb1 in onrrp_nonnull)
        has_dvp_p_t2 = bool(pb2 is not None and pb2 in ofr_sets["REPO-DVP_AR_OO-P"])
        has_tri_p_t3 = bool(pb3 is not None and pb3 in ofr_sets["REPO-TRI_AR_OO-P"])
        has_sofr_t2 = bool(pb2 is not None and pb2 in sofr_nonnull and pb2 in tgcr_nonnull)
        pd_asof, pd_stale = latest_published_pd_asof(pb1) if pb1 else (None, None)
        has_pd_pre_cutoff = bool(pd_asof is not None and pd_stale is not None and pd_stale <= 21)

        controls_ok = bool(
            all_auct_pre_cutoff and has_onrrp_t1 and has_dvp_p_t2 and has_tri_p_t3 and has_sofr_t2 and has_pd_pre_cutoff
        )

        # Build X-only summary row
        tot_sum = sum(x["tot_acc"] for x in items)
        priv_sum = sum(x["priv_acc"] for x in items)
        pd_sum = sum(x["pd_acc"] for x in items)
        d_obj = date.fromisoformat(id_s)
        tenor_shares = {b: sum(x["priv_acc"] for x in items if x["term"] == b) / priv_sum for b in buckets}
        tails = [x["tail_bps"] for x in items if x["tail_bps"] is not None]
        w_tail = (
            sum(x["tail_bps"] * x["priv_acc"] for x in items if x["tail_bps"] is not None)
            / sum(x["priv_acc"] for x in items if x["tail_bps"] is not None)
            if tails
            else None
        )
        row_x = {
            "issue_date": id_s,
            "year": d_obj.year,
            "n_auctions": len(items),
            "priv_billions": priv_sum / 1e9,
            "pd_billions": pd_sum / 1e9,
            "w_pd_share_private": pd_sum / priv_sum,
            "w_tail_bps": w_tail,
            "tenor_shares": tenor_shares,
            "month_end": 1 if (d_obj.day >= 28 or d_obj.day <= 2) else 0,
            "quarter_end": 1 if ((d_obj.month in (3, 6, 9, 12) and d_obj.day >= 28) or (d_obj.month in (1, 4, 7, 10) and d_obj.day <= 2)) else 0,
            "mid_month_15": 1 if (14 <= d_obj.day <= 17) else 0,
            "dow": d_obj.weekday(),
            "pd_staleness_days": pd_stale,
        }

        # Check Primary -F pair + pre-cutoff controls
        in_dvp_f = id_s in ofr_sets["REPO-DVP_AR_OO-F"]
        in_tri_f = id_s in ofr_sets["REPO-TRI_AR_OO-F"]
        if in_dvp_f and in_tri_f and controls_ok:
            matched_f_rows.append(row_x)
        else:
            if not in_dvp_f and id_s > (ofr_raw["REPO-DVP_AR_OO-F"]["nonnull_max_date"] or ""):
                reason = "after_ofr_final_max_date_2026_06_30"
            elif not in_dvp_f and id_s < (ofr_raw["REPO-DVP_AR_OO-F"]["nonnull_min_date"] or ""):
                reason = "before_ofr_dvp_start_2018_05_07"
            elif not in_dvp_f and id_s in ofr_nulls["REPO-DVP_AR_OO-F"]:
                reason = "ofr_dvp_final_explicit_null_gap"
            elif not in_dvp_f:
                reason = "ofr_dvp_final_date_absent"
            elif not in_tri_f:
                reason = "ofr_tri_final_missing_or_null"
            elif not has_dvp_p_t2:
                reason = "lagged_ofr_dvp_p_t_minus_2_null_or_missing"
            elif not has_tri_p_t3:
                reason = "lagged_ofr_tri_p_t_minus_3_null_or_missing"
            elif not has_onrrp_t1:
                reason = "lagged_onrrp_t_minus_1_missing"
            elif not has_pd_pre_cutoff:
                reason = "lagged_nyfed_pd_missing_or_stale"
            elif not has_sofr_t2:
                reason = "lagged_sofr_tgcr_t_minus_2_missing"
            else:
                reason = "auction_not_strictly_before_cutoff"
            drop_f_reasons[reason] += 1
            if len(dropped_f_examples[reason]) < 8:
                dropped_f_examples[reason].append(id_s)

        # Check Robustness -P pair + pre-cutoff controls
        in_dvp_p = id_s in ofr_sets["REPO-DVP_AR_OO-P"]
        in_tri_p = id_s in ofr_sets["REPO-TRI_AR_OO-P"]
        if in_dvp_p and in_tri_p and controls_ok:
            matched_p_rows.append(row_x)
        else:
            if not in_dvp_p and id_s < (ofr_raw["REPO-DVP_AR_OO-P"]["nonnull_min_date"] or ""):
                r_p = "before_ofr_dvp_start_2018_05_07"
            elif not in_dvp_p and id_s in ofr_nulls["REPO-DVP_AR_OO-P"]:
                r_p = "ofr_dvp_prelim_explicit_null_gap"
            elif not in_dvp_p:
                r_p = "ofr_dvp_prelim_date_absent"
            elif not in_tri_p:
                r_p = "ofr_tri_prelim_missing_or_null"
            elif not has_dvp_p_t2:
                r_p = "lagged_ofr_dvp_p_t_minus_2_null_or_missing"
            elif not has_tri_p_t3:
                r_p = "lagged_ofr_tri_p_t_minus_3_null_or_missing"
            else:
                r_p = "other_pre_cutoff_control_missing"
            drop_p_reasons[r_p] += 1

    def _cond_x_stats(rows: list[dict], label: str) -> dict:
        if len(rows) < 20:
            return {"label": label, "n_dates": len(rows), "note": "too_few"}
        sp = np.asarray([100.0 * r["w_pd_share_private"] for r in rows], dtype=np.float64)
        db = np.asarray([r["pd_billions"] for r in rows], dtype=np.float64)
        X_cols = [
            np.ones(len(rows)),
            np.log(np.asarray([r["priv_billions"] for r in rows])),
            np.asarray([r["priv_billions"] for r in rows]),
        ]
        for b in ("2Y", "3Y", "5Y", "7Y", "10Y", "20Y"):
            X_cols.append(np.asarray([r["tenor_shares"][b] for r in rows]))
        X_cols.extend(
            [
                np.asarray([r["month_end"] for r in rows], dtype=np.float64),
                np.asarray([r["quarter_end"] for r in rows], dtype=np.float64),
                np.asarray([r["mid_month_15"] for r in rows], dtype=np.float64),
                np.asarray([1.0 if r["dow"] == 0 else 0.0 for r in rows]),
                np.asarray([1.0 if r["dow"] == 1 else 0.0 for r in rows]),
                np.asarray([1.0 if r["dow"] == 2 else 0.0 for r in rows]),
                np.asarray([1.0 if r["dow"] == 3 else 0.0 for r in rows]),
            ]
        )
        X = np.column_stack(X_cols)
        b_sp, _, _, _ = np.linalg.lstsq(X, sp, rcond=None)
        res_sp = sp - X @ b_sp
        r2_sp = 1.0 - float(np.sum(res_sp**2) / np.sum((sp - np.mean(sp)) ** 2))
        b_db, _, _, _ = np.linalg.lstsq(X, db, rcond=None)
        res_db = db - X @ b_db
        r2_db = 1.0 - float(np.sum(res_db**2) / np.sum((db - np.mean(db)) ** 2))
        tails = np.asarray([r["w_tail_bps"] for r in rows if r["w_tail_bps"] is not None], dtype=np.float64)
        return {
            "label": label,
            "n_dates": len(rows),
            "min_date": rows[0]["issue_date"],
            "max_date": rows[-1]["issue_date"],
            "raw_private_pd_share_pct": _quantiles(sp),
            "cond_residual_private_pd_share_pct": _quantiles(res_sp),
            "r2_amt_tenor_cal_on_pd_share": round(r2_sp, 4),
            "raw_pd_billions": _quantiles(db),
            "cond_residual_pd_billions": _quantiles(res_db),
            "r2_amt_tenor_cal_on_pd_billions": round(r2_db, 4),
            "weighted_tail_bps_nonnull_count": int(len(tails)),
            "weighted_tail_bps_stats": _quantiles(tails) if len(tails) else None,
        }

    # Per-year exact support table
    all_years = sorted({date.fromisoformat(d).year for d in nom_dates})
    per_year: dict[str, dict] = {}
    for yr in all_years:
        n_nom_yr = sum(1 for d in nom_dates if date.fromisoformat(d).year == yr)
        n_f_out = sum(1 for d in nom_dates if date.fromisoformat(d).year == yr and d in pair_f_nonnull)
        n_f_full = sum(1 for r in matched_f_rows if r["year"] == yr)
        n_p_out = sum(1 for d in nom_dates if date.fromisoformat(d).year == yr and d in pair_p_nonnull)
        n_p_full = sum(1 for r in matched_p_rows if r["year"] == yr)
        per_year[str(yr)] = {
            "nominal_coupon_issue_dates": n_nom_yr,
            "ofr_F_paired_nonnull_only": n_f_out,
            "ofr_F_paired_nonnull_plus_all_pre_cutoff_controls": n_f_full,
            "ofr_P_paired_nonnull_only": n_p_out,
            "ofr_P_paired_nonnull_plus_all_pre_cutoff_controls": n_p_full,
        }

    # Strip internal sets before JSON dump
    ofr_clean = {
        mn: {k: v for k, v in info.items() if not k.startswith("_")}
        for mn, info in ofr_raw.items()
    }

    matched_f_2024 = [r for r in matched_f_rows if r["issue_date"] >= "2024-01-01"]
    matched_f_2023h2 = [r for r in matched_f_rows if r["issue_date"] >= "2023-07-01"]
    matched_p_2024 = [r for r in matched_p_rows if r["issue_date"] >= "2024-01-01"]
    matched_p_2023h2 = [r for r in matched_p_rows if r["issue_date"] >= "2023-07-01"]

    payload = {
        "stage": "stage_0b_outcome_blind_precision_overlap_audit",
        "zero_repo_outcomes_fitted_or_inspected": True,
        "forecast_cutoff_definition": {
            "named_cutoff": "Prior NY business day (t - 1) at 5:00 PM ET (17:00 America/New_York)",
            "auction_results_rule": "auction_date <= t - 1 (official Treasury results ~1:00 PM ET on auction_date)",
            "buyback_results_rule": "operation_date <= t - 1 (closes 2:00 PM ET on operation_date)",
            "on_rrp_rule": "operationDate == t - 1 (closes 1:15 PM ET on t - 1)",
            "ofr_dvp_p_lag_rule": "observation date <= t - 2 business days (1-bday lag, published 3:00 PM ET on t - 1)",
            "ofr_tri_p_lag_rule": "observation date <= t - 3 business days (2-bday lag, published 3:00 PM ET on t - 1)",
            "nyfed_sofr_tgcr_lag_rule": "effectiveDate <= t - 2 business days (published 8:00 AM ET on t - 1)",
            "nyfed_pd_holdings_rule": "latest Wednesday asofdate whose Thursday 4:15 PM ET release (next NY bday >= asofdate + 8 cal days) <= t - 1, staleness <= 21 cal days; zero forward-fill of unpublished snapshots",
        },
        "ofr_official_metadata_and_nonnull_counts": ofr_clean,
        "ofr_paired_nonnull_calendar_counts": {
            "primary_F_pair_DVP_and_TRI_OO_F": {
                "count": len(pair_f_nonnull),
                "min_date": min(pair_f_nonnull) if pair_f_nonnull else None,
                "max_date": max(pair_f_nonnull) if pair_f_nonnull else None,
            },
            "exfed_F_pair_DVP_and_TRIV1_OO_F": {
                "count": len(pair_f_exfed_nonnull),
                "min_date": min(pair_f_exfed_nonnull) if pair_f_exfed_nonnull else None,
                "max_date": max(pair_f_exfed_nonnull) if pair_f_exfed_nonnull else None,
            },
            "robustness_P_pair_DVP_and_TRI_OO_P": {
                "count": len(pair_p_nonnull),
                "min_date": min(pair_p_nonnull) if pair_p_nonnull else None,
                "max_date": max(pair_p_nonnull) if pair_p_nonnull else None,
            },
        },
        "treasury_key_and_security_class_audit": {
            "total_note_bond_rows_2018_2026": len(all_coupons),
            "unique_raw_issue_dates": len(raw_unique_dates),
            "duplicate_cusip_auction_issue_keys": dup_keys,
            "distinct_cusips": len(cusip_counts),
            "cusips_appearing_multiple_times_reopenings": sum(1 for v in cusip_counts.values() if v > 1),
            "reopening_flag_distribution": dict(reopening_flag_counts),
            "security_subclass_counts": dict(class_counts),
            "high_yield_null_by_subclass": dict(hy_null_by_class),
            "tiny_rows_under_1B": tiny_rows,
            "nominal_fixed_coupon_rows_dropped_pre_join": dict(nom_dropped_reasons),
            "unique_nominal_fixed_coupon_issue_dates": len(nom_dates),
        },
        "pre_known_net_supply_provability_audit": {
            "maturing_note_bond_rows_in_2018_2026_meta_count": mat_meta_count,
            "maturing_sample_earliest_issue_date": mat_sample_earliest,
            "buybacks_2018_2026_count": len(bb_rows),
            "buybacks_strict_pre_settlement_count": bb_lag_pos,
            "nyfed_soma_summary_http_status": st_soma,
            "nyfed_soma_summary_weekly_snapshots": soma_summary_count,
            "nyfed_pd_PDPOSGST_TOT_http_status": st_pd,
            "nyfed_pd_PDPOSGST_TOT_obs_count": len(pd_obs_dates),
            "nyfed_pd_min_max_asofdate": [pd_obs_dates[0], pd_obs_dates[-1]] if pd_obs_dates else None,
            "nyfed_pd_sample_keys_no_value": pd_sample_record,
            "timestamp_safety_finding": (
                "Gross private issuance (total_accepted - soma_accepted) for auctions with auction_date <= t - 1, "
                "scheduled total maturing par from prior auctions (maturity_date == t), and buybacks with "
                "operation_date <= t - 1 are strictly provable as-of (t - 1, 17:00 ET). Exact SOMA holdings "
                "at maturity of older CUSIPs altered by intervening secondary-market QE/QT purchases cannot be "
                "reconstructed from auctions_query soma_accepted alone without CUSIP-level weekly SOMA snapshots "
                "aligned to Thursday release timestamps; therefore Stage 1 specifies a strictly timestamp-safe "
                "gross-private-minus-scheduled-maturing-par-minus-buybacks net supply benchmark (plus separate "
                "gross private coupon issuance) and discloses the exact SOMA-at-maturity limitation."
            ),
        },
        "settlement_date_overlap_waterfall": {
            "step0_raw_note_bond_unique_issue_dates": len(raw_unique_dates),
            "step1_clean_nominal_fixed_coupon_unique_issue_dates": len(nom_dates),
            "step2_primary_F_pair_nonnull_only": sum(1 for d in nom_dates if d in pair_f_nonnull),
            "step3_primary_F_pair_nonnull_plus_all_verified_pre_cutoff_controls": len(matched_f_rows),
            "primary_F_drop_attribution_from_step1": dict(drop_f_reasons),
            "primary_F_dropped_date_examples": dict(dropped_f_examples),
            "robustness_P_step2_pair_nonnull_only": sum(1 for d in nom_dates if d in pair_p_nonnull),
            "robustness_P_step3_pair_nonnull_plus_all_verified_pre_cutoff_controls": len(matched_p_rows),
            "robustness_P_drop_attribution_from_step1": dict(drop_p_reasons),
        },
        "per_year_support": per_year,
        "effective_holdout_counts": {
            "primary_F_2024_01_to_2026_06_30": len(matched_f_2024),
            "primary_F_2023_07_to_2026_06_30": len(matched_f_2023h2),
            "primary_F_train_before_2024_01": len(matched_f_rows) - len(matched_f_2024),
            "primary_F_train_before_2023_07": len(matched_f_rows) - len(matched_f_2023h2),
            "robustness_P_2024_01_to_2026_11": len(matched_p_2024),
            "robustness_P_2023_07_to_2026_11": len(matched_p_2023h2),
        },
        "clean_nominal_x_side_conditional_variation": {
            "primary_F_full_matched": _cond_x_stats(matched_f_rows, "primary_F_clean_nominal_matched"),
            "primary_F_post_2024_holdout": _cond_x_stats(matched_f_2024, "primary_F_post_2024_holdout"),
            "primary_F_post_2023h2_holdout": _cond_x_stats(matched_f_2023h2, "primary_F_post_2023h2_holdout"),
            "robustness_P_post_2024_holdout": _cond_x_stats(matched_p_2024, "robustness_P_post_2024_holdout"),
        },
        "total_elapsed_seconds": round(perf_counter() - t_all, 3),
    }

    OUT_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print("WATERFALL:", json.dumps(payload["settlement_date_overlap_waterfall"], indent=2))
    print("HOLDOUT:", json.dumps(payload["effective_holdout_counts"], indent=2))
    print("PER_YEAR:", json.dumps(per_year, indent=2))
    print(f"Wrote Stage 0B audit: {OUT_PATH}")


if __name__ == "__main__":
    main()
