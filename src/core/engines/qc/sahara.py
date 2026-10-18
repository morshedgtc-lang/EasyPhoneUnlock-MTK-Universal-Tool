"""
Qualcomm Sahara protocol (EDL loader transfer).

A device in EDL mode (05c6:9008) speaks Sahara first. The host uses it to upload
a SIGNED Firehose programmer into the device, which then jumps to it and switches
to the Firehose protocol. The programmer bytes must be provided by the operator
(from the server vault) — this module only transfers them; it does not and cannot
forge a signed loader.

Our own implementation of the public Sahara protocol (reference: the MIT-licensed
bkerler/edl and public Qualcomm documentation).
"""
import logging
import struct

logger = logging.getLogger("Sahara")

# Command IDs
HELLO = 0x01
HELLO_RESP = 0x02
READ_DATA = 0x03
END_IMAGE_TX = 0x04
DONE = 0x05
DONE_RESP = 0x06
READ_DATA64 = 0x11

# Sahara "mode" values
MODE_IMAGE_TX_PENDING = 0x00
MODE_IMAGE_TX_COMPLETE = 0x01


class SaharaError(RuntimeError):
    pass


def _hdr(command: int, length: int) -> bytes:
    return struct.pack("<II", command, length)


def build_hello_resp(version: int = 2, version_min: int = 1,
                     mode: int = MODE_IMAGE_TX_PENDING) -> bytes:
    """48-byte HELLO_RESP: version, version_min, status(0), mode, 6x reserved."""
    payload = struct.pack("<IIII", version, version_min, 0, mode) + struct.pack("<6I", *([0] * 6))
    return _hdr(HELLO_RESP, 8 + len(payload)) + payload


def parse_header(data: bytes):
    if len(data) < 8:
        raise SaharaError(f"Short Sahara header: {data.hex()}")
    command, length = struct.unpack("<II", data[:8])
    return command, length


class SaharaClient:
    """
    Drives the Sahara image transfer over a transport exposing read(n)/write(b).
    transfer(programmer) serves the programmer bytes the device requests until the
    device reports the image transfer is done.
    """
    def __init__(self, transport):
        self.transport = transport

    def _read_packet(self) -> tuple[int, bytes]:
        header = self.transport.read(8)
        command, length = parse_header(header)
        body = self.transport.read(length - 8) if length > 8 else b""
        return command, body

    def transfer(self, programmer: bytes, max_packets: int = 100000) -> bool:
        for _ in range(max_packets):
            command, body = self._read_packet()

            if command in (HELLO,):
                self.transport.write(build_hello_resp())

            elif command == READ_DATA:
                image_id, offset, length = struct.unpack("<III", body[:12])
                self.transport.write(programmer[offset:offset + length])

            elif command == READ_DATA64:
                image_id, offset, length = struct.unpack("<QQQ", body[:24])
                self.transport.write(programmer[offset:offset + length])

            elif command == END_IMAGE_TX:
                image_id, status = struct.unpack("<II", body[:8])
                if status != 0:
                    raise SaharaError(f"Device rejected image (status 0x{status:08X}).")
                self.transport.write(_hdr(DONE, 8))

            elif command == DONE_RESP:
                logger.info("Sahara image transfer complete.")
                return True

            else:
                raise SaharaError(f"Unexpected Sahara command 0x{command:02X}")
        raise SaharaError("Sahara transfer did not complete.")
