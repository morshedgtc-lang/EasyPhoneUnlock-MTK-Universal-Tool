"""
Unisoc / Spreadtrum engine (BootROM -> FDL1 -> FDL2 -> flash ops).

Scaffold-to-real: the HDLC-framed BSL protocol lives in sprd/protocol.py and is
test-validated. The device download handshake uploads FDL1 (IRAM) then FDL2
(DRAM), both supplied by the operator from the server vault, then flash commands
run through the shared safety guards. READY=False until verified on hardware.
"""
from __future__ import annotations

from typing import List, Optional

from src.core.engines.base import DeviceEngine, DeviceInfo, EngineError, StepUpdate
from src.core.engines.sprd.protocol import SprdProtocol
from src.core.safety import SafetyConfig, guard_erase, guard_write

SPRD_VID = 0x1782
SPRD_PID_DL = 0x4D00


class UnisocEngine(DeviceEngine):
    platform = "unisoc"
    READY = False  # real protocol; needs hardware + FDL loaders to verify

    def __init__(self, port=None, log=None, step=None, transport=None,
                 fdl1=None, fdl2=None, fdl1_addr=0x5000, fdl2_addr=0x9EFFFE00):
        super().__init__(port, log or (lambda l, m: None), step or (lambda u: None))
        self.transport = transport
        self.fdl1 = fdl1              # FDL1 loader bytes (vault)
        self.fdl2 = fdl2             # FDL2 loader bytes (vault)
        self.fdl1_addr = fdl1_addr
        self.fdl2_addr = fdl2_addr
        self.proto: Optional[SprdProtocol] = None

    def set_loaders(self, fdl1: bytes, fdl2: bytes) -> None:
        self.fdl1, self.fdl2 = fdl1, fdl2

    def connect(self) -> bool:
        if self.transport is None:
            raise EngineError("No download transport. Put the device in Unisoc download mode (1782:4d00).")
        if not (self.fdl1 and self.fdl2):
            raise EngineError("FDL1/FDL2 loaders not supplied. Load them into the vault for this platform.")
        self.proto = SprdProtocol(self.transport)
        self.log("info", "Unisoc: BootROM connect...")
        self.proto.connect()
        self.log("info", "Unisoc: uploading FDL1...")
        self.proto.transfer_fdl(self.fdl1_addr, self.fdl1, execute=True)
        self.log("info", "Unisoc: uploading FDL2...")
        self.proto.transfer_fdl(self.fdl2_addr, self.fdl2, execute=True)
        return True

    def identify(self) -> DeviceInfo:
        if self.proto is None:
            raise EngineError("Not connected.")
        return DeviceInfo(platform="unisoc", chip="Unisoc (FDL)",
                          port=getattr(self.transport, "port_name", ""))

    def flash(self, steps: List[dict], safety: SafetyConfig) -> None:
        if self.proto is None:
            raise EngineError("Not connected.")
        for s in steps:
            name, fpath = s["partition"], s.get("file", "")
            guard_write(name, fpath, s.get("size", 0), safety)
            if "addr" not in s:
                raise EngineError(f"Partition '{name}' needs a flash addr from the partition map.")
            self.step(StepUpdate(name, "WRITE", fpath, "RUNNING"))
            with open(fpath, "rb") as f:
                data = f.read()
            self.proto.transfer_fdl(s["addr"], data, execute=False)
            self.step(StepUpdate(name, "WRITE", fpath, "DONE"))

    def erase(self, partitions: List[dict], safety: SafetyConfig) -> None:
        if self.proto is None:
            raise EngineError("Not connected.")
        for p in partitions:
            name = p["partition"] if isinstance(p, dict) else p
            guard_erase(name, safety, context="erase")
            if not isinstance(p, dict) or "addr" not in p:
                raise EngineError(f"Erase of '{name}' needs addr/size.")
            self.step(StepUpdate(name, "ERASE", "-", "RUNNING"))
            self.proto.erase_flash(p["addr"], p["size"])
            self.step(StepUpdate(name, "ERASE", "-", "DONE"))
