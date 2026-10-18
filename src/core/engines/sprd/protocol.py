"""
Unisoc / Spreadtrum download protocol (BSL).

The device download port (1782:4d00) speaks an HDLC-framed command protocol: the
host sends FDL1 into IRAM and executes it, then FDL2 into DRAM and executes it,
then issues flash read/write/erase commands. Each frame is
[type:2][len:2][data:len][crc:2], HDLC-wrapped with 0x7E delimiters and 0x7D
escaping.

Our own implementation of the public protocol (reference: public spd_dump /
research notes). The FDL loaders themselves are per-platform and supplied by the
operator from the server vault. CRC variant/stage details are confirmed on
hardware; the framing, escaping and sequencing are validated in tests.
"""
import logging
import struct

logger = logging.getLogger("SPRD")

# BSL commands
CMD_CONNECT = 0x00
CMD_START_DATA = 0x01
CMD_MIDST_DATA = 0x02
CMD_END_DATA = 0x03
CMD_EXEC_DATA = 0x04
CMD_READ_FLASH = 0x06
CMD_CHANGE_BAUD = 0x09
CMD_ERASE_FLASH = 0x0A

# BSL replies
REP_ACK = 0x80
REP_VER = 0x81

HDLC_FLAG = 0x7E
HDLC_ESC = 0x7D


class SprdError(RuntimeError):
    pass


def crc16_ccitt(data: bytes) -> int:
    """CRC-CCITT (XModem), used for FDL-stage frames."""
    crc = 0
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) if (crc & 0x8000) else (crc << 1)
            crc &= 0xFFFF
    return crc


def hdlc_escape(data: bytes) -> bytes:
    out = bytearray()
    for b in data:
        if b == HDLC_FLAG:
            out += bytes([HDLC_ESC, 0x5E])
        elif b == HDLC_ESC:
            out += bytes([HDLC_ESC, 0x5D])
        else:
            out.append(b)
    return bytes(out)


def hdlc_unescape(data: bytes) -> bytes:
    out = bytearray()
    i = 0
    while i < len(data):
        if data[i] == HDLC_ESC and i + 1 < len(data):
            nxt = data[i + 1]
            out.append(HDLC_FLAG if nxt == 0x5E else HDLC_ESC if nxt == 0x5D else nxt)
            i += 2
        else:
            out.append(data[i])
            i += 1
    return bytes(out)


def build_frame(ftype: int, data: bytes = b"") -> bytes:
    body = struct.pack(">HH", ftype, len(data)) + data
    body += struct.pack(">H", crc16_ccitt(body))
    return bytes([HDLC_FLAG]) + hdlc_escape(body) + bytes([HDLC_FLAG])


def parse_frame(frame: bytes) -> tuple[int, bytes]:
    """Validate delimiters + CRC; return (type, data)."""
    if len(frame) < 2 or frame[0] != HDLC_FLAG or frame[-1] != HDLC_FLAG:
        raise SprdError("Frame not 0x7E-delimited.")
    body = hdlc_unescape(frame[1:-1])
    if len(body) < 6:
        raise SprdError("Frame too short.")
    ftype, length = struct.unpack(">HH", body[:4])
    data = body[4:4 + length]
    crc = struct.unpack(">H", body[4 + length:6 + length])[0]
    if crc != crc16_ccitt(body[:4 + length]):
        raise SprdError("Frame CRC mismatch.")
    return ftype, data


class SprdProtocol:
    def __init__(self, transport):
        self.transport = transport

    def read_frame(self, max_bytes=1 << 20) -> tuple[int, bytes]:
        # Collect one 0x7E...0x7E frame, one byte at a time.
        buf = bytearray()
        started = False
        for _ in range(max_bytes):
            b = self.transport.read(1)
            if not b:
                break
            if not started:
                if b[0] == HDLC_FLAG:
                    started = True
                    buf += b
                continue
            buf += b
            if b[0] == HDLC_FLAG and len(buf) > 1:
                return parse_frame(bytes(buf))
        raise SprdError("No complete frame received.")

    def _cmd_ack(self, ftype: int, data: bytes = b"") -> None:
        self.transport.write(build_frame(ftype, data))
        rtype, _ = self.read_frame()
        if rtype != REP_ACK:
            raise SprdError(f"Expected ACK, got 0x{rtype:02X}")

    def connect(self) -> None:
        self._cmd_ack(CMD_CONNECT)

    def transfer_fdl(self, addr: int, data: bytes, block: int = 0x840, execute: bool = True) -> None:
        """START_DATA(addr,size) -> MIDST_DATA chunks -> END_DATA -> (EXEC_DATA)."""
        self._cmd_ack(CMD_START_DATA, struct.pack(">II", addr, len(data)))
        sent = 0
        while sent < len(data):
            chunk = data[sent:sent + block]
            self._cmd_ack(CMD_MIDST_DATA, chunk)
            sent += len(chunk)
        self._cmd_ack(CMD_END_DATA)
        if execute:
            self._cmd_ack(CMD_EXEC_DATA)
        logger.info("FDL transferred to 0x%08X (%d bytes)%s", addr, len(data),
                    " + exec" if execute else "")

    def erase_flash(self, addr: int, size: int) -> None:
        self._cmd_ack(CMD_ERASE_FLASH, struct.pack(">II", addr, size))
