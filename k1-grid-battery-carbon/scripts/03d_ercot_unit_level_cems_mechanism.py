"""Step 03d (v6 Nature Energy): Direct unit-level EPA CEMS physical operating-envelope
verification of ERCOT coal and gas ramping across renewable-penetration regimes.

Queries Catalyst PUDL v2026.11.0 EPA CEMS unit-level hourly records strictly for
Texas ERCOT plants (`ba == 'ERCO'`, `2024-07-01..2026-09-30`) via DuckDB HTTP range
reads, defines each generator unit's empirical physical operating envelope (`LSL` = 5th
percentile positive load, `HSL` = 98th percentile positive load), and measures directly
at the individual smokestack unit level how online counts, mean utilization, baseload-
ceiling shares, and active part-loaded flexible ramping shares (`LSL < load < 0.95*HSL`
and `|dLoad| >= 5 MW`) shift across `<20%`, `20-40%`, `40-60%`, and `>60%` renewable
penetration (both unmatched and within exact `Season x Hour x Load-Quartile` cells).
"""

from __future__ import annotations

import time

import duckdb
import numpy as np
import pandas as pd
from econ_utils import PROC_DIR, RAW_EXT_DIR, RES_DIR, WS_DIR, save_json_lf

PUDL_CEMS_URL = (
    "https://s3.us-west-2.amazonaws.com/pudl.catalyst.coop/"
    "v2026.11.0/core_epacems__hourly_emissions.parquet"
)
SHORT_TON_TO_KG = 907.18474
CACHE_PQ = RAW_EXT_DIR / "erco_unit_level_cems_202407_202609.parquet"
TAB_DIR = WS_DIR / "tables"


def fetch_erco_unit_cems() -> pd.DataFrame:
    if CACHE_PQ.exists() and CACHE_PQ.stat().st_size > 2_000_000:
        df = pd.read_parquet(CACHE_PQ)
        print(f"  [CACHED] {CACHE_PQ.name}: {len(df):,} unit-hours ({df['unit_key'].nunique()} units)", flush=True)
        return df

    t0 = time.time()
    cw_pq = RAW_EXT_DIR / "plant_ba_crosswalk.parquet"
    con = duckdb.connect()
    con.execute("INSTALL httpfs; LOAD httpfs;")
    con.execute("SET threads = 4;")
    con.execute(
        f"CREATE TABLE erco_cw AS SELECT plant_id, fuel_class FROM read_parquet('{cw_pq.as_posix()}') "
        "WHERE ba = 'ERCO' AND fuel_class IN ('COAL', 'NGCC', 'NGCT');"
    )
    q = f"""
    SELECT
      CAST(COALESCE(r.plant_id_eia, r.plant_id_epa) AS VARCHAR) || '_' || CAST(r.emissions_unit_id_epa AS VARCHAR) AS unit_key,
      COALESCE(r.plant_id_eia, r.plant_id_epa) AS plant_id,
      c.fuel_class,
      r.operating_datetime_utc,
      COALESCE(r.gross_load_mw, 0.0) AS gross_mw,
      COALESCE(r.co2_mass_tons, 0.0) * {SHORT_TON_TO_KG} AS co2_kg
    FROM read_parquet('{PUDL_CEMS_URL}') r
    INNER JOIN erco_cw c
      ON COALESCE(r.plant_id_eia, r.plant_id_epa) = c.plant_id
    WHERE r.year >= 2024
      AND r.state = 'TX'
      AND r.operating_datetime_utc >= TIMESTAMP '2024-07-01 00:00:00'
      AND r.operating_datetime_utc <  TIMESTAMP '2026-10-01 00:00:00'
    ORDER BY unit_key, operating_datetime_utc
    """
    df = con.execute(q).df()
    df.to_parquet(CACHE_PQ, index=False)
    print(
        f"  [FETCHED] {CACHE_PQ.name}: {len(df):,} unit-hours across {df['unit_key'].nunique()} ERCOT units "
        f"in {time.time() - t0:.1f}s",
        flush=True,
    )
    return df


def main() -> int:
    print("=== STEP 03d: ERCOT UNIT-LEVEL EPA CEMS PHYSICAL RAMPING VERIFICATION ===", flush=True)
    df_u = fetch_erco_unit_cems()
    df_u["utc"] = pd.to_datetime(df_u["operating_datetime_utc"], utc=True)
    df_u = df_u.sort_values(["unit_key", "utc"]).reset_index(drop=True)

    # Empirical physical operating envelope per individual generator unit (positive operating hours)
    pos = df_u[df_u["gross_mw"] >= 10.0]
    env = (
        pos.groupby(["unit_key", "fuel_class"], as_index=False)
        .agg(
            n_pos_hrs=("gross_mw", "size"),
            lsl_mw=("gross_mw", lambda s: float(np.percentile(s, 5))),
            hsl_mw=("gross_mw", lambda s: float(np.percentile(s, 98))),
        )
    )
    env = env[(env["n_pos_hrs"] >= 200) & (env["hsl_mw"] >= 25.0)].copy()
    df_u = df_u.merge(env, on=["unit_key", "fuel_class"], how="inner")

    # Hour-over-hour physical ramp per individual unit (strictly consecutive 1-hour steps)
    prev_u = df_u["unit_key"].shift(1)
    prev_t = df_u["utc"].shift(1)
    consec = (df_u["unit_key"] == prev_u) & ((df_u["utc"] - prev_t) == pd.Timedelta(hours=1))
    df_u["d_mw"] = np.where(consec, df_u["gross_mw"] - df_u["gross_mw"].shift(1), np.nan)
    df_u["abs_dmw"] = df_u["d_mw"].abs()

    # Classify each unit-hour physical state
    df_u["is_online"] = (df_u["gross_mw"] >= 10.0).astype(np.int8)
    df_u["is_part_loaded"] = (
        (df_u["gross_mw"] > df_u["lsl_mw"]) & (df_u["gross_mw"] < 0.95 * df_u["hsl_mw"])
    ).astype(np.int8)
    df_u["is_active_ramp"] = (
        (df_u["is_part_loaded"] == 1) & (df_u["abs_dmw"] >= 5.0)
    ).astype(np.int8)
    df_u["is_at_ceiling"] = (df_u["gross_mw"] >= 0.95 * df_u["hsl_mw"]).astype(np.int8)
    df_u["util_of_hsl"] = np.where(df_u["is_online"] == 1, df_u["gross_mw"] / df_u["hsl_mw"], np.nan)

    # Aggregate unit states by UTC hour x fuel_class
    hr_f = (
        df_u.groupby(["utc", "fuel_class"], as_index=False)
        .agg(
            n_online=("is_online", "sum"),
            n_part_loaded=("is_part_loaded", "sum"),
            n_active_ramp=("is_active_ramp", "sum"),
            n_at_ceiling=("is_at_ceiling", "sum"),
            sum_gross_mw=("gross_mw", "sum"),
            sum_hsl_online=("hsl_mw", lambda s: float(s[df_u.loc[s.index, "is_online"] == 1].sum())),
            sum_abs_dmw=("abs_dmw", "sum"),
            mean_util_online=("util_of_hsl", "mean"),
        )
    )
    # Pivot wide by fuel class
    piv = hr_f.pivot(index="utc", columns="fuel_class")
    piv.columns = [f"{col}_{fc.lower()}" for col, fc in piv.columns]
    piv = piv.reset_index()

    # Join ERCOT hourly renewable penetration and load/season/hour from processed hourly panel
    h_erco = pd.read_parquet(PROC_DIR / "hourly_eia930_cems_bess_202407_202610.parquet")
    h_erco = h_erco[h_erco["ba"] == "ERCO"].copy()
    h_erco["utc"] = pd.to_datetime(h_erco["utc_start"], utc=True)
    h_erco = h_erco[(h_erco["utc"] >= "2024-07-01") & (h_erco["utc"] < "2026-10-01")].copy()
    h_erco["ren_mw"] = h_erco["solar"].fillna(0.0) + h_erco["wind"].fillna(0.0)
    h_erco["ren_share"] = h_erco["ren_mw"] / h_erco["demand"].clip(lower=1.0)
    h_erco["local_dt"] = h_erco["utc"].dt.tz_convert("America/Chicago")
    h_erco["month"] = h_erco["local_dt"].dt.month
    h_erco["season"] = h_erco["month"].map(
        {12: "DJF", 1: "DJF", 2: "DJF", 3: "MAM", 4: "MAM", 5: "MAM", 6: "JJA", 7: "JJA", 8: "JJA", 9: "SON", 10: "SON", 11: "SON"}
    )
    h_erco["local_hr"] = h_erco["local_dt"].dt.hour
    h_erco["load_q"] = pd.qcut(h_erco["demand"], 4, labels=["Q1", "Q2", "Q3", "Q4"]).astype(str)
    h_erco["cell"] = h_erco["season"] + "_" + h_erco["local_hr"].astype(str) + "_" + h_erco["load_q"]
    h_erco["ren_bin"] = pd.cut(
        h_erco["ren_share"],
        bins=[-1.0, 0.20, 0.40, 0.60, 2.0],
        labels=["<20%", "20-40%", "40-60%", ">60%"],
    ).astype(str)

    m = h_erco.merge(piv, on="utc", how="inner")
    m["date_str"] = m["utc"].dt.strftime("%Y-%m-%d")

    # Derived fleet-level physical ratios per hour
    for fc in ("coal", "ngcc", "ngct"):
        n_on = m[f"n_online_{fc}"].clip(lower=1.0)
        m[f"part_load_share_{fc}"] = 100.0 * m[f"n_part_loaded_{fc}"] / n_on
        m[f"active_ramp_share_{fc}"] = 100.0 * m[f"n_active_ramp_{fc}"] / n_on
        m[f"ceiling_share_{fc}"] = 100.0 * m[f"n_at_ceiling_{fc}"] / n_on
        m[f"util_pct_{fc}"] = 100.0 * m[f"mean_util_online_{fc}"]

    m["tot_abs_dmw_fossil"] = (
        m["sum_abs_dmw_coal"].fillna(0.0) + m["sum_abs_dmw_ngcc"].fillna(0.0) + m["sum_abs_dmw_ngct"].fillna(0.0)
    ).clip(lower=1.0)
    m["coal_share_of_abs_ramp_mw"] = 100.0 * m["sum_abs_dmw_coal"].fillna(0.0) / m["tot_abs_dmw_fossil"]
    m["ngct_share_of_abs_ramp_mw"] = 100.0 * m["sum_abs_dmw_ngct"].fillna(0.0) / m["tot_abs_dmw_fossil"]

    def _day_cluster_mean_se(df_sub: pd.DataFrame, col: str) -> tuple[float, float]:
        sub = df_sub[[col, "date_str"]].dropna()
        d_means = sub.groupby("date_str")[col].mean()
        mu = float(sub[col].mean())
        se = float(d_means.std(ddof=1) / np.sqrt(len(d_means))) if len(d_means) > 1 else 0.0
        return mu, se

    # 1. Unmatched 4-bin physical telemetry profile
    bins_out = []
    for b in ["<20%", "20-40%", "40-60%", ">60%"]:
        sub = m[m["ren_bin"] == b]
        row = {"ren_bin": b, "n_hours": len(sub), "n_days": int(sub["date_str"].nunique())}
        for metric in [
            "n_online_coal",
            "n_online_ngcc",
            "n_online_ngct",
            "util_pct_coal",
            "part_load_share_coal",
            "active_ramp_share_coal",
            "ceiling_share_coal",
            "active_ramp_share_ngct",
            "coal_share_of_abs_ramp_mw",
            "ngct_share_of_abs_ramp_mw",
            "sum_abs_dmw_coal",
            "sum_abs_dmw_ngct",
        ]:
            mu, se = _day_cluster_mean_se(sub, metric)
            row[metric] = mu
            row[f"{metric}_se"] = se
        bins_out.append(row)

    # 2. Exact common-support Season x Hour x Load-Quartile cell-matched comparison (<40% vs >60%)
    low_m = m[m["ren_share"] < 0.40].copy()
    hi_m = m[m["ren_share"] >= 0.60].copy()
    low_cells = set(low_m["cell"].value_counts()[lambda s: s >= 5].index)
    hi_cells = set(hi_m["cell"].value_counts()[lambda s: s >= 5].index)
    common_cells = sorted(low_cells & hi_cells)

    hi_cs = hi_m[hi_m["cell"].isin(common_cells)].copy()
    low_cs = low_m[low_m["cell"].isin(common_cells)].copy()
    hi_w = hi_cs["cell"].value_counts(normalize=True).to_dict()
    low_cnt = low_cs["cell"].value_counts().to_dict()
    low_cs["w_match"] = low_cs["cell"].map(lambda c: hi_w[c] / low_cnt[c])
    hi_cs["w_match"] = 1.0 / len(hi_cs)

    matched_metrics = {}
    for metric in [
        "n_online_coal",
        "n_online_ngct",
        "util_pct_coal",
        "part_load_share_coal",
        "active_ramp_share_coal",
        "ceiling_share_coal",
        "coal_share_of_abs_ramp_mw",
        "ngct_share_of_abs_ramp_mw",
    ]:
        # Weighted means & date-clustered SE via daily weighted sums
        def _w_mean_se(df_in: pd.DataFrame, col_name: str = metric) -> tuple[float, float]:
            sub = df_in[[col_name, "w_match", "date_str"]].dropna()
            w = sub["w_match"].to_numpy()
            w = w / w.sum()
            y = sub[col_name].to_numpy()
            mu = float(np.sum(w * y))
            # Cluster-robust variance of weighted mean across days
            df_tmp = pd.DataFrame({"d": sub["date_str"].to_numpy(), "r": w * (y - mu)})
            g = df_tmp.groupby("d")["r"].sum().to_numpy()
            G = len(g)
            se = float(np.sqrt((G / max(G - 1, 1)) * np.sum(g**2)))
            return mu, se

        mu_lo, se_lo = _w_mean_se(low_cs)
        mu_hi, se_hi = _w_mean_se(hi_cs)
        diff = mu_hi - mu_lo
        se_diff = float(np.sqrt(se_lo**2 + se_hi**2))
        matched_metrics[metric] = {
            "low_lt40_reweighted": mu_lo,
            "low_se": se_lo,
            "high_gt60": mu_hi,
            "high_se": se_hi,
            "diff_gt60_minus_lt40": diff,
            "diff_se": se_diff,
            "t_stat": float(diff / max(se_diff, 1e-9)),
        }

    # Unit inventory summary
    u_counts = env.groupby("fuel_class").agg(
        n_units=("unit_key", "size"),
        total_hsl_mw=("hsl_mw", "sum"),
        mean_lsl_pct_hsl=("lsl_mw", lambda s: float(100.0 * (s / env.loc[s.index, "hsl_mw"]).mean())),
    )
    inv_dict = {
        fc: {
            "n_units": int(u_counts.loc[fc, "n_units"]),
            "total_hsl_mw": float(u_counts.loc[fc, "total_hsl_mw"]),
            "mean_lsl_pct_hsl": float(u_counts.loc[fc, "mean_lsl_pct_hsl"]),
        }
        for fc in u_counts.index
    }

    out = {
        "window": {"utc_start": "2024-07-01", "utc_end": "2026-09-30", "n_hours_matched": len(m)},
        "ercot_unit_inventory": inv_dict,
        "ercot_sced_public_access_note": (
            "Direct unauthenticated HTTP requests to ercot.com 60-day SCED MIS JSON endpoints "
            "(reportTypeId 13052/12301/13060) return HTTP 403 anti-bot/WAF responses; unit-level "
            "physical verification is therefore conducted directly on public EPA CEMS smokestack "
            "unit telemetry (Catalyst PUDL v2026.11.0), reserving nodal SCED offer-curve replay for future work."
        ),
        "by_renewable_penetration_bin": bins_out,
        "matched_season_hour_loadq_lt40_vs_gt60": {
            "n_common_cells": len(common_cells),
            "n_hours_low": len(low_cs),
            "n_hours_high": len(hi_cs),
            "metrics": matched_metrics,
        },
    }

    sha = save_json_lf(RES_DIR / "03d_ercot_unit_level_cems_mechanism.json", out)
    TAB_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(bins_out).to_csv(TAB_DIR / "table_ercot_unit_cems_mechanism.csv", index=False)

    print("\n=== ERCOT UNIT-LEVEL CEMS PHYSICAL OPERATING ENVELOPE SUMMARY ===", flush=True)
    print("Inventory:", inv_dict, flush=True)
    for r in bins_out:
        print(
            f"  {r['ren_bin']:6s} (n={r['n_hours']:5d}h) | Online Coal={r['n_online_coal']:4.1f}, NGCT={r['n_online_ngct']:4.1f} | "
            f"Coal Util={r['util_pct_coal']:5.1f}%, Ceiling={r['ceiling_share_coal']:5.1f}%, "
            f"PartLoad={r['part_load_share_coal']:5.1f}%, ActiveRamp={r['active_ramp_share_coal']:5.1f}% | "
            f"Coal% of Fossil |dMW|={r['coal_share_of_abs_ramp_mw']:5.1f}%, NGCT%={r['ngct_share_of_abs_ramp_mw']:5.1f}%",
            flush=True,
        )
    print(f"\nExact Season x Hour x Load-Quartile Matched (<40% -> >60%, {len(common_cells)} cells):", flush=True)
    for k, v in matched_metrics.items():
        print(
            f"  {k:28s}: {v['low_lt40_reweighted']:6.2f} -> {v['high_gt60']:6.2f} "
            f"(diff {v['diff_gt60_minus_lt40']:+6.2f} +/- {v['diff_se']:.2f}, t={v['t_stat']:+.2f})",
            flush=True,
        )
    print(f"[DONE STEP 03d] Saved 03d_ercot_unit_level_cems_mechanism.json (SHA-256: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
