"""Offscreen UI smoke test: builds every window/menu and saves screenshots to tests/_out/ui.
Run: python tests/test_ui.py"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import QPointF, QRectF  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tangerine import registry  # noqa: E402
from tangerine.ui.drop_window import DropWindow  # noqa: E402
from tangerine.ui.radial_menu import RadialMenu  # noqa: E402
from tangerine.ui.tool_windows import TOOLS, create_tool  # noqa: E402

OUT = ROOT / "tests" / "_out" / "ui"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    app = QApplication([])

    sample = OUT / "photo.jpg"
    img = Image.new("RGB", (800, 500), (250, 170, 60))
    d = ImageDraw.Draw(img)
    d.ellipse((120, 80, 520, 440), fill=(40, 120, 220))
    d.rectangle((540, 100, 760, 260), fill=(240, 240, 240))
    img.save(sample, exif=Image.Exif())

    pdf = OUT / "doc.pdf"
    import pymupdf

    doc = pymupdf.open()
    doc.new_page().insert_text((72, 100), "hi")
    doc.save(pdf)

    menu = RadialMenu()
    for name, files in (("image", [sample]), ("pdf", [pdf]), ("empty", [])):
        menu.open_for_drag(QPointF(400, 400))
        menu.set_files(files)
        menu._scale = 1.0
        menu.grab().save(str(OUT / f"menu_{name}.png"))
        print("menu", name, "groups:", [(g.name, len(g.actions)) for g in menu._groups])
    # hit-testing: top slice of the outer ring must be the first action
    menu.set_files([sample])
    c = menu._center()
    top = menu._hit(QPointF(c.x(), c.y() - 190))
    assert top == (0, 0), top
    second = menu._hit(QPointF(c.x() + 190 * 0.64, c.y() - 190 * 0.77))
    assert second == (0, 1), second
    assert menu._hit(c) is None
    menu.dismiss()

    drop = DropWindow()
    drop.grab().save(str(OUT / "drop_window.png"))

    for name in TOOLS:
        window = create_tool(name, sample)
        window.show()
        app.processEvents()
        window.grab().save(str(OUT / f"tool_{name}.png"))
        print("tool", name, "ok")
        if name == "crop":
            window.aspect.setCurrentText("16:9")
            sel = window.canvas.selection()
            assert abs(sel.width() / sel.height() - 16 / 9) < 0.01, sel
            window.width_box.setValue(400)
            sel = window.canvas.selection()
            assert round(sel.width()) == 400 and abs(sel.width() / sel.height() - 16 / 9) < 0.02, sel
            window.apply()
            assert "_cropped" in window.status.text(), window.status.text()
        if name == "redact":
            window.canvas.set_selection(None)
            window.canvas.rects.append(QRectF(50, 50, 200, 100))
            window.apply()
            assert "_redacted" in window.status.text()
        if name == "add_bg":
            window.save()
            assert "_bg" in window.status.text()
        if name == "edit":
            window.sliders["brightness"].setValue(30)
            window.save()
            assert "_edited" in window.status.text()
        if name == "metadata":
            window.strip()
            assert "_clean" in window.status.text()
        window.close()
    print("UI smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
