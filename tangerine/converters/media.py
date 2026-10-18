"""Video and audio conversion through ffmpeg."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from ..utils import output_path

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


def convert_media(src: Path, target: str, video: bool) -> list[Path]:
    exe = ffmpeg_exe()
    if not exe:
        raise RuntimeError("ffmpeg was not found. Install it or run: pip install imageio-ffmpeg")
    ext, args = (VIDEO_TARGETS if video else AUDIO_TARGETS)[target]
    dest = output_path(src, ext)
    cmd = [exe, "-y", "-i", str(src), *args, str(dest)]
    flags = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
    proc = subprocess.run(cmd, capture_output=True, text=True, errors="replace", creationflags=flags)
    if proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-4:])
        dest.unlink(missing_ok=True)
        raise RuntimeError(f"ffmpeg failed:\n{tail}")
    return [dest]
