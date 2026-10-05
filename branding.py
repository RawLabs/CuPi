"""Desktop identity and scalable assets for CᵘPⁱ."""
from pathlib import Path
import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

APP_NAME = "CᵘPⁱ"
APP_ID = "cupi"
PHILOSOPHY = "Capture, powered by understanding. Produce, powered by intelligence."


def application_icon() -> QIcon:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
    renderer = QSvgRenderer(str(root / "assets/cupi.svg"))
    if not renderer.isValid():
        raise RuntimeError("The CᵘPⁱ desktop icon is missing or invalid")
    icon = QIcon()
    for size in (16, 24, 32, 48, 64, 128, 256):
        pixmap = QPixmap(size, size)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        renderer.render(painter)
        painter.end()
        icon.addPixmap(pixmap)
    return icon
