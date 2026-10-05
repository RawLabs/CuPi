"""Compatibility facade; new code should use PlatformBackend directly."""
import base64
from typing import Optional
from PySide6.QtCore import QBuffer, QIODevice, Qt
from PySide6.QtGui import QPixmap
from platform_api import SourceTarget, get_platform_backend


def list_screens() -> list[SourceTarget]:
    return get_platform_backend().list_screens()


def list_windows() -> list[SourceTarget]:
    return get_platform_backend().list_windows()


def capture_target(target: SourceTarget) -> Optional[QPixmap]:
    return get_platform_backend().capture_target(target)


def get_window_rect(window_id: str):
    method = getattr(get_platform_backend(), "window_rect", None)
    return method(window_id) if method else None


def pixmap_to_b64(pixmap: QPixmap, max_dim: int = 1920) -> str:
    if pixmap.isNull():
        return ""
    if pixmap.width() > max_dim or pixmap.height() > max_dim:
        pixmap = pixmap.scaled(max_dim, max_dim, Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    pixmap.save(buffer, "PNG")
    return base64.b64encode(buffer.data().data()).decode("utf-8")
