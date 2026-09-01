import os
import sys
from typing import Optional

from .backend import PlatformBackend

_backend: Optional[PlatformBackend] = None


def create_platform_backend(platform_name: Optional[str] = None, session_type: Optional[str] = None) -> PlatformBackend:
    platform_name = platform_name or sys.platform
    if platform_name.startswith("win"):
        from .windows import WindowsBackend
        return WindowsBackend()
    if platform_name == "darwin":
        from .macos import MacOSBackend
        return MacOSBackend()
    if platform_name.startswith("linux"):
        desktop_session = (session_type or os.environ.get("XDG_SESSION_TYPE", "")).lower()
        if desktop_session == "wayland" or (os.environ.get("WAYLAND_DISPLAY") and not os.environ.get("DISPLAY")):
            from .linux_wayland import LinuxWaylandBackend
            return LinuxWaylandBackend()
        from .linux_x11 import LinuxX11Backend
        return LinuxX11Backend()
    from .qt_common import QtScreenBackend
    return QtScreenBackend()


def get_platform_backend() -> PlatformBackend:
    global _backend
    if _backend is None:
        _backend = create_platform_backend()
    return _backend


def set_platform_backend(backend: Optional[PlatformBackend]) -> None:
    global _backend
    _backend = backend
