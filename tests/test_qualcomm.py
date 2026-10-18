"""Qualcomm EDL protocol tests: Sahara transfer + Firehose XML/ACK framing."""
import struct

import pytest

from src.core.engines.qc import firehose, sahara
from src.core.engines.qc.firehose import FirehoseClient, FirehoseError, parse_response
from src.core.engines.qc.sahara import SaharaClient, SaharaError


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


def _pkt(cmd, payload=b""):
    return struct.pack("<II", cmd, 8 + len(payload)) + payload


def test_sahara_transfers_programmer():
    programmer = bytes(range(256)) * 4  # 1024 bytes
    # Device: HELLO -> READ_DATA(0,0,1024) -> END_IMAGE_TX(ok) -> DONE_RESP
    script = (
        _pkt(sahara.HELLO, struct.pack("<IIII", 2, 1, 0, 0) + struct.pack("<6I", *([0] * 6)))
        + _pkt(sahara.READ_DATA, struct.pack("<III", 0, 0, len(programmer)))
        + _pkt(sahara.END_IMAGE_TX, struct.pack("<II", 0, 0))
        + _pkt(sahara.DONE_RESP)
    )
    t = ScriptedTransport(script)
    assert SaharaClient(t).transfer(programmer) is True
    # Host must have sent HELLO_RESP, the programmer bytes, and DONE.
    assert programmer in bytes(t.writes)
    assert struct.pack("<II", sahara.HELLO_RESP, 48) in bytes(t.writes)
    assert struct.pack("<II", sahara.DONE, 8) in bytes(t.writes)


def test_sahara_rejects_bad_image_status():
    script = (
        _pkt(sahara.HELLO, struct.pack("<IIII", 2, 1, 0, 0) + struct.pack("<6I", *([0] * 6)))
        + _pkt(sahara.END_IMAGE_TX, struct.pack("<II", 0, 0xDEAD))
    )
    with pytest.raises(SaharaError):
        SaharaClient(ScriptedTransport(script)).transfer(b"x" * 16)


def test_firehose_xml_builders():
    assert b"<configure" in firehose.configure_xml("UFS")
    assert b'start_sector="100"' in firehose.program_xml(0, 100, 8)
    assert b"<erase" in firehose.erase_xml(0, 0, 4)
    assert b'value="reset"' in firehose.reset_xml()


def test_parse_response_ack_nak():
    assert parse_response(b'<?xml?><data><response value="ACK"/></data>') == "ACK"
    assert parse_response(b'<data><response value="NAK" /></data>') == "NAK"
    with pytest.raises(FirehoseError):
        parse_response(b"<data></data>")


def test_firehose_configure_ack():
    t = ScriptedTransport(b'<?xml?><data><response value="ACK"/></data>')
    FirehoseClient(t).configure("UFS")
    assert b"<configure" in bytes(t.writes)


def test_firehose_program_streams_data():
    # ACK after <program>, then ACK after the data.
    script = (b'<data><response value="ACK"/></data>'
              + b'<data><response value="ACK"/></data>')
    t = ScriptedTransport(script)
    fh = FirehoseClient(t, sector_size=512)
    payload = b"BOOTDATA" * 100  # 800 bytes -> 2 sectors (1024, padded)
    fh.program(lun=0, start_sector=256, data=payload)
    w = bytes(t.writes)
    assert b"<program" in w and b'start_sector="256"' in w
    assert payload in w                      # data streamed
    assert len(w.split(b"</data>")[-1]) >= 1024 - 0  # padded to sector multiple


def test_firehose_program_nak_raises():
    t = ScriptedTransport(b'<data><response value="NAK"/></data>')
    with pytest.raises(FirehoseError):
        FirehoseClient(t).program(0, 0, b"x" * 16)
