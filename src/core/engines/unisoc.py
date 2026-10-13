"""
Unisoc / Spreadtrum engine (BootROM -> FDL1 -> FDL2).

Scaffold for Unisoc (SC9863, T606, UMS512, ...) devices found in some low-end
Oppo/Realme/itel/Tecno models. The device enters download mode (USB 1782:4d00);
the host sends FDL1 (loads DRAM), then FDL2 (storage), then read/write commands.

The FDL loaders are per-platform and loaded from the server vault. Real diag/FDL
I/O is implemented where marked and verified against a device.
"""
from __future__ import annotations

from typing import List

from src.core.engines.base import DeviceEngine, DeviceInfo, EngineError
from src.core.safety import SafetyConfig, guard_erase, guard_write

SPRD_VID = 0x1782
SPRD_PID_DL = 0x4D00


class UnisocEngine(DeviceEngine):
    platform = "unisoc"
    READY = False  # scaffold

    def __init__(self, port=None, log=None, step=None):
        super().__init__(port, log or (lambda l, m: None), step or (lambda u: None))

    def connect(self) -> bool:
        self.log("info", "Unisoc: looking for Spreadtrum download port (1782:4d00)...")
        # --- real BootROM handshake + FDL1/FDL2 upload goes here ---
        raise EngineError(
            "Unisoc engine is not enabled yet. The device download handshake and "
            "FDL1/FDL2 upload will run here once enabled.")

    def identify(self) -> DeviceInfo:
        raise EngineError("Unisoc identify not implemented yet.")

    def flash(self, steps: List[dict], safety: SafetyConfig) -> None:
        for s in steps:
            guard_write(s["partition"], s.get("file", ""), s.get("size", 0), safety)
        raise EngineError("Unisoc write not implemented yet.")

    def erase(self, partitions: List[str], safety: SafetyConfig) -> None:
        for name in partitions:
            guard_erase(name, safety, context="erase")
        raise EngineError("Unisoc erase not implemented yet.")
