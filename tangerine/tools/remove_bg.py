"""Remove a plain background by flood filling from the image border (works best on solid backdrops)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from ..converters.image import open_image, save_image
from ..utils import output_path


def remove_background(img: Image.Image, tolerance: int = 28) -> Image.Image:
    rgb = img.convert("RGB")
    w, h = rgb.size
    # Fill from every border pixel region with a marker color that does not occur in the picture.
    marker = (255, 0, 255)
    work = rgb.copy()
    arr = np.asarray(work)
    while (arr == marker).all(axis=2).any():
        marker = tuple(int(v) for v in np.random.randint(0, 256, 3))
    seeds = [(0, 0), (w - 1, 0), (0, h - 1), (w - 1, h - 1)]
    seeds += [(w // 2, 0), (w // 2, h - 1), (0, h // 2), (w - 1, h // 2)]
    for seed in seeds:
        if work.getpixel(seed) != marker:
            ImageDraw.floodfill(work, seed, marker, thresh=tolerance)
    background = (np.asarray(work) == np.array(marker)).all(axis=2)
    alpha = Image.fromarray(np.where(background, 0, 255).astype(np.uint8), "L")
    alpha = alpha.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.2))  # trim halo, soften edge
    if img.mode in ("RGBA", "LA"):
        alpha = ImageChops.multiply(alpha, img.getchannel("A"))
    out = img.convert("RGBA")
    out.putalpha(alpha)
    return out


def remove_bg_file(src: Path) -> list[Path]:
    dest = output_path(src, ".png", "_nobg")
    save_image(remove_background(open_image(src)), dest, "PNG")
    return [dest]
