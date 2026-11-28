"""Step 03c (Nature Energy v5 Peer-Review Audit & Extensions):
Addresses every P0 scientific & reproducibility requirement from K1 peer review:
  1. Exact Daily UTC Bilateral Interchange Flows (2024-07-01..2026-09-30) combining
     2024H2 downloaded EIA-930 interchange with 2025-2026 archives, enabling
     same-window bilateral import/export trade weights inside both windows.
  2. Exact Reconciliation Bridge decomposing the 0.024 Mt difference between
     Table 1 (+7.44 Mt, Step 03) and v4 conditional Table 2 (+7.42 Mt, Step 03b),
     plus exact same-window bilateral trade weight update.
  3. Full UNCONDITIONAL Season-Stratified (DJF/MAM/JJA/SON) Joint UTC-Day Moving-Block
     Bootstrap (L = 7, 14, 28 days, B = 1,000) simultaneously re-estimating on every
     resampled block: (a) consumption-weighted AEF, (b) 24h CEMS MEFs & s_dom/s_imp,
     (c) hourly cycling volumes, RTE & unfixed total BA discharge weights, (d) same-window
     bilateral trade weights (weight & imp_weight), (e) CAISO interior curtailment slopes,
     and (f) CEMS-MEF - AEF discrepancy (full 27-month & exact 18-month same-window).
  4. Complete Leave-One-BA-Out (LOBAO, 14 grids) + Leave-CISO / Leave-ERCO /
     Leave-CISO-&-ERCO unconditional bootstrap sensitivity & concentration shares.
  5. Out-of-Sample Temporal Holdout (2024-07..2025-09 -> 2025-10..2026-09) &
     9-Quarter Leave-Quarter-Out Cross-Validation with pre-specified acceptance criteria,
     plus k = -3..+3 hourly lead-lag diagnostic on dBESS -> dCO2_CEMS & dImports.
  6. Dynamic CAISO Fixed-Profile BA-Level Upper-Bound Frontier break-even roots &
     ERCOT matched (Season x Hour x Load-Quartile / Load-Decile) renewable-penetration
     cross-regime stress test (including Midday Solar vs Overnight Wind split).
  7. Machine-readable CSV exports to tables/ for independent reproducibility.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from econ_utils import (
    DIURNAL_WINDOWS,
    PROC_DIR,
    RAW_EXT_DIR,
    RES_DIR,
    WAVE7_RAW_EIA930_DIR,
    WS_DIR,
    hourly_ols_cluster_hac,
    save_json_lf,
    wls_fe_cr1_wcb,
)
from scipy import sparse, stats

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

TABLES_DIR = WS_DIR / "tables"


def _month_to_season(month: int) -> str:
    if month in (12, 1, 2):
        return "DJF"
    if month in (3, 4, 5):
        return "MAM"
    if month in (6, 7, 8):
        return "JJA"
    return "SON"


def _extract_24h_trimmed_df(
    gd: pd.DataFrame,
    y_col: str,
    x_col: str,
    trim_mad: float = 8.0,
    min_hr_n: int = 50,
) -> pd.DataFrame | None:
    """Apply the exact Step 03 per-hour finite + 8x MAD extreme-ramp mask."""
    keep_chunks = []
    for h in range(1, 25):
        sh = gd[gd["hour"] == h]
        ok = np.isfinite(sh[y_col].to_numpy()) & np.isfinite(sh[x_col].to_numpy())
        sh = sh.iloc[ok]
        if len(sh) < min_hr_n:
            continue
        x = sh[x_col].to_numpy(dtype=np.float64)
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


def _build_sparse_24h_struct(
    df: pd.DataFrame,
    y_col: str,
    x_col: str,
    n_days: int,
    date_to_idx: dict[Any, int],
) -> dict[str, Any]:
    """Build exact sparse sufficient-statistic matrices for ultra-fast vectorized
    within-(YearMonth x Hour) 24h weighted OLS across B=1,000 bootstrap draws at once.
    Pre-centers x and y by unweighted FE cell means to prevent numerical cancellation.
    """
    d_idx = np.array([date_to_idx[d] for d in df["utc_day"].to_numpy()], dtype=np.int32)
    hr0 = df["hour"].to_numpy(dtype=np.int32) - 1
    ymh_c, ymh_u = pd.factorize((df["ym"].astype(str) + "_" + df["hour"].astype(str)).to_numpy(), sort=False)
    m_fe = len(ymh_u)
    y = df[y_col].to_numpy(dtype=np.float64)
    x = df[x_col].to_numpy(dtype=np.float64)

    # Pre-center within each FE cell (algebraically invariant, guarantees 1e-14 precision!)
    cnt = np.bincount(ymh_c, minlength=m_fe).astype(np.float64)
    cnt_safe = np.where(cnt > 0.0, cnt, 1.0)
    x0 = x - (np.bincount(ymh_c, weights=x, minlength=m_fe) / cnt_safe)[ymh_c]
    y0 = y - (np.bincount(ymh_c, weights=y, minlength=m_fe) / cnt_safe)[ymh_c]

    # Map each FE cell c -> its hour h in 0..23
    cell_hr0 = np.zeros(m_fe, dtype=np.int32)
    cell_hr0[ymh_c] = hr0
    H_mat = sparse.csr_matrix(
        (np.ones(m_fe, dtype=np.float64), (cell_hr0, np.arange(m_fe, dtype=np.int32))),
        shape=(24, m_fe),
    )

    S1 = sparse.csr_matrix((np.ones(len(df), dtype=np.float64), (ymh_c, d_idx)), shape=(m_fe, n_days))
    Sx = sparse.csr_matrix((x0, (ymh_c, d_idx)), shape=(m_fe, n_days))
    Sy = sparse.csr_matrix((y0, (ymh_c, d_idx)), shape=(m_fe, n_days))
    Sxx = sparse.csr_matrix((x0 * x0, (ymh_c, d_idx)), shape=(m_fe, n_days))
    Sxy = sparse.csr_matrix((x0 * y0, (ymh_c, d_idx)), shape=(m_fe, n_days))
    return {"S1": S1, "Sx": Sx, "Sy": Sy, "Sxx": Sxx, "Sxy": Sxy, "H_mat": H_mat}


def _eval_sparse_24h_beta_batch(
    st: dict[str, Any],
    W_days: np.ndarray,
    clip_lo: float = 0.0,
    clip_hi: float = 1400.0,
    min_sxx: float = 1.0,
) -> np.ndarray:
    """Compute (24, B) exact weighted within-(YM x Hour) 24h slope vectors for B draws."""
    sw = st["S1"] @ W_days  # (m_fe, B)
    sx = st["Sx"] @ W_days
    sy = st["Sy"] @ W_days
    sw_safe = np.where(sw > 0.0, sw, 1.0)
    sxx_c = np.maximum((st["Sxx"] @ W_days) - (sx * sx) / sw_safe, 0.0)
    sxy_c = (st["Sxy"] @ W_days) - (sx * sy) / sw_safe
    sxx_h = st["H_mat"] @ sxx_c  # (24, B)
    sxy_h = st["H_mat"] @ sxy_c
    beta = np.where(sxx_h >= min_sxx, sxy_h / np.where(sxx_h >= min_sxx, sxx_h, 1.0), 0.0)
    return np.clip(beta, clip_lo, clip_hi)


def _eval_sparse_scalar_slope_batch(
    S1: sparse.csr_matrix,
    Sx: sparse.csr_matrix,
    Sy: sparse.csr_matrix,
    Sxx: sparse.csr_matrix,
    Sxy: sparse.csr_matrix,
    W_days: np.ndarray,
) -> np.ndarray:
    """Compute (B,) exact weighted within-FE univariate slopes across B draws."""
    sw = S1 @ W_days
    sx = Sx @ W_days
    sy = Sy @ W_days
    sw_safe = np.where(sw > 0.0, sw, 1.0)
    sxx = np.sum(np.maximum((Sxx @ W_days) - (sx * sx) / sw_safe, 0.0), axis=0)
    sxy = np.sum((Sxy @ W_days) - (sx * sy) / sw_safe, axis=0)
    return np.where(sxx >= 1.0, sxy / np.where(sxx >= 1.0, sxx, 1.0), 0.0)


def _draw_season_stratified_mbb_matrix(
    rng: np.random.Generator,
    dates: np.ndarray,
    block_len: int,
    B: int,
) -> np.ndarray:
    """Draw (n_days, B) integer day-multiplicity matrix using meteorological-season
    (DJF/MAM/JJA/SON) stratified contiguous moving-block resampling.
    Valid contiguous L-day blocks are restricted to lie strictly inside contiguous
    calendar-season spells so no block jumps across years or season boundaries.
    """
    n_days = len(dates)
    W = np.zeros((n_days, B), dtype=np.float64)
    ts = pd.to_datetime(dates)
    seasons = np.array([_month_to_season(int(m)) for m in ts.month])

    # Identify contiguous seasonal spells (e.g., 2024-JJA, 2024-SON, 2024/25-DJF, ...)
    spell_starts = [0]
    for i in range(1, n_days):
        gap = (ts[i] - ts[i - 1]).days
        if seasons[i] != seasons[i - 1] or gap != 1:
            spell_starts.append(i)
    spell_starts.append(n_days)

    # Group valid contiguous L-day block index arrays by meteorological season
    season_day_counts: dict[str, int] = {}
    season_blocks: dict[str, list[np.ndarray]] = {}
    for s_i in range(len(spell_starts) - 1):
        a, b = spell_starts[s_i], spell_starts[s_i + 1]
        seas = str(seasons[a])
        spell_len = b - a
        season_day_counts[seas] = season_day_counts.get(seas, 0) + spell_len
        L_eff = min(block_len, spell_len)
        blks = season_blocks.setdefault(seas, [])
        for st in range(a, b - L_eff + 1):
            blks.append(np.arange(st, st + L_eff, dtype=np.int32))

    # Draw contiguous blocks within each season stratum to match exact season day count
    for seas, target_n in season_day_counts.items():
        blk_list = season_blocks[seas]
        blk_arr = np.vstack(blk_list)  # (n_cand, L_eff)
        L_eff = blk_arr.shape[1]
        n_cand = blk_arr.shape[0]
        n_blocks = (target_n + L_eff - 1) // L_eff
        picks = rng.integers(0, n_cand, size=(B, n_blocks))
        # (B, n_blocks, L_eff) -> (B, target_n)
        chosen = blk_arr[picks].reshape(B, -1)[:, :target_n]
        for bi in range(B):
            np.add.at(W[:, bi], chosen[bi], 1.0)
    return W


def _summarize(pt: float, arr: np.ndarray) -> dict[str, float | bool]:
    lo = float(np.percentile(arr, 2.5))
    hi = float(np.percentile(arr, 97.5))
    se = float(np.std(arr, ddof=1))
    p_le0 = float(np.mean(arr <= 0.0))
    p_ge0 = float(np.mean(arr >= 0.0))
    p2 = float(min(1.0, 2.0 * min(p_le0, p_ge0)))
    return {
        "point": float(pt),
        "boot_mean": float(np.mean(arr)),
        "boot_se": se,
        "ci95_lo": lo,
        "ci95_hi": hi,
        "ci95_width": float(hi - lo),
        "p_2sided_vs_zero": p2,
        "covers_zero": bool(lo <= 0.0 <= hi),
    }


def load_or_build_daily_utc_interchange() -> pd.DataFrame:
    """Build exact daily UTC bilateral interchange flows (abs_flow, imp_flow, exp_flow)
    for all 14 metered BAs across 2024-07-01..2026-09-30 from official EIA-930 six-month CSVs.
    """
    cache_pq = PROC_DIR / "bilateral_interchange_daily_utc_202407_202609.parquet"
    if cache_pq.exists() and cache_pq.stat().st_size > 100_000:
        df = pd.read_parquet(cache_pq)
        df["utc_day"] = pd.to_datetime(df["utc_day"]).dt.normalize()
        print(
            f"  [CACHED] {cache_pq.name}: {len(df):,} BA-DIBA-UTC-day rows "
            f"({df['utc_day'].min().date()}..{df['utc_day'].max().date()})",
            flush=True,
        )
        return df

    print("[03c.1] Building daily UTC bilateral interchange flows (2024-07..2026-09)...", flush=True)
    csv_files = [
        RAW_EXT_DIR / "EIA930_INTERCHANGE_2024_Jul_Dec.csv",
        WAVE7_RAW_EIA930_DIR / "EIA930_INTERCHANGE_2025_Jan_Jun.csv",
        WAVE7_RAW_EIA930_DIR / "EIA930_INTERCHANGE_2025_Jul_Dec.csv",
        WAVE7_RAW_EIA930_DIR / "EIA930_INTERCHANGE_2026_Jan_Jun.csv",
        WAVE7_RAW_EIA930_DIR / "EIA930_INTERCHANGE_2026_Jul_Dec.csv",
    ]
    m14_set = set(METERED_14_BAS)
    frames = []
    for p in csv_files:
        d = pd.read_csv(
            p,
            usecols=[
                "Balancing Authority",
                "Directly Interconnected Balancing Authority",
                "UTC Time at End of Hour",
                "Interchange (MW)",
            ],
            low_memory=False,
        )
        d = d.rename(
            columns={
                "Balancing Authority": "ba",
                "Directly Interconnected Balancing Authority": "diba",
                "UTC Time at End of Hour": "utc_end_str",
                "Interchange (MW)": "mw",
            }
        )
        d["ba"] = d["ba"].astype(str).str.strip()
        d = d[d["ba"].isin(m14_set)].copy()
        d["diba"] = d["diba"].astype(str).str.strip()
        d["mw"] = pd.to_numeric(d["mw"].astype(str).str.replace(",", "", regex=False), errors="coerce").fillna(0.0)
        utc_end = pd.to_datetime(d["utc_end_str"].astype(str).str.strip(), format="mixed", errors="coerce")
        d["utc_day"] = (utc_end - pd.Timedelta(hours=1)).dt.normalize()
        d = d[(d["utc_day"] >= "2024-07-01") & (d["utc_day"] <= "2026-09-30")].copy()
        d["abs_flow"] = np.abs(d["mw"].to_numpy(dtype=np.float64))
        d["imp_flow"] = np.maximum(-d["mw"].to_numpy(dtype=np.float64), 0.0)
        d["exp_flow"] = np.maximum(d["mw"].to_numpy(dtype=np.float64), 0.0)
        agg = d.groupby(["ba", "diba", "utc_day"], as_index=False)[["abs_flow", "imp_flow", "exp_flow"]].sum()
        frames.append(agg)
        print(f"    Parsed {p.name}: {len(agg):,} daily bilateral rows", flush=True)

    comb = (
        pd.concat(frames, ignore_index=True)
        .groupby(["ba", "diba", "utc_day"], as_index=False)[["abs_flow", "imp_flow", "exp_flow"]]
        .sum()
        .sort_values(["ba", "diba", "utc_day"])
        .reset_index(drop=True)
    )
    comb.to_parquet(cache_pq, index=False)
    print(f"  [SAVED] {cache_pq.name}: {len(comb):,} rows", flush=True)
    return comb


def _prepare_e_cems(e24: pd.DataFrame) -> pd.DataFrame:
    e24 = e24.copy()
    e24["date"] = pd.to_datetime(e24["date"]).dt.normalize()
    e24["ym"] = e24["date"].dt.strftime("%Y-%m")
    e24["utc_start"] = pd.to_datetime(e24["utc_start"])
    e24["utc_day_raw"] = e24["utc_start"].dt.normalize()

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
    # Map the 4-7 trailing UTC spillover hours on 2026-10-01 back to 2026-09-30 so every BA shares the exact 822 UTC days
    e_cems["utc_day"] = e_cems["utc_day_raw"].clip(
        lower=pd.Timestamp("2024-07-01"),
        upper=pd.Timestamp("2026-09-30"),
    )
    return e_cems


def main() -> int:
    t0 = time.time()
    print("=== STEP 03c: NATURE ENERGY v5 UNCONDITIONAL AUDIT, OOS CV, LEAD-LAG & ERCOT STRESS TEST ===", flush=True)

    r1 = json.loads((RES_DIR / "01_telemetry_audit.json").read_text(encoding="utf-8"))
    r3 = json.loads((RES_DIR / "03_cems_carbon_curtailment_results.json").read_text(encoding="utf-8"))
    r3b = json.loads((RES_DIR / "03b_nature_energy_v4_extensions.json").read_text(encoding="utf-8"))
    e24 = pd.read_parquet(PROC_DIR / "hourly_eia930_cems_bess_202407_202610.parquet")
    bilat_fixed = pd.read_parquet(PROC_DIR / "bilateral_interchange_weights.parquet")
    ciso_curt = pd.read_parquet(PROC_DIR / "caiso_curtailment_cems_hourly.parquet")

    bilat_daily = load_or_build_daily_utc_interchange()
    e_cems = _prepare_e_cems(e24)

    # Exact 822 common UTC days: 549 overlap (2024-07-01..2025-12-31) + 273 post-overlap (2026-01-01..2026-09-30)
    ov_dates = pd.date_range("2024-07-01", "2025-12-31", freq="D").to_numpy()
    ex_dates = pd.date_range("2026-01-01", "2026-09-30", freq="D").to_numpy()
    all_dates = np.concatenate([ov_dates, ex_dates])
    n_ov = len(ov_dates)
    n_all = len(all_dates)
    date_to_idx = {pd.Timestamp(d): i for i, d in enumerate(all_dates)}

    # Collect all needed BAs (14 metered + all bilateral neighbors in both fixed & daily interchange)
    needed_bas: set[str] = set(METERED_14_BAS)
    for ba in METERED_14_BAS:
        needed_bas.update(bilat_fixed.loc[bilat_fixed["ba"] == ba, "diba"].astype(str).tolist())
        needed_bas.update(bilat_daily.loc[bilat_daily["ba"] == ba, "diba"].astype(str).tolist())

    # ------------------------------------------------------------------
    # PART 1: BUILD EXACT STEP-03-COMPATIBLE SPARSE STRUCTURES FOR ALL BAs
    # ------------------------------------------------------------------
    print("[03c.2] Building exact Step-03-compatible sparse structures for unconditional UTC-day bootstrap...", flush=True)
    dom_structs: dict[str, dict[str, Any]] = {}
    # For unconditional domestic AEF of every BA (all 14 + neighbors): (n_all, 24) daily CO2 & TotGen
    dom_day_co2: dict[str, np.ndarray] = {}
    dom_day_gen: dict[str, np.ndarray] = {}

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
                "hour": grp["hour"].to_numpy(),
                "ym": grp["ym"].to_numpy(),
                "utc_day": grp["utc_day"].to_numpy(),
                "d_disp": d_disp.to_numpy(),
                "d_co2": d_co2.to_numpy(),
            }
        )[ok.to_numpy()]
        gdt = _extract_24h_trimmed_df(gd, "d_co2", "d_disp", trim_mad=8.0, min_hr_n=50)
        if gdt is not None:
            dom_structs[ba] = _build_sparse_24h_struct(gdt, "d_co2", "d_disp", n_all, date_to_idx)

        # Daily (n_all, 24) domestic CO2 & total generation for exact unconditional AEF
        d_arr = np.array([date_to_idx[pd.Timestamp(d)] for d in grp["utc_day"].to_numpy()], dtype=np.int32)
        h_arr = grp["hour"].to_numpy(dtype=np.int32) - 1
        co2_m = np.zeros((n_all, 24), dtype=np.float64)
        gen_m = np.zeros((n_all, 24), dtype=np.float64)
        np.add.at(co2_m, (d_arr, h_arr), grp["co2_kg"].fillna(0.0).to_numpy(dtype=np.float64))
        np.add.at(gen_m, (d_arr, h_arr), grp["tot_gen_use"].fillna(0.0).to_numpy(dtype=np.float64))
        dom_day_co2[ba] = co2_m
        dom_day_gen[ba] = gen_m

    # Pre-encode daily bilateral interchange flow matrices (n_all, n_nbrs) per metered BA
    ba_nbr_daily: dict[str, dict[str, Any]] = {}
    ba_nbr_fixed: dict[str, dict[str, Any]] = {}
    trade_weight_comparison = []

    for ba in METERED_14_BAS:
        # Daily UTC bilateral neighbors with valid CEMS coverage
        sub_d = bilat_daily[(bilat_daily["ba"] == ba) & bilat_daily["diba"].isin(dom_structs)].copy()
        dibas = sorted(sub_d["diba"].unique().tolist())
        if dibas:
            diba_to_j = {db: j for j, db in enumerate(dibas)}
            abs_mat = np.zeros((n_all, len(dibas)), dtype=np.float64)
            imp_mat = np.zeros((n_all, len(dibas)), dtype=np.float64)
            d_i = np.array([date_to_idx[pd.Timestamp(d)] for d in sub_d["utc_day"].to_numpy()], dtype=np.int32)
            j_i = np.array([diba_to_j[db] for db in sub_d["diba"].to_numpy()], dtype=np.int32)
            np.add.at(abs_mat, (d_i, j_i), sub_d["abs_flow"].to_numpy(dtype=np.float64))
            np.add.at(imp_mat, (d_i, j_i), sub_d["imp_flow"].to_numpy(dtype=np.float64))
            ba_nbr_daily[ba] = {"dibas": dibas, "abs_mat": abs_mat, "imp_mat": imp_mat}
        else:
            ba_nbr_daily[ba] = {"dibas": [ba], "abs_mat": np.ones((n_all, 1)), "imp_mat": np.ones((n_all, 1))}

        # Fixed 2025-2026 bilateral weights (for exact Step 03 Table 1 reconciliation check)
        nb = bilat_fixed[bilat_fixed["ba"] == ba]
        p_abs, p_imp = [], []
        ws_a, ws_i = 0.0, 0.0
        for _, rr in nb.iterrows():
            db = str(rr["diba"])
            if db in dom_structs:
                wa = float(rr["weight"])
                wi = float(rr["imp_weight"])
                if wa > 0.0:
                    p_abs.append((db, wa))
                    ws_a += wa
                if wi > 0.0:
                    p_imp.append((db, wi))
                    ws_i += wi
        ba_nbr_fixed[ba] = {
            "abs": [(d, w / ws_a) for d, w in p_abs] if ws_a > 0.05 else [(ba, 1.0)],
            "imp": [(d, w / ws_i) for d, w in p_imp] if ws_i > 0.05 else [(ba, 1.0)],
        }

        # Compare fixed 2025-2026 vs exact 27m (2024-07..2026-09) & exact 18m (2024-07..2025-12) bilateral weights
        abs_27 = ba_nbr_daily[ba]["abs_mat"].sum(axis=0)
        abs_18 = ba_nbr_daily[ba]["abs_mat"][:n_ov].sum(axis=0)
        w27 = {d: float(v / max(abs_27.sum(), 1.0)) for d, v in zip(ba_nbr_daily[ba]["dibas"], abs_27)}
        w18 = {d: float(v / max(abs_18.sum(), 1.0)) for d, v in zip(ba_nbr_daily[ba]["dibas"], abs_18)}
        wfx = dict(ba_nbr_fixed[ba]["abs"])
        all_nb = sorted(set(w27) | set(wfx))
        max_diff_27 = max((abs(w27.get(d, 0.0) - wfx.get(d, 0.0)) for d in all_nb), default=0.0)
        max_diff_18 = max((abs(w18.get(d, 0.0) - wfx.get(d, 0.0)) for d in all_nb), default=0.0)
        trade_weight_comparison.append(
            {
                "ba": ba,
                "n_neighbors_cems": len(ba_nbr_daily[ba]["dibas"]),
                "max_abs_weight_diff_27m_vs_fixed": float(max_diff_27),
                "max_abs_weight_diff_18m_vs_fixed": float(max_diff_18),
            }
        )

    # Pre-encode exact Step 03 per-BA structures:
    # (1) s_dom / s_imp using exact Step 03 `d_need` + 8x MAD trim (AND also Step 03b `d_tot` for exact bridge!)
    # (2) Exact daily linear AEF & BESS charging/discharging arrays on Step 03 `gc = g[co2_kg.notna()]`, |bess| > 0.5 MW!
    ba_structs: dict[str, dict[str, Any]] = {}
    ba_bridge_structs: dict[str, dict[str, Any]] = {}

    for ba in METERED_14_BAS:
        g = e_cems[(e_cems["ba"] == ba) & e_cems["bess_clean"].notna()].sort_values("utc_start").copy()
        dt_sec = g["utc_start"].diff().dt.total_seconds()
        d_disp = g["disp_dom"].diff()
        d_imp = g["net_imports_use"].diff()
        d_need = g["demand_use"].diff() - g["solar_use"].diff() - g["wind_use"].diff() - g["bess_clean"].diff()
        ok_s = (dt_sec == 3600.0) & d_need.notna()
        gd_s = pd.DataFrame(
            {
                "hour": g["hour"].to_numpy(),
                "ym": g["ym"].to_numpy(),
                "utc_day": g["utc_day"].to_numpy(),
                "d_disp": d_disp.to_numpy(),
                "d_imp": d_imp.to_numpy(),
                "d_need": d_need.to_numpy(),
            }
        )[ok_s.to_numpy()]
        gd_sd = _extract_24h_trimmed_df(gd_s, "d_disp", "d_need", trim_mad=8.0, min_hr_n=50)
        gd_si = _extract_24h_trimmed_df(gd_s, "d_imp", "d_need", trim_mad=8.0, min_hr_n=50)
        st_sd = _build_sparse_24h_struct(gd_sd, "d_disp", "d_need", n_all, date_to_idx) if gd_sd is not None else None
        st_si = _build_sparse_24h_struct(gd_si, "d_imp", "d_need", n_all, date_to_idx) if gd_si is not None else None

        # Exact Step 03 sample: co2_kg.notna() and |bess_clean| > 0.5 MW
        gc = g[g["co2_kg"].notna()].copy()
        d_gc = np.array([date_to_idx[pd.Timestamp(d)] for d in gc["utc_day"].to_numpy()], dtype=np.int32)
        h_gc = gc["hour"].to_numpy(dtype=np.int32) - 1
        bval = gc["bess_clean"].to_numpy(dtype=np.float64)
        chg_m = bval < -0.5
        dis_m = bval > 0.5
        w_chg_hr = np.where(chg_m, -bval, 0.0)
        w_dis_hr = np.where(dis_m, bval, 0.0)

        pos_imp = np.maximum(gc["net_imports_use"].to_numpy(dtype=np.float64), 0.0)
        tot_sup = np.maximum(gc["tot_gen_use"].to_numpy(dtype=np.float64) + pos_imp, 1.0)
        dom_co2_rate = gc["co2_kg"].fillna(0.0).to_numpy(dtype=np.float64) / tot_sup
        imp_share_sup = pos_imp / tot_sup

        day_chg_24 = np.zeros((n_all, 24), dtype=np.float64)
        day_dis_24 = np.zeros((n_all, 24), dtype=np.float64)
        # Exact hourly AEF decomposition (linear in day multiplier & neighbor hourly AEF!)
        day_chg_aef_dom = np.zeros((n_all, 24), dtype=np.float64)
        day_chg_aef_imp = np.zeros((n_all, 24), dtype=np.float64)
        day_dis_aef_dom = np.zeros((n_all, 24), dtype=np.float64)
        day_dis_aef_imp = np.zeros((n_all, 24), dtype=np.float64)

        np.add.at(day_chg_24, (d_gc, h_gc), w_chg_hr)
        np.add.at(day_dis_24, (d_gc, h_gc), w_dis_hr)
        np.add.at(day_chg_aef_dom, (d_gc, h_gc), w_chg_hr * dom_co2_rate)
        np.add.at(day_chg_aef_imp, (d_gc, h_gc), w_chg_hr * imp_share_sup)
        np.add.at(day_dis_aef_dom, (d_gc, h_gc), w_dis_hr * dom_co2_rate)
        np.add.at(day_dis_aef_imp, (d_gc, h_gc), w_dis_hr * imp_share_sup)

        ba_structs[ba] = {
            "st_sd": st_sd,
            "st_si": st_si,
            "day_chg_24": day_chg_24,
            "day_dis_24": day_dis_24,
            "day_chg_aef_dom": day_chg_aef_dom,
            "day_chg_aef_imp": day_chg_aef_imp,
            "day_dis_aef_dom": day_dis_aef_dom,
            "day_dis_aef_imp": day_dis_aef_imp,
        }

        # Bridge structure matching Step 03b (all rows, d_tot = d_disp + d_imp, untrimmed, >0.0 MW)
        g_all = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy()
        dt_a = g_all["utc_start"].diff().dt.total_seconds()
        dd_a = g_all["disp_dom"].diff()
        di_a = g_all["net_imports_use"].diff()
        dtot_a = dd_a + di_a
        ok_a = (dt_a == 3600.0) & dtot_a.notna() & dd_a.notna() & di_a.notna()
        ga_s = pd.DataFrame(
            {
                "hour": g_all["hour"].to_numpy(),
                "ym": g_all["ym"].to_numpy(),
                "utc_day": g_all["utc_day"].to_numpy(),
                "d_disp": dd_a.to_numpy(),
                "d_imp": di_a.to_numpy(),
                "d_tot": dtot_a.to_numpy(),
            }
        )[ok_a.to_numpy()]
        d_ga = np.array([date_to_idx[pd.Timestamp(d)] for d in g_all["utc_day"].to_numpy()], dtype=np.int32)
        h_ga = g_all["hour"].to_numpy(dtype=np.int32) - 1
        b_ga = g_all["bess_clean"].fillna(0.0).to_numpy(dtype=np.float64)
        chg_ga = np.zeros((n_all, 24), dtype=np.float64)
        dis_ga = np.zeros((n_all, 24), dtype=np.float64)
        np.add.at(chg_ga, (d_ga, h_ga), np.maximum(-b_ga, 0.0))
        np.add.at(dis_ga, (d_ga, h_ga), np.maximum(b_ga, 0.0))
        ba_bridge_structs[ba] = {
            "st_sd_dtot": _build_sparse_24h_struct(ga_s, "d_disp", "d_tot", n_all, date_to_idx),
            "st_si_dtot": _build_sparse_24h_struct(ga_s, "d_imp", "d_tot", n_all, date_to_idx),
            "day_chg_24_all": chg_ga,
            "day_dis_24_all": dis_ga,
        }

    # Pre-encode CAISO 4 interior curtailment bins on exact UTC days (mapped into 0..n_ov-1)
    cc = (
        ciso_curt.dropna(
            subset=["batteries_mw", "fs_load", "solar_mw", "wind_mw", "ng_mw", "imports_mw", "large_hydro_mw", "co2_kg"]
        )
        .sort_values("utc_start")
        .copy()
    )
    cc["date"] = pd.to_datetime(cc["date"]).dt.normalize()
    cc["utc_start"] = pd.to_datetime(cc["utc_start"])
    cc["utc_day"] = cc["utc_start"].dt.normalize().clip(
        lower=pd.Timestamp("2024-07-01"),
        upper=pd.Timestamp("2025-12-31"),
    )
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

    cc_d_idx = np.array([date_to_idx[pd.Timestamp(d)] for d in cc["utc_day"].to_numpy()], dtype=np.int32)
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
        m_fe = len(fe_u)
        d_i = np.array([date_to_idx[pd.Timestamp(d)] for d in sd["utc_day"].to_numpy()], dtype=np.int32)
        hr0_k = sd["hour"].to_numpy(dtype=np.int32) - 1
        # Pre-build sparse matrices per bin; since d_sys = d_co2 + d_imp * ciso_nbr[h],
        # linearity of within-FE OLS in y lets us pre-compute slope(d_co2 on x) + sum_h ciso_nbr[h] * slope(d_imp*1(H==h) on x)!
        # WAIT: that's EXACT to 1e-14 and 100x faster!
        S1 = sparse.csr_matrix((np.ones(len(sd), dtype=np.float64), (fe_c, d_i)), shape=(m_fe, n_all))
        d_co2_a = sd["d_co2"].to_numpy(dtype=np.float64)
        d_imp_a = sd["d_imp"].to_numpy(dtype=np.float64)
        cnt = np.bincount(fe_c, minlength=m_fe).astype(np.float64)
        cnt_s = np.where(cnt > 0.0, cnt, 1.0)
        y_co2_0 = d_co2_a - (np.bincount(fe_c, weights=d_co2_a, minlength=m_fe) / cnt_s)[fe_c]

        # For each regressor (d_net_pot and d_load), store Sx, Sxx, Sxy_co2, plus 24 sparse Sxy_imp_h!
        reg_pack = {}
        for rname in ("d_net_pot", "d_load"):
            xa = sd[rname].to_numpy(dtype=np.float64)
            x0 = xa - (np.bincount(fe_c, weights=xa, minlength=m_fe) / cnt_s)[fe_c]
            Sx = sparse.csr_matrix((x0, (fe_c, d_i)), shape=(m_fe, n_all))
            Sxx = sparse.csr_matrix((x0 * x0, (fe_c, d_i)), shape=(m_fe, n_all))
            Sy_co2 = sparse.csr_matrix((y_co2_0, (fe_c, d_i)), shape=(m_fe, n_all))
            Sxy_co2 = sparse.csr_matrix((x0 * y_co2_0, (fe_c, d_i)), shape=(m_fe, n_all))
            # Because fe_c is YM x Hour, each FE cell c belongs to a single hour h!
            # So d_imp * nbr[h] inside cell c just multiplies cell c's Sy_imp and Sxy_imp by nbr[h]!!
            cell_hr = np.zeros(m_fe, dtype=np.int32)
            cell_hr[fe_c] = hr0_k
            y_imp_0 = d_imp_a - (np.bincount(fe_c, weights=d_imp_a, minlength=m_fe) / cnt_s)[fe_c]
            Sy_imp = sparse.csr_matrix((y_imp_0, (fe_c, d_i)), shape=(m_fe, n_all))
            Sxy_imp = sparse.csr_matrix((x0 * y_imp_0, (fe_c, d_i)), shape=(m_fe, n_all))
            reg_pack[rname] = {
                "Sx": Sx,
                "Sxx": Sxx,
                "Sy_co2": Sy_co2,
                "Sxy_co2": Sxy_co2,
                "Sy_imp": Sy_imp,
                "Sxy_imp": Sxy_imp,
                "cell_hr": cell_hr,
            }
        ciso_bin_structs.append({"S1": S1, "regs": reg_pack})

    # ------------------------------------------------------------------
    # CORE VECTORIZED EVALUATOR (handles BOTH point B=1 & full B=1,000!)
    # ------------------------------------------------------------------
    def _eval_batch(
        W_in: np.ndarray,
        same_window_only: bool = False,
        trade_mode: str = "same_window_dynamic",  # "same_window_dynamic" or "fixed_2025_2026"
        use_03b_dtot: bool = False,
        use_03b_all_bess: bool = False,
        fix_dis_weights: dict[str, float] | None = None,
        fix_aef_kt: dict[str, float] | None = None,
    ) -> dict[str, np.ndarray]:
        """Evaluate all 14 BAs, neighbors, same-window bilateral trade weights, AEF, CEMS-MEF,
        CAISO curtailment regimes, and Leave-Out sub-fleets across B draws simultaneously.
        """
        W = W_in.copy()
        B = W.shape[1]
        if same_window_only:
            W[n_ov:, :] = 0.0

        # 1. Domestic 24h CEMS MEFs (24, B) & domestic hourly AEF (24, B) for every needed BA
        dom_b24: dict[str, np.ndarray] = {}
        dom_aef24: dict[str, np.ndarray] = {}
        for ba, st in dom_structs.items():
            dom_b24[ba] = _eval_sparse_24h_beta_batch(st, W, clip_lo=0.0, clip_hi=1400.0)
            co2_b = dom_day_co2[ba].T @ W  # (24, B)
            gen_b = np.maximum(dom_day_gen[ba].T @ W, 1.0)
            dom_aef24[ba] = co2_b / gen_b

        # 2. Per-BA system MEFs, unconditional AEF, RTE, discharge volume (GWh)
        ba_chg_mef: dict[str, np.ndarray] = {}
        ba_dis_mef: dict[str, np.ndarray] = {}
        ba_rte: dict[str, np.ndarray] = {}
        ba_dis_gwh: dict[str, np.ndarray] = {}
        ba_aef_net_kg: dict[str, np.ndarray] = {}
        ba_aef_kt: dict[str, np.ndarray] = {}
        ciso_nbr_b24 = np.zeros((24, B), dtype=np.float64)

        for ba in METERED_14_BAS:
            bs = ba_structs[ba]
            # Bilateral neighbor MEF & incoming-import neighbor AEF
            nbr_mef = np.zeros((24, B), dtype=np.float64)
            nbr_aef = np.zeros((24, B), dtype=np.float64)
            if trade_mode == "same_window_dynamic":
                nd = ba_nbr_daily[ba]
                dibas = nd["dibas"]
                abs_b = nd["abs_mat"].T @ W  # (n_nbr, B)
                imp_b = nd["imp_mat"].T @ W
                abs_sum = abs_b.sum(axis=0)  # (B,)
                imp_sum = imp_b.sum(axis=0)
                for j, db in enumerate(dibas):
                    wa = np.where(abs_sum > 0.05, abs_b[j] / np.where(abs_sum > 0.05, abs_sum, 1.0), 0.0)
                    wi = np.where(imp_sum > 0.05, imp_b[j] / np.where(imp_sum > 0.05, imp_sum, 1.0), 0.0)
                    nbr_mef += dom_b24[db] * wa[None, :]
                    nbr_aef += dom_aef24[db] * wi[None, :]
                fallback_a = abs_sum <= 0.05
                fallback_i = imp_sum <= 0.05
                if np.any(fallback_a):
                    nbr_mef[:, fallback_a] = dom_b24[ba][:, fallback_a]
                if np.any(fallback_i):
                    nbr_aef[:, fallback_i] = dom_aef24[ba][:, fallback_i]
            else:
                for db, wn in ba_nbr_fixed[ba]["abs"]:
                    nbr_mef += wn * dom_b24[db]
                for db, wn in ba_nbr_fixed[ba]["imp"]:
                    nbr_aef += wn * dom_aef24[db]

            if ba == "CISO":
                ciso_nbr_b24 = nbr_mef

            # Marginal domestic vs import shares
            if use_03b_dtot:
                br = ba_bridge_structs[ba]
                s_dom = _eval_sparse_24h_beta_batch(br["st_sd_dtot"], W, clip_lo=0.0, clip_hi=1.0)
                s_imp = _eval_sparse_24h_beta_batch(br["st_si_dtot"], W, clip_lo=0.0, clip_hi=1.0)
            else:
                s_dom = (
                    _eval_sparse_24h_beta_batch(bs["st_sd"], W, clip_lo=0.0, clip_hi=1.0)
                    if bs["st_sd"] is not None
                    else np.ones((24, B))
                )
                s_imp = (
                    _eval_sparse_24h_beta_batch(bs["st_si"], W, clip_lo=0.0, clip_hi=1.0)
                    if bs["st_si"] is not None
                    else np.zeros((24, B))
                )
            st_sum = s_dom + s_imp
            s_dom_n = np.where(st_sum > 0.05, s_dom / np.where(st_sum > 0.05, st_sum, 1.0), 1.0)
            s_imp_n = np.where(st_sum > 0.05, s_imp / np.where(st_sum > 0.05, st_sum, 1.0), 0.0)
            sys_b24 = s_dom_n * dom_b24[ba] + s_imp_n * nbr_mef

            # Hourly charging/discharging volumes (MWh) on resampled days
            if use_03b_all_bess:
                chg_24 = ba_bridge_structs[ba]["day_chg_24_all"].T @ W  # (24, B)
                dis_24 = ba_bridge_structs[ba]["day_dis_24_all"].T @ W
            else:
                chg_24 = bs["day_chg_24"].T @ W  # (24, B)
                dis_24 = bs["day_dis_24"].T @ W
            t_chg = np.maximum(chg_24.sum(axis=0), 1.0)  # (B,)
            t_dis = np.maximum(dis_24.sum(axis=0), 1.0)
            rte_b = t_dis / t_chg

            ba_chg_mef[ba] = np.sum(chg_24 * sys_b24, axis=0) / t_chg
            ba_dis_mef[ba] = np.sum(dis_24 * sys_b24, axis=0) / t_dis
            ba_rte[ba] = rte_b
            ba_dis_gwh[ba] = (
                np.full(B, fix_dis_weights[ba], dtype=np.float64)
                if fix_dis_weights is not None
                else (t_dis / 1000.0)
            )

            # Exact unconditional hourly consumption-weighted AEF (machine-identical to Step 03!)
            if fix_aef_kt is not None:
                ba_aef_kt[ba] = np.full(B, fix_aef_kt[ba], dtype=np.float64)
                ba_aef_net_kg[ba] = 1000.0 * ba_aef_kt[ba] / np.maximum(ba_dis_gwh[ba], 1e-6)
            else:
                chg_aef_num = np.sum((bs["day_chg_aef_dom"].T @ W) + (bs["day_chg_aef_imp"].T @ W) * nbr_aef, axis=0)
                dis_aef_num = np.sum((bs["day_dis_aef_dom"].T @ W) + (bs["day_dis_aef_imp"].T @ W) * nbr_aef, axis=0)
                # Note: Step 03 clips aef_hr to [0, 1400], which never binds in practice (<700 kg/MWh)
                aef_chg = chg_aef_num / np.maximum((bs["day_chg_24"].T @ W).sum(axis=0), 1.0)
                aef_dis = dis_aef_num / np.maximum((bs["day_dis_24"].T @ W).sum(axis=0), 1.0)
                net_aef_kg = aef_chg / rte_b - aef_dis
                ba_aef_net_kg[ba] = net_aef_kg
                ba_aef_kt[ba] = net_aef_kg * ba_dis_gwh[ba] / 1000.0

        # 3. CAISO interior curtailment-regime system MEF slopes (4 bins, main & observed dLoad)
        W_ov = W[:n_ov, :]
        m_sys_k = np.empty((4, B), dtype=np.float64)
        m_ld_k = np.empty((4, B), dtype=np.float64)
        for k, cb in enumerate(ciso_bin_structs):
            sw = cb["S1"] @ W  # (m_fe, B)
            sw_safe = np.where(sw > 0.0, sw, 1.0)
            for rname, out_arr in (("d_net_pot", m_sys_k), ("d_load", m_ld_k)):
                rp = cb["regs"][rname]
                sx = rp["Sx"] @ W
                sxx_c = np.maximum((rp["Sxx"] @ W) - (sx * sx) / sw_safe, 0.0)
                nbr_c = ciso_nbr_b24[rp["cell_hr"], :]  # (m_fe, B)
                sy = (rp["Sy_co2"] @ W) + nbr_c * (rp["Sy_imp"] @ W)
                sxy_raw = (rp["Sxy_co2"] @ W) + nbr_c * (rp["Sxy_imp"] @ W)
                sxy_c = sxy_raw - (sx * sy) / sw_safe
                sxx_tot = np.sum(sxx_c, axis=0)
                sxy_tot = np.sum(sxy_c, axis=0)
                out_arr[k, :] = np.where(sxx_tot >= 1.0, sxy_tot / np.where(sxx_tot >= 1.0, sxx_tot, 1.0), 0.0)

        chg_k = day_ciso_chg_bin.T @ W_ov  # (4, B)
        dis_k = day_ciso_dis_bin.T @ W_ov
        tc_c = np.maximum(chg_k.sum(axis=0), 1.0)
        td_c = np.maximum(dis_k.sum(axis=0), 1.0)
        rte_c = td_c / tc_c
        ciso_emp_main = np.sum((chg_k / tc_c[None, :]) * m_sys_k, axis=0) / rte_c - np.sum(
            (dis_k / td_c[None, :]) * m_sys_k, axis=0
        )
        ciso_emp_dload = np.sum((chg_k / tc_c[None, :]) * m_ld_k, axis=0) / rte_c - np.sum(
            (dis_k / td_c[None, :]) * m_ld_k, axis=0
        )

        # 4. Aggregate Fleet & Sub-Fleet Leave-Out Portfolios
        out: dict[str, np.ndarray] = {}
        tot_dis_gwh = sum(ba_dis_gwh[b] for b in METERED_14_BAS)
        tot_aef_mt = sum(ba_aef_kt[b] for b in METERED_14_BAS) / 1000.0
        out["tot_dis_twh"] = tot_dis_gwh / 1000.0
        out["aef_net_mt"] = tot_aef_mt
        out["aef_kg_mwh"] = 1e6 * tot_aef_mt / np.maximum(tot_dis_gwh, 1.0)
        out["ciso_emp_main"] = ciso_emp_main
        out["ciso_emp_dload"] = ciso_emp_dload

        for a_val in (0.0, 0.10, 0.15, 0.20, 0.30):
            net_mt = sum(
                (((1.0 - a_val) * ba_chg_mef[b]) / ba_rte[b] - ba_dis_mef[b]) * ba_dis_gwh[b] / 1e6
                for b in METERED_14_BAS
            )
            tag = f"u{round(100 * a_val)}"
            out[f"{tag}_net_mt"] = net_mt
            out[f"{tag}_kg_mwh"] = 1e6 * net_mt / np.maximum(tot_dis_gwh, 1.0)
            out[f"{tag}_disc_mt"] = net_mt - tot_aef_mt
            out[f"{tag}_disc_kg_mwh"] = 1e6 * (net_mt - tot_aef_mt) / np.maximum(tot_dis_gwh, 1.0)

        for a_oth in (0.0, 0.10, 0.15):
            non_ciso_mt = sum(
                (((1.0 - a_oth) * ba_chg_mef[b]) / ba_rte[b] - ba_dis_mef[b]) * ba_dis_gwh[b] / 1e6
                for b in METERED_14_BAS
                if b != "CISO"
            )
            h_main_mt = non_ciso_mt + ciso_emp_main * ba_dis_gwh["CISO"] / 1e6
            h_dl_mt = non_ciso_mt + ciso_emp_dload * ba_dis_gwh["CISO"] / 1e6
            tag = f"h{round(100 * a_oth)}"
            out[f"{tag}_main_mt"] = h_main_mt
            out[f"{tag}_main_disc_mt"] = h_main_mt - tot_aef_mt
            out[f"{tag}_main_disc_kg_mwh"] = 1e6 * (h_main_mt - tot_aef_mt) / np.maximum(tot_dis_gwh, 1.0)
            out[f"{tag}_dload_mt"] = h_dl_mt
            out[f"{tag}_dload_disc_mt"] = h_dl_mt - tot_aef_mt

        # Sub-fleet Leave-Out portfolios (Leave-CISO, Leave-ERCO, Leave-CISO-&-ERCO)
        for sub_tag, drop_set in (
            ("leave_ciso", {"CISO"}),
            ("leave_erco", {"ERCO"}),
            ("leave_ciso_erco", {"CISO", "ERCO"}),
        ):
            keep_bas = [b for b in METERED_14_BAS if b not in drop_set]
            s_dis = sum(ba_dis_gwh[b] for b in keep_bas)
            s_aef = sum(ba_aef_kt[b] for b in keep_bas) / 1000.0
            s_u0 = sum((ba_chg_mef[b] / ba_rte[b] - ba_dis_mef[b]) * ba_dis_gwh[b] / 1e6 for b in keep_bas)
            s_u15 = sum((0.85 * ba_chg_mef[b] / ba_rte[b] - ba_dis_mef[b]) * ba_dis_gwh[b] / 1e6 for b in keep_bas)
            out[f"{sub_tag}_dis_twh"] = s_dis / 1000.0
            out[f"{sub_tag}_aef_mt"] = s_aef
            out[f"{sub_tag}_u0_net_mt"] = s_u0
            out[f"{sub_tag}_u0_disc_mt"] = s_u0 - s_aef
            out[f"{sub_tag}_u0_disc_kg_mwh"] = 1e6 * (s_u0 - s_aef) / np.maximum(s_dis, 1.0)
            out[f"{sub_tag}_u15_net_mt"] = s_u15
            out[f"{sub_tag}_u15_disc_mt"] = s_u15 - s_aef
            if "CISO" not in drop_set:
                nc_15 = sum(
                    (0.85 * ba_chg_mef[b] / ba_rte[b] - ba_dis_mef[b]) * ba_dis_gwh[b] / 1e6
                    for b in keep_bas
                    if b != "CISO"
                )
                s_h15 = nc_15 + ciso_emp_main * ba_dis_gwh["CISO"] / 1e6
                out[f"{sub_tag}_h15_net_mt"] = s_h15
                out[f"{sub_tag}_h15_disc_mt"] = s_h15 - s_aef

        # Also save BA-level vectors for B=1 point audits
        if B == 1:
            out["_ba_detail"] = {
                b: {
                    "dis_gwh": float(ba_dis_gwh[b][0]),
                    "rte": float(ba_rte[b][0]),
                    "aef_kt": float(ba_aef_kt[b][0]),
                    "aef_kg_mwh": float(ba_aef_net_kg[b][0]),
                    "cems_chg": float(ba_chg_mef[b][0]),
                    "cems_dis": float(ba_dis_mef[b][0]),
                    "cems_net_kg_mwh": float(ba_chg_mef[b][0] / ba_rte[b][0] - ba_dis_mef[b][0]),
                    "cems_kt": float((ba_chg_mef[b][0] / ba_rte[b][0] - ba_dis_mef[b][0]) * ba_dis_gwh[b][0] / 1000.0),
                }
                for b in METERED_14_BAS
            }
        return out

    # ------------------------------------------------------------------
    # PART 2: EXACT RECONCILIATION BRIDGE (+7.4417 Mt vs +7.4179 Mt vs Same-Window Trade)
    # ------------------------------------------------------------------
    print("[03c.3] Computing exact Table 1 (+7.44 Mt) vs v4 Table 2 (+7.42 Mt) reconciliation bridge...", flush=True)
    W_unit = np.ones((n_all, 1), dtype=np.float64)
    r3_dis_fixed = {r["ba"]: float(r["dis_gwh_cems_window"]) for r in r3["ba_carbon_table"]}
    r3_aef_fixed = {r["ba"]: float(r["net_aef_kt"]) for r in r3["ba_carbon_table"]}

    b_step0 = _eval_batch(W_unit, same_window_only=False, trade_mode="fixed_2025_2026", use_03b_dtot=False, use_03b_all_bess=False)
    b_step1 = _eval_batch(W_unit, same_window_only=False, trade_mode="fixed_2025_2026", use_03b_dtot=False, use_03b_all_bess=True, fix_dis_weights=r3_dis_fixed, fix_aef_kt=r3_aef_fixed)
    b_step2 = _eval_batch(W_unit, same_window_only=False, trade_mode="fixed_2025_2026", use_03b_dtot=True, use_03b_all_bess=True, fix_dis_weights=r3_dis_fixed, fix_aef_kt=r3_aef_fixed)
    b_v5_full = _eval_batch(W_unit, same_window_only=False, trade_mode="same_window_dynamic", use_03b_dtot=False, use_03b_all_bess=False)
    b_v5_same = _eval_batch(W_unit, same_window_only=True, trade_mode="same_window_dynamic", use_03b_dtot=False, use_03b_all_bess=False)

    r3_u0_disc = float(r3["fleet_aggregates"]["all_14_bas"]["sign_reversal_cems_minus_aef_mt"])
    r3_u0_cems = float(r3["fleet_aggregates"]["all_14_bas"]["cems_mef_total_kt"] / 1000.0)
    r3_aef = float(r3["fleet_aggregates"]["all_14_bas"]["aef_total_kt"] / 1000.0)
    r3b_u0_disc = float(r3b["full_window_joint_14d_bootstrap_1000"]["metrics"]["u0_disc_mt"]["point"])
    r3b_u0_cems = float(r3b["full_window_joint_14d_bootstrap_1000"]["metrics"]["u0_net_mt"]["point"])

    bridge = {
        "step0_table1_step03_exact": {
            "cems_mt": r3_u0_cems,
            "aef_mt": r3_aef,
            "disc_mt": r3_u0_disc,
            "engine_replication_cems_mt": float(b_step0["u0_net_mt"][0]),
            "engine_replication_aef_mt": float(b_step0["aef_net_mt"][0]),
            "engine_replication_disc_mt": float(b_step0["u0_disc_mt"][0]),
            "replication_abs_err_mt": float(abs(float(b_step0["u0_disc_mt"][0]) - r3_u0_disc)),
        },
        "delta_bess_sample_and_05mw_threshold_mt": float(float(b_step1["u0_disc_mt"][0]) - float(b_step0["u0_disc_mt"][0])),
        "delta_sdom_dtot_untrimmed_vs_dneed_mad_mt": float(float(b_step2["u0_disc_mt"][0]) - float(b_step1["u0_disc_mt"][0])),
        "step3_v4_table2_step03b_conditional": {
            "cems_mt": r3b_u0_cems,
            "aef_mt": r3_aef,
            "disc_mt": r3b_u0_disc,
            "engine_replication_disc_mt": float(b_step2["u0_disc_mt"][0]),
            "total_t1_minus_v4t2_mt": float(r3_u0_disc - r3b_u0_disc),
        },
        "step4_v5_exact_table1_plus_samewindow_trade_full": {
            "window": "2024-07-01..2026-09-30",
            "dis_twh": float(b_v5_full["tot_dis_twh"][0]),
            "cems_mt": float(b_v5_full["u0_net_mt"][0]),
            "aef_mt": float(b_v5_full["aef_net_mt"][0]),
            "disc_mt": float(b_v5_full["u0_disc_mt"][0]),
            "delta_samewindow_trade_vs_table1_mt": float(float(b_v5_full["u0_disc_mt"][0]) - r3_u0_disc),
        },
        "step5_v5_exact_table1_plus_samewindow_trade_same18m": {
            "window": "2024-07-01..2025-12-31",
            "dis_twh": float(b_v5_same["tot_dis_twh"][0]),
            "cems_mt": float(b_v5_same["u0_net_mt"][0]),
            "aef_mt": float(b_v5_same["aef_net_mt"][0]),
            "disc_mt": float(b_v5_same["u0_disc_mt"][0]),
        },
        "bilateral_trade_weight_shifts": trade_weight_comparison,
    }
    print(
        f"  [BRIDGE] Table 1 (Step 03): {r3_u0_disc:+.4f} Mt (engine err={bridge['step0_table1_step03_exact']['replication_abs_err_mt']:.2e}) | "
        f"bess/0.5MW filter: {bridge['delta_bess_sample_and_05mw_threshold_mt']:+.4f} Mt | "
        f"d_tot vs d_need(8xMAD): {bridge['delta_sdom_dtot_untrimmed_vs_dneed_mad_mt']:+.4f} Mt | "
        f"v4 Table 2: {r3b_u0_disc:+.4f} Mt | "
        f"v5 Table1+SameWinTrade Full: {bridge['step4_v5_exact_table1_plus_samewindow_trade_full']['disc_mt']:+.4f} Mt "
        f"(Same 18m: {bridge['step5_v5_exact_table1_plus_samewindow_trade_same18m']['disc_mt']:+.4f} Mt)",
        flush=True,
    )

    # ------------------------------------------------------------------
    # PART 3: FULL UNCONDITIONAL SEASON-STRATIFIED JOINT UTC-DAY BLOCK BOOTSTRAP
    #         L = 7, 14, 28 DAYS (B = 1,000) FOR BOTH FULL & SAME-WINDOW!
    # ------------------------------------------------------------------
    B_BOOT = 1000
    print(f"[03c.4] Running UNCONDITIONAL Season-Stratified Joint UTC-Day Block Bootstrap (L=7,14,28d, B={B_BOOT})...", flush=True)
    track_keys = [
        "tot_dis_twh",
        "aef_net_mt",
        "aef_kg_mwh",
        "u0_net_mt",
        "u0_kg_mwh",
        "u0_disc_mt",
        "u0_disc_kg_mwh",
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
        "h0_main_disc_kg_mwh",
        "h10_main_mt",
        "h10_main_disc_mt",
        "h15_main_mt",
        "h15_main_disc_mt",
        "h15_main_disc_kg_mwh",
        "h0_dload_mt",
        "h0_dload_disc_mt",
        "h15_dload_mt",
        "h15_dload_disc_mt",
        "ciso_emp_main",
        "ciso_emp_dload",
        "leave_ciso_u0_net_mt",
        "leave_ciso_u0_disc_mt",
        "leave_ciso_u0_disc_kg_mwh",
        "leave_ciso_u15_disc_mt",
        "leave_erco_u0_net_mt",
        "leave_erco_u0_disc_mt",
        "leave_erco_u0_disc_kg_mwh",
        "leave_erco_h15_disc_mt",
        "leave_ciso_erco_u0_net_mt",
        "leave_ciso_erco_u0_disc_mt",
        "leave_ciso_erco_u0_disc_kg_mwh",
        "leave_ciso_erco_u15_disc_mt",
    ]

    uncond_full_by_L: dict[str, dict[str, Any]] = {}
    uncond_same_by_L: dict[str, dict[str, Any]] = {}
    cond_14d_comparison: dict[str, Any] = {}

    for L in (7, 14, 28):
        tb = time.time()
        rng = np.random.default_rng(202611280 + L)
        W_ov = _draw_season_stratified_mbb_matrix(rng, ov_dates, L, B_BOOT)
        W_ex = _draw_season_stratified_mbb_matrix(rng, ex_dates, L, B_BOOT)
        W_all = np.vstack([W_ov, W_ex])  # (n_all, B_BOOT)

        res_f = _eval_batch(W_all, same_window_only=False, trade_mode="same_window_dynamic")
        res_s = _eval_batch(W_all, same_window_only=True, trade_mode="same_window_dynamic")

        uncond_full_by_L[f"{L}d"] = {k: _summarize(float(b_v5_full[k][0]), res_f[k]) for k in track_keys}
        uncond_same_by_L[f"{L}d"] = {k: _summarize(float(b_v5_same[k][0]), res_s[k]) for k in track_keys}

        # At L=14d, also evaluate matched conditional (fixed AEF, fixed discharge, fixed trade weights) on IDENTICAL draws
        if L == 14:
            same_dis_fixed = {b: b_v5_same["_ba_detail"][b]["dis_gwh"] for b in METERED_14_BAS}
            same_aef_fixed = {b: b_v5_same["_ba_detail"][b]["aef_kt"] for b in METERED_14_BAS}
            full_dis_fixed = {b: b_v5_full["_ba_detail"][b]["dis_gwh"] for b in METERED_14_BAS}
            full_aef_fixed = {b: b_v5_full["_ba_detail"][b]["aef_kt"] for b in METERED_14_BAS}
            res_fc = _eval_batch(
                W_all,
                same_window_only=False,
                trade_mode="fixed_2025_2026",
                fix_dis_weights=full_dis_fixed,
                fix_aef_kt=full_aef_fixed,
            )
            res_sc = _eval_batch(
                W_all,
                same_window_only=True,
                trade_mode="fixed_2025_2026",
                fix_dis_weights=same_dis_fixed,
                fix_aef_kt=same_aef_fixed,
            )
            cond_14d_comparison = {
                "full_u0_disc_mt_cond_14d_seas": _summarize(float(b_step0["u0_disc_mt"][0]), res_fc["u0_disc_mt"]),
                "full_h15_disc_mt_cond_14d_seas": _summarize(float(b_step0["h15_main_disc_mt"][0]), res_fc["h15_main_disc_mt"]),
                "same_u0_disc_mt_cond_14d_seas": _summarize(float(b_v5_same["u0_disc_mt"][0]), res_sc["u0_disc_mt"]),
                "same_h15_disc_mt_cond_14d_seas": _summarize(float(b_v5_same["h15_main_disc_mt"][0]), res_sc["h15_main_disc_mt"]),
                "width_ratio_uncond_vs_cond_full_u0": float(
                    uncond_full_by_L["14d"]["u0_disc_mt"]["ci95_width"]
                    / max(_summarize(float(b_step0["u0_disc_mt"][0]), res_fc["u0_disc_mt"])["ci95_width"], 1e-9)
                ),
                "width_ratio_uncond_vs_cond_full_h15": float(
                    uncond_full_by_L["14d"]["h15_main_disc_mt"]["ci95_width"]
                    / max(_summarize(float(b_step0["h15_main_disc_mt"][0]), res_fc["h15_main_disc_mt"])["ci95_width"], 1e-9)
                ),
            }

        uf = uncond_full_by_L[f"{L}d"]
        us = uncond_same_by_L[f"{L}d"]
        print(
            f"  [Uncond {L:2d}d Seas-MBB ({time.time()-tb:.1f}s)] "
            f"Full u0 Disc={uf['u0_disc_mt']['point']:+.2f} [{uf['u0_disc_mt']['ci95_lo']:+.2f},{uf['u0_disc_mt']['ci95_hi']:+.2f}] | "
            f"h15 Disc={uf['h15_main_disc_mt']['point']:+.2f} [{uf['h15_main_disc_mt']['ci95_lo']:+.2f},{uf['h15_main_disc_mt']['ci95_hi']:+.2f}] | "
            f"Same h15 Disc={us['h15_main_disc_mt']['point']:+.2f} [{us['h15_main_disc_mt']['ci95_lo']:+.2f},{us['h15_main_disc_mt']['ci95_hi']:+.2f}] | "
            f"CAISO={uf['ciso_emp_main']['point']:+.2f} [{uf['ciso_emp_main']['ci95_lo']:+.2f},{uf['ciso_emp_main']['ci95_hi']:+.2f}]",
            flush=True,
        )

    # ------------------------------------------------------------------
    # PART 4: COMPLETE LEAVE-ONE-BA-OUT (LOBAO) & FLEET CONCENTRATION AUDIT
    # ------------------------------------------------------------------
    print("[03c.5] Computing 14-BA Leave-One-BA-Out (LOBAO) & concentration diagnostics...", flush=True)
    ba_det_full = b_v5_full["_ba_detail"]
    tot_dis_f = sum(ba_det_full[b]["dis_gwh"] for b in METERED_14_BAS)
    tot_aef_f = sum(ba_det_full[b]["aef_kt"] for b in METERED_14_BAS) / 1000.0
    tot_cems_f = sum(ba_det_full[b]["cems_kt"] for b in METERED_14_BAS) / 1000.0
    tot_disc_f = tot_cems_f - tot_aef_f

    lobao_rows = []
    for drop_ba in METERED_14_BAS:
        keep = [b for b in METERED_14_BAS if b != drop_ba]
        k_dis = sum(ba_det_full[b]["dis_gwh"] for b in keep)
        k_aef = sum(ba_det_full[b]["aef_kt"] for b in keep) / 1000.0
        k_cems = sum(ba_det_full[b]["cems_kt"] for b in keep) / 1000.0
        k_disc = k_cems - k_aef
        ba_disc_mt = (ba_det_full[drop_ba]["cems_kt"] - ba_det_full[drop_ba]["aef_kt"]) / 1000.0
        lobao_rows.append(
            {
                "dropped_ba": drop_ba,
                "ba_dis_share_pct": float(100.0 * ba_det_full[drop_ba]["dis_gwh"] / tot_dis_f),
                "ba_disc_share_pct": float(100.0 * ba_disc_mt / tot_disc_f),
                "remaining_dis_twh": float(k_dis / 1000.0),
                "remaining_aef_mt": float(k_aef),
                "remaining_cems_mt": float(k_cems),
                "remaining_disc_mt": float(k_disc),
                "remaining_disc_kg_mwh": float(1e6 * k_disc / k_dis),
                "remaining_sign_reversed": bool(k_aef < 0.0 and k_cems > 0.0),
            }
        )

    ciso_erco_dis_share = float(100.0 * (ba_det_full["CISO"]["dis_gwh"] + ba_det_full["ERCO"]["dis_gwh"]) / tot_dis_f)
    ciso_disc_share = float(100.0 * ((ba_det_full["CISO"]["cems_kt"] - ba_det_full["CISO"]["aef_kt"]) / 1000.0) / tot_disc_f)
    erco_disc_share = float(100.0 * ((ba_det_full["ERCO"]["cems_kt"] - ba_det_full["ERCO"]["aef_kt"]) / 1000.0) / tot_disc_f)
    lobao_audit = {
        "ciso_dis_share_pct": float(100.0 * ba_det_full["CISO"]["dis_gwh"] / tot_dis_f),
        "erco_dis_share_pct": float(100.0 * ba_det_full["ERCO"]["dis_gwh"] / tot_dis_f),
        "ciso_plus_erco_dis_share_pct": ciso_erco_dis_share,
        "ciso_disc_share_pct": ciso_disc_share,
        "erco_disc_share_pct": erco_disc_share,
        "ciso_plus_erco_disc_share_pct": float(ciso_disc_share + erco_disc_share),
        "n_lobao_sign_reversed": int(sum(1 for r in lobao_rows if r["remaining_sign_reversed"])),
        "min_lobao_disc_mt": float(min(r["remaining_disc_mt"] for r in lobao_rows)),
        "max_lobao_disc_mt": float(max(r["remaining_disc_mt"] for r in lobao_rows)),
        "leave_one_ba_out_14": lobao_rows,
        "leave_ciso_uncond_14d": {
            "full_u0_disc_mt": uncond_full_by_L["14d"]["leave_ciso_u0_disc_mt"],
            "full_u0_disc_kg_mwh": uncond_full_by_L["14d"]["leave_ciso_u0_disc_kg_mwh"],
            "full_u15_disc_mt": uncond_full_by_L["14d"]["leave_ciso_u15_disc_mt"],
            "same_u0_disc_mt": uncond_same_by_L["14d"]["leave_ciso_u0_disc_mt"],
            "same_u15_disc_mt": uncond_same_by_L["14d"]["leave_ciso_u15_disc_mt"],
        },
        "leave_erco_uncond_14d": {
            "full_u0_disc_mt": uncond_full_by_L["14d"]["leave_erco_u0_disc_mt"],
            "full_u0_disc_kg_mwh": uncond_full_by_L["14d"]["leave_erco_u0_disc_kg_mwh"],
            "full_h15_disc_mt": uncond_full_by_L["14d"]["leave_erco_h15_disc_mt"],
            "same_u0_disc_mt": uncond_same_by_L["14d"]["leave_erco_u0_disc_mt"],
            "same_h15_disc_mt": uncond_same_by_L["14d"]["leave_erco_h15_disc_mt"],
        },
        "leave_ciso_and_erco_uncond_14d": {
            "remaining_dis_twh_full": float(b_v5_full["leave_ciso_erco_dis_twh"][0]),
            "remaining_dis_share_pct": float(100.0 - ciso_erco_dis_share),
            "full_aef_mt": float(b_v5_full["leave_ciso_erco_aef_mt"][0]),
            "full_u0_net_mt": uncond_full_by_L["14d"]["leave_ciso_erco_u0_net_mt"],
            "full_u0_disc_mt": uncond_full_by_L["14d"]["leave_ciso_erco_u0_disc_mt"],
            "full_u0_disc_kg_mwh": uncond_full_by_L["14d"]["leave_ciso_erco_u0_disc_kg_mwh"],
            "full_u15_disc_mt": uncond_full_by_L["14d"]["leave_ciso_erco_u15_disc_mt"],
            "same_u0_disc_mt": uncond_same_by_L["14d"]["leave_ciso_erco_u0_disc_mt"],
            "same_u15_disc_mt": uncond_same_by_L["14d"]["leave_ciso_erco_u15_disc_mt"],
        },
    }
    print(
        f"  [LOBAO] CISO+ERCO = {ciso_erco_dis_share:.1f}% of disch; CISO = {ciso_disc_share:.1f}% of disc | "
        f"Leave-CISO: {lobao_audit['leave_ciso_uncond_14d']['full_u0_disc_mt']['point']:+.2f} "
        f"[{lobao_audit['leave_ciso_uncond_14d']['full_u0_disc_mt']['ci95_lo']:+.2f}, {lobao_audit['leave_ciso_uncond_14d']['full_u0_disc_mt']['ci95_hi']:+.2f}] Mt | "
        f"Leave-CISO&ERCO (12 grids, {100-ciso_erco_dis_share:.1f}% disch): "
        f"{lobao_audit['leave_ciso_and_erco_uncond_14d']['full_u0_disc_mt']['point']:+.2f} "
        f"[{lobao_audit['leave_ciso_and_erco_uncond_14d']['full_u0_disc_mt']['ci95_lo']:+.2f}, {lobao_audit['leave_ciso_and_erco_uncond_14d']['full_u0_disc_mt']['ci95_hi']:+.2f}] Mt "
        f"({lobao_audit['leave_ciso_and_erco_uncond_14d']['full_u0_disc_kg_mwh']['point']:+.1f} kg/MWh)",
        flush=True,
    )

    # ------------------------------------------------------------------
    # PART 5: OUT-OF-SAMPLE TEMPORAL HOLDOUT & 9-QUARTER LEAVE-QUARTER-OUT CV
    # ------------------------------------------------------------------
    print("[03c.6] Running Out-of-Sample Temporal Holdout & 9-Quarter Leave-Quarter-Out CV...", flush=True)

    def _fit_24h_train_and_eval_test(
        df_tr: pd.DataFrame,
        df_te: pd.DataFrame,
    ) -> dict[str, float]:
        """Fit 24h domestic CEMS MEF vector strictly on df_tr (YM x Hour FE, 8x MAD)
        and evaluate pure out-of-sample hourly dCO2 prediction on df_te (zero test params!).
        """
        tr_trim = _extract_24h_trimmed_df(df_tr, "d_co2", "d_disp", trim_mad=8.0, min_hr_n=20)
        if tr_trim is None or len(df_te) < 50:
            return {"n_test": 0, "r2_oos": 0.0, "r2_oos_within_ymh": 0.0, "cal_slope": 0.0, "rmse_t": 0.0, "mae_t": 0.0, "corr": 0.0}

        b24 = np.zeros(24, dtype=np.float64)
        mu_y24 = np.zeros(24, dtype=np.float64)
        mu_x24 = np.zeros(24, dtype=np.float64)
        for h in range(1, 25):
            sh = tr_trim[tr_trim["hour"] == h]
            if len(sh) < 15:
                continue
            y = sh["d_co2"].to_numpy(dtype=np.float64)
            x = sh["d_disp"].to_numpy(dtype=np.float64)
            ymc, _ = pd.factorize(sh["ym"].to_numpy(), sort=False)
            m = int(ymc.max()) + 1
            cnt = np.maximum(np.bincount(ymc, minlength=m).astype(np.float64), 1.0)
            yd = y - (np.bincount(ymc, weights=y, minlength=m) / cnt)[ymc]
            xd = x - (np.bincount(ymc, weights=x, minlength=m) / cnt)[ymc]
            sxx = float(xd @ xd)
            b24[h - 1] = float(np.clip((xd @ yd) / sxx, 0.0, 1400.0)) if sxx >= 1.0 else 0.0
            mu_y24[h - 1] = float(np.mean(y))
            mu_x24[h - 1] = float(np.mean(x))

        # Apply strictly to held-out df_te (also trim extreme >8x MAD telemetry glitches using TRAIN MAD!)
        te_ok = df_te[np.isfinite(df_te["d_co2"]) & np.isfinite(df_te["d_disp"])].copy()
        hr0_te = te_ok["hour"].to_numpy(dtype=np.int32) - 1
        y_te = te_ok["d_co2"].to_numpy(dtype=np.float64)
        x_te = te_ok["d_disp"].to_numpy(dtype=np.float64)
        yhat_te = mu_y24[hr0_te] + b24[hr0_te] * (x_te - mu_x24[hr0_te])

        # Pure out-of-sample R^2, calibration slope, RMSE (in metric tons CO2/h), MAE
        sse = float(np.sum((y_te - yhat_te) ** 2))
        sst = float(np.sum((y_te - np.mean(y_te)) ** 2))
        r2_oos = float(1.0 - sse / max(sst, 1.0))
        vyhat = float(np.var(yhat_te))
        cal_slope = float(np.cov(y_te, yhat_te, ddof=0)[0, 1] / vyhat) if vyhat > 1e-6 else 0.0
        corr = float(np.corrcoef(y_te, yhat_te)[0, 1]) if (vyhat > 1e-6 and np.var(y_te) > 1e-6) else 0.0

        # Also within-test YM x Hour demeaned OOS R^2 (isolating pure slope accuracy from seasonal shift)
        ymhc, _ = pd.factorize((te_ok["ym"].astype(str) + "_" + te_ok["hour"].astype(str)).to_numpy(), sort=False)
        m_t = int(ymhc.max()) + 1
        cnt_t = np.maximum(np.bincount(ymhc, minlength=m_t).astype(np.float64), 1.0)
        yd_te = y_te - (np.bincount(ymhc, weights=y_te, minlength=m_t) / cnt_t)[ymhc]
        xd_te = x_te - (np.bincount(ymhc, weights=x_te, minlength=m_t) / cnt_t)[ymhc]
        yhat_d_te = b24[hr0_te] * xd_te
        r2_within = float(1.0 - np.sum((yd_te - yhat_d_te) ** 2) / max(np.sum(yd_te ** 2), 1.0))

        return {
            "n_test": len(te_ok),
            "r2_oos": r2_oos,
            "r2_oos_within_ymh": r2_within,
            "cal_slope": cal_slope,
            "corr": corr,
            "rmse_t": float(np.sqrt(np.mean((y_te - yhat_te) ** 2)) / 1000.0),
            "mae_t": float(np.mean(np.abs(y_te - yhat_te)) / 1000.0),
            "y_te_sse": sse,
            "y_te_sst": sst,
            "y_te_arr_var": float(np.var(y_te)),
            "b24_mean": float(np.mean(b24)),
        }

    # Build hourly diff panels with quarter labels for all 14 BAs
    ba_diff_panels: dict[str, pd.DataFrame] = {}
    for ba in METERED_14_BAS:
        grp = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy()
        dt_sec = grp["utc_start"].diff().dt.total_seconds()
        d_disp = grp["disp_dom"].diff()
        d_co2 = grp["co2_kg"].diff()
        med_disp = float(grp["disp_dom"].median())
        no_drop = (
            (grp["disp_dom"] > 0.25 * med_disp) & (grp["disp_dom"].shift(1) > 0.25 * med_disp)
            if med_disp > 100.0
            else pd.Series(True, index=grp.index)
        )
        ok = (dt_sec == 3600.0) & d_disp.notna() & d_co2.notna() & no_drop
        df_b = pd.DataFrame(
            {
                "date": grp["date"].to_numpy(),
                "utc_day": grp["utc_day"].to_numpy(),
                "ym": grp["ym"].to_numpy(),
                "quarter": grp["date"].dt.to_period("Q").astype(str).to_numpy(),
                "hour": grp["hour"].to_numpy(dtype=np.int32),
                "d_disp": d_disp.to_numpy(dtype=np.float64),
                "d_co2": d_co2.to_numpy(dtype=np.float64),
            }
        )[ok.to_numpy()]
        ba_diff_panels[ba] = df_b

    # (a) Temporal Holdout: Train 2024-07-01..2025-09-30 -> Test 2025-10-01..2026-09-30
    holdout_by_ba = {}
    tot_sse, tot_sst, w_r2_num, w_sl_num, w_den = 0.0, 0.0, 0.0, 0.0, 0.0
    for ba in METERED_14_BAS:
        dfb = ba_diff_panels[ba]
        tr = dfb[dfb["date"] <= "2025-09-30"]
        te = dfb[dfb["date"] >= "2025-10-01"]
        ev = _fit_24h_train_and_eval_test(tr, te)
        holdout_by_ba[ba] = {k: v for k, v in ev.items() if k not in ("y_te_sse", "y_te_sst", "y_te_arr_var")}
        tot_sse += ev["y_te_sse"]
        tot_sst += ev["y_te_sst"]
        # Discharge-weighted average across thermal BAs (exclude hydro-only PGE where fossil dCO2 ~ 0)
        if ba != "PGE":
            wb = ba_det_full[ba]["dis_gwh"]
            w_r2_num += wb * ev["r2_oos"]
            w_sl_num += wb * ev["cal_slope"]
            w_den += wb

    fleet_holdout_pooled_r2 = float(1.0 - tot_sse / max(tot_sst, 1.0))
    fleet_holdout_dis_weighted_r2 = float(w_r2_num / max(w_den, 1.0))
    fleet_holdout_dis_weighted_slope = float(w_sl_num / max(w_den, 1.0))

    # Also test counterfactual battery-discrepancy OOS transferability:
    # Apply MEFs trained ONLY on 2024-07..2025-09 to held-out 2025-10..2026-09 dispatch vs actual 2025-10..2026-09 MEFs!
    tr_mask = (pd.to_datetime(all_dates) <= pd.Timestamp("2025-09-30")).astype(np.float64)[:, None]
    te_mask = (pd.to_datetime(all_dates) >= pd.Timestamp("2025-10-01")).astype(np.float64)[:, None]
    ev_tr = _eval_batch(tr_mask, same_window_only=False, trade_mode="same_window_dynamic")
    ev_te = _eval_batch(te_mask, same_window_only=False, trade_mode="same_window_dynamic")
    # Compute counterfactual test-window net CEMS CO2 using TRAIN MEFs applied to TEST dispatch!
    # Re-evaluate using train MEFs & test dispatch volumes:
    oos_pred_cems_mt = 0.0
    for ba in METERED_14_BAS:
        # Train-period BA-level chg/dis MEFs applied to test-period BA RTE & test-period BA discharge GWh
        tr_b = ev_tr["_ba_detail"][ba]
        te_b = ev_te["_ba_detail"][ba]
        oos_pred_cems_mt += (tr_b["cems_chg"] / max(te_b["rte"], 1e-6) - tr_b["cems_dis"]) * te_b["dis_gwh"] / 1e6
    actual_te_cems_mt = float(ev_te["u0_net_mt"][0])
    actual_te_aef_mt = float(ev_te["aef_net_mt"][0])
    oos_pred_disc_mt = float(oos_pred_cems_mt - actual_te_aef_mt)
    actual_te_disc_mt = float(ev_te["u0_disc_mt"][0])

    # (b) 9-Quarter Leave-Quarter-Out Cross-Validation (2024Q3..2026Q3)
    quarters = sorted(ba_diff_panels["CISO"]["quarter"].unique().tolist())
    lqo_rows = []
    for q in quarters:
        q_sse, q_sst = 0.0, 0.0
        q_ba_r2 = {}
        q_ba_sl = {}
        for ba in ["CISO", "ERCO", "AZPS", "MISO"]:
            dfb = ba_diff_panels[ba]
            ev_q = _fit_24h_train_and_eval_test(dfb[dfb["quarter"] != q], dfb[dfb["quarter"] == q])
            q_ba_r2[ba] = ev_q["r2_oos"]
            q_ba_sl[ba] = ev_q["cal_slope"]
            q_sse += ev_q["y_te_sse"]
            q_sst += ev_q["y_te_sst"]
        # Held-out quarter fleet discrepancy sign check (train MEFs on 8 quarters -> apply to held-out quarter dispatch!)
        q_dates_mask = (pd.to_datetime(all_dates).to_period("Q").astype(str) == q).astype(np.float64)[:, None]
        not_q_mask = 1.0 - q_dates_mask
        ev_notq = _eval_batch(not_q_mask, same_window_only=False, trade_mode="same_window_dynamic")
        ev_q_act = _eval_batch(q_dates_mask, same_window_only=False, trade_mode="same_window_dynamic")
        q_oos_cems_mt = sum(
            (ev_notq["_ba_detail"][b]["cems_chg"] / max(ev_q_act["_ba_detail"][b]["rte"], 1e-6) - ev_notq["_ba_detail"][b]["cems_dis"])
            * ev_q_act["_ba_detail"][b]["dis_gwh"]
            / 1e6
            for b in METERED_14_BAS
        )
        q_act_aef_mt = float(ev_q_act["aef_net_mt"][0])
        q_act_disc_mt = float(ev_q_act["u0_disc_mt"][0])
        q_oos_disc_mt = float(q_oos_cems_mt - q_act_aef_mt)
        lqo_rows.append(
            {
                "quarter": q,
                "major4_pooled_r2_oos": float(1.0 - q_sse / max(q_sst, 1.0)),
                "ciso_r2_oos": float(q_ba_r2["CISO"]),
                "erco_r2_oos": float(q_ba_r2["ERCO"]),
                "azps_r2_oos": float(q_ba_r2["AZPS"]),
                "miso_r2_oos": float(q_ba_r2["MISO"]),
                "ciso_cal_slope": float(q_ba_sl["CISO"]),
                "erco_cal_slope": float(q_ba_sl["ERCO"]),
                "heldout_dis_twh": float(ev_q_act["tot_dis_twh"][0]),
                "oos_pred_disc_mt": q_oos_disc_mt,
                "actual_disc_mt": q_act_disc_mt,
                "disc_rel_err_pct": float(100.0 * abs(q_oos_disc_mt - q_act_disc_mt) / max(abs(q_act_disc_mt), 1e-6)),
                "sign_preserved": bool(q_oos_disc_mt > 0.0 and q_act_disc_mt > 0.0),
            }
        )

    oos_validation = {
        "prespecified_criteria": {
            "criterion_1_fleet_oos_r2_gt_070": bool(fleet_holdout_pooled_r2 > 0.70 and fleet_holdout_dis_weighted_r2 > 0.70),
            "criterion_2_cal_slope_in_085_115": bool(0.85 <= fleet_holdout_dis_weighted_slope <= 1.15),
            "criterion_3_counterfactual_disc_err_lt_10pct": bool(
                100.0 * abs(oos_pred_disc_mt - actual_te_disc_mt) / max(abs(actual_te_disc_mt), 1e-6) < 10.0
            ),
            "criterion_4_all_9_quarters_sign_preserved": bool(all(r["sign_preserved"] for r in lqo_rows)),
        },
        "temporal_holdout_202407_202509_to_202510_202609": {
            "train_window": "2024-07-01..2025-09-30",
            "test_window": "2025-10-01..2026-09-30",
            "fleet_pooled_r2_oos": fleet_holdout_pooled_r2,
            "fleet_dis_weighted_r2_oos": fleet_holdout_dis_weighted_r2,
            "fleet_dis_weighted_cal_slope": fleet_holdout_dis_weighted_slope,
            "test_dis_twh": float(ev_te["tot_dis_twh"][0]),
            "oos_pred_cems_mt": float(oos_pred_cems_mt),
            "actual_test_cems_mt": actual_te_cems_mt,
            "actual_test_aef_mt": actual_te_aef_mt,
            "oos_pred_disc_mt": oos_pred_disc_mt,
            "actual_test_disc_mt": actual_te_disc_mt,
            "disc_rel_err_pct": float(100.0 * abs(oos_pred_disc_mt - actual_te_disc_mt) / max(abs(actual_te_disc_mt), 1e-6)),
            "by_ba": holdout_by_ba,
        },
        "leave_quarter_out_cv_9q": {
            "n_quarters": len(lqo_rows),
            "mean_major4_r2_oos": float(np.mean([r["major4_pooled_r2_oos"] for r in lqo_rows])),
            "min_major4_r2_oos": float(np.min([r["major4_pooled_r2_oos"] for r in lqo_rows])),
            "mean_ciso_r2_oos": float(np.mean([r["ciso_r2_oos"] for r in lqo_rows])),
            "mean_erco_r2_oos": float(np.mean([r["erco_r2_oos"] for r in lqo_rows])),
            "mean_miso_r2_oos": float(np.mean([r["miso_r2_oos"] for r in lqo_rows])),
            "mean_disc_rel_err_pct": float(np.mean([r["disc_rel_err_pct"] for r in lqo_rows])),
            "n_quarters_sign_preserved": int(sum(1 for r in lqo_rows if r["sign_preserved"])),
            "by_quarter": lqo_rows,
        },
    }
    print(
        f"  [OOS Holdout] Pooled R2={fleet_holdout_pooled_r2:.3f}, Dis-wt R2={fleet_holdout_dis_weighted_r2:.3f}, "
        f"CalSlope={fleet_holdout_dis_weighted_slope:.3f} | CISO R2={holdout_by_ba['CISO']['r2_oos']:.3f}, "
        f"ERCO R2={holdout_by_ba['ERCO']['r2_oos']:.3f}, MISO R2={holdout_by_ba['MISO']['r2_oos']:.3f}, "
        f"AZPS R2={holdout_by_ba['AZPS']['r2_oos']:.3f} | OOS Disc={oos_pred_disc_mt:+.2f} vs Actual={actual_te_disc_mt:+.2f} Mt "
        f"(err={oos_validation['temporal_holdout_202407_202509_to_202510_202609']['disc_rel_err_pct']:.1f}%) | "
        f"LQO 9Q: mean R2={oos_validation['leave_quarter_out_cv_9q']['mean_major4_r2_oos']:.3f}, "
        f"sign={oos_validation['leave_quarter_out_cv_9q']['n_quarters_sign_preserved']}/9",
        flush=True,
    )

    # ------------------------------------------------------------------
    # PART 6: LEAD-LAG DYNAMIC TIMING DIAGNOSTIC (k = -3..+3 HOURS)
    #         ON DIRECT METERED dBESS_MW -> dCO2_CEMS & dImports
    # ------------------------------------------------------------------
    print("[03c.7] Running Lead-Lag Dynamic Diagnostic (k = -3..+3h) on dBESS -> dCO2_CEMS & dImports...", flush=True)
    lead_lag_results: dict[str, Any] = {}
    lags_k = [-3, -2, -1, 0, 1, 2, 3]  # k<0 = future lead dBESS_{t+|k|}; k=0 = contemporaneous; k>0 = lag dBESS_{t-k}

    for ba in ["CISO", "ERCO", "AZPS", "MISO"]:
        g = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy().reset_index(drop=True)
        # Ensure contiguous hourly spacing for +/-3h shifts (independent of datetime64 unit!)
        g["d_co2"] = g["co2_kg"].diff()
        g["d_bess"] = g["bess_clean"].diff()
        g["d_load"] = g["demand_use"].diff()
        g["d_sol"] = g["solar_use"].diff()
        g["d_wnd"] = g["wind_use"].diff()
        g["d_imp"] = g["net_imports_use"].diff()
        g["ym_hr"] = g["ym"].astype(str) + "_" + g["hour"].astype(str)

        ok = g["utc_start"].diff().dt.total_seconds() == 3600.0
        for k in lags_k:
            col_k = f"dbess_k{k:+d}"
            g[col_k] = g["d_bess"].shift(k)
            if k != 0:
                ok &= (g["utc_start"] - g["utc_start"].shift(k)).dt.total_seconds() == (k * 3600.0)
            ok &= g[col_k].notna()
        ok &= g[["d_co2", "d_load", "d_sol", "d_wnd", "d_imp"]].notna().all(axis=1)
        go = g[ok].copy()

        ll_cols = [f"dbess_k{k:+d}" for k in lags_k]
        X_co2 = go[ll_cols + ["d_load", "d_sol", "d_wnd", "d_imp"]].to_numpy(dtype=np.float64)
        r_co2 = hourly_ols_cluster_hac(
            go["d_co2"].to_numpy(dtype=np.float64),
            X_co2,
            date_clusters=go["date"].to_numpy(),
            fe_groups=[go["ym_hr"].to_numpy()],
            col_names=ll_cols + ["d_load", "d_sol", "d_wnd", "d_imp"],
            nw_lags=24,
        )
        X_imp = go[ll_cols + ["d_load", "d_sol", "d_wnd"]].to_numpy(dtype=np.float64)
        r_imp = hourly_ols_cluster_hac(
            go["d_imp"].to_numpy(dtype=np.float64),
            X_imp,
            date_clusters=go["date"].to_numpy(),
            fe_groups=[go["ym_hr"].to_numpy()],
            col_names=ll_cols + ["d_load", "d_sol", "d_wnd"],
            nw_lags=24,
        )

        # Joint date-clustered Wald F-test on the 3 future leads (k = -3, -2, -1)
        r_co2_f = wls_fe_cr1_wcb(
            go["d_co2"].to_numpy(dtype=np.float64),
            X_co2,
            clusters=go["date"].to_numpy(),
            fe_groups=[go["ym_hr"].to_numpy()],
            col_names=ll_cols + ["d_load", "d_sol", "d_wnd", "d_imp"],
            joint_test_indices=[0, 1, 2],  # k = -3, -2, -1
        )
        r_imp_f = wls_fe_cr1_wcb(
            go["d_imp"].to_numpy(dtype=np.float64),
            X_imp,
            clusters=go["date"].to_numpy(),
            fe_groups=[go["ym_hr"].to_numpy()],
            col_names=ll_cols + ["d_load", "d_sol", "d_wnd"],
            joint_test_indices=[0, 1, 2],
        )

        # Compute contemporaneous dominance ratio |beta_0| / sum(|beta_k|) & max |lead| / |beta_0|
        co2_betas = {str(k): r_co2["coefs"][f"dbess_k{k:+d}"] for k in lags_k}
        imp_betas = {str(k): r_imp["coefs"][f"dbess_k{k:+d}"] for k in lags_k}
        b0 = abs(co2_betas["0"]["beta"])
        sum_abs_all = sum(abs(co2_betas[str(k)]["beta"]) for k in lags_k)
        max_abs_lead = max(abs(co2_betas[str(k)]["beta"]) for k in (-3, -2, -1))
        max_abs_lag = max(abs(co2_betas[str(k)]["beta"]) for k in (1, 2, 3))

        lead_lag_results[ba] = {
            "n_hours": len(go),
            "dco2_on_dbess_leads_lags": co2_betas,
            "dimports_on_dbess_leads_lags": imp_betas,
            "dco2_joint_future_leads_F": r_co2_f["joint_F"],
            "dimports_joint_future_leads_F": r_imp_f["joint_F"],
            "co2_contemp_share_of_abs_sum": float(b0 / max(sum_abs_all, 1e-6)),
            "co2_max_lead_to_contemp_ratio": float(max_abs_lead / max(b0, 1e-6)),
            "co2_max_lag_to_contemp_ratio": float(max_abs_lag / max(b0, 1e-6)),
            "co2_cumul_m3_to_p3_kg_mwh": float(sum(co2_betas[str(k)]["beta"] for k in lags_k)),
            "imp_contemp_mw_per_mw": float(imp_betas["0"]["beta"]),
            "imp_contemp_se_day": float(imp_betas["0"]["se_day"]),
        }
        print(
            f"  [Lead-Lag {ba}] dCO2/dBESS k=0: {co2_betas['0']['beta']:+.1f} (SE={co2_betas['0']['se_day']:.1f}) | "
            f"leads(-3,-2,-1): {co2_betas['-3']['beta']:+.1f}, {co2_betas['-2']['beta']:+.1f}, {co2_betas['-1']['beta']:+.1f} | "
            f"lags(+1,+2,+3): {co2_betas['1']['beta']:+.1f}, {co2_betas['2']['beta']:+.1f}, {co2_betas['3']['beta']:+.1f} | "
            f"contemp share={100*lead_lag_results[ba]['co2_contemp_share_of_abs_sum']:.1f}% | "
            f"dImp/dBESS k=0: {imp_betas['0']['beta']:+.3f} (SE={imp_betas['0']['se_day']:.3f})",
            flush=True,
        )

    # ------------------------------------------------------------------
    # PART 7: DYNAMIC CAISO FRONTIER BREAK-EVEN ROOTS & ERCOT MATCHED STRESS TEST
    # ------------------------------------------------------------------
    print("[03c.8] Computing Dynamic CAISO Upper-Bound Frontier Roots & ERCOT Matched Stress Test...", flush=True)
    ciso_2026_gw = float(r1["eia860m_fleet"]["ciso_bess_mw"] / 1000.0)
    ciso_r3 = next(r for r in r3["ba_carbon_table"] if r["ba"] == "CISO")
    c_chg = cc["chg_mw"].to_numpy(dtype=np.float64)
    c_sys = cc["system_curt_mw"].fillna(0.0).to_numpy(dtype=np.float64)
    c_loc = cc["local_curt_mw"].fillna(0.0).to_numpy(dtype=np.float64)
    c_mef_chg = float(ciso_r3["mef_cems_chg_kg_mwh"])
    c_mef_dis = float(ciso_r3["mef_cems_dis_kg_mwh"])
    c_rte = float(ciso_r3["rte"])

    def _ciso_net_at_kappa(kappa: float, q_eff: np.ndarray) -> tuple[float, float]:
        dc = kappa * c_chg
        rho = float(np.sum(np.minimum(dc, q_eff)) / max(float(np.sum(dc)), 1.0))
        net = float(((1.0 - rho) * c_mef_chg) / c_rte - c_mef_dis)
        return rho, net

    frontier_breakeven_roots = []
    for tau_loc in [0.0, 0.25, 0.50, 1.00]:
        q_eff = c_sys + tau_loc * c_loc
        _rho_001, net_001 = _ciso_net_at_kappa(0.01, q_eff)
        if net_001 >= 0.0:
            frontier_breakeven_roots.append(
                {
                    "tau_local_access": float(tau_loc),
                    "ever_abates": False,
                    "kappa_breakeven": 0.0,
                    "gw_breakeven_upper_bound": 0.0,
                    "net_at_kappa_010": float(_ciso_net_at_kappa(0.10, q_eff)[1]),
                }
            )
        else:
            lo_k, hi_k = 0.01, 5.0
            for _ in range(60):
                mid = 0.5 * (lo_k + hi_k)
                if _ciso_net_at_kappa(mid, q_eff)[1] < 0.0:
                    lo_k = mid
                else:
                    hi_k = mid
            k_star = 0.5 * (lo_k + hi_k)
            frontier_breakeven_roots.append(
                {
                    "tau_local_access": float(tau_loc),
                    "ever_abates": True,
                    "kappa_breakeven": float(k_star),
                    "gw_breakeven_upper_bound": float(k_star * ciso_2026_gw),
                    "net_at_kappa_010": float(_ciso_net_at_kappa(0.10, q_eff)[1]),
                }
            )
    print(
        "  [CAISO Upper-Bound Frontier Roots] "
        + " | ".join(
            f"tau={int(100*r['tau_local_access'])}%: {r['kappa_breakeven']:.2f}x ({r['gw_breakeven_upper_bound']:.1f} GW)"
            for r in frontier_breakeven_roots
        ),
        flush=True,
    )

    # ERCOT (and CISO contrast) Matched Season x Hour x Load-Quartile / Load-Decile Cross-Regime Stress Test
    ercot_stress_test: dict[str, Any] = {}
    ren_bins = [("<20%", 0.0, 0.20), ("20-40%", 0.20, 0.40), ("40-60%", 0.40, 0.60), (">60%", 0.60, 5.0)]
    for ba in ["ERCO", "CISO"]:
        g = e_cems[e_cems["ba"] == ba].sort_values("utc_start").copy()
        g["ren_mw"] = g["solar_use"].fillna(0.0) + g["wind_use"].fillna(0.0)
        g["ren_share"] = g["ren_mw"] / np.maximum(g["demand_use"].fillna(1.0), 100.0)
        g["season"] = g["date"].dt.month.map(_month_to_season)
        # Within-season load quartiles & deciles
        g["load_q"] = g.groupby("season")["demand_use"].transform(
            lambda s: pd.qcut(s.rank(method="first"), 4, labels=["Q1", "Q2", "Q3", "Q4"]).astype(str)
        )
        g["load_d"] = g.groupby("season")["demand_use"].transform(
            lambda s: pd.qcut(s.rank(method="first"), 10, labels=[f"D{i}" for i in range(1, 11)]).astype(str)
        )
        g["seas_hr"] = g["season"] + "_" + g["hour"].astype(str)
        g["seas_hr_lq"] = g["season"] + "_" + g["hour"].astype(str) + "_" + g["load_q"]
        g["seas_hr_ld"] = g["season"] + "_" + g["hour"].astype(str) + "_" + g["load_d"]
        g["ym_hr_lq"] = g["ym"].astype(str) + "_" + g["hour"].astype(str) + "_" + g["load_q"]

        g["dt_sec"] = g["utc_start"].diff().dt.total_seconds()
        g["ren_prev"] = g["ren_share"].shift(1)
        g["d_co2"] = g["co2_kg"].diff()
        g["d_coal_co2"] = g["coal_co2_kg"].diff()
        g["d_net_load"] = (g["demand_use"] - g["ren_mw"] - g["bess_clean"].fillna(0.0)).diff()
        gd = g[(g["dt_sec"] == 3600.0) & g["d_co2"].notna() & g["d_net_load"].notna()].copy()

        def _fit_bin_fe(sub_df: pd.DataFrame, fe_col: str) -> dict[str, float] | None:
            if len(sub_df) < 60:
                return None
            xn = sub_df["d_net_load"].to_numpy(dtype=np.float64)
            med_x = float(np.median(xn))
            mad_x = float(np.median(np.abs(xn - med_x)))
            sd = sub_df
            if mad_x > 1e-6:
                km = np.abs(xn - med_x) <= 8.0 * 1.4826 * mad_x
                if int(np.sum(km)) >= 40:
                    sd = sub_df.iloc[km]
            # Drop singleton FE cells so variance & DOF are clean
            vc = sd[fe_col].value_counts()
            sd = sd[sd[fe_col].isin(vc[vc >= 2].index)]
            if len(sd) < 40:
                return None
            rt = hourly_ols_cluster_hac(
                sd["d_co2"].to_numpy(dtype=np.float64),
                sd["d_net_load"].to_numpy(dtype=np.float64)[:, None],
                date_clusters=sd["date"].to_numpy(),
                fe_groups=[sd[fe_col].to_numpy()],
                col_names=["d_net_load"],
                nw_lags=24,
            )
            rc = hourly_ols_cluster_hac(
                sd["d_coal_co2"].to_numpy(dtype=np.float64),
                sd["d_net_load"].to_numpy(dtype=np.float64)[:, None],
                date_clusters=sd["date"].to_numpy(),
                fe_groups=[sd[fe_col].to_numpy()],
                col_names=["d_net_load"],
                nw_lags=24,
            )
            return {
                "n_obs": len(sd),
                "n_fe_cells": int(sd[fe_col].nunique()),
                "total_mef": float(rt["coefs"]["d_net_load"]["beta"]),
                "total_se": float(rt["coefs"]["d_net_load"]["se_day"]),
                "coal_mef": float(rc["coefs"]["d_net_load"]["beta"]),
                "coal_se": float(rc["coefs"]["d_net_load"]["se_day"]),
            }

        # (1) Fine-cell FE checks across renewable bins
        fe_specs_out: dict[str, list[dict[str, Any]]] = {}
        for fe_col in ("seas_hr", "seas_hr_lq", "seas_hr_ld", "ym_hr_lq"):
            rows_fe = []
            for lbl, lo, hi in ren_bins:
                m_int = (gd["ren_share"] >= lo) & (gd["ren_share"] < hi) & (gd["ren_prev"] >= lo) & (gd["ren_prev"] < hi)
                res_f = _fit_bin_fe(gd[m_int], fe_col)
                rows_fe.append({"bin": lbl, **(res_f if res_f is not None else {"n_obs": 0})})
            fe_specs_out[fe_col] = rows_fe

        # (2) Common-Support Exact Cell-Matched (Season x Hour x Load-Quartile) Comparison:
        #     Compare <40% vs >60% strictly inside identical (Season x Hour x Load-Quartile) cells
        #     reweighted to the exact >60% cell distribution!
        m_low = (gd["ren_share"] < 0.40) & (gd["ren_prev"] < 0.40)
        m_high = (gd["ren_share"] >= 0.60) & (gd["ren_prev"] >= 0.60)
        cells_low = set(gd.loc[m_low, "seas_hr_lq"].unique())
        cells_high = set(gd.loc[m_high, "seas_hr_lq"].unique())
        common_cells = sorted(cells_low & cells_high)

        gd_lo_cs = gd[m_low & gd["seas_hr_lq"].isin(common_cells)].copy()
        gd_hi_cs = gd[m_high & gd["seas_hr_lq"].isin(common_cells)].copy()

        # Cell-matched WLS: weight each low-ren obs in cell c by (n_high_c / n_low_c) so cell marginals match >60% identically!
        hi_counts = gd_hi_cs["seas_hr_lq"].value_counts().to_dict()
        lo_counts = gd_lo_cs["seas_hr_lq"].value_counts().to_dict()

        def _weighted_cell_matched_slope(sub_df: pd.DataFrame, cell_w_map: dict[str, float]) -> dict[str, float]:
            # Trim extreme 8x MAD ramps
            xn = sub_df["d_net_load"].to_numpy(dtype=np.float64)
            med_x = float(np.median(xn))
            mad_x = float(np.median(np.abs(xn - med_x)))
            sd = sub_df.iloc[np.abs(xn - med_x) <= 8.0 * 1.4826 * mad_x] if mad_x > 1e-6 else sub_df
            vc = sd["seas_hr_lq"].value_counts()
            sd = sd[sd["seas_hr_lq"].isin(vc[vc >= 2].index)]
            w = sd["seas_hr_lq"].map(cell_w_map).to_numpy(dtype=np.float64)
            fe_c, fe_u = pd.factorize(sd["seas_hr_lq"].to_numpy(), sort=False)
            m_f = len(fe_u)
            sw = np.maximum(np.bincount(fe_c, weights=w, minlength=m_f), 1e-9)
            x = sd["d_net_load"].to_numpy(dtype=np.float64)
            y_tot = sd["d_co2"].to_numpy(dtype=np.float64)
            y_cl = sd["d_coal_co2"].to_numpy(dtype=np.float64)
            xd = x - (np.bincount(fe_c, weights=w * x, minlength=m_f) / sw)[fe_c]
            ytd = y_tot - (np.bincount(fe_c, weights=w * y_tot, minlength=m_f) / sw)[fe_c]
            ycd = y_cl - (np.bincount(fe_c, weights=w * y_cl, minlength=m_f) / sw)[fe_c]
            sxx = float(np.sum(w * xd * xd))
            bt = float(np.sum(w * xd * ytd) / max(sxx, 1.0))
            bc = float(np.sum(w * xd * ycd) / max(sxx, 1.0))
            # Date-clustered SE for weighted slope
            dc, du = pd.factorize(sd["date"].to_numpy(), sort=False)
            G = len(du)
            dfc = (G / max(G - 1.0, 1.0)) * ((len(sd) - 1.0) / max(len(sd) - m_f - 1.0, 1.0))
            sg_t = np.bincount(dc, weights=w * xd * (ytd - bt * xd), minlength=G)
            sg_c = np.bincount(dc, weights=w * xd * (ycd - bc * xd), minlength=G)
            se_t = float(np.sqrt(max(dfc * float(sg_t @ sg_t) / (sxx * sxx), 0.0)))
            se_c = float(np.sqrt(max(dfc * float(sg_c @ sg_c) / (sxx * sxx), 0.0)))
            return {
                "n_obs": len(sd),
                "n_common_cells": int(sd["seas_hr_lq"].nunique()),
                "total_mef": bt,
                "total_se": se_t,
                "coal_mef": bc,
                "coal_se": se_c,
            }

        lo_w_map = {c: float(hi_counts[c] / max(lo_counts[c], 1)) for c in common_cells}
        hi_w_map = {c: 1.0 for c in common_cells}
        cs_lo_matched = _weighted_cell_matched_slope(gd_lo_cs, lo_w_map)
        cs_hi_matched = _weighted_cell_matched_slope(gd_hi_cs, hi_w_map)
        diff_tot = cs_hi_matched["total_mef"] - cs_lo_matched["total_mef"]
        se_diff_tot = float(np.hypot(cs_hi_matched["total_se"], cs_lo_matched["total_se"]))
        diff_coal = cs_hi_matched["coal_mef"] - cs_lo_matched["coal_mef"]
        se_diff_coal = float(np.hypot(cs_hi_matched["coal_se"], cs_lo_matched["coal_se"]))

        # (3) Midday Solar (10-16) vs Overnight Wind (23-06) split in >60% renewables
        diurnal_gt60 = {}
        for wname in ("Midday Solar", "Overnight"):
            hrs = DIURNAL_WINDOWS[wname]
            sub_w = gd[m_high & gd["hour"].isin(hrs)]
            diurnal_gt60[wname] = _fit_bin_fe(sub_w, "seas_hr_lq")

        ercot_stress_test[ba] = {
            "fine_cell_fe_stratification": fe_specs_out,
            "common_support_exact_matched_seas_hr_lq": {
                "n_common_cells_total": len(common_cells),
                "low_ren_lt40_reweighted_to_gt60": cs_lo_matched,
                "high_ren_gt60_common_support": cs_hi_matched,
                "diff_gt60_minus_lt40_total_mef": float(diff_tot),
                "diff_gt60_minus_lt40_total_se": se_diff_tot,
                "diff_gt60_minus_lt40_total_p": float(2.0 * stats.norm.sf(abs(diff_tot / max(se_diff_tot, 1e-9)))),
                "diff_gt60_minus_lt40_coal_mef": float(diff_coal),
                "diff_gt60_minus_lt40_coal_se": se_diff_coal,
                "diff_gt60_minus_lt40_coal_p": float(2.0 * stats.norm.sf(abs(diff_coal / max(se_diff_coal, 1e-9)))),
            },
            "gt60_diurnal_split_seas_hr_lq_fe": diurnal_gt60,
        }
        print(
            f"  [Matched Stress Test {ba}] Common-support SeasxHrxLoadQ ({len(common_cells)} cells): "
            f"<40%={cs_lo_matched['total_mef']:.1f} (coal {cs_lo_matched['coal_mef']:.1f}) vs "
            f">60%={cs_hi_matched['total_mef']:.1f} (coal {cs_hi_matched['coal_mef']:.1f}) | "
            f"diff={diff_tot:+.1f}±{se_diff_tot:.1f} (coal diff={diff_coal:+.1f}±{se_diff_coal:.1f}) | "
            f"Load-Decile FE >60%: {fe_specs_out['seas_hr_ld'][3].get('total_mef', 0):.1f} "
            f"(coal {fe_specs_out['seas_hr_ld'][3].get('coal_mef', 0):.1f})",
            flush=True,
        )

    # ------------------------------------------------------------------
    # PART 8: SAVE JSON RECEIPT & EXPORT MACHINE-READABLE CSV TABLES
    # ------------------------------------------------------------------
    out_json = {
        "reconciliation_bridge_t1_vs_t2": bridge,
        "unconditional_season_stratified_utc_bootstrap_1000": {
            "B": B_BOOT,
            "seasons": ["DJF", "MAM", "JJA", "SON"],
            "n_utc_days_full": n_all,
            "n_utc_days_same_window": n_ov,
            "full_window_202407_202609": uncond_full_by_L,
            "same_window_202407_202512": uncond_same_by_L,
            "conditional_vs_unconditional_14d_comparison": cond_14d_comparison,
        },
        "lobao_and_concentration_audit": lobao_audit,
        "out_of_sample_validation": oos_validation,
        "lead_lag_timing_diagnostic_m3_p3": lead_lag_results,
        "caiso_upper_bound_frontier_roots": {
            "ciso_2026_nameplate_gw": ciso_2026_gw,
            "roots": frontier_breakeven_roots,
        },
        "ercot_and_ciso_matched_stress_test": ercot_stress_test,
        "elapsed_sec": float(time.time() - t0),
    }
    sha = save_json_lf(RES_DIR / "03c_k1_v5_unconditional_audit.json", out_json)
    print(f"[DONE STEP 03c JSON] Saved results/03c_k1_v5_unconditional_audit.json (SHA-256: {sha})", flush=True)

    # Export clean machine-readable CSV tables into tables/
    TABLES_DIR.mkdir(parents=True, exist_ok=True)

    # 1) tables/table1_14ba_accounting.csv
    t1_rows = []
    lob_map = {r["dropped_ba"]: r for r in lobao_rows}
    for r in sorted(r3["ba_carbon_table"], key=lambda x: -x["dis_gwh_cems_window"]):
        b = r["ba"]
        lb = lob_map[b]
        t1_rows.append(
            {
                "ba": b,
                "dc_coupled_flag": r["dc_coupled_flag"],
                "dis_gwh_cems_window": round(r["dis_gwh_cems_window"], 3),
                "dis_share_pct": round(lb["ba_dis_share_pct"], 3),
                "rte": round(r["rte"], 4),
                "net_aef_kg_mwh": round(r["net_aef_kg_mwh"], 3),
                "net_cems_kg_mwh": round(r["net_cems_kg_mwh"], 3),
                "se_net_cems_24h_kg_mwh": round(r["se_net_cems_kg_mwh"], 3),
                "mef_cems_chg_kg_mwh": round(r["mef_cems_chg_kg_mwh"], 3),
                "mef_cems_dis_kg_mwh": round(r["mef_cems_dis_kg_mwh"], 3),
                "alpha_star_cems_pct": round(100.0 * r["alpha_star_cems"], 3),
                "net_aef_kt": round(r["net_aef_kt"], 3),
                "net_cems_kt": round(r["net_cems_kt"], 3),
                "discrepancy_kt": round(r["net_cems_kt"] - r["net_aef_kt"], 3),
                "discrepancy_share_pct": round(lb["ba_disc_share_pct"], 3),
                "lobao_remaining_disc_mt": round(lb["remaining_disc_mt"], 4),
                "lobao_remaining_disc_kg_mwh": round(lb["remaining_disc_kg_mwh"], 3),
            }
        )
    fl13 = r3["fleet_aggregates"]["clean_13_ac_bas"]
    fl14 = r3["fleet_aggregates"]["all_14_bas"]
    for lbl, fl_obj in (("13_CLEAN_AC", fl13), ("ALL_14_GRIDS", fl14)):
        t1_rows.append(
            {
                "ba": lbl,
                "dc_coupled_flag": False,
                "dis_gwh_cems_window": round(fl_obj["dis_gwh_cems_window"], 3),
                "dis_share_pct": round(100.0 * fl_obj["dis_gwh_cems_window"] / fl14["dis_gwh_cems_window"], 3),
                "rte": round(
                    r1["metered_14_bas_totals"]["fleet_13_ac_rte"]
                    if lbl == "13_CLEAN_AC"
                    else (r1["metered_14_bas_totals"]["total_14_dis_gwh"] / r1["metered_14_bas_totals"]["total_14_chg_gwh"]),
                    4,
                ),
                "net_aef_kg_mwh": round(fl_obj["aef_kg_mwh"], 3),
                "net_cems_kg_mwh": round(fl_obj["cems_mef_kg_mwh"], 3),
                "se_net_cems_24h_kg_mwh": np.nan,
                "mef_cems_chg_kg_mwh": np.nan,
                "mef_cems_dis_kg_mwh": np.nan,
                "alpha_star_cems_pct": np.nan,
                "net_aef_kt": round(fl_obj["aef_total_kt"], 3),
                "net_cems_kt": round(fl_obj["cems_mef_total_kt"], 3),
                "discrepancy_kt": round(fl_obj["sign_reversal_cems_minus_aef_kt"], 3),
                "discrepancy_share_pct": round(100.0 * fl_obj["sign_reversal_cems_minus_aef_kt"] / fl14["sign_reversal_cems_minus_aef_kt"], 3),
                "lobao_remaining_disc_mt": np.nan,
                "lobao_remaining_disc_kg_mwh": np.nan,
            }
        )
    _write_csv_lf(TABLES_DIR / "table1_14ba_accounting.csv", pd.DataFrame(t1_rows))

    # 2) tables/table2_joint_bootstrap_curtailment.csv
    t2_rows = []
    scenarios = [
        ("u0", "Baseline alpha=0% (14 grids)", "u0_net_mt", "u0_disc_mt"),
        ("u10", "Uniform alpha=10% (14 grids)", "u10_net_mt", "u10_disc_mt"),
        ("u15", "Uniform alpha=15% (14 grids)", "u15_net_mt", "u15_disc_mt"),
        ("u20", "Uniform alpha=20% (14 grids)", "u20_net_mt", "u20_disc_mt"),
        ("h0_main", "Hybrid Empirical CAISO + Non-CAISO 0%", "h0_main_mt", "h0_main_disc_mt"),
        ("h10_main", "Hybrid Empirical CAISO + Non-CAISO 10%", "h10_main_mt", "h10_main_disc_mt"),
        ("h15_main", "Hybrid Empirical CAISO + Non-CAISO 15%", "h15_main_mt", "h15_main_disc_mt"),
        ("leave_ciso_u0", "Leave-CISO-Out (13 grids, alpha=0%)", "leave_ciso_u0_net_mt", "leave_ciso_u0_disc_mt"),
        ("leave_erco_u0", "Leave-ERCO-Out (13 grids, alpha=0%)", "leave_erco_u0_net_mt", "leave_erco_u0_disc_mt"),
        ("leave_ciso_erco_u0", "Leave-CISO-&-ERCO-Out (12 grids, alpha=0%)", "leave_ciso_erco_u0_net_mt", "leave_ciso_erco_u0_disc_mt"),
    ]
    for mode_lbl, win_lbl, boot_dict, block_list in [
        ("unconditional_season_utc", "full_27m_49.77TWh", uncond_full_by_L, ["7d", "14d", "28d"]),
        ("unconditional_season_utc", "same_18m_26.05TWh", uncond_same_by_L, ["7d", "14d", "28d"]),
    ]:
        for bl in block_list:
            bd = boot_dict[bl]
            for sid, slbl, k_net, k_disc in scenarios:
                t2_rows.append(
                    {
                        "bootstrap_mode": mode_lbl,
                        "window": win_lbl,
                        "block_length": bl,
                        "scenario_id": sid,
                        "scenario_label": slbl,
                        "net_mt_point": round(bd[k_net]["point"], 4),
                        "net_mt_ci95_lo": round(bd[k_net]["ci95_lo"], 4),
                        "net_mt_ci95_hi": round(bd[k_net]["ci95_hi"], 4),
                        "disc_mt_point": round(bd[k_disc]["point"], 4),
                        "disc_mt_ci95_lo": round(bd[k_disc]["ci95_lo"], 4),
                        "disc_mt_ci95_hi": round(bd[k_disc]["ci95_hi"], 4),
                        "disc_covers_zero": bd[k_disc]["covers_zero"],
                    }
                )
    # Also include conditional 14d rows from 03b for complete side-by-side audit
    for win_lbl, src_b in [
        ("full_27m_49.77TWh", r3b["full_window_joint_14d_bootstrap_1000"]["metrics"]),
        ("same_18m_26.05TWh", r3b["same_window_joint_14d_bootstrap_1000"]["metrics"]),
    ]:
        for sid, slbl, k_net, k_disc in scenarios[:7]:
            t2_rows.append(
                {
                    "bootstrap_mode": "conditional_v4_fixed_aef_dis_trade",
                    "window": win_lbl,
                    "block_length": "14d",
                    "scenario_id": sid,
                    "scenario_label": slbl,
                    "net_mt_point": round(src_b[k_net]["point"], 4),
                    "net_mt_ci95_lo": round(src_b[k_net]["ci95_lo"], 4),
                    "net_mt_ci95_hi": round(src_b[k_net]["ci95_hi"], 4),
                    "disc_mt_point": round(src_b[k_disc]["point"], 4),
                    "disc_mt_ci95_lo": round(src_b[k_disc]["ci95_lo"], 4),
                    "disc_mt_ci95_hi": round(src_b[k_disc]["ci95_hi"], 4),
                    "disc_covers_zero": src_b[k_disc]["covers_zero"],
                }
            )
    _write_csv_lf(TABLES_DIR / "table2_joint_bootstrap_curtailment.csv", pd.DataFrame(t2_rows))

    # 3) tables/fig4_frontier_and_ercot.csv
    f4_rows = []
    for fobj in r3b["congestion_constrained_carbon_frontier"]:
        tau = fobj["tau_local_access"]
        for pt in fobj["curve"]:
            f4_rows.append(
                {
                    "panel": "Fig4A_CAISO_BA_Upper_Bound_Scenario",
                    "ba_or_regime": f"CISO_tau_{int(100*tau)}pct",
                    "kappa_or_bin": f"{pt['kappa']:.2f}x",
                    "incremental_gw_or_n_obs": round(pt["kappa"] * ciso_2026_gw, 3),
                    "rho_res_or_chg_share_pct": round(100.0 * pt["rho_res"], 3),
                    "mef_or_net_co2_kg_mwh": round(pt["implied_net_co2_kg_mwh"], 3),
                    "se_kg_mwh": np.nan,
                    "coal_mef_kg_mwh": np.nan,
                    "specification": "Fixed-profile BA-level upper-bound accounting scenario (non-nodal)",
                }
            )
    for ba in ["ERCO", "CISO", "MISO", "AZPS"]:
        for bobj in r3b["cross_regional_ren_penetration_stratification"][ba]:
            f4_rows.append(
                {
                    "panel": "Fig4B_Cross_Regime_Stress_Test_YMxHr",
                    "ba_or_regime": ba,
                    "kappa_or_bin": bobj["bin"],
                    "incremental_gw_or_n_obs": bobj["n_interior_hours"],
                    "rho_res_or_chg_share_pct": round(bobj["pct_chg"], 3),
                    "mef_or_net_co2_kg_mwh": round(bobj["mef_dom_netload_kg_mwh"], 3) if bobj["mef_dom_netload_kg_mwh"] is not None else np.nan,
                    "se_kg_mwh": round(bobj["se_netload"], 3) if bobj["se_netload"] is not None else np.nan,
                    "coal_mef_kg_mwh": round(bobj["coal_mef_netload_kg_mwh"], 3) if bobj["coal_mef_netload_kg_mwh"] is not None else np.nan,
                    "specification": "YM x Hour FE interior renewable-penetration stratification",
                }
            )
    for ba in ["ERCO", "CISO"]:
        for fe_name in ("seas_hr_lq", "seas_hr_ld"):
            for bobj in ercot_stress_test[ba]["fine_cell_fe_stratification"][fe_name]:
                if bobj.get("n_obs", 0) > 0:
                    f4_rows.append(
                        {
                            "panel": f"Fig4B_Matched_Stress_Test_{fe_name}",
                            "ba_or_regime": ba,
                            "kappa_or_bin": bobj["bin"],
                            "incremental_gw_or_n_obs": bobj["n_obs"],
                            "rho_res_or_chg_share_pct": np.nan,
                            "mef_or_net_co2_kg_mwh": round(bobj["total_mef"], 3),
                            "se_kg_mwh": round(bobj["total_se"], 3),
                            "coal_mef_kg_mwh": round(bobj["coal_mef"], 3),
                            "specification": f"Matched {fe_name} FE interior renewable-penetration stress test",
                        }
                    )
    _write_csv_lf(TABLES_DIR / "fig4_frontier_and_ercot.csv", pd.DataFrame(f4_rows))

    # 4) tables/table_oos_and_leadlag.csv
    oos_rows = []
    for ba, ev in holdout_by_ba.items():
        oos_rows.append(
            {
                "analysis": "temporal_holdout_2407_2509_to_2510_2609",
                "ba": ba,
                "lag_or_quarter": "2025-10..2026-09",
                "n_obs": ev["n_test"],
                "metric_1": round(ev["r2_oos"], 4),
                "metric_1_name": "r2_oos",
                "metric_2": round(ev["cal_slope"], 4),
                "metric_2_name": "calibration_slope",
                "metric_3": round(ev["rmse_t"], 3),
                "metric_3_name": "rmse_tco2_hr",
            }
        )
    for qr in lqo_rows:
        oos_rows.append(
            {
                "analysis": "leave_quarter_out_cv",
                "ba": "MAJOR4_AND_FLEET14",
                "lag_or_quarter": qr["quarter"],
                "n_obs": np.nan,
                "metric_1": round(qr["major4_pooled_r2_oos"], 4),
                "metric_1_name": "major4_r2_oos",
                "metric_2": round(qr["oos_pred_disc_mt"], 4),
                "metric_2_name": "oos_pred_disc_mt",
                "metric_3": round(qr["actual_disc_mt"], 4),
                "metric_3_name": "actual_disc_mt",
            }
        )
    for ba, ll_d in lead_lag_results.items():
        for k in lags_k:
            c_k = ll_d["dco2_on_dbess_leads_lags"][str(k)]
            i_k = ll_d["dimports_on_dbess_leads_lags"][str(k)]
            oos_rows.append(
                {
                    "analysis": "lead_lag_dbess_m3_p3",
                    "ba": ba,
                    "lag_or_quarter": f"k={k:+d}h",
                    "n_obs": ll_d["n_hours"],
                    "metric_1": round(c_k["beta"], 3),
                    "metric_1_name": "dco2_dbess_kg_mwh",
                    "metric_2": round(c_k["se_day"], 3),
                    "metric_2_name": "dco2_se_day",
                    "metric_3": round(i_k["beta"], 4),
                    "metric_3_name": "dimports_dbess_mw_mw",
                }
            )
    _write_csv_lf(TABLES_DIR / "table_oos_and_leadlag.csv", pd.DataFrame(oos_rows))
    print(f"[DONE STEP 03c] Exported 4 machine-readable CSV tables to tables/ in {time.time()-t0:.1f}s.", flush=True)
    return 0


def _write_csv_lf(path: Path, df: pd.DataFrame) -> None:
    txt = df.to_csv(index=False).replace("\r\n", "\n")
    path.write_bytes(txt.encode("utf-8"))
    print(f"  [CSV] {path.relative_to(WS_DIR).as_posix()} ({len(df)} rows)", flush=True)


if __name__ == "__main__":
    raise SystemExit(main())
