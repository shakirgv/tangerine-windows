"""Headless checks for converters and tools. Run: python tests/test_backend.py"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import pymupdf as fitz  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

from tangerine import registry  # noqa: E402
from tangerine.tools.add_bg import PRESETS, add_background  # noqa: E402
from tangerine.tools.crop import crop_image  # noqa: E402
from tangerine.tools.edit import adjust  # noqa: E402
from tangerine.tools.metadata import read_metadata, strip_metadata  # noqa: E402
from tangerine.tools.redact import redact  # noqa: E402

OUT = ROOT / "tests" / "_out"
failures: list[str] = []


def check(name: str, fn):
    try:
        result = fn()
        print(f"ok    {name}: {result}")
    except Exception as exc:  # noqa: BLE001
        failures.append(name)
        print(f"FAIL  {name}: {type(exc).__name__}: {exc}")


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)

    img = Image.new("RGBA", (640, 400), (255, 140, 0, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((100, 60, 400, 340), fill=(30, 144, 255, 255))
    d.rectangle((420, 80, 600, 200), fill=(255, 255, 255, 128))
    src_png = OUT / "sample.png"
    img.save(src_png)

    pdf_path = OUT / "sample.pdf"
    doc = fitz.open()
    for n in range(2):
        page = doc.new_page()
        page.insert_text((72, 100), f"Hello Tangerine page {n + 1}", fontsize=18)
    doc.save(pdf_path)
    doc.close()

    for group in registry.groups_for("image", ".png"):
        for action in group.actions:
            if action.handler:
                check(f"image {action.id}", lambda a=action: [p.name for p in a.handler(src_png)])

    # Convert chain: HEIC/AVIF results must reopen
    for ext in (".heic", ".avif", ".webp", ".tiff", ".bmp", ".pdf", ".docx"):
        produced = next((p for p in OUT.glob(f"sample*{ext}")), None)
        if produced and ext not in (".pdf", ".docx"):
            check(f"reopen {ext}", lambda p=produced: Image.open(p).size)

    for group in registry.groups_for("pdf", ".pdf"):
        for action in group.actions:
            check(f"pdf {action.id}", lambda a=action: [p.name for p in a.handler(pdf_path)])

    docx_src = next(OUT.glob("sample*.docx"), None)
    if docx_src:
        check("docx to txt", lambda: [p.name for p in registry.groups_for("docx", ".docx")[0].actions[0].handler(docx_src)])

    check("metadata read", lambda: len(read_metadata(src_png)))
    check("metadata strip", lambda: strip_metadata(src_png)[0].name)
    check("crop", lambda: crop_image(img, (10, 10, 200, 100)).size)
    check("edit", lambda: adjust(img, 20, 10, -30, 10, 90, True, False).size)
    check("redact", lambda: [redact(img, [(50, 50, 120, 80)], s).size for s in ("Black box", "Blur", "Pixelate")])
    for preset in PRESETS:
        out = add_background(img, preset, 10, 6, 40, (16, 9))
        check(f"add_bg {preset.name}", lambda o=out: o.size)
    out = add_background(img, PRESETS[0], 8, 4, 35)
    out.save(OUT / "addbg_preview.png")

    from tangerine.converters.media import ffmpeg_exe

    check("ffmpeg", lambda: ffmpeg_exe())

    print("\nFAILED: " + ", ".join(failures) if failures else "\nAll backend checks passed")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
