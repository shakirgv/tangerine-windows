"""Small tool windows: Crop, Add BG, Edit, Redact and Metadata."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QSlider,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..converters.image import open_image, save_image
from ..tools import metadata as metadata_tool
from ..tools.add_bg import PRESETS, RATIOS, add_background
from ..tools.crop import ASPECTS, crop_image
from ..tools.edit import adjust
from ..tools.redact import STYLES, redact
from ..utils import output_path
from .image_canvas import ImageCanvas
from .theme import ORANGE, STYLE, pil_to_pixmap

PANEL_WIDTH = 240


class ToolWindow(QWidget):
    """Base class: loads the image, applies the theme and reports saved files."""

    saved = Signal(object)  # Path of the file that was written
    TITLE = ""

    def __init__(self, path: Path) -> None:
        super().__init__()
        self.path = Path(path)
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.setStyleSheet(STYLE)
        self.setWindowTitle(f"{self.TITLE} - {self.path.name}")
        self.image = open_image(self.path)
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

    def report(self, out: Path) -> None:
        self.status.setText(f"Saved: {out.name}")
        self.saved.emit(out)

    def fail(self, exc: Exception) -> None:
        QMessageBox.warning(self, "Tangerine", f"{type(exc).__name__}: {exc}")

    def show_front(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()


def _caption(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("muted")
    return label


def _slider(lo: int, hi: int, value: int) -> QSlider:
    slider = QSlider(Qt.Orientation.Horizontal)
    slider.setRange(lo, hi)
    slider.setValue(value)
    return slider


# ---------------------------------------------------------------------------------------------
# Crop
# ---------------------------------------------------------------------------------------------


class CropWindow(ToolWindow):
    TITLE = "Crop"

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(900, 600)
        self.canvas = ImageCanvas(self.image, "single")
        iw, ih = self.image.size

        self.aspect = QComboBox()
        self.aspect.addItems(list(ASPECTS))
        self.width_box = QSpinBox()
        self.height_box = QSpinBox()
        for box, limit in ((self.width_box, iw), (self.height_box, ih)):
            box.setRange(1, limit)
            box.setSuffix(" px")
        reset = QPushButton("Reset")
        apply = QPushButton("Apply")
        apply.setObjectName("primary")

        panel, col = self.side_panel()
        col.addWidget(QLabel("Crop"))
        col.addWidget(_caption("Aspect ratio"))
        col.addWidget(self.aspect)
        col.addWidget(_caption("Size"))
        row = QHBoxLayout()
        row.addWidget(self.width_box)
        row.addWidget(QLabel("x"))
        row.addWidget(self.height_box)
        col.addLayout(row)
        col.addStretch(1)
        col.addWidget(self.status)
        buttons = QHBoxLayout()
        buttons.addWidget(reset)
        buttons.addWidget(apply)
        col.addLayout(buttons)

        layout = QHBoxLayout(self)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(panel)

        self._syncing = False
        self.canvas.selectionChanged.connect(self._sync_fields)
        self.aspect.currentTextChanged.connect(lambda name: self.canvas.set_aspect(ASPECTS[name]))
        self.width_box.valueChanged.connect(lambda v: self._on_size(width=v))
        self.height_box.valueChanged.connect(lambda v: self._on_size(height=v))
        reset.clicked.connect(self.reset)
        apply.clicked.connect(self.apply)
        self.reset()

    def reset(self) -> None:
        self.aspect.setCurrentText("Free")
        self.canvas.set_aspect(None)
        self.canvas.select_all()
        self.status.setText("")

    def _sync_fields(self) -> None:
        sel = self.canvas.selection()
        self._syncing = True
        self.width_box.setValue(round(sel.width()) if sel else 1)
        self.height_box.setValue(round(sel.height()) if sel else 1)
        self._syncing = False

    def _on_size(self, width: int | None = None, height: int | None = None) -> None:
        if not self._syncing:
            self.canvas.set_selection_size(width, height)

    def apply(self) -> None:
        sel = self.canvas.selection()
        if sel is None:
            QMessageBox.information(self, "Crop", "Draw a crop area first.")
            return
        try:
            result = crop_image(self.image, (sel.x(), sel.y(), sel.width(), sel.height()))
            dest = output_path(self.path, self.path.suffix, "_cropped")
            save_image(result, dest)
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(dest)


# ---------------------------------------------------------------------------------------------
# Add BG
# ---------------------------------------------------------------------------------------------


class AddBgWindow(ToolWindow):
    TITLE = "Add Background"
    DEFAULTS = {"padding": 10, "corners": 5, "shadow": 40}

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(940, 640)
        self.preview_src = self.image.copy()
        self.preview_src.thumbnail((720, 720))
        self.bg = PRESETS[0]

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(480, 400)
        self.preview.setStyleSheet("background: #141418; border-radius: 8px;")

        panel, col = self.side_panel()
        col.addWidget(QLabel("Background"))
        grid = QGridLayout()
        grid.setSpacing(6)
        self.swatches = QButtonGroup(self)
        for i, preset in enumerate(PRESETS):
            button = QPushButton("" if preset.kind != "transparent" else "None")
            button.setCheckable(True)
            button.setFixedSize(40, 30)
            button.setToolTip(preset.name)
            button.setStyleSheet(self._swatch_style(preset))
            self.swatches.addButton(button, i)
            grid.addWidget(button, i // 5, i % 5)
        self.swatches.button(0).setChecked(True)
        col.addLayout(grid)

        self.padding = _slider(0, 40, self.DEFAULTS["padding"])
        self.corners = _slider(0, 25, self.DEFAULTS["corners"])
        self.shadow = _slider(0, 100, self.DEFAULTS["shadow"])
        for name, slider in (("Padding", self.padding), ("Corners", self.corners), ("Shadow", self.shadow)):
            col.addWidget(_caption(name))
            col.addWidget(slider)
        self.ratio = QComboBox()
        self.ratio.addItems(list(RATIOS))
        col.addWidget(_caption("Ratio"))
        col.addWidget(self.ratio)
        col.addStretch(1)
        col.addWidget(self.status)
        reset = QPushButton("Reset")
        save = QPushButton("Save with Background")
        save.setObjectName("primary")
        col.addWidget(reset)
        col.addWidget(save)

        layout = QHBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addWidget(panel)

        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(40)
        self._timer.timeout.connect(self._render)
        self.swatches.idClicked.connect(self._pick)
        for control in (self.padding, self.corners, self.shadow):
            control.valueChanged.connect(self._schedule)
        self.ratio.currentIndexChanged.connect(self._schedule)
        reset.clicked.connect(self.reset)
        save.clicked.connect(self.save)
        self._render()

    @staticmethod
    def _swatch_style(preset) -> str:
        if preset.kind == "transparent":
            fill = "#2c2c34"
        elif preset.kind == "solid":
            fill = "rgb(%d,%d,%d)" % preset.c1
        else:
            fill = "qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 rgb(%d,%d,%d),stop:1 rgb(%d,%d,%d))" % (*preset.c1, *preset.c2)
        return (
            f"QPushButton {{ background: {fill}; border: 2px solid #3a3a44; border-radius: 6px; color: #9a9aa6; font-size: 10px; padding: 0; }}"
            f"QPushButton:checked {{ border-color: {ORANGE}; }}"
        )

    def _pick(self, index: int) -> None:
        self.bg = PRESETS[index]
        self._schedule()

    def _schedule(self) -> None:
        self._timer.start()

    def _compose(self, source: Image.Image) -> Image.Image:
        return add_background(
            source,
            self.bg,
            padding=self.padding.value(),
            corners=self.corners.value(),
            shadow=self.shadow.value(),
            ratio=RATIOS[self.ratio.currentText()],
        )

    def _render(self) -> None:
        pix = pil_to_pixmap(self._compose(self.preview_src))
        self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "_timer"):
            self._schedule()

    def reset(self) -> None:
        self.swatches.button(0).setChecked(True)
        self.bg = PRESETS[0]
        self.padding.setValue(self.DEFAULTS["padding"])
        self.corners.setValue(self.DEFAULTS["corners"])
        self.shadow.setValue(self.DEFAULTS["shadow"])
        self.ratio.setCurrentIndex(0)
        self._render()

    def save(self) -> None:
        try:
            result = self._compose(self.image)
            keep_jpg = self.bg.kind != "transparent" and self.path.suffix.lower() in (".jpg", ".jpeg")
            dest = output_path(self.path, ".jpg" if keep_jpg else ".png", "_bg")
            save_image(result, dest)
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(dest)


# ---------------------------------------------------------------------------------------------
# Edit
# ---------------------------------------------------------------------------------------------


class EditWindow(ToolWindow):
    TITLE = "Edit"

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(900, 620)
        self.preview_src = self.image.copy()
        self.preview_src.thumbnail((900, 900))
        self.rotation = 0
        self.flip_h = False
        self.flip_v = False

        self.preview = QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumSize(480, 400)
        self.preview.setStyleSheet("background: #141418; border-radius: 8px;")

        panel, col = self.side_panel()
        col.addWidget(QLabel("Adjust"))
        self.sliders: dict[str, QSlider] = {}
        for name in ("Brightness", "Contrast", "Saturation", "Sharpness"):
            slider = _slider(-100, 100, 0)
            self.sliders[name.lower()] = slider
            col.addWidget(_caption(name))
            col.addWidget(slider)
            slider.valueChanged.connect(self._render)
        row = QHBoxLayout()
        for text, handler in (("⟲", lambda: self._turn(-90)), ("⟳", lambda: self._turn(90)), ("⇋", self._flip_h), ("⇅", self._flip_v)):
            button = QPushButton(text)
            button.clicked.connect(handler)
            row.addWidget(button)
        col.addLayout(row)
        col.addStretch(1)
        col.addWidget(self.status)
        reset = QPushButton("Reset")
        save = QPushButton("Save")
        save.setObjectName("primary")
        buttons = QHBoxLayout()
        buttons.addWidget(reset)
        buttons.addWidget(save)
        col.addLayout(buttons)

        layout = QHBoxLayout(self)
        layout.addWidget(self.preview, 1)
        layout.addWidget(panel)
        reset.clicked.connect(self.reset)
        save.clicked.connect(self.save)
        self._render()

    def _params(self) -> dict:
        values = {name: slider.value() for name, slider in self.sliders.items()}
        return {**values, "rotation": self.rotation, "flip_h": self.flip_h, "flip_v": self.flip_v}

    def _turn(self, degrees: int) -> None:
        self.rotation = (self.rotation + degrees) % 360
        self._render()

    def _flip_h(self) -> None:
        self.flip_h = not self.flip_h
        self._render()

    def _flip_v(self) -> None:
        self.flip_v = not self.flip_v
        self._render()

    def _render(self) -> None:
        pix = pil_to_pixmap(adjust(self.preview_src, **self._params()))
        self.preview.setPixmap(pix.scaled(self.preview.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "sliders"):
            self._render()

    def reset(self) -> None:
        for slider in self.sliders.values():
            slider.blockSignals(True)
            slider.setValue(0)
            slider.blockSignals(False)
        self.rotation, self.flip_h, self.flip_v = 0, False, False
        self._render()

    def save(self) -> None:
        try:
            dest = output_path(self.path, self.path.suffix, "_edited")
            save_image(adjust(self.image, **self._params()), dest)
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(dest)


# ---------------------------------------------------------------------------------------------
# Redact
# ---------------------------------------------------------------------------------------------


class RedactWindow(ToolWindow):
    TITLE = "Redact"

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(900, 600)
        self.canvas = ImageCanvas(self.image, "multi")
        self.style_box = QComboBox()
        self.style_box.addItems(STYLES)
        undo = QPushButton("Undo")
        clear = QPushButton("Clear")
        apply = QPushButton("Apply")
        apply.setObjectName("primary")

        panel, col = self.side_panel()
        col.addWidget(QLabel("Redact"))
        hint = _caption("Drag to draw boxes over what you want to hide. Right click removes a box.")
        hint.setWordWrap(True)
        col.addWidget(hint)
        col.addWidget(_caption("Style"))
        col.addWidget(self.style_box)
        row = QHBoxLayout()
        row.addWidget(undo)
        row.addWidget(clear)
        col.addLayout(row)
        col.addStretch(1)
        col.addWidget(self.status)
        col.addWidget(apply)

        layout = QHBoxLayout(self)
        layout.addWidget(self.canvas, 1)
        layout.addWidget(panel)
        undo.clicked.connect(self.canvas.undo)
        clear.clicked.connect(self.canvas.clear)
        apply.clicked.connect(self.apply)

    def apply(self) -> None:
        if not self.canvas.rects:
            QMessageBox.information(self, "Redact", "Draw at least one box first.")
            return
        try:
            rects = [(r.x(), r.y(), r.width(), r.height()) for r in self.canvas.rects]
            result = redact(self.image, rects, self.style_box.currentText())
            dest = output_path(self.path, self.path.suffix, "_redacted")
            save_image(result, dest)
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(dest)


# ---------------------------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------------------------


class MetadataWindow(ToolWindow):
    TITLE = "Metadata"

    def __init__(self, path: Path) -> None:
        super().__init__(path)
        self.resize(560, 560)
        rows = metadata_tool.read_metadata(self.path)

        table = QTableWidget(len(rows), 2)
        table.setHorizontalHeaderLabels(["Property", "Value"])
        table.verticalHeader().setVisible(False)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for i, (key, value) in enumerate(rows):
            table.setItem(i, 0, QTableWidgetItem(key))
            item = QTableWidgetItem(value)
            item.setToolTip(value)
            table.setItem(i, 1, item)
            if key.startswith("GPS"):
                item.setForeground(QColor("#ff6b6b"))

        gps = metadata_tool.has_gps(self.path)
        note = QLabel("This photo contains GPS location data." if gps else "No GPS location data found.")
        note.setStyleSheet("color: #ff6b6b;" if gps else "color: #6bd68b;")
        clean = QPushButton("Remove metadata and save a clean copy")
        clean.setObjectName("primary")
        clean.clicked.connect(self.strip)

        layout = QVBoxLayout(self)
        layout.addWidget(table, 1)
        layout.addWidget(note)
        layout.addWidget(self.status)
        layout.addWidget(clean)

    def strip(self) -> None:
        try:
            dest = metadata_tool.strip_metadata(self.path)[0]
        except Exception as exc:  # noqa: BLE001
            self.fail(exc)
            return
        self.report(dest)


TOOLS = {
    "crop": CropWindow,
    "add_bg": AddBgWindow,
    "edit": EditWindow,
    "redact": RedactWindow,
    "metadata": MetadataWindow,
}


def create_tool(name: str, path: Path) -> ToolWindow:
    return TOOLS[name](path)
