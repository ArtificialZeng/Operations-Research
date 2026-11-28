"""Per-Fund Statutory 80% Policy, Fiscal-Year-End $1B Tier, On-Cycle Effective-Date,
and Dual-Pass EDGAR Disclosure Audit across ALL 50 Primary Multi-Asset GVI Renamers,
a Stratified Control Sample of 50 Retained-Name Multi-Asset GVI Funds, and a
Same-Date Unregulated-Word Renaming Control Group.

Strictly addresses Peer Review I4 P0 #1:
  - Links every fund via Registrant CIK10 + Fund SERIES_ID + unified COMPLEX_ID.
  - Determines the $1B Large vs. Small Group tier under SEC Release 33-11368 using
    most-recent fiscal-year-end complex net assets (plus pre-rule 2023Q2 AUM).
  - Computes each fund's first eligible on-cycle annual prospectus update window on
    or after June 11, 2026 (Large >= $1B) or December 11, 2026 (Small < $1B) using
    N-PORT fund-level FYE_MONTH cross-checked against EDGAR 485BPOS filing history.
  - Performs a transparent two-pass independent audit (Pass 1: baseline script-02
    automated parser; Pass 2: deep fund-scoped pre-/post-rename 497/497K/485BPOS
    disclosure inspection), preserving exact disagreements, SEC URLs, and verbatim
    text snippets (explicitly documenting Vanguard's unchanged-policy confirmation,
    iShares' simultaneous benchmark-index rename, and Prudential/AST's same-filing
    non-GVI co-renames).
  - Evaluates the 35/50 Growth/Value-without-Income subset strictly as a lexical
    screen and reports exact precision/recall against audited EDGAR disclosures.
  - Constructs a cleaned same-date unregulated-word renaming control group excluding
    punctuation/trademark-only cosmetic name edits.
"""

from __future__ import annotations

import hashlib
import html as html_mod
import json
import re
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests

WORK_DIR = Path(__file__).resolve().parents[1]
DATA_DIR = WORK_DIR / "data"
CACHE_DIR = DATA_DIR / "edgar_cache"
SUB_CACHE = CACHE_DIR / "submissions"
EFTS_CACHE = CACHE_DIR / "efts"
DOC_CACHE = CACHE_DIR / "docs"
TABLES_DIR = WORK_DIR / "tables"
RESULTS_DIR = WORK_DIR / "results"
for d in (CACHE_DIR, SUB_CACHE, EFTS_CACHE, DOC_CACHE, TABLES_DIR, RESULTS_DIR):
    d.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "AcademicResearch/1.0 (mailto:zijianzeng@foxmail.com)",
    "Accept-Encoding": "gzip, deflate",
}

RE_SCRIPT_STYLE = re.compile(r"<(?:script|style)[^>]*>.*?</(?:script|style)>", re.IGNORECASE | re.DOTALL)
RE_HTML_TAG = re.compile(r"<[^>]+>")

RE_RULE_35D1 = re.compile(
    r"(?:rule\s+35d[\-\u2010-\u2015\s]?1|\b35d[\-\u2010-\u2015\s]?1\b|amended\s+names?\s+rule|\bnames?\s+rule\b)",
    re.IGNORECASE,
)
RE_80_POLICY = re.compile(
    r"(?:80%\s+(?:investment\s+)?polic|at\s+least\s+80%\s+of\s+(?:the\s+|its\s+)?(?:net\s+)?assets|"
    r"80%\s+(?:of\s+(?:the\s+|its\s+)?(?:net\s+)?assets|threshold|requirement|basket|names?\s+rule))",
    re.IGNORECASE,
)
RE_UNCHANGED_POLICY = re.compile(
    r"(?:(?:investment\s+objective|objectives?,?\s+principal\s+investment\s+strategies|strategies|polic(?:y|ies)|portfolio\s+management)[^.]{0,120}"
    r"(?:will\s+remain\s+unchanged|remain\s+unchanged|remain\s+the\s+same|will\s+not\s+change|are\s+not\s+changing|have\s+not\s+changed|do\s+not\s+change)"
    r"|no\s+change(?:s)?\s+(?:to|in)\s+(?:the\s+|each\s+)?(?:fund'?s?|portfolio'?s?)?\s*"
    r"(?:principal\s+)?(?:investment\s+)?(?:objective|strateg|polic|management))",
    re.IGNORECASE,
)
RE_BENCHMARK_INDEX_RENAME = re.compile(
    r"(?:(?:underlying|benchmark|target|broad[\-\s]based)\s+index(?:es)?[^.]{0,120}(?:rename|name\s+change|change(?:d|s)?\s+(?:its\s+)?name|will\s+be\s+changed\s+to|formerly\s+known\s+as)"
    r"|index\s+name\s+change|(?:s&p|msci|ftse|russell|bloomberg|morningstar)\s+[^.]{0,90}(?:will\s+change\s+its\s+name|renamed\s+to|formerly\s+known\s+as))",
    re.IGNORECASE,
)
RE_STRATEGY_CHANGE = re.compile(
    r"(?:(?:change(?:s|d)?|modif(?:y|ied|ication)|revis(?:e|ed|ion)|updat(?:e|ed)|amend(?:ed|ment))\s+(?:to|in)\s+(?:the\s+|each\s+)?(?:fund'?s?|portfolio'?s?)?\s*"
    r"(?:principal\s+investment\s+strateg|80%\s+(?:investment\s+)?polic|investment\s+objective|sub[\-\s]?advis)"
    r"|new\s+(?:sub[\-\s]?advis|80%\s+(?:investment\s+)?polic|principal\s+investment\s+strateg))",
    re.IGNORECASE,
)
RE_NAME_CHANGE = re.compile(
    r"(?:(?:fund|portfolio|etf|series)\s+name\s+change|name\s+change(?:s)?\s+(?:for|of|to)\s+(?:the\s+|each\s+)?(?:fund|portfolio|etf)|"
    r"(?:fund|portfolio|etf|series)(?:'s)?\s+(?:name\s+)?(?:will\s+change|has\s+changed|changed\s+its\s+name|change\s+its\s+name|will\s+be\s+renamed|has\s+been\s+renamed)|"
    r"the\s+name\s+of\s+(?:the\s+|each\s+)?(?:fund|portfolio|etf)\s+will\s+change|"
    r"prior\s+(?:fund|portfolio)\s+name|current\s+(?:fund|portfolio)\s+name|new\s+(?:fund|portfolio)\s+name|"
    r"(?:fund|portfolio|etf)\s+(?:was\s+)?formerly\s+known\s+as|formerly,?\s+|"
    r"name\s+changes?\s+effective\s+(?:on\s+|as\s+of\s+|today|immediately))",
    re.IGNORECASE,
)
MONTHS_PAT = r"(?:January|February|March|April|May|June|July|August|September|October|November|December)"
RE_EFF_DATE = re.compile(
    rf"(?:effective\s+(?:on\s+or\s+about\s+|as\s+of\s+|at\s+the\s+close\s+of\s+business\s+on\s+|on\s+)?"
    rf"({MONTHS_PAT}\s+\d{{1,2}},\s+202[456])"
    rf"|prior\s+to\s+({MONTHS_PAT}\s+\d{{1,2}},\s+202[456])"
    rf"|on\s+or\s+about\s+({MONTHS_PAT}\s+\d{{1,2}},\s+202[456]))",
    re.IGNORECASE,
)
RE_PROSP_DATED = re.compile(
    rf"(?:prospectus(?:es)?\s+dated|summary\s+prospectus\s+dated|supplement\s+dated|dated)\s+({MONTHS_PAT}\s+\d{{1,2}},\s+202[456])",
    re.IGNORECASE,
)

STOPWORDS = {
    "fund", "funds", "portfolio", "portfolios", "trust", "series", "etf", "index",
    "the", "of", "and", "inc", "class", "shares", "investor", "advisors", "advisor",
    "investment", "investments", "mutual", "group", "vip", "ast", "sa", "vp", "us", "u.s.",
}

# Verified manual gold-standard overrides from direct primary-filing reading (v3 + v4 inspection)
VERIFIED_PRIMARY_CASES: dict[str, dict] = {
    "S000002928": {
        "eff_date": "2026-05-12",
        "unchanged_policy": 1,
        "index_rename": 0,
        "same_filing_unreg": 0,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/736054/000073605426000102/f45201d1.htm",
        "note": "Vanguard 497 (2026-05-12) confirms objectives, strategies, and policies remain unchanged; no fund-specific Rule 35d-1 rationale given.",
    },
    "S000002930": {
        "eff_date": "2026-05-12",
        "unchanged_policy": 1,
        "index_rename": 0,
        "same_filing_unreg": 0,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/736054/000073605426000102/f45201d1.htm",
        "note": "Vanguard 497 (2026-05-12) confirms objectives, strategies, and policies remain unchanged; no fund-specific Rule 35d-1 rationale given.",
    },
    "S000002927": {
        "eff_date": "2026-05-12",
        "unchanged_policy": 1,
        "index_rename": 0,
        "same_filing_unreg": 0,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/736054/000073605426000102/f45201d1.htm",
        "note": "Vanguard 497 (2026-05-12) confirms objectives, strategies, and policies remain unchanged; no fund-specific Rule 35d-1 rationale given.",
    },
    "S000002929": {
        "eff_date": "2026-05-12",
        "unchanged_policy": 1,
        "index_rename": 0,
        "same_filing_unreg": 0,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/736054/000073605426000102/f45201d1.htm",
        "note": "Vanguard 497 (2026-05-12) confirms objectives, strategies, and policies remain unchanged; no fund-specific Rule 35d-1 rationale given.",
    },
    "S000006796": {
        "eff_date": "2025-05-01",
        "unchanged_policy": 0,
        "index_rename": 0,
        "same_filing_unreg": 1,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/814679/000168386325002126/f41066d1.htm",
        "note": "AST/Prudential 497 (eff. 2025-05-01) renames two GVI funds alongside two non-GVI portfolios in the same trust-wide supplement; no fund-specific 35d-1 attribution.",
    },
    "S000006791": {
        "eff_date": "2025-05-01",
        "unchanged_policy": 0,
        "index_rename": 0,
        "same_filing_unreg": 1,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/814679/000168386325002126/f41066d1.htm",
        "note": "AST/Prudential 497 (eff. 2025-05-01) renames two GVI funds alongside two non-GVI portfolios in the same trust-wide supplement; no fund-specific 35d-1 attribution.",
    },
    "S000023587": {
        "eff_date": "2025-02-19",
        "unchanged_policy": 0,
        "index_rename": 1,
        "same_filing_unreg": 0,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1100663/000119312525028799/d892616d497.htm",
        "note": "iShares 497 (eff. 2025-02-19) simultaneously renames the underlying S&P Target Risk benchmark index alongside the ETF name.",
    },
    "S000068731": {
        "eff_date": "2025-02-19",
        "unchanged_policy": 0,
        "index_rename": 1,
        "same_filing_unreg": 0,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/1100663/000119312525028799/d892616d497.htm",
        "note": "iShares 497 (eff. 2025-02-19) simultaneously renames underlying/additional benchmark indices alongside the ETF name.",
    },
    "S000017667": {
        "eff_date": "2025-04-30",
        "unchanged_policy": 0,
        "index_rename": 0,
        "same_filing_unreg": 0,
        "filing_url": "https://www.sec.gov/Archives/edgar/data/823535/000082353525000230/filing8658.htm",
        "note": "Fidelity VIP registrant filing dates the Growth-to-70% rename April 30, 2025 (some insurance product supplements cite May 1, 2025).",
    },
}


class PoliteClient:
    def __init__(self, min_interval: float = 0.20):
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
            except (OSError, json.JSONDecodeError):
                pass
        for att in range(3):
            self._throttle()
            try:
                r = self.sess.get(url, params=params, timeout=20)
                if r.status_code == 200:
                    self.n_live += 1
                    data = r.json()
                    cache_path.write_text(json.dumps(data), encoding="utf-8")
                    return data
                if r.status_code in (429, 500, 502, 503, 504):
                    time.sleep(2.0 * (att + 1))
                    continue
                return None
            except (requests.RequestException, ValueError):
                time.sleep(1.5 * (att + 1))
        return None

    def get_text_cached(self, url: str, cache_path: Path, max_bytes: int = 6_000_000) -> str | None:
        if cache_path.exists():
            self.n_cache += 1
            try:
                return cache_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                pass
        for att in range(3):
            self._throttle()
            try:
                r = self.sess.get(url, timeout=20, stream=True)
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


def html_to_clean_text(raw_html: str) -> str:
    if "<" in raw_html and ">" in raw_html:
        txt = RE_SCRIPT_STYLE.sub(" ", raw_html)
        txt = RE_HTML_TAG.sub(" ", txt)
        txt = html_mod.unescape(txt)
    else:
        txt = raw_html
    return re.sub(r"\s+", " ", txt).strip()


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


def normalize_substantive_name(name: str) -> str:
    """Strip trademark symbols, punctuation, and whitespace to detect genuine word-level renames."""
    s = (name or "").lower()
    s = re.sub(r"\(r\)|\(sm\)|\(tm\)|®|™|℠", " ", s)
    s = re.sub(r"\binc\.?\b|\bcorp\.?\b", " ", s)
    s = re.sub(r"[^a-z0-9/%]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def distinctive_tokens(name: str) -> list[str]:
    clean = re.sub(r"[^A-Za-z0-9/%&\-\s]+", " ", (name or "").lower())
    return [t for t in clean.split() if len(t) >= 3 and t not in STOPWORDS]


def extract_fund_windows(text: str, old_name: str, new_name: str, radius: int = 2200) -> list[str]:
    """Extract fund-scoped text windows centered around exact or near-exact fund name mentions."""
    txt_lo = text.lower()
    anchors: list[int] = []
    for nm in (new_name, old_name):
        if not nm:
            continue
        clean = re.sub(r"\s+", " ", re.sub(r"[^A-Za-z0-9/%&\-\s]+", " ", nm.lower())).strip()
        if len(clean) >= 8:
            start = 0
            while len(anchors) < 12:
                pos = txt_lo.find(clean, start)
                if pos < 0:
                    break
                anchors.append(pos)
                start = pos + max(len(clean), 500)
        # Shorter distinctive core phrase (first 4 non-stopword tokens or without trust prefix)
        toks = distinctive_tokens(nm)
        if not anchors and len(toks) >= 2:
            pat = re.compile(r"\b" + r"\W+(?:\w+\W+){0,3}".join(re.escape(t) for t in toks[:3]) + r"\b", re.IGNORECASE)
            for m in list(pat.finditer(text))[:6]:
                anchors.append(m.start())
    # Deduplicate overlapping windows
    anchors.sort()
    windows: list[str] = []
    last_end = -1
    for a in anchors:
        lo = max(0, a - radius)
        hi = min(len(text), a + radius)
        if lo < last_end and windows:
            prev_lo = max(0, last_end - 2 * radius)
            windows[-1] = text[prev_lo:hi]
        else:
            windows.append(text[lo:hi])
        last_end = hi
    return windows


def extract_snippet(text: str, pat: re.Pattern[str], radius: int = 115) -> str:
    m = pat.search(text)
    if not m:
        return ""
    lo = max(0, m.start() - radius)
    hi = min(len(text), m.end() + radius)
    return re.sub(r"\s+", " ", text[lo:hi]).strip()


def compute_first_eligible_oncycle(fye_month: int, is_large: bool) -> tuple[str, str]:
    """Compute statutory first eligible on-cycle annual prospectus update under SEC Release 33-11368.

    Under Form N-1A / Rule 485(b), open-end funds file their annual prospectus update within
    120 days (approx. 4 calendar months) after fiscal year end (e.g., Dec 31 FYE -> ~May 1;
    Oct 31 FYE -> ~Feb 28/Mar 1; Mar 31 FYE -> ~Jul 29/Aug 1).
    Under Release 33-11368, Large Group (>= $1B at most recent FYE) compliance begins at the
    first on-cycle annual update filed on or after June 11, 2026; Small Group (< $1B) begins
    on or after December 11, 2026.
    """
    cutoff = date(2026, 6, 11) if is_large else date(2026, 12, 11)
    # Approximate standard annual update date = FYE end-of-month + 120 days
    for yr in (2025, 2026, 2027):
        if fye_month == 12:
            fye_d = date(yr, 12, 31)
        else:
            fye_d = date(yr, fye_month + 1, 1) - timedelta(days=1)
        upd_d = fye_d + timedelta(days=120)
        if upd_d >= cutoff:
            tier = "LARGE_GE_1B_JUN11_2026" if is_large else "SMALL_LT_1B_DEC11_2026"
            return tier, upd_d.isoformat()
    tier = "LARGE_GE_1B_JUN11_2026" if is_large else "SMALL_LT_1B_DEC11_2026"
    return tier, "2027-05-01"


def date_near_rep_yq(date_str: str | None, rep_yq: int) -> bool:
    if not date_str:
        return False
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return False
    yr, q = rep_yq // 10, rep_yq % 10
    q_start = datetime(yr, (q - 1) * 3 + 1, 1)
    q_end = datetime(yr, q * 3, 28)
    return (q_start.toordinal() - 180) <= dt.toordinal() <= (q_end.toordinal() + 90)


def find_effective_date_in_windows(windows: list[str], full_text: str, file_date: str, rep_yq: int, form: str) -> str:
    for win in windows:
        for m in RE_EFF_DATE.finditer(win):
            raw_d = m.group(1) or m.group(2) or m.group(3)
            parsed = parse_date_str(raw_d)
            if parsed and date_near_rep_yq(parsed, rep_yq):
                return parsed
    for m in RE_EFF_DATE.finditer(full_text[:6000]):
        raw_d = m.group(1) or m.group(2) or m.group(3)
        parsed = parse_date_str(raw_d)
        if parsed and date_near_rep_yq(parsed, rep_yq):
            return parsed
    if form in ("497", "497K", "485BPOS"):
        for m in RE_PROSP_DATED.finditer(full_text[:4000]):
            parsed = parse_date_str(m.group(1))
            if parsed and date_near_rep_yq(parsed, rep_yq):
                return parsed
        if date_near_rep_yq(file_date, rep_yq):
            return file_date
    return ""


def efts_search(client: PoliteClient, q: str, cik10: str, startdt: str = "2023-01-01", enddt: str = "2026-10-31") -> list[dict]:
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
    out = []
    for h in data.get("hits", {}).get("hits", []):
        src = h.get("_source", {})
        hid = h.get("_id", "")
        adsh = src.get("adsh", "")
        fname = hid.split(":", 1)[1] if ":" in hid else ""
        if adsh and fname:
            out.append({
                "form": src.get("form", ""),
                "file_date": src.get("file_date", ""),
                "adsh": adsh,
                "filename": fname,
            })
    return out


def fetch_doc_text(client: PoliteClient, cik10: str, adsh: str, filename: str) -> tuple[str, str]:
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
    print("[1/5] Loading panel, baseline EDGAR audit, and computing FYE complex AUM tiers...", flush=True)
    qtr = pd.read_parquet(
        DATA_DIR / "panel_quarterly.parquet",
        columns=[
            "SERIES_ID", "CIK", "COMPLEX_ID", "REP_YQ", "REPORT_DATE", "REPORT_DT",
            "FYE_DT", "FYE_MONTH", "NET_ASSETS", "PREV_NET_ASSETS",
            "SERIES_NAME", "PREV_SERIES_NAME", "IS_ALLOC_FUND", "PREV_IS_ALLOC_FUND",
            "IS_VA_INSURANCE", "IS_FOF", "IS_ETF", "IS_INDEX",
            "HAS_GV", "HAS_INCOME", "HAS_GVI", "HAS_ESG", "HAS_LEGACY",
            "PREV_HAS_GV", "PREV_HAS_INCOME", "PREV_HAS_GVI", "PREV_HAS_ESG", "PREV_HAS_LEGACY",
            "ANY_RENAME", "DROP_GVI", "DROP_ESG", "DROP_LEGACY", "COMPLIANCE_TYPE",
            "COMPLEX_TNA_23Q2", "COMPLEX_TNA_24Q4",
        ],
    )
    qtr["CIK10"] = qtr["CIK"].astype(str).str.strip().str.zfill(10)

    # Complex AUM at most recent complete fiscal year-end before June 11, 2026 (2025Q1-2026Q1 latest complete quarter per complex)
    # Using each complex's latest complete quarter at or before 2026Q1 (and specifically matching FYE quarter where available)
    cplx_qtr_aum = qtr[qtr["REP_YQ"] <= 20261].groupby(["COMPLEX_ID", "REP_YQ"])["NET_ASSETS"].sum().reset_index()

    def get_fye_complex_aum_b(complex_id: str, fye_month: int) -> tuple[float, int]:
        # Most recent fiscal-year-end quarter <= 2026Q1
        fye_q = (fye_month - 1) // 3 + 1
        sub = cplx_qtr_aum[cplx_qtr_aum["COMPLEX_ID"] == complex_id]
        if len(sub) == 0:
            return np.nan, 0
        # Target exact FYE quarter in 2025 or 2026Q1
        cands = sub[(sub["REP_YQ"] % 10 == fye_q) & (sub["REP_YQ"] >= 20251) & (sub["REP_YQ"] <= 20261)]
        if len(cands) > 0:
            r = cands.sort_values("REP_YQ").iloc[-1]
            return float(r["NET_ASSETS"] / 1e9), int(r["REP_YQ"])
        # Fallback: latest quarter <= 2026Q1 for that complex
        r = sub.sort_values("REP_YQ").iloc[-1]
        return float(r["NET_ASSETS"] / 1e9), int(r["REP_YQ"])

    # -----------------------------------------------------------------------
    # [2/5] Build Cleaned Same-Date Unregulated-Word Renaming Control Group
    # -----------------------------------------------------------------------
    print("[2/5] Constructing cleaned same-date unregulated-word renaming control group...", flush=True)
    ren_all = qtr[qtr["ANY_RENAME"] == 1].copy()
    ren_all["NORM_OLD"] = ren_all["PREV_SERIES_NAME"].map(normalize_substantive_name)
    ren_all["NORM_NEW"] = ren_all["SERIES_NAME"].map(normalize_substantive_name)
    ren_all["IS_SUBSTANTIVE_RENAME"] = (ren_all["NORM_OLD"] != ren_all["NORM_NEW"]).astype(int)
    ren_all["IS_UNREGULATED_RENAME"] = (
        (ren_all["IS_SUBSTANTIVE_RENAME"] == 1)
        & (ren_all["DROP_GVI"] == 0)
        & (ren_all["DROP_ESG"] == 0)
        & (ren_all["DROP_LEGACY"] == 0)
    ).astype(int)

    unreg_ma_25_26 = ren_all[
        (ren_all["REP_YQ"] >= 20251)
        & (ren_all["PREV_IS_ALLOC_FUND"] == 1)
        & (ren_all["IS_UNREGULATED_RENAME"] == 1)
    ].sort_values(["SERIES_ID", "REP_YQ"]).drop_duplicates("SERIES_ID", keep="first").copy()

    # Map same-complex-quarter unregulated multi-asset (and all-fund) co-renames
    unreg_by_cplx_yq_ma = (
        ren_all[(ren_all["IS_UNREGULATED_RENAME"] == 1) & (ren_all["PREV_IS_ALLOC_FUND"] == 1)]
        .groupby(["COMPLEX_ID", "REP_YQ"])["SERIES_ID"]
        .nunique()
        .to_dict()
    )
    unreg_by_cplx_yq_all = (
        ren_all[ren_all["IS_UNREGULATED_RENAME"] == 1]
        .groupby(["COMPLEX_ID", "REP_YQ"])["SERIES_ID"]
        .nunique()
        .to_dict()
    )
    unreg_ma_export = unreg_ma_25_26[
        ["SERIES_ID", "CIK10", "COMPLEX_ID", "REP_YQ", "REPORT_DATE", "PREV_SERIES_NAME", "SERIES_NAME", "IS_VA_INSURANCE", "IS_FOF", "IS_ETF", "PREV_NET_ASSETS"]
    ].copy()
    unreg_ma_export["AUM_M"] = (unreg_ma_export["PREV_NET_ASSETS"].fillna(0.0) / 1e6).round(2)
    unreg_ma_export = unreg_ma_export.drop(columns=["PREV_NET_ASSETS"]).rename(
        columns={"PREV_SERIES_NAME": "PRE_NAME", "SERIES_NAME": "POST_NAME"}
    )
    unreg_ma_export.to_csv(TABLES_DIR / "table_unregulated_renamers_control.csv", index=False, lineterminator="\n")
    print(
        f"  Substantive unregulated-word multi-asset renames (2025Q1-2026Q3): {len(unreg_ma_export)} funds "
        f"across {unreg_ma_export['COMPLEX_ID'].nunique()} complexes (${unreg_ma_export['AUM_M'].sum() / 1e3:.2f}B; "
        f"excluded {(ren_all[(ren_all['REP_YQ'] >= 20251) & (ren_all['PREV_IS_ALLOC_FUND'] == 1) & (ren_all['IS_SUBSTANTIVE_RENAME'] == 0)]).shape[0]} cosmetic trademark/punctuation edits).",
        flush=True,
    )

    # -----------------------------------------------------------------------
    # [3/5] Load ALL 50 Primary MA GVI Renamers + Stratified 50 Retained Controls
    # -----------------------------------------------------------------------
    ed_base = pd.read_json(DATA_DIR / "edgar_prospectus_audit.json", dtype={"CIK10": str})
    ed_base["CIK10"] = ed_base["CIK10"].astype(str).str.strip().str.zfill(10)
    ma_ren = ed_base[ed_base["DROP_GROUP"] == "MULTI_ASSET_GVI"].copy().reset_index(drop=True)
    assert len(ma_ren) == 50, f"Expected 50 MA GVI renamers, got {len(ma_ren)}"

    # Stratified sample of 50 retained-name MA GVI funds (including BOTH <$1B and >=$1B complexes, VA vs Retail, GV vs Income!)
    dropped_sids = set(ed_base[ed_base["SAMPLE_ARM"] != "CONTROL_MA_GVI_KEEPER"]["SERIES_ID"])
    ret_pool = (
        qtr[
            (qtr["REP_YQ"] >= 20251)
            & (qtr["PREV_IS_ALLOC_FUND"] == 1)
            & (qtr["PREV_HAS_GVI"] == 1)
            & (qtr["HAS_GVI"] == 1)
            & (~qtr["SERIES_ID"].isin(dropped_sids))
        ]
        .sort_values(["SERIES_ID", "REP_YQ"])
        .drop_duplicates("SERIES_ID", keep="last")
        .copy()
    )
    # Preferentially include the 50 cached EDGAR keeper controls + ensure <$1B small complexes represented cleanly
    cached_keepers = ed_base[ed_base["SAMPLE_ARM"] == "CONTROL_MA_GVI_KEEPER"].copy().reset_index(drop=True)
    # Build stratified 50: take all available <$1B retained MA GVI funds (up to 10) + 40 stratified from cached keepers
    ret_pool["IS_SMALL"] = (ret_pool["COMPLEX_TNA_23Q2"].fillna(2e9) < 1e9).astype(int)
    small_ret = ret_pool[ret_pool["IS_SMALL"] == 1].sort_values("NET_ASSETS", ascending=False).head(10).copy()
    # From cached_keepers, sample 50 - len(small_ret) stratified by VA and GV-no-Income
    k_meta = cached_keepers.merge(
        ret_pool[["SERIES_ID", "IS_VA_INSURANCE", "HAS_GV", "HAS_INCOME"]], on="SERIES_ID", how="left"
    )
    k_meta["STRAT"] = (
        k_meta["IS_VA_INSURANCE"].fillna(0).astype(int).astype(str)
        + "_"
        + ((k_meta["HAS_GV"].fillna(0) == 1) & (k_meta["HAS_INCOME"].fillna(0) == 0)).astype(int).astype(str)
    )
    rng = np.random.default_rng(20261128)
    n_large_pick = 50 - len(small_ret)
    # Deterministic stratified pick from cached_keepers
    picked_ids: list[str] = []
    for _, grp in k_meta.groupby("STRAT"):
        share = max(1, round(n_large_pick * len(grp) / len(k_meta)))
        take = min(len(grp), share)
        picked_ids.extend(grp.iloc[sorted(rng.choice(len(grp), size=take, replace=False))]["SERIES_ID"].tolist())
    # Trim or pad to exact n_large_pick
    picked_ids = list(dict.fromkeys(picked_ids))
    if len(picked_ids) > n_large_pick:
        picked_ids = picked_ids[:n_large_pick]
    elif len(picked_ids) < n_large_pick:
        rem = [s for s in cached_keepers["SERIES_ID"] if s not in set(picked_ids)]
        picked_ids.extend(rem[: n_large_pick - len(picked_ids)])

    large_ret = cached_keepers[cached_keepers["SERIES_ID"].isin(set(picked_ids))].copy()
    small_rows = pd.DataFrame({
        "SERIES_ID": small_ret["SERIES_ID"].to_numpy(),
        "CIK10": small_ret["CIK10"].to_numpy(),
        "COMPLEX_ID": small_ret["COMPLEX_ID"].to_numpy(),
        "DROP_GROUP": "CONTROL_MA_GVI_KEEPER_SMALL",
        "SAMPLE_ARM": "CONTROL_MA_GVI_KEEPER",
        "COMPLIANCE_TYPE": "KEEPER",
        "OLD_NAME": small_ret["SERIES_NAME"].to_numpy(),
        "NEW_NAME": small_ret["SERIES_NAME"].to_numpy(),
        "REP_YQ": small_ret["REP_YQ"].to_numpy(),
        "AUM_M": (small_ret["NET_ASSETS"].fillna(0.0) / 1e6).round(2).to_numpy(),
        "TRUST_CITES_35D1": 0,
        "FUND_CITES_35D1": 0,
        "TRUST_CITES_80PCT": 0,
        "FUND_CITES_80PCT": 0,
        "HAS_NAME_CHANGE_STICKER": 0,
        "EXPLICIT_NO_STRATEGY_CHANGE": 0,
        "EFFECTIVE_DATE": "",
        "PRIMARY_FORM": "",
        "PRIMARY_FILE_DATE": "",
        "PRIMARY_ACCESSION": "",
        "PRIMARY_URL": "",
        "SNIPPET_35D1": "",
        "SNIPPET_NAME_CHANGE": "",
        "SNIPPET_NO_STRATEGY_CHANGE": "",
    })
    strat_ret = pd.concat([large_ret, small_rows], ignore_index=True)
    assert len(strat_ret) == 50, f"Expected 50 stratified retained funds, got {len(strat_ret)}"

    # Latest N-PORT metadata per series
    s_meta = (
        qtr.sort_values(["SERIES_ID", "REP_YQ"])
        .drop_duplicates("SERIES_ID", keep="last")
        .set_index("SERIES_ID")
    )

    # -----------------------------------------------------------------------
    # [4/5] Deep Two-Pass Per-Fund Audit across ALL 50 Renamers & 50 Retained
    # -----------------------------------------------------------------------
    print("[3/5] Running two-pass fund-scoped EDGAR audit across 50 renamers + 50 stratified retained funds...", flush=True)
    client = PoliteClient(min_interval=0.20)
    doc_cache_mem: dict[tuple[str, str, str], tuple[str, str]] = {}

    def get_doc(cik10: str, adsh: str, fname: str) -> tuple[str, str]:
        k = (cik10, adsh, fname)
        if k not in doc_cache_mem:
            doc_cache_mem[k] = fetch_doc_text(client, cik10, adsh, fname)
        return doc_cache_mem[k]

    def audit_fund_group(df_grp: pd.DataFrame, is_renamer_group: bool) -> pd.DataFrame:
        rows_out = []
        for idx_r, row in df_grp.iterrows():
            sid = str(row["SERIES_ID"])
            cik10 = str(row["CIK10"]).zfill(10)
            cplx = str(row["COMPLEX_ID"])
            old_nm = str(row["OLD_NAME"] or "").strip()
            new_nm = str(row["NEW_NAME"] or "").strip()
            rep_yq = int(row["REP_YQ"])
            aum_m = float(row["AUM_M"])

            # Fund-level metadata from N-PORT
            sm = s_meta.loc[sid] if sid in s_meta.index else None
            fye_mo = int(sm["FYE_MONTH"]) if (sm is not None and pd.notna(sm["FYE_MONTH"])) else 12
            is_va = int(sm["IS_VA_INSURANCE"]) if sm is not None else 0
            is_fof = int(sm["IS_FOF"]) if sm is not None else 0
            is_etf = int(sm["IS_ETF"]) if sm is not None else 0
            is_idx = int(sm["IS_INDEX"]) if sm is not None else 0
            cplx_aum_23_b = float(sm["COMPLEX_TNA_23Q2"] / 1e9) if (sm is not None and pd.notna(sm["COMPLEX_TNA_23Q2"])) else np.nan
            cplx_aum_fye_b, fye_aum_yq = get_fye_complex_aum_b(cplx, fye_mo)
            if np.isnan(cplx_aum_fye_b):
                cplx_aum_fye_b = cplx_aum_23_b
            is_large_fye = bool(cplx_aum_fye_b >= 1.0) if not np.isnan(cplx_aum_fye_b) else True
            stat_tier, first_oncycle = compute_first_eligible_oncycle(fye_mo, is_large_fye)

            # Growth/Value-without-Income lexical screen flag (pre-name!)
            has_gv = bool(re.search(r"\b(?:growth|value)\b", old_nm, re.IGNORECASE))
            has_inc = bool(re.search(r"\bincome\b", old_nm, re.IGNORECASE))
            gv_lex_screen = int(has_gv and not has_inc)

            # EDGAR submissions metadata (trust fiscalYearEnd & empirical 485BPOS update month)
            sub_cp = SUB_CACHE / f"CIK{cik10}.json"
            sub_j = client.get_json_cached(f"https://data.sec.gov/submissions/CIK{cik10}.json", None, sub_cp)
            sub_fye_mmdd = str(sub_j.get("fiscalYearEnd") or "") if sub_j else ""
            bpos_months: list[int] = []
            if sub_j:
                rec = sub_j.get("filings", {}).get("recent", {})
                for fm, fd in zip(rec.get("form", []), rec.get("filingDate", []), strict=False):
                    if fm == "485BPOS" and fd >= "2023-01-01":
                        try:
                            bpos_months.append(int(fd[5:7]))
                        except ValueError:
                            pass
            emp_bpos_mo = int(pd.Series(bpos_months).mode().iloc[0]) if bpos_months else 0

            # Pass 1 (Baseline script-02 parser values)
            p1_eff = str(row.get("EFFECTIVE_DATE") or "").strip()
            p1_fund_35d1 = int(row.get("FUND_CITES_35D1") or 0)
            p1_fund_80 = int(row.get("FUND_CITES_80PCT") or 0)
            p1_sticker = int(row.get("HAS_NAME_CHANGE_STICKER") or 0)
            p1_unchanged = int(row.get("EXPLICIT_NO_STRATEGY_CHANGE") or 0)
            p1_form = str(row.get("PRIMARY_FORM") or "")
            p1_fdate = str(row.get("PRIMARY_FILE_DATE") or "")
            p1_url = str(row.get("PRIMARY_URL") or "")

            # Pass 2: Deep fund-scoped scan across ALL locally cached docs for this CIK
            # + targeted EFTS supplement/pre-rename fetch if missing effective date or pre-rename doc!
            cik_docs = sorted(DOC_CACHE.glob(f"{cik10}_*.txt"))
            cand_texts: list[tuple[str, str, str, str]] = []  # (label_date_or_acc, form_guess, url, text)
            seen_acc_nd: set[str] = set()

            # Build accession -> (form, file_date) map from submissions JSON
            acc_meta: dict[str, tuple[str, str]] = {}
            if sub_j:
                rec = sub_j.get("filings", {}).get("recent", {})
                for ac, fm, fd in zip(rec.get("accessionNumber", []), rec.get("form", []), rec.get("filingDate", []), strict=False):
                    acc_meta[ac.replace("-", "")] = (fm, fd)

            for dp in cik_docs:
                parts = dp.stem.split("_", 2)
                if len(parts) < 3:
                    continue
                acc_nd, fname = parts[1], parts[2]
                fm, fd = acc_meta.get(acc_nd, ("", ""))
                url = f"https://www.sec.gov/Archives/edgar/data/{int(cik10)}/{acc_nd}/{fname}"
                try:
                    txt = html_to_clean_text(dp.read_text(encoding="utf-8", errors="replace"))
                except OSError:
                    continue
                cand_texts.append((fd, fm, url, txt))
                seen_acc_nd.add(acc_nd)

            # For renamers missing effective date OR small retained funds with no cached docs, run targeted EFTS fetch
            need_fetch = (is_renamer_group and not p1_eff) or (not is_renamer_group and len(cik_docs) == 0)
            if need_fetch:
                ph_new = " ".join(re.sub(r"[^A-Za-z0-9/%&\-\s]+", " ", new_nm).split()[:5])
                ph_old = " ".join(re.sub(r"[^A-Za-z0-9/%&\-\s]+", " ", old_nm).split()[:5])
                hits = efts_search(client, f'"{ph_new}"', cik10, "2024-06-01", "2026-09-30")
                if is_renamer_group and ph_old and ph_old != ph_new:
                    hits += efts_search(client, f'"{ph_old}" "name change"', cik10, "2024-06-01", "2026-09-30")
                    hits += efts_search(client, f'"{ph_old}" "formerly"', cik10, "2024-06-01", "2026-09-30")
                # Prioritize 497/497K/485BPOS
                prio = {"497": 0, "497K": 1, "485BPOS": 2, "485APOS": 3}
                hits.sort(key=lambda h: (prio.get(h["form"], 9), h["file_date"]))
                fetched_cnt = 0
                for h in hits:
                    acc_nd = h["adsh"].replace("-", "")
                    if acc_nd in seen_acc_nd:
                        continue
                    txt, url = get_doc(cik10, h["adsh"], h["filename"])
                    if txt:
                        cand_texts.append((h["file_date"], h["form"], url, txt))
                        seen_acc_nd.add(acc_nd)
                        fetched_cnt += 1
                    if fetched_cnt >= 3:
                        break

            # Evaluate Pass 2 fund-scoped signals across all candidate filings for this fund
            p2_fund_35d1 = 0
            p2_pre_80 = 0
            p2_post_80 = 0
            p2_unchanged = 0
            p2_index_rename = 0
            p2_strat_change = 0
            p2_sticker = 0
            p2_eff = p1_eff
            p2_url = p1_url
            p2_form = p1_form
            p2_fdate = p1_fdate
            snip_80 = ""
            snip_35d1 = str(row.get("SNIPPET_35D1") or "")
            snip_policy = str(row.get("SNIPPET_NO_STRATEGY_CHANGE") or "")
            n_docs_matched = 0

            # Sort candidate texts chronologically so pre/post split is clean
            cand_texts.sort(key=lambda x: x[0])
            for fd, fm, url, txt in cand_texts:
                wins = extract_fund_windows(txt, old_nm, new_nm, radius=2200)
                if not wins:
                    continue
                n_docs_matched += 1
                win_joined = " ... ".join(wins)
                is_pre_doc = bool(fd and fd < f"{rep_yq // 10}-{((rep_yq % 10) - 1) * 3 + 1:02d}-01")

                if RE_RULE_35D1.search(win_joined):
                    p2_fund_35d1 = 1
                    if not snip_35d1:
                        snip_35d1 = extract_snippet(win_joined, RE_RULE_35D1)
                if RE_80_POLICY.search(win_joined):
                    if is_pre_doc:
                        p2_pre_80 = 1
                    else:
                        p2_post_80 = 1
                    if not snip_80:
                        snip_80 = extract_snippet(win_joined, RE_80_POLICY)
                if RE_UNCHANGED_POLICY.search(win_joined):
                    p2_unchanged = 1
                    if not snip_policy:
                        snip_policy = extract_snippet(win_joined, RE_UNCHANGED_POLICY)
                if RE_BENCHMARK_INDEX_RENAME.search(win_joined):
                    p2_index_rename = 1
                    if not snip_policy:
                        snip_policy = extract_snippet(win_joined, RE_BENCHMARK_INDEX_RENAME)
                if RE_STRATEGY_CHANGE.search(win_joined):
                    p2_strat_change = 1
                if RE_NAME_CHANGE.search(win_joined):
                    p2_sticker = 1
                    if is_renamer_group and not p2_eff:
                        cand_eff = find_effective_date_in_windows(wins, txt, fd, rep_yq, fm)
                        if cand_eff:
                            p2_eff = cand_eff
                            p2_url, p2_form, p2_fdate = url, fm, fd

            # Fallback effective date from matching post-rename 497K/485BPOS prospectus dated near drop quarter
            if is_renamer_group and not p2_eff:
                for fd, fm, url, txt in cand_texts:
                    wins = extract_fund_windows(txt, "", new_nm, radius=1800)
                    if not wins:
                        continue
                    cand_eff = find_effective_date_in_windows(wins, txt, fd, rep_yq, fm)
                    if cand_eff:
                        p2_eff = cand_eff
                        p2_url, p2_form, p2_fdate = url, fm, fd
                        break

            # Apply verified primary-filing direct audit findings (Vanguard, iShares, AST/Prudential, Fidelity VIP)
            direct_note = ""
            same_filing_unreg = 0
            if sid in VERIFIED_PRIMARY_CASES:
                vc = VERIFIED_PRIMARY_CASES[sid]
                p2_eff = vc["eff_date"]
                p2_unchanged = max(p2_unchanged, vc["unchanged_policy"])
                p2_index_rename = max(p2_index_rename, vc["index_rename"])
                same_filing_unreg = vc["same_filing_unreg"]
                p2_url = vc["filing_url"]
                direct_note = vc["note"]

            # Same-complex-quarter unregulated co-renames from N-PORT census
            n_unreg_ma_same_cq = int(unreg_by_cplx_yq_ma.get((cplx, rep_yq), 0))
            n_unreg_all_same_cq = int(unreg_by_cplx_yq_all.get((cplx, rep_yq), 0))
            has_same_cq_unreg = int(same_filing_unreg == 1 or n_unreg_ma_same_cq > 0)

            # Timing flags relative to June 11, 2026 and fund's own first eligible on-cycle update
            eff_use = p2_eff or p1_eff
            pre_june11 = int(bool(eff_use and eff_use < "2026-06-11"))
            pre_oncycle = int(bool(eff_use and eff_use < first_oncycle))
            days_before_oncycle = (
                int((date.fromisoformat(first_oncycle) - date.fromisoformat(eff_use)).days)
                if eff_use
                else -9999
            )

            # Transparent Statutory Applicability Classification
            if not is_renamer_group:
                if p2_fund_35d1 == 1 and (p2_pre_80 == 1 or p2_post_80 == 1):
                    stat_cat = "RETAINED_CITES_35D1_AND_80PCT"
                elif p2_pre_80 == 1 or p2_post_80 == 1:
                    stat_cat = "RETAINED_FUND_80PCT_NO_35D1_CITE"
                elif n_docs_matched > 0:
                    stat_cat = "RETAINED_NO_FUND_80PCT_FOUND"
                else:
                    stat_cat = "RETAINED_UNVERIFIED_NO_DOC"
            else:
                if p2_index_rename == 1:
                    stat_cat = "BENCHMARK_INDEX_RENAME_PAIRED"
                elif p2_unchanged == 1:
                    stat_cat = "UNCHANGED_POLICY_CONFIRMED"
                elif has_same_cq_unreg == 1 and p2_fund_35d1 == 0:
                    stat_cat = "MULTI_FUND_REBRAND_WITH_UNREGULATED"
                elif p2_fund_35d1 == 1 and p2_strat_change == 1:
                    stat_cat = "FUND_CITES_35D1_WITH_POLICY_EDIT"
                elif p2_fund_35d1 == 1:
                    stat_cat = "FUND_CITES_35D1_SILENT_ON_MOTIVE"
                elif p2_strat_change == 1:
                    stat_cat = "STRATEGY_OR_ADVISER_CHANGE_NO_35D1"
                elif p2_sticker == 1 or p1_sticker == 1 or eff_use:
                    stat_cat = "NAME_CHANGE_SILENT_ON_STATUTORY_BASIS"
                else:
                    stat_cat = "UNVERIFIED_NO_NAME_CHANGE_FILING"

            # Record explicit Pass 1 vs Pass 2 disagreements!
            disagreements: list[str] = []
            if p1_fund_35d1 != p2_fund_35d1:
                disagreements.append(f"35d1_fund:P1={p1_fund_35d1}_vs_P2={p2_fund_35d1}")
            if p1_unchanged != p2_unchanged:
                disagreements.append(f"unchanged:P1={p1_unchanged}_vs_P2={p2_unchanged}")
            if (not p1_eff) and bool(p2_eff):
                disagreements.append(f"eff_date_rescued:P2={p2_eff}")
            elif p1_eff and p2_eff and p1_eff != p2_eff:
                disagreements.append(f"eff_date_diff:P1={p1_eff}_vs_P2={p2_eff}")
            p1_p2_agree = int(len(disagreements) == 0)

            rows_out.append({
                "SERIES_ID": sid,
                "CIK10": cik10,
                "COMPLEX_ID": cplx,
                "COMPLIANCE_TYPE": str(row["COMPLIANCE_TYPE"]),
                "GV_LEXICAL_SCREEN": gv_lex_screen,
                "PRE_NAME": old_nm,
                "POST_NAME": new_nm,
                "REP_YQ": rep_yq,
                "AUM_M": round(aum_m, 2),
                "IS_VA_INSURANCE": is_va,
                "IS_FOF": is_fof,
                "IS_ETF": is_etf,
                "IS_INDEX": is_idx,
                "FYE_MONTH_NPORT": fye_mo,
                "SUB_FYE_MMDD": sub_fye_mmdd or "MISSING",
                "EMPIRICAL_485BPOS_MO": emp_bpos_mo,
                "COMPLEX_AUM_FYE_B": round(cplx_aum_fye_b, 3) if not np.isnan(cplx_aum_fye_b) else -1.0,
                "FYE_AUM_REF_YQ": fye_aum_yq,
                "STATUTORY_TIER_33_11368": stat_tier,
                "FIRST_ELIGIBLE_ONCYCLE_DATE": first_oncycle,
                "PASS1_EFF_DATE": p1_eff or "UNPARSED",
                "VERIFIED_EFF_DATE": eff_use or "UNPARSED",
                "PRE_JUNE11_EARLY_ACTION": pre_june11,
                "PRE_STATUTORY_ONCYCLE": pre_oncycle,
                "DAYS_BEFORE_ONCYCLE": days_before_oncycle,
                "PRIMARY_FORM": p2_form or p1_form or "NONE",
                "PRIMARY_FILE_DATE": p2_fdate or p1_fdate or "NONE",
                "PRIMARY_URL": p2_url or p1_url or "NONE",
                "N_CACHED_DOCS_MATCHED": n_docs_matched,
                "PASS1_FUND_35D1": p1_fund_35d1,
                "PASS2_FUND_SCOPED_35D1": p2_fund_35d1,
                "PASS1_FUND_80PCT": p1_fund_80,
                "PASS2_PRE_80PCT": p2_pre_80,
                "PASS2_POST_80PCT": p2_post_80,
                "EXPLICIT_UNCHANGED_POLICY": p2_unchanged,
                "PAIRED_BENCHMARK_INDEX_RENAME": p2_index_rename,
                "EXPLICIT_STRATEGY_OR_POLICY_CHANGE": p2_strat_change,
                "SAME_CPLX_QTR_UNREG_MA_RENAMES": n_unreg_ma_same_cq,
                "SAME_CPLX_QTR_UNREG_ALL_RENAMES": n_unreg_all_same_cq,
                "STATUTORY_AUDIT_CATEGORY": stat_cat,
                "PASS1_PASS2_AGREE": p1_p2_agree,
                "DISAGREEMENT_NOTES": "; ".join(disagreements) if disagreements else "AGREE",
                "AUDIT_EVIDENCE_NOTE": (direct_note or snip_policy or snip_35d1 or snip_80 or "No fund-scoped statutory rationale stated in retrieved filings")[:240],
            })
        return pd.DataFrame(rows_out)

    df_ren50 = audit_fund_group(ma_ren, is_renamer_group=True)
    df_ret50 = audit_fund_group(strat_ret, is_renamer_group=False)

    df_ren50.to_csv(TABLES_DIR / "table_50_renamers_statutory_audit.csv", index=False, lineterminator="\n")
    df_ret50.to_csv(TABLES_DIR / "table_50_retained_statutory_audit.csv", index=False, lineterminator="\n")

    # -----------------------------------------------------------------------
    # [5/5] Precision / Recall of 35/50 Growth/Value Lexical Screen & Audit Receipt
    # -----------------------------------------------------------------------
    print("[4/5] Computing precision/recall of 35/50 Growth/Value lexical screen and timing summary...", flush=True)

    def pr_metrics(pred: pd.Series, truth: pd.Series) -> dict:
        tp = int(((pred == 1) & (truth == 1)).sum())
        fp = int(((pred == 1) & (truth == 0)).sum())
        fn = int(((pred == 0) & (truth == 1)).sum())
        tn = int(((pred == 0) & (truth == 0)).sum())
        prec = float(tp / (tp + fp)) if (tp + fp) > 0 else 0.0
        rec = float(tp / (tp + fn)) if (tp + fn) > 0 else 0.0
        f1 = float(2 * prec * rec / (prec + rec)) if (prec + rec) > 0 else 0.0
        return {
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
            "precision": prec, "recall": rec, "f1": f1,
            "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) > 0 else 0.0,
        }

    pred_gv = df_ren50["GV_LEXICAL_SCREEN"]
    truth_fund_35d1_p2 = df_ren50["PASS2_FUND_SCOPED_35D1"]
    truth_fund_35d1_p1 = df_ren50["PASS1_FUND_35D1"]
    truth_fund_80_p2 = ((df_ren50["PASS2_PRE_80PCT"] == 1) | (df_ren50["PASS2_POST_80PCT"] == 1)).astype(int)
    truth_excl_unchanged_and_idx = (
        (df_ren50["EXPLICIT_UNCHANGED_POLICY"] == 0) & (df_ren50["PAIRED_BENCHMARK_INDEX_RENAME"] == 0)
    ).astype(int)

    p1_parsed = df_ren50[df_ren50["PASS1_EFF_DATE"] != "UNPARSED"]
    p2_parsed = df_ren50[df_ren50["VERIFIED_EFF_DATE"] != "UNPARSED"]
    p1_pre_jun11 = int((p1_parsed["PASS1_EFF_DATE"] < "2026-06-11").sum())
    p2_pre_jun11 = int((p2_parsed["VERIFIED_EFF_DATE"] < "2026-06-11").sum())
    p2_pre_oncycle = int((p2_parsed["PRE_STATUTORY_ONCYCLE"] == 1).sum())

    # On-cycle compliance timing distribution across all 50 renamers
    oncycle_after_26q3 = int((df_ren50["FIRST_ELIGIBLE_ONCYCLE_DATE"] > "2026-07-31").sum())
    oncycle_in_2027 = int(df_ren50["FIRST_ELIGIBLE_ONCYCLE_DATE"].str.startswith("2027").sum())

    summary = {
        "n_primary_renamers_audited": len(df_ren50),
        "n_stratified_retained_audited": len(df_ret50),
        "n_small_lt1b_among_renamers_fye": int((df_ren50["STATUTORY_TIER_33_11368"] == "SMALL_LT_1B_DEC11_2026").sum()),
        "n_large_ge1b_among_renamers_fye": int((df_ren50["STATUTORY_TIER_33_11368"] == "LARGE_GE_1B_JUN11_2026").sum()),
        "n_small_lt1b_among_retained_stratified": int((df_ret50["STATUTORY_TIER_33_11368"] == "SMALL_LT_1B_DEC11_2026").sum()),
        "gv_lexical_screen_count": int(pred_gv.sum()),
        "gv_lexical_screen_aum_B": float(df_ren50.loc[pred_gv == 1, "AUM_M"].sum() / 1e3),
        "effective_date_audit": {
            "pass1_parsed_total": len(p1_parsed),
            "pass1_pre_june11_2026": p1_pre_jun11,
            "pass2_verified_total": len(p2_parsed),
            "pass2_pre_june11_2026": p2_pre_jun11,
            "pass2_pre_fund_statutory_oncycle": p2_pre_oncycle,
            "renamers_with_oncycle_date_after_2026_07_31": oncycle_after_26q3,
            "renamers_with_oncycle_date_in_2027": oncycle_in_2027,
            "fye_month_distribution_renamers": {str(k): int(v) for k, v in df_ren50["FYE_MONTH_NPORT"].value_counts().sort_index().items()},
        },
        "statutory_category_counts_renamers": {
            str(k): int(v) for k, v in df_ren50["STATUTORY_AUDIT_CATEGORY"].value_counts().items()
        },
        "statutory_category_aum_B_renamers": {
            str(k): float(v / 1e3) for k, v in df_ren50.groupby("STATUTORY_AUDIT_CATEGORY")["AUM_M"].sum().items()
        },
        "statutory_category_counts_retained": {
            str(k): int(v) for k, v in df_ret50["STATUTORY_AUDIT_CATEGORY"].value_counts().items()
        },
        "dual_pass_reconciliation": {
            "renamers_exact_agree_n": int(df_ren50["PASS1_PASS2_AGREE"].sum()),
            "renamers_disagree_n": int((df_ren50["PASS1_PASS2_AGREE"] == 0).sum()),
            "renamers_pass1_fund_35d1_n": int(df_ren50["PASS1_FUND_35D1"].sum()),
            "renamers_pass2_fund_scoped_35d1_n": int(df_ren50["PASS2_FUND_SCOPED_35D1"].sum()),
            "renamers_explicit_unchanged_policy_n": int(df_ren50["EXPLICIT_UNCHANGED_POLICY"].sum()),
            "renamers_paired_benchmark_index_rename_n": int(df_ren50["PAIRED_BENCHMARK_INDEX_RENAME"].sum()),
            "renamers_same_complex_qtr_unreg_ma_corename_n": int((df_ren50["SAME_CPLX_QTR_UNREG_MA_RENAMES"] > 0).sum()),
            "retained_pass2_fund_scoped_35d1_n": int(df_ret50["PASS2_FUND_SCOPED_35D1"].sum()),
            "retained_pass2_any_80pct_n": int(((df_ret50["PASS2_PRE_80PCT"] == 1) | (df_ret50["PASS2_POST_80PCT"] == 1)).sum()),
        },
        "gv_lexical_screen_validation": {
            "vs_pass2_fund_scoped_35d1": pr_metrics(pred_gv, truth_fund_35d1_p2),
            "vs_pass1_document_35d1": pr_metrics(pred_gv, truth_fund_35d1_p1),
            "vs_pass2_fund_scoped_80pct": pr_metrics(pred_gv, truth_fund_80_p2),
            "vs_non_unchanged_non_index_rename": pr_metrics(pred_gv, truth_excl_unchanged_and_idx),
        },
        "unregulated_control_group": {
            "n_ma_substantive_unreg_renames_25_26": len(unreg_ma_export),
            "n_complexes": int(unreg_ma_export["COMPLEX_ID"].nunique()),
            "aum_B": float(unreg_ma_export["AUM_M"].sum() / 1e3),
            "n_cosmetic_punctuation_excluded_ma_25_26": len(
                ren_all[
                    (ren_all["REP_YQ"] >= 20251)
                    & (ren_all["PREV_IS_ALLOC_FUND"] == 1)
                    & (ren_all["IS_SUBSTANTIVE_RENAME"] == 0)
                ]
            ),
        },
        "edgar_client_stats": {"live_fetches": client.n_live, "cache_hits": client.n_cache},
    }

    (RESULTS_DIR / "02b_per_fund_statutory_audit.json").write_text(
        json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print("\n[5/5] PER-FUND STATUTORY AUDIT SUMMARY:", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
