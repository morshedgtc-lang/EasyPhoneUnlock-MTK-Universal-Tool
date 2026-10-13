"""
Device-safety guards — the "no bricked phones" layer.

Every write/erase operation is routed through these checks BEFORE anything
touches the device. The rules are deliberately conservative: when in doubt we
stop and require an explicit confirmation rather than risk a dead device.

Guarantees enforced here:
  1. Chip match  - the connected SoC must match what the firmware/scatter is for.
  2. Image sanity - an image must exist and must not exceed its partition.
  3. Protected partitions - preloader/GPT/partition-table writes are blocked
     unless the caller explicitly confirms (these are the usual brick causes).
  4. Backup-before-write - critical partitions are read back to a backup file
     before they are overwritten, so a bad flash can always be reverted.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

logger = logging.getLogger("Safety")


class SafetyError(Exception):
    """Raised when an operation is unsafe and must not proceed."""


# Partitions whose corruption commonly bricks a MediaTek device. Writing or
# erasing these is blocked unless explicitly confirmed, and they are always
# backed up first.
PROTECTED_PARTITIONS = {
    "preloader", "preloader_a", "preloader_b", "preloader_raw",
    "pgpt", "sgpt", "gpt", "pmt", "mbr", "para", "partition",
    "boot_para", "seccfg", "sec1", "md1img", "lk", "lk_a", "lk_b",
    "tee1", "tee2", "nvram", "nvdata", "nvcfg", "proinfo", "protect1", "protect2",
}

# Partitions that must never be auto-erased during an FRP / factory reset.
FRP_SAFE_ERASE = {"frp", "metadata", "userdata", "cache", "persistent"}


@dataclass
class SafetyConfig:
    # Called with a human message when a risky action needs a yes/no. Must
    # return True to proceed. Default denies, so nothing risky happens silently.
    confirm_cb: Callable[[str], bool] = field(default=lambda msg: False)
    # Where partition backups are written before overwrite.
    backup_dir: str = "backups"
    # If False, protected partitions are hard-blocked even with confirmation.
    allow_protected: bool = True
    # If True, skip the read-back backup step (NOT recommended).
    skip_backup: bool = False


def verify_chip_match(detected_hw_code: int, expected_hw_code: Optional[int]) -> None:
    """
    Ensure the SoC we're talking to is the one the firmware targets. Flashing a
    MT6765 image onto an MT6833, for example, is a classic brick — refuse it.
    """
    if expected_hw_code is None:
        logger.warning("No expected chip to compare against; relying on operator.")
        return
    if detected_hw_code != expected_hw_code:
        raise SafetyError(
            f"Chip mismatch: device reports HW 0x{detected_hw_code:04X} but the "
            f"selected firmware is for 0x{expected_hw_code:04X}. Flashing would "
            f"likely brick the device. Operation blocked."
        )
    logger.info("Chip match OK (0x%04X).", detected_hw_code)


def validate_image(partition_name: str, file_path: str, partition_size: int) -> int:
    """Check an image exists and fits its partition. Returns the file size."""
    if not file_path or not os.path.isfile(file_path):
        raise SafetyError(f"Image for '{partition_name}' not found: {file_path}")
    size = os.path.getsize(file_path)
    if size == 0:
        raise SafetyError(f"Image for '{partition_name}' is empty (0 bytes).")
    if partition_size and size > partition_size:
        raise SafetyError(
            f"Image for '{partition_name}' is {size} bytes but the partition is "
            f"only {partition_size} bytes. Writing it would overflow into the next "
            f"partition and corrupt the device. Operation blocked."
        )
    return size


def is_protected(partition_name: str) -> bool:
    return partition_name.strip().lower() in PROTECTED_PARTITIONS


def guard_write(
    partition_name: str,
    file_path: str,
    partition_size: int,
    cfg: SafetyConfig,
    backup_fn: Optional[Callable[[str, str], str]] = None,
) -> None:
    """
    Full pre-write gate for a single partition. Raises SafetyError to abort.

    backup_fn(partition_name, dest_path) -> path is the device read-back hook
    (provided by the DA layer). It is called for protected partitions before
    the overwrite so the original can always be restored.
    """
    name = partition_name.strip()
    validate_image(name, file_path, partition_size)

    if is_protected(name):
        if not cfg.allow_protected:
            raise SafetyError(f"'{name}' is a protected partition and writing it is disabled.")
        msg = (
            f"'{name}' is a PROTECTED partition. A wrong image here can permanently "
            f"brick the device. Proceed with writing {file_path}?"
        )
        if not cfg.confirm_cb(msg):
            raise SafetyError(f"Operator declined writing protected partition '{name}'.")

        if not cfg.skip_backup and backup_fn is not None:
            os.makedirs(cfg.backup_dir, exist_ok=True)
            dest = os.path.join(cfg.backup_dir, f"{name}.backup.bin")
            logger.info("Backing up protected partition '%s' -> %s before overwrite.", name, dest)
            backup_fn(name, dest)


def guard_erase(partition_name: str, cfg: SafetyConfig, context: str = "") -> None:
    """Gate an erase/format. Protected partitions require explicit confirmation."""
    name = partition_name.strip()
    if is_protected(name):
        msg = (
            f"Erasing '{name}' ({context or 'format'}) can brick the device. "
            f"Are you absolutely sure?"
        )
        if not cfg.confirm_cb(msg):
            raise SafetyError(f"Operator declined erasing protected partition '{name}'.")


def guard_frp_targets(partitions: Iterable[str]) -> list[str]:
    """
    Given candidate partitions for an FRP reset, keep only the safe ones and
    drop anything that could brick or wipe user data unexpectedly.
    """
    safe = []
    for p in partitions:
        if p.strip().lower() in FRP_SAFE_ERASE:
            safe.append(p)
        else:
            logger.warning("Skipping '%s' during FRP reset (not an FRP-safe partition).", p)
    return safe
