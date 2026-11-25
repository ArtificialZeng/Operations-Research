"""Step 4: Independent International Non-U.S. Replication — UK Environment Agency 15-Min Continuous River DO & Temp."""
from __future__ import annotations

import io
import json
import math
import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy import stats

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
UK_DIR = BASE_DIR / "data" / "raw_uk_ea"
PROC_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"
UA = {"User-Agent": "AcademicResearch-NocturnalRiverHypoxiaAudit/2.0 (contact: hydrology-audit@research.org)"}

UK_EXCL_RE = re.compile(
    r"(\bDAM\b|\bWEIR\b|\bSLUICE\b|\bLOCK\b|\bCANAL\b|\bLAKE\b|\bPOND\b|\bMERE\b|"
    r"\bRESERVOIR\b|\bLAGOON\b|\bTIDAL\b|\bESTUARY\b|\bHARBOUR\b|\bHARBOR\b|\bPIER\b|"
    r"\bBARGE\b|\bDOCK\b|\bQUAY\b|\bWHARF\b|\bPORT\b|\bBAY\b|\bSANDBAY\b|\bMARINA\b|\bINLET\b|"
    r"\bSTW\b|\bCSO\b|\bWWTW\b|\bTW\b|\bSEWAGE\b|\bEFFLUENT\b|\bOUTFALL\b|\bWORKS\b|"
    r"\bCONSENTED\s+DISCHARGE\b|\bGW\b|\bGROUNDWATER\b|\bBOREHOLE\b|\bADIT\b|\bDYKE\b|"
    r"\bMILL\s+RACE\b|\bIDB\s+WATERCOURSE\b|\bORWELL\b|\bTOFT\s+NEWTON\b|\bSALMON\s+POOL\b|"
    r"\bSILT\s+REMOVAL\b|\bLANDFILL\b|\bMINE\b|\bQUARRY\b|\bDITCH\b|\bDRAIN\b|"
    r"\bCULVERT\b|\bPUMPING\b|\bPUMP\s+STA|\bINTAKE\b|\bABSTRACTION\b|\bSPRING\b|"
    r"\bCONSTRUCTION\s+SITE\b|\bRESORT\b|\bPOLZEATH\b|"
    r"TYNE.*SWING|WITHAM.*BOSTON|LEVEN.*NEWBY|\bCUNSEY\b|EHEN.*(?:OXBOW|BLEACH)|"
    r"CHISWICK|BRENTFORD|PUTNEY|ERITH|KEW|HAMMERSMITH|CADOGAN|WOOLWICH|CROSSNESS|"
    r"PURFLEET|TILBURY|MUCKING|BECKTON|GREENWICH|BARNES|RICHMOND|TEDDINGTON|"
    r"ISLEWORTH|WESTMINSTER|WATERLOO|THAMES\s+LONDON|BARRIER)",
    re.IGNORECASE,
)


def benson_krause_do_sat(temp_c: np.ndarray) -> np.ndarray:
    t_k = np.asarray(temp_c, dtype=float) + 273.15
    ln_c = (
        -139.34411
        + 1.575701e5 / t_k
        - 6.642308e7 / (t_k**2)
        + 1.243800e10 / (t_k**3)
        - 8.621949e11 / (t_k**4)
    )
    return np.exp(ln_c)


def polite_get(url: str, timeout: tuple[int, int] = (10, 35)) -> requests.Response | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200:
                return r
            if r.status_code in (403, 404):
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2.5 * (attempt + 1))
            else:
                return None
        except requests.RequestException:
            time.sleep(2.5 * (attempt + 1))
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r_e = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2.0 * r_e * math.asin(min(1.0, math.sqrt(a)))


def discover_uk_stations() -> tuple[pd.DataFrame, dict]:
    cache = UK_DIR / "uk_ea_do_stations.json"
    if cache.exists():
        js = json.loads(cache.read_text(encoding="utf-8"))
    else:
        url = "https://environment.data.gov.uk/hydrology/id/stations.json?observedProperty=dissolved-oxygen&_limit=5000"
        r = polite_get(url, timeout=(15, 45))
        if r is None or r.status_code != 200:
            raise RuntimeError(f"UK EA station discovery failed: {None if r is None else r.status_code}")
        js = r.json()
        cache.write_text(json.dumps(js), encoding="utf-8")

    items = js.get("items", [])
    candidates = []
    excluded = 0
    for it in items:
        notation = str(it.get("notation", "")).strip()
        label = str(it.get("label", "")).strip()
        lat = it.get("lat")
        lon = it.get("long")
        if lat is None or lon is None:
            continue
        try:
            lat_f, lon_f = float(lat), float(lon)
        except (ValueError, TypeError):
            lat_f, lon_f = np.nan, np.nan
        if not (np.isfinite(lat_f) and np.isfinite(lon_f) and 49.8 <= lat_f <= 56.0 and -6.0 <= lon_f <= 2.0):
            continue

        measures = it.get("measures", [])
        do_id = None
        temp_id = None
        for m in measures:
            mid = str(m.get("@id", ""))
            if mid.endswith("-do-i-subdaily-mgL"):
                do_id = mid.split("/")[-1]
            elif mid.endswith("-temp-i-subdaily-C"):
                temp_id = mid.split("/")[-1]
        if not do_id or not temp_id:
            continue

        op = str(it.get("dateOpened") or "")[:10]
        cl = str(it.get("dateClosed") or "2025-12-31")[:10]
        if len(op) < 10 or len(cl) < 10:
            continue
        try:
            span_days = (pd.Timestamp(cl) - pd.Timestamp(op)).days
        except (ValueError, TypeError):
            span_days = -1
        if span_days < 450:
            continue

        label_norm = re.sub(r"[_\-/]+", " ", label)
        if UK_EXCL_RE.search(label_norm):
            excluded += 1
            continue

        candidates.append(
            {
                "notation": notation,
                "label": label,
                "lat": lat_f,
                "lon": lon_f,
                "date_opened": op,
                "date_closed": cl,
                "span_days": int(span_days),
                "do_measure": do_id,
                "temp_measure": temp_id,
            }
        )

    # Sort longest span first, deduplicate gauges within 2.0 km so each river reach is independent
    cdf = pd.DataFrame(candidates).sort_values("span_days", ascending=False).reset_index(drop=True)
    kept = []
    for row in cdf.to_dict("records"):
        if any(haversine_km(row["lat"], row["lon"], k["lat"], k["lon"]) < 2.0 for k in kept):
            continue
        kept.append(row)
    kdf = pd.DataFrame(kept).reset_index(drop=True)
    meta = {
        "total_uk_do_stations": len(items),
        "excluded_tidal_dam_stw_multiyear": excluded,
        "dedup_clean_multiyear_candidates": len(kdf),
    }
    return kdf, meta


def fetch_measure_warm_year(measure_id: str, yr: int) -> pd.Series | None:
    url = (
        f"https://environment.data.gov.uk/hydrology/id/measures/{measure_id}/readings.csv"
        f"?mineq-date={yr}-05-01&maxeq-date={yr}-10-31&_limit=50000"
    )
    r = polite_get(url, timeout=(10, 40))
    if r is None or r.status_code != 200 or len(r.text) < 200:
        return None
    df = pd.read_csv(io.StringIO(r.text), usecols=["dateTime", "value", "quality"], low_memory=False)
    if df.empty:
        return None
    # Drop explicitly Suspect/Bad/Missing readings if flagged
    q_up = df["quality"].astype(str).str.upper()
    df = df[~q_up.isin(["SUSPECT", "BAD", "MISSING", "REJECTED"])]
    df["val"] = pd.to_numeric(df["value"], errors="coerce")
    df["dt"] = pd.to_datetime(df["dateTime"], errors="coerce")
    df = df.dropna(subset=["dt", "val"])
    if df.empty:
        return None
    # Round timestamp to nearest 15 minutes so DO and Temp align cleanly
    df["dt15"] = df["dt"].dt.round("15min")
    return df.groupby("dt15")["val"].mean()


def process_uk_station(row: dict) -> dict | None:
    not_id = row["notation"]
    cache_pq = UK_DIR / f"uk_{not_id}.parquet"
    if cache_pq.exists():
        df = pd.read_parquet(cache_pq)
    else:
        y0 = max(2012, int(row["date_opened"][:4]))
        y1 = min(2025, int(row["date_closed"][:4]))
        years = list(range(y1, y0 - 1, -1))[:6]  # up to 6 warm seasons
        parts = []
        for yr in years:
            s_do = fetch_measure_warm_year(row["do_measure"], yr)
            if s_do is None or len(s_do) < 500:
                continue
            s_t = fetch_measure_warm_year(row["temp_measure"], yr)
            if s_t is None or len(s_t) < 500:
                continue
            m = pd.DataFrame({"do": s_do, "temp": s_t}).dropna()
            m = m[m["do"].between(0.0, 25.0) & m["temp"].between(-1.0, 38.0)]
            if len(m) >= 500:
                parts.append(m)
        if not parts:
            return None
        df = pd.concat(parts).sort_index()
        df = df[~df.index.duplicated(keep="first")]
        df.to_parquet(cache_pq)

    if len(df) < 2000:
        return None

    # Compute Local Mean Solar Time (UK EA timestamps are UTC/GMT)
    lon = float(row["lon"])
    dt_idx = pd.to_datetime(df.index)
    utc_hr = dt_idx.hour + dt_idx.minute / 60.0
    solar_hr = (utc_hr + lon / 15.0) % 24.0
    df = df.copy()
    df["day"] = dt_idx.strftime("%Y-%m-%d")
    df["year"] = dt_idx.year
    df["month"] = dt_idx.month
    df["solar_hr_bin"] = np.floor(solar_hr).astype(int) % 24
    df["utc_hr"] = utc_hr

    # Keep only complete days (>= 20 distinct hours of the 24-hour cycle observed, cadence-agnostic for 15/30/60-min loggers!)
    day_hrs = df.groupby("day")["solar_hr_bin"].nunique()
    valid_days = day_hrs[day_hrs >= 20].index
    df = df[df["day"].isin(valid_days)].copy()
    if len(valid_days) < 100:
        return None

    # Daily stats
    daily = df.groupby("day").agg(
        do_min=("do", "min"),
        do_mean=("do", "mean"),
        do_max=("do", "max"),
        temp_mean=("temp", "mean"),
        temp_min=("temp", "min"),
        temp_max=("temp", "max"),
        year=("year", "first"),
        month=("month", "first"),
    )
    # Physical sanity on daily swing
    daily = daily[(daily["do_max"] - daily["do_min"] <= 20.0) & (daily["do_min"] >= 0.0)].copy()
    if len(daily) < 100 or daily["year"].nunique() < 2:
        return None

    daily["do_sat"] = benson_krause_do_sat(daily["temp_mean"].values)
    daily["do_sat_tmin"] = benson_krause_do_sat(daily["temp_min"].values)
    daily["do_sat_tmax"] = benson_krause_do_sat(daily["temp_max"].values)
    daily["swing"] = daily["do_max"] - daily["do_min"]
    daily["plunge"] = daily["do_mean"] - daily["do_min"]
    daily["ym"] = daily["year"].astype(str) + "-" + daily["month"].astype(str).str.zfill(2)

    # Filter out singleton Year-Month cells (< 5 days)
    ym_cnt = daily["ym"].value_counts()
    daily = daily[daily["ym"].isin(ym_cnt[ym_cnt >= 5].index)].copy()
    if len(daily) < 100:
        return None

    # Within-river Year x Month FE demeaning (exact FWL)
    t_dm = daily["temp_mean"] - daily.groupby("ym")["temp_mean"].transform("mean")
    denom = float(np.dot(t_dm.values, t_dm.values))
    if denom < 1e-6:
        return None

    def fe_slope(y_s: pd.Series) -> float:
        y_dm = y_s - y_s.groupby(daily["ym"]).transform("mean")
        return float(np.dot(t_dm.values, y_dm.values) / denom)

    res: dict = {
        "notation": not_id,
        "label": row["label"],
        "lat": float(row["lat"]),
        "lon": lon,
        "n_days": len(daily),
        "n_years": int(daily["year"].nunique()),
        "mean_temp": float(daily["temp_mean"].mean()),
        "mean_do_min": float(daily["do_min"].mean()),
        "mean_do_mean": float(daily["do_mean"].mean()),
        "mean_do_max": float(daily["do_max"].mean()),
        "mean_swing": float(daily["swing"].mean()),
        "s_dosat": fe_slope(daily["do_sat"]),
        "s_dosat_tmin": fe_slope(daily["do_sat_tmin"]),
        "s_dosat_tmax": fe_slope(daily["do_sat_tmax"]),
        "s_domax": fe_slope(daily["do_max"]),
        "s_domean": fe_slope(daily["do_mean"]),
        "s_domin": fe_slope(daily["do_min"]),
        "s_diff_min_max": fe_slope(daily["do_min"] - daily["do_max"]),
        "s_diff_min_mean": fe_slope(daily["do_min"] - daily["do_mean"]),
        "s_diff_min_sat": fe_slope(daily["do_min"] - daily["do_sat"]),
        "s_diff_max_sat": fe_slope(daily["do_max"] - daily["do_sat"]),
        "s_diff_min_sat_exact": fe_slope(daily["do_min"] - daily["do_sat_tmin"]),
        "s_diff_max_sat_exact": fe_slope(daily["do_max"] - daily["do_sat_tmax"]),
        "s_plunge": fe_slope(daily["plunge"]),
    }

    # Hourly 24-hour clock-bias metrics (Local Solar Time, including exact within-river biological excess vs DO_sat!)
    hr_piv = df.pivot_table(index="day", columns="solar_hr_bin", values="do", aggfunc="mean")
    hr_piv = hr_piv.reindex(daily.index)
    for h in range(24):
        if h in hr_piv.columns:
            sub = pd.DataFrame(
                {"y": hr_piv[h], "sat": daily["do_sat"], "t": daily["temp_mean"], "ym": daily["ym"], "dmin": daily["do_min"]}
            ).dropna()
            yc = sub["ym"].value_counts()
            sub = sub[sub["ym"].isin(yc[yc >= 5].index)]
            if len(sub) >= 80:
                td = sub["t"] - sub.groupby("ym")["t"].transform("mean")
                yd = sub["y"] - sub.groupby("ym")["y"].transform("mean")
                ed = (sub["y"] - sub["sat"]) - (sub["y"] - sub["sat"]).groupby(sub["ym"]).transform("mean")
                dn = float(np.dot(td.values, td.values))
                res[f"slope_h{h:02d}"] = float(np.dot(td.values, yd.values) / dn) if dn > 1e-6 else np.nan
                res[f"exc_h{h:02d}"] = float(np.dot(td.values, ed.values) / dn) if dn > 1e-6 else np.nan
                res[f"bias_h{h:02d}"] = float((sub["y"] - sub["dmin"]).mean())
            else:
                res[f"slope_h{h:02d}"] = np.nan
                res[f"exc_h{h:02d}"] = np.nan
                res[f"bias_h{h:02d}"] = np.nan
        else:
            res[f"slope_h{h:02d}"] = np.nan
            res[f"exc_h{h:02d}"] = np.nan
            res[f"bias_h{h:02d}"] = np.nan

    # Multi-year secular slope probe for UK stations with >= 5 warm seasons (>= 60 days/yr)
    ann_uk = daily.groupby("year").agg(
        n=("do_min", "count"),
        temp_mean=("temp_mean", "mean"),
        do_min=("do_min", "mean"),
        do_max=("do_max", "mean"),
        swing=("swing", "mean"),
        diff_min_sat=("do_min", lambda s: float((s - daily.loc[s.index, "do_sat"]).mean())),
    )
    ann_uk = ann_uk[ann_uk["n"] >= 60]
    if len(ann_uk) >= 5 and (ann_uk.index.max() - ann_uk.index.min()) >= 4:
        res["has_uk_5yr"] = 1
        yf = ann_uk.index.values.astype(float)
        for col_u in ("temp_mean", "do_min", "do_max", "swing", "diff_min_sat"):
            res[f"tr_dec_{col_u}"] = float(stats.linregress(yf, ann_uk[col_u].values).slope * 10.0)
    else:
        res["has_uk_5yr"] = 0

    # Specific windows: Landsat 10:00-11:00 solar, Afternoon 13:00-16:00 solar, and UK Civil BST 13:00-16:00 (= 12:00-15:00 UTC)
    ls_s = df[df["solar_hr_bin"] == 10].groupby("day")["do"].mean().reindex(daily.index)
    pm_s = df[df["solar_hr_bin"].isin([13, 14, 15])].groupby("day")["do"].mean().reindex(daily.index)
    bst_hr = (df["utc_hr"] + 1.0) % 24.0
    pm_bst = df[bst_hr.between(13.0, 16.0)].groupby("day")["do"].mean().reindex(daily.index)
    for tag, s_win in [("ls10", ls_s), ("pm14", pm_s), ("pm_bst", pm_bst)]:
        sub = pd.DataFrame({"y": s_win, "t": daily["temp_mean"], "ym": daily["ym"], "dmin": daily["do_min"]}).dropna()
        yc = sub["ym"].value_counts()
        sub = sub[sub["ym"].isin(yc[yc >= 5].index)]
        if len(sub) >= 80:
            td = sub["t"] - sub.groupby("ym")["t"].transform("mean")
            yd = sub["y"] - sub.groupby("ym")["y"].transform("mean")
            dn = float(np.dot(td.values, td.values))
            res[f"slope_{tag}"] = float(np.dot(td.values, yd.values) / dn) if dn > 1e-6 else np.nan
            res[f"bias_{tag}"] = float((sub["y"] - sub["dmin"]).mean())
            for thr, tt in [(5.0, "5"), (3.0, "3"), (2.0, "2")]:
                res[f"hyp{tt}_min_{tag}"] = int((sub["dmin"] < thr).sum())
                res[f"hyp{tt}_miss_{tag}"] = int(((sub["dmin"] < thr) & (sub["y"] >= thr)).sum())
        else:
            res[f"slope_{tag}"] = np.nan
            res[f"bias_{tag}"] = np.nan
            for tt in ("5", "3", "2"):
                res[f"hyp{tt}_min_{tag}"] = 0
                res[f"hyp{tt}_miss_{tag}"] = 0

    return res


def uk_spatial_summary(rdf: pd.DataFrame, vals: pd.Series, rng: np.random.Generator) -> dict:
    """River-level AND spatially clustered (1-deg hydrometric grid + river catchment) CR1 t(G-1) + Wilcoxon + bootstrap inference."""
    sub = pd.DataFrame({"v": pd.to_numeric(vals, errors="coerce"), "grid1deg": rdf["grid1deg"], "river_cl": rdf["river_cl"]}).dropna()
    s = sub["v"]
    n = len(s)
    if n < 3:
        return {"n": n}
    mean_v = float(s.mean())
    se_v = float(s.std(ddof=1) / np.sqrt(n))
    t_val, p_val = stats.ttest_1samp(s, 0.0)
    try:
        _, wp = stats.wilcoxon(s)
    except ValueError:
        wp = np.nan
    tcrit = float(stats.t.ppf(0.975, df=n - 1))

    out: dict = {
        "n": n,
        "mean": round(mean_v, 5),
        "se": round(se_v, 5),
        "ci95_lo": round(mean_v - tcrit * se_v, 5),
        "ci95_hi": round(mean_v + tcrit * se_v, 5),
        "median": round(float(s.median()), 5),
        "pct_neg": round(100.0 * float((s < 0).mean()), 2),
        "pct_pos": round(100.0 * float((s > 0).mean()), 2),
        "t": round(float(t_val), 3),
        "p_t": float(p_val),
        "p_wilcoxon": float(wp) if pd.notna(wp) else None,
    }

    for cl_col, cl_tag in [("grid1deg", "grid1deg_cluster"), ("river_cl", "river_cluster")]:
        groups = [g["v"].values.astype(float) for _, g in sub.groupby(cl_col)]
        g_cnt = len(groups)
        g_means = np.array([g.mean() for g in groups], dtype=float)
        g_sums_dev = np.array([(g - mean_v).sum() for g in groups], dtype=float)
        g_lens = np.array([len(g) for g in groups], dtype=float)
        g_raw_sums = np.array([g.sum() for g in groups], dtype=float)
        se_cr1 = float(np.sqrt((g_cnt / max(1, g_cnt - 1)) * np.sum(g_sums_dev**2)) / n)
        t_cr1 = mean_v / se_cr1 if se_cr1 > 1e-12 else np.nan
        p_cr1 = float(2.0 * stats.t.sf(abs(t_cr1), df=max(1, g_cnt - 1))) if pd.notna(t_cr1) else np.nan
        tcrit_g = float(stats.t.ppf(0.975, df=max(1, g_cnt - 1)))
        try:
            _, wp_gm = stats.wilcoxon(g_means)
        except ValueError:
            wp_gm = np.nan
        idx_b = rng.integers(0, g_cnt, size=(5000, g_cnt))
        b_means = g_raw_sums[idx_b].sum(axis=1) / g_lens[idx_b].sum(axis=1)
        p_boot = max(float(2.0 * min((b_means <= 0.0).mean(), (b_means >= 0.0).mean())), 1.0 / 5001)
        out[cl_tag] = {
            "n_clusters": int(g_cnt),
            "se_cr1": round(se_cr1, 5),
            "ci95_lo": round(mean_v - tcrit_g * se_cr1, 5),
            "ci95_hi": round(mean_v + tcrit_g * se_cr1, 5),
            "t_cr1": round(float(t_cr1), 3) if pd.notna(t_cr1) else None,
            "p_cr1_t_Gminus1": p_cr1 if pd.notna(p_cr1) else None,
            "boot_p": round(p_boot, 6),
            "cluster_equal_mean": round(float(g_means.mean()), 5),
            "cluster_equal_p_wilcoxon": float(wp_gm) if pd.notna(wp_gm) else None,
        }
    return out


def main() -> None:
    rng = np.random.default_rng(20261125)
    print("Step 4: Discovering clean multi-year UK EA continuous river DO + Temp stations...", flush=True)
    kdf, disc_meta = discover_uk_stations()
    print(f"  Discovery: {disc_meta}", flush=True)
    kdf.to_csv(PROC_DIR / "uk_ea_candidate_clean_rivers.csv", index=False)

    # Process ALL clean multi-year UK candidates politely (2 concurrent workers)
    sel = kdf.to_dict("records")
    recs = []
    with ThreadPoolExecutor(max_workers=2) as ex:
        for i, r in enumerate(ex.map(process_uk_station, sel), 1):
            if r is not None:
                recs.append(r)
            if i % 10 == 0 or i == len(sel):
                print(f"  [UK EA {i:2d}/{len(sel)}] valid clean rivers = {len(recs)}", flush=True)

    rdf = pd.DataFrame(recs)
    # Attach 1-deg hydrometric grid cluster & river-name cluster for spatially robust UK inference
    rdf["grid1deg"] = rdf["lat"].round(0).astype(int).astype(str) + "_" + rdf["lon"].round(0).astype(int).astype(str)
    rdf["river_cl"] = (
        rdf["label"].astype(str).str.replace(r"[_\-/]+", " ", regex=True).str.strip().str.split().str[0].str.upper()
    )
    rdf.to_csv(PROC_DIR / "uk_ea_clean_rivers_results.csv", index=False)

    hourly_curve = []
    for h in range(24):
        sh_blk = uk_spatial_summary(rdf, rdf[f"slope_h{h:02d}"], rng)
        ex_blk = uk_spatial_summary(rdf, rdf[f"exc_h{h:02d}"], rng)
        bh = rdf[f"bias_h{h:02d}"].dropna()
        dh = (rdf[f"slope_h{h:02d}"] - rdf["s_domin"]).dropna()
        hourly_curve.append(
            {
                "solar_hour": h,
                "n_rivers": int(sh_blk.get("n", 0)),
                "mean_slope": sh_blk.get("mean"),
                "se_slope": sh_blk.get("se"),
                "se_slope_grid1deg": sh_blk.get("grid1deg_cluster", {}).get("se_cr1"),
                "bio_excess_mean": ex_blk.get("mean"),
                "bio_excess_se_grid1deg": ex_blk.get("grid1deg_cluster", {}).get("se_cr1"),
                "bio_excess_ci95_lo": ex_blk.get("grid1deg_cluster", {}).get("ci95_lo"),
                "bio_excess_ci95_hi": ex_blk.get("grid1deg_cluster", {}).get("ci95_hi"),
                "bio_excess_p_grid1deg": ex_blk.get("grid1deg_cluster", {}).get("p_cr1_t_Gminus1"),
                "mean_slope_bias_vs_min": round(float(dh.mean()), 5) if len(dh) else None,
                "mean_do_bias_mgL": round(float(bh.mean()), 4) if len(bh) else None,
            }
        )

    # Afternoon (Solar & Civil BST) vs Landsat clock bias
    def att_pct(col: str) -> float | None:
        sub_w = rdf.dropna(subset=[col, "s_domin"])
        if not len(sub_w) or abs(float(sub_w["s_domin"].mean())) < 1e-6:
            return None
        return round(100.0 * (1.0 - float(sub_w[col].mean()) / float(sub_w["s_domin"].mean())), 2)

    pm_att = att_pct("slope_pm14")
    pm_bst_att = att_pct("slope_pm_bst")
    ls_att = att_pct("slope_ls10")

    hyp_block = {}
    for tag in ("ls10", "pm14", "pm_bst"):
        hyp_block[tag] = {}
        for tt in ("5", "3", "2"):
            tot = int(rdf[f"hyp{tt}_min_{tag}"].sum())
            miss = int(rdf[f"hyp{tt}_miss_{tag}"].sum())
            hyp_block[tag][f"lt_{tt}_mgL"] = {
                "nocturnal_hypoxia_days": tot,
                "missed_days": miss,
                "missed_pct": round(100.0 * miss / tot, 2) if tot > 0 else None,
            }

    # Multi-year (>= 5 warm seasons) secular probe in UK EA
    sub_5y = rdf[rdf["has_uk_5yr"] == 1].copy()
    uk_secular = {"n_rivers_ge5warm_yrs": len(sub_5y)}
    if len(sub_5y) >= 5:
        for col_u in ("temp_mean", "do_min", "do_max", "swing", "diff_min_sat"):
            uk_secular[f"dec_{col_u}"] = uk_spatial_summary(sub_5y, sub_5y[f"tr_dec_{col_u}"], rng)

    summary = {
        "discovery": disc_meta,
        "n_valid_clean_uk_rivers": len(rdf),
        "n_uk_grid1deg_clusters": int(rdf["grid1deg"].nunique()),
        "n_uk_river_clusters": int(rdf["river_cl"].nunique()),
        "total_uk_warm_river_days": int(rdf["n_days"].sum()) if len(rdf) else 0,
        "thermal_slopes_ym_fe": {
            "DOsat_HenrysLaw": uk_spatial_summary(rdf, rdf["s_dosat"], rng),
            "DOmax_daytime": uk_spatial_summary(rdf, rdf["s_domax"], rng),
            "DOmean_daily": uk_spatial_summary(rdf, rdf["s_domean"], rng),
            "DOmin_nocturnal": uk_spatial_summary(rdf, rdf["s_domin"], rng),
            "DOmin_minus_DOmax": uk_spatial_summary(rdf, rdf["s_diff_min_max"], rng),
            "DOmin_minus_DOmean": uk_spatial_summary(rdf, rdf["s_diff_min_mean"], rng),
            "DOmin_minus_HenrysLaw": uk_spatial_summary(rdf, rdf["s_diff_min_sat"], rng),
            "DOmax_minus_HenrysLaw": uk_spatial_summary(rdf, rdf["s_diff_max_sat"], rng),
            "DOmin_minus_HenrysLaw_exactTmin": uk_spatial_summary(rdf, rdf["s_diff_min_sat_exact"], rng),
            "DOmax_minus_HenrysLaw_exactTmax": uk_spatial_summary(rdf, rdf["s_diff_max_sat_exact"], rng),
            "nocturnal_plunge": uk_spatial_summary(rdf, rdf["s_plunge"], rng),
        },
        "clock_bias_summary": {
            "afternoon_13_16_solar_slope": uk_spatial_summary(rdf, rdf["slope_pm14"], rng),
            "afternoon_minus_DOmin_slope": uk_spatial_summary(rdf, rdf["slope_pm14"] - rdf["s_domin"], rng),
            "afternoon_warming_underestimation_pct": pm_att,
            "afternoon_mean_bias_mgL": uk_spatial_summary(rdf, rdf["bias_pm14"], rng),
            "afternoon_bst_13_16_slope": uk_spatial_summary(rdf, rdf["slope_pm_bst"], rng),
            "afternoon_bst_minus_DOmin_slope": uk_spatial_summary(rdf, rdf["slope_pm_bst"] - rdf["s_domin"], rng),
            "afternoon_bst_warming_underestimation_pct": pm_bst_att,
            "afternoon_bst_mean_bias_mgL": uk_spatial_summary(rdf, rdf["bias_pm_bst"], rng),
            "landsat_10_11_slope": uk_spatial_summary(rdf, rdf["slope_ls10"], rng),
            "landsat_minus_DOmin_slope": uk_spatial_summary(rdf, rdf["slope_ls10"] - rdf["s_domin"], rng),
            "landsat_warming_underestimation_pct": ls_att,
            "landsat_mean_bias_mgL": uk_spatial_summary(rdf, rdf["bias_ls10"], rng),
            "hypoxia_blindness": hyp_block,
        },
        "uk_secular_5yr_probe": uk_secular,
        "hourly_24h_curve_solar_time": hourly_curve,
    }
    out_p = RES_DIR / "uk_ea_replication_results.json"
    out_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== STEP 4 UK EA INTERNATIONAL REPLICATION SUMMARY ===", flush=True)
    print(json.dumps({k: v for k, v in summary.items() if k != "hourly_24h_curve_solar_time"}, indent=2), flush=True)


if __name__ == "__main__":
    main()
