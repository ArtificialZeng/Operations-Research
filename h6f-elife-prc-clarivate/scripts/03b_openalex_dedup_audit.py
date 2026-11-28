"""Step 3b: OpenAlex Citing-Work ID Deduplication & Multi-DOI Manifestation Audit.

Audits a stratified random sample of N = 200 multi-DOI mature 2023-2024 eLife PRC
manuscripts (60 VoR v1<Solid, 60 VoR v1 Solid+, 40 Non-VoR v1<Solid, 40 Non-VoR
v1 Solid+; deterministic seed = 20261128) across ALL registered Crossref eLife
version DOIs (v1, v2, ..., VoR) plus the linked bioRxiv/medRxiv preprint DOI.

For every audited manuscript, resolves all DOIs to distinct OpenAlex Work IDs,
retrieves EVERY citing-work OpenAlex ID (with publication_year) for each resolved
Work ID via polite rate-limited API requests, and compares:
  1. Exact deduplicated citing-work ID union (eLife-only & All-manifestations)
  2. Yearly-max proxy across DOI variants (exact same OpenAlex timestamp)
  3. Naive sum across DOI variants (quantifying double-counting inflation)
  4. Frozen-snapshot yearly-max proxy parity & PPML regression impact.

Outputs:
  - data/openalex_citing_dedup_audit.json (cached article-level audit records)
  - results/03b_openalex_dedup_audit.json (summary metrics, correlations, ratios,
    overlap rates, and PPML regression sensitivity)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
from scipy import stats

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = BASE_DIR / "data"
RES_DIR = BASE_DIR / "results"
MAILTO = "zijianzeng@foxmail.com"
UA = f"H6fScientometricsV4Audit/1.0 (mailto:{MAILTO})"
SEED = 20261128
STRATA_TARGETS = {
    (1, 1): 60,  # VoR, v1 <Solid
    (1, 0): 60,  # VoR, v1 Solid+
    (0, 1): 40,  # Non-VoR, v1 <Solid
    (0, 0): 40,  # Non-VoR, v1 Solid+
}


def sha256_bytes(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json_lf(path: Path, obj: object) -> str:
    txt = json.dumps(obj, indent=2, ensure_ascii=False) + "\n"
    path.write_bytes(txt.encode("utf-8"))
    return sha256_bytes(path)


def oa_get(sess: requests.Session, url: str, params: dict) -> dict:
    p = dict(params)
    p["mailto"] = MAILTO
    for attempt in range(5):
        try:
            r = sess.get(url, params=p, timeout=30)
            if r.status_code == 200:
                return r.json()
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(1.5 * (attempt + 1))
                continue
            return {"error_status": r.status_code, "results": []}
        except (requests.RequestException, ValueError):
            time.sleep(1.5 * (attempt + 1))
    return {"error_status": -1, "results": []}


def fetch_citing_ids_for_work(sess: requests.Session, wid: str, max_pages: int = 12) -> dict[str, int]:
    """Fetch all citing OpenAlex Work IDs -> publication_year for a single Work ID."""
    citing: dict[str, int] = {}
    cursor = "*"
    for _ in range(max_pages):
        data = oa_get(
            sess,
            "https://api.openalex.org/works",
            {
                "filter": f"cites:{wid}",
                "select": "id,publication_year",
                "per-page": 200,
                "cursor": cursor,
            },
        )
        results = data.get("results") or []
        for item in results:
            cid = str(item.get("id") or "").rsplit("/", 1)[-1]
            yr = item.get("publication_year")
            if cid and yr is not None:
                citing[cid] = int(yr)
        nxt = (data.get("meta") or {}).get("next_cursor")
        if not nxt or len(results) < 200:
            break
        cursor = nxt
        time.sleep(0.08)
    return citing


def run_simple_ppml(df: pd.DataFrame, y_col: str, x_cols: list[str], fe_col: str, cluster_col: str) -> dict:
    """Subject-clustered PPML with FE dummies on the audit sample."""
    cols = list(dict.fromkeys([y_col] + list(x_cols) + [fe_col, cluster_col]))
    sub = df[cols].dropna().copy()
    sub = sub[sub[y_col] >= 0].copy()
    sub = sub[sub.groupby(fe_col)[y_col].transform("sum") > 0].copy()
    vc = sub[fe_col].value_counts()
    sub = sub[sub[fe_col].isin(vc[vc >= 2].index)].copy()
    fe_d = pd.get_dummies(sub[fe_col], prefix="fe", drop_first=False, dtype=float)
    X = pd.concat([sub[x_cols].astype(float), fe_d], axis=1)
    y = sub[y_col].astype(float)
    glm = sm.GLM(y, X, family=sm.families.Poisson()).fit(
        cov_type="cluster",
        cov_kwds={"groups": sub[cluster_col], "use_correction": True},
        maxiter=120,
    )
    G = int(sub[cluster_col].nunique())
    df_t = max(G - 1, 1)
    t_crit = float(stats.t.ppf(0.975, df=df_t))
    b = float(glm.params["v1_incomp"])
    se = float(glm.bse["v1_incomp"])
    lo, hi = b - t_crit * se, b + t_crit * se
    tval = b / se if se > 0 else float("nan")
    pval = float(2.0 * stats.t.sf(abs(tval), df=df_t))
    return {
        "n": len(sub),
        "G": G,
        "converged": bool(glm.converged),
        "beta": round(b, 5),
        "se": round(se, 5),
        "pct": round(float(100.0 * (np.exp(b) - 1.0)), 2),
        "pct_ci95_lo": round(float(100.0 * (np.exp(lo) - 1.0)), 2),
        "pct_ci95_hi": round(float(100.0 * (np.exp(hi) - 1.0)), 2),
        "t": round(float(tval), 3),
        "p": pval,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true", help="Re-query OpenAlex even if cache exists")
    args = parser.parse_args()

    t0 = time.time()
    cache_path = DATA_DIR / "openalex_citing_dedup_audit.json"
    print("=== STEP 3B: OPENALEX CITING-WORK ID DEDUPLICATION AUDIT (N=200 STRATIFIED) ===", flush=True)

    cr = pd.DataFrame(json.loads((DATA_DIR / "crossref_elife_2023_2026.json").read_bytes()))
    v1_map = json.loads((DATA_DIR / "elife_v1_assessments.json").read_bytes())
    panel = pd.read_csv(DATA_DIR / "h6f_boost_v1_panel.csv.gz", dtype={"eid": str}, parse_dates=["v1_date", "fin_date"])

    cr_v1_auth = cr[(cr["type"] == "posted-content") & (cr["ver"] == 1)].groupby("eid")["n_authors"].first()
    cr_dois = cr.groupby("eid")["doi"].apply(lambda s: sorted(set(s.str.lower()))).to_dict()

    mat = panel[panel["v1_date"].dt.year.isin([2023, 2024]) & panel["v1_str_min"].notna()].copy()
    mat["v1_n_authors"] = mat["eid"].map(cr_v1_auth).astype(float)
    mat["v1_primary_subject"] = mat["eid"].map(lambda e: (v1_map.get(e, {}).get("v1_subjects") or [None])[0]).fillna(mat["primary_subject"])
    mat["v1_incomp_int"] = mat["v1_str_min"].le(2).astype(int)
    mat["n_cr_dois"] = mat["eid"].map(lambda e: len(cr_dois.get(e, [])))

    # Select deterministic stratified sample (N = 200)
    rng = np.random.default_rng(SEED)
    sampled_rows = []
    for (is_vor, is_inc), target_n in STRATA_TARGETS.items():
        pool = mat[(mat["is_vor"] == is_vor) & (mat["v1_incomp_int"] == is_inc) & (mat["n_cr_dois"] >= 2)].sort_values("eid")
        pick_idx = rng.choice(len(pool), size=min(target_n, len(pool)), replace=False)
        sampled_rows.append(pool.iloc[np.sort(pick_idx)])
    sample_df = pd.concat(sampled_rows, ignore_index=True)

    records: list[dict] = []
    if cache_path.exists() and not args.force:
        cached = json.loads(cache_path.read_bytes().decode("utf-8"))
        if len(cached) == len(sample_df) and {r["eid"] for r in cached} == set(sample_df["eid"]):
            records = cached
            print(f"[Cache Hit] Loaded {len(records)} audited multi-DOI articles from {cache_path.name}", flush=True)

    if not records:
        sess = requests.Session()
        sess.headers.update({"User-Agent": UA})
        for idx, row in sample_df.iterrows():
            eid = str(row["eid"])
            v1_yr = int(row["v1_date"].year)
            elife_dois = list(cr_dois.get(eid, []))
            pdoi = str(row["preprint_doi"]).lower().strip() if pd.notna(row["preprint_doi"]) and row["preprint_doi"] else ""
            all_dois = list(dict.fromkeys(elife_dois + ([pdoi] if pdoi else [])))

            # Query OpenAlex for all manifestations of this manuscript
            flt = "|".join(f"https://doi.org/{d}" for d in all_dois)
            res = oa_get(
                sess,
                "https://api.openalex.org/works",
                {
                    "filter": f"doi:{flt}",
                    "select": "id,doi,publication_year,cited_by_count,counts_by_year,type",
                    "per-page": 50,
                },
            )
            works = res.get("results") or []
            # Deduplicate works by OpenAlex Work ID
            uniq_works: dict[str, dict] = {}
            for w in works:
                wid = str(w.get("id") or "").rsplit("/", 1)[-1]
                if wid:
                    uniq_works[wid] = w

            elife_wids: list[str] = []
            preprint_wids: list[str] = []
            for wid, w in uniq_works.items():
                wdoi = str(w.get("doi") or "").lower().replace("https://doi.org/", "")
                if re.match(rf"^10\.7554/elife\.{re.escape(eid)}(\.\d+)?$", wdoi):
                    elife_wids.append(wid)
                elif pdoi and wdoi == pdoi:
                    preprint_wids.append(wid)
                else:
                    # OpenAlex sometimes canonicalizes to another DOI when merging; classify via prefix
                    if wdoi.startswith("10.7554/elife."):
                        elife_wids.append(wid)
                    else:
                        preprint_wids.append(wid)

            # Fetch exact citing-work IDs per distinct OpenAlex Work ID
            citing_by_wid: dict[str, dict[str, int]] = {}
            cby_from_ids: dict[str, dict[int, int]] = {}
            for wid, w in uniq_works.items():
                cb_count = int(w.get("cited_by_count") or 0)
                if cb_count == 0:
                    citing_by_wid[wid] = {}
                    cby_from_ids[wid] = {}
                else:
                    cmap = fetch_citing_ids_for_work(sess, wid)
                    citing_by_wid[wid] = cmap
                    ymap: dict[int, int] = defaultdict(int)
                    for cyr in cmap.values():
                        ymap[cyr] += 1
                    cby_from_ids[wid] = dict(ymap)
                time.sleep(0.08)

            def summarize_group(
                wids: list[str],
                c_by_wid: dict[str, dict[str, int]] = citing_by_wid,
                cby_ids: dict[str, dict[int, int]] = cby_from_ids,
                yr_v1: int = v1_yr,
            ) -> dict:
                if not wids:
                    return {
                        "n_works": 0,
                        "union_total": 0,
                        "union_post_v1": 0,
                        "union_next_yr": 0,
                        "ymax_total": 0,
                        "ymax_post_v1": 0,
                        "ymax_next_yr": 0,
                        "sum_total": 0,
                        "sum_post_v1": 0,
                        "sum_next_yr": 0,
                        "overlap_citing_ids": 0,
                    }
                union_map: dict[str, int] = {}
                id_freq: dict[str, int] = defaultdict(int)
                years_present: set[int] = set()
                for w_i in wids:
                    for cid, cyr in c_by_wid[w_i].items():
                        union_map[cid] = cyr
                        id_freq[cid] += 1
                        years_present.add(cyr)
                overlap_ids = sum(1 for c in id_freq.values() if c >= 2)
                ymax_by_yr = {
                    yr: max(cby_ids[w_i].get(yr, 0) for w_i in wids)
                    for yr in years_present
                }
                sum_by_yr = {
                    yr: sum(cby_ids[w_i].get(yr, 0) for w_i in wids)
                    for yr in years_present
                }
                return {
                    "n_works": len(wids),
                    "union_total": len(union_map),
                    "union_post_v1": sum(1 for cyr in union_map.values() if cyr > yr_v1),
                    "union_next_yr": sum(1 for cyr in union_map.values() if cyr == yr_v1 + 1),
                    "ymax_total": int(sum(ymax_by_yr.values())),
                    "ymax_post_v1": int(sum(v for yr, v in ymax_by_yr.items() if yr > yr_v1)),
                    "ymax_next_yr": int(ymax_by_yr.get(yr_v1 + 1, 0)),
                    "sum_total": int(sum(sum_by_yr.values())),
                    "sum_post_v1": int(sum(v for yr, v in sum_by_yr.items() if yr > yr_v1)),
                    "sum_next_yr": int(sum_by_yr.get(yr_v1 + 1, 0)),
                    "overlap_citing_ids": int(overlap_ids),
                }

            all_wids = list(uniq_works.keys())
            rec = {
                "eid": eid,
                "is_vor": int(row["is_vor"]),
                "v1_incomp": int(row["v1_incomp_int"]),
                "v1_year": v1_yr,
                "v1_age_days": float(row["v1_age_days"]),
                "v1_n_authors": float(row["v1_n_authors"]),
                "v1_sig_rank": float(row["v1_sig_rank"]),
                "v1_primary_subject": str(row["v1_primary_subject"]),
                "log1p_pre_before_v1": float(row["log1p_pre_before_v1"]),
                "n_cr_dois": len(elife_dois),
                "has_preprint_doi": int(bool(pdoi)),
                "n_total_queried_dois": len(all_dois),
                "n_resolved_oa_works": len(all_wids),
                "n_elife_oa_works": len(elife_wids),
                "n_preprint_oa_works": len(preprint_wids),
                "frozen_oa_post_v1_cites": float(row["oa_post_v1_cites"]),
                "elife_only": summarize_group(elife_wids),
                "all_manifestations": summarize_group(all_wids),
            }
            records.append(rec)
            if (idx + 1) % 25 == 0 or (idx + 1) == len(sample_df):
                print(
                    f"  Audited {idx + 1:3d}/{len(sample_df)} | last eid={eid} | "
                    f"DOIs={len(all_dois)} -> OA works={len(all_wids)} (eLife={len(elife_wids)}, pre={len(preprint_wids)}) | "
                    f"all union_post={rec['all_manifestations']['union_post_v1']} vs ymax={rec['all_manifestations']['ymax_post_v1']}",
                    flush=True,
                )
            time.sleep(0.08)

        write_json_lf(cache_path, records)
        print(f"[Saved Audit Cache] {cache_path} ({len(records)} articles)", flush=True)

    # Compute exact audit statistics
    adf = pd.DataFrame([
        {
            "eid": r["eid"],
            "is_vor": r["is_vor"],
            "v1_incomp": r["v1_incomp"],
            "v1_year": r["v1_year"],
            "v1_age_days": r["v1_age_days"],
            "log_v1_authors": float(np.log1p(r["v1_n_authors"])),
            "v1_sig_rank": r["v1_sig_rank"],
            "v1_primary_subject": r["v1_primary_subject"],
            "log1p_pre_before_v1": r["log1p_pre_before_v1"],
            "n_cr_dois": r["n_cr_dois"],
            "n_total_queried_dois": r["n_total_queried_dois"],
            "n_resolved_oa_works": r["n_resolved_oa_works"],
            "n_elife_oa_works": r["n_elife_oa_works"],
            "n_preprint_oa_works": r["n_preprint_oa_works"],
            "frozen_oa_post_v1": r["frozen_oa_post_v1_cites"],
            "el_union_post": r["elife_only"]["union_post_v1"],
            "el_ymax_post": r["elife_only"]["ymax_post_v1"],
            "el_sum_post": r["elife_only"]["sum_post_v1"],
            "el_union_next": r["elife_only"]["union_next_yr"],
            "el_ymax_next": r["elife_only"]["ymax_next_yr"],
            "el_overlap": r["elife_only"]["overlap_citing_ids"],
            "all_union_post": r["all_manifestations"]["union_post_v1"],
            "all_ymax_post": r["all_manifestations"]["ymax_post_v1"],
            "all_sum_post": r["all_manifestations"]["sum_post_v1"],
            "all_union_next": r["all_manifestations"]["union_next_yr"],
            "all_ymax_next": r["all_manifestations"]["ymax_next_yr"],
            "all_sum_next": r["all_manifestations"]["sum_next_yr"],
            "all_union_total": r["all_manifestations"]["union_total"],
            "all_ymax_total": r["all_manifestations"]["ymax_total"],
            "all_sum_total": r["all_manifestations"]["sum_total"],
            "all_overlap": r["all_manifestations"]["overlap_citing_ids"],
        }
        for r in records
    ])

    def pair_metrics(u_col: str, p_col: str, s_col: str, sub: pd.DataFrame) -> dict:
        u = sub[u_col].to_numpy(dtype=float)
        p = sub[p_col].to_numpy(dtype=float)
        s = sub[s_col].to_numpy(dtype=float)
        pos = u > 0
        ratios_pu = p[pos] / u[pos] if pos.any() else np.array([1.0])
        ratios_su = s[pos] / u[pos] if pos.any() else np.array([1.0])
        exact_eq_pct = float(100.0 * np.mean(p == u))
        r_pear = float(stats.pearsonr(u, p).statistic) if np.std(u) > 0 and np.std(p) > 0 else float("nan")
        r_spear = float(stats.spearmanr(u, p).statistic) if np.std(u) > 0 and np.std(p) > 0 else float("nan")
        r_log = float(stats.pearsonr(np.log1p(u), np.log1p(p)).statistic) if np.std(u) > 0 and np.std(p) > 0 else float("nan")
        return {
            "n_articles": len(sub),
            "n_positive_union": int(pos.sum()),
            "exact_match_pct": round(exact_eq_pct, 2),
            "pearson_r": round(r_pear, 5),
            "spearman_rho": round(r_spear, 5),
            "log1p_pearson_r": round(r_log, 5),
            "mean_union": round(float(np.mean(u)), 3),
            "mean_ymax": round(float(np.mean(p)), 3),
            "mean_naive_sum": round(float(np.mean(s)), 3),
            "agg_ymax_to_union_ratio": round(float(np.sum(p) / max(np.sum(u), 1.0)), 4),
            "agg_sum_to_union_ratio": round(float(np.sum(s) / max(np.sum(u), 1.0)), 4),
            "median_ymax_to_union_ratio": round(float(np.median(ratios_pu)), 4),
            "p10_ymax_to_union_ratio": round(float(np.percentile(ratios_pu, 10)), 4),
            "mean_ymax_to_union_ratio": round(float(np.mean(ratios_pu)), 4),
            "median_sum_to_union_ratio": round(float(np.median(ratios_su)), 4),
            "max_abs_diff_ymax_vs_union": int(np.max(np.abs(u - p))) if len(u) else 0,
        }

    split_all = adf[adf["n_resolved_oa_works"] >= 2]
    split_elife = adf[adf["n_elife_oa_works"] >= 2]

    # Regression impact on the audited N=200 sample (subject + v1_year FE)
    adf["subj_yr"] = adf["v1_primary_subject"] + "__" + adf["v1_year"].astype(str)
    x_reg = ["v1_incomp", "v1_sig_rank", "v1_age_days", "log_v1_authors", "log1p_pre_before_v1"]
    reg_impact = {
        "all_audit_all_manifest_union_post": run_simple_ppml(adf, "all_union_post", x_reg, "subj_yr", "v1_primary_subject"),
        "all_audit_all_manifest_ymax_post": run_simple_ppml(adf, "all_ymax_post", x_reg, "subj_yr", "v1_primary_subject"),
        "all_audit_all_manifest_sum_post": run_simple_ppml(adf, "all_sum_post", x_reg, "subj_yr", "v1_primary_subject"),
        "all_audit_elife_only_union_post": run_simple_ppml(adf, "el_union_post", x_reg, "subj_yr", "v1_primary_subject"),
        "all_audit_elife_only_ymax_post": run_simple_ppml(adf, "el_ymax_post", x_reg, "subj_yr", "v1_primary_subject"),
        "all_audit_frozen_oa_post": run_simple_ppml(adf, "frozen_oa_post_v1", x_reg, "subj_yr", "v1_primary_subject"),
        "all_audit_all_manifest_union_next_yr": run_simple_ppml(adf, "all_union_next", x_reg, "subj_yr", "v1_primary_subject"),
        "all_audit_all_manifest_ymax_next_yr": run_simple_ppml(adf, "all_ymax_next", x_reg, "subj_yr", "v1_primary_subject"),
    }

    # Check if gap (union - ymax) differs systematically by v1_incomp or is_vor!
    adf["gap_all_post"] = adf["all_union_post"] - adf["all_ymax_post"]
    adf["pct_under_all_post"] = np.where(adf["all_union_post"] > 0, 100.0 * adf["gap_all_post"] / adf["all_union_post"], 0.0)
    by_stratum = {}
    for (iv, inc), grp in adf.groupby(["is_vor", "v1_incomp"]):
        lbl = f"{'VoR' if iv else 'NonVoR'}_{'v1Low' if inc else 'v1SolidPlus'}"
        by_stratum[lbl] = {
            "n": len(grp),
            "n_split_oa_works": int((grp["n_resolved_oa_works"] >= 2).sum()),
            "pct_split_oa_works": round(float(100.0 * (grp["n_resolved_oa_works"] >= 2).mean()), 1),
            "mean_union_post": round(float(grp["all_union_post"].mean()), 2),
            "mean_ymax_post": round(float(grp["all_ymax_post"].mean()), 2),
            "agg_ymax_to_union_ratio": round(float(grp["all_ymax_post"].sum() / max(grp["all_union_post"].sum(), 1.0)), 4),
            "mean_pct_undercount": round(float(grp["pct_under_all_post"].mean()), 2),
        }

    summary = {
        "audit_seed": SEED,
        "n_audited_articles": len(adf),
        "mean_queried_dois_per_article": round(float(adf["n_total_queried_dois"].mean()), 2),
        "n_collapsed_to_single_oa_work": int((adf["n_resolved_oa_works"] == 1).sum()),
        "pct_collapsed_to_single_oa_work": round(float(100.0 * (adf["n_resolved_oa_works"] == 1).mean()), 2),
        "n_split_across_multiple_oa_works_all": len(split_all),
        "pct_split_across_multiple_oa_works_all": round(float(100.0 * len(split_all) / len(adf)), 2),
        "n_split_across_multiple_elife_oa_works": len(split_elife),
        "pct_split_across_multiple_elife_oa_works": round(float(100.0 * len(split_elife) / len(adf)), 2),
        "n_articles_with_duplicate_citing_ids_across_works": int((adf["all_overlap"] > 0).sum()),
        "total_duplicate_citing_ids_across_works": int(adf["all_overlap"].sum()),
        "all_manifestations_post_v1": pair_metrics("all_union_post", "all_ymax_post", "all_sum_post", adf),
        "all_manifestations_next_yr": pair_metrics("all_union_next", "all_ymax_next", "all_sum_next", adf),
        "all_manifestations_total": pair_metrics("all_union_total", "all_ymax_total", "all_sum_total", adf),
        "elife_only_post_v1": pair_metrics("el_union_post", "el_ymax_post", "el_sum_post", adf),
        "split_works_only_all_manifest_post_v1": pair_metrics("all_union_post", "all_ymax_post", "all_sum_post", split_all),
        "frozen_vs_live_elife_post_v1": {
            "pearson_r": round(float(stats.pearsonr(adf["frozen_oa_post_v1"], adf["el_union_post"]).statistic), 5),
            "spearman_rho": round(float(stats.spearmanr(adf["frozen_oa_post_v1"], adf["el_union_post"]).statistic), 5),
            "mean_frozen": round(float(adf["frozen_oa_post_v1"].mean()), 3),
            "mean_live_elife_union": round(float(adf["el_union_post"].mean()), 3),
            "mean_live_all_union": round(float(adf["all_union_post"].mean()), 3),
        },
        "by_stratum": by_stratum,
        "regression_impact_audit_sample": reg_impact,
        "cache_sha256": sha256_bytes(cache_path),
        "elapsed_sec": round(time.time() - t0, 2),
    }

    out_path = RES_DIR / "03b_openalex_dedup_audit.json"
    sha = write_json_lf(out_path, summary)
    print("\n=== AUDIT SUMMARY ===", flush=True)
    print(f"N={summary['n_audited_articles']} | Mean DOIs={summary['mean_queried_dois_per_article']} | "
          f"Single OA Work={summary['n_collapsed_to_single_oa_work']} ({summary['pct_collapsed_to_single_oa_work']}%) | "
          f"Split All={summary['n_split_across_multiple_oa_works_all']} ({summary['pct_split_across_multiple_oa_works_all']}%) | "
          f"Split eLife={summary['n_split_across_multiple_elife_oa_works']} ({summary['pct_split_across_multiple_elife_oa_works']}%)", flush=True)
    am = summary["all_manifestations_post_v1"]
    print(f"All-Manifest Post-v1: Pearson r={am['pearson_r']}, Spearman rho={am['spearman_rho']}, "
          f"Exact match={am['exact_match_pct']}%, Median ymax/union={am['median_ymax_to_union_ratio']}, "
          f"Agg ymax/union={am['agg_ymax_to_union_ratio']}, Agg sum/union={am['agg_sum_to_union_ratio']}", flush=True)
    eo = summary["elife_only_post_v1"]
    print(f"eLife-Only Post-v1:   Pearson r={eo['pearson_r']}, Spearman rho={eo['spearman_rho']}, "
          f"Exact match={eo['exact_match_pct']}%, Median ymax/union={eo['median_ymax_to_union_ratio']}, "
          f"Agg ymax/union={eo['agg_ymax_to_union_ratio']}", flush=True)
    for k, v in reg_impact.items():
        print(f"  PPML {k:38s}: {v['pct']:+6.2f}% [{v['pct_ci95_lo']:+6.2f}%, {v['pct_ci95_hi']:+6.2f}%] p={v['p']:.4g}", flush=True)
    print(f"[DONE STEP 3B] Elapsed {summary['elapsed_sec']}s | SHA-256: {sha}", flush=True)


if __name__ == "__main__":
    main()
