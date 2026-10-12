import sys
import serial
import serial.tools.list_ports
import logging
from typing import Optional

logger = logging.getLogger("USBTransport")

class USBTransport:
    """
    Handles USB / Serial COM Port communication with MediaTek devices
    in BootROM (0x0E8D:0x0003), Preloader (0x0E8D:0x2000), or DA (0x0E8D:0x2001) mode.
    """

    MTK_VID = 0x0E8D
    MTK_PID_BROM = 0x0003
    MTK_PID_PRELOADER = 0x2000
    MTK_PID_DA = 0x2001

    def __init__(self, port_name: Optional[str] = None, baudrate: int = 115200, timeout: float = 1.0):
        self.port_name = port_name
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn: Optional[serial.Serial] = None

    @classmethod
    def find_mtk_port(cls) -> Optional[str]:
        """
        Auto-detects active MediaTek USB VCOM or BROM Port.
        """
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Check VID / PID or descriptions
            if p.vid == cls.MTK_VID or "mediatek" in p.description.lower() or "mtk" in p.description.lower():
                logger.info(f"Discovered MTK Port: {p.device} ({p.description})")
                return p.device
        return None

    def connect(self) -> bool:
        if not self.port_name:
            self.port_name = self.find_mtk_port()

        if not self.port_name:
            logger.error("No MediaTek device detected. Please connect phone holding Vol- / Vol+ buttons.")
            return False

        try:
            self.serial_conn = serial.Serial(
                port=self.port_name,
                baudrate=self.baudrate,
                timeout=self.timeout,
                write_timeout=self.timeout
            )
            logger.info(f"Connected to {self.port_name} at {self.baudrate} baud.")
            return True
        except Exception as e:
            logger.error(f"Failed to open port {self.port_name}: {e}")
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
