"""Headless checks for every converter and tool. Run: python tests/test_backend.py"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUT = ROOT / "tests" / "_out"
# Keep test runs away from the user's real settings and history.
os.environ["APPDATA"] = str(OUT / "appdata")

import pymupdf  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

from tangerine import history, registry, settings, utils  # noqa: E402
from tangerine.converters import archive, media  # noqa: E402
from tangerine.tools import pdf_tools  # noqa: E402
from tangerine.tools.add_bg import PRESETS, add_background  # noqa: E402
from tangerine.tools.crop import crop_image  # noqa: E402
from tangerine.tools.edit import adjust  # noqa: E402
from tangerine.tools.metadata import read_metadata, strip_metadata  # noqa: E402
from tangerine.tools.redact import redact  # noqa: E402
from tangerine.tools.remove_bg import remove_background  # noqa: E402
from tangerine.tools.resize import fit_long_side, resize_image  # noqa: E402
from tangerine.tools.watermark import COLORS, POSITIONS, add_watermark  # noqa: E402

failures: list[str] = []


def check(name: str, fn):
    try:
        print(f"ok    {name}: {fn()}")
    except Exception as exc:  # noqa: BLE001
        failures.append(name)
        print(f"FAIL  {name}: {type(exc).__name__}: {exc}")


def must(cond, message="assertion failed"):
    if not cond:
        raise AssertionError(message)
    return "yes"


def run_all(kind: str, src: Path, skip: set[str] = frozenset()):
    for group in registry.groups_for(kind, src.suffix):
        for action in group.actions:
            if action.handler and action.id not in skip:
                check(f"{kind} {action.id}", lambda a=action: [p.name for p in a.handler(src)])


def main() -> int:
    shutil.rmtree(OUT, ignore_errors=True)
    OUT.mkdir(parents=True)

    # --- sample inputs -------------------------------------------------------------------
    img = Image.new("RGBA", (640, 400), (255, 140, 0, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((100, 60, 400, 340), fill=(30, 144, 255, 255))
    d.rectangle((420, 80, 600, 200), fill=(255, 255, 255, 128))
    src_png = OUT / "sample.png"
    img.save(src_png)

    plain = Image.new("RGB", (600, 400), (240, 240, 240))
    ImageDraw.Draw(plain).ellipse((200, 100, 400, 300), fill=(200, 30, 30))
    plain_path = OUT / "product.jpg"
    plain.save(plain_path)

    ocr_img = Image.new("RGB", (700, 160), "white")
    ImageDraw.Draw(ocr_img).text((20, 40), "Hello Tangerine 12345", fill="black", font=ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 44))
    ocr_path = OUT / "scan.png"
    ocr_img.save(ocr_path)

    def make_pdf(path: Path, pages: int, text: str = "Hello Tangerine") -> Path:
        doc = pymupdf.open()
        for n in range(pages):
            doc.new_page().insert_text((72, 100), f"{text} page {n + 1} contact me@example.com", fontsize=14)
        doc.save(path)
        doc.close()
        return path

    pdf_a = make_pdf(OUT / "a.pdf", 3)
    pdf_b = make_pdf(OUT / "b.pdf", 2)
    txt = OUT / "note.txt"
    txt.write_text("First line\nSecond line with unicode: ə ğ ı ö ş ç\n", encoding="utf-8")
    md = OUT / "readme.md"
    md.write_text("# Title\n\nSome **bold** text.\n\n- one\n- two\n", encoding="utf-8")

    # --- image conversions and tools -----------------------------------------------------
    run_all("image", src_png, skip={"ocr"})
    for ext in (".heic", ".avif", ".webp", ".tiff", ".bmp"):
        produced = next(OUT.glob(f"sample*{ext}"), None)
        check(f"reopen {ext}", lambda p=produced: Image.open(p).size)
    check("image ocr", lambda: must("Tangerine" in ocr_text(ocr_path), "text not recognized"))
    check("crop", lambda: crop_image(img, (10, 10, 200, 100)).size)
    check("edit", lambda: adjust(img, 20, 10, -30, 10, 90, True, False).size)
    check("redact", lambda: [redact(img, [(50, 50, 120, 80)], s).size for s in ("Black box", "Blur", "Pixelate")])
    check("resize", lambda: must(resize_image(img, 320, 200).size == (320, 200)))
    check("fit_long_side", lambda: must(fit_long_side((4000, 3000), 1000) == (1000, 750)))
    for pos in POSITIONS:
        check(f"watermark {pos}", lambda p=pos: must(add_watermark(img, "© Tangerine", p, 6, 70, "Orange").size == img.size))
    check("watermark empty text", lambda: must(add_watermark(img, "  ").size == img.size))
    check("remove_bg", lambda: must(remove_background(plain).getpixel((5, 5))[3] == 0 and remove_background(plain).getpixel((300, 200))[3] > 200))
    for preset in PRESETS:
        check(f"add_bg {preset.name}", lambda p=preset: add_background(img, p, 10, 6, 40, (16, 9)).size)
    check("metadata", lambda: (len(read_metadata(src_png)), strip_metadata(src_png)[0].name))
    run_all("image", plain_path, skip={"ocr"} | {a.id for g in registry.groups_for("image", ".jpg") for a in g.actions if a.id.startswith("to_")})

    # --- PDF --------------------------------------------------------------------------------
    run_all("pdf", pdf_a, skip={"ocr"})
    check("pdf ocr", lambda: must(Path(registry_action("pdf", "ocr").handler(pdf_a)[0]).read_text("utf-8").strip() != ""))
    check("pdf merge", lambda: must(pymupdf.open(pdf_tools.merge_pdfs([pdf_a, pdf_b])[0]).page_count == 5))
    check("images to pdf", lambda: must(pymupdf.open(pdf_tools.images_to_pdf([src_png, plain_path, ocr_path])[0]).page_count == 3))
    protected = []
    check("pdf protect", lambda: protected.append(pdf_tools.protect_pdf(pdf_b, "s3cret")[0]) or must(pymupdf.open(protected[0]).needs_pass))
    check("pdf protected blocks convert", lambda: must(raises(lambda: registry_action("pdf", "to_txt").handler(protected[0]), ValueError)))
    check("pdf unlock wrong password", lambda: must(raises(lambda: pdf_tools.unlock_pdf(protected[0], "nope"), ValueError)))
    check("pdf unlock", lambda: must(not pymupdf.open(pdf_tools.unlock_pdf(protected[0], "s3cret")[0]).needs_pass))
    check("pdf redact", lambda: redact_check(pdf_a))
    check("pdf pages reorder/rotate", lambda: pages_check(pdf_a))

    # --- text, docx, archive ----------------------------------------------------------------
    run_all("text", txt)
    run_all("text", md)
    docx = next(OUT.glob("sample*.docx"))
    run_all("docx", docx)
    check("docx pdf has text", lambda: must("First line" in "".join(pg.get_text() for pg in pymupdf.open(registry_action("docx", "to_pdf").handler(OUT / "note.docx")[0]))))
    zipped = archive.zip_files([txt, md, OUT / "sub"]) if (OUT / "sub").mkdir() is None else None
    check("zip all", lambda: len(zipped))
    z1 = archive.zip_one(txt)[0]
    check("zip one", lambda: z1.name)
    check("extract", lambda: [p.name for p in archive.extract_zip(z1)])
    bad = OUT / "evil.zip"
    import zipfile

    with zipfile.ZipFile(bad, "w") as zf:
        zf.writestr("../escape.txt", "x")
    check("extract blocks traversal", lambda: must(raises(lambda: archive.extract_zip(bad), ValueError)))
    check("zip folder via registry", lambda: [p.name for p in registry_action("folder", "zip").handler(OUT / "sub")])

    # --- media ---------------------------------------------------------------------------------
    exe = media.ffmpeg_exe()
    check("ffmpeg", lambda: exe)
    clip, tone = OUT / "clip.mp4", OUT / "tone.wav"
    subprocess.run([exe, "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10", "-f", "lavfi", "-i", "sine=duration=2", "-shortest", str(clip)], capture_output=True)
    subprocess.run([exe, "-y", "-f", "lavfi", "-i", "sine=duration=2", str(tone)], capture_output=True)
    run_all("video", clip)
    run_all("audio", tone)
    check("duration", lambda: must(1.5 < media.duration_seconds(clip) < 2.6))
    check("trim copy", lambda: must(0.5 < media.duration_seconds(media.trim_media(clip, 0.5, 1.5)[0]) < 1.6))
    check("trim exact", lambda: must(0.7 < media.duration_seconds(media.trim_media(clip, 0.5, 1.5, True)[0]) < 1.3))
    gif = OUT / "anim.gif"
    check("gif compress", lambda: (subprocess.run([exe, "-y", "-i", str(clip), str(gif)], capture_output=True), registry_action("image", "compress").handler(gif)[0].name)[1])

    # --- cancellation -------------------------------------------------------------------------
    event = threading.Event()
    event.set()
    utils.set_cancel_event(event)
    check("cancel stops ffmpeg", lambda: must(raises(lambda: media.convert_media(clip, "WEBM", True), utils.Cancelled)))
    utils.set_cancel_event(None)

    # --- registry rules, settings, history ---------------------------------------------------------
    check("registry multi image", lambda: must(
        [g.name for g in registry.groups_for("image", ".png", 3)] == ["Convert", "Edit", "Utility", "Combine"] and
        not any(a.window for g in registry.groups_for("image", ".png", 3) for a in g.actions)))
    check("registry same format hidden", lambda: must("PNG" not in [a.label for a in registry.groups_for("image", ".png")[0].actions]))
    check("kinds", lambda: must([registry.kind_of(Path(n)) for n in ("a.JPG", "b.pdf", "c.docx", "d.md", "e.mkv", "f.flac", "g.zip", "h.xyz")] == ["image", "pdf", "docx", "text", "video", "audio", "archive", "other"]))
    settings.set("slices", {"pdf": {"hidden": ["to_docx"], "order": ["to_png", "to_jpg"]}})
    check("custom slices", lambda: must([a.id for a in registry.groups_for("pdf", ".pdf")[0].actions] == ["to_png", "to_jpg", "to_txt"]))
    settings.set("slices", {})
    check("quality setting", lambda: (settings.set("quality", 30), small := registry_action("image", "to_jpg").handler(src_png)[0].stat().st_size, settings.set("quality", 95), big := registry_action("image", "to_jpg").handler(src_png)[0].stat().st_size, must(small < big))[-1])
    history.add("Test", [txt, md])
    check("history", lambda: must({txt, md} <= {path for _, path in history.recent_outputs()}))
    victim = OUT / "victim.txt"
    victim.write_text("x")
    history.add("Test2", [victim])
    check("undo", lambda: must(history.undo_last() == [victim] and not victim.exists()))

    print("\nFAILED: " + ", ".join(failures) if failures else "\nAll backend checks passed")
    return 1 if failures else 0


def registry_action(kind: str, action_id: str):
    ext = {"image": ".png", "pdf": ".pdf", "docx": ".docx", "folder": "", "text": ".txt"}.get(kind, ".png")
    for group in registry.groups_for(kind, ext):
        for action in group.actions:
            if action.id == action_id:
                return action
    raise KeyError(action_id)


def ocr_text(path: Path) -> str:
    from tangerine.tools.ocr import ocr_image

    return ocr_image(Image.open(path))


def raises(fn, exc_type) -> bool:
    try:
        fn()
    except exc_type:
        return True
    return False


def redact_check(pdf: Path) -> str:
    out, count = pdf_tools.redact_pdf(pdf, ["Hello"], ["Email addresses"])
    text = "".join(p.get_text() for p in pymupdf.open(out[0]))
    must("Hello" not in text and "example.com" not in text, f"text still present: {text!r}")
    return f"{count} areas removed"


def pages_check(pdf: Path) -> str:
    out = pdf_tools.save_organized(pdf, [2, 0], {0: 90})[0]
    doc = pymupdf.open(out)
    must(doc.page_count == 2 and "page 3" in doc[0].get_text() and doc[1].rotation == 90)
    return out.name


if __name__ == "__main__":
    sys.exit(main())
