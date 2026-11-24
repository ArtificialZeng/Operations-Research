"""
Stage-0 Bounded CPU Dev Pilot Runner — GB Wind Forecast Intraday Signed Revision-Timing Signal.

Pre-Locked Protocol: `STAGE0_DEV_PILOT_PROTOCOL.md`
Data Span: Dev period ONLY (`2024-10-15 .. 2026-05-31`, `594` days from cached `raw_dev_chunks/`).
Held-out span (`2026-06-04 .. 2026-11-23`, `173` days) is NOT downloaded and NOT touched.

Strictly enforces:
  - Research cutoff `11:00:00 UTC` on delivery date D (hard assertion: publishTime <= D 11:00:00Z for ALL predictors).
  - Two disjoint chronological validation blocks with 3-day purge gaps:
      * Dev-Val 1: Train 2024-10-15..2025-07-31 (290d) | Purge 3d | Eval 2025-08-04..2025-12-31 (150d)
      * Dev-Val 2: Train 2024-10-15..2025-12-31 (443d) | Purge 3d | Eval 2026-01-04..2026-05-31 (148d)
  - Training-only q20 drop threshold (zero validation peeking).
  - Identical learner & X_base inputs for Baseline vs Candidate (adds ONLY single signed timing shift).
  - Both falsifiers: conditioned shift-shuffle placebo (N=200) and signed direction vs actual relative timing.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta, timezone
import hashlib
import json
import math
import os
import pathlib
import time
from typing import Any, Dict, List, Tuple

import numpy as np
from scipy import stats
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.preprocessing import StandardScaler


ROOT = pathlib.Path(__file__).resolve().parent
RAW_DEV = ROOT / "raw_dev_chunks"
OUT_DIR = ROOT / "dev_pilot_outputs"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DEV_START = date(2024, 10, 15)
DEV_END = date(2026, 5, 31)
REQ_HOURS = list(range(11, 22))  # 11..21 UTC inclusive (11 hourly points)
SEARCH_STARTS = list(range(11, 19))  # 11..18 UTC (8 overlapping 3h windows [s, s+3])

BLOCKS = [
    {
        "block_id": "Dev_Val_1",
        "train_start": date(2024, 10, 15),
        "train_end": date(2025, 7, 31),
        "eval_start": date(2025, 8, 4),
        "eval_end": date(2025, 12, 31),
    },
    {
        "block_id": "Dev_Val_2",
        "train_start": date(2024, 10, 15),
        "train_end": date(2025, 12, 31),
        "eval_start": date(2026, 1, 4),
        "eval_end": date(2026, 5, 31),
    },
]


def sha256_file(p: pathlib.Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_iso(s: str) -> datetime:
    return datetime.fromisoformat(s.replace("Z", "+00:00"))


def argmin_3h_drop(vec11: List[float]) -> Tuple[int, float]:
    """Steepest 3-hour drop over s in {11..18} UTC with fixed earliest-hour tie-break."""
    best_s = 11
    best_drop = vec11[3] - vec11[0]
    for i in range(1, 8):
        dv = vec11[i + 3] - vec11[i]
        if dv < best_drop:  # strict < enforces earliest-hour tie-break
            best_drop = dv
            best_s = 11 + i
    return best_s, float(best_drop)


def load_dev_raw() -> Tuple[Dict[str, Dict[str, float]], Dict[str, Tuple[str, float]]]:
    wf_clean: Dict[str, Dict[str, float]] = defaultdict(dict)
    for p in sorted(RAW_DEV.glob("windfor_*.json")):
        for r in json.loads(p.read_text(encoding="utf-8")):
            wf_clean[r["publishTime"]][r["startTime"]] = float(r["generation"])

    fh_raw: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
    for p in sorted(RAW_DEV.glob("fuelhh_*.json")):
        for r in json.loads(p.read_text(encoding="utf-8")):
            fh_raw[r["startTime"]].append((r["publishTime"], float(r["generation"])))
    fh_clean: Dict[str, Tuple[str, float]] = {}
    for st, recs in fh_raw.items():
        recs.sort(key=lambda x: x[0])
        fh_clean[st] = recs[-1]
    return wf_clean, fh_clean


def build_daily_records(
    wf_clean: Dict[str, Dict[str, float]],
    fh_clean: Dict[str, Tuple[str, float]],
) -> List[Dict[str, Any]]:
    all_pubs = sorted(wf_clean.keys())
    all_pubs_dt = [parse_iso(p) for p in all_pubs]

    records: List[Dict[str, Any]] = []
    cur = DEV_START
    while cur <= DEV_END:
        ds = str(cur)
        cutoff_dt = datetime(cur.year, cur.month, cur.day, 11, 0, 0, tzinfo=timezone.utc)
        cutoff_iso = f"{ds}T11:00:00Z"
        win_start_dt = cutoff_dt - timedelta(hours=36)
        req_sts = [f"{ds}T{h:02d}:00:00Z" for h in REQ_HOURS]

        cands = []
        for p, pdt in zip(all_pubs, all_pubs_dt):
            if win_start_dt <= pdt <= cutoff_dt:
                assert p <= cutoff_iso, f"CAUSAL VIOLATION WINDFOR {p} > {cutoff_iso}"
                smap = wf_clean[p]
                if all(st in smap for st in req_sts):
                    cands.append((p, pdt, [smap[st] for st in req_sts], smap))

        assert len(cands) >= 2, f"Missing WINDFOR vintages on {ds}"
        v_new_p, v_new_dt, v_new_vec, v_new_map = cands[-1]
        assert v_new_p <= cutoff_iso

        # Reasonably separated distinct prior vintage (>= 4h earlier, distinct on G)
        sep4 = [
            c
            for c in cands[:-1]
            if (v_new_dt - c[1]).total_seconds() >= 4 * 3600 - 60 and c[2] != v_new_vec
        ]
        assert len(sep4) >= 1, f"Missing >=4h distinct prior vintage on {ds}"
        v_old_p, v_old_dt, v_old_vec, _ = sep4[-1]
        assert v_old_p <= cutoff_iso

        # Strict causal pre-cutoff FUELHH outturn lags (publishTime <= D 11:00:00Z!)
        causal_fh = []
        for back_min in range(0, 36 * 60, 30):
            t_dt = cutoff_dt - timedelta(minutes=back_min)
            t_iso = t_dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            if t_iso in fh_clean:
                pub_iso, gen_mw = fh_clean[t_iso]
                if pub_iso <= cutoff_iso:
                    assert pub_iso <= cutoff_iso
                    causal_fh.append((t_dt, t_iso, pub_iso, gen_mw))
                    if len(causal_fh) >= 24:
                        break
        assert len(causal_fh) >= 7, f"Insufficient causal FUELHH rows on {ds}"
        t_last_dt, t_last_iso, pub_last_iso, gen_last = causal_fh[0]
        assert pub_last_iso <= cutoff_iso
        age_last_h = (cutoff_dt - t_last_dt).total_seconds() / 3600.0

        # 3h prior causal actual
        t_3h_iso = (t_last_dt - timedelta(hours=3)).strftime("%Y-%m-%dT%H:%M:%SZ")
        assert t_3h_iso in fh_clean and fh_clean[t_3h_iso][0] <= cutoff_iso
        trend_3h = gen_last - fh_clean[t_3h_iso][1]

        # Nearest causal whole hour <= t_last_dt present in v_new_map
        t_hr_dt = t_last_dt.replace(minute=0, second=0, microsecond=0)
        causal_fcst_err = 0.0
        for step_back in range(0, 8):
            cand_hr_iso = (t_hr_dt - timedelta(hours=step_back)).strftime("%Y-%m-%dT%H:%M:%SZ")
            if cand_hr_iso in v_new_map and cand_hr_iso in fh_clean and fh_clean[cand_hr_iso][0] <= cutoff_iso:
                causal_fcst_err = v_new_map[cand_hr_iso] - fh_clean[cand_hr_iso][1]
                break

        # Realized hourly outturns (avg_fwd: 0.5*(HH:00 + HH:30)) over G = 11..21 UTC (TARGET ONLY!)
        actual_hr = []
        for h in REQ_HOURS:
            st0 = f"{ds}T{h:02d}:00:00Z"
            st30 = f"{ds}T{h:02d}:30:00Z"
            assert st0 in fh_clean and st30 in fh_clean
            actual_hr.append(0.5 * (fh_clean[st0][1] + fh_clean[st30][1]))

        delta_actual_15_18 = actual_hr[18 - 11] - actual_hr[15 - 11]
        t_star_actual, min_drop_actual = argmin_3h_drop(actual_hr)

        t_star_new, min_drop_new = argmin_3h_drop(v_new_vec)
        t_star_old, min_drop_old = argmin_3h_drop(v_old_vec)
        signed_timing_shift = int(t_star_new - t_star_old)

        r_new_15_18 = v_new_vec[18 - 11] - v_new_vec[15 - 11]
        r_old_15_18 = v_old_vec[18 - 11] - v_old_vec[15 - 11]
        lead_new_h = (datetime(cur.year, cur.month, cur.day, 15, 0, 0, tzinfo=timezone.utc) - v_new_dt).total_seconds() / 3600.0
        gap_pub_h = (v_new_dt - v_old_dt).total_seconds() / 3600.0
        doy = cur.timetuple().tm_yday

        records.append(
            {
                "date": ds,
                "date_obj": cur,
                "pub_new": v_new_p,
                "pub_old": v_old_p,
                "v_new_vec": v_new_vec,
                "v_old_vec": v_old_vec,
                "r_new_15_18": r_new_15_18,
                "r_old_15_18": r_old_15_18,
                "min_drop_new": min_drop_new,
                "min_drop_old": min_drop_old,
                "t_star_new": t_star_new,
                "t_star_old": t_star_old,
                "signed_timing_shift": signed_timing_shift,
                "lead_new_h": lead_new_h,
                "gap_pub_h": gap_pub_h,
                "sin_doy": math.sin(2.0 * math.pi * doy / 365.25),
                "cos_doy": math.cos(2.0 * math.pi * doy / 365.25),
                "actual_causal_last": gen_last,
                "actual_causal_age_h": age_last_h,
                "actual_causal_3h_trend": trend_3h,
                "causal_fcst_err": causal_fcst_err,
                "delta_actual_15_18": delta_actual_15_18,
                "t_star_actual": t_star_actual,
                "min_drop_actual": min_drop_actual,
            }
        )
        cur += timedelta(days=1)
    return records


def build_feature_matrices(
    recs: List[Dict[str, Any]],
    tau_train: float,
) -> Tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, List[str]]:
    """Returns (X_simple, X_base, X_cand, shift_col, base_feature_names)."""
    base_names = (
        [f"f_new_{h:02d}Z" for h in REQ_HOURS]
        + [f"f_old_{h:02d}Z" for h in REQ_HOURS]
        + [f"df_{h:02d}Z" for h in REQ_HOURS]
        + [
            "r_new_15_18",
            "r_old_15_18",
            "dr_15_18",
            "lag_ens_ramp",
            "min_drop_new",
            "min_drop_old",
            "t_star_new",
            "abs_t_star_new_minus_15",
            "lead_new_h",
            "gap_pub_h",
            "sin_doy",
            "cos_doy",
            "agree_new_flag",
            "agree_old_flag",
            "agree_both_flag",
            "agree_min_new_flag",
            "agree_min_old_flag",
            "actual_causal_last",
            "actual_causal_age_h",
            "actual_causal_3h_trend",
            "causal_fcst_err",
        ]
    )

    simple_rows = []
    base_rows = []
    shifts = []
    for r in recs:
        vn = r["v_new_vec"]
        vo = r["v_old_vec"]
        df = [vn[i] - vo[i] for i in range(len(REQ_HOURS))]
        rn = r["r_new_15_18"]
        ro = r["r_old_15_18"]
        lag_ens = 0.5 * (rn + ro)
        ag_n = 1.0 if rn <= tau_train else 0.0
        ag_o = 1.0 if ro <= tau_train else 0.0
        ag_b = ag_n * ag_o
        ag_mn = 1.0 if r["min_drop_new"] <= tau_train else 0.0
        ag_mo = 1.0 if r["min_drop_old"] <= tau_train else 0.0

        simple_rows.append([rn, ro, lag_ens])
        base_rows.append(
            vn
            + vo
            + df
            + [
                rn,
                ro,
                rn - ro,
                lag_ens,
                r["min_drop_new"],
                r["min_drop_old"],
                float(r["t_star_new"]),
                float(abs(r["t_star_new"] - 15)),
                r["lead_new_h"],
                r["gap_pub_h"],
                r["sin_doy"],
                r["cos_doy"],
                ag_n,
                ag_o,
                ag_b,
                ag_mn,
                ag_mo,
                r["actual_causal_last"],
                r["actual_causal_age_h"],
                r["actual_causal_3h_trend"],
                r["causal_fcst_err"],
            ]
        )
        shifts.append(float(r["signed_timing_shift"]))

    X_simple = np.asarray(simple_rows, dtype=float)
    X_base = np.asarray(base_rows, dtype=float)
    shift_arr = np.asarray(shifts, dtype=float)
    X_cand = np.column_stack([X_base, shift_arr])
    assert X_base.shape[1] == len(base_names)
    return X_simple, X_base, X_cand, shift_arr, base_names


def fit_predict_lr(X_tr: np.ndarray, y_tr: np.ndarray, X_ev: np.ndarray, C: float = 0.2) -> Tuple[np.ndarray, np.ndarray]:
    sc = StandardScaler()
    Xtr_s = sc.fit_transform(X_tr)
    Xev_s = sc.transform(X_ev)
    clf = LogisticRegression(C=C, max_iter=1000)
    clf.fit(Xtr_s, y_tr)
    return clf.predict_proba(Xev_s)[:, 1], clf.coef_[0]


def fit_predict_hgb(X_tr: np.ndarray, y_tr: np.ndarray, X_ev: np.ndarray) -> np.ndarray:
    clf = HistGradientBoostingClassifier(
        max_depth=3,
        learning_rate=0.05,
        max_iter=100,
        min_samples_leaf=20,
        l2_regularization=2.0,
        random_state=42,
    )
    clf.fit(X_tr, y_tr)
    return clf.predict_proba(X_ev)[:, 1]


def ece_5bin(y: np.ndarray, p: np.ndarray) -> float:
    bins = np.linspace(0.0, 1.0, 6)
    ece = 0.0
    n = len(y)
    for i in range(5):
        lo, hi = bins[i], bins[i + 1]
        mask = (p >= lo) & (p <= hi if i == 4 else p < hi)
        if np.any(mask):
            ece += (np.sum(mask) / n) * abs(float(np.mean(y[mask])) - float(np.mean(p[mask])))
    return float(ece)


def cost_loss_metrics(y: np.ndarray, p: np.ndarray, thr: float, cl_ratio: float) -> Dict[str, Any]:
    pred = (p >= thr).astype(int)
    tp = int(np.sum((pred == 1) & (y == 1)))
    fp = int(np.sum((pred == 1) & (y == 0)))
    fn = int(np.sum((pred == 0) & (y == 1)))
    tn = int(np.sum((pred == 0) & (y == 0)))
    hit_rate = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    far = fp / (tp + fp) if (tp + fp) > 0 else 0.0
    prec = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    # Standard Richardson (2000) relative economic value at cost/loss ratio C/L
    n = len(y)
    base_rate = float(np.mean(y))
    e_clim = min(cl_ratio, base_rate)
    e_perf = cl_ratio * base_rate
    e_sys = (cl_ratio * (tp + fp) + 1.0 * fn) / n
    rel_val = (e_clim - e_sys) / (e_clim - e_perf) if (e_clim - e_perf) > 1e-12 else 0.0
    return {
        "thr": thr,
        "cl_ratio": cl_ratio,
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
        "hit_rate": round(hit_rate, 4),
        "false_alarm_ratio": round(far, 4),
        "precision": round(prec, 4),
        "expected_cost_per_day": round(e_sys, 4),
        "relative_economic_value": round(rel_val, 4),
    }


def eval_prob_metrics(y: np.ndarray, p: np.ndarray, clim_rate: float) -> Dict[str, Any]:
    p_clip = np.clip(p, 1e-6, 1.0 - 1e-6)
    brier = float(brier_score_loss(y, p_clip))
    brier_clim = float(np.mean((y - clim_rate) ** 2))
    bss = 1.0 - (brier / brier_clim) if brier_clim > 0 else 0.0
    # Calibration slope / intercept via logistic calibration on logit(p)
    logits = np.log(p_clip / (1.0 - p_clip))
    slope = float(np.cov(y, p_clip)[0, 1] / max(float(np.var(p_clip)), 1e-12))
    return {
        "n": int(len(y)),
        "n_events": int(np.sum(y)),
        "prevalence": round(float(np.mean(y)), 4),
        "brier": round(brier, 6),
        "brier_clim": round(brier_clim, 6),
        "bss_vs_train_clim": round(bss, 4),
        "log_loss": round(float(log_loss(y, p_clip)), 6),
        "ece_5bin": round(ece_5bin(y, p_clip), 4),
        "mean_pred_prob": round(float(np.mean(p_clip)), 4),
        "linear_cal_slope": round(slope, 4),
        "roc_auc": round(float(roc_auc_score(y, p_clip)), 4) if len(set(y)) > 1 else None,
        "pr_auc": round(float(average_precision_score(y, p_clip)), 4) if len(set(y)) > 1 else None,
        "ops_p30_cl25": cost_loss_metrics(y, p_clip, thr=0.30, cl_ratio=0.25),
        "ops_p50_cl50": cost_loss_metrics(y, p_clip, thr=0.50, cl_ratio=0.50),
    }


def block_bootstrap_delta_brier_ci(
    y: np.ndarray,
    p_base: np.ndarray,
    p_cand: np.ndarray,
    block_len: int = 5,
    n_boot: int = 2000,
    seed: int = 20261124,
) -> Dict[str, float]:
    rng = np.random.default_rng(seed)
    n = len(y)
    # Per-day Brier gain: positive means Candidate improved Brier over Baseline
    d = (y - p_base) ** 2 - (y - p_cand) ** 2
    obs = float(np.mean(d))
    n_blocks = int(math.ceil(n / block_len))
    starts_max = n - block_len + 1
    boots = np.empty(n_boot, dtype=float)
    for b in range(n_boot):
        starts = rng.integers(0, starts_max, size=n_blocks)
        idx = np.concatenate([np.arange(s, s + block_len) for s in starts])[:n]
        boots[b] = float(np.mean(d[idx]))
    lo, hi = np.quantile(boots, [0.025, 0.975])
    return {
        "delta_brier": round(obs, 6),
        "ci95_lo": round(float(lo), 6),
        "ci95_hi": round(float(hi), 6),
    }


def stratum_bins(t_star_new_arr: np.ndarray) -> np.ndarray:
    """3 strata for conditioned shift-shuffle placebo: <=13, 14..16, >=17."""
    bins = np.zeros(len(t_star_new_arr), dtype=int)
    bins[(t_star_new_arr >= 14) & (t_star_new_arr <= 16)] = 1
    bins[t_star_new_arr >= 17] = 2
    return bins


def permute_within_strata(vals: np.ndarray, strata: np.ndarray, rng: np.random.Generator) -> np.ndarray:
    out = vals.copy()
    for s in (0, 1, 2):
        idx = np.where(strata == s)[0]
        if len(idx) > 1:
            out[idx] = rng.permutation(out[idx])
    return out


def mechanism_diagnostics(recs: List[Dict[str, Any]], tau_train: float) -> Dict[str, Any]:
    shifts = np.array([r["signed_timing_shift"] for r in recs], dtype=float)
    rel_err = np.array([r["t_star_actual"] - r["t_star_new"] for r in recs], dtype=float)
    min_new = np.array([r["min_drop_new"] for r in recs], dtype=float)

    def corr_pack(x: np.ndarray, y: np.ndarray) -> Dict[str, Any]:
        if len(x) < 5 or np.std(x) == 0 or np.std(y) == 0:
            return {"n": int(len(x)), "pearson_r": None, "pearson_p": None, "spearman_rho": None, "spearman_p": None}
        pr, pp = stats.pearsonr(x, y)
        sr, sp = stats.spearmanr(x, y)
        return {
            "n": int(len(x)),
            "pearson_r": round(float(pr), 4),
            "pearson_p": round(float(pp), 4),
            "spearman_rho": round(float(sr), 4),
            "spearman_p": round(float(sp), 4),
            "mean_rel_err_when_shift_pos": round(float(np.mean(y[x > 0])), 3) if np.any(x > 0) else None,
            "mean_rel_err_when_shift_zero": round(float(np.mean(y[x == 0])), 3) if np.any(x == 0) else None,
            "mean_rel_err_when_shift_neg": round(float(np.mean(y[x < 0])), 3) if np.any(x < 0) else None,
        }

    mask_ramp = min_new <= tau_train
    return {
        "all_eval_days": corr_pack(shifts, rel_err),
        "predicted_ramp_days_only": corr_pack(shifts[mask_ramp], rel_err[mask_ramp]),
    }


def main() -> None:
    t0 = time.perf_counter()
    wf_clean, fh_clean = load_dev_raw()
    all_recs = build_daily_records(wf_clean, fh_clean)
    assert len(all_recs) == 594

    n_perm = 200
    rng = np.random.default_rng(20261124)

    block_reports: Dict[str, Any] = {}
    pooled_y: List[np.ndarray] = []
    pooled_preds = defaultdict(list)
    pooled_clims: List[float] = []
    pooled_placebo_lr = np.zeros(n_perm, dtype=float)
    pooled_placebo_hgb = np.zeros(n_perm, dtype=float)
    pooled_eval_recs: List[Dict[str, Any]] = []
    per_day_ledger: List[Dict[str, Any]] = []

    for bspec in BLOCKS:
        bid = bspec["block_id"]
        tr_recs = [r for r in all_recs if bspec["train_start"] <= r["date_obj"] <= bspec["train_end"]]
        ev_recs = [r for r in all_recs if bspec["eval_start"] <= r["date_obj"] <= bspec["eval_end"]]

        # Training-only q20 drop threshold (ZERO validation peeking!)
        y_tr_raw = np.array([r["delta_actual_15_18"] for r in tr_recs], dtype=float)
        tau_train = float(np.quantile(y_tr_raw, 0.20))
        y_tr = (y_tr_raw <= tau_train).astype(int)

        y_ev_raw = np.array([r["delta_actual_15_18"] for r in ev_recs], dtype=float)
        y_ev = (y_ev_raw <= tau_train).astype(int)
        clim_tr = float(np.mean(y_tr))

        Xtr_sim, Xtr_base, Xtr_cand, sh_tr, base_names = build_feature_matrices(tr_recs, tau_train)
        Xev_sim, Xev_base, Xev_cand, sh_ev, _ = build_feature_matrices(ev_recs, tau_train)

        # Fit & evaluate reference Simple Lagged-Ensemble, Primary L2_LogReg, and Strong HGB
        p_sim, _ = fit_predict_lr(Xtr_sim, y_tr, Xev_sim, C=1.0)
        p_lr_base, _ = fit_predict_lr(Xtr_base, y_tr, Xev_base, C=0.2)
        p_lr_cand, lr_cand_coef = fit_predict_lr(Xtr_cand, y_tr, Xev_cand, C=0.2)

        p_hgb_base = fit_predict_hgb(Xtr_base, y_tr, Xev_base)
        p_hgb_cand = fit_predict_hgb(Xtr_cand, y_tr, Xev_cand)

        brier_lr_base = float(brier_score_loss(y_ev, np.clip(p_lr_base, 1e-6, 1 - 1e-6)))
        brier_lr_cand = float(brier_score_loss(y_ev, np.clip(p_lr_cand, 1e-6, 1 - 1e-6)))
        delta_lr = brier_lr_base - brier_lr_cand

        brier_hgb_base = float(brier_score_loss(y_ev, np.clip(p_hgb_base, 1e-6, 1 - 1e-6)))
        brier_hgb_cand = float(brier_score_loss(y_ev, np.clip(p_hgb_cand, 1e-6, 1 - 1e-6)))
        delta_hgb = brier_hgb_base - brier_hgb_cand

        # Falsifier 1: Conditioned Shift-Shuffle Placebo (N=200) within t*(v_new) strata
        st_tr = stratum_bins(np.array([r["t_star_new"] for r in tr_recs]))
        st_ev = stratum_bins(np.array([r["t_star_new"] for r in ev_recs]))
        plac_deltas_lr = np.empty(n_perm, dtype=float)
        plac_deltas_hgb = np.empty(n_perm, dtype=float)
        for k in range(n_perm):
            sh_tr_p = permute_within_strata(sh_tr, st_tr, rng)
            sh_ev_p = permute_within_strata(sh_ev, st_ev, rng)
            Xtr_p = np.column_stack([Xtr_base, sh_tr_p])
            Xev_p = np.column_stack([Xev_base, sh_ev_p])
            p_lr_p, _ = fit_predict_lr(Xtr_p, y_tr, Xev_p, C=0.2)
            p_hgb_p = fit_predict_hgb(Xtr_p, y_tr, Xev_p)
            d_lr_p = brier_lr_base - float(brier_score_loss(y_ev, np.clip(p_lr_p, 1e-6, 1 - 1e-6)))
            d_hgb_p = brier_hgb_base - float(brier_score_loss(y_ev, np.clip(p_hgb_p, 1e-6, 1 - 1e-6)))
            plac_deltas_lr[k] = d_lr_p
            plac_deltas_hgb[k] = d_hgb_p
            # Accumulate weighted sum for pooled placebo
            pooled_placebo_lr[k] += d_lr_p * len(y_ev)
            pooled_placebo_hgb[k] += d_hgb_p * len(y_ev)

        p_val_plac_lr = float((1 + np.sum(plac_deltas_lr >= delta_lr)) / (n_perm + 1))
        p_val_plac_hgb = float((1 + np.sum(plac_deltas_hgb >= delta_hgb)) / (n_perm + 1))

        # Falsifier 2: Mechanism diagnostic (signed timing shift vs actual relative timing offset)
        mech = mechanism_diagnostics(ev_recs, tau_train)

        block_reports[bid] = {
            "train_span": [str(bspec["train_start"]), str(bspec["train_end"])],
            "eval_span": [str(bspec["eval_start"]), str(bspec["eval_end"])],
            "n_train": len(tr_recs),
            "n_eval": len(ev_recs),
            "tau_train_q20_MW": round(tau_train, 2),
            "train_events": int(np.sum(y_tr)),
            "eval_events": int(np.sum(y_ev)),
            "lr_cand_shift_std_coef": round(float(lr_cand_coef[-1]), 5),
            "metrics": {
                "Simple_LagEns": eval_prob_metrics(y_ev, p_sim, clim_tr),
                "L2_LogReg_Base": eval_prob_metrics(y_ev, p_lr_base, clim_tr),
                "L2_LogReg_Cand": eval_prob_metrics(y_ev, p_lr_cand, clim_tr),
                "HGB_Base": eval_prob_metrics(y_ev, p_hgb_base, clim_tr),
                "HGB_Cand": eval_prob_metrics(y_ev, p_hgb_cand, clim_tr),
            },
            "delta_brier_bootstrap": {
                "L2_LogReg_Cand_vs_Base": block_bootstrap_delta_brier_ci(y_ev, p_lr_base, p_lr_cand),
                "HGB_Cand_vs_Base": block_bootstrap_delta_brier_ci(y_ev, p_hgb_base, p_hgb_cand),
            },
            "falsifier1_conditioned_placebo": {
                "n_perm": n_perm,
                "L2_LogReg": {
                    "real_delta_brier": round(delta_lr, 6),
                    "placebo_mean_delta_brier": round(float(np.mean(plac_deltas_lr)), 6),
                    "placebo_p95_delta_brier": round(float(np.quantile(plac_deltas_lr, 0.95)), 6),
                    "p_placebo_onesided": round(p_val_plac_lr, 4),
                },
                "HGB": {
                    "real_delta_brier": round(delta_hgb, 6),
                    "placebo_mean_delta_brier": round(float(np.mean(plac_deltas_hgb)), 6),
                    "placebo_p95_delta_brier": round(float(np.quantile(plac_deltas_hgb, 0.95)), 6),
                    "p_placebo_onesided": round(p_val_plac_hgb, 4),
                },
            },
            "falsifier2_timing_mechanism": mech,
        }

        pooled_y.append(y_ev)
        pooled_clims.extend([clim_tr] * len(y_ev))
        pooled_preds["Simple_LagEns"].append(p_sim)
        pooled_preds["L2_LogReg_Base"].append(p_lr_base)
        pooled_preds["L2_LogReg_Cand"].append(p_lr_cand)
        pooled_preds["HGB_Base"].append(p_hgb_base)
        pooled_preds["HGB_Cand"].append(p_hgb_cand)
        pooled_eval_recs.extend(ev_recs)

        for i, r in enumerate(ev_recs):
            per_day_ledger.append(
                {
                    "block_id": bid,
                    "date": r["date"],
                    "pub_new": r["pub_new"],
                    "pub_old": r["pub_old"],
                    "tau_train_MW": round(tau_train, 2),
                    "delta_actual_15_18_MW": round(r["delta_actual_15_18"], 2),
                    "y_event": int(y_ev[i]),
                    "r_new_15_18_MW": round(r["r_new_15_18"], 2),
                    "r_old_15_18_MW": round(r["r_old_15_18"], 2),
                    "t_star_new": r["t_star_new"],
                    "t_star_old": r["t_star_old"],
                    "t_star_actual": r["t_star_actual"],
                    "signed_timing_shift": r["signed_timing_shift"],
                    "p_simple_lagens": round(float(p_sim[i]), 6),
                    "p_lr_base": round(float(p_lr_base[i]), 6),
                    "p_lr_cand": round(float(p_lr_cand[i]), 6),
                    "p_hgb_base": round(float(p_hgb_base[i]), 6),
                    "p_hgb_cand": round(float(p_hgb_cand[i]), 6),
                }
            )

        print(
            f"[{bid}] N={len(y_ev)} ev={int(np.sum(y_ev))} tau={tau_train:.1f}MW | "
            f"LR Base={brier_lr_base:.5f} Cand={brier_lr_cand:.5f} dB={delta_lr:+.5f} (p_plac={p_val_plac_lr:.4f}) | "
            f"HGB Base={brier_hgb_base:.5f} Cand={brier_hgb_cand:.5f} dB={delta_hgb:+.5f} (p_plac={p_val_plac_hgb:.4f})",
            flush=True,
        )

    # Pooled Dev-Val 1 + Dev-Val 2 summary
    y_pool = np.concatenate(pooled_y)
    n_pool = len(y_pool)
    clim_pool = float(np.mean(pooled_clims))
    p_pool = {k: np.concatenate(v) for k, v in pooled_preds.items()}
    pooled_placebo_lr /= n_pool
    pooled_placebo_hgb /= n_pool

    real_delta_pool_lr = float(brier_score_loss(y_pool, p_pool["L2_LogReg_Base"]) - brier_score_loss(y_pool, p_pool["L2_LogReg_Cand"]))
    real_delta_pool_hgb = float(brier_score_loss(y_pool, p_pool["HGB_Base"]) - brier_score_loss(y_pool, p_pool["HGB_Cand"]))
    p_plac_pool_lr = float((1 + np.sum(pooled_placebo_lr >= real_delta_pool_lr)) / (n_perm + 1))
    p_plac_pool_hgb = float((1 + np.sum(pooled_placebo_hgb >= real_delta_pool_hgb)) / (n_perm + 1))

    # Pre-locked conjunctive Dev-Pilot Advance Gate (STAGE0_DEV_PILOT_PROTOCOL.md §4)
    b1 = block_reports["Dev_Val_1"]
    b2 = block_reports["Dev_Val_2"]
    g1_events = (b1["eval_events"] >= 20) and (b2["eval_events"] >= 20)
    g2_brier = (
        (b1["falsifier1_conditioned_placebo"]["L2_LogReg"]["real_delta_brier"] >= 0.0020)
        and (b2["falsifier1_conditioned_placebo"]["L2_LogReg"]["real_delta_brier"] >= 0.0020)
        and (real_delta_pool_hgb >= 0.0)
    )
    g3_placebo = (
        (p_plac_pool_lr < 0.05)
        and (b1["falsifier1_conditioned_placebo"]["L2_LogReg"]["p_placebo_onesided"] < 0.15)
        and (b2["falsifier1_conditioned_placebo"]["L2_LogReg"]["p_placebo_onesided"] < 0.15)
    )
    r1_m = b1["falsifier2_timing_mechanism"]["all_eval_days"]["spearman_rho"]
    r2_m = b2["falsifier2_timing_mechanism"]["all_eval_days"]["spearman_rho"]
    g4_mech = (r1_m is not None and r2_m is not None and (r1_m * r2_m > 0))
    all_pass = bool(g1_events and g2_brier and g3_placebo and g4_mech)
    decision = "ADVANCE_TO_HELDOUT_PENDING_REVIEW" if all_pass else "STOP_DEV_PILOT_GATE_FAILED_NO_HELDOUT_TOUCHED"

    ledger_path = OUT_DIR / "dev_pilot_per_day_predictions.jsonl"
    with ledger_path.open("w", encoding="utf-8") as f:
        for row in per_day_ledger:
            f.write(json.dumps(row) + "\n")

    summary = {
        "protocol": "STAGE0_DEV_PILOT_PROTOCOL.md",
        "protocol_sha256": sha256_file(ROOT / "STAGE0_DEV_PILOT_PROTOCOL.md"),
        "runner_sha256": sha256_file(pathlib.Path(__file__)),
        "dev_audit_sha256": sha256_file(ROOT / "STAGE0_DEV_DATA_AUDIT.json"),
        "real_pid": os.getpid(),
        "wall_time_s": round(time.perf_counter() - t0, 3),
        "held_out_untouched": True,
        "held_out_span": ["2026-06-04", "2026-11-23"],
        "n_base_features": 54,
        "blocks": block_reports,
        "pooled_dev_val": {
            "n_eval": int(n_pool),
            "n_events": int(np.sum(y_pool)),
            "metrics": {k: eval_prob_metrics(y_pool, p_pool[k], clim_pool) for k in p_pool},
            "delta_brier_bootstrap": {
                "L2_LogReg_Cand_vs_Base": block_bootstrap_delta_brier_ci(y_pool, p_pool["L2_LogReg_Base"], p_pool["L2_LogReg_Cand"]),
                "HGB_Cand_vs_Base": block_bootstrap_delta_brier_ci(y_pool, p_pool["HGB_Base"], p_pool["HGB_Cand"]),
            },
            "falsifier1_conditioned_placebo": {
                "n_perm": n_perm,
                "L2_LogReg": {
                    "real_delta_brier": round(real_delta_pool_lr, 6),
                    "placebo_mean_delta_brier": round(float(np.mean(pooled_placebo_lr)), 6),
                    "placebo_p95_delta_brier": round(float(np.quantile(pooled_placebo_lr, 0.95)), 6),
                    "p_placebo_onesided": round(p_plac_pool_lr, 4),
                },
                "HGB": {
                    "real_delta_brier": round(real_delta_pool_hgb, 6),
                    "placebo_mean_delta_brier": round(float(np.mean(pooled_placebo_hgb)), 6),
                    "placebo_p95_delta_brier": round(float(np.quantile(pooled_placebo_hgb, 0.95)), 6),
                    "p_placebo_onesided": round(p_plac_pool_hgb, 4),
                },
            },
            "falsifier2_timing_mechanism_pooled": mechanism_diagnostics(
                pooled_eval_recs,
                tau_train=0.5 * (b1["tau_train_q20_MW"] + b2["tau_train_q20_MW"]),
            ),
        },
        "prespecified_conjunctive_gate": {
            "g1_ge_20_events_each_block": g1_events,
            "g2_repeatable_brier_gain_ge_0p002_both_blocks_and_hgb_nondeg": g2_brier,
            "g3_placebo_rejected_p_lt_0p05_pooled_and_lt_0p15_each": g3_placebo,
            "g4_mechanism_same_nonzero_sign_both_blocks": g4_mech,
            "all_pass": all_pass,
            "decision": decision,
        },
        "per_day_ledger_jsonl": ledger_path.name,
        "per_day_ledger_sha256": sha256_file(ledger_path),
    }

    sum_path = OUT_DIR / "dev_pilot_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("\n=== STAGE-0 BOUNDED CPU DEV PILOT COMPLETE ===")
    print(f"PID={os.getpid()} | Wall={summary['wall_time_s']}s | Summary SHA={sha256_file(sum_path)}")
    print(
        f"POOLED (N={n_pool}, ev={int(np.sum(y_pool))}): "
        f"SimpleLagEns={summary['pooled_dev_val']['metrics']['Simple_LagEns']['brier']:.5f} | "
        f"LR Base={summary['pooled_dev_val']['metrics']['L2_LogReg_Base']['brier']:.5f} "
        f"Cand={summary['pooled_dev_val']['metrics']['L2_LogReg_Cand']['brier']:.5f} "
        f"dB={real_delta_pool_lr:+.5f} CI={summary['pooled_dev_val']['delta_brier_bootstrap']['L2_LogReg_Cand_vs_Base']} "
        f"p_plac={p_plac_pool_lr:.4f}"
    )
    print(
        f"HGB POOLED: "
        f"Base={summary['pooled_dev_val']['metrics']['HGB_Base']['brier']:.5f} "
        f"Cand={summary['pooled_dev_val']['metrics']['HGB_Cand']['brier']:.5f} "
        f"dB={real_delta_pool_hgb:+.5f} CI={summary['pooled_dev_val']['delta_brier_bootstrap']['HGB_Cand_vs_Base']} "
        f"p_plac={p_plac_pool_hgb:.4f}"
    )
    print("GATE:", summary["prespecified_conjunctive_gate"])


if __name__ == "__main__":
    main()
