"""Step 3: Full Multi-Year 15-Minute USGS IV 24-Hour Clock-Bias Census (2021-2024 May-Oct) & OOS Transfer Function."""
from __future__ import annotations

import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy import stats

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
DV_DIR = BASE_DIR / "data" / "raw_usgs_dv"
IV_DIR = BASE_DIR / "data" / "raw_usgs_iv"
PROC_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"
UA = {"User-Agent": "AcademicResearch-NocturnalRiverHypoxiaAudit/2.0 (contact: hydrology-audit@research.org)"}

TZ_OFFSET_HOURS: dict[str, float] = {
    "EST": -5.0,
    "EDT": -4.0,
    "CST": -6.0,
    "CDT": -5.0,
    "MST": -7.0,
    "MDT": -6.0,
    "PST": -8.0,
    "PDT": -7.0,
    "AKST": -9.0,
    "AKDT": -8.0,
    "UTC": 0.0,
    "GMT": 0.0,
}

YEARS_IV = [2021, 2022, 2023, 2024]


def fetch_rdb_polite(url: str, timeout: tuple[int, int] = (10, 45)) -> str | None:
    for attempt in range(3):
        try:
            r = requests.get(url, headers=UA, timeout=timeout)
            if r.status_code == 200 and len(r.text) > 150:
                return r.text
            if r.status_code in (400, 404):
                return None
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2.5 * (attempt + 1))
            else:
                return None
        except requests.RequestException:
            time.sleep(2.5 * (attempt + 1))
    return None


def split_multi_site_rdb(text: str) -> dict[str, list[str]]:
    blocks: list[list[str]] = []
    cur: list[str] = []
    for ln in text.splitlines():
        if ln.startswith("#") or not ln.strip():
            continue
        if ln.startswith("agency_cd\tsite_no\t"):
            if cur:
                blocks.append(cur)
            cur = [ln]
        elif cur:
            cur.append(ln)
    if cur:
        blocks.append(cur)
    out: dict[str, list[str]] = {}
    for blk in blocks:
        if len(blk) >= 3:
            parts = blk[2].split("\t")
            if len(parts) >= 2:
                out[parts[1].strip()] = blk
    return out


def parse_iv_season(lines: list[str], lon: float) -> pd.DataFrame | None:
    if len(lines) < 3:
        return None
    hdr = lines[0].split("\t")
    if "datetime" not in hdr:
        return None
    do_cols = [c for c in hdr if c.endswith("_00300") and not c.endswith("_cd")]
    t_cols = [c for c in hdr if c.endswith("_00010") and not c.endswith("_cd")]
    if not do_cols or not t_cols:
        return None

    use_cols = ["datetime"] + (["tz_cd"] if "tz_cd" in hdr else []) + do_cols + t_cols
    raw = "\n".join([lines[0]] + lines[2:])
    df = pd.read_csv(io.StringIO(raw), sep="\t", usecols=use_cols, low_memory=False)
    if df.empty:
        return None

    # Pick longest valid primary sensor for DO and Temp
    def pick_best(cols: list[str], lo: float, hi: float) -> pd.Series:
        best_s = None
        best_n = -1
        for c in cols:
            s = pd.to_numeric(df[c], errors="coerce")
            s = s.where(s.between(lo, hi))
            cnt = int(s.notna().sum())
            if cnt > best_n:
                best_n = cnt
                best_s = s
        return best_s if best_s is not None else pd.Series(np.nan, index=df.index)

    do_s = pick_best(do_cols, 0.0, 25.0)
    t_s = pick_best(t_cols, -2.0, 42.0)

    dt_str = df["datetime"].astype(str)
    day_s = dt_str.str.slice(0, 10)
    hr_int = pd.to_numeric(dt_str.str.slice(11, 13), errors="coerce")
    min_int = pd.to_numeric(dt_str.str.slice(14, 16), errors="coerce")
    civil_hr = hr_int + min_int / 60.0

    if "tz_cd" in df.columns:
        tz_off = df["tz_cd"].astype(str).str.strip().map(TZ_OFFSET_HOURS)
        # Fallback to approximate standard offset from longitude if rare unknown tz_cd
        tz_off = tz_off.fillna(round(lon / 15.0))
    else:
        tz_off = pd.Series(round(lon / 15.0), index=df.index)

    utc_hr = (civil_hr - tz_off) % 24.0
    solar_hr = (utc_hr + lon / 15.0) % 24.0

    out = pd.DataFrame(
        {
            "day": day_s,
            "do": do_s,
            "temp": t_s,
            "civil_hr": civil_hr,
            "solar_hr": solar_hr,
        }
    ).dropna(subset=["day", "do", "temp", "civil_hr", "solar_hr"])
    if len(out) < 500:
        return None

    out["civil_bin"] = np.floor(out["civil_hr"]).astype(int) % 24
    out["solar_bin"] = np.floor(out["solar_hr"]).astype(int) % 24

    # Keep only complete days (>= 20 distinct hours of the 24-hour cycle observed; cadence-agnostic for 15/30/60-min sensors!)
    hr_cnts = out.groupby("day")["solar_bin"].nunique()
    good_days = hr_cnts[hr_cnts >= 20].index
    out = out[out["day"].isin(good_days)].copy()
    if len(good_days) < 25:
        return None

    # Build compact day-level summary table with hourly solar & civil DO + Temp
    daily = out.groupby("day").agg(
        do_min=("do", "min"),
        do_mean=("do", "mean"),
        do_max=("do", "max"),
        temp_mean=("temp", "mean"),
        temp_min=("temp", "min"),
        temp_max=("temp", "max"),
        n_obs=("do", "count"),
    )
    # Exact windows
    daily["do_ls10"] = out[out["solar_hr"].between(10.0, 11.0)].groupby("day")["do"].mean()
    daily["t_ls10"] = out[out["solar_hr"].between(10.0, 11.0)].groupby("day")["temp"].mean()
    daily["do_pm1316"] = out[out["civil_hr"].between(13.0, 16.0)].groupby("day")["do"].mean()
    daily["t_pm1316"] = out[out["civil_hr"].between(13.0, 16.0)].groupby("day")["temp"].mean()
    daily["do_pm1330"] = out[out["civil_hr"].between(13.5, 15.5)].groupby("day")["do"].mean()
    daily["t_pm1330"] = out[out["civil_hr"].between(13.5, 15.5)].groupby("day")["temp"].mean()
    daily["do_am0912"] = out[out["civil_hr"].between(9.0, 12.0)].groupby("day")["do"].mean()
    daily["t_am0912"] = out[out["civil_hr"].between(9.0, 12.0)].groupby("day")["temp"].mean()
    daily["do_dawn0507"] = out[out["solar_hr"].between(5.0, 7.0)].groupby("day")["do"].mean()

    # 24-hour Local Mean Solar Time bins & Local Civil Clock bins
    piv_do_sol = out.pivot_table(index="day", columns="solar_bin", values="do", aggfunc="mean")
    piv_t_sol = out.pivot_table(index="day", columns="solar_bin", values="temp", aggfunc="mean")
    piv_do_civ = out.pivot_table(index="day", columns="civil_bin", values="do", aggfunc="mean")
    piv_t_civ = out.pivot_table(index="day", columns="civil_bin", values="temp", aggfunc="mean")

    extra_cols = {}
    for h in range(24):
        extra_cols[f"do_sol_{h:02d}"] = piv_do_sol[h] if h in piv_do_sol.columns else np.nan
        extra_cols[f"t_sol_{h:02d}"] = piv_t_sol[h] if h in piv_t_sol.columns else np.nan
        extra_cols[f"do_civ_{h:02d}"] = piv_do_civ[h] if h in piv_do_civ.columns else np.nan
        extra_cols[f"t_civ_{h:02d}"] = piv_t_civ[h] if h in piv_t_civ.columns else np.nan
    daily = pd.concat([daily, pd.DataFrame(extra_cols, index=daily.index)], axis=1)
    return daily.reset_index()


def fetch_iv_batch(batch_rows: list[dict]) -> list[dict]:
    """Fetch 2021-2024 warm-season 15-min IV in polite 4-site batches and cache per-river daily-24h parquets."""
    uncached = [
        r
        for r in batch_rows
        if not (IV_DIR / f"{str(r['site_no']).strip()}_iv_daily24h.parquet").exists()
        and not (IV_DIR / f"{str(r['site_no']).strip()}.nodata").exists()
    ]
    if uncached:
        site_ids = [str(r["site_no"]).strip() for r in uncached]
        lon_map = {str(r["site_no"]).strip(): float(r["lon"]) for r in uncached}
        parts_by_site: dict[str, list[pd.DataFrame]] = {s: [] for s in site_ids}

        for yr in YEARS_IV:
            url = (
                f"https://waterservices.usgs.gov/nwis/iv/?format=rdb&sites={','.join(site_ids)}"
                f"&startDT={yr}-05-01&endDT={yr}-10-31&parameterCd=00300,00010"
            )
            txt = fetch_rdb_polite(url, timeout=(15, 90))
            if txt:
                blocks = split_multi_site_rdb(txt)
                for sno, blk in blocks.items():
                    if sno in lon_map:
                        part = parse_iv_season(blk, lon_map[sno])
                        if part is not None and len(part) >= 25:
                            parts_by_site[sno].append(part)
            else:
                # Single-site fallback for this season
                for sno in site_ids:
                    u1 = (
                        f"https://waterservices.usgs.gov/nwis/iv/?format=rdb&sites={sno}"
                        f"&startDT={yr}-05-01&endDT={yr}-10-31&parameterCd=00300,00010"
                    )
                    t1 = fetch_rdb_polite(u1, timeout=(10, 45))
                    if t1:
                        blks = split_multi_site_rdb(t1)
                        if sno in blks:
                            part = parse_iv_season(blks[sno], lon_map[sno])
                            if part is not None and len(part) >= 25:
                                parts_by_site[sno].append(part)

        for sno, parts in parts_by_site.items():
            if not parts:
                (IV_DIR / f"{sno}.nodata").write_text("no_valid_iv_2021_2024", encoding="utf-8")
                continue
            df = pd.concat(parts, ignore_index=True).drop_duplicates(subset=["day"]).sort_values("day").reset_index(drop=True)
            dv_pq = DV_DIR / f"{sno}.parquet"
            if dv_pq.exists():
                dv = pd.read_parquet(dv_pq)[["q_cfs", "spcond", "turb"]].copy()
                dv["day"] = pd.to_datetime(dv.index).strftime("%Y-%m-%d")
                df = df.merge(dv, on="day", how="left")
            else:
                df["q_cfs"] = np.nan
                df["spcond"] = np.nan
                df["turb"] = np.nan
            df.to_parquet(IV_DIR / f"{sno}_iv_daily24h.parquet", index=False)

    valid_metas = []
    for row in batch_rows:
        sno = str(row["site_no"]).strip()
        cache_pq = IV_DIR / f"{sno}_iv_daily24h.parquet"
        if not cache_pq.exists():
            continue
        df = pd.read_parquet(cache_pq)
        if len(df) < 120:
            continue
        valid_metas.append(
            {
                "site_no": sno,
                "state": row["state"],
                "huc2": str(row["huc2"]).zfill(2),
                "station_nm": row["station_nm"],
                "lat": float(row["lat"]),
                "lon": float(row["lon"]),
                "alt_va": float(row["alt_va"]) if pd.notna(row.get("alt_va")) else np.nan,
                "drain_area_va": float(row["drain_area_va"]) if pd.notna(row.get("drain_area_va")) else np.nan,
                "median_spcond": float(row["median_spcond"]) if pd.notna(row.get("median_spcond")) else np.nan,
                "n_iv_days": len(df),
                "n_iv_years": int(df["day"].str.slice(0, 4).nunique()),
                "n_iv_q_days": int(df["q_cfs"].notna().sum()),
            }
        )
    return valid_metas


def select_iv_sites(vdf: pd.DataFrame, target_n: int = 150) -> pd.DataFrame:
    """Deterministically select up to target_n active 2021-2024 clean rivers balanced across all HUC-2 basins & states."""
    elig = vdf[vdf["last_date"] >= "2022-09-01"].copy()
    elig["huc2"] = elig["huc2"].astype(str).str.zfill(2)
    elig = elig.sort_values(["huc2", "state", "hash_key"]).reset_index(drop=True)

    # Round-robin across HUC-2 basins first so every single CONUS watershed is represented
    chosen_ids: list[str] = []
    seen: set[str] = set()
    by_huc = {h: g["site_no"].tolist() for h, g in elig.groupby("huc2")}
    hucs = sorted(by_huc.keys())
    idx_map = {h: 0 for h in hucs}
    while len(chosen_ids) < target_n:
        progressed = False
        for h in hucs:
            if len(chosen_ids) >= target_n:
                break
            lst = by_huc[h]
            while idx_map[h] < len(lst) and lst[idx_map[h]] in seen:
                idx_map[h] += 1
            if idx_map[h] < len(lst):
                sno = lst[idx_map[h]]
                idx_map[h] += 1
                chosen_ids.append(sno)
                seen.add(sno)
                progressed = True
        if not progressed:
            break
    return elig[elig["site_no"].isin(seen)].sort_values(["huc2", "state", "site_no"]).reset_index(drop=True)


def fwl_slope(df: pd.DataFrame, y_col: str, t_col: str, use_q: bool = False) -> float:
    cols = [y_col, t_col, "ym"] + (["q_cfs"] if use_q else [])
    sub = df[cols].dropna().copy()
    if use_q:
        sub = sub[sub["q_cfs"] > 0.0]
    yc = sub["ym"].value_counts()
    sub = sub[sub["ym"].isin(yc[yc >= 5].index)]
    if len(sub) < 60:
        return np.nan
    y = sub[y_col] - sub.groupby("ym")[y_col].transform("mean")
    t = sub[t_col] - sub.groupby("ym")[t_col].transform("mean")
    if use_q:
        lq = np.log(sub["q_cfs"].values)
        sub["lq"] = lq
        sub["lq2"] = lq**2
        q1 = sub["lq"] - sub.groupby("ym")["lq"].transform("mean")
        q2 = sub["lq2"] - sub.groupby("ym")["lq2"].transform("mean")
        x = np.column_stack([t.values, q1.values, q2.values])
        if np.linalg.matrix_rank(x) < 3:
            return np.nan
        beta, *_ = np.linalg.lstsq(x, y.values, rcond=None)
        return float(beta[0])
    denom = float(np.dot(t.values, t.values))
    if denom < 1e-6:
        return np.nan
    return float(np.dot(t.values, y.values) / denom)


def cluster_t_block(df: pd.DataFrame, col: str, cluster_col: str) -> dict:
    sub = df[[col, cluster_col]].dropna()
    if len(sub) < 5:
        return {"n_rivers": len(sub)}
    # Cluster means (conservative finite-sample t(G-1) on cluster averages + equal-river OLS clustered SE!)
    g_means = sub.groupby(cluster_col)[col].mean()
    g = len(g_means)
    y = sub[col].values
    mu = float(y.mean())
    # Exact CR1 cluster-robust SE for the river-level sample mean (equal weight per river)
    n = len(y)
    cl_sums = sub.groupby(cluster_col)[col].apply(lambda s: float((s - mu).sum())).values
    # CR1 finite-sample adjustment G/(G-1) * (n-1)/(n-1)
    se_cr1 = float(np.sqrt((g / max(1, g - 1)) * np.sum(cl_sums**2)) / n)
    t_cr1 = mu / se_cr1 if se_cr1 > 1e-12 else np.nan
    p_cr1 = float(2.0 * stats.t.sf(abs(t_cr1), df=max(1, g - 1))) if pd.notna(t_cr1) else np.nan
    tcrit = float(stats.t.ppf(0.975, df=max(1, g - 1)))

    # Cluster-mean equal-cluster t-test & Wilcoxon
    _, p_gm = stats.ttest_1samp(g_means.values, 0.0) if g >= 3 else (np.nan, np.nan)
    try:
        _, wp_gm = stats.wilcoxon(g_means.values)
    except ValueError:
        wp_gm = np.nan

    return {
        "n_rivers": int(n),
        "n_clusters": g,
        "mean": round(mu, 5),
        "se_cr1": round(se_cr1, 5),
        "ci95_lo": round(mu - tcrit * se_cr1, 5),
        "ci95_hi": round(mu + tcrit * se_cr1, 5),
        "t_cr1": round(float(t_cr1), 3) if pd.notna(t_cr1) else None,
        "p_cr1_t_Gminus1": p_cr1 if pd.notna(p_cr1) else None,
        "cluster_equal_mean": round(float(g_means.mean()), 5),
        "cluster_equal_p_t": float(p_gm) if pd.notna(p_gm) else None,
        "cluster_equal_p_wilcoxon": float(wp_gm) if pd.notna(wp_gm) else None,
    }


def benson_krause_do_sat_alt(temp_c: np.ndarray, alt_m: np.ndarray | float) -> np.ndarray:
    """USGS TWRI Book 9 exact barometric-pressure & water-vapor adjusted Benson-Krause DO saturation (mg/L)."""
    t_k = np.asarray(temp_c, dtype=float) + 273.15
    c_1atm = np.exp(
        -139.34411
        + 1.575701e5 / t_k
        - 6.642308e7 / (t_k**2)
        + 1.243800e10 / (t_k**3)
        - 8.621949e11 / (t_k**4)
    )
    z = np.clip(np.where(np.isfinite(alt_m), np.asarray(alt_m, dtype=float), 0.0), 0.0, 4500.0)
    p_atm = np.power(1.0 - 2.25577e-5 * z, 5.25588)
    p_wv = np.exp(11.8571 - 3840.70 / t_k - 216961.0 / (t_k**2))
    f_p = np.where(z > 0.0, (p_atm - p_wv) / (1.0 - p_wv), 1.0)
    return c_1atm * f_p


def _build_spline_matrix(sub: pd.DataFrame) -> np.ndarray:
    """Nonlinear piecewise-hinge spline + interaction transfer benchmark (strictly observable features)."""
    de = sub["do_excess"].values
    tc = sub["t_c20"].values
    sp = sub["supersat_pos"].values
    sd = sub["sin_doy"].values
    cd = sub["cos_doy"].values
    lat = sub["lat"].values - 38.0
    lon = sub["lon"].values + 90.0
    alt = sub["alt_m"].values / 1000.0
    cols = [
        np.ones(len(sub)),
        de,
        np.maximum(0.0, de + 2.0),
        np.maximum(0.0, de + 1.0),
        sp,
        np.maximum(0.0, de - 1.0),
        np.maximum(0.0, de - 2.0),
        tc,
        np.maximum(0.0, tc + 5.0),
        np.maximum(0.0, tc),
        np.maximum(0.0, tc - 5.0),
        de * tc,
        sp * tc,
        sp * sd,
        sp * cd,
        sp * lat,
        tc * lat,
        sd,
        cd,
        lat,
        lon,
        alt,
    ]
    return np.column_stack(cols)


def evaluate_transfer_function(iv_meta: pd.DataFrame) -> dict:
    """Out-of-sample Leave-One-HUC2-Basin-Out & Temporal-2024 Holdout transfer function for correcting daytime/Landsat bias."""
    rows = []
    for rec in iv_meta.to_dict("records"):
        sno = str(rec["site_no"]).strip()
        pq = IV_DIR / f"{sno}_iv_daily24h.parquet"
        if not pq.exists():
            continue
        df = pd.read_parquet(pq)
        dt = pd.to_datetime(df["day"])
        df["year"] = dt.dt.year
        df["doy"] = dt.dt.day_of_year
        alt_va = float(rec["alt_va"]) if pd.notna(rec["alt_va"]) else np.nan
        alt_m = max(0.0, alt_va * 0.3048) if np.isfinite(alt_va) else 0.0
        # Stack Landsat-10:30 solar, Afternoon-13:00-16:00 wide, and Afternoon-13:30-15:30 core civil windows
        for mode, do_c, t_c, hr_val in [
            ("landsat_1030", "do_ls10", "t_ls10", 10.5),
            ("afternoon_1316", "do_pm1316", "t_pm1316", 14.5),
            ("afternoon_1430", "do_pm1330", "t_pm1330", 14.5),
        ]:
            sub = df[["day", "year", "doy", "do_min", "temp_mean", do_c, t_c, "q_cfs"]].dropna(
                subset=["do_min", "temp_mean", do_c, t_c]
            )
            if len(sub) < 40:
                continue
            tmp = pd.DataFrame(
                {
                    "site_no": sno,
                    "state": rec["state"],
                    "huc2": str(rec["huc2"]).zfill(2),
                    "mode": mode,
                    "day": sub["day"].values,
                    "year": sub["year"].values,
                    "doy": sub["doy"].values,
                    "hr": hr_val,
                    "do_obs": sub[do_c].values,
                    "t_obs": sub[t_c].values,
                    "t_mean": sub["temp_mean"].values,
                    "do_min": sub["do_min"].values,
                    "lat": float(rec["lat"]),
                    "lon": float(rec["lon"]),
                    "alt_m": alt_m,
                }
            )
            rows.append(tmp)

    if not rows:
        return {}
    panel = pd.concat(rows, ignore_index=True)
    # Exact altitude- & water-vapor-adjusted Benson-Krause saturation at observed T(h) (identical to Step 5!)
    panel["do_sat_alt_obs"] = benson_krause_do_sat_alt(panel["t_obs"].values, panel["alt_m"].values)
    # Orthogonalized, 20 C-centered physical features (eliminates collinearity between do_sat_obs and t_obs/t_obs^2/alt_m!)
    panel["do_excess"] = panel["do_obs"] - panel["do_sat_alt_obs"]
    panel["supersat_pos"] = np.maximum(0.0, panel["do_excess"])
    panel["t_c20"] = panel["t_obs"] - 20.0
    panel["t_c20_sq"] = panel["t_c20"] ** 2
    panel["supersat_x_tc20"] = panel["supersat_pos"] * panel["t_c20"]
    panel["sin_doy"] = np.sin(2.0 * np.pi * panel["doy"] / 365.25)
    panel["cos_doy"] = np.cos(2.0 * np.pi * panel["doy"] / 365.25)

    feat_cols_full = [
        "do_excess",
        "supersat_pos",
        "t_c20",
        "t_c20_sq",
        "supersat_x_tc20",
        "sin_doy",
        "cos_doy",
        "lat",
        "lon",
        "alt_m",
    ]

    out_eval: dict = {}
    for mode in ("afternoon_1316", "afternoon_1430", "landsat_1030"):
        sub = panel[panel["mode"] == mode].copy().reset_index(drop=True)
        # Predict nocturnal drawdown Delta_noc = DO_obs - DO_min >= 0 using ONLY observable grab/satellite features!
        sub["drawdown"] = sub["do_obs"] - sub["do_min"]

        # 1. Strict Leave-One-HUC2-Basin-Out Spatial Cross-Validation (Parsimonious Hinge + Nonlinear Spline Benchmark)
        oof_pred_min = np.full(len(sub), np.nan)
        oof_pred_min_nl = np.full(len(sub), np.nan)
        X_nl_all = _build_spline_matrix(sub)
        for huc in sorted(sub["huc2"].unique()):
            tr = sub["huc2"] != huc
            te = sub["huc2"] == huc
            if tr.sum() < 200 or te.sum() == 0:
                continue
            X_tr = np.column_stack([np.ones(tr.sum()), sub.loc[tr, feat_cols_full].values])
            y_tr = sub.loc[tr, "drawdown"].values
            beta, *_ = np.linalg.lstsq(X_tr, y_tr, rcond=None)
            X_te = np.column_stack([np.ones(te.sum()), sub.loc[te, feat_cols_full].values])
            pred_dd = np.maximum(0.0, X_te @ beta)
            oof_pred_min[te] = np.clip(sub.loc[te, "do_obs"].values - pred_dd, 0.0, 25.0)

            # Nonlinear piecewise-spline + interaction benchmark on identical LOHUC2 fold
            b_nl, *_ = np.linalg.lstsq(X_nl_all[tr], y_tr, rcond=None)
            pred_dd_nl = np.maximum(0.0, X_nl_all[te] @ b_nl)
            oof_pred_min_nl[te] = np.clip(sub.loc[te, "do_obs"].values - pred_dd_nl, 0.0, 25.0)

        valid = ~np.isnan(oof_pred_min)
        sub_v = sub[valid].copy()
        sub_v["pred_do_min_lohuc2"] = oof_pred_min[valid]
        sub_v["pred_do_min_nl"] = oof_pred_min_nl[valid]

        # Fit full coefficients & verify full rank AND low multicollinearity (VIF < 10)
        X_all = np.column_stack([np.ones(len(sub)), sub[feat_cols_full].values])
        if np.linalg.matrix_rank(X_all) != X_all.shape[1]:
            msg = f"Transfer function design matrix rank-deficient for {mode}"
            raise ValueError(msg)
        X_std = (X_all[:, 1:] - X_all[:, 1:].mean(axis=0)) / X_all[:, 1:].std(axis=0)
        cond_std = float(np.linalg.cond(X_std))
        vifs = np.diag(np.linalg.inv(np.corrcoef(X_std, rowvar=False)))
        max_vif = float(np.max(vifs))
        if max_vif >= 10.0:
            msg = f"Transfer function multicollinearity VIF={max_vif:.2f} >= 10 for {mode}"
            raise ValueError(msg)

        beta_all, *_ = np.linalg.lstsq(X_all, sub["drawdown"].values, rcond=None)
        coef_dict = {"intercept": round(float(beta_all[0]), 6)}
        for k, b in zip(feat_cols_full, beta_all[1:]):
            coef_dict[k] = round(float(b), 6)
        # Exact total marginal drawdown per +1 mg/L daytime supersaturation at T = 20 C (do_excess + supersat_pos)
        supersat_total_20c = float(coef_dict["do_excess"] + coef_dict["supersat_pos"])

        # Evaluate raw vs LOHUC2-corrected metrics
        raw_err = sub_v["do_obs"] - sub_v["do_min"]
        cor_err = sub_v["pred_do_min_lohuc2"] - sub_v["do_min"]
        nl_err = sub_v["pred_do_min_nl"] - sub_v["do_min"]
        pred_dd_v = sub_v["do_obs"] - sub_v["pred_do_min_lohuc2"]

        # Evaluate within-river warming slope recovery before vs after OOS LOHUC2 transfer correction!
        sub_v["ym"] = sub_v["year"].astype(str) + "-" + pd.to_datetime(sub_v["day"]).dt.month.astype(str).str.zfill(2)
        river_slopes = []
        for sno, g in sub_v.groupby("site_no"):
            s_true = fwl_slope(g, "do_min", "t_mean", use_q=False)
            s_raw = fwl_slope(g, "do_obs", "t_mean", use_q=False)
            s_cor = fwl_slope(g, "pred_do_min_lohuc2", "t_mean", use_q=False)
            s_nl = fwl_slope(g, "pred_do_min_nl", "t_mean", use_q=False)
            if pd.notna(s_true) and pd.notna(s_raw) and pd.notna(s_cor) and pd.notna(s_nl):
                river_slopes.append({"site_no": sno, "s_true": s_true, "s_raw": s_raw, "s_cor": s_cor, "s_nl": s_nl})
        rs_df = pd.DataFrame(river_slopes)

        # Hypoxia detection recall & precision at < 5.0, < 4.0, and < 3.0 mg/L
        hyp_metrics = {}
        for thr, tag in [(5.0, "lt_5_mgL"), (4.0, "lt_4_mgL"), (3.0, "lt_3_mgL")]:
            y_true = sub_v["do_min"] < thr
            y_raw = sub_v["do_obs"] < thr
            y_cor = sub_v["pred_do_min_lohuc2"] < thr
            n_pos = int(y_true.sum())
            hyp_metrics[tag] = {
                "n_true_hypoxia_days": n_pos,
                "raw_recall_pct": round(100.0 * float((y_true & y_raw).sum()) / max(1, n_pos), 2),
                "raw_missed_pct": round(100.0 * float((y_true & ~y_raw).sum()) / max(1, n_pos), 2),
                "corrected_recall_pct": round(100.0 * float((y_true & y_cor).sum()) / max(1, n_pos), 2),
                "corrected_missed_pct": round(100.0 * float((y_true & ~y_cor).sum()) / max(1, n_pos), 2),
                "corrected_precision_pct": round(100.0 * float((y_true & y_cor).sum()) / max(1, int(y_cor.sum())), 2),
                "corrected_specificity_pct": round(100.0 * float((~y_true & ~y_cor).sum()) / max(1, int((~y_true).sum())), 2),
            }

        # Temporal holdout: train 2021-2023 -> test 2024
        tr_t = sub["year"] <= 2023
        te_t = sub["year"] == 2024
        temp_holdout = {}
        if tr_t.sum() >= 500 and te_t.sum() >= 200:
            Xt_tr = np.column_stack([np.ones(tr_t.sum()), sub.loc[tr_t, feat_cols_full].values])
            bt, *_ = np.linalg.lstsq(Xt_tr, sub.loc[tr_t, "drawdown"].values, rcond=None)
            Xt_te = np.column_stack([np.ones(te_t.sum()), sub.loc[te_t, feat_cols_full].values])
            p_2024 = np.clip(sub.loc[te_t, "do_obs"].values - np.maximum(0.0, Xt_te @ bt), 0.0, 25.0)
            b_nl_t, *_ = np.linalg.lstsq(X_nl_all[tr_t], sub.loc[tr_t, "drawdown"].values, rcond=None)
            p_2024_nl = np.clip(sub.loc[te_t, "do_obs"].values - np.maximum(0.0, X_nl_all[te_t] @ b_nl_t), 0.0, 25.0)
            e_raw24 = sub.loc[te_t, "do_obs"].values - sub.loc[te_t, "do_min"].values
            e_cor24 = p_2024 - sub.loc[te_t, "do_min"].values
            e_nl24 = p_2024_nl - sub.loc[te_t, "do_min"].values
            temp_holdout = {
                "n_train_2021_2023": int(tr_t.sum()),
                "n_test_2024": int(te_t.sum()),
                "raw_rmse_2024": round(float(np.sqrt(np.mean(e_raw24**2))), 4),
                "corrected_rmse_2024": round(float(np.sqrt(np.mean(e_cor24**2))), 4),
                "nonlinear_spline_rmse_2024": round(float(np.sqrt(np.mean(e_nl24**2))), 4),
                "raw_mean_bias_2024": round(float(np.mean(e_raw24)), 4),
                "corrected_mean_bias_2024": round(float(np.mean(e_cor24)), 4),
            }

        raw_slope_bias = float((rs_df["s_raw"] - rs_df["s_true"]).mean()) if len(rs_df) else np.nan
        cor_slope_bias = float((rs_df["s_cor"] - rs_df["s_true"]).mean()) if len(rs_df) else np.nan
        nl_slope_bias = float((rs_df["s_nl"] - rs_df["s_true"]).mean()) if len(rs_df) else np.nan
        slope_bias_red = (
            round(100.0 * (1.0 - abs(cor_slope_bias) / abs(raw_slope_bias)), 2)
            if pd.notna(raw_slope_bias) and abs(raw_slope_bias) > 1e-6
            else None
        )
        nl_slope_bias_red = (
            round(100.0 * (1.0 - abs(nl_slope_bias) / abs(raw_slope_bias)), 2)
            if pd.notna(raw_slope_bias) and abs(raw_slope_bias) > 1e-6
            else None
        )

        out_eval[mode] = {
            "n_river_days": len(sub_v),
            "n_rivers": int(sub_v["site_no"].nunique()),
            "n_huc2_folds": int(sub_v["huc2"].nunique()),
            "max_vif": round(max_vif, 3),
            "condition_number_std": round(cond_std, 3),
            "supersat_marginal_drawdown_at_20C": round(supersat_total_20c, 4),
            "raw_mean_bias_mgL": round(float(raw_err.mean()), 4),
            "corrected_mean_bias_lohuc2_mgL": round(float(cor_err.mean()), 4),
            "mean_bias_reduction_pct": round(100.0 * (1.0 - abs(float(cor_err.mean())) / max(1e-6, abs(float(raw_err.mean())))), 2),
            "raw_rmse_mgL": round(float(np.sqrt(np.mean(raw_err**2))), 4),
            "corrected_rmse_lohuc2_mgL": round(float(np.sqrt(np.mean(cor_err**2))), 4),
            "rmse_reduction_pct": round(100.0 * (1.0 - float(np.sqrt(np.mean(cor_err**2))) / float(np.sqrt(np.mean(raw_err**2)))), 2),
            "raw_mae_mgL": round(float(np.mean(np.abs(raw_err))), 4),
            "corrected_mae_lohuc2_mgL": round(float(np.mean(np.abs(cor_err))), 4),
            "oos_r2_do_min": round(
                float(1.0 - np.sum((sub_v["do_min"] - sub_v["pred_do_min_lohuc2"]) ** 2) / np.sum((sub_v["do_min"] - sub_v["do_min"].mean()) ** 2)),
                4,
            ),
            "oos_r2_drawdown": round(
                float(1.0 - np.sum((sub_v["drawdown"] - pred_dd_v) ** 2) / np.sum((sub_v["drawdown"] - sub_v["drawdown"].mean()) ** 2)),
                4,
            ),
            "nonlinear_spline_benchmark": {
                "n_features": int(X_nl_all.shape[1] - 1),
                "lohuc2_mean_bias_mgL": round(float(nl_err.mean()), 4),
                "lohuc2_rmse_mgL": round(float(np.sqrt(np.mean(nl_err**2))), 4),
                "rmse_reduction_pct": round(100.0 * (1.0 - float(np.sqrt(np.mean(nl_err**2))) / float(np.sqrt(np.mean(raw_err**2)))), 2),
                "oos_r2_do_min": round(
                    float(1.0 - np.sum((sub_v["do_min"] - sub_v["pred_do_min_nl"]) ** 2) / np.sum((sub_v["do_min"] - sub_v["do_min"].mean()) ** 2)),
                    4,
                ),
                "slope_bias_reduction_pct": nl_slope_bias_red,
            },
            "warming_slope_recovery": {
                "n_rivers": len(rs_df),
                "true_DOmin_slope": round(float(rs_df["s_true"].mean()), 5) if len(rs_df) else None,
                "raw_obs_slope": round(float(rs_df["s_raw"].mean()), 5) if len(rs_df) else None,
                "lohuc2_corrected_slope": round(float(rs_df["s_cor"].mean()), 5) if len(rs_df) else None,
                "raw_slope_bias": round(raw_slope_bias, 5) if pd.notna(raw_slope_bias) else None,
                "corrected_slope_bias": round(cor_slope_bias, 5) if pd.notna(cor_slope_bias) else None,
                "slope_bias_reduction_pct": slope_bias_red,
            },
            "hypoxia_detection_lohuc2": hyp_metrics,
            "temporal_2024_holdout": temp_holdout,
            "full_fit_coefficients": coef_dict,
        }
    return out_eval


def main() -> None:
    vdf = pd.read_csv(PROC_DIR / "conus_valid_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
    sel = select_iv_sites(vdf, target_n=140)
    print(
        f"Step 3: Fetching 2021-2024 (May-Oct) 15-min IV DO & Temp for {len(sel)} clean CONUS rivers "
        f"across {sel['state'].nunique()} states & {sel['huc2'].nunique()} HUC-2 basins (3 workers)...",
        flush=True,
    )

    iv_meta_rows = []
    t0 = time.monotonic()
    recs_sel = sel.to_dict("records")
    iv_batches = [recs_sel[i : i + 4] for i in range(0, len(recs_sel), 4)]
    with ThreadPoolExecutor(max_workers=3) as ex:
        for i, res_list in enumerate(ex.map(fetch_iv_batch, iv_batches), 1):
            iv_meta_rows.extend(res_list)
            if i % 5 == 0 or i == len(iv_batches):
                print(
                    f"  [IV batch {i:2d}/{len(iv_batches)}] valid={len(iv_meta_rows)} elapsed={time.monotonic()-t0:.1f}s",
                    flush=True,
                )

    iv_meta = pd.DataFrame(iv_meta_rows).sort_values(["huc2", "state", "site_no"]).reset_index(drop=True)
    iv_meta.to_csv(PROC_DIR / "conus_iv_rivers_meta.csv", index=False)

    # Compute river-level 24-hour clock-bias metrics (both Solar Time & Civil Clock Time, with & without Q control!)
    print("Computing river-level 24-hour clock-bias slopes & hypoxia-blindness profiles...", flush=True)
    river_clock_rows = []
    # Also accumulate day-weighted pooled hypoxia counts per solar & civil hour
    sol_hyp_tot = {thr: np.zeros(24, dtype=int) for thr in ("5", "4", "3", "2")}
    sol_hyp_miss = {thr: np.zeros(24, dtype=int) for thr in ("5", "4", "3", "2")}
    civ_hyp_tot = {thr: np.zeros(24, dtype=int) for thr in ("5", "4", "3", "2")}
    civ_hyp_miss = {thr: np.zeros(24, dtype=int) for thr in ("5", "4", "3", "2")}
    win_hyp_tot = {w: {thr: 0 for thr in ("5", "4", "3", "2")} for w in ("ls10", "pm1316", "pm1330", "am0912", "dawn0507")}
    win_hyp_miss = {w: {thr: 0 for thr in ("5", "4", "3", "2")} for w in ("ls10", "pm1316", "pm1330", "am0912", "dawn0507")}

    for rec in iv_meta.to_dict("records"):
        sno = str(rec["site_no"]).strip()
        df = pd.read_parquet(IV_DIR / f"{sno}_iv_daily24h.parquet")
        df["ym"] = df["day"].str.slice(0, 7)
        alt_va = float(rec["alt_va"]) if pd.notna(rec.get("alt_va")) else np.nan
        alt_m = max(0.0, alt_va * 0.3048) if np.isfinite(alt_va) else 0.0
        df["do_sat_alt"] = benson_krause_do_sat_alt(df["temp_mean"].values, alt_m)

        r_out = dict(rec)
        use_q = int(df["q_cfs"].notna().sum() >= 100)
        r_out["has_q_iv"] = use_q
        r_out["s_dosat_alt"] = fwl_slope(df, "do_sat_alt", "temp_mean", use_q=False)

        # Core daily benchmark slopes (both YM-FE and YM-FE + Q)
        for col, k in [("do_min", "s_domin"), ("do_mean", "s_domean"), ("do_max", "s_domax")]:
            r_out[k] = fwl_slope(df, col, "temp_mean", use_q=False)
            r_out[f"{k}_q"] = fwl_slope(df, col, "temp_mean", use_q=True) if use_q else np.nan

        # Named windows: Landsat 10:00-11:00 solar, Afternoon 13:00-16:00 civil, Afternoon 13:30-15:30 civil, Morning 09:00-12:00 civil
        for w, do_c, t_c in [
            ("ls10", "do_ls10", "t_ls10"),
            ("pm1316", "do_pm1316", "t_pm1316"),
            ("pm1330", "do_pm1330", "t_pm1330"),
            ("am0912", "do_am0912", "t_am0912"),
            ("dawn0507", "do_dawn0507", "temp_mean"),
        ]:
            r_out[f"s_{w}"] = fwl_slope(df, do_c, "temp_mean", use_q=False)
            r_out[f"s_{w}_q"] = fwl_slope(df, do_c, "temp_mean", use_q=True) if use_q else np.nan
            r_out[f"s_{w}_instT"] = fwl_slope(df, do_c, t_c, use_q=False) if t_c != "temp_mean" else r_out[f"s_{w}"]
            sub_w = df[["do_min", do_c]].dropna()
            r_out[f"bias_{w}"] = float((sub_w[do_c] - sub_w["do_min"]).mean()) if len(sub_w) >= 30 else np.nan
            for thr_v, tt in [(5.0, "5"), (4.0, "4"), (3.0, "3"), (2.0, "2")]:
                tot = int((sub_w["do_min"] < thr_v).sum())
                miss = int(((sub_w["do_min"] < thr_v) & (sub_w[do_c] >= thr_v)).sum())
                win_hyp_tot[w][tt] += tot
                win_hyp_miss[w][tt] += miss

        # 24-hour Local Solar Time and Civil Clock Time curves (including exact within-river biological excess vs DO_sat_alt!)
        for h in range(24):
            c_sol, tc_sol = f"do_sol_{h:02d}", f"t_sol_{h:02d}"
            c_civ, tc_civ = f"do_civ_{h:02d}", f"t_civ_{h:02d}"
            r_out[f"s_sol_{h:02d}"] = fwl_slope(df, c_sol, "temp_mean", use_q=False)
            r_out[f"s_sol_instT_{h:02d}"] = fwl_slope(df, c_sol, tc_sol, use_q=False)
            r_out[f"s_civ_{h:02d}"] = fwl_slope(df, c_civ, "temp_mean", use_q=False)
            r_out[f"s_civ_instT_{h:02d}"] = fwl_slope(df, c_civ, tc_civ, use_q=False)
            df["_tmp_exc_sol"] = df[c_sol] - df["do_sat_alt"]
            df["_tmp_exc_civ"] = df[c_civ] - df["do_sat_alt"]
            r_out[f"s_sol_exc_{h:02d}"] = fwl_slope(df, "_tmp_exc_sol", "temp_mean", use_q=False)
            r_out[f"s_civ_exc_{h:02d}"] = fwl_slope(df, "_tmp_exc_civ", "temp_mean", use_q=False)
            if use_q:
                r_out[f"s_sol_q_{h:02d}"] = fwl_slope(df, c_sol, "temp_mean", use_q=True)
                r_out[f"s_civ_q_{h:02d}"] = fwl_slope(df, c_civ, "temp_mean", use_q=True)
            else:
                r_out[f"s_sol_q_{h:02d}"] = np.nan
                r_out[f"s_civ_q_{h:02d}"] = np.nan

            sub_s = df[["do_min", c_sol]].dropna()
            sub_c = df[["do_min", c_civ]].dropna()
            r_out[f"bias_sol_{h:02d}"] = float((sub_s[c_sol] - sub_s["do_min"]).mean()) if len(sub_s) >= 30 else np.nan
            r_out[f"bias_civ_{h:02d}"] = float((sub_c[c_civ] - sub_c["do_min"]).mean()) if len(sub_c) >= 30 else np.nan

            for thr_v, tt in [(5.0, "5"), (4.0, "4"), (3.0, "3"), (2.0, "2")]:
                sol_hyp_tot[tt][h] += int((sub_s["do_min"] < thr_v).sum())
                sol_hyp_miss[tt][h] += int(((sub_s["do_min"] < thr_v) & (sub_s[c_sol] >= thr_v)).sum())
                civ_hyp_tot[tt][h] += int((sub_c["do_min"] < thr_v).sum())
                civ_hyp_miss[tt][h] += int(((sub_c["do_min"] < thr_v) & (sub_c[c_civ] >= thr_v)).sum())

        river_clock_rows.append(r_out)

    rc_df = pd.DataFrame(river_clock_rows)
    rc_df.to_csv(PROC_DIR / "conus_iv_24h_river_slopes.csv", index=False)

    # Assemble 24-hour curves (Solar & Civil)
    def build_curve(prefix: str, hyp_tot: dict, hyp_miss: dict) -> list[dict]:
        curve = []
        for h in range(24):
            sc = f"s_{prefix}_{h:02d}"
            sc_i = f"s_{prefix}_instT_{h:02d}"
            sc_q = f"s_{prefix}_q_{h:02d}"
            sc_e = f"s_{prefix}_exc_{h:02d}"
            bc = f"bias_{prefix}_{h:02d}"
            sub = rc_df[[sc, "s_domin", "state", "huc2"]].dropna().copy()
            sub["diff"] = sub[sc] - sub["s_domin"]
            sub_q = rc_df[[sc_q, "s_domin_q", "huc2"]].dropna().copy()
            sub_q["diff_q"] = sub_q[sc_q] - sub_q["s_domin_q"]
            sub_i = rc_df[[sc_i, "s_domin", "huc2"]].dropna().copy()
            sub_i["diff_i"] = sub_i[sc_i] - sub_i["s_domin"]
            s_min_mu = float(sub["s_domin"].mean()) if len(sub) else np.nan
            s_h_mu = float(sub[sc].mean()) if len(sub) else np.nan
            att_pct = round(100.0 * (1.0 - s_h_mu / s_min_mu), 2) if pd.notna(s_min_mu) and abs(s_min_mu) > 1e-6 else None
            s_h_i_mu = float(sub_i[sc_i].mean()) if len(sub_i) else np.nan
            att_i_pct = round(100.0 * (1.0 - s_h_i_mu / float(sub_i["s_domin"].mean())), 2) if len(sub_i) else None

            h_blk = cluster_t_block(sub, sc, "huc2")
            d_blk = cluster_t_block(sub, "diff", "huc2")
            e_blk = cluster_t_block(rc_df[[sc_e, "huc2"]].dropna(), sc_e, "huc2")
            b_blk = cluster_t_block(rc_df[[bc, "huc2"]].dropna(), bc, "huc2")

            row_c = {
                "hour": h,
                "n_rivers": len(sub),
                "slope_mean": h_blk.get("mean"),
                "slope_se_huc2": h_blk.get("se_cr1"),
                "slope_ci95_lo": h_blk.get("ci95_lo"),
                "slope_ci95_hi": h_blk.get("ci95_hi"),
                "slope_instT_mean": round(s_h_i_mu, 5) if pd.notna(s_h_i_mu) else None,
                "slope_qctrl_mean": round(float(sub_q[sc_q].mean()), 5) if len(sub_q) else None,
                "bio_excess_mean": e_blk.get("mean"),
                "bio_excess_se_huc2": e_blk.get("se_cr1"),
                "bio_excess_ci95_lo": e_blk.get("ci95_lo"),
                "bio_excess_ci95_hi": e_blk.get("ci95_hi"),
                "bio_excess_p_huc2": e_blk.get("p_cr1_t_Gminus1"),
                "slope_bias_vs_DOmin": d_blk.get("mean"),
                "slope_bias_se_huc2": d_blk.get("se_cr1"),
                "slope_bias_p_huc2": d_blk.get("p_cr1_t_Gminus1"),
                "warming_underestimation_pct": att_pct,
                "warming_underestimation_instT_pct": att_i_pct,
                "do_bias_mgL": b_blk.get("mean"),
                "do_bias_se_huc2": b_blk.get("se_cr1"),
            }
            for tt in ("5", "4", "3", "2"):
                tot = int(hyp_tot[tt][h])
                miss = int(hyp_miss[tt][h])
                row_c[f"hyp{tt}_missed_pct"] = round(100.0 * miss / tot, 2) if tot > 0 else None
                row_c[f"hyp{tt}_min_days"] = tot
            curve.append(row_c)
        return curve

    solar_curve = build_curve("sol", sol_hyp_tot, sol_hyp_miss)
    civil_curve = build_curve("civ", civ_hyp_tot, civ_hyp_miss)

    # Named window contrasts (State & HUC-2 clustered)
    window_results = {}
    for w in ("ls10", "pm1316", "pm1330", "am0912", "dawn0507"):
        sub = rc_df[[f"s_{w}", f"s_{w}_instT", "s_domin", f"bias_{w}", "state", "huc2"]].dropna(subset=[f"s_{w}", "s_domin"]).copy()
        sub["diff_slope"] = sub[f"s_{w}"] - sub["s_domin"]
        sub["diff_instT"] = sub[f"s_{w}_instT"] - sub["s_domin"]
        sub_q = rc_df[[f"s_{w}_q", "s_domin_q", "state", "huc2"]].dropna().copy()
        sub_q["diff_slope_q"] = sub_q[f"s_{w}_q"] - sub_q["s_domin_q"]

        att = round(100.0 * (1.0 - float(sub[f"s_{w}"].mean()) / float(sub["s_domin"].mean())), 2)
        att_i = round(100.0 * (1.0 - float(sub[f"s_{w}_instT"].mean()) / float(sub["s_domin"].mean())), 2)
        att_q = round(100.0 * (1.0 - float(sub_q[f"s_{w}_q"].mean()) / float(sub_q["s_domin_q"].mean())), 2) if len(sub_q) else None
        pct_under = round(100.0 * float((sub["diff_slope"] > 0).mean()), 2)
        _, wp_r = stats.wilcoxon(sub["diff_slope"].values)

        window_results[w] = {
            "n_rivers": len(sub),
            "mean_DOmin_slope": round(float(sub["s_domin"].mean()), 5),
            "mean_window_slope": round(float(sub[f"s_{w}"].mean()), 5),
            "mean_window_instT_slope": round(float(sub[f"s_{w}_instT"].mean()), 5),
            "warming_underestimation_pct": att,
            "warming_underestimation_instT_pct": att_i,
            "warming_underestimation_qctrl_pct": att_q,
            "pct_rivers_underestimating": pct_under,
            "river_wilcoxon_p": float(wp_r),
            "slope_bias_huc2_clustered": cluster_t_block(sub, "diff_slope", "huc2"),
            "slope_bias_state_clustered": cluster_t_block(sub, "diff_slope", "state"),
            "slope_bias_instT_huc2_clustered": cluster_t_block(sub.dropna(subset=["diff_instT"]), "diff_instT", "huc2"),
            "slope_bias_qctrl_huc2_clustered": cluster_t_block(sub_q, "diff_slope_q", "huc2"),
            "do_bias_mgL_huc2_clustered": cluster_t_block(sub.dropna(subset=[f"bias_{w}"]), f"bias_{w}", "huc2"),
            "hypoxia_blindness": {
                f"lt_{tt}_mgL": {
                    "nocturnal_hypoxia_days": int(win_hyp_tot[w][tt]),
                    "missed_days": int(win_hyp_miss[w][tt]),
                    "missed_pct": round(100.0 * win_hyp_miss[w][tt] / win_hyp_tot[w][tt], 2)
                    if win_hyp_tot[w][tt] > 0
                    else None,
                }
                for tt in ("5", "4", "3", "2")
            },
        }

    # Direct paired comparison: Afternoon (13:00-16:00) slope bias MINUS Landsat (10:00-11:00) slope bias
    pair_al = rc_df[["s_pm1316", "s_ls10", "s_domin", "state", "huc2"]].dropna().copy()
    pair_al["pm_minus_ls_slope"] = pair_al["s_pm1316"] - pair_al["s_ls10"]

    print("Evaluating Leave-One-HUC2-Basin-Out & 2024 Temporal-Holdout Transfer Functions...", flush=True)
    tf_eval = evaluate_transfer_function(iv_meta)

    summary = {
        "n_iv_rivers": len(iv_meta),
        "n_states": int(iv_meta["state"].nunique()),
        "n_huc2_basins": int(iv_meta["huc2"].nunique()),
        "total_iv_warm_river_days": int(iv_meta["n_iv_days"].sum()),
        "n_iv_rivers_with_q": int((rc_df["has_q_iv"] == 1).sum()),
        "iv_mean_DOsat_alt_slope": round(float(rc_df["s_dosat_alt"].mean()), 5),
        "years_covered": YEARS_IV,
        "named_windows": window_results,
        "afternoon_minus_landsat_slope_contrast_huc2": cluster_t_block(pair_al, "pm_minus_ls_slope", "huc2"),
        "afternoon_minus_landsat_slope_contrast_state": cluster_t_block(pair_al, "pm_minus_ls_slope", "state"),
        "solar_24h_curve": solar_curve,
        "civil_24h_curve": civil_curve,
        "transfer_function_oos": tf_eval,
    }
    out_p = RES_DIR / "conus_iv_24h_clock_results.json"
    out_p.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== STEP 3 CONUS 24-HOUR IV CLOCK-BIAS SUMMARY ===", flush=True)
    print(
        json.dumps(
            {
                "n_iv_rivers": summary["n_iv_rivers"],
                "n_states": summary["n_states"],
                "n_huc2_basins": summary["n_huc2_basins"],
                "total_iv_warm_river_days": summary["total_iv_warm_river_days"],
                "pm1316": summary["named_windows"]["pm1316"],
                "pm1330": summary["named_windows"]["pm1330"],
                "ls10": summary["named_windows"]["ls10"],
                "transfer_function_afternoon_summary": {
                    k: v
                    for k, v in summary["transfer_function_oos"].get("afternoon_1430", {}).items()
                    if k != "full_fit_coefficients"
                },
                "transfer_function_landsat_summary": {
                    k: v
                    for k, v in summary["transfer_function_oos"].get("landsat_1030", {}).items()
                    if k != "full_fit_coefficients"
                },
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
