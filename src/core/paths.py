"""Resolve resource paths in source, in a PyInstaller onefile EXE, and from a
writable per-user cache (where server-synced catalog updates are stored)."""
import os
import sys


def resource_base() -> str:
    """Project root in source; the extraction dir (_MEIPASS) when frozen."""
    if getattr(sys, "frozen", False):
        return getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def cache_dir() -> str:
    """Writable per-user dir for server-synced catalog + session files."""
    override = os.environ.get("EPU_CACHE_DIR")
    if override:
        base = override
    elif os.name == "nt":
        base = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "EasyPhoneUnlock")
    else:
        base = os.path.join(os.path.expanduser("~"), ".easyphoneunlock")
    os.makedirs(base, exist_ok=True)
    return base


def asset_path(filename: str) -> str:
    """GUI asset (svg/ico/png) path — bundled under src/gui/assets."""
    return os.path.join(resource_base(), "src", "gui", "assets", filename)


def config_path(filename: str) -> str:
    """Prefer a server-synced cached copy; fall back to the bundled config."""
    cached = os.path.join(cache_dir(), filename)
    if os.path.isfile(cached):
        return cached
    return os.path.join(resource_base(), "config", filename)
