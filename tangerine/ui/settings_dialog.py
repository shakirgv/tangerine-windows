"""Settings dialog: trigger, output folder, quality, startup and which slices appear."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTabWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from .. import autostart, registry, settings
from .theme import STYLE


class SettingsDialog(QDialog):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Tangerine settings")
        self.setStyleSheet(STYLE)
        self.resize(520, 520)

        tabs = QTabWidget()
        tabs.addTab(self._general_tab(), "General")
        tabs.addTab(self._quality_tab(), "Quality")
        tabs.addTab(self._slices_tab(), "Slices")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self._apply)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.addWidget(tabs)
        layout.addWidget(buttons)

    # ---- tabs -------------------------------------------------------------------------------

    def _general_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.trigger = QComboBox()
        for key, text in settings.TRIGGERS.items():
            self.trigger.addItem(text, key)
        self.trigger.setCurrentIndex(max(0, self.trigger.findData(settings.get("trigger"))))
        form.addRow("Trigger key", self.trigger)

        self.output = QLineEdit(settings.get("output_dir"))
        self.output.setPlaceholderText("Next to the original file")
        browse = QPushButton("Browse...")
        browse.clicked.connect(self._browse)
        row = QHBoxLayout()
        row.addWidget(self.output, 1)
        row.addWidget(browse)
        form.addRow("Output folder", row)

        self.delete_original = QCheckBox("Move the original to the Recycle Bin after a successful conversion")
        self.delete_original.setChecked(bool(settings.get("delete_original")))
        form.addRow(self.delete_original)

        self.autostart = QCheckBox("Start Tangerine when Windows starts")
        self.autostart.setChecked(autostart.is_enabled())
        form.addRow(self.autostart)
        return page

    def _quality_tab(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.quality = QSpinBox()
        self.quality.setRange(1, 100)
        self.quality.setValue(int(settings.get("quality")))
        form.addRow("JPG / WEBP / HEIC / AVIF quality", self.quality)
        self.compress_quality = QSpinBox()
        self.compress_quality.setRange(1, 100)
        self.compress_quality.setValue(int(settings.get("compress_quality")))
        form.addRow("Compress quality", self.compress_quality)
        self.pdf_dpi = QSpinBox()
        self.pdf_dpi.setRange(50, 600)
        self.pdf_dpi.setSingleStep(25)
        self.pdf_dpi.setSuffix(" dpi")
        self.pdf_dpi.setValue(int(settings.get("pdf_dpi")))
        form.addRow("PDF to image resolution", self.pdf_dpi)
        return page

    def _slices_tab(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        hint = QLabel("Untick a slice to hide it. Drag slices to change their order inside a ring.")
        hint.setObjectName("muted")
        hint.setWordWrap(True)
        self.kind = QComboBox()
        for kind, label in registry.KIND_LABELS.items():
            self.kind.addItem(label, kind)
        self.tree = QTreeWidget()
        self.tree.setHeaderHidden(True)
        self.tree.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        reset = QPushButton("Show all and reset order")
        reset.clicked.connect(self._reset_slices)
        layout.addWidget(hint)
        layout.addWidget(self.kind)
        layout.addWidget(self.tree, 1)
        layout.addWidget(reset)

        # Working copy of the preferences, edited while the dialog is open.
        self._slices = {k: dict(v) for k, v in (settings.get("slices") or {}).items()}
        self._current_kind = self.kind.currentData()
        self.kind.currentIndexChanged.connect(self._switch_kind)
        self._fill_tree(self._current_kind)
        return page

    # ---- slices tree ------------------------------------------------------------------------

    def _fill_tree(self, kind: str) -> None:
        prefs = self._slices.get(kind, {})
        hidden, order = set(prefs.get("hidden", [])), prefs.get("order", [])
        self.tree.clear()
        for group in registry.all_groups(kind):
            parent = QTreeWidgetItem([group.name])
            parent.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDropEnabled)
            self.tree.addTopLevelItem(parent)
            actions = sorted(group.actions, key=lambda a: order.index(a.id) if a.id in order else len(order))
            for action in actions:
                item = QTreeWidgetItem([action.label])
                item.setData(0, Qt.ItemDataRole.UserRole, action.id)
                item.setFlags(
                    Qt.ItemFlag.ItemIsEnabled
                    | Qt.ItemFlag.ItemIsUserCheckable
                    | Qt.ItemFlag.ItemIsDragEnabled
                    | Qt.ItemFlag.ItemNeverHasChildren
                )
                item.setCheckState(0, Qt.CheckState.Unchecked if action.id in hidden else Qt.CheckState.Checked)
                parent.addChild(item)
            parent.setExpanded(True)

    def _collect_tree(self) -> dict:
        hidden, order = [], []
        for i in range(self.tree.topLevelItemCount()):
            parent = self.tree.topLevelItem(i)
            for j in range(parent.childCount()):
                item = parent.child(j)
                action_id = item.data(0, Qt.ItemDataRole.UserRole)
                order.append(action_id)
                if item.checkState(0) == Qt.CheckState.Unchecked:
                    hidden.append(action_id)
        return {"hidden": hidden, "order": order}

    def _switch_kind(self) -> None:
        self._slices[self._current_kind] = self._collect_tree()
        self._current_kind = self.kind.currentData()
        self._fill_tree(self._current_kind)

    def _reset_slices(self) -> None:
        self._slices.pop(self._current_kind, None)
        self._fill_tree(self._current_kind)

    # ---- actions ----------------------------------------------------------------------------

    def _browse(self) -> None:
        folder = QFileDialog.getExistingDirectory(self, "Output folder", self.output.text() or str(Path.home()))
        if folder:
            self.output.setText(folder)

    def _apply(self) -> None:
        self._slices[self._current_kind] = self._collect_tree()
        # A kind whose list is untouched is stored as nothing, so new actions added later still show.
        cleaned = {}
        for kind, prefs in self._slices.items():
            defaults = [a.id for g in registry.all_groups(kind) for a in g.actions]
            if prefs.get("hidden") or prefs.get("order") not in ([], defaults, None):
                cleaned[kind] = prefs
        settings.set("slices", cleaned)
        settings.set("trigger", self.trigger.currentData())
        settings.set("output_dir", self.output.text().strip())
        settings.set("delete_original", self.delete_original.isChecked())
        settings.set("quality", self.quality.value())
        settings.set("compress_quality", self.compress_quality.value())
        settings.set("pdf_dpi", self.pdf_dpi.value())
        try:
            autostart.set_enabled(self.autostart.isChecked())
        except OSError:
            pass
        self.accept()
