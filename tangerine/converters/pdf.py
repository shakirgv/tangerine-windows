"""PDF conversions: images, plain text and DOCX."""

from __future__ import annotations

from pathlib import Path

import pymupdf as fitz  # PyMuPDF

from .. import settings
from ..utils import output_dir, output_path, unique_path


def open_pdf(src: Path):
    """Open a PDF, with a clear error for password protected files."""
    doc = fitz.open(src)
    if doc.needs_pass:
        doc.close()
        raise ValueError("The PDF is password protected. Use Unlock first.")
    return doc


def pdf_to_images(src: Path, fmt: str, dpi: int | None = None) -> list[Path]:
    """Render every page to PNG or JPG. Several pages go into a '<name>_pages' folder."""
    dpi = dpi or int(settings.get("pdf_dpi"))
    ext = ".png" if fmt.upper() == "PNG" else ".jpg"
    results: list[Path] = []
    with open_pdf(src) as doc:
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
    with open_pdf(src) as doc:
        text = "\n\n".join(page.get_text() for page in doc)
    dest.write_text(text, encoding="utf-8")
    return [dest]


def pdf_to_docx(src: Path) -> list[Path]:
    from pdf2docx import Converter

    open_pdf(src).close()  # fail early on protected files
    dest = output_path(src, ".docx")
    converter = Converter(str(src))
    try:
        converter.convert(str(dest))
    finally:
        converter.close()
    return [dest]
