"""Basic image adjustments for the Edit window."""

from __future__ import annotations

from PIL import Image, ImageEnhance


def adjust(
    img: Image.Image,
    brightness: int = 0,
    contrast: int = 0,
    saturation: int = 0,
    sharpness: int = 0,
    rotation: int = 0,
    flip_h: bool = False,
    flip_v: bool = False,
) -> Image.Image:
    """Sliders run from -100 to 100 (0 means unchanged). rotation is clockwise degrees (multiple of 90)."""
    alpha = img.getchannel("A") if img.mode in ("RGBA", "LA") else None
    out = img.convert("RGB")
    for enhancer, value in (
        (ImageEnhance.Brightness, brightness),
        (ImageEnhance.Contrast, contrast),
        (ImageEnhance.Color, saturation),
        (ImageEnhance.Sharpness, sharpness),
    ):
        if value:
            out = enhancer(out).enhance(1 + value / 100)
    if alpha is not None:
        out.putalpha(alpha)
    if flip_h:
        out = out.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
    if flip_v:
        out = out.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    turns = (rotation // 90) % 4
    if turns:
        out = out.transpose({1: Image.Transpose.ROTATE_270, 2: Image.Transpose.ROTATE_180, 3: Image.Transpose.ROTATE_90}[turns])
    return out
