# PyInstaller spec: python -m PyInstaller packaging/tangerine.spec --noconfirm
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_submodules

ROOT = Path(SPECPATH).parent

datas, binaries, hiddenimports = [], [], []
for package in ("pillow_heif", "imageio_ffmpeg", "pymupdf", "pdf2docx", "docx", "markdown", "send2trash"):
    d, b, h = collect_all(package)
    datas += d
    binaries += b
    hiddenimports += h
hiddenimports += collect_submodules("tangerine")  # actions are imported lazily by name
hiddenimports += collect_submodules("winrt")  # Windows OCR
hiddenimports += ["pynput.keyboard._win32", "pynput.mouse._win32"]

EXCLUDES = [
    "tkinter", "matplotlib", "scipy", "pandas", "IPython", "pytest",
    "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtWebEngineQuick", "PySide6.QtWebChannel",
    "PySide6.Qt3DCore", "PySide6.Qt3DRender", "PySide6.QtQuick", "PySide6.QtQml", "PySide6.QtMultimedia",
    "PySide6.QtCharts", "PySide6.QtDataVisualization", "PySide6.QtPdf", "PySide6.QtPdfWidgets",
]

a = Analysis(
    [str(ROOT / "main.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=EXCLUDES,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Tangerine",
    console=False,
    icon=str(ROOT / "packaging" / "tangerine.ico"),
)
coll = COLLECT(exe, a.binaries, a.datas, name="Tangerine")
