"""Engine selection: by chip platform or by the USB signature of a plugged device."""
from __future__ import annotations

from typing import Optional, Type

from src.core.engines.base import DeviceEngine

# USB (VID, PID) -> platform, for the download/emergency modes of each family.
USB_SIGNATURES = {
    (0x0E8D, 0x0003): "mtk",        # MediaTek BootROM
    (0x0E8D, 0x2000): "mtk",        # MediaTek Preloader
    (0x0E8D, 0x2001): "mtk",        # MediaTek DA / VCOM
    (0x05C6, 0x9008): "qualcomm",   # Qualcomm EDL (QDLoader 9008)
    (0x05C6, 0x900E): "qualcomm",   # Qualcomm Diag
    (0x1782, 0x4D00): "unisoc",     # Spreadtrum/Unisoc download
    (0x1782, 0x4D01): "unisoc",
}


def platform_for_chip(chip_name: str) -> str:
    """Infer platform from a chip model string."""
    n = (chip_name or "").upper()
    if n.startswith("MT"):
        return "mtk"
    if n.startswith(("SM", "SDM", "MSM", "APQ", "QCM", "QCS", "SNAPDRAGON")):
        return "qualcomm"
    if n.startswith(("SC", "T", "UMS", "UIS", "SPRD")):
        return "unisoc"
    return "unknown"


def platform_for_usb(vid: int, pid: int) -> Optional[str]:
    return USB_SIGNATURES.get((vid, pid))


def get_engine_class(platform: str) -> Type[DeviceEngine]:
    """Lazy import so a missing optional engine never breaks the others."""
    if platform == "mtk":
        from src.core.engines.mtk import MtkEngine
        return MtkEngine
    if platform == "qualcomm":
        from src.core.engines.qualcomm import QualcommEngine
        return QualcommEngine
    if platform == "unisoc":
        from src.core.engines.unisoc import UnisocEngine
        return UnisocEngine
    raise ValueError(f"No engine for platform '{platform}'.")


def available_platforms() -> dict:
    """Report which engines are ready vs. scaffolded, for the UI/about screen."""
    status = {}
    for p in ("mtk", "qualcomm", "unisoc"):
        try:
            cls = get_engine_class(p)
            status[p] = getattr(cls, "READY", False)
        except Exception:
            status[p] = False
    return status
