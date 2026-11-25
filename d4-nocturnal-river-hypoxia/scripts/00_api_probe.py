"""Step 0: Polite API schema & connectivity probe for USGS NWIS and UK EA Hydrology API."""
from __future__ import annotations

import json
import time
from pathlib import Path

import requests

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
UA = {"User-Agent": "AcademicResearch-NocturnalRiverHypoxiaAudit/2.0 (contact: hydrology-audit@research.org)"}


def timed_get(label: str, url: str, timeout: tuple[int, int] = (10, 20)) -> requests.Response | None:
    t0 = time.monotonic()
    print(f"  [{label}] GET {url}", flush=True)
    try:
        r = requests.get(url, headers=UA, timeout=timeout)
        print(f"  [{label}] -> status={r.status_code} len={len(r.text)} ({time.monotonic()-t0:.2f}s)", flush=True)
        return r
    except requests.RequestException as exc:
        print(f"  [{label}] -> ERROR {exc} ({time.monotonic()-t0:.2f}s)", flush=True)
        return None


def probe_usgs() -> dict:
    out: dict = {}
    url_exp = (
        "https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd=PA"
        "&parameterCd=00300&hasDataTypeCd=dv&siteType=ST&siteStatus=all&siteOutput=expanded"
    )
    r = timed_get("usgs_site_exp", url_exp)
    if r is not None:
        out["site_expanded_status"] = r.status_code
        if r.status_code == 200:
            lines = [ln for ln in r.text.splitlines() if not ln.startswith("#")]
            out["site_expanded_cols"] = lines[0].split("\t") if lines else []
            out["site_expanded_rows"] = max(0, len(lines) - 2)
            if len(lines) >= 3:
                out["site_expanded_sample"] = dict(zip(lines[0].split("\t"), lines[2].split("\t")))

    url_cat = (
        "https://waterservices.usgs.gov/nwis/site/?format=rdb&stateCd=PA"
        "&parameterCd=00300&hasDataTypeCd=dv&siteType=ST&siteStatus=all&seriesCatalogOutput=true"
    )
    r2 = timed_get("usgs_site_cat", url_cat)
    if r2 is not None:
        out["site_catalog_status"] = r2.status_code
        if r2.status_code == 200:
            lines2 = [ln for ln in r2.text.splitlines() if not ln.startswith("#")]
            out["site_catalog_cols"] = lines2[0].split("\t") if lines2 else []
            out["site_catalog_rows"] = max(0, len(lines2) - 2)

    sample_site = "01570500"
    url_dv = (
        f"https://waterservices.usgs.gov/nwis/dv/?format=rdb&sites={sample_site}"
        "&startDT=2023-06-01&endDT=2023-06-15&parameterCd=00300,00010,00060,00095,63680&statCd=00001,00002,00003"
    )
    r3 = timed_get("usgs_dv", url_dv)
    if r3 is not None:
        out["dv_status"] = r3.status_code
        if r3.status_code == 200:
            lines3 = [ln for ln in r3.text.splitlines() if not ln.startswith("#")]
            out["dv_cols"] = lines3[0].split("\t") if lines3 else []
            out["dv_rows"] = max(0, len(lines3) - 2)

    url_iv = (
        f"https://waterservices.usgs.gov/nwis/iv/?format=rdb&sites={sample_site}"
        "&startDT=2023-07-01&endDT=2023-07-03&parameterCd=00300,00010,00060"
    )
    r4 = timed_get("usgs_iv", url_iv)
    if r4 is not None:
        out["iv_status"] = r4.status_code
        if r4.status_code == 200:
            lines4 = [ln for ln in r4.text.splitlines() if not ln.startswith("#")]
            out["iv_cols"] = lines4[0].split("\t") if lines4 else []
            out["iv_rows"] = max(0, len(lines4) - 2)
            if len(lines4) >= 3:
                out["iv_sample_row"] = dict(zip(lines4[0].split("\t"), lines4[2].split("\t")))
    return out


def probe_uk_ea() -> dict:
    out: dict = {}
    endpoints = {
        "stations_do": "https://environment.data.gov.uk/hydrology/id/stations.json?observedProperty=dissolved-oxygen&_limit=30",
        "measures_do": "https://environment.data.gov.uk/hydrology/id/measures.json?parameter=dissolved-oxygen&_limit=30",
    }
    for name, url in endpoints.items():
        r = timed_get(f"uk_{name}", url, timeout=(8, 15))
        if r is None:
            out[name] = {"error": "timeout_or_conn_err"}
            continue
        rec: dict = {"status": r.status_code}
        if r.status_code == 200:
            js = r.json()
            items = js.get("items", [])
            rec["n_items"] = len(items)
            if items:
                rec["sample_keys"] = list(items[0].keys())
                rec["sample_item"] = {
                    k: items[0].get(k)
                    for k in ("@id", "notation", "label", "parameter", "parameterName", "period", "unitName", "station", "riverName", "lat", "long", "stationStatus")
                    if k in items[0]
                }
        out[name] = rec
    return out


def main() -> None:
    print("Probing USGS NWIS and UK EA Hydrology APIs...", flush=True)
    report = {
        "usgs": probe_usgs(),
        "uk_ea": probe_uk_ea(),
    }
    out_path = BASE_DIR / "data" / "raw_usgs_meta" / "api_probe_report.json"
    out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("DONE probe!", flush=True)


if __name__ == "__main__":
    main()
