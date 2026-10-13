"""GUI application entry. `python run_gui.py` or `python -m src.gui.app`."""
import os
import sys


def run(server_url: str | None = None) -> int:
    from PyQt6.QtWidgets import QApplication
    from src.gui.main_window import MainWindow, SERVER_DEFAULT

    server = server_url or os.environ.get("EPU_SERVER", SERVER_DEFAULT)
    app = QApplication(sys.argv)
    app.setApplicationName("EasyPhoneUnlock MTK Tool")
    win = MainWindow(server_url=server)
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(run())
