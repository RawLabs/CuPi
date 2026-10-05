import sys
import os
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

from config import ConfigManager
from ui.companion_window import CompanionWindow
from platform_api import get_platform_backend
from storage import create_storage_backend
from branding import APP_NAME, APP_ID, application_icon


def main():
    # Enable High DPI scaling
    os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"
    
    app = QApplication(sys.argv)
    app.setApplicationName(APP_ID)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setDesktopFileName(APP_ID)
    app.setWindowIcon(application_icon())

    # High quality font rendering
    font = app.font()
    font.setFamily("Inter")
    app.setFont(font)

    if "--smoke-test" in sys.argv:
        from packaging_smoke import run_smoke_test
        run_smoke_test(app)
        return

    storage = create_storage_backend()
    config_mgr = ConfigManager(storage)
    window = CompanionWindow(config_mgr, platform_backend=get_platform_backend())
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
