"""
Download ONLY `RockTheVote.rda` and `RockTheVote.Rd` from official CRAN `pscl_1.5.9.tar.gz` (GPL-2)
into `raw_sources/` and verify their exact Stage-0 SHA-256 hashes.
Public aggregate market-level counts only; zero individual voter records.
"""
from __future__ import annotations

import hashlib
import io
import pathlib
import tarfile
import urllib.request


CRAN_PSCL_URL = "https://cran.r-project.org/src/contrib/pscl_1.5.9.tar.gz"
EXPECTED_SHA256 = {
    "pscl_RockTheVote.rda": "851400e266058e24cb46b964a401bf687933a26a1f2657a8630b86302f29ae4d",
    # Raw LF bytes inside CRAN pscl_1.5.9.tar.gz (Windows CRLF text write gives 0c80edd0...)
    "pscl_RockTheVote.Rd": "978b44ea4097e68f28219501a4de5f0aa02e1c2e24e85b24003440bd3a80ce5c",
}


def main() -> None:
    raw = pathlib.Path(__file__).resolve().parent / "raw_sources"
    raw.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(CRAN_PSCL_URL, headers={"User-Agent": "Python-urllib/3.12 (academic-research)"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        tb_bytes = resp.read()
    with tarfile.open(fileobj=io.BytesIO(tb_bytes), mode="r:gz") as tf:
        targets = {
            "pscl_RockTheVote.rda": "pscl/data/RockTheVote.rda",
            "pscl_RockTheVote.Rd": "pscl/man/RockTheVote.Rd",
        }
        for dst_name, member_name in targets.items():
            data = tf.extractfile(member_name).read()
            got = hashlib.sha256(data).hexdigest()
            assert got == EXPECTED_SHA256[dst_name], f"SHA-256 mismatch for {dst_name}: {got}"
            (raw / dst_name).write_bytes(data)
            print(f"Verified {dst_name:24s} {len(data):6d} B  sha256={got}")


if __name__ == "__main__":
    main()
