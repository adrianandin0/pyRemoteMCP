import sys
import os

# Ensure project root directory is in sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

# Force Qt X11 (xcb) platform plugin for 100% reliable XEmbed container window embedding (FreeRDP / RDP)
os.environ["QT_QPA_PLATFORM"] = "xcb"
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFont
from pyremotempc.ui.main_window import MainWindow
from pyremotempc.ui.icon_manager import get_icon


def main():
    """Main entry point for pyRemoteMPC application."""
    app = QApplication(sys.argv)
    app.setApplicationName("pyRemoteMPC")
    app.setOrganizationName("pyRemoteMPC")
    app.setWindowIcon(get_icon("pyremotempc"))

    # Set base application font to 11px normal weight
    font = app.font()
    font.setPixelSize(11)
    font.setBold(False)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)

    # Set strict global stylesheet enforcing 11px non-bold for all widgets, 12px non-bold for titles, and clean line splitters
    app.setStyleSheet("""
        * {
            font-size: 11px;
            font-weight: normal;
        }
        QWidget {
            font-size: 11px;
            font-weight: normal;
        }
        QGroupBox, QDockWidget::title {
            font-size: 12px;
            font-weight: normal;
        }
        QMainWindow::separator {
            background-color: #252526;
            width: 1px;
            height: 1px;
            image: none;
        }
        QSplitter::handle {
            background-color: #1e1e1e;
            image: none;
        }
        QSplitter::handle:vertical {
            height: 2px;
        }
        QSplitter::handle:horizontal {
            width: 2px;
        }
        QSplitter::handle:hover, QMainWindow::separator:hover {
            background-color: #007acc;
        }
    """)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
