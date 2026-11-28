"""Step 12: Equal-budget operational monitoring protocol comparison and cost-effectiveness analysis
across US (USGS) and England (EA) multi-year UTC sensor panels.

Compares deployable protocols under fixed annual visit budgets (12, 24, 52 visits/site-year)
and identical total dollar budgets with explicit decomposition of travel/access, nocturnal
labor/safety surcharge (1.0x, 1.35x, 1.75x, 2.5x), and amortized continuous sonde O&M costs.
Evaluates:
  - Canonical 14:30 afternoon grab schedule
  - Real-world Empirical WQP Agency Grab Clock (10,019 timestamped US field visits)
  - Daytime-Safe Rotating (07:00 / 10:30 / 14:30, zero night surcharge)
  - Dawn-Included Rotating (Pre-dawn / 10:30 / 14:30)
  - 50/50 Alternating (Pre-dawn / 14:30)
  - First-Light Daylight Grabs (Sunrise + 30 min — early-shift daylight, avoiding pitch-dark safety hazards!)
  - Targeted Pre-Dawn Grabs (Sunrise - 30 min)
  - Risk-Stratified Continuous Sonde Allocation (top-10% and top-20% sites via strictly out-of-sample
    Year-1 daytime screening, Leave-One-Region-Out static covariates, and Oracle upper bound + daytime/first-light grabs elsewhere)

Reports BOTH actionable site-nights AND distinct non-overlapping hypoxic episodes (preventing
multi-day event double-counting by continuous sondes!), impaired site-years flagged, detection
lead times (overall AND episodic <24h separately), LORO reference-negative alarm rates, and cost per detection.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROC = DATA / "processed"
RES = ROOT / "results"
TBL = ROOT / "tables"

N_MC = 1000
RNG_SEED = 20261128

DAYTIME_VISIT_USD_BENCHMARK = 200.0
NIGHT_COST_MULTIPLIERS = (1.0, 1.35, 1.75, 2.5)
SONDE_ANNUAL_VISIT_EQS = (20, 30, 40, 60, 80, 100)
ANNUAL_VISIT_BUDGETS = (12, 24, 52)


def build_empirical_wqp_clock_weights() -> dict:
    wqp_path = DATA / "raw_wqp" / "wqp_conus397_2015_2024.parquet"
    raw = pd.read_parquet(wqp_path)
    visits = raw.groupby(["site", "time_utc"], as_index=False).agg(
        solar_hr=("solar_hr", "first"),
        local_clock_hr=("local_clock_hr", "first"),
    )
    sh = visits["solar_hr"].to_numpy(dtype=float)
    bins = [
        ("predawn", (sh < 6.0)),
        ("morning07", (sh >= 6.0) & (sh < 7.5)),
        ("morning08", (sh >= 7.5) & (sh < 9.25)),
        ("overpass", (sh >= 9.25) & (sh < 11.25)),
        ("midday12", (sh >= 11.25) & (sh < 13.25)),
        ("afternoon", (sh >= 13.25) & (sh < 15.25)),
        ("latepm16", (sh >= 15.25) & (sh < 18.0)),
        ("evening20", (sh >= 18.0)),
    ]
    weights = {col: float(mask.sum() / len(sh)) for col, mask in bins}
    return {"n_wqp_visits": len(sh), "bin_weights": weights, "sum_weights": float(sum(weights.values()))}


def assign_distinct_episode_ids(day_indices: np.ndarray, act_mask: np.ndarray) -> np.ndarray:
    """Group consecutive actionable site-nights (gap <= 1 day) into distinct non-overlapping hypoxic events.
    Returns integer episode IDs >= 1 for actionable nights and 0 for non-actionable nights.
    """
    ep_ids = np.zeros(len(act_mask), dtype=int)
    cur_id = 0
    prev_day = -999999
    for i, (d, is_a) in enumerate(zip(day_indices, act_mask, strict=True)):
        if is_a:
            if d - prev_day > 1:
                cur_id += 1
            ep_ids[i] = cur_id
            prev_day = int(d)
    return ep_ids


def evaluate_visit_level_protocols(
    df_net: pd.DataFrame,
    wqp_weights: dict[str, float],
    thr: float,
    actionable_col: str,
) -> dict:
    k = int(thr)
    act = df_net[actionable_col].astype(bool).to_numpy()
    full_dur = df_net[f"t{k}_full_dur_hr"].to_numpy(dtype=float)
    episodic_act = act & np.isfinite(full_dur) & (full_dur < 24.0)
    chronic_act = act & (~episodic_act)
    loro_pos = df_net["night_min_loro"].to_numpy() < thr
    n_tot = len(df_net)
    n_act = int(act.sum())
    n_episodic = int(episodic_act.sum())

    ep_start = df_net[f"t{k}_ep_start_rel_sr_hr"].to_numpy(dtype=float)
    ep_nadir = df_net[f"t{k}_ep_nadir_rel_sr_hr"].to_numpy(dtype=float)
    ep_end = df_net[f"t{k}_ep_end_rel_sr_hr"].to_numpy(dtype=float)

    col_vals: dict[str, np.ndarray] = {}
    col_rel: dict[str, np.ndarray] = {}
    col_loro_ref: dict[str, np.ndarray] = {}
    default_rel_map = {
        "predawn": ("predawn_rel_sr_hr", -0.5),
        "sr_p0": (None, 0.0),
        "sr_p30": (None, 0.5),
        "sr_m60": (None, -1.0),
        "sr_m120": (None, -2.0),
        "morning07": ("morning07_rel_sr_hr", 1.7),
        "morning08": ("morning08_rel_sr_hr", 2.7),
        "overpass": ("overpass_rel_sr_hr", 5.2),
        "midday12": ("midday12_rel_sr_hr", 6.7),
        "afternoon": ("afternoon_rel_sr_hr", 9.2),
        "latepm16": ("latepm16_rel_sr_hr", 10.7),
        "evening20": ("evening20_rel_sr_hr", -9.3),
        "midnight": ("midnight_rel_sr_hr", -5.3),
    }
    for c, (rcol, fallback_rel) in default_rel_map.items():
        if c in df_net.columns:
            col_vals[c] = df_net[c].to_numpy(dtype=float)
            if rcol and rcol in df_net.columns:
                col_rel[c] = df_net[rcol].to_numpy(dtype=float)
            else:
                col_rel[c] = np.full(n_tot, fallback_rel, dtype=float)
            lcol = f"loro_min_{c}"
            col_loro_ref[c] = (df_net[lcol].to_numpy(dtype=float) < thr) if lcol in df_net.columns else loro_pos

    protocols: dict[str, list[tuple[str, float, bool]]] = {
        "afternoon_1430": [("afternoon", 1.0, False)],
        "empirical_wqp_clock": [(c, w, c == "predawn") for c, w in wqp_weights.items()],
        "overpass_1030": [("overpass", 1.0, False)],
        "rotating_daytime_safe": [("morning07", 1 / 3, False), ("overpass", 1 / 3, False), ("afternoon", 1 / 3, False)],
        "rotating_dawn_included": [("predawn", 1 / 3, True), ("overpass", 1 / 3, False), ("afternoon", 1 / 3, False)],
        "alternating_50_50": [("predawn", 0.5, True), ("afternoon", 0.5, False)],
        "first_light_sr_p30": [("sr_p30", 1.0, False)],
        "sunrise_sr_p0": [("sr_p0", 1.0, False)],
        "predawn_sr_m30": [("predawn", 1.0, True)],
        "early_night_sr_m120": [("sr_m120", 1.0, True)],
    }

    def lead_summary(mask_sub: np.ndarray, t_samp: np.ndarray | None = None, weights_sub: np.ndarray | None = None) -> dict:
        if t_samp is None:
            # Continuous sonde telemetry triggers 0.5 h after episode onset
            le = ep_end[mask_sub] - (ep_start[mask_sub] + 0.5)
            ln = ep_nadir[mask_sub] - (ep_start[mask_sub] + 0.5)
            ok = np.isfinite(le) & np.isfinite(ln)
            if not ok.any():
                return {"n": 0, "median_lead_end_hr": None, "median_lead_nadir_hr": None, "pct_active": None, "pct_before_nadir": None}
            return {
                "n": int(ok.sum()),
                "median_lead_end_hr": float(np.median(le[ok])),
                "iqr_lead_end_hr": [float(np.percentile(le[ok], 25)), float(np.percentile(le[ok], 75))],
                "median_lead_nadir_hr": float(np.median(ln[ok])),
                "pct_active": 100.0,
                "pct_before_nadir": float(100.0 * np.mean(ln[ok] > 0.0)),
            }
        le = ep_end[mask_sub] - t_samp
        ln = ep_nadir[mask_sub] - t_samp
        is_act_now = (t_samp >= ep_start[mask_sub] - 0.5) & (t_samp <= ep_end[mask_sub] + 0.25)
        ok = np.isfinite(le) & np.isfinite(ln)
        if not ok.any():
            return {"n": 0, "median_lead_end_hr": None, "median_lead_nadir_hr": None, "pct_active": None, "pct_before_nadir": None}
        w = weights_sub[ok] if weights_sub is not None else np.ones(int(ok.sum()))
        def wq(a: np.ndarray, q: float) -> float:
            o = np.argsort(a)
            cs = np.cumsum(w[o])
            cs /= cs[-1]
            return float(np.interp(q, cs, a[o]))
        return {
            "n": int(ok.sum()),
            "median_lead_end_hr": wq(le[ok], 0.5),
            "iqr_lead_end_hr": [wq(le[ok], 0.25), wq(le[ok], 0.75)],
            "median_lead_nadir_hr": wq(ln[ok], 0.5),
            "pct_active": float(100.0 * np.average(is_act_now[ok].astype(float), weights=w)),
            "pct_before_nadir": float(100.0 * np.average((ln[ok] > 0.0).astype(float), weights=w)),
        }

    out: dict = {
        "n_site_nights": int(n_tot),
        "n_actionable_nights": int(n_act),
        "n_episodic_lt24h_nights": int(n_episodic),
        "n_chronic_ge24h_nights": int(chronic_act.sum()),
        "actionable_prevalence_pct": float(100.0 * n_act / max(1, n_tot)),
        "continuous_sonde_benchmark": {
            "actionable_recall_pct": 100.0,
            "all_actionable_lead": lead_summary(act),
            "episodic_lt24h_lead": lead_summary(episodic_act),
        },
        "protocols": {},
    }

    for pname, mix in protocols.items():
        p_det_act = np.zeros(n_tot, dtype=float)
        p_det_epi = np.zeros(n_tot, dtype=float)
        p_det_loro = np.zeros(n_tot, dtype=float)
        p_fa_loro = np.zeros(n_tot, dtype=float)
        night_frac = 0.0

        all_idx, all_ts, all_w = [], [], []
        epi_idx, epi_ts, epi_w = [], [], []

        for col, w, is_night in mix:
            if w <= 0:
                continue
            night_frac += w if is_night else 0.0
            vals = col_vals[col]
            rels = col_rel[col]
            v_use = np.where(np.isfinite(vals), vals, col_vals["afternoon"])
            r_use = np.where(np.isfinite(vals), rels, col_rel["afternoon"])
            flag = v_use < thr
            lref = col_loro_ref[col]

            p_det_act += w * (flag & act).astype(float)
            p_det_epi += w * (flag & episodic_act).astype(float)
            p_det_loro += w * (flag & lref).astype(float)
            p_fa_loro += w * (flag & (~lref)).astype(float)

            da = np.flatnonzero(flag & act)
            if len(da):
                all_idx.append(da)
                all_ts.append(r_use[da])
                all_w.append(np.full(len(da), w, dtype=float))
            de = np.flatnonzero(flag & episodic_act)
            if len(de):
                epi_idx.append(de)
                epi_ts.append(r_use[de])
                epi_w.append(np.full(len(de), w, dtype=float))

        act_recall = float(100.0 * p_det_act.sum() / max(1, n_act))
        epi_recall = float(100.0 * p_det_epi.sum() / max(1, n_episodic))
        det_per_100v = float(100.0 * p_det_act.mean())
        epi_per_100v = float(100.0 * p_det_epi.mean())
        loro_recall = float(100.0 * p_det_loro.sum() / max(1, int(loro_pos.sum())))
        loro_fa = float(100.0 * p_fa_loro.sum() / max(1, int((~loro_pos).sum())))
        ppv = float(100.0 * p_det_act.sum() / max(1e-9, float((p_det_loro + p_fa_loro).sum())))

        lead_all = lead_summary(np.concatenate(all_idx), np.concatenate(all_ts), np.concatenate(all_w)) if all_idx else {}
        lead_epi = lead_summary(np.concatenate(epi_idx), np.concatenate(epi_ts), np.concatenate(epi_w)) if epi_idx else {}

        out["protocols"][pname] = {
            "night_shift_visit_fraction": float(night_frac),
            "actionable_recall_pct": act_recall,
            "episodic_lt24h_recall_pct": epi_recall,
            "loro_recall_pct": loro_recall,
            "actionable_detections_per_100_visits": det_per_100v,
            "episodic_detections_per_100_visits": epi_per_100v,
            "loro_ref_neg_alarm_pct": loro_fa,
            "ppv_actionable_pct": ppv,
            "all_actionable_lead": lead_all,
            "episodic_lt24h_lead": lead_epi,
        }

    base_af = out["protocols"]["afternoon_1430"]["actionable_detections_per_100_visits"]
    base_wqp = out["protocols"]["empirical_wqp_clock"]["actionable_detections_per_100_visits"]
    for blk in out["protocols"].values():
        blk["new_actionable_per_100_vs_afternoon"] = float(blk["actionable_detections_per_100_visits"] - base_af)
        blk["new_actionable_per_100_vs_wqp"] = float(blk["actionable_detections_per_100_visits"] - base_wqp)
    return out


def build_risk_rankings(df_net: pd.DataFrame, network: str, actionable_col: str) -> dict[str, pd.Series]:
    sites = sorted(df_net["site"].unique())
    oracle = df_net.groupby("site")[actionable_col].mean().reindex(sites).fillna(0.0)

    first_yr = df_net.groupby("site")["year"].transform("min")
    y1 = df_net[df_net["year"] == first_yr]
    y1_stats = y1.groupby("site")["afternoon"].agg(
        af_mean="mean",
        af_p10=lambda s: float(np.percentile(s, 10)),
        af_lt6=lambda s: float((s < 6.0).mean()),
    ).reindex(sites)
    y1_score = (
        -y1_stats["af_p10"].fillna(y1_stats["af_p10"].median())
        - 0.5 * y1_stats["af_mean"].fillna(y1_stats["af_mean"].median())
        + 5.0 * y1_stats["af_lt6"].fillna(0.0)
    )

    if network == "USGS":
        meta = pd.read_csv(PROC / "conus_iv_rivers_meta.csv", dtype={"site_no": str, "huc2": str}).rename(
            columns={"site_no": "site", "huc2": "cluster"}
        )
        covs = meta.set_index("site").reindex(sites)[["lat", "lon", "alt_va", "drain_area_va", "median_spcond", "cluster"]].copy()
        covs["log_da"] = np.log1p(covs["drain_area_va"].clip(lower=0).fillna(covs["drain_area_va"].median()))
        covs["log_sc"] = np.log1p(covs["median_spcond"].clip(lower=0).fillna(covs["median_spcond"].median()))
        covs["alt_f"] = covs["alt_va"].fillna(covs["alt_va"].median())
        feat_cols = ["lat", "lon", "alt_f", "log_da", "log_sc"]
    else:
        meta = pd.read_csv(PROC / "uk_ea_clean_rivers_results.csv", dtype={"notation": str}).rename(columns={"notation": "site"})
        covs = meta.set_index("site").reindex(sites)[["lat", "lon", "mean_temp"]].copy()
        covs["cluster"] = (
            np.floor(covs["lat"]).astype(int).astype(str) + ":" + np.floor(covs["lon"]).astype(int).astype(str)
        )
        feat_cols = ["lat", "lon", "mean_temp"]

    y_site = oracle.to_numpy(dtype=float)
    X_raw = covs[feat_cols].to_numpy(dtype=float)
    oos_pred = np.zeros(len(sites), dtype=float)
    clusters = covs["cluster"].astype(str).to_numpy()
    for cl in np.unique(clusters):
        te = clusters == cl
        tr = ~te
        mu = X_raw[tr].mean(axis=0)
        sd = X_raw[tr].std(axis=0)
        sd[sd < 1e-8] = 1.0
        X_tr = np.column_stack([np.ones(tr.sum()), (X_raw[tr] - mu) / sd])
        X_te = np.column_stack([np.ones(te.sum()), (X_raw[te] - mu) / sd])
        reg = np.eye(X_tr.shape[1]) * 5.0
        reg[0, 0] = 0.0
        beta = np.linalg.solve(X_tr.T @ X_tr + reg, X_tr.T @ y_site[tr])
        oos_pred[te] = X_te @ beta
    cov_score = pd.Series(oos_pred, index=sites)

    return {"y1_daytime_screening": y1_score, "loor_covariate_score": cov_score, "oracle_full_panel": oracle}


def simulate_equal_budget_calendars(
    df_net: pd.DataFrame,
    network: str,
    wqp_weights: dict[str, float],
    thr: float,
    actionable_col: str,
    rng: np.random.Generator,
) -> dict:
    rankings = build_risk_rankings(df_net, network, actionable_col)
    first_yr = df_net.groupby("site")["year"].transform("min")
    df_oos = df_net[df_net["year"] > first_yr].copy()
    sy_counts = df_oos.groupby(["site", "year"]).size()
    valid_sy = sy_counts[sy_counts >= 60].index
    df_eval = df_oos.set_index(["site", "year"]).loc[valid_sy].reset_index()

    n_site_years = len(valid_sy)
    sites_eval = sorted(df_eval["site"].unique())
    n_sites_eval = len(sites_eval)

    sy_list = []
    wqp_cols = list(wqp_weights.keys())
    wqp_probs = np.array([wqp_weights[c] for c in wqp_cols], dtype=float)
    wqp_probs /= wqp_probs.sum()

    for (site, yr), grp in df_eval.groupby(["site", "year"]):
        grp = grp.sort_values("day_index")
        act_arr = grp[actionable_col].astype(bool).to_numpy()
        loro_arr = grp["night_min_loro"].to_numpy() < thr
        ep_ids = assign_distinct_episode_ids(grp["day_index"].to_numpy(dtype=int), act_arr)
        n_distinct_eps = int(ep_ids.max())
        slot_flags = {}
        for col in ("afternoon", "overpass", "morning07", "morning08", "midday12", "latepm16", "evening20", "predawn", "sr_p30"):
            v = grp[col].to_numpy(dtype=float) if col in grp.columns else grp["afternoon"].to_numpy(dtype=float)
            v = np.where(np.isfinite(v), v, grp["afternoon"].to_numpy(dtype=float))
            slot_flags[col] = v < thr
        sy_list.append(
            {
                "site": str(site),
                "year": int(yr),
                "n_nights": len(grp),
                "act": act_arr,
                "loro": loro_arr,
                "ep_ids": ep_ids,
                "n_distinct_eps": n_distinct_eps,
                "has_any_act": bool(act_arr.any()),
                "n_act_nights": int(act_arr.sum()),
                "flags": slot_flags,
            }
        )

    n_impaired_sy = sum(1 for sy in sy_list if sy["has_any_act"])
    total_act_nights_panel = sum(sy["n_act_nights"] for sy in sy_list)
    total_distinct_eps_panel = sum(sy["n_distinct_eps"] for sy in sy_list)

    targeting_audit = {}
    for rname, score_s in rankings.items():
        ranked_sites = score_s.reindex(sites_eval).fillna(-1e9).sort_values(ascending=False).index.tolist()
        for frac in (0.10, 0.20):
            n_top = max(1, round(frac * n_sites_eval))
            top_set = set(ranked_sites[:n_top])
            cap_act = sum(sy["n_act_nights"] for sy in sy_list if sy["site"] in top_set)
            cap_eps = sum(sy["n_distinct_eps"] for sy in sy_list if sy["site"] in top_set)
            cap_imp_sy = sum(1 for sy in sy_list if sy["site"] in top_set and sy["has_any_act"])
            targeting_audit[f"{rname}_top{int(frac*100)}pct"] = {
                "n_sonde_sites": n_top,
                "share_of_all_actionable_nights_pct": float(100.0 * cap_act / max(1, total_act_nights_panel)),
                "share_of_distinct_episodes_pct": float(100.0 * cap_eps / max(1, total_distinct_eps_panel)),
                "share_of_impaired_site_years_pct": float(100.0 * cap_imp_sy / max(1, n_impaired_sy)),
            }

    def run_mc_grab_schedule(n_warm_visits: float, mode: str, sonde_sites: set[str] | None = None) -> dict:
        sonde_sites = sonde_sites or set()
        v_floor = int(np.floor(n_warm_visits))
        v_rem = float(n_warm_visits - v_floor)

        det_nights = np.zeros(N_MC, dtype=float)
        det_distinct_eps = np.zeros(N_MC, dtype=float)
        fa_counts = np.zeros(N_MC, dtype=float)
        visit_counts = np.zeros(N_MC, dtype=float)
        imp_flagged = np.zeros(N_MC, dtype=float)

        for sy in sy_list:
            if sy["site"] in sonde_sites:
                det_nights += sy["n_act_nights"]
                det_distinct_eps += sy["n_distinct_eps"]
                if sy["has_any_act"]:
                    imp_flagged += 1.0
                continue

            nn = sy["n_nights"]
            act_a = sy["act"]
            loro_a = sy["loro"]
            ep_ids = sy["ep_ids"]
            fl = sy["flags"]

            k_draws = v_floor + (rng.random(N_MC) < v_rem).astype(int)
            k_max = min(nn, int(k_draws.max()))
            if k_max == 0:
                continue

            bin_edges = np.linspace(0, nn, k_max + 1)
            lo_e = np.floor(bin_edges[:-1]).astype(int)
            hi_e = np.maximum(lo_e + 1, np.floor(bin_edges[1:]).astype(int))
            widths = np.maximum(1, hi_e - lo_e)
            idx_mat = lo_e[None, :] + np.floor(rng.random((N_MC, k_max)) * widths[None, :]).astype(int)
            idx_mat = np.clip(idx_mat, 0, nn - 1)
            active_mask = np.arange(k_max)[None, :] < k_draws[:, None]

            if mode == "afternoon_1430":
                hit_mat = fl["afternoon"][idx_mat]
            elif mode == "predawn_sr_m30":
                hit_mat = fl["predawn"][idx_mat]
            elif mode == "first_light_sr_p30":
                hit_mat = fl["sr_p30"][idx_mat]
            elif mode == "rotating_daytime_safe":
                cycle = np.arange(k_max) % 3
                hit_mat = np.where(
                    cycle[None, :] == 0,
                    fl["morning07"][idx_mat],
                    np.where(cycle[None, :] == 1, fl["overpass"][idx_mat], fl["afternoon"][idx_mat]),
                )
            elif mode == "rotating_dawn_included":
                cycle = np.arange(k_max) % 3
                hit_mat = np.where(
                    cycle[None, :] == 0,
                    fl["predawn"][idx_mat],
                    np.where(cycle[None, :] == 1, fl["overpass"][idx_mat], fl["afternoon"][idx_mat]),
                )
            elif mode == "alternating_50_50":
                cycle = np.arange(k_max) % 2
                hit_mat = np.where(cycle[None, :] == 0, fl["predawn"][idx_mat], fl["afternoon"][idx_mat])
            elif mode == "empirical_wqp_clock":
                slot_pick = rng.choice(len(wqp_cols), size=(N_MC, k_max), p=wqp_probs)
                hit_mat = np.zeros((N_MC, k_max), dtype=bool)
                for si, cname in enumerate(wqp_cols):
                    m_si = slot_pick == si
                    if m_si.any():
                        hit_mat[m_si] = fl[cname][idx_mat[m_si]]
            else:
                raise ValueError(f"Unknown mode: {mode}")

            act_mat = act_a[idx_mat] & active_mask
            loro_mat = loro_a[idx_mat] & active_mask
            det_mat = hit_mat & act_mat
            fa_mat = hit_mat & (~loro_mat) & active_mask

            n_det_sy = det_mat.sum(axis=1)
            det_nights += n_det_sy
            fa_counts += fa_mat.sum(axis=1)
            visit_counts += k_draws

            # Count distinct non-overlapping episodes detected per MC replicate (zero double-counting!)
            if sy["n_distinct_eps"] > 0 and det_mat.any():
                det_ep_ids = np.where(det_mat, ep_ids[idx_mat], 0)
                # Sort along visit axis; count positive transitions > 0
                det_ep_ids.sort(axis=1)
                n_uniq = (det_ep_ids[:, 0] > 0).astype(int)
                if k_max > 1:
                    n_uniq = n_uniq + np.sum((det_ep_ids[:, 1:] > 0) & (det_ep_ids[:, 1:] != det_ep_ids[:, :-1]), axis=1)
                det_distinct_eps += n_uniq

            if sy["has_any_act"]:
                imp_flagged += (n_det_sy > 0).astype(float)

        return {
            "mean_actionable_nights_detected": float(det_nights.mean()),
            "ci95_actionable_nights_detected": [float(np.percentile(det_nights, 2.5)), float(np.percentile(det_nights, 97.5))],
            "mean_distinct_episodes_detected": float(det_distinct_eps.mean()),
            "ci95_distinct_episodes_detected": [float(np.percentile(det_distinct_eps, 2.5)), float(np.percentile(det_distinct_eps, 97.5))],
            "distinct_episodes_caught_pct": float(100.0 * det_distinct_eps.mean() / max(1, total_distinct_eps_panel)),
            "impaired_sy_flagged_pct": float(100.0 * imp_flagged.mean() / max(1, n_impaired_sy)),
            "impaired_sy_flagged_ci95_pct": [
                float(100.0 * np.percentile(imp_flagged, 2.5) / max(1, n_impaired_sy)),
                float(100.0 * np.percentile(imp_flagged, 97.5) / max(1, n_impaired_sy)),
            ],
            "mean_grab_visits_total": float(visit_counts.mean()),
            "loro_ref_neg_alarm_per_100_visits": float(100.0 * fa_counts.sum() / max(1.0, visit_counts.sum())),
            "share_of_all_panel_actionable_nights_pct": float(100.0 * det_nights.mean() / max(1, total_act_nights_panel)),
        }

    fixed_visit_results = {}
    for v_ann in ANNUAL_VISIT_BUDGETS:
        v_warm = v_ann / 2.0
        fixed_visit_results[f"annual_{v_ann}"] = {
            "annual_visits_per_site": v_ann,
            "warm_season_visits_per_site": v_warm,
            "protocols": {},
        }
        for mode in (
            "afternoon_1430",
            "empirical_wqp_clock",
            "rotating_daytime_safe",
            "rotating_dawn_included",
            "alternating_50_50",
            "first_light_sr_p30",
            "predawn_sr_m30",
        ):
            fixed_visit_results[f"annual_{v_ann}"]["protocols"][mode] = run_mc_grab_schedule(v_warm, mode)

    equal_budget_results: dict = {}
    for v_ann in ANNUAL_VISIT_BUDGETS:
        v_key = f"budget_{v_ann}_dayeq"
        tot_cost_dayeq = float(v_ann * n_site_years)
        eb_block: dict = {
            "annual_budget_dayeq_per_site": v_ann,
            "annual_budget_usd_per_site": v_ann * DAYTIME_VISIT_USD_BENCHMARK,
            "total_panel_budget_dayeq": tot_cost_dayeq,
            "grab_by_night_multiplier": {},
            "hybrid_sonde_by_cost": {},
        }

        for m_night in NIGHT_COST_MULTIPLIERS:
            m_key = f"m_{m_night:.2f}".replace(".", "p")
            m_rec = {}
            # First-light (SR+30m) is full civil daylight: zero dark-terrain lone-worker surcharge,
            # optional modest early-shift differential modeled as 1.0 + 0.2*(m_night - 1.0) (i.e. 1.00x, 1.07x, 1.15x, 1.30x)!
            m_early = 1.0 + 0.20 * (m_night - 1.0)
            for mode, unit_cost in [
                ("afternoon_1430", 1.0),
                ("empirical_wqp_clock", wqp_weights.get("predawn", 0.0) * m_night + (1.0 - wqp_weights.get("predawn", 0.0))),
                ("rotating_daytime_safe", 1.0),
                ("rotating_dawn_included", (1.0 / 3.0) * m_night + (2.0 / 3.0)),
                ("alternating_50_50", 0.5 * m_night + 0.5),
                ("first_light_sr_p30", m_early),
                ("predawn_sr_m30", m_night),
            ]:
                v_ann_eff = v_ann / unit_cost
                sim = run_mc_grab_schedule(0.5 * v_ann_eff, mode)
                dn = sim["mean_actionable_nights_detected"]
                de = sim["mean_distinct_episodes_detected"]
                sim["unit_visit_cost_dayeq"] = float(unit_cost)
                sim["effective_annual_visits_per_site"] = float(v_ann_eff)
                sim["actionable_nights_per_100_dayeq"] = float(100.0 * dn / tot_cost_dayeq)
                sim["distinct_episodes_per_100_dayeq"] = float(100.0 * de / tot_cost_dayeq)
                sim["cost_usd_per_actionable_night"] = float(DAYTIME_VISIT_USD_BENCHMARK * tot_cost_dayeq / dn) if dn > 0 else None
                sim["cost_usd_per_distinct_episode"] = float(DAYTIME_VISIT_USD_BENCHMARK * tot_cost_dayeq / de) if de > 0 else None
                m_rec[mode] = sim
            eb_block["grab_by_night_multiplier"][m_key] = m_rec

        for k_sonde in SONDE_ANNUAL_VISIT_EQS:
            k_key = f"k_{k_sonde}"
            k_rec = {}
            for rname in ("y1_daytime_screening", "loor_covariate_score", "oracle_full_panel"):
                ranked_sites = rankings[rname].reindex(sites_eval).fillna(-1e9).sort_values(ascending=False).index.tolist()
                for frac in (0.10, 0.20):
                    for bg_mode, bg_tag in (("empirical_wqp_clock", "wqp"), ("first_light_sr_p30", "firstlight")):
                        if bg_tag == "firstlight" and rname != "y1_daytime_screening":
                            continue
                        tag = f"{rname}_top{int(frac*100)}pct" + ("" if bg_tag == "wqp" else "_plus_firstlight")
                        n_top = max(1, round(frac * n_sites_eval))
                        actual_frac = n_top / n_sites_eval
                        rem_budget_per_site = v_ann - actual_frac * k_sonde
                        if rem_budget_per_site < -1e-6:
                            k_rec[tag] = {"feasible": False, "required_min_budget_dayeq": float(actual_frac * k_sonde)}
                            continue
                        # If background uses first_light, apply modest 1.15x early-shift factor conservatively
                        bg_unit = 1.15 if bg_tag == "firstlight" else 1.0
                        v_ann_non = max(0.0, rem_budget_per_site / max(1e-9, (1.0 - actual_frac) * bg_unit))
                        top_set = set(ranked_sites[:n_top])
                        sim = run_mc_grab_schedule(0.5 * v_ann_non, bg_mode, sonde_sites=top_set)
                        dn = sim["mean_actionable_nights_detected"]
                        de = sim["mean_distinct_episodes_detected"]
                        sim["feasible"] = True
                        sim["n_sonde_sites"] = n_top
                        sim["sonde_site_fraction"] = float(actual_frac)
                        sim["non_sonde_annual_visits_per_site"] = float(v_ann_non)
                        sim["actionable_nights_per_100_dayeq"] = float(100.0 * dn / tot_cost_dayeq)
                        sim["distinct_episodes_per_100_dayeq"] = float(100.0 * de / tot_cost_dayeq)
                        sim["cost_usd_per_actionable_night"] = float(DAYTIME_VISIT_USD_BENCHMARK * tot_cost_dayeq / dn) if dn > 0 else None
                        sim["cost_usd_per_distinct_episode"] = float(DAYTIME_VISIT_USD_BENCHMARK * tot_cost_dayeq / de) if de > 0 else None
                        k_rec[tag] = sim
            eb_block["hybrid_sonde_by_cost"][k_key] = k_rec

        equal_budget_results[v_key] = eb_block

    return {
        "n_eval_sites": n_sites_eval,
        "n_eval_site_years": n_site_years,
        "n_impaired_site_years": int(n_impaired_sy),
        "total_actionable_nights_in_eval": int(total_act_nights_panel),
        "total_distinct_episodes_in_eval": int(total_distinct_eps_panel),
        "sonde_targeting_capture": targeting_audit,
        "fixed_visit_calendars": fixed_visit_results,
        "equal_dollar_budget": equal_budget_results,
    }


def compute_breakeven_frontiers(visit_block: dict) -> dict:
    p = visit_block["protocols"]
    r_af = p["afternoon_1430"]["actionable_detections_per_100_visits"]
    r_wqp = p["empirical_wqp_clock"]["actionable_detections_per_100_visits"]
    r_daysafe = p["rotating_daytime_safe"]["actionable_detections_per_100_visits"]
    r_rot = p["rotating_dawn_included"]["actionable_detections_per_100_visits"]
    r_alt = p["alternating_50_50"]["actionable_detections_per_100_visits"]
    r_fl = p["first_light_sr_p30"]["actionable_detections_per_100_visits"]
    r_pd = p["predawn_sr_m30"]["actionable_detections_per_100_visits"]

    def bm(r_hi: float, r_lo: float, p_n_lo: float) -> float | None:
        denom = r_lo - r_hi * p_n_lo
        if denom <= 1e-9:
            return None
        return float(r_hi * (1.0 - p_n_lo) / denom)

    return {
        "predawn_breakeven_m_vs_afternoon": bm(r_pd, r_af, 0.0),
        "predawn_breakeven_m_vs_wqp_clock": bm(r_pd, r_wqp, p["empirical_wqp_clock"]["night_shift_visit_fraction"]),
        "predawn_breakeven_m_vs_daytime_safe_rot": bm(r_pd, r_daysafe, 0.0),
        "predawn_breakeven_m_vs_dawn_included_rot": bm(r_pd, r_rot, 1.0 / 3.0),
        "predawn_breakeven_m_vs_alternating": bm(r_pd, r_alt, 0.5),
        "first_light_breakeven_m_vs_wqp_clock": bm(r_fl, r_wqp, p["empirical_wqp_clock"]["night_shift_visit_fraction"]),
        "first_light_breakeven_m_vs_afternoon": bm(r_fl, r_af, 0.0),
    }


def main() -> None:
    df_all = pd.read_parquet(PROC / "v4_nocturnal_site_nights.parquet")
    wqp_clock = build_empirical_wqp_clock_weights()
    wqp_weights = wqp_clock["bin_weights"]
    rng = np.random.default_rng(RNG_SEED)

    receipt: dict = {
        "cost_model_assumptions": {
            "daytime_visit_usd_benchmark": DAYTIME_VISIT_USD_BENCHMARK,
            "travel_share_of_daytime_visit": 0.40,
            "labor_share_of_daytime_visit": 0.60,
            "night_cost_multipliers": list(NIGHT_COST_MULTIPLIERS),
            "sonde_annual_visit_equivalents": list(SONDE_ANNUAL_VISIT_EQS),
            "annual_visit_budgets": list(ANNUAL_VISIT_BUDGETS),
            "n_monte_carlo_calendars": N_MC,
        },
        "empirical_wqp_clock_weights": wqp_clock,
        "networks": {},
    }

    for net in ("USGS", "EA"):
        df_net = df_all[df_all["network"] == net].copy()
        print(f"Running equal-budget operational protocol evaluation for {net} ({len(df_net):,} nights)...", flush=True)

        v_primary = evaluate_visit_level_protocols(df_net, wqp_weights, 5.0, "t5_actionable_2h")
        v_4mg = evaluate_visit_level_protocols(df_net, wqp_weights, 4.0, "t4_actionable_2h")
        v_5mg_4h = evaluate_visit_level_protocols(df_net, wqp_weights, 5.0, "t5_actionable_4h")
        v_3mg = evaluate_visit_level_protocols(df_net, wqp_weights, 3.0, "t3_loro_persist2")

        eb_primary = simulate_equal_budget_calendars(df_net, net, wqp_weights, 5.0, "t5_actionable_2h", rng)
        frontiers = compute_breakeven_frontiers(v_primary)

        receipt["networks"][net] = {
            "primary_actionable_5mg_2h_visit_level": v_primary,
            "sensitivity_4mg_2h_visit_level": v_4mg,
            "sensitivity_5mg_4h_visit_level": v_5mg_4h,
            "sensitivity_3mg_persist_visit_level": v_3mg,
            "equal_budget_simulation_5mg_2h": eb_primary,
            "decision_breakeven_frontiers": frontiers,
        }

        p = v_primary["protocols"]
        b24 = eb_primary["equal_dollar_budget"]["budget_24_dayeq"]
        print(f"\n=== {net} OPERATIONAL SUMMARY (Actionable >=2h <5 mg/L, LORO; total distinct eps={eb_primary['total_distinct_episodes_in_eval']:,}) ===", flush=True)
        print("  Continuous sonde (episodic <24h):", v_primary["continuous_sonde_benchmark"]["episodic_lt24h_lead"])
        for k_p in ("afternoon_1430", "empirical_wqp_clock", "rotating_daytime_safe", "rotating_dawn_included", "first_light_sr_p30", "predawn_sr_m30"):
            r = p[k_p]
            el = r["episodic_lt24h_lead"]
            print(
                f"  {k_p:22s} | act_rec={r['actionable_recall_pct']:5.1f}% (epi<24h={r['episodic_lt24h_recall_pct']:5.1f}%) | "
                f"det/100v={r['actionable_detections_per_100_visits']:5.2f} | epi_lead_end={el.get('median_lead_end_hr', 0):+5.2f}h "
                f"(epi_nadir={el.get('median_lead_nadir_hr', 0):+5.2f}h) | LORO FA={r['loro_ref_neg_alarm_pct']:.3f}%",
                flush=True,
            )
        print("  Equal-Budget (24 day-eq/site-yr, m_night=1.75x, K_sonde=40) — DISTINCT EPISODES & IMPAIRED SITE-YEARS:", flush=True)
        for mode in ("afternoon_1430", "empirical_wqp_clock", "rotating_daytime_safe", "rotating_dawn_included", "first_light_sr_p30", "predawn_sr_m30"):
            s = b24["grab_by_night_multiplier"]["m_1p75"][mode]
            print(
                f"    Grab {mode:22s}: {s['distinct_episodes_per_100_dayeq']:5.2f} ep/100eq (${s['cost_usd_per_distinct_episode']:6.0f}/ep) | "
                f"{s['actionable_nights_per_100_dayeq']:5.2f} n/100eq | impaired SY={s['impaired_sy_flagged_pct']:5.1f}%",
                flush=True,
            )
        for tag in ("y1_daytime_screening_top10pct", "y1_daytime_screening_top20pct", "y1_daytime_screening_top20pct_plus_firstlight", "loor_covariate_score_top20pct", "oracle_full_panel_top20pct"):
            s = b24["hybrid_sonde_by_cost"]["k_40"][tag]
            if s.get("feasible"):
                print(
                    f"    Sonde {tag:44s}: {s['distinct_episodes_per_100_dayeq']:5.2f} ep/100eq (${s['cost_usd_per_distinct_episode']:6.0f}/ep) | "
                    f"{s['actionable_nights_per_100_dayeq']:5.2f} n/100eq | impaired SY={s['impaired_sy_flagged_pct']:5.1f}%",
                    flush=True,
                )

    out_p = RES / "12_operational_protocol_decision.json"
    out_p.write_text(json.dumps(receipt, indent=2, allow_nan=True) + "\n", encoding="utf-8")
    print(f"\n[DONE] Saved operational decision receipt -> {out_p}", flush=True)


if __name__ == "__main__":
    main()
