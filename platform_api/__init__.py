"""OS-facing services used by the application core."""

from .backend import (
    PlatformBackend,
    PlatformCapabilities,
    PlatformPermission,
    SourceTarget,
)
from .factory import create_platform_backend, get_platform_backend, set_platform_backend

__all__ = [
    "PlatformBackend", "PlatformCapabilities", "PlatformPermission", "SourceTarget",
    "create_platform_backend", "get_platform_backend", "set_platform_backend",
]
