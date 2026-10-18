"""Trim window for video and audio."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QCheckBox, QDoubleSpinBox, QHBoxLayout, QLabel, QPushButton, QVBoxLayout

from ..converters.media import duration_seconds, trim_media
from .tool_base import ToolWindow, caption


def _fmt(seconds: float) -> str:
    m, s = divmod(seconds, 60)
    h, m = divmod(int(m), 60)
    return f"{h}:{m:02d}:{s:05.2f}"


class TrimWindow(ToolWindow):
    TITLE = "Trim"
    LOAD_IMAGE = False

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(420, 300)
        self.duration = duration_seconds(self.path)
        limit = self.duration or 86400.0

        self.start = QDoubleSpinBox()
        self.end = QDoubleSpinBox()
        for box in (self.start, self.end):
            box.setRange(0, limit)
            box.setDecimals(2)
            box.setSuffix(" s")
        self.end.setValue(limit if self.duration else 10.0)
        self.exact = QCheckBox("Exact cut (re-encode, slower)")
        self.length = caption("")
        save = QPushButton("Save trimmed copy")
        save.setObjectName("primary")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel(f"Duration: {_fmt(self.duration)}" if self.duration else "Duration: unknown"))
        row = QHBoxLayout()
        for label, box in (("Start", self.start), ("End", self.end)):
            col = QVBoxLayout()
            col.addWidget(caption(label))
            col.addWidget(box)
            row.addLayout(col)
        layout.addLayout(row)
        layout.addWidget(self.exact)
        layout.addWidget(self.length)
        layout.addStretch(1)
        layout.addWidget(self.status)
        layout.addWidget(save)

        self.start.valueChanged.connect(self._update_length)
        self.end.valueChanged.connect(self._update_length)
        save.clicked.connect(self.save)
        self._update_length()

    def _update_length(self) -> None:
        self.length.setText(f"Length: {max(0.0, self.end.value() - self.start.value()):.2f} s")

    def save(self) -> None:
        try:
            self.status.setText("Working...")
            out = trim_media(self.path, self.start.value(), self.end.value(), self.exact.isChecked())
        except Exception as exc:  # noqa: BLE001
            self.status.setText("")
            self.fail(exc)
            return
        self.report(out)
