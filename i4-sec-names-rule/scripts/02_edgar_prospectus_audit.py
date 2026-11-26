"""Pillar 2: Direct SEC EDGAR 485BPOS / 497 / 497K Prospectus-Sticker Attribution Audit.

Audits:
1. N-PORT EXPLANATORY_NOTE.tsv across 2024Q4-2026Q3 for explicit Rule 35d-1 / Names Rule /
   80% policy mentions linked to SERIES_ID.
2. Live SEC EDGAR EFTS + submissions + targeted 497/497K/485BPOS/485APOS HTML downloads
   (cached locally in data/edgar_cache/) for:
     - ALL 2025Q1-2026Q3 Multi-Asset GVI droppers (OPAQUE_SYNONYM vs NUMERIC_RATIO)
     - ALL 2025Q1-2026Q3 ESG droppers
     - ALL 2025Q1-2026Q3 Pure-Equity/Bond GVI droppers
     - A seeded random Control Sample (N=50, seed=20261126) of non-dropping Multi-Asset GVI Keepers
3. Deterministically extracts:
     - Explicit "Rule 35d-1" / "35d-1" / "Names Rule" citation (fund-specific & trust-level)
     - Explicit name-change prospectus supplement match (old/new series name)
     - Exact legal effective date of the rename (testing May 1, 2025 lock-in & May-June 2026 cliff)
     - Explicit "no change to investment objective / strategies / policies" legal admission
     - Explicit "80% investment policy" disclosure/amendment (comparing Droppers vs Keepers)
4. Saves complete verifiable receipts with accession numbers, filing dates, URLs, and verbatim snippets.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import time
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from scipy import stats

READ_DATA_DIR = Path(r"D:\AI_Science\antigravity\frontier_discovery_20261126_wave5\data_i4")
WORK_DIR = Path(r"D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126")
CACHE_DIR = WORK_DIR / "data" / "edgar_cache"
SUB_CACHE = CACHE_DIR / "submissions"
EFTS_CACHE = CACHE_DIR / "efts"
DOC_CACHE = CACHE_DIR / "docs"
for d in (CACHE_DIR, SUB_CACHE, EFTS_CACHE, DOC_CACHE):
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "AcademicResearch research@university.edu",
    "Accept-Encoding": "gzip, deflate",
}

RE_RULE_35D1 = re.compile(
    r"(?:rule\s+35d[\-\u2010-\u2015\s]?1|\b35d[\-\u2010-\u2015\s]?1\b|amended\s+names?\s+rule|\bnames?\s+rule\b)",
    re.IGNORECASE,
)
RE_80_POLICY = re.compile(
    r"(?:80%\s+(?:investment\s+)?polic|80%\s+(?:of\s+(?:the\s+|its\s+)?(?:net\s+)?assets|threshold|requirement|basket|names?\s+rule))",
    re.IGNORECASE,
)
RE_NAME_CHANGE = re.compile(
    r"(?:(?:fund|portfolio|etf|series)\s+name\s+change|name\s+change(?:s)?\s+(?:for|of|to)\s+(?:the\s+|each\s+)?(?:fund|portfolio|etf)|"
    r"(?:fund|portfolio|etf|series)(?:'s)?\s+(?:name\s+)?(?:will\s+change|has\s+changed|changed\s+its\s+name|change\s+its\s+name|will\s+be\s+renamed|has\s+been\s+renamed)|"
    r"the\s+name\s+of\s+(?:the\s+|each\s+)?(?:fund|portfolio|etf)\s+will\s+change|"
    r"prior\s+(?:fund|portfolio)\s+name|current\s+(?:fund|portfolio)\s+name|new\s+(?:fund|portfolio)\s+name|"
    r"(?:fund|portfolio|etf)\s+(?:was\s+)?formerly\s+known\s+as|"
    r"name\s+changes?\s+effective\s+(?:on\s+|as\s+of\s+|today|immediately))",
    re.IGNORECASE,
)
RE_NO_STRATEGY_CHANGE = re.compile(
    r"(?:(?:investment\s+objective|strategies|polic(?:y|ies)|portfolio\s+management)[^.]{0,90}"
    r"(?:will\s+remain\s+unchanged|remain\s+the\s+same|will\s+not\s+change|are\s+not\s+changing|have\s+not\s+changed|unchanged)"
    r"|no\s+change(?:s)?\s+(?:to|in)\s+(?:the\s+|each\s+)?(?:fund'?s?|portfolio'?s?)?\s*"
    r"(?:principal\s+)?(?:investment\s+)?(?:objective|strateg|polic|management))",
    re.IGNORECASE,
)

MONTHS_PAT = (
    r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
)
RE_EFF_DATE = re.compile(
    rf"(?:effective\s+(?:on\s+or\s+about\s+|as\s+of\s+|at\s+the\s+close\s+of\s+business\s+on\s+|on\s+)?"
    rf"({MONTHS_PAT}\s+\d{{1,2}},\s+202[456])"
    rf"|prior\s+to\s+({MONTHS_PAT}\s+\d{{1,2}},\s+202[456]))",
    re.IGNORECASE,
)
RE_EFF_TODAY = re.compile(r"effective\s+(?:today|immediately)", re.IGNORECASE)
RE_SUPP_DATED = re.compile(rf"supplement\s+dated\s+({MONTHS_PAT}\s+\d{{1,2}},\s+202[456])", re.IGNORECASE)

STOPWORDS = {
    "fund",
    "funds",
    "portfolio",
    "portfolios",
    "trust",
    "series",
    "etf",
    "index",
    "the",
    "of",
    "and",
    "inc",
    "class",
    "shares",
    "investor",
    "advisors",
    "advisor",
    "investment",
    "investments",
    "mutual",
    "group",
    "vip",
    "ast",
    "sa",
    "vp",
    "us",
    "u.s.",
}


class PoliteClient:
    """Rate-limited (<= 5 req/s), retry-capable SEC EDGAR client with disk caching."""

    def __init__(self, min_interval: float = 0.21):
        self.sess = requests.Session()
        self.sess.headers.update(HEADERS)
        self.min_interval = min_interval
        self.last_req = 0.0
        self.n_live = 0
        self.n_cache = 0

    def _throttle(self) -> None:
        dt = time.time() - self.last_req
        if dt < self.min_interval:
            time.sleep(self.min_interval - dt)
        self.last_req = time.time()

    def get_json_cached(self, url: str, params: dict | None, cache_path: Path) -> dict | None:
        if cache_path.exists():
            self.n_cache += 1
            try:
                return json.loads(cache_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                print(f"    [cache reload] {cache_path.name}: {exc}", flush=True)
        for att in range(4):
            self._throttle()
            try:
                r = self.sess.get(url, params=params, timeout=25)
                if r.status_code == 200:
                    self.n_live += 1
                    data = r.json()
                    cache_path.write_text(json.dumps(data), encoding="utf-8")
                    return data
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2.5 * (att + 1))
                    continue
                return None
            except (requests.RequestException, ValueError):
                time.sleep(2.0 * (att + 1))
        return None

    def get_text_cached(self, url: str, cache_path: Path, max_bytes: int = 6_000_000) -> str | None:
        if cache_path.exists():
            sz = cache_path.stat().st_size
            # Re-fetch if file was truncated near the legacy 1.5MB cap (<1.6MB and >=1.45MB)
            if not (1_450_000 <= sz <= 1_600_000 and max_bytes > 1_600_000):
                self.n_cache += 1
                try:
                    return cache_path.read_text(encoding="utf-8", errors="replace")
                except OSError as exc:
                    print(f"    [cache reload] {cache_path.name}: {exc}", flush=True)
        for att in range(3):
            self._throttle()
            try:
                r = self.sess.get(url, timeout=25, stream=True)
                if r.status_code == 200:
                    self.n_live += 1
                    chunks = []
                    tot = 0
                    for ch in r.iter_content(chunk_size=65536):
                        if not ch:
                            continue
                        chunks.append(ch)
                        tot += len(ch)
                        if tot >= max_bytes:
                            break
                    r.close()
                    raw = b"".join(chunks).decode("utf-8", errors="replace")
                    cache_path.write_text(raw, encoding="utf-8")
                    return raw
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2.0 * (att + 1))
                    continue
                return None
            except (requests.RequestException, OSError):
                time.sleep(1.5 * (att + 1))
        return None


RE_SCRIPT_STYLE = re.compile(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL)
RE_HTML_TAG = re.compile(r"<[^>]+>")


def parse_date_str(s: str | None) -> str | None:
    if not s:
        return None
    s_clean = re.sub(r"\s+", " ", s.strip())
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(s_clean, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


def html_to_clean_text(raw_html: str) -> str:
    """Fast deterministic HTML/XML-to-plain-text stripping (~100x faster than BS4 on 485BPOS)."""
    if "<" in raw_html and ">" in raw_html:
        txt = RE_SCRIPT_STYLE.sub(" ", raw_html)
        txt = RE_HTML_TAG.sub(" ", txt)
        txt = html_mod.unescape(txt)
    else:
        txt = raw_html
    return re.sub(r"\s+", " ", txt).strip()


def distinctive_tokens(name: str) -> list[str]:
    clean = re.sub(r"[^A-Za-z0-9/%&\-\s]+", " ", (name or "").lower())
    toks = [t for t in clean.split() if len(t) >= 3 and t not in STOPWORDS]
    return toks


def fund_matches_text(old_name: str, new_name: str, text_lower: str) -> bool:
    """Check whether a prospectus filing specifically references this fund (old or new name)."""
    for nm in (new_name, old_name):
        if not nm:
            continue
        clean = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9/%&\-\s]+", " ", nm.lower())).strip()
        if len(clean) >= 8 and clean in text_lower:
            return True
        toks = distinctive_tokens(nm)
        if len(toks) >= 2:
            hits = sum(1 for t in toks if t in text_lower)
            if hits >= max(2, int(np.ceil(0.70 * len(toks)))):
                return True
        elif len(toks) == 1 and len(toks[0]) >= 5 and toks[0] in text_lower:
            return True
    return False


def best_search_phrase(name: str) -> str:
    """Extract a crisp quoted search phrase for EFTS."""
    s = re.sub(r"\s+", " ", (name or "").strip())
    s = re.sub(r",\s*inc\.?$", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(r\)|®|™", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    words = s.split()
    if len(words) > 6:
        s = " ".join(words[:6])
    return s


def extract_snippet(text: str, pat: re.Pattern[str], radius: int = 110) -> str:
    m = pat.search(text)
    if not m:
        return ""
    lo = max(0, m.start() - radius)
    hi = min(len(text), m.end() + radius)
    return text[lo:hi].strip()


RE_PROSP_DATED = re.compile(
    rf"(?:prospectus(?:es)?\s+dated|summary\s+prospectus\s+dated|dated)\s+({MONTHS_PAT}\s+\d{{1,2}},\s+202[456])",
    re.IGNORECASE,
)


def _date_in_drop_window(date_str: str | None, rep_yq: int | None) -> bool:
    """Validate that an extracted effective date sits plausibly near the N-PORT drop quarter."""
    if not date_str:
        return False
    if rep_yq is None:
        return True
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False
    yr, q = rep_yq // 10, rep_yq % 10
    q_start = datetime(yr, (q - 1) * 3 + 1, 1)
    q_end_m = q * 3
    q_end = datetime(yr, q_end_m, 28)
    # Effective date must be within [-150 days before quarter start, +60 days after quarter end]
    return (q_start.toordinal() - 150) <= dt.toordinal() <= (q_end.toordinal() + 60)


def extract_effective_date(
    text: str,
    file_date: str | None,
    rep_yq: int | None = None,
    form: str = "",
    allow_fallback: bool = True,
) -> str | None:
    """Extract legal effective date near name change wording, validated against N-PORT drop quarter."""
    windows: list[str] = []
    for m_nc in list(RE_NAME_CHANGE.finditer(text))[:5]:
        lo = max(0, m_nc.start() - 600)
        hi = min(len(text), m_nc.end() + 900)
        windows.append(text[lo:hi])
    windows.append(text[:4500])

    for win in windows:
        for m in RE_EFF_DATE.finditer(win):
            raw_d = m.group(1) or m.group(2)
            parsed = parse_date_str(raw_d)
            if parsed and _date_in_drop_window(parsed, rep_yq):
                return parsed
        if RE_EFF_TODAY.search(win):
            ms = RE_SUPP_DATED.search(text[:2500])
            if ms:
                parsed = parse_date_str(ms.group(1))
                if parsed and _date_in_drop_window(parsed, rep_yq):
                    return parsed
            if _date_in_drop_window(file_date, rep_yq):
                return file_date

    if not allow_fallback:
        return None
    # Fallback for 497K / 497 summary prospectuses saying "formerly known as ..." with explicit Prospectus Dated
    if re.search(r"formerly\s+known\s+as|name\s+change|prior\s+(?:fund|portfolio)\s+name", text, re.IGNORECASE):
        for m in RE_PROSP_DATED.finditer(text[:3500]):
            parsed = parse_date_str(m.group(1))
            if parsed and _date_in_drop_window(parsed, rep_yq):
                return parsed
        if form in ("497", "497K") and _date_in_drop_window(file_date, rep_yq):
            return file_date
    return None


def scan_nport_explanatory_notes(target_series: set[str]) -> dict:
    """Part A: Scan local N-PORT EXPLANATORY_NOTE.tsv (2024Q4-2026Q3) for Rule 35d-1 mentions."""
    print("[1/4] Scanning local N-PORT EXPLANATORY_NOTE.tsv (2024Q4-2026Q3)...", flush=True)
    nport_dir = READ_DATA_DIR / "nport"
    q_list = ["2024q4", "2025q1", "2025q2", "2025q3", "2025q4", "2026q1", "2026q2", "2026q3"]
    all_hits = []
    dropper_hits: dict[str, list[dict]] = {}

    for q in q_list:
        qd = nport_dir / q
        en_p = qd / "EXPLANATORY_NOTE.tsv"
        fri_p = qd / "FUND_REPORTED_INFO.tsv"
        if not (en_p.exists() and fri_p.exists()):
            continue
        en = pd.read_csv(en_p, sep="\t", dtype=str, low_memory=False)
        fri = pd.read_csv(fri_p, sep="\t", usecols=["ACCESSION_NUMBER", "SERIES_ID", "SERIES_NAME"], dtype=str, low_memory=False)
        note_col = [c for c in en.columns if "NOTE" in c.upper()][-1]
        m = en[en[note_col].fillna("").str.contains(RE_RULE_35D1) | en[note_col].fillna("").str.contains(RE_80_POLICY)].copy()
        if len(m) == 0:
            continue
        m = m.merge(fri, on="ACCESSION_NUMBER", how="left")
        n_35d1 = int(m[note_col].fillna("").str.contains(RE_RULE_35D1).sum())
        n_80p = int(m[note_col].fillna("").str.contains(RE_80_POLICY).sum())
        all_hits.append({"file_qtr": q, "n_notes_35d1": n_35d1, "n_notes_80pct": n_80p})
        for _, r in m.iterrows():
            sid = str(r.get("SERIES_ID") or "").strip()
            if sid in target_series:
                dropper_hits.setdefault(sid, []).append(
                    {
                        "file_qtr": q,
                        "accession": r["ACCESSION_NUMBER"],
                        "has_35d1": bool(RE_RULE_35D1.search(str(r[note_col] or ""))),
                        "snippet": str(r[note_col] or "")[:220],
                    }
                )
    print(f"  N-PORT explanatory note hits: {sum(x['n_notes_35d1'] for x in all_hits)} Rule 35d-1 notes across {len(all_hits)} quarters; {len(dropper_hits)} target funds matched.", flush=True)
    return {"quarterly_counts": all_hits, "target_fund_hits": dropper_hits}


def efts_search(client: PoliteClient, q: str, cik10: str, startdt: str = "2024-01-01", enddt: str = "2026-09-30") -> list[dict]:
    """Cached EFTS search for 497/497K/485BPOS/485APOS within a CIK."""
    key = hashlib.md5(f"{cik10}|{startdt}|{enddt}|{q}".encode()).hexdigest()
    cp = EFTS_CACHE / f"efts_{cik10}_{key}.json"
    params = {
        "q": q,
        "ciks": cik10,
        "forms": "497,497K,485BPOS,485APOS",
        "dateRange": "custom",
        "startdt": startdt,
        "enddt": enddt,
    }
    data = client.get_json_cached("https://efts.sec.gov/LATEST/search-index", params, cp)
    if not data:
        return []
    hits = data.get("hits", {}).get("hits", [])
    out = []
    for h in hits:
        src = h.get("_source", {})
        hid = h.get("_id", "")
        adsh = src.get("adsh", "")
        fname = hid.split(":", 1)[1] if ":" in hid else ""
        out.append(
            {
                "form": src.get("form", ""),
                "file_date": src.get("file_date", ""),
                "adsh": adsh,
                "filename": fname,
                "cik": cik10,
            }
        )
    return out


def fetch_doc_text(client: PoliteClient, cik10: str, adsh: str, filename: str) -> tuple[str, str]:
    """Download & cache SEC filing HTML and return (clean_text, url)."""
    cik_int = str(int(cik10))
    acc_nd = adsh.replace("-", "")
    url = f"https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc_nd}/{filename}"
    safe_fn = re.sub(r"[^A-Za-z0-9._\-]", "_", f"{cik10}_{acc_nd}_{filename}")[:120]
    cp = DOC_CACHE / f"{safe_fn}.txt"
    raw = client.get_text_cached(url, cp)
    if not raw:
        return "", url
    return html_to_clean_text(raw), url


def main() -> int:
    audit_df = pd.read_csv(WORK_DIR / "tables" / "table_all_droppers_2025_2026_audit.csv", dtype={"CIK": str})
    qtr_panel = pd.read_parquet(WORK_DIR / "data" / "panel_quarterly.parquet")

    # Deduplicate droppers to unique SERIES_ID (preserving highest-priority drop record)
    droppers = audit_df.drop_duplicates("SERIES_ID", keep="first").copy()
    droppers["SAMPLE_ARM"] = np.where(
        droppers["DROP_GROUP"] == "MULTI_ASSET_GVI",
        np.where(
            droppers["COMPLIANCE_TYPE"] == "NUMERIC_RATIO",
            "MA_GVI_NUMERIC",
            np.where(droppers["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM", "MA_GVI_OPAQUE", "MA_GVI_OTHER"),
        ),
        np.where(droppers["DROP_ESG"] == 1, "ESG_DROPPER", "PURE_GVI_DROPPER"),
    )

    # Construct seeded random Matched Control Sample (N=50) of non-dropping Multi-Asset GVI Keepers
    dropped_sids = set(droppers["SERIES_ID"])
    keepers_pool = (
        qtr_panel[
            (qtr_panel["REP_YQ"] >= 20251)
            & (qtr_panel["PREV_IS_ALLOC_FUND"] == 1)
            & (qtr_panel["PREV_HAS_GVI"] == 1)
            & (qtr_panel["HAS_GVI"] == 1)
            & (~qtr_panel["SERIES_ID"].isin(dropped_sids))
            & (qtr_panel["LARGE_COMPLEX_23Q2"] == 1.0)
        ]
        .sort_values(["SERIES_ID", "REP_YQ"])
        .drop_duplicates("SERIES_ID", keep="last")
        .copy()
    )
    rng = np.random.default_rng(20261126)
    pick_idx = rng.choice(len(keepers_pool), size=min(50, len(keepers_pool)), replace=False)
    keepers = keepers_pool.iloc[sorted(pick_idx)].copy()
    keepers_rows = pd.DataFrame(
        {
            "SERIES_ID": keepers["SERIES_ID"].to_numpy(),
            "CIK": keepers["CIK"].astype(str).to_numpy(),
            "COMPLEX_ID": keepers["COMPLEX_ID"].to_numpy(),
            "DROP_GROUP": "CONTROL_MA_GVI_KEEPER",
            "SAMPLE_ARM": "CONTROL_MA_GVI_KEEPER",
            "COMPLIANCE_TYPE": "KEEPER",
            "OLD_NAME": keepers["SERIES_NAME"].to_numpy(),
            "NEW_NAME": keepers["SERIES_NAME"].to_numpy(),
            "REP_YQ": keepers["REP_YQ"].to_numpy(),
            "REPORT_DATE": keepers["REPORT_DATE"].to_numpy(),
            "AUM_M": (keepers["NET_ASSETS"] / 1e6).round(2).to_numpy(),
        }
    )

    all_targets = pd.concat(
        [
            droppers[
                ["SERIES_ID", "CIK", "COMPLEX_ID", "DROP_GROUP", "SAMPLE_ARM", "COMPLIANCE_TYPE", "OLD_NAME", "NEW_NAME", "REP_YQ", "REPORT_DATE", "AUM_M"]
            ],
            keepers_rows,
        ],
        ignore_index=True,
    )
    all_targets["CIK10"] = all_targets["CIK"].astype(str).str.strip().str.zfill(10)

    # Part A: Local N-PORT EXPLANATORY_NOTE scan
    nport_notes = scan_nport_explanatory_notes(set(all_targets["SERIES_ID"]))

    client = PoliteClient(min_interval=0.19)
    uniq_ciks = sorted(all_targets["CIK10"].unique())
    print(f"[2/4] Auditing {len(all_targets)} funds ({len(droppers)} droppers + {len(keepers_rows)} keeper controls) across {len(uniq_ciks)} unique CIKs on live SEC EDGAR...", flush=True)

    # Step 2a: Fetch CIK submissions metadata + CIK-level Rule 35d-1 and 80% policy EFTS hits (cached!)
    cik_35d1_hits: dict[str, list[dict]] = {}
    cik_80p_hits: dict[str, list[dict]] = {}
    cik_sub_497_cnt: dict[str, int] = {}

    for idx_c, cik10 in enumerate(uniq_ciks, 1):
        sub_cp = SUB_CACHE / f"CIK{cik10}.json"
        sub_j = client.get_json_cached(f"https://data.sec.gov/submissions/CIK{cik10}.json", None, sub_cp)
        if sub_j:
            rec = sub_j.get("filings", {}).get("recent", {})
            forms = rec.get("form", [])
            dates = rec.get("filingDate", [])
            cik_sub_497_cnt[cik10] = sum(
                1 for f, d in zip(forms, dates, strict=False) if f in ("497", "497K", "485BPOS", "485APOS") and d >= "2024-01-01"
            )
        else:
            cik_sub_497_cnt[cik10] = 0

        cik_35d1_hits[cik10] = efts_search(client, '"35d-1" OR "Names Rule"', cik10, "2024-01-01", "2026-09-30")
        cik_80p_hits[cik10] = efts_search(client, '"80% investment policy" OR "80% policy" OR "80% of its net assets"', cik10, "2024-01-01", "2026-09-30")
        if idx_c % 25 == 0 or idx_c == len(uniq_ciks):
            print(f"  CIK scan {idx_c}/{len(uniq_ciks)} done (live={client.n_live}, cache={client.n_cache})", flush=True)

    # Step 2b: Fund-specific name-change & Rule 35d-1 HTML verification (deduplicated doc cache!)
    print("[3/4] Downloading & verifying fund-specific 497/497K/485BPOS prospectus texts...", flush=True)
    doc_text_cache: dict[tuple[str, str, str], tuple[str, str]] = {}

    def get_doc(cik10: str, adsh: str, fname: str) -> tuple[str, str]:
        k = (cik10, adsh, fname)
        if k not in doc_text_cache:
            doc_text_cache[k] = fetch_doc_text(client, cik10, adsh, fname)
        return doc_text_cache[k]

    audit_records = []
    for i_row, row in all_targets.iterrows():
        sid = row["SERIES_ID"]
        cik10 = row["CIK10"]
        old_nm = str(row["OLD_NAME"] or "")
        new_nm = str(row["NEW_NAME"] or "")
        is_keeper = row["SAMPLE_ARM"] == "CONTROL_MA_GVI_KEEPER"

        c_35 = cik_35d1_hits.get(cik10, [])
        c_80 = cik_80p_hits.get(cik10, [])
        trust_cites_35d1 = len(c_35) > 0
        trust_cites_80p = len(c_80) > 0

        # 100% SYMMETRIC candidate retrieval protocol for BOTH Droppers and Keepers!
        # Same date window (2024-01-01..2026-09-30), same form priority, and direct fund-level EFTS
        # Rule 35d-1 & 80%-policy queries so multi-fund trusts never miss fund-specific citations!
        prio = {"497": 0, "497K": 1, "485BPOS": 2, "485APOS": 3}
        fund_cands: list[dict] = []
        seen_keys: set[tuple[str, str]] = set()

        def _add_cands(hit_list: list[dict], limit: int, seen: set[tuple[str, str]], out: list[dict]) -> None:
            for h in hit_list:
                hk = (h.get("adsh", ""), h.get("filename", ""))
                if hk[0] and hk[1] and hk not in seen:
                    seen.add(hk)
                    out.append(h)
                    limit -= 1
                    if limit <= 0:
                        break

        ph_new = best_search_phrase(new_nm)
        ph_old = best_search_phrase(old_nm)

        # (1) Fund-name match in 497/497K/485BPOS/485APOS (2024-01-01..2026-09-30)
        hits_nm = efts_search(client, f'"{ph_new}"', cik10, "2024-01-01", "2026-09-30")
        if len(hits_nm) < 2 and ph_old and ph_old != ph_new:
            hits_nm = hits_nm + efts_search(client, f'"{ph_old}"', cik10, "2024-01-01", "2026-09-30")
        hits_nm.sort(key=lambda h: (prio.get(h["form"], 9), h["file_date"]))
        _add_cands(hits_nm, 2, seen_keys, fund_cands)

        # (2) Direct fund-specific Rule 35d-1 / Names Rule EFTS query
        # NOTE: SEC EFTS requires parentheses-free quoted AND terms (e.g. `"Fund Name" "35d-1"`),
        # NOT `"Fund Name" ("35d-1" OR "Names Rule")` which returns 0 hits in EFTS!
        if trust_cites_35d1:
            hits_f35 = efts_search(client, f'"{ph_new}" "35d-1"', cik10, "2024-01-01", "2026-09-30")
            if not hits_f35:
                hits_f35 = efts_search(client, f'"{ph_new}" "Names Rule"', cik10, "2024-01-01", "2026-09-30")
            if not hits_f35 and ph_old and ph_old != ph_new:
                hits_f35 = efts_search(client, f'"{ph_old}" "35d-1"', cik10, "2024-01-01", "2026-09-30")
                if not hits_f35:
                    hits_f35 = efts_search(client, f'"{ph_old}" "Names Rule"', cik10, "2024-01-01", "2026-09-30")
            hits_f35.sort(key=lambda h: (prio.get(h["form"], 9), h["file_date"]))
            _add_cands(hits_f35, 2, seen_keys, fund_cands)

        # (3) Direct fund-specific 80% policy EFTS query if trust cites 80% policy (parentheses-free!)
        if trust_cites_80p:
            hits_f80 = efts_search(client, f'"{ph_new}" "80%"', cik10, "2024-01-01", "2026-09-30")
            if not hits_f80 and ph_old and ph_old != ph_new:
                hits_f80 = efts_search(client, f'"{ph_old}" "80%"', cik10, "2024-01-01", "2026-09-30")
            hits_f80.sort(key=lambda h: (prio.get(h["form"], 9), h["file_date"]))
            _add_cands(hits_f80, 1, seen_keys, fund_cands)

        fund_cites_35d1 = False
        fund_cites_80p = False
        has_name_change_sticker = False
        explicit_no_strategy_change = False
        eff_date: str | None = None
        best_acc = ""
        best_form = ""
        best_fdate = ""
        best_url = ""
        best_snippet_35d1 = ""
        best_snippet_nc = ""
        best_snippet_nostrat = ""
        rep_yq_val = int(row["REP_YQ"])

        eff_date_fb: str | None = None
        for cand in fund_cands:
            if not cand.get("adsh") or not cand.get("filename"):
                continue
            txt, url = get_doc(cik10, cand["adsh"], cand["filename"])
            if not txt:
                continue
            txt_lo = txt.lower()
            if not fund_matches_text(old_nm, new_nm, txt_lo):
                continue

            has_35 = bool(RE_RULE_35D1.search(txt))
            has_80 = bool(RE_80_POLICY.search(txt))
            has_nc = bool(RE_NAME_CHANGE.search(txt))
            has_ns = bool(RE_NO_STRATEGY_CHANGE.search(txt))

            if has_35 and not fund_cites_35d1:
                fund_cites_35d1 = True
                best_snippet_35d1 = extract_snippet(txt, RE_RULE_35D1)
                if not best_acc:
                    best_acc, best_form, best_fdate, best_url = cand["adsh"], cand["form"], cand["file_date"], url
            if has_80:
                fund_cites_80p = True
            if has_nc:
                has_name_change_sticker = True
                if not best_snippet_nc:
                    best_snippet_nc = extract_snippet(txt, RE_NAME_CHANGE)
                if not is_keeper and not eff_date:
                    eff_date = extract_effective_date(txt, cand["file_date"], rep_yq=rep_yq_val, form=cand["form"], allow_fallback=False)
                if not is_keeper and not eff_date and not eff_date_fb:
                    eff_date_fb = extract_effective_date(txt, cand["file_date"], rep_yq=rep_yq_val, form=cand["form"], allow_fallback=True)
                if not is_keeper or not best_acc:
                    best_acc, best_form, best_fdate, best_url = cand["adsh"], cand["form"], cand["file_date"], url
            if has_ns:
                explicit_no_strategy_change = True
                if not best_snippet_nostrat:
                    best_snippet_nostrat = extract_snippet(txt, RE_NO_STRATEGY_CHANGE)
            if not best_acc:
                best_acc, best_form, best_fdate, best_url = cand["adsh"], cand["form"], cand["file_date"], url
        if not eff_date and eff_date_fb:
            eff_date = eff_date_fb

        # Fallback receipt from CIK-level 35d-1 filing if trust cited it
        if not best_acc and c_35:
            h0 = c_35[0]
            best_acc, best_form, best_fdate = h0["adsh"], h0["form"], h0["file_date"]
            best_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{h0['adsh'].replace('-', '')}/{h0['filename']}"

        nport_note_35d1 = any(x["has_35d1"] for x in nport_notes["target_fund_hits"].get(sid, []))

        audit_records.append(
            {
                "SERIES_ID": sid,
                "CIK10": cik10,
                "COMPLEX_ID": row["COMPLEX_ID"],
                "DROP_GROUP": row["DROP_GROUP"],
                "SAMPLE_ARM": row["SAMPLE_ARM"],
                "COMPLIANCE_TYPE": row["COMPLIANCE_TYPE"],
                "OLD_NAME": old_nm,
                "NEW_NAME": new_nm,
                "REP_YQ": int(row["REP_YQ"]),
                "AUM_M": float(row["AUM_M"]) if pd.notna(row["AUM_M"]) else 0.0,
                "N_497_485_FILINGS_24_26": int(cik_sub_497_cnt.get(cik10, 0)),
                "TRUST_CITES_35D1": int(trust_cites_35d1),
                "FUND_CITES_35D1": int(fund_cites_35d1),
                "TRUST_CITES_80PCT": int(trust_cites_80p),
                "FUND_CITES_80PCT": int(fund_cites_80p),
                "HAS_NAME_CHANGE_STICKER": int(has_name_change_sticker),
                "EXPLICIT_NO_STRATEGY_CHANGE": int(explicit_no_strategy_change),
                "NPORT_EXPLANATORY_NOTE_35D1": int(nport_note_35d1),
                "EFFECTIVE_DATE": eff_date or "",
                "EFFECTIVE_YM": (eff_date[:7] if eff_date and len(eff_date) >= 7 else ""),
                "PRIMARY_FORM": best_form,
                "PRIMARY_FILE_DATE": best_fdate,
                "PRIMARY_ACCESSION": best_acc,
                "PRIMARY_URL": best_url,
                "SNIPPET_35D1": best_snippet_35d1[:240],
                "SNIPPET_NAME_CHANGE": best_snippet_nc[:240],
                "SNIPPET_NO_STRATEGY_CHANGE": best_snippet_nostrat[:240],
            }
        )
        if (i_row + 1) % 30 == 0 or (i_row + 1) == len(all_targets):
            print(f"  Fund audit {i_row + 1}/{len(all_targets)} complete (live={client.n_live}, cache={client.n_cache})", flush=True)

    res_df = pd.DataFrame(audit_records)

    # -----------------------------------------------------------------------
    # [4/4] Aggregate Summary Tables, Effective-Date Histogram & Fisher Tests
    # -----------------------------------------------------------------------
    print("[4/4] Aggregating EDGAR attribution rates & effective-date distribution...", flush=True)

    arm_summary = {}
    groups_spec = [
        ("ALL_DROPPERS", res_df["SAMPLE_ARM"] != "CONTROL_MA_GVI_KEEPER"),
        ("MULTI_ASSET_GVI_ALL", res_df["DROP_GROUP"] == "MULTI_ASSET_GVI"),
        ("MA_GVI_OPAQUE", res_df["SAMPLE_ARM"] == "MA_GVI_OPAQUE"),
        ("MA_GVI_NUMERIC", res_df["SAMPLE_ARM"] == "MA_GVI_NUMERIC"),
        ("ESG_DROPPER", res_df["SAMPLE_ARM"] == "ESG_DROPPER"),
        ("PURE_GVI_DROPPER", res_df["SAMPLE_ARM"] == "PURE_GVI_DROPPER"),
        ("CONTROL_MA_GVI_KEEPER", res_df["SAMPLE_ARM"] == "CONTROL_MA_GVI_KEEPER"),
    ]
    tbl_rows = []
    for gname, mask in groups_spec:
        sub = res_df[mask]
        n = len(sub)
        if n == 0:
            continue
        rec = {
            "group": gname,
            "n_funds": int(n),
            "aum_B": float(sub["AUM_M"].sum() / 1e3),
            "trust_cites_35d1_n": int(sub["TRUST_CITES_35D1"].sum()),
            "trust_cites_35d1_pct": float(100.0 * sub["TRUST_CITES_35D1"].mean()),
            "fund_cites_35d1_n": int(sub["FUND_CITES_35D1"].sum()),
            "fund_cites_35d1_pct": float(100.0 * sub["FUND_CITES_35D1"].mean()),
            "fund_cites_80pct_n": int(sub["FUND_CITES_80PCT"].sum()),
            "fund_cites_80pct_pct": float(100.0 * sub["FUND_CITES_80PCT"].mean()),
            "trust_cites_80pct_pct": float(100.0 * sub["TRUST_CITES_80PCT"].mean()),
            "name_change_sticker_n": int(sub["HAS_NAME_CHANGE_STICKER"].sum()),
            "name_change_sticker_pct": float(100.0 * sub["HAS_NAME_CHANGE_STICKER"].mean()),
            "no_strategy_change_n": int(sub["EXPLICIT_NO_STRATEGY_CHANGE"].sum()),
            "no_strategy_change_pct": float(100.0 * sub["EXPLICIT_NO_STRATEGY_CHANGE"].mean()),
            "no_strategy_change_of_stickers_pct": float(
                100.0 * sub["EXPLICIT_NO_STRATEGY_CHANGE"].sum() / max(int(sub["HAS_NAME_CHANGE_STICKER"].sum()), 1)
            ),
            "eff_date_parsed_n": int((sub["EFFECTIVE_DATE"] != "").sum()),
            "nport_note_35d1_n": int(sub["NPORT_EXPLANATORY_NOTE_35D1"].sum()),
        }
        arm_summary[gname] = rec
        tbl_rows.append(rec)
        print(
            f"  {gname:24s} (N={n:3d}): Trust35d1={rec['trust_cites_35d1_pct']:5.1f}% | "
            f"Fund35d1={rec['fund_cites_35d1_pct']:5.1f}% | Sticker={rec['name_change_sticker_pct']:5.1f}% | "
            f"NoStratChg={rec['no_strategy_change_pct']:5.1f}% ({rec['no_strategy_change_of_stickers_pct']:5.1f}% of stickers) | "
            f"Fund80%={rec['fund_cites_80pct_pct']:5.1f}% | EffDate={rec['eff_date_parsed_n']}",
            flush=True,
        )

    # Effective-date histogram across all droppers with parsed effective date (and specifically Multi-Asset GVI)
    drop_sub = res_df[res_df["SAMPLE_ARM"] != "CONTROL_MA_GVI_KEEPER"].copy()
    eff_all = drop_sub[drop_sub["EFFECTIVE_YM"] != ""]
    eff_ma = drop_sub[(drop_sub["DROP_GROUP"] == "MULTI_ASSET_GVI") & (drop_sub["EFFECTIVE_YM"] != "")]

    eff_ym_all = {str(k): int(v) for k, v in eff_all["EFFECTIVE_YM"].value_counts().sort_index().items()}
    eff_ym_ma = {str(k): int(v) for k, v in eff_ma["EFFECTIVE_YM"].value_counts().sort_index().items()}
    exact_may1_2025_all = int((eff_all["EFFECTIVE_DATE"] == "2025-05-01").sum())
    exact_may1_2025_ma = int((eff_ma["EFFECTIVE_DATE"] == "2025-05-01").sum())
    exact_apr_jun_2025_ma = int(eff_ma["EFFECTIVE_YM"].isin(["2025-04", "2025-05", "2025-06"]).sum())
    exact_apr_jun_2026_ma = int(eff_ma["EFFECTIVE_YM"].isin(["2026-04", "2026-05", "2026-06"]).sum())

    # Fisher exact comparisons: Multi-Asset Droppers vs Keeper Controls on Rule 35d-1 & 80% policy
    ma_d = res_df[res_df["DROP_GROUP"] == "MULTI_ASSET_GVI"]
    kp_c = res_df[res_df["SAMPLE_ARM"] == "CONTROL_MA_GVI_KEEPER"]
    _, p_35d1_trust = stats.fisher_exact(
        [
            [int(ma_d["TRUST_CITES_35D1"].sum()), int((ma_d["TRUST_CITES_35D1"] == 0).sum())],
            [int(kp_c["TRUST_CITES_35D1"].sum()), int((kp_c["TRUST_CITES_35D1"] == 0).sum())],
        ]
    )
    _, p_35d1_fund = stats.fisher_exact(
        [
            [int(ma_d["FUND_CITES_35D1"].sum()), int((ma_d["FUND_CITES_35D1"] == 0).sum())],
            [int(kp_c["FUND_CITES_35D1"].sum()), int((kp_c["FUND_CITES_35D1"] == 0).sum())],
        ]
    )
    _, p_80_fund = stats.fisher_exact(
        [
            [int(ma_d["FUND_CITES_80PCT"].sum()), int((ma_d["FUND_CITES_80PCT"] == 0).sum())],
            [int(kp_c["FUND_CITES_80PCT"].sum()), int((kp_c["FUND_CITES_80PCT"] == 0).sum())],
        ]
    )

    # Save full machine-readable receipts & summary CSV/JSON
    full_json_path = WORK_DIR / "data" / "edgar_prospectus_audit.json"
    full_json_path.write_text(json.dumps(audit_records, indent=2) + "\n", encoding="utf-8", newline="\n")

    tbl_csv_path = WORK_DIR / "tables" / "table_edgar_prospectus_attribution.csv"
    pd.DataFrame(tbl_rows).to_csv(tbl_csv_path, index=False, lineterminator="\n")

    summary_out = {
        "nport_explanatory_notes": {
            "quarterly_counts": nport_notes["quarterly_counts"],
            "n_target_funds_with_nport_note": len(nport_notes["target_fund_hits"]),
        },
        "arm_summary": arm_summary,
        "effective_date_clustering": {
            "n_droppers_with_parsed_eff_date": len(eff_all),
            "n_ma_gvi_with_parsed_eff_date": len(eff_ma),
            "exact_2025_05_01_all_droppers": exact_may1_2025_all,
            "exact_2025_05_01_ma_gvi": exact_may1_2025_ma,
            "ma_gvi_2025_apr_jun_count": exact_apr_jun_2025_ma,
            "ma_gvi_2026_apr_jun_count": exact_apr_jun_2026_ma,
            "monthly_histogram_all_droppers": eff_ym_all,
            "monthly_histogram_ma_gvi": eff_ym_ma,
        },
        "fisher_tests_ma_droppers_vs_keepers": {
            "p_2sided_trust_cites_35d1": float(p_35d1_trust),
            "p_2sided_fund_cites_35d1": float(p_35d1_fund),
            "p_2sided_fund_cites_80pct": float(p_80_fund),
        },
        "flagship_verbatim_receipts": [
            r
            for r in audit_records
            if r["SAMPLE_ARM"] in ("MA_GVI_OPAQUE", "MA_GVI_NUMERIC", "ESG_DROPPER", "PURE_GVI_DROPPER")
            and (r["SNIPPET_35D1"] or r["SNIPPET_NO_STRATEGY_CHANGE"])
        ][:20],
    }
    sum_path = WORK_DIR / "results" / "02_edgar_audit_summary.json"
    sum_path.write_text(json.dumps(summary_out, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("\n=== PILLAR 2 EFFECTIVE DATE CLUSTERING ===", flush=True)
    print(f"  Parsed effective dates: {len(eff_all)} droppers ({len(eff_ma)} Multi-Asset GVI)", flush=True)
    print(f"  EXACT May 1, 2025 effective date: {exact_may1_2025_all} droppers ({exact_may1_2025_ma} Multi-Asset GVI)!", flush=True)
    print(f"  Monthly effective-date histogram (MA GVI): {eff_ym_ma}", flush=True)
    print(f"  Saved {full_json_path.name}, {tbl_csv_path.name}, and {sum_path.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
