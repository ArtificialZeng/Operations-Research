"""Step 5: Pillars 3 & 4 Econometric Engine.
- Pillar 3: Clarivate Oct 24, 2024 delisting shock — sequential eid submission velocity
  (sentForReview calibration), Quandt-Andrews Sup-Wald structural break in editorial
  acceptance rate, v1 quality invariance, AND expanded N-journal Abadie-Diamond-Hainmueller
  Synthetic Control (exact convex simplex weights, RMSPE-ratio permutation across all N
  journals, Half-Yearly Event Study, LOJO, Placebo-in-Time 2022H2).
- Pillar 4: Two-Phase Asymmetric Global Metric Dependence across 12 major research nations
  (CN, US, GB, DE, FR, NL, ES, IT, IN, JP, CA, CH), external cross-validation against
  eLife's March 17, 2026 official 3-year transparency report (blog 7da92a51), Senior-PI
  (last-author) share trajectories, and DORA-institutionalized vs JIF-codified regime test.
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from scipy import optimize, stats

BASE_DIR = Path(r"D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126")
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"
TBL_DIR = BASE_DIR / "tables"

COMPLETE_PERIODS = [
    "2021H1", "2021H2", "2022H1", "2022H2",
    "2023H1", "2023H2", "2024H1", "2024H2",
    "2025H1", "2025H2", "2026H1",
]
FOCUS_12_COUNTRIES = ["CN", "IT", "ES", "DE", "NL", "US", "JP", "CA", "CH", "IN", "FR", "GB"]

# Official country submission declines published by Rodgers & Pattinson (eLife Blog 7da92a51, March 17, 2026)
ELIFE_BLOG_2026_SUBMISSION_DROP_PCT: dict[str, float] = {
    "GB": -18.0,
    "FR": -23.0,
    "IN": -25.0,
    "US": -40.0,
    "NL": -47.0,
    "DE": -52.0,
    "ES": -54.0,
    "IT": -75.0,
    "CN": -80.0,
}

# Institutional JIF-codification taxonomy grounded in published research-evaluation policy:
# JIF-codified statutory/national promotion metrics: CN (WoS/CAS tiers), IT (ANVUR VQR/ASN), ES (ANECA Sexenios JCR)
# DORA/funder-reformed systems: GB (UKRI/Wellcome/REF), FR (CNRS/ANR), US (HHMI/NIH/NSF), CH (SNSF), NL (NWO), DE (DFG)
REGIME_MAP: dict[str, str] = {
    "CN": "JIF_Codified",
    "IT": "JIF_Codified",
    "ES": "JIF_Codified",
    "GB": "DORA_Reformed",
    "FR": "DORA_Reformed",
    "US": "DORA_Reformed",
    "CH": "DORA_Reformed",
    "NL": "DORA_Reformed",
    "DE": "DORA_Reformed",
    "CA": "DORA_Reformed",
    "IN": "Mixed_Other",
    "JP": "Mixed_Other",
}
COUNTRY_NAMES: dict[str, str] = {
    "CN": "China", "IT": "Italy", "ES": "Spain", "DE": "Germany",
    "NL": "Netherlands", "US": "United States", "JP": "Japan", "CA": "Canada",
    "CH": "Switzerland", "IN": "India", "FR": "France", "GB": "United Kingdom",
}


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_lf(path: Path, obj) -> str:
    txt = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(txt.encode("utf-8"))
    return sha256_bytes(path)


def solve_simplex_sc_weights(
    y_pre: np.ndarray,
    Y0_pre: np.ndarray,
    l2_tiebreak: float = 1e-5,
    al2021_lam: float = 0.0,
    w0: np.ndarray | None = None,
) -> np.ndarray:
    """Exact Abadie-Diamond-Hainmueller convex simplex weights minimizing
    ||y_pre - w @ Y0_pre||^2 / scale + l2_tiebreak * ||w||^2 subject to w >= 0, sum(w) == 1.
    Normalizing the objective by pre-period variance scale guarantees strong numerical
    conditioning and a strictly convex, globally unique exact ADH solution independent
    of optimizer initialization. Optionally adds Abadie & L'Hour (2021) pairwise penalty.
    """
    J = Y0_pre.shape[0]
    scale = max(float(np.mean(Y0_pre ** 2)), 1e-6)
    inv_sc = 1.0 / scale
    pair_d = np.sum((Y0_pre - y_pre[None, :]) ** 2, axis=1)
    cons = {"type": "eq", "fun": lambda w: float(np.sum(w) - 1.0), "jac": lambda w: np.ones(J)}
    bnds = [(0.0, 1.0)] * J

    def loss(w: np.ndarray) -> float:
        d = y_pre - w @ Y0_pre
        val = inv_sc * float(np.dot(d, d)) + float(l2_tiebreak) * float(np.dot(w, w))
        if al2021_lam > 0.0:
            val += inv_sc * float(al2021_lam) * float(np.dot(w, pair_d))
        return val

    def grad(w: np.ndarray) -> np.ndarray:
        d = w @ Y0_pre - y_pre
        g = (2.0 * inv_sc) * (Y0_pre @ d) + 2.0 * float(l2_tiebreak) * w
        if al2021_lam > 0.0:
            g = g + (inv_sc * float(al2021_lam)) * pair_d
        return g

    w_init = np.ones(J) / J if w0 is None else np.asarray(w0, dtype=float)
    opt = optimize.minimize(
        loss, w_init, jac=grad, method="SLSQP", bounds=bnds, constraints=cons,
        options={"ftol": 1e-15, "maxiter": 1000},
    )
    w_out = np.clip(opt.x, 0.0, 1.0)
    s = float(np.sum(w_out))
    return w_out / s if s > 0 else np.ones(J) / J


def synthetic_control_panel(
    piv_df: pd.DataFrame,
    treated_name: str,
    pre_cols: list[str],
    post_cols: list[str],
    compute_lojo: bool = False,
    al2021_lam: float = 0.0,
) -> dict:
    """Exact strictly-convex ADH Synthetic Control + full in-space placebo permutation across ALL N units."""
    units = list(piv_df.index)
    all_cols = pre_cols + post_cols

    def fit_one(target: str, donor_subset: list[str] | None = None) -> dict:
        donors = donor_subset if donor_subset is not None else [u for u in units if u != target]
        y_pre = piv_df.loc[target, pre_cols].to_numpy(dtype=float)
        Y0_pre = piv_df.loc[donors, pre_cols].to_numpy(dtype=float)
        w = solve_simplex_sc_weights(y_pre, Y0_pre, al2021_lam=al2021_lam)
        y_all = piv_df.loc[target, all_cols].to_numpy(dtype=float)
        syn_all = w @ piv_df.loc[donors, all_cols].to_numpy(dtype=float)
        gap = y_all - syn_all
        pre_rmspe = float(np.sqrt(np.mean(gap[: len(pre_cols)] ** 2)))
        post_rmspe = float(np.sqrt(np.mean(gap[len(pre_cols) :] ** 2)))
        ratio = float(post_rmspe / max(pre_rmspe, 1e-6))
        post_mean_gap = float(np.mean(gap[len(pre_cols) :]))
        top_w = sorted(
            [(donors[i], round(float(w[i]), 4)) for i in range(len(donors)) if w[i] >= 0.01],
            key=lambda x: -x[1],
        )
        return {
            "pre_rmspe": pre_rmspe,
            "post_rmspe": post_rmspe,
            "rmspe_ratio": ratio,
            "post_mean_gap": post_mean_gap,
            "weight_sum": float(np.sum(w)),
            "weight_min": float(np.min(w)),
            "weight_max": float(np.max(w)),
            "actual_by_period": {all_cols[i]: round(float(y_all[i]), 4) for i in range(len(all_cols))},
            "synth_by_period": {all_cols[i]: round(float(syn_all[i]), 4) for i in range(len(all_cols))},
            "gap_by_period": {all_cols[i]: round(float(gap[i]), 4) for i in range(len(all_cols))},
            "top_weights": top_w[:8],
        }

    all_fits = {u: fit_one(u) for u in units}
    tr = all_fits[treated_name]

    ratios = sorted([(u, v["rmspe_ratio"]) for u, v in all_fits.items()], key=lambda x: -x[1])
    rank_ratio = next(i + 1 for i, (u, _) in enumerate(ratios) if u == treated_name)

    gaps = sorted([(u, v["post_mean_gap"]) for u, v in all_fits.items()], key=lambda x: x[1])
    rank_gap_low = next(i + 1 for i, (u, _) in enumerate(gaps) if u == treated_name)
    rank_gap_high = len(units) - rank_gap_low + 1

    # Also compute MSPE-filtered placebo rank (Abadie et al. 2010: dropping placebos with pre_rmspe > 5x treated)
    tr_pre_cut = max(tr["pre_rmspe"] * 5.0, 0.10)
    filt_units = [u for u in units if all_fits[u]["pre_rmspe"] <= tr_pre_cut]
    filt_ratios = sorted([(u, all_fits[u]["rmspe_ratio"]) for u in filt_units], key=lambda x: -x[1])
    filt_rank_ratio = next((i + 1 for i, (u, _) in enumerate(filt_ratios) if u == treated_name), rank_ratio)

    out: dict = {
        "treated": tr,
        "n_units": len(units),
        "rmspe_ratio_rank_of_N": int(rank_ratio),
        "p_rmspe_ratio": float(rank_ratio / len(units)),
        "filtered_n_units": len(filt_units),
        "filtered_rmspe_rank": int(filt_rank_ratio),
        "filtered_p_rmspe": float(filt_rank_ratio / max(len(filt_units), 1)),
        "gap_rank_low_of_N": int(rank_gap_low),
        "gap_rank_high_of_N": int(rank_gap_high),
        "p_gap_1sided_low": float(rank_gap_low / len(units)),
        "p_gap_1sided_high": float(rank_gap_high / len(units)),
        "p_gap_2sided": float(2.0 * min(rank_gap_low, rank_gap_high) / len(units)),
        "all_unit_ratios": [
            {
                "journal": u,
                "pre_rmspe": round(all_fits[u]["pre_rmspe"], 5),
                "post_rmspe": round(all_fits[u]["post_rmspe"], 4),
                "rmspe_ratio": round(r, 3),
                "post_mean_gap": round(all_fits[u]["post_mean_gap"], 4),
            }
            for u, r in ratios
        ],
        "all_unit_gaps": {u: v["gap_by_period"] for u, v in all_fits.items()},
    }

    if compute_lojo:
        donors = [u for u in units if u != treated_name]
        lojo_gaps = []
        for drop_u in donors:
            sub_d = [u for u in donors if u != drop_u]
            res_d = fit_one(treated_name, sub_d)
            lojo_gaps.append({"dropped": drop_u, "post_mean_gap": round(res_d["post_mean_gap"], 4), "pre_rmspe": round(res_d["pre_rmspe"], 4)})
        out["sc_lojo_min_gap"] = float(min(x["post_mean_gap"] for x in lojo_gaps))
        out["sc_lojo_max_gap"] = float(max(x["post_mean_gap"] for x in lojo_gaps))
    return out


def rank_did_stat(s: pd.Series, treated: str = "eLife", is_log: bool = True) -> dict:
    el_val = float(s.loc[treated])
    ctl = s.drop(treated)
    diff = el_val - float(ctl.mean())
    sd_ctl = float(ctl.std(ddof=1))
    z = diff / sd_ctl if sd_ctl > 0 else float("nan")
    rank_low = int((s <= el_val).sum())
    rank_high = int((s >= el_val).sum())
    n_u = len(s)
    res: dict = {
        "n_units": n_u,
        "elife_delta": el_val,
        "ctrl_mean_delta": float(ctl.mean()),
        "did": diff,
        "z_vs_ctrl_sd": float(z),
        "rank_low": rank_low,
        "rank_high": rank_high,
        "p_perm_1sided_low": float(rank_low / n_u),
        "p_perm_1sided_high": float(rank_high / n_u),
        "p_perm_2sided": float(min(1.0, 2.0 * min(rank_low, rank_high) / n_u)),
    }
    if is_log:
        res["did_pct"] = float(100.0 * (np.exp(diff) - 1.0))
    return res


def main() -> None:
    t0 = time.time()
    # Import exact fe_ols_cr1 from step 4 cleanly without circular issues
    import sys
    sys.path.insert(0, str(BASE_DIR / "scripts"))
    from importlib import import_module
    step4 = import_module("04_pillar1_2_revision_and_attention")
    fe_ols = step4.fe_ols_cr1

    print("=== STEP 5: PILLARS 3 & 4 (CLARIVATE EXPANDED SYNTHETIC CONTROL, EDITORIAL CUSHIONING & 12-NATION JIF DEPENDENCE) ===", flush=True)
    RES_DIR.mkdir(parents=True, exist_ok=True)
    TBL_DIR.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(DATA_DIR / "h6f_boost_v1_panel.csv.gz")
    df["v1_dt"] = pd.to_datetime(df["v1_date"], errors="coerce")
    df["fin_dt"] = pd.to_datetime(df["fin_date"], errors="coerce")

    jp = pd.read_csv(DATA_DIR / "h6f_boost_journal_panel.csv")
    jp_exp = jp[jp["period"].isin(COMPLETE_PERIODS)].copy()
    jp_c = jp_exp[jp_exp["in_strict_90_panel"] == 1].copy()
    n_journals = int(jp_c["journal"].nunique())
    n_journals_exp = int(jp_exp["journal"].nunique())
    print(
        f"[Expanded Journal Panel] Strict (>=90% every half): N={n_journals} journals ({n_journals-1} donors + eLife) | "
        f"Expanded (mean>=90%, min>=85%): N={n_journals_exp} journals",
        flush=True,
    )

    # =========================================================================
    # PILLAR 3A: SEQUENTIAL eid SUBMISSION VELOCITY, SUP-WALD STRUCTURAL BREAK & v1 QUALITY INVARIANCE
    # =========================================================================
    sfr_rows = json.loads((DATA_DIR / "r2_sent_for_review_sample.json").read_bytes().decode("utf-8"))
    sfr_df = pd.DataFrame(sfr_rows)
    sfr_df["sfr_dt"] = pd.to_datetime(sfr_df["sentForReview"], errors="coerce")
    sfr_df["v1_dt"] = pd.to_datetime(sfr_df["v1_date"], errors="coerce")
    sfr_ok = sfr_df[sfr_df["sfr_dt"].notna()].copy()
    sfr_ok["sfr_ord"] = sfr_ok["sfr_dt"].map(lambda d: d.toordinal())
    sfr_ok["review_days"] = (sfr_ok["v1_dt"] - sfr_ok["sfr_dt"]).dt.days
    spearman_r = stats.spearmanr(sfr_ok["eid_int"], sfr_ok["sfr_ord"])

    sfr_ok = sfr_ok.sort_values("sfr_dt")
    sfr_ok["sfr_q"] = sfr_ok["sfr_dt"].dt.to_period("Q").astype(str)
    q_med = sfr_ok.groupby("sfr_q").agg(
        n=("eid_int", "count"),
        med_eid=("eid_int", "median"),
        med_sfr_ord=("sfr_ord", "median"),
        med_review_days=("review_days", "median"),
    ).reset_index()
    sfr_q_tbl = []
    for i in range(len(q_med)):
        row = q_med.iloc[i].to_dict()
        if i > 0:
            de = q_med.iloc[i]["med_eid"] - q_med.iloc[i - 1]["med_eid"]
            dd = q_med.iloc[i]["med_sfr_ord"] - q_med.iloc[i - 1]["med_sfr_ord"]
            row["est_subs_per_quarter"] = round(float(91.25 * de / max(dd, 1.0)), 1)
        sfr_q_tbl.append(row)

    clar_ord = pd.Timestamp("2024-10-24").toordinal()
    sfr_near = sfr_ok[(sfr_ok["sfr_dt"] >= "2024-08-01") & (sfr_ok["sfr_dt"] <= "2025-01-31")]
    slope_near, int_near = np.polyfit(sfr_near["sfr_ord"], sfr_near["eid_int"], 1)
    eid_at_clar = float(slope_near * clar_ord + int_near)
    bp_clar = int(round(eid_at_clar / 500.0) * 500)

    # Pre-Clarivate (2024Q1-Q3) vs Post-Clarivate (2025Q2-2026Q2) submission velocity drop
    pre_vel = [r["est_subs_per_quarter"] for r in sfr_q_tbl if r["sfr_q"] in ("2024Q1", "2024Q2", "2024Q3") and "est_subs_per_quarter" in r]
    post_vel = [r["est_subs_per_quarter"] for r in sfr_q_tbl if r["sfr_q"] in ("2025Q2", "2025Q3", "2025Q4", "2026Q1", "2026Q2") and "est_subs_per_quarter" in r]
    vel_drop_pct = float(100.0 * (np.mean(post_vel) - np.mean(pre_vel)) / np.mean(pre_vel))

    # 500-eid sequential blocks (eid 87,500 .. 112,000, 49 blocks)
    bins_500 = []
    for lo in range(87500, 112000, 500):
        hi = lo + 500
        blk = df[(df["eid_int"] >= lo) & (df["eid_int"] < hi)]
        bins_500.append({
            "eid_lo": lo,
            "eid_mid": lo + 250,
            "n_rp": len(blk),
            "accept_pct": float(100.0 * len(blk) / 500.0),
            "v1_incomp_pct": float(100.0 * blk["v1_incomp"].mean()) if len(blk) else float("nan"),
            "med_v1_date": str(blk["v1_dt"].median())[:10] if len(blk) else "",
        })
    b500 = pd.DataFrame(bins_500)

    # Endogenous Quandt-Andrews Sup-Wald Structural Break (15% trimming -> 93,000..108,500)
    best_F = -1.0
    best_bp = 0
    bp_curve = []
    y_acc = b500["accept_pct"].to_numpy(dtype=float)
    for bp in range(93000, 109000, 500):
        post_d = (b500["eid_lo"] >= bp).astype(float).to_numpy()
        m_bp = sm.OLS(y_acc, sm.add_constant(post_d)).fit(cov_type="HAC", cov_kwds={"maxlags": 3})
        f_val = float(m_bp.tvalues[1] ** 2)
        bp_curve.append({"bp_eid": bp, "jump_pp": round(float(m_bp.params[1]), 3), "t_hac": round(float(m_bp.tvalues[1]), 3), "F_hac": round(f_val, 2)})
        if f_val > best_F:
            best_F = f_val
            best_bp = bp

    b500["post_clar"] = (b500["eid_lo"] >= bp_clar).astype(float)
    m_clar_hac = sm.OLS(b500["accept_pct"], sm.add_constant(b500["post_clar"])).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
    b_pre = b500[b500["eid_lo"] < bp_clar].copy()
    b_pre["idx"] = np.arange(len(b_pre))
    m_pre_slope = sm.OLS(b_pre["accept_pct"], sm.add_constant(b_pre["idx"])).fit(cov_type="HAC", cov_kwds={"maxlags": 3})

    rng = np.random.default_rng(42)
    obs_jump = float(b500[b500["post_clar"] == 1]["accept_pct"].mean() - b500[b500["post_clar"] == 0]["accept_pct"].mean())
    n_post_b = int(b500["post_clar"].sum())
    vals_acc = b500["accept_pct"].to_numpy()
    null_j = np.empty(5000, dtype=float)
    for b_i in range(5000):
        perm = rng.permutation(vals_acc)
        null_j[b_i] = float(perm[:n_post_b].mean() - perm[n_post_b:].mean())
    p_perm_acc = float((np.sum(np.abs(null_j) >= abs(obs_jump)) + 1) / 5001)

    # Late-block censoring sensitivity (excluding late-2026 blocks eid >= 111k / 110k / 109k)
    acc_censor_sens = []
    for max_eid in (112000, 111000, 110000, 109000):
        sb = b500[b500["eid_lo"] < max_eid].copy()
        ms = sm.OLS(sb["accept_pct"], sm.add_constant(sb["post_clar"])).fit(cov_type="HAC", cov_kwds={"maxlags": 4})
        acc_censor_sens.append({
            "max_eid_excl": max_eid,
            "n_blocks": len(sb),
            "pre_mean_pct": round(float(sb[sb["post_clar"] == 0]["accept_pct"].mean()), 2),
            "post_mean_pct": round(float(sb[sb["post_clar"] == 1]["accept_pct"].mean()), 2),
            "jump_pp": round(float(ms.params["post_clar"]), 2),
            "hac_t": round(float(ms.tvalues["post_clar"]), 2),
            "hac_p": float(ms.pvalues["post_clar"]),
        })

    # Post-Clarivate v1 Quality Invariance (with Subject FE, CR1 SE & WCB!)
    df_q = df[(df["eid_int"] >= 87500) & (df["eid_int"] < 112500) & df["v1_str_min"].notna()].copy()
    df_q["post_clar_eid"] = (df_q["eid_int"] >= bp_clar).astype(float)
    df_q["v1_exact_solid"] = (df_q["v1_str_min"] == 3).astype(float)
    df_q["is_US"] = df_q["countries"].fillna("").str.contains(r"\bUS\b", regex=True).astype(float)
    df_q["is_CN"] = df_q["countries"].fillna("").str.contains(r"\bCN\b", regex=True).astype(float)
    df_q["is_GB"] = df_q["countries"].fillna("").str.contains(r"\bGB\b", regex=True).astype(float)

    v1_quality_shift = {}
    for yv in ("v1_incomp", "v1_exact_solid", "v1_str_rank", "v1_sig_rank"):
        v1_quality_shift[yv] = {
            "base_subj_fe": fe_ols(df_q, yv, ["post_clar_eid"], "primary_subject", "primary_subject", wcb_target="post_clar_eid"),
            "ctrl_geo_subj_fe": fe_ols(df_q, yv, ["post_clar_eid", "is_US", "is_CN", "is_GB"], "primary_subject", "primary_subject", wcb_target="post_clar_eid"),
        }

    print(
        f"[Pillar 3A Editorial Cushioning] Spearman(eid,sfr)={spearman_r.statistic:.4f} | "
        f"Subs velocity drop={vel_drop_pct:.1f}% ({np.mean(pre_vel):.0f} -> {np.mean(post_vel):.0f}/Q) | "
        f"Accept jump: {b_pre['accept_pct'].mean():.2f}% -> {b500[b500['post_clar']==1]['accept_pct'].mean():.2f}% "
        f"({m_clar_hac.params['post_clar']:+.2f} pp, HAC t={m_clar_hac.tvalues['post_clar']:+.2f}, Perm p={p_perm_acc:.4f}, Sup-Wald F={best_F:.2f}) | "
        f"v1_incomp shift={100*v1_quality_shift['v1_incomp']['base_subj_fe']['params']['post_clar_eid']['beta']:+.2f} pp "
        f"(p={v1_quality_shift['v1_incomp']['base_subj_fe']['params']['post_clar_eid']['p']:.3f})",
        flush=True,
    )

    # =========================================================================
    # PILLAR 3B: EXPANDED N-JOURNAL SYNTHETIC CONTROL, EVENT STUDY, TWO-PHASE DiD, LOJO & PLACEBO-IN-TIME
    # =========================================================================
    pre_21_22 = ["2021H1", "2021H2", "2022H1", "2022H2"]
    prc_23_24 = ["2023H2", "2024H1", "2024H2"]
    pre_all_clean = pre_21_22 + prc_23_24  # excludes 2023H1 legacy seam
    post_clar = ["2025H1", "2025H2", "2026H1"]

    sc_results: dict = {}
    did_results: dict = {}
    lojo_did_results: dict = {}
    event_study_results: dict = {}
    placebo_time_results: dict = {}

    for oc in ["log_n_all", "log_n_CN", "log_n_US", "log_n_GB", "sh_CN", "sh_US", "sh_GB"]:
        is_log = oc.startswith("log_")
        piv = jp_c.pivot(index="journal", columns="period", values=oc)

        # Normalize to pre-period mean so convex simplex matches levels & dynamics cleanly across journal scales!
        piv_clar = piv.sub(piv[prc_23_24].mean(axis=1), axis=0)
        piv_tot = piv.sub(piv[pre_21_22].mean(axis=1), axis=0)
        piv_full = piv.sub(piv[pre_all_clean].mean(axis=1), axis=0)
        piv_pt = piv.sub(piv[["2021H1", "2021H2", "2022H1"]].mean(axis=1), axis=0)

        sc_clar = synthetic_control_panel(piv_clar, "eLife", prc_23_24, post_clar, compute_lojo=True)
        sc_tot = synthetic_control_panel(piv_tot, "eLife", pre_21_22, post_clar, compute_lojo=True)
        sc_full = synthetic_control_panel(piv_full, "eLife", pre_all_clean, post_clar, compute_lojo=False)
        sc_pt = synthetic_control_panel(piv_pt, "eLife", ["2021H1", "2021H2", "2022H1"], ["2022H2"], compute_lojo=False)
        sc_al21 = synthetic_control_panel(piv_clar, "eLife", prc_23_24, post_clar, compute_lojo=False, al2021_lam=0.05)

        # Also run on Expanded N=35 panel (mean>=90%, min>=85%) for exact sensitivity!
        piv_e = jp_exp.pivot(index="journal", columns="period", values=oc)
        piv_e_clar = piv_e.sub(piv_e[prc_23_24].mean(axis=1), axis=0)
        piv_e_tot = piv_e.sub(piv_e[pre_21_22].mean(axis=1), axis=0)
        piv_e_full = piv_e.sub(piv_e[pre_all_clean].mean(axis=1), axis=0)
        sc_clar_exp35 = synthetic_control_panel(piv_e_clar, "eLife", prc_23_24, post_clar, compute_lojo=False)
        sc_tot_exp35 = synthetic_control_panel(piv_e_tot, "eLife", pre_21_22, post_clar, compute_lojo=False)
        sc_full_exp35 = synthetic_control_panel(piv_e_full, "eLife", pre_all_clean, post_clar, compute_lojo=False)

        sc_results[oc] = {
            "sc_clarivate_vs_23_24": sc_clar,
            "sc_total_vs_21_22": sc_tot,
            "sc_full_pre_clarivate": sc_full,
            "sc_clarivate_al2021": sc_al21,
            "sc_clarivate_exp35": sc_clar_exp35,
            "sc_total_exp35": sc_tot_exp35,
            "sc_full_pre_exp35": sc_full_exp35,
        }
        placebo_time_results[oc] = {
            "placebo_2022H2_gap": sc_pt["treated"]["post_mean_gap"],
            "placebo_2022H2_rmspe_rank": sc_pt["rmspe_ratio_rank_of_N"],
            "placebo_2022H2_p_rmspe": sc_pt["p_rmspe_ratio"],
            "placebo_2022H2_p_gap_2sided": sc_pt["p_gap_2sided"],
        }

        # Exact Two-Phase DiD across all N journals
        pre21 = piv[["2021H1", "2021H2"]].mean(axis=1)
        pre22 = piv[["2022H1", "2022H2"]].mean(axis=1)
        m_pre = piv[pre_21_22].mean(axis=1)
        m_prc = piv[prc_23_24].mean(axis=1)
        m_post = piv[post_clar].mean(axis=1)

        did_results[oc] = {
            "pretrend_2022_vs_2021": rank_did_stat(pre22 - pre21, is_log=is_log),
            "phase1_prc_23H2_24H2_vs_21_22": rank_did_stat(m_prc - m_pre, is_log=is_log),
            "phase2_clarivate_25H1_26H1_vs_23H2_24H2": rank_did_stat(m_post - m_prc, is_log=is_log),
            "total_25H1_26H1_vs_21_22": rank_did_stat(m_post - m_pre, is_log=is_log),
        }

        # Leave-One-Journal-Out (LOJO) on Phase-2 Clarivate DiD
        d_cl = m_post - m_prc
        el_v = float(d_cl.loc["eLife"])
        ctrls = [j for j in d_cl.index if j != "eLife"]
        lojo_vals = [el_v - float(d_cl.drop(["eLife", dj]).mean()) for dj in ctrls]
        lojo_did_results[oc] = {
            "full_did": el_v - float(d_cl.drop("eLife").mean()),
            "min_did": float(min(lojo_vals)),
            "max_did": float(max(lojo_vals)),
        }

        # Half-Yearly Event Study (base = 2022H2)
        base_s = piv["2022H2"]
        es_per = {}
        for pcol in COMPLETE_PERIODS:
            diff_p = piv[pcol] - base_s
            el_p = float(diff_p.loc["eLife"])
            ct_p = diff_p.drop("eLife")
            rk_lo = int((diff_p <= el_p).sum())
            rk_hi = int((diff_p >= el_p).sum())
            es_per[pcol] = {
                "elife_val": round(float(piv.loc["eLife", pcol]), 4),
                "ctrl_mean": round(float(piv.drop("eLife")[pcol].mean()), 4),
                "did_vs_2022H2": round(el_p - float(ct_p.mean()), 4),
                "ctrl_sd": round(float(ct_p.std(ddof=1)), 4),
                "rank_low": rk_lo,
                "rank_high": rk_hi,
                "p_2sided": round(float(min(1.0, 2.0 * min(rk_lo, rk_hi) / len(diff_p))), 4),
            }
        event_study_results[oc] = es_per

        print(
            f"  [SC {oc:10s}] Strict(N={sc_clar['n_units']}) ClarSC gap={sc_clar['treated']['post_mean_gap']:+.3f} "
            f"(RMSPE rk={sc_clar['rmspe_ratio_rank_of_N']}/{sc_clar['n_units']}, p={sc_clar['p_rmspe_ratio']:.4f}; "
            f"FullPre rk={sc_full['rmspe_ratio_rank_of_N']}/{sc_full['n_units']}, p={sc_full['p_rmspe_ratio']:.4f}) | "
            f"Exp35 ClarSC gap={sc_clar_exp35['treated']['post_mean_gap']:+.3f} (rk={sc_clar_exp35['rmspe_ratio_rank_of_N']}/{sc_clar_exp35['n_units']}, p={sc_clar_exp35['p_rmspe_ratio']:.4f}; "
            f"FullPre rk={sc_full_exp35['rmspe_ratio_rank_of_N']}/{sc_full_exp35['n_units']}, p={sc_full_exp35['p_rmspe_ratio']:.4f}) | "
            f"PT22H2 p={sc_pt['p_rmspe_ratio']:.2f}",
            flush=True,
        )

    # =========================================================================
    # PILLAR 4: 12-NATION JIF-DEPENDENCE ELASTICITY, BLOG CROSS-VALIDATION & SENIOR-PI SHARES
    # =========================================================================
    country_panel_res = []
    for cc in FOCUS_12_COUNTRIES:
        # Filter to clean donor journals with >=5 mean half-year papers from country cc in 2021-2024 to avoid log(1) zero-count distortion!
        sub_c = jp_c.copy()
        piv_n = sub_c.pivot(index="journal", columns="period", values=f"n_{cc}")
        valid_j = [j for j in piv_n.index if j == "eLife" or float(piv_n.loc[j, pre_21_22 + prc_23_24].mean()) >= 5.0]
        piv_log = sub_c[sub_c["journal"].isin(valid_j)].pivot(index="journal", columns="period", values=f"log_n_{cc}")
        piv_sh = sub_c.pivot(index="journal", columns="period", values=f"sh_{cc}")

        p1_log = rank_did_stat(piv_log[prc_23_24].mean(axis=1) - piv_log[pre_21_22].mean(axis=1), is_log=True)
        p2_log = rank_did_stat(piv_log[post_clar].mean(axis=1) - piv_log[prc_23_24].mean(axis=1), is_log=True)
        tot_log = rank_did_stat(piv_log[post_clar].mean(axis=1) - piv_log[pre_21_22].mean(axis=1), is_log=True)
        p1_sh = rank_did_stat(piv_sh[prc_23_24].mean(axis=1) - piv_sh[pre_21_22].mean(axis=1), is_log=False)
        p2_sh = rank_did_stat(piv_sh[post_clar].mean(axis=1) - piv_sh[prc_23_24].mean(axis=1), is_log=False)

        # Raw eLife country half-year means
        el_n_21_22 = float(piv_n.loc["eLife", pre_21_22].mean())
        el_n_23_24 = float(piv_n.loc["eLife", prc_23_24].mean())
        el_n_25_26 = float(piv_n.loc["eLife", post_clar].mean())
        el_sh_21_22 = float(piv_sh.loc["eLife", pre_21_22].mean())
        el_sh_23_24 = float(piv_sh.loc["eLife", prc_23_24].mean())
        el_sh_25_26 = float(piv_sh.loc["eLife", post_clar].mean())

        rec = {
            "country_code": cc,
            "country_name": COUNTRY_NAMES[cc],
            "regime": REGIME_MAP[cc],
            "n_journals_log_panel": len(valid_j),
            "elife_mean_n_21_22": round(el_n_21_22, 1),
            "elife_mean_n_23_24": round(el_n_23_24, 1),
            "elife_mean_n_25_26": round(el_n_25_26, 1),
            "elife_sh_21_22_pct": round(el_sh_21_22, 2),
            "elife_sh_23_24_pct": round(el_sh_23_24, 2),
            "elife_sh_25_26_pct": round(el_sh_25_26, 2),
            "phase1_log_did": round(p1_log["did"], 4),
            "phase1_pct_did": round(p1_log["did_pct"], 2),
            "phase1_sh_did_pp": round(p1_sh["did"], 2),
            "phase2_log_did": round(p2_log["did"], 4),
            "phase2_pct_did": round(p2_log["did_pct"], 2),
            "phase2_rank_low": int(p2_log["rank_low"]),
            "phase2_p_2sided": round(p2_log["p_perm_2sided"], 4),
            "phase2_sh_did_pp": round(p2_sh["did"], 2),
            "phase2_sh_rank_low": int(p2_sh["rank_low"]),
            "phase2_sh_rank_high": int(p2_sh["rank_high"]),
            "total_log_did": round(tot_log["did"], 4),
            "total_pct_did": round(tot_log["did_pct"], 2),
            "blog_2026_sub_drop_pct": ELIFE_BLOG_2026_SUBMISSION_DROP_PCT.get(cc, np.nan),
        }
        country_panel_res.append(rec)

    c_df = pd.DataFrame(country_panel_res).sort_values("phase2_log_did").reset_index(drop=True)
    print("\n[Pillar 4: 12-Nation Phase-1 (PRC) vs Phase-2 (Clarivate IF Delisting) DiD Spectrum]:", flush=True)
    for _, r in c_df.iterrows():
        blg = f"{r['blog_2026_sub_drop_pct']:+5.0f}%" if pd.notna(r["blog_2026_sub_drop_pct"]) else "   N/A"
        print(
            f"  {r['country_code']} ({r['regime']:13s}) | Sh: {r['elife_sh_21_22_pct']:4.1f}%->{r['elife_sh_23_24_pct']:4.1f}%->{r['elife_sh_25_26_pct']:4.1f}% | "
            f"P1_log={r['phase1_log_did']:+.3f} | P2_log={r['phase2_log_did']:+.3f} ({r['phase2_pct_did']:+5.1f}%, rk={int(r['phase2_rank_low'])}/{int(r['n_journals_log_panel'])}) | "
            f"P2_sh={r['phase2_sh_did_pp']:+5.2f}pp | BlogSub={blg}",
            flush=True,
        )

    # External Ground-Truth Calibration against eLife March 17, 2026 Blog (9 overlapping countries!)
    ov = c_df[c_df["blog_2026_sub_drop_pct"].notna()].copy()
    r_pear = stats.pearsonr(ov["phase2_pct_did"], ov["blog_2026_sub_drop_pct"])
    r_spear = stats.spearmanr(ov["phase2_pct_did"], ov["blog_2026_sub_drop_pct"])

    # Regime test: JIF_Codified (CN, IT, ES) vs DORA_Reformed (GB, FR, US, CH, NL, DE, CA)
    jif_g = c_df[c_df["regime"] == "JIF_Codified"]["phase2_log_did"].to_numpy()
    dora_g = c_df[c_df["regime"] == "DORA_Reformed"]["phase2_log_did"].to_numpy()
    mw_u = stats.mannwhitneyu(jif_g, dora_g, alternative="less")
    welch_t = stats.ttest_ind(jif_g, dora_g, equal_var=False)
    # Exact permutation p-value across all C(10,3)=120 splits!
    from itertools import combinations
    comb_vals = np.concatenate([jif_g, dora_g])
    obs_diff_reg = float(np.mean(jif_g) - np.mean(dora_g))
    all_diffs = []
    n_jif = len(jif_g)
    for idxs in combinations(range(len(comb_vals)), n_jif):
        m_a = np.mean([comb_vals[i] for i in idxs])
        m_b = np.mean([comb_vals[i] for i in range(len(comb_vals)) if i not in idxs])
        all_diffs.append(m_a - m_b)
    p_exact_reg_1sided = float(np.mean(np.array(all_diffs) <= obs_diff_reg))
    p_exact_reg_2sided = float(np.mean(np.abs(all_diffs) >= abs(obs_diff_reg)))

    print(
        f"\n[External Validation vs eLife March 2026 Blog (N=9 countries)]: Pearson r={r_pear.statistic:.4f} (p={r_pear.pvalue:.4g}) | "
        f"Spearman rho={r_spear.statistic:.4f} (p={r_spear.pvalue:.4g})",
        flush=True,
    )
    print(
        f"[Institutional Regime Test (JIF-Codified CN/IT/ES vs DORA-Reformed 7 nations)]: "
        f"Mean P2_log JIF={np.mean(jif_g):+.3f} ({100*(np.exp(np.mean(jif_g))-1):+.1f}%) vs "
        f"DORA={np.mean(dora_g):+.3f} ({100*(np.exp(np.mean(dora_g))-1):+.1f}%) | "
        f"Diff={obs_diff_reg:+.3f} | Exact Comb Perm 1-sided p={p_exact_reg_1sided:.4f} (2-sided p={p_exact_reg_2sided:.4f}, MW-U p={mw_u.pvalue:.4f})",
        flush=True,
    )

    # Senior/Last-Author PI Country Shares Inside eLife PRC (2023H2-2026H1)
    prc_geo = df[df["v1_dt"].notna() & (df["v1_dt"] >= "2023-07-01") & (df["v1_dt"] <= "2026-06-30")].copy()
    prc_geo["v1_half"] = prc_geo["v1_dt"].dt.year.astype(str) + np.where(prc_geo["v1_dt"].dt.month <= 6, "H1", "H2")
    pi_geo = {}
    for per, g in sorted(prc_geo.groupby("v1_half")):
        lc = g["last_countries"].fillna("")
        has_lc = g[lc != ""]
        pi_geo[per] = {
            "n_has_last_geo": len(has_lc),
            "pi_US_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\bUS\b", regex=True).mean()), 2),
            "pi_CN_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\bCN\b", regex=True).mean()), 2),
            "pi_GB_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\bGB\b", regex=True).mean()), 2),
            "pi_DE_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\bDE\b", regex=True).mean()), 2),
            "pi_FR_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\bFR\b", regex=True).mean()), 2),
            "pi_IT_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\bIT\b", regex=True).mean()), 2),
            "pi_ES_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\bES\b", regex=True).mean()), 2),
            "pi_EU_pct": round(float(100.0 * has_lc["last_countries"].str.contains(r"\b(?:DE|FR|CH|NL|SE|ES|IT|DK|BE|AT)\b", regex=True).mean()), 2),
            "pi_GlobalSouth_exCN_pct": round(float(100.0 * (~has_lc["last_countries"].str.contains(r"\b(?:US|GB|CA|AU|NZ|JP|KR|SG|IL|DE|FR|CH|NL|SE|ES|IT|DK|BE|AT|NO|FI|CN)\b", regex=True)).mean()), 2),
        }

    # =========================================================================
    # SAVE PUBLICATION CSV TABLES (ZERO NaN!)
    # =========================================================================
    # Table 3: Expanded Synthetic Control & Two-Phase DiD Summary (zero degenerate ratios!)
    t3_rows = []
    for oc in ["log_n_all", "log_n_CN", "log_n_US", "log_n_GB", "sh_CN", "sh_US", "sh_GB"]:
        sc_c = sc_results[oc]["sc_clarivate_vs_23_24"]
        sc_t = sc_results[oc]["sc_total_vs_21_22"]
        sc_f = sc_results[oc]["sc_full_pre_clarivate"]
        sc_e35 = sc_results[oc]["sc_clarivate_exp35"]
        sc_f35 = sc_results[oc]["sc_full_pre_exp35"]
        d_p1 = did_results[oc]["phase1_prc_23H2_24H2_vs_21_22"]
        d_p2 = did_results[oc]["phase2_clarivate_25H1_26H1_vs_23H2_24H2"]
        pt = placebo_time_results[oc]
        lj = lojo_did_results[oc]
        t3_rows.append({
            "outcome": oc,
            "n_journals_strict": int(sc_c["n_units"]),
            "phase1_prc_did": round(d_p1["did"], 4),
            "phase2_clar_did": round(d_p2["did"], 4),
            "phase2_did_rank_low": int(d_p2["rank_low"]),
            "phase2_did_p_2sided": round(d_p2["p_perm_2sided"], 4),
            "sc_clar_post_gap": round(sc_c["treated"]["post_mean_gap"], 4),
            "sc_clar_pre_rmspe": round(sc_c["treated"]["pre_rmspe"], 5),
            "sc_clar_post_rmspe": round(sc_c["treated"]["post_rmspe"], 4),
            "sc_clar_gap_rank_low": int(sc_c["gap_rank_low_of_N"]),
            "sc_clar_rmspe_rank": int(sc_c["rmspe_ratio_rank_of_N"]),
            "sc_clar_p_rmspe": round(sc_c["p_rmspe_ratio"], 4),
            "sc_fullpre_post_gap": round(sc_f["treated"]["post_mean_gap"], 4),
            "sc_fullpre_gap_rank_low": int(sc_f["gap_rank_low_of_N"]),
            "sc_fullpre_rmspe_rank": int(sc_f["rmspe_ratio_rank_of_N"]),
            "sc_fullpre_p_rmspe": round(sc_f["p_rmspe_ratio"], 4),
            "sc_exp35_clar_gap": round(sc_e35["treated"]["post_mean_gap"], 4),
            "sc_exp35_clar_gap_rank_low": int(sc_e35["gap_rank_low_of_N"]),
            "sc_exp35_clar_rmspe_rank": int(sc_e35["rmspe_ratio_rank_of_N"]),
            "sc_exp35_clar_p_rmspe": round(sc_e35["p_rmspe_ratio"], 4),
            "sc_exp35_fullpre_p_rmspe": round(sc_f35["p_rmspe_ratio"], 4),
            "sc_total_vs21_gap": round(sc_t["treated"]["post_mean_gap"], 4),
            "sc_total_rmspe_rank": int(sc_t["rmspe_ratio_rank_of_N"]),
            "sc_lojo_min": round(sc_c["sc_lojo_min_gap"], 4),
            "sc_lojo_max": round(sc_c["sc_lojo_max_gap"], 4),
            "did_lojo_min": round(lj["min_did"], 4),
            "did_lojo_max": round(lj["max_did"], 4),
            "placebo_2022H2_gap": round(pt["placebo_2022H2_gap"], 4),
            "placebo_2022H2_p": round(pt["placebo_2022H2_p_rmspe"], 4),
        })
    t3_path = TBL_DIR / "table3_synthetic_control_and_editorial.csv"
    pd.DataFrame(t3_rows).to_csv(t3_path, index=False, lineterminator="\n")

    # Table 4: 12-Nation Global JIF-Dependence Elasticity (clean string "Not reported" so zero NaN!)
    t4_df = c_df.copy()
    t4_df["blog_2026_sub_drop_label"] = t4_df["blog_2026_sub_drop_pct"].apply(
        lambda v: f"{v:.0f}%" if pd.notna(v) else "Not reported"
    )
    t4_df = t4_df.drop(columns=["blog_2026_sub_drop_pct"])
    t4_path = TBL_DIR / "table4_global_country_elasticity.csv"
    t4_df.to_csv(t4_path, index=False, lineterminator="\n")

    out_obj = {
        "n_clean_journals_panel": n_journals,
        "pillar3a_editorial_cushioning": {
            "n_sfr_sample": len(sfr_ok),
            "spearman_eid_sfr_r": float(spearman_r.statistic),
            "spearman_eid_sfr_p": float(spearman_r.pvalue),
            "interpolated_eid_at_2024_10_24": eid_at_clar,
            "clarivate_bp_eid_used": bp_clar,
            "review_days_pre_med": float(sfr_ok[sfr_ok["sfr_dt"] < "2024-10-24"]["review_days"].median()),
            "review_days_post_med": float(sfr_ok[sfr_ok["sfr_dt"] >= "2024-10-24"]["review_days"].median()),
            "pre_vel_mean_subs_q": float(np.mean(pre_vel)),
            "post_vel_mean_subs_q": float(np.mean(post_vel)),
            "vel_drop_pct": vel_drop_pct,
            "sfr_quarterly_velocity": sfr_q_tbl,
            "sup_wald_best_F_hac": best_F,
            "sup_wald_best_eid": best_bp,
            "acc_pre_mean_pct": float(b_pre["accept_pct"].mean()),
            "acc_post_mean_pct": float(b500[b500["post_clar"] == 1]["accept_pct"].mean()),
            "acc_jump_pp": float(m_clar_hac.params["post_clar"]),
            "acc_jump_hac_se": float(m_clar_hac.bse["post_clar"]),
            "acc_jump_hac_t": float(m_clar_hac.tvalues["post_clar"]),
            "acc_jump_hac_p": float(m_clar_hac.pvalues["post_clar"]),
            "acc_jump_perm_p": p_perm_acc,
            "acc_late_block_censoring_sensitivity": acc_censor_sens,
            "pre_acc_slope_pp_per_500": float(m_pre_slope.params["idx"]),
            "pre_acc_slope_p": float(m_pre_slope.pvalues["idx"]),
            "blocks_500": bins_500,
            "sup_wald_curve": bp_curve,
            "v1_quality_shift": v1_quality_shift,
        },
        "pillar3b_expanded_sc_and_did": {
            "synthetic_control": sc_results,
            "two_phase_did": did_results,
            "lojo_did": lojo_did_results,
            "event_study_2021H1_2026H1": event_study_results,
            "placebo_in_time_2022H2": placebo_time_results,
        },
        "pillar4_global_metric_dependence": {
            "country_12_panel": c_df.replace({np.nan: None}).to_dict("records"),
            "external_validation_blog_9nations": {
                "n_countries": len(ov),
                "pearson_r": float(r_pear.statistic),
                "pearson_p": float(r_pear.pvalue),
                "spearman_rho": float(r_spear.statistic),
                "spearman_p": float(r_spear.pvalue),
            },
            "institutional_regime_test": {
                "jif_codified_countries": ["CN", "IT", "ES"],
                "dora_reformed_countries": ["GB", "FR", "US", "CH", "NL", "DE", "CA"],
                "jif_mean_p2_log_did": float(np.mean(jif_g)),
                "jif_mean_p2_pct": float(100.0 * (np.exp(np.mean(jif_g)) - 1.0)),
                "dora_mean_p2_log_did": float(np.mean(dora_g)),
                "dora_mean_p2_pct": float(100.0 * (np.exp(np.mean(dora_g)) - 1.0)),
                "diff_log": obs_diff_reg,
                "welch_t": float(welch_t.statistic),
                "welch_p": float(welch_t.pvalue),
                "mannwhitney_p_1sided": float(mw_u.pvalue),
                "exact_comb_perm_p_1sided": p_exact_reg_1sided,
                "exact_comb_perm_p_2sided": p_exact_reg_2sided,
            },
            "senior_pi_last_author_shares": pi_geo,
        },
        "tables_sha256": {
            t3_path.name: sha256_bytes(t3_path),
            t4_path.name: sha256_bytes(t4_path),
        },
        "elapsed_sec": round(time.time() - t0, 2),
    }
    sha = write_json_lf(RES_DIR / "05_pillar3_4_results.json", out_obj)
    print(f"[DONE STEP 5] Elapsed {out_obj['elapsed_sec']}s | SHA-256: {sha}", flush=True)


if __name__ == "__main__":
    main()
