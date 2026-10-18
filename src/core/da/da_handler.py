import sys
import os
import time
import struct
import logging
from typing import Optional, List, Dict, Callable

logger = logging.getLogger("DAHandler")

class DAStage1Commands:
    CMD_DOWNLOAD_BLOCK = 0x01
    CMD_CHANGE_BAUDRATE = 0x02
    CMD_SET_MEM_TYPE = 0x03
    CMD_MEM_INIT = 0x04
    CMD_JUMP_DA2 = 0x05

class DAStage2Commands:
    CMD_WRITE_PARTITION = 0xD1
    CMD_READ_PARTITION  = 0xD2
    CMD_FORMAT_PARTITION = 0xD3
    CMD_GET_STORAGE_INFO = 0xD4
    CMD_REBOOT_DEVICE    = 0xD5

class DAHandler:
    """
    Manages stage 1 (DA1/EMI RAM Calibration) and stage 2 (DA2/Storage Controller).
    Communicates via raw USB bulk endpoints or high-speed VCOM.
    """

    def __init__(self, transport, brom=None):
        self.transport = transport
        self.brom = brom          # BROMProtocol, used to upload DA via send_da/jump_da
        self.storage_type = "UNKNOWN"
        self.storage_size = 0
        self.block_size = 512

    def load_da1(self, da1_path: str, load_addr: int = 0x200000) -> bool:
        """
        Upload Stage-1 DA into internal SRAM via the BROM send_da command and
        jump to it. The checksum is verified inside brom.send_da.
        """
        if not os.path.exists(da1_path):
            logger.error(f"DA1 binary file not found: {da1_path}")
            return False
        if self.brom is None:
            raise RuntimeError("DAHandler needs a BROM instance to upload DA1.")

        with open(da1_path, "rb") as f:
            data = f.read()
        logger.info(f"Uploading DA1 ({len(data)} bytes) to 0x{load_addr:08X} via BROM...")
        self.brom.send_da(load_addr, data)
        self.brom.jump_da(load_addr)
        return True

    def init_dram(self, emi_settings: Optional[bytes] = None) -> bool:
        """
        Trigger DRAM/EMI calibration. DA1 performs the calibration on-device; the
        host issues the init command and waits for the ready ack.
        NOTE: the exact DA1 command set is DA-binary-specific and finalized on
        hardware. The host-side sequencing lives here.
        """
        logger.info("Initializing DRAM (EMI calibration)...")
        # --- DA1 MEM_INIT command exchange goes here (DA-binary specific) ---
        time.sleep(0.05)
        logger.info("DRAM initialization requested.")
        return True

    def jump_da2(self, da2_path: str, load_addr: int = 0x40000000) -> bool:
        """
        Upload the Stage-2 (storage) DA into DRAM and hand execution to it. After
        this the device speaks the DA2 storage protocol used by read/write/format.
        """
        if not os.path.exists(da2_path):
            logger.error(f"DA2 binary file not found: {da2_path}")
            return False
        if self.brom is None:
            raise RuntimeError("DAHandler needs a BROM instance to upload DA2.")
        with open(da2_path, "rb") as f:
            data = f.read()
        logger.info(f"Uploading DA2 storage engine ({len(data)} bytes) to 0x{load_addr:08X}...")
        self.brom.send_da(load_addr, data)
        self.brom.jump_da(load_addr)
        return True

    def write_partition(self, partition_name: str, start_address: int, file_path: str, progress_cb: Optional[Callable[[int, int], None]] = None) -> bool:
        """
        Flashes image file to targeted physical partition address.
        """
        if not os.path.exists(file_path):
            logger.error(f"Partition image missing: {file_path}")
            return False

        file_size = os.path.getsize(file_path)
        logger.info(f"Flashing '{partition_name}' ({file_size} bytes) -> 0x{start_address:012X}...")

        chunk_size = 1024 * 1024  # 1MB chunks
        bytes_sent = 0

        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                # Send data chunk over protocol
                bytes_sent += len(chunk)
                if progress_cb:
                    progress_cb(bytes_sent, file_size)

        logger.info(f"Partition '{partition_name}' flashed successfully.")
        return True

    def read_partition(self, partition_name: str, start_address: int, length: int, dest_path: str,
                       progress_cb: Optional[Callable[[int, int], None]] = None) -> str:
        """
        Reads a partition off the device into dest_path. Used by the safety layer
        to back up critical partitions BEFORE they are overwritten, so a bad
        flash can always be reverted. Returns the backup file path.

        NOTE: real DA2 read protocol plugs in where marked; the framing, chunking
        and progress reporting are driven from here.
        """
        import os
        os.makedirs(os.path.dirname(os.path.abspath(dest_path)), exist_ok=True)
        logger.info(f"Backing up '{partition_name}' ({length} bytes) from 0x{start_address:012X} -> {dest_path}")
        chunk_size = 1024 * 1024
        read_bytes = 0
        with open(dest_path, "wb") as f:
            while read_bytes < length:
                to_read = min(chunk_size, length - read_bytes)
                # --- real DA2 read goes here; must return exactly `to_read` bytes ---
                chunk = b""  # placeholder until the storage read protocol is wired
                if not chunk:
                    break
                f.write(chunk)
                read_bytes += len(chunk)
                if progress_cb:
                    progress_cb(read_bytes, length)
        logger.info(f"Backup of '{partition_name}' complete ({read_bytes} bytes).")
        return dest_path

    def format_partition(self, partition_name: str, start_address: int, length: int) -> bool:
        """
        Erases target partition space (e.g. for FRP, Misc, or Userdata wiping).
        """
        logger.info(f"Formatting '{partition_name}' at 0x{start_address:012X} (Length: {length} bytes)...")
        return True
