"""Hide parts of an image: black boxes, blur or pixelation."""

from __future__ import annotations

from PIL import Image, ImageDraw, ImageFilter

STYLES = ("Black box", "Blur", "Pixelate")


def redact(img: Image.Image, rects: list[tuple[float, float, float, float]], style: str = "Black box") -> Image.Image:
    """Cover each (x, y, w, h) rectangle in image pixels."""
    out = img.convert("RGBA")
    for x, y, w, h in rects:
        box = (max(0, round(x)), max(0, round(y)), min(out.width, round(x + w)), min(out.height, round(y + h)))
        if box[2] - box[0] < 1 or box[3] - box[1] < 1:
            continue
        if style == "Black box":
            ImageDraw.Draw(out).rectangle((box[0], box[1], box[2] - 1, box[3] - 1), fill=(0, 0, 0, 255))
            continue
        region = out.crop(box)
        if style == "Blur":
            radius = max(8, min(region.size) // 3)
            region = region.filter(ImageFilter.GaussianBlur(radius))
        else:
            block = max(8, min(region.size) // 6)
            small = region.resize(
                (max(1, region.width // block), max(1, region.height // block)), Image.Resampling.BILINEAR
            )
            region = small.resize(region.size, Image.Resampling.NEAREST)
        out.paste(region, box)
    return out
