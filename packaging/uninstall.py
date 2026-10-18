"""Tangerine uninstaller (shipped inside the install folder as Uninstall.exe)."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path
from tkinter import Tk, messagebox

import _winutil as win


def main() -> int:
    install_dir = Path(sys.executable).resolve().parent
    silent = "--silent" in sys.argv
    root = Tk()
    root.withdraw()
    if not silent and not messagebox.askyesno("Tangerine", "Remove Tangerine from this computer?"):
        return 0
    if silent:
        remove_data = "--purge" in sys.argv  # never delete settings in a silent run unless asked
    else:
        remove_data = messagebox.askyesno("Tangerine", "Also delete your settings and history?")

    win.stop_app()
    win.set_run_at_startup(install_dir / win.EXE_NAME, False)
    win.remove_shortcut("Programs")
    win.remove_shortcut("Desktop")
    win.unregister_uninstaller()
    if remove_data:
        shutil.rmtree(Path(os.environ.get("APPDATA", "")) / "Tangerine", ignore_errors=True)
    # This exe runs from the folder, so a detached command removes the folder after we exit.
    subprocess.Popen(
        f'cmd /c ping -n 3 127.0.0.1 >nul & rmdir /s /q "{install_dir}"',
        creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
    )
    if not silent:
        messagebox.showinfo("Tangerine", "Tangerine was removed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
