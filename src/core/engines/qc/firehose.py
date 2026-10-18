"""
Qualcomm Firehose protocol (storage operations after the loader is running).

Firehose is XML over the EDL endpoint: the host sends <configure>, <program>,
<erase>, <read> and <power> tags; the device replies with <response value=...>.
Program/read tags are followed by the raw sector payload.

Our own implementation of the public Firehose protocol (reference: MIT bkerler/edl
and public documentation).
"""
import logging
import re

logger = logging.getLogger("Firehose")

_XML_HDR = '<?xml version="1.0" ?>'


class FirehoseError(RuntimeError):
    pass


def _wrap(inner: str) -> bytes:
    return (f"{_XML_HDR}<data>{inner}</data>").encode("utf-8")


def configure_xml(mem="UFS", max_payload=1048576) -> bytes:
    return _wrap(f'<configure MemoryName="{mem}" Verbose="0" '
                 f'MaxPayloadSizeToTargetInBytes="{max_payload}" ZlpAwareHost="1" '
                 f'SkipStorageInit="0" />')


def program_xml(lun, start_sector, num_sectors, sector_size=4096, filename="") -> bytes:
    return _wrap(f'<program SECTOR_SIZE_IN_BYTES="{sector_size}" '
                 f'num_partition_sectors="{num_sectors}" physical_partition_number="{lun}" '
                 f'start_sector="{start_sector}" filename="{filename}" />')


def erase_xml(lun, start_sector, num_sectors, sector_size=4096) -> bytes:
    return _wrap(f'<erase SECTOR_SIZE_IN_BYTES="{sector_size}" '
                 f'num_partition_sectors="{num_sectors}" physical_partition_number="{lun}" '
                 f'start_sector="{start_sector}" />')


def read_xml(lun, start_sector, num_sectors, sector_size=4096) -> bytes:
    return _wrap(f'<read SECTOR_SIZE_IN_BYTES="{sector_size}" '
                 f'num_partition_sectors="{num_sectors}" physical_partition_number="{lun}" '
                 f'start_sector="{start_sector}" />')


def reset_xml(mode="reset", delay=1) -> bytes:
    return _wrap(f'<power value="{mode}" DelayInSeconds="{delay}" />')


_ACK_RE = re.compile(rb'value\s*=\s*"(ACK|NAK)"', re.IGNORECASE)


def parse_response(data: bytes) -> str:
    """Return 'ACK' or 'NAK' from a device XML response, else raise."""
    m = _ACK_RE.search(data)
    if not m:
        raise FirehoseError(f"No ACK/NAK in response: {data[:200]!r}")
    return m.group(1).decode().upper()


class FirehoseClient:
    def __init__(self, transport, sector_size=4096):
        self.transport = transport
        self.sector_size = sector_size

    def _read_response(self, max_bytes=65536) -> bytes:
        # Firehose responses are </data>-terminated XML; read up to the terminator
        # so consecutive responses are never merged.
        buf = bytearray()
        term = b"</data>"
        while len(buf) < max_bytes:
            b = self.transport.read(1)
            if not b:
                break
            buf += b
            if buf.endswith(term):
                break
        return bytes(buf)

    def _send_and_ack(self, xml: bytes) -> None:
        self.transport.write(xml)
        resp = self._read_response()
        if parse_response(resp) != "ACK":
            raise FirehoseError(f"Device NAK for: {xml[:120]!r}")

    def configure(self, mem="UFS") -> None:
        self._send_and_ack(configure_xml(mem))

    def program(self, lun, start_sector, data: bytes, progress_cb=None) -> None:
        num = (len(data) + self.sector_size - 1) // self.sector_size
        self.transport.write(program_xml(lun, start_sector, num, self.sector_size))
        resp = self._read_response()
        if parse_response(resp) != "ACK":
            raise FirehoseError("Device did not accept <program>.")
        # Stream the sector-aligned payload.
        padded = data + b"\x00" * (num * self.sector_size - len(data))
        sent = 0
        while sent < len(padded):
            chunk = padded[sent:sent + 1048576]
            self.transport.write(chunk)
            sent += len(chunk)
            if progress_cb:
                progress_cb(min(sent, len(data)), len(data))
        if parse_response(self._read_response()) != "ACK":
            raise FirehoseError("Device NAK after <program> data.")

    def erase(self, lun, start_sector, num_sectors) -> None:
        self._send_and_ack(erase_xml(lun, start_sector, num_sectors, self.sector_size))

    def reset(self) -> None:
        self.transport.write(reset_xml())
