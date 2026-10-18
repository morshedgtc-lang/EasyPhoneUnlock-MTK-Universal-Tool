import logging
from typing import List, Optional, Tuple

import serial
import serial.tools.list_ports

logger = logging.getLogger("USBTransport")

# USB (vid, pid) download/emergency signatures per platform.
PLATFORM_USB = {
    "mtk": [(0x0E8D, 0x0003), (0x0E8D, 0x2000), (0x0E8D, 0x2001)],
    "qualcomm": [(0x05C6, 0x9008), (0x05C6, 0x900E)],
    "unisoc": [(0x1782, 0x4D00), (0x1782, 0x4D01)],
}


class USBTransport:
    """
    Serial/COM-port transport to a device in download mode. Works for MediaTek
    (0E8D), Qualcomm EDL (05C6:9008) and Unisoc/Spreadtrum (1782:4D00) — the OS
    exposes each as a COM port via the vendor driver.
    """

    MTK_VID = 0x0E8D

    def __init__(self, port_name: Optional[str] = None, baudrate: int = 115200,
                 timeout: float = 1.0, vid_pids: Optional[List[Tuple[int, int]]] = None):
        self.port_name = port_name
        self.baudrate = baudrate
        self.timeout = timeout
        self.vid_pids = vid_pids or PLATFORM_USB["mtk"]
        self.serial_conn: Optional[serial.Serial] = None

    @classmethod
    def find_port(cls, vid_pids: List[Tuple[int, int]]) -> Optional[str]:
        for p in serial.tools.list_ports.comports():
            if p.vid is not None and (p.vid, p.pid) in vid_pids:
                logger.info("Discovered port %s (%s) [%04X:%04X]", p.device, p.description,
                            p.vid or 0, p.pid or 0)
                return p.device
        return None

    @classmethod
    def find_mtk_port(cls) -> Optional[str]:
        port = cls.find_port(PLATFORM_USB["mtk"])
        if port:
            return port
        for p in serial.tools.list_ports.comports():
            d = (p.description or "").lower()
            if "mediatek" in d or "mtk" in d or p.vid == cls.MTK_VID:
                return p.device
        return None

    def connect(self) -> bool:
        if not self.port_name:
            self.port_name = self.find_port(self.vid_pids)
        if not self.port_name:
            logger.error("No device detected on the expected download port.")
            return False
        try:
            self.serial_conn = serial.Serial(
                port=self.port_name, baudrate=self.baudrate,
                timeout=self.timeout, write_timeout=self.timeout)
            logger.info("Connected to %s at %d baud.", self.port_name, self.baudrate)
            return True
        except Exception as e:
            logger.error("Failed to open port %s: %s", self.port_name, e)
            return False

    def write(self, data: bytes) -> int:
        if not self.serial_conn or not self.serial_conn.is_open:
            raise ConnectionError("Port not open")
        return self.serial_conn.write(data)

    def read(self, length: int) -> bytes:
        if not self.serial_conn or not self.serial_conn.is_open:
            raise ConnectionError("Port not open")
        return self.serial_conn.read(length)

    def close(self):
        if self.serial_conn and self.serial_conn.is_open:
            self.serial_conn.close()
            logger.info("USB connection closed.")


def open_transport(platform: str, timeout: float = 1.0) -> Optional[USBTransport]:
    """Find and open the download port for a platform. Returns None if absent."""
    vid_pids = PLATFORM_USB.get(platform)
    if not vid_pids:
        return None
    t = USBTransport(timeout=timeout, vid_pids=vid_pids)
    return t if t.connect() else None
