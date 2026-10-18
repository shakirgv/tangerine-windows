"""Resize an image."""

from __future__ import annotations

from PIL import Image


def resize_image(img: Image.Image, width: int, height: int) -> Image.Image:
    if width < 1 or height < 1:
        raise ValueError("Width and height must be at least 1 px")
    return img.resize((width, height), Image.Resampling.LANCZOS)


def fit_long_side(size: tuple[int, int], long_side: int) -> tuple[int, int]:
    """Size scaled so its longer side equals long_side (aspect kept)."""
    w, h = size
    scale = long_side / max(w, h)
    return max(1, round(w * scale)), max(1, round(h * scale))
