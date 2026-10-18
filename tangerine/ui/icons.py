"""Tiny line icons for radial menu slices, drawn with QPainter in a -1..1 unit box."""

from __future__ import annotations

from typing import Callable

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QFont, QPainter, QPen


def _line(p: QPainter, r: float, *pts: float) -> None:
    for i in range(0, len(pts) - 2, 2):
        p.drawLine(QPointF(pts[i] * r, pts[i + 1] * r), QPointF(pts[i + 2] * r, pts[i + 3] * r))


def _rect(p: QPainter, r: float, x: float, y: float, w: float, h: float) -> None:
    p.drawRoundedRect(QRectF(x * r, y * r, w * r, h * r), r * 0.12, r * 0.12)


def _ellipse(p: QPainter, r: float, cx: float, cy: float, rx: float, ry: float | None = None) -> None:
    p.drawEllipse(QPointF(cx * r, cy * r), rx * r, (ry if ry is not None else rx) * r)


def _text(p: QPainter, r: float, s: str, scale: float = 1.5) -> None:
    font = QFont(p.font())
    font.setPixelSize(max(6, round(r * scale)))
    font.setBold(True)
    p.setFont(font)
    p.drawText(QRectF(-r, -r, 2 * r, 2 * r), Qt.AlignmentFlag.AlignCenter, s)


def _crop(p, r):
    _line(p, r, -0.5, -0.95, -0.5, 0.5, 0.95, 0.5)
    _line(p, r, 0.5, 0.95, 0.5, -0.5, -0.95, -0.5)


def _rotate(p, r):
    p.drawArc(QRectF(-0.8 * r, -0.8 * r, 1.6 * r, 1.6 * r), 40 * 16, 270 * 16)
    _line(p, r, 0.62, -0.62, 0.95, -0.2, 0.62, -0.62, 0.2, -0.75)


def _edit(p, r):
    for y, x in ((-0.6, -0.3), (0.0, 0.4), (0.6, -0.1)):
        _line(p, r, -0.9, y, 0.9, y)
        _ellipse(p, r, x, y, 0.2)


def _add_bg(p, r):
    _rect(p, r, -0.95, -0.95, 1.9, 1.9)
    _rect(p, r, -0.45, -0.45, 0.9, 0.9)


def _redact(p, r):
    _line(p, r, -0.9, -0.7, 0.9, -0.7, -0.9, 0.7, 0.9, 0.7)
    p.setBrush(p.pen().color())
    _rect(p, r, -0.9, -0.25, 1.8, 0.5)
    p.setBrush(Qt.BrushStyle.NoBrush)


def _resize(p, r):
    _line(p, r, -0.8, 0.8, 0.8, -0.8, 0.8, -0.8, 0.3, -0.8, 0.8, -0.8, 0.8, -0.3)
    _line(p, r, -0.8, 0.8, -0.3, 0.8, -0.8, 0.8, -0.8, 0.3)


def _watermark(p, r):
    _ellipse(p, r, 0, 0, 0.9)
    _text(p, r, "C", 1.2)


def _remove_bg(p, r):
    old = p.pen()
    dashed = QPen(old)
    dashed.setStyle(Qt.PenStyle.DashLine)
    p.setPen(dashed)
    _ellipse(p, r, 0, 0, 0.9)
    p.setPen(old)
    _ellipse(p, r, 0, 0, 0.35)


def _compress(p, r):
    _line(p, r, 0, -0.95, 0, -0.15, -0.35, -0.5, 0, -0.15, 0.35, -0.5)
    _line(p, r, 0, 0.95, 0, 0.15, -0.35, 0.5, 0, 0.15, 0.35, 0.5)


def _metadata(p, r):
    _ellipse(p, r, 0, 0, 0.9)
    _line(p, r, 0, -0.05, 0, 0.5)
    p.drawPoint(QPointF(0, -0.38 * r))


def _upscale(p, r):
    _line(p, r, 0, 0.7, 0, -0.9, -0.4, -0.5, 0, -0.9, 0.4, -0.5)
    _rect(p, r, -0.8, 0.45, 0.5, 0.5)


def _ocr(p, r):
    _line(p, r, -0.95, -0.4, -0.95, -0.9, -0.45, -0.9)
    _line(p, r, 0.95, -0.4, 0.95, -0.9, 0.45, -0.9)
    _line(p, r, -0.95, 0.4, -0.95, 0.9, -0.45, 0.9)
    _line(p, r, 0.95, 0.4, 0.95, 0.9, 0.45, 0.9)
    _text(p, r, "T", 1.3)


def _zip(p, r):
    _rect(p, r, -0.7, -0.95, 1.4, 1.9)
    _line(p, r, 0, -0.95, 0, -0.3)
    for y in (-0.1, 0.25):
        _line(p, r, -0.18, y, 0.18, y)


def _pages(p, r):
    _rect(p, r, -0.35, -0.95, 1.2, 1.5)
    _rect(p, r, -0.85, -0.55, 1.2, 1.5)


def _split(p, r):
    _rect(p, r, -0.8, -0.95, 1.6, 1.9)
    old = p.pen()
    dashed = QPen(old)
    dashed.setStyle(Qt.PenStyle.DashLine)
    p.setPen(dashed)
    _line(p, r, 0, -0.95, 0, 0.95)
    p.setPen(old)


def _lock(p, r, open_: bool = False):
    _rect(p, r, -0.7, -0.1, 1.4, 1.0)
    shackle = QRectF(-0.45 * r, -0.95 * r, 0.9 * r, 1.1 * r)
    p.drawArc(shackle, (0 if open_ else 0) * 16, (180 if not open_ else 140) * 16)
    if not open_:
        _line(p, r, -0.45, -0.4, -0.45, -0.1, 0.45, -0.4, 0.45, -0.1)


def _trim(p, r):
    _line(p, r, -0.9, -0.8, -0.9, 0.8, -0.9, 0, 0.9, 0)
    _line(p, r, -0.3, -0.45, -0.3, 0.45, 0.3, -0.45, 0.3, 0.45)


def _mute(p, r):
    _line(p, r, -0.9, -0.3, -0.5, -0.3, -0.1, -0.7, -0.1, 0.7, -0.5, 0.3, -0.9, 0.3, -0.9, -0.3)
    _line(p, r, 0.3, -0.4, 0.9, 0.4, 0.3, 0.4, 0.9, -0.4)


def _merge(p, r):
    _line(p, r, -0.9, -0.7, 0, 0, -0.9, 0.7, 0, 0, 0.9, 0, 0.5, -0.35, 0.9, 0, 0.5, 0.35)


def _stack(p, r):
    _rect(p, r, -0.6, -0.95, 1.4, 1.1)
    _rect(p, r, -0.8, -0.4, 1.4, 1.1)
    _rect(p, r, -0.95, 0.15, 1.4, 0.8)


def _extract(p, r):
    _rect(p, r, -0.9, -0.2, 1.4, 1.15)
    _line(p, r, 0.1, 0.3, 0.1, -0.95, -0.25, -0.6, 0.1, -0.95, 0.45, -0.6)


ICONS: dict[str, Callable[[QPainter, float], None]] = {
    "crop": _crop,
    "rotate": _rotate,
    "edit": _edit,
    "add_bg": _add_bg,
    "redact": _redact,
    "pdf_redact": _redact,
    "resize": _resize,
    "watermark": _watermark,
    "remove_bg": _remove_bg,
    "compress": _compress,
    "pdf_compress": _compress,
    "media_compress": _compress,
    "metadata": _metadata,
    "upscale": _upscale,
    "ocr": _ocr,
    "zip": _zip,
    "zip_all": _zip,
    "pdf_pages": _pages,
    "pdf_split": _split,
    "pdf_protect": _lock,
    "pdf_unlock": lambda p, r: _lock(p, r, open_=True),
    "trim": _trim,
    "mute": _mute,
    "merge": _merge,
    "images_to_pdf": _stack,
    "extract": _extract,
}


def draw_icon(p: QPainter, action_id: str, cx: float, cy: float, radius: float, color) -> bool:
    """Draw the icon for an action centered at (cx, cy). Returns False when there is none."""
    fn = ICONS.get(action_id)
    if fn is None:
        return False
    p.save()
    p.translate(cx, cy)
    pen = QPen(color, 1.7)
    pen.setCapStyle(Qt.PenCapStyle.RoundCap)
    pen.setJoinStyle(Qt.PenJoinStyle.RoundJoin)
    p.setPen(pen)
    p.setBrush(Qt.BrushStyle.NoBrush)
    fn(p, radius)
    p.restore()
    return True
