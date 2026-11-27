"""Step 03b (Nature Energy v4 Extensions):
  1. Exact Same-Window (2024-07..2025-12) 14-BA accounting + Full 14-BA Joint 14-Day
     Contiguous Moving-Block Bootstrap (B = 1,000) across ALL curtailment-absorption
     scenarios (uniform alpha in [0%, 30%] and hybrid empirical-CAISO scenarios).
  2. Three independent validations of CEMS MEFs that do NOT share EIA-930 fuel-slope
     regressions: (a) official EPA eGRID 2023 rev2 BA Non-Baseload CO2 output rates,
     (b) pure EPA CEMS internal stack ramp slopes (dCO2 / dGrossLoad_CEMS), and
     (c) direct metered battery-dispatch CEMS regressions (dCO2_CEMS / dBESS_MW).
  3. Cross-regional validation in ERCOT (ERCO, 9.92 TWh) & multi-grid (CISO, ERCO,
     AZPS, MISO) interior renewable-penetration CEMS MEF stratification.
  4. Congestion-Constrained Carbon Break-Even Frontier over storage expansion scale
     kappa, transmission-accessible curtailment fraction tau_grid, and diurnal MEF ratio.
"""

from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd
from econ_utils import (
    PROC_DIR,
    RAW_EXT_DIR,
    RES_DIR,
    hourly_ols_cluster_hac,
    save_json_lf,
)

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


def _extract_24h_trimmed_df(gd: pd.DataFrame, y_col: str, x_col: str, trim_mad: float = 8.0) -> pd.DataFrame | None:
    keep_chunks = []
    for h in range(1, 25):
        sh = gd[gd["hour"] == h]
        ok = np.isfinite(sh[y_col].values) & np.isfinite(sh[x_col].values)
        sh = sh.iloc[ok]
        if len(sh) < 40:
            continue
        x = sh[x_col].values
        if trim_mad > 0:
            med_x = float(np.median(x))
            mad_x = float(np.median(np.abs(x - med_x)))
            if mad_x > 1e-6:
                km = np.abs(x - med_x) <= trim_mad * 1.4826 * mad_x
                if int(np.sum(km)) >= 30:
                    sh = sh.iloc[km]
        keep_chunks.append(sh)
    if not keep_chunks:
        return None
    return pd.concat(keep_chunks, ignore_index=True)


def _weighted_24h_beta(
    y: np.ndarray,
    x: np.ndarray,
    hr0: np.ndarray,
    ymh_c: np.ndarray,
    m_fe: int,
    w: np.ndarray,
) -> np.ndarray:
    sw = np.bincount(ymh_c, weights=w, minlength=m_fe)
    sw_safe = np.where(sw > 0.0, sw, 1.0)
    my = np.bincount(ymh_c, weights=w * y, minlength=m_fe) / sw_safe
    mx = np.bincount(ymh_c, weights=w * x, minlength=m_fe) / sw_safe
    yd = y - my[ymh_c]
    xd = x - mx[ymh_c]
    sxx = np.bincount(hr0, weights=w * xd * xd, minlength=24)
    sxy = np.bincount(hr0, weights=w * xd * yd, minlength=24)
    beta = np.where(sxx >= 1.0, sxy / np.where(sxx >= 1.0, sxx, 1.0), 0.0)
    return np.clip(beta, 0.0, 1400.0)


def _weighted_within_fe_slope(y: np.ndarray, x: np.ndarray, fe_c: np.ndarray, m_fe: int, w: np.ndarray) -> float:
    sw = np.bincount(fe_c, weights=w, minlength=m_fe)
    sw_safe = np.where(sw > 0.0, sw, 1.0)
    my = np.bincount(fe_c, weights=w * y, minlength=m_fe) / sw_safe
    mx = np.bincount(fe_c, weights=w * x, minlength=m_fe) / sw_safe
    yd = y - my[fe_c]
    xd = x - mx[fe_c]
    sxx = float(np.sum(w * xd * xd))
    if sxx < 1.0:
        return 0.0
    return float(np.sum(w * xd * yd) / sxx)


def _draw_mbb_mult(rng: np.random.Generator, n_days: int, block_len: int) -> np.ndarray:
    if n_days <= 0:
        return np.empty(0, dtype=np.float64)
    if block_len <= 1:
        return rng.multinomial(n_days, np.full(n_days, 1.0 / n_days, dtype=np.float64)).astype(np.float64)
    L = min(block_len, n_days)
    n_starts = n_days - L + 1
    n_blocks = (n_days + L - 1) // L
    starts = rng.integers(0, n_starts, size=n_blocks)
    idx = (starts[:, None] + np.arange(L, dtype=np.int64)[None, :]).ravel()[:n_days]
    return np.bincount(idx, minlength=n_days).astype(np.float64)


def _summarize(pt: float, arr: np.ndarray) -> dict[str, float | bool]:
    lo = float(np.percentile(arr, 2.5))
    hi = float(np.percentile(arr, 97.5))
    se = float(np.std(arr, ddof=1))
    p_le0 = float(np.mean(arr <= 0.0))
    p_ge0 = float(np.mean(arr >= 0.0))
    p2 = float(min(1.0, 2.0 * min(p_le0, p_ge0)))
    return {
        "point": float(pt),
        "boot_se": se,
        "ci95_lo": lo,
        "ci95_hi": hi,
        "p_2sided_vs_zero": p2,
        "covers_zero": bool(lo <= 0.0 <= hi),
    }


def _load_egrid_nonbaseload_rates() -> dict[str, float]:
    """Load official EPA eGRID 2023 rev2 BA annual CO2 non-baseload output emission rates (kg/MWh).
    Uses ZERO EIA-930 regressions (100% EPA plant capacity-factor-weighted non-baseload metric).
    """
    xl_path = RAW_EXT_DIR / "egrid2023_data_rev2.xlsx"
    df_ba = pd.read_excel(xl_path, sheet_name="BA23", skiprows=[1])
    # Identify non-baseload CO2 rate column dynamically (lb/MWh -> kg/MWh = * 0.45359237)
    code_col = next(c for c in df_ba.columns if "Balancing Authority Code" in str(c))
    nb_co2_col = None
    for c in df_ba.columns:
        cl = str(c).lower()
        if ("nonbaseload" in cl or "non-baseload" in cl) and "co2" in cl and "rate" in cl and "equivalent" not in cl:
            nb_co2_col = c
            break
    out: dict[str, float] = {}
    if nb_co2_col is not None:
        for _, r in df_ba[[code_col, nb_co2_col]].dropna().iterrows():
            ba = str(r[code_col]).strip()
            val = pd.to_numeric(r[nb_co2_col], errors="coerce")
            if np.isfinite(val) and val >= 0.0:
                out[ba] = float(val * 0.45359237)
    else:
        # Fallback: compute exact EPA BA non-baseload CO2 rate from PLNT23 plant Nonbaseload Factor
        df_p = pd.read_excel(
            xl_path,
            sheet_name="PLNT23",
            skiprows=[1],
            usecols=[
                "Balancing Authority Code",
                "Nonbaseload Factor",
                "Plant annual net generation (MWh)",
                "Plant annual CO2 emissions (tons)",
            ],
        )
        df_p["nb_gen"] = pd.to_numeric(df_p["Nonbaseload Factor"], errors="coerce").fillna(0.0) * pd.to_numeric(
            df_p["Plant annual net generation (MWh)"], errors="coerce"
        ).fillna(0.0)
        df_p["nb_co2_kg"] = (
            pd.to_numeric(df_p["Nonbaseload Factor"], errors="coerce").fillna(0.0)
            * pd.to_numeric(df_p["Plant annual CO2 emissions (tons)"], errors="coerce").fillna(0.0)
            * 907.18474
        )
        agg = df_p.groupby("Balancing Authority Code")[["nb_gen", "nb_co2_kg"]].sum()
        for ba, r in agg.iterrows():
            if r["nb_gen"] > 1000.0:
                out[str(ba).strip()] = float(r["nb_co2_kg"] / r["nb_gen"])
    return out


def main() -> int:
    t0 = time.time()
    print("=== STEP 03b: NATURE ENERGY v4 EXTENSIONS ===", flush=True)

    r3 = json.loads((RES_DIR / "03_cems_carbon_curtailment_results.json").read_text(encoding="utf-8"))
    e24 = pd.read_parquet(PROC_DIR / "hourly_eia930_cems_bess_202407_202610.parquet")
    bilat = pd.read_parquet(PROC_DIR / "bilateral_interchange_weights.parquet")
    ciso_curt = pd.read_parquet(PROC_DIR / "caiso_curtailment_cems_hourly.parquet")

    e24["date"] = pd.to_datetime(e24["date"]).dt.normalize()
    e24["ym"] = e24["date"].dt.strftime("%Y-%m")

    is_ciso = e24["ba"] == "CISO"
    has_fs = is_ciso & e24["fs_load"].notna()
    e24["demand_use"] = np.where(has_fs, e24["fs_load"], e24["demand"])
    e24["ng_use"] = np.where(has_fs, e24["ng_mw"].fillna(0.0), e24["ng"])
    e24["solar_use"] = np.where(has_fs, e24["solar_mw"].fillna(0.0), e24["solar"])
    e24["wind_use"] = np.where(has_fs, e24["wind_mw"].fillna(0.0), e24["wind"])
    e24["hydro_use"] = np.where(
        has_fs, e24["large_hydro_mw"].fillna(0.0) + e24["small_hydro_mw"].fillna(0.0), e24["hydro"]
    )
    e24["nuclear_use"] = np.where(has_fs, e24["nuclear_mw"].fillna(0.0), e24["nuclear"])
    e24["coal_use"] = np.where(has_fs, np.maximum(e24["coal_mw"].fillna(0.0), 0.0), e24["coal"])
    e24["geo_bio_other_use"] = np.where(
        has_fs,
        e24["geothermal_mw"].fillna(0.0)
        + e24["biomass_mw"].fillna(0.0)
        + e24["biogas_mw"].fillna(0.0)
        + e24["other_mw"].fillna(0.0),
        e24["geothermal"].fillna(0.0),
    )
    e24["net_imports_use"] = np.where(has_fs, e24["imports_mw"].fillna(0.0), -e24["interchange"])
    e24["disp_dom"] = e24["ng_use"] + e24["coal_use"] + e24["oil"] + e24["hydro_use"] + e24["nuclear_use"]
    e24["tot_gen_use"] = e24["disp_dom"] + e24["solar_use"] + e24["wind_use"] + e24["geo_bio_other_use"]

    e_cems = e24[(e24["date"] >= "2024-07-01") & (e24["date"] <= "2026-09-30")].copy()

    # ------------------------------------------------------------------
    # PART 1: BUILD FAST STRUCTURES FOR ALL 14 BAs + THEIR NEIGHBORS + CAISO CURTAILMENT
    #         FOR BOTH FULL WINDOW (2024-07..2026-09) AND SAME WINDOW (2024-07..2025-12)
    # ------------------------------------------------------------------
    print("[03b.1] Preparing full 14-BA + neighbor joint 14-day block-bootstrap structures...", flush=True)
    needed_bas: set[str] = set(METERED_14_BAS)
    for ba in METERED_14_BAS:
        needed_bas.update(bilat.loc[bilat["ba"] == ba, "diba"].astype(str).tolist())

    overlap_dates = np.sort(e_cems.loc[e_cems["date"] <= "2025-12-31", "date"].unique())
    extra_dates = np.sort(e_cems.loc[e_cems["date"] > "2025-12-31", "date"].unique())
    n_ov = len(overlap_dates)
    n_ex = len(extra_dates)
    all_dates = np.concatenate([overlap_dates, extra_dates])
    date_to_idx = {d: i for i, d in enumerate(all_dates)}
    n_all = len(all_dates)

    # Pre-encode trimmed 24h domestic CEMS regressions for EVERY needed BA
    dom_structs: dict[str, dict[str, object]] = {}
    for ba in sorted(needed_bas):
        grp = e_cems[e_cems["ba"] == ba].sort_values("utc_start")
        if len(grp) < 1000:
            continue
        dt_sec = grp["utc_start"].diff().dt.total_seconds()
        d_disp = grp["disp_dom"].diff()
        d_co2 = grp["co2_kg"].diff()
        med_disp = float(grp["disp_dom"].median())
        no_drop = (
            (grp["disp_dom"] > 0.25 * med_disp) & (grp["disp_dom"].shift(1) > 0.25 * med_disp)
            if med_disp > 100.0
            else pd.Series(True, index=grp.index)
        )
        ok = (dt_sec == 3600.0) & d_disp.notna() & no_drop
        gd = pd.DataFrame(
            {
                "hour": grp["hour"].values,
                "ym": grp["ym"].values,
                "date": grp["date"].values,
                "d_disp": d_disp.values,
                "d_co2": d_co2.values,
            }
        )[ok.values]
        gdt = _extract_24h_trimmed_df(gd, "d_co2", "d_disp", trim_mad=8.0)
        if gdt is None:
            continue
        ymh_c, ymh_u = pd.factorize((gdt["ym"].astype(str) + "_" + gdt["hour"].astype(str)).to_numpy(), sort=False)
        dom_structs[ba] = {
            "d_idx": np.array([date_to_idx[d] for d in gdt["date"].to_numpy()], dtype=np.int32),
            "hr0": (gdt["hour"].to_numpy(dtype=np.int32) - 1),
            "ymh_c": ymh_c.astype(np.int32),
            "m_fe": len(ymh_u),
            "y": gdt["d_co2"].to_numpy(dtype=np.float64),
            "x": gdt["d_disp"].to_numpy(dtype=np.float64),
        }

    # Pre-encode neighbor weight maps for all 14 BAs
    nbr_weights: dict[str, list[tuple[str, float]]] = {}
    for ba in METERED_14_BAS:
        nb = bilat[bilat["ba"] == ba]
        pairs = []
        ws = 0.0
        for _, rr in nb.iterrows():
            diba = str(rr["diba"])
            wv = float(rr["weight"])
            if diba in dom_structs and wv > 0.0:
                pairs.append((diba, wv))
                ws += wv
        nbr_weights[ba] = [(d, w / ws) for d, w in pairs] if ws > 0.05 else [(ba, 1.0)]

    # Pre-encode daily 24h charging/discharging energy & net-import thermal fractions for all 14 BAs
    # (for BOTH full window [all_dates] and exact same window [overlap_dates]!)
    ba_panel_structs: dict[str, dict[str, object]] = {}
    for ba in METERED_14_BAS:
        g = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy()
        dt_sec = g["utc_start"].diff().dt.total_seconds()
        d_disp = g["disp_dom"].diff()
        d_imp = g["net_imports_use"].diff()
        d_tot = d_disp + d_imp
        ok_s = (dt_sec == 3600.0) & d_tot.notna() & d_disp.notna() & d_imp.notna()
        g_s = g[ok_s.values]
        ymh_sc, ymh_su = pd.factorize((g_s["ym"].astype(str) + "_" + g_s["hour"].astype(str)).to_numpy(), sort=False)

        # Daily 24h charge/discharge matrices (n_all x 24)
        d_idx_g = np.array([date_to_idx[d] for d in g["date"].to_numpy()], dtype=np.int32)
        hr0_g = g["hour"].to_numpy(dtype=np.int32) - 1
        chg_mw = np.maximum(-g["bess_clean"].fillna(0.0).to_numpy(dtype=np.float64), 0.0)
        dis_mw = np.maximum(g["bess_clean"].fillna(0.0).to_numpy(dtype=np.float64), 0.0)
        day_chg_24 = np.zeros((n_all, 24), dtype=np.float64)
        day_dis_24 = np.zeros((n_all, 24), dtype=np.float64)
        np.add.at(day_chg_24, (d_idx_g, hr0_g), chg_mw)
        np.add.at(day_dis_24, (d_idx_g, hr0_g), dis_mw)

        # Hourly AEF arrays by window (exact consumption-weighted AEF from Step 03)
        r3_row = next(r for r in r3["ba_carbon_table"] if r["ba"] == ba)
        # Also compute exact same-window (2024-07..2025-12) AEF directly!
        g_ov = g[g["date"] <= "2025-12-31"]
        nb_imp = bilat[bilat["ba"] == ba]
        # Domestic hourly AEF in same-window
        aef_dom_ov = np.zeros(24, dtype=np.float64)
        for h in range(1, 25):
            sh = g_ov[g_ov["hour"] == h]
            aef_dom_ov[h - 1] = float(sh["co2_kg"].fillna(0.0).sum() / max(float(sh["tot_gen_use"].sum()), 1.0))

        ba_panel_structs[ba] = {
            "s_d_idx": np.array([date_to_idx[d] for d in g_s["date"].to_numpy()], dtype=np.int32),
            "s_hr0": (g_s["hour"].to_numpy(dtype=np.int32) - 1),
            "s_ymh_c": ymh_sc.astype(np.int32),
            "s_m_fe": len(ymh_su),
            "s_d_disp": d_disp[ok_s].to_numpy(dtype=np.float64),
            "s_d_imp": d_imp[ok_s].to_numpy(dtype=np.float64),
            "s_d_tot": d_tot[ok_s].to_numpy(dtype=np.float64),
            "day_chg_24": day_chg_24,
            "day_dis_24": day_dis_24,
            "r3_net_aef_kg_mwh": float(r3_row["net_aef_kg_mwh"]),
            "r3_net_aef_kt": float(r3_row["net_aef_kt"]),
            "aef_dom_ov": aef_dom_ov,
            "nb_imp": nb_imp,
        }

    # Exact same-window AEF per BA (including incoming-import neighbor AEF, matching Step 03 identically!)
    ba_dom_aef_ov_map: dict[str, np.ndarray] = {}
    for ba in sorted(needed_bas):
        g_ov = e_cems[(e_cems["ba"] == ba) & (e_cems["date"] <= "2025-12-31")]
        if len(g_ov) < 500:
            continue
        arr_a = np.zeros(24, dtype=np.float64)
        for h in range(1, 25):
            sh = g_ov[g_ov["hour"] == h]
            arr_a[h - 1] = float(sh["co2_kg"].fillna(0.0).sum() / max(float(sh["tot_gen_use"].sum()), 1.0))
        ba_dom_aef_ov_map[ba] = arr_a

    same_win_aef_kt: dict[str, float] = {}
    same_win_aef_kg: dict[str, float] = {}
    same_win_dis_gwh: dict[str, float] = {}
    for ba in METERED_14_BAS:
        g_ov = e_cems[(e_cems["ba"] == ba) & (e_cems["date"] <= "2025-12-31")]
        nb = bilat[bilat["ba"] == ba]
        nbr_aef = np.zeros(24, dtype=np.float64)
        ws = 0.0
        for _, rr in nb.iterrows():
            diba = str(rr["diba"])
            wv = float(rr["imp_weight"])
            if diba in ba_dom_aef_ov_map and wv > 0.0:
                nbr_aef += wv * ba_dom_aef_ov_map[diba]
                ws += wv
        nbr_aef = nbr_aef / ws if ws > 0.05 else ba_dom_aef_ov_map[ba]

        cons_aef = np.zeros(24, dtype=np.float64)
        for h in range(1, 25):
            sh = g_ov[g_ov["hour"] == h]
            gen_h = max(float(sh["tot_gen_use"].sum()), 1.0)
            imp_pos_h = float(np.maximum(sh["net_imports_use"].fillna(0.0), 0.0).sum())
            cons_aef[h - 1] = (gen_h * ba_dom_aef_ov_map[ba][h - 1] + imp_pos_h * nbr_aef[h - 1]) / (gen_h + imp_pos_h)

        chg_24 = ba_panel_structs[ba]["day_chg_24"][:n_ov].sum(axis=0)
        dis_24 = ba_panel_structs[ba]["day_dis_24"][:n_ov].sum(axis=0)
        tot_chg = float(chg_24.sum())
        tot_dis = float(dis_24.sum())
        rte_ov = tot_dis / max(tot_chg, 1.0)
        aef_chg = float((chg_24 / max(tot_chg, 1.0)) @ cons_aef)
        aef_dis = float((dis_24 / max(tot_dis, 1.0)) @ cons_aef)
        net_aef_ov = aef_chg / max(rte_ov, 1e-6) - aef_dis
        same_win_aef_kg[ba] = float(net_aef_ov)
        same_win_dis_gwh[ba] = float(tot_dis / 1000.0)
        same_win_aef_kt[ba] = float(net_aef_ov * (tot_dis / 1000.0) / 1000.0)

    # Pre-encode CAISO 4 interior curtailment bins (same 549 overlap days!)
    cc = (
        ciso_curt.dropna(
            subset=["batteries_mw", "fs_load", "solar_mw", "wind_mw", "ng_mw", "imports_mw", "large_hydro_mw", "co2_kg"]
        )
        .sort_values("utc_start")
        .copy()
    )
    cc["date"] = pd.to_datetime(cc["date"]).dt.normalize()
    cc["ym"] = cc["date"].dt.strftime("%Y-%m")
    cc["ym_hr"] = cc["ym"] + "_" + cc["hour"].astype(str)
    cc["chg_mw"] = np.maximum(-cc["batteries_mw"], 0.0)
    cc["dis_mw"] = np.maximum(cc["batteries_mw"], 0.0)
    cc["pot_ren_mw"] = cc["solar_mw"] + cc["wind_mw"] + cc["total_curt_mw"]
    cc["net_load_pot"] = cc["fs_load"] - cc["pot_ren_mw"] - cc["batteries_mw"]
    cc["dt_sec"] = cc["utc_start"].diff().dt.total_seconds()
    cc["curt_prev"] = cc["total_curt_mw"].shift(1)
    cc["curt_min"] = np.minimum(cc["total_curt_mw"], cc["curt_prev"])
    cc["curt_max"] = np.maximum(cc["total_curt_mw"], cc["curt_prev"])
    cc["d_co2"] = cc["co2_kg"].diff()
    cc["d_imp"] = cc["imports_mw"].diff()
    cc["d_load"] = cc["fs_load"].diff()
    cc["d_net_pot"] = cc["net_load_pot"].diff()
    cc_diff = cc[(cc["dt_sec"] == 3600.0) & cc["d_co2"].notna() & cc["d_net_pot"].notna()].copy()

    def _bin_idx(v: float) -> int:
        if v <= 0.0:
            return 0
        if v <= 500.0:
            return 1
        if v <= 2000.0:
            return 2
        return 3

    cc_d_idx = np.array([date_to_idx[d] for d in cc["date"].to_numpy()], dtype=np.int32)
    cc_bin_k = np.array([_bin_idx(v) for v in cc["total_curt_mw"].to_numpy()], dtype=np.int32)
    day_ciso_chg_bin = np.zeros((n_ov, 4), dtype=np.float64)
    day_ciso_dis_bin = np.zeros((n_ov, 4), dtype=np.float64)
    for k in range(4):
        mk = cc_bin_k == k
        day_ciso_chg_bin[:, k] = np.bincount(cc_d_idx[mk], weights=cc["chg_mw"].to_numpy()[mk], minlength=n_ov)
        day_ciso_dis_bin[:, k] = np.bincount(cc_d_idx[mk], weights=cc["dis_mw"].to_numpy()[mk], minlength=n_ov)

    curt_masks = [
        (cc_diff["total_curt_mw"] <= 0.0) & (cc_diff["curt_prev"] <= 0.0),
        (cc_diff["curt_min"] > 0.0) & (cc_diff["curt_max"] <= 500.0),
        (cc_diff["curt_min"] > 500.0) & (cc_diff["curt_max"] <= 2000.0),
        cc_diff["curt_min"] > 2000.0,
    ]
    ciso_bin_structs = []
    for mk in curt_masks:
        sd = cc_diff[mk]
        fe_c, fe_u = pd.factorize(sd["ym_hr"].to_numpy(), sort=False)
        ciso_bin_structs.append(
            {
                "d_idx": np.array([date_to_idx[d] for d in sd["date"].to_numpy()], dtype=np.int32),
                "hr0": (sd["hour"].to_numpy(dtype=np.int32) - 1),
                "fe_c": fe_c.astype(np.int32),
                "m_fe": len(fe_u),
                "d_co2": sd["d_co2"].to_numpy(dtype=np.float64),
                "d_imp": sd["d_imp"].to_numpy(dtype=np.float64),
                "d_net_pot": sd["d_net_pot"].to_numpy(dtype=np.float64),
                "d_load": sd["d_load"].to_numpy(dtype=np.float64),
            }
        )

    def _eval_fleet_14(day_mult_full: np.ndarray, same_window_only: bool = False) -> dict[str, float]:
        # Restrict weights strictly to overlap days [0:n_ov] if same_window_only!
        w_days = day_mult_full.copy()
        if same_window_only:
            w_days[n_ov:] = 0.0

        # 1. Estimate 24h domestic CEMS MEF for every needed BA on these day weights
        dom_b24: dict[str, np.ndarray] = {}
        for ba, ds in dom_structs.items():
            wb = w_days[ds["d_idx"]]
            dom_b24[ba] = _weighted_24h_beta(ds["y"], ds["x"], ds["hr0"], ds["ymh_c"], ds["m_fe"], wb)

        # 2. Compute 24h system CEMS MEF & weighted chg/dis MEFs for all 14 BAs
        ba_chg_mef: dict[str, float] = {}
        ba_dis_mef: dict[str, float] = {}
        ba_rte: dict[str, float] = {}
        ba_dis_gwh: dict[str, float] = {}
        ciso_nbr_b24 = np.zeros(24, dtype=np.float64)

        for ba in METERED_14_BAS:
            ps = ba_panel_structs[ba]
            nbr_vec = np.zeros(24, dtype=np.float64)
            for diba, wn in nbr_weights[ba]:
                nbr_vec += wn * dom_b24[diba]
            if ba == "CISO":
                ciso_nbr_b24 = nbr_vec

            ws_b = w_days[ps["s_d_idx"]]
            s_dom = np.clip(_weighted_24h_beta(ps["s_d_disp"], ps["s_d_tot"], ps["s_hr0"], ps["s_ymh_c"], ps["s_m_fe"], ws_b), 0.0, 1.0)
            s_imp = np.clip(_weighted_24h_beta(ps["s_d_imp"], ps["s_d_tot"], ps["s_hr0"], ps["s_ymh_c"], ps["s_m_fe"], ws_b), 0.0, 1.0)
            st = np.maximum(s_dom + s_imp, 0.05)
            sys_b24 = (s_dom / st) * dom_b24[ba] + (s_imp / st) * nbr_vec

            chg_24 = w_days @ ps["day_chg_24"]
            dis_24 = w_days @ ps["day_dis_24"]
            t_chg = max(float(chg_24.sum()), 1.0)
            t_dis = max(float(dis_24.sum()), 1.0)
            ba_chg_mef[ba] = float((chg_24 / t_chg) @ sys_b24)
            ba_dis_mef[ba] = float((dis_24 / t_dis) @ sys_b24)
            ba_rte[ba] = float(t_dis / t_chg)
            ba_dis_gwh[ba] = float(t_dis / 1000.0)

        # 3. Compute CAISO curtailment-stratified empirical system balance on the SAME resampled overlap days!
        m_ov = w_days[:n_ov]
        m_sys_k = np.empty(4, dtype=np.float64)
        m_ld_k = np.empty(4, dtype=np.float64)
        for k, bs in enumerate(ciso_bin_structs):
            wk = w_days[bs["d_idx"]]
            d_sys = bs["d_co2"] + bs["d_imp"] * ciso_nbr_b24[bs["hr0"]]
            m_sys_k[k] = _weighted_within_fe_slope(d_sys, bs["d_net_pot"], bs["fe_c"], bs["m_fe"], wk)
            m_ld_k[k] = _weighted_within_fe_slope(d_sys, bs["d_load"], bs["fe_c"], bs["m_fe"], wk)
        chg_k = m_ov @ day_ciso_chg_bin
        dis_k = m_ov @ day_ciso_dis_bin
        tc_c = max(float(chg_k.sum()), 1.0)
        td_c = max(float(dis_k.sum()), 1.0)
        rte_c = td_c / tc_c
        ciso_emp_main = float(((chg_k / tc_c) @ m_sys_k) / rte_c - ((dis_k / td_c) @ m_sys_k))
        ciso_emp_dload = float(((chg_k / tc_c) @ m_ld_k) / rte_c - ((dis_k / td_c) @ m_ld_k))

        # 4. Aggregate fleet totals (using FIXED historical discharge weights so Mt scale is exact!)
        res_d: dict[str, float] = {}
        tot_aef_mt = sum(same_win_aef_kt[b] if same_window_only else ba_panel_structs[b]["r3_net_aef_kt"] for b in METERED_14_BAS) / 1000.0
        dis_fixed = {b: (same_win_dis_gwh[b] if same_window_only else float(next(r["dis_gwh_cems_window"] for r in r3["ba_carbon_table"] if r["ba"] == b))) for b in METERED_14_BAS}
        tot_dis_gwh = sum(dis_fixed.values())

        for a_val in (0.0, 0.10, 0.15, 0.20, 0.30):
            net_mt = sum(
                (((1.0 - a_val) * ba_chg_mef[b]) / ba_rte[b] - ba_dis_mef[b]) * dis_fixed[b] / 1e6
                for b in METERED_14_BAS
            )
            tag = f"u{round(100 * a_val)}"
            res_d[f"{tag}_net_mt"] = float(net_mt)
            res_d[f"{tag}_kg_mwh"] = float(1e6 * net_mt / tot_dis_gwh)
            res_d[f"{tag}_disc_mt"] = float(net_mt - tot_aef_mt)

        for a_oth in (0.0, 0.10, 0.15):
            non_ciso_mt = sum(
                (((1.0 - a_oth) * ba_chg_mef[b]) / ba_rte[b] - ba_dis_mef[b]) * dis_fixed[b] / 1e6
                for b in METERED_14_BAS
                if b != "CISO"
            )
            h_main_mt = non_ciso_mt + ciso_emp_main * dis_fixed["CISO"] / 1e6
            h_dl_mt = non_ciso_mt + ciso_emp_dload * dis_fixed["CISO"] / 1e6
            tag = f"h{round(100 * a_oth)}"
            res_d[f"{tag}_main_mt"] = float(h_main_mt)
            res_d[f"{tag}_main_disc_mt"] = float(h_main_mt - tot_aef_mt)
            res_d[f"{tag}_dload_mt"] = float(h_dl_mt)
            res_d[f"{tag}_dload_disc_mt"] = float(h_dl_mt - tot_aef_mt)

        res_d["ciso_emp_main"] = ciso_emp_main
        res_d["ciso_emp_dload"] = ciso_emp_dload
        res_d["tot_aef_mt"] = float(tot_aef_mt)
        res_d["tot_dis_twh"] = float(tot_dis_gwh / 1000.0)
        return res_d

    # Exact point estimates (Full Window vs Same Window 2024H2-2025!)
    unit_w = np.ones(n_all, dtype=np.float64)
    pt_full = _eval_fleet_14(unit_w, same_window_only=False)
    pt_same = _eval_fleet_14(unit_w, same_window_only=True)
    print(
        f"  [Full 2024H2-2026Q3, {pt_full['tot_dis_twh']:.2f} TWh] a=0%: Net={pt_full['u0_net_mt']:+.2f} Mt, "
        f"Disc={pt_full['u0_disc_mt']:+.2f} Mt | Hybrid(a_oth=0/15%): Net={pt_full['h0_main_mt']:+.2f}/{pt_full['h15_main_mt']:+.2f} Mt, "
        f"Disc={pt_full['h0_main_disc_mt']:+.2f}/{pt_full['h15_main_disc_mt']:+.2f} Mt",
        flush=True,
    )
    print(
        f"  [Same 2024H2-2025,   {pt_same['tot_dis_twh']:.2f} TWh] a=0%: Net={pt_same['u0_net_mt']:+.2f} Mt, "
        f"Disc={pt_same['u0_disc_mt']:+.2f} Mt | Hybrid(a_oth=0/15%): Net={pt_same['h0_main_mt']:+.2f}/{pt_same['h15_main_mt']:+.2f} Mt, "
        f"Disc={pt_same['h0_main_disc_mt']:+.2f}/{pt_same['h15_main_disc_mt']:+.2f} Mt (AEF={pt_same['tot_aef_mt']:+.2f} Mt)",
        flush=True,
    )

    # Full 14-BA Joint 14-Day Contiguous Block Bootstrap (B = 1,000) for BOTH windows!
    B_BOOT = 1000
    print(f"[03b.2] Running Full 14-BA Joint 14-Day Contiguous Block Bootstrap (B={B_BOOT})...", flush=True)
    keys_track = [
        "u0_net_mt",
        "u0_kg_mwh",
        "u0_disc_mt",
        "u10_net_mt",
        "u10_disc_mt",
        "u15_net_mt",
        "u15_disc_mt",
        "u20_net_mt",
        "u20_disc_mt",
        "u30_net_mt",
        "u30_disc_mt",
        "h0_main_mt",
        "h0_main_disc_mt",
        "h10_main_mt",
        "h10_main_disc_mt",
        "h15_main_mt",
        "h15_main_disc_mt",
        "h0_dload_mt",
        "h0_dload_disc_mt",
        "h15_dload_mt",
        "h15_dload_disc_mt",
    ]
    boot_full = {k: np.empty(B_BOOT, dtype=np.float64) for k in keys_track}
    boot_same = {k: np.empty(B_BOOT, dtype=np.float64) for k in keys_track}

    rng_f = np.random.default_rng(20261128)
    for bi in range(B_BOOT):
        w_ov = _draw_mbb_mult(rng_f, n_ov, 14)
        w_ex = _draw_mbb_mult(rng_f, n_ex, 14)
        w_all = np.concatenate([w_ov, w_ex])
        rf = _eval_fleet_14(w_all, same_window_only=False)
        rs = _eval_fleet_14(w_all, same_window_only=True)
        for k in keys_track:
            boot_full[k][bi] = rf[k]
            boot_same[k][bi] = rs[k]

    summary_full_14d = {k: _summarize(pt_full[k], boot_full[k]) for k in keys_track}
    summary_same_14d = {k: _summarize(pt_same[k], boot_same[k]) for k in keys_track}

    print(
        f"  [14d Joint Boot Full] a=0% Disc: {summary_full_14d['u0_disc_mt']['point']:+.2f} "
        f"[{summary_full_14d['u0_disc_mt']['ci95_lo']:+.2f}, {summary_full_14d['u0_disc_mt']['ci95_hi']:+.2f}] Mt | "
        f"Hybrid a_oth=15% Net: {summary_full_14d['h15_main_mt']['point']:+.2f} "
        f"[{summary_full_14d['h15_main_mt']['ci95_lo']:+.2f}, {summary_full_14d['h15_main_mt']['ci95_hi']:+.2f}] Mt, "
        f"Disc: {summary_full_14d['h15_main_disc_mt']['point']:+.2f} "
        f"[{summary_full_14d['h15_main_disc_mt']['ci95_lo']:+.2f}, {summary_full_14d['h15_main_disc_mt']['ci95_hi']:+.2f}] Mt",
        flush=True,
    )
    print(
        f"  [14d Joint Boot Same] a=0% Disc: {summary_same_14d['u0_disc_mt']['point']:+.2f} "
        f"[{summary_same_14d['u0_disc_mt']['ci95_lo']:+.2f}, {summary_same_14d['u0_disc_mt']['ci95_hi']:+.2f}] Mt | "
        f"Hybrid a_oth=15% Net: {summary_same_14d['h15_main_mt']['point']:+.2f} "
        f"[{summary_same_14d['h15_main_mt']['ci95_lo']:+.2f}, {summary_same_14d['h15_main_mt']['ci95_hi']:+.2f}] Mt, "
        f"Disc: {summary_same_14d['h15_main_disc_mt']['point']:+.2f} "
        f"[{summary_same_14d['h15_main_disc_mt']['ci95_lo']:+.2f}, {summary_same_14d['h15_main_disc_mt']['ci95_hi']:+.2f}] Mt",
        flush=True,
    )

    # ------------------------------------------------------------------
    # PART 2: THREE INDEPENDENT VALIDATIONS OF CEMS MEFs (ZERO SHARED EIA-930 FUEL SLOPES!)
    # ------------------------------------------------------------------
    print("[03b.3] Running 3 independent MEF validations (EPA eGRID Non-Baseload, CEMS-only stack slope, Direct dCO2/dBESS)...", flush=True)
    nb_rates = _load_egrid_nonbaseload_rates()
    indep_rows = []
    for r in r3["ba_carbon_table"]:
        ba = r["ba"]
        # (a) Official EPA eGRID 2023 rev2 BA Non-Baseload CO2 rate (trade-adjusted vs domestic)
        nb_dom = nb_rates.get(ba, np.nan)
        # Bilateral-weighted neighbor Non-Baseload rate
        ws, vs = 0.0, 0.0
        for diba, wn in nbr_weights[ba]:
            if diba in nb_rates:
                ws += wn
                vs += wn * nb_rates[diba]
        nb_nbr = vs / ws if ws > 0.05 else nb_dom

        # (b) Pure CEMS-only internal stack ramp slope: d(CO2_CEMS) / d(Gross_Load_CEMS) (ZERO EIA-930!)
        g = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy()
        dt_s = g["utc_start"].diff().dt.total_seconds()
        d_co2 = g["co2_kg"].diff()
        d_gl = g["gross_load_mw"].diff()
        ok_c = (dt_s == 3600.0) & d_co2.notna() & d_gl.notna() & (g["gross_load_mw"] > 50.0)
        g_c = g[ok_c.values]
        if len(g_c) > 200:
            r_cems_only = hourly_ols_cluster_hac(
                d_co2[ok_c].to_numpy(dtype=np.float64),
                d_gl[ok_c].to_numpy(dtype=np.float64)[:, None],
                date_clusters=g_c["date"].to_numpy(),
                fe_groups=[(g_c["ym"].astype(str) + "_" + g_c["hour"].astype(str)).to_numpy()],
                col_names=["d_gross_load_cems"],
                nw_lags=24,
            )
            cems_stack_only_beta = float(r_cems_only["coefs"]["d_gross_load_cems"]["beta"])
            cems_stack_only_se = float(r_cems_only["coefs"]["d_gross_load_cems"]["se_day"])
        else:
            cems_stack_only_beta, cems_stack_only_se = np.nan, np.nan

        # Implied net CO2 under constant official EPA Non-Baseload rate: NB_rate * (1/RTE - 1)
        # (Exact physical round-trip loss floor when marginal intensity is flat across hours!)
        nb_eff = nb_dom if np.isfinite(nb_dom) else nb_nbr
        nb_loss_net = float(nb_eff * (1.0 / float(r["rte"]) - 1.0)) if np.isfinite(nb_eff) else np.nan

        indep_rows.append(
            {
                "ba": ba,
                "dis_gwh": float(r["dis_gwh_cems_window"]),
                "cems_mef_avg_kg_mwh": float(0.5 * (r["mef_cems_chg_kg_mwh"] + r["mef_cems_dis_kg_mwh"])),
                "cems_net_kg_mwh": float(r["net_cems_kg_mwh"]),
                "egrid_nonbaseload_dom_kg_mwh": float(nb_dom) if np.isfinite(nb_dom) else None,
                "egrid_nonbaseload_nbr_kg_mwh": float(nb_nbr) if np.isfinite(nb_nbr) else None,
                "egrid_nonbaseload_rte_loss_net_kg_mwh": nb_loss_net if np.isfinite(nb_loss_net) else None,
                "cems_internal_stack_slope_kg_mwh": cems_stack_only_beta if np.isfinite(cems_stack_only_beta) else None,
                "cems_internal_stack_se": cems_stack_only_se if np.isfinite(cems_stack_only_se) else None,
            }
        )

    df_ind = pd.DataFrame(indep_rows)
    # Cross-grid correlation between CEMS-estimated average MEF and official EPA eGRID Non-Baseload CO2 rate
    v_nb = df_ind.dropna(subset=["egrid_nonbaseload_dom_kg_mwh", "cems_mef_avg_kg_mwh"])
    # Exclude PGE (hydro-dominated grid where CEMS fossil share is tiny and eGRID NB only covers combustion units)
    v_nb_th = v_nb[v_nb["ba"] != "PGE"]
    r_cems_vs_egrid_nb_all = float(v_nb["cems_mef_avg_kg_mwh"].corr(v_nb["egrid_nonbaseload_dom_kg_mwh"]))
    r_cems_vs_egrid_nb_thermal = float(v_nb_th["cems_mef_avg_kg_mwh"].corr(v_nb_th["egrid_nonbaseload_dom_kg_mwh"]))

    # Fleet-weighted net CO2 implied purely by official EPA eGRID Non-Baseload rates (pure round-trip loss floor!)
    nb_fleet_kt = float(
        sum(
            (row["egrid_nonbaseload_rte_loss_net_kg_mwh"] or 0.0) * row["dis_gwh"] / 1000.0
            for row in indep_rows
            if row["egrid_nonbaseload_rte_loss_net_kg_mwh"] is not None
        )
    )
    nb_fleet_kg = float(1000.0 * nb_fleet_kt / sum(row["dis_gwh"] for row in indep_rows if row["egrid_nonbaseload_rte_loss_net_kg_mwh"] is not None))

    # (c) Direct Metered Hourly Battery-Dispatch CEMS Regression (dCO2_CEMS on dBESS_MW controlling for dLoad, dSolar, dWind, dImp)
    direct_bess_cems = {}
    for ba in ["CISO", "ERCO", "AZPS", "MISO"]:
        g = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy()
        dt_s = g["utc_start"].diff().dt.total_seconds()
        d_co2 = g["co2_kg"].diff()
        d_bess = g["bess_clean"].diff()
        d_load = g["demand_use"].diff()
        d_sol = g["solar_use"].diff()
        d_wnd = g["wind_use"].diff()
        d_imp = g["net_imports_use"].diff()
        ok = (
            (dt_s == 3600.0)
            & d_co2.notna()
            & d_bess.notna()
            & d_load.notna()
            & d_sol.notna()
            & d_wnd.notna()
            & d_imp.notna()
        )
        g_o = g[ok.values]
        X = np.column_stack(
            [
                d_bess[ok].to_numpy(dtype=np.float64),
                d_load[ok].to_numpy(dtype=np.float64),
                d_sol[ok].to_numpy(dtype=np.float64),
                d_wnd[ok].to_numpy(dtype=np.float64),
                d_imp[ok].to_numpy(dtype=np.float64),
            ]
        )
        rr = hourly_ols_cluster_hac(
            d_co2[ok].to_numpy(dtype=np.float64),
            X,
            date_clusters=g_o["date"].to_numpy(),
            fe_groups=[(g_o["ym"].astype(str) + "_" + g_o["hour"].astype(str)).to_numpy()],
            col_names=["d_bess_mw", "d_load_mw", "d_solar_mw", "d_wind_mw", "d_imp_mw"],
            nw_lags=24,
        )
        direct_bess_cems[ba] = {
            "n_hours": len(g_o),
            "d_bess_beta_kg_mwh": float(rr["coefs"]["d_bess_mw"]["beta"]),
            "d_bess_se_day": float(rr["coefs"]["d_bess_mw"]["se_day"]),
            "d_bess_t_day": float(rr["coefs"]["d_bess_mw"]["t_day"]),
            "d_load_beta_kg_mwh": float(rr["coefs"]["d_load_mw"]["beta"]),
            "d_load_se_day": float(rr["coefs"]["d_load_mw"]["se_day"]),
        }
        print(
            f"  [Direct CEMS on dBESS: {ba}] dCO2/dBESS = {direct_bess_cems[ba]['d_bess_beta_kg_mwh']:+.1f} kg/MWh "
            f"(SE={direct_bess_cems[ba]['d_bess_se_day']:.1f}, t={direct_bess_cems[ba]['d_bess_t_day']:+.2f}; "
            f"dCO2/dLoad = {direct_bess_cems[ba]['d_load_beta_kg_mwh']:+.1f})",
            flush=True,
        )

    print(
        f"  [EPA eGRID Non-Baseload Check] r(CEMS MEF vs eGRID NB): thermal={r_cems_vs_egrid_nb_thermal:.3f} "
        f"(all={r_cems_vs_egrid_nb_all:.3f}) | Pure eGRID NB round-trip floor = +{nb_fleet_kg:.1f} kg/MWh (+{nb_fleet_kt/1000:.2f} Mt CO2)",
        flush=True,
    )

    # ------------------------------------------------------------------
    # PART 3: CROSS-REGIONAL MECHANISM VALIDATION — ERCOT (ERCO) & MULTI-GRID
    #         INTERIOR RENEWABLE-PENETRATION CEMS MEF STRATIFICATION
    # ------------------------------------------------------------------
    print("[03b.4] Running Cross-Regional Renewable-Penetration CEMS MEF Stratification (CISO, ERCO, AZPS, MISO)...", flush=True)
    cross_region_strat = {}
    ren_bins = [
        ("<20%", 0.0, 0.20),
        ("20-40%", 0.20, 0.40),
        ("40-60%", 0.40, 0.60),
        (">60%", 0.60, 5.0),
    ]
    for ba in ["CISO", "ERCO", "AZPS", "MISO"]:
        g = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy()
        g["ren_mw"] = g["solar_use"].fillna(0.0) + g["wind_use"].fillna(0.0)
        g["ren_share"] = g["ren_mw"] / np.maximum(g["demand_use"].fillna(1.0), 100.0)
        g["chg_mw"] = np.maximum(-g["bess_clean"].fillna(0.0), 0.0)
        g["dis_mw"] = np.maximum(g["bess_clean"].fillna(0.0), 0.0)
        g["dt_sec"] = g["utc_start"].diff().dt.total_seconds()
        g["ren_prev"] = g["ren_share"].shift(1)
        g["d_co2"] = g["co2_kg"].diff()
        g["d_coal_co2"] = g["coal_co2_kg"].diff()
        g["d_ng_co2"] = g["ngcc_co2_kg"].diff() + g["ngct_co2_kg"].diff()
        g["d_disp"] = g["disp_dom"].diff()
        g["d_net_load"] = (g["demand_use"] - g["ren_mw"] - g["bess_clean"].fillna(0.0)).diff()
        g["ym_hr"] = g["ym"].astype(str) + "_" + g["hour"].astype(str)

        tot_chg = max(float(g["chg_mw"].sum()), 1.0)
        tot_dis = max(float(g["dis_mw"].sum()), 1.0)
        gd = g[(g["dt_sec"] == 3600.0) & g["d_co2"].notna() & g["d_net_load"].notna() & g["d_disp"].notna()].copy()

        ba_bins = []
        for lbl, lo, hi in ren_bins:
            m_all = (g["ren_share"] >= lo) & (g["ren_share"] < hi)
            m_int = (gd["ren_share"] >= lo) & (gd["ren_share"] < hi) & (gd["ren_prev"] >= lo) & (gd["ren_prev"] < hi)
            sd = gd[m_int]
            pct_chg = 100.0 * float(g.loc[m_all, "chg_mw"].sum()) / tot_chg
            pct_dis = 100.0 * float(g.loc[m_all, "dis_mw"].sum()) / tot_dis
            if len(sd) >= 60:
                # Apply the same deterministic 8x MAD extreme-ramp glitch guard used in Step 03
                xn = sd["d_net_load"].to_numpy(dtype=np.float64)
                med_x = float(np.median(xn))
                mad_x = float(np.median(np.abs(xn - med_x)))
                if mad_x > 1e-6:
                    km = np.abs(xn - med_x) <= 8.0 * 1.4826 * mad_x
                    if int(np.sum(km)) >= 40:
                        sd = sd.iloc[km]
                r_nl = hourly_ols_cluster_hac(
                    sd["d_co2"].to_numpy(dtype=np.float64),
                    sd["d_net_load"].to_numpy(dtype=np.float64)[:, None],
                    date_clusters=sd["date"].to_numpy(),
                    fe_groups=[sd["ym_hr"].to_numpy()],
                    col_names=["d_net_load"],
                    nw_lags=24,
                )
                r_dp = hourly_ols_cluster_hac(
                    sd["d_co2"].to_numpy(dtype=np.float64),
                    sd["d_disp"].to_numpy(dtype=np.float64)[:, None],
                    date_clusters=sd["date"].to_numpy(),
                    fe_groups=[sd["ym_hr"].to_numpy()],
                    col_names=["d_disp"],
                    nw_lags=24,
                )
                r_cl = hourly_ols_cluster_hac(
                    sd["d_coal_co2"].to_numpy(dtype=np.float64),
                    sd["d_net_load"].to_numpy(dtype=np.float64)[:, None],
                    date_clusters=sd["date"].to_numpy(),
                    fe_groups=[sd["ym_hr"].to_numpy()],
                    col_names=["d_net_load"],
                    nw_lags=24,
                )
                ba_bins.append(
                    {
                        "bin": lbl,
                        "n_hours": int(m_all.sum()),
                        "n_interior_hours": len(sd),
                        "pct_chg": float(pct_chg),
                        "pct_dis": float(pct_dis),
                        "mef_dom_netload_kg_mwh": float(r_nl["coefs"]["d_net_load"]["beta"]),
                        "se_netload": float(r_nl["coefs"]["d_net_load"]["se_day"]),
                        "mef_dom_disp_kg_mwh": float(r_dp["coefs"]["d_disp"]["beta"]),
                        "se_disp": float(r_dp["coefs"]["d_disp"]["se_day"]),
                        "coal_mef_netload_kg_mwh": float(r_cl["coefs"]["d_net_load"]["beta"]),
                    }
                )
            else:
                ba_bins.append(
                    {
                        "bin": lbl,
                        "n_hours": int(m_all.sum()),
                        "n_interior_hours": len(sd),
                        "pct_chg": float(pct_chg),
                        "pct_dis": float(pct_dis),
                        "mef_dom_netload_kg_mwh": None,
                        "se_netload": None,
                        "mef_dom_disp_kg_mwh": None,
                        "se_disp": None,
                        "coal_mef_netload_kg_mwh": None,
                    }
                )
        cross_region_strat[ba] = ba_bins
        summary_str = " | ".join(
            f"{b['bin']}: {b['mef_dom_netload_kg_mwh']:.0f} (chg {b['pct_chg']:.0f}%)"
            if b["mef_dom_netload_kg_mwh"] is not None
            else f"{b['bin']}: n<60"
            for b in ba_bins
        )
        print(f"  [Ren-Pen Strat {ba}] {summary_str}", flush=True)

    # ------------------------------------------------------------------
    # PART 4: CONGESTION-CONSTRAINED CARBON BREAK-EVEN FRONTIER
    #         (Sweeping scale kappa in [0.1x..3.0x] and accessible curtailment share tau_grid!)
    # ------------------------------------------------------------------
    print("[03b.5] Computing Congestion-Constrained Carbon Break-Even Frontier...", flush=True)
    ciso_r = next(r for r in r3["ba_carbon_table"] if r["ba"] == "CISO")
    c_chg = cc["chg_mw"].to_numpy(dtype=np.float64)
    c_sys = cc["system_curt_mw"].fillna(0.0).to_numpy(dtype=np.float64)
    c_loc = cc["local_curt_mw"].fillna(0.0).to_numpy(dtype=np.float64)

    frontier_grid = []
    # tau_loc_access = fraction of local congestion curtailment unlocked by transmission/co-siting (0.0=system-only, 0.5=partial relief, 1.0=zero congestion)
    for tau_loc in [0.0, 0.25, 0.50, 1.00]:
        q_eff = c_sys + tau_loc * c_loc
        curve = []
        for kappa in [0.10, 0.25, 0.50, 0.75, 1.00, 1.50, 2.00, 3.00]:
            dc = kappa * c_chg
            rho_k = float(np.sum(np.minimum(dc, q_eff)) / max(float(np.sum(dc)), 1.0))
            net_k = float(
                ((1.0 - rho_k) * float(ciso_r["mef_cems_chg_kg_mwh"])) / float(ciso_r["rte"])
                - float(ciso_r["mef_cems_dis_kg_mwh"])
            )
            curve.append(
                {
                    "kappa": float(kappa),
                    "incremental_gw_equiv": float(kappa * 17.34),
                    "rho_res": rho_k,
                    "implied_net_co2_kg_mwh": net_k,
                    "net_abating": bool(net_k < 0.0),
                }
            )
        frontier_grid.append({"tau_local_access": float(tau_loc), "curve": curve})

    # Also record exact Proposition 2 check: which grids satisfy MEF_chg >= MEF_dis vs MEF_dis/MEF_chg < 1/eta
    prop2_exact_audit = {
        "n_grids_alpha_star_positive": int(sum(1 for r in r3["ba_carbon_table"] if r["alpha_star_cems"] > 0.0)),
        "n_grids_mef_chg_ge_mef_dis": int(
            sum(1 for r in r3["ba_carbon_table"] if r["mef_cems_chg_kg_mwh"] >= r["mef_cems_dis_kg_mwh"])
        ),
        "grids_mef_chg_ge_mef_dis": [
            r["ba"] for r in r3["ba_carbon_table"] if r["mef_cems_chg_kg_mwh"] >= r["mef_cems_dis_kg_mwh"]
        ],
        "grids_mef_dis_gt_chg_yet_below_inv_eta": [
            r["ba"]
            for r in r3["ba_carbon_table"]
            if (r["mef_cems_dis_kg_mwh"] > r["mef_cems_chg_kg_mwh"]) and (r["alpha_star_cems"] > 0.0)
        ],
    }
    print(
        f"  [Prop 2 Exact Audit] alpha*>0: {prop2_exact_audit['n_grids_alpha_star_positive']}/14 | "
        f"MEF_chg>=MEF_dis: {prop2_exact_audit['n_grids_mef_chg_ge_mef_dis']}/14 "
        f"({prop2_exact_audit['grids_mef_chg_ge_mef_dis']})",
        flush=True,
    )

    out = {
        "full_window_joint_14d_bootstrap_1000": {
            "window": "2024-07-01..2026-09-30",
            "tot_dis_twh": pt_full["tot_dis_twh"],
            "tot_aef_mt": pt_full["tot_aef_mt"],
            "B": B_BOOT,
            "block_days": 14,
            "metrics": summary_full_14d,
        },
        "same_window_joint_14d_bootstrap_1000": {
            "window": "2024-07-01..2025-12-31",
            "tot_dis_twh": pt_same["tot_dis_twh"],
            "tot_aef_mt": pt_same["tot_aef_mt"],
            "B": B_BOOT,
            "block_days": 14,
            "metrics": summary_same_14d,
        },
        "independent_mef_validations": {
            "r_cems_vs_egrid_nonbaseload_thermal": r_cems_vs_egrid_nb_thermal,
            "r_cems_vs_egrid_nonbaseload_all": r_cems_vs_egrid_nb_all,
            "egrid_nonbaseload_rte_loss_floor_kg_mwh": nb_fleet_kg,
            "egrid_nonbaseload_rte_loss_floor_mt": float(nb_fleet_kt / 1000.0),
            "by_ba": indep_rows,
            "direct_cems_on_dbess_regressions": direct_bess_cems,
        },
        "cross_regional_ren_penetration_stratification": cross_region_strat,
        "congestion_constrained_carbon_frontier": frontier_grid,
        "proposition_2_exact_inequality_audit": prop2_exact_audit,
        "elapsed_sec": float(time.time() - t0),
    }

    sha = save_json_lf(RES_DIR / "03b_nature_energy_v4_extensions.json", out)
    print(f"[DONE STEP 03b] Saved results/03b_nature_energy_v4_extensions.json (SHA-256: {sha})", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
