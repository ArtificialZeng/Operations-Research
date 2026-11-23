# Strict weighted graph bisection

This release contains executable source and results for local comparisons on the public FrontierOR `armbruster2012` task and an independent DIMACS10 Delaware graph. Each part must satisfy the original integer capacity, node 0 must be in `partition_S`, and the cut is evaluated on the original edge costs. The results are local public-data replays. Timings depend on the machine and timeout handling.

## Recorded results

`results.csv` includes the full comparison, KaHIP diagnostics, fixed-seed pairs, eight Delaware PyMetis seeds, and the two refinement runs from the best seed. All counted results passed the pinned task checker and independent recomputation. Rows marked `weight_only_fallback` describe a feasible fallback after the KaHIP arm failed to provide a usable graph-based seed. The `diagnostic` rows preserve the initial KaHIP wrapper and the KaHIP 3.29 retest. The published v1 reference is identified separately as an incumbent or an optimum where available.

On Delaware, the weight-complement arm improved the original PyMetis seed 0 from 2,740,223 to 2,699,852. The ordinary boundary arm reached 2,731,153. The two synthetic large cases in the same paired test were ties. In a follow-up search over PyMetis seeds 0–7, seed 4 produced **2,588,362**. Both refinement arms finished at that same cut from the same verified seed. The eight seed runs used 3.23 solver seconds in aggregate, and the follow-up reserved four seconds for seeds and capped refinement at 56 seconds. Host launch overhead is reported separately per run. Seed 0 is repeated in the sweep to identify its already recorded result from the full comparison.

The local IP and globally balanced move combinations build on existing graph-partitioning approaches. The fixed-seed pairs hold the starting partition, solver source and nominal budget fixed while switching the complement flag. [Henzinger, Noe and Schulz, SEA 2018](https://doi.org/10.4230/LIPIcs.SEA.2018.4) · [Sanders and Schulz, SEA 2013](https://doi.org/10.1007/978-3-642-38527-8_16)

## Data and local replay

The recorded solver runtime was Linux x86-64 with CPython 3.14.10, two CPUs and 4 GiB, with networking disabled during solving. The public checker ran on CPython 3.12.16. `requirements.txt` pins the solver dependencies, including KaHIP 3.30, PyMetis 2025.2.2, OR-Tools 9.15.6755 and HiGHS 1.15.1. Use a separate environment with `kahip==3.29` for the old-version diagnostic. Release files and input identifiers are pinned in `MANIFEST.json`.

From this directory, fetch the pinned public instance and checker. Adjust `CASE` for one of the five `large_instance_N` cases.

```sh
python3.14 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
mkdir -p work
REV=ef42a2eac13595453f986d9df0b62e86e75ab596
BASE="https://huggingface.co/datasets/frontieror/FrontierOR/resolve/$REV/tasks/armbruster2012"
CASE=tiny_instance
curl -fL "$BASE/instance/$CASE.json" -o "work/$CASE.json"
curl -fL "$BASE/feasibility_check.py" -o work/feasibility_check.py
export OMP_NUM_THREADS=2
timeout 60s python metis_exact_baseline.py --problem armbruster2012 \
  --instance "work/$CASE.json" --output work/solution.json --time-limit 60 --seed 0
python3.12 work/feasibility_check.py --instance_path "work/$CASE.json" \
  --solution_path work/solution.json --result_path work/check.json
python -c 'import json,sys; from armbruster_contract import verify_strict; print(verify_strict(*(json.load(open(p)) for p in sys.argv[1:])))' \
  "work/$CASE.json" work/solution.json
```

`baseline.py`, `native_refinement.py`, and `boundary_milp_candidate.py` accept the same four standard flags. The historical scripts preserve the original bytes used in the older CSV rows. The native refinement is the Anti-Gravity implementation with its separately generated KaHIP child-process repair. The current boundary candidate adds `--seed-witness` for offline comparison and `--weight-complements` for the additional vertex-selection rule. Run both settings with the same newly generated PyMetis witness. The original pairing used seed 0 and 59 seconds. The follow-up used the lowest verified seed from the 0–7 sweep and 56 seconds.

For Delaware, fetch the original public MAT file and generate the JSON locally. Conversion retains the original Census POP100 weights, including zeros, and exactly one copy of each positive rook-adjacency edge. The conversion originally used CPython 3.11.18, NumPy 2.4.6 and SciPy 1.17.1. Verify the converted JSON hash against `MANIFEST.json` before comparing results. The converter also emits a feasibility certificate for the two equal loads. Generate an independent PyMetis seed for refinement.

```sh
MAT=https://www.cise.ufl.edu/research/sparse/mat/DIMACS10/de2010.mat
curl -fL "$MAT" -o work/de2010.mat
python prepare_de2010.py work/de2010.mat --source-url "$MAT"
for seed in 0 1 2 3 4 5 6 7; do
  timeout 60s python metis_exact_baseline.py --problem armbruster2012 \
    --instance work/de2010.json --output "work/metis-$seed.json" --time-limit 60 --seed "$seed"
done
timeout 56s python boundary_milp_candidate.py --problem armbruster2012 \
  --instance work/de2010.json --output work/refined-complements.json --time-limit 56 \
  --seed-witness work/metis-4.json --weight-complements
```

Input files, reference solutions, seed witnesses and execution logs stay with their original archives or local runs. The FrontierOR inputs and checker come from the pinned dataset. The Delaware matrix comes from the official SuiteSparse archive. [FrontierOR task snapshot](https://huggingface.co/datasets/frontieror/FrontierOR/tree/ef42a2eac13595453f986d9df0b62e86e75ab596/tasks/armbruster2012) · [DIMACS10 Delaware archive](https://sparse.tamu.edu/DIMACS10/de2010) · [Census source totals](https://www2.census.gov/programs-surveys/decennial/tables/2010/2010-apportionment/apport2010-table2.pdf)
