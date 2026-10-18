"""Text recognition with the OCR engine that ships with Windows (no extra download)."""

from __future__ import annotations

import asyncio
import io
from pathlib import Path

from PIL import Image

from ..converters.image import flatten, open_image
from ..utils import output_path


async def _recognize(png: bytes) -> str:
    from winrt.windows.graphics.imaging import BitmapDecoder
    from winrt.windows.media.ocr import OcrEngine
    from winrt.windows.storage.streams import DataWriter, InMemoryRandomAccessStream

    engine = OcrEngine.try_create_from_user_profile_languages()
    if engine is None:
        raise RuntimeError("Windows has no OCR language installed (Settings > Time & language > Language).")
    stream = InMemoryRandomAccessStream()
    writer = DataWriter(stream)
    writer.write_bytes(png)
    await writer.store_async()
    writer.detach_stream()
    stream.seek(0)
    decoder = await BitmapDecoder.create_async(stream)
    bitmap = await decoder.get_software_bitmap_async()
    result = await engine.recognize_async(bitmap)
    return result.text


def ocr_image(img: Image.Image) -> str:
    """Recognize the text in a Pillow image."""
    from winrt.windows.media.ocr import OcrEngine

    limit = OcrEngine.max_image_dimension
    img = flatten(img)
    if max(img.size) > limit:
        img.thumbnail((limit, limit))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return asyncio.run(_recognize(buf.getvalue())).strip()


def ocr_to_txt(src: Path) -> list[Path]:
    """Image -> '<name>_ocr.txt'. PDF pages are rendered first."""
    if src.suffix.lower() == ".pdf":
        import pymupdf

        parts = []
        with pymupdf.open(src) as doc:
            if doc.needs_pass:
                raise ValueError("The PDF is password protected. Unlock it first.")
            for page in doc:
                pix = page.get_pixmap(dpi=200, alpha=False)
                img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
                parts.append(ocr_image(img))
        text = "\n\n".join(parts)
    else:
        text = ocr_image(open_image(src))
    dest = output_path(src, ".txt", "_ocr")
    dest.write_text(text, encoding="utf-8")
    return [dest]
