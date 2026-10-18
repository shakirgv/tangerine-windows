"""Simple drop window: the manual way to open the radial menu, and a place to see dropped paths."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, Qt, Signal
from PySide6.QtGui import QColor, QCursor, QPainter, QPen
from PySide6.QtWidgets import QLabel, QListWidget, QVBoxLayout, QWidget

from .theme import MUTED, ORANGE, STYLE


class DropWindow(QWidget):
    filesDropped = Signal(list, QPointF)  # list[Path], global drop position

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Tangerine")
        self.setAcceptDrops(True)
        self.setStyleSheet(STYLE)
        self.resize(380, 300)
        self._hovering = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 20)
        self._hint = QLabel("Drop files here\nthen pick a slice")
        self._hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._hint.setStyleSheet(f"color: {MUTED}; font-size: 16px; background: transparent;")
        self._list = QListWidget()
        self._list.setVisible(False)
        self._tip = QLabel("Or hold the trigger key and drag a file anywhere.")
        self._tip.setObjectName("muted")
        self._tip.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._hint, 1)
        layout.addWidget(self._list, 1)
        layout.addWidget(self._tip)

    def set_trigger_text(self, text: str) -> None:
        self._tip.setText(f"Or hold {text} and drag a file anywhere.")

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        pen = QPen(QColor(ORANGE if self._hovering else "#4a4a56"), 2, Qt.PenStyle.DashLine)
        p.setPen(pen)
        p.drawRoundedRect(self.rect().adjusted(10, 10, -10, -10), 14, 14)

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            self._hovering = True
            self.update()
            event.acceptProposedAction()

    def dragLeaveEvent(self, event) -> None:
        self._hovering = False
        self.update()

    def dropEvent(self, event) -> None:
        self._hovering = False
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        self.update()
        if not paths:
            return
        for path in paths:
            print(path, flush=True)  # roadmap step 1: print dropped file paths
        self._hint.setVisible(False)
        self._list.setVisible(True)
        self._list.clear()
        self._list.addItems([str(p) for p in paths])
        event.acceptProposedAction()
        self.filesDropped.emit(paths, QPointF(QCursor.pos()))

    def closeEvent(self, event) -> None:
        # Closing hides to the tray instead of quitting.
        event.ignore()
        self.hide()
