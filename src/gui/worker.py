"""
Background workers for the GUI.

- DeviceInfoWorker: connects over USB-BROM and reads real device info. Read-only.
- OperationWorker: runs one authorized operation through the REAL device engine
  (MTK/Qualcomm/Unisoc) selected by chip, streaming genuine per-partition
  progress. Server lifecycle: authorize -> grant -> payload fetch -> report.

There is no simulated operation path: if no device, no DA/loader, or an
unsupported step is encountered, the engine raises and the op is reported failed
(and the credit is refunded). Success is only reported when real work completed.
"""
from PyQt6.QtCore import QThread, pyqtSignal

from src.core import chipdb
from src.core.engines import registry
from src.core.engines.base import StepUpdate
from src.core.protocol.brom_protocol import BROMProtocol
from src.core.protocol.transport import USBTransport, open_transport
from src.core.safety import SafetyConfig, SafetyError, guard_frp_targets
from src.core.service import OperationRunner


class AuthWorker(QThread):
    """Login or register off the UI thread so the window never freezes."""
    done = pyqtSignal(str, dict)   # (action, response)

    def __init__(self, lic, action: str, username: str, password: str):
        super().__init__()
        self.lic = lic
        self.action = action
        self.username = username
        self.password = password

    def run(self):
        if self.action == "login":
            res = self.lic.login(self.username, self.password)
        else:
            res = self.lic.register(self.username, self.password)
        self.done.emit(self.action, res)


class FirmwareLoadWorker(QThread):
    """Decrypt/unpack a firmware file (OFP/scatter) off the UI thread."""
    log = pyqtSignal(str, str)
    done = pyqtSignal(object, str)

    def __init__(self, path: str, extract_root: str):
        super().__init__()
        self.path = path
        self.extract_root = extract_root

    def run(self):
        try:
            from src.core.firmware import loader
            fw = loader.load(self.path, self.extract_root, log=lambda m: self.log.emit("step", m))
            self.done.emit(fw, "")
        except Exception as e:
            self.done.emit(None, str(e))


class DeviceInfoWorker(QThread):
    """Connect in BootROM mode and read chip identity. Read-only / safe."""
    log = pyqtSignal(str, str)
    info = pyqtSignal(dict)
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
            self.log.emit("info", f"Port {transport.port_name}: BROM handshake...")
            if not brom.handshake(timeout_sec=8.0):
                self.done.emit(False, "BROM handshake failed. Re-insert the cable in BROM mode.")
                return
            hw_code, hw_ver, sw_ver = brom.get_hardware_info()
            chip = chipdb.chip_by_hw_code(hw_code) or {}
            data = {
                "port": transport.port_name,
                "chip": chip.get("name", f"UNKNOWN(0x{hw_code:04X})"),
                "hw_code": f"0x{hw_code:04X}", "hw_ver": f"0x{hw_ver:04X}",
                "sw_ver": f"0x{sw_ver:04X}", "arch": chip.get("arch", "-"),
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
    log = pyqtSignal(str, str)
    progress = pyqtSignal(int)
    action = pyqtSignal(str, str, str, str)        # partition, action, filename, state
    finished_op = pyqtSignal(bool, str, object)

    def __init__(self, lic, operation, payloads, brand, model, chip, imei, serial, consent,
                 confirm_cb, flash_steps=None, erase_targets=None):
        super().__init__()
        self.lic = lic
        self.operation = operation
        self.payloads = payloads
        self.brand = brand
        self.model = model
        self.chip = chip
        self.imei = imei
        self.serial = serial
        self.consent = consent
        self.confirm_cb = confirm_cb
        self.flash_steps = flash_steps or []      # [{partition,file,start,size}]
        self.erase_targets = erase_targets or []  # [name, ...]

    # --- engine step callback -> UI ---
    def _on_step(self, u: StepUpdate):
        self.action.emit(u.partition, u.action, u.filename, u.state)

    def _build_engine(self, fetched: dict):
        platform = registry.platform_for_chip(self.chip)
        if platform == "unknown":
            from src.core.engines.base import EngineError
            raise EngineError(f"Unknown platform for chip '{self.chip}'.")
        cls = registry.get_engine_class(platform)
        self.log.emit("info", f"Engine: {platform.upper()} for {self.chip}")

        if platform == "mtk":
            return cls(log=self.log.emit, step=self._on_step,
                       da1=fetched.get("da1"), da2=fetched.get("da2"))
        # Qualcomm / Unisoc need their own transport + loader bytes from the vault.
        transport = open_transport(platform)
        loaders = {k: open(v, "rb").read() for k, v in fetched.items()}
        if platform == "qualcomm":
            return cls(log=self.log.emit, step=self._on_step, transport=transport,
                       loader=loaders.get("loader") or loaders.get("firehose"))
        return cls(log=self.log.emit, step=self._on_step, transport=transport,
                   fdl1=loaders.get("fdl1"), fdl2=loaders.get("fdl2"))

    def _executor(self, fetched: dict):
        from src.core.engines.base import EngineError
        safety = SafetyConfig(confirm_cb=self.confirm_cb, backup_dir="backups")
        engine = self._build_engine(fetched)

        self.log.emit("info", "Connecting to device (hold Vol keys + plug in)...")
        if not engine.connect():
            raise EngineError("Device not detected / handshake failed.")
        try:
            info = engine.identify()
            self.log.emit("ok", f"Connected: {info.chip} on {info.port}")
            # Safety chip-match: detected chip vs the model you selected.
            if self.chip and not info.chip.startswith("UNKNOWN") and info.chip != self.chip:
                raise SafetyError(f"Chip mismatch: device is {info.chip} but you selected "
                                  f"{self.chip}. Operation blocked to protect the device.")

            if self.operation == "FLASH_FIRMWARE":
                if not self.flash_steps:
                    raise EngineError("No partitions selected to flash.")
                engine.flash(self.flash_steps, safety)
            elif self.operation == "FRP_RESET":
                targets = guard_frp_targets(self.erase_targets) or ["frp"]
                engine.erase(targets, safety)
            else:
                raise EngineError(
                    f"'{self.operation}' needs a partition map for {info.chip} that is not "
                    f"loaded yet. Flash and FRP are wired; others are enabled per device.")
        finally:
            engine.close()

    def run(self):
        try:
            self.log.emit("info", f"Authorizing '{self.operation}' with server...")
            runner = OperationRunner(self.lic, SafetyConfig(confirm_cb=self.confirm_cb))
            result = runner.run(
                self.operation, self.payloads, self._executor,
                device_info=f"{self.brand} {self.model} [{self.chip}]",
                brand=self.brand, model=self.model,
                imei=self.imei, serial=self.serial, consent=self.consent,
            )
            self.finished_op.emit(result.ok, result.message, result.remaining_credits)
        except Exception as e:  # pragma: no cover
            self.finished_op.emit(False, f"Unexpected error: {e}", None)
