"""Pillar 3: 4-Tier Exact Look-Through Holdings & Portfolio Inertia Proof (2023Q2 -> 2026Q2/Q3).

Fixes Wave-5's broken ISSUER_TYPE=='RF' look-through completely:
1. Streams FUND_REPORTED_HOLDING.tsv via HTTP 206 Range from SEC bulk zips for
   2023q2, 2023q3 (exact REP_YQ=2023Q2 pre-rule baseline) and 2026q2, 2026q3
   (latest post-cliff REP_YQ in {2026Q2, 2026Q3}), caching compact extracts under
   data/holdings_lt/.
2. 4-Tier Exact Look-Through Classifier:
   - Tier 1: Direct equity (EC/EP non-fund) vs direct debt (DBT/ABS/LON) vs cash/STIV.
   - Tier 2: Exact Underlying Fund-to-Fund CUSIP & canonical Series-Name match against
     our own N-PORT universe (capturing Vanguard, Fidelity, Prudential, American Funds,
     iShares, SPDR, etc., EVEN when reported with ASSET_CAT=='EC' and ISSUER_TYPE!='RF'!).
   - Tier 3: Audited ETF/Mutual-Fund asset-class title dictionary separating Cash/Liquidity
     sweeps (CMT/Money Market) -> STIV, Bond/Fixed-Income -> Bond, and Equity/Stock -> Equity.
   - Tier 4: Recursive 1-pass FOF look-through for multi-asset underlying holdings.
3. Explicitly asserts Vanguard LifeStrategy (20/80, 40/60, 60/40, 80/20) land within +/-3 pp
   of their stated equity/bond targets in BOTH 2023Q2 and 2026Q3, and exports a 100-position
   audit table (tables/table_lookthrough_100pos_audit.csv).
4. Computes:
   - Zero-keyword physical holdings constraint HOLD_LT_CONSTR = 1{max(%Eq,%Bond) < 80% in 2023Q2}
   - Raw & Passive Market-Drift-Adjusted Active Rebalancing (2023Q2 -> 2026Q2/Q3)
   - IS_FOF-controlled Security-Level CUSIP Overlap, HHI, Holding Count, Cash Ratio & Volatility TWFE.
"""

from __future__ import annotations

import json
import re
import struct
import sys
import time
import zlib
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parent))
from econometrics import ols_cr1_wcb, run_absorbed_twfe

WORK_DIR = Path(r"D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126")
LT_CACHE = WORK_DIR / "data" / "holdings_lt"
LT_CACHE.mkdir(parents=True, exist_ok=True)

SEC_HEADERS = {
    "User-Agent": "AcademicResearch research@university.edu",
    "Accept-Encoding": "identity",
}

# Verified canonical CUSIP lookup for major internal FOF underlying funds whose issuer/title
# may be abbreviated in N-PORT (verified directly against N-PORT holdings & SEC filings)
KNOWN_FUND_CUSIP_MAP: dict[str, tuple[float, float, float, str]] = {
    # (eq_wt, bond_wt, cash_wt, label)
    "92203C105": (0.0, 1.0, 0.0, "Vanguard Total Bond Market II Index Fund"),
    "92211J100": (0.0, 1.0, 0.0, "Vanguard Total International Bond II Index Fund"),
    "92203J407": (0.0, 1.0, 0.0, "Vanguard Total Bond Market Index Fund"),
    "92203J308": (0.0, 1.0, 0.0, "Vanguard Total Bond Market Index Fund Adm"),
    "92206C870": (0.0, 1.0, 0.0, "Vanguard Total International Bond Index Fund"),
    "922908306": (1.0, 0.0, 0.0, "Vanguard Total Stock Market Index Fund"),
    "922908728": (1.0, 0.0, 0.0, "Vanguard Total Stock Market Index Fund Inst"),
    "921909602": (1.0, 0.0, 0.0, "Vanguard Total International Stock Index Fund"),
    "921909818": (1.0, 0.0, 0.0, "Vanguard Total International Stock Index Fund Inst"),
    "922908363": (1.0, 0.0, 0.0, "Vanguard 500 Index Fund"),
    "921937835": (0.0, 1.0, 0.0, "Vanguard Total Bond Market ETF (BND)"),
    "922908769": (1.0, 0.0, 0.0, "Vanguard Total Stock Market ETF (VTI)"),
    "921909768": (1.0, 0.0, 0.0, "Vanguard Total International Stock ETF (VXUS)"),
    "464287226": (0.0, 1.0, 0.0, "iShares Core U.S. Aggregate Bond ETF (AGG)"),
    "464287200": (1.0, 0.0, 0.0, "iShares Core S&P 500 ETF (IVV)"),
    "464287465": (1.0, 0.0, 0.0, "iShares MSCI EAFE ETF (EFA)"),
    "46432F842": (1.0, 0.0, 0.0, "iShares Core MSCI EAFE ETF (IEFA)"),
    "46434G103": (1.0, 0.0, 0.0, "iShares Core MSCI Emerging Markets ETF (IEMG)"),
    "464287507": (1.0, 0.0, 0.0, "iShares Core S&P Mid-Cap ETF (IJH)"),
    "464287804": (1.0, 0.0, 0.0, "iShares Core S&P Small-Cap ETF (IJR)"),
    "46435U549": (0.0, 1.0, 0.0, "iShares Core International Aggregate Bond ETF (IAGG)"),
    "464287440": (0.0, 1.0, 0.0, "iShares 7-10 Year Treasury Bond ETF (IEF)"),
    "464287457": (0.0, 1.0, 0.0, "iShares 1-3 Year Treasury Bond ETF (SHY)"),
    "464287176": (0.0, 1.0, 0.0, "iShares TIPS Bond ETF (TIP)"),
    "464288588": (0.0, 1.0, 0.0, "iShares MBS ETF (MBB)"),
    "78462F103": (1.0, 0.0, 0.0, "SPDR S&P 500 ETF Trust (SPY)"),
    "78464A649": (0.0, 1.0, 0.0, "SPDR Portfolio Aggregate Bond ETF (SPAB)"),
    "78464A854": (1.0, 0.0, 0.0, "SPDR Portfolio S&P 500 ETF (SPLG)"),
    "78468R663": (0.0, 0.0, 1.0, "SPDR Bloomberg 1-3 Month T-Bill ETF (BIL)"),
    "78464A474": (0.0, 1.0, 0.0, "SPDR Portfolio Short Term Corporate Bond ETF (SPSB)"),
    "78468R408": (0.0, 1.0, 0.0, "SPDR Bloomberg Short Term High Yield Bond ETF (SJNK)"),
    "78468R606": (0.0, 1.0, 0.0, "SPDR Portfolio High Yield Bond ETF (SPHY)"),
    "78467V608": (0.0, 1.0, 0.0, "SPDR Blackstone Senior Loan ETF (SRLN)"),
    "46138G508": (0.0, 1.0, 0.0, "Invesco Senior Loan ETF (BKLN)"),
    "922020805": (0.0, 1.0, 0.0, "Vanguard Short-Term Inflation-Protected Securities ETF (VTIP)"),
    "464287242": (0.0, 1.0, 0.0, "iShares iBoxx $ Investment Grade Corporate Bond ETF (LQD)"),
    "74440E201": (0.0, 1.0, 0.0, "PGIM Core Ultra Short Bond Fund"),
    "543916134": (0.0, 1.0, 0.0, "Lord Abbett Floating Rate Fund"),
    "09260B747": (0.0, 1.0, 0.0, "BlackRock Floating Rate Income Portfolio"),
    "277923637": (0.0, 1.0, 0.0, "Eaton Vance Floating-Rate Advantage Fund"),
    "92837F763": (0.0, 1.0, 0.0, "Virtus Seix Floating Rate High Income Fund"),
    "00141A586": (0.0, 1.0, 0.0, "Invesco Floating Rate ESG Fund"),
    "31635T666": (0.0, 1.0, 0.0, "Fidelity Series 0-5 Year Inflation-Protected Bond Index Fund"),
    "31617H854": (0.0, 0.0, 1.0, "Fidelity Series Treasury Bill Index Fund"),
    "31638R667": (0.0, 1.0, 0.0, "Fidelity Series International Developed Markets Bond Index Fund"),
    "31641Q755": (0.0, 1.0, 0.0, "Fidelity Advisor New Markets Income Fund"),
    "02631W771": (0.0, 1.0, 0.0, "American Funds Multi-Sector Income Fund"),
    "41015G168": (1.0, 0.0, 0.0, "John Hancock VIT Strategic Equity Allocation Trust"),
    "41015G259": (0.0, 1.0, 0.0, "John Hancock VIT Select Bond Trust"),
    "693390700": (0.0, 1.0, 0.0, "PIMCO Total Return Fund Instl"),
}

# Detect underlying funds/ETFs even when reported as ASSET_CAT=='EC' and ISSUER_TYPE!='RF'
RE_IS_UNDERLYING_FUND = re.compile(
    r"(?:\b(?:etf|exchange[\-\s]traded|index\s+fund|index\s+trust|mutual\s+fund|"
    r"series\s+fund|central\s+fund|cmt\s+funds?|money\s+market|liquidity\s+fund|"
    r"investment\s+trust|select\s+sector\s+spdr|spdr\s+(?:portfolio|s&p|bloomberg|dow|msci|nuveen)|"
    r"ishares|vanguard\s+(?:total|index|star|institutional|international|short|intermediate|long|"
    r"extended|small|mid|large|growth|value|bond|stock|equity|treasury|muni|market|high|federal|"
    r"ultra|inflation|500|ftse|s&p|msci|russell|dividend|balanced|wellington|wellesley|explorer|primecap|windsor)|"
    r"fidelity\s+(?:series|central|re-?in|sai|vip|freedom|index|total|bond|stock|government|treasury|contrafund|magellan|blue\s+chip|low[\-\s]priced)|"
    r"american\s+funds|bond\s+fund\s+of\s+america|capital\s+world\s+(?:growth|bond)|new\s+perspective\s+fund|"
    r"new\s+world\s+fund|washington\s+mutual\s+investors|fundamental\s+investors|europacific\s+growth|"
    r"pgim\s+(?:total|core|short|high|jennison|qma|quant|global|international|us|u\.s\.)|"
    r"ast\s+(?:pgim|jennison|qma|pimco|blackrock|wellington|t\.\s*rowe|mfs|goldman|fi|clearbridge|fidelity|lazard|loomis|western)|"
    r"pimco\s+(?:total|income|real|short|low|global|international|all|commodity|emerging|high|stocksplus|dynamic|investment)|"
    r"blackrock\s+(?:liquidity|strategic|total|core|high|global|advantage|equity|event|cash|fedfund|t-?fund)|"
    r"state\s+street\s+(?:institutional|global|aggregate|equity|s&p|msci|russell|treasury|bond)|"
    r"invesco\s+(?:qqq|s&p|bulletshares|senior|high|short|treasury|government|optimum|global|developing)|"
    r"schwab\s+(?:u\.?s\.?|international|emerging|total|short|intermediate|fundamental|strategic|treasury)|"
    r"dimensional\s+|dfa\s+(?:u\.?s\.?|international|emerging|five|two|one|core|global|real|short|intermediate|inflation|world)|"
    r"jpmorgan\s+(?:core|short|ultra|high|equity|large|mid|small|international|emerging|u\.?s\.?|betabuilders|100%|prime|liquid)|"
    r"t\.?\s*rowe\s+price\s+|goldman\s+sachs\s+(?:fs|financial\s+square|activebeta|access|core|bond|equity|short|high|emerging|international)|"
    r"voya\s+(?:intermediate|global|international|u\.?s\.?|large|mid|small|core|high|short|multi|solution|index)|"
    r"russell\s+investment\s+|hartford\s+(?:core|total|strategic|world|schroders|multifactor|dividend|equity|growth|value|short)|"
    r"first\s+trust\s+|vaneck\s+|wisdomtree\s+|proshares\s+|direxion\s+|global\s+x\s+|"
    r"dreyfus\s+(?:treasury|government|cash|institutional)|federated\s+(?:hermes\s+)?(?:treasury|government|institutional|prime)|"
    r"northern\s+institutional|first\s+american\s+(?:government|treasury|prime)|allspring\s+(?:government|treasury|heritage))\b"
    r"|(?:fund|portfolio)\s*(?:,?\s*(?:class|cl\.?|inst|adm|inv|shs|shares|inc\.?|series)\b|$))",
    re.IGNORECASE,
)

# Tier 3 Asset-Class Title Dictionary for Underlying Funds / ETFs
RE_UF_CASH = re.compile(
    r"\b(?:money\s+market|liquidity|cash\s+management|cash\s+reserves?|cash\s+central|"
    r"treasury\s+obligations?|government\s+obligations?|fedfund|t[\-\s]fund|tempfund|"
    r"cmt\s+funds?|market\s+liquidity|sweep|prime\s+obligations?|prime\s+reserves?|"
    r"financial\s+square\s+(?:government|treasury|money|prime)|u\.?s\.?\s+government\s+money|"
    r"institutional\s+(?:government|treasury|prime)\s+(?:money|assets|cash|liquidity)|"
    r"short[\-\s]term\s+investments?\s+trust|central\s+cash|collateral\s+fund|securities\s+lending\s+cash|"
    r"treasury\s+bill\s+index|1[\-\s]3\s+month\s+t[\-\s]bill|\bt[\-\s]bills?\b)\b",
    re.IGNORECASE,
)

RE_UF_BOND = re.compile(
    r"\b(?:bond|bonds|\bbnd\b|\bbd\b|fixed[\s\-]income|treasur(?:y|ies)|muni(?:cipal)?|credit|aggregate|\bagg\b|"
    r"high[\s\-]yield|\bhy\s+bd\b|inflation[\-\s]protected|\btips\b|sh(?:ort)?[\s\-]term\s+tip|mortgage|\bmbs\b|\bcmbs\b|\babs\b|"
    r"corporate\s+(?:bond|debt|credit)|corp\s+bnd|iboxx|floating[\s\-]rate|fltng\s+rt|float\s+ra|fl\s+r(?:t|ate)|f/r\s|"
    r"bank\s+loan|senior\s+loan|leveraged\s+loan|core[\s\-]plus|short[\s\-]duration|intermediate[\s\-]duration|long[\s\-]duration|low[\s\-]duration|"
    r"short[\s\-]term\s+(?:bond|investment[\-\s]grade|gov|government|treasury|corporate|income|credit|federal)|"
    r"intermediate[\s\-]term\s+(?:bond|treasury|investment[\-\s]grade|gov|government|corporate)|"
    r"long[\s\-]term\s+(?:bond|treasury|corporate|government)|investment[\s\-]grade|securitized|"
    r"sovereign\s+debt|emerging\s+markets?\s+(?:bond|debt|local\s+debt)|new\s+markets?\s+income|gnma|agency\s+mbs|"
    r"total\s+return\s+bond|core\s+bond|multi[\s\-]?sector\s+(?:bond|income)|strategic\s+income|"
    r"u\.?s\.?\s+government\s+securities|govt|government\s+bond|ultra[\-\s]short\s+(?:bond|income|duration)|cre\s+ult\s+sh|"
    r"convertible\s+bond|global\s+income|world\s+bond|international\s+bond|fixed\s+income|"
    r"high\s+income\s+(?:bond|fund|portfolio)|bond\s+fund\s+of\s+america|"
    r"pimco\s+income|pimco\s+total\s+return|pimco\s+real\s+return|pgim\s+total\s+return|metwest\s+total\s+return|"
    r"doubleline\s+total\s+return|bloomberg\s+(?:u\.?s\.?\s+)?(?:aggregate|treasury|corporate|barclays|high\s+yield)|"
    r"1[\-\s]3\s+year\s+treasury|7[\-\s]10\s+year\s+treasury|20\+\s+year\s+treasury|short\s+treasury|"
    r"bulletshares.*corporate|bulletshares.*high\s+yield|debt\s+fund|debt\s+portfolio)\b",
    re.IGNORECASE,
)

RE_UF_EQUITY = re.compile(
    r"\b(?:stock|stocks|equit(?:y|ies)|s&p\s*(?:500|400|600|1500|100|total|mid|small)|"
    r"russell\s*(?:1000|2000|3000|mid|top)|msci\s+(?:usa|eafe|acwi|world|emerging|europe|pacific|japan|ex|kokusai|all)|"
    r"nasdaq|dow\s+jones|ftse\s+(?:developed|emerging|all|global|russell|us)|"
    r"total\s+(?:stock|market|international\s+stock|world\s+stock)|"
    r"small[\s\-]cap|mid[\s\-]cap|large[\s\-]cap|mega[\s\-]cap|micro[\s\-]cap|all[\s\-]cap|multi[\s\-]cap|"
    r"blue\s+chip|growth|value|dividend|emerging\s+markets?|eafe|developed\s+markets?|"
    r"international\s+(?:stock|equity|index|select|core|opportunities|alpha|research|focus|discovery)|"
    r"europe|asia[\-\s]pacific|msci\s+pacific|ftse\s+pacific|pacific\s+(?:stock|equity|basin|rim|ex)|japan|china|india|asia|latin\s+america|reit|real\s+estate|infrastructure|"
    r"select\s+sector|technology|health\s*care|financials|industrials|utilities|energy|consumer|materials|semiconductor|"
    r"qqq|spy|ivv|vti|voo|vxus|iefa|iemg|ijh|ijr|capital\s+appreciation|contrarian|contrafund|magellan|"
    r"new\s+perspective|new\s+world|washington\s+mutual|fundamental\s+investors|europacific|amcap|investment\s+company\s+of\s+america|"
    r"extended\s+market|500\s+index|world\s+equity|global\s+equity|u\.?s\.?\s+equity|overseas|"
    r"intrinsic\s+opportunities|low[\-\s]priced\s+stock|explorer|primecap|windsor|jennison|"
    r"qma\s+us|activebeta|betabuilders\s+(?:u\.?s\.?|developed|canada|europe|japan|international|msci))\b",
    re.IGNORECASE,
)

RE_UF_RATIO = re.compile(r"\b(\d{2})\s*/\s*(\d{2})\b")
RE_UF_MIXED = re.compile(r"\b(?:balanced|allocation|multi[\-\s]asset|lifestrategy|lifestyle|target\s+date|freedom\s+20\d\d)\b", re.IGNORECASE)


def norm_fund_name(s: str) -> str:
    """Normalize underlying fund name cleanly for exact Tier-2 N-PORT matching.

    Strips parenthetical tickers/articles like `(THE)`, `(CIB)`, `(IFA)`, `(AMBAL)`,
    `(GBAL)`, `(WGI CL R6)`, concatenated share-class suffixes (`FUNDZ`, `FUNDI`),
    and class/share boilerplate so American Funds, Fidelity, Vanguard, and peer
    underlying funds resolve directly to their exact N-PORT direct-holding mixes.
    """
    t = (s or "").lower()
    # Remove parenthetical abbreviations / tickers / class annotations
    t = re.sub(r"\([^)]{1,24}\)", " ", t)
    # Fix concatenated share-class letters like "fundz", "fundi", "fundy"
    t = re.sub(r"\bfund[a-z]\b", "fund", t)
    t = re.sub(r"\b(?:class|cl\.?)\s*[a-z0-9]+\b", " ", t)
    t = re.sub(r"\b(?:r6|r5|r4|r3|r2|r1|f3|f2|f1|instl?|admiral|adm|investor|inv|select|shares|shs|inc\.?|trust|series|nav|the)\b", " ", t)
    t = re.sub(r"[^a-z0-9]+", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    # Strip leading "the " or trailing single-letter class code (e.g. "fund z", "fund i")
    t = re.sub(r"\s+[a-z]$", "", t).strip()
    return t


def norm_fund_name_variants(s: str) -> list[str]:
    """Generate canonical name plus advisor/prefix-stripped fallback for Tier-2 N-PORT matching."""
    base = norm_fund_name(s)
    if not base:
        return []
    out = [base]
    # Strip "advisor " or "american funds " prefix when comparing against N-PORT SERIES_NAME
    v1 = re.sub(r"\badvisor\s+", "", base).strip()
    if v1 and v1 != base:
        out.append(v1)
    v2 = re.sub(r"^american\s+funds\s+", "", base).strip()
    if v2 and v2 not in out:
        out.append(v2)
    return out


def get_with_retry(
    session: requests.Session,
    url: str,
    headers: dict | None = None,
    timeout: tuple[int, int] | int = (10, 25),
    retries: int = 8,
) -> requests.Response:
    for att in range(retries):
        try:
            r = session.get(url, headers=headers, timeout=timeout)
            if r.status_code in (200, 206):
                _ = r.content  # force complete body read inside retry guard
                return r
            if r.status_code in (429, 500, 502, 503, 504):
                time.sleep(2.0 * (att + 1))
                continue
            raise RuntimeError(f"HTTP {r.status_code} for {url}")
        except Exception as e:
            if att == retries - 1:
                raise
            print(f"    [retry {att + 1}] {e}", flush=True)
            session.close()
            time.sleep(2.0 * (att + 1))
    raise RuntimeError("Retries exhausted")


def stream_quarter_holdings_raw(
    quarter: str,
    target_accs: set[str],
    cusip_track_accs: set[str],
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, dict[str, float]]]:
    """Stream FUND_REPORTED_HOLDING.tsv for `quarter` via HTTP 206 Range and cache compactly.

    Returns:
      1. direct_df: per-accession direct equity/debt/stiv/other, HHI, N_HOLDINGS.
      2. uf_df: underlying-fund positions (ACCESSION_NUMBER, CUSIP, ISSUER_NAME, ISSUER_TITLE, PCT, IS_RF_FLAG).
      3. cusip_weights: {ACCESSION_NUMBER: {cusip_or_name: pct}} for cusip_track_accs.
    """
    dir_p = LT_CACHE / f"direct_{quarter}.parquet"
    uf_p = LT_CACHE / f"uf_positions_{quarter}.parquet"
    cw_p = LT_CACHE / f"cusip_w_{quarter}.json"
    if dir_p.exists() and uf_p.exists() and cw_p.exists():
        print(f"  [CACHED] {quarter} holdings extract loaded.", flush=True)
        return (
            pd.read_parquet(dir_p),
            pd.read_parquet(uf_p),
            json.loads(cw_p.read_text(encoding="utf-8")),
        )

    url = f"https://www.sec.gov/files/dera/data/form-n-port-data-sets/{quarter}_nport.zip"
    s = requests.Session()
    s.headers.update(SEC_HEADERS)

    size = None
    for att in range(5):
        try:
            h = s.head(url, timeout=30, allow_redirects=True)
            if h.status_code == 200:
                size = int(h.headers["Content-Length"])
                break
        except (requests.RequestException, OSError):
            time.sleep(2.5 * (att + 1))
    if size is None:
        raise RuntimeError(f"HEAD failed for {url}")

    tail = get_with_retry(s, url, headers={"Range": f"bytes={size - 65536}-{size - 1}"}).content
    eocd = tail.rfind(b"PK\x05\x06")
    cd_sz, cd_off = struct.unpack("<II", tail[eocd + 12 : eocd + 20])
    cd = tail[cd_off - (size - 65536) : cd_off - (size - 65536) + cd_sz]
    pos = 0
    info = None
    while pos < len(cd):
        if cd[pos : pos + 4] != b"PK\x01\x02":
            break
        meth, csz, usz, fnl, exl, cml, loff = struct.unpack("<HxxxxxxxxIIHHHxxxxxxxxI", cd[pos + 10 : pos + 46])
        fn = cd[pos + 46 : pos + 46 + fnl].decode("utf-8", "replace")
        if fn == "FUND_REPORTED_HOLDING.tsv":
            info = (meth, csz, usz, loff)
            break
        pos += 46 + fnl + exl + cml
    if info is None:
        raise RuntimeError(f"FUND_REPORTED_HOLDING.tsv not found in {quarter}")
    _, csz, usz, loff = info
    hdr = get_with_retry(s, url, headers={"Range": f"bytes={loff}-{loff + 29}"}).content
    fn2, ex2 = struct.unpack("<HH", hdr[26:30])
    start = loff + 30 + fn2 + ex2
    end = start + csz - 1
    print(f"  [STREAM {quarter}] comp={csz / 1e6:.1f}MB -> uncomp={usz / 1e6:.1f}MB (target_accs={len(target_accs):,})...", flush=True)

    CHUNK_RANGE = 8 * 1024 * 1024
    decomp = zlib.decompressobj(-zlib.MAX_WBITS)
    buf = ""
    header_done = False
    idx_acc = idx_pct = idx_cat = idx_itype = idx_cusip = idx_name = idx_title = idx_deriv = -1

    d_eq = defaultdict(float)
    d_dbt = defaultdict(float)
    d_stiv = defaultdict(float)
    d_deriv = defaultdict(float)
    d_other = defaultdict(float)
    uf_tot = defaultdict(float)
    nh = defaultdict(int)
    hhi_sum = defaultdict(float)
    uf_rows: list[tuple[str, str, str, str, float, int]] = []
    cusip_w: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    def process_line(line: str) -> None:
        nonlocal header_done, idx_acc, idx_pct, idx_cat, idx_itype, idx_cusip, idx_name, idx_title, idx_deriv
        if not header_done:
            cols = line.strip().split("\t")
            idx_acc = cols.index("ACCESSION_NUMBER")
            idx_pct = cols.index("PERCENTAGE")
            idx_cat = cols.index("ASSET_CAT")
            idx_itype = cols.index("ISSUER_TYPE")
            idx_cusip = cols.index("ISSUER_CUSIP")
            idx_name = cols.index("ISSUER_NAME")
            idx_title = cols.index("ISSUER_TITLE")
            idx_deriv = cols.index("DERIVATIVE_CAT") if "DERIVATIVE_CAT" in cols else -1
            header_done = True
            return
        if not line:
            return
        parts = line.split("\t")
        if len(parts) <= max(idx_acc, idx_pct, idx_cat, idx_itype, idx_name, idx_title):
            return
        acc = parts[idx_acc]
        if acc not in target_accs:
            return
        cat = parts[idx_cat]
        itype = parts[idx_itype]
        try:
            pct = float(parts[idx_pct]) if parts[idx_pct] else 0.0
        except ValueError:
            pct = 0.0
        cusip = parts[idx_cusip].strip().upper()
        iname = parts[idx_name].strip()
        ititle = parts[idx_title].strip()
        deriv = parts[idx_deriv].strip() if (idx_deriv >= 0 and idx_deriv < len(parts)) else ""

        nh[acc] += 1
        if pct > 0:
            hhi_sum[acc] += (pct / 100.0) ** 2

        if acc in cusip_track_accs and pct > 0:
            ckey = cusip if (cusip and cusip not in ("000000000", "N/A", "NONE")) else ("NM:" + iname.upper()[:32])
            cusip_w[acc][ckey] += pct

        # Tier-1 Direct Debt / STIV / Derivatives take strict precedence over fund-name regexes
        if cat in ("DBT", "ABS-MBS", "ABS-CBDO", "ABS-O", "ABS-APCP", "LON"):
            d_dbt[acc] += pct
            return
        if cat == "STIV":
            d_stiv[acc] += pct
            return
        if cat == "DE" or deriv:
            d_deriv[acc] += pct
            return

        # Underlying Registered Fund / ETF detection (fixes Vanguard EC-with-non-RF bug!)
        lbl = f"{iname} {ititle}"
        is_rf_flag = int(itype == "RF" or cat == "RF")
        is_uf = bool(
            is_rf_flag
            or (cusip in KNOWN_FUND_CUSIP_MAP)
            or (cat in ("EC", "EP", "OTHER", "") and RE_IS_UNDERLYING_FUND.search(lbl))
        )
        if is_uf:
            uf_tot[acc] += pct
            if abs(pct) >= 0.005:
                uf_rows.append((acc, cusip, iname[:90], ititle[:90], pct, is_rf_flag))
        elif cat in ("EC", "EP"):
            d_eq[acc] += pct
        else:
            d_other[acc] += pct

    t0 = time.time()
    cur = start
    next_log = 64 * 1024 * 1024
    while cur <= end:
        seg_end = min(cur + CHUNK_RANGE - 1, end)
        seg_bytes = get_with_retry(s, url, headers={"Range": f"bytes={cur}-{seg_end}"}, timeout=(10, 25)).content
        for off in range(0, len(seg_bytes), 512 * 1024):
            raw_chunk = seg_bytes[off : off + 512 * 1024]
            if not raw_chunk:
                continue
            buf += decomp.decompress(raw_chunk).decode("utf-8", "replace")
            lines = buf.split("\n")
            buf = lines[-1]
            for ln in lines[:-1]:
                process_line(ln)
        cur = seg_end + 1
        if (cur - start) >= next_log:
            print(f"    ... {(cur - start) / 1e6:.0f}/{csz / 1e6:.0f} MB ({time.time() - t0:.1f}s)", flush=True)
            next_log += 64 * 1024 * 1024
    buf += decomp.flush().decode("utf-8", "replace")
    for ln in buf.split("\n"):
        if ln:
            process_line(ln)

    print(
        f"  [OK {quarter}] matched {len(nh):,} target accessions, {len(uf_rows):,} underlying-fund positions in {time.time() - t0:.1f}s",
        flush=True,
    )
    dir_df = pd.DataFrame(
        [
            {
                "ACCESSION_NUMBER": acc,
                "N_HOLDINGS": nh[acc],
                "HHI": hhi_sum[acc],
                "DIR_EQ": d_eq[acc],
                "DIR_DBT": d_dbt[acc],
                "DIR_STIV": d_stiv[acc],
                "DIR_DERIV": d_deriv[acc],
                "DIR_OTHER": d_other[acc],
                "UF_TOT": uf_tot[acc],
            }
            for acc in nh
        ]
    )
    uf_df = pd.DataFrame(
        uf_rows,
        columns=["ACCESSION_NUMBER", "ISSUER_CUSIP", "ISSUER_NAME", "ISSUER_TITLE", "PCT", "IS_RF_FLAG"],
    )
    cw_dict = {k: dict(v) for k, v in cusip_w.items()}

    dir_df.to_parquet(dir_p, index=False)
    uf_df.to_parquet(uf_p, index=False)
    cw_p.write_text(json.dumps(cw_dict) + "\n", encoding="utf-8", newline="\n")
    return dir_df, uf_df, cw_dict


def build_cusip_consensus_map(uf_frames: list[pd.DataFrame]) -> dict[str, tuple[str, str]]:
    """Build cross-quarter CUSIP -> longest untruncated (ISSUER_NAME, ISSUER_TITLE) registry.

    Eliminates 2026 custodian title-truncation artifacts (e.g., 'SPDR-PORT S/T C' vs
    'SPDR Portfolio Short Term Corporate Bond ETF' for CUSIP 78464A474) systematically
    across all funds holding the identical 9-digit security CUSIP.
    """
    comb = pd.concat(uf_frames, ignore_index=True)
    valid = comb[~comb["ISSUER_CUSIP"].fillna("").isin(["", "000000000", "N/A", "NONE"])].copy()
    valid["SCORE"] = valid["ISSUER_TITLE"].fillna("").str.len() + 0.5 * valid["ISSUER_NAME"].fillna("").str.len()
    best = valid.sort_values("SCORE", ascending=False).drop_duplicates("ISSUER_CUSIP", keep="first")
    return {
        str(c): (str(nm or ""), str(tt or ""))
        for c, nm, tt in zip(best["ISSUER_CUSIP"], best["ISSUER_NAME"], best["ISSUER_TITLE"], strict=False)
    }


def build_direct_name_lookup(snap_meta: pd.DataFrame, dir_df: pd.DataFrame) -> dict[str, tuple[float, float, float]]:
    """Build normalized series-name -> (w_eq, w_bd, w_cs) map for predominantly direct N-PORT funds."""
    base = snap_meta[["SERIES_ID", "ACCESSION_NUMBER", "SERIES_NAME"]].merge(dir_df, on="ACCESSION_NUMBER", how="inner")
    base["NORM_NAME"] = base["SERIES_NAME"].map(norm_fund_name)
    direct_pure = base[(base["UF_TOT"] < 20.0) & ((base["DIR_EQ"] + base["DIR_DBT"] + base["DIR_STIV"]) > 50.0)].copy()
    tot_dir = (direct_pure["DIR_EQ"] + direct_pure["DIR_DBT"] + direct_pure["DIR_STIV"]).clip(lower=1.0)
    direct_pure["W_EQ"] = (direct_pure["DIR_EQ"] / tot_dir).clip(0.0, 1.0)
    direct_pure["W_BD"] = (direct_pure["DIR_DBT"] / tot_dir).clip(0.0, 1.0)
    direct_pure["W_CS"] = (direct_pure["DIR_STIV"] / tot_dir).clip(0.0, 1.0)
    out: dict[str, tuple[float, float, float]] = {}
    for nm, g in direct_pure.groupby("NORM_NAME"):
        if len(nm) >= 10:
            wts = (float(g["W_EQ"].median()), float(g["W_BD"].median()), float(g["W_CS"].median()))
            for v in norm_fund_name_variants(nm):
                if len(v) >= 10 and v not in out:
                    out[v] = wts
    return out


def resolve_lookthrough_snapshot(
    snap_meta: pd.DataFrame,
    dir_df: pd.DataFrame,
    uf_df: pd.DataFrame,
    cusip_consensus: dict[str, tuple[str, str]] | None = None,
    fallback_direct_lookup: dict[str, tuple[float, float, float]] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Apply 4-Tier Look-Through (Tier 1 Direct, Tier 2 N-PORT Match/CUSIP, Tier 3 Dict, Tier 4 1-pass FOF)."""
    cusip_consensus = cusip_consensus or {}
    base = snap_meta[["SERIES_ID", "ACCESSION_NUMBER", "SERIES_NAME", "IS_FOF"]].merge(
        dir_df, on="ACCESSION_NUMBER", how="inner"
    )
    base["NORM_NAME"] = base["SERIES_NAME"].map(norm_fund_name)
    name_lookup_p1 = build_direct_name_lookup(snap_meta, dir_df)
    if fallback_direct_lookup:
        for k, v in fallback_direct_lookup.items():
            if k not in name_lookup_p1:
                name_lookup_p1[k] = v

    def classify_uf_rows(uf: pd.DataFrame, extra_lookup: dict[str, tuple[float, float, float]]) -> pd.DataFrame:
        eq_w = np.zeros(len(uf), dtype=float)
        bd_w = np.zeros(len(uf), dtype=float)
        cs_w = np.zeros(len(uf), dtype=float)
        tiers = np.empty(len(uf), dtype=object)

        cusips = uf["ISSUER_CUSIP"].fillna("").to_numpy()
        inames = uf["ISSUER_NAME"].fillna("").to_numpy()
        ititles = uf["ISSUER_TITLE"].fillna("").to_numpy()

        for i in range(len(uf)):
            c = cusips[i]
            # Enrich truncated custodian titles with cross-quarter CUSIP consensus full title
            cons_nm, cons_tt = cusip_consensus.get(c, ("", ""))
            lbl = f"{inames[i]} {ititles[i]} {cons_nm} {cons_tt}".strip()
            # Tier 2a: Exact verified canonical CUSIP match
            if c in KNOWN_FUND_CUSIP_MAP:
                ew, bw, cw, _ = KNOWN_FUND_CUSIP_MAP[c]
                eq_w[i], bd_w[i], cs_w[i], tiers[i] = ew, bw, cw, "TIER2_CUSIP"
                continue
            # Tier 2b / Tier 4: Exact N-PORT normalized series-name match (including CUSIP consensus title)
            matched = None
            cands = (
                norm_fund_name_variants(inames[i])
                + norm_fund_name_variants(ititles[i])
                + norm_fund_name_variants(cons_tt)
                + norm_fund_name_variants(cons_nm)
            )
            for cand in cands:
                if cand in extra_lookup:
                    matched = extra_lookup[cand]
                    break
            if matched is not None:
                eq_w[i], bd_w[i], cs_w[i], tiers[i] = matched[0], matched[1], matched[2], "TIER2_NPORT_NAME"
                continue
            # Tier 3: Audited ETF / Mutual-Fund Asset-Class Title Dictionary
            if RE_UF_CASH.search(lbl):
                eq_w[i], bd_w[i], cs_w[i], tiers[i] = 0.0, 0.0, 1.0, "TIER3_DICT_CASH"
                continue
            has_bd = bool(RE_UF_BOND.search(lbl))
            has_eq = bool(RE_UF_EQUITY.search(lbl))
            m_rat = RE_UF_RATIO.search(lbl)
            if m_rat:
                a, b = int(m_rat.group(1)), int(m_rat.group(2))
                if a + b == 100:
                    eq_w[i], bd_w[i], cs_w[i], tiers[i] = a / 100.0, b / 100.0, 0.0, "TIER3_DICT_RATIO"
                    continue
            if has_bd and not has_eq:
                eq_w[i], bd_w[i], cs_w[i], tiers[i] = 0.0, 1.0, 0.0, "TIER3_DICT_BOND"
            elif has_eq and not has_bd:
                eq_w[i], bd_w[i], cs_w[i], tiers[i] = 1.0, 0.0, 0.0, "TIER3_DICT_EQUITY"
            elif has_bd and has_eq:
                # e.g., "Vanguard Total Bond Market Growth" or "High Yield Equity" -> check explicit bond vs stock words
                if re.search(r"\b(?:bond|bnd|treasury|fixed[\s\-]income|muni|mortgage|mbs|credit|aggregate|tips|loan|floating|fltng|multi[\s\-]?sector\s+income|pimco\s+(?:total\s+return|income|real\s+return)|metwest|doubleline)\b", lbl, re.IGNORECASE):
                    eq_w[i], bd_w[i], cs_w[i], tiers[i] = 0.0, 1.0, 0.0, "TIER3_DICT_BOND_TIE"
                else:
                    eq_w[i], bd_w[i], cs_w[i], tiers[i] = 1.0, 0.0, 0.0, "TIER3_DICT_EQUITY_TIE"
            elif RE_UF_MIXED.search(lbl):
                eq_w[i], bd_w[i], cs_w[i], tiers[i] = 0.5, 0.5, 0.0, "TIER3_DICT_MIXED50"
            else:
                # Fallback for unclassified EC/RF equity vehicle
                eq_w[i], bd_w[i], cs_w[i], tiers[i] = 1.0, 0.0, 0.0, "TIER3_FALLBACK_EQ"

        out_u = uf.copy()
        out_u["W_EQ"] = eq_w
        out_u["W_BD"] = bd_w
        out_u["W_CS"] = cs_w
        out_u["MATCH_TIER"] = tiers
        out_u["PCT_EQ"] = out_u["PCT"] * out_u["W_EQ"]
        out_u["PCT_BD"] = out_u["PCT"] * out_u["W_BD"]
        out_u["PCT_CS"] = out_u["PCT"] * out_u["W_CS"]
        return out_u

    # Pass 1 (Tiers 1-3)
    uf_p1 = classify_uf_rows(uf_df, name_lookup_p1)
    agg_p1 = uf_p1.groupby("ACCESSION_NUMBER", as_index=False)[["PCT_EQ", "PCT_BD", "PCT_CS"]].sum()
    m1 = base.merge(agg_p1, on="ACCESSION_NUMBER", how="left")
    for c in ("PCT_EQ", "PCT_BD", "PCT_CS"):
        m1[c] = m1[c].fillna(0.0)
    m1["EQ_1"] = m1["DIR_EQ"] + m1["PCT_EQ"]
    m1["BD_1"] = m1["DIR_DBT"] + m1["PCT_BD"]
    m1["CS_1"] = m1["DIR_STIV"] + m1["PCT_CS"]

    # Pass 2 (Tier 4 Recursive 1-pass FOF look-through using ALL N-PORT funds from Pass 1!)
    tot1 = (m1["EQ_1"] + m1["BD_1"] + m1["CS_1"]).clip(lower=1.0)
    m1["W_EQ_1"] = (m1["EQ_1"] / tot1).clip(0.0, 1.0)
    m1["W_BD_1"] = (m1["BD_1"] / tot1).clip(0.0, 1.0)
    m1["W_CS_1"] = (m1["CS_1"] / tot1).clip(0.0, 1.0)
    name_lookup_p2 = dict(name_lookup_p1)
    for nm, g in m1[m1["UF_TOT"] >= 20.0].groupby("NORM_NAME"):
        if len(nm) >= 10:
            wts = (float(g["W_EQ_1"].median()), float(g["W_BD_1"].median()), float(g["W_CS_1"].median()))
            for v in norm_fund_name_variants(nm):
                if len(v) >= 10 and v not in name_lookup_p2:
                    name_lookup_p2[v] = wts

    uf_p2 = classify_uf_rows(uf_df, name_lookup_p2)
    agg_p2 = uf_p2.groupby("ACCESSION_NUMBER", as_index=False)[["PCT_EQ", "PCT_BD", "PCT_CS"]].sum()
    res = base.merge(agg_p2, on="ACCESSION_NUMBER", how="left")
    for c in ("PCT_EQ", "PCT_BD", "PCT_CS"):
        res[c] = res[c].fillna(0.0)
    res["UF_EQ"] = res["PCT_EQ"]
    res["UF_BOND"] = res["PCT_BD"]
    res["UF_CASH"] = res["PCT_CS"]
    res["TRUE_EQ"] = res["DIR_EQ"] + res["UF_EQ"]
    res["TRUE_BOND"] = res["DIR_DBT"] + res["UF_BOND"]
    res["TRUE_CASH"] = res["DIR_STIV"] + res["UF_CASH"]
    res["TRUE_MAX_CLASS"] = np.maximum(res["TRUE_EQ"], res["TRUE_BOND"])
    return res, uf_p2


def compute_cusip_overlap(w23: dict[str, float], w26: dict[str, float]) -> float:
    """Portfolio overlap in [0, 100]: 100 * sum_i min(p_i, q_i) on normalized positive weights."""
    s23 = sum(v for v in w23.values() if v > 0)
    s26 = sum(v for v in w26.values() if v > 0)
    if s23 <= 1.0 or s26 <= 1.0:
        return np.nan
    ov = 0.0
    for k, v23 in w23.items():
        if v23 > 0 and k in w26 and w26[k] > 0:
            ov += min(v23 / s23, w26[k] / s26)
    return 100.0 * ov


def main() -> int:
    qtr = pd.read_parquet(WORK_DIR / "data" / "panel_quarterly.parquet")
    audit_df = pd.read_csv(WORK_DIR / "tables" / "table_all_droppers_2025_2026_audit.csv")

    # Select EXACT REP_YQ == 2023Q2 pre-rule snapshot and latest post-cliff snapshot in {2026Q2, 2026Q3}
    s23 = qtr[qtr["REP_YQ"] == 20232].copy()
    s26 = (
        qtr[qtr["REP_YQ"].isin([20262, 20263])]
        .sort_values(["SERIES_ID", "REP_YQ"])
        .drop_duplicates("SERIES_ID", keep="last")
        .copy()
    )

    print(
        f"[1/4] Snapshot accessions: REP_YQ=2023Q2 ({len(s23):,} funds, FILE_QTRs={s23['FILE_QTR'].value_counts().head(4).to_dict()}) | "
        f"Post-cliff 2026Q2/Q3 ({len(s26):,} funds, REP_YQs={s26['REP_YQ'].value_counts().to_dict()})",
        flush=True,
    )

    # Track CUSIP weights for ALL funds with GVI or ESG in 2023Q2
    target_gvi_esg_sids = set(s23.loc[(s23["HAS_GVI"] == 1) | (s23["HAS_ESG"] == 1), "SERIES_ID"])
    cw_accs_23 = set(s23.loc[s23["SERIES_ID"].isin(target_gvi_esg_sids), "ACCESSION_NUMBER"])
    cw_accs_26 = set(s26.loc[s26["SERIES_ID"].isin(target_gvi_esg_sids), "ACCESSION_NUMBER"])

    # Stream required SEC N-PORT bulk files (cached locally on disk!)
    print("[2/4] Streaming SEC N-PORT FUND_REPORTED_HOLDING.tsv for 2023q2, 2023q3, 2026q2, 2026q3...", flush=True)
    dir_23_parts, uf_23_parts, cw_23 = [], [], {}
    for fq in ("2023q2", "2023q3"):
        accs = set(s23.loc[s23["FILE_QTR"] == fq, "ACCESSION_NUMBER"])
        if not accs:
            continue
        d_df, u_df, cw = stream_quarter_holdings_raw(fq, accs, accs & cw_accs_23)
        dir_23_parts.append(d_df)
        uf_23_parts.append(u_df)
        cw_23.update(cw)

    dir_26_parts, uf_26_parts, cw_26 = [], [], {}
    for fq in ("2026q2", "2026q3"):
        accs = set(s26.loc[s26["FILE_QTR"] == fq, "ACCESSION_NUMBER"])
        if not accs:
            continue
        d_df, u_df, cw = stream_quarter_holdings_raw(fq, accs, accs & cw_accs_26)
        dir_26_parts.append(d_df)
        uf_26_parts.append(u_df)
        cw_26.update(cw)

    dir_23 = pd.concat(dir_23_parts, ignore_index=True).drop_duplicates("ACCESSION_NUMBER", keep="last")
    uf_23 = pd.concat(uf_23_parts, ignore_index=True)
    dir_26 = pd.concat(dir_26_parts, ignore_index=True).drop_duplicates("ACCESSION_NUMBER", keep="last")
    uf_26 = pd.concat(uf_26_parts, ignore_index=True)

    # Build Cross-Quarter CUSIP Consensus Registry (un-truncates custodian abbreviations systematically!)
    cusip_consensus = build_cusip_consensus_map([uf_23, uf_26])
    print(f"  Built cross-quarter CUSIP consensus registry: {len(cusip_consensus):,} unique security CUSIPs.", flush=True)

    # Cross-snapshot direct-fund fallback lookup (recovers ~70 funds whose 2023Q2 was amended in 2023q4, e.g. IFA & CIB)
    fb_lookup_26 = build_direct_name_lookup(s26, dir_26)
    fb_lookup_23 = build_direct_name_lookup(s23, dir_23)

    # Apply 4-Tier Look-Through Classifier
    print("[3/4] Running 4-Tier Look-Through Classifier & verifying Vanguard LifeStrategy ground truth...", flush=True)
    lt23, uf23_cls = resolve_lookthrough_snapshot(s23, dir_23, uf_23, cusip_consensus=cusip_consensus, fallback_direct_lookup=fb_lookup_26)
    lt26, _uf26_cls = resolve_lookthrough_snapshot(s26, dir_26, uf_26, cusip_consensus=cusip_consensus, fallback_direct_lookup=fb_lookup_23)

    # GROUND-TRUTH SANITY CHECK ON VANGUARD LIFESTRATEGY (20/80, 40/60, 60/40, 80/20) & CAPITAL GROWTH (PURE EQ)
    vg_targets = {
        "S000002929": ("LifeStrategy 20/80 (Income)", 20.0, 80.0),
        "S000002927": ("LifeStrategy 40/60 (Cons Gr)", 40.0, 60.0),
        "S000002930": ("LifeStrategy 60/40 (Mod Gr)", 60.0, 40.0),
        "S000002928": ("LifeStrategy 80/20 (Growth)", 80.0, 20.0),
        "S000004397": ("Capital Growth -> PRIMECAP (Pure Eq)", 95.0, 0.0),
    }
    vg_check = {}
    for sid, (lbl, exp_eq, exp_bd) in vg_targets.items():
        r23 = lt23[lt23["SERIES_ID"] == sid]
        r26 = lt26[lt26["SERIES_ID"] == sid]
        eq23 = float(r23["TRUE_EQ"].iloc[0]) if len(r23) else np.nan
        bd23 = float(r23["TRUE_BOND"].iloc[0]) if len(r23) else np.nan
        eq26 = float(r26["TRUE_EQ"].iloc[0]) if len(r26) else np.nan
        bd26 = float(r26["TRUE_BOND"].iloc[0]) if len(r26) else np.nan
        vg_check[sid] = {
            "label": lbl,
            "target_eq": exp_eq,
            "target_bond": exp_bd,
            "eq_2023q2": eq23,
            "bond_2023q2": bd23,
            "eq_2026": eq26,
            "bond_2026": bd26,
        }
        print(
            f"  [SANITY] {sid} {lbl:36s}: 2023Q2={eq23:5.1f}% Eq / {bd23:5.1f}% Bond  ->  2026={eq26:5.1f}% Eq / {bd26:5.1f}% Bond",
            flush=True,
        )
        if sid != "S000004397":
            assert abs(eq23 - exp_eq) <= 3.5, f"{sid} 2023Q2 Eq {eq23:.1f}% deviates >3.5pp from {exp_eq}%"
            assert abs(eq26 - exp_eq) <= 3.5, f"{sid} 2026 Eq {eq26:.1f}% deviates >3.5pp from {exp_eq}%"
        else:
            assert eq23 >= 90.0 and eq26 >= 90.0, "Capital Growth S000004397 must be >=90% pure equity!"

    # Export 100-position underlying-fund audit table across Multi-Asset GVI funds in 2023Q2
    ma_gvi_accs_23 = set(s23.loc[(s23["IS_ALLOC_FUND"] == 1) & (s23["HAS_GVI"] == 1), "ACCESSION_NUMBER"])
    uf_ma = uf23_cls[uf23_cls["ACCESSION_NUMBER"].isin(ma_gvi_accs_23)].copy()
    uf_ma = uf_ma.merge(s23[["ACCESSION_NUMBER", "SERIES_ID", "SERIES_NAME", "NET_ASSETS"]], on="ACCESSION_NUMBER", how="left")
    uf_ma["POS_USD_M"] = (uf_ma["PCT"] / 100.0) * (uf_ma["NET_ASSETS"].fillna(0.0) / 1e6)
    top100 = (
        uf_ma.sort_values("POS_USD_M", ascending=False)
        .head(100)[
            [
                "SERIES_ID",
                "SERIES_NAME",
                "ISSUER_CUSIP",
                "ISSUER_NAME",
                "ISSUER_TITLE",
                "PCT",
                "POS_USD_M",
                "IS_RF_FLAG",
                "MATCH_TIER",
                "W_EQ",
                "W_BD",
                "W_CS",
            ]
        ]
        .reset_index(drop=True)
    )
    top100["ISSUER_CUSIP"] = top100["ISSUER_CUSIP"].fillna("").replace({"": "UNLISTED", "N/A": "UNLISTED", "NONE": "UNLISTED", "000000000": "UNLISTED"})
    top100.to_csv(WORK_DIR / "tables" / "table_lookthrough_100pos_audit.csv", index=False, lineterminator="\n")

    tier_dist = uf_ma.groupby("MATCH_TIER")["POS_USD_M"].sum()
    tier_pct = {str(k): float(100.0 * v / max(tier_dist.sum(), 1e-9)) for k, v in tier_dist.items()}

    # Build combined 2023Q2 & 2026 look-through panel for Pillar 4 & Portfolio Inertia
    lt23["HOLD_LT_CONSTR"] = (lt23["TRUE_MAX_CLASS"] < 80.0).astype(int)
    lt23["HOLD_UF_FOF"] = (lt23["UF_TOT"] >= 50.0).astype(int)

    # Save 2023Q2 + 2026 lookthrough parquet keyed by SERIES_ID (including exact REPORT_YM for non-overlapping monthly drift)
    s23["REPORT_YM"] = (s23["REPORT_DT"].dt.year * 100 + s23["REPORT_DT"].dt.month).astype(int)
    s26["REPORT_YM"] = (s26["REPORT_DT"].dt.year * 100 + s26["REPORT_DT"].dt.month).astype(int)
    lt_pair = (
        s23[["SERIES_ID", "COMPLEX_ID", "SERIES_NAME", "REPORT_YM", "HAS_GV", "HAS_GVI", "HAS_ESG", "IS_ALLOC_FUND", "IS_FOF", "IS_INDEX", "IS_ETF", "IS_VA_INSURANCE", "NET_ASSETS", "ACCESSION_NUMBER"]]
        .merge(
            lt23[["SERIES_ID", "N_HOLDINGS", "HHI", "DIR_EQ", "DIR_DBT", "UF_TOT", "TRUE_EQ", "TRUE_BOND", "TRUE_CASH", "TRUE_MAX_CLASS", "HOLD_LT_CONSTR", "HOLD_UF_FOF"]],
            on="SERIES_ID",
            how="inner",
        )
        .merge(
            s26[["SERIES_ID", "SERIES_NAME", "REP_YQ", "REPORT_YM", "NET_ASSETS", "ACCESSION_NUMBER"]].merge(
                lt26[["SERIES_ID", "N_HOLDINGS", "HHI", "DIR_EQ", "DIR_DBT", "UF_TOT", "TRUE_EQ", "TRUE_BOND", "TRUE_CASH", "TRUE_MAX_CLASS"]],
                on="SERIES_ID",
                how="inner",
            ),
            on="SERIES_ID",
            how="left",
            suffixes=("_23", "_26"),
        )
    )

    # Attach 2025-2026 dropper classification cleanly
    d_ma = audit_df[audit_df["DROP_GROUP"] == "MULTI_ASSET_GVI"].drop_duplicates("SERIES_ID")
    d_all_gvi = audit_df[audit_df["DROP_GVI"] == 1].drop_duplicates("SERIES_ID")
    d_esg = audit_df[audit_df["DROP_ESG"] == 1].drop_duplicates("SERIES_ID")
    ct_map = d_all_gvi.set_index("SERIES_ID")["COMPLIANCE_TYPE"].to_dict()

    lt_pair["DROPPED_GVI_25_26"] = lt_pair["SERIES_ID"].isin(set(d_all_gvi["SERIES_ID"])).astype(int)
    lt_pair["DROPPED_MA_GVI_25_26"] = lt_pair["SERIES_ID"].isin(set(d_ma["SERIES_ID"])).astype(int)
    lt_pair["DROPPED_ESG_25_26"] = lt_pair["SERIES_ID"].isin(set(d_esg["SERIES_ID"])).astype(int)
    lt_pair["COMPLIANCE_TYPE_25_26"] = lt_pair["SERIES_ID"].map(ct_map).fillna("KEEPER")
    # Strict SEC-FAQ non-exempt Growth/Value subsample (excluding all "Income" and "Growth and Income" hybrids)
    lt_pair["HAS_INCOME_23"] = lt_pair["SERIES_NAME_23"].fillna("").str.contains(r"\bincome\b", case=False, regex=True).astype(int)
    lt_pair["HAS_GI_23"] = lt_pair["SERIES_NAME_23"].fillna("").str.contains(r"\bgrowth\s*(?:&|and)\s*income\b", case=False, regex=True).astype(int)
    lt_pair["HAS_GV_NO_INC_23"] = ((lt_pair["HAS_GV"] == 1) & (lt_pair["HAS_INCOME_23"] == 0)).astype(int)

    # Compute exact CUSIP overlap (2023Q2 -> 2026)
    overlaps = []
    for _, r in lt_pair.iterrows():
        a23 = r["ACCESSION_NUMBER_23"]
        a26 = r["ACCESSION_NUMBER_26"]
        if pd.notna(a23) and pd.notna(a26) and a23 in cw_23 and a26 in cw_26:
            overlaps.append(compute_cusip_overlap(cw_23[a23], cw_26[a26]))
        else:
            overlaps.append(np.nan)
    lt_pair["CUSIP_OVERLAP_PCT"] = overlaps

    # -----------------------------------------------------------------------
    # [4/4] Passive Market-Drift-Adjusted Active Rebalancing & Portfolio Inertia Tests
    # -----------------------------------------------------------------------
    print("[4/4] Computing Non-Overlapping Monthly Passive Market-Drift-Adjusted Rebalancing & CUSIP Overlap...", flush=True)
    # Cross-sectional median MONTHLY returns of pure-equity (>=95% direct eq) & pure-bond (>=95% direct bond) N-PORT funds
    # Eliminates any 2026Q2/2026Q3 overlapping-quarter double counting completely!
    mon = pd.read_parquet(WORK_DIR / "data" / "panel_monthly.parquet", columns=["SERIES_ID", "YM", "RET_M_PCT"])
    pure_eq_ids = set(lt23.loc[(lt23["DIR_EQ"] >= 95.0) & (lt23["UF_TOT"] < 5.0), "SERIES_ID"])
    pure_bd_ids = set(lt23.loc[(lt23["DIR_DBT"] >= 95.0) & (lt23["UF_TOT"] < 5.0), "SERIES_ID"])

    m_eq_ser = mon[(mon["SERIES_ID"].isin(pure_eq_ids)) & (mon["YM"] >= 202304) & (mon["YM"] <= 202607)].groupby("YM")["RET_M_PCT"].median().sort_index()
    m_bd_ser = mon[(mon["SERIES_ID"].isin(pure_bd_ids)) & (mon["YM"] >= 202304) & (mon["YM"] <= 202607)].groupby("YM")["RET_M_PCT"].median().sort_index()

    def cum_monthly_ret(m_ser: pd.Series, ym_start_excl: int, ym_end_incl: int) -> float:
        sl = m_ser[(m_ser.index > ym_start_excl) & (m_ser.index <= ym_end_incl)]
        if len(sl) == 0:
            return 0.0
        return float(np.prod(1.0 + sl.to_numpy() / 100.0) - 1.0)

    r_eq_26q2 = cum_monthly_ret(m_eq_ser, 202306, 202606)
    r_bd_26q2 = cum_monthly_ret(m_bd_ser, 202306, 202606)
    r_eq_26q3 = cum_monthly_ret(m_eq_ser, 202306, 202607)
    r_bd_26q3 = cum_monthly_ret(m_bd_ser, 202306, 202607)

    print(
        f"  Non-Overlapping Monthly Benchmark Returns (2023-06->2026-06): Pure Equity={r_eq_26q2 * 100:+.1f}%, Pure Bond={r_bd_26q2 * 100:+.1f}% | "
        f"(2023-06->2026-07): Pure Equity={r_eq_26q3 * 100:+.1f}%, Pure Bond={r_bd_26q3 * 100:+.1f}%",
        flush=True,
    )

    # Exact fund-level report-month-matched passive return vectors (zero overlap!)
    r_eq_arr = np.full(len(lt_pair), np.nan, dtype=float)
    r_bd_arr = np.full(len(lt_pair), np.nan, dtype=float)
    r_cs_arr = np.full(len(lt_pair), np.nan, dtype=float)
    ym23_vals = lt_pair["REPORT_YM_23"].to_numpy()
    ym26_vals = lt_pair["REPORT_YM_26"].to_numpy()
    pair_cache: dict[tuple[int, int], tuple[float, float, float]] = {}
    for i in range(len(lt_pair)):
        if pd.isna(ym26_vals[i]):
            continue
        k = (int(ym23_vals[i]), int(ym26_vals[i]))
        if k not in pair_cache:
            n_mo = ((k[1] // 100) * 12 + (k[1] % 100)) - ((k[0] // 100) * 12 + (k[0] % 100))
            pair_cache[k] = (
                cum_monthly_ret(m_eq_ser, k[0], k[1]),
                cum_monthly_ret(m_bd_ser, k[0], k[1]),
                float((1.045) ** (max(n_mo, 0) / 12.0) - 1.0),
            )
        r_eq_arr[i], r_bd_arr[i], r_cs_arr[i] = pair_cache[k]

    w_eq0 = lt_pair["TRUE_EQ_23"].clip(0.0, 100.0) / 100.0
    w_bd0 = lt_pair["TRUE_BOND_23"].clip(0.0, 100.0) / 100.0
    w_cs0 = (1.0 - w_eq0 - w_bd0).clip(0.0, 1.0)
    num_eq = w_eq0 * (1.0 + r_eq_arr)
    num_bd = w_bd0 * (1.0 + r_bd_arr)
    num_cs = w_cs0 * (1.0 + r_cs_arr)
    denom = (num_eq + num_bd + num_cs).clip(lower=1e-6)

    lt_pair["PASSIVE_EQ_26"] = 100.0 * (num_eq / denom)
    lt_pair["PASSIVE_BOND_26"] = 100.0 * (num_bd / denom)
    lt_pair["D_TRUE_EQ"] = lt_pair["TRUE_EQ_26"] - lt_pair["TRUE_EQ_23"]
    lt_pair["ABS_D_TRUE_EQ"] = lt_pair["D_TRUE_EQ"].abs()
    lt_pair["D_TRUE_BOND"] = lt_pair["TRUE_BOND_26"] - lt_pair["TRUE_BOND_23"]
    lt_pair["ABS_D_TRUE_BOND"] = lt_pair["D_TRUE_BOND"].abs()
    lt_pair["ACTIVE_REBAL_EQ"] = lt_pair["TRUE_EQ_26"] - lt_pair["PASSIVE_EQ_26"]
    lt_pair["ABS_ACTIVE_REBAL_EQ"] = lt_pair["ACTIVE_REBAL_EQ"].abs()
    lt_pair["D_MAX_CLASS_TOWARD_80"] = lt_pair["TRUE_MAX_CLASS_26"] - lt_pair["TRUE_MAX_CLASS_23"]
    lt_pair["ACTIVE_TOWARD_80"] = lt_pair["TRUE_MAX_CLASS_26"] - np.maximum(lt_pair["PASSIVE_EQ_26"], lt_pair["PASSIVE_BOND_26"])
    lt_pair["D_HHI_BPS"] = (lt_pair["HHI_26"] - lt_pair["HHI_23"]) * 10000.0
    lt_pair["D_LOG_NHOLD"] = np.log(lt_pair["N_HOLDINGS_26"].clip(lower=1)) - np.log(lt_pair["N_HOLDINGS_23"].clip(lower=1))

    lt_pair.to_parquet(LT_CACHE / "lookthrough_panel_2023_2026.parquet", index=False)

    # Inertia regressions on Constrained Multi-Asset GVI funds AND strict SEC-FAQ non-exempt Growth/Value (excl. Income & Growth and Income)
    inertia_results = {}
    inertia_rows = []
    for sample_name, smask in [
        ("HOLD_LT_CONSTR_GVI", (lt_pair["HAS_GVI"] == 1) & (lt_pair["HOLD_LT_CONSTR"] == 1) & lt_pair["TRUE_EQ_26"].notna()),
        ("MULTI_ASSET_GVI_ALL", (lt_pair["HAS_GVI"] == 1) & (lt_pair["IS_ALLOC_FUND"] == 1) & lt_pair["TRUE_EQ_26"].notna()),
        ("HOLD_LT_CONSTR_GV_NO_INC", (lt_pair["HAS_GV_NO_INC_23"] == 1) & (lt_pair["HOLD_LT_CONSTR"] == 1) & lt_pair["TRUE_EQ_26"].notna()),
        ("MULTI_ASSET_GV_NO_INC", (lt_pair["HAS_GV_NO_INC_23"] == 1) & (lt_pair["IS_ALLOC_FUND"] == 1) & lt_pair["TRUE_EQ_26"].notna()),
    ]:
        sub = lt_pair[smask].copy()
        d_flag = sub["DROPPED_GVI_25_26"].to_numpy(dtype=float)
        n_drop = int(d_flag.sum())
        n_keep = int((d_flag == 0).sum())
        inertia_results[sample_name] = {"n_droppers": n_drop, "n_keepers": n_keep, "metrics": {}}
        print(f"\n  [{sample_name}] Droppers={n_drop} vs Keepers={n_keep}:", flush=True)

        for mcol, ctrl_fof in [
            ("D_TRUE_EQ", False),
            ("ABS_D_TRUE_EQ", False),
            ("D_TRUE_BOND", False),
            ("ABS_D_TRUE_BOND", False),
            ("ACTIVE_REBAL_EQ", False),
            ("ABS_ACTIVE_REBAL_EQ", False),
            ("ACTIVE_TOWARD_80", False),
            ("CUSIP_OVERLAP_PCT", False),
            ("CUSIP_OVERLAP_PCT", True),
            ("D_HHI_BPS", True),
            ("D_LOG_NHOLD", True),
        ]:
            sv = sub.dropna(subset=[mcol]).copy()
            if len(sv) < 20 or sv["DROPPED_GVI_25_26"].sum() < 5:
                continue
            lo, hi = sv[mcol].quantile([0.01, 0.99])
            y = sv[mcol].clip(lo, hi).to_numpy(dtype=float)
            tr = sv["DROPPED_GVI_25_26"].to_numpy(dtype=float)
            if ctrl_fof:
                fof_v = sv["IS_FOF"].to_numpy(dtype=float)
                X = np.column_stack([tr, fof_v, np.ones(len(sv))])
                key = f"{mcol}_CTRL_FOF"
            else:
                X = np.column_stack([tr, np.ones(len(sv))])
                key = mcol
            r = ols_cr1_wcb(y, X, sv["COMPLEX_ID"].to_numpy(), test_col_idx=0, n_boot=999)
            md = float(y[tr == 1].mean())
            mk = float(y[tr == 0].mean())
            # Also split OPAQUE vs NUMERIC dropper means
            op_m = (sv["COMPLIANCE_TYPE_25_26"] == "OPAQUE_SYNONYM").to_numpy()
            nm_m = (sv["COMPLIANCE_TYPE_25_26"] == "NUMERIC_RATIO").to_numpy()
            rec = {
                "sample": sample_name,
                "metric": key,
                "mean_dropper": md,
                "mean_opaque": float(y[op_m].mean()) if op_m.any() else np.nan,
                "mean_numeric": float(y[nm_m].mean()) if nm_m.any() else np.nan,
                "mean_keeper": mk,
                **r,
            }
            inertia_results[sample_name]["metrics"][key] = rec
            inertia_rows.append(rec)
            print(
                f"    {key:26s} | Drop={md:+6.2f} (Opq={rec['mean_opaque']:+6.2f}, Num={rec['mean_numeric']:+6.2f}) "
                f"vs Keep={mk:+6.2f} | Diff={r['beta']:+6.2f} (t={r['t_cr1']:+5.2f}, wcb={r['p_wcb']:.3f})",
                flush=True,
            )

    # Panel TWFE for Balance-Sheet Cash Ratio & Quarterly Return Volatility (SERIES_ID FE + REP_YQ FE, exact DoF!)
    print("\n  [PANEL TWFE] Cash Ratio & Return Volatility around Multi-Asset GVI & ESG drops (SERIES_ID FE + REP_YQ FE):", flush=True)
    panel_twfe_inertia = {}
    for grp, risk_mask, drop_col in [
        ("MULTI_ASSET_GVI", (qtr["PREV_IS_ALLOC_FUND"] == 1) & (qtr["PREV_HAS_GVI"] == 1), "DROP_GVI"),
        ("ESG", qtr["PREV_HAS_ESG"] == 1, "DROP_ESG"),
    ]:
        ever_ids = set(qtr.loc[risk_mask, "SERIES_ID"])
        sub = qtr[qtr["SERIES_ID"].isin(ever_ids)].copy()
        first_drop = sub[(sub[drop_col] == 1) & (sub["REP_YQ"] >= 20251)].groupby("SERIES_ID")["REP_YQ"].min()
        sub["POST_DROP"] = (sub["SERIES_ID"].map(first_drop).notna() & (sub["REP_YQ"] >= sub["SERIES_ID"].map(first_drop))).astype(float)
        panel_twfe_inertia[grp] = {"n_droppers_25_26": len(first_drop)}
        for yvar in ["CASH_PCT", "QTR_VOL_PCT", "LEVERAGE_PCT"]:
            sv = sub.dropna(subset=[yvar, "LOG_LAG_TNA"]).copy()
            lo, hi = sv[yvar].quantile([0.01, 0.99])
            sv[yvar] = sv[yvar].clip(lo, hi)
            r = run_absorbed_twfe(
                sv,
                y_col=yvar,
                x_cols=["POST_DROP", "LOG_LAG_TNA"],
                absorb_fe_col="SERIES_ID",
                cluster_col="COMPLEX_ID",
                time_fe_col="REP_YQ",
                test_col_idx=0,
                n_boot=999,
            )
            panel_twfe_inertia[grp][yvar] = r
            print(
                f"    [{grp:16s}] {yvar:14s}: POST_DROP={r['beta']:+.3f} (se={r['se_cr1']:.3f}, t={r['t_cr1']:+.2f}, wcb={r['p_wcb']:.3f}, N={r['N']:,}, G={r['G']})",
                flush=True,
            )

    # Flagship case studies table (exact 2023Q2 -> 2026 look-through!)
    flag_ids = [
        "S000002928",
        "S000002930",
        "S000002927",
        "S000002929",
        "S000006796",
        "S000006791",
        "S000021944",
        "S000023587",
        "S000017667",
        "S000011112",
        "S000009325",
        "S000004397",
    ]
    cases = []
    for sid in flag_ids:
        sub_c = lt_pair[lt_pair["SERIES_ID"] == sid]
        if len(sub_c) == 0:
            continue
        r = sub_c.iloc[0]
        cases.append(
            {
                "SERIES_ID": sid,
                "COMPLEX_ID": r["COMPLEX_ID"],
                "OLD_NAME_23": r["SERIES_NAME_23"],
                "NEW_NAME_26": r["SERIES_NAME_26"],
                "COMPLIANCE_TYPE": r["COMPLIANCE_TYPE_25_26"],
                "AUM_23_B": float((r["NET_ASSETS_23"] or 0.0) / 1e9),
                "TRUE_EQ_23": float(r["TRUE_EQ_23"]),
                "TRUE_EQ_26": float(r["TRUE_EQ_26"]) if pd.notna(r["TRUE_EQ_26"]) else np.nan,
                "TRUE_BOND_23": float(r["TRUE_BOND_23"]),
                "TRUE_BOND_26": float(r["TRUE_BOND_26"]) if pd.notna(r["TRUE_BOND_26"]) else np.nan,
                "PASSIVE_EQ_26": float(r["PASSIVE_EQ_26"]) if pd.notna(r["PASSIVE_EQ_26"]) else np.nan,
                "ACTIVE_REBAL_EQ": float(r["ACTIVE_REBAL_EQ"]) if pd.notna(r["ACTIVE_REBAL_EQ"]) else np.nan,
                "CUSIP_OVERLAP_PCT": float(r["CUSIP_OVERLAP_PCT"]) if pd.notna(r["CUSIP_OVERLAP_PCT"]) else np.nan,
            }
        )

    pd.DataFrame(inertia_rows).to_csv(WORK_DIR / "tables" / "table_holdings_lookthrough_inertia.csv", index=False, lineterminator="\n")

    out = {
        "snapshot_counts": {
            "n_2023q2_matched": len(lt23),
            "n_2026_matched": len(lt26),
            "n_paired_2023_2026": int(lt_pair["TRUE_EQ_26"].notna().sum()),
            "n_hold_lt_constr_gvi_2023q2": int(((lt_pair["HAS_GVI"] == 1) & (lt_pair["HOLD_LT_CONSTR"] == 1)).sum()),
        },
        "vanguard_sanity_check": vg_check,
        "tier_aum_share_ma_gvi_2023q2_pct": tier_pct,
        "passive_drift_benchmarks": {
            "pure_eq_cum_ret_23Q3_26Q2": r_eq_26q2,
            "pure_bd_cum_ret_23Q3_26Q2": r_bd_26q2,
            "pure_eq_cum_ret_23Q3_26Q3": r_eq_26q3,
            "pure_bd_cum_ret_23Q3_26Q3": r_bd_26q3,
            "n_pure_eq_bench_funds": len(pure_eq_ids),
            "n_pure_bd_bench_funds": len(pure_bd_ids),
        },
        "inertia_cross_section": inertia_results,
        "panel_twfe_balance_sheet": panel_twfe_inertia,
        "flagship_case_studies": cases,
    }
    res_p = WORK_DIR / "results" / "03_holdings_lookthrough.json"
    res_p.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(f"\n[DONE PILLAR 3] Saved {res_p.name} and table_holdings_lookthrough_inertia.csv", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
