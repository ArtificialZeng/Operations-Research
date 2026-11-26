"""Step 5: Full-Rank Econometric, Hydrologic, Compound-Extreme, Biophysical Mechanism & Secular Trend Suite."""
from __future__ import annotations

import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

BASE_DIR = Path(r"D:\AI_Science\antigravity\d4_boost_nocturnal_river_hypoxia_20261125")
DV_DIR = BASE_DIR / "data" / "raw_usgs_dv"
PROC_DIR = BASE_DIR / "data" / "processed"
RES_DIR = BASE_DIR / "results"

RNG_SEED = 20261125
N_BOOT = 5000


def benson_krause_do_sat_1atm(temp_c: np.ndarray) -> np.ndarray:
    """USGS standard Benson & Krause (1984) freshwater DO saturation (mg/L) at 1 atm."""
    t_k = np.asarray(temp_c, dtype=float) + 273.15
    ln_c = (
        -139.34411
        + 1.575701e5 / t_k
        - 6.642308e7 / (t_k**2)
        + 1.243800e10 / (t_k**3)
        - 8.621949e11 / (t_k**4)
    )
    return np.exp(ln_c)


def benson_krause_do_sat_alt(temp_c: np.ndarray, alt_m: float) -> np.ndarray:
    """USGS TWRI Book 9 barometric-pressure & water-vapor adjusted Benson-Krause DO saturation (mg/L)."""
    c_1atm = benson_krause_do_sat_1atm(temp_c)
    if not np.isfinite(alt_m) or alt_m <= 0.0:
        return c_1atm
    z = float(np.clip(alt_m, 0.0, 4500.0))
    p_atm = (1.0 - 2.25577e-5 * z) ** 5.25588
    # Antoine/Benson-Krause water vapor pressure in atm
    t_k = np.asarray(temp_c, dtype=float) + 273.15
    p_wv = np.exp(11.8571 - 3840.70 / t_k - 216961.0 / (t_k**2))
    f_p = (p_atm - p_wv) / (1.0 - p_wv)
    return c_1atm * f_p


def fwl_demean_cols(df: pd.DataFrame, group_col: str, cols: list[str]) -> np.ndarray:
    """Exact Frisch-Waugh-Lovell within-group demeaning returning matrix (n, len(cols))."""
    g = df.groupby(group_col)
    mats = [df[c].values - g[c].transform("mean").values for c in cols]
    return np.column_stack(mats)


def fit_within_ym_ols(
    df: pd.DataFrame,
    y_cols: list[str],
    x_cols: list[str],
    ym_col: str = "ym",
    min_days: int = 300,
) -> dict[str, float] | None:
    """Full-rank within-YearxMonth FE OLS returning coefficient on x_cols[0] for each y_col."""
    need = list(dict.fromkeys(y_cols + x_cols + [ym_col]))
    sub = df[need].dropna().copy()
    if len(sub) < min_days:
        return None
    # Drop Year-Month cells with < 5 observations to ensure clean within-month variation
    yc = sub[ym_col].value_counts()
    sub = sub[sub[ym_col].isin(yc[yc >= 5].index)]
    if len(sub) < min_days:
        return None

    X = fwl_demean_cols(sub, ym_col, x_cols)
    k = X.shape[1]
    if np.linalg.matrix_rank(X) < k:
        return None
    # Guard against near-collinearity (condition number check)
    svals = np.linalg.svd(X, compute_uv=False)
    if svals[-1] <= 1e-8 * svals[0]:
        return None

    Y = fwl_demean_cols(sub, ym_col, y_cols)
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    return {yc_name: float(beta[0, j]) for j, yc_name in enumerate(y_cols)}


def fit_within_ym_full_betas(
    df: pd.DataFrame,
    y_cols: list[str],
    x_cols: list[str],
    ym_col: str = "ym",
    min_days: int = 300,
) -> dict[str, list[float]] | None:
    """Full-rank within-YM FE OLS returning all x_cols coefficients for each y_col."""
    need = list(dict.fromkeys(y_cols + x_cols + [ym_col]))
    sub = df[need].dropna().copy()
    if len(sub) < min_days:
        return None
    yc = sub[ym_col].value_counts()
    sub = sub[sub[ym_col].isin(yc[yc >= 5].index)]
    if len(sub) < min_days:
        return None

    X = fwl_demean_cols(sub, ym_col, x_cols)
    k = X.shape[1]
    if np.linalg.matrix_rank(X) < k:
        return None
    svals = np.linalg.svd(X, compute_uv=False)
    if svals[-1] <= 1e-8 * svals[0]:
        return None

    Y = fwl_demean_cols(sub, ym_col, y_cols)
    beta, *_ = np.linalg.lstsq(X, Y, rcond=None)
    return {yc_name: [float(beta[r, j]) for r in range(k)] for j, yc_name in enumerate(y_cols)}


def spatial_inference_block(df: pd.DataFrame, col: str, rng: np.random.Generator) -> dict:
    """Comprehensive river-level, State-clustered, and HUC-2-clustered inference (finite-sample t(G-1), Wilcoxon, bootstrap)."""
    sub = df[[col, "state", "huc2"]].dropna().copy()
    y = sub[col].values.astype(float)
    n = len(y)
    if n < 5:
        return {"n_rivers": n}

    mu = float(y.mean())
    med = float(np.median(y))
    sd = float(y.std(ddof=1))
    se_r = sd / np.sqrt(n)
    t_r, p_r = stats.ttest_1samp(y, 0.0)
    try:
        _, wp_r = stats.wilcoxon(y)
    except ValueError:
        wp_r = np.nan

    res: dict = {
        "n_rivers": n,
        "mean": round(mu, 5),
        "median": round(med, 5),
        "sd": round(sd, 5),
        "pct_neg": round(100.0 * float((y < 0).mean()), 2),
        "pct_pos": round(100.0 * float((y > 0).mean()), 2),
        "river_se": round(float(se_r), 5),
        "river_t": round(float(t_r), 3),
        "river_p_t": float(p_r),
        "river_p_wilcoxon": float(wp_r) if pd.notna(wp_r) else None,
    }

    for cl_col, cl_tag in [("state", "state_cluster"), ("huc2", "huc2_cluster")]:
        groups = [g[col].values.astype(float) for _, g in sub.groupby(cl_col)]
        g_cnt = len(groups)
        g_means = np.array([g.mean() for g in groups], dtype=float)
        g_sums_dev = np.array([(g - mu).sum() for g in groups], dtype=float)
        g_lens = np.array([len(g) for g in groups], dtype=float)
        g_raw_sums = np.array([g.sum() for g in groups], dtype=float)

        # CR1 cluster-robust SE for equal-river sample mean
        se_cr1 = float(np.sqrt((g_cnt / max(1, g_cnt - 1)) * np.sum(g_sums_dev**2)) / n)
        t_cr1 = mu / se_cr1 if se_cr1 > 1e-12 else np.nan
        p_cr1 = float(2.0 * stats.t.sf(abs(t_cr1), df=max(1, g_cnt - 1))) if pd.notna(t_cr1) else np.nan
        tcrit = float(stats.t.ppf(0.975, df=max(1, g_cnt - 1)))

        # Equal-cluster-mean conservative t(G-1) and Wilcoxon
        t_gm, p_gm = stats.ttest_1samp(g_means, 0.0) if g_cnt >= 3 else (np.nan, np.nan)
        try:
            _, wp_gm = stats.wilcoxon(g_means)
        except ValueError:
            wp_gm = np.nan

        # Vectorized pairs cluster bootstrap (B = 5,000) for equal-river mean
        idx_b = rng.integers(0, g_cnt, size=(N_BOOT, g_cnt))
        b_means = g_raw_sums[idx_b].sum(axis=1) / g_lens[idx_b].sum(axis=1)
        b_lo, b_hi = np.percentile(b_means, [2.5, 97.5])
        # Two-sided bootstrap p-value (percentile sign test)
        p_boot = float(2.0 * min((b_means <= 0.0).mean(), (b_means >= 0.0).mean()))
        p_boot = max(p_boot, 1.0 / (N_BOOT + 1))

        res[cl_tag] = {
            "n_clusters": int(g_cnt),
            "se_cr1": round(se_cr1, 5),
            "ci95_lo": round(mu - tcrit * se_cr1, 5),
            "ci95_hi": round(mu + tcrit * se_cr1, 5),
            "t_cr1": round(float(t_cr1), 3) if pd.notna(t_cr1) else None,
            "p_cr1_t_Gminus1": p_cr1 if pd.notna(p_cr1) else None,
            "boot_ci95_lo": round(float(b_lo), 5),
            "boot_ci95_hi": round(float(b_hi), 5),
            "boot_p": round(p_boot, 6),
            "cluster_equal_mean": round(float(g_means.mean()), 5),
            "cluster_equal_t": round(float(t_gm), 3) if pd.notna(t_gm) else None,
            "cluster_equal_p_t": float(p_gm) if pd.notna(p_gm) else None,
            "cluster_equal_p_wilcoxon": float(wp_gm) if pd.notna(wp_gm) else None,
        }
    return res


def process_all_rivers(meta_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Process every clean CONUS river daily time series & compute all within-river estimators + pooled panel sufficient stats."""
    river_rows = []
    # Pooled sufficient stats accumulated by cluster for exact full-sample pooled FWL regression!
    # Wait: even cleaner, collect demeaned (y, x) arrays for pooled Spec 2 (YM-FE + logQ + logQ^2)
    pooled_chunks = []

    hyp_counts = {
        thr: {"min": 0, "mean": 0, "max": 0, "miss_mean": 0, "miss_max": 0, "rivers_any": 0}
        for thr in ("5", "4", "3", "2")
    }
    hyp_warm_counts = {
        thr: {"min": 0, "mean": 0, "max": 0, "miss_mean": 0, "miss_max": 0, "rivers_any": 0}
        for thr in ("5", "4", "3", "2")
    }

    for rec in meta_df.to_dict("records"):
        sno = str(rec["site_no"]).strip()
        pq = DV_DIR / f"{sno}.parquet"
        if not pq.exists():
            continue
        df = pd.read_parquet(pq).copy()
        df.index = pd.to_datetime(df.index)
        alt_va = float(rec["alt_va"]) if pd.notna(rec.get("alt_va")) else np.nan
        alt_m = alt_va * 0.3048 if np.isfinite(alt_va) else 0.0

        df["year"] = df.index.year
        df["month"] = df.index.month
        df["ym"] = df["year"].astype(str) + "-" + df["month"].astype(str).str.zfill(2)

        df["do_sat_1atm"] = benson_krause_do_sat_1atm(df["temp_mean"].values)
        df["do_sat_alt"] = benson_krause_do_sat_alt(df["temp_mean"].values, alt_m)
        df["do_sat_tmin"] = np.where(
            df["temp_min"].notna(),
            benson_krause_do_sat_alt(df["temp_min"].fillna(df["temp_mean"]).values, alt_m),
            np.nan,
        )
        df["do_sat_tmax"] = np.where(
            df["temp_max"].notna(),
            benson_krause_do_sat_alt(df["temp_max"].fillna(df["temp_mean"]).values, alt_m),
            np.nan,
        )
        df["swing"] = df["do_max"] - df["do_min"]
        df["plunge"] = df["do_mean"] - df["do_min"]
        df["diff_min_max"] = df["do_min"] - df["do_max"]
        df["diff_min_mean"] = df["do_min"] - df["do_mean"]
        df["diff_min_sat"] = df["do_min"] - df["do_sat_alt"]
        df["diff_max_sat"] = df["do_max"] - df["do_sat_alt"]
        df["diff_min_sat_1atm"] = df["do_min"] - df["do_sat_1atm"]
        df["diff_max_sat_1atm"] = df["do_max"] - df["do_sat_1atm"]
        df["diff_min_sat_exact"] = df["do_min"] - df["do_sat_tmin"]
        df["diff_max_sat_exact"] = df["do_max"] - df["do_sat_tmax"]
        df["pct_sat_min"] = 100.0 * df["do_min"] / df["do_sat_alt"]
        df["pct_sat_max"] = 100.0 * df["do_max"] / df["do_sat_alt"]
        df["log_q"] = np.where(df["q_cfs"] > 0.0, np.log(df["q_cfs"].where(df["q_cfs"] > 0.0)), np.nan)
        df["log_q2"] = df["log_q"] ** 2
        df["log_spcond"] = np.where(df["spcond"] > 0.0, np.log(df["spcond"].where(df["spcond"] > 0.0)), np.nan)
        df["log_turb"] = np.where(df["turb"] >= 0.0, np.log1p(df["turb"].where(df["turb"] >= 0.0)), np.nan)
        for thr_v, tt in [(5.0, "5"), (4.0, "4"), (3.0, "3"), (2.0, "2")]:
            df[f"hyp{tt}_min"] = (df["do_min"] < thr_v).astype(float)
            df[f"hyp{tt}_max"] = (df["do_max"] < thr_v).astype(float)
        df["hyp5_min_minus_max"] = df["hyp5_min"] - df["hyp5_max"]

        warm = df[df["month"].between(5, 10)].copy()
        peak = df[df["month"].between(6, 8)].copy()

        # Hypoxia blindness totals (all year & warm season)
        for frame, target_dict in [(df, hyp_counts), (warm, hyp_warm_counts)]:
            for thr_v, tt in [(5.0, "5"), (4.0, "4"), (3.0, "3"), (2.0, "2")]:
                n_min = int((frame["do_min"] < thr_v).sum())
                n_mean = int((frame["do_mean"] < thr_v).sum())
                n_max = int((frame["do_max"] < thr_v).sum())
                m_mean = int(((frame["do_min"] < thr_v) & (frame["do_mean"] >= thr_v)).sum())
                m_max = int(((frame["do_min"] < thr_v) & (frame["do_max"] >= thr_v)).sum())
                target_dict[tt]["min"] += n_min
                target_dict[tt]["mean"] += n_mean
                target_dict[tt]["max"] += n_max
                target_dict[tt]["miss_mean"] += m_mean
                target_dict[tt]["miss_max"] += m_max
                if n_min > 0:
                    target_dict[tt]["rivers_any"] += 1

        out = {
            "site_no": sno,
            "state": rec["state"],
            "huc2": str(rec["huc2"]).zfill(2),
            "station_nm": rec["station_nm"],
            "lat": float(rec["lat"]),
            "lon": float(rec["lon"]),
            "alt_m": alt_m,
            "drain_area_va": float(rec["drain_area_va"]) if pd.notna(rec.get("drain_area_va")) else np.nan,
            "ultra_strict_flagged": int(rec["ultra_strict_flagged"]),
            "nid_dist_any_km": float(rec["nid_dist_any_km"]) if pd.notna(rec.get("nid_dist_any_km")) else np.nan,
            "nid_dist_ge500af_km": float(rec["nid_dist_ge500af_km"]) if pd.notna(rec.get("nid_dist_ge500af_km")) else np.nan,
            "nid_dist_ge5000af_km": float(rec["nid_dist_ge5000af_km"]) if pd.notna(rec.get("nid_dist_ge5000af_km")) else np.nan,
            "n_days": len(df),
            "n_warm_days": len(warm),
            "n_warm_years": int(warm["year"].nunique()),
            "warm_mean_temp": float(warm["temp_mean"].mean()),
            "warm_mean_do_min": float(warm["do_min"].mean()),
            "warm_mean_do_mean": float(warm["do_mean"].mean()),
            "warm_mean_do_max": float(warm["do_max"].mean()),
            "warm_mean_swing": float(warm["swing"].mean()),
            "warm_mean_plunge": float(warm["plunge"].mean()),
            "warm_median_q": float(warm["q_cfs"].median()) if warm["q_cfs"].notna().sum() >= 100 else np.nan,
            "warm_median_spcond": float(warm["spcond"].median()) if warm["spcond"].notna().sum() >= 100 else np.nan,
            "warm_median_turb": float(warm["turb"].median()) if warm["turb"].notna().sum() >= 100 else np.nan,
        }

        core_ys = [
            "do_sat_alt",
            "do_sat_1atm",
            "do_max",
            "do_mean",
            "do_min",
            "diff_min_max",
            "diff_min_mean",
            "diff_min_sat",
            "diff_max_sat",
            "diff_min_sat_1atm",
            "diff_max_sat_1atm",
            "plunge",
            "swing",
            "pct_sat_min",
            "pct_sat_max",
        ]

        # Spec 1: Warm-season Year x Month FE (all clean rivers)
        b1 = fit_within_ym_ols(warm, core_ys, ["temp_mean"], min_days=300)
        if b1 is None:
            continue
        for k, v in b1.items():
            out[f"s1_{k}"] = v

        # Spec 2 (Primary): Warm-season Year x Month FE + log(Q) + log(Q)^2
        b2 = fit_within_ym_ols(warm, core_ys, ["temp_mean", "log_q", "log_q2"], min_days=300)
        out["has_spec2_q"] = int(b2 is not None)
        if b2 is not None:
            for k, v in b2.items():
                out[f"s2_{k}"] = v
            # Store demeaned vectors for pooled continental panel check!
            sub_p = warm[["ym", "temp_mean", "log_q", "log_q2", "do_min", "do_max", "do_mean", "do_sat_alt"]].dropna()
            yc = sub_p["ym"].value_counts()
            sub_p = sub_p[sub_p["ym"].isin(yc[yc >= 5].index)]
            if len(sub_p) >= 300:
                dm = fwl_demean_cols(
                    sub_p,
                    "ym",
                    ["temp_mean", "log_q", "log_q2", "do_min", "do_max", "do_mean", "do_sat_alt"],
                )
                pooled_chunks.append(
                    {
                        "state": rec["state"],
                        "huc2": str(rec["huc2"]).zfill(2),
                        "site_no": sno,
                        "n_ym_cells": int(sub_p["ym"].nunique()),
                        "dm": dm.astype(np.float64),
                    }
                )

        # Spec 3: Exact diurnal T_min / T_max Benson-Krause solubility check (with YM FE + logQ + logQ^2)
        b3 = fit_within_ym_ols(
            warm,
            ["do_sat_tmin", "do_sat_tmax", "diff_min_sat_exact", "diff_max_sat_exact", "diff_min_sat", "diff_max_sat"],
            ["temp_mean", "log_q", "log_q2"],
            min_days=300,
        )
        out["has_spec3_exactT"] = int(b3 is not None)
        if b3 is not None:
            for k, v in b3.items():
                out[f"s3_{k}"] = v

        # Spec 4a / 4b: Adding log(SpCond) and log(1+Turbidity) controls on top of Spec 2
        b4a = fit_within_ym_ols(
            warm,
            ["do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat"],
            ["temp_mean", "log_q", "log_q2", "log_spcond"],
            min_days=300,
        )
        out["has_spec4_spcond"] = int(b4a is not None)
        if b4a is not None:
            for k, v in b4a.items():
                out[f"s4sc_{k}"] = v

        b4b = fit_within_ym_ols(
            warm,
            ["do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat"],
            ["temp_mean", "log_q", "log_q2", "log_turb"],
            min_days=300,
        )
        out["has_spec4_turb"] = int(b4b is not None)
        if b4b is not None:
            for k, v in b4b.items():
                out[f"s4tb_{k}"] = v

        # Spec 5a / 5b: Peak summer (Jun-Aug) & All-year (Jan-Dec) with YM FE + logQ + logQ^2
        b5_pk = fit_within_ym_ols(peak, ["do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat"], ["temp_mean", "log_q", "log_q2"], min_days=180)
        if b5_pk is not None:
            for k, v in b5_pk.items():
                out[f"s5pk_{k}"] = v
        b5_all = fit_within_ym_ols(df, ["do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat"], ["temp_mean", "log_q", "log_q2"], min_days=500)
        if b5_all is not None:
            for k, v in b5_all.items():
                out[f"s5all_{k}"] = v

        # Compound Heatwave x Low-Flow Drought Interaction (within-river YM FE: Hot + Dry + Hot*Dry)
        wq = warm.dropna(subset=["q_cfs", "temp_mean", "do_min", "do_max", "do_mean", "do_sat_alt"]).copy()
        wq = wq[wq["q_cfs"] > 0.0]
        if len(wq) >= 400:
            t90 = wq.groupby("month")["temp_mean"].transform(lambda s: s.quantile(0.90))
            q20 = wq.groupby("month")["q_cfs"].transform(lambda s: s.quantile(0.20))
            wq["hot"] = (wq["temp_mean"] >= t90).astype(float)
            wq["dry"] = (wq["q_cfs"] <= q20).astype(float)
            wq["hot_x_dry"] = wq["hot"] * wq["dry"]
            n_comp = int(wq["hot_x_dry"].sum())
            if n_comp >= 12:
                comp_ys = ["do_sat_alt", "do_max", "do_mean", "do_min", "diff_min_max", "diff_min_sat", "plunge", "hyp5_min", "hyp3_min", "hyp2_min", "hyp5_max", "hyp5_min_minus_max"]
                bc = fit_within_ym_full_betas(wq, comp_ys, ["hot", "dry", "hot_x_dry"], min_days=300)
                if bc is not None:
                    out["has_compound"] = 1
                    out["n_compound_days"] = n_comp
                    for k, bvec in bc.items():
                        out[f"cmp_hot_{k}"] = bvec[0]
                        out[f"cmp_dry_{k}"] = bvec[1]
                        out[f"cmp_int_{k}"] = bvec[2]
                        out[f"cmp_tot_{k}"] = bvec[0] + bvec[1] + bvec[2]
                else:
                    out["has_compound"] = 0
            else:
                out["has_compound"] = 0
        else:
            out["has_compound"] = 0

        # Split-Half Out-of-Sample Productivity Mechanism Test (eliminating same-period mathematical coupling!)
        # Strictly uniform specifications: (a) Uniform Q-controlled (primary, matching Spec 2) and (b) Uniform YM-FE-only!
        out["has_split_half_q"] = 0
        out["has_split_half_ym"] = 0
        yrs_sorted = sorted(warm["year"].unique())
        if len(yrs_sorted) >= 6:
            mid = len(yrs_sorted) // 2
            early_yrs = set(yrs_sorted[:mid])
            late_yrs = set(yrs_sorted[mid:])
            w_early = warm[warm["year"].isin(early_yrs)]
            w_late = warm[warm["year"].isin(late_yrs)]
            if len(w_early) >= 200 and len(w_late) >= 200:
                out["split_early_swing"] = float(w_early["swing"].mean())
                sh_ys = ["do_sat_alt", "do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat", "plunge"]
                b_late_q = fit_within_ym_ols(w_late, sh_ys, ["temp_mean", "log_q", "log_q2"], min_days=180)
                if b_late_q is not None:
                    out["has_split_half_q"] = 1
                    for k, v in b_late_q.items():
                        out[f"split_late_{k}"] = v
                b_late_ym = fit_within_ym_ols(w_late, sh_ys, ["temp_mean"], min_days=180)
                if b_late_ym is not None:
                    out["has_split_half_ym"] = 1
                    for k, v in b_late_ym.items():
                        out[f"split_late_ym_{k}"] = v

        # Secular 10-20 Year Warm-Season Trend Audit (annual warm means requiring >= 90 days/yr, >= 10 warm yrs)
        ann = warm.groupby("year").agg(
            n=("do_min", "count"),
            temp_mean=("temp_mean", "mean"),
            do_sat_alt=("do_sat_alt", "mean"),
            do_max=("do_max", "mean"),
            do_mean=("do_mean", "mean"),
            do_min=("do_min", "mean"),
            swing=("swing", "mean"),
            plunge=("plunge", "mean"),
            diff_min_sat=("diff_min_sat", "mean"),
            hyp5_rate=("hyp5_min", "mean"),
            log_q=("log_q", "mean"),
            log_spcond=("log_spcond", "mean"),
        )
        ann = ann[ann["n"] >= 90]
        if len(ann) >= 10 and (ann.index.max() - ann.index.min()) >= 10:
            out["has_secular_10yr"] = 1
            out["secular_n_years"] = len(ann)
            out["secular_span_years"] = int(ann.index.max() - ann.index.min())
            yrs_f = ann.index.values.astype(float)
            for c in ["temp_mean", "do_sat_alt", "do_max", "do_mean", "do_min", "swing", "plunge", "diff_min_sat", "hyp5_rate"]:
                out[f"tr_dec_{c}"] = float(stats.linregress(yrs_f, ann[c].values).slope * 10.0)
                # Theil-Sen robust decadal slope check
                out[f"tsen_dec_{c}"] = float(stats.theilslopes(ann[c].values, yrs_f)[0] * 10.0)
            # Discharge-adjusted secular trend (controlling for annual mean log Q)
            ann_q = ann.dropna(subset=["log_q"])
            if len(ann_q) >= 10:
                Xq = np.column_stack([np.ones(len(ann_q)), ann_q.index.values.astype(float) - 2015.0, ann_q["log_q"].values])
                if np.linalg.matrix_rank(Xq) == 3:
                    for c in ["temp_mean", "do_min", "do_max", "swing", "plunge", "diff_min_sat"]:
                        out[f"trq_dec_{c}"] = float(np.linalg.lstsq(Xq, ann_q[c].values, rcond=None)[0][1] * 10.0)
        else:
            out["has_secular_10yr"] = 0

        river_rows.append(out)

    rdf = pd.DataFrame(river_rows).sort_values(["huc2", "state", "site_no"]).reset_index(drop=True)

    # Compute exact Pooled River-Day Panel Regressions (Spec 6) with HUC-2 & State cluster-robust SEs!
    pooled_res = compute_pooled_panel_cr1(pooled_chunks)
    aux = {
        "hypoxia_all_year": hyp_counts,
        "hypoxia_warm_season": hyp_warm_counts,
        "pooled_panel": pooled_res,
    }
    return rdf, aux


def compute_pooled_panel_cr1(chunks: list[dict]) -> dict:
    """Exact pooled River x Year x Month FE regression with State and HUC-2 CR1 cluster-robust SEs."""
    if not chunks:
        return {}
    # columns in dm: [0:temp_mean, 1:log_q, 2:log_q2, 3:do_min, 4:do_max, 5:do_mean, 6:do_sat_alt]
    n_obs = sum(c["dm"].shape[0] for c in chunks)
    X_all = np.vstack([c["dm"][:, :3].astype(np.float64) for c in chunks])
    Y_dict = {
        "do_sat_alt": np.concatenate([c["dm"][:, 6].astype(np.float64) for c in chunks]),
        "do_max": np.concatenate([c["dm"][:, 4].astype(np.float64) for c in chunks]),
        "do_mean": np.concatenate([c["dm"][:, 5].astype(np.float64) for c in chunks]),
        "do_min": np.concatenate([c["dm"][:, 3].astype(np.float64) for c in chunks]),
        "diff_min_max": np.concatenate([(c["dm"][:, 3] - c["dm"][:, 4]).astype(np.float64) for c in chunks]),
        "diff_min_mean": np.concatenate([(c["dm"][:, 3] - c["dm"][:, 5]).astype(np.float64) for c in chunks]),
        "diff_min_sat": np.concatenate([(c["dm"][:, 3] - c["dm"][:, 6]).astype(np.float64) for c in chunks]),
        "diff_max_sat": np.concatenate([(c["dm"][:, 4] - c["dm"][:, 6]).astype(np.float64) for c in chunks]),
    }
    XtX = X_all.T @ X_all
    assert np.linalg.matrix_rank(XtX) == 3, "Pooled panel X'X rank deficient!"
    XtX_inv = np.linalg.inv(XtX)

    # Build slice indices per cluster
    states_arr = [c["state"] for c in chunks]
    hucs_arr = [c["huc2"] for c in chunks]
    lens = [c["dm"].shape[0] for c in chunks]
    k_fe = int(sum(c.get("n_ym_cells", 0) for c in chunks))
    starts = np.cumsum([0] + lens[:-1])

    out = {"n_river_days": int(n_obs), "n_rivers": len(chunks), "n_absorbed_fe_cells": k_fe, "outcomes": {}}
    for name, y in Y_dict.items():
        beta = XtX_inv @ (X_all.T @ y)
        resid = y - X_all @ beta
        rec: dict = {"beta_temp": round(float(beta[0]), 5)}

        for cl_label, cl_keys in [("state_cluster", states_arr), ("huc2_cluster", hucs_arr)]:
            uniq = sorted(set(cl_keys))
            g = len(uniq)
            meat = np.zeros((3, 3), dtype=np.float64)
            u_map = {k: np.zeros(3, dtype=np.float64) for k in uniq}
            for st_i, ln_i, ck in zip(starts, lens, cl_keys):
                Xi = X_all[st_i : st_i + ln_i]
                ei = resid[st_i : st_i + ln_i]
                u_map[ck] += Xi.T @ ei
            for vec in u_map.values():
                meat += np.outer(vec, vec)
            # Exact CR1 finite-sample scaling: G/(G-1) * (N-1)/(N - K_fe - k)
            dof_scale = (n_obs - 1) / max(1, n_obs - k_fe - 3)
            V = (g / max(1, g - 1)) * dof_scale * (XtX_inv @ meat @ XtX_inv)
            se = float(np.sqrt(V[0, 0]))
            t_v = float(beta[0] / se)
            p_v = float(2.0 * stats.t.sf(abs(t_v), df=max(1, g - 1)))
            tcrit = float(stats.t.ppf(0.975, df=max(1, g - 1)))
            rec[cl_label] = {
                "n_clusters": int(g),
                "se_cr1": round(se, 5),
                "ci95_lo": round(float(beta[0] - tcrit * se), 5),
                "ci95_hi": round(float(beta[0] + tcrit * se), 5),
                "t_cr1": round(t_v, 3),
                "p_cr1_t_Gminus1": p_v,
            }
        out["outcomes"][name] = rec
    return out


def format_hyp_summary(d: dict) -> dict:
    out = {}
    for tt in ("5", "4", "3", "2"):
        c = d[tt]
        n_min = c["min"]
        out[f"lt_{tt}_mgL"] = {
            "DOmin_days": n_min,
            "DOmean_days": c["mean"],
            "DOmax_days": c["max"],
            "missed_by_DOmean_pct": round(100.0 * c["miss_mean"] / max(1, n_min), 2),
            "missed_by_DOmax_pct": round(100.0 * c["miss_max"] / max(1, n_min), 2),
            "ratio_DOmin_to_DOmax": round(n_min / max(1, c["max"]), 3),
            "rivers_with_any_DOmin_hypoxia": c["rivers_any"],
        }
    return out


def cross_river_ols_clustered(df: pd.DataFrame, y_col: str, x_cols: list[str], cl_col: str = "huc2") -> dict:
    """Full-rank cross-river OLS with CR1 cluster-robust SEs and t(G-1) p-values."""
    sub = df[[y_col, cl_col] + x_cols].dropna().copy()
    if len(sub) < len(x_cols) + 10:
        return {"n": len(sub)}
    X = np.column_stack([np.ones(len(sub))] + [sub[c].values.astype(float) for c in x_cols])
    y = sub[y_col].values.astype(float)
    k = X.shape[1]
    assert np.linalg.matrix_rank(X) == k, f"Cross-river OLS rank deficient for {y_col}"
    XtX_inv = np.linalg.inv(X.T @ X)
    beta = XtX_inv @ (X.T @ y)
    resid = y - X @ beta
    r2 = float(1.0 - np.sum(resid**2) / np.sum((y - y.mean()) ** 2))

    # CR1 cluster SEs
    uniq = sorted(sub[cl_col].unique())
    g = len(uniq)
    meat = np.zeros((k, k), dtype=float)
    for u in uniq:
        m = (sub[cl_col].values == u)
        score = X[m].T @ resid[m]
        meat += np.outer(score, score)
    scale = (g / max(1, g - 1)) * ((len(sub) - 1) / max(1, len(sub) - k))
    V = scale * (XtX_inv @ meat @ XtX_inv)
    ses = np.sqrt(np.diag(V))

    names = ["intercept"] + x_cols
    coefs = {}
    for j, nm in enumerate(names):
        tv = float(beta[j] / ses[j])
        pv = float(2.0 * stats.t.sf(abs(tv), df=max(1, g - 1)))
        coefs[nm] = {"beta": round(float(beta[j]), 5), "se_cr1": round(float(ses[j]), 5), "t": round(tv, 3), "p_t_Gminus1": pv}
    return {"n_rivers": len(sub), "n_clusters": int(g), "r2": round(r2, 4), "rank": int(k), "coefs": coefs}


def main() -> None:
    t0 = time.monotonic()
    rng = np.random.default_rng(RNG_SEED)
    meta_df = pd.read_csv(PROC_DIR / "conus_valid_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
    print(f"Step 5: Running full-rank econometric & hydrologic suite on {len(meta_df)} clean CONUS rivers...", flush=True)

    rdf, aux = process_all_rivers(meta_df)
    rdf.to_csv(PROC_DIR / "conus_river_econometric_panel.csv", index=False)
    print(f"  Processed {len(rdf)} valid rivers across {rdf['state'].nunique()} states & {rdf['huc2'].nunique()} HUC-2 basins ({time.monotonic()-t0:.1f}s)", flush=True)

    sub_q = rdf[rdf["has_spec2_q"] == 1].copy()
    sub_ex = rdf[rdf["has_spec3_exactT"] == 1].copy()
    sub_sc = rdf[rdf["has_spec4_spcond"] == 1].copy()
    sub_tb = rdf[rdf["has_spec4_turb"] == 1].copy()
    sub_us = sub_q[sub_q["ultra_strict_flagged"] == 0].copy()
    sub_10y = sub_q[sub_q["n_warm_years"] >= 10].copy()
    sub_nid_500 = sub_q[sub_q["nid_dist_ge500af_km"] > 5.0].copy()
    sub_nid_5000 = sub_q[sub_q["nid_dist_ge5000af_km"] > 10.0].copy()
    sub_nid_any = sub_q[sub_q["nid_dist_any_km"] > 5.0].copy()
    # 2.0 km reach deduplication (keeping longest warm-season record per 2 km radius)
    sub_q_sorted = sub_q.sort_values("n_warm_days", ascending=False).reset_index(drop=True)
    kept_dedup = []
    for rec_d in sub_q_sorted.to_dict("records"):
        p1 = np.radians(rec_d["lat"])
        dup = False
        for k_d in kept_dedup:
            dp = np.radians(rec_d["lat"] - k_d["lat"])
            dl = np.radians(rec_d["lon"] - k_d["lon"])
            a_v = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(np.radians(k_d["lat"])) * np.sin(dl / 2) ** 2
            if 2.0 * 6371.0088 * np.arcsin(min(1.0, np.sqrt(a_v))) < 2.0:
                dup = True
                break
        if not dup:
            kept_dedup.append(rec_d)
    sub_dedup2km = pd.DataFrame(kept_dedup)
    sub_cmp = rdf[rdf["has_compound"] == 1].copy()
    sub_sh = rdf[rdf["has_split_half_q"] == 1].copy()
    sub_sh_ym = rdf[rdf["has_split_half_ym"] == 1].copy()
    sub_sec = rdf[rdf["has_secular_10yr"] == 1].copy()

    # Core thermal decoupling specifications
    spec1_out = {
        k: spatial_inference_block(rdf, f"s1_{k}", rng)
        for k in ("do_sat_alt", "do_sat_1atm", "do_max", "do_mean", "do_min", "diff_min_max", "diff_min_mean", "diff_min_sat", "diff_max_sat", "plunge", "swing")
    }
    spec2_out = {
        k: spatial_inference_block(sub_q, f"s2_{k}", rng)
        for k in ("do_sat_alt", "do_sat_1atm", "do_max", "do_mean", "do_min", "diff_min_max", "diff_min_mean", "diff_min_sat", "diff_max_sat", "diff_min_sat_1atm", "diff_max_sat_1atm", "plunge", "swing", "pct_sat_min", "pct_sat_max")
    }
    # Spec 3 exact T_min/T_max solubility invariance test
    sub_ex["sol_gap_min"] = sub_ex["s3_diff_min_sat_exact"] - sub_ex["s3_diff_min_sat"]
    sub_ex["sol_gap_max"] = sub_ex["s3_diff_max_sat_exact"] - sub_ex["s3_diff_max_sat"]
    spec3_out = {
        "n_rivers": len(sub_ex),
        "diff_min_sat_Tmean": spatial_inference_block(sub_ex, "s3_diff_min_sat", rng),
        "diff_min_sat_exactTmin": spatial_inference_block(sub_ex, "s3_diff_min_sat_exact", rng),
        "diff_max_sat_Tmean": spatial_inference_block(sub_ex, "s3_diff_max_sat", rng),
        "diff_max_sat_exactTmax": spatial_inference_block(sub_ex, "s3_diff_max_sat_exact", rng),
        "invariance_gap_min_exact_minus_Tmean": spatial_inference_block(sub_ex, "sol_gap_min", rng),
        "invariance_gap_max_exact_minus_Tmean": spatial_inference_block(sub_ex, "sol_gap_max", rng),
    }

    # Robustness battery (including official USACE NID dam-free sensitivity & 2-km reach deduplication!)
    robustness = {
        "spec4_plus_logSpCond": {
            k: spatial_inference_block(sub_sc, f"s4sc_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec4_plus_logTurbidity": {
            k: spatial_inference_block(sub_tb, f"s4tb_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_ultra_strict_zero_infra": {
            k: spatial_inference_block(sub_us, f"s2_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_long_record_ge10warm_yrs": {
            k: spatial_inference_block(sub_10y, f"s2_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_peak_summer_JunAug": {
            k: spatial_inference_block(rdf.dropna(subset=[f"s5pk_{k}"]), f"s5pk_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_all_year_JanDec": {
            k: spatial_inference_block(rdf.dropna(subset=[f"s5all_{k}"]), f"s5all_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_nid_gt5km_ge500af": {
            k: spatial_inference_block(sub_nid_500, f"s2_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_nid_gt10km_ge5000af": {
            k: spatial_inference_block(sub_nid_5000, f"s2_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_nid_gt5km_any_dam": {
            k: spatial_inference_block(sub_nid_any, f"s2_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
        "spec5_dedup_2km_reach": {
            k: spatial_inference_block(sub_dedup2km, f"s2_{k}", rng)
            for k in ("do_min", "do_max", "diff_min_max", "diff_min_sat", "diff_max_sat")
        },
    }

    # Leave-one-HUC2-basin-out sensitivity for primary s2_diff_min_max
    lohuc_rows = []
    for h in sorted(sub_q["huc2"].unique()):
        sub_l = sub_q[sub_q["huc2"] != h]
        blk = spatial_inference_block(sub_l, "s2_diff_min_max", rng)
        lohuc_rows.append(
            {
                "dropped_huc2": h,
                "n_rivers_remaining": blk["n_rivers"],
                "mean": blk["mean"],
                "p_huc2": blk["huc2_cluster"]["p_cr1_t_Gminus1"],
            }
        )
    robustness["leave_one_huc2_out_diff_min_max"] = lohuc_rows

    # Compound Heatwave x Low-Flow Drought results
    compound_out = {
        "n_rivers": len(sub_cmp),
        "total_compound_days": int(sub_cmp["n_compound_days"].sum()) if len(sub_cmp) else 0,
        "effects": {},
    }
    for k in ("do_sat_alt", "do_max", "do_mean", "do_min", "diff_min_max", "diff_min_sat", "plunge", "hyp5_min", "hyp3_min", "hyp2_min", "hyp5_max", "hyp5_min_minus_max"):
        compound_out["effects"][k] = {
            "hot_only": spatial_inference_block(sub_cmp, f"cmp_hot_{k}", rng),
            "dry_only": spatial_inference_block(sub_cmp, f"cmp_dry_{k}", rng),
            "hot_x_dry_interaction": spatial_inference_block(sub_cmp, f"cmp_int_{k}", rng),
            "total_compound_vs_normal": spatial_inference_block(sub_cmp, f"cmp_tot_{k}", rng),
        }

    # Biophysical Mechanism: Split-half productivity, SpCond, Turbidity, Latitude, Drainage Area
    def spearman_blk(frame: pd.DataFrame, x_c: str, y_c: str) -> dict:
        s = frame[[x_c, y_c]].dropna()
        if len(s) < 10:
            return {"n": len(s)}
        r_v, p_v = stats.spearmanr(s[x_c].values, s[y_c].values)
        return {"n": len(s), "spearman_r": round(float(r_v), 4), "p": float(p_v)}

    # Quartiles of strictly uniform Q-controlled split-half early productivity (matching Spec 2!)
    sub_sh = sub_sh.copy()
    sub_sh["prod_q"] = pd.qcut(sub_sh["split_early_swing"], 4, labels=["Q1_Oligotrophic", "Q2_LowMesotrophic", "Q3_HighMesotrophic", "Q4_Eutrophic"])
    prod_quartiles = {}
    for qlab, g in sub_sh.groupby("prod_q", observed=True):
        prod_quartiles[str(qlab)] = {
            "n_rivers": len(g),
            "early_swing_mean": round(float(g["split_early_swing"].mean()), 3),
            "late_do_sat_alt_slope": spatial_inference_block(g, "split_late_do_sat_alt", rng),
            "late_do_max_slope": spatial_inference_block(g, "split_late_do_max", rng),
            "late_do_min_slope": spatial_inference_block(g, "split_late_do_min", rng),
            "late_diff_min_max": spatial_inference_block(g, "split_late_diff_min_max", rng),
            "late_diff_min_sat": spatial_inference_block(g, "split_late_diff_min_sat", rng),
            "late_diff_max_sat": spatial_inference_block(g, "split_late_diff_max_sat", rng),
        }

    # Stratifications on Spec 2 clean Q-controlled sample
    sub_q = sub_q.copy()
    sub_q["log_spcond_med"] = np.log(sub_q["warm_median_spcond"].where(sub_q["warm_median_spcond"] > 0))
    sub_q["log_turb_med"] = np.log1p(sub_q["warm_median_turb"].where(sub_q["warm_median_turb"] >= 0))
    sub_q["log_da"] = np.log1p(sub_q["drain_area_va"].where(sub_q["drain_area_va"] >= 0))
    sub_q["lat_band"] = pd.cut(sub_q["lat"], bins=[24.0, 35.0, 41.0, 50.0], labels=["South_lt35N", "MidLat_35_41N", "North_gt41N"])

    lat_strata = {}
    for band, g in sub_q.groupby("lat_band", observed=True):
        lat_strata[str(band)] = {
            "n_rivers": len(g),
            "diff_min_max": spatial_inference_block(g, "s2_diff_min_max", rng),
            "do_min": spatial_inference_block(g, "s2_do_min", rng),
            "do_max": spatial_inference_block(g, "s2_do_max", rng),
            "diff_min_sat": spatial_inference_block(g, "s2_diff_min_sat", rng),
        }

    # SpCond tertiles & Turbidity tertiles
    spcond_sub = sub_q.dropna(subset=["warm_median_spcond"]).copy()
    spcond_strata = {}
    if len(spcond_sub) >= 30:
        spcond_sub["sc_tert"] = pd.qcut(spcond_sub["warm_median_spcond"], 3, labels=["T1_LowSpCond", "T2_MidSpCond", "T3_HighSpCond"])
        for tlab, g in spcond_sub.groupby("sc_tert", observed=True):
            spcond_strata[str(tlab)] = {
                "n_rivers": len(g),
                "median_spcond": round(float(g["warm_median_spcond"].median()), 1),
                "diff_min_max": spatial_inference_block(g, "s2_diff_min_max", rng),
                "diff_min_sat": spatial_inference_block(g, "s2_diff_min_sat", rng),
                "do_max": spatial_inference_block(g, "s2_do_max", rng),
                "do_min": spatial_inference_block(g, "s2_do_min", rng),
            }

    turb_sub = sub_q.dropna(subset=["warm_median_turb"]).copy()
    turb_strata = {}
    if len(turb_sub) >= 30:
        turb_sub["tb_tert"] = pd.qcut(turb_sub["warm_median_turb"], 3, labels=["T1_Clear", "T2_ModerateTurb", "T3_Turbid"])
        for tlab, g in turb_sub.groupby("tb_tert", observed=True):
            turb_strata[str(tlab)] = {
                "n_rivers": len(g),
                "median_turb_fnu": round(float(g["warm_median_turb"].median()), 2),
                "diff_min_max": spatial_inference_block(g, "s2_diff_min_max", rng),
                "do_max": spatial_inference_block(g, "s2_do_max", rng),
                "do_min": spatial_inference_block(g, "s2_do_min", rng),
                "diff_max_sat": spatial_inference_block(g, "s2_diff_max_sat", rng),
            }

    # Cross-river multivariate OLS explaining thermal decoupling
    sub_sh_mv = sub_sh.merge(sub_q[["site_no", "log_spcond_med", "log_turb_med", "log_da"]], on="site_no", how="left")
    mv_ols = {
        "split_half_productivity_plus_geo_on_diff_min_max": cross_river_ols_clustered(
            sub_sh_mv, "split_late_diff_min_max", ["split_early_swing", "lat", "alt_m", "log_da"], "huc2"
        ),
        "water_quality_spcond_turb_on_diff_min_max": cross_river_ols_clustered(
            sub_q, "s2_diff_min_max", ["log_spcond_med", "log_turb_med", "lat", "alt_m", "log_da"], "huc2"
        ),
        "water_quality_spcond_turb_on_do_max": cross_river_ols_clustered(
            sub_q, "s2_do_max", ["log_spcond_med", "log_turb_med", "lat", "alt_m", "log_da"], "huc2"
        ),
    }

    mechanism_out = {
        "split_half_oos_spearman": {
            "early_swing_vs_late_diff_min_max": spearman_blk(sub_sh, "split_early_swing", "split_late_diff_min_max"),
            "early_swing_vs_late_do_max": spearman_blk(sub_sh, "split_early_swing", "split_late_do_max"),
            "early_swing_vs_late_do_min": spearman_blk(sub_sh, "split_early_swing", "split_late_do_min"),
            "early_swing_vs_late_diff_max_sat": spearman_blk(sub_sh, "split_early_swing", "split_late_diff_max_sat"),
            "early_swing_vs_late_diff_min_sat": spearman_blk(sub_sh, "split_early_swing", "split_late_diff_min_sat"),
            "early_swing_vs_late_plunge": spearman_blk(sub_sh, "split_early_swing", "split_late_plunge"),
        },
        "split_half_ym_only_spearman": {
            "early_swing_vs_late_diff_min_max": spearman_blk(sub_sh_ym, "split_early_swing", "split_late_ym_diff_min_max"),
            "early_swing_vs_late_diff_min_sat": spearman_blk(sub_sh_ym, "split_early_swing", "split_late_ym_diff_min_sat"),
            "early_swing_vs_late_diff_max_sat": spearman_blk(sub_sh_ym, "split_early_swing", "split_late_ym_diff_max_sat"),
        },
        "same_period_spearman_reference": {
            "swing_vs_s2_diff_min_max": spearman_blk(sub_q, "warm_mean_swing", "s2_diff_min_max"),
            "spcond_vs_s2_diff_min_max": spearman_blk(sub_q, "warm_median_spcond", "s2_diff_min_max"),
            "turb_vs_s2_diff_min_max": spearman_blk(sub_q, "warm_median_turb", "s2_diff_min_max"),
            "turb_vs_s2_do_max": spearman_blk(sub_q, "warm_median_turb", "s2_do_max"),
            "turb_vs_s2_diff_max_sat": spearman_blk(sub_q, "warm_median_turb", "s2_diff_max_sat"),
            "lat_vs_s2_diff_min_max": spearman_blk(sub_q, "lat", "s2_diff_min_max"),
            "drain_area_vs_s2_diff_min_max": spearman_blk(sub_q, "drain_area_va", "s2_diff_min_max"),
        },
        "split_half_productivity_quartiles": prod_quartiles,
        "latitude_strata": lat_strata,
        "spcond_tertiles": spcond_strata,
        "turbidity_tertiles": turb_strata,
        "multivariate_ols": mv_ols,
    }

    # Secular 15-20 Year Trend Audit & CWA Confounding Test
    secular_out: dict = {"n_rivers_ge10warm_yrs": len(sub_sec)}
    if len(sub_sec) >= 15:
        sub_sec = sub_sec.copy()
        sub_sec["tr_dec_diff_min_max"] = sub_sec["tr_dec_do_min"] - sub_sec["tr_dec_do_max"]
        for c in ("temp_mean", "do_sat_alt", "do_max", "do_mean", "do_min", "swing", "plunge", "diff_min_sat", "hyp5_rate", "diff_min_max"):
            secular_out[f"ols_dec_{c}"] = spatial_inference_block(sub_sec, f"tr_dec_{c}", rng)
        for c in ("temp_mean", "do_min", "do_max", "swing", "plunge", "diff_min_sat"):
            secular_out[f"theilsen_dec_{c}"] = spatial_inference_block(sub_sec, f"tsen_dec_{c}", rng)
            if f"trq_dec_{c}" in sub_sec.columns:
                secular_out[f"qctrl_dec_{c}"] = spatial_inference_block(sub_sec, f"trq_dec_{c}", rng)

        # CWA Confounding Test: cross-river warming rate vs DO_min, DO_max, diurnal swing trends!
        secular_out["warming_rate_vs_trends_spearman"] = {
            "dT_vs_dDOmin": spearman_blk(sub_sec, "tr_dec_temp_mean", "tr_dec_do_min"),
            "dT_vs_dDOmax": spearman_blk(sub_sec, "tr_dec_temp_mean", "tr_dec_do_max"),
            "dT_vs_dSwing": spearman_blk(sub_sec, "tr_dec_temp_mean", "tr_dec_swing"),
            "dT_vs_dPlunge": spearman_blk(sub_sec, "tr_dec_temp_mean", "tr_dec_plunge"),
            "dT_vs_dBioDeficit_min": spearman_blk(sub_sec, "tr_dec_temp_mean", "tr_dec_diff_min_sat"),
        }
        # Stratify by faster-warming (> +0.25 C/dec) vs slower/cooling rivers
        fast_w = sub_sec[sub_sec["tr_dec_temp_mean"] >= 0.25]
        slow_w = sub_sec[sub_sec["tr_dec_temp_mean"] < 0.25]
        secular_out["stratified_by_warming_rate"] = {
            "fast_warming_ge025C_dec": {
                "n_rivers": len(fast_w),
                "tr_temp": spatial_inference_block(fast_w, "tr_dec_temp_mean", rng),
                "tr_do_min": spatial_inference_block(fast_w, "tr_dec_do_min", rng),
                "tr_do_max": spatial_inference_block(fast_w, "tr_dec_do_max", rng),
                "tr_swing": spatial_inference_block(fast_w, "tr_dec_swing", rng),
                "tr_diff_min_sat": spatial_inference_block(fast_w, "tr_dec_diff_min_sat", rng),
            },
            "slow_or_cooling_lt025C_dec": {
                "n_rivers": len(slow_w),
                "tr_temp": spatial_inference_block(slow_w, "tr_dec_temp_mean", rng),
                "tr_do_min": spatial_inference_block(slow_w, "tr_dec_do_min", rng),
                "tr_do_max": spatial_inference_block(slow_w, "tr_dec_do_max", rng),
                "tr_swing": spatial_inference_block(slow_w, "tr_dec_swing", rng),
                "tr_diff_min_sat": spatial_inference_block(slow_w, "tr_dec_diff_min_sat", rng),
            },
        }

    # Basin-level (HUC-2) summary table
    huc_rows = []
    for h, g in sub_q.groupby("huc2"):
        huc_rows.append(
            {
                "huc2": h,
                "n_rivers": len(g),
                "n_states": int(g["state"].nunique()),
                "mean_s2_dosat": round(float(g["s2_do_sat_alt"].mean()), 5),
                "mean_s2_domax": round(float(g["s2_do_max"].mean()), 5),
                "mean_s2_domean": round(float(g["s2_do_mean"].mean()), 5),
                "mean_s2_domin": round(float(g["s2_do_min"].mean()), 5),
                "mean_s2_diff_min_max": round(float(g["s2_diff_min_max"].mean()), 5),
                "mean_s2_diff_min_sat": round(float(g["s2_diff_min_sat"].mean()), 5),
                "pct_neg_diff_min_max": round(100.0 * float((g["s2_diff_min_max"] < 0).mean()), 1),
            }
        )

    full_results = {
        "census_overview": {
            "n_clean_rivers_total": len(rdf),
            "n_states_total": int(rdf["state"].nunique()),
            "n_huc2_total": int(rdf["huc2"].nunique()),
            "total_station_days": int(rdf["n_days"].sum()),
            "total_warm_station_days": int(rdf["n_warm_days"].sum()),
            "n_rivers_with_q_primary": len(sub_q),
            "n_states_with_q": int(sub_q["state"].nunique()),
            "n_huc2_with_q": int(sub_q["huc2"].nunique()),
            "n_rivers_exact_diurnal_T": len(sub_ex),
            "n_rivers_spcond": len(sub_sc),
            "n_rivers_turbidity": len(sub_tb),
            "n_rivers_ultra_strict": len(sub_us),
            "n_rivers_long_10yr": len(sub_10y),
            "n_rivers_nid_gt5km_ge500af": len(sub_nid_500),
            "n_rivers_nid_gt10km_ge5000af": len(sub_nid_5000),
            "n_rivers_nid_gt5km_any_dam": len(sub_nid_any),
            "n_rivers_dedup_2km": len(sub_dedup2km),
            "n_rivers_compound": len(sub_cmp),
            "n_rivers_split_half": len(sub_sh),
            "n_rivers_split_half_ym": len(sub_sh_ym),
            "n_rivers_secular_10yr": len(sub_sec),
        },
        "hypoxia_blindness_all_year": format_hyp_summary(aux["hypoxia_all_year"]),
        "hypoxia_blindness_warm_season": format_hyp_summary(aux["hypoxia_warm_season"]),
        "spec1_ym_fe_all_clean": spec1_out,
        "spec2_ym_fe_logQ_quad_primary": spec2_out,
        "spec3_exact_diurnal_solubility": spec3_out,
        "spec6_pooled_panel_ym_fe_logQ": aux["pooled_panel"],
        "robustness_suite": robustness,
        "compound_hot_x_dry": compound_out,
        "biophysical_mechanism": mechanism_out,
        "secular_trend_audit": secular_out,
        "huc2_basin_summary": huc_rows,
    }

    out_path = RES_DIR / "d4_econometric_hydrologic_results.json"
    out_path.write_text(json.dumps(full_results, indent=2), encoding="utf-8")
    print(f"\nDONE Step 5 in {time.monotonic()-t0:.1f}s -> {out_path}", flush=True)
    print(
        json.dumps(
            {
                "overview": full_results["census_overview"],
                "spec2_DOmin_minus_DOmax": full_results["spec2_ym_fe_logQ_quad_primary"]["diff_min_max"],
                "spec2_DOmin_minus_Henrys": full_results["spec2_ym_fe_logQ_quad_primary"]["diff_min_sat"],
                "spec2_DOmax_minus_Henrys": full_results["spec2_ym_fe_logQ_quad_primary"]["diff_max_sat"],
                "compound_int_DOmin": full_results["compound_hot_x_dry"]["effects"]["do_min"]["hot_x_dry_interaction"],
                "split_half_spearman": full_results["biophysical_mechanism"]["split_half_oos_spearman"]["early_swing_vs_late_diff_min_max"],
            },
            indent=2,
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()
