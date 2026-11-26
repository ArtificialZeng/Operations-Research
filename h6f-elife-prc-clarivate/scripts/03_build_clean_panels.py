"""Step 3: Assemble unified zero-VoR-contamination True-v1 Longitudinal Panel
(N = 4,541 true-v1 PRC papers + live monthly eLife page-views & downloads on
mature 2023-2024 cohorts) AND the expanded 36-45 journal clean OpenAlex
16-country benchmark panel (2021H1-2026H1).
"""
from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(r"D:\AI_Science\antigravity\h6f_boost_elife_prc_clarivate_20261126")
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"

SIG_RANK = {"useful": 1, "valuable": 2, "important": 3, "fundamental": 4, "landmark": 5}
STR_RANK = {"inadequate": 1, "incomplete": 2, "solid": 3, "convincing": 4, "compelling": 5, "exceptional": 6}
COUNTRIES = [
    "US", "CN", "GB", "DE", "FR", "NL", "ES", "IT",
    "IN", "JP", "CA", "CH", "AU", "BR", "KR", "SE",
]
COMPLETE_PERIODS = [
    "2021H1", "2021H2", "2022H1", "2022H2",
    "2023H1", "2023H2", "2024H1", "2024H2",
    "2025H1", "2025H2", "2026H1",
]


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_lf(path: Path, obj) -> str:
    txt = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(txt.encode("utf-8"))
    return sha256_bytes(path)


def parse_rank(val_list, rank_map: dict[str, int]) -> tuple[list[str], float, float]:
    if not val_list:
        return [], float("nan"), float("nan")
    vals = [str(v).strip().lower() for v in val_list if str(v).strip().lower() in rank_map]
    if not vals:
        return [], float("nan"), float("nan")
    ranks = [rank_map[v] for v in vals]
    return vals, float(min(ranks)), float(np.mean(ranks))


def ym_to_int(ym: str) -> int | None:
    if not ym or len(ym) < 7 or ym[4] != "-":
        return None
    y, m = ym[:4], ym[5:7]
    if not (y.isdigit() and m.isdigit()):
        return None
    return int(y) * 12 + (int(m) - 1)


# Verified live API rolling window: api.elifesciences.org/metrics/article/{eid}/*?by=month
# returns a 37-month rolling window (2023-11..2026-11). Months before 2023-11 are absent
# from `periods` (though included in `totalValue`), and 2026-11 is a partial observation month.
API_METRICS_MIN_YM = "2023-11"
API_METRICS_MAX_COMPLETE_YM = "2026-10"


def summarize_monthly_metrics(rec: dict, v1_ym: str, fin_ym: str, is_vor: int) -> dict:
    """Compute untruncated cumulative totals AND strictly untruncated monthly metrics.

    CRITICAL ANTI-TRUNCATION INVARIANT:
    - Lifetime `pv_total` and `dl_total` (`totalValue`) are untruncated for 100% of mature papers.
    - Monthly series (`periods`) begin at `2023-11`. Any article with `v1_ym < 2023-11` is
      left-truncated in `periods`, so `first_3m`, `pre_vor`, and `rate_pre_vor` MUST be `NaN`
      rather than silently imputed as zero!
    - For local VoR event-study windows `[fin_m - 3, fin_m + 6]`, we require all 10 monthly
      observations to lie strictly inside `[2023-12, 2026-10]` AND `fin_m - v1_m >= 4` so
      `t = -3..-1` excludes the `v1` launch month and `2026-11` partial-month truncation.
    - For balanced 22-month post-`v1` trajectories (`tau = 0..21`), we require `v1_ym >= 2023-11`
      and `v1_m + 21 <= 2026-10` (satisfied by 100% of `2023-11..2024-12` `v1` cohorts).
    """
    if not rec or rec.get("pv_status") != 200 or rec.get("dl_status") != 200:
        return {"has_metrics": 0, "has_complete_monthly_metrics": 0, "has_clean_vor_ev": 0}

    v1_m = ym_to_int(v1_ym)
    fin_m = ym_to_int(fin_ym) if is_vor == 1 else None
    min_api_m = ym_to_int(API_METRICS_MIN_YM)
    max_comp_m = ym_to_int(API_METRICS_MAX_COMPLETE_YM)
    assert min_api_m is not None and max_comp_m is not None

    complete_monthly = int(v1_m is not None and v1_m >= min_api_m)
    clean_vor_ev = int(
        fin_m is not None
        and v1_m is not None
        and (fin_m - 3) >= (min_api_m + 1)  # >= 2023-12 (strictly post API start month)
        and (fin_m + 6) <= max_comp_m       # <= 2026-10 (strictly pre partial 2026-11)
        and (fin_m - v1_m) >= 4             # >= 4m gap so t=-3..-1 is post v1 launch month
    )

    out: dict = {
        "has_metrics": 1,
        "has_complete_monthly_metrics": complete_monthly,
        "has_clean_vor_ev": clean_vor_ev,
        "pv_total": float(rec.get("pv_total") or 0),
        "dl_total": float(rec.get("dl_total") or 0),
    }

    for prefix in ("pv", "dl"):
        periods = rec.get(f"{prefix}_periods") or []
        pmap: dict[int, float] = {}
        for item in periods:
            pm = ym_to_int(str(item.get("p", "")))
            if pm is not None:
                pmap[pm] = float(item.get("v") or 0)

        # 1. Balanced 22-month post-v1 horizon (ONLY for untruncated v1_ym >= 2023-11!)
        if complete_monthly == 1 and v1_m is not None and (v1_m + 21) <= max_comp_m:
            m0_2 = float(sum(pmap.get(v1_m + k, 0.0) for k in range(3)))
            m3_11 = float(sum(pmap.get(v1_m + k, 0.0) for k in range(3, 12)))
            m12_21 = float(sum(pmap.get(v1_m + k, 0.0) for k in range(12, 22)))
            out[f"{prefix}_first_3m"] = m0_2
            out[f"{prefix}_first_12m"] = m0_2 + m3_11
            out[f"{prefix}_m0_2"] = m0_2
            out[f"{prefix}_m3_11"] = m3_11
            out[f"{prefix}_m12_21"] = m12_21
        else:
            out[f"{prefix}_first_3m"] = float("nan")
            out[f"{prefix}_first_12m"] = float("nan")
            out[f"{prefix}_m0_2"] = float("nan")
            out[f"{prefix}_m3_11"] = float("nan")
            out[f"{prefix}_m12_21"] = float("nan")

        # 2. Pre-vs-Post VoR monthly rates (STRICTLY untruncated v1 >= 2023-11, complete months <= 2026-10!)
        if complete_monthly == 1 and fin_m is not None and v1_m is not None and fin_m <= max_comp_m:
            n_m_pre = max(fin_m - v1_m, 0)
            n_m_post = max(max_comp_m - fin_m + 1, 1)
            n_m_post_strict = max(max_comp_m - fin_m, 0)
            pre_vor = float(sum(pmap.get(m, 0.0) for m in range(v1_m, fin_m)))
            post_vor = float(sum(pmap.get(m, 0.0) for m in range(fin_m, max_comp_m + 1)))
            post_vor_strict = float(sum(pmap.get(m, 0.0) for m in range(fin_m + 1, max_comp_m + 1)))
            post_vor_6m = float(sum(pmap.get(fin_m + k, 0.0) for k in range(6))) if (fin_m + 5) <= max_comp_m else float("nan")
            post_vor_12m = float(sum(pmap.get(fin_m + k, 0.0) for k in range(12))) if (fin_m + 11) <= max_comp_m else float("nan")
            out[f"{prefix}_pre_vor"] = pre_vor if n_m_pre > 0 else float("nan")
            out[f"{prefix}_post_vor"] = post_vor
            out[f"{prefix}_post_vor_strict"] = post_vor_strict if n_m_post_strict > 0 else float("nan")
            out[f"{prefix}_post_vor_6m"] = post_vor_6m
            out[f"{prefix}_post_vor_12m"] = post_vor_12m
            out[f"{prefix}_rate_pre_vor"] = pre_vor / n_m_pre if n_m_pre > 0 else float("nan")
            out[f"{prefix}_rate_post_vor"] = post_vor / n_m_post
            out[f"{prefix}_rate_post_vor_strict"] = post_vor_strict / n_m_post_strict if n_m_post_strict > 0 else float("nan")
            out["n_months_pre_vor"] = float(n_m_pre)
            out["n_months_post_vor"] = float(n_m_post)
        else:
            out[f"{prefix}_pre_vor"] = float("nan")
            out[f"{prefix}_post_vor"] = float("nan")
            out[f"{prefix}_post_vor_strict"] = float("nan")
            out[f"{prefix}_post_vor_6m"] = float("nan")
            out[f"{prefix}_post_vor_12m"] = float("nan")
            out[f"{prefix}_rate_pre_vor"] = float("nan")
            out[f"{prefix}_rate_post_vor"] = float("nan")
            out[f"{prefix}_rate_post_vor_strict"] = float("nan")

        # 3. Clean untruncated local event study around VoR month (t = -3..+6)
        if clean_vor_ev == 1 and fin_m is not None:
            pre3 = float(np.mean([pmap.get(fin_m + k, 0.0) for k in (-3, -2, -1)]))
            m0 = float(pmap.get(fin_m, 0.0))
            p13 = float(np.mean([pmap.get(fin_m + k, 0.0) for k in (1, 2, 3)]))
            p16 = float(np.mean([pmap.get(fin_m + k, 0.0) for k in (1, 2, 3, 4, 5, 6)]))
            p46 = float(np.mean([pmap.get(fin_m + k, 0.0) for k in (4, 5, 6)]))
            out[f"{prefix}_ev_pre3"] = pre3
            out[f"{prefix}_ev_m0"] = m0
            out[f"{prefix}_ev_p13"] = p13
            out[f"{prefix}_ev_p16"] = p16
            out[f"{prefix}_ev_p46"] = p46
            out[f"dlog_{prefix}_ev_m0"] = float(np.log1p(m0) - np.log1p(pre3))
            out[f"dlog_{prefix}_ev_p13"] = float(np.log1p(p13) - np.log1p(pre3))
            out[f"dlog_{prefix}_ev_p16"] = float(np.log1p(p16) - np.log1p(pre3))
            out[f"dlog_{prefix}_ev_p46"] = float(np.log1p(p46) - np.log1p(pre3))
            for k in range(-3, 7):
                out[f"dlog_{prefix}_ev_t{k}"] = float(np.log1p(pmap.get(fin_m + k, 0.0)) - np.log1p(pre3))
        else:
            for nm in (
                f"{prefix}_ev_pre3", f"{prefix}_ev_m0", f"{prefix}_ev_p13", f"{prefix}_ev_p16", f"{prefix}_ev_p46",
                f"dlog_{prefix}_ev_m0", f"dlog_{prefix}_ev_p13", f"dlog_{prefix}_ev_p16", f"dlog_{prefix}_ev_p46",
            ):
                out[nm] = float("nan")
            for k in range(-3, 7):
                out[f"dlog_{prefix}_ev_t{k}"] = float("nan")
    return out


def build_v1_longitudinal_panel() -> tuple[pd.DataFrame, dict]:
    """Assemble the complete 4,541-paper true-v1 panel with zero VoR-date leakage."""
    prc_items = json.loads((DATA_DIR / "elife_prc_search_census.json").read_bytes().decode("utf-8"))
    v1_map = json.loads((DATA_DIR / "elife_v1_assessments.json").read_bytes().decode("utf-8"))
    cr_rows = json.loads((DATA_DIR / "crossref_elife_2023_2026.json").read_bytes().decode("utf-8"))
    oa_elife = json.loads((DATA_DIR / "openalex_elife_prc_dois.json").read_bytes().decode("utf-8"))
    oa_pre = json.loads((DATA_DIR / "openalex_preprint_dois.json").read_bytes().decode("utf-8"))

    metrics_map: dict[str, dict] = {}
    metrics_path = DATA_DIR / "elife_article_metrics_2023_2024.jsonl"
    if metrics_path.exists():
        for line in metrics_path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            metrics_map[str(rec["eid"])] = rec

    cr_df = pd.DataFrame(cr_rows)
    cr_agg = cr_df.groupby("eid").agg(
        cr_cites_max=("cited", "max"),
        cr_cites_sum=("cited", "sum"),
        cr_n_versions=("ver", "nunique"),
        cr_max_ver=("ver", "max"),
        cr_has_vor=("type", lambda s: int((s == "journal-article").any())),
        cr_v1_date=("pub_date", "min"),
        cr_n_authors=("n_authors", "max"),
    ).reset_index()

    # Index OpenAlex eLife works strictly by eid (merging versioned canonical DOIs!)
    oa_by_eid: dict[str, dict] = {}
    for src_map in (oa_elife, oa_pre):
        for k_doi, rec in src_map.items():
            m_e = re.match(r"^10\.7554/elife\.(\d+)", k_doi)
            if not m_e:
                continue
            ee = m_e.group(1)
            cur = oa_by_eid.get(ee)
            if cur is None:
                oa_by_eid[ee] = dict(rec)
            else:
                cur["cited"] = max(int(cur.get("cited", 0)), int(rec.get("cited", 0)))
                cur["n_authors"] = max(int(cur.get("n_authors", 0)), int(rec.get("n_authors", 0)))
                cur["countries"] = sorted(set((cur.get("countries") or []) + (rec.get("countries") or [])))
                if not cur.get("first_countries") and rec.get("first_countries"):
                    cur["first_countries"] = rec["first_countries"]
                if not cur.get("last_countries") and rec.get("last_countries"):
                    cur["last_countries"] = rec["last_countries"]
                cby = dict(cur.get("counts_by_year") or {})
                for yk, yv in (rec.get("counts_by_year") or {}).items():
                    cby[str(yk)] = max(int(cby.get(str(yk), 0)), int(yv))
                cur["counts_by_year"] = cby

    rows = []
    for it in prc_items:
        eid = str(it["id"]).strip()
        v1 = v1_map.get(eid, {})
        if v1.get("v1_status") != 200:
            continue
        is_vor = 1 if it.get("type") == "research-article" else 0
        ea_fin = it.get("elifeAssessment") or {}
        fin_sig_list, fin_sig_min, fin_sig_mean = parse_rank(ea_fin.get("significance"), SIG_RANK)
        fin_str_list, fin_str_min, fin_str_mean = parse_rank(ea_fin.get("strength"), STR_RANK)
        v1_sig_list, v1_sig_min, v1_sig_mean = parse_rank(v1.get("v1_sig"), SIG_RANK)
        v1_str_list, v1_str_min, v1_str_mean = parse_rank(v1.get("v1_str"), STR_RANK)

        # STRICT TRUE v1 DATE (NEVER VoR date!)
        v1_dt_str = (v1.get("v1_reviewedDate") or v1.get("v1_published") or "")[:10]
        fin_dt_str = (it.get("published") or it.get("statusDate") or "")[:10]
        subjs = [s.get("id") for s in (it.get("subjects") or []) if isinstance(s, dict)]
        if not subjs:
            subjs = v1.get("v1_subjects") or ["unknown"]
        primary_subj = subjs[0]

        oe = oa_by_eid.get(eid, {})
        oa_elife_cites = int(oe.get("cited", 0))
        oa_countries = list(oe.get("countries") or [])
        oa_first_countries = list(oe.get("first_countries") or [])
        oa_last_countries = list(oe.get("last_countries") or [])
        oa_n_authors = int(oe.get("n_authors", 0))

        pdoi = v1.get("v1_preprint_doi") or ""
        op = oa_pre.get(pdoi, {})
        pre_cites_tot = int(op.get("cited", 0))
        v1_yr = int(v1_dt_str[:4]) if len(v1_dt_str) >= 4 and v1_dt_str[:4].isdigit() else None

        cby_elife = dict(oe.get("counts_by_year") or {})
        cby_all = dict(cby_elife)
        for yk, yv in (op.get("counts_by_year") or {}).items():
            cby_all[str(yk)] = max(int(cby_all.get(str(yk), 0)), int(yv))

        pre_cites_before_v1 = 0
        oa_post_v1_cites = 0
        oa_ge_v1_cites = 0
        if v1_yr:
            pre_cites_before_v1 = sum(int(cnt) for ys, cnt in cby_all.items() if str(ys).isdigit() and int(ys) < v1_yr)
            oa_post_v1_cites = sum(int(cnt) for ys, cnt in cby_elife.items() if str(ys).isdigit() and int(ys) > v1_yr)
            oa_ge_v1_cites = sum(int(cnt) for ys, cnt in cby_elife.items() if str(ys).isdigit() and int(ys) >= v1_yr)

        pre_pub_date = op.get("pub_date") or ""
        if not oa_countries and op.get("countries"):
            oa_countries = list(op["countries"])
        if not oa_first_countries and op.get("first_countries"):
            oa_first_countries = list(op["first_countries"])
        if not oa_last_countries and op.get("last_countries"):
            oa_last_countries = list(op["last_countries"])

        m_summary = summarize_monthly_metrics(metrics_map.get(eid, {}), v1_dt_str[:7], fin_dt_str[:7], is_vor)

        row = {
            "eid": eid,
            "eid_int": int(eid) if eid.isdigit() else np.nan,
            "is_vor": is_vor,
            "v1_date": v1_dt_str,
            "fin_date": fin_dt_str,
            "primary_subject": primary_subj,
            "v1_sig_str": "|".join(v1_sig_list),
            "v1_str_str": "|".join(v1_str_list),
            "fin_sig_str": "|".join(fin_sig_list),
            "fin_str_str": "|".join(fin_str_list),
            "v1_sig_rank": v1_sig_mean,
            "v1_str_rank": v1_str_mean,
            "v1_str_min": v1_str_min,
            "fin_sig_rank": fin_sig_mean,
            "fin_str_rank": fin_str_mean,
            "fin_str_min": fin_str_min,
            "v1_incomp": int(v1_str_min <= 2) if pd.notna(v1_str_min) else np.nan,
            "v1_solid": int(v1_str_min == 3) if pd.notna(v1_str_min) else np.nan,
            "fin_incomp": int(fin_str_min <= 2) if pd.notna(fin_str_min) else np.nan,
            "str_upgraded": int(fin_str_min > v1_str_min) if (pd.notna(fin_str_min) and pd.notna(v1_str_min)) else 0,
            "str_upgraded_to_solid": int((v1_str_min <= 2) and (fin_str_min >= 3)) if (pd.notna(fin_str_min) and pd.notna(v1_str_min)) else 0,
            "sig_upgraded": int(fin_sig_min > v1_sig_min) if (pd.notna(fin_sig_min) and pd.notna(v1_sig_min)) else 0,
            "oa_elife_cites": float(oa_elife_cites),
            "oa_post_v1_cites": float(oa_post_v1_cites),
            "oa_ge_v1_cites": float(oa_ge_v1_cites),
            "preprint_doi": pdoi,
            "has_preprint_doi": int(bool(pdoi)),
            "pre_pub_date": pre_pub_date,
            "oa_pre_cites_tot": float(pre_cites_tot),
            "oa_pre_cites_before_v1": float(pre_cites_before_v1),
            "oa_n_authors": oa_n_authors,
            "countries": "|".join(oa_countries),
            "first_countries": "|".join(oa_first_countries),
            "last_countries": "|".join(oa_last_countries),
            "v1_assess_len": int(v1.get("v1_assess_len") or 0),
        }
        row.update(m_summary)
        rows.append(row)

    df = pd.DataFrame(rows).merge(cr_agg, on="eid", how="left")
    df["v1_dt"] = pd.to_datetime(df["v1_date"], errors="coerce")
    df["fin_dt"] = pd.to_datetime(df["fin_date"], errors="coerce")
    df["pre_dt"] = pd.to_datetime(df["pre_pub_date"], errors="coerce")

    ref_dt = pd.Timestamp("2026-11-26")
    df["v1_age_days"] = (ref_dt - df["v1_dt"]).dt.days
    df["rev_lag_days"] = np.where(df["is_vor"] == 1, (df["fin_dt"] - df["v1_dt"]).dt.days, np.nan)
    df["v1_year"] = df["v1_dt"].dt.year
    df["v1_quarter"] = df["v1_dt"].dt.to_period("Q").astype(str)
    df["fin_quarter"] = df["fin_dt"].dt.to_period("Q").astype(str)
    df["v1_half"] = df["v1_year"].astype("Int64").astype(str) + np.where(df["v1_dt"].dt.month <= 6, "H1", "H2")
    df["subj_v1q"] = df["primary_subject"] + "__" + df["v1_quarter"]
    df["subj_finq"] = df["primary_subject"] + "__" + df["fin_quarter"]

    df["cr_cites"] = df["cr_cites_max"].fillna(0).astype(float)
    df["cr_cites_sum"] = df["cr_cites_sum"].fillna(0).astype(float)
    df["cr_plus_pre_cites"] = df["cr_cites"] + df["oa_pre_cites_tot"].fillna(0).astype(float)
    df["oa_plus_pre_cites"] = df["oa_elife_cites"].fillna(0).astype(float) + df["oa_pre_cites_tot"].fillna(0).astype(float)

    df["log1p_cr"] = np.log1p(df["cr_cites"])
    df["log1p_cr_sum"] = np.log1p(df["cr_cites_sum"])
    df["log1p_cr_plus_pre"] = np.log1p(df["cr_plus_pre_cites"])
    df["log1p_oa"] = np.log1p(df["oa_elife_cites"].fillna(0).astype(float))
    df["log1p_oa_post_v1"] = np.log1p(df["oa_post_v1_cites"].fillna(0).astype(float))
    df["log1p_pre_before_v1"] = np.log1p(df["oa_pre_cites_before_v1"].fillna(0).astype(float))
    df["n_authors"] = df["cr_n_authors"].fillna(df["oa_n_authors"]).fillna(5.0).astype(float)
    df["log_authors"] = np.log1p(df["n_authors"])

    # Log transforms for live eLife article metrics (cumulative + untruncated monthly windows)
    for col in [
        "pv_total", "dl_total", "pv_first_3m", "dl_first_3m", "pv_first_12m", "dl_first_12m",
        "pv_m0_2", "pv_m3_11", "pv_m12_21", "dl_m0_2", "dl_m3_11", "dl_m12_21",
        "pv_pre_vor", "dl_pre_vor", "pv_post_vor", "dl_post_vor",
        "pv_post_vor_strict", "dl_post_vor_strict", "pv_post_vor_6m", "dl_post_vor_6m",
        "pv_post_vor_12m", "dl_post_vor_12m",
    ]:
        if col in df.columns:
            df[f"log1p_{col}"] = np.log1p(df[col].clip(lower=0))

    # Within-paper post-vs-pre VoR monthly rate shift (STRICTLY untruncated v1 >= 2023-11!)
    df["delta_log_pv_rate"] = np.log1p(df["pv_rate_post_vor"].clip(lower=0)) - np.log1p(df["pv_rate_pre_vor"].clip(lower=0))
    df["delta_log_dl_rate"] = np.log1p(df["dl_rate_post_vor"].clip(lower=0)) - np.log1p(df["dl_rate_pre_vor"].clip(lower=0))
    df["delta_log_pv_rate_strict"] = np.log1p(df["pv_rate_post_vor_strict"].clip(lower=0)) - np.log1p(df["pv_rate_pre_vor"].clip(lower=0))
    df["delta_log_dl_rate_strict"] = np.log1p(df["dl_rate_post_vor_strict"].clip(lower=0)) - np.log1p(df["dl_rate_pre_vor"].clip(lower=0))

    # Balanced 22-month post-v1 trajectory shifts (tau=3..11 & tau=12..21 vs tau=0..2, untruncated v1 >= 2023-11!)
    df["dlog_pv_3_11_vs_0_2"] = df["log1p_pv_m3_11"] - df["log1p_pv_m0_2"]
    df["dlog_pv_12_21_vs_0_2"] = df["log1p_pv_m12_21"] - df["log1p_pv_m0_2"]
    df["dlog_dl_3_11_vs_0_2"] = df["log1p_dl_m3_11"] - df["log1p_dl_m0_2"]
    df["dlog_dl_12_21_vs_0_2"] = df["log1p_dl_m12_21"] - df["log1p_dl_m0_2"]

    # Strict v1-date alignment & API rolling-window telemetry audit!
    vors = df[df["is_vor"] == 1]
    n_vor_date_before_v1 = int((vors["fin_dt"] < vors["v1_dt"]).sum())
    n_v1_missing = int(df["v1_dt"].isna().sum())
    mat = df[(df["v1_dt"] >= "2023-01-01") & (df["v1_dt"] <= "2024-12-31") & df["v1_str_min"].notna()]
    n_mat_metrics = int((mat["has_metrics"] == 1).sum())
    n_mat_complete_monthly = int((mat["has_complete_monthly_metrics"] == 1).sum())
    n_mat_left_truncated = int((mat["has_metrics"] == 1).sum() - n_mat_complete_monthly)
    n_mat_clean_vor_ev = int((mat["has_clean_vor_ev"] == 1).sum())

    out_gz = DATA_DIR / "h6f_boost_v1_panel.csv.gz"
    df.to_csv(out_gz, index=False, compression="gzip", lineterminator="\n")

    audit = {
        "n_prc_census": len(prc_items),
        "n_v1_recovered_http200": len(df),
        "n_v1_with_strength": int(df["v1_str_min"].notna().sum()),
        "v1_recovery_pct": float(100.0 * df["v1_str_min"].notna().sum() / max(len(prc_items), 1)),
        "n_v1_date_missing": n_v1_missing,
        "n_vors_total": len(vors),
        "n_vors_fin_lt_v1": n_vor_date_before_v1,
        "n_mature_2023_2024": len(mat),
        "n_mature_with_live_metrics": n_mat_metrics,
        "mature_metrics_coverage_pct": float(100.0 * n_mat_metrics / max(len(mat), 1)),
        "api_monthly_min_ym": API_METRICS_MIN_YM,
        "api_monthly_max_complete_ym": API_METRICS_MAX_COMPLETE_YM,
        "n_mature_complete_monthly_ge_2023_11": n_mat_complete_monthly,
        "n_mature_left_truncated_lt_2023_11": n_mat_left_truncated,
        "n_mature_clean_local_vor_event_study": n_mat_clean_vor_ev,
        "panel_gz_sha256": sha256_bytes(out_gz),
    }
    print(
        f"[v1 Panel Built] N={len(df):,} | Mature 2023-2024={len(mat):,} | "
        f"Live Totals={n_mat_metrics:,}/{len(mat):,} ({audit['mature_metrics_coverage_pct']:.2f}%) | "
        f"Untruncated Monthly (v1>=2023-11)={n_mat_complete_monthly:,} (left-trunc={n_mat_left_truncated:,}) | "
        f"Clean VoR Event-Study={n_mat_clean_vor_ev:,} | VoR<v1 anomalies={n_vor_date_before_v1}",
        flush=True,
    )
    return df, audit


def build_expanded_journal_panel(v1_df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """Assemble the clean lag-free expanded 16-country OpenAlex journal panel (2021H1-2026H1)."""
    raw = json.loads((DATA_DIR / "expanded_openalex_panel_2021_2026.json").read_bytes().decode("utf-8"))
    raw_ok = [r for r in raw if not r.get("error")]

    # Separate eLife 2021-2022 OpenAlex baseline from candidate donors
    elife_pre = [r for r in raw_ok if r["journal"] == "eLife" and r["year"] <= 2022]
    donor_rows = [r for r in raw_ok if r["journal"] != "eLife"]

    # Build eLife 2023H1-2026H2_YTD strictly from deduplicated true-v1 PRC census (VoR + RP!)
    prc_geo = v1_df[v1_df["v1_dt"].notna() & (v1_df["v1_dt"] >= "2023-01-01") & (v1_df["v1_dt"] <= "2026-11-25")].copy()
    prc_geo["period"] = np.where(
        (prc_geo["v1_year"] == 2026) & (prc_geo["v1_dt"].dt.month >= 7),
        "2026H2_YTD",
        prc_geo["v1_half"],
    )
    elife_prc_rows = []
    for per, g in sorted(prc_geo.groupby("period")):
        cstr = g["countries"].fillna("")
        rec: dict = {
            "journal": "eLife",
            "issn": "2050-084X",
            "period": per,
            "year": int(per[:4]),
            "half": 2 if "H2" in per else 1,
            "n_all": len(g),
            "n_has_geo": int((cstr != "").sum()),
            "error": False,
        }
        for cc in COUNTRIES:
            rec[f"n_{cc}"] = int(cstr.str.contains(rf"\b{cc}\b", regex=True).sum())
        elife_prc_rows.append(rec)

    all_df = pd.DataFrame(elife_pre + elife_prc_rows + donor_rows)
    comp = all_df[all_df["period"].isin(COMPLETE_PERIODS)].copy()
    comp["geo_cov_pct"] = 100.0 * comp["n_has_geo"] / np.maximum(comp["n_all"], 1)

    # Strict programmatic donor quality filter:
    # Primary strict panel (N=30): all 11 complete half-years (2021H1-2026H1),
    #   min(geo_cov_pct) >= 90.0% in EVERY half-year, min(n_all) >= 25, min/med >= 0.30.
    # Expanded robustness panel (N=35): all 11 half-years, mean(geo_cov_pct) >= 90.0%,
    #   min(geo_cov_pct) >= 85.0%, min(n_all) >= 25, min/med >= 0.30.
    strict_journals = ["eLife"]
    expanded_journals = ["eLife"]
    donor_audit = []
    expanded_only_donors = []
    excluded_donors = []

    for jn, g in sorted(comp[comp["journal"] != "eLife"].groupby("journal")):
        n_per = len(g)
        min_cov = float(g["geo_cov_pct"].min())
        mean_cov = float(g["geo_cov_pct"].mean())
        min_n = int(g["n_all"].min())
        med_n = float(g["n_all"].median())
        max_n = int(g["n_all"].max())
        min_ratio = float(min_n / max(med_n, 1.0))
        rec = {
            "journal": jn,
            "issn": str(g["issn"].iloc[0]),
            "n_periods": n_per,
            "min_geo_cov_pct": round(min_cov, 2),
            "mean_geo_cov_pct": round(mean_cov, 2),
            "min_n_half": min_n,
            "med_n_half": round(med_n, 1),
            "max_n_half": max_n,
            "min_to_med_ratio": round(min_ratio, 3),
        }
        if n_per == 11 and min_cov >= 90.0 and min_n >= 25 and min_ratio >= 0.30:
            strict_journals.append(jn)
            expanded_journals.append(jn)
            donor_audit.append(rec)
        elif n_per == 11 and mean_cov >= 90.0 and min_cov >= 85.0 and min_n >= 25 and min_ratio >= 0.30:
            expanded_journals.append(jn)
            expanded_only_donors.append(rec)
        else:
            reasons = []
            if n_per < 11:
                reasons.append(f"periods={n_per}<11")
            if min_cov < 85.0:
                reasons.append(f"min_geo_cov={min_cov:.1f}%<85%")
            elif min_cov < 90.0 and mean_cov < 90.0:
                reasons.append(f"mean_geo_cov={mean_cov:.1f}%<90%")
            if min_n < 25:
                reasons.append(f"min_n={min_n}<25")
            if min_ratio < 0.30:
                reasons.append(f"indexing_break(min/med={min_ratio:.2f}<0.30)")
            rec["exclude_reason"] = "; ".join(reasons)
            excluded_donors.append(rec)

    jp_clean = all_df[all_df["journal"].isin(expanded_journals)].copy()
    jp_clean["in_strict_90_panel"] = jp_clean["journal"].isin(strict_journals).astype(int)
    jp_clean["in_expanded_85_panel"] = 1
    jp_clean["geo_cov_pct"] = 100.0 * jp_clean["n_has_geo"] / np.maximum(jp_clean["n_all"], 1)
    jp_clean["log_n_all"] = np.log(jp_clean["n_all"].clip(lower=1))
    for cc in COUNTRIES:
        jp_clean[f"sh_{cc}"] = 100.0 * jp_clean[f"n_{cc}"] / np.maximum(jp_clean["n_has_geo"], 1)
        jp_clean[f"log_n_{cc}"] = np.log(jp_clean[f"n_{cc}"].clip(lower=1))
    jp_clean["is_elife"] = (jp_clean["journal"] == "eLife").astype(int)
    jp_clean = jp_clean.sort_values(["journal", "year", "half", "period"]).reset_index(drop=True)

    out_csv = DATA_DIR / "h6f_boost_journal_panel.csv"
    jp_clean.to_csv(out_csv, index=False, lineterminator="\n")

    el_audit = jp_clean[(jp_clean["journal"] == "eLife") & (jp_clean["period"].isin(COMPLETE_PERIODS))]
    audit = {
        "n_clean_donors": len(donor_audit),
        "n_total_journals_with_elife": len(strict_journals),
        "n_expanded_donors": int(len(donor_audit) + len(expanded_only_donors)),
        "n_expanded_journals_with_elife": len(expanded_journals),
        "exact_min_perm_p_1sided": float(1.0 / len(strict_journals)),
        "exact_min_perm_p_2sided": float(2.0 / len(strict_journals)),
        "expanded_min_perm_p_1sided": float(1.0 / len(expanded_journals)),
        "expanded_min_perm_p_2sided": float(2.0 / len(expanded_journals)),
        "elife_min_geo_cov_pct": round(float(el_audit["geo_cov_pct"].min()), 2),
        "elife_mean_geo_cov_pct": round(float(el_audit["geo_cov_pct"].mean()), 2),
        "n_excluded_donors": len(excluded_donors),
        "clean_donors": donor_audit,
        "expanded_only_donors": expanded_only_donors,
        "excluded_donors": excluded_donors,
        "journal_panel_csv_sha256": sha256_bytes(out_csv),
    }
    print(
        f"[Journal Panel Built] Strict (>=90% every half) N={len(strict_journals)} (p_min={audit['exact_min_perm_p_1sided']:.4f}) | "
        f"Expanded (mean>=90%, min>=85%) N={len(expanded_journals)} (p_min={audit['expanded_min_perm_p_1sided']:.4f}) | "
        f"Excluded={len(excluded_donors)}",
        flush=True,
    )
    for ex_r in excluded_donors:
        print(f"  Excluded donor: {ex_r['journal']:38s} -> {ex_r['exclude_reason']}", flush=True)
    return jp_clean, audit


def main() -> None:
    t0 = time.time()
    print("=== STEP 3: BUILD CLEAN TRUE-v1 PANEL & EXPANDED OPENALEX BENCHMARK PANEL ===", flush=True)
    v1_df, v1_audit = build_v1_longitudinal_panel()
    _, jp_audit = build_expanded_journal_panel(v1_df)

    out = {
        "v1_panel_audit": v1_audit,
        "journal_panel_audit": jp_audit,
        "elapsed_sec": round(time.time() - t0, 2),
    }
    sha = write_json_lf(RES_DIR / "03_panel_audit.json", out)
    print(f"[DONE STEP 3] Elapsed {out['elapsed_sec']}s | SHA-256: {sha}", flush=True)


if __name__ == "__main__":
    main()
