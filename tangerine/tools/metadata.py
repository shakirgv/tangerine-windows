"""Read and strip image metadata (EXIF, GPS, text chunks)."""

from __future__ import annotations

from pathlib import Path

from PIL import ExifTags, Image, ImageOps

from ..converters.image import save_image
from ..utils import human_size, output_path


def _text(value) -> str:
    if isinstance(value, bytes):
        value = f"{len(value)} bytes" if len(value) > 64 else value.decode("utf-8", "replace")
    text = str(value)
    return text if len(text) <= 200 else text[:200] + "..."


def read_metadata(path: Path) -> list[tuple[str, str]]:
    """Return (name, value) rows describing the file and any embedded metadata."""
    rows: list[tuple[str, str]] = [("File", path.name), ("Size", human_size(path.stat().st_size))]
    with Image.open(path) as img:
        rows += [("Format", str(img.format)), ("Dimensions", f"{img.width} x {img.height} px"), ("Mode", img.mode)]
        exif = img.getexif()
        for tag_id, value in exif.items():
            rows.append((ExifTags.TAGS.get(tag_id, f"Tag {tag_id}"), _text(value)))
        for ifd_id in (ExifTags.IFD.Exif, ExifTags.IFD.GPSInfo):
            try:
                ifd = exif.get_ifd(ifd_id)
            except Exception:
                continue
            names = ExifTags.GPSTAGS if ifd_id == ExifTags.IFD.GPSInfo else ExifTags.TAGS
            prefix = "GPS " if ifd_id == ExifTags.IFD.GPSInfo else ""
            for tag_id, value in ifd.items():
                rows.append((prefix + names.get(tag_id, f"Tag {tag_id}"), _text(value)))
        for key, value in img.info.items():
            if key in ("exif", "icc_profile", "transparency"):
                if key != "transparency":
                    rows.append((key, f"{len(value)} bytes"))
            else:
                rows.append((str(key), _text(value)))
    return rows


def has_gps(path: Path) -> bool:
    with Image.open(path) as img:
        try:
            return bool(img.getexif().get_ifd(ExifTags.IFD.GPSInfo))
        except Exception:
            return False


def strip_metadata(src: Path) -> list[Path]:
    """Save '<name>_clean.<ext>' with pixels only: no EXIF, GPS, comments or profiles."""
    with Image.open(src) as img:
        clean = ImageOps.exif_transpose(img)
        clean.load()
    clean.info = {}
    dest = output_path(src, src.suffix, "_clean")
    save_image(clean, dest)
    return [dest]
