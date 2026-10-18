"""PDF conversions: images, plain text and DOCX."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz  # PyMuPDF

from ..utils import output_dir, output_path, unique_path


def pdf_to_images(src: Path, fmt: str, dpi: int = 150) -> list[Path]:
    """Render every page to PNG or JPG. Several pages go into a '<name>_pages' folder."""
    ext = ".png" if fmt.upper() == "PNG" else ".jpg"
    results: list[Path] = []
    with fitz.open(src) as doc:
        if doc.page_count == 0:
            raise ValueError("The PDF has no pages")
        folder = None
        if doc.page_count > 1:
            folder = unique_path(output_dir(src) / f"{src.stem}_pages")
            folder.mkdir(parents=True)
        for index, page in enumerate(doc, start=1):
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            if folder is None:
                dest = output_path(src, ext)
            else:
                dest = folder / f"page_{index:03d}{ext}"
            pix.save(dest)
            results.append(dest)
    return results


def pdf_to_txt(src: Path) -> list[Path]:
    dest = output_path(src, ".txt")
    with fitz.open(src) as doc:
        text = "\n\n".join(page.get_text() for page in doc)
    dest.write_text(text, encoding="utf-8")
    return [dest]


def pdf_to_docx(src: Path) -> list[Path]:
    from pdf2docx import Converter

    dest = output_path(src, ".docx")
    converter = Converter(str(src))
    try:
        converter.convert(str(dest))
    finally:
        converter.close()
    return [dest]
