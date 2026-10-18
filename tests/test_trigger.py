"""Checks the trigger state machine and the menu's drag/drop handlers without touching the real mouse.
Run: python tests/test_trigger.py"""

from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from pynput import keyboard, mouse  # noqa: E402
from PySide6.QtCore import QMimeData, QPointF, Qt, QUrl  # noqa: E402
from PySide6.QtGui import QDragEnterEvent, QDropEvent  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tangerine.trigger import TriggerListener  # noqa: E402
from tangerine.ui.radial_menu import RadialMenu  # noqa: E402


def main() -> int:
    app = QApplication([])
    events: list[str] = []

    trig = TriggerListener("ctrl+shift")
    trig.triggered.connect(lambda: events.append("triggered"))
    trig.released.connect(lambda: events.append("released"))

    # Moving without the modifier does nothing.
    trig._on_click(100, 100, mouse.Button.left, True)
    trig._on_move(140, 100)
    assert events == [], events
    # Pressing the modifiers mid-drag fires once.
    trig._on_press(keyboard.Key.ctrl_l)
    assert events == [], events
    trig._on_press(keyboard.Key.shift)
    assert events == ["triggered"], events
    trig._on_move(180, 100)
    assert events == ["triggered"], events
    trig._on_click(180, 100, mouse.Button.left, False)
    assert events == ["triggered", "released"], events
    trig._on_release(keyboard.Key.ctrl_l)
    trig._on_release(keyboard.Key.shift)

    # Small movement below the threshold does not fire.
    events.clear()
    trig._on_press(keyboard.Key.ctrl_l)
    trig._on_press(keyboard.Key.shift)
    trig._on_click(10, 10, mouse.Button.left, True)
    trig._on_move(13, 12)
    assert events == [], events
    trig._on_move(40, 12)
    assert events == ["triggered"], events
    trig._on_click(40, 12, mouse.Button.left, False)
    app.processEvents()
    print("trigger state machine ok")

    # Menu drag/drop handlers with synthetic events.
    sample = ROOT / "tests" / "_out" / "sample.png"
    if not sample.exists():
        from PIL import Image

        sample.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (50, 50), "orange").save(sample)

    menu = RadialMenu()
    chosen: list = []
    menu.actionChosen.connect(lambda action, files: chosen.append((action.id, [f.name for f in files])))
    menu.open_for_drag(QPointF(500, 400))
    assert menu.isVisible()

    mime = QMimeData()
    mime.setUrls([QUrl.fromLocalFile(str(sample))])
    c = menu._center()
    enter = QDragEnterEvent(c.toPoint(), Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    menu.dragEnterEvent(enter)
    assert menu.files == [sample], menu.files
    assert [g.name for g in menu._groups] == ["Convert", "Edit", "Utility"]

    target = QPointF(c.x(), c.y() - 235)  # top slice of the outer ring
    drop = QDropEvent(target, Qt.DropAction.CopyAction, mime, Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    menu.dropEvent(drop)
    app.processEvents()
    assert chosen and chosen[0][1] == ["sample.png"], chosen
    assert not menu.isVisible()
    print("menu drop ok ->", chosen[0])

    # With no drag the overlay hides itself.
    menu.open_for_drag(QPointF(500, 400))
    menu._on_no_drag()
    assert not menu.isVisible()
    print("no-drag timeout ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
