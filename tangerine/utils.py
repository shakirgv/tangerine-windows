"""Small shared helpers for output paths and file sizes."""

from __future__ import annotations

from pathlib import Path

from . import settings


def unique_path(path: Path) -> Path:
    """Return path, or 'name (1).ext', 'name (2).ext'... if it already exists."""
    if not path.exists():
        return path
    i = 1
    while True:
        candidate = path.with_name(f"{path.stem} ({i}){path.suffix}")
        if not candidate.exists():
            return candidate
        i += 1


def output_dir(src: Path) -> Path:
    custom = settings.get("output_dir")
    folder = Path(custom) if custom else src.parent
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def output_path(src: Path, ext: str | None = None, tag: str = "") -> Path:
    """Free output path for a file derived from src (same name, new extension/tag)."""
    ext = ext if ext is not None else src.suffix
    return unique_path(output_dir(src) / f"{src.stem}{tag}{ext}")


def human_size(num: float) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if num < 1024 or unit == "GB":
            return f"{num:.0f} {unit}" if unit == "B" else f"{num:.1f} {unit}"
        num /= 1024
    return f"{num:.1f} GB"
