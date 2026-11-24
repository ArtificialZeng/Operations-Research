"""Stage 0 bounded data feasibility pilot (schema, coverage, timing gap, variation only).

Strictly NO outcome regressions, NO settlement-day spread correlations, and NO
hypothesis tests. Verifies live keyless access, exact JSON schema, missingness,
auction-to-settlement lag (`issue_date > auction_date`), and cross-auction
variation of primary-dealer coupon takedown share on a bounded 2024-2025 window.

Attribution / Terms Notice:
  SOFR, TGCR, BGCR, EFFR, and ON RRP data are retrieved from the Federal Reserve
  Bank of New York Markets Data API and are subject to the Terms of Use posted at
  newyorkfed.org. The New York Fed is not responsible for any use of the data and
  does not sanction, endorse, or recommend this study.
"""

from __future__ import annotations

from datetime import date
import json
from pathlib import Path
from statistics import median
from time import perf_counter
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

OUT_PATH = Path(__file__).resolve().parent / "data_feasibility_pilot.json"
START_DATE = "2024-01-01"
END_DATE = "2025-12-31"
HEADERS = {"User-Agent": "Academic-Research-Feasibility-Check/1.0", "Accept": "application/json"}


def fetch_json(url: str, timeout: float = 20.0) -> tuple[int, dict | list | None, str | None, float]:
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


def main() -> None:
    t_all = perf_counter()
    results: dict = {
        "stage": "stage_0_bounded_data_feasibility_pilot_no_outcome_regressions",
        "window": {"start": START_DATE, "end": END_DATE},
        "nyfed_terms_notice": (
            "SOFR, TGCR, BGCR, EFFR, and ON RRP data are subject to the Terms of Use posted at "
            "newyorkfed.org. The New York Fed is not responsible for any use of the data and does "
            "not sanction, endorse, or recommend this study."
        ),
        "endpoints": {},
    }

    # 1. NY Fed Reference Rates (SOFR, TGCR, BGCR, EFFR) + ON RRP
    nyfed_urls = {
        "sofr": f"https://markets.newyorkfed.org/api/rates/secured/sofr/search.json?startDate={START_DATE}&endDate={END_DATE}",
        "tgcr": f"https://markets.newyorkfed.org/api/rates/secured/tgcr/search.json?startDate={START_DATE}&endDate={END_DATE}",
        "bgcr": f"https://markets.newyorkfed.org/api/rates/secured/bgcr/search.json?startDate={START_DATE}&endDate={END_DATE}",
        "effr": f"https://markets.newyorkfed.org/api/rates/unsecured/effr/search.json?startDate={START_DATE}&endDate={END_DATE}",
        "onrrp": f"https://markets.newyorkfed.org/api/rp/reverserepo/propositions/search.json?startDate={START_DATE}&endDate={END_DATE}",
    }

    rate_dates: dict[str, set[str]] = {}
    for name, url in nyfed_urls.items():
        status, payload, err, dt = fetch_json(url)
        info: dict = {"url": url, "http_status": status, "error": err, "elapsed_seconds": round(dt, 3)}
        if isinstance(payload, dict):
            top_keys = sorted(payload.keys())
            info["top_level_keys"] = top_keys
            if name != "onrrp":
                rows = payload.get("refRates", [])
                info["record_count"] = len(rows)
                if rows:
                    info["sample_keys"] = sorted(rows[0].keys())
                    dates = [r.get("effectiveDate") for r in rows if r.get("effectiveDate")]
                    rate_dates[name] = set(dates)
                    info["min_date"] = min(dates) if dates else None
                    info["max_date"] = max(dates) if dates else None
                    for field in ("percentRate", "percentPercentile1", "percentPercentile25", "percentPercentile75", "percentPercentile99", "volumeInBillions"):
                        non_null = sum(1 for r in rows if _to_float(r.get(field)) is not None)
                        info[f"non_null_{field}"] = non_null
            else:
                ops = payload.get("repo", {}).get("operations", [])
                info["record_count"] = len(ops)
                if ops:
                    info["sample_keys"] = sorted(ops[0].keys())
                    dates = [r.get("operationDate") for r in ops if r.get("operationDate")]
                    rate_dates[name] = set(dates)
                    info["min_date"] = min(dates) if dates else None
                    info["max_date"] = max(dates) if dates else None
                    non_null_acc = sum(1 for r in ops if _to_float(r.get("totalAmtAccepted")) is not None)
                    info["non_null_totalAmtAccepted"] = non_null_acc
        results["endpoints"][name] = info

    # 2. U.S. Treasury Fiscal Data API (auctions_query — Notes & Bonds in 2024-2025)
    treasury_url = (
        "https://api.fiscaldata.treasury.gov/services/api/fiscal_service/v1/accounting/od/auctions_query"
        f"?filter=issue_date:gte:{START_DATE},issue_date:lte:{END_DATE},security_type:in:(Note,Bond)"
        "&sort=issue_date&page[number]=1&page[size]=500"
    )
    status, payload, err, dt = fetch_json(treasury_url)
    t_info: dict = {"url": treasury_url, "http_status": status, "error": err, "elapsed_seconds": round(dt, 3)}
    coupon_audit: dict = {}
    if isinstance(payload, dict) and isinstance(payload.get("data"), list):
        rows = payload["data"]
        meta = payload.get("meta", {})
        t_info["total_count_meta"] = meta.get("total-count")
        t_info["total_pages_meta"] = meta.get("total-pages")
        t_info["fetched_count"] = len(rows)
        if rows:
            sample_keys = sorted(rows[0].keys())
            t_info["num_schema_fields"] = len(sample_keys)
            target_fields = [
                "cusip",
                "security_type",
                "security_term",
                "auction_date",
                "record_date",
                "issue_date",
                "announcemt_date",
                "offering_amt",
                "total_accepted",
                "primary_dealer_accepted",
                "direct_bidder_accepted",
                "indirect_bidder_accepted",
                "high_yield",
                "bid_to_cover_ratio",
            ]
            t_info["present_target_fields"] = {k: (k in rows[0]) for k in target_fields}
            t_info["date_like_fields"] = [k for k in sample_keys if "date" in k.lower()]
            t_info["yield_like_fields"] = [k for k in sample_keys if "yield" in k.lower() or "rate" in k.lower()]

            # Audit non-null completeness, auction-to-settlement lag (issue_date - auction_date), and dealer-share variation (NO repo outcomes!)
            n_rows = len(rows)
            n_pd = 0
            n_tot = 0
            n_hy = 0
            n_direct = 0
            n_indirect = 0
            lags: list[int] = []
            dealer_shares: list[float] = []
            settle_dates: set[str] = set()
            for r in rows:
                idate = r.get("issue_date")
                adate = r.get("auction_date") or r.get("record_date")
                if idate and str(idate).lower() != "null":
                    settle_dates.add(str(idate))
                if idate and adate and str(idate).lower() != "null" and str(adate).lower() != "null":
                    try:
                        lag_days = (date.fromisoformat(str(idate)) - date.fromisoformat(str(adate))).days
                        lags.append(lag_days)
                    except ValueError:
                        pass
                pd_acc = _to_float(r.get("primary_dealer_accepted"))
                dir_acc = _to_float(r.get("direct_bidder_accepted"))
                ind_acc = _to_float(r.get("indirect_bidder_accepted"))
                tot_acc = _to_float(r.get("total_accepted"))
                hy = _to_float(r.get("high_yield"))
                if pd_acc is not None:
                    n_pd += 1
                if dir_acc is not None:
                    n_direct += 1
                if ind_acc is not None:
                    n_indirect += 1
                if tot_acc is not None and tot_acc > 0:
                    n_tot += 1
                if hy is not None:
                    n_hy += 1
                if pd_acc is not None and tot_acc is not None and tot_acc > 0:
                    dealer_shares.append(pd_acc / tot_acc)

            dealer_shares.sort()
            p25 = dealer_shares[len(dealer_shares) // 4] if dealer_shares else None
            p50 = median(dealer_shares) if dealer_shares else None
            p75 = dealer_shares[(3 * len(dealer_shares)) // 4] if dealer_shares else None
            iqr = (p75 - p25) if (p25 is not None and p75 is not None) else None
            sofr_dates = rate_dates.get("sofr", set())
            tgcr_dates = rate_dates.get("tgcr", set())
            matched_settle = sorted(settle_dates & sofr_dates & tgcr_dates)
            coupon_audit = {
                "coupon_auctions_fetched": n_rows,
                "distinct_settlement_dates": len(settle_dates),
                "settlement_dates_matched_to_sofr_and_tgcr": len(matched_settle),
                "non_null_primary_dealer_accepted": n_pd,
                "non_null_direct_bidder_accepted": n_direct,
                "non_null_indirect_bidder_accepted": n_indirect,
                "non_null_total_accepted": n_tot,
                "non_null_high_yield": n_hy,
                "lag_issue_minus_auction_date_count": len(lags),
                "lag_positive_count": sum(1 for x in lags if x > 0),
                "lag_min_median_max_days": (
                    [min(lags), median(lags), max(lags)] if lags else None
                ),
                "dealer_share_count": len(dealer_shares),
                "dealer_share_min_p25_p50_p75_max": (
                    [round(dealer_shares[0], 4), round(p25, 4), round(p50, 4), round(p75, 4), round(dealer_shares[-1], 4)]
                    if dealer_shares
                    else None
                ),
                "dealer_share_iqr_pct_points": round(100.0 * iqr, 2) if iqr is not None else None,
            }
    results["endpoints"]["treasury_auctions_coupons"] = t_info
    results["coupon_feasibility_audit"] = coupon_audit

    # Stage 0 pass/fail check
    all_http_200 = all(v.get("http_status") == 200 for v in results["endpoints"].values())
    pd_rate = (
        coupon_audit.get("non_null_primary_dealer_accepted", 0) / max(1, coupon_audit.get("coupon_auctions_fetched", 0))
        if coupon_audit
        else 0.0
    )
    lag_pos_rate = (
        coupon_audit.get("lag_positive_count", 0) / max(1, coupon_audit.get("lag_issue_minus_auction_date_count", 0))
        if coupon_audit
        else 0.0
    )
    iqr_pp = coupon_audit.get("dealer_share_iqr_pct_points") or 0.0
    results["stage_0_feasibility_gate"] = {
        "all_endpoints_http_200": all_http_200,
        "primary_dealer_non_null_rate": round(pd_rate, 4),
        "positive_auction_to_settlement_lag_rate": round(lag_pos_rate, 4),
        "dealer_share_iqr_pct_points": iqr_pp,
        "stage_0_cleared": bool(all_http_200 and pd_rate >= 0.95 and lag_pos_rate >= 0.95 and iqr_pp >= 3.0),
    }
    results["total_elapsed_seconds"] = round(perf_counter() - t_all, 3)

    OUT_PATH.write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(results["stage_0_feasibility_gate"], indent=2))
    print(json.dumps(coupon_audit, indent=2))
    print(f"Wrote feasibility pilot: {OUT_PATH}")


if __name__ == "__main__":
    main()
