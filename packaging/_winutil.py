"""Windows helpers shared by the installer and uninstaller (shortcuts, registry, process control)."""

from __future__ import annotations

import subprocess
import winreg
from pathlib import Path

APP_NAME = "Tangerine"
EXE_NAME = "Tangerine.exe"
RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
UNINSTALL_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\Tangerine"
NO_WINDOW = subprocess.CREATE_NO_WINDOW


def powershell(script: str) -> str:
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
        capture_output=True,
        text=True,
        creationflags=NO_WINDOW,
    )
    return proc.stdout.strip()


def special_folder(name: str) -> Path:
    """name: 'Desktop' or 'Programs' (the per-user Start Menu programs folder)."""
    return Path(powershell(f"[Environment]::GetFolderPath('{name}')"))


def shortcut_path(where: str) -> Path:
    return special_folder(where) / f"{APP_NAME}.lnk"


def create_shortcut(where: str, target: Path, workdir: Path) -> None:
    lnk = shortcut_path(where)
    powershell(
        f'$s=(New-Object -ComObject WScript.Shell).CreateShortcut("{lnk}");'
        f'$s.TargetPath="{target}";$s.WorkingDirectory="{workdir}";$s.IconLocation="{target},0";$s.Save()'
    )


def remove_shortcut(where: str) -> None:
    try:
        shortcut_path(where).unlink(missing_ok=True)
    except OSError:
        pass


def stop_app() -> None:
    subprocess.run(["taskkill", "/F", "/IM", EXE_NAME], capture_output=True, creationflags=NO_WINDOW)


def set_run_at_startup(exe: Path, on: bool) -> None:
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE) as key:
        if on:
            winreg.SetValueEx(key, APP_NAME, 0, winreg.REG_SZ, f'"{exe}" --hidden')
        else:
            try:
                winreg.DeleteValue(key, APP_NAME)
            except FileNotFoundError:
                pass


def register_uninstaller(install_dir: Path, version: str, size_kb: int) -> None:
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY) as key:
        values = {
            "DisplayName": APP_NAME,
            "DisplayVersion": version,
            "Publisher": APP_NAME,
            "InstallLocation": str(install_dir),
            "DisplayIcon": str(install_dir / EXE_NAME),
            "UninstallString": f'"{install_dir / "Uninstall.exe"}"',
        }
        for name, value in values.items():
            winreg.SetValueEx(key, name, 0, winreg.REG_SZ, value)
        winreg.SetValueEx(key, "EstimatedSize", 0, winreg.REG_DWORD, size_kb)
        winreg.SetValueEx(key, "NoModify", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "NoRepair", 0, winreg.REG_DWORD, 1)


def unregister_uninstaller() -> None:
    try:
        winreg.DeleteKey(winreg.HKEY_CURRENT_USER, UNINSTALL_KEY)
    except FileNotFoundError:
        pass
