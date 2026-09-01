from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from typing import Callable, Optional

from PyQt6.QtCore import QPoint, QRect
from PyQt6.QtGui import QPixmap


@dataclass(frozen=True)
class SourceTarget:
    target_type: str
    target_id: str
    name: str
    rect: Optional[QRect] = None
    application: str = ""

    def __str__(self) -> str:
        return f"{self.name} ({self.target_type})"


class PlatformPermission(str, Enum):
    GRANTED = "granted"
    PROMPT_REQUIRED = "prompt_required"
    DENIED = "denied"
    UNAVAILABLE = "unavailable"


@dataclass(frozen=True)
class PlatformCapabilities:
    screen_capture: bool = False
    region_capture: bool = False
    window_capture: bool = False
    window_listing: bool = False
    active_window: bool = False
    cursor_position: bool = False
    global_hotkeys: bool = False


class PlatformBackend(ABC):
    name = "unknown"

    @property
    @abstractmethod
    def capabilities(self) -> PlatformCapabilities: ...

    @abstractmethod
    def list_screens(self) -> list[SourceTarget]: ...

    def list_windows(self) -> list[SourceTarget]:
        return []

    def active_window(self) -> Optional[SourceTarget]:
        return None

    @abstractmethod
    def capture_screen(self, target: Optional[SourceTarget] = None) -> Optional[QPixmap]: ...

    @abstractmethod
    def capture_region(self, rect: QRect) -> Optional[QPixmap]: ...

    def capture_window(self, target: SourceTarget) -> Optional[QPixmap]:
        return None

    def capture_target(self, target: SourceTarget) -> Optional[QPixmap]:
        if target.target_type == "window":
            return self.capture_window(target)
        if target.target_type == "region" and target.rect:
            return self.capture_region(target.rect)
        return self.capture_screen(target)

    def cursor_position(self) -> QPoint:
        return QPoint()

    def register_global_hotkey(self, hotkey: str, callback: Callable[[], None]) -> bool:
        return False

    def platform_permissions(self) -> dict[str, PlatformPermission]:
        return {}

    @property
    def last_capture_error(self) -> str:
        """A user-actionable explanation for the most recent failed capture."""
        return ""

    @property
    def last_capture_notice(self) -> str:
        """A non-fatal note about the most recent successful capture."""
        return ""

    def activate_window(self, target: SourceTarget) -> bool:
        return False
