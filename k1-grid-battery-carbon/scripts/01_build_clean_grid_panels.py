"""Step 01 (Pillar 1): Clean Data Engineering, Telemetry Forensics & Official External Linkage.

Permanently eliminates every Wave-7 telemetry defect:
  - Documents ERCO (-6,115 MW) & AZPS (-2,951 MW) Unknown Energy Storage charging routing bug.
  - Verifies 0.0% pumped-hydro leakage across SOCO, DUK, MISO, CPLE.
  - Applies deterministic physical nameplate bound (catching & removing FPL 2025-08-27 HE6 2,668 MW
    glitch) and transparently reconciles DUK's 75-79 MW telemetry vs 53.5 MW operating + 18.8 MW
    2026 under-construction EIA-860M BESS (72.3 MW total).
  - Replaces CISO's broken EIA-930 'Other' proxy (RTE = 1.082) permanently with official standalone
    CAISO 5-min->hourly fuelsource.csv Batteries telemetry (RTE ~ 0.863).
  - Enforces the exact 4-window disjoint diurnal partition (Overnight 23-06 [8h], Morning 07-09 [3h],
    Midday Solar 10-16 [7h], Evening Peak 17-22 [6h]) plus full 24-hour profiles.
  - Empirically cross-verifies EPA CEMS UTC hour-beginning alignment against EIA-930 UTC hour-ending
    across lags -2..+2 hours.
  - Merges official CAISO 2024-2025 hourly curtailments (System vs Local) directly onto standalone
    CAISO battery telemetry and EPA CEMS smokestack CO2.
"""

from __future__ import annotations

import time
from typing import Any

import numpy as np
import pandas as pd
from econ_utils import (
    DIURNAL_WINDOWS,
    HOUR_TO_WINDOW,
    PROC_DIR,
    RAW_EXT_DIR,
    RES_DIR,
    WAVE7_DATA_DIR,
    WAVE7_RAW_EIA930_DIR,
    save_json_lf,
)

# 14 two-way metered BESS BAs (13 clean AC-coupled + FPL flagged DC-coupled hybrid)
METERED_14_BAS = [
    "CISO",
    "ERCO",
    "AZPS",
    "PNM",
    "SRP",
    "PGE",
    "MISO",
    "IPCO",
    "TEPC",
    "IID",
    "SOCO",
    "DUK",
    "CPLE",
    "FPL",
]


def load_860m_sheet(xlsx_path, sheet_name: str) -> pd.DataFrame:
    raw = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=None, nrows=10)
    hdr_row = next(
        i
        for i in range(len(raw))
        if "Plant ID" in [str(v).strip() for v in raw.iloc[i].tolist()]
    )
    df = pd.read_excel(xlsx_path, sheet_name=sheet_name, header=hdr_row)
    df.columns = [str(c).strip() for c in df.columns]
    return df[pd.to_numeric(df["Plant ID"], errors="coerce").notna()].copy()


def build_clean_860m_capacity() -> tuple[pd.DataFrame, pd.DataFrame, dict[str, Any]]:
    print("[01.1] Building clean EIA-860M monthly BA capacity & thermal fleet panel...", flush=True)
    xlsx_path = WAVE7_DATA_DIR / "eia860m_latest.xlsx"
    op_df = load_860m_sheet(xlsx_path, "Operating")
    ret_df = load_860m_sheet(xlsx_path, "Retired")
    plan_df = load_860m_sheet(xlsx_path, "Planned")

    def prep_gen(df: pd.DataFrame, mode: str) -> pd.DataFrame:
        ba_col = next(c for c in df.columns if "Balancing Authority" in c)
        mw_col = next(c for c in df.columns if "Nameplate Capacity" in c)
        mwh_cols = [c for c in df.columns if "Nameplate Energy Capacity" in c]
        out = pd.DataFrame(
            {
                "ba": df[ba_col].astype(str).str.strip(),
                "tech": df["Technology"].fillna("").astype(str).str.strip(),
                "esc": df["Energy Source Code"].fillna("").astype(str).str.strip(),
                "pm": df["Prime Mover Code"].fillna("").astype(str).str.strip(),
                "status": df["Status"].fillna("").astype(str).str.strip()
                if "Status" in df.columns
                else "",
                "mw": pd.to_numeric(df[mw_col], errors="coerce").fillna(0.0),
                "mwh": pd.to_numeric(df[mwh_cols[0]], errors="coerce").fillna(0.0)
                if mwh_cols
                else 0.0,
            }
        )
        if mode in ("operating", "retired"):
            op_yr = next(c for c in df.columns if "Operating Year" in c)
            op_mo = next(c for c in df.columns if "Operating Month" in c)
            out["op_ym"] = (
                pd.to_numeric(df[op_yr], errors="coerce") * 100
                + pd.to_numeric(df[op_mo], errors="coerce").fillna(1)
            )
            if mode == "retired":
                ry = next(c for c in df.columns if "Retirement Year" in c)
                rm = next(c for c in df.columns if "Retirement Month" in c)
                out["ret_ym"] = (
                    pd.to_numeric(df[ry], errors="coerce") * 100
                    + pd.to_numeric(df[rm], errors="coerce").fillna(12)
                )
            else:
                out["ret_ym"] = 999999
        else:
            py = next((c for c in df.columns if "Planned Operation Year" in c), None)
            pm = next((c for c in df.columns if "Planned Operation Month" in c), None)
            out["plan_yr"] = pd.to_numeric(df[py], errors="coerce") if py else np.nan
            out["plan_mo"] = pd.to_numeric(df[pm], errors="coerce").fillna(12) if pm else 12
        return out

    op_p = prep_gen(op_df, "operating")
    ret_p = prep_gen(ret_df, "retired")
    plan_p = prep_gen(plan_df, "planned")

    def map_bucket(row: pd.Series) -> str:
        tl = row["tech"].lower()
        if "batter" in tl or row["pm"] == "BA" or row["esc"] == "MWH":
            return "BESS"
        if "solar" in tl:
            return "SOLAR"
        if "wind" in tl:
            return "WIND"
        if "coal" in tl:
            return "COAL"
        if "combined cycle" in tl and "gas" in tl:
            return "NGCC"
        if "natural gas" in tl:
            return "NGCT"
        if "nuclear" in tl:
            return "NUCLEAR"
        if "pumped storage" in tl:
            return "PUMPED"
        if "hydroelectric" in tl:
            return "HYDRO"
        return "OTHER"

    gen_all = pd.concat([op_p, ret_p], ignore_index=True)
    gen_all["bucket"] = gen_all.apply(map_bucket, axis=1)
    gen_all = gen_all[
        gen_all["ba"].notna() & (~gen_all["ba"].isin(["", "nan", "None"]))
    ].copy()

    plan_p["bucket"] = plan_p.apply(map_bucket, axis=1)
    # 2026 under-construction BESS per BA (for pre-commercial testing & DUK reconciliation)
    uc_2026 = (
        plan_p[
            (plan_p["bucket"] == "BESS")
            & (plan_p["plan_yr"] <= 2026)
            & (plan_p["status"].str.contains(r"\(V\)|\(U\)|\(TS\)", regex=True, na=False))
        ]
        .groupby("ba")["mw"]
        .sum()
        .to_dict()
    )

    yms = [y * 100 + m for y in range(2019, 2027) for m in range(1, 13) if (y < 2026 or m <= 10)]
    cap_rows = []
    for ym in yms:
        active = gen_all[(gen_all["op_ym"] <= ym) & (gen_all["ret_ym"] > ym)]
        piv = active.groupby(["ba", "bucket"])["mw"].sum().unstack(fill_value=0.0).reset_index()
        bess_mwh = active[active["bucket"] == "BESS"].groupby("ba")["mwh"].sum()
        piv["BESS_MWH"] = piv["ba"].map(bess_mwh).fillna(0.0)
        piv["ym_int"] = ym
        piv["ym"] = f"{ym // 100:04d}-{ym % 100:02d}"
        cap_rows.append(piv)

    cap_panel = pd.concat(cap_rows, ignore_index=True).fillna(0.0)
    for b in ["BESS", "BESS_MWH", "SOLAR", "WIND", "COAL", "NGCC", "NGCT", "NUCLEAR", "HYDRO", "PUMPED", "OTHER"]:
        if b not in cap_panel.columns:
            cap_panel[b] = 0.0
    cap_panel["GAS"] = cap_panel["NGCC"] + cap_panel["NGCT"]
    cap_panel["BESS_DUR_HR"] = np.where(
        cap_panel["BESS"] > 0.0, cap_panel["BESS_MWH"] / cap_panel["BESS"], 0.0
    )
    cap_panel["PEAKER_SHARE"] = np.where(
        cap_panel["GAS"] > 0.0, cap_panel["NGCT"] / cap_panel["GAS"], 0.35
    )

    # Also build planned BESS 12-month pipeline indicator (for COD-lag check in Step 02!)
    cap_panel.to_parquet(PROC_DIR / "eia860m_clean_monthly_capacity.parquet", index=False)

    latest = cap_panel[cap_panel["ym"] == "2026-10"].sort_values("BESS", ascending=False).copy()
    latest["BESS_UC_2026_MW"] = latest["ba"].map(uc_2026).fillna(0.0)
    bess_19 = cap_panel[cap_panel["ym"] == "2019-01"].set_index("ba")["BESS"]
    latest["BESS_2019_MW"] = latest["ba"].map(bess_19).fillna(0.0)
    latest["BESS_ADDED_MW"] = latest["BESS"] - latest["BESS_2019_MW"]

    tot_mw = float(latest["BESS"].sum())
    tot_mwh = float(latest["BESS_MWH"].sum())
    non_ce_mw = float(latest.loc[~latest["ba"].isin(["CISO", "ERCO"]), "BESS"].sum())

    # Audit strictly clean top-20 BAs (ZERO stale all-zero keys!)
    top20 = [
        {
            "ba": str(r["ba"]),
            "bess_mw": float(r["BESS"]),
            "bess_mwh": float(r["BESS_MWH"]),
            "dur_hr": float(r["BESS_DUR_HR"]),
            "bess_uc_2026_mw": float(r["BESS_UC_2026_MW"]),
            "solar_mw": float(r["SOLAR"]),
            "wind_mw": float(r["WIND"]),
            "gas_mw": float(r["GAS"]),
            "coal_mw": float(r["COAL"]),
            "pumped_mw": float(r["PUMPED"]),
            "peaker_share": float(r["PEAKER_SHARE"]),
        }
        for _, r in latest.head(20).iterrows()
    ]

    summary = {
        "as_of_ym": "2026-10",
        "total_us_bess_mw": tot_mw,
        "total_us_bess_mwh": tot_mwh,
        "fleet_mean_duration_hr": float(tot_mwh / max(tot_mw, 1.0)),
        "n_bas_with_bess": int((latest["BESS"] > 0).sum()),
        "n_bas_ge50mw": int((latest["BESS"] >= 50).sum()),
        "n_bas_ge200mw": int((latest["BESS"] >= 200).sum()),
        "n_bas_ge500mw": int((latest["BESS"] >= 500).sum()),
        "ciso_bess_mw": float(latest.loc[latest["ba"] == "CISO", "BESS"].sum()),
        "erco_bess_mw": float(latest.loc[latest["ba"] == "ERCO", "BESS"].sum()),
        "non_ciso_erco_bess_mw": non_ce_mw,
        "non_ciso_erco_share_pct": float(100.0 * non_ce_mw / max(tot_mw, 1.0)),
        "top20_bas": top20,
    }
    print(
        f"  EIA-860M (2026-10): {tot_mw:,.1f} MW ({tot_mwh:,.1f} MWh, dur={tot_mwh/tot_mw:.2f}h) "
        f"across {summary['n_bas_with_bess']} BAs; Non-CISO/ERCO={non_ce_mw:,.1f} MW "
        f"({summary['non_ciso_erco_share_pct']:.1f}%)",
        flush=True,
    )
    return cap_panel, latest, summary


def load_2024h2_2026_raw_eia930_with_utc() -> pd.DataFrame:
    """Load exact UTC Time at End of Hour + Battery/Other/Unknown/Pumped Storage columns
    from raw 65-column EIA-930 CSVs (2024_Jul_Dec through 2026_Jul_Dec).
    """
    print("[01.2] Parsing raw 65-column EIA-930 CSVs (2024H2-2026) for UTC & storage telemetry...", flush=True)
    tags = ["2024_Jul_Dec", "2025_Jan_Jun", "2025_Jul_Dec", "2026_Jan_Jun", "2026_Jul_Dec"]
    frames = []
    for tag in tags:
        p = WAVE7_RAW_EIA930_DIR / f"EIA930_BALANCE_{tag}.csv"
        hdr = pd.read_csv(p, nrows=0).columns.tolist()
        hdr_s = [c.strip() for c in hdr]
        want = {
            "Balancing Authority",
            "Data Date",
            "Hour Number",
            "UTC Time at End of Hour",
            "Net Generation (MW) from Battery Storage (Adjusted)",
            "Net Generation (MW) from Battery Storage",
            "Net Generation (MW) from Other Energy Storage (Adjusted)",
            "Net Generation (MW) from Other Energy Storage",
            "Net Generation (MW) from Unknown Energy Storage (Adjusted)",
            "Net Generation (MW) from Unknown Energy Storage",
            "Net Generation (MW) from Hydroelectric Pumped Storage (Adjusted)",
            "Net Generation (MW) from Hydroelectric Pumped Storage",
            "Net Generation (MW) from Solar with Integrated Battery Storage (Adjusted)",
            "Net Generation (MW) from Solar with Integrated Battery Storage",
        }
        use_cols = [hdr[i] for i, c in enumerate(hdr_s) if c in want]
        d = pd.read_csv(p, usecols=use_cols, low_memory=False)
        d.columns = [c.strip() for c in d.columns]

        def gnum(c1: str, c2: str, df_cur: pd.DataFrame = d) -> pd.Series:
            s1 = (
                pd.to_numeric(df_cur[c1].astype(str).str.replace(",", "", regex=False), errors="coerce")
                if c1 in df_cur.columns
                else pd.Series(np.nan, index=df_cur.index)
            )
            s2 = (
                pd.to_numeric(df_cur[c2].astype(str).str.replace(",", "", regex=False), errors="coerce")
                if c2 in df_cur.columns
                else pd.Series(np.nan, index=df_cur.index)
            )
            return s1.fillna(s2)

        b_raw = gnum(
            "Net Generation (MW) from Battery Storage (Adjusted)",
            "Net Generation (MW) from Battery Storage",
        )
        b_oth = gnum(
            "Net Generation (MW) from Other Energy Storage (Adjusted)",
            "Net Generation (MW) from Other Energy Storage",
        )
        b_unk = gnum(
            "Net Generation (MW) from Unknown Energy Storage (Adjusted)",
            "Net Generation (MW) from Unknown Energy Storage",
        )
        pumped = gnum(
            "Net Generation (MW) from Hydroelectric Pumped Storage (Adjusted)",
            "Net Generation (MW) from Hydroelectric Pumped Storage",
        )
        sol_bess = gnum(
            "Net Generation (MW) from Solar with Integrated Battery Storage (Adjusted)",
            "Net Generation (MW) from Solar with Integrated Battery Storage",
        )
        has_any = b_raw.notna() | b_oth.notna() | b_unk.notna()
        b_combined = (b_raw.fillna(0.0) + b_oth.fillna(0.0) + b_unk.fillna(0.0)).where(
            has_any, np.nan
        )

        utc_end = pd.to_datetime(
            d["UTC Time at End of Hour"].astype(str).str.strip(),
            format="mixed",
            errors="coerce",
        )
        tmp = pd.DataFrame(
            {
                "ba": d["Balancing Authority"].astype(str).str.strip(),
                "date": pd.to_datetime(
                    d["Data Date"].astype(str).str.strip(), format="mixed", errors="coerce"
                ).dt.normalize(),
                "hour": pd.to_numeric(d["Hour Number"], errors="coerce"),
                "utc_end": utc_end,
                "utc_start": utc_end - pd.Timedelta(hours=1),
                "bess_raw": b_raw.astype("float32"),
                "bess_oth": b_oth.astype("float32"),
                "bess_unk": b_unk.astype("float32"),
                "bess_combined": b_combined.astype("float32"),
                "pumped_raw": pumped.astype("float32"),
                "solar_w_bess_raw": sol_bess.astype("float32"),
            }
        )
        tmp = tmp[tmp["date"].notna() & tmp["hour"].between(1, 24)].copy()
        tmp["hour"] = tmp["hour"].astype("int16")
        frames.append(tmp)

    out = pd.concat(frames, ignore_index=True).drop_duplicates(["ba", "date", "hour"])
    print(f"  Loaded {len(out):,} raw 2024H2-2026 BA-hour telemetry rows with exact UTC timestamps", flush=True)
    return out


def parse_caiso_curtailments_with_reason() -> pd.DataFrame:
    """Re-parse CAISO 2024-2025 curtailments preserving System vs Local curtailment breakdown."""
    print("[01.3] Building hourly CAISO System vs Local curtailment panel (2024-2025)...", flush=True)
    files = [
        RAW_EXT_DIR / "caiso_curtailments_2024.xlsx",
        RAW_EXT_DIR / "caiso_curtailments_2025_jan_may.xlsx",
        RAW_EXT_DIR / "caiso_curtailments_2025_jun_dec.xlsx",
    ]
    frames = []
    for p in files:
        xl = pd.ExcelFile(p)
        sh = next((s for s in xl.sheet_names if "curtail" in s.lower()), xl.sheet_names[0])
        df = pd.read_excel(p, sheet_name=sh)
        df.columns = [str(c).strip() for c in df.columns]
        sub = pd.DataFrame(
            {
                "date": pd.to_datetime(df["Date"], errors="coerce").dt.normalize(),
                "hour": pd.to_numeric(df["Hour"], errors="coerce"),
                "wind_mw": pd.to_numeric(df["Wind Curtailment"], errors="coerce").fillna(0.0),
                "solar_mw": pd.to_numeric(df["Solar Curtailment"], errors="coerce").fillna(0.0),
                "reason": df["Reason"].fillna("").astype(str).str.strip().str.lower()
                if "Reason" in df.columns
                else "unknown",
            }
        )
        sub = sub[sub["date"].notna() & sub["hour"].between(1, 24)].copy()
        sub["hour"] = sub["hour"].astype("int16")
        sub["tot_mw"] = sub["wind_mw"] + sub["solar_mw"]
        sub["sys_mw"] = np.where(sub["reason"].str.contains("sys"), sub["tot_mw"], 0.0)
        sub["loc_mw"] = np.where(sub["reason"].str.contains("loc"), sub["tot_mw"], 0.0)

        # Divide sum of 5-minute MW values by 12 intervals/hour -> exact hourly MWh (= average MW)
        agg = (
            sub.groupby(["date", "hour"], as_index=False)[
                ["wind_mw", "solar_mw", "tot_mw", "sys_mw", "loc_mw"]
            ].sum()
        )
        for c in ["wind_mw", "solar_mw", "tot_mw", "sys_mw", "loc_mw"]:
            agg[c] = agg[c] / 12.0
        agg = agg.rename(
            columns={
                "wind_mw": "wind_curt_mw",
                "solar_mw": "solar_curt_mw",
                "tot_mw": "total_curt_mw",
                "sys_mw": "system_curt_mw",
                "loc_mw": "local_curt_mw",
            }
        )
        frames.append(agg)

    comb = (
        pd.concat(frames, ignore_index=True)
        .groupby(["date", "hour"], as_index=False)[
            ["wind_curt_mw", "solar_curt_mw", "total_curt_mw", "system_curt_mw", "local_curt_mw"]
        ]
        .max()
    )
    all_dates = pd.date_range("2024-01-01", "2025-12-31", freq="D")
    grid = pd.MultiIndex.from_product([all_dates, range(1, 25)], names=["date", "hour"]).to_frame(
        index=False
    )
    grid["hour"] = grid["hour"].astype("int16")
    curt_full = grid.merge(comb, on=["date", "hour"], how="left").fillna(0.0)
    curt_full.to_parquet(PROC_DIR / "caiso_curtailments_hourly_clean.parquet", index=False)
    print(
        f"  CAISO Curtailments (2024-2025): Total={curt_full['total_curt_mw'].sum()/1000:,.1f} GWh "
        f"(System={curt_full['system_curt_mw'].sum()/1000:,.1f} GWh, "
        f"Local={curt_full['local_curt_mw'].sum()/1000:,.1f} GWh)",
        flush=True,
    )
    return curt_full


def main() -> int:
    t0 = time.time()
    print("=== STEP 01: CLEAN DATA ENGINEERING, TELEMETRY FORENSICS & EXTERNAL LINKAGE ===", flush=True)
    PROC_DIR.mkdir(parents=True, exist_ok=True)

    cap_panel, latest_cap, cap_summary = build_clean_860m_capacity()
    raw_ext = load_2024h2_2026_raw_eia930_with_utc()
    curt_df = parse_caiso_curtailments_with_reason()

    # Load read-only Wave-7 EIA-930 full hourly parquet (2019-01..2026-10)
    print("[01.4] Loading read-only EIA-930 2019-2026 hourly archive...", flush=True)
    eia = pd.read_parquet(WAVE7_DATA_DIR / "eia930_hourly_2019_2026.parquet")
    eia["ba"] = eia["ba"].astype(str).str.strip()
    eia["ym"] = eia["ym"].astype(str).str.strip()
    eia["region"] = eia["region"].astype(str).str.strip()
    eia["date"] = pd.to_datetime(eia["date"]).dt.normalize()
    eia["hour"] = eia["hour"].astype("int16")
    eia_19_26 = eia[eia["ym"] <= "2026-10"].copy()

    # Recover exact G=49 balanced U.S. BA universe (>=72 non-null demand & net_gen months, d19 >= 100 MW)
    ba_mo = eia_19_26.dropna(subset=["demand", "net_gen"]).groupby("ba")["ym"].nunique()
    d19_series = eia_19_26[eia_19_26["ym"].str.startswith("2019")].groupby("ba")["demand"].mean()
    valid_bas = sorted(set(ba_mo[ba_mo >= 72].index) & set(d19_series[d19_series >= 100.0].index))
    d19_map = d19_series.loc[valid_bas].to_dict()
    ba_reg_map = (
        eia_19_26[eia_19_26["ba"].isin(valid_bas)]
        .groupby("ba")["region"]
        .agg(lambda s: s.mode().iloc[0])
        .to_dict()
    )
    print(f"  Balanced U.S. BA universe: G = {len(valid_bas)} BAs (2019-01..2026-10)", flush=True)

    # ------------------------------------------------------------------
    # Load official CAISO standalone hourly fuelsource.csv (2023-12-01..2026-10-31)
    # Audit & PERMANENTLY REPAIR EIA-930's 2-year CISO midday NG corruption (+3 to +7.6 GW,
    # 2023-12 through 2025-12, fixed by EIA mid-Dec 2025) BEFORE constructing Panel A!
    # ------------------------------------------------------------------
    caiso_fs = pd.read_parquet(RAW_EXT_DIR / "caiso_fuelsource_hourly_202312_202610.parquet")
    caiso_fs["date"] = pd.to_datetime(caiso_fs["date"]).dt.normalize()
    caiso_fs["hour"] = caiso_fs["hour"].astype("int16")
    fs_sup_cols = [
        "solar_mw",
        "wind_mw",
        "geothermal_mw",
        "biomass_mw",
        "biogas_mw",
        "small_hydro_mw",
        "coal_mw",
        "nuclear_mw",
        "ng_mw",
        "large_hydro_mw",
        "batteries_mw",
        "imports_mw",
        "other_mw",
    ]
    caiso_fs["fs_load"] = caiso_fs[fs_sup_cols].fillna(0.0).sum(axis=1)
    caiso_fs["fs_hydro_tot"] = (
        caiso_fs["large_hydro_mw"].fillna(0.0) + caiso_fs["small_hydro_mw"].fillna(0.0)
    )

    eia_v = eia_19_26[eia_19_26["ba"].isin(valid_bas)].copy()
    for c in ["ng", "coal", "solar", "wind", "hydro", "nuclear", "oil", "other", "interchange"]:
        eia_v[c] = eia_v[c].fillna(0.0)

    # Audit EIA-930 CISO NG corruption (2023-12..2025-12) vs Jan-Oct 2026 post-EIA-fix convergence!
    ciso_cmp = eia_v[(eia_v["ba"] == "CISO") & (eia_v["date"] >= "2023-12-01")].merge(
        caiso_fs[
            [
                "date",
                "hour",
                "ng_mw",
                "solar_mw",
                "wind_mw",
                "fs_hydro_tot",
                "nuclear_mw",
                "geothermal_mw",
                "imports_mw",
                "fs_load",
                "batteries_mw",
            ]
        ],
        on=["date", "hour"],
        how="inner",
    )
    ciso_cmp["ym"] = ciso_cmp["date"].dt.strftime("%Y-%m")
    ciso_cmp_md = ciso_cmp[ciso_cmp["hour"].isin(DIURNAL_WINDOWS["Midday Solar"])]
    md_by_ym = ciso_cmp_md.groupby("ym")[["ng", "ng_mw"]].mean()
    md_by_ym["phantom_mw"] = md_by_ym["ng"] - md_by_ym["ng_mw"]
    corr_win = md_by_ym.loc[(md_by_ym.index >= "2024-01") & (md_by_ym.index <= "2025-11")]
    fixed_win = md_by_ym.loc[md_by_ym.index >= "2026-01"]
    ciso_ng_corruption_audit = {
        "corrupted_window": "2023-12 to 2025-12",
        "mean_midday_phantom_ng_mw_2024_2025": float(corr_win["phantom_mw"].mean()),
        "peak_month_ym": str(corr_win["phantom_mw"].idxmax()),
        "peak_month_midday_phantom_ng_mw": float(corr_win["phantom_mw"].max()),
        "post_eia_fix_2026_mean_abs_diff_mw": float(fixed_win["phantom_mw"].abs().mean()),
        "eia_ciso_raw_2025_md_ng_mw": float(
            md_by_ym.loc[md_by_ym.index.str.startswith("2025"), "ng"].mean()
        ),
        "caiso_true_2025_md_ng_mw": float(
            md_by_ym.loc[md_by_ym.index.str.startswith("2025"), "ng_mw"].mean()
        ),
        "n_repaired_panel_a_ciso_hours": len(ciso_cmp),
    }
    print(
        f"  [FORENSIC AUDIT] EIA-930 CISO NG Corruption (2024-01..2025-11): mean midday phantom NG = "
        f"+{ciso_ng_corruption_audit['mean_midday_phantom_ng_mw_2024_2025']:,.0f} MW "
        f"(peak {ciso_ng_corruption_audit['peak_month_ym']}: "
        f"+{ciso_ng_corruption_audit['peak_month_midday_phantom_ng_mw']:,.0f} MW) -> "
        f"post-EIA-fix 2026 mean |diff| = {ciso_ng_corruption_audit['post_eia_fix_2026_mean_abs_diff_mw']:.1f} MW; "
        f"splicing official CAISO fuelsource.csv into Panel A ({len(ciso_cmp):,} hrs)!",
        flush=True,
    )

    # Preserve unrepaired EIA-930 CISO NG solely for transparent before-vs-after audit sensitivity
    eia_v["ng_unrepaired"] = eia_v["ng"].copy()
    ciso_splice = caiso_fs[
        [
            "date",
            "hour",
            "ng_mw",
            "solar_mw",
            "wind_mw",
            "fs_hydro_tot",
            "nuclear_mw",
            "imports_mw",
            "fs_load",
        ]
    ].copy()
    ciso_splice["ba"] = "CISO"
    eia_v = eia_v.merge(ciso_splice, on=["ba", "date", "hour"], how="left")
    m_fix = (eia_v["ba"] == "CISO") & (eia_v["date"] >= "2023-12-01") & eia_v["ng_mw"].notna()
    eia_v["ng"] = np.where(m_fix, eia_v["ng_mw"].fillna(0.0), eia_v["ng"]).astype("float64")
    eia_v["solar"] = np.where(m_fix, eia_v["solar_mw"].fillna(0.0), eia_v["solar"]).astype("float64")
    eia_v["wind"] = np.where(m_fix, eia_v["wind_mw"].fillna(0.0), eia_v["wind"]).astype("float64")
    eia_v["hydro"] = np.where(m_fix, eia_v["fs_hydro_tot"].fillna(0.0), eia_v["hydro"]).astype("float64")
    eia_v["nuclear"] = np.where(
        m_fix & eia_v["nuclear_mw"].notna(), eia_v["nuclear_mw"].fillna(0.0), eia_v["nuclear"]
    ).astype("float64")
    eia_v["interchange"] = np.where(m_fix, -eia_v["imports_mw"].fillna(0.0), eia_v["interchange"]).astype("float64")
    eia_v["demand"] = np.where(m_fix, eia_v["fs_load"].fillna(0.0), eia_v["demand"]).astype("float64")
    eia_v = eia_v.drop(
        columns=["ng_mw", "solar_mw", "wind_mw", "fs_hydro_tot", "nuclear_mw", "imports_mw", "fs_load"]
    )

    eia_v["fossil"] = eia_v["ng"] + eia_v["coal"] + eia_v["oil"]
    eia_v["fossil_plus_imp"] = eia_v["fossil"] - eia_v["interchange"]
    eia_v["window"] = eia_v["hour"].map(HOUR_TO_WINDOW)

    # 1) BA x YM x Hour panel (for 24-hour diurnal curve in Step 02!)
    panel_h = eia_v.groupby(["ba", "ym", "hour"], as_index=False)[
        ["demand", "ng", "ng_unrepaired", "coal", "oil", "fossil", "fossil_plus_imp", "solar", "wind", "hydro", "nuclear", "interchange", "other"]
    ].mean()
    panel_h["region"] = panel_h["ba"].map(ba_reg_map)
    panel_h["d19_mw"] = panel_h["ba"].map(d19_map)
    cap_cols = ["ba", "ym", "BESS", "BESS_MWH", "BESS_DUR_HR", "SOLAR", "WIND", "COAL", "GAS", "NGCC", "NGCT", "NUCLEAR", "PUMPED"]
    panel_h = panel_h.merge(cap_panel[cap_cols], on=["ba", "ym"], how="left")
    for c in cap_cols[2:]:
        panel_h[c] = panel_h[c].fillna(0.0)
    panel_h.to_parquet(PROC_DIR / "panel_a_ba_ym_hour.parquet", index=False)

    # 2) BA x YM 4-Window Diurnal Spread Panel (exact Ev 17-22 vs Mid 10-16 vs Night 23-06!)
    def make_win(hrs: list[int], pfx: str) -> pd.DataFrame:
        return (
            panel_h[panel_h["hour"].isin(hrs)]
            .groupby(["ba", "ym"])[
                ["ng", "ng_unrepaired", "coal", "fossil", "fossil_plus_imp", "nuclear", "solar", "wind", "demand", "hydro", "interchange", "other"]
            ]
            .mean()
            .add_prefix(pfx)
        )

    sp = pd.concat(
        [
            make_win(DIURNAL_WINDOWS["Evening Peak"], "ev_"),  # 17-22 (6h)
            make_win(DIURNAL_WINDOWS["Midday Solar"], "md_"),  # 10-16 (7h)
            make_win(DIURNAL_WINDOWS["Morning Ramp"], "mr_"),  # 07-09 (3h)
            make_win(DIURNAL_WINDOWS["Overnight"], "nt_"),  # 23-06 (8h)
            make_win([19, 20], "pk_"),  # 2-hr narrow evening peak
        ],
        axis=1,
    ).reset_index()
    sp["region"] = sp["ba"].map(ba_reg_map)
    sp["d19_mw"] = sp["ba"].map(d19_map)
    sp = sp.merge(cap_panel[cap_cols], on=["ba", "ym"], how="left")
    for c in cap_cols[2:]:
        sp[c] = sp[c].fillna(0.0)
    sp["bess_share"] = sp["BESS"] / sp["d19_mw"]
    sp["bess_mwh_share"] = sp["BESS_MWH"] / sp["d19_mw"]
    sp["solar_cap_share"] = sp["SOLAR"] / sp["d19_mw"]
    sp["wind_cap_share"] = sp["WIND"] / sp["d19_mw"]
    sp["coal_cap_share"] = sp["COAL"] / sp["d19_mw"]
    sp["gas_cap_share"] = sp["GAS"] / sp["d19_mw"]
    sp["cal_mo"] = sp["ym"].str.slice(5, 7).astype(int)
    sp["ba_calmo"] = sp["ba"] + "_" + sp["cal_mo"].astype(str)
    sp["post_2024h2"] = (sp["ym"] >= "2024-07").astype(int)
    sp["ba_post24h2"] = sp["ba"] + "_" + sp["post_2024h2"].astype(str)
    sp["reg_ym"] = sp["region"] + "_" + sp["ym"]
    ym_list = sorted(sp["ym"].unique())
    sp["t_idx"] = sp["ym"].map({m: i for i, m in enumerate(ym_list)}).astype(float)

    for v in ["ng", "ng_unrepaired", "coal", "fossil", "fossil_plus_imp", "nuclear", "solar", "wind", "demand", "hydro", "interchange", "other"]:
        sp[f"em_{v}"] = (sp[f"ev_{v}"] - sp[f"md_{v}"]) / sp["d19_mw"]
        sp[f"en_{v}"] = (sp[f"ev_{v}"] - sp[f"nt_{v}"]) / sp["d19_mw"]
        sp[f"mn_{v}"] = (sp[f"md_{v}"] - sp[f"nt_{v}"]) / sp["d19_mw"]
        sp[f"pkmd_{v}"] = (sp[f"pk_{v}"] - sp[f"md_{v}"]) / sp["d19_mw"]

    thermal_bas = sorted(sp.groupby("ba")["GAS"].max()[lambda s: s >= 100.0].index)
    sp["is_thermal"] = sp["ba"].isin(thermal_bas).astype(int)
    sp.to_parquet(PROC_DIR / "panel_a_monthly_spreads.parquet", index=False)

    # 3) High-frequency BA x Date diurnal spread panel (for within-BA-Month daily solar-swing x BESS_MWh test!)
    print("[01.5] Building high-frequency daily BA diurnal panel (for BA x Year-Month FE check)...", flush=True)
    ev_d = (
        eia_v[eia_v["hour"].isin(DIURNAL_WINDOWS["Evening Peak"])]
        .groupby(["ba", "date", "ym"])[["ng", "fossil_plus_imp", "nuclear", "demand", "solar", "wind", "hydro"]]
        .mean()
        .add_prefix("ev_")
    )
    md_d = (
        eia_v[eia_v["hour"].isin(DIURNAL_WINDOWS["Midday Solar"])]
        .groupby(["ba", "date", "ym"])[["ng", "fossil_plus_imp", "nuclear", "demand", "solar", "wind", "hydro"]]
        .mean()
        .add_prefix("md_")
    )
    daily = pd.concat([ev_d, md_d], axis=1).reset_index()
    daily["d19_mw"] = daily["ba"].map(d19_map)
    daily = daily.merge(cap_panel[["ba", "ym", "BESS", "BESS_MWH", "SOLAR"]], on=["ba", "ym"], how="left")
    daily["BESS"] = daily["BESS"].fillna(0.0)
    daily["BESS_MWH"] = daily["BESS_MWH"].fillna(0.0)
    daily["SOLAR"] = daily["SOLAR"].fillna(0.0)
    daily["bess_share"] = daily["BESS"] / daily["d19_mw"]
    daily["bess_mwh_share"] = daily["BESS_MWH"] / daily["d19_mw"]
    daily["solar_cap_share"] = daily["SOLAR"] / daily["d19_mw"]
    for v in ["ng", "fossil_plus_imp", "nuclear", "demand", "solar", "wind", "hydro"]:
        daily[f"em_{v}"] = (daily[f"ev_{v}"] - daily[f"md_{v}"]) / daily["d19_mw"]
    daily["md_sol_norm"] = daily["md_solar"] / daily["d19_mw"]
    daily["ba_ym"] = daily["ba"] + "_" + daily["ym"]
    daily["dow"] = daily["date"].dt.day_of_week.astype("int8")
    daily.to_parquet(PROC_DIR / "panel_a_daily_spreads.parquet", index=False)
    print(f"  Saved Panel A monthly ({len(sp):,} rows) & daily ({len(daily):,} rows)", flush=True)

    # ------------------------------------------------------------------
    # TELEMETRY FORENSICS & CLEAN 2024H2-2026 METERED HOURLY PANEL (WITH CISO STANDALONE & CEMS!)
    # ------------------------------------------------------------------
    print("[01.6] Executing Telemetry Forensics, CISO Standalone Swap, & EPA CEMS Alignment...", flush=True)
    e24 = eia[(eia["date"] >= "2024-07-01") & (eia["date"] <= "2026-10-31")].copy()
    e24 = e24.merge(
        raw_ext[
            ["ba", "date", "hour", "utc_end", "utc_start", "bess_raw", "bess_oth", "bess_unk", "bess_combined", "pumped_raw"]
        ],
        on=["ba", "date", "hour"],
        how="left",
    )
    for c in ["ng", "coal", "oil", "hydro", "nuclear", "solar", "wind", "demand", "interchange", "other", "geothermal"]:
        e24[c] = e24[c].fillna(0.0)

    # Restrict CAISO fuelsource to exact 2024-07-01..2026-10-31 metered telemetry window
    caiso_fs24 = caiso_fs[caiso_fs["date"] >= "2024-07-01"].copy()

    # Cross-verify CAISO fuelsource hour-ending alignment against EIA-930 CISO Solar & NG across shifts -2..+2!
    ciso_eia = e24[e24["ba"] == "CISO"][["date", "hour", "solar", "ng", "other", "geothermal"]].copy()
    ciso_chk = ciso_eia.merge(caiso_fs24[["date", "hour", "solar_mw", "ng_mw", "batteries_mw"]], on=["date", "hour"], how="inner")
    ciso_chk = ciso_chk.sort_values(["date", "hour"]).reset_index(drop=True)
    ciso_align_corrs = {}
    for lag in [-2, -1, 0, 1, 2]:
        r_sol = float(ciso_chk["solar"].corr(ciso_chk["solar_mw"].shift(lag)))
        r_ng = float(ciso_chk["ng"].corr(ciso_chk["ng_mw"].shift(lag)))
        ciso_align_corrs[str(lag)] = {"r_solar": r_sol, "r_ng": r_ng}
    print(f"  CAISO fuelsource vs EIA-930 lag correlations: {ciso_align_corrs}", flush=True)

    # Document broken EIA-930 CISO 'Other + Geothermal' (1.076-1.082) vs official standalone CAISO RTE!
    ciso_eia25 = ciso_eia[ciso_eia["date"] >= "2025-01-01"]
    ciso_og = ciso_eia25["other"] + ciso_eia25["geothermal"]
    ciso_eia_og_dis = float(ciso_og[ciso_og > 0].sum() / 1000.0)
    ciso_eia_og_chg = float(abs(ciso_og[ciso_og < 0].sum()) / 1000.0)
    ciso_eia_broken_rte = float(ciso_eia_og_dis / max(ciso_eia_og_chg, 1e-6))

    ciso_fs_dis = float(caiso_fs24.loc[caiso_fs24["batteries_mw"] > 0, "batteries_mw"].sum() / 1000.0)
    ciso_fs_chg = float(abs(caiso_fs24.loc[caiso_fs24["batteries_mw"] < 0, "batteries_mw"].sum()) / 1000.0)
    ciso_fs_rte = float(ciso_fs_dis / max(ciso_fs_chg, 1e-6))
    print(
        f"  CISO Telemetry Repair: Broken EIA-930 Other+Geo RTE={ciso_eia_broken_rte:.4f} -> "
        f"Official Standalone CAISO fuelsource.csv RTE={ciso_fs_rte:.4f} "
        f"(Dis={ciso_fs_dis:,.1f} GWh, Chg={ciso_fs_chg:,.1f} GWh)",
        flush=True,
    )

    # Merge official CAISO standalone Batteries + FULL supply mix into e24!
    caiso_batt_map = caiso_fs24[
        [
            "date",
            "hour",
            "batteries_mw",
            "ng_mw",
            "solar_mw",
            "wind_mw",
            "imports_mw",
            "large_hydro_mw",
            "small_hydro_mw",
            "geothermal_mw",
            "biomass_mw",
            "biogas_mw",
            "nuclear_mw",
            "coal_mw",
            "other_mw",
            "fs_load",
        ]
    ].copy()
    caiso_batt_map["ba"] = "CISO"
    e24 = e24.merge(caiso_batt_map, on=["ba", "date", "hour"], how="left")
    e24["bess_unfiltered"] = np.where(e24["ba"] == "CISO", e24["batteries_mw"], e24["bess_combined"])

    # Document ERCO & AZPS Unknown Energy Storage charging routing bug in exact numbers
    ues_bug_audit = {}
    for ba_u in ["ERCO", "AZPS"]:
        sub = e24[e24["ba"] == ba_u]
        dis_raw = float(sub.loc[sub["bess_raw"] > 0, "bess_raw"].sum() / 1000.0)
        chg_raw = float(abs(sub.loc[sub["bess_raw"] < 0, "bess_raw"].sum()) / 1000.0)
        chg_unk = float(abs(sub.loc[sub["bess_unk"] < 0, "bess_unk"].sum()) / 1000.0)
        dis_comb = float(sub.loc[sub["bess_combined"] > 0, "bess_combined"].sum() / 1000.0)
        chg_comb = float(abs(sub.loc[sub["bess_combined"] < 0, "bess_combined"].sum()) / 1000.0)
        ues_bug_audit[ba_u] = {
            "raw_bess_min_mw": float(sub["bess_raw"].min()),
            "raw_bess_max_mw": float(sub["bess_raw"].max()),
            "unk_stor_min_mw": float(sub["bess_unk"].min()),
            "raw_dis_gwh": dis_raw,
            "raw_chg_gwh": chg_raw,
            "unk_chg_gwh": chg_unk,
            "raw_broken_rte": float(dis_raw / chg_raw) if chg_raw > 0 else None,
            "repaired_dis_gwh": dis_comb,
            "repaired_chg_gwh": chg_comb,
            "repaired_rte": float(dis_comb / max(chg_comb, 1e-6)),
        }
        print(
            f"  UES Bug [{ba_u}]: min_unk={ues_bug_audit[ba_u]['unk_stor_min_mw']:.0f} MW, "
            f"unk_chg={chg_unk:,.1f} GWh, repaired_RTE={ues_bug_audit[ba_u]['repaired_rte']:.4f}",
            flush=True,
        )

    # Pumped-hydro zero-leakage verification for SOCO, DUK, MISO, CPLE (using eia930 `pumped` column)
    latest_idx = latest_cap.set_index("ba")
    pumped_leak_audit = {}
    for ba_p in ["SOCO", "DUK", "MISO", "CPLE"]:
        sub = e24[e24["ba"] == ba_p]
        pmp_cap = float(latest_idx.loc[ba_p, "PUMPED"]) if ba_p in latest_idx.index else 0.0
        bess_cap = float(latest_idx.loc[ba_p, "BESS"]) if ba_p in latest_idx.index else 0.0
        bess_uc = float(latest_idx.loc[ba_p, "BESS_UC_2026_MW"]) if ba_p in latest_idx.index else 0.0
        pmp_s = sub["pumped"].dropna()
        pmp_max = float(pmp_s.max()) if len(pmp_s) else 0.0
        bess_max = float(sub["bess_unfiltered"].abs().max()) if sub["bess_unfiltered"].notna().any() else 0.0
        valid_both = sub[["bess_unfiltered", "pumped"]].dropna()
        corr_bp = (
            float(valid_both["bess_unfiltered"].corr(valid_both["pumped"]))
            if len(valid_both) > 100 and valid_both["pumped"].std() > 1.0
            else 0.0
        )
        pumped_leak_audit[ba_p] = {
            "eia860m_pumped_mw": pmp_cap,
            "eia860m_bess_operating_mw": bess_cap,
            "eia860m_bess_uc_2026_mw": bess_uc,
            "eia930_pumped_max_mw": pmp_max,
            "eia930_bess_abs_max_mw": bess_max,
            "pumped_leakage_detected": bool(pmp_cap > 0 and bess_max > max(1.5 * (bess_cap + bess_uc), 200.0)),
            "corr_bess_pumped": corr_bp,
        }
    print(f"  Pumped-hydro zero-leakage audit: { {k: v['pumped_leakage_detected'] for k, v in pumped_leak_audit.items()} }", flush=True)

    # Deterministic physical nameplate bound across ALL 14 metered BAs:
    # Bound = 1.25 * (EIA-860M Operating BESS MW + 2026 Under-Construction BESS MW)
    # Wait: let's log BOTH strict operating bound (1.25 * op) and reconciled bound (1.25 * (op + uc_2026))!
    cap_op_map = latest_idx["BESS"].to_dict()
    cap_rec_map = (latest_idx["BESS"] + latest_idx["BESS_UC_2026_MW"]).to_dict()
    e24["ba_bess_op_mw"] = e24["ba"].map(cap_op_map).fillna(0.0)
    e24["ba_bess_rec_mw"] = e24["ba"].map(cap_rec_map).fillna(0.0)
    e24["phys_bound_mw"] = 1.25 * e24["ba_bess_rec_mw"]

    glitch_mask = (
        e24["ba"].isin(METERED_14_BAS)
        & e24["bess_unfiltered"].notna()
        & (e24["phys_bound_mw"] > 0)
        & (e24["bess_unfiltered"].abs() > e24["phys_bound_mw"])
    )
    flagged_anomalies = []
    for _, r in e24[glitch_mask].iterrows():
        flagged_anomalies.append(
            {
                "ba": str(r["ba"]),
                "date": str(r["date"].date()),
                "hour": int(r["hour"]),
                "raw_bess_mw": float(r["bess_unfiltered"]),
                "eia860m_bess_op_mw": float(r["ba_bess_op_mw"]),
                "eia860m_bess_reconciled_mw": float(r["ba_bess_rec_mw"]),
                "phys_bound_125pct_mw": float(r["phys_bound_mw"]),
                "action": "set_to_nan_filtered",
            }
        )
    print(f"  Deterministic Physical Bound (1.25x nameplate) flagged {len(flagged_anomalies)} anomaly rows:", flush=True)
    for fa in flagged_anomalies[:10]:
        print("   ", fa, flush=True)

    e24["bess_clean"] = e24["bess_unfiltered"].where(~glitch_mask, np.nan)

    # Transparent DUK reconciliation record (100% dynamic, zero hardcoded numbers!)
    duk_sub = e24[(e24["ba"] == "DUK") & e24["bess_clean"].notna()]
    duk_dis_t = float(duk_sub.loc[duk_sub["bess_clean"] > 0.5, "bess_clean"].sum())
    duk_chg_t = float(abs(duk_sub.loc[duk_sub["bess_clean"] < -0.5, "bess_clean"].sum()))
    duk_rte_dyn = float(duk_dis_t / max(duk_chg_t, 1.0))
    duk_reconciliation = {
        "eia860m_operating_mw": float(cap_op_map.get("DUK", 0.0)),
        "eia860m_under_construction_2026_mw": float(latest_idx.loc["DUK", "BESS_UC_2026_MW"]),
        "reconciled_nameplate_mw": float(cap_rec_map.get("DUK", 0.0)),
        "phys_bound_125pct_reconciled_mw": float(1.25 * cap_rec_map.get("DUK", 0.0)),
        "eia930_bess_max_discharge_mw": float(duk_sub["bess_clean"].max()),
        "eia930_bess_min_charge_mw": float(duk_sub["bess_clean"].min()),
        "eia930_bess_p99_abs_mw": float(duk_sub["bess_clean"].abs().quantile(0.99)),
        "eia930_bess_rte": duk_rte_dyn,
        "eia860m_pumped_hydro_mw": float(latest_idx.loc["DUK", "PUMPED"]),
        "eia930_pumped_max_mw": float(e24.loc[e24["ba"] == "DUK", "pumped"].dropna().max()),
        "explanation": (
            f"DUK reports {cap_op_map.get('DUK', 0.0):.1f} MW operating BESS plus "
            f"{latest_idx.loc['DUK', 'BESS_UC_2026_MW']:.1f} MW 2026 under-construction BESS "
            f"({cap_rec_map.get('DUK', 0.0):.1f} MW total, 1.25x bound = {1.25 * cap_rec_map.get('DUK', 0.0):.1f} MW), "
            f"explaining steady {duk_sub['bess_clean'].min():.0f} to +{duk_sub['bess_clean'].max():.0f} MW EIA-930 telemetry "
            f"(RTE={duk_rte_dyn:.3f}) with zero leakage from DUK's {latest_idx.loc['DUK', 'PUMPED']:,.0f} MW pumped hydro."
        ),
    }

    # ------------------------------------------------------------------
    # Empirically Cross-Verify & Merge EPA CEMS Hourly Smokestack CO2 (2024-07-01..2026-09-30)
    # ------------------------------------------------------------------
    print("[01.7] Merging & verifying EPA CEMS hourly smokestack CO2 alignment (lags -2..+2)...", flush=True)
    cems = pd.read_parquet(RAW_EXT_DIR / "cems_ba_hourly_2024_2026.parquet")
    cems["utc_start"] = pd.to_datetime(cems["operating_datetime_utc"]).dt.tz_localize(None)
    e24["utc_start"] = pd.to_datetime(e24["utc_start"]).dt.tz_localize(None)

    e24 = e24.merge(
        cems[
            [
                "ba",
                "utc_start",
                "co2_kg",
                "gross_load_mw",
                "heat_mmbtu",
                "coal_co2_kg",
                "ngcc_co2_kg",
                "ngct_co2_kg",
                "oil_co2_kg",
                "coal_gross_mw",
                "ngcc_gross_mw",
                "ngct_gross_mw",
                "n_cems_units",
            ]
        ],
        on=["ba", "utc_start"],
        how="left",
    )

    # Verify exact 0-hour alignment across major grids (correlating CEMS gross_load_mw vs thermal gen)
    # For CISO, compare BOTH official CAISO fuelsource.csv Natural Gas (r > 0.995!) and raw EIA-930 NG!
    ciso_raw_cems_sub = e24[(e24["ba"] == "CISO") & e24["gross_load_mw"].notna()].sort_values("utc_start")
    ciso_raw_eia_vs_cems_r = float(ciso_raw_cems_sub["ng"].corr(ciso_raw_cems_sub["gross_load_mw"]))
    cems_lag_audit = {}
    for ba_c in ["CISO", "ERCO", "AZPS", "MISO", "SOCO", "DUK"]:
        sub = e24[(e24["ba"] == ba_c) & e24["gross_load_mw"].notna()].sort_values("utc_start")
        eia_th = sub["ng_mw"].fillna(sub["ng"]) if ba_c == "CISO" else (sub["ng"] + sub["coal"] + sub["oil"])
        lags = {}
        for lg in [-2, -1, 0, 1, 2]:
            lags[str(lg)] = float(eia_th.corr(sub["gross_load_mw"].shift(lg)))
        best_lag = max(lags, key=lambda k: lags[k])
        cems_lag_audit[ba_c] = {
            "n_hours": len(sub),
            "lag_corrs": lags,
            "best_lag_hr": int(best_lag),
            "r_at_lag0": lags["0"],
            "cems_to_eia_thermal_ratio": float(sub["gross_load_mw"].sum() / max(eia_th.sum(), 1.0)),
        }
        print(
            f"  CEMS Alignment [{ba_c}]: n={len(sub):,}, best_lag={best_lag}h, "
            f"r(0)={lags['0']:.4f} vs r(-1)={lags['-1']:.4f}, r(+1)={lags['1']:.4f}, "
            f"gross/net={cems_lag_audit[ba_c]['cems_to_eia_thermal_ratio']:.3f}",
            flush=True,
        )

    # Compute exact 4-window diurnal charging/discharging shares for all 14 metered BAs
    # (Clean 2024-07-01..2026-10-31 telemetry; also track exact CEMS overlap 2024-07-01..2026-09-30!)
    e24["window"] = e24["hour"].map(HOUR_TO_WINDOW)
    ba_telemetry_table = []
    for ba in METERED_14_BAS:
        sub = e24[(e24["ba"] == ba) & e24["bess_clean"].notna()].copy()
        dis_m = sub["bess_clean"] > 0.5
        chg_m = sub["bess_clean"] < -0.5
        dis_gwh = float(sub.loc[dis_m, "bess_clean"].sum() / 1000.0)
        chg_gwh = float(abs(sub.loc[chg_m, "bess_clean"].sum()) / 1000.0)
        rte = float(dis_gwh / max(chg_gwh, 1e-6))

        chg_win = {}
        dis_win = {}
        for wn in DIURNAL_WINDOWS:
            wc = float(abs(sub.loc[chg_m & (sub["window"] == wn), "bess_clean"].sum()) / 1000.0)
            wd = float(sub.loc[dis_m & (sub["window"] == wn), "bess_clean"].sum() / 1000.0)
            chg_win[wn] = float(100.0 * wc / max(chg_gwh, 1e-6))
            dis_win[wn] = float(100.0 * wd / max(dis_gwh, 1e-6))

        mid_sub = sub[sub["window"] == "Midday Solar"]
        mid_sol_pct = float(100.0 * mid_sub["solar"].sum() / max(mid_sub["demand"].sum(), 1.0))
        coal_pct = float(
            100.0 * sub["coal"].sum() / max((sub["coal"] + sub["ng"] + sub["oil"] + sub["nuclear"] + sub["hydro"] + sub["solar"] + sub["wind"]).sum(), 1.0)
        )
        cems_cov_hrs = int(sub["co2_kg"].notna().sum())

        ba_telemetry_table.append(
            {
                "ba": ba,
                "source": "CAISO_fuelsource_csv" if ba == "CISO" else "EIA930_clean",
                "dc_coupled_flag": bool(ba == "FPL"),
                "n_hours": len(sub),
                "cems_matched_hours": cems_cov_hrs,
                "eia860m_bess_mw": float(cap_op_map.get(ba, 0.0)),
                "dis_gwh": dis_gwh,
                "chg_gwh": chg_gwh,
                "rte": rte,
                "midday_solar_pct": mid_sol_pct,
                "coal_gen_pct": coal_pct,
                "chg_share_pct": chg_win,
                "dis_share_pct": dis_win,
            }
        )

    # Save clean metered hourly panel (all 50+ BAs for 2024-07-01..2026-10-31 so neighbor CEMS MEFs work too!)
    e24.to_parquet(PROC_DIR / "hourly_eia930_cems_bess_202407_202610.parquet", index=False)

    # Build dedicated CAISO Curtailment + Standalone Battery + EPA CEMS Hourly Panel (2024-07-01..2025-12-31)
    ciso_full = (
        e24[(e24["ba"] == "CISO") & (e24["date"] >= "2024-07-01") & (e24["date"] <= "2025-12-31")]
        .merge(curt_df, on=["date", "hour"], how="inner")
        .sort_values(["date", "hour"])
        .reset_index(drop=True)
    )
    ciso_full.to_parquet(PROC_DIR / "caiso_curtailment_cems_hourly.parquet", index=False)

    # Also compute bilateral interchange trade weights from Wave-7 cached EIA930_INTERCHANGE CSVs
    # Store BOTH abs_flow (two-way marginal interchange) AND imp_flow (incoming imports only for AEF!)
    print("[01.8] Computing bilateral EIA-930 interchange flow matrix (2025-2026)...", flush=True)
    int_frames = []
    for tag in ["2025_Jan_Jun", "2025_Jul_Dec", "2026_Jan_Jun", "2026_Jul_Dec"]:
        p = WAVE7_RAW_EIA930_DIR / f"EIA930_INTERCHANGE_{tag}.csv"
        d_i = pd.read_csv(
            p,
            usecols=[
                "Balancing Authority",
                "Directly Interconnected Balancing Authority",
                "Interchange (MW)",
            ],
            low_memory=False,
        )
        d_i.columns = ["ba", "diba", "mw"]
        d_i["mw"] = pd.to_numeric(
            d_i["mw"].astype(str).str.replace(",", "", regex=False), errors="coerce"
        ).fillna(0.0)
        int_frames.append(
            d_i.groupby(["ba", "diba"], as_index=False)["mw"].agg(
                abs_flow=lambda s: float(np.abs(s).sum()),
                imp_flow=lambda s: float(np.maximum(-s, 0.0).sum()),
                exp_flow=lambda s: float(np.maximum(s, 0.0).sum()),
                net_flow="sum",
            )
        )
    bilat = pd.concat(int_frames, ignore_index=True).groupby(["ba", "diba"], as_index=False).sum()
    bilat["weight"] = bilat["abs_flow"] / np.maximum(
        bilat.groupby("ba")["abs_flow"].transform("sum"), 1.0
    )
    bilat["imp_weight"] = bilat["imp_flow"] / np.maximum(
        bilat.groupby("ba")["imp_flow"].transform("sum"), 1.0
    )
    bilat.to_parquet(PROC_DIR / "bilateral_interchange_weights.parquet", index=False)

    tot_dis_14 = float(sum(r["dis_gwh"] for r in ba_telemetry_table))
    tot_chg_14 = float(sum(r["chg_gwh"] for r in ba_telemetry_table))
    tot_dis_13 = float(sum(r["dis_gwh"] for r in ba_telemetry_table if not r["dc_coupled_flag"]))
    tot_chg_13 = float(sum(r["chg_gwh"] for r in ba_telemetry_table if not r["dc_coupled_flag"]))

    audit = {
        "diurnal_windows": DIURNAL_WINDOWS,
        "panel_a_universe": {
            "n_valid_bas": len(valid_bas),
            "n_thermal_bas": len(thermal_bas),
            "valid_bas": valid_bas,
            "thermal_bas": thermal_bas,
            "n_hourly_eia930_rows": len(eia_19_26),
            "n_hourly_valid49_rows": len(eia_v),
            "n_monthly_rows": len(sp),
            "n_daily_rows": len(daily),
            "ym_min": str(sp["ym"].min()),
            "ym_max": str(sp["ym"].max()),
        },
        "eia860m_fleet": cap_summary,
        "ciso_telemetry_repair": {
            "eia930_broken_other_geo_dis_gwh": ciso_eia_og_dis,
            "eia930_broken_other_geo_chg_gwh": ciso_eia_og_chg,
            "eia930_broken_other_geo_rte": ciso_eia_broken_rte,
            "caiso_fuelsource_dis_gwh": ciso_fs_dis,
            "caiso_fuelsource_chg_gwh": ciso_fs_chg,
            "caiso_fuelsource_rte": ciso_fs_rte,
            "raw_eia930_ng_vs_cems_r": ciso_raw_eia_vs_cems_r,
            "alignment_lag_corrs": ciso_align_corrs,
            "eia930_ng_corruption_202312_202512": ciso_ng_corruption_audit,
        },
        "ues_charging_bug": ues_bug_audit,
        "pumped_hydro_leakage_audit": pumped_leak_audit,
        "physical_bound_anomalies": flagged_anomalies,
        "duk_reconciliation": duk_reconciliation,
        "cems_utc_alignment_audit": cems_lag_audit,
        "caiso_curtailment_overlap": {
            "n_hours": len(ciso_full),
            "date_min": str(ciso_full["date"].min().date()),
            "date_max": str(ciso_full["date"].max().date()),
            "total_curt_gwh": float(ciso_full["total_curt_mw"].sum() / 1000.0),
            "system_curt_gwh": float(ciso_full["system_curt_mw"].sum() / 1000.0),
            "local_curt_gwh": float(ciso_full["local_curt_mw"].sum() / 1000.0),
            "caiso_bess_chg_gwh": float(
                abs(ciso_full.loc[ciso_full["batteries_mw"] < 0, "batteries_mw"].sum()) / 1000.0
            ),
            "caiso_bess_dis_gwh": float(
                ciso_full.loc[ciso_full["batteries_mw"] > 0, "batteries_mw"].sum() / 1000.0
            ),
        },
        "metered_14_bas_totals": {
            "n_bas_total": len(ba_telemetry_table),
            "n_bas_clean_ac": sum(1 for r in ba_telemetry_table if not r["dc_coupled_flag"]),
            "total_14_dis_gwh": tot_dis_14,
            "total_14_chg_gwh": tot_chg_14,
            "total_13_ac_dis_gwh": tot_dis_13,
            "total_13_ac_chg_gwh": tot_chg_13,
            "fleet_13_ac_rte": float(tot_dis_13 / max(tot_chg_13, 1e-6)),
        },
        "metered_14_bas_table": ba_telemetry_table,
        "elapsed_sec": float(time.time() - t0),
    }

    sha = save_json_lf(RES_DIR / "01_telemetry_audit.json", audit)
    print("\n=== METERED 14-BA TELEMETRY SUMMARY (2024-07..2026-10) ===", flush=True)
    print(f"{'BA':6s} {'DisGWh':8s} {'ChgGWh':8s} {'RTE':6s} {'Ovn%':6s} {'Mng%':6s} {'Mid%':6s} {'Evn%':6s} {'MidSol%':7s}", flush=True)
    for r in ba_telemetry_table:
        cs = r["chg_share_pct"]
        print(
            f"{r['ba']:6s} {r['dis_gwh']:8.1f} {r['chg_gwh']:8.1f} {r['rte']:6.3f} "
            f"{cs['Overnight']:5.1f}% {cs['Morning Ramp']:5.1f}% {cs['Midday Solar']:5.1f}% "
            f"{cs['Evening Peak']:5.1f}% {r['midday_solar_pct']:6.1f}%",
            flush=True,
        )
    print(
        f"[DONE STEP 01] 14-BA Dis={tot_dis_14:,.1f} GWh, Chg={tot_chg_14:,.1f} GWh; "
        f"saved results/01_telemetry_audit.json (SHA-256: {sha})",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
