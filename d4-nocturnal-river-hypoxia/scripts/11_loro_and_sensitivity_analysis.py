"""Step 11: Primary Leave-One-Reading-Out (LORO) nocturnal detection analysis, sensor-tolerance
and persistence sensitivity, out-of-sample site/region holdout validation, coverage/attrition
audit, native cadence downsampling (15/30/60-min), chronically-hypoxic site sensitivity,
and left/right-censoring + Kaplan-Meier duration analysis across US (USGS) and England (EA).
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PROC = DATA / "processed"
RES = ROOT / "results"
TBL = ROOT / "tables"

EPOCH = pd.Timestamp("1970-01-01", tz="UTC")
THRESHOLDS = (5.0, 4.0, 3.0, 2.0)

# Relative-to-sunrise offsets (minutes) for out-of-sample optimal timing search
SR_OFFSETS_MIN = (-180, -120, -90, -60, -30, 0, 30, 60, 120)
# Fixed local mean solar hours (minutes from midnight)
FIXED_SOLAR_MIN = {
    "midnight": 0.0,
    "dawn05": 300.0,
    "morning07": 420.0,
    "morning08": 480.0,
    "overpass": 630.0,    # 10:30 LMST
    "midday12": 720.0,    # 12:00 LMST
    "afternoon": 870.0,   # 14:30 LMST
    "latepm16": 960.0,    # 16:00 LMST
    "evening20": 1200.0,  # 20:00 LMST
}


def solar_boundaries(lat: float, date: pd.Timestamp) -> tuple[float, float]:
    """Geometric sun-center sunrise and sunset in minutes of local mean solar time (Iqbal 1983)."""
    g = 2.0 * np.pi * (date.day_of_year - 1) / (366 if date.is_leap_year else 365)
    dec = (
        0.006918
        - 0.399912 * np.cos(g)
        + 0.070257 * np.sin(g)
        - 0.006758 * np.cos(2 * g)
        + 0.000907 * np.sin(2 * g)
        - 0.002697 * np.cos(3 * g)
        + 0.001480 * np.sin(3 * g)
    )
    eq_time = 229.18 * (
        0.000075
        + 0.001868 * np.cos(g)
        - 0.032077 * np.sin(g)
        - 0.014615 * np.cos(2 * g)
        - 0.040849 * np.sin(2 * g)
    )
    arc_min = 4.0 * np.rad2deg(np.arccos(np.clip(-np.tan(np.deg2rad(lat)) * np.tan(dec), -1.0, 1.0)))
    return float(720.0 - eq_time - arc_min), float(720.0 - eq_time + arc_min)


def read_candidates(network: str) -> pd.DataFrame:
    if network == "USGS":
        frame = pd.read_csv(PROC / "conus_iv_rivers_meta.csv", dtype={"site_no": str, "huc2": str})
        return frame.rename(columns={"site_no": "site", "huc2": "cluster"})
    frame = pd.read_csv(PROC / "uk_ea_clean_rivers_results.csv", usecols=["notation", "lat", "lon"], dtype={"notation": str})
    frame = frame.rename(columns={"notation": "site"})
    frame["cluster"] = np.floor(frame["lat"]).astype(int).astype(str) + ":" + np.floor(frame["lon"]).astype(int).astype(str)
    return frame


def read_station_utc(network: str, site: str) -> tuple[pd.DatetimeIndex, np.ndarray]:
    if network == "USGS":
        raw = pd.read_parquet(DATA / "raw_usgs_stac" / f"{site}.parquet")
        ts = pd.DatetimeIndex(pd.to_datetime(raw["time"], utc=True))
    else:
        raw = pd.read_parquet(DATA / "raw_uk_ea" / f"uk_{site}.parquet", columns=["do"])
        ts = pd.DatetimeIndex(pd.to_datetime(raw.index, utc=True))
    vals = raw["do"].to_numpy(dtype=float)
    valid = np.isfinite(vals)
    if not ts.is_monotonic_increasing or ts.has_duplicates:
        raise ValueError(f"Unsorted or duplicate timestamps: {network} {site}")
    return ts[valid], vals[valid]


def nearest_index_within(solar: np.ndarray, target: float, tol: float) -> int | None:
    ix = int(np.searchsorted(solar, target))
    best_i = None
    best_d = tol + 1.0
    for cand in (ix - 1, ix):
        if 0 <= cand < len(solar):
            d = abs(solar[cand] - target)
            if d < best_d:
                best_d = d
                best_i = cand
    if best_i is not None and best_d <= tol + 1e-6:
        return best_i
    return None


def max_consecutive_run_length(mask: np.ndarray) -> int:
    if not mask.any():
        return 0
    edges = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    return int(np.max(edges[1::2] - edges[::2]))


def max_continuous_low_minutes(times: np.ndarray, mask: np.ndarray, max_gap: float) -> float:
    """Longest continuous duration (minutes) of True entries in mask without gaps > max_gap."""
    if not mask.any():
        return 0.0
    edges = np.flatnonzero(np.diff(np.r_[False, mask, False]))
    starts, ends = edges[::2], edges[1::2]
    best = 0.0
    for s, e in zip(starts, ends, strict=True):
        seg_t = times[s:e]
        if len(seg_t) == 1:
            span = 0.0
        else:
            # Break on any internal gap > max_gap
            breaks = np.flatnonzero(np.diff(seg_t) > max_gap + 1e-6)
            sub_s = np.r_[0, breaks + 1]
            sub_e = np.r_[breaks + 1, len(seg_t)]
            span = float(np.max(seg_t[sub_e - 1] - seg_t[sub_s]))
        best = max(best, span)
    return best


def analyze_night_episode(
    solar: np.ndarray,
    values: np.ndarray,
    begin: int,
    end: int,
    night_end: float,
    threshold: float,
    step: int,
    max_gap: float,
    predawn_idx: int,
) -> dict:
    """Analyze nocturnal run censoring inside darkness AND trace full unbroken episode across sunrise/sunset."""
    n_times = solar[begin:end]
    n_vals = values[begin:end]
    low = n_vals < threshold
    res: dict = {
        "censor_status": "none",
        "night_dur_lo_hr": np.nan,
        "night_dur_hi_hr": np.nan,
        "night_km_obs_hr": np.nan,
        "night_km_event": 0,
        "onset_lo_hr_before_sr": np.nan,
        "onset_hi_hr_before_sr": np.nan,
        "full_dur_hr": np.nan,
        "full_closed": False,
        "ep_start_rel_sr_hr": np.nan,
        "ep_nadir_rel_sr_hr": np.nan,
        "ep_end_rel_sr_hr": np.nan,
        "loro_ref": False,
        "loro_pm30m_ref": False,
        "loro_persist2": False,
        "loro_persist30m": False,
        "actionable_2h": False,
        "actionable_4h": False,
    }

    # LORO checks (excluding candidate predawn reading; and excluding +/-30 min window)
    local_pd = predawn_idx - begin
    other_mask = np.ones(len(n_vals), dtype=bool)
    if 0 <= local_pd < len(n_vals):
        other_mask[local_pd] = False
    other_vals = n_vals[other_mask]
    other_low = other_vals < threshold

    res["loro_ref"] = bool(other_low.any())
    far_mask = np.abs(n_times - solar[predawn_idx]) > 30.0 + 1e-6
    res["loro_pm30m_ref"] = bool((n_vals[far_mask] < threshold).any()) if far_mask.any() else False

    # Persistence excluding predawn reading: require >=2 consecutive low readings AND/OR >=30 min continuous
    if res["loro_ref"]:
        # Evaluate consecutive runs on night array with predawn reading treated as masked/removed
        # Note: removing single point splits a continuous run if it sits inside; evaluate on full night
        # requiring >=2 low readings OTHER than predawn in the same contiguous run (bridging predawn slot only if both neighbors are low)
        # Strictest definition: max consecutive run in other_vals (with gaps <= 2.5*step across the single dropped slot)
        # Actually, strictly check runs in n_vals where count of OTHER low readings >= 2!
        edges_all = np.flatnonzero(np.diff(np.r_[False, low, False]))
        max_other_in_run = 0
        max_other_span_min = 0.0
        for s_i, e_i in zip(edges_all[::2], edges_all[1::2], strict=True):
            idx_range = np.arange(s_i, e_i)
            other_in_run = idx_range[idx_range != local_pd]
            max_other_in_run = max(max_other_in_run, len(other_in_run))
            if len(other_in_run) >= 2:
                span_m = float(n_times[other_in_run[-1]] - n_times[other_in_run[0]])
                max_other_span_min = max(max_other_span_min, span_m)
        res["loro_persist2"] = bool(max_other_in_run >= 2)
        res["loro_persist30m"] = bool(max_other_span_min >= 30.0 - 1e-6 or (step >= 30 and max_other_in_run >= 2))

    if not low.any():
        return res

    # Longest low run inside astronomical night
    edges = np.flatnonzero(np.diff(np.r_[False, low, False]))
    starts, ends = edges[::2], edges[1::2]
    spans = n_times[ends - 1] - n_times[starts]
    longest = int(np.argmax(spans))
    s_l, e_l = int(starts[longest]), int(ends[longest])

    left_cens = s_l == 0
    right_cens = e_l == len(n_vals)
    if left_cens and right_cens:
        res["censor_status"] = "doubly_censored"
    elif left_cens:
        res["censor_status"] = "left_only"
    elif right_cens:
        res["censor_status"] = "right_only"
    else:
        res["censor_status"] = "both_closed"

    # Observed span inside night (midpoint / conservative bounds)
    if not left_cens and not right_cens:
        res["night_dur_lo_hr"] = float(spans[longest] / 60.0)
        res["night_dur_hi_hr"] = float((n_times[e_l] - n_times[s_l - 1]) / 60.0)
        # For KM survival among episodes with observed nocturnal onset:
        res["night_km_obs_hr"] = float((spans[longest] + step) / 60.0)
        res["night_km_event"] = 1
    elif not left_cens and right_cens:
        # Observed onset inside darkness, right-censored at sunrise!
        res["night_km_obs_hr"] = float((night_end - n_times[s_l] + 0.5 * step) / 60.0)
        res["night_km_event"] = 0

    # First crossing onset inside darkness
    first_low = int(starts[0])
    if first_low > 0:
        res["onset_lo_hr_before_sr"] = float((night_end - n_times[first_low]) / 60.0)
        res["onset_hi_hr_before_sr"] = float((night_end - n_times[first_low - 1]) / 60.0)

    # Trace FULL unbroken episode across sunset/sunrise in the complete continuous UTC series!
    # Pick the longest run inside night (global indices) and expand left & right while values < threshold and gap <= max_gap
    g_s = begin + s_l
    g_e = begin + e_l - 1  # inclusive index
    hit_left_gap = False
    while g_s > 0:
        if solar[g_s] - solar[g_s - 1] > max_gap + 1e-6:
            hit_left_gap = True
            break
        if values[g_s - 1] < threshold:
            g_s -= 1
        else:
            break
    if g_s == 0:
        hit_left_gap = True

    hit_right_gap = False
    while g_e + 1 < len(values):
        if solar[g_e + 1] - solar[g_e] > max_gap + 1e-6:
            hit_right_gap = True
            break
        if values[g_e + 1] < threshold:
            g_e += 1
        else:
            break
    if g_e == len(values) - 1:
        hit_right_gap = True

    full_span_min = float(solar[g_e] - solar[g_s])
    # Add one sampling step midpoint correction (half step on each closed boundary) for duration estimate
    est_full_min = full_span_min + (0.5 * step if not hit_left_gap else 0.0) + (0.5 * step if not hit_right_gap else 0.0)
    res["full_dur_hr"] = float(est_full_min / 60.0)
    res["full_closed"] = bool(not hit_left_gap and not hit_right_gap)

    # Episode start, nadir, and recovery times relative to geometric sunrise (hours; negative = before sunrise, positive = after sunrise)
    ep_vals = values[g_s : g_e + 1]
    ep_times = solar[g_s : g_e + 1]
    nadir_local = int(np.argmin(ep_vals))
    res["ep_start_rel_sr_hr"] = float((ep_times[0] - night_end) / 60.0)
    res["ep_nadir_rel_sr_hr"] = float((ep_times[nadir_local] - night_end) / 60.0)
    end_time_min = solar[g_e + 1] if (not hit_right_gap and g_e + 1 < len(solar)) else ep_times[-1]
    res["ep_end_rel_sr_hr"] = float((end_time_min - night_end) / 60.0)

    # Actionable persistent episode (strictly LORO: verified even after excluding predawn reading!)
    ep_other_cnt = int(np.sum(np.arange(g_s, g_e + 1) != predawn_idx))
    res["actionable_2h"] = bool(res["loro_ref"] and ep_other_cnt >= 2 and est_full_min >= 120.0 - 1e-6)
    res["actionable_4h"] = bool(res["loro_ref"] and ep_other_cnt >= 2 and est_full_min >= 240.0 - 1e-6)
    return res


def evaluate_station_full(
    network: str,
    site: str,
    cluster: str,
    lat: float,
    lon: float,
    solar_override: np.ndarray | None = None,
    values_override: np.ndarray | None = None,
    forced_step: int | None = None,
    detailed_episodes: bool = True,
) -> tuple[list[dict], dict, list[dict]]:
    if solar_override is None or values_override is None:
        ts, values = read_station_utc(network, site)
        solar = (ts - EPOCH).total_seconds().to_numpy() / 60.0 + 4.0 * lon
    else:
        solar = solar_override
        values = values_override

    diffs = np.diff(solar)
    small = np.rint(diffs[(diffs >= 1) & (diffs <= 65)]).astype(int)
    audit = {
        "network": network,
        "site": site,
        "cluster": str(cluster),
        "raw_points": len(solar),
        "native_step_min": None,
        "candidate_nights": 0,
        "complete_nights": 0,
        "matched_nights": 0,
        "fail_night_gap": 0,
        "fail_target_match": 0,
        "fail_predawn_outside": 0,
        "excl_partial_obs_nights": 0,
        "excl_partial_lt5_nights": 0,
    }
    if forced_step is None:
        if len(small) < 100:
            return [], audit, []
        step = int(np.bincount(small).argmax())
    else:
        step = int(forced_step)
    audit["native_step_min"] = step
    max_gap = 1.5 * step

    unique_days = np.unique(np.floor(solar / 1440.0).astype(int))
    solar_dates = pd.to_datetime(unique_days, unit="D", origin="unix")
    phases = [solar_boundaries(lat, d) for d in solar_dates]
    geometry = dict(zip(unique_days, phases, strict=True))

    output: list[dict] = []
    attrition_rows: list[dict] = []

    for day, date in zip(unique_days, solar_dates, strict=True):
        if not 5 <= date.month <= 10 or day - 1 not in geometry:
            continue
        rise = geometry[day][0]
        night_start = (day - 1) * 1440.0 + geometry[day - 1][1]
        night_end = day * 1440.0 + rise
        begin, end = np.searchsorted(solar, [night_start, night_end])
        audit["candidate_nights"] += 1

        # Check completeness
        night_complete = not (
            end - begin < 2
            or solar[begin] - night_start > max_gap
            or night_end - solar[end - 1] > max_gap
            or np.any(np.diff(solar[begin:end]) > max_gap + 1e-6)
        )
        if not night_complete:
            audit["fail_night_gap"] += 1
            partial_lt5 = bool(end > begin and np.any(values[begin:end] < 5.0))
            if end > begin:
                audit["excl_partial_obs_nights"] += 1
                if partial_lt5:
                    audit["excl_partial_lt5_nights"] += 1
            attrition_rows.append(
                {
                    "network": network,
                    "site": site,
                    "month": int(date.month),
                    "native_step_min": step,
                    "status": "fail_night_gap",
                    "has_partial_obs": bool(end > begin),
                    "partial_lt5": partial_lt5,
                }
            )
            continue

        audit["complete_nights"] += 1

        # Exact common-support matching (identical to v3 for exact parity!)
        targets = day * 1440.0 + np.array([870.0, 630.0, rise - 30.0])
        ix = np.searchsorted(solar, targets).clip(1, len(solar) - 1)
        prev_d = np.abs(targets - solar[ix - 1])
        next_d = np.abs(solar[ix] - targets)
        if np.any(np.minimum(prev_d, next_d) > 0.55 * step + 1e-6):
            audit["fail_target_match"] += 1
            partial_lt5 = bool(np.any(values[begin:end] < 5.0))
            audit["excl_partial_obs_nights"] += 1
            if partial_lt5:
                audit["excl_partial_lt5_nights"] += 1
            attrition_rows.append(
                {
                    "network": network,
                    "site": site,
                    "month": int(date.month),
                    "native_step_min": step,
                    "status": "fail_target_match",
                    "has_partial_obs": True,
                    "partial_lt5": partial_lt5,
                }
            )
            continue

        closest = ix - (prev_d <= next_d)
        predawn_idx = int(closest[2])
        if not (night_start <= solar[predawn_idx] < night_end):
            audit["fail_predawn_outside"] += 1
            attrition_rows.append(
                {
                    "network": network,
                    "site": site,
                    "month": int(date.month),
                    "native_step_min": step,
                    "status": "fail_predawn_outside",
                    "has_partial_obs": True,
                    "partial_lt5": bool(np.any(values[begin:end] < 5.0)),
                }
            )
            continue

        audit["matched_nights"] += 1
        attrition_rows.append(
            {
                "network": network,
                "site": site,
                "month": int(date.month),
                "native_step_min": step,
                "status": "matched",
                "has_partial_obs": True,
                "partial_lt5": bool(np.any(values[begin:end] < 5.0)),
            }
        )

        afternoon, overpass, predawn = (float(v) for v in values[closest])
        night_vals = values[begin:end]
        night_times = solar[begin:end]

        # Exact LORO night minimum (dropping ONLY predawn_idx)
        local_pd = predawn_idx - begin
        other_vals = np.delete(night_vals, local_pd)
        night_min_loro = float(other_vals.min())
        far_mask = np.abs(night_times - solar[predawn_idx]) > 30.0 + 1e-6
        night_min_loro_pm30m = float(night_vals[far_mask].min()) if far_mask.any() else np.nan

        rec: dict = {
            "network": network,
            "site": site,
            "cluster": str(cluster),
            "date": date.date().isoformat(),
            "year": int(date.year),
            "month": int(date.month),
            "day_index": int(day),
            "native_step_min": step,
            "lat": float(lat),
            "lon": float(lon),
            "sunrise_min": float(rise),
            "night_len_hr": float((night_end - night_start) / 60.0),
            "night_n_obs": int(end - begin),
            "night_min_shared": float(night_vals.min()),
            "night_min_loro": night_min_loro,
            "night_min_loro_pm30m": night_min_loro_pm30m,
            "afternoon": afternoon,
            "overpass": overpass,
            "predawn": predawn,
            "alternating": predawn if day % 2 == 0 else afternoon,
            "predawn_rel_sr_hr": float((solar[predawn_idx] - night_end) / 60.0),
            "overpass_rel_sr_hr": float((solar[int(closest[1])] - night_end) / 60.0),
            "afternoon_rel_sr_hr": float((solar[int(closest[0])] - night_end) / 60.0),
        }

        if detailed_episodes:
            # Extract additional candidate solar offsets & fixed clock hours for holdout optimization + operational protocols
            tol_extra = 0.55 * step
            for off in SR_OFFSETS_MIN:
                t_off = night_end + off
                ci = nearest_index_within(solar, t_off, tol_extra)
                col_val = f"sr_{'m' if off < 0 else 'p'}{abs(off)}"
                rec[col_val] = float(values[ci]) if ci is not None else np.nan
                # LORO night min specifically excluding THIS offset reading (if it fell inside darkness)
                if ci is not None and begin <= ci < end:
                    o_v = np.delete(night_vals, ci - begin)
                    rec[f"loro_min_{col_val}"] = float(o_v.min()) if len(o_v) else np.nan
                else:
                    rec[f"loro_min_{col_val}"] = float(night_vals.min())

            for f_name, f_min in FIXED_SOLAR_MIN.items():
                if f_name in ("afternoon", "overpass"):
                    continue
                # Evening hours (20:00) belong to previous solar evening (day - 1) before midnight,
                # midnight (00:00) and morning/daytime hours belong to sunrise date `day`
                t_f = ((day - 1) if f_min >= 1080.0 else day) * 1440.0 + f_min
                ci = nearest_index_within(solar, t_f, tol_extra)
                rec[f_name] = float(values[ci]) if ci is not None else np.nan
                rec[f"{f_name}_rel_sr_hr"] = float((solar[ci] - night_end) / 60.0) if ci is not None else np.nan
                if ci is not None and begin <= ci < end:
                    o_v = np.delete(night_vals, ci - begin)
                    rec[f"loro_min_{f_name}"] = float(o_v.min()) if len(o_v) else np.nan
                else:
                    rec[f"loro_min_{f_name}"] = float(night_vals.min())

            # Episode, censoring, persistence, and actionable event analysis across all 4 thresholds
            for thr in THRESHOLDS:
                k = int(thr)
                ep = analyze_night_episode(solar, values, begin, end, night_end, thr, step, max_gap, predawn_idx)
                for ek, ev in ep.items():
                    rec[f"t{k}_{ek}"] = ev

        output.append(rec)

    return output, audit, attrition_rows


def clustered_rate(values: np.ndarray | pd.Series, group: pd.Series) -> list[float]:
    arr = np.asarray(values, dtype=float)
    valid = np.isfinite(arr)
    arr = arr[valid]
    grp = group.iloc[np.flatnonzero(valid)]
    centre = float(np.mean(arr))
    cluster_totals = pd.Series(arr - centre).groupby(grp.to_numpy()).sum()
    g = len(cluster_totals)
    if g < 2:
        return [100.0 * centre, np.nan, np.nan]
    se = float(np.sqrt(g / (g - 1) * np.square(cluster_totals).sum()) / len(arr))
    radius = float(stats.t.ppf(0.975, g - 1) * se)
    return [100.0 * centre, 100.0 * (centre - radius), 100.0 * (centre + radius)]


def kaplan_meier_quantiles(durations: np.ndarray, events: np.ndarray) -> dict:
    """Exact Kaplan-Meier right-censored survival curve median, Q25, Q75, and restricted mean."""
    mask = np.isfinite(durations) & (durations >= 0)
    d = durations[mask]
    e = events[mask].astype(int)
    n_total = len(d)
    n_events = int(e.sum())
    n_censored = n_total - n_events
    if n_total == 0:
        return {"n_total": 0, "n_events": 0, "n_censored": 0, "median_hr": None, "q25_hr": None, "q75_hr": None, "rmst_12h_hr": None}

    uniq_t = np.sort(np.unique(d))
    surv = 1.0
    times_s = [0.0]
    surv_s = [1.0]
    for t in uniq_t:
        at_risk = int(np.sum(d >= t))
        died = int(np.sum((d == t) & (e == 1)))
        if died > 0 and at_risk > 0:
            surv *= 1.0 - died / at_risk
            times_s.append(float(t))
            surv_s.append(float(surv))

    times_arr = np.array(times_s)
    surv_arr = np.array(surv_s)

    def quantile(p_surv: float) -> float | None:
        idx = np.flatnonzero(surv_arr <= p_surv)
        return float(times_arr[idx[0]]) if len(idx) else None

    # Restricted mean survival time up to tau = 12 h (typical max warm-season night)
    tau = 12.0
    rmst = 0.0
    prev_t = 0.0
    prev_s = 1.0
    for t_cur, s_cur in zip(times_arr[1:], surv_arr[1:], strict=True):
        if t_cur >= tau:
            rmst += (tau - prev_t) * prev_s
            prev_t = tau
            break
        rmst += (t_cur - prev_t) * prev_s
        prev_t = t_cur
        prev_s = s_cur
    if prev_t < tau:
        rmst += (tau - prev_t) * prev_s

    return {
        "n_total": n_total,
        "n_events": n_events,
        "n_censored": n_censored,
        "censored_pct": 100.0 * n_censored / n_total,
        "q25_hr": quantile(0.75),
        "median_hr": quantile(0.50),
        "q75_hr": quantile(0.25),
        "surv_at_6h_pct": float(100.0 * surv_arr[np.searchsorted(times_arr, 6.0, side="right") - 1]),
        "rmst_12h_hr": float(rmst),
    }


def summarize_loro_primary(df: pd.DataFrame) -> dict:
    """Compute primary LORO, shared-reference benchmark, +/-30m LORO, persistence, tolerance,
    probe-noise Monte Carlo, equal-site, and chronic-site-exclusion tables across US and England.
    """
    out: dict = {}
    rng = np.random.default_rng(20261128)

    for net, g in df.groupby("network"):
        net_rec: dict = {
            "n_sites": int(g["site"].nunique()),
            "n_nights": len(g),
            "n_clusters": int(g["cluster"].nunique()),
            "date_range": [str(g["date"].min()), str(g["date"].max())],
            "thresholds": {},
        }
        for thr in THRESHOLDS:
            k = int(thr)
            # 1. Shared-reference benchmark (for transparent comparison to v3)
            sh_pos = g["night_min_shared"] < thr
            sh_hyp = g.loc[sh_pos]
            sh_gain = clustered_rate(
                (sh_hyp["predawn"] < thr).astype(int) - (sh_hyp["afternoon"] < thr).astype(int),
                sh_hyp["cluster"],
            )

            # 2. PRIMARY: Leave-One-Reading-Out (LORO) excluding predawn reading
            loro_pos = g["night_min_loro"] < thr
            loro_hyp = g.loc[loro_pos]
            loro_non = g.loc[~loro_pos]

            schedules_map = {
                "afternoon": ("afternoon", False),
                "overpass": ("overpass", False),
                "morning08": ("morning08", False),
                "predawn": ("predawn", True),
                "early_dawn": ("sr_m60", True),
                "alternating": ("alternating", True),
            }
            sched_stats = {}
            for s_name, (col, _) in schedules_map.items():
                valid_hyp = loro_hyp.dropna(subset=[col])
                valid_non = loro_non.dropna(subset=[col])
                # For early_dawn, use its own LORO reference if available
                if s_name == "early_dawn":
                    l_pos_ed = g["loro_min_sr_m60"] < thr
                    valid_hyp = g.loc[l_pos_ed].dropna(subset=[col])
                    valid_non = g.loc[~l_pos_ed].dropna(subset=[col])
                det = (valid_hyp[col] < thr).astype(int)
                fa = (valid_non[col] < thr).astype(int)
                sched_stats[s_name] = {
                    "n_ref_pos": len(valid_hyp),
                    "n_ref_neg": len(valid_non),
                    "detected": int(det.sum()),
                    "ref_neg_alarms": int(fa.sum()),
                    "recall_95_pct": clustered_rate(det, valid_hyp["cluster"]),
                    "ref_neg_alarm_95_pct": clustered_rate(fa, valid_non["cluster"]),
                }

            loro_gain = clustered_rate(
                (loro_hyp["predawn"] < thr).astype(int) - (loro_hyp["afternoon"] < thr).astype(int),
                loro_hyp["cluster"],
            )
            loro_gain_overpass = clustered_rate(
                (loro_hyp["predawn"] < thr).astype(int) - (loro_hyp["overpass"] < thr).astype(int),
                loro_hyp["cluster"],
            )

            # 3. Stricter LORO (+/-30 min buffer around predawn excluded)
            pm30_pos = g["night_min_loro_pm30m"] < thr
            pm30_hyp = g.loc[pm30_pos]
            pm30_non = g.loc[~pm30_pos & g["night_min_loro_pm30m"].notna()]
            pm30_gain = clustered_rate(
                (pm30_hyp["predawn"] < thr).astype(int) - (pm30_hyp["afternoon"] < thr).astype(int),
                pm30_hyp["cluster"],
            )
            pm30_pd_rec = clustered_rate((pm30_hyp["predawn"] < thr).astype(int), pm30_hyp["cluster"])
            pm30_pd_fa = clustered_rate((pm30_non["predawn"] < thr).astype(int), pm30_non["cluster"])

            # 4. Persistence sensitivity (>=2 consecutive other readings, >=30 min, and >=2h actionable)
            persist_blocks = {}
            for p_key, col_flag in [
                ("persist_ge2_readings", f"t{k}_loro_persist2"),
                ("persist_ge30min", f"t{k}_loro_persist30m"),
                ("actionable_ge2h", f"t{k}_actionable_2h"),
                ("actionable_ge4h", f"t{k}_actionable_4h"),
            ]:
                p_pos = g[col_flag].astype(bool)
                p_hyp = g.loc[p_pos]
                p_non = g.loc[~p_pos]
                if len(p_hyp) > 0:
                    persist_blocks[p_key] = {
                        "n_ref_pos": len(p_hyp),
                        "predawn_recall_95_pct": clustered_rate((p_hyp["predawn"] < thr).astype(int), p_hyp["cluster"]),
                        "afternoon_recall_95_pct": clustered_rate((p_hyp["afternoon"] < thr).astype(int), p_hyp["cluster"]),
                        "overpass_recall_95_pct": clustered_rate((p_hyp["overpass"] < thr).astype(int), p_hyp["cluster"]),
                        "dawn_minus_afternoon_95_pp": clustered_rate(
                            (p_hyp["predawn"] < thr).astype(int) - (p_hyp["afternoon"] < thr).astype(int),
                            p_hyp["cluster"],
                        ),
                        "predawn_ref_neg_alarm_pct": float(100.0 * (p_non["predawn"] < thr).mean()),
                        "afternoon_ref_neg_alarm_pct": float(100.0 * (p_non["afternoon"] < thr).mean()),
                    }

            # 5. Sensor tolerance sensitivity (+/-0.1 and +/-0.2 mg/L deterministic buffers + independent MC probe noise)
            tol_blocks = {}
            for delta in (-0.2, -0.1, 0.1, 0.2):
                ref_thr = thr + delta
                t_pos = g["night_min_loro"] < ref_thr
                t_hyp = g.loc[t_pos]
                t_non = g.loc[~t_pos]
                tag = f"ref_thr_{ref_thr:.1f}".replace(".", "p")
                if len(t_hyp) > 0:
                    tol_blocks[tag] = {
                        "candidate_thr": thr,
                        "reference_thr": ref_thr,
                        "n_ref_pos": len(t_hyp),
                        "predawn_recall_95_pct": clustered_rate((t_hyp["predawn"] < thr).astype(int), t_hyp["cluster"]),
                        "afternoon_recall_95_pct": clustered_rate((t_hyp["afternoon"] < thr).astype(int), t_hyp["cluster"]),
                        "dawn_minus_afternoon_95_pp": clustered_rate(
                            (t_hyp["predawn"] < thr).astype(int) - (t_hyp["afternoon"] < thr).astype(int),
                            t_hyp["cluster"],
                        ),
                        "predawn_ref_neg_alarm_pct": float(100.0 * (t_non["predawn"] < thr).mean()),
                    }

            # Independent Monte Carlo probe noise (simulating independent co-located sensor with sigma=0.1, 0.2 mg/L)
            mc_noise = {}
            for sigma in (0.10, 0.20):
                b_reps = 200
                gains_b = np.empty(b_reps)
                pd_rec_b = np.empty(b_reps)
                af_rec_b = np.empty(b_reps)
                pd_fa_b = np.empty(b_reps)
                n_arr = len(g)
                ref_base = g["night_min_loro"].to_numpy()
                pd_base = g["predawn"].to_numpy()
                af_base = g["afternoon"].to_numpy()
                for b in range(b_reps):
                    ref_noisy = ref_base + rng.normal(0.0, sigma, n_arr)
                    pd_noisy = pd_base + rng.normal(0.0, sigma, n_arr)
                    af_noisy = af_base + rng.normal(0.0, sigma, n_arr)
                    pos_b = ref_noisy < thr
                    if pos_b.sum() > 0:
                        pd_r = float(np.mean(pd_noisy[pos_b] < thr))
                        af_r = float(np.mean(af_noisy[pos_b] < thr))
                        pd_rec_b[b] = 100.0 * pd_r
                        af_rec_b[b] = 100.0 * af_r
                        gains_b[b] = 100.0 * (pd_r - af_r)
                        pd_fa_b[b] = 100.0 * float(np.mean(pd_noisy[~pos_b] < thr))
                mc_noise[f"sigma_{sigma:.2f}".replace(".", "p")] = {
                    "sigma_mgL": sigma,
                    "n_reps": b_reps,
                    "predawn_recall_mean_pct": float(np.mean(pd_rec_b)),
                    "afternoon_recall_mean_pct": float(np.mean(af_rec_b)),
                    "dawn_minus_afternoon_mean_pp": float(np.mean(gains_b)),
                    "dawn_minus_afternoon_p025_p975_pp": [float(np.percentile(gains_b, 2.5)), float(np.percentile(gains_b, 97.5))],
                    "predawn_ref_neg_alarm_mean_pct": float(np.mean(pd_fa_b)),
                }

            # 6. Equal-site weighting & Chronically-hypoxic site exclusion
            site_rates = (
                g.assign(loro_pos=loro_pos.astype(int), af_pos=(g["afternoon"] < thr).astype(int))
                .groupby(["cluster", "site"], as_index=False)
                .agg(
                    n_nights=("loro_pos", "size"),
                    n_hyp=("loro_pos", "sum"),
                    hyp_frac=("loro_pos", "mean"),
                    af_frac=("af_pos", "mean"),
                )
            )
            by_site_gain = (
                loro_hyp.assign(
                    pd_det=(loro_hyp["predawn"] < thr).astype(int),
                    af_det=(loro_hyp["afternoon"] < thr).astype(int),
                    contrast=(loro_hyp["predawn"] < thr).astype(int) - (loro_hyp["afternoon"] < thr).astype(int),
                )
                .groupby(["cluster", "site"], as_index=False)
                .agg(n_hyp=("contrast", "size"), pd_rec=("pd_det", "mean"), af_rec=("af_det", "mean"), gain=("contrast", "mean"))
                .merge(site_rates[["site", "n_nights", "hyp_frac", "af_frac"]], on="site", how="left")
            )
            eq_all = by_site_gain
            eq_ge5 = by_site_gain[by_site_gain["n_hyp"] >= 5]

            chronic_sens = {}
            for label_c, keep_mask in [
                ("excl_chronic_gt50pct_nights", site_rates["hyp_frac"] <= 0.50),
                ("excl_chronic_gt30pct_nights", site_rates["hyp_frac"] <= 0.30),
                ("excl_chronic_gt20pct_nights", site_rates["hyp_frac"] <= 0.20),
                ("excl_daytime_chronic_gt25pct_af", site_rates["af_frac"] <= 0.25),
            ]:
                kept_sites = set(site_rates.loc[keep_mask, "site"])
                dropped_sites = int((~keep_mask).sum())
                sub_hyp = loro_hyp[loro_hyp["site"].isin(kept_sites)]
                sub_eq = eq_ge5[eq_ge5["site"].isin(kept_sites)]
                chronic_sens[label_c] = {
                    "n_sites_dropped": dropped_sites,
                    "n_hyp_nights_remaining": len(sub_hyp),
                    "pooled_dawn_minus_afternoon_95_pp": clustered_rate(
                        (sub_hyp["predawn"] < thr).astype(int) - (sub_hyp["afternoon"] < thr).astype(int),
                        sub_hyp["cluster"],
                    ) if len(sub_hyp) > 0 else [np.nan, np.nan, np.nan],
                    "equal_site_ge5_n": len(sub_eq),
                    "equal_site_ge5_gain_95_pp": clustered_rate(sub_eq["gain"], sub_eq["cluster"]) if len(sub_eq) > 1 else [np.nan, np.nan, np.nan],
                }

            # 7. Left/Right-Censoring & Kaplan-Meier + Full Continuous Episode Duration
            censor_counts = sh_hyp[f"t{k}_censor_status"].value_counts().to_dict()
            censor_counts = {str(ck): int(cv) for ck, cv in censor_counts.items()}
            km_onset = kaplan_meier_quantiles(
                sh_hyp[f"t{k}_night_km_obs_hr"].to_numpy(dtype=float),
                sh_hyp[f"t{k}_night_km_event"].to_numpy(dtype=int),
            )
            full_closed = sh_hyp.loc[sh_hyp[f"t{k}_full_closed"].astype(bool), f"t{k}_full_dur_hr"].dropna()
            full_all = sh_hyp[f"t{k}_full_dur_hr"].dropna()
            # Full-series KM (treating only rare data-gap truncated episodes as right-censored)
            km_full = kaplan_meier_quantiles(
                sh_hyp[f"t{k}_full_dur_hr"].to_numpy(dtype=float),
                sh_hyp[f"t{k}_full_closed"].astype(int).to_numpy(dtype=int),
            )

            closed_lo = sh_hyp[f"t{k}_night_dur_lo_hr"].dropna()
            closed_hi = sh_hyp[f"t{k}_night_dur_hi_hr"].dropna()
            onset_lo = sh_hyp[f"t{k}_onset_lo_hr_before_sr"].dropna()
            onset_hi = sh_hyp[f"t{k}_onset_hi_hr_before_sr"].dropna()

            net_rec["thresholds"][str(k)] = {
                "shared_n_ref_pos": int(sh_pos.sum()),
                "loro_n_ref_pos": int(loro_pos.sum()),
                "shared_minus_loro_dropped_nights": int(sh_pos.sum() - loro_pos.sum()),
                "shared_dawn_minus_afternoon_95_pp": sh_gain,
                "loro_dawn_minus_afternoon_95_pp": loro_gain,
                "loro_dawn_minus_overpass_95_pp": loro_gain_overpass,
                "loro_schedules": sched_stats,
                "loro_pm30m_exclusion": {
                    "n_ref_pos": int(pm30_pos.sum()),
                    "predawn_recall_95_pct": pm30_pd_rec,
                    "predawn_ref_neg_alarm_95_pct": pm30_pd_fa,
                    "dawn_minus_afternoon_95_pp": pm30_gain,
                },
                "persistence_sensitivity": persist_blocks,
                "tolerance_buffers": tol_blocks,
                "independent_probe_noise_mc": mc_noise,
                "equal_site_all_n": len(eq_all),
                "equal_site_all_gain_95_pp": clustered_rate(eq_all["gain"], eq_all["cluster"]) if len(eq_all) > 1 else [np.nan, np.nan, np.nan],
                "equal_site_ge5_n": len(eq_ge5),
                "equal_site_ge5_gain_95_pp": clustered_rate(eq_ge5["gain"], eq_ge5["cluster"]) if len(eq_ge5) > 1 else [np.nan, np.nan, np.nan],
                "chronic_site_sensitivity": chronic_sens,
                "censoring_and_duration": {
                    "censor_counts": censor_counts,
                    "both_closed_n": len(closed_lo),
                    "both_closed_pct": float(100.0 * len(closed_lo) / max(1, len(sh_hyp))),
                    "both_closed_median_lo_hi_hr": [float(closed_lo.median()), float(closed_hi.median())] if len(closed_lo) else [None, None],
                    "km_nocturnal_observed_onset": km_onset,
                    "full_continuous_series_km": km_full,
                    "full_continuous_closed_n": len(full_closed),
                    "full_continuous_closed_pct": float(100.0 * len(full_closed) / max(1, len(sh_hyp))),
                    "full_continuous_median_iqr_hr": [
                        float(full_all.quantile(0.25)),
                        float(full_all.median()),
                        float(full_all.quantile(0.75)),
                    ] if len(full_all) else [None, None, None],
                    "onset_valid_n": len(onset_lo),
                    "onset_median_lo_hi_hr_before_sr": [float(onset_lo.median()), float(onset_hi.median())] if len(onset_lo) else [None, None],
                },
            }
        out[net] = net_rec
    return out


def run_holdout_validation(df: pd.DataFrame) -> dict:
    """Out-of-sample site/region holdout validation + Cross-Atlantic transfer:
    Select optimal single-reading solar offset on training folds -> evaluate LORO gain on held-out folds.
    """
    candidates = [f"sr_{'m' if off < 0 else 'p'}{abs(off)}" for off in SR_OFFSETS_MIN] + [
        "morning08", "overpass", "midday12", "afternoon", "latepm16", "evening20", "midnight"
    ]
    thr = 5.0
    results: dict = {}

    def select_best_offset(train_df: pd.DataFrame) -> tuple[str, float]:
        best_c = "sr_m30"
        best_score = -1.0
        for col in candidates:
            loro_col = f"loro_min_{col}" if f"loro_min_{col}" in train_df.columns else "night_min_loro"
            sub = train_df.dropna(subset=[col, loro_col])
            pos = sub[loro_col] < thr
            if pos.sum() < 10:
                continue
            recall = float((sub.loc[pos, col] < thr).mean())
            fa = float((sub.loc[~pos, col] < thr).mean())
            youden = recall - fa  # Youden's J balances recall and LORO reference-negative alarms!
            if youden > best_score:
                best_score = youden
                best_c = col
        return best_c, best_score

    # 1. Within-network Leave-One-Cluster-Out (LOHUC2 for US, Leave-One-1deg-Grid-Out for England)
    for net in ("USGS", "EA"):
        g = df[df["network"] == net].copy()
        clusters = sorted(g["cluster"].unique())
        fold_rows = []
        oos_det_sel = []
        oos_det_af = []
        oos_cluster = []
        oos_site = []
        oos_fa_sel = []
        oos_fa_cluster = []

        for cl in clusters:
            tr = g[g["cluster"] != cl]
            te = g[g["cluster"] == cl]
            chosen, tr_j = select_best_offset(tr)
            loro_col = f"loro_min_{chosen}" if f"loro_min_{chosen}" in te.columns else "night_min_loro"
            te_v = te.dropna(subset=[chosen, loro_col, "afternoon"])
            pos = te_v[loro_col] < thr
            te_hyp = te_v.loc[pos]
            te_non = te_v.loc[~pos]
            if len(te_hyp) > 0:
                d_s = (te_hyp[chosen] < thr).astype(int).to_numpy()
                d_a = (te_hyp["afternoon"] < thr).astype(int).to_numpy()
                oos_det_sel.append(d_s)
                oos_det_af.append(d_a)
                oos_cluster.append(te_hyp["cluster"].to_numpy())
                oos_site.append(te_hyp["site"].to_numpy())
                fold_rows.append(
                    {
                        "heldout_cluster": cl,
                        "selected_offset": chosen,
                        "train_youden_j": round(tr_j, 4),
                        "n_test_hyp_nights": len(te_hyp),
                        "test_recall_pct": float(100.0 * d_s.mean()),
                        "test_afternoon_recall_pct": float(100.0 * d_a.mean()),
                        "test_gain_pp": float(100.0 * (d_s.mean() - d_a.mean())),
                        "test_ref_neg_alarm_pct": float(100.0 * (te_non[chosen] < thr).mean()) if len(te_non) else 0.0,
                    }
                )
            if len(te_non) > 0:
                oos_fa_sel.append((te_non[chosen] < thr).astype(int).to_numpy())
                oos_fa_cluster.append(te_non["cluster"].to_numpy())

        all_sel = np.concatenate(oos_det_sel)
        all_af = np.concatenate(oos_det_af)
        all_cl = pd.Series(np.concatenate(oos_cluster))
        all_st = pd.Series(np.concatenate(oos_site))
        all_fa = np.concatenate(oos_fa_sel)
        all_fa_cl = pd.Series(np.concatenate(oos_fa_cluster))

        # Equal-site held-out gain (sites with >=5 hypoxic nights)
        oos_df = pd.DataFrame({"cluster": all_cl, "site": all_st, "gain": all_sel - all_af})
        eq_oos = oos_df.groupby(["cluster", "site"], as_index=False)["gain"].agg(["mean", "size"]).query("size >= 5")

        # 5-fold random site holdout (disjoint stations, deterministic seed)
        sites = sorted(g["site"].unique())
        rng_s = np.random.default_rng(42)
        perm = rng_s.permutation(sites)
        site_folds = np.array_split(perm, 5)
        sf_sel, sf_af, sf_cl, sf_fa = [], [], [], []
        sf_chosen = []
        for te_sites in site_folds:
            te_set = set(te_sites)
            tr = g[~g["site"].isin(te_set)]
            te = g[g["site"].isin(te_set)]
            chosen, _ = select_best_offset(tr)
            sf_chosen.append(chosen)
            loro_col = f"loro_min_{chosen}" if f"loro_min_{chosen}" in te.columns else "night_min_loro"
            te_v = te.dropna(subset=[chosen, loro_col, "afternoon"])
            pos = te_v[loro_col] < thr
            te_hyp = te_v.loc[pos]
            te_non = te_v.loc[~pos]
            if len(te_hyp) > 0:
                sf_sel.append((te_hyp[chosen] < thr).astype(int).to_numpy())
                sf_af.append((te_hyp["afternoon"] < thr).astype(int).to_numpy())
                sf_cl.append(te_hyp["cluster"].to_numpy())
            if len(te_non) > 0:
                sf_fa.append((te_non[chosen] < thr).astype(int).to_numpy())

        results[net] = {
            "leave_one_region_out": {
                "n_folds_total": len(clusters),
                "n_folds_with_hypoxia": len(fold_rows),
                "selected_offset_counts": pd.Series([r["selected_offset"] for r in fold_rows]).value_counts().to_dict(),
                "n_oos_hyp_nights": len(all_sel),
                "oos_recall_95_pct": clustered_rate(all_sel, all_cl),
                "oos_afternoon_recall_95_pct": clustered_rate(all_af, all_cl),
                "oos_gain_95_pp": clustered_rate(all_sel - all_af, all_cl),
                "oos_ref_neg_alarm_95_pct": clustered_rate(all_fa, all_fa_cl),
                "oos_equal_site_ge5_n": len(eq_oos),
                "oos_equal_site_ge5_gain_95_pp": clustered_rate(eq_oos["mean"], eq_oos["cluster"]),
                "folds": fold_rows,
            },
            "five_fold_site_holdout": {
                "selected_offsets": sf_chosen,
                "n_oos_hyp_nights": int(sum(len(x) for x in sf_sel)),
                "oos_recall_95_pct": clustered_rate(np.concatenate(sf_sel), pd.Series(np.concatenate(sf_cl))),
                "oos_gain_95_pp": clustered_rate(np.concatenate(sf_sel) - np.concatenate(sf_af), pd.Series(np.concatenate(sf_cl))),
                "oos_ref_neg_alarm_pct": float(100.0 * np.concatenate(sf_fa).mean()),
            },
        }

    # 2. Cross-Atlantic Zero-Shot Transfer (Train US -> Test England; Train England -> Test US)
    xfer = {}
    for tr_net, te_net in (("USGS", "EA"), ("EA", "USGS")):
        tr = df[df["network"] == tr_net]
        te = df[df["network"] == te_net]
        chosen, tr_j = select_best_offset(tr)
        loro_col = f"loro_min_{chosen}" if f"loro_min_{chosen}" in te.columns else "night_min_loro"
        te_v = te.dropna(subset=[chosen, loro_col, "afternoon"])
        pos = te_v[loro_col] < thr
        te_hyp = te_v.loc[pos]
        te_non = te_v.loc[~pos]
        xfer[f"{tr_net}_to_{te_net}"] = {
            "selected_offset": chosen,
            "train_youden_j": round(tr_j, 4),
            "test_n_hyp": len(te_hyp),
            "test_recall_95_pct": clustered_rate((te_hyp[chosen] < thr).astype(int), te_hyp["cluster"]),
            "test_afternoon_recall_95_pct": clustered_rate((te_hyp["afternoon"] < thr).astype(int), te_hyp["cluster"]),
            "test_gain_95_pp": clustered_rate(
                (te_hyp[chosen] < thr).astype(int) - (te_hyp["afternoon"] < thr).astype(int),
                te_hyp["cluster"],
            ),
            "test_ref_neg_alarm_95_pct": clustered_rate((te_non[chosen] < thr).astype(int), te_non["cluster"]),
        }
    results["cross_atlantic_transfer"] = xfer

    # 3. Full Solar-Offset Profile (for Figure 2 timing-curve plot)
    offset_profile = {}
    for net in ("USGS", "EA"):
        g = df[df["network"] == net]
        rows = []
        for off in SR_OFFSETS_MIN:
            col = f"sr_{'m' if off < 0 else 'p'}{abs(off)}"
            loro_col = f"loro_min_{col}"
            sub = g.dropna(subset=[col, loro_col])
            pos = sub[loro_col] < thr
            hyp = sub.loc[pos]
            non = sub.loc[~pos]
            rows.append(
                {
                    "offset_min_rel_sr": int(off),
                    "col": col,
                    "n_ref_pos": len(hyp),
                    "recall_95_pct": clustered_rate((hyp[col] < thr).astype(int), hyp["cluster"]),
                    "ref_neg_alarm_95_pct": clustered_rate((non[col] < thr).astype(int), non["cluster"]),
                }
            )
        offset_profile[net] = rows
    results["sunrise_offset_profile_lt5"] = offset_profile
    return results


def run_cadence_downsampling(audits_df: pd.DataFrame) -> dict:
    """Downsample all native <=15-min stations in USGS and EA onto exact 15-, 30-, and 60-min UTC grids."""
    out: dict = {}
    for net in ("USGS", "EA"):
        meta = read_candidates(net)
        hf_sites = set(audits_df.loc[(audits_df["network"] == net) & (audits_df["native_step_min"] <= 15), "site"])
        meta_hf = meta[meta["site"].isin(hf_sites)]
        net_out: dict = {"n_highfreq_sites_tested": len(meta_hf), "cadences": {}}

        # Pre-load station series once
        loaded = []
        for row in meta_hf.itertuples(index=False):
            ts, vals = read_station_utc(net, row.site)
            loaded.append((row.site, str(row.cluster), float(row.lat), float(row.lon), ts, vals))

        for cad in (15, 30, 60):
            recs = []
            for site, cluster, lat, lon, ts, vals in loaded:
                # Select exact on-grid UTC readings matching cadence (minute % cad == 0 and second == 0)
                keep = (ts.minute % cad == 0) & (ts.second == 0)
                if keep.sum() < 100:
                    continue
                ts_c = ts[keep]
                vals_c = vals[keep]
                solar_c = (ts_c - EPOCH).total_seconds().to_numpy() / 60.0 + 4.0 * lon
                st_recs, _, _ = evaluate_station_full(
                    net, site, cluster, lat, lon,
                    solar_override=solar_c,
                    values_override=vals_c,
                    forced_step=cad,
                    detailed_episodes=True,
                )
                recs.extend(st_recs)
            df_c = pd.DataFrame(recs)
            pos = df_c["night_min_loro"] < 5.0
            hyp = df_c.loc[pos]
            non = df_c.loc[~pos]
            sh_hyp = df_c.loc[df_c["night_min_shared"] < 5.0]
            closed = sh_hyp["t5_night_dur_lo_hr"].dropna()
            closed_hi = sh_hyp["t5_night_dur_hi_hr"].dropna()
            km_n = kaplan_meier_quantiles(
                sh_hyp["t5_night_km_obs_hr"].to_numpy(dtype=float),
                sh_hyp["t5_night_km_event"].to_numpy(dtype=int),
            )
            net_out["cadences"][f"{cad}min"] = {
                "cadence_min": cad,
                "n_sites": int(df_c["site"].nunique()),
                "n_matched_nights": len(df_c),
                "shared_lt5_nights": len(sh_hyp),
                "loro_lt5_nights": len(hyp),
                "shared_minus_loro_dropped": int(len(sh_hyp) - len(hyp)),
                "predawn_recall_95_pct": clustered_rate((hyp["predawn"] < 5.0).astype(int), hyp["cluster"]),
                "afternoon_recall_95_pct": clustered_rate((hyp["afternoon"] < 5.0).astype(int), hyp["cluster"]),
                "loro_dawn_minus_afternoon_95_pp": clustered_rate(
                    (hyp["predawn"] < 5.0).astype(int) - (hyp["afternoon"] < 5.0).astype(int),
                    hyp["cluster"],
                ),
                "predawn_ref_neg_alarm_pct": float(100.0 * (non["predawn"] < 5.0).mean()),
                "both_closed_n": len(closed),
                "both_closed_median_lo_hi_hr": [float(closed.median()), float(closed_hi.median())] if len(closed) else [None, None],
                "km_nocturnal_median_hr": km_n["median_hr"],
            }
            print(
                f"  Downsample {net} {cad}min: {len(df_c):,} nights, LORO <5={len(hyp):,}, "
                f"gain={net_out['cadences'][f'{cad}min']['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} pp, "
                f"ref-neg alarm={net_out['cadences'][f'{cad}min']['predawn_ref_neg_alarm_pct']:.3f}%",
                flush=True,
            )
        # For EA, also evaluate 30 -> 60 min downsampling across all native <=30 min stations (broader cluster support)
        if net == "EA":
            le30_sites = set(audits_df.loc[(audits_df["network"] == "EA") & (audits_df["native_step_min"] <= 30), "site"])
            meta_30 = meta[meta["site"].isin(le30_sites)]
            loaded_30 = []
            for row in meta_30.itertuples(index=False):
                ts, vals = read_station_utc(net, row.site)
                loaded_30.append((row.site, str(row.cluster), float(row.lat), float(row.lon), ts, vals))
            ea30_out: dict = {"n_sites_le30min": len(meta_30), "cadences": {}}
            for cad in (30, 60):
                recs = []
                for site, cluster, lat, lon, ts, vals in loaded_30:
                    keep = (ts.minute % cad == 0) & (ts.second == 0)
                    if keep.sum() < 100:
                        continue
                    ts_c, vals_c = ts[keep], vals[keep]
                    solar_c = (ts_c - EPOCH).total_seconds().to_numpy() / 60.0 + 4.0 * lon
                    st_recs, _, _ = evaluate_station_full(
                        net, site, cluster, lat, lon,
                        solar_override=solar_c, values_override=vals_c, forced_step=cad, detailed_episodes=True,
                    )
                    recs.extend(st_recs)
                df_c = pd.DataFrame(recs)
                pos = df_c["night_min_loro"] < 5.0
                hyp, non = df_c.loc[pos], df_c.loc[~pos]
                sh_hyp = df_c.loc[df_c["night_min_shared"] < 5.0]
                ea30_out["cadences"][f"{cad}min"] = {
                    "cadence_min": cad,
                    "n_sites": int(df_c["site"].nunique()),
                    "n_clusters": int(hyp["cluster"].nunique()),
                    "n_matched_nights": len(df_c),
                    "loro_lt5_nights": len(hyp),
                    "shared_minus_loro_dropped": int(len(sh_hyp) - len(hyp)),
                    "loro_dawn_minus_afternoon_95_pp": clustered_rate(
                        (hyp["predawn"] < 5.0).astype(int) - (hyp["afternoon"] < 5.0).astype(int), hyp["cluster"]
                    ),
                    "predawn_ref_neg_alarm_pct": float(100.0 * (non["predawn"] < 5.0).mean()),
                }
            net_out["ea_le30min_cohort_30_vs_60"] = ea30_out
        out[net] = net_out
    return out


def summarize_attrition(audits_df: pd.DataFrame, attr_df: pd.DataFrame) -> dict:
    """Summarize common-support entry rates and attrition by network, native cadence, and month."""
    summary: dict = {}
    for net in ("USGS", "EA"):
        a_net = audits_df[audits_df["network"] == net]
        r_net = attr_df[attr_df["network"] == net]
        cand = int(a_net["candidate_nights"].sum())
        comp = int(a_net["complete_nights"].sum())
        mat = int(a_net["matched_nights"].sum())
        by_step = []
        for step, grp in r_net.groupby("native_step_min"):
            n_tot = len(grp)
            n_m = int((grp["status"] == "matched").sum())
            by_step.append(
                {
                    "native_step_min": int(step),
                    "n_sites": int(grp["site"].nunique()),
                    "candidate_nights": n_tot,
                    "matched_nights": n_m,
                    "entry_rate_pct": float(100.0 * n_m / n_tot),
                    "fail_night_gap": int((grp["status"] == "fail_night_gap").sum()),
                    "fail_target_match": int((grp["status"] == "fail_target_match").sum()),
                    "fail_predawn_outside": int((grp["status"] == "fail_predawn_outside").sum()),
                }
            )
        by_month = []
        for m, grp in r_net.groupby("month"):
            n_tot = len(grp)
            n_m = int((grp["status"] == "matched").sum())
            by_month.append(
                {
                    "month": int(m),
                    "candidate_nights": n_tot,
                    "matched_nights": n_m,
                    "entry_rate_pct": float(100.0 * n_m / n_tot),
                    "fail_night_gap": int((grp["status"] == "fail_night_gap").sum()),
                    "fail_target_match": int((grp["status"] == "fail_target_match").sum()),
                }
            )
        incl_lt5_pct = float(100.0 * r_net.loc[r_net["status"] == "matched", "partial_lt5"].mean())
        excl_obs = r_net[(r_net["status"] != "matched") & (r_net["has_partial_obs"])]
        excl_lt5_pct = float(100.0 * excl_obs["partial_lt5"].mean()) if len(excl_obs) else np.nan
        summary[net] = {
            "n_sites_candidate": len(a_net),
            "n_sites_with_matched": int((a_net["matched_nights"] > 0).sum()),
            "candidate_nights": cand,
            "complete_nights": comp,
            "matched_nights": mat,
            "complete_rate_pct": float(100.0 * comp / cand),
            "common_support_entry_pct": float(100.0 * mat / cand),
            "fail_night_gap": int(a_net["fail_night_gap"].sum()),
            "fail_target_match": int(a_net["fail_target_match"].sum()),
            "fail_predawn_outside": int(a_net["fail_predawn_outside"].sum()),
            "included_lt5_rate_pct": incl_lt5_pct,
            "excluded_with_partial_obs_n": len(excl_obs),
            "excluded_partial_lt5_rate_pct": excl_lt5_pct,
            "by_native_step": by_step,
            "by_month": by_month,
        }
    return summary


def audit_real_wqp_grab_logs(df_nights: pd.DataFrame) -> dict:
    """Audit actual timestamped WQP discrete grab-sample logs (2021-2024 IV-139 and 2015-2024 CONUS-397):
    1) Real-world empirical clock distribution (local clock & solar time & relative to sunrise).
    2) Independent co-located field-meter vs. continuous sonde validation (|dt| <= 30 min).
    3) Actual agency visit-day nocturnal hypoxia detection vs. miss rate.
    """
    wqp_iv_p = DATA / "raw_wqp" / "wqp_iv139_2021_2024.parquet"
    wqp_all_p = DATA / "raw_wqp" / "wqp_conus397_2015_2024.parquet"
    if not wqp_iv_p.exists():
        return {"available": False}

    def summarize_clock(pq_path: Path) -> tuple[pd.DataFrame, dict]:
        raw = pd.read_parquet(pq_path)
        visits = raw.groupby(["site", "time_utc"], as_index=False).agg(
            do_grab=("do_grab", "median"),
            local_clock_hr=("local_clock_hr", "first"),
            solar_hr=("solar_hr", "first"),
            solar_min=("solar_min", "first"),
            solar_day=("solar_day", "first"),
            lat=("lat", "first"),
            lon=("lon", "first"),
            huc2=("huc2", "first"),
            month=("month", "first"),
        )
        # Compute geometric sunrise/sunset for each visit
        dates = pd.to_datetime(visits["solar_day"], unit="D", origin="unix")
        sr_min = np.array([solar_boundaries(lat, d)[0] for lat, d in zip(visits["lat"], dates, strict=True)])
        ss_min = np.array([solar_boundaries(lat, d)[1] for lat, d in zip(visits["lat"], dates, strict=True)])
        tod_min = visits["solar_hr"].to_numpy() * 60.0
        visits["rel_sr_hr"] = (tod_min - sr_min) / 60.0
        in_daylight = (tod_min >= sr_min) & (tod_min <= ss_min)
        in_predawn_2h = (tod_min >= sr_min - 120.0) & (tod_min < sr_min)
        in_work_08_17 = visits["local_clock_hr"].between(8.0, 17.0)
        in_morning_08_12 = visits["local_clock_hr"].between(8.0, 12.0, inclusive="left")
        in_afternoon_12_17 = visits["local_clock_hr"].between(12.0, 17.0)
        # Hourly histogram (0..23 local civil clock and solar hour)
        hist_local = [int(np.sum((visits["local_clock_hr"] >= h) & (visits["local_clock_hr"] < h + 1))) for h in range(24)]
        hist_solar = [int(np.sum((visits["solar_hr"] >= h) & (visits["solar_hr"] < h + 1))) for h in range(24)]
        info = {
            "n_visits": len(visits),
            "n_sites": int(visits["site"].nunique()),
            "n_huc2": int(visits["huc2"].nunique()),
            "local_clock_median_hr": float(visits["local_clock_hr"].median()),
            "local_clock_iqr_hr": [float(visits["local_clock_hr"].quantile(0.25)), float(visits["local_clock_hr"].quantile(0.75))],
            "solar_median_hr": float(visits["solar_hr"].median()),
            "solar_iqr_hr": [float(visits["solar_hr"].quantile(0.25)), float(visits["solar_hr"].quantile(0.75))],
            "rel_sr_median_hr": float(visits["rel_sr_hr"].median()),
            "pct_daylight": float(100.0 * in_daylight.mean()),
            "pct_work_08_17_local": float(100.0 * in_work_08_17.mean()),
            "pct_morning_08_12_local": float(100.0 * in_morning_08_12.mean()),
            "pct_afternoon_12_17_local": float(100.0 * in_afternoon_12_17.mean()),
            "pct_predawn_2h": float(100.0 * in_predawn_2h.mean()),
            "n_predawn_2h": int(in_predawn_2h.sum()),
            "hourly_hist_local": hist_local,
            "hourly_hist_solar": hist_solar,
        }
        return visits, info

    iv_visits, iv_clock = summarize_clock(wqp_iv_p)
    _all_visits, all_clock = summarize_clock(wqp_all_p) if wqp_all_p.exists() else (pd.DataFrame(), {})

    # Pair IV-139 discrete field-meter visits against raw continuous USGS STAC sonde readings (|dt| <= 30 min)
    # AND against matched nocturnal reference outcomes on the exact same solar day!
    us_nights = df_nights[df_nights["network"] == "USGS"].set_index(["site", "day_index"])
    paired_rows = []
    for site, s_grp in iv_visits.groupby("site"):
        pq_f = DATA / "raw_usgs_stac" / f"{site}.parquet"
        if not pq_f.exists():
            continue
        ts, vals = read_station_utc("USGS", str(site))
        sec_sonde = (ts - EPOCH).total_seconds().to_numpy()
        for v in s_grp.itertuples(index=False):
            t_v = (v.time_utc - EPOCH).total_seconds()
            ix = int(np.searchsorted(sec_sonde, t_v))
            best_i = None
            best_dt = 1801.0
            for c in (ix - 1, ix):
                if 0 <= c < len(sec_sonde):
                    dt = abs(sec_sonde[c] - t_v)
                    if dt < best_dt:
                        best_dt = dt
                        best_i = c
            sonde_do = float(vals[best_i]) if best_i is not None and best_dt <= 1800.0 else np.nan
            key = (str(site), int(v.solar_day))
            has_night = key in us_nights.index
            night_row = us_nights.loc[key] if has_night else None
            paired_rows.append(
                {
                    "site": str(site),
                    "huc2": str(v.huc2),
                    "time_utc": v.time_utc,
                    "local_clock_hr": float(v.local_clock_hr),
                    "solar_hr": float(v.solar_hr),
                    "rel_sr_hr": float(v.rel_sr_hr),
                    "do_grab": float(v.do_grab),
                    "do_sonde": sonde_do,
                    "dt_min": float(best_dt / 60.0) if best_i is not None and best_dt <= 1800.0 else np.nan,
                    "has_matched_night": has_night,
                    "night_min_loro": float(night_row["night_min_loro"]) if has_night else np.nan,
                    "predawn_sonde": float(night_row["predawn"]) if has_night else np.nan,
                    "t5_actionable_2h": bool(night_row["t5_actionable_2h"]) if has_night else False,
                }
            )
    pdf = pd.DataFrame(paired_rows)
    pdf.to_parquet(PROC / "v4_wqp_paired_visits.parquet", index=False)

    # Independent probe validation stats
    co = pdf.dropna(subset=["do_grab", "do_sonde"])
    diff = co["do_sonde"] - co["do_grab"]
    r_val = float(stats.pearsonr(co["do_grab"], co["do_sonde"])[0]) if len(co) >= 3 else np.nan
    mae = float(np.abs(diff).mean()) if len(co) else np.nan
    rmse = float(np.sqrt(np.mean(diff**2))) if len(co) else np.nan
    bias = float(diff.mean()) if len(co) else np.nan
    within_02 = float(100.0 * (np.abs(diff) <= 0.20).mean()) if len(co) else np.nan
    within_05 = float(100.0 * (np.abs(diff) <= 0.50).mean()) if len(co) else np.nan

    # Actual agency grab-sample detection on matched nocturnal-hypoxia days (independent instrument!)
    mn = pdf[pdf["has_matched_night"]].copy()
    hyp5 = mn[mn["night_min_loro"] < 5.0]
    non5 = mn[mn["night_min_loro"] >= 5.0]
    act5 = mn[mn["t5_actionable_2h"]]

    return {
        "available": True,
        "iv139_2021_2024_clock": iv_clock,
        "conus397_2015_2024_clock": all_clock,
        "independent_colocated_validation": {
            "n_paired_readings_le30min": len(co),
            "n_sites": int(co["site"].nunique()),
            "median_dt_min": float(co["dt_min"].median()) if len(co) else None,
            "pearson_r": r_val,
            "mean_bias_sonde_minus_grab_mgL": bias,
            "median_abs_err_mgL": float(np.abs(diff).median()) if len(co) else None,
            "mae_mgL": mae,
            "rmse_mgL": rmse,
            "pct_within_0p2_mgL": within_02,
            "pct_within_0p5_mgL": within_05,
        },
        "actual_agency_visit_detection": {
            "n_matched_visit_nights": len(mn),
            "n_sites": int(mn["site"].nunique()),
            "lt5_n_hyp_nights": len(hyp5),
            "lt5_grab_detected": int((hyp5["do_grab"] < 5.0).sum()),
            "lt5_grab_recall_pct": float(100.0 * (hyp5["do_grab"] < 5.0).mean()) if len(hyp5) else None,
            "lt5_grab_missed_pct": float(100.0 * (hyp5["do_grab"] >= 5.0).mean()) if len(hyp5) else None,
            "lt5_predawn_sonde_detected": int((hyp5["predawn_sonde"] < 5.0).sum()),
            "lt5_predawn_sonde_recall_pct": float(100.0 * (hyp5["predawn_sonde"] < 5.0).mean()) if len(hyp5) else None,
            "lt5_grab_ref_neg_alarms": int((non5["do_grab"] < 5.0).sum()),
            "lt5_grab_ref_neg_alarm_pct": float(100.0 * (non5["do_grab"] < 5.0).mean()) if len(non5) else None,
            "actionable_2h_n_nights": len(act5),
            "actionable_2h_grab_detected": int((act5["do_grab"] < 5.0).sum()),
            "actionable_2h_grab_recall_pct": float(100.0 * (act5["do_grab"] < 5.0).mean()) if len(act5) else None,
            "actionable_2h_predawn_recall_pct": float(100.0 * (act5["predawn_sonde"] < 5.0).mean()) if len(act5) else None,
        },
    }


def main() -> None:
    RES.mkdir(parents=True, exist_ok=True)
    TBL.mkdir(parents=True, exist_ok=True)
    PROC.mkdir(parents=True, exist_ok=True)

    all_records: list[dict] = []
    all_audits: list[dict] = []
    all_attrition: list[dict] = []

    for net in ("USGS", "EA"):
        meta = read_candidates(net)
        print(f"Evaluating {net} ({len(meta)} screened stations) on raw UTC timestamps...", flush=True)
        for row in meta.itertuples(index=False):
            recs, aud, att = evaluate_station_full(net, row.site, str(row.cluster), float(row.lat), float(row.lon))
            all_records.extend(recs)
            all_audits.append(aud)
            all_attrition.extend(att)
        print(f"  Completed {net}: {sum(a['matched_nights'] for a in all_audits if a['network'] == net):,} matched site-nights", flush=True)

    df_nights = pd.DataFrame(all_records)
    df_audits = pd.DataFrame(all_audits)
    df_attr = pd.DataFrame(all_attrition)

    df_nights.to_parquet(PROC / "v4_nocturnal_site_nights.parquet", index=False)
    df_audits.to_csv(TBL / "table_s1_station_coverage_attrition.csv", index=False)

    print("Summarizing primary LORO, tolerance, persistence, censoring & KM duration...", flush=True)
    loro_summary = summarize_loro_primary(df_nights)

    print("Running out-of-sample region/site holdout & cross-Atlantic transfer...", flush=True)
    holdout = run_holdout_validation(df_nights)

    print("Running 15/30/60-min cadence downsampling on high-frequency stations...", flush=True)
    downsampling = run_cadence_downsampling(df_audits)

    print("Summarizing coverage & attrition...", flush=True)
    attrition = summarize_attrition(df_audits, df_attr)

    print("Auditing real timestamped WQP discrete grab-sample logs...", flush=True)
    wqp_audit = audit_real_wqp_grab_logs(df_nights)

    receipt = {
        "loro_primary": loro_summary,
        "holdout_validation": holdout,
        "cadence_downsampling": downsampling,
        "coverage_attrition": attrition,
        "real_wqp_grab_audit": wqp_audit,
    }
    out_path = RES / "11_loro_and_sensitivity.json"
    out_path.write_text(json.dumps(receipt, indent=2, allow_nan=True) + "\n", encoding="utf-8")

    # Print key verification benchmarks immediately
    for net in ("USGS", "EA"):
        b5 = loro_summary[net]["thresholds"]["5"]
        print(
            f"\n[{net} <5 mg/L] N={loro_summary[net]['n_nights']:,} nights | "
            f"Shared pos={b5['shared_n_ref_pos']:,} -> LORO pos={b5['loro_n_ref_pos']:,} "
            f"(dropped={b5['shared_minus_loro_dropped_nights']}) | "
            f"Shared gain={b5['shared_dawn_minus_afternoon_95_pp'][0]:+.2f} pp | "
            f"LORO gain={b5['loro_dawn_minus_afternoon_95_pp'][0]:+.2f} pp "
            f"[{b5['loro_dawn_minus_afternoon_95_pp'][1]:+.2f}, {b5['loro_dawn_minus_afternoon_95_pp'][2]:+.2f}] | "
            f"LORO predawn ref-neg alarm={b5['loro_schedules']['predawn']['ref_neg_alarm_95_pct'][0]:.3f}%",
            flush=True,
        )
        cd = b5["censoring_and_duration"]
        print(
            f"  Censoring: {cd['censor_counts']} | Closed median={cd['both_closed_median_lo_hi_hr']} h | "
            f"KM night median={cd['km_nocturnal_observed_onset']['median_hr']} h | "
            f"Full continuous median/IQR={cd['full_continuous_median_iqr_hr']} h",
            flush=True,
        )
    if wqp_audit.get("available"):
        print("\n[WQP Real Grab Audit]", json.dumps(wqp_audit["independent_colocated_validation"], indent=2))
        print("[WQP Actual Visit Detection]", json.dumps(wqp_audit["actual_agency_visit_detection"], indent=2))


if __name__ == "__main__":
    main()
