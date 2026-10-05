from __future__ import annotations

import ctypes
from ctypes import wintypes
from typing import Optional

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QPixmap

from .backend import PlatformCapabilities, PlatformPermission, SourceTarget
from .qt_common import QtScreenBackend


class WindowsBackend(QtScreenBackend):
    name = "windows"

    @property
    def capabilities(self):
        return PlatformCapabilities(True, True, True, True, True, True, False)

    def _target(self, hwnd: int) -> Optional[SourceTarget]:
        user32 = ctypes.windll.user32
        length = user32.GetWindowTextLengthW(hwnd)
        if not length or not user32.IsWindowVisible(hwnd):
            return None
        title = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, title, length + 1)
        rect = wintypes.RECT()
        if not title.value or not user32.GetWindowRect(hwnd, ctypes.byref(rect)):
            return None
        geometry = QRect(rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top)
        return SourceTarget("window", str(hwnd), title.value, geometry)

    def list_windows(self) -> list[SourceTarget]:
        windows = []
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        callback = callback_type(lambda hwnd, _: (windows.append(target) if (target := self._target(hwnd)) else None) is None)
        ctypes.windll.user32.EnumWindows(callback, 0)
        return windows

    def active_window(self):
        return self._target(ctypes.windll.user32.GetForegroundWindow())

    def activate_window(self, target):
        return bool(ctypes.windll.user32.SetForegroundWindow(int(target.target_id)))

    def capture_window(self, target):
        screen = QGuiApplication.screenAt(target.rect.center()) if target.rect else QGuiApplication.primaryScreen()
        return screen.grabWindow(int(target.target_id)) if screen else None

    def platform_permissions(self):
        return {"screen_capture": PlatformPermission.GRANTED, "window_capture": PlatformPermission.GRANTED}
