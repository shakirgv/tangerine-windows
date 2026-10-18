# Tangerine for Windows

Drag a file while holding a modifier key, a radial menu opens at the cursor, drop the file on a slice to convert it or run a tool on it. Everything runs locally.

## Run

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
.venv\Scripts\python main.py
```

Use `--hidden` to start in the tray only.

## Use

1. Hold **Ctrl + Shift** (configurable in the tray menu: Alt, Ctrl + Alt) and start dragging a file in Explorer.
2. The radial menu appears under the cursor. Move the file onto a slice and release.
3. Results are saved next to the original (or in the folder chosen in the tray menu).

No trigger needed: you can also drop files on the Tangerine window and click a slice.

| File | Slices |
| --- | --- |
| Image | PNG, WEBP, HEIC, TIFF, PDF, DOCX, BMP, AVIF, JPG + Compress, Metadata, Edit, Add BG, Crop, Redact, Rotate |
| PDF | DOCX, TXT, JPG, PNG |
| DOCX | TXT |
| Video | MP4, WEBM, MKV, GIF, MP3 (ffmpeg) |
| Audio | MP3, WAV, FLAC, OGG, M4A (ffmpeg) |

## Tests

```
python tests/test_backend.py   # converters and tools
python tests/test_ui.py        # builds every window offscreen, saves screenshots to tests/_out/ui
python tests/test_trigger.py   # trigger state machine and menu drop handling
```
