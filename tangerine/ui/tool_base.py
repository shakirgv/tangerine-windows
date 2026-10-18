"""Shared base class and helpers for tool windows."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel, QMessageBox, QSlider, QVBoxLayout, QWidget

from ..converters.image import open_image
from .theme import STYLE

PANEL_WIDTH = 240


class ToolWindow(QWidget):
    """Applies the theme, loads the source file and reports saved files.

    Subclasses set LOAD_IMAGE = False when the file is not an image (PDF, video, ...).
    """

    saved = Signal(object)  # Path of the file that was written
    TITLE = ""
    LOAD_IMAGE = True

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.setWindowTitle(f"{self.TITLE} - {self.path.name}")
        self.image = open_image(self.path) if self.LOAD_IMAGE else None
        self.status = QLabel("")
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)

    def side_panel(self) -> tuple[QWidget, QVBoxLayout]:
        panel = QWidget()
        panel.setFixedWidth(PANEL_WIDTH)
        layout = QVBoxLayout(panel)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)
        return panel, layout

    def report(self, out: Path | list[Path]) -> None:
        outs = out if isinstance(out, list) else [out]
        self.status.setText("Saved: " + ", ".join(Path(o).name for o in outs))
        for item in outs:
            self.saved.emit(Path(item))

    def fail(self, exc: Exception) -> None:
        QMessageBox.warning(self, "Tangerine", f"{type(exc).__name__}: {exc}")

    def show_front(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()


def caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    return label


def make_slider(lo: int, hi: int, value: int) -> QSlider:
    s = QSlider(Qt.Orientation.Horizontal)
    s.setRange(lo, hi)
    s.setValue(value)
    return s
