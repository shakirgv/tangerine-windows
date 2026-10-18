# Tangerine for Windows

A Windows clone of Tangerine (a Mac app): drag a file while holding a modifier key, a radial (circular) menu appears at the cursor, drop the file on a slice to convert it or run a tool on it. Everything runs locally, nothing is uploaded to a server.

## How I want to work (IMPORTANT)

- NO teaching mode. Do NOT explain code line by line and do NOT ask me to type code myself.
- You build the whole project yourself: create files, install dependencies, write all the code, run it and fix errors on your own.
- Work through the roadmap end to end without waiting for my approval after each step. Stop and ask only if a decision is truly mine (for example the trigger key) or something cannot be done without me (for example I must test the drag on my own screen).
- Be direct and action-oriented. Keep messages short: say what you built, how to run it, and what is next.
- All text inside code (strings, comments, identifiers, UI labels) must be in English.
- Talk to me in Azerbaijani.
- Commit working milestones to git with clear messages.

## Stack

- Python 3.11+
- PySide6: windows, drag and drop, radial menu widget, tray icon
- Pillow: image convert, crop, rotate, compress, add background
- pillow-heif: HEIC support
- PyMuPDF (fitz): PDF to JPG/PNG/TXT, redact
- pdf2docx: PDF to DOCX
- pynput: global keyboard/mouse listening (trigger)
- ffmpeg (later): video and audio

Install: `pip install PySide6 pillow pillow-heif pymupdf pdf2docx pynput`

## Core behavior (from the original app)

1. User drags a file and holds the trigger modifier.
2. A radial menu opens around the cursor. Slices depend on the file type:
   - PDF: DOCX, TXT, JPG, PNG
   - Image: format slices (PNG, WEBP, HEIC, TIFF, PDF, DOCX, BMP, AVIF, JPG) plus tool slices: Compress, Metadata, Edit, Add BG, Crop, Redact, Rotate
3. Dropping on a slice runs that action. Converted files are saved next to the original.
4. Some tools open a small window:
   - Crop: aspect ratio (Free, 1:1, 16:9, 9:16, 4:3, 3:4), W/H fields in px, Reset, Apply
   - Add BG: gradient/color presets, padding, corners, shadow sliders, ratio (Auto, 1:1, 16:9, 4:5), Reset, "Save with Background"

## Windows-specific notes

- Windows does not let us read dragged file paths during a system-wide drag. Plan: the overlay opens when the trigger is detected, and we read file paths in `dropEvent` when the user drops on a slice.
- Explorer already uses Shift+drag for "move", so use Ctrl+Shift or Alt as the trigger (make it configurable later).
- The overlay must be a frameless, transparent, always-on-top window that accepts drops.

## Architecture (planned)

```
tangerine/
  main.py            # entry point, tray icon
  registry.py        # file type -> list of actions (slices)
  converters/        # image.py, pdf.py, (later) media.py
  tools/             # crop.py, add_bg.py, compress.py, ...
  ui/
    drop_window.py   # simple drop window (step 1, done)
    radial_menu.py   # radial menu widget
    tool_windows.py  # crop / add bg dialogs
  trigger.py         # global hotkey/mouse listener
```

## Roadmap

1. Simple drop window that prints dropped file paths
2. Registry: file extension -> available actions
3. Converters: image to image, PDF to image/TXT
4. Radial menu widget, slices come from the registry
5. Global trigger (Ctrl+Shift + drag) opening the menu at the cursor
6. Tool windows: Crop first, then Add BG
7. Tray icon, settings (trigger key, output folder)
8. Later: video/audio via ffmpeg, DOCX conversions, merge/trim

## Current status

Nothing is built yet. Start from Step 1 and build the whole roadmap yourself, in order. Create the project structure above, set up a virtual environment, and make sure the app runs with `python main.py`.
