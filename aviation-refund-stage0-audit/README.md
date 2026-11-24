# Aviation Refund Rule Stage 0 Measurement-Gate Audit (`aviation-refund-stage0-audit`)

Standalone, formally **closed Stage 0B** legal-timeline, BTS data-dictionary, and pre-rule confounder/selection audit for a prospective empirical evaluation of the 2024 U.S. DOT Automatic Cash Refund Rule (`14 CFR Part 260`, `89 FR 32760`, FAA Reauthorization Act of 2024 § 503).

**Status:** **Formally Closed at Stage 0B Measurement Gate (2026-11-24).**  
**Zero post-`2024-04` BTS flight archives were ever downloaded or analyzed.** No policy effect, refund receipt, or causal claim is estimated.

---

## Core Measurement-Gate Conclusions

1. **Descriptive Segment Operations Only — Policy Effect & Refund Receipt Unestimated:**  
   Published U.S. DOT BTS On-Time Performance data (`TableInfo FGJ`) supports **descriptive segment operations only**. Both the **policy effect** and **refund receipt** remain **unestimated**; prior carrier policies, preexisting `14 CFR § 259.4` tarmac delay rules, and threshold/completion censoring all matter.
2. **Statutory Treatment vs. BTS Universe (`14 CFR §§ 260.2 / 260.6` & FR `2024-07177` Footnote 30):**
   - `14 CFR § 260.2` defines the domestic `3-hour` (`180`-min) threshold relative to the **originally purchased itinerary** for **earlier scheduled origination departure (`>= 3h` earlier)** or **later scheduled final-destination arrival (`>= 3h` later)** — not realized positive nonstop `DepDelay`. `§ 260.6` triggers automatic fare refunds only when the passenger rejects / does not accept alternative transportation.
   - **FR `2024-07177` Footnote 30** distinguishes `14 CFR Part 234`'s within-7-day CRS cancellation reporting universe from `14 CFR Part 260`'s purchase-time refund universe. Completed flight clocks cannot mark Part 260 eligibility, and **no defensible untreated comparison or versioned purchased-itinerary data was verified in this audit**.
3. **Staggered Legal Timeline (No Single Clean Oct 28 Onset):**
   - `2024-04-26`: Final Rule `89 FR 32760` (`2024-07177`) published; `2024-05-16`: FAA Reauthorization Act § 503 (`49 U.S.C. § 42305`) required eligible automatic ticket refunds starting May 16, 2024 (per DOT Small Business Compliance Guidance); `2024-06-25`: Final Rule effective date; `2024-10-28`: remaining regulatory/ancillary compliance date; `2026-07-07`: `91 FR 41556` enforcement pause for merely renumbered flights through `2027-07-07`.
4. **Contrast with Xing (*JEMS*, `DOI: 10.1111/jems.70019`) & Pre-Rule `2024-03` Selection/Confounder Evidence:**
   - **Xing (*JEMS*)** studies the 2009-era EU rule (CJEU *Sturgeon*, `https://eur-lex.europa.eu/legal-content/en/ALL/?uri=CELEX%3A62007CJ0402`), which provides **compensation eligibility for covered travelers delayed at the final destination by at least three hours, subject to extraordinary-circumstance exceptions**, and uses **the paper's eligible/exempt carrier comparison**. By contrast, **the U.S. rule being studied provides fare refunds in eligible nontravel cases**, and **no defensible untreated comparison or versioned purchased-itinerary data was verified in this audit**.
   - **Pre-rule `2024-03` audit (`628,786` scheduled flights, zero post-`2024-04` bytes touched):**
     - **Cancellation-tail missingness:** `1,021 / 5,377` (`18.99%`) of cancelled flights have missing `Tail_Number` vs. `0 / 623,409` (`0.00%`) of operating records; high airport continuity (`98.38%`, `7,715` discontinuous) of realized day-tail sequences still reflects post-assignment rotations on local clocks and does not supply pre-assignment.
     - **Preexisting `14 CFR § 259.4` tarmac rule & completion censoring:** `8.06%` (`1,033 / 12,818`) of completed flights with `DepDelay in [120, 240]` had gate-return tarmac time (`TotalAddGTime/LongestAddGTime > 0`); `189` cancelled flights had non-null pushback `DepDelay` (`49 >= 120` min) and `171` had gate-return tarmac time (cf. DOT OIG `ST2017003`, Oct 26, 2016; Fukui & Nagata 2014). Conditioning on `DepDelay < 120` is completion-conditioned, not known zero exposure.
     - **Heaping & carrier-panel shift:** Pre-rule `2024-03` `[120, 240]`-min `ArrDelay % 5 == 0` varies from `25.17%` (`NK`) and `22.10%` (`WN`) to `19.11%` (`DL`) and `18.39%` (`G4`), and the `2022–2026` Part 234 carrier panel shifts with Alaska–Hawaiian SOC consolidation (`Oct 2025`) and Spirit cessation (`mid-2026`).
     - Earlier Poisson calculations established pre-rule flight-count capacity only (`48/48` `HTTP 200` monthly archives `2022-09`–`2026-08`; `632,162` avg flights/month in `2023-10` & `2024-03`), not causal identifiability.

---

## Package Contents, Metadata-Only Projection & Verification

- `STAGE0B_MEASUREMENT_GATE_CLOSURE.md` — Formal Stage 0B closure memo.
- `PROPOSAL_AND_STAGE0_PLAN.md` — Superseded initial Stage 0 draft (retained with explicit retraction banner for audit history).
- `audit/stage0_*.py` & `audit/stage0b_*.py` — Pre-rule-only audit scripts (zero post-`2024-04` downloads).
- `audit/stage0_bts_and_statute_audit.json` & `audit/stage0b_legal_and_measurement_gate.json` — Documented **metadata-and-aggregate-count projections** stripping long copied regulatory/HTML/dictionary excerpts and Crossref author arrays while preserving all provenance URLs, DOIs, legal timeline facts, FR Footnote 30 cross-reference, and executed pre-rule schema/selection counts.
- `ARCHIVE_MANIFEST.json`, `requirements.txt`, `.gitattributes` (`* -text`). Zero raw flight records, zero copied abstracts, zero PDFs, zero credentials, zero causal claims.

Verify exact archived bytes:
```bash
python3 -c '
import hashlib, json, pathlib
m = json.loads(pathlib.Path("ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
for e in m["files"]:
    raw = pathlib.Path(e["path"]).read_bytes()
    assert len(raw) == e["bytes"] and hashlib.sha256(raw).hexdigest() == e["sha256"], e["path"]
print(f"Verified {len(m["files"])} allowlisted files successfully.")
'
```

## Official Primary Sources
- DOT Final Rule `89 FR 32760` (`2024-07177`, `14 CFR Part 260`, incl. §§ 260.2, 260.6 & Footnote 30): https://www.govinfo.gov/content/pkg/FR-2024-04-26/html/2024-07177.htm
- DOT Small Business Compliance Guidance (`2024-12`): https://www.transportation.gov/sites/dot.gov/files/2024-12/Refund%20Final%20Rule%20Small%20Business%20Compliance%20Guidance.pdf
- DOT Enforcement Discretion Extension `91 FR 41556` (`2026-07-07`): https://www.federalregister.gov/documents/2026/07/07/2026-13675/airline-refunds-and-other-consumer-protections
- BTS On-Time Performance Data Dictionary (`FGJ`): https://www.transtats.bts.gov/TableInfo.asp?QO_fu146_anzr=b0-gvzr&gnoyr_VQ=FGJ
- DOT OIG Tarmac Delay Rule Report (`ST2017003`, Oct 26, 2016): https://www.oig.dot.gov/library-item/33850
- Historical EU Scope (CJEU *Sturgeon*, Joined Cases C-402/07 & C-432/07): https://eur-lex.europa.eu/legal-content/en/ALL/?uri=CELEX%3A62007CJ0402
- Closest Precedents: Xing (*JEMS*, `https://doi.org/10.1111/jems.70019`), Forbes, Lederman & Tombe (*AEJ: Micro* 2015, `https://doi.org/10.1257/mic.20130164`), Fukui & Nagata (*Economics of Transportation* 2014, `https://doi.org/10.1016/j.ecotra.2014.02.004`), Kleven (*Annu. Rev. Econ.* 2016, `https://doi.org/10.1146/annurev-economics-080315-015234`).
