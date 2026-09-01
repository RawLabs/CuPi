import sys
import os
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt

from config import ConfigManager
from ui.companion_window import CompanionWindow
from platform_api import get_platform_backend
from storage import create_storage_backend


def main():
    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setApplicationName("AI Work Companion")
    app.setOrganizationName("Antigravity")

    # High quality font rendering
    font = app.font()
    font.setFamily("Inter")
    app.setFont(font)

    storage = create_storage_backend()
    config_mgr = ConfigManager(storage)
    window = CompanionWindow(config_mgr, platform_backend=get_platform_backend())
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
