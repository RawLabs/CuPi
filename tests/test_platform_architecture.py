import json
import os
from unittest.mock import Mock, patch
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtGui import QGuiApplication, QPixmap, QColor
from PyQt6.QtCore import QRect

from platform_api.factory import create_platform_backend
from platform_api.backend import SourceTarget
from platform_api.linux_wayland import LinuxWaylandBackend
from platform_api.linux_x11 import LinuxX11Backend
from platform_api.macos import MacOSBackend
from platform_api.windows import WindowsBackend
from sessions import SOPSession, SOPStep
from storage import create_storage_backend


_app = QGuiApplication.instance() or QGuiApplication([])


def test_factory_selects_explicit_backends():
    assert isinstance(create_platform_backend("linux", "x11"), LinuxX11Backend)
    assert isinstance(create_platform_backend("linux", "wayland"), LinuxWaylandBackend)
    assert isinstance(create_platform_backend("win32"), WindowsBackend)
    assert isinstance(create_platform_backend("darwin"), MacOSBackend)


def test_macos_supports_screen_and_region_capture():
    capabilities = MacOSBackend().capabilities
    assert capabilities.screen_capture
    assert capabilities.region_capture


def test_wayland_backend_prefers_compositor_capture():
    backend = LinuxWaylandBackend()
    captured = QPixmap(12, 8)
    captured.fill(QColor("red"))
    screen = Mock()
    screen.name.return_value = "eDP-2"

    with patch.object(backend, "_screen_for_target", return_value=screen), patch.object(
        backend, "_pixmap_from_grim", return_value=captured
    ) as capture:
        pixmap = backend.capture_screen()

    assert pixmap is captured
    assert capture.call_args.args[0][0] == "-o"


def test_wayland_clean_window_capture_decodes_native_helper_output():
    import struct
    from unittest.mock import patch

    backend = LinuxWaylandBackend()
    target = SourceTarget("window", "0x123", "Terminal")
    pixels = bytes((255, 0, 0, 255)) * 2
    helper_output = struct.pack("<4sIII", b"AWC1", 2, 1, 8) + pixels

    with patch.object(backend, "_toplevel_capture_helper", return_value="/helper"), patch(
        "platform_api.linux_wayland.subprocess.run"
    ) as run:
        run.return_value.returncode = 0
        run.return_value.stdout = helper_output
        pixmap = backend.capture_window(target)

    assert pixmap is not None
    assert (pixmap.width(), pixmap.height()) == (2, 1)
    assert run.call_args.args[0] == ["/helper", "0x123"]


def test_wayland_window_capture_falls_back_to_visible_region():
    backend = LinuxWaylandBackend()
    target = SourceTarget("window", "0x123", "Terminal", QRect(20, 30, 400, 300))
    captured = QPixmap(400, 300)
    captured.fill(QColor("blue"))

    with patch.object(backend, "_toplevel_capture_helper", return_value=None), patch.object(
        backend, "capture_region", return_value=captured
    ) as capture_region:
        pixmap = backend.capture_window(target)

    assert pixmap is captured
    assert capture_region.call_args.args == (target.rect,)
    assert "visible window region" in backend.last_capture_notice


def test_wayland_backend_lists_hyprland_clients_across_workspaces():
    backend = LinuxWaylandBackend()
    responses = {
        "activeworkspace": {"id": 4},
        "clients": [
            {
                "address": "0x123", "mapped": True, "hidden": False,
                "workspace": {"id": 4}, "title": "Terminal", "class": "foot",
                "at": [807, 38], "size": [781, 468],
            },
            {
                "address": "0x456", "mapped": True, "hidden": False,
                "workspace": {"id": 3}, "title": "Other workspace", "class": "foot",
                "at": [0, 0], "size": [500, 400],
            },
        ],
    }
    with patch.object(backend, "_hyprctl_json", side_effect=lambda command: responses[command]):
        windows = backend.list_windows()

    assert len(windows) == 2
    assert windows[0].target_id == "0x123"
    assert windows[0].rect.width() == 781
    assert "Workspace 3" in windows[1].name


def test_wayland_inactive_workspace_never_falls_back_to_visible_region():
    backend = LinuxWaylandBackend()
    target = SourceTarget("window", "0x456", "Other", QRect(0, 0, 500, 400))
    clients = [{"address": "0x456", "workspace": {"id": 3}}]
    with patch.object(backend, "_toplevel_capture_helper", return_value=None), patch.object(
        backend, "_hyprctl_json", side_effect=lambda command: clients if command == "clients" else {"id": 4}
    ), patch.object(backend, "capture_region") as capture_region:
        assert backend.capture_window(target) is None

    capture_region.assert_not_called()
    assert "did not switch workspaces" in backend.last_capture_error


def test_portable_storage_keeps_all_data_beside_executable(tmp_path):
    (tmp_path / "portable.flag").touch()
    storage = create_storage_backend(tmp_path, "linux")
    assert storage.layout.portable
    assert storage.layout.root == tmp_path / "data"
    storage.ensure_directories()
    assert all(path.is_dir() for path in (
        storage.layout.config, storage.layout.sessions, storage.layout.captures,
        storage.layout.exports, storage.layout.logs,
    ))


def test_session_json_is_os_neutral(tmp_path):
    session = SOPSession("Receive parts", steps=[SOPStep(
        step=7, timestamp="2026-08-27T12:00:00Z", application="Mitchell Manager",
        window="Repair Order #12345", screenshot="step_007.png",
        note="Receive the part against the PO.",
    )])
    path = tmp_path / "session.json"
    session.save(path)
    payload = json.loads(path.read_text())
    assert payload["steps"][0]["application"] == "Mitchell Manager"
    assert "platform" not in payload and "os" not in payload
    assert SOPSession.load(path) == session
