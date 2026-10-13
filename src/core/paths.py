"""Resolve bundled resource paths both in source and in a PyInstaller onefile EXE."""
import os
import sys


def resource_base() -> str:
    """Project root in source; the extraction dir (_MEIPASS) when frozen."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def config_path(filename: str) -> str:
    return os.path.join(resource_base(), "config", filename)
