"""
Low-level MediaTek BootROM (BROM) protocol.

Implements the documented MTK BROM wire protocol: the complement-echo handshake,
hardware identification, 16/32-bit register read/write with echo + status
framing, and Download Agent upload (send_da) with a 16-bit checksum + jump_da.

This is our own implementation of the public protocol (reference: the
GPL-licensed mtkclient and public BROM documentation). Byte-level details vary
across BROM revisions; the framing here follows the common legacy path and is
validated by a device-simulator in tests. Final verification requires hardware.
"""
import logging
import struct
import time
from typing import Tuple

logger = logging.getLogger("MTK_BROM")


class BROMError(RuntimeError):
    pass


class BROMCommands:
    # Handshake bytes (device replies with the bitwise complement of each).
    START_CMD = bytes([0xA0, 0x0A, 0x50, 0x05])

    GET_HW_CODE = 0xFD
    GET_HW_SW_VER = 0xFC
    READ16 = 0xA2
    WRITE16 = 0xA1
    READ32 = 0xD1
    WRITE32 = 0xD4
    SEND_DA = 0xD7
    JUMP_DA = 0xD5


class BROMProtocol:
    def __init__(self, transport):
        self.transport = transport
        self.hw_code = None
        self.hw_sub_code = None
        self.hw_ver = None
        self.sw_ver = None

    # ------------------------------------------------------------------ #
    # low-level framing helpers
    # ------------------------------------------------------------------ #
    def _echo(self, data: bytes) -> None:
        """Write bytes and verify the device echoes them back unchanged."""
        self.transport.write(data)
        echo = self.transport.read(len(data))
        if echo != data:
            raise BROMError(f"Echo mismatch: sent {data.hex()}, got {echo.hex()}")

    def _cmd(self, command: int) -> None:
        """Send a command byte; the device echoes it back."""
        self._echo(bytes([command]))

    def _status(self) -> int:
        """Read a 2-byte status word; 0 means OK. Returns the raw value."""
        raw = self.transport.read(2)
        if len(raw) < 2:
            raise BROMError(f"Short status read: {raw.hex()}")
        status = struct.unpack(">H", raw)[0]
        return status

    def _expect_ok(self) -> None:
        st = self._status()
        if st != 0:
            raise BROMError(f"BROM returned error status 0x{st:04X}")

    # ------------------------------------------------------------------ #
    # handshake + identity
    # ------------------------------------------------------------------ #
    def handshake(self, timeout_sec: float = 10.0) -> bool:
        """
        MTK start handshake: for each byte B in A0 0A 50 05, the device must
        reply with ~B (0x5F 0xF5 0xAF 0xFA). Retries until the device appears.
        """
        logger.info("Waiting for MediaTek BROM handshake...")
        start = time.time()
        while (time.time() - start) < timeout_sec:
            if self._try_start():
                logger.info("BROM handshake synchronized.")
                return True
            time.sleep(0.02)
        logger.error("BROM handshake timed out.")
        return False

    def _try_start(self) -> bool:
        for b in BROMCommands.START_CMD:
            self.transport.write(bytes([b]))
            resp = self.transport.read(1)
            if len(resp) != 1 or resp[0] != ((~b) & 0xFF):
                return False
        return True

    def get_hardware_info(self) -> Tuple[int, int, int]:
        """Read HW code, HW version and SW version. Also stores hw_sub_code."""
        self._cmd(BROMCommands.GET_HW_CODE)
        self.hw_code = struct.unpack(">H", self.transport.read(2))[0]
        self._expect_ok()

        self._cmd(BROMCommands.GET_HW_SW_VER)
        self.hw_sub_code = struct.unpack(">H", self.transport.read(2))[0]
        self.hw_ver = struct.unpack(">H", self.transport.read(2))[0]
        self.sw_ver = struct.unpack(">H", self.transport.read(2))[0]
        self._expect_ok()

        logger.info("Chip: HW 0x%04X sub 0x%04X HWver 0x%04X SWver 0x%04X",
                    self.hw_code, self.hw_sub_code, self.hw_ver, self.sw_ver)
        return self.hw_code, self.hw_ver, self.sw_ver

    # ------------------------------------------------------------------ #
    # register access
    # ------------------------------------------------------------------ #
    def read32(self, addr: int, count: int = 1) -> list[int]:
        self._cmd(BROMCommands.READ32)
        self._echo(struct.pack(">I", addr))
        self._echo(struct.pack(">I", count))
        self._expect_ok()
        values = [struct.unpack(">I", self.transport.read(4))[0] for _ in range(count)]
        self._expect_ok()
        return values

    def write32(self, addr: int, values) -> bool:
        if isinstance(values, int):
            values = [values]
        self._cmd(BROMCommands.WRITE32)
        self._echo(struct.pack(">I", addr))
        self._echo(struct.pack(">I", len(values)))
        self._expect_ok()
        for v in values:
            self._echo(struct.pack(">I", v & 0xFFFFFFFF))
        self._expect_ok()
        return True

    def read16(self, addr: int, count: int = 1) -> list[int]:
        self._cmd(BROMCommands.READ16)
        self._echo(struct.pack(">I", addr))
        self._echo(struct.pack(">I", count))
        self._expect_ok()
        values = [struct.unpack(">H", self.transport.read(2))[0] for _ in range(count)]
        self._expect_ok()
        return values

    def write16(self, addr: int, values) -> bool:
        if isinstance(values, int):
            values = [values]
        self._cmd(BROMCommands.WRITE16)
        self._echo(struct.pack(">I", addr))
        self._echo(struct.pack(">I", len(values)))
        self._expect_ok()
        for v in values:
            self._echo(struct.pack(">H", v & 0xFFFF))
        self._expect_ok()
        return True

    def disable_watchdog(self, watchdog_base: int = 0x10007000) -> bool:
        """Write the WDT disable key so the device doesn't reboot mid-operation."""
        WDT_KEY = 0x22000000
        logger.info("Disabling watchdog at 0x%08X", watchdog_base)
        return self.write32(watchdog_base, WDT_KEY)

    # ------------------------------------------------------------------ #
    # Download Agent upload
    # ------------------------------------------------------------------ #
    @staticmethod
    def _checksum16(data: bytes) -> int:
        return sum(data) & 0xFFFF

    def send_da(self, da_address: int, da_data: bytes, sig_len: int = 0,
                block: int = 0x1000) -> int:
        """
        Upload a Download Agent to SRAM/DRAM at da_address. Returns the device
        checksum. Framing: cmd, address, size, sig_len, status, data blocks,
        device checksum (2 bytes), status.
        """
        size = len(da_data)
        self._cmd(BROMCommands.SEND_DA)
        self._echo(struct.pack(">I", da_address))
        self._echo(struct.pack(">I", size))
        self._echo(struct.pack(">I", sig_len))
        self._expect_ok()

        sent = 0
        while sent < size:
            chunk = da_data[sent:sent + block]
            self.transport.write(chunk)
            sent += len(chunk)

        dev_checksum = struct.unpack(">H", self.transport.read(2))[0]
        self._expect_ok()
        local = self._checksum16(da_data)
        if dev_checksum != local:
            raise BROMError(f"DA checksum mismatch: device 0x{dev_checksum:04X} "
                            f"!= local 0x{local:04X}")
        logger.info("DA uploaded (%d bytes) to 0x%08X, checksum 0x%04X OK", size, da_address, dev_checksum)
        return dev_checksum

    def jump_da(self, da_address: int) -> bool:
        """Transfer execution to the uploaded DA."""
        self._cmd(BROMCommands.JUMP_DA)
        self._echo(struct.pack(">I", da_address))
        self._expect_ok()
        logger.info("Jumped to DA at 0x%08X", da_address)
        return True
