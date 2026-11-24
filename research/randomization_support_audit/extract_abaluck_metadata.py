"""
Extract ONLY tiny aggregate/code/README files (< 200 KB total) from Zenodo 5703876
(Abaluck et al. 2022 Science Bangladesh Mask Cluster-RCT, CC-BY-4.0) via HTTP Range.
ZERO individual/personal survey or blood files are downloaded.
"""
from __future__ import annotations

import hashlib
import io
import pathlib
import struct
import urllib.request
import zlib

import pandas as pd


ZENODO_URL = "https://zenodo.org/api/records/5703876/files/bd-mask-rct.zip/content"
ZIP_SIZE = 37681487

WANTED = [
    "bd-mask-rct/README.md",
    "bd-mask-rct/01_data/README.md",
    "bd-mask-rct/01_data/00_common/01_clean/union_reg_sample.dta",
    "bd-mask-rct/01_data/00_common/00_raw/union_baseline_blood_stats.dta",
    "bd-mask-rct/02_code/00_common/02_bal_tests_vill.do",
    "bd-mask-rct/02_code/05_bloodEndline/robustness/10a_reg_rand_inf_symp_sero.do",
    "bd-mask-rct/02_code/05_bloodEndline/robustness/10b_reg_rand_inf_symp.do",
    "bd-mask-rct/02_code/01_surveillance/04_reg_vill_cross_rand.do",
]


def get_range(start: int, end: int) -> bytes:
    req = urllib.request.Request(
        ZENODO_URL,
        headers={
            "User-Agent": "Python-urllib/3.12 (academic-research)",
            "Range": f"bytes={start}-{end}",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def main() -> None:
    out = pathlib.Path(__file__).resolve().parent / "raw_sources" / "abaluck2022_bd_mask_rct"
    out.mkdir(parents=True, exist_ok=True)

    tail = get_range(ZIP_SIZE - (65536 + 22), ZIP_SIZE - 1)
    eocd = tail.rfind(b"PK\x05\x06")
    cd_size, cd_offset = struct.unpack("<II", tail[eocd + 12 : eocd + 20])
    cd = get_range(cd_offset, cd_offset + cd_size - 1)

    index = {}
    pos = 0
    while pos < len(cd):
        assert cd[pos : pos + 4] == b"PK\x01\x02"
        comp_method = struct.unpack("<H", cd[pos + 10 : pos + 12])[0]
        comp_size, uncomp_size = struct.unpack("<II", cd[pos + 20 : pos + 28])
        fname_len, extra_len, comment_len = struct.unpack("<HHH", cd[pos + 28 : pos + 34])
        lhoff = struct.unpack("<I", cd[pos + 42 : pos + 46])[0]
        fname = cd[pos + 46 : pos + 46 + fname_len].decode("utf-8", errors="replace")
        index[fname] = (comp_method, comp_size, uncomp_size, lhoff)
        pos += 46 + fname_len + extra_len + comment_len

    for fn in WANTED:
        comp_method, comp_size, uncomp_size, lhoff = index[fn]
        # Read local header + compressed payload
        blob = get_range(lhoff, lhoff + 30 + len(fn) + 256 + comp_size - 1)
        assert blob[:4] == b"PK\x03\x04"
        lh_fn_len, lh_ex_len = struct.unpack("<HH", blob[26:30])
        payload = blob[30 + lh_fn_len + lh_ex_len : 30 + lh_fn_len + lh_ex_len + comp_size]
        if comp_method == 0:
            raw = payload
        elif comp_method == 8:
            raw = zlib.decompress(payload, -15)
        else:
            raise ValueError(f"Unsupported method {comp_method}")
        assert len(raw) == uncomp_size
        rel = fn.replace("bd-mask-rct/", "")
        dst = out / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(raw)
        print(f"Extracted {rel:65s} {len(raw):7d} B  sha256={hashlib.sha256(raw).hexdigest()[:16]}")

    print("\n=== 10a_reg_rand_inf_symp_sero.do ===")
    print((out / "02_code/05_bloodEndline/robustness/10a_reg_rand_inf_symp_sero.do").read_text(encoding="utf-8", errors="replace"))

    print("\n=== 01_data/README.md ===")
    print((out / "01_data/README.md").read_text(encoding="utf-8", errors="replace")[:3500])

    print("\n=== union_reg_sample.dta SCHEMA & COUNTS ===")
    df = pd.read_stata(out / "01_data/00_common/01_clean/union_reg_sample.dta", convert_categoricals=False)
    print("Shape:", df.shape)
    print("Columns:", list(df.columns))
    print(df.head(12).to_string())
    for c in df.columns:
        if df[c].nunique() <= 20:
            print(f"  {c}: {df[c].value_counts(dropna=False).to_dict()}")
        else:
            print(f"  {c}: nunique={df[c].nunique()}")

    print("\n=== union_baseline_blood_stats.dta SCHEMA ===")
    df2 = pd.read_stata(out / "01_data/00_common/00_raw/union_baseline_blood_stats.dta", convert_categoricals=False)
    print("Shape:", df2.shape, "Columns:", list(df2.columns))
    print(df2.head(8).to_string())


if __name__ == "__main__":
    main()
