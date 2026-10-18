"""Global trigger: detects "modifier held + left mouse drag" anywhere on screen.

Windows does not expose dragged file paths during a system-wide drag, so this only reports
that a drag with the modifier started and when the mouse button was released. The radial menu
then reads the real paths from its own dragEnter event.
"""

from __future__ import annotations

import math

from pynput import keyboard, mouse
from PySide6.QtCore import QObject, Signal

DRAG_THRESHOLD_PX = 8


def _modifier(key) -> str | None:
    name = getattr(key, "name", "") or ""
    for mod in ("ctrl", "shift", "alt"):
        if name.startswith(mod):
            return mod
    return None


class TriggerListener(QObject):
    triggered = Signal()  # modifier held and the mouse dragged past the threshold
    released = Signal()  # the left button was released after a trigger

    def __init__(self, combo: str = "ctrl+shift") -> None:
        super().__init__()
        self._required = set(combo.split("+"))
        self.enabled = True
        self._held: set[str] = set()
        self._down = False
        self._fired = False
        self._origin = (0, 0)
        self._pos = (0, 0)
        self._kb = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self._mouse = mouse.Listener(on_move=self._on_move, on_click=self._on_click)

    def set_combo(self, combo: str) -> None:
        self._required = set(combo.split("+"))

    def start(self) -> None:
        self._kb.start()
        self._mouse.start()

    def stop(self) -> None:
        self._kb.stop()
        self._mouse.stop()

    # These callbacks run on pynput's threads, so they only touch plain state and emit signals.

    def _on_press(self, key) -> None:
        mod = _modifier(key)
        if mod:
            self._held.add(mod)
            self._maybe_fire()

    def _on_release(self, key) -> None:
        mod = _modifier(key)
        if mod:
            self._held.discard(mod)

    def _on_move(self, x, y) -> None:
        self._pos = (x, y)
        if self._down and not self._fired:
            self._maybe_fire()

    def _on_click(self, x, y, button, pressed) -> None:
        if button != mouse.Button.left:
            return
        self._pos = (x, y)
        if pressed:
            self._down = True
            self._fired = False
            self._origin = (x, y)
        else:
            self._down = False
            if self._fired:
                self._fired = False
                self.released.emit()

    def _maybe_fire(self) -> None:
        if not (self.enabled and self._down) or self._fired:
            return
        if not self._required <= self._held:
            return
        if math.dist(self._origin, self._pos) < DRAG_THRESHOLD_PX:
            return
        self._fired = True
        self.triggered.emit()
