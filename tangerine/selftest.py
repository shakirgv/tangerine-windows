"""`Tangerine.exe --selftest result.txt`: exercises the bundled libraries and writes OK or the errors.

Used to verify a PyInstaller build, where dynamically imported modules and binaries can go missing.
"""

from __future__ import annotations

import importlib
import pkgutil
import tempfile
import traceback
from pathlib import Path


def _checks(tmp: Path) -> list[tuple[str, callable]]:
    import pymupdf
    from PIL import Image, ImageDraw, ImageFont

    from . import registry

    def all_modules():
        import tangerine

        names = [m.name for m in pkgutil.walk_packages(tangerine.__path__, "tangerine.") if not m.name.endswith(".main")]
        for name in names:
            importlib.import_module(name)
        return len(names)

    def image_formats():
        from .converters.image import convert_image

        src = tmp / "t.png"
        Image.new("RGB", (64, 64), "orange").save(src)
        return [convert_image(src, f).name for f in ("JPG", "WEBP", "HEIC", "AVIF", "TIFF", "BMP", "PDF", "DOCX")]

    def pdf_things():
        from .converters.pdf import pdf_to_docx, pdf_to_images, pdf_to_txt
        from .tools import pdf_tools

        pdf = tmp / "t.pdf"
        doc = pymupdf.open()
        doc.new_page().insert_text((72, 100), "hello selftest")
        doc.save(pdf)
        out = [pdf_to_images(pdf, "PNG")[0].name, pdf_to_txt(pdf)[0].name, pdf_to_docx(pdf)[0].name]
        out += [pdf_tools.compress_pdf(pdf)[0].name, pdf_tools.protect_pdf(pdf, "x")[0].name]
        return out

    def text_pdf():
        from .converters.text import text_to_pdf

        src = tmp / "t.md"
        src.write_text("# hi\n\ntext", encoding="utf-8")
        return text_to_pdf(src)[0].name

    def ocr():
        from .tools.ocr import ocr_image

        img = Image.new("RGB", (600, 120), "white")
        ImageDraw.Draw(img).text((10, 30), "Selftest", fill="black", font=ImageFont.truetype(r"C:\Windows\Fonts\arial.ttf", 44))
        text = ocr_image(img)
        if "Selftest" not in text:
            raise RuntimeError(f"unexpected OCR text {text!r}")
        return text

    def ffmpeg():
        from .converters.media import ffmpeg_exe

        exe = ffmpeg_exe()
        if not exe or not Path(exe).exists():
            raise RuntimeError("ffmpeg missing")
        return exe

    def tools_run():
        from .tools.add_bg import PRESETS, add_background
        from .tools.remove_bg import remove_background
        from .tools.watermark import add_watermark

        img = Image.new("RGB", (200, 120), "white")
        add_background(img, PRESETS[0])
        remove_background(img)
        add_watermark(img, "x")
        return "ok"

    def registry_all():
        return sum(len(g.actions) for kind in registry.KIND_LABELS for g in registry.all_groups(kind))

    def qt_gui():
        from PySide6.QtWidgets import QApplication

        from .ui.radial_menu import RadialMenu
        from .ui.tool_windows import create_tool

        app = QApplication.instance() or QApplication([])
        menu = RadialMenu()
        menu.set_files([tmp / "t.png"])
        menu.grab()
        window = create_tool("crop", tmp / "t.png")
        window.grab()
        window.close()
        return "ok"

    return [
        ("all modules import", all_modules),
        ("registry", registry_all),
        ("image formats", image_formats),
        ("pdf", pdf_things),
        ("text to pdf", text_pdf),
        ("ocr", ocr),
        ("ffmpeg", ffmpeg),
        ("tools", tools_run),
        ("qt gui", qt_gui),
    ]


def run(result_file: str) -> int:
    lines, failed = [], False
    with tempfile.TemporaryDirectory() as folder:
        tmp = Path(folder)
        for name, fn in _checks(tmp):
            try:
                lines.append(f"ok    {name}: {fn()}")
            except Exception:  # noqa: BLE001
                failed = True
                lines.append(f"FAIL  {name}\n{traceback.format_exc()}")
    lines.append("SELFTEST FAILED" if failed else "SELFTEST OK")
    Path(result_file).write_text("\n".join(lines), encoding="utf-8")
    return 1 if failed else 0
