from __future__ import annotations

from typing import Optional
from PySide6.QtCore import QRect
from PySide6.QtGui import QCursor, QGuiApplication, QPixmap

from .backend import PlatformBackend, PlatformCapabilities, SourceTarget


class QtScreenBackend(PlatformBackend):
    """Portable Qt implementation for monitor and region operations."""

    @property
    def capabilities(self) -> PlatformCapabilities:
        return PlatformCapabilities(screen_capture=True, region_capture=True, cursor_position=True)

    def list_screens(self) -> list[SourceTarget]:
        result = []
        primary = QGuiApplication.primaryScreen()
        for idx, screen in enumerate(QGuiApplication.screens()):
            geo = screen.geometry()
            output_name = screen.name().strip()
            display_name = output_name or f"Screen {idx + 1}"
            label = f"{display_name} ({geo.width()}x{geo.height()})"
            if screen == primary:
                label += " [Primary]"
            result.append(SourceTarget("screen", f"screen_{idx}", label, geo))
        return result

    def capture_screen(self, target: Optional[SourceTarget] = None) -> Optional[QPixmap]:
        screens = QGuiApplication.screens()
        idx = 0
        if target:
            try:
                idx = int(target.target_id.removeprefix("screen_"))
            except ValueError:
                pass
        screen = screens[idx] if 0 <= idx < len(screens) else QGuiApplication.primaryScreen()
        return screen.grabWindow(0) if screen else None

    def capture_region(self, rect: QRect) -> Optional[QPixmap]:
        screen = QGuiApplication.screenAt(rect.center()) or QGuiApplication.primaryScreen()
        if not screen:
            return None
        geo = screen.geometry()
        local = rect.translated(-geo.x(), -geo.y())
        return screen.grabWindow(0, local.x(), local.y(), local.width(), local.height())

    def cursor_position(self):
        return QCursor.pos()
