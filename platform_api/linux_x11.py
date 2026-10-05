from __future__ import annotations

import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QPixmap

from .backend import PlatformCapabilities, PlatformPermission, SourceTarget
from .qt_common import QtScreenBackend


class LinuxX11Backend(QtScreenBackend):
    name = "linux-x11"
    _ignored_titles = ("Desktop", "AI Work Companion", "GuideForge", "mutter guard window", "gnome-shell")

    @property
    def capabilities(self):
        return PlatformCapabilities(True, True, True, True, True, True, False)

    def _run(self, args: list[str], timeout: int = 2):
        return subprocess.run(args, capture_output=True, text=True, timeout=timeout)

    def window_rect(self, window_id: str) -> Optional[QRect]:
        try:
            output = self._run(["xwininfo", "-id", window_id]).stdout
            fields = {}
            names = {"Absolute upper-left X": "x", "Absolute upper-left Y": "y", "Width": "w", "Height": "h"}
            for line in output.splitlines():
                for prefix, key in names.items():
                    if line.strip().startswith(prefix + ":"):
                        fields[key] = int(line.rsplit(":", 1)[1].strip())
            return QRect(fields["x"], fields["y"], fields["w"], fields["h"]) if len(fields) == 4 else None
        except (OSError, subprocess.SubprocessError, KeyError, ValueError):
            return None

    def list_windows(self) -> list[SourceTarget]:
        result = []
        try:
            root = self._run(["xprop", "-root", "_NET_CLIENT_LIST"])
            for wid in re.findall(r"0x[0-9a-fA-F]+", root.stdout):
                title_out = self._run(["xprop", "-id", wid, "_NET_WM_NAME", "WM_NAME"]).stdout
                class_out = self._run(["xprop", "-id", wid, "WM_CLASS"]).stdout
                titles = [line.split("=", 1)[1].strip().strip('"') for line in title_out.splitlines() if "=" in line]
                title = next((value for value in titles if value and "not found" not in value.lower()), "")
                cls = class_out.rsplit(",", 1)[-1].strip().strip('"') if "=" in class_out else ""
                rect = self.window_rect(wid)
                if title and rect and rect.width() > 80 and rect.height() > 80 and not any(x in title for x in self._ignored_titles):
                    result.append(SourceTarget("window", wid, f"{title} [{cls}] ({rect.width()}x{rect.height()})", rect, cls))
        except (OSError, subprocess.SubprocessError):
            return []
        return result

    def active_window(self) -> Optional[SourceTarget]:
        try:
            wid = self._run(["xdotool", "getactivewindow"], 1).stdout.strip()
            rect = self.window_rect(wid)
            return SourceTarget("window", wid, "Active window", rect) if wid else None
        except (OSError, subprocess.SubprocessError):
            return None

    def activate_window(self, target: SourceTarget) -> bool:
        try:
            return self._run(["xdotool", "windowactivate", "--sync", target.target_id], 1).returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def capture_window(self, target: SourceTarget) -> Optional[QPixmap]:
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                temp_path = Path(tmp.name)
            wid = str(int(target.target_id, 16)) if target.target_id.startswith("0x") else target.target_id
            result = subprocess.run(
                ["ffmpeg", "-y", "-f", "x11grab", "-window_id", wid, "-i", os.environ.get("DISPLAY", ":0"), "-vframes", "1", str(temp_path)],
                capture_output=True, timeout=3,
            )
            if result.returncode == 0:
                pixmap = QPixmap(str(temp_path))
                if not pixmap.isNull():
                    return pixmap
        except (OSError, subprocess.SubprocessError, ValueError):
            pass
        finally:
            if temp_path:
                temp_path.unlink(missing_ok=True)
        rect = self.window_rect(target.target_id) or target.rect
        return self.capture_region(rect) if rect else None

    def platform_permissions(self):
        state = PlatformPermission.GRANTED if os.environ.get("DISPLAY") else PlatformPermission.UNAVAILABLE
        return {"screen_capture": state, "window_control": state}
