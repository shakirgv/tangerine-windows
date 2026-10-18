"""Tangerine setup: unpacks the bundled app into the user profile (no admin rights needed)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
import zipfile
from pathlib import Path
from tkinter import BooleanVar, StringVar, Tk, filedialog, messagebox, ttk

import _winutil as win

VERSION = "0.2.0"


def payload() -> Path:
    base = Path(getattr(sys, "_MEIPASS", Path(__file__).parent))
    return base / "payload.zip"


class Installer:
    def __init__(self) -> None:
        self.root = Tk()
        self.root.title("Tangerine Setup")
        self.root.resizable(False, False)
        default = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "Programs" / "Tangerine"
        self.path = StringVar(value=str(default))
        self.autostart = BooleanVar(value=True)
        self.desktop = BooleanVar(value=True)
        self.launch = BooleanVar(value=True)
        self.error: str | None = None
        self.worker: threading.Thread | None = None

        frame = ttk.Frame(self.root, padding=18)
        frame.grid()
        ttk.Label(frame, text="Install Tangerine", font=("Segoe UI", 15, "bold")).grid(sticky="w")
        ttk.Label(frame, text="Drag a file with Ctrl+Shift held to convert it or run a tool on it.").grid(sticky="w", pady=(0, 12))
        ttk.Label(frame, text="Install folder").grid(sticky="w")
        row = ttk.Frame(frame)
        row.grid(sticky="ew")
        ttk.Entry(row, textvariable=self.path, width=52).grid(row=0, column=0)
        ttk.Button(row, text="Browse...", command=self.browse).grid(row=0, column=1, padx=(6, 0))
        ttk.Checkbutton(frame, text="Start Tangerine when Windows starts (recommended)", variable=self.autostart).grid(sticky="w", pady=(12, 0))
        ttk.Checkbutton(frame, text="Create a desktop shortcut", variable=self.desktop).grid(sticky="w")
        ttk.Checkbutton(frame, text="Start Tangerine now", variable=self.launch).grid(sticky="w")
        self.bar = ttk.Progressbar(frame, length=440, mode="determinate")
        self.bar.grid(pady=(14, 4))
        self.status = ttk.Label(frame, text="")
        self.status.grid(sticky="w")
        self.button = ttk.Button(frame, text="Install", command=self.start)
        self.button.grid(sticky="e", pady=(8, 0))

    def browse(self) -> None:
        folder = filedialog.askdirectory(initialdir=self.path.get())
        if folder:
            chosen = Path(folder)
            self.path.set(str(chosen if chosen.name == "Tangerine" else chosen / "Tangerine"))

    def start(self) -> None:
        self.button.state(["disabled"])
        self.worker = threading.Thread(target=self.work, daemon=True)
        self.worker.start()
        self.poll()

    def poll(self) -> None:
        if self.worker and self.worker.is_alive():
            self.root.after(100, self.poll)
        else:
            self.finish()

    def set_status(self, text: str) -> None:
        self.root.after(0, lambda: self.status.configure(text=text))

    def work(self) -> None:
        try:
            target = Path(self.path.get())
            self.set_status("Closing a running Tangerine...")
            win.stop_app()
            if target.exists():
                self.set_status("Removing the old version...")
                shutil.rmtree(target, ignore_errors=True)
            target.mkdir(parents=True, exist_ok=True)
            with zipfile.ZipFile(payload()) as zf:
                members = zf.infolist()
                total = sum(m.file_size for m in members) or 1
                done = 0
                for member in members:
                    zf.extract(member, target)
                    done += member.file_size
                    self.root.after(0, lambda v=done / total * 100: self.bar.configure(value=v))
                    self.set_status(f"Copying {Path(member.filename).name}")
            exe = target / win.EXE_NAME
            self.set_status("Creating shortcuts...")
            win.create_shortcut("Programs", exe, target)
            if self.desktop.get():
                win.create_shortcut("Desktop", exe, target)
            win.set_run_at_startup(exe, self.autostart.get())
            win.register_uninstaller(target, VERSION, total // 1024)
        except Exception as exc:  # noqa: BLE001
            self.error = f"{type(exc).__name__}: {exc}"

    def finish(self) -> None:
        if self.error:
            messagebox.showerror("Tangerine Setup", f"Installation failed:\n{self.error}")
            self.button.state(["!disabled"])
            return
        self.bar.configure(value=100)
        if self.launch.get():
            exe = Path(self.path.get()) / win.EXE_NAME
            subprocess.Popen([str(exe)], cwd=str(exe.parent), creationflags=subprocess.DETACHED_PROCESS)
        messagebox.showinfo("Tangerine Setup", "Tangerine is installed. Look for the tangerine icon near the clock.")
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()


if __name__ == "__main__":
    if "--silent" in sys.argv:  # automated checks: install with the defaults and no dialogs
        app = Installer()
        app.root.withdraw()
        app.launch.set(False)
        app.autostart.set("--autostart" in sys.argv)
        app.desktop.set(False)
        if "--dir" in sys.argv:
            app.path.set(sys.argv[sys.argv.index("--dir") + 1])
        app.work()
        print(app.error or "installed")
        sys.exit(1 if app.error else 0)
    Installer().run()
