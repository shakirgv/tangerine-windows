"""File type -> radial menu actions.

A file kind maps to one or more groups. Each group becomes a ring in the radial menu;
the first group is the outer ring.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".avif", ".gif"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus"}

Handler = Callable[[Path], "list[Path]"]


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    handler: Handler | None = None  # runs in a worker thread
    window: str | None = None  # name of a tool window (see ui.tool_windows) opened instead


@dataclass(frozen=True)
class Group:
    name: str
    actions: tuple[Action, ...]


def kind_of(path: Path) -> str | None:
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in PDF_EXTS:
        return "pdf"
    if ext in DOCX_EXTS:
        return "docx"
    if ext in VIDEO_EXTS:
        return "video"
    if ext in AUDIO_EXTS:
        return "audio"
    return None


def common_kind(paths: list[Path]) -> tuple[str | None, list[Path]]:
    """Kind of the first supported file and all files of that same kind."""
    for path in paths:
        kind = kind_of(path)
        if kind:
            return kind, [p for p in paths if kind_of(p) == kind]
    return None, []


# --- handlers (imports are lazy so the app starts fast) -------------------------------------


def _image_format(label: str) -> Handler:
    def run(src: Path) -> list[Path]:
        from .converters.image import convert_image

        return [convert_image(src, label)]

    return run


def _pdf_images(fmt: str) -> Handler:
    def run(src: Path) -> list[Path]:
        from .converters.pdf import pdf_to_images

        return pdf_to_images(src, fmt)

    return run


def _pdf_txt(src: Path) -> list[Path]:
    from .converters.pdf import pdf_to_txt

    return pdf_to_txt(src)


def _pdf_docx(src: Path) -> list[Path]:
    from .converters.pdf import pdf_to_docx

    return pdf_to_docx(src)


def _docx_txt(src: Path) -> list[Path]:
    from .converters.word import docx_to_txt

    return docx_to_txt(src)


def _media(label: str, video: bool) -> Handler:
    def run(src: Path) -> list[Path]:
        from .converters.media import convert_media

        return convert_media(src, label, video)

    return run


def _compress(src: Path) -> list[Path]:
    from .tools.compress import compress

    return compress(src)


def _rotate(src: Path) -> list[Path]:
    from .tools.rotate import rotate_clockwise

    return rotate_clockwise(src)


# --- action tables --------------------------------------------------------------------------

_IMAGE_FORMATS = ["PNG", "WEBP", "HEIC", "TIFF", "PDF", "DOCX", "BMP", "AVIF", "JPG"]
_IMAGE_TOOLS = (
    Action("compress", "Compress", handler=_compress),
    Action("metadata", "Metadata", window="metadata"),
    Action("edit", "Edit", window="edit"),
    Action("add_bg", "Add BG", window="add_bg"),
    Action("crop", "Crop", window="crop"),
    Action("redact", "Redact", window="redact"),
    Action("rotate", "Rotate", handler=_rotate),
)


def _same_format(ext: str, label: str) -> bool:
    ext = ext.lower().lstrip(".")
    aliases = {"jpg": "jpg", "jpeg": "jpg", "tif": "tiff", "heif": "heic"}
    return aliases.get(ext, ext) == label.lower()


def groups_for(kind: str, ext: str) -> list[Group]:
    """Ring groups for a file kind. A format slice that equals the source format is left out."""
    ext = ext.lower()
    if kind == "image":
        convert = tuple(
            Action(f"to_{fmt.lower()}", fmt, handler=_image_format(fmt))
            for fmt in _IMAGE_FORMATS
            if not _same_format(ext, fmt)
        )
        return [Group("Convert", convert), Group("Tools", _IMAGE_TOOLS)]
    if kind == "pdf":
        return [
            Group(
                "Convert",
                (
                    Action("to_docx", "DOCX", handler=_pdf_docx),
                    Action("to_txt", "TXT", handler=_pdf_txt),
                    Action("to_jpg", "JPG", handler=_pdf_images("JPG")),
                    Action("to_png", "PNG", handler=_pdf_images("PNG")),
                ),
            )
        ]
    if kind == "docx":
        return [Group("Convert", (Action("to_txt", "TXT", handler=_docx_txt),))]
    if kind == "video":
        from .converters.media import VIDEO_TARGETS

        return [
            Group(
                "Convert",
                tuple(
                    Action(f"to_{label.lower()}", label, handler=_media(label, True))
                    for label in VIDEO_TARGETS
                    if not _same_format(ext, label)
                ),
            )
        ]
    if kind == "audio":
        from .converters.media import AUDIO_TARGETS

        return [
            Group(
                "Convert",
                tuple(
                    Action(f"to_{label.lower()}", label, handler=_media(label, False))
                    for label in AUDIO_TARGETS
                    if not _same_format(ext, label)
                ),
            )
        ]
    return []
