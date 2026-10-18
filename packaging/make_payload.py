"""Zip dist/Tangerine into build/payload.zip, the data bundled inside the installer."""

import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "dist" / "Tangerine"
DEST = ROOT / "build" / "payload.zip"

if not (SRC / "Tangerine.exe").exists():
    sys.exit("dist/Tangerine/Tangerine.exe is missing: build the app first")
DEST.parent.mkdir(exist_ok=True)
DEST.unlink(missing_ok=True)
with zipfile.ZipFile(DEST, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
    for path in sorted(SRC.rglob("*")):
        if path.is_file():
            zf.write(path, path.relative_to(SRC))
print(f"payload: {DEST.stat().st_size / 1e6:.0f} MB")
