"""Verify every archived file against ARCHIVE_MANIFEST.json (sha256 and size)."""
import hashlib, json, sys
from pathlib import Path
root = Path(__file__).resolve().parent
m = json.loads((root / "ARCHIVE_MANIFEST.json").read_text(encoding="utf-8"))
bad = 0
for e in m["files"]:
    p = root / e["path"]
    data = p.read_bytes() if p.exists() else None
    ok = data is not None and hashlib.sha256(data).hexdigest() == e["sha256"] and len(data) == e["bytes"]
    bad += not ok
    print("OK  " if ok else "FAIL", e["path"])
extra = sorted(str(p.relative_to(root)).replace("\\", "/") for p in root.rglob("*") if p.is_file()
               and p.name != "ARCHIVE_MANIFEST.json" and ".git/" not in str(p).replace("\\", "/")
               and str(p.relative_to(root)).replace("\\", "/") not in {e["path"] for e in m["files"]})
print("unlisted files:", extra)
sys.exit(1 if bad or extra else 0)
