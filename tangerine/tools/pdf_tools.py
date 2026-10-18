"""PDF tools: merge, split, compress, protect, unlock, redact and page organizing."""

from __future__ import annotations

import re
from pathlib import Path

import pymupdf

from ..converters.image import flatten, open_image
from ..converters.pdf import open_pdf
from ..utils import output_dir, output_path, unique_path


def merge_pdfs(files: list[Path]) -> list[Path]:
    """Append all PDFs in the given order into '<first>_merged.pdf'."""
    out = pymupdf.open()
    try:
        for path in files:
            with open_pdf(path) as doc:
                out.insert_pdf(doc)
        dest = output_path(files[0], ".pdf", "_merged")
        out.save(dest, garbage=3, deflate=True)
    finally:
        out.close()
    return [dest]


def images_to_pdf(files: list[Path]) -> list[Path]:
    """One page per image into '<first>_combined.pdf'."""
    pages = [flatten(open_image(p)) for p in files]
    dest = output_path(files[0], ".pdf", "_combined")
    pages[0].save(dest, "PDF", save_all=True, append_images=pages[1:], resolution=150.0)
    return [dest]


def split_pdf(src: Path) -> list[Path]:
    """Every page becomes its own PDF inside '<name>_split'."""
    results: list[Path] = []
    with open_pdf(src) as doc:
        folder = unique_path(output_dir(src) / f"{src.stem}_split")
        folder.mkdir(parents=True)
        for index in range(doc.page_count):
            part = pymupdf.open()
            part.insert_pdf(doc, from_page=index, to_page=index)
            dest = folder / f"page_{index + 1:03d}.pdf"
            part.save(dest)
            part.close()
            results.append(dest)
    return [folder]


def compress_pdf(src: Path) -> list[Path]:
    """Recompress images and drop unused objects into '<name>_compressed.pdf'."""
    dest = output_path(src, ".pdf", "_compressed")
    with open_pdf(src) as doc:
        try:
            doc.rewrite_images(dpi_threshold=150, dpi_target=110, quality=70)
        except Exception:  # older PyMuPDF or unusual images: structure cleanup still helps
            pass
        doc.save(dest, garbage=4, deflate=True, deflate_images=True, deflate_fonts=True, clean=True)
    return [dest]


def protect_pdf(src: Path, password: str) -> list[Path]:
    """AES-256 encrypted copy '<name>_protected.pdf'; the same password opens and edits it."""
    if not password:
        raise ValueError("Enter a password")
    dest = output_path(src, ".pdf", "_protected")
    with open_pdf(src) as doc:
        doc.save(
            dest,
            encryption=pymupdf.PDF_ENCRYPT_AES_256,
            owner_pw=password,
            user_pw=password,
            garbage=3,
            deflate=True,
        )
    return [dest]


def unlock_pdf(src: Path, password: str) -> list[Path]:
    """Decrypted copy '<name>_unlocked.pdf'."""
    doc = pymupdf.open(src)
    try:
        if doc.needs_pass and not doc.authenticate(password):
            raise ValueError("Wrong password")
        dest = output_path(src, ".pdf", "_unlocked")
        doc.save(dest, encryption=pymupdf.PDF_ENCRYPT_NONE, garbage=3, deflate=True)
    finally:
        doc.close()
    return [dest]


PATTERNS = {
    "Email addresses": r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+",
    "Phone numbers": r"\+?\d[\d\s().-]{7,}\d",
    "Long numbers (card, IBAN, IDs)": r"\b[A-Z]{0,2}\d(?:[\s-]?\d){7,}\b",
}


def redact_pdf(src: Path, terms: list[str], patterns: list[str]) -> tuple[list[Path], int]:
    """Permanently remove text. Returns ([output], number of areas removed)."""
    terms = [t for t in (t.strip() for t in terms) if t]
    if not terms and not patterns:
        raise ValueError("Enter text to redact or choose a pattern")
    dest = output_path(src, ".pdf", "_redacted")
    count = 0
    with open_pdf(src) as doc:
        for page in doc:
            wanted = set(terms)
            text = page.get_text()
            for pattern in patterns:
                wanted.update(m.group(0).strip() for m in re.finditer(PATTERNS[pattern], text))
            for needle in wanted:
                for rect in page.search_for(needle):
                    page.add_redact_annot(rect, fill=(0, 0, 0))
                    count += 1
            page.apply_redactions()
        doc.save(dest, garbage=4, deflate=True)
    return [dest], count


def save_organized(src: Path, order: list[int], rotations: dict[int, int], dest_tag: str = "_edited") -> list[Path]:
    """New PDF from the pages in `order` (original indexes), adding rotations (degrees clockwise)."""
    if not order:
        raise ValueError("No pages selected")
    dest = output_path(src, ".pdf", dest_tag)
    with open_pdf(src) as doc:
        doc.select(order)
        for new_index, original in enumerate(order):
            extra = rotations.get(original, 0)
            if extra:
                page = doc[new_index]
                page.set_rotation((page.rotation + extra) % 360)
        doc.save(dest, garbage=3, deflate=True)
    return [dest]
