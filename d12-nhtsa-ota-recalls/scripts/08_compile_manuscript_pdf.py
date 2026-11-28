"""Step 8: Clean entrypoint that delegates PDF compilation to the zero-hardcode v4 builder
(scripts/11_build_v4_manuscripts_and_pdfs.py) and re-exports verify_pdf_zero_leaks.
"""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

BASE_DIR = Path(r"D:\AI_Science\antigravity\d12_boost_nhtsa_ota_recalls_20261125")


def _load_v4_builder():
    path = BASE_DIR / "scripts" / "11_build_v4_manuscripts_and_pdfs.py"
    spec = importlib.util.spec_from_file_location("v4_builder", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_pdf_zero_leaks(pdf_path: Path) -> tuple[int, list[str]]:
    return _load_v4_builder().verify_pdf_zero_leaks(pdf_path)


def main() -> int:
    return int(_load_v4_builder().main())


if __name__ == "__main__":
    sys.exit(main())
