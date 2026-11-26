"""Gate #2 (Decisive Journal-Tier Test): Live openFDA Drugs@FDA + Drug Label + FAERS Linkage.

Links all canonical Phase-3 MRCT investigational molecules to:
  1. openFDA Drugs@FDA (https://api.fda.gov/drug/drugsfda.json):
     Originator NDA/BLA identification, original approval date, total supplements,
     post-approval LABELING supplements (total, per year, 3-yr & 5-yr fixed windows),
     EFFICACY supplements (commercial popularity control / placebo outcome), and
     safety/REMS labeling supplements.
  2. openFDA Drug Label (https://api.fda.gov/drug/label.json):
     Boxed warning indicator, warnings_and_cautions length, adverse_reactions length.
  3. openFDA FAERS (https://api.fda.gov/drug/event.json):
     US Primary-Suspect serious vs non-serious adverse event counts AND Global Primary-Suspect
     counts -> US serious share, US non-serious per year, and US-vs-Non-US non-serious reporting
     log-odds ratio.

Tests honestly whether high-EE-share pivotal programs experience higher post-approval safety
label revisions, boxed warnings, or US post-marketing AE surprises — reporting exact empirical
estimates regardless of whether they are positive, nuanced, or null.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
import warnings
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
import statsmodels.api as sm
import statsmodels.formula.api as smf
from scipy import stats

warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=RuntimeWarning)

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")
PROC_DIR = BASE_DIR / "data" / "processed"
FDA_DIR = BASE_DIR / "data" / "raw_openfda"
RES_DIR = BASE_DIR / "results"
TAB_DIR = BASE_DIR / "tables"
FDA_DIR.mkdir(parents=True, exist_ok=True)
RES_DIR.mkdir(parents=True, exist_ok=True)
TAB_DIR.mkdir(parents=True, exist_ok=True)

OPENFDA_BASE = "https://api.fda.gov/drug"
DRUGSFDA_CACHE = FDA_DIR / "drugsfda_cache.json"
LABEL_CACHE = FDA_DIR / "label_cache.json"
FAERS_CACHE = FDA_DIR / "faers_cache.json"

# Pre-approval compound code pattern (never approved under internal alphanumeric code)
CODE_MOL_RE = re.compile(
    r"^(?:[a-z]{1,5}[\s\-_]?\d{3,}[a-z0-9\-]*|\d{3,}[a-z\-]*)$",
    flags=re.IGNORECASE,
)


class OpenFDAClient:
    """Rate-limited, budget-capped openFDA REST client with retry hygiene."""

    def __init__(self, max_requests: int = 920, min_interval_sec: float = 0.28):
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "D30-Boost-Pharmacovigilance-Audit/1.0"})
        self.max_requests = max_requests
        self.min_interval = min_interval_sec
        self.n_requests = 0
        self.last_ts = 0.0

    def get(self, endpoint: str, params: dict[str, str | int]) -> tuple[int, dict | None]:
        if self.n_requests >= self.max_requests:
            raise RuntimeError(f"Reached safety request budget cap ({self.max_requests})")
        url = f"{OPENFDA_BASE}/{endpoint}.json"
        for attempt in range(1, 5):
            dt = time.time() - self.last_ts
            if dt < self.min_interval:
                time.sleep(self.min_interval - dt)
            self.last_ts = time.time()
            self.n_requests += 1
            try:
                r = self.session.get(url, params=params, timeout=30)
                if r.status_code == 200:
                    return 200, r.json()
                if r.status_code == 404:
                    return 404, None
                if r.status_code == 429:
                    wait = min(60, 5 * attempt)
                    print(f"  [429] Rate limited on {endpoint}, sleeping {wait}s...", flush=True)
                    time.sleep(wait)
                    continue
                if r.status_code in (500, 502, 503, 504):
                    time.sleep(2 * attempt)
                    continue
                return r.status_code, None
            except requests.RequestException as exc:
                print(f"  [NET ERR {attempt}] {endpoint}: {exc}", flush=True)
                time.sleep(2 * attempt)
        return 500, None


def parse_fda_date(s: str | None) -> datetime | None:
    if not s or not isinstance(s, str):
        return None
    s = s.strip()
    if len(s) >= 8 and s[:8].isdigit():
        try:
            return datetime.strptime(s[:8], "%Y%m%d")
        except ValueError:
            return None
    return None


def summarize_drugsfda_record(rec: dict) -> dict | None:
    """Extract clean originator NDA/BLA submission & safety-labeling metrics."""
    app_num = (rec.get("application_number") or "").upper()
    if not app_num.startswith(("NDA", "BLA")):
        return None  # Strictly exclude ANDA generics

    subs = rec.get("submissions") or []
    orig_dates = []
    for s in subs:
        if (s.get("submission_type") or "").upper() == "ORIG" and (s.get("submission_status") or "").upper() == "AP":
            dt = parse_fda_date(s.get("submission_status_date"))
            if dt:
                orig_dates.append(dt)
    if not orig_dates:
        # Fallback: earliest approved submission date
        for s in subs:
            if (s.get("submission_status") or "").upper() == "AP":
                dt = parse_fda_date(s.get("submission_status_date"))
                if dt:
                    orig_dates.append(dt)
    if not orig_dates:
        return None
    orig_dt = min(orig_dates)

    n_suppl_total = 0
    n_labeling_suppl = 0
    n_labeling_3yr = 0
    n_labeling_5yr = 0
    n_efficacy_suppl = 0
    n_efficacy_5yr = 0
    n_safety_rems_suppl = 0

    for s in subs:
        stype = (s.get("submission_type") or "").upper()
        sstat = (s.get("submission_status") or "").upper()
        if stype != "SUPPL" or sstat != "AP":
            continue
        sdt = parse_fda_date(s.get("submission_status_date"))
        if sdt and sdt < orig_dt:
            continue
        yrs_after = ((sdt - orig_dt).days / 365.25) if sdt else np.nan
        cls_code = (s.get("submission_class_code") or "").upper()
        cls_desc = (s.get("submission_class_code_description") or "").upper()
        docs_blob = " ".join(
            f"{d.get('type', '')} {d.get('title', '')}" for d in (s.get("application_docs") or [])
        ).upper()

        n_suppl_total += 1
        is_lab = ("LABELING" in cls_code) or ("LABELING" in cls_desc)
        is_eff = ("EFFICACY" in cls_code) or ("EFFICACY" in cls_desc)
        is_saf = any(w in f"{cls_code} {cls_desc} {docs_blob}" for w in ("REMS", "SAFETY", "BOXED", "MEDICATION GUIDE", "RISK EVALUATION"))

        if is_lab:
            n_labeling_suppl += 1
            if not np.isnan(yrs_after) and yrs_after <= 3.0:
                n_labeling_3yr += 1
            if not np.isnan(yrs_after) and yrs_after <= 5.0:
                n_labeling_5yr += 1
        if is_eff:
            n_efficacy_suppl += 1
            if not np.isnan(yrs_after) and yrs_after <= 5.0:
                n_efficacy_5yr += 1
        if is_saf:
            n_safety_rems_suppl += 1

    openfda = rec.get("openfda") or {}
    gnames = [g.upper() for g in (openfda.get("generic_name") or [])]
    bnames = [b.upper() for b in (openfda.get("brand_name") or [])]
    prods = rec.get("products") or []
    active_ings = sorted({
        (ai.get("name") or "").upper()
        for p in prods
        for ai in (p.get("active_ingredients") or [])
        if ai.get("name")
    })

    return {
        "application_number": app_num,
        "is_bla": int(app_num.startswith("BLA")),
        "fda_sponsor": (rec.get("sponsor_name") or "").upper(),
        "orig_approval_date": orig_dt.strftime("%Y-%m-%d"),
        "orig_approval_year": int(orig_dt.year),
        "n_suppl_total": int(n_suppl_total),
        "n_labeling_suppl": int(n_labeling_suppl),
        "n_labeling_3yr": int(n_labeling_3yr),
        "n_labeling_5yr": int(n_labeling_5yr),
        "n_efficacy_suppl": int(n_efficacy_suppl),
        "n_efficacy_5yr": int(n_efficacy_5yr),
        "n_safety_rems_suppl": int(n_safety_rems_suppl),
        "generic_names": gnames[:5],
        "brand_names": bnames[:5],
        "active_ingredients": active_ings[:5],
    }


def match_drugsfda_batch(
    client: OpenFDAClient,
    molecules: list[str],
    cache: dict[str, dict | None],
    refresh_misses: bool = False,
) -> None:
    """Batch-query Drugs@FDA strictly for originator NDA/BLAs, supporting FDA 4-letter biologic suffixes."""
    if refresh_misses:
        todo = [m for m in molecules if (m not in cache) or (cache[m] is None)]
    else:
        todo = [m for m in molecules if m not in cache]
    if not todo:
        print(f"  [CACHE] All {len(molecules)} molecules already in drugsfda_cache.", flush=True)
        return

    print(f"  [Drugs@FDA] Querying {len(todo)} molecules (NDA/BLA filter + biologic-suffix support)...", flush=True)

    def _query_token(m: str) -> str:
        # Single-word alphabetic INN >= 5 chars: use wildcard so "RISANKIZUMAB*" matches "RISANKIZUMAB-RZAA"
        m_up = m.upper()
        if re.fullmatch(r"[A-Z]{5,}", m_up):
            return f"{m_up}*"
        return f'"{m_up}"'

    def fetch_batch(batch: list[str]) -> list[dict]:
        q_parts = [_query_token(m) for m in batch]
        q_str = "(" + " OR ".join(q_parts) + ")"
        # Strictly restrict to NDA* or BLA* so ANDA generics never overflow limit=100!
        search = (
            f"(application_number:NDA* OR application_number:BLA*) "
            f"AND (openfda.generic_name:{q_str} OR products.active_ingredients.name:{q_str})"
        )
        status, data = client.get("drugsfda", {"search": search, "limit": 100})
        if status == 404 or not data:
            return []
        if status != 200:
            if len(batch) > 1:
                mid = len(batch) // 2
                return fetch_batch(batch[:mid]) + fetch_batch(batch[mid:])
            return []
        total = ((data.get("meta") or {}).get("results") or {}).get("total", 0)
        res = data.get("results") or []
        if total > 100 and len(batch) > 1:
            mid = len(batch) // 2
            return fetch_batch(batch[:mid]) + fetch_batch(batch[mid:])
        return res

    batch_size = 8
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        raw_recs = fetch_batch(batch)
        # Parse all originator NDA/BLA records returned in batch
        parsed_recs = [x for r in raw_recs if (x := summarize_drugsfda_record(r)) is not None]
        for m in batch:
            m_up = m.upper()
            # Match molecule strictly by exact generic_name/active_ingredient, salt prefix (" "),
            # OR FDA 4-letter biologic nonproprietary suffix ("-", e.g. "RISANKIZUMAB-RZAA")
            matches = []
            for pr in parsed_recs:
                ing_pool = set(pr["generic_names"]) | set(pr["active_ingredients"])
                exact_hit = (m_up in ing_pool) or any(
                    (g == m_up or g.startswith((m_up + " ", m_up + "-")))
                    for g in ing_pool
                )
                # Exclude multi-ingredient combos if single-ingredient molecule is queried
                is_single_ing = len(pr["active_ingredients"]) <= 1 or (" " in m_up and " AND " in m_up)
                if exact_hit:
                    matches.append((1 if is_single_ing else 0, -pr["orig_approval_year"], pr["n_suppl_total"], pr))
            if matches:
                # Prefer single-ingredient originator with earliest approval date
                matches.sort(key=lambda t: (t[0], t[1], t[2]), reverse=True)
                cache[m] = matches[0][3]
            else:
                cache[m] = None

        if (i // batch_size + 1) % 10 == 0 or (i + batch_size) >= len(todo):
            DRUGSFDA_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            n_hit = sum(1 for v in cache.values() if v is not None)
            print(
                f"    Drugs@FDA progress: {min(i+batch_size, len(todo))}/{len(todo)} | "
                f"matched={n_hit} | api_reqs={client.n_requests}",
                flush=True,
            )


def match_labels_batch(client: OpenFDAClient, app_nums: list[str], cache: dict[str, dict | None]) -> None:
    """Batch-query openFDA drug/label by exact NDA/BLA application_number."""
    todo = [a for a in app_nums if a not in cache]
    if not todo:
        print(f"  [CACHE] All {len(app_nums)} NDA/BLAs already in label_cache.", flush=True)
        return
    print(f"  [Drug/Label] Querying {len(todo)} NDA/BLAs in batches...", flush=True)

    batch_size = 8
    for i in range(0, len(todo), batch_size):
        batch = todo[i : i + batch_size]
        q_str = "(" + " OR ".join(f'"{a}"' for a in batch) + ")"
        status, data = client.get("label", {"search": f"openfda.application_number.exact:{q_str}", "limit": 100})
        recs = (data.get("results") or []) if (status == 200 and data) else []
        by_app: dict[str, dict] = {}
        for r in recs:
            apps = ((r.get("openfda") or {}).get("application_number") or [])
            bw = r.get("boxed_warning") or []
            wc = r.get("warnings_and_cautions") or r.get("warnings") or []
            ar = r.get("adverse_reactions") or []
            bw_text = " ".join(bw) if isinstance(bw, list) else str(bw)
            wc_text = " ".join(wc) if isinstance(wc, list) else str(wc)
            ar_text = " ".join(ar) if isinstance(ar, list) else str(ar)
            info = {
                "has_boxed_warning": int(len(bw_text.strip()) > 10),
                "boxed_warning_chars": len(bw_text),
                "warnings_chars": len(wc_text),
                "adverse_reactions_chars": len(ar_text),
                "effective_time": r.get("effective_time"),
            }
            for a in apps:
                a_up = a.upper()
                if a_up in batch:
                    # Keep latest effective_time record if multiple SPL versions exist
                    prev = by_app.get(a_up)
                    if prev is None or str(info.get("effective_time") or "") > str(prev.get("effective_time") or ""):
                        by_app[a_up] = info
        for a in batch:
            cache[a] = by_app.get(a)
        LABEL_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    n_hit = sum(1 for a in app_nums if cache.get(a) is not None)
    print(f"    Drug/Label done: matched={n_hit}/{len(app_nums)} | api_reqs={client.n_requests}", flush=True)


def fetch_faers_for_molecules(
    client: OpenFDAClient,
    mol_info: list[tuple[str, str, str]],
    cache: dict[str, dict],
) -> None:
    """Query FAERS primary-suspect US and Global serious vs non-serious counts per approved drug.

    mol_info: list of (canonical_mol, fda_generic_name, app_number)
    """
    todo_us = [item for item in mol_info if item[0] not in cache]
    if todo_us:
        print(f"  [FAERS Pass 1 — US Primary-Suspect] Querying {len(todo_us)} drugs...", flush=True)
    for idx, (mol, fda_gen, app_num) in enumerate(todo_us, 1):
        # Query exact application_number first (cleanest linkage, avoids generic/combo bleed!), fallback to generic_name
        q_us = f'patient.drug.openfda.application_number.exact:"{app_num}" AND occurcountry:"US" AND patient.drug.drugcharacterization:1'
        st, d = client.get("event", {"search": q_us, "count": "serious"})
        source_key = "app_num"
        if st != 200 or not d or not d.get("results"):
            q_us_fb = f'patient.drug.openfda.generic_name.exact:"{fda_gen}" AND occurcountry:"US" AND patient.drug.drugcharacterization:1'
            st, d = client.get("event", {"search": q_us_fb, "count": "serious"})
            source_key = "generic_name"

        us_ser, us_non = 0, 0
        if st == 200 and d and d.get("results"):
            for row in d["results"]:
                if row.get("term") == 1:
                    us_ser = int(row.get("count", 0))
                elif row.get("term") == 2:
                    us_non = int(row.get("count", 0))
        cache[mol] = {
            "source_key": source_key,
            "us_serious_n": us_ser,
            "us_nonserious_n": us_non,
            "us_total_n": us_ser + us_non,
            "global_queried": False,
        }
        if idx % 25 == 0 or idx == len(todo_us):
            FAERS_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
            print(f"    FAERS US progress: {idx}/{len(todo_us)} | api_reqs={client.n_requests}", flush=True)

    # Pass 2: Global Primary-Suspect counts (derives Non-US counts by exact subtraction!) within remaining request budget
    todo_gl = [
        item for item in mol_info
        if item[0] in cache and not cache[item[0]].get("global_queried") and cache[item[0]].get("us_total_n", 0) > 0
    ]
    remaining_budget = client.max_requests - client.n_requests
    if todo_gl and remaining_budget >= 20:
        to_run = todo_gl[: max(0, remaining_budget - 10)]
        print(
            f"  [FAERS Pass 2 — Global Primary-Suspect] Querying {len(to_run)}/{len(todo_gl)} drugs "
            f"(remaining budget={remaining_budget})...",
            flush=True,
        )
        for idx, (mol, fda_gen, app_num) in enumerate(to_run, 1):
            src = cache[mol].get("source_key", "app_num")
            if src == "app_num":
                q_gl = f'patient.drug.openfda.application_number.exact:"{app_num}" AND patient.drug.drugcharacterization:1'
            else:
                q_gl = f'patient.drug.openfda.generic_name.exact:"{fda_gen}" AND patient.drug.drugcharacterization:1'
            st, d = client.get("event", {"search": q_gl, "count": "serious"})
            gl_ser, gl_non = 0, 0
            if st == 200 and d and d.get("results"):
                for row in d["results"]:
                    if row.get("term") == 1:
                        gl_ser = int(row.get("count", 0))
                    elif row.get("term") == 2:
                        gl_non = int(row.get("count", 0))
            cache[mol]["global_serious_n"] = gl_ser
            cache[mol]["global_nonserious_n"] = gl_non
            cache[mol]["global_total_n"] = gl_ser + gl_non
            cache[mol]["global_queried"] = True
            if idx % 25 == 0 or idx == len(to_run):
                FAERS_CACHE.write_text(json.dumps(cache, indent=2), encoding="utf-8")
                print(f"    FAERS Global progress: {idx}/{len(to_run)} | api_reqs={client.n_requests}", flush=True)


def run_ols_hc3(df: pd.DataFrame, formula: str, target_terms: list[str]) -> dict:
    """Fit HC3/sponsor-clustered OLS with finite-sample t(G-1) SEs and full-rank verification."""
    cols_needed = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
    reserved = {"C", "np", "log", "log1p", "I"}
    req = [c for c in dict.fromkeys(cols_needed) if c not in reserved and c in df.columns]
    sub = df.dropna(subset=req).copy()
    if len(sub) < 25:
        return {"n": len(sub), "error": "insufficient_n"}
    try:
        mod = smf.ols(formula, data=sub)
        n_cl = int(sub["lead_sponsor"].nunique()) if "lead_sponsor" in sub.columns else 0
        if "lead_sponsor" in sub.columns and n_cl >= 15:
            fit = mod.fit(
                cov_type="cluster",
                cov_kwds={"groups": sub["lead_sponsor"], "df_correction": True},
                use_t=True,
            )
            se_type = "cluster:lead_sponsor"
            t_df = max(1, n_cl - 1)
        else:
            fit = mod.fit(cov_type="HC3", use_t=True)
            se_type = "HC3"
            t_df = max(1, int(fit.df_resid))
    except (ValueError, np.linalg.LinAlgError, KeyError, ZeroDivisionError, RuntimeError) as exc:
        return {"n": len(sub), "error": str(exc)[:180]}
    t_crit = float(stats.t.ppf(0.975, df=t_df))
    t_crit_90 = float(stats.t.ppf(0.95, df=t_df))
    mat_rank = round(float(fit.df_model)) + 1
    out = {
        "n": int(fit.nobs),
        "n_clusters": int(n_cl),
        "n_params": len(fit.params),
        "matrix_rank": mat_rank,
        "is_full_rank": bool(mat_rank == len(fit.params)),
        "use_t": bool(fit.use_t),
        "t_df": int(t_df),
        "r2": round(float(fit.rsquared), 4),
        "se_type": se_type,
        "y_mean": round(float(sub[req[0]].mean()), 4),
        "terms": {},
    }
    for t in target_terms:
        if t in fit.params.index:
            c, s = float(fit.params[t]), float(fit.bse[t])
            if not (np.isfinite(c) and np.isfinite(s) and s > 0):
                continue
            ci95_lo, ci95_hi = c - t_crit * s, c + t_crit * s
            ci90_lo, ci90_hi = c - t_crit_90 * s, c + t_crit_90 * s
            out["terms"][t] = {
                "coef": round(c, 5),
                "se": round(s, 5),
                "t": round(float(fit.tvalues[t]), 3),
                "p": float(fit.pvalues[t]),
                "ci95_lo": round(ci95_lo, 5),
                "ci95_hi": round(ci95_hi, 5),
                "ci90_lo": round(ci90_lo, 5),
                "ci90_hi": round(ci90_hi, 5),
                "tost_90_margin": round(max(abs(ci90_lo), abs(ci90_hi)), 5),
                "excludable_95_abs": round(max(abs(ci95_lo), abs(ci95_hi)), 5),
                "per_10pp_coef": round(0.10 * c, 5),
                "per_10pp_se": round(0.10 * s, 5),
                "per_10pp_ci95_lo": round(0.10 * ci95_lo, 5),
                "per_10pp_ci95_hi": round(0.10 * ci95_hi, 5),
            }
    return out


def run_poisson_cluster(df: pd.DataFrame, formula: str, target_terms: list[str]) -> dict:
    """Fit Poisson GLM (log link) with sponsor-clustered SEs for non-negative supplement counts."""
    cols_needed = re.findall(r"[A-Za-z_][A-Za-z0-9_]*", formula)
    reserved = {"C", "np", "log", "log1p", "I"}
    req = [c for c in dict.fromkeys(cols_needed) if c not in reserved and c in df.columns]
    sub = df.dropna(subset=req).copy()
    if len(sub) < 25:
        return {"n": len(sub), "error": "insufficient_n"}
    try:
        mod = smf.glm(formula, data=sub, family=sm.families.Poisson())
        n_cl = int(sub["lead_sponsor"].nunique()) if "lead_sponsor" in sub.columns else 0
        if "lead_sponsor" in sub.columns and n_cl >= 15:
            fit = mod.fit(cov_type="cluster", cov_kwds={"groups": sub["lead_sponsor"]})
            se_type = "cluster:lead_sponsor"
        else:
            fit = mod.fit(cov_type="HC3")
            se_type = "HC3"
    except (ValueError, np.linalg.LinAlgError, KeyError, ZeroDivisionError, RuntimeError) as exc:
        return {"n": len(sub), "error": str(exc)[:180]}
    out = {
        "n": int(fit.nobs),
        "n_clusters": int(n_cl),
        "model": "Poisson_GLM_log_link",
        "se_type": se_type,
        "y_mean": round(float(sub[req[0]].mean()), 4),
        "terms": {},
    }
    for t in target_terms:
        if t in fit.params.index:
            c, s = float(fit.params[t]), float(fit.bse[t])
            lo95, hi95 = c - 1.96 * s, c + 1.96 * s
            out["terms"][t] = {
                "coef_log_irr": round(c, 5),
                "irr": round(float(np.exp(c)), 4),
                "irr_ci95_lo": round(float(np.exp(lo95)), 4),
                "irr_ci95_hi": round(float(np.exp(hi95)), 4),
                "irr_per_10pp": round(float(np.exp(0.10 * c)), 4),
                "irr_per_10pp_ci95_lo": round(float(np.exp(0.10 * lo95)), 4),
                "irr_per_10pp_ci95_hi": round(float(np.exp(0.10 * hi95)), 4),
                "se": round(s, 5),
                "z": round(float(fit.tvalues[t]), 3),
                "p": float(fit.pvalues[t]),
                "ci95_lo": round(lo95, 5),
                "ci95_hi": round(hi95, 5),
            }
    return out


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--test-batch", action="store_true")
    parser.add_argument("--refresh-misses", action="store_true")
    parser.add_argument("--max-requests", type=int, default=920)
    args = parser.parse_args()

    client = OpenFDAClient(max_requests=args.max_requests, min_interval_sec=0.28)

    if args.test_batch:
        st, d = client.get(
            "drugsfda",
            {"search": '(application_number:NDA* OR application_number:BLA*) AND openfda.generic_name:(DUPILUMAB* OR RISANKIZUMAB* OR SEMAGLUTIDE*)', "limit": 100},
        )
        print(f"[TEST BATCH] status={st} n_results={len((d or {}).get('results', []))}", flush=True)
        return 0

    df_p23 = pd.read_parquet(PROC_DIR / "d30_mrct_placebo_panel.parquet")
    df_p3 = df_p23[(df_p23["is_phase3"] == 1) & (df_p23["primary_molecule"] != "")].copy()

    # Candidate molecules from Phase-3 MRCT universe (excluding pure internal alphanumeric codes)
    all_mols = sorted(df_p3["primary_molecule"].unique().tolist())
    named_mols = [m for m in all_mols if not CODE_MOL_RE.match(m) and len(m) >= 3]
    print(
        f"[START Gate #2] Phase-3 MRCTs={len(df_p3)} | total_unique_mols={len(all_mols)} | "
        f"named_noncode_mols={len(named_mols)}",
        flush=True,
    )

    # Load existing caches if any
    drugsfda_cache: dict[str, dict | None] = json.loads(DRUGSFDA_CACHE.read_text(encoding="utf-8")) if DRUGSFDA_CACHE.exists() else {}
    label_cache: dict[str, dict | None] = json.loads(LABEL_CACHE.read_text(encoding="utf-8")) if LABEL_CACHE.exists() else {}
    faers_cache: dict[str, dict] = json.loads(FAERS_CACHE.read_text(encoding="utf-8")) if FAERS_CACHE.exists() else {}

    # Step 1: Drugs@FDA match across ALL named Phase-3 molecules (with NDA/BLA filter + biologic suffix matching)
    match_drugsfda_batch(client, named_mols, drugsfda_cache, refresh_misses=args.refresh_misses)
    approved_mols = {m: v for m, v in drugsfda_cache.items() if v is not None and m in set(named_mols)}
    print(f"  [MATCHED] Approved NDA/BLA molecules: {len(approved_mols)} / {len(named_mols)}", flush=True)

    # Step 2: Drug/Label match for all matched NDA/BLAs
    app_nums = sorted({v["application_number"] for v in approved_mols.values()})
    match_labels_batch(client, app_nums, label_cache)

    # Step 3: FAERS primary-suspect query (prioritize 2005+ approvals first, then older!)
    mol_order = sorted(
        approved_mols.items(),
        key=lambda kv: (0 if kv[1]["orig_approval_year"] >= 2005 else 1, -kv[1]["orig_approval_year"], kv[0]),
    )
    mol_info = [
        (m, (v["generic_names"][0] if v["generic_names"] else m.upper()), v["application_number"])
        for m, v in mol_order
    ]
    fetch_faers_for_molecules(client, mol_info, faers_cache)

    # Step 4: Assemble clean molecule-level Gate-2 analytic dataset
    # Build BOTH: (a) ALL Phase-3 trials of the molecule, and (b) PRE-APPROVAL pivotal trials (start_year <= orig_approval_year)
    prog_rows = []
    for mol, fda in approved_mols.items():
        grp_all = df_p3[df_p3["primary_molecule"] == mol].copy()
        if grp_all.empty:
            continue
        appr_yr = fda["orig_approval_year"]
        appr_dt = fda["orig_approval_date"]
        # Strict pre-approval date ordering: start_date <= orig_approval_date (fallback to start_year if date missing)
        has_dt = grp_all["start_date"].notna()
        grp_pre = grp_all[
            (has_dt & (grp_all["start_date"] <= appr_dt))
            | (~has_dt & (grp_all["start_year"] <= appr_yr))
        ].copy()
        use_pre = len(grp_pre) >= 1

        def agg_trials(g: pd.DataFrame) -> dict:
            w = g["enrollment"].fillna(100.0).to_numpy(dtype=float)
            w_sum = max(1.0, float(np.sum(w)))

            def wavg(col: str) -> float:
                vals = g[col].to_numpy(dtype=float)
                ok = ~np.isnan(vals)
                if not ok.any():
                    return np.nan
                return float(np.sum(vals[ok] * w[ok]) / np.sum(w[ok]))

            return {
                "n_trials": len(g),
                "total_enroll": float(w_sum),
                "eu_east_sh": wavg("eu_east_sh"),
                "ru_ua_sh": wavg("ru_ua_sh"),
                "ee_sh": wavg("ee_sh"),
                "us_sh": wavg("us_sh"),
                "we_sh": wavg("we_sh"),
                "latam_sh": wavg("latam_sh"),
                "asia_sh": wavg("asia_sh"),
                "act_oth": wavg("act_oth"),
                "ctrl_oth": wavg("ctrl_oth"),
                "act_sae": wavg("act_sae"),
                "ctrl_sae": wavg("ctrl_sae"),
                "oth_rd": wavg("oth_rd"),
                "mean_freq_thr": float(g["freq_thr"].mean()),
                "first_start_yr": int(g["start_year"].min()),
            }

        a_all = agg_trials(grp_all)
        a_pre = agg_trials(grp_pre) if use_pre else None

        lbl = label_cache.get(fda["application_number"]) or {}
        frs = faers_cache.get(mol) or {}

        yrs_mkt = max(0.5, 2026.9 - float(appr_yr))
        us_ser = int(frs.get("us_serious_n", 0))
        us_non = int(frs.get("us_nonserious_n", 0))
        us_tot = us_ser + us_non
        gl_ser = int(frs.get("global_serious_n", 0)) if frs.get("global_queried") else np.nan
        gl_non = int(frs.get("global_nonserious_n", 0)) if frs.get("global_queried") else np.nan

        nonus_ser = max(0.0, float(gl_ser - us_ser)) if not np.isnan(gl_ser) else np.nan
        nonus_non = max(0.0, float(gl_non - us_non)) if not np.isnan(gl_non) else np.nan
        nonus_tot = (nonus_ser + nonus_non) if not np.isnan(nonus_ser) else np.nan

        # US-vs-Non-US Non-Serious vs Serious Log Odds Ratio (exact Haldane +0.5 smoothing)
        if not np.isnan(nonus_tot) and us_tot >= 20 and nonus_tot >= 20:
            us_vs_nonus_nonser_lor = float(
                np.log(((us_non + 0.5) / (us_ser + 0.5)) / ((nonus_non + 0.5) / (nonus_ser + 0.5)))
            )
            us_share_of_global_faers = float(us_tot / (us_tot + nonus_tot))
        else:
            us_vs_nonus_nonser_lor = np.nan
            us_share_of_global_faers = np.nan

        n_lab = fda["n_labeling_suppl"]
        n_eff = fda["n_efficacy_suppl"]
        lab_share = float(n_lab / (n_lab + n_eff)) if (n_lab + n_eff) > 0 else np.nan

        row = {
            "molecule": mol,
            "application_number": fda["application_number"],
            "is_bla": fda["is_bla"],
            "lead_sponsor": grp_all["sponsor_nm"].mode().iloc[0],
            "therapeutic_area": grp_all["therapeutic_area"].mode().iloc[0],
            "orig_approval_date": fda["orig_approval_date"],
            "orig_approval_year": int(appr_yr),
            "years_on_market": round(yrs_mkt, 2),
            "has_pre_approval_p3": int(use_pre),
            "approved_2005_2024": int(2005 <= appr_yr <= 2024),
            "approved_2005_2021_5yr_fup": int(2005 <= appr_yr and appr_dt <= "2021-11-25"),
            "approved_2005_2023_3yr_fup": int(2005 <= appr_yr and appr_dt <= "2023-11-25"),
            # All-Phase-3 exposure
            "all_n_trials": a_all["n_trials"],
            "all_log_enroll": float(np.log(a_all["total_enroll"])),
            "all_ee_sh": a_all["ee_sh"],
            "all_eu_east_sh": a_all["eu_east_sh"],
            "all_ru_ua_sh": a_all["ru_ua_sh"],
            "all_us_sh": a_all["us_sh"],
            "all_we_sh": a_all["we_sh"],
            "all_act_oth": a_all["act_oth"],
            "all_ctrl_oth": a_all["ctrl_oth"],
            "all_act_sae": a_all["act_sae"],
            # Pre-approval pivotal Phase-3 exposure (strict temporal ordering!)
            "pre_n_trials": a_pre["n_trials"] if a_pre else np.nan,
            "pre_log_enroll": float(np.log(a_pre["total_enroll"])) if a_pre else np.nan,
            "pre_ee_sh": a_pre["ee_sh"] if a_pre else np.nan,
            "pre_eu_east_sh": a_pre["eu_east_sh"] if a_pre else np.nan,
            "pre_ru_ua_sh": a_pre["ru_ua_sh"] if a_pre else np.nan,
            "pre_us_sh": a_pre["us_sh"] if a_pre else np.nan,
            "pre_we_sh": a_pre["we_sh"] if a_pre else np.nan,
            "pre_latam_sh": a_pre["latam_sh"] if a_pre else np.nan,
            "pre_asia_sh": a_pre["asia_sh"] if a_pre else np.nan,
            "pre_act_oth": a_pre["act_oth"] if a_pre else np.nan,
            "pre_ctrl_oth": a_pre["ctrl_oth"] if a_pre else np.nan,
            "pre_act_sae": a_pre["act_sae"] if a_pre else np.nan,
            "pre_freq_thr": a_pre["mean_freq_thr"] if a_pre else np.nan,
            # Drugs@FDA outcomes
            "n_suppl_total": fda["n_suppl_total"],
            "n_labeling_suppl": n_lab,
            "n_labeling_3yr": fda["n_labeling_3yr"],
            "n_labeling_5yr": fda["n_labeling_5yr"],
            "n_efficacy_suppl": n_eff,
            "n_efficacy_5yr": fda["n_efficacy_5yr"],
            "n_safety_rems_suppl": fda["n_safety_rems_suppl"],
            "labeling_per_yr": float(n_lab / yrs_mkt),
            "log_labeling_per_yr": float(np.log1p(n_lab / yrs_mkt)),
            "log_labeling_5yr": float(np.log1p(fda["n_labeling_5yr"])),
            "log_efficacy_5yr": float(np.log1p(fda["n_efficacy_5yr"])),
            "labeling_share": lab_share,
            "any_safety_rems": int(fda["n_safety_rems_suppl"] > 0),
            # Drug/Label outcomes
            "has_label_match": int(bool(lbl)),
            "has_boxed_warning": lbl.get("has_boxed_warning", np.nan),
            "log_adverse_reactions_chars": float(np.log1p(lbl["adverse_reactions_chars"])) if lbl.get("adverse_reactions_chars") else np.nan,
            "log_warnings_chars": float(np.log1p(lbl["warnings_chars"])) if lbl.get("warnings_chars") else np.nan,
            # FAERS outcomes
            "us_serious_n": us_ser,
            "us_nonserious_n": us_non,
            "us_total_n": us_tot,
            "us_serious_share": float(us_ser / us_tot) if us_tot >= 20 else np.nan,
            "us_nonserious_share": float(us_non / us_tot) if us_tot >= 20 else np.nan,
            "log_us_total_per_yr": float(np.log1p(us_tot / yrs_mkt)) if us_tot > 0 else np.nan,
            "log_us_serious_per_yr": float(np.log1p(us_ser / yrs_mkt)) if us_tot > 0 else np.nan,
            "log_us_nonserious_per_yr": float(np.log1p(us_non / yrs_mkt)) if us_tot > 0 else np.nan,
            "us_vs_nonus_nonser_lor": us_vs_nonus_nonser_lor,
            "us_share_of_global_faers": us_share_of_global_faers,
        }
        prog_rows.append(row)

    gdf = pd.DataFrame(prog_rows)
    gate2_csv = PROC_DIR / "d30_gate2_openfda_molecules.csv"
    gdf.to_csv(gate2_csv, index=False)

    # =========================================================================
    # GATE #2 ECONOMETRIC TESTS (Honest, Pre-Specified, Strictly Controlled)
    # =========================================================================
    # Primary cohort: Pre-approval pivotal Phase-3 MRCTs, FDA approved 2005-2024
    g_pre = gdf[(gdf["has_pre_approval_p3"] == 1) & (gdf["approved_2005_2024"] == 1)].copy()
    g_pre_5yr = gdf[(gdf["has_pre_approval_p3"] == 1) & (gdf["approved_2005_2021_5yr_fup"] == 1)].copy()
    g_pre_3yr = gdf[(gdf["has_pre_approval_p3"] == 1) & (gdf["approved_2005_2023_3yr_fup"] == 1)].copy()
    g_pre_before17 = g_pre[g_pre["orig_approval_year"] <= 2016].copy()
    g_pre_after17 = g_pre[g_pre["orig_approval_year"] >= 2017].copy()

    base_controls = "is_bla + pre_log_enroll + pre_act_sae + C(therapeutic_area) + C(orig_approval_year)"
    base_controls_eff = base_controls + " + log_efficacy_5yr"

    n_us_pos = sum(1 for m in approved_mols if (faers_cache.get(m) or {}).get("us_total_n", 0) > 0)
    n_gl_done = sum(
        1 for m in approved_mols
        if (faers_cache.get(m) or {}).get("us_total_n", 0) > 0 and (faers_cache.get(m) or {}).get("global_queried")
    )

    g2_res: dict = {
        "linkage_audit": {
            "total_p3_unique_named_molecules": len(named_mols),
            "matched_originator_nda_bla": len(gdf),
            "match_rate_pct": round(100.0 * len(gdf) / max(1, len(named_mols)), 2),
            "with_pre_approval_p3_2005_2024": len(g_pre),
            "with_5yr_followup_2005_2021": len(g_pre_5yr),
            "with_3yr_followup_2005_2023": len(g_pre_3yr),
            "with_fda_label_match": int(g_pre["has_label_match"].sum()),
            "with_us_faers_ge20_reports": int((g_pre["us_total_n"] >= 20).sum()),
            "with_us_and_nonus_faers_ge20": int(g_pre["us_vs_nonus_nonser_lor"].notna().sum()),
            "faers_global_queried_among_us_pos": f"{n_gl_done}/{n_us_pos}",
            "total_openfda_api_requests_this_run": int(client.n_requests),
        },
        "descriptive_by_ee_tertile_pre_2005_2024": {},
        "first_stage_molecule_level_check": {},
        "drugsfda_labeling_supplements": {},
        "fda_label_warnings": {},
        "faers_pharmacovigilance": {},
        "faers_us_serious_forensic_audit": {},
        "era_split_pre2017_vs_post2017": {},
        "all_p3_robustness_check": {},
        "null_endpoint_equivalence_bounds": {},
    }

    # First-stage sanity check at the molecule level: does pivotal pre_ee_sh still predict lower pre_act_oth?
    g2_res["first_stage_molecule_level_check"]["pre_act_oth_on_pre_ee_sh"] = run_ols_hc3(
        g_pre, f"pre_act_oth ~ pre_ee_sh + pre_freq_thr + {base_controls}", ["pre_ee_sh"]
    )
    g2_res["first_stage_molecule_level_check"]["pre_ctrl_oth_on_pre_ee_sh"] = run_ols_hc3(
        g_pre, f"pre_ctrl_oth ~ pre_ee_sh + pre_freq_thr + {base_controls}", ["pre_ee_sh"]
    )

    # Descriptive tertiles / bins of pre_ee_sh
    for lbl, m in [
        ("EE_0pct", g_pre["pre_ee_sh"] == 0),
        ("EE_0_15pct", (g_pre["pre_ee_sh"] > 0) & (g_pre["pre_ee_sh"] < 0.15)),
        ("EE_ge15pct", g_pre["pre_ee_sh"] >= 0.15),
    ]:
        s = g_pre[m]
        s5 = g_pre_5yr[g_pre_5yr["molecule"].isin(s["molecule"])]
        g2_res["descriptive_by_ee_tertile_pre_2005_2024"][lbl] = {
            "n_drugs": len(s),
            "n_drugs_5yr": len(s5),
            "mean_pre_ee_sh": round(float(s["pre_ee_sh"].mean()), 4) if len(s) else None,
            "mean_pre_act_oth": round(float(s["pre_act_oth"].mean()), 4) if len(s) else None,
            "mean_labeling_per_yr": round(float(s["labeling_per_yr"].mean()), 3) if len(s) else None,
            "mean_n_labeling_5yr": round(float(s5["n_labeling_5yr"].mean()), 3) if len(s5) else None,
            "mean_n_efficacy_5yr": round(float(s5["n_efficacy_5yr"].mean()), 3) if len(s5) else None,
            "boxed_warning_pct": round(100.0 * float(s["has_boxed_warning"].mean()), 2) if s["has_boxed_warning"].notna().any() else None,
            "us_serious_share_pct": round(100.0 * float(s["us_serious_share"].mean()), 2) if s["us_serious_share"].notna().any() else None,
            "us_nonserious_share_pct": round(100.0 * float(s["us_nonserious_share"].mean()), 2) if s["us_nonserious_share"].notna().any() else None,
            "mean_us_vs_nonus_nonser_lor": round(float(s["us_vs_nonus_nonser_lor"].mean()), 4) if s["us_vs_nonus_nonser_lor"].notna().any() else None,
        }

    # Test 1: Drugs@FDA Post-Approval Labeling Supplements (strict follow-up windows + Poisson count check!)
    for y, dset, ctrl in [
        ("log_labeling_per_yr", g_pre, base_controls_eff),
        ("labeling_per_yr", g_pre, base_controls_eff),
        ("log_labeling_5yr", g_pre_5yr, base_controls_eff),
        ("n_labeling_5yr", g_pre_5yr, base_controls_eff),
        ("n_labeling_3yr", g_pre_3yr, base_controls_eff),
        ("labeling_share", g_pre, base_controls),
        ("any_safety_rems", g_pre, base_controls_eff),
        ("log_efficacy_5yr", g_pre_5yr, base_controls),  # Placebo commercial-popularity outcome!
    ]:
        g2_res["drugsfda_labeling_supplements"][f"{y}_ee"] = run_ols_hc3(
            dset, f"{y} ~ pre_ee_sh + {ctrl}", ["pre_ee_sh"]
        )
        g2_res["drugsfda_labeling_supplements"][f"{y}_split"] = run_ols_hc3(
            dset, f"{y} ~ pre_eu_east_sh + pre_ru_ua_sh + {ctrl}", ["pre_eu_east_sh", "pre_ru_ua_sh"]
        )
    g2_res["drugsfda_labeling_supplements"]["n_labeling_5yr_poisson_glm"] = run_poisson_cluster(
        g_pre_5yr, f"n_labeling_5yr ~ pre_ee_sh + {base_controls_eff}", ["pre_ee_sh"]
    )
    g2_res["drugsfda_labeling_supplements"]["n_labeling_3yr_poisson_glm"] = run_poisson_cluster(
        g_pre_3yr, f"n_labeling_3yr ~ pre_ee_sh + {base_controls_eff}", ["pre_ee_sh"]
    )

    # Test 2: FDA Drug Label Boxed Warning & Safety Text Length
    for y in ["has_boxed_warning", "log_adverse_reactions_chars", "log_warnings_chars"]:
        g2_res["fda_label_warnings"][f"{y}_ee"] = run_ols_hc3(
            g_pre, f"{y} ~ pre_ee_sh + {base_controls}", ["pre_ee_sh"]
        )
        g2_res["fda_label_warnings"][f"{y}_split"] = run_ols_hc3(
            g_pre, f"{y} ~ pre_eu_east_sh + pre_ru_ua_sh + {base_controls}", ["pre_eu_east_sh", "pre_ru_ua_sh"]
        )

    # Test 3: FAERS Post-Marketing US Adverse Events & Disproportionality
    for y in [
        "us_serious_share",
        "us_nonserious_share",
        "us_vs_nonus_nonser_lor",
        "log_us_total_per_yr",
        "log_us_serious_per_yr",
        "log_us_nonserious_per_yr",
        "us_share_of_global_faers",
    ]:
        g2_res["faers_pharmacovigilance"][f"{y}_ee"] = run_ols_hc3(
            g_pre, f"{y} ~ pre_ee_sh + {base_controls}", ["pre_ee_sh"]
        )
        g2_res["faers_pharmacovigilance"][f"{y}_ee_ctrl_actoth"] = run_ols_hc3(
            g_pre, f"{y} ~ pre_ee_sh + pre_act_oth + {base_controls}", ["pre_ee_sh", "pre_act_oth"]
        )
        g2_res["faers_pharmacovigilance"][f"{y}_split"] = run_ols_hc3(
            g_pre, f"{y} ~ pre_eu_east_sh + pre_ru_ua_sh + {base_controls}", ["pre_eu_east_sh", "pre_ru_ua_sh"]
        )

    # Test 3b: Complete persisted 10-step forensic covariate audit on FAERS us_serious_share
    s_faers = g_pre.dropna(
        subset=["us_serious_share", "pre_ee_sh", "is_bla", "pre_log_enroll", "pre_act_sae", "therapeutic_area", "orig_approval_year"]
    ).copy()
    for step_key, rhs in [
        ("01_raw_bivariate", "pre_ee_sh"),
        ("02_ta_fe", "pre_ee_sh + C(therapeutic_area)"),
        ("03_year_fe", "pre_ee_sh + C(orig_approval_year)"),
        ("04_ta_year_fe", "pre_ee_sh + C(therapeutic_area) + C(orig_approval_year)"),
        ("05_plus_bla", "pre_ee_sh + is_bla + C(therapeutic_area) + C(orig_approval_year)"),
        ("06_plus_enroll", "pre_ee_sh + is_bla + pre_log_enroll + C(therapeutic_area) + C(orig_approval_year)"),
        ("07_main_plus_sae", f"pre_ee_sh + {base_controls}"),
        ("08_plus_us_faers_vol", f"pre_ee_sh + log_us_total_per_yr + {base_controls}"),
        ("09_plus_other_regions", f"pre_ee_sh + pre_we_sh + pre_latam_sh + pre_asia_sh + {base_controls}"),
        ("10_plus_sponsor_fe", f"pre_ee_sh + {base_controls} + C(lead_sponsor)"),
    ]:
        d_use = s_faers
        if step_key == "10_plus_sponsor_fe":
            cnt_sp = s_faers["lead_sponsor"].value_counts()
            d_use = s_faers[s_faers["lead_sponsor"].isin(cnt_sp[cnt_sp >= 2].index)].copy()
        g2_res["faers_us_serious_forensic_audit"][step_key] = run_ols_hc3(
            d_use, f"us_serious_share ~ {rhs}", ["pre_ee_sh"]
        )

    # Test 4: Pre-2017 vs Post-2017 Approval Cohort Split
    for era_lbl, esub in [("approved_2005_2016", g_pre_before17), ("approved_2017_2024", g_pre_after17)]:
        g2_res["era_split_pre2017_vs_post2017"][era_lbl] = {
            "n_drugs": len(esub),
            "log_labeling_per_yr": run_ols_hc3(esub, f"log_labeling_per_yr ~ pre_ee_sh + {base_controls_eff}", ["pre_ee_sh"]),
            "has_boxed_warning": run_ols_hc3(esub, f"has_boxed_warning ~ pre_ee_sh + {base_controls}", ["pre_ee_sh"]),
            "us_serious_share": run_ols_hc3(esub, f"us_serious_share ~ pre_ee_sh + {base_controls}", ["pre_ee_sh"]),
            "us_vs_nonus_nonser_lor": run_ols_hc3(esub, f"us_vs_nonus_nonser_lor ~ pre_ee_sh + {base_controls}", ["pre_ee_sh"]),
        }

    # Test 5: Robustness using ALL matched Phase-3 trials (not restricted to pre-approval start_year)
    g_all05 = gdf[gdf["approved_2005_2024"] == 1].copy()
    all_ctrl = "is_bla + all_log_enroll + all_act_sae + C(therapeutic_area) + C(orig_approval_year)"
    for y in ["log_labeling_per_yr", "has_boxed_warning", "us_serious_share", "us_vs_nonus_nonser_lor"]:
        g2_res["all_p3_robustness_check"][y] = run_ols_hc3(
            g_all05, f"{y} ~ all_ee_sh + {all_ctrl}", ["all_ee_sh"]
        )

    # Exact 95% CIs & Minimum Excludable Equivalence Bounds (TOST 90% & 95% CI) for Gate-2 Null Endpoints
    g2_eq_targets = [
        ("n_labeling_5yr", g2_res["drugsfda_labeling_supplements"]["n_labeling_5yr_ee"]),
        ("n_labeling_3yr", g2_res["drugsfda_labeling_supplements"]["n_labeling_3yr_ee"]),
        ("log_labeling_per_yr", g2_res["drugsfda_labeling_supplements"]["log_labeling_per_yr_ee"]),
        ("labeling_share", g2_res["drugsfda_labeling_supplements"]["labeling_share_ee"]),
        ("any_safety_rems", g2_res["drugsfda_labeling_supplements"]["any_safety_rems_ee"]),
        ("has_boxed_warning", g2_res["fda_label_warnings"]["has_boxed_warning_ee"]),
        ("us_vs_nonus_nonser_lor", g2_res["faers_pharmacovigilance"]["us_vs_nonus_nonser_lor_ee"]),
    ]
    for name, rec in g2_eq_targets:
        t = rec.get("terms", {}).get("pre_ee_sh", {})
        if not t:
            continue
        g2_res["null_endpoint_equivalence_bounds"][name] = {
            "n": rec["n"],
            "y_mean": rec["y_mean"],
            "coef": t["coef"],
            "se": t["se"],
            "p": t["p"],
            "ci95": [t["ci95_lo"], t["ci95_hi"]],
            "ci90": [t["ci90_lo"], t["ci90_hi"]],
            "tost_90_margin": t["tost_90_margin"],
            "excludable_95_abs": t["excludable_95_abs"],
            "per_10pp_coef": t["per_10pp_coef"],
            "per_10pp_ci95": [t["per_10pp_ci95_lo"], t["per_10pp_ci95_hi"]],
            "per_10pp_tost_90": round(0.10 * t["tost_90_margin"], 5),
        }

    out_json = RES_DIR / "d30_gate2_openfda_results.json"
    out_json.write_text(json.dumps(g2_res, indent=2), encoding="utf-8")
    sha = hashlib.sha256(out_json.read_bytes()).hexdigest()

    # Export clean Table 5 CSV
    t5_rows = []
    for block_name, block_dict in [
        ("First-Stage (Molecule-Level Pivotal AE)", g2_res["first_stage_molecule_level_check"]),
        ("Drugs@FDA Labeling Supplements", g2_res["drugsfda_labeling_supplements"]),
        ("FDA Drug Label Warnings", g2_res["fda_label_warnings"]),
        ("FAERS Post-Marketing Pharmacovigilance", g2_res["faers_pharmacovigilance"]),
    ]:
        for k, v in block_dict.items():
            if not k.endswith("_ee") and "first-stage" not in block_name.lower():
                continue
            t = v.get("terms", {}).get("pre_ee_sh", {})
            t5_rows.append({
                "category": block_name,
                "outcome": k,
                "n": v.get("n"),
                "y_mean": v.get("y_mean"),
                "coef_pre_ee_sh": t.get("coef"),
                "se": t.get("se"),
                "t": t.get("t"),
                "p": t.get("p"),
                "ci95_lo": t.get("ci95_lo"),
                "ci95_hi": t.get("ci95_hi"),
                "tost_90_margin": t.get("tost_90_margin"),
                "per_10pp_coef": t.get("per_10pp_coef"),
            })
    pd.DataFrame(t5_rows).to_csv(TAB_DIR / "table5_gate2_openfda_faers.csv", index=False)

    print(f"\n[DONE Gate #2] openFDA linkage complete! JSON SHA-256: {sha}", flush=True)
    print("Linkage Audit:", json.dumps(g2_res["linkage_audit"], indent=2), flush=True)
    print("\n=== GATE #2 KEY RESULTS (pre_ee_sh, approved 2005-2024) ===", flush=True)
    for row in t5_rows:
        print(
            f"  {row['outcome']:36s} (N={row['n'] or 0:3d}, ybar={row['y_mean'] or 0:.3f}): "
            f"coef={row['coef_pre_ee_sh'] if row['coef_pre_ee_sh'] is not None else np.nan:+.4f} "
            f"(se={row['se'] if row['se'] is not None else np.nan:.4f}, "
            f"t={row['t'] if row['t'] is not None else np.nan:+.2f}, "
            f"p={row['p'] if row['p'] is not None else np.nan:.4g})",
            flush=True,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
