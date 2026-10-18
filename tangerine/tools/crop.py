"""Crop helpers shared by the crop window."""

from __future__ import annotations

from PIL import Image

# label -> width / height ratio (None means free)
ASPECTS: dict[str, float | None] = {
    "Free": None,
    "1:1": 1.0,
    "16:9": 16 / 9,
    "9:16": 9 / 16,
    "4:3": 4 / 3,
    "3:4": 3 / 4,
}


def fit_box(box: tuple[float, float, float, float], aspect: float) -> tuple[float, float, float, float]:
    """Largest box with the given aspect that fits inside box and shares its center."""
    x, y, w, h = box
    if w / h > aspect:
        new_w, new_h = h * aspect, h
    else:
        new_w, new_h = w, w / aspect
    return x + (w - new_w) / 2, y + (h - new_h) / 2, new_w, new_h


def crop_image(img: Image.Image, box: tuple[float, float, float, float]) -> Image.Image:
    """Crop to (x, y, w, h) in pixels, clamped to the image."""
    x, y, w, h = box
    left = max(0, round(x))
    top = max(0, round(y))
    right = min(img.width, round(x + w))
    bottom = min(img.height, round(y + h))
    if right - left < 1 or bottom - top < 1:
        raise ValueError("The crop area is empty")
    return img.crop((left, top, right, bottom))
