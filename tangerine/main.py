"""Entry point: tray icon, global trigger, radial menu and action runner."""

from __future__ import annotations

import subprocess
import sys
import threading
import time
import traceback
from pathlib import Path

from PySide6.QtCore import QObject, QPointF, QRunnable, QStandardPaths, QThreadPool, Signal
from PySide6.QtGui import QCursor
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from . import history, registry, settings, utils
from .trigger import TriggerListener
from .ui.drop_window import DropWindow
from .ui.progress import ProgressBox
from .ui.radial_menu import RadialMenu
from .ui.settings_dialog import SettingsDialog
from .ui.theme import app_icon
from .ui.tool_base import ToolWindow
from .ui.tool_windows import create_tool

INSTANCE_NAME = "TangerineWindowsSingleInstance"


class _JobSignals(QObject):
    progress = Signal(int, str)  # files finished, name of the next file
    finished = Signal(object)  # JobResult


class JobResult:
    def __init__(self, action: registry.Action, files: list[Path]) -> None:
        self.action = action
        self.files = files
        self.outputs: list[Path] = []
        self.succeeded: list[Path] = []
        self.errors: list[str] = []
        self.cancelled = False


class _Job(QRunnable):
    """Runs an action over files in a worker thread. A failure on one file does not stop the others."""

    def __init__(self, action: registry.Action, files: list[Path], signals: _JobSignals, cancel: threading.Event) -> None:
        super().__init__()
        self.result = JobResult(action, files)
        self.signals, self.cancel = signals, cancel

    def run(self) -> None:
        utils.set_cancel_event(self.cancel)
        result = self.result
        try:
            if result.action.batch:
                self.signals.progress.emit(0, f"{len(result.files)} files")
                try:
                    result.outputs += result.action.batch(result.files)
                    result.succeeded = list(result.files)
                except utils.Cancelled:
                    result.cancelled = True
                except Exception as exc:  # noqa: BLE001 - report every failure to the user
                    traceback.print_exc()
                    result.errors.append(f"{type(exc).__name__}: {exc}")
            else:
                for done, src in enumerate(result.files):
                    if self.cancel.is_set():
                        result.cancelled = True
                        break
                    self.signals.progress.emit(done, src.name)
                    try:
                        result.outputs += result.action.handler(src)
                        result.succeeded.append(src)
                    except utils.Cancelled:
                        result.cancelled = True
                        break
                    except Exception as exc:  # noqa: BLE001
                        traceback.print_exc()
                        result.errors.append(f"{src.name}: {type(exc).__name__}: {exc}")
        finally:
            utils.set_cancel_event(None)
            self.signals.finished.emit(result)


class Controller(QObject):
    def __init__(self, app: QApplication, show_window: bool = True) -> None:
        super().__init__()
        self.app = app
        self._windows: set[ToolWindow] = set()
        self._last_output: Path | None = None
        self._cancel = threading.Event()
        self._busy = 0

        self.menu = RadialMenu()
        self.menu.actionChosen.connect(self.run_action)

        self.drop_window = DropWindow()
        self.drop_window.setWindowIcon(app_icon())
        self.drop_window.filesDropped.connect(self._on_files_dropped)

        self.progress = ProgressBox()
        self.progress.cancelRequested.connect(self._cancel.set)
        self.signals = _JobSignals()
        self.signals.progress.connect(self._on_progress)
        self.signals.finished.connect(self._on_finished)

        self.trigger = TriggerListener(settings.get("trigger"))
        self.trigger.enabled = bool(settings.get("enabled"))
        self.trigger.triggered.connect(self._on_triggered)
        self.trigger.released.connect(self.menu.dismiss_later)
        self.trigger.start()

        self._build_tray()
        self._refresh_trigger_text()
        if show_window:
            self.drop_window.show()

    # ---- trigger and menu -------------------------------------------------------------------

    def _on_triggered(self) -> None:
        self.menu.open_for_drag(QPointF(QCursor.pos()))

    def _on_files_dropped(self, files: list, pos: QPointF) -> None:
        self.menu.open_for_files(pos, files)

    def menu_from_clipboard(self) -> None:
        """Open the menu for what is on the clipboard: files, an image or text."""
        data = self.app.clipboard().mimeData()
        files: list[Path] = []
        stamp = time.strftime("%Y%m%d_%H%M%S")
        if data.hasUrls():
            files = [Path(u.toLocalFile()) for u in data.urls() if u.isLocalFile()]
        elif data.hasImage():
            folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.PicturesLocation)) / "Tangerine"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"clipboard_{stamp}.png"
            if self.app.clipboard().image().save(str(target)):
                files = [target]
        elif data.hasText() and data.text().strip():
            folder = Path(QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)) / "Tangerine"
            folder.mkdir(parents=True, exist_ok=True)
            target = folder / f"clipboard_{stamp}.txt"
            target.write_text(data.text(), encoding="utf-8")
            files = [target]
        if not files:
            self._notify("Tangerine", "The clipboard has no files, image or text.")
            return
        self.menu.open_for_files(QPointF(QCursor.pos()), files)

    # ---- running actions ----------------------------------------------------------------------

    def run_action(self, action: registry.Action, files: list[Path]) -> None:
        if action.window:
            self._open_tool(action.window, files[0])
            return
        if self._busy:
            self._notify("Tangerine", "Another operation is still running. Please wait or cancel it.")
            return
        self._busy += 1
        self._cancel.clear()
        self.progress.start(action.label, len(files) if not action.batch else 1)
        QThreadPool.globalInstance().start(_Job(action, files, self.signals, self._cancel))

    def _on_progress(self, done: int, name: str) -> None:
        self.progress.update_progress(done, name)

    def _on_finished(self, result: JobResult) -> None:
        self._busy = max(0, self._busy - 1)
        self.progress.finish()
        label = result.action.label
        if result.outputs:
            self._last_output = result.outputs[0]
            history.add(label, result.outputs)
        if result.cancelled:
            self._notify(f"{label} cancelled", f"{len(result.outputs)} file(s) were finished before cancelling.")
        elif result.errors:
            shown = "\n".join(result.errors[:3]) + (f"\n+{len(result.errors) - 3} more" if len(result.errors) > 3 else "")
            self.tray.showMessage(f"{label} failed", shown, QSystemTrayIcon.MessageIcon.Warning, 9000)
        elif result.outputs:
            names = result.outputs[0].name if len(result.outputs) == 1 else f"{len(result.outputs)} files"
            self._notify(f"{label} done", f"Saved: {names}\nClick to show in folder.")
        if result.action.convert and settings.get("delete_original") and result.succeeded:
            self._trash_originals(result)

    def _trash_originals(self, result: JobResult) -> None:
        from send2trash import send2trash

        produced = {p.resolve() for p in result.outputs}
        for src in result.succeeded:
            try:
                if src.resolve() not in produced and src.exists():
                    send2trash(str(src))
            except OSError:
                traceback.print_exc()

    def _open_tool(self, name: str, path: Path) -> None:
        try:
            window = create_tool(name, path)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            self.tray.showMessage(f"{name} failed", f"{type(exc).__name__}: {exc}", QSystemTrayIcon.MessageIcon.Warning, 8000)
            return
        window.setWindowIcon(app_icon())
        window.saved.connect(self._on_saved)
        window.destroyed.connect(lambda _=None, w=window: self._windows.discard(w))
        self._windows.add(window)
        window.show_front()

    def _on_saved(self, path: Path) -> None:
        self._last_output = Path(path)
        history.add(getattr(self.sender(), "TITLE", "Tool"), [Path(path)])
        self._notify("Saved", Path(path).name)

    def _notify(self, title: str, message: str) -> None:
        self.tray.showMessage(title, message, QSystemTrayIcon.MessageIcon.Information, 4000)

    def _reveal(self, path: Path | None) -> None:
        if path and path.exists():
            subprocess.Popen(["explorer", "/select,", str(path)])

    # ---- tray ---------------------------------------------------------------------------------

    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(app_icon(), self)
        self.tray.setToolTip("Tangerine")
        self.tray.messageClicked.connect(lambda: self._reveal(self._last_output))
        menu = QMenu()

        menu.addAction("Open drop window").triggered.connect(self.show_drop_window)
        menu.addAction("Menu from clipboard").triggered.connect(self.menu_from_clipboard)
        self.recent_menu = menu.addMenu("Recent")
        self.recent_menu.aboutToShow.connect(self._fill_recent)
        menu.addAction("Undo last operation").triggered.connect(self._undo_last)
        menu.addSeparator()

        self.enabled_action = menu.addAction("Trigger enabled")
        self.enabled_action.setCheckable(True)
        self.enabled_action.setChecked(bool(settings.get("enabled")))
        self.enabled_action.toggled.connect(self._set_enabled)
        menu.addAction("Settings...").triggered.connect(self.open_settings)
        menu.addSeparator()
        menu.addAction("Quit").triggered.connect(self.quit)

        self.tray.setContextMenu(menu)
        self._tray_menu = menu
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _fill_recent(self) -> None:
        self.recent_menu.clear()
        entries = history.recent_outputs()
        if not entries:
            self.recent_menu.addAction("Nothing yet").setEnabled(False)
        for label, path in entries:
            action = self.recent_menu.addAction(f"{path.name}  ({label})")
            action.triggered.connect(lambda _=False, p=path: self._reveal(p))

    def _undo_last(self) -> None:
        try:
            removed = history.undo_last()
        except Exception as exc:  # noqa: BLE001
            self.tray.showMessage("Undo failed", f"{type(exc).__name__}: {exc}", QSystemTrayIcon.MessageIcon.Warning, 6000)
            return
        if removed:
            self._notify("Undone", f"Moved to the Recycle Bin: {removed[0].name}" + (f" +{len(removed) - 1} more" if len(removed) > 1 else ""))
        else:
            self._notify("Tangerine", "Nothing to undo.")

    def _on_tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self.show_drop_window()

    def show_drop_window(self) -> None:
        self.drop_window.show()
        self.drop_window.raise_()
        self.drop_window.activateWindow()

    def _set_enabled(self, on: bool) -> None:
        settings.set("enabled", on)
        self.trigger.enabled = on

    def open_settings(self) -> None:
        dialog = SettingsDialog()
        dialog.setWindowIcon(app_icon())
        if dialog.exec():
            self.trigger.set_combo(settings.get("trigger"))
            self._refresh_trigger_text()

    def _refresh_trigger_text(self) -> None:
        self.drop_window.set_trigger_text(settings.TRIGGERS[settings.get("trigger")])

    def quit(self) -> None:
        self.trigger.stop()
        self.tray.hide()
        self.app.quit()


def _already_running() -> bool:
    """Ask a running instance to show its window. True when one answered."""
    socket = QLocalSocket()
    socket.connectToServer(INSTANCE_NAME)
    if socket.waitForConnected(300):
        socket.write(b"show")
        socket.flush()
        socket.waitForBytesWritten(300)
        socket.disconnectFromServer()
        return True
    return False


def run(argv: list[str] | None = None) -> int:
    argv = sys.argv if argv is None else argv
    app = QApplication(argv)
    app.setApplicationName("Tangerine")
    app.setQuitOnLastWindowClosed(False)
    app.setWindowIcon(app_icon())
    if _already_running():
        return 0
    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(None, "Tangerine", "No system tray is available; the app will still work from its window.")

    controller = Controller(app, show_window="--hidden" not in argv)
    server = QLocalServer()
    QLocalServer.removeServer(INSTANCE_NAME)
    server.listen(INSTANCE_NAME)
    server.newConnection.connect(lambda: (server.nextPendingConnection(), controller.show_drop_window()))
    app._controller, app._server = controller, server  # keep references for the lifetime of the app
    return app.exec()
