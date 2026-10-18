"""UI smoke test: builds every window/menu and saves screenshots to tests/_out/ui.
Run: python tests/test_ui.py   (set QT_QPA_PLATFORM=windows for real fonts, default is offscreen)"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
OUT = ROOT / "tests" / "_out" / "ui"
os.environ["APPDATA"] = str(ROOT / "tests" / "_out" / "appdata")

import pymupdf  # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402
from PySide6.QtCore import QPointF, QRectF, Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tangerine import registry, settings  # noqa: E402
from tangerine.ui.drop_window import DropWindow  # noqa: E402
from tangerine.ui.progress import ProgressBox  # noqa: E402
from tangerine.ui.radial_menu import RadialMenu  # noqa: E402
from tangerine.ui.settings_dialog import SettingsDialog  # noqa: E402
from tangerine.ui.tool_windows import create_tool  # noqa: E402


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
    doc = pymupdf.open()
    for n in range(4):
        doc.new_page().insert_text((72, 100), f"Page {n + 1} secret@example.com", fontsize=20)
    doc.save(pdf)
    doc.close()

    clip = OUT / "clip.mp4"
    import subprocess

    from tangerine.converters.media import ffmpeg_exe

    subprocess.run([ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "testsrc=duration=2:size=160x120:rate=10", str(clip)], capture_output=True)

    # ---- radial menu: layout and hit testing for every kind ------------------------------------
    menu = RadialMenu()
    samples = {
        "image": [sample],
        "image_multi": [sample, sample],
        "pdf": [pdf],
        "video": [clip],
        "folder": [OUT],
        "empty": [],
    }
    for name, files in samples.items():
        menu.open_for_drag(QPointF(600, 500))
        menu.set_files(files)
        menu._scale = 1.0
        menu.grab().save(str(OUT / f"menu_{name}.png"))
        print("menu", name, [(g.name, len(g.actions)) for g in menu._groups])
    menu.set_files([sample])
    c = menu._center()
    assert menu._hit(QPointF(c.x(), c.y() - 235)) == (0, 0)
    assert menu._hit(c) is None
    # every slice of every ring is reachable at its label position
    import math

    for ring, group in enumerate(menu._groups):
        r_in, r_out = menu._ring_bounds(ring)
        step = 360 / len(group.actions)
        for i in range(len(group.actions)):
            ang = math.radians(90 - i * step)
            rm = (r_in + r_out) / 2
            assert menu._hit(QPointF(c.x() + rm * math.cos(ang), c.y() - rm * math.sin(ang))) == (ring, i), (ring, i)
    menu.dismiss()

    DropWindow().grab().save(str(OUT / "drop_window.png"))
    box = ProgressBox()
    box.start("Compress", 5)
    box.update_progress(2, "photo.jpg")
    box.grab().save(str(OUT / "progress.png"))
    box.finish()
    dialog = SettingsDialog()
    dialog.grab().save(str(OUT / "settings.png"))
    for index in range(dialog.kind.count()):  # slices tab fills for every kind
        dialog.kind.setCurrentIndex(index)
    dialog.close()

    # ---- tool windows: each one opens, renders and saves ---------------------------------------
    cases = {
        "crop": sample,
        "add_bg": sample,
        "edit": sample,
        "redact": sample,
        "metadata": sample,
        "resize": sample,
        "watermark": sample,
        "trim": clip,
        "pdf_pages": pdf,
        "pdf_protect": pdf,
        "pdf_unlock": pdf,
        "pdf_redact": pdf,
    }
    for name, path in cases.items():
        window = create_tool(name, path)
        window.show()
        app.processEvents()
        window.grab().save(str(OUT / f"tool_{name}.png"))
        if name == "crop":
            window.aspect.setCurrentText("16:9")
            sel = window.canvas.selection()
            assert abs(sel.width() / sel.height() - 16 / 9) < 0.01, sel
            window.width_box.setValue(400)
            sel = window.canvas.selection()
            assert round(sel.width()) == 400 and abs(sel.width() / sel.height() - 16 / 9) < 0.02, sel
            window.apply()
            assert "_cropped" in window.status.text(), window.status.text()
        elif name == "redact":
            window.canvas.rects.append(QRectF(50, 50, 200, 100))
            window.apply()
            assert "_redacted" in window.status.text()
        elif name == "add_bg":
            window.save()
            assert "_bg" in window.status.text()
        elif name == "edit":
            window.sliders["brightness"].setValue(30)
            window.save()
            assert "_edited" in window.status.text()
        elif name == "metadata":
            window.strip()
            assert "_clean" in window.status.text()
        elif name == "resize":
            window.preset.setCurrentText("50%")
            assert (window.width_box.value(), window.height_box.value()) == (400, 250)
            window.width_box.setValue(200)
            assert window.height_box.value() == 125
            window.save()
            assert "_resized" in window.status.text()
        elif name == "watermark":
            window.position.setCurrentText("Tiled")
            window.save()
            assert "_watermark" in window.status.text()
        elif name == "trim":
            window.start.setValue(0.5)
            window.end.setValue(1.5)
            window.save()
            assert "_trimmed" in window.status.text(), window.status.text()
        elif name == "pdf_pages":
            assert window.list.count() == 4
            window.list.item(1).setSelected(True)
            window._rotate(90)
            window._delete()
            assert window.list.count() == 3
            window.save()
            assert "_edited" in window.status.text()
        elif name == "pdf_protect":
            window.password.setText("pw123")
            window.run()
            assert "_protected" in window.status.text()
        elif name == "pdf_unlock":
            protected = next(OUT.glob("doc_protected*.pdf"))
            unlock = create_tool("pdf_unlock", protected)
            unlock.password.setText("pw123")
            unlock.run()
            assert "_unlocked" in unlock.status.text(), unlock.status.text()
            unlock.close()
        elif name == "pdf_redact":
            window.terms.setPlainText("Page")
            window.checks["Email addresses"].setChecked(True)
            window.run()
            assert "_redacted" in window.status.text()
        print("tool", name, "ok")
        window.close()
    print("UI smoke test passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
