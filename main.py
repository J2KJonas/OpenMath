#!/usr/bin/env python3
"""
Entry point for OpenMath Desktop CAS Calculator.
Run with: python3 main.py
"""

import sys
import os

# Enable high-DPI scaling attributes before creating QApplication
os.environ["QT_AUTO_SCREEN_SCALE_FACTOR"] = "1"

from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QIcon
from PyQt6.QtCore import Qt
from ui.main_window import MainWindow


def main():
    def excepthook(exc_type, exc_value, exc_tb):
        import traceback
        traceback.print_exception(exc_type, exc_value, exc_tb)
    sys.excepthook = excepthook

    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.j2k.calculator")
        except Exception:
            pass

    # Set high DPI policy
    app = QApplication(sys.argv)
    app.setApplicationName("OpenMath")
    app.setOrganizationName("OpenMath")

    from ui.theme import Theme
    app.setPalette(Theme.get_dialog_palette())
    app.setStyleSheet(Theme.get_qss(Theme.LIGHT))

    icon_path = os.path.join(os.path.dirname(__file__), "resources", "AppIcon.png")
    if os.path.isfile(icon_path):
        app.setWindowIcon(QIcon(icon_path))

    window = MainWindow()
    if len(sys.argv) > 1 and os.path.isfile(sys.argv[1]):
        window.load_worksheet_from_file(sys.argv[1])
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
