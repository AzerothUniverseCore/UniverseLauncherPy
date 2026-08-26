#!/usr/bin/env python3
"""
main.py
-------
Point d'entree du launcher Azeroth Universe.

Usage (developpement) : python3 main.py
Usage (utilisateur final) : AzerothUniverseLauncher.exe (compile via PyInstaller,
voir build/BUILD_INSTRUCTIONS.md)
"""

import sys

from PySide6.QtWidgets import QApplication, QMessageBox

import config


def main():
    app = QApplication(sys.argv)
    app.setApplicationName(config.APP_NAME)
    app.setApplicationVersion(config.APP_VERSION)

    from ui import theme
    app.setStyleSheet(theme.STYLESHEET)

    try:
        from ui.main_window import AzerothLauncherWindow
        window = AzerothLauncherWindow()
    except Exception as exc:  # noqa: BLE001
        QMessageBox.critical(None, config.APP_NAME, f"Erreur au demarrage :\n{exc}")
        raise

    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
