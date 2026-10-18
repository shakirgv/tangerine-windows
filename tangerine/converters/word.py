"""DOCX conversions."""

from __future__ import annotations

from pathlib import Path

from ..utils import output_path


def docx_to_txt(src: Path) -> list[Path]:
    from docx import Document

    doc = Document(str(src))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            lines.append("\t".join(cell.text for cell in row.cells))
    dest = output_path(src, ".txt")
    dest.write_text("\n".join(lines), encoding="utf-8")
    return [dest]
