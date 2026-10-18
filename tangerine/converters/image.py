"""Image loading, saving and format conversion."""

from __future__ import annotations

import io
from pathlib import Path

import pillow_heif
from PIL import Image, ImageOps

from .. import settings
from ..utils import output_path

pillow_heif.register_heif_opener()
try:
    pillow_heif.register_avif_opener()
except Exception:  # AVIF support is optional
    pass

# label -> (Pillow format name, extension)
FORMATS = {
    "PNG": ("PNG", ".png"),
    "JPG": ("JPEG", ".jpg"),
    "WEBP": ("WEBP", ".webp"),
    "HEIC": ("HEIF", ".heic"),
    "TIFF": ("TIFF", ".tiff"),
    "BMP": ("BMP", ".bmp"),
    "AVIF": ("AVIF", ".avif"),
    "PDF": ("PDF", ".pdf"),
    "DOCX": (None, ".docx"),
}

_SUFFIX_TO_FORMAT = {
    ".png": "PNG",
    ".jpg": "JPEG",
    ".jpeg": "JPEG",
    ".webp": "WEBP",
    ".heic": "HEIF",
    ".heif": "HEIF",
    ".tif": "TIFF",
    ".tiff": "TIFF",
    ".bmp": "BMP",
    ".avif": "AVIF",
    ".gif": "GIF",
    ".pdf": "PDF",
}

_NO_ALPHA = {"JPEG", "BMP", "PDF"}


def open_image(path: Path | str) -> Image.Image:
    """Open an image fully loaded, with EXIF orientation applied."""
    with Image.open(path) as img:
        img = ImageOps.exif_transpose(img)
        img.load()
        return img


def flatten(img: Image.Image, background=(255, 255, 255)) -> Image.Image:
    """Return an RGB copy; transparency is composited over the background."""
    if img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info):
        rgba = img.convert("RGBA")
        base = Image.new("RGB", rgba.size, background)
        base.paste(rgba, mask=rgba.getchannel("A"))
        return base
    return img.convert("RGB")


def save_image(img: Image.Image, dest: Path, pil_format: str | None = None) -> Path:
    """Save img to dest, choosing the Pillow format from the suffix unless given."""
    fmt = pil_format or _SUFFIX_TO_FORMAT.get(dest.suffix.lower(), "PNG")
    kwargs: dict = {}
    if fmt in _NO_ALPHA:
        img = flatten(img)
    elif img.mode not in ("RGB", "RGBA", "L", "LA", "P", "1"):
        img = img.convert("RGBA")
    quality = int(settings.get("quality"))
    if fmt == "JPEG":
        kwargs = {"quality": quality, "optimize": True}
    elif fmt == "WEBP":
        kwargs = {"quality": quality}
    elif fmt in ("HEIF", "AVIF"):
        kwargs = {"quality": quality}
        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA" if "A" in img.mode else "RGB")
    elif fmt == "PDF":
        kwargs = {"resolution": 150.0}
    elif fmt == "TIFF":
        kwargs = {"compression": "tiff_adobe_deflate"}
    img.save(dest, fmt, **kwargs)
    return dest


def _save_docx(img: Image.Image, dest: Path) -> Path:
    from docx import Document
    from docx.shared import Emu

    doc = Document()
    section = doc.sections[0]
    max_w = section.page_width - section.left_margin - section.right_margin
    max_h = section.page_height - section.top_margin - section.bottom_margin

    buf = io.BytesIO()
    flatten(img).save(buf, "PNG")
    buf.seek(0)

    natural_w = img.width * 9525  # 96 dpi in EMU
    natural_h = img.height * 9525
    scale = min(1.0, max_w / natural_w, max_h / natural_h)
    doc.add_picture(buf, width=Emu(int(natural_w * scale)), height=Emu(int(natural_h * scale)))
    doc.save(dest)
    return dest


def convert_image(src: Path, target: str) -> Path:
    """Convert src to the target label from FORMATS; result is saved next to the original."""
    pil_format, ext = FORMATS[target]
    dest = output_path(src, ext)
    img = open_image(src)
    if target == "DOCX":
        return _save_docx(img, dest)
    return save_image(img, dest, pil_format)
