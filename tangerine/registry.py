"""File type -> radial menu actions.

A file kind maps to one or more groups. Each group becomes a ring in the radial menu;
the first group is the outer ring.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from . import settings

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif", ".tif", ".tiff", ".bmp", ".avif", ".gif"}
PDF_EXTS = {".pdf"}
DOCX_EXTS = {".docx"}
TEXT_EXTS = {".txt", ".md", ".markdown"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wmv", ".flv"}
AUDIO_EXTS = {".mp3", ".wav", ".flac", ".ogg", ".m4a", ".aac", ".wma", ".opus"}
ARCHIVE_EXTS = {".zip"}

KIND_LABELS = {
    "image": "Images",
    "pdf": "PDF",
    "docx": "Word (DOCX)",
    "text": "Text / Markdown",
    "video": "Video",
    "audio": "Audio",
    "archive": "ZIP archives",
    "folder": "Folders",
    "other": "Other files",
}

Handler = Callable[[Path], "list[Path]"]
BatchHandler = Callable[["list[Path]"], "list[Path]"]


@dataclass(frozen=True)
class Action:
    id: str
    label: str
    handler: Handler | None = None  # runs once per file in a worker thread
    batch: BatchHandler | None = None  # runs once for all files (merge, zip all)
    window: str | None = None  # name of a tool window (see ui.tool_windows) opened instead
    convert: bool = False  # produces the same content in another format (may delete the original)


@dataclass(frozen=True)
class Group:
    name: str
    actions: tuple[Action, ...]


def kind_of(path: Path) -> str:
    if path.is_dir():
        return "folder"
    ext = path.suffix.lower()
    for kind, exts in (
        ("image", IMAGE_EXTS),
        ("pdf", PDF_EXTS),
        ("docx", DOCX_EXTS),
        ("text", TEXT_EXTS),
        ("video", VIDEO_EXTS),
        ("audio", AUDIO_EXTS),
        ("archive", ARCHIVE_EXTS),
    ):
        if ext in exts:
            return kind
    return "other"


def common_kind(paths: list[Path]) -> tuple[str | None, list[Path]]:
    """Kind of the first file and all files of that same kind."""
    if not paths:
        return None, []
    kind = kind_of(paths[0])
    return kind, [p for p in paths if kind_of(p) == kind]


# --- handler factories (imports are lazy so the app starts fast) ----------------------------


def _each(module: str, func: str, *args) -> Handler:
    def run(src: Path) -> list[Path]:
        result = getattr(importlib.import_module(module, __package__), func)(src, *args)
        return result if isinstance(result, list) else [result]

    return run


def _all(module: str, func: str) -> BatchHandler:
    def run(files: list[Path]) -> list[Path]:
        return getattr(importlib.import_module(module, __package__), func)(files)

    return run


def _act(id: str, label: str, module: str, func: str, *args, convert: bool = False) -> Action:
    return Action(id, label, handler=_each(module, func, *args), convert=convert)


def _win(id: str, label: str) -> Action:
    return Action(id, label, window=id)


_IMAGE_FORMATS = ["PNG", "WEBP", "HEIC", "TIFF", "PDF", "DOCX", "BMP", "AVIF", "JPG"]


def _same_format(ext: str, label: str) -> bool:
    ext = ext.lower().lstrip(".")
    aliases = {"jpg": "jpg", "jpeg": "jpg", "tif": "tiff", "heif": "heic"}
    return aliases.get(ext, ext) == label.lower()


_ZIP = _act("zip", "ZIP", ".converters.archive", "zip_one")


def _definitions(kind: str, ext: str) -> list[Group]:
    """All groups for a kind before multi-file filtering and user customization."""
    if kind == "image":
        convert = tuple(
            _act(f"to_{fmt.lower()}", fmt, ".converters.image", "convert_image", fmt, convert=True)
            for fmt in _IMAGE_FORMATS
            if not _same_format(ext, fmt)
        )
        edit = (
            _win("crop", "Crop"),
            _win("edit", "Edit"),
            _win("add_bg", "Add BG"),
            _win("redact", "Redact"),
            _act("rotate", "Rotate", ".tools.rotate", "rotate_clockwise"),
            _win("resize", "Resize"),
            _win("watermark", "Watermark"),
            _act("remove_bg", "Remove BG", ".tools.remove_bg", "remove_bg_file"),
        )
        utility = (
            _act("compress", "Compress", ".tools.compress", "compress"),
            _win("metadata", "Metadata"),
            _act("upscale", "Upscale", ".tools.upscale", "upscale_2x"),
            _act("ocr", "OCR", ".tools.ocr", "ocr_to_txt"),
            _ZIP,
        )
        return [Group("Convert", convert), Group("Edit", edit), Group("Utility", utility)]
    if kind == "pdf":
        convert = (
            _act("to_docx", "DOCX", ".converters.pdf", "pdf_to_docx", convert=True),
            _act("to_txt", "TXT", ".converters.pdf", "pdf_to_txt", convert=True),
            _act("to_jpg", "JPG", ".converters.pdf", "pdf_to_images", "JPG", convert=True),
            _act("to_png", "PNG", ".converters.pdf", "pdf_to_images", "PNG", convert=True),
        )
        tools = (
            _win("pdf_pages", "Pages"),
            _act("pdf_compress", "Compress", ".tools.pdf_tools", "compress_pdf"),
            _act("pdf_split", "Split", ".tools.pdf_tools", "split_pdf"),
            _win("pdf_protect", "Protect"),
            _win("pdf_unlock", "Unlock"),
            _win("pdf_redact", "Redact"),
            _act("ocr", "OCR", ".tools.ocr", "ocr_to_txt"),
            _ZIP,
        )
        return [Group("Convert", convert), Group("Tools", tools)]
    if kind == "docx":
        convert = (
            _act("to_pdf", "PDF", ".converters.word", "docx_to_pdf", convert=True),
            _act("to_txt", "TXT", ".converters.word", "docx_to_txt", convert=True),
        )
        return [Group("Convert", convert), Group("Tools", (_ZIP,))]
    if kind == "text":
        convert = (
            _act("to_pdf", "PDF", ".converters.text", "text_to_pdf", convert=True),
            _act("to_docx", "DOCX", ".converters.text", "text_to_docx", convert=True),
        )
        return [Group("Convert", convert), Group("Tools", (_ZIP,))]
    if kind in ("video", "audio"):
        from .converters.media import AUDIO_TARGETS, VIDEO_TARGETS

        video = kind == "video"
        convert = tuple(
            _act(f"to_{label.lower()}", label, ".converters.media", "convert_media", label, video, convert=True)
            for label in (VIDEO_TARGETS if video else AUDIO_TARGETS)
            if not _same_format(ext, label)
        )
        tools = [_win("trim", "Trim"), _act("media_compress", "Compress", ".converters.media", "compress_media")]
        if video:
            tools.append(_act("mute", "Mute", ".converters.media", "mute_video"))
        tools.append(_ZIP)
        return [Group("Convert", convert), Group("Tools", tuple(tools))]
    if kind == "archive":
        return [Group("Tools", (_act("extract", "Extract", ".converters.archive", "extract_zip"), _ZIP))]
    return [Group("Tools", (_ZIP,))]  # folders and unknown files


def _combine_group(kind: str) -> Group:
    actions = []
    if kind == "image":
        actions.append(Action("images_to_pdf", "1 PDF", batch=_all(".tools.pdf_tools", "images_to_pdf")))
    if kind == "pdf":
        actions.append(Action("merge", "Merge", batch=_all(".tools.pdf_tools", "merge_pdfs")))
    actions.append(Action("zip_all", "ZIP all", batch=_all(".converters.archive", "zip_files")))
    return Group("Combine", tuple(actions))


def _customize(kind: str, groups: list[Group]) -> list[Group]:
    prefs = (settings.get("slices") or {}).get(kind, {})
    hidden = set(prefs.get("hidden", []))
    order = prefs.get("order", [])
    result = []
    for group in groups:
        actions = [a for a in group.actions if a.id not in hidden]
        if order:
            actions.sort(key=lambda a: order.index(a.id) if a.id in order else len(order))
        if actions:
            result.append(Group(group.name, tuple(actions)))
    return result


def groups_for(kind: str, ext: str, count: int = 1) -> list[Group]:
    """Ring groups for a file kind (outer first). A format slice equal to the source is left out.

    With several files, tool windows (one file at a time) are dropped and a Combine ring is added.
    """
    groups = _customize(kind, _definitions(kind, ext.lower()))
    if count > 1:
        groups = [
            Group(g.name, tuple(a for a in g.actions if a.window is None)) for g in groups
        ]
        groups = [g for g in groups if g.actions]
        groups.append(_combine_group(kind))
    return groups


def all_groups(kind: str) -> list[Group]:
    """Every group of a kind ignoring customization (for the settings dialog)."""
    return _definitions(kind, "")
