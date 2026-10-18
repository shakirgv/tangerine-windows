"""Colors, stylesheet and generated icons."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPen, QPixmap

ORANGE = "#ff8a1f"
ORANGE_DARK = "#e5670a"
BG = "#1d1d22"
PANEL = "#26262d"
TEXT = "#f2f2f5"
MUTED = "#9a9aa6"

STYLE = f"""
QWidget {{ background: {BG}; color: {TEXT}; font-size: 13px; }}
QLabel#muted {{ color: {MUTED}; }}
QLabel#title {{ font-size: 15px; font-weight: 600; }}
QPushButton {{ background: {PANEL}; border: 1px solid #3a3a44; border-radius: 6px; padding: 6px 14px; }}
QPushButton:hover {{ border-color: {ORANGE}; }}
QPushButton:pressed {{ background: #30303a; }}
QPushButton#primary {{ background: {ORANGE}; border: none; color: #1a1206; font-weight: 600; }}
QPushButton#primary:hover {{ background: #ffa04a; }}
QPushButton:checked {{ border-color: {ORANGE}; background: #3a2a18; }}
QComboBox, QSpinBox, QDoubleSpinBox {{ background: {PANEL}; border: 1px solid #3a3a44; border-radius: 6px; padding: 4px 8px; }}
QComboBox QAbstractItemView {{ background: {PANEL}; selection-background-color: {ORANGE_DARK}; }}
QSlider::groove:horizontal {{ height: 4px; background: #3a3a44; border-radius: 2px; }}
QSlider::handle:horizontal {{ background: {ORANGE}; width: 14px; margin: -6px 0; border-radius: 7px; }}
QSlider::sub-page:horizontal {{ background: {ORANGE}; border-radius: 2px; }}
QTableWidget {{ background: {PANEL}; gridline-color: #34343e; border: 1px solid #34343e; }}
QHeaderView::section {{ background: {BG}; color: {MUTED}; border: none; padding: 4px; }}
"""


def pil_to_pixmap(img: Image.Image) -> QPixmap:
    rgba = img.convert("RGBA")
    data = rgba.tobytes("raw", "RGBA")
    qimg = QImage(data, rgba.width, rgba.height, rgba.width * 4, QImage.Format.Format_RGBA8888)
    return QPixmap.fromImage(qimg.copy())


def app_icon() -> QIcon:
    """A small tangerine: orange disc with segment lines and a leaf."""
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128):
        pm = QPixmap(size, size)
        pm.fill(Qt.GlobalColor.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = QPointF(size / 2, size * 0.56)
        r = size * 0.42
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(ORANGE))
        p.drawEllipse(c, r, r)
        p.setPen(QPen(QColor(255, 255, 255, 110), max(1.0, size / 40)))
        for i in range(4):
            p.save()
            p.translate(c)
            p.rotate(i * 45)
            p.drawLine(QPointF(0, -r * 0.8), QPointF(0, r * 0.8))
            p.restore()
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor("#3fae49"))
        p.drawEllipse(QRectF(size * 0.5, size * 0.04, size * 0.3, size * 0.18))
        p.end()
        icon.addPixmap(pm)
    return icon
