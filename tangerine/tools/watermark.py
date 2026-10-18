"""Text watermark."""

from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

POSITIONS = ["Bottom right", "Bottom left", "Top right", "Top left", "Center", "Tiled"]
COLORS = {"White": (255, 255, 255), "Black": (0, 0, 0), "Orange": (255, 138, 31)}

_FONTS = [r"C:\Windows\Fonts\segoeuib.ttf", r"C:\Windows\Fonts\arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf"]


def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default(size)


def add_watermark(
    img: Image.Image,
    text: str,
    position: str = "Bottom right",
    size: int = 5,
    opacity: int = 60,
    color: str = "White",
) -> Image.Image:
    """size: font height as percent of the shorter side; opacity 0-100."""
    base = img.convert("RGBA")
    if not text.strip():
        return base
    px = max(10, round(min(base.size) * size / 100))
    font = _font(px)
    rgb = COLORS.get(color, COLORS["White"])
    fill = (*rgb, round(255 * opacity / 100))

    probe = ImageDraw.Draw(base)
    left, top, right, bottom = probe.textbbox((0, 0), text, font=font)
    tw, th = right - left, bottom - top
    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)
    margin = round(px * 0.8)

    if position == "Tiled":
        tile = Image.new("RGBA", (tw + px * 2, th + px * 2), (0, 0, 0, 0))
        ImageDraw.Draw(tile).text((px - left, px - top), text, font=font, fill=fill)
        tile = tile.rotate(30, expand=True, resample=Image.Resampling.BICUBIC)
        step_x, step_y = round(tile.width * 1.1), round(tile.height * 1.1)
        for y in range(-tile.height, base.height + tile.height, step_y):
            for x in range(-tile.width, base.width + tile.width, step_x):
                offset = (step_x // 2) if (y // step_y) % 2 else 0
                _paste_clipped(layer, tile, x + offset, y)
    else:
        pos_x = margin if "left" in position.lower() else base.width - tw - margin
        pos_y = margin if "top" in position.lower() else base.height - th - margin
        if position == "Center":
            pos_x, pos_y = (base.width - tw) // 2, (base.height - th) // 2
        draw.text((pos_x - left, pos_y - top), text, font=font, fill=fill)
    return Image.alpha_composite(base, layer)


def _paste_clipped(dest: Image.Image, tile: Image.Image, x: int, y: int) -> None:
    """alpha_composite that tolerates tiles hanging over the edges."""
    cx, cy = max(0, x), max(0, y)
    ex, ey = min(dest.width, x + tile.width), min(dest.height, y + tile.height)
    if ex <= cx or ey <= cy:
        return
    part = tile.crop((cx - x, cy - y, ex - x, ey - y))
    dest.alpha_composite(part, (cx, cy))
