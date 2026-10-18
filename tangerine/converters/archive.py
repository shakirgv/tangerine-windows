"""ZIP and extract."""

from __future__ import annotations

import zipfile
from pathlib import Path

from ..utils import Cancelled, cancelled, output_dir, output_path, unique_path


def _add(zf: zipfile.ZipFile, path: Path, base: Path) -> None:
    if path.is_dir():
        for child in sorted(path.rglob("*")):
            if cancelled():
                raise Cancelled()
            if child.is_file():
                zf.write(child, child.relative_to(base))
    else:
        zf.write(path, path.relative_to(base))


def zip_files(files: list[Path], name: str | None = None) -> list[Path]:
    """Zip one or more files/folders. Several items go into '<first>_files.zip'."""
    first = files[0]
    dest = output_path(first, ".zip") if len(files) == 1 else output_path(first, ".zip", "_files")
    if len(files) > 1 and name:
        dest = unique_path(output_dir(first) / f"{name}.zip")
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for path in files:
            _add(zf, path, path.parent)
    return [dest]


def zip_one(src: Path) -> list[Path]:
    return zip_files([src])


def extract_zip(src: Path) -> list[Path]:
    """Extract into a '<name>' folder next to the archive (never overwrites)."""
    folder = unique_path(output_dir(src) / src.stem)
    root = folder.resolve()
    with zipfile.ZipFile(src) as zf:
        for member in zf.infolist():
            target = (folder / member.filename).resolve()
            if root != target and root not in target.parents:  # block path traversal
                raise ValueError(f"Unsafe path in archive: {member.filename}")
        zf.extractall(folder)
    return [folder]
