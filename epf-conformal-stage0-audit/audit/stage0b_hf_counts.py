"""Fetch EnergyBench HuggingFace datasets-server info + exact first/last rows via JSON API (zero pyarrow, zero outcome modeling)."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.request import Request, urlopen

HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE / "stage0b_frontier_and_boundary_audit.json"
HEADERS = {"User-Agent": "Academic-Research-Stage0B-HFCheck/1.0"}


def get_json(url: str) -> dict:
    with urlopen(Request(url, headers=HEADERS), timeout=25) as r:
        return json.loads(r.read().decode("utf-8"))


def main() -> None:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))
    info = {}
    for cfg in ["scores", "forecasts", "actuals"]:
        try:
            res = get_json(f"https://datasets-server.huggingface.co/size?dataset=ujohn33/foretec-energy-bench&config={cfg}")
            info[cfg] = res.get("size", {}).get("splits", res)
        except Exception as e:
            info[cfg] = {"error": str(e)}
    # Check unique issue_date counts from scores/live and scores/backtest via first-rows/filter check
    splits_meta = {}
    for split in ["backtest", "live"]:
        try:
            r0 = get_json(f"https://datasets-server.huggingface.co/rows?dataset=ujohn33/foretec-energy-bench&config=scores&split={split}&offset=0&length=1")
            tot = r0.get("num_rows_total", 0)
            rlast = get_json(f"https://datasets-server.huggingface.co/rows?dataset=ujohn33/foretec-energy-bench&config=scores&split={split}&offset={max(0, tot - 1)}&length=1")
            first_row = r0["rows"][0]["row"] if r0.get("rows") else {}
            last_row = rlast["rows"][0]["row"] if rlast.get("rows") else {}
            splits_meta[split] = {
                "num_rows_total": tot,
                "first_issue_date": first_row.get("issue_date"),
                "last_issue_date": last_row.get("issue_date"),
                "columns": list(first_row.keys()),
            }
        except Exception as e:
            splits_meta[split] = {"error": str(e)}
    data["energybench_frozen_inputs"]["hf_datasets_server_sizes"] = info
    data["energybench_frozen_inputs"]["scores_split_date_bounds"] = splits_meta
    AUDIT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"sizes": info, "bounds": splits_meta}, indent=2))


if __name__ == "__main__":
    main()
