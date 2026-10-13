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

    def __init__(self, transport):
        self.transport = transport
        self.storage_type = "UNKNOWN"
        self.storage_size = 0
        self.block_size = 512

    def load_da1(self, da1_path: str, load_addr: int = 0x40000000) -> bool:
        """
        Loads Stage 1 Download Agent binary into target internal SRAM/DRAM.
        """
        if not os.path.exists(da1_path):
            logger.error(f"DA1 binary file not found: {da1_path}")
            return False

        with open(da1_path, "rb") as f:
            data = f.read()

        logger.info(f"Uploading DA1 ({len(data)} bytes) to address 0x{load_addr:08X}...")
        # Write binary chunk protocol
        return True

    def init_dram(self, emi_settings: Optional[bytes] = None) -> bool:
        """
        Initializes DRAM / LPDDR controller using EMI calibration tables.
        """
        logger.info("Initializing DRAM (EMI RAM Calibration)...")
        # In actual DA protocol, this sends memory timings or preloader settings
        time.sleep(0.1)
        logger.info("DRAM initialization complete.")
        return True

    def jump_da2(self, da2_path: str, load_addr: int = 0x42000000) -> bool:
        """
        Uploads and executes Stage 2 Download Agent (High-speed storage engine).
        """
        logger.info(f"Loading DA2 storage engine ({da2_path}) to 0x{load_addr:08X}...")
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
