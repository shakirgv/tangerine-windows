"""The radial menu: a frameless always-on-top overlay that accepts file drops on its slices."""

from __future__ import annotations

import math
from pathlib import Path

from PySide6.QtCore import QEasingCurve, QEvent, QPointF, QRectF, Qt, QTimer, QVariantAnimation, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QGuiApplication, QLinearGradient, QPainter, QPainterPath, QPen
from PySide6.QtWidgets import QWidget

from .. import registry
from .theme import ORANGE, ORANGE_DARK

SIZE = 480
CENTER_R = 62
OUTER_R = 226
RING_GAP = 4
BACKDROP_R = 236
NO_DRAG_TIMEOUT_MS = 2500


def _sector_path(c: QPointF, r_in: float, r_out: float, start: float, span: float) -> QPainterPath:
    outer = QRectF(c.x() - r_out, c.y() - r_out, 2 * r_out, 2 * r_out)
    inner = QRectF(c.x() - r_in, c.y() - r_in, 2 * r_in, 2 * r_in)
    path = QPainterPath()
    path.arcMoveTo(outer, start)
    path.arcTo(outer, start, span)
    path.arcTo(inner, start + span, -span)
    path.closeSubpath()
    return path


class RadialMenu(QWidget):
    """Slices come from the registry. Two modes:

    drag  - opened by the global trigger; the files appear in dragEnter, a drop on a slice runs it.
    click - opened after a drop on the drop window; a click on a slice runs it.
    """

    actionChosen = Signal(object, list)  # registry.Action, list[Path]
    closed = Signal()

    def __init__(self) -> None:
        super().__init__(None)
        self.setWindowFlags(Qt.WindowType.Tool | Qt.WindowType.FramelessWindowHint | Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setAcceptDrops(True)
        self.setMouseTracking(True)
        self.resize(SIZE, SIZE)

        self._mode = "drag"
        self._files: list[Path] = []
        self._groups: list[registry.Group] = []
        self._unsupported = False
        self._hover: tuple[int, int] | None = None
        self._drag_seen = False
        self._scale = 1.0

        self._anim = QVariantAnimation(self)
        self._anim.setStartValue(0.82)
        self._anim.setEndValue(1.0)
        self._anim.setDuration(140)
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.valueChanged.connect(self._on_scale)

        self._timeout = QTimer(self)
        self._timeout.setSingleShot(True)
        self._timeout.timeout.connect(self._on_no_drag)

    # ---- public API -------------------------------------------------------------------------

    @property
    def files(self) -> list[Path]:
        return list(self._files)

    def open_for_drag(self, center: QPointF) -> None:
        """Show at center, waiting for a drag to enter. Hides itself if none does."""
        self._prepare("drag", center)
        self.set_files([])
        self._timeout.start(NO_DRAG_TIMEOUT_MS)
        self.show()

    def open_for_files(self, center: QPointF, files: list[Path]) -> None:
        """Show at center for already known files; a click on a slice runs it."""
        self._prepare("click", center)
        self.set_files(files)
        self.show()
        self.raise_()
        self.activateWindow()
        self.setFocus()

    def set_files(self, files: list[Path]) -> None:
        kind, same = registry.common_kind(files)
        self._files = same
        self._unsupported = bool(files) and kind is None
        self._groups = registry.groups_for(kind, same[0].suffix) if kind else []
        self._hover = None
        self.update()

    def dismiss(self) -> None:
        self._timeout.stop()
        if self.isVisible():
            self.hide()
        self._hover = None
        self.closed.emit()

    def dismiss_later(self, ms: int = 300) -> None:
        """Hide after a short delay, so a drop that is still being delivered is not lost."""
        QTimer.singleShot(ms, lambda: self.dismiss() if self.isVisible() else None)

    # ---- setup helpers ----------------------------------------------------------------------

    def _prepare(self, mode: str, center: QPointF) -> None:
        self._mode = mode
        self._drag_seen = False
        drag = mode == "drag"
        self.setWindowFlag(Qt.WindowType.WindowDoesNotAcceptFocus, drag)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, drag)
        self.setFocusPolicy(Qt.FocusPolicy.NoFocus if drag else Qt.FocusPolicy.StrongFocus)

        screen = QGuiApplication.screenAt(center.toPoint()) or QGuiApplication.primaryScreen()
        geo = screen.availableGeometry()
        x = min(max(center.x() - SIZE / 2, geo.left()), geo.right() - SIZE + 1)
        y = min(max(center.y() - SIZE / 2, geo.top()), geo.bottom() - SIZE + 1)
        self.move(int(x), int(y))
        self._anim.stop()
        self._scale = 0.82
        self._anim.start()

    def _on_scale(self, value) -> None:
        self._scale = float(value)
        self.update()

    def _on_no_drag(self) -> None:
        if self._mode == "drag" and not self._drag_seen and self.isVisible():
            self.dismiss()

    # ---- geometry ---------------------------------------------------------------------------

    def _ring_bounds(self, ring: int) -> tuple[float, float]:
        n = len(self._groups)
        total = OUTER_R - CENTER_R - RING_GAP * (n - 1)
        thickness = total / n
        r_out = OUTER_R - ring * (thickness + RING_GAP)
        return r_out - thickness, r_out

    def _center(self) -> QPointF:
        return QPointF(self.width() / 2, self.height() / 2)

    def _hit(self, pos: QPointF) -> tuple[int, int] | None:
        c = self._center()
        dx, dy = pos.x() - c.x(), c.y() - pos.y()
        radius = math.hypot(dx, dy)
        angle = math.degrees(math.atan2(dy, dx))
        for ring, group in enumerate(self._groups):
            r_in, r_out = self._ring_bounds(ring)
            if r_in <= radius <= r_out:
                n = len(group.actions)
                step = 360 / n
                index = int(((90 - angle) % 360 + step / 2) // step) % n
                return ring, index
        return None

    def _action_at(self, hit: tuple[int, int] | None):
        if hit is None:
            return None
        return self._groups[hit[0]].actions[hit[1]]

    # ---- painting ---------------------------------------------------------------------------

    def paintEvent(self, _event) -> None:
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setRenderHint(QPainter.RenderHint.TextAntialiasing)
        c = self._center()
        p.translate(c)
        p.scale(self._scale, self._scale)
        p.translate(-c)

        # Backdrop. It is never fully transparent, so the whole disc receives mouse/drop events.
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor(12, 12, 16, 150))
        p.drawEllipse(c, BACKDROP_R, BACKDROP_R)

        for ring, group in enumerate(self._groups):
            self._paint_ring(p, c, ring, group)
        self._paint_center(p, c)

    def _paint_ring(self, p: QPainter, c: QPointF, ring: int, group: registry.Group) -> None:
        r_in, r_out = self._ring_bounds(ring)
        n = len(group.actions)
        step = 360 / n
        font = QFont(self.font())
        font.setBold(True)
        font.setPixelSize(13 if n <= 6 else 12 if n <= 9 else 11)
        p.setFont(font)
        for i, action in enumerate(group.actions):
            mid = 90 - i * step
            path = _sector_path(c, r_in, r_out, mid - step / 2, step)
            hovered = self._hover == (ring, i)
            if hovered:
                grad = QLinearGradient(c.x(), c.y() - r_out, c.x(), c.y() + r_out)
                grad.setColorAt(0, QColor("#ffb04a"))
                grad.setColorAt(1, QColor(ORANGE_DARK))
                p.setBrush(grad)
            else:
                p.setBrush(QColor(40, 40, 48, 238) if ring == 0 else QColor(52, 46, 42, 238))
            p.setPen(QPen(QColor(255, 255, 255, 36), 1.2))
            p.drawPath(path)

            rm = (r_in + r_out) / 2
            rad = math.radians(mid)
            lx, ly = c.x() + rm * math.cos(rad), c.y() - rm * math.sin(rad)
            p.setPen(QColor("#1a1206") if hovered else QColor("#f2f2f5"))
            rect = QRectF(lx - 40, ly - 14, 80, 28)
            p.drawText(rect, Qt.AlignmentFlag.AlignCenter, action.label)

    def _paint_center(self, p: QPainter, c: QPointF) -> None:
        p.setPen(QPen(QColor(255, 255, 255, 50), 1.2))
        p.setBrush(QColor(24, 24, 30, 245))
        p.drawEllipse(c, CENTER_R - 4, CENTER_R - 4)

        action = self._action_at(self._hover)
        if action:
            title, sub = action.label, "release to run" if self._mode == "drag" else "click to run"
        elif self._unsupported:
            title, sub = "Unsupported", "file type"
        elif self._files:
            name = self._files[0].name
            title = QFontMetrics(p.font()).elidedText(name, Qt.TextElideMode.ElideMiddle, 80)
            sub = f"+{len(self._files) - 1} more" if len(self._files) > 1 else "choose a slice"
        else:
            title, sub = "Drag a", "file here"

        font = QFont(self.font())
        font.setPixelSize(12)
        font.setBold(True)
        p.setFont(font)
        p.setPen(QColor(ORANGE))
        p.drawText(QRectF(c.x() - 52, c.y() - 22, 104, 22), Qt.AlignmentFlag.AlignCenter, title)
        font.setBold(False)
        font.setPixelSize(10)
        p.setFont(font)
        p.setPen(QColor("#9a9aa6"))
        p.drawText(QRectF(c.x() - 52, c.y() + 2, 104, 18), Qt.AlignmentFlag.AlignCenter, sub)

    # ---- drag and drop (trigger mode) ---------------------------------------------------------

    def dragEnterEvent(self, event) -> None:
        paths = [Path(u.toLocalFile()) for u in event.mimeData().urls() if u.isLocalFile()]
        if not paths:
            event.ignore()
            return
        self._drag_seen = True
        self._timeout.stop()
        self.set_files(paths)
        self._update_hover(event.position())
        event.acceptProposedAction()

    def dragMoveEvent(self, event) -> None:
        hit = self._update_hover(event.position())
        if hit is not None:
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragLeaveEvent(self, event) -> None:
        self._hover = None
        self.update()

    def dropEvent(self, event) -> None:
        action = self._action_at(self._hit(event.position()))
        files = list(self._files)
        if action is None or not files:
            event.ignore()
            self.dismiss()
            return
        event.setDropAction(Qt.DropAction.CopyAction)
        event.accept()
        self.dismiss()
        # Emit after the drop has been handed back to the drag source.
        QTimer.singleShot(0, lambda: self.actionChosen.emit(action, files))

    def _update_hover(self, pos: QPointF) -> tuple[int, int] | None:
        hit = self._hit(pos)
        if hit != self._hover:
            self._hover = hit
            self.update()
        return hit

    # ---- click mode ---------------------------------------------------------------------------

    def mouseMoveEvent(self, event) -> None:
        self._update_hover(event.position())

    def mousePressEvent(self, event) -> None:
        if self._mode != "click":
            return
        action = self._action_at(self._hit(event.position()))
        if event.button() == Qt.MouseButton.LeftButton and action and self._files:
            files = list(self._files)
            self.dismiss()
            QTimer.singleShot(0, lambda: self.actionChosen.emit(action, files))
        else:
            self.dismiss()

    def keyPressEvent(self, event) -> None:
        if event.key() == Qt.Key.Key_Escape:
            self.dismiss()

    def event(self, event) -> bool:
        if event.type() == QEvent.Type.WindowDeactivate and self._mode == "click" and self.isVisible():
            QTimer.singleShot(0, self.dismiss)
        return super().event(event)
