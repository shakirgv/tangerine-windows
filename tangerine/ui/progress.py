"""Small always-on-top progress box with a Cancel button for batch and long operations."""

from __future__ import annotations

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QPushButton, QVBoxLayout, QWidget

from .theme import STYLE

SHOW_DELAY_MS = 600


class ProgressBox(QWidget):
    cancelRequested = Signal()

    def __init__(self) -> None:
        super().__init__()
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.WindowStaysOnTopHint | Qt.WindowType.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setStyleSheet(STYLE)
        self.setFixedWidth(340)
        self.title = QLabel("")
        self.title.setObjectName("title")
        self.detail = QLabel("")
        self.detail.setObjectName("muted")
        self.bar = QProgressBar()
        self.bar.setTextVisible(False)
        self.bar.setFixedHeight(8)
        self.bar.setStyleSheet(
            "QProgressBar { background: #3a3a44; border: none; border-radius: 4px; }"
            "QProgressBar::chunk { background: #ff8a1f; border-radius: 4px; }"
        )
        self.cancel = QPushButton("Cancel")
        self.cancel.clicked.connect(self._on_cancel)

        layout = QVBoxLayout(self)
        layout.addWidget(self.title)
        layout.addWidget(self.detail)
        layout.addWidget(self.bar)
        row = QHBoxLayout()
        row.addStretch(1)
        row.addWidget(self.cancel)
        layout.addLayout(row)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._reveal)
        self._active = False

    def start(self, title: str, total: int) -> None:
        self._active = True
        self.title.setText(title)
        self.detail.setText("Starting...")
        self.cancel.setEnabled(True)
        self.bar.setRange(0, total if total > 1 else 0)  # 0..0 is the busy indicator
        self.bar.setValue(0)
        if total > 1:
            self._reveal()
        else:
            self._timer.start(SHOW_DELAY_MS)

    def update_progress(self, done: int, name: str) -> None:
        if self.bar.maximum() > 0:
            self.bar.setValue(done)
        self.detail.setText(name)

    def finish(self) -> None:
        self._active = False
        self._timer.stop()
        self.hide()

    def _reveal(self) -> None:
        if not self._active:
            return
        screen = QGuiApplication.primaryScreen().availableGeometry()
        self.adjustSize()
        self.move(screen.right() - self.width() - 20, screen.bottom() - self.height() - 20)
        self.show()

    def _on_cancel(self) -> None:
        self.cancel.setEnabled(False)
        self.detail.setText("Cancelling...")
        self.cancelRequested.emit()
