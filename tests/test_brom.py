"""
BROM protocol framing tests using a scripted transport that plays the device
side. Validates the handshake, hardware-info, register R/W and DA-upload framing
(echo + status discipline, checksum). Byte-for-byte hardware truth still needs a
real device, but these lock the wire framing our code emits/consumes.
"""
import struct

import pytest

from src.core.protocol.brom_protocol import BROMError, BROMProtocol


class ScriptedTransport:
    """Returns pre-scripted bytes on read(); records everything written."""
    def __init__(self, read_script: bytes):
        self._buf = bytearray(read_script)
        self.writes = bytearray()

    def write(self, data: bytes) -> int:
        self.writes += data
        return len(data)

    def read(self, n: int) -> bytes:
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out


def test_handshake_complement_echo():
    # Device replies with ~B for each start byte.
    script = bytes([0x5F, 0xF5, 0xAF, 0xFA])
    t = ScriptedTransport(script)
    brom = BROMProtocol(t)
    assert brom.handshake(timeout_sec=1.0) is True
    assert bytes(t.writes) == bytes([0xA0, 0x0A, 0x50, 0x05])


def test_handshake_fails_on_bad_reply():
    t = ScriptedTransport(bytes([0x00, 0x00, 0x00, 0x00]))
    brom = BROMProtocol(t)
    assert brom.handshake(timeout_sec=0.3) is False


def test_get_hardware_info():
    script = (
        bytes([0xFD]) + struct.pack(">H", 0x0766) + b"\x00\x00"          # hw code + status
        + bytes([0xFC]) + struct.pack(">H", 0x8A00) + struct.pack(">H", 0xCA00)
        + struct.pack(">H", 0x0001) + b"\x00\x00"                        # sub/ver/sw + status
    )
    brom = BROMProtocol(ScriptedTransport(script))
    hw, hwver, sw = brom.get_hardware_info()
    assert hw == 0x0766 and brom.hw_sub_code == 0x8A00
    assert hwver == 0xCA00 and sw == 0x0001


def test_write32_framing():
    # cmd echo, addr echo, count echo, status, value echo, status
    script = (bytes([0xD4]) + struct.pack(">I", 0x10007000) + struct.pack(">I", 1)
              + b"\x00\x00" + struct.pack(">I", 0x22000000) + b"\x00\x00")
    t = ScriptedTransport(script)
    brom = BROMProtocol(t)
    assert brom.write32(0x10007000, 0x22000000) is True
    # The host must have written: cmd, addr, count, value.
    assert bytes(t.writes) == (bytes([0xD4]) + struct.pack(">I", 0x10007000)
                               + struct.pack(">I", 1) + struct.pack(">I", 0x22000000))


def test_read32_returns_value():
    script = (bytes([0xD1]) + struct.pack(">I", 0x100A00) + struct.pack(">I", 1)
              + b"\x00\x00" + struct.pack(">I", 0xDEADBEEF) + b"\x00\x00")
    brom = BROMProtocol(ScriptedTransport(script))
    assert brom.read32(0x100A00) == [0xDEADBEEF]


def test_error_status_raises():
    # read32 with a non-zero status word after echoes.
    script = (bytes([0xD1]) + struct.pack(">I", 0) + struct.pack(">I", 1) + b"\x00\x01")
    brom = BROMProtocol(ScriptedTransport(script))
    with pytest.raises(BROMError):
        brom.read32(0)


def test_send_da_checksum_ok():
    da = b"\x01\x02\x03\x04\x05\x06\x07\x08" * 4  # 32 bytes
    checksum = sum(da) & 0xFFFF
    script = (bytes([0xD7]) + struct.pack(">I", 0x200000) + struct.pack(">I", len(da))
              + struct.pack(">I", 0) + b"\x00\x00"           # echoes + status
              + struct.pack(">H", checksum) + b"\x00\x00")   # device checksum + status
    t = ScriptedTransport(script)
    brom = BROMProtocol(t)
    assert brom.send_da(0x200000, da) == checksum
    assert da in bytes(t.writes)  # the DA payload was transmitted


def test_send_da_checksum_mismatch_raises():
    da = b"\xAA" * 16
    bad = (sum(da) + 1) & 0xFFFF
    script = (bytes([0xD7]) + struct.pack(">I", 0x200000) + struct.pack(">I", len(da))
              + struct.pack(">I", 0) + b"\x00\x00" + struct.pack(">H", bad) + b"\x00\x00")
    brom = BROMProtocol(ScriptedTransport(script))
    with pytest.raises(BROMError):
        brom.send_da(0x200000, da)


def test_jump_da_framing():
    script = bytes([0xD5]) + struct.pack(">I", 0x200000) + b"\x00\x00"
    t = ScriptedTransport(script)
    brom = BROMProtocol(t)
    assert brom.jump_da(0x200000) is True
    assert bytes(t.writes) == bytes([0xD5]) + struct.pack(">I", 0x200000)


# ---- DA upload path through DAHandler + BROM ----
def test_da_handler_uploads_da1(tmp_path):
    from src.core.da.da_handler import DAHandler
    da = b"\x11\x22\x33\x44" * 8
    checksum = sum(da) & 0xFFFF
    # send_da framing (@0x200000) then jump_da framing.
    script = (bytes([0xD7]) + struct.pack(">I", 0x200000) + struct.pack(">I", len(da))
              + struct.pack(">I", 0) + b"\x00\x00" + struct.pack(">H", checksum) + b"\x00\x00"
              + bytes([0xD5]) + struct.pack(">I", 0x200000) + b"\x00\x00")
    t = ScriptedTransport(script)
    brom = BROMProtocol(t)
    da_path = tmp_path / "da1.bin"
    da_path.write_bytes(da)
    h = DAHandler(t, brom)
    assert h.load_da1(str(da_path), load_addr=0x200000) is True
    assert da in bytes(t.writes)
