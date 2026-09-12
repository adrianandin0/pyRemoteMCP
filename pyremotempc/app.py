import sys
import os

# Force X11 backend (xcb) so XEmbed (xfreerdp /parent) works under Wayland.
# Without this, xfreerdp cannot embed into the PySide6 window natively on Wayland.
os.environ["QT_QPA_PLATFORM"] = "xcb"
from PySide6.QtWidgets import QApplication
from pyremotempc.ui.main_window import MainWindow


def main():
    """Main entry point for pyRemoteNG application."""
    app = QApplication(sys.argv)
    app.setApplicationName("pyRemoteNG")
    app.setOrganizationName("pyRemoteNG")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
