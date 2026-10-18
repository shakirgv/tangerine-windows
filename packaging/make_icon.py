"""Generate packaging/tangerine.ico from the app's own tray icon."""
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image  # noqa: E402
from PySide6.QtCore import QBuffer, QByteArray, QIODevice  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

from tangerine.ui.theme import app_icon  # noqa: E402

app = QApplication([])
pix = app_icon().pixmap(256, 256)
data = QByteArray()
buf = QBuffer(data)
buf.open(QIODevice.OpenModeFlag.WriteOnly)
pix.save(buf, "PNG")
img = Image.open(__import__("io").BytesIO(bytes(data)))
img.save(ROOT / "packaging" / "tangerine.ico", sizes=[(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)])
print("icon written")
