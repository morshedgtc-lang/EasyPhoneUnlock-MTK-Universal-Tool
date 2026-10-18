"""MediaTek engine: BROM handshake + chip identify + DA-driven flash/erase."""
from __future__ import annotations

from typing import List

from src.core import chipdb
from src.core.da.da_handler import DAHandler
from src.core.engines.base import DeviceEngine, DeviceInfo, EngineError, StepUpdate
from src.core.protocol.brom_protocol import BROMProtocol
from src.core.protocol.transport import USBTransport
from src.core.safety import SafetyConfig, guard_erase, guard_write


class MtkEngine(DeviceEngine):
    platform = "mtk"
    READY = True  # identify is real; low-level DA write finishing needs a device

    def __init__(self, port=None, log=None, step=None, da1=None, da2=None):
        super().__init__(port, log or (lambda l, m: None), step or (lambda u: None))
        self.transport = None
        self.brom = None
        self.da = None
        self.hw_code = None
        self.da1 = da1      # DA1 binary path (from vault)
        self.da2 = da2      # DA2 binary path (from vault)
        self._da_running = False

    def set_da(self, da1: str, da2: str) -> None:
        self.da1, self.da2 = da1, da2

    def connect(self) -> bool:
        self.transport = USBTransport(port_name=self.port)
        if not self.transport.connect():
            return False
        self.brom = BROMProtocol(self.transport)
        self.log("info", f"MTK: handshaking on {self.transport.port_name}...")
        if not self.brom.handshake(timeout_sec=8.0):
            return False
        self.brom.get_hardware_info()
        self.hw_code = self.brom.hw_code
        self.brom.disable_watchdog(chipdb.watchdog_base(self.hw_code))
        return True

    def _start_da(self):
        """Upload DA1 (EMI), init DRAM, upload+run DA2 (storage). Needs vault DA."""
        self._ensure_da()
        if self._da_running:
            return
        if not (self.da1 and self.da2):
            raise EngineError("DA1/DA2 binaries not loaded. Upload them to the server vault "
                              "for this chip (python -m backend.core.vault put da1 <file>).")
        self.log("info", "MTK: uploading DA1 + calibrating DRAM...")
        self.da.load_da1(self.da1)
        self.da.init_dram()
        self.log("info", "MTK: starting DA2 storage engine...")
        self.da.jump_da2(self.da2)
        self._da_running = True

    def identify(self) -> DeviceInfo:
        if not self.brom:
            raise EngineError("Not connected.")
        hw_code, hw_ver, sw_ver = self.brom.get_hardware_info()
        self.hw_code = hw_code
        chip = chipdb.chip_by_hw_code(hw_code) or {}
        return DeviceInfo(
            platform="mtk",
            chip=chip.get("name", f"UNKNOWN(0x{hw_code:04X})"),
            port=self.transport.port_name,
            details={"hw_code": f"0x{hw_code:04X}", "hw_ver": f"0x{hw_ver:04X}",
                     "sw_ver": f"0x{sw_ver:04X}", "arch": chip.get("arch", "-")},
        )

    def _ensure_da(self):
        if self.da is None:
            self.da = DAHandler(self.transport, self.brom)

    def flash(self, steps: List[dict], safety: SafetyConfig) -> None:
        self._start_da()

        def backup_fn(name, dest):
            s = next((x for x in steps if x["partition"] == name), {})
            return self.da.read_partition(name, s.get("start", 0), s.get("size", 0), dest)

        for s in steps:
            name, fpath = s["partition"], s.get("file", "")
            self.step(StepUpdate(name, "WRITE", fpath, "RUNNING"))
            guard_write(name, fpath, s.get("size", 0), safety, backup_fn=backup_fn)
            self.da.write_partition(name, s.get("start", 0), fpath)
            self.step(StepUpdate(name, "WRITE", fpath, "DONE"))

    def erase(self, partitions: List[str], safety: SafetyConfig) -> None:
        self._start_da()
        for name in partitions:
            self.step(StepUpdate(name, "ERASE", "-", "RUNNING"))
            guard_erase(name, safety, context="erase")
            self.da.format_partition(name, 0, 0)
            self.step(StepUpdate(name, "ERASE", "-", "DONE"))

    def close(self) -> None:
        if self.transport:
            self.transport.close()
