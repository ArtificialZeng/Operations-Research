"""Pillar 1: Build clean REPORT_DATE-aligned quarterly & monthly SEC N-PORT + N-CEN panels.

Fixes every Wave-5 forensic defect:
1. Strict REPORT_DATE calendar-quarter alignment (`REP_YQ`) with explicit complete-quarter
   flag (`2020Q1-2026Q2`) vs. partial `2026Q3` (`IS_COMPLETE_QTR`), and clean NPORT-P/A
   amendment deduplication logging exact raw/amendment/final counts.
2. Excludes closed-end sentinel `SERIES_ID == 'S000000000'` (prevents cross-CIK collisions).
3. Unified `COMPLEX_ID` from N-CEN `FAMILY_INVESTMENT_COMPANY_NAME` + `ADVISER.tsv`
   (`ADVISER_TYPE == 'Advisor'`) + transparent Rule 0-10(a) parent-complex normalization
   (unifying WisdomTree, Quantified/Advisors Preferred, Fidelity, Vanguard, Prudential/PGIM,
   Brighthouse, BlackRock/iShares, Capital Group/American Funds, Goldman Sachs, State Street/SSGA).
4. Deterministic structural flags from N-CEN (`IS_FOF`, `IS_TARGET_DATE`, `IS_INDEX`,
   `IS_ETF` via FRI + `ETF.tsv`, `IS_MONEY_MARKET`, `IS_FEEDER`) and Variable-Annuity /
   Insurance-Dedicated Trust classifier (`IS_VA_INSURANCE`).
5. Audits the ~18.5% negative-redemption sign bug in N-PORT `REDEMPTION_FLOW_MON1/2/3`,
   computes `NET_FLOW = SALES + REINVEST - abs(REDEMPTION)`, and cross-validates quarterly
   N-PORT net flows against TNA-implied net flows (raw vs. fixed Pearson/Spearman jump).
6. Builds both `data/panel_quarterly.parquet` and `data/panel_monthly.parquet` (2020-01 to
   2026-09) using empirically verified chronological order (MON1=M-2, MON2=M-1, MON3=M).
7. Deterministic Bifurcated Compliance Taxonomy (`OPAQUE_SYNONYM`, `NUMERIC_RATIO`,
   `OTHER_MERGER_BRAND`) and full audit CSV (`tables/table_all_droppers_2025_2026_audit.csv`).
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import stats

READ_DATA_DIR = Path(r"D:\AI_Science\antigravity\frontier_discovery_20261126_wave5\data_i4")
WORK_DIR = Path(r"D:\AI_Science\antigravity\i4_boost_sec_names_rule_20261126")
DATA_OUT = WORK_DIR / "data"
TABLES_OUT = WORK_DIR / "tables"
RESULTS_OUT = WORK_DIR / "results"
for d in (DATA_OUT, TABLES_OUT, RESULTS_OUT):
    d.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Deterministic Regexes for Regulated Terms, Multi-Asset Mandates & Taxonomy
# ---------------------------------------------------------------------------
RE_GV = re.compile(r"\b(?:growth|value)\b", re.IGNORECASE)
RE_GROWTH = re.compile(r"\bgrowth\b", re.IGNORECASE)
RE_VALUE = re.compile(r"\bvalue\b", re.IGNORECASE)
RE_INCOME = re.compile(r"\bincome\b", re.IGNORECASE)
RE_INCOME_DIV = re.compile(r"\b(?:income|dividend)\b", re.IGNORECASE)

RE_ESG = re.compile(
    r"\b(?:esg|sustainab\w*|climate|impact|socially[\s\-]responsible|green|"
    r"low[\s\-]carbon|clean[\s\-]energy|net[\s\-]zero|carbon|renewable|"
    r"environment\w*|fossil[\s\-]free|decarbon\w*|biodivers\w*|stewardship|"
    r"energy[\s\-]transition)\b",
    re.IGNORECASE,
)

RE_LEGACY_2001 = re.compile(
    r"\b(?:municipal|muni|treasury|government|small[\s\-]cap|mid[\s\-]cap|"
    r"large[\s\-]cap|international|global|emerging[\s\-]market\w*|high[\s\-]yield|"
    r"short[\s\-]term|bond|equity)\b",
    re.IGNORECASE,
)

RE_ALLOC_NAME = re.compile(
    r"\b(?:allocation|balanced|lifestrategy|lifestyle|target[\s\-]risk|target[\s\-]date|"
    r"target[\s\-]retirement|multi[\s\-]asset|asset[\s\-]allocation|asset[\s\-]manager|"
    r"moderate|conservative|retirement|lifecycle|model[\s\-]portfolio|strategy[\s\-]fund|"
    r"strategy[\s\-]portfolio|blended|horizon|blueprint|"
    r"2025|2030|2035|2040|2045|2050|2055|2060|2065)\b",
    re.IGNORECASE,
)
# Exclude fixed-income "Balanced Risk" pure bond funds from name-based allocation match
RE_FIXED_INCOME_BALANCED_RISK = re.compile(r"fixed[\s\-]income.*balanced[\s\-]risk", re.IGNORECASE)

# Bifurcated Compliance Taxonomy inside Multi-Asset GVI droppers:
# 1) NUMERIC_RATIO: Explicit quantitative equity/bond allocation ratio or percentage added in NEW name
RE_NUMERIC_RATIO = re.compile(
    r"(?:\b\d{2}\s*/\s*\d{2}\b|\b(?:10|15|20|25|30|35|40|45|50|55|60|65|70|75|80|85|90)\s*%)",
    re.IGNORECASE,
)
# 2) OPAQUE_SYNONYM: Replaced G/V/I with SEC-exempt vague risk/style/allocation near-synonyms
RE_OPAQUE_SYNONYM = re.compile(
    r"\b(?:aggressive|moderately[\s\-]aggressive|moderate|moderately[\s\-]conservative|"
    r"conservative|opportunit\w*|dynamic|tactical|strategic|multi[\s\-]asset|"
    r"allocation|balanced|blend|core|total[\s\-]return|capital[\s\-]appreciation|"
    r"retirement|diversified|plus|advantage|select|yield)\b",
    re.IGNORECASE,
)

# Variable-Annuity / Insurance-Dedicated Trust deterministic classifier
RE_VA_TRUST = re.compile(
    r"(?:variable\s+(?:insurance|annuity|investment|products?|series|portfolio|trust|funds?|account)"
    r"|\bvip\b|\bast\b|advanced\s+series\s+trust|\bnvit\b|\blvip\b|\bbrighthouse\b"
    r"|\beq\s+advisors\b|\beq\s*/\s*|\bvoya\s+(?:investors|variable|partners|separate)\b"
    r"|\bsunamerica\s+series\b|\btransamerica\s+series\b|\bglobal\s+atlantic\b"
    r"|\bthrivent\s+series\s+fund\b|\bamerican\s+funds\s+insurance\s+series\b"
    r"|\bpvit\b|\bmml\s+series\b|\bjnl\s+series\b|\bprotective\s+investment\b"
    r"|\bdelaware\s+vip\b|\binvestor\s+freedom\b|\bmetropolitan\s+series\b"
    r"|\bprudential\s+series\b|\bjanus\s+aspen\b|\blinc\w*\s+variable\b"
    r"|\bpacific\s+select\s+fund\b|\bsecurian\s+funds\s+trust\b"
    r"|\bmainstay\s+vp\b|\bny\s+life\s+vp\b|\balger\s+portfolios\b"
    r"|\bfranklin\s+templeton\s+variable\b|\bt\.\s*rowe\s+price\s+(?:equity|fixed|international)\s+series\b)",
    re.IGNORECASE,
)
RE_VA_SERIES = re.compile(
    r"(?:^sa\s+|\bvp\b$|\bvip\b|\bast\b|\bnvit\b|\blvip\b|\bvif\b|\bvariable\s+(?:portfolio|fund)\b"
    r"|\bglobal\s+atlantic\b|\bbrighthouse\b|\bvoya\s+retirement\b|\bssga\s+.*\betf\s+portfolio\b"
    r"|\btops\s+.*etf\s+portfolio\b|\bstate\s+street\s+.*etf\s+portfolio\b)",
    re.IGNORECASE,
)

# Rule 0-10(a) Corporate Parent Unification (maps multi-trust / multi-adviser aliases of same sponsor)
PARENT_COMPLEX_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bVANGUARD\b", re.IGNORECASE), "VANGUARD"),
    (re.compile(r"\bFIDELITY\b|\bFMR\b|\bSTRATEGIC ADVISERS\b", re.IGNORECASE), "FIDELITY"),
    (re.compile(r"\bBLACKROCK\b|\bISHARES\b", re.IGNORECASE), "BLACKROCK / ISHARES"),
    (re.compile(r"\bPRUDENTIAL\b|\bPGIM\b|\bAST INVESTMENT SERVICES\b|\bADVANCED SERIES TRUST\b", re.IGNORECASE), "PRUDENTIAL / PGIM"),
    (re.compile(r"\bBRIGHTHOUSE\b", re.IGNORECASE), "BRIGHTHOUSE"),
    (re.compile(r"\bCAPITAL GROUP\b|\bCAPITAL RESEARCH AND MANAGEMENT\b|\bAMERICAN FUNDS\b", re.IGNORECASE), "CAPITAL GROUP / AMERICAN FUNDS"),
    (re.compile(r"\bSTATE STREET\b|\bSSGA\b", re.IGNORECASE), "STATE STREET / SSGA"),
    (re.compile(r"\bGOLDMAN SACHS\b", re.IGNORECASE), "GOLDMAN SACHS"),
    (re.compile(r"\bWISDOMTREE\b", re.IGNORECASE), "WISDOMTREE"),
    (re.compile(r"\bADVISORS PREFERRED\b|\bQUANTIFIED\b", re.IGNORECASE), "ADVISORS PREFERRED / QUANTIFIED"),
    (re.compile(r"\bSUNAMERICA\b|\bCOREBRIDGE\b", re.IGNORECASE), "SUNAMERICA / COREBRIDGE"),
    (re.compile(r"\bVOYA\b", re.IGNORECASE), "VOYA"),
    (re.compile(r"\bHARTFORD\b|\bLATTICE STRATEGIES\b", re.IGNORECASE), "HARTFORD"),
    (re.compile(r"\bTHRIVENT\b", re.IGNORECASE), "THRIVENT"),
    (re.compile(r"\bTRANSAMERICA\b", re.IGNORECASE), "TRANSAMERICA"),
    (re.compile(r"\bRUSSELL INVESTMENT\b|\bRUSSELL FUNDS\b", re.IGNORECASE), "RUSSELL INVESTMENTS"),
    (re.compile(r"\bGLOBAL ATLANTIC\b", re.IGNORECASE), "GLOBAL ATLANTIC"),
    (re.compile(r"\bLINCOLN\b|\bLINCOLNTRS\b|\bLVIP\b", re.IGNORECASE), "LINCOLN FINANCIAL"),
    (re.compile(r"\bNATIONWIDE\b|\bNVIT\b", re.IGNORECASE), "NATIONWIDE"),
    (re.compile(r"\bEQUITABLE\b|\bEQFUNDS\b|\bEQ ADVISORS\b", re.IGNORECASE), "EQUITABLE"),
    (re.compile(r"\bNORTHERN TRUST\b|\bNORTHERN FUNDS\b|\bFLEXSHARES\b", re.IGNORECASE), "NORTHERN TRUST"),
    (re.compile(r"\bFIRST EAGLE\b", re.IGNORECASE), "FIRST EAGLE"),
    (re.compile(r"\bPUTNAM\b", re.IGNORECASE), "PUTNAM"),
    (re.compile(r"\bFRANKLIN\b|\bTEMPLETON\b|\bLEGG MASON\b", re.IGNORECASE), "FRANKLIN TEMPLETON"),
    (re.compile(r"\bDWS\b|\bDBX\b|\bXTRACKERS\b|\bDEUTSCHE\b", re.IGNORECASE), "DWS / XTRACKERS"),
    (re.compile(r"\bNEUBERGER BERMAN\b", re.IGNORECASE), "NEUBERGER BERMAN"),
    (re.compile(r"\bAMERICAN CENTURY\b|\bAVANTIS\b", re.IGNORECASE), "AMERICAN CENTURY"),
    (re.compile(r"\bT\.?\s*ROWE PRICE\b", re.IGNORECASE), "T. ROWE PRICE"),
    (re.compile(r"\bMAIRS\s*&\s*POWER\b", re.IGNORECASE), "MAIRS & POWER"),
    (re.compile(r"\bJ\.?P\.?\s*MORGAN\b|\bJPMORGAN\b", re.IGNORECASE), "JPMORGAN"),
    (re.compile(r"\bINVESCO\b", re.IGNORECASE), "INVESCO"),
    (re.compile(r"\bSCHWAB\b", re.IGNORECASE), "CHARLES SCHWAB"),
    (re.compile(r"\bDIMENSIONAL\b|\bDFA\b", re.IGNORECASE), "DIMENSIONAL"),
    (re.compile(r"\bMORGAN STANLEY\b|\bEATON VANCE\b|\bCALVERT\b", re.IGNORECASE), "MORGAN STANLEY"),
    (re.compile(r"\bVALMARK\b|\bTOPS\b", re.IGNORECASE), "VALMARK / TOPS"),
    (re.compile(r"\bHOWARD CAPITAL\b|\bHCM\b", re.IGNORECASE), "HOWARD CAPITAL (HCM)"),
    (re.compile(r"\bJOHN HANCOCK\b", re.IGNORECASE), "JOHN HANCOCK"),
    (re.compile(r"\bJACKSON NATIONAL\b|\bJNL\b", re.IGNORECASE), "JACKSON NATIONAL"),
    (re.compile(r"\bALLSPRING\b|\bWELLS FARGO FUNDS\b", re.IGNORECASE), "ALLSPRING"),
    (re.compile(r"\bPACIFIC LIFE\b|\bPACIFIC FUNDS\b|\bARISTOTLE\b", re.IGNORECASE), "ARISTOTLE / PACIFIC"),
    (re.compile(r"\bMASSMUTUAL\b|\bMML\b", re.IGNORECASE), "MASSMUTUAL"),
    (re.compile(r"\bPRINCIPAL\b", re.IGNORECASE), "PRINCIPAL"),
    (re.compile(r"\bPIMCO\b", re.IGNORECASE), "PIMCO"),
    (re.compile(r"\bNU?VEEN\b|\bTIAA\b", re.IGNORECASE), "TIAA / NUVEEN"),
    (re.compile(r"\bJANUS HENDERSON\b", re.IGNORECASE), "JANUS HENDERSON"),
    (re.compile(r"\bMFS\b", re.IGNORECASE), "MFS"),
    (re.compile(r"\bCOLUMBIA\b|\bTHREADNEEDLE\b", re.IGNORECASE), "COLUMBIA THREADNEEDLE"),
    (re.compile(r"\bALLIANCEBERNSTEIN\b|\bAB FUNDS\b|\bAB CAP\b", re.IGNORECASE), "ALLIANCEBERNSTEIN"),
    (re.compile(r"\bNATIXIS\b|\bLOOMIS SAYLES\b|\bVAUGHAN NELSON\b", re.IGNORECASE), "NATIXIS"),
    (re.compile(r"\bGLOBAL X\b", re.IGNORECASE), "GLOBAL X"),
    (re.compile(r"\bKENSINGTON\b", re.IGNORECASE), "KENSINGTON"),
    (re.compile(r"\bFIRST TRUST\b", re.IGNORECASE), "FIRST TRUST"),
    (re.compile(r"\bVANECK\b|\bVAN ECK\b", re.IGNORECASE), "VANECK"),
    (re.compile(r"\bPROSHARES\b|\bPROFUNDS\b", re.IGNORECASE), "PROSHARES"),
    (re.compile(r"\bDIREXION\b", re.IGNORECASE), "DIREXION"),
    (re.compile(r"\bLORD ABBETT\b", re.IGNORECASE), "LORD ABBETT"),
    (re.compile(r"\bFEDERATED HERMES\b|\bFEDERATED\b", re.IGNORECASE), "FEDERATED HERMES"),
    (re.compile(r"\bSEI\b", re.IGNORECASE), "SEI"),
    (re.compile(r"\bNEW YORK LIFE\b|\bMAINSTAY\b|\bNYLIFE\b|\bINDEXIQ\b|\bNYLI\b", re.IGNORECASE), "NEW YORK LIFE / NYLI"),
    (re.compile(r"\bNORTHWESTERN MUTUAL\b|\bMASON STREET\b", re.IGNORECASE), "NORTHWESTERN MUTUAL"),
    (re.compile(r"\bAMERIPRISE\b|\bRIVERSOURCE\b", re.IGNORECASE), "RIVERSOURCE / AMERIPRISE"),
    (re.compile(r"\bBNY MELLON\b|\bDREYFUS\b", re.IGNORECASE), "BNY MELLON"),
    (re.compile(r"\bUBS\b", re.IGNORECASE), "UBS"),
    (re.compile(r"\bMACQUARIE\b|\bDELAWARE\b", re.IGNORECASE), "MACQUARIE / DELAWARE"),
    (re.compile(r"\bVICTORY\b", re.IGNORECASE), "VICTORY CAPITAL"),
    (re.compile(r"\bWELLS FARGO\b", re.IGNORECASE), "WELLS FARGO"),
    (re.compile(r"\bGUGGENHEIM\b", re.IGNORECASE), "GUGGENHEIM"),
    (re.compile(r"\bHARBOR\b", re.IGNORECASE), "HARBOR"),
    (re.compile(r"\bDODGE\s*&\s*COX\b", re.IGNORECASE), "DODGE & COX"),
    (re.compile(r"\bBAIRD\b", re.IGNORECASE), "BAIRD"),
    (re.compile(r"\bPARNASSUS\b", re.IGNORECASE), "PARNASSUS"),
    (re.compile(r"\bCALAMOS\b", re.IGNORECASE), "CALAMOS"),
    (re.compile(r"\bCOHEN\s*&\s*STEERS\b", re.IGNORECASE), "COHEN & STEERS"),
    (re.compile(r"\bHOTCHKIS\b", re.IGNORECASE), "HOTCHKIS & WILEY"),
    (re.compile(r"\bMOERUS\b", re.IGNORECASE), "MOERUS"),
    (re.compile(r"\bDEFIANCE\b", re.IGNORECASE), "DEFIANCE"),
    (re.compile(r"\bDONOGHUE FORLINES\b", re.IGNORECASE), "DONOGHUE FORLINES"),
    (re.compile(r"\bAMPLIFY\b|\bAMPLFY\b", re.IGNORECASE), "AMPLIFY INVESTMENTS"),
    (re.compile(r"\bTIDAL\b|\bTOROSO\b", re.IGNORECASE), "TIDAL INVESTMENTS"),
    (re.compile(r"\bABRDN\b|\bABERDEEN\b", re.IGNORECASE), "ABRDN / ABERDEEN"),
    (re.compile(r"\bBROOKFIELD\b", re.IGNORECASE), "BROOKFIELD"),
    (re.compile(r"\bSIMPLIFY\b", re.IGNORECASE), "SIMPLIFY ASSET"),
    (re.compile(r"\bALGER\b|\bALGERFUNDS\b", re.IGNORECASE), "ALGER"),
    (re.compile(r"\bFORUM\s+(?:FAMILY|FMLY|FUNDS)\b", re.IGNORECASE), "FORUM FUNDS"),
    (re.compile(r"\bGMO\b", re.IGNORECASE), "GMO"),
    (re.compile(r"\bSEGALL BRYANT\b", re.IGNORECASE), "SEGALL BRYANT & HAMILL"),
    (re.compile(r"\bGREAT[\-\s]WEST\b|\bEMPOWER\b", re.IGNORECASE), "EMPOWER / GREAT-WEST"),
    (re.compile(r"\bPAX\s*WORLD\b|\bIMPAX\b", re.IGNORECASE), "IMPAX / PAX WORLD"),
    (re.compile(r"\bAMG\s*FUNDS\b|\bAMGFUNDS", re.IGNORECASE), "AMG FUNDS"),
    (re.compile(r"\bVIRTUS\b|\bALLIANZ\b", re.IGNORECASE), "VIRTUS"),
    (re.compile(r"\bPAYDEN\b", re.IGNORECASE), "PAYDEN & RYGEL"),
    (re.compile(r"\bDAVENPORT\b", re.IGNORECASE), "DAVENPORT & COMPANY"),
]


def canonicalize_complex(raw_family: str | None, raw_adviser: str | None, raw_reg: str | None, cik: str | None) -> str:
    """Map raw N-CEN family / primary adviser / registrant into a unified Rule 0-10(a) COMPLEX_ID."""
    fam = (raw_family or "").strip()
    adv = (raw_adviser or "").strip()
    reg = (raw_reg or "").strip()

    # Priority 1: Explicit family name if non-empty; otherwise primary adviser; otherwise registrant; else CIK
    primary = fam if fam else (adv if adv else (reg if reg else f"CIK_{(cik or 'UNK').strip()}"))
    norm = re.sub(r"\s+", " ", primary).strip().upper()
    norm_no_punct = re.sub(r"[,.;]+$", "", norm).strip()

    # Check parent unification rules against family first, then adviser, then registrant
    for candidate in (fam, adv, reg):
        if not candidate:
            continue
        for pat, canon in PARENT_COMPLEX_RULES:
            if pat.search(candidate):
                return canon

    # Strip standard legal suffixes to merge minor punctuation/LLC differences
    cleaned = re.sub(
        r"\b(?:LLC|L\.L\.C\.|INC\.?|CORP\.?|CORPORATION|L\.P\.|LP|LLP|LTD\.?|CO\.?|"
        r"MANAGEMENT|ADVISORS?|ADVISERS?|GROUP OF FUNDS|FUND COMPLEX|FUNDS?|TRUST|SERIES)\b",
        "",
        norm_no_punct,
    )
    cleaned = re.sub(r"[^A-Z0-9&/\-\s]+", " ", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) >= 3 else norm_no_punct


def classify_compliance_type(old_name: str, new_name: str) -> str:
    """Deterministic Bifurcated Compliance Taxonomy for Multi-Asset GVI droppers.

    1. NUMERIC_RATIO: New name introduces explicit quantitative equity/bond ratio or %
       (e.g., 80/20, 60/40, 40/60, 20/80, 70%) not present in old name.
    2. OPAQUE_SYNONYM: Replaces G/V/I with SEC-exempt vague risk/style/allocation near-synonyms
       (Aggressive, Moderately Aggressive, Moderate, Conservative, Opportunities, Dynamic,
       Tactical, Strategic, Multi-Asset, Allocation, Balanced, Retirement, Plus, etc.)
       without introducing an explicit numeric ratio.
    3. OTHER_MERGER_BRAND: Residual brand/subadviser rename.
    """
    old_s = old_name or ""
    new_s = new_name or ""
    if RE_NUMERIC_RATIO.search(new_s) and not RE_NUMERIC_RATIO.search(old_s):
        return "NUMERIC_RATIO"
    if RE_OPAQUE_SYNONYM.search(new_s):
        return "OPAQUE_SYNONYM"
    return "OTHER_MERGER_BRAND"


def load_ncen_metadata() -> tuple[pd.DataFrame, dict]:
    """Load all 27 N-CEN quarters (SUBMISSION, REGISTRANT, FUND_REPORTED_INFO, ADVISER, ETF)."""
    print("[1/5] Loading 27 N-CEN quarters (FRI + REGISTRANT + ADVISER + ETF)...", flush=True)
    ncen_dir = READ_DATA_DIR / "ncen"
    qdirs = sorted([d for d in ncen_dir.iterdir() if d.is_dir()])

    rows = []
    etf_series_set: set[str] = set()
    for qd in qdirs:
        sub_p = qd / "SUBMISSION.tsv"
        reg_p = qd / "REGISTRANT.tsv"
        fri_p = qd / "FUND_REPORTED_INFO.tsv"
        adv_p = qd / "ADVISER.tsv"
        etf_p = qd / "ETF.tsv"
        if not (sub_p.exists() and reg_p.exists() and fri_p.exists()):
            continue

        sub = pd.read_csv(sub_p, sep="\t", usecols=["ACCESSION_NUMBER", "FILING_DATE"], dtype=str, low_memory=False)
        reg = pd.read_csv(
            reg_p,
            sep="\t",
            usecols=["ACCESSION_NUMBER", "CIK", "REGISTRANT_NAME", "FAMILY_INVESTMENT_COMPANY_NAME"],
            dtype=str,
            low_memory=False,
        )
        fri = pd.read_csv(
            fri_p,
            sep="\t",
            usecols=[
                "FUND_ID",
                "ACCESSION_NUMBER",
                "SERIES_ID",
                "IS_ETF",
                "IS_INDEX",
                "IS_MONEY_MARKET",
                "IS_TARGET_DATE",
                "IS_FUND_OF_FUND",
                "IS_MASTER_FEEDER",
                "MANAGEMENT_FEE",
                "NET_OPERATING_EXPENSES",
            ],
            dtype=str,
            low_memory=False,
        )
        if adv_p.exists():
            adv = pd.read_csv(
                adv_p,
                sep="\t",
                usecols=["FUND_ID", "ADVISER_TYPE", "ADVISER_NAME"],
                dtype=str,
                low_memory=False,
            )
            adv_prim = adv[adv["ADVISER_TYPE"].str.strip().str.lower() == "advisor"].drop_duplicates(
                "FUND_ID", keep="first"
            )
            fri = fri.merge(adv_prim[["FUND_ID", "ADVISER_NAME"]], on="FUND_ID", how="left")
        else:
            fri["ADVISER_NAME"] = np.nan

        if etf_p.exists():
            etf_df = pd.read_csv(etf_p, sep="\t", usecols=["SERIES_ID"], dtype=str, low_memory=False)
            etf_series_set.update(etf_df["SERIES_ID"].dropna().str.strip().tolist())

        m = fri.merge(reg, on="ACCESSION_NUMBER", how="left").merge(sub, on="ACCESSION_NUMBER", how="left")
        rows.append(m)

    ncen = pd.concat(rows, ignore_index=True)
    ncen = ncen[ncen["SERIES_ID"].notna()].copy()
    ncen["SERIES_ID"] = ncen["SERIES_ID"].str.strip()
    ncen = ncen[ncen["SERIES_ID"].str.match(r"^S\d{9}$") & (ncen["SERIES_ID"] != "S000000000")].copy()
    ncen["FILING_DT"] = pd.to_datetime(ncen["FILING_DATE"], format="mixed", errors="coerce")
    ncen = ncen.sort_values(["FILING_DT", "ACCESSION_NUMBER"])

    # Pre-rule snapshot (latest <= 2023-09-20) with earliest-available fallback for post-adoption entrants
    pre = ncen[ncen["FILING_DT"] <= "2023-09-20"].drop_duplicates("SERIES_ID", keep="last")
    first_any = ncen.drop_duplicates("SERIES_ID", keep="first")
    meta = pd.concat([pre, first_any[~first_any["SERIES_ID"].isin(pre["SERIES_ID"])]], ignore_index=True)

    # Also capture latest non-null ADVISER_NAME / FAMILY_INVESTMENT_COMPANY_NAME if missing in pre
    latest_adv = ncen.dropna(subset=["ADVISER_NAME"]).drop_duplicates("SERIES_ID", keep="last").set_index("SERIES_ID")["ADVISER_NAME"]
    latest_fam = (
        ncen[ncen["FAMILY_INVESTMENT_COMPANY_NAME"].fillna("").str.strip() != ""]
        .drop_duplicates("SERIES_ID", keep="last")
        .set_index("SERIES_ID")["FAMILY_INVESTMENT_COMPANY_NAME"]
    )
    meta["ADVISER_NAME"] = meta["ADVISER_NAME"].fillna(meta["SERIES_ID"].map(latest_adv))
    blank_fam = meta["FAMILY_INVESTMENT_COMPANY_NAME"].fillna("").str.strip() == ""
    meta.loc[blank_fam, "FAMILY_INVESTMENT_COMPANY_NAME"] = meta.loc[blank_fam, "SERIES_ID"].map(latest_fam)

    # Capture pre-rule and post-rule expense ratios for mechanism analysis
    ncen["EXP_NUM"] = pd.to_numeric(ncen["NET_OPERATING_EXPENSES"], errors="coerce")
    ncen["MGMT_NUM"] = pd.to_numeric(ncen["MANAGEMENT_FEE"], errors="coerce")
    exp_pre = (
        ncen[(ncen["FILING_DT"] >= "2022-01-01") & (ncen["FILING_DT"] <= "2023-09-20")]
        .dropna(subset=["EXP_NUM"])
        .drop_duplicates("SERIES_ID", keep="last")
        .set_index("SERIES_ID")["EXP_NUM"]
    )
    exp_post = (
        ncen[ncen["FILING_DT"] >= "2025-10-01"]
        .dropna(subset=["EXP_NUM"])
        .drop_duplicates("SERIES_ID", keep="last")
        .set_index("SERIES_ID")["EXP_NUM"]
    )
    mgmt_pre = (
        ncen[(ncen["FILING_DT"] >= "2022-01-01") & (ncen["FILING_DT"] <= "2023-09-20")]
        .dropna(subset=["MGMT_NUM"])
        .drop_duplicates("SERIES_ID", keep="last")
        .set_index("SERIES_ID")["MGMT_NUM"]
    )

    meta["EXP_PRE_NCEN"] = meta["SERIES_ID"].map(exp_pre)
    meta["EXP_POST_NCEN"] = meta["SERIES_ID"].map(exp_post)
    meta["MGMT_FEE_PRE_NCEN"] = meta["SERIES_ID"].map(mgmt_pre)

    # Structural boolean flags (ever-Y for ETF/ETF.tsv, pre-rule for FOF/TD/INDEX/MM/FEEDER)
    ever_etf = set(ncen.loc[ncen["IS_ETF"] == "Y", "SERIES_ID"]) | etf_series_set
    meta["IS_ETF"] = meta["SERIES_ID"].isin(ever_etf).astype(int)
    meta["IS_INDEX"] = (meta["IS_INDEX"] == "Y").astype(int)
    meta["IS_FOF"] = (meta["IS_FUND_OF_FUND"] == "Y").astype(int)
    meta["IS_TARGET_DATE"] = (meta["IS_TARGET_DATE"] == "Y").astype(int)
    meta["IS_MONEY_MARKET"] = (meta["IS_MONEY_MARKET"] == "Y").astype(int)
    meta["IS_FEEDER"] = (meta["IS_MASTER_FEEDER"] == "Y").astype(int)

    # Build unified Rule 0-10(a) COMPLEX_ID
    meta["COMPLEX_ID"] = [
        canonicalize_complex(f, a, r, c)
        for f, a, r, c in zip(
            meta["FAMILY_INVESTMENT_COMPANY_NAME"].fillna(""),
            meta["ADVISER_NAME"].fillna(""),
            meta["REGISTRANT_NAME"].fillna(""),
            meta["CIK"].fillna(""),
            strict=False,
        )
    ]

    ncen_stats = {
        "n_ncen_quarters": len(qdirs),
        "n_ncen_unique_series": len(meta),
        "n_ncen_matched_primary_adviser": int(meta["ADVISER_NAME"].notna().sum()),
        "n_ncen_unique_complexes": int(meta["COMPLEX_ID"].nunique()),
        "n_etf_series": int(meta["IS_ETF"].sum()),
        "n_fof_series": int(meta["IS_FOF"].sum()),
        "n_target_date_series": int(meta["IS_TARGET_DATE"].sum()),
        "n_index_series": int(meta["IS_INDEX"].sum()),
        "n_money_market_series": int(meta["IS_MONEY_MARKET"].sum()),
    }
    print(
        f"  N-CEN loaded: {ncen_stats['n_ncen_unique_series']:,} unique series, "
        f"{ncen_stats['n_ncen_matched_primary_adviser']:,} primary adviser matches, "
        f"{ncen_stats['n_ncen_unique_complexes']:,} unified complexes.",
        flush=True,
    )
    keep_cols = [
        "SERIES_ID",
        "COMPLEX_ID",
        "FAMILY_INVESTMENT_COMPANY_NAME",
        "ADVISER_NAME",
        "IS_ETF",
        "IS_INDEX",
        "IS_FOF",
        "IS_TARGET_DATE",
        "IS_MONEY_MARKET",
        "IS_FEEDER",
        "EXP_PRE_NCEN",
        "EXP_POST_NCEN",
        "MGMT_FEE_PRE_NCEN",
    ]
    return meta[keep_cols].copy(), ncen_stats


def main() -> int:
    ncen_meta, ncen_stats = load_ncen_metadata()

    print("[2/5] Loading 28 N-PORT quarters (2019Q4-2026Q3) with strict REPORT_DATE alignment...", flush=True)
    nport_dir = READ_DATA_DIR / "nport"
    qdirs = sorted([d for d in nport_dir.iterdir() if d.is_dir()])

    np_rows = []
    ret_rows = []
    for qd in qdirs:
        sub = pd.read_csv(
            qd / "SUBMISSION.tsv",
            sep="\t",
            usecols=["ACCESSION_NUMBER", "FILING_DATE", "SUB_TYPE", "REPORT_ENDING_PERIOD", "REPORT_DATE", "IS_LAST_FILING"],
            dtype=str,
            low_memory=False,
        )
        reg = pd.read_csv(
            qd / "REGISTRANT.tsv",
            sep="\t",
            usecols=["ACCESSION_NUMBER", "CIK", "REGISTRANT_NAME"],
            dtype=str,
            low_memory=False,
        )
        fri_cols = [
            "ACCESSION_NUMBER",
            "SERIES_NAME",
            "SERIES_ID",
            "TOTAL_ASSETS",
            "TOTAL_LIABILITIES",
            "NET_ASSETS",
            "CASH_NOT_RPTD_IN_C_OR_D",
            "SALES_FLOW_MON1",
            "REINVESTMENT_FLOW_MON1",
            "REDEMPTION_FLOW_MON1",
            "SALES_FLOW_MON2",
            "REINVESTMENT_FLOW_MON2",
            "REDEMPTION_FLOW_MON2",
            "SALES_FLOW_MON3",
            "REINVESTMENT_FLOW_MON3",
            "REDEMPTION_FLOW_MON3",
        ]
        fri = pd.read_csv(qd / "FUND_REPORTED_INFO.tsv", sep="\t", usecols=fri_cols, dtype=str, low_memory=False)
        m = fri.merge(sub, on="ACCESSION_NUMBER", how="inner").merge(reg, on="ACCESSION_NUMBER", how="left")
        m["FILE_QTR"] = qd.name
        np_rows.append(m)

        mtr = pd.read_csv(
            qd / "MONTHLY_TOTAL_RETURN.tsv",
            sep="\t",
            usecols=["ACCESSION_NUMBER", "MONTHLY_TOTAL_RETURN1", "MONTHLY_TOTAL_RETURN2", "MONTHLY_TOTAL_RETURN3"],
            dtype=str,
            low_memory=False,
        )
        for c in ["MONTHLY_TOTAL_RETURN1", "MONTHLY_TOTAL_RETURN2", "MONTHLY_TOTAL_RETURN3"]:
            mtr[c] = pd.to_numeric(mtr[c], errors="coerce")
        ret_rows.append(
            mtr.groupby("ACCESSION_NUMBER", as_index=False)[
                ["MONTHLY_TOTAL_RETURN1", "MONTHLY_TOTAL_RETURN2", "MONTHLY_TOTAL_RETURN3"]
            ].mean()
        )

    raw_nport = pd.concat(np_rows, ignore_index=True)
    rets = pd.concat(ret_rows, ignore_index=True).drop_duplicates("ACCESSION_NUMBER", keep="last")
    raw_nport = raw_nport.merge(rets, on="ACCESSION_NUMBER", how="left")
    del np_rows, ret_rows, rets

    n_total_raw_all = len(raw_nport)
    raw_nport["SERIES_ID"] = raw_nport["SERIES_ID"].fillna("").str.strip()
    n_cef_sentinel = int((raw_nport["SERIES_ID"] == "S000000000").sum())
    n_blank_sid = int((raw_nport["SERIES_ID"] == "").sum())
    nport = raw_nport[raw_nport["SERIES_ID"].str.match(r"^S\d{9}$") & (raw_nport["SERIES_ID"] != "S000000000")].copy()
    del raw_nport

    n_raw_valid_sid = len(nport)
    n_sub_orig = int((nport["SUB_TYPE"] == "NPORT-P").sum())
    n_sub_amend = int((nport["SUB_TYPE"] == "NPORT-P/A").sum())

    # Convert numeric columns BEFORE dedup to audit raw negative redemptions cleanly
    num_cols = [
        "TOTAL_ASSETS",
        "TOTAL_LIABILITIES",
        "NET_ASSETS",
        "CASH_NOT_RPTD_IN_C_OR_D",
        "SALES_FLOW_MON1",
        "REINVESTMENT_FLOW_MON1",
        "REDEMPTION_FLOW_MON1",
        "SALES_FLOW_MON2",
        "REINVESTMENT_FLOW_MON2",
        "REDEMPTION_FLOW_MON2",
        "SALES_FLOW_MON3",
        "REINVESTMENT_FLOW_MON3",
        "REDEMPTION_FLOW_MON3",
    ]
    for col in num_cols:
        nport[col] = pd.to_numeric(nport[col], errors="coerce")

    # Audit negative redemptions across all raw valid filings
    neg_red_audit = {}
    tot_nonnull_red = 0
    tot_nonzero_red = 0
    tot_neg_red = 0
    for k in (1, 2, 3):
        s = nport[f"REDEMPTION_FLOW_MON{k}"].dropna()
        snz = s[s != 0]
        n_neg = int((s < 0).sum())
        tot_nonnull_red += len(s)
        tot_nonzero_red += len(snz)
        tot_neg_red += n_neg
        neg_red_audit[f"MON{k}"] = {
            "n_nonnull": len(s),
            "n_nonzero": len(snz),
            "n_negative": n_neg,
            "pct_negative_of_nonnull": float(100.0 * n_neg / max(len(s), 1)),
            "pct_negative_of_nonzero": float(100.0 * n_neg / max(len(snz), 1)),
        }
    neg_red_audit["POOLED_MON1_TO_MON3"] = {
        "n_nonnull": int(tot_nonnull_red),
        "n_nonzero": int(tot_nonzero_red),
        "n_negative": int(tot_neg_red),
        "pct_negative_of_nonnull": float(100.0 * tot_neg_red / max(tot_nonnull_red, 1)),
        "pct_negative_of_nonzero": float(100.0 * tot_neg_red / max(tot_nonzero_red, 1)),
    }

    # Parse dates & build exact REPORT_DATE quarter (`REP_YQ`)
    nport["REPORT_DT"] = pd.to_datetime(nport["REPORT_DATE"], format="mixed", errors="coerce")
    nport["FILING_DT"] = pd.to_datetime(nport["FILING_DATE"], format="mixed", errors="coerce")
    nport["FYE_DT"] = pd.to_datetime(nport["REPORT_ENDING_PERIOD"], format="mixed", errors="coerce")
    nport = nport[nport["REPORT_DT"].notna()].copy()
    nport["REP_YQ"] = (nport["REPORT_DT"].dt.year * 10 + nport["REPORT_DT"].dt.quarter).astype(int)
    nport["FILE_YQ"] = (nport["FILE_QTR"].str[:4].astype(int) * 10 + nport["FILE_QTR"].str[-1].astype(int)).astype(int)
    nport["FYE_MONTH"] = nport["FYE_DT"].dt.month

    # Step 1 dedup: exact (SERIES_ID, REPORT_DT) amendment dedup (NPORT-P/A replaces NPORT-P)
    n_before_amend_dedup = len(nport)
    nport = nport.sort_values(["SERIES_ID", "REPORT_DT", "FILING_DT", "ACCESSION_NUMBER"]).drop_duplicates(
        ["SERIES_ID", "REPORT_DT"], keep="last"
    )
    n_amendments_replaced = n_before_amend_dedup - len(nport)

    # Step 2 dedup: collapse multiple reports within same (SERIES_ID, REP_YQ) keeping latest REPORT_DT, FILING_DT
    n_before_qtr_dedup = len(nport)
    nport = nport.sort_values(["SERIES_ID", "REP_YQ", "REPORT_DT", "FILING_DT", "ACCESSION_NUMBER"]).drop_duplicates(
        ["SERIES_ID", "REP_YQ"], keep="last"
    )
    n_within_qtr_dedup = n_before_qtr_dedup - len(nport)
    n_after_dedup = len(nport)

    # Merge time-invariant N-CEN metadata & unify COMPLEX_ID strictly at SERIES_ID level
    nport = nport.merge(ncen_meta, on="SERIES_ID", how="left")
    missing_cplx = nport["COMPLEX_ID"].isna()
    if missing_cplx.any():
        # Assign one time-invariant COMPLEX_ID per unmatched SERIES_ID using its modal/first registrant+CIK
        unm = (
            nport.loc[missing_cplx, ["SERIES_ID", "REGISTRANT_NAME", "CIK"]]
            .drop_duplicates("SERIES_ID", keep="first")
            .copy()
        )
        unm["FB_COMPLEX"] = [
            canonicalize_complex("", "", r, c)
            for r, c in zip(unm["REGISTRANT_NAME"].fillna(""), unm["CIK"].fillna(""), strict=False)
        ]
        fb_map = unm.set_index("SERIES_ID")["FB_COMPLEX"]
        nport.loc[missing_cplx, "COMPLEX_ID"] = nport.loc[missing_cplx, "SERIES_ID"].map(fb_map)

    # Assert strict nesting: every SERIES_ID belongs to EXACTLY ONE COMPLEX_ID!
    assert int(nport.groupby("SERIES_ID")["COMPLEX_ID"].nunique().max()) == 1, "SERIES_ID spans >1 COMPLEX_ID!"

    for flag in ["IS_ETF", "IS_INDEX", "IS_FOF", "IS_TARGET_DATE", "IS_MONEY_MARKET", "IS_FEEDER"]:
        nport[flag] = nport[flag].fillna(0).astype(int)

    # Drop money market funds (Rule 35d-1 does not apply to Rule 2a-7 MMFs in the same way; matches Wave-5)
    n_mmf_rows = int((nport["IS_MONEY_MARKET"] == 1).sum())
    nport = nport[nport["IS_MONEY_MARKET"] == 0].copy()

    # Deterministic Variable-Annuity / Insurance-Dedicated Trust flag (time-invariant per SERIES_ID)
    va_row = (
        nport["REGISTRANT_NAME"].fillna("").str.contains(RE_VA_TRUST)
        | nport["SERIES_NAME"].fillna("").str.contains(RE_VA_SERIES)
    )
    va_series = set(nport.loc[va_row, "SERIES_ID"])
    nport["IS_VA_INSURANCE"] = nport["SERIES_ID"].isin(va_series).astype(int)

    # Ensure Brighthouse CIK 0001126087 is cleanly attributed
    bh_cplx = nport.loc[nport["CIK"].str.lstrip("0") == "1126087", "COMPLEX_ID"].unique().tolist()
    print(f"  Brighthouse CIK 0001126087 COMPLEX_ID check: {bh_cplx}", flush=True)

    # -----------------------------------------------------------------------
    # [3/5] Regulated Name Term Classification, Lags & Bifurcated Taxonomy
    # -----------------------------------------------------------------------
    print("[3/5] Classifying regulated terms, lags, and bifurcated compliance taxonomy...", flush=True)
    # Sort chronologically first and repair obvious malformed non-alphabetic XML series-name glitches
    # (e.g., S000012125 filing phone number '303-626-0600' into SERIES_NAME in 2026Q1)
    nport = nport.sort_values(["SERIES_ID", "REP_YQ"]).reset_index(drop=True)
    raw_sn = nport["SERIES_NAME"].fillna("").str.strip()
    malformed_mask = (raw_sn == "") | (~raw_sn.str.contains(r"[A-Za-z]{2,}", regex=True))
    malformed_records = [
        {"SERIES_ID": str(r["SERIES_ID"]), "REP_YQ": int(r["REP_YQ"]), "RAW_SERIES_NAME": str(r["SERIES_NAME"])}
        for _, r in nport.loc[malformed_mask, ["SERIES_ID", "REP_YQ", "SERIES_NAME"]].iterrows()
    ]
    if malformed_mask.any():
        nport.loc[malformed_mask, "SERIES_NAME"] = np.nan
        nport["SERIES_NAME"] = nport.groupby("SERIES_ID")["SERIES_NAME"].ffill().bfill().fillna("")
    print(f"  Repaired {len(malformed_records)} malformed non-alphabetic XML SERIES_NAME rows.", flush=True)

    nm = nport["SERIES_NAME"].fillna("")
    nport["HAS_GV"] = nm.str.contains(RE_GV).astype(int)
    nport["HAS_GROWTH"] = nm.str.contains(RE_GROWTH).astype(int)
    nport["HAS_VALUE"] = nm.str.contains(RE_VALUE).astype(int)
    nport["HAS_INCOME"] = nm.str.contains(RE_INCOME).astype(int)
    nport["HAS_INCOME_DIV"] = nm.str.contains(RE_INCOME_DIV).astype(int)
    nport["HAS_GVI"] = ((nport["HAS_GV"] == 1) | (nport["HAS_INCOME"] == 1)).astype(int)
    nport["HAS_GVI_DIV"] = ((nport["HAS_GV"] == 1) | (nport["HAS_INCOME_DIV"] == 1)).astype(int)
    nport["HAS_ESG"] = nm.str.contains(RE_ESG).astype(int)
    nport["HAS_LEGACY"] = nm.str.contains(RE_LEGACY_2001).astype(int)

    has_alloc_nm = nm.str.contains(RE_ALLOC_NAME) & (~nm.str.contains(RE_FIXED_INCOME_BALANCED_RISK))
    nport["HAS_ALLOC_NM"] = has_alloc_nm.astype(int)
    nport["STRUCT_FOF_TD"] = ((nport["IS_FOF"] == 1) | (nport["IS_TARGET_DATE"] == 1)).astype(int)
    nport["IS_ALLOC_FUND"] = ((nport["HAS_ALLOC_NM"] == 1) | (nport["STRUCT_FOF_TD"] == 1)).astype(int)

    # Verify S000004397 (Vanguard Capital Growth Portfolio -> PRIMECAP Portfolio) is pure equity (NOT multi-asset!)
    s4397_alloc = int(nport.loc[nport["SERIES_ID"] == "S000004397", "IS_ALLOC_FUND"].max())
    assert s4397_alloc == 0, f"S000004397 must be pure equity (IS_ALLOC_FUND=0), got {s4397_alloc}"

    g = nport.groupby("SERIES_ID")

    # Compute exact gap in calendar quarters between consecutive filings for the same SERIES_ID
    q_idx = (nport["REP_YQ"] // 10) * 4 + (nport["REP_YQ"] % 10)
    nport["Q_IDX"] = q_idx
    nport["PREV_Q_IDX"] = g["Q_IDX"].shift(1)
    nport["Q_GAP"] = nport["Q_IDX"] - nport["PREV_Q_IDX"]

    lag_cols = [
        "SERIES_NAME",
        "HAS_GV",
        "HAS_GROWTH",
        "HAS_VALUE",
        "HAS_INCOME",
        "HAS_INCOME_DIV",
        "HAS_GVI",
        "HAS_GVI_DIV",
        "HAS_ESG",
        "HAS_LEGACY",
        "IS_ALLOC_FUND",
        "STRUCT_FOF_TD",
        "NET_ASSETS",
    ]
    for col in lag_cols:
        nport["PREV_" + col] = g[col].shift(1)

    norm_nm = nport["SERIES_NAME"].fillna("").str.upper().str.replace(r"[^A-Z0-9]+", " ", regex=True).str.strip()
    prev_norm_nm = (
        nport["PREV_SERIES_NAME"].fillna("").str.upper().str.replace(r"[^A-Z0-9]+", " ", regex=True).str.strip()
    )
    nport["ANY_RENAME"] = ((nport["PREV_SERIES_NAME"].notna()) & (norm_nm != prev_norm_nm)).astype(int)

    nport["DROP_GV"] = ((nport["PREV_HAS_GV"] == 1) & (nport["HAS_GV"] == 0)).astype(int)
    nport["DROP_GROWTH"] = ((nport["PREV_HAS_GROWTH"] == 1) & (nport["HAS_GROWTH"] == 0)).astype(int)
    nport["DROP_VALUE"] = ((nport["PREV_HAS_VALUE"] == 1) & (nport["HAS_VALUE"] == 0)).astype(int)
    nport["DROP_INCOME"] = ((nport["PREV_HAS_INCOME"] == 1) & (nport["HAS_INCOME"] == 0)).astype(int)
    # Strict regulated-term exit: DROP_GVI == 1 ONLY when ALL regulated G/V/I terms are stripped
    # (prevents false positives when a fund switches Income -> Value or Value -> Income!)
    nport["DROP_GVI"] = ((nport["PREV_HAS_GVI"] == 1) & (nport["HAS_GVI"] == 0)).astype(int)
    nport["DROP_GVI_DIV"] = ((nport["PREV_HAS_GVI_DIV"] == 1) & (nport["HAS_GVI_DIV"] == 0)).astype(int)
    nport["DROP_ESG"] = ((nport["PREV_HAS_ESG"] == 1) & (nport["HAS_ESG"] == 0)).astype(int)
    nport["DROP_LEGACY"] = ((nport["PREV_HAS_LEGACY"] == 1) & (nport["HAS_LEGACY"] == 0)).astype(int)

    # Classify compliance substitution type for EVERY GVI or GV drop
    comp_types = np.full(len(nport), "NONE", dtype=object)
    drop_mask = (nport["DROP_GVI"] == 1) | (nport["DROP_GVI_DIV"] == 1)
    for idx in nport.index[drop_mask]:
        comp_types[idx] = classify_compliance_type(
            str(nport.at[idx, "PREV_SERIES_NAME"] or ""),
            str(nport.at[idx, "SERIES_NAME"] or ""),
        )
    nport["COMPLIANCE_TYPE"] = comp_types
    nport["DROP_GVI_OPAQUE"] = ((nport["DROP_GVI"] == 1) & (nport["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM")).astype(int)
    nport["DROP_GVI_NUMERIC"] = ((nport["DROP_GVI"] == 1) & (nport["COMPLIANCE_TYPE"] == "NUMERIC_RATIO")).astype(int)
    nport["DROP_GVI_OTHER"] = ((nport["DROP_GVI"] == 1) & (nport["COMPLIANCE_TYPE"] == "OTHER_MERGER_BRAND")).astype(int)
    nport["DROP_GV_OPAQUE"] = ((nport["DROP_GV"] == 1) & (nport["COMPLIANCE_TYPE"] == "OPAQUE_SYNONYM")).astype(int)
    nport["DROP_GV_NUMERIC"] = ((nport["DROP_GV"] == 1) & (nport["COMPLIANCE_TYPE"] == "NUMERIC_RATIO")).astype(int)

    # -----------------------------------------------------------------------
    # [4/5] Fix Negative-Redemption Sign Bug & Cross-Validate Quarterly + Monthly Flows
    # -----------------------------------------------------------------------
    print("[4/5] Fixing abs(REDEMPTION) monthly & quarterly flows and cross-validating vs TNA-implied flow...", flush=True)
    for k in (1, 2, 3):
        s_col = f"SALES_FLOW_MON{k}"
        i_col = f"REINVESTMENT_FLOW_MON{k}"
        r_col = f"REDEMPTION_FLOW_MON{k}"
        # Both sales and reinvest can be NaN; if all three are NaN, net flow is NaN
        all_na = nport[s_col].isna() & nport[i_col].isna() & nport[r_col].isna()
        nf_fixed = nport[s_col].fillna(0.0) + nport[i_col].fillna(0.0) - nport[r_col].fillna(0.0).abs()
        nf_raw = nport[s_col].fillna(0.0) + nport[i_col].fillna(0.0) - nport[r_col].fillna(0.0)
        nport[f"NET_FLOW_FIXED_MON{k}"] = np.where(all_na, np.nan, nf_fixed)
        nport[f"NET_FLOW_RAW_MON{k}"] = np.where(all_na, np.nan, nf_raw)
        nport[f"REDEMP_ABS_MON{k}"] = nport[r_col].abs()

    q_all_na = (
        nport["NET_FLOW_FIXED_MON1"].isna()
        & nport["NET_FLOW_FIXED_MON2"].isna()
        & nport["NET_FLOW_FIXED_MON3"].isna()
    )
    nport["QTR_NET_FLOW_FIXED_USD"] = np.where(
        q_all_na,
        np.nan,
        nport["NET_FLOW_FIXED_MON1"].fillna(0.0)
        + nport["NET_FLOW_FIXED_MON2"].fillna(0.0)
        + nport["NET_FLOW_FIXED_MON3"].fillna(0.0),
    )
    nport["QTR_NET_FLOW_RAW_USD"] = np.where(
        q_all_na,
        np.nan,
        nport["NET_FLOW_RAW_MON1"].fillna(0.0)
        + nport["NET_FLOW_RAW_MON2"].fillna(0.0)
        + nport["NET_FLOW_RAW_MON3"].fillna(0.0),
    )
    nport["QTR_SALES_USD"] = np.where(
        q_all_na,
        np.nan,
        nport["SALES_FLOW_MON1"].fillna(0.0) + nport["SALES_FLOW_MON2"].fillna(0.0) + nport["SALES_FLOW_MON3"].fillna(0.0),
    )
    nport["QTR_REINVEST_USD"] = np.where(
        q_all_na,
        np.nan,
        nport["REINVESTMENT_FLOW_MON1"].fillna(0.0)
        + nport["REINVESTMENT_FLOW_MON2"].fillna(0.0)
        + nport["REINVESTMENT_FLOW_MON3"].fillna(0.0),
    )
    nport["QTR_REDEMP_ABS_USD"] = np.where(
        q_all_na,
        np.nan,
        nport["REDEMP_ABS_MON1"].fillna(0.0) + nport["REDEMP_ABS_MON2"].fillna(0.0) + nport["REDEMP_ABS_MON3"].fillna(0.0),
    )

    # Compound quarterly return from monthly total returns (in %)
    r1 = nport["MONTHLY_TOTAL_RETURN1"] / 100.0
    r2 = nport["MONTHLY_TOTAL_RETURN2"] / 100.0
    r3 = nport["MONTHLY_TOTAL_RETURN3"] / 100.0
    has_all_3r = r1.notna() & r2.notna() & r3.notna()
    nport["QTR_RET_PCT"] = np.where(
        has_all_3r,
        ((1.0 + r1) * (1.0 + r2) * (1.0 + r3) - 1.0) * 100.0,
        np.where(
            r1.notna() | r2.notna() | r3.notna(),
            ((1.0 + r1.fillna(0.0)) * (1.0 + r2.fillna(0.0)) * (1.0 + r3.fillna(0.0)) - 1.0) * 100.0,
            np.nan,
        ),
    )
    nport["QTR_VOL_PCT"] = nport[["MONTHLY_TOTAL_RETURN1", "MONTHLY_TOTAL_RETURN2", "MONTHLY_TOTAL_RETURN3"]].std(axis=1)
    nport["CASH_PCT"] = np.where(
        nport["TOTAL_ASSETS"] > 1e6,
        100.0 * nport["CASH_NOT_RPTD_IN_C_OR_D"].fillna(0.0) / nport["TOTAL_ASSETS"],
        np.nan,
    )
    nport["LEVERAGE_PCT"] = np.where(
        nport["NET_ASSETS"] > 1e6,
        100.0 * (nport["TOTAL_ASSETS"] / nport["NET_ASSETS"] - 1.0),
        np.nan,
    )

    # Quarterly percentage flows (require consecutive quarter Q_GAP == 1 & PREV_NET_ASSETS > $1M)
    valid_base = (nport["Q_GAP"] == 1) & (nport["PREV_NET_ASSETS"] > 1e6)
    nport["QTR_FLOW_FIXED_PCT"] = np.where(valid_base, 100.0 * nport["QTR_NET_FLOW_FIXED_USD"] / nport["PREV_NET_ASSETS"], np.nan)
    nport["QTR_FLOW_RAW_PCT"] = np.where(valid_base, 100.0 * nport["QTR_NET_FLOW_RAW_USD"] / nport["PREV_NET_ASSETS"], np.nan)
    nport["QTR_SALES_PCT"] = np.where(valid_base, 100.0 * nport["QTR_SALES_USD"] / nport["PREV_NET_ASSETS"], np.nan)
    nport["QTR_REDEMP_ABS_PCT"] = np.where(valid_base, 100.0 * nport["QTR_REDEMP_ABS_USD"] / nport["PREV_NET_ASSETS"], np.nan)
    nport["QTR_FLOW_TNA_PCT"] = np.where(
        valid_base & nport["NET_ASSETS"].notna() & nport["QTR_RET_PCT"].notna(),
        100.0 * (nport["NET_ASSETS"] - nport["PREV_NET_ASSETS"] * (1.0 + nport["QTR_RET_PCT"] / 100.0)) / nport["PREV_NET_ASSETS"],
        np.nan,
    )

    # Cross-validation correlation jump (raw vs abs(REDEMPTION)) against TNA-implied flow
    cv_df = nport[
        (nport["REP_YQ"] >= 20201)
        & nport["QTR_FLOW_FIXED_PCT"].notna()
        & nport["QTR_FLOW_RAW_PCT"].notna()
        & nport["QTR_FLOW_TNA_PCT"].notna()
        & (nport["QTR_FLOW_TNA_PCT"].abs() <= 100.0)
        & (nport["QTR_FLOW_FIXED_PCT"].abs() <= 100.0)
    ].copy()
    # Clip extreme raw outliers to [-500, 500] only for Pearson comparability, and also compute unclipped Spearman
    raw_clip = cv_df["QTR_FLOW_RAW_PCT"].clip(-100.0, 100.0)
    pearson_raw = float(stats.pearsonr(raw_clip, cv_df["QTR_FLOW_TNA_PCT"])[0])
    pearson_raw_unclipped = float(stats.pearsonr(cv_df["QTR_FLOW_RAW_PCT"], cv_df["QTR_FLOW_TNA_PCT"])[0])
    spearman_raw = float(stats.spearmanr(cv_df["QTR_FLOW_RAW_PCT"], cv_df["QTR_FLOW_TNA_PCT"])[0])
    pearson_fixed = float(stats.pearsonr(cv_df["QTR_FLOW_FIXED_PCT"], cv_df["QTR_FLOW_TNA_PCT"])[0])
    spearman_fixed = float(stats.spearmanr(cv_df["QTR_FLOW_FIXED_PCT"], cv_df["QTR_FLOW_TNA_PCT"])[0])

    # Also evaluate strictly on the subset where at least one month had negative redemption!
    neg_sub = cv_df[
        (cv_df["REDEMPTION_FLOW_MON1"] < 0)
        | (cv_df["REDEMPTION_FLOW_MON2"] < 0)
        | (cv_df["REDEMPTION_FLOW_MON3"] < 0)
    ]
    pearson_neg_raw = float(stats.pearsonr(neg_sub["QTR_FLOW_RAW_PCT"].clip(-100.0, 100.0), neg_sub["QTR_FLOW_TNA_PCT"])[0])
    pearson_neg_fixed = float(stats.pearsonr(neg_sub["QTR_FLOW_FIXED_PCT"], neg_sub["QTR_FLOW_TNA_PCT"])[0])

    flow_validation = {
        "n_valid_qtr_obs": len(cv_df),
        "pearson_raw_unclipped_vs_tna": pearson_raw_unclipped,
        "pearson_raw_clipped100_vs_tna": pearson_raw,
        "spearman_raw_vs_tna": spearman_raw,
        "pearson_fixed_abs_vs_tna": pearson_fixed,
        "spearman_fixed_abs_vs_tna": spearman_fixed,
        "n_neg_redemption_obs": len(neg_sub),
        "neg_subset_pearson_raw_vs_tna": pearson_neg_raw,
        "neg_subset_pearson_fixed_vs_tna": pearson_neg_fixed,
    }
    print(
        f"  Flow sign-fix validation (N={len(cv_df):,}): "
        f"Raw unclipped r={pearson_raw_unclipped:.4f} (clipped100 r={pearson_raw:.4f}, Spearman={spearman_raw:.4f}) -> "
        f"Fixed abs(REDEMP) Pearson r={pearson_fixed:.4f}, Spearman={spearman_fixed:.4f} "
        f"(Neg-sign subset: raw r={pearson_neg_raw:.4f} -> fixed r={pearson_neg_fixed:.4f})",
        flush=True,
    )

    # Pre-rule Complex & CIK TNA snapshots at REP_YQ = 2023Q2 and 2024Q4, plus active-in-2024+ complex flag
    for tag, rq in [("23Q2", 20232), ("24Q4", 20244)]:
        s_rq = nport[nport["REP_YQ"] == rq]
        ct = s_rq.groupby("COMPLEX_ID")["NET_ASSETS"].sum()
        kt = s_rq.groupby("CIK")["NET_ASSETS"].sum()
        nport[f"COMPLEX_TNA_{tag}"] = nport["COMPLEX_ID"].map(ct)
        nport[f"CIK_TNA_{tag}"] = nport["CIK"].map(kt)
        nport[f"LARGE_COMPLEX_{tag}"] = np.where(
            nport[f"COMPLEX_TNA_{tag}"].notna(),
            (nport[f"COMPLEX_TNA_{tag}"] >= 1e9).astype(float),
            np.nan,
        )
        nport[f"LARGE_CIK_{tag}"] = np.where(
            nport[f"CIK_TNA_{tag}"].notna(),
            (nport[f"CIK_TNA_{tag}"] >= 1e9).astype(float),
            np.nan,
        )

    # Complex active in 2024+ (identifies complexes that did NOT exit before 2024)
    cplx_max_yq = nport.groupby("COMPLEX_ID")["REP_YQ"].transform("max")
    nport["COMPLEX_ACTIVE_2024PLUS"] = (cplx_max_yq >= 20241).astype(int)

    # Lagged return & size controls
    nport["LAG_QTR_RET_PCT"] = nport.groupby("SERIES_ID")["QTR_RET_PCT"].shift(1)
    nport["LOG_LAG_TNA"] = np.log(nport["PREV_NET_ASSETS"].clip(lower=1e6))
    nport["IS_COMPLETE_QTR"] = ((nport["REP_YQ"] >= 20201) & (nport["REP_YQ"] <= 20262)).astype(int)

    # Exit flag (last filing <= 2026Q1 or explicit IS_LAST_FILING == 'Y')
    last_yq_series = nport.groupby("SERIES_ID")["REP_YQ"].transform("max")
    nport["IS_EXIT"] = (((nport["REP_YQ"] == last_yq_series) & (nport["REP_YQ"] <= 20261)) | (nport["IS_LAST_FILING"] == "Y")).astype(int)

    # Save quarterly panel (keep 2020Q1-2026Q3 with valid lag; also keep 2019Q4+ in memory for monthly panel)
    qtr_panel = nport[(nport["REP_YQ"] >= 20201) & (nport["REP_YQ"] <= 20263) & (nport["PREV_SERIES_NAME"].notna())].copy()
    qtr_out = DATA_OUT / "panel_quarterly.parquet"
    qtr_panel.to_parquet(qtr_out, index=False)
    print(f"  Saved {qtr_out.name}: {len(qtr_panel):,} rows, {qtr_panel['SERIES_ID'].nunique():,} unique funds, {qtr_panel['COMPLEX_ID'].nunique():,} complexes.", flush=True)

    # -----------------------------------------------------------------------
    # [5/5] Build Exact Monthly Panel (2020-01 through 2026-09) & Dropper Audit CSV
    # -----------------------------------------------------------------------
    print("[5/5] Building exact monthly panel (2020-01..2026-09) and exporting 2025-2026 dropper audit CSV...", flush=True)
    # Chronological mapping verified empirically via March 2020 COVID crash:
    # MON3 = report month M; MON2 = M - 1; MON1 = M - 2.
    # Predetermined beginning-of-month TNA from PREV_NET_ASSETS (when Q_GAP == 1):
    #   TNA_beg_1 = PREV_NET_ASSETS
    #   TNA_beg_2 = TNA_beg_1 * (1 + r1) + nf1
    #   TNA_beg_3 = TNA_beg_2 * (1 + r2) + nf2
    m_base = nport[(nport["REP_YQ"] >= 20201) & (nport["REP_YQ"] <= 20263)].copy()
    m_base["REP_PER"] = m_base["REPORT_DT"].dt.to_period("M")

    tna0 = np.where((m_base["Q_GAP"] == 1) & (m_base["PREV_NET_ASSETS"] > 1e6), m_base["PREV_NET_ASSETS"], np.nan)
    r1_v = m_base["MONTHLY_TOTAL_RETURN1"].to_numpy(dtype=float) / 100.0
    r2_v = m_base["MONTHLY_TOTAL_RETURN2"].to_numpy(dtype=float) / 100.0
    r3_v = m_base["MONTHLY_TOTAL_RETURN3"].to_numpy(dtype=float) / 100.0
    nf1_v = m_base["NET_FLOW_FIXED_MON1"].to_numpy(dtype=float)
    nf2_v = m_base["NET_FLOW_FIXED_MON2"].to_numpy(dtype=float)
    nf3_v = m_base["NET_FLOW_FIXED_MON3"].to_numpy(dtype=float)

    tna_beg_1 = tna0
    tna_beg_2 = np.where(np.isfinite(tna_beg_1) & np.isfinite(r1_v) & np.isfinite(nf1_v), tna_beg_1 * (1.0 + r1_v) + nf1_v, np.nan)
    tna_beg_3 = np.where(np.isfinite(tna_beg_2) & np.isfinite(r2_v) & np.isfinite(nf2_v), tna_beg_2 * (1.0 + r2_v) + nf2_v, np.nan)
    # Fallback when prior quarter is unavailable: back out TNA_beg from report-date NET_ASSETS (clip > $1M)
    tna_end = np.where(m_base["NET_ASSETS"] > 1e6, m_base["NET_ASSETS"], np.nan)
    fb_beg_3 = np.where(np.isfinite(tna_end) & np.isfinite(r3_v) & np.isfinite(nf3_v) & ((1.0 + r3_v) > 0.2), (tna_end - nf3_v) / (1.0 + r3_v), np.nan)
    fb_beg_2 = np.where(np.isfinite(fb_beg_3) & np.isfinite(r2_v) & np.isfinite(nf2_v) & ((1.0 + r2_v) > 0.2), (fb_beg_3 - nf2_v) / (1.0 + r2_v), np.nan)
    fb_beg_1 = np.where(np.isfinite(fb_beg_2) & np.isfinite(r1_v) & np.isfinite(nf1_v) & ((1.0 + r1_v) > 0.2), (fb_beg_2 - nf1_v) / (1.0 + r1_v), np.nan)

    tna_beg_arr = {
        1: np.where(np.isfinite(tna_beg_1) & (tna_beg_1 > 1e6), tna_beg_1, np.where(fb_beg_1 > 1e6, fb_beg_1, np.nan)),
        2: np.where(np.isfinite(tna_beg_2) & (tna_beg_2 > 1e6), tna_beg_2, np.where(fb_beg_2 > 1e6, fb_beg_2, np.nan)),
        3: np.where(np.isfinite(tna_beg_3) & (tna_beg_3 > 1e6), tna_beg_3, np.where(fb_beg_3 > 1e6, fb_beg_3, np.nan)),
    }

    mon_frames = []
    for k, offset in [(1, -2), (2, -1), (3, 0)]:
        tb = tna_beg_arr[k]
        per = m_base["REP_PER"] + offset
        ym = per.dt.year * 100 + per.dt.month
        sales = m_base[f"SALES_FLOW_MON{k}"].to_numpy(dtype=float)
        reinv = m_base[f"REINVESTMENT_FLOW_MON{k}"].to_numpy(dtype=float)
        red_abs = m_base[f"REDEMP_ABS_MON{k}"].to_numpy(dtype=float)
        nf_fix = m_base[f"NET_FLOW_FIXED_MON{k}"].to_numpy(dtype=float)
        nf_raw = m_base[f"NET_FLOW_RAW_MON{k}"].to_numpy(dtype=float)
        ret_m = m_base[f"MONTHLY_TOTAL_RETURN{k}"].to_numpy(dtype=float)
        ok = np.isfinite(tb) & (tb > 1e6)
        mon_frames.append(
            pd.DataFrame(
                {
                    "SERIES_ID": m_base["SERIES_ID"].to_numpy(),
                    "COMPLEX_ID": m_base["COMPLEX_ID"].to_numpy(),
                    "YM": ym.to_numpy(dtype=int),
                    "REP_YQ": m_base["REP_YQ"].to_numpy(dtype=int),
                    "FILING_DT": m_base["FILING_DT"].to_numpy(),
                    "TNA_BEG": tb,
                    "RET_M_PCT": ret_m,
                    "NET_FLOW_FIXED_USD": nf_fix,
                    "NET_FLOW_RAW_USD": nf_raw,
                    "SALES_USD": sales,
                    "REINVEST_USD": reinv,
                    "REDEMP_ABS_USD": red_abs,
                    "NET_FLOW_PCT": np.where(ok, 100.0 * nf_fix / tb, np.nan),
                    "NET_FLOW_RAW_PCT": np.where(ok, 100.0 * nf_raw / tb, np.nan),
                    "SALES_PCT": np.where(ok, 100.0 * sales / tb, np.nan),
                    "REINVEST_PCT": np.where(ok, 100.0 * reinv / tb, np.nan),
                    "REDEMP_ABS_PCT": np.where(ok, 100.0 * red_abs / tb, np.nan),
                    "IS_ETF": m_base["IS_ETF"].to_numpy(dtype=int),
                    "IS_INDEX": m_base["IS_INDEX"].to_numpy(dtype=int),
                    "IS_FOF": m_base["IS_FOF"].to_numpy(dtype=int),
                    "IS_VA_INSURANCE": m_base["IS_VA_INSURANCE"].to_numpy(dtype=int),
                }
            )
        )

    monthly = pd.concat(mon_frames, ignore_index=True)
    monthly = monthly[(monthly["YM"] >= 202001) & (monthly["YM"] <= 202609)].copy()
    monthly = monthly.sort_values(["SERIES_ID", "YM", "FILING_DT"]).drop_duplicates(["SERIES_ID", "YM"], keep="last")
    monthly = monthly.sort_values(["SERIES_ID", "YM"]).reset_index(drop=True)

    # Compute lagged 3-month and 12-month compounded returns per SERIES_ID with consecutive-month guard
    m_ret_fac = 1.0 + monthly["RET_M_PCT"].clip(-90.0, 200.0) / 100.0
    monthly["RET_FAC"] = m_ret_fac
    monthly["YM_IDX"] = (monthly["YM"] // 100) * 12 + (monthly["YM"] % 100)
    mg = monthly.groupby("SERIES_ID")
    gap1 = monthly["YM_IDX"] - mg["YM_IDX"].shift(1)
    gap3 = monthly["YM_IDX"] - mg["YM_IDX"].shift(3)
    gap12 = monthly["YM_IDX"] - mg["YM_IDX"].shift(12)
    # Lagged 1m, 3m, 12m cumulative returns (purely lagged & consecutive-calendar guarded!)
    monthly["LAG1_RET_PCT"] = np.where(gap1 == 1, mg["RET_M_PCT"].shift(1), np.nan)
    log_rf = np.log(monthly["RET_FAC"].clip(lower=0.05))
    monthly["LOG_RF"] = log_rf
    raw_lag3 = (
        np.exp(monthly.groupby("SERIES_ID")["LOG_RF"].transform(lambda s: s.shift(1).rolling(3, min_periods=2).sum())) - 1.0
    ) * 100.0
    raw_lag12 = (
        np.exp(monthly.groupby("SERIES_ID")["LOG_RF"].transform(lambda s: s.shift(1).rolling(12, min_periods=6).sum())) - 1.0
    ) * 100.0
    monthly["LAG3M_RET_PCT"] = np.where((gap1 == 1) & (gap3.isna() | (gap3 <= 4)), raw_lag3, np.nan)
    monthly["LAG12M_RET_PCT"] = np.where((gap1 == 1) & (gap12.isna() | (gap12 <= 14)), raw_lag12, np.nan)
    monthly["LOG_TNA_BEG"] = np.log(monthly["TNA_BEG"].clip(lower=1e6))
    monthly = monthly.drop(columns=["RET_FAC", "LOG_RF", "YM_IDX"])

    mon_out = DATA_OUT / "panel_monthly.parquet"
    monthly.to_parquet(mon_out, index=False)
    print(f"  Saved {mon_out.name}: {len(monthly):,} fund-months ({monthly['YM'].min()}..{monthly['YM'].max()}), {monthly['SERIES_ID'].nunique():,} funds.", flush=True)

    # Export complete auditable 2025Q1-2026Q3 dropper table (ALL Multi-Asset GVI + ALL ESG + ALL Pure-Equity GVI)
    d25 = qtr_panel[(qtr_panel["REP_YQ"] >= 20251) & ((qtr_panel["DROP_GVI"] == 1) | (qtr_panel["DROP_ESG"] == 1))].copy()
    d25["DROP_GROUP"] = np.where(
        (d25["DROP_GVI"] == 1) & (d25["PREV_IS_ALLOC_FUND"] == 1),
        "MULTI_ASSET_GVI",
        np.where(d25["DROP_ESG"] == 1, "ESG", "PURE_EQUITY_OR_BOND_GVI"),
    )
    # Also flag dual drops (both GVI & ESG) cleanly
    d25["IS_DUAL_GVI_ESG"] = ((d25["DROP_GVI"] == 1) & (d25["DROP_ESG"] == 1)).astype(int)
    d25["AUM_M"] = (d25["PREV_NET_ASSETS"] / 1e6).round(2)

    audit_cols = [
        "SERIES_ID",
        "CIK",
        "COMPLEX_ID",
        "REGISTRANT_NAME",
        "DROP_GROUP",
        "DROP_GV",
        "DROP_GVI",
        "DROP_ESG",
        "IS_DUAL_GVI_ESG",
        "COMPLIANCE_TYPE",
        "PREV_SERIES_NAME",
        "SERIES_NAME",
        "REP_YQ",
        "REPORT_DATE",
        "FILE_YQ",
        "FILING_DATE",
        "AUM_M",
        "PREV_IS_ALLOC_FUND",
        "IS_FOF",
        "IS_TARGET_DATE",
        "IS_INDEX",
        "IS_ETF",
        "IS_VA_INSURANCE",
    ]
    audit_df = (
        d25[audit_cols]
        .rename(columns={"PREV_SERIES_NAME": "OLD_NAME", "SERIES_NAME": "NEW_NAME"})
        .sort_values(["DROP_GROUP", "AUM_M"], ascending=[True, False])
        .reset_index(drop=True)
    )
    audit_csv = TABLES_OUT / "table_all_droppers_2025_2026_audit.csv"
    audit_df.to_csv(audit_csv, index=False, lineterminator="\n")

    # Compute exact bifurcated equilibrium breakdown on Multi-Asset GVI droppers (2025Q1-2026Q3)
    ma_drops = audit_df[audit_df["DROP_GROUP"] == "MULTI_ASSET_GVI"].drop_duplicates("SERIES_ID")
    esg_drops = audit_df[audit_df["DROP_ESG"] == 1].drop_duplicates("SERIES_ID")
    pure_drops = audit_df[audit_df["DROP_GROUP"] == "PURE_EQUITY_OR_BOND_GVI"].drop_duplicates("SERIES_ID")
    pure_excl_esg = pure_drops[~pure_drops["SERIES_ID"].isin(set(esg_drops["SERIES_ID"]))]
    all_gvi_drops = audit_df[audit_df["DROP_GVI"] == 1].drop_duplicates("SERIES_ID")
    all_any_drops = audit_df.drop_duplicates("SERIES_ID")
    n_seq_esg_then_gvi = len(set(esg_drops["SERIES_ID"]) & set(pure_drops["SERIES_ID"]))

    bifurc = {}
    tot_ma_n = len(ma_drops)
    tot_ma_aum = float(ma_drops["AUM_M"].sum() / 1e3)
    for ct in ["OPAQUE_SYNONYM", "NUMERIC_RATIO", "OTHER_MERGER_BRAND"]:
        sub_c = ma_drops[ma_drops["COMPLIANCE_TYPE"] == ct]
        aum_b = float(sub_c["AUM_M"].sum() / 1e3)
        bifurc[ct] = {
            "n_funds": len(sub_c),
            "pct_funds": float(100.0 * len(sub_c) / max(tot_ma_n, 1)),
            "aum_B": aum_b,
            "pct_aum": float(100.0 * aum_b / max(tot_ma_aum, 1e-9)),
            "n_complexes": int(sub_c["COMPLEX_ID"].nunique()),
            "pct_index": float(100.0 * sub_c["IS_INDEX"].mean()) if len(sub_c) else 0.0,
            "pct_etf": float(100.0 * sub_c["IS_ETF"].mean()) if len(sub_c) else 0.0,
            "pct_va_insurance": float(100.0 * sub_c["IS_VA_INSURANCE"].mean()) if len(sub_c) else 0.0,
            "pct_fof": float(100.0 * sub_c["IS_FOF"].mean()) if len(sub_c) else 0.0,
        }

    # Verify major complex unification
    major_check = {}
    for target in [
        "VANGUARD",
        "FIDELITY",
        "PRUDENTIAL / PGIM",
        "BRIGHTHOUSE",
        "BLACKROCK / ISHARES",
        "CAPITAL GROUP / AMERICAN FUNDS",
        "GOLDMAN SACHS",
        "STATE STREET / SSGA",
        "WISDOMTREE",
        "ADVISORS PREFERRED / QUANTIFIED",
    ]:
        sub_t = qtr_panel[qtr_panel["COMPLEX_ID"] == target]
        major_check[target] = {
            "n_series": int(sub_t["SERIES_ID"].nunique()),
            "n_ciks": int(sub_t["CIK"].nunique()),
            "tna_23Q2_B": float(sub_t.loc[sub_t["REP_YQ"] == 20232, "NET_ASSETS"].sum() / 1e9),
        }

    rep_yq_counts = {int(k): int(v) for k, v in qtr_panel["REP_YQ"].value_counts().sort_index().items()}

    summary = {
        "nport_dedup_audit": {
            "n_raw_total_all_rows": int(n_total_raw_all),
            "n_excluded_cef_sentinel_S000000000": int(n_cef_sentinel),
            "n_excluded_blank_series_id": int(n_blank_sid),
            "n_raw_valid_series_id": int(n_raw_valid_sid),
            "n_sub_type_NPORT_P": int(n_sub_orig),
            "n_sub_type_NPORT_PA_amendments": int(n_sub_amend),
            "n_amendments_replaced_same_report_dt": int(n_amendments_replaced),
            "n_within_qtr_multi_report_dedup": int(n_within_qtr_dedup),
            "n_unique_series_rep_yq_pre_mmf": int(n_after_dedup),
            "n_excluded_money_market_rows": int(n_mmf_rows),
            "n_final_quarterly_panel_2020Q1_2026Q3": len(qtr_panel),
            "n_final_quarterly_complete_2020Q1_2026Q2": int((qtr_panel["IS_COMPLETE_QTR"] == 1).sum()),
            "n_final_unique_series": int(qtr_panel["SERIES_ID"].nunique()),
            "n_final_unique_complexes": int(qtr_panel["COMPLEX_ID"].nunique()),
            "total_latest_aum_T": float(qtr_panel.groupby("SERIES_ID")["NET_ASSETS"].last().sum() / 1e12),
            "rep_yq_counts": rep_yq_counts,
        },
        "ncen_stats": ncen_stats,
        "negative_redemption_audit": neg_red_audit,
        "flow_sign_fix_validation": flow_validation,
        "monthly_panel_stats": {
            "n_fund_months": len(monthly),
            "n_unique_series": int(monthly["SERIES_ID"].nunique()),
            "min_ym": int(monthly["YM"].min()),
            "max_ym": int(monthly["YM"].max()),
        },
        "economic_scale_2025Q1_2026Q3_rep_yq": {
            "MULTI_ASSET_GVI": {
                "n_funds": len(ma_drops),
                "aum_B": float(ma_drops["AUM_M"].sum() / 1e3),
                "n_complexes": int(ma_drops["COMPLEX_ID"].nunique()),
            },
            "ALL_GVI": {
                "n_funds": len(all_gvi_drops),
                "aum_B": float(all_gvi_drops["AUM_M"].sum() / 1e3),
                "n_complexes": int(all_gvi_drops["COMPLEX_ID"].nunique()),
            },
            "ESG": {
                "n_funds": len(esg_drops),
                "aum_B": float(esg_drops["AUM_M"].sum() / 1e3),
                "n_complexes": int(esg_drops["COMPLEX_ID"].nunique()),
            },
            "PURE_EQUITY_OR_BOND_GVI": {
                "n_funds": len(pure_drops),
                "aum_B": float(pure_drops["AUM_M"].sum() / 1e3),
                "n_complexes": int(pure_drops["COMPLEX_ID"].nunique()),
                "n_funds_excl_sequential_esg_dropper": len(pure_excl_esg),
                "aum_B_excl_sequential_esg_dropper": float(pure_excl_esg["AUM_M"].sum() / 1e3),
                "n_sequential_esg_then_pure_gvi": n_seq_esg_then_gvi,
            },
            "ANY_RULE35D1_GVI_OR_ESG": {
                "n_funds": len(all_any_drops),
                "aum_B": float(all_any_drops["AUM_M"].sum() / 1e3),
                "n_complexes": int(all_any_drops["COMPLEX_ID"].nunique()),
            },
        },
        "bifurcated_equilibrium_multi_asset_gvi": bifurc,
        "major_complex_unification_check": major_check,
        "individual_fixes_verified": {
            "S000004397_vanguard_capital_growth_is_alloc": int(s4397_alloc),
            "CIK_0001126087_brighthouse_complex_id": bh_cplx,
            "n_malformed_xml_series_names_repaired": len(malformed_records),
            "malformed_xml_series_names_repaired": malformed_records,
        },
    }

    res_path = RESULTS_OUT / "01_panel_audit.json"
    res_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8", newline="\n")

    print("\n=== PILLAR 1 SUMMARY ===", flush=True)
    print(f"  Quarterly panel (2020Q1-2026Q3): {len(qtr_panel):,} obs | Complete (2020Q1-2026Q2): {(qtr_panel['IS_COMPLETE_QTR']==1).sum():,} obs", flush=True)
    print(f"  Amendments replaced: {n_amendments_replaced:,} | CEF S000000000 excluded: {n_cef_sentinel:,}", flush=True)
    print(f"  2025Q1-2026Q3 Any GVI/ESG Droppers: {len(all_any_drops)} funds, ${all_any_drops['AUM_M'].sum()/1e3:.2f}B across {all_any_drops['COMPLEX_ID'].nunique()} complexes", flush=True)
    print(f"  Multi-Asset GVI Droppers: {tot_ma_n} funds, ${tot_ma_aum:.2f}B across {ma_drops['COMPLEX_ID'].nunique()} complexes", flush=True)
    for ct, d in bifurc.items():
        print(
            f"    - {ct:18s}: {d['n_funds']:2d} funds ({d['pct_funds']:5.1f}%), "
            f"${d['aum_B']:6.2f}B ({d['pct_aum']:5.1f}% AUM) | Index={d['pct_index']:.1f}%, ETF={d['pct_etf']:.1f}%, VA={d['pct_va_insurance']:.1f}%",
            flush=True,
        )
    print(f"  Saved {res_path.name} and {audit_csv.name}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
