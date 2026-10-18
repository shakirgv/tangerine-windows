"""Compress an image to a smaller file."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from .. import settings
from ..converters.image import flatten, open_image
from ..utils import output_path


def compress(src: Path, quality: int | None = None) -> list[Path]:
    """Save a smaller copy as '<name>_compressed.<ext>' next to the original."""
    ext = src.suffix.lower()
    if ext == ".gif":
        from ..converters.media import gif_optimize

        return gif_optimize(src)
    quality = int(settings.get("compress_quality")) if quality is None else quality
    img = open_image(src)

    if ext in (".jpg", ".jpeg"):
        dest = output_path(src, ".jpg", "_compressed")
        flatten(img).save(dest, "JPEG", quality=quality, optimize=True, progressive=True)
    elif ext == ".png":
        dest = output_path(src, ".png", "_compressed")
        rgba = img.convert("RGBA")
        method = Image.Quantize.FASTOCTREE
        rgba.quantize(colors=256, method=method).save(dest, "PNG", optimize=True)
    elif ext == ".webp":
        dest = output_path(src, ".webp", "_compressed")
        img.save(dest, "WEBP", quality=quality, method=6)
    elif ext in (".heic", ".heif"):
        dest = output_path(src, ".heic", "_compressed")
        img.convert("RGB").save(dest, "HEIF", quality=quality)
    elif ext == ".avif":
        dest = output_path(src, ".avif", "_compressed")
        img.convert("RGB").save(dest, "AVIF", quality=quality)
    elif ext in (".tif", ".tiff"):
        dest = output_path(src, ".tiff", "_compressed")
        img.save(dest, "TIFF", compression="tiff_adobe_deflate")
    else:  # BMP, GIF and anything else become an optimized PNG
        dest = output_path(src, ".png", "_compressed")
        img.save(dest, "PNG", optimize=True)
    return [dest]
