"""Unisoc/Spreadtrum BSL protocol tests: CRC, HDLC framing/escaping, FDL transfer."""
import struct

import pytest

from src.core.engines.sprd import protocol as sp
from src.core.engines.sprd.protocol import SprdError, SprdProtocol


class ScriptedTransport:
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


def test_crc16_ccitt_known_value():
    # CRC-CCITT/XModem of b"123456789" is 0x31C3.
    assert sp.crc16_ccitt(b"123456789") == 0x31C3


def test_hdlc_escape_roundtrip():
    raw = bytes([0x00, 0x7E, 0x11, 0x7D, 0x5E, 0x7E])
    esc = sp.hdlc_escape(raw)
    assert 0x7E not in esc  # all flags escaped
    assert sp.hdlc_unescape(esc) == raw


def test_frame_build_parse_roundtrip():
    frame = sp.build_frame(sp.CMD_START_DATA, struct.pack(">II", 0x5000, 1024))
    assert frame[0] == 0x7E and frame[-1] == 0x7E
    ftype, data = sp.parse_frame(frame)
    assert ftype == sp.CMD_START_DATA
    assert struct.unpack(">II", data) == (0x5000, 1024)


def test_frame_with_flag_bytes_in_payload():
    # Payload containing 0x7E/0x7D must survive framing.
    payload = bytes([0x7E, 0x7D, 0x7E, 0x00, 0xFF])
    frame = sp.build_frame(sp.CMD_MIDST_DATA, payload)
    ftype, data = sp.parse_frame(frame)
    assert ftype == sp.CMD_MIDST_DATA and data == payload


def test_parse_frame_bad_crc():
    frame = bytearray(sp.build_frame(sp.CMD_CONNECT, b"\x01\x02"))
    frame[-2] ^= 0xFF  # corrupt a CRC byte (inside the delimiters)
    with pytest.raises(SprdError):
        sp.parse_frame(bytes(frame))


def _ack():
    return sp.build_frame(sp.REP_ACK)


def test_connect_acks():
    t = ScriptedTransport(_ack())
    SprdProtocol(t).connect()
    ftype, _ = sp.parse_frame(_extract_frame(bytes(t.writes)))
    assert ftype == sp.CMD_CONNECT


def test_transfer_fdl_sequence():
    # START + 2 MIDST + END + EXEC => 5 ACKs.
    t = ScriptedTransport(_ack() * 5)
    data = b"\xAB" * (0x840 + 16)  # 2 chunks at block=0x840
    SprdProtocol(t).transfer_fdl(0x5000, data, block=0x840, execute=True)
    frames = _all_frames(bytes(t.writes))
    types = [sp.parse_frame(f)[0] for f in frames]
    assert types == [sp.CMD_START_DATA, sp.CMD_MIDST_DATA, sp.CMD_MIDST_DATA,
                     sp.CMD_END_DATA, sp.CMD_EXEC_DATA]


def test_transfer_fdl_nak_raises():
    t = ScriptedTransport(sp.build_frame(sp.REP_VER))  # not ACK
    with pytest.raises(SprdError):
        SprdProtocol(t).transfer_fdl(0x5000, b"\x00" * 8)


# -- helpers to split concatenated 0x7E-delimited frames from the write stream --
def _all_frames(stream: bytes):
    frames, cur, started = [], bytearray(), False
    for b in stream:
        if b == 0x7E:
            if started:
                cur.append(b); frames.append(bytes(cur)); cur = bytearray(); started = False
            else:
                started = True; cur = bytearray([b])
        elif started:
            cur.append(b)
    return frames


def _extract_frame(stream: bytes):
    return _all_frames(stream)[0]
