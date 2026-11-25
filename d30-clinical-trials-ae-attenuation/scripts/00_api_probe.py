"""Quick schema & count probe for ClinicalTrials.gov v2 and openFDA APIs."""
from __future__ import annotations

import sys

import requests

CTGOV_URL = "https://clinicaltrials.gov/api/v2/studies"
OPENFDA_BASE = "https://api.fda.gov/drug"


def probe_ctgov() -> None:
    print("=== ClinicalTrials.gov v2 Count Probe ===", flush=True)
    queries = {
        "phase3_completed_industry_results": (
            "AREA[Phase]PHASE3 AND AREA[StudyType]INTERVENTIONAL "
            "AND AREA[LeadSponsorClass]INDUSTRY AND AREA[OverallStatus]COMPLETED "
            "AND AREA[HasResults]true"
        ),
        "phase2_completed_industry_results": (
            "AREA[Phase]PHASE2 AND AREA[StudyType]INTERVENTIONAL "
            "AND AREA[LeadSponsorClass]INDUSTRY AND AREA[OverallStatus]COMPLETED "
            "AND AREA[HasResults]true"
        ),
        "phase2_or_3_completed_industry_results": (
            "(AREA[Phase]PHASE2 OR AREA[Phase]PHASE3) AND AREA[StudyType]INTERVENTIONAL "
            "AND AREA[LeadSponsorClass]INDUSTRY AND AREA[OverallStatus]COMPLETED "
            "AND AREA[HasResults]true"
        ),
        "phase2_or_3_allstatus_industry_results": (
            "(AREA[Phase]PHASE2 OR AREA[Phase]PHASE3) AND AREA[StudyType]INTERVENTIONAL "
            "AND AREA[LeadSponsorClass]INDUSTRY AND AREA[HasResults]true"
        ),
    }
    for name, q in queries.items():
        r = requests.get(
            CTGOV_URL,
            params={"query.term": q, "pageSize": 1, "countTotal": "true"},
            timeout=30,
        )
        r.raise_for_status()
        d = r.json()
        print(f"  {name}: totalCount={d.get('totalCount')}", flush=True)

    # Fetch 1 rich sample Phase-3 record to verify exact field paths
    for field_spec in [
        "ProtocolSection.IdentificationModule,ProtocolSection.StatusModule,ProtocolSection.DesignModule,ProtocolSection.ConditionsModule,ProtocolSection.InterventionsModule,ProtocolSection.SponsorCollaboratorsModule,ProtocolSection.ContactsLocationsModule,ResultsSection.AdverseEventsModule",
        "IdentificationModule,StatusModule,DesignModule,ConditionsModule,InterventionsModule,SponsorCollaboratorsModule,ContactsLocationsModule,AdverseEventsModule",
        None,
    ]:
        params = {
            "query.term": queries["phase3_completed_industry_results"],
            "pageSize": 1,
        }
        if field_spec:
            params["fields"] = field_spec
        r = requests.get(CTGOV_URL, params=params, timeout=30)
        print(f"  fields={str(field_spec)[:40]}... -> status={r.status_code}", flush=True)
        if r.status_code != 200:
            print("    err:", r.text[:200], flush=True)
            continue
        studies = r.json().get("studies", [])
        if studies:
            st = studies[0]
            ps = st.get("protocolSection", {})
            rs = st.get("resultsSection", {})
            ae = rs.get("adverseEventsModule", {})
            print("    NCT:", ps.get("identificationModule", {}).get("nctId"), flush=True)
            print("    protocolSection keys:", list(ps.keys()), flush=True)
            print("    phases:", ps.get("designModule", {}).get("phases"), flush=True)
            print("    conditions:", ps.get("conditionsModule", {}).get("conditions"), flush=True)
            print("    interventions sample:", ps.get("interventionsModule", {}).get("interventions", [])[:2], flush=True)
            print("    ae keys:", list(ae.keys()), flush=True)
            print("    ae freq_thr:", ae.get("frequencyThreshold"), flush=True)
            if ae.get("otherEvents"):
                print("    otherEvents[0] keys:", list(ae["otherEvents"][0].keys()), flush=True)
                print("    otherEvents[0] assessmentType:", ae["otherEvents"][0].get("assessmentType"), flush=True)
            if ae.get("eventGroups"):
                print("    eventGroups[0]:", ae["eventGroups"][0], flush=True)
            break


def probe_openfda() -> None:
    print("\n=== openFDA Schema Probe (dupilumab) ===", flush=True)
    # 1. drugsfda
    r1 = requests.get(
        f"{OPENFDA_BASE}/drugsfda.json",
        params={"search": 'openfda.generic_name.exact:"DUPILUMAB"', "limit": 5},
        timeout=30,
    )
    print(f"  drugsfda status={r1.status_code}", flush=True)
    if r1.status_code == 200:
        d1 = r1.json()
        rec = d1["results"][0]
        print("  app_num:", rec.get("application_number"), "sponsor:", rec.get("sponsor_name"), flush=True)
        subs = rec.get("submissions", [])
        print(f"  n_submissions={len(subs)}, sample types:", sorted({(s.get("submission_type"), s.get("submission_class_code"), s.get("submission_class_code_description")) for s in subs})[:10], flush=True)

    # 2. label
    r2 = requests.get(
        f"{OPENFDA_BASE}/label.json",
        params={"search": 'openfda.generic_name.exact:"DUPILUMAB"', "limit": 1},
        timeout=30,
    )
    print(f"  label status={r2.status_code}", flush=True)
    if r2.status_code == 200:
        rec2 = r2.json()["results"][0]
        print("  label keys (safety):", [k for k in rec2.keys() if any(w in k for w in ["box", "warn", "adverse", "effective"])], flush=True)

    # 3. event (FAERS)
    r3 = requests.get(
        f"{OPENFDA_BASE}/event.json",
        params={
            "search": 'patient.drug.openfda.generic_name.exact:"DUPILUMAB" AND occurcountry:"US" AND patient.drug.drugcharacterization:1',
            "count": "serious",
        },
        timeout=30,
    )
    print(f"  FAERS US primary-suspect status={r3.status_code} results={r3.json().get('results') if r3.status_code==200 else r3.text[:150]}", flush=True)


if __name__ == "__main__":
    probe_ctgov()
    probe_openfda()
    sys.exit(0)
