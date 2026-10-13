"""
EasyPhoneUnlock MTK Universal Tool — GUI launcher.

    python run_gui.py
    EPU_SERVER=https://panel.example.com python run_gui.py
"""
import sys

from src.gui.app import run

if __name__ == "__main__":
    sys.exit(run())
