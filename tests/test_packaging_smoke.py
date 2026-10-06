from pathlib import Path

from PySide6.QtWidgets import QApplication

from packaging_smoke import run_smoke_test
from platform_api.qt_common import QtScreenBackend


def test_packaging_smoke_handles_windows_default_encoding(monkeypatch, capsys):
    # Packaged CI checks cover the native capture helper separately.
    monkeypatch.setattr('ui.companion_window.get_platform_backend', QtScreenBackend)
    original_read_text = Path.read_text

    def read_text_with_windows_default(path, encoding=None, errors=None):
        return original_read_text(path, encoding=encoding or 'cp1252', errors=errors)

    monkeypatch.setattr(Path, 'read_text', read_text_with_windows_default)
    run_smoke_test(QApplication.instance())
    assert 'smoke test passed' in capsys.readouterr().out
