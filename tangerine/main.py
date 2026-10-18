"""Entry point: tray icon, global trigger, radial menu and action runner."""

from __future__ import annotations

import subprocess
import sys
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRunnable, QThreadPool, Signal
from PySide6.QtGui import QActionGroup, QCursor
from PySide6.QtWidgets import QApplication, QFileDialog, QMenu, QMessageBox, QSystemTrayIcon

from . import registry, settings
from .trigger import TriggerListener
from .ui.drop_window import DropWindow
from .ui.radial_menu import RadialMenu
from .ui.theme import app_icon
from .ui.tool_windows import ToolWindow, create_tool


class _JobSignals(QObject):
    done = Signal(str, list)  # action label, output paths
    failed = Signal(str, str)  # action label, message


class _Job(QRunnable):
    def __init__(self, action: registry.Action, files: list[Path], signals: _JobSignals) -> None:
        super().__init__()
        self.action, self.files, self.signals = action, files, signals

    def run(self) -> None:
        outputs: list[Path] = []
        try:
            for src in self.files:
                outputs += self.action.handler(src)
        except Exception as exc:  # noqa: BLE001 - report every failure to the user
            traceback.print_exc()
            self.signals.failed.emit(self.action.label, f"{type(exc).__name__}: {exc}")
            return
        self.signals.done.emit(self.action.label, [str(p) for p in outputs])


class Controller(QObject):
    def __init__(self, app: QApplication, show_window: bool = True) -> None:
        super().__init__()
        self.app = app
        self._windows: set[ToolWindow] = set()
        self._last_output: Path | None = None

        self.menu = RadialMenu()
        self.menu.actionChosen.connect(self.run_action)

        self.drop_window = DropWindow()
        self.drop_window.setWindowIcon(app_icon())
        self.drop_window.filesDropped.connect(self._on_files_dropped)

        self.signals = _JobSignals()
        self.signals.done.connect(self._on_done)
        self.signals.failed.connect(self._on_failed)

        self.trigger = TriggerListener(settings.get("trigger"))
        self.trigger.enabled = bool(settings.get("enabled"))
        self.trigger.triggered.connect(self._on_triggered)
        self.trigger.released.connect(self.menu.dismiss_later)
        self.trigger.start()

        self._build_tray()
        self.drop_window.set_trigger_text(settings.TRIGGERS[settings.get("trigger")])
        if show_window:
            self.drop_window.show()

    # ---- trigger and menu -------------------------------------------------------------------

    def _on_triggered(self) -> None:
        self.menu.open_for_drag(QPointF(QCursor.pos()))

    def _on_files_dropped(self, files: list, pos: QPointF) -> None:
        self.menu.open_for_files(pos, files)

    # ---- running actions ----------------------------------------------------------------------

    def run_action(self, action: registry.Action, files: list[Path]) -> None:
        if action.window:
            self._open_tool(action.window, files[0])
            if len(files) > 1:
                self._notify("Tangerine", f"{action.label} works on one file at a time; opened {files[0].name}.")
            return
        self._notify("Tangerine", f"{action.label}: working on {len(files)} file(s)...")
        QThreadPool.globalInstance().start(_Job(action, files, self.signals))

    def _open_tool(self, name: str, path: Path) -> None:
        try:
            window = create_tool(name, path)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self._on_failed(name, f"{type(exc).__name__}: {exc}")
            return
        window.setWindowIcon(app_icon())
        window.saved.connect(self._on_saved)
        window.destroyed.connect(lambda _=None, w=window: self._windows.discard(w))
        self._windows.add(window)
        window.show_front()

    def _on_saved(self, path: Path) -> None:
        self._last_output = Path(path)
        self._notify("Saved", Path(path).name)

    def _on_done(self, label: str, outputs: list) -> None:
        if not outputs:
            return
        self._last_output = Path(outputs[0])
        names = Path(outputs[0]).name if len(outputs) == 1 else f"{len(outputs)} files"
        self._notify(f"{label} done", f"Saved: {names}\nClick to show in folder.")

    def _on_failed(self, label: str, message: str) -> None:
        self.tray.showMessage(f"{label} failed", message, QSystemTrayIcon.MessageIcon.Warning, 8000)

    def _notify(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _reveal_last(self) -> None:
        if self._last_output and self._last_output.exists():
            subprocess.Popen(["explorer", "/select,", str(self._last_output)])

    # ---- tray and settings --------------------------------------------------------------------

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("Tangerine")
        self.tray.messageClicked.connect(self._reveal_last)
        menu = QMenu()

        show = menu.addAction("Open drop window")
        show.triggered.connect(self._show_drop_window)

        self.enabled_action = menu.addAction("Trigger enabled")
        self.enabled_action.setCheckable(True)
        self.enabled_action.setChecked(bool(settings.get("enabled")))
        self.enabled_action.toggled.connect(self._set_enabled)

        trigger_menu = menu.addMenu("Trigger key")
        group = QActionGroup(trigger_menu)
        for key, text in settings.TRIGGERS.items():
            act = trigger_menu.addAction(text)
            act.setCheckable(True)
            act.setChecked(key == settings.get("trigger"))
            group.addAction(act)
            act.triggered.connect(lambda _=False, k=key: self._set_trigger(k))

        menu.addSeparator()
        self.output_action = menu.addAction("")
        self.output_action.triggered.connect(self._choose_output)
        reset_output = menu.addAction("Save next to the original")
        reset_output.triggered.connect(lambda: self._set_output(""))
        self._refresh_output_label()

        menu.addSeparator()
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit)
        self.tray.setContextMenu(menu)
        self._tray_menu = menu
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_drop_window()

    def _show_drop_window(self) -> None:
        self.drop_window.show()
        self.drop_window.raise_()
        self.drop_window.activateWindow()

    def _set_enabled(self, on: bool) -> None:
        settings.set("enabled", on)
        self.trigger.enabled = on

    def _set_trigger(self, key: str) -> None:
        settings.set("trigger", key)
        self.trigger.set_combo(key)
        self.drop_window.set_trigger_text(settings.TRIGGERS[key])

    def _choose_output(self) -> None:
        folder = QFileDialog.getExistingDirectory(None, "Output folder", settings.get("output_dir") or str(Path.home()))
        if folder:
            self._set_output(folder)

    def _set_output(self, folder: str) -> None:
        settings.set("output_dir", folder)
        self._refresh_output_label()

    def _refresh_output_label(self) -> None:
        folder = settings.get("output_dir")
        self.output_action.setText(f"Output folder: {folder}..." if folder else "Output folder: next to original...")

    def quit(self) -> None:
        self.trigger.stop()
        self.tray.hide()
        self.app.quit()


def run(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("Tangerine")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, "Tangerine", "No system tray is available; the app will still work from its window.")
    controller = Controller(app, show_window="--hidden" not in argv)
    app._controller = controller  # keep a reference for the lifetime of the app
    return app.exec()
