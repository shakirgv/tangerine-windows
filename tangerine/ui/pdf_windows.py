"""PDF tool windows: organize pages, protect, unlock and redact."""

from __future__ import annotations

from pathlib import Path

import pymupdf
from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QIcon, QImage, QPixmap, QTransform
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QListWidgetItem,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
)

from ..tools import pdf_tools
from .tool_base import ToolWindow, caption

THUMB = QSize(130, 170)


class PdfPagesWindow(ToolWindow):
    """Thumbnails you can drag to reorder, rotate, delete and extract."""

    TITLE = "Pages"
    LOAD_IMAGE = False

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(860, 620)
        self._rotations: dict[int, int] = {}
        self._thumbs: dict[int, QPixmap] = {}

        self.list = QListWidget()
        self.list.setViewMode(QListView.ViewMode.IconMode)
        self.list.setIconSize(THUMB)
        self.list.setResizeMode(QListView.ResizeMode.Adjust)
        self.list.setMovement(QListView.Movement.Snap)
        self.list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.list.setSpacing(8)
        self.list.setGridSize(QSize(THUMB.width() + 24, THUMB.height() + 40))

        self._load_thumbnails()

        left = QPushButton("Rotate left")
        right = QPushButton("Rotate right")
        delete = QPushButton("Delete selected")
        extract = QPushButton("Extract selected")
        save = QPushButton("Save")
        save.setObjectName("primary")

        panel, col = self.side_panel()
        col.addWidget(QLabel("Pages"))
        hint = caption("Drag pages to reorder. Select several with Ctrl or Shift.")
        hint.setWordWrap(True)
        col.addWidget(hint)
        col.addWidget(left)
        col.addWidget(right)
        col.addWidget(delete)
        col.addWidget(extract)
        col.addStretch(1)
        col.addWidget(self.status)
        col.addWidget(save)

        layout = QHBoxLayout(self)
        layout.addWidget(self.list, 1)
        layout.addWidget(panel)

        left.clicked.connect(lambda: self._rotate(-90))
        right.clicked.connect(lambda: self._rotate(90))
        delete.clicked.connect(self._delete)
        extract.clicked.connect(self._extract)
        save.clicked.connect(self.save)

    def _load_thumbnails(self) -> None:
        from ..converters.pdf import open_pdf

        with open_pdf(self.path) as doc:
            for index, page in enumerate(doc):
                pix = page.get_pixmap(dpi=40, alpha=False)
                qimg = QImage(pix.samples, pix.width, pix.height, pix.stride, QImage.Format.Format_RGB888).copy()
                self._thumbs[index] = QPixmap.fromImage(qimg)
                item = QListWidgetItem(f"Page {index + 1}")
                item.setData(Qt.ItemDataRole.UserRole, index)
                item.setTextAlignment(Qt.AlignmentFlag.AlignHCenter)
                self.list.addItem(item)
                self._refresh_icon(item)

    def _refresh_icon(self, item: QListWidgetItem) -> None:
        index = item.data(Qt.ItemDataRole.UserRole)
        pix = self._thumbs[index]
        turn = self._rotations.get(index, 0)
        if turn:
            pix = pix.transformed(QTransform().rotate(turn), Qt.TransformationMode.SmoothTransformation)
        item.setIcon(QIcon(pix.scaled(THUMB, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)))

    def _rotate(self, degrees: int) -> None:
        for item in self.list.selectedItems():
            index = item.data(Qt.ItemDataRole.UserRole)
            self._rotations[index] = (self._rotations.get(index, 0) + degrees) % 360
            self._refresh_icon(item)

    def _delete(self) -> None:
        for item in self.list.selectedItems():
            self.list.takeItem(self.list.row(item))

    def _order(self, selected_only: bool = False) -> list[int]:
        items = [self.list.item(i) for i in range(self.list.count())]
        if selected_only:
            items = [it for it in items if it.isSelected()]
        return [it.data(Qt.ItemDataRole.UserRole) for it in items]

    def _extract(self) -> None:
        order = self._order(selected_only=True)
        if not order:
            self.status.setText("Select pages first.")
            return
        self._write(order, "_extract")

    def save(self) -> None:
        self._write(self._order(), "_edited")

    def _write(self, order: list[int], tag: str) -> None:
        try:
            out = pdf_tools.save_organized(self.path, order, self._rotations, tag)
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(out)


class _PasswordWindow(ToolWindow):
    LOAD_IMAGE = False
    ACTION = "Run"

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(380, 220)
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("Password")
        self.password.returnPressed.connect(self.run)
        go = QPushButton(self.ACTION)
        go.setObjectName("primary")
        go.clicked.connect(self.run)
        layout = QVBoxLayout(self)
        layout.addWidget(caption(self.HINT))
        layout.addWidget(self.password)
        layout.addStretch(1)
        layout.addWidget(self.status)
        layout.addWidget(go)

    HINT = ""

    def run(self) -> None:
        try:
            out = self.work(self.path, self.password.text())
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(out)

    def work(self, path: Path, password: str) -> list[Path]:
        raise NotImplementedError


class PdfProtectWindow(_PasswordWindow):
    TITLE = "Protect"
    ACTION = "Save protected copy"
    HINT = "Choose a password. Keep it safe: it cannot be recovered."

    def work(self, path: Path, password: str) -> list[Path]:
        return pdf_tools.protect_pdf(path, password)


class PdfUnlockWindow(_PasswordWindow):
    TITLE = "Unlock"
    ACTION = "Save unlocked copy"
    HINT = "Enter the password of this PDF."

    def work(self, path: Path, password: str) -> list[Path]:
        return pdf_tools.unlock_pdf(path, password)


class PdfRedactWindow(ToolWindow):
    TITLE = "Redact"
    LOAD_IMAGE = False

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(460, 460)
        self.terms = QPlainTextEdit()
        self.terms.setPlaceholderText("One word or phrase per line")
        self.checks = {name: QCheckBox(name) for name in pdf_tools.PATTERNS}
        go = QPushButton("Remove text permanently")
        go.setObjectName("primary")
        go.clicked.connect(self.run)

        layout = QVBoxLayout(self)
        layout.addWidget(caption("Text to remove from every page"))
        layout.addWidget(self.terms, 1)
        layout.addWidget(caption("Also remove"))
        for box in self.checks.values():
            layout.addWidget(box)
        layout.addWidget(self.status)
        layout.addWidget(go)

    def run(self) -> None:
        patterns = [name for name, box in self.checks.items() if box.isChecked()]
        try:
            out, count = pdf_tools.redact_pdf(self.path, self.terms.toPlainText().splitlines(), patterns)
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(out)
        self.status.setText(self.status.text() + f"  ({count} areas removed)")


TOOLS = {
    "pdf_pages": PdfPagesWindow,
    "pdf_protect": PdfProtectWindow,
    "pdf_unlock": PdfUnlockWindow,
    "pdf_redact": PdfRedactWindow,
}
