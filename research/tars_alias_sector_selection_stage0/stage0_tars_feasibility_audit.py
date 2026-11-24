"""
Stage-0 Step 1 — TARS Public Data Feasibility, Coverage & Raw FITS Verification Audit.

STRICT BLINDNESS GUARD:
  - From validation_samples.zip feathers, reads ONLY ['TICID', 'sector', 'camera', 'ccd', 'Tmag', 'Prot'],
    immediately converting 'Prot' to a boolean `has_ref_prot = isfinite(Prot) & (Prot > 0)` and
    DISCARDING numeric `Prot` values completely (NEVER printed, saved, or used for selection!).
  - NEVER reads TARS period/power/classifier/adopted columns or FITS HDU-1 periodogram headers.
  - Verifies 12+ genuine per-sector TARS FITS directly from MAST (including co-located stars on the
    same (sector, camera, ccd) to test whether TIME arrays are pure temporal sampling or star-specific).
"""
from __future__ import annotations

import hashlib
import json
import pathlib
import urllib.request
import zipfile
from typing import Any, Dict, List

import numpy as np
import pandas as pd
import pyarrow.feather as pf
from astropy.io import fits


ROOT = pathlib.Path(__file__).resolve().parent
RAW_DIR = ROOT / "raw_stage0"
FITS_DIR = RAW_DIR / "verified_fits"
FITS_DIR.mkdir(parents=True, exist_ok=True)
OUT_DIR = ROOT / "stage0_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)


def tars_mast_url(sector: int, camera: int, ccd: int, tic: int) -> str:
    # Verified pattern from MAST CAOM: mast:HLSP/tars/sec_<sec>_cam_<cam>_ccd_<ccd>/hlsp_tars_tess_ffi_s<SSSS>-<TIC16>_tess_v01_lc.fits
    # Note: let's test both unpadded sec_{sector} and zero-padded if sector < 10!
    return (
        f"https://mast.stsci.edu/api/v0.1/Download/file?uri="
        f"mast:HLSP/tars/sec_{sector}_cam_{camera}_ccd_{ccd}/"
        f"hlsp_tars_tess_ffi_s{sector:04d}-{tic:016d}_tess_v01_lc.fits"
    )


def mast_caom_lookup_lc_uri(tic: int, sector: int) -> str:
    """Fallback authoritative MAST CAOM API lookup if direct URL pattern differs for early sectors."""
    payload = json.dumps({
        "service": "Mast.Caom.Filtered",
        "format": "json",
        "params": {
            "columns": "obsid,target_name,sequence_number,dataURL",
            "filters": [
                {"paramName": "provenance_name", "values": ["tars"]},
                {"paramName": "target_name", "values": [str(tic)]},
                {"paramName": "sequence_number", "values": [int(sector)]},
            ],
        },
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://mast.stsci.edu/api/v0/invoke",
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "Python-urllib/3.12"},
    )
    resp = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))
    rows = resp.get("data", [])
    if not rows:
        raise RuntimeError(f"No CAOM record for TIC {tic} sector {sector}")
    obsid = rows[0]["obsid"]
    p2 = json.dumps({
        "service": "Mast.Caom.Products",
        "format": "json",
        "params": {"obsid": str(obsid)},
    }).encode("utf-8")
    req2 = urllib.request.Request(
        "https://mast.stsci.edu/api/v0/invoke",
        data=p2,
        headers={"Content-Type": "application/json", "User-Agent": "Python-urllib/3.12"},
    )
    r2 = json.loads(urllib.request.urlopen(req2, timeout=30).read().decode("utf-8"))
    for prod in r2.get("data", []):
        uri = prod.get("dataURI", "")
        if uri.endswith("_lc.fits"):
            return f"https://mast.stsci.edu/api/v0.1/Download/file?uri={uri}"
    raise RuntimeError(f"No _lc.fits product for obsid {obsid}")


def download_tars_fits(tic: int, sector: int, camera: int, ccd: int) -> Dict[str, Any]:
    fname = f"hlsp_tars_tess_ffi_s{sector:04d}-{tic:016d}_tess_v01_lc.fits"
    dst = FITS_DIR / fname
    url_direct = tars_mast_url(sector, camera, ccd, tic)
    used_url = url_direct
    used_fallback = False

    if not dst.exists():
        try:
            req = urllib.request.Request(url_direct, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            if len(data) < 2880 or not data.startswith(b"SIMPLE"):
                raise ValueError(f"Non-FITS response ({len(data)} B)")
            dst.write_bytes(data)
        except Exception:
            used_url = mast_caom_lookup_lc_uri(tic, sector)
            used_fallback = True
            req = urllib.request.Request(used_url, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
            with urllib.request.urlopen(req, timeout=45) as r:
                data = r.read()
            assert data.startswith(b"SIMPLE"), "Fallback did not return FITS!"
            dst.write_bytes(data)
    else:
        data = dst.read_bytes()

    with fits.open(dst) as hdul:
        h0 = hdul[0].header
        h1 = hdul[1].header
        tab = hdul[1].data
        cols = [(c.name, c.format, c.unit) for c in tab.columns]
        t = np.asarray(tab["TIME"], dtype=np.float64)
        fl = np.asarray(tab["FLUX"], dtype=np.float64)
        good = np.isfinite(t) & np.isfinite(fl)
        t_g = t[good]
        dt = np.diff(t_g)
        med_dt_s = float(np.median(dt) * 86400.0)
        gaps_05 = dt[dt > 0.5]
        # Verify primary metadata matches
        assert int(h0["TICID"]) == int(tic)
        assert int(h0["SECTOR"]) == int(sector)
        hdu1_flux_hdr_keys = [k for k in ("PER1", "POW1", "PER2", "POW2", "AMPFIT", "SNR", "BIC1T") if k in h1]

    return {
        "tic": int(tic),
        "sector": int(sector),
        "camera": int(camera),
        "ccd": int(ccd),
        "filename": fname,
        "url": used_url,
        "used_caom_fallback": used_fallback,
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "license": str(h0.get("LICENSE", "")),
        "doi": str(h0.get("DOI", "")),
        "columns": cols,
        "has_quality_col": any("QUAL" in c[0].upper() for c in cols),
        "flux_derived_hdu1_headers_present_must_ignore": hdu1_flux_hdr_keys,
        "n_rows": int(len(t)),
        "n_finite": int(good.sum()),
        "t_start_btjd": round(float(t_g[0]), 6),
        "t_stop_btjd": round(float(t_g[-1]), 6),
        "span_days": round(float(t_g[-1] - t_g[0]), 5),
        "median_cadence_s": round(med_dt_s, 2),
        "exptime_hdr_s": h0.get("EXPTIME"),
        "max_gap_days": round(float(np.max(dt)), 5),
        "n_gaps_gt_0p5d": int(len(gaps_05)),
        "total_gap_gt_0p5d_days": round(float(np.sum(gaps_05)), 5),
        "flux_median": round(float(np.median(fl[good])), 6),
        "flux_iqr": round(float(np.percentile(fl[good], 75) - np.percentile(fl[good], 25)), 6),
    }


def main() -> None:
    zpath = RAW_DIR / "validation_samples.zip"
    cov_summary: Dict[str, Any] = {}
    cov_dfs: Dict[str, pd.DataFrame] = {}

    # 1. STRICT LABEL-BLIND COVERAGE AUDIT (NO numeric Prot values or TARS period columns ever kept!)
    with zipfile.ZipFile(zpath) as zf:
        for tag, member in [
            ("k2", "validation_samples/k2_validation_sample.feather"),
            ("mcquillan", "validation_samples/mcquillan_holdout.feather"),
        ]:
            with zf.open(member) as f:
                tbl = pf.read_table(f, columns=["TICID", "sector", "camera", "ccd", "Tmag", "Prot"])
            df = tbl.to_pandas()
            df["has_valid_ref_prot"] = np.isfinite(df["Prot"].to_numpy(dtype=np.float64)) & (df["Prot"].to_numpy(dtype=np.float64) > 0.0)
            # IMMEDIATELY drop numeric Prot so selection cannot touch it!
            df = df.drop(columns=["Prot"])
            df = df[df["has_valid_ref_prot"]].drop_duplicates(subset=["TICID", "sector"]).copy()
            cov_dfs[tag] = df

            sec_counts = df.groupby("TICID")["sector"].nunique()
            n_total_stars = int(len(sec_counts))
            n_ge2 = int((sec_counts >= 2).sum())
            n_ge3 = int((sec_counts >= 3).sum())
            n_ge4 = int((sec_counts >= 4).sum())
            n_ge5 = int((sec_counts >= 5).sum())
            sec_min, sec_max = int(df["sector"].min()), int(df["sector"].max())
            cov_summary[tag] = {
                "rows_valid_ref_prot": int(len(df)),
                "unique_tics_valid_ref_prot": n_total_stars,
                "tics_ge2_sectors": n_ge2,
                "tics_ge3_sectors_S1_plus_ge2_S2": n_ge3,
                "tics_ge4_sectors": n_ge4,
                "tics_ge5_sectors": n_ge5,
                "sector_range": [sec_min, sec_max],
            }
            print(f"[{tag:10s}] unique TICs={n_total_stars:5d} | >=2 secs: {n_ge2:5d} | >=3 secs (S1 + >=2 S2): {n_ge3:5d} | >=4: {n_ge4:5d} | >=5: {n_ge5:5d} | sectors={sec_min}..{sec_max}")

    # Check overlap between K2 and McQuillan TICs
    k2_ge3 = set(cov_dfs["k2"].groupby("TICID")["sector"].nunique().loc[lambda s: s >= 3].index)
    mcq_ge3 = set(cov_dfs["mcquillan"].groupby("TICID")["sector"].nunique().loc[lambda s: s >= 3].index)
    print(f"Overlap between K2>=3 and McQuillan>=3: {len(k2_ge3 & mcq_ge3)} TICs")

    # 2. Deterministically pick 4 multi-sector stars (2 K2 + 2 McQuillan, by SHA-256 hash of TICID)
    #    and verify 3 sectors each = 12 genuine per-sector FITS files directly from MAST!
    verified_fits: List[Dict[str, Any]] = []
    for tag, pool in [("k2", sorted(k2_ge3)), ("mcquillan", sorted(mcq_ge3))]:
        ordered = sorted(pool, key=lambda x: hashlib.sha256(f"stage0_fits_smoke:{tag}:{x}".encode()).hexdigest())
        df = cov_dfs[tag]
        picked_stars = 0
        for tic in ordered:
            sub = df[df["TICID"] == tic].sort_values("sector")
            # Prefer a star spanning both early (<27) and later (>=27) sectors for cadence check if present, else first 3
            secs = sub.to_dict("records")
            chosen_rows = [secs[0], secs[len(secs)//2], secs[-1]]
            star_ok = True
            star_recs = []
            for row in chosen_rows:
                try:
                    rec = download_tars_fits(int(row["TICID"]), int(row["sector"]), int(row["camera"]), int(row["ccd"]))
                    rec["benchmark_source"] = tag
                    star_recs.append(rec)
                except Exception as e:
                    print(f"  WARN download failed TIC {tic} S{row['sector']}: {e}")
                    star_ok = False
                    break
            if star_ok:
                verified_fits.extend(star_recs)
                picked_stars += 1
                print(f"  VERIFIED STAR ({tag}) TIC {tic}: sectors={[r['sector'] for r in star_recs]} | cadences={[r['median_cadence_s'] for r in star_recs]}s | spans={[r['span_days'] for r in star_recs]}d | n_rows={[r['n_rows'] for r in star_recs]}")
            if picked_stars >= 2:
                break

    # 3. CRITICAL QUALITY-MASK / TEMPORAL-SAMPLING AUDIT:
    #    Find 2 DIFFERENT stars on the EXACT SAME (sector, camera, ccd) and compare their TIME arrays!
    first_rec = verified_fits[0]
    same_scc = cov_dfs[first_rec["benchmark_source"]]
    peers = same_scc[
        (same_scc["sector"] == first_rec["sector"])
        & (same_scc["camera"] == first_rec["camera"])
        & (same_scc["ccd"] == first_rec["ccd"])
        & (same_scc["TICID"] != first_rec["tic"])
    ].sort_values("TICID")
    colocated_audit = None
    if len(peers) > 0:
        peer_row = peers.iloc[0]
        rec_peer = download_tars_fits(int(peer_row["TICID"]), int(peer_row["sector"]), int(peer_row["camera"]), int(peer_row["ccd"]))
        rec_peer["benchmark_source"] = first_rec["benchmark_source"]
        verified_fits.append(rec_peer)
        with fits.open(FITS_DIR / first_rec["filename"]) as h1, fits.open(FITS_DIR / rec_peer["filename"]) as h2:
            t1 = np.asarray(h1[1].data["TIME"], dtype=np.float64)
            t2 = np.asarray(h2[1].data["TIME"], dtype=np.float64)
        same_len = (len(t1) == len(t2))
        max_abs_dt_diff_s = float(np.max(np.abs(t1 - t2)) * 86400.0) if same_len else None
        # Compare rounded to 10-second grid (barycentric correction differs by up to ~few minutes across a CCD!)
        # Actually barycentric light-travel time shifts TIME smoothly across sky coordinates; check cadence-count equality!
        colocated_audit = {
            "sector": first_rec["sector"],
            "camera": first_rec["camera"],
            "ccd": first_rec["ccd"],
            "tic_a": first_rec["tic"],
            "tic_b": rec_peer["tic"],
            "n_rows_a": int(len(t1)),
            "n_rows_b": int(len(t2)),
            "same_row_count": bool(same_len),
            "span_a_days": first_rec["span_days"],
            "span_b_days": rec_peer["span_days"],
            "max_abs_barycentric_time_diff_s": round(max_abs_dt_diff_s, 3) if max_abs_dt_diff_s is not None else None,
            "diff_std_s": round(float(np.std(t1 - t2) * 86400.0), 3) if same_len else None,
        }
        print("\n=== CO-LOCATED SAME (SECTOR, CAMERA, CCD) TIME-SAMPLING AUDIT ===")
        print(json.dumps(colocated_audit, indent=2))

    out_p = OUT_DIR / "stage0_fits_and_coverage_receipt.json"
    out_p.write_text(json.dumps({
        "coverage_summary_label_blind": cov_summary,
        "n_verified_fits": len(verified_fits),
        "verified_fits": verified_fits,
        "colocated_time_sampling_audit": colocated_audit,
    }, indent=2), encoding="utf-8")
    print(f"\nSaved Stage-0 FITS & coverage receipt -> {out_p} (SHA256={hashlib.sha256(out_p.read_bytes()).hexdigest()})")


if __name__ == "__main__":
    main()
