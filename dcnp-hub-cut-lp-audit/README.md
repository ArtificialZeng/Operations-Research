# dcnp-hub-cut-lp-audit

Frozen archival record of a **synthetic-only** study of hub-lifted closed-neighbourhood valid inequalities for the fixed-budget distance-2 critical node problem (2-DCNP). Not a paper, not a performance claim, no submission intended.

## Outcome
- **Valid inequalities (Theorem 1):** exhaustive 2^n integer check on 15 small synthetic graphs, 2,284,928 exact checks, 0 violations (`certificates/stage0b_validity_and_witness.json`). Not claimed to be facets or a convex hull.
- **Exact LP results (`certificates/`):** on d-regular graphs of girth >= 6 the whole row family reduces to a boxed two-variable LP (proved for all d >= 3, see `docs/THEOREM_VALIDITY_AND_WITNESS.md` Section 7, scope map). The simplified closed form `n*max_t v_t(alpha)` is verified exactly only for 3 <= d <= 10 and alpha in [1/(d+1), 1/3]. Exact two-sided Fraction certificates exist for Heawood, Tutte-Coxeter and PG(2,3)/PG(2,5) Levi graphs (e.g. PG(2,5), b=20: base 96, t=1 rows 135, whole family 153).
- **Sealed held-out benchmark (`sealed/`, 16 synthetic instances, 2 arms, one run, exit 0):** Tier 1 PASS (16/16 root-LP lifts, mean extra gap closure 47.09%). Tier 2 FAIL: shifted wall ratio 0.9907 vs <= 0.85; on the 4 branching instances 1 win / 1 tie / 2 losses. No speed claim.

## Limitations
Synthetic graphs only; one instance order and solver seed; the baseline is the specified bounded comparator (thin formulation + simplicial fixing + bounded clique and 5-cycle separation, caps in the script), not all published formulations; HiGHS 1.15.1 only; four branching instances; hub-cut caps were fixed before the run and never varied. Prior-art screen is incomplete: Chen et al. (2025) full text was not accessible, so overlap with that paper is **not** excluded. No priority claim.

## Re-open criterion
Re-open only if (a) authorized full text of Chen, Chen, Li & Dai (2025), COAP, doi:10.1007/s10589-025-00698-5 shows no equivalent projected star / closed-neighbourhood inequality, **and** (b) a concrete new falsifiable mechanism is written down before any run.

## Reproduce
Python 3.14 with `requirements.txt`. Run in a scratch copy (scripts overwrite their JSON; timing fields differ between runs).
```
python verify_archive.py                                   # sha256 of every file against ARCHIVE_MANIFEST.json
python sealed/stage1_postcheck.py                          # check the original JSON and receipt before any rerun
cd certificates
python stage0b_validity_and_witness.py                     # exhaustive 2^n check + smoke (~30 s)
python stage0b_rational_opt_lift_witness.py
python stage0b_exact_rational_certificate.py
python stage2_family_reduction_certificate.py
python stage2b_closed_form_check.py
cd ../sealed
python stage1_heldout_synthetic_benchmark.py               # ~3 min, 60 s per-arm limit, single thread
```
The sealed protocol and script are byte-identical to the files hashed before the run (protocol `cf81fad4...71f5`, script `e958589f...5b5f`, results `8dbfd8f3...9700`); the protocol still says "unexecuted" because that is its original pre-run wording.

## Not included
Stage 0 smoke/audit on named public networks (not synthetic-only; relied on a repository with no license file), launcher shell script, session notes, any third-party code or data, PDFs.

## Official links
- Salemi & Buchanan, INFORMS J. Comput. 34(3), doi:10.1287/ijoc.2021.1136 (preprint: optimization-online.org/2020/04/7751)
- Chen, Chen, Li, Dai (2025), COAP, doi:10.1007/s10589-025-00698-5
- Alozie et al., Comput. Oper. Res. (2021), doi:10.1016/j.cor.2021.105254
