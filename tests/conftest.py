"""Shared Qt bootstrap for pytest.

QPixmap is a GUI resource and aborts the Python process when constructed before
a QGuiApplication/QApplication exists. Loading this module before test
collection gives every test one safe offscreen application instance.
"""

import os

# Test processes are often launched from a live Wayland desktop, but CI and
# sandboxed runs cannot connect to that display. Force Qt's headless backend
# rather than retaining a user-session value such as ``wayland;xcb``.
os.environ["QT_QPA_PLATFORM"] = "offscreen"
os.environ.pop("QT_QPA_PLATFORMTHEME", None)

from PyQt6.QtWidgets import QApplication


qt_app = QApplication.instance() or QApplication([])
