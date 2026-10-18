"""Enlarge an image 2x with Lanczos resampling and light sharpening (classic, not AI)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageFilter

from ..converters.image import open_image, save_image
from ..utils import output_path


def upscale_2x(src: Path) -> list[Path]:
    img = open_image(src)
    big = img.resize((img.width * 2, img.height * 2), Image.Resampling.LANCZOS)
    if big.mode in ("RGB", "RGBA", "L"):
        big = big.filter(ImageFilter.UnsharpMask(radius=1.4, percent=60, threshold=2))
    dest = output_path(src, src.suffix, "_2x")
    save_image(big, dest)
    return [dest]
