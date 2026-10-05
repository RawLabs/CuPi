from __future__ import annotations

import os
import json
import shutil
import struct
import subprocess
import sys
from pathlib import Path
from typing import Optional
from PySide6.QtCore import QRect
from PySide6.QtGui import QGuiApplication, QImage, QPixmap

from .backend import PlatformCapabilities, PlatformPermission, SourceTarget
from .qt_common import QtScreenBackend


class LinuxWaylandBackend(QtScreenBackend):
    """Wayland capture through a compositor-authorized screenshot provider.

    Qt can enumerate Wayland outputs but ``QScreen.grabWindow(0)`` is not a
    reliable screenshot API under compositor security rules.  ``grim`` is the
    standard screenshot client on wlroots compositors (including Hyprland and
    Sway), and reads pixels through the compositor's screencopy protocol.
    Other Wayland desktops retain the Qt fallback until their portal capture
    session is implemented.
    """

    name = "linux-wayland"

    def __init__(self):
        self._last_capture_error = ""
        self._last_capture_notice = ""

    @property
    def last_capture_error(self) -> str:
        return self._last_capture_error

    @property
    def last_capture_notice(self) -> str:
        return self._last_capture_notice

    def _begin_capture(self) -> None:
        self._last_capture_error = ""
        self._last_capture_notice = ""

    @property
    def capabilities(self):
        hyprland_available = bool(shutil.which("hyprctl"))
        # A Hyprland client always has a valid visible-region capture through
        # grim. The optional native helper only improves that capture by
        # supplying unobscured client pixels, so it must not decide whether a
        # window is selectable at all.
        visible_window_capture = hyprland_available and bool(shutil.which("grim"))
        return PlatformCapabilities(
            screen_capture=True,
            region_capture=True,
            window_capture=visible_window_capture,
            window_listing=hyprland_available,
            active_window=hyprland_available,
            cursor_position=True,
        )

    @staticmethod
    def _toplevel_capture_helper() -> Optional[str]:
        """Find the bundled Hyprland clean-window capture helper."""
        candidates = []
        bundle_dir = getattr(sys, "_MEIPASS", None)
        if bundle_dir:
            candidates.append(Path(bundle_dir) / "awc-hyprland-toplevel-capture")
        candidates.append(Path(__file__).resolve().parent.parent / "capture" / "awc-hyprland-toplevel-capture")
        system_helper = shutil.which("awc-hyprland-toplevel-capture")
        if system_helper:
            candidates.append(Path(system_helper))
        for candidate in candidates:
            if candidate.is_file() and candidate.stat().st_mode & 0o111:
                return str(candidate)
        return None

    @staticmethod
    def _hyprctl_json(command: str) -> Optional[dict | list]:
        hyprctl = shutil.which("hyprctl")
        if not hyprctl:
            return None
        try:
            result = subprocess.run(
                [hyprctl, command, "-j"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2,
                check=False,
            )
            return json.loads(result.stdout) if result.returncode == 0 else None
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return None

    @staticmethod
    def _client_target(client: dict) -> Optional[SourceTarget]:
        address = str(client.get("address", ""))
        title = str(client.get("title", "")).strip()
        app_class = str(client.get("class", "")).strip()
        position = client.get("at") or []
        size = client.get("size") or []
        if not address or not title or len(position) != 2 or len(size) != 2:
            return None
        rect = QRect(int(position[0]), int(position[1]), int(size[0]), int(size[1]))
        if rect.width() < 20 or rect.height() < 20:
            return None
        workspace = client.get("workspace") if isinstance(client.get("workspace"), dict) else {}
        workspace_name = str(workspace.get("name") or workspace.get("id") or "?")
        location = f"Workspace {workspace_name}"
        label = f"{title} [{app_class}] — {location} ({rect.width()}x{rect.height()})" if app_class else f"{title} — {location}"
        return SourceTarget("window", address, label, rect, app_class)

    def list_windows(self) -> list[SourceTarget]:
        """List all mapped Hyprland clients without changing workspaces.

        The bundled toplevel-export helper asks Hyprland for a window buffer by
        address, so it can capture a window on an inactive workspace cleanly.
        A visible-region fallback is intentionally forbidden for such a target:
        it would otherwise crop the current workspace at stale coordinates.
        """
        clients = self._hyprctl_json("clients")
        if not isinstance(clients, list):
            return []
        result = []
        for client in clients:
            if not isinstance(client, dict) or not client.get("mapped"):
                continue
            target = self._client_target(client)
            if target:
                result.append(target)
        return result

    def active_window(self) -> Optional[SourceTarget]:
        client = self._hyprctl_json("activewindow")
        return self._client_target(client) if isinstance(client, dict) else None

    def activate_window(self, target: SourceTarget) -> bool:
        hyprctl = shutil.which("hyprctl")
        if not hyprctl or not target.target_id:
            return False
        try:
            result = subprocess.run(
                [hyprctl, "dispatch", "focuswindow", f"address:{target.target_id}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=2,
                check=False,
            )
            return result.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False

    def _pixmap_from_grim(self, arguments: list[str], operation: str) -> Optional[QPixmap]:
        """Capture a PNG from grim without creating a temporary screenshot file."""
        grim = shutil.which("grim")
        if not grim:
            self._last_capture_error = "`grim` is not installed. Install it to capture screens on Wayland."
            return None
        try:
            result = subprocess.run(
                [grim, *arguments, "-"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=5,
                check=False,
            )
        except subprocess.TimeoutExpired:
            self._last_capture_error = f"{operation} timed out. Try again after your desktop has settled."
            return None
        except (OSError, subprocess.SubprocessError) as exc:
            self._last_capture_error = f"Could not start `grim` for {operation}: {exc}"
            return None

        if result.returncode != 0 or not result.stdout:
            reason = result.stderr.decode("utf-8", errors="replace").strip()
            self._last_capture_error = (
                f"{operation} failed"
                + (f": {reason}" if reason else " (grim returned no image).")
            )
            return None
        pixmap = QPixmap()
        if pixmap.loadFromData(result.stdout, "PNG"):
            return pixmap
        self._last_capture_error = f"{operation} returned an image that could not be decoded."
        return None

    @staticmethod
    def _screen_for_target(target: Optional[SourceTarget]):
        screens = QGuiApplication.screens()
        index = 0
        if target:
            try:
                index = int(target.target_id.removeprefix("screen_"))
            except ValueError:
                pass
        return screens[index] if 0 <= index < len(screens) else QGuiApplication.primaryScreen()

    def capture_screen(self, target: Optional[SourceTarget] = None) -> Optional[QPixmap]:
        self._begin_capture()
        screen = self._screen_for_target(target)
        output_name = screen.name() if screen else ""
        if output_name:
            pixmap = self._pixmap_from_grim(["-o", output_name], f"display '{output_name}' capture")
            if pixmap:
                return pixmap
        pixmap = super().capture_screen(target)
        if pixmap and not pixmap.isNull():
            self._last_capture_notice = "Wayland compositor capture was unavailable; Qt's screen fallback was used."
            self._last_capture_error = ""
            return pixmap
        if not self._last_capture_error:
            self._last_capture_error = "No Wayland screen-capture provider returned an image."
        return None

    def capture_region(self, rect: QRect) -> Optional[QPixmap]:
        self._begin_capture()
        if rect.isValid():
            geometry = f"{rect.x()},{rect.y()} {rect.width()}x{rect.height()}"
            pixmap = self._pixmap_from_grim(["-g", geometry], "selected area capture")
            if pixmap:
                return pixmap
        pixmap = super().capture_region(rect)
        if pixmap and not pixmap.isNull():
            self._last_capture_notice = "Wayland compositor capture was unavailable; Qt's area fallback was used."
            self._last_capture_error = ""
            return pixmap
        if not self._last_capture_error:
            self._last_capture_error = "The selected area is outside the available displays."
        return None

    def capture_window(self, target: SourceTarget) -> Optional[QPixmap]:
        """Capture a Hyprland client, favoring clean pixels but never failing needlessly.

        The bundled helper is only present in packaged builds.  A source checkout
        should still be useful, so its fallback is a compositor-authorized grim
        crop of the visible client region.  This can include an overlapping
        window, but it is an honest, successful capture instead of a dead-end.
        """
        self._begin_capture()
        helper = self._toplevel_capture_helper()
        if helper and target.target_id:
            try:
                result = subprocess.run(
                    [helper, target.target_id],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=5,
                    check=False,
                )
            except subprocess.TimeoutExpired:
                result = None
                self._last_capture_error = "Clean window capture timed out."
            except (OSError, subprocess.SubprocessError) as exc:
                result = None
                self._last_capture_error = f"Could not start the clean window helper: {exc}"
            if result and result.returncode == 0 and len(result.stdout) >= 20:
                try:
                    magic, width, height, stride = struct.unpack_from("<4sIII", result.stdout)
                    if magic == b"AWC1" and width > 0 and height > 0 and stride >= width * 4:
                        expected = 16 + stride * height
                        if len(result.stdout) >= expected:
                            image = QImage(
                                result.stdout[16:expected], width, height, stride,
                                QImage.Format.Format_RGBA8888,
                            ).copy()
                            if not image.isNull():
                                return QPixmap.fromImage(image)
                    self._last_capture_error = "The clean window helper returned an invalid frame."
                except (struct.error, ValueError):
                    self._last_capture_error = "The clean window helper returned an invalid frame."
            elif result:
                reason = result.stderr.decode("utf-8", errors="replace").strip()
                self._last_capture_error = "Clean window capture failed" + (f": {reason}" if reason else ".")

        # `grim -g` can only see the current workspace. Never return a crop of
        # the current desktop when the requested window belongs elsewhere.
        # The helper is the only trustworthy cross-workspace route. We identify
        # inactive targets from Hyprland's client list rather than activating
        # them, preserving the user's desktop state.
        clients = self._hyprctl_json("clients")
        active_workspace = self._hyprctl_json("activeworkspace")
        target_workspace_id = None
        if isinstance(clients, list):
            for client in clients:
                if isinstance(client, dict) and str(client.get("address")) == target.target_id:
                    workspace = client.get("workspace") or {}
                    target_workspace_id = workspace.get("id") if isinstance(workspace, dict) else None
                    break
        active_workspace_id = active_workspace.get("id") if isinstance(active_workspace, dict) else None
        if target_workspace_id is not None and active_workspace_id is not None and target_workspace_id != active_workspace_id:
            self._last_capture_error = (
                "Clean inactive-workspace capture is unavailable for this window. "
                "The companion did not switch workspaces or capture the wrong desktop."
            )
            return None

        if target.rect and target.rect.isValid():
            pixmap = self.capture_region(target.rect)
            if pixmap:
                self._last_capture_notice = (
                    "Captured the visible window region. A clean, unobscured window helper is unavailable."
                )
                return pixmap
        if not self._last_capture_error:
            self._last_capture_error = "The selected window has no valid on-screen geometry."
        return None

    def platform_permissions(self):
        portal = bool(os.environ.get("DBUS_SESSION_BUS_ADDRESS"))
        if shutil.which("grim"):
            state = PlatformPermission.GRANTED
        else:
            state = PlatformPermission.PROMPT_REQUIRED if portal else PlatformPermission.UNAVAILABLE
        return {"screen_capture": state, "window_capture": state, "global_hotkeys": state}
