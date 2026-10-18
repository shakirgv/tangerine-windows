"""Place an image on a gradient/color background with padding, rounded corners and a shadow."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from PIL import Image, ImageChops, ImageFilter

Color = tuple[int, int, int]


@dataclass(frozen=True)
class Background:
    name: str
    kind: str  # "solid", "gradient" or "transparent"
    c1: Color = (255, 255, 255)
    c2: Color = (255, 255, 255)
    angle: float = 135.0


PRESETS: list[Background] = [
    Background("Tangerine", "gradient", (255, 176, 59), (255, 94, 58), 135),
    Background("Sunset", "gradient", (255, 126, 179), (255, 117, 140), 120),
    Background("Ocean", "gradient", (56, 189, 248), (37, 99, 235), 135),
    Background("Mint", "gradient", (110, 231, 183), (16, 185, 129), 135),
    Background("Lavender", "gradient", (196, 181, 253), (124, 58, 237), 135),
    Background("Night", "gradient", (30, 41, 59), (15, 23, 42), 160),
    Background("White", "solid", (255, 255, 255)),
    Background("Light", "solid", (235, 238, 242)),
    Background("Black", "solid", (12, 12, 14)),
    Background("None", "transparent"),
]

RATIOS: dict[str, tuple[int, int] | None] = {
    "Auto": None,
    "1:1": (1, 1),
    "16:9": (16, 9),
    "4:5": (4, 5),
}


def _gradient(size: tuple[int, int], c1: Color, c2: Color, angle: float) -> Image.Image:
    cw, ch = size
    # Compute on a small grid and upscale: gradients are smooth, this keeps memory low.
    k = 256 / max(cw, ch)
    gw, gh = max(2, round(cw * k)), max(2, round(ch * k))
    rad = math.radians(angle)
    dx, dy = math.cos(rad), math.sin(rad)
    ys, xs = np.mgrid[0:gh, 0:gw].astype(np.float32)
    proj = (xs - gw / 2) * dx + (ys - gh / 2) * dy
    extent = abs(gw * dx) + abs(gh * dy)
    t = np.clip(proj / extent + 0.5, 0.0, 1.0)[..., None]
    arr = np.array(c1, np.float32) * (1 - t) + np.array(c2, np.float32) * t
    small = Image.fromarray(arr.astype(np.uint8), "RGB")
    return small.resize((cw, ch), Image.Resampling.BICUBIC).convert("RGBA")


def _make_background(bg: Background, size: tuple[int, int]) -> Image.Image:
    if bg.kind == "transparent":
        return Image.new("RGBA", size, (0, 0, 0, 0))
    if bg.kind == "solid":
        return Image.new("RGBA", size, (*bg.c1, 255))
    return _gradient(size, bg.c1, bg.c2, bg.angle)


def _rounded_mask(size: tuple[int, int], radius: int) -> Image.Image:
    w, h = size
    mask = Image.new("L", size, 255)
    r = min(radius, w // 2, h // 2)
    if r < 1:
        return mask
    circle = Image.new("L", (r * 8, r * 8), 0)
    from PIL import ImageDraw

    ImageDraw.Draw(circle).ellipse((0, 0, r * 8 - 1, r * 8 - 1), fill=255)
    circle = circle.resize((r * 2, r * 2), Image.Resampling.LANCZOS)
    tl = circle.crop((0, 0, r, r))
    mask.paste(tl, (0, 0))
    mask.paste(tl.transpose(Image.Transpose.FLIP_LEFT_RIGHT), (w - r, 0))
    mask.paste(tl.transpose(Image.Transpose.FLIP_TOP_BOTTOM), (0, h - r))
    mask.paste(tl.transpose(Image.Transpose.ROTATE_180), (w - r, h - r))
    return mask


def add_background(
    img: Image.Image,
    bg: Background,
    padding: float = 8,
    corners: float = 4,
    shadow: float = 35,
    ratio: tuple[int, int] | None = None,
) -> Image.Image:
    """Compose img on a background.

    padding: percent of the longer image side, corners: percent of the shorter side,
    shadow: 0-100, ratio: (w, h) of the final canvas or None for automatic.
    All values are relative, so a small preview looks like the full-size result.
    """
    img = img.convert("RGBA")
    w, h = img.size
    pad = round(max(w, h) * padding / 100)
    radius = round(min(w, h) * corners / 100)

    cw, ch = w + 2 * pad, h + 2 * pad
    if ratio:
        target = ratio[0] / ratio[1]
        if cw / ch < target:
            cw = round(ch * target)
        else:
            ch = round(cw / target)

    canvas = _make_background(bg, (cw, ch))
    x, y = (cw - w) // 2, (ch - h) // 2
    mask = _rounded_mask((w, h), radius)

    if shadow > 0:
        blur = max(1, round(max(w, h) * (0.008 + shadow / 100 * 0.04)))
        offset = round(blur * 0.6)
        opacity = 0.12 + 0.55 * shadow / 100
        layer = Image.new("L", (cw, ch), 0)
        layer.paste(mask, (x, y + offset))
        layer = layer.filter(ImageFilter.GaussianBlur(blur)).point(lambda v: int(v * opacity))
        black = Image.new("RGBA", (cw, ch), (0, 0, 0, 255))
        black.putalpha(layer)
        canvas = Image.alpha_composite(canvas, black)

    img.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    canvas.alpha_composite(img, (x, y))
    return canvas
