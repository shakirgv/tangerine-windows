"""Recent operations, kept on disk so Recent/Undo survive a restart."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

MAX_ENTRIES = 30


def _file() -> Path:
    return Path(os.environ.get("APPDATA") or Path.home()) / "Tangerine" / "history.json"


def load() -> list[dict]:
    try:
        return json.loads(_file().read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []


def _save(entries: list[dict]) -> None:
    try:
        _file().parent.mkdir(parents=True, exist_ok=True)
        _file().write_text(json.dumps(entries[-MAX_ENTRIES:], indent=1), encoding="utf-8")
    except OSError:
        pass


def add(label: str, outputs: list[Path]) -> None:
    entries = load()
    entries.append({"time": time.time(), "label": label, "outputs": [str(p) for p in outputs]})
    _save(entries)


def recent_outputs(limit: int = 10) -> list[tuple[str, Path]]:
    """Newest first: (label, path) for outputs that still exist."""
    found: list[tuple[str, Path]] = []
    for entry in reversed(load()):
        for out in entry["outputs"]:
            if Path(out).exists():
                found.append((entry["label"], Path(out)))
    return found[:limit]


def undo_last() -> list[Path]:
    """Move the outputs of the newest operation to the Recycle Bin. Returns what was removed."""
    from send2trash import send2trash

    entries = load()
    while entries:
        entry = entries.pop()
        removed = []
        for out in entry["outputs"]:
            path = Path(out)
            if path.exists():
                send2trash(str(path))
                removed.append(path)
        _save(entries)
        if removed:
            return removed
    return []
