# Tangerine for Windows

Drag a file while holding a modifier key, a radial menu opens at the cursor, drop the file on a slice to convert it or run a tool on it. Everything runs locally, nothing is uploaded.

## Install (no Python needed)

Run `dist\Tangerine-Setup.exe` (build it with `packaging\build.ps1`). It installs per user, no admin rights, and asks whether Tangerine should **start with Windows** (on by default), so you never have to open it by hand after a reboot. Uninstall from Windows Settings > Apps or `Uninstall.exe` in the install folder.

## Run from source

```
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt send2trash markdown winrt-runtime winrt-Windows.Media.Ocr winrt-Windows.Graphics.Imaging winrt-Windows.Storage.Streams winrt-Windows.Globalization winrt-Windows.Foundation winrt-Windows.Foundation.Collections winrt-Windows.Storage
.venv\Scripts\python main.py
```

`--hidden` starts in the tray only. A second launch just brings up the running instance.

## Use

1. Hold **Ctrl + Shift** (change it in Settings: Alt, Ctrl + Alt) and start dragging a file in Explorer.
2. The radial menu appears under the cursor. Move the file onto a slice and release.
3. Results are saved next to the original, or in the folder chosen in Settings.

No trigger needed: drop files on the Tangerine window, or use the tray menu **Menu from clipboard** (files, an image or text).
Select several files to get the **Combine** ring (merge PDFs, images into one PDF, ZIP all). Tray menu: **Recent**, **Undo last operation** (moves results to the Recycle Bin), **Settings**.

| File | Slices |
| --- | --- |
| Image | Convert: PNG, WEBP, HEIC, TIFF, PDF, DOCX, BMP, AVIF, JPG. Edit: Crop, Edit, Add BG, Redact, Rotate, Resize, Watermark, Remove BG (plain backgrounds). Utility: Compress, Metadata, Upscale 2x, OCR, ZIP |
| PDF | Convert: DOCX, TXT, JPG, PNG. Tools: Pages (reorder, rotate, delete, extract), Compress, Split, Protect, Unlock, Redact (text), OCR, ZIP |
| DOCX, TXT, Markdown | PDF, DOCX or TXT, ZIP |
| Video | MP4, WEBM, MKV, GIF, MP3. Trim, Compress, Mute, ZIP |
| Audio | MP3, WAV, FLAC, OGG, M4A. Trim, Compress, ZIP |
| ZIP / folders / anything else | Extract, ZIP |

Settings also control quality (JPG/WEBP/HEIC/AVIF, compress, PDF DPI), "move original to Recycle Bin after converting", and which slices are shown and in what order.

OCR uses the engine built into Windows (needs an OCR language installed, normally your display language). Video and audio use ffmpeg (bundled through imageio-ffmpeg, a system ffmpeg is preferred if present).

## Tests

```
python tests/test_backend.py   # every converter and tool
python tests/test_ui.py        # builds every window offscreen, screenshots in tests/_out/ui
python tests/test_trigger.py   # trigger state machine and menu drop handling
python main.py --selftest out.txt   # also works inside the built exe
```
