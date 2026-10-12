import time
import struct
import logging
from typing import Optional, Tuple

logger = logging.getLogger("MTK_BROM")

class BROMCommands:
    SYNC_CHAR       = b"\xa0"
    SYNC_RESPONSE   = b"\x5f"
    SYNC_CONFIRM    = b"\x0a\x50\x05"
    
    CMD_GET_HW_CODE = b"\xfd"
    CMD_GET_HW_VER  = b"\xfc"
    CMD_GET_SW_VER  = b"\xfb"
    CMD_READ16      = b"\xa2"
    CMD_READ32      = b"\xd1"
    CMD_WRITE16     = b"\xa1"
    CMD_WRITE32     = b"\xd4"
    CMD_SEND_DA     = b"\xd7"
    CMD_JUMP_DA     = b"\xd5"

class BROMProtocol:
    """
    Low-level BootROM (BROM) Protocol Engine for MediaTek SoCs.
    Handles device synchronization, hardware identification, register read/writes,
    and stage-1 Download Agent handoff.
    """

    def __init__(self, transport):
        """
        :param transport: Object implementing write(data) and read(length)
        """
        self.transport = transport
        self.hw_code = None
        self.hw_sub_code = None
        self.hw_ver = None
        self.sw_ver = None

    def handshake(self, timeout_sec: float = 10.0) -> bool:
        """
        Performs the initial MediaTek BROM handshake sequence.
        """
        logger.info("Waiting for MediaTek BROM handshake...")
        start_time = time.time()
        
        while (time.time() - start_time) < timeout_sec:
            self.transport.write(BROMCommands.SYNC_CHAR)
            resp = self.transport.read(1)
            if resp == BROMCommands.SYNC_RESPONSE:
                self.transport.write(BROMCommands.SYNC_CONFIRM)
                logger.info("BROM handshake synchronized successfully.")
                return True
            time.sleep(0.01)

        logger.error("BROM handshake timed out.")
        return False

    def get_hardware_info(self) -> Tuple[int, int, int, int]:
        """
        Retrieves CPU Hardware Code, Sub-code, HW Version, and SW Version.
        """
        # Read HW Code
        self.transport.write(BROMCommands.CMD_GET_HW_CODE)
        self._check_echo(BROMCommands.CMD_GET_HW_CODE)
        hw_code_bytes = self.transport.read(2)
        self.hw_code = struct.unpack(">H", hw_code_bytes)[0]
        self._check_status()

        # Read HW Sub-code
        self.transport.write(BROMCommands.CMD_GET_HW_VER)
        self._check_echo(BROMCommands.CMD_GET_HW_VER)
        hw_ver_bytes = self.transport.read(2)
        self.hw_ver = struct.unpack(">H", hw_ver_bytes)[0]
        self._check_status()

        # Read SW Version
        self.transport.write(BROMCommands.CMD_GET_SW_VER)
        self._check_echo(BROMCommands.CMD_GET_SW_VER)
        sw_ver_bytes = self.transport.read(2)
        self.sw_ver = struct.unpack(">H", sw_ver_bytes)[0]
        self._check_status()

        logger.info(f"Detected Chip: HW Code = 0x{self.hw_code:04X}, HW Ver = 0x{self.hw_ver:04X}, SW Ver = 0x{self.sw_ver:04X}")
        return self.hw_code, self.hw_ver, self.sw_ver

    def read32(self, addr: int) -> int:
        """Reads a 32-bit register value from target memory."""
        self.transport.write(BROMCommands.CMD_READ32)
        self._check_echo(BROMCommands.CMD_READ32)
        self.transport.write(struct.pack(">I", addr))
        self._check_echo(struct.pack(">I", addr))
        self.transport.write(struct.pack(">I", 1)) # read count 1 word
        self._check_echo(struct.pack(">I", 1))
        self._check_status()
        val_bytes = self.transport.read(4)
        self._check_status()
        return struct.unpack(">I", val_bytes)[0]

    def write32(self, addr: int, val: int) -> bool:
        """Writes a 32-bit register value to target memory."""
        self.transport.write(BROMCommands.CMD_WRITE32)
        self._check_echo(BROMCommands.CMD_WRITE32)
        self.transport.write(struct.pack(">I", addr))
        self._check_echo(struct.pack(">I", addr))
        self.transport.write(struct.pack(">I", 1))
        self._check_echo(struct.pack(">I", 1))
        self._check_status()
        self.transport.write(struct.pack(">I", val))
        self._check_echo(struct.pack(">I", val))
        self._check_status()
        return True

    def disable_watchdog(self, watchdog_base: int = 0x10007000) -> bool:
        """
        Disables hardware watchdog timer to prevent phone rebooting during flash operations.
        """
        wdt_mode_reg = watchdog_base + 0x0000
        # MediaTek WDT Key unlock & disable
        WDT_KEY = 0x22000000
        logger.info(f"Disabling Watchdog Timer at 0x{wdt_mode_reg:08X}...")
        return self.write32(wdt_mode_reg, WDT_KEY)

    def _check_echo(self, expected: bytes):
        echo = self.transport.read(len(expected))
        if echo != expected:
            raise RuntimeError(f"Protocol Echo mismatch! Expected: {expected.hex()}, Got: {echo.hex()}")

    def _check_status(self):
        status = self.transport.read(2)
        if len(status) < 2 or struct.unpack(">H", status)[0] != 0:
            raise RuntimeError(f"BROM returned error status: {status.hex()}")
