from __future__ import annotations

import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class StorageLayout:
    root: Path
    config: Path
    sessions: Path
    captures: Path
    exports: Path
    logs: Path
    portable: bool


class StorageBackend:
    def __init__(self, layout: StorageLayout):
        self.layout = layout

    def ensure_directories(self) -> None:
        for path in (self.layout.config, self.layout.sessions, self.layout.captures, self.layout.exports, self.layout.logs):
            path.mkdir(parents=True, exist_ok=True)


def _executable_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[1]


def _installed_root(platform_name: str) -> Path:
    if platform_name.startswith("win"):
        return Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / "AIWorkCompanion"
    if platform_name == "darwin":
        return Path.home() / "Library" / "Application Support" / "AI Work Companion"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share")) / "ai_work_companion"


def create_storage_backend(base_dir: Optional[Path] = None, platform_name: Optional[str] = None) -> StorageBackend:
    executable_dir = Path(base_dir).resolve() if base_dir else _executable_dir()
    portable = os.environ.get("AWC_PORTABLE", "").lower() in {"1", "true", "yes"} or (executable_dir / "portable.flag").is_file()
    root = executable_dir / "data" if portable else _installed_root(platform_name or sys.platform)
    layout = StorageLayout(
        root=root,
        config=root / "config",
        sessions=root / "sessions",
        captures=root / "captures",
        exports=root / "exports",
        logs=root / "logs",
        portable=portable,
    )
    return StorageBackend(layout)
