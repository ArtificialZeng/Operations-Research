"""
Stage-0 Bounded Feasibility Audit: Spain ESEF 2025 XBRL Precision & Threshold Identifiability.

Locked Protocol: STAGE0_XBRL_PRECISION_PROTOCOL.md
Pre-Launch Gates Asserted BEFORE Network Access:
  1. `filings-2025.json` SHA-256 == f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f
  2. `STAGE0_XBRL_FIXTURE_RECEIPT.json` (`all_fixtures_passed == True`)
  3. `SPAIN_ESEF_2025_COHORT_20_RECEIPT.json` (`n_selected == 20`)
  4. `STAGE0_XBRL_PRECISION_PROTOCOL.md` exists (locked before observing any 2025 filing)

Polite Anonymous Access:
  - Sequential single-threaded HTTP GET to `https://filings.xbrl.org` with `>= 1.5s` delay between requests.
  - Generic non-identifying User-Agent, zero credentials or personal contact disclosure.
  - Stops immediately and reports exact error on HTTP 403/429/503 or non-XML/CAPTCHA block.

Exact Arithmetic & Scope:
  - Parses primary `.xhtml` Inline XBRL (`ix:nonFraction`) with full provenance.
  - Primary test: 1.00% YoY consolidated `ifrs-full:Revenue` growth (`100*A - 101*B > 0`, B > 0).
  - Secondary test 1: 0.00% YoY consolidated `ifrs-full:Revenue` growth (`A - B > 0`, B > 0).
  - Secondary test 2 (prespecified): Change in Gross Margin (`G_t/R_t > G_{t-1}/R_{t-1}`) on reports
    with BOTH consistent consolidated `ifrs-full:GrossProfit` and `ifrs-full:Revenue` for the exact
    same consecutive full FYs and currency.
  - Evaluates official XBRL Calculations 1.1 `round_to_nearest` and `truncation` SEPARATELY with
    programmatic exact `Fraction` witness verification, plus conservative convention-uncertainty label.
  - ZERO LLM calls. Full denominator & exclusion accounting across all 20 independent filings.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import Counter
from typing import Any, Dict, List

BASE = pathlib.Path(os.environ.get("XBRL_AUDIT_BASE", str(pathlib.Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(BASE))

import xbrl_interval_core as xic  # noqa: E402

HOST = "https://filings.xbrl.org"
USER_AGENT = "Mozilla/5.0 (compatible; XBRLPrecisionAudit/1.0)"
POLITE_DELAY_S = 1.5
TIMEOUT_S = 60

EXPECTED_INDEX_SHA256 = "f74e1da4adc6cd7c9513bf4a59cf7953c203faeae5c3f410cc9bfa1a0965885f"


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def polite_download_xhtml(report_url: str, dest_path: pathlib.Path) -> Dict[str, Any]:
    """Downloads one public `.xhtml` report politely with zero credentials; stops on block/429/403."""
    if report_url.startswith("/"):
        encoded_path = urllib.parse.quote(report_url, safe="/:@!$&'()*+,;=-._~%")
        full_url = HOST + encoded_path
    else:
        parts = urllib.parse.urlsplit(report_url)
        full_url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, urllib.parse.quote(parts.path, safe="/:@!$&'()*+,;=-._~%"), parts.query, parts.fragment))
    if dest_path.exists() and dest_path.stat().st_size > 0:
        return {
            "url": full_url,
            "cached": True,
            "http_status": 200,
            "bytes": dest_path.stat().st_size,
            "sha256": sha256_file(dest_path),
        }

    req = urllib.request.Request(
        full_url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/xhtml+xml, application/xml, text/html;q=0.9, */*;q=0.8",
            "Accept-Encoding": "gzip",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            status = resp.status
            if status != 200:
                raise RuntimeError(f"Non-200 HTTP status {status} on {full_url}")
            raw = resp.read()
            c_enc = (resp.headers.get("Content-Encoding") or "").lower()
            if "gzip" in c_enc or raw[:2] == b"\x1f\x8b":
                raw = gzip.decompress(raw)
    except urllib.error.HTTPError as ex:
        raise RuntimeError(f"BLOCKED_OR_HTTP_ERROR status={ex.code} reason={ex.reason} url={full_url}") from ex

    # Basic guard against CAPTCHA / challenge HTML pages
    head_snip = raw[:2048].decode("utf-8", errors="ignore").lower()
    if any(tok in head_snip for tok in ("captcha", "verify you are human", "cloudflare", "access denied")):
        raise RuntimeError(f"BLOCKED_CHALLENGE_PAGE detected on {full_url}")

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(raw)
    return {
        "url": full_url,
        "cached": False,
        "http_status": status,
        "bytes": len(raw),
        "sha256": hashlib.sha256(raw).hexdigest(),
    }


def serialize_fact_provenance(f: Dict[str, Any]) -> Dict[str, Any]:
    """JSON-safe provenance snapshot of one extracted iXBRL fact (excluding non-JSON Fraction object)."""
    return {k: v for k, v in f.items() if k != "exact_value"}


def serialize_dup_meta(m: Dict[str, Any]) -> Dict[str, Any]:
    out = {k: v for k, v in m.items() if k != "all_occurrences"}
    if "all_occurrences" in m:
        out["all_occurrences"] = [serialize_fact_provenance(x) for x in m["all_occurrences"]]
    return out


def main():
    t0 = time.perf_counter()
    pid = os.getpid()

    # 1. HARD PRE-LAUNCH GATES (BEFORE TOUCHING ANY 2025 REPORT)
    idx_p = BASE / "filings-2025.json"
    fix_p = BASE / "STAGE0_XBRL_FIXTURE_RECEIPT.json"
    coh_p = BASE / "SPAIN_ESEF_2025_COHORT_20_RECEIPT.json"
    proto_p = BASE / "STAGE0_XBRL_PRECISION_PROTOCOL.md"

    assert sha256_file(idx_p) == EXPECTED_INDEX_SHA256, "filings-2025.json hash mismatch!"
    assert fix_p.exists() and json.loads(fix_p.read_text(encoding="utf-8"))["all_fixtures_passed"] is True
    assert coh_p.exists(), "Missing locked cohort receipt!"
    assert proto_p.exists(), "Missing locked STAGE0_XBRL_PRECISION_PROTOCOL.md!"

    cohort = json.loads(coh_p.read_text(encoding="utf-8"))
    filings = cohort["selected_filings"]
    assert len(filings) == 20

    print(f"=== Stage-0 Spain ESEF 2025 Precision & Threshold Audit (PID={pid}, N={len(filings)} independent LEIs) ===", flush=True)

    dl_dir = BASE / "downloaded_esef_es_2025_xhtml"
    dl_dir.mkdir(parents=True, exist_ok=True)
    out_dir = BASE / "stage0_audit_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    jsonl_p = out_dir / "spain_esef_2025_per_filing.jsonl"

    records: List[Dict[str, Any]] = []
    did_network_req = False

    with jsonl_p.open("w", encoding="utf-8") as fout:
        for i, fl in enumerate(filings):
            lei = fl["lei"]
            fxo_id = fl["fxo_id"]
            report_url = fl["report_url"]
            dest = dl_dir / f"{i+1:02d}_{fxo_id}.xhtml"

            if did_network_req and not dest.exists():
                time.sleep(POLITE_DELAY_S)

            dl_info = polite_download_xhtml(report_url, dest)
            if not dl_info["cached"]:
                did_network_req = True

            rec: Dict[str, Any] = {
                "cohort_idx": i + 1,
                "lei": lei,
                "entity_name": fl["entity_name"],
                "filing_id": fl["filing_id"],
                "fxo_id": fxo_id,
                "index_period_end": fl["period_end"],
                "download": dl_info,
            }

            try:
                parsed = xic.parse_ixbrl_numeric_facts(str(dest))
                rec["ixbrl_summary"] = {
                    "n_contexts": parsed["n_contexts"],
                    "n_units": parsed["n_units"],
                    "has_consolidated_separate_axis": parsed["has_consolidated_separate_axis"],
                    "n_ifrs_revenue_facts_total": sum(1 for f in parsed["target_facts"] if f["local_name"] == "Revenue"),
                    "n_ifrs_gross_profit_facts_total": sum(1 for f in parsed["target_facts"] if f["local_name"] == "GrossProfit"),
                    "n_target_parse_errors": len(parsed["target_parse_errors"]),
                    "target_parse_errors": parsed["target_parse_errors"],
                }

                # Primary Revenue extraction (consecutive full FYs ending in 2025, dims == [], same currency)
                rev = xic.extract_consecutive_fy_pair(parsed["target_facts"], "Revenue", expected_fy_end_year=2025)
                if not rev["ok"]:
                    rec["revenue_eligible"] = False
                    rec["revenue_exclusion_reason"] = rev["exclusion_reason"]
                    rec["revenue_exclusion_detail"] = {k: v for k, v in rev.items() if k not in ("ok", "exclusion_reason")}
                else:
                    cf = rev["current_fact"]
                    pf = rev["prior_fact"]
                    yoy_1_n = xic.evaluate_yoy_threshold(cf["exact_value"], cf["decimals"], pf["exact_value"], pf["decimals"], 1, 100, "round_to_nearest")
                    yoy_1_t = xic.evaluate_yoy_threshold(cf["exact_value"], cf["decimals"], pf["exact_value"], pf["decimals"], 1, 100, "truncation")
                    yoy_0_n = xic.evaluate_yoy_threshold(cf["exact_value"], cf["decimals"], pf["exact_value"], pf["decimals"], 0, 1, "round_to_nearest")
                    yoy_0_t = xic.evaluate_yoy_threshold(cf["exact_value"], cf["decimals"], pf["exact_value"], pf["decimals"], 0, 1, "truncation")

                    if not (yoy_1_n["eligible"] and yoy_1_t["eligible"]):
                        rec["revenue_eligible"] = False
                        rec["revenue_exclusion_reason"] = yoy_1_n.get("exclusion_reason") or yoy_1_t.get("exclusion_reason")
                    else:
                        rec["revenue_eligible"] = True
                        rec["revenue_exclusion_reason"] = None

                    rec["revenue_pair"] = {
                        "currency": rev["currency"],
                        "current_fact": serialize_fact_provenance(cf),
                        "current_dup_meta": serialize_dup_meta(rev["current_dup_meta"]),
                        "prior_fact": serialize_fact_provenance(pf),
                        "prior_dup_meta": serialize_dup_meta(rev["prior_dup_meta"]),
                        "threshold_1pct": {
                            "round_to_nearest": yoy_1_n,
                            "truncation": yoy_1_t,
                            "conservative_label": xic.conservative_convention_label(yoy_1_n, yoy_1_t),
                        },
                        "threshold_0pct": {
                            "round_to_nearest": yoy_0_n,
                            "truncation": yoy_0_t,
                            "conservative_label": xic.conservative_convention_label(yoy_0_n, yoy_0_t),
                        },
                    }

                # Secondary Prespecified Accounting Comparison: Change in Gross Margin (only if BOTH consistent tags match exact FYs & currency)
                gp = xic.extract_consecutive_fy_pair(parsed["target_facts"], "GrossProfit", expected_fy_end_year=2025)
                if not rec.get("revenue_eligible"):
                    rec["gross_margin_eligible"] = False
                    rec["gross_margin_exclusion_reason"] = "revenue_ineligible"
                elif not gp["ok"]:
                    rec["gross_margin_eligible"] = False
                    rec["gross_margin_exclusion_reason"] = gp["exclusion_reason"]
                else:
                    g_cf = gp["current_fact"]
                    g_pf = gp["prior_fact"]
                    r_cf = rev["current_fact"]
                    r_pf = rev["prior_fact"]
                    same_scope = (
                        gp["currency"] == rev["currency"]
                        and g_cf["period_start"][:10] == r_cf["period_start"][:10]
                        and g_cf["period_end"][:10] == r_cf["period_end"][:10]
                        and g_pf["period_start"][:10] == r_pf["period_start"][:10]
                        and g_pf["period_end"][:10] == r_pf["period_end"][:10]
                    )
                    if not same_scope:
                        rec["gross_margin_eligible"] = False
                        rec["gross_margin_exclusion_reason"] = "gross_profit_period_or_currency_mismatch_with_revenue"
                    else:
                        gm_n = xic.evaluate_gross_margin_change(
                            g_cf["exact_value"], g_cf["decimals"], r_cf["exact_value"], r_cf["decimals"],
                            g_pf["exact_value"], g_pf["decimals"], r_pf["exact_value"], r_pf["decimals"],
                            "round_to_nearest",
                        )
                        gm_t = xic.evaluate_gross_margin_change(
                            g_cf["exact_value"], g_cf["decimals"], r_cf["exact_value"], r_cf["decimals"],
                            g_pf["exact_value"], g_pf["decimals"], r_pf["exact_value"], r_pf["decimals"],
                            "truncation",
                        )
                        rec["gross_margin_eligible"] = bool(gm_n["eligible"] and gm_t["eligible"])
                        rec["gross_margin_exclusion_reason"] = None if rec["gross_margin_eligible"] else (gm_n.get("exclusion_reason") or gm_t.get("exclusion_reason"))
                        rec["gross_margin_pair"] = {
                            "currency": gp["currency"],
                            "gross_profit_current": serialize_fact_provenance(g_cf),
                            "gross_profit_prior": serialize_fact_provenance(g_pf),
                            "delta_gm_gt_0": {
                                "round_to_nearest": gm_n,
                                "truncation": gm_t,
                                "conservative_label": xic.conservative_convention_label(gm_n, gm_t),
                            },
                        }

            except Exception as ex:
                rec["xml_or_pipeline_error"] = str(ex)
                rec["revenue_eligible"] = False
                rec["revenue_exclusion_reason"] = f"xml_parse_error: {ex}"
                rec["gross_margin_eligible"] = False
                rec["gross_margin_exclusion_reason"] = "xml_parse_error"

            records.append(rec)
            fout.write(json.dumps(rec, ensure_ascii=False) + "\n")
            fout.flush()

            if rec.get("revenue_eligible"):
                t1 = rec["revenue_pair"]["threshold_1pct"]
                cf = rec["revenue_pair"]["current_fact"]
                pf = rec["revenue_pair"]["prior_fact"]
                gm_tag = rec["gross_margin_pair"]["delta_gm_gt_0"]["conservative_label"] if rec.get("gross_margin_eligible") else "no_GM"
                print(
                    f"  [{i+1:2d}/20] {lei} | {fl['entity_name'][:28]:28s} | dec=({cf['decimals']},{pf['decimals']}) | "
                    f"g={t1['round_to_nearest']['displayed_growth_pct']}% | "
                    f"1%=[N:{t1['round_to_nearest']['status']}, T:{t1['truncation']['status']}] | GM={gm_tag}",
                    flush=True,
                )
            else:
                print(
                    f"  [{i+1:2d}/20] {lei} | {fl['entity_name'][:28]:28s} | EXCLUDED_REV: {rec['revenue_exclusion_reason']}",
                    flush=True,
                )

    # 2. AGGREGATE EXACT DENOMINATORS, EXCLUSIONS, FLIP COUNTS & PRECISION DISTRIBUTION
    n_total = len(records)
    rev_elig = [r for r in records if r.get("revenue_eligible")]
    rev_excl = [r for r in records if not r.get("revenue_eligible")]
    gm_elig = [r for r in records if r.get("gross_margin_eligible")]
    gm_excl = [r for r in records if not r.get("gross_margin_eligible")]

    def tally_test(subset: List[Dict], path_fn) -> Dict[str, Any]:
        c_n = Counter()
        c_t = Counter()
        c_cons = Counter()
        strict_flip_cases = []
        tie_cases = []
        touch_cases = []
        for r in subset:
            blk = path_fn(r)
            sn = blk["round_to_nearest"]["status"]
            st = blk["truncation"]["status"]
            sc = blk["conservative_label"]
            c_n[sn] += 1
            c_t[st] += 1
            c_cons[sc] += 1
            if sn == "strict_non_tie_flip" or st == "strict_non_tie_flip":
                strict_flip_cases.append({
                    "lei": r["lei"],
                    "entity_name": r["entity_name"],
                    "fxo_id": r["fxo_id"],
                    "round_to_nearest": blk["round_to_nearest"],
                    "truncation": blk["truncation"],
                    "conservative_label": sc,
                })
            if sn == "exact_displayed_tie" or st == "exact_displayed_tie":
                tie_cases.append({"lei": r["lei"], "entity_name": r["entity_name"]})
            if sn == "endpoint_touch_only" or st == "endpoint_touch_only":
                touch_cases.append({"lei": r["lei"], "entity_name": r["entity_name"]})
        return {
            "n_eligible": len(subset),
            "round_to_nearest_counts": dict(c_n),
            "truncation_counts": dict(c_t),
            "conservative_label_counts": dict(c_cons),
            "n_strict_non_tie_flips_round_to_nearest": c_n["strict_non_tie_flip"],
            "n_strict_non_tie_flips_truncation": c_t["strict_non_tie_flip"],
            "n_strict_non_tie_flips_either_rule": len(strict_flip_cases),
            "strict_non_tie_flip_cases": strict_flip_cases,
            "exact_displayed_tie_cases": tie_cases,
            "endpoint_touch_only_cases": touch_cases,
        }

    dec_pairs = Counter(
        (str(r["revenue_pair"]["current_fact"]["decimals"]), str(r["revenue_pair"]["prior_fact"]["decimals"]))
        for r in rev_elig
    )
    currencies = Counter(r["revenue_pair"]["currency"] for r in rev_elig)

    summary = {
        "protocol": "STAGE0_XBRL_PRECISION_PROTOCOL.md",
        "protocol_sha256": sha256_file(proto_p),
        "real_pid": pid,
        "wall_time_s": time.perf_counter() - t0,
        "input_and_code_hashes": {
            "filings_2025_json": sha256_file(idx_p),
            "xbrl_interval_core_py": sha256_file(BASE / "xbrl_interval_core.py"),
            "STAGE0_XBRL_FIXTURE_RECEIPT_json": sha256_file(fix_p),
            "SPAIN_ESEF_2025_COHORT_20_RECEIPT_json": sha256_file(coh_p),
            "run_spain_esef_2025_audit_py": sha256_file(pathlib.Path(__file__)),
            "spain_esef_2025_per_filing_jsonl": sha256_file(jsonl_p),
        },
        "cohort_denominators": {
            "n_spain_esef_v0_unique_leis_in_2025_index": cohort["n_es_esef_v0_unique_leis_in_index"],
            "n_selected_bounded_cohort": n_total,
            "n_downloaded_successfully": sum(1 for r in records if r["download"]["http_status"] == 200),
            "n_revenue_eligible": len(rev_elig),
            "n_revenue_excluded": len(rev_excl),
            "revenue_exclusion_reasons": dict(Counter(r["revenue_exclusion_reason"] for r in rev_excl)),
            "revenue_decimals_pairs": {f"({k[0]}, {k[1]})": v for k, v in sorted(dec_pairs.items())},
            "revenue_currencies": dict(currencies),
            "n_gross_margin_eligible": len(gm_elig),
            "n_gross_margin_excluded": len(gm_excl),
            "gross_margin_exclusion_reasons": dict(Counter(r["gross_margin_exclusion_reason"] for r in gm_excl)),
        },
        "primary_1pct_yoy_revenue_growth": tally_test(rev_elig, lambda r: r["revenue_pair"]["threshold_1pct"]),
        "secondary_0pct_yoy_revenue_growth": tally_test(rev_elig, lambda r: r["revenue_pair"]["threshold_0pct"]),
        "secondary_gross_margin_change": tally_test(gm_elig, lambda r: r["gross_margin_pair"]["delta_gm_gt_0"]),
    }

    sum_p = out_dir / "spain_esef_2025_summary.json"
    sum_p.write_text(json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    p1 = summary["primary_1pct_yoy_revenue_growth"]
    p0 = summary["secondary_0pct_yoy_revenue_growth"]
    gm = summary["secondary_gross_margin_change"]
    print(f"\n=== Stage-0 Spain ESEF 2025 Audit COMPLETE (PID={pid}, wall={summary['wall_time_s']:.1f}s) ===", flush=True)
    print(f"Eligible denominators: Revenue={len(rev_elig)}/{n_total} (excl={dict(summary['cohort_denominators']['revenue_exclusion_reasons'])}), GrossMargin={len(gm_elig)}/{n_total}", flush=True)
    print(f"Revenue decimals pairs: {summary['cohort_denominators']['revenue_decimals_pairs']}", flush=True)
    print(f"PRIMARY 1.00% YoY Revenue Growth: strict non-tie flips N={p1['n_strict_non_tie_flips_round_to_nearest']}, T={p1['n_strict_non_tie_flips_truncation']}, either={p1['n_strict_non_tie_flips_either_rule']} | ties={len(p1['exact_displayed_tie_cases'])} | touch={len(p1['endpoint_touch_only_cases'])}", flush=True)
    print(f"SECONDARY 0.00% YoY Revenue Growth: strict non-tie flips N={p0['n_strict_non_tie_flips_round_to_nearest']}, T={p0['n_strict_non_tie_flips_truncation']}, either={p0['n_strict_non_tie_flips_either_rule']}", flush=True)
    print(f"SECONDARY Gross Margin Change: strict non-tie flips N={gm['n_strict_non_tie_flips_round_to_nearest']}, T={gm['n_strict_non_tie_flips_truncation']}, either={gm['n_strict_non_tie_flips_either_rule']}", flush=True)
    print(f"Saved {sum_p} (sha256={sha256_file(sum_p)})", flush=True)


if __name__ == "__main__":
    main()
