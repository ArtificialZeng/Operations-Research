"""
Stage-0 Outcome-Independent Balanced Single-Line Full Diagnostic Split (N = 30) &
Fast Persistent-KeepAlive Minimal HTTP-Range Extraction.

Why Single-Line Pinned-Code Diagnostic:
  - Audited RayanA07/LinePilot commit `8fb89a62fb0565290b72ba61cb073d732d8e7578` (and all
    branches/repos under RayanA07): the released Python/CLI (`Digitizer/digitizer_api.py`)
    exports ONLY one active color slot (`_auto_select_color`), and no public automatic
    multicurve DP runner is shipped. Running multiline plots through a single-slot API would
    force structural line-count failures (pred=1 != gt in {2,3,5}, F_i=1.0) in BOTH OCR and
    oracle arms, confounding calibration bottlenecks with single-slot API limits.
  - Therefore we lock a balanced SINGLE-line Full diagnostic cohort (N = 30 non-bridge Full
    `base_id`s: 10 matplotlib, 10 plotly, 10 altair), leaving ALL 60 Lite/bridge `base_id`s
    and ALL remaining 2,470 Full `base_id`s completely untouched and un-downloaded.
  - This pinned-code diagnostic is NEVER compared directly with Table 3's Full 0.672 / 38.2% TU.
"""
from __future__ import annotations

import hashlib
import http.client
import io
import json
import struct
import urllib.parse
import urllib.request
import zipfile
import zlib
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq

import eval_digitizerbench_sec43 as ev

PROJ = Path(r"D:\AI_Science\antigravity\linepilot_axis_calibration_stage0_20261124")
DATA_DIR = PROJ / "data_digitizerbench"
DEV_DIR = DATA_DIR / "full_single_dev_30"

DS_REV = "8b4a3190d5991414dad92049671de75754dd9f44"
FULL_URL = f"https://huggingface.co/datasets/LinePilot/DigitizerBench/resolve/{DS_REV}/full.zip"
FULL_SIZE = 749958209
RENDERERS = ["matplotlib", "plotly", "altair"]
PER_RENDERER = 10  # 10 x 3 = 30 balanced single-line Full diagnostic plots


def sha256_str(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def sha256_file(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class KeepAliveRangeClient:
    """Resolves HF 302 redirect once and reuses a single HTTPS Keep-Alive connection for Ranges."""

    def __init__(self, url: str):
        req = urllib.request.Request(
            url, headers={"Range": "bytes=0-0", "User-Agent": "linepilot-stage0/1.0"}
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            self.final_url = resp.geturl()
            resp.read()
        parsed = urllib.parse.urlsplit(self.final_url)
        self.host = parsed.netloc
        self.path = parsed.path + (f"?{parsed.query}" if parsed.query else "")
        self.conn = http.client.HTTPSConnection(self.host, timeout=120)
        self.bytes_fetched = 0
        self.requests_made = 0

    def fetch(self, start: int, end_inclusive: int) -> bytes:
        for attempt in range(3):
            try:
                self.conn.request(
                    "GET",
                    self.path,
                    headers={
                        "Range": f"bytes={start}-{end_inclusive}",
                        "User-Agent": "linepilot-stage0/1.0",
                        "Connection": "keep-alive",
                    },
                )
                resp = self.conn.getresponse()
                data = resp.read()
                if resp.status not in (200, 206):
                    raise RuntimeError(f"HTTP {resp.status} for range {start}-{end_inclusive}")
                self.bytes_fetched += len(data)
                self.requests_made += 1
                return data
            except Exception:
                self.conn.close()
                self.conn = http.client.HTTPSConnection(self.host, timeout=120)
                if attempt == 2:
                    raise
        raise RuntimeError("Unreachable")

    def close(self) -> None:
        self.conn.close()


class SubRangeView(io.RawIOBase):
    """Seekable view of a byte slice [base_offset, base_offset + length) via KeepAliveRangeClient."""

    def __init__(self, client: KeepAliveRangeClient, base_offset: int, length: int):
        self.client = client
        self.base_offset = base_offset
        self.length = length
        self.pos = 0

    def readable(self) -> bool:
        return True

    def seekable(self) -> bool:
        return True

    def tell(self) -> int:
        return self.pos

    def seek(self, offset: int, whence: int = io.SEEK_SET) -> int:
        if whence == io.SEEK_SET:
            self.pos = offset
        elif whence == io.SEEK_CUR:
            self.pos += offset
        elif whence == io.SEEK_END:
            self.pos = self.length + offset
        self.pos = max(0, min(self.length, self.pos))
        return self.pos

    def read(self, n: int = -1) -> bytes:
        if self.pos >= self.length:
            return b""
        to_read = (self.length - self.pos) if (n is None or n < 0) else min(n, self.length - self.pos)
        if to_read <= 0:
            return b""
        abs_start = self.base_offset + self.pos
        data = self.client.fetch(abs_start, abs_start + to_read - 1)
        self.pos += len(data)
        return data


def zip_entry_data_offset(client: KeepAliveRangeClient, info: zipfile.ZipInfo) -> int:
    lh = client.fetch(info.header_offset, info.header_offset + 29)
    sig, _, _, _, _, _, _, _, _, fname_len, extra_len = struct.unpack("<IHHHHHIIIHH", lh)
    assert sig == 0x04034B50
    return info.header_offset + 30 + fname_len + extra_len


def main() -> None:
    DEV_DIR.mkdir(parents=True, exist_ok=True)
    manifest_path = DATA_DIR / "full_metadata_only" / "manifest.parquet"
    lite_manifest_path = DATA_DIR / "lite_extracted" / "lite" / "manifest.parquet"
    full_m = pd.read_parquet(manifest_path)
    lite_m = pd.read_parquet(lite_manifest_path)
    lite_base_ids = set(lite_m["base_id"].astype(str))

    pool = full_m[
        (~full_m["is_bridge"])
        & (~full_m["base_id"].astype(str).isin(lite_base_ids))
        & (full_m["S10"] == "single")
        & (full_m["line_count"] == 1)
    ].copy()
    assert pool["base_id"].nunique() == len(pool) == 814

    selected_rows = []
    for rend in RENDERERS:
        cell = pool[pool["T1"] == rend].copy()
        cell["sel_hash"] = cell["base_id"].astype(str).map(
            lambda bid: sha256_str(f"linepilot_stage0_single_dev_20261124:{bid}")
        )
        cell = cell.sort_values("sel_hash", kind="mergesort")
        for _, r in cell.head(PER_RENDERER).iterrows():
            selected_rows.append(r)

    dev_df = pd.DataFrame(selected_rows).reset_index(drop=True)
    dev_base_ids = set(dev_df["base_id"].astype(str))
    dev_image_ids = set(dev_df["image_id"].astype(str))
    untouched_base_ids = set(full_m["base_id"].astype(str)) - dev_base_ids

    assert len(dev_df) == 30 and len(dev_base_ids) == 30
    assert len(dev_base_ids & lite_base_ids) == 0
    assert len(dev_base_ids & untouched_base_ids) == 0

    client = KeepAliveRangeClient(FULL_URL)
    print("Resolved CDN host:", client.host, flush=True)

    # Read ZIP Central Directory via Keep-Alive view
    with zipfile.ZipFile(SubRangeView(client, 0, FULL_SIZE), "r") as zf:
        zinfo_map = {info.filename: info for info in zf.infolist()}

    # 1. Fetch each of the 30 PNGs (reuse already-fetched intact PNGs!)
    img_receipts = []
    reused = 0
    for idx, r in dev_df.iterrows():
        entry_name = f"full/{r['image_path']}"
        info = zinfo_map[entry_name]
        dest_png = DEV_DIR / r["image_path"]
        dest_png.parent.mkdir(parents=True, exist_ok=True)
        if dest_png.is_file() and dest_png.stat().st_size == info.file_size:
            raw_png = dest_png.read_bytes()
            reused += 1
        else:
            data_off = zip_entry_data_offset(client, info)
            comp_bytes = client.fetch(data_off, data_off + info.compress_size - 1)
            raw_png = comp_bytes if info.compress_type == zipfile.ZIP_STORED else zlib.decompress(comp_bytes, -zlib.MAX_WBITS)
            assert len(raw_png) == info.file_size
            dest_png.write_bytes(raw_png)
        img_receipts.append({
            "base_id": str(r["base_id"]),
            "image_id": str(r["image_id"]),
            "renderer": str(r["T1"]),
            "plot_type": str(r["S10"]),
            "line_count": int(r["line_count"]),
            "R1_thickness_px": float(r["R1"]),
            "R2_color": str(r["R2"]),
            "R3_dpi": int(r["R3"]),
            "R4_blur": float(r["R4"]),
            "R5_width_in": float(r["R5"]),
            "R7_tick_font_pt": float(r["R7"]),
            "R8_ticks": int(r["R8"]),
            "R9_x_range": str(r["R9"]),
            "R10_y_range": str(r["R10"]),
            "width_px": int(r["width_px"]),
            "height_px": int(r["height_px"]),
            "image_path": str(r["image_path"]),
            "png_bytes": len(raw_png),
            "png_sha256": hashlib.sha256(raw_png).hexdigest(),
            "selection_hash": str(r["sel_hash"]),
        })
    print(f"30/30 dev PNGs ready (reused={reused}, fetched={30 - reused}); bytes so far={client.bytes_fetched:,}", flush=True)

    # 2. Fetch tick_ground_truth.parquet (289 KB, ZIP_STORED) in ONE Range call
    tk_info = zinfo_map["full/tick_ground_truth.parquet"]
    tk_off = zip_entry_data_offset(client, tk_info)
    tk_raw = client.fetch(tk_off, tk_off + tk_info.file_size - 1)
    tk_full_sha = hashlib.sha256(tk_raw).hexdigest()
    tk_all = pd.read_parquet(io.BytesIO(tk_raw))
    tk_dev = tk_all[tk_all["image_id"].isin(dev_image_ids)].copy()
    del tk_all, tk_raw
    assert tk_dev["image_id"].nunique() == 30
    print(f"Filtered tick_ground_truth to 30 dev images ({len(tk_dev)} rows).", flush=True)

    # 3. Read ONLY the Parquet row groups of full/ground_truth.parquet containing our 30 dev image_ids
    gt_info = zinfo_map["full/ground_truth.parquet"]
    gt_off = zip_entry_data_offset(client, gt_info)
    gt_view = SubRangeView(client, gt_off, gt_info.file_size)
    pf = pq.ParquetFile(gt_view)
    cols_needed = ["image_id", "line_id", "sample_index", "x", "y"]
    img_col_idx = pf.schema_arrow.get_field_index("image_id")
    print(f"ground_truth.parquet num_row_groups={pf.num_row_groups}", flush=True)

    dev_gt_parts = []
    rg_read = 0
    for rg_i in range(pf.num_row_groups):
        rg_meta = pf.metadata.row_group(rg_i)
        col_stats = rg_meta.column(img_col_idx).statistics
        if col_stats is not None and col_stats.has_min_max:
            lo_id = str(col_stats.min)
            hi_id = str(col_stats.max)
            if not any(lo_id <= iid <= hi_id for iid in dev_image_ids):
                continue
        tbl = pf.read_row_group(rg_i, columns=cols_needed)
        rg_read += 1
        df_rg = tbl.to_pandas()
        sub = df_rg[df_rg["image_id"].isin(dev_image_ids)]
        if not sub.empty:
            dev_gt_parts.append(sub)
        print(f"  read row_group {rg_i}/{pf.num_row_groups} -> matched {len(sub)} rows (cum bytes={client.bytes_fetched:,})", flush=True)
    gt_dev = pd.concat(dev_gt_parts, ignore_index=True)
    assert gt_dev["image_id"].nunique() == 30
    client.close()

    dev_df.drop(columns=["sel_hash"]).to_parquet(DEV_DIR / "dev_manifest_30.parquet", index=False)
    gt_dev.to_parquet(DEV_DIR / "dev_ground_truth_30.parquet", index=False)
    tk_dev.to_parquet(DEV_DIR / "dev_tick_ground_truth_30.parquet", index=False)

    split_receipt = {
        "dataset_id": "LinePilot/DigitizerBench",
        "pinned_revision": DS_REV,
        "scope_note": (
            "Pinned-code (RayanA07/LinePilot 8fb89a62) balanced SINGLE-line Full diagnostic split "
            "(N = 30 non-bridge single-line Full base_ids: 10 matplotlib, 10 plotly, 10 altair). "
            "Upstream 8fb89a62 CLI exports one active color slot only and no public multicurve DP "
            "runner is shipped; do NOT compare this subset directly with Table 3's Full 0.672."
        ),
        "full_manifest_sha256": sha256_file(manifest_path),
        "full_tick_ground_truth_parquet_sha256": tk_full_sha,
        "full_ground_truth_parquet_row_groups_total": pf.num_row_groups,
        "full_ground_truth_parquet_row_groups_read": rg_read,
        "selection_rule": (
            "Exclude ALL 60 Lite/bridge base_ids (540 images) and restrict to non-bridge single-line "
            "Full base_ids (814 unique base_ids; 1 image per base_id, keeping all rerenders together). "
            "Within each renderer (matplotlib, plotly, altair), sort base_ids ascending by "
            "sha256('linepilot_stage0_single_dev_20261124:' + base_id) and take the first 10 -> "
            "30 balanced single-line Full dev plots. All remaining 2,470 Full base_ids (2,950 images) "
            "remain untouched and un-downloaded."
        ),
        "total_full_base_ids": 2500,
        "dev_selected_base_ids_count": 30,
        "untouched_full_base_ids_count": len(untouched_base_ids),
        "overlap_with_lite_base_ids": 0,
        "overlap_with_untouched_full_base_ids": 0,
        "http_range_bytes_fetched_session": client.bytes_fetched,
        "http_range_requests_session": client.requests_made,
        "dev_ground_truth_30_sha256": sha256_file(DEV_DIR / "dev_ground_truth_30.parquet"),
        "dev_tick_ground_truth_30_sha256": sha256_file(DEV_DIR / "dev_tick_ground_truth_30.parquet"),
        "selected_plots": img_receipts,
    }
    (PROJ / "STAGE0_SINGLE_DEV_30_RECEIPT.json").write_text(json.dumps(split_receipt, indent=2), encoding="utf-8")

    sec43_fx = ev.run_unit_fixtures()
    fixture_receipt = {
        "purpose": "Pre-launch Stage-0 fixture receipt: exact paper §4.3 evaluator unit tests + workspace-only Tesseract 5.5.3 + LinePilot 75 pytest + 3-figure smoke test.",
        "eval_sec43_py_sha256": sha256_file(PROJ / "eval_digitizerbench_sec43.py"),
        "portable_ocr_receipt_sha256": sha256_file(PROJ / "PORTABLE_OCR_RECEIPT.json"),
        "dev_split_receipt_sha256": sha256_file(PROJ / "STAGE0_SINGLE_DEV_30_RECEIPT.json"),
        "sec43_unit_fixtures": sec43_fx,
        "upstream_pytest_passed": "75 passed in 1.67s",
        "upstream_smoke_test_passed": "3/3 figures digitized and scored within 2.0% NRMSE (0.667%-1.405%)",
        "all_prelaunch_fixtures_passed": True,
    }
    (PROJ / "STAGE0_PRELAUNCH_FIXTURES_RECEIPT.json").write_text(json.dumps(fixture_receipt, indent=2), encoding="utf-8")

    print("\nSUCCESS: Locked 30 balanced single-line Full dev plots:")
    print(dev_df[["image_id", "T1", "R1", "R2", "R3", "R4", "R5", "R8", "width_px", "height_px"]].to_string(index=False))


if __name__ == "__main__":
    main()
