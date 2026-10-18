"""Rotate an image."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from ..converters.image import open_image, save_image
from ..utils import output_path


def rotate_clockwise(src: Path) -> list[Path]:
    """Save a 90 degree clockwise copy as '<name>_rotated.<ext>'."""
    img = open_image(src).transpose(Image.Transpose.ROTATE_270)
    dest = output_path(src, src.suffix, "_rotated")
    save_image(img, dest)
    return [dest]
