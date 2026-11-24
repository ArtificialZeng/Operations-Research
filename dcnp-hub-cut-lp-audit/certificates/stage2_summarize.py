import json
from pathlib import Path
d = json.loads((Path(__file__).resolve().parent / "stage2_family_reduction_certificate.json").read_text())
for s in d["sweeps"]:
    if s["family"] in ("all", "t1full") and s["d"] >= 3:
        print(s["d"], s["family"])
        for p in s["pieces"]:
            print("   [%s, %s] v = %s + (%s) a  active=%s" % (p["from"], p["to"], p["intercept"], p["slope"], p["active"]))
print("--- comparison")
bad_eq = 0
for c in d["comparison_at_breakpoints"]:
    if c["full_nbr_all_t"] != c["all_subsets"]:
        bad_eq += 1
    print(c["d"], c["alpha"], "base", c["base"], "t1", c["t1_exact"], "t1cf", c["t1_closed_form"], "full", c["full_nbr_all_t"], "all", c["all_subsets"], "all-t1", c["all_minus_t1"])
print("full_nbr != all count:", bad_eq)
