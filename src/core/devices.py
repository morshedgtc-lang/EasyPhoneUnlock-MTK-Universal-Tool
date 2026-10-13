"""Loader for config/device_models.json (brand/model/operation registry)."""
import json
from functools import lru_cache
from typing import Dict, List

from src.core.paths import config_path

# Human labels + the vault payloads each operation needs, mirrored from the
# server's operation keys.
OPERATION_LABELS: Dict[str, str] = {
    "FLASH_FIRMWARE": "Flash Firmware",
    "FRP_RESET": "FRP Erase",
    "NETWORK_UNLOCK": "Network Unlock",
    "IMEI_REPAIR": "IMEI Repair",
    "BACKUP_FLASH": "Backup Flash File",
    "BACKUP_SECURITY": "Backup Security File",
    "BOOTLOADER_UNLOCK": "Bootloader Unlock",
    "SLA_BYPASS": "SLA/DAA Bypass",
}

OPERATION_PAYLOADS: Dict[str, List[str]] = {
    "FLASH_FIRMWARE": ["da1", "da2"],
    "FRP_RESET": ["da1", "da2"],
    "NETWORK_UNLOCK": ["da1", "da2"],
    "IMEI_REPAIR": ["da1", "da2"],
    "BACKUP_FLASH": ["da1", "da2"],
    "BACKUP_SECURITY": ["da1", "da2"],
    "BOOTLOADER_UNLOCK": ["da1", "da2", "sla_payload"],
    "SLA_BYPASS": ["da1", "da2", "sla_payload"],
}


@lru_cache
def _load() -> dict:
    with open(config_path("device_models.json"), "r", encoding="utf-8") as f:
        return json.load(f)


def brands() -> List[str]:
    return sorted(_load().get("brands", {}).keys())


def models(brand: str) -> List[str]:
    return sorted(_load().get("brands", {}).get(brand, {}).get("models", {}).keys())


def model_info(brand: str, model: str) -> dict:
    return _load().get("brands", {}).get(brand, {}).get("models", {}).get(model, {})


def operations_for(brand: str, model: str) -> List[str]:
    return model_info(brand, model).get("operations", [])


def label(operation: str) -> str:
    return OPERATION_LABELS.get(operation, operation)


def payloads_for(operation: str) -> List[str]:
    return OPERATION_PAYLOADS.get(operation, ["da1", "da2"])
