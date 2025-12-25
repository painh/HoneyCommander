"""Entry point for Commander application."""

import sys

from PySide6.QtWidgets import QApplication

from commander.views.main_window import MainWindow


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("Commander")
    app.setOrganizationName("Commander")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
