"""Build clean, auditable trial-level analytic panel from ClinicalTrials.gov v2 raw pages.

Exports:
  - data/processed/d30_all_trials.parquet (all parsed Phase 2/3 randomized industry trials)
  - data/processed/d30_mrct_placebo_panel.parquet (core placebo-controlled MRCT analytic panel)
  - data/processed/d30_mrct_placebo_panel.csv
  - data/processed/panel_build_summary.json
"""
from __future__ import annotations

import gzip
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(r"D:\AI_Science\antigravity\d30_boost_clinical_trials_20261125")
RAW_DIR = BASE_DIR / "data" / "raw_ctgov"
PROC_DIR = BASE_DIR / "data" / "processed"
PROC_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Mutually exclusive, collectively exhaustive country-to-region mappings
# ---------------------------------------------------------------------------
# Puerto Rico is a U.S. territory under direct U.S. FDA regulatory jurisdiction
US_SET = {"United States", "Puerto Rico"}

WE_EU_SET = {
    "United Kingdom", "Germany", "France", "Italy", "Spain", "Netherlands",
    "Belgium", "Switzerland", "Sweden", "Norway", "Denmark", "Finland",
    "Austria", "Ireland", "Portugal", "Greece", "Iceland", "Luxembourg",
    "Malta", "Cyprus",
}
DEV_APAC_CA_SET = {
    "Canada", "Australia", "New Zealand", "Israel", "Japan", "South Korea",
    "Republic of Korea", "Korea, Republic of", "Singapore",
}
WE_DEV_SET = WE_EU_SET | DEV_APAC_CA_SET

EU_EAST_SET = {
    "Poland", "Hungary", "Czechia", "Czech Republic", "Romania", "Bulgaria",
    "Slovakia", "Croatia", "Lithuania", "Latvia", "Estonia", "Slovenia",
}
RU_UA_ONLY_SET = {"Russia", "Russian Federation", "Ukraine"}
NONEU_EE_OTHER_SET = {
    "Serbia", "Serbia and Montenegro", "Georgia", "Belarus", "Bosnia and Herzegovina",
    "Moldova", "Moldova, Republic of", "North Macedonia", "Macedonia",
    "The Former Yugoslav Republic of Macedonia", "Montenegro", "Albania",
    "Armenia", "Kazakhstan", "Azerbaijan",
}
RU_UA_ALL_SET = RU_UA_ONLY_SET | NONEU_EE_OTHER_SET
EAST_ALL_SET = EU_EAST_SET | RU_UA_ALL_SET

LATAM_SET = {
    "Brazil", "Mexico", "Argentina", "Colombia", "Chile", "Peru",
    "Costa Rica", "Guatemala", "Ecuador", "Panama", "Uruguay",
    "Dominican Republic", "El Salvador", "Paraguay", "Venezuela",
    "Bolivia", "Honduras", "Nicaragua",
}
ASIA_EMERG_SET = {
    "China", "India", "Thailand", "Philippines", "Malaysia", "Vietnam",
    "Indonesia", "Taiwan", "Hong Kong", "Pakistan", "Bangladesh", "Sri Lanka",
}

# Subjective symptom-oriented vs objective lab/organ MedDRA System Organ Classes (case-folded).
# Note: ClinicalTrials.gov v2 abbreviates "General disorders and administration site conditions"
# as "General disorders" (90,190 terms vs 847 full-name terms); both spellings are included.
SUBJECTIVE_SOCS = {
    "nervous system disorders",
    "gastrointestinal disorders",
    "general disorders",
    "general disorders and administration site conditions",
    "psychiatric disorders",
    "musculoskeletal and connective tissue disorders",
    "skin and subcutaneous tissue disorders",
    "respiratory, thoracic and mediastinal disorders",
    "ear and labyrinth disorders",
    "eye disorders",
}
OBJECTIVE_SOCS = {
    "investigations",
    "blood and lymphatic system disorders",
    "metabolism and nutrition disorders",
    "cardiac disorders",
    "vascular disorders",
    "renal and urinary disorders",
    "hepatobiliary disorders",
    "infections and infestations",
}

# Generic/artifact NLM MeSH auto-tagger terms that must never be adopted as a molecule name
MESH_ARTIFACT_EXCLUSIONS = {
    "bid protein human", "bid protein, human", "salicylhydroxamic acid",
    "double-blind method", "double blind method", "blood specimen collection",
    "drug therapy", "therapeutics", "radiotherapy", "solutions",
    "ophthalmic solutions", "pharmaceutical solutions", "adrenal cortex hormones",
    "sulfonylurea compounds", "vaccines", "placebos", "antibodies monoclonal",
    "antibodies, monoclonal", "calcineurin inhibitors", "hormones",
    "biological products", "anti-inflammatory agents", "analgesics",
    "immunologic factors", "antineoplastic agents", "hypoglycemic agents",
    "saline", "saline solution", "sodium chloride", "water",
}

CODE_MOL_RE = re.compile(
    r"^(?:[a-z]{1,5}[\s\-_]?\d{3,}[a-z0-9\-\s]*|\d{3,}[a-z\-]*)$",
    flags=re.IGNORECASE,
)

# Non-drug period/phase/arm descriptors allowed adjacent to a dash next to "placebo"
NON_DRUG_ARM_WORDS = {
    "treatment", "randomization", "randomized", "period", "phase", "part",
    "cohort", "group", "arm", "acute", "maintenance", "induction", "initial",
    "double", "blind", "blinded", "core", "entire", "safety", "follow",
    "followup", "post", "pre", "oral", "subcutaneous", "intravenous",
    "matched", "matching", "placebo", "controlled", "control", "responder",
    "responders", "non", "naive", "week", "weeks", "wk", "wks", "day", "days",
    "month", "months", "low", "high", "medium", "qd", "bid", "tid", "qw",
    "q2w", "q4w", "open", "label", "extension", "parent", "saber", "vehicle",
    "sham", "standard", "background", "overall", "total", "all", "main",
    "primary", "secondary", "study", "trial", "run", "lead", "washout",
    "titration", "stabilization", "consolidation", "db", "ole", "lte", "set",
    "population", "adults", "adolescents", "pediatric", "children", "patients",
    "subjects", "daily", "weekly", "monthly", "once", "twice", "dose",
    "dosing", "regimen", "only", "alone", "pbo", "active", "placebos",
    "placebo-controlled", "parallel", "single", "multi", "center", "part1",
    "part2", "group1", "group2", "cohort1", "cohort2", "arm1", "arm2",
    "stage", "epoch", "cycle", "visit", "short", "long", "term", "fixed",
    "flexible", "experienced", "stratum", "strata", "substudy",
}

# Non-investigational terms to exclude from primary molecule identification
PLACEBO_EXCLUSION_TERMS = {
    "placebo", "matching placebo", "saline", "normal saline", "sodium chloride",
    "vehicle", "sham", "water", "sterile water", "standard of care", "soc",
    "best supportive care", "no intervention", "observation", "rescue medication",
    "background therapy", "dextrose", "diluent", "dummy", "control",
}

# Common background/backbone agents down-weighted when co-present with an investigational drug
BACKBONE_AGENTS = {
    "metformin", "methotrexate", "dexamethasone", "prednisone", "prednisolone",
    "methylprednisolone", "aspirin", "acetylsalicylic acid", "acetaminophen",
    "paracetamol", "albuterol", "salbutamol", "folic acid", "leucovorin",
    "carboplatin", "cisplatin", "paclitaxel", "docetaxel", "gemcitabine",
    "fluorouracil", "5-fluorouracil", "cyclophosphamide", "doxorubicin",
    "etoposide", "capecitabine", "oxaliplatin", "irinotecan", "pemetrexed",
    "bevacizumab", "rituximab", "lenalidomide", "bortezomib", "atorvastatin",
    "simvastatin", "lisinopril", "amlodipine", "hydrochlorothiazide",
    "insulin glargine", "insulin lispro", "insulin aspart", "glimepiride",
    "pioglitazone", "sitagliptin", "budesonide", "fluticasone", "tiotropium",
    "sulfasalazine", "hydroxychloroquine", "leflunomide", "azathioprine",
    "cyclosporine", "tacrolimus", "mycophenolate mofetil", "heparin",
    "enoxaparin", "warfarin", "clopidogrel", "omeprazole", "pantoprazole",
    "ondansetron", "diphenhydramine", "vitamin d", "calcium", "potassium chloride",
}

SALT_AND_FORM_RE = re.compile(
    r"\b("
    r"hydrochloride|hcl|dihydrochloride|sodium|disodium|monosodium|potassium|"
    r"calcium|magnesium|mesylate|mesilate|maleate|tartrate|fumarate|acetate|"
    r"succinate|sulfate|sulphate|phosphate|citrate|besylate|besilate|tosylate|"
    r"tosilate|bromide|chloride|hydrate|monohydrate|dihydrate|trihydrate|"
    r"hemifumarate|hemihydrate|malate|lactate|gluconate|propionate|valerate|"
    r"dipropionate|furoate|acetonide|palmitate|benzoate|oxalate|nitrate|"
    r"injection|injectable|tablet|tablets|capsule|capsules|solution|suspension|"
    r"oral|subcutaneous|intravenous|intramuscular|topical|ophthalmic|inhaled|"
    r"inhalation|nasal|spray|cream|gel|ointment|lotion|patch|powder|syrup|"
    r"infusion|concentrate|lyophilized|extended[\s-]release|delayed[\s-]release|"
    r"modified[\s-]release|sustained[\s-]release|controlled[\s-]release|"
    r"xr|er|sr|cr|dr|iv|sc|im|qd|bid|tid|qw|q2w|q4w"
    r")\b",
    flags=re.IGNORECASE,
)
DOSE_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ug|µg|g|kg|ml|l|iu|u|units?|mmol|meq|%)(?:/[a-z0-9]+)?\b.*",
    flags=re.IGNORECASE,
)


def parse_iso_date(date_str: str | None) -> tuple[str | None, float, datetime | None]:
    """Parse CT.gov YYYY, YYYY-MM, or YYYY-MM-DD into (iso_str, year_float, datetime)."""
    if not date_str or not isinstance(date_str, str):
        return None, np.nan, None
    s = date_str.strip()
    m = re.match(r"^(\d{4})(?:-(\d{2}))?(?:-(\d{2}))?", s)
    if not m:
        return None, np.nan, None
    yr = int(m.group(1))
    mo = int(m.group(2)) if m.group(2) else 6
    dy = int(m.group(3)) if m.group(3) else 15
    mo = max(1, min(12, mo))
    dy = max(1, min(28, dy))
    dt = datetime(yr, mo, dy)
    iso = f"{yr:04d}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if (m.group(2) and m.group(3)) else (
        f"{yr:04d}-{int(m.group(2)):02d}-15" if m.group(2) else f"{yr:04d}-06-15"
    )
    return iso, float(yr), dt


def canonicalize_molecule(raw_name: str) -> str:
    """Normalize an intervention drug/biologic string into a canonical molecule key."""
    if not raw_name:
        return ""
    s = raw_name.strip().lower()
    # Strip arm/role prefixes frequently embedded in CT.gov intervention names
    s = re.sub(
        r"^(?:experimental|active\s+comparator|comparator|in\s+open[\s-]label\s+phase\s+treatment\s+with|"
        r"treatment\s+with|group\s+\d+|arm\s+[a-z0-9]+|cohort\s+\d+)\s*[:\-]?\s*",
        "",
        s,
    )
    # Remove parenthetical brand/code aliases e.g. "dupilumab (dupixent)" -> "dupilumab"
    s = re.sub(r"\([^)]*\)", " ", s)
    # Remove dosage tails
    s = DOSE_RE.sub("", s)
    # Remove trailing dose-level / arm labels e.g. "guselkumab dose 1", "benralizumab arm a"
    s = re.sub(
        r"\b(?:dose\s+level\s*\d+|dose\s*\d+|arm\s+[a-z0-9]+|low\s+dose|high\s+dose|medium\s+dose)\b.*",
        "",
        s,
    )
    # Remove salt / formulation suffixes
    s = SALT_AND_FORM_RE.sub(" ", s)
    # Keep alphanumerics, hyphens, spaces
    s = re.sub(r"[^a-z0-9\- ]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip(" -")
    return s[:50]


def is_placebo_term(name: str) -> bool:
    low = name.strip().lower()
    if not low:
        return True
    if low in PLACEBO_EXCLUSION_TERMS:
        return True
    for bad in ("placebo", "sham", "vehicle", "saline", "standard of care", "best supportive", "no intervention"):
        if re.search(rf"\b{re.escape(bad)}\b", low):
            return True
    return False


def _is_valid_mesh_drug(term: str) -> bool:
    """Reject generic class/method/auto-tagger artifact MeSH terms."""
    low = term.strip().lower()
    if not low or len(low) < 4:
        return False
    if low in MESH_ARTIFACT_EXCLUSIONS or is_placebo_term(low):
        return False
    if any(
        bad in low
        for bad in (
            "drug combination", "vaccine", "method", "collection", "solutions",
            "compounds", "hormones", "antibodies", "agents", "inhibitors",
            "bid protein", "salicylhydroxamic",
        )
    ):
        return False
    return True


def extract_primary_molecule(ps: dict, derived: dict) -> tuple[str, str, list[str]]:
    """Extract canonical primary investigational molecule, raw name, and all candidate molecules."""
    brief = ((ps.get("identificationModule") or {}).get("briefTitle") or "").lower()
    official = ((ps.get("identificationModule") or {}).get("officialTitle") or "").lower()
    title_blob = f"{brief} {official}"

    # Collect verified NLM MeSH standardized drug terms first so dirty/coded names can resolve cleanly
    mesh_list = ((derived.get("interventionBrowseModule") or {}).get("meshes") or [])
    mesh_cands: list[str] = []
    for m in mesh_list:
        term = (m.get("term") or "").strip()
        if not term or not _is_valid_mesh_drug(term):
            continue
        c = canonicalize_molecule(term)
        if c and len(c) >= 4 and _is_valid_mesh_drug(c):
            mesh_cands.append(c)
    mesh_cands = list(dict.fromkeys(mesh_cands))
    mesh_non_backbone = [mc for mc in mesh_cands if mc not in BACKBONE_AGENTS]

    interventions = (ps.get("armsInterventionsModule") or {}).get("interventions") or []
    drug_cands: list[tuple[str, str]] = []
    for iv in interventions:
        itype = (iv.get("type") or "").upper()
        if itype not in {"DRUG", "BIOLOGICAL", "COMBINATION_PRODUCT"}:
            continue
        raw = (iv.get("name") or "").strip()
        if not raw or is_placebo_term(raw):
            continue
        canon = canonicalize_molecule(raw)
        if not canon or len(canon) < 2 or is_placebo_term(canon):
            continue
        # If dirty raw string wraps a verified single-word MeSH INN (e.g., "dupilumab sar231893" or
        # "atezolizumab an engineered anti-pd-l1 antibody"), snap cleanly to the canonical INN
        if " " in canon:
            for mc in mesh_non_backbone:
                if " " not in mc and len(mc) >= 5 and re.search(rf"\b{re.escape(mc)}\b", canon):
                    canon = mc
                    break
        drug_cands.append((canon, raw))

    # Deduplicate preserving order
    seen_c: set[str] = set()
    uniq_cands: list[tuple[str, str]] = []
    for c, r in drug_cands:
        if c not in seen_c:
            seen_c.add(c)
            uniq_cands.append((c, r))

    if not uniq_cands and mesh_cands:
        uniq_cands = [(c, c) for c in mesh_cands]

    if not uniq_cands:
        return "", "", []

    # Score candidates: prefer non-backbone drugs, drugs appearing in title, drugs confirmed by MeSH
    mesh_set = set(mesh_cands)

    def score_cand(idx_cand: tuple[int, tuple[str, str]]) -> tuple[int, int, int, int]:
        idx, (c, _) = idx_cand
        not_backbone = 1 if c not in BACKBONE_AGENTS else 0
        in_title = 1 if (len(c) >= 4 and c in title_blob) else 0
        in_mesh = 1 if c in mesh_set else 0
        # Higher tuple wins; prefer earlier index on tie
        return (not_backbone, in_title, in_mesh, -idx)

    best_canon, best_raw = max(enumerate(uniq_cands), key=score_cand)[1]

    # If the best candidate is an internal alphanumeric code (e.g. "cp-690 550", "bibf 1120", "bi 1356")
    # and NLM MeSH uniquely identifies one non-backbone canonical substance (or one appearing in the title),
    # resolve the code cleanly to its standardized INN so twin trials & openFDA link accurately.
    if CODE_MOL_RE.match(best_canon) and mesh_non_backbone:
        if len(mesh_non_backbone) == 1:
            best_canon = mesh_non_backbone[0]
        else:
            title_hits = [mc for mc in mesh_non_backbone if len(mc) >= 5 and mc in title_blob]
            if len(title_hits) == 1:
                best_canon = title_hits[0]

    all_c = [c for c, _ in uniq_cands]
    return best_canon, best_raw, all_c


def classify_event_group(title: str, desc: str) -> tuple[str, bool]:
    """Classify an AE eventGroup into ('placebo', 'active', 'exclude') plus legacy Wave-1 bool.

    Cleanly separates pure placebo/vehicle/sham (including 'Placebo + Background SoC' and
    phase-labeled arms like 'Placebo - Treatment Phase' or 'Placebo-Controlled Phase: Placebo')
    from active-plus-placebo double-dummy arms ('Drug X + Placebo', 'Apremilast (Placebo-Controlled Phase)')
    and genuine crossover/switch arms ('Placebo -> Drug X', 'Drug X / Placebo', 'Placebo-Efgartigimod').
    """
    tl = (title or "").strip().lower()
    dl = (desc or "").strip().lower()

    legacy_is_pl = ("placebo" in tl) or ("placebo" in dl[:120] and "plus placebo" not in tl)

    # Remove design/phase qualifiers ("placebo-controlled", "placebo - controlled") so they neither
    # trigger false crossover exclusions nor misclassify active arms as placebo!
    tl_clean = re.sub(r"\bplacebo\s*[\-\s]\s*controlled\b", " ", tl)
    tl_clean = re.sub(r"\bplacebo\s*-\s*placebo\b", "placebo", tl_clean)
    tl_clean = re.sub(r"\bplacebo\s*-\s*match(?:ed|ing)\b", "matching placebo", tl_clean)
    tl_clean = re.sub(r"\s+", " ", tl_clean).strip()

    # 1. Exclude explicit crossover / switch / open-label extension sequences
    if re.search(
        r"(\bplacebo(?:\s+(?:to|then|followed\s+by)\b|\s*->)|"
        r"(?:\b(?:to|then|followed\s+by)\s+|->\s*)placebo\b)",
        tl_clean,
    ):
        return "exclude", legacy_is_pl

    # Slash crossover ("Placebo / Drug X" or "Drug X / Placebo"), ignoring harmless "Placebo / Placebo"
    for m_slash in re.finditer(
        r"\bplacebo\s*/\s*([a-z0-9][a-z0-9\-]*)|([a-z0-9][a-z0-9\-]*)\s*/\s*placebo\b",
        tl_clean,
    ):
        other_tok = (m_slash.group(1) or m_slash.group(2) or "").strip("-")
        if other_tok and other_tok not in NON_DRUG_ARM_WORDS:
            return "exclude", legacy_is_pl

    # Hyphen/dash crossover ("Placebo-Efgartigimod", "Placebo - TNX-102 SL"): exclude ONLY when
    # the adjacent word is NOT a phase/period/arm/regimen descriptor!
    for m_dash in re.finditer(
        r"\bplacebo\s*-\s*([a-z]{3,})|([a-z]{3,})\s*-\s*placebo\b",
        tl_clean,
    ):
        other_tok = (m_dash.group(1) or m_dash.group(2) or "").strip()
        if other_tok and other_tok not in NON_DRUG_ARM_WORDS:
            return "exclude", legacy_is_pl

    # 2. Double-dummy active arm: "Drug X + Placebo", "Drug X plus Placebo", "Drug X with Placebo"
    if re.search(r"(?:\+|\bplus\b|\bwith\b|\band\b)\s*(?:matching\s+)?(?:placebo|vehicle|sham)\b", tl_clean):
        return "active", legacy_is_pl

    # 3. Pure placebo or "Placebo + Background SoC" (where placebo leads the arm label)
    if re.search(r"\b(placebo|vehicle|sham)\b", tl_clean):
        return "placebo", legacy_is_pl

    # 4. Description fallback only if title has no dose units and no "+" combination
    dl_clean = re.sub(r"\bplacebo\s*[\-\s]\s*controlled\b", " ", dl[:160])
    has_dose_in_title = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:mg|mcg|ug|µg|g|ml|iu|%)\b", tl_clean))
    if (
        not has_dose_in_title
        and "+" not in tl_clean
        and re.search(r"\b(placebo|vehicle|sham)\b", dl_clean)
        and not re.search(r"(?:\+|\bplus\b|\bwith\b)\s*(?:matching\s+)?placebo\b", dl_clean)
    ):
        return "placebo", legacy_is_pl

    return "active", legacy_is_pl


def map_therapeutic_area(conditions: list[str], ancestors: list[dict], meshes: list[dict]) -> str:
    """Assign a mutually exclusive pan-disease therapeutic area from MeSH ancestors & conditions."""
    blob = " | ".join(
        [c.lower() for c in conditions]
        + [(m.get("term") or "").lower() for m in meshes]
        + [(a.get("term") or "").lower() for a in ancestors]
    )
    rules = [
        ("Oncology", ("neoplasm", "carcinoma", "leukemia", "lymphoma", "melanoma", "sarcoma", "myeloma", "tumor", "cancer", "glioma")),
        ("Infectious", ("infection", "virus", "viral", "bacterial", "hiv", "hepatitis", "covid", "influenza", "malaria", "tuberculosis", "fungal", "sepsis", "pneumonia")),
        ("Immune/Inflam/Derm", ("autoimmune", "arthritis", "psoriasis", "dermatitis", "lupus", "spondylitis", "colitis", "crohn", "inflammatory bowel", "eczema", "urticaria", "skin diseases", "immune system")),
        ("Cardiovascular", ("cardiovascular", "heart", "coronary", "hypertension", "atrial fibrillation", "thrombosis", "embolism", "stroke", "atherosclerosis", "vascular diseases", "myocardial", "dyslipidemia", "hypercholesterolemia")),
        ("Endocrine/Metabolic", ("diabetes", "obesity", "metabolic", "endocrine", "thyroid", "osteoporosis", "lipodystrophy", "gout", "hyperuricemia", "hypoglycemia", "acromegaly")),
        ("Neuro/Psych", ("nervous system", "alzheimer", "parkinson", "epilepsy", "migraine", "multiple sclerosis", "schizophrenia", "depression", "depressive", "bipolar", "anxiety", "insomnia", "mental disorders", "neuropathy", "dementia", "adhd")),
        ("Respiratory", ("respiratory", "asthma", "pulmonary", "copd", "bronchitis", "cystic fibrosis", "rhinitis", "lung diseases")),
        ("Ophthalmology", ("eye diseases", "macular", "glaucoma", "retinopathy", "conjunctivitis", "dry eye", "uveitis", "cataract", "vitreomacular")),
        ("GI/Hepatology", ("digestive system", "gastrointestinal", "liver", "hepatic", "cirrhosis", "gerd", "reflux", "constipation", "irritable bowel", "pancreatitis", "steatohepatitis", "nash", "nafld")),
        ("Hematology/Renal", ("hematologic", "anemia", "hemophilia", "thrombocytopenia", "kidney", "renal", "urologic", "nephritis", "overactive bladder", "prostatic")),
        ("Musculoskeletal/Pain", ("musculoskeletal", "osteoarthritis", "pain", "fibromyalgia", "back pain", "fracture")),
    ]
    for label, keywords in rules:
        if any(kw in blob for kw in keywords):
            return label
    return "Other"


def compute_region_shares(countries: list[str]) -> dict[str, float]:
    """Compute mutually exclusive regional site shares summing strictly to 1.0."""
    n = len(countries)
    if n == 0:
        return {}
    c_us = sum(1 for c in countries if c in US_SET)
    c_we_eu = sum(1 for c in countries if c in WE_EU_SET)
    c_dev_apac = sum(1 for c in countries if c in DEV_APAC_CA_SET)
    c_eu_east = sum(1 for c in countries if c in EU_EAST_SET)
    c_ru_ua_only = sum(1 for c in countries if c in RU_UA_ONLY_SET)
    c_noneu_ee_oth = sum(1 for c in countries if c in NONEU_EE_OTHER_SET)
    c_latam = sum(1 for c in countries if c in LATAM_SET)
    c_asia = sum(1 for c in countries if c in ASIA_EMERG_SET)

    c_we = c_we_eu + c_dev_apac
    c_ru_ua = c_ru_ua_only + c_noneu_ee_oth
    c_known = c_us + c_we + c_eu_east + c_ru_ua + c_latam + c_asia
    c_other = n - c_known

    return {
        "us_sh": c_us / n,
        "we_sh": c_we / n,
        "we_eu_sh": c_we_eu / n,
        "dev_apac_ca_sh": c_dev_apac / n,
        "eu_east_sh": c_eu_east / n,
        "ru_ua_sh": c_ru_ua / n,
        "ru_ua_strict_sh": c_ru_ua_only / n,
        "noneu_ee_other_sh": c_noneu_ee_oth / n,
        "ee_sh": (c_eu_east + c_ru_ua) / n,
        "latam_sh": c_latam / n,
        "asia_sh": c_asia / n,
        "other_sh": c_other / n,
        # Country-specific shares for leave-one-country-out diagnostics
        "pl_sh": sum(1 for c in countries if c == "Poland") / n,
        "cz_sh": sum(1 for c in countries if c in {"Czechia", "Czech Republic"}) / n,
        "hu_sh": sum(1 for c in countries if c == "Hungary") / n,
        "ro_sh": sum(1 for c in countries if c == "Romania") / n,
        "bg_sh": sum(1 for c in countries if c == "Bulgaria") / n,
        "ru_sh": sum(1 for c in countries if c in {"Russia", "Russian Federation"}) / n,
        "ua_sh": sum(1 for c in countries if c == "Ukraine") / n,
    }


def parse_study_record(st: dict) -> dict | None:
    """Parse one CT.gov v2 study JSON dict into a flat analytic row."""
    ps = st.get("protocolSection") or {}
    rs = st.get("resultsSection") or {}
    ds = st.get("derivedSection") or {}

    ident = ps.get("identificationModule") or {}
    nct = ident.get("nctId")
    if not nct:
        return None

    status_mod = ps.get("statusModule") or {}
    overall_status = (status_mod.get("overallStatus") or "").upper()

    design = ps.get("designModule") or {}
    phases = [p.upper() for p in (design.get("phases") or [])]
    has_p3 = "PHASE3" in phases
    has_p2 = "PHASE2" in phases
    if not (has_p2 or has_p3):
        return None
    phase_group = "PHASE2_3" if (has_p2 and has_p3) else ("PHASE3" if has_p3 else "PHASE2")

    dinfo = design.get("designInfo") or {}
    allocation = (dinfo.get("allocation") or "").upper()
    if allocation != "RANDOMIZED":
        return None
    masking = ((dinfo.get("maskingInfo") or {}).get("masking") or "").upper()
    is_double_blind = int(masking in {"DOUBLE", "TRIPLE", "QUADRUPLE"})

    enroll_raw = (design.get("enrollmentInfo") or {}).get("count")
    enrollment = float(enroll_raw) if (enroll_raw is not None and enroll_raw > 0) else np.nan

    smod = (ps.get("sponsorCollaboratorsModule") or {}).get("leadSponsor") or {}
    sponsor_cls = (smod.get("class") or "").upper()
    if sponsor_cls != "INDUSTRY":
        return None
    sponsor_nm = re.sub(r"\s+", " ", (smod.get("name") or "").strip().upper())[:60]

    start_iso, start_yr, start_dt = parse_iso_date((status_mod.get("startDateStruct") or {}).get("date"))
    pcomp_iso, pcomp_yr, pcomp_dt = parse_iso_date((status_mod.get("primaryCompletionDateStruct") or {}).get("date"))
    rpost_iso, rpost_yr, _ = parse_iso_date((status_mod.get("resultsFirstPostDateStruct") or {}).get("date"))

    dur_yr = np.nan
    if start_dt and pcomp_dt:
        diff_y = (pcomp_dt - start_dt).days / 365.25
        if 0.0 <= diff_y <= 15.0:
            dur_yr = float(diff_y)

    locs = (ps.get("contactsLocationsModule") or {}).get("locations") or []
    countries = [loc.get("country").strip() for loc in locs if loc.get("country")]
    n_sites = len(countries)
    if n_sites < 1:
        return None
    n_countries = len(set(countries))
    reg_shares = compute_region_shares(countries)

    # Conditions & therapeutic area
    conds = (ps.get("conditionsModule") or {}).get("conditions") or []
    primary_cond = re.sub(r"\s+", " ", str(conds[0]).strip().lower())[:70] if conds else ""
    cb = ds.get("conditionBrowseModule") or {}
    therapeutic_area = map_therapeutic_area(conds, cb.get("ancestors") or [], cb.get("meshes") or [])

    # Canonical investigational molecule
    primary_mol, raw_mol, all_mols = extract_primary_molecule(ps, ds)

    # Adverse Events Module
    ae_mod = rs.get("adverseEventsModule") or {}
    egroups = ae_mod.get("eventGroups") or []
    if len(egroups) < 2:
        return None

    freq_raw = ae_mod.get("frequencyThreshold")
    try:
        freq_thr = float(freq_raw) if freq_raw is not None else np.nan
    except (ValueError, TypeError):
        freq_thr = np.nan

    other_events = ae_mod.get("otherEvents") or []
    serious_events = ae_mod.get("seriousEvents") or []
    n_other_terms = len(other_events)
    n_serious_terms = len(serious_events)

    # Systematic vs non-systematic assessment share
    assess_vals = [e.get("assessmentType") for e in other_events if e.get("assessmentType")]
    if assess_vals:
        n_sys = sum(1 for v in assess_vals if v == "SYSTEMATIC_ASSESSMENT")
        sys_assess_share = n_sys / len(assess_vals)
        all_systematic = int(n_sys == len(assess_vals))
        all_nonsystematic = int(n_sys == 0)
    else:
        sys_assess_share = np.nan
        all_systematic = np.nan
        all_nonsystematic = np.nan

    # Subjective vs objective MedDRA SOC share among reported non-serious events (case-insensitive)
    socs = [(e.get("organSystem") or "").strip().lower() for e in other_events if e.get("organSystem")]
    if socs:
        subj_soc_share = sum(1 for s in socs if s in SUBJECTIVE_SOCS) / len(socs)
        obj_soc_share = sum(1 for s in socs if s in OBJECTIVE_SOCS) / len(socs)
    else:
        subj_soc_share = np.nan
        obj_soc_share = np.nan

    # Parse eventGroups into Placebo vs Active arms (risk-weighted AND unweighted)
    ctrl_list, act_list = [], []
    leg_ctrl_list, leg_act_list = [], []
    all_sae_num, all_sae_den = 0.0, 0.0
    all_oth_num, all_oth_den = 0.0, 0.0
    all_mrt_num, all_mrt_den = 0.0, 0.0

    for g in egroups:
        tl = g.get("title") or ""
        desc = g.get("description") or ""
        sa, sr = g.get("seriousNumAffected"), g.get("seriousNumAtRisk")
        oa, orisk = g.get("otherNumAffected"), g.get("otherNumAtRisk")
        da, dr = g.get("deathsNumAffected"), g.get("deathsNumAtRisk")

        if not sr or sr < 20:
            continue
        s_rate = float(sa) / float(sr) if (sa is not None and 0 <= sa <= sr) else np.nan
        o_rate = float(oa) / float(orisk) if (oa is not None and orisk and orisk >= 20 and 0 <= oa <= orisk) else np.nan
        m_rate = float(da) / float(dr) if (da is not None and dr and dr >= 20 and 0 <= da <= dr) else np.nan

        if not np.isnan(s_rate):
            all_sae_num += float(sa)
            all_sae_den += float(sr)
        if not np.isnan(o_rate):
            all_oth_num += float(oa)
            all_oth_den += float(orisk)
        if not np.isnan(m_rate):
            all_mrt_num += float(da)
            all_mrt_den += float(dr)

        arm_tuple = (
            s_rate, float(sa) if not np.isnan(s_rate) else np.nan, float(sr) if not np.isnan(s_rate) else 0.0,
            o_rate, float(oa) if not np.isnan(o_rate) else np.nan, float(orisk) if not np.isnan(o_rate) else 0.0,
            m_rate, float(da) if not np.isnan(m_rate) else np.nan, float(dr) if not np.isnan(m_rate) else 0.0,
        )
        cls, leg_is_pl = classify_event_group(tl, desc)
        if cls == "placebo":
            ctrl_list.append(arm_tuple)
        elif cls == "active":
            act_list.append(arm_tuple)

        if leg_is_pl:
            leg_ctrl_list.append(arm_tuple)
        else:
            leg_act_list.append(arm_tuple)

    if all_sae_den < 20:
        return None

    def wmean(lst: list[tuple], num_idx: int, den_idx: int) -> float:
        num = sum(x[num_idx] for x in lst if not np.isnan(x[num_idx]) and x[den_idx] > 0)
        den = sum(x[den_idx] for x in lst if not np.isnan(x[num_idx]) and x[den_idx] > 0)
        return float(num / den) if den >= 20 else np.nan

    def umean(lst: list[tuple], rate_idx: int) -> float:
        vals = [x[rate_idx] for x in lst if not np.isnan(x[rate_idx])]
        return float(np.mean(vals)) if vals else np.nan

    has_placebo = int(len(ctrl_list) >= 1 and len(act_list) >= 1)
    has_legacy_placebo = int(len(leg_ctrl_list) >= 1 and len(leg_act_list) >= 1)

    rec: dict = {
        "nct_id": nct,
        "overall_status": overall_status,
        "is_completed": int(overall_status == "COMPLETED"),
        "is_terminated": int(overall_status == "TERMINATED"),
        "phase_group": phase_group,
        "is_phase3": int(has_p3),
        "is_phase2_only": int(has_p2 and not has_p3),
        "sponsor_nm": sponsor_nm,
        "primary_cond": primary_cond,
        "therapeutic_area": therapeutic_area,
        "primary_molecule": primary_mol,
        "raw_molecule": raw_mol[:80],
        "n_molecules": len(all_mols),
        "masking": masking,
        "is_double_blind": is_double_blind,
        "start_date": start_iso,
        "start_year": start_yr,
        "prim_comp_date": pcomp_iso,
        "prim_comp_year": pcomp_yr,
        "results_post_date": rpost_iso,
        "results_post_year": rpost_yr,
        "dur_yr": dur_yr,
        "post_fdaaa_2017": int(pcomp_iso is not None and pcomp_iso >= "2017-01-18") if pcomp_iso else np.nan,
        "post_ich_2017": int(start_yr >= 2017) if not np.isnan(start_yr) else np.nan,
        "post_war_2022": int(start_iso is not None and start_iso >= "2022-02-24") if start_iso else np.nan,
        "enrollment": enrollment,
        "n_sites": int(n_sites),
        "n_countries": int(n_countries),
        "patients_per_site": float(enrollment / n_sites) if (not np.isnan(enrollment) and n_sites > 0) else np.nan,
        "freq_thr": freq_thr,
        "n_other_terms": int(n_other_terms),
        "n_serious_terms": int(n_serious_terms),
        "sys_assess_share": sys_assess_share,
        "all_systematic": all_systematic,
        "all_nonsystematic": all_nonsystematic,
        "subj_soc_share": subj_soc_share,
        "obj_soc_share": obj_soc_share,
        "trial_mean_sae": float(all_sae_num / all_sae_den) if all_sae_den >= 20 else np.nan,
        "trial_mean_oth": float(all_oth_num / all_oth_den) if all_oth_den >= 20 else np.nan,
        "trial_mean_mort": float(all_mrt_num / all_mrt_den) if all_mrt_den >= 20 else np.nan,
        "has_placebo": has_placebo,
        "has_legacy_placebo": has_legacy_placebo,
        "n_ctrl_arms": len(ctrl_list),
        "n_act_arms": len(act_list),
    }
    rec.update(reg_shares)

    if has_placebo:
        c_sae, a_sae = wmean(ctrl_list, 1, 2), wmean(act_list, 1, 2)
        c_oth, a_oth = wmean(ctrl_list, 4, 5), wmean(act_list, 4, 5)
        c_mrt, a_mrt = wmean(ctrl_list, 7, 8), wmean(act_list, 7, 8)
        rec.update({
            "ctrl_sae": c_sae,
            "act_sae": a_sae,
            "sae_rd": a_sae - c_sae if (not np.isnan(a_sae) and not np.isnan(c_sae)) else np.nan,
            "sae_log_rr": float(np.log((a_sae + 0.005) / (c_sae + 0.005))) if (not np.isnan(a_sae) and not np.isnan(c_sae)) else np.nan,
            "ctrl_oth": c_oth,
            "act_oth": a_oth,
            "ctrl_oth_unw": umean(ctrl_list, 3),
            "act_oth_unw": umean(act_list, 3),
            "oth_rd": a_oth - c_oth if (not np.isnan(a_oth) and not np.isnan(c_oth)) else np.nan,
            "oth_log_rr": float(np.log((a_oth + 0.01) / (c_oth + 0.01))) if (not np.isnan(a_oth) and not np.isnan(c_oth)) else np.nan,
            "ctrl_mort": c_mrt,
            "act_mort": a_mrt,
            "mort_rd": a_mrt - c_mrt if (not np.isnan(a_mrt) and not np.isnan(c_mrt)) else np.nan,
            "ctrl_oth_minus_sae": c_oth - c_sae if (not np.isnan(c_oth) and not np.isnan(c_sae)) else np.nan,
            "act_oth_minus_sae": a_oth - a_sae if (not np.isnan(a_oth) and not np.isnan(a_sae)) else np.nan,
            "log_ctrl_oth_to_sae": float(np.log((c_oth + 0.01) / (c_sae + 0.01))) if (not np.isnan(c_oth) and not np.isnan(c_sae)) else np.nan,
            "ctrl_oth_at_risk": float(sum(x[5] for x in ctrl_list)),
            "act_oth_at_risk": float(sum(x[5] for x in act_list)),
        })

    if has_legacy_placebo:
        rec["leg_ctrl_oth"] = wmean(leg_ctrl_list, 4, 5)
        rec["leg_act_oth"] = wmean(leg_act_list, 4, 5)

    return rec


def main() -> int:
    pages = sorted(RAW_DIR.glob("page_*.json.gz"))
    if not pages:
        print("[ERROR] No raw page_*.json.gz files found in data/raw_ctgov!", flush=True)
        return 1

    print(f"[START] Parsing {len(pages)} raw gzipped CT.gov pages...", flush=True)
    rows: list[dict] = []
    seen_nct: set[str] = set()
    total_raw = 0
    other_country_counter: Counter[str] = Counter()

    for pg in pages:
        with gzip.open(pg, "rb") as fh:
            studies = json.loads(fh.read().decode("utf-8")).get("studies", [])
        total_raw += len(studies)
        for st in studies:
            ps = st.get("protocolSection") or {}
            nct = (ps.get("identificationModule") or {}).get("nctId")
            if not nct or nct in seen_nct:
                continue
            # Track unmapped countries for audit
            locs = (ps.get("contactsLocationsModule") or {}).get("locations") or []
            for loc in locs:
                c = (loc.get("country") or "").strip()
                if c and c not in (US_SET | WE_DEV_SET | EAST_ALL_SET | LATAM_SET | ASIA_EMERG_SET):
                    other_country_counter[c] += 1
            rec = parse_study_record(st)
            if rec is not None:
                seen_nct.add(nct)
                rows.append(rec)

    df = pd.DataFrame(rows)
    # Derived log covariates & FE keys
    df["log_enroll"] = np.log(df["enrollment"].where(df["enrollment"] > 0))
    df["log_sites"] = np.log(df["n_sites"].where(df["n_sites"] > 0))
    df["log_countries"] = np.log(df["n_countries"].where(df["n_countries"] > 0))
    df["log_pps"] = np.log(df["patients_per_site"].where(df["patients_per_site"] > 0))
    df["log_other_terms"] = np.log1p(df["n_other_terms"])

    df["mol_sponsor"] = np.where(
        (df["primary_molecule"] != "") & (df["sponsor_nm"] != ""),
        df["primary_molecule"] + "||" + df["sponsor_nm"],
        "",
    )
    df["mol_cond"] = np.where(
        (df["primary_molecule"] != "") & (df["primary_cond"] != ""),
        df["primary_molecule"] + "||" + df["primary_cond"],
        "",
    )
    df["mol_sp_cond"] = np.where(
        (df["primary_molecule"] != "") & (df["sponsor_nm"] != "") & (df["primary_cond"] != ""),
        df["primary_molecule"] + "||" + df["sponsor_nm"] + "||" + df["primary_cond"],
        "",
    )
    df["sp_cond"] = np.where(
        (df["sponsor_nm"] != "") & (df["primary_cond"] != ""),
        df["sponsor_nm"] + "||" + df["primary_cond"],
        "",
    )

    all_parquet = PROC_DIR / "d30_all_trials.parquet"
    df.to_parquet(all_parquet, index=False)

    # Core MRCT Placebo-Controlled Analytic Panel:
    # Completed (main), start_year 2005-2024, enrollment >= 100, >= 5 sites, >= 3 countries, explicit placebo & active arm
    mrct_all_status = df[
        (df["start_year"].between(2005, 2024))
        & (df["enrollment"] >= 100)
        & (df["n_sites"] >= 5)
        & (df["n_countries"] >= 3)
        & (df["has_placebo"] == 1)
    ].copy()
    mrct_comp = mrct_all_status[mrct_all_status["is_completed"] == 1].copy()

    mrct_parquet = PROC_DIR / "d30_mrct_placebo_panel.parquet"
    mrct_csv = PROC_DIR / "d30_mrct_placebo_panel.csv"
    mrct_all_parquet = PROC_DIR / "d30_mrct_placebo_allstatus.parquet"
    mrct_comp.to_parquet(mrct_parquet, index=False)
    mrct_comp.to_csv(mrct_csv, index=False)
    mrct_all_status.to_parquet(mrct_all_parquet, index=False)

    p3_comp = mrct_comp[mrct_comp["is_phase3"] == 1]
    p2_comp = mrct_comp[mrct_comp["is_phase2_only"] == 1]

    summary = {
        "total_raw_studies_scanned": int(total_raw),
        "parsed_randomized_industry_p2_p3_allstatus": int(len(df)),
        "parsed_completed_total": int((df["is_completed"] == 1).sum()),
        "parsed_completed_phase3": int(((df["is_completed"] == 1) & (df["is_phase3"] == 1)).sum()),
        "parsed_completed_phase2_only": int(((df["is_completed"] == 1) & (df["is_phase2_only"] == 1)).sum()),
        "mrct_placebo_completed_p2_p3": int(len(mrct_comp)),
        "mrct_placebo_completed_phase3": int(len(p3_comp)),
        "mrct_placebo_completed_phase2_only": int(len(p2_comp)),
        "mrct_placebo_allstatus_p2_p3": int(len(mrct_all_status)),
        "mrct_placebo_terminated_p2_p3": int((mrct_all_status["is_terminated"] == 1).sum()),
        "p3_twin_mol_sponsor_n": int(p3_comp[p3_comp["mol_sponsor"] != ""].groupby("mol_sponsor")["nct_id"].transform("count").ge(2).sum()),
        "p3_twin_mol_cond_n": int(p3_comp[p3_comp["mol_cond"] != ""].groupby("mol_cond")["nct_id"].transform("count").ge(2).sum()),
        "p23_twin_mol_sponsor_n": int(mrct_comp[mrct_comp["mol_sponsor"] != ""].groupby("mol_sponsor")["nct_id"].transform("count").ge(2).sum()),
        "p23_twin_mol_cond_n": int(mrct_comp[mrct_comp["mol_cond"] != ""].groupby("mol_cond")["nct_id"].transform("count").ge(2).sum()),
        "therapeutic_areas_mrct_p23": mrct_comp["therapeutic_area"].value_counts().to_dict(),
        "top_unmapped_other_countries": dict(other_country_counter.most_common(15)),
        "artifacts_sha256": {
            "d30_all_trials.parquet": hashlib.sha256(all_parquet.read_bytes()).hexdigest(),
            "d30_mrct_placebo_panel.parquet": hashlib.sha256(mrct_parquet.read_bytes()).hexdigest(),
            "d30_mrct_placebo_allstatus.parquet": hashlib.sha256(mrct_all_parquet.read_bytes()).hexdigest(),
        },
    }
    sum_path = PROC_DIR / "panel_build_summary.json"
    sum_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print("[DONE] Panel build summary:", flush=True)
    print(json.dumps(summary, indent=2), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
