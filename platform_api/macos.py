from .backend import PlatformCapabilities, PlatformPermission
from .qt_common import QtScreenBackend


class MacOSBackend(QtScreenBackend):
    """macOS display capture through Qt and the Screen Recording permission."""

    name = "macos"

    @property
    def capabilities(self):
        return PlatformCapabilities(screen_capture=True, region_capture=True, cursor_position=True)

    def platform_permissions(self):
        # Qt asks macOS for Screen Recording access when the app first captures.
        return {"screen_capture": PlatformPermission.PROMPT_REQUIRED}
