"""Persistent user settings stored as JSON in %APPDATA%/Tangerine."""

from __future__ import annotations

import json
import os
from pathlib import Path

TRIGGERS = {
    "ctrl+shift": "Ctrl + Shift",
    "alt": "Alt",
    "ctrl+alt": "Ctrl + Alt",
}

DEFAULTS = {
    "trigger": "ctrl+shift",
    "output_dir": "",  # empty string means "next to the original file"
    "enabled": True,
}

_data: dict | None = None


def _file() -> Path:
    base = Path(os.environ.get("APPDATA") or Path.home()) / "Tangerine"
    return base / "settings.json"


def _load() -> dict:
    global _data
    if _data is None:
        _data = dict(DEFAULTS)
        try:
            _data.update(json.loads(_file().read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return _data


def get(key: str):
    return _load().get(key, DEFAULTS.get(key))


def set(key: str, value) -> None:  # noqa: A001 - mirrors dict-like API
    data = _load()
    data[key] = value
    try:
        path = _file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except OSError:
        pass
