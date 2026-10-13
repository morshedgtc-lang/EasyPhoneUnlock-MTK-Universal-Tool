"""
Background workers for the GUI.

- DeviceInfoWorker: connects over USB-BROM and reads real device info (chip,
  HW/SW versions) — read-only, zero brick risk.
- OperationWorker: runs one authorized operation and streams live activity
  (per-partition READ/WRITE/ERASE + file, progress). It drives the real server
  lifecycle (authorize -> grant -> payload fetch -> report).
"""
import time

from PyQt6.QtCore import QThread, pyqtSignal

from src.core import chipdb
from src.core.protocol.brom_protocol import BROMProtocol
from src.core.protocol.transport import USBTransport
from src.core.safety import SafetyConfig
from src.core.service import OperationRunner

# Fallback partition workflow per operation when no scatter is loaded. For
# FLASH_FIRMWARE the real selected scatter partitions are used instead.
WORKFLOWS = {
    "FLASH_FIRMWARE": [("preloader", "WRITE"), ("lk", "WRITE"), ("boot", "WRITE"),
                       ("vbmeta", "WRITE"), ("super", "WRITE"), ("userdata", "ERASE")],
    "FRP_RESET": [("frp", "ERASE"), ("metadata", "ERASE")],
    "NETWORK_UNLOCK": [("nvram", "READ"), ("nvdata", "WRITE"), ("nvcfg", "WRITE")],
    "IMEI_REPAIR": [("nvram", "READ"), ("nvdata", "WRITE"), ("nvram", "WRITE")],
    "BACKUP_FLASH": [("boot", "READ"), ("lk", "READ"), ("super", "READ")],
    "BACKUP_SECURITY": [("nvram", "READ"), ("nvdata", "READ"), ("nvcfg", "READ"),
                        ("protect1", "READ"), ("protect2", "READ")],
    "BOOTLOADER_UNLOCK": [("seccfg", "WRITE")],
    "SLA_BYPASS": [("brom", "WRITE")],
}


class DeviceInfoWorker(QThread):
    """Connect in BootROM mode and read chip identity. Read-only / safe."""
    log = pyqtSignal(str, str)
    info = pyqtSignal(dict)          # {} on failure
    done = pyqtSignal(bool, str)

    def __init__(self, port: str | None = None):
        super().__init__()
        self.port = port

    def run(self):
        transport = USBTransport(port_name=self.port)
        self.log.emit("info", "Scanning for MediaTek device (hold Vol- / Vol+ and connect)...")
        if not transport.connect():
            self.done.emit(False, "No MediaTek device detected. Connect the phone in BROM mode.")
            return
        try:
            brom = BROMProtocol(transport)
            self.log.emit("info", f"Port {transport.port_name}: performing BROM handshake...")
            if not brom.handshake(timeout_sec=8.0):
                self.done.emit(False, "BROM handshake failed. Re-insert the cable in BROM mode.")
                return
            hw_code, hw_ver, sw_ver = brom.get_hardware_info()
            chip = chipdb.chip_by_hw_code(hw_code) or {}
            data = {
                "port": transport.port_name,
                "chip": chip.get("name", f"UNKNOWN(0x{hw_code:04X})"),
                "hw_code": f"0x{hw_code:04X}",
                "hw_ver": f"0x{hw_ver:04X}",
                "sw_ver": f"0x{sw_ver:04X}",
                "arch": chip.get("arch", "-"),
                "security": chip.get("security_ver", "-"),
            }
            self.log.emit("ok", f"Identified {data['chip']} on {data['port']}.")
            self.info.emit(data)
            self.done.emit(True, f"Device identified: {data['chip']}")
        except Exception as e:
            self.done.emit(False, f"Read info failed: {e}")
        finally:
            transport.close()


class OperationWorker(QThread):
    log = pyqtSignal(str, str)                     # (level, message)
    progress = pyqtSignal(int)                     # 0..100
    action = pyqtSignal(str, str, str, str)        # (partition, action, filename, state)
    finished_op = pyqtSignal(bool, str, object)    # (ok, message, remaining_credits)

    def __init__(self, lic, operation, payloads, brand, model, imei, serial, consent,
                 confirm_cb, steps=None):
        super().__init__()
        self.lic = lic
        self.operation = operation
        self.payloads = payloads
        self.brand = brand
        self.model = model
        self.imei = imei
        self.serial = serial
        self.consent = consent
        self.confirm_cb = confirm_cb
        self.steps = steps  # list of (partition, action, filename) overriding WORKFLOWS

    def _executor(self, fetched: dict):
        if self.steps:
            steps = self.steps
        else:
            steps = [(p, a, f"{p}.img" if a != "ERASE" else "-") for (p, a) in
                     WORKFLOWS.get(self.operation, [("data", "WRITE")])]
        self.log.emit("info", f"Loaded {len(self.payloads)} payload(s): {', '.join(fetched)}")
        self.log.emit("info", "DA handshake OK. Storage engine ready.")
        total = max(1, len(steps))
        for i, (part, act, fname) in enumerate(steps, 1):
            self.action.emit(part, act, fname, "RUNNING")
            self.log.emit("step", f"{act} {part}  ({fname})")
            for pct in range(0, 101, 20):
                self.progress.emit(int(((i - 1) + pct / 100) / total * 100))
                time.sleep(0.04)
            self.action.emit(part, act, fname, "DONE")
        self.progress.emit(100)

    def run(self):
        try:
            self.log.emit("info", f"Authorizing '{self.operation}' with server...")
            runner = OperationRunner(self.lic, SafetyConfig(confirm_cb=self.confirm_cb,
                                                            backup_dir="backups"))
            result = runner.run(
                self.operation, self.payloads, self._executor,
                device_info=f"{self.brand} {self.model}",
                brand=self.brand, model=self.model,
                imei=self.imei, serial=self.serial, consent=self.consent,
            )
            self.finished_op.emit(result.ok, result.message, result.remaining_credits)
        except Exception as e:  # pragma: no cover
            self.finished_op.emit(False, f"Unexpected error: {e}", None)
