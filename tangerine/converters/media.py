"""Video and audio through ffmpeg: conversion, trim, compress, mute."""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..utils import Cancelled, cancelled, output_path

# target label -> (extension, ffmpeg arguments placed after the input)
VIDEO_TARGETS = {
    "MP4": (".mp4", ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart"]),
    "WEBM": (".webm", ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-c:a", "libopus"]),
    "MKV": (".mkv", ["-c:v", "libx264", "-preset", "medium", "-crf", "23", "-c:a", "aac"]),
    "GIF": (".gif", ["-vf", "fps=12,scale=480:-1:flags=lanczos", "-an"]),
    "MP3": (".mp3", ["-vn", "-c:a", "libmp3lame", "-q:a", "2"]),
}

AUDIO_TARGETS = {
    "MP3": (".mp3", ["-c:a", "libmp3lame", "-q:a", "2"]),
    "WAV": (".wav", ["-c:a", "pcm_s16le"]),
    "FLAC": (".flac", ["-c:a", "flac"]),
    "OGG": (".ogg", ["-c:a", "libvorbis", "-q:a", "5"]),
    "M4A": (".m4a", ["-c:a", "aac", "-b:a", "192k"]),
}

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def ffmpeg_exe() -> str | None:
    """System ffmpeg if present, otherwise the binary bundled with imageio-ffmpeg."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return None


def run_ffmpeg(args: list[str], dest: Path) -> None:
    """Run ffmpeg, polling for cancellation. Removes the partial output on failure or cancel."""
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg was not found. Install it or run: pip install imageio-ffmpeg")
    # ffmpeg logs a lot to stderr; a pipe nobody reads would fill up and block it, so use a file.
    with tempfile.TemporaryFile() as log:
        proc = subprocess.Popen(
            [exe, "-y", "-nostdin", *args, str(dest)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=log,
            creationflags=_NO_WINDOW,
        )
        while proc.poll() is None:
            if cancelled():
                proc.kill()
                proc.wait()
                dest.unlink(missing_ok=True)
                raise Cancelled()
            time.sleep(0.1)
        if proc.returncode != 0:
            log.seek(0)
            tail = "\n".join(log.read().decode("utf-8", "replace").strip().splitlines()[-4:])
            dest.unlink(missing_ok=True)
            raise RuntimeError(f"ffmpeg failed:\n{tail}")


def duration_seconds(src: Path) -> float:
    """Media duration parsed from ffmpeg's banner (0.0 when unknown)."""
    exe = ffmpeg_exe()
    if not exe:
        return 0.0
    proc = subprocess.run([exe, "-i", str(src)], capture_output=True, text=True, errors="replace", creationflags=_NO_WINDOW)
    match = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", proc.stderr)
    if not match:
        return 0.0
    h, m, s = match.groups()
    return int(h) * 3600 + int(m) * 60 + float(s)


def convert_media(src: Path, target: str, video: bool) -> list[Path]:
    ext, args = (VIDEO_TARGETS if video else AUDIO_TARGETS)[target]
    dest = output_path(src, ext)
    run_ffmpeg(["-i", str(src), *args], dest)
    return [dest]


def compress_media(src: Path) -> list[Path]:
    """Smaller copy: H.264 CRF 28 for video, 128 kbps MP3 for audio."""
    from ..registry import kind_of

    if kind_of(src) == "audio":
        dest = output_path(src, ".mp3", "_compressed")
        run_ffmpeg(["-i", str(src), "-c:a", "libmp3lame", "-b:a", "128k"], dest)
    else:
        dest = output_path(src, ".mp4", "_compressed")
        run_ffmpeg(
            ["-i", str(src), "-c:v", "libx264", "-preset", "medium", "-crf", "28", "-c:a", "aac", "-b:a", "96k",
             "-movflags", "+faststart"],
            dest,
        )
    return [dest]


def mute_video(src: Path) -> list[Path]:
    dest = output_path(src, src.suffix, "_muted")
    run_ffmpeg(["-i", str(src), "-an", "-c:v", "copy"], dest)
    return [dest]


def trim_media(src: Path, start: float, end: float, reencode: bool = False) -> list[Path]:
    """Cut [start, end] seconds. Stream copy is instant but cuts on keyframes; re-encode is exact."""
    if end <= start:
        raise ValueError("The end time must be after the start time")
    dest = output_path(src, src.suffix, "_trimmed")
    args = ["-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src)]
    args += [] if reencode else ["-c", "copy"]
    run_ffmpeg(args, dest)
    return [dest]


def gif_optimize(src: Path) -> list[Path]:
    """Smaller GIF: lower frame rate, 75% size and an adaptive palette."""
    dest = output_path(src, ".gif", "_compressed")
    graph = "fps=10,scale=iw*0.75:-1:flags=lanczos,split[a][b];[a]palettegen=max_colors=128[p];[b][p]paletteuse=dither=bayer"
    run_ffmpeg(["-i", str(src), "-vf", graph], dest)
    return [dest]
