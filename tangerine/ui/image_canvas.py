"""Image preview with a draggable selection (crop) or several boxes (redact)."""

from __future__ import annotations

from PIL import Image
from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QBrush, QColor, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .theme import ORANGE, pil_to_pixmap

HANDLE_PX = 9
MIN_SIZE = 4  # smallest selection side in image pixels


class ImageCanvas(QWidget):
    """mode "single": one resizable selection with optional aspect lock.
    mode "multi": any number of boxes, right click removes one.
    Rectangles are kept in image pixel coordinates."""

    selectionChanged = Signal()

    def __init__(self, image: Image.Image, mode: str = "single") -> None:
        super().__init__()
        self.setMinimumSize(460, 340)
        self.setMouseTracking(True)
        self.mode = mode
        self.aspect: float | None = None
        self.rects: list[QRectF] = []
        self._pix = pil_to_pixmap(image)
        self._drag: tuple | None = None  # (kind, anchor/start point, original rect)

    # ---- geometry -----------------------------------------------------------------------------

    @property
    def image_size(self) -> tuple[int, int]:
        return self._pix.width(), self._pix.height()

    def _view(self) -> tuple[QRectF, float]:
        iw, ih = self.image_size
        margin = 12
        scale = min((self.width() - 2 * margin) / iw, (self.height() - 2 * margin) / ih)
        w, h = iw * scale, ih * scale
        return QRectF((self.width() - w) / 2, (self.height() - h) / 2, w, h), scale

    def _to_image(self, pt: QPointF, clamp: bool = True) -> QPointF:
        view, scale = self._view()
        x, y = (pt.x() - view.x()) / scale, (pt.y() - view.y()) / scale
        if clamp:
            iw, ih = self.image_size
            x, y = min(max(x, 0), iw), min(max(y, 0), ih)
        return QPointF(x, y)

    def _to_widget(self, rect: QRectF) -> QRectF:
        view, scale = self._view()
        return QRectF(view.x() + rect.x() * scale, view.y() + rect.y() * scale, rect.width() * scale, rect.height() * scale)

    def _handles(self, rect: QRectF) -> dict[str, QPointF]:
        r = self._to_widget(rect)
        return {"tl": r.topLeft(), "tr": r.topRight(), "bl": r.bottomLeft(), "br": r.bottomRight()}

    # ---- selection API ------------------------------------------------------------------------

    def selection(self) -> QRectF | None:
        return self.rects[0] if self.mode == "single" and self.rects else None

    def set_selection(self, rect: QRectF | None) -> None:
        self.rects = [rect] if rect is not None else []
        self.update()
        self.selectionChanged.emit()

    def select_all(self) -> None:
        iw, ih = self.image_size
        self.set_selection(QRectF(0, 0, iw, ih))

    def set_aspect(self, aspect: float | None) -> None:
        """Lock the ratio and reshape the current selection to it (largest centered fit)."""
        self.aspect = aspect
        sel = self.selection()
        if aspect and sel:
            from ..tools.crop import fit_box

            self.set_selection(QRectF(*fit_box((sel.x(), sel.y(), sel.width(), sel.height()), aspect)))

    def set_selection_size(self, width: float | None = None, height: float | None = None) -> None:
        """Resize keeping the top-left corner; shifts the box back inside the image if needed."""
        sel = self.selection()
        if sel is None:
            return
        iw, ih = self.image_size
        w, h = sel.width(), sel.height()
        if width is not None:
            w = min(max(width, MIN_SIZE), iw)
            if self.aspect:
                h = w / self.aspect
        if height is not None:
            h = min(max(height, MIN_SIZE), ih)
            if self.aspect:
                w = h * self.aspect
        if self.aspect:  # shrink to fit while keeping the ratio
            if w > iw:
                w, h = iw, iw / self.aspect
            if h > ih:
                w, h = ih * self.aspect, ih
        x = min(sel.x(), iw - w)
        y = min(sel.y(), ih - h)
        self.set_selection(QRectF(max(0, x), max(0, y), w, h))

    def undo(self) -> None:
        if self.rects:
            self.rects.pop()
            self.update()
            self.selectionChanged.emit()

    def clear(self) -> None:
        self.rects = []
        self.update()
        self.selectionChanged.emit()

    # ---- painting -----------------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(), QColor("#141418"))
        view, _ = self._view()
        p.drawPixmap(view, self._pix, QRectF(self._pix.rect()))

        if self.mode == "single" and self.rects:
            sel = self._to_widget(self.rects[0])
            dim = QPainterPath()
            dim.addRect(view)
            hole = QPainterPath()
            hole.addRect(sel)
            p.fillPath(dim.subtracted(hole), QColor(0, 0, 0, 150))
            p.setPen(QPen(QColor(ORANGE), 2))
            p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawRect(sel)
            p.setPen(QPen(QColor(255, 255, 255, 70), 1))
            for i in (1, 2):  # rule-of-thirds guides
                p.drawLine(QPointF(sel.x() + sel.width() * i / 3, sel.y()), QPointF(sel.x() + sel.width() * i / 3, sel.bottom()))
                p.drawLine(QPointF(sel.x(), sel.y() + sel.height() * i / 3), QPointF(sel.right(), sel.y() + sel.height() * i / 3))
            p.setPen(QPen(QColor("#ffffff"), 1.5))
            p.setBrush(QBrush(QColor(ORANGE)))
            for pt in self._handles(self.rects[0]).values():
                p.drawEllipse(pt, HANDLE_PX / 2, HANDLE_PX / 2)
        elif self.mode == "multi":
            for rect in self.rects:
                r = self._to_widget(rect)
                p.setBrush(QColor(0, 0, 0, 170))
                p.setPen(QPen(QColor("#ff4d4d"), 2))
                p.drawRect(r)

    # ---- mouse --------------------------------------------------------------------------------

    def _handle_at(self, pos: QPointF) -> str | None:
        sel = self.selection()
        if sel is None:
            return None
        for name, pt in self._handles(sel).items():
            if abs(pt.x() - pos.x()) <= HANDLE_PX and abs(pt.y() - pos.y()) <= HANDLE_PX:
                return name
        return None

    def mousePressEvent(self, event) -> None:
        pos = event.position()
        if self.mode == "multi" and event.button() == Qt.MouseButton.RightButton:
            pt = self._to_image(pos, clamp=False)
            for rect in reversed(self.rects):
                if rect.contains(pt):
                    self.rects.remove(rect)
                    self.update()
                    self.selectionChanged.emit()
                    break
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return
        pt = self._to_image(pos)
        sel = self.selection()
        handle = self._handle_at(pos)
        if handle and sel:
            opposite = {"tl": sel.bottomRight(), "tr": sel.bottomLeft(), "bl": sel.topRight(), "br": sel.topLeft()}[handle]
            self._drag = ("resize", opposite, sel)
        elif sel and sel.contains(self._to_image(pos, clamp=False)):
            self._drag = ("move", pt, QRectF(sel))
        else:
            if self.mode == "multi":
                self.rects.append(QRectF(pt, pt))
            else:
                self.rects = [QRectF(pt, pt)]
            self._drag = ("resize", pt, None)

    def mouseMoveEvent(self, event) -> None:
        pos = event.position()
        if self._drag is None:
            handle = self._handle_at(pos)
            sel = self.selection()
            if handle in ("tl", "br"):
                self.setCursor(Qt.CursorShape.SizeFDiagCursor)
            elif handle in ("tr", "bl"):
                self.setCursor(Qt.CursorShape.SizeBDiagCursor)
            elif sel and sel.contains(self._to_image(pos, clamp=False)):
                self.setCursor(Qt.CursorShape.SizeAllCursor)
            else:
                self.setCursor(Qt.CursorShape.CrossCursor)
            return

        kind, anchor, original = self._drag
        pt = self._to_image(pos)
        if kind == "move":
            iw, ih = self.image_size
            dx, dy = pt.x() - anchor.x(), pt.y() - anchor.y()
            x = min(max(original.x() + dx, 0), iw - original.width())
            y = min(max(original.y() + dy, 0), ih - original.height())
            self.rects[0] = QRectF(x, y, original.width(), original.height())
        else:
            rect = self._rect_from(anchor, pt)
            if self.mode == "multi":
                self.rects[-1] = rect
            else:
                self.rects = [rect]
        self.update()
        self.selectionChanged.emit()

    def mouseReleaseEvent(self, event) -> None:
        if self._drag is None:
            return
        self._drag = None
        if self.mode == "multi" and self.rects and (self.rects[-1].width() < MIN_SIZE or self.rects[-1].height() < MIN_SIZE):
            self.rects.pop()
        elif self.mode == "single" and self.rects and (self.rects[0].width() < MIN_SIZE or self.rects[0].height() < MIN_SIZE):
            self.rects = []
        self.update()
        self.selectionChanged.emit()

    def _rect_from(self, anchor: QPointF, pt: QPointF) -> QRectF:
        """Rectangle spanned by a fixed corner and the pointer, honoring the aspect lock."""
        dx, dy = pt.x() - anchor.x(), pt.y() - anchor.y()
        if self.aspect and self.mode == "single":
            iw, ih = self.image_size
            sx = 1 if dx >= 0 else -1
            sy = 1 if dy >= 0 else -1
            w = max(abs(dx), abs(dy) * self.aspect)
            max_w = (iw - anchor.x()) if sx > 0 else anchor.x()
            max_h = (ih - anchor.y()) if sy > 0 else anchor.y()
            w = min(w, max_w, max_h * self.aspect)
            h = w / self.aspect
            return QRectF(anchor, QPointF(anchor.x() + sx * w, anchor.y() + sy * h)).normalized()
        return QRectF(anchor, pt).normalized()
