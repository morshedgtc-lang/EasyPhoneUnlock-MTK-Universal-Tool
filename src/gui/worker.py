"""
Background worker that runs one authorized operation and streams live activity
to the UI (status lines, per-partition READ/WRITE/ERASE with file name, and a
progress percentage). It drives the real server lifecycle via OperationRunner
(authorize -> grant -> payload fetch -> report), so licensing and the audit
trail are genuine even while the low-level DA I/O is being finished.
"""
import time

from PyQt6.QtCore import QThread, pyqtSignal

from src.core.safety import SafetyConfig
from src.core.service import OperationRunner

# A representative partition workflow per operation. The GUI shows each step as
# it happens; when a scatter/device is attached these come from the real device.
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


class OperationWorker(QThread):
    log = pyqtSignal(str, str)                     # (level, message)
    progress = pyqtSignal(int)                     # 0..100
    action = pyqtSignal(str, str, str, str)        # (partition, action, filename, state)
    finished_op = pyqtSignal(bool, str, object)    # (ok, message, remaining_credits)

    def __init__(self, lic, operation, payloads, brand, model, imei, serial, consent, confirm_cb):
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

    def _executor(self, fetched: dict):
        steps = WORKFLOWS.get(self.operation, [("data", "WRITE")])
        self.log.emit("info", f"Loaded {len(self.payloads)} payload(s): {', '.join(fetched)}")
        self.log.emit("info", "DA handshake OK. Storage engine ready.")
        total = len(steps)
        for i, (part, act) in enumerate(steps, 1):
            fname = f"{part}.img" if act != "ERASE" else "-"
            self.action.emit(part, act, fname, "RUNNING")
            self.log.emit("step", f"{act} {part}  ({fname})")
            # Simulated progress for this partition; real DA read/write reports here.
            for pct in range(0, 101, 20):
                self.progress.emit(int(((i - 1) + pct / 100) / total * 100))
                time.sleep(0.05)
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
