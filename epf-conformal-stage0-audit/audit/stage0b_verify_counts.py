"""Complete Stage 0B exact verification of SMARD 18:00 text and EnergyBench exact day counts (non-outcome)."""

from __future__ import annotations

import io
import json
from pathlib import Path
import re
from urllib.request import Request, urlopen

import pandas as pd

HERE = Path(__file__).resolve().parent
AUDIT_PATH = HERE / "stage0b_frontier_and_boundary_audit.json"
HEADERS = {"User-Agent": "Academic-Research-Stage0B-Verify/1.0"}


def get(url: str) -> bytes:
    with urlopen(Request(url, headers=HEADERS), timeout=30) as r:
        return r.read()


def main() -> None:
    data = json.loads(AUDIT_PATH.read_text(encoding="utf-8"))

    # 1. Inspect SMARD page text (handle '18 Uhr' or '18.00' or JSON-embedded content)
    smard_url = "https://www.smard.de/home/neu-prognostizierte-pv-und-windenergieeinspeisung-208702"
    html = get(smard_url).decode("utf-8", errors="replace")
    plain = " ".join(re.sub(r"<[^>]+>", " ", html).split())
    hits = re.findall(r".{0,100}(?:18\s*Uhr|18[:.]00|Prognose|Vortag|Folgetag).{0,120}", plain, flags=re.I)
    data["smard_official_release_deadline"]["plain_text_len"] = len(plain)
    data["smard_official_release_deadline"]["matched_snippets"] = hits[:5]
    # Also check SMARD CMS JSON endpoint if Angular SPA
    cms_url = "https://www.smard.de/nip-download-manager/nip/download/market-data"
    article_api = "https://www.smard.de/app/page_data/208702/de.json"
    try:
        art = json.loads(get(article_api).decode("utf-8", errors="replace"))
        art_str = json.dumps(art, ensure_ascii=False)
        ahits = re.findall(r".{0,100}(?:18\s*Uhr|18[:.]00|Folgetag|Vortag).{0,120}", art_str, flags=re.I)
        data["smard_official_release_deadline"]["article_api_url"] = article_api
        data["smard_official_release_deadline"]["article_api_snippets"] = ahits[:5]
    except Exception as e:
        data["smard_official_release_deadline"]["article_api_error"] = str(e)

    # 2. Verify EnergyBench models.csv and actuals/actuals.parquet exact date/row/zone/target counts (NO values inspected!)
    models_raw = get("https://huggingface.co/datasets/ujohn33/foretec-energy-bench/resolve/main/models.csv")
    df_models = pd.read_csv(io.BytesIO(models_raw))
    eb_counts = {
        "models_count": int(len(df_models)),
        "models_columns": list(df_models.columns),
        "model_families": df_models["family"].value_counts().to_dict() if "family" in df_models.columns else {},
    }
    try:
        act_raw = get("https://huggingface.co/datasets/ujohn33/foretec-energy-bench/resolve/main/actuals/actuals.parquet")
        df_act = pd.read_parquet(io.BytesIO(act_raw), columns=["delivery_date", "zone", "target", "delivery_utc"])
        eb_counts["actuals_rows"] = int(len(df_act))
        eb_counts["actuals_zones"] = sorted(df_act["zone"].dropna().astype(str).unique().tolist())
        eb_counts["actuals_targets"] = sorted(df_act["target"].dropna().astype(str).unique().tolist())
        price_dates = sorted(df_act.loc[df_act["target"] == "price", "delivery_date"].astype(str).unique().tolist())
        eb_counts["price_unique_delivery_dates"] = len(price_dates)
        eb_counts["price_min_date"] = price_dates[0] if price_dates else None
        eb_counts["price_max_date"] = price_dates[-1] if price_dates else None
    except Exception as e:
        eb_counts["actuals_parquet_error"] = str(e)

    data["energybench_frozen_inputs"]["exact_counts_non_outcome"] = eb_counts
    AUDIT_PATH.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    print("SMARD_SNIPPETS:", data["smard_official_release_deadline"].get("matched_snippets") or data["smard_official_release_deadline"].get("article_api_snippets"))
    print("ENERGYBENCH_COUNTS:", json.dumps(eb_counts, indent=2))


if __name__ == "__main__":
    main()
